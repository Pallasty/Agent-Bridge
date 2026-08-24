use std::process::Command;

#[test]
fn focus_observer_help_exposes_bounded_session_without_confirmation_gate() {
    let output = Command::new(env!("CARGO_BIN_EXE_agent-bridge"))
        .args(["avatar", "focus-follow-observe", "--help"])
        .output()
        .expect("run focus-follow-observe help");
    assert!(output.status.success());
    let stdout = String::from_utf8_lossy(&output.stdout);
    for flag in [
        "--duration-ms",
        "--poll-ms",
        "--dwell-ms",
        "--cooldown-secs",
        "--failure-backoff-secs",
        "--min-travel-px",
        "--max-travel-px",
        "--max-attempts",
        "--pause-file",
        "--deny-app-id",
        "--execute",
        "--json",
    ] {
        assert!(stdout.contains(flag), "missing {flag} in help: {stdout}");
    }
    assert!(!stdout.contains("--confirm"));
    assert!(!stdout.contains("--reason"));
}

#[cfg(unix)]
#[test]
fn focus_observer_dry_run_is_privacy_safe_bounded_and_write_free() {
    use std::os::unix::fs::PermissionsExt;

    let root = tempfile::tempdir().expect("focus observer CLI tempdir");
    let runtime = root.path().join("runtime");
    let state = root.path().join("state");
    let bin = root.path().join("bin");
    std::fs::create_dir_all(&runtime).expect("runtime directory");
    std::fs::create_dir_all(&bin).expect("fake bin directory");
    std::fs::set_permissions(&runtime, std::fs::Permissions::from_mode(0o700))
        .expect("private runtime mode");
    let swaymsg = bin.join("swaymsg");
    std::fs::write(
        &swaymsg,
        r#"#!/bin/sh
printf '%s\n' '{"type":"root","nodes":[{"type":"output","rect":{"x":0,"y":0,"width":1920,"height":1080},"nodes":[{"type":"workspace","name":"1","rect":{"x":0,"y":0,"width":1920,"height":1040},"nodes":[{"id":41,"type":"con","app_id":"secret.application.identity","name":"secret window title","focused":true,"rect":{"x":100,"y":80,"width":1200,"height":800}}],"floating_nodes":[{"id":99,"type":"floating_con","app_id":"agent-bridge-avatar","name":"Xiao Shu","focused":false,"rect":{"x":1700,"y":850,"width":90,"height":130}}]}]}]}'
"#,
    )
    .expect("write fake swaymsg");
    std::fs::set_permissions(&swaymsg, std::fs::Permissions::from_mode(0o700))
        .expect("make fake swaymsg executable");
    let path = std::env::var_os("PATH").unwrap_or_default();
    let path = format!("{}:{}", bin.display(), path.to_string_lossy());

    let output = Command::new(env!("CARGO_BIN_EXE_agent-bridge"))
        .args([
            "avatar",
            "focus-follow-observe",
            "--duration-ms",
            "999999999",
            "--max-attempts",
            "99",
            "--deny-app-id",
            "owner.private.extra",
            "--json",
        ])
        .env("PATH", path)
        .env("XDG_RUNTIME_DIR", &runtime)
        .env("AGENT_BRIDGE_STATE_DIR", &state)
        .env("SWAYSOCK", runtime.join("sway-ipc.sock"))
        .env("WAYLAND_DISPLAY", "wayland-test")
        .output()
        .expect("run focus observer dry-run");
    assert!(
        output.status.success(),
        "stderr: {}",
        String::from_utf8_lossy(&output.stderr)
    );
    let payload: serde_json::Value =
        serde_json::from_slice(&output.stdout).expect("privacy-safe preflight JSON");
    assert_eq!(payload["status"], "dry_run");
    assert_eq!(payload["ready"], true);
    assert_eq!(payload["execute_requested"], false);
    assert_eq!(payload["bounds"]["duration_ms"], 1_800_000);
    assert_eq!(payload["bounds"]["max_attempts"], 3);
    assert_eq!(payload["effects"]["moves_pointer"], false);
    assert_eq!(payload["effects"]["changes_focus"], false);
    assert_eq!(payload["effects"]["emits_input"], false);
    let projected = payload.to_string();
    assert!(!projected.contains("secret window title"));
    assert!(!projected.contains("secret.application.identity"));
    assert!(!projected.contains("owner.private.extra"));
    assert!(!runtime
        .join("ab-focus-follow-observer-receipt.json")
        .exists());
    assert!(!state.exists(), "dry-run must not create durable state");
}

#[cfg(unix)]
#[test]
fn focus_observer_execute_is_duration_bounded_and_honors_pause_without_action() {
    use std::os::unix::fs::PermissionsExt;

    let root = tempfile::tempdir().expect("focus observer execute tempdir");
    let runtime = root.path().join("runtime");
    let state = root.path().join("state");
    let bin = root.path().join("bin");
    let pause = runtime.join("observer.pause");
    std::fs::create_dir_all(&runtime).expect("runtime directory");
    std::fs::create_dir_all(&bin).expect("fake bin directory");
    std::fs::set_permissions(&runtime, std::fs::Permissions::from_mode(0o700))
        .expect("private runtime mode");
    std::fs::write(&pause, b"paused\n").expect("pause marker");
    let swaymsg = bin.join("swaymsg");
    std::fs::write(
        &swaymsg,
        r#"#!/bin/sh
printf '%s\n' '{"type":"root","nodes":[{"type":"output","rect":{"x":0,"y":0,"width":1920,"height":1080},"nodes":[{"type":"workspace","name":"1","rect":{"x":0,"y":0,"width":1920,"height":1040},"nodes":[{"id":41,"type":"con","app_id":"org.example.Editor","name":"private title must not escape","focused":true,"rect":{"x":100,"y":80,"width":1200,"height":800}}],"floating_nodes":[{"id":99,"type":"floating_con","app_id":"agent-bridge-avatar","name":"Xiao Shu","focused":false,"rect":{"x":1700,"y":850,"width":90,"height":130}}]}]}]}'
"#,
    )
    .expect("write fake swaymsg");
    std::fs::set_permissions(&swaymsg, std::fs::Permissions::from_mode(0o700))
        .expect("make fake swaymsg executable");
    let path = std::env::var_os("PATH").unwrap_or_default();
    let path = format!("{}:{}", bin.display(), path.to_string_lossy());

    let started = std::time::Instant::now();
    let output = Command::new(env!("CARGO_BIN_EXE_agent-bridge"))
        .args([
            "avatar",
            "focus-follow-observe",
            "--duration-ms",
            "1000",
            "--poll-ms",
            "250",
            "--pause-file",
            pause.to_str().expect("UTF-8 pause path"),
            "--execute",
            "--json",
        ])
        .env("PATH", path)
        .env("XDG_RUNTIME_DIR", &runtime)
        .env("AGENT_BRIDGE_STATE_DIR", &state)
        .env("SWAYSOCK", runtime.join("sway-ipc.sock"))
        .env("WAYLAND_DISPLAY", "wayland-test")
        .output()
        .expect("run bounded focus observer");
    let elapsed = started.elapsed();
    assert!(
        output.status.success(),
        "stderr: {}",
        String::from_utf8_lossy(&output.stderr)
    );
    assert!(
        elapsed >= std::time::Duration::from_millis(900)
            && elapsed < std::time::Duration::from_secs(5),
        "observer elapsed outside bounded window: {elapsed:?}"
    );
    let payload: serde_json::Value =
        serde_json::from_slice(&output.stdout).expect("terminal observer JSON");
    assert_eq!(payload["status"], "completed");
    assert_eq!(payload["completed"], true);
    assert_eq!(payload["terminal_reason"], "duration_elapsed");
    assert_eq!(payload["attempt_count"], 0);
    assert!(payload["suppressed"]["paused"].as_u64().unwrap_or(0) > 0);
    assert_eq!(payload["effects"]["moves_pointer"], false);
    assert_eq!(payload["effects"]["changes_focus"], false);
    let projected = payload.to_string();
    assert!(!projected.contains("private title must not escape"));
    assert!(!projected.contains("org.example.Editor"));
    assert!(
        !state.exists(),
        "paused observer must not start a durable action"
    );

    let receipt_path = runtime.join("ab-focus-follow-observer-receipt.json");
    let receipt: serde_json::Value = serde_json::from_slice(
        &std::fs::read(&receipt_path).expect("read terminal observer receipt"),
    )
    .expect("parse terminal observer receipt");
    assert_eq!(receipt, payload);
    assert_eq!(
        std::fs::metadata(receipt_path)
            .expect("observer receipt metadata")
            .permissions()
            .mode()
            & 0o777,
        0o600
    );
}
