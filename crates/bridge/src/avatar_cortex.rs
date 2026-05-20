//! Shadow-only Seed cortex for Xiao Shu avatar events.
//!
//! This is deliberately separate from the global memory substrate. It consumes
//! avatar alert perception records, trains an isolated `SeedBackend`, and writes
//! a dedicated snapshot file for inspection.

use anyhow::{Context, Result};
use serde_json::{Value, json};
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
        assert!(
            gate["gate"]["blocked_reasons"]
                .as_array()
                .unwrap()
                .contains(&json!("gate_disabled"))
        );
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
        assert!(
            gate["gate"]["blocked_reasons"]
                .as_array()
                .unwrap()
                .contains(&json!("missing_reason"))
        );
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
        assert!(
            gate["gate"]["blocked_reasons"]
                .as_array()
                .unwrap()
                .contains(&json!("policy_voice_disabled"))
        );
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
        assert!(
            gate["gate"]["blocked_reasons"]
                .as_array()
                .unwrap()
                .is_empty()
        );
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
        assert!(
            gate["gate"]["blocked_reasons"]
                .as_array()
                .unwrap()
                .is_empty()
        );
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
        assert!(
            gate["gate"]["blocked_reasons"]
                .as_array()
                .unwrap()
                .contains(&json!("cooldown_active"))
        );

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
