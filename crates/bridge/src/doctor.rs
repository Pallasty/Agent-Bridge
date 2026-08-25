//! `agent-bridge doctor` — deployment self-check.
//!
//! Born from the 2026-05-23 wrapper-clobber incident: `~/.local/bin/agent-bridge`
//! was silently replaced by a direct stale binary (the wrapper that injects
//! `AB_SUBSTRATE_PROJECTION=svd` + execs `agent-bridge.real`), which made every
//! `cp ... agent-bridge.real` deploy an orphan (MCP + daemon kept running the
//! stale binary) AND silently dropped the SVD projection env for days. The
//! failure was invisible — `cp` succeeded, the daemon ran, nothing errored.
//!
//! `doctor` turns that class of silent "I deployed but it didn't take effect"
//! failure into an explicit report. Read-only file/process/local-HTTP
//! inspection; no mutation.
//! See `lesson_wrapper_clobbered_orphans_real_deploys_2026_05_23`.

use std::path::{Path, PathBuf};
use std::time::Duration;

#[cfg(unix)]
use std::os::unix::fs::MetadataExt;

use anyhow::Result;
use serde_json::{json, Value};

use ab_bridge::instinct;
use ab_bridge::mcp_tools::exposed_tool_count_current;

const DOCTOR_DAEMON_HTTP_BASE: &str = "http://127.0.0.1:7878";
const DOCTOR_EMBED_PROBE_TEXT: &str = "agent-bridge doctor fixed embedding readiness probe";

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Status {
    Ok,
    Warn,
    Fail,
}

impl Status {
    fn label(self) -> &'static str {
        match self {
            Status::Ok => "ok",
            Status::Warn => "warn",
            Status::Fail => "fail",
        }
    }
    fn glyph(self) -> &'static str {
        match self {
            Status::Ok => "✓",
            Status::Warn => "⚠",
            Status::Fail => "✗",
        }
    }
    /// Emoji glyph for Markdown rendering (table-friendly).
    fn md_glyph(self) -> &'static str {
        match self {
            Status::Ok => "✅",
            Status::Warn => "⚠️",
            Status::Fail => "❌",
        }
    }
}

#[derive(Debug, Clone)]
pub struct Check {
    pub name: &'static str,
    pub status: Status,
    pub detail: String,
    /// Optional remediation hint shown for warn/fail.
    pub fix: Option<String>,
}

impl Check {
    fn ok(name: &'static str, detail: impl Into<String>) -> Self {
        Self {
            name,
            status: Status::Ok,
            detail: detail.into(),
            fix: None,
        }
    }
    fn warn(name: &'static str, detail: impl Into<String>, fix: impl Into<String>) -> Self {
        Self {
            name,
            status: Status::Warn,
            detail: detail.into(),
            fix: Some(fix.into()),
        }
    }
    fn fail(name: &'static str, detail: impl Into<String>, fix: impl Into<String>) -> Self {
        Self {
            name,
            status: Status::Fail,
            detail: detail.into(),
            fix: Some(fix.into()),
        }
    }
}

/// Sanitize a string for a Markdown table cell: escape pipes, collapse whitespace.
fn md_cell(s: &str) -> String {
    s.replace('|', "\\|")
        .split_whitespace()
        .collect::<Vec<_>>()
        .join(" ")
}

fn truthy_env(key: &str) -> bool {
    std::env::var(key).is_ok_and(|v| {
        matches!(
            v.as_str(),
            "1" | "true" | "TRUE" | "yes" | "YES" | "on" | "ON"
        )
    })
}

// ── pure classification helpers (unit-tested) ──────────────────────────────

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum FileKind {
    Elf,
    MachO,
    Script,
    Other,
}

/// Classify a file from its leading bytes. ELF/Mach-O magic → a direct binary;
/// `#!` → a script. Pure.
pub fn classify_file_head(head: &[u8]) -> FileKind {
    if head.is_empty() {
        return FileKind::Other;
    }
    if head.starts_with(b"\x7fELF") {
        return FileKind::Elf;
    }
    // Mach-O (fat + thin, both endians).
    if head.starts_with(&[0xCF, 0xFA, 0xED, 0xFE])
        || head.starts_with(&[0xCE, 0xFA, 0xED, 0xFE])
        || head.starts_with(&[0xCA, 0xFE, 0xBA, 0xBE])
    {
        return FileKind::MachO;
    }
    if head.starts_with(b"#!") {
        return FileKind::Script;
    }
    FileKind::Other
}

/// Does a wrapper script body inject the SVD projection env + exec the real
/// binary? Pure — caller supplies the file text.
pub fn wrapper_injects_svd(text: &str) -> bool {
    text.contains("AB_SUBSTRATE_PROJECTION")
}
pub fn wrapper_execs_real(text: &str) -> bool {
    text.contains("agent-bridge.real")
}

// ── IO checks ──────────────────────────────────────────────────────────────

fn install_dir() -> PathBuf {
    if let Ok(d) = std::env::var("AGENT_BRIDGE_INSTALL_DIR") {
        return PathBuf::from(d);
    }
    let home = std::env::var("HOME").unwrap_or_else(|_| "/".into());
    PathBuf::from(home).join(".local/bin")
}

fn read_head(path: &Path, n: usize) -> Option<Vec<u8>> {
    use std::io::Read;
    let mut f = std::fs::File::open(path).ok()?;
    let mut buf = vec![0u8; n];
    let read = f.read(&mut buf).ok()?;
    buf.truncate(read);
    Some(buf)
}

/// Check 1+3: wrapper integrity + SVD injection. The headline check — this is
/// the exact failure mode from 2026-05-23.
fn check_wrapper(dir: &Path) -> Check {
    let wrapper = dir.join("agent-bridge");
    let head = match read_head(&wrapper, 256) {
        Some(h) => h,
        None => {
            return Check::warn(
                "wrapper",
                format!("{} not found", wrapper.display()),
                "run scripts/wrapper/install.sh after placing the binary at agent-bridge.real",
            );
        }
    };
    match classify_file_head(&head) {
        FileKind::Elf | FileKind::MachO => Check::fail(
            "wrapper",
            format!(
                "{} is a DIRECT BINARY, not the wrapper script — deploys to \
                 agent-bridge.real are orphaned (MCP + daemon run this stale file) \
                 and the SVD env injection is lost",
                wrapper.display()
            ),
            "mv ~/.local/bin/agent-bridge /tmp/agent-bridge-stale.bak && \
             bash scripts/wrapper/install.sh  (keeps your agent-bridge.real)",
        ),
        FileKind::Script => {
            // Read full text to verify SVD injection + exec .real.
            let text = std::fs::read_to_string(&wrapper).unwrap_or_default();
            let svd = wrapper_injects_svd(&text);
            let execs = wrapper_execs_real(&text);
            if svd && execs {
                Check::ok(
                    "wrapper",
                    "wrapper script intact (injects AB_SUBSTRATE_PROJECTION + execs agent-bridge.real)",
                )
            } else if !execs {
                Check::fail(
                    "wrapper",
                    "wrapper script does not exec agent-bridge.real",
                    "reinstall: bash scripts/wrapper/install.sh",
                )
            } else {
                Check::warn(
                    "wrapper",
                    "wrapper script does not inject AB_SUBSTRATE_PROJECTION — substrate runs default (non-SVD) projection",
                    "reinstall the current wrapper template: bash scripts/wrapper/install.sh",
                )
            }
        }
        _ => Check::warn(
            "wrapper",
            format!(
                "{} is neither a known binary nor a script",
                wrapper.display()
            ),
            "inspect manually",
        ),
    }
}

/// Check 2: the real binary exists.
fn check_real_binary(dir: &Path) -> Check {
    let real = dir.join("agent-bridge.real");
    if real.is_file() {
        Check::ok("real_binary", format!("{} present", real.display()))
    } else {
        Check::fail(
            "real_binary",
            format!("{} missing — wrapper has nothing to exec", real.display()),
            "cp -f target/release/agent-bridge ~/.local/bin/agent-bridge.real",
        )
    }
}

/// Check 4: SVD projection artifact resolvable when the opt-in substrate needs it.
fn check_svd_artifact() -> Check {
    let path = std::env::var("AB_SUBSTRATE_SVD_PATH")
        .unwrap_or_else(|_| "/Data/CascadeProjects/AiOT/build/svd_projection_v1.bin".into());
    let projection = std::env::var("AB_SUBSTRATE_PROJECTION").unwrap_or_default();
    check_svd_artifact_status(
        &path,
        truthy_env("AB_SUBSTRATE"),
        projection.as_str(),
        Path::new(&path).is_file(),
    )
}

fn check_svd_artifact_status(
    path: &str,
    substrate_enabled: bool,
    projection: &str,
    present: bool,
) -> Check {
    let projection = projection.trim();
    if !substrate_enabled {
        return Check::ok(
            "svd_artifact",
            format!(
                "substrate disabled (AB_SUBSTRATE unset/false); SVD artifact not required until opt-in; configured path: {path}"
            ),
        );
    }

    if projection != "svd" {
        let projection = if projection.is_empty() {
            "<unset>"
        } else {
            projection
        };
        return Check::ok(
            "svd_artifact",
            format!("AB_SUBSTRATE enabled with projection={projection}; SVD artifact not required"),
        );
    }

    if present {
        Check::ok("svd_artifact", format!("SVD projection present: {path}"))
    } else {
        Check::warn(
            "svd_artifact",
            format!("SVD projection file absent: {path} — substrate falls back to bucket-pool"),
            "build/distribute svd_projection_v1.bin, or accept bucket-pool fallback",
        )
    }
}

fn parse_env_assignment(text: &str, key: &str) -> Option<String> {
    let prefix = format!("{key}=");
    text.split_whitespace()
        .find_map(|token| token.strip_prefix(&prefix).map(ToOwned::to_owned))
}

/// Read AGENT_BRIDGE / AB_SUBSTRATE env of a pid from /proc (Linux). Best-effort.
#[cfg(not(target_os = "macos"))]
fn proc_env_from_proc(pid: i64, key: &str) -> Option<String> {
    let data = std::fs::read(format!("/proc/{pid}/environ")).ok()?;
    for entry in data.split(|&b| b == 0) {
        if let Ok(s) = std::str::from_utf8(entry) {
            if let Some(v) = s.strip_prefix(&format!("{key}=")) {
                return Some(v.to_string());
            }
        }
    }
    None
}

fn proc_env_from_ps(pid: i64, key: &str) -> Option<String> {
    let out = std::process::Command::new("ps")
        .args(["eww", "-p", &pid.to_string()])
        .output()
        .ok()?;
    if !out.status.success() {
        return None;
    }
    parse_env_assignment(&String::from_utf8_lossy(&out.stdout), key)
}

#[cfg(target_os = "macos")]
fn proc_env(pid: i64, key: &str) -> Option<String> {
    proc_env_from_ps(pid, key)
}

#[cfg(not(target_os = "macos"))]
fn proc_env(pid: i64, key: &str) -> Option<String> {
    proc_env_from_proc(pid, key).or_else(|| proc_env_from_ps(pid, key))
}

fn pgrep(pattern: &str) -> Vec<i64> {
    std::process::Command::new("pgrep")
        .arg("-f")
        .arg(pattern)
        .output()
        .ok()
        .map(|o| {
            String::from_utf8_lossy(&o.stdout)
                .lines()
                .filter_map(|l| l.trim().parse::<i64>().ok())
                .collect()
        })
        .unwrap_or_default()
}

#[cfg(unix)]
fn file_inode(path: &Path) -> Option<u64> {
    std::fs::metadata(path).ok().map(|m| m.ino())
}

#[cfg(not(unix))]
fn file_inode(_path: &Path) -> Option<u64> {
    None
}

#[derive(Debug, Clone, PartialEq, Eq)]
struct ProcessTextFile {
    path: String,
    inode: Option<u64>,
}

fn basename(path: &str) -> &str {
    path.trim_end_matches(" (deleted)")
        .rsplit('/')
        .next()
        .unwrap_or(path)
}

fn process_command(pid: i64) -> Option<String> {
    let out = std::process::Command::new("ps")
        .args(["-p", &pid.to_string(), "-o", "command="])
        .output()
        .ok()?;
    if !out.status.success() {
        return None;
    }
    let s = String::from_utf8_lossy(&out.stdout).trim().to_string();
    (!s.is_empty()).then_some(s)
}

fn process_parent_pid(pid: i64) -> Option<i64> {
    #[cfg(target_os = "linux")]
    {
        let data = std::fs::read_to_string(format!("/proc/{pid}/status")).ok()?;
        for line in data.lines() {
            if let Some(rest) = line.strip_prefix("PPid:") {
                return rest.trim().parse::<i64>().ok();
            }
        }
    }
    let out = std::process::Command::new("ps")
        .args(["-p", &pid.to_string(), "-o", "ppid="])
        .output()
        .ok()?;
    if !out.status.success() {
        return None;
    }
    String::from_utf8_lossy(&out.stdout).trim().parse().ok()
}

fn process_elapsed(pid: i64) -> Option<String> {
    let out = std::process::Command::new("ps")
        .args(["-p", &pid.to_string(), "-o", "etime="])
        .output()
        .ok()?;
    if !out.status.success() {
        return None;
    }
    let s = String::from_utf8_lossy(&out.stdout).trim().to_string();
    (!s.is_empty()).then_some(s)
}

fn process_text_file_from_proc(pid: i64) -> Option<ProcessTextFile> {
    let path = std::fs::read_link(format!("/proc/{pid}/exe")).ok()?;
    let inode = std::fs::metadata(&path)
        .ok()
        .and_then(|m| file_inode_from_metadata(&m));
    Some(ProcessTextFile {
        path: path.to_string_lossy().to_string(),
        inode,
    })
}

#[cfg(unix)]
fn file_inode_from_metadata(meta: &std::fs::Metadata) -> Option<u64> {
    Some(meta.ino())
}

#[cfg(not(unix))]
fn file_inode_from_metadata(_meta: &std::fs::Metadata) -> Option<u64> {
    None
}

fn process_text_file_from_lsof(pid: i64) -> Option<ProcessTextFile> {
    let out = std::process::Command::new("lsof")
        .args(["-p", &pid.to_string()])
        .output()
        .ok()?;
    if !out.status.success() {
        return None;
    }
    for line in String::from_utf8_lossy(&out.stdout).lines().skip(1) {
        let parts: Vec<&str> = line.split_whitespace().collect();
        if parts.len() < 9 || parts.get(3).copied() != Some("txt") {
            continue;
        }
        let path = parts[8..].join(" ");
        let base = basename(&path);
        if base == "agent-bridge" || base == "agent-bridge.real" {
            let inode = parts.get(7).and_then(|s| s.parse::<u64>().ok());
            return Some(ProcessTextFile { path, inode });
        }
    }
    None
}

fn process_text_file(pid: i64) -> Option<ProcessTextFile> {
    // macOS has no /proc; Linux may not have lsof. Try both and prefer lsof
    // because it can report deleted/replaced executable inodes on macOS.
    process_text_file_from_lsof(pid).or_else(|| process_text_file_from_proc(pid))
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
enum McpProcessKind {
    CurrentReal,
    StaleReal,
    DirectBinary,
    Unknown,
}

#[derive(Debug, Clone, PartialEq, Eq)]
struct McpProcessObservation {
    pid: i64,
    kind: McpProcessKind,
    text_file: Option<ProcessTextFile>,
    command: Option<String>,
    ppid: Option<i64>,
    parent_command: Option<String>,
    elapsed: Option<String>,
}

fn classify_mcp_process(
    text_file: Option<&ProcessTextFile>,
    command: Option<&str>,
    current_real_inode: Option<u64>,
) -> McpProcessKind {
    if let Some(text) = text_file {
        match basename(&text.path) {
            "agent-bridge.real" => {
                if let (Some(actual), Some(current)) = (text.inode, current_real_inode) {
                    if actual != current {
                        return McpProcessKind::StaleReal;
                    }
                }
                return McpProcessKind::CurrentReal;
            }
            "agent-bridge" => return McpProcessKind::DirectBinary,
            _ => {}
        }
    }

    let Some(command) = command else {
        return McpProcessKind::Unknown;
    };
    if command.contains("agent-bridge.real mcp") {
        McpProcessKind::CurrentReal
    } else if command.contains("agent-bridge mcp") {
        McpProcessKind::Unknown
    } else {
        McpProcessKind::Unknown
    }
}

fn observe_mcp_process(pid: i64, current_real_inode: Option<u64>) -> McpProcessObservation {
    let text_file = process_text_file(pid);
    let command = process_command(pid);
    let kind = classify_mcp_process(text_file.as_ref(), command.as_deref(), current_real_inode);
    let ppid = process_parent_pid(pid);
    let parent_command = ppid.and_then(process_command);
    McpProcessObservation {
        pid,
        kind,
        text_file,
        command,
        ppid,
        parent_command,
        elapsed: process_elapsed(pid),
    }
}

fn one_line(s: &str) -> String {
    s.split_whitespace().collect::<Vec<_>>().join(" ")
}

fn mcp_process_debug_row(row: &McpProcessObservation) -> String {
    let exe = row
        .text_file
        .as_ref()
        .map(|f| f.path.as_str())
        .unwrap_or("unknown");
    let parent = row.parent_command.as_deref().unwrap_or("unknown");
    let elapsed = row.elapsed.as_deref().unwrap_or("unknown");
    let ppid = row
        .ppid
        .map(|p| p.to_string())
        .unwrap_or_else(|| "unknown".to_string());
    format!(
        "pid={} ppid={} parent={} elapsed={} exe={}",
        row.pid,
        ppid,
        one_line(parent),
        one_line(elapsed),
        one_line(exe)
    )
}

fn mcp_pids_by_kind(rows: &[McpProcessObservation], kind: McpProcessKind) -> Vec<i64> {
    rows.iter()
        .filter(|row| row.kind == kind)
        .map(|row| row.pid)
        .collect()
}

fn mcp_detail_for_kind(
    rows: &[McpProcessObservation],
    kind: McpProcessKind,
    label: &str,
) -> Option<String> {
    let details: Vec<String> = rows
        .iter()
        .filter(|row| row.kind == kind)
        .map(mcp_process_debug_row)
        .collect();
    if details.is_empty() {
        None
    } else {
        Some(format!("{label} detail: {}", details.join("; ")))
    }
}

fn mcp_refresh_parent_summary(rows: &[McpProcessObservation]) -> Option<String> {
    let mut groups: std::collections::BTreeMap<(Option<i64>, String), usize> =
        std::collections::BTreeMap::new();
    for row in rows
        .iter()
        .filter(|row| row.kind != McpProcessKind::CurrentReal)
    {
        let parent = row
            .parent_command
            .as_deref()
            .map(one_line)
            .unwrap_or_else(|| "unknown".to_string());
        *groups.entry((row.ppid, parent)).or_insert(0) += 1;
    }
    if groups.is_empty() {
        return None;
    }

    let parts = groups
        .into_iter()
        .map(|((ppid, parent), count)| {
            let ppid = ppid
                .map(|p| p.to_string())
                .unwrap_or_else(|| "unknown".to_string());
            format!("ppid={ppid} count={count} parent={parent}")
        })
        .collect::<Vec<_>>();
    Some(format!("refresh parent(s): {}", parts.join("; ")))
}

fn format_mcp_process_summary(rows: &[McpProcessObservation]) -> String {
    let current_real = mcp_pids_by_kind(rows, McpProcessKind::CurrentReal);
    let stale_real = mcp_pids_by_kind(rows, McpProcessKind::StaleReal);
    let direct_binary = mcp_pids_by_kind(rows, McpProcessKind::DirectBinary);
    let unknown = mcp_pids_by_kind(rows, McpProcessKind::Unknown);
    let mut summary = format!(
        "{} MCP server(s): {} current .real, {} stale .real, {} direct \
         agent-bridge binary, {} unknown (current {:?}, stale {:?}, direct {:?}, unknown {:?})",
        rows.len(),
        current_real.len(),
        stale_real.len(),
        direct_binary.len(),
        unknown.len(),
        current_real,
        stale_real,
        direct_binary,
        unknown
    );
    if current_real.is_empty() {
        summary.push_str(
            "; no current .real MCP server detected for this install path, so an active client may still be stale",
        );
    } else if !stale_real.is_empty() || !direct_binary.is_empty() || !unknown.is_empty() {
        summary.push_str(
            "; at least one current .real MCP server is active; stale/direct/unknown rows are other clients or old sessions that still need refresh",
        );
    }
    let detail_blocks = [
        mcp_refresh_parent_summary(rows),
        mcp_detail_for_kind(rows, McpProcessKind::StaleReal, "stale"),
        mcp_detail_for_kind(rows, McpProcessKind::DirectBinary, "direct"),
        mcp_detail_for_kind(rows, McpProcessKind::Unknown, "unknown"),
    ]
    .into_iter()
    .flatten()
    .collect::<Vec<_>>();
    if !detail_blocks.is_empty() {
        summary.push_str(" | ");
        summary.push_str(&detail_blocks.join(" | "));
    }
    summary
}

fn mcp_process_reconnect_hint(rows: &[McpProcessObservation]) -> &'static str {
    if mcp_pids_by_kind(rows, McpProcessKind::CurrentReal).is_empty() {
        "restart the MCP client(s) so they respawn from the current wrapper \
         and re-read tools/list; this refreshes newly added tool manifests. \
         If a soft MCP reconnect leaves stale children under the same Codex/Cursor/Claude \
         parent process, reload or restart that host app/server so it respawns stdio MCP"
    } else {
        "current .real MCP server(s) are already active; restart only stale/direct/unknown \
         MCP client(s) that still need refreshed tool manifests. If those rows stay under \
         the same host parent after a soft reconnect, reload or restart that host app/server"
    }
}

/// Check 5: running daemon has the SVD env (catches the silent regression at
/// runtime, not just on disk).
fn check_daemon_runtime() -> Check {
    let pids = pgrep(r"agent-bridge.real daemon$");
    let Some(&pid) = pids.first() else {
        return Check::warn(
            "daemon_runtime",
            "no agent-bridge.real daemon process found",
            "systemctl --user start agent-bridge-daemon.service",
        );
    };
    match proc_env(pid, "AB_SUBSTRATE_PROJECTION").as_deref() {
        Some("svd") => Check::ok(
            "daemon_runtime",
            format!("daemon PID {pid} running with AB_SUBSTRATE_PROJECTION=svd"),
        ),
        Some(other) => Check::warn(
            "daemon_runtime",
            format!("daemon PID {pid} projection={other} (expected svd)"),
            "restart daemon after fixing the wrapper: systemctl --user restart agent-bridge-daemon.service",
        ),
        None => Check::warn(
            "daemon_runtime",
            format!("daemon PID {pid} has no AB_SUBSTRATE_PROJECTION env — wrapper injection lost"),
            "fix wrapper then restart: systemctl --user restart agent-bridge-daemon.service",
        ),
    }
}

fn value_display(value: Option<&Value>) -> String {
    match value {
        Some(Value::String(value)) => value.clone(),
        Some(Value::Bool(value)) => value.to_string(),
        Some(Value::Number(value)) => value.to_string(),
        Some(_) => "invalid_type".to_string(),
        None => "missing".to_string(),
    }
}

/// Classify the two daemon-http embedding observations without retaining or
/// printing the probe vector. `/embed/readiness` describes configured intent;
/// the fixed `/embed` request proves what the live process actually returned.
fn classify_embedding_runtime(readiness: &Value, probe: &Value) -> Check {
    let configured_backend = readiness.get("configured_backend");
    let configured_dim = readiness.get("configured_dim");
    let model_state = readiness.get("model_state");
    let semantic_ready = readiness.get("semantic_ready");
    let actual_backend = probe.get("backend");
    let actual_dim = probe.get("dim");
    let vector_len = probe
        .get("embedding")
        .and_then(Value::as_array)
        .map(|values| values.len() as u64);

    let configured_backend_str = configured_backend.and_then(Value::as_str);
    let configured_dim_u64 = configured_dim.and_then(Value::as_u64);
    let actual_backend_str = actual_backend.and_then(Value::as_str);
    let actual_dim_u64 = actual_dim.and_then(Value::as_u64);
    let ready = semantic_ready.and_then(Value::as_bool) == Some(true)
        && model_state.and_then(Value::as_str) == Some("ready")
        && configured_backend_str.is_some()
        && configured_backend_str == actual_backend_str
        && configured_dim_u64.is_some()
        && configured_dim_u64 == actual_dim_u64
        && configured_dim_u64 == vector_len;

    let detail = format!(
        "readiness backend={} dim={} state={} semantic_ready={}; probe backend={} dim={} vector_len={}",
        value_display(configured_backend),
        value_display(configured_dim),
        value_display(model_state),
        value_display(semantic_ready),
        value_display(actual_backend),
        value_display(actual_dim),
        vector_len
            .map(|value| value.to_string())
            .unwrap_or_else(|| "missing".to_string()),
    );

    if ready {
        Check::ok("embedding_runtime", detail)
    } else {
        Check::warn(
            "embedding_runtime",
            detail,
            "restore the configured ONNX model assets, restart agent-bridge-daemon-http.service, and require /embed backend, dim, and vector length to match /embed/readiness",
        )
    }
}

/// Check the live local encoder rather than treating `/healthz` as semantic
/// readiness. The request contains only a fixed public probe string and the
/// returned vector is reduced to metadata before it reaches doctor output.
async fn check_embedding_runtime() -> Check {
    let readiness_url = format!("{DOCTOR_DAEMON_HTTP_BASE}/embed/readiness");
    let embed_url = format!("{DOCTOR_DAEMON_HTTP_BASE}/embed");
    let client = match reqwest::Client::builder()
        .connect_timeout(Duration::from_secs(2))
        .timeout(Duration::from_secs(15))
        .build()
    {
        Ok(client) => client,
        Err(error) => {
            return Check::warn(
                "embedding_runtime",
                format!("failed to create local HTTP client: {error}"),
                "verify the local TLS/HTTP runtime and retry agent-bridge doctor",
            );
        }
    };

    let readiness = match client.get(&readiness_url).send().await {
        Ok(response) if response.status().is_success() => match response.json::<Value>().await {
            Ok(value) => value,
            Err(error) => {
                return Check::warn(
                    "embedding_runtime",
                    format!("{readiness_url} returned invalid JSON: {error}"),
                    "restart agent-bridge-daemon-http.service and inspect /embed/readiness",
                );
            }
        },
        Ok(response) => {
            return Check::warn(
                "embedding_runtime",
                format!("{readiness_url} returned HTTP {}", response.status()),
                "restart agent-bridge-daemon-http.service and inspect /embed/readiness",
            );
        }
        Err(error) => {
            return Check::warn(
                "embedding_runtime",
                format!("{readiness_url} is unreachable: {error}"),
                "start agent-bridge-daemon-http.service on the standard local 127.0.0.1:7878 listener",
            );
        }
    };

    let probe = match client
        .post(&embed_url)
        .json(&json!({"text": DOCTOR_EMBED_PROBE_TEXT}))
        .send()
        .await
    {
        Ok(response) if response.status().is_success() => match response.json::<Value>().await {
            Ok(value) => value,
            Err(error) => {
                return Check::warn(
                    "embedding_runtime",
                    format!("{embed_url} returned invalid JSON: {error}"),
                    "restart agent-bridge-daemon-http.service and inspect /embed",
                );
            }
        },
        Ok(response) => {
            return Check::warn(
                "embedding_runtime",
                format!("{embed_url} returned HTTP {}", response.status()),
                "restart agent-bridge-daemon-http.service and inspect /embed",
            );
        }
        Err(error) => {
            return Check::warn(
                "embedding_runtime",
                format!("{embed_url} probe failed: {error}"),
                "restart agent-bridge-daemon-http.service and verify the configured model assets",
            );
        }
    };

    classify_embedding_runtime(&readiness, &probe)
}

/// Check 6: running MCP servers should execute the current `agent-bridge.real`.
/// On macOS, old replaced binaries can keep running from orphaned inodes even
/// after the path has been repaired. That serves stale tool manifests until the
/// client reconnects, which is exactly the failure mode this check catches.
fn check_mcp_servers(dir: &Path) -> Check {
    let pids = pgrep(r"agent-bridge(\.real)? mcp");
    if pids.is_empty() {
        return Check::ok("mcp_servers", "no agent-bridge mcp processes running");
    }

    let real_inode = file_inode(&dir.join("agent-bridge.real"));
    let rows: Vec<McpProcessObservation> = pids
        .iter()
        .map(|pid| observe_mcp_process(*pid, real_inode))
        .collect();
    let stale_real = mcp_pids_by_kind(&rows, McpProcessKind::StaleReal);
    let direct_binary = mcp_pids_by_kind(&rows, McpProcessKind::DirectBinary);
    let unknown = mcp_pids_by_kind(&rows, McpProcessKind::Unknown);

    if stale_real.is_empty() && direct_binary.is_empty() && unknown.is_empty() {
        Check::ok(
            "mcp_servers",
            format!(
                "{} MCP server(s) — all executing current agent-bridge.real",
                pids.len()
            ),
        )
    } else {
        // WARN not FAIL: the authoritative integrity gate is the `wrapper`
        // check. These are MCP servers spawned while the wrapper was clobbered
        // or before a redeploy. They can serve stale tool surfaces (e.g. miss
        // forum_digest/mobile_*) until the client reconnects. Lingering old
        // servers from past sessions are expected churn, not a current-deploy
        // integrity failure.
        Check::warn(
            "mcp_servers",
            format_mcp_process_summary(&rows),
            mcp_process_reconnect_hint(&rows),
        )
    }
}

fn check_mcp_tool_surface() -> Check {
    // Reality view (host detection applied): report what servers on THIS
    // host actually expose, not the nominal fully-available surface.
    let cursor_count =
        exposed_tool_count_current(Some("claude-standard"), Some("cursor"), Some("standard"));
    let process_count = exposed_tool_count_current(
        std::env::var("AGENT_BRIDGE_TOOLSET").ok().as_deref(),
        std::env::var("AGENT_BRIDGE_CLIENT").ok().as_deref(),
        std::env::var("AGENT_BRIDGE_TOOL_PROFILE").ok().as_deref(),
    );
    let toolset = std::env::var("AGENT_BRIDGE_TOOLSET").unwrap_or_else(|_| "(unset)".into());
    let client = std::env::var("AGENT_BRIDGE_CLIENT").unwrap_or_else(|_| "(unset)".into());
    Check::ok(
        "mcp_tool_surface",
        format!(
            "claude-standard+cursor={cursor_count} tools; current process ({client}/{toolset})={process_count} tools"
        ),
    )
}

fn system_control_bin_path(dir: &Path) -> PathBuf {
    std::env::var_os("AB_SYSTEM_CONTROL_BIN")
        .map(PathBuf::from)
        .unwrap_or_else(|| dir.join("ab-system-control"))
}

fn system_control_audit_dir() -> PathBuf {
    if let Ok(dir) = std::env::var("AB_SYSTEM_CONTROL_AUDIT_DIR") {
        return PathBuf::from(dir);
    }
    if Path::new("/Data").is_dir() {
        return PathBuf::from("/Data/agent-bridge/system-control");
    }
    let home = PathBuf::from(std::env::var("HOME").unwrap_or_else(|_| "/".into()));
    // Per-OS data dir (mirror of setup::agent_bridge_data_dir): macOS uses
    // ~/Library/Application Support; Linux honours XDG_DATA_HOME then falls
    // back to ~/.local/share.
    #[cfg(target_os = "macos")]
    let dir = home.join("Library/Application Support/agent-bridge/system-control");
    #[cfg(not(target_os = "macos"))]
    let dir = std::env::var("XDG_DATA_HOME")
        .map(|x| PathBuf::from(x).join("agent-bridge/system-control"))
        .unwrap_or_else(|_| home.join(".local/share/agent-bridge/system-control"));
    dir
}

#[cfg(unix)]
fn mode_octal(path: &Path) -> Option<u32> {
    std::fs::metadata(path).ok().map(|m| m.mode() & 0o777)
}

#[cfg(not(unix))]
fn mode_octal(_path: &Path) -> Option<u32> {
    None
}

#[cfg(unix)]
fn is_executable(path: &Path) -> bool {
    std::fs::metadata(path)
        .ok()
        .is_some_and(|m| m.is_file() && (m.mode() & 0o111) != 0)
}

#[cfg(not(unix))]
fn is_executable(path: &Path) -> bool {
    path.is_file()
}

fn system_control_script_has_confirm_gate(text: &str) -> bool {
    text.contains("power off --confirm")
        && text.contains("Refusing poweroff without --confirm")
        && text.contains("agent_bridge.system_control.audit.v0")
}

fn check_system_control_api(dir: &Path) -> Check {
    let bin = system_control_bin_path(dir);
    if !bin.is_file() {
        return Check::warn(
            "system_control_api",
            format!("{} missing", bin.display()),
            "run scripts/setup-sway-workstation.sh to install ab-system-control",
        );
    }
    if !is_executable(&bin) {
        return Check::warn(
            "system_control_api",
            format!("{} is not executable", bin.display()),
            format!("chmod +x {}", bin.display()),
        );
    }

    let text = std::fs::read_to_string(&bin).unwrap_or_default();
    if !system_control_script_has_confirm_gate(&text) {
        return Check::fail(
            "system_control_api",
            format!(
                "{} does not advertise the audited power-off confirmation gate",
                bin.display()
            ),
            "reinstall the current ab-system-control script from scripts/setup-sway-workstation.sh",
        );
    }

    let audit_dir = system_control_audit_dir();
    let audit_log = audit_dir.join("system-actions.jsonl");
    let dir_mode = mode_octal(&audit_dir);
    let log_mode = mode_octal(&audit_log);
    let dir_private = dir_mode.is_some_and(|m| m & 0o077 == 0);
    let log_private = log_mode.is_some_and(|m| m & 0o077 == 0);
    let detail = format!(
        "bin={}, audit_dir={} mode={:?}, audit_log={} mode={:?}, power_confirm_gate=true",
        bin.display(),
        audit_dir.display(),
        dir_mode.map(|m| format!("{m:o}")),
        audit_log.display(),
        log_mode.map(|m| format!("{m:o}"))
    );

    if !audit_dir.exists() || !audit_log.exists() {
        return Check::warn(
            "system_control_api",
            detail,
            "run ab-system-control audit-tail 1 once, or use any system_control action, to initialize the audit log",
        );
    }
    if !dir_private || !log_private {
        return Check::warn(
            "system_control_api",
            detail,
            format!(
                "chmod 700 {} && chmod 600 {}",
                audit_dir.display(),
                audit_log.display()
            ),
        );
    }

    let snapshot_out = match std::process::Command::new(&bin)
        .args(["status", "snapshot"])
        .env("AB_SYSTEM_CONTROL_SNAPSHOT_SKIP_AGENT_DOCTOR", "1")
        .output()
    {
        Ok(out) => out,
        Err(e) => {
            return Check::warn(
                "system_control_api",
                format!("{detail}, status_snapshot=error({e})"),
                "verify ab-system-control is executable and can run status snapshot",
            );
        }
    };
    if !snapshot_out.status.success() {
        return Check::fail(
            "system_control_api",
            format!(
                "{detail}, status_snapshot=exit({}); stderr={}",
                snapshot_out.status.code().unwrap_or(-1),
                String::from_utf8_lossy(&snapshot_out.stderr).trim()
            ),
            "reinstall the current ab-system-control script from scripts/setup-sway-workstation.sh",
        );
    }
    let snapshot: Value = match serde_json::from_slice(&snapshot_out.stdout) {
        Ok(v) => v,
        Err(e) => {
            return Check::fail(
                "system_control_api",
                format!("{detail}, status_snapshot=non_json({e})"),
                "check ab-system-control status snapshot output",
            );
        }
    };
    let snapshot_schema_ok =
        value_str(&snapshot, "/schema") == "agent_bridge.system_control.snapshot.v0";
    let snapshot_read_only = value_bool(&snapshot, "/read_only").unwrap_or(false);
    if !snapshot_schema_ok || !snapshot_read_only {
        return Check::fail(
            "system_control_api",
            format!(
                "{detail}, status_snapshot_schema={}, status_snapshot_read_only={snapshot_read_only}",
                value_str(&snapshot, "/schema")
            ),
            "reinstall the current ab-system-control script from scripts/setup-sway-workstation.sh",
        );
    }

    let snapshot_status = value_str(&snapshot, "/summary/desktop_status");
    let snapshot_watchdog = value_str(&snapshot, "/summary/watchdog_status");

    let diagnosis_out = match std::process::Command::new(&bin)
        .args(["status", "diagnose", "20"])
        .output()
    {
        Ok(out) => out,
        Err(e) => {
            return Check::warn(
                "system_control_api",
                format!("{detail}, status_diagnosis=error({e})"),
                "verify ab-system-control can run status diagnose",
            );
        }
    };
    if !diagnosis_out.status.success() {
        return Check::fail(
            "system_control_api",
            format!(
                "{detail}, status_diagnosis=exit({}); stderr={}",
                diagnosis_out.status.code().unwrap_or(-1),
                String::from_utf8_lossy(&diagnosis_out.stderr).trim()
            ),
            "reinstall the current ab-system-control script from scripts/setup-sway-workstation.sh",
        );
    }
    let diagnosis: Value = match serde_json::from_slice(&diagnosis_out.stdout) {
        Ok(v) => v,
        Err(e) => {
            return Check::fail(
                "system_control_api",
                format!("{detail}, status_diagnosis=non_json({e})"),
                "check ab-system-control status diagnose output",
            );
        }
    };
    let diagnosis_schema_ok =
        value_str(&diagnosis, "/schema") == "agent_bridge.system_control.snapshot_diagnosis.v0";
    let diagnosis_read_only = value_bool(&diagnosis, "/read_only").unwrap_or(false);
    if !diagnosis_schema_ok || !diagnosis_read_only {
        return Check::fail(
            "system_control_api",
            format!(
                "{detail}, status_diagnosis_schema={}, status_diagnosis_read_only={diagnosis_read_only}",
                value_str(&diagnosis, "/schema")
            ),
            "reinstall the current ab-system-control script from scripts/setup-sway-workstation.sh",
        );
    }
    let diagnosis_status = value_str(&diagnosis, "/status");

    Check::ok(
        "system_control_api",
        format!(
            "{detail}, status_snapshot=true, status_diagnosis=true, desktop_status={snapshot_status}, watchdog_status={snapshot_watchdog}, diagnosis_status={diagnosis_status}"
        ),
    )
}

fn value_str<'a>(v: &'a Value, pointer: &str) -> &'a str {
    v.pointer(pointer).and_then(Value::as_str).unwrap_or("")
}

fn value_bool(v: &Value, pointer: &str) -> Option<bool> {
    v.pointer(pointer).and_then(Value::as_bool)
}

fn value_u64(v: &Value, pointer: &str) -> Option<u64> {
    v.pointer(pointer).and_then(Value::as_u64)
}

fn desktop_runtime_detail(status: &Value) -> (String, Vec<String>) {
    let audio_volume = value_str(status, "/audio/volume");
    let audio_muted = value_str(status, "/audio/muted");
    let mic_muted = value_str(status, "/audio/mic_muted");
    let brightness = value_str(status, "/brightness/percent");
    let wifi_radio = value_str(status, "/wifi/radio");
    let wifi_ssid = value_str(status, "/wifi/ssid");
    let wifi_signal = value_str(status, "/wifi/signal");
    let wifi_connected = value_bool(status, "/wifi/connected").unwrap_or(false);
    let outputs_active = value_u64(status, "/display/outputs_active").unwrap_or(0);
    let outputs_powered = value_u64(status, "/display/outputs_powered").unwrap_or(0);
    let outputs_total = value_u64(status, "/display/outputs_total").unwrap_or(0);
    let focused_output = value_str(status, "/display/focused_output");
    let battery_state = value_str(status, "/battery/state");
    let battery_percent = value_str(status, "/battery/percentage");
    let swayidle = value_bool(status, "/services/swayidle").unwrap_or(false);
    let mako = value_bool(status, "/services/mako").unwrap_or(false);
    let networkmanager = value_bool(status, "/services/networkmanager").unwrap_or(false);

    let mut warnings = Vec::new();
    if outputs_powered == 0 {
        warnings.push("no powered display output".to_string());
    }
    if !swayidle {
        warnings.push("swayidle not running".to_string());
    }
    if !mako {
        warnings.push("mako not running".to_string());
    }
    if !networkmanager {
        warnings.push("NetworkManager not active".to_string());
    }
    if wifi_radio != "enabled" {
        warnings.push("WiFi radio disabled".to_string());
    } else if !wifi_connected {
        warnings.push("WiFi not connected".to_string());
    }

    let wifi_label = if wifi_connected {
        format!("{wifi_ssid} {wifi_signal}%")
    } else {
        format!("radio={wifi_radio} disconnected")
    };
    let detail = format!(
        "audio={audio_volume} muted={audio_muted} mic={mic_muted}; brightness={brightness}; wifi={wifi_label}; display={outputs_powered}/{outputs_active}/{outputs_total} powered/active/total focused={focused_output}; battery={battery_state} {battery_percent}; services=swayidle:{swayidle},mako:{mako},NetworkManager:{networkmanager}"
    );
    (detail, warnings)
}

fn check_desktop_runtime(dir: &Path) -> Check {
    let bin = system_control_bin_path(dir);
    if !bin.is_file() {
        return Check::warn(
            "desktop_runtime",
            format!("{} missing; cannot read desktop status", bin.display()),
            "install ab-system-control via scripts/setup-sway-workstation.sh",
        );
    }
    let out = match std::process::Command::new(&bin)
        .args(["status", "summary"])
        .output()
    {
        Ok(out) => out,
        Err(e) => {
            return Check::warn(
                "desktop_runtime",
                format!("failed to run {} status summary: {e}", bin.display()),
                "verify ab-system-control is executable and on the current Sway session",
            );
        }
    };
    if !out.status.success() {
        return Check::warn(
            "desktop_runtime",
            format!(
                "status summary exited {}; stderr={}",
                out.status.code().unwrap_or(-1),
                String::from_utf8_lossy(&out.stderr).trim()
            ),
            "run ab-system-control status summary manually to inspect the read-only status failure",
        );
    }
    let status: Value = match serde_json::from_slice(&out.stdout) {
        Ok(v) => v,
        Err(e) => {
            return Check::warn(
                "desktop_runtime",
                format!("status summary returned non-JSON: {e}"),
                "check ab-system-control status summary output",
            );
        }
    };
    let (detail, warnings) = desktop_runtime_detail(&status);
    if warnings.is_empty() {
        Check::ok("desktop_runtime", detail)
    } else {
        Check::warn(
            "desktop_runtime",
            format!("{detail}; warnings={}", warnings.join(",")),
            "check Sway services or use system_control/status to inspect the failing component",
        )
    }
}

fn check_instinct_observer() -> Check {
    let status = instinct::observer_status();
    let detail = format!(
        "enabled={}, installed={}, executable={}, permissions_ok={}, dir_mode={:?}, log_mode={:?}, records={}, sessions={}, verdict={}, recommendation={}, log={}",
        status.enabled,
        status.installed,
        status.executable,
        status.permissions_ok,
        status.log_dir_mode_octal,
        status.log_mode_octal,
        status.total_records,
        status.sessions,
        status.verdict,
        status.recommendation,
        status.log_path
    );

    if status.installed && !status.executable {
        return Check::warn(
            "instinct_observer",
            detail,
            format!("chmod +x {}", status.installed_path),
        );
    }
    if !status.permissions_ok {
        return Check::warn(
            "instinct_observer",
            detail,
            format!(
                "chmod 700 {} && chmod 600 {}",
                status.log_dir_path, status.log_path
            ),
        );
    }
    if status.log_bytes >= status.max_bytes {
        return Check::warn(
            "instinct_observer",
            detail,
            format!(
                "rotate or remove the observer log after preserving any needed evidence: {}",
                status.log_path
            ),
        );
    }
    Check::ok("instinct_observer", detail)
}

pub async fn run_doctor(json: bool, markdown: bool) -> Result<()> {
    let dir = install_dir();
    let checks = vec![
        check_wrapper(&dir),
        check_real_binary(&dir),
        check_svd_artifact(),
        check_daemon_runtime(),
        check_embedding_runtime().await,
        check_mcp_servers(&dir),
        check_mcp_tool_surface(),
        check_system_control_api(&dir),
        check_desktop_runtime(&dir),
        check_instinct_observer(),
    ];

    let fails = checks.iter().filter(|c| c.status == Status::Fail).count();
    let warns = checks.iter().filter(|c| c.status == Status::Warn).count();

    if json {
        let rows: Vec<_> = checks
            .iter()
            .map(|c| {
                json!({
                    "name": c.name,
                    "status": c.status.label(),
                    "detail": c.detail,
                    "fix": c.fix,
                })
            })
            .collect();
        let out = json!({
            "ok": fails == 0,
            "fails": fails,
            "warns": warns,
            "install_dir": dir.display().to_string(),
            "checks": rows,
        });
        println!("{}", serde_json::to_string_pretty(&out)?);
    } else if markdown {
        println!("## agent-bridge doctor — `{}`", dir.display());
        println!();
        println!(
            "**{} ok · {warns} warn · {fails} fail**",
            checks.len() - warns - fails
        );
        println!();
        println!("| | check | detail |");
        println!("|---|---|---|");
        for c in &checks {
            println!(
                "| {} | {} | {} |",
                c.status.md_glyph(),
                md_cell(c.name),
                md_cell(&c.detail)
            );
        }
        let fixes: Vec<&Check> = checks.iter().filter(|c| c.fix.is_some()).collect();
        if !fixes.is_empty() {
            println!();
            println!("**Fixes**");
            for c in &fixes {
                println!(
                    "- **{}** — {}",
                    md_cell(c.name),
                    md_cell(c.fix.as_deref().unwrap_or(""))
                );
            }
        }
    } else {
        println!("=== agent-bridge doctor ({}) ===", dir.display());
        for c in &checks {
            println!(
                "{} [{}] {}: {}",
                c.status.glyph(),
                c.status.label(),
                c.name,
                c.detail
            );
            if let Some(fix) = &c.fix {
                println!("    fix: {fix}");
            }
        }
        println!(
            "--- {} ok / {warns} warn / {fails} fail ---",
            checks.len() - warns - fails
        );
    }

    if fails > 0 {
        anyhow::bail!("{fails} doctor check(s) failed");
    }
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn md_cell_escapes_pipes_and_collapses_ws() {
        assert_eq!(md_cell("a | b\nc   d"), "a \\| b c d");
        assert_eq!(md_cell("  trimmed  "), "trimmed");
    }

    #[test]
    fn md_glyph_distinct_per_status() {
        assert_eq!(Status::Ok.md_glyph(), "✅");
        assert_eq!(Status::Warn.md_glyph(), "⚠️");
        assert_eq!(Status::Fail.md_glyph(), "❌");
    }

    #[test]
    fn classify_elf_vs_script() {
        assert_eq!(classify_file_head(b"\x7fELF\x02\x01"), FileKind::Elf);
        assert_eq!(
            classify_file_head(b"#!/usr/bin/env bash\n"),
            FileKind::Script
        );
        assert_eq!(
            classify_file_head(&[0xCF, 0xFA, 0xED, 0xFE]),
            FileKind::MachO
        );
        assert_eq!(classify_file_head(b"random text"), FileKind::Other);
        assert_eq!(classify_file_head(b""), FileKind::Other);
    }

    #[test]
    fn wrapper_text_detection() {
        let good = "#!/usr/bin/env bash\nexport AB_SUBSTRATE_PROJECTION=svd\nexec \"$real\" agent-bridge.real\n";
        assert!(wrapper_injects_svd(good));
        assert!(wrapper_execs_real(good));
        let no_svd = "#!/bin/bash\nexec agent-bridge.real \"$@\"\n";
        assert!(!wrapper_injects_svd(no_svd));
        assert!(wrapper_execs_real(no_svd));
        let elf_text = "not a wrapper";
        assert!(!wrapper_execs_real(elf_text));
    }

    #[test]
    fn svd_artifact_check_is_ok_when_substrate_disabled() {
        let check =
            check_svd_artifact_status("/missing/svd_projection_v1.bin", false, "svd", false);
        assert_eq!(check.status, Status::Ok);
        assert!(check.detail.contains("SVD artifact not required"));
    }

    #[test]
    fn svd_artifact_check_is_ok_when_projection_is_not_svd() {
        let check =
            check_svd_artifact_status("/missing/svd_projection_v1.bin", true, "bucket_pool", false);
        assert_eq!(check.status, Status::Ok);
        assert!(check.detail.contains("projection=bucket_pool"));
    }

    #[test]
    fn svd_artifact_check_warns_when_active_svd_is_missing() {
        let check = check_svd_artifact_status("/missing/svd_projection_v1.bin", true, "svd", false);
        assert_eq!(check.status, Status::Warn);
        assert!(check.detail.contains("SVD projection file absent"));
    }

    #[test]
    fn svd_artifact_check_ok_when_active_svd_is_present() {
        let check = check_svd_artifact_status("/tmp/svd_projection_v1.bin", true, "svd", true);
        assert_eq!(check.status, Status::Ok);
        assert!(check.detail.contains("SVD projection present"));
    }

    #[test]
    fn embedding_runtime_is_ok_only_when_readiness_and_wire_vector_agree() {
        let readiness = json!({
            "configured_backend": "gte-multilingual-base",
            "configured_dim": 768,
            "model_state": "ready",
            "semantic_ready": true
        });
        let probe = json!({
            "backend": "gte-multilingual-base",
            "dim": 768,
            "embedding": vec![0.0_f32; 768]
        });
        let check = classify_embedding_runtime(&readiness, &probe);
        assert_eq!(check.status, Status::Ok);
        assert!(check.detail.contains("backend=gte-multilingual-base"));
        assert!(check.detail.contains("vector_len=768"));
        assert!(!check.detail.contains(DOCTOR_EMBED_PROBE_TEXT));
    }

    #[test]
    fn embedding_runtime_warns_on_hash_fallback() {
        let readiness = json!({
            "configured_backend": "gte-multilingual-base",
            "configured_dim": 768,
            "model_state": "fallback",
            "semantic_ready": false
        });
        let probe = json!({
            "backend": "fnv1a-hash-384",
            "dim": 384,
            "embedding": vec![0.0_f32; 384]
        });
        let check = classify_embedding_runtime(&readiness, &probe);
        assert_eq!(check.status, Status::Warn);
        assert!(check.detail.contains("state=fallback"));
        assert!(check.detail.contains("probe backend=fnv1a-hash-384"));
        assert!(check.fix.is_some());
    }

    #[test]
    fn embedding_runtime_warns_on_declared_dimension_mismatch() {
        let readiness = json!({
            "configured_backend": "gte-multilingual-base",
            "configured_dim": 768,
            "model_state": "ready",
            "semantic_ready": true
        });
        let probe = json!({
            "backend": "gte-multilingual-base",
            "dim": 384,
            "embedding": vec![0.0_f32; 384]
        });
        let check = classify_embedding_runtime(&readiness, &probe);
        assert_eq!(check.status, Status::Warn);
        assert!(check
            .detail
            .contains("readiness backend=gte-multilingual-base dim=768"));
        assert!(check
            .detail
            .contains("probe backend=gte-multilingual-base dim=384"));
    }

    #[test]
    fn embedding_runtime_warns_when_vector_length_disagrees() {
        let readiness = json!({
            "configured_backend": "gte-multilingual-base",
            "configured_dim": 768,
            "model_state": "ready",
            "semantic_ready": true
        });
        let probe = json!({
            "backend": "gte-multilingual-base",
            "dim": 768,
            "embedding": vec![0.0_f32; 384]
        });
        let check = classify_embedding_runtime(&readiness, &probe);
        assert_eq!(check.status, Status::Warn);
        assert!(check.detail.contains("vector_len=384"));
    }

    #[test]
    fn embedding_runtime_warns_on_missing_or_wrong_typed_metadata() {
        let check = classify_embedding_runtime(
            &json!({"configured_backend": 7, "semantic_ready": "yes"}),
            &json!({"backend": "gte-multilingual-base", "embedding": "not-an-array"}),
        );
        assert_eq!(check.status, Status::Warn);
        assert!(check.detail.contains("backend=7"));
        assert!(check.detail.contains("vector_len=missing"));
    }

    #[test]
    fn parse_env_assignment_from_ps_eww_output() {
        let ps_out = "\
  PID TT  STAT      TIME COMMAND\n\
12345 ??  S      0:00.01 /Users/me/.local/bin/agent-bridge.real daemon AB_SUBSTRATE_PROJECTION=svd AB_SYNC_NODE=maxiaodeMac-Pro OTHER=value\n";
        assert_eq!(
            parse_env_assignment(ps_out, "AB_SUBSTRATE_PROJECTION"),
            Some("svd".into())
        );
        assert_eq!(
            parse_env_assignment(ps_out, "AB_SYNC_NODE"),
            Some("maxiaodeMac-Pro".into())
        );
        assert_eq!(parse_env_assignment(ps_out, "MISSING"), None);
    }

    #[test]
    fn system_control_confirm_gate_detection_requires_audit_and_confirm() {
        let good = r#"
audit "power.off" "high" "blocked" "missing --confirm"
echo "Refusing poweroff without --confirm" >&2
power off --confirm
agent_bridge.system_control.audit.v0
"#;
        assert!(system_control_script_has_confirm_gate(good));
        assert!(!system_control_script_has_confirm_gate(
            "power off\nagent_bridge.system_control.audit.v0"
        ));
        assert!(!system_control_script_has_confirm_gate(
            "power off --confirm\nRefusing poweroff without --confirm"
        ));
    }

    #[test]
    fn desktop_runtime_detail_warns_on_missing_core_services() {
        let status = json!({
            "audio": {"volume": "75%", "muted": "no", "mic_muted": "no"},
            "brightness": {"percent": "80%"},
            "wifi": {"radio": "enabled", "connected": true, "ssid": "Lab", "signal": "71"},
            "display": {"outputs_total": 1, "outputs_active": 1, "outputs_powered": 1, "focused_output": "eDP-1"},
            "battery": {"state": "charging", "percentage": "90%"},
            "services": {"swayidle": true, "mako": true, "networkmanager": true}
        });
        let (detail, warnings) = desktop_runtime_detail(&status);
        assert!(warnings.is_empty(), "{warnings:?}");
        assert!(detail.contains("audio=75%"));
        assert!(detail.contains("wifi=Lab 71%"));

        let broken = json!({
            "wifi": {"radio": "disabled", "connected": false},
            "display": {"outputs_total": 1, "outputs_active": 1, "outputs_powered": 0},
            "services": {"swayidle": false, "mako": false, "networkmanager": false}
        });
        let (_, warnings) = desktop_runtime_detail(&broken);
        assert!(warnings.iter().any(|w| w.contains("no powered")));
        assert!(warnings.iter().any(|w| w.contains("swayidle")));
        assert!(warnings.iter().any(|w| w.contains("WiFi radio disabled")));
    }

    #[test]
    fn mcp_process_classification_detects_stale_and_direct_binaries() {
        let current = ProcessTextFile {
            path: "/Users/me/.local/bin/agent-bridge.real".into(),
            inode: Some(42),
        };
        assert_eq!(
            classify_mcp_process(Some(&current), None, Some(42)),
            McpProcessKind::CurrentReal
        );

        let stale = ProcessTextFile {
            path: "/Users/me/.local/bin/agent-bridge.real".into(),
            inode: Some(41),
        };
        assert_eq!(
            classify_mcp_process(Some(&stale), None, Some(42)),
            McpProcessKind::StaleReal
        );

        let direct = ProcessTextFile {
            path: "/Users/me/.local/bin/agent-bridge".into(),
            inode: Some(7),
        };
        assert_eq!(
            classify_mcp_process(Some(&direct), None, Some(42)),
            McpProcessKind::DirectBinary
        );

        assert_eq!(
            classify_mcp_process(
                None,
                Some("/Users/me/.local/bin/agent-bridge.real mcp"),
                None
            ),
            McpProcessKind::CurrentReal
        );
    }

    #[test]
    fn mcp_process_summary_includes_parent_age_and_exe_for_stale_rows() {
        let rows = vec![
            McpProcessObservation {
                pid: 101,
                kind: McpProcessKind::CurrentReal,
                text_file: Some(ProcessTextFile {
                    path: "/home/me/.local/bin/agent-bridge.real".into(),
                    inode: Some(42),
                }),
                command: Some("/home/me/.local/bin/agent-bridge.real mcp".into()),
                ppid: Some(90),
                parent_command: Some("cursor --type=extensionHost".into()),
                elapsed: Some("00:01:02".into()),
            },
            McpProcessObservation {
                pid: 202,
                kind: McpProcessKind::StaleReal,
                text_file: Some(ProcessTextFile {
                    path: "/home/me/.local/bin/agent-bridge.real (deleted)".into(),
                    inode: Some(41),
                }),
                command: Some("/home/me/.local/bin/agent-bridge.real mcp".into()),
                ppid: Some(77),
                parent_command: Some("claude --continue".into()),
                elapsed: Some("01:17:30".into()),
            },
        ];

        let detail = format_mcp_process_summary(&rows);

        assert!(detail.contains("2 MCP server(s): 1 current .real, 1 stale .real"));
        assert!(detail.contains("refresh parent(s): ppid=77 count=1 parent=claude --continue"));
        assert!(detail.contains("stale detail"));
        assert!(detail.contains("pid=202"));
        assert!(detail.contains("ppid=77"));
        assert!(detail.contains("parent=claude --continue"));
        assert!(detail.contains("elapsed=01:17:30"));
        assert!(detail.contains("exe=/home/me/.local/bin/agent-bridge.real (deleted)"));
    }

    #[test]
    fn mcp_process_summary_distinguishes_current_active_from_other_stale_clients() {
        let rows = vec![
            McpProcessObservation {
                pid: 101,
                kind: McpProcessKind::CurrentReal,
                text_file: Some(ProcessTextFile {
                    path: "/home/me/.local/bin/agent-bridge.real".into(),
                    inode: Some(42),
                }),
                command: Some("/home/me/.local/bin/agent-bridge.real mcp".into()),
                ppid: Some(90),
                parent_command: Some("codex app-server".into()),
                elapsed: Some("00:00:18".into()),
            },
            McpProcessObservation {
                pid: 202,
                kind: McpProcessKind::StaleReal,
                text_file: Some(ProcessTextFile {
                    path: "/home/me/.local/bin/agent-bridge.real (deleted)".into(),
                    inode: Some(41),
                }),
                command: Some("/home/me/.local/bin/agent-bridge.real mcp".into()),
                ppid: Some(77),
                parent_command: Some("warp".into()),
                elapsed: Some("02:00:00".into()),
            },
        ];

        let detail = format_mcp_process_summary(&rows);
        let hint = mcp_process_reconnect_hint(&rows);

        assert!(detail.contains("at least one current .real MCP server is active"));
        assert!(detail.contains("stale/direct/unknown rows are other clients or old sessions"));
        assert!(detail.contains("refresh parent(s): ppid=77 count=1 parent=warp"));
        assert!(hint.contains("current .real MCP server(s) are already active"));
        assert!(hint.contains("restart only stale/direct/unknown"));
        assert!(hint.contains("reload or restart that host app/server"));
    }

    #[test]
    fn mcp_process_summary_warns_when_no_current_real_process_exists() {
        let rows = vec![McpProcessObservation {
            pid: 202,
            kind: McpProcessKind::StaleReal,
            text_file: Some(ProcessTextFile {
                path: "/home/me/.local/bin/agent-bridge.real (deleted)".into(),
                inode: Some(41),
            }),
            command: Some("/home/me/.local/bin/agent-bridge.real mcp".into()),
            ppid: Some(77),
            parent_command: Some("claude --continue".into()),
            elapsed: Some("01:17:30".into()),
        }];

        let detail = format_mcp_process_summary(&rows);
        let hint = mcp_process_reconnect_hint(&rows);

        assert!(detail.contains("no current .real MCP server detected"));
        assert!(detail.contains("active client may still be stale"));
        assert!(detail.contains("refresh parent(s): ppid=77 count=1 parent=claude --continue"));
        assert!(hint.contains("restart the MCP client(s) so they respawn"));
        assert!(hint.contains("soft MCP reconnect leaves stale children"));
    }

    #[test]
    fn status_labels_stable() {
        // Pinned — json consumers + tests grep these.
        assert_eq!(Status::Ok.label(), "ok");
        assert_eq!(Status::Warn.label(), "warn");
        assert_eq!(Status::Fail.label(), "fail");
    }
}
