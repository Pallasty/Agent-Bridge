//! Live Semantic World Runtime Step E outcome-admission classifier.
//!
//! Step D proves that an LSWR world result can be rendered as an honest
//! present-compatible review artifact. Step E is a separate learning boundary:
//! it decides whether that artifact can become a verified outcome candidate, or
//! whether it must stay audit-only / rejected evidence. This module is pure:
//! no MCP calls and no memory writes. The E2 projection below performs
//! read-only artifact IO, but still writes nothing.

use std::collections::{BTreeMap, BTreeSet};
use std::path::{Path, PathBuf};

use serde_json::{json, Value};
use sha2::{Digest, Sha256};

use crate::lswr_present::LSWR_PRESENT_PACKET_SCHEMA;
use crate::present::{ArtifactInfo, OUTCOME_SIDECAR_SUFFIX};
use crate::present_ingest::{build_outcome_memory, OUTCOME_MEMORY_KIND};

pub const LSWR_OUTCOME_ADMISSION_SCHEMA: &str = "agent_bridge.lswr.outcome_admission.v0";
pub const LSWR_OUTCOME_ADMISSIONS_PROJECTION_SCHEMA: &str =
    "agent_bridge.lswr.outcome_admissions.v0";
pub const LSWR_OUTCOME_ADMISSION_DRY_RUN_SCHEMA: &str =
    "agent_bridge.lswr.outcome_admission_dry_run.v0";
pub const LSWR_OUTCOME_ADMISSION_INGEST_PLAN_SCHEMA: &str =
    "agent_bridge.lswr.outcome_admission_ingest_plan.v0";

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

/// Read-only E2 projection over persisted Step D review artifacts.
///
/// The caller supplies [`ArtifactInfo`] rows, usually from
/// [`crate::present::list_artifacts`]. This function reads each artifact's HTML,
/// recovers its dual-encoded LSWR packet, looks for a sibling
/// `<artifact_id>.outcome.json` expression record, then applies the E1
/// classifier. Artifacts that are not LSWR Step D packets are skipped, not
/// treated as rejected LSWR evidence.
pub fn outcome_admissions_projection(
    artifacts: &[ArtifactInfo],
    eligible_only: bool,
    generated_at: u64,
    window_secs: u64,
) -> Value {
    let mut training_eligible_count = 0usize;
    let mut audit_only_count = 0usize;
    let mut rejected_count = 0usize;
    let mut skipped_non_lswr_count = 0usize;
    let mut artifact_read_error_count = 0usize;
    let mut reason_counts: BTreeMap<String, usize> = BTreeMap::new();
    let mut admissions: Vec<Value> = Vec::new();

    for artifact in artifacts {
        let path = Path::new(&artifact.artifact_path);
        let html = match std::fs::read_to_string(path) {
            Ok(html) => html,
            Err(_) => {
                artifact_read_error_count += 1;
                let admission = artifact_rejection(artifact, "artifact_read_error");
                rejected_count += 1;
                bump_reason(&mut reason_counts, "artifact_read_error");
                if !eligible_only {
                    admissions.push(admission);
                }
                continue;
            }
        };
        let provenance = crate::present::extract_script_json(&html, "ab-provenance");
        let source_tool = str_at_value(provenance.as_ref(), &["source_tool"]);
        let payload = crate::present::extract_ab_payload(&html);
        let is_lswr_payload =
            str_at_value(payload.as_ref(), &["schema"]) == Some(LSWR_PRESENT_PACKET_SCHEMA);
        let is_lswr_artifact = is_lswr_payload || source_tool == Some("lswr_present");

        if !is_lswr_artifact {
            skipped_non_lswr_count += 1;
            continue;
        }

        let Some(packet) = payload else {
            rejected_count += 1;
            bump_reason(&mut reason_counts, "dual_payload_missing");
            let admission = artifact_rejection(artifact, "dual_payload_missing");
            if !eligible_only {
                admissions.push(admission);
            }
            continue;
        };

        let expression = expression_record_for_artifact(artifact, path);
        let mut admission = classify_outcome_admission(&packet, &expression, Some(&packet));
        if let Some(obj) = admission.as_object_mut() {
            obj.insert(
                "artifact".into(),
                json!({
                    "id": artifact.id,
                    "artifact_path": artifact.artifact_path,
                    "kind": artifact.kind,
                    "ts": artifact.ts,
                    "bytes": artifact.bytes,
                    "dual_encoding": artifact.dual_encoding,
                    "has_screenshot": artifact.has_screenshot,
                    "expression_source": expression
                        .get("expression_source")
                        .and_then(Value::as_str)
                        .unwrap_or("unknown"),
                }),
            );
        }

        let class = str_at(&admission, &["admission", "class"]).unwrap_or("rejected");
        let reason = str_at(&admission, &["admission", "reason"]).unwrap_or("unknown");
        match class {
            "training_eligible" => training_eligible_count += 1,
            "audit_only" => audit_only_count += 1,
            _ => rejected_count += 1,
        }
        bump_reason(&mut reason_counts, reason);

        if class == "training_eligible" || !eligible_only {
            admissions.push(admission);
        }
    }

    let mut reasons = serde_json::Map::new();
    for (reason, count) in reason_counts {
        reasons.insert(reason, json!(count));
    }

    json!({
        "schema": LSWR_OUTCOME_ADMISSIONS_PROJECTION_SCHEMA,
        "generated_at": generated_at,
        "window_secs": window_secs,
        "scanned_artifacts": artifacts.len(),
        "skipped_non_lswr_count": skipped_non_lswr_count,
        "artifact_read_error_count": artifact_read_error_count,
        "lswr_artifact_count": training_eligible_count + audit_only_count + rejected_count,
        "training_eligible_count": training_eligible_count,
        "audit_only_count": audit_only_count,
        "rejected_count": rejected_count,
        "eligible_only": eligible_only,
        "reason_counts": Value::Object(reasons),
        "admissions": admissions,
    })
}

/// Step E3 dry-run adapter from E2 admissions to #94-compatible memory rows.
///
/// This is intentionally pure: it performs no IO, calls no store APIs, and
/// always returns a planned candidate set only. Only `training_eligible`
/// admissions can flow through; audit-only/rejected records remain evidence.
pub fn outcome_admission_dry_run_candidates(
    admissions: &[Value],
    generated_at: u64,
    window_secs: u64,
    max_candidates: usize,
) -> Value {
    let mut training_eligible_count = 0usize;
    let mut skipped_non_training_eligible_count = 0usize;
    let mut skipped_unbuildable_count = 0usize;
    let mut skipped_duplicate_key_count = 0usize;
    let mut skipped_over_cap = 0usize;
    let mut seen_keys: BTreeSet<String> = BTreeSet::new();
    let mut candidates: Vec<Value> = Vec::new();

    for (admission_index, admission) in admissions.iter().enumerate() {
        let is_training_eligible = str_at(admission, &["admission", "class"])
            == Some("training_eligible")
            && admission
                .get("admission")
                .and_then(|v| v.get("eligible"))
                .and_then(Value::as_bool)
                == Some(true);
        if !is_training_eligible {
            skipped_non_training_eligible_count += 1;
            continue;
        }
        training_eligible_count += 1;

        let Some(outcome_record) = admission_to_outcome_record(admission, generated_at) else {
            skipped_unbuildable_count += 1;
            continue;
        };
        let Some(mem) =
            build_outcome_memory(&outcome_record, generated_at.min(i64::MAX as u64) as i64)
        else {
            skipped_unbuildable_count += 1;
            continue;
        };
        if !seen_keys.insert(mem.key.clone()) {
            skipped_duplicate_key_count += 1;
            continue;
        }
        if candidates.len() >= max_candidates {
            skipped_over_cap += 1;
            continue;
        }

        candidates.push(json!({
            "admission_index": admission_index,
            "present_artifact_id": outcome_record.get("artifact_id").cloned().unwrap_or(Value::Null),
            "dry_run": true,
            "write_allowed": false,
            "memory": {
                "key": mem.key,
                "kind": mem.kind,
                "scope": mem.scope,
                "tags": mem.tags,
                "content": mem.content,
                "related_keys": mem.related_keys,
                "importance": mem.importance,
            },
            "outcome_record": outcome_record,
            "source": admission.get("source").cloned().unwrap_or(Value::Null),
            "expression": admission.get("expression").cloned().unwrap_or(Value::Null),
            "admission": admission.get("admission").cloned().unwrap_or(Value::Null),
        }));
    }

    json!({
        "schema": LSWR_OUTCOME_ADMISSION_DRY_RUN_SCHEMA,
        "dry_run": true,
        "writes_state": false,
        "generated_at": generated_at,
        "window_secs": window_secs,
        "admission_count": admissions.len(),
        "training_eligible_count": training_eligible_count,
        "candidate_count": candidates.len(),
        "skipped_non_training_eligible_count": skipped_non_training_eligible_count,
        "skipped_unbuildable_count": skipped_unbuildable_count,
        "skipped_duplicate_key_count": skipped_duplicate_key_count,
        "skipped_over_cap": skipped_over_cap,
        "max_candidates": max_candidates,
        "memory_kind": OUTCOME_MEMORY_KIND,
        "note": "dry-run only: planned #94-compatible present_outcome memory rows from training_eligible LSWR admissions; no store writes, no present_outcomes_ingest call.",
        "candidates": candidates,
    })
}

/// Step E4b/E4c read-only approval packet over an E3 dry-run result.
///
/// This is intentionally not a writer. It canonicalizes the E3 would-write
/// candidate rows, computes a stable review hash, and marks every row as
/// requiring explicit review. The optional `active_rows` set is produced by a
/// non-mutating keyed probe in the MCP wrapper; when absent, the active-row
/// status is reported as unknown rather than guessed.
pub fn outcome_admission_ingest_plan_from_dry_run(
    dry_run: &Value,
    generated_at: u64,
    active_rows: Option<&BTreeSet<String>>,
) -> Value {
    let mut rows: Vec<Value> = dry_run
        .get("candidates")
        .and_then(Value::as_array)
        .into_iter()
        .flatten()
        .filter_map(|candidate| canonical_ingest_plan_row(candidate, active_rows))
        .collect();

    rows.sort_by(|a, b| {
        let ak = str_at(a, &["key"]).unwrap_or("");
        let bk = str_at(b, &["key"]).unwrap_or("");
        ak.cmp(bk)
    });

    let candidate_keys: Vec<Value> = rows
        .iter()
        .filter_map(|row| str_at(row, &["key"]).map(|key| Value::String(key.to_string())))
        .collect();
    let skipped_unkeyed_candidate_count = dry_run
        .get("candidates")
        .and_then(Value::as_array)
        .map(|candidates| candidates.len().saturating_sub(rows.len()))
        .unwrap_or(0);
    let active_row_known_count = rows
        .iter()
        .filter(|row| row.get("active_row_exists").is_some_and(|v| v.is_boolean()))
        .count();
    let active_row_exists_count = rows
        .iter()
        .filter(|row| row.get("active_row_exists").and_then(Value::as_bool) == Some(true))
        .count();
    let plan_hash = outcome_admission_ingest_plan_hash(&rows);

    json!({
        "schema": LSWR_OUTCOME_ADMISSION_INGEST_PLAN_SCHEMA,
        "dry_run": true,
        "writes_state": false,
        "generated_at": generated_at,
        "window_secs": dry_run.get("window_secs").cloned().unwrap_or(Value::Null),
        "source_schema": dry_run.get("schema").cloned().unwrap_or(Value::Null),
        "source_candidate_count": dry_run.get("candidate_count").cloned().unwrap_or(Value::Null),
        "candidate_count": rows.len(),
        "candidate_keys": candidate_keys,
        "skipped_unkeyed_candidate_count": skipped_unkeyed_candidate_count,
        "active_row_check": if active_rows.is_some() { "checked" } else { "not_checked" },
        "active_row_known_count": active_row_known_count,
        "active_row_exists_count": active_row_exists_count,
        "plan_hash_algorithm": "sha256",
        "plan_hash_scope": "canonical_e4_ingest_plan_rows_v0",
        "plan_hash": plan_hash,
        "requires_owner_review": true,
        "write_tool_open": false,
        "future_write_tool": "lswr_outcome_admissions_ingest",
        "note": "read-only E4 approval packet: no store writes, no dry_run=false switch, no present_outcomes_ingest call.",
        "rows": rows,
    })
}

pub fn outcome_admission_ingest_plan_hash(rows: &[Value]) -> String {
    let canonical = serde_json::to_vec(&Value::Array(rows.to_vec())).unwrap_or_default();
    let digest = Sha256::digest(canonical);
    format!("sha256:{digest:x}")
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

fn artifact_rejection(artifact: &ArtifactInfo, reason: &str) -> Value {
    json!({
        "schema": LSWR_OUTCOME_ADMISSION_SCHEMA,
        "source": {
            "present_artifact_id": artifact.id,
            "world_tool": Value::Null,
            "world_verdict": Value::Null,
            "world_reason": Value::Null,
            "verified_to": Value::Null,
            "verify_method": Value::Null,
        },
        "expression": {
            "verify_status": Value::Null,
            "embody_status": Value::Null,
            "interactive_status": Value::Null,
            "decision": Value::Null,
            "token_match": Value::Null,
        },
        "admission": {
            "class": LswrAdmissionClass::Rejected.as_str(),
            "eligible": false,
            "reason": reason,
        },
        "memory": {
            "write_allowed": false,
            "dry_run_required": true,
            "target_kind": OUTCOME_MEMORY_KIND,
        },
        "artifact": {
            "id": artifact.id,
            "artifact_path": artifact.artifact_path,
            "kind": artifact.kind,
            "ts": artifact.ts,
            "bytes": artifact.bytes,
            "dual_encoding": artifact.dual_encoding,
            "has_screenshot": artifact.has_screenshot,
            "expression_source": "none",
        },
    })
}

fn canonical_ingest_plan_row(
    candidate: &Value,
    active_rows: Option<&BTreeSet<String>>,
) -> Option<Value> {
    let key = str_at(candidate, &["memory", "key"])?;
    let active_row_exists = active_rows
        .map(|rows| Value::Bool(rows.contains(key)))
        .unwrap_or(Value::Null);

    Some(json!({
        "key": key,
        "kind": str_at(candidate, &["memory", "kind"]),
        "scope": str_at(candidate, &["memory", "scope"]),
        "present_artifact_id": candidate.get("present_artifact_id").cloned().unwrap_or(Value::Null),
        "active_row_exists": active_row_exists,
        "write_allowed": false,
        "requires_review": true,
        "memory": candidate.get("memory").cloned().unwrap_or(Value::Null),
        "outcome_record": candidate.get("outcome_record").cloned().unwrap_or(Value::Null),
        "source": candidate.get("source").cloned().unwrap_or(Value::Null),
        "expression": candidate.get("expression").cloned().unwrap_or(Value::Null),
        "admission": candidate.get("admission").cloned().unwrap_or(Value::Null),
    }))
}

fn admission_to_outcome_record(admission: &Value, generated_at: u64) -> Option<Value> {
    if str_at(admission, &["admission", "reason"]) != Some("eligible") {
        return None;
    }
    if str_at(admission, &["source", "world_verdict"]) != Some("verified") {
        return None;
    }
    if str_at(admission, &["source", "world_reason"]).is_some() {
        return None;
    }
    if str_at(admission, &["expression", "verify_status"]) != Some("rendered_ok") {
        return None;
    }

    let artifact_id = first_str(
        admission,
        &[&["artifact", "id"], &["source", "present_artifact_id"]],
    )?;
    let ts = admission
        .get("artifact")
        .and_then(|v| v.get("ts"))
        .and_then(Value::as_u64)
        .unwrap_or(generated_at);
    let world_tool = str_at(admission, &["source", "world_tool"])?;
    let verify_method = str_at(admission, &["source", "verify_method"])?;
    let verified_to = str_at(admission, &["source", "verified_to"])?;
    let intent = format!("LSWR training-eligible {world_tool} outcome verified to {verified_to}");

    Some(json!({
        "artifact_id": artifact_id,
        "ts": ts,
        "intent": intent,
        "action_tool": "lswr_outcome_admission",
        "kind": "lswr_world_outcome",
        "verify_status": "rendered_ok",
        "verify_method": verify_method,
        "embody_status": str_at(admission, &["expression", "embody_status"]).unwrap_or("not_applicable"),
        "interactive_status": str_at(admission, &["expression", "interactive_status"]).unwrap_or("not_applicable"),
        "decision": str_at(admission, &["expression", "decision"]),
        "token_match": admission
            .get("expression")
            .and_then(|v| v.get("token_match"))
            .and_then(Value::as_bool),
        "chain_head": str_at(admission, &["expression", "chain_head"]),
        "verified_to": verified_to,
        "not_verified": Value::Null,
        "lswr": {
            "world_tool": str_at(admission, &["source", "world_tool"]),
            "world_verdict": str_at(admission, &["source", "world_verdict"]),
            "world_reason": str_at(admission, &["source", "world_reason"]),
            "admission_reason": str_at(admission, &["admission", "reason"]),
        },
    }))
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

fn str_at_value<'a>(value: Option<&'a Value>, path: &[&str]) -> Option<&'a str> {
    value.and_then(|v| str_at(v, path))
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

fn expression_record_for_artifact(artifact: &ArtifactInfo, artifact_path: &Path) -> Value {
    if let Some(record) = read_expression_sidecar(&artifact.id, artifact_path) {
        return normalize_expression_record(artifact, record, "outcome_sidecar");
    }
    normalize_expression_record(
        artifact,
        json!({
            "artifact_id": artifact.id,
            "present_artifact_id": artifact.id,
            "verify_status": "skipped",
            "embody_status": "not_applicable",
            "interactive_status": "not_applicable",
        }),
        "no_outcome_sidecar",
    )
}

fn read_expression_sidecar(id: &str, artifact_path: &Path) -> Option<Value> {
    let parent = artifact_path.parent()?;
    let path: PathBuf = parent.join(format!("{id}.{OUTCOME_SIDECAR_SUFFIX}"));
    let body = std::fs::read_to_string(path).ok()?;
    serde_json::from_str(&body).ok()
}

fn normalize_expression_record(artifact: &ArtifactInfo, mut record: Value, source: &str) -> Value {
    if !record.is_object() {
        record = json!({});
    }
    if let Some(obj) = record.as_object_mut() {
        obj.entry("artifact_id")
            .or_insert_with(|| json!(artifact.id));
        obj.entry("present_artifact_id")
            .or_insert_with(|| json!(artifact.id));
        obj.entry("expression_source")
            .or_insert_with(|| json!(source));
    }
    record
}

fn bump_reason(reasons: &mut BTreeMap<String, usize>, reason: &str) {
    *reasons.entry(reason.to_string()).or_insert(0) += 1;
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
        world_envelope_to_present_packet, PresentPacketOptions, WORLD_TOOL_SCHEMA,
    };
    use std::fs;

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

    fn artifact_info(id: &str, path: &Path) -> ArtifactInfo {
        ArtifactInfo {
            id: id.to_string(),
            artifact_path: path.display().to_string(),
            kind: Some("html".to_string()),
            ts: Some(1_780_000_000),
            generated_by: Some(crate::present::PRESENT_SCHEMA.to_string()),
            session_id: None,
            dual_encoding: true,
            has_screenshot: false,
            bytes: fs::metadata(path).map(|m| m.len()).unwrap_or(0),
        }
    }

    fn temp_dir(name: &str) -> std::path::PathBuf {
        std::env::temp_dir().join(format!(
            "ab-lswr-outcome-admission-{name}-{}-{}",
            std::process::id(),
            crate::present::now_unix()
        ))
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

    fn write_html_artifact(dir: &Path, id: &str, packet: &Value) -> std::path::PathBuf {
        fs::create_dir_all(dir).expect("mkdir");
        let html = crate::present::build_html(
            crate::present::PresentKind::Html,
            "<article>LSWR review</article>",
            Some("LSWR review"),
            Some(packet),
            Some(&json!({
                "source_tool": "lswr_present",
                "source_schema": packet.get("schema").cloned().unwrap_or(Value::Null),
                "kind": "html",
                "ts": 1_780_000_000u64,
            })),
        );
        let path = dir.join(format!("{id}.html"));
        fs::write(&path, html).expect("write html");
        path
    }

    fn write_outcome_sidecar(dir: &Path, id: &str, mut record: Value) {
        if let Some(obj) = record.as_object_mut() {
            obj.entry("artifact_id").or_insert_with(|| json!(id));
        }
        let path = dir.join(format!("{id}.{OUTCOME_SIDECAR_SUFFIX}"));
        fs::write(path, serde_json::to_string(&record).expect("json")).expect("write sidecar");
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

    #[test]
    fn projection_counts_training_audit_rejected_and_skips_non_lswr() {
        let dir = temp_dir("projection-matrix");
        let eligible_path = write_html_artifact(&dir, "eligible", &verified_patch_packet());
        write_outcome_sidecar(&dir, "eligible", expression());

        let audit_path = write_html_artifact(&dir, "audit", &expected_effect_failure_packet());
        write_outcome_sidecar(&dir, "audit", expression());

        let no_sidecar_path = write_html_artifact(&dir, "no_sidecar", &verified_patch_packet());

        let mismatch_packet = verified_patch_packet();
        let mismatch_path = write_html_artifact(&dir, "mismatch", &mismatch_packet);
        write_outcome_sidecar(
            &dir,
            "mismatch",
            json!({
                "verify_status": "rendered_ok",
                "token_match": false,
            }),
        );

        let non_lswr_html = crate::present::build_html(
            crate::present::PresentKind::Html,
            "<p>ordinary present artifact</p>",
            Some("ordinary"),
            Some(&json!({"schema": "ordinary"})),
            Some(&json!({"source_tool": "present", "kind": "html"})),
        );
        let non_lswr_path = dir.join("ordinary.html");
        fs::write(&non_lswr_path, non_lswr_html).expect("write non-lswr");

        let artifacts = vec![
            artifact_info("eligible", &eligible_path),
            artifact_info("audit", &audit_path),
            artifact_info("no_sidecar", &no_sidecar_path),
            artifact_info("mismatch", &mismatch_path),
            artifact_info("ordinary", &non_lswr_path),
        ];
        let projection = outcome_admissions_projection(&artifacts, false, 1_780_000_010, 86_400);

        assert_eq!(
            projection["schema"],
            LSWR_OUTCOME_ADMISSIONS_PROJECTION_SCHEMA
        );
        assert_eq!(projection["scanned_artifacts"], json!(5));
        assert_eq!(projection["skipped_non_lswr_count"], json!(1));
        assert_eq!(projection["lswr_artifact_count"], json!(4));
        assert_eq!(projection["training_eligible_count"], json!(1));
        assert_eq!(projection["audit_only_count"], json!(2));
        assert_eq!(projection["rejected_count"], json!(1));
        assert_eq!(projection["reason_counts"]["eligible"], json!(1));
        assert_eq!(
            projection["reason_counts"]["source_world_not_verified"],
            json!(1)
        );
        assert_eq!(
            projection["reason_counts"]["expression_not_rendered_ok"],
            json!(1)
        );
        assert_eq!(projection["reason_counts"]["token_mismatch"], json!(1));
        assert_eq!(projection["admissions"].as_array().unwrap().len(), 4);

        let eligible_only = outcome_admissions_projection(&artifacts, true, 1_780_000_010, 86_400);
        assert_eq!(eligible_only["admissions"].as_array().unwrap().len(), 1);
        assert_eq!(
            eligible_only["admissions"][0]["admission"]["class"],
            "training_eligible"
        );

        let _ = fs::remove_dir_all(&dir);
    }

    #[test]
    fn projection_marks_lswr_artifact_without_payload_rejected() {
        let dir = temp_dir("missing-payload");
        fs::create_dir_all(&dir).expect("mkdir");
        let html = crate::present::build_html(
            crate::present::PresentKind::Html,
            "<article>payload missing</article>",
            Some("LSWR missing payload"),
            None,
            Some(&json!({
                "source_tool": "lswr_present",
                "kind": "html",
                "ts": 1_780_000_000u64,
            })),
        );
        let path = dir.join("missing.html");
        fs::write(&path, html).expect("write");

        let projection =
            outcome_admissions_projection(&[artifact_info("missing", &path)], false, 1, 60);

        assert_eq!(projection["lswr_artifact_count"], json!(1));
        assert_eq!(projection["rejected_count"], json!(1));
        assert_eq!(
            projection["reason_counts"]["dual_payload_missing"],
            json!(1)
        );
        assert_eq!(
            projection["admissions"][0]["admission"]["reason"],
            "dual_payload_missing"
        );

        let _ = fs::remove_dir_all(&dir);
    }

    #[test]
    fn dry_run_candidates_build_present_outcome_row_for_training_eligible_admission() {
        let packet = verified_patch_packet();
        let admission = classify_outcome_admission(&packet, &expression(), Some(&packet));
        let dry_run = outcome_admission_dry_run_candidates(&[admission], 1_780_000_020, 86_400, 25);

        assert_eq!(dry_run["schema"], LSWR_OUTCOME_ADMISSION_DRY_RUN_SCHEMA);
        assert_eq!(dry_run["dry_run"], true);
        assert_eq!(dry_run["writes_state"], false);
        assert_eq!(dry_run["admission_count"], json!(1));
        assert_eq!(dry_run["training_eligible_count"], json!(1));
        assert_eq!(dry_run["candidate_count"], json!(1));
        assert_eq!(dry_run["memory_kind"], OUTCOME_MEMORY_KIND);

        let candidate = &dry_run["candidates"][0];
        assert_eq!(candidate["present_artifact_id"], "ab_step_e_fixture");
        assert_eq!(candidate["write_allowed"], false);
        assert_eq!(candidate["memory"]["key"], "outcome_ab_step_e_fixture");
        assert_eq!(candidate["memory"]["kind"], OUTCOME_MEMORY_KIND);
        assert_eq!(candidate["memory"]["scope"], "outcome:ab_step_e_fixture");
        assert!(candidate["memory"]["content"]
            .as_str()
            .unwrap()
            .contains("\"action_tool\": \"lswr_outcome_admission\""));
        assert_eq!(
            candidate["outcome_record"]["action_tool"],
            "lswr_outcome_admission"
        );
        assert_eq!(candidate["outcome_record"]["kind"], "lswr_world_outcome");
        assert_eq!(
            candidate["outcome_record"]["verified_to"],
            "onsen_live_root_viewport"
        );
        let tags = candidate["memory"]["tags"].as_array().unwrap();
        assert!(tags.iter().any(|v| v == "present_outcome"));
        assert!(tags.iter().any(|v| v == "verified_outcome"));
        assert!(tags.iter().any(|v| v == "auto_ingested"));
        assert!(tags.iter().any(|v| v == "verify:rendered_ok"));
    }

    #[test]
    fn dry_run_candidates_skip_audit_only_and_rejected_admissions() {
        let audit_packet = expected_effect_failure_packet();
        let audit = classify_outcome_admission(&audit_packet, &expression(), Some(&audit_packet));

        let reject_packet = verified_patch_packet();
        let mut reject_expr = expression();
        reject_expr["token_match"] = json!(false);
        let rejected =
            classify_outcome_admission(&reject_packet, &reject_expr, Some(&reject_packet));

        let dry_run =
            outcome_admission_dry_run_candidates(&[audit, rejected], 1_780_000_020, 86_400, 25);

        assert_eq!(dry_run["candidate_count"], json!(0));
        assert_eq!(dry_run["training_eligible_count"], json!(0));
        assert_eq!(dry_run["skipped_non_training_eligible_count"], json!(2));
        assert_eq!(dry_run["skipped_unbuildable_count"], json!(0));
        assert_eq!(dry_run["candidates"].as_array().unwrap().len(), 0);
    }

    #[test]
    fn dry_run_candidates_refuse_laundered_training_eligible_axes() {
        let packet = verified_patch_packet();
        let mut admission = classify_outcome_admission(&packet, &expression(), Some(&packet));
        admission["expression"]["verify_status"] = json!("blank");

        let dry_run = outcome_admission_dry_run_candidates(&[admission], 1_780_000_020, 86_400, 25);

        assert_eq!(dry_run["training_eligible_count"], json!(1));
        assert_eq!(dry_run["candidate_count"], json!(0));
        assert_eq!(dry_run["skipped_unbuildable_count"], json!(1));
        assert_eq!(dry_run["candidates"].as_array().unwrap().len(), 0);
    }

    #[test]
    fn dry_run_candidates_dedupe_keys_and_respect_cap() {
        let packet = verified_patch_packet();

        let mut expr_a = expression();
        expr_a["present_artifact_id"] = json!("admission_a");
        expr_a["artifact_id"] = json!("admission_a");
        let first = classify_outcome_admission(&packet, &expr_a, Some(&packet));
        let duplicate = classify_outcome_admission(&packet, &expr_a, Some(&packet));

        let mut expr_b = expression();
        expr_b["present_artifact_id"] = json!("admission_b");
        expr_b["artifact_id"] = json!("admission_b");
        let capped = classify_outcome_admission(&packet, &expr_b, Some(&packet));

        let dry_run = outcome_admission_dry_run_candidates(
            &[first, duplicate, capped],
            1_780_000_020,
            86_400,
            1,
        );

        assert_eq!(dry_run["training_eligible_count"], json!(3));
        assert_eq!(dry_run["candidate_count"], json!(1));
        assert_eq!(dry_run["skipped_duplicate_key_count"], json!(1));
        assert_eq!(dry_run["skipped_over_cap"], json!(1));
        assert_eq!(
            dry_run["candidates"][0]["memory"]["key"],
            "outcome_admission_a"
        );
    }

    #[test]
    fn ingest_plan_hash_is_stable_across_candidate_order() {
        let packet = verified_patch_packet();

        let mut expr_a = expression();
        expr_a["present_artifact_id"] = json!("admission_a");
        expr_a["artifact_id"] = json!("admission_a");
        let admission_a = classify_outcome_admission(&packet, &expr_a, Some(&packet));

        let mut expr_b = expression();
        expr_b["present_artifact_id"] = json!("admission_b");
        expr_b["artifact_id"] = json!("admission_b");
        let admission_b = classify_outcome_admission(&packet, &expr_b, Some(&packet));

        let dry_ab = outcome_admission_dry_run_candidates(
            &[admission_a.clone(), admission_b.clone()],
            1_780_000_020,
            86_400,
            25,
        );
        let dry_ba = outcome_admission_dry_run_candidates(
            &[admission_b, admission_a],
            1_780_000_020,
            86_400,
            25,
        );

        let plan_ab = outcome_admission_ingest_plan_from_dry_run(&dry_ab, 1_780_000_030, None);
        let plan_ba = outcome_admission_ingest_plan_from_dry_run(&dry_ba, 1_780_000_031, None);

        assert_eq!(plan_ab["schema"], LSWR_OUTCOME_ADMISSION_INGEST_PLAN_SCHEMA);
        assert_eq!(plan_ab["dry_run"], true);
        assert_eq!(plan_ab["writes_state"], false);
        assert_eq!(plan_ab["write_tool_open"], false);
        assert_eq!(plan_ab["candidate_count"], json!(2));
        assert_eq!(plan_ab["plan_hash"], plan_ba["plan_hash"]);
        assert!(plan_ab["plan_hash"]
            .as_str()
            .unwrap()
            .starts_with("sha256:"));
        assert_eq!(plan_ab["rows"][0]["key"], "outcome_admission_a");
        assert_eq!(plan_ab["rows"][1]["key"], "outcome_admission_b");
    }

    #[test]
    fn ingest_plan_hash_changes_when_reviewed_row_changes() {
        let packet = verified_patch_packet();
        let admission = classify_outcome_admission(&packet, &expression(), Some(&packet));
        let dry_run = outcome_admission_dry_run_candidates(&[admission], 1_780_000_020, 86_400, 25);
        let original = outcome_admission_ingest_plan_from_dry_run(&dry_run, 1_780_000_030, None);

        let mut tampered = dry_run.clone();
        tampered["candidates"][0]["memory"]["content"] = json!("changed content");
        let changed = outcome_admission_ingest_plan_from_dry_run(&tampered, 1_780_000_031, None);

        assert_ne!(original["plan_hash"], changed["plan_hash"]);
    }

    #[test]
    fn ingest_plan_records_active_row_state_without_write_permission() {
        let packet = verified_patch_packet();
        let admission = classify_outcome_admission(&packet, &expression(), Some(&packet));
        let dry_run = outcome_admission_dry_run_candidates(&[admission], 1_780_000_020, 86_400, 25);
        let active_rows = BTreeSet::from(["outcome_ab_step_e_fixture".to_string()]);
        let plan =
            outcome_admission_ingest_plan_from_dry_run(&dry_run, 1_780_000_030, Some(&active_rows));

        assert_eq!(plan["active_row_check"], "checked");
        assert_eq!(plan["active_row_known_count"], json!(1));
        assert_eq!(plan["active_row_exists_count"], json!(1));
        assert_eq!(plan["rows"][0]["active_row_exists"], true);
        assert_eq!(plan["rows"][0]["write_allowed"], false);
        assert_eq!(plan["rows"][0]["requires_review"], true);
    }
}
