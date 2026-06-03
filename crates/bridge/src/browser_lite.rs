//! Read-only probes for optional browser-lite backends.
//!
//! These probes deliberately do not implement routing and do not start a
//! persistent service. Their job is to capture binary/tool-surface evidence
//! before a backend is allowed into Agent-Bridge's browser strategy.

use anyhow::Result;
use serde::Serialize;
use serde_json::Value;
use std::io::Write;
use std::path::{Path, PathBuf};
use std::process::{Command, Stdio};
use std::time::{Duration, SystemTime, UNIX_EPOCH};

const OBSCURA_ENV: &str = "AGENT_BRIDGE_OBSCURA_BIN";

#[derive(Clone, Debug)]
pub struct ObscuraProbeOptions {
    pub bin: Option<PathBuf>,
    pub timeout_ms: u64,
    pub probe_mcp_tools: bool,
    pub json: bool,
}

#[derive(Debug, Serialize)]
pub struct ObscuraProbeReport {
    pub schema_version: u32,
    pub generated_at_unix: i64,
    pub backend: &'static str,
    pub status: String,
    pub recommendation: String,
    pub binary: BinaryProbe,
    pub help: HelpProbe,
    pub mcp: McpProbe,
    pub safety: SafetyProbe,
    pub notes: Vec<String>,
}

#[derive(Debug, Serialize)]
pub struct BinaryProbe {
    pub path: Option<String>,
    pub source: String,
    pub exists: bool,
    pub executable: bool,
    pub env_var: &'static str,
}

#[derive(Debug, Serialize)]
pub struct HelpProbe {
    pub ok: bool,
    pub exit_code: Option<i32>,
    pub timed_out: bool,
    pub contains_fetch: bool,
    pub contains_serve: bool,
    pub contains_mcp: bool,
    pub contains_allow_private_network: bool,
    pub error: Option<String>,
}

#[derive(Debug, Serialize)]
pub struct McpProbe {
    pub requested: bool,
    pub ok: bool,
    pub exit_code: Option<i32>,
    pub timed_out: bool,
    pub tool_count: usize,
    pub tools: Vec<String>,
    pub server_info: Option<Value>,
    pub error: Option<String>,
}

#[derive(Debug, Serialize)]
pub struct SafetyProbe {
    pub persistent_service_started: bool,
    pub mutates_agent_bridge_state: bool,
    pub private_network_default_block_inferred: bool,
    pub file_access_default_off_inferred: bool,
    pub stealth_enabled: bool,
}

#[derive(Debug)]
struct ResolvedBinary {
    path: Option<PathBuf>,
    source: String,
}

#[derive(Debug)]
struct CapturedCommand {
    exit_code: Option<i32>,
    timed_out: bool,
    stdout: String,
    stderr: String,
    error: Option<String>,
}

pub fn run_obscura_probe(options: ObscuraProbeOptions) -> Result<()> {
    let report = probe_obscura(&options);
    if options.json {
        println!("{}", serde_json::to_string_pretty(&report)?);
    } else {
        print_obscura_probe(&report);
    }
    Ok(())
}

pub fn probe_obscura(options: &ObscuraProbeOptions) -> ObscuraProbeReport {
    let timeout = Duration::from_millis(options.timeout_ms.clamp(250, 60_000));
    let resolved = resolve_obscura_binary(options.bin.as_deref());
    let binary = binary_probe(&resolved);

    let help = match resolved.path.as_deref().filter(|_| binary.executable) {
        Some(path) => probe_help(path, timeout),
        None => HelpProbe {
            ok: false,
            exit_code: None,
            timed_out: false,
            contains_fetch: false,
            contains_serve: false,
            contains_mcp: false,
            contains_allow_private_network: false,
            error: Some("obscura binary not found or not executable".to_string()),
        },
    };

    let mcp = if options.probe_mcp_tools {
        match resolved.path.as_deref().filter(|_| binary.executable) {
            Some(path) if help.contains_mcp => probe_mcp_tools(path, timeout),
            Some(_) => McpProbe {
                requested: true,
                ok: false,
                exit_code: None,
                timed_out: false,
                tool_count: 0,
                tools: Vec::new(),
                server_info: None,
                error: Some("obscura --help did not advertise the mcp command".to_string()),
            },
            None => McpProbe {
                requested: true,
                ok: false,
                exit_code: None,
                timed_out: false,
                tool_count: 0,
                tools: Vec::new(),
                server_info: None,
                error: Some("obscura binary not found or not executable".to_string()),
            },
        }
    } else {
        McpProbe {
            requested: false,
            ok: false,
            exit_code: None,
            timed_out: false,
            tool_count: 0,
            tools: Vec::new(),
            server_info: None,
            error: None,
        }
    };

    let safety = SafetyProbe {
        persistent_service_started: false,
        mutates_agent_bridge_state: false,
        private_network_default_block_inferred: help.contains_allow_private_network,
        file_access_default_off_inferred: true,
        stealth_enabled: false,
    };

    let mut notes = Vec::new();
    if !binary.executable {
        notes.push(format!(
            "install obscura on PATH, pass --bin, or set {OBSCURA_ENV}"
        ));
    }
    if binary.executable && !mcp.ok && options.probe_mcp_tools {
        notes.push("MCP tools/list did not complete; keep Obscura out of routed use".to_string());
    }
    if mcp.ok && mcp.tool_count <= 12 {
        notes.push(
            "observed a small release-style tool surface; record exact ref before comparing to main"
                .to_string(),
        );
    }
    if mcp.ok && mcp.tool_count > 12 {
        notes.push(
            "observed expanded main-style tool surface; do not assume release parity".to_string(),
        );
    }

    let status = if !binary.executable {
        "missing"
    } else if options.probe_mcp_tools && !mcp.ok {
        "partial"
    } else {
        "available"
    };
    let recommendation = match status {
        "available" => "candidate",
        "partial" => "inspect_before_use",
        _ => "install_or_configure",
    };

    ObscuraProbeReport {
        schema_version: 1,
        generated_at_unix: unix_now(),
        backend: "obscura",
        status: status.to_string(),
        recommendation: recommendation.to_string(),
        binary,
        help,
        mcp,
        safety,
        notes,
    }
}

fn print_obscura_probe(report: &ObscuraProbeReport) {
    println!("agent-bridge browser-lite probe: {}", report.backend);
    println!("status: {}", report.status);
    println!("recommendation: {}", report.recommendation);
    match report.binary.path.as_deref() {
        Some(path) => println!("binary: {path} ({})", report.binary.source),
        None => println!("binary: not found ({})", report.binary.source),
    }
    println!(
        "help: ok={} fetch={} serve={} mcp={} allow_private_network_flag={}",
        report.help.ok,
        report.help.contains_fetch,
        report.help.contains_serve,
        report.help.contains_mcp,
        report.help.contains_allow_private_network
    );
    if let Some(err) = report.help.error.as_deref() {
        println!("help_error: {err}");
    }
    if report.mcp.requested {
        println!(
            "mcp: ok={} tools={} timed_out={}",
            report.mcp.ok, report.mcp.tool_count, report.mcp.timed_out
        );
        if !report.mcp.tools.is_empty() {
            println!("mcp_tools: {}", report.mcp.tools.join(", "));
        }
        if let Some(err) = report.mcp.error.as_deref() {
            println!("mcp_error: {err}");
        }
    } else {
        println!("mcp: skipped");
    }
    println!(
        "safety: persistent_service_started={} mutates_agent_bridge_state={} private_network_default_block_inferred={} stealth_enabled={}",
        report.safety.persistent_service_started,
        report.safety.mutates_agent_bridge_state,
        report.safety.private_network_default_block_inferred,
        report.safety.stealth_enabled
    );
    for note in &report.notes {
        println!("note: {note}");
    }
}

fn resolve_obscura_binary(arg: Option<&Path>) -> ResolvedBinary {
    if let Some(path) = arg {
        return ResolvedBinary {
            path: Some(path.to_path_buf()),
            source: "arg".to_string(),
        };
    }
    if let Some(path) = std::env::var_os(OBSCURA_ENV) {
        let path = PathBuf::from(path);
        return ResolvedBinary {
            path: Some(path),
            source: format!("env:{OBSCURA_ENV}"),
        };
    }
    match which("obscura") {
        Some(path) => ResolvedBinary {
            path: Some(path),
            source: "path".to_string(),
        },
        None => ResolvedBinary {
            path: None,
            source: "not_found".to_string(),
        },
    }
}

fn binary_probe(resolved: &ResolvedBinary) -> BinaryProbe {
    let exists = resolved.path.as_ref().is_some_and(|p| p.exists());
    let executable = resolved.path.as_ref().is_some_and(|p| is_executable(p));
    BinaryProbe {
        path: resolved.path.as_ref().map(|p| p.display().to_string()),
        source: resolved.source.clone(),
        exists,
        executable,
        env_var: OBSCURA_ENV,
    }
}

fn probe_help(path: &Path, timeout: Duration) -> HelpProbe {
    let captured = run_command(path, &["--help"], None, timeout);
    let text = format!("{}\n{}", captured.stdout, captured.stderr);
    let ok = captured.exit_code == Some(0) && captured.error.is_none() && !captured.timed_out;
    HelpProbe {
        ok,
        exit_code: captured.exit_code,
        timed_out: captured.timed_out,
        contains_fetch: text.contains("fetch"),
        contains_serve: text.contains("serve"),
        contains_mcp: text.contains("mcp"),
        contains_allow_private_network: text.contains("--allow-private-network")
            || text.contains("allow-private-network"),
        error: captured.error,
    }
}

fn probe_mcp_tools(path: &Path, timeout: Duration) -> McpProbe {
    let input = concat!(
        "{\"jsonrpc\":\"2.0\",\"id\":1,\"method\":\"initialize\",\"params\":{\"protocolVersion\":\"2024-11-05\",\"capabilities\":{},\"clientInfo\":{\"name\":\"agent-bridge-browser-lite-probe\",\"version\":\"0\"}}}\n",
        "{\"jsonrpc\":\"2.0\",\"id\":2,\"method\":\"tools/list\",\"params\":{}}\n"
    );
    let captured = run_command(path, &["mcp"], Some(input), timeout);
    let mut parse_error = captured.error.clone();
    let (tools, server_info, parsed_error) = parse_mcp_tools_list(&captured.stdout);
    if parse_error.is_none() {
        parse_error = parsed_error;
    }
    let ok = captured.exit_code == Some(0)
        && !captured.timed_out
        && parse_error.is_none()
        && !tools.is_empty();
    McpProbe {
        requested: true,
        ok,
        exit_code: captured.exit_code,
        timed_out: captured.timed_out,
        tool_count: tools.len(),
        tools,
        server_info,
        error: parse_error,
    }
}

fn parse_mcp_tools_list(stdout: &str) -> (Vec<String>, Option<Value>, Option<String>) {
    let mut tools = Vec::new();
    let mut server_info = None;
    let mut parse_errors = Vec::new();
    for line in stdout
        .lines()
        .map(str::trim)
        .filter(|line| !line.is_empty())
    {
        let value: Value = match serde_json::from_str(line) {
            Ok(value) => value,
            Err(err) => {
                parse_errors.push(format!("parse MCP line: {err}"));
                continue;
            }
        };
        if value.get("id").and_then(Value::as_i64) == Some(1) {
            server_info = value
                .get("result")
                .and_then(|result| result.get("serverInfo"))
                .cloned();
        }
        if value.get("id").and_then(Value::as_i64) == Some(2) {
            if let Some(arr) = value
                .get("result")
                .and_then(|result| result.get("tools"))
                .and_then(Value::as_array)
            {
                tools = arr
                    .iter()
                    .filter_map(|tool| tool.get("name").and_then(Value::as_str))
                    .map(str::to_string)
                    .collect();
            } else if let Some(error) = value.get("error") {
                parse_errors.push(format!("tools/list error: {error}"));
            }
        }
    }
    let error = if tools.is_empty() {
        Some(if parse_errors.is_empty() {
            "tools/list response missing tool names".to_string()
        } else {
            parse_errors.join("; ")
        })
    } else if parse_errors.is_empty() {
        None
    } else {
        Some(parse_errors.join("; "))
    };
    (tools, server_info, error)
}

fn run_command(
    path: &Path,
    args: &[&str],
    stdin: Option<&str>,
    timeout: Duration,
) -> CapturedCommand {
    let mut command = Command::new(path);
    command.args(args);
    if stdin.is_some() {
        command.stdin(Stdio::piped());
    } else {
        command.stdin(Stdio::null());
    }
    command.stdout(Stdio::piped()).stderr(Stdio::piped());

    let mut child = match command.spawn() {
        Ok(child) => child,
        Err(err) => {
            return CapturedCommand {
                exit_code: None,
                timed_out: false,
                stdout: String::new(),
                stderr: String::new(),
                error: Some(format!("spawn failed: {err}")),
            };
        }
    };

    if let Some(input) = stdin {
        if let Some(mut child_stdin) = child.stdin.take() {
            if let Err(err) = child_stdin.write_all(input.as_bytes()) {
                let _ = child.kill();
                return CapturedCommand {
                    exit_code: None,
                    timed_out: false,
                    stdout: String::new(),
                    stderr: String::new(),
                    error: Some(format!("stdin write failed: {err}")),
                };
            }
        }
    }

    let start = std::time::Instant::now();
    let mut timed_out = false;
    loop {
        match child.try_wait() {
            Ok(Some(_)) => break,
            Ok(None) if start.elapsed() < timeout => {
                std::thread::sleep(Duration::from_millis(20));
            }
            Ok(None) => {
                timed_out = true;
                let _ = child.kill();
                break;
            }
            Err(err) => {
                let _ = child.kill();
                return CapturedCommand {
                    exit_code: None,
                    timed_out: false,
                    stdout: String::new(),
                    stderr: String::new(),
                    error: Some(format!("wait failed: {err}")),
                };
            }
        }
    }

    match child.wait_with_output() {
        Ok(output) => CapturedCommand {
            exit_code: output.status.code(),
            timed_out,
            stdout: String::from_utf8_lossy(&output.stdout).to_string(),
            stderr: String::from_utf8_lossy(&output.stderr).to_string(),
            error: None,
        },
        Err(err) => CapturedCommand {
            exit_code: None,
            timed_out,
            stdout: String::new(),
            stderr: String::new(),
            error: Some(format!("capture output failed: {err}")),
        },
    }
}

fn which(bin: &str) -> Option<PathBuf> {
    let path = std::env::var_os("PATH")?;
    std::env::split_paths(&path)
        .map(|dir| dir.join(bin))
        .find(|path| is_executable(path))
}

#[cfg(unix)]
fn is_executable(path: &Path) -> bool {
    use std::os::unix::fs::PermissionsExt;
    let Ok(meta) = path.metadata() else {
        return false;
    };
    meta.is_file() && meta.permissions().mode() & 0o111 != 0
}

#[cfg(not(unix))]
fn is_executable(path: &Path) -> bool {
    path.is_file()
}

fn unix_now() -> i64 {
    SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map(|d| d.as_secs() as i64)
        .unwrap_or(0)
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::json;

    #[test]
    fn parse_mcp_tools_list_extracts_tool_names_and_server_info() {
        let stdout = r#"{"jsonrpc":"2.0","id":1,"result":{"serverInfo":{"name":"obscura-mcp","version":"0.1.0"}}}
{"jsonrpc":"2.0","id":2,"result":{"tools":[{"name":"browser_navigate"},{"name":"browser_snapshot"}]}}"#;
        let (tools, server_info, error) = parse_mcp_tools_list(stdout);
        assert_eq!(tools, vec!["browser_navigate", "browser_snapshot"]);
        assert_eq!(
            server_info,
            Some(json!({"name":"obscura-mcp","version":"0.1.0"}))
        );
        assert!(error.is_none());
    }

    #[test]
    fn parse_mcp_tools_list_reports_missing_tools() {
        let (tools, server_info, error) =
            parse_mcp_tools_list(r#"{"jsonrpc":"2.0","id":2,"result":{"tools":[]}}"#);
        assert!(tools.is_empty());
        assert!(server_info.is_none());
        assert_eq!(
            error.as_deref(),
            Some("tools/list response missing tool names")
        );
    }

    #[test]
    fn missing_binary_probe_is_non_mutating_report() {
        let report = probe_obscura(&ObscuraProbeOptions {
            bin: Some(PathBuf::from("/definitely/missing/obscura")),
            timeout_ms: 250,
            probe_mcp_tools: true,
            json: true,
        });
        assert_eq!(report.status, "missing");
        assert!(!report.binary.exists);
        assert!(!report.safety.persistent_service_started);
        assert!(!report.safety.mutates_agent_bridge_state);
    }
}
