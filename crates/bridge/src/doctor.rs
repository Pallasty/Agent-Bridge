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
//! failure into an explicit report. Pure file/process inspection; no mutation.
//! See `lesson_wrapper_clobbered_orphans_real_deploys_2026_05_23`.

use std::path::{Path, PathBuf};

#[cfg(unix)]
use std::os::unix::fs::MetadataExt;

use anyhow::Result;
use serde_json::json;

use ab_bridge::instinct;
use ab_bridge::mcp_tools::exposed_tool_count_for;

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
    let mut current_real = Vec::new();
    let mut stale_real = Vec::new();
    let mut direct_binary = Vec::new();
    let mut unknown = Vec::new();

    for pid in &pids {
        let text = process_text_file(*pid);
        let command = process_command(*pid);
        match classify_mcp_process(text.as_ref(), command.as_deref(), real_inode) {
            McpProcessKind::CurrentReal => current_real.push(*pid),
            McpProcessKind::StaleReal => stale_real.push(*pid),
            McpProcessKind::DirectBinary => direct_binary.push(*pid),
            McpProcessKind::Unknown => unknown.push(*pid),
        }
    }

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
            format!(
                "{} MCP server(s): {} current .real, {} stale .real, {} direct \
                 agent-bridge binary, {} unknown (current {:?}, stale {:?}, direct {:?}, unknown {:?})",
                pids.len(),
                current_real.len(),
                stale_real.len(),
                direct_binary.len(),
                unknown.len(),
                current_real,
                stale_real,
                direct_binary,
                unknown
            ),
            "restart the MCP client(s) so they respawn from the current wrapper \
             and re-read tools/list; this refreshes newly added tool manifests",
        )
    }
}

fn check_mcp_tool_surface() -> Check {
    let cursor_count =
        exposed_tool_count_for(Some("claude-standard"), Some("cursor"), Some("standard"));
    let process_count = exposed_tool_count_for(
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

fn check_instinct_observer() -> Check {
    let status = instinct::observer_status();
    let detail = format!(
        "enabled={}, installed={}, executable={}, records={}, sessions={}, verdict={}, recommendation={}, log={}",
        status.enabled,
        status.installed,
        status.executable,
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
        check_mcp_servers(&dir),
        check_mcp_tool_surface(),
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
    fn status_labels_stable() {
        // Pinned — json consumers + tests grep these.
        assert_eq!(Status::Ok.label(), "ok");
        assert_eq!(Status::Warn.label(), "warn");
        assert_eq!(Status::Fail.label(), "fail");
    }
}
