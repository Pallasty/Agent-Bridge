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
    pub enabled: bool,
    pub force: bool,
    pub cooldown_secs: i64,
    pub reason: Option<&'a str>,
    pub allow_policy_override: bool,
    pub tts_voice: Option<&'a str>,
    pub tts_rate: Option<u64>,
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

fn avatar_cortex_voice_paths(project: &str, heartbeat_label: &str) -> Result<(PathBuf, PathBuf)> {
    let dir = avatar_cortex_voice_dir()?.join(label_component(project));
    let slug = label_component(heartbeat_label);
    Ok((
        dir.join(format!("{slug}.voice.json")),
        dir.join(format!("{slug}.events.jsonl")),
    ))
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
                "source": "desktop_visual_review_2026_05_21_alert_peek",
                "outcome": "request_visual_revision",
                "notes": [
                    "too_bright",
                    "aesthetic_needs_improvement",
                    "voice_linkage_desired",
                    "slightly_thicker_shape_ok"
                ]
            },
            "revision_response": [
                "replace the white CSS stand-in with the read-only xiao-shu-dev sprite source",
                "mute the attention mark brightness",
                "soften alert_peek motion timing",
                "add slight outline and body weight only in alert state",
                "reduce alert-state body brightness without changing other tracks",
                "keep voice linkage as future sparse voice design, not immediate emit"
            ],
            "voice_linkage": {
                "requested": true,
                "policy": "future_sparse_voice_after_visual_re_review",
                "emits_audio_now": false
            },
            "recommended_next_step": "re-review revised alert_peek before any voice or binding approval design"
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
        "xiao_shu::alert_peek::medium" => vec![
            json!({
                "variant_id": "current_alert_row",
                "label": "current alert row",
                "sprite_row": 5,
                "sprite_frames": 8,
                "alert_mark": true,
                "default": true,
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
        "semantic_variant_review": if has_semantic_variants {
            json!({
                "schema": 1,
                "surface": "alert_peek_semantic_variant_review",
                "read_only": true,
                "default_variant": "current_alert_row",
                "writes_approval": false,
                "persists_record": false,
                "can_promote_binding": false,
                "emits_audio": false,
                "next_step": "compare alert_peek posture variants before choosing any binding or sparse voice cue",
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

fn avatar_cortex_renderer_review_report_item(packet: &Value) -> Value {
    let token = vstr(packet.get("token")).unwrap_or("xiao_shu::unknown");
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

    json!({
        "token": token,
        "readiness": if ready_for_human_review {
            "ready_for_human_visual_review"
        } else {
            "blocked"
        },
        "default_decision": packet
            .get("default_decision")
            .cloned()
            .unwrap_or(json!("keep_pending")),
        "approval_state": packet
            .get("approval_state")
            .cloned()
            .unwrap_or(json!("not_approved")),
        "can_promote_binding": false,
        "ready_for_human_review": ready_for_human_review,
        "ready_for_approval": false,
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
        },
        "missing": {
            "preview_route": !has_preview_route,
            "visual_questions": !has_questions,
            "acceptance_criteria": !has_acceptance,
            "operator_checks": !has_operator_checks,
            "source_blockers": has_blockers,
        },
        "next_step": "open focused renderer preview and record a human observation outside this read-only report",
    })
}

fn avatar_cortex_renderer_review_report_from_packet_payload(review_packet_payload: Value) -> Value {
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
        .map(avatar_cortex_renderer_review_report_item)
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
    let blocked_count = packet_count.saturating_sub(ready_count);
    let ready_for_human_review = packet_count > 0 && blocked_count == 0;
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
        "ready_for_approval": false,
        "approval_writes_allowed": false,
        "records_persisted": false,
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
        "human_decision_count": 0,
        "report_state": report_state,
        "items": items,
        "checklist": checklist,
        "acceptance": acceptance,
        "decision": "implementation is ready for human visual review, but no pending track is approved or promotable",
        "next_step": "perform the human visual pass for sorting_glow, look_sideways, and alert_peek before designing any approval record",
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

pub(crate) fn avatar_cortex_renderer_review_report_from_status(status: Value) -> Value {
    let review_packet = avatar_cortex_renderer_review_packet_from_status(status);
    avatar_cortex_renderer_review_report_from_packet_payload(review_packet)
}

pub fn avatar_cortex_renderer_review_report(
    label: Option<&str>,
    heartbeat_label: Option<&str>,
    project: Option<&str>,
    output: Option<&Path>,
) -> Result<Value> {
    let status = avatar_cortex_status(label, heartbeat_label, project, output)?;
    Ok(avatar_cortex_renderer_review_report_from_status(status))
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
    let launchd = crate::avatar_health::probe_launchd(&label)?;
    let snapshot = avatar_cortex_snapshot_payload(&snapshot_path);
    let events = avatar_cortex_events_summary(&heartbeat_label, project);
    let trend = avatar_cortex_trend(&snapshot, &events);
    Ok(json!({
        "surface": "avatar_cortex_status",
        "schema": 1,
        "project": project,
        "label": label,
        "heartbeat_label": heartbeat_label,
        "launchd": {
            "loaded": launchd.loaded,
            "domain": launchd.domain,
            "target": launchd.target,
            "state": launchd.state,
            "runs": launchd.runs,
            "last_exit_code": launchd.last_exit_code,
            "run_interval_secs": launchd.run_interval_secs,
            "error": launchd.error,
        },
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
        "learning_state": preview.get("learning_state").cloned().unwrap_or(Value::Null),
        "behavior_policy": preview.get("behavior_policy").cloned().unwrap_or(Value::Null),
        "source_preview": preview,
    })
}

pub fn avatar_cortex_voice_gate_dry_run(opts: &AvatarCortexVoiceGateOptions<'_>) -> Result<Value> {
    let preview =
        avatar_cortex_voice_preview(opts.label, opts.heartbeat_label, opts.project, opts.output)?;
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
    let preview =
        avatar_cortex_voice_preview(opts.label, opts.heartbeat_label, opts.project, opts.output)?;
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
        let sorting_glow = tracks
            .iter()
            .find(|track| track["token"] == "xiao_shu::sorting_glow::medium")
            .unwrap();
        assert_eq!(sorting_glow["track_kind"], "review_only");
        assert_eq!(sorting_glow["binding_stage"], "needs_review");
        assert_eq!(sorting_glow["review_only"], true);
        assert_eq!(sorting_glow["duration_ms"], 1440);
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
        let alert_peek = tracks
            .iter()
            .find(|track| track["token"] == "xiao_shu::alert_peek::medium")
            .unwrap();
        assert_eq!(alert_peek["semantic_variant_count"], 3);
        assert_eq!(alert_peek["has_semantic_variants"], true);
        assert_eq!(
            alert_peek["semantic_variants"][0]["variant_id"],
            "current_alert_row"
        );
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
        assert_eq!(alert_peek["semantic_variants"][2]["sprite_row"], 8);
        assert_eq!(
            alert_peek["semantic_variant_review"]["can_promote_binding"],
            false
        );
        assert_eq!(alert_peek["semantic_variant_review"]["emits_audio"], false);
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
            "request_visual_revision"
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
            "request_visual_revision"
        );
        assert_eq!(alert["voice_linkage"]["emits_audio_now"], false);
        assert_eq!(alert["evidence_counts"]["revision_response"], 6);
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
