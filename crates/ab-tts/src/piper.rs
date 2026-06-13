//! Piper VITS backend (opt-in behind the `piper` feature).
//!
//! Text → phonemes via the bundled **`piper_phonemize` CLI** (it links espeak-ng,
//! GPL-3.0; we shell to it like `whisper-cli` / `ffmpeg`, so this crate links no
//! GPL C code and needs no `bindgen`/`libclang`), then the VITS `.onnx` forward
//! pass via `ort`. 22.05 kHz (read from the voice config).
//!
//! `piper_phonemize` already emits the model-ready integer **phoneme id** sequence
//! (BOS/pad/EOS interleaved) per sentence as JSONL, so the backend feeds those ids
//! straight to the model — no per-voice `phoneme_id_map` re-implementation needed.
//! Multi-sentence input yields one JSONL line per sentence; each is synthesized and
//! the audio concatenated with a short pause (matches piper's own behaviour).
//!
//! Honest boundary unchanged: the produced [`AudioBuf`] is played + bus-verified by
//! the lane's falsifier; this module only owns text→audio.

use std::io::Write as _;
use std::path::{Path, PathBuf};
use std::process::{Command, Stdio};
use std::sync::Mutex;

use ort::session::builder::GraphOptimizationLevel;
use ort::session::Session;
use ort::value::Tensor;

use crate::{AudioBuf, TtsBackend, TtsError};

// Inference defaults; overridden per-voice by the `.onnx.json` `inference` block.
const DEFAULT_SAMPLE_RATE: u32 = 22_050;
const DEFAULT_NOISE_SCALE: f32 = 0.667;
const DEFAULT_LENGTH_SCALE: f32 = 1.0;
const DEFAULT_NOISE_W: f32 = 0.8;
// Silence inserted BETWEEN synthesized sentences (piper does the same), in seconds.
const SENTENCE_GAP_SECS: f32 = 0.2;

/// Per-voice synthesis config read from the model's sidecar `.onnx.json`.
#[derive(Debug, Clone)]
pub struct PiperVoiceConfig {
    pub sample_rate: u32,
    pub noise_scale: f32,
    pub length_scale: f32,
    pub noise_w: f32,
}

impl PiperVoiceConfig {
    /// Parse the fields we need (`audio.sample_rate`, `inference.{noise_scale,
    /// length_scale,noise_w}`) from a piper voice `.onnx.json`. Missing fields fall
    /// back to piper's documented defaults rather than failing.
    pub fn parse(json_bytes: &[u8]) -> Result<Self, TtsError> {
        let v: serde_json::Value = serde_json::from_slice(json_bytes)
            .map_err(|e| TtsError::Model(format!("parse voice .onnx.json: {e}")))?;
        let sample_rate = v
            .get("audio")
            .and_then(|a| a.get("sample_rate"))
            .and_then(|s| s.as_u64())
            .map(|s| s as u32)
            .unwrap_or(DEFAULT_SAMPLE_RATE);
        let inf = v.get("inference");
        let f = |k: &str, d: f32| -> f32 {
            inf.and_then(|i| i.get(k))
                .and_then(|x| x.as_f64())
                .map(|x| x as f32)
                .unwrap_or(d)
        };
        Ok(Self {
            sample_rate,
            noise_scale: f("noise_scale", DEFAULT_NOISE_SCALE),
            length_scale: f("length_scale", DEFAULT_LENGTH_SCALE),
            noise_w: f("noise_w", DEFAULT_NOISE_W),
        })
    }
}

/// Parse `piper_phonemize` JSONL stdout into one phoneme-id sequence per sentence.
/// Pure (no subprocess) so the parse is unit-tested. Skips blank lines; a line
/// missing/!-array `phoneme_ids` is an honest error (we never fabricate ids).
pub fn parse_phoneme_id_lines(stdout: &str) -> Result<Vec<Vec<i64>>, TtsError> {
    let mut out = Vec::new();
    for line in stdout.lines() {
        let line = line.trim();
        if line.is_empty() {
            continue;
        }
        let v: serde_json::Value = serde_json::from_str(line)
            .map_err(|e| TtsError::Phonemize(format!("piper_phonemize line not JSON: {e}")))?;
        let arr = v
            .get("phoneme_ids")
            .and_then(|a| a.as_array())
            .ok_or_else(|| {
                TtsError::Phonemize("piper_phonemize line has no phoneme_ids array".into())
            })?;
        let ids: Vec<i64> = arr.iter().filter_map(|x| x.as_i64()).collect();
        if !ids.is_empty() {
            out.push(ids);
        }
    }
    Ok(out)
}

/// Grapheme→phoneme-id via the external `piper_phonemize` CLI. Holds the binary +
/// espeak data + library dir so each call is a clean, offline subprocess.
pub struct PiperPhonemizer {
    bin: PathBuf,
    espeak_data: PathBuf,
    lib_dir: PathBuf,
    language: String,
}

impl PiperPhonemizer {
    /// Run `piper_phonemize -l <lang> --espeak_data <dir>` over `text` and return
    /// one phoneme-id sequence per sentence.
    pub fn phoneme_id_lines(&self, text: &str) -> Result<Vec<Vec<i64>>, TtsError> {
        if !self.bin.is_file() {
            return Err(TtsError::Phonemize(format!(
                "piper_phonemize not found: {:?}",
                self.bin
            )));
        }
        let mut cmd = Command::new(&self.bin);
        cmd.arg("-l")
            .arg(&self.language)
            .arg("--espeak_data")
            .arg(&self.espeak_data)
            .env("LD_LIBRARY_PATH", self.ld_library_path())
            .stdin(Stdio::piped())
            .stdout(Stdio::piped())
            .stderr(Stdio::piped());
        let mut child = cmd
            .spawn()
            .map_err(|e| TtsError::Phonemize(format!("spawn piper_phonemize: {e}")))?;
        child
            .stdin
            .take()
            .ok_or_else(|| TtsError::Phonemize("no stdin pipe".into()))?
            .write_all(text.as_bytes())
            .map_err(|e| TtsError::Phonemize(format!("write text: {e}")))?;
        let out = child
            .wait_with_output()
            .map_err(|e| TtsError::Phonemize(format!("piper_phonemize wait: {e}")))?;
        if !out.status.success() {
            let err = String::from_utf8_lossy(&out.stderr);
            return Err(TtsError::Phonemize(format!(
                "piper_phonemize exit {:?}: {}",
                out.status.code(),
                err.trim()
            )));
        }
        let stdout = String::from_utf8_lossy(&out.stdout);
        let lines = parse_phoneme_id_lines(&stdout)?;
        if lines.is_empty() {
            return Err(TtsError::Phonemize(format!("no phonemes for {text:?}")));
        }
        Ok(lines)
    }

    /// Prepend our library dir to any inherited `LD_LIBRARY_PATH` so the CLI finds
    /// `libpiper_phonemize.so` + `libespeak-ng.so` without clobbering system libs.
    fn ld_library_path(&self) -> String {
        match std::env::var("LD_LIBRARY_PATH") {
            Ok(existing) if !existing.is_empty() => {
                format!("{}:{}", self.lib_dir.display(), existing)
            }
            _ => self.lib_dir.display().to_string(),
        }
    }
}

/// `ort::Session::run` takes `&mut self` but [`TtsBackend::synthesize`] is `&self`,
/// so the session is serialized behind a [`Mutex`] (one engine, one forward at a
/// time — the realistic embodiment cadence).
pub struct PiperBackend {
    session: Mutex<Session>,
    phonemizer: PiperPhonemizer,
    config: PiperVoiceConfig,
    /// The single voice this model renders (piper voice packs are 1-voice here).
    voice_name: String,
}

impl PiperBackend {
    /// Load from explicit paths: the VITS `.onnx` (its `.onnx.json` sits beside it),
    /// the `piper_phonemize` binary, the `espeak-ng-data` dir, the shared-library dir
    /// (holding `libpiper_phonemize.so` + `libespeak-ng.so`), and the espeak language.
    pub fn load(
        model_path: impl AsRef<Path>,
        phonemize_bin: impl AsRef<Path>,
        espeak_data: impl AsRef<Path>,
        lib_dir: impl AsRef<Path>,
        language: &str,
    ) -> Result<Self, TtsError> {
        let model_path = model_path.as_ref();
        let json_path = sidecar_json(model_path);
        let json = std::fs::read(&json_path)
            .map_err(|e| TtsError::Io(format!("read voice config {json_path:?}: {e}")))?;
        let config = PiperVoiceConfig::parse(&json)?;

        let session = Session::builder()
            .map_err(|e| TtsError::Model(format!("session builder: {e}")))?
            .with_optimization_level(GraphOptimizationLevel::Level3)
            .map_err(|e| TtsError::Model(format!("optimization level: {e}")))?
            .with_intra_threads(intra_threads())
            .map_err(|e| TtsError::Model(format!("intra threads: {e}")))?
            .commit_from_file(model_path)
            .map_err(|e| TtsError::Model(format!("load model {model_path:?}: {e}")))?;

        let voice_name = model_path
            .file_stem()
            .map(|s| s.to_string_lossy().to_string())
            .unwrap_or_else(|| "piper".to_string());

        Ok(Self {
            session: Mutex::new(session),
            phonemizer: PiperPhonemizer {
                bin: phonemize_bin.as_ref().to_path_buf(),
                espeak_data: espeak_data.as_ref().to_path_buf(),
                lib_dir: lib_dir.as_ref().to_path_buf(),
                language: language.to_string(),
            },
            config,
            voice_name,
        })
    }

    /// Resolve assets from env / cache, then [`load`]. No network at call time; the
    /// error names exactly what to provision. Env: `AB_TTS_PIPER_MODEL`,
    /// `AB_TTS_PIPER_PHONEMIZE`, `AB_TTS_PIPER_ESPEAK_DATA`, `AB_TTS_PIPER_LIBDIR`,
    /// `AB_TTS_PIPER_LANG` (default `en-us`).
    ///
    /// [`load`]: PiperBackend::load
    pub fn from_cache() -> Result<Self, TtsError> {
        let model = resolve_model()?;
        let phonemize = resolve_phonemize_bin()?;
        let lib_dir = std::env::var("AB_TTS_PIPER_LIBDIR")
            .map(PathBuf::from)
            .unwrap_or_else(|_| {
                phonemize
                    .parent()
                    .map(|p| p.to_path_buf())
                    .unwrap_or_default()
            });
        let espeak_data = std::env::var("AB_TTS_PIPER_ESPEAK_DATA")
            .map(PathBuf::from)
            .unwrap_or_else(|_| lib_dir.join("espeak-ng-data"));
        let lang = std::env::var("AB_TTS_PIPER_LANG").unwrap_or_else(|_| "en-us".to_string());
        Self::load(model, phonemize, espeak_data, lib_dir, &lang)
    }

    /// One VITS forward over a single sentence's phoneme ids → audio samples.
    fn synth_ids(&self, ids: Vec<i64>) -> Result<Vec<f32>, TtsError> {
        let n = ids.len() as i64;
        let input_t = Tensor::from_array((vec![1i64, n], ids))
            .map_err(|e| TtsError::Inference(format!("input tensor: {e}")))?;
        let lengths_t = Tensor::from_array((vec![1i64], vec![n]))
            .map_err(|e| TtsError::Inference(format!("input_lengths tensor: {e}")))?;
        let scales_t = Tensor::from_array((
            vec![3i64],
            vec![
                self.config.noise_scale,
                self.config.length_scale,
                self.config.noise_w,
            ],
        ))
        .map_err(|e| TtsError::Inference(format!("scales tensor: {e}")))?;

        let inputs = ort::inputs! {
            "input" => input_t,
            "input_lengths" => lengths_t,
            "scales" => scales_t,
        };

        let mut session = self
            .session
            .lock()
            .map_err(|_| TtsError::Inference("session mutex poisoned".into()))?;
        let outputs = session
            .run(inputs)
            .map_err(|e| TtsError::Inference(format!("onnx run: {e}")))?;
        let (_shape, data) = outputs[0]
            .try_extract_tensor::<f32>()
            .map_err(|e| TtsError::Inference(format!("extract audio: {e}")))?;
        Ok(data.to_vec())
    }
}

impl TtsBackend for PiperBackend {
    fn id(&self) -> &'static str {
        "piper"
    }
    fn sample_rate(&self) -> u32 {
        self.config.sample_rate
    }
    fn voices(&self) -> Vec<String> {
        vec![self.voice_name.clone()]
    }
    fn synthesize(&self, text: &str, _voice: &str) -> Result<AudioBuf, TtsError> {
        // `_voice` is ignored: a piper voice pack is a single-voice model (the voice
        // IS the model file). Phonemize per sentence, synth each, concatenate.
        let sentences = self.phonemizer.phoneme_id_lines(text)?;
        let gap = vec![0.0f32; (SENTENCE_GAP_SECS * self.config.sample_rate as f32) as usize];
        let mut samples = Vec::new();
        for (i, ids) in sentences.into_iter().enumerate() {
            if i > 0 {
                samples.extend_from_slice(&gap);
            }
            samples.extend(self.synth_ids(ids)?);
        }
        if samples.is_empty() {
            return Err(TtsError::Inference("model produced empty audio".into()));
        }
        Ok(AudioBuf::new(samples, self.config.sample_rate))
    }
}

fn intra_threads() -> usize {
    std::thread::available_parallelism()
        .map(|n| n.get().min(4))
        .unwrap_or(2)
}

/// `<model>.onnx` → `<model>.onnx.json` (piper's sidecar config convention).
fn sidecar_json(model_path: &Path) -> PathBuf {
    let mut s = model_path.as_os_str().to_os_string();
    s.push(".json");
    PathBuf::from(s)
}

fn cache_dir() -> PathBuf {
    if let Ok(d) = std::env::var("AB_TTS_CACHE") {
        return PathBuf::from(d);
    }
    if let Ok(d) = std::env::var("XDG_CACHE_HOME") {
        return PathBuf::from(d).join("ab-tts");
    }
    if let Ok(h) = std::env::var("HOME") {
        return PathBuf::from(h).join(".cache").join("ab-tts");
    }
    PathBuf::from(".")
}

const MODEL_FILE: &str = "en_US-lessac-medium.onnx";
const MODEL_URL: &str = "https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/lessac/medium/en_US-lessac-medium.onnx";

fn resolve_model() -> Result<PathBuf, TtsError> {
    if let Ok(p) = std::env::var("AB_TTS_PIPER_MODEL") {
        let pb = PathBuf::from(p);
        return if pb.is_file() {
            Ok(pb)
        } else {
            Err(TtsError::Model(format!(
                "AB_TTS_PIPER_MODEL={pb:?} is not a file"
            )))
        };
    }
    let pb = cache_dir().join(MODEL_FILE);
    if pb.is_file() {
        return Ok(pb);
    }
    Err(TtsError::Model(format!(
        "Piper voice missing: {pb:?} (+ its {pb:?}.json)\n  fetch once:  curl -L -o {pb:?} {MODEL_URL}  (and the matching .onnx.json)\n  (or set AB_TTS_PIPER_MODEL). Synthesis stays offline; one-time provisioning."
    )))
}

fn resolve_phonemize_bin() -> Result<PathBuf, TtsError> {
    if let Ok(p) = std::env::var("AB_TTS_PIPER_PHONEMIZE") {
        let pb = PathBuf::from(p);
        return if pb.is_file() {
            Ok(pb)
        } else {
            Err(TtsError::Phonemize(format!(
                "AB_TTS_PIPER_PHONEMIZE={pb:?} is not a file"
            )))
        };
    }
    let pb = cache_dir().join("piper").join("piper_phonemize");
    if pb.is_file() {
        return Ok(pb);
    }
    Err(TtsError::Phonemize(format!(
        "piper_phonemize missing: {pb:?}\n  install the piper release (bundles piper_phonemize + libespeak-ng + espeak-ng-data)\n  or set AB_TTS_PIPER_PHONEMIZE / AB_TTS_PIPER_LIBDIR / AB_TTS_PIPER_ESPEAK_DATA."
    )))
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn voice_config_parses_fields_and_defaults() {
        let json = br#"{"audio":{"sample_rate":22050},"inference":{"noise_scale":0.667,"length_scale":1.0,"noise_w":0.8}}"#;
        let c = PiperVoiceConfig::parse(json).expect("parse");
        assert_eq!(c.sample_rate, 22_050);
        assert!((c.noise_scale - 0.667).abs() < 1e-6);
        assert!((c.length_scale - 1.0).abs() < 1e-6);
        assert!((c.noise_w - 0.8).abs() < 1e-6);
        // missing inference block -> documented defaults, not a failure
        let c2 = PiperVoiceConfig::parse(br#"{"audio":{"sample_rate":16000}}"#).expect("parse2");
        assert_eq!(c2.sample_rate, 16_000);
        assert!((c2.noise_scale - DEFAULT_NOISE_SCALE).abs() < 1e-6);
        assert!((c2.length_scale - DEFAULT_LENGTH_SCALE).abs() < 1e-6);
    }

    #[test]
    fn voice_config_missing_sample_rate_uses_default() {
        let c = PiperVoiceConfig::parse(br#"{}"#).expect("parse");
        assert_eq!(c.sample_rate, DEFAULT_SAMPLE_RATE);
    }

    #[test]
    fn phoneme_id_lines_parses_one_seq_per_sentence() {
        // two sentences -> two JSONL lines -> two id sequences (blank lines ignored)
        let stdout = "{\"phoneme_ids\":[1,0,20,0,2],\"text\":\"Hi.\"}\n\n{\"phoneme_ids\":[1,0,35,0,2],\"text\":\"Bye.\"}\n";
        let lines = parse_phoneme_id_lines(stdout).expect("parse");
        assert_eq!(lines.len(), 2);
        assert_eq!(lines[0], vec![1, 0, 20, 0, 2]);
        assert_eq!(lines[1], vec![1, 0, 35, 0, 2]);
    }

    #[test]
    fn phoneme_id_lines_missing_array_is_honest_error() {
        // a line without phoneme_ids must error, never silently fabricate ids
        let r = parse_phoneme_id_lines("{\"phonemes\":[\"h\"],\"text\":\"h\"}");
        assert!(
            matches!(r, Err(TtsError::Phonemize(_))),
            "expected Phonemize error, got {r:?}"
        );
        // non-JSON line errors too
        assert!(parse_phoneme_id_lines("not json").is_err());
    }

    #[test]
    fn sidecar_json_appends_json() {
        assert_eq!(
            sidecar_json(Path::new("/x/en_US-lessac-medium.onnx")),
            PathBuf::from("/x/en_US-lessac-medium.onnx.json")
        );
    }
}
