use std::io::{Read, Write};
use std::process::{Command, Stdio};
use std::thread;
use std::time::{Duration, Instant};

use serde_json::{json, Value};

fn wait_with_timeout(
    child: &mut std::process::Child,
    timeout: Duration,
) -> std::process::ExitStatus {
    let deadline = Instant::now() + timeout;
    loop {
        match child.try_wait() {
            Ok(Some(status)) => return status,
            Ok(None) if Instant::now() < deadline => thread::sleep(Duration::from_millis(50)),
            Ok(None) => {
                let _ = child.kill();
                let _ = child.wait();
                panic!("agent-bridge MCP did not exit within {timeout:?}");
            }
            Err(error) => panic!("wait for agent-bridge MCP: {error}"),
        }
    }
}

#[test]
fn production_enforce_hold_reports_invalid_and_denies_shell_before_effect() {
    let directory = tempfile::tempdir().expect("test directory");
    let state_db = directory.path().join("state.sqlite3");
    let sentinel = directory.path().join("must-not-exist");
    let binary = env!("CARGO_BIN_EXE_agent-bridge");

    let mut child = Command::new(binary)
        .arg("mcp")
        .env("AGENT_BRIDGE_DB", &state_db)
        .env("AGENT_BRIDGE_EMBED_BACKEND", "hash")
        .env("AGENT_BRIDGE_TOOLSET", "all-dev")
        .env("AGENT_BRIDGE_MAX_BLOCKING_THREADS", "32")
        .env("AGENT_BRIDGE_HEADLESS", "1")
        // Fix the static ceiling open so this test cannot pass by taking the
        // earlier AB_ALLOW_SHELL_EXEC denial branch from the parent environment.
        .env("AB_ALLOW_SHELL_EXEC", "true")
        .env("AB_INVOCATION_LEASE_MODE", "enforce")
        .env_remove("AB_INVOCATION_LEASE_DB")
        .env_remove("AB_INVOCATION_LEASE_DB_GENERATION")
        .env_remove("AB_INVOCATION_LEASE_VERIFY_KEY")
        .stdin(Stdio::piped())
        .stdout(Stdio::piped())
        .stderr(Stdio::piped())
        .spawn()
        .expect("spawn agent-bridge MCP");

    let initialize = json!({
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": { "name": "invocation-lease-hold-test", "version": "0" }
        }
    });
    let initialized = json!({
        "jsonrpc": "2.0",
        "method": "notifications/initialized"
    });
    let capabilities = json!({
        "jsonrpc": "2.0",
        "id": 2,
        "method": "tools/call",
        "params": { "name": "capabilities", "arguments": {} }
    });
    let call = json!({
        "jsonrpc": "2.0",
        "id": 3,
        "method": "tools/call",
        "params": {
            "name": "shell_exec",
            "arguments": {
                "cmd": "printf forbidden > must-not-exist",
                "cwd": directory.path().to_string_lossy()
            }
        }
    });
    let payload = format!("{initialize}\n{initialized}\n{capabilities}\n{call}\n");

    let mut stdout = child.stdout.take().expect("stdout pipe");
    let mut stderr = child.stderr.take().expect("stderr pipe");
    let stdout_reader = thread::spawn(move || {
        let mut bytes = Vec::new();
        stdout.read_to_end(&mut bytes).expect("read stdout");
        bytes
    });
    let stderr_reader = thread::spawn(move || {
        let mut bytes = Vec::new();
        stderr.read_to_end(&mut bytes).expect("read stderr");
        bytes
    });
    child
        .stdin
        .take()
        .expect("stdin pipe")
        .write_all(payload.as_bytes())
        .expect("write MCP payload");

    let status = wait_with_timeout(&mut child, Duration::from_secs(25));
    let stdout = stdout_reader.join().expect("join stdout reader");
    let stderr = stderr_reader.join().expect("join stderr reader");
    assert!(
        status.success(),
        "MCP child failed: status={status:?}; stderr={}",
        String::from_utf8_lossy(&stderr)
    );
    assert!(!sentinel.exists(), "HOLD must deny before shell starts");

    let responses: Vec<Value> = String::from_utf8_lossy(&stdout)
        .lines()
        .filter_map(|line| serde_json::from_str::<Value>(line).ok())
        .collect();
    let capabilities_response = responses
        .iter()
        .find(|value| value.get("id") == Some(&json!(2)))
        .expect("capabilities response");
    assert_eq!(capabilities_response["result"]["isError"], false);
    let capabilities_text = capabilities_response["result"]["content"][0]["text"]
        .as_str()
        .expect("capabilities text");
    let capabilities_payload: Value =
        serde_json::from_str(capabilities_text).expect("capabilities JSON");
    let lease = &capabilities_payload["security"]["invocation_lease"];
    assert_eq!(lease["mode"], "invalid");
    assert_eq!(lease["configuration_valid"], false);
    assert_eq!(lease["fail_closed"], false);
    assert_eq!(lease["invalid_hold_default_deny_at_guarded_ingress"], true);
    assert_eq!(lease["coverage"]["authorizer_gate_requested"], true);
    assert_eq!(lease["coverage"]["current_process_ingress_attested"], false);

    let call_response = responses
        .iter()
        .find(|value| value.get("id") == Some(&json!(3)))
        .expect("tools/call response");
    assert_eq!(call_response["result"]["isError"], true);
    let text = call_response["result"]["content"][0]["text"]
        .as_str()
        .expect("error text");
    assert!(text.contains("authorization denied"), "{text}");
    assert!(text.contains("invalid_configuration"), "{text}");
    assert!(text.contains("HOLD"), "{text}");
}

#[cfg(unix)]
#[test]
fn non_utf8_mode_is_invalid_hold_not_off() {
    use std::ffi::OsString;
    use std::os::unix::ffi::OsStringExt as _;

    let directory = tempfile::tempdir().expect("test directory");
    let state_db = directory.path().join("state.sqlite3");
    let sentinel = directory.path().join("must-not-exist-non-utf8");
    let binary = env!("CARGO_BIN_EXE_agent-bridge");
    let invalid_mode = OsString::from_vec(vec![b'e', b'n', b'f', 0xff]);

    let mut child = Command::new(binary)
        .arg("mcp")
        .env("AGENT_BRIDGE_DB", &state_db)
        .env("AGENT_BRIDGE_EMBED_BACKEND", "hash")
        .env("AGENT_BRIDGE_TOOLSET", "all-dev")
        .env("AGENT_BRIDGE_MAX_BLOCKING_THREADS", "32")
        .env("AGENT_BRIDGE_HEADLESS", "1")
        .env("AB_ALLOW_SHELL_EXEC", "true")
        .env("AB_INVOCATION_LEASE_MODE", invalid_mode)
        .env_remove("AB_INVOCATION_LEASE_DB")
        .env_remove("AB_INVOCATION_LEASE_DB_GENERATION")
        .env_remove("AB_INVOCATION_LEASE_VERIFY_KEY")
        .stdin(Stdio::piped())
        .stdout(Stdio::piped())
        .stderr(Stdio::piped())
        .spawn()
        .expect("spawn agent-bridge MCP");

    let initialize = json!({
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": { "name": "invocation-lease-non-utf8-test", "version": "0" }
        }
    });
    let initialized = json!({
        "jsonrpc": "2.0",
        "method": "notifications/initialized"
    });
    let call = json!({
        "jsonrpc": "2.0",
        "id": 2,
        "method": "tools/call",
        "params": {
            "name": "shell_exec",
            "arguments": {
                "cmd": "printf forbidden > must-not-exist-non-utf8",
                "cwd": directory.path().to_string_lossy()
            }
        }
    });
    let payload = format!("{initialize}\n{initialized}\n{call}\n");

    let mut stdout = child.stdout.take().expect("stdout pipe");
    let mut stderr = child.stderr.take().expect("stderr pipe");
    let stdout_reader = thread::spawn(move || {
        let mut bytes = Vec::new();
        stdout.read_to_end(&mut bytes).expect("read stdout");
        bytes
    });
    let stderr_reader = thread::spawn(move || {
        let mut bytes = Vec::new();
        stderr.read_to_end(&mut bytes).expect("read stderr");
        bytes
    });
    child
        .stdin
        .take()
        .expect("stdin pipe")
        .write_all(payload.as_bytes())
        .expect("write MCP payload");

    let status = wait_with_timeout(&mut child, Duration::from_secs(25));
    let stdout = stdout_reader.join().expect("join stdout reader");
    let stderr = stderr_reader.join().expect("join stderr reader");
    assert!(
        status.success(),
        "MCP child failed: status={status:?}; stderr={}",
        String::from_utf8_lossy(&stderr)
    );
    assert!(
        !sentinel.exists(),
        "non-UTF-8 mode must install Invalid/HOLD rather than disable the guard"
    );

    let responses: Vec<Value> = String::from_utf8_lossy(&stdout)
        .lines()
        .filter_map(|line| serde_json::from_str::<Value>(line).ok())
        .collect();
    let response = responses
        .iter()
        .find(|value| value.get("id") == Some(&json!(2)))
        .expect("tools/call response");
    assert_eq!(response["result"]["isError"], true);
    let text = response["result"]["content"][0]["text"]
        .as_str()
        .expect("error text");
    assert!(text.contains("invalid_configuration"), "{text}");
    assert!(text.contains("must be valid UTF-8"), "{text}");
}
