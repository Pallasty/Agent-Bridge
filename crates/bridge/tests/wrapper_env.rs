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

#[test]
fn wrapper_derives_common_state_root_from_canonical_app_control_journal() {
    let root = test_root("wrapper-state-root");
    let home = root.join("home");
    fs::create_dir_all(&home).expect("home");
    let secure_state = root.join("private-state");
    let machine_env = root.join("machine.env");
    fs::write(
        &machine_env,
        format!(
            "export AB_APP_CONTROL_OPERATION_DIR='{}/app_control_operations'\n",
            secure_state.display()
        ),
    )
    .expect("write machine env");

    let fake_real = root.join("agent-bridge.real");
    write_executable(
        &fake_real,
        r#"#!/usr/bin/env bash
printf 'AGENT_BRIDGE_STATE_DIR=%s\n' "${AGENT_BRIDGE_STATE_DIR:-}"
"#,
    );
    let wrapper =
        Path::new(env!("CARGO_MANIFEST_DIR")).join("../../scripts/wrapper/agent-bridge-wrapper.sh");
    let output = Command::new("bash")
        .arg(wrapper)
        .env_clear()
        .env("HOME", &home)
        .env("PATH", "/usr/bin:/bin")
        .env("AGENT_BRIDGE_REAL_BIN", &fake_real)
        .env("AGENT_BRIDGE_MACHINE_ENV", &machine_env)
        .output()
        .expect("run wrapper");

    let stdout = String::from_utf8(output.stdout).expect("stdout utf8");
    let stderr = String::from_utf8(output.stderr).expect("stderr utf8");
    assert!(
        output.status.success(),
        "wrapper failed: status={:?}\nstdout={stdout}\nstderr={stderr}",
        output.status
    );
    assert_eq!(
        stdout.trim(),
        format!("AGENT_BRIDGE_STATE_DIR={}", secure_state.display())
    );

    let explicit_state = root.join("explicit-state");
    let explicit = Command::new("bash")
        .arg(
            Path::new(env!("CARGO_MANIFEST_DIR"))
                .join("../../scripts/wrapper/agent-bridge-wrapper.sh"),
        )
        .env_clear()
        .env("HOME", &home)
        .env("PATH", "/usr/bin:/bin")
        .env("AGENT_BRIDGE_REAL_BIN", &fake_real)
        .env("AGENT_BRIDGE_MACHINE_ENV", &machine_env)
        .env("AGENT_BRIDGE_STATE_DIR", &explicit_state)
        .output()
        .expect("run wrapper with explicit state root");
    assert!(explicit.status.success());
    assert_eq!(
        String::from_utf8(explicit.stdout)
            .expect("explicit stdout utf8")
            .trim(),
        format!("AGENT_BRIDGE_STATE_DIR={}", explicit_state.display())
    );

    let _ = fs::remove_dir_all(root);
}

#[test]
fn wrapper_routes_resident_before_shared_credentials_and_parses_only_safe_paths() {
    let root = test_root("wrapper-resident-isolation");
    let home = root.join("home");
    let local_bin = home.join(".local/bin");
    fs::create_dir_all(&local_bin).expect("local bin");

    let awk_marker = root.join("awk-was-called");
    write_executable(
        &local_bin.join("awk"),
        &format!(
            "#!/usr/bin/env bash\ntouch '{}'\nexec /usr/bin/awk \"$@\"\n",
            awk_marker.display()
        ),
    );

    let secure_state = root.join("private-state");
    let native_codex = root.join("pinned-codex");
    write_executable(&native_codex, "#!/usr/bin/env bash\nexit 0\n");
    let machine_env = root.join("machine.env");
    fs::write(
        &machine_env,
        format!(
            concat!(
                "export AB_APP_CONTROL_OPERATION_DIR=\"${{AB_APP_CONTROL_OPERATION_DIR:-{}/app_control_operations}}\"\n",
                "export AB_RESIDENT_CODEX_BIN='${{AB_RESIDENT_CODEX_BIN:-{}}}'\n",
                "export GITHUB_TOKEN='must-not-enter-resident'\n"
            ),
            secure_state.display(),
            native_codex.display()
        ),
    )
    .expect("write machine env");
    let creds = root.join("credentials.txt");
    fs::write(&creds, "# Github PAT Token\nghp_must_not_enter_resident\n")
        .expect("write credentials");

    let fake_real = root.join("agent-bridge.real");
    write_executable(
        &fake_real,
        r#"#!/usr/bin/env bash
printf 'ARGS=%s\n' "$*"
printf 'AGENT_BRIDGE_STATE_DIR=%s\n' "${AGENT_BRIDGE_STATE_DIR:-}"
printf 'AB_RESIDENT_CODEX_BIN=%s\n' "${AB_RESIDENT_CODEX_BIN:-}"
printf 'GITHUB_TOKEN=%s\n' "${GITHUB_TOKEN:-}"
"#,
    );

    let wrapper =
        Path::new(env!("CARGO_MANIFEST_DIR")).join("../../scripts/wrapper/agent-bridge-wrapper.sh");
    let output = Command::new("bash")
        .arg(wrapper)
        .args(["resident", "risk-preflight", "--json"])
        .env_clear()
        .env("HOME", &home)
        .env("PATH", "/usr/bin:/bin")
        .env("AGENT_BRIDGE_REAL_BIN", &fake_real)
        .env("AGENT_BRIDGE_MACHINE_ENV", &machine_env)
        .env("AGENT_BRIDGE_CREDS_FILE", &creds)
        .output()
        .expect("run resident wrapper");

    let stdout = String::from_utf8(output.stdout).expect("stdout utf8");
    let stderr = String::from_utf8(output.stderr).expect("stderr utf8");
    assert!(
        output.status.success(),
        "wrapper failed: status={:?}\nstdout={stdout}\nstderr={stderr}",
        output.status
    );
    assert_eq!(
        stdout,
        format!(
            concat!(
                "ARGS=resident risk-preflight --json\n",
                "AGENT_BRIDGE_STATE_DIR={}\n",
                "AB_RESIDENT_CODEX_BIN={}\n",
                "GITHUB_TOKEN=\n"
            ),
            secure_state.display(),
            native_codex.display()
        )
    );
    assert!(
        !awk_marker.exists(),
        "Resident path must not parse the shared credentials notebook"
    );

    let _ = fs::remove_dir_all(root);
}
