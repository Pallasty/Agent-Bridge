use std::process::Command;

const RUNNER_LABEL: &str = "com.agentbridge.avatar-cortex.safety-test";

fn install_runner_command(home: &std::path::Path) -> Command {
    let mut command = Command::new(env!("CARGO_BIN_EXE_agent-bridge"));
    command
        .args([
            "avatar",
            "install-cortex-runner",
            "--project",
            "agent-bridge-safety-test",
            "--label",
            RUNNER_LABEL,
            "--bin",
            "/bin/true",
        ])
        .env("HOME", home);
    command
}

#[test]
fn test_install_cortex_runner_rejects_disabled_replay_before_writing_plist() {
    let home = tempfile::tempdir().expect("temp HOME");
    let launch_agents = home.path().join("Library").join("LaunchAgents");
    let logs = home
        .path()
        .join("Library")
        .join("Logs")
        .join("agent-bridge");
    let plist = launch_agents.join(format!("{RUNNER_LABEL}.plist"));

    let output = install_runner_command(home.path())
        .arg("--no-load")
        .output()
        .expect("run install-cortex-runner");

    assert!(
        !output.status.success(),
        "disabled replay runner must be rejected; stdout={}; stderr={}",
        String::from_utf8_lossy(&output.stdout),
        String::from_utf8_lossy(&output.stderr)
    );
    assert!(
        String::from_utf8_lossy(&output.stderr).contains("avatar cortex replay is unavailable"),
        "stderr={}",
        String::from_utf8_lossy(&output.stderr)
    );
    assert!(!plist.exists(), "runner rejection must not write a plist");
    assert!(
        !launch_agents.exists(),
        "runner rejection must not create the plist parent"
    );
    assert!(
        !logs.exists(),
        "runner rejection must not create the launchd log parent"
    );
}

#[test]
fn test_install_cortex_runner_dry_run_remains_effect_free() {
    let home = tempfile::tempdir().expect("temp HOME");
    let output = install_runner_command(home.path())
        .arg("--dry-run")
        .output()
        .expect("run install-cortex-runner --dry-run");

    assert!(
        output.status.success(),
        "dry-run should remain available for inspection; stderr={}",
        String::from_utf8_lossy(&output.stderr)
    );
    assert!(String::from_utf8_lossy(&output.stdout).contains("<plist"));
    assert!(
        !home.path().join("Library").exists(),
        "dry-run must not create launchd paths"
    );
}
