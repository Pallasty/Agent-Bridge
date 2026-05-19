use ab_store::AgentPresenceRecord;
use serde_json::{json, Value};

pub const AGENT_AVATAR_PROTOCOL_VERSION: u8 = 1;

#[derive(Debug, Clone, Copy)]
pub struct ReportContext<'a> {
    pub project: Option<&'a str>,
    pub role: Option<&'a str>,
    pub max_idle_secs: i64,
    pub source: &'a str,
}

fn field(primary: Option<&Value>, compat: Option<&Value>, key: &str) -> Value {
    primary
        .and_then(|v| v.get(key).cloned())
        .or_else(|| compat.and_then(|v| v.get(key).cloned()))
        .unwrap_or(Value::Null)
}

fn field_or_string(
    primary: Option<&Value>,
    compat: Option<&Value>,
    key: &str,
    fallback: String,
) -> Value {
    let value = field(primary, compat, key);
    if value.is_null() {
        json!(fallback)
    } else {
        value
    }
}

fn str_field(value: &Value, key: &str) -> Option<String> {
    value
        .get(key)
        .and_then(|v| v.as_str())
        .filter(|s| !s.is_empty())
        .map(ToString::to_string)
}

pub fn entry_from_presence(
    row: &AgentPresenceRecord,
    include_raw_presence: bool,
    include_compat: bool,
) -> Value {
    let capabilities = row.capabilities.as_ref();
    let avatar_state = capabilities
        .and_then(|v| v.get("avatar_state"))
        .filter(|v| v.is_object());
    let pet_state = capabilities
        .and_then(|v| v.get("pet_state"))
        .filter(|v| v.is_object());
    let source = if avatar_state.is_some() {
        "avatar_state"
    } else if pet_state.is_some() {
        "pet_state"
    } else {
        "presence"
    };
    let state = avatar_state.or(pet_state).unwrap_or(&Value::Null);
    let mode = str_field(state, "mode").unwrap_or_else(|| "unknown".to_string());
    let activity_state = str_field(state, "activity_state").unwrap_or_else(|| mode.clone());

    let mut entry = json!({
        "agent_avatar_protocol": AGENT_AVATAR_PROTOCOL_VERSION,
        "agent_id": field_or_string(avatar_state, pet_state, "agent_id", row.session_id.clone()),
        "session_id": row.session_id,
        "name": row.name,
        "runtime": field(avatar_state, pet_state, "runtime"),
        "avatar_id": field(avatar_state, pet_state, "avatar_id"),
        "mode": mode,
        "activity_state": activity_state,
        "focus": field(avatar_state, pet_state, "focus"),
        "risk_level": field(avatar_state, pet_state, "risk_level"),
        "blocked_reason": field(avatar_state, pet_state, "blocked_reason"),
        "evidence": field(avatar_state, pet_state, "evidence"),
        "next_action": field(avatar_state, pet_state, "next_action"),
        "updated_at": field(avatar_state, pet_state, "updated_at"),
        "project": field_or_string(avatar_state, pet_state, "project", row.project.clone()),
        "cwd": field_or_string(
            avatar_state,
            pet_state,
            "cwd",
            row.cwd.clone().unwrap_or_default()
        ),
        "node": row.node,
        "role": row.role,
        "tag": row.tag,
        "pid": row.pid,
        "last_heartbeat_at": row.last_heartbeat_at,
        "started_at": row.started_at,
        "voice_policy": avatar_state
            .and_then(|v| v.get("voice_policy").cloned())
            .or_else(|| capabilities.and_then(|v| v.get("voice_policy").cloned()))
            .unwrap_or(Value::Null),
        "source": source,
        "has_avatar_state": avatar_state.is_some(),
        "has_compat_pet_state": pet_state.is_some()
    });
    if include_compat {
        entry["compat_pet_state"] = pet_state.cloned().unwrap_or(Value::Null);
    }
    if include_raw_presence {
        entry["presence"] = json!(row);
    }
    entry
}

fn report_clean(value: &str) -> String {
    let collapsed = value.split_whitespace().collect::<Vec<_>>().join(" ");
    if collapsed.chars().count() <= 160 {
        return collapsed;
    }
    let mut clipped: String = collapsed.chars().take(157).collect();
    clipped.push_str("...");
    clipped
}

fn report_value(entry: &Value, key: &str) -> Option<String> {
    let value = entry.get(key)?;
    match value {
        Value::Null => None,
        Value::String(s) => {
            let cleaned = report_clean(s);
            if cleaned.is_empty() {
                None
            } else {
                Some(cleaned)
            }
        }
        Value::Number(_) | Value::Bool(_) => Some(value.to_string()),
        _ => Some(report_clean(&value.to_string())),
    }
}

fn report_value_or(entry: &Value, key: &str, fallback: &str) -> String {
    report_value(entry, key).unwrap_or_else(|| fallback.to_string())
}

pub fn report_from_entries(avatars: &[Value], ctx: &ReportContext<'_>) -> String {
    let mut lines = Vec::new();
    lines.push("Agent Avatar Surface".to_string());
    lines.push(format!(
        "count={} project={} role={} max_idle_secs={} source={}",
        avatars.len(),
        ctx.project.unwrap_or("*"),
        ctx.role.unwrap_or("*"),
        ctx.max_idle_secs,
        ctx.source
    ));

    if avatars.is_empty() {
        lines.push("No avatar presence rows matched the filters.".to_string());
        return lines.join("\n");
    }

    for (idx, avatar) in avatars.iter().enumerate() {
        let agent_id = report_value_or(avatar, "agent_id", "unknown-agent");
        let runtime = report_value_or(avatar, "runtime", "unknown-runtime");
        let avatar_id = report_value_or(avatar, "avatar_id", "unknown-avatar");
        let mode = report_value_or(avatar, "mode", "unknown");
        let activity = report_value_or(avatar, "activity_state", &mode);
        let focus = report_value_or(avatar, "focus", "-");
        let risk = report_value_or(avatar, "risk_level", "-");
        let heartbeat = report_value_or(avatar, "last_heartbeat_at", "-");
        let source = report_value_or(avatar, "source", "presence");
        let has_avatar_state = report_value_or(avatar, "has_avatar_state", "false");
        let has_compat_pet_state = report_value_or(avatar, "has_compat_pet_state", "false");

        lines.push(format!(
            "{}. {} runtime={} avatar={} mode={} activity={} focus={} risk={} heartbeat={}",
            idx + 1,
            agent_id,
            runtime,
            avatar_id,
            mode,
            activity,
            focus,
            risk,
            heartbeat
        ));
        if let Some(blocked_reason) = report_value(avatar, "blocked_reason") {
            lines.push(format!("   blocked: {blocked_reason}"));
        }
        if let Some(next_action) = report_value(avatar, "next_action") {
            lines.push(format!("   next: {next_action}"));
        }
        if let Some(evidence) = report_value(avatar, "evidence") {
            lines.push(format!("   evidence: {evidence}"));
        }
        lines.push(format!(
            "   flags: avatar_state={} compat_pet={} source={}",
            has_avatar_state, has_compat_pet_state, source
        ));
    }

    lines.join("\n")
}
