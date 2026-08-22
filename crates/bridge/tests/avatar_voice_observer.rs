#![cfg(unix)]

use std::process::Command;

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
            "focus": "voice-observer-contract",
            "risk_level": "low",
            "updated_at": "2026-08-22T00:00:00Z"
        }))
        .expect("serialize pet fixture"),
    )
    .expect("write pet fixture");
}

fn repo_audio_script() -> std::path::PathBuf {
    std::path::PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("../../scripts/audio_embody.py")
}

fn configure_lan(command: &mut Command) {
    command
        .env("AB_QWEN3_LAN_REMOTE_HOST", "operator@mac.lan")
        .env("AB_QWEN3_LAN_REMOTE_PYTHON", "/opt/qwen/bin/python")
        .env("AB_QWEN3_LAN_WORKER_SOCKET", "/tmp/qwen.sock")
        .env("AB_QWEN3_LAN_HOST_KEY_ALIAS", "mac.lan");
}

#[test]
fn voice_observer_dry_run_is_reviewable_bounded_and_non_owning() {
    let temp = tempfile::tempdir().expect("create tempdir");
    let xdg = temp.path().join("xdg");
    let home = temp.path().join("home");
    write_pet_fixture(&xdg, "voice-observer-plan");

    let output = Command::new(env!("CARGO_BIN_EXE_agent-bridge"))
        .args([
            "avatar",
            "voice-observe",
            "--pet-id",
            "voice-observer-plan",
            "--duration-ms",
            "1",
            "--state-poll-ms",
            "1",
            "--voice-cooldown-secs",
            "1",
            "--voice-max-utterances",
            "99",
            "--qwen-worker",
            temp.path().join("missing.sock").to_str().expect("utf8 path"),
            "--dry-run",
            "--json",
        ])
        .env("HOME", &home)
        .env("XDG_DATA_HOME", &xdg)
        .output()
        .expect("run voice observer dry run");

    assert!(
        output.status.success(),
        "stdout={}; stderr={}",
        String::from_utf8_lossy(&output.stdout),
        String::from_utf8_lossy(&output.stderr)
    );
    let payload: Value = serde_json::from_slice(&output.stdout).expect("parse plan JSON");
    assert_eq!(payload["surface"], "linux_avatar_voice_observer_plan");
    assert_eq!(payload["ready"], false);
    assert_eq!(payload["duration_ms"], 1_000);
    assert_eq!(payload["state_poll_ms"], 100);
    assert_eq!(payload["voice_feedback"]["cooldown_secs"], 30);
    assert_eq!(payload["voice_feedback"]["max_utterances"], 10);
    assert_eq!(payload["voice_feedback"]["voice_profile"], "cute_playful");
    assert_eq!(payload["ownership"]["voice_observer"], true);
    assert_eq!(payload["ownership"]["renderer"], false);
    assert_eq!(payload["ownership"]["presence"], false);
    assert_eq!(payload["ownership"]["pet_state"], false);
    assert_eq!(payload["safety"]["foreground_only"], true);
    assert_eq!(payload["safety"]["initial_state_silent"], true);
    assert_eq!(payload["safety"]["starts_renderer"], false);
    assert_eq!(payload["safety"]["writes_presence"], false);
    assert_eq!(payload["safety"]["writes_pet_sidecar"], false);
    assert!(!xdg.join("agent-bridge").join("state.db").exists());
}

#[test]
fn voice_observer_lan_plan_is_ready_without_renderer_or_presence_ownership() {
    let temp = tempfile::tempdir().expect("create tempdir");
    let xdg = temp.path().join("xdg");
    let home = temp.path().join("home");
    write_pet_fixture(&xdg, "voice-observer-lan");

    let mut command = Command::new(env!("CARGO_BIN_EXE_agent-bridge"));
    command.args([
        "avatar",
        "voice-observe",
        "--pet-id",
        "voice-observer-lan",
        "--voice-backend",
        "qwen3-lan",
        "--voice-script",
        repo_audio_script().to_str().expect("utf8 script path"),
        "--dry-run",
        "--json",
    ]);
    command.env("HOME", &home).env("XDG_DATA_HOME", &xdg);
    configure_lan(&mut command);
    let output = command.output().expect("run LAN voice observer dry run");

    assert!(
        output.status.success(),
        "stdout={}; stderr={}",
        String::from_utf8_lossy(&output.stdout),
        String::from_utf8_lossy(&output.stderr)
    );
    let payload: Value = serde_json::from_slice(&output.stdout).expect("parse plan JSON");
    assert_eq!(payload["ready"], true);
    assert_eq!(payload["voice_feedback"]["backend"], "qwen3-lan");
    assert_eq!(payload["voice_feedback"]["lan_config_ready"], true);
    assert_eq!(payload["voice_feedback"]["lan_dispatcher_ready"], true);
    assert_eq!(payload["ownership"]["renderer"], false);
    assert_eq!(payload["ownership"]["presence"], false);
    assert!(!xdg.join("agent-bridge").join("state.db").exists());
}

#[test]
fn voice_observer_short_live_run_stays_silent_and_non_mutating() {
    let temp = tempfile::tempdir().expect("create tempdir");
    let xdg = temp.path().join("xdg");
    let home = temp.path().join("home");
    write_pet_fixture(&xdg, "voice-observer-live");
    let sidecar = xdg
        .join("agent-bridge")
        .join("pet_state")
        .join("voice-observer-live.json");
    let before = std::fs::read(&sidecar).expect("read initial sidecar");

    let mut command = Command::new(env!("CARGO_BIN_EXE_agent-bridge"));
    command.args([
        "avatar",
        "voice-observe",
        "--pet-id",
        "voice-observer-live",
        "--voice-backend",
        "qwen3-lan",
        "--voice-script",
        repo_audio_script().to_str().expect("utf8 script path"),
        "--duration-ms",
        "1",
        "--state-poll-ms",
        "1",
        "--json",
    ]);
    command.env("HOME", &home).env("XDG_DATA_HOME", &xdg);
    configure_lan(&mut command);
    let output = command.output().expect("run short voice observer");

    assert!(
        output.status.success(),
        "stdout={}; stderr={}",
        String::from_utf8_lossy(&output.stdout),
        String::from_utf8_lossy(&output.stderr)
    );
    let payload: Value = serde_json::from_slice(&output.stdout).expect("parse receipt JSON");
    assert_eq!(payload["surface"], "linux_avatar_voice_observer_receipt");
    assert_eq!(payload["completed"], true);
    assert_eq!(payload["voice_feedback"]["utterance_count"], 0);
    assert_eq!(payload["voice_feedback"]["invocation_count"], 0);
    assert_eq!(payload["ownership"]["renderer"], false);
    assert_eq!(payload["ownership"]["presence"], false);
    assert_eq!(std::fs::read(&sidecar).expect("read final sidecar"), before);
    assert!(!xdg.join("agent-bridge").join("state.db").exists());
}

#[test]
fn voice_observer_help_states_its_non_ownership_boundary() {
    let output = Command::new(env!("CARGO_BIN_EXE_agent-bridge"))
        .args(["avatar", "voice-observe", "--help"])
        .output()
        .expect("run voice observer help");
    assert!(output.status.success());
    let help = String::from_utf8_lossy(&output.stdout);
    assert!(help.contains("without starting a renderer"));
    assert!(help.contains("writing presence"));
    assert!(help.contains("modifying pet state"));
    assert!(help.contains("foreground"));
}
