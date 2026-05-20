//! Seed-ready projection for avatar heartbeat alert events.
//!
//! This module does not call or mutate the Seed substrate. It turns the
//! append-only avatar alert JSONL into the `{text, key, ts, kind}` records
//! already accepted by `agent-bridge substrate replay`.

use anyhow::{Context, Result};
use serde_json::{json, Value};
use std::path::{Path, PathBuf};

pub struct AvatarSeedEventsOptions<'a> {
    pub label: Option<&'a str>,
    pub project: Option<&'a str>,
    pub input: Option<&'a Path>,
    pub limit: usize,
    pub include_preview: bool,
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

fn default_heartbeat_label(project: &str) -> String {
    format!(
        "com.agentbridge.avatar-heartbeat.{}",
        label_component(project)
    )
}

pub fn avatar_alert_events_path(label: &str) -> Result<PathBuf> {
    Ok(home_dir()?
        .join("Library")
        .join("Application Support")
        .join("agent-bridge")
        .join("avatar_health")
        .join(format!("{}.events.jsonl", label_component(label))))
}

fn vi64(value: Option<&Value>) -> Option<i64> {
    value.and_then(|v| v.as_i64().or_else(|| v.as_u64().map(|n| n as i64)))
}

fn vbool(value: Option<&Value>) -> Option<bool> {
    value.and_then(Value::as_bool)
}

fn vstr(value: Option<&Value>) -> Option<&str> {
    value.and_then(Value::as_str)
}

fn compact_bool(value: Option<bool>) -> &'static str {
    match value {
        Some(true) => "true",
        Some(false) => "false",
        None => "unknown",
    }
}

fn compact_i64(value: Option<i64>) -> String {
    value
        .map(|n| n.to_string())
        .unwrap_or_else(|| "unknown".to_string())
}

fn avatar_seed_text(event: &Value) -> String {
    let health = event.get("health").unwrap_or(&Value::Null);
    let launchd = health.get("launchd").unwrap_or(&Value::Null);
    let presence = health.get("presence").unwrap_or(&Value::Null);
    let summary = vstr(health.get("summary")).unwrap_or("avatar heartbeat health event");
    format!(
        concat!(
            "avatar heartbeat event ",
            "project={} label={} status={} healthy={} reason={} event_key={} ",
            "should_emit={} emitted={} preview={} launchd_exit={} presence_fresh={} ",
            "presence_age_secs={} summary={}"
        ),
        vstr(event.get("project")).unwrap_or("unknown"),
        vstr(event.get("label")).unwrap_or("unknown"),
        vstr(event.get("status")).unwrap_or("unknown"),
        compact_bool(vbool(event.get("healthy"))),
        vstr(event.get("reason")).unwrap_or("unknown"),
        vstr(event.get("event_key")).unwrap_or("unknown"),
        compact_bool(vbool(event.get("should_emit"))),
        compact_bool(vbool(event.get("emitted"))),
        compact_bool(vbool(event.get("preview"))),
        compact_i64(vi64(launchd.get("last_exit_code"))),
        compact_bool(vbool(presence.get("fresh"))),
        compact_i64(vi64(presence.get("age_secs"))),
        summary
    )
}

pub fn avatar_event_to_seed_record(event: &Value, source_path: &Path) -> Option<Value> {
    if vstr(event.get("surface")) != Some("avatar_heartbeat_alert") {
        return None;
    }
    let ts = vi64(event.get("generated_at")).unwrap_or(0);
    let label = vstr(event.get("label")).unwrap_or("avatar-heartbeat");
    let project = vstr(event.get("project")).unwrap_or("agent-bridge");
    let event_key = vstr(event.get("event_key")).unwrap_or("unknown");
    let reason = vstr(event.get("reason")).unwrap_or("unknown");
    let kind = event
        .get("seed_ready")
        .and_then(|v| v.get("substrate_input"))
        .and_then(Value::as_str)
        .unwrap_or("avatar_health_transition_v1");
    let key = format!("avatar:{project}:{label}:{ts}:{event_key}:{reason}");
    Some(json!({
        "text": avatar_seed_text(event),
        "key": key,
        "ts": ts,
        "kind": kind,
        "source": "avatar_heartbeat_alert",
        "source_path": source_path.to_string_lossy(),
        "avatar": {
            "project": project,
            "label": label,
            "status": event.get("status").cloned().unwrap_or(Value::Null),
            "healthy": event.get("healthy").cloned().unwrap_or(Value::Null),
            "event_key": event_key,
            "reason": reason,
            "should_emit": event.get("should_emit").cloned().unwrap_or(Value::Null),
            "emitted": event.get("emitted").cloned().unwrap_or(Value::Null),
            "preview": event.get("preview").cloned().unwrap_or(Value::Null),
        },
        "seed_ready": {
            "substrate_input": kind,
            "target": "agent-bridge substrate replay"
        }
    }))
}

pub fn avatar_seed_events(opts: &AvatarSeedEventsOptions<'_>) -> Result<Value> {
    let project = opts.project.unwrap_or("agent-bridge");
    let label = opts
        .label
        .filter(|s| !s.trim().is_empty())
        .map(str::to_string)
        .unwrap_or_else(|| default_heartbeat_label(project));
    let events_path = match opts.input {
        Some(path) => path.to_path_buf(),
        None => avatar_alert_events_path(&label)?,
    };
    let raw = std::fs::read_to_string(&events_path)
        .with_context(|| format!("read avatar alert events {}", events_path.display()))?;
    let mut events_seen = 0usize;
    let mut parse_skips = 0usize;
    let mut surface_skips = 0usize;
    let mut preview_skips = 0usize;
    let mut records: Vec<Value> = Vec::new();
    for line in raw.lines() {
        let trimmed = line.trim();
        if trimmed.is_empty() {
            continue;
        }
        events_seen += 1;
        let event: Value = match serde_json::from_str(trimmed) {
            Ok(event) => event,
            Err(_) => {
                parse_skips += 1;
                continue;
            }
        };
        if vstr(event.get("surface")) != Some("avatar_heartbeat_alert") {
            surface_skips += 1;
            continue;
        }
        if !opts.include_preview && vbool(event.get("preview")).unwrap_or(false) {
            preview_skips += 1;
            continue;
        }
        match avatar_event_to_seed_record(&event, &events_path) {
            Some(record) => records.push(record),
            None => surface_skips += 1,
        }
    }
    if opts.limit > 0 && records.len() > opts.limit {
        let keep_from = records.len() - opts.limit;
        records.drain(0..keep_from);
    }
    Ok(json!({
        "surface": "avatar_seed_events",
        "schema": 1,
        "read_only": true,
        "project": project,
        "label": label,
        "events_path": events_path.to_string_lossy(),
        "include_preview": opts.include_preview,
        "limit": opts.limit,
        "events_seen": events_seen,
        "records_count": records.len(),
        "parse_skips": parse_skips,
        "surface_skips": surface_skips,
        "preview_skips": preview_skips,
        "substrate_input": "avatar_health_transition_v1",
        "target": "agent-bridge substrate replay --log <jsonl>",
        "records": records,
    }))
}

#[cfg(test)]
mod tests {
    use super::*;

    fn sample_event(preview: bool, status: &str, ts: i64) -> Value {
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
            "preview": preview,
            "health": {
                "summary": format!("{status}: sample"),
                "launchd": {"last_exit_code": 0},
                "presence": {"fresh": true, "age_secs": 12}
            },
            "seed_ready": {"substrate_input": "avatar_health_transition_v1"}
        })
    }

    #[test]
    fn avatar_event_to_seed_record_maps_replay_fields() {
        let source = Path::new("/tmp/avatar.events.jsonl");
        let record = avatar_event_to_seed_record(&sample_event(false, "healthy", 123), source)
            .expect("record");
        assert_eq!(record["kind"], "avatar_health_transition_v1");
        assert_eq!(record["ts"], 123);
        assert_eq!(record["avatar"]["status"], "healthy");
        assert!(record["key"]
            .as_str()
            .expect("key")
            .contains("avatar:agent-bridge:com.agentbridge.avatar-heartbeat.agent-bridge:123"));
        assert!(record["text"]
            .as_str()
            .expect("text")
            .contains("status=healthy"));
    }

    #[test]
    fn avatar_seed_events_filters_preview_by_default_and_keeps_last_limit() {
        let dir = tempfile::tempdir().expect("tempdir");
        let path = dir.path().join("events.jsonl");
        let body = [
            serde_json::to_string(&sample_event(true, "healthy", 1)).unwrap(),
            serde_json::to_string(&sample_event(false, "failing", 2)).unwrap(),
            serde_json::to_string(&sample_event(false, "healthy", 3)).unwrap(),
        ]
        .join("\n");
        std::fs::write(&path, body).expect("write events");
        let opts = AvatarSeedEventsOptions {
            label: None,
            project: Some("agent-bridge"),
            input: Some(&path),
            limit: 1,
            include_preview: false,
        };
        let payload = avatar_seed_events(&opts).expect("payload");
        assert_eq!(payload["events_seen"], 3);
        assert_eq!(payload["preview_skips"], 1);
        assert_eq!(payload["records_count"], 1);
        assert_eq!(payload["records"][0]["ts"], 3);
    }
}
