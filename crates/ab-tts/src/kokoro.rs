//! Kokoro-82M backend (StyleTTS2, Apache-2.0 model, 24 kHz output).
//!
//! **MIT-clean path:** grapheme→phoneme via `misaki-rs` (MIT) — Kokoro's own g2p
//! with embedded lexicons + POS-tagger weights (no runtime data files, no espeak,
//! no GPL). This is why Kokoro is the license-clean primary: the entire
//! text→phoneme→audio path stays MIT/Apache (misaki-rs MIT + ort MIT/Apache +
//! Kokoro model Apache-2.0).
//!
//! Pipeline (mirrors hexgrad/Kokoro-82M + thewh1teagle/kokoro-onnx exactly):
//! 1. text → IPA phonemes (`MisakiPhonemizer`).
//! 2. phonemes → token ids via the fixed 114-symbol [`KOKORO_VOCAB`]; out-of-vocab
//!    chars are dropped (matches the reference `filter(p in vocab)`).
//! 3. style vector = `voices[voice][token_count]` — a `[256]` row indexed by the
//!    *unpadded* token count (the model conditions prosody on utterance length).
//! 4. tokens wrapped `[0, …, 0]` (pad sentinel) → `ort` ONNX forward
//!    (`tokens` int64, `style` f32[1,256], `speed` f32[1]) → `audio` f32 @ 24 kHz.
//!
//! The 326 MB model + 28 MB voice pack are **not** vendored in git — they are
//! resolved from env / a cache dir at load time (see [`KokoroBackend::from_cache`]),
//! with an honest error telling the caller what to fetch. Synthesis itself is
//! fully offline.

use crate::{AudioBuf, Phonemizer, TtsBackend, TtsError};
use misaki_rs::{Language, G2P};
use std::collections::HashMap;
use std::path::{Path, PathBuf};
use std::sync::Mutex;

use ort::session::builder::GraphOptimizationLevel;
use ort::session::{Session, SessionInputValue};
use ort::value::Tensor;

/// Kokoro's fixed phoneme→token-id vocabulary (114 symbols), copied verbatim from
/// hexgrad/Kokoro-82M `config.json`. Ids are intentionally non-contiguous (they
/// match the trained embedding table). Characters absent here are dropped during
/// tokenization — the reference does the same (`filter(p in vocab)`), so an
/// out-of-vocab phoneme contributes nothing rather than corrupting the sequence.
pub const KOKORO_VOCAB: &[(char, i64)] = &[
    (';', 1),
    (':', 2),
    (',', 3),
    ('.', 4),
    ('!', 5),
    ('?', 6),
    ('\u{2014}', 9),
    ('\u{2026}', 10),
    ('"', 11),
    ('(', 12),
    (')', 13),
    ('\u{201c}', 14),
    ('\u{201d}', 15),
    (' ', 16),
    ('\u{303}', 17),
    ('\u{2a3}', 18),
    ('\u{2a5}', 19),
    ('\u{2a6}', 20),
    ('\u{2a8}', 21),
    ('\u{1d5d}', 22),
    ('\u{ab67}', 23),
    ('A', 24),
    ('I', 25),
    ('O', 31),
    ('Q', 33),
    ('S', 35),
    ('T', 36),
    ('W', 39),
    ('Y', 41),
    ('\u{1d4a}', 42),
    ('a', 43),
    ('b', 44),
    ('c', 45),
    ('d', 46),
    ('e', 47),
    ('f', 48),
    ('h', 50),
    ('i', 51),
    ('j', 52),
    ('k', 53),
    ('l', 54),
    ('m', 55),
    ('n', 56),
    ('o', 57),
    ('p', 58),
    ('q', 59),
    ('r', 60),
    ('s', 61),
    ('t', 62),
    ('u', 63),
    ('v', 64),
    ('w', 65),
    ('x', 66),
    ('y', 67),
    ('z', 68),
    ('\u{251}', 69),
    ('\u{250}', 70),
    ('\u{252}', 71),
    ('\u{e6}', 72),
    ('\u{3b2}', 75),
    ('\u{254}', 76),
    ('\u{255}', 77),
    ('\u{e7}', 78),
    ('\u{256}', 80),
    ('\u{f0}', 81),
    ('\u{2a4}', 82),
    ('\u{259}', 83),
    ('\u{25a}', 85),
    ('\u{25b}', 86),
    ('\u{25c}', 87),
    ('\u{25f}', 90),
    ('\u{261}', 92),
    ('\u{265}', 99),
    ('\u{268}', 101),
    ('\u{26a}', 102),
    ('\u{29d}', 103),
    ('\u{26f}', 110),
    ('\u{270}', 111),
    ('\u{14b}', 112),
    ('\u{273}', 113),
    ('\u{272}', 114),
    ('\u{274}', 115),
    ('\u{f8}', 116),
    ('\u{278}', 118),
    ('\u{3b8}', 119),
    ('\u{153}', 120),
    ('\u{279}', 123),
    ('\u{27e}', 125),
    ('\u{27b}', 126),
    ('\u{281}', 128),
    ('\u{27d}', 129),
    ('\u{282}', 130),
    ('\u{283}', 131),
    ('\u{288}', 132),
    ('\u{2a7}', 133),
    ('\u{28a}', 135),
    ('\u{28b}', 136),
    ('\u{28c}', 138),
    ('\u{263}', 139),
    ('\u{264}', 140),
    ('\u{3c7}', 142),
    ('\u{28e}', 143),
    ('\u{292}', 147),
    ('\u{294}', 148),
    ('\u{2c8}', 156),
    ('\u{2cc}', 157),
    ('\u{2d0}', 158),
    ('\u{2b0}', 162),
    ('\u{2b2}', 164),
    ('\u{2193}', 169),
    ('\u{2192}', 171),
    ('\u{2197}', 172),
    ('\u{2198}', 173),
    ('\u{1d7b}', 177),
];

/// Kokoro context limit: max phonemes per forward pass (pad tokens excluded).
const MAX_PHONEME_LENGTH: usize = 510;
/// Kokoro native output sample rate.
const SAMPLE_RATE: u32 = 24_000;
/// Per-token style-vector dimensionality.
const STYLE_DIM: usize = 256;

// ───────────────────────────── phonemizer ──────────────────────────────────

/// Kokoro grapheme→phoneme via `misaki-rs` (MIT, `default-features=false` → no
/// espeak/GPL/C). US English by default; set `british=true` for the `b*` voices.
/// Self-contained — embedded lexicon + POS tagger, no runtime data files.
/// Out-of-vocabulary words map to misaki's `❓` placeholder (no espeak fallback).
pub struct MisakiPhonemizer {
    g2p: G2P,
}

impl MisakiPhonemizer {
    /// `british=false` → US English (Kokoro `a*` voices); `true` → British (`b*`).
    pub fn new(british: bool) -> Self {
        let lang = if british {
            Language::EnglishGB
        } else {
            Language::EnglishUS
        };
        Self {
            g2p: G2P::new(lang),
        }
    }
}

impl Default for MisakiPhonemizer {
    fn default() -> Self {
        Self::new(false)
    }
}

impl Phonemizer for MisakiPhonemizer {
    fn phonemize(&self, text: &str) -> Result<String, TtsError> {
        if text.trim().is_empty() {
            return Err(TtsError::Phonemize("empty input text".into()));
        }
        let (phonemes, _tokens) = self
            .g2p
            .g2p(text)
            .map_err(|e| TtsError::Phonemize(format!("misaki g2p: {e}")))?;
        if phonemes.trim().is_empty() {
            return Err(TtsError::Phonemize(format!(
                "misaki produced no phonemes for {text:?}"
            )));
        }
        Ok(phonemes)
    }
}

// ───────────────────────────── voice pack ──────────────────────────────────

/// A parsed Kokoro voice pack: each voice name → its `rows × STYLE_DIM` style
/// matrix, flattened row-major. Synthesis selects a row by phoneme-token count.
struct VoicePack {
    voices: HashMap<String, Vec<f32>>,
    rows: usize,
}

impl VoicePack {
    /// Parse `voices-v1.0.bin` — a NumPy `.npz` (a **STORED**, i.e. uncompressed,
    /// ZIP of one `.npy` per voice). We walk ZIP local file headers only to read
    /// each entry's *name* and locate its data; the byte length comes from the
    /// self-describing `.npy` header, so we never touch the ZIP size fields
    /// (which numpy writes as Zip64) and need neither a zip crate nor inflate.
    fn parse(bytes: &[u8]) -> Result<Self, TtsError> {
        const LFH: u32 = 0x0403_4b50; // "PK\x03\x04" — local file header
        let mut voices = HashMap::new();
        let mut rows_seen: Option<usize> = None;
        let mut pos = 0usize;
        while pos + 4 <= bytes.len() {
            if read_u32(bytes, pos)? != LFH {
                break; // central directory / EOCD reached → entries done
            }
            if pos + 30 > bytes.len() {
                return Err(TtsError::Voice("truncated zip local header".into()));
            }
            let flag = read_u16(bytes, pos + 6)?;
            if flag & 0x08 != 0 {
                // bit 3 = sizes in a trailing data descriptor; numpy never sets it
                return Err(TtsError::Voice("zip data descriptors unsupported".into()));
            }
            let fnlen = read_u16(bytes, pos + 26)? as usize;
            let extralen = read_u16(bytes, pos + 28)? as usize;
            let name_start = pos + 30;
            let name_end = name_start + fnlen;
            if name_end > bytes.len() {
                return Err(TtsError::Voice("truncated zip filename".into()));
            }
            let fname = std::str::from_utf8(&bytes[name_start..name_end])
                .map_err(|_| TtsError::Voice("non-utf8 voice name".into()))?
                .to_string();
            let data_start = name_end + extralen;
            let (shape, data, consumed) = parse_npy(bytes, data_start)?;
            let rows = *shape.first().unwrap_or(&0);
            let per_row: usize = shape.iter().skip(1).product();
            if per_row != STYLE_DIM {
                return Err(TtsError::Voice(format!(
                    "voice {fname:?}: expected {STYLE_DIM} values/row, got {per_row} (shape {shape:?})"
                )));
            }
            rows_seen = Some(rows);
            let name = fname.strip_suffix(".npy").unwrap_or(&fname).to_string();
            voices.insert(name, data);
            pos = data_start + consumed;
        }
        if voices.is_empty() {
            return Err(TtsError::Voice("no voices found in pack".into()));
        }
        Ok(Self {
            voices,
            rows: rows_seen.unwrap_or(0),
        })
    }

    /// The `[STYLE_DIM]` style row for `voice`, selected by phoneme-token count
    /// (clamped into `[0, rows)` — the reference indexes `voice[len(tokens)]`).
    fn style(&self, voice: &str, token_count: usize) -> Result<Vec<f32>, TtsError> {
        let flat = self
            .voices
            .get(voice)
            .ok_or_else(|| TtsError::Voice(format!("voice {voice:?} not in pack")))?;
        if self.rows == 0 {
            return Err(TtsError::Voice("voice pack has no rows".into()));
        }
        let idx = token_count.min(self.rows - 1);
        let start = idx * STYLE_DIM;
        let end = start + STYLE_DIM;
        flat.get(start..end)
            .map(|s| s.to_vec())
            .ok_or_else(|| TtsError::Voice("style row out of bounds".into()))
    }

    fn names(&self) -> Vec<String> {
        let mut v: Vec<String> = self.voices.keys().cloned().collect();
        v.sort();
        v
    }
}

/// Parse a NumPy `.npy` blob at offset `off`. Returns `(shape, f32 data, bytes
/// consumed)`. Only little-endian `<f4`, C-order is supported (all Kokoro voices
/// are). `consumed` lets the caller step to the next ZIP entry.
fn parse_npy(bytes: &[u8], off: usize) -> Result<(Vec<usize>, Vec<f32>, usize), TtsError> {
    const MAGIC: &[u8] = b"\x93NUMPY";
    if off + 10 > bytes.len() || &bytes[off..off + 6] != MAGIC {
        return Err(TtsError::Voice("bad .npy magic".into()));
    }
    let major = bytes[off + 6];
    let (hlen, hstart) = if major >= 2 {
        (read_u32(bytes, off + 8)? as usize, off + 12)
    } else {
        (read_u16(bytes, off + 8)? as usize, off + 10)
    };
    let hend = hstart + hlen;
    if hend > bytes.len() {
        return Err(TtsError::Voice("truncated .npy header".into()));
    }
    let header = std::str::from_utf8(&bytes[hstart..hend])
        .map_err(|_| TtsError::Voice("non-utf8 .npy header".into()))?;
    if !header.contains("'<f4'") {
        return Err(TtsError::Voice(format!(
            "unsupported .npy dtype (want '<f4'): {header}"
        )));
    }
    if header.contains("'fortran_order': True") {
        return Err(TtsError::Voice("fortran-order .npy unsupported".into()));
    }
    let shape = parse_npy_shape(header)?;
    let nelem: usize = shape.iter().product();
    let dstart = hend;
    let dend = dstart
        .checked_add(
            nelem
                .checked_mul(4)
                .ok_or_else(|| TtsError::Voice("npy size overflow".into()))?,
        )
        .ok_or_else(|| TtsError::Voice("npy size overflow".into()))?;
    if dend > bytes.len() {
        return Err(TtsError::Voice("truncated .npy data".into()));
    }
    let mut data = Vec::with_capacity(nelem);
    let mut i = dstart;
    while i < dend {
        data.push(f32::from_le_bytes([
            bytes[i],
            bytes[i + 1],
            bytes[i + 2],
            bytes[i + 3],
        ]));
        i += 4;
    }
    Ok((shape, data, (hend - off) + nelem * 4))
}

/// Extract the shape tuple from a `.npy` header dict string, e.g.
/// `…'shape': (510, 1, 256), …` → `[510, 1, 256]`.
fn parse_npy_shape(header: &str) -> Result<Vec<usize>, TtsError> {
    const KEY: &str = "'shape':";
    let ks = header
        .find(KEY)
        .ok_or_else(|| TtsError::Voice("no shape in .npy header".into()))?;
    let after = &header[ks + KEY.len()..];
    let lp = after
        .find('(')
        .ok_or_else(|| TtsError::Voice("malformed shape (no '(')".into()))?;
    let rp = after[lp..]
        .find(')')
        .ok_or_else(|| TtsError::Voice("malformed shape (no ')')".into()))?
        + lp;
    let mut dims = Vec::new();
    for part in after[lp + 1..rp].split(',') {
        let t = part.trim();
        if t.is_empty() {
            continue; // trailing comma of a 1-tuple, or "()" scalar
        }
        dims.push(
            t.parse::<usize>()
                .map_err(|_| TtsError::Voice(format!("bad shape dim {t:?}")))?,
        );
    }
    if dims.is_empty() {
        return Err(TtsError::Voice("empty/scalar shape".into()));
    }
    Ok(dims)
}

fn read_u16(b: &[u8], at: usize) -> Result<u16, TtsError> {
    b.get(at..at + 2)
        .map(|s| u16::from_le_bytes([s[0], s[1]]))
        .ok_or_else(|| TtsError::Voice("read u16 out of bounds".into()))
}

fn read_u32(b: &[u8], at: usize) -> Result<u32, TtsError> {
    b.get(at..at + 4)
        .map(|s| u32::from_le_bytes([s[0], s[1], s[2], s[3]]))
        .ok_or_else(|| TtsError::Voice("read u32 out of bounds".into()))
}

// ───────────────────────────── tokenizer ───────────────────────────────────

/// Map an IPA phoneme string to Kokoro token ids, dropping out-of-vocab chars and
/// truncating to [`MAX_PHONEME_LENGTH`] (pure — unit-tested without the model).
fn tokenize_phonemes(vocab: &HashMap<char, i64>, phonemes: &str) -> Vec<i64> {
    phonemes
        .chars()
        .filter_map(|c| vocab.get(&c).copied())
        .take(MAX_PHONEME_LENGTH)
        .collect()
}

// ───────────────────────────── backend ─────────────────────────────────────

/// Kokoro-82M synthesizer: misaki g2p → fixed vocab → `ort` ONNX forward → 24 kHz.
/// The `ort` [`Session::run`] takes `&mut self`, but [`TtsBackend::synthesize`] is
/// `&self`, so the session lives behind a [`Mutex`] (synthesis is serialized — one
/// engine, one forward pass at a time, which is the realistic embodiment cadence).
pub struct KokoroBackend {
    session: Mutex<Session>,
    voices: VoicePack,
    vocab: HashMap<char, i64>,
    phonemizer: MisakiPhonemizer,
    /// ONNX token input name: `"tokens"` (v1.0 export) or `"input_ids"` (newer).
    token_input: String,
    /// Whether `speed` is int32 (newer `input_ids` export) vs f32 (`tokens`).
    speed_is_int: bool,
}

impl KokoroBackend {
    /// Load from explicit model + voice-pack paths. `british=true` selects the GB
    /// lexicon (for `b*` voices); US English otherwise.
    pub fn load(
        model_path: impl AsRef<Path>,
        voices_path: impl AsRef<Path>,
        british: bool,
    ) -> Result<Self, TtsError> {
        let model_path = model_path.as_ref();
        let voices_path = voices_path.as_ref();

        let voices_bytes = std::fs::read(voices_path)
            .map_err(|e| TtsError::Io(format!("read voices {voices_path:?}: {e}")))?;
        let voices = VoicePack::parse(&voices_bytes)?;

        let builder = Session::builder()
            .map_err(|e| TtsError::Model(format!("session builder: {e}")))?
            .with_optimization_level(GraphOptimizationLevel::Level3)
            .map_err(|e| TtsError::Model(format!("optimization level: {e}")))?;
        let mut builder = builder
            .with_intra_threads(intra_threads())
            .map_err(|e| TtsError::Model(format!("intra threads: {e}")))?;
        let session = builder
            .commit_from_file(model_path)
            .map_err(|e| TtsError::Model(format!("load model {model_path:?}: {e}")))?;

        // Detect token input name + speed dtype from the model's actual signature.
        let in_names: Vec<&str> = session.inputs().iter().map(|o| o.name()).collect();
        let (token_input, speed_is_int) = if in_names.contains(&"input_ids") {
            ("input_ids".to_string(), true)
        } else {
            ("tokens".to_string(), false)
        };

        Ok(Self {
            session: Mutex::new(session),
            voices,
            vocab: KOKORO_VOCAB.iter().copied().collect(),
            phonemizer: MisakiPhonemizer::new(british),
            token_input,
            speed_is_int,
        })
    }

    /// Resolve the model + voice pack from env / a cache dir, then [`load`]. No
    /// network fetch — provisioning is a one-time prep step (keeps synthesis
    /// offline and the crate dependency-light); the error names exactly what to
    /// download and where. Env overrides: `AB_TTS_KOKORO_MODEL`,
    /// `AB_TTS_KOKORO_VOICES`. Cache dir: `$AB_TTS_CACHE` → `$XDG_CACHE_HOME/ab-tts`
    /// → `~/.cache/ab-tts`.
    ///
    /// [`load`]: KokoroBackend::load
    pub fn from_cache(british: bool) -> Result<Self, TtsError> {
        let (model, voices) = resolve_kokoro_assets()?;
        Self::load(model, voices, british)
    }

    /// Synthesize at the given speed (`0.5..=2.0`; default path uses `1.0`).
    pub fn synthesize_at(&self, text: &str, voice: &str, speed: f32) -> Result<AudioBuf, TtsError> {
        let phonemes = self.phonemizer.phonemize(text)?;
        let tokens = tokenize_phonemes(&self.vocab, &phonemes);
        if tokens.is_empty() {
            return Err(TtsError::Phonemize(format!(
                "no in-vocab phonemes for {text:?} (phonemes={phonemes:?})"
            )));
        }
        // style is indexed by the UNPADDED token count (matches the reference).
        let style = self.voices.style(voice, tokens.len())?;

        // pad sentinel 0 at both ends: [[0, *tokens, 0]]
        let mut padded = Vec::with_capacity(tokens.len() + 2);
        padded.push(0i64);
        padded.extend_from_slice(&tokens);
        padded.push(0i64);
        let seq_len = padded.len() as i64;

        let tokens_t = Tensor::from_array((vec![1i64, seq_len], padded))
            .map_err(|e| TtsError::Inference(format!("tokens tensor: {e}")))?;
        let style_t = Tensor::from_array((vec![1i64, STYLE_DIM as i64], style))
            .map_err(|e| TtsError::Inference(format!("style tensor: {e}")))?;
        let speed_v: SessionInputValue = if self.speed_is_int {
            Tensor::from_array((vec![1i64], vec![speed as i32]))
                .map_err(|e| TtsError::Inference(format!("speed tensor: {e}")))?
                .into()
        } else {
            Tensor::from_array((vec![1i64], vec![speed]))
                .map_err(|e| TtsError::Inference(format!("speed tensor: {e}")))?
                .into()
        };

        let inputs = ort::inputs! {
            self.token_input.as_str() => tokens_t,
            "style" => style_t,
            "speed" => speed_v,
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
        let samples = data.to_vec();
        drop(outputs);
        drop(session);

        if samples.is_empty() {
            return Err(TtsError::Inference("model produced empty audio".into()));
        }
        Ok(AudioBuf::new(samples, SAMPLE_RATE))
    }
}

impl TtsBackend for KokoroBackend {
    fn id(&self) -> &'static str {
        "kokoro"
    }
    fn sample_rate(&self) -> u32 {
        SAMPLE_RATE
    }
    fn voices(&self) -> Vec<String> {
        self.voices.names()
    }
    fn synthesize(&self, text: &str, voice: &str) -> Result<AudioBuf, TtsError> {
        self.synthesize_at(text, voice, 1.0)
    }
}

/// Bounded intra-op thread count — cap at 4 so a synthesis on a shared box never
/// monopolizes cores (the embodiment lane is latency-tolerant, not throughput-bound).
fn intra_threads() -> usize {
    std::thread::available_parallelism()
        .map(|n| n.get().min(4))
        .unwrap_or(2)
}

const MODEL_FILE: &str = "kokoro-v1.0.onnx";
const VOICES_FILE: &str = "voices-v1.0.bin";
const MODEL_URL: &str =
    "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/kokoro-v1.0.onnx";
const VOICES_URL: &str =
    "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/voices-v1.0.bin";

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

fn resolve_one(env_key: &str, file: &str, url: &str) -> Result<PathBuf, TtsError> {
    if let Ok(p) = std::env::var(env_key) {
        let pb = PathBuf::from(p);
        return if pb.is_file() {
            Ok(pb)
        } else {
            Err(TtsError::Model(format!("{env_key}={pb:?} is not a file")))
        };
    }
    let dir = cache_dir();
    let pb = dir.join(file);
    if pb.is_file() {
        return Ok(pb);
    }
    Err(TtsError::Model(format!(
        "Kokoro asset missing: {pb:?}\n  fetch once:  mkdir -p {dir:?} && curl -L -o {pb:?} {url}\n  (or set {env_key} to an existing file). Synthesis stays offline; this is a one-time provisioning step."
    )))
}

fn resolve_kokoro_assets() -> Result<(PathBuf, PathBuf), TtsError> {
    Ok((
        resolve_one("AB_TTS_KOKORO_MODEL", MODEL_FILE, MODEL_URL)?,
        resolve_one("AB_TTS_KOKORO_VOICES", VOICES_FILE, VOICES_URL)?,
    ))
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn misaki_phonemizes_english() {
        let p = MisakiPhonemizer::new(false);
        let ph = p.phonemize("hello world").expect("phonemes");
        assert!(!ph.trim().is_empty(), "expected non-empty phonemes");
        // both "hello" and "world" carry an /l/; cheap, non-brittle presence check
        assert!(ph.contains('l'), "expected an l phoneme, got: {ph:?}");
    }

    #[test]
    fn empty_input_is_honest_error() {
        let p = MisakiPhonemizer::new(false);
        assert!(p.phonemize("").is_err());
        assert!(p.phonemize("   ").is_err());
    }

    #[test]
    fn vocab_is_the_114_symbol_kokoro_table() {
        let vocab: HashMap<char, i64> = KOKORO_VOCAB.iter().copied().collect();
        assert_eq!(vocab.len(), 114, "Kokoro vocab must be exactly 114 symbols");
        // spot-check fixed ids that anchor the trained embedding table
        assert_eq!(vocab.get(&' '), Some(&16));
        assert_eq!(vocab.get(&'a'), Some(&43));
        assert_eq!(vocab.get(&'\u{2c8}'), Some(&156)); // ˈ primary stress
    }

    #[test]
    fn tokenize_maps_known_and_drops_unknown() {
        let vocab: HashMap<char, i64> = KOKORO_VOCAB.iter().copied().collect();
        // 'a'→43, ' '→16, 'b'→44; '€' and '✓' are not phonemes → dropped.
        let ids = tokenize_phonemes(&vocab, "a\u{20ac}b \u{2713}a");
        assert_eq!(ids, vec![43, 44, 16, 43]);
    }

    #[test]
    fn tokenize_truncates_to_context_limit() {
        let vocab: HashMap<char, i64> = KOKORO_VOCAB.iter().copied().collect();
        let long = "a".repeat(MAX_PHONEME_LENGTH + 50);
        assert_eq!(tokenize_phonemes(&vocab, &long).len(), MAX_PHONEME_LENGTH);
    }

    // ── synthetic-npz fixtures: prove the parser without the 28 MB asset ──

    fn make_npy(shape: &[usize], data: &[f32]) -> Vec<u8> {
        let dims = shape
            .iter()
            .map(|d| d.to_string())
            .collect::<Vec<_>>()
            .join(", ");
        let dict = format!("{{'descr': '<f4', 'fortran_order': False, 'shape': ({dims}), }}");
        let mut header = dict.into_bytes();
        // numpy pads the header so (10 + len) is a multiple of 64, ending in \n.
        // Our parser doesn't require it, but we mimic real files for fidelity.
        let mut total = 10 + header.len() + 1;
        while total % 64 != 0 {
            header.push(b' ');
            total += 1;
        }
        header.push(b'\n');
        let mut out = Vec::new();
        out.extend_from_slice(b"\x93NUMPY");
        out.push(1);
        out.push(0); // version 1.0
        out.extend_from_slice(&(header.len() as u16).to_le_bytes());
        out.extend_from_slice(&header);
        for &f in data {
            out.extend_from_slice(&f.to_le_bytes());
        }
        out
    }

    fn make_npz(entries: &[(&str, Vec<u8>)]) -> Vec<u8> {
        let mut out = Vec::new();
        for (name, npy) in entries {
            out.extend_from_slice(&0x0403_4b50u32.to_le_bytes()); // local file header
            out.extend_from_slice(&[0u8; 2]); // version needed
            out.extend_from_slice(&[0u8; 2]); // flags (no data descriptor)
            out.extend_from_slice(&[0u8; 2]); // method = 0 (STORED)
            out.extend_from_slice(&[0u8; 4]); // mod time + date
            out.extend_from_slice(&[0u8; 4]); // crc32 (parser ignores)
            out.extend_from_slice(&(npy.len() as u32).to_le_bytes()); // csize
            out.extend_from_slice(&(npy.len() as u32).to_le_bytes()); // usize
            out.extend_from_slice(&(name.len() as u16).to_le_bytes()); // fnlen
            out.extend_from_slice(&0u16.to_le_bytes()); // extralen
            out.extend_from_slice(name.as_bytes());
            out.extend_from_slice(npy);
        }
        out.extend_from_slice(&0x0201_4b50u32.to_le_bytes()); // central dir → stop
        out
    }

    #[test]
    fn voicepack_parses_synthetic_npz_and_indexes_by_token_count() {
        // 2 voices, 3 rows × (1 × 4) — row r filled with value (10*v + r).
        let dim = 4usize;
        let rows = 3usize;
        let mk = |v: f32| -> Vec<f32> {
            let mut d = Vec::new();
            for r in 0..rows {
                for _ in 0..dim {
                    d.push(10.0 * v + r as f32);
                }
            }
            d
        };
        let npz = make_npz(&[
            ("af_test.npy", make_npy(&[rows, 1, dim], &mk(1.0))),
            ("bf_other.npy", make_npy(&[rows, 1, dim], &mk(2.0))),
        ]);
        // STYLE_DIM is 256 in prod; the parser checks per_row==STYLE_DIM. This
        // fixture's per_row (4) ≠ STYLE_DIM ⇒ honest rejection — proves the guard.
        // (`match` rather than `unwrap_err` so VoicePack needn't derive Debug.)
        let err = match VoicePack::parse(&npz) {
            Ok(_) => panic!("fixture dim must be rejected by the STYLE_DIM guard"),
            Err(e) => e,
        };
        assert!(format!("{err}").contains("values/row"));
    }

    #[test]
    fn voicepack_parses_real_width_npz_and_clamps_index() {
        // Use the production STYLE_DIM so parse succeeds, then exercise indexing.
        let rows = 3usize;
        let mut data = Vec::new();
        for r in 0..rows {
            for _ in 0..STYLE_DIM {
                data.push(r as f32); // row r is all-r → trivially checkable
            }
        }
        let npz = make_npz(&[("af_x.npy", make_npy(&[rows, 1, STYLE_DIM], &data))]);
        let pack = VoicePack::parse(&npz).expect("parse");
        assert_eq!(pack.names(), vec!["af_x".to_string()]);
        assert_eq!(pack.rows, rows);

        // row 1 → all 1.0, length STYLE_DIM
        let row1 = pack.style("af_x", 1).expect("row1");
        assert_eq!(row1.len(), STYLE_DIM);
        assert!(row1.iter().all(|&x| (x - 1.0).abs() < 1e-6));

        // token_count beyond rows clamps to the last row (rows-1 = 2)
        let clamped = pack.style("af_x", 999).expect("clamped");
        assert!(clamped.iter().all(|&x| (x - 2.0).abs() < 1e-6));

        // missing voice → honest error, not a panic
        assert!(pack.style("zz_missing", 0).is_err());
    }
}
