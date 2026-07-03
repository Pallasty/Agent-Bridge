//! memory_biocortex T5–T7 continuity surfaces: shadow trial, redacted evidence aggregate, recall-expansion / relevance-lift summaries, the T6 candidate-expansion gate ceremony family, and the neural-critic shadow eval.
//! Extracted verbatim from `mcp_tools.rs` (2026-07 split, step 2); the
//! only mechanical delta is `pub(super)` on previously-private top-level
//! items (114 promoted) so the parent module and its other children
//! (tests.rs) keep seeing them through the parent's glob re-export.

use super::*;

// ===========================================================================
//          memory_biocortex_shadow_trial — T5 AB candidate shadow packet
// ===========================================================================

pub struct MemoryBioCortexShadowTrialTool {
    hub: Hub,
}
impl MemoryBioCortexShadowTrialTool {
    pub fn new(hub: Hub) -> Self {
        Self { hub }
    }
}
#[async_trait]
impl McpTool for MemoryBioCortexShadowTrialTool {
    fn name(&self) -> &'static str {
        "memory_biocortex_shadow_trial"
    }
    fn schema(&self) -> ToolSchema {
        ToolSchema {
            name: self.name().into(),
            description: "Read-only T5 BioCortex shadow-trial packet for AB memory. \
                Calls baseline memory_search, gathers graph-neighborhood slices and \
                T4 consolidation feedback buckets, then emits redacted hashes/counts \
                plus a deterministic suppression/advisory-order control. It does not \
                run BioCortex, mutate memory, expose raw keys/content, or change \
                default retrieval order."
                .into(),
            input_schema: json!({
                "type": "object",
                "required": ["query"],
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Baseline memory_search query. Output includes only a hash."
                    },
                    "tags_any": {
                        "type": "array",
                        "items": { "type": "string" },
                        "default": [],
                        "description": "Optional tag filter forwarded to baseline memory_search."
                    },
                    "limit": {
                        "type": "integer",
                        "minimum": 1,
                        "maximum": 100,
                        "default": 10,
                        "description": "Baseline candidate limit."
                    },
                    "scope": {
                        "type": "string",
                        "description": "Optional memory scope for the T4 queue slice, e.g. project:/abs/path."
                    },
                    "scope_mode": {
                        "type": "string",
                        "enum": ["local_only", "local_plus_global", "exploratory"],
                        "default": "local_plus_global",
                        "description": "Scope matching mode for the T4 queue slice."
                    },
                    "neighbor_limit": {
                        "type": "integer",
                        "minimum": 0,
                        "maximum": 50,
                        "default": 8,
                        "description": "Maximum graph-neighbor rows collected per baseline candidate."
                    },
                    "queue_max_records": {
                        "type": "integer",
                        "minimum": 1,
                        "maximum": 10000,
                        "default": 1000,
                        "description": "Maximum records scanned for the embedded T4 queue summary."
                    },
                    "queue_max_per_bucket": {
                        "type": "integer",
                        "minimum": 1,
                        "maximum": 100,
                        "default": 20,
                        "description": "Maximum candidates per T4 bucket before redaction/counting."
                    }
                }
            }),
        }
    }

    async fn execute(&self, args: Value, _ctx: &ToolContext) -> Result<ToolResult> {
        let store = match &self.hub.store {
            Some(s) => s.clone(),
            None => return Ok(ToolResult::error("no store configured")),
        };
        let query = match args
            .get("query")
            .and_then(Value::as_str)
            .map(str::trim)
            .filter(|s| !s.is_empty())
        {
            Some(query) => query.to_string(),
            None => return Ok(ToolResult::error("missing or empty 'query'")),
        };
        let tags_any = memory_string_array_arg(&args, "tags_any", &[]);
        let limit = args
            .get("limit")
            .and_then(Value::as_u64)
            .unwrap_or(10)
            .clamp(1, 100) as u32;
        let neighbor_limit = args
            .get("neighbor_limit")
            .and_then(Value::as_u64)
            .unwrap_or(8)
            .min(50) as usize;
        let queue_max_records = args
            .get("queue_max_records")
            .and_then(Value::as_u64)
            .unwrap_or(1000)
            .clamp(1, 10_000) as u32;
        let queue_max_per_bucket = args
            .get("queue_max_per_bucket")
            .and_then(Value::as_u64)
            .unwrap_or(20)
            .clamp(1, 100) as usize;
        let requested_scope = args
            .get("scope")
            .and_then(Value::as_str)
            .map(str::trim)
            .filter(|s| !s.is_empty());
        let scope_mode = MemorySearchScopeMode::parse(
            args.get("scope_mode")
                .and_then(Value::as_str)
                .map(str::trim)
                .filter(|s| !s.is_empty()),
            true,
        );

        let baseline_hits = store.memory_search(&query, &tags_any, limit).await?;
        let baseline_keys: Vec<String> = baseline_hits
            .iter()
            .map(|hit| hit.record.key.clone())
            .collect();

        let mut neighborhood_rows = Vec::new();
        for (idx, hit) in baseline_hits.iter().enumerate() {
            let key = &hit.record.key;
            let edges = store.memory_neighbors(key).await.unwrap_or_default();
            for edge in edges.into_iter().take(neighbor_limit) {
                let neighbor = if edge.from_key == *key {
                    Some(edge.to_key.as_str())
                } else if edge.to_key == *key {
                    Some(edge.from_key.as_str())
                } else {
                    None
                };
                let Some(neighbor_key) = neighbor else {
                    continue;
                };
                neighborhood_rows.push(json!({
                    "source_rank": idx + 1,
                    "source_key_hash": memory_biocortex_key_hash(key),
                    "neighbor_key_hash": memory_biocortex_key_hash(neighbor_key),
                    "edge_type": edge.edge_type,
                    "weight": edge.weight,
                }));
            }
        }

        let queue_rows = store
            .list_memories(None, MemoryListSort::Recent, queue_max_records)
            .await
            .unwrap_or_default();
        let queue_records: Vec<MemoryRecord> = queue_rows
            .into_iter()
            .filter(|rec| {
                memory_record_active(rec)
                    && requested_scope
                        .map(|scope| memory_search_scope_mode_matches(rec, scope, scope_mode))
                        .unwrap_or(true)
            })
            .collect();
        let mut queue_edges_by_key: HashMap<String, Vec<MemoryEdge>> = HashMap::new();
        for rec in &queue_records {
            if let Ok(edges) = store.memory_neighbors(&rec.key).await {
                queue_edges_by_key.insert(rec.key.clone(), edges);
            }
        }
        let queue = memory_consolidation_queue_from_records(
            &queue_records,
            &queue_edges_by_key,
            MemoryConsolidationQueueOptions {
                max_per_bucket: queue_max_per_bucket,
                max_gated_actions: 50,
                preview_chars: 0,
                large_content_chars: 2_400,
                low_use_max_access_count: 1,
            },
        );
        let suppression_map = memory_biocortex_suppression_map(&queue);
        let alternate_keys = memory_biocortex_alternate_order(&baseline_keys, &suppression_map);
        let suppressed_baseline_count = baseline_keys
            .iter()
            .filter(|key| suppression_map.contains_key(*key))
            .count();
        let alternate_order_changed = baseline_keys != alternate_keys;

        Ok(ToolResult::json_text(&json!({
            "schema": "agent_bridge.memory_biocortex_shadow_trial.v0",
            "generated_at": unix_now_secs(),
            "read_only": true,
            "purpose": "T5 shadow packet: compare default AB baseline candidates with graph/T3/T4-derived suppression/advisory controls before any BioCortex runtime influence.",
            "input_contract": {
                "raw_query_included": false,
                "raw_keys_included": false,
                "content_included": false,
                "candidate_content_included": false,
                "unknown_fields_ignored": true,
            },
            "query": {
                "hash": memory_biocortex_sha256_json(&json!({"query": query})),
                "tag_filter_count": tags_any.len(),
                "limit": limit,
            },
            "baseline": {
                "source": "memory_search",
                "key_count": baseline_keys.len(),
                "order_hash": memory_biocortex_order_hash("baseline", &baseline_keys),
                "top_key_hash": baseline_keys
                    .first()
                    .map(|key| Value::String(memory_biocortex_key_hash(key)))
                    .unwrap_or(Value::Null),
                "redacted_rank_rows": memory_biocortex_redacted_rank_rows(&baseline_keys, "baseline_rank"),
                "raw_keys_included": false,
                "content_included": false,
            },
            "graph_neighborhood": {
                "baseline_key_count": baseline_keys.len(),
                "neighbor_row_count": neighborhood_rows.len(),
                "neighbor_limit_per_baseline_key": neighbor_limit,
                "rows": neighborhood_rows,
                "raw_keys_included": false,
                "content_included": false,
            },
            "consolidation_queue": {
                "schema": queue.get("schema").cloned().unwrap_or(Value::Null),
                "scanned_records": queue.pointer("/summary/scanned_records").cloned().unwrap_or(Value::Null),
                "bucket_counts": memory_biocortex_bucket_counts(&queue),
                "raw_rows_included": false,
            },
            "suppression_set": {
                "source": "t3_t4_feedback_buckets",
                "source_buckets": ["duplicate_lessons", "stale_warnings", "harmful_memories", "too_large_memories"],
                "redacted_count": suppression_map.len(),
                "suppressed_baseline_count": suppressed_baseline_count,
                "redacted_rows": memory_biocortex_redacted_suppression_rows(&suppression_map),
                "raw_keys_included": false,
            },
            "advisory_control_order": {
                "source": "deterministic_t3_t4_suppression_control",
                "key_count": alternate_keys.len(),
                "order_hash": memory_biocortex_order_hash("deterministic_t3_t4_control", &alternate_keys),
                "redacted_rank_rows": memory_biocortex_redacted_rank_rows(&alternate_keys, "advisory_control_rank"),
                "alternate_order_changed": alternate_order_changed,
                "used_for_return_order": false,
                "raw_keys_included": false,
                "content_included": false,
            },
            "biocortex_runtime_path": {
                "adapter_run_in_this_tool": false,
                "next_existing_tools": [
                    "biocortex_retrieval_opt_in_dry_run",
                    "biocortex_retrieval_opt_in_review_packet",
                    "biocortex_retrieval_opt_in_execution_packet",
                    "biocortex_retrieval_opt_in_runtime_trial",
                    "biocortex_retrieval_opt_in_order_diff_packet",
                    "biocortex_retrieval_relevance_lift_eval"
                ],
                "candidate_content_required_later": true,
                "candidate_content_included_now": false,
            },
            "current_biocortex_frontier": {
                "thread": 89,
                "latest_position": "substrate_discovered_selection_is_open_frontier",
                "stale_s93_s94_s95_sequence_avoided": true,
                "discovered_selection_claimed": false,
                "bio_cortex_as_agent_cognitive_substrate_extension": true,
            },
            "comparison": {
                "baseline_returned": true,
                "actual_return_order_changed": false,
                "alternate_order_changed": alternate_order_changed,
                "suppressed_baseline_count": suppressed_baseline_count,
            },
            "non_goals": [
                "Does not run BioCortex or claim substrate-discovered selection.",
                "Does not change memory_search order or bootstrap selection.",
                "Does not write memory, graph edges, approval packets, or runtime influence decisions.",
                "Does not include raw query, memory keys, or memory content."
            ],
            "calls_memory_search": true,
            "calls_memory_neighbors": true,
            "runs_biocortex": false,
            "writes_memory": false,
            "changes_memory_search_order": false,
            "default_search_order_change_allowed": false,
        })))
    }
}

pub(super) const MEMORY_BIOCORTEX_T6_INFLUENCE_GATE_SCHEMA: &str =
    "agent_bridge.memory_biocortex_t6_influence_gate.v0";
pub(super) const MEMORY_BIOCORTEX_SHADOW_TRIAL_SCHEMA: &str = "agent_bridge.memory_biocortex_shadow_trial.v0";
pub(super) const MEMORY_BIOCORTEX_RECALL_EXPANSION_SUMMARY_SCHEMA: &str =
    "agent_bridge.memory_biocortex.recall_expansion_summary.v0";
pub(super) const BIOCORTEX_RETRIEVAL_RELEVANCE_LIFT_EVAL_SCHEMA_LOCAL: &str =
    "agent_bridge.biocortex_retrieval.relevance_lift_eval.v0";
pub(super) const BIOCORTEX_RETRIEVAL_REDACTED_EVIDENCE_AGGREGATE_SCHEMA_LOCAL: &str =
    "agent_bridge.biocortex_retrieval.opt_in_redacted_evidence_aggregate.v0";

pub(super) fn memory_biocortex_value_u64_at(value: &Value, path: &str) -> u64 {
    value.pointer(path).and_then(Value::as_u64).unwrap_or(0)
}

pub(super) fn memory_biocortex_value_bool_at(value: &Value, path: &str) -> Option<bool> {
    value.pointer(path).and_then(Value::as_bool)
}

pub(super) fn memory_biocortex_shadow_raw_flags_ok(value: &Value) -> bool {
    !memory_biocortex_t6_has_raw_payload_fields(value)
        && !memory_biocortex_t6_any_true(
            value,
            &[
                "/input_contract/raw_query_included",
                "/input_contract/raw_keys_included",
                "/input_contract/raw_queries_included",
                "/input_contract/content_included",
                "/input_contract/candidate_content_included",
                "/baseline/raw_keys_included",
                "/baseline/content_included",
                "/graph_neighborhood/raw_keys_included",
                "/graph_neighborhood/content_included",
                "/suppression_set/raw_keys_included",
                "/advisory_control_order/raw_keys_included",
                "/advisory_control_order/content_included",
            ],
        )
}

pub(super) fn memory_biocortex_redacted_evidence_aggregate_payload(args: Value) -> Value {
    let min_shadow_trials = args
        .get("min_shadow_trials")
        .and_then(Value::as_u64)
        .unwrap_or(3)
        .clamp(1, 100);
    let shadow_trials = args
        .get("shadow_trials")
        .and_then(Value::as_array)
        .cloned()
        .unwrap_or_default();
    let mut block_reasons = BTreeSet::<String>::new();
    if shadow_trials.len() < min_shadow_trials as usize {
        memory_biocortex_t6_push_reason(&mut block_reasons, "insufficient_shadow_trials");
    }

    let mut baseline_returned_count = 0u64;
    let mut baseline_candidate_count = 0u64;
    let mut graph_neighbor_row_count = 0u64;
    let mut suppressed_baseline_count = 0u64;
    let mut suppression_redacted_count = 0u64;
    let mut alternate_order_changed_count = 0u64;
    let mut read_only_count = 0u64;
    let mut raw_flags_ok_count = 0u64;
    let mut frontier_safe_count = 0u64;

    for shadow in &shadow_trials {
        if memory_biocortex_t6_string_at(shadow, "/schema")
            != Some(MEMORY_BIOCORTEX_SHADOW_TRIAL_SCHEMA)
        {
            memory_biocortex_t6_push_reason(&mut block_reasons, "shadow_schema_invalid");
        }
        if memory_biocortex_t6_bool_at(shadow, "/read_only") != Some(true) {
            memory_biocortex_t6_push_reason(&mut block_reasons, "shadow_not_read_only");
        } else {
            read_only_count += 1;
        }
        if memory_biocortex_t6_bool_at(shadow, "/runs_biocortex") != Some(false) {
            memory_biocortex_t6_push_reason(&mut block_reasons, "shadow_runs_biocortex");
        }
        if memory_biocortex_t6_bool_at(shadow, "/writes_memory") == Some(true) {
            memory_biocortex_t6_push_reason(&mut block_reasons, "shadow_writes_memory");
        }
        if memory_biocortex_t6_bool_at(shadow, "/changes_memory_search_order") != Some(false) {
            memory_biocortex_t6_push_reason(
                &mut block_reasons,
                "shadow_changes_memory_search_order",
            );
        }
        if memory_biocortex_shadow_raw_flags_ok(shadow) {
            raw_flags_ok_count += 1;
        } else {
            memory_biocortex_t6_push_reason(
                &mut block_reasons,
                "shadow_raw_query_key_or_content_included",
            );
        }
        if memory_biocortex_t6_bool_at(
            shadow,
            "/current_biocortex_frontier/discovered_selection_claimed",
        ) == Some(false)
        {
            frontier_safe_count += 1;
        } else {
            memory_biocortex_t6_push_reason(
                &mut block_reasons,
                "shadow_frontier_claimed_discovered_selection",
            );
        }

        if memory_biocortex_value_bool_at(shadow, "/comparison/baseline_returned") == Some(true) {
            baseline_returned_count += 1;
        }
        if memory_biocortex_value_bool_at(shadow, "/comparison/alternate_order_changed")
            == Some(true)
        {
            alternate_order_changed_count += 1;
        }
        baseline_candidate_count += memory_biocortex_value_u64_at(shadow, "/baseline/key_count");
        graph_neighbor_row_count +=
            memory_biocortex_value_u64_at(shadow, "/graph_neighborhood/neighbor_row_count");
        suppressed_baseline_count +=
            memory_biocortex_value_u64_at(shadow, "/comparison/suppressed_baseline_count");
        suppression_redacted_count +=
            memory_biocortex_value_u64_at(shadow, "/suppression_set/redacted_count");
    }

    let aggregate_evidence_ready = block_reasons.is_empty();
    let block_reasons = block_reasons.into_iter().collect::<Vec<_>>();

    json!({
        "schema": BIOCORTEX_RETRIEVAL_REDACTED_EVIDENCE_AGGREGATE_SCHEMA_LOCAL,
        "generated_at": unix_now_secs(),
        "read_only": true,
        "redacted_evidence_aggregate": true,
        "implementation_stage": "memory_continuity_t5_redacted_evidence_aggregate",
        "purpose": "Aggregate redacted T5 memory_biocortex_shadow_trial packets into the schema consumed by the T6 influence gate. This does not run BioCortex, call memory_search, write memory, echo shadow packets, or change retrieval order.",
        "input_contract": {
            "shadow_trials_included": false,
            "movement_fixture_run_included": false,
            "coverage_fixture_run_included": false,
            "raw_queries_included": false,
            "raw_query_included": false,
            "raw_keys_included": false,
            "content_included": false,
            "side_signal_raw_included": false,
        },
        "shadow_evidence": {
            "shadow_trial_count": shadow_trials.len(),
            "min_shadow_trials": min_shadow_trials,
            "baseline_returned_count": baseline_returned_count,
            "baseline_candidate_count": baseline_candidate_count,
            "graph_neighbor_row_count": graph_neighbor_row_count,
            "suppression_redacted_count": suppression_redacted_count,
            "suppressed_baseline_count": suppressed_baseline_count,
            "alternate_order_changed_count": alternate_order_changed_count,
        },
        "movement_evidence": {
            "raw_flags_all_false": raw_flags_ok_count == shadow_trials.len() as u64,
            "movement_observed": alternate_order_changed_count > 0,
            "actual_return_order_changed": false,
        },
        "coverage_evidence": {
            "raw_flags_all_false": raw_flags_ok_count == shadow_trials.len() as u64,
            "graph_neighborhood_observed": graph_neighbor_row_count > 0,
            "baseline_candidates_observed": baseline_candidate_count > 0,
            "expanded_coverage_observed": graph_neighbor_row_count > baseline_candidate_count,
        },
        "safety": {
            "shadow_trials_read_only_count": read_only_count,
            "raw_flags_ok_count": raw_flags_ok_count,
            "frontier_safe_count": frontier_safe_count,
            "calls_memory_search": false,
            "runs_biocortex": false,
            "writes_memory": false,
            "changes_memory_search_order": false,
            "default_search_order_change_allowed": false,
        },
        "interpretation": {
            "aggregate_evidence_ready": aggregate_evidence_ready,
            "controlled_rank_movement_observed": alternate_order_changed_count > 0,
            "expanded_coverage_without_additional_movement": graph_neighbor_row_count > 0 && alternate_order_changed_count == 0,
            "default_influence_ready": false,
            "human_review_required": true,
            "review_state": if aggregate_evidence_ready { "redacted_aggregate_ready" } else { "blocked" },
            "block_reasons": block_reasons,
        },
        "approval_state": "evidence_aggregate_only",
        "authorization_state": "does_not_grant_runtime_influence",
        "approval_writes_allowed": false,
        "writes_approval": false,
        "calls_memory_search": false,
        "runs_biocortex": false,
        "registers_embedding_backend": false,
        "changes_memory_search_order": false,
        "default_search_order_change_allowed": false,
        "default_calls_unchanged": true,
    })
}

// ===========================================================================
//          memory_biocortex_redacted_evidence_aggregate — T5 aggregate
// ===========================================================================

pub struct MemoryBioCortexRedactedEvidenceAggregateTool;

impl MemoryBioCortexRedactedEvidenceAggregateTool {
    pub fn new() -> Self {
        Self
    }
}

#[async_trait]
impl McpTool for MemoryBioCortexRedactedEvidenceAggregateTool {
    fn name(&self) -> &'static str {
        "memory_biocortex_redacted_evidence_aggregate"
    }

    fn schema(&self) -> ToolSchema {
        ToolSchema {
            name: self.name().into(),
            description: "Read-only T5 evidence aggregate for AB memory BioCortex shadow trials. \
                Consumes redacted memory_biocortex_shadow_trial packets and emits the \
                redacted aggregate schema expected by the T6 influence gate. It never \
                runs BioCortex, calls memory_search, writes memory, echoes raw packets, \
                exposes raw queries/keys/content, or changes retrieval order."
                .into(),
            input_schema: json!({
                "type": "object",
                "properties": {
                    "shadow_trials": {
                        "type": "array",
                        "items": { "type": "object" },
                        "default": [],
                        "description": "T5 memory_biocortex_shadow_trial outputs. Output never echoes them."
                    },
                    "min_shadow_trials": {
                        "type": "integer",
                        "minimum": 1,
                        "maximum": 100,
                        "default": 3
                    }
                }
            }),
        }
    }

    async fn execute(&self, args: Value, _ctx: &ToolContext) -> Result<ToolResult> {
        Ok(ToolResult::json_text(
            &memory_biocortex_redacted_evidence_aggregate_payload(args),
        ))
    }
}

pub(super) fn memory_biocortex_relevance_lift_summary_payload(payload: Value) -> Value {
    let class_aggregates =
        memory_biocortex_relevance_lift_summary_class_aggregates(&payload);
    let mut summary = json!({
        "schema": payload.get("schema").cloned().unwrap_or(Value::Null),
        "generated_at": payload.get("generated_at").cloned().unwrap_or(Value::Null),
        "status": payload.get("status").cloned().unwrap_or(Value::Null),
        "purpose": payload.get("purpose").cloned().unwrap_or(Value::Null),
        "verdict": payload.get("verdict").cloned().unwrap_or(Value::Null),
        "sampling": payload.get("sampling").cloned().unwrap_or(Value::Null),
        "metrics": payload.get("metrics").cloned().unwrap_or(Value::Null),
        "class_aggregates": class_aggregates,
        "caveats": payload.get("caveats").cloned().unwrap_or(Value::Null),
        "safety": payload.get("safety").cloned().unwrap_or(Value::Null),
        "input_contract": {
            "source_eval_included": false,
            "samples_included": false,
            "first_side_signal_error_included": false,
            "raw_query_included": false,
            "raw_queries_included": false,
            "raw_keys_included": false,
            "content_included": false,
            "side_signal_raw_included": false,
        }
    });
    if let Some(obj) = summary.as_object_mut() {
        obj.retain(|_, value| !value.is_null());
    }
    summary
}

pub(super) fn memory_biocortex_relevance_lift_summary_class_aggregates(payload: &Value) -> Value {
    const ALLOWED_FIELDS: &[&str] = &[
        "class_label",
        "evaluated_count",
        "source_found_count",
        "mrr_baseline",
        "mrr_reordered",
        "mrr_lift",
        "recall_baseline",
        "recall_reordered",
        "recall_lift",
        "improved",
        "worsened",
        "unchanged",
        "order_changed_count",
        "verdict",
    ];

    let rows = payload
        .get("class_aggregates")
        .and_then(Value::as_array)
        .map(|items| {
            items
                .iter()
                .filter_map(|item| item.as_object())
                .map(|item| {
                    let mut row = Map::new();
                    for field in ALLOWED_FIELDS {
                        if let Some(value) = item.get(*field) {
                            row.insert((*field).to_string(), value.clone());
                        }
                    }
                    Value::Object(row)
                })
                .filter(|row| row.as_object().map_or(false, |obj| !obj.is_empty()))
                .collect::<Vec<_>>()
        })
        .unwrap_or_default();

    Value::Array(rows)
}

// ===========================================================================
//   memory_biocortex_recall_expansion_summary — baseline-miss graph evidence
// ===========================================================================

#[derive(Debug, Clone)]
pub(super) struct MemoryBioCortexRecallExpansionCase {
    query: String,
    relevant_keys: Vec<String>,
    class_label: Option<String>,
    case_source: String,
}

pub(super) fn memory_biocortex_recall_expansion_cases_from_args(
    args: &Value,
) -> Vec<MemoryBioCortexRecallExpansionCase> {
    args.get("query_cases")
        .and_then(Value::as_array)
        .map(|cases| {
            cases
                .iter()
                .filter_map(|case| {
                    let query = case
                        .get("query")
                        .and_then(Value::as_str)
                        .map(str::trim)
                        .filter(|query| !query.is_empty())?
                        .to_string();
                    let relevant_keys = case
                        .get("relevant_keys")
                        .and_then(Value::as_array)
                        .map(|keys| {
                            keys.iter()
                                .filter_map(Value::as_str)
                                .map(str::trim)
                                .filter(|key| !key.is_empty())
                                .map(str::to_string)
                                .collect::<Vec<_>>()
                        })
                        .unwrap_or_default();
                    if relevant_keys.is_empty() {
                        return None;
                    }
                    let class_label = case
                        .get("class_label")
                        .and_then(Value::as_str)
                        .map(str::trim)
                        .filter(|label| !label.is_empty())
                        .map(str::to_string);
                    Some(MemoryBioCortexRecallExpansionCase {
                        query,
                        relevant_keys,
                        class_label,
                        case_source: "explicit".to_string(),
                    })
                })
                .take(30)
                .collect::<Vec<_>>()
        })
        .unwrap_or_default()
}

pub(super) fn memory_biocortex_recall_expansion_strip_frontmatter(content: &str) -> &str {
    let trimmed = content.trim_start();
    if let Some(rest) = trimmed.strip_prefix("---") {
        if let Some(end) = rest.find("\n---") {
            return rest[end + 4..].trim_start();
        }
    }
    trimmed
}

pub(super) fn memory_biocortex_recall_expansion_derive_query(content: &str, max_chars: usize) -> String {
    let body = memory_biocortex_recall_expansion_strip_frontmatter(content);
    let cleaned = body
        .chars()
        .map(|c| if c.is_alphanumeric() { c } else { ' ' })
        .collect::<String>();
    cleaned
        .split_whitespace()
        .collect::<Vec<_>>()
        .join(" ")
        .to_lowercase()
        .chars()
        .take(max_chars.clamp(16, 400))
        .collect()
}

pub(super) fn memory_biocortex_recall_expansion_neighbor_key(edge: &MemoryEdge, source_key: &str) -> Option<String> {
    if edge.from_key == source_key {
        Some(edge.to_key.clone())
    } else if edge.to_key == source_key {
        Some(edge.from_key.clone())
    } else {
        None
    }
}

pub(super) async fn memory_biocortex_recall_expansion_graph_holdout_cases(
    store: &dyn StateStore,
    sample_size: usize,
    candidate_limit: u32,
    query_chars: usize,
) -> Vec<MemoryBioCortexRecallExpansionCase> {
    let candidates = store
        .list_memories(None, MemoryListSort::Recent, candidate_limit)
        .await
        .unwrap_or_default();
    let mut seen_edges = BTreeSet::<(String, String)>::new();
    let mut cases = Vec::new();
    for rec in candidates {
        let query = memory_biocortex_recall_expansion_derive_query(&rec.content, query_chars);
        if query.is_empty() {
            continue;
        }
        let edges = store.memory_neighbors(&rec.key).await.unwrap_or_default();
        for edge in edges {
            let Some(target_key) =
                memory_biocortex_recall_expansion_neighbor_key(&edge, &rec.key)
            else {
                continue;
            };
            if target_key == rec.key {
                continue;
            }
            let pair = if rec.key <= target_key {
                (rec.key.clone(), target_key.clone())
            } else {
                (target_key.clone(), rec.key.clone())
            };
            if !seen_edges.insert(pair) {
                continue;
            }
            cases.push(MemoryBioCortexRecallExpansionCase {
                query: query.clone(),
                relevant_keys: vec![target_key],
                class_label: Some("graph_holdout".to_string()),
                case_source: "graph_holdout".to_string(),
            });
            break;
        }
        if cases.len() >= sample_size {
            break;
        }
    }
    cases
}

pub(super) fn memory_biocortex_recall_expansion_round3(value: f64) -> f64 {
    (value * 1000.0).round() / 1000.0
}

pub(super) fn memory_biocortex_recall_expansion_class_label(label: Option<&str>) -> String {
    let cleaned = label
        .unwrap_or("unlabeled")
        .chars()
        .map(|c| {
            if c.is_ascii_alphanumeric() || matches!(c, '_' | '-' | '.') {
                c
            } else {
                '_'
            }
        })
        .collect::<String>();
    let trimmed = cleaned.trim_matches('_');
    if trimmed.is_empty() {
        "unlabeled".to_string()
    } else {
        trimmed.chars().take(64).collect()
    }
}

pub(super) fn memory_biocortex_recall_expansion_first_relevant_position(
    ordered_keys: &[String],
    relevant: &BTreeSet<String>,
) -> Option<usize> {
    ordered_keys
        .iter()
        .position(|key| relevant.contains(key))
        .map(|idx| idx + 1)
}

pub(super) fn memory_biocortex_recall_expansion_class_row(class_label: String, rows: &[Value]) -> Value {
    let evaluated_count = rows.len() as u64;
    let search_error_count = rows
        .iter()
        .filter(|row| row["status"] == json!("search_error"))
        .count() as u64;
    let baseline_hit_count = rows
        .iter()
        .filter(|row| row["status"] == json!("baseline_hit"))
        .count() as u64;
    let baseline_miss_count = rows
        .iter()
        .filter(|row| {
            row["status"] == json!("graph_expansion_found")
                || row["status"] == json!("graph_expansion_miss")
        })
        .count() as u64;
    let graph_expansion_found_count = rows
        .iter()
        .filter(|row| row["status"] == json!("graph_expansion_found"))
        .count() as u64;
    let graph_expansion_miss_count = rows
        .iter()
        .filter(|row| row["status"] == json!("graph_expansion_miss"))
        .count() as u64;
    let graph_neighbor_row_count = rows
        .iter()
        .map(|row| row["graph_neighbor_row_count"].as_u64().unwrap_or(0))
        .sum::<u64>();
    let candidate_expansion_added_hit_count = rows
        .iter()
        .filter(|row| {
            row["baseline_relevant_count"].as_u64().unwrap_or(0) == 0
                && row["expanded_relevant_count"].as_u64().unwrap_or(0) > 0
        })
        .count() as u64;
    let expanded_hit_count = rows
        .iter()
        .filter(|row| row["expanded_relevant_count"].as_u64().unwrap_or(0) > 0)
        .count() as u64;

    json!({
        "class_label": class_label,
        "evaluated_count": evaluated_count,
        "search_error_count": search_error_count,
        "baseline_hit_count": baseline_hit_count,
        "baseline_miss_count": baseline_miss_count,
        "graph_expansion_found_count": graph_expansion_found_count,
        "graph_expansion_miss_count": graph_expansion_miss_count,
        "graph_neighbor_row_count": graph_neighbor_row_count,
        "expanded_hit_count": expanded_hit_count,
        "candidate_expansion_added_hit_count": candidate_expansion_added_hit_count,
        "candidate_expansion_added_hit_rate": if baseline_miss_count > 0 {
            memory_biocortex_recall_expansion_round3(
                candidate_expansion_added_hit_count as f64 / baseline_miss_count as f64,
            )
        } else {
            0.0
        },
        "graph_expansion_found_rate": if baseline_miss_count > 0 {
            memory_biocortex_recall_expansion_round3(
                graph_expansion_found_count as f64 / baseline_miss_count as f64,
            )
        } else {
            0.0
        },
    })
}

pub struct MemoryBioCortexRecallExpansionSummaryTool {
    hub: Hub,
}

impl MemoryBioCortexRecallExpansionSummaryTool {
    pub fn new(hub: Hub) -> Self {
        Self { hub }
    }
}

#[async_trait]
impl McpTool for MemoryBioCortexRecallExpansionSummaryTool {
    fn name(&self) -> &'static str {
        "memory_biocortex_recall_expansion_summary"
    }

    fn schema(&self) -> ToolSchema {
        ToolSchema {
            name: self.name().into(),
            description: "Read-only recall-expansion evidence for AB memory BioCortex T6. \
                For explicit query/relevance cases, it checks whether baseline FTS already \
                contains a relevant memory; for baseline misses, it inspects graph neighbors \
                of the baseline candidates to estimate whether graph expansion could recover \
                a relevant memory. It can also build a weakly-labeled graph-holdout sample \
                from existing memory graph edges and report a hypothetical baseline-then-neighbor \
                candidate set. It never runs BioCortex, writes memory, exposes raw \
                queries/keys/content, or changes retrieval order."
                .into(),
            input_schema: json!({
                "type": "object",
                "properties": {
                    "query_cases": {
                        "type": "array",
                        "description": "Explicit downstream recall cases. Raw queries and relevant keys are accepted as input but never echoed.",
                        "items": {
                            "type": "object",
                            "required": ["query", "relevant_keys"],
                            "properties": {
                                "query": {
                                    "type": "string",
                                    "description": "Baseline FTS query. Output includes only a query hash."
                                },
                                "relevant_keys": {
                                    "type": "array",
                                    "items": { "type": "string" },
                                    "description": "Known relevant memory keys. Output includes only counts and hashes."
                                },
                                "class_label": {
                                    "type": "string",
                                    "description": "Optional sanitized bucket label for aggregate review."
                                }
                            }
                        }
                    },
                    "sample_graph_holdout": {
                        "type": "boolean",
                        "default": false,
                        "description": "When true and query_cases is omitted/empty, derive weakly-labeled graph holdout cases from existing memory graph edges. Raw source/target keys and derived queries are not echoed."
                    },
                    "sample_size": {
                        "type": "integer",
                        "minimum": 1,
                        "maximum": 30,
                        "default": 8,
                        "description": "Maximum graph-holdout cases to sample when sample_graph_holdout=true."
                    },
                    "candidate_limit": {
                        "type": "integer",
                        "minimum": 1,
                        "maximum": 500,
                        "default": 100,
                        "description": "Recent memory rows inspected while building graph-holdout cases."
                    },
                    "query_chars": {
                        "type": "integer",
                        "minimum": 16,
                        "maximum": 400,
                        "default": 120,
                        "description": "Max chars of sanitized memory content used as each graph-holdout baseline query."
                    },
                    "limit": {
                        "type": "integer",
                        "minimum": 1,
                        "maximum": 100,
                        "default": 10,
                        "description": "Baseline memory_search candidate limit."
                    },
                    "neighbor_limit": {
                        "type": "integer",
                        "minimum": 0,
                        "maximum": 50,
                        "default": 8,
                        "description": "Maximum direct graph-neighbor edges inspected per baseline candidate."
                    },
                    "include_case_rows": {
                        "type": "boolean",
                        "default": true,
                        "description": "When false, omit redacted per-case rows and emit aggregate/class metrics only so downstream dry-run reports can consume the summary."
                    }
                }
            }),
        }
    }

    async fn execute(&self, args: Value, _ctx: &ToolContext) -> Result<ToolResult> {
        let store = self
            .hub
            .store
            .as_ref()
            .ok_or_else(|| ab_core::Error::Backend("store unavailable".into()))?;
        let mut cases = memory_biocortex_recall_expansion_cases_from_args(&args);
        let invalid_case_count = args
            .get("query_cases")
            .and_then(Value::as_array)
            .map(|raw| raw.len().saturating_sub(cases.len()))
            .unwrap_or(0);
        let sample_graph_holdout = args
            .get("sample_graph_holdout")
            .and_then(Value::as_bool)
            .unwrap_or(false);
        let sample_size = args
            .get("sample_size")
            .and_then(Value::as_u64)
            .unwrap_or(8)
            .clamp(1, 30) as usize;
        let candidate_limit = args
            .get("candidate_limit")
            .and_then(Value::as_u64)
            .unwrap_or(100)
            .clamp(1, 500) as u32;
        let query_chars = args
            .get("query_chars")
            .and_then(Value::as_u64)
            .unwrap_or(120)
            .clamp(16, 400) as usize;
        let limit = args
            .get("limit")
            .and_then(Value::as_u64)
            .unwrap_or(10)
            .clamp(1, 100) as u32;
        let neighbor_limit = args
            .get("neighbor_limit")
            .and_then(Value::as_u64)
            .unwrap_or(8)
            .min(50) as usize;
        let include_case_rows = args
            .get("include_case_rows")
            .and_then(Value::as_bool)
            .unwrap_or(true);

        let query_source = if cases.is_empty() && sample_graph_holdout {
            cases = memory_biocortex_recall_expansion_graph_holdout_cases(
                store.as_ref(),
                sample_size,
                candidate_limit,
                query_chars,
            )
            .await;
            "graph_holdout_sample"
        } else {
            "explicit_cases"
        };
        let graph_holdout_sampled_count = cases
            .iter()
            .filter(|case| case.case_source == "graph_holdout")
            .count();

        let mut case_rows = Vec::new();
        let mut rows_by_class = BTreeMap::<String, Vec<Value>>::new();

        for (idx, case) in cases.iter().enumerate() {
            let class_label =
                memory_biocortex_recall_expansion_class_label(case.class_label.as_deref());
            let query_hash = memory_biocortex_sha256_json(&json!({"query": case.query}));
            let relevant = case
                .relevant_keys
                .iter()
                .cloned()
                .collect::<BTreeSet<_>>();

            let baseline_hits = match store.memory_search(&case.query, &[], limit).await {
                Ok(hits) => hits,
                Err(_) => {
                    let row = json!({
                        "case_index": idx,
                        "query_hash": query_hash,
                        "class_label": class_label,
                        "case_source": case.case_source,
                        "status": "search_error",
                        "error_kind": "memory_search_error",
                        "relevant_key_count": relevant.len(),
                        "baseline_candidate_count": 0,
                        "baseline_relevant_count": 0,
                        "baseline_order_hash": memory_biocortex_order_hash("baseline", &[]),
                        "graph_neighbor_row_count": 0,
                        "graph_unique_neighbor_count": 0,
                        "graph_relevant_count": 0,
                        "graph_neighbor_order_hash": memory_biocortex_order_hash(
                            "graph_neighbors",
                            &[]
                        ),
                        "candidate_expansion_mode": "baseline_then_graph_neighbors",
                        "expanded_candidate_count": 0,
                        "expanded_relevant_count": 0,
                        "expanded_first_relevant_position": Value::Null,
                        "expanded_candidate_order_hash": memory_biocortex_order_hash(
                            "expanded_candidates",
                            &[]
                        ),
                        "raw_query_included": false,
                        "raw_keys_included": false,
                        "content_included": false,
                        "raw_error_included": false,
                    });
                    rows_by_class
                        .entry(class_label)
                        .or_default()
                        .push(row.clone());
                    case_rows.push(row);
                    continue;
                }
            };
            let baseline_keys = baseline_hits
                .iter()
                .map(|hit| hit.record.key.clone())
                .collect::<Vec<_>>();
            let baseline_key_set = baseline_keys.iter().cloned().collect::<BTreeSet<_>>();
            let baseline_relevant_count =
                relevant.intersection(&baseline_key_set).count() as u64;

            let mut graph_neighbor_row_count = 0u64;
            let mut graph_neighbor_keys = BTreeSet::<String>::new();
            let mut graph_neighbor_ordered = Vec::<String>::new();
            let mut graph_neighbor_seen = BTreeSet::<String>::new();
            for hit in &baseline_hits {
                let edges = store.memory_neighbors(&hit.record.key).await.unwrap_or_default();
                for edge in edges.into_iter().take(neighbor_limit) {
                    graph_neighbor_row_count += 1;
                    if let Some(neighbor_key) =
                        memory_biocortex_recall_expansion_neighbor_key(&edge, &hit.record.key)
                    {
                        graph_neighbor_keys.insert(neighbor_key.clone());
                        if graph_neighbor_seen.insert(neighbor_key.clone()) {
                            graph_neighbor_ordered.push(neighbor_key);
                        }
                    }
                }
            }

            let graph_relevant_count =
                relevant.intersection(&graph_neighbor_keys).count() as u64;
            let mut expanded_keys = baseline_keys.clone();
            let mut expanded_seen = baseline_key_set.clone();
            for neighbor_key in &graph_neighbor_ordered {
                if expanded_seen.insert(neighbor_key.clone()) {
                    expanded_keys.push(neighbor_key.clone());
                }
            }
            let expanded_key_set = expanded_keys.iter().cloned().collect::<BTreeSet<_>>();
            let expanded_relevant_count =
                relevant.intersection(&expanded_key_set).count() as u64;
            let expanded_first_relevant_position =
                memory_biocortex_recall_expansion_first_relevant_position(
                    &expanded_keys,
                    &relevant,
                );
            let status = if baseline_relevant_count > 0 {
                "baseline_hit"
            } else if graph_relevant_count > 0 {
                "graph_expansion_found"
            } else {
                "graph_expansion_miss"
            };
            let row = json!({
                "case_index": idx,
                "query_hash": query_hash,
                "class_label": class_label,
                "case_source": case.case_source,
                "status": status,
                "relevant_key_count": relevant.len(),
                "baseline_candidate_count": baseline_keys.len(),
                "baseline_relevant_count": baseline_relevant_count,
                "baseline_order_hash": memory_biocortex_order_hash("baseline", &baseline_keys),
                "graph_neighbor_row_count": graph_neighbor_row_count,
                "graph_unique_neighbor_count": graph_neighbor_keys.len(),
                "graph_relevant_count": graph_relevant_count,
                "graph_neighbor_order_hash": memory_biocortex_order_hash(
                    "graph_neighbors",
                    &graph_neighbor_keys.iter().cloned().collect::<Vec<_>>()
                ),
                "candidate_expansion_mode": "baseline_then_graph_neighbors",
                "expanded_candidate_count": expanded_keys.len(),
                "expanded_relevant_count": expanded_relevant_count,
                "expanded_first_relevant_position": expanded_first_relevant_position,
                "expanded_candidate_order_hash": memory_biocortex_order_hash(
                    "expanded_candidates",
                    &expanded_keys
                ),
                "raw_query_included": false,
                "raw_keys_included": false,
                "content_included": false,
            });
            rows_by_class
                .entry(class_label)
                .or_default()
                .push(row.clone());
            case_rows.push(row);
        }

        let evaluated_count = case_rows.len() as u64;
        let search_error_count = case_rows
            .iter()
            .filter(|row| row["status"] == json!("search_error"))
            .count() as u64;
        let baseline_hit_count = case_rows
            .iter()
            .filter(|row| row["status"] == json!("baseline_hit"))
            .count() as u64;
        let baseline_miss_count = case_rows
            .iter()
            .filter(|row| {
                row["status"] == json!("graph_expansion_found")
                    || row["status"] == json!("graph_expansion_miss")
            })
            .count() as u64;
        let graph_expansion_found_count = case_rows
            .iter()
            .filter(|row| row["status"] == json!("graph_expansion_found"))
            .count() as u64;
        let graph_expansion_miss_count = case_rows
            .iter()
            .filter(|row| row["status"] == json!("graph_expansion_miss"))
            .count() as u64;
        let graph_neighbor_row_count = case_rows
            .iter()
            .map(|row| row["graph_neighbor_row_count"].as_u64().unwrap_or(0))
            .sum::<u64>();
        let expanded_hit_count = case_rows
            .iter()
            .filter(|row| row["expanded_relevant_count"].as_u64().unwrap_or(0) > 0)
            .count() as u64;
        let candidate_expansion_added_hit_count = case_rows
            .iter()
            .filter(|row| {
                row["baseline_relevant_count"].as_u64().unwrap_or(0) == 0
                    && row["expanded_relevant_count"].as_u64().unwrap_or(0) > 0
            })
            .count() as u64;
        let class_aggregates = rows_by_class
            .into_iter()
            .map(|(class_label, rows)| {
                memory_biocortex_recall_expansion_class_row(class_label, &rows)
            })
            .collect::<Vec<_>>();

        let mut payload = json!({
            "schema": MEMORY_BIOCORTEX_RECALL_EXPANSION_SUMMARY_SCHEMA,
            "generated_at": unix_now_secs(),
            "read_only": true,
            "purpose": "Read-only recall-expansion yardstick: for explicit downstream cases, measure whether baseline FTS already recalls a relevant memory and whether direct graph-neighbor expansion could recover relevant memories for baseline misses. It also reports an offline baseline-then-neighbor candidate set without changing production candidates or ranking.",
            "sampling": {
                "query_source": query_source,
                "query_cases_count": cases.len(),
                "invalid_query_cases": invalid_case_count,
                "sample_graph_holdout": sample_graph_holdout,
                "graph_holdout_sampled_count": graph_holdout_sampled_count,
                "candidate_limit": candidate_limit,
                "query_chars": query_chars,
                "telemetry_top_miss_query_hashes_included": false,
                "search_limit": limit,
                "neighbor_limit_per_baseline_key": neighbor_limit,
            },
            "metrics": {
                "evaluated_count": evaluated_count,
                "search_error_count": search_error_count,
                "baseline_hit_count": baseline_hit_count,
                "baseline_miss_count": baseline_miss_count,
                "graph_expansion_found_count": graph_expansion_found_count,
                "graph_expansion_miss_count": graph_expansion_miss_count,
                "graph_neighbor_row_count": graph_neighbor_row_count,
                "expanded_hit_count": expanded_hit_count,
                "candidate_expansion_added_hit_count": candidate_expansion_added_hit_count,
                "candidate_expansion_added_hit_rate": if baseline_miss_count > 0 {
                    memory_biocortex_recall_expansion_round3(
                        candidate_expansion_added_hit_count as f64 / baseline_miss_count as f64,
                    )
                } else {
                    0.0
                },
                "graph_expansion_found_rate": if baseline_miss_count > 0 {
                    memory_biocortex_recall_expansion_round3(
                        graph_expansion_found_count as f64 / baseline_miss_count as f64,
                    )
                } else {
                    0.0
                },
            },
            "class_aggregates": class_aggregates,
            "input_contract": {
                "case_rows_included": include_case_rows,
                "raw_query_included": false,
                "raw_queries_included": false,
                "raw_keys_included": false,
                "content_included": false,
                "candidate_content_included": false,
                "source_eval_included": false,
                "raw_error_included": false,
            },
            "safety": {
                "read_only": true,
                "calls_memory_search": true,
                "calls_memory_neighbors": true,
                "runs_biocortex": false,
                "writes_memory": false,
                "changes_search_order": false,
                "changes_prod_retrieval_order": false,
                "writes_state": false,
                "default_search_order_change_allowed": false,
                "changes_candidate_set_now": false,
            },
            "interpretation": {
                "baseline_misses_have_graph_expansion_signal": graph_expansion_found_count > 0,
                "candidate_expansion_has_added_hit_signal": candidate_expansion_added_hit_count > 0,
                "runtime_influence_ready": false,
                "next_gate": "inspect_redacted_recall_expansion_evidence_before_any_candidate-expansion_experiment",
            },
            "non_goals": [
                "Does not run BioCortex.",
                "Does not add graph neighbors to live memory_search results.",
                "Does not change memory_search ranking or default recall.",
                "Does not write memory, graph edges, approval packets, or runtime influence decisions.",
                "Does not include raw query, memory keys, or memory content."
            ],
            "calls_memory_search": true,
            "calls_memory_neighbors": true,
            "runs_biocortex": false,
            "writes_memory": false,
            "changes_memory_search_order": false,
        });
        if include_case_rows {
            if let Some(payload_obj) = payload.as_object_mut() {
                payload_obj.insert("case_rows".to_string(), Value::Array(case_rows));
            }
        }

        Ok(ToolResult::json_text(&payload))
    }
}

// ===========================================================================
//          memory_biocortex_relevance_lift_summary — T6 lift summary
// ===========================================================================

pub struct MemoryBioCortexRelevanceLiftSummaryTool {
    hub: Hub,
}

impl MemoryBioCortexRelevanceLiftSummaryTool {
    pub fn new(hub: Hub) -> Self {
        Self { hub }
    }
}

#[async_trait]
impl McpTool for MemoryBioCortexRelevanceLiftSummaryTool {
    fn name(&self) -> &'static str {
        "memory_biocortex_relevance_lift_summary"
    }

    fn schema(&self) -> ToolSchema {
        ToolSchema {
            name: self.name().into(),
            description: "Read-only redacted relevance-lift summary for AB memory BioCortex T6. \
                Runs the existing relevance-lift yardstick, then strips per-sample rows and \
                raw side-signal errors so the output contains only schema/status/verdict, \
                sampling, metrics, caveats, and safety fields consumed by the T6 gate. \
                It never writes memory or changes production retrieval order."
                .into(),
            input_schema: BioCortexRetrievalRelevanceLiftEvalTool::new(self.hub.clone())
                .schema()
                .input_schema,
        }
    }

    async fn execute(&self, args: Value, _ctx: &ToolContext) -> Result<ToolResult> {
        let store = self
            .hub
            .store
            .as_ref()
            .ok_or_else(|| ab_core::Error::Backend("store unavailable".into()))?;
        let sample_size = args
            .get("sample_size")
            .and_then(Value::as_u64)
            .unwrap_or(8)
            .clamp(1, 30) as usize;
        let kind = args
            .get("kind")
            .and_then(Value::as_str)
            .map(str::trim)
            .filter(|s| !s.is_empty())
            .map(str::to_string);
        let query_cases = relevance_lift_query_cases_from_args(&args);
        let sort = match args
            .get("sort")
            .and_then(Value::as_str)
            .unwrap_or("by_importance")
        {
            "recent" => MemoryListSort::Recent,
            "frequent" => MemoryListSort::Frequent,
            "newest" => MemoryListSort::Newest,
            _ => MemoryListSort::ByImportance,
        };
        let limit = args
            .get("limit")
            .and_then(Value::as_u64)
            .unwrap_or(20)
            .clamp(5, 100) as u32;
        let query_chars = args
            .get("query_chars")
            .and_then(Value::as_u64)
            .unwrap_or(120)
            .clamp(16, 400) as usize;
        let or_terms = args
            .get("or_terms")
            .and_then(Value::as_u64)
            .unwrap_or(10)
            .min(24) as usize;
        let include_related = args
            .get("include_related")
            .and_then(Value::as_bool)
            .unwrap_or(true);
        let blend_alpha = args
            .get("blend_alpha")
            .and_then(Value::as_f64)
            .unwrap_or(0.8) as f32;
        let coverage_threshold = args
            .get("coverage_threshold")
            .and_then(Value::as_f64)
            .unwrap_or(0.8);
        let checkout = args
            .get("checkout_path")
            .and_then(Value::as_str)
            .map(str::trim)
            .filter(|s| !s.is_empty())
            .map(PathBuf::from);
        let timeout_ms = args
            .get("timeout_ms")
            .and_then(Value::as_u64)
            .unwrap_or(180_000);

        let payload = biocortex_retrieval_relevance_lift_eval(
            store.as_ref(),
            RelevanceLiftEvalOptions {
                sample_size,
                kind,
                query_cases,
                sort,
                limit,
                query_chars,
                or_terms,
                blend_alpha,
                coverage_threshold,
                include_related,
                checkout,
                timeout_ms,
            },
        )
        .await;
        Ok(ToolResult::json_text(
            &memory_biocortex_relevance_lift_summary_payload(payload),
        ))
    }
}

pub(super) fn memory_biocortex_t6_bool_at(value: &Value, path: &str) -> Option<bool> {
    value.pointer(path).and_then(Value::as_bool)
}

pub(super) fn memory_biocortex_t6_string_at<'a>(value: &'a Value, path: &str) -> Option<&'a str> {
    value.pointer(path).and_then(Value::as_str)
}

pub(super) fn memory_biocortex_t6_f64_at(value: &Value, path: &str) -> Option<f64> {
    value.pointer(path).and_then(Value::as_f64)
}

pub(super) fn memory_biocortex_t6_u64_at(value: &Value, path: &str) -> Option<u64> {
    value.pointer(path).and_then(Value::as_u64)
}

pub(super) fn memory_biocortex_t6_string_array_at(value: &Value, path: &str) -> Vec<String> {
    value
        .pointer(path)
        .and_then(Value::as_array)
        .map(|items| {
            items
                .iter()
                .filter_map(Value::as_str)
                .map(str::trim)
                .filter(|s| !s.is_empty())
                .map(str::to_string)
                .collect()
        })
        .unwrap_or_default()
}

pub(super) fn memory_biocortex_t6_rate(numerator: Option<u64>, denominator: Option<u64>) -> Option<f64> {
    match (numerator, denominator) {
        (Some(numerator), Some(denominator)) if denominator > 0 => {
            Some(numerator as f64 / denominator as f64)
        }
        _ => None,
    }
}

pub(super) fn memory_biocortex_t6_push_reason(reasons: &mut BTreeSet<String>, reason: &str) {
    reasons.insert(reason.to_string());
}

pub(super) fn memory_biocortex_t6_has_raw_payload_fields(value: &Value) -> bool {
    ["raw_query", "raw_key", "raw_keys", "baseline_keys", "content"]
        .iter()
        .any(|field| value.get(*field).is_some())
}

pub(super) fn memory_biocortex_t6_any_true(value: &Value, paths: &[&str]) -> bool {
    paths
        .iter()
        .any(|path| memory_biocortex_t6_bool_at(value, path) == Some(true))
}

pub(super) fn memory_biocortex_t6_check_shadow_trial(value: &Value, reasons: &mut BTreeSet<String>) {
    if memory_biocortex_t6_string_at(value, "/schema") != Some(MEMORY_BIOCORTEX_SHADOW_TRIAL_SCHEMA)
    {
        memory_biocortex_t6_push_reason(reasons, "shadow_schema_invalid");
    }
    if memory_biocortex_t6_bool_at(value, "/read_only") != Some(true) {
        memory_biocortex_t6_push_reason(reasons, "shadow_not_read_only");
    }
    if memory_biocortex_t6_bool_at(value, "/runs_biocortex") != Some(false) {
        memory_biocortex_t6_push_reason(reasons, "shadow_runs_biocortex");
    }
    if memory_biocortex_t6_bool_at(value, "/changes_memory_search_order") != Some(false) {
        memory_biocortex_t6_push_reason(reasons, "shadow_changes_memory_search_order");
    }
    if memory_biocortex_t6_bool_at(value, "/current_biocortex_frontier/discovered_selection_claimed")
        != Some(false)
    {
        memory_biocortex_t6_push_reason(reasons, "shadow_frontier_claimed_discovered_selection");
    }
    if memory_biocortex_t6_has_raw_payload_fields(value)
        || memory_biocortex_t6_any_true(
            value,
            &[
                "/input_contract/raw_query_included",
                "/input_contract/raw_keys_included",
                "/input_contract/content_included",
                "/input_contract/candidate_content_included",
                "/baseline/raw_keys_included",
                "/baseline/content_included",
                "/graph_neighborhood/raw_keys_included",
                "/graph_neighborhood/content_included",
                "/suppression_set/raw_keys_included",
                "/advisory_control_order/raw_keys_included",
                "/advisory_control_order/content_included",
            ],
        )
    {
        memory_biocortex_t6_push_reason(reasons, "shadow_raw_query_key_or_content_included");
    }
}

pub(super) fn memory_biocortex_t6_check_relevance_lift(
    value: Option<&Value>,
    min_evaluated_count: u64,
    min_mrr_lift: f64,
    max_worsened: u64,
    reasons: &mut BTreeSet<String>,
) -> (Option<u64>, Option<f64>, Option<u64>, Option<u64>, Option<u64>) {
    let Some(value) = value else {
        memory_biocortex_t6_push_reason(reasons, "missing_relevance_lift_eval");
        return (None, None, None, None, None);
    };

    if memory_biocortex_t6_string_at(value, "/schema")
        != Some(BIOCORTEX_RETRIEVAL_RELEVANCE_LIFT_EVAL_SCHEMA_LOCAL)
    {
        memory_biocortex_t6_push_reason(reasons, "relevance_lift_schema_invalid");
    }
    if memory_biocortex_t6_string_at(value, "/status") != Some("completed") {
        memory_biocortex_t6_push_reason(reasons, "relevance_lift_not_completed");
    }
    if memory_biocortex_t6_bool_at(value, "/safety/read_only") != Some(true)
        || memory_biocortex_t6_bool_at(value, "/safety/mutates_ab_memory") != Some(false)
        || memory_biocortex_t6_bool_at(value, "/safety/changes_prod_retrieval_order") != Some(false)
        || memory_biocortex_t6_bool_at(value, "/safety/writes_state") != Some(false)
    {
        memory_biocortex_t6_push_reason(reasons, "relevance_lift_safety_contract_invalid");
    }
    if !matches!(
        memory_biocortex_t6_string_at(value, "/verdict"),
        Some("lift_demonstrated" | "lift")
    ) {
        memory_biocortex_t6_push_reason(reasons, "relevance_lift_verdict_not_positive");
    }
    if memory_biocortex_t6_has_raw_payload_fields(value) {
        memory_biocortex_t6_push_reason(reasons, "relevance_lift_raw_payload_supplied");
    }

    let evaluated_count = memory_biocortex_t6_u64_at(value, "/sampling/evaluated_count");
    if evaluated_count.unwrap_or(0) < min_evaluated_count {
        memory_biocortex_t6_push_reason(reasons, "insufficient_evaluated_count");
    }
    let mrr_lift = memory_biocortex_t6_f64_at(value, "/metrics/mrr_lift");
    if mrr_lift.unwrap_or(f64::NEG_INFINITY) < min_mrr_lift {
        memory_biocortex_t6_push_reason(reasons, "insufficient_mrr_lift");
    }
    let worsened = memory_biocortex_t6_u64_at(value, "/metrics/worsened");
    if worsened.unwrap_or(u64::MAX) > max_worsened {
        memory_biocortex_t6_push_reason(reasons, "regressions_exceed_max_worsened");
    }

    (
        evaluated_count,
        mrr_lift,
        worsened,
        memory_biocortex_t6_u64_at(value, "/metrics/improved"),
        memory_biocortex_t6_u64_at(value, "/metrics/unchanged"),
    )
}

pub(super) fn memory_biocortex_t6_check_redacted_aggregate(
    value: Option<&Value>,
    reasons: &mut BTreeSet<String>,
) -> bool {
    let Some(value) = value else {
        memory_biocortex_t6_push_reason(reasons, "missing_redacted_evidence_aggregate");
        return false;
    };

    if memory_biocortex_t6_string_at(value, "/schema")
        != Some(BIOCORTEX_RETRIEVAL_REDACTED_EVIDENCE_AGGREGATE_SCHEMA_LOCAL)
    {
        memory_biocortex_t6_push_reason(reasons, "redacted_evidence_aggregate_schema_invalid");
    }
    if memory_biocortex_t6_bool_at(value, "/read_only") != Some(true)
        || memory_biocortex_t6_bool_at(value, "/redacted_evidence_aggregate") != Some(true)
    {
        memory_biocortex_t6_push_reason(reasons, "redacted_evidence_aggregate_not_read_only");
    }
    if memory_biocortex_t6_any_true(
        value,
        &[
            "/input_contract/raw_queries_included",
            "/input_contract/raw_keys_included",
            "/input_contract/content_included",
            "/input_contract/side_signal_raw_included",
        ],
    )
    {
        memory_biocortex_t6_push_reason(
            reasons,
            "redacted_evidence_aggregate_raw_query_key_or_content_included",
        );
    }
    let aggregate_ready =
        memory_biocortex_t6_bool_at(value, "/interpretation/aggregate_evidence_ready")
            == Some(true);
    if !aggregate_ready {
        memory_biocortex_t6_push_reason(reasons, "redacted_evidence_aggregate_not_ready");
    }
    if memory_biocortex_t6_bool_at(value, "/interpretation/default_influence_ready") == Some(true) {
        memory_biocortex_t6_push_reason(reasons, "redacted_evidence_claims_default_influence_ready");
    }
    aggregate_ready
}

#[derive(Debug, Default)]
pub(super) struct MemoryBioCortexT6RecallExpansionMetrics {
    evaluated_count: Option<u64>,
    search_error_count: Option<u64>,
    baseline_miss_count: Option<u64>,
    graph_expansion_found_count: Option<u64>,
    expanded_hit_count: Option<u64>,
    candidate_expansion_added_hit_count: Option<u64>,
    candidate_expansion_added_hit_rate: Option<f64>,
}

pub(super) fn memory_biocortex_t6_check_recall_expansion_summary(
    value: Option<&Value>,
    min_recall_evaluated_count: u64,
    min_baseline_miss_count: u64,
    min_candidate_expansion_added_hit_count: u64,
    min_candidate_expansion_added_hit_rate: f64,
    max_recall_search_error_count: u64,
    reasons: &mut BTreeSet<String>,
) -> MemoryBioCortexT6RecallExpansionMetrics {
    let Some(value) = value else {
        memory_biocortex_t6_push_reason(reasons, "missing_recall_expansion_summary");
        return MemoryBioCortexT6RecallExpansionMetrics::default();
    };

    if memory_biocortex_t6_string_at(value, "/schema")
        != Some(MEMORY_BIOCORTEX_RECALL_EXPANSION_SUMMARY_SCHEMA)
    {
        memory_biocortex_t6_push_reason(reasons, "recall_expansion_schema_invalid");
    }
    if memory_biocortex_t6_bool_at(value, "/read_only") != Some(true)
        || memory_biocortex_t6_bool_at(value, "/safety/read_only") != Some(true)
        || memory_biocortex_t6_bool_at(value, "/safety/runs_biocortex") != Some(false)
        || memory_biocortex_t6_bool_at(value, "/safety/writes_memory") != Some(false)
        || memory_biocortex_t6_bool_at(value, "/safety/changes_search_order") != Some(false)
        || memory_biocortex_t6_bool_at(value, "/safety/changes_prod_retrieval_order")
            != Some(false)
        || memory_biocortex_t6_bool_at(value, "/safety/writes_state") != Some(false)
        || memory_biocortex_t6_bool_at(value, "/safety/default_search_order_change_allowed")
            != Some(false)
        || memory_biocortex_t6_bool_at(value, "/safety/changes_candidate_set_now") != Some(false)
    {
        memory_biocortex_t6_push_reason(reasons, "recall_expansion_safety_contract_invalid");
    }
    if memory_biocortex_t6_has_raw_payload_fields(value)
        || memory_biocortex_t6_any_true(
            value,
            &[
                "/input_contract/case_rows_included",
                "/input_contract/raw_query_included",
                "/input_contract/raw_queries_included",
                "/input_contract/raw_keys_included",
                "/input_contract/content_included",
                "/input_contract/candidate_content_included",
                "/input_contract/raw_error_included",
            ],
        )
    {
        memory_biocortex_t6_push_reason(
            reasons,
            "recall_expansion_raw_query_key_or_content_included",
        );
    }

    let evaluated_count = memory_biocortex_t6_u64_at(value, "/metrics/evaluated_count");
    if evaluated_count.unwrap_or(0) < min_recall_evaluated_count {
        memory_biocortex_t6_push_reason(reasons, "insufficient_recall_evaluated_count");
    }
    let search_error_count = memory_biocortex_t6_u64_at(value, "/metrics/search_error_count");
    if search_error_count.unwrap_or(u64::MAX) > max_recall_search_error_count {
        memory_biocortex_t6_push_reason(reasons, "recall_expansion_search_errors_exceed_max");
    }
    let baseline_miss_count = memory_biocortex_t6_u64_at(value, "/metrics/baseline_miss_count");
    if baseline_miss_count.unwrap_or(0) < min_baseline_miss_count {
        memory_biocortex_t6_push_reason(reasons, "insufficient_baseline_miss_count");
    }
    let candidate_expansion_added_hit_count =
        memory_biocortex_t6_u64_at(value, "/metrics/candidate_expansion_added_hit_count");
    if candidate_expansion_added_hit_count.unwrap_or(0)
        < min_candidate_expansion_added_hit_count
    {
        memory_biocortex_t6_push_reason(
            reasons,
            "insufficient_candidate_expansion_added_hits",
        );
    }
    let candidate_expansion_added_hit_rate = memory_biocortex_t6_f64_at(
        value,
        "/metrics/candidate_expansion_added_hit_rate",
    )
    .or_else(|| {
        memory_biocortex_t6_rate(candidate_expansion_added_hit_count, baseline_miss_count)
    });
    if candidate_expansion_added_hit_rate.unwrap_or(f64::NEG_INFINITY)
        < min_candidate_expansion_added_hit_rate
    {
        memory_biocortex_t6_push_reason(
            reasons,
            "insufficient_candidate_expansion_added_hit_rate",
        );
    }

    MemoryBioCortexT6RecallExpansionMetrics {
        evaluated_count,
        search_error_count,
        baseline_miss_count,
        graph_expansion_found_count: memory_biocortex_t6_u64_at(
            value,
            "/metrics/graph_expansion_found_count",
        ),
        expanded_hit_count: memory_biocortex_t6_u64_at(value, "/metrics/expanded_hit_count"),
        candidate_expansion_added_hit_count,
        candidate_expansion_added_hit_rate,
    }
}

pub(super) fn memory_biocortex_t6_influence_gate_payload(args: Value) -> Value {
    let min_shadow_trials = args
        .get("min_shadow_trials")
        .and_then(Value::as_u64)
        .unwrap_or(3)
        .clamp(1, 100);
    let min_evaluated_count = args
        .get("min_evaluated_count")
        .and_then(Value::as_u64)
        .unwrap_or(10)
        .clamp(1, 10_000);
    let min_mrr_lift = args
        .get("min_mrr_lift")
        .and_then(Value::as_f64)
        .unwrap_or(0.001)
        .max(0.0);
    let max_worsened = args
        .get("max_worsened")
        .and_then(Value::as_u64)
        .unwrap_or(0);
    let min_improved_count = args
        .get("min_improved_count")
        .and_then(Value::as_u64)
        .unwrap_or(0)
        .min(10_000);
    let min_improved_rate = args
        .get("min_improved_rate")
        .and_then(Value::as_f64)
        .filter(|value| value.is_finite())
        .unwrap_or(0.0)
        .clamp(0.0, 1.0);
    let candidate_expansion_review_requested = args
        .get("candidate_expansion_review_requested")
        .and_then(Value::as_bool)
        .unwrap_or(false)
        || args.get("recall_expansion_summary").is_some();
    let min_recall_evaluated_count = args
        .get("min_recall_evaluated_count")
        .and_then(Value::as_u64)
        .unwrap_or(8)
        .clamp(1, 10_000);
    let min_baseline_miss_count = args
        .get("min_baseline_miss_count")
        .and_then(Value::as_u64)
        .unwrap_or(1)
        .clamp(1, 10_000);
    let min_candidate_expansion_added_hit_count = args
        .get("min_candidate_expansion_added_hit_count")
        .and_then(Value::as_u64)
        .unwrap_or(1)
        .clamp(1, 10_000);
    let min_candidate_expansion_added_hit_rate = args
        .get("min_candidate_expansion_added_hit_rate")
        .and_then(Value::as_f64)
        .filter(|value| value.is_finite())
        .unwrap_or(0.10)
        .clamp(0.0, 1.0);
    let max_recall_search_error_count = args
        .get("max_recall_search_error_count")
        .and_then(Value::as_u64)
        .unwrap_or(0);

    let shadow_trials = args
        .get("shadow_trials")
        .and_then(Value::as_array)
        .cloned()
        .unwrap_or_default();
    let mut block_reasons = BTreeSet::<String>::new();
    if shadow_trials.len() < min_shadow_trials as usize {
        memory_biocortex_t6_push_reason(&mut block_reasons, "insufficient_shadow_trials");
    }
    for shadow in &shadow_trials {
        memory_biocortex_t6_check_shadow_trial(shadow, &mut block_reasons);
    }

    let (evaluated_count, mrr_lift, worsened, improved, unchanged) =
        memory_biocortex_t6_check_relevance_lift(
            args.get("relevance_lift_eval"),
            min_evaluated_count,
            min_mrr_lift,
            max_worsened,
            &mut block_reasons,
        );
    let improved_rate = memory_biocortex_t6_rate(improved, evaluated_count);
    if improved.unwrap_or(0) < min_improved_count {
        memory_biocortex_t6_push_reason(&mut block_reasons, "insufficient_improved_count");
    }
    if min_improved_rate > 0.0
        && improved_rate.unwrap_or(f64::NEG_INFINITY) < min_improved_rate
    {
        memory_biocortex_t6_push_reason(&mut block_reasons, "insufficient_improved_rate");
    }
    let redacted_evidence_aggregate_ready = memory_biocortex_t6_check_redacted_aggregate(
        args.get("redacted_evidence_aggregate"),
        &mut block_reasons,
    );
    let mut candidate_expansion_block_reasons = BTreeSet::<String>::new();
    let recall_expansion_metrics = if candidate_expansion_review_requested {
        memory_biocortex_t6_check_recall_expansion_summary(
            args.get("recall_expansion_summary"),
            min_recall_evaluated_count,
            min_baseline_miss_count,
            min_candidate_expansion_added_hit_count,
            min_candidate_expansion_added_hit_rate,
            max_recall_search_error_count,
            &mut candidate_expansion_block_reasons,
        )
    } else {
        MemoryBioCortexT6RecallExpansionMetrics::default()
    };
    let relevance_lift_eval = args.get("relevance_lift_eval");
    let relevance_kind_filter = relevance_lift_eval
        .and_then(|value| memory_biocortex_t6_string_at(value, "/sampling/kind_filter"));
    let relevance_sort =
        relevance_lift_eval.and_then(|value| memory_biocortex_t6_string_at(value, "/sampling/sort"));
    let mut review_caveats = Vec::new();
    if let Some(evaluated_count) = evaluated_count {
        if evaluated_count < 30 {
            review_caveats.push("low_evaluated_count_for_strength_label");
        }
    }
    if let Some(mrr_lift) = mrr_lift {
        if mrr_lift < 0.01 {
            review_caveats.push("weak_mrr_lift_margin");
        }
    }
    if let Some(improved_rate) = improved_rate {
        if improved_rate < 0.10 {
            review_caveats.push("low_improved_rate");
        }
    }
    if relevance_kind_filter.is_some() {
        review_caveats.push("kind_stratified_evidence_narrow_scope");
    } else if relevance_lift_eval.is_some() {
        review_caveats.push("unstratified_evidence_scope");
    }
    let evidence_strength_tier = if block_reasons.is_empty() {
        if review_caveats.iter().any(|caveat| {
            matches!(
                *caveat,
                "low_evaluated_count_for_strength_label"
                    | "weak_mrr_lift_margin"
                    | "low_improved_rate"
                    | "kind_stratified_evidence_narrow_scope"
            )
        }) {
            "weak_narrow_lift"
        } else {
            "review_ready"
        }
    } else {
        "blocked"
    };
    let ready_for_opt_in_experiment = block_reasons.is_empty();
    let mut candidate_expansion_review_caveats = Vec::new();
    if candidate_expansion_review_requested {
        if recall_expansion_metrics.evaluated_count.unwrap_or(0) < 30 {
            candidate_expansion_review_caveats.push("low_recall_evaluated_count_for_strength_label");
        }
        if recall_expansion_metrics.baseline_miss_count.unwrap_or(0) < 5 {
            candidate_expansion_review_caveats.push("low_baseline_miss_count");
        }
        if recall_expansion_metrics
            .candidate_expansion_added_hit_count
            .unwrap_or(0)
            < 2
        {
            candidate_expansion_review_caveats.push("narrow_candidate_expansion_added_hit_count");
        }
    }
    let candidate_expansion_evidence_strength_tier = if !candidate_expansion_review_requested {
        "not_requested"
    } else if candidate_expansion_block_reasons.is_empty() {
        if candidate_expansion_review_caveats.is_empty() {
            "review_ready"
        } else {
            "weak_narrow_candidate_expansion"
        }
    } else {
        "blocked"
    };
    let ready_for_candidate_expansion_review =
        candidate_expansion_review_requested && candidate_expansion_block_reasons.is_empty();
    let block_reasons = block_reasons.into_iter().collect::<Vec<_>>();
    let candidate_expansion_block_reasons = candidate_expansion_block_reasons
        .into_iter()
        .collect::<Vec<_>>();

    json!({
        "schema": MEMORY_BIOCORTEX_T6_INFLUENCE_GATE_SCHEMA,
        "generated_at": unix_now_secs(),
        "read_only": true,
        "purpose": "T6 gate: decide whether T5 BioCortex shadow evidence is sufficient to request an opt-in influence experiment review, without approving runtime influence.",
        "ready_for_opt_in_experiment": ready_for_opt_in_experiment,
        "ready_for_influence": false,
        "runtime_influence_approved": false,
        "may_change_search_order_now": false,
        "changes_memory_search_order": false,
        "default_search_order_change_allowed": false,
        "calls_memory_search": false,
        "runs_biocortex": false,
        "writes_memory": false,
        "block_reasons": block_reasons,
        "candidate_expansion_gate": {
            "requested": candidate_expansion_review_requested,
            "ready_for_candidate_expansion_review": ready_for_candidate_expansion_review,
            "candidate_expansion_experiment_approved": false,
            "may_expand_candidate_set_now": false,
            "changes_candidate_set_now": false,
            "block_reasons": candidate_expansion_block_reasons,
            "decision": {
                "verdict": if ready_for_candidate_expansion_review {
                    "ready_for_human_review"
                } else if candidate_expansion_review_requested {
                    "blocked"
                } else {
                    "not_requested"
                },
                "next_gate": if ready_for_candidate_expansion_review {
                    "human_review_before_candidate_expansion_experiment"
                } else if candidate_expansion_review_requested {
                    "collect_more_redacted_recall_expansion_evidence"
                } else {
                    "provide_recall_expansion_summary_when_evaluating_candidate_expansion"
                },
                "human_review_required": true,
                "candidate_expansion_authority_out_of_scope": true,
            },
            "thresholds": {
                "min_recall_evaluated_count": min_recall_evaluated_count,
                "min_baseline_miss_count": min_baseline_miss_count,
                "min_candidate_expansion_added_hit_count": min_candidate_expansion_added_hit_count,
                "min_candidate_expansion_added_hit_rate": min_candidate_expansion_added_hit_rate,
                "max_recall_search_error_count": max_recall_search_error_count,
            },
            "metrics": {
                "evaluated_count": recall_expansion_metrics.evaluated_count,
                "search_error_count": recall_expansion_metrics.search_error_count,
                "baseline_miss_count": recall_expansion_metrics.baseline_miss_count,
                "graph_expansion_found_count": recall_expansion_metrics.graph_expansion_found_count,
                "expanded_hit_count": recall_expansion_metrics.expanded_hit_count,
                "candidate_expansion_added_hit_count": recall_expansion_metrics.candidate_expansion_added_hit_count,
                "candidate_expansion_added_hit_rate": recall_expansion_metrics.candidate_expansion_added_hit_rate,
            },
            "evidence_strength": {
                "tier": candidate_expansion_evidence_strength_tier,
                "review_caveats": candidate_expansion_review_caveats,
                "label_thresholds": {
                    "low_recall_evaluated_count_below": 30,
                    "low_baseline_miss_count_below": 5,
                    "narrow_added_hit_count_below": 2
                }
            },
        },
        "decision": {
            "verdict": if ready_for_opt_in_experiment { "ready_for_human_review" } else { "blocked" },
            "next_gate": if ready_for_opt_in_experiment {
                "human_review_before_any_runtime_influence"
            } else {
                "collect_more_redacted_shadow_and_lift_evidence"
            },
            "human_review_required": true,
            "runtime_influence_decision_out_of_scope": true,
        },
        "thresholds": {
            "min_shadow_trials": min_shadow_trials,
            "min_evaluated_count": min_evaluated_count,
            "min_mrr_lift": min_mrr_lift,
            "max_worsened": max_worsened,
            "min_improved_count": min_improved_count,
            "min_improved_rate": min_improved_rate,
        },
        "evidence_summary": {
            "shadow_trial_count": shadow_trials.len(),
            "relevance_lift_eval_provided": args.get("relevance_lift_eval").is_some(),
            "redacted_evidence_aggregate_provided": args.get("redacted_evidence_aggregate").is_some(),
            "redacted_evidence_aggregate_ready": redacted_evidence_aggregate_ready,
            "recall_expansion_summary_provided": args.get("recall_expansion_summary").is_some(),
            "ready_for_candidate_expansion_review": ready_for_candidate_expansion_review,
            "evaluated_count": evaluated_count,
            "mrr_lift": mrr_lift,
            "worsened": worsened,
            "improved": improved,
            "improved_rate": improved_rate,
            "unchanged": unchanged,
        },
        "evidence_strength": {
            "tier": evidence_strength_tier,
            "evaluated_count": evaluated_count,
            "mrr_lift": mrr_lift,
            "worsened": worsened,
            "improved": improved,
            "improved_rate": improved_rate,
            "unchanged": unchanged,
            "kind_filter": relevance_kind_filter,
            "sort": relevance_sort,
            "review_caveats": review_caveats,
            "label_thresholds": {
                "low_evaluated_count_below": 30,
                "weak_mrr_lift_below": 0.01,
                "low_improved_rate_below": 0.10
            }
        },
        "input_contract": {
            "shadow_trials_included": false,
            "relevance_lift_eval_included": false,
            "redacted_evidence_aggregate_included": false,
            "recall_expansion_summary_included": false,
            "raw_query_included": false,
            "raw_queries_included": false,
            "raw_keys_included": false,
            "content_included": false,
            "side_signal_raw_included": false,
        },
        "non_goals": [
            "Does not run BioCortex.",
            "Does not call memory_search.",
            "Does not write memory, graph edges, authorization records, or approval packets.",
            "Does not approve runtime influence or change retrieval order.",
            "Does not approve candidate-set expansion.",
            "Does not include raw shadow packets, lift samples, recall expansion rows, queries, keys, or content."
        ],
    })
}

// ===========================================================================
//          memory_biocortex_t6_influence_gate — T6 evidence/readiness gate
// ===========================================================================

pub struct MemoryBioCortexT6InfluenceGateTool;
impl MemoryBioCortexT6InfluenceGateTool {
    pub fn new() -> Self {
        Self
    }
}
#[async_trait]
impl McpTool for MemoryBioCortexT6InfluenceGateTool {
    fn name(&self) -> &'static str {
        "memory_biocortex_t6_influence_gate"
    }
    fn schema(&self) -> ToolSchema {
        ToolSchema {
            name: self.name().into(),
            description: "Read-only T6 evidence gate for AB memory BioCortex opt-in influence. \
                Consumes T5 shadow-trial packets, a relevance-lift eval, and a redacted \
                evidence aggregate; it can also consume a redacted recall-expansion summary \
                for candidate-expansion review readiness. It returns whether the evidence is \
                sufficient to request human review. It never approves runtime influence, \
                candidate-set expansion, runs BioCortex, calls memory_search, mutates memory, \
                echoes raw query/keys/content, or changes retrieval order."
                .into(),
            input_schema: json!({
                "type": "object",
                "properties": {
                    "shadow_trials": {
                        "type": "array",
                        "items": { "type": "object" },
                        "default": [],
                        "description": "T5 memory_biocortex_shadow_trial outputs. Output never echoes them."
                    },
                    "relevance_lift_eval": {
                        "type": "object",
                        "description": "BioCortex relevance-lift eval output. Output consumes only safe aggregate fields."
                    },
                    "redacted_evidence_aggregate": {
                        "type": "object",
                        "description": "Optional existing BioCortex redacted evidence aggregate. Required for ready_for_opt_in_experiment."
                    },
                    "candidate_expansion_review_requested": {
                        "type": "boolean",
                        "default": false,
                        "description": "When true, evaluate recall_expansion_summary for candidate-expansion review readiness without approving expansion."
                    },
                    "recall_expansion_summary": {
                        "type": "object",
                        "description": "Optional memory_biocortex_recall_expansion_summary output. Output consumes only safe aggregate fields and never echoes case rows."
                    },
                    "min_shadow_trials": {
                        "type": "integer",
                        "minimum": 1,
                        "maximum": 100,
                        "default": 3
                    },
                    "min_evaluated_count": {
                        "type": "integer",
                        "minimum": 1,
                        "maximum": 10000,
                        "default": 10
                    },
                    "min_mrr_lift": {
                        "type": "number",
                        "minimum": 0.0,
                        "default": 0.001
                    },
                    "min_improved_count": {
                        "type": "integer",
                        "minimum": 0,
                        "maximum": 10000,
                        "default": 0
                    },
                    "min_improved_rate": {
                        "type": "number",
                        "minimum": 0.0,
                        "maximum": 1.0,
                        "default": 0.0
                    },
                    "max_worsened": {
                        "type": "integer",
                        "minimum": 0,
                        "default": 0
                    },
                    "min_recall_evaluated_count": {
                        "type": "integer",
                        "minimum": 1,
                        "maximum": 10000,
                        "default": 8
                    },
                    "min_baseline_miss_count": {
                        "type": "integer",
                        "minimum": 1,
                        "maximum": 10000,
                        "default": 1
                    },
                    "min_candidate_expansion_added_hit_count": {
                        "type": "integer",
                        "minimum": 1,
                        "maximum": 10000,
                        "default": 1
                    },
                    "min_candidate_expansion_added_hit_rate": {
                        "type": "number",
                        "minimum": 0.0,
                        "maximum": 1.0,
                        "default": 0.10
                    },
                    "max_recall_search_error_count": {
                        "type": "integer",
                        "minimum": 0,
                        "default": 0
                    }
                }
            }),
        }
    }

    async fn execute(&self, args: Value, _ctx: &ToolContext) -> Result<ToolResult> {
        Ok(ToolResult::json_text(
            &memory_biocortex_t6_influence_gate_payload(args),
        ))
    }
}

pub(super) const MEMORY_BIOCORTEX_T6_CANDIDATE_EXPANSION_REVIEW_PACKET_SCHEMA: &str =
    "agent_bridge.memory_biocortex_t6_candidate_expansion_review_packet.v0";
pub(super) const MEMORY_BIOCORTEX_T6_CANDIDATE_EXPANSION_DRY_RUN_PLAN_SCHEMA: &str =
    "agent_bridge.memory_biocortex_t6_candidate_expansion_dry_run_plan.v0";
pub(super) const MEMORY_BIOCORTEX_T6_CANDIDATE_EXPANSION_DRY_RUN_REPORT_SCHEMA: &str =
    "agent_bridge.memory_biocortex_t6_candidate_expansion_dry_run_report.v0";
pub(super) const MEMORY_BIOCORTEX_T6_CANDIDATE_EXPANSION_HUMAN_REVIEW_PACKET_SCHEMA: &str =
    "agent_bridge.memory_biocortex_t6_candidate_expansion_human_review_packet.v0";
pub(super) const MEMORY_BIOCORTEX_T6_CANDIDATE_EXPANSION_OWNER_DECISION_RECORD_SCHEMA: &str =
    "agent_bridge.memory_biocortex_t6_candidate_expansion_owner_decision_record.v0";
pub(super) const MEMORY_BIOCORTEX_T6_CANDIDATE_EXPANSION_RUNTIME_GATE_PREFLIGHT_SCHEMA: &str =
    "agent_bridge.memory_biocortex_t6_candidate_expansion_runtime_gate_preflight.v0";
pub(super) const MEMORY_BIOCORTEX_T6_CANDIDATE_EXPANSION_RUNTIME_GATE_DESIGN_ARTIFACT_SCHEMA: &str =
    "agent_bridge.memory_biocortex_t6_candidate_expansion_runtime_gate_design_artifact.v0";
pub(super) const MEMORY_BIOCORTEX_T6_CANDIDATE_EXPANSION_RUNTIME_GATE_OWNER_REVIEW_RECORD_SCHEMA: &str =
    "agent_bridge.memory_biocortex_t6_candidate_expansion_runtime_gate_owner_review_record.v0";
pub(super) const MEMORY_BIOCORTEX_T6_CANDIDATE_EXPANSION_RUNTIME_GATE_IMPLEMENTATION_PLAN_ARTIFACT_SCHEMA:
    &str =
    "agent_bridge.memory_biocortex_t6_candidate_expansion_runtime_gate_implementation_plan_artifact.v0";
pub(super) const MEMORY_BIOCORTEX_T6_CANDIDATE_EXPANSION_RUNTIME_GATE_CODE_IMPLEMENTATION_GATE_SCHEMA: &str =
    "agent_bridge.memory_biocortex_t6_candidate_expansion_runtime_gate_code_implementation_gate.v0";

pub(super) fn memory_biocortex_t6_clamp_label(value: &str, max_bytes: usize) -> String {
    let value = value.trim();
    if value.len() <= max_bytes {
        return value.to_string();
    }
    let mut end = 0;
    for (idx, _) in value.char_indices() {
        if idx > max_bytes {
            break;
        }
        end = idx;
    }
    value[..end].to_string()
}

pub(super) fn memory_biocortex_t6_candidate_expansion_review_packet_payload(args: Value) -> Value {
    let gate = args.get("t6_influence_gate").unwrap_or(&Value::Null);
    let reviewer = args
        .get("reviewer")
        .and_then(Value::as_str)
        .map(|s| memory_biocortex_t6_clamp_label(s, 80))
        .filter(|s| !s.is_empty());
    let commit = args
        .get("commit")
        .and_then(Value::as_str)
        .map(|s| memory_biocortex_t6_clamp_label(s, 80))
        .filter(|s| !s.is_empty());
    let forum_post_id = args
        .get("forum_post_id")
        .and_then(Value::as_str)
        .map(|s| memory_biocortex_t6_clamp_label(s, 80))
        .filter(|s| !s.is_empty());
    let memory_key = args
        .get("memory_key")
        .and_then(Value::as_str)
        .map(|s| memory_biocortex_t6_clamp_label(s, 160))
        .filter(|s| !s.is_empty());
    let review_scope = args
        .get("review_scope")
        .and_then(Value::as_str)
        .map(|s| memory_biocortex_t6_clamp_label(s, 120))
        .filter(|s| !s.is_empty())
        .unwrap_or_else(|| "t6_candidate_expansion_human_review".to_string());

    let gate_schema_valid = memory_biocortex_t6_string_at(gate, "/schema")
        == Some(MEMORY_BIOCORTEX_T6_INFLUENCE_GATE_SCHEMA);
    let gate_safe_contract = memory_biocortex_t6_bool_at(gate, "/read_only") == Some(true)
        && memory_biocortex_t6_bool_at(gate, "/calls_memory_search") == Some(false)
        && memory_biocortex_t6_bool_at(gate, "/runs_biocortex") == Some(false)
        && memory_biocortex_t6_bool_at(gate, "/writes_memory") == Some(false)
        && memory_biocortex_t6_bool_at(gate, "/changes_memory_search_order") == Some(false);
    let source_claims_runtime_authority = memory_biocortex_t6_any_true(
        gate,
        &[
            "/candidate_expansion_gate/candidate_expansion_experiment_approved",
            "/candidate_expansion_gate/may_expand_candidate_set_now",
            "/candidate_expansion_gate/changes_candidate_set_now",
        ],
    );
    let mut source_gate_warnings = Vec::<String>::new();
    if !gate_schema_valid {
        source_gate_warnings.push("source_gate_schema_invalid".to_string());
    }
    if !gate_safe_contract {
        source_gate_warnings.push("source_gate_safety_contract_invalid".to_string());
    }
    if source_claims_runtime_authority {
        source_gate_warnings.push("source_gate_claims_candidate_expansion_authority".to_string());
    }
    if memory_biocortex_t6_has_raw_payload_fields(gate)
        || gate.get("case_rows").is_some()
        || memory_biocortex_t6_any_true(
            gate,
            &[
                "/input_contract/raw_query_included",
                "/input_contract/raw_queries_included",
                "/input_contract/raw_keys_included",
                "/input_contract/content_included",
                "/input_contract/recall_expansion_summary_included",
            ],
        )
    {
        source_gate_warnings.push("source_gate_contains_or_flags_raw_payload".to_string());
    }

    let requested =
        memory_biocortex_t6_bool_at(gate, "/candidate_expansion_gate/requested").unwrap_or(false);
    let gate_ready = memory_biocortex_t6_bool_at(
        gate,
        "/candidate_expansion_gate/ready_for_candidate_expansion_review",
    )
    .unwrap_or(false);
    let ready =
        gate_schema_valid && gate_safe_contract && !source_claims_runtime_authority && gate_ready;
    let block_reasons =
        memory_biocortex_t6_string_array_at(gate, "/candidate_expansion_gate/block_reasons");
    let review_caveats = memory_biocortex_t6_string_array_at(
        gate,
        "/candidate_expansion_gate/evidence_strength/review_caveats",
    );
    let source_next_gate = memory_biocortex_t6_string_at(
        gate,
        "/candidate_expansion_gate/decision/next_gate",
    )
    .unwrap_or(if ready {
        "human_review_before_candidate_expansion_experiment"
    } else if requested {
        "collect_more_redacted_recall_expansion_evidence"
    } else {
        "provide_recall_expansion_summary_when_evaluating_candidate_expansion"
    });
    let verdict = if ready {
        "ready_for_human_review"
    } else if requested {
        "blocked_collect_more_evidence"
    } else {
        "not_requested"
    };
    let next_gate = if ready {
        "human_review_before_candidate_expansion_experiment"
    } else {
        source_next_gate
    };

    json!({
        "schema": MEMORY_BIOCORTEX_T6_CANDIDATE_EXPANSION_REVIEW_PACKET_SCHEMA,
        "generated_at": unix_now_secs(),
        "read_only": true,
        "purpose": "T6 candidate-expansion review packet: consume the redacted T6 influence gate aggregate and prepare a human-review contract without approving or applying runtime candidate-set expansion.",
        "review_scope": review_scope,
        "candidate_expansion_review": {
            "requested": requested,
            "ready": ready,
            "block_reasons": block_reasons,
            "source_gate_warnings": source_gate_warnings,
            "decision": {
                "verdict": verdict,
                "next_gate": next_gate,
                "human_review_required": true,
                "candidate_expansion_authority_out_of_scope": true,
            },
            "metrics": {
                "evaluated_count": memory_biocortex_t6_u64_at(gate, "/candidate_expansion_gate/metrics/evaluated_count"),
                "search_error_count": memory_biocortex_t6_u64_at(gate, "/candidate_expansion_gate/metrics/search_error_count"),
                "baseline_miss_count": memory_biocortex_t6_u64_at(gate, "/candidate_expansion_gate/metrics/baseline_miss_count"),
                "graph_expansion_found_count": memory_biocortex_t6_u64_at(gate, "/candidate_expansion_gate/metrics/graph_expansion_found_count"),
                "expanded_hit_count": memory_biocortex_t6_u64_at(gate, "/candidate_expansion_gate/metrics/expanded_hit_count"),
                "candidate_expansion_added_hit_count": memory_biocortex_t6_u64_at(gate, "/candidate_expansion_gate/metrics/candidate_expansion_added_hit_count"),
                "candidate_expansion_added_hit_rate": memory_biocortex_t6_f64_at(gate, "/candidate_expansion_gate/metrics/candidate_expansion_added_hit_rate"),
            },
            "thresholds": {
                "min_recall_evaluated_count": memory_biocortex_t6_u64_at(gate, "/candidate_expansion_gate/thresholds/min_recall_evaluated_count"),
                "min_baseline_miss_count": memory_biocortex_t6_u64_at(gate, "/candidate_expansion_gate/thresholds/min_baseline_miss_count"),
                "min_candidate_expansion_added_hit_count": memory_biocortex_t6_u64_at(gate, "/candidate_expansion_gate/thresholds/min_candidate_expansion_added_hit_count"),
                "min_candidate_expansion_added_hit_rate": memory_biocortex_t6_f64_at(gate, "/candidate_expansion_gate/thresholds/min_candidate_expansion_added_hit_rate"),
                "max_recall_search_error_count": memory_biocortex_t6_u64_at(gate, "/candidate_expansion_gate/thresholds/max_recall_search_error_count"),
            },
            "evidence_strength": {
                "tier": memory_biocortex_t6_string_at(gate, "/candidate_expansion_gate/evidence_strength/tier"),
                "review_caveats": review_caveats,
            },
        },
        "review_contract": {
            "human_review_required": true,
            "candidate_expansion_experiment_approved": false,
            "may_expand_candidate_set_now": false,
            "changes_candidate_set_now": false,
            "runtime_influence_approved": false,
            "may_change_search_order_now": false,
            "requires_separate_owner_approval": true,
            "requires_separate_dry_run_experiment_plan": true,
        },
        "review_checklist": [
            "Confirm evidence source is a deployed memory_biocortex_t6_influence_gate packet.",
            "Inspect candidate-expansion metrics, thresholds, block reasons, and evidence-strength caveats.",
            "Compare against the current first-stage FTS baseline, including the v36 continuity retrieval-trigger projection.",
            "Require a separate explicit owner decision before any candidate-expansion experiment.",
            "Require a separate dry-run experiment plan before any runtime candidate-set expansion path exists."
        ],
        "decision": {
            "verdict": verdict,
            "next_gate": next_gate,
            "human_review_required": true,
            "candidate_expansion_authority_out_of_scope": true,
        },
        "links": {
            "reviewer": reviewer,
            "commit": commit,
            "forum_post_id": forum_post_id,
            "memory_key": memory_key,
        },
        "input_contract": {
            "source_gate_included": false,
            "recall_expansion_summary_included": false,
            "case_rows_included": false,
            "raw_query_included": false,
            "raw_queries_included": false,
            "raw_keys_included": false,
            "content_included": false,
        },
        "non_goals": [
            "Does not run BioCortex.",
            "Does not call memory_search or memory_neighbors.",
            "Does not write memory, graph edges, authorization records, or approval packets.",
            "Does not approve runtime influence, search-order changes, or candidate-set expansion.",
            "Does not include raw gate payloads, recall expansion summaries, case rows, queries, keys, or content."
        ],
    })
}

pub struct MemoryBioCortexT6CandidateExpansionReviewPacketTool;
impl MemoryBioCortexT6CandidateExpansionReviewPacketTool {
    pub fn new() -> Self {
        Self
    }
}
#[async_trait]
impl McpTool for MemoryBioCortexT6CandidateExpansionReviewPacketTool {
    fn name(&self) -> &'static str {
        "memory_biocortex_t6_candidate_expansion_review_packet"
    }
    fn schema(&self) -> ToolSchema {
        ToolSchema {
            name: self.name().into(),
            description: "Read-only T6 candidate-expansion human review packet. \
                Consumes a memory_biocortex_t6_influence_gate output and emits \
                a safe review contract without echoing the raw gate, recall \
                summary, case rows, query/key/content fields, or approving \
                runtime candidate-set expansion."
                .into(),
            input_schema: json!({
                "type": "object",
                "required": ["t6_influence_gate"],
                "properties": {
                    "t6_influence_gate": {
                        "type": "object",
                        "description": "JSON object produced by memory_biocortex_t6_influence_gate. Unknown/raw fields are ignored and never echoed."
                    },
                    "reviewer": {
                        "type": "string",
                        "description": "Optional reviewer identity or handle."
                    },
                    "commit": {
                        "type": "string",
                        "description": "Optional implementation commit under review."
                    },
                    "forum_post_id": {
                        "type": "string",
                        "description": "Optional forum post id linking this review packet."
                    },
                    "memory_key": {
                        "type": "string",
                        "description": "Optional memory key linking this review packet."
                    },
                    "review_scope": {
                        "type": "string",
                        "description": "Optional short review scope label."
                    }
                }
            }),
        }
    }

    async fn execute(&self, args: Value, _ctx: &ToolContext) -> Result<ToolResult> {
        Ok(ToolResult::json_text(
            &memory_biocortex_t6_candidate_expansion_review_packet_payload(args),
        ))
    }
}

pub(super) fn memory_biocortex_t6_candidate_expansion_dry_run_plan_payload(args: Value) -> Value {
    let packet = args
        .get("candidate_expansion_review_packet")
        .unwrap_or(&Value::Null);
    let reviewer = args
        .get("reviewer")
        .and_then(Value::as_str)
        .map(|s| memory_biocortex_t6_clamp_label(s, 80))
        .filter(|s| !s.is_empty());
    let commit = args
        .get("commit")
        .and_then(Value::as_str)
        .map(|s| memory_biocortex_t6_clamp_label(s, 80))
        .filter(|s| !s.is_empty());
    let forum_post_id = args
        .get("forum_post_id")
        .and_then(Value::as_str)
        .map(|s| memory_biocortex_t6_clamp_label(s, 80))
        .filter(|s| !s.is_empty());
    let memory_key = args
        .get("memory_key")
        .and_then(Value::as_str)
        .map(|s| memory_biocortex_t6_clamp_label(s, 160))
        .filter(|s| !s.is_empty());
    let min_dry_run_cases = args
        .get("min_dry_run_cases")
        .and_then(Value::as_u64)
        .unwrap_or(30)
        .clamp(8, 10_000);
    let sampling_strategy = args
        .get("sampling_strategy")
        .and_then(Value::as_str)
        .map(|s| memory_biocortex_t6_clamp_label(s, 120))
        .filter(|s| !s.is_empty())
        .unwrap_or_else(|| "less_handpicked_baseline_miss_corpus".to_string());

    let packet_schema_valid = memory_biocortex_t6_string_at(packet, "/schema")
        == Some(MEMORY_BIOCORTEX_T6_CANDIDATE_EXPANSION_REVIEW_PACKET_SCHEMA);
    let packet_ready =
        memory_biocortex_t6_bool_at(packet, "/candidate_expansion_review/ready") == Some(true);
    let packet_safe_contract = memory_biocortex_t6_bool_at(packet, "/read_only") == Some(true)
        && memory_biocortex_t6_bool_at(
            packet,
            "/review_contract/candidate_expansion_experiment_approved",
        ) == Some(false)
        && memory_biocortex_t6_bool_at(packet, "/review_contract/may_expand_candidate_set_now")
            == Some(false)
        && memory_biocortex_t6_bool_at(packet, "/review_contract/changes_candidate_set_now")
            == Some(false)
        && memory_biocortex_t6_bool_at(packet, "/review_contract/runtime_influence_approved")
            == Some(false)
        && memory_biocortex_t6_bool_at(packet, "/review_contract/may_change_search_order_now")
            == Some(false);
    let packet_claims_runtime_authority = memory_biocortex_t6_any_true(
        packet,
        &[
            "/review_contract/candidate_expansion_experiment_approved",
            "/review_contract/may_expand_candidate_set_now",
            "/review_contract/changes_candidate_set_now",
            "/review_contract/runtime_influence_approved",
            "/review_contract/may_change_search_order_now",
        ],
    );
    let packet_flags_raw = memory_biocortex_t6_has_raw_payload_fields(packet)
        || memory_biocortex_t6_any_true(
            packet,
            &[
                "/input_contract/source_gate_included",
                "/input_contract/recall_expansion_summary_included",
                "/input_contract/case_rows_included",
                "/input_contract/raw_query_included",
                "/input_contract/raw_queries_included",
                "/input_contract/raw_keys_included",
                "/input_contract/content_included",
            ],
        );
    let mut block_reasons = BTreeSet::<String>::new();
    if !packet_schema_valid {
        memory_biocortex_t6_push_reason(&mut block_reasons, "source_review_packet_schema_invalid");
    }
    if !packet_ready {
        memory_biocortex_t6_push_reason(&mut block_reasons, "source_review_packet_not_ready");
    }
    if !packet_safe_contract || packet_claims_runtime_authority {
        memory_biocortex_t6_push_reason(
            &mut block_reasons,
            "source_review_packet_claims_runtime_authority",
        );
    }
    if packet_flags_raw {
        memory_biocortex_t6_push_reason(&mut block_reasons, "source_review_packet_contains_raw");
    }

    let source_block_reasons =
        memory_biocortex_t6_string_array_at(packet, "/candidate_expansion_review/block_reasons");
    for reason in source_block_reasons {
        memory_biocortex_t6_push_reason(&mut block_reasons, &reason);
    }
    let ready = block_reasons.is_empty();
    let verdict = if ready {
        "plan_ready_for_owner_review"
    } else {
        "blocked_collect_more_review_evidence"
    };
    let next_gate = if ready {
        "owner_review_before_any_candidate_expansion_dry_run"
    } else {
        "produce_ready_candidate_expansion_review_packet"
    };

    json!({
        "schema": MEMORY_BIOCORTEX_T6_CANDIDATE_EXPANSION_DRY_RUN_PLAN_SCHEMA,
        "generated_at": unix_now_secs(),
        "read_only": true,
        "purpose": "T6 candidate-expansion dry-run plan: consume a sanitized human-review packet and specify a less-handpicked baseline-miss sampling contract before any runtime candidate-set expansion path exists.",
        "dry_run_plan": {
            "ready": ready,
            "block_reasons": block_reasons.into_iter().collect::<Vec<_>>(),
            "decision": {
                "verdict": verdict,
                "next_gate": next_gate,
                "owner_review_required": true,
                "dry_run_authority_out_of_scope": true,
                "candidate_expansion_authority_out_of_scope": true,
            },
            "sampling_contract": {
                "strategy": sampling_strategy,
                "min_dry_run_cases": min_dry_run_cases,
                "requires_less_handpicked_baseline_miss_corpus": true,
                "requires_deterministic_sampling_seed": true,
                "requires_redacted_case_ids": true,
                "requires_negative_controls": true,
                "requires_trigger_projection_stratum": true,
                "requires_baseline_miss_stratum": true,
                "requires_graph_neighbor_recovery_stratum": true,
                "exclude_raw_queries_keys_and_content": true,
                "exclude_runtime_candidate_set_changes": true,
            },
            "metrics": {
                "evaluated_count": memory_biocortex_t6_u64_at(packet, "/candidate_expansion_review/metrics/evaluated_count"),
                "search_error_count": memory_biocortex_t6_u64_at(packet, "/candidate_expansion_review/metrics/search_error_count"),
                "baseline_miss_count": memory_biocortex_t6_u64_at(packet, "/candidate_expansion_review/metrics/baseline_miss_count"),
                "graph_expansion_found_count": memory_biocortex_t6_u64_at(packet, "/candidate_expansion_review/metrics/graph_expansion_found_count"),
                "expanded_hit_count": memory_biocortex_t6_u64_at(packet, "/candidate_expansion_review/metrics/expanded_hit_count"),
                "candidate_expansion_added_hit_count": memory_biocortex_t6_u64_at(packet, "/candidate_expansion_review/metrics/candidate_expansion_added_hit_count"),
                "candidate_expansion_added_hit_rate": memory_biocortex_t6_f64_at(packet, "/candidate_expansion_review/metrics/candidate_expansion_added_hit_rate"),
            },
            "thresholds": {
                "min_recall_evaluated_count": memory_biocortex_t6_u64_at(packet, "/candidate_expansion_review/thresholds/min_recall_evaluated_count"),
                "min_baseline_miss_count": memory_biocortex_t6_u64_at(packet, "/candidate_expansion_review/thresholds/min_baseline_miss_count"),
                "min_candidate_expansion_added_hit_count": memory_biocortex_t6_u64_at(packet, "/candidate_expansion_review/thresholds/min_candidate_expansion_added_hit_count"),
                "min_candidate_expansion_added_hit_rate": memory_biocortex_t6_f64_at(packet, "/candidate_expansion_review/thresholds/min_candidate_expansion_added_hit_rate"),
                "max_recall_search_error_count": memory_biocortex_t6_u64_at(packet, "/candidate_expansion_review/thresholds/max_recall_search_error_count"),
            },
            "evidence_strength": {
                "tier": memory_biocortex_t6_string_at(packet, "/candidate_expansion_review/evidence_strength/tier"),
                "review_caveats": memory_biocortex_t6_string_array_at(packet, "/candidate_expansion_review/evidence_strength/review_caveats"),
            },
        },
        "experiment_contract": {
            "candidate_expansion_experiment_approved": false,
            "may_run_candidate_expansion_dry_run_now": false,
            "may_expand_candidate_set_now": false,
            "changes_candidate_set_now": false,
            "runtime_influence_approved": false,
            "may_change_search_order_now": false,
            "requires_separate_owner_approval": true,
            "requires_separate_dry_run_executor": true,
            "requires_post_dry_run_human_decision": true,
        },
        "review_checklist": [
            "Confirm the source packet is a deployed memory_biocortex_t6_candidate_expansion_review_packet output.",
            "Confirm the prior evidence is weak or narrow enough to require a broader dry-run corpus before runtime work.",
            "Define deterministic sampling over baseline misses instead of handpicked recovery examples.",
            "Include negative controls and trigger-projection strata so candidate expansion cannot win by construction.",
            "Require a separate owner decision before running even the dry-run executor.",
            "Require a separate post-dry-run decision before any runtime candidate-set expansion path exists."
        ],
        "decision": {
            "verdict": verdict,
            "next_gate": next_gate,
            "owner_review_required": true,
            "candidate_expansion_authority_out_of_scope": true,
        },
        "links": {
            "reviewer": reviewer,
            "commit": commit,
            "forum_post_id": forum_post_id,
            "memory_key": memory_key,
        },
        "input_contract": {
            "review_packet_included": false,
            "source_gate_included": false,
            "recall_expansion_summary_included": false,
            "case_rows_included": false,
            "raw_query_included": false,
            "raw_queries_included": false,
            "raw_keys_included": false,
            "content_included": false,
        },
        "non_goals": [
            "Does not run BioCortex.",
            "Does not call memory_search or memory_neighbors.",
            "Does not sample production memories or graph rows.",
            "Does not write memory, graph edges, authorization records, or approval packets.",
            "Does not approve or execute a dry-run experiment.",
            "Does not approve runtime influence, search-order changes, or candidate-set expansion.",
            "Does not include raw review packets, gate payloads, recall summaries, case rows, queries, keys, or content."
        ],
    })
}

pub struct MemoryBioCortexT6CandidateExpansionDryRunPlanTool;
impl MemoryBioCortexT6CandidateExpansionDryRunPlanTool {
    pub fn new() -> Self {
        Self
    }
}
#[async_trait]
impl McpTool for MemoryBioCortexT6CandidateExpansionDryRunPlanTool {
    fn name(&self) -> &'static str {
        "memory_biocortex_t6_candidate_expansion_dry_run_plan"
    }
    fn schema(&self) -> ToolSchema {
        ToolSchema {
            name: self.name().into(),
            description: "Read-only T6 candidate-expansion dry-run plan. \
                Consumes a sanitized candidate-expansion review packet and emits \
                a sampling/review contract for a later dry-run executor. It never \
                echoes raw packets, calls memory_search, samples memories, writes \
                state, approves a dry-run, or expands the runtime candidate set."
                .into(),
            input_schema: json!({
                "type": "object",
                "required": ["candidate_expansion_review_packet"],
                "properties": {
                    "candidate_expansion_review_packet": {
                        "type": "object",
                        "description": "JSON object produced by memory_biocortex_t6_candidate_expansion_review_packet. Unknown/raw fields are ignored and never echoed."
                    },
                    "reviewer": {
                        "type": "string",
                        "description": "Optional reviewer identity or handle."
                    },
                    "commit": {
                        "type": "string",
                        "description": "Optional implementation commit under review."
                    },
                    "forum_post_id": {
                        "type": "string",
                        "description": "Optional forum post id linking this dry-run plan."
                    },
                    "memory_key": {
                        "type": "string",
                        "description": "Optional memory key linking this dry-run plan."
                    },
                    "min_dry_run_cases": {
                        "type": "integer",
                        "minimum": 8,
                        "maximum": 10000,
                        "default": 30,
                        "description": "Minimum redacted dry-run cases to require in the later executor."
                    },
                    "sampling_strategy": {
                        "type": "string",
                        "description": "Optional short label for the planned baseline-miss sampling strategy."
                    }
                }
            }),
        }
    }

    async fn execute(&self, args: Value, _ctx: &ToolContext) -> Result<ToolResult> {
        Ok(ToolResult::json_text(
            &memory_biocortex_t6_candidate_expansion_dry_run_plan_payload(args),
        ))
    }
}

pub(super) fn memory_biocortex_t6_candidate_expansion_dry_run_report_payload(args: Value) -> Value {
    let plan = args
        .get("candidate_expansion_dry_run_plan")
        .unwrap_or(&Value::Null);
    let summary = args
        .get("recall_expansion_summary")
        .unwrap_or(&Value::Null);
    let reviewer = args
        .get("reviewer")
        .and_then(Value::as_str)
        .map(|s| memory_biocortex_t6_clamp_label(s, 80))
        .filter(|s| !s.is_empty());
    let commit = args
        .get("commit")
        .and_then(Value::as_str)
        .map(|s| memory_biocortex_t6_clamp_label(s, 80))
        .filter(|s| !s.is_empty());
    let forum_post_id = args
        .get("forum_post_id")
        .and_then(Value::as_str)
        .map(|s| memory_biocortex_t6_clamp_label(s, 80))
        .filter(|s| !s.is_empty());
    let memory_key = args
        .get("memory_key")
        .and_then(Value::as_str)
        .map(|s| memory_biocortex_t6_clamp_label(s, 160))
        .filter(|s| !s.is_empty());

    let plan_schema_valid = memory_biocortex_t6_string_at(plan, "/schema")
        == Some(MEMORY_BIOCORTEX_T6_CANDIDATE_EXPANSION_DRY_RUN_PLAN_SCHEMA);
    let plan_ready = memory_biocortex_t6_bool_at(plan, "/dry_run_plan/ready") == Some(true);
    let plan_safe_contract = memory_biocortex_t6_bool_at(plan, "/read_only") == Some(true)
        && memory_biocortex_t6_bool_at(
            plan,
            "/experiment_contract/candidate_expansion_experiment_approved",
        ) == Some(false)
        && memory_biocortex_t6_bool_at(
            plan,
            "/experiment_contract/may_run_candidate_expansion_dry_run_now",
        ) == Some(false)
        && memory_biocortex_t6_bool_at(
            plan,
            "/experiment_contract/may_expand_candidate_set_now",
        ) == Some(false)
        && memory_biocortex_t6_bool_at(plan, "/experiment_contract/changes_candidate_set_now")
            == Some(false)
        && memory_biocortex_t6_bool_at(plan, "/experiment_contract/runtime_influence_approved")
            == Some(false)
        && memory_biocortex_t6_bool_at(plan, "/experiment_contract/may_change_search_order_now")
            == Some(false);
    let plan_claims_authority = memory_biocortex_t6_any_true(
        plan,
        &[
            "/experiment_contract/candidate_expansion_experiment_approved",
            "/experiment_contract/may_run_candidate_expansion_dry_run_now",
            "/experiment_contract/may_expand_candidate_set_now",
            "/experiment_contract/changes_candidate_set_now",
            "/experiment_contract/runtime_influence_approved",
            "/experiment_contract/may_change_search_order_now",
        ],
    );
    let plan_flags_raw = memory_biocortex_t6_has_raw_payload_fields(plan)
        || memory_biocortex_t6_any_true(
            plan,
            &[
                "/input_contract/review_packet_included",
                "/input_contract/source_gate_included",
                "/input_contract/recall_expansion_summary_included",
                "/input_contract/case_rows_included",
                "/input_contract/raw_query_included",
                "/input_contract/raw_queries_included",
                "/input_contract/raw_keys_included",
                "/input_contract/content_included",
            ],
        );

    let summary_schema_valid = memory_biocortex_t6_string_at(summary, "/schema")
        == Some(MEMORY_BIOCORTEX_RECALL_EXPANSION_SUMMARY_SCHEMA);
    let summary_safe_contract = memory_biocortex_t6_bool_at(summary, "/read_only") == Some(true)
        && memory_biocortex_t6_bool_at(summary, "/safety/writes_memory") == Some(false)
        && memory_biocortex_t6_bool_at(summary, "/safety/writes_state") == Some(false)
        && memory_biocortex_t6_bool_at(summary, "/safety/runs_biocortex") == Some(false)
        && memory_biocortex_t6_bool_at(summary, "/safety/changes_search_order") == Some(false)
        && memory_biocortex_t6_bool_at(summary, "/safety/changes_prod_retrieval_order")
            == Some(false)
        && memory_biocortex_t6_bool_at(summary, "/safety/changes_candidate_set_now")
            == Some(false);
    let summary_claims_authority = memory_biocortex_t6_any_true(
        summary,
        &[
            "/safety/writes_memory",
            "/safety/writes_state",
            "/safety/runs_biocortex",
            "/safety/changes_search_order",
            "/safety/changes_prod_retrieval_order",
            "/safety/changes_candidate_set_now",
            "/changes_candidate_set_now",
            "/changes_memory_search_order",
        ],
    );
    let summary_flags_raw = memory_biocortex_t6_has_raw_payload_fields(summary)
        || summary.get("case_rows").is_some()
        || memory_biocortex_t6_any_true(
            summary,
            &[
                "/input_contract/raw_query_included",
                "/input_contract/raw_queries_included",
                "/input_contract/raw_keys_included",
                "/input_contract/content_included",
                "/input_contract/candidate_content_included",
                "/input_contract/raw_error_included",
            ],
        );

    let min_dry_run_cases =
        memory_biocortex_t6_u64_at(plan, "/dry_run_plan/sampling_contract/min_dry_run_cases")
            .unwrap_or(30);
    let evaluated_count = memory_biocortex_t6_u64_at(summary, "/metrics/evaluated_count");
    let search_error_count = memory_biocortex_t6_u64_at(summary, "/metrics/search_error_count");
    let baseline_miss_count = memory_biocortex_t6_u64_at(summary, "/metrics/baseline_miss_count");
    let added_hit_count =
        memory_biocortex_t6_u64_at(summary, "/metrics/candidate_expansion_added_hit_count");
    let enough_cases = evaluated_count.unwrap_or(0) >= min_dry_run_cases;
    let no_search_errors = search_error_count.unwrap_or(u64::MAX) == 0;
    let has_baseline_misses = baseline_miss_count.unwrap_or(0) > 0;

    let mut block_reasons = BTreeSet::<String>::new();
    if !plan_schema_valid {
        memory_biocortex_t6_push_reason(&mut block_reasons, "source_dry_run_plan_schema_invalid");
    }
    if !plan_ready {
        memory_biocortex_t6_push_reason(&mut block_reasons, "source_dry_run_plan_not_ready");
    }
    if !plan_safe_contract || plan_claims_authority {
        memory_biocortex_t6_push_reason(
            &mut block_reasons,
            "source_dry_run_plan_claims_runtime_authority",
        );
    }
    if plan_flags_raw {
        memory_biocortex_t6_push_reason(&mut block_reasons, "source_dry_run_plan_contains_raw");
    }
    if !summary_schema_valid {
        memory_biocortex_t6_push_reason(
            &mut block_reasons,
            "recall_expansion_summary_schema_invalid",
        );
    }
    if !summary_safe_contract || summary_claims_authority {
        memory_biocortex_t6_push_reason(
            &mut block_reasons,
            "recall_expansion_summary_claims_runtime_authority",
        );
    }
    if summary_flags_raw {
        memory_biocortex_t6_push_reason(
            &mut block_reasons,
            "recall_expansion_summary_contains_raw_or_case_rows",
        );
    }
    if !enough_cases {
        memory_biocortex_t6_push_reason(&mut block_reasons, "insufficient_dry_run_cases");
    }
    if !no_search_errors {
        memory_biocortex_t6_push_reason(&mut block_reasons, "recall_expansion_search_errors");
    }
    if !has_baseline_misses {
        memory_biocortex_t6_push_reason(&mut block_reasons, "missing_baseline_miss_stratum");
    }

    let ready = block_reasons.is_empty();
    let verdict = if ready {
        "dry_run_report_ready_for_human_review"
    } else {
        "blocked_collect_more_dry_run_evidence"
    };
    let next_gate = if ready {
        "post_dry_run_human_decision_before_candidate_set_expansion"
    } else {
        "produce_ready_redacted_candidate_expansion_dry_run"
    };

    json!({
        "schema": MEMORY_BIOCORTEX_T6_CANDIDATE_EXPANSION_DRY_RUN_REPORT_SCHEMA,
        "generated_at": unix_now_secs(),
        "read_only": true,
        "purpose": "T6 candidate-expansion dry-run report: consume a ready dry-run plan plus a redacted recall-expansion summary, then report aggregate dry-run evidence without running search, sampling memories, echoing raw rows, or granting runtime candidate-set authority.",
        "dry_run_report": {
            "ready": ready,
            "block_reasons": block_reasons.into_iter().collect::<Vec<_>>(),
            "decision": {
                "verdict": verdict,
                "next_gate": next_gate,
                "human_review_required": true,
                "candidate_expansion_authority_out_of_scope": true,
            },
            "sampling_contract": {
                "min_dry_run_cases": min_dry_run_cases,
                "actual_evaluated_count": evaluated_count,
                "enough_cases": enough_cases,
                "requires_less_handpicked_baseline_miss_corpus": memory_biocortex_t6_bool_at(plan, "/dry_run_plan/sampling_contract/requires_less_handpicked_baseline_miss_corpus"),
                "requires_negative_controls": memory_biocortex_t6_bool_at(plan, "/dry_run_plan/sampling_contract/requires_negative_controls"),
                "requires_trigger_projection_stratum": memory_biocortex_t6_bool_at(plan, "/dry_run_plan/sampling_contract/requires_trigger_projection_stratum"),
            },
            "metrics": {
                "evaluated_count": evaluated_count,
                "search_error_count": search_error_count,
                "baseline_hit_count": memory_biocortex_t6_u64_at(summary, "/metrics/baseline_hit_count"),
                "baseline_miss_count": baseline_miss_count,
                "graph_expansion_found_count": memory_biocortex_t6_u64_at(summary, "/metrics/graph_expansion_found_count"),
                "expanded_hit_count": memory_biocortex_t6_u64_at(summary, "/metrics/expanded_hit_count"),
                "candidate_expansion_added_hit_count": added_hit_count,
                "candidate_expansion_added_hit_rate": memory_biocortex_t6_f64_at(summary, "/metrics/candidate_expansion_added_hit_rate"),
                "graph_expansion_found_rate": memory_biocortex_t6_f64_at(summary, "/metrics/graph_expansion_found_rate"),
            },
            "evidence_strength": {
                "tier": if ready && added_hit_count.unwrap_or(0) > 0 {
                    "redacted_dry_run_signal_ready"
                } else if ready {
                    "redacted_dry_run_no_added_hit"
                } else {
                    "blocked"
                },
                "caveats": [
                    "aggregate_only_no_case_rows",
                    "does_not_score_production_runtime_rank",
                    "requires_post_dry_run_human_decision"
                ],
            },
        },
        "experiment_contract": {
            "candidate_expansion_experiment_approved": false,
            "may_run_candidate_expansion_dry_run_now": false,
            "may_expand_candidate_set_now": false,
            "changes_candidate_set_now": false,
            "runtime_influence_approved": false,
            "may_change_search_order_now": false,
            "requires_post_dry_run_human_decision": true,
        },
        "decision": {
            "verdict": verdict,
            "next_gate": next_gate,
            "human_review_required": true,
            "candidate_expansion_authority_out_of_scope": true,
        },
        "links": {
            "reviewer": reviewer,
            "commit": commit,
            "forum_post_id": forum_post_id,
            "memory_key": memory_key,
        },
        "input_contract": {
            "dry_run_plan_included": false,
            "recall_expansion_summary_included": false,
            "case_rows_included": false,
            "raw_query_included": false,
            "raw_queries_included": false,
            "raw_keys_included": false,
            "content_included": false,
            "raw_error_included": false,
        },
        "non_goals": [
            "Does not run BioCortex.",
            "Does not call memory_search or memory_neighbors.",
            "Does not sample production memories or graph rows.",
            "Does not echo dry-run plans, recall summaries, case rows, queries, keys, content, or raw errors.",
            "Does not write memory, graph edges, authorization records, or approval packets.",
            "Does not approve runtime influence, search-order changes, or candidate-set expansion."
        ],
    })
}

pub struct MemoryBioCortexT6CandidateExpansionDryRunReportTool;
impl MemoryBioCortexT6CandidateExpansionDryRunReportTool {
    pub fn new() -> Self {
        Self
    }
}
#[async_trait]
impl McpTool for MemoryBioCortexT6CandidateExpansionDryRunReportTool {
    fn name(&self) -> &'static str {
        "memory_biocortex_t6_candidate_expansion_dry_run_report"
    }

    fn schema(&self) -> ToolSchema {
        ToolSchema {
            name: self.name().into(),
            description: "Read-only T6 candidate-expansion dry-run report. \
                Consumes a dry-run plan and an already-produced redacted \
                recall-expansion summary, then emits aggregate review evidence. \
                It never echoes raw inputs, calls search, samples memories, writes \
                state, approves runtime influence, or expands candidate sets."
                .into(),
            input_schema: json!({
                "type": "object",
                "required": ["candidate_expansion_dry_run_plan", "recall_expansion_summary"],
                "properties": {
                    "candidate_expansion_dry_run_plan": {
                        "type": "object",
                        "description": "JSON object produced by memory_biocortex_t6_candidate_expansion_dry_run_plan. Unknown/raw fields are ignored and never echoed."
                    },
                    "recall_expansion_summary": {
                        "type": "object",
                        "description": "Redacted JSON object produced by memory_biocortex_recall_expansion_summary. case_rows/raw fields are rejected and never echoed."
                    },
                    "reviewer": {
                        "type": "string",
                        "description": "Optional reviewer identity or handle."
                    },
                    "commit": {
                        "type": "string",
                        "description": "Optional implementation commit under review."
                    },
                    "forum_post_id": {
                        "type": "string",
                        "description": "Optional forum post id linking this dry-run report."
                    },
                    "memory_key": {
                        "type": "string",
                        "description": "Optional memory key linking this dry-run report."
                    }
                }
            }),
        }
    }

    async fn execute(&self, args: Value, _ctx: &ToolContext) -> Result<ToolResult> {
        Ok(ToolResult::json_text(
            &memory_biocortex_t6_candidate_expansion_dry_run_report_payload(args),
        ))
    }
}

pub(super) fn memory_biocortex_t6_candidate_expansion_human_review_packet_payload(args: Value) -> Value {
    let report = args
        .get("candidate_expansion_dry_run_report")
        .unwrap_or(&Value::Null);
    let reviewer = args
        .get("reviewer")
        .and_then(Value::as_str)
        .map(|s| memory_biocortex_t6_clamp_label(s, 80))
        .filter(|s| !s.is_empty());
    let commit = args
        .get("commit")
        .and_then(Value::as_str)
        .map(|s| memory_biocortex_t6_clamp_label(s, 80))
        .filter(|s| !s.is_empty());
    let forum_post_id = args
        .get("forum_post_id")
        .and_then(Value::as_str)
        .map(|s| memory_biocortex_t6_clamp_label(s, 80))
        .filter(|s| !s.is_empty());
    let memory_key = args
        .get("memory_key")
        .and_then(Value::as_str)
        .map(|s| memory_biocortex_t6_clamp_label(s, 160))
        .filter(|s| !s.is_empty());

    let report_schema_valid = memory_biocortex_t6_string_at(report, "/schema")
        == Some(MEMORY_BIOCORTEX_T6_CANDIDATE_EXPANSION_DRY_RUN_REPORT_SCHEMA);
    let report_ready = memory_biocortex_t6_bool_at(report, "/dry_run_report/ready") == Some(true);
    let report_safe_contract = memory_biocortex_t6_bool_at(report, "/read_only") == Some(true)
        && memory_biocortex_t6_bool_at(
            report,
            "/experiment_contract/candidate_expansion_experiment_approved",
        ) == Some(false)
        && memory_biocortex_t6_bool_at(
            report,
            "/experiment_contract/may_run_candidate_expansion_dry_run_now",
        ) == Some(false)
        && memory_biocortex_t6_bool_at(
            report,
            "/experiment_contract/may_expand_candidate_set_now",
        ) == Some(false)
        && memory_biocortex_t6_bool_at(report, "/experiment_contract/changes_candidate_set_now")
            == Some(false)
        && memory_biocortex_t6_bool_at(report, "/experiment_contract/runtime_influence_approved")
            == Some(false)
        && memory_biocortex_t6_bool_at(report, "/experiment_contract/may_change_search_order_now")
            == Some(false);
    let report_claims_authority = memory_biocortex_t6_any_true(
        report,
        &[
            "/experiment_contract/candidate_expansion_experiment_approved",
            "/experiment_contract/may_run_candidate_expansion_dry_run_now",
            "/experiment_contract/may_expand_candidate_set_now",
            "/experiment_contract/changes_candidate_set_now",
            "/experiment_contract/runtime_influence_approved",
            "/experiment_contract/may_change_search_order_now",
        ],
    );
    let report_flags_raw = memory_biocortex_t6_has_raw_payload_fields(report)
        || report.get("candidate_expansion_dry_run_plan").is_some()
        || report.get("recall_expansion_summary").is_some()
        || report.get("case_rows").is_some()
        || memory_biocortex_t6_any_true(
            report,
            &[
                "/input_contract/dry_run_plan_included",
                "/input_contract/recall_expansion_summary_included",
                "/input_contract/case_rows_included",
                "/input_contract/raw_query_included",
                "/input_contract/raw_queries_included",
                "/input_contract/raw_keys_included",
                "/input_contract/content_included",
                "/input_contract/raw_error_included",
            ],
        );

    let mut block_reasons = BTreeSet::<String>::new();
    if !report_schema_valid {
        memory_biocortex_t6_push_reason(&mut block_reasons, "source_dry_run_report_schema_invalid");
    }
    if !report_ready {
        memory_biocortex_t6_push_reason(&mut block_reasons, "source_dry_run_report_not_ready");
    }
    if !report_safe_contract || report_claims_authority {
        memory_biocortex_t6_push_reason(
            &mut block_reasons,
            "source_dry_run_report_claims_runtime_authority",
        );
    }
    if report_flags_raw {
        memory_biocortex_t6_push_reason(&mut block_reasons, "source_dry_run_report_contains_raw");
    }
    for reason in memory_biocortex_t6_string_array_at(report, "/dry_run_report/block_reasons") {
        memory_biocortex_t6_push_reason(&mut block_reasons, &reason);
    }

    let ready = block_reasons.is_empty();
    let verdict = if ready {
        "ready_for_post_dry_run_human_decision"
    } else {
        "blocked_collect_more_dry_run_evidence"
    };
    let next_gate = if ready {
        "owner_decision_before_candidate_set_expansion_design"
    } else {
        "produce_ready_redacted_candidate_expansion_dry_run_report"
    };

    json!({
        "schema": MEMORY_BIOCORTEX_T6_CANDIDATE_EXPANSION_HUMAN_REVIEW_PACKET_SCHEMA,
        "generated_at": unix_now_secs(),
        "read_only": true,
        "purpose": "T6 candidate-expansion human-review packet: consume a safe dry-run report and prepare an explicit post-dry-run human decision surface without approving runtime candidate-set expansion.",
        "human_review_packet": {
            "ready": ready,
            "block_reasons": block_reasons.into_iter().collect::<Vec<_>>(),
            "decision": {
                "verdict": verdict,
                "next_gate": next_gate,
                "human_review_required": true,
                "candidate_expansion_authority_out_of_scope": true,
            },
            "metrics": {
                "evaluated_count": memory_biocortex_t6_u64_at(report, "/dry_run_report/metrics/evaluated_count"),
                "search_error_count": memory_biocortex_t6_u64_at(report, "/dry_run_report/metrics/search_error_count"),
                "baseline_hit_count": memory_biocortex_t6_u64_at(report, "/dry_run_report/metrics/baseline_hit_count"),
                "baseline_miss_count": memory_biocortex_t6_u64_at(report, "/dry_run_report/metrics/baseline_miss_count"),
                "graph_expansion_found_count": memory_biocortex_t6_u64_at(report, "/dry_run_report/metrics/graph_expansion_found_count"),
                "expanded_hit_count": memory_biocortex_t6_u64_at(report, "/dry_run_report/metrics/expanded_hit_count"),
                "candidate_expansion_added_hit_count": memory_biocortex_t6_u64_at(report, "/dry_run_report/metrics/candidate_expansion_added_hit_count"),
                "candidate_expansion_added_hit_rate": memory_biocortex_t6_f64_at(report, "/dry_run_report/metrics/candidate_expansion_added_hit_rate"),
                "graph_expansion_found_rate": memory_biocortex_t6_f64_at(report, "/dry_run_report/metrics/graph_expansion_found_rate"),
            },
            "sampling_contract": {
                "min_dry_run_cases": memory_biocortex_t6_u64_at(report, "/dry_run_report/sampling_contract/min_dry_run_cases"),
                "actual_evaluated_count": memory_biocortex_t6_u64_at(report, "/dry_run_report/sampling_contract/actual_evaluated_count"),
                "enough_cases": memory_biocortex_t6_bool_at(report, "/dry_run_report/sampling_contract/enough_cases"),
                "requires_less_handpicked_baseline_miss_corpus": memory_biocortex_t6_bool_at(report, "/dry_run_report/sampling_contract/requires_less_handpicked_baseline_miss_corpus"),
                "requires_negative_controls": memory_biocortex_t6_bool_at(report, "/dry_run_report/sampling_contract/requires_negative_controls"),
                "requires_trigger_projection_stratum": memory_biocortex_t6_bool_at(report, "/dry_run_report/sampling_contract/requires_trigger_projection_stratum"),
            },
            "evidence_strength": {
                "tier": memory_biocortex_t6_string_at(report, "/dry_run_report/evidence_strength/tier"),
                "caveats": memory_biocortex_t6_string_array_at(report, "/dry_run_report/evidence_strength/caveats"),
            },
        },
        "human_decision_options": [
            {
                "option": "request_more_redacted_dry_run_evidence",
                "effect": "No runtime change; produce a broader or better-stratified dry-run report."
            },
            {
                "option": "reject_candidate_expansion_path",
                "effect": "No runtime change; stop T6 candidate-expansion progression."
            },
            {
                "option": "approve_next_design_gate_only",
                "effect": "Allows design of a separate candidate-expansion experiment gate, but this packet still grants no runtime authority."
            }
        ],
        "review_contract": {
            "human_review_required": true,
            "candidate_expansion_experiment_approved": false,
            "may_run_candidate_expansion_dry_run_now": false,
            "may_expand_candidate_set_now": false,
            "changes_candidate_set_now": false,
            "runtime_influence_approved": false,
            "may_change_search_order_now": false,
            "requires_separate_owner_decision": true,
            "requires_separate_runtime_gate": true,
            "this_packet_approves_candidate_expansion": false,
        },
        "review_checklist": [
            "Confirm the source dry-run report is ready and aggregate-only.",
            "Inspect evaluated count, baseline-miss stratum, search-error count, and added-hit signal.",
            "Check negative-control and trigger-projection strata before interpreting lift.",
            "Decide whether more dry-run evidence is needed before any experiment design.",
            "Require a separate explicit owner decision and runtime gate before candidate-set expansion can exist."
        ],
        "decision": {
            "verdict": verdict,
            "next_gate": next_gate,
            "human_review_required": true,
            "candidate_expansion_authority_out_of_scope": true,
        },
        "links": {
            "reviewer": reviewer,
            "commit": commit,
            "forum_post_id": forum_post_id,
            "memory_key": memory_key,
        },
        "input_contract": {
            "dry_run_report_included": false,
            "dry_run_plan_included": false,
            "recall_expansion_summary_included": false,
            "case_rows_included": false,
            "raw_query_included": false,
            "raw_queries_included": false,
            "raw_keys_included": false,
            "content_included": false,
            "raw_error_included": false,
        },
        "non_goals": [
            "Does not run BioCortex.",
            "Does not call memory_search or memory_neighbors.",
            "Does not sample production memories or graph rows.",
            "Does not echo dry-run reports, dry-run plans, recall summaries, case rows, queries, keys, content, or raw errors.",
            "Does not write memory, graph edges, authorization records, or approval packets.",
            "Does not approve runtime influence, search-order changes, dry-run execution, or candidate-set expansion."
        ],
    })
}

pub struct MemoryBioCortexT6CandidateExpansionHumanReviewPacketTool;
impl MemoryBioCortexT6CandidateExpansionHumanReviewPacketTool {
    pub fn new() -> Self {
        Self
    }
}
#[async_trait]
impl McpTool for MemoryBioCortexT6CandidateExpansionHumanReviewPacketTool {
    fn name(&self) -> &'static str {
        "memory_biocortex_t6_candidate_expansion_human_review_packet"
    }

    fn schema(&self) -> ToolSchema {
        ToolSchema {
            name: self.name().into(),
            description: "Read-only T6 candidate-expansion human-review packet. \
                Consumes a safe candidate-expansion dry-run report and emits an \
                explicit post-dry-run human decision surface without echoing raw \
                inputs, calling search, writing state, approving runtime \
                influence, or expanding candidate sets."
                .into(),
            input_schema: json!({
                "type": "object",
                "required": ["candidate_expansion_dry_run_report"],
                "properties": {
                    "candidate_expansion_dry_run_report": {
                        "type": "object",
                        "description": "JSON object produced by memory_biocortex_t6_candidate_expansion_dry_run_report. Unknown/raw fields are ignored and never echoed."
                    },
                    "reviewer": {
                        "type": "string",
                        "description": "Optional reviewer identity or handle."
                    },
                    "commit": {
                        "type": "string",
                        "description": "Optional implementation commit under review."
                    },
                    "forum_post_id": {
                        "type": "string",
                        "description": "Optional forum post id linking this human-review packet."
                    },
                    "memory_key": {
                        "type": "string",
                        "description": "Optional memory key linking this human-review packet."
                    }
                }
            }),
        }
    }

    async fn execute(&self, args: Value, _ctx: &ToolContext) -> Result<ToolResult> {
        Ok(ToolResult::json_text(
            &memory_biocortex_t6_candidate_expansion_human_review_packet_payload(args),
        ))
    }
}

pub(super) fn memory_biocortex_t6_candidate_expansion_owner_decision_record_payload(args: Value) -> Value {
    let packet = args
        .get("human_review_packet")
        .unwrap_or(&Value::Null);
    let owner = args
        .get("owner")
        .and_then(Value::as_str)
        .map(|s| memory_biocortex_t6_clamp_label(s, 80))
        .filter(|s| !s.is_empty());
    let decision_source = args
        .get("decision_source")
        .and_then(Value::as_str)
        .map(|s| memory_biocortex_t6_clamp_label(s, 160))
        .filter(|s| !s.is_empty());
    let reviewer = args
        .get("reviewer")
        .and_then(Value::as_str)
        .map(|s| memory_biocortex_t6_clamp_label(s, 80))
        .filter(|s| !s.is_empty());
    let commit = args
        .get("commit")
        .and_then(Value::as_str)
        .map(|s| memory_biocortex_t6_clamp_label(s, 80))
        .filter(|s| !s.is_empty());
    let forum_post_id = args
        .get("forum_post_id")
        .and_then(Value::as_str)
        .map(|s| memory_biocortex_t6_clamp_label(s, 80))
        .filter(|s| !s.is_empty());
    let memory_key = args
        .get("memory_key")
        .and_then(Value::as_str)
        .map(|s| memory_biocortex_t6_clamp_label(s, 160))
        .filter(|s| !s.is_empty());
    let rationale = args
        .get("rationale")
        .and_then(Value::as_str)
        .map(|s| memory_biocortex_t6_clamp_label(s, 240))
        .filter(|s| !s.is_empty());
    let owner_decision = args
        .get("owner_decision")
        .and_then(Value::as_str)
        .map(str::trim)
        .filter(|s| !s.is_empty())
        .map(str::to_ascii_lowercase);
    let owner_decision_valid = matches!(
        owner_decision.as_deref(),
        Some("request_more_redacted_dry_run_evidence")
            | Some("reject_candidate_expansion_path")
            | Some("approve_next_design_gate_only")
    );

    let packet_schema_valid = memory_biocortex_t6_string_at(packet, "/schema")
        == Some(MEMORY_BIOCORTEX_T6_CANDIDATE_EXPANSION_HUMAN_REVIEW_PACKET_SCHEMA);
    let packet_ready =
        memory_biocortex_t6_bool_at(packet, "/human_review_packet/ready") == Some(true);
    let packet_safe_contract = memory_biocortex_t6_bool_at(packet, "/read_only") == Some(true)
        && memory_biocortex_t6_bool_at(
            packet,
            "/review_contract/candidate_expansion_experiment_approved",
        ) == Some(false)
        && memory_biocortex_t6_bool_at(
            packet,
            "/review_contract/may_run_candidate_expansion_dry_run_now",
        ) == Some(false)
        && memory_biocortex_t6_bool_at(
            packet,
            "/review_contract/may_expand_candidate_set_now",
        ) == Some(false)
        && memory_biocortex_t6_bool_at(packet, "/review_contract/changes_candidate_set_now")
            == Some(false)
        && memory_biocortex_t6_bool_at(packet, "/review_contract/runtime_influence_approved")
            == Some(false)
        && memory_biocortex_t6_bool_at(packet, "/review_contract/may_change_search_order_now")
            == Some(false)
        && memory_biocortex_t6_bool_at(
            packet,
            "/review_contract/this_packet_approves_candidate_expansion",
        ) == Some(false);
    let packet_claims_authority = memory_biocortex_t6_any_true(
        packet,
        &[
            "/review_contract/candidate_expansion_experiment_approved",
            "/review_contract/may_run_candidate_expansion_dry_run_now",
            "/review_contract/may_expand_candidate_set_now",
            "/review_contract/changes_candidate_set_now",
            "/review_contract/runtime_influence_approved",
            "/review_contract/may_change_search_order_now",
            "/review_contract/this_packet_approves_candidate_expansion",
        ],
    );
    let packet_flags_raw = memory_biocortex_t6_has_raw_payload_fields(packet)
        || packet.get("candidate_expansion_dry_run_report").is_some()
        || packet.get("dry_run_report").is_some()
        || packet.get("candidate_expansion_dry_run_plan").is_some()
        || packet.get("recall_expansion_summary").is_some()
        || packet.get("case_rows").is_some()
        || memory_biocortex_t6_any_true(
            packet,
            &[
                "/input_contract/dry_run_report_included",
                "/input_contract/dry_run_plan_included",
                "/input_contract/recall_expansion_summary_included",
                "/input_contract/case_rows_included",
                "/input_contract/raw_query_included",
                "/input_contract/raw_queries_included",
                "/input_contract/raw_keys_included",
                "/input_contract/content_included",
                "/input_contract/raw_error_included",
            ],
        );

    let mut block_reasons = BTreeSet::<String>::new();
    if !packet_schema_valid {
        memory_biocortex_t6_push_reason(
            &mut block_reasons,
            "source_human_review_packet_schema_invalid",
        );
    }
    if !packet_ready {
        memory_biocortex_t6_push_reason(&mut block_reasons, "source_human_review_packet_not_ready");
    }
    if !packet_safe_contract || packet_claims_authority {
        memory_biocortex_t6_push_reason(
            &mut block_reasons,
            "source_human_review_packet_claims_runtime_authority",
        );
    }
    if packet_flags_raw {
        memory_biocortex_t6_push_reason(
            &mut block_reasons,
            "source_human_review_packet_contains_raw",
        );
    }
    if owner.is_none() {
        memory_biocortex_t6_push_reason(&mut block_reasons, "missing_owner");
    }
    if decision_source.is_none() {
        memory_biocortex_t6_push_reason(&mut block_reasons, "missing_decision_source");
    }
    if !owner_decision_valid {
        memory_biocortex_t6_push_reason(&mut block_reasons, "invalid_owner_decision");
    }
    for reason in memory_biocortex_t6_string_array_at(packet, "/human_review_packet/block_reasons")
    {
        memory_biocortex_t6_push_reason(&mut block_reasons, &reason);
    }

    let ready = block_reasons.is_empty();
    let decision = owner_decision
        .as_deref()
        .filter(|_| owner_decision_valid)
        .unwrap_or("invalid_owner_decision");
    let next_design_gate_requested = ready && decision == "approve_next_design_gate_only";
    let (verdict, next_gate) = if !ready {
        (
            "blocked_collect_more_human_decision_evidence",
            "produce_ready_human_review_packet_and_explicit_owner_decision",
        )
    } else {
        match decision {
            "request_more_redacted_dry_run_evidence" => (
                "owner_requested_more_redacted_dry_run_evidence",
                "produce_broader_redacted_candidate_expansion_dry_run_report",
            ),
            "reject_candidate_expansion_path" => (
                "owner_rejected_candidate_expansion_path",
                "stop_candidate_expansion_path",
            ),
            "approve_next_design_gate_only" => (
                "owner_approved_next_design_gate_only",
                "design_candidate_expansion_runtime_gate_preflight",
            ),
            _ => (
                "blocked_collect_more_human_decision_evidence",
                "produce_ready_human_review_packet_and_explicit_owner_decision",
            ),
        }
    };

    json!({
        "schema": MEMORY_BIOCORTEX_T6_CANDIDATE_EXPANSION_OWNER_DECISION_RECORD_SCHEMA,
        "generated_at": unix_now_secs(),
        "read_only": true,
        "purpose": "T6 candidate-expansion owner-decision record: consume a safe human-review packet plus an explicit owner decision and record the next design-only gate without granting runtime candidate-set authority.",
        "owner_decision_record": {
            "ready": ready,
            "block_reasons": block_reasons.into_iter().collect::<Vec<_>>(),
            "owner_decision": decision,
            "owner": owner,
            "decision_source": decision_source,
            "rationale": rationale,
            "decision": {
                "verdict": verdict,
                "next_gate": next_gate,
                "next_design_gate_requested": next_design_gate_requested,
                "candidate_expansion_authority_out_of_scope": true,
                "runtime_authority_out_of_scope": true,
            },
            "source_evidence": {
                "metrics": {
                    "evaluated_count": memory_biocortex_t6_u64_at(packet, "/human_review_packet/metrics/evaluated_count"),
                    "search_error_count": memory_biocortex_t6_u64_at(packet, "/human_review_packet/metrics/search_error_count"),
                    "baseline_miss_count": memory_biocortex_t6_u64_at(packet, "/human_review_packet/metrics/baseline_miss_count"),
                    "candidate_expansion_added_hit_count": memory_biocortex_t6_u64_at(packet, "/human_review_packet/metrics/candidate_expansion_added_hit_count"),
                    "candidate_expansion_added_hit_rate": memory_biocortex_t6_f64_at(packet, "/human_review_packet/metrics/candidate_expansion_added_hit_rate"),
                    "graph_expansion_found_rate": memory_biocortex_t6_f64_at(packet, "/human_review_packet/metrics/graph_expansion_found_rate"),
                },
                "sampling_contract": {
                    "min_dry_run_cases": memory_biocortex_t6_u64_at(packet, "/human_review_packet/sampling_contract/min_dry_run_cases"),
                    "actual_evaluated_count": memory_biocortex_t6_u64_at(packet, "/human_review_packet/sampling_contract/actual_evaluated_count"),
                    "enough_cases": memory_biocortex_t6_bool_at(packet, "/human_review_packet/sampling_contract/enough_cases"),
                    "requires_less_handpicked_baseline_miss_corpus": memory_biocortex_t6_bool_at(packet, "/human_review_packet/sampling_contract/requires_less_handpicked_baseline_miss_corpus"),
                    "requires_negative_controls": memory_biocortex_t6_bool_at(packet, "/human_review_packet/sampling_contract/requires_negative_controls"),
                    "requires_trigger_projection_stratum": memory_biocortex_t6_bool_at(packet, "/human_review_packet/sampling_contract/requires_trigger_projection_stratum"),
                },
                "evidence_strength": {
                    "tier": memory_biocortex_t6_string_at(packet, "/human_review_packet/evidence_strength/tier"),
                    "caveats": memory_biocortex_t6_string_array_at(packet, "/human_review_packet/evidence_strength/caveats"),
                },
            },
        },
        "decision_contract": {
            "explicit_owner_decision_required": true,
            "owner_decision_recorded": ready,
            "next_design_gate_requested": next_design_gate_requested,
            "may_prepare_candidate_expansion_design_gate": next_design_gate_requested,
            "candidate_expansion_experiment_approved": false,
            "may_run_candidate_expansion_dry_run_now": false,
            "may_expand_candidate_set_now": false,
            "changes_candidate_set_now": false,
            "runtime_influence_approved": false,
            "may_change_search_order_now": false,
            "this_record_approves_runtime_candidate_expansion": false,
        },
        "review_checklist": [
            "Confirm the owner decision came from an explicit external source such as a forum post, issue, or signed review note.",
            "Confirm the source human-review packet is ready and aggregate-only.",
            "If approving next design gate, limit follow-up work to design/preflight artifacts only.",
            "Require a separate runtime gate before any dry-run execution or candidate-set expansion exists.",
            "Never treat this record as memory-write, search-order, or runtime candidate-set authorization."
        ],
        "decision": {
            "verdict": verdict,
            "next_gate": next_gate,
            "next_design_gate_requested": next_design_gate_requested,
            "candidate_expansion_authority_out_of_scope": true,
            "runtime_authority_out_of_scope": true,
        },
        "links": {
            "reviewer": reviewer,
            "commit": commit,
            "forum_post_id": forum_post_id,
            "memory_key": memory_key,
        },
        "input_contract": {
            "human_review_packet_included": false,
            "dry_run_report_included": false,
            "dry_run_plan_included": false,
            "recall_expansion_summary_included": false,
            "case_rows_included": false,
            "raw_query_included": false,
            "raw_queries_included": false,
            "raw_keys_included": false,
            "content_included": false,
            "raw_error_included": false,
        },
        "non_goals": [
            "Does not run BioCortex.",
            "Does not call memory_search or memory_neighbors.",
            "Does not sample production memories or graph rows.",
            "Does not echo human-review packets, dry-run reports, dry-run plans, recall summaries, case rows, queries, keys, content, or raw errors.",
            "Does not write memory, graph edges, authorization records, or approval packets.",
            "Does not approve runtime influence, search-order changes, dry-run execution, or candidate-set expansion."
        ],
    })
}

pub struct MemoryBioCortexT6CandidateExpansionOwnerDecisionRecordTool;
impl MemoryBioCortexT6CandidateExpansionOwnerDecisionRecordTool {
    pub fn new() -> Self {
        Self
    }
}
#[async_trait]
impl McpTool for MemoryBioCortexT6CandidateExpansionOwnerDecisionRecordTool {
    fn name(&self) -> &'static str {
        "memory_biocortex_t6_candidate_expansion_owner_decision_record"
    }

    fn schema(&self) -> ToolSchema {
        ToolSchema {
            name: self.name().into(),
            description: "Read-only T6 candidate-expansion owner-decision record. \
                Consumes a safe human-review packet plus an explicit owner \
                decision and records the next design-only gate without echoing \
                raw inputs, writing state, approving runtime influence, or \
                expanding candidate sets."
                .into(),
            input_schema: json!({
                "type": "object",
                "required": ["human_review_packet", "owner_decision", "owner", "decision_source"],
                "properties": {
                    "human_review_packet": {
                        "type": "object",
                        "description": "JSON object produced by memory_biocortex_t6_candidate_expansion_human_review_packet. Unknown/raw fields are ignored and never echoed."
                    },
                    "owner_decision": {
                        "type": "string",
                        "enum": [
                            "request_more_redacted_dry_run_evidence",
                            "reject_candidate_expansion_path",
                            "approve_next_design_gate_only"
                        ],
                        "description": "Explicit owner decision. The approve option only permits design/preflight follow-up; it grants no runtime authority."
                    },
                    "owner": {
                        "type": "string",
                        "description": "Owner/operator identity for the decision record."
                    },
                    "decision_source": {
                        "type": "string",
                        "description": "External source for the owner decision, such as a forum post id, issue URL, or signed review note id."
                    },
                    "rationale": {
                        "type": "string",
                        "description": "Optional short rationale copied from the external decision source."
                    },
                    "reviewer": {
                        "type": "string",
                        "description": "Optional reviewer identity or handle."
                    },
                    "commit": {
                        "type": "string",
                        "description": "Optional implementation commit under review."
                    },
                    "forum_post_id": {
                        "type": "string",
                        "description": "Optional forum post id linking this decision record."
                    },
                    "memory_key": {
                        "type": "string",
                        "description": "Optional memory key linking this decision record."
                    }
                }
            }),
        }
    }

    async fn execute(&self, args: Value, _ctx: &ToolContext) -> Result<ToolResult> {
        Ok(ToolResult::json_text(
            &memory_biocortex_t6_candidate_expansion_owner_decision_record_payload(args),
        ))
    }
}

pub(super) fn memory_biocortex_t6_candidate_expansion_runtime_gate_preflight_payload(args: Value) -> Value {
    let record = args
        .get("owner_decision_record")
        .unwrap_or(&Value::Null);
    let reviewer = args
        .get("reviewer")
        .and_then(Value::as_str)
        .map(|s| memory_biocortex_t6_clamp_label(s, 80))
        .filter(|s| !s.is_empty());
    let commit = args
        .get("commit")
        .and_then(Value::as_str)
        .map(|s| memory_biocortex_t6_clamp_label(s, 80))
        .filter(|s| !s.is_empty());
    let forum_post_id = args
        .get("forum_post_id")
        .and_then(Value::as_str)
        .map(|s| memory_biocortex_t6_clamp_label(s, 80))
        .filter(|s| !s.is_empty());
    let memory_key = args
        .get("memory_key")
        .and_then(Value::as_str)
        .map(|s| memory_biocortex_t6_clamp_label(s, 160))
        .filter(|s| !s.is_empty());

    let record_schema_valid = memory_biocortex_t6_string_at(record, "/schema")
        == Some(MEMORY_BIOCORTEX_T6_CANDIDATE_EXPANSION_OWNER_DECISION_RECORD_SCHEMA);
    let record_ready =
        memory_biocortex_t6_bool_at(record, "/owner_decision_record/ready") == Some(true);
    let owner_decision = memory_biocortex_t6_string_at(record, "/owner_decision_record/owner_decision")
        .unwrap_or("missing_owner_decision");
    let next_design_gate_requested =
        memory_biocortex_t6_bool_at(record, "/decision_contract/next_design_gate_requested")
            == Some(true)
            && memory_biocortex_t6_bool_at(
                record,
                "/decision_contract/may_prepare_candidate_expansion_design_gate",
            ) == Some(true);
    let record_safe_contract = memory_biocortex_t6_bool_at(record, "/read_only") == Some(true)
        && memory_biocortex_t6_bool_at(
            record,
            "/decision_contract/candidate_expansion_experiment_approved",
        ) == Some(false)
        && memory_biocortex_t6_bool_at(
            record,
            "/decision_contract/may_run_candidate_expansion_dry_run_now",
        ) == Some(false)
        && memory_biocortex_t6_bool_at(
            record,
            "/decision_contract/may_expand_candidate_set_now",
        ) == Some(false)
        && memory_biocortex_t6_bool_at(record, "/decision_contract/changes_candidate_set_now")
            == Some(false)
        && memory_biocortex_t6_bool_at(record, "/decision_contract/runtime_influence_approved")
            == Some(false)
        && memory_biocortex_t6_bool_at(record, "/decision_contract/may_change_search_order_now")
            == Some(false)
        && memory_biocortex_t6_bool_at(
            record,
            "/decision_contract/this_record_approves_runtime_candidate_expansion",
        ) == Some(false);
    let record_claims_runtime_authority = memory_biocortex_t6_any_true(
        record,
        &[
            "/decision_contract/candidate_expansion_experiment_approved",
            "/decision_contract/may_run_candidate_expansion_dry_run_now",
            "/decision_contract/may_expand_candidate_set_now",
            "/decision_contract/changes_candidate_set_now",
            "/decision_contract/runtime_influence_approved",
            "/decision_contract/may_change_search_order_now",
            "/decision_contract/this_record_approves_runtime_candidate_expansion",
        ],
    );
    let record_flags_raw = memory_biocortex_t6_has_raw_payload_fields(record)
        || record.get("human_review_packet").is_some()
        || record.get("candidate_expansion_dry_run_report").is_some()
        || record.get("dry_run_report").is_some()
        || record.get("candidate_expansion_dry_run_plan").is_some()
        || record.get("recall_expansion_summary").is_some()
        || record.get("case_rows").is_some()
        || memory_biocortex_t6_any_true(
            record,
            &[
                "/input_contract/human_review_packet_included",
                "/input_contract/dry_run_report_included",
                "/input_contract/dry_run_plan_included",
                "/input_contract/recall_expansion_summary_included",
                "/input_contract/case_rows_included",
                "/input_contract/raw_query_included",
                "/input_contract/raw_queries_included",
                "/input_contract/raw_keys_included",
                "/input_contract/content_included",
                "/input_contract/raw_error_included",
            ],
        );

    let mut block_reasons = BTreeSet::<String>::new();
    if !record_schema_valid {
        memory_biocortex_t6_push_reason(
            &mut block_reasons,
            "source_owner_decision_record_schema_invalid",
        );
    }
    if !record_ready {
        memory_biocortex_t6_push_reason(
            &mut block_reasons,
            "source_owner_decision_record_not_ready",
        );
    }
    if !record_safe_contract || record_claims_runtime_authority {
        memory_biocortex_t6_push_reason(
            &mut block_reasons,
            "source_owner_decision_record_claims_runtime_authority",
        );
    }
    if record_flags_raw {
        memory_biocortex_t6_push_reason(
            &mut block_reasons,
            "source_owner_decision_record_contains_raw",
        );
    }
    if owner_decision != "approve_next_design_gate_only" || !next_design_gate_requested {
        memory_biocortex_t6_push_reason(
            &mut block_reasons,
            "source_owner_decision_not_approved_for_design_gate",
        );
    }
    for reason in memory_biocortex_t6_string_array_at(record, "/owner_decision_record/block_reasons")
    {
        memory_biocortex_t6_push_reason(&mut block_reasons, &reason);
    }

    let ready = block_reasons.is_empty();
    let verdict = if ready {
        "runtime_gate_preflight_ready_for_design_review"
    } else {
        "blocked_before_runtime_gate_preflight"
    };
    let next_gate = if ready {
        "design_runtime_gate_contract_before_any_execution_path"
    } else {
        "collect_explicit_owner_design_gate_decision"
    };

    json!({
        "schema": MEMORY_BIOCORTEX_T6_CANDIDATE_EXPANSION_RUNTIME_GATE_PREFLIGHT_SCHEMA,
        "generated_at": unix_now_secs(),
        "read_only": true,
        "purpose": "T6 candidate-expansion runtime-gate preflight: consume an owner-decision record and emit design requirements for a future separate runtime gate without approving or creating runtime candidate-set expansion.",
        "runtime_gate_preflight": {
            "ready": ready,
            "block_reasons": block_reasons.into_iter().collect::<Vec<_>>(),
            "decision": {
                "verdict": verdict,
                "next_gate": next_gate,
                "design_only": true,
                "runtime_authority_out_of_scope": true,
                "candidate_expansion_authority_out_of_scope": true,
            },
            "source_decision": {
                "owner_decision": owner_decision,
                "owner": memory_biocortex_t6_string_at(record, "/owner_decision_record/owner"),
                "decision_source": memory_biocortex_t6_string_at(record, "/owner_decision_record/decision_source"),
                "next_design_gate_requested": next_design_gate_requested,
            },
            "source_evidence": {
                "metrics": {
                    "evaluated_count": memory_biocortex_t6_u64_at(record, "/owner_decision_record/source_evidence/metrics/evaluated_count"),
                    "search_error_count": memory_biocortex_t6_u64_at(record, "/owner_decision_record/source_evidence/metrics/search_error_count"),
                    "baseline_miss_count": memory_biocortex_t6_u64_at(record, "/owner_decision_record/source_evidence/metrics/baseline_miss_count"),
                    "candidate_expansion_added_hit_count": memory_biocortex_t6_u64_at(record, "/owner_decision_record/source_evidence/metrics/candidate_expansion_added_hit_count"),
                    "candidate_expansion_added_hit_rate": memory_biocortex_t6_f64_at(record, "/owner_decision_record/source_evidence/metrics/candidate_expansion_added_hit_rate"),
                    "graph_expansion_found_rate": memory_biocortex_t6_f64_at(record, "/owner_decision_record/source_evidence/metrics/graph_expansion_found_rate"),
                },
                "evidence_strength": {
                    "tier": memory_biocortex_t6_string_at(record, "/owner_decision_record/source_evidence/evidence_strength/tier"),
                    "caveats": memory_biocortex_t6_string_array_at(record, "/owner_decision_record/source_evidence/evidence_strength/caveats"),
                },
            },
        },
        "runtime_gate_design_requirements": {
            "requires_separate_runtime_gate_tool": true,
            "requires_separate_owner_runtime_approval": true,
            "requires_feature_flag_default_off": true,
            "requires_shadow_mode_first": true,
            "requires_deterministic_replay_fixture": true,
            "requires_bounded_candidate_delta": true,
            "requires_negative_controls": true,
            "requires_rollback_plan": true,
            "requires_telemetry_fields": [
                "baseline_candidate_count",
                "expanded_candidate_count",
                "added_candidate_count",
                "selected_candidate_source",
                "recall_lift_class",
                "negative_control_regression_count"
            ],
        },
        "preflight_contract": {
            "may_prepare_runtime_gate_design_artifact": ready,
            "may_implement_runtime_gate_code_now": false,
            "candidate_expansion_experiment_approved": false,
            "may_run_candidate_expansion_dry_run_now": false,
            "may_expand_candidate_set_now": false,
            "changes_candidate_set_now": false,
            "runtime_influence_approved": false,
            "may_change_search_order_now": false,
            "this_preflight_approves_runtime_candidate_expansion": false,
        },
        "review_checklist": [
            "Confirm this preflight came from an owner-decision record that approved next design gate only.",
            "Design a separate runtime gate tool or config path; do not add a live candidate-expansion path in this preflight.",
            "Keep the runtime gate feature-flagged off by default and shadow-only before any owner runtime approval.",
            "Specify deterministic replay, negative controls, telemetry, and rollback before implementing runtime code.",
            "Require a separate owner runtime approval after the design artifact and before any execution path can run."
        ],
        "decision": {
            "verdict": verdict,
            "next_gate": next_gate,
            "design_only": true,
            "runtime_authority_out_of_scope": true,
            "candidate_expansion_authority_out_of_scope": true,
        },
        "links": {
            "reviewer": reviewer,
            "commit": commit,
            "forum_post_id": forum_post_id,
            "memory_key": memory_key,
        },
        "input_contract": {
            "owner_decision_record_included": false,
            "human_review_packet_included": false,
            "dry_run_report_included": false,
            "dry_run_plan_included": false,
            "recall_expansion_summary_included": false,
            "case_rows_included": false,
            "raw_query_included": false,
            "raw_queries_included": false,
            "raw_keys_included": false,
            "content_included": false,
            "raw_error_included": false,
        },
        "non_goals": [
            "Does not run BioCortex.",
            "Does not call memory_search or memory_neighbors.",
            "Does not sample production memories or graph rows.",
            "Does not echo owner-decision records, human-review packets, dry-run reports, dry-run plans, recall summaries, case rows, queries, keys, content, or raw errors.",
            "Does not write memory, graph edges, authorization records, or approval packets.",
            "Does not approve runtime influence, search-order changes, dry-run execution, or candidate-set expansion."
        ],
    })
}

pub struct MemoryBioCortexT6CandidateExpansionRuntimeGatePreflightTool;
impl MemoryBioCortexT6CandidateExpansionRuntimeGatePreflightTool {
    pub fn new() -> Self {
        Self
    }
}
#[async_trait]
impl McpTool for MemoryBioCortexT6CandidateExpansionRuntimeGatePreflightTool {
    fn name(&self) -> &'static str {
        "memory_biocortex_t6_candidate_expansion_runtime_gate_preflight"
    }

    fn schema(&self) -> ToolSchema {
        ToolSchema {
            name: self.name().into(),
            description: "Read-only T6 candidate-expansion runtime-gate preflight. \
                Consumes a safe owner-decision record and emits design-only \
                requirements for a future separate runtime gate without writing \
                state, approving runtime influence, or expanding candidate sets."
                .into(),
            input_schema: json!({
                "type": "object",
                "required": ["owner_decision_record"],
                "properties": {
                    "owner_decision_record": {
                        "type": "object",
                        "description": "JSON object produced by memory_biocortex_t6_candidate_expansion_owner_decision_record. Unknown/raw fields are ignored and never echoed."
                    },
                    "reviewer": {
                        "type": "string",
                        "description": "Optional reviewer identity or handle."
                    },
                    "commit": {
                        "type": "string",
                        "description": "Optional implementation commit under review."
                    },
                    "forum_post_id": {
                        "type": "string",
                        "description": "Optional forum post id linking this preflight."
                    },
                    "memory_key": {
                        "type": "string",
                        "description": "Optional memory key linking this preflight."
                    }
                }
            }),
        }
    }

    async fn execute(&self, args: Value, _ctx: &ToolContext) -> Result<ToolResult> {
        Ok(ToolResult::json_text(
            &memory_biocortex_t6_candidate_expansion_runtime_gate_preflight_payload(args),
        ))
    }
}

pub(super) fn memory_biocortex_t6_candidate_expansion_runtime_gate_design_artifact_payload(
    args: Value,
) -> Value {
    let preflight = args
        .get("runtime_gate_preflight")
        .unwrap_or(&Value::Null);
    let reviewer = args
        .get("reviewer")
        .and_then(Value::as_str)
        .map(|s| memory_biocortex_t6_clamp_label(s, 80))
        .filter(|s| !s.is_empty());
    let commit = args
        .get("commit")
        .and_then(Value::as_str)
        .map(|s| memory_biocortex_t6_clamp_label(s, 80))
        .filter(|s| !s.is_empty());
    let forum_post_id = args
        .get("forum_post_id")
        .and_then(Value::as_str)
        .map(|s| memory_biocortex_t6_clamp_label(s, 80))
        .filter(|s| !s.is_empty());
    let memory_key = args
        .get("memory_key")
        .and_then(Value::as_str)
        .map(|s| memory_biocortex_t6_clamp_label(s, 160))
        .filter(|s| !s.is_empty());

    let preflight_schema_valid = memory_biocortex_t6_string_at(preflight, "/schema")
        == Some(MEMORY_BIOCORTEX_T6_CANDIDATE_EXPANSION_RUNTIME_GATE_PREFLIGHT_SCHEMA);
    let preflight_ready =
        memory_biocortex_t6_bool_at(preflight, "/runtime_gate_preflight/ready") == Some(true);
    let preflight_safe_contract = memory_biocortex_t6_bool_at(preflight, "/read_only")
        == Some(true)
        && memory_biocortex_t6_bool_at(
            preflight,
            "/preflight_contract/may_prepare_runtime_gate_design_artifact",
        ) == Some(true)
        && memory_biocortex_t6_bool_at(
            preflight,
            "/preflight_contract/may_implement_runtime_gate_code_now",
        ) == Some(false)
        && memory_biocortex_t6_bool_at(
            preflight,
            "/preflight_contract/candidate_expansion_experiment_approved",
        ) == Some(false)
        && memory_biocortex_t6_bool_at(
            preflight,
            "/preflight_contract/may_run_candidate_expansion_dry_run_now",
        ) == Some(false)
        && memory_biocortex_t6_bool_at(
            preflight,
            "/preflight_contract/may_expand_candidate_set_now",
        ) == Some(false)
        && memory_biocortex_t6_bool_at(preflight, "/preflight_contract/changes_candidate_set_now")
            == Some(false)
        && memory_biocortex_t6_bool_at(
            preflight,
            "/preflight_contract/runtime_influence_approved",
        ) == Some(false)
        && memory_biocortex_t6_bool_at(
            preflight,
            "/preflight_contract/may_change_search_order_now",
        ) == Some(false)
        && memory_biocortex_t6_bool_at(
            preflight,
            "/preflight_contract/this_preflight_approves_runtime_candidate_expansion",
        ) == Some(false);
    let preflight_claims_runtime_authority = memory_biocortex_t6_any_true(
        preflight,
        &[
            "/preflight_contract/may_implement_runtime_gate_code_now",
            "/preflight_contract/candidate_expansion_experiment_approved",
            "/preflight_contract/may_run_candidate_expansion_dry_run_now",
            "/preflight_contract/may_expand_candidate_set_now",
            "/preflight_contract/changes_candidate_set_now",
            "/preflight_contract/runtime_influence_approved",
            "/preflight_contract/may_change_search_order_now",
            "/preflight_contract/this_preflight_approves_runtime_candidate_expansion",
        ],
    );
    let preflight_requirements_ok = [
        "/runtime_gate_design_requirements/requires_separate_runtime_gate_tool",
        "/runtime_gate_design_requirements/requires_separate_owner_runtime_approval",
        "/runtime_gate_design_requirements/requires_feature_flag_default_off",
        "/runtime_gate_design_requirements/requires_shadow_mode_first",
        "/runtime_gate_design_requirements/requires_deterministic_replay_fixture",
        "/runtime_gate_design_requirements/requires_bounded_candidate_delta",
        "/runtime_gate_design_requirements/requires_negative_controls",
        "/runtime_gate_design_requirements/requires_rollback_plan",
    ]
    .iter()
    .all(|path| memory_biocortex_t6_bool_at(preflight, path) == Some(true))
        && !memory_biocortex_t6_string_array_at(
            preflight,
            "/runtime_gate_design_requirements/requires_telemetry_fields",
        )
        .is_empty();
    let preflight_flags_raw = memory_biocortex_t6_has_raw_payload_fields(preflight)
        || preflight.get("owner_decision_record").is_some()
        || preflight.get("human_review_packet").is_some()
        || preflight.get("candidate_expansion_dry_run_report").is_some()
        || preflight.get("dry_run_report").is_some()
        || preflight.get("candidate_expansion_dry_run_plan").is_some()
        || preflight.get("recall_expansion_summary").is_some()
        || preflight.get("case_rows").is_some()
        || memory_biocortex_t6_any_true(
            preflight,
            &[
                "/input_contract/owner_decision_record_included",
                "/input_contract/human_review_packet_included",
                "/input_contract/dry_run_report_included",
                "/input_contract/dry_run_plan_included",
                "/input_contract/recall_expansion_summary_included",
                "/input_contract/case_rows_included",
                "/input_contract/raw_query_included",
                "/input_contract/raw_queries_included",
                "/input_contract/raw_keys_included",
                "/input_contract/content_included",
                "/input_contract/raw_error_included",
            ],
        );

    let mut block_reasons = BTreeSet::<String>::new();
    if !preflight_schema_valid {
        memory_biocortex_t6_push_reason(
            &mut block_reasons,
            "source_runtime_gate_preflight_schema_invalid",
        );
    }
    if !preflight_ready {
        memory_biocortex_t6_push_reason(
            &mut block_reasons,
            "source_runtime_gate_preflight_not_ready",
        );
    }
    if !preflight_safe_contract || preflight_claims_runtime_authority {
        memory_biocortex_t6_push_reason(
            &mut block_reasons,
            "source_runtime_gate_preflight_claims_runtime_authority",
        );
    }
    if !preflight_requirements_ok {
        memory_biocortex_t6_push_reason(
            &mut block_reasons,
            "source_runtime_gate_preflight_requirements_incomplete",
        );
    }
    if preflight_flags_raw {
        memory_biocortex_t6_push_reason(
            &mut block_reasons,
            "source_runtime_gate_preflight_contains_raw",
        );
    }
    for reason in
        memory_biocortex_t6_string_array_at(preflight, "/runtime_gate_preflight/block_reasons")
    {
        memory_biocortex_t6_push_reason(&mut block_reasons, &reason);
    }

    let ready = block_reasons.is_empty();
    let verdict = if ready {
        "runtime_gate_design_artifact_ready_for_owner_review"
    } else {
        "blocked_before_runtime_gate_design_artifact"
    };
    let next_gate = if ready {
        "author_review_runtime_gate_design_artifact_before_runtime_code"
    } else {
        "repair_runtime_gate_preflight_before_design_artifact"
    };
    let telemetry_fields = memory_biocortex_t6_string_array_at(
        preflight,
        "/runtime_gate_design_requirements/requires_telemetry_fields",
    );

    json!({
        "schema": MEMORY_BIOCORTEX_T6_CANDIDATE_EXPANSION_RUNTIME_GATE_DESIGN_ARTIFACT_SCHEMA,
        "generated_at": unix_now_secs(),
        "read_only": true,
        "purpose": "T6 candidate-expansion runtime-gate design artifact: consume a safe runtime-gate preflight and emit an owner-reviewable design checklist for a future separate runtime gate without implementing code, running dry-runs, or approving candidate-set expansion.",
        "runtime_gate_design_artifact": {
            "ready": ready,
            "block_reasons": block_reasons.into_iter().collect::<Vec<_>>(),
            "decision": {
                "verdict": verdict,
                "next_gate": next_gate,
                "design_only": true,
                "runtime_code_out_of_scope": true,
                "runtime_authority_out_of_scope": true,
                "candidate_expansion_authority_out_of_scope": true,
            },
            "source_decision": {
                "owner_decision": memory_biocortex_t6_string_at(preflight, "/runtime_gate_preflight/source_decision/owner_decision"),
                "owner": memory_biocortex_t6_string_at(preflight, "/runtime_gate_preflight/source_decision/owner"),
                "decision_source": memory_biocortex_t6_string_at(preflight, "/runtime_gate_preflight/source_decision/decision_source"),
                "next_design_gate_requested": memory_biocortex_t6_bool_at(preflight, "/runtime_gate_preflight/source_decision/next_design_gate_requested"),
            },
            "source_evidence": {
                "metrics": {
                    "evaluated_count": memory_biocortex_t6_u64_at(preflight, "/runtime_gate_preflight/source_evidence/metrics/evaluated_count"),
                    "search_error_count": memory_biocortex_t6_u64_at(preflight, "/runtime_gate_preflight/source_evidence/metrics/search_error_count"),
                    "baseline_miss_count": memory_biocortex_t6_u64_at(preflight, "/runtime_gate_preflight/source_evidence/metrics/baseline_miss_count"),
                    "candidate_expansion_added_hit_count": memory_biocortex_t6_u64_at(preflight, "/runtime_gate_preflight/source_evidence/metrics/candidate_expansion_added_hit_count"),
                    "candidate_expansion_added_hit_rate": memory_biocortex_t6_f64_at(preflight, "/runtime_gate_preflight/source_evidence/metrics/candidate_expansion_added_hit_rate"),
                    "graph_expansion_found_rate": memory_biocortex_t6_f64_at(preflight, "/runtime_gate_preflight/source_evidence/metrics/graph_expansion_found_rate"),
                },
                "evidence_strength": {
                    "tier": memory_biocortex_t6_string_at(preflight, "/runtime_gate_preflight/source_evidence/evidence_strength/tier"),
                    "caveats": memory_biocortex_t6_string_array_at(preflight, "/runtime_gate_preflight/source_evidence/evidence_strength/caveats"),
                },
            },
            "requirements": {
                "separate_runtime_gate_tool": true,
                "separate_owner_runtime_approval": true,
                "feature_flag_default_off": true,
                "shadow_mode_first": true,
                "deterministic_replay_fixture": true,
                "bounded_candidate_delta": true,
                "negative_controls": true,
                "rollback_plan": true,
                "telemetry_fields": telemetry_fields,
            },
            "shadow_mode_contract": {
                "default_enabled": false,
                "can_influence_candidate_set": false,
                "can_change_search_order": false,
                "requires_deterministic_replay_before_runtime": true,
                "requires_negative_control_pass_before_runtime": true,
            },
            "rollback_contract": {
                "feature_flag_must_disable_all_runtime_influence": true,
                "must_preserve_baseline_candidate_path": true,
                "must_log_added_candidate_count": true,
                "must_log_selected_candidate_source": true,
            },
        },
        "design_contract": {
            "may_prepare_runtime_gate_design_artifact": ready,
            "may_implement_runtime_gate_code_now": false,
            "candidate_expansion_experiment_approved": false,
            "may_run_candidate_expansion_dry_run_now": false,
            "may_expand_candidate_set_now": false,
            "changes_candidate_set_now": false,
            "runtime_influence_approved": false,
            "may_change_search_order_now": false,
            "this_artifact_approves_runtime_candidate_expansion": false,
            "requires_separate_owner_runtime_approval": true,
            "requires_separate_runtime_gate_tool": true,
        },
        "review_checklist": [
            "Confirm this artifact came from a ready runtime-gate preflight with no raw source packets.",
            "Specify the separate runtime gate entry point and keep the feature flag default off.",
            "Define deterministic replay fixtures before adding any runtime execution path.",
            "Define negative controls and failure thresholds before enabling shadow-mode comparison.",
            "Define telemetry for baseline and expanded candidate counts, added candidates, selected source, lift class, and negative-control regressions.",
            "Define rollback behavior that restores the baseline candidate path with no search-order influence.",
            "Require a separate owner runtime approval after this artifact and before any implementation can influence candidate expansion."
        ],
        "decision": {
            "verdict": verdict,
            "next_gate": next_gate,
            "design_only": true,
            "runtime_code_out_of_scope": true,
            "runtime_authority_out_of_scope": true,
            "candidate_expansion_authority_out_of_scope": true,
        },
        "links": {
            "reviewer": reviewer,
            "commit": commit,
            "forum_post_id": forum_post_id,
            "memory_key": memory_key,
        },
        "input_contract": {
            "runtime_gate_preflight_included": false,
            "owner_decision_record_included": false,
            "human_review_packet_included": false,
            "dry_run_report_included": false,
            "dry_run_plan_included": false,
            "recall_expansion_summary_included": false,
            "case_rows_included": false,
            "raw_query_included": false,
            "raw_queries_included": false,
            "raw_keys_included": false,
            "content_included": false,
            "raw_error_included": false,
        },
        "non_goals": [
            "Does not implement a runtime gate.",
            "Does not run BioCortex.",
            "Does not call memory_search or memory_neighbors.",
            "Does not sample production memories or graph rows.",
            "Does not echo runtime-gate preflights, owner-decision records, human-review packets, dry-run reports, dry-run plans, recall summaries, case rows, queries, keys, content, or raw errors.",
            "Does not write memory, graph edges, authorization records, or approval packets.",
            "Does not approve runtime influence, search-order changes, dry-run execution, or candidate-set expansion."
        ],
    })
}

pub struct MemoryBioCortexT6CandidateExpansionRuntimeGateDesignArtifactTool;
impl MemoryBioCortexT6CandidateExpansionRuntimeGateDesignArtifactTool {
    pub fn new() -> Self {
        Self
    }
}
#[async_trait]
impl McpTool for MemoryBioCortexT6CandidateExpansionRuntimeGateDesignArtifactTool {
    fn name(&self) -> &'static str {
        "memory_biocortex_t6_candidate_expansion_runtime_gate_design_artifact"
    }

    fn schema(&self) -> ToolSchema {
        ToolSchema {
            name: self.name().into(),
            description: "Read-only T6 candidate-expansion runtime-gate design artifact. \
                Consumes a safe runtime-gate preflight and emits an owner-reviewable \
                design checklist for a future separate runtime gate without writing \
                state, implementing runtime code, approving runtime influence, or \
                expanding candidate sets."
                .into(),
            input_schema: json!({
                "type": "object",
                "required": ["runtime_gate_preflight"],
                "properties": {
                    "runtime_gate_preflight": {
                        "type": "object",
                        "description": "JSON object produced by memory_biocortex_t6_candidate_expansion_runtime_gate_preflight. Unknown/raw fields are ignored and never echoed."
                    },
                    "reviewer": {
                        "type": "string",
                        "description": "Optional reviewer identity or handle."
                    },
                    "commit": {
                        "type": "string",
                        "description": "Optional implementation commit under review."
                    },
                    "forum_post_id": {
                        "type": "string",
                        "description": "Optional forum post id linking this design artifact."
                    },
                    "memory_key": {
                        "type": "string",
                        "description": "Optional memory key linking this design artifact."
                    }
                }
            }),
        }
    }

    async fn execute(&self, args: Value, _ctx: &ToolContext) -> Result<ToolResult> {
        Ok(ToolResult::json_text(
            &memory_biocortex_t6_candidate_expansion_runtime_gate_design_artifact_payload(args),
        ))
    }
}

pub(super) fn memory_biocortex_t6_candidate_expansion_runtime_gate_owner_review_record_payload(
    args: Value,
) -> Value {
    let artifact = args
        .get("runtime_gate_design_artifact")
        .unwrap_or(&Value::Null);
    let owner = args
        .get("owner")
        .and_then(Value::as_str)
        .map(|s| memory_biocortex_t6_clamp_label(s, 80))
        .filter(|s| !s.is_empty());
    let decision_source = args
        .get("decision_source")
        .and_then(Value::as_str)
        .map(|s| memory_biocortex_t6_clamp_label(s, 160))
        .filter(|s| !s.is_empty());
    let owner_decision = args
        .get("owner_decision")
        .and_then(Value::as_str)
        .map(str::trim)
        .filter(|s| !s.is_empty())
        .unwrap_or("missing_owner_decision");
    let reviewer = args
        .get("reviewer")
        .and_then(Value::as_str)
        .map(|s| memory_biocortex_t6_clamp_label(s, 80))
        .filter(|s| !s.is_empty());
    let commit = args
        .get("commit")
        .and_then(Value::as_str)
        .map(|s| memory_biocortex_t6_clamp_label(s, 80))
        .filter(|s| !s.is_empty());
    let forum_post_id = args
        .get("forum_post_id")
        .and_then(Value::as_str)
        .map(|s| memory_biocortex_t6_clamp_label(s, 80))
        .filter(|s| !s.is_empty());
    let memory_key = args
        .get("memory_key")
        .and_then(Value::as_str)
        .map(|s| memory_biocortex_t6_clamp_label(s, 160))
        .filter(|s| !s.is_empty());

    let artifact_schema_valid = memory_biocortex_t6_string_at(artifact, "/schema")
        == Some(MEMORY_BIOCORTEX_T6_CANDIDATE_EXPANSION_RUNTIME_GATE_DESIGN_ARTIFACT_SCHEMA);
    let artifact_ready =
        memory_biocortex_t6_bool_at(artifact, "/runtime_gate_design_artifact/ready") == Some(true);
    let artifact_safe_contract = memory_biocortex_t6_bool_at(artifact, "/read_only")
        == Some(true)
        && memory_biocortex_t6_bool_at(
            artifact,
            "/design_contract/may_prepare_runtime_gate_design_artifact",
        ) == Some(true)
        && memory_biocortex_t6_bool_at(
            artifact,
            "/design_contract/may_implement_runtime_gate_code_now",
        ) == Some(false)
        && memory_biocortex_t6_bool_at(
            artifact,
            "/design_contract/candidate_expansion_experiment_approved",
        ) == Some(false)
        && memory_biocortex_t6_bool_at(
            artifact,
            "/design_contract/may_run_candidate_expansion_dry_run_now",
        ) == Some(false)
        && memory_biocortex_t6_bool_at(
            artifact,
            "/design_contract/may_expand_candidate_set_now",
        ) == Some(false)
        && memory_biocortex_t6_bool_at(artifact, "/design_contract/changes_candidate_set_now")
            == Some(false)
        && memory_biocortex_t6_bool_at(artifact, "/design_contract/runtime_influence_approved")
            == Some(false)
        && memory_biocortex_t6_bool_at(artifact, "/design_contract/may_change_search_order_now")
            == Some(false)
        && memory_biocortex_t6_bool_at(
            artifact,
            "/design_contract/this_artifact_approves_runtime_candidate_expansion",
        ) == Some(false)
        && memory_biocortex_t6_bool_at(
            artifact,
            "/design_contract/requires_separate_owner_runtime_approval",
        ) == Some(true)
        && memory_biocortex_t6_bool_at(
            artifact,
            "/design_contract/requires_separate_runtime_gate_tool",
        ) == Some(true);
    let artifact_claims_runtime_authority = memory_biocortex_t6_any_true(
        artifact,
        &[
            "/design_contract/may_implement_runtime_gate_code_now",
            "/design_contract/candidate_expansion_experiment_approved",
            "/design_contract/may_run_candidate_expansion_dry_run_now",
            "/design_contract/may_expand_candidate_set_now",
            "/design_contract/changes_candidate_set_now",
            "/design_contract/runtime_influence_approved",
            "/design_contract/may_change_search_order_now",
            "/design_contract/this_artifact_approves_runtime_candidate_expansion",
        ],
    );
    let artifact_requirements_ok = [
        "/runtime_gate_design_artifact/requirements/separate_runtime_gate_tool",
        "/runtime_gate_design_artifact/requirements/separate_owner_runtime_approval",
        "/runtime_gate_design_artifact/requirements/feature_flag_default_off",
        "/runtime_gate_design_artifact/requirements/shadow_mode_first",
        "/runtime_gate_design_artifact/requirements/deterministic_replay_fixture",
        "/runtime_gate_design_artifact/requirements/bounded_candidate_delta",
        "/runtime_gate_design_artifact/requirements/negative_controls",
        "/runtime_gate_design_artifact/requirements/rollback_plan",
    ]
    .iter()
    .all(|path| memory_biocortex_t6_bool_at(artifact, path) == Some(true))
        && !memory_biocortex_t6_string_array_at(
            artifact,
            "/runtime_gate_design_artifact/requirements/telemetry_fields",
        )
        .is_empty();
    let artifact_flags_raw = memory_biocortex_t6_has_raw_payload_fields(artifact)
        || artifact.get("runtime_gate_preflight").is_some()
        || artifact.get("owner_decision_record").is_some()
        || artifact.get("human_review_packet").is_some()
        || artifact.get("candidate_expansion_dry_run_report").is_some()
        || artifact.get("dry_run_report").is_some()
        || artifact.get("candidate_expansion_dry_run_plan").is_some()
        || artifact.get("recall_expansion_summary").is_some()
        || artifact.get("case_rows").is_some()
        || memory_biocortex_t6_any_true(
            artifact,
            &[
                "/input_contract/runtime_gate_preflight_included",
                "/input_contract/owner_decision_record_included",
                "/input_contract/human_review_packet_included",
                "/input_contract/dry_run_report_included",
                "/input_contract/dry_run_plan_included",
                "/input_contract/recall_expansion_summary_included",
                "/input_contract/case_rows_included",
                "/input_contract/raw_query_included",
                "/input_contract/raw_queries_included",
                "/input_contract/raw_keys_included",
                "/input_contract/content_included",
                "/input_contract/raw_error_included",
            ],
        );
    let owner_decision_valid = matches!(
        owner_decision,
        "approve_runtime_gate_implementation_plan_only"
            | "request_runtime_gate_design_changes"
            | "reject_runtime_gate"
    );
    let owner_approves_plan =
        owner_decision == "approve_runtime_gate_implementation_plan_only";

    let mut block_reasons = BTreeSet::<String>::new();
    if !artifact_schema_valid {
        memory_biocortex_t6_push_reason(
            &mut block_reasons,
            "source_runtime_gate_design_artifact_schema_invalid",
        );
    }
    if !artifact_ready {
        memory_biocortex_t6_push_reason(
            &mut block_reasons,
            "source_runtime_gate_design_artifact_not_ready",
        );
    }
    if !artifact_safe_contract || artifact_claims_runtime_authority {
        memory_biocortex_t6_push_reason(
            &mut block_reasons,
            "source_runtime_gate_design_artifact_claims_runtime_authority",
        );
    }
    if !artifact_requirements_ok {
        memory_biocortex_t6_push_reason(
            &mut block_reasons,
            "source_runtime_gate_design_artifact_requirements_incomplete",
        );
    }
    if artifact_flags_raw {
        memory_biocortex_t6_push_reason(
            &mut block_reasons,
            "source_runtime_gate_design_artifact_contains_raw",
        );
    }
    if owner.is_none() {
        memory_biocortex_t6_push_reason(&mut block_reasons, "missing_owner");
    }
    if decision_source.is_none() {
        memory_biocortex_t6_push_reason(&mut block_reasons, "missing_decision_source");
    }
    if !owner_decision_valid {
        memory_biocortex_t6_push_reason(&mut block_reasons, "invalid_owner_decision");
    }
    if owner_decision_valid && !owner_approves_plan {
        memory_biocortex_t6_push_reason(
            &mut block_reasons,
            "owner_did_not_approve_runtime_gate_implementation_plan",
        );
    }
    for reason in memory_biocortex_t6_string_array_at(
        artifact,
        "/runtime_gate_design_artifact/block_reasons",
    ) {
        memory_biocortex_t6_push_reason(&mut block_reasons, &reason);
    }

    let ready = block_reasons.is_empty();
    let verdict = if ready {
        "owner_approved_runtime_gate_implementation_plan_only"
    } else {
        "blocked_before_runtime_gate_owner_review_record"
    };
    let next_gate = if ready {
        "prepare_runtime_gate_implementation_plan_before_code"
    } else {
        "repair_or_reapprove_runtime_gate_design_artifact"
    };
    let telemetry_fields = memory_biocortex_t6_string_array_at(
        artifact,
        "/runtime_gate_design_artifact/requirements/telemetry_fields",
    );

    json!({
        "schema": MEMORY_BIOCORTEX_T6_CANDIDATE_EXPANSION_RUNTIME_GATE_OWNER_REVIEW_RECORD_SCHEMA,
        "generated_at": unix_now_secs(),
        "read_only": true,
        "purpose": "T6 candidate-expansion runtime-gate owner-review record: consume a safe runtime-gate design artifact plus an explicit owner decision and record whether implementation planning may begin without implementing runtime code, running dry-runs, or approving candidate-set expansion.",
        "runtime_gate_owner_review_record": {
            "ready": ready,
            "block_reasons": block_reasons.into_iter().collect::<Vec<_>>(),
            "owner": owner,
            "owner_decision": owner_decision,
            "decision_source": decision_source,
            "decision": {
                "verdict": verdict,
                "next_gate": next_gate,
                "implementation_plan_only": true,
                "runtime_code_out_of_scope": true,
                "runtime_authority_out_of_scope": true,
                "candidate_expansion_authority_out_of_scope": true,
            },
            "source_decision": {
                "design_artifact_verdict": memory_biocortex_t6_string_at(artifact, "/runtime_gate_design_artifact/decision/verdict"),
                "design_artifact_next_gate": memory_biocortex_t6_string_at(artifact, "/runtime_gate_design_artifact/decision/next_gate"),
                "source_owner_decision": memory_biocortex_t6_string_at(artifact, "/runtime_gate_design_artifact/source_decision/owner_decision"),
                "source_owner": memory_biocortex_t6_string_at(artifact, "/runtime_gate_design_artifact/source_decision/owner"),
                "source_decision_source": memory_biocortex_t6_string_at(artifact, "/runtime_gate_design_artifact/source_decision/decision_source"),
            },
            "source_evidence": {
                "metrics": {
                    "evaluated_count": memory_biocortex_t6_u64_at(artifact, "/runtime_gate_design_artifact/source_evidence/metrics/evaluated_count"),
                    "search_error_count": memory_biocortex_t6_u64_at(artifact, "/runtime_gate_design_artifact/source_evidence/metrics/search_error_count"),
                    "baseline_miss_count": memory_biocortex_t6_u64_at(artifact, "/runtime_gate_design_artifact/source_evidence/metrics/baseline_miss_count"),
                    "candidate_expansion_added_hit_count": memory_biocortex_t6_u64_at(artifact, "/runtime_gate_design_artifact/source_evidence/metrics/candidate_expansion_added_hit_count"),
                    "candidate_expansion_added_hit_rate": memory_biocortex_t6_f64_at(artifact, "/runtime_gate_design_artifact/source_evidence/metrics/candidate_expansion_added_hit_rate"),
                    "graph_expansion_found_rate": memory_biocortex_t6_f64_at(artifact, "/runtime_gate_design_artifact/source_evidence/metrics/graph_expansion_found_rate"),
                },
                "evidence_strength": {
                    "tier": memory_biocortex_t6_string_at(artifact, "/runtime_gate_design_artifact/source_evidence/evidence_strength/tier"),
                    "caveats": memory_biocortex_t6_string_array_at(artifact, "/runtime_gate_design_artifact/source_evidence/evidence_strength/caveats"),
                },
            },
            "requirements": {
                "separate_runtime_gate_tool": true,
                "separate_owner_runtime_approval": true,
                "feature_flag_default_off": true,
                "shadow_mode_first": true,
                "deterministic_replay_fixture": true,
                "bounded_candidate_delta": true,
                "negative_controls": true,
                "rollback_plan": true,
                "telemetry_fields": telemetry_fields,
            },
        },
        "review_contract": {
            "may_prepare_runtime_gate_implementation_plan": ready,
            "may_implement_runtime_gate_code_now": false,
            "candidate_expansion_experiment_approved": false,
            "may_run_candidate_expansion_dry_run_now": false,
            "may_expand_candidate_set_now": false,
            "changes_candidate_set_now": false,
            "runtime_influence_approved": false,
            "may_change_search_order_now": false,
            "this_record_approves_runtime_candidate_expansion": false,
            "requires_separate_implementation_plan_artifact": true,
            "requires_separate_code_implementation_gate": true,
        },
        "implementation_plan_checklist": [
            "Define a runtime gate entry point that is feature-flagged off by default.",
            "Keep initial implementation shadow-only and unable to change candidate ordering.",
            "Define deterministic replay fixtures and acceptance thresholds before coding runtime behavior.",
            "Define negative controls and regression thresholds before any shadow-mode run.",
            "Define telemetry for baseline and expanded candidate counts, added candidates, selected source, lift class, and negative-control regressions.",
            "Define rollback behavior that restores the baseline candidate path with no search-order influence.",
            "Require a separate code implementation gate after the implementation plan; this owner-review record is not code approval."
        ],
        "decision": {
            "verdict": verdict,
            "next_gate": next_gate,
            "implementation_plan_only": true,
            "runtime_code_out_of_scope": true,
            "runtime_authority_out_of_scope": true,
            "candidate_expansion_authority_out_of_scope": true,
        },
        "links": {
            "reviewer": reviewer,
            "commit": commit,
            "forum_post_id": forum_post_id,
            "memory_key": memory_key,
        },
        "input_contract": {
            "runtime_gate_design_artifact_included": false,
            "runtime_gate_preflight_included": false,
            "owner_decision_record_included": false,
            "human_review_packet_included": false,
            "dry_run_report_included": false,
            "dry_run_plan_included": false,
            "recall_expansion_summary_included": false,
            "case_rows_included": false,
            "raw_query_included": false,
            "raw_queries_included": false,
            "raw_keys_included": false,
            "content_included": false,
            "raw_error_included": false,
        },
        "non_goals": [
            "Does not implement a runtime gate.",
            "Does not run BioCortex.",
            "Does not call memory_search or memory_neighbors.",
            "Does not sample production memories or graph rows.",
            "Does not echo runtime-gate design artifacts, preflights, owner-decision records, human-review packets, dry-run reports, dry-run plans, recall summaries, case rows, queries, keys, content, or raw errors.",
            "Does not write memory, graph edges, authorization records, or approval packets.",
            "Does not approve runtime influence, search-order changes, dry-run execution, candidate-set expansion, or runtime-gate code implementation."
        ],
    })
}

pub struct MemoryBioCortexT6CandidateExpansionRuntimeGateOwnerReviewRecordTool;
impl MemoryBioCortexT6CandidateExpansionRuntimeGateOwnerReviewRecordTool {
    pub fn new() -> Self {
        Self
    }
}
#[async_trait]
impl McpTool for MemoryBioCortexT6CandidateExpansionRuntimeGateOwnerReviewRecordTool {
    fn name(&self) -> &'static str {
        "memory_biocortex_t6_candidate_expansion_runtime_gate_owner_review_record"
    }

    fn schema(&self) -> ToolSchema {
        ToolSchema {
            name: self.name().into(),
            description: "Read-only T6 candidate-expansion runtime-gate owner-review record. \
                Consumes a safe runtime-gate design artifact plus an explicit \
                owner decision and records whether implementation planning may \
                begin without writing state, implementing runtime code, \
                approving runtime influence, or expanding candidate sets."
                .into(),
            input_schema: json!({
                "type": "object",
                "required": [
                    "runtime_gate_design_artifact",
                    "owner",
                    "owner_decision",
                    "decision_source"
                ],
                "properties": {
                    "runtime_gate_design_artifact": {
                        "type": "object",
                        "description": "JSON object produced by memory_biocortex_t6_candidate_expansion_runtime_gate_design_artifact. Unknown/raw fields are ignored and never echoed."
                    },
                    "owner": {
                        "type": "string",
                        "description": "Owner identity or handle making the review decision."
                    },
                    "owner_decision": {
                        "type": "string",
                        "enum": [
                            "approve_runtime_gate_implementation_plan_only",
                            "request_runtime_gate_design_changes",
                            "reject_runtime_gate"
                        ],
                        "description": "Explicit owner decision. Only approve_runtime_gate_implementation_plan_only can open the next implementation-plan gate; no value approves runtime code or candidate expansion."
                    },
                    "decision_source": {
                        "type": "string",
                        "description": "External source for the owner decision, such as forum post id or chat checkpoint."
                    },
                    "reviewer": {
                        "type": "string",
                        "description": "Optional reviewer identity or handle."
                    },
                    "commit": {
                        "type": "string",
                        "description": "Optional implementation commit under review."
                    },
                    "forum_post_id": {
                        "type": "string",
                        "description": "Optional forum post id linking this review record."
                    },
                    "memory_key": {
                        "type": "string",
                        "description": "Optional memory key linking this review record."
                    }
                }
            }),
        }
    }

    async fn execute(&self, args: Value, _ctx: &ToolContext) -> Result<ToolResult> {
        Ok(ToolResult::json_text(
            &memory_biocortex_t6_candidate_expansion_runtime_gate_owner_review_record_payload(args),
        ))
    }
}

pub(super) fn memory_biocortex_t6_candidate_expansion_runtime_gate_implementation_plan_artifact_payload(
    args: Value,
) -> Value {
    let record = args
        .get("runtime_gate_owner_review_record")
        .unwrap_or(&Value::Null);
    let reviewer = args
        .get("reviewer")
        .and_then(Value::as_str)
        .map(|s| memory_biocortex_t6_clamp_label(s, 80))
        .filter(|s| !s.is_empty());
    let commit = args
        .get("commit")
        .and_then(Value::as_str)
        .map(|s| memory_biocortex_t6_clamp_label(s, 80))
        .filter(|s| !s.is_empty());
    let forum_post_id = args
        .get("forum_post_id")
        .and_then(Value::as_str)
        .map(|s| memory_biocortex_t6_clamp_label(s, 80))
        .filter(|s| !s.is_empty());
    let memory_key = args
        .get("memory_key")
        .and_then(Value::as_str)
        .map(|s| memory_biocortex_t6_clamp_label(s, 160))
        .filter(|s| !s.is_empty());

    let record_schema_valid = memory_biocortex_t6_string_at(record, "/schema")
        == Some(MEMORY_BIOCORTEX_T6_CANDIDATE_EXPANSION_RUNTIME_GATE_OWNER_REVIEW_RECORD_SCHEMA);
    let record_ready =
        memory_biocortex_t6_bool_at(record, "/runtime_gate_owner_review_record/ready")
            == Some(true);
    let owner_decision = memory_biocortex_t6_string_at(
        record,
        "/runtime_gate_owner_review_record/owner_decision",
    )
    .unwrap_or("missing_owner_decision");
    let owner_approves_plan =
        owner_decision == "approve_runtime_gate_implementation_plan_only";
    let record_safe_contract = memory_biocortex_t6_bool_at(record, "/read_only") == Some(true)
        && memory_biocortex_t6_bool_at(
            record,
            "/review_contract/may_prepare_runtime_gate_implementation_plan",
        ) == Some(true)
        && memory_biocortex_t6_bool_at(
            record,
            "/review_contract/may_implement_runtime_gate_code_now",
        ) == Some(false)
        && memory_biocortex_t6_bool_at(
            record,
            "/review_contract/candidate_expansion_experiment_approved",
        ) == Some(false)
        && memory_biocortex_t6_bool_at(
            record,
            "/review_contract/may_run_candidate_expansion_dry_run_now",
        ) == Some(false)
        && memory_biocortex_t6_bool_at(
            record,
            "/review_contract/may_expand_candidate_set_now",
        ) == Some(false)
        && memory_biocortex_t6_bool_at(record, "/review_contract/changes_candidate_set_now")
            == Some(false)
        && memory_biocortex_t6_bool_at(record, "/review_contract/runtime_influence_approved")
            == Some(false)
        && memory_biocortex_t6_bool_at(record, "/review_contract/may_change_search_order_now")
            == Some(false)
        && memory_biocortex_t6_bool_at(
            record,
            "/review_contract/this_record_approves_runtime_candidate_expansion",
        ) == Some(false)
        && memory_biocortex_t6_bool_at(
            record,
            "/review_contract/requires_separate_implementation_plan_artifact",
        ) == Some(true)
        && memory_biocortex_t6_bool_at(
            record,
            "/review_contract/requires_separate_code_implementation_gate",
        ) == Some(true);
    let record_claims_runtime_authority = memory_biocortex_t6_any_true(
        record,
        &[
            "/review_contract/may_implement_runtime_gate_code_now",
            "/review_contract/candidate_expansion_experiment_approved",
            "/review_contract/may_run_candidate_expansion_dry_run_now",
            "/review_contract/may_expand_candidate_set_now",
            "/review_contract/changes_candidate_set_now",
            "/review_contract/runtime_influence_approved",
            "/review_contract/may_change_search_order_now",
            "/review_contract/this_record_approves_runtime_candidate_expansion",
        ],
    );
    let record_requirements_ok = [
        "/runtime_gate_owner_review_record/requirements/separate_runtime_gate_tool",
        "/runtime_gate_owner_review_record/requirements/separate_owner_runtime_approval",
        "/runtime_gate_owner_review_record/requirements/feature_flag_default_off",
        "/runtime_gate_owner_review_record/requirements/shadow_mode_first",
        "/runtime_gate_owner_review_record/requirements/deterministic_replay_fixture",
        "/runtime_gate_owner_review_record/requirements/bounded_candidate_delta",
        "/runtime_gate_owner_review_record/requirements/negative_controls",
        "/runtime_gate_owner_review_record/requirements/rollback_plan",
    ]
    .iter()
    .all(|path| memory_biocortex_t6_bool_at(record, path) == Some(true))
        && !memory_biocortex_t6_string_array_at(
            record,
            "/runtime_gate_owner_review_record/requirements/telemetry_fields",
        )
        .is_empty();
    let record_flags_raw = memory_biocortex_t6_has_raw_payload_fields(record)
        || record.get("runtime_gate_design_artifact").is_some()
        || record.get("runtime_gate_preflight").is_some()
        || record.get("owner_decision_record").is_some()
        || record.get("human_review_packet").is_some()
        || record.get("candidate_expansion_dry_run_report").is_some()
        || record.get("dry_run_report").is_some()
        || record.get("candidate_expansion_dry_run_plan").is_some()
        || record.get("recall_expansion_summary").is_some()
        || record.get("case_rows").is_some()
        || memory_biocortex_t6_any_true(
            record,
            &[
                "/input_contract/runtime_gate_owner_review_record_included",
                "/input_contract/runtime_gate_design_artifact_included",
                "/input_contract/runtime_gate_preflight_included",
                "/input_contract/owner_decision_record_included",
                "/input_contract/human_review_packet_included",
                "/input_contract/dry_run_report_included",
                "/input_contract/dry_run_plan_included",
                "/input_contract/recall_expansion_summary_included",
                "/input_contract/case_rows_included",
                "/input_contract/raw_query_included",
                "/input_contract/raw_queries_included",
                "/input_contract/raw_keys_included",
                "/input_contract/content_included",
                "/input_contract/raw_error_included",
            ],
        );

    let mut block_reasons = BTreeSet::<String>::new();
    if !record_schema_valid {
        memory_biocortex_t6_push_reason(
            &mut block_reasons,
            "source_runtime_gate_owner_review_record_schema_invalid",
        );
    }
    if !record_ready {
        memory_biocortex_t6_push_reason(
            &mut block_reasons,
            "source_runtime_gate_owner_review_record_not_ready",
        );
    }
    if !record_safe_contract || record_claims_runtime_authority {
        memory_biocortex_t6_push_reason(
            &mut block_reasons,
            "source_runtime_gate_owner_review_record_claims_runtime_authority",
        );
    }
    if !record_requirements_ok {
        memory_biocortex_t6_push_reason(
            &mut block_reasons,
            "source_runtime_gate_owner_review_record_requirements_incomplete",
        );
    }
    if record_flags_raw {
        memory_biocortex_t6_push_reason(
            &mut block_reasons,
            "source_runtime_gate_owner_review_record_contains_raw",
        );
    }
    if !owner_approves_plan {
        memory_biocortex_t6_push_reason(
            &mut block_reasons,
            "source_owner_review_record_not_approved_for_implementation_plan",
        );
    }
    for reason in memory_biocortex_t6_string_array_at(
        record,
        "/runtime_gate_owner_review_record/block_reasons",
    ) {
        memory_biocortex_t6_push_reason(&mut block_reasons, &reason);
    }

    let ready = block_reasons.is_empty();
    let verdict = if ready {
        "runtime_gate_implementation_plan_ready_for_code_gate_review"
    } else {
        "blocked_before_runtime_gate_implementation_plan_artifact"
    };
    let next_gate = if ready {
        "author_review_runtime_gate_code_implementation_gate_before_code"
    } else {
        "repair_or_reapprove_runtime_gate_owner_review_record"
    };
    let telemetry_fields = memory_biocortex_t6_string_array_at(
        record,
        "/runtime_gate_owner_review_record/requirements/telemetry_fields",
    );

    json!({
        "schema": MEMORY_BIOCORTEX_T6_CANDIDATE_EXPANSION_RUNTIME_GATE_IMPLEMENTATION_PLAN_ARTIFACT_SCHEMA,
        "generated_at": unix_now_secs(),
        "read_only": true,
        "purpose": "T6 candidate-expansion runtime-gate implementation-plan artifact: consume a safe owner-review record and describe the code-gate plan without implementing runtime code, running dry-runs, or approving candidate-set expansion.",
        "runtime_gate_implementation_plan_artifact": {
            "ready": ready,
            "block_reasons": block_reasons.into_iter().collect::<Vec<_>>(),
            "decision": {
                "verdict": verdict,
                "next_gate": next_gate,
                "implementation_plan_only": true,
                "runtime_code_out_of_scope": true,
                "runtime_authority_out_of_scope": true,
                "candidate_expansion_authority_out_of_scope": true,
            },
            "source_decision": {
                "owner": memory_biocortex_t6_string_at(record, "/runtime_gate_owner_review_record/owner"),
                "owner_decision": owner_decision,
                "decision_source": memory_biocortex_t6_string_at(record, "/runtime_gate_owner_review_record/decision_source"),
                "owner_review_verdict": memory_biocortex_t6_string_at(record, "/runtime_gate_owner_review_record/decision/verdict"),
                "owner_review_next_gate": memory_biocortex_t6_string_at(record, "/runtime_gate_owner_review_record/decision/next_gate"),
                "design_artifact_verdict": memory_biocortex_t6_string_at(record, "/runtime_gate_owner_review_record/source_decision/design_artifact_verdict"),
                "design_artifact_next_gate": memory_biocortex_t6_string_at(record, "/runtime_gate_owner_review_record/source_decision/design_artifact_next_gate"),
            },
            "source_evidence": {
                "metrics": {
                    "evaluated_count": memory_biocortex_t6_u64_at(record, "/runtime_gate_owner_review_record/source_evidence/metrics/evaluated_count"),
                    "search_error_count": memory_biocortex_t6_u64_at(record, "/runtime_gate_owner_review_record/source_evidence/metrics/search_error_count"),
                    "baseline_miss_count": memory_biocortex_t6_u64_at(record, "/runtime_gate_owner_review_record/source_evidence/metrics/baseline_miss_count"),
                    "candidate_expansion_added_hit_count": memory_biocortex_t6_u64_at(record, "/runtime_gate_owner_review_record/source_evidence/metrics/candidate_expansion_added_hit_count"),
                    "candidate_expansion_added_hit_rate": memory_biocortex_t6_f64_at(record, "/runtime_gate_owner_review_record/source_evidence/metrics/candidate_expansion_added_hit_rate"),
                    "graph_expansion_found_rate": memory_biocortex_t6_f64_at(record, "/runtime_gate_owner_review_record/source_evidence/metrics/graph_expansion_found_rate"),
                },
                "evidence_strength": {
                    "tier": memory_biocortex_t6_string_at(record, "/runtime_gate_owner_review_record/source_evidence/evidence_strength/tier"),
                    "caveats": memory_biocortex_t6_string_array_at(record, "/runtime_gate_owner_review_record/source_evidence/evidence_strength/caveats"),
                },
            },
            "requirements": {
                "separate_runtime_gate_tool": true,
                "separate_owner_runtime_approval": true,
                "feature_flag_default_off": true,
                "shadow_mode_first": true,
                "deterministic_replay_fixture": true,
                "bounded_candidate_delta": true,
                "negative_controls": true,
                "rollback_plan": true,
                "telemetry_fields": telemetry_fields,
            },
        },
        "implementation_plan": {
            "runtime_gate_entrypoint": {
                "tool_name": "memory_biocortex_t6_candidate_expansion_runtime_gate_code_implementation_gate",
                "scope": "separate_code_gate_review_before_runtime_code",
                "default_runtime_enabled": false,
            },
            "feature_flag": {
                "name": "AB_BIOCORTEX_T6_CANDIDATE_EXPANSION_SHADOW",
                "default_off": true,
                "required_before_any_shadow_execution": true,
            },
            "shadow_mode_contract": {
                "shadow_mode_first": true,
                "default_enabled": false,
                "can_influence_candidate_set": false,
                "can_change_search_order": false,
                "can_write_memory": false,
            },
            "deterministic_replay_fixture": {
                "required": true,
                "uses_redacted_fixture_ids_only": true,
                "must_run_before_shadow_execution": true,
            },
            "bounded_candidate_delta": {
                "required": true,
                "max_added_candidates_requires_separate_code_gate": true,
                "no_unbounded_neighbor_walks": true,
            },
            "negative_controls": {
                "required": true,
                "must_include_no_lift_and_noise_cases": true,
                "regression_blocks_shadow_execution": true,
            },
            "telemetry_fields": telemetry_fields,
            "rollback_contract": {
                "required": true,
                "restores_baseline_candidate_path": true,
                "disables_shadow_flag": true,
                "removes_runtime_influence": true,
            },
        },
        "plan_contract": {
            "may_prepare_runtime_gate_code_implementation_gate": ready,
            "may_implement_runtime_gate_code_now": false,
            "candidate_expansion_experiment_approved": false,
            "may_run_candidate_expansion_dry_run_now": false,
            "may_expand_candidate_set_now": false,
            "changes_candidate_set_now": false,
            "runtime_influence_approved": false,
            "may_change_search_order_now": false,
            "this_plan_approves_runtime_candidate_expansion": false,
            "requires_separate_code_implementation_gate": true,
        },
        "code_gate_checklist": [
            "Review this implementation plan before adding any runtime code.",
            "Keep the future runtime gate behind a default-off feature flag.",
            "Implement shadow-only observation before any candidate-set influence.",
            "Require deterministic replay fixtures and negative controls before shadow execution.",
            "Emit only aggregate telemetry fields and never raw queries, keys, content, or case rows.",
            "Require a separate owner approval before any runtime influence or candidate-set expansion."
        ],
        "links": {
            "reviewer": reviewer,
            "commit": commit,
            "forum_post_id": forum_post_id,
            "memory_key": memory_key,
        },
        "input_contract": {
            "runtime_gate_owner_review_record_included": false,
            "runtime_gate_design_artifact_included": false,
            "runtime_gate_preflight_included": false,
            "owner_decision_record_included": false,
            "human_review_packet_included": false,
            "dry_run_report_included": false,
            "dry_run_plan_included": false,
            "recall_expansion_summary_included": false,
            "case_rows_included": false,
            "raw_query_included": false,
            "raw_queries_included": false,
            "raw_keys_included": false,
            "content_included": false,
            "raw_error_included": false,
        },
        "non_goals": [
            "Does not implement runtime-gate code.",
            "Does not run BioCortex.",
            "Does not call memory_search or memory_neighbors.",
            "Does not sample production memories or graph rows.",
            "Does not echo owner-review records, runtime-gate design artifacts, preflights, owner-decision records, human-review packets, dry-run reports, dry-run plans, recall summaries, case rows, queries, keys, content, or raw errors.",
            "Does not write memory, graph edges, authorization records, approval packets, feature flags, or runtime configuration.",
            "Does not approve runtime influence, search-order changes, dry-run execution, candidate-set expansion, or runtime-gate code implementation."
        ],
    })
}

pub struct MemoryBioCortexT6CandidateExpansionRuntimeGateImplementationPlanArtifactTool;
impl MemoryBioCortexT6CandidateExpansionRuntimeGateImplementationPlanArtifactTool {
    pub fn new() -> Self {
        Self
    }
}
#[async_trait]
impl McpTool for MemoryBioCortexT6CandidateExpansionRuntimeGateImplementationPlanArtifactTool {
    fn name(&self) -> &'static str {
        "memory_biocortex_t6_candidate_expansion_runtime_gate_implementation_plan_artifact"
    }

    fn schema(&self) -> ToolSchema {
        ToolSchema {
            name: self.name().into(),
            description: "Read-only T6 candidate-expansion runtime-gate implementation-plan artifact. \
                Consumes a safe runtime-gate owner-review record and emits a \
                code-gate planning contract without writing state, implementing \
                runtime code, approving runtime influence, or expanding \
                candidate sets."
                .into(),
            input_schema: json!({
                "type": "object",
                "required": ["runtime_gate_owner_review_record"],
                "properties": {
                    "runtime_gate_owner_review_record": {
                        "type": "object",
                        "description": "JSON object produced by memory_biocortex_t6_candidate_expansion_runtime_gate_owner_review_record. Unknown/raw fields are ignored and never echoed."
                    },
                    "reviewer": {
                        "type": "string",
                        "description": "Optional reviewer identity or handle."
                    },
                    "commit": {
                        "type": "string",
                        "description": "Optional implementation commit under review."
                    },
                    "forum_post_id": {
                        "type": "string",
                        "description": "Optional forum post id linking this implementation-plan artifact."
                    },
                    "memory_key": {
                        "type": "string",
                        "description": "Optional memory key linking this implementation-plan artifact."
                    }
                }
            }),
        }
    }

    async fn execute(&self, args: Value, _ctx: &ToolContext) -> Result<ToolResult> {
        Ok(ToolResult::json_text(
            &memory_biocortex_t6_candidate_expansion_runtime_gate_implementation_plan_artifact_payload(args),
        ))
    }
}

pub(super) fn memory_biocortex_t6_candidate_expansion_runtime_gate_code_implementation_gate_payload(
    args: Value,
) -> Value {
    let plan = args
        .get("runtime_gate_implementation_plan_artifact")
        .unwrap_or(&Value::Null);
    let reviewer = args
        .get("reviewer")
        .and_then(Value::as_str)
        .map(|s| memory_biocortex_t6_clamp_label(s, 80))
        .filter(|s| !s.is_empty());
    let decision_source = args
        .get("decision_source")
        .and_then(Value::as_str)
        .map(|s| memory_biocortex_t6_clamp_label(s, 160))
        .filter(|s| !s.is_empty());
    let code_gate_decision = args
        .get("code_gate_decision")
        .and_then(Value::as_str)
        .map(str::trim)
        .filter(|s| !s.is_empty())
        .unwrap_or("missing_code_gate_decision");
    let commit = args
        .get("commit")
        .and_then(Value::as_str)
        .map(|s| memory_biocortex_t6_clamp_label(s, 80))
        .filter(|s| !s.is_empty());
    let forum_post_id = args
        .get("forum_post_id")
        .and_then(Value::as_str)
        .map(|s| memory_biocortex_t6_clamp_label(s, 80))
        .filter(|s| !s.is_empty());
    let memory_key = args
        .get("memory_key")
        .and_then(Value::as_str)
        .map(|s| memory_biocortex_t6_clamp_label(s, 160))
        .filter(|s| !s.is_empty());

    let plan_schema_valid = memory_biocortex_t6_string_at(plan, "/schema")
        == Some(
            MEMORY_BIOCORTEX_T6_CANDIDATE_EXPANSION_RUNTIME_GATE_IMPLEMENTATION_PLAN_ARTIFACT_SCHEMA,
        );
    let plan_ready =
        memory_biocortex_t6_bool_at(plan, "/runtime_gate_implementation_plan_artifact/ready")
            == Some(true);
    let plan_safe_contract = memory_biocortex_t6_bool_at(plan, "/read_only") == Some(true)
        && memory_biocortex_t6_bool_at(
            plan,
            "/plan_contract/may_prepare_runtime_gate_code_implementation_gate",
        ) == Some(true)
        && memory_biocortex_t6_bool_at(
            plan,
            "/plan_contract/may_implement_runtime_gate_code_now",
        ) == Some(false)
        && memory_biocortex_t6_bool_at(
            plan,
            "/plan_contract/candidate_expansion_experiment_approved",
        ) == Some(false)
        && memory_biocortex_t6_bool_at(
            plan,
            "/plan_contract/may_run_candidate_expansion_dry_run_now",
        ) == Some(false)
        && memory_biocortex_t6_bool_at(plan, "/plan_contract/may_expand_candidate_set_now")
            == Some(false)
        && memory_biocortex_t6_bool_at(plan, "/plan_contract/changes_candidate_set_now")
            == Some(false)
        && memory_biocortex_t6_bool_at(plan, "/plan_contract/runtime_influence_approved")
            == Some(false)
        && memory_biocortex_t6_bool_at(plan, "/plan_contract/may_change_search_order_now")
            == Some(false)
        && memory_biocortex_t6_bool_at(
            plan,
            "/plan_contract/this_plan_approves_runtime_candidate_expansion",
        ) == Some(false)
        && memory_biocortex_t6_bool_at(
            plan,
            "/plan_contract/requires_separate_code_implementation_gate",
        ) == Some(true);
    let plan_claims_runtime_authority = memory_biocortex_t6_any_true(
        plan,
        &[
            "/plan_contract/may_implement_runtime_gate_code_now",
            "/plan_contract/candidate_expansion_experiment_approved",
            "/plan_contract/may_run_candidate_expansion_dry_run_now",
            "/plan_contract/may_expand_candidate_set_now",
            "/plan_contract/changes_candidate_set_now",
            "/plan_contract/runtime_influence_approved",
            "/plan_contract/may_change_search_order_now",
            "/plan_contract/this_plan_approves_runtime_candidate_expansion",
            "/implementation_plan/shadow_mode_contract/can_influence_candidate_set",
            "/implementation_plan/shadow_mode_contract/can_change_search_order",
            "/implementation_plan/shadow_mode_contract/can_write_memory",
        ],
    );
    let plan_requirements_ok = [
        "/runtime_gate_implementation_plan_artifact/requirements/separate_runtime_gate_tool",
        "/runtime_gate_implementation_plan_artifact/requirements/separate_owner_runtime_approval",
        "/runtime_gate_implementation_plan_artifact/requirements/feature_flag_default_off",
        "/runtime_gate_implementation_plan_artifact/requirements/shadow_mode_first",
        "/runtime_gate_implementation_plan_artifact/requirements/deterministic_replay_fixture",
        "/runtime_gate_implementation_plan_artifact/requirements/bounded_candidate_delta",
        "/runtime_gate_implementation_plan_artifact/requirements/negative_controls",
        "/runtime_gate_implementation_plan_artifact/requirements/rollback_plan",
        "/implementation_plan/feature_flag/default_off",
        "/implementation_plan/feature_flag/required_before_any_shadow_execution",
        "/implementation_plan/shadow_mode_contract/shadow_mode_first",
        "/implementation_plan/deterministic_replay_fixture/required",
        "/implementation_plan/bounded_candidate_delta/required",
        "/implementation_plan/negative_controls/required",
        "/implementation_plan/rollback_contract/required",
    ]
    .iter()
    .all(|path| memory_biocortex_t6_bool_at(plan, path) == Some(true))
        && memory_biocortex_t6_bool_at(
            plan,
            "/implementation_plan/runtime_gate_entrypoint/default_runtime_enabled",
        ) == Some(false)
        && memory_biocortex_t6_bool_at(
            plan,
            "/implementation_plan/shadow_mode_contract/default_enabled",
        ) == Some(false)
        && memory_biocortex_t6_bool_at(
            plan,
            "/implementation_plan/shadow_mode_contract/can_influence_candidate_set",
        ) == Some(false)
        && memory_biocortex_t6_bool_at(
            plan,
            "/implementation_plan/shadow_mode_contract/can_change_search_order",
        ) == Some(false)
        && memory_biocortex_t6_bool_at(
            plan,
            "/implementation_plan/shadow_mode_contract/can_write_memory",
        ) == Some(false)
        && !memory_biocortex_t6_string_array_at(
            plan,
            "/runtime_gate_implementation_plan_artifact/requirements/telemetry_fields",
        )
        .is_empty()
        && !memory_biocortex_t6_string_array_at(plan, "/implementation_plan/telemetry_fields")
            .is_empty();
    let plan_flags_raw = memory_biocortex_t6_has_raw_payload_fields(plan)
        || plan.get("runtime_gate_owner_review_record").is_some()
        || plan.get("runtime_gate_design_artifact").is_some()
        || plan.get("runtime_gate_preflight").is_some()
        || plan.get("owner_decision_record").is_some()
        || plan.get("human_review_packet").is_some()
        || plan.get("candidate_expansion_dry_run_report").is_some()
        || plan.get("dry_run_report").is_some()
        || plan.get("candidate_expansion_dry_run_plan").is_some()
        || plan.get("recall_expansion_summary").is_some()
        || plan.get("case_rows").is_some()
        || memory_biocortex_t6_any_true(
            plan,
            &[
                "/input_contract/runtime_gate_implementation_plan_artifact_included",
                "/input_contract/runtime_gate_owner_review_record_included",
                "/input_contract/runtime_gate_design_artifact_included",
                "/input_contract/runtime_gate_preflight_included",
                "/input_contract/owner_decision_record_included",
                "/input_contract/human_review_packet_included",
                "/input_contract/dry_run_report_included",
                "/input_contract/dry_run_plan_included",
                "/input_contract/recall_expansion_summary_included",
                "/input_contract/case_rows_included",
                "/input_contract/raw_query_included",
                "/input_contract/raw_queries_included",
                "/input_contract/raw_keys_included",
                "/input_contract/content_included",
                "/input_contract/raw_error_included",
            ],
        );
    let code_gate_decision_valid = matches!(
        code_gate_decision,
        "approve_shadow_runtime_gate_code_implementation_only"
            | "request_runtime_gate_implementation_plan_changes"
            | "reject_runtime_gate_code_implementation"
    );
    let code_gate_approves_shadow_code =
        code_gate_decision == "approve_shadow_runtime_gate_code_implementation_only";

    let mut block_reasons = BTreeSet::<String>::new();
    if !plan_schema_valid {
        memory_biocortex_t6_push_reason(
            &mut block_reasons,
            "source_runtime_gate_implementation_plan_artifact_schema_invalid",
        );
    }
    if !plan_ready {
        memory_biocortex_t6_push_reason(
            &mut block_reasons,
            "source_runtime_gate_implementation_plan_artifact_not_ready",
        );
    }
    if !plan_safe_contract || plan_claims_runtime_authority {
        memory_biocortex_t6_push_reason(
            &mut block_reasons,
            "source_runtime_gate_implementation_plan_artifact_claims_runtime_authority",
        );
    }
    if !plan_requirements_ok {
        memory_biocortex_t6_push_reason(
            &mut block_reasons,
            "source_runtime_gate_implementation_plan_artifact_requirements_incomplete",
        );
    }
    if plan_flags_raw {
        memory_biocortex_t6_push_reason(
            &mut block_reasons,
            "source_runtime_gate_implementation_plan_artifact_contains_raw",
        );
    }
    if reviewer.is_none() {
        memory_biocortex_t6_push_reason(&mut block_reasons, "missing_reviewer");
    }
    if decision_source.is_none() {
        memory_biocortex_t6_push_reason(&mut block_reasons, "missing_decision_source");
    }
    if !code_gate_decision_valid {
        memory_biocortex_t6_push_reason(&mut block_reasons, "invalid_code_gate_decision");
    }
    if code_gate_decision_valid && !code_gate_approves_shadow_code {
        memory_biocortex_t6_push_reason(
            &mut block_reasons,
            "code_gate_did_not_approve_shadow_runtime_gate_code_implementation",
        );
    }
    for reason in memory_biocortex_t6_string_array_at(
        plan,
        "/runtime_gate_implementation_plan_artifact/block_reasons",
    ) {
        memory_biocortex_t6_push_reason(&mut block_reasons, &reason);
    }

    let ready = block_reasons.is_empty();
    let verdict = if ready {
        "shadow_runtime_gate_code_implementation_authorized"
    } else {
        "blocked_before_runtime_gate_code_implementation"
    };
    let next_gate = if ready {
        "implement_default_off_shadow_runtime_gate_code"
    } else {
        "repair_or_reapprove_runtime_gate_implementation_plan_artifact"
    };
    let telemetry_fields = memory_biocortex_t6_string_array_at(
        plan,
        "/implementation_plan/telemetry_fields",
    );

    json!({
        "schema": MEMORY_BIOCORTEX_T6_CANDIDATE_EXPANSION_RUNTIME_GATE_CODE_IMPLEMENTATION_GATE_SCHEMA,
        "generated_at": unix_now_secs(),
        "read_only": true,
        "purpose": "T6 candidate-expansion runtime-gate code-implementation gate: consume a safe implementation-plan artifact plus an explicit code-gate decision and record whether default-off shadow runtime-gate code may be implemented without enabling runtime execution, dry-runs, search-order changes, or candidate-set expansion.",
        "runtime_gate_code_implementation_gate": {
            "ready": ready,
            "block_reasons": block_reasons.into_iter().collect::<Vec<_>>(),
            "reviewer": reviewer,
            "code_gate_decision": code_gate_decision,
            "decision_source": decision_source,
            "decision": {
                "verdict": verdict,
                "next_gate": next_gate,
                "shadow_code_only": true,
                "default_off_required": true,
                "runtime_enablement_out_of_scope": true,
                "runtime_authority_out_of_scope": true,
                "candidate_expansion_authority_out_of_scope": true,
            },
            "source_decision": {
                "plan_verdict": memory_biocortex_t6_string_at(plan, "/runtime_gate_implementation_plan_artifact/decision/verdict"),
                "plan_next_gate": memory_biocortex_t6_string_at(plan, "/runtime_gate_implementation_plan_artifact/decision/next_gate"),
                "owner": memory_biocortex_t6_string_at(plan, "/runtime_gate_implementation_plan_artifact/source_decision/owner"),
                "owner_decision": memory_biocortex_t6_string_at(plan, "/runtime_gate_implementation_plan_artifact/source_decision/owner_decision"),
                "owner_decision_source": memory_biocortex_t6_string_at(plan, "/runtime_gate_implementation_plan_artifact/source_decision/decision_source"),
            },
            "source_evidence": {
                "metrics": {
                    "evaluated_count": memory_biocortex_t6_u64_at(plan, "/runtime_gate_implementation_plan_artifact/source_evidence/metrics/evaluated_count"),
                    "search_error_count": memory_biocortex_t6_u64_at(plan, "/runtime_gate_implementation_plan_artifact/source_evidence/metrics/search_error_count"),
                    "baseline_miss_count": memory_biocortex_t6_u64_at(plan, "/runtime_gate_implementation_plan_artifact/source_evidence/metrics/baseline_miss_count"),
                    "candidate_expansion_added_hit_count": memory_biocortex_t6_u64_at(plan, "/runtime_gate_implementation_plan_artifact/source_evidence/metrics/candidate_expansion_added_hit_count"),
                    "candidate_expansion_added_hit_rate": memory_biocortex_t6_f64_at(plan, "/runtime_gate_implementation_plan_artifact/source_evidence/metrics/candidate_expansion_added_hit_rate"),
                    "graph_expansion_found_rate": memory_biocortex_t6_f64_at(plan, "/runtime_gate_implementation_plan_artifact/source_evidence/metrics/graph_expansion_found_rate"),
                },
                "evidence_strength": {
                    "tier": memory_biocortex_t6_string_at(plan, "/runtime_gate_implementation_plan_artifact/source_evidence/evidence_strength/tier"),
                    "caveats": memory_biocortex_t6_string_array_at(plan, "/runtime_gate_implementation_plan_artifact/source_evidence/evidence_strength/caveats"),
                },
            },
        },
        "implementation_boundaries": {
            "feature_flag_name": memory_biocortex_t6_string_at(plan, "/implementation_plan/feature_flag/name"),
            "feature_flag_default_off": true,
            "shadow_mode_first": true,
            "default_runtime_enabled": false,
            "default_shadow_enabled": false,
            "deterministic_replay_fixture_required": true,
            "negative_controls_required": true,
            "bounded_candidate_delta_required": true,
            "rollback_required": true,
            "telemetry_fields": telemetry_fields,
        },
        "code_implementation_contract": {
            "may_implement_shadow_runtime_gate_code": ready,
            "may_enable_runtime_gate_now": false,
            "may_run_shadow_mode_now": false,
            "candidate_expansion_experiment_approved": false,
            "may_run_candidate_expansion_dry_run_now": false,
            "may_expand_candidate_set_now": false,
            "changes_candidate_set_now": false,
            "runtime_influence_approved": false,
            "may_change_search_order_now": false,
            "may_write_memory_or_graph_edges": false,
            "this_gate_approves_runtime_candidate_expansion": false,
            "requires_separate_shadow_execution_gate": true,
            "requires_separate_runtime_enablement_gate": true,
        },
        "implementation_checklist": [
            "Implement only a default-off shadow runtime-gate code path.",
            "Keep feature flag disabled by default and unreachable without explicit operator opt-in.",
            "Do not change candidate ordering, candidate-set membership, memory search, or graph writes.",
            "Add deterministic replay fixtures before any shadow execution.",
            "Add negative controls that block later shadow execution on regression.",
            "Emit only aggregate telemetry fields; never log raw queries, keys, content, case rows, or raw errors.",
            "Require a separate shadow-execution gate before running the code and a separate runtime-enable gate before any influence."
        ],
        "links": {
            "commit": commit,
            "forum_post_id": forum_post_id,
            "memory_key": memory_key,
        },
        "input_contract": {
            "runtime_gate_implementation_plan_artifact_included": false,
            "runtime_gate_owner_review_record_included": false,
            "runtime_gate_design_artifact_included": false,
            "runtime_gate_preflight_included": false,
            "owner_decision_record_included": false,
            "human_review_packet_included": false,
            "dry_run_report_included": false,
            "dry_run_plan_included": false,
            "recall_expansion_summary_included": false,
            "case_rows_included": false,
            "raw_query_included": false,
            "raw_queries_included": false,
            "raw_keys_included": false,
            "content_included": false,
            "raw_error_included": false,
        },
        "non_goals": [
            "Does not enable a runtime gate.",
            "Does not run shadow mode.",
            "Does not run BioCortex.",
            "Does not call memory_search or memory_neighbors.",
            "Does not sample production memories or graph rows.",
            "Does not echo implementation-plan artifacts, owner-review records, design artifacts, preflights, owner-decision records, human-review packets, dry-run reports, dry-run plans, recall summaries, case rows, queries, keys, content, or raw errors.",
            "Does not write memory, graph edges, authorization records, approval packets, feature flags, or runtime configuration.",
            "Does not approve runtime influence, search-order changes, dry-run execution, candidate-set expansion, or runtime enablement."
        ],
    })
}

pub struct MemoryBioCortexT6CandidateExpansionRuntimeGateCodeImplementationGateTool;
impl MemoryBioCortexT6CandidateExpansionRuntimeGateCodeImplementationGateTool {
    pub fn new() -> Self {
        Self
    }
}
#[async_trait]
impl McpTool for MemoryBioCortexT6CandidateExpansionRuntimeGateCodeImplementationGateTool {
    fn name(&self) -> &'static str {
        "memory_biocortex_t6_candidate_expansion_runtime_gate_code_implementation_gate"
    }

    fn schema(&self) -> ToolSchema {
        ToolSchema {
            name: self.name().into(),
            description: "Read-only T6 candidate-expansion runtime-gate code-implementation gate. \
                Consumes a safe implementation-plan artifact plus an explicit \
                code-gate decision and can only authorize default-off shadow \
                code implementation; it never enables runtime execution, \
                runtime influence, search-order changes, writes, or candidate \
                expansion."
                .into(),
            input_schema: json!({
                "type": "object",
                "required": [
                    "runtime_gate_implementation_plan_artifact",
                    "reviewer",
                    "code_gate_decision",
                    "decision_source"
                ],
                "properties": {
                    "runtime_gate_implementation_plan_artifact": {
                        "type": "object",
                        "description": "JSON object produced by memory_biocortex_t6_candidate_expansion_runtime_gate_implementation_plan_artifact. Unknown/raw fields are ignored and never echoed."
                    },
                    "reviewer": {
                        "type": "string",
                        "description": "Reviewer identity or handle authorizing the code gate decision."
                    },
                    "code_gate_decision": {
                        "type": "string",
                        "enum": [
                            "approve_shadow_runtime_gate_code_implementation_only",
                            "request_runtime_gate_implementation_plan_changes",
                            "reject_runtime_gate_code_implementation"
                        ],
                        "description": "Explicit code-gate decision. Only approve_shadow_runtime_gate_code_implementation_only can open default-off shadow code implementation; no value approves runtime execution or candidate expansion."
                    },
                    "decision_source": {
                        "type": "string",
                        "description": "External source for the code-gate decision, such as forum post id or chat checkpoint."
                    },
                    "commit": {
                        "type": "string",
                        "description": "Optional implementation commit under review."
                    },
                    "forum_post_id": {
                        "type": "string",
                        "description": "Optional forum post id linking this code gate."
                    },
                    "memory_key": {
                        "type": "string",
                        "description": "Optional memory key linking this code gate."
                    }
                }
            }),
        }
    }

    async fn execute(&self, args: Value, _ctx: &ToolContext) -> Result<ToolResult> {
        Ok(ToolResult::json_text(
            &memory_biocortex_t6_candidate_expansion_runtime_gate_code_implementation_gate_payload(args),
        ))
    }
}

pub(super) const MEMORY_BIOCORTEX_T6_CANDIDATE_EXPANSION_SHADOW_RUNTIME_GATE_SCHEMA: &str =
    "agent_bridge.memory_biocortex_t6_candidate_expansion.shadow_runtime_gate.v0";
pub(super) const MEMORY_BIOCORTEX_T6_CANDIDATE_EXPANSION_SHADOW_ENABLE_ENV: &str =
    "AB_BIOCORTEX_T6_CANDIDATE_EXPANSION_SHADOW";
pub(super) const MEMORY_BIOCORTEX_T6_CANDIDATE_EXPANSION_DISABLE_ENV: &str =
    "AB_BIOCORTEX_T6_CANDIDATE_EXPANSION_DISABLE";

pub(super) fn memory_biocortex_t6_candidate_expansion_shadow_runtime_gate_u64(
    args: &Value,
    key: &str,
    default: u64,
    max: u64,
) -> u64 {
    args.get(key)
        .and_then(Value::as_u64)
        .unwrap_or(default)
        .min(max)
}

pub(super) fn memory_biocortex_t6_candidate_expansion_shadow_runtime_gate_bool(
    args: &Value,
    key: &str,
) -> bool {
    args.get(key).and_then(Value::as_bool).unwrap_or(false)
}

pub(super) fn memory_biocortex_t6_candidate_expansion_shadow_runtime_gate_has_raw(args: &Value) -> bool {
    [
        "raw_query",
        "raw_queries",
        "raw_key",
        "raw_keys",
        "baseline_keys",
        "expanded_keys",
        "graph_neighbor_keys",
        "candidate_keys",
        "content",
        "candidate_content",
        "case_rows",
        "dry_run_report",
        "recall_expansion_summary",
    ]
    .iter()
    .any(|field| args.get(*field).is_some())
}

pub(super) fn memory_biocortex_t6_candidate_expansion_shadow_runtime_gate_payload(args: Value) -> Value {
    let runtime_enabled =
        mcp_env_truthy(MEMORY_BIOCORTEX_T6_CANDIDATE_EXPANSION_SHADOW_ENABLE_ENV);
    let operator_disabled =
        mcp_env_truthy(MEMORY_BIOCORTEX_T6_CANDIDATE_EXPANSION_DISABLE_ENV);
    let baseline_candidate_count =
        memory_biocortex_t6_candidate_expansion_shadow_runtime_gate_u64(
            &args,
            "baseline_candidate_count",
            0,
            10_000,
        );
    let expanded_candidate_count =
        memory_biocortex_t6_candidate_expansion_shadow_runtime_gate_u64(
            &args,
            "expanded_candidate_count",
            baseline_candidate_count,
            10_000,
        );
    let added_candidate_count =
        memory_biocortex_t6_candidate_expansion_shadow_runtime_gate_u64(
            &args,
            "added_candidate_count",
            expanded_candidate_count.saturating_sub(baseline_candidate_count),
            10_000,
        );
    let max_added_candidates =
        memory_biocortex_t6_candidate_expansion_shadow_runtime_gate_u64(
            &args,
            "max_added_candidates",
            3,
            100,
        );
    let negative_control_regression_count =
        memory_biocortex_t6_candidate_expansion_shadow_runtime_gate_u64(
            &args,
            "negative_control_regression_count",
            0,
            10_000,
        );
    let deterministic_replay_fixture_present =
        memory_biocortex_t6_candidate_expansion_shadow_runtime_gate_bool(
            &args,
            "deterministic_replay_fixture_present",
        );
    let bounded_candidate_delta =
        memory_biocortex_t6_candidate_expansion_shadow_runtime_gate_bool(
            &args,
            "bounded_candidate_delta",
        );
    let rollback_plan_present =
        memory_biocortex_t6_candidate_expansion_shadow_runtime_gate_bool(
            &args,
            "rollback_plan_present",
        );
    let raw_fields_present =
        memory_biocortex_t6_candidate_expansion_shadow_runtime_gate_has_raw(&args);

    let mut block_reasons = BTreeSet::<String>::new();
    if operator_disabled {
        block_reasons.insert("operator_disabled".to_string());
    }
    if !runtime_enabled {
        block_reasons.insert("runtime_disabled".to_string());
    }
    if raw_fields_present {
        block_reasons.insert("raw_or_source_fields_present".to_string());
    }
    if !deterministic_replay_fixture_present {
        block_reasons.insert("deterministic_replay_fixture_missing".to_string());
    }
    if !bounded_candidate_delta {
        block_reasons.insert("bounded_candidate_delta_missing".to_string());
    }
    if added_candidate_count > max_added_candidates {
        block_reasons.insert("candidate_delta_exceeds_bound".to_string());
    }
    if negative_control_regression_count > 0 {
        block_reasons.insert("negative_control_regression_present".to_string());
    }
    if !rollback_plan_present {
        block_reasons.insert("rollback_plan_missing".to_string());
    }
    if runtime_enabled && !operator_disabled {
        block_reasons.insert("separate_shadow_execution_gate_required".to_string());
    }

    let status = if operator_disabled {
        "operator_disabled"
    } else if !runtime_enabled {
        "runtime_disabled"
    } else {
        "blocked_before_shadow_execution_gate"
    };

    json!({
        "schema": MEMORY_BIOCORTEX_T6_CANDIDATE_EXPANSION_SHADOW_RUNTIME_GATE_SCHEMA,
        "generated_at": unix_now_secs(),
        "read_only": true,
        "runtime_gate": {
            "status": status,
            "runtime_enable_env": MEMORY_BIOCORTEX_T6_CANDIDATE_EXPANSION_SHADOW_ENABLE_ENV,
            "runtime_enabled": runtime_enabled,
            "operator_disable_env": MEMORY_BIOCORTEX_T6_CANDIDATE_EXPANSION_DISABLE_ENV,
            "operator_disabled": operator_disabled,
            "feature_flag_default_off": true,
            "requires_separate_shadow_execution_gate": true,
            "requires_separate_runtime_enablement_gate": true,
            "next_gate": "author_review_shadow_execution_gate_before_any_shadow_run",
            "block_reasons": block_reasons.into_iter().collect::<Vec<_>>(),
        },
        "candidate_delta": {
            "baseline_candidate_count": baseline_candidate_count,
            "expanded_candidate_count": expanded_candidate_count,
            "added_candidate_count": added_candidate_count,
            "max_added_candidates": max_added_candidates,
            "bounded_candidate_delta": bounded_candidate_delta,
            "within_bound": added_candidate_count <= max_added_candidates,
            "raw_keys_included": false,
            "content_included": false,
        },
        "deterministic_replay_fixture": {
            "required": true,
            "present": deterministic_replay_fixture_present,
            "uses_redacted_fixture_ids_only": true,
            "case_rows_included": false,
        },
        "negative_controls": {
            "required": true,
            "negative_control_regression_count": negative_control_regression_count,
            "regression_blocks_shadow_execution": true,
        },
        "telemetry": {
            "required_fields": [
                "baseline_candidate_count",
                "expanded_candidate_count",
                "added_candidate_count",
                "selected_candidate_source",
                "recall_lift_class",
                "negative_control_regression_count"
            ],
            "raw_query_included": false,
            "raw_keys_included": false,
            "content_included": false,
            "writes_memory": false,
            "writes_graph_edges": false,
        },
        "rollback_contract": {
            "required": true,
            "present": rollback_plan_present,
            "restores_baseline_candidate_path": true,
            "disables_shadow_flag": true,
            "removes_runtime_influence": true,
        },
        "shadow_execution_contract": {
            "may_implement_shadow_runtime_gate_code": true,
            "may_run_shadow_mode_now": false,
            "may_enable_runtime_gate_now": false,
            "candidate_expansion_experiment_approved": false,
            "may_run_candidate_expansion_dry_run_now": false,
            "may_expand_candidate_set_now": false,
            "changes_candidate_set_now": false,
            "runtime_influence_approved": false,
            "may_change_search_order_now": false,
            "may_write_memory_or_graph_edges": false,
            "calls_memory_search": false,
            "calls_memory_neighbors": false,
            "runs_biocortex": false,
        },
        "input_contract": {
            "raw_query_included": false,
            "raw_queries_included": false,
            "raw_keys_included": false,
            "content_included": false,
            "case_rows_included": false,
            "source_artifacts_echoed": false,
            "unknown_fields_ignored": true,
        },
        "non_goals": [
            "Does not run shadow mode, BioCortex, memory_search, or memory_neighbors.",
            "Does not expand or reorder the runtime candidate set.",
            "Does not write memory, graph edges, telemetry rows, approvals, or feature flags.",
            "Does not approve runtime influence or runtime enablement."
        ],
    })
}

pub struct MemoryBioCortexT6CandidateExpansionShadowRuntimeGateTool;
impl MemoryBioCortexT6CandidateExpansionShadowRuntimeGateTool {
    pub fn new() -> Self {
        Self
    }
}

impl Default for MemoryBioCortexT6CandidateExpansionShadowRuntimeGateTool {
    fn default() -> Self {
        Self::new()
    }
}

#[async_trait]
impl McpTool for MemoryBioCortexT6CandidateExpansionShadowRuntimeGateTool {
    fn name(&self) -> &'static str {
        "memory_biocortex_t6_candidate_expansion_shadow_runtime_gate"
    }

    fn schema(&self) -> ToolSchema {
        ToolSchema {
            name: self.name().into(),
            description: "Read-only T6 candidate-expansion shadow runtime gate. \
                Reports the default-off feature flag, bounded candidate-delta, \
                deterministic replay, negative-control, telemetry, and rollback \
                contract before any separate shadow-execution gate. It never \
                runs shadow mode, BioCortex, memory_search, memory_neighbors, \
                writes, search-order changes, or candidate-set expansion."
                .into(),
            input_schema: json!({
                "type": "object",
                "properties": {
                    "baseline_candidate_count": {
                        "type": "integer",
                        "minimum": 0,
                        "maximum": 10000,
                        "default": 0,
                        "description": "Redacted baseline candidate count only."
                    },
                    "expanded_candidate_count": {
                        "type": "integer",
                        "minimum": 0,
                        "maximum": 10000,
                        "description": "Redacted hypothetical expanded candidate count only."
                    },
                    "added_candidate_count": {
                        "type": "integer",
                        "minimum": 0,
                        "maximum": 10000,
                        "description": "Redacted added candidate count only."
                    },
                    "max_added_candidates": {
                        "type": "integer",
                        "minimum": 0,
                        "maximum": 100,
                        "default": 3,
                        "description": "Bound for hypothetical added candidates before a later gate."
                    },
                    "negative_control_regression_count": {
                        "type": "integer",
                        "minimum": 0,
                        "maximum": 10000,
                        "default": 0,
                        "description": "Count only; any regression blocks later shadow execution."
                    },
                    "deterministic_replay_fixture_present": {
                        "type": "boolean",
                        "default": false,
                        "description": "Whether a deterministic, redacted replay fixture is present."
                    },
                    "bounded_candidate_delta": {
                        "type": "boolean",
                        "default": false,
                        "description": "Whether the candidate-delta bound is present."
                    },
                    "rollback_plan_present": {
                        "type": "boolean",
                        "default": false,
                        "description": "Whether rollback can restore the baseline path and disable the shadow flag."
                    }
                }
            }),
        }
    }

    async fn execute(&self, args: Value, _ctx: &ToolContext) -> Result<ToolResult> {
        Ok(ToolResult::json_text(
            &memory_biocortex_t6_candidate_expansion_shadow_runtime_gate_payload(args),
        ))
    }
}

pub(super) const MEMORY_BIOCORTEX_T6_CANDIDATE_EXPANSION_SHADOW_EXECUTION_GATE_SCHEMA: &str =
    "agent_bridge.memory_biocortex_t6_candidate_expansion.shadow_execution_gate.v0";

pub(super) fn memory_biocortex_t6_candidate_expansion_shadow_execution_gate_string(
    args: &Value,
    key: &str,
) -> String {
    args.get(key)
        .and_then(Value::as_str)
        .map(str::trim)
        .filter(|value| !value.is_empty())
        .unwrap_or("")
        .to_string()
}

pub(super) fn memory_biocortex_t6_candidate_expansion_shadow_execution_gate_bool_at(
    value: &Value,
    pointer: &str,
) -> bool {
    value
        .pointer(pointer)
        .and_then(Value::as_bool)
        .unwrap_or(false)
}

pub(super) fn memory_biocortex_t6_candidate_expansion_shadow_execution_gate_u64_at(
    value: &Value,
    pointer: &str,
) -> u64 {
    value.pointer(pointer).and_then(Value::as_u64).unwrap_or(0)
}

pub(super) fn memory_biocortex_t6_candidate_expansion_shadow_execution_gate_raw_key(key: &str) -> bool {
    matches!(
        key,
        "raw_query"
            | "raw_queries"
            | "raw_key"
            | "raw_keys"
            | "baseline_keys"
            | "expanded_keys"
            | "graph_neighbor_keys"
            | "candidate_keys"
            | "content"
            | "candidate_content"
            | "case_rows"
            | "dry_run_report"
            | "recall_expansion_summary"
    )
}

pub(super) fn memory_biocortex_t6_candidate_expansion_shadow_execution_gate_contains_raw(
    value: &Value,
) -> bool {
    match value {
        Value::Object(map) => map.iter().any(|(key, value)| {
            memory_biocortex_t6_candidate_expansion_shadow_execution_gate_raw_key(key)
                || memory_biocortex_t6_candidate_expansion_shadow_execution_gate_contains_raw(
                    value,
                )
        }),
        Value::Array(values) => values.iter().any(|value| {
            memory_biocortex_t6_candidate_expansion_shadow_execution_gate_contains_raw(value)
        }),
        _ => false,
    }
}

pub(super) fn memory_biocortex_t6_candidate_expansion_shadow_execution_gate_source_claims_runtime_authority(
    report: &Value,
) -> bool {
    [
        "/shadow_execution_contract/may_run_shadow_mode_now",
        "/shadow_execution_contract/may_expand_candidate_set_now",
        "/shadow_execution_contract/changes_candidate_set_now",
        "/shadow_execution_contract/runtime_influence_approved",
        "/shadow_execution_contract/may_change_search_order_now",
        "/shadow_execution_contract/may_write_memory_or_graph_edges",
        "/shadow_execution_contract/calls_memory_search",
        "/shadow_execution_contract/calls_memory_neighbors",
        "/shadow_execution_contract/runs_biocortex",
        "/shadow_execution_contract/candidate_expansion_experiment_approved",
        "/telemetry/writes_memory",
        "/telemetry/writes_graph_edges",
    ]
    .iter()
    .any(|pointer| {
        memory_biocortex_t6_candidate_expansion_shadow_execution_gate_bool_at(report, pointer)
    })
}

pub(super) fn memory_biocortex_t6_candidate_expansion_shadow_execution_gate_source_requirements_complete(
    report: &Value,
) -> bool {
    memory_biocortex_t6_candidate_expansion_shadow_execution_gate_bool_at(
        report,
        "/runtime_gate/runtime_enabled",
    ) && !memory_biocortex_t6_candidate_expansion_shadow_execution_gate_bool_at(
        report,
        "/runtime_gate/operator_disabled",
    ) && memory_biocortex_t6_candidate_expansion_shadow_execution_gate_bool_at(
        report,
        "/runtime_gate/requires_separate_shadow_execution_gate",
    ) && memory_biocortex_t6_candidate_expansion_shadow_execution_gate_bool_at(
        report,
        "/candidate_delta/bounded_candidate_delta",
    ) && memory_biocortex_t6_candidate_expansion_shadow_execution_gate_bool_at(
        report,
        "/candidate_delta/within_bound",
    ) && !memory_biocortex_t6_candidate_expansion_shadow_execution_gate_bool_at(
        report,
        "/candidate_delta/raw_keys_included",
    ) && !memory_biocortex_t6_candidate_expansion_shadow_execution_gate_bool_at(
        report,
        "/candidate_delta/content_included",
    ) && memory_biocortex_t6_candidate_expansion_shadow_execution_gate_bool_at(
        report,
        "/deterministic_replay_fixture/present",
    ) && memory_biocortex_t6_candidate_expansion_shadow_execution_gate_bool_at(
        report,
        "/deterministic_replay_fixture/uses_redacted_fixture_ids_only",
    ) && memory_biocortex_t6_candidate_expansion_shadow_execution_gate_u64_at(
        report,
        "/negative_controls/negative_control_regression_count",
    ) == 0
        && memory_biocortex_t6_candidate_expansion_shadow_execution_gate_bool_at(
            report,
            "/rollback_contract/present",
        )
        && !memory_biocortex_t6_candidate_expansion_shadow_execution_gate_bool_at(
            report,
            "/input_contract/raw_query_included",
        )
        && !memory_biocortex_t6_candidate_expansion_shadow_execution_gate_bool_at(
            report,
            "/input_contract/raw_queries_included",
        )
        && !memory_biocortex_t6_candidate_expansion_shadow_execution_gate_bool_at(
            report,
            "/input_contract/raw_keys_included",
        )
        && !memory_biocortex_t6_candidate_expansion_shadow_execution_gate_bool_at(
            report,
            "/input_contract/content_included",
        )
        && !memory_biocortex_t6_candidate_expansion_shadow_execution_gate_bool_at(
            report,
            "/input_contract/case_rows_included",
        )
        && !memory_biocortex_t6_candidate_expansion_shadow_execution_gate_bool_at(
            report,
            "/input_contract/source_artifacts_echoed",
        )
        && !memory_biocortex_t6_candidate_expansion_shadow_execution_gate_bool_at(
            report,
            "/telemetry/raw_query_included",
        )
        && !memory_biocortex_t6_candidate_expansion_shadow_execution_gate_bool_at(
            report,
            "/telemetry/raw_keys_included",
        )
        && !memory_biocortex_t6_candidate_expansion_shadow_execution_gate_bool_at(
            report,
            "/telemetry/content_included",
        )
}

pub(super) fn memory_biocortex_t6_candidate_expansion_shadow_execution_gate_payload(args: Value) -> Value {
    let report = args
        .get("shadow_runtime_gate_report")
        .cloned()
        .unwrap_or(Value::Null);
    let reviewer =
        memory_biocortex_t6_candidate_expansion_shadow_execution_gate_string(&args, "reviewer");
    let decision = memory_biocortex_t6_candidate_expansion_shadow_execution_gate_string(
        &args,
        "shadow_execution_decision",
    );
    let decision_source = memory_biocortex_t6_candidate_expansion_shadow_execution_gate_string(
        &args,
        "decision_source",
    );
    let replay_fixture_id = memory_biocortex_t6_candidate_expansion_shadow_execution_gate_string(
        &args,
        "replay_fixture_id",
    );
    let telemetry_sink =
        memory_biocortex_t6_candidate_expansion_shadow_execution_gate_string(&args, "telemetry_sink");

    let source_schema = report
        .get("schema")
        .and_then(Value::as_str)
        .unwrap_or("")
        .to_string();
    let source_runtime_gate_status = report
        .pointer("/runtime_gate/status")
        .and_then(Value::as_str)
        .unwrap_or("missing")
        .to_string();
    let source_block_reasons = report
        .pointer("/runtime_gate/block_reasons")
        .and_then(Value::as_array)
        .cloned()
        .unwrap_or_default();

    let mut block_reasons = BTreeSet::<String>::new();
    if source_schema != MEMORY_BIOCORTEX_T6_CANDIDATE_EXPANSION_SHADOW_RUNTIME_GATE_SCHEMA {
        block_reasons.insert("source_shadow_runtime_gate_schema_mismatch".to_string());
    }
    if source_runtime_gate_status != "blocked_before_shadow_execution_gate" {
        block_reasons.insert("source_shadow_runtime_gate_not_ready".to_string());
    }
    if !report
        .get("read_only")
        .and_then(Value::as_bool)
        .unwrap_or(false)
    {
        block_reasons.insert("source_shadow_runtime_gate_not_read_only".to_string());
    }
    if memory_biocortex_t6_candidate_expansion_shadow_execution_gate_contains_raw(&report) {
        block_reasons.insert("source_shadow_runtime_gate_contains_raw".to_string());
    }
    if memory_biocortex_t6_candidate_expansion_shadow_execution_gate_contains_raw(&args) {
        block_reasons.insert("input_contains_raw_or_source_fields".to_string());
    }
    if memory_biocortex_t6_candidate_expansion_shadow_execution_gate_source_claims_runtime_authority(&report) {
        block_reasons.insert("source_shadow_runtime_gate_claims_runtime_authority".to_string());
    }
    if !memory_biocortex_t6_candidate_expansion_shadow_execution_gate_source_requirements_complete(
        &report,
    ) {
        block_reasons.insert("source_shadow_runtime_gate_requirements_incomplete".to_string());
    }
    if decision != "approve_shadow_execution_only" {
        block_reasons.insert("invalid_shadow_execution_decision".to_string());
    }
    if reviewer.is_empty() {
        block_reasons.insert("reviewer_missing".to_string());
    }
    if decision_source.is_empty() {
        block_reasons.insert("decision_source_missing".to_string());
    }
    if replay_fixture_id.is_empty() {
        block_reasons.insert("replay_fixture_id_missing".to_string());
    }
    if telemetry_sink.is_empty() {
        block_reasons.insert("telemetry_sink_missing".to_string());
    }

    let block_reasons: Vec<String> = block_reasons.into_iter().collect();
    let ready = block_reasons.is_empty();
    let status = if ready {
        "ready_for_shadow_execution_only"
    } else {
        "blocked_before_shadow_execution"
    };

    json!({
        "schema": MEMORY_BIOCORTEX_T6_CANDIDATE_EXPANSION_SHADOW_EXECUTION_GATE_SCHEMA,
        "generated_at": unix_now_secs(),
        "read_only": true,
        "shadow_execution_gate": {
            "ready": ready,
            "status": status,
            "source_runtime_gate_schema": source_schema,
            "source_runtime_gate_status": source_runtime_gate_status,
            "source_runtime_gate_block_reasons": source_block_reasons,
            "decision": {
                "reviewer_present": !reviewer.is_empty(),
                "shadow_execution_decision": if decision.is_empty() {
                    Value::Null
                } else {
                    json!(decision)
                },
                "decision_source_present": !decision_source.is_empty(),
            },
            "block_reasons": block_reasons,
        },
        "shadow_execution_contract": {
            "may_run_shadow_executor_now": ready,
            "this_tool_runs_shadow_mode": false,
            "this_tool_calls_memory_search": false,
            "this_tool_calls_memory_neighbors": false,
            "this_tool_runs_biocortex": false,
            "may_expand_runtime_candidate_set_now": false,
            "changes_runtime_candidate_set_now": false,
            "may_change_runtime_search_order_now": false,
            "runtime_influence_approved": false,
            "may_enable_runtime_gate_now": false,
            "may_write_memory_or_graph_edges": false,
            "requires_later_runtime_enablement_gate": true,
            "requires_later_candidate_expansion_enablement_gate": true,
        },
        "shadow_run_bounds": {
            "requires_redacted_replay_fixture": true,
            "replay_fixture_id_present": !replay_fixture_id.is_empty(),
            "requires_append_only_telemetry": true,
            "telemetry_sink_present": !telemetry_sink.is_empty(),
            "raw_queries_allowed": false,
            "raw_keys_allowed": false,
            "content_allowed": false,
            "case_rows_allowed": false,
        },
        "input_contract": {
            "shadow_runtime_gate_report_included": false,
            "raw_query_included": false,
            "raw_queries_included": false,
            "raw_keys_included": false,
            "content_included": false,
            "case_rows_included": false,
            "unknown_fields_ignored": true,
        },
        "non_goals": [
            "This tool does not run shadow mode; it only records whether an author-reviewed shadow-only executor gate is open.",
            "This tool does not approve production runtime influence, candidate-set expansion, search-order changes, memory writes, or graph-edge writes.",
            "This tool does not echo the source shadow-runtime-gate report or raw query/key/content/case rows.",
            "A later runtime enablement gate is still required before any production candidate expansion can influence retrieval."
        ],
    })
}

pub struct MemoryBioCortexT6CandidateExpansionShadowExecutionGateTool;
impl MemoryBioCortexT6CandidateExpansionShadowExecutionGateTool {
    pub fn new() -> Self {
        Self
    }
}

impl Default for MemoryBioCortexT6CandidateExpansionShadowExecutionGateTool {
    fn default() -> Self {
        Self::new()
    }
}

#[async_trait]
impl McpTool for MemoryBioCortexT6CandidateExpansionShadowExecutionGateTool {
    fn name(&self) -> &'static str {
        "memory_biocortex_t6_candidate_expansion_shadow_execution_gate"
    }

    fn schema(&self) -> ToolSchema {
        ToolSchema {
            name: self.name().into(),
            description: "Read-only T6 candidate-expansion author-review gate \
                for a later shadow-only executor. It consumes the redacted \
                shadow runtime gate report plus an explicit reviewer decision, \
                but never runs shadow mode, BioCortex, memory_search, \
                memory_neighbors, writes, runtime influence, production \
                candidate expansion, or search-order changes."
                .into(),
            input_schema: json!({
                "type": "object",
                "required": [
                    "shadow_runtime_gate_report",
                    "reviewer",
                    "shadow_execution_decision",
                    "decision_source",
                    "replay_fixture_id",
                    "telemetry_sink"
                ],
                "properties": {
                    "shadow_runtime_gate_report": {
                        "type": "object",
                        "description": "JSON object produced by memory_biocortex_t6_candidate_expansion_shadow_runtime_gate. It is inspected for redacted counts/flags only and is never echoed."
                    },
                    "reviewer": {
                        "type": "string",
                        "description": "Reviewer identity authorizing the shadow-only execution gate."
                    },
                    "shadow_execution_decision": {
                        "type": "string",
                        "enum": [
                            "approve_shadow_execution_only",
                            "request_shadow_execution_changes",
                            "reject_shadow_execution"
                        ],
                        "description": "Only approve_shadow_execution_only can open the shadow-only executor gate; no value approves production runtime influence."
                    },
                    "decision_source": {
                        "type": "string",
                        "description": "External source for the author decision, such as forum post id or review checkpoint."
                    },
                    "replay_fixture_id": {
                        "type": "string",
                        "description": "Redacted deterministic replay fixture id. Raw cases must not be supplied."
                    },
                    "telemetry_sink": {
                        "type": "string",
                        "description": "Append-only shadow telemetry sink identifier; this tool does not write telemetry."
                    }
                }
            }),
        }
    }

    async fn execute(&self, args: Value, _ctx: &ToolContext) -> Result<ToolResult> {
        Ok(ToolResult::json_text(
            &memory_biocortex_t6_candidate_expansion_shadow_execution_gate_payload(args),
        ))
    }
}

pub(super) const MEMORY_BIOCORTEX_T6_CANDIDATE_EXPANSION_SHADOW_EXECUTOR_PREFLIGHT_SCHEMA: &str =
    "agent_bridge.memory_biocortex_t6_candidate_expansion.shadow_executor_preflight.v0";

pub(super) fn memory_biocortex_t6_candidate_expansion_shadow_executor_preflight_u64(
    args: &Value,
    key: &str,
    default: u64,
) -> u64 {
    args.get(key).and_then(Value::as_u64).unwrap_or(default)
}

pub(super) fn memory_biocortex_t6_candidate_expansion_shadow_executor_preflight_source_claims_runtime_authority(
    report: &Value,
) -> bool {
    [
        "/shadow_execution_contract/this_tool_runs_shadow_mode",
        "/shadow_execution_contract/this_tool_calls_memory_search",
        "/shadow_execution_contract/this_tool_calls_memory_neighbors",
        "/shadow_execution_contract/this_tool_runs_biocortex",
        "/shadow_execution_contract/may_expand_runtime_candidate_set_now",
        "/shadow_execution_contract/changes_runtime_candidate_set_now",
        "/shadow_execution_contract/may_change_runtime_search_order_now",
        "/shadow_execution_contract/runtime_influence_approved",
        "/shadow_execution_contract/may_enable_runtime_gate_now",
        "/shadow_execution_contract/may_write_memory_or_graph_edges",
        "/shadow_run_bounds/raw_queries_allowed",
        "/shadow_run_bounds/raw_keys_allowed",
        "/shadow_run_bounds/content_allowed",
        "/shadow_run_bounds/case_rows_allowed",
    ]
    .iter()
    .any(|pointer| {
        memory_biocortex_t6_candidate_expansion_shadow_execution_gate_bool_at(report, pointer)
    })
}

pub(super) fn memory_biocortex_t6_candidate_expansion_shadow_executor_preflight_source_ready(
    report: &Value,
) -> bool {
    report.get("schema").and_then(Value::as_str)
        == Some(MEMORY_BIOCORTEX_T6_CANDIDATE_EXPANSION_SHADOW_EXECUTION_GATE_SCHEMA)
        && report.get("read_only").and_then(Value::as_bool) == Some(true)
        && memory_biocortex_t6_candidate_expansion_shadow_execution_gate_bool_at(
            report,
            "/shadow_execution_gate/ready",
        )
        && report
            .pointer("/shadow_execution_gate/status")
            .and_then(Value::as_str)
            == Some("ready_for_shadow_execution_only")
        && memory_biocortex_t6_candidate_expansion_shadow_execution_gate_bool_at(
            report,
            "/shadow_execution_contract/may_run_shadow_executor_now",
        )
        && !memory_biocortex_t6_candidate_expansion_shadow_executor_preflight_source_claims_runtime_authority(report)
        && memory_biocortex_t6_candidate_expansion_shadow_execution_gate_bool_at(
            report,
            "/shadow_run_bounds/replay_fixture_id_present",
        )
        && memory_biocortex_t6_candidate_expansion_shadow_execution_gate_bool_at(
            report,
            "/shadow_run_bounds/telemetry_sink_present",
        )
        && !memory_biocortex_t6_candidate_expansion_shadow_execution_gate_bool_at(
            report,
            "/input_contract/shadow_runtime_gate_report_included",
        )
        && !memory_biocortex_t6_candidate_expansion_shadow_execution_gate_bool_at(
            report,
            "/input_contract/raw_query_included",
        )
        && !memory_biocortex_t6_candidate_expansion_shadow_execution_gate_bool_at(
            report,
            "/input_contract/raw_queries_included",
        )
        && !memory_biocortex_t6_candidate_expansion_shadow_execution_gate_bool_at(
            report,
            "/input_contract/raw_keys_included",
        )
        && !memory_biocortex_t6_candidate_expansion_shadow_execution_gate_bool_at(
            report,
            "/input_contract/content_included",
        )
        && !memory_biocortex_t6_candidate_expansion_shadow_execution_gate_bool_at(
            report,
            "/input_contract/case_rows_included",
        )
}

pub(super) fn memory_biocortex_t6_candidate_expansion_shadow_executor_preflight_payload(args: Value) -> Value {
    let report = args
        .get("shadow_execution_gate_report")
        .cloned()
        .unwrap_or(Value::Null);
    let executor_id =
        memory_biocortex_t6_candidate_expansion_shadow_execution_gate_string(&args, "executor_id");
    let replay_fixture_id = memory_biocortex_t6_candidate_expansion_shadow_execution_gate_string(
        &args,
        "replay_fixture_id",
    );
    let telemetry_sink =
        memory_biocortex_t6_candidate_expansion_shadow_execution_gate_string(&args, "telemetry_sink");
    let max_shadow_cases =
        memory_biocortex_t6_candidate_expansion_shadow_executor_preflight_u64(
            &args,
            "max_shadow_cases",
            0,
        );
    let max_shadow_case_bound = 100_u64;

    let mut block_reasons = BTreeSet::<String>::new();
    if !memory_biocortex_t6_candidate_expansion_shadow_executor_preflight_source_ready(&report) {
        block_reasons.insert("source_shadow_execution_gate_not_ready".to_string());
    }
    if memory_biocortex_t6_candidate_expansion_shadow_execution_gate_contains_raw(&report) {
        block_reasons.insert("source_shadow_execution_gate_contains_raw".to_string());
    }
    if memory_biocortex_t6_candidate_expansion_shadow_execution_gate_contains_raw(&args) {
        block_reasons.insert("input_contains_raw_or_source_fields".to_string());
    }
    if memory_biocortex_t6_candidate_expansion_shadow_executor_preflight_source_claims_runtime_authority(&report) {
        block_reasons.insert("source_shadow_execution_gate_claims_runtime_authority".to_string());
    }
    if executor_id.is_empty() {
        block_reasons.insert("executor_id_missing".to_string());
    }
    if replay_fixture_id.is_empty() {
        block_reasons.insert("replay_fixture_id_missing".to_string());
    }
    if telemetry_sink.is_empty() {
        block_reasons.insert("telemetry_sink_missing".to_string());
    }
    if max_shadow_cases == 0 {
        block_reasons.insert("max_shadow_cases_missing".to_string());
    }
    if max_shadow_cases > max_shadow_case_bound {
        block_reasons.insert("max_shadow_cases_exceeds_bound".to_string());
    }

    let block_reasons: Vec<String> = block_reasons.into_iter().collect();
    let ready = block_reasons.is_empty();
    let status = if ready {
        "ready_for_shadow_only_executor_invocation"
    } else {
        "blocked_before_shadow_only_executor_invocation"
    };

    json!({
        "schema": MEMORY_BIOCORTEX_T6_CANDIDATE_EXPANSION_SHADOW_EXECUTOR_PREFLIGHT_SCHEMA,
        "generated_at": unix_now_secs(),
        "read_only": true,
        "shadow_executor_preflight": {
            "ready": ready,
            "status": status,
            "block_reasons": block_reasons,
            "executor_id_present": !executor_id.is_empty(),
            "replay_fixture_id_present": !replay_fixture_id.is_empty(),
            "telemetry_sink_present": !telemetry_sink.is_empty(),
            "max_shadow_cases": max_shadow_cases,
            "max_shadow_case_bound": max_shadow_case_bound,
        },
        "shadow_executor_contract": {
            "may_invoke_shadow_only_executor_now": ready,
            "this_tool_invokes_executor": false,
            "this_tool_runs_shadow_mode": false,
            "this_tool_calls_memory_search": false,
            "this_tool_calls_memory_neighbors": false,
            "this_tool_runs_biocortex": false,
            "may_mutate_runtime_candidate_set": false,
            "changes_runtime_candidate_set": false,
            "may_change_runtime_search_order": false,
            "runtime_influence_approved": false,
            "may_enable_runtime_gate_now": false,
            "may_write_memory_or_graph_edges": false,
            "requires_later_runtime_enablement_gate": true,
            "requires_later_candidate_expansion_enablement_gate": true,
        },
        "bounded_invocation": {
            "redacted_replay_fixture_required": true,
            "append_only_telemetry_required": true,
            "max_shadow_cases": max_shadow_cases,
            "max_shadow_case_bound": max_shadow_case_bound,
            "raw_queries_allowed": false,
            "raw_keys_allowed": false,
            "content_allowed": false,
            "case_rows_allowed": false,
        },
        "input_contract": {
            "shadow_execution_gate_report_included": false,
            "raw_query_included": false,
            "raw_queries_included": false,
            "raw_keys_included": false,
            "content_included": false,
            "case_rows_included": false,
            "unknown_fields_ignored": true,
        },
        "non_goals": [
            "This tool does not invoke a shadow executor or run shadow mode.",
            "This tool does not call BioCortex, memory_search, or memory_neighbors.",
            "This tool does not mutate runtime candidate sets, search order, memory, graph edges, feature flags, approvals, or telemetry.",
            "This tool does not approve production runtime influence or runtime enablement."
        ],
    })
}

pub struct MemoryBioCortexT6CandidateExpansionShadowExecutorPreflightTool;
impl MemoryBioCortexT6CandidateExpansionShadowExecutorPreflightTool {
    pub fn new() -> Self {
        Self
    }
}

impl Default for MemoryBioCortexT6CandidateExpansionShadowExecutorPreflightTool {
    fn default() -> Self {
        Self::new()
    }
}

#[async_trait]
impl McpTool for MemoryBioCortexT6CandidateExpansionShadowExecutorPreflightTool {
    fn name(&self) -> &'static str {
        "memory_biocortex_t6_candidate_expansion_shadow_executor_preflight"
    }

    fn schema(&self) -> ToolSchema {
        ToolSchema {
            name: self.name().into(),
            description: "Read-only T6 candidate-expansion shadow executor preflight. \
                Consumes a safe shadow execution gate report and bounded fixture \
                invocation metadata, then reports whether a later shadow-only \
                executor may be invoked. It never invokes the executor, runs \
                shadow mode, calls BioCortex or memory tools, writes, mutates \
                runtime candidates, changes search order, or approves runtime \
                influence."
                .into(),
            input_schema: json!({
                "type": "object",
                "required": [
                    "shadow_execution_gate_report",
                    "executor_id",
                    "replay_fixture_id",
                    "telemetry_sink",
                    "max_shadow_cases"
                ],
                "properties": {
                    "shadow_execution_gate_report": {
                        "type": "object",
                        "description": "JSON object produced by memory_biocortex_t6_candidate_expansion_shadow_execution_gate. It is inspected but never echoed."
                    },
                    "executor_id": {
                        "type": "string",
                        "description": "Identifier for the later shadow-only executor. This tool does not invoke it."
                    },
                    "replay_fixture_id": {
                        "type": "string",
                        "description": "Redacted deterministic replay fixture id. Raw cases must not be supplied."
                    },
                    "telemetry_sink": {
                        "type": "string",
                        "description": "Append-only telemetry sink identifier. This tool does not write telemetry."
                    },
                    "max_shadow_cases": {
                        "type": "integer",
                        "minimum": 1,
                        "maximum": 100,
                        "default": 25,
                        "description": "Upper bound for a later shadow-only invocation."
                    }
                }
            }),
        }
    }

    async fn execute(&self, args: Value, _ctx: &ToolContext) -> Result<ToolResult> {
        Ok(ToolResult::json_text(
            &memory_biocortex_t6_candidate_expansion_shadow_executor_preflight_payload(args),
        ))
    }
}

pub(super) const MEMORY_BIOCORTEX_T6_CANDIDATE_EXPANSION_SHADOW_EXECUTOR_INVOCATION_REPORT_SCHEMA: &str =
    "agent_bridge.memory_biocortex_t6_candidate_expansion.shadow_executor_invocation_report.v0";

pub(super) fn memory_biocortex_t6_candidate_expansion_shadow_executor_invocation_report_bool(
    args: &Value,
    key: &str,
    default: bool,
) -> bool {
    args.get(key).and_then(Value::as_bool).unwrap_or(default)
}

pub(super) fn memory_biocortex_t6_candidate_expansion_shadow_executor_invocation_report_source_claims_runtime_authority(
    report: &Value,
) -> bool {
    [
        "/shadow_executor_contract/this_tool_invokes_executor",
        "/shadow_executor_contract/this_tool_runs_shadow_mode",
        "/shadow_executor_contract/this_tool_calls_memory_search",
        "/shadow_executor_contract/this_tool_calls_memory_neighbors",
        "/shadow_executor_contract/this_tool_runs_biocortex",
        "/shadow_executor_contract/may_mutate_runtime_candidate_set",
        "/shadow_executor_contract/changes_runtime_candidate_set",
        "/shadow_executor_contract/may_change_runtime_search_order",
        "/shadow_executor_contract/runtime_influence_approved",
        "/shadow_executor_contract/may_enable_runtime_gate_now",
        "/shadow_executor_contract/may_write_memory_or_graph_edges",
        "/bounded_invocation/raw_queries_allowed",
        "/bounded_invocation/raw_keys_allowed",
        "/bounded_invocation/content_allowed",
        "/bounded_invocation/case_rows_allowed",
    ]
    .iter()
    .any(|pointer| {
        memory_biocortex_t6_candidate_expansion_shadow_execution_gate_bool_at(report, pointer)
    })
}

pub(super) fn memory_biocortex_t6_candidate_expansion_shadow_executor_invocation_report_source_ready(
    report: &Value,
) -> bool {
    report.get("schema").and_then(Value::as_str)
        == Some(MEMORY_BIOCORTEX_T6_CANDIDATE_EXPANSION_SHADOW_EXECUTOR_PREFLIGHT_SCHEMA)
        && report.get("read_only").and_then(Value::as_bool) == Some(true)
        && memory_biocortex_t6_candidate_expansion_shadow_execution_gate_bool_at(
            report,
            "/shadow_executor_preflight/ready",
        )
        && report
            .pointer("/shadow_executor_preflight/status")
            .and_then(Value::as_str)
            == Some("ready_for_shadow_only_executor_invocation")
        && memory_biocortex_t6_candidate_expansion_shadow_execution_gate_bool_at(
            report,
            "/shadow_executor_contract/may_invoke_shadow_only_executor_now",
        )
        && !memory_biocortex_t6_candidate_expansion_shadow_executor_invocation_report_source_claims_runtime_authority(report)
        && !memory_biocortex_t6_candidate_expansion_shadow_execution_gate_bool_at(
            report,
            "/input_contract/shadow_execution_gate_report_included",
        )
        && !memory_biocortex_t6_candidate_expansion_shadow_execution_gate_bool_at(
            report,
            "/input_contract/raw_query_included",
        )
        && !memory_biocortex_t6_candidate_expansion_shadow_execution_gate_bool_at(
            report,
            "/input_contract/raw_queries_included",
        )
        && !memory_biocortex_t6_candidate_expansion_shadow_execution_gate_bool_at(
            report,
            "/input_contract/raw_keys_included",
        )
        && !memory_biocortex_t6_candidate_expansion_shadow_execution_gate_bool_at(
            report,
            "/input_contract/content_included",
        )
        && !memory_biocortex_t6_candidate_expansion_shadow_execution_gate_bool_at(
            report,
            "/input_contract/case_rows_included",
        )
}

pub(super) fn memory_biocortex_t6_candidate_expansion_shadow_executor_invocation_report_payload(
    args: Value,
) -> Value {
    let report = args
        .get("shadow_executor_preflight_report")
        .cloned()
        .unwrap_or(Value::Null);
    let executor_id =
        memory_biocortex_t6_candidate_expansion_shadow_execution_gate_string(&args, "executor_id");
    let executor_run_id = memory_biocortex_t6_candidate_expansion_shadow_execution_gate_string(
        &args,
        "executor_run_id",
    );
    let replay_fixture_id = memory_biocortex_t6_candidate_expansion_shadow_execution_gate_string(
        &args,
        "replay_fixture_id",
    );
    let telemetry_sink =
        memory_biocortex_t6_candidate_expansion_shadow_execution_gate_string(&args, "telemetry_sink");
    let shadow_case_count =
        memory_biocortex_t6_candidate_expansion_shadow_executor_preflight_u64(
            &args,
            "shadow_case_count",
            0,
        );
    let completed_case_count =
        memory_biocortex_t6_candidate_expansion_shadow_executor_preflight_u64(
            &args,
            "completed_case_count",
            0,
        );
    let failed_case_count =
        memory_biocortex_t6_candidate_expansion_shadow_executor_preflight_u64(
            &args,
            "failed_case_count",
            0,
        );
    let candidate_delta_count =
        memory_biocortex_t6_candidate_expansion_shadow_executor_preflight_u64(
            &args,
            "candidate_delta_count",
            0,
        );
    let negative_control_regression_count =
        memory_biocortex_t6_candidate_expansion_shadow_executor_preflight_u64(
            &args,
            "negative_control_regression_count",
            0,
        );
    let append_only_telemetry_written =
        memory_biocortex_t6_candidate_expansion_shadow_executor_invocation_report_bool(
            &args,
            "append_only_telemetry_written",
            false,
        );
    let redacted_summary_only =
        memory_biocortex_t6_candidate_expansion_shadow_executor_invocation_report_bool(
            &args,
            "redacted_summary_only",
            false,
        );
    let source_max_shadow_cases =
        memory_biocortex_t6_candidate_expansion_shadow_execution_gate_u64_at(
            &report,
            "/shadow_executor_preflight/max_shadow_cases",
        );
    let max_shadow_case_bound = if source_max_shadow_cases == 0 {
        100
    } else {
        source_max_shadow_cases.min(100)
    };
    let completed_plus_failed = completed_case_count.saturating_add(failed_case_count);

    let mut block_reasons = BTreeSet::<String>::new();
    if !memory_biocortex_t6_candidate_expansion_shadow_executor_invocation_report_source_ready(
        &report,
    ) {
        block_reasons.insert("source_shadow_executor_preflight_not_ready".to_string());
    }
    if memory_biocortex_t6_candidate_expansion_shadow_execution_gate_contains_raw(&report) {
        block_reasons.insert("source_shadow_executor_preflight_contains_raw".to_string());
    }
    if memory_biocortex_t6_candidate_expansion_shadow_execution_gate_contains_raw(&args) {
        block_reasons.insert("input_contains_raw_or_source_fields".to_string());
    }
    if memory_biocortex_t6_candidate_expansion_shadow_executor_invocation_report_source_claims_runtime_authority(&report) {
        block_reasons.insert("source_shadow_executor_preflight_claims_runtime_authority".to_string());
    }
    if executor_id.is_empty() {
        block_reasons.insert("executor_id_missing".to_string());
    }
    if executor_run_id.is_empty() {
        block_reasons.insert("executor_run_id_missing".to_string());
    }
    if replay_fixture_id.is_empty() {
        block_reasons.insert("replay_fixture_id_missing".to_string());
    }
    if telemetry_sink.is_empty() {
        block_reasons.insert("telemetry_sink_missing".to_string());
    }
    if shadow_case_count == 0 {
        block_reasons.insert("shadow_case_count_missing".to_string());
    }
    if shadow_case_count > max_shadow_case_bound {
        block_reasons.insert("shadow_case_count_exceeds_bound".to_string());
    }
    if completed_plus_failed != shadow_case_count {
        block_reasons.insert("case_counts_mismatch".to_string());
    }
    if candidate_delta_count > shadow_case_count {
        block_reasons.insert("candidate_delta_exceeds_shadow_cases".to_string());
    }
    if failed_case_count > 0 {
        block_reasons.insert("shadow_executor_failures_present".to_string());
    }
    if negative_control_regression_count > 0 {
        block_reasons.insert("negative_control_regression_detected".to_string());
    }
    if !append_only_telemetry_written {
        block_reasons.insert("append_only_telemetry_missing".to_string());
    }
    if !redacted_summary_only {
        block_reasons.insert("redacted_summary_only_missing".to_string());
    }

    let block_reasons: Vec<String> = block_reasons.into_iter().collect();
    let ready = block_reasons.is_empty();
    let status = if ready {
        "ready_for_shadow_telemetry_review"
    } else {
        "blocked_shadow_executor_invocation_report"
    };

    json!({
        "schema": MEMORY_BIOCORTEX_T6_CANDIDATE_EXPANSION_SHADOW_EXECUTOR_INVOCATION_REPORT_SCHEMA,
        "generated_at": unix_now_secs(),
        "read_only": true,
        "shadow_executor_invocation_report": {
            "ready": ready,
            "status": status,
            "block_reasons": block_reasons,
            "executor_id_present": !executor_id.is_empty(),
            "executor_run_id_present": !executor_run_id.is_empty(),
            "replay_fixture_id_present": !replay_fixture_id.is_empty(),
            "telemetry_sink_present": !telemetry_sink.is_empty(),
            "shadow_case_count": shadow_case_count,
            "completed_case_count": completed_case_count,
            "failed_case_count": failed_case_count,
            "candidate_delta_count": candidate_delta_count,
            "negative_control_regression_count": negative_control_regression_count,
            "max_shadow_case_bound": max_shadow_case_bound,
            "case_counts_match": completed_plus_failed == shadow_case_count,
            "append_only_telemetry_written": append_only_telemetry_written,
            "redacted_summary_only": redacted_summary_only,
        },
        "shadow_invocation_contract": {
            "may_review_shadow_telemetry_now": ready,
            "this_tool_invokes_executor": false,
            "this_tool_runs_shadow_mode": false,
            "this_tool_calls_memory_search": false,
            "this_tool_calls_memory_neighbors": false,
            "this_tool_runs_biocortex": false,
            "may_mutate_runtime_candidate_set": false,
            "changes_runtime_candidate_set": false,
            "may_change_runtime_search_order": false,
            "runtime_influence_approved": false,
            "may_enable_runtime_gate_now": false,
            "may_write_memory_or_graph_edges": false,
            "may_approve_production_candidate_expansion_now": false,
            "requires_later_shadow_telemetry_review": true,
            "requires_later_runtime_enablement_gate": true,
            "requires_later_candidate_expansion_enablement_gate": true,
        },
        "bounded_shadow_telemetry": {
            "redacted_replay_fixture_required": true,
            "append_only_telemetry_required": true,
            "append_only_telemetry_written": append_only_telemetry_written,
            "redacted_summary_only": redacted_summary_only,
            "max_shadow_case_bound": max_shadow_case_bound,
            "raw_queries_allowed": false,
            "raw_keys_allowed": false,
            "content_allowed": false,
            "case_rows_allowed": false,
        },
        "input_contract": {
            "shadow_executor_preflight_report_included": false,
            "raw_query_included": false,
            "raw_queries_included": false,
            "raw_keys_included": false,
            "content_included": false,
            "case_rows_included": false,
            "unknown_fields_ignored": true,
        },
        "non_goals": [
            "This tool does not invoke a shadow executor or run shadow mode.",
            "This tool validates a redacted invocation summary only; it does not consume raw queries, raw keys, content, or case rows.",
            "This tool does not call BioCortex, memory_search, or memory_neighbors.",
            "This tool does not mutate runtime candidate sets, search order, memory, graph edges, feature flags, approvals, or telemetry.",
            "This tool does not approve production runtime influence or runtime enablement."
        ],
    })
}

pub struct MemoryBioCortexT6CandidateExpansionShadowExecutorInvocationReportTool;
impl MemoryBioCortexT6CandidateExpansionShadowExecutorInvocationReportTool {
    pub fn new() -> Self {
        Self
    }
}

impl Default for MemoryBioCortexT6CandidateExpansionShadowExecutorInvocationReportTool {
    fn default() -> Self {
        Self::new()
    }
}

#[async_trait]
impl McpTool for MemoryBioCortexT6CandidateExpansionShadowExecutorInvocationReportTool {
    fn name(&self) -> &'static str {
        "memory_biocortex_t6_candidate_expansion_shadow_executor_invocation_report"
    }

    fn schema(&self) -> ToolSchema {
        ToolSchema {
            name: self.name().into(),
            description: "Read-only T6 candidate-expansion shadow executor invocation report. \
                Consumes a safe shadow executor preflight report plus redacted, bounded \
                invocation-summary counts. It does not invoke the executor, run shadow \
                mode, call BioCortex or memory tools, write telemetry, mutate runtime \
                candidates, change search order, or approve runtime influence."
                .into(),
            input_schema: json!({
                "type": "object",
                "required": [
                    "shadow_executor_preflight_report",
                    "executor_id",
                    "executor_run_id",
                    "replay_fixture_id",
                    "telemetry_sink",
                    "shadow_case_count",
                    "completed_case_count",
                    "failed_case_count",
                    "candidate_delta_count",
                    "negative_control_regression_count",
                    "append_only_telemetry_written",
                    "redacted_summary_only"
                ],
                "properties": {
                    "shadow_executor_preflight_report": {
                        "type": "object",
                        "description": "JSON object produced by memory_biocortex_t6_candidate_expansion_shadow_executor_preflight. It is inspected but never echoed."
                    },
                    "executor_id": {
                        "type": "string",
                        "description": "Redacted shadow-only executor identifier."
                    },
                    "executor_run_id": {
                        "type": "string",
                        "description": "Redacted shadow-only run identifier; raw case ids must not be supplied."
                    },
                    "replay_fixture_id": {
                        "type": "string",
                        "description": "Redacted deterministic replay fixture id. Raw cases must not be supplied."
                    },
                    "telemetry_sink": {
                        "type": "string",
                        "description": "Append-only telemetry sink identifier. This tool does not write telemetry."
                    },
                    "shadow_case_count": {
                        "type": "integer",
                        "minimum": 1,
                        "maximum": 100,
                        "description": "Bounded count of redacted fixture cases summarized by the report."
                    },
                    "completed_case_count": {
                        "type": "integer",
                        "minimum": 0,
                        "maximum": 100,
                        "description": "Count of summarized cases that completed in the external shadow-only invocation."
                    },
                    "failed_case_count": {
                        "type": "integer",
                        "minimum": 0,
                        "maximum": 100,
                        "description": "Count of summarized cases that failed in the external shadow-only invocation."
                    },
                    "candidate_delta_count": {
                        "type": "integer",
                        "minimum": 0,
                        "maximum": 100,
                        "description": "Redacted count of hypothetical candidate-set differences. No keys or content allowed."
                    },
                    "negative_control_regression_count": {
                        "type": "integer",
                        "minimum": 0,
                        "maximum": 100,
                        "description": "Count only; any negative-control regression blocks telemetry review."
                    },
                    "append_only_telemetry_written": {
                        "type": "boolean",
                        "default": false,
                        "description": "Whether the external invocation wrote append-only shadow telemetry."
                    },
                    "redacted_summary_only": {
                        "type": "boolean",
                        "default": false,
                        "description": "Must be true to confirm no raw queries, keys, content, or case rows were supplied."
                    }
                }
            }),
        }
    }

    async fn execute(&self, args: Value, _ctx: &ToolContext) -> Result<ToolResult> {
        Ok(ToolResult::json_text(
            &memory_biocortex_t6_candidate_expansion_shadow_executor_invocation_report_payload(
                args,
            ),
        ))
    }
}

pub(super) const MEMORY_BIOCORTEX_T6_CANDIDATE_EXPANSION_SHADOW_TELEMETRY_REVIEW_SCHEMA: &str =
    "agent_bridge.memory_biocortex_t6_candidate_expansion.shadow_telemetry_review.v0";
pub(super) const MEMORY_BIOCORTEX_T6_CANDIDATE_EXPANSION_RUNTIME_ENABLEMENT_REVIEW_SCHEMA: &str =
    "agent_bridge.memory_biocortex_t6_candidate_expansion.runtime_enablement_review.v0";
pub(super) const MEMORY_BIOCORTEX_T6_CANDIDATE_EXPANSION_RUNTIME_ENABLEMENT_OWNER_DECISION_RECORD_SCHEMA:
    &str =
    "agent_bridge.memory_biocortex_t6_candidate_expansion.runtime_enablement_owner_decision_record.v0";
pub(super) const MEMORY_BIOCORTEX_T6_CANDIDATE_EXPANSION_RUNTIME_ENABLEMENT_IMPLEMENTATION_PLAN_ARTIFACT_SCHEMA:
    &str =
    "agent_bridge.memory_biocortex_t6_candidate_expansion.runtime_enablement_implementation_plan_artifact.v0";
pub(super) const MEMORY_BIOCORTEX_T6_CANDIDATE_EXPANSION_RUNTIME_ENABLEMENT_CODE_IMPLEMENTATION_GATE_SCHEMA:
    &str =
    "agent_bridge.memory_biocortex_t6_candidate_expansion.runtime_enablement_code_implementation_gate.v0";
pub(super) const MEMORY_BIOCORTEX_T6_CANDIDATE_EXPANSION_RUNTIME_ENABLEMENT_SHADOW_CODE_GATE_SCHEMA: &str =
    "agent_bridge.memory_biocortex_t6_candidate_expansion.runtime_enablement_shadow_code_gate.v0";
pub(super) const MEMORY_BIOCORTEX_T6_CANDIDATE_EXPANSION_RUNTIME_ENABLEMENT_SHADOW_FEATURE_FLAG: &str =
    "AB_BIOCORTEX_T6_CANDIDATE_EXPANSION_RUNTIME_ENABLEMENT_SHADOW";

pub(super) fn memory_biocortex_t6_candidate_expansion_shadow_telemetry_review_source_claims_runtime_authority(
    report: &Value,
) -> bool {
    [
        "/shadow_invocation_contract/this_tool_invokes_executor",
        "/shadow_invocation_contract/this_tool_runs_shadow_mode",
        "/shadow_invocation_contract/this_tool_calls_memory_search",
        "/shadow_invocation_contract/this_tool_calls_memory_neighbors",
        "/shadow_invocation_contract/this_tool_runs_biocortex",
        "/shadow_invocation_contract/may_mutate_runtime_candidate_set",
        "/shadow_invocation_contract/changes_runtime_candidate_set",
        "/shadow_invocation_contract/may_change_runtime_search_order",
        "/shadow_invocation_contract/runtime_influence_approved",
        "/shadow_invocation_contract/may_enable_runtime_gate_now",
        "/shadow_invocation_contract/may_write_memory_or_graph_edges",
        "/shadow_invocation_contract/may_approve_production_candidate_expansion_now",
        "/bounded_shadow_telemetry/raw_queries_allowed",
        "/bounded_shadow_telemetry/raw_keys_allowed",
        "/bounded_shadow_telemetry/content_allowed",
        "/bounded_shadow_telemetry/case_rows_allowed",
    ]
    .iter()
    .any(|pointer| {
        memory_biocortex_t6_candidate_expansion_shadow_execution_gate_bool_at(report, pointer)
    })
}

pub(super) fn memory_biocortex_t6_candidate_expansion_shadow_telemetry_review_source_ready(
    report: &Value,
) -> bool {
    report.get("schema").and_then(Value::as_str)
        == Some(
            MEMORY_BIOCORTEX_T6_CANDIDATE_EXPANSION_SHADOW_EXECUTOR_INVOCATION_REPORT_SCHEMA,
        )
        && report.get("read_only").and_then(Value::as_bool) == Some(true)
        && memory_biocortex_t6_candidate_expansion_shadow_execution_gate_bool_at(
            report,
            "/shadow_executor_invocation_report/ready",
        )
        && report
            .pointer("/shadow_executor_invocation_report/status")
            .and_then(Value::as_str)
            == Some("ready_for_shadow_telemetry_review")
        && memory_biocortex_t6_candidate_expansion_shadow_execution_gate_bool_at(
            report,
            "/shadow_invocation_contract/may_review_shadow_telemetry_now",
        )
        && !memory_biocortex_t6_candidate_expansion_shadow_telemetry_review_source_claims_runtime_authority(report)
        && !memory_biocortex_t6_candidate_expansion_shadow_execution_gate_bool_at(
            report,
            "/input_contract/shadow_executor_preflight_report_included",
        )
        && !memory_biocortex_t6_candidate_expansion_shadow_execution_gate_bool_at(
            report,
            "/input_contract/raw_query_included",
        )
        && !memory_biocortex_t6_candidate_expansion_shadow_execution_gate_bool_at(
            report,
            "/input_contract/raw_queries_included",
        )
        && !memory_biocortex_t6_candidate_expansion_shadow_execution_gate_bool_at(
            report,
            "/input_contract/raw_keys_included",
        )
        && !memory_biocortex_t6_candidate_expansion_shadow_execution_gate_bool_at(
            report,
            "/input_contract/content_included",
        )
        && !memory_biocortex_t6_candidate_expansion_shadow_execution_gate_bool_at(
            report,
            "/input_contract/case_rows_included",
        )
}

pub(super) fn memory_biocortex_t6_candidate_expansion_shadow_telemetry_review_payload(args: Value) -> Value {
    let report = args
        .get("shadow_executor_invocation_report")
        .cloned()
        .unwrap_or(Value::Null);
    let reviewer =
        memory_biocortex_t6_candidate_expansion_shadow_execution_gate_string(&args, "reviewer");
    let review_source = memory_biocortex_t6_candidate_expansion_shadow_execution_gate_string(
        &args,
        "review_source",
    );
    let telemetry_window_id =
        memory_biocortex_t6_candidate_expansion_shadow_execution_gate_string(
            &args,
            "telemetry_window_id",
        );
    let telemetry_review_decision =
        memory_biocortex_t6_candidate_expansion_shadow_execution_gate_string(
            &args,
            "telemetry_review_decision",
        );
    let observed_case_count =
        memory_biocortex_t6_candidate_expansion_shadow_executor_preflight_u64(
            &args,
            "observed_case_count",
            0,
        );
    let reviewed_case_count =
        memory_biocortex_t6_candidate_expansion_shadow_executor_preflight_u64(
            &args,
            "reviewed_case_count",
            0,
        );
    let failed_case_count =
        memory_biocortex_t6_candidate_expansion_shadow_executor_preflight_u64(
            &args,
            "failed_case_count",
            0,
        );
    let candidate_delta_count =
        memory_biocortex_t6_candidate_expansion_shadow_executor_preflight_u64(
            &args,
            "candidate_delta_count",
            0,
        );
    let negative_control_regression_count =
        memory_biocortex_t6_candidate_expansion_shadow_executor_preflight_u64(
            &args,
            "negative_control_regression_count",
            0,
        );
    let redaction_violation_count =
        memory_biocortex_t6_candidate_expansion_shadow_executor_preflight_u64(
            &args,
            "redaction_violation_count",
            0,
        );
    let append_only_telemetry_confirmed =
        memory_biocortex_t6_candidate_expansion_shadow_executor_invocation_report_bool(
            &args,
            "append_only_telemetry_confirmed",
            false,
        );
    let redacted_aggregate_only =
        memory_biocortex_t6_candidate_expansion_shadow_executor_invocation_report_bool(
            &args,
            "redacted_aggregate_only",
            false,
        );
    let source_shadow_case_count =
        memory_biocortex_t6_candidate_expansion_shadow_execution_gate_u64_at(
            &report,
            "/shadow_executor_invocation_report/shadow_case_count",
        );
    let source_max_shadow_case_bound =
        memory_biocortex_t6_candidate_expansion_shadow_execution_gate_u64_at(
            &report,
            "/bounded_shadow_telemetry/max_shadow_case_bound",
        );
    let source_case_bound = if source_shadow_case_count > 0 {
        source_shadow_case_count
    } else if source_max_shadow_case_bound > 0 {
        source_max_shadow_case_bound
    } else {
        100
    }
    .min(100);

    let mut block_reasons = BTreeSet::<String>::new();
    if !memory_biocortex_t6_candidate_expansion_shadow_telemetry_review_source_ready(&report) {
        block_reasons.insert("source_shadow_executor_invocation_report_not_ready".to_string());
    }
    if memory_biocortex_t6_candidate_expansion_shadow_execution_gate_contains_raw(&report) {
        block_reasons.insert("source_shadow_executor_invocation_report_contains_raw".to_string());
    }
    if memory_biocortex_t6_candidate_expansion_shadow_execution_gate_contains_raw(&args) {
        block_reasons.insert("input_contains_raw_or_source_fields".to_string());
    }
    if memory_biocortex_t6_candidate_expansion_shadow_telemetry_review_source_claims_runtime_authority(&report) {
        block_reasons
            .insert("source_shadow_executor_invocation_report_claims_runtime_authority".to_string());
    }
    if reviewer.is_empty() {
        block_reasons.insert("reviewer_missing".to_string());
    }
    if review_source.is_empty() {
        block_reasons.insert("review_source_missing".to_string());
    }
    if telemetry_window_id.is_empty() {
        block_reasons.insert("telemetry_window_id_missing".to_string());
    }
    if telemetry_review_decision != "approve_shadow_telemetry_only" {
        block_reasons
            .insert("telemetry_review_decision_not_approve_shadow_telemetry_only".to_string());
    }
    if observed_case_count == 0 {
        block_reasons.insert("observed_case_count_missing".to_string());
    }
    if observed_case_count > source_case_bound {
        block_reasons.insert("observed_case_count_exceeds_source_bound".to_string());
    }
    if reviewed_case_count != observed_case_count {
        block_reasons.insert("reviewed_case_count_mismatch".to_string());
    }
    if candidate_delta_count > observed_case_count {
        block_reasons.insert("candidate_delta_exceeds_observed_cases".to_string());
    }
    if failed_case_count > 0 {
        block_reasons.insert("failed_case_count_present".to_string());
    }
    if negative_control_regression_count > 0 {
        block_reasons.insert("negative_control_regression_detected".to_string());
    }
    if redaction_violation_count > 0 {
        block_reasons.insert("redaction_violation_detected".to_string());
    }
    if !append_only_telemetry_confirmed {
        block_reasons.insert("append_only_telemetry_not_confirmed".to_string());
    }
    if !redacted_aggregate_only {
        block_reasons.insert("redacted_aggregate_only_missing".to_string());
    }

    let block_reasons: Vec<String> = block_reasons.into_iter().collect();
    let ready = block_reasons.is_empty();
    let status = if ready {
        "ready_for_runtime_enablement_review"
    } else {
        "blocked_shadow_telemetry_review"
    };

    json!({
        "schema": MEMORY_BIOCORTEX_T6_CANDIDATE_EXPANSION_SHADOW_TELEMETRY_REVIEW_SCHEMA,
        "generated_at": unix_now_secs(),
        "read_only": true,
        "shadow_telemetry_review": {
            "ready": ready,
            "status": status,
            "block_reasons": block_reasons,
            "reviewer_present": !reviewer.is_empty(),
            "review_source_present": !review_source.is_empty(),
            "telemetry_window_id_present": !telemetry_window_id.is_empty(),
            "telemetry_review_decision": telemetry_review_decision,
            "observed_case_count": observed_case_count,
            "reviewed_case_count": reviewed_case_count,
            "failed_case_count": failed_case_count,
            "candidate_delta_count": candidate_delta_count,
            "negative_control_regression_count": negative_control_regression_count,
            "redaction_violation_count": redaction_violation_count,
            "source_case_bound": source_case_bound,
            "reviewed_case_count_matches": reviewed_case_count == observed_case_count,
            "append_only_telemetry_confirmed": append_only_telemetry_confirmed,
            "redacted_aggregate_only": redacted_aggregate_only,
        },
        "shadow_telemetry_contract": {
            "may_prepare_runtime_enablement_review_now": ready,
            "this_tool_invokes_executor": false,
            "this_tool_runs_shadow_mode": false,
            "this_tool_calls_memory_search": false,
            "this_tool_calls_memory_neighbors": false,
            "this_tool_runs_biocortex": false,
            "may_mutate_runtime_candidate_set": false,
            "changes_runtime_candidate_set": false,
            "may_change_runtime_search_order": false,
            "runtime_influence_approved": false,
            "may_enable_runtime_gate_now": false,
            "may_write_memory_or_graph_edges": false,
            "may_approve_production_candidate_expansion_now": false,
            "requires_later_runtime_enablement_gate": true,
            "requires_later_candidate_expansion_enablement_gate": true,
        },
        "bounded_shadow_telemetry_review": {
            "redacted_aggregate_required": true,
            "append_only_telemetry_required": true,
            "append_only_telemetry_confirmed": append_only_telemetry_confirmed,
            "redacted_aggregate_only": redacted_aggregate_only,
            "source_case_bound": source_case_bound,
            "raw_queries_allowed": false,
            "raw_keys_allowed": false,
            "content_allowed": false,
            "case_rows_allowed": false,
            "production_traffic_allowed": false,
        },
        "input_contract": {
            "shadow_executor_invocation_report_included": false,
            "raw_query_included": false,
            "raw_queries_included": false,
            "raw_keys_included": false,
            "content_included": false,
            "case_rows_included": false,
            "unknown_fields_ignored": true,
        },
        "non_goals": [
            "This tool does not invoke a shadow executor or run shadow mode.",
            "This tool does not read telemetry rows; it validates a bounded redacted aggregate review only.",
            "This tool does not consume raw queries, raw keys, memory content, production traffic, or case rows.",
            "This tool does not call BioCortex, memory_search, or memory_neighbors.",
            "This tool does not mutate runtime candidate sets, search order, memory, graph edges, feature flags, approvals, or telemetry.",
            "This tool does not approve runtime enablement or production candidate expansion."
        ],
    })
}

pub struct MemoryBioCortexT6CandidateExpansionShadowTelemetryReviewTool;
impl MemoryBioCortexT6CandidateExpansionShadowTelemetryReviewTool {
    pub fn new() -> Self {
        Self
    }
}

impl Default for MemoryBioCortexT6CandidateExpansionShadowTelemetryReviewTool {
    fn default() -> Self {
        Self::new()
    }
}

#[async_trait]
impl McpTool for MemoryBioCortexT6CandidateExpansionShadowTelemetryReviewTool {
    fn name(&self) -> &'static str {
        "memory_biocortex_t6_candidate_expansion_shadow_telemetry_review"
    }

    fn schema(&self) -> ToolSchema {
        ToolSchema {
            name: self.name().into(),
            description: "Read-only T6 candidate-expansion shadow telemetry review gate. \
                Consumes a safe shadow executor invocation report plus bounded redacted \
                aggregate telemetry-review counts. It does not read raw telemetry, invoke \
                executors, run shadow mode, call BioCortex or memory tools, mutate runtime \
                candidates, change search order, or approve runtime influence."
                .into(),
            input_schema: json!({
                "type": "object",
                "required": [
                    "shadow_executor_invocation_report",
                    "reviewer",
                    "review_source",
                    "telemetry_window_id",
                    "telemetry_review_decision",
                    "observed_case_count",
                    "reviewed_case_count",
                    "failed_case_count",
                    "candidate_delta_count",
                    "negative_control_regression_count",
                    "redaction_violation_count",
                    "append_only_telemetry_confirmed",
                    "redacted_aggregate_only"
                ],
                "properties": {
                    "shadow_executor_invocation_report": {
                        "type": "object",
                        "description": "JSON object produced by memory_biocortex_t6_candidate_expansion_shadow_executor_invocation_report. It is inspected but never echoed."
                    },
                    "reviewer": {
                        "type": "string",
                        "description": "Human or agent reviewer id for the telemetry review decision."
                    },
                    "review_source": {
                        "type": "string",
                        "description": "Review provenance such as a forum post or evidence packet id."
                    },
                    "telemetry_window_id": {
                        "type": "string",
                        "description": "Redacted aggregate telemetry window id. Raw telemetry row ids must not be supplied."
                    },
                    "telemetry_review_decision": {
                        "type": "string",
                        "enum": [
                            "approve_shadow_telemetry_only",
                            "request_shadow_telemetry_changes",
                            "reject_shadow_telemetry"
                        ],
                        "description": "Only approve_shadow_telemetry_only can open the later runtime-enablement review path."
                    },
                    "observed_case_count": {
                        "type": "integer",
                        "minimum": 1,
                        "maximum": 100,
                        "description": "Bounded count of redacted shadow cases observed in the aggregate telemetry."
                    },
                    "reviewed_case_count": {
                        "type": "integer",
                        "minimum": 0,
                        "maximum": 100,
                        "description": "Count of redacted shadow cases reviewed; must match observed_case_count."
                    },
                    "failed_case_count": {
                        "type": "integer",
                        "minimum": 0,
                        "maximum": 100,
                        "description": "Any failed case blocks the later runtime-enablement review path."
                    },
                    "candidate_delta_count": {
                        "type": "integer",
                        "minimum": 0,
                        "maximum": 100,
                        "description": "Redacted count of hypothetical candidate deltas. No keys or content allowed."
                    },
                    "negative_control_regression_count": {
                        "type": "integer",
                        "minimum": 0,
                        "maximum": 100,
                        "description": "Any negative-control regression blocks the later runtime-enablement review path."
                    },
                    "redaction_violation_count": {
                        "type": "integer",
                        "minimum": 0,
                        "maximum": 100,
                        "description": "Any redaction violation blocks the later runtime-enablement review path."
                    },
                    "append_only_telemetry_confirmed": {
                        "type": "boolean",
                        "default": false,
                        "description": "Must be true to confirm only append-only telemetry was reviewed."
                    },
                    "redacted_aggregate_only": {
                        "type": "boolean",
                        "default": false,
                        "description": "Must be true to confirm no raw queries, keys, content, or case rows were supplied."
                    }
                }
            }),
        }
    }

    async fn execute(&self, args: Value, _ctx: &ToolContext) -> Result<ToolResult> {
        Ok(ToolResult::json_text(
            &memory_biocortex_t6_candidate_expansion_shadow_telemetry_review_payload(args),
        ))
    }
}

pub(super) fn memory_biocortex_t6_candidate_expansion_runtime_enablement_review_source_claims_runtime_authority(
    review: &Value,
) -> bool {
    [
        "/shadow_telemetry_contract/may_enable_runtime_gate_now",
        "/shadow_telemetry_contract/runtime_influence_approved",
        "/shadow_telemetry_contract/may_mutate_runtime_candidate_set",
        "/shadow_telemetry_contract/changes_runtime_candidate_set",
        "/shadow_telemetry_contract/may_change_runtime_search_order",
        "/shadow_telemetry_contract/may_write_memory_or_graph_edges",
        "/shadow_telemetry_contract/may_approve_production_candidate_expansion_now",
        "/bounded_shadow_telemetry_review/raw_queries_allowed",
        "/bounded_shadow_telemetry_review/raw_keys_allowed",
        "/bounded_shadow_telemetry_review/content_allowed",
        "/bounded_shadow_telemetry_review/case_rows_allowed",
        "/bounded_shadow_telemetry_review/production_traffic_allowed",
    ]
    .iter()
    .any(|pointer| {
        memory_biocortex_t6_candidate_expansion_shadow_execution_gate_bool_at(review, pointer)
    })
}

pub(super) fn memory_biocortex_t6_candidate_expansion_runtime_enablement_review_source_ready(
    review: &Value,
) -> bool {
    review.get("schema").and_then(Value::as_str)
        == Some(MEMORY_BIOCORTEX_T6_CANDIDATE_EXPANSION_SHADOW_TELEMETRY_REVIEW_SCHEMA)
        && review.get("read_only").and_then(Value::as_bool) == Some(true)
        && memory_biocortex_t6_candidate_expansion_shadow_execution_gate_bool_at(
            review,
            "/shadow_telemetry_review/ready",
        )
        && review
            .pointer("/shadow_telemetry_review/status")
            .and_then(Value::as_str)
            == Some("ready_for_runtime_enablement_review")
        && memory_biocortex_t6_candidate_expansion_shadow_execution_gate_bool_at(
            review,
            "/shadow_telemetry_contract/may_prepare_runtime_enablement_review_now",
        )
        && !memory_biocortex_t6_candidate_expansion_runtime_enablement_review_source_claims_runtime_authority(review)
        && memory_biocortex_t6_candidate_expansion_shadow_execution_gate_u64_at(
            review,
            "/shadow_telemetry_review/failed_case_count",
        ) == 0
        && memory_biocortex_t6_candidate_expansion_shadow_execution_gate_u64_at(
            review,
            "/shadow_telemetry_review/negative_control_regression_count",
        ) == 0
        && memory_biocortex_t6_candidate_expansion_shadow_execution_gate_u64_at(
            review,
            "/shadow_telemetry_review/redaction_violation_count",
        ) == 0
        && memory_biocortex_t6_candidate_expansion_shadow_execution_gate_bool_at(
            review,
            "/shadow_telemetry_review/append_only_telemetry_confirmed",
        )
        && memory_biocortex_t6_candidate_expansion_shadow_execution_gate_bool_at(
            review,
            "/shadow_telemetry_review/redacted_aggregate_only",
        )
        && !memory_biocortex_t6_candidate_expansion_shadow_execution_gate_bool_at(
            review,
            "/input_contract/shadow_executor_invocation_report_included",
        )
        && !memory_biocortex_t6_candidate_expansion_shadow_execution_gate_bool_at(
            review,
            "/input_contract/raw_query_included",
        )
        && !memory_biocortex_t6_candidate_expansion_shadow_execution_gate_bool_at(
            review,
            "/input_contract/raw_queries_included",
        )
        && !memory_biocortex_t6_candidate_expansion_shadow_execution_gate_bool_at(
            review,
            "/input_contract/raw_keys_included",
        )
        && !memory_biocortex_t6_candidate_expansion_shadow_execution_gate_bool_at(
            review,
            "/input_contract/content_included",
        )
        && !memory_biocortex_t6_candidate_expansion_shadow_execution_gate_bool_at(
            review,
            "/input_contract/case_rows_included",
        )
}

pub(super) fn memory_biocortex_t6_candidate_expansion_runtime_enablement_review_payload(
    args: Value,
) -> Value {
    let review = args
        .get("shadow_telemetry_review")
        .cloned()
        .unwrap_or(Value::Null);
    let reviewer =
        memory_biocortex_t6_candidate_expansion_shadow_execution_gate_string(&args, "reviewer");
    let review_source = memory_biocortex_t6_candidate_expansion_shadow_execution_gate_string(
        &args,
        "review_source",
    );
    let decision_source = memory_biocortex_t6_candidate_expansion_shadow_execution_gate_string(
        &args,
        "decision_source",
    );
    let runtime_enablement_review_decision =
        memory_biocortex_t6_candidate_expansion_shadow_execution_gate_string(
            &args,
            "runtime_enablement_review_decision",
        );
    let observed_case_count =
        memory_biocortex_t6_candidate_expansion_shadow_execution_gate_u64_at(
            &review,
            "/shadow_telemetry_review/observed_case_count",
        );
    let reviewed_case_count =
        memory_biocortex_t6_candidate_expansion_shadow_execution_gate_u64_at(
            &review,
            "/shadow_telemetry_review/reviewed_case_count",
        );
    let failed_case_count =
        memory_biocortex_t6_candidate_expansion_shadow_execution_gate_u64_at(
            &review,
            "/shadow_telemetry_review/failed_case_count",
        );
    let candidate_delta_count =
        memory_biocortex_t6_candidate_expansion_shadow_execution_gate_u64_at(
            &review,
            "/shadow_telemetry_review/candidate_delta_count",
        );
    let negative_control_regression_count =
        memory_biocortex_t6_candidate_expansion_shadow_execution_gate_u64_at(
            &review,
            "/shadow_telemetry_review/negative_control_regression_count",
        );
    let redaction_violation_count =
        memory_biocortex_t6_candidate_expansion_shadow_execution_gate_u64_at(
            &review,
            "/shadow_telemetry_review/redaction_violation_count",
        );
    let source_case_bound =
        memory_biocortex_t6_candidate_expansion_shadow_execution_gate_u64_at(
            &review,
            "/shadow_telemetry_review/source_case_bound",
        );
    let append_only_telemetry_confirmed =
        memory_biocortex_t6_candidate_expansion_shadow_execution_gate_bool_at(
            &review,
            "/shadow_telemetry_review/append_only_telemetry_confirmed",
        );
    let redacted_aggregate_only =
        memory_biocortex_t6_candidate_expansion_shadow_execution_gate_bool_at(
            &review,
            "/shadow_telemetry_review/redacted_aggregate_only",
        );

    let mut block_reasons = BTreeSet::<String>::new();
    if !memory_biocortex_t6_candidate_expansion_runtime_enablement_review_source_ready(&review) {
        block_reasons.insert("source_shadow_telemetry_review_not_ready".to_string());
    }
    if memory_biocortex_t6_candidate_expansion_shadow_execution_gate_contains_raw(&review) {
        block_reasons.insert("source_shadow_telemetry_review_contains_raw".to_string());
    }
    if memory_biocortex_t6_candidate_expansion_shadow_execution_gate_contains_raw(&args) {
        block_reasons.insert("input_contains_raw_or_source_fields".to_string());
    }
    if memory_biocortex_t6_candidate_expansion_runtime_enablement_review_source_claims_runtime_authority(&review) {
        block_reasons
            .insert("source_shadow_telemetry_review_claims_runtime_authority".to_string());
    }
    if reviewer.is_empty() {
        block_reasons.insert("reviewer_missing".to_string());
    }
    if review_source.is_empty() {
        block_reasons.insert("review_source_missing".to_string());
    }
    if decision_source.is_empty() {
        block_reasons.insert("decision_source_missing".to_string());
    }
    if runtime_enablement_review_decision != "approve_owner_runtime_enablement_review_only" {
        block_reasons
            .insert("runtime_enablement_review_decision_not_owner_review_only".to_string());
    }
    if failed_case_count > 0 {
        block_reasons.insert("failed_case_count_present".to_string());
    }
    if negative_control_regression_count > 0 {
        block_reasons.insert("negative_control_regression_detected".to_string());
    }
    if redaction_violation_count > 0 {
        block_reasons.insert("redaction_violation_detected".to_string());
    }
    if !append_only_telemetry_confirmed {
        block_reasons.insert("append_only_telemetry_not_confirmed".to_string());
    }
    if !redacted_aggregate_only {
        block_reasons.insert("redacted_aggregate_only_missing".to_string());
    }
    for reason in memory_biocortex_t6_string_array_at(
        &review,
        "/shadow_telemetry_review/block_reasons",
    ) {
        memory_biocortex_t6_push_reason(&mut block_reasons, &reason);
    }

    let block_reasons: Vec<String> = block_reasons.into_iter().collect();
    let ready = block_reasons.is_empty();
    let status = if ready {
        "ready_for_owner_runtime_enablement_decision"
    } else {
        "blocked_runtime_enablement_review"
    };

    json!({
        "schema": MEMORY_BIOCORTEX_T6_CANDIDATE_EXPANSION_RUNTIME_ENABLEMENT_REVIEW_SCHEMA,
        "generated_at": unix_now_secs(),
        "read_only": true,
        "runtime_enablement_review": {
            "ready": ready,
            "status": status,
            "block_reasons": block_reasons,
            "reviewer_present": !reviewer.is_empty(),
            "review_source_present": !review_source.is_empty(),
            "decision_source_present": !decision_source.is_empty(),
            "runtime_enablement_review_decision": runtime_enablement_review_decision,
            "observed_case_count": observed_case_count,
            "reviewed_case_count": reviewed_case_count,
            "failed_case_count": failed_case_count,
            "candidate_delta_count": candidate_delta_count,
            "negative_control_regression_count": negative_control_regression_count,
            "redaction_violation_count": redaction_violation_count,
            "source_case_bound": source_case_bound,
            "append_only_telemetry_confirmed": append_only_telemetry_confirmed,
            "redacted_aggregate_only": redacted_aggregate_only,
        },
        "owner_decision_options": [
            {
                "option": "request_more_shadow_telemetry",
                "effect": "No runtime change; collect more bounded append-only redacted shadow telemetry."
            },
            {
                "option": "reject_runtime_enablement_path",
                "effect": "No runtime change; stop the T6 runtime-enablement path."
            },
            {
                "option": "approve_runtime_enablement_implementation_plan_only",
                "effect": "Allows an implementation-plan review for runtime enablement, but still grants no runtime authority."
            }
        ],
        "runtime_enablement_contract": {
            "may_prepare_owner_runtime_enablement_decision": ready,
            "owner_runtime_enablement_decision_required": true,
            "may_prepare_runtime_enablement_implementation_plan_now": false,
            "may_implement_runtime_enablement_code_now": false,
            "may_enable_runtime_gate_now": false,
            "this_tool_runs_shadow_mode": false,
            "this_tool_calls_memory_search": false,
            "this_tool_calls_memory_neighbors": false,
            "this_tool_runs_biocortex": false,
            "may_mutate_runtime_candidate_set": false,
            "changes_runtime_candidate_set": false,
            "may_change_runtime_search_order": false,
            "runtime_influence_approved": false,
            "may_write_memory_or_graph_edges": false,
            "may_approve_production_candidate_expansion_now": false,
            "requires_later_owner_runtime_enablement_decision": true,
            "requires_later_runtime_enablement_implementation_plan": true,
            "requires_later_runtime_enablement_gate": true,
        },
        "bounded_runtime_enablement_review": {
            "redacted_aggregate_required": true,
            "append_only_telemetry_required": true,
            "append_only_telemetry_confirmed": append_only_telemetry_confirmed,
            "redacted_aggregate_only": redacted_aggregate_only,
            "source_case_bound": source_case_bound,
            "raw_queries_allowed": false,
            "raw_keys_allowed": false,
            "content_allowed": false,
            "case_rows_allowed": false,
            "production_traffic_allowed": false,
        },
        "review_checklist": [
            "Confirm the source shadow telemetry review is ready and aggregate-only.",
            "Inspect observed/reviewed counts, failed cases, candidate deltas, negative-control regressions, and redaction violations.",
            "Do not approve runtime enablement from this review tool; prepare an explicit owner runtime-enablement decision only.",
            "Require a separate implementation plan, default-off feature flag, rollback plan, and runtime gate before any production influence.",
            "Keep raw queries, raw keys, memory content, production traffic, and per-case rows out of the artifact."
        ],
        "input_contract": {
            "shadow_telemetry_review_included": false,
            "shadow_executor_invocation_report_included": false,
            "raw_query_included": false,
            "raw_queries_included": false,
            "raw_keys_included": false,
            "content_included": false,
            "case_rows_included": false,
            "unknown_fields_ignored": true,
        },
        "links": {
            "reviewer": reviewer,
            "review_source": review_source,
            "decision_source": decision_source,
        },
        "non_goals": [
            "This tool does not enable the runtime gate.",
            "This tool does not implement runtime-enablement code or change feature flags.",
            "This tool does not run shadow mode or production candidate expansion.",
            "This tool does not call BioCortex, memory_search, or memory_neighbors.",
            "This tool does not mutate candidate sets, search order, memory, graph edges, approvals, or telemetry.",
            "This tool does not approve production candidate expansion."
        ],
    })
}

pub struct MemoryBioCortexT6CandidateExpansionRuntimeEnablementReviewTool;
impl MemoryBioCortexT6CandidateExpansionRuntimeEnablementReviewTool {
    pub fn new() -> Self {
        Self
    }
}

impl Default for MemoryBioCortexT6CandidateExpansionRuntimeEnablementReviewTool {
    fn default() -> Self {
        Self::new()
    }
}

#[async_trait]
impl McpTool for MemoryBioCortexT6CandidateExpansionRuntimeEnablementReviewTool {
    fn name(&self) -> &'static str {
        "memory_biocortex_t6_candidate_expansion_runtime_enablement_review"
    }

    fn schema(&self) -> ToolSchema {
        ToolSchema {
            name: self.name().into(),
            description: "Read-only T6 candidate-expansion runtime-enablement review gate. \
                Consumes a safe shadow telemetry review artifact and emits an owner-decision \
                surface only. It does not enable runtime behavior, implement runtime code, \
                call BioCortex or memory tools, mutate candidate sets, write memory/graph \
                edges, or approve production candidate expansion."
                .into(),
            input_schema: json!({
                "type": "object",
                "required": [
                    "shadow_telemetry_review",
                    "reviewer",
                    "review_source",
                    "decision_source",
                    "runtime_enablement_review_decision"
                ],
                "properties": {
                    "shadow_telemetry_review": {
                        "type": "object",
                        "description": "JSON object produced by memory_biocortex_t6_candidate_expansion_shadow_telemetry_review. It is inspected but never echoed."
                    },
                    "reviewer": {
                        "type": "string",
                        "description": "Human or agent reviewer id for this runtime-enablement review."
                    },
                    "review_source": {
                        "type": "string",
                        "description": "Review provenance such as a forum post or evidence packet id."
                    },
                    "decision_source": {
                        "type": "string",
                        "description": "Provenance for the reviewer decision on this artifact."
                    },
                    "runtime_enablement_review_decision": {
                        "type": "string",
                        "enum": [
                            "approve_owner_runtime_enablement_review_only",
                            "request_more_shadow_telemetry",
                            "reject_runtime_enablement_review"
                        ],
                        "description": "Only approve_owner_runtime_enablement_review_only can open the owner decision review path. No value enables runtime behavior."
                    }
                }
            }),
        }
    }

    async fn execute(&self, args: Value, _ctx: &ToolContext) -> Result<ToolResult> {
        Ok(ToolResult::json_text(
            &memory_biocortex_t6_candidate_expansion_runtime_enablement_review_payload(args),
        ))
    }
}

pub(super) fn memory_biocortex_t6_candidate_expansion_runtime_enablement_owner_decision_source_claims_runtime_authority(
    review: &Value,
) -> bool {
    [
        "/runtime_enablement_contract/may_prepare_runtime_enablement_implementation_plan_now",
        "/runtime_enablement_contract/may_implement_runtime_enablement_code_now",
        "/runtime_enablement_contract/may_enable_runtime_gate_now",
        "/runtime_enablement_contract/runtime_influence_approved",
        "/runtime_enablement_contract/may_mutate_runtime_candidate_set",
        "/runtime_enablement_contract/changes_runtime_candidate_set",
        "/runtime_enablement_contract/may_change_runtime_search_order",
        "/runtime_enablement_contract/may_write_memory_or_graph_edges",
        "/runtime_enablement_contract/may_approve_production_candidate_expansion_now",
        "/bounded_runtime_enablement_review/raw_queries_allowed",
        "/bounded_runtime_enablement_review/raw_keys_allowed",
        "/bounded_runtime_enablement_review/content_allowed",
        "/bounded_runtime_enablement_review/case_rows_allowed",
        "/bounded_runtime_enablement_review/production_traffic_allowed",
    ]
    .iter()
    .any(|pointer| {
        memory_biocortex_t6_candidate_expansion_shadow_execution_gate_bool_at(review, pointer)
    })
}

pub(super) fn memory_biocortex_t6_candidate_expansion_runtime_enablement_owner_decision_source_ready(
    review: &Value,
) -> bool {
    review.get("schema").and_then(Value::as_str)
        == Some(MEMORY_BIOCORTEX_T6_CANDIDATE_EXPANSION_RUNTIME_ENABLEMENT_REVIEW_SCHEMA)
        && review.get("read_only").and_then(Value::as_bool) == Some(true)
        && memory_biocortex_t6_candidate_expansion_shadow_execution_gate_bool_at(
            review,
            "/runtime_enablement_review/ready",
        )
        && review
            .pointer("/runtime_enablement_review/status")
            .and_then(Value::as_str)
            == Some("ready_for_owner_runtime_enablement_decision")
        && memory_biocortex_t6_candidate_expansion_shadow_execution_gate_bool_at(
            review,
            "/runtime_enablement_contract/may_prepare_owner_runtime_enablement_decision",
        )
        && !memory_biocortex_t6_candidate_expansion_runtime_enablement_owner_decision_source_claims_runtime_authority(
            review,
        )
        && memory_biocortex_t6_candidate_expansion_shadow_execution_gate_u64_at(
            review,
            "/runtime_enablement_review/failed_case_count",
        ) == 0
        && memory_biocortex_t6_candidate_expansion_shadow_execution_gate_u64_at(
            review,
            "/runtime_enablement_review/negative_control_regression_count",
        ) == 0
        && memory_biocortex_t6_candidate_expansion_shadow_execution_gate_u64_at(
            review,
            "/runtime_enablement_review/redaction_violation_count",
        ) == 0
        && memory_biocortex_t6_candidate_expansion_shadow_execution_gate_bool_at(
            review,
            "/runtime_enablement_review/append_only_telemetry_confirmed",
        )
        && memory_biocortex_t6_candidate_expansion_shadow_execution_gate_bool_at(
            review,
            "/runtime_enablement_review/redacted_aggregate_only",
        )
        && !memory_biocortex_t6_candidate_expansion_shadow_execution_gate_bool_at(
            review,
            "/input_contract/shadow_telemetry_review_included",
        )
        && !memory_biocortex_t6_candidate_expansion_shadow_execution_gate_bool_at(
            review,
            "/input_contract/shadow_executor_invocation_report_included",
        )
        && !memory_biocortex_t6_candidate_expansion_shadow_execution_gate_bool_at(
            review,
            "/input_contract/raw_query_included",
        )
        && !memory_biocortex_t6_candidate_expansion_shadow_execution_gate_bool_at(
            review,
            "/input_contract/raw_queries_included",
        )
        && !memory_biocortex_t6_candidate_expansion_shadow_execution_gate_bool_at(
            review,
            "/input_contract/raw_keys_included",
        )
        && !memory_biocortex_t6_candidate_expansion_shadow_execution_gate_bool_at(
            review,
            "/input_contract/content_included",
        )
        && !memory_biocortex_t6_candidate_expansion_shadow_execution_gate_bool_at(
            review,
            "/input_contract/case_rows_included",
        )
}

pub(super) fn memory_biocortex_t6_candidate_expansion_runtime_enablement_owner_decision_record_payload(
    args: Value,
) -> Value {
    let review = args
        .get("runtime_enablement_review")
        .cloned()
        .unwrap_or(Value::Null);
    let owner =
        memory_biocortex_t6_candidate_expansion_shadow_execution_gate_string(&args, "owner");
    let decision_source = memory_biocortex_t6_candidate_expansion_shadow_execution_gate_string(
        &args,
        "decision_source",
    );
    let reviewer =
        memory_biocortex_t6_candidate_expansion_shadow_execution_gate_string(&args, "reviewer");
    let rationale =
        memory_biocortex_t6_candidate_expansion_shadow_execution_gate_string(&args, "rationale");
    let owner_decision = memory_biocortex_t6_candidate_expansion_shadow_execution_gate_string(
        &args,
        "owner_decision",
    );
    let observed_case_count =
        memory_biocortex_t6_candidate_expansion_shadow_execution_gate_u64_at(
            &review,
            "/runtime_enablement_review/observed_case_count",
        );
    let reviewed_case_count =
        memory_biocortex_t6_candidate_expansion_shadow_execution_gate_u64_at(
            &review,
            "/runtime_enablement_review/reviewed_case_count",
        );
    let failed_case_count =
        memory_biocortex_t6_candidate_expansion_shadow_execution_gate_u64_at(
            &review,
            "/runtime_enablement_review/failed_case_count",
        );
    let candidate_delta_count =
        memory_biocortex_t6_candidate_expansion_shadow_execution_gate_u64_at(
            &review,
            "/runtime_enablement_review/candidate_delta_count",
        );
    let negative_control_regression_count =
        memory_biocortex_t6_candidate_expansion_shadow_execution_gate_u64_at(
            &review,
            "/runtime_enablement_review/negative_control_regression_count",
        );
    let redaction_violation_count =
        memory_biocortex_t6_candidate_expansion_shadow_execution_gate_u64_at(
            &review,
            "/runtime_enablement_review/redaction_violation_count",
        );
    let source_case_bound =
        memory_biocortex_t6_candidate_expansion_shadow_execution_gate_u64_at(
            &review,
            "/runtime_enablement_review/source_case_bound",
        );
    let append_only_telemetry_confirmed =
        memory_biocortex_t6_candidate_expansion_shadow_execution_gate_bool_at(
            &review,
            "/runtime_enablement_review/append_only_telemetry_confirmed",
        );
    let redacted_aggregate_only =
        memory_biocortex_t6_candidate_expansion_shadow_execution_gate_bool_at(
            &review,
            "/runtime_enablement_review/redacted_aggregate_only",
        );

    let mut block_reasons = BTreeSet::<String>::new();
    if !memory_biocortex_t6_candidate_expansion_runtime_enablement_owner_decision_source_ready(
        &review,
    ) {
        block_reasons.insert("source_runtime_enablement_review_not_ready".to_string());
    }
    if memory_biocortex_t6_candidate_expansion_shadow_execution_gate_contains_raw(&review) {
        block_reasons.insert("source_runtime_enablement_review_contains_raw".to_string());
    }
    if memory_biocortex_t6_candidate_expansion_shadow_execution_gate_contains_raw(&args) {
        block_reasons.insert("input_contains_raw_or_source_fields".to_string());
    }
    if memory_biocortex_t6_candidate_expansion_runtime_enablement_owner_decision_source_claims_runtime_authority(
        &review,
    ) {
        block_reasons
            .insert("source_runtime_enablement_review_claims_runtime_authority".to_string());
    }
    if owner.is_empty() {
        block_reasons.insert("owner_missing".to_string());
    }
    if decision_source.is_empty() {
        block_reasons.insert("decision_source_missing".to_string());
    }
    if !matches!(
        owner_decision.as_str(),
        "approve_runtime_enablement_preflight_or_plan_review_only"
            | "request_more_shadow_telemetry"
            | "reject_runtime_enablement_path"
    ) {
        block_reasons.insert("owner_decision_invalid".to_string());
    }
    if owner_decision != "approve_runtime_enablement_preflight_or_plan_review_only" {
        block_reasons
            .insert("owner_decision_not_preflight_or_plan_review_only".to_string());
    }
    if failed_case_count > 0 {
        block_reasons.insert("failed_case_count_present".to_string());
    }
    if negative_control_regression_count > 0 {
        block_reasons.insert("negative_control_regression_detected".to_string());
    }
    if redaction_violation_count > 0 {
        block_reasons.insert("redaction_violation_detected".to_string());
    }
    if !append_only_telemetry_confirmed {
        block_reasons.insert("append_only_telemetry_not_confirmed".to_string());
    }
    if !redacted_aggregate_only {
        block_reasons.insert("redacted_aggregate_only_missing".to_string());
    }
    for reason in memory_biocortex_t6_string_array_at(
        &review,
        "/runtime_enablement_review/block_reasons",
    ) {
        memory_biocortex_t6_push_reason(&mut block_reasons, &reason);
    }

    let block_reasons: Vec<String> = block_reasons.into_iter().collect();
    let ready = block_reasons.is_empty();
    let status = if ready {
        "ready_for_runtime_enablement_preflight_or_plan_review"
    } else {
        "blocked_runtime_enablement_owner_decision_record"
    };
    let next_gate = if ready {
        "prepare_runtime_enablement_preflight_or_plan_review_artifact"
    } else {
        "repair_runtime_enablement_review_or_owner_decision"
    };

    json!({
        "schema": MEMORY_BIOCORTEX_T6_CANDIDATE_EXPANSION_RUNTIME_ENABLEMENT_OWNER_DECISION_RECORD_SCHEMA,
        "generated_at": unix_now_secs(),
        "read_only": true,
        "runtime_enablement_owner_decision_record": {
            "ready": ready,
            "status": status,
            "block_reasons": block_reasons,
            "owner_present": !owner.is_empty(),
            "decision_source_present": !decision_source.is_empty(),
            "reviewer_present": !reviewer.is_empty(),
            "owner_decision": owner_decision,
            "owner": owner,
            "decision_source": decision_source,
            "reviewer": reviewer,
            "rationale": rationale,
            "observed_case_count": observed_case_count,
            "reviewed_case_count": reviewed_case_count,
            "failed_case_count": failed_case_count,
            "candidate_delta_count": candidate_delta_count,
            "negative_control_regression_count": negative_control_regression_count,
            "redaction_violation_count": redaction_violation_count,
            "source_case_bound": source_case_bound,
            "append_only_telemetry_confirmed": append_only_telemetry_confirmed,
            "redacted_aggregate_only": redacted_aggregate_only,
            "decision": {
                "verdict": status,
                "next_gate": next_gate,
                "preflight_or_plan_review_only": true,
                "runtime_code_out_of_scope": true,
                "runtime_authority_out_of_scope": true,
                "candidate_expansion_authority_out_of_scope": true,
            }
        },
        "runtime_enablement_owner_decision_contract": {
            "explicit_owner_decision_required": true,
            "may_prepare_runtime_enablement_preflight_or_plan_review": ready,
            "may_prepare_runtime_enablement_implementation_plan_now": false,
            "may_implement_runtime_enablement_code_now": false,
            "may_enable_runtime_gate_now": false,
            "this_tool_runs_shadow_mode": false,
            "this_tool_calls_memory_search": false,
            "this_tool_calls_memory_neighbors": false,
            "this_tool_runs_biocortex": false,
            "may_mutate_runtime_candidate_set": false,
            "changes_runtime_candidate_set": false,
            "may_change_runtime_search_order": false,
            "runtime_influence_approved": false,
            "may_write_memory_or_graph_edges": false,
            "may_approve_production_candidate_expansion_now": false,
            "requires_later_runtime_enablement_preflight_or_plan": true,
            "requires_later_runtime_enablement_gate": true,
            "requires_later_runtime_enablement_code_gate": true,
        },
        "bounded_runtime_enablement_owner_decision": {
            "redacted_aggregate_required": true,
            "append_only_telemetry_required": true,
            "append_only_telemetry_confirmed": append_only_telemetry_confirmed,
            "redacted_aggregate_only": redacted_aggregate_only,
            "source_case_bound": source_case_bound,
            "raw_queries_allowed": false,
            "raw_keys_allowed": false,
            "content_allowed": false,
            "case_rows_allowed": false,
            "production_traffic_allowed": false,
        },
        "review_checklist": [
            "Confirm the source runtime-enablement review is ready and aggregate-only.",
            "Confirm the owner decision came from an explicit external source.",
            "If approving, limit follow-up work to a preflight or implementation-plan review artifact only.",
            "Require a separate runtime-enablement gate and code gate before any runtime behavior exists.",
            "Keep raw queries, raw keys, memory content, production traffic, and per-case rows out of the artifact."
        ],
        "input_contract": {
            "runtime_enablement_review_included": false,
            "shadow_telemetry_review_included": false,
            "shadow_executor_invocation_report_included": false,
            "raw_query_included": false,
            "raw_queries_included": false,
            "raw_keys_included": false,
            "content_included": false,
            "case_rows_included": false,
            "unknown_fields_ignored": true,
        },
        "non_goals": [
            "This tool does not enable the runtime gate.",
            "This tool does not implement runtime-enablement code or change feature flags.",
            "This tool does not run shadow mode or production candidate expansion.",
            "This tool does not call BioCortex, memory_search, or memory_neighbors.",
            "This tool does not mutate candidate sets, search order, memory, graph edges, approvals, or telemetry.",
            "This tool does not approve production candidate expansion."
        ],
    })
}

pub struct MemoryBioCortexT6CandidateExpansionRuntimeEnablementOwnerDecisionRecordTool;
impl MemoryBioCortexT6CandidateExpansionRuntimeEnablementOwnerDecisionRecordTool {
    pub fn new() -> Self {
        Self
    }
}

impl Default for MemoryBioCortexT6CandidateExpansionRuntimeEnablementOwnerDecisionRecordTool {
    fn default() -> Self {
        Self::new()
    }
}

#[async_trait]
impl McpTool for MemoryBioCortexT6CandidateExpansionRuntimeEnablementOwnerDecisionRecordTool {
    fn name(&self) -> &'static str {
        "memory_biocortex_t6_candidate_expansion_runtime_enablement_owner_decision_record"
    }

    fn schema(&self) -> ToolSchema {
        ToolSchema {
            name: self.name().into(),
            description: "Read-only T6 runtime-enablement owner decision record. \
                Consumes a safe runtime-enablement review artifact and an explicit owner \
                decision. A positive decision can only open a later preflight/plan review \
                surface; it does not enable runtime behavior, implement runtime code, \
                call BioCortex or memory tools, mutate candidate sets, write memory/graph \
                edges, or approve production candidate expansion."
                .into(),
            input_schema: json!({
                "type": "object",
                "required": [
                    "runtime_enablement_review",
                    "owner",
                    "decision_source",
                    "owner_decision"
                ],
                "properties": {
                    "runtime_enablement_review": {
                        "type": "object",
                        "description": "JSON object produced by memory_biocortex_t6_candidate_expansion_runtime_enablement_review. It is inspected but never echoed."
                    },
                    "owner": {
                        "type": "string",
                        "description": "Owner/operator identity for the decision record."
                    },
                    "decision_source": {
                        "type": "string",
                        "description": "External source for the owner decision, such as a forum post id, issue URL, or signed review note id."
                    },
                    "owner_decision": {
                        "type": "string",
                        "enum": [
                            "approve_runtime_enablement_preflight_or_plan_review_only",
                            "request_more_shadow_telemetry",
                            "reject_runtime_enablement_path"
                        ],
                        "description": "Only approve_runtime_enablement_preflight_or_plan_review_only opens the next review/planning path. No value enables runtime behavior."
                    },
                    "reviewer": {
                        "type": "string",
                        "description": "Optional reviewer identity or handle."
                    },
                    "rationale": {
                        "type": "string",
                        "description": "Optional short rationale copied from the external decision source."
                    }
                }
            }),
        }
    }

    async fn execute(&self, args: Value, _ctx: &ToolContext) -> Result<ToolResult> {
        Ok(ToolResult::json_text(
            &memory_biocortex_t6_candidate_expansion_runtime_enablement_owner_decision_record_payload(
                args,
            ),
        ))
    }
}

pub(super) fn memory_biocortex_t6_candidate_expansion_runtime_enablement_implementation_plan_source_claims_runtime_authority(
    record: &Value,
) -> bool {
    [
        "/runtime_enablement_owner_decision_contract/may_prepare_runtime_enablement_implementation_plan_now",
        "/runtime_enablement_owner_decision_contract/may_implement_runtime_enablement_code_now",
        "/runtime_enablement_owner_decision_contract/may_enable_runtime_gate_now",
        "/runtime_enablement_owner_decision_contract/this_tool_runs_shadow_mode",
        "/runtime_enablement_owner_decision_contract/this_tool_calls_memory_search",
        "/runtime_enablement_owner_decision_contract/this_tool_calls_memory_neighbors",
        "/runtime_enablement_owner_decision_contract/this_tool_runs_biocortex",
        "/runtime_enablement_owner_decision_contract/may_mutate_runtime_candidate_set",
        "/runtime_enablement_owner_decision_contract/changes_runtime_candidate_set",
        "/runtime_enablement_owner_decision_contract/may_change_runtime_search_order",
        "/runtime_enablement_owner_decision_contract/runtime_influence_approved",
        "/runtime_enablement_owner_decision_contract/may_write_memory_or_graph_edges",
        "/runtime_enablement_owner_decision_contract/may_approve_production_candidate_expansion_now",
        "/bounded_runtime_enablement_owner_decision/raw_queries_allowed",
        "/bounded_runtime_enablement_owner_decision/raw_keys_allowed",
        "/bounded_runtime_enablement_owner_decision/content_allowed",
        "/bounded_runtime_enablement_owner_decision/case_rows_allowed",
        "/bounded_runtime_enablement_owner_decision/production_traffic_allowed",
    ]
    .iter()
    .any(|path| {
        memory_biocortex_t6_candidate_expansion_shadow_execution_gate_bool_at(record, path)
    })
}

pub(super) fn memory_biocortex_t6_candidate_expansion_runtime_enablement_implementation_plan_source_ready(
    record: &Value,
) -> bool {
    memory_biocortex_t6_string_at(record, "/schema")
        == Some(
            MEMORY_BIOCORTEX_T6_CANDIDATE_EXPANSION_RUNTIME_ENABLEMENT_OWNER_DECISION_RECORD_SCHEMA,
        )
        && memory_biocortex_t6_bool_at(record, "/read_only") == Some(true)
        && memory_biocortex_t6_bool_at(record, "/runtime_enablement_owner_decision_record/ready")
            == Some(true)
        && record
            .pointer("/runtime_enablement_owner_decision_record/status")
            .and_then(Value::as_str)
            == Some("ready_for_runtime_enablement_preflight_or_plan_review")
        && memory_biocortex_t6_bool_at(
            record,
            "/runtime_enablement_owner_decision_contract/may_prepare_runtime_enablement_preflight_or_plan_review",
        ) == Some(true)
        && !memory_biocortex_t6_candidate_expansion_runtime_enablement_implementation_plan_source_claims_runtime_authority(record)
}

pub(super) fn memory_biocortex_t6_candidate_expansion_runtime_enablement_implementation_plan_artifact_payload(
    args: Value,
) -> Value {
    let record = args
        .get("runtime_enablement_owner_decision_record")
        .cloned()
        .unwrap_or(Value::Null);
    let reviewer =
        memory_biocortex_t6_candidate_expansion_shadow_execution_gate_string(&args, "reviewer");
    let commit =
        memory_biocortex_t6_candidate_expansion_shadow_execution_gate_string(&args, "commit");
    let forum_post_id = memory_biocortex_t6_candidate_expansion_shadow_execution_gate_string(
        &args,
        "forum_post_id",
    );
    let memory_key =
        memory_biocortex_t6_candidate_expansion_shadow_execution_gate_string(&args, "memory_key");

    let source_ready =
        memory_biocortex_t6_candidate_expansion_runtime_enablement_implementation_plan_source_ready(
            &record,
        );
    let source_claims_runtime_authority =
        memory_biocortex_t6_candidate_expansion_runtime_enablement_implementation_plan_source_claims_runtime_authority(
            &record,
        );
    let source_contains_raw =
        memory_biocortex_t6_candidate_expansion_shadow_execution_gate_contains_raw(&record)
            || record.get("runtime_enablement_review").is_some()
            || memory_biocortex_t6_any_true(
                &record,
                &[
                    "/input_contract/runtime_enablement_review_included",
                    "/input_contract/shadow_telemetry_review_included",
                    "/input_contract/shadow_executor_invocation_report_included",
                    "/input_contract/raw_query_included",
                    "/input_contract/raw_queries_included",
                    "/input_contract/raw_keys_included",
                    "/input_contract/content_included",
                    "/input_contract/case_rows_included",
                ],
            );
    let input_contains_raw =
        memory_biocortex_t6_candidate_expansion_shadow_execution_gate_contains_raw(&args);
    let append_only_telemetry_confirmed =
        memory_biocortex_t6_candidate_expansion_shadow_execution_gate_bool_at(
            &record,
            "/runtime_enablement_owner_decision_record/append_only_telemetry_confirmed",
        );
    let redacted_aggregate_only =
        memory_biocortex_t6_candidate_expansion_shadow_execution_gate_bool_at(
            &record,
            "/runtime_enablement_owner_decision_record/redacted_aggregate_only",
        );
    let failed_case_count =
        memory_biocortex_t6_candidate_expansion_shadow_execution_gate_u64_at(
            &record,
            "/runtime_enablement_owner_decision_record/failed_case_count",
        );
    let negative_control_regression_count =
        memory_biocortex_t6_candidate_expansion_shadow_execution_gate_u64_at(
            &record,
            "/runtime_enablement_owner_decision_record/negative_control_regression_count",
        );
    let redaction_violation_count =
        memory_biocortex_t6_candidate_expansion_shadow_execution_gate_u64_at(
            &record,
            "/runtime_enablement_owner_decision_record/redaction_violation_count",
        );
    let owner_decision = memory_biocortex_t6_string_at(
        &record,
        "/runtime_enablement_owner_decision_record/owner_decision",
    )
    .unwrap_or("");
    let source_requirements_ok = memory_biocortex_t6_bool_at(
        &record,
        "/runtime_enablement_owner_decision_contract/requires_later_runtime_enablement_preflight_or_plan",
    ) == Some(true)
        && memory_biocortex_t6_bool_at(
            &record,
            "/runtime_enablement_owner_decision_contract/requires_later_runtime_enablement_gate",
        ) == Some(true)
        && memory_biocortex_t6_bool_at(
            &record,
            "/runtime_enablement_owner_decision_contract/requires_later_runtime_enablement_code_gate",
        ) == Some(true)
        && append_only_telemetry_confirmed
        && redacted_aggregate_only;

    let mut block_reasons = BTreeSet::<String>::new();
    if !source_ready {
        block_reasons
            .insert("source_runtime_enablement_owner_decision_record_not_ready".to_string());
    }
    if source_contains_raw {
        block_reasons
            .insert("source_runtime_enablement_owner_decision_record_contains_raw".to_string());
    }
    if input_contains_raw {
        block_reasons.insert("input_contains_raw_or_source_fields".to_string());
    }
    if source_claims_runtime_authority {
        block_reasons.insert(
            "source_runtime_enablement_owner_decision_record_claims_runtime_authority"
                .to_string(),
        );
    }
    if !source_requirements_ok {
        block_reasons.insert(
            "source_runtime_enablement_owner_decision_record_requirements_incomplete".to_string(),
        );
    }
    if owner_decision != "approve_runtime_enablement_preflight_or_plan_review_only" {
        block_reasons.insert(
            "source_owner_decision_record_not_approved_for_runtime_enablement_plan".to_string(),
        );
    }
    if failed_case_count > 0 {
        block_reasons.insert("failed_case_count_present".to_string());
    }
    if negative_control_regression_count > 0 {
        block_reasons.insert("negative_control_regression_detected".to_string());
    }
    if redaction_violation_count > 0 {
        block_reasons.insert("redaction_violation_detected".to_string());
    }
    if !append_only_telemetry_confirmed {
        block_reasons.insert("append_only_telemetry_not_confirmed".to_string());
    }
    if !redacted_aggregate_only {
        block_reasons.insert("redacted_aggregate_only_missing".to_string());
    }
    for reason in memory_biocortex_t6_string_array_at(
        &record,
        "/runtime_enablement_owner_decision_record/block_reasons",
    ) {
        memory_biocortex_t6_push_reason(&mut block_reasons, &reason);
    }

    let block_reasons: Vec<String> = block_reasons.into_iter().collect();
    let ready = block_reasons.is_empty();
    let status = if ready {
        "ready_for_runtime_enablement_implementation_plan_review"
    } else {
        "blocked_runtime_enablement_implementation_plan_artifact"
    };
    let next_gate = if ready {
        "author_review_runtime_enablement_code_implementation_gate_before_code"
    } else {
        "repair_runtime_enablement_owner_decision_record"
    };
    let telemetry_fields = vec![
        "source_case_bound",
        "observed_case_count",
        "reviewed_case_count",
        "candidate_delta_count",
        "failed_case_count",
        "negative_control_regression_count",
        "redaction_violation_count",
        "append_only_telemetry_confirmed",
        "redacted_aggregate_only",
        "runtime_gate_enabled",
    ];

    json!({
        "schema": MEMORY_BIOCORTEX_T6_CANDIDATE_EXPANSION_RUNTIME_ENABLEMENT_IMPLEMENTATION_PLAN_ARTIFACT_SCHEMA,
        "generated_at": unix_now_secs(),
        "read_only": true,
        "purpose": "T6 runtime-enablement implementation-plan artifact: consume a safe owner-decision record and emit the checklist for a later code-gate lane without implementing runtime code, enabling runtime behavior, invoking BioCortex, or approving candidate expansion.",
        "runtime_enablement_implementation_plan_artifact": {
            "ready": ready,
            "status": status,
            "block_reasons": block_reasons,
            "decision": {
                "verdict": status,
                "next_gate": next_gate,
                "preflight_plan_review_only": true,
                "implementation_plan_review_required": true,
                "runtime_code_out_of_scope": true,
                "runtime_authority_out_of_scope": true,
                "candidate_expansion_authority_out_of_scope": true,
            },
            "source_decision": {
                "owner": memory_biocortex_t6_string_at(&record, "/runtime_enablement_owner_decision_record/owner"),
                "owner_decision": memory_biocortex_t6_string_at(&record, "/runtime_enablement_owner_decision_record/owner_decision"),
                "decision_source": memory_biocortex_t6_string_at(&record, "/runtime_enablement_owner_decision_record/decision_source"),
                "reviewer": memory_biocortex_t6_string_at(&record, "/runtime_enablement_owner_decision_record/reviewer"),
                "owner_decision_verdict": memory_biocortex_t6_string_at(&record, "/runtime_enablement_owner_decision_record/decision/verdict"),
                "owner_decision_next_gate": memory_biocortex_t6_string_at(&record, "/runtime_enablement_owner_decision_record/decision/next_gate"),
            },
            "source_evidence": {
                "observed_case_count": memory_biocortex_t6_u64_at(&record, "/runtime_enablement_owner_decision_record/observed_case_count"),
                "reviewed_case_count": memory_biocortex_t6_u64_at(&record, "/runtime_enablement_owner_decision_record/reviewed_case_count"),
                "failed_case_count": failed_case_count,
                "candidate_delta_count": memory_biocortex_t6_u64_at(&record, "/runtime_enablement_owner_decision_record/candidate_delta_count"),
                "negative_control_regression_count": negative_control_regression_count,
                "redaction_violation_count": redaction_violation_count,
                "source_case_bound": memory_biocortex_t6_u64_at(&record, "/runtime_enablement_owner_decision_record/source_case_bound"),
                "append_only_telemetry_confirmed": append_only_telemetry_confirmed,
                "redacted_aggregate_only": redacted_aggregate_only,
            },
            "requirements": {
                "separate_runtime_enablement_gate": true,
                "separate_runtime_enablement_code_gate": true,
                "feature_flag_default_off": true,
                "shadow_mode_first": true,
                "deterministic_replay_fixture": true,
                "bounded_candidate_delta": true,
                "negative_controls": true,
                "rollback_plan": true,
                "telemetry_fields": telemetry_fields,
            },
        },
        "implementation_plan": {
            "runtime_gate_entrypoint": {
                "tool_name": "memory_biocortex_t6_candidate_expansion_runtime_enablement_code_implementation_gate",
                "scope": "separate_code_gate_review_before_runtime_enablement_code",
                "default_runtime_enabled": false,
            },
            "feature_flag": {
                "name": "AB_BIOCORTEX_T6_CANDIDATE_EXPANSION_RUNTIME_ENABLEMENT_SHADOW",
                "default_off": true,
                "required_before_any_shadow_execution": true,
            },
            "shadow_mode_contract": {
                "shadow_mode_first": true,
                "default_enabled": false,
                "can_influence_candidate_set": false,
                "can_change_search_order": false,
                "can_write_memory": false,
            },
            "deterministic_replay_fixture": {
                "required": true,
                "uses_redacted_fixture_ids_only": true,
                "must_run_before_shadow_execution": true,
            },
            "bounded_candidate_delta": {
                "required": true,
                "max_added_candidates_requires_separate_code_gate": true,
                "no_unbounded_neighbor_walks": true,
            },
            "negative_controls": {
                "required": true,
                "must_include_no_lift_and_noise_cases": true,
                "regression_blocks_shadow_execution": true,
            },
            "telemetry_fields": telemetry_fields,
            "rollback_contract": {
                "required": true,
                "restores_baseline_candidate_path": true,
                "disables_shadow_flag": true,
                "removes_runtime_influence": true,
            },
        },
        "plan_contract": {
            "may_prepare_runtime_enablement_code_implementation_gate": ready,
            "may_prepare_runtime_enablement_code_gate_now": false,
            "may_implement_runtime_enablement_code_now": false,
            "may_enable_runtime_gate_now": false,
            "may_run_shadow_mode_now": false,
            "candidate_expansion_experiment_approved": false,
            "may_run_candidate_expansion_dry_run_now": false,
            "may_expand_candidate_set_now": false,
            "changes_candidate_set_now": false,
            "runtime_influence_approved": false,
            "may_change_search_order_now": false,
            "may_write_memory_or_graph_edges": false,
            "requires_separate_runtime_enablement_implementation_plan": true,
            "requires_separate_runtime_enablement_code_gate": true,
            "requires_separate_runtime_enablement_gate": true,
        },
        "implementation_plan_checklist": [
            "Treat this artifact as a plan-review handoff only, not runtime authorization.",
            "Require a separate runtime-enablement implementation plan before code changes.",
            "Require a separate code gate before adding default-off shadow runtime code.",
            "Keep any future runtime gate default-off and shadow-only until separately approved.",
            "Preserve deterministic replay fixtures, negative controls, bounded candidate deltas, and rollback.",
            "Emit only aggregate telemetry fields; never include raw queries, keys, content, case rows, or raw errors.",
            "Require a later runtime-enable gate before any candidate-set influence, search-order change, or production expansion."
        ],
        "links": {
            "reviewer": reviewer,
            "commit": commit,
            "forum_post_id": forum_post_id,
            "memory_key": memory_key,
        },
        "input_contract": {
            "runtime_enablement_owner_decision_record_included": false,
            "runtime_enablement_review_included": false,
            "shadow_telemetry_review_included": false,
            "shadow_executor_invocation_report_included": false,
            "raw_query_included": false,
            "raw_queries_included": false,
            "raw_keys_included": false,
            "content_included": false,
            "case_rows_included": false,
            "raw_error_included": false,
            "unknown_fields_ignored": true,
        },
        "non_goals": [
            "This tool does not enable a runtime gate.",
            "This tool does not implement runtime-enablement code or change feature flags.",
            "This tool does not run shadow mode, invoke executors, or run BioCortex.",
            "This tool does not call memory_search or memory_neighbors.",
            "This tool does not mutate candidate sets, search order, memory, graph edges, approvals, telemetry, feature flags, or runtime configuration.",
            "This tool does not approve runtime influence or production candidate expansion."
        ],
    })
}

pub struct MemoryBioCortexT6CandidateExpansionRuntimeEnablementImplementationPlanArtifactTool;
impl MemoryBioCortexT6CandidateExpansionRuntimeEnablementImplementationPlanArtifactTool {
    pub fn new() -> Self {
        Self
    }
}

impl Default for MemoryBioCortexT6CandidateExpansionRuntimeEnablementImplementationPlanArtifactTool {
    fn default() -> Self {
        Self::new()
    }
}

#[async_trait]
impl McpTool for MemoryBioCortexT6CandidateExpansionRuntimeEnablementImplementationPlanArtifactTool {
    fn name(&self) -> &'static str {
        "memory_biocortex_t6_candidate_expansion_runtime_enablement_implementation_plan_artifact"
    }

    fn schema(&self) -> ToolSchema {
        ToolSchema {
            name: self.name().into(),
            description: "Read-only T6 runtime-enablement preflight/plan artifact. \
                Consumes a safe runtime-enablement owner-decision record and emits \
                requirements for a later implementation-plan/code-gate lane. It \
                does not enable runtime behavior, implement runtime code, call \
                BioCortex or memory tools, mutate candidate sets, write \
                memory/graph edges, or approve production candidate expansion."
                .into(),
            input_schema: json!({
                "type": "object",
                "required": ["runtime_enablement_owner_decision_record"],
                "properties": {
                    "runtime_enablement_owner_decision_record": {
                        "type": "object",
                        "description": "JSON object produced by memory_biocortex_t6_candidate_expansion_runtime_enablement_owner_decision_record. It is inspected but never echoed."
                    },
                    "reviewer": {
                        "type": "string",
                        "description": "Optional reviewer identity or handle."
                    },
                    "commit": {
                        "type": "string",
                        "description": "Optional implementation commit under review."
                    },
                    "forum_post_id": {
                        "type": "string",
                        "description": "Optional forum post id linking this artifact."
                    },
                    "memory_key": {
                        "type": "string",
                        "description": "Optional memory key linking this artifact."
                    }
                }
            }),
        }
    }

    async fn execute(&self, args: Value, _ctx: &ToolContext) -> Result<ToolResult> {
        Ok(ToolResult::json_text(
            &memory_biocortex_t6_candidate_expansion_runtime_enablement_implementation_plan_artifact_payload(
                args,
            ),
        ))
    }
}

pub(super) fn memory_biocortex_t6_candidate_expansion_runtime_enablement_code_implementation_gate_payload(
    args: Value,
) -> Value {
    let plan = args
        .get("runtime_enablement_implementation_plan_artifact")
        .unwrap_or(&Value::Null);
    let reviewer =
        memory_biocortex_t6_candidate_expansion_shadow_execution_gate_string(&args, "reviewer");
    let decision_source = memory_biocortex_t6_candidate_expansion_shadow_execution_gate_string(
        &args,
        "decision_source",
    );
    let code_gate_decision = args
        .get("code_gate_decision")
        .and_then(Value::as_str)
        .map(str::trim)
        .filter(|s| !s.is_empty())
        .unwrap_or("missing_code_gate_decision");
    let commit =
        memory_biocortex_t6_candidate_expansion_shadow_execution_gate_string(&args, "commit");
    let forum_post_id = memory_biocortex_t6_candidate_expansion_shadow_execution_gate_string(
        &args,
        "forum_post_id",
    );
    let memory_key =
        memory_biocortex_t6_candidate_expansion_shadow_execution_gate_string(&args, "memory_key");

    let plan_schema_valid = memory_biocortex_t6_string_at(plan, "/schema")
        == Some(
            MEMORY_BIOCORTEX_T6_CANDIDATE_EXPANSION_RUNTIME_ENABLEMENT_IMPLEMENTATION_PLAN_ARTIFACT_SCHEMA,
        );
    let plan_ready = memory_biocortex_t6_bool_at(
        plan,
        "/runtime_enablement_implementation_plan_artifact/ready",
    ) == Some(true);
    let plan_safe_contract = memory_biocortex_t6_bool_at(plan, "/read_only") == Some(true)
        && memory_biocortex_t6_bool_at(
            plan,
            "/plan_contract/may_prepare_runtime_enablement_code_implementation_gate",
        ) == Some(true)
        && memory_biocortex_t6_bool_at(
            plan,
            "/plan_contract/may_prepare_runtime_enablement_code_gate_now",
        ) == Some(false)
        && memory_biocortex_t6_bool_at(
            plan,
            "/plan_contract/may_implement_runtime_enablement_code_now",
        ) == Some(false)
        && memory_biocortex_t6_bool_at(plan, "/plan_contract/may_enable_runtime_gate_now")
            == Some(false)
        && memory_biocortex_t6_bool_at(plan, "/plan_contract/may_run_shadow_mode_now")
            == Some(false)
        && memory_biocortex_t6_bool_at(
            plan,
            "/plan_contract/candidate_expansion_experiment_approved",
        ) == Some(false)
        && memory_biocortex_t6_bool_at(
            plan,
            "/plan_contract/may_run_candidate_expansion_dry_run_now",
        ) == Some(false)
        && memory_biocortex_t6_bool_at(plan, "/plan_contract/may_expand_candidate_set_now")
            == Some(false)
        && memory_biocortex_t6_bool_at(plan, "/plan_contract/changes_candidate_set_now")
            == Some(false)
        && memory_biocortex_t6_bool_at(plan, "/plan_contract/runtime_influence_approved")
            == Some(false)
        && memory_biocortex_t6_bool_at(plan, "/plan_contract/may_change_search_order_now")
            == Some(false)
        && memory_biocortex_t6_bool_at(plan, "/plan_contract/may_write_memory_or_graph_edges")
            == Some(false)
        && memory_biocortex_t6_bool_at(
            plan,
            "/plan_contract/requires_separate_runtime_enablement_code_gate",
        ) == Some(true)
        && memory_biocortex_t6_bool_at(
            plan,
            "/plan_contract/requires_separate_runtime_enablement_gate",
        ) == Some(true);
    let plan_claims_runtime_authority = memory_biocortex_t6_any_true(
        plan,
        &[
            "/plan_contract/may_prepare_runtime_enablement_code_gate_now",
            "/plan_contract/may_implement_runtime_enablement_code_now",
            "/plan_contract/may_enable_runtime_gate_now",
            "/plan_contract/may_run_shadow_mode_now",
            "/plan_contract/candidate_expansion_experiment_approved",
            "/plan_contract/may_run_candidate_expansion_dry_run_now",
            "/plan_contract/may_expand_candidate_set_now",
            "/plan_contract/changes_candidate_set_now",
            "/plan_contract/runtime_influence_approved",
            "/plan_contract/may_change_search_order_now",
            "/plan_contract/may_write_memory_or_graph_edges",
            "/implementation_plan/runtime_gate_entrypoint/default_runtime_enabled",
            "/implementation_plan/shadow_mode_contract/default_enabled",
            "/implementation_plan/shadow_mode_contract/can_influence_candidate_set",
            "/implementation_plan/shadow_mode_contract/can_change_search_order",
            "/implementation_plan/shadow_mode_contract/can_write_memory",
        ],
    );
    let plan_requirements_ok = [
        "/runtime_enablement_implementation_plan_artifact/requirements/separate_runtime_enablement_gate",
        "/runtime_enablement_implementation_plan_artifact/requirements/separate_runtime_enablement_code_gate",
        "/runtime_enablement_implementation_plan_artifact/requirements/feature_flag_default_off",
        "/runtime_enablement_implementation_plan_artifact/requirements/shadow_mode_first",
        "/runtime_enablement_implementation_plan_artifact/requirements/deterministic_replay_fixture",
        "/runtime_enablement_implementation_plan_artifact/requirements/bounded_candidate_delta",
        "/runtime_enablement_implementation_plan_artifact/requirements/negative_controls",
        "/runtime_enablement_implementation_plan_artifact/requirements/rollback_plan",
        "/implementation_plan/feature_flag/default_off",
        "/implementation_plan/feature_flag/required_before_any_shadow_execution",
        "/implementation_plan/shadow_mode_contract/shadow_mode_first",
        "/implementation_plan/deterministic_replay_fixture/required",
        "/implementation_plan/bounded_candidate_delta/required",
        "/implementation_plan/negative_controls/required",
        "/implementation_plan/rollback_contract/required",
    ]
    .iter()
    .all(|path| memory_biocortex_t6_bool_at(plan, path) == Some(true))
        && memory_biocortex_t6_bool_at(
            plan,
            "/implementation_plan/runtime_gate_entrypoint/default_runtime_enabled",
        ) == Some(false)
        && memory_biocortex_t6_bool_at(
            plan,
            "/implementation_plan/shadow_mode_contract/default_enabled",
        ) == Some(false)
        && memory_biocortex_t6_bool_at(
            plan,
            "/implementation_plan/shadow_mode_contract/can_influence_candidate_set",
        ) == Some(false)
        && memory_biocortex_t6_bool_at(
            plan,
            "/implementation_plan/shadow_mode_contract/can_change_search_order",
        ) == Some(false)
        && memory_biocortex_t6_bool_at(
            plan,
            "/implementation_plan/shadow_mode_contract/can_write_memory",
        ) == Some(false)
        && !memory_biocortex_t6_string_array_at(
            plan,
            "/runtime_enablement_implementation_plan_artifact/requirements/telemetry_fields",
        )
        .is_empty()
        && !memory_biocortex_t6_string_array_at(plan, "/implementation_plan/telemetry_fields")
            .is_empty();
    let plan_flags_raw = memory_biocortex_t6_candidate_expansion_shadow_execution_gate_contains_raw(
        plan,
    ) || plan
        .get("runtime_enablement_owner_decision_record")
        .is_some()
        || plan.get("runtime_enablement_review").is_some()
        || plan.get("shadow_telemetry_review").is_some()
        || plan.get("shadow_executor_invocation_report").is_some()
        || plan.get("runtime_gate_owner_review_record").is_some()
        || plan.get("owner_decision_record").is_some()
        || plan.get("human_review_packet").is_some()
        || plan.get("candidate_expansion_dry_run_report").is_some()
        || plan.get("dry_run_report").is_some()
        || plan.get("candidate_expansion_dry_run_plan").is_some()
        || plan.get("recall_expansion_summary").is_some()
        || plan.get("case_rows").is_some()
        || memory_biocortex_t6_any_true(
            plan,
            &[
                "/input_contract/runtime_enablement_implementation_plan_artifact_included",
                "/input_contract/runtime_enablement_owner_decision_record_included",
                "/input_contract/runtime_enablement_review_included",
                "/input_contract/shadow_telemetry_review_included",
                "/input_contract/shadow_executor_invocation_report_included",
                "/input_contract/runtime_gate_owner_review_record_included",
                "/input_contract/owner_decision_record_included",
                "/input_contract/human_review_packet_included",
                "/input_contract/dry_run_report_included",
                "/input_contract/dry_run_plan_included",
                "/input_contract/recall_expansion_summary_included",
                "/input_contract/case_rows_included",
                "/input_contract/raw_query_included",
                "/input_contract/raw_queries_included",
                "/input_contract/raw_keys_included",
                "/input_contract/content_included",
                "/input_contract/raw_error_included",
            ],
        );
    let input_contains_raw =
        memory_biocortex_t6_candidate_expansion_shadow_execution_gate_contains_raw(&args);
    let code_gate_decision_valid = matches!(
        code_gate_decision,
        "approve_shadow_runtime_enablement_code_implementation_only"
            | "request_runtime_enablement_implementation_plan_changes"
            | "reject_runtime_enablement_code_implementation"
    );
    let code_gate_approves_shadow_code =
        code_gate_decision == "approve_shadow_runtime_enablement_code_implementation_only";

    let mut block_reasons = BTreeSet::<String>::new();
    if !plan_schema_valid {
        block_reasons.insert(
            "source_runtime_enablement_implementation_plan_artifact_schema_invalid".to_string(),
        );
    }
    if !plan_ready {
        block_reasons.insert(
            "source_runtime_enablement_implementation_plan_artifact_not_ready".to_string(),
        );
    }
    if !plan_safe_contract || plan_claims_runtime_authority {
        block_reasons.insert(
            "source_runtime_enablement_implementation_plan_artifact_claims_runtime_authority"
                .to_string(),
        );
    }
    if !plan_requirements_ok {
        block_reasons.insert(
            "source_runtime_enablement_implementation_plan_artifact_requirements_incomplete"
                .to_string(),
        );
    }
    if plan_flags_raw {
        block_reasons.insert(
            "source_runtime_enablement_implementation_plan_artifact_contains_raw".to_string(),
        );
    }
    if input_contains_raw {
        block_reasons.insert("input_contains_raw_or_source_fields".to_string());
    }
    if reviewer.is_empty() {
        block_reasons.insert("missing_reviewer".to_string());
    }
    if decision_source.is_empty() {
        block_reasons.insert("missing_decision_source".to_string());
    }
    if !code_gate_decision_valid {
        block_reasons.insert("invalid_code_gate_decision".to_string());
    }
    if code_gate_decision_valid && !code_gate_approves_shadow_code {
        block_reasons.insert(
            "code_gate_did_not_approve_shadow_runtime_enablement_code_implementation".to_string(),
        );
    }
    for reason in memory_biocortex_t6_string_array_at(
        plan,
        "/runtime_enablement_implementation_plan_artifact/block_reasons",
    ) {
        memory_biocortex_t6_push_reason(&mut block_reasons, &reason);
    }

    let block_reasons: Vec<String> = block_reasons.into_iter().collect();
    let ready = block_reasons.is_empty();
    let status = if ready {
        "shadow_runtime_enablement_code_implementation_authorized"
    } else {
        "blocked_before_runtime_enablement_code_implementation"
    };
    let next_gate = if ready {
        "implement_default_off_shadow_runtime_enablement_code"
    } else {
        "repair_or_reapprove_runtime_enablement_implementation_plan_artifact"
    };
    let telemetry_fields =
        memory_biocortex_t6_string_array_at(plan, "/implementation_plan/telemetry_fields");

    json!({
        "schema": MEMORY_BIOCORTEX_T6_CANDIDATE_EXPANSION_RUNTIME_ENABLEMENT_CODE_IMPLEMENTATION_GATE_SCHEMA,
        "generated_at": unix_now_secs(),
        "read_only": true,
        "purpose": "T6 runtime-enablement code-implementation gate: consume a safe runtime-enablement implementation-plan artifact plus an explicit code-gate decision and record whether default-off shadow runtime-enablement code may be implemented without enabling runtime execution, shadow mode, candidate expansion, search-order changes, memory writes, or graph writes.",
        "runtime_enablement_code_implementation_gate": {
            "ready": ready,
            "status": status,
            "block_reasons": block_reasons,
            "reviewer": reviewer,
            "code_gate_decision": code_gate_decision,
            "decision_source": decision_source,
            "decision": {
                "verdict": status,
                "next_gate": next_gate,
                "shadow_code_only": true,
                "default_off_required": true,
                "runtime_enablement_out_of_scope": true,
                "runtime_authority_out_of_scope": true,
                "candidate_expansion_authority_out_of_scope": true,
            },
            "source_decision": {
                "plan_verdict": memory_biocortex_t6_string_at(plan, "/runtime_enablement_implementation_plan_artifact/decision/verdict"),
                "plan_next_gate": memory_biocortex_t6_string_at(plan, "/runtime_enablement_implementation_plan_artifact/decision/next_gate"),
                "owner": memory_biocortex_t6_string_at(plan, "/runtime_enablement_implementation_plan_artifact/source_decision/owner"),
                "owner_decision": memory_biocortex_t6_string_at(plan, "/runtime_enablement_implementation_plan_artifact/source_decision/owner_decision"),
                "owner_decision_source": memory_biocortex_t6_string_at(plan, "/runtime_enablement_implementation_plan_artifact/source_decision/decision_source"),
                "reviewer": memory_biocortex_t6_string_at(plan, "/runtime_enablement_implementation_plan_artifact/source_decision/reviewer"),
            },
            "source_evidence": {
                "observed_case_count": memory_biocortex_t6_u64_at(plan, "/runtime_enablement_implementation_plan_artifact/source_evidence/observed_case_count"),
                "reviewed_case_count": memory_biocortex_t6_u64_at(plan, "/runtime_enablement_implementation_plan_artifact/source_evidence/reviewed_case_count"),
                "failed_case_count": memory_biocortex_t6_u64_at(plan, "/runtime_enablement_implementation_plan_artifact/source_evidence/failed_case_count"),
                "candidate_delta_count": memory_biocortex_t6_u64_at(plan, "/runtime_enablement_implementation_plan_artifact/source_evidence/candidate_delta_count"),
                "negative_control_regression_count": memory_biocortex_t6_u64_at(plan, "/runtime_enablement_implementation_plan_artifact/source_evidence/negative_control_regression_count"),
                "redaction_violation_count": memory_biocortex_t6_u64_at(plan, "/runtime_enablement_implementation_plan_artifact/source_evidence/redaction_violation_count"),
                "source_case_bound": memory_biocortex_t6_u64_at(plan, "/runtime_enablement_implementation_plan_artifact/source_evidence/source_case_bound"),
                "append_only_telemetry_confirmed": memory_biocortex_t6_bool_at(plan, "/runtime_enablement_implementation_plan_artifact/source_evidence/append_only_telemetry_confirmed"),
                "redacted_aggregate_only": memory_biocortex_t6_bool_at(plan, "/runtime_enablement_implementation_plan_artifact/source_evidence/redacted_aggregate_only"),
            },
        },
        "implementation_boundaries": {
            "feature_flag_name": memory_biocortex_t6_string_at(plan, "/implementation_plan/feature_flag/name"),
            "feature_flag_default_off": true,
            "shadow_mode_first": true,
            "default_runtime_enabled": false,
            "default_shadow_enabled": false,
            "deterministic_replay_fixture_required": true,
            "negative_controls_required": true,
            "bounded_candidate_delta_required": true,
            "rollback_required": true,
            "telemetry_fields": telemetry_fields,
        },
        "code_implementation_contract": {
            "may_implement_shadow_runtime_enablement_code": ready,
            "may_enable_runtime_gate_now": false,
            "may_run_shadow_mode_now": false,
            "candidate_expansion_experiment_approved": false,
            "may_run_candidate_expansion_dry_run_now": false,
            "may_expand_candidate_set_now": false,
            "changes_candidate_set_now": false,
            "runtime_influence_approved": false,
            "may_change_search_order_now": false,
            "may_write_memory_or_graph_edges": false,
            "this_gate_approves_runtime_candidate_expansion": false,
            "requires_separate_shadow_execution_gate": true,
            "requires_separate_runtime_enablement_gate": true,
        },
        "implementation_checklist": [
            "Implement only a default-off shadow runtime-enablement code path.",
            "Keep the runtime-enablement feature flag disabled by default and unreachable without explicit operator opt-in.",
            "Do not change candidate ordering, candidate-set membership, memory search, graph traversal, or writes.",
            "Add deterministic replay fixtures before any shadow execution.",
            "Add negative controls that block later shadow execution on regression.",
            "Emit only aggregate telemetry fields; never log raw queries, keys, content, case rows, or raw errors.",
            "Require a separate shadow-execution gate before running the code and a separate runtime-enable gate before any influence."
        ],
        "links": {
            "commit": commit,
            "forum_post_id": forum_post_id,
            "memory_key": memory_key,
        },
        "input_contract": {
            "runtime_enablement_implementation_plan_artifact_included": false,
            "runtime_enablement_owner_decision_record_included": false,
            "runtime_enablement_review_included": false,
            "shadow_telemetry_review_included": false,
            "shadow_executor_invocation_report_included": false,
            "runtime_gate_owner_review_record_included": false,
            "owner_decision_record_included": false,
            "human_review_packet_included": false,
            "dry_run_report_included": false,
            "dry_run_plan_included": false,
            "recall_expansion_summary_included": false,
            "case_rows_included": false,
            "raw_query_included": false,
            "raw_queries_included": false,
            "raw_keys_included": false,
            "content_included": false,
            "raw_error_included": false,
        },
        "non_goals": [
            "This tool does not enable a runtime gate.",
            "This tool does not run shadow mode or invoke executors.",
            "This tool does not run BioCortex.",
            "This tool does not call memory_search or memory_neighbors.",
            "This tool does not sample production memories or graph rows.",
            "This tool does not echo implementation-plan artifacts, owner-decision records, runtime-enablement reviews, shadow telemetry reviews, shadow executor invocation reports, case rows, queries, keys, content, or raw errors.",
            "This tool does not write memory, graph edges, authorization records, approval packets, feature flags, or runtime configuration.",
            "This tool does not approve runtime influence, search-order changes, dry-run execution, candidate-set expansion, or production candidate expansion."
        ],
    })
}

pub struct MemoryBioCortexT6CandidateExpansionRuntimeEnablementCodeImplementationGateTool;
impl MemoryBioCortexT6CandidateExpansionRuntimeEnablementCodeImplementationGateTool {
    pub fn new() -> Self {
        Self
    }
}

impl Default for MemoryBioCortexT6CandidateExpansionRuntimeEnablementCodeImplementationGateTool {
    fn default() -> Self {
        Self::new()
    }
}

#[async_trait]
impl McpTool for MemoryBioCortexT6CandidateExpansionRuntimeEnablementCodeImplementationGateTool {
    fn name(&self) -> &'static str {
        "memory_biocortex_t6_candidate_expansion_runtime_enablement_code_implementation_gate"
    }

    fn schema(&self) -> ToolSchema {
        ToolSchema {
            name: self.name().into(),
            description: "Read-only T6 runtime-enablement code-implementation gate. \
                Consumes a safe runtime-enablement implementation-plan artifact \
                plus an explicit code-gate decision and can only authorize \
                default-off shadow runtime-enablement code implementation; it \
                never enables runtime execution, shadow mode, runtime influence, \
                search-order changes, writes, or candidate expansion."
                .into(),
            input_schema: json!({
                "type": "object",
                "required": [
                    "runtime_enablement_implementation_plan_artifact",
                    "reviewer",
                    "code_gate_decision",
                    "decision_source"
                ],
                "properties": {
                    "runtime_enablement_implementation_plan_artifact": {
                        "type": "object",
                        "description": "JSON object produced by memory_biocortex_t6_candidate_expansion_runtime_enablement_implementation_plan_artifact. It is inspected but never echoed."
                    },
                    "reviewer": {
                        "type": "string",
                        "description": "Reviewer identity or handle authorizing the code-gate decision."
                    },
                    "code_gate_decision": {
                        "type": "string",
                        "enum": [
                            "approve_shadow_runtime_enablement_code_implementation_only",
                            "request_runtime_enablement_implementation_plan_changes",
                            "reject_runtime_enablement_code_implementation"
                        ],
                        "description": "Explicit code-gate decision. Only approve_shadow_runtime_enablement_code_implementation_only can open default-off shadow runtime-enablement code implementation; no value approves runtime execution or candidate expansion."
                    },
                    "decision_source": {
                        "type": "string",
                        "description": "External source for the code-gate decision, such as forum post id or chat checkpoint."
                    },
                    "commit": {
                        "type": "string",
                        "description": "Optional implementation commit under review."
                    },
                    "forum_post_id": {
                        "type": "string",
                        "description": "Optional forum post id linking this code gate."
                    },
                    "memory_key": {
                        "type": "string",
                        "description": "Optional memory key linking this code gate."
                    }
                }
            }),
        }
    }

    async fn execute(&self, args: Value, _ctx: &ToolContext) -> Result<ToolResult> {
        Ok(ToolResult::json_text(
            &memory_biocortex_t6_candidate_expansion_runtime_enablement_code_implementation_gate_payload(
                args,
            ),
        ))
    }
}

pub(super) fn memory_biocortex_t6_candidate_expansion_runtime_enablement_shadow_code_source_claims_runtime_authority(
    code_gate: &Value,
) -> bool {
    memory_biocortex_t6_any_true(
        code_gate,
        &[
            "/code_implementation_contract/may_enable_runtime_gate_now",
            "/code_implementation_contract/may_run_shadow_mode_now",
            "/code_implementation_contract/candidate_expansion_experiment_approved",
            "/code_implementation_contract/may_run_candidate_expansion_dry_run_now",
            "/code_implementation_contract/may_expand_candidate_set_now",
            "/code_implementation_contract/changes_candidate_set_now",
            "/code_implementation_contract/runtime_influence_approved",
            "/code_implementation_contract/may_change_search_order_now",
            "/code_implementation_contract/may_write_memory_or_graph_edges",
            "/code_implementation_contract/this_gate_approves_runtime_candidate_expansion",
            "/implementation_boundaries/default_runtime_enabled",
            "/implementation_boundaries/default_shadow_enabled",
            "/input_contract/runtime_enablement_implementation_plan_artifact_included",
            "/input_contract/runtime_enablement_owner_decision_record_included",
            "/input_contract/runtime_enablement_review_included",
            "/input_contract/shadow_telemetry_review_included",
            "/input_contract/shadow_executor_invocation_report_included",
            "/input_contract/runtime_gate_owner_review_record_included",
            "/input_contract/owner_decision_record_included",
            "/input_contract/human_review_packet_included",
            "/input_contract/dry_run_report_included",
            "/input_contract/dry_run_plan_included",
            "/input_contract/recall_expansion_summary_included",
            "/input_contract/case_rows_included",
            "/input_contract/raw_query_included",
            "/input_contract/raw_queries_included",
            "/input_contract/raw_keys_included",
            "/input_contract/content_included",
            "/input_contract/raw_error_included",
        ],
    )
}

pub(super) fn memory_biocortex_t6_candidate_expansion_runtime_enablement_shadow_code_payload(
    args: Value,
) -> Value {
    let code_gate = args
        .get("runtime_enablement_code_implementation_gate")
        .unwrap_or(&Value::Null);
    let reviewer =
        memory_biocortex_t6_candidate_expansion_shadow_execution_gate_string(&args, "reviewer");
    let decision_source = memory_biocortex_t6_candidate_expansion_shadow_execution_gate_string(
        &args,
        "decision_source",
    );
    let implementation_decision = args
        .get("implementation_decision")
        .and_then(Value::as_str)
        .map(str::trim)
        .filter(|s| !s.is_empty())
        .unwrap_or("missing_implementation_decision");
    let implementation_commit =
        memory_biocortex_t6_candidate_expansion_shadow_execution_gate_string(
            &args,
            "implementation_commit",
        );
    let forum_post_id = memory_biocortex_t6_candidate_expansion_shadow_execution_gate_string(
        &args,
        "forum_post_id",
    );
    let memory_key =
        memory_biocortex_t6_candidate_expansion_shadow_execution_gate_string(&args, "memory_key");
    let feature_flag_default_off_confirmed =
        memory_biocortex_t6_candidate_expansion_shadow_executor_invocation_report_bool(
            &args,
            "feature_flag_default_off_confirmed",
            false,
        );
    let runtime_entrypoint_default_off_confirmed =
        memory_biocortex_t6_candidate_expansion_shadow_executor_invocation_report_bool(
            &args,
            "runtime_entrypoint_default_off_confirmed",
            false,
        );
    let shadow_mode_default_off_confirmed =
        memory_biocortex_t6_candidate_expansion_shadow_executor_invocation_report_bool(
            &args,
            "shadow_mode_default_off_confirmed",
            false,
        );
    let deterministic_replay_fixture_present =
        memory_biocortex_t6_candidate_expansion_shadow_executor_invocation_report_bool(
            &args,
            "deterministic_replay_fixture_present",
            false,
        );
    let bounded_candidate_delta_guard_present =
        memory_biocortex_t6_candidate_expansion_shadow_executor_invocation_report_bool(
            &args,
            "bounded_candidate_delta_guard_present",
            false,
        );
    let negative_controls_present =
        memory_biocortex_t6_candidate_expansion_shadow_executor_invocation_report_bool(
            &args,
            "negative_controls_present",
            false,
        );
    let aggregate_telemetry_only_confirmed =
        memory_biocortex_t6_candidate_expansion_shadow_executor_invocation_report_bool(
            &args,
            "aggregate_telemetry_only_confirmed",
            false,
        );
    let rollback_path_confirmed =
        memory_biocortex_t6_candidate_expansion_shadow_executor_invocation_report_bool(
            &args,
            "rollback_path_confirmed",
            false,
        );

    let source_schema_valid = memory_biocortex_t6_string_at(code_gate, "/schema")
        == Some(
            MEMORY_BIOCORTEX_T6_CANDIDATE_EXPANSION_RUNTIME_ENABLEMENT_CODE_IMPLEMENTATION_GATE_SCHEMA,
        );
    let source_ready = memory_biocortex_t6_bool_at(
        code_gate,
        "/runtime_enablement_code_implementation_gate/ready",
    ) == Some(true);
    let source_status = memory_biocortex_t6_string_at(
        code_gate,
        "/runtime_enablement_code_implementation_gate/status",
    ) == Some("shadow_runtime_enablement_code_implementation_authorized");
    let source_next_gate = memory_biocortex_t6_string_at(
        code_gate,
        "/runtime_enablement_code_implementation_gate/decision/next_gate",
    ) == Some("implement_default_off_shadow_runtime_enablement_code");
    let source_contract_ok = memory_biocortex_t6_bool_at(code_gate, "/read_only") == Some(true)
        && memory_biocortex_t6_bool_at(
            code_gate,
            "/code_implementation_contract/may_implement_shadow_runtime_enablement_code",
        ) == Some(true)
        && memory_biocortex_t6_bool_at(
            code_gate,
            "/code_implementation_contract/may_enable_runtime_gate_now",
        ) == Some(false)
        && memory_biocortex_t6_bool_at(
            code_gate,
            "/code_implementation_contract/may_run_shadow_mode_now",
        ) == Some(false)
        && memory_biocortex_t6_bool_at(
            code_gate,
            "/code_implementation_contract/candidate_expansion_experiment_approved",
        ) == Some(false)
        && memory_biocortex_t6_bool_at(
            code_gate,
            "/code_implementation_contract/may_run_candidate_expansion_dry_run_now",
        ) == Some(false)
        && memory_biocortex_t6_bool_at(
            code_gate,
            "/code_implementation_contract/may_expand_candidate_set_now",
        ) == Some(false)
        && memory_biocortex_t6_bool_at(
            code_gate,
            "/code_implementation_contract/changes_candidate_set_now",
        ) == Some(false)
        && memory_biocortex_t6_bool_at(
            code_gate,
            "/code_implementation_contract/runtime_influence_approved",
        ) == Some(false)
        && memory_biocortex_t6_bool_at(
            code_gate,
            "/code_implementation_contract/may_change_search_order_now",
        ) == Some(false)
        && memory_biocortex_t6_bool_at(
            code_gate,
            "/code_implementation_contract/may_write_memory_or_graph_edges",
        ) == Some(false)
        && memory_biocortex_t6_bool_at(
            code_gate,
            "/code_implementation_contract/this_gate_approves_runtime_candidate_expansion",
        ) == Some(false)
        && memory_biocortex_t6_bool_at(
            code_gate,
            "/code_implementation_contract/requires_separate_shadow_execution_gate",
        ) == Some(true)
        && memory_biocortex_t6_bool_at(
            code_gate,
            "/code_implementation_contract/requires_separate_runtime_enablement_gate",
        ) == Some(true);
    let source_boundaries_ok = memory_biocortex_t6_bool_at(
        code_gate,
        "/implementation_boundaries/feature_flag_default_off",
    ) == Some(true)
        && memory_biocortex_t6_bool_at(code_gate, "/implementation_boundaries/shadow_mode_first")
            == Some(true)
        && memory_biocortex_t6_bool_at(
            code_gate,
            "/implementation_boundaries/default_runtime_enabled",
        ) == Some(false)
        && memory_biocortex_t6_bool_at(
            code_gate,
            "/implementation_boundaries/default_shadow_enabled",
        ) == Some(false)
        && memory_biocortex_t6_bool_at(
            code_gate,
            "/implementation_boundaries/deterministic_replay_fixture_required",
        ) == Some(true)
        && memory_biocortex_t6_bool_at(
            code_gate,
            "/implementation_boundaries/negative_controls_required",
        ) == Some(true)
        && memory_biocortex_t6_bool_at(
            code_gate,
            "/implementation_boundaries/bounded_candidate_delta_required",
        ) == Some(true)
        && memory_biocortex_t6_bool_at(code_gate, "/implementation_boundaries/rollback_required")
            == Some(true)
        && !memory_biocortex_t6_string_array_at(
            code_gate,
            "/implementation_boundaries/telemetry_fields",
        )
        .is_empty();
    let source_claims_runtime_authority =
        memory_biocortex_t6_candidate_expansion_runtime_enablement_shadow_code_source_claims_runtime_authority(code_gate);
    let source_contains_raw =
        memory_biocortex_t6_candidate_expansion_shadow_execution_gate_contains_raw(code_gate)
            || code_gate
                .get("runtime_enablement_implementation_plan_artifact")
                .is_some()
            || code_gate
                .get("runtime_enablement_owner_decision_record")
                .is_some()
            || code_gate.get("runtime_enablement_review").is_some()
            || code_gate.get("shadow_telemetry_review").is_some()
            || code_gate.get("shadow_executor_invocation_report").is_some()
            || code_gate.get("case_rows").is_some();
    let input_contains_raw =
        memory_biocortex_t6_candidate_expansion_shadow_execution_gate_contains_raw(&args);
    let implementation_decision_valid = matches!(
        implementation_decision,
        "accept_default_off_shadow_runtime_enablement_code"
            | "request_shadow_runtime_enablement_code_changes"
            | "reject_shadow_runtime_enablement_code"
    );
    let implementation_decision_accepts =
        implementation_decision == "accept_default_off_shadow_runtime_enablement_code";

    let mut block_reasons = BTreeSet::<String>::new();
    if !source_schema_valid {
        block_reasons.insert(
            "source_runtime_enablement_code_implementation_gate_schema_invalid".to_string(),
        );
    }
    if !source_ready || !source_status || !source_next_gate {
        block_reasons
            .insert("source_runtime_enablement_code_implementation_gate_not_ready".to_string());
    }
    if !source_contract_ok || source_claims_runtime_authority {
        block_reasons.insert(
            "source_runtime_enablement_code_implementation_gate_claims_runtime_authority"
                .to_string(),
        );
    }
    if !source_boundaries_ok {
        block_reasons.insert(
            "source_runtime_enablement_code_implementation_gate_requirements_incomplete"
                .to_string(),
        );
    }
    if source_contains_raw {
        block_reasons
            .insert("source_runtime_enablement_code_implementation_gate_contains_raw".to_string());
    }
    if input_contains_raw {
        block_reasons.insert("input_contains_raw_or_source_fields".to_string());
    }
    if reviewer.is_empty() {
        block_reasons.insert("missing_reviewer".to_string());
    }
    if decision_source.is_empty() {
        block_reasons.insert("missing_decision_source".to_string());
    }
    if implementation_commit.is_empty() {
        block_reasons.insert("missing_implementation_commit".to_string());
    }
    if !implementation_decision_valid || !implementation_decision_accepts {
        block_reasons.insert(
            "implementation_decision_not_accept_default_off_shadow_runtime_enablement_code"
                .to_string(),
        );
    }
    if !feature_flag_default_off_confirmed {
        block_reasons.insert("feature_flag_default_off_not_confirmed".to_string());
    }
    if !runtime_entrypoint_default_off_confirmed {
        block_reasons.insert("runtime_entrypoint_default_off_not_confirmed".to_string());
    }
    if !shadow_mode_default_off_confirmed {
        block_reasons.insert("shadow_mode_default_off_not_confirmed".to_string());
    }
    if !deterministic_replay_fixture_present {
        block_reasons.insert("deterministic_replay_fixture_missing".to_string());
    }
    if !bounded_candidate_delta_guard_present {
        block_reasons.insert("bounded_candidate_delta_guard_missing".to_string());
    }
    if !negative_controls_present {
        block_reasons.insert("negative_controls_missing".to_string());
    }
    if !aggregate_telemetry_only_confirmed {
        block_reasons.insert("aggregate_telemetry_only_not_confirmed".to_string());
    }
    if !rollback_path_confirmed {
        block_reasons.insert("rollback_path_not_confirmed".to_string());
    }
    for reason in memory_biocortex_t6_string_array_at(
        code_gate,
        "/runtime_enablement_code_implementation_gate/block_reasons",
    ) {
        memory_biocortex_t6_push_reason(&mut block_reasons, &reason);
    }

    let feature_flag_name =
        memory_biocortex_t6_string_at(code_gate, "/implementation_boundaries/feature_flag_name")
            .unwrap_or("");
    if feature_flag_name
        != MEMORY_BIOCORTEX_T6_CANDIDATE_EXPANSION_RUNTIME_ENABLEMENT_SHADOW_FEATURE_FLAG
    {
        block_reasons
            .insert("runtime_enablement_shadow_feature_flag_name_invalid".to_string());
    }

    let block_reasons: Vec<String> = block_reasons.into_iter().collect();
    let ready = block_reasons.is_empty();
    let status = if ready {
        "default_off_shadow_runtime_enablement_code_recorded"
    } else {
        "blocked_before_runtime_enablement_shadow_code_gate"
    };
    let next_gate = if ready {
        "author_review_shadow_execution_gate_before_any_shadow_run"
    } else {
        "repair_default_off_shadow_runtime_enablement_code"
    };
    let telemetry_fields = memory_biocortex_t6_string_array_at(
        code_gate,
        "/implementation_boundaries/telemetry_fields",
    );

    json!({
        "schema": MEMORY_BIOCORTEX_T6_CANDIDATE_EXPANSION_RUNTIME_ENABLEMENT_SHADOW_CODE_GATE_SCHEMA,
        "generated_at": unix_now_secs(),
        "read_only": true,
        "purpose": "T6 runtime-enablement shadow-code gate: record whether the default-off shadow runtime-enablement code implementation satisfies the previous code-implementation gate without enabling runtime execution, shadow mode, BioCortex, memory tools, candidate expansion, search-order changes, memory writes, graph writes, or feature flags.",
        "runtime_enablement_shadow_code_gate": {
            "ready": ready,
            "status": status,
            "block_reasons": block_reasons,
            "reviewer": reviewer,
            "implementation_decision": implementation_decision,
            "decision_source": decision_source,
            "implementation_commit": implementation_commit,
            "decision": {
                "verdict": status,
                "next_gate": next_gate,
                "default_off_shadow_code_only": true,
                "runtime_enablement_out_of_scope": true,
                "shadow_execution_out_of_scope": true,
                "runtime_authority_out_of_scope": true,
                "candidate_expansion_authority_out_of_scope": true,
            },
            "source_decision": {
                "code_gate_status": memory_biocortex_t6_string_at(code_gate, "/runtime_enablement_code_implementation_gate/status"),
                "code_gate_next_gate": memory_biocortex_t6_string_at(code_gate, "/runtime_enablement_code_implementation_gate/decision/next_gate"),
                "source_feature_flag_name": feature_flag_name,
            },
        },
        "implementation_evidence": {
            "feature_flag_name": feature_flag_name,
            "feature_flag_default_off_confirmed": feature_flag_default_off_confirmed,
            "runtime_entrypoint_default_off_confirmed": runtime_entrypoint_default_off_confirmed,
            "shadow_mode_default_off_confirmed": shadow_mode_default_off_confirmed,
            "deterministic_replay_fixture_present": deterministic_replay_fixture_present,
            "bounded_candidate_delta_guard_present": bounded_candidate_delta_guard_present,
            "negative_controls_present": negative_controls_present,
            "aggregate_telemetry_only_confirmed": aggregate_telemetry_only_confirmed,
            "rollback_path_confirmed": rollback_path_confirmed,
            "source_telemetry_fields": telemetry_fields,
        },
        "runtime_enablement_shadow_code_contract": {
            "default_off_shadow_code_recorded": ready,
            "may_run_shadow_mode_now": false,
            "may_enable_runtime_gate_now": false,
            "candidate_expansion_experiment_approved": false,
            "may_run_candidate_expansion_dry_run_now": false,
            "may_expand_candidate_set_now": false,
            "changes_candidate_set_now": false,
            "runtime_influence_approved": false,
            "may_change_search_order_now": false,
            "may_write_memory_or_graph_edges": false,
            "this_gate_approves_runtime_candidate_expansion": false,
            "this_tool_calls_memory_search": false,
            "this_tool_calls_memory_neighbors": false,
            "this_tool_runs_biocortex": false,
            "requires_separate_shadow_execution_gate": true,
            "requires_separate_runtime_enablement_gate": true,
        },
        "bounded_runtime_enablement_shadow_code": {
            "aggregate_telemetry_only_confirmed": aggregate_telemetry_only_confirmed,
            "raw_queries_allowed": false,
            "raw_keys_allowed": false,
            "content_allowed": false,
            "case_rows_allowed": false,
            "raw_errors_allowed": false,
            "production_traffic_allowed": false,
        },
        "links": {
            "commit": implementation_commit,
            "forum_post_id": forum_post_id,
            "memory_key": memory_key,
        },
        "input_contract": {
            "runtime_enablement_code_implementation_gate_included": false,
            "runtime_enablement_implementation_plan_artifact_included": false,
            "runtime_enablement_owner_decision_record_included": false,
            "runtime_enablement_review_included": false,
            "shadow_telemetry_review_included": false,
            "shadow_executor_invocation_report_included": false,
            "case_rows_included": false,
            "raw_query_included": false,
            "raw_queries_included": false,
            "raw_keys_included": false,
            "content_included": false,
            "raw_error_included": false,
        },
        "non_goals": [
            "This tool does not enable a runtime gate.",
            "This tool does not run shadow mode or invoke executors.",
            "This tool does not run BioCortex.",
            "This tool does not call memory_search or memory_neighbors.",
            "This tool does not sample production memories or graph rows.",
            "This tool does not echo runtime-enablement code-implementation gate payloads, implementation-plan artifacts, owner-decision records, runtime-enablement reviews, shadow telemetry reviews, shadow executor invocation reports, case rows, queries, keys, content, or raw errors.",
            "This tool does not write memory, graph edges, authorization records, approval packets, feature flags, runtime configuration, or telemetry.",
            "This tool does not approve shadow execution, runtime influence, search-order changes, dry-run execution, candidate-set expansion, or production candidate expansion."
        ],
    })
}

pub struct MemoryBioCortexT6CandidateExpansionRuntimeEnablementShadowCodeGateTool;
impl MemoryBioCortexT6CandidateExpansionRuntimeEnablementShadowCodeGateTool {
    pub fn new() -> Self {
        Self
    }
}

impl Default for MemoryBioCortexT6CandidateExpansionRuntimeEnablementShadowCodeGateTool {
    fn default() -> Self {
        Self::new()
    }
}

#[async_trait]
impl McpTool for MemoryBioCortexT6CandidateExpansionRuntimeEnablementShadowCodeGateTool {
    fn name(&self) -> &'static str {
        "memory_biocortex_t6_candidate_expansion_runtime_enablement_shadow_code_gate"
    }

    fn schema(&self) -> ToolSchema {
        ToolSchema {
            name: self.name().into(),
            description: "Read-only T6 runtime-enablement shadow-code gate. \
                Consumes the prior runtime-enablement code-implementation gate \
                plus explicit implementation evidence and can only record that \
                default-off shadow runtime-enablement code is ready for a later \
                shadow-execution gate; it never enables runtime execution, runs \
                shadow mode, calls BioCortex or memory tools, changes candidate \
                sets/search order, writes memory/graph edges, or approves \
                production candidate expansion."
                .into(),
            input_schema: json!({
                "type": "object",
                "required": [
                    "runtime_enablement_code_implementation_gate",
                    "reviewer",
                    "implementation_decision",
                    "decision_source",
                    "implementation_commit",
                    "feature_flag_default_off_confirmed",
                    "runtime_entrypoint_default_off_confirmed",
                    "shadow_mode_default_off_confirmed",
                    "deterministic_replay_fixture_present",
                    "bounded_candidate_delta_guard_present",
                    "negative_controls_present",
                    "aggregate_telemetry_only_confirmed",
                    "rollback_path_confirmed"
                ],
                "properties": {
                    "runtime_enablement_code_implementation_gate": {
                        "type": "object",
                        "description": "JSON object produced by memory_biocortex_t6_candidate_expansion_runtime_enablement_code_implementation_gate. It is inspected but never echoed."
                    },
                    "reviewer": {
                        "type": "string",
                        "description": "Reviewer identity or handle validating the default-off shadow runtime-enablement code."
                    },
                    "implementation_decision": {
                        "type": "string",
                        "enum": [
                            "accept_default_off_shadow_runtime_enablement_code",
                            "request_shadow_runtime_enablement_code_changes",
                            "reject_shadow_runtime_enablement_code"
                        ],
                        "description": "Only accept_default_off_shadow_runtime_enablement_code can open the later shadow-execution gate."
                    },
                    "decision_source": {
                        "type": "string",
                        "description": "External source for the implementation review decision, such as a forum post id."
                    },
                    "implementation_commit": {
                        "type": "string",
                        "description": "Commit or build identifier for the default-off shadow runtime-enablement code under review."
                    },
                    "forum_post_id": {
                        "type": "string",
                        "description": "Optional forum post id linking this gate."
                    },
                    "memory_key": {
                        "type": "string",
                        "description": "Optional memory key linking this gate."
                    },
                    "feature_flag_default_off_confirmed": {
                        "type": "boolean",
                        "description": "Must be true: feature flag remains default-off."
                    },
                    "runtime_entrypoint_default_off_confirmed": {
                        "type": "boolean",
                        "description": "Must be true: runtime entrypoint remains disabled by default."
                    },
                    "shadow_mode_default_off_confirmed": {
                        "type": "boolean",
                        "description": "Must be true: shadow execution remains disabled by default."
                    },
                    "deterministic_replay_fixture_present": {
                        "type": "boolean",
                        "description": "Must be true before any later shadow-execution gate can be reviewed."
                    },
                    "bounded_candidate_delta_guard_present": {
                        "type": "boolean",
                        "description": "Must be true: candidate deltas remain bounded aggregate counts only."
                    },
                    "negative_controls_present": {
                        "type": "boolean",
                        "description": "Must be true: negative controls exist and block later shadow execution on regression."
                    },
                    "aggregate_telemetry_only_confirmed": {
                        "type": "boolean",
                        "description": "Must be true: telemetry remains aggregate-only and excludes raw queries, keys, content, rows, and raw errors."
                    },
                    "rollback_path_confirmed": {
                        "type": "boolean",
                        "description": "Must be true: rollback path exists before later gates."
                    }
                }
            }),
        }
    }

    async fn execute(&self, args: Value, _ctx: &ToolContext) -> Result<ToolResult> {
        Ok(ToolResult::json_text(
            &memory_biocortex_t6_candidate_expansion_runtime_enablement_shadow_code_payload(args),
        ))
    }
}

pub(super) const MEMORY_NEURAL_CRITIC_SHADOW_EVAL_SCHEMA: &str =
    "agent_bridge.memory_neural_critic_shadow_eval.v0";
pub(super) const MEMORY_NEURAL_CRITIC_LABELS: [&str; 5] =
    ["stale", "duplicate", "missing", "too_large", "ok"];

pub(super) fn memory_neural_critic_round3(value: f64) -> f64 {
    (value * 1000.0).round() / 1000.0
}

pub(super) fn memory_neural_critic_label_at(value: &Value, key: &str) -> Option<String> {
    value
        .get(key)
        .and_then(Value::as_str)
        .map(str::trim)
        .filter(|label| !label.is_empty())
        .map(|label| label.to_ascii_lowercase())
}

pub(super) fn memory_neural_critic_label_valid(label: &str) -> bool {
    MEMORY_NEURAL_CRITIC_LABELS.contains(&label)
}

pub(super) fn memory_neural_critic_push_reason(reasons: &mut BTreeSet<String>, reason: &str) {
    reasons.insert(reason.to_string());
}

pub(super) fn memory_neural_critic_case_hash(value: &Value, fallback_index: usize) -> String {
    let case_id = value
        .get("case_id")
        .and_then(Value::as_str)
        .map(str::trim)
        .filter(|s| !s.is_empty())
        .map(str::to_string)
        .unwrap_or_else(|| format!("case:{fallback_index}"));
    memory_biocortex_sha256_json(&json!({ "case_id": case_id }))
}

pub(super) fn memory_neural_critic_has_raw_fields(value: &Value) -> bool {
    ["raw_query", "raw_key", "raw_keys", "memory_key", "content"]
        .iter()
        .any(|field| value.get(*field).is_some())
}

pub(super) fn memory_neural_critic_shadow_eval_payload(args: Value) -> Value {
    let cases = args
        .get("cases")
        .and_then(Value::as_array)
        .cloned()
        .unwrap_or_default();
    let min_cases = args
        .get("min_cases")
        .and_then(Value::as_u64)
        .unwrap_or(20)
        .clamp(1, 10_000);
    let min_delta_accuracy = args
        .get("min_delta_accuracy")
        .and_then(Value::as_f64)
        .unwrap_or(0.01)
        .max(0.0);
    let max_critic_regressions = args
        .get("max_critic_regressions")
        .and_then(Value::as_u64)
        .unwrap_or(0);

    let mut block_reasons = BTreeSet::<String>::new();
    if cases.is_empty() {
        memory_neural_critic_push_reason(&mut block_reasons, "missing_heldout_cases");
    }

    let mut valid_case_count = 0u64;
    let mut deterministic_correct = 0u64;
    let mut critic_correct = 0u64;
    let mut critic_fixes = 0u64;
    let mut critic_regressions = 0u64;
    let mut invalid_label_count = 0u64;
    let mut input_raw_fields_ignored_count = 0u64;
    let mut label_counts = BTreeMap::<String, u64>::new();
    let mut redacted_case_rows = Vec::<Value>::new();

    for (idx, case) in cases.iter().enumerate() {
        if memory_neural_critic_has_raw_fields(case) {
            input_raw_fields_ignored_count += 1;
        }
        let expected = memory_neural_critic_label_at(case, "expected_label");
        let deterministic = memory_neural_critic_label_at(case, "deterministic_label");
        let critic = memory_neural_critic_label_at(case, "critic_label");
        let labels_valid = expected
            .as_deref()
            .map(memory_neural_critic_label_valid)
            .unwrap_or(false)
            && deterministic
                .as_deref()
                .map(memory_neural_critic_label_valid)
                .unwrap_or(false)
            && critic
                .as_deref()
                .map(memory_neural_critic_label_valid)
                .unwrap_or(false);
        if !labels_valid {
            invalid_label_count += 1;
            continue;
        }
        let expected = expected.expect("valid expected label");
        let deterministic = deterministic.expect("valid deterministic label");
        let critic = critic.expect("valid critic label");
        valid_case_count += 1;
        *label_counts.entry(expected.clone()).or_default() += 1;

        let deterministic_hit = deterministic == expected;
        let critic_hit = critic == expected;
        if deterministic_hit {
            deterministic_correct += 1;
        }
        if critic_hit {
            critic_correct += 1;
        }
        if !deterministic_hit && critic_hit {
            critic_fixes += 1;
        }
        if deterministic_hit && !critic_hit {
            critic_regressions += 1;
        }
        if redacted_case_rows.len() < 20 {
            redacted_case_rows.push(json!({
                "case_hash": memory_neural_critic_case_hash(case, idx),
                "expected_label": expected,
                "deterministic_label": deterministic,
                "critic_label": critic,
                "deterministic_correct": deterministic_hit,
                "critic_correct": critic_hit,
            }));
        }
    }

    if invalid_label_count > 0 {
        memory_neural_critic_push_reason(&mut block_reasons, "invalid_or_missing_labels");
    }
    if valid_case_count < min_cases {
        memory_neural_critic_push_reason(&mut block_reasons, "insufficient_heldout_cases");
    }

    let deterministic_accuracy = if valid_case_count == 0 {
        0.0
    } else {
        deterministic_correct as f64 / valid_case_count as f64
    };
    let critic_accuracy = if valid_case_count == 0 {
        0.0
    } else {
        critic_correct as f64 / valid_case_count as f64
    };
    let delta_accuracy = critic_accuracy - deterministic_accuracy;
    let critic_beats_deterministic =
        critic_accuracy > deterministic_accuracy && delta_accuracy >= min_delta_accuracy;
    if !critic_beats_deterministic {
        memory_neural_critic_push_reason(
            &mut block_reasons,
            "critic_does_not_beat_deterministic_baseline",
        );
    }
    if critic_regressions > max_critic_regressions {
        memory_neural_critic_push_reason(&mut block_reasons, "critic_regressions_exceed_max");
    }

    let ready_for_review = block_reasons.is_empty();
    let block_reasons = block_reasons.into_iter().collect::<Vec<_>>();

    json!({
        "schema": MEMORY_NEURAL_CRITIC_SHADOW_EVAL_SCHEMA,
        "generated_at": unix_now_secs(),
        "read_only": true,
        "purpose": "T7 offline neural-critic shadow eval: compare externally produced critic labels against deterministic T3/T4 baseline labels on held-out cases before granting any write or ranking authority.",
        "ready_for_review": ready_for_review,
        "critic_beats_deterministic": critic_beats_deterministic,
        "critic_write_authority": false,
        "may_write_memory_now": false,
        "changes_memory_search_order": false,
        "default_search_order_change_allowed": false,
        "runs_neural_model": false,
        "calls_memory_search": false,
        "writes_memory": false,
        "block_reasons": block_reasons,
        "decision": {
            "verdict": if ready_for_review { "ready_for_human_review" } else { "blocked" },
            "next_gate": if ready_for_review {
                "human_review_before_any_write_or_ranking_authority"
            } else {
                "collect_more_or_better_heldout_critic_evidence"
            },
            "human_review_required": true,
            "write_or_ranking_authority_out_of_scope": true,
        },
        "thresholds": {
            "min_cases": min_cases,
            "min_delta_accuracy": min_delta_accuracy,
            "max_critic_regressions": max_critic_regressions,
        },
        "metrics": {
            "case_count": valid_case_count,
            "submitted_case_count": cases.len(),
            "invalid_label_count": invalid_label_count,
            "deterministic_correct": deterministic_correct,
            "critic_correct": critic_correct,
            "deterministic_accuracy": memory_neural_critic_round3(deterministic_accuracy),
            "critic_accuracy": memory_neural_critic_round3(critic_accuracy),
            "delta_accuracy": memory_neural_critic_round3(delta_accuracy),
            "critic_fixes": critic_fixes,
            "critic_regressions": critic_regressions,
            "input_raw_fields_ignored_count": input_raw_fields_ignored_count,
        },
        "label_counts": label_counts,
        "redacted_case_rows": redacted_case_rows,
        "labels_supported": MEMORY_NEURAL_CRITIC_LABELS,
        "input_contract": {
            "cases_included": false,
            "raw_query_included": false,
            "raw_queries_included": false,
            "raw_keys_included": false,
            "content_included": false,
            "critic_scores_are_external": true,
        },
        "non_goals": [
            "Does not run a neural model.",
            "Does not train, fine-tune, or persist model weights.",
            "Does not call memory_search.",
            "Does not write memories, graph edges, feedback labels, or consolidation decisions.",
            "Does not grant write authority, ranking authority, or default retrieval influence.",
            "Does not echo raw case ids, memory keys, queries, or content."
        ],
    })
}

// ===========================================================================
//          memory_neural_critic_shadow_eval — T7 offline critic evaluator
// ===========================================================================

pub struct MemoryNeuralCriticShadowEvalTool;
impl MemoryNeuralCriticShadowEvalTool {
    pub fn new() -> Self {
        Self
    }
}
#[async_trait]
impl McpTool for MemoryNeuralCriticShadowEvalTool {
    fn name(&self) -> &'static str {
        "memory_neural_critic_shadow_eval"
    }
    fn schema(&self) -> ToolSchema {
        ToolSchema {
            name: self.name().into(),
            description: "Read-only T7 offline neural-critic evaluator for AB memory. \
                Compares externally produced critic labels against deterministic T3/T4 \
                baseline labels on held-out stale/duplicate/missing/too_large/ok cases. \
                It does not run a model, train weights, call memory_search, write memory, \
                expose raw case ids/keys/content, change retrieval order, or grant critic \
                write/ranking authority."
                .into(),
            input_schema: json!({
                "type": "object",
                "properties": {
                    "cases": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "case_id": { "type": "string" },
                                "expected_label": {
                                    "type": "string",
                                    "enum": MEMORY_NEURAL_CRITIC_LABELS
                                },
                                "deterministic_label": {
                                    "type": "string",
                                    "enum": MEMORY_NEURAL_CRITIC_LABELS
                                },
                                "critic_label": {
                                    "type": "string",
                                    "enum": MEMORY_NEURAL_CRITIC_LABELS
                                },
                                "critic_score": { "type": "number" }
                            }
                        },
                        "default": [],
                        "description": "Held-out offline eval rows. Output includes only hash/redacted rows."
                    },
                    "min_cases": {
                        "type": "integer",
                        "minimum": 1,
                        "maximum": 10000,
                        "default": 20
                    },
                    "min_delta_accuracy": {
                        "type": "number",
                        "minimum": 0.0,
                        "default": 0.01
                    },
                    "max_critic_regressions": {
                        "type": "integer",
                        "minimum": 0,
                        "default": 0
                    }
                }
            }),
        }
    }

    async fn execute(&self, args: Value, _ctx: &ToolContext) -> Result<ToolResult> {
        Ok(ToolResult::json_text(
            &memory_neural_critic_shadow_eval_payload(args),
        ))
    }
}

