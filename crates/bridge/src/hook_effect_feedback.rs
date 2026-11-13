//! Read-only projection of hook effect receipts. Never infer an effect from exit=0.
use serde_json::{json, Map, Value};

pub(crate) fn fields(run: Option<&Value>) -> Map<String, Value> {
    let raw = run.and_then(|r| r.get("effect_feedback"));
    let feedback = raw.and_then(project_feedback);
    let state = match (raw, &feedback) {
        (_, Some(_)) => "reported",
        (None | Some(Value::Null), _) => "unreported",
        _ => "invalid",
    };
    let session = run
        .and_then(|r| r.get("session_id_sha256"))
        .and_then(Value::as_str)
        .filter(|s| s.len() == 64 && s.bytes().all(|b| b.is_ascii_hexdigit()));
    json!({
        "last_effect_feedback": feedback,
        "last_effect_feedback_state": state,
        "last_session_id_sha256": session,
    })
    .as_object()
    .expect("effect fields object")
    .clone()
}

fn project_feedback(raw: &Value) -> Option<Value> {
    // Strict vocabulary prevents a future/free-form payload (prompt or memory
    // body) from accidentally becoming a status response. Unknown schemas remain
    // explicitly invalid, rather than silently reporting success or old effects.
    let lifecycle =
        raw.get("requested").and_then(Value::as_str) == Some("session_lifecycle_precompact");
    let vocabularies: &[(&str, &[&str])] = if lifecycle {
        &[
            (
                "status",
                &["completed", "degraded", "skipped", "failed", "unknown"],
            ),
            (
                "code",
                &[
                    "session_id_missing",
                    "binary_missing",
                    "transcript_missing",
                    "temporary_workspace_failed",
                    "transcript_read_failed",
                    "conversation_empty",
                    "request_build_failed",
                    "hook_did_not_reach_outcome",
                    "lifecycle_timeout",
                    "lifecycle_process_failed",
                    "lifecycle_response_missing",
                    "lifecycle_response_invalid",
                    "lifecycle_rpc_error",
                    "lifecycle_tool_error",
                    "lifecycle_partial_result",
                    "lifecycle_completed",
                ],
            ),
            ("requested", &["session_lifecycle_precompact"]),
            ("actual", &["none", "not_confirmed", "lifecycle_response"]),
            ("verification_scope", &["hook_and_mcp_response_only"]),
        ]
    } else {
        &[
            (
                "status",
                &["emitted", "degraded", "skipped", "failed", "unknown"],
            ),
            (
                "code",
                &[
                    "bootstrap_context_emitted",
                    "static_fallback_emitted",
                    "static_requested_emitted",
                    "cooldown",
                    "curator_guard",
                    "database_missing",
                    "no_context_emitted",
                    "static_query_failed",
                    "hook_did_not_reach_outcome",
                ],
            ),
            ("requested", &["bootstrap_context", "static_context"]),
            (
                "actual",
                &[
                    "bootstrap_context_payload",
                    "static_context_payload",
                    "none",
                ],
            ),
            ("verification_scope", &["hook_payload_only"]),
        ]
    };
    let mut projected = Map::new();
    for (key, allowed) in vocabularies {
        let value = raw.get(*key)?.as_str()?;
        if !allowed.contains(&value) {
            return None;
        }
        projected.insert((*key).into(), json!(value));
    }
    let dropped = raw.get("dropped")?.as_array()?;
    if (lifecycle && !dropped.is_empty())
        || dropped.len() > 1
        || dropped
            .iter()
            .any(|v| v.as_str() != Some("bootstrap_context_selection"))
    {
        return None;
    }
    projected.insert("dropped".into(), json!(dropped));
    Some(Value::Object(projected))
}

#[cfg(test)]
mod tests {
    use super::*;

    fn receipt(status: &str, code: &str, actual: &str) -> Value {
        json!({"exit_code":0,"session_id_sha256":"a".repeat(64),
            "effect_feedback":{"status":status,"code":code,
                "requested":"bootstrap_context","actual":actual,
                "dropped":[],"verification_scope":"hook_payload_only"}})
    }

    #[test]
    fn effects_remain_distinct_despite_zero_exit_codes() {
        for (status, code, actual) in [
            (
                "emitted",
                "bootstrap_context_emitted",
                "bootstrap_context_payload",
            ),
            (
                "degraded",
                "static_fallback_emitted",
                "static_context_payload",
            ),
            ("skipped", "cooldown", "none"),
            ("failed", "static_query_failed", "none"),
            ("unknown", "hook_did_not_reach_outcome", "none"),
        ] {
            let row = receipt(status, code, actual);
            let result = fields(Some(&row));
            assert_eq!(result["last_effect_feedback"], row["effect_feedback"]);
            assert_eq!(result["last_effect_feedback_state"], "reported");
            assert_eq!(result["last_session_id_sha256"], "a".repeat(64));
        }
    }

    #[test]
    fn legacy_or_absent_receipts_do_not_infer_success() {
        for row in [None, Some(json!({"exit_code":0,"output_bytes":500}))] {
            let result = fields(row.as_ref());
            assert_eq!(result["last_effect_feedback"], Value::Null);
            assert_eq!(result["last_effect_feedback_state"], "unreported");
            assert_eq!(result["last_session_id_sha256"], Value::Null);
        }
    }

    #[test]
    fn feedback_is_allowlisted_without_forwarding_private_extensions() {
        let mut row = receipt(
            "degraded",
            "static_fallback_emitted",
            "static_context_payload",
        );
        row["effect_feedback"]["dropped"] = json!(["bootstrap_context_selection"]);
        row["effect_feedback"]["prompt"] = json!("private prompt fixture");
        row["session_id"] = json!("plaintext-session");
        let result = fields(Some(&row));
        assert_eq!(
            result["last_effect_feedback"]["dropped"],
            json!(["bootstrap_context_selection"])
        );
        assert!(!serde_json::to_string(&result)
            .unwrap()
            .contains("private prompt"));
        assert!(!serde_json::to_string(&result)
            .unwrap()
            .contains("plaintext-session"));
    }

    #[test]
    fn malformed_feedback_stays_invalid_and_does_not_echo_arbitrary_text() {
        for bad in [
            json!("private text"),
            json!({}),
            json!({"status":"emitted"}),
        ] {
            let mut row = receipt(
                "emitted",
                "bootstrap_context_emitted",
                "bootstrap_context_payload",
            );
            row["effect_feedback"] = bad;
            let result = fields(Some(&row));
            assert_eq!(result["last_effect_feedback"], Value::Null);
            assert_eq!(result["last_effect_feedback_state"], "invalid");
        }
        let mut row = receipt(
            "emitted",
            "bootstrap_context_emitted",
            "bootstrap_context_payload",
        );
        row["effect_feedback"]["dropped"] = json!(["private memory body"]);
        row["session_id_sha256"] = json!("plaintext-session");
        let result = fields(Some(&row));
        assert_eq!(result["last_effect_feedback_state"], "invalid");
        assert_eq!(result["last_session_id_sha256"], Value::Null);
    }

    #[test]
    fn lifecycle_feedback_preserves_unknown_partial_and_completed_distinctions() {
        for (status, code, actual) in [
            ("skipped", "transcript_missing", "none"),
            ("failed", "lifecycle_tool_error", "not_confirmed"),
            ("unknown", "lifecycle_timeout", "not_confirmed"),
            ("unknown", "lifecycle_response_missing", "not_confirmed"),
            ("degraded", "lifecycle_partial_result", "lifecycle_response"),
            ("completed", "lifecycle_completed", "lifecycle_response"),
        ] {
            let mut row = receipt(status, code, actual);
            row["effect_feedback"]["requested"] = json!("session_lifecycle_precompact");
            row["effect_feedback"]["verification_scope"] = json!("hook_and_mcp_response_only");
            let result = fields(Some(&row));
            assert_eq!(result["last_effect_feedback_state"], "reported");
            assert_eq!(result["last_effect_feedback"], row["effect_feedback"]);
            row["effect_feedback"]["private_error"] = json!("secret transcript");
            assert!(!serde_json::to_string(&fields(Some(&row)))
                .unwrap()
                .contains("secret"));
            row["effect_feedback"]["verification_scope"] = json!("hook_payload_only");
            assert_eq!(fields(Some(&row))["last_effect_feedback_state"], "invalid");
        }
    }
}
