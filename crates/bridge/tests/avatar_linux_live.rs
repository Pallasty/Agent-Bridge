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
}
