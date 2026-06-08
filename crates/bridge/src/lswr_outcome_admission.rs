//! Live Semantic World Runtime Step E outcome-admission classifier.
//!
//! Step D proves that an LSWR world result can be rendered as an honest
//! present-compatible review artifact. Step E is a separate learning boundary:
//! it decides whether that artifact can become a verified outcome candidate, or
//! whether it must stay audit-only / rejected evidence. This module is pure:
//! no MCP calls, no filesystem IO, no memory writes.

use serde_json::{Value, json};

use crate::lswr_present::LSWR_PRESENT_PACKET_SCHEMA;
use crate::present_ingest::OUTCOME_MEMORY_KIND;

pub const LSWR_OUTCOME_ADMISSION_SCHEMA: &str = "agent_bridge.lswr.outcome_admission.v0";

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum LswrAdmissionClass {
    TrainingEligible,
    AuditOnly,
    Rejected,
}

impl LswrAdmissionClass {
    pub fn as_str(&self) -> &'static str {
        match self {
            Self::TrainingEligible => "training_eligible",
            Self::AuditOnly => "audit_only",
            Self::Rejected => "rejected",
        }
    }
}

/// Classify an LSWR Step D review artifact for later #94-compatible use.
///
/// `source_packet` is the original Step D packet, `expression` is the output
/// lane record for the rendered artifact, and `extracted_payload` is the
/// dual-encoded `#ab-payload` recovered from that artifact. Passing the
/// recovered payload explicitly makes the no-laundering boundary testable: a
/// rendered HTML surface cannot claim training eligibility if its embedded
/// machine payload is missing or differs from the source packet.
pub fn classify_outcome_admission(
    source_packet: &Value,
    expression: &Value,
    extracted_payload: Option<&Value>,
) -> Value {
    let (class, reason) = if !source_packet.is_object() {
        (LswrAdmissionClass::Rejected, "malformed_source_packet")
    } else if str_at(source_packet, &["schema"]) != Some(LSWR_PRESENT_PACKET_SCHEMA) {
        (LswrAdmissionClass::Rejected, "unsupported_schema")
    } else if !supported_world_tool(str_at(source_packet, &["world_tool"])) {
        (LswrAdmissionClass::Rejected, "unsupported_world_tool")
    } else if source_packet.get("machine_payload").is_none()
        || source_packet
            .get("machine_payload")
            .is_some_and(Value::is_null)
    {
        (LswrAdmissionClass::Rejected, "missing_machine_payload")
    } else if expression.get("token_match").and_then(Value::as_bool) == Some(false) {
        (LswrAdmissionClass::Rejected, "token_mismatch")
    } else if extracted_payload.is_none() {
        (LswrAdmissionClass::Rejected, "dual_payload_missing")
    } else if extracted_payload != Some(source_packet) {
        (LswrAdmissionClass::Rejected, "dual_payload_mismatch")
    } else if unsafe_block_reason(str_at(source_packet, &["reason"])) {
        (LswrAdmissionClass::Rejected, "unsafe_endpoint_rejected")
    } else if str_at(source_packet, &["verdict"]) != Some("verified") {
        let reason = match str_at(source_packet, &["verdict"]) {
            Some("blocked") => "source_world_blocked",
            _ => "source_world_not_verified",
        };
        (LswrAdmissionClass::AuditOnly, reason)
    } else if str_at(source_packet, &["reason"]).is_some() {
        (LswrAdmissionClass::AuditOnly, "source_world_reason_present")
    } else if str_at(source_packet, &["provenance", "verified_to"]).is_none() {
        (LswrAdmissionClass::AuditOnly, "missing_verified_to")
    } else if str_at(source_packet, &["machine_payload", "verify", "method"]).is_none() {
        (LswrAdmissionClass::AuditOnly, "missing_verify_method")
    } else if str_at(source_packet, &["world_tool"]) == Some("world_patch")
        && bool_at(
            source_packet,
            &["machine_payload", "patch_result", "applied"],
        ) != Some(true)
    {
        (LswrAdmissionClass::AuditOnly, "patch_not_applied")
    } else if expected_effect_failed(source_packet) {
        (
            LswrAdmissionClass::AuditOnly,
            "expected_effect_not_verified",
        )
    } else if action_result_not_verified(source_packet) {
        (LswrAdmissionClass::AuditOnly, "action_result_not_verified")
    } else if let Some(expression_reason) = expression_gate_reason(expression) {
        (LswrAdmissionClass::AuditOnly, expression_reason)
    } else {
        (LswrAdmissionClass::TrainingEligible, "eligible")
    };

    admission_record(source_packet, expression, class, reason)
}

fn admission_record(
    source_packet: &Value,
    expression: &Value,
    class: LswrAdmissionClass,
    reason: &str,
) -> Value {
    let eligible = class == LswrAdmissionClass::TrainingEligible;
    json!({
        "schema": LSWR_OUTCOME_ADMISSION_SCHEMA,
        "source": {
            "present_artifact_id": first_str(expression, &[&["present_artifact_id"], &["artifact_id"]]),
            "world_tool": str_at(source_packet, &["world_tool"]),
            "world_verdict": str_at(source_packet, &["verdict"]),
            "world_reason": str_at(source_packet, &["reason"]),
            "verified_to": str_at(source_packet, &["provenance", "verified_to"]),
            "verify_method": first_str(source_packet, &[
                &["machine_payload", "verify", "method"],
                &["provenance", "verify_method"],
            ]),
        },
        "expression": {
            "verify_status": str_at(expression, &["verify_status"]),
            "embody_status": str_at(expression, &["embody_status"]),
            "interactive_status": str_at(expression, &["interactive_status"]),
            "decision": str_at(expression, &["decision"]),
            "token_match": expression.get("token_match").and_then(Value::as_bool),
        },
        "admission": {
            "class": class.as_str(),
            "eligible": eligible,
            "reason": reason,
        },
        "memory": {
            "write_allowed": false,
            "dry_run_required": true,
            "target_kind": OUTCOME_MEMORY_KIND,
        },
    })
}

fn supported_world_tool(tool: Option<&str>) -> bool {
    matches!(
        tool,
        Some("world_patch" | "world_query" | "world_visibility_query")
    )
}

fn unsafe_block_reason(reason: Option<&str>) -> bool {
    matches!(
        reason,
        Some("world_host_non_loopback_rejected" | "unsafe_endpoint_rejected")
    )
}

fn expected_effect_failed(packet: &Value) -> bool {
    let Some(effect) = get_path(packet, &["machine_payload", "expected_effect"]) else {
        return false;
    };
    if effect.is_null() {
        return false;
    }
    effect.get("verified").and_then(Value::as_bool) != Some(true)
}

fn action_result_not_verified(packet: &Value) -> bool {
    let Some(action) = get_path(packet, &["machine_payload", "action_result"]) else {
        return false;
    };
    if action.is_null() {
        return false;
    }
    str_at(action, &["verdict"]) == Some("not_verified")
        || str_at(action, &["status"]) == Some("not_verified")
        || action.get("verified").and_then(Value::as_bool) == Some(false)
}

fn expression_gate_reason(expression: &Value) -> Option<&'static str> {
    match str_at(expression, &["verify_status"]) {
        Some("rendered_ok") => {}
        Some(_) | None => return Some("expression_not_rendered_ok"),
    }

    if let Some(embody) = str_at(expression, &["embody_status"]) {
        if embody != "embodied" && embody != "not_applicable" {
            return Some("expression_embody_not_eligible");
        }
    }

    if let Some(interactive) = str_at(expression, &["interactive_status"]) {
        if interactive != "verified" && interactive != "not_applicable" {
            return Some("expression_interactive_not_eligible");
        }
    }

    if let Some(decision) = str_at(expression, &["decision"]) {
        if decision != "approved" {
            return Some("expression_decision_not_approved");
        }
    }

    None
}

fn first_str<'a>(value: &'a Value, paths: &[&[&str]]) -> Option<&'a str> {
    paths.iter().find_map(|path| str_at(value, path))
}

fn str_at<'a>(value: &'a Value, path: &[&str]) -> Option<&'a str> {
    get_path(value, path).and_then(Value::as_str).and_then(|s| {
        let trimmed = s.trim();
        if trimmed.is_empty() {
            None
        } else {
            Some(trimmed)
        }
    })
}

fn bool_at(value: &Value, path: &[&str]) -> Option<bool> {
    get_path(value, path).and_then(Value::as_bool)
}

fn get_path<'a>(value: &'a Value, path: &[&str]) -> Option<&'a Value> {
    let mut cur = value;
    for key in path {
        cur = cur.get(*key)?;
    }
    Some(cur)
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::lswr_present::{
        PresentPacketOptions, WORLD_TOOL_SCHEMA, world_envelope_to_present_packet,
    };
    use serde_json::json;

    const GENERATED_AT: &str = "2026-06-08T00:00:00Z";

    fn opts() -> PresentPacketOptions<'static> {
        PresentPacketOptions::new(GENERATED_AT).with_commit("8dd77bb")
    }

    fn expression() -> Value {
        json!({
            "present_artifact_id": "ab_step_e_fixture",
            "verify_status": "rendered_ok",
            "embody_status": "not_applicable",
            "interactive_status": "not_applicable",
            "decision": "approved",
            "token_match": true
        })
    }

    fn verified_patch_packet() -> Value {
        let envelope = json!({
            "schema": WORLD_TOOL_SCHEMA,
            "ok": true,
            "verified": true,
            "request": {
                "world.patch": {
                    "op": "move",
                    "entity": "bath",
                    "args": {"cell": [8, 0]},
                    "expected_effect": {
                        "target": "bath",
                        "metric": "screen_area",
                        "to_op": ">=",
                        "to_value": 0.001
                    }
                }
            },
            "verify": {
                "method": "live_viewport_pixel_coverage",
                "verified_to": "onsen_live_root_viewport",
                "evidence": {"screen_area": 0.003}
            },
            "host_response": {
                "world.patch": {
                    "applied": true,
                    "entity": "bath",
                    "op": "move"
                },
                "expected_effect": {
                    "verified": true,
                    "metric": "screen_area",
                    "actual": 0.003,
                    "clauses": [{
                        "metric": "screen_area",
                        "actual": 0.003,
                        "to_op": ">=",
                        "to_value": 0.001,
                        "verified": true
                    }]
                }
            }
        });
        world_envelope_to_present_packet("world_patch", &envelope, opts())
    }

    fn expected_effect_failure_packet() -> Value {
        let envelope = json!({
            "schema": WORLD_TOOL_SCHEMA,
            "ok": true,
            "verified": false,
            "reason": "expected_effect_clause_failed",
            "request": {
                "world.patch": {
                    "op": "move",
                    "entity": "bath",
                    "args": {"cell": [8, 0]},
                    "expected_effect": {
                        "target": "bath",
                        "metric": "screen_area",
                        "to_op": ">=",
                        "to_value": 0.25
                    }
                }
            },
            "verify": {
                "method": "live_viewport_pixel_coverage",
                "verified_to": null,
                "evidence": {"host_reason": "expected_effect_clause_failed"}
            },
            "host_response": {
                "world.patch": {"applied": true, "entity": "bath", "op": "move"},
                "expected_effect": {
                    "verified": false,
                    "reason": "expected_effect_clause_failed",
                    "actual": 0.12,
                    "clauses": [{
                        "metric": "screen_area",
                        "actual": 0.12,
                        "to_op": ">=",
                        "to_value": 0.25,
                        "verified": false,
                        "reason": "expected_effect_clause_failed"
                    }]
                }
            }
        });
        world_envelope_to_present_packet("world_patch", &envelope, opts())
    }

    #[test]
    fn verified_world_and_expression_classifies_training_eligible() {
        let packet = verified_patch_packet();
        let admission = classify_outcome_admission(&packet, &expression(), Some(&packet));

        assert_eq!(admission["schema"], LSWR_OUTCOME_ADMISSION_SCHEMA);
        assert_eq!(admission["admission"]["class"], "training_eligible");
        assert_eq!(admission["admission"]["eligible"], true);
        assert_eq!(admission["admission"]["reason"], "eligible");
        assert_eq!(admission["source"]["world_tool"], "world_patch");
        assert_eq!(admission["source"]["world_verdict"], "verified");
        assert_eq!(
            admission["source"]["verified_to"],
            "onsen_live_root_viewport"
        );
        assert_eq!(
            admission["source"]["verify_method"],
            "live_viewport_pixel_coverage"
        );
        assert_eq!(admission["memory"]["write_allowed"], false);
        assert_eq!(admission["memory"]["dry_run_required"], true);
        assert_eq!(admission["memory"]["target_kind"], OUTCOME_MEMORY_KIND);
    }

    #[test]
    fn expected_effect_failure_stays_audit_only_even_when_rendered_and_approved() {
        let packet = expected_effect_failure_packet();
        let admission = classify_outcome_admission(&packet, &expression(), Some(&packet));

        assert_eq!(admission["admission"]["class"], "audit_only");
        assert_eq!(admission["admission"]["eligible"], false);
        assert_eq!(
            admission["admission"]["reason"],
            "source_world_not_verified"
        );
        assert_eq!(admission["source"]["world_verdict"], "not_verified");
        assert_eq!(
            admission["source"]["world_reason"],
            "expected_effect_clause_failed"
        );
        assert_eq!(admission["expression"]["decision"], "approved");
        assert_eq!(admission["memory"]["write_allowed"], false);
    }

    #[test]
    fn human_rejection_keeps_verified_world_audit_only() {
        let packet = verified_patch_packet();
        let mut expr = expression();
        expr["decision"] = json!("rejected");

        let admission = classify_outcome_admission(&packet, &expr, Some(&packet));

        assert_eq!(admission["admission"]["class"], "audit_only");
        assert_eq!(
            admission["admission"]["reason"],
            "expression_decision_not_approved"
        );
        assert_eq!(admission["source"]["world_verdict"], "verified");
    }

    #[test]
    fn expression_render_failure_is_audit_only_not_rejected() {
        let packet = verified_patch_packet();
        let mut expr = expression();
        expr["verify_status"] = json!("blank");

        let admission = classify_outcome_admission(&packet, &expr, Some(&packet));

        assert_eq!(admission["admission"]["class"], "audit_only");
        assert_eq!(
            admission["admission"]["reason"],
            "expression_not_rendered_ok"
        );
    }

    #[test]
    fn token_mismatch_is_rejected() {
        let packet = verified_patch_packet();
        let mut expr = expression();
        expr["token_match"] = json!(false);

        let admission = classify_outcome_admission(&packet, &expr, Some(&packet));

        assert_eq!(admission["admission"]["class"], "rejected");
        assert_eq!(admission["admission"]["reason"], "token_mismatch");
    }

    #[test]
    fn missing_dual_payload_is_rejected() {
        let packet = verified_patch_packet();
        let admission = classify_outcome_admission(&packet, &expression(), None);

        assert_eq!(admission["admission"]["class"], "rejected");
        assert_eq!(admission["admission"]["reason"], "dual_payload_missing");
    }

    #[test]
    fn dual_payload_mismatch_is_rejected() {
        let packet = verified_patch_packet();
        let mut extracted = packet.clone();
        extracted["verdict"] = json!("verified");
        extracted["machine_payload"]["expected_effect"]["actual"] = json!(999);

        let admission = classify_outcome_admission(&packet, &expression(), Some(&extracted));

        assert_eq!(admission["admission"]["class"], "rejected");
        assert_eq!(admission["admission"]["reason"], "dual_payload_mismatch");
    }

    #[test]
    fn malformed_or_unsupported_schema_is_rejected() {
        let packet = json!({"schema": "other.schema", "world_tool": "world_patch"});
        let admission = classify_outcome_admission(&packet, &expression(), Some(&packet));

        assert_eq!(admission["admission"]["class"], "rejected");
        assert_eq!(admission["admission"]["reason"], "unsupported_schema");

        let admission = classify_outcome_admission(&Value::Null, &expression(), None);
        assert_eq!(admission["admission"]["class"], "rejected");
        assert_eq!(admission["admission"]["reason"], "malformed_source_packet");
    }

    #[test]
    fn unsafe_blocked_packet_is_rejected() {
        let packet = json!({
            "schema": LSWR_PRESENT_PACKET_SCHEMA,
            "world_tool": "world_query",
            "verdict": "blocked",
            "reason": "world_host_non_loopback_rejected",
            "machine_payload": {"verify": {"method": "preflight"}},
            "provenance": {"verified_to": null, "verify_method": "preflight"},
            "ingestion": {"allowed": false}
        });

        let admission = classify_outcome_admission(&packet, &expression(), Some(&packet));

        assert_eq!(admission["admission"]["class"], "rejected");
        assert_eq!(admission["admission"]["reason"], "unsafe_endpoint_rejected");
    }

    #[test]
    fn verified_patch_without_applied_result_is_audit_only() {
        let mut packet = verified_patch_packet();
        packet["machine_payload"]["patch_result"]["applied"] = json!(false);

        let admission = classify_outcome_admission(&packet, &expression(), Some(&packet));

        assert_eq!(admission["admission"]["class"], "audit_only");
        assert_eq!(admission["admission"]["reason"], "patch_not_applied");
    }
}
