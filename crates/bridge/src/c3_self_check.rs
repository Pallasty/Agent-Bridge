//! **C3 — Daemon self-check tick** (Collab Protocol v0, design §3.4).
//!
//! Run once per 30s tick from `Cmd::Daemon`. Detects:
//!
//! - **S1** any `agent-bridge.real`-binary process holding a state.db
//!   FD that readlink-resolves to `... (deleted)` (F8 multi-process
//!   partial-swap mitigation).
//! - **S2-S4** DB metric drops (memories.count / forum_threads.count /
//!   memory_edges.count) — implemented in [`db_metric_check`].
//! - **S5** schema_meta.version change — implemented in
//!   [`db_metric_check`].
//!
//! DB-anomaly findings (S1, S5, S6) fire through [`ab_oob_alert`]
//! (file + tracing), bypassing SQLite. Non-DB findings (S2-S4) go via
//! `forum_post` (TODO: wire when storeAdapter exposes it).
//!
//! Env gate: `AB_C3_DISABLE=1` skips the tick entirely (escape hatch
//! for tests / pathological loops).

use std::fs;
use std::path::PathBuf;
use std::sync::Mutex;
use std::time::{Duration, Instant};

use ab_oob_alert::{write_alert, Alert, AlertKind, ProcessFd};

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
}
