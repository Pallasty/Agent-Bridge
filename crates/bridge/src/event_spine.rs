//! Read-only event-spine projections over existing Agent-Bridge telemetry.
//!
//! Phase 0 deliberately does not create a new source of truth. It derives a
//! small ordered hash chain from existing SQLite rows (MCP telemetry plus
//! agent session lifecycle rows) so callers can inspect whether telemetry can
//! support replay/explainability before we persist a unified event table.

use ab_store::{McpToolCallRow, McpToolErrorRecord, StoredSession};
use serde::Serialize;
use serde_json::{json, Value};
use sha2::{Digest, Sha256};
use std::collections::BTreeMap;

const EVENT_SPINE_SCHEMA_VERSION: u32 = 1;
const EVENT_SPINE_HASH_ALGORITHM: &str = "sha256";
const EVENT_SPINE_ZERO_HASH: &str =
    "0000000000000000000000000000000000000000000000000000000000000000";

#[derive(Debug, Clone, Serialize, PartialEq)]
pub struct EventSpineSnapshot {
    pub schema_version: u32,
    pub generated_at: i64,
    pub window_secs: i64,
    pub limit: usize,
    pub candidate_count: usize,
    pub event_count: usize,
    pub truncated_count: usize,
    pub sources: Vec<EventSpineSourceCount>,
    pub integrity: EventSpineIntegrity,
    pub events: Vec<EventSpineEvent>,
}

#[derive(Debug, Clone, Serialize, PartialEq, Eq)]
pub struct EventSpineSourceCount {
    pub source: String,
    pub count: usize,
}

#[derive(Debug, Clone, Serialize, PartialEq, Eq)]
pub struct EventSpineIntegrity {
    pub hash_algorithm: &'static str,
    pub chain_head: String,
    pub verified: bool,
}

#[derive(Debug, Clone, Serialize, PartialEq)]
pub struct EventSpineEvent {
    pub event_id: String,
    pub ts: i64,
    pub source: String,
    pub kind: String,
    pub label: String,
    pub ok: Option<bool>,
    pub payload_sha256: String,
    pub prev_hash: String,
    pub hash: String,
    pub facts: Value,
}

#[derive(Debug, Clone)]
struct RawEvent {
    ts: i64,
    source: &'static str,
    source_index: usize,
    kind: &'static str,
    label: String,
    ok: Option<bool>,
    facts: Value,
}

pub fn mcp_event_spine_snapshot(
    calls: &[McpToolCallRow],
    errors: &[McpToolErrorRecord],
    sessions: &[StoredSession],
    window_secs: i64,
    limit: usize,
    generated_at: i64,
) -> EventSpineSnapshot {
    let window_secs = window_secs.clamp(60, 31_536_000);
    let limit = limit.clamp(1, 500);
    let cutoff = generated_at.saturating_sub(window_secs);

    let mut raw = Vec::new();
    for (idx, call) in calls.iter().enumerate() {
        if call.ts < cutoff {
            continue;
        }
        raw.push(RawEvent {
            ts: call.ts,
            source: "mcp_tool_calls",
            source_index: idx,
            kind: "tool_call",
            label: call.tool_name.clone(),
            ok: Some(call.ok),
            facts: json!({
                "tool_name": call.tool_name,
                "duration_ms": call.duration_ms,
                "ok": call.ok,
                "args_size": call.args_size,
                "result_size": call.result_size,
            }),
        });
    }
    for (idx, error) in errors.iter().enumerate() {
        if error.ts < cutoff {
            continue;
        }
        raw.push(RawEvent {
            ts: error.ts,
            source: "mcp_tool_errors",
            source_index: idx,
            kind: "tool_error",
            label: error.tool_name.clone(),
            ok: Some(false),
            facts: json!({
                "tool_name": error.tool_name,
                "message": error.message,
            }),
        });
    }
    for (idx, session) in sessions.iter().enumerate() {
        if session.started_at >= cutoff {
            raw.push(RawEvent {
                ts: session.started_at,
                source: "agent_sessions",
                source_index: idx * 2,
                kind: "agent_session_started",
                label: session.runtime_id.clone(),
                ok: None,
                facts: json!({
                    "session_id": session.id.as_str(),
                    "runtime_id": session.runtime_id,
                    "cwd": session.cwd,
                    "started_at": session.started_at,
                    "ended_at": session.ended_at,
                    "running": session.ended_at.is_none(),
                }),
            });
        }
        let Some(ended_at) = session.ended_at else {
            continue;
        };
        if ended_at < cutoff {
            continue;
        }
        raw.push(RawEvent {
            ts: ended_at,
            source: "agent_sessions",
            source_index: idx * 2 + 1,
            kind: "agent_session_finished",
            label: session.runtime_id.clone(),
            ok: session.exit_code.map(|code| code == 0),
            facts: json!({
                "session_id": session.id.as_str(),
                "runtime_id": session.runtime_id,
                "cwd": session.cwd,
                "started_at": session.started_at,
                "ended_at": ended_at,
                "duration_secs": ended_at.saturating_sub(session.started_at),
                "exit_code": session.exit_code,
                "stdout_len": session.stdout.as_ref().map(|s| s.len()).unwrap_or(0),
                "stderr_len": session.stderr.as_ref().map(|s| s.len()).unwrap_or(0),
                "stdout_preview": session.stdout.as_deref().map(output_preview),
                "stderr_preview": session.stderr.as_deref().map(output_preview),
            }),
        });
    }

    raw.sort_by(|a, b| (a.ts, a.source, a.source_index).cmp(&(b.ts, b.source, b.source_index)));
    let candidate_count = raw.len();
    if raw.len() > limit {
        raw = raw.split_off(raw.len() - limit);
    }

    let mut source_counts = BTreeMap::<String, usize>::new();
    let mut events = Vec::with_capacity(raw.len());
    let mut prev_hash = EVENT_SPINE_ZERO_HASH.to_string();
    for event in raw {
        *source_counts.entry(event.source.to_string()).or_default() += 1;
        let facts_hash = sha256_json(&event.facts);
        let event_id = format!(
            "{}:{}:{}:{}",
            event.source,
            event.ts,
            event.source_index,
            &facts_hash[..12]
        );
        let hash = event_hash(
            &event_id,
            event.ts,
            event.source,
            event.kind,
            &event.label,
            event.ok,
            &facts_hash,
            &prev_hash,
        );
        events.push(EventSpineEvent {
            event_id,
            ts: event.ts,
            source: event.source.to_string(),
            kind: event.kind.to_string(),
            label: event.label,
            ok: event.ok,
            payload_sha256: facts_hash,
            prev_hash: prev_hash.clone(),
            hash: hash.clone(),
            facts: event.facts,
        });
        prev_hash = hash;
    }

    let chain_head = events
        .last()
        .map(|event| event.hash.clone())
        .unwrap_or_else(|| EVENT_SPINE_ZERO_HASH.to_string());
    let verified = verify_event_chain(&events, &chain_head);
    let sources = source_counts
        .into_iter()
        .map(|(source, count)| EventSpineSourceCount { source, count })
        .collect::<Vec<_>>();
    let event_count = events.len();

    EventSpineSnapshot {
        schema_version: EVENT_SPINE_SCHEMA_VERSION,
        generated_at,
        window_secs,
        limit,
        candidate_count,
        event_count,
        truncated_count: candidate_count.saturating_sub(event_count),
        sources,
        integrity: EventSpineIntegrity {
            hash_algorithm: EVENT_SPINE_HASH_ALGORITHM,
            chain_head,
            verified,
        },
        events,
    }
}

pub fn verify_event_chain(events: &[EventSpineEvent], expected_chain_head: &str) -> bool {
    let mut prev_hash = EVENT_SPINE_ZERO_HASH.to_string();
    for event in events {
        if event.prev_hash != prev_hash {
            return false;
        }
        let payload_sha256 = sha256_json(&event.facts);
        if event.payload_sha256 != payload_sha256 {
            return false;
        }
        let expected_hash = event_hash(
            &event.event_id,
            event.ts,
            &event.source,
            &event.kind,
            &event.label,
            event.ok,
            &event.payload_sha256,
            &event.prev_hash,
        );
        if event.hash != expected_hash {
            return false;
        }
        prev_hash = event.hash.clone();
    }
    prev_hash == expected_chain_head
}

fn event_hash(
    event_id: &str,
    ts: i64,
    source: &str,
    kind: &str,
    label: &str,
    ok: Option<bool>,
    payload_sha256: &str,
    prev_hash: &str,
) -> String {
    sha256_json(&json!({
        "event_id": event_id,
        "ts": ts,
        "source": source,
        "kind": kind,
        "label": label,
        "ok": ok,
        "payload_sha256": payload_sha256,
        "prev_hash": prev_hash,
    }))
}

fn sha256_json(value: &Value) -> String {
    let bytes = serde_json::to_vec(value).unwrap_or_else(|_| value.to_string().into_bytes());
    let mut hasher = Sha256::new();
    hasher.update(bytes);
    hex_lower(&hasher.finalize())
}

fn output_preview(s: &str) -> String {
    let redacted = redact_secret_like_tokens(s).replace('\n', " ⏎ ");
    redacted.chars().take(240).collect()
}

fn redact_secret_like_tokens(s: &str) -> String {
    let mut redact_next = false;
    s.split_whitespace()
        .map(|token| {
            if redact_next {
                redact_next = false;
                return "***redacted***";
            }
            if token.eq_ignore_ascii_case("bearer") {
                redact_next = true;
                return token;
            }
            if token.starts_with("sk-") {
                "***redacted***"
            } else {
                token
            }
        })
        .collect::<Vec<_>>()
        .join(" ")
}

fn hex_lower(bytes: &[u8]) -> String {
    const HEX: &[u8; 16] = b"0123456789abcdef";
    let mut out = String::with_capacity(bytes.len() * 2);
    for b in bytes {
        out.push(HEX[(b >> 4) as usize] as char);
        out.push(HEX[(b & 0x0f) as usize] as char);
    }
    out
}

#[cfg(test)]
mod tests {
    use super::*;

    fn call(ts: i64, tool_name: &str, ok: bool) -> McpToolCallRow {
        McpToolCallRow {
            ts,
            tool_name: tool_name.to_string(),
            duration_ms: 12,
            ok,
            args_size: Some(4),
            result_size: Some(8),
        }
    }

    fn error(ts: i64, tool_name: &str, message: &str) -> McpToolErrorRecord {
        McpToolErrorRecord {
            ts,
            tool_name: tool_name.to_string(),
            message: message.to_string(),
        }
    }

    fn session(
        id: &str,
        runtime_id: &str,
        started_at: i64,
        ended_at: Option<i64>,
        exit_code: Option<i32>,
    ) -> StoredSession {
        StoredSession {
            id: ab_core::SessionId::from_raw(id.to_string()),
            runtime_id: runtime_id.to_string(),
            cwd: "/tmp/work".to_string(),
            started_at,
            ended_at,
            exit_code,
            stdout: Some("Failed to authenticate. API Error: 403 quota".to_string()),
            stderr: None,
            cloud_run_id: None,
            cloud_run_state: None,
            cloud_session_link: None,
        }
    }

    #[test]
    fn mcp_event_spine_orders_events_and_builds_verified_chain() {
        let snapshot = mcp_event_spine_snapshot(
            &[
                call(100, "memory_search", true),
                call(102, "skills_route", true),
            ],
            &[error(
                101,
                "agent_spawn",
                "spawn kilo: No such file or directory",
            )],
            &[],
            60,
            10,
            120,
        );

        assert_eq!(snapshot.schema_version, 1);
        assert_eq!(snapshot.event_count, 3);
        assert_eq!(snapshot.truncated_count, 0);
        assert_eq!(
            snapshot
                .events
                .iter()
                .map(|event| event.kind.as_str())
                .collect::<Vec<_>>(),
            vec!["tool_call", "tool_error", "tool_call"]
        );
        assert_eq!(snapshot.events[0].prev_hash, EVENT_SPINE_ZERO_HASH);
        assert_eq!(snapshot.events[1].prev_hash, snapshot.events[0].hash);
        assert_eq!(snapshot.events[2].prev_hash, snapshot.events[1].hash);
        assert_eq!(snapshot.integrity.chain_head, snapshot.events[2].hash);
        assert!(snapshot.integrity.verified);
        assert!(verify_event_chain(
            &snapshot.events,
            &snapshot.integrity.chain_head
        ));
    }

    #[test]
    fn mcp_event_spine_filters_window_and_reports_truncation() {
        let snapshot = mcp_event_spine_snapshot(
            &[
                call(10, "old_tool", true),
                call(95, "first_new_tool", true),
                call(96, "second_new_tool", true),
            ],
            &[],
            &[],
            60,
            1,
            120,
        );

        assert_eq!(snapshot.candidate_count, 2);
        assert_eq!(snapshot.event_count, 1);
        assert_eq!(snapshot.truncated_count, 1);
        assert_eq!(snapshot.events[0].label, "second_new_tool");
        assert_eq!(snapshot.sources[0].source, "mcp_tool_calls");
        assert_eq!(snapshot.sources[0].count, 1);
    }

    #[test]
    fn event_spine_marks_failed_agent_session_finish_not_ok() {
        let snapshot = mcp_event_spine_snapshot(
            &[],
            &[],
            &[session(
                "ses-failed",
                "claude-code",
                100,
                Some(103),
                Some(1),
            )],
            60,
            10,
            120,
        );

        assert_eq!(snapshot.event_count, 2);
        assert_eq!(snapshot.events[0].source, "agent_sessions");
        assert_eq!(snapshot.events[0].kind, "agent_session_started");
        assert_eq!(snapshot.events[0].ok, None);
        assert_eq!(snapshot.events[1].source, "agent_sessions");
        assert_eq!(snapshot.events[1].kind, "agent_session_finished");
        assert_eq!(snapshot.events[1].ok, Some(false));
        assert_eq!(snapshot.events[1].facts["session_id"], "ses-failed");
        assert_eq!(snapshot.events[1].facts["runtime_id"], "claude-code");
        assert_eq!(snapshot.events[1].facts["exit_code"], 1);
        assert!(snapshot.integrity.verified);
    }

    #[test]
    fn event_spine_limit_keeps_most_recent_events() {
        let snapshot = mcp_event_spine_snapshot(
            &[call(70, "old_tool", true), call(80, "middle_tool", true)],
            &[],
            &[session("ses-recent", "kilo", 110, Some(115), Some(1))],
            60,
            1,
            120,
        );

        assert_eq!(snapshot.candidate_count, 4);
        assert_eq!(snapshot.event_count, 1);
        assert_eq!(snapshot.truncated_count, 3);
        assert_eq!(snapshot.events[0].kind, "agent_session_finished");
        assert_eq!(snapshot.events[0].facts["session_id"], "ses-recent");
    }

    #[test]
    fn output_preview_redacts_secret_like_tokens() {
        let preview = output_preview("api_key sk-live-secret\nAuthorization: Bearer abc123");

        assert!(!preview.contains("sk-live-secret"));
        assert!(!preview.contains("abc123"));
        assert!(preview.contains("***redacted***"));
    }
}
