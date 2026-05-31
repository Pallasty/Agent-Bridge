//! Output / expression lane — **Slice B (v0) outcome → memory ingestion**.
//!
//! Slice A (`present_outcomes`, read-only) turned the lane's falsifier-LABELED
//! render results into a queryable verified (intent→action→outcome) stream of
//! `<id>.outcome.json` sidecars. Slice B is the CONSUMER: it can persist the
//! gate-eligible verified outcomes as ordinary memory rows so they join the
//! coactivation/PageRank graph the memory substrate (#6) is growing.
//!
//! **Discipline (why this is a separate, opt-in, dry-run-default tool):**
//! - The *always-on* Slice B surface is the read-only `outcomes_memory_drift`
//!   projection (in `present.rs` / `mcp_tools.rs`). Ingestion here is
//!   **opt-in, `dry_run=true` by default, never automatic** (no session_finalize
//!   hook), and **capped** — a human/operator closes the loop on evidence.
//! - **Additive only**: writes ordinary [`MemoryRecord`]s via the existing
//!   `memory_save`. NO new column, NO new table, NO `event_spine` write
//!   (that is #6 / #56 territory; the #56 owner session is stopped).
//! - **Gate is inherited, never re-implemented**: this module only ever sees
//!   records already filtered by `present_outcomes_projection(verified_only=true)`
//!   → `outcome_gate`. [`build_outcome_memory`] additionally returns `None` for
//!   any record missing an `artifact_id`, so it can never mint a keyless row.
//!
//! **Write-path hazards (verified in `store/sqlite.rs`) and how v0 neutralizes
//! them — see the Slice B design audit:**
//! - *auto-supersede clobber* (a new active row with >0.5 token overlap vs a
//!   same-kind+same-scope active row silently supersedes the older): isolated by
//!   a DISTINCT `kind = "present_outcome"` used by no other writer, AND by
//!   embedding the artifact_id+ts in the content so rows stay lexically varied
//!   (token overlap < 0.5).
//! - *idempotency / resurrection*: the deterministic `outcome_<artifact_id>` key
//!   makes re-ingest an `ON CONFLICT(key)` update (not a duplicate). The caller
//!   must surface that ON CONFLICT resurrects a superseded/tombstoned row to
//!   active — the dry-run report's `already_present` flag exposes this before any
//!   write.
//! - *search/decay pollution*: `related_keys = []` (no graph edges in v0 → does
//!   not regress the orphan_fraction / PageRank-readiness #6 tracks) and the
//!   distinct kind/tags let the cohort be filtered out of human-facing recall.

use ab_store::MemoryRecord;
use serde_json::Value;

/// The distinct memory `kind` for ingested verified outcomes. Used by NO other
/// writer so the auto-supersede candidate scan (`WHERE kind=?1 AND scope IS ?2`)
/// is isolated to this cohort and can never clobber unrelated rows.
pub const OUTCOME_MEMORY_KIND: &str = "present_outcome";

/// Build the [`MemoryRecord`] a verified outcome record would persist, or `None`
/// if the record cannot be safely ingested (missing `artifact_id`).
///
/// PURE: no IO, no store, deterministic — unit-testable in isolation. The caller
/// is responsible for only passing gate-eligible records (the `outcomes` list of
/// `present_outcomes_projection(verified_only=true)`); this fn does not re-run
/// the gate, but it does refuse a keyless record so it can never mint garbage.
///
/// - `key = outcome_<artifact_id>` (deterministic → idempotent ON CONFLICT update)
/// - `kind = present_outcome` (distinct; isolates auto-supersede candidate set)
/// - `content` embeds artifact_id+ts+intent+verify fields as a compact, VARIED,
///   self-contained JSON line (human-readable head + machine-readable body) so
///   token overlap between rows stays < 0.5
/// - `tags = [present_outcome, verified_outcome, auto_ingested, verify:<s>, method:<m>]`
/// - `related_keys = []` (graph-orphan by design in v0)
/// - `importance = 0.5` (the `importance_for_kind` fallback for an unknown kind)
pub fn build_outcome_memory(record: &Value, now: i64) -> Option<MemoryRecord> {
    let artifact_id = record.get("artifact_id").and_then(Value::as_str)?;
    if artifact_id.is_empty() {
        return None;
    }
    let ts = record.get("ts").and_then(Value::as_u64).unwrap_or(0);
    let intent = record.get("intent").and_then(Value::as_str).unwrap_or("");
    let action_tool = record
        .get("action_tool")
        .and_then(Value::as_str)
        .unwrap_or("present");
    let verify_status = record
        .get("verify_status")
        .and_then(Value::as_str)
        .unwrap_or("");
    let verify_method = record
        .get("verify_method")
        .and_then(Value::as_str)
        .unwrap_or("");
    let kind_label = record.get("kind").and_then(Value::as_str).unwrap_or("");
    let decision = record.get("decision").and_then(Value::as_str);

    // Content: a human line + an embedded machine-readable JSON body, both
    // carrying artifact_id+ts so the row text is lexically varied (anti
    // auto-supersede) and self-describing. NOT a fixed boilerplate skeleton.
    let body = serde_json::json!({
        "artifact_id": artifact_id,
        "ts": ts,
        "intent": intent,
        "action_tool": action_tool,
        "present_kind": kind_label,
        "verify_status": verify_status,
        "verify_method": verify_method,
        "decision": decision,
    });
    let human = if intent.is_empty() {
        format!("verified outcome: {action_tool} {kind_label} → {verify_status} [{artifact_id}]")
    } else {
        format!("verified outcome: \"{intent}\" via {action_tool} {kind_label} → {verify_status} [{artifact_id}]")
    };
    let content = format!(
        "{human}\n\n```json ab-outcome\n{}\n```",
        serde_json::to_string_pretty(&body).unwrap_or_else(|_| body.to_string())
    );

    let mut tags = vec![
        OUTCOME_MEMORY_KIND.to_string(),
        "verified_outcome".to_string(),
        "auto_ingested".to_string(),
    ];
    if !verify_status.is_empty() {
        tags.push(format!("verify:{verify_status}"));
    }
    if !verify_method.is_empty() {
        tags.push(format!("method:{verify_method}"));
    }
    if let Some(d) = decision {
        tags.push(format!("decision:{d}"));
    }

    Some(MemoryRecord {
        key: format!("outcome_{artifact_id}"),
        kind: OUTCOME_MEMORY_KIND.to_string(),
        content,
        tags,
        related_keys: Vec::new(),
        scope: None,
        created_at: now,
        updated_at: now,
        last_accessed_at: now,
        access_count: 0,
        importance: 0.5,
        status: "active".to_string(),
        trigger_pattern: None,
        superseded_by: None,
    })
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::json;

    fn rec(artifact_id: &str) -> Value {
        json!({
            "artifact_id": artifact_id,
            "ts": 1_780_000_000u64,
            "intent": "show the deploy table",
            "action_tool": "present",
            "kind": "table",
            "verify_status": "rendered_ok",
            "verify_method": "browser_eval",
        })
    }

    #[test]
    fn builds_deterministic_key_and_distinct_kind() {
        let m = build_outcome_memory(&rec("abc123def456"), 42).expect("builds");
        assert_eq!(m.key, "outcome_abc123def456");
        assert_eq!(m.kind, OUTCOME_MEMORY_KIND);
        assert_eq!(m.kind, "present_outcome");
        assert_eq!(m.importance, 0.5);
        assert!(m.related_keys.is_empty(), "v0 is graph-orphan by design");
        assert_eq!(m.scope, None);
        assert_eq!(m.status, "active");
    }

    #[test]
    fn refuses_keyless_record() {
        assert!(build_outcome_memory(&json!({"ts": 1}), 0).is_none());
        assert!(build_outcome_memory(&json!({"artifact_id": ""}), 0).is_none());
    }

    #[test]
    fn content_is_varied_per_artifact_anti_supersede() {
        // Two different artifacts must produce content with <0.5 token overlap
        // failure mode avoided: the artifact_id + ts appear in BOTH the human
        // line and the JSON body, so the rows differ substantially.
        let a = build_outcome_memory(&rec("aaaaaaaa1111"), 1).unwrap();
        let b = build_outcome_memory(&rec("bbbbbbbb2222"), 1).unwrap();
        assert_ne!(a.content, b.content);
        assert!(a.content.contains("aaaaaaaa1111"));
        assert!(b.content.contains("bbbbbbbb2222"));
    }

    #[test]
    fn carries_verify_and_method_tags() {
        let m = build_outcome_memory(&rec("c0ffee123456"), 0).unwrap();
        assert!(m.tags.contains(&"present_outcome".to_string()));
        assert!(m.tags.contains(&"verified_outcome".to_string()));
        assert!(m.tags.contains(&"auto_ingested".to_string()));
        assert!(m.tags.contains(&"verify:rendered_ok".to_string()));
        assert!(m.tags.contains(&"method:browser_eval".to_string()));
    }

    #[test]
    fn approval_decision_record_carries_decision_tag() {
        let v = json!({
            "artifact_id": "dec1a5100000",
            "ts": 1u64,
            "action_tool": "present_await_decision",
            "kind": "approval",
            "verify_status": "rendered_ok",
            "verify_method": "human_decision",
            "decision": "approved",
        });
        let m = build_outcome_memory(&v, 0).unwrap();
        assert!(m.tags.contains(&"decision:approved".to_string()));
        assert!(m.content.contains("dec1a5100000"));
    }

    #[test]
    fn content_embeds_machine_readable_body() {
        let m = build_outcome_memory(&rec("feed1234abcd"), 0).unwrap();
        assert!(m.content.contains("```json ab-outcome"));
        assert!(m.content.contains("\"artifact_id\": \"feed1234abcd\""));
    }
}
