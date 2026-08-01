#![cfg(unix)]

use std::os::unix::fs::PermissionsExt;
use std::path::Path;
use std::process::Command;

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

#[test]
fn heartbeat_health_rejects_unsafe_label_before_db_or_system_probes() {
    assert_unsafe_label_rejected_before_db_or_system_probes("heartbeat-health");
}

#[test]
fn heartbeat_alert_rejects_unsafe_label_before_db_or_system_probes() {
    assert_unsafe_label_rejected_before_db_or_system_probes("heartbeat-alert");
}
