use super::*;
use ab_browser::BrowserBackend;
use std::{
    collections::BTreeMap,
    fs,
    io::Write,
    os::unix::fs::{OpenOptionsExt, PermissionsExt},
    path::Path,
    sync::OnceLock,
};

const PROVIDER_ID: &str = "modelscope.studio.amap_cvlab.abot-world-0";
const BASE_URL: &str = "https://amap-cvlab-abot-world-0.ms.show";
const ENABLE_ENV: &str = "AB_MODELSCOPE_ABOT_RUNTIME_ENABLE";
const MIN_OBSERVE_MS: u64 = 5_000;
const MAX_OBSERVE_MS: u64 = 60_000;
const DEFAULT_OBSERVE_MS: u64 = 30_000;
const MAX_PROMPT_CHARS: usize = 4_000;
const MAX_REQUEST_ID_CHARS: usize = 128;
const TASK_SCHEMA: &str = "agent_bridge.modelscope_abot_task.v0";
const STUDIO_PROMPT_SELECTOR: &str = "textarea";
const STUDIO_READY_TIMEOUT_MS: u64 = 45_000;
const STUDIO_START_TIMEOUT_MS: u64 = 20_000;
const MAX_PROVIDER_TASK_SCAN: usize = 256;
const MAX_FAILURE_DIAGNOSTIC_FRAMES: usize = 16;
const MAX_RECEIPT_AUDIT_DOCUMENTS: usize = 256;
const PROVIDER_COOLDOWN_STEPS_MS: &[u64] = &[5 * 60_000, 15 * 60_000, 30 * 60_000, 60 * 60_000];

static SESSION_LOCK: OnceLock<tokio::sync::Mutex<()>> = OnceLock::new();
static TASK_LOCK: OnceLock<tokio::sync::Mutex<()>> = OnceLock::new();
static PROCESS_INSTANCE_ID: OnceLock<String> = OnceLock::new();

#[derive(Debug, Clone)]
struct RunRequest {
    prompt: String,
    prompt_sha256: String,
    observe_ms: u64,
}

#[derive(Debug)]
struct RunFailure {
    message: String,
    diagnostics: Option<Value>,
}

impl RunFailure {
    fn new(message: impl Into<String>) -> Self {
        Self {
            message: message.into(),
            diagnostics: None,
        }
    }

    fn with_diagnostics(message: impl Into<String>, diagnostics: Value) -> Self {
        Self {
            message: message.into(),
            diagnostics: Some(diagnostics),
        }
    }
}

fn attach_verified_prompt_binding(failure: &mut RunFailure, prompt_binding: Value) {
    match failure.diagnostics.take() {
        Some(mut diagnostics) if diagnostics.is_object() => {
            diagnostics["prompt_binding"] = prompt_binding;
            failure.diagnostics = Some(diagnostics);
        }
        Some(diagnostics) => {
            failure.diagnostics = Some(json!({
                "schema": "agent_bridge.modelscope_abot_downstream_failure.v0",
                "prompt_binding": prompt_binding,
                "downstream_diagnostics": diagnostics,
            }));
        }
        None => {
            failure.diagnostics = Some(json!({
                "schema": "agent_bridge.modelscope_abot_downstream_failure.v0",
                "prompt_binding": prompt_binding,
                "downstream_diagnostics": Value::Null,
            }));
        }
    }
}

fn lowercase_sha256(value: Option<&Value>) -> bool {
    value.and_then(Value::as_str).is_some_and(|value| {
        value.len() == 64
            && value
                .chars()
                .all(|character| character.is_ascii_hexdigit() && !character.is_ascii_uppercase())
    })
}

fn contains_raw_prompt_field(value: &Value) -> bool {
    match value {
        Value::Object(object) => object.iter().any(|(key, value)| {
            matches!(key.as_str(), "prompt" | "raw_prompt" | "prompt_text")
                || contains_raw_prompt_field(value)
        }),
        Value::Array(values) => values.iter().any(contains_raw_prompt_field),
        _ => false,
    }
}

fn validate_prompt_binding(binding: Option<&Value>, violations: &mut Vec<&'static str>) {
    let Some(binding) = binding.filter(|value| value.is_object()) else {
        violations.push("prompt_binding_missing");
        return;
    };
    if binding.get("schema").and_then(Value::as_str)
        != Some("agent_bridge.modelscope_abot_prompt_binding.v0")
    {
        violations.push("prompt_binding_schema_mismatch");
    }
    if binding.get("readback_observed").and_then(Value::as_bool) != Some(true) {
        violations.push("prompt_readback_not_observed");
    }
    if binding.get("exact_match").and_then(Value::as_bool) != Some(true) {
        violations.push("prompt_exact_match_not_verified");
    }
    if binding.get("raw_prompt_recorded").and_then(Value::as_bool) != Some(false) {
        violations.push("raw_prompt_recording_boundary_violated");
    }
    let observed = binding.get("observed_sha256");
    let expected = binding.get("expected_sha256");
    if !lowercase_sha256(observed) || !lowercase_sha256(expected) {
        violations.push("prompt_sha256_invalid");
    } else if observed != expected {
        violations.push("prompt_sha256_mismatch");
    }
}

fn validate_abot_receipt(document: &Value) -> Value {
    if contains_raw_prompt_field(document) {
        return validation_projection("unknown", vec!["raw_prompt_field_present"]);
    }
    let schema = document.get("schema").and_then(Value::as_str);
    let (document_kind, binding) = match schema {
        Some("agent_bridge.modelscope_abot_run_once_receipt.v1") => {
            let mut violations = Vec::new();
            if document.get("status").and_then(Value::as_str) != Some("completed") {
                violations.push("run_status_not_completed");
            }
            if document.get("lifecycle_closed").and_then(Value::as_bool) != Some(true) {
                violations.push("runtime_lifecycle_not_closed");
            }
            let binding = document.get("binding");
            if binding
                .and_then(|value| value.get("status"))
                .and_then(Value::as_str)
                != Some("submission_bound_output_unverified")
            {
                violations.push("binding_status_mismatch");
            }
            if binding
                .and_then(|value| value.get("world_semantics_verified"))
                .and_then(Value::as_bool)
                != Some(false)
            {
                violations.push("world_semantics_claim_exceeds_evidence");
            }
            validate_prompt_binding(
                binding.and_then(|value| value.get("prompt_submission")),
                &mut violations,
            );
            let run_prompt_sha256 = document.get("prompt_sha256");
            let bound_prompt_sha256 = binding
                .and_then(|value| value.get("prompt_submission"))
                .and_then(|value| value.get("expected_sha256"));
            if !lowercase_sha256(run_prompt_sha256) {
                violations.push("run_prompt_sha256_invalid");
            } else if run_prompt_sha256 != bound_prompt_sha256 {
                violations.push("run_prompt_sha256_mismatch");
            }
            return validation_projection("success_receipt", violations);
        }
        Some("agent_bridge.modelscope_abot_prompt_binding_failure.v0") => {
            ("prompt_binding_failure", document.get("prompt_binding"))
        }
        Some("agent_bridge.modelscope_abot_downstream_failure.v0") => {
            ("downstream_failure", document.get("prompt_binding"))
        }
        Some("agent_bridge.modelscope_abot_failure_diagnostics.v1") => {
            ("downstream_failure", document.get("prompt_binding"))
        }
        _ => {
            return validation_projection("unknown", vec!["unsupported_document_schema"]);
        }
    };
    let mut violations = Vec::new();
    validate_prompt_binding(binding, &mut violations);
    validation_projection(document_kind, violations)
}

fn canonical_json_sha256(value: &Value) -> String {
    let canonical = serde_json_canonicalizer::to_vec(value)
        .expect("serde_json::Value always has a valid JCS representation");
    format!("{:x}", Sha256::digest(canonical))
}

fn audit_abot_receipts(documents: &[Value]) -> Value {
    let mut accepted = 0_u64;
    let mut document_kinds = BTreeMap::<String, u64>::new();
    let mut violation_counts = BTreeMap::<String, u64>::new();
    let document_sha256 = documents
        .iter()
        .map(canonical_json_sha256)
        .collect::<Vec<_>>();
    let results = documents
        .iter()
        .enumerate()
        .map(|(index, document)| {
            let validation = validate_abot_receipt(document);
            let status = validation["status"].as_str().unwrap_or("rejected");
            let document_kind = validation["document_kind"].as_str().unwrap_or("unknown");
            *document_kinds.entry(document_kind.to_string()).or_default() += 1;
            if status == "accepted" {
                accepted += 1;
            }
            if let Some(violations) = validation["violations"].as_array() {
                for violation in violations.iter().filter_map(Value::as_str) {
                    *violation_counts.entry(violation.to_string()).or_default() += 1;
                }
            }
            json!({
                "index": index,
                "status": status,
                "document_kind": document_kind,
                "violations": validation["violations"],
            })
        })
        .collect::<Vec<_>>();
    let total = documents.len() as u64;
    let rejected = total.saturating_sub(accepted);
    let evidence_manifest = json!({
        "schema": "agent_bridge.modelscope_abot_receipt_audit_evidence.v0",
        "document_sha256": document_sha256,
    });
    let batch_sha256 = canonical_json_sha256(&evidence_manifest);

    json!({
        "schema": "agent_bridge.modelscope_abot_receipt_audit.v0",
        "status": if rejected == 0 { "accepted" } else { "rejected" },
        "summary": {
            "total": total,
            "accepted": accepted,
            "rejected": rejected,
            "document_kinds": document_kinds,
            "violation_counts": violation_counts,
        },
        "results": results,
        "evidence_binding": {
            "schema": "agent_bridge.modelscope_abot_receipt_audit_evidence.v0",
            "canonicalization": "rfc8785.jcs.v1",
            "documents": evidence_manifest["document_sha256"]
                .as_array()
                .expect("evidence manifest document list")
                .iter()
                .enumerate()
                .map(|(index, sha256)| json!({"index": index, "sha256": sha256}))
                .collect::<Vec<_>>(),
            "batch_sha256": batch_sha256,
        },
        "claims": {
            "all_prompt_submissions_bound": total > 0 && rejected == 0,
            "world_semantics_verified": false,
        },
        "runtime_effects": {
            "network_request_sent": false,
            "browser_opened": false,
            "task_state_read": false,
            "task_state_written": false,
        },
    })
}

fn verify_audit_evidence_binding(expected: &Value, actual: &Value) -> Value {
    let mut violations = Vec::<&'static str>::new();
    let Some(expected_object) = expected.as_object() else {
        return json!({
            "schema": "agent_bridge.modelscope_abot_receipt_audit_evidence_verification.v0",
            "status": "mismatch",
            "violations": ["evidence_binding_not_object"],
            "claims": {"audit_evidence_bound": false},
        });
    };

    if expected_object.len() != 4
        || !["schema", "canonicalization", "documents", "batch_sha256"]
            .iter()
            .all(|key| expected_object.contains_key(*key))
    {
        violations.push("evidence_binding_shape_mismatch");
    }
    if expected.get("schema") != actual.get("schema") {
        violations.push("evidence_schema_mismatch");
    }
    if expected.get("canonicalization") != actual.get("canonicalization") {
        violations.push("canonicalization_mismatch");
    }

    match (
        expected.get("documents").and_then(Value::as_array),
        actual.get("documents").and_then(Value::as_array),
    ) {
        (Some(expected_documents), Some(actual_documents)) => {
            if expected_documents.len() != actual_documents.len() {
                violations.push("document_count_mismatch");
            }
            if expected_documents != actual_documents {
                violations.push("document_manifest_mismatch");
            }
        }
        _ => violations.push("document_manifest_invalid"),
    }
    if expected.get("batch_sha256") != actual.get("batch_sha256") {
        violations.push("batch_sha256_mismatch");
    }

    let verified = violations.is_empty();
    json!({
        "schema": "agent_bridge.modelscope_abot_receipt_audit_evidence_verification.v0",
        "status": if verified { "verified" } else { "mismatch" },
        "violations": violations,
        "claims": {"audit_evidence_bound": verified},
    })
}

fn audit_chain_binding(evidence_binding: &Value, previous_chain_sha256: Option<&str>) -> Value {
    let audit_batch_sha256 = evidence_binding
        .get("batch_sha256")
        .and_then(Value::as_str)
        .expect("audit evidence binding batch digest");
    let chain_payload = json!({
        "schema": "agent_bridge.modelscope_abot_receipt_audit_chain_payload.v0",
        "previous_chain_sha256": previous_chain_sha256,
        "audit_batch_sha256": audit_batch_sha256,
    });

    json!({
        "schema": "agent_bridge.modelscope_abot_receipt_audit_chain.v0",
        "canonicalization": "rfc8785.jcs.v1",
        "previous_chain_sha256": previous_chain_sha256,
        "audit_batch_sha256": audit_batch_sha256,
        "chain_sha256": canonical_json_sha256(&chain_payload),
        "claims": {
            "chain_link_constructed": true,
            "external_custody_verified": false,
            "world_semantics_verified": false,
        },
    })
}

fn audit_chain_checkpoint(chain_sha256: &str, total_link_count: u64) -> Value {
    let payload = json!({
        "schema": "agent_bridge.modelscope_abot_receipt_audit_chain_checkpoint_payload.v0",
        "chain_sha256": chain_sha256,
        "total_link_count": total_link_count,
    });
    json!({
        "schema": "agent_bridge.modelscope_abot_receipt_audit_chain_checkpoint.v0",
        "canonicalization": "rfc8785.jcs.v1",
        "chain_sha256": chain_sha256,
        "total_link_count": total_link_count,
        "checkpoint_sha256": canonical_json_sha256(&payload),
        "claims": {
            "checkpoint_integrity_bound": true,
            "historical_source_documents_verified": false,
            "external_custody_verified": false,
            "world_semantics_verified": false,
        },
    })
}

fn verify_audit_chain_checkpoint(checkpoint: &Value) -> (Option<(&str, u64)>, Vec<Value>) {
    let mut violations = Vec::new();
    let Some(object) = checkpoint.as_object() else {
        return (
            None,
            vec![json!({"index": 0, "code": "chain_checkpoint_not_object"})],
        );
    };
    if object.len() != 6
        || ![
            "schema",
            "canonicalization",
            "chain_sha256",
            "total_link_count",
            "checkpoint_sha256",
            "claims",
        ]
        .iter()
        .all(|key| object.contains_key(*key))
    {
        violations.push(json!({"index": 0, "code": "chain_checkpoint_shape_mismatch"}));
    }
    if checkpoint.get("schema").and_then(Value::as_str)
        != Some("agent_bridge.modelscope_abot_receipt_audit_chain_checkpoint.v0")
    {
        violations.push(json!({"index": 0, "code": "chain_checkpoint_schema_mismatch"}));
    }
    if checkpoint.get("canonicalization").and_then(Value::as_str) != Some("rfc8785.jcs.v1") {
        violations.push(json!({"index": 0, "code": "chain_checkpoint_canonicalization_mismatch"}));
    }
    let chain_sha256 = checkpoint
        .get("chain_sha256")
        .filter(|value| lowercase_sha256(Some(value)))
        .and_then(Value::as_str);
    if chain_sha256.is_none() {
        violations.push(json!({"index": 0, "code": "chain_checkpoint_chain_sha256_invalid"}));
    }
    let total_link_count = checkpoint
        .get("total_link_count")
        .and_then(Value::as_u64)
        .filter(|count| *count > 0);
    if total_link_count.is_none() {
        violations.push(json!({"index": 0, "code": "chain_checkpoint_total_link_count_invalid"}));
    }
    let checkpoint_sha256 = checkpoint
        .get("checkpoint_sha256")
        .filter(|value| lowercase_sha256(Some(value)))
        .and_then(Value::as_str);
    if checkpoint_sha256.is_none() {
        violations.push(json!({"index": 0, "code": "chain_checkpoint_sha256_invalid"}));
    }
    if checkpoint.get("claims")
        != Some(&json!({
            "checkpoint_integrity_bound": true,
            "historical_source_documents_verified": false,
            "external_custody_verified": false,
            "world_semantics_verified": false,
        }))
    {
        violations.push(json!({"index": 0, "code": "chain_checkpoint_claims_mismatch"}));
    }
    if let (Some(chain_sha256), Some(total_link_count), Some(checkpoint_sha256)) =
        (chain_sha256, total_link_count, checkpoint_sha256)
    {
        let payload = json!({
            "schema": "agent_bridge.modelscope_abot_receipt_audit_chain_checkpoint_payload.v0",
            "chain_sha256": chain_sha256,
            "total_link_count": total_link_count,
        });
        if canonical_json_sha256(&payload) != checkpoint_sha256 {
            violations.push(json!({"index": 0, "code": "chain_checkpoint_sha256_mismatch"}));
        }
    }
    (
        chain_sha256
            .zip(total_link_count)
            .filter(|_| violations.is_empty()),
        violations,
    )
}

fn verify_audit_chain_history(
    history: &[Value],
    current: &Value,
    checkpoint: Option<&Value>,
) -> Value {
    let mut violations = Vec::<Value>::new();
    let mut previous_head: Option<&str> = None;
    let mut checkpoint_link_count = None;

    if let Some(checkpoint) = checkpoint {
        let (verified_checkpoint, checkpoint_violations) =
            verify_audit_chain_checkpoint(checkpoint);
        violations.extend(checkpoint_violations);
        if let Some((checkpoint_head, total_link_count)) = verified_checkpoint {
            checkpoint_link_count = Some(total_link_count);
            previous_head = Some(checkpoint_head);
        }
    }

    for (index, link) in history.iter().enumerate() {
        let Some(object) = link.as_object() else {
            violations.push(json!({"index": index, "code": "chain_link_not_object"}));
            previous_head = None;
            continue;
        };
        if object.len() != 6
            || ![
                "schema",
                "canonicalization",
                "previous_chain_sha256",
                "audit_batch_sha256",
                "chain_sha256",
                "claims",
            ]
            .iter()
            .all(|key| object.contains_key(*key))
        {
            violations.push(json!({"index": index, "code": "chain_link_shape_mismatch"}));
        }
        if link.get("schema").and_then(Value::as_str)
            != Some("agent_bridge.modelscope_abot_receipt_audit_chain.v0")
        {
            violations.push(json!({"index": index, "code": "chain_schema_mismatch"}));
        }
        if link.get("canonicalization").and_then(Value::as_str) != Some("rfc8785.jcs.v1") {
            violations.push(json!({"index": index, "code": "canonicalization_mismatch"}));
        }

        let predecessor = match link.get("previous_chain_sha256") {
            Some(Value::Null) => Some(None),
            Some(value) if lowercase_sha256(Some(value)) => Some(value.as_str()),
            _ => {
                violations.push(json!({"index": index, "code": "previous_chain_sha256_invalid"}));
                None
            }
        };
        let batch_sha256 = link
            .get("audit_batch_sha256")
            .filter(|value| lowercase_sha256(Some(value)))
            .and_then(Value::as_str);
        if batch_sha256.is_none() {
            violations.push(json!({"index": index, "code": "audit_batch_sha256_invalid"}));
        }
        let chain_sha256 = link
            .get("chain_sha256")
            .filter(|value| lowercase_sha256(Some(value)))
            .and_then(Value::as_str);
        if chain_sha256.is_none() {
            violations.push(json!({"index": index, "code": "chain_sha256_invalid"}));
        }
        if link.get("claims")
            != Some(&json!({
                "chain_link_constructed": true,
                "external_custody_verified": false,
                "world_semantics_verified": false,
            }))
        {
            violations.push(json!({"index": index, "code": "chain_claims_mismatch"}));
        }

        if (index > 0 || checkpoint.is_some()) && predecessor.flatten() != previous_head {
            violations.push(json!({"index": index, "code": "chain_continuity_mismatch"}));
        }
        if let (Some(predecessor), Some(batch_sha256), Some(chain_sha256)) =
            (predecessor, batch_sha256, chain_sha256)
        {
            let payload = json!({
                "schema": "agent_bridge.modelscope_abot_receipt_audit_chain_payload.v0",
                "previous_chain_sha256": predecessor,
                "audit_batch_sha256": batch_sha256,
            });
            if canonical_json_sha256(&payload) != chain_sha256 {
                violations.push(json!({"index": index, "code": "chain_sha256_mismatch"}));
            }
        }
        previous_head = chain_sha256;
    }

    if current.get("previous_chain_sha256").and_then(Value::as_str) != previous_head {
        violations.push(json!({
            "index": history.len(),
            "code": "current_link_predecessor_mismatch",
        }));
    }
    let total_link_count = if let Some(count) = checkpoint_link_count {
        match count.checked_add(history.len() as u64 + 1) {
            Some(total) => Some(total),
            None => {
                violations.push(json!({
                    "index": 0,
                    "code": "chain_checkpoint_total_link_count_overflow",
                }));
                None
            }
        }
    } else {
        Some(history.len() as u64 + 1)
    };
    let verified = violations.is_empty();
    let mut claims = json!({
        "bounded_chain_continuity_verified": verified,
        "historical_source_documents_verified": false,
        "external_custody_verified": false,
        "world_semantics_verified": false,
    });
    if checkpoint.is_some() {
        claims["caller_supplied_checkpoint_bound"] = json!(verified);
    }
    json!({
        "schema": "agent_bridge.modelscope_abot_receipt_audit_chain_history_verification.v0",
        "status": if verified { "verified" } else { "mismatch" },
        "history_link_count": history.len(),
        "total_link_count": total_link_count,
        "chain_head_sha256": current["chain_sha256"],
        "violations": violations,
        "claims": claims,
    })
}

fn checkpoint_total_for_output(
    emit: bool,
    history_verification: Option<&Value>,
    has_history: bool,
    genesis: bool,
) -> Option<u64> {
    if !emit {
        return None;
    }
    match history_verification {
        Some(verification)
            if has_history
                && verification.get("status").and_then(Value::as_str) == Some("verified") =>
        {
            verification.get("total_link_count").and_then(Value::as_u64)
        }
        None if !has_history && genesis => Some(1),
        _ => None,
    }
}

fn verify_audit_chain_checkpoint_transition(
    history_verification: &Value,
    expected_successor: &Value,
    actual_successor: Option<&Value>,
) -> Value {
    let mut violations = Vec::<Value>::new();
    if history_verification.get("status").and_then(Value::as_str) != Some("verified") {
        violations.push(json!("source_transition_not_verified"));
    }

    let (_, expected_violations) = verify_audit_chain_checkpoint(expected_successor);
    for violation in expected_violations {
        let code = violation
            .get("code")
            .and_then(Value::as_str)
            .unwrap_or("chain_checkpoint_invalid")
            .strip_prefix("chain_checkpoint_")
            .unwrap_or("invalid");
        violations.push(json!(format!("expected_successor_{code}")));
    }

    if let Some(actual_successor) = actual_successor {
        for (field, code) in [
            ("schema", "successor_schema_mismatch"),
            ("canonicalization", "successor_canonicalization_mismatch"),
            ("chain_sha256", "successor_chain_sha256_mismatch"),
            ("total_link_count", "successor_total_link_count_mismatch"),
            ("claims", "successor_claims_mismatch"),
        ] {
            if expected_successor.get(field) != actual_successor.get(field) {
                violations.push(json!(code));
            }
        }
    } else if violations.is_empty() {
        violations.push(json!("successor_checkpoint_unavailable"));
    }

    let verified = violations.is_empty();
    json!({
        "schema": "agent_bridge.modelscope_abot_receipt_audit_chain_checkpoint_transition_verification.v0",
        "status": if verified { "verified" } else { "mismatch" },
        "violations": violations,
        "claims": {
            "checkpoint_transition_verified": verified,
            "historical_source_documents_verified": false,
            "external_custody_verified": false,
            "world_semantics_verified": false,
        },
    })
}

fn verify_audit_chain_checkpoint_candidates(
    history_verification: &Value,
    candidates: &[Value],
    actual_successor: Option<&Value>,
) -> Value {
    let source_verified =
        history_verification.get("status").and_then(Value::as_str) == Some("verified");
    let mut candidate_verifications = Vec::with_capacity(candidates.len());
    let mut candidate_groups = BTreeMap::<String, Vec<usize>>::new();
    let mut all_candidates_self_valid = true;
    let mut all_candidates_valid = true;

    for (index, candidate) in candidates.iter().enumerate() {
        let (_, checkpoint_violations) = verify_audit_chain_checkpoint(candidate);
        let mut violations = checkpoint_violations
            .into_iter()
            .filter_map(|violation| {
                violation.get("code").and_then(Value::as_str).map(|code| {
                    let code = code.strip_prefix("chain_checkpoint_").unwrap_or(code);
                    format!("candidate_{code}")
                })
            })
            .collect::<Vec<_>>();
        let self_valid = violations.is_empty();
        all_candidates_self_valid &= self_valid;
        if self_valid {
            candidate_groups
                .entry(canonical_json_sha256(candidate))
                .or_default()
                .push(index);
        }
        if self_valid {
            if let Some(actual_successor) = actual_successor {
                if candidate != actual_successor {
                    violations.push("candidate_successor_mismatch".into());
                }
            } else {
                violations.push("candidate_successor_unavailable".into());
            }
        }
        let valid = violations.is_empty();
        all_candidates_valid &= valid;
        candidate_verifications.push(json!({
            "index": index,
            "status": if valid { "verified" } else { "mismatch" },
            "violations": violations,
        }));
    }

    let fork_detected = source_verified && all_candidates_self_valid && candidate_groups.len() > 1;
    let exact_agreement = source_verified
        && all_candidates_valid
        && candidate_groups.len() == 1
        && actual_successor.is_some();
    let status = if exact_agreement {
        "verified"
    } else if fork_detected {
        "fork"
    } else {
        "mismatch"
    };
    json!({
        "schema": "agent_bridge.modelscope_abot_receipt_audit_chain_checkpoint_candidates_verification.v0",
        "status": status,
        "candidate_count": candidates.len(),
        "unique_candidate_count": candidate_groups.len(),
        "candidate_groups": candidate_groups,
        "candidate_verifications": candidate_verifications,
        "claims": {
            "candidate_consistency_verified": exact_agreement,
            "fork_detected": fork_detected,
            "historical_source_documents_verified": false,
            "external_custody_verified": false,
            "world_semantics_verified": false,
        },
    })
}

fn verify_audit_chain_binding(expected: &Value, actual: &Value) -> Value {
    let mut violations = Vec::<&'static str>::new();
    let Some(expected_object) = expected.as_object() else {
        return json!({
            "schema": "agent_bridge.modelscope_abot_receipt_audit_chain_verification.v0",
            "status": "mismatch",
            "violations": ["chain_binding_not_object"],
            "claims": {"audit_chain_bound": false},
        });
    };

    if expected_object.len() != 6
        || ![
            "schema",
            "canonicalization",
            "previous_chain_sha256",
            "audit_batch_sha256",
            "chain_sha256",
            "claims",
        ]
        .iter()
        .all(|key| expected_object.contains_key(*key))
    {
        violations.push("chain_binding_shape_mismatch");
    }
    for (field, violation) in [
        ("schema", "chain_schema_mismatch"),
        ("canonicalization", "canonicalization_mismatch"),
        ("previous_chain_sha256", "previous_chain_sha256_mismatch"),
        ("audit_batch_sha256", "audit_batch_sha256_mismatch"),
        ("chain_sha256", "chain_sha256_mismatch"),
        ("claims", "chain_claims_mismatch"),
    ] {
        if expected.get(field) != actual.get(field) {
            violations.push(violation);
        }
    }

    let verified = violations.is_empty();
    json!({
        "schema": "agent_bridge.modelscope_abot_receipt_audit_chain_verification.v0",
        "status": if verified { "verified" } else { "mismatch" },
        "violations": violations,
        "claims": {"audit_chain_bound": verified},
    })
}

fn validation_projection(document_kind: &str, violations: Vec<&'static str>) -> Value {
    let accepted = violations.is_empty();
    json!({
        "schema": "agent_bridge.modelscope_abot_receipt_validation.v0",
        "status": if accepted { "accepted" } else { "rejected" },
        "document_kind": document_kind,
        "violations": violations,
        "claims": {
            "prompt_submission_bound": accepted,
            "world_semantics_verified": false,
        },
        "runtime_effects": {
            "network_request_sent": false,
            "browser_opened": false,
            "task_state_written": false,
        },
    })
}

impl From<String> for RunFailure {
    fn from(message: String) -> Self {
        Self::new(message)
    }
}

impl From<&str> for RunFailure {
    fn from(message: &str) -> Self {
        Self::new(message)
    }
}

#[derive(Debug, Clone)]
struct TaskRequest {
    request_id: String,
    task_id: String,
    request_digest: String,
}

impl TaskRequest {
    fn parse(args: &Value, request: &RunRequest) -> std::result::Result<Option<Self>, String> {
        let Some(request_id) = args
            .get("request_id")
            .and_then(Value::as_str)
            .map(str::trim)
            .filter(|value| !value.is_empty())
        else {
            return Ok(None);
        };
        if request_id.chars().count() > MAX_REQUEST_ID_CHARS {
            return Err(format!(
                "request_id exceeds {MAX_REQUEST_ID_CHARS} characters"
            ));
        }
        let task_hash = format!(
            "{:x}",
            Sha256::digest(format!("{PROVIDER_ID}\0{request_id}").as_bytes())
        );
        let task_id = format!("abot-task-{}", &task_hash[..24]);
        let intent_id = args
            .get("embodiment_intent_id")
            .and_then(Value::as_str)
            .map(str::trim)
            .unwrap_or_default();
        let request_digest = format!(
            "{:x}",
            Sha256::digest(
                format!(
                    "{TASK_SCHEMA}\0{PROVIDER_ID}\0{request_id}\0{}\0{}\0{intent_id}",
                    request.prompt_sha256, request.observe_ms,
                )
                .as_bytes()
            )
        );
        Ok(Some(Self {
            request_id: request_id.to_string(),
            task_id,
            request_digest,
        }))
    }
}

impl RunRequest {
    fn parse(args: &Value) -> std::result::Result<Self, String> {
        if args.get("owner_confirmed").and_then(Value::as_bool) != Some(true) {
            return Err("owner_confirmed=true is required for live ModelScope execution".into());
        }
        Self::parse_inputs(args)
    }

    fn parse_inputs(args: &Value) -> std::result::Result<Self, String> {
        let prompt = args
            .get("prompt")
            .and_then(Value::as_str)
            .map(str::trim)
            .filter(|value| !value.is_empty())
            .ok_or_else(|| "missing non-empty 'prompt'".to_string())?
            .to_string();
        if prompt.chars().count() > MAX_PROMPT_CHARS {
            return Err(format!("prompt exceeds {MAX_PROMPT_CHARS} characters"));
        }
        let observe_ms = args
            .get("observe_ms")
            .and_then(Value::as_u64)
            .unwrap_or(DEFAULT_OBSERVE_MS);
        if !(MIN_OBSERVE_MS..=MAX_OBSERVE_MS).contains(&observe_ms) {
            return Err(format!(
                "observe_ms must be between {MIN_OBSERVE_MS} and {MAX_OBSERVE_MS}"
            ));
        }
        let prompt_sha256 = format!("{:x}", Sha256::digest(prompt.as_bytes()));
        Ok(Self {
            prompt,
            prompt_sha256,
            observe_ms,
        })
    }
}

fn attempt_task_state(task: &TaskRequest, record: Option<&Value>) -> Value {
    let Some(record) = record else {
        return json!({
            "state": "new_request",
            "idempotency_match": Value::Null,
            "requires_new_request_id": false,
            "external_execution_required": true,
        });
    };
    if record.get("request_digest").and_then(Value::as_str) != Some(task.request_digest.as_str()) {
        return json!({
            "state": "idempotency_conflict",
            "idempotency_match": false,
            "requires_new_request_id": true,
            "external_execution_required": false,
        });
    }
    match record.get("status").and_then(Value::as_str) {
        Some("completed") => json!({
            "state": "completed_replay_available",
            "idempotency_match": true,
            "requires_new_request_id": false,
            "external_execution_required": false,
        }),
        Some("failed") => json!({
            "state": "failed_requires_new_request_id",
            "idempotency_match": true,
            "requires_new_request_id": true,
            "external_execution_required": false,
        }),
        Some("running") if is_interrupted_running(record) => json!({
            "state": "interrupted_requires_new_request_id",
            "idempotency_match": true,
            "requires_new_request_id": true,
            "external_execution_required": false,
        }),
        Some("running") => json!({
            "state": "task_in_progress",
            "idempotency_match": true,
            "requires_new_request_id": false,
            "external_execution_required": false,
        }),
        Some(_) | None => json!({
            "state": "task_record_invalid",
            "idempotency_match": true,
            "requires_new_request_id": true,
            "external_execution_required": false,
        }),
    }
}

fn runtime_enabled() -> bool {
    matches!(
        std::env::var(ENABLE_ENV).as_deref(),
        Ok("1" | "true" | "yes")
    )
}

fn first_selector(value: &Value) -> Option<String> {
    match value {
        Value::Object(map) => map
            .get("selector")
            .and_then(Value::as_str)
            .map(str::to_string)
            .or_else(|| map.values().find_map(first_selector)),
        Value::Array(values) => values.iter().find_map(first_selector),
        _ => None,
    }
}

fn strings_in(value: &Value, out: &mut Vec<String>) {
    match value {
        Value::String(text) => out.push(text.clone()),
        Value::Array(values) => values.iter().for_each(|value| strings_in(value, out)),
        Value::Object(map) => map.values().for_each(|value| strings_in(value, out)),
        _ => {}
    }
}

fn eval_string(value: &Value) -> Option<&str> {
    match value {
        Value::String(text) => Some(text),
        Value::Array(values) => values.iter().find_map(eval_string),
        Value::Object(map) => map.values().find_map(eval_string),
        _ => None,
    }
}

fn prompt_binding_evidence(value: &Value, request: &RunRequest) -> Value {
    let observed = eval_string(value);
    let observed_sha256 = observed.map(|text| format!("{:x}", Sha256::digest(text.as_bytes())));
    json!({
        "schema": "agent_bridge.modelscope_abot_prompt_binding.v0",
        "selector": STUDIO_PROMPT_SELECTOR,
        "readback_observed": observed.is_some(),
        "exact_match": observed == Some(request.prompt.as_str()),
        "observed_chars": observed.map(|text| text.chars().count()),
        "observed_sha256": observed_sha256,
        "expected_sha256": request.prompt_sha256,
        "raw_prompt_recorded": false,
    })
}

fn frame_values(value: &Value) -> Vec<Value> {
    value
        .get("frames")
        .and_then(Value::as_array)
        .cloned()
        .unwrap_or_default()
}

fn observed_fps(value: &Value) -> Option<f64> {
    let mut strings = Vec::new();
    strings_in(value, &mut strings);
    strings.into_iter().find_map(|text| {
        let marker = text.find("FPS")?;
        let prefix = &text[..marker];
        let token = prefix
            .split_whitespace()
            .last()?
            .trim_matches(|character: char| !character.is_ascii_digit() && character != '.');
        token.parse::<f64>().ok().filter(|value| *value > 0.0)
    })
}

fn cache_dir() -> PathBuf {
    std::env::var_os("XDG_CACHE_HOME")
        .map(PathBuf::from)
        .or_else(|| std::env::var_os("HOME").map(|home| PathBuf::from(home).join(".cache")))
        .unwrap_or_else(|| PathBuf::from("."))
        .join("agent-bridge/modelscope-abot")
}

fn task_dir() -> PathBuf {
    cache_dir().join("tasks")
}

fn task_path(task_id: &str) -> PathBuf {
    task_dir().join(format!("{task_id}.json"))
}

fn now_unix_ms() -> u64 {
    SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .unwrap_or_default()
        .as_millis() as u64
}

fn process_instance_id() -> &'static str {
    PROCESS_INSTANCE_ID.get_or_init(|| format!("mcp-{}-{}", std::process::id(), now_unix_ms()))
}

fn atomic_write_json(path: &Path, value: &Value) -> std::result::Result<(), String> {
    let parent = path
        .parent()
        .ok_or_else(|| format!("task path has no parent: {}", path.display()))?;
    fs::create_dir_all(parent)
        .map_err(|error| format!("create task directory {}: {error}", parent.display()))?;
    fs::set_permissions(parent, fs::Permissions::from_mode(0o700))
        .map_err(|error| format!("secure task directory {}: {error}", parent.display()))?;
    let staged = path.with_extension(format!("json.tmp-{}-{}", std::process::id(), now_unix_ms()));
    let bytes = serde_json::to_vec_pretty(value)
        .map_err(|error| format!("serialize task record: {error}"))?;
    let mut file = fs::OpenOptions::new()
        .write(true)
        .create_new(true)
        .mode(0o600)
        .open(&staged)
        .map_err(|error| format!("create staged task record {}: {error}", staged.display()))?;
    file.write_all(&bytes)
        .map_err(|error| format!("stage task record {}: {error}", staged.display()))?;
    file.sync_all()
        .map_err(|error| format!("sync task record {}: {error}", staged.display()))?;
    fs::rename(&staged, path)
        .map_err(|error| format!("commit task record {}: {error}", path.display()))?;
    fs::File::open(parent)
        .and_then(|directory| directory.sync_all())
        .map_err(|error| format!("sync task directory {}: {error}", parent.display()))
}

fn read_task(path: &Path) -> std::result::Result<Option<Value>, String> {
    let bytes = match fs::read(path) {
        Ok(bytes) => bytes,
        Err(error) if error.kind() == std::io::ErrorKind::NotFound => return Ok(None),
        Err(error) => return Err(format!("read task record {}: {error}", path.display())),
    };
    serde_json::from_slice(&bytes)
        .map(Some)
        .map_err(|error| format!("parse task record {}: {error}", path.display()))
}

#[derive(Default)]
struct ProviderTaskScan {
    records: Vec<Value>,
    invalid_records: usize,
    omitted_records: usize,
}

fn valid_provider_health_record(record: &Value) -> bool {
    record.get("schema").and_then(Value::as_str) == Some(TASK_SCHEMA)
        && record.get("provider_id").and_then(Value::as_str) == Some(PROVIDER_ID)
        && record
            .get("task_id")
            .and_then(Value::as_str)
            .is_some_and(|task_id| task_id.starts_with("abot-task-"))
        && record
            .get("updated_at_unix_ms")
            .and_then(Value::as_u64)
            .is_some_and(|timestamp| timestamp > 0)
        && matches!(
            record.get("status").and_then(Value::as_str),
            Some("running" | "completed" | "failed")
        )
}

fn read_provider_tasks() -> std::result::Result<ProviderTaskScan, String> {
    let entries = match fs::read_dir(task_dir()) {
        Ok(entries) => entries,
        Err(error) if error.kind() == std::io::ErrorKind::NotFound => {
            return Ok(ProviderTaskScan::default())
        }
        Err(error) => return Err(format!("read provider task directory: {error}")),
    };
    let mut paths = Vec::new();
    for entry in entries {
        let entry = entry.map_err(|error| format!("read provider task entry: {error}"))?;
        let path = entry.path();
        if path.extension().and_then(|value| value.to_str()) != Some("json") {
            continue;
        }
        let metadata = match fs::symlink_metadata(&path) {
            Ok(metadata) if metadata.file_type().is_file() => metadata,
            _ => continue,
        };
        paths.push((metadata.modified().unwrap_or(UNIX_EPOCH), path));
    }
    paths.sort_by(|left, right| right.0.cmp(&left.0));
    let omitted_records = paths.len().saturating_sub(MAX_PROVIDER_TASK_SCAN);
    paths.truncate(MAX_PROVIDER_TASK_SCAN);

    let mut scan = ProviderTaskScan {
        omitted_records,
        ..ProviderTaskScan::default()
    };
    for (_, path) in paths {
        match read_task(&path) {
            Ok(Some(record)) if valid_provider_health_record(&record) => scan.records.push(record),
            _ => scan.invalid_records += 1,
        }
    }
    Ok(scan)
}

fn task_updated_at(record: &Value) -> u64 {
    record
        .get("updated_at_unix_ms")
        .and_then(Value::as_u64)
        .unwrap_or_default()
}

fn is_provider_failure(record: &Value) -> bool {
    let provider_failure = record.get("status").and_then(Value::as_str) == Some("failed")
        && matches!(
            record.get("failure_class").and_then(Value::as_str),
            Some("provider_timeout" | "provider_lifecycle")
        );
    provider_failure || is_interrupted_running(record)
}

fn is_interrupted_running(record: &Value) -> bool {
    record.get("status").and_then(Value::as_str) == Some("running")
        && record.get("process_instance_id").and_then(Value::as_str) != Some(process_instance_id())
}

fn cooldown_duration_ms(failure_count: usize) -> u64 {
    if failure_count == 0 {
        return 0;
    }
    PROVIDER_COOLDOWN_STEPS_MS[failure_count
        .saturating_sub(1)
        .min(PROVIDER_COOLDOWN_STEPS_MS.len() - 1)]
}

fn provider_recovery_state(records: &[Value], now_ms: u64) -> Value {
    let mut ordered = records.iter().collect::<Vec<_>>();
    ordered.sort_by_key(|record| std::cmp::Reverse(task_updated_at(record)));
    let last_success_at = ordered
        .iter()
        .find(|record| record.get("status").and_then(Value::as_str) == Some("completed"))
        .map(|record| task_updated_at(record));
    let provider_failures = ordered
        .iter()
        .copied()
        .filter(|record| {
            is_provider_failure(record)
                && last_success_at
                    .map(|success_at| task_updated_at(record) > success_at)
                    .unwrap_or(true)
        })
        .collect::<Vec<_>>();
    let failure_count = provider_failures.len();
    let latest_failure = provider_failures.first().copied();
    let cooldown_ms = cooldown_duration_ms(failure_count);
    let retry_not_before_unix_ms = latest_failure
        .map(task_updated_at)
        .unwrap_or_default()
        .saturating_add(cooldown_ms);
    let cooldown_active = failure_count > 0 && now_ms < retry_not_before_unix_ms;
    let remaining_ms = if cooldown_active {
        retry_not_before_unix_ms.saturating_sub(now_ms)
    } else {
        0
    };
    let latest_terminal_task = ordered
        .iter()
        .find(|record| {
            matches!(
                record.get("status").and_then(Value::as_str),
                Some("completed" | "failed")
            ) || is_interrupted_running(record)
        })
        .map(|record| {
            let interrupted = is_interrupted_running(record);
            json!({
                "task_id": record.get("task_id").and_then(Value::as_str),
                "status": if interrupted { Some("interrupted") } else { record.get("status").and_then(Value::as_str) },
                "failure_class": if interrupted { Some("interrupted_after_restart") } else { record.get("failure_class").and_then(Value::as_str) },
                "updated_at_unix_ms": task_updated_at(record),
            })
        });

    json!({
        "consecutive_provider_failures": failure_count,
        "last_success_at_unix_ms": last_success_at,
        "latest_terminal_task": latest_terminal_task,
        "cooldown": {
            "active": cooldown_active,
            "duration_ms": cooldown_ms,
            "remaining_ms": remaining_ms,
            "retry_not_before_unix_ms": if failure_count > 0 { Some(retry_not_before_unix_ms) } else { None },
            "policy_ms": PROVIDER_COOLDOWN_STEPS_MS,
            "reason": if cooldown_active { Some("recent_provider_failure") } else { None },
        },
    })
}

fn provider_cooldown_error(recovery: &Value) -> Option<String> {
    if recovery["cooldown"]["active"].as_bool() != Some(true) {
        return None;
    }
    let retry_at = recovery["cooldown"]["retry_not_before_unix_ms"]
        .as_u64()
        .unwrap_or_default();
    let remaining = recovery["cooldown"]["remaining_ms"]
        .as_u64()
        .unwrap_or_default();
    Some(format!(
        "provider_cooldown: ModelScope ABot recently failed; retry after unix_ms={retry_at} (remaining_ms={remaining}); no external execution was started"
    ))
}

fn running_task_record(task: &TaskRequest, request: &RunRequest, lease_id: &LeaseId) -> Value {
    let now = now_unix_ms();
    json!({
        "schema": TASK_SCHEMA,
        "task_id": task.task_id,
        "request_id": task.request_id,
        "request_digest": task.request_digest,
        "provider_id": PROVIDER_ID,
        "status": "running",
        "failure_class": Value::Null,
        "error": Value::Null,
        "created_at_unix_ms": now,
        "updated_at_unix_ms": now,
        "process_instance_id": process_instance_id(),
        "process_id": std::process::id(),
        "prompt_sha256": request.prompt_sha256,
        "observe_ms": request.observe_ms,
        "embodiment_lease_id": lease_id,
        "receipt": Value::Null,
        "retry_policy": "new_request_id_required_after_failure_or_interruption",
        "persistent_runtime_admitted": false,
    })
}

fn classify_failure(error: &str) -> &'static str {
    if error.contains("prompt binding") {
        "prompt_binding"
    } else if error.contains("positive FPS") || error.contains("candidate runtime frame") {
        "provider_timeout"
    } else if error.contains("stop action") || error.contains("lifecycle did not close") {
        "provider_lifecycle"
    } else if error.contains("receipt")
        || error.contains("screenshot")
        || error.contains("artifact")
    {
        "artifact_io"
    } else if error.contains("already active") {
        "concurrency_busy"
    } else {
        "browser_backend"
    }
}

fn completed_task_record(mut record: Value, receipt: Value) -> Value {
    record["status"] = json!("completed");
    record["updated_at_unix_ms"] = json!(now_unix_ms());
    record["receipt"] = receipt;
    record
}

fn failed_task_record(mut record: Value, error: &str, diagnostics: Option<Value>) -> Value {
    record["status"] = json!("failed");
    record["failure_class"] = json!(classify_failure(error));
    record["error"] = json!(error);
    record["diagnostics"] = diagnostics.unwrap_or(Value::Null);
    record["updated_at_unix_ms"] = json!(now_unix_ms());
    record
}

fn frame_host(url: &str) -> Option<String> {
    let (_, remainder) = url.split_once("://")?;
    let authority = remainder.split(['/', '?', '#']).next()?;
    let host_port = authority.rsplit('@').next()?;
    let host = if host_port.starts_with('[') {
        host_port
            .split_once(']')
            .map(|(host, _)| format!("{host}]"))
    } else {
        Some(host_port.split(':').next()?.to_string())
    }?;
    (!host.is_empty()).then_some(host)
}

fn is_ignored_presentation_host(host: &str) -> bool {
    let host = host.trim_end_matches('.').to_ascii_lowercase();
    host == "youtu.be"
        || host == "youtube.com"
        || host.ends_with(".youtube.com")
        || host == "youtube-nocookie.com"
        || host.ends_with(".youtube-nocookie.com")
}

fn is_candidate_runtime_frame(frame: &Value) -> bool {
    if frame.get("parent_id").and_then(Value::as_str).is_none() {
        return false;
    }
    !frame
        .get("url")
        .and_then(Value::as_str)
        .and_then(frame_host)
        .is_some_and(|host| is_ignored_presentation_host(&host))
}

fn child_frame_counts(frames: &[Value]) -> (usize, usize) {
    let total = frames
        .iter()
        .filter(|frame| frame.get("parent_id").and_then(Value::as_str).is_some())
        .count();
    let candidates = frames
        .iter()
        .filter(|frame| is_candidate_runtime_frame(frame))
        .count();
    (total, candidates)
}

fn diagnostic_status_signals(text: &str) -> Value {
    let lower = text.to_lowercase();
    json!({
        "fps_token_present": lower.contains("fps"),
        "queue_signal_present": lower.contains("queue") || lower.contains("排队"),
        "loading_signal_present": lower.contains("loading") || lower.contains("加载") || lower.contains("分配"),
        "error_signal_present": lower.contains("error") || lower.contains("failed") || lower.contains("失败") || lower.contains("错误"),
    })
}

fn redacted_error(kind: &str, error: &str) -> Value {
    json!({
        "kind": kind,
        "message_sha256": format!("{:x}", Sha256::digest(error.as_bytes())),
    })
}

fn write_private_artifact(path: &Path, bytes: &[u8]) -> std::io::Result<()> {
    let mut file = std::fs::OpenOptions::new()
        .create(true)
        .truncate(true)
        .write(true)
        .mode(0o600)
        .open(path)?;
    file.write_all(bytes)?;
    file.sync_all()
}

async fn capture_failure_diagnostics(
    browser: &dyn BrowserBackend,
    page: &PageId,
    observed_child_frame_count: usize,
    observed_candidate_frame_count: usize,
    start_control_present_after_click: bool,
    stop_control_present_after_click: bool,
) -> Value {
    let captured_at_unix_ms = now_unix_ms();
    let mut frame_diagnostics = Vec::new();
    let mut frame_list_error = None;
    match browser.list_frames(page).await {
        Ok(frames) => {
            for frame in frame_values(&frames)
                .into_iter()
                .filter(|frame| frame.get("parent_id").and_then(Value::as_str).is_some())
                .take(MAX_FAILURE_DIAGNOSTIC_FRAMES)
            {
                let frame_id = frame.get("frame_id").and_then(Value::as_str);
                let host = frame
                    .get("url")
                    .and_then(Value::as_str)
                    .and_then(frame_host);
                let candidate_runtime_frame = is_candidate_runtime_frame(&frame);
                let body_diagnostic = match if candidate_runtime_frame {
                    Some(
                        browser
                            .eval_in_frame(
                                page,
                                frame_id,
                                None,
                                "document.body ? document.body.innerText : ''",
                            )
                            .await,
                    )
                } else {
                    None
                } {
                    None => Value::Null,
                    Some(Ok(value)) => {
                        let mut strings = Vec::new();
                        strings_in(&value, &mut strings);
                        let text = strings.join("\n");
                        json!({
                            "text_chars": text.chars().count(),
                            "text_sha256": format!("{:x}", Sha256::digest(text.as_bytes())),
                            "status_signals": diagnostic_status_signals(&text),
                            "read_error": Value::Null,
                        })
                    }
                    Some(Err(error)) => json!({
                        "text_chars": Value::Null,
                        "text_sha256": Value::Null,
                        "status_signals": Value::Null,
                        "read_error": redacted_error("frame_eval_failed", &error.to_string()),
                    }),
                };
                frame_diagnostics.push(json!({
                    "host": host,
                    "role": if candidate_runtime_frame { "runtime_candidate" } else { "ignored_presentation" },
                    "body": body_diagnostic,
                }));
            }
        }
        Err(error) => {
            frame_list_error = Some(redacted_error("frame_list_failed", &error.to_string()))
        }
    }

    let artifact_dir = cache_dir();
    let screenshot = match browser.screenshot(page).await {
        Ok(bytes) => {
            let path = artifact_dir.join(format!("abot-failure-{captured_at_unix_ms}.png"));
            match std::fs::create_dir_all(&artifact_dir)
                .and_then(|_| write_private_artifact(&path, bytes.as_ref()))
            {
                Ok(()) => json!({
                    "path": path,
                    "sha256": format!("{:x}", Sha256::digest(bytes.as_ref())),
                    "bytes": bytes.len(),
                    "content_type": "image/png",
                }),
                Err(error) => {
                    json!({"capture_error": format!("write failure screenshot: {error}")})
                }
            }
        }
        Err(error) => json!({"capture_error": format!("capture failure screenshot: {error}")}),
    };

    let main_page = match browser.extract_text(page).await {
        Ok(text) => json!({
            "text_chars": text.chars().count(),
            "text_sha256": format!("{:x}", Sha256::digest(text.as_bytes())),
            "status_signals": diagnostic_status_signals(&text),
            "read_error": Value::Null,
        }),
        Err(error) => json!({
            "text_chars": Value::Null,
            "text_sha256": Value::Null,
            "status_signals": Value::Null,
            "read_error": redacted_error("main_page_text_failed", &error.to_string()),
        }),
    };

    json!({
        "schema": "agent_bridge.modelscope_abot_failure_diagnostics.v1",
        "captured_at_unix_ms": captured_at_unix_ms,
        "privacy": {
            "raw_text_recorded": false,
            "prompt_recorded": false,
            "frame_urls_recorded": false,
            "credentials_recorded": false,
            "screenshot_may_contain_submitted_prompt": true,
        },
        "controls": {
            "start_present_after_click": start_control_present_after_click,
            "stop_present_after_click": stop_control_present_after_click,
        },
        "observed_child_frame_count": observed_child_frame_count,
        "observed_candidate_runtime_frame_count": observed_candidate_frame_count,
        "recorded_frame_count": frame_diagnostics.len(),
        "frames_truncated": observed_child_frame_count > MAX_FAILURE_DIAGNOSTIC_FRAMES,
        "frame_list_error": frame_list_error,
        "main_page": main_page,
        "frames": frame_diagnostics,
        "screenshot": screenshot,
    })
}

fn inspect_existing_task(
    task: &TaskRequest,
    record: &Value,
) -> std::result::Result<Option<Value>, String> {
    if record.get("request_digest").and_then(Value::as_str) != Some(task.request_digest.as_str()) {
        return Err(format!(
            "idempotency_conflict: request_id '{}' is already bound to a different request digest",
            task.request_id
        ));
    }
    match record.get("status").and_then(Value::as_str) {
        Some("completed") => {
            let mut receipt = record
                .get("receipt")
                .cloned()
                .filter(Value::is_object)
                .ok_or_else(|| "completed task has no receipt".to_string())?;
            receipt["task_protocol"] = json!({
                "schema": TASK_SCHEMA,
                "task_id": task.task_id,
                "request_id": task.request_id,
                "request_digest": task.request_digest,
                "idempotent_replay": true,
                "external_execution_repeated": false,
            });
            Ok(Some(receipt))
        }
        Some("running") => {
            let same_process = record.get("process_instance_id").and_then(Value::as_str)
                == Some(process_instance_id());
            Err(if same_process {
                format!("task_in_progress: {}", task.task_id)
            } else {
                format!(
                    "task_interrupted_after_restart: {}; use a new request_id to retry",
                    task.task_id
                )
            })
        }
        Some("failed") => Err(format!(
            "task_previously_failed: {}; use a new request_id to retry",
            task.task_id
        )),
        Some(status) => Err(format!("unknown task status '{status}'")),
        None => Err("task record has no status".into()),
    }
}

fn task_status_projection(mut record: Value, include_receipt: bool) -> Value {
    let persisted_status = record
        .get("status")
        .and_then(Value::as_str)
        .unwrap_or("unknown")
        .to_string();
    if persisted_status == "running"
        && record.get("process_instance_id").and_then(Value::as_str) != Some(process_instance_id())
    {
        record["persisted_status"] = json!("running");
        record["status"] = json!("interrupted");
        record["failure_class"] = json!("interrupted_after_restart");
        record["requires_new_request_id"] = json!(true);
    }
    if !include_receipt {
        record
            .as_object_mut()
            .map(|object| object.remove("receipt"));
    }
    record["read_only"] = json!(true);
    record["status_projection_mutated_record"] = json!(false);
    record
}

async fn selector_for_text(
    browser: &dyn BrowserBackend,
    page: &PageId,
    text: &str,
) -> std::result::Result<String, String> {
    let candidates = browser
        .find_by_text(page, text, Some("button"))
        .await
        .map_err(|error| format!("find button '{text}': {error}"))?;
    first_selector(&candidates).ok_or_else(|| format!("button '{text}' not found"))
}

async fn wait_for_text_selector(
    browser: &dyn BrowserBackend,
    page: &PageId,
    text: &str,
    timeout_ms: u64,
) -> std::result::Result<String, String> {
    let deadline = Instant::now() + Duration::from_millis(timeout_ms);
    loop {
        match selector_for_text(browser, page, text).await {
            Ok(selector) => return Ok(selector),
            Err(_) if Instant::now() < deadline => {
                browser
                    .wait_for(page, None, None, 500)
                    .await
                    .map_err(|error| format!("wait for button '{text}': {error}"))?;
            }
            Err(_) => {
                return Err(format!(
                    "button '{text}' did not become ready within {timeout_ms}ms"
                ))
            }
        }
    }
}

async fn stop_session(browser: &dyn BrowserBackend, page: &PageId) -> bool {
    let Ok(selector) = selector_for_text(browser, page, "封存你的世界").await else {
        return false;
    };
    if browser.click(page, &selector).await.is_err() {
        return false;
    }
    let _ = browser.wait_for(page, None, None, 8_000).await;
    true
}

async fn run_once(
    browser: Arc<dyn BrowserBackend>,
    request: RunRequest,
) -> std::result::Result<Value, RunFailure> {
    let page = browser
        .navigate(BASE_URL)
        .await
        .map_err(|error| format!("navigate Studio: {error}"))?;
    let mut started = false;
    let mut verified_prompt_binding = None;
    let run_result: std::result::Result<Value, RunFailure> = async {
        let ready = browser
            .wait_for(
                &page,
                Some(STUDIO_PROMPT_SELECTOR),
                None,
                STUDIO_READY_TIMEOUT_MS,
            )
            .await
            .map_err(|error| format!("wait Studio load: {error}"))?;
        if ready.matched != "selector" {
            return Err(RunFailure::new(format!(
                "Studio prompt did not become ready within {STUDIO_READY_TIMEOUT_MS}ms"
            )));
        }
        browser
            .fill_form(&page, STUDIO_PROMPT_SELECTOR, &request.prompt)
            .await
            .map_err(|error| format!("fill prompt: {error}"))?;
        let prompt_readback = browser
            .eval(
                &page,
                "(() => { const el = document.querySelector('textarea'); return el && 'value' in el ? String(el.value) : null; })()",
            )
            .await
            .map_err(|error| format!("read prompt binding: {error}"))?;
        let prompt_binding = prompt_binding_evidence(&prompt_readback, &request);
        if prompt_binding["exact_match"] != true {
            return Err(RunFailure::with_diagnostics(
                "Studio prompt binding readback did not exactly match the authorized request",
                json!({
                    "schema": "agent_bridge.modelscope_abot_prompt_binding_failure.v0",
                    "prompt_binding": prompt_binding,
                }),
            ));
        }
        verified_prompt_binding = Some(prompt_binding.clone());
        let frames_before_start = browser
            .list_frames(&page)
            .await
            .map_err(|error| format!("list Studio frames before start: {error}"))?;
        let (child_frame_count_before_start, candidate_frame_count_before_start) =
            child_frame_counts(&frame_values(&frames_before_start));
        let start_selector = wait_for_text_selector(
            browser.as_ref(),
            &page,
            "唤醒你的世界",
            STUDIO_START_TIMEOUT_MS,
        )
        .await?;
        browser
            .click(&page, &start_selector)
            .await
            .map_err(|error| format!("start Studio: {error}"))?;
        started = true;
        browser
            .wait_for(&page, None, None, 3_000)
            .await
            .map_err(|error| format!("wait GPU allocation: {error}"))?;
        let start_control_present_after_click = selector_for_text(
            browser.as_ref(),
            &page,
            "唤醒你的世界",
        )
        .await
        .is_ok();
        let stop_control_present_after_click = selector_for_text(
            browser.as_ref(),
            &page,
            "封存你的世界",
        )
        .await
        .is_ok();

        let deadline = Instant::now() + Duration::from_millis(request.observe_ms);
        let mut max_fps = 0.0_f64;
        let mut observed_child_frame_count = 0_usize;
        let mut observed_candidate_frame_count = 0_usize;
        while Instant::now() < deadline {
            let frames = browser
                .list_frames(&page)
                .await
                .map_err(|error| format!("list Studio frames: {error}"))?;
            let frame_values = frame_values(&frames);
            let (child_count, candidate_count) = child_frame_counts(&frame_values);
            observed_child_frame_count = observed_child_frame_count.max(child_count);
            observed_candidate_frame_count =
                observed_candidate_frame_count.max(candidate_count);
            for frame in frame_values {
                let frame_id = frame.get("frame_id").and_then(Value::as_str);
                if !is_candidate_runtime_frame(&frame) {
                    continue;
                }
                let value = browser
                    .eval_in_frame(
                        &page,
                        frame_id,
                        None,
                        "document.body ? document.body.innerText : ''",
                    )
                    .await;
                if let Ok(value) = value {
                    if let Some(fps) = observed_fps(&value) {
                        max_fps = max_fps.max(fps);
                    }
                }
            }
            if max_fps > 0.0 {
                break;
            }
            let _ = browser.wait_for(&page, None, None, 1_000).await;
        }
        if max_fps <= 0.0 {
            let diagnostics = capture_failure_diagnostics(
                browser.as_ref(),
                &page,
                observed_child_frame_count,
                observed_candidate_frame_count,
                start_control_present_after_click,
                stop_control_present_after_click,
            )
            .await;
            let message = if observed_candidate_frame_count == 0 {
                "Studio did not expose a candidate runtime frame before deadline"
            } else {
                "Studio candidate runtime frame did not report positive FPS before deadline"
            };
            return Err(RunFailure::with_diagnostics(
                message,
                diagnostics,
            ));
        }

        let screenshot = browser
            .screenshot(&page)
            .await
            .map_err(|error| format!("capture Studio screenshot: {error}"))?;
        let screenshot_sha256 = format!("{:x}", Sha256::digest(screenshot.as_ref()));
        let observed_at_unix_ms = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .unwrap_or_default()
            .as_millis() as u64;
        let artifact_dir = cache_dir();
        std::fs::create_dir_all(&artifact_dir)
            .map_err(|error| format!("create receipt directory: {error}"))?;
        let run_id = format!("abot-live-{observed_at_unix_ms}");
        let screenshot_path = artifact_dir.join(format!("{run_id}.png"));
        std::fs::write(&screenshot_path, screenshot.as_ref())
            .map_err(|error| format!("write Studio screenshot: {error}"))?;

        if !stop_session(browser.as_ref(), &page).await {
            return Err("Studio stop action failed".into());
        }
        let frames_after_stop = browser
            .list_frames(&page)
            .await
            .map_err(|error| format!("verify Studio stop: {error}"))?;
        let frames_after_stop = frame_values(&frames_after_stop);
        let (iframe_count_after_stop, candidate_iframe_count_after_stop) =
            child_frame_counts(&frames_after_stop);
        if candidate_iframe_count_after_stop != 0 {
            return Err(RunFailure::new(format!(
                "Studio lifecycle did not close: {candidate_iframe_count_after_stop} candidate runtime iframe(s) remain"
            )));
        }
        started = false;

        let receipt = json!({
            "schema": "agent_bridge.modelscope_abot_run_once_receipt.v1",
            "provider_id": PROVIDER_ID,
            "run_id": run_id,
            "observed_at_unix_ms": observed_at_unix_ms,
            "prompt_sha256": request.prompt_sha256,
            "authorization": {
                "owner_confirmed": true,
                "scope": "one_shot_browser_runtime",
                "persistent_runtime_authorized": false,
            },
            "observations": {
                "gpu_session_observed": observed_candidate_frame_count > 0,
                "stream_observed": true,
                "max_observed_fps": max_fps,
                "child_frame_count_observed": observed_child_frame_count,
                "candidate_runtime_frame_count_observed": observed_candidate_frame_count,
                "start_control_present_after_click": start_control_present_after_click,
                "stop_control_present_after_click": stop_control_present_after_click,
                "stop_observed": true,
                "post_stop_iframe_count": iframe_count_after_stop,
                "post_stop_candidate_runtime_iframe_count": candidate_iframe_count_after_stop,
            },
            "binding": {
                "status": "submission_bound_output_unverified",
                "prompt_submission": prompt_binding,
                "output_freshness": {
                    "child_frame_count_before_start": child_frame_count_before_start,
                    "candidate_runtime_frame_count_before_start": candidate_frame_count_before_start,
                    "fresh_candidate_runtime_frame_observed": observed_candidate_frame_count > candidate_frame_count_before_start,
                    "positive_fps_observed": max_fps > 0.0,
                },
                "world_semantics_verified": false,
                "semantic_verification_reason": "provider exposes no machine-verifiable prompt-to-world identity or semantic attestation",
            },
            "artifact": {
                "path": screenshot_path,
                "sha256": screenshot_sha256,
                "bytes": screenshot.len(),
                "content_type": "image/png",
                "evidence_type": "presentation_screenshot",
            },
            "execution": {
                "network_request_sent": true,
                "studio_start_called": true,
                "execution_attempted": true,
                "execution_authorized": true,
                "one_shot_runtime_admitted": true,
                "persistent_runtime_admitted": false,
                "mcp_tool_registered": true,
            },
            "lifecycle_closed": true,
            "status": "completed",
        });
        let receipt_path = artifact_dir.join(format!("{run_id}.json"));
        let receipt_bytes = serde_json::to_vec_pretty(&receipt)
            .map_err(|error| format!("serialize Studio receipt: {error}"))?;
        std::fs::write(&receipt_path, receipt_bytes)
            .map_err(|error| format!("write Studio receipt: {error}"))?;
        let mut receipt = receipt;
        receipt["receipt_path"] = json!(receipt_path);
        Ok(receipt)
    }
    .await;

    let cleanup_stop_observed = if started {
        stop_session(browser.as_ref(), &page).await
    } else {
        true
    };
    let close_observed = browser.close(&page).await.is_ok();
    run_result.map_err(|mut failure| {
        if let Some(prompt_binding) = verified_prompt_binding {
            attach_verified_prompt_binding(&mut failure, prompt_binding);
        }
        failure.message = format!(
            "{}; cleanup_stop_observed={cleanup_stop_observed}; close_observed={close_observed}",
            failure.message
        );
        failure
    })
}

pub struct ModelScopeAbotRunOnceTool {
    hub: Hub,
}

impl ModelScopeAbotRunOnceTool {
    pub fn new(hub: Hub) -> Self {
        Self { hub }
    }
}

#[async_trait]
impl McpTool for ModelScopeAbotRunOnceTool {
    fn name(&self) -> &'static str {
        "modelscope_abot_run_once"
    }

    fn schema(&self) -> ToolSchema {
        ToolSchema {
            name: self.name().into(),
            description: "Run one bounded ABot-World Studio session. Exact private prompt readback proves submission; the receipt leaves world semantics unverified. Requires Browser, body lease, owner confirmation, and runtime opt-in; never creates a persistent runtime.".into(),
            input_schema: json!({
                "type": "object",
                "required": ["prompt", "owner_confirmed", "embodiment_lease_id"],
                "properties": {
                    "prompt": {"type": "string", "minLength": 1, "maxLength": MAX_PROMPT_CHARS},
                    "observe_ms": {"type": "integer", "minimum": MIN_OBSERVE_MS, "maximum": MAX_OBSERVE_MS, "default": DEFAULT_OBSERVE_MS},
                    "owner_confirmed": {"type": "boolean", "const": true},
                    "embodiment_lease_id": {"type": "string", "minLength": 1, "maxLength": 128},
                    "embodiment_intent_id": {"type": "string", "minLength": 1, "maxLength": 128},
                    "request_id": {"type": "string", "minLength": 1, "maxLength": MAX_REQUEST_ID_CHARS, "description": "Optional stable idempotency key. Same id plus same request replays the completed receipt without external execution; failed or interrupted tasks require a new id."}
                }
            }),
        }
    }

    async fn execute(&self, args: Value, ctx: &ToolContext) -> Result<ToolResult> {
        if let Err(error) = self.hub.security.check(Cap::Browser) {
            return Ok(ToolResult::error(error));
        }
        let lease_id = match require_body_write_lease(&self.hub, &args, ctx).await {
            Ok(lease_id) => lease_id,
            Err(error) => return Ok(ToolResult::error(error)),
        };
        if !runtime_enabled() {
            return Ok(ToolResult::error(format!(
                "ModelScope ABot runtime is disabled; set {ENABLE_ENV}=1 before starting agent-bridge"
            )));
        }
        let request = match RunRequest::parse(&args) {
            Ok(request) => request,
            Err(error) => return Ok(ToolResult::error(error)),
        };
        let task = match TaskRequest::parse(&args, &request) {
            Ok(task) => task,
            Err(error) => return Ok(ToolResult::error(error)),
        };
        let browser = match self.hub.browser.clone() {
            Some(browser) => browser,
            None => return Ok(ToolResult::error("no browser backend configured")),
        };
        if let Some(task) = task.as_ref() {
            let _task_guard = TASK_LOCK
                .get_or_init(|| tokio::sync::Mutex::new(()))
                .lock()
                .await;
            match read_task(&task_path(&task.task_id)) {
                Ok(Some(record)) => match inspect_existing_task(task, &record) {
                    Ok(Some(receipt)) => return Ok(ToolResult::structured_json(&receipt)),
                    Ok(None) => {}
                    Err(error) => return Ok(ToolResult::error(error)),
                },
                Ok(None) => {}
                Err(error) => return Ok(ToolResult::error(error)),
            }
        }
        let provider_tasks = match read_provider_tasks() {
            Ok(scan) => scan,
            Err(error) => {
                return Ok(ToolResult::error(format!(
                    "provider recovery preflight unavailable: {error}"
                )))
            }
        };
        if provider_tasks.invalid_records > 0 {
            return Ok(ToolResult::error(format!(
                "provider recovery preflight unavailable: {} invalid task record(s); no external execution was started",
                provider_tasks.invalid_records
            )));
        }
        let recovery = provider_recovery_state(&provider_tasks.records, now_unix_ms());
        if let Some(error) = provider_cooldown_error(&recovery) {
            return Ok(ToolResult::error(error));
        }
        let lock = SESSION_LOCK.get_or_init(|| tokio::sync::Mutex::new(()));
        let _guard = match lock.try_lock() {
            Ok(guard) => guard,
            Err(_) => {
                return Ok(ToolResult::error(
                    "a ModelScope ABot session is already active",
                ))
            }
        };
        let mut task_record = None;
        if let Some(task) = task.as_ref() {
            let _task_guard = TASK_LOCK
                .get_or_init(|| tokio::sync::Mutex::new(()))
                .lock()
                .await;
            let path = task_path(&task.task_id);
            match read_task(&path) {
                Ok(Some(record)) => match inspect_existing_task(task, &record) {
                    Ok(Some(receipt)) => return Ok(ToolResult::structured_json(&receipt)),
                    Ok(None) => {}
                    Err(error) => return Ok(ToolResult::error(error)),
                },
                Ok(None) => {}
                Err(error) => return Ok(ToolResult::error(error)),
            }
            let record = running_task_record(task, &request, &lease_id);
            if let Err(error) = atomic_write_json(&path, &record) {
                return Ok(ToolResult::error(error));
            }
            task_record = Some(record);
        }
        let intent_id = args
            .get("embodiment_intent_id")
            .and_then(Value::as_str)
            .map(str::trim)
            .filter(|value| !value.is_empty());
        match run_once(browser, request).await {
            Ok(mut receipt) => {
                receipt["embodiment_lease_id"] = json!(lease_id.to_string());
                if let (Some(task), Some(record)) = (task.as_ref(), task_record.take()) {
                    receipt["task_protocol"] = json!({
                        "schema": TASK_SCHEMA,
                        "task_id": task.task_id,
                        "request_id": task.request_id,
                        "request_digest": task.request_digest,
                        "idempotent_replay": false,
                        "external_execution_repeated": false,
                    });
                    let completed = completed_task_record(record, receipt.clone());
                    if let Err(error) = atomic_write_json(&task_path(&task.task_id), &completed) {
                        return Ok(ToolResult::error(format!(
                            "execution completed but durable task receipt failed: {error}; do not retry with the same request_id"
                        )));
                    }
                }
                record_embodiment_receipt(
                    &self.hub,
                    "modelscope_abot",
                    "run_once",
                    intent_id,
                    receipt
                        .get("run_id")
                        .and_then(Value::as_str)
                        .map(str::to_string),
                    true,
                    receipt.clone(),
                )
                .await;
                Ok(ToolResult::structured_json(&receipt))
            }
            Err(failure) => {
                let error = failure.message;
                let diagnostics = failure.diagnostics;
                if let (Some(task), Some(record)) = (task.as_ref(), task_record.take()) {
                    let failed = failed_task_record(record, &error, diagnostics.clone());
                    if let Err(persist_error) =
                        atomic_write_json(&task_path(&task.task_id), &failed)
                    {
                        return Ok(ToolResult::error(format!(
                            "{error}; durable task failure write also failed: {persist_error}; do not retry with the same request_id"
                        )));
                    }
                }
                record_embodiment_receipt(
                    &self.hub,
                    "modelscope_abot",
                    "run_once",
                    intent_id,
                    None,
                    false,
                    json!({
                        "error": error,
                        "diagnostics": diagnostics,
                        "embodiment_lease_id": lease_id,
                    }),
                )
                .await;
                Ok(ToolResult::error(error))
            }
        }
    }
}

pub struct ModelScopeAbotProviderStatusTool {
    hub: Hub,
}

pub struct ModelScopeAbotAttemptPreviewTool {
    hub: Hub,
}

impl ModelScopeAbotAttemptPreviewTool {
    pub fn new(hub: Hub) -> Self {
        Self { hub }
    }
}

#[async_trait]
impl McpTool for ModelScopeAbotAttemptPreviewTool {
    fn name(&self) -> &'static str {
        "modelscope_abot_attempt_preview"
    }

    fn schema(&self) -> ToolSchema {
        ToolSchema {
            name: self.name().into(),
            description: "Preview one exact ModelScope ABot request identity and its current admission blockers. Read-only: never accepts owner confirmation, acquires a lease, writes a task, opens a browser, probes the network, or executes the provider.".into(),
            input_schema: json!({
                "type": "object",
                "required": ["prompt", "request_id"],
                "properties": {
                    "prompt": {"type": "string", "minLength": 1, "maxLength": MAX_PROMPT_CHARS},
                    "observe_ms": {"type": "integer", "minimum": MIN_OBSERVE_MS, "maximum": MAX_OBSERVE_MS, "default": DEFAULT_OBSERVE_MS},
                    "embodiment_intent_id": {"type": "string", "minLength": 1, "maxLength": 128},
                    "request_id": {"type": "string", "minLength": 1, "maxLength": MAX_REQUEST_ID_CHARS}
                }
            }),
        }
    }

    async fn execute(&self, args: Value, _ctx: &ToolContext) -> Result<ToolResult> {
        let request = match RunRequest::parse_inputs(&args) {
            Ok(request) => request,
            Err(error) => return Ok(ToolResult::error(error)),
        };
        let task = match TaskRequest::parse(&args, &request) {
            Ok(Some(task)) => task,
            Ok(None) => return Ok(ToolResult::error("missing non-empty 'request_id'")),
            Err(error) => return Ok(ToolResult::error(error)),
        };
        let existing = match read_task(&task_path(&task.task_id)) {
            Ok(record) => record,
            Err(error) => return Ok(ToolResult::error(error)),
        };
        let task_state = attempt_task_state(&task, existing.as_ref());
        let provider_tasks = match read_provider_tasks() {
            Ok(scan) => scan,
            Err(error) => return Ok(ToolResult::error(error)),
        };
        let recovery = provider_recovery_state(&provider_tasks.records, now_unix_ms());
        let replay = task_state["state"].as_str() == Some("completed_replay_available");
        let new_request = task_state["state"].as_str() == Some("new_request");
        let mut blockers = Vec::new();
        if !runtime_enabled() {
            blockers.push("runtime_opt_in_missing");
        }
        if self.hub.browser.is_none() {
            blockers.push("browser_backend_missing");
        }
        if self.hub.security.check(Cap::Browser).is_err() {
            blockers.push("browser_capability_denied");
        }
        if !new_request && !replay {
            blockers.push(
                task_state["state"]
                    .as_str()
                    .unwrap_or("task_record_invalid"),
            );
        }
        if new_request {
            if provider_tasks.invalid_records > 0 {
                blockers.push("task_history_invalid");
            }
            if recovery["cooldown"]["active"].as_bool() == Some(true) {
                blockers.push("provider_cooldown_active");
            }
        }
        Ok(ToolResult::structured_json(&json!({
            "schema": "agent_bridge.modelscope_abot_attempt_preview.v0",
            "provider_id": PROVIDER_ID,
            "read_only": true,
            "prompt_persisted": false,
            "task_record_written": false,
            "lease_acquired": false,
            "browser_opened": false,
            "network_probe_performed": false,
            "external_execution_started": false,
            "persistent_runtime_admitted": false,
            "request": {
                "request_id": task.request_id,
                "task_id": task.task_id,
                "request_digest": task.request_digest,
                "prompt_sha256": request.prompt_sha256,
                "observe_ms": request.observe_ms,
                "embodiment_intent_bound": args.get("embodiment_intent_id").and_then(Value::as_str).is_some(),
            },
            "existing_task": task_state,
            "provider_recovery": recovery,
            "execution_preflight": {
                "ready_for_authorized_call": blockers.is_empty(),
                "blockers": blockers,
                "requires_owner_confirmed_true": true,
                "requires_active_body_write_lease": true,
                "preview_grants_authority": false,
            },
        })))
    }
}

impl ModelScopeAbotProviderStatusTool {
    pub fn new(hub: Hub) -> Self {
        Self { hub }
    }
}

#[async_trait]
impl McpTool for ModelScopeAbotProviderStatusTool {
    fn name(&self) -> &'static str {
        "modelscope_abot_provider_status"
    }

    fn schema(&self) -> ToolSchema {
        ToolSchema {
            name: self.name().into(),
            description: "Project local ModelScope ABot recovery readiness from durable task records. Read-only: performs no network probe, browser action, retry, lease acquisition, or runtime enablement.".into(),
            input_schema: json!({"type": "object", "properties": {}}),
        }
    }

    async fn execute(&self, _args: Value, _ctx: &ToolContext) -> Result<ToolResult> {
        let scan = match read_provider_tasks() {
            Ok(scan) => scan,
            Err(error) => return Ok(ToolResult::error(error)),
        };
        let recovery = provider_recovery_state(&scan.records, now_unix_ms());
        let runtime_opted_in = runtime_enabled();
        let browser_configured = self.hub.browser.is_some();
        let browser_capability_allowed = self.hub.security.check(Cap::Browser).is_ok();
        let cooldown_active = recovery["cooldown"]["active"].as_bool() == Some(true);
        let mut blockers = Vec::new();
        if !runtime_opted_in {
            blockers.push("runtime_opt_in_missing");
        }
        if !browser_configured {
            blockers.push("browser_backend_missing");
        }
        if !browser_capability_allowed {
            blockers.push("browser_capability_denied");
        }
        if cooldown_active {
            blockers.push("provider_cooldown_active");
        }
        if scan.invalid_records > 0 {
            blockers.push("task_history_invalid");
        }
        Ok(ToolResult::structured_json(&json!({
            "schema": "agent_bridge.modelscope_abot_provider_status.v0",
            "provider_id": PROVIDER_ID,
            "read_only": true,
            "network_probe_performed": false,
            "external_execution_started": false,
            "persistent_runtime_admitted": false,
            "task_scan": {
                "records_considered": scan.records.len(),
                "invalid_records": scan.invalid_records,
                "omitted_records": scan.omitted_records,
                "limit": MAX_PROVIDER_TASK_SCAN,
            },
            "recovery": recovery,
            "runtime": {
                "opted_in": runtime_opted_in,
                "browser_configured": browser_configured,
                "browser_capability_allowed": browser_capability_allowed,
            },
            "execution_preflight": {
                "eligible": blockers.is_empty(),
                "blockers": blockers,
                "owner_confirmation_and_body_lease_still_required_per_call": true,
            },
        })))
    }
}

pub struct ModelScopeAbotTaskStatusTool;

pub struct ModelScopeAbotReceiptValidateTool;

pub struct ModelScopeAbotReceiptAuditTool;

#[async_trait]
impl McpTool for ModelScopeAbotReceiptAuditTool {
    fn name(&self) -> &'static str {
        "modelscope_abot_receipt_audit"
    }

    fn schema(&self) -> ToolSchema {
        ToolSchema {
            name: self.name().into(),
            description: "Audit ModelScope ABot receipts; verify evidence, chain history, checkpoint suffix, or expected successor checkpoint. Read-only and offline: no persistence, task-state read, browser action, or provider request.".into(),
            input_schema: json!({
                "type": "object",
                "required": ["documents"],
                "properties": {
                    "documents": {
                        "type": "array",
                        "minItems": 1,
                        "maxItems": MAX_RECEIPT_AUDIT_DOCUMENTS,
                        "items": {"type": "object"},
                        "description": "Structured receipts or failure diagnostics. Raw prompt fields are rejected."
                    },
                    "evidence_binding": {
                        "type": "object",
                        "description": "Optional prior Gate 8O evidence binding to verify against these ordered documents."
                    },
                    "previous_chain_sha256": {
                        "type": "string",
                        "pattern": "^[0-9a-f]{64}$",
                        "description": "Optional prior Gate 8Q chain digest. Omit for a genesis link. This does not prove external custody."
                    },
                    "chain_binding": {
                        "type": "object",
                        "description": "Optional prior Gate 8Q chain binding to verify against these documents and previous-chain digest."
                    },
                    "chain_history": {
                        "type": "array",
                        "minItems": 1,
                        "maxItems": MAX_RECEIPT_AUDIT_DOCUMENTS,
                        "items": {"type": "object"},
                        "description": "Optional ordered Gate 8Q links to verify before joining this batch. This verifies bounded continuity, not historical source documents or external custody."
                    },
                    "chain_checkpoint": {
                        "type": "object",
                        "description": "Optional Gate 8S checkpoint anchoring the first history link and cumulative count. Requires chain_history; proves only supplied-checkpoint integrity and suffix continuity."
                    },
                    "emit_chain_checkpoint": {
                        "type": "boolean",
                        "default": false,
                        "description": "Opt in to a new checkpoint output after successful genesis or chain-history verification. False preserves the pre-8S response shape."
                    },
                    "expected_successor_checkpoint": {
                        "type": "object",
                        "description": "Optional Gate 8T successor checkpoint to verify exactly after a valid checkpoint-anchored suffix transition. Requires chain_checkpoint and chain_history."
                    },
                    "successor_checkpoint_candidates": {
                        "type": "array",
                        "minItems": 2,
                        "maxItems": MAX_RECEIPT_AUDIT_DOCUMENTS,
                        "items": {"type": "object"},
                        "description": "Optional Gate 8U parallel successor candidates. Requires chain_checkpoint and chain_history; reports agreement or fork without selecting a candidate."
                    }
                }
            }),
        }
    }

    async fn execute(&self, args: Value, _ctx: &ToolContext) -> Result<ToolResult> {
        let Some(documents) = args.get("documents").and_then(Value::as_array) else {
            return Ok(ToolResult::error("missing array 'documents'"));
        };
        if documents.is_empty() || documents.len() > MAX_RECEIPT_AUDIT_DOCUMENTS {
            return Ok(ToolResult::error(format!(
                "documents must contain 1..={MAX_RECEIPT_AUDIT_DOCUMENTS} items"
            )));
        }
        let chain_history = match args.get("chain_history") {
            Some(Value::Array(history))
                if !history.is_empty() && history.len() <= MAX_RECEIPT_AUDIT_DOCUMENTS =>
            {
                Some(history.as_slice())
            }
            Some(_) => {
                return Ok(ToolResult::error(format!(
                    "chain_history must contain 1..={MAX_RECEIPT_AUDIT_DOCUMENTS} items"
                )));
            }
            None => None,
        };
        let chain_checkpoint = args.get("chain_checkpoint");
        if chain_checkpoint.is_some() && chain_history.is_none() {
            return Ok(ToolResult::error(
                "chain_checkpoint requires non-empty chain_history",
            ));
        }
        let expected_successor_checkpoint = args.get("expected_successor_checkpoint");
        if expected_successor_checkpoint.is_some()
            && (chain_checkpoint.is_none() || chain_history.is_none())
        {
            return Ok(ToolResult::error(
                "expected_successor_checkpoint requires chain_checkpoint and non-empty chain_history",
            ));
        }
        let successor_checkpoint_candidates = match args.get("successor_checkpoint_candidates") {
            Some(Value::Array(candidates))
                if candidates.len() >= 2 && candidates.len() <= MAX_RECEIPT_AUDIT_DOCUMENTS =>
            {
                Some(candidates.as_slice())
            }
            Some(Value::Array(_)) => {
                return Ok(ToolResult::error(format!(
                    "successor_checkpoint_candidates must contain 2..={MAX_RECEIPT_AUDIT_DOCUMENTS} items"
                )));
            }
            Some(_) => {
                return Ok(ToolResult::error(
                    "successor_checkpoint_candidates must be an array",
                ));
            }
            None => None,
        };
        if successor_checkpoint_candidates.is_some()
            && (chain_checkpoint.is_none() || chain_history.is_none())
        {
            return Ok(ToolResult::error(
                "successor_checkpoint_candidates requires chain_checkpoint and non-empty chain_history",
            ));
        }
        let emit_chain_checkpoint = match args.get("emit_chain_checkpoint") {
            Some(Value::Bool(value)) => *value,
            Some(_) => return Ok(ToolResult::error("emit_chain_checkpoint must be boolean")),
            None => false,
        };
        let explicit_previous_chain_sha256 = match args.get("previous_chain_sha256") {
            Some(Value::String(value)) if lowercase_sha256(Some(&Value::String(value.clone()))) => {
                Some(value.as_str())
            }
            Some(_) => {
                return Ok(ToolResult::error(
                    "previous_chain_sha256 must be 64 lowercase hexadecimal characters",
                ));
            }
            None => None,
        };
        let history_head_sha256 = chain_history
            .and_then(|history| history.last())
            .and_then(|link| link.get("chain_sha256"))
            .filter(|value| lowercase_sha256(Some(value)))
            .and_then(Value::as_str);
        let previous_chain_sha256 = explicit_previous_chain_sha256.or(history_head_sha256);
        let mut audit = audit_abot_receipts(documents);
        if let Some(expected) = args.get("evidence_binding") {
            let verification = verify_audit_evidence_binding(expected, &audit["evidence_binding"]);
            audit["evidence_verification"] = verification;
        }
        let chain_binding = audit_chain_binding(&audit["evidence_binding"], previous_chain_sha256);
        if let Some(expected) = args.get("chain_binding") {
            audit["chain_verification"] = verify_audit_chain_binding(expected, &chain_binding);
        }
        let history_verification = chain_history
            .map(|history| verify_audit_chain_history(history, &chain_binding, chain_checkpoint));
        if let Some(verification) = &history_verification {
            audit["chain_history_verification"] = verification.clone();
        }
        let checkpoint_total = checkpoint_total_for_output(
            emit_chain_checkpoint
                || expected_successor_checkpoint.is_some()
                || successor_checkpoint_candidates.is_some(),
            history_verification.as_ref(),
            chain_history.is_some(),
            chain_history.is_none() && previous_chain_sha256.is_none(),
        );
        let successor_checkpoint = if let (Some(total_link_count), Some(chain_sha256)) =
            (checkpoint_total, chain_binding["chain_sha256"].as_str())
        {
            Some(audit_chain_checkpoint(chain_sha256, total_link_count))
        } else {
            None
        };
        if let (Some(expected), Some(verification)) =
            (expected_successor_checkpoint, history_verification.as_ref())
        {
            audit["checkpoint_transition_verification"] = verify_audit_chain_checkpoint_transition(
                verification,
                expected,
                successor_checkpoint.as_ref(),
            );
        }
        if let (Some(candidates), Some(verification)) = (
            successor_checkpoint_candidates,
            history_verification.as_ref(),
        ) {
            audit["checkpoint_candidates_verification"] = verify_audit_chain_checkpoint_candidates(
                verification,
                candidates,
                successor_checkpoint.as_ref(),
            );
        }
        if emit_chain_checkpoint {
            if let Some(checkpoint) = successor_checkpoint {
                audit["chain_checkpoint"] = checkpoint;
            }
        }
        audit["chain_binding"] = chain_binding;
        Ok(ToolResult::structured_json(&audit))
    }
}

#[async_trait]
impl McpTool for ModelScopeAbotReceiptValidateTool {
    fn name(&self) -> &'static str {
        "modelscope_abot_receipt_validate"
    }

    fn schema(&self) -> ToolSchema {
        ToolSchema {
            name: self.name().into(),
            description: "Validate a ModelScope ABot success receipt or failure diagnostic locally. Read-only and offline: it never opens a browser, contacts the provider, or changes task state.".into(),
            input_schema: json!({
                "type": "object",
                "required": ["document"],
                "properties": {
                    "document": {
                        "type": "object",
                        "description": "Structured run receipt or failure diagnostics. Do not include a raw prompt."
                    }
                }
            }),
        }
    }

    async fn execute(&self, args: Value, _ctx: &ToolContext) -> Result<ToolResult> {
        let Some(document) = args.get("document") else {
            return Ok(ToolResult::error("missing 'document'"));
        };
        Ok(ToolResult::structured_json(&validate_abot_receipt(
            document,
        )))
    }
}

#[async_trait]
impl McpTool for ModelScopeAbotTaskStatusTool {
    fn name(&self) -> &'static str {
        "modelscope_abot_task_status"
    }

    fn schema(&self) -> ToolSchema {
        ToolSchema {
            name: self.name().into(),
            description: "Read one durable ModelScope ABot task record. A running record from an earlier MCP process is projected as interrupted and is never resumed automatically.".into(),
            input_schema: json!({
                "type": "object",
                "required": ["task_id"],
                "properties": {
                    "task_id": {"type": "string", "pattern": "^abot-task-[0-9a-f]{24}$"},
                    "include_receipt": {"type": "boolean", "default": true}
                }
            }),
        }
    }

    async fn execute(&self, args: Value, _ctx: &ToolContext) -> Result<ToolResult> {
        let Some(task_id) = args.get("task_id").and_then(Value::as_str) else {
            return Ok(ToolResult::error("missing 'task_id'"));
        };
        let valid = task_id.len() == "abot-task-".len() + 24
            && task_id.starts_with("abot-task-")
            && task_id["abot-task-".len()..]
                .chars()
                .all(|character| character.is_ascii_hexdigit() && !character.is_ascii_uppercase());
        if !valid {
            return Ok(ToolResult::error(
                "task_id must match ^abot-task-[0-9a-f]{24}$",
            ));
        }
        let record = match read_task(&task_path(task_id)) {
            Ok(Some(record)) => record,
            Ok(None) => return Ok(ToolResult::error(format!("task not found: {task_id}"))),
            Err(error) => return Ok(ToolResult::error(error)),
        };
        let include_receipt = args
            .get("include_receipt")
            .and_then(Value::as_bool)
            .unwrap_or(true);
        Ok(ToolResult::structured_json(&task_status_projection(
            record,
            include_receipt,
        )))
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn valid_args() -> Value {
        json!({
            "prompt": "A sunlit sandstone temple",
            "observe_ms": 10_000,
            "owner_confirmed": true,
        })
    }

    #[test]
    fn request_is_prompt_hash_bound_and_bounded() {
        let request = RunRequest::parse(&valid_args()).expect("valid request");
        assert_eq!(request.observe_ms, 10_000);
        assert_eq!(request.prompt_sha256.len(), 64);
        assert!(!request.prompt_sha256.contains("sandstone"));
    }

    fn verified_binding() -> Value {
        let request = RunRequest::parse(&valid_args()).expect("valid request");
        prompt_binding_evidence(&json!(request.prompt), &request)
    }

    #[test]
    fn receipt_validator_accepts_bounded_success_claim() {
        let result = validate_abot_receipt(&json!({
            "schema": "agent_bridge.modelscope_abot_run_once_receipt.v1",
            "status": "completed",
            "lifecycle_closed": true,
            "prompt_sha256": verified_binding()["expected_sha256"],
            "binding": {
                "status": "submission_bound_output_unverified",
                "prompt_submission": verified_binding(),
                "world_semantics_verified": false,
            }
        }));
        assert_eq!(result["status"], "accepted");
        assert_eq!(result["document_kind"], "success_receipt");
        assert_eq!(result["claims"]["prompt_submission_bound"], true);
        assert_eq!(result["claims"]["world_semantics_verified"], false);
        assert_eq!(result["runtime_effects"]["network_request_sent"], false);
    }

    #[test]
    fn receipt_validator_accepts_downstream_failure_binding() {
        let result = validate_abot_receipt(&json!({
            "schema": "agent_bridge.modelscope_abot_downstream_failure.v0",
            "prompt_binding": verified_binding(),
            "downstream_diagnostics": null,
        }));
        assert_eq!(result["status"], "accepted");
        assert_eq!(result["document_kind"], "downstream_failure");
        assert_eq!(result["violations"], json!([]));
    }

    #[test]
    fn receipt_validator_rejects_hash_drift_and_semantic_overclaim() {
        let mut binding = verified_binding();
        binding["observed_sha256"] = json!("0".repeat(64));
        let result = validate_abot_receipt(&json!({
            "schema": "agent_bridge.modelscope_abot_run_once_receipt.v1",
            "status": "completed",
            "lifecycle_closed": true,
            "prompt_sha256": verified_binding()["expected_sha256"],
            "binding": {
                "status": "submission_bound_output_unverified",
                "prompt_submission": binding,
                "world_semantics_verified": true,
            }
        }));
        assert_eq!(result["status"], "rejected");
        let violations = result["violations"].as_array().expect("violations");
        assert!(violations.contains(&json!("prompt_sha256_mismatch")));
        assert!(violations.contains(&json!("world_semantics_claim_exceeds_evidence")));
    }

    #[test]
    fn receipt_validator_rejects_unbound_or_unknown_documents() {
        let unbound = validate_abot_receipt(&json!({
            "schema": "agent_bridge.modelscope_abot_failure_diagnostics.v1"
        }));
        assert_eq!(unbound["status"], "rejected");
        assert_eq!(unbound["violations"], json!(["prompt_binding_missing"]));

        let unknown = validate_abot_receipt(&json!({
            "schema": "example.unknown.v0",
            "prompt_binding": verified_binding(),
        }));
        assert_eq!(unknown["document_kind"], "unknown");
        assert_eq!(
            unknown["violations"],
            json!(["unsupported_document_schema"])
        );
    }

    #[test]
    fn receipt_validator_rejects_nested_raw_prompt_fields() {
        let result = validate_abot_receipt(&json!({
            "schema": "agent_bridge.modelscope_abot_downstream_failure.v0",
            "prompt_binding": verified_binding(),
            "downstream_diagnostics": {"prompt_text": "must not persist"},
        }));
        assert_eq!(result["status"], "rejected");
        assert_eq!(result["violations"], json!(["raw_prompt_field_present"]));
    }

    #[test]
    fn receipt_audit_aggregates_mixed_history_without_runtime_effects() {
        let accepted = json!({
            "schema": "agent_bridge.modelscope_abot_downstream_failure.v0",
            "prompt_binding": verified_binding(),
            "downstream_diagnostics": null,
        });
        let rejected = json!({
            "schema": "agent_bridge.modelscope_abot_failure_diagnostics.v1"
        });
        let result = audit_abot_receipts(&[accepted, rejected]);
        assert_eq!(result["status"], "rejected");
        assert_eq!(result["summary"]["total"], 2);
        assert_eq!(result["summary"]["accepted"], 1);
        assert_eq!(result["summary"]["rejected"], 1);
        assert_eq!(result["summary"]["document_kinds"]["downstream_failure"], 2);
        assert_eq!(
            result["summary"]["violation_counts"]["prompt_binding_missing"],
            1
        );
        assert_eq!(result["claims"]["all_prompt_submissions_bound"], false);
        assert_eq!(result["claims"]["world_semantics_verified"], false);
        assert_eq!(result["runtime_effects"]["network_request_sent"], false);
        assert_eq!(result["runtime_effects"]["task_state_read"], false);
    }

    #[test]
    fn receipt_audit_accepts_all_bound_history() {
        let document = json!({
            "schema": "agent_bridge.modelscope_abot_downstream_failure.v0",
            "prompt_binding": verified_binding(),
            "downstream_diagnostics": null,
        });
        let result = audit_abot_receipts(&[document.clone(), document]);
        assert_eq!(result["status"], "accepted");
        assert_eq!(result["summary"]["accepted"], 2);
        assert_eq!(result["summary"]["violation_counts"], json!({}));
        assert_eq!(result["claims"]["all_prompt_submissions_bound"], true);
    }

    #[test]
    fn receipt_audit_digest_is_stable_across_object_key_order() {
        let left: Value = serde_json::from_str(
            r#"{"schema":"agent_bridge.modelscope_abot_downstream_failure.v0","prompt_binding":{"schema":"agent_bridge.modelscope_abot_prompt_binding.v0","readback_observed":true,"exact_match":true,"raw_prompt_recorded":false,"observed_sha256":"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa","expected_sha256":"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"},"downstream_diagnostics":null}"#,
        )
        .expect("left document");
        let right: Value = serde_json::from_str(
            r#"{"downstream_diagnostics":null,"prompt_binding":{"expected_sha256":"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa","observed_sha256":"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa","raw_prompt_recorded":false,"exact_match":true,"readback_observed":true,"schema":"agent_bridge.modelscope_abot_prompt_binding.v0"},"schema":"agent_bridge.modelscope_abot_downstream_failure.v0"}"#,
        )
        .expect("right document");

        let left_audit = audit_abot_receipts(&[left]);
        let right_audit = audit_abot_receipts(&[right]);
        assert_eq!(
            left_audit["evidence_binding"],
            right_audit["evidence_binding"]
        );
        assert_eq!(
            left_audit["evidence_binding"]["documents"][0]["sha256"]
                .as_str()
                .expect("document digest")
                .len(),
            64
        );
    }

    #[test]
    fn receipt_audit_digest_binds_content_and_document_order() {
        let first = json!({
            "schema": "agent_bridge.modelscope_abot_downstream_failure.v0",
            "prompt_binding": verified_binding(),
            "downstream_diagnostics": null,
        });
        let second = json!({
            "schema": "agent_bridge.modelscope_abot_failure_diagnostics.v1"
        });
        let original = audit_abot_receipts(&[first.clone(), second.clone()]);
        let reordered = audit_abot_receipts(&[second, first.clone()]);
        let changed = audit_abot_receipts(&[
            first,
            json!({
                "schema": "example.changed.v0"
            }),
        ]);

        assert_ne!(
            original["evidence_binding"]["batch_sha256"],
            reordered["evidence_binding"]["batch_sha256"]
        );
        assert_ne!(
            original["evidence_binding"]["batch_sha256"],
            changed["evidence_binding"]["batch_sha256"]
        );
        assert_eq!(
            original["evidence_binding"]["canonicalization"],
            "rfc8785.jcs.v1"
        );
    }

    #[test]
    fn receipt_audit_evidence_verification_accepts_exact_binding() {
        let document = json!({
            "schema": "agent_bridge.modelscope_abot_downstream_failure.v0",
            "prompt_binding": verified_binding(),
            "downstream_diagnostics": null,
        });
        let audit = audit_abot_receipts(&[document]);
        let verification =
            verify_audit_evidence_binding(&audit["evidence_binding"], &audit["evidence_binding"]);

        assert_eq!(verification["status"], "verified");
        assert_eq!(verification["violations"], json!([]));
        assert!(verification["claims"]
            .get("caller_supplied_checkpoint_bound")
            .is_none());
        assert_eq!(verification["claims"]["audit_evidence_bound"], true);
        assert!(verification.get("world_semantics_verified").is_none());
    }

    #[test]
    fn receipt_audit_evidence_verification_rejects_tampered_batch_digest() {
        let document = json!({
            "schema": "agent_bridge.modelscope_abot_downstream_failure.v0",
            "prompt_binding": verified_binding(),
            "downstream_diagnostics": null,
        });
        let audit = audit_abot_receipts(&[document]);
        let mut expected = audit["evidence_binding"].clone();
        expected["batch_sha256"] = json!("0".repeat(64));
        let verification = verify_audit_evidence_binding(&expected, &audit["evidence_binding"]);

        assert_eq!(verification["status"], "mismatch");
        assert_eq!(verification["violations"], json!(["batch_sha256_mismatch"]));
        assert_eq!(verification["claims"]["audit_evidence_bound"], false);
    }

    #[test]
    fn receipt_audit_evidence_verification_rejects_document_order_drift() {
        let first = json!({
            "schema": "agent_bridge.modelscope_abot_downstream_failure.v0",
            "prompt_binding": verified_binding(),
            "downstream_diagnostics": null,
        });
        let second = json!({"schema": "agent_bridge.modelscope_abot_failure_diagnostics.v1"});
        let original = audit_abot_receipts(&[first.clone(), second.clone()]);
        let reordered = audit_abot_receipts(&[second, first]);
        let verification = verify_audit_evidence_binding(
            &original["evidence_binding"],
            &reordered["evidence_binding"],
        );

        assert_eq!(verification["status"], "mismatch");
        assert_eq!(
            verification["violations"],
            json!(["document_manifest_mismatch", "batch_sha256_mismatch"])
        );
    }

    #[test]
    fn receipt_audit_evidence_verification_rejects_malformed_binding() {
        let document = json!({
            "schema": "agent_bridge.modelscope_abot_downstream_failure.v0",
            "prompt_binding": verified_binding(),
            "downstream_diagnostics": null,
        });
        let audit = audit_abot_receipts(&[document]);
        let verification = verify_audit_evidence_binding(
            &json!({"schema": "unexpected", "documents": "not-an-array"}),
            &audit["evidence_binding"],
        );

        assert_eq!(verification["status"], "mismatch");
        let violations = verification["violations"].as_array().expect("violations");
        assert!(violations.contains(&json!("evidence_binding_shape_mismatch")));
        assert!(violations.contains(&json!("evidence_schema_mismatch")));
        assert!(violations.contains(&json!("canonicalization_mismatch")));
        assert!(violations.contains(&json!("document_manifest_invalid")));
        assert!(violations.contains(&json!("batch_sha256_mismatch")));
    }

    #[test]
    fn receipt_audit_chain_constructs_and_verifies_genesis_link() {
        let document = json!({
            "schema": "agent_bridge.modelscope_abot_downstream_failure.v0",
            "prompt_binding": verified_binding(),
            "downstream_diagnostics": null,
        });
        let audit = audit_abot_receipts(&[document]);
        let binding = audit_chain_binding(&audit["evidence_binding"], None);
        let verification = verify_audit_chain_binding(&binding, &binding);

        assert_eq!(binding["previous_chain_sha256"], Value::Null);
        assert_eq!(
            binding["audit_batch_sha256"],
            audit["evidence_binding"]["batch_sha256"]
        );
        assert_eq!(binding["chain_sha256"].as_str().unwrap().len(), 64);
        assert_eq!(binding["claims"]["external_custody_verified"], false);
        assert_eq!(binding["claims"]["world_semantics_verified"], false);
        assert_eq!(verification["status"], "verified");
        assert_eq!(verification["violations"], json!([]));
        assert_eq!(verification["claims"]["audit_chain_bound"], true);
    }

    #[test]
    fn receipt_audit_chain_binds_predecessor_digest() {
        let document = json!({
            "schema": "agent_bridge.modelscope_abot_downstream_failure.v0",
            "prompt_binding": verified_binding(),
            "downstream_diagnostics": null,
        });
        let audit = audit_abot_receipts(&[document]);
        let left = audit_chain_binding(&audit["evidence_binding"], Some(&"1".repeat(64)));
        let right = audit_chain_binding(&audit["evidence_binding"], Some(&"2".repeat(64)));
        let verification = verify_audit_chain_binding(&left, &right);

        assert_ne!(left["chain_sha256"], right["chain_sha256"]);
        assert_eq!(verification["status"], "mismatch");
        assert_eq!(
            verification["violations"],
            json!(["previous_chain_sha256_mismatch", "chain_sha256_mismatch"])
        );
    }

    #[test]
    fn receipt_audit_chain_rejects_tampered_digest() {
        let document = json!({
            "schema": "agent_bridge.modelscope_abot_downstream_failure.v0",
            "prompt_binding": verified_binding(),
            "downstream_diagnostics": null,
        });
        let audit = audit_abot_receipts(&[document]);
        let actual = audit_chain_binding(&audit["evidence_binding"], None);
        let mut expected = actual.clone();
        expected["chain_sha256"] = json!("0".repeat(64));
        let verification = verify_audit_chain_binding(&expected, &actual);

        assert_eq!(verification["status"], "mismatch");
        assert_eq!(verification["violations"], json!(["chain_sha256_mismatch"]));
        assert_eq!(verification["claims"]["audit_chain_bound"], false);
    }

    #[test]
    fn receipt_audit_chain_rejects_malformed_binding() {
        let document = json!({
            "schema": "agent_bridge.modelscope_abot_downstream_failure.v0",
            "prompt_binding": verified_binding(),
            "downstream_diagnostics": null,
        });
        let audit = audit_abot_receipts(&[document]);
        let actual = audit_chain_binding(&audit["evidence_binding"], None);
        let verification = verify_audit_chain_binding(
            &json!({"schema": "unexpected", "chain_sha256": 7}),
            &actual,
        );

        assert_eq!(verification["status"], "mismatch");
        let violations = verification["violations"].as_array().unwrap();
        assert!(violations.contains(&json!("chain_binding_shape_mismatch")));
        assert!(violations.contains(&json!("chain_schema_mismatch")));
        assert!(violations.contains(&json!("canonicalization_mismatch")));
        assert!(violations.contains(&json!("previous_chain_sha256_mismatch")));
        assert!(violations.contains(&json!("audit_batch_sha256_mismatch")));
        assert!(violations.contains(&json!("chain_sha256_mismatch")));
        assert!(violations.contains(&json!("chain_claims_mismatch")));
    }

    fn three_link_audit_chain() -> (Vec<Value>, Value) {
        let document = json!({
            "schema": "agent_bridge.modelscope_abot_downstream_failure.v0",
            "prompt_binding": verified_binding(),
            "downstream_diagnostics": null,
        });
        let audit = audit_abot_receipts(&[document]);
        let first = audit_chain_binding(&audit["evidence_binding"], None);
        let second =
            audit_chain_binding(&audit["evidence_binding"], first["chain_sha256"].as_str());
        let current =
            audit_chain_binding(&audit["evidence_binding"], second["chain_sha256"].as_str());
        (vec![first, second], current)
    }

    #[test]
    fn receipt_audit_chain_history_verifies_ordered_links_and_current_join() {
        let (history, current) = three_link_audit_chain();
        let verification = verify_audit_chain_history(&history, &current, None);

        assert_eq!(verification["status"], "verified");
        assert_eq!(verification["history_link_count"], 2);
        assert_eq!(verification["total_link_count"], 3);
        assert_eq!(verification["chain_head_sha256"], current["chain_sha256"]);
        assert_eq!(verification["violations"], json!([]));
        assert_eq!(
            verification["claims"]["bounded_chain_continuity_verified"],
            true
        );
        assert_eq!(
            verification["claims"]["historical_source_documents_verified"],
            false
        );
        assert_eq!(verification["claims"]["external_custody_verified"], false);
        assert_eq!(verification["claims"]["world_semantics_verified"], false);
    }

    #[test]
    fn receipt_audit_chain_history_rejects_tampered_link_digest() {
        let (mut history, current) = three_link_audit_chain();
        history[0]["chain_sha256"] = json!("0".repeat(64));
        let verification = verify_audit_chain_history(&history, &current, None);
        let violations = verification["violations"].as_array().unwrap();

        assert_eq!(verification["status"], "mismatch");
        assert!(violations.contains(&json!({"index": 0, "code": "chain_sha256_mismatch"})));
        assert!(violations.contains(&json!({"index": 1, "code": "chain_continuity_mismatch"})));
        assert_eq!(
            verification["claims"]["bounded_chain_continuity_verified"],
            false
        );
    }

    #[test]
    fn receipt_audit_chain_history_rejects_reordered_links() {
        let (mut history, current) = three_link_audit_chain();
        history.swap(0, 1);
        let verification = verify_audit_chain_history(&history, &current, None);
        let violations = verification["violations"].as_array().unwrap();

        assert_eq!(verification["status"], "mismatch");
        assert!(violations.contains(&json!({"index": 1, "code": "chain_continuity_mismatch"})));
        assert!(
            violations.contains(&json!({"index": 2, "code": "current_link_predecessor_mismatch"}))
        );
    }

    #[test]
    fn receipt_audit_chain_history_rejects_self_valid_gap() {
        let (mut history, _) = three_link_audit_chain();
        let gap_predecessor = "f".repeat(64);
        let batch_sha256 = history[1]["audit_batch_sha256"]
            .as_str()
            .unwrap()
            .to_string();
        history[1] = audit_chain_binding(
            &json!({"batch_sha256": &batch_sha256}),
            Some(&gap_predecessor),
        );
        let current = audit_chain_binding(
            &json!({"batch_sha256": &batch_sha256}),
            history[1]["chain_sha256"].as_str(),
        );
        let verification = verify_audit_chain_history(&history, &current, None);

        assert_eq!(verification["status"], "mismatch");
        assert_eq!(
            verification["violations"],
            json!([{"index": 1, "code": "chain_continuity_mismatch"}])
        );
    }

    #[test]
    fn receipt_audit_chain_history_rejects_malformed_link() {
        let (_, current) = three_link_audit_chain();
        let verification = verify_audit_chain_history(
            &[json!({"schema": "unexpected", "chain_sha256": 7})],
            &current,
            None,
        );
        let violations = verification["violations"].as_array().unwrap();

        assert_eq!(verification["status"], "mismatch");
        assert!(violations.contains(&json!({"index": 0, "code": "chain_link_shape_mismatch"})));
        assert!(violations.contains(&json!({"index": 0, "code": "chain_schema_mismatch"})));
        assert!(violations.contains(&json!({"index": 0, "code": "chain_sha256_invalid"})));
        assert!(
            violations.contains(&json!({"index": 1, "code": "current_link_predecessor_mismatch"}))
        );
    }

    #[test]
    fn receipt_audit_chain_checkpoint_verifies_bounded_suffix_and_count() {
        let (history, current) = three_link_audit_chain();
        let checkpoint = audit_chain_checkpoint(history[0]["chain_sha256"].as_str().unwrap(), 1);
        let verification = verify_audit_chain_history(&history[1..], &current, Some(&checkpoint));

        assert_eq!(verification["status"], "verified");
        assert_eq!(verification["history_link_count"], 1);
        assert_eq!(verification["total_link_count"], 3);
        assert_eq!(verification["violations"], json!([]));
        assert_eq!(
            verification["claims"]["caller_supplied_checkpoint_bound"],
            true
        );
        assert_eq!(
            verification["claims"]["historical_source_documents_verified"],
            false
        );
        assert_eq!(verification["claims"]["external_custody_verified"], false);
        assert_eq!(verification["claims"]["world_semantics_verified"], false);
    }

    #[test]
    fn receipt_audit_chain_checkpoint_rejects_tampered_count() {
        let (history, current) = three_link_audit_chain();
        let mut checkpoint =
            audit_chain_checkpoint(history[0]["chain_sha256"].as_str().unwrap(), 1);
        checkpoint["total_link_count"] = json!(9);
        let verification = verify_audit_chain_history(&history[1..], &current, Some(&checkpoint));

        assert_eq!(verification["status"], "mismatch");
        assert!(verification["violations"]
            .as_array()
            .unwrap()
            .contains(&json!({"index": 0, "code": "chain_checkpoint_sha256_mismatch"})));
        assert_eq!(
            verification["claims"]["caller_supplied_checkpoint_bound"],
            false
        );
    }

    #[test]
    fn receipt_audit_chain_checkpoint_rejects_wrong_anchor() {
        let (history, current) = three_link_audit_chain();
        let checkpoint = audit_chain_checkpoint(&"f".repeat(64), 1);
        let verification = verify_audit_chain_history(&history[1..], &current, Some(&checkpoint));

        assert_eq!(verification["status"], "mismatch");
        assert_eq!(
            verification["violations"],
            json!([{"index": 0, "code": "chain_continuity_mismatch"}])
        );
    }

    #[test]
    fn receipt_audit_chain_checkpoint_is_deterministic_and_bounded() {
        let checkpoint = audit_chain_checkpoint(&"a".repeat(64), 257);
        let duplicate = audit_chain_checkpoint(&"a".repeat(64), 257);

        assert_eq!(checkpoint, duplicate);
        assert_eq!(checkpoint["total_link_count"], 257);
        assert_eq!(checkpoint["checkpoint_sha256"].as_str().unwrap().len(), 64);
        assert_eq!(
            checkpoint["claims"],
            json!({
                "checkpoint_integrity_bound": true,
                "historical_source_documents_verified": false,
                "external_custody_verified": false,
                "world_semantics_verified": false,
            })
        );
    }

    #[test]
    fn receipt_audit_chain_checkpoint_rejects_count_overflow() {
        let (history, current) = three_link_audit_chain();
        let checkpoint =
            audit_chain_checkpoint(history[0]["chain_sha256"].as_str().unwrap(), u64::MAX);
        let verification = verify_audit_chain_history(&history[1..], &current, Some(&checkpoint));

        assert_eq!(verification["status"], "mismatch");
        assert_eq!(verification["total_link_count"], Value::Null);
        assert!(verification["violations"]
            .as_array()
            .unwrap()
            .contains(&json!({"index": 0, "code": "chain_checkpoint_total_link_count_overflow"})));
    }

    #[test]
    fn receipt_audit_chain_checkpoint_output_requires_opt_in_and_verified_history() {
        let verified = json!({"status": "verified", "total_link_count": 3});
        let mismatch = json!({"status": "mismatch", "total_link_count": 3});

        assert_eq!(
            checkpoint_total_for_output(false, Some(&verified), true, false),
            None
        );
        assert_eq!(
            checkpoint_total_for_output(true, Some(&mismatch), true, false),
            None
        );
        assert_eq!(
            checkpoint_total_for_output(true, Some(&verified), true, false),
            Some(3)
        );
        assert_eq!(
            checkpoint_total_for_output(true, None, false, true),
            Some(1)
        );
    }

    #[tokio::test]
    async fn receipt_audit_tool_checkpoint_output_is_opt_in() {
        let document = json!({
            "schema": "agent_bridge.modelscope_abot_downstream_failure.v0",
            "prompt_binding": verified_binding(),
            "downstream_diagnostics": null,
        });
        let tool = ModelScopeAbotReceiptAuditTool;
        let legacy = tool
            .execute(
                json!({"documents": [document.clone()]}),
                &ToolContext::default(),
            )
            .await
            .unwrap();
        let opted_in = tool
            .execute(
                json!({"documents": [document], "emit_chain_checkpoint": true}),
                &ToolContext::default(),
            )
            .await
            .unwrap();

        assert!(legacy
            .structured_content
            .unwrap()
            .get("chain_checkpoint")
            .is_none());
        let payload = opted_in.structured_content.unwrap();
        let checkpoint = &payload["chain_checkpoint"];
        assert_eq!(checkpoint["total_link_count"], 1);
        assert_eq!(checkpoint["claims"]["checkpoint_integrity_bound"], true);
    }

    #[tokio::test]
    async fn receipt_audit_tool_does_not_emit_checkpoint_for_invalid_history() {
        let document = json!({
            "schema": "agent_bridge.modelscope_abot_downstream_failure.v0",
            "prompt_binding": verified_binding(),
            "downstream_diagnostics": null,
        });
        let tool = ModelScopeAbotReceiptAuditTool;
        let result = tool
            .execute(
                json!({
                    "documents": [document],
                    "chain_history": [{"schema": "unexpected"}],
                    "emit_chain_checkpoint": true,
                }),
                &ToolContext::default(),
            )
            .await
            .unwrap();
        let payload = result.structured_content.unwrap();

        assert_eq!(payload["chain_history_verification"]["status"], "mismatch");
        assert!(payload.get("chain_checkpoint").is_none());
    }

    #[test]
    fn receipt_audit_checkpoint_transition_verifies_exact_successor() {
        let (history, current) = three_link_audit_chain();
        let source = audit_chain_checkpoint(history[0]["chain_sha256"].as_str().unwrap(), 1);
        let history_verification =
            verify_audit_chain_history(&history[1..], &current, Some(&source));
        let successor = audit_chain_checkpoint(current["chain_sha256"].as_str().unwrap(), 3);
        let verification = verify_audit_chain_checkpoint_transition(
            &history_verification,
            &successor,
            Some(&successor),
        );

        assert_eq!(verification["status"], "verified");
        assert_eq!(verification["violations"], json!([]));
        assert_eq!(
            verification["claims"]["checkpoint_transition_verified"],
            true
        );
        assert_eq!(
            verification["claims"]["historical_source_documents_verified"],
            false
        );
        assert_eq!(verification["claims"]["external_custody_verified"], false);
        assert_eq!(verification["claims"]["world_semantics_verified"], false);
    }

    #[test]
    fn receipt_audit_checkpoint_transition_rejects_self_valid_wrong_successor() {
        let (history, current) = three_link_audit_chain();
        let source = audit_chain_checkpoint(history[0]["chain_sha256"].as_str().unwrap(), 1);
        let history_verification =
            verify_audit_chain_history(&history[1..], &current, Some(&source));
        let actual = audit_chain_checkpoint(current["chain_sha256"].as_str().unwrap(), 3);
        let expected = audit_chain_checkpoint(&"f".repeat(64), 3);
        let verification = verify_audit_chain_checkpoint_transition(
            &history_verification,
            &expected,
            Some(&actual),
        );

        assert_eq!(verification["status"], "mismatch");
        assert_eq!(
            verification["violations"],
            json!(["successor_chain_sha256_mismatch"])
        );
    }

    #[test]
    fn receipt_audit_checkpoint_transition_rejects_tampered_expected_digest() {
        let (history, current) = three_link_audit_chain();
        let source = audit_chain_checkpoint(history[0]["chain_sha256"].as_str().unwrap(), 1);
        let history_verification =
            verify_audit_chain_history(&history[1..], &current, Some(&source));
        let actual = audit_chain_checkpoint(current["chain_sha256"].as_str().unwrap(), 3);
        let mut expected = actual.clone();
        expected["checkpoint_sha256"] = json!("0".repeat(64));
        let verification = verify_audit_chain_checkpoint_transition(
            &history_verification,
            &expected,
            Some(&actual),
        );

        assert_eq!(verification["status"], "mismatch");
        assert!(verification["violations"]
            .as_array()
            .unwrap()
            .contains(&json!("expected_successor_sha256_mismatch")));
        assert_eq!(verification["violations"].as_array().unwrap().len(), 1);
    }

    #[test]
    fn receipt_audit_checkpoint_transition_rejects_unverified_source() {
        let expected = audit_chain_checkpoint(&"a".repeat(64), 3);
        let history_verification = json!({"status": "mismatch"});
        let verification =
            verify_audit_chain_checkpoint_transition(&history_verification, &expected, None);

        assert_eq!(verification["status"], "mismatch");
        assert_eq!(
            verification["violations"],
            json!(["source_transition_not_verified"])
        );
    }

    #[test]
    fn receipt_audit_checkpoint_candidates_verify_exact_agreement() {
        let (history, current) = three_link_audit_chain();
        let source = audit_chain_checkpoint(history[0]["chain_sha256"].as_str().unwrap(), 1);
        let history_verification =
            verify_audit_chain_history(&history[1..], &current, Some(&source));
        let candidate = audit_chain_checkpoint(current["chain_sha256"].as_str().unwrap(), 3);
        let verification = verify_audit_chain_checkpoint_candidates(
            &history_verification,
            &[candidate.clone(), candidate],
            Some(&audit_chain_checkpoint(
                current["chain_sha256"].as_str().unwrap(),
                3,
            )),
        );

        assert_eq!(verification["status"], "verified");
        assert_eq!(verification["candidate_count"], 2);
        assert_eq!(verification["unique_candidate_count"], 1);
        assert_eq!(
            verification["claims"]["candidate_consistency_verified"],
            true
        );
        assert_eq!(verification["claims"]["fork_detected"], false);
    }

    #[test]
    fn receipt_audit_checkpoint_candidates_detect_self_valid_fork() {
        let (history, current) = three_link_audit_chain();
        let source = audit_chain_checkpoint(history[0]["chain_sha256"].as_str().unwrap(), 1);
        let history_verification =
            verify_audit_chain_history(&history[1..], &current, Some(&source));
        let actual = audit_chain_checkpoint(current["chain_sha256"].as_str().unwrap(), 3);
        let alternate = audit_chain_checkpoint(&"f".repeat(64), 3);
        let verification = verify_audit_chain_checkpoint_candidates(
            &history_verification,
            &[actual.clone(), alternate],
            Some(&actual),
        );

        assert_eq!(verification["status"], "fork");
        assert_eq!(verification["unique_candidate_count"], 2);
        assert_eq!(
            verification["claims"]["candidate_consistency_verified"],
            false
        );
        assert_eq!(verification["claims"]["fork_detected"], true);
        assert!(verification["candidate_verifications"][1]["violations"]
            .as_array()
            .unwrap()
            .contains(&json!("candidate_successor_mismatch")));
    }

    #[test]
    fn receipt_audit_checkpoint_candidates_reject_tampered_candidate() {
        let (history, current) = three_link_audit_chain();
        let source = audit_chain_checkpoint(history[0]["chain_sha256"].as_str().unwrap(), 1);
        let history_verification =
            verify_audit_chain_history(&history[1..], &current, Some(&source));
        let actual = audit_chain_checkpoint(current["chain_sha256"].as_str().unwrap(), 3);
        let mut tampered = actual.clone();
        tampered["checkpoint_sha256"] = json!("0".repeat(64));
        let verification = verify_audit_chain_checkpoint_candidates(
            &history_verification,
            &[actual.clone(), tampered],
            Some(&actual),
        );

        assert_eq!(verification["status"], "mismatch");
        assert_eq!(verification["claims"]["fork_detected"], false);
        assert!(verification["candidate_verifications"][1]["violations"]
            .as_array()
            .unwrap()
            .contains(&json!("candidate_sha256_mismatch")));
    }

    #[tokio::test]
    async fn receipt_audit_tool_verifies_checkpoint_candidates_without_runtime_effects() {
        let document = json!({
            "schema": "agent_bridge.modelscope_abot_downstream_failure.v0",
            "prompt_binding": verified_binding(),
            "downstream_diagnostics": null,
        });
        let audit = audit_abot_receipts(std::slice::from_ref(&document));
        let first = audit_chain_binding(&audit["evidence_binding"], None);
        let second =
            audit_chain_binding(&audit["evidence_binding"], first["chain_sha256"].as_str());
        let current =
            audit_chain_binding(&audit["evidence_binding"], second["chain_sha256"].as_str());
        let source = audit_chain_checkpoint(first["chain_sha256"].as_str().unwrap(), 1);
        let candidate = audit_chain_checkpoint(current["chain_sha256"].as_str().unwrap(), 3);
        let result = ModelScopeAbotReceiptAuditTool
            .execute(
                json!({
                    "documents": [document],
                    "chain_checkpoint": source,
                    "chain_history": [second],
                    "successor_checkpoint_candidates": [candidate.clone(), candidate],
                }),
                &ToolContext::default(),
            )
            .await
            .unwrap();
        let payload = result.structured_content.unwrap();

        assert_eq!(
            payload["checkpoint_candidates_verification"]["status"],
            "verified"
        );
        assert!(payload.get("chain_checkpoint").is_none());
        assert_eq!(
            payload["runtime_effects"],
            json!({
                "network_request_sent": false,
                "browser_opened": false,
                "task_state_read": false,
                "task_state_written": false,
            })
        );
    }

    #[tokio::test]
    async fn receipt_audit_tool_verifies_expected_successor_without_emitting_it() {
        let document = json!({
            "schema": "agent_bridge.modelscope_abot_downstream_failure.v0",
            "prompt_binding": verified_binding(),
            "downstream_diagnostics": null,
        });
        let audit = audit_abot_receipts(std::slice::from_ref(&document));
        let first = audit_chain_binding(&audit["evidence_binding"], None);
        let second =
            audit_chain_binding(&audit["evidence_binding"], first["chain_sha256"].as_str());
        let current =
            audit_chain_binding(&audit["evidence_binding"], second["chain_sha256"].as_str());
        let source = audit_chain_checkpoint(first["chain_sha256"].as_str().unwrap(), 1);
        let expected = audit_chain_checkpoint(current["chain_sha256"].as_str().unwrap(), 3);
        let result = ModelScopeAbotReceiptAuditTool
            .execute(
                json!({
                    "documents": [document],
                    "chain_checkpoint": source,
                    "chain_history": [second],
                    "expected_successor_checkpoint": expected,
                }),
                &ToolContext::default(),
            )
            .await
            .unwrap();
        let payload = result.structured_content.unwrap();

        assert_eq!(
            payload["checkpoint_transition_verification"]["status"],
            "verified"
        );
        assert!(payload.get("chain_checkpoint").is_none());
        assert_eq!(
            payload["runtime_effects"],
            json!({
                "network_request_sent": false,
                "browser_opened": false,
                "task_state_read": false,
                "task_state_written": false,
            })
        );
    }

    #[tokio::test]
    async fn receipt_audit_tool_requires_source_for_expected_successor() {
        let result = ModelScopeAbotReceiptAuditTool
            .execute(
                json!({
                    "documents": [{}],
                    "expected_successor_checkpoint": {},
                }),
                &ToolContext::default(),
            )
            .await
            .unwrap();

        assert!(result.is_error);
    }

    #[test]
    fn request_rejects_missing_authority_and_bad_timeout() {
        let mut args = valid_args();
        args["owner_confirmed"] = json!(false);
        assert!(RunRequest::parse(&args)
            .unwrap_err()
            .contains("owner_confirmed"));
        args["owner_confirmed"] = json!(true);
        args["observe_ms"] = json!(MAX_OBSERVE_MS + 1);
        assert!(RunRequest::parse(&args).unwrap_err().contains("observe_ms"));
    }

    #[test]
    fn task_request_is_stable_and_digest_bound() {
        let mut args = valid_args();
        args["request_id"] = json!("gate8a-request-001");
        let request = RunRequest::parse(&args).expect("run request");
        let first = TaskRequest::parse(&args, &request)
            .expect("task request")
            .expect("present task");
        let second = TaskRequest::parse(&args, &request)
            .expect("task request")
            .expect("present task");
        assert_eq!(first.task_id, second.task_id);
        assert_eq!(first.request_digest, second.request_digest);
        assert!(first.task_id.starts_with("abot-task-"));

        args["observe_ms"] = json!(20_000);
        let changed = RunRequest::parse(&args).expect("changed run request");
        let changed = TaskRequest::parse(&args, &changed)
            .expect("changed task request")
            .expect("present task");
        assert_eq!(first.task_id, changed.task_id);
        assert_ne!(first.request_digest, changed.request_digest);

        args["observe_ms"] = json!(10_000);
        args["embodiment_intent_id"] = json!("different-intent");
        let changed_intent = RunRequest::parse(&args).expect("changed intent run request");
        let changed_intent = TaskRequest::parse(&args, &changed_intent)
            .expect("changed intent task request")
            .expect("present task");
        assert_eq!(first.task_id, changed_intent.task_id);
        assert_ne!(first.request_digest, changed_intent.request_digest);
    }

    #[test]
    fn task_record_replays_completed_and_projects_restart_interruption() {
        let mut args = valid_args();
        args["request_id"] = json!("gate8a-request-002");
        let request = RunRequest::parse(&args).expect("run request");
        let task = TaskRequest::parse(&args, &request)
            .expect("task request")
            .expect("present task");
        let lease = LeaseId::from_raw("lease-test");
        let running = running_task_record(&task, &request, &lease);
        let completed = completed_task_record(
            running.clone(),
            json!({"schema": "agent_bridge.modelscope_abot_run_once_receipt.v0"}),
        );
        let replay = inspect_existing_task(&task, &completed)
            .expect("completed inspection")
            .expect("replay receipt");
        assert_eq!(replay["task_protocol"]["idempotent_replay"], true);
        assert_eq!(
            replay["task_protocol"]["external_execution_repeated"],
            false
        );

        let mut prior_process = running;
        prior_process["process_instance_id"] = json!("mcp-prior-process");
        let projection = task_status_projection(prior_process, false);
        assert_eq!(projection["status"], "interrupted");
        assert_eq!(projection["failure_class"], "interrupted_after_restart");
        assert!(projection.get("receipt").is_none());
        assert_eq!(projection["status_projection_mutated_record"], false);
    }

    #[test]
    fn task_conflict_and_failure_classes_are_stable() {
        let mut args = valid_args();
        args["request_id"] = json!("gate8a-request-003");
        let request = RunRequest::parse(&args).expect("run request");
        let task = TaskRequest::parse(&args, &request)
            .expect("task request")
            .expect("present task");
        let mut record = running_task_record(&task, &request, &LeaseId::from_raw("lease-test"));
        record["request_digest"] = json!("different");
        assert!(inspect_existing_task(&task, &record)
            .unwrap_err()
            .contains("idempotency_conflict"));
        assert_eq!(
            classify_failure("Studio stream did not report positive FPS before deadline"),
            "provider_timeout"
        );
        assert_eq!(
            classify_failure("Studio lifecycle did not close"),
            "provider_lifecycle"
        );
    }

    #[test]
    fn attempt_preview_uses_execution_identity_without_owner_authority() {
        let args = json!({
            "prompt": "A sunlit sandstone temple",
            "observe_ms": 10_000,
            "request_id": "gate8c-preview-001",
            "embodiment_intent_id": "intent-preview-001",
        });
        let request = RunRequest::parse_inputs(&args).expect("preview request inputs");
        assert!(RunRequest::parse(&args)
            .unwrap_err()
            .contains("owner_confirmed"));
        let task = TaskRequest::parse(&args, &request)
            .expect("task request")
            .expect("request id present");
        assert_eq!(attempt_task_state(&task, None)["state"], "new_request");
        assert_eq!(
            attempt_task_state(&task, None)["external_execution_required"],
            true
        );
        assert_eq!(request.prompt_sha256.len(), 64);
        assert_eq!(task.request_digest.len(), 64);
    }

    #[test]
    fn attempt_preview_distinguishes_replay_conflict_and_terminal_states() {
        let mut args = valid_args();
        args["request_id"] = json!("gate8c-preview-002");
        let request = RunRequest::parse(&args).expect("run request");
        let task = TaskRequest::parse(&args, &request)
            .expect("task request")
            .expect("request id present");
        let running = running_task_record(&task, &request, &LeaseId::from_raw("lease-test"));
        let completed = completed_task_record(running.clone(), json!({"receipt": true}));
        assert_eq!(
            attempt_task_state(&task, Some(&completed))["state"],
            "completed_replay_available"
        );

        let failed = failed_task_record(running.clone(), "positive FPS missing", None);
        assert_eq!(
            attempt_task_state(&task, Some(&failed))["state"],
            "failed_requires_new_request_id"
        );

        let mut interrupted = running.clone();
        interrupted["process_instance_id"] = json!("mcp-prior-process");
        assert_eq!(
            attempt_task_state(&task, Some(&interrupted))["state"],
            "interrupted_requires_new_request_id"
        );

        let mut conflict = running;
        conflict["request_digest"] = json!("different");
        let conflict = attempt_task_state(&task, Some(&conflict));
        assert_eq!(conflict["state"], "idempotency_conflict");
        assert_eq!(conflict["requires_new_request_id"], true);
    }

    fn terminal_record(
        task_id: &str,
        status: &str,
        failure_class: Option<&str>,
        updated_at_unix_ms: u64,
    ) -> Value {
        json!({
            "schema": TASK_SCHEMA,
            "provider_id": PROVIDER_ID,
            "task_id": task_id,
            "status": status,
            "failure_class": failure_class,
            "updated_at_unix_ms": updated_at_unix_ms,
        })
    }

    #[test]
    fn provider_recovery_applies_bounded_cooldown_without_network_work() {
        let records = vec![
            terminal_record("newer", "failed", Some("provider_timeout"), 2_000),
            terminal_record("older", "failed", Some("provider_lifecycle"), 1_000),
            terminal_record("local", "failed", Some("browser_backend"), 3_000),
        ];
        let recovery = provider_recovery_state(&records, 2_500);
        assert_eq!(recovery["consecutive_provider_failures"], 2);
        assert_eq!(recovery["cooldown"]["active"], true);
        assert_eq!(recovery["cooldown"]["duration_ms"], 15 * 60_000);
        assert_eq!(
            recovery["cooldown"]["retry_not_before_unix_ms"],
            2_000 + 15 * 60_000
        );
        let error = provider_cooldown_error(&recovery).expect("active cooldown");
        assert!(error.contains("no external execution was started"));

        let elapsed = provider_recovery_state(&records, 2_000 + 15 * 60_000);
        assert_eq!(elapsed["cooldown"]["active"], false);
        assert!(provider_cooldown_error(&elapsed).is_none());
    }

    #[test]
    fn provider_success_resets_failure_streak() {
        let records = vec![
            terminal_record("failed", "failed", Some("provider_timeout"), 1_000),
            terminal_record("success", "completed", None, 2_000),
        ];
        let recovery = provider_recovery_state(&records, 2_500);
        assert_eq!(recovery["consecutive_provider_failures"], 0);
        assert_eq!(recovery["last_success_at_unix_ms"], 2_000);
        assert_eq!(recovery["cooldown"]["active"], false);
        assert_eq!(
            recovery["cooldown"]["retry_not_before_unix_ms"],
            Value::Null
        );
    }

    #[test]
    fn provider_health_record_validation_rejects_incomplete_history() {
        let valid = terminal_record(
            "abot-task-0123456789abcdef01234567",
            "failed",
            Some("provider_timeout"),
            1_000,
        );
        assert!(valid_provider_health_record(&valid));

        let mut missing_time = valid.clone();
        missing_time
            .as_object_mut()
            .expect("record object")
            .remove("updated_at_unix_ms");
        assert!(!valid_provider_health_record(&missing_time));

        let mut unknown_status = valid;
        unknown_status["status"] = json!("queued");
        assert!(!valid_provider_health_record(&unknown_status));
    }

    #[test]
    fn interrupted_prior_process_enters_recovery_cooldown() {
        let mut running = terminal_record(
            "abot-task-0123456789abcdef01234567",
            "running",
            None,
            10_000,
        );
        running["process_instance_id"] = json!("mcp-prior-process");
        let recovery = provider_recovery_state(&[running], 10_500);
        assert_eq!(recovery["consecutive_provider_failures"], 1);
        assert_eq!(recovery["cooldown"]["active"], true);
        assert_eq!(recovery["latest_terminal_task"]["status"], "interrupted");
        assert_eq!(
            recovery["latest_terminal_task"]["failure_class"],
            "interrupted_after_restart"
        );
    }

    #[test]
    fn task_record_atomic_roundtrip_preserves_digest() {
        let directory = tempfile::tempdir().expect("tempdir");
        let path = directory.path().join("abot-task-test.json");
        let record = json!({
            "schema": TASK_SCHEMA,
            "task_id": "abot-task-0123456789abcdef01234567",
            "request_digest": "digest-test",
            "status": "running",
        });
        atomic_write_json(&path, &record).expect("atomic write");
        let readback = read_task(&path).expect("read task").expect("task present");
        assert_eq!(readback, record);
        assert_eq!(
            fs::metadata(&path)
                .expect("task metadata")
                .permissions()
                .mode()
                & 0o777,
            0o600
        );
        assert_eq!(
            fs::metadata(directory.path())
                .expect("directory metadata")
                .permissions()
                .mode()
                & 0o777,
            0o700
        );
        assert!(directory
            .path()
            .read_dir()
            .expect("read directory")
            .all(|entry| !entry
                .expect("directory entry")
                .file_name()
                .to_string_lossy()
                .contains(".tmp-")));
    }

    #[test]
    fn selector_and_fps_parsers_accept_browser_payloads() {
        let candidates = json!([{"text": "start", "selector": "button:nth-of-type(1)"}]);
        assert_eq!(
            first_selector(&candidates).as_deref(),
            Some("button:nth-of-type(1)")
        );
        assert_eq!(
            observed_fps(&json!({"text": "GPU ready · 2.0 FPS"})),
            Some(2.0)
        );
        assert_eq!(
            frame_values(&json!({
                "count": 2,
                "frames": [{"kind": "main"}, {"kind": "oopif"}]
            }))
            .len(),
            2
        );
        assert!(frame_values(&json!([{"kind": "main"}])).is_empty());
    }

    #[test]
    fn prompt_binding_evidence_is_hash_bound_without_raw_prompt() {
        let request = RunRequest::parse(&valid_args()).expect("valid request");
        let matching = prompt_binding_evidence(&json!(request.prompt), &request);
        assert_eq!(matching["readback_observed"], true);
        assert_eq!(matching["exact_match"], true);
        assert_eq!(matching["observed_sha256"], request.prompt_sha256);
        assert_eq!(matching["expected_sha256"], request.prompt_sha256);
        assert_eq!(matching["raw_prompt_recorded"], false);
        assert!(!matching.to_string().contains("sandstone"));

        let mismatch = prompt_binding_evidence(&json!("different prompt"), &request);
        assert_eq!(mismatch["exact_match"], false);
        assert_ne!(mismatch["observed_sha256"], request.prompt_sha256);
        assert_eq!(
            classify_failure("Studio prompt binding readback did not exactly match"),
            "prompt_binding"
        );
    }

    #[test]
    fn verified_prompt_binding_survives_all_downstream_failure_shapes() {
        let request = RunRequest::parse(&valid_args()).expect("valid request");
        let binding = prompt_binding_evidence(&json!(request.prompt), &request);

        let mut timeout = RunFailure::with_diagnostics(
            "candidate runtime frame missing",
            json!({"schema": "agent_bridge.modelscope_abot_failure_diagnostics.v1"}),
        );
        attach_verified_prompt_binding(&mut timeout, binding.clone());
        let timeout_diagnostics = timeout.diagnostics.expect("timeout diagnostics");
        assert_eq!(timeout_diagnostics["prompt_binding"]["exact_match"], true);
        assert_eq!(
            timeout_diagnostics["schema"],
            "agent_bridge.modelscope_abot_failure_diagnostics.v1"
        );

        let mut lifecycle = RunFailure::new("Studio stop action failed");
        attach_verified_prompt_binding(&mut lifecycle, binding);
        let lifecycle_diagnostics = lifecycle.diagnostics.expect("lifecycle diagnostics");
        assert_eq!(
            lifecycle_diagnostics["schema"],
            "agent_bridge.modelscope_abot_downstream_failure.v0"
        );
        assert_eq!(
            lifecycle_diagnostics["prompt_binding"]["observed_sha256"],
            request.prompt_sha256
        );
        assert_eq!(lifecycle_diagnostics["downstream_diagnostics"], Value::Null);
        assert!(!lifecycle_diagnostics.to_string().contains("sandstone"));
    }

    #[test]
    fn failure_diagnostics_redact_frame_content_and_urls() {
        assert_eq!(
            frame_host("https://user:secret@example.com:443/path?token=x").as_deref(),
            Some("example.com")
        );
        assert_eq!(frame_host("not-a-url"), None);

        let text = "排队 loading then ERROR at 0 FPS; private provider detail";
        let signals = diagnostic_status_signals(text);
        assert_eq!(signals["fps_token_present"], true);
        assert_eq!(signals["queue_signal_present"], true);
        assert_eq!(signals["loading_signal_present"], true);
        assert_eq!(signals["error_signal_present"], true);
        assert!(!signals.to_string().contains("private provider detail"));

        let browser_error = "secret at https://example.com/?token=private";
        let redacted = redacted_error("frame_eval_failed", browser_error);
        assert_eq!(redacted["kind"], "frame_eval_failed");
        assert_eq!(redacted["message_sha256"].as_str().unwrap().len(), 64);
        assert!(!redacted.to_string().contains("private"));

        let failed = failed_task_record(
            json!({"status": "running"}),
            "positive FPS missing",
            Some(json!({"schema": "diagnostics-test"})),
        );
        assert_eq!(failed["diagnostics"]["schema"], "diagnostics-test");
    }

    #[test]
    fn frame_admission_excludes_presentation_media_consistently() {
        let main = json!({
            "frame_id": "main",
            "url": BASE_URL,
            "parent_id": Value::Null,
        });
        let youtube = json!({
            "frame_id": "video",
            "url": "https://www.youtube.com/embed/example?token=private",
            "parent_id": "main",
        });
        let runtime = json!({
            "frame_id": "runtime",
            "url": "https://runtime.example/session/opaque",
            "parent_id": "main",
        });
        let frames = vec![main.clone(), youtube.clone(), runtime.clone()];

        assert!(!is_candidate_runtime_frame(&main));
        assert!(!is_candidate_runtime_frame(&youtube));
        assert!(is_candidate_runtime_frame(&runtime));
        assert_eq!(child_frame_counts(&frames), (2, 1));
        assert!(is_ignored_presentation_host("YOUTUBE.COM."));
        assert_eq!(
            classify_failure("Studio did not expose a candidate runtime frame before deadline"),
            "provider_timeout"
        );
    }

    #[test]
    fn tool_stays_niche_and_declares_persistence_boundary() {
        let tool = ModelScopeAbotRunOnceTool::new(Hub::builder().build());
        assert_eq!(tool.name(), "modelscope_abot_run_once");
        let schema = tool.schema();
        assert_eq!(
            schema.input_schema["properties"]["owner_confirmed"]["const"],
            true
        );
        assert!(schema
            .description
            .contains("never creates a persistent runtime"));
        assert!(schema.input_schema["properties"]
            .get("request_id")
            .is_some());

        let status = ModelScopeAbotTaskStatusTool;
        assert_eq!(status.name(), "modelscope_abot_task_status");
        assert!(status.schema().description.contains("never resumed"));

        let provider = ModelScopeAbotProviderStatusTool::new(Hub::builder().build());
        assert_eq!(provider.name(), "modelscope_abot_provider_status");
        assert!(provider.schema().description.contains("Read-only"));
        assert!(provider.schema().description.contains("no network probe"));
    }
}
