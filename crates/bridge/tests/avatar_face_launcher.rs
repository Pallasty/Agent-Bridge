#![cfg(target_os = "linux")]

use std::io::{Read, Write};
use std::net::TcpListener;
use std::process::{Command, Output};
use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::Arc;
use std::time::{Duration, Instant};

use serde_json::{json, Value};

fn write_pet_fixture(root: &std::path::Path, pet_id: &str) {
    let dir = root.join("agent-bridge").join("pet_state");
    std::fs::create_dir_all(&dir).expect("create pet fixture directory");
    std::fs::write(
        dir.join(format!("{pet_id}.json")),
        serde_json::to_vec_pretty(&json!({
            "schema_version": 1,
            "pet_id": pet_id,
            "mode": "working",
            "activity_state": "verifying",
            "updated_at": "2026-08-22T00:00:00Z"
        }))
        .expect("serialize fixture"),
    )
    .expect("write fixture");
}

fn launcher_path() -> std::path::PathBuf {
    std::path::PathBuf::from(env!("CARGO_MANIFEST_DIR"))
        .join("../../scripts/dock/face-native-launch.sh")
}

fn audio_script_path() -> std::path::PathBuf {
    std::path::PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("../../scripts/audio_embody.py")
}

fn base_command(temp: &std::path::Path, endpoint: &str) -> Command {
    let mut command = Command::new("bash");
    command
        .arg(launcher_path())
        .env("HOME", temp.join("home"))
        .env("XDG_DATA_HOME", temp.join("xdg"))
        .env("XDG_RUNTIME_DIR", temp.join("runtime"))
        .env("AB_BIN", env!("CARGO_BIN_EXE_agent-bridge"))
        .env("AB_FACE_STATE_URL", endpoint)
        .env("AB_FACE_PET_ID", "face-launcher-voice")
        .env("AB_FACE_SEGMENT_MS", "1000")
        .env("AB_FACE_HEARTBEAT_SECS", "1")
        .env("AB_FACE_VOICE_ENABLED", "1")
        .env("AB_FACE_VOICE_BACKEND", "qwen3-lan")
        .env("AB_FACE_VOICE_SEGMENT_MS", "1000")
        .env("AB_FACE_VOICE_POLL_MS", "100")
        .env("AB_FACE_VOICE_SCRIPT", audio_script_path())
        .env("AB_QWEN3_LAN_REMOTE_HOST", "operator@mac.lan")
        .env("AB_QWEN3_LAN_REMOTE_PYTHON", "/opt/qwen/bin/python")
        .env("AB_QWEN3_LAN_WORKER_SOCKET", "/tmp/qwen.sock")
        .env("AB_QWEN3_LAN_HOST_KEY_ALIAS", "mac.lan");
    command
}

fn run(mut command: Command) -> Output {
    command.output().expect("run face launcher")
}

fn start_http_probe() -> (String, Arc<AtomicBool>, std::thread::JoinHandle<()>) {
    let listener = TcpListener::bind("127.0.0.1:0").expect("bind HTTP probe");
    listener.set_nonblocking(true).expect("nonblocking probe");
    let endpoint = format!(
        "http://{}/avatar-surface/linux-renderer-state",
        listener.local_addr().unwrap()
    );
    let stop = Arc::new(AtomicBool::new(false));
    let thread_stop = Arc::clone(&stop);
    let handle = std::thread::spawn(move || {
        while !thread_stop.load(Ordering::Relaxed) {
            match listener.accept() {
                Ok((mut stream, _)) => {
                    let mut request = [0_u8; 1024];
                    let _ = stream.read(&mut request);
                    let _ = stream.write_all(
                        b"HTTP/1.1 200 OK\r\nContent-Length: 2\r\nConnection: close\r\n\r\n{}",
                    );
                }
                Err(error) if error.kind() == std::io::ErrorKind::WouldBlock => {
                    std::thread::sleep(Duration::from_millis(10));
                }
                Err(_) => break,
            }
        }
    });
    (endpoint, stop, handle)
}

#[test]
fn face_launcher_supervises_voice_observer_and_reports_its_pid() {
    let temp = tempfile::tempdir().expect("create tempdir");
    std::fs::create_dir_all(temp.path().join("runtime")).expect("create runtime dir");
    write_pet_fixture(&temp.path().join("xdg"), "face-launcher-voice");
    let sidecar = temp
        .path()
        .join("xdg/agent-bridge/pet_state/face-launcher-voice.json");
    let sidecar_before = std::fs::read(&sidecar).expect("read initial sidecar");
    let (endpoint, stop_http, http_thread) = start_http_probe();

    let started = run(base_command(temp.path(), &endpoint));
    assert!(
        started.status.success(),
        "stdout={}; stderr={}",
        String::from_utf8_lossy(&started.stdout),
        String::from_utf8_lossy(&started.stderr)
    );
    assert!(String::from_utf8_lossy(&started.stdout).contains("sparse voice: enabled"));

    let deadline = Instant::now() + Duration::from_secs(5);
    let status = loop {
        let mut command = base_command(temp.path(), &endpoint);
        command.args(["--status", "--json"]);
        let output = run(command);
        if output.status.success() {
            if let Ok(payload) = serde_json::from_slice::<Value>(&output.stdout) {
                if payload["voice_supervisor_pid"].is_number() {
                    break payload;
                }
            }
        }
        assert!(
            Instant::now() < deadline,
            "voice observer did not become observable"
        );
        std::thread::sleep(Duration::from_millis(100));
    };
    assert_eq!(status["surface"], "linux_avatar_native_entrypoint_status");
    assert_eq!(status["voice_configured"], true);
    assert!(status["supervisor_pid"].is_number());
    assert!(status["voice_supervisor_pid"].is_number());

    let mut stop = base_command(temp.path(), &endpoint);
    stop.arg("--stop");
    let stopped = run(stop);
    assert!(stopped.status.success());
    std::thread::sleep(Duration::from_millis(200));

    let mut final_status = base_command(temp.path(), &endpoint);
    final_status.args(["--status", "--json"]);
    let payload: Value =
        serde_json::from_slice(&run(final_status).stdout).expect("final status JSON");
    assert_eq!(payload["state"], "stopped");
    assert!(payload["voice_supervisor_pid"].is_null());
    assert!(payload["voice_observer_pid"].is_null());
    assert_eq!(
        std::fs::read(&sidecar).expect("read final sidecar"),
        sidecar_before
    );

    stop_http.store(true, Ordering::Relaxed);
    http_thread.join().expect("join HTTP probe");
}

#[test]
fn face_launcher_fails_closed_when_enabled_voice_is_not_ready() {
    let temp = tempfile::tempdir().expect("create tempdir");
    std::fs::create_dir_all(temp.path().join("runtime")).expect("create runtime dir");
    write_pet_fixture(&temp.path().join("xdg"), "face-launcher-voice");
    let (endpoint, stop_http, http_thread) = start_http_probe();

    let mut command = base_command(temp.path(), &endpoint);
    command
        .env_remove("AB_QWEN3_LAN_REMOTE_HOST")
        .env_remove("AB_QWEN3_LAN_REMOTE_PYTHON")
        .env_remove("AB_QWEN3_LAN_WORKER_SOCKET")
        .env_remove("AB_QWEN3_LAN_HOST_KEY_ALIAS");
    let output = run(command);
    assert!(!output.status.success());
    assert!(String::from_utf8_lossy(&output.stderr).contains("voice observer is not ready"));
    assert!(!temp.path().join("runtime/ab-face-native.pid").exists());
    assert!(!temp.path().join("xdg/agent-bridge/state.db").exists());

    stop_http.store(true, Ordering::Relaxed);
    http_thread.join().expect("join HTTP probe");
}
