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
//!   same-kind+SAME-SCOPE active row silently supersedes the older): neutralized
//!   by a DISTINCT per-artifact `scope = outcome:<artifact_id>` (see
//!   [`outcome_scope`]) — the candidate scan is `WHERE kind=?1 AND scope IS ?2`,
//!   so a distinct scope makes the candidate set a singleton and no peer is ever
//!   found. (The original "content stays token-overlap < 0.5" bet was FALSE —
//!   the Slice B review measured ~0.83 — so scope, not content, is the guard.)
//! - *idempotency*: the deterministic `outcome_<artifact_id>` key makes re-ingest
//!   an `ON CONFLICT(key)` update (not a duplicate). NOTE: `memory_search` only
//!   returns active rows, so the dry-run `active_row_exists` flag detects an
//!   existing ACTIVE row (a benign content refresh) but CANNOT see a
//!   superseded/tombstoned row (no non-mutating status-aware keyed read exists
//!   in the store trait) — it does not claim to. With the distinct-scope guard
//!   above, auto-supersede no longer manufactures retired rows, so the residual
//!   resurrection source is only manual delete/tombstone.
//! - *search/decay pollution*: `related_keys = []` (no graph edges in v0 → does
//!   not regress the orphan_fraction / PageRank-readiness #6 tracks) and the
//!   distinct kind/tags/scope let the cohort be filtered out of human-facing recall.

use ab_store::MemoryRecord;
use serde_json::Value;

/// The distinct memory `kind` for ingested verified outcomes. Used by NO other
/// writer so the auto-supersede candidate scan (`WHERE kind=?1 AND scope IS ?2`)
/// never pulls in unrelated kinds.
pub const OUTCOME_MEMORY_KIND: &str = "present_outcome";

/// Per-artifact scope for an outcome row: `outcome:<artifact_id>`.
///
/// **This is the load-bearing auto-supersede guard** (Slice B review fix). The
/// store's contradiction detector supersedes any *same-kind, same-scope* active
/// row whose token-overlap exceeds 0.5 (`store/sqlite.rs` candidate query
/// `WHERE kind=?1 AND (scope IS ?2) AND status='active'`). Outcome rows share a
/// kind AND their content is boilerplate-heavy (the embedded JSON field names
/// alone push pairwise Jaccard overlap to ~0.83 — well past 0.5), so a shared
/// scope would make the whole cohort mutually supersede down to ONE survivor.
/// A DISTINCT scope per artifact makes the candidate set a singleton → the
/// detector never finds a peer → every outcome row survives. `memory_search`
/// (the probe both Slice B tools use) does not filter on scope, so the rows
/// stay fully queryable; project-scoped human recall naturally excludes them.
pub fn outcome_scope(artifact_id: &str) -> String {
    format!("outcome:{artifact_id}")
}

/// Integrity admission check applied ON TOP of the verified gate, for both Slice
/// B consumers (ingest + drift). The gate (`outcome_gate`) admits an approval on
/// `decision ∈ {approved,rejected}` alone, but the approval card's authoritative
/// verdict also requires `token_match` (the rendered `#ab-token` matching the
/// daemon-minted token) — a DOM-tampered "approved" with `token_match:false` is
/// NOT a genuine human approval. The gate (output-lane-owned, separately tested)
/// does not see `token_match`, so we enforce it fail-closed here at the consumer:
/// a record carrying `token_match:false` is inadmissible (never minted, never
/// counted as a closable outcome). Records without a `token_match` field (every
/// non-approval present() outcome) are unaffected.
pub fn outcome_integrity_ok(record: &Value) -> bool {
    match record.get("token_match").and_then(Value::as_bool) {
        Some(false) => false,
        _ => true,
    }
}

/// Build the [`MemoryRecord`] a verified outcome record would persist, or `None`
/// if the record cannot be safely ingested (missing `artifact_id`).
///
/// PURE: no IO, no store, deterministic — unit-testable in isolation. The caller
/// is responsible for only passing gate-eligible records (the `outcomes` list of
/// `present_outcomes_projection(verified_only=true)`); this fn does not re-run
/// the gate, but it does refuse a keyless record so it can never mint garbage.
///
/// - `key = outcome_<artifact_id>` (deterministic → idempotent ON CONFLICT update)
/// - `kind = present_outcome` (distinct; no other writer uses it)
/// - `scope = outcome:<artifact_id>` (distinct PER ROW — the real auto-supersede
///   guard; see [`outcome_scope`]. NOT a content-overlap bet, which was false:
///   measured pairwise Jaccard is ~0.83.)
/// - `content` = human-readable head + embedded machine-readable JSON body
///   (dual-encoding; carries artifact_id+ts+intent+verify fields, plus
///   embody_status + chain_head provenance when the producer stamped them)
/// - `tags = [present_outcome, verified_outcome, auto_ingested, verify:<s>, method:<m>, embody:<e>?]`
/// - `related_keys = []` (graph-orphan by design in v0)
/// - `importance = 0.5` (the `importance_for_kind` fallback for an unknown kind)
pub fn build_outcome_memory(record: &Value, now: i64) -> Option<MemoryRecord> {
    let artifact_id = record.get("artifact_id").and_then(Value::as_str)?;
    if artifact_id.is_empty() {
        return None;
    }
    // Fail-closed integrity: a token-mismatched approval is not a genuine
    // verified outcome (see outcome_integrity_ok). Never mint it.
    if !outcome_integrity_ok(record) {
        return None;
    }
    let ts = record.get("ts").and_then(Value::as_u64).unwrap_or(0);
    // Cap intent before embedding (it is otherwise unbounded — present()/
    // present_await_decision write it verbatim). Without this, a pathologically
    // large intent pushes content past MEMORY_CONTENT_CAP (256 KiB) and the
    // store's clamp cuts inside the trailing JSON body, silently corrupting the
    // machine-readable dual-encoding while the row still saves. We also put the
    // JSON body FIRST below so the structured half survives even if a clamp
    // ever fires on the human tail.
    const INTENT_CAP: usize = 4096;
    let intent_full = record.get("intent").and_then(Value::as_str).unwrap_or("");
    let intent: String = if intent_full.chars().count() > INTENT_CAP {
        let mut s: String = intent_full.chars().take(INTENT_CAP).collect();
        s.push('…');
        s
    } else {
        intent_full.to_string()
    };
    let intent = intent.as_str();
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
    // Provenance forward (P-defer #2, thread 94): the dashboard stamps a REAL
    // embody_status and present()/dashboard now stamp chain_head. Carry both into
    // the durable memory body so a downstream consumer sees the SAME provenance the
    // Slice A stream (present_outcomes / outcomes_memory_drift) already sees, closing
    // the producer→memory provenance gap the adversarial review flagged. Additive
    // only — null for a present() render that carries no embody axis / no head.
    let embody_status = record.get("embody_status").and_then(Value::as_str);
    let chain_head = record
        .get("chain_head")
        .and_then(Value::as_str)
        .filter(|s| !s.is_empty());

    // Content: a human line + an embedded machine-readable JSON body
    // (dual-encoding; carries artifact_id+ts so the row is self-describing).
    // NOTE: content is NOT relied on to dodge auto-supersede — that guard is
    // the distinct per-artifact `scope` below (review found content overlap is
    // ~0.83, far above the 0.5 supersede threshold).
    let body = serde_json::json!({
        "artifact_id": artifact_id,
        "ts": ts,
        "intent": intent,
        "action_tool": action_tool,
        "present_kind": kind_label,
        "verify_status": verify_status,
        "verify_method": verify_method,
        "embody_status": embody_status,
        "decision": decision,
        "chain_head": chain_head,
    });
    let human = if intent.is_empty() {
        format!("verified outcome: {action_tool} {kind_label} → {verify_status} [{artifact_id}]")
    } else {
        format!("verified outcome: \"{intent}\" via {action_tool} {kind_label} → {verify_status} [{artifact_id}]")
    };
    // JSON body FIRST: with intent already capped, content stays well under the
    // 256 KiB cap, but ordering the machine-readable block ahead of the human
    // tail means even a future clamp would truncate prose, never the structured
    // dual-encoding payload.
    let content = format!(
        "```json ab-outcome\n{}\n```\n\n{human}",
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
    if let Some(e) = embody_status {
        tags.push(format!("embody:{e}"));
    }

    Some(MemoryRecord {
        key: format!("outcome_{artifact_id}"),
        kind: OUTCOME_MEMORY_KIND.to_string(),
        content,
        tags,
        related_keys: Vec::new(),
        scope: Some(outcome_scope(artifact_id)),
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
        assert_eq!(m.scope, Some("outcome:abc123def456".to_string()));
        assert_eq!(m.status, "active");
    }

    #[test]
    fn refuses_keyless_record() {
        assert!(build_outcome_memory(&json!({"ts": 1}), 0).is_none());
        assert!(build_outcome_memory(&json!({"artifact_id": ""}), 0).is_none());
    }

    #[test]
    fn distinct_scope_per_artifact_is_the_supersede_guard() {
        // Slice B review fix: the auto-supersede guard is the DISTINCT per-artifact
        // scope, NOT content variance (measured overlap ~0.83, far above 0.5).
        // The store's candidate scan is `WHERE kind=?1 AND (scope IS ?2)`, so two
        // outcome rows with different scopes are never mutual supersede candidates.
        let a = build_outcome_memory(&rec("aaaaaaaa1111"), 1).unwrap();
        let b = build_outcome_memory(&rec("bbbbbbbb2222"), 1).unwrap();
        assert_eq!(a.scope, Some("outcome:aaaaaaaa1111".to_string()));
        assert_eq!(b.scope, Some("outcome:bbbbbbbb2222".to_string()));
        assert_ne!(a.scope, b.scope, "distinct scope = distinct supersede candidate set");
        // same kind (cohort) but never same scope → singleton candidate set each.
        assert_eq!(a.kind, b.kind);
        assert_eq!(a.kind, "present_outcome");
        // content still carries the artifact_id for dual-encoding / self-describing.
        assert!(a.content.contains("aaaaaaaa1111"));
        assert!(b.content.contains("bbbbbbbb2222"));
    }

    #[test]
    fn scope_helper_matches_record() {
        let m = build_outcome_memory(&rec("c0ffee123456"), 0).unwrap();
        assert_eq!(m.scope, Some(outcome_scope("c0ffee123456")));
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

    #[test]
    fn forwards_embody_and_chain_head_provenance() {
        // P-defer #2 (thread 94): a dashboard outcome carries a REAL embody_status +
        // chain_head — both must reach the durable memory body + an `embody:<s>` tag
        // so a consumer of the memory row sees the SAME provenance the Slice A stream
        // (present_outcomes / drift) sees, closing the producer→memory gap.
        let dash = json!({
            "artifact_id": "_ab_dashboard",
            "ts": 1u64,
            "action_tool": "present_dashboard",
            "kind": "dashboard",
            "verify_status": "rendered_ok",
            "verify_method": "browser_eval",
            "embody_status": "embodied",
            "chain_head": "f4bbe660912587cd",
        });
        let m = build_outcome_memory(&dash, 0).unwrap();
        assert!(m.content.contains("\"embody_status\": \"embodied\""));
        assert!(m.content.contains("\"chain_head\": \"f4bbe660912587cd\""));
        assert!(m.tags.contains(&"embody:embodied".to_string()));

        // A present() outcome carries chain_head but NO embody axis: chain_head
        // forwards, embody_status is honestly null, and there is NO embody tag
        // (the absence is not silently turned into a claim).
        let plain = json!({
            "artifact_id": "plainprov0001",
            "ts": 1u64,
            "action_tool": "present",
            "kind": "table",
            "verify_status": "rendered_ok",
            "verify_method": "browser_eval",
            "chain_head": "deadbeefcafe0000",
        });
        let m2 = build_outcome_memory(&plain, 0).unwrap();
        assert!(m2.content.contains("\"chain_head\": \"deadbeefcafe0000\""));
        assert!(m2.content.contains("\"embody_status\": null"));
        assert!(!m2.tags.iter().any(|t| t.starts_with("embody:")));
    }

    #[test]
    fn refuses_token_mismatched_approval() {
        // MED fix: a DOM-tampered approval (decision=approved but token_match=false)
        // is NOT a genuine verified outcome — must never be minted.
        let tampered = json!({
            "artifact_id": "tampered01234",
            "ts": 1u64,
            "action_tool": "present_await_decision",
            "kind": "approval",
            "verify_status": "rendered_ok",
            "verify_method": "human_decision",
            "decision": "approved",
            "token_match": false,
        });
        assert!(build_outcome_memory(&tampered, 0).is_none());
        assert!(!outcome_integrity_ok(&tampered));
        // genuine approval (token_match=true) is admitted.
        let genuine = json!({
            "artifact_id": "genuine012345",
            "ts": 1u64,
            "action_tool": "present_await_decision",
            "kind": "approval",
            "verify_status": "rendered_ok",
            "verify_method": "human_decision",
            "decision": "approved",
            "token_match": true,
        });
        assert!(build_outcome_memory(&genuine, 0).is_some());
        assert!(outcome_integrity_ok(&genuine));
        // present() outcomes carry no token_match field → unaffected.
        assert!(outcome_integrity_ok(&rec("plain00001234")));
    }

    #[test]
    fn oversized_intent_capped_and_json_body_first() {
        // MED fix: unbounded intent must be capped so content stays under the
        // 256 KiB store cap, and the JSON body must come FIRST so a clamp can
        // never corrupt the machine-readable dual-encoding.
        let huge = "x".repeat(100_000);
        let v = json!({
            "artifact_id": "bigintent0001",
            "ts": 1u64,
            "action_tool": "present",
            "kind": "table",
            "verify_status": "rendered_ok",
            "verify_method": "browser_eval",
            "intent": huge,
        });
        let m = build_outcome_memory(&v, 0).unwrap();
        // content far below the 256 KiB cap despite a 100k-char intent.
        assert!(m.content.len() < 16_384, "content len = {}", m.content.len());
        // JSON body precedes the human tail.
        assert!(m.content.starts_with("```json ab-outcome"));
        // the embedded body's intent is the capped form (truncation marker).
        assert!(m.content.contains('…'));
    }

    #[test]
    fn never_fabricates_graph_signal() {
        // **Anti-fabrication invariant (Slice B graph-design verdict, thread 94).**
        // The graph-design workflow (3 lenses, unanimous) ruled that outcome rows
        // must NOT receive minted edges: cofires/co_referenced are the ONLY edge
        // types PageRank/hebbian_clusters/M5 consume, and they are EARNED via
        // record_coactivation → dream promote on REAL co-fire. Minting any edge at
        // ingest time fabricates the exact signal #6 measures (the decorative-edge
        // / surprise-starvation anti-pattern). build_outcome_memory must therefore
        // NEVER populate related_keys (a row-local hyperlink list that doesn't even
        // enter the PageRank subgraph) and the ingest tool must never write
        // memory_edges. This test locks the row half so a future edge-mint cannot
        // land silently; the "no memory_edges write" half is enforced structurally
        // (PresentOutcomesIngestTool::execute calls only memory_save, never
        // memory_link — there is no edge-writing call site in the Slice B path).
        for (aid, decision) in [
            ("orphan00aaaa", None),
            ("orphan00bbbb", Some("approved")),
        ] {
            let mut v = rec(aid);
            if let Some(d) = decision {
                v["action_tool"] = json!("present_await_decision");
                v["kind"] = json!("approval");
                v["verify_method"] = json!("human_decision");
                v["decision"] = json!(d);
                v["token_match"] = json!(true);
            }
            let m = build_outcome_memory(&v, 0).expect("builds");
            assert!(
                m.related_keys.is_empty(),
                "Slice B must never mint related_keys (graph-orphan by design); got {:?}",
                m.related_keys
            );
            assert!(
                m.superseded_by.is_none() && m.trigger_pattern.is_none(),
                "no synthetic graph/structural fields"
            );
        }
    }
}
