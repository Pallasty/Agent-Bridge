//! `agent-bridge sync` — cross-device memory sync via private git repo.
//!
//! Replaces the old `~/agent-bridge-memory/sync.sh` (bash + python).
//! All logic lives in this binary so the Stop hook can call
//! `agent-bridge sync &` directly.
//!
//! Steady-state algorithm (idempotent):
//!   1. `git pull --rebase --autostash`
//!   2. `memory_import(VersionVectorMerge)` from `<repo>/memory.jsonl`
//!      (Track MS-3 — conflict-aware; concurrent same-key edits become
//!      non-destructive conflict copies instead of a silent last-write-wins
//!      drop; falls back to NewerWins for rows without a version vector yet)
//!   3. `memory_export` overwriting `<repo>/memory.jsonl`
//!   4. `git add` then commit + push if anything changed
//!
//! `agent-bridge sync init` bootstraps a fresh machine via `gh` CLI:
//! it ensures `gh auth status` is healthy, detects/creates the private
//! repo `<user>/agent-bridge-memory`, clones to the configured path, and
//! runs an initial sync.

use ab_store::{
    default_db_path, node_id_from_name, ImportConflictPolicy, MemoryExportFilter, MemoryRecord,
    SqliteStore, StateStore,
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
///
/// Failure tracking: maintains `~/.cache/agent-bridge/sync_state.json` with
/// a consecutive-fail counter. After 3 consecutive failures, emits a
/// `kind=alert` memory (with a 1h cooldown so persistent failures don't
/// spam the memory store). On success, the counter is reset. This is the
/// detection layer that would have surfaced the 2026-05-18→19 31h silent
/// loop within 45 minutes of onset; see
/// `lesson_sync_fallback_branch_divergence_gap_2026_05_19`.
pub async fn run_sync(verbose: bool) -> Result<bool> {
    let outcome = run_sync_inner(verbose).await;
    let _ = record_sync_outcome(&outcome, verbose).await;
    outcome
}

async fn run_sync_inner(verbose: bool) -> Result<bool> {
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

    // If pull left us off a branch (or some earlier run did and was never
    // cleaned), refuse to proceed: every code path below assumes HEAD is on a
    // real branch, and the prior failure mode was "commit on detached HEAD,
    // push HEAD, get rejected with 'destination not a full refname'" — which
    // looks like success in the logs but blocks all future syncs.
    let branch = git_current_branch(&repo).with_context(|| {
        "sync requires HEAD on a branch; aborting. Manual recovery: \
         cd repo && git rebase --abort (or --quit), then check out main."
    })?;

    let memory_file = repo.join(MEMORY_FILE);
    let store = open_store().await?;

    if memory_file.exists() {
        let report = store
            .memory_import(&memory_file, ImportConflictPolicy::VersionVectorMerge, None)
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
    // Push the named branch — never `HEAD`. A detached commit pushed as
    // `HEAD` is rejected by both gitlab and github with "destination is not
    // a full refname", and silent for ~1.5 days of "no changes" sync logs.
    let refspec = format!("{branch}:refs/heads/{branch}");
    push_origin_primary_aware(&repo, &branch, &refspec, verbose).context("git push")?;
    if verbose {
        eprintln!("[sync] pushed: {msg}");
    }
    Ok(true)
}

/// Provider for the cross-device memory repo. Resolved from the CLI
/// `--provider` flag; `Auto` picks gitlab if `glab` is on PATH and
/// `gh` isn't, github otherwise.
#[derive(Copy, Clone, Debug)]
pub enum Provider {
    Github,
    Gitlab,
    Auto,
}

impl Provider {
    fn cli(self) -> &'static str {
        match self {
            Provider::Github => "gh",
            Provider::Gitlab => "glab",
            // Auto is resolved before reaching this point.
            Provider::Auto => "gh",
        }
    }

    fn forge(self) -> &'static str {
        match self {
            Provider::Github => "GitHub",
            Provider::Gitlab => "GitLab",
            Provider::Auto => "GitHub",
        }
    }

    fn install_hint(self) -> &'static str {
        match self {
            Provider::Github => {
                "Install with: brew install gh   (or see https://cli.github.com)"
            }
            Provider::Gitlab => {
                "Install with: brew install glab   (or see https://gitlab.com/gitlab-org/cli)"
            }
            Provider::Auto => "",
        }
    }

    /// `gh api user --jq .login` (GitHub) vs `glab api user --jq .username`.
    fn user_jq(self) -> &'static str {
        match self {
            Provider::Github => ".login",
            Provider::Gitlab => ".username",
            Provider::Auto => ".login",
        }
    }
}

/// Resolve `Auto` based on which CLI is present. Tie-break to github
/// (legacy default) when both are installed — the user can pick
/// explicitly with `--provider gitlab` if they want the new path.
fn resolve_provider(p: Provider) -> Provider {
    match p {
        Provider::Auto => {
            let has_gh = which_on_path("gh");
            let has_glab = which_on_path("glab");
            if has_glab && !has_gh {
                Provider::Gitlab
            } else {
                Provider::Github
            }
        }
        explicit => explicit,
    }
}

fn which_on_path(cmd: &str) -> bool {
    let Some(path) = std::env::var_os("PATH") else {
        return false;
    };
    std::env::split_paths(&path).any(|p| p.join(cmd).is_file())
}

/// Bootstrap the memory-sync repo on a new machine via `gh` (GitHub) or
/// `glab` (GitLab). `repo_arg` overrides the repo name (default:
/// `agent-bridge-memory`).
pub async fn run_init(repo_arg: Option<String>, provider: Provider) -> Result<()> {
    let provider = resolve_provider(provider);
    let cli = provider.cli();
    ensure_command_on_path(cli, provider.install_hint())?;
    ensure_command_on_path("git", "git is required for memory sync")?;

    if !forge_authenticated(provider) {
        bail!(
            "`{cli}` is not authenticated. Run:\n    {cli} auth login\nthen rerun `agent-bridge sync init`."
        );
    }

    let user = forge_username(provider)?;
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
        if !forge_repo_exists(provider, &full) {
            eprintln!("[init] creating private repo {full} on {}", provider.forge());
            run_forge(
                provider,
                &[
                    "repo",
                    "create",
                    &full,
                    "--private",
                    "--description",
                    "agent-bridge cross-device memory store",
                ],
            )
            .with_context(|| format!("{cli} repo create"))?;
        } else {
            eprintln!("[init] repo {full} already exists on {}", provider.forge());
        }
        eprintln!("[init] cloning into {}", dest.display());
        let dest_str = dest
            .to_str()
            .ok_or_else(|| anyhow!("non-UTF8 path: {}", dest.display()))?;
        run_forge(provider, &["repo", "clone", &full, dest_str])
            .with_context(|| format!("{cli} repo clone"))?;
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

// ─── failure tracking + alert emit ──────────────────────────────────────

const SYNC_FAIL_ALERT_THRESHOLD: u32 = 3;
const SYNC_ALERT_COOLDOWN_SECS: u64 = 3600;

#[derive(Default, serde::Serialize, serde::Deserialize)]
struct SyncState {
    #[serde(default)]
    consecutive_fails: u32,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    last_alert_at_unix: Option<u64>,
}

fn sync_state_path() -> PathBuf {
    let cache_dir = std::env::var("XDG_CACHE_HOME")
        .map(PathBuf::from)
        .unwrap_or_else(|_| {
            std::env::var("HOME")
                .map(|h| PathBuf::from(h).join(".cache"))
                .unwrap_or_else(|_| PathBuf::from("/tmp"))
        });
    cache_dir.join("agent-bridge").join("sync_state.json")
}

fn load_sync_state() -> SyncState {
    std::fs::read_to_string(sync_state_path())
        .ok()
        .and_then(|s| serde_json::from_str(&s).ok())
        .unwrap_or_default()
}

fn save_sync_state(state: &SyncState) -> Result<()> {
    let path = sync_state_path();
    if let Some(parent) = path.parent() {
        std::fs::create_dir_all(parent)
            .with_context(|| format!("mkdir {}", parent.display()))?;
    }
    let tmp = path.with_extension("tmp");
    let body = serde_json::to_string_pretty(state).context("serialize sync_state")?;
    std::fs::write(&tmp, body).with_context(|| format!("write {}", tmp.display()))?;
    std::fs::rename(&tmp, &path).with_context(|| format!("rename {}", tmp.display()))?;
    Ok(())
}

fn now_unix_secs() -> u64 {
    std::time::SystemTime::now()
        .duration_since(std::time::UNIX_EPOCH)
        .map(|d| d.as_secs())
        .unwrap_or(0)
}

/// Update `sync_state.json` based on the latest sync outcome, and emit a
/// `kind=alert` memory once `SYNC_FAIL_ALERT_THRESHOLD` consecutive failures
/// are reached. Cooldown of `SYNC_ALERT_COOLDOWN_SECS` between alerts so
/// the same persistent failure doesn't spam the store on every 15-minute
/// timer fire. All errors here are best-effort and logged — they MUST NOT
/// short-circuit the sync result.
async fn record_sync_outcome(outcome: &Result<bool>, verbose: bool) -> Result<()> {
    let mut state = load_sync_state();

    if outcome.is_ok() {
        if state.consecutive_fails > 0 || state.last_alert_at_unix.is_some() {
            if verbose && state.consecutive_fails > 0 {
                eprintln!(
                    "[sync] recovery: clearing consecutive_fails={}",
                    state.consecutive_fails
                );
            }
            save_sync_state(&SyncState::default())?;
        }
        return Ok(());
    }

    state.consecutive_fails = state.consecutive_fails.saturating_add(1);
    let now_unix = now_unix_secs();
    let cooldown_ok = state
        .last_alert_at_unix
        .map_or(true, |last| now_unix.saturating_sub(last) >= SYNC_ALERT_COOLDOWN_SECS);

    if verbose {
        eprintln!(
            "[sync] failure #{} (cooldown_ok={cooldown_ok}, threshold={})",
            state.consecutive_fails, SYNC_FAIL_ALERT_THRESHOLD
        );
    }

    if state.consecutive_fails >= SYNC_FAIL_ALERT_THRESHOLD && cooldown_ok {
        let error_summary = outcome
            .as_ref()
            .err()
            .map(|e| e.to_string())
            .unwrap_or_else(|| "(error message not captured)".to_string());
        let host = hostname_short();
        match open_store().await {
            Ok(store) => {
                let mem = MemoryRecord {
                    key: format!("alert-sync-failing-{host}-{now_unix}"),
                    kind: "alert".to_string(),
                    content: format!(
                        "agent-bridge memory sync has failed {} consecutive runs on host `{host}`.\n\n\
                         Likely cause: branch divergence, transient network, or stale rebase state. \
                         Manual recovery recipe in `lesson_sync_fallback_branch_divergence_gap_2026_05_19`.\n\n\
                         Last error: {}",
                        state.consecutive_fails, error_summary
                    ),
                    tags: vec![
                        "sync".to_string(),
                        "alert".to_string(),
                        "severity:high".to_string(),
                    ],
                    related_keys: vec![
                        "lesson_sync_fallback_branch_divergence_gap_2026_05_19".to_string(),
                    ],
                    scope: None,
                    created_at: now_unix as i64,
                    updated_at: now_unix as i64,
                    last_accessed_at: now_unix as i64,
                    access_count: 0,
                    importance: 0.8,
                    status: "active".to_string(),
                    trigger_pattern: None,
                    superseded_by: None,
                };
                match store.memory_save(&mem).await {
                    Ok(_) => {
                        state.last_alert_at_unix = Some(now_unix);
                        eprintln!(
                            "[sync] WARNING: {} consecutive sync failures — emitted kind=alert memory `{}`",
                            state.consecutive_fails, mem.key
                        );
                    }
                    Err(e) => {
                        eprintln!("[sync] failed to emit alert memory: {e}");
                    }
                }
            }
            Err(e) => {
                eprintln!("[sync] failed to open store for alert emit: {e}");
            }
        }
    }

    save_sync_state(&state)?;
    Ok(())
}

// ─── helpers ────────────────────────────────────────────────────────────

async fn open_store() -> Result<SqliteStore> {
    let db_path = std::env::var("AGENT_BRIDGE_DB")
        .ok()
        .map(PathBuf::from)
        .unwrap_or_else(default_db_path);
    let mut store = SqliteStore::open(&db_path)
        .await
        .with_context(|| format!("open {}", db_path.display()))?;
    // Track MS — stamp this machine's identity so version-vector writes and the
    // VersionVectorMerge import policy attribute edits to the right node.
    store.set_node_id(node_id_from_name(&hostname_short()));
    Ok(store)
}

fn ensure_command_on_path(cmd: &str, hint: &str) -> Result<()> {
    let path = std::env::var_os("PATH").ok_or_else(|| anyhow!("PATH unset"))?;
    let found = std::env::split_paths(&path).any(|p| p.join(cmd).is_file());
    if !found {
        bail!("`{cmd}` not on PATH. {hint}");
    }
    Ok(())
}

fn forge_authenticated(provider: Provider) -> bool {
    Command::new(provider.cli())
        .args(["auth", "status"])
        .stdout(Stdio::null())
        .stderr(Stdio::null())
        .status()
        .map(|s| s.success())
        .unwrap_or(false)
}

fn forge_username(provider: Provider) -> Result<String> {
    let cli = provider.cli();
    let jq = provider.user_jq();
    let out = Command::new(cli)
        .args(["api", "user", "--jq", jq])
        .output()
        .with_context(|| format!("invoke {cli} api user"))?;
    if !out.status.success() {
        bail!(
            "{cli} api user failed: {}",
            String::from_utf8_lossy(&out.stderr).trim()
        );
    }
    let user = String::from_utf8_lossy(&out.stdout).trim().to_string();
    if user.is_empty() {
        bail!("{cli} api user returned an empty login");
    }
    Ok(user)
}

fn forge_repo_exists(provider: Provider, full: &str) -> bool {
    Command::new(provider.cli())
        .args(["repo", "view", full])
        .stdout(Stdio::null())
        .stderr(Stdio::null())
        .status()
        .map(|s| s.success())
        .unwrap_or(false)
}

fn run_forge(provider: Provider, args: &[&str]) -> Result<()> {
    let cli = provider.cli();
    let status = Command::new(cli)
        .args(args)
        .status()
        .with_context(|| format!("invoke {cli}"))?;
    if !status.success() {
        bail!("{cli} {} failed (exit {status})", args.join(" "));
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

/// `git rev-list --count <range>` parsed as u64. `range` is any git revision
/// range, e.g. `origin/main..HEAD`. Errors when the ref doesn't exist (caller
/// distinguishes "missing ref" via Err vs in-sync via Ok(0)).
fn git_rev_list_count(repo: &Path, range: &str) -> Result<u64> {
    let out = git_capture(repo, &["rev-list", "--count", range])?;
    out.trim()
        .parse::<u64>()
        .with_context(|| format!("parse rev-list count: {}", out.trim()))
}

/// Outcome of a `git push origin` round where `origin` is a multi-push
/// remote (GitLab primary fetch URL + GitHub mirror push URL).
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
enum PushVerdict {
    /// Every push leg succeeded.
    AllOk,
    /// The combined push exited non-zero, but the *primary* (GitLab, the
    /// `origin` fetch URL) already has HEAD — only a mirror leg failed.
    /// Sync truth source is in sync; do NOT count this as a sync failure.
    MirrorOnlyFailure,
    /// The combined push failed AND the primary is still behind HEAD (or
    /// couldn't be verified) — a genuine sync failure.
    RealFailure,
}

/// Pure classification: a multi-push exits non-zero if *any* leg fails,
/// but GitLab (the `origin` fetch URL) is the truth source. A dead GitHub
/// mirror leg must not inflate the consecutive-fail alert counter (see
/// lesson_sync_alert_inflated_by_dead_github_mirror_leg_20260524). After a
/// push error we re-check how far the primary is behind HEAD: 0 ⇒ the
/// primary got our commit (mirror-only failure), >0 ⇒ real failure.
fn classify_push(push_ok: bool, primary_behind_after_fail: u64) -> PushVerdict {
    if push_ok {
        PushVerdict::AllOk
    } else if primary_behind_after_fail == 0 {
        PushVerdict::MirrorOnlyFailure
    } else {
        PushVerdict::RealFailure
    }
}

/// Push to `origin` (multi-push: GitLab primary + GitHub mirror) treating
/// the primary as the source of truth. A mirror-only failure logs a
/// warning and returns `Ok` so the consecutive-fail alert isn't inflated
/// by a dead mirror leg; a primary failure (or unverifiable primary)
/// returns `Err` so a genuine outage still trips the alert.
fn push_origin_primary_aware(
    repo: &Path,
    branch: &str,
    refspec: &str,
    verbose: bool,
) -> Result<()> {
    let push_ok = run_git(repo, &["push", "origin", refspec]).is_ok();
    if push_ok {
        return Ok(());
    }
    // Push reported failure. Re-fetch the primary (origin fetch URL =
    // GitLab) and measure whether it already carries HEAD. `git fetch
    // origin` updates `origin/<branch>` via the default refspec; if that
    // fetch itself fails the primary is unverifiable and we fall through
    // to RealFailure (conservative — a true outage must still alert).
    let primary_behind = match run_git(repo, &["fetch", "origin"]) {
        Ok(()) => git_rev_list_count(repo, &format!("origin/{branch}..HEAD")).unwrap_or(u64::MAX),
        Err(_) => u64::MAX,
    };
    match classify_push(false, primary_behind) {
        PushVerdict::MirrorOnlyFailure => {
            eprintln!(
                "[sync] push: primary (origin/GitLab) is in sync; a mirror leg \
                 (GitHub) failed — not counting as a sync failure. Reconcile the \
                 mirror separately (see lesson_sync_alert_inflated_by_dead_github_mirror_leg)."
            );
            Ok(())
        }
        PushVerdict::RealFailure => bail!(
            "git push origin {refspec} failed and primary still {} behind HEAD",
            if primary_behind == u64::MAX {
                "unverifiable /".to_string()
            } else {
                primary_behind.to_string()
            }
        ),
        // push_ok was false above, so AllOk is unreachable here.
        PushVerdict::AllOk => {
            let _ = verbose;
            Ok(())
        }
    }
}

/// Best-effort `git pull --rebase --autostash`. Last-resort fallback (when
/// rebase fails) checks out the remote `memory.jsonl` so subsequent
/// import/export reconciles via the local SQLite store.
///
/// Always cleans up leftover rebase state (`.git/rebase-merge` /
/// `rebase-apply`) before and after the pull. Without this, a single
/// conflicting pull-rebase would strand the repo in interactive-rebase
/// mode forever, with every subsequent sync committing on detached HEAD
/// and silently failing the push (see commit msg for the 1.5-day outage).
fn git_pull_rebase(repo: &Path, verbose: bool) {
    abort_leftover_rebase(repo, verbose);
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
            // pull --rebase may have stopped mid-rebase; clean before fallback.
            abort_leftover_rebase(repo, verbose);
            let _ = Command::new("git")
                .arg("-C")
                .arg(repo)
                .args(["fetch", "origin"])
                .status();
            // Try common default branches in order; first usable ref wins.
            //
            // When local is forked from origin (ahead>0 AND behind>0), a file-
            // only fallback would commit + push and get REJECTED forever — the
            // 2026-05-18→19 31h silent-loop failure mode. In that case we
            // `reset --hard` to origin, which is safe because every prior sync
            // commit's jsonl content is derivable from the current state.db
            // (SQLite is the source of truth; jsonl/git are just transport).
            // The subsequent import + export step re-emits a single union
            // commit on top of origin. See memory key
            // `lesson_sync_fallback_branch_divergence_gap_2026_05_19`.
            for branch in ["origin/HEAD", "origin/main", "origin/master"] {
                let Ok(ahead) = git_rev_list_count(repo, &format!("{branch}..HEAD")) else {
                    continue; // ref doesn't exist — try next
                };
                let Ok(behind) = git_rev_list_count(repo, &format!("HEAD..{branch}")) else {
                    continue;
                };
                let success = if ahead > 0 && behind > 0 {
                    if verbose {
                        eprintln!(
                            "[sync] branch divergent vs {branch} (ahead={ahead} behind={behind}); \
                             reset --hard (SQLite-as-truth)"
                        );
                    }
                    Command::new("git")
                        .arg("-C")
                        .arg(repo)
                        .args(["reset", "--hard", branch])
                        .status()
                } else {
                    // Pure file conflict, not divergent. Legacy fallback: take
                    // origin's memory.jsonl and let import/export reconcile.
                    Command::new("git")
                        .arg("-C")
                        .arg(repo)
                        .args(["checkout", branch, "--", MEMORY_FILE])
                        .status()
                };
                if matches!(success, Ok(s) if s.success()) {
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
    // Belt-and-braces: even a "successful" pull --rebase --autostash can leave
    // rebase state if the autostash pop conflicts.
    abort_leftover_rebase(repo, verbose);
}

/// If `.git/rebase-merge` or `.git/rebase-apply` exists, run `git rebase
/// --abort` to clean it. No-op when neither directory is present.
fn abort_leftover_rebase(repo: &Path, verbose: bool) {
    let merge = repo.join(".git/rebase-merge").exists();
    let apply = repo.join(".git/rebase-apply").exists();
    if !merge && !apply {
        return;
    }
    if verbose {
        eprintln!("[sync] leftover rebase state detected — running `git rebase --abort`");
    }
    let _ = Command::new("git")
        .arg("-C")
        .arg(repo)
        .args(["rebase", "--abort"])
        .status();
}

/// Returns the current branch name (e.g. `"main"`). Errors when HEAD is
/// detached — sync refuses to operate from detached HEAD because the
/// subsequent push would have nothing to name on the remote.
fn git_current_branch(repo: &Path) -> Result<String> {
    let s = git_capture(repo, &["symbolic-ref", "--short", "HEAD"])
        .context("HEAD is detached (no current branch)")?;
    let name = s.trim().to_string();
    if name.is_empty() {
        bail!("HEAD is detached (no current branch)");
    }
    Ok(name)
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

pub(crate) fn hostname_short() -> String {
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

    #[test]
    fn provider_explicit_passes_through() {
        // Explicit choices are returned unchanged regardless of PATH.
        assert!(matches!(resolve_provider(Provider::Github), Provider::Github));
        assert!(matches!(resolve_provider(Provider::Gitlab), Provider::Gitlab));
    }

    #[test]
    fn provider_metadata_consistent() {
        assert_eq!(Provider::Github.cli(), "gh");
        assert_eq!(Provider::Gitlab.cli(), "glab");
        assert_eq!(Provider::Github.user_jq(), ".login");
        assert_eq!(Provider::Gitlab.user_jq(), ".username");
        assert_eq!(Provider::Github.forge(), "GitHub");
        assert_eq!(Provider::Gitlab.forge(), "GitLab");
    }

    #[test]
    fn classify_push_all_legs_ok() {
        // push_ok=true short-circuits; behind value is irrelevant.
        assert_eq!(classify_push(true, 0), PushVerdict::AllOk);
        assert_eq!(classify_push(true, 99), PushVerdict::AllOk);
    }

    #[test]
    fn classify_push_mirror_only_failure_when_primary_in_sync() {
        // Combined push failed but primary (GitLab) already has HEAD
        // (0 behind) — the dead-GitHub-mirror false-alarm case.
        assert_eq!(classify_push(false, 0), PushVerdict::MirrorOnlyFailure);
    }

    #[test]
    fn classify_push_real_failure_when_primary_behind() {
        // Primary still behind → genuine sync failure, must still alert.
        assert_eq!(classify_push(false, 1), PushVerdict::RealFailure);
        // Unverifiable primary (fetch failed → u64::MAX sentinel) is also
        // treated conservatively as a real failure.
        assert_eq!(classify_push(false, u64::MAX), PushVerdict::RealFailure);
    }
}
