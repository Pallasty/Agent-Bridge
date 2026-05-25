//! Shadow-only Seed cortex for Xiao Shu avatar events.
//!
//! This is deliberately separate from the global memory substrate. It consumes
//! avatar alert perception records, trains an isolated `SeedBackend`, and writes
//! a dedicated snapshot file for inspection.

use anyhow::{Context, Result};
use serde_json::{json, Value};
use std::collections::BTreeMap;
use std::fs::OpenOptions;
use std::io::Write;
use std::path::{Path, PathBuf};
use std::sync::Arc;

const STATUS_EVENT_LIMIT: usize = 500;

pub struct AvatarCortexReplayOptions<'a> {
    pub label: Option<&'a str>,
    pub project: Option<&'a str>,
    pub input: Option<&'a Path>,
    pub output: Option<&'a Path>,
    pub limit: usize,
    pub include_preview: bool,
    pub use_hash: bool,
    pub n: usize,
    pub d: usize,
}

pub struct AvatarCortexVoiceGateOptions<'a> {
    pub label: Option<&'a str>,
    pub heartbeat_label: Option<&'a str>,
    pub project: Option<&'a str>,
    pub output: Option<&'a Path>,
    pub preview_text: Option<&'a str>,
    pub enabled: bool,
    pub force: bool,
    pub cooldown_secs: i64,
    pub reason: Option<&'a str>,
}

pub struct AvatarCortexVoiceEmitOptions<'a> {
    pub label: Option<&'a str>,
    pub heartbeat_label: Option<&'a str>,
    pub project: Option<&'a str>,
    pub output: Option<&'a Path>,
    pub preview_text: Option<&'a str>,
    pub enabled: bool,
    pub force: bool,
    pub cooldown_secs: i64,
    pub reason: Option<&'a str>,
    pub allow_policy_override: bool,
    pub tts_voice: Option<&'a str>,
    pub tts_rate: Option<u64>,
}

#[derive(Clone, Copy)]
pub struct AvatarCortexVoiceActionOptions<'a> {
    pub label: Option<&'a str>,
    pub heartbeat_label: Option<&'a str>,
    pub project: Option<&'a str>,
    pub output: Option<&'a Path>,
    pub requested_track: Option<&'a str>,
    pub reason: Option<&'a str>,
    pub confirm: bool,
    pub emit: bool,
    pub force: bool,
    pub cooldown_secs: i64,
    pub tts_voice: Option<&'a str>,
    pub tts_rate: Option<u64>,
}

#[derive(Clone, Copy)]
pub struct AvatarCortexVoiceActionPreviewOptions<'a> {
    pub label: Option<&'a str>,
    pub heartbeat_label: Option<&'a str>,
    pub project: Option<&'a str>,
    pub output: Option<&'a Path>,
    pub requested_track: Option<&'a str>,
    pub reason: Option<&'a str>,
    pub confirm: bool,
    pub force: bool,
    pub cooldown_secs: i64,
    pub tts_voice: Option<&'a str>,
    pub tts_rate: Option<u64>,
}

#[derive(Clone, Copy)]
pub struct XiaoShuActionRequestOptions<'a> {
    pub label: Option<&'a str>,
    pub heartbeat_label: Option<&'a str>,
    pub project: Option<&'a str>,
    pub output: Option<&'a Path>,
    pub actor: Option<&'a str>,
    pub intent: Option<&'a str>,
    pub message: Option<&'a str>,
    pub requested_track: Option<&'a str>,
    pub reason: Option<&'a str>,
    pub confirm: bool,
    pub force: bool,
    pub cooldown_secs: i64,
    pub tts_voice: Option<&'a str>,
    pub tts_rate: Option<u64>,
    pub include_details: bool,
}

#[derive(Clone, Copy)]
pub struct XiaoShuActionRequestQueueOptions<'a> {
    pub project: Option<&'a str>,
    pub request_id: Option<&'a str>,
    pub state: Option<&'a str>,
    pub include_all_states: bool,
    pub include_details: bool,
    pub limit: usize,
}

#[derive(Clone, Copy)]
pub struct XiaoShuActionRequestActionOptions<'a> {
    pub label: Option<&'a str>,
    pub heartbeat_label: Option<&'a str>,
    pub project: Option<&'a str>,
    pub output: Option<&'a Path>,
    pub request_id: Option<&'a str>,
    pub reason: Option<&'a str>,
    pub confirm: bool,
    pub emit: bool,
    pub dismiss: bool,
    pub force: bool,
    pub cooldown_secs: i64,
    pub tts_voice: Option<&'a str>,
    pub tts_rate: Option<u64>,
}

#[derive(Clone, Copy)]
pub struct AvatarCortexReviewRecordOptions<'a> {
    pub label: Option<&'a str>,
    pub heartbeat_label: Option<&'a str>,
    pub project: Option<&'a str>,
    pub output: Option<&'a Path>,
    pub requested_track: Option<&'a str>,
    pub requested_variant: Option<&'a str>,
    pub outcome: Option<&'a str>,
    pub reviewer: Option<&'a str>,
    pub reason: Option<&'a str>,
    pub notes: &'a [String],
    pub confirm: bool,
}

fn home_dir() -> Result<PathBuf> {
    std::env::var_os("HOME")
        .map(PathBuf::from)
        .ok_or_else(|| anyhow::anyhow!("HOME is not set"))
}

fn label_component(value: &str) -> String {
    let mut out = String::new();
    for ch in value.chars() {
        if ch.is_ascii_alphanumeric() || matches!(ch, '-' | '_' | '.') {
            out.push(ch.to_ascii_lowercase());
        } else if ch.is_whitespace() {
            out.push('-');
        }
    }
    let out = out.trim_matches(['-', '.', '_']).to_string();
    if out.is_empty() {
        "default".to_string()
    } else {
        out
    }
}

pub fn default_avatar_cortex_path(project: &str, label: &str) -> Result<PathBuf> {
    Ok(home_dir()?
        .join(".local")
        .join("share")
        .join("agent-bridge")
        .join("avatar_cortex")
        .join(label_component(project))
        .join(format!("{}.parquet", label_component(label))))
}

fn avatar_cortex_voice_dir() -> Result<PathBuf> {
    Ok(home_dir()?
        .join("Library")
        .join("Application Support")
        .join("agent-bridge")
        .join("avatar_cortex_voice"))
}

fn avatar_cortex_action_request_dir() -> Result<PathBuf> {
    Ok(home_dir()?
        .join("Library")
        .join("Application Support")
        .join("agent-bridge")
        .join("avatar_cortex_action_requests"))
}

fn avatar_cortex_review_record_dir() -> Result<PathBuf> {
    Ok(home_dir()?
        .join("Library")
        .join("Application Support")
        .join("agent-bridge")
        .join("avatar_cortex_reviews"))
}

fn avatar_cortex_voice_paths(project: &str, heartbeat_label: &str) -> Result<(PathBuf, PathBuf)> {
    let dir = avatar_cortex_voice_dir()?.join(label_component(project));
    let slug = label_component(heartbeat_label);
    Ok((
        dir.join(format!("{slug}.voice.json")),
        dir.join(format!("{slug}.events.jsonl")),
    ))
}

fn xiao_shu_action_request_queue_path(project: &str) -> Result<PathBuf> {
    Ok(avatar_cortex_action_request_dir()?
        .join(label_component(project))
        .join("requests.jsonl"))
}

fn avatar_cortex_review_record_path(project: &str) -> Result<PathBuf> {
    Ok(avatar_cortex_review_record_dir()?
        .join(label_component(project))
        .join("review_records.jsonl"))
}

pub fn cortex_runner_label(label: Option<&str>, project: &str) -> String {
    label
        .map(str::trim)
        .filter(|s| !s.is_empty())
        .map(ToString::to_string)
        .unwrap_or_else(|| format!("com.agentbridge.avatar-cortex.{}", label_component(project)))
}

fn now_secs() -> i64 {
    std::time::SystemTime::now()
        .duration_since(std::time::UNIX_EPOCH)
        .map(|d| d.as_secs() as i64)
        .unwrap_or(0)
}

fn fnv1a_hex16(value: &str) -> String {
    let mut hash: u64 = 14695981039346656037;
    for byte in value.as_bytes() {
        hash ^= *byte as u64;
        hash = hash.wrapping_mul(1099511628211);
    }
    format!("{hash:016x}")
}

fn records(value: &Value) -> &[Value] {
    value
        .get("records")
        .and_then(Value::as_array)
        .map(Vec::as_slice)
        .unwrap_or(&[])
}

fn vstr(value: Option<&Value>) -> Option<&str> {
    value.and_then(Value::as_str)
}

fn vi64(value: Option<&Value>) -> Option<i64> {
    value.and_then(|v| v.as_i64().or_else(|| v.as_u64().map(|n| n as i64)))
}

fn vbool(value: Option<&Value>) -> Option<bool> {
    value.and_then(Value::as_bool)
}

fn read_json(path: &Path) -> Value {
    std::fs::read_to_string(path)
        .ok()
        .and_then(|s| serde_json::from_str(&s).ok())
        .unwrap_or(Value::Null)
}

fn write_json(path: &Path, value: &Value) -> Result<()> {
    if let Some(parent) = path.parent() {
        std::fs::create_dir_all(parent).with_context(|| format!("create {}", parent.display()))?;
    }
    std::fs::write(path, serde_json::to_vec_pretty(value)?)
        .with_context(|| format!("write {}", path.display()))
}

fn append_jsonl(path: &Path, value: &Value) -> Result<()> {
    if let Some(parent) = path.parent() {
        std::fs::create_dir_all(parent).with_context(|| format!("create {}", parent.display()))?;
    }
    let mut file = OpenOptions::new()
        .create(true)
        .append(true)
        .open(path)
        .with_context(|| format!("open {}", path.display()))?;
    writeln!(file, "{}", serde_json::to_string(value)?)
        .with_context(|| format!("append {}", path.display()))
}

fn read_jsonl_records(path: &Path) -> Result<Vec<Value>> {
    if !path.exists() {
        return Ok(Vec::new());
    }
    let body = std::fs::read_to_string(path).with_context(|| format!("read {}", path.display()))?;
    let mut records = Vec::new();
    for (idx, line) in body.lines().enumerate() {
        let line = line.trim();
        if line.is_empty() {
            continue;
        }
        let value: Value = serde_json::from_str(line)
            .with_context(|| format!("parse {} line {}", path.display(), idx + 1))?;
        records.push(value);
    }
    Ok(records)
}

fn feed_record(backend: &ab_seed_bridge::SeedBackend, record: &Value) -> Option<(String, String)> {
    let text = vstr(record.get("text"))?;
    let key = vstr(record.get("key")).unwrap_or(text);
    if text.trim().is_empty() || key.trim().is_empty() {
        return None;
    }
    let _ = ab_store::embedding::EmbeddingBackend::perceive(backend, text, key);
    Some((text.to_string(), key.to_string()))
}

fn avatar_cortex_events_summary_from_seed(seed_payload: &Value) -> Value {
    let mut status_counts: BTreeMap<String, usize> = BTreeMap::new();
    let mut reason_counts: BTreeMap<String, usize> = BTreeMap::new();
    let mut emitted_count = 0usize;
    let mut should_emit_count = 0usize;
    let mut unhealthy_count = 0usize;
    let mut latest: Option<&Value> = None;
    for record in records(seed_payload) {
        let avatar = record.get("avatar").unwrap_or(&Value::Null);
        let status = vstr(avatar.get("status")).unwrap_or("unknown");
        let reason = vstr(avatar.get("reason")).unwrap_or("unknown");
        *status_counts.entry(status.to_string()).or_default() += 1;
        *reason_counts.entry(reason.to_string()).or_default() += 1;
        if vbool(avatar.get("emitted")).unwrap_or(false) {
            emitted_count += 1;
        }
        if vbool(avatar.get("should_emit")).unwrap_or(false) {
            should_emit_count += 1;
        }
        if vbool(avatar.get("healthy")) == Some(false) {
            unhealthy_count += 1;
        }
        latest = Some(record);
    }

    let recent: Vec<Value> = records(seed_payload)
        .iter()
        .rev()
        .take(5)
        .rev()
        .map(|record| {
            let avatar = record.get("avatar").unwrap_or(&Value::Null);
            json!({
                "ts": vi64(record.get("ts")),
                "status": avatar.get("status").cloned().unwrap_or(Value::Null),
                "healthy": avatar.get("healthy").cloned().unwrap_or(Value::Null),
                "reason": avatar.get("reason").cloned().unwrap_or(Value::Null),
                "event_key": avatar.get("event_key").cloned().unwrap_or(Value::Null),
                "should_emit": avatar.get("should_emit").cloned().unwrap_or(Value::Null),
                "emitted": avatar.get("emitted").cloned().unwrap_or(Value::Null),
            })
        })
        .collect();

    let latest = latest.map(|record| {
        let avatar = record.get("avatar").unwrap_or(&Value::Null);
        json!({
            "ts": vi64(record.get("ts")),
            "status": avatar.get("status").cloned().unwrap_or(Value::Null),
            "healthy": avatar.get("healthy").cloned().unwrap_or(Value::Null),
            "reason": avatar.get("reason").cloned().unwrap_or(Value::Null),
            "event_key": avatar.get("event_key").cloned().unwrap_or(Value::Null),
            "should_emit": avatar.get("should_emit").cloned().unwrap_or(Value::Null),
            "emitted": avatar.get("emitted").cloned().unwrap_or(Value::Null),
        })
    });

    json!({
        "source": "avatar seed-events",
        "events_path": seed_payload.get("events_path").cloned().unwrap_or(Value::Null),
        "include_preview": seed_payload.get("include_preview").cloned().unwrap_or(Value::Null),
        "limit": seed_payload.get("limit").cloned().unwrap_or(Value::Null),
        "events_seen": seed_payload.get("events_seen").cloned().unwrap_or(Value::Null),
        "records_count": seed_payload.get("records_count").cloned().unwrap_or(Value::Null),
        "window_records": records(seed_payload).len(),
        "parse_skips": seed_payload.get("parse_skips").cloned().unwrap_or(Value::Null),
        "surface_skips": seed_payload.get("surface_skips").cloned().unwrap_or(Value::Null),
        "preview_skips": seed_payload.get("preview_skips").cloned().unwrap_or(Value::Null),
        "status_counts": status_counts,
        "reason_counts": reason_counts,
        "emitted_count": emitted_count,
        "should_emit_count": should_emit_count,
        "unhealthy_count": unhealthy_count,
        "latest": latest.unwrap_or(Value::Null),
        "recent": recent,
    })
}

fn avatar_cortex_events_summary(label: &str, project: &str) -> Value {
    let opts = crate::avatar_seed::AvatarSeedEventsOptions {
        label: Some(label),
        project: Some(project),
        input: None,
        limit: STATUS_EVENT_LIMIT,
        include_preview: false,
    };
    match crate::avatar_seed::avatar_seed_events(&opts) {
        Ok(seed_payload) => avatar_cortex_events_summary_from_seed(&seed_payload),
        Err(err) => json!({
            "source": "avatar seed-events",
            "events_path": crate::avatar_seed::avatar_alert_events_path(label)
                .ok()
                .map(|p| p.to_string_lossy().to_string()),
            "limit": STATUS_EVENT_LIMIT,
            "records_count": 0,
            "window_records": 0,
            "latest": Value::Null,
            "recent": [],
            "error": err.to_string(),
        }),
    }
}

fn avatar_cortex_trend(snapshot: &Value, events: &Value) -> Value {
    let latest_long = snapshot.get("latest_long").unwrap_or(&Value::Null);
    let snapshot_step = vi64(latest_long.get("step"));
    let snapshot_cycle_ts = vi64(latest_long.get("cycle_ts"));
    let records_count = vi64(events.get("records_count"));
    let latest_event_ts = events.get("latest").and_then(|v| vi64(v.get("ts")));
    let step_records_delta = match (snapshot_step, records_count) {
        (Some(step), Some(records)) => Some(step - records),
        _ => None,
    };
    let snapshot_event_lag_secs = match (snapshot_cycle_ts, latest_event_ts) {
        (Some(snapshot_ts), Some(event_ts)) => Some(snapshot_ts.saturating_sub(event_ts)),
        _ => None,
    };
    let learning_state = avatar_cortex_learning_state(
        snapshot_step,
        records_count,
        step_records_delta,
        snapshot_event_lag_secs,
        latest_event_ts,
    );
    let behavior_policy =
        avatar_cortex_behavior_policy(&learning_state, step_records_delta, snapshot_event_lag_secs);
    json!({
        "snapshot_step": snapshot_step,
        "records_count": records_count,
        "step_records_delta": step_records_delta,
        "step_matches_records": step_records_delta.map(|d| d == 0),
        "latest_event_ts": latest_event_ts,
        "snapshot_cycle_ts": snapshot_cycle_ts,
        "snapshot_event_lag_secs": snapshot_event_lag_secs,
        "latest_status": events.get("latest").and_then(|v| v.get("status")).cloned().unwrap_or(Value::Null),
        "latest_healthy": events.get("latest").and_then(|v| v.get("healthy")).cloned().unwrap_or(Value::Null),
        "learning_state": learning_state,
        "behavior_policy": behavior_policy,
    })
}

fn avatar_cortex_learning_state(
    snapshot_step: Option<i64>,
    records_count: Option<i64>,
    step_records_delta: Option<i64>,
    snapshot_event_lag_secs: Option<i64>,
    latest_event_ts: Option<i64>,
) -> Value {
    let no_events = latest_event_ts.is_none() || records_count.unwrap_or(0) == 0;
    let (state, reason, severity, summary) = if no_events {
        (
            "stale",
            "no_events",
            "warning",
            "no avatar health events are available for the cortex window",
        )
    } else if snapshot_step.is_none() {
        (
            "stale",
            "no_snapshot",
            "warning",
            "avatar events exist but no cortex snapshot has been written yet",
        )
    } else if step_records_delta == Some(0) && snapshot_event_lag_secs.unwrap_or(0) >= 0 {
        (
            "caught_up",
            "step_matches_records",
            "ok",
            "shadow cortex is caught up with the avatar event window",
        )
    } else if step_records_delta.is_some_and(|delta| delta < 0)
        || snapshot_event_lag_secs.is_some_and(|lag| lag < 0)
    {
        (
            "learning",
            "events_ahead_of_snapshot",
            "info",
            "new avatar events are waiting for the cortex runner to replay",
        )
    } else if step_records_delta.is_some_and(|delta| delta > 0) {
        (
            "behind",
            "snapshot_ahead_of_event_window",
            "warning",
            "cortex snapshot step is ahead of the currently visible event window",
        )
    } else {
        (
            "stale",
            "insufficient_timing",
            "warning",
            "not enough timing data to classify cortex learning progress",
        )
    };
    json!({
        "state": state,
        "reason": reason,
        "severity": severity,
        "summary": summary,
    })
}

fn avatar_cortex_behavior_policy(
    learning_state: &Value,
    step_records_delta: Option<i64>,
    snapshot_event_lag_secs: Option<i64>,
) -> Value {
    let state = vstr(learning_state.get("state")).unwrap_or("stale");
    let reason = vstr(learning_state.get("reason")).unwrap_or("unknown");
    let (badge, panel_hint, recommended_action) = match state {
        "caught_up" => (
            "caught up",
            "shadow cortex has replayed the current avatar event window",
            "none",
        ),
        "learning" => (
            "learning",
            "new avatar events are queued for the cortex runner",
            "wait_for_cortex_runner",
        ),
        "behind" => (
            "check window",
            "snapshot step is ahead of the visible event window",
            "inspect_event_window",
        ),
        _ => (
            "stale",
            "cortex learning progress needs fresh events and a snapshot",
            "inspect_cortex_status",
        ),
    };
    json!({
        "schema": 1,
        "state": state,
        "reason": reason,
        "badge": badge,
        "panel_hint": panel_hint,
        "recommended_action": recommended_action,
        "step_records_delta": step_records_delta,
        "snapshot_event_lag_secs": snapshot_event_lag_secs,
        "voice": {
            "allowed": false,
            "preview": match state {
                "caught_up" => "小舒已追上最新事件。",
                "learning" => "小舒正在吸收新事件。",
                "behind" => "小舒的事件窗口需要检查。",
                _ => "小舒的皮质层状态需要刷新。",
            },
            "reason": "sparse_voice_policy",
        },
        "notification": {
            "allowed": false,
            "reason": "read_only_panel_policy",
        },
    })
}

fn avatar_cortex_language_memory(events: &Value) -> Value {
    let recent = events
        .get("recent")
        .and_then(Value::as_array)
        .cloned()
        .unwrap_or_default();
    let window_size = recent.len();
    let mut healthy_count = 0usize;
    let mut unhealthy_count = 0usize;
    let mut stable_count = 0usize;
    let mut transition_count = 0usize;
    let mut previous_signature: Option<String> = None;

    for record in &recent {
        let status = vstr(record.get("status")).unwrap_or("unknown");
        let reason = vstr(record.get("reason")).unwrap_or("unknown");
        if vbool(record.get("healthy")) == Some(false) || status != "healthy" {
            unhealthy_count += 1;
        } else {
            healthy_count += 1;
        }
        if status == "healthy" && reason == "unchanged" {
            stable_count += 1;
        }
        let signature = format!("{status}:{reason}");
        if previous_signature
            .as_ref()
            .is_some_and(|previous| previous != &signature)
        {
            transition_count += 1;
        }
        previous_signature = Some(signature);
    }

    let first = recent.first().unwrap_or(&Value::Null);
    let latest = recent.last().unwrap_or(&Value::Null);
    let first_status = vstr(first.get("status")).unwrap_or("unknown");
    let latest_status = vstr(latest.get("status")).unwrap_or("unknown");
    let first_reason = vstr(first.get("reason")).unwrap_or("unknown");
    let latest_reason = vstr(latest.get("reason")).unwrap_or("unknown");
    let observation = if window_size == 0 {
        "no_recent_events"
    } else if unhealthy_count > 0 {
        "recent_unhealthy_signal"
    } else if transition_count > 0 {
        "recent_transition"
    } else if stable_count == window_size {
        "stable_recent_window"
    } else {
        "mixed_recent_window"
    };
    let clause = match observation {
        "stable_recent_window" => "小舒记得最近几次信号都很稳。",
        "recent_transition" => "小舒记得刚才有过状态切换。",
        "recent_unhealthy_signal" => "小舒记得最近几次里有异常信号。",
        "mixed_recent_window" => "小舒记得最近几次信号还在变化。",
        _ => "",
    };
    let summary = match observation {
        "stable_recent_window" => "recent window is stable",
        "recent_transition" => "recent window contains a transition",
        "recent_unhealthy_signal" => "recent window contains an unhealthy signal",
        "mixed_recent_window" => "recent window is mixed",
        _ => "no recent event window",
    };

    json!({
        "schema": 1,
        "kind": "short_event_window",
        "read_only": true,
        "writes_persistent_memory": false,
        "window_size": window_size,
        "healthy_count": healthy_count,
        "unhealthy_count": unhealthy_count,
        "stable_count": stable_count,
        "transition_count": transition_count,
        "observation": observation,
        "summary": summary,
        "clause": clause,
        "first": {
            "ts": vi64(first.get("ts")),
            "status": first_status,
            "reason": first_reason,
        },
        "latest": {
            "ts": vi64(latest.get("ts")),
            "status": latest_status,
            "reason": latest_reason,
        },
        "recent": recent,
    })
}

pub(crate) fn avatar_cortex_language_preview_from_status(status: Value) -> Value {
    let trend = status.get("trend").unwrap_or(&Value::Null);
    let learning = trend.get("learning_state").unwrap_or(&Value::Null);
    let events = status.get("events").unwrap_or(&Value::Null);
    let latest = events.get("latest").unwrap_or(&Value::Null);
    let project = vstr(status.get("project")).unwrap_or("agent-bridge");
    let state = vstr(learning.get("state")).unwrap_or("stale");
    let reason = vstr(learning.get("reason")).unwrap_or("unknown");
    let latest_status = vstr(latest.get("status")).unwrap_or("unknown");
    let latest_reason = vstr(latest.get("reason")).unwrap_or("unknown");
    let records_count = vi64(events.get("records_count"));
    let unhealthy_count = vi64(events.get("unhealthy_count")).unwrap_or(0);
    let step_records_delta = vi64(trend.get("step_records_delta"));
    let snapshot_event_lag_secs = vi64(trend.get("snapshot_event_lag_secs"));
    let memory = avatar_cortex_language_memory(events);
    let recent_unhealthy_count = vi64(memory.get("unhealthy_count")).unwrap_or(0);

    let intent = match state {
        "caught_up" if latest_status == "healthy" => "reassure",
        "caught_up" => "settled",
        "learning" => "processing",
        "behind" => "inspect",
        _ => "refresh",
    };
    let opener = match state {
        "caught_up" => "小舒追上啦，",
        "learning" => "小舒正在整理新事件，",
        "behind" => "小舒发现事件窗口有点不齐，",
        _ => "小舒还在找最新状态，",
    };
    let state_clause = match (state, latest_status, unhealthy_count > 0) {
        ("caught_up", "healthy", false) => "当前信号是健康的。",
        ("caught_up", "healthy", true) if recent_unhealthy_count == 0 => "当前信号是健康的。",
        ("caught_up", _, true) => "还有健康信号需要留意。",
        ("learning", _, _) => "先把变化叠进自己的皮质层。",
        ("behind", _, _) => "需要看一下快照和事件的顺序。",
        _ => "需要刷新后再判断。",
    };
    let mut context_clauses: Vec<String> = Vec::new();
    if let Some(clause) = vstr(memory.get("clause")).filter(|s| !s.is_empty()) {
        context_clauses.push(clause.to_string());
    }
    if reason == "events_ahead_of_snapshot" {
        context_clauses.push("新事件已经排队。".to_string());
    } else if latest_reason == "transition" {
        context_clauses.push("刚刚发生过一次状态切换。".to_string());
    } else if latest_reason == "unchanged" {
        context_clauses.push("最近状态保持稳定。".to_string());
    }
    let context_clause = if context_clauses.is_empty() {
        String::new()
    } else {
        format!(" {}", context_clauses.join(" "))
    };
    let next_hint = match state {
        "caught_up" => " 我会继续安静观察。",
        "learning" => " 等 runner 追上就好。",
        "behind" => " 建议检查事件窗口。",
        _ => " 建议刷新 cortex 状态。",
    };
    let utterance = format!("{opener}{state_clause}{context_clause}{next_hint}");
    let alternatives = match state {
        "caught_up" => vec![
            "小舒已经把最新事件收好啦。",
            "当前状态稳定，小舒继续安静守着。",
            "皮质层已追上，小舒会继续观察。",
        ],
        "learning" => vec![
            "小舒正在吸收新事件，马上跟上。",
            "新信号到了，小舒先整理一下。",
            "小舒在更新自己的小皮质层。",
        ],
        "behind" => vec![
            "事件窗口有点错位，小舒建议检查一下。",
            "快照跑在窗口前面了，需要看一眼。",
            "小舒需要对齐事件和快照。",
        ],
        _ => vec![
            "小舒还没有足够的新状态。",
            "小舒需要刷新后再判断。",
            "状态有点旧，小舒先保持安静。",
        ],
    };

    json!({
        "surface": "avatar_cortex_language_preview",
        "schema": 1,
        "read_only": true,
        "emits_audio": false,
        "emits_notification": false,
        "mutates_global_substrate": false,
        "project": status.get("project").cloned().unwrap_or(Value::Null),
        "label": status.get("label").cloned().unwrap_or(Value::Null),
        "heartbeat_label": status.get("heartbeat_label").cloned().unwrap_or(Value::Null),
        "language": {
            "schema": 1,
            "locale": "zh-CN",
            "style": "xiao_shu_bright_childlike",
            "intent": intent,
            "utterance": utterance,
            "alternatives": alternatives,
            "memory": memory,
            "slots": {
                "project": project,
                "state": state,
                "reason": reason,
                "latest_status": latest_status,
                "latest_reason": latest_reason,
                "records_count": records_count,
                "unhealthy_count": unhealthy_count,
                "step_records_delta": step_records_delta,
                "snapshot_event_lag_secs": snapshot_event_lag_secs,
            },
            "generator": {
                "kind": "deterministic_phrase_composer",
                "version": 1,
                "uses_llm": false,
                "uses_voice_model": false,
            },
            "safety": {
                "requires_explicit_emit_gate": true,
                "voice_allowed": false,
                "notification_allowed": false,
                "reason": "language_preview_only",
            },
        },
        "learning_state": learning.clone(),
        "source_status": {
            "surface": status.get("surface").cloned().unwrap_or(Value::Null),
            "launchd": status.get("launchd").cloned().unwrap_or(Value::Null),
            "snapshot": status.get("snapshot").cloned().unwrap_or(Value::Null),
            "events": status.get("events").cloned().unwrap_or(Value::Null),
            "trend": trend.clone(),
        }
    })
}

pub fn avatar_cortex_language_preview(
    label: Option<&str>,
    heartbeat_label: Option<&str>,
    project: Option<&str>,
    output: Option<&Path>,
) -> Result<Value> {
    let status = avatar_cortex_status(label, heartbeat_label, project, output)?;
    Ok(avatar_cortex_language_preview_from_status(status))
}

pub(crate) fn avatar_cortex_motion_preview_from_status(status: Value) -> Value {
    let language_preview = avatar_cortex_language_preview_from_status(status.clone());
    let language = language_preview
        .get("language")
        .cloned()
        .unwrap_or(Value::Null);
    let slots = language.get("slots").unwrap_or(&Value::Null);
    let memory = language.get("memory").unwrap_or(&Value::Null);
    let learning = language_preview
        .get("learning_state")
        .cloned()
        .unwrap_or(Value::Null);
    let state = vstr(slots.get("state")).unwrap_or("stale");
    let latest_status = vstr(slots.get("latest_status")).unwrap_or("unknown");
    let memory_observation = vstr(memory.get("observation")).unwrap_or("no_recent_events");

    let (gesture, mood, attention, animation_loop, intensity, reason) =
        if memory_observation == "recent_unhealthy_signal" {
            (
                "alert_peek",
                "concerned",
                "health_signal",
                "alert_peek",
                "medium",
                "recent_unhealthy_signal",
            )
        } else if state == "caught_up"
            && latest_status == "healthy"
            && memory_observation == "stable_recent_window"
        {
            (
                "caught_up_bounce",
                "bright",
                "steady_watch",
                "soft_bounce",
                "low",
                "caught_up_stable_window",
            )
        } else {
            match state {
                "caught_up" => (
                    "settled_watch",
                    "calm",
                    "steady_watch",
                    "idle_breathe",
                    "low",
                    "caught_up",
                ),
                "learning" => (
                    "sorting_stack",
                    "focused",
                    "event_queue",
                    "sorting_glow",
                    "medium",
                    "events_waiting_for_runner",
                ),
                "behind" => (
                    "inspect_tilt",
                    "alert",
                    "window_check",
                    "look_sideways",
                    "medium",
                    "snapshot_ahead_of_window",
                ),
                _ => (
                    "quiet_listening",
                    "calm",
                    "refresh_wait",
                    "idle_breathe",
                    "low",
                    "insufficient_fresh_state",
                ),
            }
        };

    json!({
        "surface": "avatar_cortex_motion_preview",
        "schema": 1,
        "read_only": true,
        "emits_audio": false,
        "emits_notification": false,
        "mutates_global_substrate": false,
        "project": status.get("project").cloned().unwrap_or(Value::Null),
        "label": status.get("label").cloned().unwrap_or(Value::Null),
        "heartbeat_label": status.get("heartbeat_label").cloned().unwrap_or(Value::Null),
        "motion": {
            "schema": 1,
            "gesture": gesture,
            "mood": mood,
            "attention": attention,
            "reason": reason,
            "animation_hint": {
                "loop": animation_loop,
                "intensity": intensity,
                "duration_ms": 1800,
                "renderer_token": format!("xiao_shu::{animation_loop}::{intensity}"),
            },
            "source": {
                "state": state,
                "latest_status": latest_status,
                "memory_observation": memory_observation,
                "language_intent": language.get("intent").cloned().unwrap_or(Value::Null),
                "memory_window": memory.get("window_size").cloned().unwrap_or(Value::Null),
                "transition_count": memory.get("transition_count").cloned().unwrap_or(Value::Null),
            },
            "safety": {
                "read_only": true,
                "sidecar_only": true,
                "requires_renderer_mapping": true,
                "codex_pet_package_mutation": false,
                "emits_audio": false,
                "emits_notification": false,
            },
        },
        "language": language,
        "learning_state": learning,
        "source_status": {
            "surface": status.get("surface").cloned().unwrap_or(Value::Null),
            "launchd": status.get("launchd").cloned().unwrap_or(Value::Null),
            "snapshot": status.get("snapshot").cloned().unwrap_or(Value::Null),
            "events": status.get("events").cloned().unwrap_or(Value::Null),
            "trend": status.get("trend").cloned().unwrap_or(Value::Null),
        }
    })
}

pub fn avatar_cortex_motion_preview(
    label: Option<&str>,
    heartbeat_label: Option<&str>,
    project: Option<&str>,
    output: Option<&Path>,
) -> Result<Value> {
    let status = avatar_cortex_status(label, heartbeat_label, project, output)?;
    Ok(avatar_cortex_motion_preview_from_status(status))
}

fn avatar_cortex_renderer_mapping(renderer_token: &str) -> Value {
    let (resolved, pose_slot, expression_slot, motion_slot, accessory_slot, timeline, note) =
        match renderer_token {
            "xiao_shu::soft_bounce::low" => (
                true,
                "upright_ready",
                "bright_smile",
                "soft_bounce",
                "none",
                json!([
                    {"at_ms": 0, "slot": "pose", "value": "upright_ready"},
                    {"at_ms": 200, "slot": "expression", "value": "bright_smile"},
                    {"at_ms": 400, "slot": "motion", "value": "soft_bounce"},
                    {"at_ms": 1800, "slot": "motion", "value": "idle_breathe"}
                ]),
                "stable caught-up state can become a small cheerful bounce",
            ),
            "xiao_shu::idle_breathe::low" => (
                true,
                "neutral_idle",
                "calm_eyes",
                "idle_breathe",
                "none",
                json!([
                    {"at_ms": 0, "slot": "pose", "value": "neutral_idle"},
                    {"at_ms": 150, "slot": "expression", "value": "calm_eyes"},
                    {"at_ms": 300, "slot": "motion", "value": "idle_breathe"}
                ]),
                "settled or stale state should remain quiet and legible",
            ),
            "xiao_shu::sorting_glow::medium" => (
                true,
                "lean_forward",
                "focused_eyes",
                "sorting_glow",
                "soft_status_glow",
                json!([
                    {"at_ms": 0, "slot": "pose", "value": "lean_forward"},
                    {"at_ms": 180, "slot": "expression", "value": "focused_eyes"},
                    {"at_ms": 360, "slot": "accessory", "value": "soft_status_glow"},
                    {"at_ms": 540, "slot": "motion", "value": "sorting_glow"}
                ]),
                "learning state can show quiet focused sorting",
            ),
            "xiao_shu::look_sideways::medium" => (
                true,
                "inspect_tilt",
                "checking_eyes",
                "look_sideways",
                "none",
                json!([
                    {"at_ms": 0, "slot": "pose", "value": "inspect_tilt"},
                    {"at_ms": 200, "slot": "expression", "value": "checking_eyes"},
                    {"at_ms": 420, "slot": "motion", "value": "look_sideways"}
                ]),
                "window mismatch should read as inspection, not alarm",
            ),
            "xiao_shu::alert_peek::medium" => (
                true,
                "peek_forward",
                "concerned_eyes",
                "alert_peek",
                "small_attention_mark",
                json!([
                    {"at_ms": 0, "slot": "pose", "value": "peek_forward"},
                    {"at_ms": 160, "slot": "expression", "value": "concerned_eyes"},
                    {"at_ms": 320, "slot": "accessory", "value": "small_attention_mark"},
                    {"at_ms": 480, "slot": "motion", "value": "alert_peek"}
                ]),
                "recent unhealthy signal should request attention without panic",
            ),
            _ => (
                false,
                "neutral_idle",
                "calm_eyes",
                "idle_breathe",
                "none",
                json!([
                    {"at_ms": 0, "slot": "pose", "value": "neutral_idle"},
                    {"at_ms": 150, "slot": "expression", "value": "calm_eyes"},
                    {"at_ms": 300, "slot": "motion", "value": "idle_breathe"}
                ]),
                "unknown renderer token falls back to neutral idle",
            ),
        };
    let evidence = match renderer_token {
        "xiao_shu::soft_bounce::low" => json!({
            "schema": 1,
            "binding_stage": "candidate",
            "risk_level": "low",
            "visual_intent": "show a small cheerful confirmation when Xiao Shu is caught up and recent signals are stable",
            "acceptance_criteria": [
                "reads as happy but not celebratory",
                "returns to idle within two seconds",
                "does not distract from the terminal or panel content"
            ],
            "risk_notes": "avoid repeating the bounce too frequently during stable heartbeat loops",
            "review_questions": [
                "does the bounce still feel calm after several panel refreshes",
                "is the smile visible at desktop pet size"
            ],
            "recommended_next_step": "safe candidate for first manual renderer binding"
        }),
        "xiao_shu::idle_breathe::low" => json!({
            "schema": 1,
            "binding_stage": "candidate",
            "risk_level": "low",
            "visual_intent": "keep Xiao Shu present without implying work or urgency",
            "acceptance_criteria": [
                "motion is barely noticeable during long idle periods",
                "expression remains neutral and friendly",
                "loop can run repeatedly without visual fatigue"
            ],
            "risk_notes": "too much movement would make idle feel needy",
            "review_questions": [
                "does idle remain comfortable beside a coding session",
                "does it preserve the official pet silhouette"
            ],
            "recommended_next_step": "bind after soft_bounce baseline is accepted"
        }),
        "xiao_shu::sorting_glow::medium" => json!({
            "schema": 1,
            "binding_stage": "needs_review",
            "risk_level": "medium",
            "visual_intent": "show quiet concentration while cortex events are waiting for replay",
            "acceptance_criteria": [
                "reads as focused sorting, not error handling",
                "glow is subtle enough for repeated background use",
                "the pose suggests attention without blocking interaction"
            ],
            "risk_notes": "glow or forward lean can look like a warning if too bright",
            "review_questions": [
                "does the glow imply urgency",
                "does the state remain understandable without text"
            ],
            "recommended_next_step": "prototype after stable idle and bounce slots exist"
        }),
        "xiao_shu::look_sideways::medium" => json!({
            "schema": 1,
            "binding_stage": "needs_review",
            "risk_level": "medium",
            "visual_intent": "suggest inspection when snapshot and event windows are misaligned",
            "acceptance_criteria": [
                "reads as checking rather than confused",
                "does not imply user error",
                "returns to neutral if the next cortex pass catches up"
            ],
            "risk_notes": "sideways look can feel uncertain if expression is too strong",
            "review_questions": [
                "is inspection distinguishable from alert_peek",
                "does it feel supportive rather than worried"
            ],
            "recommended_next_step": "prototype only after mismatch states are common enough to judge"
        }),
        "xiao_shu::alert_peek::medium" => json!({
            "schema": 1,
            "binding_stage": "needs_review",
            "risk_level": "medium",
            "visual_intent": "request attention for recent unhealthy signals without sounding alarmed",
            "acceptance_criteria": [
                "communicates attention needed in one glance",
                "stays gentle and non-panicked",
                "attention mark is muted enough for repeated desktop use",
                "shape can feel slightly thicker without becoming heavy",
                "does not trigger unless the recent window contains an unhealthy signal"
            ],
            "risk_notes": "attention mark can become noisy if health flaps",
            "review_questions": [
                "is the attention mark too loud",
                "does the revised silhouette feel warmer and less toy-like",
                "should this ever pair with sparse voice output"
            ],
            "latest_human_feedback": {
                "source": "desktop_visual_review_2026_05_22_sidecar_peek_v4",
                "outcome": "accept_visual_motion_candidate",
                "notes": [
                    "sidecar_peek_v2_is_clear_raised_hand_motion_baseline",
                    "sidecar_peek_v4_restores_xiao_shu_identity_cues",
                    "motion_canonical_v4_reads_correctly",
                    "voice_linkage_desired",
                    "no_official_pet_package_mutation"
                ]
            },
            "revision_response": [
                "replace the white CSS stand-in with the read-only xiao-shu-dev sprite source",
                "mute the attention mark brightness",
                "soften alert_peek motion timing",
                "add slight outline and body weight only in alert state",
                "reduce alert-state body brightness without changing other tracks",
                "keep voice linkage as future sparse voice design, not immediate emit",
                "add sidecar_peek_v4 as the accepted motion-canonical visual candidate using the sidecar_peek_v2 raised-hand skeleton"
            ],
            "voice_linkage": {
                "requested": true,
                "policy": "future_sparse_voice_after_visual_re_review",
                "emits_audio_now": false
            },
            "recommended_next_step": "use sidecar_peek_v4 as the alert_peek visual baseline before any sparse voice or binding approval design"
        }),
        _ => json!({
            "schema": 1,
            "binding_stage": "fallback_only",
            "risk_level": "high",
            "visual_intent": "preserve safe neutral behavior for an unknown renderer token",
            "acceptance_criteria": [
                "unknown tokens never mutate assets",
                "fallback remains visually neutral",
                "payload makes the unresolved token obvious"
            ],
            "risk_notes": "do not bind unknown tokens without adding an explicit evidence entry",
            "review_questions": [
                "should this token become a named motion",
                "what state produced the unknown token"
            ],
            "recommended_next_step": "add a named mapping before any renderer binding"
        }),
    };

    json!({
        "schema": 1,
        "resolved": resolved,
        "input_token": renderer_token,
        "target": {
            "runtime": "codex_pet_compatible_sidecar",
            "contract": "xiao_shu_renderer_slots_v1",
            "pose_slot": pose_slot,
            "expression_slot": expression_slot,
            "motion_slot": motion_slot,
            "accessory_slot": accessory_slot,
        },
        "timeline": timeline,
        "note": note,
        "evidence": evidence,
    })
}

fn avatar_cortex_renderer_known_tokens() -> Vec<&'static str> {
    vec![
        "xiao_shu::soft_bounce::low",
        "xiao_shu::idle_breathe::low",
        "xiao_shu::sorting_glow::medium",
        "xiao_shu::look_sideways::medium",
        "xiao_shu::alert_peek::medium",
    ]
}

fn avatar_cortex_renderer_registry_entry(renderer_token: &str) -> Value {
    let mapping = avatar_cortex_renderer_mapping(renderer_token);
    let target = mapping.get("target").cloned().unwrap_or(Value::Null);
    let evidence = mapping.get("evidence").unwrap_or(&Value::Null);
    json!({
        "token": renderer_token,
        "resolved": mapping.get("resolved").cloned().unwrap_or(Value::Null),
        "target": target,
        "binding_stage": evidence.get("binding_stage").cloned().unwrap_or(Value::Null),
        "risk_level": evidence.get("risk_level").cloned().unwrap_or(Value::Null),
        "visual_intent": evidence.get("visual_intent").cloned().unwrap_or(Value::Null),
        "recommended_next_step": evidence.get("recommended_next_step").cloned().unwrap_or(Value::Null),
    })
}

fn avatar_cortex_renderer_registry_payload(current: Option<Value>) -> Value {
    let entries: Vec<Value> = avatar_cortex_renderer_known_tokens()
        .into_iter()
        .map(avatar_cortex_renderer_registry_entry)
        .collect();
    let fallback_policy = avatar_cortex_renderer_registry_entry("xiao_shu::unknown::fallback");
    let mut stage_counts: BTreeMap<String, usize> = BTreeMap::new();
    let mut risk_counts: BTreeMap<String, usize> = BTreeMap::new();
    for entry in entries.iter().chain(std::iter::once(&fallback_policy)) {
        let stage = vstr(entry.get("binding_stage")).unwrap_or("unknown");
        let risk = vstr(entry.get("risk_level")).unwrap_or("unknown");
        *stage_counts.entry(stage.to_string()).or_default() += 1;
        *risk_counts.entry(risk.to_string()).or_default() += 1;
    }

    let current_renderer = current
        .as_ref()
        .and_then(|value| value.get("renderer"))
        .unwrap_or(&Value::Null);
    let current_mapping = current_renderer.get("mapping").unwrap_or(&Value::Null);
    let current_evidence = current_mapping.get("evidence").unwrap_or(&Value::Null);

    json!({
        "surface": "avatar_cortex_renderer_registry",
        "schema": 1,
        "read_only": true,
        "dry_run": true,
        "emits_audio": false,
        "emits_notification": false,
        "mutates_global_substrate": false,
        "writes_files": false,
        "registry": {
            "schema": 1,
            "contract": "xiao_shu_renderer_slots_v1",
            "known_token_count": entries.len(),
            "entries": entries,
            "fallback_policy": fallback_policy,
            "stage_counts": stage_counts,
            "risk_counts": risk_counts,
            "current": {
                "token": current_mapping.get("input_token").cloned().unwrap_or(Value::Null),
                "resolved": current_mapping.get("resolved").cloned().unwrap_or(Value::Null),
                "binding_stage": current_evidence.get("binding_stage").cloned().unwrap_or(Value::Null),
                "risk_level": current_evidence.get("risk_level").cloned().unwrap_or(Value::Null),
            },
        },
        "renderer": current_renderer.clone(),
        "source_status": current
            .as_ref()
            .and_then(|value| value.get("source_status"))
            .cloned()
            .unwrap_or(Value::Null),
    })
}

pub(crate) fn avatar_cortex_renderer_preview_from_status(status: Value) -> Value {
    let motion_preview = avatar_cortex_motion_preview_from_status(status.clone());
    let motion = motion_preview.get("motion").cloned().unwrap_or(Value::Null);
    let hint = motion.get("animation_hint").unwrap_or(&Value::Null);
    let renderer_token = vstr(hint.get("renderer_token")).unwrap_or("xiao_shu::idle_breathe::low");
    let mapping = avatar_cortex_renderer_mapping(renderer_token);

    json!({
        "surface": "avatar_cortex_renderer_preview",
        "schema": 1,
        "read_only": true,
        "dry_run": true,
        "emits_audio": false,
        "emits_notification": false,
        "mutates_global_substrate": false,
        "writes_files": false,
        "project": status.get("project").cloned().unwrap_or(Value::Null),
        "label": status.get("label").cloned().unwrap_or(Value::Null),
        "heartbeat_label": status.get("heartbeat_label").cloned().unwrap_or(Value::Null),
        "renderer": {
            "schema": 1,
            "adapter": {
                "kind": "xiao_shu_motion_renderer_dry_run",
                "version": 1,
                "input": "motion.animation_hint.renderer_token",
            },
            "mapping": mapping,
            "safety": {
                "dry_run": true,
                "sidecar_only": true,
                "writes_files": false,
                "mutates_renderer": false,
                "codex_pet_package_mutation": false,
                "requires_human_binding": true,
            },
        },
        "motion": motion,
        "language": motion_preview.get("language").cloned().unwrap_or(Value::Null),
        "source_status": motion_preview.get("source_status").cloned().unwrap_or(Value::Null),
    })
}

pub fn avatar_cortex_renderer_preview(
    label: Option<&str>,
    heartbeat_label: Option<&str>,
    project: Option<&str>,
    output: Option<&Path>,
) -> Result<Value> {
    let status = avatar_cortex_status(label, heartbeat_label, project, output)?;
    Ok(avatar_cortex_renderer_preview_from_status(status))
}

pub(crate) fn avatar_cortex_renderer_registry_from_status(status: Value) -> Value {
    let renderer = avatar_cortex_renderer_preview_from_status(status);
    avatar_cortex_renderer_registry_payload(Some(renderer))
}

pub fn avatar_cortex_renderer_registry(
    label: Option<&str>,
    heartbeat_label: Option<&str>,
    project: Option<&str>,
    output: Option<&Path>,
) -> Result<Value> {
    let status = avatar_cortex_status(label, heartbeat_label, project, output)?;
    Ok(avatar_cortex_renderer_registry_from_status(status))
}

fn avatar_cortex_binding_plan_entry(entry: &Value, selected: bool) -> Value {
    let token = vstr(entry.get("token")).unwrap_or("unknown");
    let binding_stage = vstr(entry.get("binding_stage")).unwrap_or("unknown");
    let risk_level = vstr(entry.get("risk_level")).unwrap_or("unknown");
    let reason = if selected {
        "low-risk resolved candidate with explicit visual evidence"
    } else if binding_stage == "fallback_only" {
        "fallback policy is not a named renderer binding"
    } else {
        "requires manual review before renderer binding"
    };

    json!({
        "token": token,
        "resolved": entry.get("resolved").cloned().unwrap_or(Value::Null),
        "target": entry.get("target").cloned().unwrap_or(Value::Null),
        "binding_stage": binding_stage,
        "risk_level": risk_level,
        "visual_intent": entry.get("visual_intent").cloned().unwrap_or(Value::Null),
        "recommended_next_step": entry.get("recommended_next_step").cloned().unwrap_or(Value::Null),
        "selection": if selected { "selected" } else { "deferred" },
        "reason": reason,
    })
}

fn avatar_cortex_binding_plan_from_registry(registry_preview: Value) -> Value {
    let registry = registry_preview.get("registry").unwrap_or(&Value::Null);
    let mut selected = Vec::new();
    let mut deferred = Vec::new();
    if let Some(entries) = registry.get("entries").and_then(Value::as_array) {
        for entry in entries {
            let is_candidate = vstr(entry.get("binding_stage")) == Some("candidate");
            let is_low_risk = vstr(entry.get("risk_level")) == Some("low");
            let resolved = entry
                .get("resolved")
                .and_then(Value::as_bool)
                .unwrap_or(false);
            if is_candidate && is_low_risk && resolved {
                selected.push(avatar_cortex_binding_plan_entry(entry, true));
            } else {
                deferred.push(avatar_cortex_binding_plan_entry(entry, false));
            }
        }
    }
    if let Some(fallback) = registry.get("fallback_policy") {
        deferred.push(avatar_cortex_binding_plan_entry(fallback, false));
    }

    let first = selected.first().cloned().unwrap_or(Value::Null);
    let current = registry.get("current").cloned().unwrap_or(Value::Null);
    let selected_count = selected.len();
    let deferred_count = deferred.len();

    json!({
        "surface": "avatar_cortex_binding_plan",
        "schema": 1,
        "read_only": true,
        "dry_run": true,
        "emits_audio": false,
        "emits_notification": false,
        "mutates_global_substrate": false,
        "writes_files": false,
        "mutates_renderer": false,
        "codex_pet_package_mutation": false,
        "binding_plan": {
            "schema": 1,
            "contract": "xiao_shu_renderer_slots_v1",
            "decision": "bind only low-risk resolved candidates first; keep review and fallback tokens deferred",
            "selected_count": selected_count,
            "deferred_count": deferred_count,
            "first_candidate": first,
            "selected": selected,
            "deferred": deferred,
            "current": current,
            "phases": [
                {
                    "id": "sidecar_renderer_slot_contract_snapshot",
                    "action": "freeze the selected slot contract as a local sidecar preview fixture",
                    "validation": "CLI, HTTP, and panel surfaces expose identical selected tokens",
                    "rollback": "drop the fixture and continue serving registry-only dry-runs"
                },
                {
                    "id": "local_preview_fixture_golden_payload",
                    "action": "generate golden payloads for soft_bounce and idle_breathe without touching assets",
                    "validation": "focused tests prove writes_files=false and mutates_renderer=false",
                    "rollback": "remove golden payloads; motion semantics remain unchanged"
                },
                {
                    "id": "manual_visual_qa_panel_desktop_adapter",
                    "action": "review the selected motions in a desktop adapter or panel preview before package binding",
                    "validation": "soft_bounce returns to idle within two seconds and idle_breathe remains subtle",
                    "rollback": "map the token back to idle_breathe in the adapter layer"
                },
                {
                    "id": "optional_official_package_binding_after_approval",
                    "action": "only after explicit approval, bind accepted motions into an official Codex-compatible package",
                    "validation": "official package validation and contact-sheet QA pass",
                    "rollback": "restore the previously installed package and keep sidecar semantics intact"
                }
            ],
            "validation_checklist": [
                "no official Pet package mutation in this phase",
                "CLI, HTTP, and panel smoke checks all read the same plan",
                "renderer slot fallback remains neutral idle",
                "low-risk candidates return to idle within two seconds",
                "needs_review and fallback_only tokens remain deferred"
            ],
            "rollback_points": [
                "disable selected token mapping in the adapter",
                "fall back to xiao_shu::idle_breathe::low",
                "remove adapter binding without changing cortex state",
                "keep registry and motion semantics as the source of truth"
            ],
            "safety": {
                "read_only": true,
                "dry_run": true,
                "sidecar_only": true,
                "writes_files": false,
                "mutates_renderer": false,
                "codex_pet_package_mutation": false,
                "requires_human_approval": true
            }
        },
        "registry": registry_preview,
    })
}

pub(crate) fn avatar_cortex_binding_plan_from_status(status: Value) -> Value {
    let registry = avatar_cortex_renderer_registry_from_status(status);
    avatar_cortex_binding_plan_from_registry(registry)
}

pub fn avatar_cortex_binding_plan(
    label: Option<&str>,
    heartbeat_label: Option<&str>,
    project: Option<&str>,
    output: Option<&Path>,
) -> Result<Value> {
    let status = avatar_cortex_status(label, heartbeat_label, project, output)?;
    Ok(avatar_cortex_binding_plan_from_status(status))
}

fn avatar_cortex_fixture_id(token: &str) -> String {
    token.replace("::", "_")
}

fn avatar_cortex_timeline_max_ms(timeline: &Value) -> i64 {
    timeline
        .as_array()
        .map(|items| {
            items
                .iter()
                .filter_map(|item| item.get("at_ms").and_then(Value::as_i64))
                .max()
                .unwrap_or(0)
        })
        .unwrap_or(0)
}

fn avatar_cortex_timeline_returns_to_idle(timeline: &Value) -> bool {
    timeline
        .as_array()
        .map(|items| {
            items.iter().any(|item| {
                vstr(item.get("slot")) == Some("motion")
                    && vstr(item.get("value")) == Some("idle_breathe")
            })
        })
        .unwrap_or(false)
}

fn avatar_cortex_binding_fixture_record(entry: &Value) -> Value {
    let token = vstr(entry.get("token")).unwrap_or("unknown");
    let mapping = avatar_cortex_renderer_mapping(token);
    let target = mapping.get("target").cloned().unwrap_or(Value::Null);
    let timeline = mapping.get("timeline").cloned().unwrap_or(Value::Null);
    let duration_ms = avatar_cortex_timeline_max_ms(&timeline);
    let returns_to_idle = avatar_cortex_timeline_returns_to_idle(&timeline);
    let motion_slot = vstr(target.get("motion_slot")).unwrap_or("unknown");

    json!({
        "fixture_id": format!("{}_fixture_v1", avatar_cortex_fixture_id(token)),
        "token": token,
        "source_selection": entry.get("selection").cloned().unwrap_or(Value::Null),
        "risk_level": entry.get("risk_level").cloned().unwrap_or(Value::Null),
        "binding_stage": entry.get("binding_stage").cloned().unwrap_or(Value::Null),
        "track_kind": "selected",
        "review_only": false,
        "visual_intent": entry.get("visual_intent").cloned().unwrap_or(Value::Null),
        "target": target,
        "timeline": timeline,
        "golden_assertions": {
            "schema": 1,
            "motion_slot": motion_slot,
            "duration_ms": duration_ms,
            "returns_to_idle": returns_to_idle,
            "duration_within_2s": duration_ms <= 2000,
            "asset_writes_allowed": false,
            "renderer_mutation_allowed": false,
            "codex_pet_package_mutation_allowed": false,
        },
    })
}

fn avatar_cortex_binding_fixture_from_plan(plan_preview: Value) -> Value {
    let plan = plan_preview.get("binding_plan").unwrap_or(&Value::Null);
    let records: Vec<Value> = plan
        .get("selected")
        .and_then(Value::as_array)
        .map(|selected| {
            selected
                .iter()
                .map(avatar_cortex_binding_fixture_record)
                .collect()
        })
        .unwrap_or_default();
    let first = records.first().cloned().unwrap_or(Value::Null);
    let all_return_to_idle = records.iter().all(|record| {
        record["golden_assertions"]["returns_to_idle"]
            .as_bool()
            .unwrap_or(false)
    });
    let all_duration_within_2s = records.iter().all(|record| {
        record["golden_assertions"]["duration_within_2s"]
            .as_bool()
            .unwrap_or(false)
    });
    let fixture_count = records.len();

    json!({
        "surface": "avatar_cortex_binding_fixture",
        "schema": 1,
        "read_only": true,
        "dry_run": true,
        "emits_audio": false,
        "emits_notification": false,
        "mutates_global_substrate": false,
        "writes_files": false,
        "mutates_renderer": false,
        "codex_pet_package_mutation": false,
        "fixture": {
            "schema": 1,
            "kind": "sidecar_renderer_preview_fixture",
            "contract": "xiao_shu_renderer_slots_v1",
            "source": "avatar_cortex_binding_plan.selected",
            "fixture_count": fixture_count,
            "first_fixture": first,
            "golden_payloads": records,
            "deferred_count": plan.get("deferred_count").cloned().unwrap_or(Value::Null),
            "acceptance": {
                "all_return_to_idle": all_return_to_idle,
                "all_duration_within_2s": all_duration_within_2s,
                "asset_writes_allowed": false,
                "renderer_mutation_allowed": false,
                "codex_pet_package_mutation_allowed": false,
                "manual_visual_qa_required": true,
            },
            "next_step": "review these slot timelines in a sidecar visual adapter before any package binding",
        },
        "source_plan": plan_preview,
    })
}

pub(crate) fn avatar_cortex_binding_fixture_from_status(status: Value) -> Value {
    let plan = avatar_cortex_binding_plan_from_status(status);
    avatar_cortex_binding_fixture_from_plan(plan)
}

pub fn avatar_cortex_binding_fixture(
    label: Option<&str>,
    heartbeat_label: Option<&str>,
    project: Option<&str>,
    output: Option<&Path>,
) -> Result<Value> {
    let status = avatar_cortex_status(label, heartbeat_label, project, output)?;
    Ok(avatar_cortex_binding_fixture_from_status(status))
}

fn avatar_cortex_visual_adapter_frames(record: &Value) -> Vec<Value> {
    let mut pose = "neutral_idle".to_string();
    let mut expression = "calm_eyes".to_string();
    let mut motion = "idle_breathe".to_string();
    let mut accessory = "none".to_string();
    let mut events = record
        .get("timeline")
        .and_then(Value::as_array)
        .cloned()
        .unwrap_or_default();
    events.sort_by_key(|event| event.get("at_ms").and_then(Value::as_i64).unwrap_or(0));

    let mut frames = Vec::new();
    for event in events {
        let slot = vstr(event.get("slot")).unwrap_or("unknown");
        let value = vstr(event.get("value")).unwrap_or("unknown");
        match slot {
            "pose" => pose = value.to_string(),
            "expression" => expression = value.to_string(),
            "motion" => motion = value.to_string(),
            "accessory" => accessory = value.to_string(),
            _ => {}
        }
        let at_ms = event.get("at_ms").and_then(Value::as_i64).unwrap_or(0);
        frames.push(json!({
            "frame_id": format!("{}@{}", vstr(record.get("fixture_id")).unwrap_or("fixture"), at_ms),
            "at_ms": at_ms,
            "updated_slot": slot,
            "updated_value": value,
            "pose_slot": pose,
            "expression_slot": expression,
            "motion_slot": motion,
            "accessory_slot": accessory,
            "state_label": format!(
                "pose={} expression={} motion={} accessory={}",
                pose, expression, motion, accessory
            ),
        }));
    }

    if frames.is_empty() {
        frames.push(json!({
            "frame_id": format!("{}@0", vstr(record.get("fixture_id")).unwrap_or("fixture")),
            "at_ms": 0,
            "updated_slot": "none",
            "updated_value": "none",
            "pose_slot": pose,
            "expression_slot": expression,
            "motion_slot": motion,
            "accessory_slot": accessory,
            "state_label": "pose=neutral_idle expression=calm_eyes motion=idle_breathe accessory=none",
        }));
    }

    frames
}

fn avatar_cortex_visual_adapter_preview(record: &Value) -> Value {
    let frames = avatar_cortex_visual_adapter_frames(record);
    let final_frame = frames.last().cloned().unwrap_or(Value::Null);
    let final_motion = vstr(final_frame.get("motion_slot")).unwrap_or("unknown");
    let assertions = record.get("golden_assertions").unwrap_or(&Value::Null);
    json!({
        "fixture_id": record.get("fixture_id").cloned().unwrap_or(Value::Null),
        "token": record.get("token").cloned().unwrap_or(Value::Null),
        "source_selection": record.get("source_selection").cloned().unwrap_or(Value::Null),
        "binding_stage": record.get("binding_stage").cloned().unwrap_or(Value::Null),
        "track_kind": record.get("track_kind").cloned().unwrap_or(json!("selected")),
        "review_only": record.get("review_only").cloned().unwrap_or(json!(false)),
        "risk_level": record.get("risk_level").cloned().unwrap_or(Value::Null),
        "visual_intent": record.get("visual_intent").cloned().unwrap_or(Value::Null),
        "frame_count": frames.len(),
        "duration_ms": assertions.get("duration_ms").cloned().unwrap_or(Value::Null),
        "frames": frames,
        "final_state": final_frame,
        "acceptance": {
            "returns_to_idle": final_motion == "idle_breathe",
            "duration_within_2s": assertions
                .get("duration_within_2s")
                .and_then(Value::as_bool)
                .unwrap_or(false),
            "pixel_rendered": false,
            "asset_writes_allowed": false,
            "renderer_mutation_allowed": false,
            "codex_pet_package_mutation_allowed": false,
        },
    })
}

fn avatar_cortex_visual_adapter_from_fixture(fixture_preview: Value) -> Value {
    let fixture = fixture_preview.get("fixture").unwrap_or(&Value::Null);
    let previews: Vec<Value> = fixture
        .get("golden_payloads")
        .and_then(Value::as_array)
        .map(|records| {
            records
                .iter()
                .map(avatar_cortex_visual_adapter_preview)
                .collect()
        })
        .unwrap_or_default();
    let first = previews.first().cloned().unwrap_or(Value::Null);
    let all_return_to_idle = previews.iter().all(|preview| {
        preview["acceptance"]["returns_to_idle"]
            .as_bool()
            .unwrap_or(false)
    });
    let all_duration_within_2s = previews.iter().all(|preview| {
        preview["acceptance"]["duration_within_2s"]
            .as_bool()
            .unwrap_or(false)
    });
    let preview_count = previews.len();

    json!({
        "surface": "avatar_cortex_sidecar_visual_adapter",
        "schema": 1,
        "read_only": true,
        "dry_run": true,
        "emits_audio": false,
        "emits_notification": false,
        "mutates_global_substrate": false,
        "writes_files": false,
        "renders_pixels": false,
        "mutates_renderer": false,
        "codex_pet_package_mutation": false,
        "visual_adapter": {
            "schema": 1,
            "kind": "sidecar_slot_timeline_adapter_dry_run",
            "input": "avatar_cortex_binding_fixture.fixture.golden_payloads",
            "contract": "xiao_shu_renderer_slots_v1",
            "preview_count": preview_count,
            "first_preview": first,
            "previews": previews,
            "acceptance": {
                "all_return_to_idle": all_return_to_idle,
                "all_duration_within_2s": all_duration_within_2s,
                "pixel_rendered": false,
                "asset_writes_allowed": false,
                "renderer_mutation_allowed": false,
                "codex_pet_package_mutation_allowed": false,
                "manual_visual_qa_required": true,
            },
            "next_step": "connect these preview frames to a local sidecar renderer view before package binding",
        },
        "source_fixture": fixture_preview,
    })
}

pub(crate) fn avatar_cortex_visual_adapter_from_status(status: Value) -> Value {
    let fixture = avatar_cortex_binding_fixture_from_status(status);
    avatar_cortex_visual_adapter_from_fixture(fixture)
}

pub fn avatar_cortex_visual_adapter(
    label: Option<&str>,
    heartbeat_label: Option<&str>,
    project: Option<&str>,
    output: Option<&Path>,
) -> Result<Value> {
    let status = avatar_cortex_status(label, heartbeat_label, project, output)?;
    Ok(avatar_cortex_visual_adapter_from_status(status))
}

fn avatar_cortex_slot_css_class(prefix: &str, value: Option<&Value>, fallback: &str) -> String {
    let raw = vstr(value).unwrap_or(fallback);
    let mut slug = String::with_capacity(raw.len());
    for ch in raw.chars() {
        if ch.is_ascii_alphanumeric() {
            slug.push(ch.to_ascii_lowercase());
        } else if (ch == '_' || ch == '-' || ch.is_ascii_whitespace()) && !slug.ends_with('-') {
            slug.push('-');
        }
    }
    let slug = slug.trim_matches('-');
    if slug.is_empty() {
        format!("{prefix}-unknown")
    } else {
        format!("{prefix}-{slug}")
    }
}

fn avatar_cortex_review_timeline(timeline: &Value) -> (Value, i64) {
    let mut events = timeline.as_array().cloned().unwrap_or_default();
    let base_ms = avatar_cortex_timeline_max_ms(timeline);
    events.extend([
        json!({"at_ms": base_ms + 660, "slot": "expression", "value": "calm_eyes"}),
        json!({"at_ms": base_ms + 740, "slot": "accessory", "value": "none"}),
        json!({"at_ms": base_ms + 820, "slot": "pose", "value": "neutral_idle"}),
        json!({"at_ms": base_ms + 900, "slot": "motion", "value": "idle_breathe"}),
    ]);
    (Value::Array(events), base_ms + 900)
}

fn avatar_cortex_review_preview_from_deferred(entry: &Value) -> Option<Value> {
    let token = vstr(entry.get("token"))?;
    let resolved = entry
        .get("resolved")
        .and_then(Value::as_bool)
        .unwrap_or(false);
    let binding_stage = vstr(entry.get("binding_stage")).unwrap_or("unknown");
    let risk_level = vstr(entry.get("risk_level")).unwrap_or("unknown");
    if !resolved || binding_stage != "needs_review" || risk_level != "medium" {
        return None;
    }

    let mapping = avatar_cortex_renderer_mapping(token);
    if mapping
        .get("resolved")
        .and_then(Value::as_bool)
        .unwrap_or(false)
        != true
    {
        return None;
    }
    let target = mapping.get("target").cloned().unwrap_or(Value::Null);
    let (timeline, duration_ms) =
        avatar_cortex_review_timeline(mapping.get("timeline").unwrap_or(&Value::Null));
    let motion_slot = vstr(target.get("motion_slot")).unwrap_or("unknown");
    let record = json!({
        "fixture_id": format!("{}_review_fixture_v1", avatar_cortex_fixture_id(token)),
        "token": token,
        "source_selection": "deferred",
        "risk_level": risk_level,
        "binding_stage": binding_stage,
        "track_kind": "review_only",
        "review_only": true,
        "visual_intent": entry.get("visual_intent").cloned().unwrap_or(Value::Null),
        "target": target,
        "timeline": timeline,
        "golden_assertions": {
            "schema": 1,
            "motion_slot": motion_slot,
            "duration_ms": duration_ms,
            "returns_to_idle": true,
            "duration_within_2s": duration_ms <= 2000,
            "asset_writes_allowed": false,
            "renderer_mutation_allowed": false,
            "codex_pet_package_mutation_allowed": false,
        },
    });
    Some(avatar_cortex_visual_adapter_preview(&record))
}

fn avatar_cortex_renderer_review_previews(visual_adapter_preview: &Value) -> Vec<Value> {
    visual_adapter_preview
        .get("source_fixture")
        .and_then(|value| value.get("source_plan"))
        .and_then(|value| value.get("binding_plan"))
        .and_then(|value| value.get("deferred"))
        .and_then(Value::as_array)
        .map(|entries| {
            entries
                .iter()
                .filter_map(avatar_cortex_review_preview_from_deferred)
                .collect()
        })
        .unwrap_or_default()
}

fn avatar_cortex_renderer_view_frame(frame: &Value, index: usize, duration_ms: i64) -> Value {
    let at_ms = frame
        .get("at_ms")
        .and_then(Value::as_i64)
        .unwrap_or(0)
        .max(0);
    let at_pct = if duration_ms > 0 {
        ((at_ms * 100) / duration_ms).clamp(0, 100)
    } else {
        0
    };
    let pose_class = avatar_cortex_slot_css_class("pose", frame.get("pose_slot"), "neutral_idle");
    let expression_class =
        avatar_cortex_slot_css_class("expression", frame.get("expression_slot"), "calm_eyes");
    let motion_class =
        avatar_cortex_slot_css_class("motion", frame.get("motion_slot"), "idle_breathe");
    let accessory_class =
        avatar_cortex_slot_css_class("accessory", frame.get("accessory_slot"), "none");
    let css_classes = format!("{pose_class} {expression_class} {motion_class} {accessory_class}");
    json!({
        "index": index,
        "frame_id": frame.get("frame_id").cloned().unwrap_or(Value::Null),
        "at_ms": at_ms,
        "at_pct": at_pct,
        "pose_slot": frame.get("pose_slot").cloned().unwrap_or(Value::Null),
        "expression_slot": frame.get("expression_slot").cloned().unwrap_or(Value::Null),
        "motion_slot": frame.get("motion_slot").cloned().unwrap_or(Value::Null),
        "accessory_slot": frame.get("accessory_slot").cloned().unwrap_or(Value::Null),
        "state_label": frame.get("state_label").cloned().unwrap_or(Value::Null),
        "css_classes": css_classes,
    })
}

fn avatar_cortex_renderer_view_track_variants(token: &str) -> Vec<Value> {
    match token {
        "xiao_shu::soft_bounce::low" => vec![json!({
            "variant_id": "sidecar_soft_bounce_v1",
            "label": "sidecar soft bounce v1",
            "sprite_row": 0,
            "sprite_frames": 8,
            "alert_mark": false,
            "default": true,
            "intent": "motion-canonical baseline bounce using Xiao Shu sidecar identity cues without requiring an installed Codex pet package",
            "sidecar_asset": {
                "asset_id": "xiao-shu-motion-canonical-soft-bounce-v1",
                "route": "/avatar-surface/sidecar-spritesheet?asset=xiao-shu-motion-canonical-soft-bounce-v1",
                "format": "image/svg+xml",
                "atlas": "1536x1872",
                "cell": "192x208",
                "read_only": true,
                "official_pet_package_mutation": false,
                "art_pass": "motion_canonical_baseline_v1"
            },
            "asset_route": "/avatar-surface/sidecar-spritesheet?asset=xiao-shu-motion-canonical-soft-bounce-v1",
            "frame_choreography": {
                "schema": 1,
                "choreography_id": "soft_bounce_sidecar_v1_frame_choreo",
                "mode": "sidecar_sprite_atlas_columns",
                "uses_css_motion": false,
                "loop": "soft_bounce_return",
                "duration_ms": 1800,
                "frames": [
                    {"row": 0, "col": 0, "hold_ms": 180, "phase": "idle_entry", "mark": false},
                    {"row": 0, "col": 1, "hold_ms": 160, "phase": "compress", "mark": false},
                    {"row": 0, "col": 2, "hold_ms": 150, "phase": "lift_start", "mark": false},
                    {"row": 0, "col": 3, "hold_ms": 190, "phase": "apex", "mark": false},
                    {"row": 0, "col": 4, "hold_ms": 220, "phase": "float", "mark": false},
                    {"row": 0, "col": 5, "hold_ms": 170, "phase": "descend", "mark": false},
                    {"row": 0, "col": 6, "hold_ms": 170, "phase": "settle", "mark": false},
                    {"row": 0, "col": 7, "hold_ms": 560, "phase": "idle_return", "mark": false}
                ],
                "review_note": "keeps the cheerful confirmation readable without relying on the missing installed pet spritesheet",
            },
            "review_question": "does the sidecar baseline bounce still feel calm after several loops",
        })],
        "xiao_shu::idle_breathe::low" => vec![json!({
            "variant_id": "sidecar_idle_breathe_v1",
            "label": "sidecar idle breathe v1",
            "sprite_row": 0,
            "sprite_frames": 6,
            "alert_mark": false,
            "default": true,
            "intent": "motion-canonical idle loop for quiet desktop presence without requiring an installed Codex pet package",
            "sidecar_asset": {
                "asset_id": "xiao-shu-motion-canonical-idle-breathe-v1",
                "route": "/avatar-surface/sidecar-spritesheet?asset=xiao-shu-motion-canonical-idle-breathe-v1",
                "format": "image/svg+xml",
                "atlas": "1536x1872",
                "cell": "192x208",
                "read_only": true,
                "official_pet_package_mutation": false,
                "art_pass": "motion_canonical_baseline_v1"
            },
            "asset_route": "/avatar-surface/sidecar-spritesheet?asset=xiao-shu-motion-canonical-idle-breathe-v1",
            "frame_choreography": {
                "schema": 1,
                "choreography_id": "idle_breathe_sidecar_v1_frame_choreo",
                "mode": "sidecar_sprite_atlas_columns",
                "uses_css_motion": false,
                "loop": "quiet_breathe",
                "duration_ms": 1800,
                "frames": [
                    {"row": 0, "col": 0, "hold_ms": 260, "phase": "idle_floor", "mark": false},
                    {"row": 0, "col": 1, "hold_ms": 260, "phase": "inhale_start", "mark": false},
                    {"row": 0, "col": 2, "hold_ms": 300, "phase": "inhale_hold", "mark": false},
                    {"row": 0, "col": 3, "hold_ms": 300, "phase": "soft_hold", "mark": false},
                    {"row": 0, "col": 4, "hold_ms": 260, "phase": "exhale", "mark": false},
                    {"row": 0, "col": 5, "hold_ms": 420, "phase": "idle_return", "mark": false}
                ],
                "review_note": "slows the source 300ms idle fixture into a humane desktop breathing loop for visual QA",
            },
            "review_question": "does idle remain present without becoming needy beside a coding session",
        })],
        "xiao_shu::sorting_glow::medium" => vec![json!({
            "variant_id": "sidecar_sorting_glow_v1",
            "label": "sidecar sorting glow v1",
            "sprite_row": 0,
            "sprite_frames": 8,
            "alert_mark": false,
            "default": true,
            "intent": "motion-canonical review-only processing loop with visible signal sorting glow, independent of the installed Codex pet package",
            "sidecar_asset": {
                "asset_id": "xiao-shu-motion-canonical-sorting-glow-v1",
                "route": "/avatar-surface/sidecar-spritesheet?asset=xiao-shu-motion-canonical-sorting-glow-v1",
                "format": "image/svg+xml",
                "atlas": "1536x1872",
                "cell": "192x208",
                "read_only": true,
                "official_pet_package_mutation": false,
                "art_pass": "motion_canonical_review_v1"
            },
            "asset_route": "/avatar-surface/sidecar-spritesheet?asset=xiao-shu-motion-canonical-sorting-glow-v1",
            "frame_choreography": {
                "schema": 1,
                "choreography_id": "sorting_glow_sidecar_v1_frame_choreo",
                "mode": "sidecar_sprite_atlas_columns",
                "uses_css_motion": false,
                "loop": "gather_sort_glow_return",
                "duration_ms": 1440,
                "frames": [
                    {"row": 0, "col": 0, "hold_ms": 150, "phase": "idle_entry", "mark": false},
                    {"row": 0, "col": 1, "hold_ms": 160, "phase": "gather_left", "mark": false},
                    {"row": 0, "col": 2, "hold_ms": 170, "phase": "sort_left", "mark": false},
                    {"row": 0, "col": 3, "hold_ms": 190, "phase": "sort_right", "mark": false},
                    {"row": 0, "col": 4, "hold_ms": 260, "phase": "glow_peak", "mark": false},
                    {"row": 0, "col": 5, "hold_ms": 190, "phase": "coalesce", "mark": false},
                    {"row": 0, "col": 6, "hold_ms": 160, "phase": "settle", "mark": false},
                    {"row": 0, "col": 7, "hold_ms": 160, "phase": "idle_return", "mark": false}
                ],
                "review_note": "keeps sorting_glow visually distinct from alert_peek by using process glow instead of attention marks",
            },
            "review_question": "does sorting_glow read as quiet processing rather than a warning or alert",
        })],
        "xiao_shu::look_sideways::medium" => vec![json!({
            "variant_id": "sidecar_look_sideways_v1",
            "label": "sidecar look sideways v1",
            "sprite_row": 0,
            "sprite_frames": 7,
            "alert_mark": false,
            "default": true,
            "intent": "motion-canonical review-only sideways glance for gentle inspection states without relying on the installed Codex pet package",
            "sidecar_asset": {
                "asset_id": "xiao-shu-motion-canonical-look-sideways-v1",
                "route": "/avatar-surface/sidecar-spritesheet?asset=xiao-shu-motion-canonical-look-sideways-v1",
                "format": "image/svg+xml",
                "atlas": "1536x1872",
                "cell": "192x208",
                "read_only": true,
                "official_pet_package_mutation": false,
                "art_pass": "motion_canonical_review_v1"
            },
            "asset_route": "/avatar-surface/sidecar-spritesheet?asset=xiao-shu-motion-canonical-look-sideways-v1",
            "frame_choreography": {
                "schema": 1,
                "choreography_id": "look_sideways_sidecar_v1_frame_choreo",
                "mode": "sidecar_sprite_atlas_columns",
                "uses_css_motion": false,
                "loop": "glance_hold_return",
                "duration_ms": 1320,
                "frames": [
                    {"row": 0, "col": 0, "hold_ms": 160, "phase": "idle_entry", "mark": false},
                    {"row": 0, "col": 1, "hold_ms": 170, "phase": "notice_side", "mark": false},
                    {"row": 0, "col": 2, "hold_ms": 190, "phase": "glance_left", "mark": false},
                    {"row": 0, "col": 3, "hold_ms": 260, "phase": "inspect_hold", "mark": false},
                    {"row": 0, "col": 4, "hold_ms": 190, "phase": "blink_hold", "mark": false},
                    {"row": 0, "col": 5, "hold_ms": 170, "phase": "returning", "mark": false},
                    {"row": 0, "col": 6, "hold_ms": 180, "phase": "idle_return", "mark": false}
                ],
                "review_note": "uses eye and ribbon offsets instead of warning color so the glance remains curious, not urgent",
            },
            "review_question": "does look_sideways feel like calm inspection rather than distraction",
        })],
        "xiao_shu::alert_peek::medium" => vec![
            json!({
                "variant_id": "current_alert_row",
                "label": "current alert row",
                "sprite_row": 5,
                "sprite_frames": 8,
                "alert_mark": true,
                "default": false,
                "intent": "accepted original-sprite baseline; strongest attention read",
                "frame_choreography": {
                    "schema": 1,
                    "choreography_id": "alert_peek_frame_choreo_v1",
                    "mode": "sprite_atlas_columns",
                    "uses_css_motion": false,
                    "loop": "enter_hold_return",
                    "duration_ms": 1760,
                    "frames": [
                        {"row": 5, "col": 0, "hold_ms": 110, "phase": "idle_entry", "mark": false},
                        {"row": 5, "col": 1, "hold_ms": 110, "phase": "notice_start", "mark": false},
                        {"row": 5, "col": 2, "hold_ms": 130, "phase": "peek_in", "mark": false},
                        {"row": 5, "col": 3, "hold_ms": 160, "phase": "peek_check", "mark": true},
                        {"row": 5, "col": 4, "hold_ms": 300, "phase": "attention_hold", "mark": true},
                        {"row": 5, "col": 5, "hold_ms": 160, "phase": "soften", "mark": true},
                        {"row": 5, "col": 6, "hold_ms": 130, "phase": "returning", "mark": false},
                        {"row": 5, "col": 7, "hold_ms": 700, "phase": "idle_return", "mark": false}
                    ],
                    "review_note": "uses every available row-5 atlas column before any CSS motion",
                },
                "review_question": "does this still feel like a gentle attention request rather than failure",
                "voice_policy": "silent_now_review_sparse_voice_later",
            }),
            json!({
                "variant_id": "waiting_peek_row",
                "label": "waiting peek row",
                "sprite_row": 6,
                "sprite_frames": 6,
                "alert_mark": true,
                "default": false,
                "intent": "softer waiting or inspection posture with the same muted attention mark",
                "frame_choreography": {
                    "schema": 1,
                    "choreography_id": "alert_peek_frame_choreo_v1",
                    "mode": "sprite_atlas_columns",
                    "uses_css_motion": false,
                    "loop": "enter_hold_return",
                    "duration_ms": 1760,
                    "frames": [
                        {"row": 6, "col": 0, "hold_ms": 120, "phase": "idle_entry", "mark": false},
                        {"row": 6, "col": 1, "hold_ms": 120, "phase": "notice_start", "mark": false},
                        {"row": 6, "col": 2, "hold_ms": 150, "phase": "peek_in", "mark": false},
                        {"row": 6, "col": 3, "hold_ms": 190, "phase": "peek_check", "mark": true},
                        {"row": 6, "col": 4, "hold_ms": 330, "phase": "attention_hold", "mark": true},
                        {"row": 6, "col": 5, "hold_ms": 240, "phase": "gentle_hold", "mark": true},
                        {"row": 6, "col": 4, "hold_ms": 160, "phase": "soften", "mark": true},
                        {"row": 6, "col": 3, "hold_ms": 130, "phase": "returning", "mark": false},
                        {"row": 6, "col": 2, "hold_ms": 110, "phase": "returning", "mark": false},
                        {"row": 6, "col": 1, "hold_ms": 100, "phase": "settle", "mark": false},
                        {"row": 6, "col": 0, "hold_ms": 210, "phase": "idle_return", "mark": false}
                    ],
                    "review_note": "uses row-6 ping-pong columns so the peek reads as atlas-frame action, not CSS wobble",
                },
                "review_question": "does this read as supportively checking rather than alarmed",
                "voice_policy": "silent_now_review_sparse_voice_later",
            }),
            json!({
                "variant_id": "sidecar_peek_v2",
                "label": "sidecar peek v2",
                "sprite_row": 0,
                "sprite_frames": 8,
                "alert_mark": true,
                "default": false,
                "intent": "purpose-built sidecar-only action frames with a clearer peek, hand lift, blink, and return",
                "sidecar_asset": {
                    "asset_id": "xiao-shu-alert-peek-v2",
                    "route": "/avatar-surface/sidecar-spritesheet?asset=xiao-shu-alert-peek-v2",
                    "format": "image/svg+xml",
                    "atlas": "1536x1872",
                    "cell": "192x208",
                    "read_only": true,
                    "official_pet_package_mutation": false,
                    "art_pass": "prototype_v2"
                },
                "asset_route": "/avatar-surface/sidecar-spritesheet?asset=xiao-shu-alert-peek-v2",
                "frame_choreography": {
                    "schema": 1,
                    "choreography_id": "alert_peek_sidecar_v2_frame_choreo",
                    "mode": "sidecar_sprite_atlas_columns",
                    "uses_css_motion": false,
                    "loop": "enter_blink_return",
                    "duration_ms": 1660,
                    "frames": [
                        {"row": 0, "col": 0, "hold_ms": 95, "phase": "hidden_entry", "mark": false},
                        {"row": 0, "col": 1, "hold_ms": 110, "phase": "peek_start", "mark": false},
                        {"row": 0, "col": 2, "hold_ms": 130, "phase": "notice", "mark": false},
                        {"row": 0, "col": 3, "hold_ms": 150, "phase": "hand_lift", "mark": true},
                        {"row": 0, "col": 4, "hold_ms": 260, "phase": "attention_hold", "mark": true},
                        {"row": 0, "col": 5, "hold_ms": 150, "phase": "blink", "mark": true},
                        {"row": 0, "col": 4, "hold_ms": 150, "phase": "soften", "mark": true},
                        {"row": 0, "col": 6, "hold_ms": 130, "phase": "returning", "mark": false},
                        {"row": 0, "col": 7, "hold_ms": 185, "phase": "settle", "mark": false},
                        {"row": 0, "col": 0, "hold_ms": 300, "phase": "idle_return", "mark": false}
                    ],
                    "review_note": "switches to a read-only sidecar asset so the action frames can change before any official package decision",
                },
                "review_question": "does this finally read as Xiao Shu actively peeking rather than a flat atlas wobble",
                "voice_policy": "silent_now_review_sparse_voice_later",
            }),
            json!({
                "variant_id": "sidecar_peek_v4",
                "label": "sidecar peek v4",
                "sprite_row": 0,
                "sprite_frames": 8,
                "alert_mark": true,
                "default": true,
                "intent": "motion-canonical redraw that keeps the readable v2 raised-hand geometry while adding Xiao Shu paper-charm identity cues",
                "sidecar_asset": {
                    "asset_id": "xiao-shu-motion-canonical-peek-v4",
                    "route": "/avatar-surface/sidecar-spritesheet?asset=xiao-shu-motion-canonical-peek-v4",
                    "format": "image/svg+xml",
                    "atlas": "1536x1872",
                    "cell": "192x208",
                    "read_only": true,
                    "official_pet_package_mutation": false,
                    "art_pass": "motion_canonical_v4"
                },
                "asset_route": "/avatar-surface/sidecar-spritesheet?asset=xiao-shu-motion-canonical-peek-v4",
                "frame_choreography": {
                    "schema": 1,
                    "choreography_id": "alert_peek_sidecar_v4_frame_choreo",
                    "mode": "sidecar_sprite_atlas_columns",
                    "uses_css_motion": false,
                    "loop": "motion_canonical_peek_blink_return",
                    "duration_ms": 1660,
                    "frames": [
                        {"row": 0, "col": 0, "hold_ms": 95, "phase": "hidden_entry", "mark": false},
                        {"row": 0, "col": 1, "hold_ms": 110, "phase": "peek_start", "mark": false},
                        {"row": 0, "col": 2, "hold_ms": 130, "phase": "notice", "mark": false},
                        {"row": 0, "col": 3, "hold_ms": 150, "phase": "hand_lift", "mark": true},
                        {"row": 0, "col": 4, "hold_ms": 260, "phase": "attention_hold", "mark": true},
                        {"row": 0, "col": 5, "hold_ms": 150, "phase": "blink", "mark": true},
                        {"row": 0, "col": 4, "hold_ms": 150, "phase": "soften", "mark": true},
                        {"row": 0, "col": 6, "hold_ms": 130, "phase": "returning", "mark": false},
                        {"row": 0, "col": 7, "hold_ms": 185, "phase": "settle", "mark": false},
                        {"row": 0, "col": 0, "hold_ms": 300, "phase": "idle_return", "mark": false}
                    ],
                    "review_note": "keeps v2's visible raised-hand arm skeleton and layers Xiao Shu's canonical colors and small identity marks over it",
                },
                "review_question": "does this keep the v2 hand-lift read while feeling closer to Xiao Shu than the pure prototype",
                "voice_policy": "silent_now_review_sparse_voice_later",
            }),
            json!({
                "variant_id": "sidecar_peek_v3",
                "label": "sidecar peek v3",
                "sprite_row": 0,
                "sprite_frames": 8,
                "alert_mark": true,
                "default": false,
                "intent": "canonical-style redraw of the v2 motion, closer to the xiao-shu-dev paper charm silhouette and colors",
                "sidecar_asset": {
                    "asset_id": "xiao-shu-canonical-peek-v3",
                    "route": "/avatar-surface/sidecar-spritesheet?asset=xiao-shu-canonical-peek-v3",
                    "format": "image/svg+xml",
                    "atlas": "1536x1872",
                    "cell": "192x208",
                    "read_only": true,
                    "official_pet_package_mutation": false,
                    "art_pass": "canonical_style_v3"
                },
                "asset_route": "/avatar-surface/sidecar-spritesheet?asset=xiao-shu-canonical-peek-v3",
                "frame_choreography": {
                    "schema": 1,
                    "choreography_id": "alert_peek_sidecar_v3_frame_choreo",
                    "mode": "sidecar_sprite_atlas_columns",
                    "uses_css_motion": false,
                    "loop": "canonical_peek_blink_return",
                    "duration_ms": 1660,
                    "frames": [
                        {"row": 0, "col": 0, "hold_ms": 95, "phase": "hidden_entry", "mark": false},
                        {"row": 0, "col": 1, "hold_ms": 110, "phase": "peek_start", "mark": false},
                        {"row": 0, "col": 2, "hold_ms": 130, "phase": "notice", "mark": false},
                        {"row": 0, "col": 3, "hold_ms": 150, "phase": "sleeve_lift", "mark": true},
                        {"row": 0, "col": 4, "hold_ms": 260, "phase": "attention_hold", "mark": true},
                        {"row": 0, "col": 5, "hold_ms": 150, "phase": "blink", "mark": true},
                        {"row": 0, "col": 4, "hold_ms": 150, "phase": "soften", "mark": true},
                        {"row": 0, "col": 6, "hold_ms": 130, "phase": "returning", "mark": false},
                        {"row": 0, "col": 7, "hold_ms": 185, "phase": "settle", "mark": false},
                        {"row": 0, "col": 0, "hold_ms": 300, "phase": "idle_return", "mark": false}
                    ],
                    "review_note": "uses the same motion grammar as v2 but restores the formal Xiao Shu visual identity for review",
                },
                "review_question": "does this preserve Xiao Shu identity while keeping the stronger action read from v2",
                "voice_policy": "silent_now_review_sparse_voice_later",
            }),
            json!({
                "variant_id": "focused_review_row",
                "label": "focused review row",
                "sprite_row": 8,
                "sprite_frames": 6,
                "alert_mark": true,
                "default": false,
                "intent": "focused review posture for attention-needed states that should feel work-like",
                "frame_choreography": {
                    "schema": 1,
                    "choreography_id": "alert_peek_frame_choreo_v1",
                    "mode": "sprite_atlas_columns",
                    "uses_css_motion": false,
                    "loop": "enter_hold_return",
                    "duration_ms": 1560,
                    "frames": [
                        {"row": 8, "col": 0, "hold_ms": 120, "phase": "idle_entry", "mark": false},
                        {"row": 8, "col": 1, "hold_ms": 140, "phase": "focus_in", "mark": false},
                        {"row": 8, "col": 2, "hold_ms": 190, "phase": "review_check", "mark": true},
                        {"row": 8, "col": 3, "hold_ms": 330, "phase": "review_hold", "mark": true},
                        {"row": 8, "col": 4, "hold_ms": 210, "phase": "soften", "mark": true},
                        {"row": 8, "col": 5, "hold_ms": 160, "phase": "returning", "mark": false},
                        {"row": 8, "col": 4, "hold_ms": 120, "phase": "settle", "mark": false},
                        {"row": 8, "col": 0, "hold_ms": 290, "phase": "idle_return", "mark": false}
                    ],
                    "review_note": "uses the brighter row-8 columns as a focused inspection alternative",
                },
                "review_question": "does this make alert_peek feel too much like sorting_glow",
                "voice_policy": "silent_now_review_sparse_voice_later",
            }),
        ],
        _ => Vec::new(),
    }
}

fn avatar_cortex_renderer_view_track(preview: &Value, index: usize) -> Value {
    let token = vstr(preview.get("token")).unwrap_or("xiao_shu::unknown");
    let source_frames = preview
        .get("frames")
        .and_then(Value::as_array)
        .cloned()
        .filter(|frames| !frames.is_empty())
        .unwrap_or_else(|| {
            vec![json!({
                "frame_id": format!("{token}@0"),
                "at_ms": 0,
                "pose_slot": "neutral_idle",
                "expression_slot": "calm_eyes",
                "motion_slot": "idle_breathe",
                "accessory_slot": "none",
                "state_label": "pose=neutral_idle expression=calm_eyes motion=idle_breathe accessory=none",
            })]
        });
    let duration_ms = preview
        .get("duration_ms")
        .and_then(Value::as_i64)
        .or_else(|| {
            source_frames
                .last()
                .and_then(|frame| frame.get("at_ms"))
                .and_then(Value::as_i64)
        })
        .unwrap_or(0)
        .max(1);
    let frames: Vec<Value> = source_frames
        .iter()
        .enumerate()
        .map(|(frame_index, frame)| {
            avatar_cortex_renderer_view_frame(frame, frame_index, duration_ms)
        })
        .collect();
    let initial_frame = frames.first().cloned().unwrap_or(Value::Null);
    let final_frame = frames.last().cloned().unwrap_or(Value::Null);
    let semantic_variants = avatar_cortex_renderer_view_track_variants(token);
    let has_semantic_variants = !semantic_variants.is_empty();

    json!({
        "track_id": format!("xiao_shu_sidecar_renderer_track_{}", index + 1),
        "token": token,
        "fixture_id": preview.get("fixture_id").cloned().unwrap_or(Value::Null),
        "source_selection": preview.get("source_selection").cloned().unwrap_or(Value::Null),
        "binding_stage": preview.get("binding_stage").cloned().unwrap_or(Value::Null),
        "track_kind": preview.get("track_kind").cloned().unwrap_or(json!("selected")),
        "review_only": preview.get("review_only").cloned().unwrap_or(json!(false)),
        "risk_level": preview.get("risk_level").cloned().unwrap_or(Value::Null),
        "visual_intent": preview.get("visual_intent").cloned().unwrap_or(Value::Null),
        "semantic_variant_count": semantic_variants.len(),
        "has_semantic_variants": has_semantic_variants,
        "semantic_variants": semantic_variants,
        "semantic_variant_review": if token == "xiao_shu::alert_peek::medium" && has_semantic_variants {
            json!({
                "schema": 1,
                "surface": "alert_peek_semantic_variant_review",
                "read_only": true,
                "default_variant": "sidecar_peek_v4",
                "preferred_variant": "sidecar_peek_v4",
                "human_review_status": "visual_motion_candidate_accepted",
                "voice_linkage_preview": {
                    "schema": 1,
                    "surface": "alert_peek_voice_linkage_preview",
                    "read_only": true,
                    "selected_variant": "sidecar_peek_v4",
                    "intent": "pair the accepted visual attention cue with a sparse spoken prompt after an explicit gate",
                    "utterance": "小舒发现一点需要你看一下。",
                    "alternatives": [
                        "小舒看到一个需要注意的信号。",
                        "这里可能需要你看一眼。"
                    ],
                    "voice": {
                        "allowed_now": false,
                        "reason": "visual_linkage_preview_only",
                        "requires_explicit_emit_gate": true,
                        "suggested_voice": "Flo",
                        "suggested_rate": 190,
                    },
                    "gate": {
                        "dry_run_route": "/avatar-surface/cortex-voice-gate?enabled=true&reason=alert-peek-visual-review&preview_text=%E5%B0%8F%E8%88%92%E5%8F%91%E7%8E%B0%E4%B8%80%E7%82%B9%E9%9C%80%E8%A6%81%E4%BD%A0%E7%9C%8B%E4%B8%80%E4%B8%8B%E3%80%82",
                        "real_emit_surface": "agent-bridge avatar cortex-voice-emit",
                        "http_emit_route": Value::Null,
                        "requires_operator_reason": true,
                        "requires_policy_or_manual_override": true,
                        "cooldown_secs": 300,
                    },
                    "emits_audio": false,
                    "emits_notification": false,
                    "mutates_global_substrate": false,
                },
                "writes_approval": false,
                "persists_record": false,
                "can_promote_binding": false,
                "emits_audio": false,
                "next_step": "keep sidecar_peek_v4 as the alert_peek visual baseline before choosing any binding or sparse voice cue",
            })
        } else {
            Value::Null
        },
        "duration_ms": duration_ms,
        "frame_count": frames.len(),
        "renderer": {
            "schema": 1,
            "kind": "browser_codex_pet_sprite_sidecar",
            "geometry": "xiao_shu_codex_pet_atlas_1536x1872",
            "asset_source": "installed_codex_pet_package_readonly",
            "asset_pet_id": "xiao-shu-dev",
            "asset_route": "/avatar-surface/pet-spritesheet?pet_id=xiao-shu-dev",
            "fallback_geometry": "xiao_shu_sidecar_css_v1",
            "official_pet_package_binding": false,
            "official_pet_package_mutation": false,
        },
        "viewport": {
            "width": 320,
            "height": 320,
            "unit": "css_px",
        },
        "initial_frame": initial_frame,
        "final_frame": final_frame,
        "frames": frames,
    })
}

fn avatar_cortex_renderer_view_from_visual_adapter_payload(visual_adapter_preview: Value) -> Value {
    let adapter = visual_adapter_preview
        .get("visual_adapter")
        .unwrap_or(&Value::Null);
    let mut previews: Vec<Value> = adapter
        .get("previews")
        .and_then(Value::as_array)
        .cloned()
        .unwrap_or_default();
    let selected_track_count = previews.len();
    let review_previews = avatar_cortex_renderer_review_previews(&visual_adapter_preview);
    let review_track_count = review_previews.len();
    previews.extend(review_previews);
    let tracks: Vec<Value> = previews
        .iter()
        .enumerate()
        .map(|(index, preview)| avatar_cortex_renderer_view_track(preview, index))
        .collect();
    let first_track = tracks.first().cloned().unwrap_or(Value::Null);
    let all_return_to_idle = previews.iter().all(|preview| {
        preview["acceptance"]["returns_to_idle"]
            .as_bool()
            .unwrap_or(false)
    });
    let all_duration_within_2s = previews.iter().all(|preview| {
        preview["acceptance"]["duration_within_2s"]
            .as_bool()
            .unwrap_or(false)
    });
    let track_count = tracks.len();

    json!({
        "surface": "avatar_cortex_sidecar_renderer_view",
        "schema": 1,
        "read_only": true,
        "dry_run": true,
        "sidecar_only": true,
        "emits_audio": false,
        "emits_notification": false,
        "mutates_global_substrate": false,
        "writes_files": false,
        "renders_pixels": true,
        "browser_renders_pixels": true,
        "server_side_renders_pixels": false,
        "mutates_renderer": false,
        "codex_pet_package_mutation": false,
        "renderer_view": {
            "schema": 1,
            "kind": "browser_codex_pet_sprite_sidecar_renderer_view",
            "input": "avatar_cortex_sidecar_visual_adapter.visual_adapter.previews + avatar_cortex_binding_plan.deferred.needs_review",
            "contract": "xiao_shu_renderer_slots_v1",
            "html_route": "/avatar-surface/cortex-renderer-view",
            "asset_source": {
                "pet_id": "xiao-shu-dev",
                "route": "/avatar-surface/pet-spritesheet?pet_id=xiao-shu-dev",
                "atlas": "1536x1872",
                "cell": "192x208",
                "read_only": true,
                "official_pet_package_mutation": false
            },
            "track_count": track_count,
            "selected_track_count": selected_track_count,
            "review_track_count": review_track_count,
            "first_track": first_track,
            "tracks": tracks,
            "acceptance": {
                "all_return_to_idle": all_return_to_idle,
                "all_duration_within_2s": all_duration_within_2s,
                "review_tracks_require_manual_approval": review_track_count > 0,
                "review_tracks_mutate_bindings": false,
                "browser_view_only": true,
                "asset_writes_allowed": false,
                "renderer_mutation_allowed": false,
                "codex_pet_package_mutation_allowed": false,
                "manual_visual_qa_required": true,
            },
            "next_step": "manual browser visual QA for selected and review-only tracks before any official package binding",
        },
        "source_visual_adapter": visual_adapter_preview,
    })
}

pub(crate) fn avatar_cortex_renderer_view_from_status(status: Value) -> Value {
    let visual_adapter = avatar_cortex_visual_adapter_from_status(status);
    avatar_cortex_renderer_view_from_visual_adapter_payload(visual_adapter)
}

pub fn avatar_cortex_renderer_view(
    label: Option<&str>,
    heartbeat_label: Option<&str>,
    project: Option<&str>,
    output: Option<&Path>,
) -> Result<Value> {
    let status = avatar_cortex_status(label, heartbeat_label, project, output)?;
    Ok(avatar_cortex_renderer_view_from_status(status))
}

fn avatar_cortex_value_array_strings(value: &Value) -> Vec<Value> {
    value
        .as_array()
        .map(|items| {
            items
                .iter()
                .filter_map(Value::as_str)
                .map(|item| json!(item))
                .collect()
        })
        .unwrap_or_default()
}

fn avatar_cortex_renderer_review_gate_item(track: &Value, index: usize) -> Value {
    let token = vstr(track.get("token")).unwrap_or("xiao_shu::unknown");
    let mapping = avatar_cortex_renderer_mapping(token);
    let evidence = mapping.get("evidence").unwrap_or(&Value::Null);
    let binding_stage = vstr(track.get("binding_stage")).unwrap_or("unknown");
    let track_kind = vstr(track.get("track_kind")).unwrap_or("unknown");
    let risk_level = vstr(track.get("risk_level")).unwrap_or("unknown");
    let review_only = track
        .get("review_only")
        .and_then(Value::as_bool)
        .unwrap_or(false);
    let duration_ms = track
        .get("duration_ms")
        .and_then(Value::as_i64)
        .unwrap_or(0);
    let frame_count = track
        .get("frame_count")
        .and_then(Value::as_u64)
        .unwrap_or(0);
    let final_frame = track.get("final_frame").unwrap_or(&Value::Null);
    let final_motion = vstr(final_frame.get("motion_slot")).unwrap_or("unknown");
    let returns_to_idle = final_motion == "idle_breathe";
    let duration_within_2s = duration_ms <= 2000;
    let has_frames = frame_count > 0;
    let named_mapping_resolved = mapping
        .get("resolved")
        .and_then(Value::as_bool)
        .unwrap_or(false);
    let official_package_binding = track
        .get("renderer")
        .and_then(|renderer| renderer.get("official_pet_package_binding"))
        .and_then(Value::as_bool)
        .unwrap_or(false);
    let binding_stage_ok = if review_only {
        binding_stage == "needs_review" && track_kind == "review_only"
    } else {
        binding_stage == "candidate" && track_kind == "selected"
    };

    let mut blockers = Vec::new();
    if !has_frames {
        blockers.push(json!("no_frames"));
    }
    if !returns_to_idle {
        blockers.push(json!("does_not_return_to_idle_motion"));
    }
    if !duration_within_2s {
        blockers.push(json!("duration_over_2s"));
    }
    if !named_mapping_resolved {
        blockers.push(json!("unresolved_renderer_mapping"));
    }
    if official_package_binding {
        blockers.push(json!("official_package_binding_detected"));
    }
    if !binding_stage_ok {
        blockers.push(json!("binding_stage_mismatch"));
    }

    let automatic_gate = if blockers.is_empty() {
        if review_only {
            "ready_for_manual_review"
        } else {
            "selected_baseline_ready"
        }
    } else {
        "blocked"
    };
    let manual_decision = if review_only { "pending" } else { "baseline" };

    json!({
        "index": index,
        "token": token,
        "track_kind": track_kind,
        "review_only": review_only,
        "binding_stage": binding_stage,
        "risk_level": risk_level,
        "duration_ms": duration_ms,
        "frame_count": frame_count,
        "preferred_variant": track.get("preferred_variant").cloned().unwrap_or(Value::Null),
        "semantic_variant_count": track
            .get("semantic_variant_count")
            .cloned()
            .unwrap_or(Value::Null),
        "automatic_gate": automatic_gate,
        "manual_decision": manual_decision,
        "can_promote_binding": false,
        "blockers": blockers,
        "auto_checks": {
            "has_frames": has_frames,
            "returns_to_idle": returns_to_idle,
            "duration_within_2s": duration_within_2s,
            "named_mapping_resolved": named_mapping_resolved,
            "binding_stage_ok": binding_stage_ok,
            "official_package_binding": official_package_binding,
        },
        "visual_intent": track.get("visual_intent").cloned().unwrap_or(Value::Null),
        "risk_notes": evidence.get("risk_notes").cloned().unwrap_or(Value::Null),
        "latest_human_feedback": evidence
            .get("latest_human_feedback")
            .cloned()
            .unwrap_or(Value::Null),
        "revision_response": evidence
            .get("revision_response")
            .cloned()
            .unwrap_or_else(|| json!([])),
        "voice_linkage": evidence
            .get("voice_linkage")
            .cloned()
            .unwrap_or(Value::Null),
        "acceptance_criteria": avatar_cortex_value_array_strings(
            evidence.get("acceptance_criteria").unwrap_or(&Value::Null),
        ),
        "review_questions": avatar_cortex_value_array_strings(
            evidence.get("review_questions").unwrap_or(&Value::Null),
        ),
        "recommended_next_step": evidence
            .get("recommended_next_step")
            .cloned()
            .unwrap_or(Value::Null),
    })
}

fn avatar_cortex_renderer_review_gate_from_renderer_view_payload(renderer_view: Value) -> Value {
    let view = renderer_view.get("renderer_view").unwrap_or(&Value::Null);
    let review_items: Vec<Value> = view
        .get("tracks")
        .and_then(Value::as_array)
        .map(|tracks| {
            tracks
                .iter()
                .enumerate()
                .map(|(index, track)| avatar_cortex_renderer_review_gate_item(track, index))
                .collect()
        })
        .unwrap_or_default();
    let track_count = review_items.len();
    let automatic_pass_count = review_items
        .iter()
        .filter(|item| {
            item["blockers"]
                .as_array()
                .map(Vec::is_empty)
                .unwrap_or(false)
        })
        .count();
    let manual_pending_count = review_items
        .iter()
        .filter(|item| item["manual_decision"] == "pending")
        .count();
    let selected_baseline_count = review_items
        .iter()
        .filter(|item| item["manual_decision"] == "baseline")
        .count();

    json!({
        "surface": "avatar_cortex_renderer_review_gate",
        "schema": 1,
        "read_only": true,
        "dry_run": true,
        "sidecar_only": true,
        "emits_audio": false,
        "emits_notification": false,
        "mutates_global_substrate": false,
        "writes_files": false,
        "renders_pixels": false,
        "browser_renders_pixels": false,
        "server_side_renders_pixels": false,
        "mutates_renderer": false,
        "codex_pet_package_mutation": false,
        "review_gate": {
            "schema": 1,
            "input": "avatar_cortex_sidecar_renderer_view.renderer_view.tracks",
            "html_route": "/avatar-surface/cortex-review-gate",
            "renderer_view_route": view
                .get("html_route")
                .cloned()
                .unwrap_or(json!("/avatar-surface/cortex-renderer-view")),
            "track_count": track_count,
            "selected_baseline_count": selected_baseline_count,
            "manual_pending_count": manual_pending_count,
            "automatic_pass_count": automatic_pass_count,
            "automatic_blocked_count": track_count.saturating_sub(automatic_pass_count),
            "items": review_items,
            "acceptance": {
                "all_automatic_checks_pass": automatic_pass_count == track_count,
                "manual_review_required": manual_pending_count > 0,
                "review_tracks_require_explicit_approval": manual_pending_count > 0,
                "review_tracks_mutate_bindings": false,
                "can_promote_review_tracks": false,
                "asset_writes_allowed": false,
                "renderer_mutation_allowed": false,
                "codex_pet_package_mutation_allowed": false,
            },
            "decision": "review-only tracks remain inspection evidence until an explicit future approval gate is designed",
            "next_step": "inspect each pending review-only track in the browser renderer view and record a human decision outside this dry-run surface",
        },
        "source_renderer_view": renderer_view,
    })
}

pub(crate) fn avatar_cortex_renderer_review_gate_from_status(status: Value) -> Value {
    let renderer_view = avatar_cortex_renderer_view_from_status(status);
    avatar_cortex_renderer_review_gate_from_renderer_view_payload(renderer_view)
}

pub fn avatar_cortex_renderer_review_gate(
    label: Option<&str>,
    heartbeat_label: Option<&str>,
    project: Option<&str>,
    output: Option<&Path>,
) -> Result<Value> {
    let status = avatar_cortex_status(label, heartbeat_label, project, output)?;
    Ok(avatar_cortex_renderer_review_gate_from_status(status))
}

fn avatar_cortex_renderer_review_packet_item(item: &Value) -> Value {
    let token = vstr(item.get("token")).unwrap_or("xiao_shu::unknown");
    let risk_level = vstr(item.get("risk_level")).unwrap_or("unknown");
    let automatic_gate = vstr(item.get("automatic_gate")).unwrap_or("unknown");
    let recommended_next_step = item
        .get("recommended_next_step")
        .cloned()
        .unwrap_or(Value::Null);
    let mut operator_checks = vec![
        json!("does this motion stay comfortable beside an active coding session"),
        json!("does it remain readable at desktop pet size"),
        json!("does it avoid implying failure unless the source signal is unhealthy"),
    ];
    if token.contains("alert") {
        operator_checks.push(json!(
            "should this ever pair with sparse voice output, or stay visual-only"
        ));
    } else {
        operator_checks.push(json!(
            "should this remain silent even when the same state repeats"
        ));
    }

    json!({
        "token": token,
        "track_kind": item.get("track_kind").cloned().unwrap_or(Value::Null),
        "risk_level": risk_level,
        "preferred_variant": item
            .get("preferred_variant")
            .cloned()
            .unwrap_or(Value::Null),
        "semantic_variant_count": item
            .get("semantic_variant_count")
            .cloned()
            .unwrap_or(Value::Null),
        "automatic_gate": automatic_gate,
        "manual_decision": item.get("manual_decision").cloned().unwrap_or(Value::Null),
        "approval_state": "not_approved",
        "proposed_decision": "keep_pending",
        "default_decision": "keep_pending",
        "can_promote_binding": false,
        "writes_approval": false,
        "persists_record": false,
        "renderer_view": {
            "route": "/avatar-surface/cortex-renderer-view",
            "query_param": "track",
            "track": token,
        },
        "review_packet": {
            "schema": 1,
            "required_human_checks": operator_checks,
            "visual_questions": item
                .get("review_questions")
                .cloned()
                .unwrap_or_else(|| json!([])),
            "acceptance_criteria": item
                .get("acceptance_criteria")
                .cloned()
                .unwrap_or_else(|| json!([])),
            "latest_human_feedback": item
                .get("latest_human_feedback")
                .cloned()
                .unwrap_or(Value::Null),
            "revision_response": item
                .get("revision_response")
                .cloned()
                .unwrap_or_else(|| json!([])),
            "voice_linkage": item
                .get("voice_linkage")
                .cloned()
                .unwrap_or(Value::Null),
            "evidence_to_capture": [
                "desktop screenshot or live panel observation",
                "whether the motion feels calm after repeated loops",
                "whether it should remain visual-only or later pair with sparse voice",
            ],
            "allowed_future_decisions": [
                "keep_pending",
                "request_visual_revision",
                "candidate_for_future_approval_design",
            ],
            "recommended_next_step": recommended_next_step,
        },
        "source_checks": {
            "auto_checks": item.get("auto_checks").cloned().unwrap_or(Value::Null),
            "blockers": item.get("blockers").cloned().unwrap_or_else(|| json!([])),
        },
    })
}

fn avatar_cortex_renderer_review_packet_from_review_gate_payload(
    review_gate_payload: Value,
) -> Value {
    let gate = review_gate_payload
        .get("review_gate")
        .unwrap_or(&Value::Null);
    let items = gate
        .get("items")
        .and_then(Value::as_array)
        .cloned()
        .unwrap_or_default();
    let packets: Vec<Value> = items
        .iter()
        .filter(|item| item.get("manual_decision").and_then(Value::as_str) == Some("pending"))
        .map(avatar_cortex_renderer_review_packet_item)
        .collect();
    let baseline_references: Vec<Value> = items
        .iter()
        .filter(|item| item.get("manual_decision").and_then(Value::as_str) == Some("baseline"))
        .map(|item| {
            json!({
                "token": item.get("token").cloned().unwrap_or(Value::Null),
                "automatic_gate": item.get("automatic_gate").cloned().unwrap_or(Value::Null),
                "can_promote_binding": false,
            })
        })
        .collect();

    json!({
        "surface": "avatar_cortex_renderer_review_packet",
        "schema": 1,
        "read_only": true,
        "dry_run": true,
        "sidecar_only": true,
        "emits_audio": false,
        "emits_notification": false,
        "mutates_global_substrate": false,
        "writes_files": false,
        "renders_pixels": false,
        "browser_renders_pixels": false,
        "server_side_renders_pixels": false,
        "mutates_renderer": false,
        "codex_pet_package_mutation": false,
        "writes_approval": false,
        "persists_review_record": false,
        "review_packet": {
            "schema": 1,
            "input": "avatar_cortex_renderer_review_gate.review_gate.items",
            "html_route": "/avatar-surface/cortex-review-packet",
            "renderer_view_route": gate
                .get("renderer_view_route")
                .cloned()
                .unwrap_or(json!("/avatar-surface/cortex-renderer-view")),
            "packet_count": packets.len(),
            "manual_pending_count": packets.len(),
            "baseline_reference_count": baseline_references.len(),
            "packets": packets,
            "baseline_references": baseline_references,
            "acceptance": {
                "manual_review_required": !packets.is_empty(),
                "packets_are_approval_state": false,
                "approval_writes_allowed": false,
                "records_persisted": false,
                "review_tracks_mutate_bindings": false,
                "can_promote_review_tracks": false,
                "asset_writes_allowed": false,
                "renderer_mutation_allowed": false,
                "codex_pet_package_mutation_allowed": false,
            },
            "decision": "review packets organize human inspection evidence but do not approve, persist, or bind tracks",
            "next_step": "open each packet's focused renderer view, then record any human decision in a separately designed approval surface",
        },
        "source_review_gate": review_gate_payload,
    })
}

pub(crate) fn avatar_cortex_renderer_review_packet_from_status(status: Value) -> Value {
    let review_gate = avatar_cortex_renderer_review_gate_from_status(status);
    avatar_cortex_renderer_review_packet_from_review_gate_payload(review_gate)
}

pub fn avatar_cortex_renderer_review_packet(
    label: Option<&str>,
    heartbeat_label: Option<&str>,
    project: Option<&str>,
    output: Option<&Path>,
) -> Result<Value> {
    let status = avatar_cortex_status(label, heartbeat_label, project, output)?;
    Ok(avatar_cortex_renderer_review_packet_from_status(status))
}

fn avatar_cortex_json_array_len(value: &Value) -> usize {
    value.as_array().map(Vec::len).unwrap_or(0)
}

fn avatar_cortex_review_record_outcome_state(outcome: &str) -> &'static str {
    match outcome {
        "approved" => "approved",
        "request_revision" => "revision_requested",
        "rejected" => "rejected",
        "keep_pending" => "kept_pending",
        _ => "recorded",
    }
}

fn avatar_cortex_latest_review_record<'a>(
    records: &'a [Value],
    token: &str,
    variant: Option<&str>,
) -> Option<&'a Value> {
    records.iter().rev().find(|record| {
        vstr(record.get("track")) == Some(token)
            && match (variant, vstr(record.get("variant"))) {
                (Some(expected), Some(actual)) => expected == actual,
                (Some(_), None) => false,
                (None, _) => true,
            }
    })
}

fn avatar_cortex_review_record_command(
    project: &str,
    token: &str,
    variant: Option<&str>,
) -> String {
    let mut command = format!(
        "agent-bridge avatar cortex-review-record --project {project:?} --track {token:?} --outcome approved --reviewer \"local-operator\" --reason \"human-visual-review\" --confirm"
    );
    if let Some(variant) = variant.filter(|v| !v.trim().is_empty()) {
        command.push_str(&format!(" --variant {variant:?}"));
    }
    command
}

fn avatar_cortex_renderer_review_report_item(
    packet: &Value,
    project: &str,
    review_records: &[Value],
) -> Value {
    let token = vstr(packet.get("token")).unwrap_or("xiao_shu::unknown");
    let preferred_variant = vstr(packet.get("preferred_variant"));
    let latest_review_record =
        avatar_cortex_latest_review_record(review_records, token, preferred_variant);
    let review_packet = packet.get("review_packet").unwrap_or(&Value::Null);
    let source_checks = packet.get("source_checks").unwrap_or(&Value::Null);
    let blockers = source_checks.get("blockers").unwrap_or(&Value::Null);
    let latest_human_feedback = review_packet
        .get("latest_human_feedback")
        .cloned()
        .unwrap_or(Value::Null);
    let revision_response = review_packet
        .get("revision_response")
        .cloned()
        .unwrap_or_else(|| json!([]));
    let voice_linkage = review_packet
        .get("voice_linkage")
        .cloned()
        .unwrap_or(Value::Null);
    let has_blockers = avatar_cortex_json_array_len(blockers) > 0;
    let has_human_feedback = latest_human_feedback.is_object();
    let voice_linkage_requested = voice_linkage
        .get("requested")
        .and_then(Value::as_bool)
        .unwrap_or(false);
    let has_preview_route = packet
        .get("renderer_view")
        .and_then(|renderer| renderer.get("track"))
        .and_then(Value::as_str)
        .is_some();
    let has_questions = avatar_cortex_json_array_len(
        review_packet
            .get("visual_questions")
            .unwrap_or(&Value::Null),
    ) > 0;
    let has_acceptance = avatar_cortex_json_array_len(
        review_packet
            .get("acceptance_criteria")
            .unwrap_or(&Value::Null),
    ) > 0;
    let has_operator_checks = avatar_cortex_json_array_len(
        review_packet
            .get("required_human_checks")
            .unwrap_or(&Value::Null),
    ) > 0;
    let ready_for_human_review = !has_blockers
        && has_preview_route
        && has_questions
        && has_acceptance
        && has_operator_checks;
    let latest_review_record_value = latest_review_record.cloned().unwrap_or(Value::Null);
    let latest_outcome = latest_review_record
        .and_then(|record| vstr(record.get("outcome")))
        .unwrap_or("not_approved");
    let human_decision_present = latest_review_record.is_some();
    let approved = latest_outcome == "approved";
    let approval_state = if human_decision_present {
        avatar_cortex_review_record_outcome_state(latest_outcome)
    } else {
        packet
            .get("approval_state")
            .and_then(Value::as_str)
            .unwrap_or("not_approved")
    };

    json!({
        "token": token,
        "preferred_variant": packet
            .get("preferred_variant")
            .cloned()
            .unwrap_or(Value::Null),
        "readiness": if ready_for_human_review {
            "ready_for_human_visual_review"
        } else {
            "blocked"
        },
        "default_decision": packet
            .get("default_decision")
            .cloned()
            .unwrap_or(json!("keep_pending")),
        "approval_state": approval_state,
        "can_promote_binding": false,
        "ready_for_human_review": ready_for_human_review,
        "ready_for_approval": ready_for_human_review && approved,
        "human_decision_present": human_decision_present,
        "latest_review_record": latest_review_record_value,
        "review_record_command": avatar_cortex_review_record_command(
            project,
            token,
            preferred_variant,
        ),
        "focused_renderer": packet
            .get("renderer_view")
            .cloned()
            .unwrap_or(Value::Null),
        "latest_human_feedback": latest_human_feedback,
        "revision_response": revision_response,
        "voice_linkage": voice_linkage,
        "human_feedback_present": has_human_feedback,
        "voice_linkage_requested": voice_linkage_requested,
        "evidence_counts": {
            "visual_questions": avatar_cortex_json_array_len(
                review_packet.get("visual_questions").unwrap_or(&Value::Null),
            ),
            "acceptance_criteria": avatar_cortex_json_array_len(
                review_packet.get("acceptance_criteria").unwrap_or(&Value::Null),
            ),
            "operator_checks": avatar_cortex_json_array_len(
                review_packet.get("required_human_checks").unwrap_or(&Value::Null),
            ),
            "revision_response": avatar_cortex_json_array_len(
                review_packet.get("revision_response").unwrap_or(&Value::Null),
            ),
            "source_blockers": avatar_cortex_json_array_len(blockers),
            "review_records": if human_decision_present { 1 } else { 0 },
        },
        "missing": {
            "preview_route": !has_preview_route,
            "visual_questions": !has_questions,
            "acceptance_criteria": !has_acceptance,
            "operator_checks": !has_operator_checks,
            "source_blockers": has_blockers,
        },
        "next_step": if approved {
            "review record is approved; binding promotion still requires a separate explicit design"
        } else {
            "open focused renderer preview and record a local CLI review decision"
        },
    })
}

#[cfg(test)]
fn avatar_cortex_renderer_review_report_from_packet_payload(review_packet_payload: Value) -> Value {
    avatar_cortex_renderer_review_report_from_packet_payload_with_records(
        review_packet_payload,
        "agent-bridge",
        &[],
    )
}

fn avatar_cortex_renderer_review_report_from_packet_payload_with_records(
    review_packet_payload: Value,
    project: &str,
    review_records: &[Value],
) -> Value {
    let packet = review_packet_payload
        .get("review_packet")
        .unwrap_or(&Value::Null);
    let packets = packet
        .get("packets")
        .and_then(Value::as_array)
        .cloned()
        .unwrap_or_default();
    let items: Vec<Value> = packets
        .iter()
        .map(|packet| avatar_cortex_renderer_review_report_item(packet, project, review_records))
        .collect();
    let packet_count = items.len();
    let ready_count = items
        .iter()
        .filter(|item| {
            item.get("ready_for_human_review")
                .and_then(Value::as_bool)
                .unwrap_or(false)
        })
        .count();
    let human_feedback_count = items
        .iter()
        .filter(|item| {
            item.get("human_feedback_present")
                .and_then(Value::as_bool)
                .unwrap_or(false)
        })
        .count();
    let voice_linkage_requested_count = items
        .iter()
        .filter(|item| {
            item.get("voice_linkage_requested")
                .and_then(Value::as_bool)
                .unwrap_or(false)
        })
        .count();
    let human_decision_count = items
        .iter()
        .filter(|item| {
            item.get("human_decision_present")
                .and_then(Value::as_bool)
                .unwrap_or(false)
        })
        .count();
    let approved_count = items
        .iter()
        .filter(|item| item.get("approval_state").and_then(Value::as_str) == Some("approved"))
        .count();
    let blocked_count = packet_count.saturating_sub(ready_count);
    let ready_for_human_review = packet_count > 0 && blocked_count == 0;
    let ready_for_approval = approved_count > 0;
    let packet_route = packet
        .get("html_route")
        .cloned()
        .unwrap_or_else(|| json!("/avatar-surface/cortex-review-packet"));
    let renderer_view_route = packet
        .get("renderer_view_route")
        .cloned()
        .unwrap_or_else(|| json!("/avatar-surface/cortex-renderer-view"));
    let report_state = if ready_for_human_review {
        "ready_for_human_visual_review"
    } else {
        "needs_packet_repair"
    };
    let checklist = json!([
        "open each focused renderer preview from the packet",
        "watch the motion through several loops beside a coding session",
        "compare the visual behavior with the packet acceptance criteria",
        "record any human observation in a future explicit review record surface",
    ]);
    let acceptance = json!({
        "ready_for_human_visual_review": ready_for_human_review,
        "ready_for_approval": ready_for_approval,
        "approval_writes_allowed": false,
        "cli_review_record_available": true,
        "records_persisted": !review_records.is_empty(),
        "review_tracks_mutate_bindings": false,
        "can_promote_review_tracks": false,
        "asset_writes_allowed": false,
        "renderer_mutation_allowed": false,
        "codex_pet_package_mutation_allowed": false,
        "merge_without_human_review_allowed": false,
    });
    let review_report = json!({
        "schema": 1,
        "input": "avatar_cortex_renderer_review_packet.review_packet.packets",
        "html_route": "/avatar-surface/cortex-review-report",
        "packet_route": packet_route,
        "renderer_view_route": renderer_view_route,
        "packet_count": packet_count,
        "ready_packet_count": ready_count,
        "blocked_packet_count": blocked_count,
        "human_feedback_count": human_feedback_count,
        "voice_linkage_requested_count": voice_linkage_requested_count,
        "human_decision_count": human_decision_count,
        "approved_count": approved_count,
        "review_record_count": review_records.len(),
        "report_state": report_state,
        "items": items,
        "checklist": checklist,
        "acceptance": acceptance,
        "decision": if approved_count > 0 {
            "human review records exist; renderer bindings still require a separate explicit promotion design"
        } else {
            "implementation is ready for human visual review, but no pending track is approved or promotable"
        },
        "next_step": if approved_count > 0 {
            "inspect approved records and design a separate binding promotion gate before any renderer binding changes"
        } else {
            "perform the human visual pass for sorting_glow, look_sideways, and alert_peek, then record a local CLI review decision"
        },
    });

    json!({
        "surface": "avatar_cortex_renderer_review_report",
        "schema": 1,
        "read_only": true,
        "dry_run": true,
        "sidecar_only": true,
        "emits_audio": false,
        "emits_notification": false,
        "mutates_global_substrate": false,
        "writes_files": false,
        "renders_pixels": false,
        "browser_renders_pixels": false,
        "server_side_renders_pixels": false,
        "mutates_renderer": false,
        "codex_pet_package_mutation": false,
        "writes_approval": false,
        "persists_review_record": false,
        "review_report": review_report,
        "source_review_packet": review_packet_payload,
    })
}

#[cfg(test)]
pub(crate) fn avatar_cortex_renderer_review_report_from_status(status: Value) -> Value {
    let review_packet = avatar_cortex_renderer_review_packet_from_status(status);
    avatar_cortex_renderer_review_report_from_packet_payload(review_packet)
}

pub(crate) fn avatar_cortex_renderer_review_report_from_status_for_project(
    status: Value,
    project: &str,
) -> Result<Value> {
    let review_packet = avatar_cortex_renderer_review_packet_from_status(status);
    let path = avatar_cortex_review_record_path(project)?;
    let records = read_jsonl_records(&path)?;
    Ok(
        avatar_cortex_renderer_review_report_from_packet_payload_with_records(
            review_packet,
            project,
            &records,
        ),
    )
}

pub fn avatar_cortex_renderer_review_report(
    label: Option<&str>,
    heartbeat_label: Option<&str>,
    project: Option<&str>,
    output: Option<&Path>,
) -> Result<Value> {
    let project = project.unwrap_or("agent-bridge");
    let status = avatar_cortex_status(label, heartbeat_label, Some(project), output)?;
    avatar_cortex_renderer_review_report_from_status_for_project(status, project)
}

fn avatar_cortex_review_outcome_allowed(outcome: &str) -> bool {
    matches!(
        outcome,
        "approved" | "keep_pending" | "request_revision" | "rejected"
    )
}

fn avatar_cortex_track_default_variant(track: &Value) -> Option<String> {
    vstr(track.get("preferred_variant"))
        .or_else(|| {
            track
                .get("semantic_variants")
                .and_then(Value::as_array)
                .and_then(|variants| {
                    variants
                        .iter()
                        .find(|variant| {
                            variant
                                .get("default")
                                .and_then(Value::as_bool)
                                .unwrap_or(false)
                        })
                        .or_else(|| variants.first())
                })
                .and_then(|variant| vstr(variant.get("variant_id")))
        })
        .map(ToString::to_string)
}

fn avatar_cortex_track_has_variant(track: &Value, variant: &str) -> bool {
    track
        .get("semantic_variants")
        .and_then(Value::as_array)
        .map(|variants| {
            variants
                .iter()
                .any(|candidate| vstr(candidate.get("variant_id")) == Some(variant))
        })
        .unwrap_or(false)
}

fn avatar_cortex_review_record_from_renderer_view_payload(
    renderer_view_payload: Value,
    opts: &AvatarCortexReviewRecordOptions<'_>,
    record_path: &Path,
) -> Result<Value> {
    let project = opts.project.unwrap_or("agent-bridge");
    let token = opts
        .requested_track
        .map(str::trim)
        .filter(|track| !track.is_empty())
        .unwrap_or("xiao_shu::alert_peek::medium");
    let outcome = opts
        .outcome
        .map(str::trim)
        .filter(|outcome| !outcome.is_empty())
        .unwrap_or("approved");
    let reviewer = opts
        .reviewer
        .map(str::trim)
        .filter(|reviewer| !reviewer.is_empty())
        .unwrap_or("local-operator");
    let reason = opts
        .reason
        .map(str::trim)
        .filter(|reason| !reason.is_empty());
    let view = renderer_view_payload
        .get("renderer_view")
        .unwrap_or(&Value::Null);
    let track = view
        .get("tracks")
        .and_then(Value::as_array)
        .and_then(|tracks| {
            tracks
                .iter()
                .find(|track| vstr(track.get("token")) == Some(token))
        });
    let variant = track
        .and_then(|track| {
            opts.requested_variant
                .map(str::trim)
                .filter(|variant| !variant.is_empty())
                .map(ToString::to_string)
                .or_else(|| avatar_cortex_track_default_variant(track))
        })
        .unwrap_or_else(|| "default".to_string());
    let mut blocked_reasons = Vec::new();
    if track.is_none() {
        blocked_reasons.push(json!("track_not_found"));
    }
    if !avatar_cortex_review_outcome_allowed(outcome) {
        blocked_reasons.push(json!("unsupported_outcome"));
    }
    if let Some(track) = track {
        if !avatar_cortex_track_has_variant(track, &variant) {
            blocked_reasons.push(json!("variant_not_found"));
        }
        if track
            .get("track_kind")
            .and_then(Value::as_str)
            .unwrap_or("-")
            != "review_only"
        {
            blocked_reasons.push(json!("track_not_review_only"));
        }
    }
    if reason.is_none() {
        blocked_reasons.push(json!("reason_missing"));
    }
    if !opts.confirm {
        blocked_reasons.push(json!("confirm_flag_missing"));
    }

    let blocked = !blocked_reasons.is_empty();
    let now = now_secs();
    let nonce = std::time::SystemTime::now()
        .duration_since(std::time::UNIX_EPOCH)
        .map(|d| d.as_nanos())
        .unwrap_or(now as u128);
    let notes: Vec<String> = opts
        .notes
        .iter()
        .map(|note| note.trim())
        .filter(|note| !note.is_empty())
        .map(ToString::to_string)
        .collect();
    let review_hash = fnv1a_hex16(&format!(
        "{project}|{token}|{variant}|{outcome}|{reviewer}|{now}|{nonce}|{:?}",
        notes
    ));
    let review_id = format!("xsrrev-{now}-{}", &review_hash[..8]);
    let record = if blocked {
        Value::Null
    } else {
        json!({
            "schema": 1,
            "review_id": review_id,
            "created_at": now,
            "updated_at": now,
            "project": project,
            "target": "xiao-shu",
            "source": "avatar_cortex_review_record",
            "actor": "local-cli",
            "reviewer": reviewer,
            "track": token,
            "variant": variant,
            "outcome": outcome,
            "approval_state": avatar_cortex_review_record_outcome_state(outcome),
            "reason": reason,
            "notes": notes,
            "cli_only": true,
            "sidecar_only": true,
            "llm_safe": true,
            "direct_pet_control_allowed": false,
            "direct_llm_emit_allowed": false,
            "emits_audio": false,
            "emits_notification": false,
            "writes_approval": outcome == "approved",
            "writes_files": true,
            "writes_cooldown_state": false,
            "mutates_renderer": false,
            "codex_pet_package_mutation": false,
            "mutates_global_substrate": false,
            "can_promote_binding": false,
            "review_tracks_mutate_bindings": false,
            "record_path": record_path.to_string_lossy(),
        })
    };
    if !blocked {
        append_jsonl(record_path, &record)?;
    }

    Ok(json!({
        "surface": "avatar_cortex_review_record",
        "schema": 1,
        "generated_at": now,
        "cli_only": true,
        "http_available": false,
        "read_only": blocked,
        "dry_run": blocked,
        "llm_safe": true,
        "sidecar_only": true,
        "direct_pet_control_allowed": false,
        "direct_llm_emit_allowed": false,
        "emits_audio": false,
        "emits_notification": false,
        "writes_files": !blocked,
        "writes_approval": !blocked && outcome == "approved",
        "persists_review_record": !blocked,
        "writes_cooldown_state": false,
        "mutates_renderer": false,
        "codex_pet_package_mutation": false,
        "mutates_global_substrate": false,
        "can_promote_binding": false,
        "review_tracks_mutate_bindings": false,
        "project": project,
        "track": token,
        "variant": variant,
        "outcome": outcome,
        "reviewer": reviewer,
        "confirmed": opts.confirm,
        "blocked": blocked,
        "blocked_reasons": blocked_reasons,
        "record_path": record_path.to_string_lossy(),
        "record": record,
        "source_renderer_view": renderer_view_payload,
        "next_step": if blocked {
            "review the focused renderer view and rerun this local CLI command with --confirm plus a reason to persist the review record"
        } else {
            "review record persisted; inspect cortex-review-report before any separate binding promotion design"
        },
    }))
}

pub fn avatar_cortex_renderer_review_record(
    opts: &AvatarCortexReviewRecordOptions<'_>,
) -> Result<Value> {
    let project = opts.project.unwrap_or("agent-bridge");
    let status =
        avatar_cortex_status(opts.label, opts.heartbeat_label, Some(project), opts.output)?;
    let renderer_view = avatar_cortex_renderer_view_from_status(status);
    let record_path = avatar_cortex_review_record_path(project)?;
    avatar_cortex_review_record_from_renderer_view_payload(renderer_view, opts, &record_path)
}

fn avatar_cortex_voice_policy_rule_from_track(track: &Value) -> Value {
    let token = vstr(track.get("token")).unwrap_or("xiao_shu::unknown");
    let review = track.get("semantic_variant_review").unwrap_or(&Value::Null);
    let voice_linkage = review.get("voice_linkage_preview").unwrap_or(&Value::Null);
    let has_voice_linkage = voice_linkage.is_object();
    let default_variant = vstr(review.get("preferred_variant"))
        .or_else(|| vstr(review.get("default_variant")))
        .unwrap_or("-");
    let visual_intent = vstr(track.get("visual_intent")).unwrap_or("-");
    let utterance = vstr(voice_linkage.get("utterance"));
    let dry_run_route = voice_linkage
        .get("gate")
        .and_then(|gate| gate.get("dry_run_route"))
        .cloned()
        .unwrap_or(Value::Null);
    let real_emit_allowed = has_voice_linkage && default_variant == "sidecar_peek_v4";
    let mode = match token {
        "xiao_shu::idle_breathe::low" => "silent_presence",
        "xiao_shu::soft_bounce::low" => "visual_only_completion",
        "xiao_shu::sorting_glow::medium" => "display_only_processing",
        "xiao_shu::look_sideways::medium" => "silent_visual_attention",
        "xiao_shu::alert_peek::medium" if real_emit_allowed => "manual_cli_emit_after_attention",
        "xiao_shu::alert_peek::medium" => "visual_attention_pending_voice_review",
        _ => "silent_unknown",
    };
    let fallback_utterance = match token {
        "xiao_shu::soft_bounce::low" => Some("小舒已跟上。"),
        "xiao_shu::sorting_glow::medium" => Some("小舒正在整理信号。"),
        _ => None,
    };

    json!({
        "token": token,
        "visual_intent": visual_intent,
        "binding_stage": track.get("binding_stage").cloned().unwrap_or(Value::Null),
        "risk_level": track.get("risk_level").cloned().unwrap_or(Value::Null),
        "review_only": track.get("review_only").cloned().unwrap_or_else(|| json!(false)),
        "mode": mode,
        "default_silence": true,
        "display_allowed": true,
        "auto_emit_allowed": false,
        "manual_cli_emit_allowed": real_emit_allowed,
        "http_emit_route": Value::Null,
        "real_emit_surface": if real_emit_allowed {
            json!("agent-bridge avatar cortex-voice-emit")
        } else {
            Value::Null
        },
        "requires_operator_reason": true,
        "requires_policy_override": real_emit_allowed,
        "cooldown_secs": 300,
        "utterance": utterance
            .map(|line| json!(line))
            .or_else(|| fallback_utterance.map(|line| json!(line)))
            .unwrap_or(Value::Null),
        "utterance_source": if has_voice_linkage {
            "voice_linkage_preview"
        } else if fallback_utterance.is_some() {
            "policy_seed"
        } else {
            "none"
        },
        "dry_run_route": dry_run_route,
        "suggested_voice": if real_emit_allowed { json!("Flo (中文（中国大陆）)") } else { Value::Null },
        "suggested_rate": if real_emit_allowed { json!(190) } else { Value::Null },
        "visual_variant": if default_variant == "-" { Value::Null } else { json!(default_variant) },
        "binding_promotable": false,
        "notes": if real_emit_allowed {
            json!("visual motion accepted; voice remains manual CLI-only")
        } else {
            json!("kept silent or display-only until a later explicit review")
        },
    })
}

fn avatar_cortex_voice_policy_from_renderer_view_payload(renderer_view_payload: Value) -> Value {
    let view = renderer_view_payload
        .get("renderer_view")
        .unwrap_or(&Value::Null);
    let rules: Vec<Value> = view
        .get("tracks")
        .and_then(Value::as_array)
        .map(|tracks| {
            tracks
                .iter()
                .map(avatar_cortex_voice_policy_rule_from_track)
                .collect()
        })
        .unwrap_or_default();
    let manual_cli_emit_count = rules
        .iter()
        .filter(|rule| {
            rule.get("manual_cli_emit_allowed")
                .and_then(Value::as_bool)
                .unwrap_or(false)
        })
        .count();
    let display_only_count = rules
        .iter()
        .filter(|rule| {
            !rule
                .get("manual_cli_emit_allowed")
                .and_then(Value::as_bool)
                .unwrap_or(false)
                && rule
                    .get("display_allowed")
                    .and_then(Value::as_bool)
                    .unwrap_or(false)
        })
        .count();
    let auto_emit_count = rules
        .iter()
        .filter(|rule| {
            rule.get("auto_emit_allowed")
                .and_then(Value::as_bool)
                .unwrap_or(false)
        })
        .count();

    let policy = json!({
        "schema": 1,
        "input": "avatar_cortex_renderer_view.renderer_view.tracks + accepted alert_peek voice dogfood",
        "html_route": "/avatar-surface/cortex-voice-policy",
        "renderer_view_route": view
            .get("html_route")
            .cloned()
            .unwrap_or_else(|| json!("/avatar-surface/cortex-renderer-view")),
        "summary": "sparse, purposeful Chinese voice; silent by default; real output is CLI-only",
        "default_voice": "Flo (中文（中国大陆）)",
        "default_rate": 190,
        "default_cooldown_secs": 300,
        "approved_sparse_cases": [
            {
                "case_id": "completion",
                "default_mode": "display_first",
                "example": "小舒已跟上。"
            },
            {
                "case_id": "failure",
                "default_mode": "manual_gate",
                "example": "小舒遇到一个需要你看看的问题。"
            },
            {
                "case_id": "waiting_for_user",
                "default_mode": "manual_gate",
                "example": "小舒需要你看一下。"
            },
            {
                "case_id": "memory_or_session_handoff",
                "default_mode": "display_first",
                "example": "小舒已经记下这一步。"
            },
        ],
        "rules": rules,
        "track_count": rules.len(),
        "manual_cli_emit_count": manual_cli_emit_count,
        "display_only_count": display_only_count,
        "auto_emit_count": auto_emit_count,
        "gate": {
            "explicit_enabled_required": true,
            "operator_reason_required": true,
            "policy_override_required_for_real_emit": true,
            "cooldown_secs": 300,
            "http_emit_route": Value::Null,
            "real_emit_surface": "agent-bridge avatar cortex-voice-emit",
        },
        "acceptance": {
            "read_only": true,
            "dry_run": true,
            "auto_emit_allowed": false,
            "http_emit_route_added": false,
            "approval_writes_allowed": false,
            "records_persisted": false,
            "asset_writes_allowed": false,
            "renderer_mutation_allowed": false,
            "codex_pet_package_mutation_allowed": false,
        },
        "next_step": "use this policy as the source of truth for a future slash command or two-step panel trigger",
    });

    json!({
        "surface": "avatar_cortex_voice_policy",
        "schema": 1,
        "read_only": true,
        "dry_run": true,
        "sidecar_only": true,
        "emits_audio": false,
        "emits_notification": false,
        "mutates_global_substrate": false,
        "writes_files": false,
        "renders_pixels": false,
        "browser_renders_pixels": false,
        "server_side_renders_pixels": false,
        "mutates_renderer": false,
        "codex_pet_package_mutation": false,
        "http_emit_route_added": false,
        "voice_policy": policy,
        "source_renderer_view": renderer_view_payload,
    })
}

pub(crate) fn avatar_cortex_voice_policy_from_status(status: Value) -> Value {
    let renderer_view = avatar_cortex_renderer_view_from_status(status);
    avatar_cortex_voice_policy_from_renderer_view_payload(renderer_view)
}

pub fn avatar_cortex_voice_policy(
    label: Option<&str>,
    heartbeat_label: Option<&str>,
    project: Option<&str>,
    output: Option<&Path>,
) -> Result<Value> {
    let status = avatar_cortex_status(label, heartbeat_label, project, output)?;
    Ok(avatar_cortex_voice_policy_from_status(status))
}

fn avatar_cortex_voice_request_from_policy_payload(
    policy_payload: Value,
    requested_track: Option<&str>,
    project: Option<&str>,
    reason: Option<&str>,
) -> Value {
    let policy = policy_payload.get("voice_policy").unwrap_or(&Value::Null);
    let rules = policy
        .get("rules")
        .and_then(Value::as_array)
        .cloned()
        .unwrap_or_default();
    let requested_track = requested_track.map(str::trim).filter(|s| !s.is_empty());
    let selected_rule = requested_track
        .and_then(|token| {
            rules
                .iter()
                .find(|rule| rule.get("token").and_then(Value::as_str) == Some(token))
        })
        .or_else(|| {
            rules.iter().find(|rule| {
                rule.get("manual_cli_emit_allowed")
                    .and_then(Value::as_bool)
                    .unwrap_or(false)
            })
        });
    let selected_rule = selected_rule.cloned().unwrap_or_else(|| json!({}));
    let token = vstr(selected_rule.get("token")).unwrap_or("xiao_shu::unknown");
    let line = vstr(selected_rule.get("utterance")).unwrap_or("");
    let manual_cli_allowed = selected_rule
        .get("manual_cli_emit_allowed")
        .and_then(Value::as_bool)
        .unwrap_or(false);
    let auto_emit_allowed = selected_rule
        .get("auto_emit_allowed")
        .and_then(Value::as_bool)
        .unwrap_or(false);
    let project = project.unwrap_or("agent-bridge");
    let operator_reason = reason.map(str::trim).filter(|s| !s.is_empty());
    let suggested_reason = format!("confirm-sparse-voice-{token}");
    let command_reason = operator_reason.unwrap_or("<operator-reason>");
    let voice = vstr(selected_rule.get("suggested_voice"))
        .or_else(|| vstr(policy.get("default_voice")))
        .unwrap_or("Flo (中文（中国大陆）)");
    let rate = selected_rule
        .get("suggested_rate")
        .and_then(Value::as_u64)
        .or_else(|| policy.get("default_rate").and_then(Value::as_u64))
        .unwrap_or(190);
    let cooldown_secs = selected_rule
        .get("cooldown_secs")
        .and_then(Value::as_i64)
        .or_else(|| policy.get("default_cooldown_secs").and_then(Value::as_i64))
        .unwrap_or(300);
    let request_state = if manual_cli_allowed && !line.is_empty() {
        "ready_for_operator_confirmation"
    } else if line.is_empty() {
        "blocked_missing_utterance"
    } else {
        "blocked_by_voice_policy"
    };
    let command_args = if manual_cli_allowed && !line.is_empty() {
        json!([
            "agent-bridge",
            "avatar",
            "cortex-voice-emit",
            "--project",
            project,
            "--enabled",
            "--allow-policy-override",
            "--reason",
            command_reason,
            "--preview-text",
            line,
            "--tts-voice",
            voice,
            "--tts-rate",
            rate.to_string(),
        ])
    } else {
        Value::Null
    };
    let command_preview = if manual_cli_allowed && !line.is_empty() {
        json!(format!(
            "agent-bridge avatar cortex-voice-emit --project {project} --enabled --allow-policy-override --reason {command_reason:?} --preview-text {line:?} --tts-voice {voice:?} --tts-rate {rate}"
        ))
    } else {
        Value::Null
    };
    let dry_run_route = selected_rule
        .get("dry_run_route")
        .cloned()
        .unwrap_or(Value::Null);

    let request = json!({
        "schema": 1,
        "input": "avatar_cortex_voice_policy.voice_policy.rules",
        "html_route": "/avatar-surface/cortex-voice-request",
        "policy_route": policy
            .get("html_route")
            .cloned()
            .unwrap_or_else(|| json!("/avatar-surface/cortex-voice-policy")),
        "request_state": request_state,
        "project": project,
        "requested_track": requested_track,
        "selected_token": token,
        "line": if line.is_empty() { Value::Null } else { json!(line) },
        "visual_variant": selected_rule.get("visual_variant").cloned().unwrap_or(Value::Null),
        "mode": selected_rule.get("mode").cloned().unwrap_or(Value::Null),
        "manual_cli_emit_allowed": manual_cli_allowed,
        "auto_emit_allowed": auto_emit_allowed,
        "display_allowed": selected_rule
            .get("display_allowed")
            .cloned()
            .unwrap_or_else(|| json!(false)),
        "requires_second_step": true,
        "requires_operator_confirmation": true,
        "requires_operator_reason": true,
        "operator_reason_present": operator_reason.is_some(),
        "operator_reason": operator_reason,
        "suggested_reason": suggested_reason,
        "requires_policy_override": selected_rule
            .get("requires_policy_override")
            .cloned()
            .unwrap_or_else(|| json!(manual_cli_allowed)),
        "cooldown_secs": cooldown_secs,
        "suggested_voice": voice,
        "suggested_rate": rate,
        "dry_run_route": dry_run_route,
        "real_emit_surface": selected_rule
            .get("real_emit_surface")
            .cloned()
            .unwrap_or_else(|| json!("agent-bridge avatar cortex-voice-emit")),
        "http_emit_route": Value::Null,
        "command_args": command_args,
        "command_preview": command_preview,
        "approval": {
            "writes_approval": false,
            "persists_request_record": false,
            "records_persisted": false,
            "approval_writes_allowed": false,
        },
        "safety": {
            "read_only": true,
            "dry_run": true,
            "emits_audio": false,
            "auto_emit_allowed": false,
            "http_emit_route_added": false,
            "cli_only_real_emit": true,
            "codex_pet_package_mutation_allowed": false,
        },
        "next_step": "operator can copy the CLI args into a future explicit emit step, or a future slash command can present the same request",
    });

    json!({
        "surface": "avatar_cortex_voice_request",
        "schema": 1,
        "read_only": true,
        "dry_run": true,
        "sidecar_only": true,
        "emits_audio": false,
        "emits_notification": false,
        "mutates_global_substrate": false,
        "writes_files": false,
        "renders_pixels": false,
        "browser_renders_pixels": false,
        "server_side_renders_pixels": false,
        "mutates_renderer": false,
        "codex_pet_package_mutation": false,
        "http_emit_route_added": false,
        "writes_approval": false,
        "persists_request_record": false,
        "voice_request": request,
        "source_voice_policy": policy_payload,
    })
}

pub(crate) fn avatar_cortex_voice_request_from_status(
    status: Value,
    requested_track: Option<&str>,
    project: Option<&str>,
    reason: Option<&str>,
) -> Value {
    let policy = avatar_cortex_voice_policy_from_status(status);
    avatar_cortex_voice_request_from_policy_payload(policy, requested_track, project, reason)
}

pub fn avatar_cortex_voice_request(
    label: Option<&str>,
    heartbeat_label: Option<&str>,
    project: Option<&str>,
    output: Option<&Path>,
    requested_track: Option<&str>,
    reason: Option<&str>,
) -> Result<Value> {
    let status = avatar_cortex_status(label, heartbeat_label, project, output)?;
    Ok(avatar_cortex_voice_request_from_status(
        status,
        requested_track,
        project,
        reason,
    ))
}

fn avatar_cortex_voice_confirm_from_request_payload(
    request_payload: Value,
    confirm: bool,
) -> Value {
    let request = request_payload.get("voice_request").unwrap_or(&Value::Null);
    let request_ready = request.get("request_state").and_then(Value::as_str)
        == Some("ready_for_operator_confirmation");
    let operator_reason_present = request
        .get("operator_reason_present")
        .and_then(Value::as_bool)
        .unwrap_or(false);
    let manual_cli_allowed = request
        .get("manual_cli_emit_allowed")
        .and_then(Value::as_bool)
        .unwrap_or(false);
    let command_args_present = request
        .get("command_args")
        .and_then(Value::as_array)
        .map(|args| !args.is_empty())
        .unwrap_or(false);
    let project = vstr(request.get("project")).unwrap_or("agent-bridge");
    let selected_token = vstr(request.get("selected_token")).unwrap_or("xiao_shu::unknown");
    let suggested_voice = vstr(request.get("suggested_voice")).unwrap_or("Flo (中文（中国大陆）)");
    let suggested_rate = request
        .get("suggested_rate")
        .and_then(Value::as_u64)
        .unwrap_or(190);
    let cooldown_secs = request
        .get("cooldown_secs")
        .and_then(Value::as_i64)
        .unwrap_or(300);
    let command_reason = vstr(request.get("operator_reason")).unwrap_or("<operator-reason>");
    let confirmation_state = if !request_ready || !manual_cli_allowed || !command_args_present {
        "blocked_by_request"
    } else if !confirm {
        "waiting_for_operator_confirmation"
    } else if !operator_reason_present {
        "blocked_missing_operator_reason"
    } else {
        "would_execute_cli_emit_if_operator_runs_command"
    };
    let would_execute_cli = confirmation_state == "would_execute_cli_emit_if_operator_runs_command";
    let action_command_args = if request_ready && manual_cli_allowed && command_args_present {
        json!([
            "agent-bridge",
            "avatar",
            "cortex-voice-action",
            "--project",
            project,
            "--track",
            selected_token,
            "--confirm",
            "--emit",
            "--reason",
            command_reason,
            "--cooldown-secs",
            cooldown_secs.to_string(),
            "--tts-voice",
            suggested_voice,
            "--tts-rate",
            suggested_rate.to_string(),
        ])
    } else {
        Value::Null
    };
    let action_command_preview = if request_ready && manual_cli_allowed && command_args_present {
        json!(format!(
            "agent-bridge avatar cortex-voice-action --project {project} --track {selected_token:?} --confirm --emit --reason {command_reason:?} --cooldown-secs {cooldown_secs} --tts-voice {suggested_voice:?} --tts-rate {suggested_rate}"
        ))
    } else {
        Value::Null
    };

    let voice_confirm = json!({
        "schema": 1,
        "input": "avatar_cortex_voice_request.voice_request",
        "html_route": "/avatar-surface/cortex-voice-confirm",
        "request_route": request
            .get("html_route")
            .cloned()
            .unwrap_or_else(|| json!("/avatar-surface/cortex-voice-request")),
        "confirmation_state": confirmation_state,
        "confirm_requested": confirm,
        "would_execute_cli": would_execute_cli,
        "would_emit_audio": false,
        "actual_execution_available_here": false,
        "selected_token": request.get("selected_token").cloned().unwrap_or(Value::Null),
        "line": request.get("line").cloned().unwrap_or(Value::Null),
        "visual_variant": request.get("visual_variant").cloned().unwrap_or(Value::Null),
        "manual_cli_emit_allowed": manual_cli_allowed,
        "auto_emit_allowed": request
            .get("auto_emit_allowed")
            .cloned()
            .unwrap_or_else(|| json!(false)),
        "operator_reason_present": operator_reason_present,
        "operator_reason": request.get("operator_reason").cloned().unwrap_or(Value::Null),
        "suggested_reason": request.get("suggested_reason").cloned().unwrap_or(Value::Null),
        "suggested_voice": request.get("suggested_voice").cloned().unwrap_or(Value::Null),
        "suggested_rate": request.get("suggested_rate").cloned().unwrap_or(Value::Null),
        "http_emit_route": Value::Null,
        "command_args": if would_execute_cli {
            request.get("command_args").cloned().unwrap_or(Value::Null)
        } else {
            Value::Null
        },
        "command_preview": if would_execute_cli {
            request.get("command_preview").cloned().unwrap_or(Value::Null)
        } else {
            Value::Null
        },
        "action_surface": "agent-bridge avatar cortex-voice-action",
        "action_command_args": if would_execute_cli {
            action_command_args.clone()
        } else {
            Value::Null
        },
        "action_command_preview": if would_execute_cli {
            action_command_preview.clone()
        } else {
            Value::Null
        },
        "pending_command_args": request.get("command_args").cloned().unwrap_or(Value::Null),
        "pending_command_preview": request.get("command_preview").cloned().unwrap_or(Value::Null),
        "pending_action_command_args": action_command_args,
        "pending_action_command_preview": action_command_preview,
        "approval": {
            "writes_approval": false,
            "persists_confirmation_record": false,
            "records_persisted": false,
            "approval_writes_allowed": false,
        },
        "safety": {
            "read_only": true,
            "dry_run": true,
            "emits_audio": false,
            "would_emit_audio": false,
            "auto_emit_allowed": false,
            "http_emit_route_added": false,
            "cli_only_real_emit": true,
            "codex_pet_package_mutation_allowed": false,
        },
        "next_step": "future slash command or panel action can display this dry-run confirmation before invoking the CLI-only emit gate",
    });

    json!({
        "surface": "avatar_cortex_voice_confirm",
        "schema": 1,
        "read_only": true,
        "dry_run": true,
        "sidecar_only": true,
        "emits_audio": false,
        "emits_notification": false,
        "mutates_global_substrate": false,
        "writes_files": false,
        "renders_pixels": false,
        "browser_renders_pixels": false,
        "server_side_renders_pixels": false,
        "mutates_renderer": false,
        "codex_pet_package_mutation": false,
        "http_emit_route_added": false,
        "writes_approval": false,
        "persists_confirmation_record": false,
        "voice_confirm": voice_confirm,
        "source_voice_request": request_payload,
    })
}

pub(crate) fn avatar_cortex_voice_confirm_from_status(
    status: Value,
    requested_track: Option<&str>,
    project: Option<&str>,
    reason: Option<&str>,
    confirm: bool,
) -> Value {
    let request = avatar_cortex_voice_request_from_status(status, requested_track, project, reason);
    avatar_cortex_voice_confirm_from_request_payload(request, confirm)
}

pub fn avatar_cortex_voice_confirm(
    label: Option<&str>,
    heartbeat_label: Option<&str>,
    project: Option<&str>,
    output: Option<&Path>,
    requested_track: Option<&str>,
    reason: Option<&str>,
    confirm: bool,
) -> Result<Value> {
    let status = avatar_cortex_status(label, heartbeat_label, project, output)?;
    Ok(avatar_cortex_voice_confirm_from_status(
        status,
        requested_track,
        project,
        reason,
        confirm,
    ))
}

pub fn avatar_cortex_replay(opts: &AvatarCortexReplayOptions<'_>) -> Result<Value> {
    use ab_seed_bridge::snapshot::{self, SnapshotTier};
    use ab_seed_bridge::{SeedBackend, SubstrateConfig};
    use ab_store::embedding::{EmbeddingBackend, HashBackend, OnnxBackend};

    let seed_opts = crate::avatar_seed::AvatarSeedEventsOptions {
        label: opts.label,
        project: opts.project,
        input: opts.input,
        limit: opts.limit,
        include_preview: opts.include_preview,
    };
    let seed_payload = crate::avatar_seed::avatar_seed_events(&seed_opts)?;
    let project = vstr(seed_payload.get("project")).unwrap_or("agent-bridge");
    let label = vstr(seed_payload.get("label")).unwrap_or("avatar-heartbeat");
    let output = match opts.output {
        Some(path) => path.to_path_buf(),
        None => default_avatar_cortex_path(project, label)?,
    };
    if let Some(parent) = output.parent() {
        std::fs::create_dir_all(parent).with_context(|| format!("create {}", parent.display()))?;
    }
    if output.exists() {
        std::fs::remove_file(&output)
            .with_context(|| format!("remove prior cortex snapshot {}", output.display()))?;
    }

    let inner: Arc<dyn EmbeddingBackend> = if opts.use_hash {
        Arc::new(HashBackend)
    } else {
        Arc::new(OnnxBackend)
    };
    let config = SubstrateConfig {
        n: opts.n.clamp(4, 1024),
        d: opts.d.clamp(4, 384),
        state_noise: 0.01,
        lr: 0.01,
    };
    let backend = SeedBackend::wrap_with(inner, config.clone());
    backend.set_snapshot_path(Some(output.clone()));

    let mut perceived = 0usize;
    let mut skipped = 0usize;
    let mut last_key = String::new();
    for record in records(&seed_payload) {
        match feed_record(&backend, record) {
            Some((_text, key)) => {
                perceived += 1;
                last_key = key;
            }
            None => skipped += 1,
        }
    }
    let stats = backend.stats();
    let final_fp = match backend.build_row(SnapshotTier::Long, now_secs()) {
        Some(row) => match snapshot::append_row(&output, row) {
            Ok(fp) => Some(fp),
            Err(err) => {
                return Err(anyhow::anyhow!(
                    "append avatar cortex snapshot {}: {}",
                    output.display(),
                    err
                ));
            }
        },
        None => None,
    };
    let rows = snapshot::read_all(&output).unwrap_or_default();

    Ok(json!({
        "surface": "avatar_cortex_replay",
        "schema": 1,
        "mode": "shadow_only",
        "read_only_source": true,
        "mutates_global_substrate": false,
        "cortex_id": format!("xiao-shu/{project}/{label}"),
        "project": project,
        "label": label,
        "events_path": seed_payload.get("events_path").cloned().unwrap_or(Value::Null),
        "include_preview": opts.include_preview,
        "records_count": records(&seed_payload).len(),
        "perceived": perceived,
        "skipped": skipped,
        "last_key": if last_key.is_empty() { Value::Null } else { json!(last_key) },
        "encoder": if opts.use_hash { "hash" } else { "onnx" },
        "n": config.n,
        "d": config.d,
        "stats": stats,
        "snapshot_path": output.to_string_lossy(),
        "snapshot_rows": rows.len(),
        "latest_long_fingerprint": final_fp,
        "seed_source": "avatar seed-events",
        "aiot_alignment": {
            "cortical_phase": "shadow-only single-stream v0",
            "no_daemon_restart": true,
            "no_sibling_activation": true,
            "future_path": "MultiModalGrid health/voice/session cortex after dry-run evidence"
        }
    }))
}

pub fn avatar_cortex_snapshot_payload(path: &Path) -> Value {
    match ab_seed_bridge::snapshot::read_all(path) {
        Ok(rows) => {
            let latest_long = rows
                .iter()
                .rev()
                .find(|r| matches!(r.tier, ab_seed_bridge::SnapshotTier::Long));
            json!({
                "path": path.to_string_lossy(),
                "exists": path.exists(),
                "file_bytes": std::fs::metadata(path).ok().map(|m| m.len()),
                "total_rows": rows.len(),
                "long_rows": rows.iter().filter(|r| matches!(r.tier, ab_seed_bridge::SnapshotTier::Long)).count(),
                "hot_rows": rows.iter().filter(|r| matches!(r.tier, ab_seed_bridge::SnapshotTier::Hot)).count(),
                "latest_long": latest_long.map(|row| {
                    json!({
                        "step": row.step,
                        "cycle_ts": row.cycle_ts,
                        "fingerprint": ab_seed_bridge::snapshot::fingerprint(row),
                    })
                }),
            })
        }
        Err(err) => json!({
            "path": path.to_string_lossy(),
            "exists": path.exists(),
            "error": err.to_string(),
        }),
    }
}

fn avatar_cortex_launchd_payload(label: &str) -> Value {
    match crate::avatar_health::probe_launchd(label) {
        Ok(launchd) => json!({
            "loaded": launchd.loaded,
            "domain": launchd.domain,
            "target": launchd.target,
            "state": launchd.state,
            "runs": launchd.runs,
            "last_exit_code": launchd.last_exit_code,
            "run_interval_secs": launchd.run_interval_secs,
            "error": launchd.error,
        }),
        Err(err) => json!({
            "loaded": false,
            "domain": Value::Null,
            "target": label,
            "state": Value::Null,
            "runs": Value::Null,
            "last_exit_code": Value::Null,
            "run_interval_secs": Value::Null,
            "error": err.to_string(),
            "degraded": true,
            "degraded_reason": "launchd_probe_unavailable",
            "platform": std::env::consts::OS,
        }),
    }
}

pub fn avatar_cortex_status(
    label: Option<&str>,
    heartbeat_label: Option<&str>,
    project: Option<&str>,
    output: Option<&Path>,
) -> Result<Value> {
    let project = project.unwrap_or("agent-bridge");
    let label = cortex_runner_label(label, project);
    let heartbeat_label = crate::avatar_health::heartbeat_label(heartbeat_label, project);
    let snapshot_path = match output {
        Some(path) => path.to_path_buf(),
        None => default_avatar_cortex_path(project, &heartbeat_label)?,
    };
    let snapshot = avatar_cortex_snapshot_payload(&snapshot_path);
    let events = avatar_cortex_events_summary(&heartbeat_label, project);
    let trend = avatar_cortex_trend(&snapshot, &events);
    let launchd = avatar_cortex_launchd_payload(&label);
    Ok(json!({
        "surface": "avatar_cortex_status",
        "schema": 1,
        "project": project,
        "label": label,
        "heartbeat_label": heartbeat_label,
        "launchd": launchd,
        "snapshot": snapshot,
        "events": events,
        "trend": trend,
        "read_only": true,
        "mutates_global_substrate": false,
    }))
}

fn avatar_cortex_voice_preview_from_status(status: Value) -> Value {
    let language_preview = avatar_cortex_language_preview_from_status(status.clone());
    let language = language_preview
        .get("language")
        .cloned()
        .unwrap_or(Value::Null);
    let trend = status.get("trend").unwrap_or(&Value::Null);
    let learning = trend.get("learning_state").cloned().unwrap_or(Value::Null);
    let policy = trend.get("behavior_policy").cloned().unwrap_or(Value::Null);
    let voice = policy.get("voice").cloned().unwrap_or(Value::Null);
    let notification = policy.get("notification").cloned().unwrap_or(Value::Null);
    let preview_text = language
        .get("utterance")
        .and_then(Value::as_str)
        .or_else(|| voice.get("preview").and_then(Value::as_str))
        .unwrap_or("小舒当前保持安静。");
    json!({
        "surface": "avatar_cortex_voice_preview",
        "schema": 1,
        "read_only": true,
        "emits_audio": false,
        "emits_notification": false,
        "mutates_global_substrate": false,
        "project": status.get("project").cloned().unwrap_or(Value::Null),
        "label": status.get("label").cloned().unwrap_or(Value::Null),
        "heartbeat_label": status.get("heartbeat_label").cloned().unwrap_or(Value::Null),
        "learning_state": learning,
        "behavior_policy": policy,
        "language": language,
        "preview": {
            "text": preview_text,
            "voice_allowed": voice.get("allowed").cloned().unwrap_or(json!(false)),
            "voice_reason": voice.get("reason").cloned().unwrap_or(json!("sparse_voice_policy")),
            "notification_allowed": notification.get("allowed").cloned().unwrap_or(json!(false)),
            "notification_reason": notification.get("reason").cloned().unwrap_or(json!("read_only_panel_policy")),
            "requires_explicit_emit_gate": true,
        },
        "source_status": {
            "surface": status.get("surface").cloned().unwrap_or(Value::Null),
            "launchd": status.get("launchd").cloned().unwrap_or(Value::Null),
            "snapshot": status.get("snapshot").cloned().unwrap_or(Value::Null),
            "events": status.get("events").cloned().unwrap_or(Value::Null),
            "trend": trend.clone(),
        }
    })
}

pub fn avatar_cortex_voice_preview(
    label: Option<&str>,
    heartbeat_label: Option<&str>,
    project: Option<&str>,
    output: Option<&Path>,
) -> Result<Value> {
    let status = avatar_cortex_status(label, heartbeat_label, project, output)?;
    Ok(avatar_cortex_voice_preview_from_status(status))
}

fn avatar_cortex_voice_gate_from_preview(
    preview: Value,
    enabled: bool,
    force: bool,
    cooldown_secs: i64,
    reason: Option<&str>,
) -> Value {
    avatar_cortex_voice_gate_payload(
        preview,
        enabled,
        force,
        cooldown_secs,
        reason,
        false,
        None,
        true,
        now_secs(),
    )
}

#[allow(clippy::too_many_arguments)]
fn avatar_cortex_voice_gate_payload(
    preview: Value,
    enabled: bool,
    force: bool,
    cooldown_secs: i64,
    reason: Option<&str>,
    allow_policy_override: bool,
    last_emit_at: Option<i64>,
    dry_run: bool,
    now: i64,
) -> Value {
    let preview_block = preview.get("preview").unwrap_or(&Value::Null);
    let preview_text = vstr(preview_block.get("text")).unwrap_or("").trim();
    let operator_reason = reason.map(str::trim).filter(|s| !s.is_empty());
    let voice_allowed = vbool(preview_block.get("voice_allowed")).unwrap_or(false);
    let explicit_gate_required =
        vbool(preview_block.get("requires_explicit_emit_gate")).unwrap_or(true);
    let cooldown_secs = cooldown_secs.clamp(0, 86_400);
    let cooldown_active = last_emit_at
        .map(|then| cooldown_secs > 0 && now >= then && now - then < cooldown_secs)
        .unwrap_or(false);
    let cooldown_clear = force || !cooldown_active;
    let next_allowed_at = last_emit_at.map(|then| then.saturating_add(cooldown_secs));

    let mut blocked_reasons = Vec::new();
    if !enabled {
        blocked_reasons.push("gate_disabled");
    }
    if operator_reason.is_none() {
        blocked_reasons.push("missing_reason");
    }
    if preview_text.is_empty() {
        blocked_reasons.push("missing_preview_text");
    }
    if !explicit_gate_required {
        blocked_reasons.push("explicit_gate_contract_absent");
    }
    if !voice_allowed && !allow_policy_override {
        blocked_reasons.push("policy_voice_disabled");
    }
    if !cooldown_clear {
        blocked_reasons.push("cooldown_active");
    }

    let would_emit = blocked_reasons.is_empty();
    json!({
        "surface": if dry_run { "avatar_cortex_voice_gate_dry_run" } else { "avatar_cortex_voice_gate" },
        "schema": 1,
        "generated_at": now,
        "read_only": dry_run,
        "dry_run": dry_run,
        "would_emit": would_emit,
        "emits_audio": false,
        "emits_notification": false,
        "mutates_global_substrate": false,
        "gate": {
            "enabled": enabled,
            "force": force,
            "allow_policy_override": allow_policy_override,
            "operator_reason": operator_reason,
            "decision": if would_emit && dry_run { "would_emit_if_not_dry_run" } else if would_emit { "emit_allowed" } else { "blocked" },
            "blocked": !would_emit,
            "blocked_reasons": blocked_reasons,
        },
        "required": {
            "explicit_enabled": enabled,
            "operator_reason_present": operator_reason.is_some(),
            "preview_text_present": !preview_text.is_empty(),
            "voice_policy_allowed": voice_allowed,
            "policy_override_allowed": allow_policy_override,
            "explicit_emit_gate_required": explicit_gate_required,
            "cooldown_clear": cooldown_clear,
        },
        "cooldown": {
            "cooldown_secs": cooldown_secs,
            "active": cooldown_active,
            "last_emit_at": last_emit_at,
            "next_allowed_at": next_allowed_at,
            "stateful_cooldown": last_emit_at.is_some(),
            "dry_run_no_state_mutation": dry_run,
        },
        "preview": preview_block.clone(),
        "preview_text_override": preview
            .get("preview_text_override")
            .cloned()
            .unwrap_or_else(|| json!({"provided": false})),
        "learning_state": preview.get("learning_state").cloned().unwrap_or(Value::Null),
        "behavior_policy": preview.get("behavior_policy").cloned().unwrap_or(Value::Null),
        "source_preview": preview,
    })
}

fn avatar_cortex_voice_preview_with_override(
    mut preview: Value,
    preview_text: Option<&str>,
    source: &str,
) -> Value {
    let Some(preview_text) = preview_text.map(str::trim).filter(|text| !text.is_empty()) else {
        return preview;
    };
    let mut preview_block = preview.get("preview").cloned().unwrap_or_else(|| json!({}));
    if let Some(preview_obj) = preview_block.as_object_mut() {
        preview_obj.insert("text".to_string(), json!(preview_text));
        preview_obj.insert(
            "source".to_string(),
            json!("operator_preview_text_override"),
        );
    }
    if let Some(preview_obj) = preview.as_object_mut() {
        preview_obj.insert("preview".to_string(), preview_block);
        preview_obj.insert(
            "preview_text_override".to_string(),
            json!({
                "provided": true,
                "source": source,
                "emits_audio": false,
            }),
        );
    }
    preview
}

pub fn avatar_cortex_voice_gate_dry_run(opts: &AvatarCortexVoiceGateOptions<'_>) -> Result<Value> {
    let preview = avatar_cortex_voice_preview_with_override(
        avatar_cortex_voice_preview(opts.label, opts.heartbeat_label, opts.project, opts.output)?,
        opts.preview_text,
        "voice_gate_query",
    );
    Ok(avatar_cortex_voice_gate_from_preview(
        preview,
        opts.enabled,
        opts.force,
        opts.cooldown_secs,
        opts.reason,
    ))
}

fn tts_voice_or_env(voice: Option<&str>) -> Option<String> {
    voice
        .map(str::trim)
        .filter(|v| !v.is_empty())
        .map(ToString::to_string)
        .or_else(|| {
            std::env::var("AB_PET_TTS_VOICE")
                .ok()
                .map(|v| v.trim().to_string())
                .filter(|v| !v.is_empty())
        })
}

fn tts_rate_or_env(rate: Option<u64>) -> Option<u64> {
    rate.or_else(|| {
        std::env::var("AB_PET_TTS_RATE")
            .ok()
            .and_then(|v| v.trim().parse::<u64>().ok())
    })
    .map(|rate| rate.clamp(80, 300))
}

pub fn avatar_cortex_voice_emit(opts: &AvatarCortexVoiceEmitOptions<'_>) -> Result<Value> {
    let preview = avatar_cortex_voice_preview_with_override(
        avatar_cortex_voice_preview(opts.label, opts.heartbeat_label, opts.project, opts.output)?,
        opts.preview_text,
        "voice_emit_cli",
    );
    let project = vstr(preview.get("project"))
        .or(opts.project)
        .unwrap_or("agent-bridge")
        .to_string();
    let heartbeat_label = vstr(preview.get("heartbeat_label"))
        .or(opts.heartbeat_label)
        .unwrap_or("avatar-heartbeat")
        .to_string();
    let (state_path, events_path) = avatar_cortex_voice_paths(&project, &heartbeat_label)?;
    let state = read_json(&state_path);
    let last_emit_at = vi64(state.get("last_emit_at"));
    let now = now_secs();
    let gate = avatar_cortex_voice_gate_payload(
        preview,
        opts.enabled,
        opts.force,
        opts.cooldown_secs,
        opts.reason,
        opts.allow_policy_override,
        last_emit_at,
        false,
        now,
    );
    let line = vstr(gate.get("preview").and_then(|v| v.get("text")))
        .unwrap_or("")
        .to_string();
    let should_emit = vbool(gate.get("would_emit")).unwrap_or(false);
    let tts_voice = tts_voice_or_env(opts.tts_voice);
    let tts_rate = tts_rate_or_env(opts.tts_rate);
    let mut tts = Value::Null;
    let mut emitted = false;
    if should_emit {
        tts = crate::avatar_alert::emit_tts(&line, tts_voice.as_deref(), tts_rate);
        emitted = vbool(tts.get("ok")).unwrap_or(false);
    }

    if emitted {
        let receipt = json!({
            "schema": 1,
            "surface": "avatar_cortex_voice_emit_receipt",
            "project": project,
            "heartbeat_label": heartbeat_label,
            "line": line,
            "reason": opts.reason.map(str::trim).filter(|s| !s.is_empty()),
            "policy_override": opts.allow_policy_override,
            "tts_voice": tts_voice,
            "tts_rate": tts_rate,
            "last_emit_at": now,
            "cooldown_secs": gate.get("cooldown").and_then(|v| vi64(v.get("cooldown_secs"))).unwrap_or(300),
            "source": "avatar_cortex_voice_emit",
        });
        write_json(&state_path, &receipt)?;
    }

    let event = json!({
        "surface": "avatar_cortex_voice_emit",
        "schema": 1,
        "generated_at": now,
        "project": project,
        "heartbeat_label": heartbeat_label,
        "line": line,
        "requested": opts.enabled,
        "would_emit": should_emit,
        "emitted": emitted,
        "emits_audio": should_emit,
        "emits_notification": false,
        "reason": opts.reason.map(str::trim).filter(|s| !s.is_empty()),
        "allow_policy_override": opts.allow_policy_override,
        "state_path": state_path.to_string_lossy(),
        "events_path": events_path.to_string_lossy(),
        "gate": gate,
        "tts": tts,
    });
    append_jsonl(&events_path, &event)?;

    Ok(json!({
        "surface": "avatar_cortex_voice_emit",
        "schema": 1,
        "generated_at": now,
        "cli_only": true,
        "http_available": false,
        "dry_run": false,
        "read_only": false,
        "mutates_global_substrate": false,
        "writes_cooldown_state": emitted,
        "would_emit": should_emit,
        "emitted": emitted,
        "emits_audio": should_emit,
        "emits_notification": false,
        "state_path": state_path.to_string_lossy(),
        "events_path": events_path.to_string_lossy(),
        "gate": event.get("gate").cloned().unwrap_or(Value::Null),
        "tts": event.get("tts").cloned().unwrap_or(Value::Null),
        "event": event,
    }))
}

fn avatar_cortex_voice_action_from_confirm_payload(
    confirm_payload: Value,
    opts: &AvatarCortexVoiceActionOptions<'_>,
) -> Result<Value> {
    let confirm = confirm_payload.get("voice_confirm").unwrap_or(&Value::Null);
    let confirmation_state =
        vstr(confirm.get("confirmation_state")).unwrap_or("blocked_by_request");
    let confirmed = confirmation_state == "would_execute_cli_emit_if_operator_runs_command";
    let operator_reason = opts.reason.map(str::trim).filter(|s| !s.is_empty());
    let line = vstr(confirm.get("line")).unwrap_or("").to_string();
    let selected_token = vstr(confirm.get("selected_token")).unwrap_or("xiao_shu::unknown");
    let project = opts.project.unwrap_or_else(|| {
        vstr(confirm.get("project"))
            .or_else(|| {
                confirm_payload
                    .get("source_voice_request")
                    .and_then(|request_payload| request_payload.get("voice_request"))
                    .and_then(|request| vstr(request.get("project")))
            })
            .unwrap_or("agent-bridge")
    });
    let tts_voice = opts
        .tts_voice
        .or_else(|| vstr(confirm.get("suggested_voice")));
    let tts_rate = opts
        .tts_rate
        .or_else(|| confirm.get("suggested_rate").and_then(Value::as_u64));

    let mut blocked_reasons = Vec::new();
    if !opts.confirm {
        blocked_reasons.push("confirm_flag_missing");
    }
    if !confirmed {
        blocked_reasons.push("confirmation_not_ready");
    }
    if !opts.emit {
        blocked_reasons.push("emit_flag_missing");
    }
    if operator_reason.is_none() {
        blocked_reasons.push("missing_reason");
    }
    if line.is_empty() {
        blocked_reasons.push("missing_line");
    }
    let actual_emit_invoked = blocked_reasons.is_empty();
    let emit_payload = if actual_emit_invoked {
        let emit_opts = AvatarCortexVoiceEmitOptions {
            label: opts.label,
            heartbeat_label: opts.heartbeat_label,
            project: Some(project),
            output: opts.output,
            preview_text: Some(line.as_str()),
            enabled: true,
            force: opts.force,
            cooldown_secs: opts.cooldown_secs,
            reason: opts.reason,
            allow_policy_override: true,
            tts_voice,
            tts_rate,
        };
        avatar_cortex_voice_emit(&emit_opts)?
    } else {
        Value::Null
    };
    let emitted = vbool(emit_payload.get("emitted")).unwrap_or(false);
    let would_emit = vbool(emit_payload.get("would_emit")).unwrap_or(false);
    let emits_audio = vbool(emit_payload.get("emits_audio")).unwrap_or(false);
    let command_preview = confirm
        .get("action_command_preview")
        .filter(|value| !value.is_null())
        .cloned()
        .or_else(|| {
            confirm
                .get("pending_action_command_preview")
                .filter(|value| !value.is_null())
                .cloned()
        })
        .unwrap_or(Value::Null);
    let command_args = confirm
        .get("action_command_args")
        .filter(|value| !value.is_null())
        .cloned()
        .or_else(|| {
            confirm
                .get("pending_action_command_args")
                .filter(|value| !value.is_null())
                .cloned()
        })
        .unwrap_or(Value::Null);

    Ok(json!({
        "surface": "avatar_cortex_voice_action",
        "schema": 1,
        "generated_at": now_secs(),
        "cli_only": true,
        "http_available": false,
        "read_only": !actual_emit_invoked,
        "dry_run": !actual_emit_invoked,
        "sidecar_only": true,
        "mutates_global_substrate": false,
        "writes_files": actual_emit_invoked,
        "writes_cooldown_state": emitted,
        "codex_pet_package_mutation": false,
        "requested_emit": opts.emit,
        "actual_emit_invoked": actual_emit_invoked,
        "would_emit": would_emit,
        "emitted": emitted,
        "emits_audio": emits_audio,
        "emits_notification": false,
        "action": {
            "confirmation_state": confirmation_state,
            "confirmed": confirmed,
            "confirm_flag": opts.confirm,
            "emit_flag": opts.emit,
            "blocked": !actual_emit_invoked,
            "blocked_reasons": blocked_reasons,
            "selected_token": selected_token,
            "line": line,
            "reason_present": operator_reason.is_some(),
            "allow_policy_override": actual_emit_invoked,
            "cooldown_secs": opts.cooldown_secs,
            "force": opts.force,
            "tts_voice": tts_voice,
            "tts_rate": tts_rate,
            "command_args": command_args,
            "command_preview": command_preview,
        },
        "source_voice_confirm": confirm_payload,
        "source_voice_emit": emit_payload,
    }))
}

pub fn avatar_cortex_voice_action(opts: &AvatarCortexVoiceActionOptions<'_>) -> Result<Value> {
    let confirm_payload = avatar_cortex_voice_confirm(
        opts.label,
        opts.heartbeat_label,
        opts.project,
        opts.output,
        opts.requested_track,
        opts.reason,
        opts.confirm,
    )?;
    avatar_cortex_voice_action_from_confirm_payload(confirm_payload, opts)
}

#[allow(clippy::too_many_arguments)]
fn avatar_cortex_voice_action_preview_from_confirm_payload(
    confirm_payload: Value,
    opts: &AvatarCortexVoiceActionPreviewOptions<'_>,
    last_emit_at: Option<i64>,
    state_path: Option<&Path>,
    events_path: Option<&Path>,
    now: i64,
) -> Value {
    let confirm = confirm_payload.get("voice_confirm").unwrap_or(&Value::Null);
    let confirmation_state =
        vstr(confirm.get("confirmation_state")).unwrap_or("blocked_by_request");
    let confirmed = confirmation_state == "would_execute_cli_emit_if_operator_runs_command";
    let operator_reason = opts.reason.map(str::trim).filter(|s| !s.is_empty());
    let line = vstr(confirm.get("line")).unwrap_or("");
    let selected_token = vstr(confirm.get("selected_token")).unwrap_or("xiao_shu::unknown");
    let project = opts.project.unwrap_or_else(|| {
        confirm_payload
            .get("source_voice_request")
            .and_then(|request_payload| request_payload.get("voice_request"))
            .and_then(|request| vstr(request.get("project")))
            .unwrap_or("agent-bridge")
    });
    let heartbeat_label = crate::avatar_health::heartbeat_label(opts.heartbeat_label, project);
    let tts_voice = opts
        .tts_voice
        .or_else(|| vstr(confirm.get("suggested_voice")));
    let tts_rate = opts
        .tts_rate
        .or_else(|| confirm.get("suggested_rate").and_then(Value::as_u64));
    let preview = json!({
        "surface": "avatar_cortex_voice_action_preview_input",
        "schema": 1,
        "project": project,
        "heartbeat_label": heartbeat_label,
        "preview": {
            "text": line,
            "voice_allowed": false,
            "requires_explicit_emit_gate": true,
            "source": "voice_action_preview_confirm",
        },
        "preview_text_override": {
            "provided": true,
            "source": "voice_action_preview",
            "emits_audio": false,
        },
    });
    let gate = avatar_cortex_voice_gate_payload(
        preview,
        opts.confirm,
        opts.force,
        opts.cooldown_secs,
        opts.reason,
        true,
        last_emit_at,
        true,
        now,
    );
    let mut blocked_reasons = Vec::<String>::new();
    fn push_reason(reasons: &mut Vec<String>, reason: &str) {
        if !reasons.iter().any(|existing| existing == reason) {
            reasons.push(reason.to_string());
        }
    }
    if !opts.confirm {
        push_reason(&mut blocked_reasons, "confirm_flag_missing");
    }
    if !confirmed {
        push_reason(&mut blocked_reasons, "confirmation_not_ready");
    }
    if line.is_empty() {
        push_reason(&mut blocked_reasons, "missing_line");
    }
    if let Some(gate_reasons) = gate
        .get("gate")
        .and_then(|gate| gate.get("blocked_reasons"))
        .and_then(Value::as_array)
    {
        for reason in gate_reasons.iter().filter_map(Value::as_str) {
            push_reason(&mut blocked_reasons, reason);
        }
    }
    let gate_would_emit = vbool(gate.get("would_emit")).unwrap_or(false);
    let ready_to_emit_now = blocked_reasons.is_empty() && confirmed && gate_would_emit;
    let command_preview = confirm
        .get("action_command_preview")
        .filter(|value| !value.is_null())
        .cloned()
        .or_else(|| {
            confirm
                .get("pending_action_command_preview")
                .filter(|value| !value.is_null())
                .cloned()
        })
        .unwrap_or(Value::Null);
    let command_args = confirm
        .get("action_command_args")
        .filter(|value| !value.is_null())
        .cloned()
        .or_else(|| {
            confirm
                .get("pending_action_command_args")
                .filter(|value| !value.is_null())
                .cloned()
        })
        .unwrap_or(Value::Null);

    json!({
        "surface": "avatar_cortex_voice_action_preview",
        "schema": 1,
        "generated_at": now,
        "read_only": true,
        "dry_run": true,
        "cli_only_real_emit": true,
        "http_available": true,
        "http_emit_route_added": false,
        "actual_emit_invoked": false,
        "writes_files": false,
        "writes_cooldown_state": false,
        "codex_pet_package_mutation": false,
        "mutates_global_substrate": false,
        "emits_audio": false,
        "would_emit_audio": ready_to_emit_now,
        "emits_notification": false,
        "action_preview": {
            "confirmation_state": confirmation_state,
            "confirmed": confirmed,
            "confirm_flag": opts.confirm,
            "force": opts.force,
            "cooldown_secs": opts.cooldown_secs,
            "ready_to_emit_now": ready_to_emit_now,
            "would_emit_if_operator_runs_command": ready_to_emit_now,
            "blocked": !ready_to_emit_now,
            "blocked_reasons": blocked_reasons,
            "selected_token": selected_token,
            "line": line,
            "reason_present": operator_reason.is_some(),
            "allow_policy_override": true,
            "tts_voice": tts_voice,
            "tts_rate": tts_rate,
            "state_path": state_path.map(|path| path.to_string_lossy().to_string()),
            "events_path": events_path.map(|path| path.to_string_lossy().to_string()),
            "command_args": command_args,
            "command_preview": command_preview,
        },
        "gate_dry_run": gate,
        "source_voice_confirm": confirm_payload,
    })
}

#[allow(clippy::too_many_arguments)]
#[cfg(test)]
pub(crate) fn avatar_cortex_voice_action_preview_from_status(
    status: Value,
    requested_track: Option<&str>,
    project: Option<&str>,
    reason: Option<&str>,
    confirm: bool,
    force: bool,
    cooldown_secs: i64,
    last_emit_at: Option<i64>,
) -> Value {
    let confirm_payload =
        avatar_cortex_voice_confirm_from_status(status, requested_track, project, reason, confirm);
    let opts = AvatarCortexVoiceActionPreviewOptions {
        label: None,
        heartbeat_label: None,
        project,
        output: None,
        requested_track,
        reason,
        confirm,
        force,
        cooldown_secs,
        tts_voice: None,
        tts_rate: None,
    };
    avatar_cortex_voice_action_preview_from_confirm_payload(
        confirm_payload,
        &opts,
        last_emit_at,
        None,
        None,
        now_secs(),
    )
}

pub fn avatar_cortex_voice_action_preview(
    opts: &AvatarCortexVoiceActionPreviewOptions<'_>,
) -> Result<Value> {
    let confirm_payload = avatar_cortex_voice_confirm(
        opts.label,
        opts.heartbeat_label,
        opts.project,
        opts.output,
        opts.requested_track,
        opts.reason,
        opts.confirm,
    )?;
    let project = opts.project.unwrap_or_else(|| {
        confirm_payload
            .get("source_voice_request")
            .and_then(|request_payload| request_payload.get("voice_request"))
            .and_then(|request| vstr(request.get("project")))
            .unwrap_or("agent-bridge")
    });
    let heartbeat_label = crate::avatar_health::heartbeat_label(opts.heartbeat_label, project);
    let (state_path, events_path) = avatar_cortex_voice_paths(project, &heartbeat_label)?;
    let state = read_json(&state_path);
    let last_emit_at = vi64(state.get("last_emit_at"));
    Ok(avatar_cortex_voice_action_preview_from_confirm_payload(
        confirm_payload,
        opts,
        last_emit_at,
        Some(&state_path),
        Some(&events_path),
        now_secs(),
    ))
}

fn xiao_shu_action_intent_supported(intent: &str) -> bool {
    matches!(
        intent,
        "voice_alert" | "alert_peek" | "attention" | "review_attention" | "xiao_shu_alert_peek"
    )
}

fn strip_recursive_provenance(value: &Value) -> Value {
    match value {
        Value::Object(map) => {
            let mut compact = serde_json::Map::new();
            for (key, child) in map {
                if key.starts_with("source_") {
                    continue;
                }
                compact.insert(key.clone(), strip_recursive_provenance(child));
            }
            Value::Object(compact)
        }
        Value::Array(items) => Value::Array(items.iter().map(strip_recursive_provenance).collect()),
        _ => value.clone(),
    }
}

fn xiao_shu_action_downstream_preview_payload(
    action_preview_payload: &Value,
    include_details: bool,
) -> Value {
    if include_details {
        return action_preview_payload.clone();
    }

    let mut compact = strip_recursive_provenance(action_preview_payload);
    if let Some(obj) = compact.as_object_mut() {
        obj.insert("compact".to_string(), json!(true));
        obj.insert("include_details".to_string(), json!(false));
        obj.insert(
            "provenance_ref".to_string(),
            json!({
                "full_available_with_details": true,
                "omitted": "recursive source_* provenance",
            }),
        );
    }
    compact
}

fn xiao_shu_action_degraded_preview(
    error: String,
    opts: &AvatarCortexVoiceActionPreviewOptions<'_>,
    project: &str,
    track: &str,
    reason: &str,
) -> Value {
    let heartbeat_label = crate::avatar_health::heartbeat_label(opts.heartbeat_label, project);
    json!({
        "surface": "avatar_cortex_voice_action_preview",
        "schema": 1,
        "generated_at": now_secs(),
        "read_only": true,
        "dry_run": true,
        "degraded": true,
        "degraded_reason": "downstream_preview_unavailable",
        "error": error,
        "cli_only_real_emit": true,
        "http_available": true,
        "http_emit_route_added": false,
        "actual_emit_invoked": false,
        "writes_files": false,
        "writes_cooldown_state": false,
        "codex_pet_package_mutation": false,
        "mutates_global_substrate": false,
        "emits_audio": false,
        "would_emit_audio": false,
        "emits_notification": false,
        "action_preview": {
            "confirmation_state": "blocked_by_downstream_preview",
            "confirmed": false,
            "confirm_flag": opts.confirm,
            "force": opts.force,
            "cooldown_secs": opts.cooldown_secs,
            "ready_to_emit_now": false,
            "would_emit_if_operator_runs_command": false,
            "blocked": true,
            "blocked_reasons": ["downstream_preview_unavailable"],
            "selected_token": track,
            "line": Value::Null,
            "reason_present": !reason.trim().is_empty(),
            "reason": reason,
            "allow_policy_override": false,
            "tts_voice": opts.tts_voice,
            "tts_rate": opts.tts_rate,
            "state_path": Value::Null,
            "events_path": Value::Null,
            "command_args": Value::Null,
            "command_preview": Value::Null,
        },
        "gate_dry_run": {
            "surface": "avatar_cortex_voice_gate",
            "read_only": true,
            "dry_run": true,
            "would_emit": false,
            "emits_audio": false,
            "blocked_reasons": ["downstream_preview_unavailable"],
            "heartbeat_label": heartbeat_label,
        },
        "source_voice_confirm": Value::Null,
    })
}

fn xiao_shu_action_request_from_preview(
    action_preview_payload: Value,
    opts: &XiaoShuActionRequestOptions<'_>,
    project: &str,
    intent: &str,
    track: &str,
    reason: &str,
) -> Value {
    let actor = opts
        .actor
        .map(str::trim)
        .filter(|actor| !actor.is_empty())
        .unwrap_or("llm");
    let message = opts
        .message
        .map(str::trim)
        .filter(|message| !message.is_empty());
    let supported_intent = xiao_shu_action_intent_supported(intent);
    let action = action_preview_payload
        .get("action_preview")
        .unwrap_or(&Value::Null);
    let downstream_ready = vbool(action.get("ready_to_emit_now")).unwrap_or(false);
    let request_state = if !supported_intent {
        "blocked_unsupported_intent"
    } else if !opts.confirm {
        "requires_human_confirmation"
    } else if downstream_ready {
        "ready_for_local_cli_emit"
    } else {
        "confirmed_but_blocked"
    };
    let preview_command = format!(
        "agent-bridge avatar cortex-voice-action-preview --project {project} --track {track:?} --reason {reason:?} --confirm"
    );
    let message_arg = message
        .map(|message| format!(" --message {message:?}"))
        .unwrap_or_default();
    let request_command = format!(
        "agent-bridge avatar xiao-shu-action-request --project {project} --actor {actor:?} --intent {intent:?}{message_arg} --reason {reason:?}"
    );
    let confirm_request_command = format!(
        "agent-bridge avatar xiao-shu-action-request --project {project} --actor {actor:?} --intent {intent:?}{message_arg} --reason {reason:?} --confirm"
    );
    let emit_command = action
        .get("command_preview")
        .cloned()
        .unwrap_or(Value::Null);
    let mut blocked_reasons = Vec::<String>::new();
    if !supported_intent {
        blocked_reasons.push("unsupported_intent".to_string());
    }
    if !opts.confirm {
        blocked_reasons.push("human_confirmation_required".to_string());
    }
    if let Some(reasons) = action.get("blocked_reasons").and_then(Value::as_array) {
        for reason in reasons.iter().filter_map(Value::as_str) {
            if !blocked_reasons.iter().any(|existing| existing == reason) {
                blocked_reasons.push(reason.to_string());
            }
        }
    }
    let downstream_action_preview =
        xiao_shu_action_downstream_preview_payload(&action_preview_payload, opts.include_details);
    let action_request = json!({
        "target": "xiao-shu",
        "actor": actor,
        "intent": intent,
        "message": message,
        "request_state": request_state,
        "supported_intent": supported_intent,
        "mapped_surface": "avatar_cortex_voice_action_preview",
        "mapped_track": track,
        "line": action.get("line").cloned().unwrap_or(Value::Null),
        "reason": reason,
        "requires_human_confirmation": true,
        "human_confirmation_present": opts.confirm,
        "real_emit_requires_local_cli": true,
        "direct_llm_emit_allowed": false,
        "ready_for_local_cli_emit": supported_intent && opts.confirm && downstream_ready,
        "blocked": !supported_intent || !opts.confirm || !downstream_ready,
        "blocked_reasons": blocked_reasons,
        "request_command": request_command,
        "confirm_request_command": confirm_request_command,
        "preview_command": preview_command,
        "emit_command": emit_command,
        "next_step": "show this request to the operator; only a local CLI confirmation may run the emitted command",
    });
    let policy = json!({
        "llm_can_request": true,
        "llm_can_directly_control_pet": false,
        "llm_can_emit_audio": false,
        "operator_confirmation_required": true,
        "local_cli_emit_only": true,
        "http_emit_route_allowed": false,
    });

    let queue_summary = xiao_shu_action_request_queue_summary(Some(project))
        .unwrap_or_else(|e| {
            json!({
                "read_only": true,
                "error": e.to_string(),
            })
        });

    json!({
        "surface": "xiao_shu_action_request",
        "schema": 1,
        "generated_at": now_secs(),
        "read_only": true,
        "dry_run": true,
        "llm_safe": true,
        "sidecar_only": true,
        "direct_pet_control_allowed": false,
        "actual_emit_invoked": false,
        "emits_audio": false,
        "emits_notification": false,
        "http_available": true,
        "http_emit_route_added": false,
        "writes_files": false,
        "writes_request_record": false,
        "writes_cooldown_state": false,
        "codex_pet_package_mutation": false,
        "mutates_global_substrate": false,
        "include_details": opts.include_details,
        "compact_downstream_action_preview": !opts.include_details,
        "action_request": action_request,
        "policy": policy,
        "downstream_action_preview": downstream_action_preview,
        "queue_summary": queue_summary,
    })
}

pub fn xiao_shu_action_request(opts: &XiaoShuActionRequestOptions<'_>) -> Result<Value> {
    let project = opts.project.unwrap_or("agent-bridge");
    let intent = opts
        .intent
        .map(str::trim)
        .filter(|intent| !intent.is_empty())
        .unwrap_or("voice_alert")
        .to_string();
    let track = opts
        .requested_track
        .map(str::trim)
        .filter(|track| !track.is_empty())
        .unwrap_or("xiao_shu::alert_peek::medium")
        .to_string();
    let reason = opts
        .reason
        .map(str::trim)
        .filter(|reason| !reason.is_empty())
        .map(ToString::to_string)
        .unwrap_or_else(|| format!("xiao-shu-action-request-{intent}"));
    let preview_opts = AvatarCortexVoiceActionPreviewOptions {
        label: opts.label,
        heartbeat_label: opts.heartbeat_label,
        project: opts.project,
        output: opts.output,
        requested_track: Some(track.as_str()),
        reason: Some(reason.as_str()),
        confirm: opts.confirm,
        force: opts.force,
        cooldown_secs: opts.cooldown_secs,
        tts_voice: opts.tts_voice,
        tts_rate: opts.tts_rate,
    };
    let action_preview = avatar_cortex_voice_action_preview(&preview_opts).unwrap_or_else(|e| {
        xiao_shu_action_degraded_preview(e.to_string(), &preview_opts, project, &track, &reason)
    });
    Ok(xiao_shu_action_request_from_preview(
        action_preview,
        opts,
        project,
        &intent,
        &track,
        &reason,
    ))
}

fn xiao_shu_action_enqueue_record_from_request(
    request_payload: Value,
    project: &str,
    queue_path: &Path,
    now: i64,
) -> Value {
    let request = request_payload
        .get("action_request")
        .unwrap_or(&Value::Null);
    let actor = vstr(request.get("actor")).unwrap_or("llm");
    let intent = vstr(request.get("intent")).unwrap_or("voice_alert");
    let reason = vstr(request.get("reason")).unwrap_or("xiao-shu-action-request");
    let mapped_track = vstr(request.get("mapped_track")).unwrap_or("xiao_shu::alert_peek::medium");
    let message = request.get("message").cloned().unwrap_or(Value::Null);
    let seed = json!({
        "created_at": now,
        "project": project,
        "actor": actor,
        "intent": intent,
        "reason": reason,
        "mapped_track": mapped_track,
        "message": message,
    });
    let seed_hash = fnv1a_hex16(&serde_json::to_string(&seed).unwrap_or_default());
    let request_id = format!("xsr-{now}-{}", &seed_hash[..8]);
    let action_preview_command = format!(
        "agent-bridge avatar xiao-shu-action-request-action --project {project} --request-id {request_id:?} --reason {reason:?} --confirm"
    );
    let local_emit_command = format!(
        "agent-bridge avatar xiao-shu-action-request-action --project {project} --request-id {request_id:?} --reason {reason:?} --confirm --emit"
    );

    json!({
        "schema": 1,
        "request_id": request_id,
        "created_at": now,
        "updated_at": now,
        "state": "pending_human_confirmation",
        "project": project,
        "target": "xiao-shu",
        "actor": actor,
        "intent": intent,
        "message": message,
        "reason": reason,
        "mapped_track": mapped_track,
        "source": "xiao_shu_action_request_enqueue",
        "queue_path": queue_path.to_string_lossy(),
        "llm_safe": true,
        "sidecar_only": true,
        "direct_pet_control_allowed": false,
        "direct_llm_emit_allowed": false,
        "requires_human_confirmation": true,
        "human_confirmation_present": false,
        "real_emit_requires_local_cli": true,
        "actual_emit_invoked": false,
        "emits_audio": false,
        "emits_notification": false,
        "writes_request_record": true,
        "writes_cooldown_state": false,
        "codex_pet_package_mutation": false,
        "mutates_global_substrate": false,
        "action_preview_command": action_preview_command,
        "local_confirm_command": action_preview_command,
        "local_emit_command": local_emit_command,
        "action_request": request.clone(),
        "source_request": request_payload,
    })
}

fn xiao_shu_action_request_compact_record(record: Value) -> Value {
    let request = record.get("action_request").unwrap_or(&Value::Null);
    let mut action_request = serde_json::Map::new();
    action_request.insert(
        "target".to_string(),
        request
            .get("target")
            .cloned()
            .unwrap_or_else(|| json!("xiao-shu")),
    );
    action_request.insert(
        "actor".to_string(),
        request
            .get("actor")
            .cloned()
            .or_else(|| record.get("actor").cloned())
            .unwrap_or(Value::Null),
    );
    action_request.insert(
        "intent".to_string(),
        request
            .get("intent")
            .cloned()
            .or_else(|| record.get("intent").cloned())
            .unwrap_or(Value::Null),
    );
    action_request.insert(
        "message".to_string(),
        request
            .get("message")
            .cloned()
            .or_else(|| record.get("message").cloned())
            .unwrap_or(Value::Null),
    );
    action_request.insert(
        "request_state".to_string(),
        request.get("request_state").cloned().unwrap_or(Value::Null),
    );
    action_request.insert(
        "mapped_track".to_string(),
        request
            .get("mapped_track")
            .cloned()
            .or_else(|| record.get("mapped_track").cloned())
            .unwrap_or(Value::Null),
    );
    action_request.insert(
        "line".to_string(),
        request.get("line").cloned().unwrap_or(Value::Null),
    );
    action_request.insert(
        "reason".to_string(),
        request
            .get("reason")
            .cloned()
            .or_else(|| record.get("reason").cloned())
            .unwrap_or(Value::Null),
    );
    action_request.insert(
        "blocked".to_string(),
        request.get("blocked").cloned().unwrap_or(Value::Null),
    );
    action_request.insert(
        "blocked_reasons".to_string(),
        request
            .get("blocked_reasons")
            .cloned()
            .unwrap_or(Value::Null),
    );
    action_request.insert(
        "ready_for_local_cli_emit".to_string(),
        request
            .get("ready_for_local_cli_emit")
            .cloned()
            .unwrap_or(Value::Null),
    );

    let mut compact = serde_json::Map::new();
    compact.insert(
        "schema".to_string(),
        record.get("schema").cloned().unwrap_or_else(|| json!(1)),
    );
    for key in [
        "request_id",
        "created_at",
        "updated_at",
        "state",
        "prior_state",
        "project",
        "actor",
        "intent",
        "message",
        "reason",
        "mapped_track",
        "source",
        "would_emit",
        "emitted",
        "local_confirm_command",
        "local_emit_command",
    ] {
        compact.insert(
            key.to_string(),
            record.get(key).cloned().unwrap_or(Value::Null),
        );
    }
    compact.insert(
        "target".to_string(),
        record
            .get("target")
            .cloned()
            .unwrap_or_else(|| json!("xiao-shu")),
    );
    for (key, fallback) in [
        ("llm_safe", true),
        ("sidecar_only", true),
        ("direct_pet_control_allowed", false),
        ("direct_llm_emit_allowed", false),
        ("requires_human_confirmation", true),
        ("human_confirmation_present", false),
        ("real_emit_requires_local_cli", true),
        ("actual_emit_invoked", false),
        ("emits_audio", false),
        ("writes_request_record", false),
        ("writes_cooldown_state", false),
        ("codex_pet_package_mutation", false),
    ] {
        compact.insert(
            key.to_string(),
            record.get(key).cloned().unwrap_or_else(|| json!(fallback)),
        );
    }
    compact.insert("action_request".to_string(), Value::Object(action_request));
    compact.insert("compact".to_string(), json!(true));
    Value::Object(compact)
}

pub fn xiao_shu_action_request_enqueue(opts: &XiaoShuActionRequestOptions<'_>) -> Result<Value> {
    let project = opts.project.unwrap_or("agent-bridge");
    let queue_path = xiao_shu_action_request_queue_path(project)?;
    let request_payload = xiao_shu_action_request(opts)?;
    let now = now_secs();
    let record =
        xiao_shu_action_enqueue_record_from_request(request_payload, project, &queue_path, now);
    append_jsonl(&queue_path, &record)?;

    Ok(json!({
        "surface": "xiao_shu_action_request_enqueue",
        "schema": 1,
        "generated_at": now,
        "read_only": false,
        "dry_run": false,
        "llm_safe": true,
        "sidecar_only": true,
        "direct_pet_control_allowed": false,
        "direct_llm_emit_allowed": false,
        "requires_human_confirmation": true,
        "real_emit_requires_local_cli": true,
        "actual_emit_invoked": false,
        "emits_audio": false,
        "emits_notification": false,
        "http_emit_route_added": false,
        "writes_files": true,
        "writes_request_record": true,
        "writes_cooldown_state": false,
        "codex_pet_package_mutation": false,
        "mutates_global_substrate": false,
        "queue": {
            "project": project,
            "path": queue_path.to_string_lossy(),
            "request_id": record.get("request_id").cloned().unwrap_or(Value::Null),
            "state": record.get("state").cloned().unwrap_or(Value::Null),
            "append_only": true,
        },
        "record": record,
        "next_step": "show this pending request in a human confirmation surface; only a later local CLI action may emit audio",
    }))
}

fn xiao_shu_action_request_queue_from_path(
    opts: &XiaoShuActionRequestQueueOptions<'_>,
    project: &str,
    queue_path: &Path,
) -> Result<Value> {
    let limit = opts.limit.clamp(1, 500);
    let request_id_filter = opts
        .request_id
        .map(str::trim)
        .filter(|request_id| !request_id.is_empty());
    let state_filter = opts
        .state
        .map(str::trim)
        .filter(|state| !state.is_empty())
        .or_else(|| {
            if opts.include_all_states || request_id_filter.is_some() {
                None
            } else {
                Some("pending_human_confirmation")
            }
        });
    let include_details =
        opts.include_details || opts.include_all_states || request_id_filter.is_some();
    let queue_exists = queue_path.exists();
    let mut latest_by_request = BTreeMap::<String, (usize, Value)>::new();
    let mut state_counts = BTreeMap::<String, usize>::new();
    let mut total_lines = 0usize;
    let mut parsed_records = 0usize;
    let mut parse_errors = 0usize;

    if queue_exists {
        let body = std::fs::read_to_string(&queue_path)
            .with_context(|| format!("read {}", queue_path.display()))?;
        for line in body.lines() {
            let trimmed = line.trim();
            if trimmed.is_empty() {
                continue;
            }
            total_lines += 1;
            let Ok(record) = serde_json::from_str::<Value>(trimmed) else {
                parse_errors += 1;
                continue;
            };
            parsed_records += 1;
            let request_key = vstr(record.get("request_id"))
                .map(str::trim)
                .filter(|request_id| !request_id.is_empty())
                .map(ToString::to_string)
                .unwrap_or_else(|| format!("line-{total_lines}"));
            latest_by_request.insert(request_key, (total_lines, record));
        }
    }

    let mut current_records_by_line = latest_by_request.into_values().collect::<Vec<_>>();
    current_records_by_line.sort_by_key(|(line_index, _record)| *line_index);
    let current_records = current_records_by_line.len();
    let mut records = Vec::<Value>::new();
    for (_line_index, record) in current_records_by_line {
        let state = vstr(record.get("state")).unwrap_or("unknown").to_string();
        *state_counts.entry(state.clone()).or_default() += 1;

        if let Some(expected_request_id) = request_id_filter {
            if vstr(record.get("request_id")) != Some(expected_request_id) {
                continue;
            }
        }
        if let Some(expected_state) = state_filter {
            if state != expected_state {
                continue;
            }
        }
        records.push(record);
    }

    let matching_records = records.len();
    records.reverse();
    records.truncate(limit);
    if !include_details {
        records = records
            .into_iter()
            .map(xiao_shu_action_request_compact_record)
            .collect();
    }

    Ok(json!({
        "surface": "xiao_shu_action_request_queue",
        "schema": 1,
        "generated_at": now_secs(),
        "read_only": true,
        "dry_run": true,
        "llm_safe": true,
        "sidecar_only": true,
        "direct_pet_control_allowed": false,
        "direct_llm_emit_allowed": false,
        "requires_human_confirmation": true,
        "real_emit_requires_local_cli": true,
        "actual_emit_invoked": false,
        "emits_audio": false,
        "emits_notification": false,
        "http_emit_route_added": false,
        "writes_files": false,
        "writes_request_record": false,
        "writes_cooldown_state": false,
        "codex_pet_package_mutation": false,
        "mutates_global_substrate": false,
        "queue": {
            "project": project,
            "path": queue_path.to_string_lossy(),
            "exists": queue_exists,
            "append_only": true,
            "request_id_filter": request_id_filter,
            "state_filter": state_filter,
            "include_all_states": opts.include_all_states,
            "include_details": include_details,
            "limit": limit,
            "total_lines": total_lines,
            "parsed_records": parsed_records,
            "current_records": current_records,
            "parse_errors": parse_errors,
            "matching_records": matching_records,
            "returned_count": records.len(),
            "state_counts": state_counts,
        },
        "records": records,
        "next_step": "select a pending request_id for a separate local confirmation action; this read surface cannot emit audio or control the pet",
    }))
}

pub fn xiao_shu_action_request_queue(opts: &XiaoShuActionRequestQueueOptions<'_>) -> Result<Value> {
    let project = opts.project.unwrap_or("agent-bridge");
    let queue_path = xiao_shu_action_request_queue_path(project)?;
    xiao_shu_action_request_queue_from_path(opts, project, &queue_path)
}

/// Compact read-only queue headline for MCP/panel surfaces (no nested renderer payloads).
pub fn xiao_shu_action_request_queue_summary(project: Option<&str>) -> Result<Value> {
    let project_slug = project.unwrap_or("agent-bridge");
    let queue_path = xiao_shu_action_request_queue_path(project_slug)?;

    let all_states = xiao_shu_action_request_queue_from_path(
        &XiaoShuActionRequestQueueOptions {
            project: Some(project_slug),
            request_id: None,
            state: None,
            include_all_states: true,
            include_details: false,
            limit: 1,
        },
        project_slug,
        &queue_path,
    )?;
    let queue_meta = all_states.get("queue").cloned().unwrap_or(Value::Null);
    let state_counts = queue_meta
        .get("state_counts")
        .cloned()
        .unwrap_or_else(|| json!({}));
    let pending_count = state_counts
        .get("pending_human_confirmation")
        .and_then(Value::as_u64)
        .unwrap_or(0) as usize;

    let pending_head = xiao_shu_action_request_queue_from_path(
        &XiaoShuActionRequestQueueOptions {
            project: Some(project_slug),
            request_id: None,
            state: None,
            include_all_states: false,
            include_details: false,
            limit: 5,
        },
        project_slug,
        &queue_path,
    )?;
    let newest_pending = pending_head
        .get("records")
        .and_then(Value::as_array)
        .cloned()
        .unwrap_or_default()
        .into_iter()
        .map(|record| {
            json!({
                "request_id": record.get("request_id").cloned().unwrap_or(Value::Null),
                "state": record.get("state").cloned().unwrap_or(Value::Null),
                "actor": record.get("actor").cloned().unwrap_or(Value::Null),
                "intent": record.get("intent").cloned().unwrap_or(Value::Null),
                "reason": record.get("reason").cloned().unwrap_or(Value::Null),
                "mapped_track": record.get("mapped_track").cloned().unwrap_or(Value::Null),
                "created_at": record.get("created_at").cloned().unwrap_or(Value::Null),
            })
        })
        .collect::<Vec<_>>();

    Ok(json!({
        "read_only": true,
        "dry_run": true,
        "llm_safe": true,
        "project": project_slug,
        "queue_exists": queue_meta.get("exists").cloned().unwrap_or(Value::Bool(false)),
        "pending_count": pending_count,
        "current_records": queue_meta.get("current_records").cloned().unwrap_or(Value::Null),
        "state_counts": state_counts,
        "newest_pending": newest_pending,
        "panel_path": format!("/avatar-surface/xiao-shu-action-requests?project={project_slug}"),
        "local_queue_command": format!(
            "agent-bridge avatar xiao-shu-action-requests --project {project_slug}"
        ),
    }))
}

pub fn xiao_shu_action_request_action(
    opts: &XiaoShuActionRequestActionOptions<'_>,
) -> Result<Value> {
    let project = opts.project.unwrap_or("agent-bridge");
    let request_id = opts
        .request_id
        .map(str::trim)
        .filter(|request_id| !request_id.is_empty())
        .ok_or_else(|| anyhow::anyhow!("request_id is required"))?;
    let queue_path = xiao_shu_action_request_queue_path(project)?;
    let queue_opts = XiaoShuActionRequestQueueOptions {
        project: Some(project),
        request_id: Some(request_id),
        state: None,
        include_all_states: true,
        include_details: true,
        limit: 1,
    };
    let queue = xiao_shu_action_request_queue_from_path(&queue_opts, project, &queue_path)?;
    let record = queue
        .get("records")
        .and_then(Value::as_array)
        .and_then(|records| records.first())
        .cloned()
        .ok_or_else(|| anyhow::anyhow!("xiao shu action request not found: {request_id}"))?;
    let current_state = vstr(record.get("state")).unwrap_or("unknown");
    let request = record.get("action_request").unwrap_or(&Value::Null);
    let track = vstr(record.get("mapped_track"))
        .or_else(|| vstr(request.get("mapped_track")))
        .unwrap_or("xiao_shu::alert_peek::medium")
        .to_string();
    let reason = opts
        .reason
        .map(str::trim)
        .filter(|reason| !reason.is_empty())
        .or_else(|| vstr(record.get("reason")))
        .unwrap_or("xiao-shu-action-request-action")
        .to_string();
    let pending = current_state == "pending_human_confirmation";
    let action_payload = if opts.dismiss {
        let mut blocked_reasons = Vec::new();
        if !pending {
            blocked_reasons.push(json!("request_state_not_pending"));
        }
        if !opts.confirm {
            blocked_reasons.push(json!("confirm_flag_missing"));
        }
        if opts.emit {
            blocked_reasons.push(json!("emit_flag_conflicts_with_dismiss"));
        }
        let blocked = !blocked_reasons.is_empty();
        json!({
            "surface": "xiao_shu_action_request_dismiss",
            "schema": 1,
            "generated_at": now_secs(),
            "cli_only": true,
            "http_available": false,
            "read_only": blocked,
            "dry_run": blocked,
            "sidecar_only": true,
            "mutates_global_substrate": false,
            "writes_files": false,
            "writes_cooldown_state": false,
            "codex_pet_package_mutation": false,
            "requested_emit": opts.emit,
            "actual_emit_invoked": false,
            "would_emit": false,
            "emitted": false,
            "emits_audio": false,
            "emits_notification": false,
            "dismiss_requested": true,
            "dismissed": !blocked,
            "action": {
                "confirmation_state": if blocked {
                    "dismiss_blocked"
                } else {
                    "dismissed_without_emit"
                },
                "confirmed": opts.confirm,
                "confirm_flag": opts.confirm,
                "emit_flag": opts.emit,
                "dismiss_flag": opts.dismiss,
                "blocked": blocked,
                "blocked_reasons": blocked_reasons,
                "selected_token": track,
                "line": request.get("line").cloned().unwrap_or(Value::Null),
                "reason_present": !reason.trim().is_empty(),
                "allow_policy_override": false,
                "cooldown_secs": opts.cooldown_secs,
                "force": opts.force,
                "tts_voice": opts.tts_voice,
                "tts_rate": opts.tts_rate,
                "command_preview": Value::Null,
            },
            "source_queue_record": record,
        })
    } else if pending {
        let action_opts = AvatarCortexVoiceActionOptions {
            label: opts.label,
            heartbeat_label: opts.heartbeat_label,
            project: Some(project),
            output: opts.output,
            requested_track: Some(track.as_str()),
            reason: Some(reason.as_str()),
            confirm: opts.confirm,
            emit: opts.emit,
            force: opts.force,
            cooldown_secs: opts.cooldown_secs,
            tts_voice: opts.tts_voice,
            tts_rate: opts.tts_rate,
        };
        avatar_cortex_voice_action(&action_opts)?
    } else {
        json!({
            "surface": "avatar_cortex_voice_action",
            "schema": 1,
            "generated_at": now_secs(),
            "cli_only": true,
            "http_available": false,
            "read_only": true,
            "dry_run": true,
            "sidecar_only": true,
            "mutates_global_substrate": false,
            "writes_files": false,
            "writes_cooldown_state": false,
            "codex_pet_package_mutation": false,
            "requested_emit": opts.emit,
            "actual_emit_invoked": false,
            "would_emit": false,
            "emitted": false,
            "emits_audio": false,
            "emits_notification": false,
            "action": {
                "confirmation_state": "blocked_by_queue_state",
                "confirmed": false,
                "confirm_flag": opts.confirm,
                "emit_flag": opts.emit,
                "blocked": true,
                "blocked_reasons": ["request_state_not_pending"],
                "selected_token": track,
                "line": request.get("line").cloned().unwrap_or(Value::Null),
                "reason_present": !reason.trim().is_empty(),
                "allow_policy_override": false,
                "cooldown_secs": opts.cooldown_secs,
                "force": opts.force,
                "tts_voice": opts.tts_voice,
                "tts_rate": opts.tts_rate,
                "command_preview": Value::Null,
            },
            "source_queue_record": record,
        })
    };

    let actual_emit_invoked = vbool(action_payload.get("actual_emit_invoked")).unwrap_or(false);
    let would_emit = vbool(action_payload.get("would_emit")).unwrap_or(false);
    let emitted = vbool(action_payload.get("emitted")).unwrap_or(false);
    let emits_audio = vbool(action_payload.get("emits_audio")).unwrap_or(false);
    let dismissed = vbool(action_payload.get("dismissed")).unwrap_or(false);
    let writes_cooldown_state = vbool(action_payload.get("writes_cooldown_state")).unwrap_or(false);
    let now = now_secs();
    let transition_state = if emitted {
        "emitted"
    } else if dismissed {
        "dismissed"
    } else if actual_emit_invoked && would_emit {
        "emit_failed"
    } else if actual_emit_invoked {
        "emit_blocked"
    } else {
        current_state
    };
    let transition_written = actual_emit_invoked || dismissed;
    let transition_record = if transition_written {
        let record = json!({
            "schema": 1,
            "request_id": request_id,
            "created_at": record.get("created_at").cloned().unwrap_or(Value::Null),
            "updated_at": now,
            "state": transition_state,
            "prior_state": current_state,
            "project": project,
            "target": "xiao-shu",
            "actor": "local-cli",
            "intent": record.get("intent").cloned().unwrap_or_else(|| json!("voice_alert")),
            "message": record.get("message").cloned().unwrap_or(Value::Null),
            "reason": reason,
            "mapped_track": track,
            "source": "xiao_shu_action_request_action",
            "queue_path": queue_path.to_string_lossy(),
            "llm_safe": true,
            "sidecar_only": true,
            "direct_pet_control_allowed": false,
            "direct_llm_emit_allowed": false,
            "requires_human_confirmation": true,
            "human_confirmation_present": opts.confirm,
            "real_emit_requires_local_cli": true,
            "actual_emit_invoked": actual_emit_invoked,
            "would_emit": would_emit,
            "emitted": emitted,
            "dismiss_requested": opts.dismiss,
            "dismissed": dismissed,
            "emits_audio": emits_audio,
            "emits_notification": false,
            "writes_request_record": true,
            "writes_cooldown_state": writes_cooldown_state,
            "codex_pet_package_mutation": false,
            "mutates_global_substrate": false,
            "action_request": request.clone(),
            "source_record": record.clone(),
            "source_action": action_payload.clone(),
        });
        append_jsonl(&queue_path, &record)?;
        record
    } else {
        Value::Null
    };

    Ok(json!({
        "surface": "xiao_shu_action_request_action",
        "schema": 1,
        "generated_at": now,
        "cli_only": true,
        "http_available": false,
        "read_only": !transition_written,
        "dry_run": !transition_written,
        "llm_safe": true,
        "sidecar_only": true,
        "direct_pet_control_allowed": false,
        "direct_llm_emit_allowed": false,
        "real_emit_requires_local_cli": true,
        "http_emit_route_added": false,
        "codex_pet_package_mutation": false,
        "mutates_global_substrate": false,
        "request_id": request_id,
        "project": project,
        "prior_state": current_state,
        "state": transition_state,
        "pending_before_action": pending,
        "confirm_requested": opts.confirm,
        "emit_requested": opts.emit,
        "dismiss_requested": opts.dismiss,
        "actual_emit_invoked": actual_emit_invoked,
        "would_emit": would_emit,
        "emitted": emitted,
        "dismissed": dismissed,
        "emits_audio": emits_audio,
        "emits_notification": false,
        "writes_files": transition_written,
        "writes_request_record": transition_written,
        "writes_cooldown_state": writes_cooldown_state,
        "queue": {
            "project": project,
            "path": queue_path.to_string_lossy(),
            "append_only": true,
        },
        "record": record,
        "action": action_payload,
        "transition_record": transition_record,
        "next_step": if dismissed {
            "queue dismissal transition appended; inspect xiao-shu-action-requests --all-states for audit history"
        } else if actual_emit_invoked {
            "queue state transition appended; inspect xiao-shu-action-requests --all-states for audit history"
        } else {
            "review the pending request and rerun this local CLI action with --confirm --emit for audio or --confirm --dismiss to clear it"
        },
    }))
}

#[cfg(test)]
mod tests {
    use super::*;

    fn event(ts: i64, status: &str) -> Value {
        json!({
            "surface": "avatar_heartbeat_alert",
            "generated_at": ts,
            "label": "com.agentbridge.avatar-heartbeat.agent-bridge",
            "project": "agent-bridge",
            "status": status,
            "healthy": status == "healthy",
            "event_key": status,
            "reason": "transition",
            "should_emit": true,
            "emitted": false,
            "preview": false,
            "health": {
                "summary": format!("{status}: sample"),
                "launchd": {"last_exit_code": 0},
                "presence": {"fresh": true, "age_secs": 12}
            },
            "seed_ready": {"substrate_input": "avatar_health_transition_v1"}
        })
    }

    #[test]
    fn avatar_cortex_replay_writes_isolated_snapshot() {
        let dir = tempfile::tempdir().expect("tempdir");
        let input = dir.path().join("events.jsonl");
        let output = dir.path().join("xiao-shu-cortex.parquet");
        let body = [
            serde_json::to_string(&event(1, "healthy")).unwrap(),
            serde_json::to_string(&event(2, "failing")).unwrap(),
        ]
        .join("\n");
        std::fs::write(&input, body).expect("write events");
        let opts = AvatarCortexReplayOptions {
            label: None,
            project: Some("agent-bridge"),
            input: Some(&input),
            output: Some(&output),
            limit: 20,
            include_preview: false,
            use_hash: true,
            n: 8,
            d: 8,
        };
        let payload = avatar_cortex_replay(&opts).expect("replay");
        assert_eq!(payload["mode"], "shadow_only");
        assert_eq!(payload["perceived"], 2);
        assert_eq!(payload["snapshot_rows"], 1);
        assert_eq!(payload["mutates_global_substrate"], false);
        assert!(output.exists());
    }

    #[test]
    fn cortex_runner_label_defaults_to_project() {
        assert_eq!(
            cortex_runner_label(None, "Agent Bridge"),
            "com.agentbridge.avatar-cortex.agent-bridge"
        );
        assert_eq!(
            cortex_runner_label(Some("custom.label"), "Agent Bridge"),
            "custom.label"
        );
    }

    #[test]
    fn avatar_cortex_event_summary_counts_latest_status() {
        let source = Path::new("/tmp/avatar.events.jsonl");
        let healthy =
            crate::avatar_seed::avatar_event_to_seed_record(&event(10, "healthy"), source)
                .expect("healthy record");
        let failing =
            crate::avatar_seed::avatar_event_to_seed_record(&event(20, "failing"), source)
                .expect("failing record");
        let seed_payload = json!({
            "events_path": source,
            "include_preview": false,
            "limit": 500,
            "events_seen": 2,
            "records_count": 2,
            "parse_skips": 0,
            "surface_skips": 0,
            "preview_skips": 0,
            "records": [healthy, failing],
        });
        let events = avatar_cortex_events_summary_from_seed(&seed_payload);
        assert_eq!(events["records_count"], 2);
        assert_eq!(events["status_counts"]["healthy"], 1);
        assert_eq!(events["status_counts"]["failing"], 1);
        assert_eq!(events["latest"]["status"], "failing");
        assert_eq!(events["unhealthy_count"], 1);

        let snapshot = json!({
            "latest_long": {
                "step": 2,
                "cycle_ts": 25,
            }
        });
        let trend = avatar_cortex_trend(&snapshot, &events);
        assert_eq!(trend["step_records_delta"], 0);
        assert_eq!(trend["snapshot_event_lag_secs"], 5);
        assert_eq!(trend["latest_status"], "failing");
        assert_eq!(trend["learning_state"]["state"], "caught_up");
        assert_eq!(trend["behavior_policy"]["badge"], "caught up");
        assert_eq!(trend["behavior_policy"]["recommended_action"], "none");
        assert_eq!(trend["behavior_policy"]["voice"]["allowed"], false);

        let learning_snapshot = json!({
            "latest_long": {
                "step": 1,
                "cycle_ts": 15,
            }
        });
        let learning = avatar_cortex_trend(&learning_snapshot, &events);
        assert_eq!(learning["step_records_delta"], -1);
        assert_eq!(learning["snapshot_event_lag_secs"], -5);
        assert_eq!(learning["learning_state"]["state"], "learning");
        assert_eq!(
            learning["behavior_policy"]["recommended_action"],
            "wait_for_cortex_runner"
        );
        assert_eq!(
            learning["behavior_policy"]["notification"]["allowed"],
            false
        );

        let stale = avatar_cortex_trend(&json!({}), &events);
        assert_eq!(stale["learning_state"]["state"], "stale");
        assert_eq!(stale["learning_state"]["reason"], "no_snapshot");
        assert_eq!(
            stale["behavior_policy"]["recommended_action"],
            "inspect_cortex_status"
        );
    }

    #[test]
    fn avatar_cortex_voice_preview_never_emits_audio() {
        let status = json!({
            "surface": "avatar_cortex_status",
            "project": "agent-bridge",
            "label": "com.agentbridge.avatar-cortex.agent-bridge",
            "heartbeat_label": "com.agentbridge.avatar-heartbeat.agent-bridge",
            "launchd": {"loaded": true},
            "snapshot": {"total_rows": 1},
            "events": {
                "records_count": 3,
                "unhealthy_count": 0,
                "latest": {
                    "status": "healthy",
                    "reason": "transition"
                }
            },
            "trend": {
                "step_records_delta": -1,
                "snapshot_event_lag_secs": -5,
                "learning_state": {
                    "state": "learning",
                    "reason": "events_ahead_of_snapshot"
                },
                "behavior_policy": {
                    "badge": "learning",
                    "recommended_action": "wait_for_cortex_runner",
                    "voice": {
                        "allowed": false,
                        "preview": "小舒正在吸收新事件。",
                        "reason": "sparse_voice_policy"
                    },
                    "notification": {
                        "allowed": false,
                        "reason": "read_only_panel_policy"
                    }
                }
            }
        });
        let preview = avatar_cortex_voice_preview_from_status(status);
        assert_eq!(preview["surface"], "avatar_cortex_voice_preview");
        assert_eq!(preview["emits_audio"], false);
        assert_eq!(preview["emits_notification"], false);
        assert_eq!(
            preview["preview"]["text"],
            "小舒正在整理新事件，先把变化叠进自己的皮质层。 新事件已经排队。 等 runner 追上就好。"
        );
        assert_eq!(preview["language"]["intent"], "processing");
        assert_eq!(preview["preview"]["voice_allowed"], false);
        assert_eq!(preview["preview"]["notification_allowed"], false);
        assert_eq!(preview["preview"]["requires_explicit_emit_gate"], true);
        assert_eq!(preview["learning_state"]["state"], "learning");
    }

    #[test]
    fn avatar_cortex_language_preview_composes_caught_up_line() {
        let status = json!({
            "surface": "avatar_cortex_status",
            "project": "agent-bridge",
            "label": "com.agentbridge.avatar-cortex.agent-bridge",
            "heartbeat_label": "com.agentbridge.avatar-heartbeat.agent-bridge",
            "launchd": {"loaded": true},
            "snapshot": {"total_rows": 1},
            "events": {
                "records_count": 8,
                "unhealthy_count": 0,
                "latest": {
                    "status": "healthy",
                    "reason": "unchanged"
                }
            },
            "trend": {
                "step_records_delta": 0,
                "snapshot_event_lag_secs": 30,
                "learning_state": {
                    "state": "caught_up",
                    "reason": "step_matches_records"
                },
                "behavior_policy": {
                    "badge": "caught up",
                    "recommended_action": "none"
                }
            }
        });
        let preview = avatar_cortex_language_preview_from_status(status);
        assert_eq!(preview["surface"], "avatar_cortex_language_preview");
        assert_eq!(preview["emits_audio"], false);
        assert_eq!(preview["language"]["intent"], "reassure");
        assert_eq!(preview["language"]["generator"]["uses_llm"], false);
        assert_eq!(preview["language"]["generator"]["uses_voice_model"], false);
        assert_eq!(
            preview["language"]["safety"]["requires_explicit_emit_gate"],
            true
        );
        assert_eq!(
            preview["language"]["utterance"],
            "小舒追上啦，当前信号是健康的。 最近状态保持稳定。 我会继续安静观察。"
        );
    }

    #[test]
    fn avatar_cortex_language_preview_remembers_stable_recent_window() {
        let status = json!({
            "surface": "avatar_cortex_status",
            "project": "agent-bridge",
            "label": "com.agentbridge.avatar-cortex.agent-bridge",
            "heartbeat_label": "com.agentbridge.avatar-heartbeat.agent-bridge",
            "launchd": {"loaded": true},
            "snapshot": {"total_rows": 1},
            "events": {
                "records_count": 3,
                "unhealthy_count": 0,
                "latest": {
                    "status": "healthy",
                    "healthy": true,
                    "reason": "unchanged",
                    "ts": 300
                },
                "recent": [
                    {"status": "healthy", "healthy": true, "reason": "unchanged", "ts": 100},
                    {"status": "healthy", "healthy": true, "reason": "unchanged", "ts": 200},
                    {"status": "healthy", "healthy": true, "reason": "unchanged", "ts": 300}
                ]
            },
            "trend": {
                "step_records_delta": 0,
                "snapshot_event_lag_secs": 0,
                "learning_state": {
                    "state": "caught_up",
                    "reason": "step_matches_records"
                },
                "behavior_policy": {
                    "badge": "caught up",
                    "recommended_action": "none"
                }
            }
        });
        let preview = avatar_cortex_language_preview_from_status(status);
        assert_eq!(
            preview["language"]["memory"]["observation"],
            "stable_recent_window"
        );
        assert_eq!(preview["language"]["memory"]["window_size"], 3);
        assert_eq!(preview["language"]["memory"]["transition_count"], 0);
        assert_eq!(
            preview["language"]["utterance"],
            "小舒追上啦，当前信号是健康的。 小舒记得最近几次信号都很稳。 最近状态保持稳定。 我会继续安静观察。"
        );
    }

    #[test]
    fn avatar_cortex_language_preview_remembers_recent_transition() {
        let status = json!({
            "surface": "avatar_cortex_status",
            "project": "agent-bridge",
            "label": "com.agentbridge.avatar-cortex.agent-bridge",
            "heartbeat_label": "com.agentbridge.avatar-heartbeat.agent-bridge",
            "launchd": {"loaded": true},
            "snapshot": {"total_rows": 1},
            "events": {
                "records_count": 3,
                "unhealthy_count": 1,
                "latest": {
                    "status": "healthy",
                    "healthy": true,
                    "reason": "transition",
                    "ts": 300
                },
                "recent": [
                    {"status": "failing", "healthy": false, "reason": "launchd_error", "ts": 100},
                    {"status": "healthy", "healthy": true, "reason": "transition", "ts": 200},
                    {"status": "healthy", "healthy": true, "reason": "unchanged", "ts": 300}
                ]
            },
            "trend": {
                "step_records_delta": -1,
                "snapshot_event_lag_secs": -10,
                "learning_state": {
                    "state": "learning",
                    "reason": "events_ahead_of_snapshot"
                },
                "behavior_policy": {
                    "badge": "learning",
                    "recommended_action": "wait_for_cortex_runner"
                }
            }
        });
        let preview = avatar_cortex_language_preview_from_status(status);
        assert_eq!(
            preview["language"]["memory"]["observation"],
            "recent_unhealthy_signal"
        );
        assert_eq!(preview["language"]["memory"]["transition_count"], 2);
        assert_eq!(
            preview["language"]["memory"]["clause"],
            "小舒记得最近几次里有异常信号。"
        );
        assert_eq!(preview["language"]["intent"], "processing");
    }

    #[test]
    fn avatar_cortex_motion_preview_maps_stable_window_to_bounce() {
        let status = json!({
            "surface": "avatar_cortex_status",
            "project": "agent-bridge",
            "label": "com.agentbridge.avatar-cortex.agent-bridge",
            "heartbeat_label": "com.agentbridge.avatar-heartbeat.agent-bridge",
            "launchd": {"loaded": true},
            "snapshot": {"total_rows": 1},
            "events": {
                "records_count": 3,
                "unhealthy_count": 0,
                "latest": {
                    "status": "healthy",
                    "healthy": true,
                    "reason": "unchanged",
                    "ts": 300
                },
                "recent": [
                    {"status": "healthy", "healthy": true, "reason": "unchanged", "ts": 100},
                    {"status": "healthy", "healthy": true, "reason": "unchanged", "ts": 200},
                    {"status": "healthy", "healthy": true, "reason": "unchanged", "ts": 300}
                ]
            },
            "trend": {
                "step_records_delta": 0,
                "snapshot_event_lag_secs": 0,
                "learning_state": {
                    "state": "caught_up",
                    "reason": "step_matches_records"
                }
            }
        });
        let preview = avatar_cortex_motion_preview_from_status(status);
        assert_eq!(preview["surface"], "avatar_cortex_motion_preview");
        assert_eq!(preview["emits_audio"], false);
        assert_eq!(preview["motion"]["gesture"], "caught_up_bounce");
        assert_eq!(preview["motion"]["mood"], "bright");
        assert_eq!(preview["motion"]["attention"], "steady_watch");
        assert_eq!(
            preview["motion"]["source"]["memory_observation"],
            "stable_recent_window"
        );
        assert_eq!(
            preview["motion"]["safety"]["codex_pet_package_mutation"],
            false
        );
    }

    #[test]
    fn avatar_cortex_motion_preview_prioritizes_recent_unhealthy_signal() {
        let status = json!({
            "surface": "avatar_cortex_status",
            "project": "agent-bridge",
            "label": "com.agentbridge.avatar-cortex.agent-bridge",
            "heartbeat_label": "com.agentbridge.avatar-heartbeat.agent-bridge",
            "launchd": {"loaded": true},
            "snapshot": {"total_rows": 1},
            "events": {
                "records_count": 3,
                "unhealthy_count": 1,
                "latest": {
                    "status": "healthy",
                    "healthy": true,
                    "reason": "transition",
                    "ts": 300
                },
                "recent": [
                    {"status": "failing", "healthy": false, "reason": "launchd_error", "ts": 100},
                    {"status": "healthy", "healthy": true, "reason": "transition", "ts": 200},
                    {"status": "healthy", "healthy": true, "reason": "unchanged", "ts": 300}
                ]
            },
            "trend": {
                "step_records_delta": -1,
                "snapshot_event_lag_secs": -10,
                "learning_state": {
                    "state": "learning",
                    "reason": "events_ahead_of_snapshot"
                }
            }
        });
        let preview = avatar_cortex_motion_preview_from_status(status);
        assert_eq!(preview["motion"]["gesture"], "alert_peek");
        assert_eq!(preview["motion"]["mood"], "concerned");
        assert_eq!(preview["motion"]["attention"], "health_signal");
        assert_eq!(preview["motion"]["animation_hint"]["loop"], "alert_peek");
        assert_eq!(
            preview["motion"]["source"]["memory_observation"],
            "recent_unhealthy_signal"
        );
    }

    #[test]
    fn avatar_cortex_renderer_preview_maps_soft_bounce_slots() {
        let status = json!({
            "surface": "avatar_cortex_status",
            "project": "agent-bridge",
            "label": "com.agentbridge.avatar-cortex.agent-bridge",
            "heartbeat_label": "com.agentbridge.avatar-heartbeat.agent-bridge",
            "launchd": {"loaded": true},
            "snapshot": {"total_rows": 1},
            "events": {
                "records_count": 3,
                "unhealthy_count": 0,
                "latest": {
                    "status": "healthy",
                    "healthy": true,
                    "reason": "unchanged",
                    "ts": 300
                },
                "recent": [
                    {"status": "healthy", "healthy": true, "reason": "unchanged", "ts": 100},
                    {"status": "healthy", "healthy": true, "reason": "unchanged", "ts": 200},
                    {"status": "healthy", "healthy": true, "reason": "unchanged", "ts": 300}
                ]
            },
            "trend": {
                "step_records_delta": 0,
                "snapshot_event_lag_secs": 0,
                "learning_state": {
                    "state": "caught_up",
                    "reason": "step_matches_records"
                }
            }
        });
        let preview = avatar_cortex_renderer_preview_from_status(status);
        assert_eq!(preview["surface"], "avatar_cortex_renderer_preview");
        assert_eq!(preview["dry_run"], true);
        assert_eq!(preview["writes_files"], false);
        assert_eq!(preview["renderer"]["mapping"]["resolved"], true);
        assert_eq!(
            preview["renderer"]["mapping"]["input_token"],
            "xiao_shu::soft_bounce::low"
        );
        assert_eq!(
            preview["renderer"]["mapping"]["target"]["expression_slot"],
            "bright_smile"
        );
        assert_eq!(
            preview["renderer"]["mapping"]["evidence"]["binding_stage"],
            "candidate"
        );
        assert_eq!(
            preview["renderer"]["mapping"]["evidence"]["risk_level"],
            "low"
        );
        assert_eq!(
            preview["renderer"]["safety"]["codex_pet_package_mutation"],
            false
        );
    }

    #[test]
    fn avatar_cortex_renderer_mapping_falls_back_for_unknown_token() {
        let mapping = avatar_cortex_renderer_mapping("xiao_shu::unknown::high");
        assert_eq!(mapping["resolved"], false);
        assert_eq!(mapping["target"]["pose_slot"], "neutral_idle");
        assert_eq!(mapping["target"]["motion_slot"], "idle_breathe");
        assert_eq!(mapping["evidence"]["binding_stage"], "fallback_only");
        assert_eq!(mapping["evidence"]["risk_level"], "high");
    }

    #[test]
    fn avatar_cortex_renderer_registry_counts_binding_stages() {
        let registry = avatar_cortex_renderer_registry_payload(None);
        assert_eq!(registry["surface"], "avatar_cortex_renderer_registry");
        assert_eq!(registry["read_only"], true);
        assert_eq!(registry["writes_files"], false);
        assert_eq!(registry["registry"]["known_token_count"], 5);
        assert_eq!(registry["registry"]["stage_counts"]["candidate"], 2);
        assert_eq!(registry["registry"]["stage_counts"]["needs_review"], 3);
        assert_eq!(registry["registry"]["stage_counts"]["fallback_only"], 1);
        assert_eq!(registry["registry"]["risk_counts"]["low"], 2);
        assert_eq!(registry["registry"]["risk_counts"]["medium"], 3);
        assert_eq!(registry["registry"]["risk_counts"]["high"], 1);
    }

    #[test]
    fn avatar_cortex_renderer_registry_tracks_current_token() {
        let status = json!({
            "surface": "avatar_cortex_status",
            "project": "agent-bridge",
            "label": "com.agentbridge.avatar-cortex.agent-bridge",
            "heartbeat_label": "com.agentbridge.avatar-heartbeat.agent-bridge",
            "launchd": {"loaded": true},
            "snapshot": {"total_rows": 1},
            "events": {
                "records_count": 3,
                "unhealthy_count": 0,
                "latest": {
                    "status": "healthy",
                    "healthy": true,
                    "reason": "unchanged",
                    "ts": 300
                },
                "recent": [
                    {"status": "healthy", "healthy": true, "reason": "unchanged", "ts": 100},
                    {"status": "healthy", "healthy": true, "reason": "unchanged", "ts": 200},
                    {"status": "healthy", "healthy": true, "reason": "unchanged", "ts": 300}
                ]
            },
            "trend": {
                "step_records_delta": 0,
                "snapshot_event_lag_secs": 0,
                "learning_state": {
                    "state": "caught_up",
                    "reason": "step_matches_records"
                }
            }
        });
        let registry = avatar_cortex_renderer_registry_from_status(status);
        assert_eq!(
            registry["registry"]["current"]["token"],
            "xiao_shu::soft_bounce::low"
        );
        assert_eq!(
            registry["registry"]["current"]["binding_stage"],
            "candidate"
        );
        assert_eq!(registry["registry"]["current"]["risk_level"], "low");
    }

    #[test]
    fn avatar_cortex_binding_plan_selects_low_risk_candidates() {
        let registry = avatar_cortex_renderer_registry_payload(None);
        let plan = avatar_cortex_binding_plan_from_registry(registry);
        assert_eq!(plan["surface"], "avatar_cortex_binding_plan");
        assert_eq!(plan["read_only"], true);
        assert_eq!(plan["writes_files"], false);
        assert_eq!(plan["mutates_renderer"], false);
        assert_eq!(plan["codex_pet_package_mutation"], false);
        assert_eq!(plan["binding_plan"]["selected_count"], 2);
        assert_eq!(plan["binding_plan"]["deferred_count"], 4);
        assert_eq!(
            plan["binding_plan"]["first_candidate"]["token"],
            "xiao_shu::soft_bounce::low"
        );
        assert_eq!(
            plan["binding_plan"]["selected"][1]["token"],
            "xiao_shu::idle_breathe::low"
        );
        assert_eq!(
            plan["binding_plan"]["safety"]["requires_human_approval"],
            true
        );
    }

    #[test]
    fn avatar_cortex_binding_plan_defers_review_and_fallback_tokens() {
        let registry = avatar_cortex_renderer_registry_payload(None);
        let plan = avatar_cortex_binding_plan_from_registry(registry);
        let deferred = plan["binding_plan"]["deferred"].as_array().unwrap();
        assert!(deferred.iter().any(|entry| {
            entry["token"] == "xiao_shu::sorting_glow::medium"
                && entry["reason"] == "requires manual review before renderer binding"
        }));
        assert!(deferred.iter().any(|entry| {
            entry["token"] == "xiao_shu::unknown::fallback"
                && entry["reason"] == "fallback policy is not a named renderer binding"
        }));
        assert!(plan["binding_plan"]["validation_checklist"]
            .as_array()
            .unwrap()
            .iter()
            .any(|item| item == "needs_review and fallback_only tokens remain deferred"));
    }

    #[test]
    fn avatar_cortex_binding_fixture_freezes_selected_slot_timelines() {
        let registry = avatar_cortex_renderer_registry_payload(None);
        let plan = avatar_cortex_binding_plan_from_registry(registry);
        let fixture = avatar_cortex_binding_fixture_from_plan(plan);
        assert_eq!(fixture["surface"], "avatar_cortex_binding_fixture");
        assert_eq!(fixture["read_only"], true);
        assert_eq!(fixture["writes_files"], false);
        assert_eq!(fixture["mutates_renderer"], false);
        assert_eq!(fixture["codex_pet_package_mutation"], false);
        assert_eq!(fixture["fixture"]["fixture_count"], 2);
        assert_eq!(
            fixture["fixture"]["first_fixture"]["token"],
            "xiao_shu::soft_bounce::low"
        );
        assert_eq!(
            fixture["fixture"]["golden_payloads"][0]["target"]["motion_slot"],
            "soft_bounce"
        );
        assert_eq!(
            fixture["fixture"]["golden_payloads"][1]["token"],
            "xiao_shu::idle_breathe::low"
        );
    }

    #[test]
    fn avatar_cortex_binding_fixture_keeps_golden_assertions_safe() {
        let registry = avatar_cortex_renderer_registry_payload(None);
        let plan = avatar_cortex_binding_plan_from_registry(registry);
        let fixture = avatar_cortex_binding_fixture_from_plan(plan);
        assert_eq!(fixture["fixture"]["acceptance"]["all_return_to_idle"], true);
        assert_eq!(
            fixture["fixture"]["acceptance"]["all_duration_within_2s"],
            true
        );
        assert_eq!(
            fixture["fixture"]["acceptance"]["manual_visual_qa_required"],
            true
        );
        assert_eq!(
            fixture["fixture"]["first_fixture"]["golden_assertions"]["returns_to_idle"],
            true
        );
        assert_eq!(
            fixture["fixture"]["first_fixture"]["golden_assertions"]["duration_ms"],
            1800
        );
        assert!(!fixture["fixture"]["golden_payloads"]
            .as_array()
            .unwrap()
            .iter()
            .any(|entry| entry["token"] == "xiao_shu::sorting_glow::medium"));
    }

    #[test]
    fn avatar_cortex_visual_adapter_builds_preview_frames() {
        let registry = avatar_cortex_renderer_registry_payload(None);
        let plan = avatar_cortex_binding_plan_from_registry(registry);
        let fixture = avatar_cortex_binding_fixture_from_plan(plan);
        let adapter = avatar_cortex_visual_adapter_from_fixture(fixture);
        assert_eq!(adapter["surface"], "avatar_cortex_sidecar_visual_adapter");
        assert_eq!(adapter["read_only"], true);
        assert_eq!(adapter["renders_pixels"], false);
        assert_eq!(adapter["visual_adapter"]["preview_count"], 2);
        assert_eq!(
            adapter["visual_adapter"]["first_preview"]["token"],
            "xiao_shu::soft_bounce::low"
        );
        assert_eq!(
            adapter["visual_adapter"]["first_preview"]["frames"][2]["motion_slot"],
            "soft_bounce"
        );
        assert_eq!(
            adapter["visual_adapter"]["first_preview"]["final_state"]["motion_slot"],
            "idle_breathe"
        );
        assert_eq!(adapter["visual_adapter"]["first_preview"]["frame_count"], 4);
        assert_eq!(
            adapter["visual_adapter"]["first_preview"]["track_kind"],
            "selected"
        );
        assert_eq!(
            adapter["visual_adapter"]["first_preview"]["review_only"],
            false
        );
    }

    #[test]
    fn avatar_cortex_visual_adapter_keeps_sidecar_acceptance_safe() {
        let registry = avatar_cortex_renderer_registry_payload(None);
        let plan = avatar_cortex_binding_plan_from_registry(registry);
        let fixture = avatar_cortex_binding_fixture_from_plan(plan);
        let adapter = avatar_cortex_visual_adapter_from_fixture(fixture);
        assert_eq!(adapter["writes_files"], false);
        assert_eq!(adapter["mutates_renderer"], false);
        assert_eq!(adapter["codex_pet_package_mutation"], false);
        assert_eq!(
            adapter["visual_adapter"]["acceptance"]["all_return_to_idle"],
            true
        );
        assert_eq!(
            adapter["visual_adapter"]["acceptance"]["all_duration_within_2s"],
            true
        );
        assert_eq!(
            adapter["visual_adapter"]["acceptance"]["pixel_rendered"],
            false
        );
        assert_eq!(
            adapter["visual_adapter"]["acceptance"]["manual_visual_qa_required"],
            true
        );
    }

    #[test]
    fn avatar_cortex_renderer_view_builds_browser_tracks() {
        let registry = avatar_cortex_renderer_registry_payload(None);
        let plan = avatar_cortex_binding_plan_from_registry(registry);
        let fixture = avatar_cortex_binding_fixture_from_plan(plan);
        let adapter = avatar_cortex_visual_adapter_from_fixture(fixture);
        let view = avatar_cortex_renderer_view_from_visual_adapter_payload(adapter);
        let first = &view["renderer_view"]["first_track"];
        assert_eq!(view["surface"], "avatar_cortex_sidecar_renderer_view");
        assert_eq!(view["read_only"], true);
        assert_eq!(view["browser_renders_pixels"], true);
        assert_eq!(view["server_side_renders_pixels"], false);
        assert_eq!(view["writes_files"], false);
        assert_eq!(view["mutates_renderer"], false);
        assert_eq!(view["codex_pet_package_mutation"], false);
        assert_eq!(
            view["renderer_view"]["kind"],
            "browser_codex_pet_sprite_sidecar_renderer_view"
        );
        assert_eq!(
            view["renderer_view"]["asset_source"]["pet_id"],
            "xiao-shu-dev"
        );
        assert_eq!(
            view["renderer_view"]["asset_source"]["official_pet_package_mutation"],
            false
        );
        assert_eq!(view["renderer_view"]["track_count"], 5);
        assert_eq!(view["renderer_view"]["selected_track_count"], 2);
        assert_eq!(view["renderer_view"]["review_track_count"], 3);
        assert_eq!(first["token"], "xiao_shu::soft_bounce::low");
        assert_eq!(first["track_kind"], "selected");
        assert_eq!(first["review_only"], false);
        assert_eq!(first["frame_count"], 4);
        assert_eq!(first["duration_ms"], 1800);
        assert_eq!(
            first["renderer"]["asset_source"],
            "installed_codex_pet_package_readonly"
        );
        assert_eq!(first["renderer"]["asset_pet_id"], "xiao-shu-dev");
        assert_eq!(first["renderer"]["official_pet_package_mutation"], false);
        assert_eq!(first["semantic_variant_count"], 1);
        assert_eq!(
            first["semantic_variants"][0]["variant_id"],
            "sidecar_soft_bounce_v1"
        );
        assert_eq!(
            first["semantic_variants"][0]["sidecar_asset"]["asset_id"],
            "xiao-shu-motion-canonical-soft-bounce-v1"
        );
        assert_eq!(first["semantic_variant_review"], Value::Null);
        assert!(first["frames"][2]["css_classes"]
            .as_str()
            .unwrap()
            .contains("motion-soft-bounce"));
        assert_eq!(
            first["final_frame"]["css_classes"]
                .as_str()
                .unwrap()
                .contains("motion-idle-breathe"),
            true
        );
        let tracks = view["renderer_view"]["tracks"].as_array().unwrap();
        let idle_breathe = tracks
            .iter()
            .find(|track| track["token"] == "xiao_shu::idle_breathe::low")
            .unwrap();
        assert_eq!(idle_breathe["semantic_variant_count"], 1);
        assert_eq!(
            idle_breathe["semantic_variants"][0]["variant_id"],
            "sidecar_idle_breathe_v1"
        );
        assert_eq!(
            idle_breathe["semantic_variants"][0]["sidecar_asset"]["asset_id"],
            "xiao-shu-motion-canonical-idle-breathe-v1"
        );
        assert_eq!(idle_breathe["semantic_variant_review"], Value::Null);
        let sorting_glow = tracks
            .iter()
            .find(|track| track["token"] == "xiao_shu::sorting_glow::medium")
            .unwrap();
        assert_eq!(sorting_glow["track_kind"], "review_only");
        assert_eq!(sorting_glow["binding_stage"], "needs_review");
        assert_eq!(sorting_glow["review_only"], true);
        assert_eq!(sorting_glow["duration_ms"], 1440);
        assert_eq!(sorting_glow["semantic_variant_count"], 1);
        assert_eq!(
            sorting_glow["semantic_variants"][0]["variant_id"],
            "sidecar_sorting_glow_v1"
        );
        assert_eq!(
            sorting_glow["semantic_variants"][0]["sidecar_asset"]["asset_id"],
            "xiao-shu-motion-canonical-sorting-glow-v1"
        );
        assert_eq!(sorting_glow["semantic_variant_review"], Value::Null);
        assert!(sorting_glow["frames"]
            .as_array()
            .unwrap()
            .iter()
            .any(|frame| frame["css_classes"]
                .as_str()
                .unwrap()
                .contains("motion-sorting-glow")));
        assert!(sorting_glow["final_frame"]["css_classes"]
            .as_str()
            .unwrap()
            .contains("pose-neutral-idle"));
        assert!(sorting_glow["final_frame"]["css_classes"]
            .as_str()
            .unwrap()
            .contains("motion-idle-breathe"));
        assert!(tracks
            .iter()
            .any(|track| track["token"] == "xiao_shu::look_sideways::medium"));
        let look_sideways = tracks
            .iter()
            .find(|track| track["token"] == "xiao_shu::look_sideways::medium")
            .unwrap();
        assert_eq!(look_sideways["semantic_variant_count"], 1);
        assert_eq!(
            look_sideways["semantic_variants"][0]["variant_id"],
            "sidecar_look_sideways_v1"
        );
        assert_eq!(
            look_sideways["semantic_variants"][0]["sidecar_asset"]["asset_id"],
            "xiao-shu-motion-canonical-look-sideways-v1"
        );
        assert_eq!(look_sideways["semantic_variant_review"], Value::Null);
        let alert_peek = tracks
            .iter()
            .find(|track| track["token"] == "xiao_shu::alert_peek::medium")
            .unwrap();
        assert_eq!(alert_peek["semantic_variant_count"], 6);
        assert_eq!(alert_peek["has_semantic_variants"], true);
        assert_eq!(
            alert_peek["semantic_variants"][0]["variant_id"],
            "current_alert_row"
        );
        assert_eq!(alert_peek["semantic_variants"][0]["default"], false);
        assert_eq!(
            alert_peek["semantic_variants"][1]["variant_id"],
            "waiting_peek_row"
        );
        assert_eq!(
            alert_peek["semantic_variants"][1]["frame_choreography"]["choreography_id"],
            "alert_peek_frame_choreo_v1"
        );
        assert_eq!(
            alert_peek["semantic_variants"][1]["frame_choreography"]["uses_css_motion"],
            false
        );
        assert_eq!(
            alert_peek["semantic_variants"][1]["frame_choreography"]["frames"]
                .as_array()
                .unwrap()
                .len(),
            11
        );
        assert_eq!(
            alert_peek["semantic_variants"][1]["frame_choreography"]["frames"][5]["col"],
            5
        );
        assert_eq!(
            alert_peek["semantic_variants"][2]["variant_id"],
            "sidecar_peek_v2"
        );
        assert_eq!(
            alert_peek["semantic_variants"][2]["sidecar_asset"]["route"],
            "/avatar-surface/sidecar-spritesheet?asset=xiao-shu-alert-peek-v2"
        );
        assert_eq!(
            alert_peek["semantic_variants"][2]["frame_choreography"]["choreography_id"],
            "alert_peek_sidecar_v2_frame_choreo"
        );
        assert_eq!(
            alert_peek["semantic_variants"][3]["variant_id"],
            "sidecar_peek_v4"
        );
        assert_eq!(alert_peek["semantic_variants"][3]["default"], true);
        assert_eq!(
            alert_peek["semantic_variants"][3]["sidecar_asset"]["asset_id"],
            "xiao-shu-motion-canonical-peek-v4"
        );
        assert_eq!(
            alert_peek["semantic_variants"][3]["frame_choreography"]["choreography_id"],
            "alert_peek_sidecar_v4_frame_choreo"
        );
        assert_eq!(
            alert_peek["semantic_variants"][4]["variant_id"],
            "sidecar_peek_v3"
        );
        assert_eq!(
            alert_peek["semantic_variants"][4]["sidecar_asset"]["asset_id"],
            "xiao-shu-canonical-peek-v3"
        );
        assert_eq!(
            alert_peek["semantic_variants"][4]["frame_choreography"]["choreography_id"],
            "alert_peek_sidecar_v3_frame_choreo"
        );
        assert_eq!(alert_peek["semantic_variants"][5]["sprite_row"], 8);
        assert_eq!(
            alert_peek["semantic_variant_review"]["default_variant"],
            "sidecar_peek_v4"
        );
        assert_eq!(
            alert_peek["semantic_variant_review"]["human_review_status"],
            "visual_motion_candidate_accepted"
        );
        assert_eq!(
            alert_peek["semantic_variant_review"]["voice_linkage_preview"]["surface"],
            "alert_peek_voice_linkage_preview"
        );
        assert_eq!(
            alert_peek["semantic_variant_review"]["voice_linkage_preview"]["selected_variant"],
            "sidecar_peek_v4"
        );
        assert_eq!(
            alert_peek["semantic_variant_review"]["voice_linkage_preview"]["utterance"],
            "小舒发现一点需要你看一下。"
        );
        assert_eq!(
            alert_peek["semantic_variant_review"]["voice_linkage_preview"]["gate"]
                ["real_emit_surface"],
            "agent-bridge avatar cortex-voice-emit"
        );
        assert!(
            alert_peek["semantic_variant_review"]["voice_linkage_preview"]["gate"]["dry_run_route"]
                .as_str()
                .unwrap()
                .contains("preview_text=%E5%B0%8F%E8%88%92")
        );
        assert_eq!(
            alert_peek["semantic_variant_review"]["voice_linkage_preview"]["gate"]
                ["http_emit_route"],
            Value::Null
        );
        assert_eq!(
            alert_peek["semantic_variant_review"]["voice_linkage_preview"]["emits_audio"],
            false
        );
        assert_eq!(
            alert_peek["semantic_variant_review"]["can_promote_binding"],
            false
        );
        assert_eq!(alert_peek["semantic_variant_review"]["emits_audio"], false);
    }

    #[test]
    fn avatar_cortex_renderer_view_accepts_degraded_launchd_status() {
        let status = json!({
            "surface": "avatar_cortex_status",
            "project": "agent-bridge",
            "label": "com.agentbridge.avatar-cortex.agent-bridge",
            "heartbeat_label": "com.agentbridge.avatar-heartbeat.agent-bridge",
            "launchd": {
                "loaded": false,
                "degraded": true,
                "degraded_reason": "launchd_probe_unavailable",
                "error": "launchctl unavailable"
            },
            "snapshot": {"exists": false, "total_rows": 0},
            "events": {"records_count": 0, "unhealthy_count": 0, "recent": []},
            "trend": {
                "step_records_delta": null,
                "snapshot_event_lag_secs": null,
                "learning_state": {"state": "stale", "reason": "no_snapshot"}
            }
        });
        let view = avatar_cortex_renderer_view_from_status(status);

        assert_eq!(view["surface"], "avatar_cortex_sidecar_renderer_view");
        assert_eq!(view["read_only"], true);
        assert_eq!(view["writes_files"], false);
        assert_eq!(view["mutates_renderer"], false);
        assert_eq!(view["codex_pet_package_mutation"], false);
        assert_eq!(view["renderer_view"]["track_count"], 5);
        assert_eq!(
            view["source_visual_adapter"]["source_fixture"]["source_plan"]["registry"]
                ["source_status"]["launchd"]["degraded"],
            true
        );
    }

    #[test]
    fn avatar_cortex_renderer_view_keeps_official_package_untouched() {
        let registry = avatar_cortex_renderer_registry_payload(None);
        let plan = avatar_cortex_binding_plan_from_registry(registry);
        let fixture = avatar_cortex_binding_fixture_from_plan(plan);
        let adapter = avatar_cortex_visual_adapter_from_fixture(fixture);
        let view = avatar_cortex_renderer_view_from_visual_adapter_payload(adapter);
        let acceptance = &view["renderer_view"]["acceptance"];
        assert_eq!(view["sidecar_only"], true);
        assert_eq!(acceptance["browser_view_only"], true);
        assert_eq!(acceptance["review_tracks_require_manual_approval"], true);
        assert_eq!(acceptance["review_tracks_mutate_bindings"], false);
        assert_eq!(acceptance["asset_writes_allowed"], false);
        assert_eq!(acceptance["renderer_mutation_allowed"], false);
        assert_eq!(acceptance["codex_pet_package_mutation_allowed"], false);
        assert_eq!(
            view["renderer_view"]["asset_source"]["route"],
            "/avatar-surface/pet-spritesheet?pet_id=xiao-shu-dev"
        );
        assert_eq!(view["renderer_view"]["asset_source"]["read_only"], true);
        assert_eq!(
            view["renderer_view"]["next_step"],
            "manual browser visual QA for selected and review-only tracks before any official package binding"
        );
    }

    #[test]
    fn avatar_cortex_renderer_review_gate_keeps_review_tracks_pending() {
        let registry = avatar_cortex_renderer_registry_payload(None);
        let plan = avatar_cortex_binding_plan_from_registry(registry);
        let fixture = avatar_cortex_binding_fixture_from_plan(plan);
        let adapter = avatar_cortex_visual_adapter_from_fixture(fixture);
        let view = avatar_cortex_renderer_view_from_visual_adapter_payload(adapter);
        let gate = avatar_cortex_renderer_review_gate_from_renderer_view_payload(view);
        let review_gate = &gate["review_gate"];

        assert_eq!(gate["surface"], "avatar_cortex_renderer_review_gate");
        assert_eq!(gate["read_only"], true);
        assert_eq!(gate["writes_files"], false);
        assert_eq!(gate["mutates_renderer"], false);
        assert_eq!(gate["codex_pet_package_mutation"], false);
        assert_eq!(gate["renders_pixels"], false);
        assert_eq!(review_gate["track_count"], 5);
        assert_eq!(review_gate["selected_baseline_count"], 2);
        assert_eq!(review_gate["manual_pending_count"], 3);
        assert_eq!(review_gate["automatic_pass_count"], 5);
        assert_eq!(review_gate["acceptance"]["all_automatic_checks_pass"], true);
        assert_eq!(
            review_gate["acceptance"]["review_tracks_mutate_bindings"],
            false
        );
        assert_eq!(
            review_gate["acceptance"]["can_promote_review_tracks"],
            false
        );

        let items = review_gate["items"].as_array().unwrap();
        let sorting_glow = items
            .iter()
            .find(|item| item["token"] == "xiao_shu::sorting_glow::medium")
            .unwrap();
        assert_eq!(sorting_glow["manual_decision"], "pending");
        assert_eq!(sorting_glow["automatic_gate"], "ready_for_manual_review");
        assert_eq!(sorting_glow["can_promote_binding"], false);
        assert_eq!(sorting_glow["auto_checks"]["returns_to_idle"], true);
        assert!(sorting_glow["review_questions"]
            .as_array()
            .unwrap()
            .iter()
            .any(|question| question == "does the glow imply urgency"));
    }

    #[test]
    fn avatar_cortex_renderer_review_packet_is_not_approval_state() {
        let registry = avatar_cortex_renderer_registry_payload(None);
        let plan = avatar_cortex_binding_plan_from_registry(registry);
        let fixture = avatar_cortex_binding_fixture_from_plan(plan);
        let adapter = avatar_cortex_visual_adapter_from_fixture(fixture);
        let view = avatar_cortex_renderer_view_from_visual_adapter_payload(adapter);
        let gate = avatar_cortex_renderer_review_gate_from_renderer_view_payload(view);
        let packet = avatar_cortex_renderer_review_packet_from_review_gate_payload(gate);
        let review_packet = &packet["review_packet"];

        assert_eq!(packet["surface"], "avatar_cortex_renderer_review_packet");
        assert_eq!(packet["read_only"], true);
        assert_eq!(packet["writes_files"], false);
        assert_eq!(packet["mutates_renderer"], false);
        assert_eq!(packet["codex_pet_package_mutation"], false);
        assert_eq!(packet["writes_approval"], false);
        assert_eq!(packet["persists_review_record"], false);
        assert_eq!(review_packet["packet_count"], 3);
        assert_eq!(review_packet["baseline_reference_count"], 2);
        assert_eq!(
            review_packet["acceptance"]["approval_writes_allowed"],
            false
        );
        assert_eq!(
            review_packet["acceptance"]["can_promote_review_tracks"],
            false
        );
        assert_eq!(review_packet["acceptance"]["records_persisted"], false);

        let packets = review_packet["packets"].as_array().unwrap();
        let alert = packets
            .iter()
            .find(|item| item["token"] == "xiao_shu::alert_peek::medium")
            .unwrap();
        assert_eq!(alert["approval_state"], "not_approved");
        assert_eq!(alert["default_decision"], "keep_pending");
        assert_eq!(alert["can_promote_binding"], false);
        assert_eq!(alert["writes_approval"], false);
        assert_eq!(
            alert["renderer_view"]["track"],
            "xiao_shu::alert_peek::medium"
        );
        assert_eq!(
            alert["review_packet"]["latest_human_feedback"]["outcome"],
            "accept_visual_motion_candidate"
        );
        assert_eq!(alert["review_packet"]["voice_linkage"]["requested"], true);
        assert_eq!(
            alert["review_packet"]["voice_linkage"]["emits_audio_now"],
            false
        );
        assert!(alert["review_packet"]["revision_response"]
            .as_array()
            .unwrap()
            .iter()
            .any(|step| step == "mute the attention mark brightness"));
        assert!(alert["review_packet"]["required_human_checks"]
            .as_array()
            .unwrap()
            .iter()
            .any(|check| check
                == "should this ever pair with sparse voice output, or stay visual-only"));
    }

    #[test]
    fn avatar_cortex_renderer_review_report_marks_packets_ready_but_unapproved() {
        let registry = avatar_cortex_renderer_registry_payload(None);
        let plan = avatar_cortex_binding_plan_from_registry(registry);
        let fixture = avatar_cortex_binding_fixture_from_plan(plan);
        let adapter = avatar_cortex_visual_adapter_from_fixture(fixture);
        let view = avatar_cortex_renderer_view_from_visual_adapter_payload(adapter);
        let gate = avatar_cortex_renderer_review_gate_from_renderer_view_payload(view);
        let packet = avatar_cortex_renderer_review_packet_from_review_gate_payload(gate);
        let report = avatar_cortex_renderer_review_report_from_packet_payload(packet);
        let review_report = &report["review_report"];

        assert_eq!(report["surface"], "avatar_cortex_renderer_review_report");
        assert_eq!(report["read_only"], true);
        assert_eq!(report["writes_files"], false);
        assert_eq!(report["mutates_renderer"], false);
        assert_eq!(report["codex_pet_package_mutation"], false);
        assert_eq!(report["writes_approval"], false);
        assert_eq!(report["persists_review_record"], false);
        assert_eq!(review_report["packet_count"], 3);
        assert_eq!(review_report["ready_packet_count"], 3);
        assert_eq!(review_report["blocked_packet_count"], 0);
        assert_eq!(review_report["human_feedback_count"], 1);
        assert_eq!(review_report["voice_linkage_requested_count"], 1);
        assert_eq!(review_report["human_decision_count"], 0);
        assert_eq!(
            review_report["report_state"],
            "ready_for_human_visual_review"
        );
        assert_eq!(
            review_report["acceptance"]["ready_for_human_visual_review"],
            true
        );
        assert_eq!(review_report["acceptance"]["ready_for_approval"], false);
        assert_eq!(
            review_report["acceptance"]["can_promote_review_tracks"],
            false
        );
        assert_eq!(
            review_report["acceptance"]["merge_without_human_review_allowed"],
            false
        );

        let items = review_report["items"].as_array().unwrap();
        let look_sideways = items
            .iter()
            .find(|item| item["token"] == "xiao_shu::look_sideways::medium")
            .unwrap();
        assert_eq!(look_sideways["readiness"], "ready_for_human_visual_review");
        assert_eq!(look_sideways["ready_for_approval"], false);
        assert_eq!(look_sideways["can_promote_binding"], false);
        assert_eq!(look_sideways["evidence_counts"]["source_blockers"], 0);

        let alert = items
            .iter()
            .find(|item| item["token"] == "xiao_shu::alert_peek::medium")
            .unwrap();
        assert_eq!(alert["human_feedback_present"], true);
        assert_eq!(alert["voice_linkage_requested"], true);
        assert_eq!(
            alert["latest_human_feedback"]["outcome"],
            "accept_visual_motion_candidate"
        );
        assert_eq!(alert["voice_linkage"]["emits_audio_now"], false);
        assert_eq!(alert["evidence_counts"]["revision_response"], 7);
    }

    #[test]
    fn avatar_cortex_review_record_writes_cli_only_approval() {
        let registry = avatar_cortex_renderer_registry_payload(None);
        let plan = avatar_cortex_binding_plan_from_registry(registry);
        let fixture = avatar_cortex_binding_fixture_from_plan(plan);
        let adapter = avatar_cortex_visual_adapter_from_fixture(fixture);
        let view = avatar_cortex_renderer_view_from_visual_adapter_payload(adapter);
        let root =
            std::env::temp_dir().join(format!("agent-bridge-xiao-review-record-{}", now_secs()));
        std::fs::create_dir_all(&root).unwrap();
        let path = root.join("review_records.jsonl");
        let notes = vec!["v4 keeps the raised hand and restores Xiao Shu identity".to_string()];
        let opts = AvatarCortexReviewRecordOptions {
            label: None,
            heartbeat_label: None,
            project: Some("agent-bridge"),
            output: None,
            requested_track: Some("xiao_shu::alert_peek::medium"),
            requested_variant: Some("sidecar_peek_v4"),
            outcome: Some("approved"),
            reviewer: Some("unit-test"),
            reason: Some("visual review accepted v4"),
            notes: &notes,
            confirm: true,
        };
        let payload =
            avatar_cortex_review_record_from_renderer_view_payload(view, &opts, &path).unwrap();

        assert_eq!(payload["surface"], "avatar_cortex_review_record");
        assert_eq!(payload["cli_only"], true);
        assert_eq!(payload["http_available"], false);
        assert_eq!(payload["persists_review_record"], true);
        assert_eq!(payload["writes_approval"], true);
        assert_eq!(payload["writes_files"], true);
        assert_eq!(payload["emits_audio"], false);
        assert_eq!(payload["mutates_renderer"], false);
        assert_eq!(payload["codex_pet_package_mutation"], false);
        assert_eq!(payload["can_promote_binding"], false);
        assert_eq!(payload["record"]["outcome"], "approved");
        assert_eq!(payload["record"]["variant"], "sidecar_peek_v4");

        let records = read_jsonl_records(&path).unwrap();
        assert_eq!(records.len(), 1);
        assert_eq!(records[0]["track"], "xiao_shu::alert_peek::medium");
        assert_eq!(records[0]["approval_state"], "approved");
    }

    #[test]
    fn avatar_cortex_review_report_reflects_persisted_review_records() {
        let registry = avatar_cortex_renderer_registry_payload(None);
        let plan = avatar_cortex_binding_plan_from_registry(registry);
        let fixture = avatar_cortex_binding_fixture_from_plan(plan);
        let adapter = avatar_cortex_visual_adapter_from_fixture(fixture);
        let view = avatar_cortex_renderer_view_from_visual_adapter_payload(adapter);
        let gate = avatar_cortex_renderer_review_gate_from_renderer_view_payload(view);
        let packet = avatar_cortex_renderer_review_packet_from_review_gate_payload(gate);
        let records = vec![json!({
            "schema": 1,
            "review_id": "xsrrev-test",
            "created_at": 1,
            "updated_at": 1,
            "project": "agent-bridge",
            "track": "xiao_shu::alert_peek::medium",
            "variant": "sidecar_peek_v4",
            "outcome": "approved",
            "approval_state": "approved",
            "reviewer": "unit-test",
            "reason": "visual review accepted v4",
            "notes": ["looks correct"],
            "cli_only": true,
            "can_promote_binding": false,
            "codex_pet_package_mutation": false,
        })];
        let report = avatar_cortex_renderer_review_report_from_packet_payload_with_records(
            packet,
            "agent-bridge",
            &records,
        );
        let review_report = &report["review_report"];

        assert_eq!(review_report["human_decision_count"], 1);
        assert_eq!(review_report["approved_count"], 1);
        assert_eq!(review_report["review_record_count"], 1);
        assert_eq!(review_report["acceptance"]["records_persisted"], true);
        assert_eq!(review_report["acceptance"]["ready_for_approval"], true);
        assert_eq!(
            review_report["acceptance"]["can_promote_review_tracks"],
            false
        );

        let alert = review_report["items"]
            .as_array()
            .unwrap()
            .iter()
            .find(|item| item["token"] == "xiao_shu::alert_peek::medium")
            .unwrap();
        assert_eq!(alert["approval_state"], "approved");
        assert_eq!(alert["ready_for_approval"], true);
        assert_eq!(alert["can_promote_binding"], false);
        assert_eq!(alert["human_decision_present"], true);
        assert_eq!(alert["latest_review_record"]["review_id"], "xsrrev-test");
        assert!(alert["review_record_command"]
            .as_str()
            .unwrap()
            .contains("cortex-review-record"));
    }

    #[test]
    fn avatar_cortex_voice_policy_keeps_real_audio_cli_only() {
        let registry = avatar_cortex_renderer_registry_payload(None);
        let plan = avatar_cortex_binding_plan_from_registry(registry);
        let fixture = avatar_cortex_binding_fixture_from_plan(plan);
        let adapter = avatar_cortex_visual_adapter_from_fixture(fixture);
        let view = avatar_cortex_renderer_view_from_visual_adapter_payload(adapter);
        let payload = avatar_cortex_voice_policy_from_renderer_view_payload(view);
        let policy = &payload["voice_policy"];

        assert_eq!(payload["surface"], "avatar_cortex_voice_policy");
        assert_eq!(payload["read_only"], true);
        assert_eq!(payload["dry_run"], true);
        assert_eq!(payload["emits_audio"], false);
        assert_eq!(payload["http_emit_route_added"], false);
        assert_eq!(policy["track_count"], 5);
        assert_eq!(policy["manual_cli_emit_count"], 1);
        assert_eq!(policy["auto_emit_count"], 0);
        assert_eq!(policy["gate"]["http_emit_route"], Value::Null);
        assert_eq!(
            policy["gate"]["real_emit_surface"],
            "agent-bridge avatar cortex-voice-emit"
        );
        assert_eq!(policy["acceptance"]["http_emit_route_added"], false);
        assert_eq!(
            policy["acceptance"]["codex_pet_package_mutation_allowed"],
            false
        );

        let rules = policy["rules"].as_array().unwrap();
        assert!(rules.iter().all(|rule| rule["auto_emit_allowed"] == false));
        let alert = rules
            .iter()
            .find(|rule| rule["token"] == "xiao_shu::alert_peek::medium")
            .unwrap();
        assert_eq!(alert["mode"], "manual_cli_emit_after_attention");
        assert_eq!(alert["manual_cli_emit_allowed"], true);
        assert_eq!(alert["utterance"], "小舒发现一点需要你看一下。");
        assert_eq!(alert["visual_variant"], "sidecar_peek_v4");
        assert_eq!(alert["suggested_voice"], "Flo (中文（中国大陆）)");
        assert_eq!(alert["suggested_rate"], 190);
        assert_eq!(alert["http_emit_route"], Value::Null);
        assert_eq!(alert["binding_promotable"], false);

        let idle = rules
            .iter()
            .find(|rule| rule["token"] == "xiao_shu::idle_breathe::low")
            .unwrap();
        assert_eq!(idle["mode"], "silent_presence");
        assert_eq!(idle["manual_cli_emit_allowed"], false);
    }

    #[test]
    fn avatar_cortex_voice_request_previews_second_step_without_audio() {
        let registry = avatar_cortex_renderer_registry_payload(None);
        let plan = avatar_cortex_binding_plan_from_registry(registry);
        let fixture = avatar_cortex_binding_fixture_from_plan(plan);
        let adapter = avatar_cortex_visual_adapter_from_fixture(fixture);
        let view = avatar_cortex_renderer_view_from_visual_adapter_payload(adapter);
        let policy = avatar_cortex_voice_policy_from_renderer_view_payload(view);
        let payload = avatar_cortex_voice_request_from_policy_payload(
            policy,
            Some("xiao_shu::alert_peek::medium"),
            Some("agent-bridge"),
            Some("manual confirmation"),
        );
        let request = &payload["voice_request"];

        assert_eq!(payload["surface"], "avatar_cortex_voice_request");
        assert_eq!(payload["read_only"], true);
        assert_eq!(payload["dry_run"], true);
        assert_eq!(payload["emits_audio"], false);
        assert_eq!(payload["http_emit_route_added"], false);
        assert_eq!(payload["writes_approval"], false);
        assert_eq!(payload["persists_request_record"], false);
        assert_eq!(request["request_state"], "ready_for_operator_confirmation");
        assert_eq!(request["selected_token"], "xiao_shu::alert_peek::medium");
        assert_eq!(request["line"], "小舒发现一点需要你看一下。");
        assert_eq!(request["visual_variant"], "sidecar_peek_v4");
        assert_eq!(request["manual_cli_emit_allowed"], true);
        assert_eq!(request["auto_emit_allowed"], false);
        assert_eq!(request["requires_second_step"], true);
        assert_eq!(request["operator_reason_present"], true);
        assert_eq!(request["operator_reason"], "manual confirmation");
        assert_eq!(request["http_emit_route"], Value::Null);
        assert_eq!(request["safety"]["emits_audio"], false);
        assert_eq!(request["safety"]["cli_only_real_emit"], true);
        assert_eq!(
            request["safety"]["codex_pet_package_mutation_allowed"],
            false
        );
        assert!(request["command_args"]
            .as_array()
            .unwrap()
            .iter()
            .any(|arg| arg == "--allow-policy-override"));
        assert!(request["command_args"]
            .as_array()
            .unwrap()
            .iter()
            .any(|arg| arg == "小舒发现一点需要你看一下。"));

        let blocked = avatar_cortex_voice_request_from_policy_payload(
            payload["source_voice_policy"].clone(),
            Some("xiao_shu::idle_breathe::low"),
            Some("agent-bridge"),
            None,
        );
        assert_eq!(
            blocked["voice_request"]["request_state"],
            "blocked_missing_utterance"
        );
        assert_eq!(blocked["voice_request"]["manual_cli_emit_allowed"], false);
        assert_eq!(blocked["voice_request"]["command_args"], Value::Null);
    }

    #[test]
    fn avatar_cortex_voice_confirm_previews_cli_action_without_audio() {
        let registry = avatar_cortex_renderer_registry_payload(None);
        let plan = avatar_cortex_binding_plan_from_registry(registry);
        let fixture = avatar_cortex_binding_fixture_from_plan(plan);
        let adapter = avatar_cortex_visual_adapter_from_fixture(fixture);
        let view = avatar_cortex_renderer_view_from_visual_adapter_payload(adapter);
        let policy = avatar_cortex_voice_policy_from_renderer_view_payload(view);
        let request = avatar_cortex_voice_request_from_policy_payload(
            policy,
            Some("xiao_shu::alert_peek::medium"),
            Some("agent-bridge"),
            Some("manual confirmation"),
        );
        let payload = avatar_cortex_voice_confirm_from_request_payload(request, true);
        let confirm = &payload["voice_confirm"];

        assert_eq!(payload["surface"], "avatar_cortex_voice_confirm");
        assert_eq!(payload["read_only"], true);
        assert_eq!(payload["dry_run"], true);
        assert_eq!(payload["emits_audio"], false);
        assert_eq!(payload["http_emit_route_added"], false);
        assert_eq!(payload["writes_approval"], false);
        assert_eq!(payload["persists_confirmation_record"], false);
        assert_eq!(
            confirm["confirmation_state"],
            "would_execute_cli_emit_if_operator_runs_command"
        );
        assert_eq!(confirm["confirm_requested"], true);
        assert_eq!(confirm["would_execute_cli"], true);
        assert_eq!(confirm["would_emit_audio"], false);
        assert_eq!(confirm["actual_execution_available_here"], false);
        assert_eq!(confirm["selected_token"], "xiao_shu::alert_peek::medium");
        assert_eq!(confirm["line"], "小舒发现一点需要你看一下。");
        assert_eq!(confirm["operator_reason_present"], true);
        assert_eq!(confirm["http_emit_route"], Value::Null);
        assert_eq!(confirm["safety"]["emits_audio"], false);
        assert_eq!(confirm["safety"]["http_emit_route_added"], false);
        assert_eq!(
            confirm["safety"]["codex_pet_package_mutation_allowed"],
            false
        );
        assert!(confirm["command_args"]
            .as_array()
            .unwrap()
            .iter()
            .any(|arg| arg == "--allow-policy-override"));
        assert_eq!(
            confirm["action_surface"],
            "agent-bridge avatar cortex-voice-action"
        );
        assert!(confirm["action_command_args"]
            .as_array()
            .unwrap()
            .iter()
            .any(|arg| arg == "cortex-voice-action"));
        assert!(confirm["action_command_preview"]
            .as_str()
            .unwrap()
            .contains("--confirm --emit"));

        let waiting = avatar_cortex_voice_confirm_from_request_payload(
            payload["source_voice_request"].clone(),
            false,
        );
        assert_eq!(
            waiting["voice_confirm"]["confirmation_state"],
            "waiting_for_operator_confirmation"
        );
        assert_eq!(waiting["voice_confirm"]["would_execute_cli"], false);
        assert_eq!(waiting["voice_confirm"]["command_args"], Value::Null);

        let missing_reason_request = avatar_cortex_voice_request_from_policy_payload(
            waiting["source_voice_request"]["source_voice_policy"].clone(),
            Some("xiao_shu::alert_peek::medium"),
            Some("agent-bridge"),
            None,
        );
        let missing_reason =
            avatar_cortex_voice_confirm_from_request_payload(missing_reason_request, true);
        assert_eq!(
            missing_reason["voice_confirm"]["confirmation_state"],
            "blocked_missing_operator_reason"
        );
        assert_eq!(missing_reason["voice_confirm"]["would_execute_cli"], false);
    }

    #[test]
    fn avatar_cortex_voice_action_wraps_confirm_before_emit() {
        let registry = avatar_cortex_renderer_registry_payload(None);
        let plan = avatar_cortex_binding_plan_from_registry(registry);
        let fixture = avatar_cortex_binding_fixture_from_plan(plan);
        let adapter = avatar_cortex_visual_adapter_from_fixture(fixture);
        let view = avatar_cortex_renderer_view_from_visual_adapter_payload(adapter);
        let policy = avatar_cortex_voice_policy_from_renderer_view_payload(view);
        let request = avatar_cortex_voice_request_from_policy_payload(
            policy,
            Some("xiao_shu::alert_peek::medium"),
            Some("agent-bridge"),
            Some("manual confirmation"),
        );
        let confirm = avatar_cortex_voice_confirm_from_request_payload(request, true);
        let opts = AvatarCortexVoiceActionOptions {
            label: None,
            heartbeat_label: None,
            project: Some("agent-bridge"),
            output: None,
            requested_track: Some("xiao_shu::alert_peek::medium"),
            reason: Some("manual confirmation"),
            confirm: true,
            emit: false,
            force: false,
            cooldown_secs: 300,
            tts_voice: None,
            tts_rate: None,
        };
        let action = avatar_cortex_voice_action_from_confirm_payload(confirm, &opts).unwrap();

        assert_eq!(action["surface"], "avatar_cortex_voice_action");
        assert_eq!(action["cli_only"], true);
        assert_eq!(action["http_available"], false);
        assert_eq!(action["read_only"], true);
        assert_eq!(action["dry_run"], true);
        assert_eq!(action["requested_emit"], false);
        assert_eq!(action["actual_emit_invoked"], false);
        assert_eq!(action["emitted"], false);
        assert_eq!(action["emits_audio"], false);
        assert_eq!(
            action["action"]["confirmation_state"],
            "would_execute_cli_emit_if_operator_runs_command"
        );
        assert_eq!(action["action"]["confirmed"], true);
        assert_eq!(action["action"]["blocked"], true);
        assert!(action["action"]["blocked_reasons"]
            .as_array()
            .unwrap()
            .iter()
            .any(|reason| reason == "emit_flag_missing"));
        assert!(action["action"]["command_preview"]
            .as_str()
            .unwrap()
            .contains("cortex-voice-action"));
        assert_eq!(action["source_voice_emit"], Value::Null);

        let waiting = avatar_cortex_voice_confirm_from_request_payload(
            action["source_voice_confirm"]["source_voice_request"].clone(),
            false,
        );
        let blocked_opts = AvatarCortexVoiceActionOptions {
            emit: true,
            confirm: false,
            ..opts
        };
        let blocked =
            avatar_cortex_voice_action_from_confirm_payload(waiting, &blocked_opts).unwrap();
        let reasons = blocked["action"]["blocked_reasons"].as_array().unwrap();
        assert!(reasons
            .iter()
            .any(|reason| reason == "confirm_flag_missing"));
        assert!(reasons
            .iter()
            .any(|reason| reason == "confirmation_not_ready"));
        assert_eq!(blocked["actual_emit_invoked"], false);
        assert_eq!(blocked["emits_audio"], false);
    }

    #[test]
    fn avatar_cortex_voice_action_preview_reports_cooldown_without_audio() {
        let registry = avatar_cortex_renderer_registry_payload(None);
        let plan = avatar_cortex_binding_plan_from_registry(registry);
        let fixture = avatar_cortex_binding_fixture_from_plan(plan);
        let adapter = avatar_cortex_visual_adapter_from_fixture(fixture);
        let view = avatar_cortex_renderer_view_from_visual_adapter_payload(adapter);
        let policy = avatar_cortex_voice_policy_from_renderer_view_payload(view);
        let request = avatar_cortex_voice_request_from_policy_payload(
            policy,
            Some("xiao_shu::alert_peek::medium"),
            Some("agent-bridge"),
            Some("manual confirmation"),
        );
        let confirm = avatar_cortex_voice_confirm_from_request_payload(request, true);
        let opts = AvatarCortexVoiceActionPreviewOptions {
            label: None,
            heartbeat_label: Some("com.agentbridge.avatar-heartbeat.agent-bridge"),
            project: Some("agent-bridge"),
            output: None,
            requested_track: Some("xiao_shu::alert_peek::medium"),
            reason: Some("manual confirmation"),
            confirm: true,
            force: false,
            cooldown_secs: 300,
            tts_voice: None,
            tts_rate: None,
        };
        let preview = avatar_cortex_voice_action_preview_from_confirm_payload(
            confirm.clone(),
            &opts,
            Some(1_000),
            None,
            None,
            1_100,
        );

        assert_eq!(preview["surface"], "avatar_cortex_voice_action_preview");
        assert_eq!(preview["read_only"], true);
        assert_eq!(preview["dry_run"], true);
        assert_eq!(preview["actual_emit_invoked"], false);
        assert_eq!(preview["writes_files"], false);
        assert_eq!(preview["emits_audio"], false);
        assert_eq!(preview["would_emit_audio"], false);
        assert_eq!(preview["action_preview"]["ready_to_emit_now"], false);
        assert_eq!(preview["action_preview"]["blocked"], true);
        assert!(preview["action_preview"]["blocked_reasons"]
            .as_array()
            .unwrap()
            .iter()
            .any(|reason| reason == "cooldown_active"));
        assert_eq!(preview["gate_dry_run"]["cooldown"]["active"], true);
        assert!(preview["action_preview"]["command_preview"]
            .as_str()
            .unwrap()
            .contains("cortex-voice-action"));

        let forced_opts = AvatarCortexVoiceActionPreviewOptions {
            force: true,
            ..opts
        };
        let forced = avatar_cortex_voice_action_preview_from_confirm_payload(
            confirm,
            &forced_opts,
            Some(1_000),
            None,
            None,
            1_100,
        );
        assert_eq!(forced["action_preview"]["ready_to_emit_now"], true);
        assert_eq!(forced["would_emit_audio"], true);
        assert_eq!(forced["action_preview"]["blocked"], false);
        assert_eq!(
            forced["action_preview"]["blocked_reasons"]
                .as_array()
                .unwrap()
                .len(),
            0
        );
    }

    #[test]
    fn xiao_shu_action_request_keeps_llm_behind_confirmation() {
        let registry = avatar_cortex_renderer_registry_payload(None);
        let plan = avatar_cortex_binding_plan_from_registry(registry);
        let fixture = avatar_cortex_binding_fixture_from_plan(plan);
        let adapter = avatar_cortex_visual_adapter_from_fixture(fixture);
        let view = avatar_cortex_renderer_view_from_visual_adapter_payload(adapter);
        let policy = avatar_cortex_voice_policy_from_renderer_view_payload(view);
        let request = avatar_cortex_voice_request_from_policy_payload(
            policy,
            Some("xiao_shu::alert_peek::medium"),
            Some("agent-bridge"),
            Some("manual confirmation"),
        );
        let confirm = avatar_cortex_voice_confirm_from_request_payload(request, true);
        let preview_opts = AvatarCortexVoiceActionPreviewOptions {
            label: None,
            heartbeat_label: None,
            project: Some("agent-bridge"),
            output: None,
            requested_track: Some("xiao_shu::alert_peek::medium"),
            reason: Some("manual confirmation"),
            confirm: true,
            force: true,
            cooldown_secs: 300,
            tts_voice: None,
            tts_rate: None,
        };
        let action_preview = avatar_cortex_voice_action_preview_from_confirm_payload(
            confirm,
            &preview_opts,
            None,
            None,
            None,
            1_100,
        );
        let action_preview_for_details = action_preview.clone();
        let opts = XiaoShuActionRequestOptions {
            label: None,
            heartbeat_label: None,
            project: Some("agent-bridge"),
            output: None,
            actor: Some("llm"),
            intent: Some("voice_alert"),
            message: Some("please alert the operator"),
            requested_track: Some("xiao_shu::alert_peek::medium"),
            reason: Some("manual confirmation"),
            confirm: false,
            force: false,
            cooldown_secs: 300,
            tts_voice: None,
            tts_rate: None,
            include_details: false,
        };
        let request = xiao_shu_action_request_from_preview(
            action_preview,
            &opts,
            "agent-bridge",
            "voice_alert",
            "xiao_shu::alert_peek::medium",
            "manual confirmation",
        );

        assert_eq!(request["surface"], "xiao_shu_action_request");
        assert_eq!(request["llm_safe"], true);
        assert_eq!(request["read_only"], true);
        assert_eq!(request["dry_run"], true);
        assert_eq!(request["direct_pet_control_allowed"], false);
        assert_eq!(request["actual_emit_invoked"], false);
        assert_eq!(request["emits_audio"], false);
        assert_eq!(request["http_emit_route_added"], false);
        assert_eq!(request["include_details"], false);
        assert_eq!(request["compact_downstream_action_preview"], true);
        assert_eq!(request["downstream_action_preview"]["compact"], true);
        assert!(request["downstream_action_preview"]["source_voice_confirm"].is_null());
        assert!(
            request["downstream_action_preview"]["action_preview"]["command_preview"]
                .as_str()
                .unwrap()
                .contains("cortex-voice-action")
        );
        assert_eq!(
            request["action_request"]["request_state"],
            "requires_human_confirmation"
        );
        assert_eq!(request["action_request"]["actor"], "llm");
        assert_eq!(request["action_request"]["supported_intent"], true);
        assert_eq!(request["action_request"]["direct_llm_emit_allowed"], false);
        assert_eq!(
            request["action_request"]["real_emit_requires_local_cli"],
            true
        );
        assert_eq!(request["action_request"]["ready_for_local_cli_emit"], false);
        assert!(request["action_request"]["blocked_reasons"]
            .as_array()
            .unwrap()
            .iter()
            .any(|reason| reason == "human_confirmation_required"));
        assert!(request["action_request"]["confirm_request_command"]
            .as_str()
            .unwrap()
            .contains("--confirm"));
        assert!(request["action_request"]["emit_command"]
            .as_str()
            .unwrap()
            .contains("cortex-voice-action"));

        let unsupported = xiao_shu_action_request_from_preview(
            request["downstream_action_preview"].clone(),
            &opts,
            "agent-bridge",
            "dance_now",
            "xiao_shu::alert_peek::medium",
            "manual confirmation",
        );
        assert_eq!(
            unsupported["action_request"]["request_state"],
            "blocked_unsupported_intent"
        );
        assert_eq!(unsupported["action_request"]["supported_intent"], false);

        let detailed_opts = XiaoShuActionRequestOptions {
            include_details: true,
            ..opts
        };
        let detailed = xiao_shu_action_request_from_preview(
            action_preview_for_details,
            &detailed_opts,
            "agent-bridge",
            "voice_alert",
            "xiao_shu::alert_peek::medium",
            "manual confirmation",
        );
        assert_eq!(detailed["include_details"], true);
        assert_eq!(detailed["compact_downstream_action_preview"], false);
        assert_eq!(
            detailed["downstream_action_preview"]["source_voice_confirm"]["surface"],
            "avatar_cortex_voice_confirm"
        );
        let compact_len = serde_json::to_string(&request).unwrap().len();
        let detailed_len = serde_json::to_string(&detailed).unwrap().len();
        assert!(compact_len < detailed_len / 2);
    }

    #[test]
    fn xiao_shu_action_enqueue_record_is_pending_and_non_emitting() {
        let request_payload = json!({
            "surface": "xiao_shu_action_request",
            "read_only": true,
            "dry_run": true,
            "llm_safe": true,
            "action_request": {
                "actor": "codex",
                "intent": "voice_alert",
                "message": "please look",
                "reason": "unit-test",
                "mapped_track": "xiao_shu::alert_peek::medium",
                "request_state": "requires_human_confirmation",
                "requires_human_confirmation": true,
                "human_confirmation_present": false,
                "direct_llm_emit_allowed": false
            }
        });
        let queue_path = Path::new("/tmp/xiao-shu-requests.jsonl");
        let record = xiao_shu_action_enqueue_record_from_request(
            request_payload,
            "agent-bridge",
            queue_path,
            1_779_470_000,
        );

        assert_eq!(record["schema"], 1);
        assert!(record["request_id"]
            .as_str()
            .unwrap()
            .starts_with("xsr-1779470000-"));
        assert_eq!(record["state"], "pending_human_confirmation");
        assert_eq!(record["llm_safe"], true);
        assert_eq!(record["sidecar_only"], true);
        assert_eq!(record["direct_pet_control_allowed"], false);
        assert_eq!(record["direct_llm_emit_allowed"], false);
        assert_eq!(record["requires_human_confirmation"], true);
        assert_eq!(record["human_confirmation_present"], false);
        assert_eq!(record["actual_emit_invoked"], false);
        assert_eq!(record["emits_audio"], false);
        assert_eq!(record["writes_request_record"], true);
        assert_eq!(record["writes_cooldown_state"], false);
        assert_eq!(record["codex_pet_package_mutation"], false);
        assert_eq!(record["queue_path"], queue_path.to_string_lossy().as_ref());
        assert!(record["local_confirm_command"]
            .as_str()
            .unwrap()
            .contains("xiao-shu-action-request-action"));
        assert!(record["local_emit_command"]
            .as_str()
            .unwrap()
            .contains("--confirm --emit"));
        assert_eq!(record["action_request"]["actor"], "codex");
        assert_eq!(
            record["source_request"]["action_request"]["request_state"],
            "requires_human_confirmation"
        );
    }

    #[test]
    fn xiao_shu_action_queue_lists_pending_without_emitting() {
        let root =
            std::env::temp_dir().join(format!("agent-bridge-xiao-shu-action-queue-{}", now_secs()));
        std::fs::create_dir_all(&root).unwrap();

        let request_payload = json!({
            "surface": "xiao_shu_action_request",
            "read_only": true,
            "dry_run": true,
            "llm_safe": true,
            "action_request": {
                "actor": "codex",
                "intent": "voice_alert",
                "message": "please look",
                "reason": "unit-test",
                "mapped_track": "xiao_shu::alert_peek::medium",
                "request_state": "requires_human_confirmation",
                "requires_human_confirmation": true,
                "human_confirmation_present": false,
                "direct_llm_emit_allowed": false
            }
        });
        let queue_path = root.join("requests.jsonl");
        let older = xiao_shu_action_enqueue_record_from_request(
            request_payload.clone(),
            "agent-bridge",
            &queue_path,
            1_779_470_000,
        );
        let newer = xiao_shu_action_enqueue_record_from_request(
            request_payload,
            "agent-bridge",
            &queue_path,
            1_779_470_100,
        );
        append_jsonl(&queue_path, &older).unwrap();
        append_jsonl(&queue_path, &newer).unwrap();

        let queue = xiao_shu_action_request_queue_from_path(
            &XiaoShuActionRequestQueueOptions {
                project: Some("agent-bridge"),
                request_id: None,
                state: None,
                include_all_states: false,
                include_details: false,
                limit: 1,
            },
            "agent-bridge",
            &queue_path,
        )
        .unwrap();

        assert_eq!(queue["surface"], "xiao_shu_action_request_queue");
        assert_eq!(queue["read_only"], true);
        assert_eq!(queue["actual_emit_invoked"], false);
        assert_eq!(queue["emits_audio"], false);
        assert_eq!(queue["direct_pet_control_allowed"], false);
        assert_eq!(queue["writes_request_record"], false);
        assert_eq!(queue["queue"]["exists"], true);
        assert_eq!(queue["queue"]["state_filter"], "pending_human_confirmation");
        assert_eq!(queue["queue"]["include_details"], false);
        assert_eq!(queue["queue"]["parsed_records"], 2);
        assert_eq!(queue["queue"]["current_records"], 2);
        assert_eq!(queue["queue"]["matching_records"], 2);
        assert_eq!(queue["queue"]["returned_count"], 1);
        assert_eq!(queue["records"][0]["compact"], true);
        assert_eq!(queue["records"][0]["source_request"], Value::Null);
        assert_eq!(
            queue["records"][0]["request_id"].as_str(),
            newer.get("request_id").and_then(Value::as_str)
        );

        let request_id = older["request_id"].as_str().unwrap();
        let one = xiao_shu_action_request_queue_from_path(
            &XiaoShuActionRequestQueueOptions {
                project: Some("agent-bridge"),
                request_id: Some(request_id),
                state: None,
                include_all_states: false,
                include_details: false,
                limit: 10,
            },
            "agent-bridge",
            &queue_path,
        )
        .unwrap();
        assert_eq!(one["queue"]["request_id_filter"], request_id);
        assert_eq!(one["queue"]["include_details"], true);
        assert_eq!(one["records"][0]["request_id"], request_id);
        assert_eq!(
            one["records"][0]["source_request"]["surface"],
            "xiao_shu_action_request"
        );

        let _ = std::fs::remove_dir_all(root);
    }

    #[test]
    fn xiao_shu_action_request_includes_read_only_queue_summary() {
        let payload = xiao_shu_action_request(&XiaoShuActionRequestOptions {
            label: None,
            heartbeat_label: None,
            project: Some("agent-bridge"),
            output: None,
            actor: Some("llm"),
            intent: Some("voice_alert"),
            message: None,
            requested_track: None,
            reason: Some("unit-test"),
            confirm: false,
            force: false,
            cooldown_secs: 300,
            tts_voice: None,
            tts_rate: None,
            include_details: false,
        })
        .unwrap();
        let summary = payload
            .get("queue_summary")
            .expect("queue_summary should be attached to preview responses");
        assert_eq!(summary["read_only"], true);
        assert!(summary.get("pending_count").is_some());
        assert!(summary.get("state_counts").is_some());
        assert!(summary.get("newest_pending").is_some());
    }

    #[test]
    fn xiao_shu_action_queue_uses_latest_append_only_state() {
        let root = std::env::temp_dir().join(format!(
            "agent-bridge-xiao-shu-action-current-{}",
            now_secs()
        ));
        std::fs::create_dir_all(&root).unwrap();

        let request_payload = json!({
            "surface": "xiao_shu_action_request",
            "read_only": true,
            "dry_run": true,
            "llm_safe": true,
            "action_request": {
                "actor": "codex",
                "intent": "voice_alert",
                "message": "please look",
                "reason": "unit-test",
                "mapped_track": "xiao_shu::alert_peek::medium",
                "request_state": "requires_human_confirmation",
                "requires_human_confirmation": true,
                "human_confirmation_present": false,
                "direct_llm_emit_allowed": false
            }
        });
        let queue_path = root.join("requests.jsonl");
        let pending = xiao_shu_action_enqueue_record_from_request(
            request_payload,
            "agent-bridge",
            &queue_path,
            1_779_470_000,
        );
        let mut emitted = pending.clone();
        emitted["updated_at"] = json!(1_779_470_100);
        emitted["prior_state"] = json!("pending_human_confirmation");
        emitted["state"] = json!("emitted");
        emitted["source"] = json!("xiao_shu_action_request_action");
        emitted["actual_emit_invoked"] = json!(true);
        emitted["emitted"] = json!(true);
        append_jsonl(&queue_path, &pending).unwrap();
        append_jsonl(&queue_path, &emitted).unwrap();

        let pending_view = xiao_shu_action_request_queue_from_path(
            &XiaoShuActionRequestQueueOptions {
                project: Some("agent-bridge"),
                request_id: None,
                state: None,
                include_all_states: false,
                include_details: false,
                limit: 10,
            },
            "agent-bridge",
            &queue_path,
        )
        .unwrap();
        assert_eq!(pending_view["queue"]["parsed_records"], 2);
        assert_eq!(pending_view["queue"]["current_records"], 1);
        assert_eq!(pending_view["queue"]["matching_records"], 0);
        assert_eq!(pending_view["queue"]["state_counts"]["emitted"], 1);

        let current = xiao_shu_action_request_queue_from_path(
            &XiaoShuActionRequestQueueOptions {
                project: Some("agent-bridge"),
                request_id: pending["request_id"].as_str(),
                state: None,
                include_all_states: true,
                include_details: true,
                limit: 10,
            },
            "agent-bridge",
            &queue_path,
        )
        .unwrap();
        assert_eq!(current["queue"]["matching_records"], 1);
        assert_eq!(current["records"][0]["state"], "emitted");
        assert_eq!(current["records"][0]["request_id"], pending["request_id"]);

        let _ = std::fs::remove_dir_all(root);
    }

    fn sample_voice_preview(voice_allowed: bool) -> Value {
        json!({
            "surface": "avatar_cortex_voice_preview",
            "schema": 1,
            "read_only": true,
            "emits_audio": false,
            "emits_notification": false,
            "mutates_global_substrate": false,
            "project": "agent-bridge",
            "label": "com.agentbridge.avatar-cortex.agent-bridge",
            "heartbeat_label": "com.agentbridge.avatar-heartbeat.agent-bridge",
            "learning_state": {
                "state": "caught_up",
                "reason": "step_matches_records"
            },
            "behavior_policy": {
                "badge": "caught up",
                "recommended_action": "none",
                "voice": {
                    "allowed": voice_allowed,
                    "preview": "小舒已追上最新事件。",
                    "reason": "sparse_voice_policy"
                },
                "notification": {
                    "allowed": false,
                    "reason": "read_only_panel_policy"
                }
            },
            "preview": {
                "text": "小舒已追上最新事件。",
                "voice_allowed": voice_allowed,
                "voice_reason": "sparse_voice_policy",
                "notification_allowed": false,
                "notification_reason": "read_only_panel_policy",
                "requires_explicit_emit_gate": true
            }
        })
    }

    #[test]
    fn avatar_cortex_voice_gate_dry_run_blocks_without_enabled_gate() {
        let gate = avatar_cortex_voice_gate_from_preview(
            sample_voice_preview(false),
            false,
            false,
            300,
            Some("manual dogfood"),
        );
        assert_eq!(gate["surface"], "avatar_cortex_voice_gate_dry_run");
        assert_eq!(gate["dry_run"], true);
        assert_eq!(gate["would_emit"], false);
        assert_eq!(gate["emits_audio"], false);
        assert_eq!(gate["emits_notification"], false);
        assert_eq!(gate["required"]["explicit_enabled"], false);
        assert!(gate["gate"]["blocked_reasons"]
            .as_array()
            .unwrap()
            .contains(&json!("gate_disabled")));
    }

    #[test]
    fn avatar_cortex_voice_gate_dry_run_requires_operator_reason() {
        let gate = avatar_cortex_voice_gate_from_preview(
            sample_voice_preview(false),
            true,
            false,
            300,
            None,
        );
        assert_eq!(gate["would_emit"], false);
        assert_eq!(gate["required"]["operator_reason_present"], false);
        assert!(gate["gate"]["blocked_reasons"]
            .as_array()
            .unwrap()
            .contains(&json!("missing_reason")));
    }

    #[test]
    fn avatar_cortex_voice_gate_dry_run_obeys_voice_policy() {
        let gate = avatar_cortex_voice_gate_from_preview(
            sample_voice_preview(false),
            true,
            false,
            300,
            Some("manual dogfood"),
        );
        assert_eq!(gate["would_emit"], false);
        assert_eq!(gate["required"]["voice_policy_allowed"], false);
        assert!(gate["gate"]["blocked_reasons"]
            .as_array()
            .unwrap()
            .contains(&json!("policy_voice_disabled")));
    }

    #[test]
    fn avatar_cortex_voice_gate_dry_run_can_reach_would_emit_without_audio() {
        let gate = avatar_cortex_voice_gate_from_preview(
            sample_voice_preview(true),
            true,
            false,
            300,
            Some("manual dogfood"),
        );
        assert_eq!(gate["would_emit"], true);
        assert_eq!(gate["dry_run"], true);
        assert_eq!(gate["emits_audio"], false);
        assert_eq!(gate["emits_notification"], false);
        assert!(gate["gate"]["blocked_reasons"]
            .as_array()
            .unwrap()
            .is_empty());
    }

    #[test]
    fn avatar_cortex_voice_preview_override_keeps_audio_gated() {
        let preview = avatar_cortex_voice_preview_with_override(
            sample_voice_preview(false),
            Some("小舒发现一点需要你看一下。"),
            "voice_emit_cli",
        );
        let gate = avatar_cortex_voice_gate_payload(
            preview,
            true,
            false,
            300,
            Some("manual dogfood"),
            true,
            None,
            false,
            1_000,
        );
        assert_eq!(gate["preview"]["text"], "小舒发现一点需要你看一下。");
        assert_eq!(gate["preview"]["source"], "operator_preview_text_override");
        assert_eq!(gate["preview_text_override"]["provided"], true);
        assert_eq!(gate["preview_text_override"]["source"], "voice_emit_cli");
        assert_eq!(gate["preview_text_override"]["emits_audio"], false);
        assert_eq!(gate["gate"]["allow_policy_override"], true);
        assert_eq!(gate["would_emit"], true);
    }

    #[test]
    fn avatar_cortex_voice_gate_emit_decision_requires_policy_or_override() {
        let gate = avatar_cortex_voice_gate_payload(
            sample_voice_preview(false),
            true,
            false,
            300,
            Some("manual dogfood"),
            true,
            None,
            false,
            1_000,
        );
        assert_eq!(gate["surface"], "avatar_cortex_voice_gate");
        assert_eq!(gate["dry_run"], false);
        assert_eq!(gate["would_emit"], true);
        assert_eq!(gate["gate"]["allow_policy_override"], true);
        assert_eq!(gate["required"]["voice_policy_allowed"], false);
        assert_eq!(gate["required"]["policy_override_allowed"], true);
        assert!(gate["gate"]["blocked_reasons"]
            .as_array()
            .unwrap()
            .is_empty());
    }

    #[test]
    fn avatar_cortex_voice_gate_emit_decision_respects_cooldown() {
        let gate = avatar_cortex_voice_gate_payload(
            sample_voice_preview(true),
            true,
            false,
            300,
            Some("manual dogfood"),
            false,
            Some(1_000),
            false,
            1_100,
        );
        assert_eq!(gate["would_emit"], false);
        assert_eq!(gate["cooldown"]["active"], true);
        assert!(gate["gate"]["blocked_reasons"]
            .as_array()
            .unwrap()
            .contains(&json!("cooldown_active")));

        let forced = avatar_cortex_voice_gate_payload(
            sample_voice_preview(true),
            true,
            true,
            300,
            Some("manual dogfood"),
            false,
            Some(1_000),
            false,
            1_100,
        );
        assert_eq!(forced["would_emit"], true);
        assert_eq!(forced["cooldown"]["active"], true);
        assert_eq!(forced["required"]["cooldown_clear"], true);
    }
}
