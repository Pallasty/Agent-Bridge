//! `agent-bridge sync` — cross-device memory sync via private git repo.
//!
//! Replaces the old `~/agent-bridge-memory/sync.sh` (bash + python).
//! All logic lives in this binary so the Stop hook can call
//! `agent-bridge sync &` directly.
//!
//! Steady-state algorithm (idempotent):
//!   1. `git pull --rebase --autostash`
//!   2. `memory_import(NewerWins)` from `<repo>/memory.jsonl`
//!   3. `memory_export` overwriting `<repo>/memory.jsonl`
//!   4. `git add` then commit + push if anything changed
//!
//! `agent-bridge sync init` bootstraps a fresh machine via `gh` CLI:
//! it ensures `gh auth status` is healthy, detects/creates the private
//! repo `<user>/agent-bridge-memory`, clones to the configured path, and
//! runs an initial sync.

use ab_store::{
    default_db_path, ImportConflictPolicy, MemoryExportFilter, SqliteStore, StateStore,
};
use anyhow::{anyhow, bail, Context, Result};
use std::path::{Path, PathBuf};
use std::process::{Command, Stdio};

const DEFAULT_REPO_NAME: &str = "agent-bridge-memory";
const MEMORY_FILE: &str = "memory.jsonl";
const FORUM_FILE: &str = "forum.jsonl";

/// Resolve the cross-device memory repo path.
///
/// Resolution order (first match wins):
///   1. `AGENT_BRIDGE_MEMORY_REPO` env var
///   2. legacy `~/agent-bridge-memory` (README v0 default, if it has `.git`)
///   3. legacy `~/Projects/agent-bridge-memory` (some users put it here)
///   4. sibling of `state.db`: `<state-dir>/memory-sync` — the new canonical location
pub fn default_memory_repo_path() -> PathBuf {
    if let Ok(p) = std::env::var("AGENT_BRIDGE_MEMORY_REPO") {
        if !p.trim().is_empty() {
            return PathBuf::from(p);
        }
    }
    if let Ok(home) = std::env::var("HOME") {
        let home = PathBuf::from(home);
        for legacy in ["agent-bridge-memory", "Projects/agent-bridge-memory"] {
            let p = home.join(legacy);
            if p.join(".git").exists() {
                return p;
            }
        }
    }
    let db_path = std::env::var("AGENT_BRIDGE_DB")
        .ok()
        .map(PathBuf::from)
        .unwrap_or_else(default_db_path);
    db_path
        .parent()
        .map(|p| p.join("memory-sync"))
        .unwrap_or_else(|| PathBuf::from("./memory-sync"))
}

/// One sync round. Idempotent; safe to invoke from cron / Stop hook.
///
/// Returns `Ok(true)` when a commit + push happened, `Ok(false)` when
/// nothing changed (or the repo isn't initialised).
pub async fn run_sync(verbose: bool) -> Result<bool> {
    let repo = default_memory_repo_path();
    if !repo.join(".git").exists() {
        eprintln!(
            "[sync] no memory-sync repo at {} — run `agent-bridge sync init`",
            repo.display()
        );
        return Ok(false);
    }
    if verbose {
        eprintln!("[sync] repo: {}", repo.display());
    }

    git_pull_rebase(&repo, verbose);

    let memory_file = repo.join(MEMORY_FILE);
    let store = open_store().await?;

    if memory_file.exists() {
        let report = store
            .memory_import(&memory_file, ImportConflictPolicy::NewerWins, None)
            .await
            .context("memory_import")?;
        if verbose {
            eprintln!(
                "[sync] memory import: inserted={} updated={} skipped={} malformed={}",
                report.inserted, report.updated, report.skipped, report.malformed
            );
        }
    }

    // Forum import — natural-key dedup, append-only. Subscriptions stay local.
    let forum_file = repo.join(FORUM_FILE);
    if forum_file.exists() {
        let freport = store.forum_import(&forum_file).await.context("forum_import")?;
        if verbose {
            eprintln!(
                "[sync] forum import: threads_inserted={} threads_matched={} posts_inserted={} posts_skipped={} malformed={}",
                freport.threads_inserted,
                freport.threads_matched,
                freport.posts_inserted,
                freport.posts_skipped,
                freport.malformed
            );
        }
    }

    let filter = MemoryExportFilter::default();
    let result = store
        .memory_export(&filter, &memory_file)
        .await
        .context("memory_export")?;
    if verbose {
        eprintln!(
            "[sync] memory export: memories_written={}",
            result.memories_written
        );
    }

    let fresult = store
        .forum_export(&forum_file)
        .await
        .context("forum_export")?;
    if verbose {
        eprintln!(
            "[sync] forum export: threads_written={} posts_written={}",
            fresult.threads_written, fresult.posts_written
        );
    }
    drop(store);

    // Stage first so brand-new files are noticed (git diff doesn't see untracked).
    run_git(&repo, &["add", MEMORY_FILE, FORUM_FILE]).context("git add")?;
    let memory_changed = git_index_changed(&repo, MEMORY_FILE)?;
    let forum_changed = git_index_changed(&repo, FORUM_FILE)?;
    if !memory_changed && !forum_changed {
        if verbose {
            eprintln!("[sync] no changes to push.");
        }
        return Ok(false);
    }

    let host = hostname_short();
    let ts = iso8601_utc_now();
    let msg = format!("sync from {host} at {ts}");

    run_git(&repo, &["commit", "-m", &msg]).context("git commit")?;
    run_git(&repo, &["push", "origin", "HEAD"]).context("git push")?;
    if verbose {
        eprintln!("[sync] pushed: {msg}");
    }
    Ok(true)
}

/// Bootstrap the memory-sync repo on a new machine via `gh` CLI.
///
/// `repo_arg` overrides the repo name (default: `agent-bridge-memory`).
pub async fn run_init(repo_arg: Option<String>) -> Result<()> {
    ensure_command_on_path(
        "gh",
        "Install with: brew install gh   (or see https://cli.github.com)",
    )?;
    ensure_command_on_path("git", "git is required for memory sync")?;

    if !gh_authenticated() {
        bail!(
            "`gh` is not authenticated. Run:\n    gh auth login\nthen rerun `agent-bridge sync init`."
        );
    }

    let user = gh_username()?;
    let repo_name = repo_arg.unwrap_or_else(|| DEFAULT_REPO_NAME.to_string());
    let full = format!("{user}/{repo_name}");
    let dest = default_memory_repo_path();

    if dest.join(".git").exists() {
        eprintln!("[init] already cloned at {}", dest.display());
    } else {
        if let Some(parent) = dest.parent() {
            std::fs::create_dir_all(parent)
                .with_context(|| format!("mkdir {}", parent.display()))?;
        }
        if !gh_repo_exists(&full) {
            eprintln!("[init] creating private repo {full}");
            run_gh(&[
                "repo",
                "create",
                &full,
                "--private",
                "--description",
                "agent-bridge cross-device memory store",
            ])
            .context("gh repo create")?;
        } else {
            eprintln!("[init] repo {full} already exists on GitHub");
        }
        eprintln!("[init] cloning into {}", dest.display());
        let dest_str = dest
            .to_str()
            .ok_or_else(|| anyhow!("non-UTF8 path: {}", dest.display()))?;
        run_gh(&["repo", "clone", &full, dest_str]).context("gh repo clone")?;
    }

    eprintln!("[init] running first sync …");
    run_sync(true).await?;
    eprintln!();
    eprintln!("Cross-device memory sync ready.");
    eprintln!("  • Repo path: {}", dest.display());
    eprintln!("  • Stop hook will auto-sync at session end (Claude Code).");
    eprintln!("  • Manual sync: agent-bridge sync");
    Ok(())
}

/// Print resolved repo path + remote + last commit. No network calls.
pub fn run_status() -> Result<()> {
    let repo = default_memory_repo_path();
    println!("repo path:  {}", repo.display());
    if !repo.join(".git").exists() {
        println!("status:     not initialised — run `agent-bridge sync init`");
        return Ok(());
    }
    let remote = git_capture(&repo, &["remote", "get-url", "origin"])
        .unwrap_or_else(|_| "(no origin)".into());
    println!("remote:     {}", remote.trim());
    let last = git_capture(&repo, &["log", "-1", "--format=%h %s (%cr)"])
        .unwrap_or_else(|_| "(no commits)".into());
    println!("last sync:  {}", last.trim());
    let dirty = git_capture(&repo, &["status", "--porcelain"]).unwrap_or_default();
    println!(
        "dirty:      {}",
        if dirty.trim().is_empty() {
            "clean"
        } else {
            "yes"
        }
    );
    Ok(())
}

// ─── helpers ────────────────────────────────────────────────────────────

async fn open_store() -> Result<SqliteStore> {
    let db_path = std::env::var("AGENT_BRIDGE_DB")
        .ok()
        .map(PathBuf::from)
        .unwrap_or_else(default_db_path);
    SqliteStore::open(&db_path)
        .await
        .with_context(|| format!("open {}", db_path.display()))
}

fn ensure_command_on_path(cmd: &str, hint: &str) -> Result<()> {
    let path = std::env::var_os("PATH").ok_or_else(|| anyhow!("PATH unset"))?;
    let found = std::env::split_paths(&path).any(|p| p.join(cmd).is_file());
    if !found {
        bail!("`{cmd}` not on PATH. {hint}");
    }
    Ok(())
}

fn gh_authenticated() -> bool {
    Command::new("gh")
        .args(["auth", "status"])
        .stdout(Stdio::null())
        .stderr(Stdio::null())
        .status()
        .map(|s| s.success())
        .unwrap_or(false)
}

fn gh_username() -> Result<String> {
    let out = Command::new("gh")
        .args(["api", "user", "--jq", ".login"])
        .output()
        .context("invoke gh api user")?;
    if !out.status.success() {
        bail!(
            "gh api user failed: {}",
            String::from_utf8_lossy(&out.stderr).trim()
        );
    }
    let user = String::from_utf8_lossy(&out.stdout).trim().to_string();
    if user.is_empty() {
        bail!("gh api user returned an empty login");
    }
    Ok(user)
}

fn gh_repo_exists(full: &str) -> bool {
    Command::new("gh")
        .args(["repo", "view", full])
        .stdout(Stdio::null())
        .stderr(Stdio::null())
        .status()
        .map(|s| s.success())
        .unwrap_or(false)
}

fn run_gh(args: &[&str]) -> Result<()> {
    let status = Command::new("gh")
        .args(args)
        .status()
        .context("invoke gh")?;
    if !status.success() {
        bail!("gh {} failed (exit {status})", args.join(" "));
    }
    Ok(())
}

fn run_git(repo: &Path, args: &[&str]) -> Result<()> {
    let status = Command::new("git")
        .arg("-C")
        .arg(repo)
        .args(args)
        .status()
        .context("invoke git")?;
    if !status.success() {
        bail!("git {} failed (exit {status})", args.join(" "));
    }
    Ok(())
}

fn git_capture(repo: &Path, args: &[&str]) -> Result<String> {
    let out = Command::new("git")
        .arg("-C")
        .arg(repo)
        .args(args)
        .output()
        .context("invoke git")?;
    if !out.status.success() {
        bail!(
            "git {} failed: {}",
            args.join(" "),
            String::from_utf8_lossy(&out.stderr).trim()
        );
    }
    Ok(String::from_utf8_lossy(&out.stdout).into_owned())
}

/// Best-effort `git pull --rebase --autostash`. Last-resort fallback (when
/// rebase fails) checks out the remote `memory.jsonl` so subsequent
/// import/export reconciles via the local SQLite store.
fn git_pull_rebase(repo: &Path, verbose: bool) {
    let out = Command::new("git")
        .arg("-C")
        .arg(repo)
        .args(["pull", "--rebase", "--autostash"])
        .output();
    match out {
        Ok(o) if o.status.success() => {}
        Ok(o) => {
            if verbose {
                eprintln!(
                    "[sync] git pull failed: {}",
                    String::from_utf8_lossy(&o.stderr).trim()
                );
            }
            let _ = Command::new("git")
                .arg("-C")
                .arg(repo)
                .args(["fetch", "origin"])
                .status();
            // Try common default branches in order; first success wins.
            for branch in ["origin/HEAD", "origin/main", "origin/master"] {
                let s = Command::new("git")
                    .arg("-C")
                    .arg(repo)
                    .args(["checkout", branch, "--", MEMORY_FILE])
                    .status();
                if matches!(s, Ok(s) if s.success()) {
                    break;
                }
            }
        }
        Err(e) => {
            if verbose {
                eprintln!("[sync] could not invoke git pull ({e})");
            }
        }
    }
}

/// Returns true iff the staging area differs from HEAD for `path`.
/// Use this AFTER `git add <path>` to detect both new files and modifications.
fn git_index_changed(repo: &Path, path: &str) -> Result<bool> {
    let status = Command::new("git")
        .arg("-C")
        .arg(repo)
        .args(["diff", "--cached", "--quiet", "--", path])
        .status()
        .context("invoke git diff --cached")?;
    match status.code() {
        Some(0) => Ok(false), // nothing staged
        Some(1) => Ok(true),  // staged change present
        _ => bail!("git diff --cached returned unexpected status {status}"),
    }
}

fn hostname_short() -> String {
    Command::new("hostname")
        .arg("-s")
        .output()
        .ok()
        .and_then(|o| {
            if o.status.success() {
                Some(String::from_utf8_lossy(&o.stdout).trim().to_string())
            } else {
                None
            }
        })
        .filter(|s| !s.is_empty())
        .unwrap_or_else(|| "unknown".to_string())
}

/// Cheap ISO-8601 UTC timestamp via the `date` binary; falls back to the
/// Unix epoch in seconds when `date` is missing or fails.
fn iso8601_utc_now() -> String {
    let out = Command::new("date")
        .args(["-u", "+%Y-%m-%dT%H:%M:%SZ"])
        .output();
    if let Ok(o) = out {
        if o.status.success() {
            let s = String::from_utf8_lossy(&o.stdout).trim().to_string();
            if !s.is_empty() {
                return s;
            }
        }
    }
    let secs = std::time::SystemTime::now()
        .duration_since(std::time::UNIX_EPOCH)
        .map(|d| d.as_secs())
        .unwrap_or(0);
    format!("epoch+{secs}")
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn env_override_wins() {
        let tmp =
            std::env::temp_dir().join(format!("agent-bridge-sync-test-{}", std::process::id()));
        std::env::set_var("AGENT_BRIDGE_MEMORY_REPO", &tmp);
        let p = default_memory_repo_path();
        assert_eq!(p, tmp);
        std::env::remove_var("AGENT_BRIDGE_MEMORY_REPO");
    }

    #[test]
    fn empty_env_falls_through_to_default() {
        std::env::set_var("AGENT_BRIDGE_MEMORY_REPO", "   ");
        let p = default_memory_repo_path();
        assert_ne!(p.as_os_str(), "   ");
        std::env::remove_var("AGENT_BRIDGE_MEMORY_REPO");
    }
}
