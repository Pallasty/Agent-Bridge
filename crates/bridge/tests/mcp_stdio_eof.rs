use std::io::{Read, Write};
use std::process::{Command, Stdio};
use std::thread;
use std::time::{Duration, Instant};

use serde_json::Value;

// Do not pin the hash backend here: that hides the native initialization vs
// process-teardown race. Match the publisher's empty HOME and immediate EOF.
#[cfg(feature = "onnx-embed")]
#[test]
fn mcp_native_initialization_drains_after_immediate_eof() {
    for _ in 0..3 {
        let home = tempfile::tempdir().expect("isolated home");
        let home_path = home.path().canonicalize().expect("canonical isolated home");
        for dir in ["tmp", "xdg/data", "xdg/config", "xdg/cache", "xdg/state"] {
            std::fs::create_dir_all(home_path.join(dir)).unwrap();
        }
        let mut child = Command::new(env!("CARGO_BIN_EXE_agent-bridge"))
            .arg("mcp")
            .env_clear()
            .env("HOME", &home_path)
            .env("PATH", "/usr/bin:/bin:/usr/sbin:/sbin")
            .env("TMPDIR", home_path.join("tmp"))
            .env("XDG_DATA_HOME", home_path.join("xdg/data"))
            .env("XDG_CONFIG_HOME", home_path.join("xdg/config"))
            .env("XDG_CACHE_HOME", home_path.join("xdg/cache"))
            .env("XDG_STATE_HOME", home_path.join("xdg/state"))
            .env("AGENT_BRIDGE_DB", home_path.join("state.db"))
            .env("AGENT_BRIDGE_STATE_DIR", home_path.join("state"))
            .env("AGENT_BRIDGE_TOOLSET", "codex-essential")
            .env("AGENT_BRIDGE_TERMINAL", "pty")
            .stdin(Stdio::piped())
            .stdout(Stdio::piped())
            .stderr(Stdio::piped())
            .spawn()
            .expect("spawn native MCP");
        let mut stdout = child.stdout.take().unwrap();
        let mut stderr = child.stderr.take().unwrap();
        let output = thread::spawn(move || {
            let mut b = Vec::new();
            stdout.read_to_end(&mut b).unwrap();
            b
        });
        let errors = thread::spawn(move || {
            let mut b = Vec::new();
            stderr.read_to_end(&mut b).unwrap();
            b
        });
        child.stdin.take().unwrap().write_all(concat!(
            "{\"jsonrpc\":\"2.0\",\"id\":1,\"method\":\"initialize\",\"params\":{\"protocolVersion\":\"2024-11-05\",\"capabilities\":{},\"clientInfo\":{\"name\":\"shutdown-regression\",\"version\":\"1\"}}}\n",
            "{\"jsonrpc\":\"2.0\",\"method\":\"notifications/initialized\",\"params\":{}}\n",
            "{\"jsonrpc\":\"2.0\",\"id\":2,\"method\":\"tools/list\",\"params\":{}}\n",
            "{\"jsonrpc\":\"2.0\",\"id\":3,\"method\":\"tools/call\",\"params\":{\"name\":\"capabilities\",\"arguments\":{\"compact\":true}}}\n"
        ).as_bytes()).unwrap();
        let status = wait_with_timeout(&mut child, Duration::from_secs(45));
        let stdout = output.join().unwrap();
        let stderr = errors.join().unwrap();
        assert!(
            status.success(),
            "native MCP failed: {status:?}: {}",
            String::from_utf8_lossy(&stderr)
        );
        let rows: Vec<Value> = String::from_utf8(stdout)
            .unwrap()
            .lines()
            .map(|s| serde_json::from_str(s).unwrap())
            .collect();
        for id in [1, 2, 3] {
            let row = rows
                .iter()
                .find(|r| r["id"] == id)
                .expect("complete response set");
            assert!(row.get("error").is_none(), "protocol error: {row}");
        }
    }
}

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
                panic!("agent-bridge mcp did not exit after stdin EOF within {timeout:?}");
            }
            Err(e) => panic!("wait agent-bridge mcp: {e}"),
        }
    }
}

#[test]
fn mcp_stdio_tools_list_exits_cleanly_after_eof() {
    let temp_dir = tempfile::tempdir().expect("tempdir");
    let db_path = temp_dir.path().join("state.db");
    let bin = env!("CARGO_BIN_EXE_agent-bridge");

    let mut child = Command::new(bin)
        .arg("mcp")
        .env("AGENT_BRIDGE_DB", &db_path)
        .env("AGENT_BRIDGE_EMBED_BACKEND", "hash")
        .env("AGENT_BRIDGE_TOOLSET", "profile")
        .env("AGENT_BRIDGE_TOOL_PROFILE", "all")
        .env("AGENT_BRIDGE_MAX_BLOCKING_THREADS", "32")
        .env("AGENT_BRIDGE_HEADLESS", "1")
        .stdin(Stdio::piped())
        .stdout(Stdio::piped())
        .stderr(Stdio::piped())
        .spawn()
        .expect("spawn agent-bridge mcp");

    let mut stdout = child.stdout.take().expect("stdout pipe");
    let mut stderr = child.stderr.take().expect("stderr pipe");
    let stdout_reader = thread::spawn(move || {
        let mut buf = Vec::new();
        stdout.read_to_end(&mut buf).expect("read stdout");
        buf
    });
    let stderr_reader = thread::spawn(move || {
        let mut buf = Vec::new();
        stderr.read_to_end(&mut buf).expect("read stderr");
        buf
    });

    let payload = [
        r#"{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"mcp-stdio-eof-test","version":"0"}}}"#,
        r#"{"jsonrpc":"2.0","method":"notifications/initialized"}"#,
        r#"{"jsonrpc":"2.0","id":2,"method":"tools/list","params":{}}"#,
    ]
    .join("\n")
        + "\n";

    {
        let mut stdin = child.stdin.take().expect("stdin pipe");
        stdin
            .write_all(payload.as_bytes())
            .expect("write json-rpc payload");
    }

    let status = wait_with_timeout(&mut child, Duration::from_secs(20));
    let stdout = stdout_reader.join().expect("join stdout reader");
    let stderr = stderr_reader.join().expect("join stderr reader");

    assert!(
        status.success(),
        "agent-bridge mcp should exit successfully after stdin EOF; status={status:?}; stderr={}",
        String::from_utf8_lossy(&stderr)
    );

    let mut saw_initialize = false;
    let mut saw_tools_list = false;
    for line in String::from_utf8_lossy(&stdout).lines() {
        let value: Value = serde_json::from_str(line).expect("json-rpc response line");
        match value.get("id").and_then(Value::as_i64) {
            Some(1) => {
                assert_eq!(value["result"]["serverInfo"]["name"], "agent-bridge");
                saw_initialize = true;
            }
            Some(2) => {
                let tools = value["result"]["tools"]
                    .as_array()
                    .expect("tools/list array");
                assert!(
                    tools.iter().any(|tool| tool["name"] == "capabilities"),
                    "tools/list should include capabilities"
                );
                saw_tools_list = true;
            }
            _ => {}
        }
    }

    assert!(saw_initialize, "initialize response missing");
    assert!(saw_tools_list, "tools/list response missing");
}
