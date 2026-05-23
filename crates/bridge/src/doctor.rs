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

/// Check 4: SVD projection artifact resolvable.
fn check_svd_artifact() -> Check {
    let path = std::env::var("AB_SUBSTRATE_SVD_PATH")
        .unwrap_or_else(|_| "/Data/CascadeProjects/AiOT/build/svd_projection_v1.bin".into());
    if Path::new(&path).is_file() {
        Check::ok("svd_artifact", format!("SVD projection present: {path}"))
    } else {
        Check::warn(
            "svd_artifact",
            format!("SVD projection file absent: {path} — substrate falls back to bucket-pool"),
            "build/distribute svd_projection_v1.bin, or accept bucket-pool fallback",
        )
    }
}

/// Read AGENT_BRIDGE / AB_SUBSTRATE env of a pid from /proc (Linux). Best-effort.
fn proc_env(pid: i64, key: &str) -> Option<String> {
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

pub async fn run_doctor(json: bool) -> Result<()> {
    let dir = install_dir();
    let checks = vec![
        check_wrapper(&dir),
        check_real_binary(&dir),
        check_svd_artifact(),
        check_daemon_runtime(),
        check_mcp_servers(&dir),
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
