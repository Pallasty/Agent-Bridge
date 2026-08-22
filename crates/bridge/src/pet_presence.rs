//! Shared pet/avatar presence projection.
//!
//! This module is deliberately UI-agnostic: it reads the Codex-compatible
//! pet sidecar, projects it into Agent Avatar Protocol fields, and refreshes
//! an agent_presence row. MCP tools and CLI commands both call this path so
//! terminal adapters can heartbeat without expanding the Codex Essential tool
//! surface.

use ab_core::{Error, Result};
use ab_store::{AgentPresenceUpsert, StateStore};
use serde_json::{json, Value};
use std::path::Path;
use std::time::{SystemTime, UNIX_EPOCH};

const PRESENCE_FRESH_SECS: i64 = 60;

fn str_field(value: &Value, key: &str) -> Option<String> {
    value
        .get(key)
        .and_then(|v| v.as_str())
        .map(str::trim)
        .filter(|s| !s.is_empty())
        .map(ToString::to_string)
}

fn optional_string<'a>(args: &'a Value, key: &str) -> Option<&'a str> {
    args.get(key)
        .and_then(|v| v.as_str())
        .map(str::trim)
        .filter(|s| !s.is_empty())
}

fn string_or_default(args: &Value, key: &str, default: &str) -> String {
    optional_string(args, key)
        .map(str::to_string)
        .unwrap_or_else(|| default.to_string())
}

fn string_from_args_or_state_or_default(
    args: &Value,
    state: &Value,
    key: &str,
    default: &str,
) -> String {
    optional_string(args, key)
        .map(str::to_string)
        .or_else(|| str_field(state, key))
        .unwrap_or_else(|| default.to_string())
}

fn string_from_args_or_state_or_null(args: &Value, state: &Value, key: &str) -> Value {
    optional_string(args, key)
        .map(|s| json!(s))
        .or_else(|| str_field(state, key).map(|s| json!(s)))
        .unwrap_or(Value::Null)
}

fn string_arg_state_or_default(args: &Value, state: &Value, key: &str, default: &str) -> String {
    str_field(args, key)
        .or_else(|| str_field(state, key))
        .unwrap_or_else(|| default.to_string())
}

fn string_arg_state_or_null(args: &Value, state: &Value, key: &str) -> Value {
    str_field(args, key)
        .or_else(|| str_field(state, key))
        .map(|s| json!(s))
        .unwrap_or(Value::Null)
}

fn string_or_env(args: &Value, key: &str, env_key: &str) -> Option<String> {
    str_field(args, key).or_else(|| {
        std::env::var(env_key)
            .ok()
            .map(|v| v.trim().to_string())
            .filter(|v| !v.is_empty())
    })
}

fn tts_rate(args: &Value) -> Option<u64> {
    args.get("tts_rate")
        .and_then(|v| v.as_u64())
        .or_else(|| {
            std::env::var("AB_PET_TTS_RATE")
                .ok()
                .and_then(|v| v.trim().parse::<u64>().ok())
        })
        .map(|rate| rate.clamp(80, 300))
}

fn normalize_runtime(value: &str) -> String {
    value
        .trim()
        .to_lowercase()
        .replace('_', "-")
        .replace(' ', "-")
}

fn avatar_state_runtime(args: &Value, state: &Value) -> String {
    str_field(args, "runtime")
        .or_else(|| str_field(state, "runtime"))
        .or_else(|| std::env::var("AGENT_BRIDGE_MCP_SOURCE").ok())
        .or_else(|| std::env::var("AGENT_BRIDGE_CLIENT").ok())
        .map(|s| normalize_runtime(&s))
        .filter(|s| !s.is_empty())
        .unwrap_or_else(|| "codex".to_string())
}

fn pid_tag_short(pid: u32) -> String {
    format!("{:04x}", pid & 0xffff)
}

fn unix_now() -> i64 {
    SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map(|d| d.as_secs() as i64)
        .unwrap_or(0)
}

/// Resolve the canonical `node:project:role[:tag]` session id from env + args.
pub fn resolve_identity(
    role: Option<&str>,
    tag: Option<&str>,
    node_arg: Option<&str>,
    project_arg: Option<&str>,
    cwd_arg: Option<&str>,
) -> (String, String, String, Option<String>, String) {
    let node = node_arg
        .map(|s| s.to_string())
        .or_else(|| std::env::var("AGENT_BRIDGE_NODE").ok())
        .unwrap_or_else(|| {
            std::fs::read_to_string("/etc/hostname")
                .map(|s| s.trim().to_string())
                .ok()
                .filter(|s| !s.is_empty())
                .or_else(|| {
                    std::process::Command::new("hostname")
                        .output()
                        .ok()
                        .and_then(|o| String::from_utf8(o.stdout).ok())
                        .map(|s| s.trim().to_string())
                        .filter(|s| !s.is_empty())
                })
                .unwrap_or_else(|| "unknown".into())
        });
    let project = project_arg
        .map(|s| s.to_string())
        .or_else(|| std::env::var("AGENT_BRIDGE_PROJECT").ok())
        .or_else(|| {
            cwd_arg.and_then(|cwd| {
                Path::new(cwd)
                    .file_name()
                    .and_then(|n| n.to_str().map(|s| s.to_string()))
            })
        })
        .or_else(|| {
            std::env::current_dir().ok().and_then(|p| {
                p.file_name()
                    .and_then(|n| n.to_str().map(|s| s.to_string()))
            })
        })
        .unwrap_or_else(|| "unknown".into());
    let role = role.unwrap_or("main").to_string();
    let tag = tag.filter(|s| !s.is_empty()).map(|s| s.to_string());
    let session_id = match &tag {
        Some(t) => format!("{node}:{project}:{role}:{t}"),
        None => format!("{node}:{project}:{role}"),
    };
    (node, project, role, tag, session_id)
}

pub fn avatar_state_project(args: &Value, pet_id: &str, state: &Value, state_path: &Path) -> Value {
    let cwd_default = str_field(state, "cwd").unwrap_or_else(|| {
        std::env::current_dir()
            .ok()
            .map(|p| p.display().to_string())
            .unwrap_or_else(|| ".".to_string())
    });
    let cwd = string_arg_state_or_default(args, state, "cwd", &cwd_default);
    let project_default = str_field(state, "project").unwrap_or_else(|| {
        Path::new(&cwd)
            .file_name()
            .and_then(|n| n.to_str())
            .unwrap_or("unknown")
            .to_string()
    });
    let project = string_arg_state_or_default(args, state, "project", &project_default);
    let runtime = avatar_state_runtime(args, state);
    let agent_id = str_field(args, "agent_id")
        .or_else(|| str_field(state, "agent_id"))
        .or_else(|| str_field(state, "session_id"))
        .unwrap_or_else(|| {
            let (_, _, _, _, session_id) = resolve_identity(
                args.get("role").and_then(|v| v.as_str()),
                args.get("tag").and_then(|v| v.as_str()),
                args.get("node").and_then(|v| v.as_str()),
                Some(&project),
                Some(&cwd),
            );
            session_id
        });
    let mode = string_arg_state_or_default(args, state, "mode", "idle");
    let activity_state = str_field(args, "activity_state")
        .or_else(|| str_field(state, "activity_state"))
        .unwrap_or_else(|| mode.clone());
    let updated_at = str_field(state, "updated_at")
        .or_else(|| str_field(state, "last_verified_at"))
        .unwrap_or_else(crate::pet_state::now_utc_rfc3339);
    let mut voice_policy = json!({
        "default_silent": true,
        "allowed_modes": ["verified", "failed", "waiting_for_user", "handoff"]
    });
    if let Some(voice) = string_or_env(args, "tts_voice", "AB_PET_TTS_VOICE") {
        voice_policy["voice"] = json!(voice);
    }
    if let Some(rate) = tts_rate(args) {
        voice_policy["rate"] = json!(rate);
    }

    json!({
        "agent_avatar_protocol": 1,
        "agent_id": agent_id,
        "runtime": runtime,
        "avatar_id": pet_id,
        "mode": mode,
        "project": project,
        "cwd": cwd,
        "session_id": string_arg_state_or_null(args, state, "session_id"),
        "source": string_arg_state_or_null(args, state, "source"),
        "reason": string_arg_state_or_null(args, state, "reason"),
        "activity_state": activity_state,
        "focus": string_arg_state_or_null(args, state, "focus"),
        "risk_level": string_arg_state_or_null(args, state, "risk_level"),
        "blocked_reason": string_arg_state_or_null(args, state, "blocked_reason"),
        "evidence": string_arg_state_or_null(args, state, "evidence"),
        "verification_outcome_id": string_arg_state_or_null(args, state, "verification_outcome_id"),
        "next_action": string_arg_state_or_null(args, state, "next_action"),
        "voice_policy": voice_policy,
        "compat": {
            "codex": {
                "pet_id": pet_id,
                "package_contract": "codex-pet-atlas-8x9-v1",
                "schema_version": state.get("schema_version").cloned().unwrap_or(Value::Null),
                "sidecar_state_path": state_path.display().to_string()
            }
        },
        "updated_at": updated_at
    })
}

pub fn pet_presence_capabilities(args: &Value, pet_id: &str, state: &Value) -> Value {
    let mut capabilities = args
        .get("capabilities")
        .and_then(Value::as_object)
        .cloned()
        .unwrap_or_default();
    let mode = str_field(state, "mode").unwrap_or_else(|| "idle".to_string());
    let activity_state = string_from_args_or_state_or_default(args, state, "activity_state", &mode);

    capabilities.insert("pet_presence".to_string(), json!(true));
    capabilities.insert(
        "pet_state".to_string(),
        json!({
            "pet_id": pet_id,
            "activity_state": activity_state,
            "focus": string_from_args_or_state_or_null(args, state, "focus"),
            "risk_level": string_from_args_or_state_or_null(args, state, "risk_level"),
            "blocked_reason": string_from_args_or_state_or_null(args, state, "blocked_reason"),
            "evidence": string_from_args_or_state_or_null(args, state, "evidence"),
            "verification_outcome_id": string_from_args_or_state_or_null(args, state, "verification_outcome_id"),
            "next_action": string_from_args_or_state_or_null(args, state, "next_action"),
            "mode": mode,
            "mood": state.get("mood").cloned().unwrap_or(Value::Null),
            "project": state.get("project").cloned().unwrap_or(Value::Null),
            "cwd": state.get("cwd").cloned().unwrap_or(Value::Null),
            "last_event": state.get("last_event").cloned().unwrap_or(Value::Null),
            "last_verified_at": state.get("last_verified_at").cloned().unwrap_or(Value::Null),
            "voice_line": state.get("voice_line").cloned().unwrap_or(Value::Null),
            "ritual": state.get("ritual").cloned().unwrap_or(Value::Null),
        }),
    );
    capabilities.insert(
        "avatar_state".to_string(),
        avatar_state_project(
            args,
            pet_id,
            state,
            &crate::pet_state::pet_state_path(pet_id),
        ),
    );
    capabilities.insert(
        "voice_policy".to_string(),
        json!({
            "default_silent": true,
            "auto_ritual_allowed_modes": ["verified", "failed", "waiting_for_user", "handoff"],
            "current_voice": string_or_env(args, "tts_voice", "AB_PET_TTS_VOICE"),
            "current_rate": tts_rate(args),
        }),
    );
    Value::Object(capabilities)
}

pub async fn sync_pet_presence(store: &dyn StateStore, args: Value) -> Result<Value> {
    let pet_id = crate::pet_state::normalize_pet_id(args.get("pet_id").and_then(|v| v.as_str()));
    let state_path = crate::pet_state::pet_state_path(&pet_id);
    let state = match crate::pet_state::read_pet_state(&pet_id) {
        Ok(Some(state)) => state,
        Ok(None) => {
            return Err(Error::Backend(format!(
                "pet_presence_sync: no state file at {}",
                state_path.display()
            )))
        }
        Err(e) => {
            return Err(Error::Backend(format!(
                "pet_presence_sync: failed to read {}: {e}",
                state_path.display()
            )))
        }
    };

    let cwd_default = str_field(&state, "cwd").unwrap_or_else(|| {
        std::env::current_dir()
            .map(|p| p.display().to_string())
            .unwrap_or_else(|_| "/".to_string())
    });
    let cwd = string_or_default(&args, "cwd", &cwd_default);
    let project_default = str_field(&state, "project").unwrap_or_else(|| {
        Path::new(&cwd)
            .file_name()
            .and_then(|s| s.to_str())
            .filter(|s| !s.is_empty())
            .unwrap_or(&cwd)
            .to_string()
    });
    let project = string_or_default(&args, "project", &project_default);
    let role = string_or_default(&args, "role", "main");
    let explicit_tag = args.get("tag").and_then(|v| v.as_str());
    let (node, _, _, tag, base_session_id) = resolve_identity(
        Some(role.as_str()),
        explicit_tag,
        args.get("node").and_then(|v| v.as_str()),
        Some(project.as_str()),
        Some(cwd.as_str()),
    );
    let explicit_session_id = str_field(&args, "session_id");
    let auto_tag_enabled = args
        .get("auto_tag")
        .and_then(|v| v.as_bool())
        .unwrap_or(true);

    let (final_tag, session_id, auto_tagged) = if let Some(session_id) = explicit_session_id {
        (tag, session_id, false)
    } else if explicit_tag.is_some() || !auto_tag_enabled {
        (tag, base_session_id, false)
    } else {
        match store.agent_presence_get(&base_session_id).await {
            Ok(Some(existing)) => {
                let my_pid = std::process::id();
                let is_fresh = unix_now() - existing.last_heartbeat_at <= PRESENCE_FRESH_SECS;
                let other_owner = existing.pid != Some(i64::from(my_pid));
                if is_fresh && other_owner {
                    let auto = pid_tag_short(my_pid);
                    let new_id = format!("{node}:{project}:{role}:{auto}");
                    (Some(auto), new_id, true)
                } else {
                    (tag, base_session_id, false)
                }
            }
            Ok(None) | Err(_) => (tag, base_session_id, false),
        }
    };

    let mode = str_field(&state, "mode").unwrap_or_else(|| "idle".to_string());
    let default_name = format!("Codex {pet_id}");
    let name = string_or_default(&args, "name", &default_name);
    let default_description = format!("Pet presence: {pet_id} is {mode} in {project}");
    let description = string_or_default(&args, "description", &default_description);
    let version = string_or_default(&args, "version", "agent-bridge pet-presence-v23");
    let url = args.get("url").and_then(|v| v.as_str());
    let pid = args
        .get("pid")
        .and_then(|v| v.as_i64())
        .unwrap_or_else(|| i64::from(std::process::id()));
    let capabilities = pet_presence_capabilities(&args, &pet_id, &state);
    let default_skills = json!([{
        "id": "pet-presence",
        "name": "Codex pet presence",
        "tags": ["pet_state", "voice", "agent-bridge"]
    }]);
    let skills_v = args.get("skills").cloned().unwrap_or(default_skills);

    let upsert = AgentPresenceUpsert {
        name: Some(name.as_str()),
        description: Some(description.as_str()),
        version: Some(version.as_str()),
        url,
        node: Some(node.as_str()),
        project: Some(project.as_str()),
        role: Some(role.as_str()),
        tag: final_tag.as_deref(),
        cwd: Some(cwd.as_str()),
        pid: Some(pid),
        capabilities: Some(&capabilities),
        skills: Some(&skills_v),
    };

    let row = store
        .agent_presence_announce(&session_id, upsert)
        .await
        .map_err(|e| Error::Backend(format!("pet_presence_sync: {e}")))?;

    Ok(json!({
        "status": "ok",
        "session_id": session_id,
        "auto_tagged": auto_tagged,
        "pet_id": pet_id,
        "pet_state": capabilities.get("pet_state").cloned().unwrap_or(Value::Null),
        "avatar_state": capabilities.get("avatar_state").cloned().unwrap_or(Value::Null),
        "voice_policy": capabilities.get("voice_policy").cloned().unwrap_or(Value::Null),
        "presence": row,
    }))
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn capabilities_reads_behavior_facets_from_state() {
        let args = json!({
            "capabilities": { "forum": true },
            "tts_voice": "Flo",
            "tts_rate": 190
        });
        let state = json!({
            "mode": "working",
            "activity_state": "verifying",
            "focus": "cargo-tests",
            "risk_level": "low",
            "blocked_reason": null,
            "evidence": "cargo test -p ab-bridge pet_state passed",
            "next_action": "sync presence",
            "mood": "calm",
            "project": "agent-bridge",
            "cwd": "/tmp/agent-bridge",
            "last_event": "unit-test",
            "last_verified_at": null,
            "voice_line": null,
            "ritual": null
        });

        let capabilities = pet_presence_capabilities(&args, "xiao-shu-dev", &state);

        assert_eq!(capabilities["forum"], true);
        assert_eq!(capabilities["pet_state"]["activity_state"], "verifying");
        assert_eq!(capabilities["pet_state"]["focus"], "cargo-tests");
        assert_eq!(capabilities["pet_state"]["risk_level"], "low");
        assert_eq!(capabilities["pet_state"]["blocked_reason"], Value::Null);
        assert_eq!(
            capabilities["pet_state"]["evidence"],
            "cargo test -p ab-bridge pet_state passed"
        );
        assert_eq!(capabilities["pet_state"]["next_action"], "sync presence");
        assert_eq!(capabilities["avatar_state"]["agent_avatar_protocol"], 1);
        assert_eq!(capabilities["avatar_state"]["avatar_id"], "xiao-shu-dev");
        assert_eq!(capabilities["avatar_state"]["mode"], "working");
        assert_eq!(capabilities["avatar_state"]["activity_state"], "verifying");
        assert_eq!(capabilities["avatar_state"]["focus"], "cargo-tests");
        assert_eq!(capabilities["avatar_state"]["risk_level"], "low");
        assert_eq!(capabilities["avatar_state"]["next_action"], "sync presence");
        assert_eq!(capabilities["voice_policy"]["current_voice"], "Flo");
        assert_eq!(capabilities["voice_policy"]["current_rate"], 190);
    }

    #[test]
    fn avatar_state_defaults_activity_state_to_mode() {
        let projected = avatar_state_project(
            &json!({"agent_id": "mac:agent-bridge:main"}),
            "xiao-shu-dev",
            &json!({
                "schema_version": 1,
                "mode": "orienting",
                "updated_at": "2026-05-18T15:31:18Z"
            }),
            Path::new("/tmp/xiao-shu-dev.json"),
        );

        assert_eq!(projected["mode"], "orienting");
        assert_eq!(projected["activity_state"], "orienting");
    }
}
