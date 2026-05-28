use std::fs;
use std::os::unix::fs::PermissionsExt;
use std::path::{Path, PathBuf};
use std::process::Command;

fn make_executable(path: &Path) {
    let mut perms = fs::metadata(path).expect("metadata").permissions();
    perms.set_mode(0o755);
    fs::set_permissions(path, perms).expect("chmod");
}

fn write_executable(path: &Path, body: &str) {
    fs::write(path, body).expect("write executable");
    make_executable(path);
}

fn test_root(name: &str) -> PathBuf {
    let root = std::env::temp_dir().join(format!(
        "agent-bridge-{name}-{}-{}",
        std::process::id(),
        std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)
            .expect("time")
            .as_nanos()
    ));
    fs::create_dir_all(&root).expect("create temp root");
    root
}

#[test]
fn wrapper_exposes_user_cli_bins_to_child_processes() {
    let root = test_root("wrapper-env");
    let home = root.join("home");
    let local_bin = home.join(".local/bin");
    let npm_bin = home.join(".npm-global/bin");
    let cargo_bin = home.join(".cargo/bin");
    fs::create_dir_all(&local_bin).expect("local bin");
    fs::create_dir_all(&npm_bin).expect("npm bin");
    fs::create_dir_all(&cargo_bin).expect("cargo bin");

    let claude = local_bin.join("claude");
    write_executable(&claude, "#!/usr/bin/env bash\nexit 0\n");

    let fake_real = root.join("agent-bridge.real");
    write_executable(
        &fake_real,
        r#"#!/usr/bin/env bash
printf 'PATH=%s\n' "$PATH"
printf 'AGENT_BRIDGE_CLAUDE_BIN=%s\n' "${AGENT_BRIDGE_CLAUDE_BIN:-}"
"#,
    );

    let wrapper =
        Path::new(env!("CARGO_MANIFEST_DIR")).join("../../scripts/wrapper/agent-bridge-wrapper.sh");
    let output = Command::new("bash")
        .arg(wrapper)
        .arg("mcp")
        .env_clear()
        .env("HOME", &home)
        .env("PATH", "/usr/bin:/bin")
        .env("AGENT_BRIDGE_REAL_BIN", &fake_real)
        .output()
        .expect("run wrapper");

    let stdout = String::from_utf8(output.stdout).expect("stdout utf8");
    let stderr = String::from_utf8(output.stderr).expect("stderr utf8");
    assert!(
        output.status.success(),
        "wrapper failed: status={:?}\nstdout={stdout}\nstderr={stderr}",
        output.status
    );

    let expected_path = format!(
        "PATH={}:{}:{}:/usr/bin:/bin",
        local_bin.display(),
        npm_bin.display(),
        cargo_bin.display()
    );
    assert!(
        stdout.lines().any(|line| line == expected_path),
        "expected user CLI dirs at front of PATH, got:\n{stdout}"
    );
    let expected_claude = format!("AGENT_BRIDGE_CLAUDE_BIN={}", claude.display());
    assert!(
        stdout.lines().any(|line| line == expected_claude),
        "expected default Claude binary, got:\n{stdout}"
    );

    let _ = fs::remove_dir_all(root);
}
