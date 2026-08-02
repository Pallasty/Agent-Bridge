//! Sparse alert gate for avatar heartbeat health.
//!
//! The heartbeat job stays a quiet liveness writer. This module watches the
//! read-only health projection, emits only on meaningful transitions, and
//! appends structured JSONL events that a future Seed substrate can consume.

use ab_store::StateStore;
use anyhow::{Context, Result};
use serde_json::{json, Value};
use std::fs::OpenOptions;
use std::io::Write;
use std::path::PathBuf;

pub struct HeartbeatAlertOptions<'a> {
    pub label: Option<&'a str>,
    pub project: Option<&'a str>,
    pub stale_secs: i64,
    pub force: bool,
    pub preview: bool,
    pub notification: bool,
    pub tts: bool,
    pub repeat_secs: i64,
    pub tts_voice: Option<&'a str>,
    pub tts_rate: Option<u64>,
}

fn home_dir() -> Result<PathBuf> {
    std::env::var_os("HOME")
        .map(PathBuf::from)
        .ok_or_else(|| anyhow::anyhow!("HOME is not set"))
}

fn alert_dir() -> Result<PathBuf> {
    Ok(home_dir()?
        .join("Library")
        .join("Application Support")
        .join("agent-bridge")
        .join("avatar_health"))
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

fn alert_paths(label: &str) -> Result<(PathBuf, PathBuf)> {
    let dir = alert_dir()?;
    let slug = label_component(label);
    Ok((
        dir.join(format!("{slug}.alert.json")),
        dir.join(format!("{slug}.events.jsonl")),
    ))
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

fn alert_event_key(health: &Value) -> String {
    let status = vstr(health.get("status")).unwrap_or("unknown");
    if status == "healthy" {
        return "healthy".to_string();
    }
    let launchd = health.get("launchd").unwrap_or(&Value::Null);
    let binary = health.get("binary").unwrap_or(&Value::Null);
    let presence = health.get("presence").unwrap_or(&Value::Null);
    format!(
        "status={status};exit={};binary_missing_command={};presence_fresh={}",
        vi64(launchd.get("last_exit_code"))
            .map(|v| v.to_string())
            .unwrap_or_else(|| "-".to_string()),
        vbool(binary.get("missing_command")).unwrap_or(false),
        vbool(presence.get("fresh")).unwrap_or(false)
    )
}

fn alert_message(health: &Value) -> String {
    vstr(health.get("summary"))
        .unwrap_or("avatar heartbeat health changed")
        .to_string()
}

pub fn alert_should_emit(
    previous_key: Option<&str>,
    last_emitted_at: Option<i64>,
    now: i64,
    event_key: &str,
    healthy: bool,
    force: bool,
    repeat_secs: i64,
) -> (bool, &'static str) {
    if force {
        return (true, "force");
    }
    match previous_key {
        None if healthy => (false, "first_healthy"),
        None => (true, "first_unhealthy"),
        Some(prev) if prev != event_key => (true, "transition"),
        Some(_) if !healthy && repeat_secs > 0 => {
            let last = last_emitted_at.unwrap_or(0);
            if now.saturating_sub(last) >= repeat_secs {
                (true, "repeat_due")
            } else {
                (false, "cooldown")
            }
        }
        Some(_) => (false, "unchanged"),
    }
}

fn read_state(path: &PathBuf) -> Value {
    std::fs::read_to_string(path)
        .ok()
        .and_then(|s| serde_json::from_str(&s).ok())
        .unwrap_or(Value::Null)
}

fn write_json(path: &PathBuf, value: &Value) -> Result<()> {
    if let Some(parent) = path.parent() {
        std::fs::create_dir_all(parent).with_context(|| format!("create {}", parent.display()))?;
    }
    std::fs::write(path, serde_json::to_vec_pretty(value)?)
        .with_context(|| format!("write {}", path.display()))
}

fn append_jsonl(path: &PathBuf, value: &Value) -> Result<()> {
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

fn quote_applescript(value: &str) -> String {
    value.replace('\\', "\\\\").replace('"', "\\\"")
}

fn emit_notification(title: &str, subtitle: &str, body: &str) -> Value {
    if !cfg!(target_os = "macos") {
        return json!({"attempted": false, "ok": false, "error": "macOS notification only"});
    }
    let script = format!(
        "display notification \"{}\" with title \"{}\" subtitle \"{}\"",
        quote_applescript(body),
        quote_applescript(title),
        quote_applescript(subtitle)
    );
    match std::process::Command::new("osascript")
        .args(["-e", &script])
        .status()
    {
        Ok(status) => {
            json!({"attempted": true, "ok": status.success(), "status": status.to_string()})
        }
        Err(err) => json!({"attempted": true, "ok": false, "error": err.to_string()}),
    }
}

pub(crate) fn emit_tts(line: &str, voice: Option<&str>, rate: Option<u64>) -> Value {
    if !cfg!(target_os = "macos") {
        return json!({"attempted": false, "ok": false, "error": "macOS say only"});
    }
    let mut cmd = std::process::Command::new("say");
    if let Some(voice) = voice.filter(|v| !v.trim().is_empty()) {
        cmd.args(["-v", voice]);
    }
    if let Some(rate) = rate {
        cmd.args(["-r", &rate.clamp(80, 300).to_string()]);
    }
    cmd.arg(line);
    match cmd.status() {
        Ok(status) => {
            json!({"attempted": true, "ok": status.success(), "status": status.to_string(), "voice": voice, "rate": rate})
        }
        Err(err) => {
            json!({"attempted": true, "ok": false, "error": err.to_string(), "voice": voice, "rate": rate})
        }
    }
}

pub async fn heartbeat_alert(
    store: &dyn StateStore,
    opts: &HeartbeatAlertOptions<'_>,
) -> Result<Value> {
    let health =
        crate::avatar_health::heartbeat_health(store, opts.label, opts.project, opts.stale_secs)
            .await?;
    let label = vstr(health.get("label")).unwrap_or("avatar-heartbeat");
    let now = vi64(health.get("generated_at")).unwrap_or(0);
    let healthy = vbool(health.get("healthy")).unwrap_or(false);
    let event_key = alert_event_key(&health);
    let message = alert_message(&health);
    let (state_path, events_path) = alert_paths(label)?;
    let previous = read_state(&state_path);
    let previous_key = vstr(previous.get("last_event_key"));
    let last_emitted_at = vi64(previous.get("last_emitted_at"));
    let (should_emit, reason) = alert_should_emit(
        previous_key,
        last_emitted_at,
        now,
        &event_key,
        healthy,
        opts.force,
        opts.repeat_secs,
    );
    let emit_now = should_emit && !opts.preview;
    let mut notification = Value::Null;
    let mut tts = Value::Null;
    if emit_now && opts.notification {
        notification = emit_notification("Xiao Shu heartbeat", &event_key, &message);
    }
    if emit_now && opts.tts {
        tts = emit_tts(&message, opts.tts_voice, opts.tts_rate);
    }

    let event = json!({
        "surface": "avatar_heartbeat_alert",
        "schema": 1,
        "generated_at": now,
        "label": label,
        "project": health.get("project").cloned().unwrap_or(Value::Null),
        "status": health.get("status").cloned().unwrap_or(Value::Null),
        "healthy": healthy,
        "event_key": event_key,
        "previous_event_key": previous_key,
        "should_emit": should_emit,
        "emitted": emit_now,
        "reason": reason,
        "preview": opts.preview,
        "notification": notification,
        "tts": tts,
        "health": health,
        "seed_ready": {
            "event_log_path": events_path.to_string_lossy(),
            "substrate_input": "avatar_health_transition_v1"
        }
    });

    if !opts.preview {
        append_jsonl(&events_path, &event)?;
    }
    let next_state = json!({
        "label": label,
        "updated_at": now,
        "last_event_key": event_key,
        "last_status": event["status"].clone(),
        "last_healthy": healthy,
        "last_emitted_at": if emit_now { now } else { last_emitted_at.unwrap_or(0) },
        "last_reason": reason,
        "events_path": events_path.to_string_lossy(),
    });
    if !opts.preview {
        write_json(&state_path, &next_state)?;
    }

    Ok(json!({
        "surface": "avatar_heartbeat_alert",
        "read_only_health": true,
        "state_path": state_path.to_string_lossy(),
        "events_path": events_path.to_string_lossy(),
        "event": event,
        "state": next_state,
    }))
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn alert_should_emit_on_first_unhealthy_and_transition_only() {
        assert_eq!(
            alert_should_emit(None, None, 100, "healthy", true, false, 3600),
            (false, "first_healthy")
        );
        assert_eq!(
            alert_should_emit(None, None, 100, "status=failing", false, false, 3600),
            (true, "first_unhealthy")
        );
        assert_eq!(
            alert_should_emit(
                Some("healthy"),
                Some(10),
                100,
                "status=failing",
                false,
                false,
                3600,
            ),
            (true, "transition")
        );
        assert_eq!(
            alert_should_emit(
                Some("status=failing"),
                Some(50),
                100,
                "status=failing",
                false,
                false,
                3600,
            ),
            (false, "cooldown")
        );
        assert_eq!(
            alert_should_emit(
                Some("status=failing"),
                Some(50),
                3700,
                "status=failing",
                false,
                false,
                3600,
            ),
            (true, "repeat_due")
        );
    }
}
