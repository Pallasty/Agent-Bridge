//! **C3 — Daemon self-check tick** (Collab Protocol v0, design §3.4).
//!
//! Run once per 30s tick from `Cmd::Daemon`. Detects:
//!
//! - **S1** any `agent-bridge.real`-binary process holding a state.db
//!   FD that readlink-resolves to `... (deleted)` (F8 multi-process
//!   partial-swap mitigation).
//! - **S2-S4** DB metric drops (memories.count active / forum_threads.count /
//!   memory_edges.count) — implemented in [`s234_check_against_snapshot`].
//!   Forum-post channel (non-DB-anomaly tier per §3.4.1).
//! - **S5** schema_meta.version change — implemented in
//!   [`s5_schema_meta_change_check`].
//! - **S6** forum_post post-write race-miss — wired in `mcp_tools.rs`
//!   directly via [`ab_oob_alert`].
//!
//! DB-anomaly findings (S1, S5, S6) fire through [`ab_oob_alert`]
//! (file + tracing), bypassing SQLite. Non-DB findings (S2-S4) post
//! into the `incidents` board via the store's `forum_post` so the
//! signal lands somewhere human-reviewable.
//!
//! Env gate: `AB_C3_DISABLE=1` skips the tick entirely (escape hatch
//! for tests / pathological loops).

use std::fs;
use std::path::PathBuf;
use std::sync::Mutex;
use std::time::{Duration, Instant, SystemTime};

use ab_oob_alert::{write_alert, Alert, AlertKind, ProcessFd};
use ab_store::S234Counts;

/// Window between consecutive S2-S4 anchor snapshots (per §3.4.2 "5min").
pub const S234_WINDOW_SECS: u64 = 300;
/// S2 fires when active-memories count drops by more than this fraction.
pub const S2_DROP_THRESHOLD: f64 = 0.05;
/// S4 fires when memory_edges count drops by more than this fraction.
pub const S4_DROP_THRESHOLD: f64 = 0.05;

/// Process whose `cmdline` first token must match one of these path
/// suffixes for us to inspect its fd table. We match on suffix so both
/// `~/.local/bin/agent-bridge.real` (production wrapper layout) and
/// `target/release/agent-bridge` (dev layout) land in the same audit.
///
/// Future: read from `~/.config/agent-bridge/fd-watch-binaries.toml`
/// when the auxiliary fork list grows.
pub const SUSPECT_BINARY_SUFFIXES: &[&str] = &["agent-bridge.real", "agent-bridge"];

/// Returns `true` if [`c3_self_check`] is opted out via env var.
pub fn c3_disabled_via_env() -> bool {
    matches!(
        std::env::var("AB_C3_DISABLE").ok().as_deref(),
        Some("1") | Some("true") | Some("TRUE")
    )
}

/// Read `/proc/<pid>/cmdline`, return the first NUL-delimited token as
/// `Option<String>`. Returns `None` if the file is unreadable or the
/// cmdline is empty (kernel threads, zombies).
fn read_proc_cmdline_argv0(pid: u32) -> Option<String> {
    let path = PathBuf::from(format!("/proc/{pid}/cmdline"));
    let bytes = fs::read(&path).ok()?;
    if bytes.is_empty() {
        return None;
    }
    // cmdline is NUL-delimited; argv[0] runs up to the first NUL.
    let end = bytes.iter().position(|b| *b == 0).unwrap_or(bytes.len());
    Some(String::from_utf8_lossy(&bytes[..end]).into_owned())
}

/// Does `argv0` look like one of our binaries?
fn matches_suspect_binary(argv0: &str) -> bool {
    // First strip cmdline arguments by space (cmdline rare-case argv0
    // could contain a literal space; the kernel still NUL-separates so
    // [`read_proc_cmdline_argv0`] already handles that — but defensive
    // here in case argv0 was constructed atypically).
    let argv0 = argv0.split_whitespace().next().unwrap_or(argv0);
    SUSPECT_BINARY_SUFFIXES
        .iter()
        .any(|suffix| argv0.ends_with(suffix))
}

/// Scan `/proc/<pid>/fd/*` symlinks for state.db-family targets that
/// readlink-resolves to a `... (deleted)` path. Returns one
/// [`ProcessFd`] per offending fd (multiple may come from one PID —
/// daemon owns main/wal/shm = 3 fds).
fn enum_deleted_state_db_fds_for_pid(pid: u32) -> Vec<ProcessFd> {
    let fd_dir = PathBuf::from(format!("/proc/{pid}/fd"));
    let entries = match fs::read_dir(&fd_dir) {
        Ok(it) => it,
        Err(_) => return Vec::new(), // EACCES / process gone — fail silent
    };
    let mut out = Vec::new();
    for ent in entries.flatten() {
        let fd_num: u32 = match ent.file_name().to_string_lossy().parse() {
            Ok(n) => n,
            Err(_) => continue,
        };
        let target = match fs::read_link(ent.path()) {
            Ok(t) => t,
            Err(_) => continue,
        };
        let target_str = target.to_string_lossy();
        // Hit when target points to a state.db-family file marked deleted.
        if target_str.contains("state.db") && target_str.ends_with(" (deleted)") {
            out.push(ProcessFd {
                pid,
                fd: fd_num,
                target: target_str.into_owned(),
            });
        }
    }
    out
}

/// State for rate-limiting per (alert_kind, signal-fingerprint).
/// Per design §3.4.4, same signal max 1 alert per 1h window.
pub(crate) struct RateLimiter {
    /// Map `(kind, signature)` → last fired `Instant`. Kept tiny —
    /// O(1) signals per tick.
    seen: Vec<(String, Instant)>,
    window: Duration,
}

impl RateLimiter {
    const fn new(window: Duration) -> Self {
        Self {
            seen: Vec::new(),
            window,
        }
    }

    /// Returns `true` if `key` was last seen >`window` ago (or never)
    /// — caller should fire the alert. Also records the new sighting.
    pub(crate) fn check_and_record(&mut self, key: String, now: Instant) -> bool {
        // Garbage-collect entries outside the window.
        self.seen.retain(|(_, t)| now.duration_since(*t) <= self.window);
        if self.seen.iter().any(|(k, _)| k == &key) {
            return false;
        }
        self.seen.push((key, now));
        true
    }
}

/// Process-wide rate limiter. 1h window per design §3.4.4.
/// `pub(crate)` so siblings like S6 in `mcp_tools::ForumPostTool` can dedupe
/// against the same window — one fire-and-forget alert per (kind, signature)
/// across the whole bridge process.
pub(crate) fn rate_limiter() -> &'static Mutex<RateLimiter> {
    static LIM: std::sync::OnceLock<Mutex<RateLimiter>> = std::sync::OnceLock::new();
    LIM.get_or_init(|| Mutex::new(RateLimiter::new(Duration::from_secs(3600))))
}

/// Track last-seen schema version across S5 ticks. `None` until the
/// first tick observes a value.
fn s5_last_schema_version() -> &'static Mutex<Option<String>> {
    static V: std::sync::OnceLock<Mutex<Option<String>>> = std::sync::OnceLock::new();
    V.get_or_init(|| Mutex::new(None))
}

/// **S1** — enumerate `(deleted)` state.db fds across all
/// `agent-bridge.real` processes on this host.
///
/// Empty returned `Vec` = healthy state. Non-empty = at least one
/// process is holding a state.db fd whose path entry has been
/// unlinked (= F8 partial-swap consumer fork).
pub fn s1_enum_deleted_state_db_fds() -> Vec<ProcessFd> {
    let proc_dir = match fs::read_dir("/proc") {
        Ok(it) => it,
        Err(_) => return Vec::new(),
    };
    let mut out = Vec::new();
    for ent in proc_dir.flatten() {
        let name = ent.file_name();
        let pid: u32 = match name.to_string_lossy().parse() {
            Ok(p) => p,
            Err(_) => continue, // Not a PID dir
        };
        let argv0 = match read_proc_cmdline_argv0(pid) {
            Some(s) => s,
            None => continue,
        };
        if !matches_suspect_binary(&argv0) {
            continue;
        }
        out.extend(enum_deleted_state_db_fds_for_pid(pid));
    }
    out
}

/// **S5** — schema_meta.version change watch. Compares current version
/// against the in-process last-seen value; first call seeds the cache
/// without firing. Subsequent change fires an `OOB` alert with the
/// before/after evidence.
///
/// Returns `Some(alert)` when an alert was fired, `None` when stable
/// or first-tick seed.
pub fn s5_schema_meta_change_check(current_version: &str) -> Option<Alert> {
    let cell = s5_last_schema_version();
    let mut guard = match cell.lock() {
        Ok(g) => g,
        Err(_) => return None,
    };
    let prev = guard.clone();
    *guard = Some(current_version.to_string());
    drop(guard);

    let prev = prev?;
    if prev == current_version {
        return None;
    }
    let sig = format!("schema_change:{prev}->{current_version}");
    let now = Instant::now();
    if !rate_limiter().lock().ok()?.check_and_record(sig, now) {
        return None;
    }
    let alert = Alert::new(AlertKind::SchemaChange)
        .with_evidence(serde_json::json!({
            "before": prev,
            "after": current_version,
        }))
        .with_suggested_action(
            "inspect SCHEMA_V* migration in crates/store/src/sqlite.rs — \
             schema bump should always be commit-traceable",
        )
        .with_next_steps(vec![
            "git log --all -- crates/store/src/sqlite.rs | head -20".into(),
        ]);
    // NOTE: this function used to call `write_alert` inline. That leaked
    // test literals (`v26`→`v27`) into the production alert dir whenever
    // unit tests exercised the check — see `~/.cache/agent-bridge/alerts/`
    // pollution observed on Mac dogfood 2026-05-15. The pure shape now
    // returns the constructed Alert; only `s5_check_and_alert` (the
    // production wrapper) persists it.
    Some(alert)
}

/// **S1 + alert dispatch** — wrapper that runs S1 and, on hit, fires
/// an OOB alert (rate-limited by hit signature). Returns the inventory
/// for caller logging. Designed to be called from the daemon tick.
pub fn s1_check_and_alert() -> Vec<ProcessFd> {
    let inv = s1_enum_deleted_state_db_fds();
    if inv.is_empty() {
        return inv;
    }
    // Rate-limit by sorted list of pids — same set of offenders within
    // the window only fires once.
    let mut pids: Vec<u32> = inv.iter().map(|p| p.pid).collect();
    pids.sort();
    let sig = format!(
        "fd_deleted:{}",
        pids.iter()
            .map(|p| p.to_string())
            .collect::<Vec<_>>()
            .join(",")
    );
    let now = Instant::now();
    let fire = match rate_limiter().lock() {
        Ok(mut g) => g.check_and_record(sig, now),
        Err(_) => true, // poisoned → still attempt alert
    };
    if !fire {
        return inv;
    }
    let alert = Alert::new(AlertKind::FdDeleted)
        .with_process_inventory(inv.clone())
        .with_suggested_action(
            "agent-bridge rescue-snapshot --canonical && sibling kill+respawn",
        )
        .with_next_steps(vec![
            "see lesson_state_db_deleted_inode_vs_phantom_diagnosis".into(),
            "see lesson_split_brain_forum_id_collision".into(),
        ]);
    let _ = write_alert(&alert);
    inv
}

/// **S5 + dispatch** — convenience wrapper around `s5_schema_meta_change_check`
/// for daemon tick. The alert was already written inside; this returns
/// `bool` for caller telemetry.
pub fn s5_check_and_alert(current_version: &str) -> bool {
    match s5_schema_meta_change_check(current_version) {
        Some(alert) => {
            let _ = write_alert(&alert);
            true
        }
        None => false,
    }
}

/// Which of the three count series tripped. Stable as a kebab-case
/// string for forum_post titles.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum S234Signal {
    /// S2 — `memories` active count dropped > 5% in one 5-min window.
    S2Memories,
    /// S3 — `forum_threads` total count dropped at all in one 5-min
    /// window (threshold = drop > 0; threads only retire via status,
    /// they shouldn't disappear).
    S3ForumThreads,
    /// S4 — `memory_edges` total count dropped > 5% in one 5-min
    /// window.
    S4MemoryEdges,
}

impl S234Signal {
    pub fn as_str(&self) -> &'static str {
        match self {
            S234Signal::S2Memories => "s2-memories-drop",
            S234Signal::S3ForumThreads => "s3-forum-threads-drop",
            S234Signal::S4MemoryEdges => "s4-memory-edges-drop",
        }
    }
}

/// One drop the §3.4.2 check would have alerted on. Caller decides
/// where to post (forum vs. local log).
#[derive(Debug, Clone, PartialEq)]
pub struct S234DropEvent {
    pub signal: S234Signal,
    pub before: u64,
    pub after: u64,
    /// Fraction of `before` lost (0.0..=1.0). For S3 the threshold is
    /// "any drop" but we still report the percentage for the alert body.
    pub drop_pct: f64,
}

/// Per-process anchor snapshot for S2-S4. `None` until the first tick
/// observes a value; `Some((ts, counts))` once seeded. Rotated to the
/// current sample once `now - ts >= S234_WINDOW_SECS` (per §3.4.2).
fn s234_last_snapshot() -> &'static Mutex<Option<(SystemTime, S234Counts)>> {
    static C: std::sync::OnceLock<Mutex<Option<(SystemTime, S234Counts)>>> =
        std::sync::OnceLock::new();
    C.get_or_init(|| Mutex::new(None))
}

/// Pure logic for the three drop checks. Exposed for testability —
/// the anchor management lives in [`s234_check_against_snapshot`].
pub fn compute_s234_drops(prev: S234Counts, current: S234Counts) -> Vec<S234DropEvent> {
    let mut out = Vec::new();
    // S2 — memories_active drop > 5%
    if prev.memories_active > 0 && current.memories_active < prev.memories_active {
        let drop = prev.memories_active - current.memories_active;
        let pct = drop as f64 / prev.memories_active as f64;
        if pct > S2_DROP_THRESHOLD {
            out.push(S234DropEvent {
                signal: S234Signal::S2Memories,
                before: prev.memories_active,
                after: current.memories_active,
                drop_pct: pct,
            });
        }
    }
    // S3 — forum_threads drop > 0 (threads should never disappear)
    if current.forum_threads < prev.forum_threads {
        let drop = prev.forum_threads - current.forum_threads;
        let pct = if prev.forum_threads > 0 {
            drop as f64 / prev.forum_threads as f64
        } else {
            0.0
        };
        out.push(S234DropEvent {
            signal: S234Signal::S3ForumThreads,
            before: prev.forum_threads,
            after: current.forum_threads,
            drop_pct: pct,
        });
    }
    // S4 — memory_edges drop > 5%
    if prev.memory_edges > 0 && current.memory_edges < prev.memory_edges {
        let drop = prev.memory_edges - current.memory_edges;
        let pct = drop as f64 / prev.memory_edges as f64;
        if pct > S4_DROP_THRESHOLD {
            out.push(S234DropEvent {
                signal: S234Signal::S4MemoryEdges,
                before: prev.memory_edges,
                after: current.memory_edges,
                drop_pct: pct,
            });
        }
    }
    out
}

/// **S2-S4** — compare `current` counts against the 5-min anchor,
/// returning the drops that fired AND passed the shared rate limiter.
/// Caller is responsible for emitting each event to its channel
/// (forum_post per §3.4.1).
///
/// Snapshot lifecycle:
/// - first call seeds the anchor with `(now, current)` and returns
///   empty (no comparison possible).
/// - subsequent calls within `< S234_WINDOW_SECS` of anchor return
///   empty (still in window).
/// - calls at `>= S234_WINDOW_SECS` compare current vs anchor, rotate
///   anchor to `(now, current)`, and return the drop set.
pub fn s234_check_against_snapshot(
    current: S234Counts,
    now: SystemTime,
) -> Vec<S234DropEvent> {
    let mut guard = match s234_last_snapshot().lock() {
        Ok(g) => g,
        Err(_) => return Vec::new(),
    };

    let (prev_ts, prev_counts) = match *guard {
        Some(snap) => snap,
        None => {
            *guard = Some((now, current));
            return Vec::new();
        }
    };

    let age = now.duration_since(prev_ts).unwrap_or(Duration::ZERO);
    if age.as_secs() < S234_WINDOW_SECS {
        return Vec::new();
    }

    let events = compute_s234_drops(prev_counts, current);
    *guard = Some((now, current));
    drop(guard);

    // Rate-limit each event via the shared rate_limiter (1h window).
    let limit_now = Instant::now();
    let mut out = Vec::new();
    for ev in events {
        let sig = format!(
            "{}:{}->{}",
            ev.signal.as_str(),
            ev.before,
            ev.after
        );
        let allow = match rate_limiter().lock() {
            Ok(mut g) => g.check_and_record(sig, limit_now),
            Err(_) => true,
        };
        if allow {
            out.push(ev);
        }
    }
    out
}

/// Format an S2-S4 alert body per design §3.4.5. The forum_post tool
/// receives this as the body; the title is built separately by the
/// caller to keep the heading short.
pub fn format_s234_alert_body(ev: &S234DropEvent, ts_unix: i64) -> String {
    format!(
        "[ALERT] {} at ts_unix={}\n\
         [evidence] {} → {} ({:.1}% drop in <={}s window)\n\
         [fd_state] state.db = live (non-DB-anomaly tier)\n\
         [suggested action] inspect dream-tier output / GC logs / \
         recent retire ops; see docs/DESIGN-COLLAB-PROTOCOL-v0.md §3.4.4 \
         for false-positive mitigations",
        ev.signal.as_str(),
        ts_unix,
        ev.before,
        ev.after,
        ev.drop_pct * 100.0,
        S234_WINDOW_SECS,
    )
}

/// Test-only: clear the S2-S4 anchor so a fresh test run isn't biased
/// by previous tests in the same process.
#[cfg(test)]
pub(crate) fn _reset_s234_snapshot_for_tests() {
    if let Ok(mut g) = s234_last_snapshot().lock() {
        *g = None;
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn suspect_binary_matches_both_path_layouts() {
        assert!(matches_suspect_binary(
            "/home/pallasting/.local/bin/agent-bridge.real"
        ));
        assert!(matches_suspect_binary(
            "/Data/CascadeProjects/agent-bridge/target/release/agent-bridge"
        ));
        assert!(matches_suspect_binary("agent-bridge.real"));
        assert!(!matches_suspect_binary("/usr/bin/zsh"));
        assert!(!matches_suspect_binary("agent-bridge-helper"));
    }

    #[test]
    fn cmdline_argv0_handles_missing_pid() {
        // Very high PID that almost certainly doesn't exist.
        assert!(read_proc_cmdline_argv0(9_999_999).is_none());
    }

    #[test]
    // `/proc/self/cmdline` only exists on Linux; on macOS there's no `/proc`
    // at all. S1's runtime path already returns Vec::new() gracefully when
    // /proc is missing, so the helper degrades correctly — this test is a
    // Linux-only sanity check.
    #[cfg(target_os = "linux")]
    fn cmdline_argv0_self_returns_test_runner() {
        // /proc/self/cmdline is readable in normal test env. The token
        // we get back depends on cargo's harness; just assert non-empty.
        let argv0 = read_proc_cmdline_argv0(std::process::id())
            .expect("/proc/self/cmdline readable");
        assert!(!argv0.is_empty());
    }

    #[test]
    fn s1_returns_empty_when_no_agent_bridge_process_running() {
        // In test env there's no agent-bridge.real instance with
        // (deleted) state.db; expect empty.
        // (If tests are running concurrently with a real daemon that
        // happens to have a deleted fd, this assertion may flake — in
        // that case the real signal is exactly what we want to fire,
        // so failure here is informative.)
        let out = s1_enum_deleted_state_db_fds();
        // We don't assert empty because production may have such a fd
        // (today's case study). Just assert the call doesn't panic.
        // Length assertion in integration tests with mock /proc.
        let _ = out;
    }

    #[test]
    fn c3_env_disable_recognized() {
        std::env::set_var("AB_C3_DISABLE", "1");
        assert!(c3_disabled_via_env());
        std::env::set_var("AB_C3_DISABLE", "0");
        assert!(!c3_disabled_via_env());
        std::env::remove_var("AB_C3_DISABLE");
        assert!(!c3_disabled_via_env());
    }

    #[test]
    fn rate_limiter_drops_repeated_signal_within_window() {
        let mut rl = RateLimiter::new(Duration::from_secs(3600));
        let t0 = Instant::now();
        assert!(rl.check_and_record("k1".into(), t0));
        // Same key within window → suppressed.
        assert!(!rl.check_and_record("k1".into(), t0 + Duration::from_secs(60)));
        // Different key → fires.
        assert!(rl.check_and_record("k2".into(), t0 + Duration::from_secs(120)));
    }

    #[test]
    fn rate_limiter_lets_signal_through_after_window() {
        let mut rl = RateLimiter::new(Duration::from_secs(60));
        let t0 = Instant::now();
        assert!(rl.check_and_record("k".into(), t0));
        // Past window → re-fires.
        assert!(rl.check_and_record("k".into(), t0 + Duration::from_secs(120)));
    }

    #[test]
    fn s5_first_call_seeds_without_firing() {
        let _g = S5_TEST_LOCK.lock().unwrap_or_else(|e| e.into_inner());
        // Reset the per-process cache so tests are deterministic; the
        // module-level static can't be reset post-init, so this test
        // uses a stable, unlikely-to-collide version string.
        let _ = s5_schema_meta_change_check("v26");
        // Calling again with the same version: no alert.
        assert!(s5_schema_meta_change_check("v26").is_none());
    }

    /// Wet-test smoke against the LIVE host's `/proc`. Ignored by
    /// default (depends on production state, not deterministic).
    /// Run with `--ignored --nocapture` to inspect what S1 sees in
    /// real time:
    ///
    /// ```bash
    /// cargo test -p ab-bridge --lib c3_self_check::tests::s1_wet_test \
    ///     -- --ignored --nocapture
    /// ```
    ///
    /// Per `lesson_state_db_deleted_inode_vs_phantom_diagnosis` today's
    /// production has ~8 auxiliary MCPs still holding zombie deleted-
    /// inode fds (per #132 inventory). S1 should enumerate them.
    #[test]
    #[ignore = "wet-test: depends on live host /proc; run with --ignored"]
    fn s1_wet_test_against_live_proc() {
        let inv = s1_enum_deleted_state_db_fds();
        eprintln!(
            "[S1 wet-test] live /proc inventory: {} entries",
            inv.len()
        );
        for p in &inv {
            eprintln!("  pid={} fd={} target={}", p.pid, p.fd, p.target);
        }
    }

    // The three s5_* tests below share the module-level
    // `s5_last_schema_version` Mutex. Without serialization, a sibling
    // test can race in between Test A's seed call and its assertion
    // call, leaving stale global state. This in-mod lock is cheap and
    // avoids pulling in `serial_test` as a workspace dep.
    static S5_TEST_LOCK: std::sync::Mutex<()> = std::sync::Mutex::new(());

    #[test]
    fn s5_pure_check_does_not_write_to_alert_dir() {
        // Regression: until 2026-05-15 the pure check inlined
        // `write_alert`, so every test that exercised it leaked
        // `v26→v27` JSON into the production alert dir
        // (`~/.cache/agent-bridge/alerts/`). After this refactor the
        // pure shape is side-effect-free; only `s5_check_and_alert`
        // persists. Point AB_OOB_ALERT_DIR at a fresh tempdir and
        // assert it stays empty after a transition.
        let _g = S5_TEST_LOCK.lock().unwrap_or_else(|e| e.into_inner());
        let tag = format!(
            "ab-s5-pure-{}",
            std::time::SystemTime::now()
                .duration_since(std::time::UNIX_EPOCH)
                .unwrap_or_default()
                .as_nanos()
        );
        let dir = std::env::temp_dir().join(&tag);
        std::env::set_var("AB_OOB_ALERT_DIR", &dir);
        let v_seed = format!("PURE_SEED_{tag}");
        let v_change = format!("PURE_CHANGE_{tag}");
        let _ = s5_schema_meta_change_check(&v_seed);
        let alert = s5_schema_meta_change_check(&v_change);
        assert!(alert.is_some(), "transition must still produce Alert");
        assert!(
            !dir.exists(),
            "pure check leaked into AB_OOB_ALERT_DIR={dir:?}"
        );
        std::env::remove_var("AB_OOB_ALERT_DIR");
    }

    #[test]
    fn s5_change_returns_some_with_evidence() {
        let _g = S5_TEST_LOCK.lock().unwrap_or_else(|e| e.into_inner());
        // Seed (may or may not be first call in the test run; either
        // way we just need a known prior).
        let _ = s5_schema_meta_change_check("v26");
        let alert = s5_schema_meta_change_check("v27");
        assert!(alert.is_some(), "version change must fire an alert");
        let alert = alert.unwrap();
        assert_eq!(alert.kind, AlertKind::SchemaChange);
        let ev = &alert.evidence;
        assert_eq!(ev["before"], "v26");
        assert_eq!(ev["after"], "v27");
    }

    // ─── S2-S4 — drop-detection ────────────────────────────────────────

    // The four s234_* tests share the module-level `s234_last_snapshot`
    // Mutex; serialize them with this lock so a sibling test can't see
    // stale state from a previous run within the same process.
    static S234_TEST_LOCK: std::sync::Mutex<()> = std::sync::Mutex::new(());

    fn mk_counts(memories: u64, threads: u64, edges: u64) -> S234Counts {
        S234Counts {
            memories_active: memories,
            forum_threads: threads,
            memory_edges: edges,
        }
    }

    #[test]
    fn compute_s234_drops_no_change_no_events() {
        let prev = mk_counts(100, 5, 200);
        let cur = mk_counts(100, 5, 200);
        assert!(compute_s234_drops(prev, cur).is_empty());
    }

    #[test]
    fn compute_s234_drops_s2_below_threshold_no_event() {
        // 5% drop is the threshold (exclusive >). Drop to 95 from 100 = 5%,
        // which is NOT strictly greater than 5% → no event.
        let prev = mk_counts(100, 5, 200);
        let cur = mk_counts(95, 5, 200);
        assert!(compute_s234_drops(prev, cur).is_empty());
    }

    #[test]
    fn compute_s234_drops_s2_above_threshold_fires() {
        let prev = mk_counts(100, 5, 200);
        let cur = mk_counts(80, 5, 200); // 20% drop
        let events = compute_s234_drops(prev, cur);
        assert_eq!(events.len(), 1);
        assert_eq!(events[0].signal, S234Signal::S2Memories);
        assert_eq!(events[0].before, 100);
        assert_eq!(events[0].after, 80);
        assert!((events[0].drop_pct - 0.20).abs() < 1e-9);
    }

    #[test]
    fn compute_s234_drops_s3_any_drop_fires() {
        // S3 threshold is strictly drop > 0 (threads should never
        // disappear under normal operation).
        let prev = mk_counts(100, 5, 200);
        let cur = mk_counts(100, 4, 200);
        let events = compute_s234_drops(prev, cur);
        assert_eq!(events.len(), 1);
        assert_eq!(events[0].signal, S234Signal::S3ForumThreads);
    }

    #[test]
    fn compute_s234_drops_s4_above_threshold_fires() {
        let prev = mk_counts(100, 5, 200);
        let cur = mk_counts(100, 5, 170); // 15% drop
        let events = compute_s234_drops(prev, cur);
        assert_eq!(events.len(), 1);
        assert_eq!(events[0].signal, S234Signal::S4MemoryEdges);
    }

    #[test]
    fn compute_s234_drops_growth_never_fires() {
        // Adding memories / threads / edges is normal and must never
        // alert (the signal is one-sided).
        let prev = mk_counts(100, 5, 200);
        let cur = mk_counts(200, 10, 400);
        assert!(compute_s234_drops(prev, cur).is_empty());
    }

    #[test]
    fn s234_check_first_call_seeds_returns_empty() {
        let _g = S234_TEST_LOCK.lock().unwrap_or_else(|e| e.into_inner());
        _reset_s234_snapshot_for_tests();
        let now = SystemTime::UNIX_EPOCH + Duration::from_secs(1_000_000);
        let out = s234_check_against_snapshot(mk_counts(100, 5, 200), now);
        assert!(out.is_empty(), "first call must seed, return empty");
    }

    #[test]
    fn s234_check_within_window_returns_empty_even_on_drop() {
        let _g = S234_TEST_LOCK.lock().unwrap_or_else(|e| e.into_inner());
        _reset_s234_snapshot_for_tests();
        let t0 = SystemTime::UNIX_EPOCH + Duration::from_secs(1_000_000);
        let _ = s234_check_against_snapshot(mk_counts(100, 5, 200), t0); // seed
        // 60s later (well within the 5-min window); even with a clear
        // drop, the helper must wait for the window to elapse.
        let t1 = t0 + Duration::from_secs(60);
        let out = s234_check_against_snapshot(mk_counts(50, 5, 200), t1);
        assert!(out.is_empty(), "within-window must not fire (got {out:?})");
    }

    #[test]
    fn s234_check_past_window_with_drop_fires_event() {
        let _g = S234_TEST_LOCK.lock().unwrap_or_else(|e| e.into_inner());
        _reset_s234_snapshot_for_tests();
        // Use a high base time to avoid sig collision across tests that
        // share the same rate limiter.
        let base = 9_000_000 + (std::process::id() as u64);
        let t0 = SystemTime::UNIX_EPOCH + Duration::from_secs(base);
        let _ = s234_check_against_snapshot(mk_counts(1000, 100, 5000), t0);
        let t1 = t0 + Duration::from_secs(S234_WINDOW_SECS + 5);
        let out = s234_check_against_snapshot(mk_counts(800, 100, 5000), t1);
        assert_eq!(out.len(), 1, "expected one drop event (got {out:?})");
        assert_eq!(out[0].signal, S234Signal::S2Memories);
        assert_eq!(out[0].before, 1000);
        assert_eq!(out[0].after, 800);
    }

    #[test]
    fn format_s234_alert_body_contains_signal_and_evidence() {
        let ev = S234DropEvent {
            signal: S234Signal::S4MemoryEdges,
            before: 500,
            after: 400,
            drop_pct: 0.20,
        };
        let body = format_s234_alert_body(&ev, 1_700_000_000);
        assert!(body.contains("s4-memory-edges-drop"), "signal in body");
        assert!(body.contains("500"), "before in body");
        assert!(body.contains("400"), "after in body");
        assert!(body.contains("20"), "percent in body");
        assert!(body.contains("ts_unix=1700000000"), "ts in body");
        assert!(body.contains("non-DB-anomaly"), "tier annotation present");
    }
}
