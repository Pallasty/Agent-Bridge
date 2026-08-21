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
            "focus": "eap-1a",
            "risk_level": "low",
            "updated_at": "2026-08-20T00:00:00Z"
        }))
        .expect("serialize pet fixture"),
    )
    .expect("write pet fixture");
}

#[test]
fn linux_live_dry_run_is_stable_non_mutating_and_action_free() {
    let temp = tempfile::tempdir().expect("create tempdir");
    let xdg = temp.path().join("xdg");
    let home = temp.path().join("home");
    write_pet_fixture(&xdg, "eap-live-test");

    let output = Command::new(env!("CARGO_BIN_EXE_agent-bridge"))
        .args([
            "avatar",
            "linux-live",
            "--project",
            "Agent Bridge",
            "--pet-id",
            "eap-live-test",
            "--duration-ms",
            "1",
            "--heartbeat-interval-secs",
            "1",
            "--state-poll-ms",
            "1",
            "--dry-run",
            "--json",
        ])
        .env("HOME", &home)
        .env("XDG_DATA_HOME", &xdg)
        .env("XDG_SESSION_TYPE", "wayland")
        .env("XDG_CURRENT_DESKTOP", "sway")
        .env("WAYLAND_DISPLAY", "wayland-test")
        .env("SWAYSOCK", "/tmp/sway-test.sock")
        .output()
        .expect("run linux-live dry run");

    assert!(
        output.status.success(),
        "stdout={}; stderr={}",
        String::from_utf8_lossy(&output.stdout),
        String::from_utf8_lossy(&output.stderr)
    );
    let payload: Value = serde_json::from_slice(&output.stdout).expect("parse plan JSON");
    assert_eq!(payload["surface"], "linux_avatar_live_plan");
    assert_eq!(payload["dry_run"], true);
    assert_eq!(payload["backend"]["recommended"], "native_transparent");
    assert_eq!(payload["presence"]["stable_identity"], true);
    assert_eq!(
        payload["presence"]["session_id"],
        "com.agentbridge.avatar-live.agent-bridge"
    );
    assert_eq!(payload["presence"]["pet_id"], "eap-live-test");
    assert_eq!(payload["presence"]["heartbeat_interval_secs"], 5);
    assert_eq!(payload["renderer"]["duration_ms"], 1_000);
    assert_eq!(payload["renderer"]["state_poll"]["poll_ms"], 100);
    assert_eq!(payload["observation"]["enabled"], true);
    assert_eq!(payload["observation"]["read_only"], true);
    assert_eq!(payload["observation"]["configured_poll_ms"], 100);
    assert!(payload["observation"]["does_not_measure"]
        .as_array()
        .expect("observation exclusions")
        .contains(&json!("physical_audio")));
    assert_eq!(
        payload["renderer"]["sprite"]["asset"],
        "xiao-shu-v3-ai-soft-bounce-v1"
    );
    assert_eq!(payload["safety"]["foreground_only"], true);
    assert_eq!(payload["safety"]["installs_service"], false);
    assert_eq!(payload["safety"]["writes_presence_only"], true);
    assert_eq!(payload["safety"]["writes_pet_sidecar"], false);
    assert_eq!(payload["safety"]["emits_audio"], false);
    assert_eq!(payload["safety"]["controls_desktop"], false);
    assert_eq!(payload["safety"]["executes_actions"], false);
    assert_eq!(payload["safety"]["enables_embodiment_runtime_p4"], false);
    assert!(
        !xdg.join("agent-bridge").join("state.db").exists(),
        "dry run must not acquire or create state.db"
    );
}

#[test]
fn linux_live_help_states_the_foreground_non_control_boundary() {
    let output = Command::new(env!("CARGO_BIN_EXE_agent-bridge"))
        .args(["avatar", "linux-live", "--help"])
        .output()
        .expect("run linux-live help");
    assert!(output.status.success());
    let help = String::from_utf8_lossy(&output.stdout);
    assert!(help.contains("owner-local Linux embodiment loop"));
    assert!(help.contains("foreground"));
    assert!(help.contains("emits no audio"));
    assert!(help.contains("controls no desktop input"));
    assert!(help.contains("Qwen3-TTS"));
}

#[test]
fn linux_live_voice_feedback_is_explicit_bounded_and_fail_closed() {
    let temp = tempfile::tempdir().expect("create tempdir");
    let xdg = temp.path().join("xdg");
    let home = temp.path().join("home");
    write_pet_fixture(&xdg, "eap-live-voice-test");
    let missing_worker = temp.path().join("missing-qwen.sock");

    let output = Command::new(env!("CARGO_BIN_EXE_agent-bridge"))
        .args([
            "avatar",
            "linux-live",
            "--project",
            "agent-bridge",
            "--pet-id",
            "eap-live-voice-test",
            "--voice-feedback",
            "--qwen-worker",
            missing_worker.to_str().expect("utf8 worker path"),
            "--voice-cooldown-secs",
            "1",
            "--voice-max-utterances",
            "99",
            "--dry-run",
            "--json",
        ])
        .env("HOME", &home)
        .env("XDG_DATA_HOME", &xdg)
        .env("XDG_SESSION_TYPE", "wayland")
        .env("XDG_CURRENT_DESKTOP", "sway")
        .env("WAYLAND_DISPLAY", "wayland-test")
        .env("SWAYSOCK", "/tmp/sway-test.sock")
        .output()
        .expect("run voice-enabled linux-live dry run");

    assert!(
        output.status.success(),
        "stdout={}; stderr={}",
        String::from_utf8_lossy(&output.stdout),
        String::from_utf8_lossy(&output.stderr)
    );
    let payload: Value = serde_json::from_slice(&output.stdout).expect("parse plan JSON");
    assert_eq!(payload["ready"], false);
    assert_eq!(payload["voice_feedback"]["enabled"], true);
    assert_eq!(payload["voice_feedback"]["backend"], "qwen3");
    assert_eq!(payload["voice_feedback"]["worker_socket_ready"], false);
    assert_eq!(payload["voice_feedback"]["script_contract_ready"], true);
    assert_eq!(payload["voice_feedback"]["python_ready"], true);
    assert_eq!(payload["voice_feedback"]["cooldown_secs"], 30);
    assert_eq!(payload["voice_feedback"]["max_utterances"], 10);
    assert_eq!(payload["voice_feedback"]["initial_state_silent"], true);
    assert_eq!(payload["voice_feedback"]["fixed_lines_only"], true);
    assert_eq!(payload["safety"]["audio_default_off"], true);
    assert_eq!(payload["safety"]["emits_audio"], true);
    assert_eq!(payload["safety"]["writes_presence_only"], false);
    assert_eq!(payload["safety"]["persistent_writes_presence_only"], true);
    assert_eq!(payload["safety"]["creates_ephemeral_audio_files"], true);
    assert_eq!(payload["safety"]["controls_desktop"], false);
    assert!(!xdg.join("agent-bridge").join("state.db").exists());
}
