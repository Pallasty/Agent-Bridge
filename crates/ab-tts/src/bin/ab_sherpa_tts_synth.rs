//! CLI and persistent Worker v1 bridge for offline Sherpa-ONNX Chinese VITS.
use ab_tts::sherpa::{SherpaVitsBackend, SherpaVitsConfig};
use ab_tts::TtsBackend;
use serde_json::{json, Value};
use std::io::{BufRead, BufReader, Write};
use std::os::unix::fs::PermissionsExt;
use std::os::unix::net::{UnixListener, UnixStream};
use std::path::{Path, PathBuf};
use std::process::exit;

const PROTOCOL: &str = "ab.tts.worker.v1";
const ENGINE: &str = "sherpa-onnx";

fn fail(message: impl AsRef<str>) -> ! {
    println!("{}", json!({"ok": false, "error": message.as_ref()}));
    exit(1);
}

fn load_backend() -> (SherpaVitsBackend, PathBuf) {
    let model_dir = std::env::var("AB_TTS_SHERPA_MODEL_DIR")
        .map(PathBuf::from)
        .unwrap_or_else(|_| fail("AB_TTS_SHERPA_MODEL_DIR is required"));
    let voice_map = std::env::var("AB_TTS_SHERPA_VOICE_MAP").unwrap_or_else(|_| {
        fail("AB_TTS_SHERPA_VOICE_MAP is required; use explicit name=sid entries")
    });
    let voices =
        SherpaVitsConfig::parse_voice_map(&voice_map).unwrap_or_else(|e| fail(e.to_string()));
    let backend = SherpaVitsBackend::from_config(SherpaVitsConfig {
        model_dir: model_dir.clone(),
        voice_map: voices,
        num_threads: std::env::var("AB_TTS_SHERPA_THREADS")
            .ok()
            .and_then(|v| v.parse().ok())
            .unwrap_or(4),
        noise_scale: 0.667,
        noise_scale_w: 0.8,
        silence_scale: 0.2,
    })
    .unwrap_or_else(|e| fail(e.to_string()));
    (backend, model_dir)
}

fn identity(backend: &SherpaVitsBackend, model_dir: &Path) -> Value {
    json!({
        "protocol": PROTOCOL,
        "backend": "sherpa-vits",
        "engine": ENGINE,
        "model": model_dir.display().to_string(),
        "device": "cpu",
        "dtype": std::env::var("AB_TTS_SHERPA_DTYPE").unwrap_or_else(|_| "unknown".into()),
        "capabilities": ["zh", "multi_speaker", "speed"],
        "voices": backend.voices(),
        "speakers": backend.model_num_speakers().unwrap_or(-1),
    })
}

fn worker_reply(request: &Value, backend: &SherpaVitsBackend, model_dir: &Path) -> Value {
    let mut base = identity(backend, model_dir);
    let Some(object) = base.as_object_mut() else {
        unreachable!()
    };
    match request.get("op").and_then(Value::as_str) {
        Some("health") => {
            object.insert("ok".into(), json!(true));
            object.insert("state".into(), json!("ready"));
        }
        Some("synthesize") => {
            let instruct = request
                .get("instruct")
                .and_then(Value::as_str)
                .unwrap_or("");
            if !instruct.trim().is_empty() {
                object.insert("ok".into(), json!(false));
                object.insert(
                    "detail".into(),
                    json!("sherpa-onnx worker does not support instruct"),
                );
                return base;
            }
            let text = request
                .get("text")
                .and_then(Value::as_str)
                .unwrap_or("")
                .trim();
            let output = request.get("output").and_then(Value::as_str).unwrap_or("");
            let voice = request
                .get("speaker")
                .and_then(Value::as_str)
                .unwrap_or("narrator_calm");
            let speed = request.get("speed").and_then(Value::as_f64).unwrap_or(1.0) as f32;
            if text.is_empty() || output.is_empty() || !Path::new(output).is_absolute() {
                object.insert("ok".into(), json!(false));
                object.insert(
                    "detail".into(),
                    json!("synthesize requires text and an absolute output path"),
                );
                return base;
            }
            match backend.synthesize_with_speed(text, voice, speed) {
                Ok(audio) => match audio.write_wav(output) {
                    Ok(()) => {
                        object.insert("ok".into(), json!(true));
                        object.insert("voice".into(), json!(voice));
                        object.insert("sample_rate".into(), json!(audio.sample_rate));
                        object.insert("samples".into(), json!(audio.samples.len()));
                        object.insert("instruct_applied".into(), json!(false));
                        object.insert("worker".into(), json!("unix_socket"));
                    }
                    Err(e) => {
                        object.insert("ok".into(), json!(false));
                        object.insert("detail".into(), json!(format!("write wav: {e}")));
                    }
                },
                Err(e) => {
                    object.insert("ok".into(), json!(false));
                    object.insert("detail".into(), json!(e.to_string()));
                }
            }
        }
        _ => {
            object.insert("ok".into(), json!(false));
            object.insert("detail".into(), json!("unsupported op"));
        }
    }
    base
}

fn serve_connection(mut stream: UnixStream, backend: &SherpaVitsBackend, model_dir: &Path) {
    let mut line = String::new();
    let reply = match BufReader::new(&stream).read_line(&mut line) {
        Ok(0) => {
            json!({"ok": false, "protocol": PROTOCOL, "engine": ENGINE, "detail": "empty request"})
        }
        Ok(_) => match serde_json::from_str::<Value>(&line) {
            Ok(request) => worker_reply(&request, backend, model_dir),
            Err(e) => {
                json!({"ok": false, "protocol": PROTOCOL, "engine": ENGINE, "detail": format!("invalid JSON: {e}")})
            }
        },
        Err(e) => {
            json!({"ok": false, "protocol": PROTOCOL, "engine": ENGINE, "detail": format!("read request: {e}")})
        }
    };
    let _ = writeln!(stream, "{reply}");
}

fn serve(socket_path: &Path, backend: SherpaVitsBackend, model_dir: PathBuf) -> ! {
    if socket_path.exists() {
        std::fs::remove_file(socket_path)
            .unwrap_or_else(|e| fail(format!("remove stale socket: {e}")));
    }
    if let Some(parent) = socket_path.parent() {
        std::fs::create_dir_all(parent).unwrap_or_else(|e| fail(format!("create socket dir: {e}")));
        std::fs::set_permissions(parent, std::fs::Permissions::from_mode(0o700))
            .unwrap_or_else(|e| fail(format!("protect socket dir: {e}")));
    }
    let listener = UnixListener::bind(socket_path)
        .unwrap_or_else(|e| fail(format!("bind {}: {e}", socket_path.display())));
    std::fs::set_permissions(socket_path, std::fs::Permissions::from_mode(0o600))
        .unwrap_or_else(|e| fail(format!("protect socket: {e}")));
    println!(
        "{}",
        worker_reply(&json!({"op":"health"}), &backend, &model_dir)
    );
    for stream in listener.incoming() {
        match stream {
            Ok(stream) => serve_connection(stream, &backend, &model_dir),
            Err(e) => eprintln!("accept failed: {e}"),
        }
    }
    fail("listener stopped")
}

fn main() {
    let mut text = None;
    let mut out = None;
    let mut socket_path = None;
    let mut voice = "narrator_calm".to_owned();
    let mut speed = 1.0_f32;
    let mut args = std::env::args().skip(1);
    while let Some(arg) = args.next() {
        match arg.as_str() {
            "--text" => text = args.next(),
            "--out" => out = args.next(),
            "--voice" => voice = args.next().unwrap_or(voice),
            "--speed" => speed = args.next().and_then(|v| v.parse().ok()).unwrap_or(speed),
            "--socket" => socket_path = args.next().map(PathBuf::from),
            other => fail(format!("unknown argument {other:?}")),
        }
    }
    let (backend, model_dir) = load_backend();
    if let Some(socket_path) = socket_path {
        serve(&socket_path, backend, model_dir);
    }
    let text = text.unwrap_or_else(|| fail("missing --text"));
    let out = out.unwrap_or_else(|| fail("missing --out"));
    let audio = backend
        .synthesize_with_speed(&text, &voice, speed)
        .unwrap_or_else(|e| fail(e.to_string()));
    audio
        .write_wav(&out)
        .unwrap_or_else(|e| fail(format!("write wav: {e}")));
    println!(
        "{}",
        json!({"ok":true,"backend":"sherpa-vits","voice":voice,
        "out":out,"samples":audio.samples.len(),"sample_rate":audio.sample_rate,
        "speakers":backend.model_num_speakers().unwrap_or(-1)})
    );
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn protocol_and_engine_are_stable() {
        assert_eq!(PROTOCOL, "ab.tts.worker.v1");
        assert_eq!(ENGINE, "sherpa-onnx");
    }
}
