//! BioCortex retrieval opt-in surface: shadow digest, replay compare, the opt-in gate/ceremony packet chain, gated trials/diagnostics, relevance-lift eval, runtime readiness/transition gate, and the retrieval shadow report.
//! Extracted verbatim from `mcp_tools.rs` (2026-07 split, step 2); the
//! only mechanical delta is `pub(super)` on previously-private top-level
//! items (9 promoted) so the parent module and its other children
//! (tests.rs) keep seeing them through the parent's glob re-export.

use super::*;

// ===========================================================================
//       biocortex_shadow_digest — shadow-only external BioCortex adapter
// ===========================================================================

/// Read-only BioCortex integration probe. This runs a sanctioned adapter
/// example from a local `biocortex-rs` checkout and projects its deterministic
/// `key=value` report into AB JSON. It intentionally does not link BioCortex
/// into the AB runtime or mutate AB memory/retrieval state.
pub struct BioCortexShadowDigestTool;

impl BioCortexShadowDigestTool {
    pub fn new() -> Self {
        Self
    }
}

impl Default for BioCortexShadowDigestTool {
    fn default() -> Self {
        Self::new()
    }
}

#[async_trait]
impl McpTool for BioCortexShadowDigestTool {
    fn name(&self) -> &'static str {
        "biocortex_shadow_digest"
    }

    fn schema(&self) -> ToolSchema {
        ToolSchema {
            name: self.name().into(),
            description: "Read-only BioCortex shadow digest. Runs a sanctioned \
                 local biocortex-rs adapter example via `cargo run --offline` and \
                 returns AB JSON. Does not link BioCortex into the AB runtime, \
                 mutate AB memory, or alter retrieval vectors."
                .into(),
            input_schema: json!({
                "type": "object",
                "properties": {
                    "checkout_path": {
                        "type": "string",
                        "description": "Optional local biocortex-rs checkout. Defaults to AB_BIOCORTEX_RS, sibling checkout paths, then /tmp/biocortex-rs-ab-eval."
                    },
                    "benchmark": {
                        "type": "string",
                        "enum": supported_benchmarks(),
                        "default": "scaled_morphology",
                        "description": "Adapter benchmark to run."
                    },
                    "timeout_ms": {
                        "type": "integer",
                        "minimum": 1000,
                        "maximum": 600000,
                        "default": 120000,
                        "description": "External adapter timeout in milliseconds."
                    },
                    "include_raw": {
                        "type": "boolean",
                        "default": false,
                        "description": "Include raw stdout/stderr from the external adapter."
                    }
                }
            }),
        }
    }

    async fn execute(&self, args: Value, _ctx: &ToolContext) -> Result<ToolResult> {
        let checkout = args
            .get("checkout_path")
            .and_then(|v| v.as_str())
            .map(str::trim)
            .filter(|s| !s.is_empty())
            .map(PathBuf::from);
        let benchmark = args
            .get("benchmark")
            .and_then(|v| v.as_str())
            .unwrap_or("scaled_morphology")
            .to_string();
        let timeout_ms = args
            .get("timeout_ms")
            .and_then(|v| v.as_u64())
            .unwrap_or(120_000);
        let include_raw = args
            .get("include_raw")
            .and_then(|v| v.as_bool())
            .unwrap_or(false);

        let payload = biocortex_shadow_digest(BioCortexShadowOptions {
            checkout,
            benchmark,
            timeout_ms,
            include_raw,
            fixture_projection: None,
        })
        .await;
        Ok(ToolResult::json_text(&json!({
            "checkout_env": BIOCORTEX_CHECKOUT_ENV,
            "digest": payload,
        })))
    }
}

// ===========================================================================
//  biocortex_replay_compare — AB fixture projection + BioCortex shadow digest
// ===========================================================================

/// Read-only comparison between an AB shadow-cortex replay fixture and a
/// BioCortex sanctioned shadow report. This is not a training bridge: current
/// BioCortex examples do not consume AB events, and this tool does not change
/// memory retrieval.
pub struct BioCortexReplayCompareTool {
    hub: Hub,
}

impl BioCortexReplayCompareTool {
    pub fn new(hub: Hub) -> Self {
        Self { hub }
    }
}

#[async_trait]
impl McpTool for BioCortexReplayCompareTool {
    fn name(&self) -> &'static str {
        "biocortex_replay_compare"
    }

    fn schema(&self) -> ToolSchema {
        ToolSchema {
            name: self.name().into(),
            description: "Read-only BioCortex replay comparison. Collects an AB \
                 shadow-cortex fixture from state.db, projects it into a stable \
                 replay summary, then runs a sanctioned local biocortex-rs shadow \
                 adapter side-by-side. BioCortex does not yet consume AB events; \
                 retrieval vectors and AB memory remain unchanged."
                .into(),
            input_schema: json!({
                "type": "object",
                "properties": {
                    "window_days": {
                        "type": "integer",
                        "minimum": 1,
                        "maximum": 365,
                        "default": 7,
                        "description": "Look-back window for AB shadow-cortex fixture collection."
                    },
                    "source": {
                        "type": "string",
                        "default": "all",
                        "description": "Source selector: all | mcp_dispatch | memory | forum | codex."
                    },
                    "checkout_path": {
                        "type": "string",
                        "description": "Optional local biocortex-rs checkout. Defaults to AB_BIOCORTEX_RS, sibling checkout paths, then /tmp/biocortex-rs-ab-eval."
                    },
                    "benchmark": {
                        "type": "string",
                        "enum": supported_benchmarks(),
                        "default": "ab_fixture_projection",
                        "description": "BioCortex shadow benchmark to run side-by-side."
                    },
                    "timeout_ms": {
                        "type": "integer",
                        "minimum": 1000,
                        "maximum": 600000,
                        "default": 120000,
                        "description": "External adapter timeout in milliseconds."
                    },
                    "include_raw": {
                        "type": "boolean",
                        "default": false,
                        "description": "Include raw stdout/stderr from the external BioCortex adapter."
                    },
                    "include_events": {
                        "type": "boolean",
                        "default": false,
                        "description": "Include every projected AB event instead of only a compact preview."
                    }
                }
            }),
        }
    }

    async fn execute(&self, args: Value, _ctx: &ToolContext) -> Result<ToolResult> {
        let Some(store) = &self.hub.store else {
            return Ok(ToolResult::error("no store configured"));
        };
        let window_days = args
            .get("window_days")
            .and_then(|v| v.as_u64())
            .map(|n| n as u32)
            .unwrap_or(7);
        let source = args
            .get("source")
            .and_then(|v| v.as_str())
            .unwrap_or("all")
            .to_string();
        let checkout = args
            .get("checkout_path")
            .and_then(|v| v.as_str())
            .map(str::trim)
            .filter(|s| !s.is_empty())
            .map(PathBuf::from);
        let benchmark = args
            .get("benchmark")
            .and_then(|v| v.as_str())
            .unwrap_or("ab_fixture_projection")
            .to_string();
        let timeout_ms = args
            .get("timeout_ms")
            .and_then(|v| v.as_u64())
            .unwrap_or(120_000);
        let include_raw = args
            .get("include_raw")
            .and_then(|v| v.as_bool())
            .unwrap_or(false);
        let include_events = args
            .get("include_events")
            .and_then(|v| v.as_bool())
            .unwrap_or(false);

        let fixture = crate::shadow_cortex::collect_shadow_cortex_fixture(
            store.as_ref(),
            crate::shadow_cortex::ShadowCortexOptions {
                window_days,
                source,
            },
        )
        .await
        .map_err(|e| ab_core::Error::Backend(format!("collect shadow-cortex fixture: {e}")))?;
        let payload = biocortex_replay_comparison(
            &fixture,
            BioCortexReplayComparisonOptions {
                checkout,
                benchmark,
                timeout_ms,
                include_raw,
                include_events,
            },
        )
        .await;
        Ok(ToolResult::json_text(&json!({
            "checkout_env": BIOCORTEX_CHECKOUT_ENV,
            "comparison": payload,
        })))
    }
}

// ===========================================================================
//  biocortex_retrieval_opt_in_status — read-only opt-in gate/audit report
// ===========================================================================

/// Read-only BioCortex retrieval opt-in status surface. This tool reports the
/// gate and audit shape for a hypothetical per-call opt-in request. It does not
/// call `memory_search`, run BioCortex, include raw memory content, or change
/// retrieval order.
pub struct BioCortexRetrievalOptInStatusTool;

impl BioCortexRetrievalOptInStatusTool {
    pub fn new() -> Self {
        Self
    }
}

impl Default for BioCortexRetrievalOptInStatusTool {
    fn default() -> Self {
        Self::new()
    }
}

#[async_trait]
impl McpTool for BioCortexRetrievalOptInStatusTool {
    fn name(&self) -> &'static str {
        "biocortex_retrieval_opt_in_status"
    }

    fn schema(&self) -> ToolSchema {
        ToolSchema {
            name: self.name().into(),
            description: "Read-only BioCortex retrieval opt-in status/audit \
                 report. Reports feature/runtime/per-call gate state and an \
                 audit-shape preview with hashed query/order data only. Does \
                 not call memory_search, run BioCortex, mutate memory, include \
                 raw memory keys/content, register an EmbeddingBackend, or \
                 alter retrieval order."
                .into(),
            input_schema: json!({
                "type": "object",
                "properties": {
                    "mode": {
                        "type": "string",
                        "enum": ["fts", "hybrid", "semantic"],
                        "default": "fts",
                        "description": "Retrieval mode under review. Only fts is authorized for opt-in work."
                    },
                    "per_call_opt_in": {
                        "type": "boolean",
                        "default": false,
                        "description": "Explicit per-call opt-in bit to evaluate."
                    },
                    "query": {
                        "type": "string",
                        "description": "Optional query text. Output includes only a hash."
                    },
                    "baseline_keys": {
                        "type": "array",
                        "items": { "type": "string" },
                        "description": "Optional baseline candidate keys. Output includes only count/hash, never raw keys."
                    },
                    "side_signal_status": {
                        "type": "string",
                        "description": "Optional side-signal status label for audit-shape previews."
                    },
                    "fallback_reason": {
                        "type": "string",
                        "description": "Optional fallback reason override for audit-shape previews."
                    },
                    "latency_ms": {
                        "type": "number",
                        "description": "Optional latency in milliseconds for audit-shape previews."
                    },
                    "runtime_readiness_packet": {
                        "type": "object",
                        "description": "Optional JSON object produced by biocortex_retrieval_opt_in_runtime_readiness_packet. The status tool consumes only safe summary fields and never echoes the packet."
                    },
                    "runtime_transition_gate": {
                        "type": "object",
                        "description": "Optional JSON object produced by biocortex_retrieval_opt_in_runtime_transition_gate. The status tool consumes only safe summary fields and never echoes the gate."
                    },
                    "gated_store_trial": {
                        "type": "object",
                        "description": "Optional JSON object produced by biocortex_retrieval_opt_in_gated_store_trial. The status tool consumes only safe summary fields and never echoes query data."
                    },
                    "gated_batch_diagnostics": {
                        "type": "object",
                        "description": "Optional JSON object produced by biocortex_retrieval_opt_in_gated_batch_diagnostics. The status tool consumes only safe summary fields and never echoes query rows."
                    }
                }
            }),
        }
    }

    async fn execute(&self, args: Value, _ctx: &ToolContext) -> Result<ToolResult> {
        let mode = args
            .get("mode")
            .and_then(Value::as_str)
            .unwrap_or("fts")
            .to_string();
        let per_call_opt_in = args
            .get("per_call_opt_in")
            .and_then(Value::as_bool)
            .unwrap_or(false);
        let query = args
            .get("query")
            .and_then(Value::as_str)
            .map(str::to_string);
        let baseline_keys = args
            .get("baseline_keys")
            .cloned()
            .map(serde_json::from_value::<Vec<String>>)
            .transpose()
            .map_err(|e| ab_core::Error::Backend(format!("parse baseline_keys: {e}")))?
            .unwrap_or_default();
        let side_signal_status = args
            .get("side_signal_status")
            .and_then(Value::as_str)
            .map(str::to_string);
        let fallback_reason = args
            .get("fallback_reason")
            .and_then(Value::as_str)
            .map(str::to_string);
        let latency_ms = args.get("latency_ms").and_then(Value::as_f64);
        let runtime_readiness_packet = args.get("runtime_readiness_packet").cloned();
        let runtime_transition_gate = args.get("runtime_transition_gate").cloned();
        let gated_store_trial = args.get("gated_store_trial").cloned();
        let gated_batch_diagnostics = args.get("gated_batch_diagnostics").cloned();

        let payload =
            biocortex_retrieval_opt_in_audit_report(BioCortexRetrievalOptInAuditOptions {
                mode,
                per_call_opt_in,
                query,
                baseline_keys,
                side_signal_status,
                fallback_reason,
                latency_ms,
                runtime_readiness_packet,
                runtime_transition_gate,
                gated_store_trial,
                gated_batch_diagnostics,
            });
        Ok(ToolResult::json_text(&payload))
    }
}

// ===========================================================================
//  trigger_recall_opt_in_status - read-only trigger recall opt-in gate status
// ===========================================================================

/// Read-only trigger-recall opt-in status surface. Reports runtime env,
/// per-call opt-in, local FTS scope, regression anchor, and redacted eval
/// metric readiness before any transition gate. It does not call
/// `memory_search`, inspect memory rows, record coactivation, or authorize
/// hold/enforcement behavior.
pub struct TriggerRecallOptInStatusTool;

impl TriggerRecallOptInStatusTool {
    pub fn new() -> Self {
        Self
    }
}

impl Default for TriggerRecallOptInStatusTool {
    fn default() -> Self {
        Self::new()
    }
}

pub(super) fn trigger_recall_mcp_arg_u64(args: &Value, key: &str) -> Option<u64> {
    args.get(key).and_then(Value::as_u64)
}

pub(super) fn trigger_recall_trial_unexpected_raw_fields(args: &Value) -> bool {
    let mut redacted_boundary = args.clone();
    if let Some(obj) = redacted_boundary.as_object_mut() {
        obj.remove("query");
        obj.remove("runtime_transition_gate");
    }
    trigger_recall_value_contains_raw(&redacted_boundary)
}

pub(super) fn trigger_recall_baseline_trial_hit(
    hit: &MemorySearchHit,
) -> TriggerRecallOptInGatedBaselineTrialHit {
    TriggerRecallOptInGatedBaselineTrialHit {
        key: hit.record.key.clone(),
        kind: hit.record.kind.clone(),
        score: hit.score,
        scope: hit.record.scope.clone(),
        created_at: hit.record.created_at,
        updated_at: hit.record.updated_at,
        tags_count: hit.record.tags.len(),
    }
}

#[async_trait]
impl McpTool for TriggerRecallOptInStatusTool {
    fn name(&self) -> &'static str {
        "trigger_recall_opt_in_status"
    }

    fn schema(&self) -> ToolSchema {
        ToolSchema {
            name: self.name().into(),
            description: "Read-only trigger recall opt-in status surface. \
                 Reports runtime env, per-call opt-in, fts/local scope, \
                 regression-anchor, and redacted eval-metric readiness before \
                 any runtime transition gate. Does not call memory_search, \
                 inspect memory rows, return raw query/keys/content, record \
                 coactivation, write memory, change default search, or \
                 authorize enforce_hold."
                .into(),
            input_schema: json!({
                "type": "object",
                "properties": {
                    "mode": { "type": "string", "enum": ["fts", "hybrid", "semantic"], "default": "fts" },
                    "per_call_opt_in": { "type": "boolean", "default": false },
                    "scope": { "type": "string", "description": "Exact local project scope, e.g. project:/abs/path. Output includes only a hash." },
                    "scope_mode": {
                        "type": "string",
                        "enum": ["local_only", "local_plus_global", "exploratory"],
                        "default": "local_only"
                    },
                    "regression_anchor": { "type": "string" },
                    "aio2_corpus_ready": { "type": "boolean" },
                    "union_cont_misses": { "type": "integer", "minimum": 0 },
                    "union_cont_false_hits": { "type": "integer", "minimum": 0 },
                    "baseline_shadow_true_hits_lost": { "type": "integer", "minimum": 0 },
                    "baseline_shadow_positive_cases_held": { "type": "integer", "minimum": 0 },
                    "baseline_shadow_false_hits_after_gate": { "type": "integer", "minimum": 0 },
                    "metric_captured_at": { "type": "string" },
                    "operator_disabled": { "type": "boolean", "default": false }
                }
            }),
        }
    }

    async fn execute(&self, args: Value, _ctx: &ToolContext) -> Result<ToolResult> {
        let operator_disabled = args
            .get("operator_disabled")
            .and_then(Value::as_bool)
            .unwrap_or(false)
            || mcp_env_truthy(TRIGGER_RECALL_DISABLE_ENV);
        let payload = trigger_recall_opt_in_status(TriggerRecallOptInStatusOptions {
            mode: args.get("mode").and_then(Value::as_str).unwrap_or("fts").to_string(),
            per_call_opt_in: args
                .get("per_call_opt_in")
                .and_then(Value::as_bool)
                .unwrap_or(false),
            scope: args.get("scope").and_then(Value::as_str).map(str::to_string),
            scope_mode: args
                .get("scope_mode")
                .and_then(Value::as_str)
                .unwrap_or("local_only")
                .to_string(),
            regression_anchor: args
                .get("regression_anchor")
                .and_then(Value::as_str)
                .map(str::to_string),
            aio2_corpus_ready: args.get("aio2_corpus_ready").and_then(Value::as_bool),
            union_cont_misses: trigger_recall_mcp_arg_u64(&args, "union_cont_misses"),
            union_cont_false_hits: trigger_recall_mcp_arg_u64(&args, "union_cont_false_hits"),
            baseline_shadow_true_hits_lost: trigger_recall_mcp_arg_u64(
                &args,
                "baseline_shadow_true_hits_lost",
            ),
            baseline_shadow_positive_cases_held: trigger_recall_mcp_arg_u64(
                &args,
                "baseline_shadow_positive_cases_held",
            ),
            baseline_shadow_false_hits_after_gate: trigger_recall_mcp_arg_u64(
                &args,
                "baseline_shadow_false_hits_after_gate",
            ),
            metric_captured_at: args
                .get("metric_captured_at")
                .and_then(Value::as_str)
                .map(str::to_string),
            runtime_enabled: mcp_env_truthy(TRIGGER_RECALL_OPT_IN_ENABLE_ENV),
            operator_disabled,
            raw_payload_fields_present: trigger_recall_value_contains_raw(&args),
        });
        Ok(ToolResult::json_text(&payload))
    }
}

// ===========================================================================
//  trigger_recall_opt_in_runtime_transition_gate - read-only gate
// ===========================================================================

/// Read-only trigger-recall opt-in runtime transition gate. Consumes a status
/// packet plus requested transition shape and reports whether a later gated
/// baseline trial may be called. It never calls `memory_search` and never
/// authorizes `enforce_hold`.
pub struct TriggerRecallOptInRuntimeTransitionGateTool;

impl TriggerRecallOptInRuntimeTransitionGateTool {
    pub fn new() -> Self {
        Self
    }
}

impl Default for TriggerRecallOptInRuntimeTransitionGateTool {
    fn default() -> Self {
        Self::new()
    }
}

#[async_trait]
impl McpTool for TriggerRecallOptInRuntimeTransitionGateTool {
    fn name(&self) -> &'static str {
        "trigger_recall_opt_in_runtime_transition_gate"
    }

    fn schema(&self) -> ToolSchema {
        ToolSchema {
            name: self.name().into(),
            description: "Read-only trigger recall opt-in runtime-transition \
                 gate. Consumes a trigger_recall_opt_in_status packet and \
                 decides whether a later gated baseline trial may be called. \
                 Does not call memory_search, inspect memory rows, echo the \
                 status packet, return raw query/keys/content, record \
                 coactivation, write memory, change default search, or \
                 authorize enforce_hold."
                .into(),
            input_schema: json!({
                "type": "object",
                "required": ["status_packet"],
                "properties": {
                    "status_packet": { "type": "object", "description": "JSON object produced by trigger_recall_opt_in_status. The gate consumes only safe summary fields and does not echo the packet." },
                    "mode": { "type": "string", "enum": ["fts", "hybrid", "semantic"], "default": "fts" },
                    "per_call_opt_in": { "type": "boolean", "default": false },
                    "scope": { "type": "string", "description": "Exact local project scope, e.g. project:/abs/path. Output includes only a hash." },
                    "scope_mode": {
                        "type": "string",
                        "enum": ["local_only", "local_plus_global", "exploratory"],
                        "default": "local_only"
                    },
                    "regression_anchor": { "type": "string" },
                    "operator_disabled": { "type": "boolean", "default": false },
                    "reviewer": { "type": "string" },
                    "commit": { "type": "string" },
                    "forum_post_id": { "type": "string" },
                    "memory_key": { "type": "string" }
                }
            }),
        }
    }

    async fn execute(&self, args: Value, _ctx: &ToolContext) -> Result<ToolResult> {
        let operator_disabled = args
            .get("operator_disabled")
            .and_then(Value::as_bool)
            .unwrap_or(false)
            || mcp_env_truthy(TRIGGER_RECALL_DISABLE_ENV);
        let payload = trigger_recall_opt_in_runtime_transition_gate(
            TriggerRecallOptInRuntimeTransitionGateOptions {
                status_packet: args.get("status_packet").cloned().unwrap_or(Value::Null),
                mode: args.get("mode").and_then(Value::as_str).unwrap_or("fts").to_string(),
                per_call_opt_in: args
                    .get("per_call_opt_in")
                    .and_then(Value::as_bool)
                    .unwrap_or(false),
                scope: args.get("scope").and_then(Value::as_str).map(str::to_string),
                scope_mode: args
                    .get("scope_mode")
                    .and_then(Value::as_str)
                    .unwrap_or("local_only")
                    .to_string(),
                regression_anchor: args
                    .get("regression_anchor")
                    .and_then(Value::as_str)
                    .map(str::to_string),
                runtime_enabled: mcp_env_truthy(TRIGGER_RECALL_OPT_IN_ENABLE_ENV),
                operator_disabled,
                reviewer: args.get("reviewer").and_then(Value::as_str).map(str::to_string),
                commit: args.get("commit").and_then(Value::as_str).map(str::to_string),
                forum_post_id: args
                    .get("forum_post_id")
                    .and_then(Value::as_str)
                    .map(str::to_string),
                memory_key: args
                    .get("memory_key")
                    .and_then(Value::as_str)
                    .map(str::to_string),
                raw_payload_fields_present: trigger_recall_value_contains_raw(&args),
            },
        );
        Ok(ToolResult::json_text(&payload))
    }
}

// ===========================================================================
//  trigger_recall_opt_in_gated_baseline_trial - transition-gated trial
// ===========================================================================

/// Transition-gated trigger-recall baseline acceptance trial. This is a
/// separate opt-in diagnostic surface: it refuses to call store FTS until the
/// runtime transition gate allows it, never calls the MCP `memory_search` tool,
/// never records coactivation, and never changes default search behavior.
pub struct TriggerRecallOptInGatedBaselineTrialTool {
    hub: Hub,
}

impl TriggerRecallOptInGatedBaselineTrialTool {
    pub fn new(hub: Hub) -> Self {
        Self { hub }
    }
}

#[async_trait]
impl McpTool for TriggerRecallOptInGatedBaselineTrialTool {
    fn name(&self) -> &'static str {
        "trigger_recall_opt_in_gated_baseline_trial"
    }

    fn schema(&self) -> ToolSchema {
        ToolSchema {
            name: self.name().into(),
            description: "Transition-gated trigger recall baseline acceptance \
                 trial. Consumes trigger_recall_opt_in_runtime_transition_gate \
                 and refuses to call store FTS unless that gate allows the \
                 explicit FTS per-call opt-in. Returns a redacted response \
                 contract with accepted or held_by_query_intent status; does \
                 not call the MCP memory_search tool, record coactivation, \
                 expose raw keys/content, change default memory_search, or \
                 authorize enforce_hold outside this opt-in trial."
                .into(),
            input_schema: json!({
                "type": "object",
                "required": [
                    "runtime_transition_gate",
                    "query",
                    "per_call_opt_in"
                ],
                "properties": {
                    "runtime_transition_gate": {
                        "type": "object",
                        "description": "JSON object produced by trigger_recall_opt_in_runtime_transition_gate. The tool consumes only safe summary fields and does not echo the gate."
                    },
                    "query": {
                        "type": "string",
                        "description": "FTS query for the gated baseline trial. Output includes only a query hash."
                    },
                    "tags_any": {
                        "type": "array",
                        "items": { "type": "string" },
                        "description": "Optional tag filter forwarded to store FTS. Output includes only the filter count."
                    },
                    "limit": {
                        "type": "integer",
                        "minimum": 1,
                        "maximum": 100,
                        "default": 10
                    },
                    "mode": {
                        "type": "string",
                        "enum": ["fts", "hybrid", "semantic"],
                        "default": "fts"
                    },
                    "scope": {
                        "type": "string",
                        "description": "Exact local project scope, e.g. project:/abs/path. Output includes only a hash."
                    },
                    "scope_mode": {
                        "type": "string",
                        "enum": ["local_only", "local_plus_global", "exploratory"],
                        "default": "local_only"
                    },
                    "per_call_opt_in": {
                        "type": "boolean",
                        "description": "Required explicit per-call opt-in bit."
                    },
                    "operator_disabled": {
                        "type": "boolean",
                        "default": false
                    },
                    "attempt_id": {
                        "type": "string",
                        "description": "Optional attempt id for redacted audit correlation."
                    },
                    "commit": {
                        "type": "string",
                        "description": "Optional implementation commit under review."
                    }
                }
            }),
        }
    }

    async fn execute(&self, args: Value, _ctx: &ToolContext) -> Result<ToolResult> {
        let runtime_transition_gate = args
            .get("runtime_transition_gate")
            .cloned()
            .unwrap_or(Value::Null);
        let query = args
            .get("query")
            .and_then(Value::as_str)
            .unwrap_or("")
            .to_string();
        let tags_any = args
            .get("tags_any")
            .cloned()
            .map(serde_json::from_value::<Vec<String>>)
            .transpose()
            .map_err(|e| ab_core::Error::Backend(format!("parse tags_any: {e}")))?
            .unwrap_or_default();
        let limit = args
            .get("limit")
            .and_then(Value::as_u64)
            .unwrap_or(10)
            .clamp(1, 100);
        let mode = args
            .get("mode")
            .and_then(Value::as_str)
            .unwrap_or("fts")
            .to_string();
        let scope = args.get("scope").and_then(Value::as_str).map(str::to_string);
        let scope_mode = args
            .get("scope_mode")
            .and_then(Value::as_str)
            .unwrap_or("local_only")
            .to_string();
        let per_call_opt_in = args
            .get("per_call_opt_in")
            .and_then(Value::as_bool)
            .unwrap_or(false);
        let operator_disabled = args
            .get("operator_disabled")
            .and_then(Value::as_bool)
            .unwrap_or(false)
            || mcp_env_truthy(TRIGGER_RECALL_DISABLE_ENV);
        let raw_payload_fields_present = trigger_recall_trial_unexpected_raw_fields(&args);
        let attempt_id = args.get("attempt_id").and_then(Value::as_str).map(str::to_string);
        let commit = args.get("commit").and_then(Value::as_str).map(str::to_string);

        let base_options = TriggerRecallOptInGatedBaselineTrialOptions {
            runtime_transition_gate,
            query,
            tags_count: tags_any.len(),
            limit,
            mode,
            per_call_opt_in,
            scope,
            scope_mode,
            runtime_enabled: mcp_env_truthy(TRIGGER_RECALL_OPT_IN_ENABLE_ENV),
            operator_disabled,
            raw_payload_fields_present,
            attempt_id,
            commit,
            ..Default::default()
        };

        let preflight = trigger_recall_opt_in_gated_baseline_trial(base_options.clone());
        let transition_allowed = preflight
            .pointer("/runtime_transition_preflight/transition_gate_allowed")
            .and_then(Value::as_bool)
            .unwrap_or(false);
        if !transition_allowed {
            return Ok(ToolResult::json_text(&preflight));
        }

        let store = match self.hub.store.as_ref() {
            Some(store) => store,
            None => {
                let mut options = base_options;
                options.baseline_search_error = Some("store_unavailable".to_string());
                return Ok(ToolResult::json_text(
                    &trigger_recall_opt_in_gated_baseline_trial(options),
                ));
            }
        };

        let mut options = base_options;
        let search_limit = if options.scope.is_some() {
            (limit.saturating_mul(5)).min(200)
        } else {
            limit
        } as u32;
        match store.memory_search(&options.query, &tags_any, search_limit).await {
            Ok(mut hits) => {
                if let Some(scope) = options.scope.as_deref() {
                    hits =
                        memory_search_apply_scope_mode(hits, scope, MemorySearchScopeMode::LocalOnly);
                }
                hits.truncate(limit as usize);
                options.baseline_search_called = true;
                options.baseline_hits = Some(
                    hits.iter()
                        .map(trigger_recall_baseline_trial_hit)
                        .collect(),
                );
            }
            Err(_) => {
                options.baseline_search_called = true;
                options.baseline_search_error = Some("memory_search_failed".to_string());
            }
        }

        Ok(ToolResult::json_text(
            &trigger_recall_opt_in_gated_baseline_trial(options),
        ))
    }
}

// ===========================================================================
//  trigger_recall_opt_in_pre_policy_hold_simulation - candidate-only surface
// ===========================================================================

/// Candidate-only pre-policy hold simulation. This surface requires a separate
/// approval packet, stays in Tier::Niche, never calls the MCP memory_search
/// tool, and never changes default memory_search behavior.
pub struct TriggerRecallOptInPrePolicyHoldSimulationTool {
    hub: Hub,
}

impl TriggerRecallOptInPrePolicyHoldSimulationTool {
    pub fn new(hub: Hub) -> Self {
        Self { hub }
    }
}

pub(super) fn trigger_recall_pre_policy_hold_unexpected_raw_fields(args: &Value) -> bool {
    let mut redacted_boundary = args.clone();
    if let Some(obj) = redacted_boundary.as_object_mut() {
        obj.remove("query");
        obj.remove("approval_packet");
    }
    trigger_recall_value_contains_raw(&redacted_boundary)
        || args.get("mutate").is_some()
        || args.get("write").is_some()
        || args.get("dry_run").is_some()
}

#[async_trait]
impl McpTool for TriggerRecallOptInPrePolicyHoldSimulationTool {
    fn name(&self) -> &'static str {
        "trigger_recall_opt_in_pre_policy_hold_simulation"
    }

    fn schema(&self) -> ToolSchema {
        ToolSchema {
            name: self.name().into(),
            description: "Candidate-only trigger recall pre-policy hold \
                 simulation. Requires an exact approval packet plus explicit \
                 per-call opt-in. Held queries return an object status and do \
                 not call store FTS unless count audit is requested. Accepted \
                 or fail-open paths may call store FTS directly, but never the \
                 MCP memory_search tool, never record coactivation, never echo \
                 raw query/keys/content, never change default memory_search, \
                 and never authorize production enforce_hold."
                .into(),
            input_schema: json!({
                "type": "object",
                "required": [
                    "approval_packet",
                    "query",
                    "per_call_opt_in"
                ],
                "properties": {
                    "approval_packet": {
                        "type": "object",
                        "description": "Approval packet for pre_policy_hold_simulation. The tool consumes only safe summary fields and does not echo the packet."
                    },
                    "query": {
                        "type": "string",
                        "description": "FTS query for this opt-in simulation. Output includes only a query hash."
                    },
                    "tags_any": {
                        "type": "array",
                        "items": { "type": "string" },
                        "description": "Optional tag filter forwarded to store FTS when baseline lookup is required. Output includes only the filter count."
                    },
                    "limit": {
                        "type": "integer",
                        "minimum": 1,
                        "maximum": 100,
                        "default": 10
                    },
                    "mode": {
                        "type": "string",
                        "enum": ["fts", "hybrid", "semantic"],
                        "default": "fts"
                    },
                    "scope": {
                        "type": "string",
                        "description": "Exact local project scope, e.g. project:/abs/path. Output includes only a hash."
                    },
                    "scope_mode": {
                        "type": "string",
                        "enum": ["local_only", "local_plus_global", "exploratory"],
                        "default": "local_only"
                    },
                    "include_baseline_counts": {
                        "type": "boolean",
                        "default": false,
                        "description": "When true, held queries may call store FTS only for count/order-hash audit while still returning no visible hits."
                    },
                    "per_call_opt_in": {
                        "type": "boolean",
                        "description": "Required explicit per-call opt-in bit."
                    },
                    "operator_disabled": {
                        "type": "boolean",
                        "default": false
                    },
                    "attempt_id": {
                        "type": "string",
                        "description": "Optional attempt id for redacted audit correlation."
                    },
                    "commit": {
                        "type": "string",
                        "description": "Candidate implementation commit named by the approval packet."
                    }
                }
            }),
        }
    }

    async fn execute(&self, args: Value, _ctx: &ToolContext) -> Result<ToolResult> {
        let query = args
            .get("query")
            .and_then(Value::as_str)
            .unwrap_or("")
            .to_string();
        let tags_any = args
            .get("tags_any")
            .cloned()
            .map(serde_json::from_value::<Vec<String>>)
            .transpose()
            .map_err(|e| ab_core::Error::Backend(format!("parse tags_any: {e}")))?
            .unwrap_or_default();
        let limit = args
            .get("limit")
            .and_then(Value::as_u64)
            .unwrap_or(10)
            .clamp(1, 100);
        let mode = args
            .get("mode")
            .and_then(Value::as_str)
            .unwrap_or("fts")
            .to_string();
        let scope = args.get("scope").and_then(Value::as_str).map(str::to_string);
        let scope_mode = args
            .get("scope_mode")
            .and_then(Value::as_str)
            .unwrap_or("local_only")
            .to_string();
        let include_baseline_counts = args
            .get("include_baseline_counts")
            .and_then(Value::as_bool)
            .unwrap_or(false);
        let per_call_opt_in = args
            .get("per_call_opt_in")
            .and_then(Value::as_bool)
            .unwrap_or(false);
        let operator_disabled = args
            .get("operator_disabled")
            .and_then(Value::as_bool)
            .unwrap_or(false)
            || mcp_env_truthy(TRIGGER_RECALL_PRE_POLICY_HOLD_DISABLE_ENV);
        let attempt_id = args.get("attempt_id").and_then(Value::as_str).map(str::to_string);
        let commit = args.get("commit").and_then(Value::as_str).map(str::to_string);

        let base_options = TriggerRecallPrePolicyHoldSimulationOptions {
            approval_packet: args
                .get("approval_packet")
                .cloned()
                .unwrap_or(Value::Null),
            query,
            tags_count: tags_any.len(),
            limit,
            mode,
            per_call_opt_in,
            scope,
            scope_mode,
            include_baseline_counts,
            runtime_enabled: mcp_env_truthy(TRIGGER_RECALL_PRE_POLICY_HOLD_OPT_IN_ENV),
            operator_disabled,
            raw_payload_fields_present: trigger_recall_pre_policy_hold_unexpected_raw_fields(&args),
            attempt_id,
            commit,
            ..Default::default()
        };

        let preflight = trigger_recall_opt_in_pre_policy_hold_simulation(base_options.clone());
        let store_search_required = preflight
            .pointer("/baseline/store_search_required")
            .and_then(Value::as_bool)
            .unwrap_or(false);
        if !store_search_required {
            return Ok(ToolResult::json_text(&preflight));
        }

        let store = match self.hub.store.as_ref() {
            Some(store) => store,
            None => {
                let mut options = base_options;
                options.baseline_search_error = Some("store_unavailable".to_string());
                return Ok(ToolResult::json_text(
                    &trigger_recall_opt_in_pre_policy_hold_simulation(options),
                ));
            }
        };

        let mut options = base_options;
        let exact_local_scope = preflight
            .pointer("/request/exact_local_project_scope")
            .and_then(Value::as_bool)
            .unwrap_or(false);
        let search_limit = if exact_local_scope {
            (limit.saturating_mul(5)).min(200)
        } else {
            limit
        } as u32;
        match store.memory_search(&options.query, &tags_any, search_limit).await {
            Ok(mut hits) => {
                if exact_local_scope {
                    if let Some(scope) = options.scope.as_deref() {
                        hits = memory_search_apply_scope_mode(
                            hits,
                            scope,
                            MemorySearchScopeMode::LocalOnly,
                        );
                    }
                }
                hits.truncate(limit as usize);
                options.baseline_search_called = true;
                options.baseline_hits = Some(
                    hits.iter()
                        .map(trigger_recall_baseline_trial_hit)
                        .collect(),
                );
            }
            Err(_) => {
                options.baseline_search_called = true;
                options.baseline_search_error = Some("memory_search_failed".to_string());
            }
        }

        Ok(ToolResult::json_text(
            &trigger_recall_opt_in_pre_policy_hold_simulation(options),
        ))
    }
}

// ===========================================================================
//  trigger_recall_opt_in_gated_batch_diagnostics - gated trial batch review
// ===========================================================================

/// Read-only batch diagnostics for redacted trigger-recall gated baseline trial
/// packets. This tool never calls store FTS itself; it only summarizes trial
/// packet statuses, counts, and order hashes for the next review packet.
pub struct TriggerRecallOptInGatedBatchDiagnosticsTool;

impl TriggerRecallOptInGatedBatchDiagnosticsTool {
    pub fn new() -> Self {
        Self
    }
}

impl Default for TriggerRecallOptInGatedBatchDiagnosticsTool {
    fn default() -> Self {
        Self::new()
    }
}

pub(super) fn trigger_recall_gated_batch_packets_from_args(
    args: &Value,
) -> Vec<TriggerRecallOptInGatedBatchDiagnosticsPacket> {
    args.get("trial_packets")
        .or_else(|| args.get("packets"))
        .and_then(Value::as_array)
        .map(|packets| {
            packets
                .iter()
                .map(|packet| TriggerRecallOptInGatedBatchDiagnosticsPacket {
                    trial_packet: packet
                        .get("trial_packet")
                        .or_else(|| packet.get("gated_baseline_trial"))
                        .cloned()
                        .unwrap_or(Value::Null),
                    case_id: packet
                        .get("case_id")
                        .and_then(Value::as_str)
                        .map(str::to_string),
                    expected_status: packet
                        .get("expected_status")
                        .and_then(Value::as_str)
                        .map(str::to_string),
                    expected_visible_behavior: packet
                        .get("expected_visible_behavior")
                        .and_then(Value::as_str)
                        .map(str::to_string),
                    raw_payload_fields_present: trigger_recall_value_contains_raw(packet),
                })
                .collect()
        })
        .unwrap_or_default()
}

pub(super) fn trigger_recall_gated_batch_outer_args_contain_raw(args: &Value) -> bool {
    let mut outer = args.clone();
    if let Value::Object(map) = &mut outer {
        map.remove("trial_packets");
        map.remove("packets");
    }
    trigger_recall_value_contains_raw(&outer)
}

#[async_trait]
impl McpTool for TriggerRecallOptInGatedBatchDiagnosticsTool {
    fn name(&self) -> &'static str {
        "trigger_recall_opt_in_gated_batch_diagnostics"
    }

    fn schema(&self) -> ToolSchema {
        ToolSchema {
            name: self.name().into(),
            description: "Read-only batch diagnostics for redacted trigger \
                 recall gated baseline trial packets. Consumes \
                 trigger_recall_opt_in_gated_baseline_trial outputs and reports \
                 only status counts, order hashes, hashed case ids, and blocker \
                 summaries. Does not call memory_search or store FTS itself, \
                 echo trial packets, return raw query/keys/content, record \
                 coactivation, write memory, change default search, or \
                 authorize enforce_hold."
                .into(),
            input_schema: json!({
                "type": "object",
                "required": ["trial_packets"],
                "properties": {
                    "trial_packets": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "required": ["trial_packet"],
                            "properties": {
                                "trial_packet": {
                                    "type": "object",
                                    "description": "JSON object produced by trigger_recall_opt_in_gated_baseline_trial. The tool consumes only safe summary fields and does not echo the packet."
                                },
                                "case_id": {
                                    "type": "string",
                                    "description": "Optional audit case id. Output includes only a hash."
                                },
                                "expected_status": {
                                    "type": "string",
                                    "enum": [
                                        "returned_accepted",
                                        "held_by_query_intent",
                                        "transition_gate_blocked",
                                        "baseline_search_error",
                                        "baseline_search_pending"
                                    ]
                                },
                                "expected_visible_behavior": {
                                    "type": "string",
                                    "enum": [
                                        "baseline_fts_visible",
                                        "held_by_query_intent",
                                        "transition_gate_blocked",
                                        "baseline_search_error",
                                        "baseline_search_pending"
                                    ]
                                }
                            }
                        },
                        "description": "Redacted trial packets under review. Raw queries, memory keys, and content fields are rejected and never echoed."
                    },
                    "attempt_id": {
                        "type": "string",
                        "description": "Optional batch attempt id for audit correlation. Output includes only a hash."
                    },
                    "reviewer": { "type": "string" },
                    "commit": { "type": "string" },
                    "forum_post_id": { "type": "string" }
                }
            }),
        }
    }

    async fn execute(&self, args: Value, _ctx: &ToolContext) -> Result<ToolResult> {
        let payload = trigger_recall_opt_in_gated_batch_diagnostics(
            TriggerRecallOptInGatedBatchDiagnosticsOptions {
                packets: trigger_recall_gated_batch_packets_from_args(&args),
                attempt_id: args
                    .get("attempt_id")
                    .and_then(Value::as_str)
                    .map(str::to_string),
                reviewer: args
                    .get("reviewer")
                    .and_then(Value::as_str)
                    .map(str::to_string),
                commit: args.get("commit").and_then(Value::as_str).map(str::to_string),
                forum_post_id: args
                    .get("forum_post_id")
                    .and_then(Value::as_str)
                    .map(str::to_string),
                raw_payload_fields_present: trigger_recall_gated_batch_outer_args_contain_raw(&args),
            },
        );
        Ok(ToolResult::json_text(&payload))
    }
}

// ===========================================================================
//  trigger_recall_enforce_hold_approval_packet_validator - read-only packet gate
// ===========================================================================

/// Read-only validator for trigger-recall enforce-hold approval packets. This
/// tool never calls search; it only reports whether a packet can authorize a
/// later audit-only or pre-policy-hold implementation slice.
pub struct TriggerRecallEnforceHoldApprovalPacketValidatorTool;

impl TriggerRecallEnforceHoldApprovalPacketValidatorTool {
    pub fn new() -> Self {
        Self
    }
}

impl Default for TriggerRecallEnforceHoldApprovalPacketValidatorTool {
    fn default() -> Self {
        Self::new()
    }
}

#[async_trait]
impl McpTool for TriggerRecallEnforceHoldApprovalPacketValidatorTool {
    fn name(&self) -> &'static str {
        "trigger_recall_enforce_hold_approval_packet_validator"
    }

    fn schema(&self) -> ToolSchema {
        ToolSchema {
            name: self.name().into(),
            description: format!(
                "Read-only validator for `{}` approval packets. Returns a \
                 redacted readiness result for audit_only or pre_policy_hold \
                 implementation slices. Does not call memory_search or store \
                 FTS, echo the approval packet, return raw query/keys/content, \
                 record coactivation, write memory, write graph edges, change \
                 default memory_search, or authorize production enforce_hold.",
                TRIGGER_RECALL_ENFORCE_HOLD_APPROVAL_PACKET_SCHEMA
            ),
            input_schema: json!({
                "type": "object",
                "required": ["approval_packet"],
                "properties": {
                    "approval_packet": {
                        "type": "object",
                        "description": "Approval packet using the enforce-hold approval schema. The packet is validated but never echoed."
                    },
                    "raw_payload_fields_present": {
                        "type": "boolean",
                        "description": "Optional caller-side redaction preflight. If true, the validator blocks without echoing raw fields."
                    }
                }
            }),
        }
    }

    async fn execute(&self, args: Value, _ctx: &ToolContext) -> Result<ToolResult> {
        let payload = trigger_recall_enforce_hold_approval_packet_validator(
            TriggerRecallEnforceHoldApprovalPacketValidatorOptions {
                approval_packet: args.get("approval_packet").cloned().unwrap_or(Value::Null),
                raw_payload_fields_present: args
                    .get("raw_payload_fields_present")
                    .and_then(Value::as_bool)
                    .unwrap_or(false)
                    || trigger_recall_value_contains_raw(&args),
            },
        );
        Ok(ToolResult::json_text(&payload))
    }
}

// ===========================================================================
//  biocortex_retrieval_opt_in_dry_run — read-only future-path planner
// ===========================================================================

/// Read-only BioCortex retrieval opt-in dry-run planner. This tool reports the
/// future FTS opt-in ordering path and store-contract fallback decision. It
/// does not call `memory_search`, run BioCortex, include raw memory content, or
/// change retrieval order.
pub struct BioCortexRetrievalOptInDryRunTool;

impl BioCortexRetrievalOptInDryRunTool {
    pub fn new() -> Self {
        Self
    }
}

impl Default for BioCortexRetrievalOptInDryRunTool {
    fn default() -> Self {
        Self::new()
    }
}

#[async_trait]
impl McpTool for BioCortexRetrievalOptInDryRunTool {
    fn name(&self) -> &'static str {
        "biocortex_retrieval_opt_in_dry_run"
    }

    fn schema(&self) -> ToolSchema {
        ToolSchema {
            name: self.name().into(),
            description: "Read-only BioCortex retrieval opt-in dry-run planner. \
                 Reports the future FTS opt-in ordering path, planned side-signal \
                 steps, and store-contract fallback decision with hashed query/order \
                 data only. Does not call memory_search, run BioCortex, mutate \
                 memory, include raw memory keys/content, register an EmbeddingBackend, \
                 or alter retrieval order."
                .into(),
            input_schema: json!({
                "type": "object",
                "properties": {
                    "mode": {
                        "type": "string",
                        "enum": ["fts", "hybrid", "semantic"],
                        "default": "fts",
                        "description": "Retrieval mode under review. Only fts is authorized for opt-in work."
                    },
                    "per_call_opt_in": {
                        "type": "boolean",
                        "default": false,
                        "description": "Explicit per-call opt-in bit to evaluate."
                    },
                    "query": {
                        "type": "string",
                        "description": "Optional query text. Output includes only a hash."
                    },
                    "baseline_keys": {
                        "type": "array",
                        "items": { "type": "string" },
                        "description": "Optional baseline candidate keys. Output includes only count/hash, never raw keys."
                    },
                    "baseline_completed": {
                        "type": "boolean",
                        "default": true,
                        "description": "Whether the baseline memory_search result already exists for this dry run."
                    },
                    "timeout_ms": {
                        "type": "integer",
                        "minimum": 1,
                        "default": 120000,
                        "description": "Future side-signal adapter timeout in milliseconds."
                    },
                    "coverage_threshold": {
                        "type": "number",
                        "minimum": 0.0,
                        "maximum": 1.0,
                        "default": 0.8,
                        "description": "Future minimum side-signal coverage threshold."
                    }
                }
            }),
        }
    }

    async fn execute(&self, args: Value, _ctx: &ToolContext) -> Result<ToolResult> {
        let mode = args
            .get("mode")
            .and_then(Value::as_str)
            .unwrap_or("fts")
            .to_string();
        let per_call_opt_in = args
            .get("per_call_opt_in")
            .and_then(Value::as_bool)
            .unwrap_or(false);
        let query = args
            .get("query")
            .and_then(Value::as_str)
            .map(str::to_string);
        let baseline_keys = args
            .get("baseline_keys")
            .cloned()
            .map(serde_json::from_value::<Vec<String>>)
            .transpose()
            .map_err(|e| ab_core::Error::Backend(format!("parse baseline_keys: {e}")))?
            .unwrap_or_default();
        let baseline_completed = args
            .get("baseline_completed")
            .and_then(Value::as_bool)
            .unwrap_or(true);
        let timeout_ms = args
            .get("timeout_ms")
            .and_then(Value::as_u64)
            .unwrap_or(120_000);
        let coverage_threshold = args
            .get("coverage_threshold")
            .and_then(Value::as_f64)
            .unwrap_or(0.8);

        let payload =
            biocortex_retrieval_opt_in_dry_run_plan(BioCortexRetrievalOptInDryRunOptions {
                mode,
                per_call_opt_in,
                query,
                baseline_keys,
                baseline_completed,
                timeout_ms,
                coverage_threshold,
            });
        Ok(ToolResult::json_text(&payload))
    }
}

// ===========================================================================
//  biocortex_retrieval_opt_in_review_packet — read-only dry-run review packet
// ===========================================================================

/// Read-only BioCortex retrieval opt-in review-packet consumer. This tool
/// accepts an opt-in dry-run plan and emits a safe review packet for human/agent
/// inspection. It does not include the raw dry-run payload, approve anything,
/// call `memory_search`, run BioCortex, or change retrieval order.
pub struct BioCortexRetrievalOptInReviewPacketTool;

impl BioCortexRetrievalOptInReviewPacketTool {
    pub fn new() -> Self {
        Self
    }
}

impl Default for BioCortexRetrievalOptInReviewPacketTool {
    fn default() -> Self {
        Self::new()
    }
}

#[async_trait]
impl McpTool for BioCortexRetrievalOptInReviewPacketTool {
    fn name(&self) -> &'static str {
        "biocortex_retrieval_opt_in_review_packet"
    }

    fn schema(&self) -> ToolSchema {
        ToolSchema {
            name: self.name().into(),
            description: "Read-only BioCortex retrieval opt-in review packet \
                 consumer. Accepts a dry-run plan and emits safe summary evidence \
                 for review without including the raw dry-run payload. Does not \
                 call memory_search, run BioCortex, mutate memory, include raw \
                 memory keys/content, register an EmbeddingBackend, approve \
                 runtime influence, or alter retrieval order."
                .into(),
            input_schema: json!({
                "type": "object",
                "required": ["dry_run_plan"],
                "properties": {
                    "dry_run_plan": {
                        "type": "object",
                        "description": "JSON object produced by biocortex_retrieval_opt_in_dry_run. Unknown/raw fields are ignored."
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
                    }
                }
            }),
        }
    }

    async fn execute(&self, args: Value, _ctx: &ToolContext) -> Result<ToolResult> {
        let dry_run_plan = args.get("dry_run_plan").cloned().unwrap_or(Value::Null);
        let reviewer = args
            .get("reviewer")
            .and_then(Value::as_str)
            .map(str::to_string);
        let commit = args
            .get("commit")
            .and_then(Value::as_str)
            .map(str::to_string);
        let forum_post_id = args
            .get("forum_post_id")
            .and_then(Value::as_str)
            .map(str::to_string);
        let memory_key = args
            .get("memory_key")
            .and_then(Value::as_str)
            .map(str::to_string);
        let payload =
            biocortex_retrieval_opt_in_review_packet(BioCortexRetrievalOptInReviewPacketOptions {
                dry_run_plan,
                reviewer,
                commit,
                forum_post_id,
                memory_key,
            });
        Ok(ToolResult::json_text(&payload))
    }
}

// ===========================================================================
//  biocortex_retrieval_opt_in_execution_packet — protected preflight contract
// ===========================================================================

/// Read-only BioCortex retrieval opt-in execution packet. This tool accepts an
/// opt-in review packet and emits a protected preflight contract for a future
/// adapter. It does not include the raw review packet, approve anything, call
/// `memory_search`, run BioCortex, or change retrieval order.
pub struct BioCortexRetrievalOptInExecutionPacketTool;

impl BioCortexRetrievalOptInExecutionPacketTool {
    pub fn new() -> Self {
        Self
    }
}

impl Default for BioCortexRetrievalOptInExecutionPacketTool {
    fn default() -> Self {
        Self::new()
    }
}

#[async_trait]
impl McpTool for BioCortexRetrievalOptInExecutionPacketTool {
    fn name(&self) -> &'static str {
        "biocortex_retrieval_opt_in_execution_packet"
    }

    fn schema(&self) -> ToolSchema {
        ToolSchema {
            name: self.name().into(),
            description: "Read-only BioCortex retrieval opt-in execution preflight \
                 packet. Accepts a review packet and emits a protected adapter \
                 contract while still returning baseline. Does not call \
                 memory_search, run BioCortex, mutate memory, include raw memory \
                 keys/content, register an EmbeddingBackend, approve runtime \
                 influence, or alter retrieval order."
                .into(),
            input_schema: json!({
                "type": "object",
                "required": ["review_packet"],
                "properties": {
                    "review_packet": {
                        "type": "object",
                        "description": "JSON object produced by biocortex_retrieval_opt_in_review_packet. Unknown/raw fields are ignored."
                    },
                    "per_call_opt_in": {
                        "type": "boolean",
                        "default": false,
                        "description": "Explicit per-call opt-in bit to evaluate in the store contract."
                    },
                    "attempt_id": {
                        "type": "string",
                        "description": "Optional execution attempt id for audit correlation."
                    },
                    "commit": {
                        "type": "string",
                        "description": "Optional implementation commit under review."
                    }
                }
            }),
        }
    }

    async fn execute(&self, args: Value, _ctx: &ToolContext) -> Result<ToolResult> {
        let review_packet = args.get("review_packet").cloned().unwrap_or(Value::Null);
        let per_call_opt_in = args
            .get("per_call_opt_in")
            .and_then(Value::as_bool)
            .unwrap_or(false);
        let attempt_id = args
            .get("attempt_id")
            .and_then(Value::as_str)
            .map(str::to_string);
        let commit = args
            .get("commit")
            .and_then(Value::as_str)
            .map(str::to_string);
        let payload = biocortex_retrieval_opt_in_execution_packet(
            BioCortexRetrievalOptInExecutionPacketOptions {
                review_packet,
                per_call_opt_in,
                attempt_id,
                commit,
            },
        );
        Ok(ToolResult::json_text(&payload))
    }
}

// ===========================================================================
//  biocortex_retrieval_opt_in_runtime_trial — baseline-preserving side signal
// ===========================================================================

/// Baseline-preserving BioCortex retrieval opt-in runtime trial. This tool
/// accepts an execution packet plus explicit candidate rows and may run the
/// external side-signal adapter when opt-in gates pass. It never calls
/// `memory_search`, includes raw query/key/content data in output, registers an
/// EmbeddingBackend, approves runtime influence, or changes returned order.
pub struct BioCortexRetrievalOptInRuntimeTrialTool;

impl BioCortexRetrievalOptInRuntimeTrialTool {
    pub fn new() -> Self {
        Self
    }
}

impl Default for BioCortexRetrievalOptInRuntimeTrialTool {
    fn default() -> Self {
        Self::new()
    }
}

#[async_trait]
impl McpTool for BioCortexRetrievalOptInRuntimeTrialTool {
    fn name(&self) -> &'static str {
        "biocortex_retrieval_opt_in_runtime_trial"
    }

    fn schema(&self) -> ToolSchema {
        ToolSchema {
            name: self.name().into(),
            description: "Baseline-preserving BioCortex retrieval opt-in runtime \
                 trial. Accepts an execution packet and explicit candidate rows, \
                 runs the external side-signal adapter only when opt-in gates pass, \
                 and returns a sanitized evidence packet. Does not call \
                 memory_search, mutate memory, include raw query/keys/content, \
                 register an EmbeddingBackend, approve runtime influence, or alter \
                 retrieval order."
                .into(),
            input_schema: json!({
                "type": "object",
                "required": ["execution_packet", "query", "candidates"],
                "properties": {
                    "execution_packet": {
                        "type": "object",
                        "description": "JSON object produced by biocortex_retrieval_opt_in_execution_packet. Unknown/raw fields are ignored."
                    },
                    "query": {
                        "type": "string",
                        "description": "Query text for the side-signal trial. Output includes only a hash."
                    },
                    "candidates": {
                        "type": "array",
                        "minItems": 1,
                        "items": {
                            "type": "object",
                            "properties": {
                                "key": { "type": "string" },
                                "content": { "type": "string" }
                            },
                            "required": ["key", "content"]
                        },
                        "description": "Explicit baseline candidate rows. The tool never fetches memory_search results and does not echo keys/content."
                    },
                    "expected_key": {
                        "type": "string",
                        "description": "Optional expected key. Output includes only a hash and ranks."
                    },
                    "checkout_path": {
                        "type": "string",
                        "description": "Optional local biocortex-rs checkout. Defaults to AB_BIOCORTEX_RS, sibling checkout paths, then /tmp/biocortex-rs-ab-eval."
                    },
                    "timeout_ms": {
                        "type": "integer",
                        "minimum": 1000,
                        "maximum": 600000,
                        "default": 120000,
                        "description": "External side-signal adapter timeout in milliseconds."
                    },
                    "coverage_threshold": {
                        "type": "number",
                        "minimum": 0.0,
                        "maximum": 1.0,
                        "default": 0.8,
                        "description": "Minimum matched side-signal coverage for advisory availability."
                    },
                    "attempt_id": {
                        "type": "string",
                        "description": "Optional runtime trial attempt id for audit correlation."
                    },
                    "commit": {
                        "type": "string",
                        "description": "Optional implementation commit under review."
                    }
                }
            }),
        }
    }

    async fn execute(&self, args: Value, _ctx: &ToolContext) -> Result<ToolResult> {
        let execution_packet = args.get("execution_packet").cloned().unwrap_or(Value::Null);
        let query = args
            .get("query")
            .and_then(Value::as_str)
            .unwrap_or("")
            .to_string();
        let candidates_value = args.get("candidates").cloned().unwrap_or_else(|| json!([]));
        let candidates =
            serde_json::from_value::<Vec<BioCortexRetrievalCandidate>>(candidates_value)
                .map_err(|e| ab_core::Error::Backend(format!("parse candidates: {e}")))?;
        let expected_key = args
            .get("expected_key")
            .and_then(Value::as_str)
            .map(str::to_string);
        let checkout = args
            .get("checkout_path")
            .and_then(Value::as_str)
            .map(str::trim)
            .filter(|s| !s.is_empty())
            .map(PathBuf::from);
        let timeout_ms = args
            .get("timeout_ms")
            .and_then(Value::as_u64)
            .unwrap_or(120_000);
        let coverage_threshold = args
            .get("coverage_threshold")
            .and_then(Value::as_f64)
            .unwrap_or(0.8);
        let attempt_id = args
            .get("attempt_id")
            .and_then(Value::as_str)
            .map(str::to_string);
        let commit = args
            .get("commit")
            .and_then(Value::as_str)
            .map(str::to_string);

        let payload =
            biocortex_retrieval_opt_in_runtime_trial(BioCortexRetrievalOptInRuntimeTrialOptions {
                execution_packet,
                query,
                candidates,
                expected_key,
                checkout,
                timeout_ms,
                coverage_threshold,
                attempt_id,
                commit,
            })
            .await;
        Ok(ToolResult::json_text(&payload))
    }
}

// ===========================================================================
//  biocortex_retrieval_opt_in_runtime_trial_review_packet — review evidence
// ===========================================================================

/// Read-only BioCortex retrieval opt-in runtime-trial review packet. This tool
/// accepts a runtime trial packet and emits safe post-implementation review
/// evidence. It does not include the raw runtime trial payload, approve
/// anything, call `memory_search`, run BioCortex, or change retrieval order.
pub struct BioCortexRetrievalOptInRuntimeTrialReviewPacketTool;

impl BioCortexRetrievalOptInRuntimeTrialReviewPacketTool {
    pub fn new() -> Self {
        Self
    }
}

impl Default for BioCortexRetrievalOptInRuntimeTrialReviewPacketTool {
    fn default() -> Self {
        Self::new()
    }
}

#[async_trait]
impl McpTool for BioCortexRetrievalOptInRuntimeTrialReviewPacketTool {
    fn name(&self) -> &'static str {
        "biocortex_retrieval_opt_in_runtime_trial_review_packet"
    }

    fn schema(&self) -> ToolSchema {
        ToolSchema {
            name: self.name().into(),
            description: "Read-only BioCortex retrieval opt-in runtime-trial \
                 review packet. Accepts a runtime trial packet and emits safe \
                 post-implementation review evidence without including the raw \
                 trial payload. Does not call memory_search, run BioCortex, \
                 mutate memory, include raw query/keys/content, register an \
                 EmbeddingBackend, approve runtime influence, or alter retrieval \
                 order."
                .into(),
            input_schema: json!({
                "type": "object",
                "required": ["runtime_trial"],
                "properties": {
                    "runtime_trial": {
                        "type": "object",
                        "description": "JSON object produced by biocortex_retrieval_opt_in_runtime_trial. Unknown/raw fields are ignored."
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
                    }
                }
            }),
        }
    }

    async fn execute(&self, args: Value, _ctx: &ToolContext) -> Result<ToolResult> {
        let runtime_trial = args.get("runtime_trial").cloned().unwrap_or(Value::Null);
        let reviewer = args
            .get("reviewer")
            .and_then(Value::as_str)
            .map(str::to_string);
        let commit = args
            .get("commit")
            .and_then(Value::as_str)
            .map(str::to_string);
        let forum_post_id = args
            .get("forum_post_id")
            .and_then(Value::as_str)
            .map(str::to_string);
        let memory_key = args
            .get("memory_key")
            .and_then(Value::as_str)
            .map(str::to_string);
        let payload = biocortex_retrieval_opt_in_runtime_trial_review_packet(
            BioCortexRetrievalOptInRuntimeTrialReviewPacketOptions {
                runtime_trial,
                reviewer,
                commit,
                forum_post_id,
                memory_key,
            },
        );
        Ok(ToolResult::json_text(&payload))
    }
}

// ===========================================================================
//  biocortex_retrieval_opt_in_order_diff_packet — hash-only order diff
// ===========================================================================

/// Read-only BioCortex retrieval opt-in order-diff packet. This tool accepts a
/// runtime-trial or runtime-trial-review packet and compares baseline order
/// against the advisory order using safe hash/rank summaries only. It does not
/// include raw order keys, approve anything, call `memory_search`, run
/// BioCortex, or change retrieval order.
pub struct BioCortexRetrievalOptInOrderDiffPacketTool;

impl BioCortexRetrievalOptInOrderDiffPacketTool {
    pub fn new() -> Self {
        Self
    }
}

impl Default for BioCortexRetrievalOptInOrderDiffPacketTool {
    fn default() -> Self {
        Self::new()
    }
}

#[async_trait]
impl McpTool for BioCortexRetrievalOptInOrderDiffPacketTool {
    fn name(&self) -> &'static str {
        "biocortex_retrieval_opt_in_order_diff_packet"
    }

    fn schema(&self) -> ToolSchema {
        ToolSchema {
            name: self.name().into(),
            description: "Read-only BioCortex retrieval opt-in order-diff \
                 packet. Accepts a runtime trial or runtime-trial-review packet \
                 and compares baseline order against advisory order using \
                 hash/rank summaries only. Does not call memory_search, run \
                 BioCortex, mutate memory, include raw query/keys/content, \
                 register an EmbeddingBackend, approve runtime influence, or \
                 alter retrieval order."
                .into(),
            input_schema: json!({
                "type": "object",
                "required": ["source_packet"],
                "properties": {
                    "source_packet": {
                        "type": "object",
                        "description": "JSON object produced by biocortex_retrieval_opt_in_runtime_trial or biocortex_retrieval_opt_in_runtime_trial_review_packet. Unknown/raw fields are ignored."
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
                        "description": "Optional forum post id linking this packet."
                    },
                    "memory_key": {
                        "type": "string",
                        "description": "Optional memory key linking this packet."
                    }
                }
            }),
        }
    }

    async fn execute(&self, args: Value, _ctx: &ToolContext) -> Result<ToolResult> {
        let source_packet = args.get("source_packet").cloned().unwrap_or(Value::Null);
        let reviewer = args
            .get("reviewer")
            .and_then(Value::as_str)
            .map(str::to_string);
        let commit = args
            .get("commit")
            .and_then(Value::as_str)
            .map(str::to_string);
        let forum_post_id = args
            .get("forum_post_id")
            .and_then(Value::as_str)
            .map(str::to_string);
        let memory_key = args
            .get("memory_key")
            .and_then(Value::as_str)
            .map(str::to_string);
        let payload = biocortex_retrieval_opt_in_order_diff_packet(
            BioCortexRetrievalOptInOrderDiffPacketOptions {
                source_packet,
                reviewer,
                commit,
                forum_post_id,
                memory_key,
            },
        );
        Ok(ToolResult::json_text(&payload))
    }
}

// ===========================================================================
//  biocortex_retrieval_opt_in_redacted_order_artifact — rank movement metrics
// ===========================================================================

/// Read-only BioCortex retrieval opt-in redacted-order artifact. This tool
/// accepts a runtime-trial or runtime-trial-review packet and computes top-k
/// overlap plus per-key rank movements from sanitized key_hash rows only. It
/// does not include raw order keys, approve anything, call `memory_search`, run
/// BioCortex, or change retrieval order.
pub struct BioCortexRetrievalOptInRedactedOrderArtifactTool;

impl BioCortexRetrievalOptInRedactedOrderArtifactTool {
    pub fn new() -> Self {
        Self
    }
}

impl Default for BioCortexRetrievalOptInRedactedOrderArtifactTool {
    fn default() -> Self {
        Self::new()
    }
}

#[async_trait]
impl McpTool for BioCortexRetrievalOptInRedactedOrderArtifactTool {
    fn name(&self) -> &'static str {
        "biocortex_retrieval_opt_in_redacted_order_artifact"
    }

    fn schema(&self) -> ToolSchema {
        ToolSchema {
            name: self.name().into(),
            description: "Read-only BioCortex retrieval opt-in redacted-order \
                 artifact. Accepts a runtime trial or runtime-trial-review \
                 packet and computes top-k overlap plus per-key rank movement \
                 from sanitized key_hash rows only. Does not call \
                 memory_search, run BioCortex, mutate memory, include raw \
                 query/keys/content, register an EmbeddingBackend, approve \
                 runtime influence, or alter retrieval order."
                .into(),
            input_schema: json!({
                "type": "object",
                "required": ["source_packet"],
                "properties": {
                    "source_packet": {
                        "type": "object",
                        "description": "JSON object produced by biocortex_retrieval_opt_in_runtime_trial or biocortex_retrieval_opt_in_runtime_trial_review_packet. Unknown/raw fields are ignored."
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
        let source_packet = args.get("source_packet").cloned().unwrap_or(Value::Null);
        let reviewer = args
            .get("reviewer")
            .and_then(Value::as_str)
            .map(str::to_string);
        let commit = args
            .get("commit")
            .and_then(Value::as_str)
            .map(str::to_string);
        let forum_post_id = args
            .get("forum_post_id")
            .and_then(Value::as_str)
            .map(str::to_string);
        let memory_key = args
            .get("memory_key")
            .and_then(Value::as_str)
            .map(str::to_string);
        let payload = biocortex_retrieval_opt_in_redacted_order_artifact(
            BioCortexRetrievalOptInRedactedOrderArtifactOptions {
                source_packet,
                reviewer,
                commit,
                forum_post_id,
                memory_key,
            },
        );
        Ok(ToolResult::json_text(&payload))
    }
}

// ===========================================================================
//  biocortex_retrieval_opt_in_authorization_decision_packet — impl-only gate
// ===========================================================================

/// Read-only BioCortex retrieval opt-in authorization decision consumer. This
/// tool accepts an authorization request plus the human decision record and
/// emits an implementation-only gate packet. It never approves runtime adapter
/// influence, calls `memory_search`, runs BioCortex, or changes retrieval order.
pub struct BioCortexRetrievalOptInAuthorizationDecisionPacketTool;

impl BioCortexRetrievalOptInAuthorizationDecisionPacketTool {
    pub fn new() -> Self {
        Self
    }
}

impl Default for BioCortexRetrievalOptInAuthorizationDecisionPacketTool {
    fn default() -> Self {
        Self::new()
    }
}

#[async_trait]
impl McpTool for BioCortexRetrievalOptInAuthorizationDecisionPacketTool {
    fn name(&self) -> &'static str {
        "biocortex_retrieval_opt_in_authorization_decision_packet"
    }

    fn schema(&self) -> ToolSchema {
        ToolSchema {
            name: self.name().into(),
            description: "Read-only BioCortex retrieval opt-in authorization \
                 decision consumer. Accepts an authorization request and a human \
                 decision record, then emits an implementation-only gate packet. \
                 Does not call memory_search, run BioCortex, mutate memory, \
                 include raw query/keys/content, register an EmbeddingBackend, \
                 approve runtime influence, or alter retrieval order."
                .into(),
            input_schema: json!({
                "type": "object",
                "required": ["authorization_request", "authorization_decision"],
                "properties": {
                    "authorization_request": {
                        "type": "object",
                        "description": "JSON object produced by prepare-biocortex-retrieval-opt-in-authorization-request.sh. Unknown/raw fields are ignored."
                    },
                    "authorization_decision": {
                        "type": "object",
                        "description": "Human opt-in implementation authorization decision record. Unknown/raw fields are ignored."
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
                        "description": "Optional forum post id linking this decision packet."
                    },
                    "memory_key": {
                        "type": "string",
                        "description": "Optional memory key linking this decision packet."
                    }
                }
            }),
        }
    }

    async fn execute(&self, args: Value, _ctx: &ToolContext) -> Result<ToolResult> {
        let authorization_request = args
            .get("authorization_request")
            .cloned()
            .unwrap_or(Value::Null);
        let authorization_decision = args
            .get("authorization_decision")
            .cloned()
            .unwrap_or(Value::Null);
        let reviewer = args
            .get("reviewer")
            .and_then(Value::as_str)
            .map(str::to_string);
        let commit = args
            .get("commit")
            .and_then(Value::as_str)
            .map(str::to_string);
        let forum_post_id = args
            .get("forum_post_id")
            .and_then(Value::as_str)
            .map(str::to_string);
        let memory_key = args
            .get("memory_key")
            .and_then(Value::as_str)
            .map(str::to_string);
        let payload = biocortex_retrieval_opt_in_authorization_decision_packet(
            BioCortexRetrievalOptInAuthorizationDecisionPacketOptions {
                authorization_decision,
                authorization_request,
                reviewer,
                commit,
                forum_post_id,
                memory_key,
            },
        );
        Ok(ToolResult::json_text(&payload))
    }
}

// ===========================================================================
//  biocortex_retrieval_opt_in_post_implementation_review_gate — review gate
// ===========================================================================

/// Read-only BioCortex retrieval opt-in post-implementation review gate. This
/// tool accepts the authorization decision packet plus the opt-in plan fixture
/// and emits a readiness packet for a separate human runtime-influence review.
/// It never approves runtime adapter influence, calls `memory_search`, runs
/// BioCortex, or changes retrieval order.
pub struct BioCortexRetrievalOptInPostImplementationReviewGateTool;

impl BioCortexRetrievalOptInPostImplementationReviewGateTool {
    pub fn new() -> Self {
        Self
    }
}

impl Default for BioCortexRetrievalOptInPostImplementationReviewGateTool {
    fn default() -> Self {
        Self::new()
    }
}

#[async_trait]
impl McpTool for BioCortexRetrievalOptInPostImplementationReviewGateTool {
    fn name(&self) -> &'static str {
        "biocortex_retrieval_opt_in_post_implementation_review_gate"
    }

    fn schema(&self) -> ToolSchema {
        ToolSchema {
            name: self.name().into(),
            description: "Read-only BioCortex retrieval opt-in \
                 post-implementation review gate. Accepts an authorization \
                 decision packet and opt-in plan fixture, then emits readiness \
                 for a separate human runtime-influence review. Does not call \
                 memory_search, run BioCortex, mutate memory, include raw \
                 query/keys/content, register an EmbeddingBackend, approve \
                 runtime influence, or alter retrieval order."
                .into(),
            input_schema: json!({
                "type": "object",
                "required": ["authorization_decision_packet", "opt_in_plan"],
                "properties": {
                    "authorization_decision_packet": {
                        "type": "object",
                        "description": "JSON object produced by biocortex_retrieval_opt_in_authorization_decision_packet. Unknown/raw fields are ignored."
                    },
                    "opt_in_plan": {
                        "type": "object",
                        "description": "Machine-readable opt-in experiment plan fixture. Unknown/raw fields are ignored."
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
                        "description": "Optional forum post id linking this review gate."
                    },
                    "memory_key": {
                        "type": "string",
                        "description": "Optional memory key linking this review gate."
                    }
                }
            }),
        }
    }

    async fn execute(&self, args: Value, _ctx: &ToolContext) -> Result<ToolResult> {
        let authorization_decision_packet = args
            .get("authorization_decision_packet")
            .cloned()
            .unwrap_or(Value::Null);
        let opt_in_plan = args.get("opt_in_plan").cloned().unwrap_or(Value::Null);
        let reviewer = args
            .get("reviewer")
            .and_then(Value::as_str)
            .map(str::to_string);
        let commit = args
            .get("commit")
            .and_then(Value::as_str)
            .map(str::to_string);
        let forum_post_id = args
            .get("forum_post_id")
            .and_then(Value::as_str)
            .map(str::to_string);
        let memory_key = args
            .get("memory_key")
            .and_then(Value::as_str)
            .map(str::to_string);
        let payload = biocortex_retrieval_opt_in_post_implementation_review_gate(
            BioCortexRetrievalOptInPostImplementationReviewGateOptions {
                authorization_decision_packet,
                opt_in_plan,
                reviewer,
                commit,
                forum_post_id,
                memory_key,
            },
        );
        Ok(ToolResult::json_text(&payload))
    }
}

// ===========================================================================
//  biocortex_retrieval_opt_in_runtime_influence_review_request — request
// ===========================================================================

/// Read-only BioCortex retrieval opt-in runtime-influence review request. This
/// tool accepts the post-implementation review gate plus redacted order artifact
/// and may accept a redacted evidence aggregate summary. It emits a human
/// review request for explicit opt-in FTS influence. It never approves runtime
/// adapter influence, calls `memory_search`, runs BioCortex, or changes
/// retrieval order.
pub struct BioCortexRetrievalOptInRuntimeInfluenceReviewRequestTool;

impl BioCortexRetrievalOptInRuntimeInfluenceReviewRequestTool {
    pub fn new() -> Self {
        Self
    }
}

impl Default for BioCortexRetrievalOptInRuntimeInfluenceReviewRequestTool {
    fn default() -> Self {
        Self::new()
    }
}

#[async_trait]
impl McpTool for BioCortexRetrievalOptInRuntimeInfluenceReviewRequestTool {
    fn name(&self) -> &'static str {
        "biocortex_retrieval_opt_in_runtime_influence_review_request"
    }

    fn schema(&self) -> ToolSchema {
        ToolSchema {
            name: self.name().into(),
            description: "Read-only BioCortex retrieval opt-in \
                 runtime-influence review request. Accepts a post-implementation \
                 review gate, redacted order artifact, optional redacted \
                 evidence aggregate, and optional post-runtime evidence \
                 summary, then emits a request for separate human review of \
                 explicit opt-in FTS influence. Does not call \
                 memory_search, run BioCortex, mutate memory, include raw \
                 query/keys/content, register an EmbeddingBackend, approve \
                 runtime influence, or alter retrieval order."
                .into(),
            input_schema: json!({
                "type": "object",
                "required": ["post_implementation_review_gate", "redacted_order_artifact"],
                "properties": {
                    "post_implementation_review_gate": {
                        "type": "object",
                        "description": "JSON object produced by biocortex_retrieval_opt_in_post_implementation_review_gate. Unknown/raw fields are ignored."
                    },
                    "redacted_order_artifact": {
                        "type": "object",
                        "description": "JSON object produced by biocortex_retrieval_opt_in_redacted_order_artifact. Unknown/raw fields are ignored."
                    },
                    "redacted_evidence_aggregate": {
                        "type": "object",
                        "description": "Optional JSON object produced by biocortex_retrieval_opt_in_redacted_evidence_aggregate. Unknown/raw fields are ignored; the input body is not copied to output."
                    },
                    "evidence_summary": {
                        "type": "object",
                        "description": "Optional JSON object produced by biocortex_retrieval_opt_in_evidence_summary. Unknown/raw fields are ignored; the input body is not copied to output."
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
                        "description": "Optional forum post id linking this request."
                    },
                    "memory_key": {
                        "type": "string",
                        "description": "Optional memory key linking this request."
                    }
                }
            }),
        }
    }

    async fn execute(&self, args: Value, _ctx: &ToolContext) -> Result<ToolResult> {
        let post_implementation_review_gate = args
            .get("post_implementation_review_gate")
            .cloned()
            .unwrap_or(Value::Null);
        let redacted_order_artifact = args
            .get("redacted_order_artifact")
            .cloned()
            .unwrap_or(Value::Null);
        let redacted_evidence_aggregate = args.get("redacted_evidence_aggregate").cloned();
        let evidence_summary = args.get("evidence_summary").cloned();
        let reviewer = args
            .get("reviewer")
            .and_then(Value::as_str)
            .map(str::to_string);
        let commit = args
            .get("commit")
            .and_then(Value::as_str)
            .map(str::to_string);
        let forum_post_id = args
            .get("forum_post_id")
            .and_then(Value::as_str)
            .map(str::to_string);
        let memory_key = args
            .get("memory_key")
            .and_then(Value::as_str)
            .map(str::to_string);
        let payload = biocortex_retrieval_opt_in_runtime_influence_review_request(
            BioCortexRetrievalOptInRuntimeInfluenceReviewRequestOptions {
                post_implementation_review_gate,
                redacted_order_artifact,
                redacted_evidence_aggregate,
                evidence_summary,
                reviewer,
                commit,
                forum_post_id,
                memory_key,
            },
        );
        Ok(ToolResult::json_text(&payload))
    }
}

// ===========================================================================
//  biocortex_retrieval_opt_in_runtime_influence_decision_packet — decision
// ===========================================================================

/// Read-only BioCortex retrieval opt-in runtime-influence decision consumer.
/// This tool accepts a runtime-influence review request plus a separate human
/// decision record. It can authorize implementation of explicit opt-in FTS
/// runtime influence only; it never calls `memory_search`, runs BioCortex,
/// mutates memory, connects ordering behavior, or changes retrieval order.
pub struct BioCortexRetrievalOptInRuntimeInfluenceDecisionPacketTool;

impl BioCortexRetrievalOptInRuntimeInfluenceDecisionPacketTool {
    pub fn new() -> Self {
        Self
    }
}

impl Default for BioCortexRetrievalOptInRuntimeInfluenceDecisionPacketTool {
    fn default() -> Self {
        Self::new()
    }
}

#[async_trait]
impl McpTool for BioCortexRetrievalOptInRuntimeInfluenceDecisionPacketTool {
    fn name(&self) -> &'static str {
        "biocortex_retrieval_opt_in_runtime_influence_decision_packet"
    }

    fn schema(&self) -> ToolSchema {
        ToolSchema {
            name: self.name().into(),
            description: "Read-only BioCortex retrieval opt-in \
                 runtime-influence decision consumer. Accepts a \
                 runtime-influence review request and a separate human \
                 decision record, then emits a machine-checkable decision \
                 packet for explicit opt-in FTS runtime influence only. \
                 Does not call memory_search, run BioCortex, mutate memory, \
                 include raw query/keys/content or human decision text, \
                 register an EmbeddingBackend, connect ordering behavior, \
                 allow default search order changes, or alter retrieval order."
                .into(),
            input_schema: json!({
                "type": "object",
                "required": ["runtime_influence_review_request", "runtime_influence_decision"],
                "properties": {
                    "runtime_influence_review_request": {
                        "type": "object",
                        "description": "JSON object produced by biocortex_retrieval_opt_in_runtime_influence_review_request. Unknown/raw fields are ignored."
                    },
                    "runtime_influence_decision": {
                        "type": "object",
                        "description": "Human runtime-influence review decision record. Unknown/raw fields are ignored."
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
                        "description": "Optional forum post id linking this decision packet."
                    },
                    "memory_key": {
                        "type": "string",
                        "description": "Optional memory key linking this decision packet."
                    }
                }
            }),
        }
    }

    async fn execute(&self, args: Value, _ctx: &ToolContext) -> Result<ToolResult> {
        let runtime_influence_review_request = args
            .get("runtime_influence_review_request")
            .cloned()
            .unwrap_or(Value::Null);
        let runtime_influence_decision = args
            .get("runtime_influence_decision")
            .cloned()
            .unwrap_or(Value::Null);
        let reviewer = args
            .get("reviewer")
            .and_then(Value::as_str)
            .map(str::to_string);
        let commit = args
            .get("commit")
            .and_then(Value::as_str)
            .map(str::to_string);
        let forum_post_id = args
            .get("forum_post_id")
            .and_then(Value::as_str)
            .map(str::to_string);
        let memory_key = args
            .get("memory_key")
            .and_then(Value::as_str)
            .map(str::to_string);
        let payload = biocortex_retrieval_opt_in_runtime_influence_decision_packet(
            BioCortexRetrievalOptInRuntimeInfluenceDecisionPacketOptions {
                runtime_influence_review_request,
                runtime_influence_decision,
                reviewer,
                commit,
                forum_post_id,
                memory_key,
            },
        );
        Ok(ToolResult::json_text(&payload))
    }
}

// ===========================================================================
//  biocortex_retrieval_opt_in_store_trial — protected store wrapper connection
// ===========================================================================

/// Explicit opt-in BioCortex store trial. This tool calls AB store baseline
/// `memory_search`, runs the external BioCortex side-signal adapter only after a
/// runtime-influence decision packet authorizes it, then feeds the side-signal
/// into the protected opt-in store wrapper. Output is redacted to hashes/counts.
pub struct BioCortexRetrievalOptInStoreTrialTool {
    hub: Hub,
}

impl BioCortexRetrievalOptInStoreTrialTool {
    pub fn new(hub: Hub) -> Self {
        Self { hub }
    }
}

#[async_trait]
impl McpTool for BioCortexRetrievalOptInStoreTrialTool {
    fn name(&self) -> &'static str {
        "biocortex_retrieval_opt_in_store_trial"
    }

    fn schema(&self) -> ToolSchema {
        ToolSchema {
            name: self.name().into(),
            description: "Explicit opt-in BioCortex store trial. Calls AB store \
                 baseline memory_search, runs the external BioCortex side-signal \
                 adapter only when a runtime-influence decision packet and runtime \
                 gates authorize it, and feeds sanitized side-signal rows into the \
                 protected opt-in store wrapper. Returns only redacted hashes/counts; \
                 does not mutate memory, register an EmbeddingBackend, expose raw \
                 query/keys/content, or affect default memory_search."
                .into(),
            input_schema: json!({
                "type": "object",
                "required": ["runtime_influence_decision_packet", "query", "per_call_opt_in"],
                "properties": {
                    "runtime_influence_decision_packet": {
                        "type": "object",
                        "description": "JSON object produced by biocortex_retrieval_opt_in_runtime_influence_decision_packet. The tool consumes only safe summary fields and does not echo the packet."
                    },
                    "query": {
                        "type": "string",
                        "description": "FTS query for baseline memory_search. Output includes only a query hash."
                    },
                    "tags_any": {
                        "type": "array",
                        "items": { "type": "string" },
                        "description": "Optional tag filter forwarded to baseline memory_search. Output includes only the filter count."
                    },
                    "limit": {
                        "type": "integer",
                        "minimum": 1,
                        "maximum": 100,
                        "default": 10,
                        "description": "Maximum baseline candidates to retrieve from store memory_search."
                    },
                    "mode": {
                        "type": "string",
                        "enum": ["fts", "hybrid", "semantic"],
                        "default": "fts",
                        "description": "Retrieval mode. Only fts is authorized for runtime influence."
                    },
                    "per_call_opt_in": {
                        "type": "boolean",
                        "description": "Required explicit per-call opt-in bit."
                    },
                    "checkout_path": {
                        "type": "string",
                        "description": "Optional local biocortex-rs checkout. Defaults to AB_BIOCORTEX_RS, sibling checkout paths, then /tmp/biocortex-rs-ab-eval."
                    },
                    "timeout_ms": {
                        "type": "integer",
                        "minimum": 1000,
                        "maximum": 600000,
                        "default": 120000,
                        "description": "External side-signal adapter timeout in milliseconds."
                    },
                    "coverage_threshold": {
                        "type": "number",
                        "minimum": 0.0,
                        "maximum": 1.0,
                        "default": 0.8,
                        "description": "Minimum matched side-signal coverage required before the store wrapper may return experimental order."
                    },
                    "blend_alpha": {
                        "type": "number",
                        "minimum": 0.0,
                        "maximum": 1.0,
                        "default": 0.8,
                        "description": "Blend weight passed to the protected store wrapper."
                    },
                    "attempt_id": {
                        "type": "string",
                        "description": "Optional attempt id for audit correlation."
                    },
                    "commit": {
                        "type": "string",
                        "description": "Optional implementation commit under review."
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
        let runtime_influence_decision_packet = args
            .get("runtime_influence_decision_packet")
            .cloned()
            .unwrap_or(Value::Null);
        let query = args
            .get("query")
            .and_then(Value::as_str)
            .unwrap_or("")
            .to_string();
        let tags_any = args
            .get("tags_any")
            .cloned()
            .map(serde_json::from_value::<Vec<String>>)
            .transpose()
            .map_err(|e| ab_core::Error::Backend(format!("parse tags_any: {e}")))?
            .unwrap_or_default();
        let limit = args
            .get("limit")
            .and_then(Value::as_u64)
            .unwrap_or(10)
            .clamp(1, 100) as u32;
        let mode = args
            .get("mode")
            .and_then(Value::as_str)
            .unwrap_or("fts")
            .to_string();
        let per_call_opt_in = args
            .get("per_call_opt_in")
            .and_then(Value::as_bool)
            .unwrap_or(false);
        let checkout = args
            .get("checkout_path")
            .and_then(Value::as_str)
            .map(str::trim)
            .filter(|s| !s.is_empty())
            .map(PathBuf::from);
        let timeout_ms = args
            .get("timeout_ms")
            .and_then(Value::as_u64)
            .unwrap_or(120_000);
        let coverage_threshold = args
            .get("coverage_threshold")
            .and_then(Value::as_f64)
            .unwrap_or(0.8);
        let blend_alpha = args
            .get("blend_alpha")
            .and_then(Value::as_f64)
            .unwrap_or(0.8) as f32;
        let attempt_id = args
            .get("attempt_id")
            .and_then(Value::as_str)
            .map(str::to_string);
        let commit = args
            .get("commit")
            .and_then(Value::as_str)
            .map(str::to_string);

        let payload = biocortex_retrieval_opt_in_store_trial(
            store.as_ref(),
            BioCortexRetrievalOptInStoreTrialOptions {
                runtime_influence_decision_packet,
                query,
                tags_any,
                limit,
                mode,
                per_call_opt_in,
                checkout,
                timeout_ms,
                coverage_threshold,
                blend_alpha,
                attempt_id,
                commit,
            },
        )
        .await;
        Ok(ToolResult::json_text(&payload))
    }
}

// ===========================================================================
//  biocortex_retrieval_opt_in_gated_store_trial — transition-gated runtime entry
// ===========================================================================

/// Transition-gated explicit opt-in BioCortex store trial. This tool refuses to
/// call AB store baseline `memory_search` unless a runtime-transition gate
/// explicitly allows the FTS per-call opt-in transition.
pub struct BioCortexRetrievalOptInGatedStoreTrialTool {
    hub: Hub,
}

impl BioCortexRetrievalOptInGatedStoreTrialTool {
    pub fn new(hub: Hub) -> Self {
        Self { hub }
    }
}

#[async_trait]
impl McpTool for BioCortexRetrievalOptInGatedStoreTrialTool {
    fn name(&self) -> &'static str {
        "biocortex_retrieval_opt_in_gated_store_trial"
    }

    fn schema(&self) -> ToolSchema {
        ToolSchema {
            name: self.name().into(),
            description: "Transition-gated explicit opt-in BioCortex store trial. \
                 Consumes a runtime-transition gate and refuses to call AB store \
                 baseline memory_search unless that gate allows the explicit FTS \
                 per-call opt-in transition. After the gate passes it delegates to \
                 the protected opt-in store trial. Returns only redacted summaries; \
                 does not mutate memory, register an EmbeddingBackend, expose raw \
                 query/keys/content, or affect default memory_search."
                .into(),
            input_schema: json!({
                "type": "object",
                "required": [
                    "runtime_transition_gate",
                    "runtime_influence_decision_packet",
                    "query",
                    "per_call_opt_in"
                ],
                "properties": {
                    "runtime_transition_gate": {
                        "type": "object",
                        "description": "JSON object produced by biocortex_retrieval_opt_in_runtime_transition_gate. The tool consumes only safe summary fields and does not echo the gate."
                    },
                    "runtime_influence_decision_packet": {
                        "type": "object",
                        "description": "JSON object produced by biocortex_retrieval_opt_in_runtime_influence_decision_packet. The tool consumes only safe summary fields and does not echo the packet."
                    },
                    "query": {
                        "type": "string",
                        "description": "FTS query for baseline memory_search after the transition gate passes. Output includes only a query hash."
                    },
                    "tags_any": {
                        "type": "array",
                        "items": { "type": "string" },
                        "description": "Optional tag filter forwarded to baseline memory_search. Output includes only the filter count."
                    },
                    "limit": {
                        "type": "integer",
                        "minimum": 1,
                        "maximum": 100,
                        "default": 10,
                        "description": "Maximum baseline candidates to retrieve from store memory_search."
                    },
                    "mode": {
                        "type": "string",
                        "enum": ["fts", "hybrid", "semantic"],
                        "default": "fts",
                        "description": "Retrieval mode. Only fts is authorized for runtime influence."
                    },
                    "per_call_opt_in": {
                        "type": "boolean",
                        "description": "Required explicit per-call opt-in bit."
                    },
                    "checkout_path": {
                        "type": "string",
                        "description": "Optional local biocortex-rs checkout. Defaults to AB_BIOCORTEX_RS, sibling checkout paths, then /tmp/biocortex-rs-ab-eval."
                    },
                    "timeout_ms": {
                        "type": "integer",
                        "minimum": 1000,
                        "maximum": 600000,
                        "default": 120000,
                        "description": "External side-signal adapter timeout in milliseconds."
                    },
                    "coverage_threshold": {
                        "type": "number",
                        "minimum": 0.0,
                        "maximum": 1.0,
                        "default": 0.8,
                        "description": "Minimum matched side-signal coverage required before the store wrapper may return experimental order."
                    },
                    "blend_alpha": {
                        "type": "number",
                        "minimum": 0.0,
                        "maximum": 1.0,
                        "default": 0.8,
                        "description": "Blend weight passed to the protected store wrapper."
                    },
                    "attempt_id": {
                        "type": "string",
                        "description": "Optional attempt id for audit correlation."
                    },
                    "commit": {
                        "type": "string",
                        "description": "Optional implementation commit under review."
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
        let runtime_transition_gate = args
            .get("runtime_transition_gate")
            .cloned()
            .unwrap_or(Value::Null);
        let runtime_influence_decision_packet = args
            .get("runtime_influence_decision_packet")
            .cloned()
            .unwrap_or(Value::Null);
        let query = args
            .get("query")
            .and_then(Value::as_str)
            .unwrap_or("")
            .to_string();
        let tags_any = args
            .get("tags_any")
            .cloned()
            .map(serde_json::from_value::<Vec<String>>)
            .transpose()
            .map_err(|e| ab_core::Error::Backend(format!("parse tags_any: {e}")))?
            .unwrap_or_default();
        let limit = args
            .get("limit")
            .and_then(Value::as_u64)
            .unwrap_or(10)
            .clamp(1, 100) as u32;
        let mode = args
            .get("mode")
            .and_then(Value::as_str)
            .unwrap_or("fts")
            .to_string();
        let per_call_opt_in = args
            .get("per_call_opt_in")
            .and_then(Value::as_bool)
            .unwrap_or(false);
        let checkout = args
            .get("checkout_path")
            .and_then(Value::as_str)
            .map(str::trim)
            .filter(|s| !s.is_empty())
            .map(PathBuf::from);
        let timeout_ms = args
            .get("timeout_ms")
            .and_then(Value::as_u64)
            .unwrap_or(120_000);
        let coverage_threshold = args
            .get("coverage_threshold")
            .and_then(Value::as_f64)
            .unwrap_or(0.8);
        let blend_alpha = args
            .get("blend_alpha")
            .and_then(Value::as_f64)
            .unwrap_or(0.8) as f32;
        let attempt_id = args
            .get("attempt_id")
            .and_then(Value::as_str)
            .map(str::to_string);
        let commit = args
            .get("commit")
            .and_then(Value::as_str)
            .map(str::to_string);

        let payload = biocortex_retrieval_opt_in_gated_store_trial(
            store.as_ref(),
            BioCortexRetrievalOptInGatedStoreTrialOptions {
                runtime_transition_gate,
                runtime_influence_decision_packet,
                query,
                tags_any,
                limit,
                mode,
                per_call_opt_in,
                checkout,
                timeout_ms,
                coverage_threshold,
                blend_alpha,
                attempt_id,
                commit,
            },
        )
        .await;
        Ok(ToolResult::json_text(&payload))
    }
}

// ===========================================================================
//  biocortex_retrieval_opt_in_batch_diagnostics — redacted ranking diagnostics
// ===========================================================================

/// Batch redacted diagnostics for explicit opt-in BioCortex store trials. This
/// tool runs multiple protected store trials and aggregates only hashes/counts.
pub struct BioCortexRetrievalOptInBatchDiagnosticsTool {
    hub: Hub,
}

impl BioCortexRetrievalOptInBatchDiagnosticsTool {
    pub fn new(hub: Hub) -> Self {
        Self { hub }
    }
}

#[async_trait]
impl McpTool for BioCortexRetrievalOptInBatchDiagnosticsTool {
    fn name(&self) -> &'static str {
        "biocortex_retrieval_opt_in_batch_diagnostics"
    }

    fn schema(&self) -> ToolSchema {
        ToolSchema {
            name: self.name().into(),
            description: "Batch redacted diagnostics for explicit opt-in \
                 BioCortex store trials. Reuses the protected store-trial gate \
                 for every query, then aggregates baseline vs experimental \
                 order hashes, side-signal coverage, latency, and movement \
                 classes. Does not expose raw queries/keys/content, mutate \
                 memory, register an EmbeddingBackend, or affect default \
                 memory_search."
                .into(),
            input_schema: json!({
                "type": "object",
                "required": ["runtime_influence_decision_packet", "per_call_opt_in"],
                "properties": {
                    "runtime_influence_decision_packet": {
                        "type": "object",
                        "description": "JSON object produced by biocortex_retrieval_opt_in_runtime_influence_decision_packet. The tool consumes only safe summary fields and does not echo the packet."
                    },
                    "queries": {
                        "type": "array",
                        "items": { "type": "string" },
                        "description": "FTS queries to diagnose. Output includes only query hashes."
                    },
                    "query_cases": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "required": ["query"],
                            "properties": {
                                "query": {
                                    "type": "string",
                                    "description": "FTS query. Output includes only a query hash."
                                },
                                "class_label": {
                                    "type": "string",
                                    "description": "Optional operator-defined bucket label. It is normalized before output."
                                }
                            }
                        },
                        "description": "Optional query cases with sanitized bucket labels."
                    },
                    "tags_any": {
                        "type": "array",
                        "items": { "type": "string" },
                        "description": "Optional tag filter forwarded to each baseline memory_search. Output includes only the filter count."
                    },
                    "limit": {
                        "type": "integer",
                        "minimum": 1,
                        "maximum": 100,
                        "default": 10,
                        "description": "Maximum baseline candidates per query."
                    },
                    "mode": {
                        "type": "string",
                        "enum": ["fts", "hybrid", "semantic"],
                        "default": "fts",
                        "description": "Retrieval mode. Only fts is authorized for runtime influence."
                    },
                    "per_call_opt_in": {
                        "type": "boolean",
                        "description": "Required explicit per-call opt-in bit for every query."
                    },
                    "checkout_path": {
                        "type": "string",
                        "description": "Optional local biocortex-rs checkout. Defaults to AB_BIOCORTEX_RS, sibling checkout paths, then /tmp/biocortex-rs-ab-eval."
                    },
                    "timeout_ms": {
                        "type": "integer",
                        "minimum": 1000,
                        "maximum": 600000,
                        "default": 120000,
                        "description": "External side-signal adapter timeout per query in milliseconds."
                    },
                    "coverage_threshold": {
                        "type": "number",
                        "minimum": 0.0,
                        "maximum": 1.0,
                        "default": 0.8,
                        "description": "Minimum matched side-signal coverage required before the store wrapper may return experimental order."
                    },
                    "blend_alpha": {
                        "type": "number",
                        "minimum": 0.0,
                        "maximum": 1.0,
                        "default": 0.8,
                        "description": "Blend weight passed to the protected store wrapper."
                    },
                    "attempt_id": {
                        "type": "string",
                        "description": "Optional batch attempt id for audit correlation."
                    },
                    "commit": {
                        "type": "string",
                        "description": "Optional implementation commit under review."
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
        let runtime_influence_decision_packet = args
            .get("runtime_influence_decision_packet")
            .cloned()
            .unwrap_or(Value::Null);
        let queries = biocortex_batch_query_cases_from_args(&args);
        let tags_any = args
            .get("tags_any")
            .cloned()
            .map(serde_json::from_value::<Vec<String>>)
            .transpose()
            .map_err(|e| ab_core::Error::Backend(format!("parse tags_any: {e}")))?
            .unwrap_or_default();
        let limit = args
            .get("limit")
            .and_then(Value::as_u64)
            .unwrap_or(10)
            .clamp(1, 100) as u32;
        let mode = args
            .get("mode")
            .and_then(Value::as_str)
            .unwrap_or("fts")
            .to_string();
        let per_call_opt_in = args
            .get("per_call_opt_in")
            .and_then(Value::as_bool)
            .unwrap_or(false);
        let checkout = args
            .get("checkout_path")
            .and_then(Value::as_str)
            .map(str::trim)
            .filter(|s| !s.is_empty())
            .map(PathBuf::from);
        let timeout_ms = args
            .get("timeout_ms")
            .and_then(Value::as_u64)
            .unwrap_or(120_000);
        let coverage_threshold = args
            .get("coverage_threshold")
            .and_then(Value::as_f64)
            .unwrap_or(0.8);
        let blend_alpha = args
            .get("blend_alpha")
            .and_then(Value::as_f64)
            .unwrap_or(0.8) as f32;
        let attempt_id = args
            .get("attempt_id")
            .and_then(Value::as_str)
            .map(str::to_string);
        let commit = args
            .get("commit")
            .and_then(Value::as_str)
            .map(str::to_string);

        let payload = biocortex_retrieval_opt_in_batch_diagnostics(
            store.as_ref(),
            BioCortexRetrievalOptInBatchDiagnosticsOptions {
                runtime_influence_decision_packet,
                queries,
                tags_any,
                limit,
                mode,
                per_call_opt_in,
                checkout,
                timeout_ms,
                coverage_threshold,
                blend_alpha,
                attempt_id,
                commit,
            },
        )
        .await;
        Ok(ToolResult::json_text(&payload))
    }
}

// ===========================================================================
//  biocortex_retrieval_relevance_lift_eval — the read-only relevance yardstick
// ===========================================================================

/// Read-only relevance-lift eval. Samples memories, derives a self-retrieval
/// query per sample, runs baseline FTS memory_search, computes the BioCortex
/// side-signal, applies the production reorder blend (eval-local only), and
/// measures whether the reorder lifts the rank of the true source memory.
pub struct BioCortexRetrievalRelevanceLiftEvalTool {
    hub: Hub,
}

impl BioCortexRetrievalRelevanceLiftEvalTool {
    pub fn new(hub: Hub) -> Self {
        Self { hub }
    }
}

pub(super) fn relevance_lift_query_cases_from_args(args: &Value) -> Vec<RelevanceLiftQueryCase> {
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
                    Some(RelevanceLiftQueryCase {
                        query,
                        relevant_keys,
                        class_label,
                    })
                })
                .take(30)
                .collect::<Vec<_>>()
        })
        .unwrap_or_default()
}

#[async_trait]
impl McpTool for BioCortexRetrievalRelevanceLiftEvalTool {
    fn name(&self) -> &'static str {
        "biocortex_retrieval_relevance_lift_eval"
    }

    fn schema(&self) -> ToolSchema {
        ToolSchema {
            name: self.name().into(),
            description: "Read-only relevance-lift yardstick for the BioCortex \
                 retrieval side-signal. Samples memories, derives a \
                 self-retrieval query from each, runs baseline FTS \
                 memory_search, computes the biomimetic side-signal, applies \
                 the production reorder blend (EVAL-LOCAL — never returned as \
                 live recall), and measures whether the reorder lifts the rank \
                 of the true source via MRR / recall@k / rank-of-source. Answers \
                 the question the hashed-movement diagnostics omit: did the \
                 right memory rise? Self-retrieval labels are a PROXY and \
                 regressions are reported as regressions. Does not mutate \
                 memory, change default memory_search order, or write state."
                .into(),
            input_schema: json!({
                "type": "object",
                "properties": {
                    "sample_size": {
                        "type": "integer",
                        "minimum": 1,
                        "maximum": 30,
                        "default": 8,
                        "description": "How many memories to sample (head of the chosen sort)."
                    },
                    "kind": {
                        "type": "string",
                        "description": "Optional memory kind filter (e.g. 'lesson', 'decision')."
                    },
                    "query_cases": {
                        "type": "array",
                        "description": "Optional explicit downstream-query relevance cases. When present, these replace self-retrieval sampling. Raw queries and relevant keys are accepted as input but are not echoed in output.",
                        "items": {
                            "type": "object",
                            "required": ["query", "relevant_keys"],
                            "properties": {
                                "query": {
                                    "type": "string",
                                    "description": "Downstream-style FTS query to evaluate. Output includes only a query hash."
                                },
                                "relevant_keys": {
                                    "type": "array",
                                    "items": { "type": "string" },
                                    "description": "Known relevant memory keys for this query. Output includes only counts and rank metrics."
                                },
                                "class_label": {
                                    "type": "string",
                                    "description": "Optional sanitized bucket label for aggregate review."
                                }
                            }
                        }
                    },
                    "sort": {
                        "type": "string",
                        "enum": ["recent", "frequent", "newest", "by_importance"],
                        "default": "by_importance",
                        "description": "Sort used to pick the head sample."
                    },
                    "limit": {
                        "type": "integer",
                        "minimum": 5,
                        "maximum": 100,
                        "default": 20,
                        "description": "memory_search candidate limit per derived query."
                    },
                    "query_chars": {
                        "type": "integer",
                        "minimum": 16,
                        "maximum": 400,
                        "default": 120,
                        "description": "Chars of frontmatter-stripped content used as the AND-style query when or_terms=0 (char-safe)."
                    },
                    "or_terms": {
                        "type": "integer",
                        "minimum": 0,
                        "maximum": 24,
                        "default": 10,
                        "description": "When >0, build a BROAD query from the first N distinct tokens joined with OR (multi-candidate sets give the reorder rank headroom). 0 = precise AND-style char query (often returns just the source on distinctive memories)."
                    },
                    "include_related": {
                        "type": "boolean",
                        "default": true,
                        "description": "Fold each memory's related_keys into its relevant set (graph labels)."
                    },
                    "blend_alpha": {
                        "type": "number",
                        "minimum": 0.0,
                        "maximum": 1.0,
                        "default": 0.8,
                        "description": "Blend weight for the side-signal reorder (mirrors production)."
                    },
                    "coverage_threshold": {
                        "type": "number",
                        "minimum": 0.0,
                        "maximum": 1.0,
                        "default": 0.8,
                        "description": "Minimum side-signal coverage before the reorder gate engages (mirrors production)."
                    },
                    "checkout_path": {
                        "type": "string",
                        "description": "Optional local biocortex-rs checkout. Defaults to AB_BIOCORTEX_RS, sibling paths, then /tmp/biocortex-rs-ab-eval."
                    },
                    "timeout_ms": {
                        "type": "integer",
                        "minimum": 1000,
                        "maximum": 600000,
                        "default": 180000,
                        "description": "Per side-signal adapter call timeout in milliseconds (shells out to cargo; the first call may compile the example)."
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
        Ok(ToolResult::json_text(&payload))
    }
}

// ===========================================================================
//  biocortex_retrieval_opt_in_gated_batch_diagnostics — transition-gated batch
// ===========================================================================

/// Transition-gated batch diagnostics for explicit opt-in BioCortex store
/// trials. Every query consumes the same runtime-transition gate before it may
/// call the protected store-trial path.
pub struct BioCortexRetrievalOptInGatedBatchDiagnosticsTool {
    hub: Hub,
}

impl BioCortexRetrievalOptInGatedBatchDiagnosticsTool {
    pub fn new(hub: Hub) -> Self {
        Self { hub }
    }
}

#[async_trait]
impl McpTool for BioCortexRetrievalOptInGatedBatchDiagnosticsTool {
    fn name(&self) -> &'static str {
        "biocortex_retrieval_opt_in_gated_batch_diagnostics"
    }

    fn schema(&self) -> ToolSchema {
        ToolSchema {
            name: self.name().into(),
            description: "Transition-gated batch diagnostics for explicit \
                 opt-in BioCortex store trials. Consumes a runtime-transition \
                 gate before each query may call the protected store-trial \
                 path. Blocked gates return only redacted transition evidence \
                 and do not call memory_search or BioCortex. Does not mutate \
                 memory, register an EmbeddingBackend, expose raw queries/keys/\
                 content, or affect default memory_search."
                .into(),
            input_schema: json!({
                "type": "object",
                "required": [
                    "runtime_transition_gate",
                    "runtime_influence_decision_packet",
                    "per_call_opt_in"
                ],
                "properties": {
                    "runtime_transition_gate": {
                        "type": "object",
                        "description": "JSON object produced by biocortex_retrieval_opt_in_runtime_transition_gate. The tool consumes only safe summary fields and does not echo the gate."
                    },
                    "runtime_influence_decision_packet": {
                        "type": "object",
                        "description": "JSON object produced by biocortex_retrieval_opt_in_runtime_influence_decision_packet. The tool consumes only safe summary fields and does not echo the packet."
                    },
                    "queries": {
                        "type": "array",
                        "items": { "type": "string" },
                        "description": "FTS queries to diagnose. Output includes only query hashes."
                    },
                    "query_cases": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "required": ["query"],
                            "properties": {
                                "query": {
                                    "type": "string",
                                    "description": "FTS query. Output includes only a query hash."
                                },
                                "class_label": {
                                    "type": "string",
                                    "description": "Optional operator-defined bucket label. It is normalized before output."
                                }
                            }
                        },
                        "description": "Optional query cases with sanitized bucket labels."
                    },
                    "tags_any": {
                        "type": "array",
                        "items": { "type": "string" },
                        "description": "Optional tag filter forwarded to each baseline memory_search after the transition gate passes. Output includes only the filter count."
                    },
                    "limit": {
                        "type": "integer",
                        "minimum": 1,
                        "maximum": 100,
                        "default": 10,
                        "description": "Maximum baseline candidates per query."
                    },
                    "mode": {
                        "type": "string",
                        "enum": ["fts", "hybrid", "semantic"],
                        "default": "fts",
                        "description": "Retrieval mode. Only fts is authorized for runtime influence."
                    },
                    "per_call_opt_in": {
                        "type": "boolean",
                        "description": "Required explicit per-call opt-in bit for every query."
                    },
                    "checkout_path": {
                        "type": "string",
                        "description": "Optional local biocortex-rs checkout. Defaults to AB_BIOCORTEX_RS, sibling checkout paths, then /tmp/biocortex-rs-ab-eval."
                    },
                    "timeout_ms": {
                        "type": "integer",
                        "minimum": 1000,
                        "maximum": 600000,
                        "default": 120000,
                        "description": "External side-signal adapter timeout per query in milliseconds."
                    },
                    "coverage_threshold": {
                        "type": "number",
                        "minimum": 0.0,
                        "maximum": 1.0,
                        "default": 0.8,
                        "description": "Minimum matched side-signal coverage required before the store wrapper may return experimental order."
                    },
                    "blend_alpha": {
                        "type": "number",
                        "minimum": 0.0,
                        "maximum": 1.0,
                        "default": 0.8,
                        "description": "Blend weight passed to the protected store wrapper."
                    },
                    "attempt_id": {
                        "type": "string",
                        "description": "Optional batch attempt id for audit correlation."
                    },
                    "commit": {
                        "type": "string",
                        "description": "Optional implementation commit under review."
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
        let runtime_transition_gate = args
            .get("runtime_transition_gate")
            .cloned()
            .unwrap_or(Value::Null);
        let runtime_influence_decision_packet = args
            .get("runtime_influence_decision_packet")
            .cloned()
            .unwrap_or(Value::Null);
        let queries = biocortex_batch_query_cases_from_args(&args);
        let tags_any = args
            .get("tags_any")
            .cloned()
            .map(serde_json::from_value::<Vec<String>>)
            .transpose()
            .map_err(|e| ab_core::Error::Backend(format!("parse tags_any: {e}")))?
            .unwrap_or_default();
        let limit = args
            .get("limit")
            .and_then(Value::as_u64)
            .unwrap_or(10)
            .clamp(1, 100) as u32;
        let mode = args
            .get("mode")
            .and_then(Value::as_str)
            .unwrap_or("fts")
            .to_string();
        let per_call_opt_in = args
            .get("per_call_opt_in")
            .and_then(Value::as_bool)
            .unwrap_or(false);
        let checkout = args
            .get("checkout_path")
            .and_then(Value::as_str)
            .map(str::trim)
            .filter(|s| !s.is_empty())
            .map(PathBuf::from);
        let timeout_ms = args
            .get("timeout_ms")
            .and_then(Value::as_u64)
            .unwrap_or(120_000);
        let coverage_threshold = args
            .get("coverage_threshold")
            .and_then(Value::as_f64)
            .unwrap_or(0.8);
        let blend_alpha = args
            .get("blend_alpha")
            .and_then(Value::as_f64)
            .unwrap_or(0.8) as f32;
        let attempt_id = args
            .get("attempt_id")
            .and_then(Value::as_str)
            .map(str::to_string);
        let commit = args
            .get("commit")
            .and_then(Value::as_str)
            .map(str::to_string);

        let payload = biocortex_retrieval_opt_in_gated_batch_diagnostics(
            store.as_ref(),
            BioCortexRetrievalOptInGatedBatchDiagnosticsOptions {
                runtime_transition_gate,
                runtime_influence_decision_packet,
                queries,
                tags_any,
                limit,
                mode,
                per_call_opt_in,
                checkout,
                timeout_ms,
                coverage_threshold,
                blend_alpha,
                attempt_id,
                commit,
            },
        )
        .await;
        Ok(ToolResult::json_text(&payload))
    }
}

// ===========================================================================
//  biocortex_retrieval_opt_in_runtime_readiness_packet - readiness summary
// ===========================================================================

/// Read-only BioCortex retrieval opt-in runtime-readiness packet. This tool
/// consumes aggregate-backed runtime-influence decision, store-trial, and
/// legacy or transition-gated batch-diagnostics summaries to report whether
/// the explicit opt-in FTS control plane is ready. It never calls
/// `memory_search`, runs BioCortex, writes approval, exposes raw
/// query/key/content data, or changes ordering.
pub struct BioCortexRetrievalOptInRuntimeReadinessPacketTool;

impl BioCortexRetrievalOptInRuntimeReadinessPacketTool {
    pub fn new() -> Self {
        Self
    }
}

impl Default for BioCortexRetrievalOptInRuntimeReadinessPacketTool {
    fn default() -> Self {
        Self::new()
    }
}

#[async_trait]
impl McpTool for BioCortexRetrievalOptInRuntimeReadinessPacketTool {
    fn name(&self) -> &'static str {
        "biocortex_retrieval_opt_in_runtime_readiness_packet"
    }

    fn schema(&self) -> ToolSchema {
        ToolSchema {
            name: self.name().into(),
            description: "Read-only BioCortex retrieval opt-in runtime-readiness \
                 packet. Consumes aggregate-backed runtime-influence decision, \
                 store-trial, and legacy or transition-gated batch-diagnostics \
                 summaries to report whether the explicit opt-in FTS control \
                 plane is ready. Distinguishes empty live probes from blocked \
                 control-plane state. Does not \
                 call memory_search, run BioCortex, mutate memory, write approval, \
                 include raw query/keys/content or human decision text, register \
                 an EmbeddingBackend, allow default search order changes, or \
                 alter retrieval order."
                .into(),
            input_schema: json!({
                "type": "object",
                "required": [
                    "runtime_influence_decision_packet",
                    "store_trial",
                    "batch_diagnostics"
                ],
                "properties": {
                    "runtime_influence_decision_packet": {
                        "type": "object",
                        "description": "JSON object produced by biocortex_retrieval_opt_in_runtime_influence_decision_packet. The tool consumes only safe summary fields and does not echo the packet."
                    },
                    "store_trial": {
                        "type": "object",
                        "description": "JSON object produced by biocortex_retrieval_opt_in_store_trial. The tool consumes only safe summary fields and does not echo the trial body."
                    },
                    "batch_diagnostics": {
                        "type": "object",
                        "description": "JSON object produced by biocortex_retrieval_opt_in_batch_diagnostics or biocortex_retrieval_opt_in_gated_batch_diagnostics. The tool consumes only safe aggregate fields and does not echo query rows."
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
                        "description": "Optional forum post id linking this readiness packet."
                    },
                    "memory_key": {
                        "type": "string",
                        "description": "Optional memory key linking this readiness packet."
                    }
                }
            }),
        }
    }

    async fn execute(&self, args: Value, _ctx: &ToolContext) -> Result<ToolResult> {
        let runtime_influence_decision_packet = args
            .get("runtime_influence_decision_packet")
            .cloned()
            .unwrap_or(Value::Null);
        let store_trial = args.get("store_trial").cloned().unwrap_or(Value::Null);
        let batch_diagnostics = args
            .get("batch_diagnostics")
            .cloned()
            .unwrap_or(Value::Null);
        let reviewer = args
            .get("reviewer")
            .and_then(Value::as_str)
            .map(str::to_string);
        let commit = args
            .get("commit")
            .and_then(Value::as_str)
            .map(str::to_string);
        let forum_post_id = args
            .get("forum_post_id")
            .and_then(Value::as_str)
            .map(str::to_string);
        let memory_key = args
            .get("memory_key")
            .and_then(Value::as_str)
            .map(str::to_string);

        let payload = biocortex_retrieval_opt_in_runtime_readiness_packet(
            BioCortexRetrievalOptInRuntimeReadinessPacketOptions {
                runtime_influence_decision_packet,
                store_trial,
                batch_diagnostics,
                reviewer,
                commit,
                forum_post_id,
                memory_key,
            },
        );
        Ok(ToolResult::json_text(&payload))
    }
}

// ===========================================================================
//  biocortex_retrieval_opt_in_runtime_transition_gate - readiness-gated switch
// ===========================================================================

/// Read-only BioCortex retrieval opt-in runtime-transition gate. This tool
/// consumes a runtime-readiness packet and reports whether a requested
/// explicit opt-in FTS transition may proceed. It never calls `memory_search`,
/// runs BioCortex, writes approval, exposes raw data, or changes default order.
pub struct BioCortexRetrievalOptInRuntimeTransitionGateTool;

impl BioCortexRetrievalOptInRuntimeTransitionGateTool {
    pub fn new() -> Self {
        Self
    }
}

impl Default for BioCortexRetrievalOptInRuntimeTransitionGateTool {
    fn default() -> Self {
        Self::new()
    }
}

pub(super) fn mcp_env_truthy(key: &str) -> bool {
    std::env::var(key)
        .ok()
        .map(|value| {
            matches!(
                value.trim().to_ascii_lowercase().as_str(),
                "1" | "true" | "yes" | "on"
            )
        })
        .unwrap_or(false)
}

#[async_trait]
impl McpTool for BioCortexRetrievalOptInRuntimeTransitionGateTool {
    fn name(&self) -> &'static str {
        "biocortex_retrieval_opt_in_runtime_transition_gate"
    }

    fn schema(&self) -> ToolSchema {
        ToolSchema {
            name: self.name().into(),
            description: "Read-only BioCortex retrieval opt-in runtime-transition \
                 gate. Consumes a runtime-readiness packet and checks that the \
                 requested transition is explicit per-call FTS, readiness-gated, \
                 and not operator-disabled. Does not call memory_search, run \
                 BioCortex, mutate memory, write approval, include raw query/keys/\
                 content or human decision text, register an EmbeddingBackend, \
                 allow default search order changes, or alter retrieval order."
                .into(),
            input_schema: json!({
                "type": "object",
                "required": ["runtime_readiness_packet"],
                "properties": {
                    "runtime_readiness_packet": {
                        "type": "object",
                        "description": "JSON object produced by biocortex_retrieval_opt_in_runtime_readiness_packet. The tool consumes only safe summary fields and does not echo the packet."
                    },
                    "mode": {
                        "type": "string",
                        "default": "fts",
                        "description": "Requested retrieval mode. Only fts can pass this transition gate."
                    },
                    "per_call_opt_in": {
                        "type": "boolean",
                        "default": false,
                        "description": "Required explicit per-call opt-in bit."
                    },
                    "operator_disabled": {
                        "type": "boolean",
                        "default": false,
                        "description": "Treat the operator disable switch as active for this gate. The environment variable AB_BIOCORTEX_RETRIEVAL_DISABLE is also honored."
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
                        "description": "Optional forum post id linking this transition gate."
                    },
                    "memory_key": {
                        "type": "string",
                        "description": "Optional memory key linking this transition gate."
                    }
                }
            }),
        }
    }

    async fn execute(&self, args: Value, _ctx: &ToolContext) -> Result<ToolResult> {
        let runtime_readiness_packet = args
            .get("runtime_readiness_packet")
            .cloned()
            .unwrap_or(Value::Null);
        let mode = args
            .get("mode")
            .and_then(Value::as_str)
            .unwrap_or("fts")
            .to_string();
        let per_call_opt_in = args
            .get("per_call_opt_in")
            .and_then(Value::as_bool)
            .unwrap_or(false);
        let operator_disabled = args
            .get("operator_disabled")
            .and_then(Value::as_bool)
            .unwrap_or(false)
            || mcp_env_truthy(BIOCORTEX_RETRIEVAL_DISABLE_ENV);
        let reviewer = args
            .get("reviewer")
            .and_then(Value::as_str)
            .map(str::to_string);
        let commit = args
            .get("commit")
            .and_then(Value::as_str)
            .map(str::to_string);
        let forum_post_id = args
            .get("forum_post_id")
            .and_then(Value::as_str)
            .map(str::to_string);
        let memory_key = args
            .get("memory_key")
            .and_then(Value::as_str)
            .map(str::to_string);

        let payload = biocortex_retrieval_opt_in_runtime_transition_gate(
            BioCortexRetrievalOptInRuntimeTransitionGateOptions {
                runtime_readiness_packet,
                mode,
                per_call_opt_in,
                operator_disabled,
                reviewer,
                commit,
                forum_post_id,
                memory_key,
            },
        );
        Ok(ToolResult::json_text(&payload))
    }
}

pub(super) fn biocortex_batch_query_cases_from_args(
    args: &Value,
) -> Vec<BioCortexRetrievalOptInBatchQueryCase> {
    let mut cases = Vec::new();
    if let Some(values) = args.get("queries").and_then(Value::as_array) {
        for value in values {
            if let Some(query) = value.as_str() {
                cases.push(BioCortexRetrievalOptInBatchQueryCase {
                    query: query.to_string(),
                    class_label: None,
                });
            }
        }
    }
    if let Some(values) = args.get("query_cases").and_then(Value::as_array) {
        for value in values {
            if let Some(query) = value.get("query").and_then(Value::as_str) {
                let class_label = value
                    .get("class_label")
                    .and_then(Value::as_str)
                    .map(str::to_string);
                cases.push(BioCortexRetrievalOptInBatchQueryCase {
                    query: query.to_string(),
                    class_label,
                });
            }
        }
    }
    cases
}

// ===========================================================================
//   biocortex_retrieval_shadow — review-only retrieval side-signal report
// ===========================================================================

/// Review-only BioCortex retrieval side-signal surface. This tool accepts
/// explicit query/candidate rows and reports advisory BioCortex side-signal
/// evidence. It does not call `memory_search`, does not mutate AB memory, and
/// does not change returned retrieval order.
#[cfg(feature = "biocortex-retrieval-shadow")]
pub struct BioCortexRetrievalShadowTool;

#[cfg(feature = "biocortex-retrieval-shadow")]
impl BioCortexRetrievalShadowTool {
    pub fn new() -> Self {
        Self
    }
}

#[cfg(feature = "biocortex-retrieval-shadow")]
impl Default for BioCortexRetrievalShadowTool {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(feature = "biocortex-retrieval-shadow")]
#[async_trait]
impl McpTool for BioCortexRetrievalShadowTool {
    fn name(&self) -> &'static str {
        "biocortex_retrieval_shadow"
    }

    fn schema(&self) -> ToolSchema {
        ToolSchema {
            name: self.name().into(),
            description: "Review-only BioCortex retrieval side-signal report. \
                 Accepts explicit query/candidate rows, runs the optional \
                 BioCortex side-signal adapter only when runtime-enabled, and \
                 returns an advisory report with runtime_adapter_approved=false. \
                 Does not call memory_search, mutate memory, register an \
                 EmbeddingBackend, or alter retrieval order."
                .into(),
            input_schema: json!({
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Query text to evaluate against explicit candidates."
                    },
                    "candidates": {
                        "type": "array",
                        "minItems": 1,
                        "items": {
                            "type": "object",
                            "properties": {
                                "key": { "type": "string" },
                                "content": { "type": "string" }
                            },
                            "required": ["key", "content"]
                        },
                        "description": "Explicit candidate rows. The tool never fetches or mutates memory_search results."
                    },
                    "expected_key": {
                        "type": "string",
                        "description": "Optional expected key for labeled regression reporting."
                    },
                    "checkout_path": {
                        "type": "string",
                        "description": "Optional local biocortex-rs checkout. Defaults to AB_BIOCORTEX_RS, sibling checkout paths, then /tmp/biocortex-rs-ab-eval."
                    },
                    "timeout_ms": {
                        "type": "integer",
                        "minimum": 1000,
                        "maximum": 600000,
                        "default": 120000,
                        "description": "External side-signal adapter timeout in milliseconds."
                    },
                    "include_raw": {
                        "type": "boolean",
                        "default": false,
                        "description": "Include raw stdout/stderr from the external adapter."
                    }
                },
                "required": ["query", "candidates"]
            }),
        }
    }

    async fn execute(&self, args: Value, _ctx: &ToolContext) -> Result<ToolResult> {
        let query = args
            .get("query")
            .and_then(Value::as_str)
            .unwrap_or("")
            .to_string();
        let candidates_value = args.get("candidates").cloned().unwrap_or_else(|| json!([]));
        let candidates =
            serde_json::from_value::<Vec<BioCortexRetrievalCandidate>>(candidates_value)
                .map_err(|e| ab_core::Error::Backend(format!("parse candidates: {e}")))?;
        let expected_key = args
            .get("expected_key")
            .and_then(Value::as_str)
            .map(str::to_string);
        let checkout = args
            .get("checkout_path")
            .and_then(Value::as_str)
            .map(str::trim)
            .filter(|s| !s.is_empty())
            .map(PathBuf::from);
        let timeout_ms = args
            .get("timeout_ms")
            .and_then(Value::as_u64)
            .unwrap_or(120_000);
        let include_raw = args
            .get("include_raw")
            .and_then(Value::as_bool)
            .unwrap_or(false);

        let payload = biocortex_retrieval_shadow_report(BioCortexRetrievalShadowOptions {
            query,
            candidates,
            expected_key,
            checkout,
            timeout_ms,
            include_raw,
        })
        .await;
        Ok(ToolResult::json_text(&payload))
    }
}

