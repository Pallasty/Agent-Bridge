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
        Self { name, status: Status::Ok, detail: detail.into(), fix: None }
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
    Missing,
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
            format!("{} is neither a known binary nor a script", wrapper.display()),
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

/// Check 6: running MCP servers went through the wrapper (exe basename =
/// `agent-bridge.real`), NOT the clobbered direct binary. This catches the
/// integrity problem (wrapper bypassed) without false-positiving on normal
/// post-deploy inode churn — an MCP server execing an *older inode* of
/// `agent-bridge.real` is fine (a `/mcp` reconnect refreshes tools); an MCP
/// server execing `agent-bridge` (no `.real`) means the wrapper was bypassed.
fn check_mcp_servers(_dir: &Path) -> Check {
    let pids = pgrep(r"agent-bridge mcp");
    if pids.is_empty() {
        return Check::ok("mcp_servers", "no agent-bridge mcp processes running");
    }
    let mut bypassed = Vec::new();
    for pid in &pids {
        if let Ok(exe) = std::fs::read_link(format!("/proc/{pid}/exe")) {
            let s = exe.to_string_lossy();
            // bash = still in wrapper before exec (transient); .real = went
            // through wrapper (good). Anything ending in /agent-bridge (no
            // .real) = direct binary = wrapper bypassed.
            let base = exe
                .file_name()
                .map(|n| n.to_string_lossy().to_string())
                .unwrap_or_default();
            let base = base.trim_end_matches(" (deleted)");
            if base == "agent-bridge" && !s.contains("bash") {
                bypassed.push(*pid);
            }
        }
    }
    if bypassed.is_empty() {
        Check::ok(
            "mcp_servers",
            format!(
                "{} MCP server(s) — all went through the wrapper (exec agent-bridge.real)",
                pids.len()
            ),
        )
    } else {
        // WARN not FAIL: the authoritative integrity gate is the `wrapper`
        // check. These are MCP servers spawned while the wrapper was clobbered
        // (or before a redeploy) — they serve a stale tool surface (e.g. miss
        // forum_digest) until the client reconnects. Lingering old servers from
        // past sessions are expected churn, not a current-deployment failure.
        Check::warn(
            "mcp_servers",
            format!(
                "{} of {} MCP server(s) exec the direct agent-bridge binary, not \
                 the wrapper→.real path (PIDs {:?}) — spawned before the wrapper \
                 was (re)installed; they serve a stale tool surface",
                bypassed.len(),
                pids.len(),
                bypassed
            ),
            "restart the MCP client(s) so they respawn from the current wrapper \
             (the `wrapper` check above is the authoritative integrity gate)",
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
            println!("{} [{}] {}: {}", c.status.glyph(), c.status.label(), c.name, c.detail);
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
        assert_eq!(classify_file_head(b"#!/usr/bin/env bash\n"), FileKind::Script);
        assert_eq!(classify_file_head(&[0xCF, 0xFA, 0xED, 0xFE]), FileKind::MachO);
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
    fn status_labels_stable() {
        // Pinned — json consumers + tests grep these.
        assert_eq!(Status::Ok.label(), "ok");
        assert_eq!(Status::Warn.label(), "warn");
        assert_eq!(Status::Fail.label(), "fail");
    }
}
