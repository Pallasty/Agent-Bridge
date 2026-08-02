#![cfg(unix)]

use std::os::unix::fs::PermissionsExt;
use std::path::{Path, PathBuf};
use std::process::{Command, Output};

use serde_json::Value;
use tempfile::TempDir;

fn write_executable(path: &Path, contents: &str) {
    std::fs::write(path, contents).expect("write executable fixture");
    let mut permissions = std::fs::metadata(path)
        .expect("stat executable fixture")
        .permissions();
    permissions.set_mode(0o700);
    std::fs::set_permissions(path, permissions).expect("make executable fixture runnable");
}

fn assert_unsafe_label_rejected_before_db_or_system_probes(operation: &str) {
    let temp = tempfile::tempdir().expect("create tempdir");
    let fake_bin = temp.path().join("fake-bin");
    let home = temp.path().join("home");
    let xdg_data = temp.path().join("xdg-data");
    let system_marker = temp.path().join("system-probe-invoked");
    let program_marker = temp.path().join("plist-program-invoked");
    std::fs::create_dir(&fake_bin).expect("create fake PATH directory");

    write_executable(
        &fake_bin.join("id"),
        "#!/bin/sh\nprintf id >> \"$AB_HEARTBEAT_TEST_SYSTEM_MARKER\"\nprintf 501\n",
    );
    write_executable(
        &fake_bin.join("launchctl"),
        "#!/bin/sh\nprintf launchctl >> \"$AB_HEARTBEAT_TEST_SYSTEM_MARKER\"\nexit 1\n",
    );

    let unsafe_label = temp.path().join("payload");
    let plist = unsafe_label.with_extension("plist");
    let sentinel = temp.path().join("plist-sentinel");
    write_executable(
        &sentinel,
        "#!/bin/sh\nprintf program >> \"$AB_HEARTBEAT_TEST_PROGRAM_MARKER\"\nprintf 'sync-presence heartbeat-health\\n'\n",
    );
    std::fs::write(
        &plist,
        format!(
            r#"<dict>
  <key>ProgramArguments</key>
  <array>
    <string>{}</string>
    <string>avatar</string>
    <string>sync-presence</string>
  </array>
</dict>
"#,
            sentinel.display()
        ),
    )
    .expect("write escaped plist fixture");

    let mut command = Command::new(env!("CARGO_BIN_EXE_agent-bridge"));
    command
        .args([
            "avatar",
            operation,
            "--label",
            unsafe_label.to_str().expect("utf-8 unsafe label"),
        ])
        .env("HOME", &home)
        .env("XDG_DATA_HOME", &xdg_data)
        .env("PATH", &fake_bin)
        .env("AB_HEARTBEAT_TEST_SYSTEM_MARKER", &system_marker)
        .env("AB_HEARTBEAT_TEST_PROGRAM_MARKER", &program_marker);
    if operation == "heartbeat-alert" {
        command.arg("--preview");
    }
    let output = command
        .arg("--json")
        .output()
        .expect("run heartbeat health");

    assert!(
        !output.status.success(),
        "unsafe label must be rejected; stdout={}; stderr={}",
        String::from_utf8_lossy(&output.stdout),
        String::from_utf8_lossy(&output.stderr)
    );
    assert!(
        String::from_utf8_lossy(&output.stderr).contains("invalid heartbeat label"),
        "stderr={}",
        String::from_utf8_lossy(&output.stderr)
    );
    assert!(
        !system_marker.exists(),
        "rejection must precede id/launchctl probes"
    );
    assert!(
        !program_marker.exists(),
        "rejection must precede plist-program execution"
    );
    assert!(
        !xdg_data.join("agent-bridge").exists(),
        "rejection must precede Linux state.db acquisition"
    );
    assert!(
        !home
            .join("Library")
            .join("Application Support")
            .join("agent-bridge")
            .exists(),
        "rejection must precede macOS state.db acquisition"
    );
}

fn alert_paths(home: &Path, label: &str) -> (PathBuf, PathBuf) {
    let dir = home
        .join("Library")
        .join("Application Support")
        .join("agent-bridge")
        .join("avatar_health");
    (
        dir.join(format!("{label}.alert.json")),
        dir.join(format!("{label}.events.jsonl")),
    )
}

fn run_heartbeat_alert(temp: &TempDir, label: &str, preview: bool) -> Output {
    let fake_bin = temp.path().join("fake-bin");
    let home = temp.path().join("home");
    let xdg_data = temp.path().join("xdg-data");
    std::fs::create_dir(&fake_bin).expect("create fake PATH directory");
    write_executable(&fake_bin.join("id"), "#!/bin/sh\nprintf 501\n");
    write_executable(&fake_bin.join("launchctl"), "#!/bin/sh\nexit 1\n");

    let mut command = Command::new(env!("CARGO_BIN_EXE_agent-bridge"));
    command
        .args([
            "avatar",
            "heartbeat-alert",
            "--label",
            label,
            "--project",
            "agent-bridge",
            "--force",
            "--no-notification",
            "--repeat-secs",
            "0",
            "--json",
        ])
        .env("HOME", &home)
        .env("XDG_DATA_HOME", &xdg_data)
        .env("PATH", &fake_bin);
    if preview {
        command.arg("--preview");
    }
    command.output().expect("run heartbeat alert")
}

#[test]
fn heartbeat_health_rejects_unsafe_label_before_db_or_system_probes() {
    assert_unsafe_label_rejected_before_db_or_system_probes("heartbeat-health");
}

#[test]
fn heartbeat_alert_rejects_unsafe_label_before_db_or_system_probes() {
    assert_unsafe_label_rejected_before_db_or_system_probes("heartbeat-alert");
}

#[test]
fn heartbeat_alert_preview_preserves_existing_state_and_event_log_bytes() {
    let temp = tempfile::tempdir().expect("create tempdir");
    let home = temp.path().join("home");
    let label = "com.agentbridge.preview-existing";
    let (state_path, events_path) = alert_paths(&home, label);
    std::fs::create_dir_all(state_path.parent().expect("state parent"))
        .expect("create alert fixture directory");
    let original_state = br#"{
  "last_event_key": "fixture-before-preview",
  "last_emitted_at": 7,
  "sentinel": "state-must-not-change"
}
"#;
    let original_events = b"{\"sentinel\":\"events-must-not-change\"}\n";
    std::fs::write(&state_path, original_state).expect("write state fixture");
    std::fs::write(&events_path, original_events).expect("write events fixture");

    let output = run_heartbeat_alert(&temp, label, true);

    assert!(
        output.status.success(),
        "preview failed; stdout={}; stderr={}",
        String::from_utf8_lossy(&output.stdout),
        String::from_utf8_lossy(&output.stderr)
    );
    let payload: Value = serde_json::from_slice(&output.stdout).expect("parse preview payload");
    assert_eq!(payload["event"]["preview"], true);
    assert_eq!(payload["event"]["should_emit"], true);
    assert_eq!(payload["event"]["emitted"], false);
    assert_eq!(
        std::fs::read(&state_path).expect("read state after preview"),
        original_state
    );
    assert_eq!(
        std::fs::read(&events_path).expect("read events after preview"),
        original_events
    );
}

#[test]
fn heartbeat_alert_preview_does_not_create_state_or_event_log() {
    let temp = tempfile::tempdir().expect("create tempdir");
    let home = temp.path().join("home");
    let label = "com.agentbridge.preview-absent";
    let (state_path, events_path) = alert_paths(&home, label);

    let output = run_heartbeat_alert(&temp, label, true);

    assert!(
        output.status.success(),
        "preview failed; stdout={}; stderr={}",
        String::from_utf8_lossy(&output.stdout),
        String::from_utf8_lossy(&output.stderr)
    );
    assert!(!state_path.exists(), "preview created alert state");
    assert!(!events_path.exists(), "preview created alert event log");
}

#[test]
fn heartbeat_alert_non_preview_still_writes_state_and_event_log() {
    let temp = tempfile::tempdir().expect("create tempdir");
    let home = temp.path().join("home");
    let label = "com.agentbridge.non-preview";
    let (state_path, events_path) = alert_paths(&home, label);

    let output = run_heartbeat_alert(&temp, label, false);

    assert!(
        output.status.success(),
        "alert failed; stdout={}; stderr={}",
        String::from_utf8_lossy(&output.stdout),
        String::from_utf8_lossy(&output.stderr)
    );
    let payload: Value = serde_json::from_slice(&output.stdout).expect("parse alert payload");
    assert_eq!(payload["event"]["preview"], false);
    assert_eq!(payload["event"]["emitted"], true);
    assert!(
        state_path.is_file(),
        "non-preview did not write alert state"
    );
    assert!(
        !std::fs::read(&events_path)
            .expect("read non-preview event log")
            .is_empty(),
        "non-preview event log is empty"
    );
}

#[test]
fn heartbeat_alert_preview_help_declares_no_write_semantics() {
    let output = Command::new(env!("CARGO_BIN_EXE_agent-bridge"))
        .args(["avatar", "heartbeat-alert", "--help"])
        .output()
        .expect("run heartbeat alert help");

    assert!(output.status.success());
    let stdout = String::from_utf8_lossy(&output.stdout);
    assert!(
        stdout.contains("without writing alert state/events"),
        "stdout={stdout}"
    );
    assert!(!stdout.contains("Compute and record the event"));
}
