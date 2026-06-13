use std::collections::{BTreeMap, HashMap};
use std::path::{Path, PathBuf};
use std::time::{SystemTime, UNIX_EPOCH};

use serde::{Deserialize, Serialize};
use serde_json::{json, Value};

pub const OBSERVER_MAX_BYTES: u64 = 8 * 1024 * 1024;
const MIN_SESSIONS: usize = 5;
const MINEABLE_MEAN_GATE: f64 = 1.0;

const CORRECTION_CUES: &[&str] = &[
    "不对",
    "不是",
    "错了",
    "错误",
    "应该",
    "而不是",
    "别这样",
    "不要",
    "其实",
    "重来",
    "撤销",
    "回退",
    "改成",
    "不行",
    "有问题",
    "搞错",
    "弄反",
    "no,",
    "not quite",
    "that's not",
    "that is not",
    "wrong",
    "actually",
    "instead",
    "should be",
    "should not",
    "shouldn't",
    "don't",
    "do not",
    "revert",
    "undo",
    "rollback",
    "mistake",
    "incorrect",
    "fix that",
    "no.",
];

#[derive(Debug, Clone, Deserialize)]
struct ObservationRecord {
    ts: Option<f64>,
    sid: Option<String>,
    ev: Option<String>,
    prompt: Option<String>,
    tool: Option<String>,
    err: Option<bool>,
    err_source: Option<Value>,
    stderr_nonempty: Option<bool>,
}

#[derive(Debug, Clone, Default, Serialize, PartialEq, Eq)]
pub struct SessionSignalSummary {
    pub prompts: u64,
    pub corrections: u64,
    pub tools: u64,
    pub clean_errors: u64,
    pub clean_error_resolutions: u64,
    pub stderr_success: u64,
    pub legacy_untrusted_errors: u64,
    pub legacy_error_resolutions: u64,
    pub clean_mineable: u64,
    pub legacy_upper_bound_mineable: u64,
}

#[derive(Debug, Clone, Serialize, PartialEq)]
pub struct InstinctObserverStatus {
    pub enabled: bool,
    pub installed_path: String,
    pub installed: bool,
    pub executable: bool,
    pub log_path: String,
    pub log_dir_path: String,
    pub log_present: bool,
    pub log_dir_mode_octal: Option<String>,
    pub log_mode_octal: Option<String>,
    pub permissions_ok: bool,
    pub log_bytes: u64,
    pub max_bytes: u64,
    pub total_records: u64,
    pub sessions: usize,
    pub events: BTreeMap<String, u64>,
    pub top_tools: Vec<(String, u64)>,
    pub latest_event_at_unix: Option<f64>,
    pub latest_event_age_secs: Option<u64>,
    pub total_clean_mineable: u64,
    pub mean_clean_mineable_per_session: f64,
    pub total_legacy_upper_bound_mineable: u64,
    pub mean_legacy_upper_bound_per_session: f64,
    pub legacy_untrusted_errors: u64,
    pub stderr_success_records: u64,
    pub gate: String,
    pub verdict: String,
    pub legacy_upper_bound_verdict: String,
    pub recommendation: String,
    pub per_session: BTreeMap<String, SessionSignalSummary>,
}

#[derive(Debug, Clone, Default)]
struct SessionWorking {
    summary: SessionSignalSummary,
    clean_pending: HashMap<String, u64>,
    legacy_pending: HashMap<String, u64>,
}

pub fn default_observer_log_path() -> PathBuf {
    if let Some(path) = std::env::var_os("AB_INSTINCT_OBSERVER_LOG") {
        return PathBuf::from(path);
    }
    if Path::new("/Data").is_dir() {
        return PathBuf::from("/Data/agent-bridge/instinct-probe/observations.jsonl");
    }
    home_dir()
        .join(".cache")
        .join("agent-bridge")
        .join("instinct-probe")
        .join("observations.jsonl")
}

pub fn installed_observer_hook_path() -> PathBuf {
    home_dir()
        .join(".local")
        .join("bin")
        .join("ab-instinct-observer-hook")
}

fn home_dir() -> PathBuf {
    std::env::var("HOME")
        .map(PathBuf::from)
        .unwrap_or_else(|_| PathBuf::from("/tmp"))
}

pub fn observer_status() -> InstinctObserverStatus {
    observer_status_for_paths(
        installed_observer_hook_path(),
        default_observer_log_path(),
        std::env::var("AB_INSTINCT_OBSERVER").unwrap_or_else(|_| "1".to_string()) != "0",
    )
}

pub fn observer_status_json() -> Value {
    serde_json::to_value(observer_status()).unwrap_or_else(|e| {
        json!({
            "enabled": std::env::var("AB_INSTINCT_OBSERVER").unwrap_or_else(|_| "1".to_string()) != "0",
            "error": e.to_string()
        })
    })
}

pub fn rotate_observer_log(dry_run: bool) -> std::io::Result<Value> {
    let now_unix = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map(|d| d.as_secs())
        .unwrap_or(0);
    rotate_observer_log_for_path(&default_observer_log_path(), now_unix, dry_run)
}

pub fn rotate_observer_log_for_path(
    log_path: &Path,
    now_unix: u64,
    dry_run: bool,
) -> std::io::Result<Value> {
    let meta = std::fs::metadata(log_path).ok();
    let log_exists = meta.as_ref().is_some_and(|m| m.is_file());
    let log_bytes = meta.as_ref().map(|m| m.len()).unwrap_or(0);
    let archive_path = observer_log_archive_path(log_path, now_unix);
    let action = if log_exists { "rotate_log" } else { "noop" };
    let mut status = if log_exists {
        if dry_run {
            "would_rotate"
        } else {
            "rotated"
        }
    } else {
        "no_log"
    };

    if log_exists && !dry_run {
        std::fs::rename(log_path, &archive_path)?;
    } else if !log_exists && !dry_run {
        status = "no_log";
    }

    Ok(json!({
        "schema": "agent_bridge_instinct_observer_log_rotation.v0",
        "dry_run": dry_run,
        "action": action,
        "status": status,
        "log_path": log_path.display().to_string(),
        "archive_path": archive_path.display().to_string(),
        "log_exists": log_exists,
        "log_bytes": log_bytes,
        "max_bytes": OBSERVER_MAX_BYTES,
        "rotation_recommended": log_bytes >= OBSERVER_MAX_BYTES,
    }))
}

fn observer_log_archive_path(log_path: &Path, now_unix: u64) -> PathBuf {
    let file_name = log_path
        .file_name()
        .and_then(|name| name.to_str())
        .unwrap_or("observations.jsonl");
    log_path.with_file_name(format!("{file_name}.rotated-{now_unix}"))
}

pub fn observer_status_for_paths(
    installed_path: PathBuf,
    log_path: PathBuf,
    enabled: bool,
) -> InstinctObserverStatus {
    let installed = installed_path.exists();
    let executable = installed && is_executable(&installed_path);
    let log_dir_path = log_path
        .parent()
        .map(Path::to_path_buf)
        .unwrap_or_else(|| PathBuf::from(""));
    let log_dir_mode = private_dir_mode_octal(&log_dir_path);
    let log_meta = std::fs::metadata(&log_path).ok();
    let log_present = log_meta.as_ref().is_some_and(|m| m.is_file());
    let log_mode = private_file_mode_octal(&log_path);
    let permissions_ok = observer_permissions_ok(&log_dir_path, &log_path, log_present);
    let log_bytes = log_meta.as_ref().map(|m| m.len()).unwrap_or(0);
    let records = load_records(&log_path);
    let analyzed = analyze_records(&records);
    let summary = summarize(&records, analyzed);
    let recommendation = recommendation_for(enabled, &summary, log_present, log_bytes);

    InstinctObserverStatus {
        enabled,
        installed_path: installed_path.display().to_string(),
        installed,
        executable,
        log_path: log_path.display().to_string(),
        log_dir_path: log_dir_path.display().to_string(),
        log_present,
        log_dir_mode_octal: log_dir_mode,
        log_mode_octal: log_mode,
        permissions_ok,
        log_bytes,
        max_bytes: OBSERVER_MAX_BYTES,
        total_records: records.len() as u64,
        sessions: summary.per_session.len(),
        events: summary.events,
        top_tools: summary.top_tools,
        latest_event_at_unix: summary.latest_event_at_unix,
        latest_event_age_secs: summary.latest_event_age_secs,
        total_clean_mineable: summary.total_clean_mineable,
        mean_clean_mineable_per_session: summary.mean_clean_mineable_per_session,
        total_legacy_upper_bound_mineable: summary.total_legacy_upper_bound_mineable,
        mean_legacy_upper_bound_per_session: summary.mean_legacy_upper_bound_per_session,
        legacy_untrusted_errors: summary.legacy_untrusted_errors,
        stderr_success_records: summary.stderr_success_records,
        gate: format!("mean>={MINEABLE_MEAN_GATE:.1} over >={MIN_SESSIONS} sessions"),
        verdict: verdict_for(
            summary.mean_clean_mineable_per_session,
            summary.per_session.len(),
        ),
        legacy_upper_bound_verdict: verdict_for(
            summary.mean_legacy_upper_bound_per_session,
            summary.per_session.len(),
        ),
        recommendation,
        per_session: summary.per_session,
    }
}

#[derive(Debug, Clone)]
struct ObserverSummary {
    events: BTreeMap<String, u64>,
    top_tools: Vec<(String, u64)>,
    latest_event_at_unix: Option<f64>,
    latest_event_age_secs: Option<u64>,
    total_clean_mineable: u64,
    mean_clean_mineable_per_session: f64,
    total_legacy_upper_bound_mineable: u64,
    mean_legacy_upper_bound_per_session: f64,
    legacy_untrusted_errors: u64,
    stderr_success_records: u64,
    per_session: BTreeMap<String, SessionSignalSummary>,
}

fn load_records(path: &Path) -> Vec<ObservationRecord> {
    let Ok(text) = std::fs::read_to_string(path) else {
        return Vec::new();
    };
    text.lines()
        .filter_map(|line| {
            let line = line.trim();
            if line.is_empty() {
                None
            } else {
                serde_json::from_str::<ObservationRecord>(line).ok()
            }
        })
        .collect()
}

fn analyze_records(records: &[ObservationRecord]) -> BTreeMap<String, SessionSignalSummary> {
    let mut sorted = records.to_vec();
    sorted.sort_by(|a, b| {
        a.ts.unwrap_or(0.0)
            .partial_cmp(&b.ts.unwrap_or(0.0))
            .unwrap_or(std::cmp::Ordering::Equal)
    });

    let mut sessions: BTreeMap<String, SessionWorking> = BTreeMap::new();
    for record in &sorted {
        let sid = record.sid.as_deref().unwrap_or("?").to_string();
        let state = sessions.entry(sid).or_default();
        match record.ev.as_deref() {
            Some("UserPromptSubmit") => {
                state.summary.prompts += 1;
                if classify_prompt(record.prompt.as_deref().unwrap_or_default()) {
                    state.summary.corrections += 1;
                }
            }
            Some("PostToolUse") => {
                state.summary.tools += 1;
                let tool = record.tool.as_deref().unwrap_or("?").to_string();
                let clean_err = is_clean_error(record);
                let legacy_err = record.err.unwrap_or(false);
                let stderr_success = record.stderr_nonempty.unwrap_or(false) && !clean_err;
                let legacy_untrusted = legacy_err && !has_err_source(record);

                if stderr_success {
                    state.summary.stderr_success += 1;
                }
                if legacy_untrusted {
                    state.summary.legacy_untrusted_errors += 1;
                }

                if clean_err {
                    state.summary.clean_errors += 1;
                    *state.clean_pending.entry(tool.clone()).or_insert(0) += 1;
                } else if decrement_pending(&mut state.clean_pending, &tool) {
                    state.summary.clean_error_resolutions += 1;
                }

                if legacy_err {
                    *state.legacy_pending.entry(tool.clone()).or_insert(0) += 1;
                } else if decrement_pending(&mut state.legacy_pending, &tool) {
                    state.summary.legacy_error_resolutions += 1;
                }
            }
            _ => {}
        }
    }

    sessions
        .into_iter()
        .map(|(sid, mut state)| {
            state.summary.clean_mineable =
                state.summary.corrections + state.summary.clean_error_resolutions;
            state.summary.legacy_upper_bound_mineable =
                state.summary.corrections + state.summary.legacy_error_resolutions;
            (sid, state.summary)
        })
        .collect()
}

fn summarize(
    records: &[ObservationRecord],
    per_session: BTreeMap<String, SessionSignalSummary>,
) -> ObserverSummary {
    let mut events = BTreeMap::new();
    let mut tools = BTreeMap::new();
    let mut latest_event_at_unix: Option<f64> = None;
    for record in records {
        let ev = record.ev.as_deref().unwrap_or("?").to_string();
        *events.entry(ev.clone()).or_insert(0) += 1;
        if ev == "PostToolUse" {
            *tools
                .entry(record.tool.as_deref().unwrap_or("?").to_string())
                .or_insert(0) += 1;
        }
        if let Some(ts) = record.ts {
            latest_event_at_unix = Some(
                latest_event_at_unix
                    .map(|latest| latest.max(ts))
                    .unwrap_or(ts),
            );
        }
    }

    let mut top_tools: Vec<(String, u64)> = tools.into_iter().collect();
    top_tools.sort_by(|a, b| b.1.cmp(&a.1).then_with(|| a.0.cmp(&b.0)));
    top_tools.truncate(10);

    let sessions = per_session.len();
    let total_clean_mineable = per_session.values().map(|s| s.clean_mineable).sum();
    let total_legacy_upper_bound_mineable = per_session
        .values()
        .map(|s| s.legacy_upper_bound_mineable)
        .sum();
    let legacy_untrusted_errors = per_session
        .values()
        .map(|s| s.legacy_untrusted_errors)
        .sum();
    let stderr_success_records = per_session.values().map(|s| s.stderr_success).sum();

    ObserverSummary {
        events,
        top_tools,
        latest_event_at_unix,
        latest_event_age_secs: latest_event_at_unix.and_then(latest_age_secs),
        total_clean_mineable,
        mean_clean_mineable_per_session: mean(total_clean_mineable, sessions),
        total_legacy_upper_bound_mineable,
        mean_legacy_upper_bound_per_session: mean(total_legacy_upper_bound_mineable, sessions),
        legacy_untrusted_errors,
        stderr_success_records,
        per_session,
    }
}

fn classify_prompt(text: &str) -> bool {
    let low = text.to_lowercase();
    CORRECTION_CUES
        .iter()
        .any(|cue| text.contains(cue) || low.contains(cue))
}

fn is_clean_error(record: &ObservationRecord) -> bool {
    record.err.unwrap_or(false) && has_err_source(record)
}

fn has_err_source(record: &ObservationRecord) -> bool {
    match &record.err_source {
        Some(Value::Null) | None => false,
        Some(Value::String(s)) => !s.trim().is_empty(),
        Some(_) => true,
    }
}

fn decrement_pending(pending: &mut HashMap<String, u64>, tool: &str) -> bool {
    let Some(count) = pending.get_mut(tool) else {
        return false;
    };
    if *count == 0 {
        return false;
    }
    *count -= 1;
    true
}

fn mean(total: u64, sessions: usize) -> f64 {
    if sessions == 0 {
        return 0.0;
    }
    let mean = total as f64 / sessions as f64;
    (mean * 1000.0).round() / 1000.0
}

fn verdict_for(mean: f64, sessions: usize) -> String {
    if sessions < MIN_SESSIONS {
        "INSUFFICIENT_SESSIONS".to_string()
    } else if mean >= MINEABLE_MEAN_GATE {
        "DENSITY_OK_PROCEED_PHASE1".to_string()
    } else {
        "NO_SIGNAL".to_string()
    }
}

fn recommendation_for(
    enabled: bool,
    summary: &ObserverSummary,
    log_present: bool,
    log_bytes: u64,
) -> String {
    if !enabled {
        return "observer_disabled".to_string();
    }
    if !log_present || summary.per_session.is_empty() {
        return "no_observations_yet".to_string();
    }
    if log_bytes >= OBSERVER_MAX_BYTES {
        return "rotate_observer_log".to_string();
    }
    match verdict_for(
        summary.mean_clean_mineable_per_session,
        summary.per_session.len(),
    )
    .as_str()
    {
        "INSUFFICIENT_SESSIONS" => "wait_for_sessions".to_string(),
        "DENSITY_OK_PROCEED_PHASE1" => "review_before_phase1_miner".to_string(),
        _ => "do_not_build_miner".to_string(),
    }
}

fn latest_age_secs(ts: f64) -> Option<u64> {
    let now = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .ok()?
        .as_secs_f64();
    if now >= ts {
        Some((now - ts).round() as u64)
    } else {
        Some(0)
    }
}

#[cfg(unix)]
fn mode_octal(path: &Path) -> Option<String> {
    use std::os::unix::fs::PermissionsExt;
    std::fs::metadata(path)
        .ok()
        .map(|m| format!("{:03o}", m.permissions().mode() & 0o777))
}

#[cfg(not(unix))]
fn mode_octal(_path: &Path) -> Option<String> {
    None
}

fn private_dir_mode_octal(path: &Path) -> Option<String> {
    mode_octal(path)
}

fn private_file_mode_octal(path: &Path) -> Option<String> {
    mode_octal(path)
}

#[cfg(unix)]
fn observer_permissions_ok(log_dir: &Path, log_path: &Path, log_present: bool) -> bool {
    use std::os::unix::fs::PermissionsExt;

    let dir_ok = std::fs::metadata(log_dir)
        .ok()
        .map(|m| {
            let mode = m.permissions().mode() & 0o777;
            // Directory should be owner-only; execute is needed to traverse.
            mode & 0o077 == 0 && mode & 0o700 == 0o700
        })
        .unwrap_or(true);
    let file_ok = if log_present {
        std::fs::metadata(log_path)
            .ok()
            .map(|m| {
                let mode = m.permissions().mode() & 0o777;
                // JSONL may contain prompt/tool summaries; no group/other or exec bits.
                mode & 0o177 == 0 && mode & 0o600 == 0o600
            })
            .unwrap_or(true)
    } else {
        true
    };
    dir_ok && file_ok
}

#[cfg(not(unix))]
fn observer_permissions_ok(_log_dir: &Path, _log_path: &Path, _log_present: bool) -> bool {
    true
}

#[cfg(unix)]
fn is_executable(path: &Path) -> bool {
    use std::os::unix::fs::PermissionsExt;
    std::fs::metadata(path)
        .map(|m| m.permissions().mode() & 0o111 != 0)
        .unwrap_or(false)
}

#[cfg(not(unix))]
fn is_executable(path: &Path) -> bool {
    path.is_file()
}

#[cfg(test)]
mod tests {
    use super::*;

    fn write_jsonl(path: &Path, rows: &[Value]) {
        let mut text = String::new();
        for row in rows {
            text.push_str(&serde_json::to_string(row).unwrap());
            text.push('\n');
        }
        std::fs::write(path, text).unwrap();
    }

    #[test]
    fn observer_status_separates_clean_errors_from_legacy_noise() {
        let tmp = tempfile::tempdir().unwrap();
        let hook = tmp.path().join("ab-instinct-observer-hook");
        let log = tmp.path().join("observations.jsonl");
        std::fs::write(&hook, "#!/bin/sh\n").unwrap();
        write_jsonl(
            &log,
            &[
                json!({"ts": 1.0, "sid": "legacy", "ev": "PostToolUse", "tool": "Bash", "err": true}),
                json!({"ts": 2.0, "sid": "legacy", "ev": "PostToolUse", "tool": "Bash", "err": false}),
                json!({"ts": 3.0, "sid": "clean", "ev": "PostToolUse", "tool": "Bash", "err": true, "err_source": "exit_code"}),
                json!({"ts": 4.0, "sid": "clean", "ev": "PostToolUse", "tool": "Bash", "err": false}),
            ],
        );

        let status = observer_status_for_paths(hook, log, true);
        assert_eq!(status.total_clean_mineable, 1);
        assert_eq!(status.total_legacy_upper_bound_mineable, 2);
        assert_eq!(status.legacy_untrusted_errors, 1);
        assert_eq!(status.verdict, "INSUFFICIENT_SESSIONS");
        assert_eq!(status.recommendation, "wait_for_sessions");
    }

    #[cfg(unix)]
    #[test]
    fn observer_status_reports_private_sidecar_permissions() {
        use std::os::unix::fs::PermissionsExt;

        let tmp = tempfile::tempdir().unwrap();
        let hook = tmp.path().join("ab-instinct-observer-hook");
        let dir = tmp.path().join("instinct-probe");
        let log = dir.join("observations.jsonl");
        std::fs::create_dir(&dir).unwrap();
        std::fs::write(&hook, "#!/bin/sh\n").unwrap();
        write_jsonl(
            &log,
            &[json!({"ts": 1.0, "sid": "s", "ev": "UserPromptSubmit", "prompt": "hello"})],
        );
        std::fs::set_permissions(&dir, std::fs::Permissions::from_mode(0o700)).unwrap();
        std::fs::set_permissions(&log, std::fs::Permissions::from_mode(0o600)).unwrap();

        let status = observer_status_for_paths(hook.clone(), log.clone(), true);
        assert!(status.permissions_ok);
        assert_eq!(status.log_dir_mode_octal.as_deref(), Some("700"));
        assert_eq!(status.log_mode_octal.as_deref(), Some("600"));

        std::fs::set_permissions(&dir, std::fs::Permissions::from_mode(0o775)).unwrap();
        std::fs::set_permissions(&log, std::fs::Permissions::from_mode(0o664)).unwrap();
        let status = observer_status_for_paths(hook, log, true);
        assert!(!status.permissions_ok);
        assert_eq!(status.log_dir_mode_octal.as_deref(), Some("775"));
        assert_eq!(status.log_mode_octal.as_deref(), Some("664"));
    }

    #[test]
    fn observer_status_handles_missing_log_as_non_blocking() {
        let tmp = tempfile::tempdir().unwrap();
        let status = observer_status_for_paths(
            tmp.path().join("missing-hook"),
            tmp.path().join("missing.jsonl"),
            true,
        );
        assert_eq!(status.total_records, 0);
        assert_eq!(status.sessions, 0);
        assert_eq!(status.verdict, "INSUFFICIENT_SESSIONS");
        assert_eq!(status.recommendation, "no_observations_yet");
    }

    #[test]
    fn observer_status_detects_density_ok_after_five_sessions() {
        let tmp = tempfile::tempdir().unwrap();
        let hook = tmp.path().join("ab-instinct-observer-hook");
        let log = tmp.path().join("observations.jsonl");
        std::fs::write(&hook, "#!/bin/sh\n").unwrap();
        let rows: Vec<Value> = (0..5)
            .map(|idx| {
                json!({
                    "ts": idx as f64,
                    "sid": format!("s{idx}"),
                    "ev": "UserPromptSubmit",
                    "prompt": "不对，应该改成这样"
                })
            })
            .collect();
        write_jsonl(&log, &rows);

        let status = observer_status_for_paths(hook, log, true);
        assert_eq!(status.total_clean_mineable, 5);
        assert_eq!(status.mean_clean_mineable_per_session, 1.0);
        assert_eq!(status.verdict, "DENSITY_OK_PROCEED_PHASE1");
        assert_eq!(status.recommendation, "review_before_phase1_miner");
    }

    #[test]
    fn observer_log_rotation_dry_run_preserves_log() {
        let tmp = tempfile::tempdir().unwrap();
        let log = tmp.path().join("observations.jsonl");
        write_jsonl(
            &log,
            &[json!({"ts": 1.0, "sid": "s", "ev": "UserPromptSubmit", "prompt": "hello"})],
        );

        let plan = rotate_observer_log_for_path(&log, 1_780_747_000, true).unwrap();

        assert_eq!(
            plan["schema"],
            "agent_bridge_instinct_observer_log_rotation.v0"
        );
        assert_eq!(plan["dry_run"], json!(true));
        assert_eq!(plan["action"], "rotate_log");
        assert_eq!(plan["status"], "would_rotate");
        assert_eq!(plan["log_exists"], json!(true));
        assert_eq!(plan["log_bytes"].as_u64().unwrap() > 0, true);
        assert!(log.exists(), "dry-run must not move the live log");
        let archive = PathBuf::from(plan["archive_path"].as_str().unwrap());
        assert!(!archive.exists(), "dry-run must not create archive");
    }

    #[test]
    fn observer_log_rotation_moves_log_to_timestamped_archive() {
        let tmp = tempfile::tempdir().unwrap();
        let log = tmp.path().join("observations.jsonl");
        write_jsonl(
            &log,
            &[json!({"ts": 1.0, "sid": "s", "ev": "UserPromptSubmit", "prompt": "hello"})],
        );
        let original = std::fs::read_to_string(&log).unwrap();

        let plan = rotate_observer_log_for_path(&log, 1_780_747_001, false).unwrap();

        assert_eq!(
            plan["schema"],
            "agent_bridge_instinct_observer_log_rotation.v0"
        );
        assert_eq!(plan["dry_run"], json!(false));
        assert_eq!(plan["action"], "rotate_log");
        assert_eq!(plan["status"], "rotated");
        assert_eq!(plan["log_exists"], json!(true));
        assert!(!log.exists(), "rotation leaves hook to recreate live log");
        let archive = PathBuf::from(plan["archive_path"].as_str().unwrap());
        assert!(archive.exists(), "archive must be created by rename");
        assert_eq!(std::fs::read_to_string(archive).unwrap(), original);
    }
}
