//! Orphan reaper — kills agent process groups whose owning bridge process is
//! provably gone.
//!
//! The leak this closes (kill-routing arc residual, 2026-07-01): interactive
//! PTY children are setsid'd session leaders that survive their owner's
//! death. `PtySession::Drop` covers a graceful owner shutdown, but a
//! SIGKILLed owner (OOM kill, crash, `kill -9`) runs no destructors — the
//! child TUI (gemini's Ink famously catches SIGHUP *and* SIGTERM) keeps
//! running forever, and `agent_session_reconcile` could only mark the DB row
//! dead, never signal the process, because the pid lived exclusively in the
//! dead owner's memory.
//!
//! v41 stores the identity at spawn: child pid + pgid + `/proc` starttime,
//! plus the OWNER's pid + starttime. Safety ladder (each rung reviewed
//! adversarially, 2026-07-03):
//!
//! - **starttime tokens** — a recycled pid has a different starttime, so a
//!   matching token proves the process is the one we spawned;
//! - **boot fence** — starttime is boot-relative, so rows whose session
//!   started before the current boot are NEVER signalled (their tokens
//!   could collide with innocent same-boot processes); everything from a
//!   previous boot is dead by definition and only needs finalising;
//! - **owner precedence** — a session whose owner still lives (same pid,
//!   same starttime, not a zombie) is never touched;
//! - **conservative on missing evidence** — a row without a child token OR
//!   with an owner pid but no owner token is `Legacy`: report-only;
//! - **pgid sanity** — the group is only signalled when `pgid == pid`
//!   (the setsid invariant the stamp records), `pid > 1`, and it fits
//!   `pid_t`; anything else can address the daemon's own group (pgid 0),
//!   every process on the host (pgid 1), or an unrelated group (i64→i32
//!   truncation) — refused, loudly;
//! - **zombie awareness** — a zombie keeps its `/proc` starttime until
//!   waited on: a zombie OWNER is dead (runs no exit-watcher), a zombie
//!   LEADER is dead but still *reserves the pgid*, which makes a group
//!   signal provably safe — that's the one case where we kill a group whose
//!   leader already exited (its SIGTERM-trapping descendants survive it);
//! - **finalise only what's proven** — a row is only marked ended when the
//!   kill verifiably landed (or nothing matching the token exists); a
//!   surviving group (EPERM, D-state) stays running in the DB and is
//!   retried next tick instead of becoming an invisible permanent leak.
//!
//! Gated OFF by default (`AGENT_BRIDGE_ORPHAN_REAPER=1` to enable). The
//! daemon tick fires immediately at startup — recovering right after a
//! daemon restart IS the point — then hourly.

use ab_agent::pty_session::proc_start_ticks;
use ab_store::{SessionFilter, StateStore, StoredSession};
use std::future::Future;
use std::sync::Arc;
use std::time::{Duration, SystemTime};

/// Live `/proc` observation of one pid: distinguishes "no such process",
/// "dead but unwaited" (zombie — keeps its original starttime!), and alive.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum ProcSight {
    Missing,
    Zombie(i64),
    Alive(i64),
}

/// Snapshot a pid's current identity. `Missing` for pid ≤ 0.
pub fn probe(pid: i64) -> ProcSight {
    if pid <= 0 {
        return ProcSight::Missing;
    }
    let Some(ticks) = proc_start_ticks(pid as u32) else {
        return ProcSight::Missing;
    };
    if proc_state(pid as u32) == Some('Z') {
        ProcSight::Zombie(ticks)
    } else {
        ProcSight::Alive(ticks)
    }
}

/// Process state char from `/proc/<pid>/stat` (field 3, right after the
/// parenthesised comm). `Z` = zombie: already dead, just not yet waited on.
#[cfg(target_os = "linux")]
fn proc_state(pid: u32) -> Option<char> {
    let stat = std::fs::read_to_string(format!("/proc/{pid}/stat")).ok()?;
    let after = &stat[stat.rfind(')')? + 1..];
    after.split_ascii_whitespace().next()?.chars().next()
}

#[cfg(not(target_os = "linux"))]
fn proc_state(_pid: u32) -> Option<char> {
    None
}

/// How a stale running session row relates to the processes it names.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum OrphanClass {
    /// The owning bridge process still exists (same pid AND same starttime,
    /// not a zombie): the session is theirs — never touch it.
    OwnerAlive,
    /// Owner is gone/zombie/recycled while the child group leader is alive
    /// under its original identity: a true orphan — reapable.
    OrphanAlive,
    /// Owner gone and the leader is a matching-ticks ZOMBIE: dead itself,
    /// but it still reserves the pgid, so a group signal is provably safe —
    /// this reaps SIGTERM-trapping descendants that outlived their leader.
    OrphanZombieLeader,
    /// The child leader is gone or its pid was recycled: nothing provably
    /// ours remains addressable — finalise the row without signalling.
    ChildGoneOrReused,
    /// Pre-v41 row, or one missing any token (child OR owner): no proven
    /// identity, so the reaper must not signal anything. The dry-run-gated
    /// `agent_session_reconcile` tool owns these, report-only.
    Legacy,
}

/// Pure classification over stored identity + live `/proc` observations —
/// separated from I/O so every branch is unit-testable.
pub fn classify(
    stored_child_pid: Option<i64>,
    stored_child_ticks: Option<i64>,
    stored_owner_pid: Option<i64>,
    stored_owner_ticks: Option<i64>,
    child: ProcSight,
    owner: ProcSight,
) -> OrphanClass {
    let (Some(_), Some(child_ticks)) = (stored_child_pid, stored_child_ticks) else {
        // No pid, or a pid without its anti-reuse token: killing would be a
        // guess. Guesses and SIGKILL don't mix.
        return OrphanClass::Legacy;
    };
    // Owner evidence must be COMPLETE: an owner pid without its token could
    // belong to a live-but-unprovable owner — treating it as "gone" would
    // kill an active session out from under its living owner (review
    // finding, 2026-07-03). Same conservatism as the child rule.
    let (Some(_), Some(owner_ticks)) = (stored_owner_pid, stored_owner_ticks) else {
        return OrphanClass::Legacy;
    };
    // A zombie owner is dead: it runs no exit-watcher and holds no PTY.
    if owner == ProcSight::Alive(owner_ticks) {
        return OrphanClass::OwnerAlive;
    }
    match child {
        ProcSight::Alive(t) if t == child_ticks => OrphanClass::OrphanAlive,
        ProcSight::Zombie(t) if t == child_ticks => OrphanClass::OrphanZombieLeader,
        _ => OrphanClass::ChildGoneOrReused,
    }
}

/// starttime tokens are boot-relative: a row whose session STARTED before
/// the current boot cannot address any live process (its pid space died with
/// the old boot), and worse, its token could numerically collide with an
/// innocent same-pid process of THIS boot. Fence with a safety margin.
pub fn predates_boot(started_at: i64, boot_wall_secs: i64) -> bool {
    started_at < boot_wall_secs + 60
}

/// Wall-clock time of the current boot (now − uptime).
fn boot_wall_secs(now: i64) -> Option<i64> {
    let up = std::fs::read_to_string("/proc/uptime").ok()?;
    let secs: f64 = up.split_ascii_whitespace().next()?.parse().ok()?;
    Some(now - secs as i64)
}

/// The only pgid shape the reaper will ever signal: the setsid invariant
/// recorded at spawn (`pgid == pid`), a real group (`> 1` — 0 would address
/// OUR OWN group, 1 would address everything), and no i64→pid_t truncation.
fn signalable_pgid(pid: i64, pgid: Option<i64>) -> Option<i64> {
    let pgid = pgid?;
    (pgid == pid && pid > 1 && pid <= i32::MAX as i64).then_some(pgid)
}

/// Signal an entire process group, tolerating "already gone".
#[cfg(unix)]
fn signal_group(pgid: i64, sig: libc::c_int) -> std::io::Result<()> {
    debug_assert!(pgid > 1, "signalable_pgid must gate every caller");
    let rc = unsafe { libc::kill(-(pgid as libc::pid_t), sig) };
    if rc == 0 {
        return Ok(());
    }
    let err = std::io::Error::last_os_error();
    if err.raw_os_error() == Some(libc::ESRCH) {
        Ok(()) // group already exited — success for a reaper
    } else {
        Err(err)
    }
}

#[cfg(not(unix))]
fn signal_group(_pgid: i64, _sig: i32) -> std::io::Result<()> {
    Ok(())
}

/// "No live process holds the original identity" — a zombie counts as gone
/// (SIGKILL is uncatchable; delivered is dead), and so does a recycled pid.
fn leader_gone(pid: i64, expected_ticks: i64) -> bool {
    !matches!(probe(pid), ProcSight::Alive(t) if t == expected_ticks)
}

/// SIGTERM the group, wait `grace`, then SIGKILL while the identity still
/// proves the pgid is ours (alive OR zombie leader with matching ticks both
/// do — a zombie still reserves the group id). Returns whether no live
/// process with the original identity remains afterwards.
pub async fn reap_group(
    pid: i64,
    pgid: i64,
    expected_ticks: i64,
    grace: std::time::Duration,
) -> bool {
    #[cfg(unix)]
    const TERM: libc::c_int = libc::SIGTERM;
    #[cfg(unix)]
    const KILL: libc::c_int = libc::SIGKILL;
    #[cfg(not(unix))]
    const TERM: i32 = 0;
    #[cfg(not(unix))]
    const KILL: i32 = 0;

    if let Err(e) = signal_group(pgid, TERM) {
        tracing::warn!(pgid, error = %e, "orphan-reaper: SIGTERM failed");
    }
    tokio::time::sleep(grace).await;
    // Escalate while the token still proves the group: a leader that exited
    // during the grace but sits as a matching-ticks zombie still reserves
    // the pgid, and its TERM-trapping descendants are exactly who SIGKILL
    // is for. A MISMATCHED token means the pid was recycled — never signal.
    match probe(pid) {
        ProcSight::Alive(t) | ProcSight::Zombie(t) if t == expected_ticks => {
            if let Err(e) = signal_group(pgid, KILL) {
                tracing::warn!(pgid, error = %e, "orphan-reaper: SIGKILL failed");
                return false;
            }
        }
        _ => {}
    }
    // Small settle: SIGKILL delivery is asynchronous; without it a genuinely
    // killed leader can still read as alive and poison the verdict.
    tokio::time::sleep(std::time::Duration::from_millis(200)).await;
    leader_gone(pid, expected_ticks)
}

/// Outcome of one reaper pass.
#[derive(Debug, Default)]
pub struct ReaperReport {
    pub scanned: usize,
    pub skipped_recent: usize,
    pub owner_alive: usize,
    pub legacy_untracked: usize,
    pub reaped: usize,
    pub finalised_gone: usize,
    /// Kill did not verifiably land (EPERM, D-state, …): row left RUNNING so
    /// the next tick retries — never silently hidden.
    pub still_alive: usize,
    pub errors: usize,
}

fn append_reason(stderr: Option<&str>, reason: &str) -> String {
    match stderr {
        Some(prev) if !prev.is_empty() => format!("{prev}\n{reason}"),
        _ => reason.to_string(),
    }
}

/// One reaper pass over stale running session rows: classify each against
/// live `/proc`, kill proven orphan groups, finalise rows whose process is
/// proven gone. Never touches rows owned by a living process, never signals
/// anything without a starttime match, and never finalises a row whose
/// process may still be alive.
pub async fn run_reaper_pass(
    store: &Arc<dyn StateStore>,
    stale_after_secs: i64,
    grace: std::time::Duration,
    now: i64,
) -> ab_core::Result<ReaperReport> {
    let filter = SessionFilter {
        runtime_id: None,
        cwd_prefix: None,
        exited_only: Some(false),
        exit_code: None,
    };
    const SCAN_LIMIT: u32 = 1000;
    let rows = store.list_sessions(&filter, SCAN_LIMIT).await?;
    if rows.len() as u32 >= SCAN_LIMIT {
        // list_sessions is newest-first: at saturation the OLDEST running
        // rows — the likeliest true orphans — are the ones falling off.
        tracing::warn!(
            limit = SCAN_LIMIT,
            "orphan-reaper: scan saturated; oldest running rows not examined this pass"
        );
    }
    let boot_wall = boot_wall_secs(now);
    let mut report = ReaperReport {
        scanned: rows.len(),
        ..ReaperReport::default()
    };
    for session in rows {
        if now.saturating_sub(session.started_at) < stale_after_secs {
            report.skipped_recent += 1;
            continue;
        }
        // Boot fence: rows from a previous boot are dead by definition and
        // their tokens are meaningless in this boot's pid space — finalise
        // without signalling, no matter what the tokens appear to match.
        if session.proc_pid.is_some() {
            match boot_wall {
                Some(bw) if predates_boot(session.started_at, bw) => {
                    if finalise(
                        store,
                        &session,
                        now,
                        -15,
                        "orphan-reaper: session predates the current boot; \
                         process long gone, finalised without signalling",
                    )
                    .await
                    {
                        report.finalised_gone += 1;
                    } else {
                        report.errors += 1;
                    }
                    continue;
                }
                Some(_) => {}
                None => {
                    // No /proc/uptime: cannot prove same-boot — do not
                    // signal anything this pass.
                    report.legacy_untracked += 1;
                    continue;
                }
            }
        }
        let class = classify(
            session.proc_pid,
            session.proc_start_ticks,
            session.owner_pid,
            session.owner_start_ticks,
            session.proc_pid.map_or(ProcSight::Missing, probe),
            session.owner_pid.map_or(ProcSight::Missing, probe),
        );
        match class {
            OrphanClass::OwnerAlive => report.owner_alive += 1,
            OrphanClass::Legacy => report.legacy_untracked += 1,
            OrphanClass::OrphanAlive | OrphanClass::OrphanZombieLeader => {
                let pid = session.proc_pid.unwrap_or(0);
                let ticks = session.proc_start_ticks.unwrap_or(0);
                let Some(pgid) = signalable_pgid(pid, session.proc_pgid) else {
                    tracing::warn!(
                        session = %session.id,
                        pid,
                        pgid = ?session.proc_pgid,
                        "orphan-reaper: refusing unsafe pgid shape (must equal pid, be >1, fit pid_t)"
                    );
                    report.errors += 1;
                    continue;
                };
                tracing::info!(
                    session = %session.id,
                    runtime = %session.runtime_id,
                    pid,
                    pgid,
                    class = ?class,
                    "orphan-reaper: reaping abandoned process group"
                );
                let gone = reap_group(pid, pgid, ticks, grace).await;
                if !gone {
                    // EPERM / D-state / delivery race: leave the row RUNNING
                    // so the next tick retries — finalising now would hide a
                    // live orphan forever.
                    tracing::warn!(
                        session = %session.id,
                        pid,
                        "orphan-reaper: group not verifiably gone; leaving row for retry"
                    );
                    report.still_alive += 1;
                    continue;
                }
                if finalise(
                    store,
                    &session,
                    now,
                    -9,
                    &format!(
                        "orphan-reaper: owner process gone; process group {pgid} \
                         SIGTERM→SIGKILL, leader verified gone"
                    ),
                )
                .await
                {
                    report.reaped += 1;
                } else {
                    report.errors += 1;
                }
            }
            OrphanClass::ChildGoneOrReused => {
                if finalise(
                    store,
                    &session,
                    now,
                    -15,
                    "orphan-reaper: owner and child both gone (or pid recycled); \
                     finalised without signalling",
                )
                .await
                {
                    report.finalised_gone += 1;
                } else {
                    report.errors += 1;
                }
            }
        }
    }
    Ok(report)
}

async fn finalise(
    store: &Arc<dyn StateStore>,
    session: &StoredSession,
    now: i64,
    exit_code: i32,
    reason: &str,
) -> bool {
    let stderr = append_reason(session.stderr.as_deref(), reason);
    match store
        .finalise_session(
            &session.id,
            now,
            Some(exit_code),
            session.stdout.clone(),
            Some(stderr),
        )
        .await
    {
        Ok(()) => true,
        Err(e) => {
            tracing::warn!(session = %session.id, error = %e, "orphan-reaper: finalise failed");
            false
        }
    }
}

/// Gate for the daemon reaper tick. Default OFF — enabling is a
/// per-deployment machine.env decision.
pub fn reaper_enabled() -> bool {
    reaper_enabled_from(std::env::var("AGENT_BRIDGE_ORPHAN_REAPER").ok().as_deref())
}

fn reaper_enabled_from(v: Option<&str>) -> bool {
    v.map(|v| v == "1" || v.eq_ignore_ascii_case("true"))
        .unwrap_or(false)
}

/// Tick cadence (default hourly). The FIRST pass runs immediately at daemon
/// startup — recovering right after a daemon crash/restart is the scenario
/// this exists for.
pub fn reaper_tick_secs() -> u64 {
    reaper_tick_secs_from(std::env::var("AB_ORPHAN_REAPER_TICK_SECS").ok().as_deref())
}

fn reaper_tick_secs_from(v: Option<&str>) -> u64 {
    v.and_then(|s| s.parse().ok())
        .unwrap_or(3_600)
        .clamp(60, 86_400)
}

/// Only rows older than this are considered (default 600s): a freshly
/// spawned session whose owner briefly pauses must not look abandoned.
pub fn reaper_stale_secs() -> i64 {
    std::env::var("AB_ORPHAN_REAPER_STALE_SECS")
        .ok()
        .and_then(|s| s.parse().ok())
        .unwrap_or(600)
        .clamp(60, 86_400)
}

pub fn spawn_reaper_supervisor(
    store: Arc<dyn StateStore>,
    tick_secs: u64,
) -> tokio::task::JoinHandle<()> {
    tokio::spawn(async move {
        run_reaper_loop(Duration::from_secs(tick_secs), || {
            run_supervisor_reaper_pass(&store)
        })
        .await;
    })
}

async fn run_reaper_loop<F, Fut>(tick_period: Duration, mut run_pass: F)
where
    F: FnMut() -> Fut,
    Fut: Future<Output = ()>,
{
    let mut interval = tokio::time::interval(tick_period);
    interval.set_missed_tick_behavior(tokio::time::MissedTickBehavior::Delay);
    loop {
        interval.tick().await;
        run_pass().await;
    }
}

async fn run_supervisor_reaper_pass(store: &Arc<dyn StateStore>) {
    let now = SystemTime::now()
        .duration_since(SystemTime::UNIX_EPOCH)
        .map(|duration| duration.as_secs() as i64)
        .unwrap_or(0);
    match run_reaper_pass(store, reaper_stale_secs(), Duration::from_secs(3), now).await {
        Ok(report)
            if report.reaped > 0
                || report.finalised_gone > 0
                || report.still_alive > 0
                || report.errors > 0 =>
        {
            tracing::info!(
                scanned = report.scanned,
                reaped = report.reaped,
                finalised_gone = report.finalised_gone,
                still_alive = report.still_alive,
                owner_alive = report.owner_alive,
                legacy = report.legacy_untracked,
                errors = report.errors,
                "orphan-reaper: pass ran"
            );
        }
        Ok(report) => {
            tracing::debug!(
                scanned = report.scanned,
                owner_alive = report.owner_alive,
                legacy = report.legacy_untracked,
                "orphan-reaper: nothing to reap"
            );
        }
        Err(error) => {
            tracing::warn!(error = %error, "orphan-reaper: pass error");
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::sync::atomic::{AtomicUsize, Ordering};

    #[tokio::test]
    async fn supervisor_runs_first_pass_immediately_then_waits() {
        let passes = Arc::new(AtomicUsize::new(0));
        let observed = Arc::clone(&passes);
        let handle = tokio::spawn(async move {
            run_reaper_loop(Duration::from_secs(60), || {
                let observed = Arc::clone(&observed);
                async move {
                    observed.fetch_add(1, Ordering::SeqCst);
                }
            })
            .await;
        });

        tokio::time::timeout(Duration::from_millis(100), async {
            while passes.load(Ordering::SeqCst) == 0 {
                tokio::task::yield_now().await;
            }
        })
        .await
        .expect("first reaper pass should run immediately");
        tokio::time::sleep(Duration::from_millis(20)).await;
        assert_eq!(passes.load(Ordering::SeqCst), 1);
        handle.abort();
    }

    #[test]
    fn classify_covers_every_branch() {
        use ProcSight::*;
        let d = OrphanClass::Legacy;
        // Legacy: no child pid / no child token.
        assert_eq!(classify(None, None, None, None, Missing, Missing), d);
        assert_eq!(
            classify(Some(10), None, Some(1), Some(5), Alive(7), Alive(5)),
            d,
            "pid without starttime token must never be killable"
        );
        // Legacy: owner evidence incomplete (pid without token, or absent).
        assert_eq!(
            classify(Some(10), Some(7), Some(1), None, Alive(7), Alive(5)),
            d,
            "owner pid without token could be a live unprovable owner"
        );
        assert_eq!(
            classify(Some(10), Some(7), None, None, Alive(7), Missing),
            d,
            "absent owner identity is not proof of death"
        );
        // Owner alive (ticks match, not zombie) shields the child.
        assert_eq!(
            classify(Some(10), Some(7), Some(1), Some(5), Alive(7), Alive(5)),
            OrphanClass::OwnerAlive
        );
        assert_eq!(
            classify(Some(10), Some(7), Some(1), Some(5), Missing, Alive(5)),
            OrphanClass::OwnerAlive,
            "dead child + live owner = owner's exit-watcher will finalise"
        );
        // Zombie owner is DEAD (runs no exit-watcher).
        assert_eq!(
            classify(Some(10), Some(7), Some(1), Some(5), Alive(7), Zombie(5)),
            OrphanClass::OrphanAlive,
            "zombie owner must not shield its orphans"
        );
        // Owner gone / recycled → child decides.
        assert_eq!(
            classify(Some(10), Some(7), Some(1), Some(5), Alive(7), Missing),
            OrphanClass::OrphanAlive
        );
        assert_eq!(
            classify(Some(10), Some(7), Some(1), Some(5), Alive(7), Alive(6)),
            OrphanClass::OrphanAlive,
            "recycled owner pid counts as gone"
        );
        // Zombie leader with matching ticks: group still addressable safely.
        assert_eq!(
            classify(Some(10), Some(7), Some(1), Some(5), Zombie(7), Missing),
            OrphanClass::OrphanZombieLeader
        );
        // Child gone or recycled → finalise only.
        assert_eq!(
            classify(Some(10), Some(7), Some(1), Some(5), Missing, Missing),
            OrphanClass::ChildGoneOrReused
        );
        assert_eq!(
            classify(Some(10), Some(7), Some(1), Some(5), Alive(8), Missing),
            OrphanClass::ChildGoneOrReused,
            "recycled child pid must not be signalled"
        );
        assert_eq!(
            classify(Some(10), Some(7), Some(1), Some(5), Zombie(8), Missing),
            OrphanClass::ChildGoneOrReused,
            "zombie with WRONG ticks is someone else's corpse"
        );
    }

    #[test]
    fn pgid_safety_and_boot_fence() {
        // The only signalable shape: pgid == pid, > 1, fits pid_t.
        assert_eq!(signalable_pgid(1234, Some(1234)), Some(1234));
        assert_eq!(signalable_pgid(1234, None), None);
        assert_eq!(signalable_pgid(1234, Some(0)), None, "kill(0) = own group");
        assert_eq!(signalable_pgid(1, Some(1)), None, "kill(-1) = everything");
        assert_eq!(signalable_pgid(0, Some(0)), None);
        assert_eq!(
            signalable_pgid(1234, Some(5678)),
            None,
            "setsid invariant violated → refuse"
        );
        assert_eq!(
            signalable_pgid((i32::MAX as i64) + 10, Some((i32::MAX as i64) + 10)),
            None,
            "i64→pid_t truncation refused"
        );
        // Boot fence: anything at or before boot(+margin) is untouchable.
        assert!(predates_boot(999, 1_000));
        assert!(predates_boot(1_040, 1_000), "inside the 60s margin");
        assert!(!predates_boot(1_100, 1_000));
    }

    #[test]
    fn env_parsing_defaults_and_clamps() {
        assert!(!reaper_enabled_from(None));
        assert!(!reaper_enabled_from(Some("0")));
        assert!(reaper_enabled_from(Some("1")));
        assert!(reaper_enabled_from(Some("TRUE")));
        assert_eq!(reaper_tick_secs_from(None), 3_600);
        assert_eq!(reaper_tick_secs_from(Some("10")), 60);
        assert_eq!(reaper_tick_secs_from(Some("999999")), 86_400);
        assert_eq!(reaper_tick_secs_from(Some("garbage")), 3_600);
    }

    #[cfg(target_os = "linux")]
    fn spawn_setsid_sleeper() -> std::process::Child {
        use std::os::unix::process::CommandExt;
        let mut cmd = std::process::Command::new("sleep");
        cmd.arg("300");
        unsafe {
            cmd.pre_exec(|| {
                if libc::setsid() == -1 {
                    return Err(std::io::Error::last_os_error());
                }
                Ok(())
            });
        }
        cmd.spawn().expect("spawn sleeper")
    }

    #[cfg(target_os = "linux")]
    #[tokio::test]
    async fn reap_group_kills_a_real_setsid_leader() {
        let mut child = spawn_setsid_sleeper();
        let pid = child.id() as i64;
        let ticks = proc_start_ticks(pid as u32).expect("child starttime");

        let gone = reap_group(pid, pid, ticks, std::time::Duration::from_millis(200)).await;
        assert!(gone, "sleeper group must be gone after TERM→KILL");
        assert!(leader_gone(pid, ticks));
        let _ = child.wait();
    }

    #[cfg(target_os = "linux")]
    #[tokio::test]
    async fn reap_group_never_escalates_onto_recycled_identity() {
        // A mismatched token means "the process we knew no longer exists":
        // reap_group must not SIGKILL the group under that id, and must
        // report gone=true (nothing matching the token remains).
        let mut child = spawn_setsid_sleeper();
        let pid = child.id() as i64;
        let real = proc_start_ticks(pid as u32).expect("ticks");
        let wrong = real + 123_456;

        let gone = reap_group(pid, pid, wrong, std::time::Duration::from_millis(50)).await;
        assert!(gone, "mismatched token reads as 'no such identity' → gone");
        let _ = child.kill();
        let _ = child.wait();
    }

    #[cfg(target_os = "linux")]
    #[tokio::test]
    async fn reaper_pass_kills_orphan_spares_owned_and_legacy() {
        // Full matrix e2e on a real store: (a) dead-owner + live setsid child
        // → reaped + finalised; (b) live-owner row → untouched; (c) legacy
        // row (no identity) → untouched; (d) pre-boot row → finalised
        // without signalling. The "dead owner" is our own pid with a WRONG
        // starttime token (identity mismatch == gone).
        let dir = std::env::temp_dir().join(format!(
            "ab-orphan-reaper-e2e-{}-{}",
            std::process::id(),
            std::time::SystemTime::now()
                .duration_since(std::time::UNIX_EPOCH)
                .map(|d| d.subsec_nanos())
                .unwrap_or(0)
        ));
        tokio::fs::create_dir_all(&dir).await.expect("mkdir");
        let store = ab_store::SqliteStore::open(&dir.join("state.db"))
            .await
            .expect("open store");
        let store: Arc<dyn StateStore> = Arc::new(store);

        let now = std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)
            .map(|d| d.as_secs() as i64)
            .unwrap_or(0);
        // The boot fence needs stale rows that are still same-boot: skip on
        // hosts (fresh CI containers) that have not been up long enough.
        let Some(bw) = boot_wall_secs(now) else {
            return;
        };
        if now - bw < 900 {
            eprintln!("skipping: uptime too short for a same-boot stale row");
            return;
        }

        let mut child = spawn_setsid_sleeper();
        let child_pid = child.id() as i64;
        let child_ticks = proc_start_ticks(child_pid as u32).expect("child ticks");
        let own_pid = std::process::id() as i64;
        let own_ticks = proc_start_ticks(own_pid as u32).expect("own ticks");

        let mk = |id: &str, started_at: i64, pp, pt, op, ot| StoredSession {
            id: ab_core::SessionId::from_raw(id.to_string()),
            runtime_id: "gemini".into(),
            cwd: "/tmp".into(),
            started_at,
            ended_at: None,
            exit_code: None,
            stdout: None,
            stderr: None,
            cloud_run_id: None,
            cloud_run_state: None,
            cloud_session_link: None,
            proc_pid: pp,
            proc_pgid: pp,
            proc_start_ticks: pt,
            owner_pid: op,
            owner_start_ticks: ot,
        };
        let stale = now - 700; // > stale_after (600) but well after boot
        store
            .save_session(&mk(
                "reap-orphan",
                stale,
                Some(child_pid),
                Some(child_ticks),
                Some(own_pid),
                Some(own_ticks + 987_654),
            ))
            .await
            .expect("save orphan row");
        store
            .save_session(&mk(
                "reap-owned",
                stale,
                Some(own_pid),
                Some(own_ticks),
                Some(own_pid),
                Some(own_ticks),
            ))
            .await
            .expect("save owned row");
        store
            .save_session(&mk("reap-legacy", stale, None, None, None, None))
            .await
            .expect("save legacy row");
        store
            .save_session(&mk(
                "reap-preboot",
                bw - 3_600, // before this boot
                Some(child_pid),
                Some(child_ticks),
                Some(own_pid),
                Some(own_ticks + 1),
            ))
            .await
            .expect("save preboot row");

        let report = run_reaper_pass(&store, 600, std::time::Duration::from_millis(200), now)
            .await
            .expect("pass");
        assert_eq!(report.reaped, 1, "exactly the orphan is reaped");
        assert_eq!(report.owner_alive, 1, "owned row untouched");
        assert_eq!(report.legacy_untracked, 1, "legacy row untouched");
        assert_eq!(
            report.finalised_gone, 1,
            "pre-boot row finalised without signalling (its pid points at a LIVE process!)"
        );
        assert_eq!(report.still_alive, 0);
        assert_eq!(report.errors, 0);

        let orphan = store
            .load_session(&ab_core::SessionId::from_raw("reap-orphan".to_string()))
            .await
            .expect("load")
            .expect("row");
        assert!(orphan.ended_at.is_some(), "orphan row finalised");
        assert_eq!(orphan.exit_code, Some(-9));
        assert!(orphan
            .stderr
            .as_deref()
            .unwrap_or("")
            .contains("orphan-reaper"));
        let owned = store
            .load_session(&ab_core::SessionId::from_raw("reap-owned".to_string()))
            .await
            .expect("load")
            .expect("row");
        assert!(owned.ended_at.is_none(), "owned row still running");

        // The sleeper must actually be dead; the PRE-BOOT row pointing at
        // the same (now killed) pid must not have been the one to kill it —
        // order-independent here because the fence never signals at all.
        assert!(leader_gone(child_pid, child_ticks));
        let _ = child.wait();

        // Idempotence: a second pass finds nothing reapable.
        let rerun = run_reaper_pass(&store, 600, std::time::Duration::from_millis(50), now)
            .await
            .expect("rerun");
        assert_eq!(rerun.reaped, 0);
        assert_eq!(rerun.errors, 0);

        let _ = tokio::fs::remove_dir_all(&dir).await;
    }
}
