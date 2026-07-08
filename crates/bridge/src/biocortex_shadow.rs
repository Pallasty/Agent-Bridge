//! Read-only BioCortex shadow report adapter.
//!
//! This module intentionally does not link `biocortex-rs` into the AB runtime.
//! It runs a local checkout's sanctioned shadow examples and projects their
//! deterministic `key=value` output into AB status JSON.

use crate::biocortex_capability_ledger::BIOCORTEX_CAPABILITY_LEDGER_REPORT_PACKET_SCHEMA;
use crate::shadow_cortex::{ShadowCortexEvent, ShadowCortexReplayFixture, SignalScope};
use ab_store::{
    biocortex_opt_in_apply_side_signal, cosine_similarity, embedding::default_backend,
    BioCortexRetrievalOptInRequest, BioCortexRetrievalOptInSearchOptions,
    BioCortexRetrievalOptInSideSignal, MemoryListSort, MemoryRecord, MemorySearchHit, StateStore,
};
use serde::{Deserialize, Serialize};
use serde_json::{json, Map, Number, Value};
use sha2::{Digest, Sha256};
use std::collections::{BTreeMap, BTreeSet};
use std::path::{Path, PathBuf};
use std::time::{Duration, Instant, SystemTime, UNIX_EPOCH};
use tokio::process::Command as TokioCommand;

pub const BIOCORTEX_SHADOW_SCHEMA: &str = "agent_bridge.biocortex_shadow_digest.v0";
pub const BIOCORTEX_REPLAY_COMPARISON_SCHEMA: &str = "agent_bridge.biocortex_replay_comparison.v0";
pub const BIOCORTEX_RETRIEVAL_SHADOW_SCHEMA: &str =
    "agent_bridge.biocortex_retrieval_shadow_report.v0";
pub const BIOCORTEX_RETRIEVAL_RUNTIME_APPROVAL_PACKET_SCHEMA: &str =
    "agent_bridge.biocortex_retrieval.runtime_approval_packet_preview.v0";
pub const BIOCORTEX_RETRIEVAL_OPT_IN_GATE_SCHEMA: &str =
    "agent_bridge.biocortex_retrieval.opt_in_gate.v0";
pub const BIOCORTEX_RETRIEVAL_OPT_IN_AUDIT_SCHEMA: &str =
    "agent_bridge.biocortex_retrieval.opt_in_call_audit.v0";
pub const BIOCORTEX_RETRIEVAL_OPT_IN_DRY_RUN_SCHEMA: &str =
    "agent_bridge.biocortex_retrieval.opt_in_dry_run_plan.v0";
pub const BIOCORTEX_RETRIEVAL_OPT_IN_REVIEW_PACKET_SCHEMA: &str =
    "agent_bridge.biocortex_retrieval.opt_in_review_packet.v0";
pub const BIOCORTEX_RETRIEVAL_OPT_IN_EXECUTION_PACKET_SCHEMA: &str =
    "agent_bridge.biocortex_retrieval.opt_in_execution_packet.v0";
pub const BIOCORTEX_RETRIEVAL_OPT_IN_RUNTIME_TRIAL_SCHEMA: &str =
    "agent_bridge.biocortex_retrieval.opt_in_runtime_trial.v0";
pub const BIOCORTEX_RETRIEVAL_OPT_IN_RUNTIME_TRIAL_REVIEW_PACKET_SCHEMA: &str =
    "agent_bridge.biocortex_retrieval.opt_in_runtime_trial_review_packet.v0";
pub const BIOCORTEX_RETRIEVAL_OPT_IN_ORDER_DIFF_PACKET_SCHEMA: &str =
    "agent_bridge.biocortex_retrieval.opt_in_order_diff_packet.v0";
pub const BIOCORTEX_RETRIEVAL_OPT_IN_REDACTED_ORDER_ARTIFACT_SCHEMA: &str =
    "agent_bridge.biocortex_retrieval.opt_in_redacted_order_artifact.v0";
pub const BIOCORTEX_RETRIEVAL_OPT_IN_AUTHORIZATION_DECISION_PACKET_SCHEMA: &str =
    "agent_bridge.biocortex_retrieval.opt_in_authorization_decision_packet.v0";
pub const BIOCORTEX_RETRIEVAL_OPT_IN_POST_IMPLEMENTATION_REVIEW_GATE_SCHEMA: &str =
    "agent_bridge.biocortex_retrieval.opt_in_post_implementation_review_gate.v0";
pub const BIOCORTEX_RETRIEVAL_OPT_IN_RUNTIME_INFLUENCE_REVIEW_REQUEST_SCHEMA: &str =
    "agent_bridge.biocortex_retrieval.opt_in_runtime_influence_review_request.v0";
pub const BIOCORTEX_RETRIEVAL_OPT_IN_REDACTED_EVIDENCE_AGGREGATE_SCHEMA: &str =
    "agent_bridge.biocortex_retrieval.opt_in_redacted_evidence_aggregate.v0";
pub const BIOCORTEX_RETRIEVAL_OPT_IN_EVIDENCE_SUMMARY_SCHEMA: &str =
    "agent_bridge.biocortex_retrieval.opt_in_evidence_summary.v0";
pub const BIOCORTEX_RETRIEVAL_OPT_IN_RUNTIME_INFLUENCE_DECISION_PACKET_SCHEMA: &str =
    "agent_bridge.biocortex_retrieval.opt_in_runtime_influence_decision_packet.v0";
pub const BIOCORTEX_RETRIEVAL_OPT_IN_STORE_TRIAL_SCHEMA: &str =
    "agent_bridge.biocortex_retrieval.opt_in_store_trial.v0";
pub const BIOCORTEX_RETRIEVAL_OPT_IN_GATED_STORE_TRIAL_SCHEMA: &str =
    "agent_bridge.biocortex_retrieval.opt_in_gated_store_trial.v0";
pub const BIOCORTEX_RETRIEVAL_OPT_IN_BATCH_DIAGNOSTICS_SCHEMA: &str =
    "agent_bridge.biocortex_retrieval.opt_in_batch_diagnostics.v0";
pub const BIOCORTEX_RETRIEVAL_RELEVANCE_LIFT_EVAL_SCHEMA: &str =
    "agent_bridge.biocortex_retrieval.relevance_lift_eval.v0";
pub const BIOCORTEX_RETRIEVAL_OPT_IN_GATED_BATCH_DIAGNOSTICS_SCHEMA: &str =
    "agent_bridge.biocortex_retrieval.opt_in_gated_batch_diagnostics.v0";
pub const BIOCORTEX_RETRIEVAL_OPT_IN_RUNTIME_READINESS_PACKET_SCHEMA: &str =
    "agent_bridge.biocortex_retrieval.opt_in_runtime_readiness_packet.v0";
pub const BIOCORTEX_RETRIEVAL_OPT_IN_RUNTIME_TRANSITION_GATE_SCHEMA: &str =
    "agent_bridge.biocortex_retrieval.opt_in_runtime_transition_gate.v0";
pub const BIOCORTEX_RETRIEVAL_POST_SEMANTIC_DIVERSE_REVIEW_SCHEMA: &str =
    "agent_bridge.biocortex_retrieval.post_semantic_diverse_review.v0";
pub const BIOCORTEX_RETRIEVAL_DOWNSTREAM_AIO_CHECKPOINT_SELECTION_SCHEMA: &str =
    "agent_bridge.biocortex_retrieval.downstream_aio_checkpoint_selection.v0";
pub const BIOCORTEX_RETRIEVAL_DOWNSTREAM_AIO_RUNTIME_EVIDENCE_HANDOFF_SCHEMA: &str =
    "agent_bridge.biocortex_retrieval.downstream_aio_runtime_evidence_handoff.v0";
pub const BIOCORTEX_SUBSTRATE_REPLAY_PLAN_SCHEMA: &str =
    "agent_bridge.biocortex_substrate_replay_plan.v0";
pub const BIOCORTEX_CHECKOUT_ENV: &str = "AB_BIOCORTEX_RS";
pub const BIOCORTEX_RETRIEVAL_SHADOW_ENABLE_ENV: &str = "AB_BIOCORTEX_RETRIEVAL_SHADOW";
pub const BIOCORTEX_RETRIEVAL_OPT_IN_ENABLE_ENV: &str = "AB_BIOCORTEX_RETRIEVAL_OPT_IN";
pub const BIOCORTEX_RETRIEVAL_DISABLE_ENV: &str = "AB_BIOCORTEX_RETRIEVAL_DISABLE";

const DEFAULT_TIMEOUT_MS: u64 = 120_000;
const CONSERVATIVE_RETRIEVAL_ALPHA: f32 = 0.20;
const CANDIDATE_STRONG_RETRIEVAL_ALPHA: f32 = 0.80;

#[derive(Debug, Clone)]
pub struct BioCortexShadowOptions {
    pub checkout: Option<PathBuf>,
    pub benchmark: String,
    pub timeout_ms: u64,
    pub include_raw: bool,
    pub fixture_projection: Option<Value>,
}

#[derive(Debug, Clone)]
pub struct BioCortexReplayComparisonOptions {
    pub checkout: Option<PathBuf>,
    pub benchmark: String,
    pub timeout_ms: u64,
    pub include_raw: bool,
    pub include_events: bool,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct BioCortexRetrievalCandidate {
    pub key: String,
    pub content: String,
}

#[derive(Debug, Clone)]
pub struct BioCortexRetrievalShadowOptions {
    pub query: String,
    pub candidates: Vec<BioCortexRetrievalCandidate>,
    pub expected_key: Option<String>,
    pub checkout: Option<PathBuf>,
    pub timeout_ms: u64,
    pub include_raw: bool,
}

#[derive(Debug, Clone, Default)]
pub struct BioCortexRetrievalApprovalPacketOptions {
    pub target_host: Option<String>,
    pub branch: Option<String>,
    pub commit: Option<String>,
    pub reviewer: Option<String>,
    pub agent_attestor: Option<String>,
    pub agent_attestation_decision: Option<String>,
    pub agent_attestation_summary: Option<String>,
    pub human_authorization_scope: Option<String>,
    pub verification_status: Option<String>,
    pub verification_captured_at: Option<String>,
    pub current_gate_status: Option<String>,
    pub hard_holdout_gate_status: Option<String>,
    pub side_signal_p95_ms_for_5_candidates: Option<String>,
    pub default_memory_search_added_latency_ms: Option<String>,
    pub exact_call_site: Option<String>,
    pub fail_open_behavior: Option<String>,
    pub rollback_command: Option<String>,
    pub forum_decision_post_id: Option<String>,
    pub memory_key: Option<String>,
}

#[derive(Debug, Clone)]
pub struct BioCortexRetrievalOptInAuditOptions {
    pub mode: String,
    pub per_call_opt_in: bool,
    pub query: Option<String>,
    pub baseline_keys: Vec<String>,
    pub side_signal_status: Option<String>,
    pub fallback_reason: Option<String>,
    pub latency_ms: Option<f64>,
    pub runtime_readiness_packet: Option<Value>,
    pub runtime_transition_gate: Option<Value>,
    pub gated_store_trial: Option<Value>,
    pub gated_batch_diagnostics: Option<Value>,
}

#[derive(Debug, Clone)]
pub struct BioCortexRetrievalOptInDryRunOptions {
    pub mode: String,
    pub per_call_opt_in: bool,
    pub query: Option<String>,
    pub baseline_keys: Vec<String>,
    pub baseline_completed: bool,
    pub timeout_ms: u64,
    pub coverage_threshold: f64,
}

#[derive(Debug, Clone)]
pub struct BioCortexRetrievalOptInReviewPacketOptions {
    pub dry_run_plan: Value,
    pub reviewer: Option<String>,
    pub commit: Option<String>,
    pub forum_post_id: Option<String>,
    pub memory_key: Option<String>,
}

#[derive(Debug, Clone)]
pub struct BioCortexRetrievalOptInExecutionPacketOptions {
    pub review_packet: Value,
    pub per_call_opt_in: bool,
    pub attempt_id: Option<String>,
    pub commit: Option<String>,
}

#[derive(Debug, Clone)]
pub struct BioCortexRetrievalOptInRuntimeTrialOptions {
    pub execution_packet: Value,
    pub query: String,
    pub candidates: Vec<BioCortexRetrievalCandidate>,
    pub expected_key: Option<String>,
    pub checkout: Option<PathBuf>,
    pub timeout_ms: u64,
    pub coverage_threshold: f64,
    pub attempt_id: Option<String>,
    pub commit: Option<String>,
}

#[derive(Debug, Clone)]
pub struct BioCortexRetrievalOptInRuntimeTrialReviewPacketOptions {
    pub runtime_trial: Value,
    pub reviewer: Option<String>,
    pub commit: Option<String>,
    pub forum_post_id: Option<String>,
    pub memory_key: Option<String>,
}

#[derive(Debug, Clone)]
pub struct BioCortexRetrievalOptInOrderDiffPacketOptions {
    pub source_packet: Value,
    pub reviewer: Option<String>,
    pub commit: Option<String>,
    pub forum_post_id: Option<String>,
    pub memory_key: Option<String>,
}

#[derive(Debug, Clone)]
pub struct BioCortexRetrievalOptInRedactedOrderArtifactOptions {
    pub source_packet: Value,
    pub reviewer: Option<String>,
    pub commit: Option<String>,
    pub forum_post_id: Option<String>,
    pub memory_key: Option<String>,
}

#[derive(Debug, Clone)]
pub struct BioCortexRetrievalOptInAuthorizationDecisionPacketOptions {
    pub authorization_decision: Value,
    pub authorization_request: Value,
    pub reviewer: Option<String>,
    pub commit: Option<String>,
    pub forum_post_id: Option<String>,
    pub memory_key: Option<String>,
}

#[derive(Debug, Clone)]
pub struct BioCortexRetrievalOptInPostImplementationReviewGateOptions {
    pub authorization_decision_packet: Value,
    pub opt_in_plan: Value,
    pub reviewer: Option<String>,
    pub commit: Option<String>,
    pub forum_post_id: Option<String>,
    pub memory_key: Option<String>,
}

#[derive(Debug, Clone)]
pub struct BioCortexRetrievalOptInRuntimeInfluenceReviewRequestOptions {
    pub post_implementation_review_gate: Value,
    pub redacted_order_artifact: Value,
    pub redacted_evidence_aggregate: Option<Value>,
    pub evidence_summary: Option<Value>,
    pub capability_ledger_report_packet: Option<Value>,
    pub reviewer: Option<String>,
    pub commit: Option<String>,
    pub forum_post_id: Option<String>,
    pub memory_key: Option<String>,
}

#[derive(Debug, Clone)]
pub struct BioCortexRetrievalOptInRuntimeInfluenceDecisionPacketOptions {
    pub runtime_influence_review_request: Value,
    pub runtime_influence_decision: Value,
    pub reviewer: Option<String>,
    pub commit: Option<String>,
    pub forum_post_id: Option<String>,
    pub memory_key: Option<String>,
}

#[derive(Debug, Clone)]
pub struct BioCortexRetrievalOptInStoreTrialOptions {
    pub runtime_influence_decision_packet: Value,
    pub query: String,
    pub tags_any: Vec<String>,
    pub limit: u32,
    pub mode: String,
    pub per_call_opt_in: bool,
    pub checkout: Option<PathBuf>,
    pub timeout_ms: u64,
    pub coverage_threshold: f64,
    pub blend_alpha: f32,
    pub attempt_id: Option<String>,
    pub commit: Option<String>,
}

#[derive(Debug, Clone)]
pub struct BioCortexRetrievalOptInGatedStoreTrialOptions {
    pub runtime_transition_gate: Value,
    pub runtime_influence_decision_packet: Value,
    pub query: String,
    pub tags_any: Vec<String>,
    pub limit: u32,
    pub mode: String,
    pub per_call_opt_in: bool,
    pub checkout: Option<PathBuf>,
    pub timeout_ms: u64,
    pub coverage_threshold: f64,
    pub blend_alpha: f32,
    pub attempt_id: Option<String>,
    pub commit: Option<String>,
}

#[derive(Debug, Clone)]
pub struct BioCortexRetrievalOptInBatchQueryCase {
    pub query: String,
    pub class_label: Option<String>,
}

#[derive(Debug, Clone)]
pub struct BioCortexRetrievalOptInBatchDiagnosticsOptions {
    pub runtime_influence_decision_packet: Value,
    pub queries: Vec<BioCortexRetrievalOptInBatchQueryCase>,
    pub tags_any: Vec<String>,
    pub limit: u32,
    pub mode: String,
    pub per_call_opt_in: bool,
    pub checkout: Option<PathBuf>,
    pub timeout_ms: u64,
    pub coverage_threshold: f64,
    pub blend_alpha: f32,
    pub attempt_id: Option<String>,
    pub commit: Option<String>,
}

#[derive(Debug, Clone)]
pub struct BioCortexRetrievalOptInGatedBatchDiagnosticsOptions {
    pub runtime_transition_gate: Value,
    pub runtime_influence_decision_packet: Value,
    pub queries: Vec<BioCortexRetrievalOptInBatchQueryCase>,
    pub tags_any: Vec<String>,
    pub limit: u32,
    pub mode: String,
    pub per_call_opt_in: bool,
    pub checkout: Option<PathBuf>,
    pub timeout_ms: u64,
    pub coverage_threshold: f64,
    pub blend_alpha: f32,
    pub attempt_id: Option<String>,
    pub commit: Option<String>,
}

#[derive(Debug, Clone)]
pub struct BioCortexRetrievalOptInRuntimeReadinessPacketOptions {
    pub runtime_influence_decision_packet: Value,
    pub store_trial: Value,
    pub batch_diagnostics: Value,
    pub reviewer: Option<String>,
    pub commit: Option<String>,
    pub forum_post_id: Option<String>,
    pub memory_key: Option<String>,
}

#[derive(Debug, Clone)]
pub struct BioCortexRetrievalOptInRuntimeTransitionGateOptions {
    pub runtime_readiness_packet: Value,
    pub mode: String,
    pub per_call_opt_in: bool,
    pub operator_disabled: bool,
    pub reviewer: Option<String>,
    pub commit: Option<String>,
    pub forum_post_id: Option<String>,
    pub memory_key: Option<String>,
}

#[derive(Debug, Clone)]
pub struct BioCortexRetrievalDownstreamAioRuntimeEvidenceHandoffOptions {
    pub checkpoint_selection: Value,
    pub post_semantic_diverse_review: Value,
    pub controlled_trial_readiness: Option<Value>,
    pub reviewer: Option<String>,
    pub commit: Option<String>,
    pub forum_post_id: Option<String>,
    pub memory_key: Option<String>,
}

impl Default for BioCortexShadowOptions {
    fn default() -> Self {
        Self {
            checkout: None,
            benchmark: "scaled_morphology".to_string(),
            timeout_ms: DEFAULT_TIMEOUT_MS,
            include_raw: false,
            fixture_projection: None,
        }
    }
}

impl Default for BioCortexReplayComparisonOptions {
    fn default() -> Self {
        Self {
            checkout: None,
            benchmark: "ab_fixture_projection".to_string(),
            timeout_ms: DEFAULT_TIMEOUT_MS,
            include_raw: false,
            include_events: false,
        }
    }
}

impl Default for BioCortexRetrievalShadowOptions {
    fn default() -> Self {
        Self {
            query: String::new(),
            candidates: Vec::new(),
            expected_key: None,
            checkout: None,
            timeout_ms: DEFAULT_TIMEOUT_MS,
            include_raw: false,
        }
    }
}

impl Default for BioCortexRetrievalOptInAuditOptions {
    fn default() -> Self {
        Self {
            mode: "fts".to_string(),
            per_call_opt_in: false,
            query: None,
            baseline_keys: Vec::new(),
            side_signal_status: None,
            fallback_reason: None,
            latency_ms: None,
            runtime_readiness_packet: None,
            runtime_transition_gate: None,
            gated_store_trial: None,
            gated_batch_diagnostics: None,
        }
    }
}

impl Default for BioCortexRetrievalOptInDryRunOptions {
    fn default() -> Self {
        Self {
            mode: "fts".to_string(),
            per_call_opt_in: false,
            query: None,
            baseline_keys: Vec::new(),
            baseline_completed: true,
            timeout_ms: DEFAULT_TIMEOUT_MS,
            coverage_threshold: 0.8,
        }
    }
}

impl Default for BioCortexRetrievalOptInReviewPacketOptions {
    fn default() -> Self {
        Self {
            dry_run_plan: Value::Null,
            reviewer: None,
            commit: None,
            forum_post_id: None,
            memory_key: None,
        }
    }
}

impl Default for BioCortexRetrievalOptInExecutionPacketOptions {
    fn default() -> Self {
        Self {
            review_packet: Value::Null,
            per_call_opt_in: false,
            attempt_id: None,
            commit: None,
        }
    }
}

impl Default for BioCortexRetrievalOptInRuntimeTrialOptions {
    fn default() -> Self {
        Self {
            execution_packet: Value::Null,
            query: String::new(),
            candidates: Vec::new(),
            expected_key: None,
            checkout: None,
            timeout_ms: DEFAULT_TIMEOUT_MS,
            coverage_threshold: 0.8,
            attempt_id: None,
            commit: None,
        }
    }
}

impl Default for BioCortexRetrievalOptInRuntimeTrialReviewPacketOptions {
    fn default() -> Self {
        Self {
            runtime_trial: Value::Null,
            reviewer: None,
            commit: None,
            forum_post_id: None,
            memory_key: None,
        }
    }
}

impl Default for BioCortexRetrievalOptInOrderDiffPacketOptions {
    fn default() -> Self {
        Self {
            source_packet: Value::Null,
            reviewer: None,
            commit: None,
            forum_post_id: None,
            memory_key: None,
        }
    }
}

impl Default for BioCortexRetrievalOptInRedactedOrderArtifactOptions {
    fn default() -> Self {
        Self {
            source_packet: Value::Null,
            reviewer: None,
            commit: None,
            forum_post_id: None,
            memory_key: None,
        }
    }
}

impl Default for BioCortexRetrievalOptInStoreTrialOptions {
    fn default() -> Self {
        Self {
            runtime_influence_decision_packet: Value::Null,
            query: String::new(),
            tags_any: Vec::new(),
            limit: 10,
            mode: "fts".to_string(),
            per_call_opt_in: false,
            checkout: None,
            timeout_ms: DEFAULT_TIMEOUT_MS,
            coverage_threshold: 0.8,
            blend_alpha: CANDIDATE_STRONG_RETRIEVAL_ALPHA,
            attempt_id: None,
            commit: None,
        }
    }
}

impl Default for BioCortexRetrievalOptInGatedStoreTrialOptions {
    fn default() -> Self {
        Self {
            runtime_transition_gate: Value::Null,
            runtime_influence_decision_packet: Value::Null,
            query: String::new(),
            tags_any: Vec::new(),
            limit: 10,
            mode: "fts".to_string(),
            per_call_opt_in: false,
            checkout: None,
            timeout_ms: DEFAULT_TIMEOUT_MS,
            coverage_threshold: 0.8,
            blend_alpha: CANDIDATE_STRONG_RETRIEVAL_ALPHA,
            attempt_id: None,
            commit: None,
        }
    }
}

impl Default for BioCortexRetrievalOptInGatedBatchDiagnosticsOptions {
    fn default() -> Self {
        Self {
            runtime_transition_gate: Value::Null,
            runtime_influence_decision_packet: Value::Null,
            queries: Vec::new(),
            tags_any: Vec::new(),
            limit: 10,
            mode: "fts".to_string(),
            per_call_opt_in: false,
            checkout: None,
            timeout_ms: DEFAULT_TIMEOUT_MS,
            coverage_threshold: 0.8,
            blend_alpha: CANDIDATE_STRONG_RETRIEVAL_ALPHA,
            attempt_id: None,
            commit: None,
        }
    }
}

#[derive(Debug, Clone)]
struct RetrievalAlphaConfig {
    policy: String,
    alpha: f32,
    explicit_alpha: bool,
}

#[derive(Debug, Deserialize)]
/// One row emitted by the local BioCortex retrieval side-signal diagnostic.
///
/// This type is public so examples can inspect score/rank behavior without
/// adding a new MCP tool surface.
pub struct RetrievalSideSignalRow {
    pub query_id: String,
    pub candidate_key: String,
    pub score: f32,
    #[serde(default)]
    pub evidence: Option<String>,
}

#[derive(Debug, Clone)]
struct RetrievalBaselineScore {
    key: String,
    content: String,
    score: f32,
    rank: usize,
}

#[derive(Debug)]
/// Raw output from a local BioCortex retrieval side-signal run.
///
/// Intended for diagnostics and examples; runtime MCP callers still go through
/// the guarded opt-in retrieval path.
pub struct RetrievalSideSignalRun {
    pub rows: Vec<RetrievalSideSignalRow>,
    pub payload: Value,
    pub raw: Value,
}

#[derive(Debug, Clone, Copy)]
struct BenchmarkSpec {
    benchmark: &'static str,
    example: &'static str,
    description: &'static str,
    requires_fixture_projection: bool,
}

const BENCHMARKS: &[BenchmarkSpec] = &[
    BenchmarkSpec {
        benchmark: "scaled_morphology",
        example: "scaled_morphology_shadow_adapter",
        description: "S9g scaled morphology read-only adapter",
        requires_fixture_projection: false,
    },
    BenchmarkSpec {
        benchmark: "temporal_credit",
        example: "temporal_credit_shadow_adapter",
        description: "S10f temporal credit read-only adapter",
        requires_fixture_projection: false,
    },
    BenchmarkSpec {
        benchmark: "minimal_morphology",
        example: "morphology_shadow_adapter",
        description: "S7b minimal morphology read-only adapter",
        requires_fixture_projection: false,
    },
    BenchmarkSpec {
        benchmark: "ab_fixture_projection",
        example: "ab_fixture_projection_shadow_adapter",
        description: "Agent-Bridge fixture projection read-only adapter",
        requires_fixture_projection: true,
    },
];

pub fn supported_benchmarks() -> Vec<&'static str> {
    BENCHMARKS.iter().map(|spec| spec.benchmark).collect()
}

pub async fn biocortex_shadow_digest(opts: BioCortexShadowOptions) -> Value {
    let requested = opts.benchmark.trim();
    let spec = match benchmark_spec(requested) {
        Some(spec) => spec,
        None => {
            return json!({
                "schema": BIOCORTEX_SHADOW_SCHEMA,
                "generated_at": now_secs(),
                "read_only": true,
                "status": "invalid_benchmark",
                "requested_benchmark": requested,
                "supported_benchmarks": supported_benchmarks(),
                "boundary": boundary_payload(false, false),
            });
        }
    };

    if spec.requires_fixture_projection && opts.fixture_projection.is_none() {
        return json!({
            "schema": BIOCORTEX_SHADOW_SCHEMA,
            "generated_at": now_secs(),
            "read_only": true,
            "status": "fixture_required",
            "benchmark": spec.benchmark,
            "example": spec.example,
            "reason": "benchmark requires an AB fixture projection input",
            "boundary": boundary_payload(false, false),
        });
    }

    let candidates = checkout_candidates(opts.checkout.as_deref());
    let checkout = match resolve_checkout(&candidates) {
        Some(path) => path,
        None => {
            return json!({
                "schema": BIOCORTEX_SHADOW_SCHEMA,
                "generated_at": now_secs(),
                "read_only": true,
                "status": "unavailable",
                "benchmark": spec.benchmark,
                "example": spec.example,
                "reason": "no local biocortex-rs checkout found",
                "checkout_env": BIOCORTEX_CHECKOUT_ENV,
                "candidates": candidates
                    .iter()
                    .map(|path| display_path(path.as_path()))
                    .collect::<Vec<_>>(),
                "boundary": boundary_payload(false, false),
            });
        }
    };

    let manifest = checkout.join("Cargo.toml");
    let timeout_ms = opts.timeout_ms.clamp(1_000, 600_000);
    let mut temp_projection_path = None;
    let mut cmd = TokioCommand::new("cargo");
    cmd.arg("run")
        .arg("--offline")
        .arg("--quiet")
        .arg("--manifest-path")
        .arg(&manifest)
        .arg("--example")
        .arg(spec.example)
        .kill_on_drop(true);

    if let Some(projection) = opts.fixture_projection.as_ref() {
        let path = std::env::temp_dir().join(format!(
            "ab-biocortex-fixture-projection-{}-{}.json",
            std::process::id(),
            now_nanos()
        ));
        match serde_json::to_vec_pretty(projection)
            .map_err(|e| e.to_string())
            .and_then(|bytes| std::fs::write(&path, bytes).map_err(|e| e.to_string()))
        {
            Ok(()) => {
                cmd.arg(&path);
                temp_projection_path = Some(path);
            }
            Err(err) => {
                return json!({
                    "schema": BIOCORTEX_SHADOW_SCHEMA,
                    "generated_at": now_secs(),
                    "read_only": true,
                    "status": "fixture_write_error",
                    "benchmark": spec.benchmark,
                    "example": spec.example,
                    "checkout_path": display_path(&checkout),
                    "manifest_path": display_path(&manifest),
                    "error": err,
                    "boundary": boundary_payload(false, true),
                });
            }
        }
    }

    let output_result = tokio::time::timeout(Duration::from_millis(timeout_ms), cmd.output()).await;
    if let Some(path) = temp_projection_path.as_ref() {
        let _ = std::fs::remove_file(path);
    }

    let output = match output_result {
        Ok(Ok(output)) => output,
        Ok(Err(err)) => {
            return json!({
                "schema": BIOCORTEX_SHADOW_SCHEMA,
                "generated_at": now_secs(),
                "read_only": true,
                "status": "spawn_error",
                "benchmark": spec.benchmark,
                "example": spec.example,
                "checkout_path": display_path(&checkout),
                "manifest_path": display_path(&manifest),
                "error": err.to_string(),
                "boundary": boundary_payload(true, spec.requires_fixture_projection),
            });
        }
        Err(_) => {
            return json!({
                "schema": BIOCORTEX_SHADOW_SCHEMA,
                "generated_at": now_secs(),
                "read_only": true,
                "status": "timeout",
                "benchmark": spec.benchmark,
                "example": spec.example,
                "checkout_path": display_path(&checkout),
                "manifest_path": display_path(&manifest),
                "timeout_ms": timeout_ms,
                "boundary": boundary_payload(true, spec.requires_fixture_projection),
            });
        }
    };

    let stdout = String::from_utf8_lossy(&output.stdout).to_string();
    let stderr = String::from_utf8_lossy(&output.stderr).to_string();
    let report = parse_key_value_report(&stdout);
    let summary = summarize_report(&report);
    let status = if output.status.success() {
        "ok"
    } else {
        "command_failed"
    };
    let mut payload = json!({
        "schema": BIOCORTEX_SHADOW_SCHEMA,
        "generated_at": now_secs(),
        "read_only": true,
        "status": status,
        "benchmark": spec.benchmark,
        "example": spec.example,
        "description": spec.description,
        "checkout_path": display_path(&checkout),
        "manifest_path": display_path(&manifest),
        "timeout_ms": timeout_ms,
        "exit_code": output.status.code(),
        "report": report,
        "summary": summary,
        "fixture_projection_input": fixture_projection_summary(opts.fixture_projection.as_ref()),
        "boundary": boundary_payload(true, spec.requires_fixture_projection),
    });

    if opts.include_raw {
        payload["raw"] = json!({
            "stdout": stdout,
            "stderr": stderr,
        });
    } else if !stderr.trim().is_empty() {
        payload["stderr_preview"] = json!(stderr.chars().take(1200).collect::<String>());
    }

    payload
}

pub async fn biocortex_replay_comparison(
    fixture: &ShadowCortexReplayFixture,
    opts: BioCortexReplayComparisonOptions,
) -> Value {
    // The external BioCortex adapter APPLIES the plan's pulse list to demonstrate
    // (`adapter_demonstrated`/`event_pulses_applied`). The compact
    // `event_pulse_preview` (first 12 of N) STARVES it into a false
    // `command_failed` → `biocortex_unavailable` verdict — a healthy integration
    // misreported as broken (the first-run footgun). So always feed the adapter
    // the FULL plan; the echoed `ab_fixture_projection` still honors the caller's
    // `include_events` for response token budget. (`include_events` conflated two
    // concerns: response verbosity vs adapter-input completeness — split here.)
    let adapter_projection = biocortex_replay_fixture_projection(fixture, true);
    let echo_projection = if opts.include_events {
        adapter_projection.clone()
    } else {
        biocortex_replay_fixture_projection(fixture, false)
    };
    let digest = biocortex_shadow_digest(BioCortexShadowOptions {
        checkout: opts.checkout,
        benchmark: opts.benchmark,
        timeout_ms: opts.timeout_ms,
        include_raw: opts.include_raw,
        fixture_projection: Some(adapter_projection),
    })
    .await;
    let comparison = replay_comparison_summary(&echo_projection, &digest);

    json!({
        "schema": BIOCORTEX_REPLAY_COMPARISON_SCHEMA,
        "generated_at": now_secs(),
        "read_only": true,
        "status": comparison.get("status").cloned().unwrap_or_else(|| json!("unknown")),
        "ab_fixture_projection": echo_projection,
        "biocortex_shadow_digest": digest,
        "comparison": comparison,
        "boundary": replay_boundary_payload(),
    })
}

pub async fn biocortex_retrieval_shadow_report(opts: BioCortexRetrievalShadowOptions) -> Value {
    let gates = retrieval_gate_state();
    if !cfg!(feature = "biocortex-retrieval-shadow") {
        return retrieval_status_payload(
            "compile_feature_disabled",
            "Cargo feature biocortex-retrieval-shadow is not enabled",
            gates,
        );
    }
    if env_truthy(BIOCORTEX_RETRIEVAL_DISABLE_ENV) {
        return retrieval_status_payload(
            "operator_disabled",
            "AB_BIOCORTEX_RETRIEVAL_DISABLE=1 forces baseline-only behavior",
            gates,
        );
    }
    if !env_truthy(BIOCORTEX_RETRIEVAL_SHADOW_ENABLE_ENV) {
        return retrieval_status_payload(
            "runtime_disabled",
            "Set AB_BIOCORTEX_RETRIEVAL_SHADOW=1 to run the review-only shadow surface",
            gates,
        );
    }

    let query = opts.query.trim().to_string();
    if query.is_empty() {
        return retrieval_status_payload("invalid_input", "query is empty", gates);
    }
    let candidates: Vec<_> = opts
        .candidates
        .into_iter()
        .filter(|candidate| !candidate.key.trim().is_empty())
        .collect();
    if candidates.is_empty() {
        return retrieval_status_payload("invalid_input", "candidates are empty", gates);
    }

    let alpha = retrieval_alpha_config();
    let baseline = retrieval_baseline_scores(&query, &candidates);
    let started = Instant::now();
    let side = run_retrieval_side_signal(
        &query,
        &candidates,
        opts.expected_key.as_deref(),
        opts.checkout.as_deref(),
        opts.timeout_ms,
    )
    .await;
    let latency_ms = started.elapsed().as_secs_f64() * 1000.0;

    let (side_rows, side_payload, raw_payload) = match side {
        Ok(run) => (run.rows, run.payload, run.raw),
        Err(payload) => {
            return retrieval_fail_open_report(
                "side_signal_unavailable",
                query,
                candidates,
                opts.expected_key,
                baseline,
                alpha,
                gates,
                latency_ms,
                payload,
                opts.include_raw,
            );
        }
    };

    let mut side_by_key = BTreeMap::new();
    let mut evidence_by_key = BTreeMap::new();
    for row in side_rows {
        if row.query_id == "q_runtime_shadow" {
            side_by_key.insert(row.candidate_key.clone(), row.score);
            if let Some(evidence) = row.evidence {
                evidence_by_key.insert(row.candidate_key, evidence);
            }
        }
    }
    let report = retrieval_rank_report(
        "ok",
        query,
        candidates,
        opts.expected_key,
        baseline,
        &side_by_key,
        &evidence_by_key,
        alpha,
        gates,
        latency_ms,
        Some(side_payload),
        opts.include_raw.then_some(raw_payload),
    );
    report
}

pub fn biocortex_retrieval_runtime_approval_packet_preview(
    opts: BioCortexRetrievalApprovalPacketOptions,
) -> Value {
    let evidence = json!({
        "target_host": required_or_value(opts.target_host),
        "branch": required_or_value(opts.branch),
        "commit": required_or_value(opts.commit),
        "reviewer": required_or_value(opts.reviewer),
        "verification_bundle": {
            "command": "AB_BIOCORTEX_RS=/Data/CascadeProjects/biocortex-rs scripts/verify-biocortex-retrieval-shadow.sh",
            "status": required_or_value(opts.verification_status),
            "captured_at": required_or_value(opts.verification_captured_at),
        },
        "gate_summaries": [
            {
                "corpus": "current",
                "policy": "candidate-strong",
                "side_signal_coverage_min": 0.8,
                "regressions_required": 0,
                "mrr_delta_required": "> 0",
                "status": required_or_value(opts.current_gate_status),
            },
            {
                "corpus": "hard_holdout",
                "policy": "candidate-strong",
                "side_signal_coverage_min": 0.8,
                "regressions_required": 0,
                "mrr_delta_required": "> 0",
                "status": required_or_value(opts.hard_holdout_gate_status),
            }
        ],
        "live_mcp_default_disabled": {
            "status": "<required: runtime_disabled>",
            "runtime_adapter_approved": false,
            "default_search_order_changed": false,
        },
        "operator_kill_switch": {
            "env": BIOCORTEX_RETRIEVAL_DISABLE_ENV,
            "expected_status": "operator_disabled",
            "must_win_over_enable": true,
        },
        "latency": {
            "side_signal_p95_ms_for_5_candidates": required_or_value(opts.side_signal_p95_ms_for_5_candidates),
            "default_memory_search_added_latency_ms": required_or_value(opts.default_memory_search_added_latency_ms),
        },
        "ordering_change_design": {
            "exact_call_site": required_or_value(opts.exact_call_site),
            "default_search_order_change_allowed": false,
            "fail_open_behavior": required_or_value(opts.fail_open_behavior),
            "bio_cortex_absent_behavior": "<required>",
            "bio_cortex_slow_behavior": "<required>",
            "bio_cortex_error_behavior": "<required>",
        },
        "rollback": {
            "operator_kill_switch": format!("{BIOCORTEX_RETRIEVAL_DISABLE_ENV}=1"),
            "rollback_command": required_or_value(opts.rollback_command),
        },
        "audit_links": {
            "forum_decision_post_id": required_or_value(opts.forum_decision_post_id),
            "memory_key": required_or_value(opts.memory_key),
        },
    });
    let agent_technical_attestation = json!({
        "required": true,
        "attestor": required_or_value(opts.agent_attestor),
        "decision": required_or_value(opts.agent_attestation_decision),
        "summary": required_or_value(opts.agent_attestation_summary),
        "can_authorize_runtime_influence": false,
        "scope": "technical_evidence_and_behavioral_risk_only",
    });
    let human_authorization = json!({
        "required": true,
        "status": "not_authorized",
        "scope": required_or_value(opts.human_authorization_scope),
        "can_be_replaced_by_agent_attestation": false,
        "owner_decides_trust_boundary": true,
    });
    let missing_evidence = missing_required_paths(&evidence);
    let missing_attestation = missing_required_paths(&agent_technical_attestation);
    let missing_authorization = missing_required_paths(&human_authorization);

    json!({
        "schema": BIOCORTEX_RETRIEVAL_RUNTIME_APPROVAL_PACKET_SCHEMA,
        "generated_at": now_secs(),
        "purpose": "Preview packet for future human review; this is not approval state.",
        "approval_state": "not_approved",
        "default_decision": "keep_shadow_only",
        "runtime_adapter_approved": false,
        "writes_approval": false,
        "approval_writes_allowed": false,
        "default_search_order_change_allowed": false,
        "requires_separate_human_approval": true,
        "read_only_shadow_required_until_approved": true,
        "kill_switch_required": true,
        "rollback_required": true,
        "read_only": true,
        "template": {
            "doc": "docs/design/BIOCORTEX_RETRIEVAL_RUNTIME_APPROVAL_PACKET_TEMPLATE_2026_06_11.md",
            "fixture": "docs/design/fixtures/biocortex-retrieval-runtime-approval-packet-template.json",
            "fixture_schema": "agent_bridge.biocortex_retrieval.runtime_approval_packet_template.v0",
        },
        "approval_model": {
            "agent_technical_attestation_required": true,
            "human_authorization_required": true,
            "agent_attestation_can_replace_human_authorization": false,
            "human_reviews_scope_not_raw_memory_contents": true,
        },
        "gates": retrieval_gate_state(),
        "evidence": evidence,
        "agent_technical_attestation": agent_technical_attestation,
        "human_authorization": human_authorization,
        "missing_evidence": missing_evidence,
        "missing_attestation": missing_attestation,
        "missing_authorization": missing_authorization,
        "ready_for_human_approval_review": false,
        "review_rule": "Approval requires a separate human decision explicitly allowing default retrieval influence and naming the reviewed implementation commit.",
    })
}

pub fn biocortex_retrieval_opt_in_gate_report(per_call_opt_in: bool) -> Value {
    let compile_feature_enabled = cfg!(feature = "biocortex-retrieval-opt-in");
    let runtime_enabled = env_truthy(BIOCORTEX_RETRIEVAL_OPT_IN_ENABLE_ENV);
    let operator_disabled = env_truthy(BIOCORTEX_RETRIEVAL_DISABLE_ENV);
    let ready_for_explicit_opt_in_experiment =
        compile_feature_enabled && runtime_enabled && per_call_opt_in && !operator_disabled;
    let status = if !compile_feature_enabled {
        "compile_feature_disabled"
    } else if operator_disabled {
        "operator_disabled"
    } else if !runtime_enabled {
        "runtime_disabled"
    } else if !per_call_opt_in {
        "per_call_opt_in_missing"
    } else {
        "ready_for_explicit_opt_in_experiment"
    };

    json!({
        "schema": BIOCORTEX_RETRIEVAL_OPT_IN_GATE_SCHEMA,
        "generated_at": now_secs(),
        "read_only": true,
        "status": status,
        "implementation_stage": "gate_skeleton_only",
        "feature": "biocortex-retrieval-opt-in",
        "compile_feature_enabled": compile_feature_enabled,
        "runtime_enable_env": BIOCORTEX_RETRIEVAL_OPT_IN_ENABLE_ENV,
        "runtime_enabled": runtime_enabled,
        "per_call_opt_in_required": true,
        "per_call_opt_in": per_call_opt_in,
        "operator_disable_env": BIOCORTEX_RETRIEVAL_DISABLE_ENV,
        "operator_disabled": operator_disabled,
        "ready_for_explicit_opt_in_experiment": ready_for_explicit_opt_in_experiment,
        "runtime_adapter_approved": false,
        "default_search_order_change_allowed": false,
        "default_calls_unchanged": true,
        "may_change_search_order_now": false,
        "ordering_behavior_connected": false,
        "effective_behavior": "baseline_only_until_ordering_implementation",
        "authorized_scope": "opt_in_experiment",
        "boundary": retrieval_boundary_payload(),
    })
}

fn biocortex_retrieval_controlled_trial_readiness_summary(
    mode: &str,
    per_call_opt_in: bool,
    runtime_readiness_packet: Option<&Value>,
    runtime_transition_gate: Option<&Value>,
    gated_store_trial: Option<&Value>,
    gated_batch_diagnostics: Option<&Value>,
) -> Value {
    let status_request_ok = mode == "fts" && per_call_opt_in;
    let readiness_provided = runtime_readiness_packet.is_some();
    let readiness_schema_ok = runtime_readiness_packet
        .map(|packet| {
            value_str_eq(
                packet.get("schema"),
                BIOCORTEX_RETRIEVAL_OPT_IN_RUNTIME_READINESS_PACKET_SCHEMA,
            ) && value_bool_is(packet.get("read_only"), true)
                && value_bool_is(packet.get("runtime_readiness_packet"), true)
                && value_str_eq(packet.get("status"), "completed")
        })
        .unwrap_or(false);
    let readiness_boundary_ready = runtime_readiness_packet
        .map(|packet| {
            value_bool_is(
                packet.pointer("/boundary_check/runtime_readiness_ready"),
                true,
            ) && json_string_array(packet.pointer("/boundary_check/blockers")).is_empty()
        })
        .unwrap_or(false);
    let readiness_control_plane_ready = runtime_readiness_packet
        .map(|packet| {
            value_bool_is(packet.pointer("/readiness/control_plane_ready"), true)
                && value_bool_is(
                    packet.pointer("/readiness/may_accept_controlled_explicit_opt_in_fts_calls"),
                    true,
                )
                && value_bool_is(
                    packet.pointer("/readiness/may_change_default_memory_search_order"),
                    false,
                )
                && value_bool_is(packet.pointer("/readiness/default_influence_ready"), false)
        })
        .unwrap_or(false);
    let readiness_side_effects_absent = runtime_readiness_packet
        .map(|packet| {
            value_bool_is(packet.get("calls_memory_search"), false)
                && value_bool_is(packet.get("runs_biocortex"), false)
                && value_bool_is(packet.get("registers_embedding_backend"), false)
                && value_bool_is(packet.get("changes_memory_search_order"), false)
                && value_bool_is(packet.get("default_search_order_change_allowed"), false)
                && value_bool_is(packet.get("default_calls_unchanged"), true)
        })
        .unwrap_or(false);
    let readiness_post_runtime_backed = runtime_readiness_packet
        .map(|packet| {
            value_bool_is(
                packet.pointer(
                    "/decision_summary/post_runtime_evidence_summary_backed_review_request",
                ),
                true,
            )
        })
        .unwrap_or(false);
    let readiness_post_runtime_ready = runtime_readiness_packet
        .map(|packet| {
            value_bool_is(
                packet.pointer("/decision_summary/post_runtime_evidence_summary_ready"),
                true,
            ) && value_bool_is(
                packet.pointer(
                    "/decision_summary/legacy_decision_packet_without_post_runtime_evidence_summary_allowed",
                ),
                false,
            ) && value_bool_is(
                packet.pointer("/decision_summary/post_runtime_evidence_summary_safe_for_decision"),
                true,
            ) && value_bool_is(
                packet.pointer(
                    "/decision_summary/post_runtime_readiness_gated_batch_evidence_ready",
                ),
                true,
            ) && value_bool_is(
                packet.pointer("/decision_summary/post_runtime_batch_transition_gated"),
                true,
            ) && value_str_eq(
                packet.pointer("/decision_summary/post_runtime_batch_evidence_source"),
                "runtime_transition_gated_batch_diagnostics",
            ) && value_str_eq(
                packet.pointer("/decision_summary/post_runtime_evidence_summary_state"),
                "post_runtime_evidence_ready",
            ) && value_bool_is(
                packet.pointer("/store_trial_summary/post_runtime_evidence_preflight_ok"),
                true,
            ) && value_bool_is(
                packet.pointer("/batch_summary/post_runtime_evidence_preflight_ok"),
                true,
            )
        })
        .unwrap_or(false);
    let readiness_ready = readiness_schema_ok
        && readiness_boundary_ready
        && readiness_control_plane_ready
        && readiness_side_effects_absent
        && (!readiness_post_runtime_backed || readiness_post_runtime_ready);

    let transition_provided = runtime_transition_gate.is_some();
    let transition_schema_ok = runtime_transition_gate
        .map(|gate| {
            value_str_eq(
                gate.get("schema"),
                BIOCORTEX_RETRIEVAL_OPT_IN_RUNTIME_TRANSITION_GATE_SCHEMA,
            ) && value_bool_is(gate.get("read_only"), true)
                && value_bool_is(gate.get("runtime_transition_gate"), true)
                && value_str_eq(gate.get("status"), "transition_allowed")
        })
        .unwrap_or(false);
    let transition_request_ok = runtime_transition_gate
        .map(|gate| {
            value_str_eq(gate.pointer("/requested_transition/mode"), "fts")
                && value_bool_is(gate.pointer("/requested_transition/mode_authorized"), true)
                && value_bool_is(gate.pointer("/requested_transition/per_call_opt_in"), true)
                && value_bool_is(
                    gate.pointer("/requested_transition/operator_disabled"),
                    false,
                )
                && value_bool_is(
                    gate.pointer("/requested_transition/default_search_order_change_requested"),
                    false,
                )
        })
        .unwrap_or(false);
    let transition_allowed = runtime_transition_gate
        .map(|gate| {
            value_bool_is(gate.pointer("/transition/transition_allowed"), true)
                && value_bool_is(
                    gate.pointer("/transition/may_call_controlled_store_trial"),
                    true,
                )
                && value_bool_is(
                    gate.pointer("/transition/may_run_runtime_adapter_for_explicit_opt_in_fts"),
                    true,
                )
                && value_bool_is(
                    gate.pointer(
                        "/transition/may_connect_ordering_behavior_for_explicit_opt_in_fts",
                    ),
                    true,
                )
                && value_bool_is(
                    gate.pointer("/transition/may_change_default_memory_search_order"),
                    false,
                )
                && value_bool_is(gate.pointer("/transition/default_influence_ready"), false)
                && value_bool_is(
                    gate.pointer("/boundary_check/runtime_transition_allowed"),
                    true,
                )
                && json_string_array(gate.pointer("/boundary_check/blockers")).is_empty()
        })
        .unwrap_or(false);
    let transition_side_effects_absent = runtime_transition_gate
        .map(|gate| {
            value_bool_is(gate.get("calls_memory_search"), false)
                && value_bool_is(gate.get("runs_biocortex"), false)
                && value_bool_is(gate.get("registers_embedding_backend"), false)
                && value_bool_is(gate.get("changes_memory_search_order"), false)
                && value_bool_is(gate.get("default_search_order_change_allowed"), false)
                && value_bool_is(gate.get("default_calls_unchanged"), true)
        })
        .unwrap_or(false);
    let transition_post_runtime_backed = runtime_transition_gate
        .map(|gate| {
            value_bool_is(
                gate.pointer("/readiness_summary/post_runtime_evidence_summary_backed"),
                true,
            )
        })
        .unwrap_or(false);
    let transition_post_runtime_ready = runtime_transition_gate
        .map(|gate| {
            value_bool_is(
                gate.pointer("/readiness_summary/post_runtime_evidence_summary_ready"),
                true,
            ) && value_bool_is(
                gate.pointer(
                    "/readiness_summary/legacy_decision_packet_without_post_runtime_evidence_summary_allowed",
                ),
                false,
            ) && value_bool_is(
                gate.pointer("/readiness_summary/post_runtime_readiness_gated_batch_evidence_ready"),
                true,
            ) && value_bool_is(
                gate.pointer("/readiness_summary/post_runtime_batch_transition_gated"),
                true,
            ) && value_str_eq(
                gate.pointer("/readiness_summary/post_runtime_evidence_summary_state"),
                "post_runtime_evidence_ready",
            ) && value_str_eq(
                gate.pointer("/readiness_summary/post_runtime_batch_evidence_source"),
                "runtime_transition_gated_batch_diagnostics",
            ) && value_bool_is(
                gate.pointer("/readiness_summary/store_post_runtime_evidence_preflight_ok"),
                true,
            ) && value_bool_is(
                gate.pointer("/readiness_summary/batch_post_runtime_evidence_preflight_ok"),
                true,
            )
        })
        .unwrap_or(false);
    let transition_ready = transition_schema_ok
        && transition_request_ok
        && transition_allowed
        && transition_side_effects_absent
        && (!transition_post_runtime_backed || transition_post_runtime_ready);

    let gated_store_provided = gated_store_trial.is_some();
    let gated_store_schema_ok = gated_store_trial
        .map(|trial| {
            value_str_eq(
                trial.get("schema"),
                BIOCORTEX_RETRIEVAL_OPT_IN_GATED_STORE_TRIAL_SCHEMA,
            ) && value_bool_is(trial.get("gated_store_trial"), true)
        })
        .unwrap_or(false);
    let gated_store_consumed = gated_store_trial
        .map(|trial| {
            value_str_eq(trial.get("status"), "transition_gate_consumed")
                && value_bool_is(
                    trial.pointer("/runtime_transition_preflight/transition_gate_allowed"),
                    true,
                )
                && json_string_array(trial.pointer("/runtime_transition_preflight/blockers"))
                    .is_empty()
                && value_bool_is(trial.get("store_trial_called"), true)
                && value_bool_is(trial.get("calls_memory_search"), true)
                && value_bool_is(trial.get("changes_memory_search_order"), false)
                && value_bool_is(trial.get("default_search_order_change_allowed"), false)
                && value_bool_is(trial.get("default_calls_unchanged"), true)
        })
        .unwrap_or(false);
    let gated_store_post_runtime_ready = gated_store_trial
        .map(|trial| {
            value_bool_is(
                trial.pointer(
                    "/runtime_transition_preflight/gate_post_runtime_evidence_summary_backed",
                ),
                true,
            ) && value_bool_is(
                trial.pointer(
                    "/runtime_transition_preflight/gate_post_runtime_evidence_summary_ready",
                ),
                true,
            ) && value_str_eq(
                trial.pointer(
                    "/runtime_transition_preflight/gate_post_runtime_evidence_summary_state",
                ),
                "post_runtime_evidence_ready",
            ) && value_str_eq(
                trial.pointer(
                    "/runtime_transition_preflight/gate_post_runtime_batch_evidence_source",
                ),
                "runtime_transition_gated_batch_diagnostics",
            ) && value_bool_is(
                trial.pointer(
                    "/runtime_transition_preflight/gate_store_post_runtime_evidence_preflight_ok",
                ),
                true,
            ) && value_bool_is(
                trial.pointer(
                    "/runtime_transition_preflight/gate_batch_post_runtime_evidence_preflight_ok",
                ),
                true,
            ) && value_bool_is(
                trial.pointer(
                    "/store_trial_summary/decision_packet_post_runtime_evidence_summary_backed",
                ),
                true,
            ) && value_bool_is(
                trial.pointer(
                    "/store_trial_summary/decision_packet_post_runtime_evidence_summary_ready",
                ),
                true,
            )
        })
        .unwrap_or(false);
    let gated_store_ready =
        !gated_store_provided || (gated_store_schema_ok && gated_store_consumed);

    let gated_batch_provided = gated_batch_diagnostics.is_some();
    let gated_batch_schema_ok = gated_batch_diagnostics
        .map(|batch| {
            value_str_eq(
                batch.get("schema"),
                BIOCORTEX_RETRIEVAL_OPT_IN_GATED_BATCH_DIAGNOSTICS_SCHEMA,
            ) && value_bool_is(batch.get("gated_batch_diagnostics"), true)
        })
        .unwrap_or(false);
    let gated_batch_query_count = gated_batch_diagnostics
        .and_then(|batch| batch.pointer("/summary/query_count"))
        .and_then(Value::as_u64)
        .unwrap_or(0);
    let gated_batch_ready = gated_batch_diagnostics
        .map(|batch| {
            gated_batch_query_count > 0
                && value_str_eq(batch.get("status"), "completed")
                && batch
                    .pointer("/summary/transition_gate_allowed_count")
                    .and_then(Value::as_u64)
                    == Some(gated_batch_query_count)
                && batch
                    .pointer("/summary/transition_gate_blocked_count")
                    .and_then(Value::as_u64)
                    == Some(0)
                && batch
                    .pointer("/summary/store_trial_called_count")
                    .and_then(Value::as_u64)
                    == Some(gated_batch_query_count)
                && batch
                    .pointer("/summary/calls_memory_search_count")
                    .and_then(Value::as_u64)
                    == Some(gated_batch_query_count)
                && value_bool_is(batch.pointer("/safety/transition_gate_allowed_all"), true)
                && value_bool_is(batch.pointer("/safety/store_trial_called_all"), true)
                && value_bool_is(batch.pointer("/safety/calls_memory_search_all"), true)
                && value_bool_is(batch.pointer("/safety/raw_flags_all_false"), true)
                && value_bool_is(batch.get("changes_memory_search_order"), false)
                && value_bool_is(batch.get("default_search_order_change_allowed"), false)
                && value_bool_is(batch.get("default_calls_unchanged"), true)
        })
        .unwrap_or(false);
    let gated_batch_post_runtime_ready = gated_batch_diagnostics
        .and_then(|batch| batch.get("query_results").and_then(Value::as_array))
        .and_then(|rows| rows.first())
        .map(|row| {
            value_bool_is(
                row.pointer("/transition_preflight/gate_post_runtime_evidence_summary_backed"),
                true,
            ) && value_bool_is(
                row.pointer("/transition_preflight/gate_post_runtime_evidence_summary_ready"),
                true,
            ) && value_str_eq(
                row.pointer("/transition_preflight/gate_post_runtime_evidence_summary_state"),
                "post_runtime_evidence_ready",
            ) && value_str_eq(
                row.pointer("/transition_preflight/gate_post_runtime_batch_evidence_source"),
                "runtime_transition_gated_batch_diagnostics",
            ) && value_bool_is(
                row.pointer("/transition_preflight/gate_store_post_runtime_evidence_preflight_ok"),
                true,
            ) && value_bool_is(
                row.pointer("/transition_preflight/gate_batch_post_runtime_evidence_preflight_ok"),
                true,
            ) && value_bool_is(
                row.pointer("/store_trial/decision_packet_post_runtime_evidence_summary_backed"),
                true,
            ) && value_bool_is(
                row.pointer("/store_trial/decision_packet_post_runtime_evidence_summary_ready"),
                true,
            )
        })
        .unwrap_or(false);
    let gated_batch_ready = !gated_batch_provided || (gated_batch_schema_ok && gated_batch_ready);

    let readiness_capability_ledger_backed = runtime_readiness_packet
        .map(|packet| {
            value_bool_is(
                packet.pointer("/decision_summary/capability_ledger_backed_review_request"),
                true,
            ) || value_bool_is(
                packet.pointer("/boundary_check/capability_ledger_backed_decision_packet"),
                true,
            )
        })
        .unwrap_or(false);
    let readiness_capability_ledger_safe = runtime_readiness_packet
        .map(|packet| {
            value_bool_is(
                packet.pointer("/decision_summary/capability_ledger_safe_for_decision"),
                true,
            ) && value_bool_is(
                packet.pointer("/boundary_check/capability_ledger_safe_for_readiness"),
                true,
            )
        })
        .unwrap_or(false);
    let readiness_capability_ledger_authorizes_runtime_influence = runtime_readiness_packet
        .map(|packet| {
            value_bool_is(
                packet.pointer(
                    "/decision_summary/capability_ledger_can_authorize_runtime_influence",
                ),
                true,
            ) || value_bool_is(
                packet.pointer("/boundary_check/capability_ledger_authorizes_runtime_influence"),
                true,
            )
        })
        .unwrap_or(false);
    let readiness_capability_ledger_report_packet_included = runtime_readiness_packet
        .map(|packet| {
            value_bool_is(
                packet.pointer("/input_contract/capability_ledger_report_packet_included"),
                true,
            ) || value_bool_is(
                packet.pointer("/decision_summary/capability_ledger_report_packet_included"),
                true,
            )
        })
        .unwrap_or(false);
    let readiness_capability_ledger_ready = !readiness_capability_ledger_backed
        || (readiness_capability_ledger_safe
            && !readiness_capability_ledger_authorizes_runtime_influence
            && !readiness_capability_ledger_report_packet_included);

    let transition_capability_ledger_backed = runtime_transition_gate
        .map(|gate| {
            value_bool_is(
                gate.pointer("/readiness_summary/capability_ledger_backed_review_request"),
                true,
            ) || value_bool_is(
                gate.pointer("/boundary_check/capability_ledger_backed_readiness_packet"),
                true,
            )
        })
        .unwrap_or(false);
    let transition_capability_ledger_safe = runtime_transition_gate
        .map(|gate| {
            value_bool_is(
                gate.pointer("/readiness_summary/capability_ledger_safe_for_transition"),
                true,
            ) && value_bool_is(
                gate.pointer("/boundary_check/capability_ledger_safe_for_transition"),
                true,
            )
        })
        .unwrap_or(false);
    let transition_capability_ledger_authorizes_runtime_influence = runtime_transition_gate
        .map(|gate| {
            value_bool_is(
                gate.pointer(
                    "/readiness_summary/capability_ledger_can_authorize_runtime_influence",
                ),
                true,
            ) || value_bool_is(
                gate.pointer("/transition/capability_ledger_can_authorize_runtime_influence"),
                true,
            ) || value_bool_is(
                gate.pointer("/boundary_check/capability_ledger_authorizes_runtime_influence"),
                true,
            )
        })
        .unwrap_or(false);
    let transition_capability_ledger_report_packet_included = runtime_transition_gate
        .map(|gate| {
            value_bool_is(
                gate.pointer("/input_contract/capability_ledger_report_packet_included"),
                true,
            ) || value_bool_is(
                gate.pointer("/readiness_summary/capability_ledger_report_packet_included"),
                true,
            )
        })
        .unwrap_or(false);
    let transition_capability_ledger_ready = !transition_capability_ledger_backed
        || (transition_capability_ledger_safe
            && !transition_capability_ledger_authorizes_runtime_influence
            && !transition_capability_ledger_report_packet_included);

    let gated_store_capability_ledger_backed = gated_store_trial
        .map(|trial| {
            value_bool_is(
                trial.pointer(
                    "/runtime_transition_preflight/gate_capability_ledger_backed_review_request",
                ),
                true,
            )
        })
        .unwrap_or(false);
    let gated_store_capability_ledger_safe = gated_store_trial
        .map(|trial| {
            value_bool_is(
                trial.pointer(
                    "/runtime_transition_preflight/gate_capability_ledger_safe_for_transition",
                ),
                true,
            )
        })
        .unwrap_or(false);
    let gated_store_capability_ledger_authorizes_runtime_influence = gated_store_trial
        .map(|trial| {
            value_bool_is(
                trial.pointer(
                    "/runtime_transition_preflight/gate_capability_ledger_can_authorize_runtime_influence",
                ),
                true,
            )
        })
        .unwrap_or(false);
    let gated_store_capability_ledger_report_packet_included = gated_store_trial
        .map(|trial| {
            value_bool_is(
                trial.pointer(
                    "/runtime_transition_preflight/gate_capability_ledger_report_packet_included",
                ),
                true,
            )
        })
        .unwrap_or(false);
    let gated_store_capability_ledger_preflight_ok = gated_store_trial
        .map(|trial| {
            value_bool_is(
                trial.pointer("/runtime_transition_preflight/gate_capability_ledger_preflight_ok"),
                true,
            )
        })
        .unwrap_or(false);
    let gated_store_capability_ledger_ready = !gated_store_capability_ledger_backed
        || (gated_store_capability_ledger_safe
            && !gated_store_capability_ledger_authorizes_runtime_influence
            && !gated_store_capability_ledger_report_packet_included
            && gated_store_capability_ledger_preflight_ok);

    let gated_batch_capability_ledger_backed_count = gated_batch_diagnostics
        .and_then(|batch| batch.pointer("/summary/gate_capability_ledger_backed_count"))
        .and_then(Value::as_u64)
        .unwrap_or(0);
    let gated_batch_capability_ledger_safe_count = gated_batch_diagnostics
        .and_then(|batch| batch.pointer("/summary/gate_capability_ledger_safe_count"))
        .and_then(Value::as_u64)
        .unwrap_or(0);
    let gated_batch_capability_ledger_authorizes_runtime_influence_count =
        gated_batch_diagnostics
            .and_then(|batch| {
                batch.pointer(
                    "/summary/gate_capability_ledger_authorizes_runtime_influence_count",
                )
            })
            .and_then(Value::as_u64)
            .unwrap_or(0);
    let gated_batch_capability_ledger_report_packet_included_count = gated_batch_diagnostics
        .and_then(|batch| {
            batch.pointer("/summary/gate_capability_ledger_report_packet_included_count")
        })
        .and_then(Value::as_u64)
        .unwrap_or(0);
    let gated_batch_capability_ledger_backed =
        gated_batch_capability_ledger_backed_count > 0;
    let gated_batch_capability_ledger_safe = gated_batch_capability_ledger_backed
        && gated_batch_capability_ledger_safe_count == gated_batch_capability_ledger_backed_count
        && gated_batch_diagnostics
            .map(|batch| {
                value_bool_is(
                    batch.pointer("/safety/gate_capability_ledger_safe_for_transition_all"),
                    true,
                )
            })
            .unwrap_or(false);
    let gated_batch_capability_ledger_authorizes_runtime_influence =
        gated_batch_capability_ledger_authorizes_runtime_influence_count > 0
            || gated_batch_diagnostics
                .map(|batch| {
                    value_bool_is(
                        batch.pointer(
                            "/safety/gate_capability_ledger_authorizes_runtime_influence_any",
                        ),
                        true,
                    )
                })
                .unwrap_or(false);
    let gated_batch_capability_ledger_report_packet_included =
        gated_batch_capability_ledger_report_packet_included_count > 0
            || gated_batch_diagnostics
                .map(|batch| {
                    value_bool_is(
                        batch.pointer(
                            "/safety/gate_capability_ledger_report_packet_included_any",
                        ),
                        true,
                    )
                })
                .unwrap_or(false);
    let gated_batch_capability_ledger_ready = !gated_batch_capability_ledger_backed
        || (gated_batch_capability_ledger_safe
            && !gated_batch_capability_ledger_authorizes_runtime_influence
            && !gated_batch_capability_ledger_report_packet_included);

    let capability_ledger_backed_evidence = readiness_capability_ledger_backed
        || transition_capability_ledger_backed
        || gated_store_capability_ledger_backed
        || gated_batch_capability_ledger_backed;
    let capability_ledger_can_authorize_runtime_influence =
        readiness_capability_ledger_authorizes_runtime_influence
            || transition_capability_ledger_authorizes_runtime_influence
            || gated_store_capability_ledger_authorizes_runtime_influence
            || gated_batch_capability_ledger_authorizes_runtime_influence;
    let capability_ledger_report_packet_included =
        readiness_capability_ledger_report_packet_included
            || transition_capability_ledger_report_packet_included
            || gated_store_capability_ledger_report_packet_included
            || gated_batch_capability_ledger_report_packet_included;
    let capability_ledger_ready = !capability_ledger_backed_evidence
        || (readiness_capability_ledger_ready
            && transition_capability_ledger_ready
            && gated_store_capability_ledger_ready
            && gated_batch_capability_ledger_ready
            && !capability_ledger_can_authorize_runtime_influence
            && !capability_ledger_report_packet_included);

    let evidence_provided =
        readiness_provided || transition_provided || gated_store_provided || gated_batch_provided;
    let mut blockers = Vec::new();
    if evidence_provided {
        push_string_blocker(
            &mut blockers,
            status_request_ok,
            "status_request_not_explicit_opt_in_fts",
        );
        push_string_blocker(
            &mut blockers,
            readiness_provided,
            "runtime_readiness_packet_missing",
        );
        push_string_blocker(
            &mut blockers,
            transition_provided,
            "runtime_transition_gate_missing",
        );
        push_string_blocker(
            &mut blockers,
            readiness_ready,
            "runtime_readiness_packet_not_ready",
        );
        push_string_blocker(
            &mut blockers,
            transition_ready,
            "runtime_transition_gate_not_allowed",
        );
        push_string_blocker(
            &mut blockers,
            gated_store_ready,
            "gated_store_trial_not_consumed",
        );
        push_string_blocker(
            &mut blockers,
            gated_batch_ready,
            "gated_batch_diagnostics_not_ready",
        );
        if readiness_post_runtime_backed {
            push_string_blocker(
                &mut blockers,
                readiness_post_runtime_ready,
                "readiness_post_runtime_evidence_not_ready",
            );
        }
        if transition_post_runtime_backed {
            push_string_blocker(
                &mut blockers,
                transition_post_runtime_ready,
                "transition_post_runtime_evidence_not_ready",
            );
        }
        if gated_store_provided && transition_post_runtime_backed {
            push_string_blocker(
                &mut blockers,
                gated_store_post_runtime_ready,
                "gated_store_post_runtime_evidence_not_ready",
            );
        }
        if gated_batch_provided && transition_post_runtime_backed {
            push_string_blocker(
                &mut blockers,
                gated_batch_post_runtime_ready,
                "gated_batch_post_runtime_evidence_not_ready",
            );
        }
        if readiness_capability_ledger_backed {
            push_string_blocker(
                &mut blockers,
                readiness_capability_ledger_ready,
                "readiness_capability_ledger_not_ready",
            );
        }
        if transition_capability_ledger_backed {
            push_string_blocker(
                &mut blockers,
                transition_capability_ledger_ready,
                "transition_capability_ledger_not_ready",
            );
        }
        if gated_store_capability_ledger_backed {
            push_string_blocker(
                &mut blockers,
                gated_store_capability_ledger_ready,
                "gated_store_capability_ledger_not_ready",
            );
        }
        if gated_batch_capability_ledger_backed {
            push_string_blocker(
                &mut blockers,
                gated_batch_capability_ledger_ready,
                "gated_batch_capability_ledger_not_ready",
            );
        }
    }
    let ready_for_controlled_trial = evidence_provided
        && blockers.is_empty()
        && status_request_ok
        && readiness_ready
        && transition_ready;
    let status = if !evidence_provided {
        "evidence_not_provided"
    } else if ready_for_controlled_trial {
        "ready_for_controlled_explicit_opt_in_fts_trial"
    } else {
        "blocked"
    };

    json!({
        "schema": "agent_bridge.biocortex_retrieval.controlled_trial_readiness_summary.v0",
        "read_only": true,
        "evidence_provided": evidence_provided,
        "status": status,
        "ready_for_controlled_trial": ready_for_controlled_trial,
        "blockers": blockers,
        "requested_mode": mode,
        "requested_per_call_opt_in": per_call_opt_in,
        "status_request_ok": status_request_ok,
        "requires_runtime_readiness_packet": true,
        "requires_runtime_transition_gate": true,
        "gated_store_trial_optional_evidence": true,
        "gated_batch_diagnostics_optional_evidence": true,
        "capability_ledger_optional_evidence": true,
        "capability_ledger": {
            "backed_evidence": capability_ledger_backed_evidence,
            "ready": capability_ledger_backed_evidence && capability_ledger_ready,
            "legacy_evidence_without_capability_ledger_allowed": !capability_ledger_backed_evidence,
            "can_authorize_runtime_influence": capability_ledger_can_authorize_runtime_influence,
            "report_packet_included": capability_ledger_report_packet_included,
            "may_grant_new_authorization": false,
            "may_change_default_retrieval": false,
            "raw_report_included": false,
            "source_summary": {
                "runtime_readiness_packet_backed": readiness_capability_ledger_backed,
                "runtime_transition_gate_backed": transition_capability_ledger_backed,
                "gated_store_trial_backed": gated_store_capability_ledger_backed,
                "gated_batch_diagnostics_backed": gated_batch_capability_ledger_backed,
                "gated_batch_backed_count": gated_batch_capability_ledger_backed_count,
                "gated_batch_safe_count": gated_batch_capability_ledger_safe_count,
            },
        },
        "runtime_readiness_packet": {
            "provided": readiness_provided,
            "schema_ok": readiness_schema_ok,
            "control_plane_ready": readiness_control_plane_ready,
            "boundary_ready": readiness_boundary_ready,
            "side_effects_absent": readiness_side_effects_absent,
            "ready": readiness_ready,
            "post_runtime_evidence_summary_backed": readiness_post_runtime_backed,
            "post_runtime_evidence_summary_ready": readiness_post_runtime_ready,
            "post_runtime_evidence_summary_state": runtime_readiness_packet
                .and_then(|packet| packet.pointer("/decision_summary/post_runtime_evidence_summary_state"))
                .cloned()
                .unwrap_or(Value::Null),
            "post_runtime_batch_evidence_source": runtime_readiness_packet
                .and_then(|packet| packet.pointer("/decision_summary/post_runtime_batch_evidence_source"))
                .cloned()
                .unwrap_or(Value::Null),
            "batch_evidence_source": runtime_readiness_packet
                .and_then(|packet| packet.pointer("/batch_summary/evidence_source"))
                .cloned()
                .unwrap_or(Value::Null),
            "capability_ledger_backed_review_request": readiness_capability_ledger_backed,
            "capability_ledger_ready": readiness_capability_ledger_backed
                && readiness_capability_ledger_ready,
            "capability_ledger_input_schema": runtime_readiness_packet
                .and_then(|packet| packet.pointer("/decision_summary/capability_ledger_input_schema"))
                .cloned()
                .unwrap_or(Value::Null),
            "capability_ledger_input_schema_version": runtime_readiness_packet
                .and_then(|packet| packet.pointer("/decision_summary/capability_ledger_input_schema_version"))
                .cloned()
                .unwrap_or(Value::Null),
            "capability_ledger_can_authorize_runtime_influence": readiness_capability_ledger_authorizes_runtime_influence,
            "capability_ledger_report_packet_included": readiness_capability_ledger_report_packet_included,
        },
        "runtime_transition_gate": {
            "provided": transition_provided,
            "schema_ok": transition_schema_ok,
            "request_ok": transition_request_ok,
            "transition_allowed": transition_allowed,
            "side_effects_absent": transition_side_effects_absent,
            "ready": transition_ready,
            "post_runtime_evidence_summary_backed": transition_post_runtime_backed,
            "post_runtime_evidence_summary_ready": transition_post_runtime_ready,
            "post_runtime_evidence_summary_state": runtime_transition_gate
                .and_then(|gate| gate.pointer("/readiness_summary/post_runtime_evidence_summary_state"))
                .cloned()
                .unwrap_or(Value::Null),
            "post_runtime_batch_evidence_source": runtime_transition_gate
                .and_then(|gate| gate.pointer("/readiness_summary/post_runtime_batch_evidence_source"))
                .cloned()
                .unwrap_or(Value::Null),
            "capability_ledger_backed_review_request": transition_capability_ledger_backed,
            "capability_ledger_safe_for_transition": transition_capability_ledger_backed
                && transition_capability_ledger_ready,
            "capability_ledger_input_schema": runtime_transition_gate
                .and_then(|gate| gate.pointer("/readiness_summary/capability_ledger_input_schema"))
                .cloned()
                .unwrap_or(Value::Null),
            "capability_ledger_input_schema_version": runtime_transition_gate
                .and_then(|gate| gate.pointer("/readiness_summary/capability_ledger_input_schema_version"))
                .cloned()
                .unwrap_or(Value::Null),
            "capability_ledger_can_authorize_runtime_influence": transition_capability_ledger_authorizes_runtime_influence,
            "capability_ledger_report_packet_included": transition_capability_ledger_report_packet_included,
        },
        "gated_store_trial": {
            "provided": gated_store_provided,
            "schema_ok": gated_store_schema_ok,
            "gate_consumed": gated_store_consumed,
            "ready": gated_store_ready,
            "post_runtime_evidence_summary_ready": gated_store_post_runtime_ready,
            "store_trial_called": gated_store_trial
                .and_then(|trial| trial.get("store_trial_called"))
                .cloned()
                .unwrap_or(Value::Bool(false)),
            "calls_memory_search": gated_store_trial
                .and_then(|trial| trial.get("calls_memory_search"))
                .cloned()
                .unwrap_or(Value::Bool(false)),
            "runs_biocortex": gated_store_trial
                .and_then(|trial| trial.get("runs_biocortex"))
                .cloned()
                .unwrap_or(Value::Bool(false)),
            "changes_memory_search_order": gated_store_trial
                .and_then(|trial| trial.get("changes_memory_search_order"))
                .cloned()
                .unwrap_or(Value::Bool(false)),
            "capability_ledger_backed_review_request": gated_store_capability_ledger_backed,
            "capability_ledger_safe_for_transition": gated_store_capability_ledger_backed
                && gated_store_capability_ledger_ready,
            "capability_ledger_can_authorize_runtime_influence": gated_store_capability_ledger_authorizes_runtime_influence,
            "capability_ledger_report_packet_included": gated_store_capability_ledger_report_packet_included,
            "capability_ledger_preflight_ok": gated_store_capability_ledger_preflight_ok,
        },
        "gated_batch_diagnostics": {
            "provided": gated_batch_provided,
            "schema_ok": gated_batch_schema_ok,
            "ready": gated_batch_ready,
            "post_runtime_evidence_summary_ready": gated_batch_post_runtime_ready,
            "query_count": gated_batch_query_count,
            "transition_gate_allowed_count": gated_batch_diagnostics
                .and_then(|batch| batch.pointer("/summary/transition_gate_allowed_count"))
                .cloned()
                .unwrap_or_else(|| json!(0)),
            "store_trial_called_count": gated_batch_diagnostics
                .and_then(|batch| batch.pointer("/summary/store_trial_called_count"))
                .cloned()
                .unwrap_or_else(|| json!(0)),
            "calls_memory_search_count": gated_batch_diagnostics
                .and_then(|batch| batch.pointer("/summary/calls_memory_search_count"))
                .cloned()
                .unwrap_or_else(|| json!(0)),
            "runs_biocortex_any": gated_batch_diagnostics
                .and_then(|batch| batch.pointer("/safety/runs_biocortex_any"))
                .cloned()
                .unwrap_or(Value::Bool(false)),
            "capability_ledger_backed_count": gated_batch_capability_ledger_backed_count,
            "capability_ledger_safe_count": gated_batch_capability_ledger_safe_count,
            "capability_ledger_authorizes_runtime_influence_count": gated_batch_capability_ledger_authorizes_runtime_influence_count,
            "capability_ledger_report_packet_included_count": gated_batch_capability_ledger_report_packet_included_count,
            "capability_ledger_backed_all": gated_batch_diagnostics
                .and_then(|batch| batch.pointer("/safety/gate_capability_ledger_backed_all"))
                .cloned()
                .unwrap_or(Value::Bool(false)),
            "capability_ledger_safe_for_transition_all": gated_batch_capability_ledger_safe,
            "capability_ledger_authorizes_runtime_influence_any": gated_batch_capability_ledger_authorizes_runtime_influence,
            "capability_ledger_report_packet_included_any": gated_batch_capability_ledger_report_packet_included,
        },
        "status_surface_calls_memory_search": false,
        "status_surface_runs_biocortex": false,
        "status_surface_changes_memory_search_order": false,
        "raw_packets_included": false,
        "raw_queries_included": false,
        "raw_keys_included": false,
        "content_included": false,
    })
}

pub fn biocortex_retrieval_opt_in_audit_report(opts: BioCortexRetrievalOptInAuditOptions) -> Value {
    let mode = normalize_token(&opts.mode);
    let mode = if mode.is_empty() {
        "fts".to_string()
    } else {
        mode
    };
    let mode_authorized = mode == "fts";
    let gate = biocortex_retrieval_opt_in_gate_report(opts.per_call_opt_in);
    let gate_status = gate
        .get("status")
        .and_then(Value::as_str)
        .unwrap_or("unknown");
    let gate_ready = gate
        .get("ready_for_explicit_opt_in_experiment")
        .and_then(Value::as_bool)
        .unwrap_or(false);
    let fallback_reason = opts
        .fallback_reason
        .as_deref()
        .map(str::trim)
        .filter(|reason| !reason.is_empty())
        .map(str::to_string)
        .unwrap_or_else(|| {
            if !mode_authorized {
                "mode_not_authorized".to_string()
            } else if !gate_ready {
                gate_status.to_string()
            } else {
                "ordering_behavior_not_connected".to_string()
            }
        });
    let side_signal_status = opts
        .side_signal_status
        .as_deref()
        .map(str::trim)
        .filter(|status| !status.is_empty())
        .unwrap_or(if gate_ready && mode_authorized {
            "not_run_ordering_behavior_not_connected"
        } else {
            "not_run_gate_unavailable"
        });
    let baseline_key_count = opts.baseline_keys.len();
    let baseline_order_hash = sha256_json(&json!({
        "mode": &mode,
        "baseline_keys": &opts.baseline_keys,
    }));
    let query_hash = opts
        .query
        .as_deref()
        .map(str::trim)
        .filter(|query| !query.is_empty())
        .map(|query| sha256_json(&json!({"query": query})))
        .unwrap_or_else(|| sha256_json(&Value::Null));
    let latency = opts
        .latency_ms
        .map(|value| json!(round3(value)))
        .unwrap_or(Value::Null);
    let store_contract = BioCortexRetrievalOptInRequest {
        mode: mode.clone(),
        per_call_opt_in: opts.per_call_opt_in,
        compile_feature_enabled: cfg!(feature = "biocortex-retrieval-opt-in"),
        runtime_enabled: env_truthy(BIOCORTEX_RETRIEVAL_OPT_IN_ENABLE_ENV),
        operator_disabled: env_truthy(BIOCORTEX_RETRIEVAL_DISABLE_ENV),
        baseline_completed: true,
        baseline_key_count,
        runtime_adapter_approved: false,
        ordering_behavior_connected: false,
    }
    .evaluate()
    .response_contract(false);
    let store_contract = serde_json::to_value(&store_contract).unwrap_or(Value::Null);
    let controlled_trial_readiness = biocortex_retrieval_controlled_trial_readiness_summary(
        &mode,
        opts.per_call_opt_in,
        opts.runtime_readiness_packet.as_ref(),
        opts.runtime_transition_gate.as_ref(),
        opts.gated_store_trial.as_ref(),
        opts.gated_batch_diagnostics.as_ref(),
    );

    json!({
        "schema": BIOCORTEX_RETRIEVAL_OPT_IN_AUDIT_SCHEMA,
        "generated_at": now_secs(),
        "read_only": true,
        "implementation_stage": "audit_shape_only",
        "authorization_scope": "opt_in_experiment",
        "mode": mode,
        "mode_authorized": mode_authorized,
        "per_call_opt_in": {
            "present": opts.per_call_opt_in,
            "source": "explicit_call_argument_reserved",
            "required": true,
        },
        "query_hash": query_hash,
        "baseline_order": {
            "key_count": baseline_key_count,
            "hash": baseline_order_hash,
            "raw_keys_included": false,
            "content_included": false,
        },
        "experimental_order": {
            "available": false,
            "hash": Value::Null,
            "reason": "ordering_behavior_not_connected",
        },
        "returned_order": {
            "source": "baseline",
            "hash_matches_baseline": true,
        },
        "fallback": {
            "baseline_returned": true,
            "reason": fallback_reason,
        },
        "side_signal": {
            "status": side_signal_status,
            "raw_included": false,
        },
        "latency_ms": latency,
        "affected_call_site": if mode_authorized {
            json!({
                "file": "crates/store/src/sqlite.rs",
                "line": 3067,
                "function": "SqliteStore::memory_search",
                "ordering_behavior_connected": false,
            })
        } else {
            Value::Null
        },
        "unaffected_modes": [
            "hybrid",
            "semantic"
        ],
        "gate": gate,
        "store_contract": store_contract,
        "controlled_trial_readiness": controlled_trial_readiness,
        "runtime_adapter_approved": false,
        "default_search_order_change_allowed": false,
        "default_calls_unchanged": true,
        "may_change_search_order_now": false,
        "ordering_behavior_connected": false,
        "changes_memory_search_order": false,
        "boundary": retrieval_boundary_payload(),
    })
}

pub fn biocortex_retrieval_opt_in_dry_run_plan(
    opts: BioCortexRetrievalOptInDryRunOptions,
) -> Value {
    let mode = normalize_token(&opts.mode);
    let mode = if mode.is_empty() {
        "fts".to_string()
    } else {
        mode
    };
    let mode_authorized = mode == "fts";
    let gate = biocortex_retrieval_opt_in_gate_report(opts.per_call_opt_in);
    let baseline_key_count = opts.baseline_keys.len();
    let baseline_order_hash = sha256_json(&json!({
        "mode": &mode,
        "baseline_keys": &opts.baseline_keys,
    }));
    let query_hash = opts
        .query
        .as_deref()
        .map(str::trim)
        .filter(|query| !query.is_empty())
        .map(|query| sha256_json(&json!({"query": query})))
        .unwrap_or_else(|| sha256_json(&Value::Null));
    let coverage_threshold = opts.coverage_threshold.clamp(0.0, 1.0);
    let store_contract = BioCortexRetrievalOptInRequest {
        mode: mode.clone(),
        per_call_opt_in: opts.per_call_opt_in,
        compile_feature_enabled: cfg!(feature = "biocortex-retrieval-opt-in"),
        runtime_enabled: env_truthy(BIOCORTEX_RETRIEVAL_OPT_IN_ENABLE_ENV),
        operator_disabled: env_truthy(BIOCORTEX_RETRIEVAL_DISABLE_ENV),
        baseline_completed: opts.baseline_completed,
        baseline_key_count,
        runtime_adapter_approved: false,
        ordering_behavior_connected: false,
    }
    .evaluate()
    .response_contract(false);
    let fallback_reason = serde_json::to_value(store_contract.fallback_reason)
        .unwrap_or(Value::Null)
        .as_str()
        .map(str::to_string)
        .unwrap_or_else(|| "dry_run_planner_only".to_string());
    let blocking_reasons = store_contract.decision.blocking_reasons.clone();
    let store_contract_json = serde_json::to_value(&store_contract).unwrap_or(Value::Null);

    json!({
        "schema": BIOCORTEX_RETRIEVAL_OPT_IN_DRY_RUN_SCHEMA,
        "generated_at": now_secs(),
        "read_only": true,
        "dry_run": true,
        "implementation_stage": "dry_run_planner_only",
        "authorization_scope": "opt_in_experiment",
        "mode": mode,
        "mode_authorized": mode_authorized,
        "per_call_opt_in": {
            "present": opts.per_call_opt_in,
            "source": "explicit_call_argument_reserved",
            "required": true,
        },
        "query_hash": query_hash,
        "baseline_order": {
            "completed": opts.baseline_completed,
            "key_count": baseline_key_count,
            "hash": baseline_order_hash,
            "raw_keys_included": false,
            "content_included": false,
        },
        "planned_steps": [
            {
                "id": "baseline_fts_memory_search",
                "status": "not_run_dry_run",
                "call_site": {
                    "file": "crates/store/src/sqlite.rs",
                    "line": 3067,
                    "function": "SqliteStore::memory_search",
                },
                "would_run_in_real_ordering_path": mode_authorized,
                "dry_run_calls_memory_search": false,
                "output": "baseline_order",
            },
            {
                "id": "candidate_projection",
                "status": if opts.baseline_completed {
                    "planned_after_baseline"
                } else {
                    "blocked_baseline_not_established"
                },
                "input": "baseline_order",
                "output": "bounded_candidate_summaries",
                "raw_keys_included_in_report": false,
                "content_included_in_report": false,
            },
            {
                "id": "biocortex_side_signal",
                "status": "not_run_dry_run",
                "checkout_env": BIOCORTEX_CHECKOUT_ENV,
                "timeout_ms": opts.timeout_ms,
                "coverage_threshold": round3(coverage_threshold),
                "join_key": "candidate_key",
                "runs_biocortex_now": false,
                "raw_side_signal_included": false,
            },
            {
                "id": "join_and_score",
                "status": "not_run_dry_run",
                "join_key": "candidate_key",
                "candidate_recall_source": "baseline_only",
                "can_add_new_candidates": false,
            },
            {
                "id": "return_order",
                "status": "baseline_returned_by_contract",
                "returned_order_source": "baseline",
                "fallback_reason": fallback_reason,
            }
        ],
        "planned_side_signal": {
            "status": "not_run_dry_run",
            "checkout_env": BIOCORTEX_CHECKOUT_ENV,
            "timeout_ms": opts.timeout_ms,
            "coverage_threshold": round3(coverage_threshold),
            "join_key": "candidate_key",
            "raw_included": false,
        },
        "planner_result": {
            "returned_order_source": "baseline",
            "baseline_returned": true,
            "fallback_reason": fallback_reason,
            "blocking_reasons": serde_json::to_value(blocking_reasons).unwrap_or(Value::Null),
            "execution_ready": false,
        },
        "gate": gate,
        "store_contract": store_contract_json,
        "calls_memory_search": false,
        "runs_biocortex": false,
        "registers_embedding_backend": false,
        "changes_memory_search_order": false,
        "default_search_order_change_allowed": false,
        "default_calls_unchanged": true,
        "ordering_behavior_connected": false,
        "may_change_search_order_now": false,
        "boundary": retrieval_boundary_payload(),
    })
}

pub fn biocortex_retrieval_opt_in_review_packet(
    opts: BioCortexRetrievalOptInReviewPacketOptions,
) -> Value {
    let plan = opts.dry_run_plan;
    let schema_ok = value_str_eq(
        plan.get("schema"),
        BIOCORTEX_RETRIEVAL_OPT_IN_DRY_RUN_SCHEMA,
    );
    let read_only_ok = value_bool_is(plan.get("read_only"), true);
    let dry_run_ok = value_bool_is(plan.get("dry_run"), true);
    let calls_memory_search_false = value_bool_is(plan.get("calls_memory_search"), false);
    let runs_biocortex_false = value_bool_is(plan.get("runs_biocortex"), false);
    let registers_embedding_backend_false =
        value_bool_is(plan.get("registers_embedding_backend"), false);
    let changes_memory_search_order_false =
        value_bool_is(plan.get("changes_memory_search_order"), false);
    let default_search_order_change_allowed_false =
        value_bool_is(plan.get("default_search_order_change_allowed"), false);
    let ordering_behavior_connected_false =
        value_bool_is(plan.get("ordering_behavior_connected"), false);
    let may_change_search_order_now_false =
        value_bool_is(plan.get("may_change_search_order_now"), false);
    let baseline_raw_keys_absent =
        value_bool_is(plan.pointer("/baseline_order/raw_keys_included"), false);
    let baseline_content_absent =
        value_bool_is(plan.pointer("/baseline_order/content_included"), false);
    let side_signal_raw_absent =
        value_bool_is(plan.pointer("/planned_side_signal/raw_included"), false);
    let baseline_returned = value_bool_is(plan.pointer("/planner_result/baseline_returned"), true);
    let returned_order_is_baseline = value_str_eq(
        plan.pointer("/planner_result/returned_order_source"),
        "baseline",
    );

    let mut violations = Vec::new();
    push_violation(&mut violations, schema_ok, "schema_not_dry_run_plan");
    push_violation(&mut violations, read_only_ok, "dry_run_plan_not_read_only");
    push_violation(&mut violations, dry_run_ok, "dry_run_flag_missing");
    push_violation(
        &mut violations,
        calls_memory_search_false,
        "calls_memory_search_true_or_missing",
    );
    push_violation(
        &mut violations,
        runs_biocortex_false,
        "runs_biocortex_true_or_missing",
    );
    push_violation(
        &mut violations,
        registers_embedding_backend_false,
        "registers_embedding_backend_true_or_missing",
    );
    push_violation(
        &mut violations,
        changes_memory_search_order_false,
        "changes_memory_search_order_true_or_missing",
    );
    push_violation(
        &mut violations,
        default_search_order_change_allowed_false,
        "default_search_order_change_allowed_true_or_missing",
    );
    push_violation(
        &mut violations,
        ordering_behavior_connected_false,
        "ordering_behavior_connected_true_or_missing",
    );
    push_violation(
        &mut violations,
        may_change_search_order_now_false,
        "may_change_search_order_now_true_or_missing",
    );
    push_violation(
        &mut violations,
        baseline_raw_keys_absent,
        "baseline_raw_keys_included_or_missing",
    );
    push_violation(
        &mut violations,
        baseline_content_absent,
        "baseline_content_included_or_missing",
    );
    push_violation(
        &mut violations,
        side_signal_raw_absent,
        "side_signal_raw_included_or_missing",
    );
    push_violation(
        &mut violations,
        baseline_returned,
        "baseline_not_returned_by_contract",
    );
    push_violation(
        &mut violations,
        returned_order_is_baseline,
        "returned_order_not_baseline",
    );

    let review_ready = violations.is_empty();
    let mode = plan
        .get("mode")
        .and_then(Value::as_str)
        .unwrap_or("unknown");
    let gate = plan.get("gate").unwrap_or(&Value::Null);
    let planner = plan.get("planner_result").unwrap_or(&Value::Null);
    let baseline = plan.get("baseline_order").unwrap_or(&Value::Null);
    let side_signal = plan.get("planned_side_signal").unwrap_or(&Value::Null);
    let store_contract = plan.get("store_contract").unwrap_or(&Value::Null);

    json!({
        "schema": BIOCORTEX_RETRIEVAL_OPT_IN_REVIEW_PACKET_SCHEMA,
        "generated_at": now_secs(),
        "read_only": true,
        "dry_run_consumer": true,
        "implementation_stage": "review_packet_consumer_only",
        "authorization_scope": "opt_in_experiment",
        "purpose": "Review packet derived from a dry-run plan; this is not approval state.",
        "input_contract": {
            "source_schema": plan.get("schema").cloned().unwrap_or(Value::Null),
            "requires_schema": BIOCORTEX_RETRIEVAL_OPT_IN_DRY_RUN_SCHEMA,
            "dry_run_plan_included": false,
            "unknown_fields_ignored": true,
            "raw_query_included": false,
            "raw_keys_included": false,
            "content_included": false,
        },
        "review_target": {
            "mode": mode,
            "mode_authorized": plan.get("mode_authorized").cloned().unwrap_or(Value::Null),
            "commit": required_or_value(opts.commit),
            "reviewer": required_or_value(opts.reviewer),
            "forum_post_id": required_or_value(opts.forum_post_id),
            "memory_key": required_or_value(opts.memory_key),
        },
        "dry_run_summary": {
            "query_hash": plan.get("query_hash").cloned().unwrap_or(Value::Null),
            "baseline_order": {
                "completed": baseline.get("completed").cloned().unwrap_or(Value::Null),
                "key_count": baseline.get("key_count").cloned().unwrap_or(Value::Null),
                "hash": baseline.get("hash").cloned().unwrap_or(Value::Null),
                "raw_keys_included": false,
                "content_included": false,
            },
            "gate": {
                "status": gate.get("status").cloned().unwrap_or(Value::Null),
                "ready_for_explicit_opt_in_experiment": gate
                    .get("ready_for_explicit_opt_in_experiment")
                    .cloned()
                    .unwrap_or(Value::Null),
                "runtime_enabled": gate.get("runtime_enabled").cloned().unwrap_or(Value::Null),
                "operator_disabled": gate.get("operator_disabled").cloned().unwrap_or(Value::Null),
            },
            "planner_result": {
                "returned_order_source": planner
                    .get("returned_order_source")
                    .cloned()
                    .unwrap_or(Value::Null),
                "baseline_returned": planner
                    .get("baseline_returned")
                    .cloned()
                    .unwrap_or(Value::Null),
                "fallback_reason": planner
                    .get("fallback_reason")
                    .cloned()
                    .unwrap_or(Value::Null),
                "blocking_reasons": planner
                    .get("blocking_reasons")
                    .cloned()
                    .unwrap_or(Value::Null),
                "execution_ready": planner
                    .get("execution_ready")
                    .cloned()
                    .unwrap_or(Value::Null),
            },
            "planned_side_signal": {
                "status": side_signal.get("status").cloned().unwrap_or(Value::Null),
                "timeout_ms": side_signal.get("timeout_ms").cloned().unwrap_or(Value::Null),
                "coverage_threshold": side_signal
                    .get("coverage_threshold")
                    .cloned()
                    .unwrap_or(Value::Null),
                "raw_included": false,
            },
            "store_contract": {
                "schema": store_contract.get("schema").cloned().unwrap_or(Value::Null),
                "baseline_returned": store_contract
                    .get("baseline_returned")
                    .cloned()
                    .unwrap_or(Value::Null),
                "returned_order_source": store_contract
                    .get("returned_order_source")
                    .cloned()
                    .unwrap_or(Value::Null),
                "fallback_reason": store_contract
                    .get("fallback_reason")
                    .cloned()
                    .unwrap_or(Value::Null),
                "changes_memory_search_order": store_contract
                    .get("changes_memory_search_order")
                    .cloned()
                    .unwrap_or(Value::Null),
            },
        },
        "boundary_check": {
            "review_ready": review_ready,
            "violations": violations,
            "schema_ok": schema_ok,
            "read_only_ok": read_only_ok,
            "dry_run_ok": dry_run_ok,
            "calls_memory_search_false": calls_memory_search_false,
            "runs_biocortex_false": runs_biocortex_false,
            "registers_embedding_backend_false": registers_embedding_backend_false,
            "changes_memory_search_order_false": changes_memory_search_order_false,
            "default_search_order_change_allowed_false": default_search_order_change_allowed_false,
            "ordering_behavior_connected_false": ordering_behavior_connected_false,
            "may_change_search_order_now_false": may_change_search_order_now_false,
            "baseline_raw_keys_absent": baseline_raw_keys_absent,
            "baseline_content_absent": baseline_content_absent,
            "side_signal_raw_absent": side_signal_raw_absent,
            "baseline_returned": baseline_returned,
            "returned_order_is_baseline": returned_order_is_baseline,
        },
        "required_human_checks": [
            "Confirm the dry-run packet was generated from the reviewed commit.",
            "Confirm fts is the only authorized mode for this opt-in experiment.",
            "Confirm the packet still reports baseline-only return order.",
            "Confirm no raw query, memory keys, or memory contents are present.",
            "Confirm any later ordering implementation has a separate review and authorization record."
        ],
        "approval_state": "not_approved",
        "runtime_adapter_approved": false,
        "approval_writes_allowed": false,
        "writes_approval": false,
        "calls_memory_search": false,
        "runs_biocortex": false,
        "registers_embedding_backend": false,
        "changes_memory_search_order": false,
        "default_search_order_change_allowed": false,
        "ordering_behavior_connected": false,
        "may_change_search_order_now": false,
        "may_implement_ordering_now": false,
        "default_calls_unchanged": true,
        "boundary": retrieval_boundary_payload(),
    })
}

pub fn biocortex_retrieval_opt_in_execution_packet(
    opts: BioCortexRetrievalOptInExecutionPacketOptions,
) -> Value {
    let review = opts.review_packet;
    let schema_ok = value_str_eq(
        review.get("schema"),
        BIOCORTEX_RETRIEVAL_OPT_IN_REVIEW_PACKET_SCHEMA,
    );
    let read_only_ok = value_bool_is(review.get("read_only"), true);
    let dry_run_consumer_ok = value_bool_is(review.get("dry_run_consumer"), true);
    let approval_state_not_approved = value_str_eq(review.get("approval_state"), "not_approved");
    let review_ready = value_bool_is(review.pointer("/boundary_check/review_ready"), true);
    let review_violations_empty = review
        .pointer("/boundary_check/violations")
        .and_then(Value::as_array)
        .map(Vec::is_empty)
        .unwrap_or(false);
    let raw_plan_absent = value_bool_is(
        review.pointer("/input_contract/dry_run_plan_included"),
        false,
    );
    let raw_query_absent =
        value_bool_is(review.pointer("/input_contract/raw_query_included"), false);
    let raw_keys_absent = value_bool_is(review.pointer("/input_contract/raw_keys_included"), false);
    let content_absent = value_bool_is(review.pointer("/input_contract/content_included"), false);
    let review_calls_memory_search_false = value_bool_is(review.get("calls_memory_search"), false);
    let review_runs_biocortex_false = value_bool_is(review.get("runs_biocortex"), false);
    let review_changes_order_false =
        value_bool_is(review.get("changes_memory_search_order"), false);
    let review_ordering_connected_false =
        value_bool_is(review.get("ordering_behavior_connected"), false);

    let mut packet_blockers = Vec::new();
    push_string_blocker(
        &mut packet_blockers,
        schema_ok,
        "review_packet_schema_invalid",
    );
    push_string_blocker(
        &mut packet_blockers,
        read_only_ok,
        "review_packet_not_read_only",
    );
    push_string_blocker(
        &mut packet_blockers,
        dry_run_consumer_ok,
        "review_packet_not_dry_run_consumer",
    );
    push_string_blocker(
        &mut packet_blockers,
        approval_state_not_approved,
        "review_packet_approval_state_changed",
    );
    push_string_blocker(
        &mut packet_blockers,
        review_ready,
        "review_packet_not_ready",
    );
    push_string_blocker(
        &mut packet_blockers,
        review_violations_empty,
        "review_packet_has_boundary_violations",
    );
    push_string_blocker(&mut packet_blockers, raw_plan_absent, "raw_plan_included");
    push_string_blocker(&mut packet_blockers, raw_query_absent, "raw_query_included");
    push_string_blocker(&mut packet_blockers, raw_keys_absent, "raw_keys_included");
    push_string_blocker(&mut packet_blockers, content_absent, "content_included");
    push_string_blocker(
        &mut packet_blockers,
        review_calls_memory_search_false,
        "review_packet_claims_memory_search",
    );
    push_string_blocker(
        &mut packet_blockers,
        review_runs_biocortex_false,
        "review_packet_claims_biocortex_execution",
    );
    push_string_blocker(
        &mut packet_blockers,
        review_changes_order_false,
        "review_packet_claims_order_change",
    );
    push_string_blocker(
        &mut packet_blockers,
        review_ordering_connected_false,
        "review_packet_claims_ordering_connected",
    );

    let mode = review
        .pointer("/review_target/mode")
        .and_then(Value::as_str)
        .unwrap_or("fts")
        .to_string();
    let baseline_completed = review
        .pointer("/dry_run_summary/baseline_order/completed")
        .and_then(Value::as_bool)
        .unwrap_or(false);
    let baseline_key_count = review
        .pointer("/dry_run_summary/baseline_order/key_count")
        .and_then(Value::as_u64)
        .unwrap_or(0) as usize;
    let store_contract = BioCortexRetrievalOptInRequest {
        mode: mode.clone(),
        per_call_opt_in: opts.per_call_opt_in,
        compile_feature_enabled: cfg!(feature = "biocortex-retrieval-opt-in"),
        runtime_enabled: env_truthy(BIOCORTEX_RETRIEVAL_OPT_IN_ENABLE_ENV),
        operator_disabled: env_truthy(BIOCORTEX_RETRIEVAL_DISABLE_ENV),
        baseline_completed,
        baseline_key_count,
        runtime_adapter_approved: false,
        ordering_behavior_connected: false,
    }
    .evaluate()
    .response_contract(false);
    let store_blockers = store_contract
        .decision
        .blocking_reasons
        .iter()
        .map(|reason| serde_json::to_value(reason).unwrap_or(Value::Null))
        .collect::<Vec<_>>();
    let store_fallback_reason = serde_json::to_value(store_contract.fallback_reason)
        .unwrap_or(Value::Null)
        .as_str()
        .map(str::to_string)
        .unwrap_or_else(|| "execution_packet_contract_only".to_string());
    let execution_allowed = false;
    let preflight_passed = packet_blockers.is_empty()
        && store_contract.baseline_returned
        && !store_contract.changes_memory_search_order;
    let store_contract_json = serde_json::to_value(&store_contract).unwrap_or(Value::Null);

    json!({
        "schema": BIOCORTEX_RETRIEVAL_OPT_IN_EXECUTION_PACKET_SCHEMA,
        "generated_at": now_secs(),
        "read_only": true,
        "execution_packet": true,
        "implementation_stage": "execution_packet_contract_only",
        "authorization_scope": "opt_in_experiment",
        "purpose": "Preflight contract for a future protected adapter; this does not execute retrieval ordering.",
        "attempt": {
            "attempt_id": required_or_value(opts.attempt_id),
            "commit": required_or_value(opts.commit),
            "mode": mode,
            "per_call_opt_in": opts.per_call_opt_in,
        },
        "input_contract": {
            "source_schema": review.get("schema").cloned().unwrap_or(Value::Null),
            "requires_schema": BIOCORTEX_RETRIEVAL_OPT_IN_REVIEW_PACKET_SCHEMA,
            "review_packet_included": false,
            "unknown_fields_ignored": true,
            "raw_query_included": false,
            "raw_keys_included": false,
            "content_included": false,
        },
        "review_summary": {
            "review_ready": review_ready,
            "review_violation_count": review
                .pointer("/boundary_check/violations")
                .and_then(Value::as_array)
                .map(|items| items.len())
                .unwrap_or(0),
            "approval_state": review.get("approval_state").cloned().unwrap_or(Value::Null),
            "query_hash": review
                .pointer("/dry_run_summary/query_hash")
                .cloned()
                .unwrap_or(Value::Null),
            "baseline_order": {
                "completed": baseline_completed,
                "key_count": baseline_key_count,
                "hash": review
                    .pointer("/dry_run_summary/baseline_order/hash")
                    .cloned()
                    .unwrap_or(Value::Null),
                "raw_keys_included": false,
                "content_included": false,
            },
            "fallback_reason": review
                .pointer("/dry_run_summary/planner_result/fallback_reason")
                .cloned()
                .unwrap_or(Value::Null),
        },
        "protected_adapter_contract": {
            "call_site": {
                "file": "crates/store/src/sqlite.rs",
                "line": 3067,
                "function": "SqliteStore::memory_search",
            },
            "candidate_recall_source": "baseline_only",
            "can_add_new_candidates": false,
            "join_key": "candidate_key",
            "requires_review_packet": true,
            "requires_per_call_opt_in": true,
            "requires_runtime_adapter_approval": true,
            "requires_ordering_behavior_connected": true,
            "fail_open_return": "baseline",
            "raw_query_included": false,
            "raw_keys_included": false,
            "content_included": false,
            "side_signal_raw_included": false,
        },
        "preflight": {
            "preflight_passed_for_baseline_only_contract": preflight_passed,
            "execution_allowed": execution_allowed,
            "packet_blockers": packet_blockers,
            "store_blockers": store_blockers,
            "fallback_reason": store_fallback_reason,
        },
        "store_contract": store_contract_json,
        "execution_decision": {
            "calls_memory_search_now": false,
            "runs_biocortex_now": false,
            "registers_embedding_backend_now": false,
            "returned_order_source": "baseline",
            "baseline_returned": true,
            "changes_memory_search_order": false,
            "ordering_behavior_connected": false,
            "may_change_search_order_now": false,
            "may_implement_ordering_now": false,
        },
        "approval_state": "not_approved",
        "runtime_adapter_approved": false,
        "approval_writes_allowed": false,
        "writes_approval": false,
        "calls_memory_search": false,
        "runs_biocortex": false,
        "registers_embedding_backend": false,
        "changes_memory_search_order": false,
        "default_search_order_change_allowed": false,
        "ordering_behavior_connected": false,
        "may_change_search_order_now": false,
        "may_implement_ordering_now": false,
        "default_calls_unchanged": true,
        "boundary": retrieval_boundary_payload(),
    })
}

pub async fn biocortex_retrieval_opt_in_runtime_trial(
    opts: BioCortexRetrievalOptInRuntimeTrialOptions,
) -> Value {
    let packet = opts.execution_packet;
    let schema_ok = value_str_eq(
        packet.get("schema"),
        BIOCORTEX_RETRIEVAL_OPT_IN_EXECUTION_PACKET_SCHEMA,
    );
    let read_only_ok = value_bool_is(packet.get("read_only"), true);
    let execution_packet_ok = value_bool_is(packet.get("execution_packet"), true);
    let preflight_ok = value_bool_is(
        packet.pointer("/preflight/preflight_passed_for_baseline_only_contract"),
        true,
    );
    let ordering_execution_disallowed =
        value_bool_is(packet.pointer("/preflight/execution_allowed"), false);
    let approval_state_not_approved = value_str_eq(packet.get("approval_state"), "not_approved");
    let runtime_adapter_not_approved = value_bool_is(packet.get("runtime_adapter_approved"), false);
    let calls_memory_search_false = value_bool_is(packet.get("calls_memory_search"), false);
    let changes_order_false = value_bool_is(packet.get("changes_memory_search_order"), false);
    let ordering_connected_false = value_bool_is(packet.get("ordering_behavior_connected"), false);
    let raw_packet_absent = value_bool_is(
        packet.pointer("/input_contract/review_packet_included"),
        false,
    );
    let raw_query_absent =
        value_bool_is(packet.pointer("/input_contract/raw_query_included"), false);
    let raw_keys_absent = value_bool_is(packet.pointer("/input_contract/raw_keys_included"), false);
    let content_absent = value_bool_is(packet.pointer("/input_contract/content_included"), false);

    let mode = packet
        .pointer("/attempt/mode")
        .and_then(Value::as_str)
        .unwrap_or("fts")
        .to_string();
    let per_call_opt_in = packet
        .pointer("/attempt/per_call_opt_in")
        .and_then(Value::as_bool)
        .unwrap_or(false);
    let mode_authorized = normalize_token(&mode) == "fts";
    let baseline_completed = packet
        .pointer("/review_summary/baseline_order/completed")
        .and_then(Value::as_bool)
        .unwrap_or(false);
    let packet_baseline_key_count = packet
        .pointer("/review_summary/baseline_order/key_count")
        .and_then(Value::as_u64)
        .unwrap_or(0) as usize;

    let query = opts.query.trim().to_string();
    let candidates = opts
        .candidates
        .into_iter()
        .filter(|candidate| !candidate.key.trim().is_empty())
        .collect::<Vec<_>>();
    let candidate_count = candidates.len();
    let candidate_count_matches_packet = packet_baseline_key_count == candidate_count;
    let coverage_threshold = opts.coverage_threshold.clamp(0.0, 1.0);
    let timeout_ms = opts.timeout_ms.clamp(1_000, 600_000);
    let gate = biocortex_retrieval_opt_in_gate_report(per_call_opt_in);
    let gate_ready = gate
        .get("ready_for_explicit_opt_in_experiment")
        .and_then(Value::as_bool)
        .unwrap_or(false);
    let query_present = !query.is_empty();
    let candidates_present = candidate_count > 0;

    let store_contract = BioCortexRetrievalOptInRequest {
        mode: mode.clone(),
        per_call_opt_in,
        compile_feature_enabled: cfg!(feature = "biocortex-retrieval-opt-in"),
        runtime_enabled: env_truthy(BIOCORTEX_RETRIEVAL_OPT_IN_ENABLE_ENV),
        operator_disabled: env_truthy(BIOCORTEX_RETRIEVAL_DISABLE_ENV),
        baseline_completed,
        baseline_key_count: candidate_count,
        runtime_adapter_approved: false,
        ordering_behavior_connected: false,
    }
    .evaluate()
    .response_contract(false);
    let store_contract_json = serde_json::to_value(&store_contract).unwrap_or(Value::Null);

    let mut blockers = Vec::new();
    push_string_blocker(&mut blockers, schema_ok, "execution_packet_schema_invalid");
    push_string_blocker(
        &mut blockers,
        read_only_ok,
        "execution_packet_not_read_only",
    );
    push_string_blocker(
        &mut blockers,
        execution_packet_ok,
        "execution_packet_flag_missing",
    );
    push_string_blocker(
        &mut blockers,
        preflight_ok,
        "execution_packet_preflight_failed",
    );
    push_string_blocker(
        &mut blockers,
        ordering_execution_disallowed,
        "execution_packet_allows_ordering_execution",
    );
    push_string_blocker(
        &mut blockers,
        approval_state_not_approved,
        "execution_packet_approval_state_changed",
    );
    push_string_blocker(
        &mut blockers,
        runtime_adapter_not_approved,
        "execution_packet_runtime_adapter_approved",
    );
    push_string_blocker(
        &mut blockers,
        calls_memory_search_false,
        "execution_packet_claims_memory_search",
    );
    push_string_blocker(
        &mut blockers,
        changes_order_false,
        "execution_packet_claims_order_change",
    );
    push_string_blocker(
        &mut blockers,
        ordering_connected_false,
        "execution_packet_claims_ordering_connected",
    );
    push_string_blocker(
        &mut blockers,
        raw_packet_absent,
        "raw_execution_packet_included",
    );
    push_string_blocker(&mut blockers, raw_query_absent, "raw_query_included");
    push_string_blocker(&mut blockers, raw_keys_absent, "raw_keys_included");
    push_string_blocker(&mut blockers, content_absent, "content_included");
    push_string_blocker(&mut blockers, mode_authorized, "mode_not_authorized");
    push_string_blocker(&mut blockers, baseline_completed, "baseline_not_completed");
    push_string_blocker(
        &mut blockers,
        candidate_count_matches_packet,
        "candidate_count_mismatch",
    );
    push_string_blocker(&mut blockers, query_present, "query_missing");
    push_string_blocker(&mut blockers, candidates_present, "candidates_missing");
    push_string_blocker(&mut blockers, gate_ready, "opt_in_gate_not_ready");

    let side_signal_trial_allowed = blockers.is_empty();
    let baseline = if query_present && candidates_present {
        retrieval_baseline_scores(&query, &candidates)
    } else {
        Vec::new()
    };
    let baseline_order_keys = baseline
        .iter()
        .map(|row| row.key.clone())
        .collect::<Vec<_>>();
    let baseline_order_hash = sha256_json(&json!({
        "mode": &mode,
        "baseline_keys": &baseline_order_keys,
    }));
    let query_hash = if query_present {
        sha256_json(&json!({"query": &query}))
    } else {
        sha256_json(&Value::Null)
    };

    let mut side_status = if side_signal_trial_allowed {
        "not_run".to_string()
    } else {
        "not_run_preflight_blocked".to_string()
    };
    let mut side_attempted = false;
    let mut side_row_count = 0usize;
    let mut matched_candidate_count = 0usize;
    let mut latency_ms = 0.0f64;
    let mut side_by_key = BTreeMap::new();
    let mut evidence_by_key = BTreeMap::new();

    if side_signal_trial_allowed {
        side_attempted = true;
        let started = Instant::now();
        match run_retrieval_side_signal(
            &query,
            &candidates,
            opts.expected_key.as_deref(),
            opts.checkout.as_deref(),
            timeout_ms,
        )
        .await
        {
            Ok(run) => {
                latency_ms = started.elapsed().as_secs_f64() * 1000.0;
                side_row_count = run.rows.len();
                for row in run.rows {
                    if row.query_id != "q_runtime_shadow" {
                        continue;
                    }
                    if candidates
                        .iter()
                        .any(|candidate| candidate.key == row.candidate_key)
                    {
                        side_by_key.insert(row.candidate_key.clone(), row.score);
                        if let Some(evidence) = row.evidence {
                            evidence_by_key.insert(row.candidate_key, evidence);
                        }
                    }
                }
                matched_candidate_count = side_by_key.len();
                let coverage = matched_candidate_count as f64 / candidate_count.max(1) as f64;
                side_status = if coverage >= coverage_threshold {
                    "ok".to_string()
                } else {
                    "coverage_below_threshold".to_string()
                };
            }
            Err(error) => {
                latency_ms = started.elapsed().as_secs_f64() * 1000.0;
                side_status = safe_side_signal_error_status(&error);
            }
        }
    }

    let side_signal_coverage = matched_candidate_count as f64 / candidate_count.max(1) as f64;
    let alpha = retrieval_alpha_config();
    let advisory = advisory_order_summary(
        &mode,
        &baseline,
        &side_by_key,
        &evidence_by_key,
        &alpha,
        opts.expected_key.as_deref(),
        side_status == "ok",
    );
    let fallback_reason = if !side_signal_trial_allowed {
        blockers
            .first()
            .cloned()
            .unwrap_or_else(|| "preflight_blocked".to_string())
    } else if side_status != "ok" {
        side_status.clone()
    } else {
        "ordering_behavior_not_connected".to_string()
    };

    json!({
        "schema": BIOCORTEX_RETRIEVAL_OPT_IN_RUNTIME_TRIAL_SCHEMA,
        "generated_at": now_secs(),
        "read_only": true,
        "runtime_trial": true,
        "implementation_stage": "baseline_preserving_runtime_trial",
        "authorization_scope": "opt_in_experiment",
        "purpose": "Run a protected side-signal trial for explicit candidates while returning baseline order.",
        "attempt": {
            "attempt_id": required_or_value(opts.attempt_id),
            "commit": required_or_value(opts.commit),
            "mode": mode,
            "per_call_opt_in": per_call_opt_in,
        },
        "input_contract": {
            "source_schema": packet.get("schema").cloned().unwrap_or(Value::Null),
            "requires_schema": BIOCORTEX_RETRIEVAL_OPT_IN_EXECUTION_PACKET_SCHEMA,
            "execution_packet_included": false,
            "unknown_fields_ignored": true,
            "raw_query_included": false,
            "raw_keys_included": false,
            "content_included": false,
        },
        "query_hash": query_hash,
        "baseline_order": {
            "completed": baseline_completed,
            "key_count": candidate_count,
            "hash": baseline_order_hash,
            "top_key_hash": baseline
                .first()
                .map(|row| candidate_key_hash(&row.key))
                .map(Value::String)
                .unwrap_or(Value::Null),
            "redacted_rank_rows": redacted_baseline_rank_rows(&baseline),
            "redacted_rank_rows_included": !baseline.is_empty(),
            "raw_keys_included": false,
            "raw_order_keys_included": false,
            "content_included": false,
        },
        "runtime_preflight": {
            "side_signal_trial_allowed": side_signal_trial_allowed,
            "blockers": blockers,
            "execution_packet_preflight_passed": preflight_ok,
            "gate_ready": gate_ready,
            "candidate_count_matches_packet": candidate_count_matches_packet,
            "ordering_execution_allowed": false,
        },
        "protected_adapter_contract": {
            "candidate_recall_source": "baseline_only",
            "can_add_new_candidates": false,
            "join_key": "candidate_key",
            "calls_memory_search": false,
            "writes_temp_corpus": side_attempted,
            "mutates_ab_memory": false,
            "registers_embedding_backend": false,
            "raw_query_included": false,
            "raw_keys_included": false,
            "content_included": false,
            "side_signal_raw_included": false,
        },
        "side_signal": {
            "attempted": side_attempted,
            "status": side_status,
            "timeout_ms": timeout_ms,
            "coverage_threshold": round3(coverage_threshold),
            "row_count": side_row_count,
            "matched_candidate_count": matched_candidate_count,
            "coverage": round3(side_signal_coverage),
            "latency_ms": round3(latency_ms),
            "raw_included": false,
            "checkout_path_included": false,
            "candidate_keys_included": false,
            "content_included": false,
        },
        "advisory_result": advisory,
        "returned_order": {
            "source": "baseline",
            "baseline_returned": true,
            "hash_matches_baseline": true,
            "fallback_reason": fallback_reason,
        },
        "gate": gate,
        "store_contract": store_contract_json,
        "approval_state": "not_approved",
        "runtime_adapter_approved": false,
        "approval_writes_allowed": false,
        "writes_approval": false,
        "calls_memory_search": false,
        "runs_biocortex": side_attempted,
        "registers_embedding_backend": false,
        "changes_memory_search_order": false,
        "default_search_order_change_allowed": false,
        "ordering_behavior_connected": false,
        "may_change_search_order_now": false,
        "may_implement_ordering_now": false,
        "default_calls_unchanged": true,
        "boundary": retrieval_runtime_trial_boundary_payload(side_attempted),
    })
}

fn retrieval_status_payload(status: &str, reason: &str, gates: Value) -> Value {
    json!({
        "schema": BIOCORTEX_RETRIEVAL_SHADOW_SCHEMA,
        "generated_at": now_secs(),
        "read_only": true,
        "runtime_adapter_approved": false,
        "status": status,
        "reason": reason,
        "default_search_order_changed": false,
        "boundary": retrieval_boundary_payload(),
        "gates": gates,
    })
}

pub fn biocortex_retrieval_opt_in_runtime_trial_review_packet(
    opts: BioCortexRetrievalOptInRuntimeTrialReviewPacketOptions,
) -> Value {
    let trial = opts.runtime_trial;
    let schema_ok = value_str_eq(
        trial.get("schema"),
        BIOCORTEX_RETRIEVAL_OPT_IN_RUNTIME_TRIAL_SCHEMA,
    );
    let read_only_ok = value_bool_is(trial.get("read_only"), true);
    let runtime_trial_ok = value_bool_is(trial.get("runtime_trial"), true);
    let runtime_stage_ok = value_str_eq(
        trial.get("implementation_stage"),
        "baseline_preserving_runtime_trial",
    );
    let input_packet_absent = value_bool_is(
        trial.pointer("/input_contract/execution_packet_included"),
        false,
    );
    let input_raw_query_absent =
        value_bool_is(trial.pointer("/input_contract/raw_query_included"), false);
    let input_raw_keys_absent =
        value_bool_is(trial.pointer("/input_contract/raw_keys_included"), false);
    let input_content_absent =
        value_bool_is(trial.pointer("/input_contract/content_included"), false);
    let baseline_raw_keys_absent =
        value_bool_is(trial.pointer("/baseline_order/raw_keys_included"), false);
    let baseline_content_absent =
        value_bool_is(trial.pointer("/baseline_order/content_included"), false);
    let side_signal_raw_absent = value_bool_is(trial.pointer("/side_signal/raw_included"), false);
    let side_signal_keys_absent =
        value_bool_is(trial.pointer("/side_signal/candidate_keys_included"), false);
    let side_signal_content_absent =
        value_bool_is(trial.pointer("/side_signal/content_included"), false);
    let advisory_raw_keys_absent =
        value_bool_is(trial.pointer("/advisory_result/raw_keys_included"), false);
    let advisory_content_absent =
        value_bool_is(trial.pointer("/advisory_result/content_included"), false);
    let advisory_raw_absent = value_bool_is(
        trial.pointer("/advisory_result/side_signal_raw_included"),
        false,
    );
    let returned_baseline = value_str_eq(trial.pointer("/returned_order/source"), "baseline");
    let baseline_returned = value_bool_is(trial.pointer("/returned_order/baseline_returned"), true);
    let hash_matches_baseline =
        value_bool_is(trial.pointer("/returned_order/hash_matches_baseline"), true);
    let calls_memory_search_false = value_bool_is(trial.get("calls_memory_search"), false);
    let registers_embedding_backend_false =
        value_bool_is(trial.get("registers_embedding_backend"), false);
    let changes_order_false = value_bool_is(trial.get("changes_memory_search_order"), false);
    let ordering_connected_false = value_bool_is(trial.get("ordering_behavior_connected"), false);
    let may_change_order_false = value_bool_is(trial.get("may_change_search_order_now"), false);
    let may_implement_ordering_false =
        value_bool_is(trial.get("may_implement_ordering_now"), false);
    let default_change_false =
        value_bool_is(trial.get("default_search_order_change_allowed"), false);
    let approval_state_not_approved = value_str_eq(trial.get("approval_state"), "not_approved");
    let runtime_adapter_not_approved = value_bool_is(trial.get("runtime_adapter_approved"), false);
    let approval_writes_false = value_bool_is(trial.get("approval_writes_allowed"), false);
    let writes_approval_false = value_bool_is(trial.get("writes_approval"), false);
    let boundary_calls_memory_search_false =
        value_bool_is(trial.pointer("/boundary/calls_memory_search"), false);
    let boundary_changes_order_false = value_bool_is(
        trial.pointer("/boundary/changes_memory_search_order"),
        false,
    );
    let boundary_mutates_memory_false =
        value_bool_is(trial.pointer("/boundary/mutates_ab_memory"), false);
    let side_signal_attempted = value_bool_is(trial.pointer("/side_signal/attempted"), true);
    let side_signal_ok = value_str_eq(trial.pointer("/side_signal/status"), "ok");
    let trial_allowed = value_bool_is(
        trial.pointer("/runtime_preflight/side_signal_trial_allowed"),
        true,
    );
    let preflight_blockers_empty = trial
        .pointer("/runtime_preflight/blockers")
        .and_then(Value::as_array)
        .map(Vec::is_empty)
        .unwrap_or(false);
    let advisory_not_used_for_return = value_bool_is(
        trial.pointer("/advisory_result/used_for_return_order"),
        false,
    );

    let mut violations = Vec::new();
    push_violation(
        &mut violations,
        schema_ok,
        "schema_not_runtime_trial_packet",
    );
    push_violation(&mut violations, read_only_ok, "runtime_trial_not_read_only");
    push_violation(
        &mut violations,
        runtime_trial_ok,
        "runtime_trial_flag_missing",
    );
    push_violation(
        &mut violations,
        runtime_stage_ok,
        "runtime_trial_stage_unexpected",
    );
    push_violation(
        &mut violations,
        input_packet_absent,
        "runtime_trial_packet_included",
    );
    push_violation(
        &mut violations,
        input_raw_query_absent,
        "input_raw_query_included",
    );
    push_violation(
        &mut violations,
        input_raw_keys_absent,
        "input_raw_keys_included",
    );
    push_violation(
        &mut violations,
        input_content_absent,
        "input_content_included",
    );
    push_violation(
        &mut violations,
        baseline_raw_keys_absent,
        "baseline_raw_keys_included",
    );
    push_violation(
        &mut violations,
        baseline_content_absent,
        "baseline_content_included",
    );
    push_violation(
        &mut violations,
        side_signal_raw_absent,
        "side_signal_raw_included",
    );
    push_violation(
        &mut violations,
        side_signal_keys_absent,
        "side_signal_candidate_keys_included",
    );
    push_violation(
        &mut violations,
        side_signal_content_absent,
        "side_signal_content_included",
    );
    push_violation(
        &mut violations,
        advisory_raw_keys_absent,
        "advisory_raw_keys_included",
    );
    push_violation(
        &mut violations,
        advisory_content_absent,
        "advisory_content_included",
    );
    push_violation(
        &mut violations,
        advisory_raw_absent,
        "advisory_side_signal_raw_included",
    );
    push_violation(
        &mut violations,
        returned_baseline,
        "returned_order_not_baseline",
    );
    push_violation(&mut violations, baseline_returned, "baseline_not_returned");
    push_violation(
        &mut violations,
        hash_matches_baseline,
        "returned_order_hash_not_baseline",
    );
    push_violation(
        &mut violations,
        calls_memory_search_false,
        "calls_memory_search_true_or_missing",
    );
    push_violation(
        &mut violations,
        registers_embedding_backend_false,
        "registers_embedding_backend_true_or_missing",
    );
    push_violation(
        &mut violations,
        changes_order_false,
        "changes_memory_search_order_true_or_missing",
    );
    push_violation(
        &mut violations,
        ordering_connected_false,
        "ordering_behavior_connected_true_or_missing",
    );
    push_violation(
        &mut violations,
        may_change_order_false,
        "may_change_search_order_now_true_or_missing",
    );
    push_violation(
        &mut violations,
        may_implement_ordering_false,
        "may_implement_ordering_now_true_or_missing",
    );
    push_violation(
        &mut violations,
        default_change_false,
        "default_search_order_change_allowed_true_or_missing",
    );
    push_violation(
        &mut violations,
        approval_state_not_approved,
        "approval_state_changed",
    );
    push_violation(
        &mut violations,
        runtime_adapter_not_approved,
        "runtime_adapter_approved",
    );
    push_violation(
        &mut violations,
        approval_writes_false,
        "approval_writes_allowed",
    );
    push_violation(&mut violations, writes_approval_false, "writes_approval");
    push_violation(
        &mut violations,
        boundary_calls_memory_search_false,
        "boundary_calls_memory_search",
    );
    push_violation(
        &mut violations,
        boundary_changes_order_false,
        "boundary_changes_memory_search_order",
    );
    push_violation(
        &mut violations,
        boundary_mutates_memory_false,
        "boundary_mutates_ab_memory",
    );
    push_violation(
        &mut violations,
        advisory_not_used_for_return,
        "advisory_used_for_return_order",
    );

    let review_ready_for_baseline_runtime_trial = violations.is_empty()
        && side_signal_attempted
        && side_signal_ok
        && trial_allowed
        && preflight_blockers_empty;
    let attempt = trial.get("attempt").unwrap_or(&Value::Null);
    let baseline = trial.get("baseline_order").unwrap_or(&Value::Null);
    let preflight = trial.get("runtime_preflight").unwrap_or(&Value::Null);
    let side_signal = trial.get("side_signal").unwrap_or(&Value::Null);
    let advisory = trial.get("advisory_result").unwrap_or(&Value::Null);
    let returned_order = trial.get("returned_order").unwrap_or(&Value::Null);
    let baseline_redacted_rank_rows =
        sanitized_redacted_rank_rows(baseline.get("redacted_rank_rows"), "baseline_rank");
    let advisory_redacted_rank_rows =
        sanitized_redacted_rank_rows(advisory.get("redacted_rank_rows"), "advisory_rank");

    json!({
        "schema": BIOCORTEX_RETRIEVAL_OPT_IN_RUNTIME_TRIAL_REVIEW_PACKET_SCHEMA,
        "generated_at": now_secs(),
        "read_only": true,
        "runtime_trial_consumer": true,
        "implementation_stage": "runtime_trial_review_packet_only",
        "authorization_scope": "opt_in_experiment",
        "review_scope": "baseline_preserving_runtime_trial_only",
        "purpose": "Review packet derived from a runtime trial; this is not runtime influence approval.",
        "input_contract": {
            "source_schema": trial.get("schema").cloned().unwrap_or(Value::Null),
            "requires_schema": BIOCORTEX_RETRIEVAL_OPT_IN_RUNTIME_TRIAL_SCHEMA,
            "runtime_trial_packet_included": false,
            "unknown_fields_ignored": true,
            "raw_query_included": false,
            "raw_keys_included": false,
            "content_included": false,
            "side_signal_raw_included": false,
        },
        "review_target": {
            "mode": attempt.get("mode").cloned().unwrap_or(Value::Null),
            "per_call_opt_in": attempt.get("per_call_opt_in").cloned().unwrap_or(Value::Null),
            "runtime_trial_attempt_id": attempt.get("attempt_id").cloned().unwrap_or(Value::Null),
            "runtime_trial_commit": attempt.get("commit").cloned().unwrap_or(Value::Null),
            "reviewer": required_or_value(opts.reviewer),
            "commit": required_or_value(opts.commit),
            "forum_post_id": required_or_value(opts.forum_post_id),
            "memory_key": required_or_value(opts.memory_key),
        },
        "runtime_trial_summary": {
            "query_hash": trial.get("query_hash").cloned().unwrap_or(Value::Null),
            "baseline_order": {
                "completed": baseline.get("completed").cloned().unwrap_or(Value::Null),
                "key_count": baseline.get("key_count").cloned().unwrap_or(Value::Null),
                "hash": baseline.get("hash").cloned().unwrap_or(Value::Null),
                "top_key_hash": baseline.get("top_key_hash").cloned().unwrap_or(Value::Null),
                "redacted_rank_rows": redacted_rank_rows_value(
                    &baseline_redacted_rank_rows,
                    "baseline_rank"
                ),
                "redacted_rank_rows_included": !baseline_redacted_rank_rows.is_empty(),
                "raw_keys_included": false,
                "raw_order_keys_included": false,
                "content_included": false,
            },
            "runtime_preflight": {
                "side_signal_trial_allowed": preflight
                    .get("side_signal_trial_allowed")
                    .cloned()
                    .unwrap_or(Value::Null),
                "blocker_count": preflight
                    .get("blockers")
                    .and_then(Value::as_array)
                    .map(|items| json!(items.len()))
                    .unwrap_or(Value::Null),
                "execution_packet_preflight_passed": preflight
                    .get("execution_packet_preflight_passed")
                    .cloned()
                    .unwrap_or(Value::Null),
                "gate_ready": preflight.get("gate_ready").cloned().unwrap_or(Value::Null),
                "candidate_count_matches_packet": preflight
                    .get("candidate_count_matches_packet")
                    .cloned()
                    .unwrap_or(Value::Null),
                "ordering_execution_allowed": preflight
                    .get("ordering_execution_allowed")
                    .cloned()
                    .unwrap_or(Value::Null),
            },
            "side_signal": {
                "attempted": side_signal.get("attempted").cloned().unwrap_or(Value::Null),
                "status": side_signal.get("status").cloned().unwrap_or(Value::Null),
                "timeout_ms": side_signal.get("timeout_ms").cloned().unwrap_or(Value::Null),
                "coverage_threshold": side_signal
                    .get("coverage_threshold")
                    .cloned()
                    .unwrap_or(Value::Null),
                "row_count": side_signal.get("row_count").cloned().unwrap_or(Value::Null),
                "matched_candidate_count": side_signal
                    .get("matched_candidate_count")
                    .cloned()
                    .unwrap_or(Value::Null),
                "coverage": side_signal.get("coverage").cloned().unwrap_or(Value::Null),
                "latency_ms": side_signal.get("latency_ms").cloned().unwrap_or(Value::Null),
                "raw_included": false,
                "candidate_keys_included": false,
                "content_included": false,
            },
            "advisory_result": {
                "available": advisory.get("available").cloned().unwrap_or(Value::Null),
                "used_for_return_order": advisory
                    .get("used_for_return_order")
                    .cloned()
                    .unwrap_or(Value::Null),
                "order_hash": advisory.get("order_hash").cloned().unwrap_or(Value::Null),
                "top_key_hash": advisory.get("top_key_hash").cloned().unwrap_or(Value::Null),
                "matched_side_signal_count": advisory
                    .get("matched_side_signal_count")
                    .cloned()
                    .unwrap_or(Value::Null),
                "evidence_count": advisory.get("evidence_count").cloned().unwrap_or(Value::Null),
                "expected": advisory.get("expected").cloned().unwrap_or(Value::Null),
                "redacted_rank_rows": redacted_rank_rows_value(
                    &advisory_redacted_rank_rows,
                    "advisory_rank"
                ),
                "redacted_rank_rows_included": !advisory_redacted_rank_rows.is_empty(),
                "raw_keys_included": false,
                "raw_order_keys_included": false,
                "content_included": false,
                "side_signal_raw_included": false,
            },
            "returned_order": {
                "source": returned_order.get("source").cloned().unwrap_or(Value::Null),
                "baseline_returned": returned_order
                    .get("baseline_returned")
                    .cloned()
                    .unwrap_or(Value::Null),
                "hash_matches_baseline": returned_order
                    .get("hash_matches_baseline")
                    .cloned()
                    .unwrap_or(Value::Null),
                "fallback_reason": returned_order
                    .get("fallback_reason")
                    .cloned()
                    .unwrap_or(Value::Null),
            },
        },
        "boundary_check": {
            "review_ready_for_baseline_runtime_trial": review_ready_for_baseline_runtime_trial,
            "violations": violations,
            "schema_ok": schema_ok,
            "read_only_ok": read_only_ok,
            "runtime_trial_ok": runtime_trial_ok,
            "side_signal_attempted": side_signal_attempted,
            "side_signal_ok": side_signal_ok,
            "trial_allowed": trial_allowed,
            "preflight_blockers_empty": preflight_blockers_empty,
            "returned_baseline": returned_baseline,
            "baseline_returned": baseline_returned,
            "calls_memory_search_false": calls_memory_search_false,
            "registers_embedding_backend_false": registers_embedding_backend_false,
            "changes_order_false": changes_order_false,
            "ordering_connected_false": ordering_connected_false,
            "advisory_not_used_for_return": advisory_not_used_for_return,
        },
        "required_human_checks": [
            "Confirm the runtime trial packet was generated from the reviewed commit.",
            "Confirm only explicit baseline candidates were used and BioCortex was not a recall source.",
            "Confirm the side-signal adapter ran only under opt-in gates.",
            "Confirm returned order remained baseline.",
            "Confirm no raw query, memory keys, memory contents, or raw side-signal payloads are present.",
            "Confirm any later ordering implementation has a separate review and authorization record."
        ],
        "approval_state": "not_approved",
        "runtime_adapter_approved": false,
        "approval_writes_allowed": false,
        "writes_approval": false,
        "calls_memory_search": false,
        "runs_biocortex": false,
        "registers_embedding_backend": false,
        "changes_memory_search_order": false,
        "default_search_order_change_allowed": false,
        "ordering_behavior_connected": false,
        "may_change_search_order_now": false,
        "may_implement_ordering_now": false,
        "default_calls_unchanged": true,
        "boundary": retrieval_runtime_trial_review_boundary_payload(),
    })
}

pub fn biocortex_retrieval_opt_in_order_diff_packet(
    opts: BioCortexRetrievalOptInOrderDiffPacketOptions,
) -> Value {
    let source = opts.source_packet;
    let schema = source.get("schema").and_then(Value::as_str).unwrap_or("");
    let source_is_runtime_trial = schema == BIOCORTEX_RETRIEVAL_OPT_IN_RUNTIME_TRIAL_SCHEMA;
    let source_is_runtime_trial_review =
        schema == BIOCORTEX_RETRIEVAL_OPT_IN_RUNTIME_TRIAL_REVIEW_PACKET_SCHEMA;
    let schema_ok = source_is_runtime_trial || source_is_runtime_trial_review;
    let read_only_ok = value_bool_is(source.get("read_only"), true);
    let null = Value::Null;
    let summary = if source_is_runtime_trial_review {
        source.get("runtime_trial_summary").unwrap_or(&null)
    } else {
        &source
    };
    let input_contract = source.get("input_contract").unwrap_or(&null);
    let baseline = summary.get("baseline_order").unwrap_or(&null);
    let side_signal = summary.get("side_signal").unwrap_or(&null);
    let advisory = summary.get("advisory_result").unwrap_or(&null);
    let returned_order = summary.get("returned_order").unwrap_or(&null);

    let source_packet_absent = if source_is_runtime_trial_review {
        value_bool_is(input_contract.get("runtime_trial_packet_included"), false)
    } else {
        value_bool_is(input_contract.get("execution_packet_included"), false)
    };
    let input_raw_query_absent = value_bool_is(input_contract.get("raw_query_included"), false);
    let input_raw_keys_absent = value_bool_is(input_contract.get("raw_keys_included"), false);
    let input_content_absent = value_bool_is(input_contract.get("content_included"), false);
    let input_side_signal_raw_absent =
        !value_bool_is(input_contract.get("side_signal_raw_included"), true);
    let baseline_raw_keys_absent = value_bool_is(baseline.get("raw_keys_included"), false);
    let baseline_content_absent = value_bool_is(baseline.get("content_included"), false);
    let side_signal_raw_absent = value_bool_is(side_signal.get("raw_included"), false);
    let side_signal_keys_absent = value_bool_is(side_signal.get("candidate_keys_included"), false);
    let side_signal_content_absent = value_bool_is(side_signal.get("content_included"), false);
    let advisory_available = value_bool_is(advisory.get("available"), true);
    let advisory_not_used_for_return = value_bool_is(advisory.get("used_for_return_order"), false);
    let advisory_raw_keys_absent = value_bool_is(advisory.get("raw_keys_included"), false);
    let advisory_content_absent = value_bool_is(advisory.get("content_included"), false);
    let advisory_raw_absent = value_bool_is(advisory.get("side_signal_raw_included"), false);
    let returned_baseline = value_str_eq(returned_order.get("source"), "baseline");
    let baseline_returned = value_bool_is(returned_order.get("baseline_returned"), true);
    let hash_matches_baseline = value_bool_is(returned_order.get("hash_matches_baseline"), true);
    let calls_memory_search_false = value_bool_is(source.get("calls_memory_search"), false);
    let registers_embedding_backend_false =
        value_bool_is(source.get("registers_embedding_backend"), false);
    let changes_order_false = value_bool_is(source.get("changes_memory_search_order"), false);
    let ordering_connected_false = value_bool_is(source.get("ordering_behavior_connected"), false);
    let may_change_order_false = value_bool_is(source.get("may_change_search_order_now"), false);
    let may_implement_ordering_false =
        value_bool_is(source.get("may_implement_ordering_now"), false);
    let default_change_false =
        value_bool_is(source.get("default_search_order_change_allowed"), false);
    let approval_state_not_approved = value_str_eq(source.get("approval_state"), "not_approved");
    let runtime_adapter_not_approved = value_bool_is(source.get("runtime_adapter_approved"), false);
    let approval_writes_false = value_bool_is(source.get("approval_writes_allowed"), false);
    let writes_approval_false = value_bool_is(source.get("writes_approval"), false);
    let source_review_ready = if source_is_runtime_trial_review {
        value_bool_is(
            source.pointer("/boundary_check/review_ready_for_baseline_runtime_trial"),
            true,
        )
    } else {
        value_bool_is(
            summary.pointer("/runtime_preflight/side_signal_trial_allowed"),
            true,
        ) && value_str_eq(side_signal.get("status"), "ok")
    };

    let baseline_hash = baseline.get("hash").and_then(Value::as_str);
    let advisory_hash = advisory.get("order_hash").and_then(Value::as_str);
    let order_hashes_comparable = baseline_hash.is_some() && advisory_hash.is_some();
    let order_hash_changed = order_hashes_comparable.then(|| baseline_hash != advisory_hash);
    let baseline_top_hash = baseline.get("top_key_hash").and_then(Value::as_str);
    let advisory_top_hash = advisory.get("top_key_hash").and_then(Value::as_str);
    let top_hashes_comparable = baseline_top_hash.is_some() && advisory_top_hash.is_some();
    let top_key_changed = top_hashes_comparable.then(|| baseline_top_hash != advisory_top_hash);

    let expected = advisory.get("expected").unwrap_or(&null);
    let expected_baseline_rank = expected.get("baseline_rank").and_then(Value::as_i64);
    let expected_advisory_rank = expected.get("advisory_rank").and_then(Value::as_i64);
    let expected_rank_delta = match (expected_baseline_rank, expected_advisory_rank) {
        (Some(baseline_rank), Some(advisory_rank)) => Some(advisory_rank - baseline_rank),
        _ => None,
    };
    let expected_rank_direction = match expected_rank_delta {
        Some(delta) if delta < 0 => "improved",
        Some(delta) if delta > 0 => "regressed",
        Some(_) => "unchanged",
        None => "unknown",
    };

    let mut violations = Vec::new();
    push_violation(&mut violations, schema_ok, "source_schema_not_supported");
    push_violation(&mut violations, read_only_ok, "source_not_read_only");
    push_violation(
        &mut violations,
        source_packet_absent,
        "source_packet_included",
    );
    push_violation(
        &mut violations,
        input_raw_query_absent,
        "input_raw_query_included",
    );
    push_violation(
        &mut violations,
        input_raw_keys_absent,
        "input_raw_keys_included",
    );
    push_violation(
        &mut violations,
        input_content_absent,
        "input_content_included",
    );
    push_violation(
        &mut violations,
        input_side_signal_raw_absent,
        "input_side_signal_raw_included",
    );
    push_violation(
        &mut violations,
        baseline_raw_keys_absent,
        "baseline_raw_keys_included",
    );
    push_violation(
        &mut violations,
        baseline_content_absent,
        "baseline_content_included",
    );
    push_violation(
        &mut violations,
        side_signal_raw_absent,
        "side_signal_raw_included",
    );
    push_violation(
        &mut violations,
        side_signal_keys_absent,
        "side_signal_candidate_keys_included",
    );
    push_violation(
        &mut violations,
        side_signal_content_absent,
        "side_signal_content_included",
    );
    push_violation(
        &mut violations,
        advisory_available,
        "advisory_order_unavailable",
    );
    push_violation(
        &mut violations,
        advisory_not_used_for_return,
        "advisory_used_for_return_order",
    );
    push_violation(
        &mut violations,
        advisory_raw_keys_absent,
        "advisory_raw_keys_included",
    );
    push_violation(
        &mut violations,
        advisory_content_absent,
        "advisory_content_included",
    );
    push_violation(
        &mut violations,
        advisory_raw_absent,
        "advisory_side_signal_raw_included",
    );
    push_violation(
        &mut violations,
        returned_baseline,
        "returned_order_not_baseline",
    );
    push_violation(&mut violations, baseline_returned, "baseline_not_returned");
    push_violation(
        &mut violations,
        hash_matches_baseline,
        "returned_order_hash_not_baseline",
    );
    push_violation(
        &mut violations,
        calls_memory_search_false,
        "calls_memory_search_true_or_missing",
    );
    push_violation(
        &mut violations,
        registers_embedding_backend_false,
        "registers_embedding_backend_true_or_missing",
    );
    push_violation(
        &mut violations,
        changes_order_false,
        "changes_memory_search_order_true_or_missing",
    );
    push_violation(
        &mut violations,
        ordering_connected_false,
        "ordering_behavior_connected_true_or_missing",
    );
    push_violation(
        &mut violations,
        may_change_order_false,
        "may_change_search_order_now_true_or_missing",
    );
    push_violation(
        &mut violations,
        may_implement_ordering_false,
        "may_implement_ordering_now_true_or_missing",
    );
    push_violation(
        &mut violations,
        default_change_false,
        "default_search_order_change_allowed_true_or_missing",
    );
    push_violation(
        &mut violations,
        approval_state_not_approved,
        "approval_state_changed",
    );
    push_violation(
        &mut violations,
        runtime_adapter_not_approved,
        "runtime_adapter_approved",
    );
    push_violation(
        &mut violations,
        approval_writes_false,
        "approval_writes_allowed",
    );
    push_violation(&mut violations, writes_approval_false, "writes_approval");
    push_violation(
        &mut violations,
        source_review_ready,
        "source_review_not_ready",
    );
    push_violation(
        &mut violations,
        order_hashes_comparable,
        "order_hashes_not_comparable",
    );
    push_violation(
        &mut violations,
        top_hashes_comparable,
        "top_key_hashes_not_comparable",
    );

    let diff_ready = violations.is_empty();
    let source_runs_biocortex = source.get("runs_biocortex").cloned().unwrap_or(Value::Null);

    json!({
        "schema": BIOCORTEX_RETRIEVAL_OPT_IN_ORDER_DIFF_PACKET_SCHEMA,
        "generated_at": now_secs(),
        "read_only": true,
        "order_diff_packet": true,
        "source_packet_consumer": true,
        "implementation_stage": "order_diff_review_packet_only",
        "authorization_scope": "opt_in_experiment",
        "comparison_scope": "baseline_vs_advisory_hash_only",
        "purpose": "Compare baseline order against the BioCortex advisory order without changing returned order.",
        "input_contract": {
            "source_schema": source.get("schema").cloned().unwrap_or(Value::Null),
            "accepted_source_schemas": [
                BIOCORTEX_RETRIEVAL_OPT_IN_RUNTIME_TRIAL_SCHEMA,
                BIOCORTEX_RETRIEVAL_OPT_IN_RUNTIME_TRIAL_REVIEW_PACKET_SCHEMA
            ],
            "source_packet_included": false,
            "unknown_fields_ignored": true,
            "raw_query_included": false,
            "raw_keys_included": false,
            "content_included": false,
            "side_signal_raw_included": false,
        },
        "review_target": {
            "source_kind": if source_is_runtime_trial_review {
                "runtime_trial_review_packet"
            } else if source_is_runtime_trial {
                "runtime_trial"
            } else {
                "unsupported"
            },
            "reviewer": required_or_value(opts.reviewer),
            "commit": required_or_value(opts.commit),
            "forum_post_id": required_or_value(opts.forum_post_id),
            "memory_key": required_or_value(opts.memory_key),
        },
        "order_comparison": {
            "baseline_order": {
                "key_count": baseline.get("key_count").cloned().unwrap_or(Value::Null),
                "hash": baseline.get("hash").cloned().unwrap_or(Value::Null),
                "top_key_hash": baseline.get("top_key_hash").cloned().unwrap_or(Value::Null),
                "raw_keys_included": false,
                "content_included": false,
            },
            "advisory_order": {
                "available": advisory.get("available").cloned().unwrap_or(Value::Null),
                "hash": advisory.get("order_hash").cloned().unwrap_or(Value::Null),
                "top_key_hash": advisory.get("top_key_hash").cloned().unwrap_or(Value::Null),
                "used_for_return_order": advisory
                    .get("used_for_return_order")
                    .cloned()
                    .unwrap_or(Value::Null),
                "matched_side_signal_count": advisory
                    .get("matched_side_signal_count")
                    .cloned()
                    .unwrap_or(Value::Null),
                "evidence_count": advisory.get("evidence_count").cloned().unwrap_or(Value::Null),
                "raw_keys_included": false,
                "content_included": false,
                "side_signal_raw_included": false,
            },
            "hash_diff": {
                "order_hashes_comparable": order_hashes_comparable,
                "order_hash_changed": order_hash_changed.map(Value::Bool).unwrap_or(Value::Null),
                "top_key_hashes_comparable": top_hashes_comparable,
                "top_key_changed": top_key_changed.map(Value::Bool).unwrap_or(Value::Null),
            },
            "expected_key_rank": {
                "key_hash": expected.get("key_hash").cloned().unwrap_or(Value::Null),
                "baseline_rank": expected.get("baseline_rank").cloned().unwrap_or(Value::Null),
                "advisory_rank": expected.get("advisory_rank").cloned().unwrap_or(Value::Null),
                "rank_delta_advisory_minus_baseline": expected_rank_delta
                    .map(|delta| json!(delta))
                    .unwrap_or(Value::Null),
                "direction": expected_rank_direction,
                "regressed": expected.get("regressed").cloned().unwrap_or(Value::Null),
            },
            "returned_order": {
                "source": returned_order.get("source").cloned().unwrap_or(Value::Null),
                "baseline_returned": returned_order
                    .get("baseline_returned")
                    .cloned()
                    .unwrap_or(Value::Null),
                "hash_matches_baseline": returned_order
                    .get("hash_matches_baseline")
                    .cloned()
                    .unwrap_or(Value::Null),
                "actual_return_order_changed": false,
            },
            "unavailable_metrics": {
                "top_k_overlap": "not_computed_no_raw_order_keys",
                "rank_delta_distribution": "not_computed_no_raw_order_keys",
                "per_key_movements": "not_computed_no_raw_order_keys",
            },
        },
        "boundary_check": {
            "diff_ready": diff_ready,
            "violations": violations,
            "source_schema_ok": schema_ok,
            "read_only_ok": read_only_ok,
            "source_review_ready": source_review_ready,
            "advisory_available": advisory_available,
            "advisory_not_used_for_return": advisory_not_used_for_return,
            "returned_baseline": returned_baseline,
            "baseline_returned": baseline_returned,
            "order_hashes_comparable": order_hashes_comparable,
            "top_key_hashes_comparable": top_hashes_comparable,
            "calls_memory_search_false": calls_memory_search_false,
            "changes_order_false": changes_order_false,
            "ordering_connected_false": ordering_connected_false,
        },
        "source_execution_summary": {
            "source_runs_biocortex": source_runs_biocortex,
            "order_diff_packet_runs_biocortex": false,
            "order_diff_packet_calls_memory_search": false,
        },
        "required_human_checks": [
            "Confirm this packet compares advisory order only and did not change returned order.",
            "Confirm hash changes are acceptable evidence without raw keys.",
            "Confirm top-k overlap and per-key movement are intentionally unavailable unless a separate redacted-order artifact is approved.",
            "Confirm any future ordering behavior has separate authorization."
        ],
        "approval_state": "not_approved",
        "runtime_adapter_approved": false,
        "approval_writes_allowed": false,
        "writes_approval": false,
        "calls_memory_search": false,
        "runs_biocortex": false,
        "registers_embedding_backend": false,
        "changes_memory_search_order": false,
        "default_search_order_change_allowed": false,
        "ordering_behavior_connected": false,
        "may_change_search_order_now": false,
        "may_implement_ordering_now": false,
        "default_calls_unchanged": true,
        "boundary": retrieval_order_diff_boundary_payload(),
    })
}

pub fn biocortex_retrieval_opt_in_redacted_order_artifact(
    opts: BioCortexRetrievalOptInRedactedOrderArtifactOptions,
) -> Value {
    let source = opts.source_packet;
    let schema = source.get("schema").and_then(Value::as_str).unwrap_or("");
    let source_is_runtime_trial = schema == BIOCORTEX_RETRIEVAL_OPT_IN_RUNTIME_TRIAL_SCHEMA;
    let source_is_runtime_trial_review =
        schema == BIOCORTEX_RETRIEVAL_OPT_IN_RUNTIME_TRIAL_REVIEW_PACKET_SCHEMA;
    let schema_ok = source_is_runtime_trial || source_is_runtime_trial_review;
    let source_schema = if schema_ok {
        Value::String(schema.to_string())
    } else {
        Value::String("unsupported".to_string())
    };
    let read_only_ok = value_bool_is(source.get("read_only"), true);
    let null = Value::Null;
    let summary = if source_is_runtime_trial_review {
        source.get("runtime_trial_summary").unwrap_or(&null)
    } else {
        &source
    };
    let input_contract = source.get("input_contract").unwrap_or(&null);
    let baseline = summary.get("baseline_order").unwrap_or(&null);
    let side_signal = summary.get("side_signal").unwrap_or(&null);
    let advisory = summary.get("advisory_result").unwrap_or(&null);
    let returned_order = summary.get("returned_order").unwrap_or(&null);

    let baseline_redacted_rank_rows =
        sanitized_redacted_rank_rows(baseline.get("redacted_rank_rows"), "baseline_rank");
    let advisory_redacted_rank_rows =
        sanitized_redacted_rank_rows(advisory.get("redacted_rank_rows"), "advisory_rank");
    let baseline_rows_present = !baseline_redacted_rank_rows.is_empty();
    let advisory_rows_present = !advisory_redacted_rank_rows.is_empty();
    let baseline_duplicate_hashes =
        redacted_rank_rows_have_duplicate_hash(&baseline_redacted_rank_rows);
    let advisory_duplicate_hashes =
        redacted_rank_rows_have_duplicate_hash(&advisory_redacted_rank_rows);
    let redacted_rows_comparable = baseline_rows_present
        && advisory_rows_present
        && !baseline_duplicate_hashes
        && !advisory_duplicate_hashes;

    let source_packet_absent = if source_is_runtime_trial_review {
        value_bool_is(input_contract.get("runtime_trial_packet_included"), false)
    } else {
        value_bool_is(input_contract.get("execution_packet_included"), false)
    };
    let input_raw_query_absent = value_bool_is(input_contract.get("raw_query_included"), false);
    let input_raw_keys_absent = value_bool_is(input_contract.get("raw_keys_included"), false);
    let input_content_absent = value_bool_is(input_contract.get("content_included"), false);
    let input_side_signal_raw_absent =
        !value_bool_is(input_contract.get("side_signal_raw_included"), true);
    let baseline_raw_keys_absent = value_bool_is(baseline.get("raw_keys_included"), false);
    let baseline_raw_order_keys_absent =
        !value_bool_is(baseline.get("raw_order_keys_included"), true);
    let baseline_content_absent = value_bool_is(baseline.get("content_included"), false);
    let side_signal_raw_absent = value_bool_is(side_signal.get("raw_included"), false);
    let side_signal_keys_absent = value_bool_is(side_signal.get("candidate_keys_included"), false);
    let side_signal_content_absent = value_bool_is(side_signal.get("content_included"), false);
    let advisory_available = value_bool_is(advisory.get("available"), true);
    let advisory_not_used_for_return = value_bool_is(advisory.get("used_for_return_order"), false);
    let advisory_raw_keys_absent = value_bool_is(advisory.get("raw_keys_included"), false);
    let advisory_raw_order_keys_absent =
        !value_bool_is(advisory.get("raw_order_keys_included"), true);
    let advisory_content_absent = value_bool_is(advisory.get("content_included"), false);
    let advisory_raw_absent = value_bool_is(advisory.get("side_signal_raw_included"), false);
    let returned_baseline = value_str_eq(returned_order.get("source"), "baseline");
    let baseline_returned = value_bool_is(returned_order.get("baseline_returned"), true);
    let hash_matches_baseline = value_bool_is(returned_order.get("hash_matches_baseline"), true);
    let calls_memory_search_false = value_bool_is(source.get("calls_memory_search"), false);
    let registers_embedding_backend_false =
        value_bool_is(source.get("registers_embedding_backend"), false);
    let changes_order_false = value_bool_is(source.get("changes_memory_search_order"), false);
    let ordering_connected_false = value_bool_is(source.get("ordering_behavior_connected"), false);
    let may_change_order_false = value_bool_is(source.get("may_change_search_order_now"), false);
    let may_implement_ordering_false =
        value_bool_is(source.get("may_implement_ordering_now"), false);
    let default_change_false =
        value_bool_is(source.get("default_search_order_change_allowed"), false);
    let approval_state_not_approved = value_str_eq(source.get("approval_state"), "not_approved");
    let runtime_adapter_not_approved = value_bool_is(source.get("runtime_adapter_approved"), false);
    let approval_writes_false = value_bool_is(source.get("approval_writes_allowed"), false);
    let writes_approval_false = value_bool_is(source.get("writes_approval"), false);
    let source_review_ready = if source_is_runtime_trial_review {
        value_bool_is(
            source.pointer("/boundary_check/review_ready_for_baseline_runtime_trial"),
            true,
        )
    } else {
        value_bool_is(
            summary.pointer("/runtime_preflight/side_signal_trial_allowed"),
            true,
        ) && value_str_eq(side_signal.get("status"), "ok")
    };

    let mut violations = Vec::new();
    push_violation(&mut violations, schema_ok, "source_schema_not_supported");
    push_violation(&mut violations, read_only_ok, "source_not_read_only");
    push_violation(
        &mut violations,
        source_packet_absent,
        "source_packet_included",
    );
    push_violation(
        &mut violations,
        input_raw_query_absent,
        "input_raw_query_included",
    );
    push_violation(
        &mut violations,
        input_raw_keys_absent,
        "input_raw_keys_included",
    );
    push_violation(
        &mut violations,
        input_content_absent,
        "input_content_included",
    );
    push_violation(
        &mut violations,
        input_side_signal_raw_absent,
        "input_side_signal_raw_included",
    );
    push_violation(
        &mut violations,
        baseline_raw_keys_absent,
        "baseline_raw_keys_included",
    );
    push_violation(
        &mut violations,
        baseline_raw_order_keys_absent,
        "baseline_raw_order_keys_included",
    );
    push_violation(
        &mut violations,
        baseline_content_absent,
        "baseline_content_included",
    );
    push_violation(
        &mut violations,
        side_signal_raw_absent,
        "side_signal_raw_included",
    );
    push_violation(
        &mut violations,
        side_signal_keys_absent,
        "side_signal_candidate_keys_included",
    );
    push_violation(
        &mut violations,
        side_signal_content_absent,
        "side_signal_content_included",
    );
    push_violation(
        &mut violations,
        advisory_available,
        "advisory_order_unavailable",
    );
    push_violation(
        &mut violations,
        advisory_not_used_for_return,
        "advisory_used_for_return_order",
    );
    push_violation(
        &mut violations,
        advisory_raw_keys_absent,
        "advisory_raw_keys_included",
    );
    push_violation(
        &mut violations,
        advisory_raw_order_keys_absent,
        "advisory_raw_order_keys_included",
    );
    push_violation(
        &mut violations,
        advisory_content_absent,
        "advisory_content_included",
    );
    push_violation(
        &mut violations,
        advisory_raw_absent,
        "advisory_side_signal_raw_included",
    );
    push_violation(
        &mut violations,
        returned_baseline,
        "returned_order_not_baseline",
    );
    push_violation(&mut violations, baseline_returned, "baseline_not_returned");
    push_violation(
        &mut violations,
        hash_matches_baseline,
        "returned_order_hash_not_baseline",
    );
    push_violation(
        &mut violations,
        calls_memory_search_false,
        "calls_memory_search_true_or_missing",
    );
    push_violation(
        &mut violations,
        registers_embedding_backend_false,
        "registers_embedding_backend_true_or_missing",
    );
    push_violation(
        &mut violations,
        changes_order_false,
        "changes_memory_search_order_true_or_missing",
    );
    push_violation(
        &mut violations,
        ordering_connected_false,
        "ordering_behavior_connected_true_or_missing",
    );
    push_violation(
        &mut violations,
        may_change_order_false,
        "may_change_search_order_now_true_or_missing",
    );
    push_violation(
        &mut violations,
        may_implement_ordering_false,
        "may_implement_ordering_now_true_or_missing",
    );
    push_violation(
        &mut violations,
        default_change_false,
        "default_search_order_change_allowed_true_or_missing",
    );
    push_violation(
        &mut violations,
        approval_state_not_approved,
        "approval_state_changed",
    );
    push_violation(
        &mut violations,
        runtime_adapter_not_approved,
        "runtime_adapter_approved",
    );
    push_violation(
        &mut violations,
        approval_writes_false,
        "approval_writes_allowed",
    );
    push_violation(&mut violations, writes_approval_false, "writes_approval");
    push_violation(
        &mut violations,
        source_review_ready,
        "source_review_not_ready",
    );
    push_violation(
        &mut violations,
        baseline_rows_present,
        "baseline_redacted_rank_rows_missing",
    );
    push_violation(
        &mut violations,
        advisory_rows_present,
        "advisory_redacted_rank_rows_missing",
    );
    push_violation(
        &mut violations,
        !baseline_duplicate_hashes,
        "baseline_redacted_rank_rows_duplicate_key_hash",
    );
    push_violation(
        &mut violations,
        !advisory_duplicate_hashes,
        "advisory_redacted_rank_rows_duplicate_key_hash",
    );

    let artifact_ready = violations.is_empty();
    let top_k_overlap =
        redacted_top_k_overlap_value(&baseline_redacted_rank_rows, &advisory_redacted_rank_rows);
    let (rank_delta_distribution, per_key_movements) =
        redacted_rank_movement_values(&baseline_redacted_rank_rows, &advisory_redacted_rank_rows);
    let source_runs_biocortex = source.get("runs_biocortex").cloned().unwrap_or(Value::Null);

    json!({
        "schema": BIOCORTEX_RETRIEVAL_OPT_IN_REDACTED_ORDER_ARTIFACT_SCHEMA,
        "generated_at": now_secs(),
        "read_only": true,
        "redacted_order_artifact": true,
        "source_packet_consumer": true,
        "implementation_stage": "redacted_order_review_artifact_only",
        "authorization_scope": "opt_in_experiment",
        "comparison_scope": "baseline_vs_advisory_redacted_rank_rows",
        "purpose": "Compute top-k overlap and per-key rank movement from redacted order rows without changing returned order.",
        "input_contract": {
            "source_schema": source_schema,
            "accepted_source_schemas": [
                BIOCORTEX_RETRIEVAL_OPT_IN_RUNTIME_TRIAL_SCHEMA,
                BIOCORTEX_RETRIEVAL_OPT_IN_RUNTIME_TRIAL_REVIEW_PACKET_SCHEMA
            ],
            "source_packet_included": false,
            "unknown_fields_ignored": true,
            "raw_query_included": false,
            "raw_keys_included": false,
            "raw_order_keys_included": false,
            "content_included": false,
            "side_signal_raw_included": false,
            "hashes_included": true,
        },
        "review_target": {
            "source_kind": if source_is_runtime_trial_review {
                "runtime_trial_review_packet"
            } else if source_is_runtime_trial {
                "runtime_trial"
            } else {
                "unsupported"
            },
            "reviewer": required_or_value(opts.reviewer),
            "commit": required_or_value(opts.commit),
            "forum_post_id": required_or_value(opts.forum_post_id),
            "memory_key": required_or_value(opts.memory_key),
        },
        "redacted_order_comparison": {
            "baseline_order": {
                "key_count": baseline.get("key_count").cloned().unwrap_or(Value::Null),
                "hash": baseline.get("hash").cloned().unwrap_or(Value::Null),
                "top_key_hash": baseline.get("top_key_hash").cloned().unwrap_or(Value::Null),
                "rank_rows": redacted_rank_rows_value(
                    &baseline_redacted_rank_rows,
                    "baseline_rank"
                ),
                "redacted_rank_rows_included": baseline_rows_present,
                "raw_keys_included": false,
                "raw_order_keys_included": false,
                "content_included": false,
            },
            "advisory_order": {
                "available": advisory.get("available").cloned().unwrap_or(Value::Null),
                "hash": advisory.get("order_hash").cloned().unwrap_or(Value::Null),
                "top_key_hash": advisory.get("top_key_hash").cloned().unwrap_or(Value::Null),
                "used_for_return_order": advisory
                    .get("used_for_return_order")
                    .cloned()
                    .unwrap_or(Value::Null),
                "matched_side_signal_count": advisory
                    .get("matched_side_signal_count")
                    .cloned()
                    .unwrap_or(Value::Null),
                "evidence_count": advisory.get("evidence_count").cloned().unwrap_or(Value::Null),
                "rank_rows": redacted_rank_rows_value(
                    &advisory_redacted_rank_rows,
                    "advisory_rank"
                ),
                "redacted_rank_rows_included": advisory_rows_present,
                "raw_keys_included": false,
                "raw_order_keys_included": false,
                "content_included": false,
                "side_signal_raw_included": false,
            },
            "top_k_overlap": top_k_overlap,
            "rank_delta_distribution": rank_delta_distribution,
            "per_key_movements": per_key_movements,
            "returned_order": {
                "source": returned_order.get("source").cloned().unwrap_or(Value::Null),
                "baseline_returned": returned_order
                    .get("baseline_returned")
                    .cloned()
                    .unwrap_or(Value::Null),
                "hash_matches_baseline": returned_order
                    .get("hash_matches_baseline")
                    .cloned()
                    .unwrap_or(Value::Null),
                "actual_return_order_changed": false,
            },
        },
        "boundary_check": {
            "artifact_ready": artifact_ready,
            "violations": violations,
            "source_schema_ok": schema_ok,
            "read_only_ok": read_only_ok,
            "source_review_ready": source_review_ready,
            "advisory_available": advisory_available,
            "advisory_not_used_for_return": advisory_not_used_for_return,
            "returned_baseline": returned_baseline,
            "baseline_returned": baseline_returned,
            "redacted_rows_comparable": redacted_rows_comparable,
            "baseline_rows_present": baseline_rows_present,
            "advisory_rows_present": advisory_rows_present,
            "baseline_duplicate_hashes": baseline_duplicate_hashes,
            "advisory_duplicate_hashes": advisory_duplicate_hashes,
            "calls_memory_search_false": calls_memory_search_false,
            "changes_order_false": changes_order_false,
            "ordering_connected_false": ordering_connected_false,
        },
        "source_execution_summary": {
            "source_runs_biocortex": source_runs_biocortex,
            "redacted_order_artifact_runs_biocortex": false,
            "redacted_order_artifact_calls_memory_search": false,
        },
        "required_human_checks": [
            "Confirm this artifact computes rank statistics from redacted hashes only.",
            "Confirm the returned order remains baseline and actual_return_order_changed=false.",
            "Confirm per-key movements are acceptable with key_hash identifiers and no raw keys/content.",
            "Confirm any future ordering behavior has separate authorization."
        ],
        "approval_state": "not_approved",
        "runtime_adapter_approved": false,
        "approval_writes_allowed": false,
        "writes_approval": false,
        "calls_memory_search": false,
        "runs_biocortex": false,
        "registers_embedding_backend": false,
        "changes_memory_search_order": false,
        "actual_return_order_changed": false,
        "default_search_order_change_allowed": false,
        "ordering_behavior_connected": false,
        "may_change_search_order_now": false,
        "may_implement_ordering_now": false,
        "default_calls_unchanged": true,
        "boundary": retrieval_redacted_order_artifact_boundary_payload(),
    })
}

pub fn biocortex_retrieval_opt_in_authorization_decision_packet(
    opts: BioCortexRetrievalOptInAuthorizationDecisionPacketOptions,
) -> Value {
    let decision = opts.authorization_decision;
    let request = opts.authorization_request;

    let decision_schema_ok = value_str_eq(
        decision.get("schema"),
        "agent_bridge.biocortex_retrieval.opt_in_authorization_decision.v0",
    );
    let decision_authorized = value_str_eq(decision.get("decision"), "authorized")
        && value_str_eq(decision.get("authorization_state"), "authorized");
    let decision_scope_ok = value_str_eq(decision.get("authorized_scope"), "opt_in_experiment");
    let decision_implementation_allowed =
        value_bool_is(decision.get("implementation_allowed"), true);
    let decision_runtime_adapter_not_approved =
        value_bool_is(decision.get("runtime_adapter_approved"), false);
    let decision_default_order_not_allowed =
        value_bool_is(decision.get("default_search_order_change_allowed"), false);
    let decision_default_influence_not_authorized = value_bool_is(
        decision.get("default_retrieval_influence_authorized"),
        false,
    );
    let decision_hybrid_not_authorized =
        value_bool_is(decision.get("hybrid_retrieval_influence_authorized"), false);
    let decision_semantic_not_authorized = value_bool_is(
        decision.get("semantic_retrieval_influence_authorized"),
        false,
    );
    let decision_post_review_required = value_bool_is(
        decision.get("requires_post_implementation_review_before_use"),
        true,
    );
    let decision_not_authorizes_runtime_adapter =
        array_contains_str(decision.get("not_authorized"), "runtime_adapter_approved");
    let decision_not_authorizes_default_order = array_contains_str(
        decision.get("not_authorized"),
        "default_search_order_change_allowed",
    );
    let decision_not_authorizes_production_use = array_contains_str(
        decision.get("not_authorized"),
        "production_use_without_post_implementation_review",
    );
    let authorized_impl = decision
        .get("authorized_implementation")
        .unwrap_or(&Value::Null);
    let decision_fts_only = value_bool_is(
        authorized_impl.get("may_affect_only_explicitly_opted_in_fts_calls"),
        true,
    );
    let decision_per_call_surface =
        value_bool_is(authorized_impl.get("may_add_per_call_opt_in_surface"), true);
    let decision_runtime_env_ok = value_str_eq(
        authorized_impl.get("may_add_runtime_enable_env"),
        BIOCORTEX_RETRIEVAL_OPT_IN_ENABLE_ENV,
    );
    let decision_kill_switch_ok = value_str_eq(
        authorized_impl.get("must_keep_operator_disable"),
        BIOCORTEX_RETRIEVAL_DISABLE_ENV,
    );
    let decision_must_return_baseline_without_opt_in = value_bool_is(
        authorized_impl.get("must_return_baseline_without_per_call_opt_in"),
        true,
    );
    let decision_must_fail_open = value_bool_is(
        authorized_impl
            .get("must_return_baseline_on_absent_error_timeout_low_coverage_malformed_rows"),
        true,
    );

    let request_schema_ok = value_str_eq(
        request.get("schema"),
        "agent_bridge.biocortex_retrieval.opt_in_authorization_request.v0",
    );
    let request_scope_ok = value_str_eq(request.get("request_scope"), "opt_in_experiment");
    let request_reflects_implementation_auth = value_str_eq(
        request.get("approval_state"),
        "opt_in_implementation_authorized",
    ) && value_str_eq(
        request.get("authorization_state"),
        "authorized_for_opt_in_implementation",
    );
    let request_implementation_allowed = value_bool_is(request.get("implementation_allowed"), true);
    let request_runtime_adapter_not_approved =
        value_bool_is(request.get("runtime_adapter_approved"), false);
    let request_default_order_not_allowed =
        value_bool_is(request.get("default_search_order_change_allowed"), false);
    let request_writes_approval_false = value_bool_is(request.get("writes_approval"), false);
    let request_current_permission_ok = value_bool_is(
        request.pointer("/current_permissions/may_implement_opt_in_experiment"),
        true,
    );
    let request_default_permission_false = value_bool_is(
        request.pointer("/current_permissions/may_change_default_retrieval_order"),
        false,
    );
    let request_not_requested_runtime_adapter =
        array_contains_str(request.get("not_requested"), "runtime_adapter_approved");
    let request_not_requested_default_order = array_contains_str(
        request.get("not_requested"),
        "default_search_order_change_allowed",
    );
    let request_plan_status_known = request
        .pointer("/opt_in_plan/status")
        .and_then(Value::as_str)
        .map(|status| {
            status == "store_opt_in_search_wrapper_implemented"
                || status == "authorization_decision_consumer_implemented"
                || status == "post_implementation_review_gate_implemented"
                || status == "runtime_influence_review_request_implemented"
                || status == "runtime_influence_decision_packet_implemented"
                || status == "store_opt_in_order_connection_implemented"
                || status == "store_opt_in_runtime_adapter_connection_implemented"
                || status == "runtime_readiness_packet_implemented"
                || status == "post_runtime_semantic_diverse_live_candidate_evidence_ready"
                || status == "post_semantic_diverse_review_recorded"
                || status == "downstream_aio_integration_checkpoint_selected"
                || status == "downstream_aio_runtime_evidence_handoff_ready"
                || status == "ssb_lswr_action_result_review_fixture_ready"
                || status == "read_only_ssb_adapter_fixture_ready"
                || status == "live_lswr_action_result_runtime_evidence_observed_not_verified"
                || status == "loopback_lswr_action_result_verified_fixture_host_observed"
                || status == "loopback_lswr_host_attach_preflight_blocked"
        })
        .unwrap_or(false);

    let mut blockers = Vec::new();
    push_string_blocker(&mut blockers, decision_schema_ok, "decision_schema_invalid");
    push_string_blocker(
        &mut blockers,
        decision_authorized,
        "decision_not_authorized",
    );
    push_string_blocker(
        &mut blockers,
        decision_scope_ok,
        "decision_scope_not_opt_in",
    );
    push_string_blocker(
        &mut blockers,
        decision_implementation_allowed,
        "decision_implementation_not_allowed",
    );
    push_string_blocker(
        &mut blockers,
        decision_runtime_adapter_not_approved,
        "decision_runtime_adapter_approved",
    );
    push_string_blocker(
        &mut blockers,
        decision_default_order_not_allowed,
        "decision_default_order_allowed",
    );
    push_string_blocker(
        &mut blockers,
        decision_default_influence_not_authorized,
        "decision_default_influence_authorized",
    );
    push_string_blocker(
        &mut blockers,
        decision_hybrid_not_authorized,
        "decision_hybrid_influence_authorized",
    );
    push_string_blocker(
        &mut blockers,
        decision_semantic_not_authorized,
        "decision_semantic_influence_authorized",
    );
    push_string_blocker(
        &mut blockers,
        decision_post_review_required,
        "decision_missing_post_implementation_review_requirement",
    );
    push_string_blocker(
        &mut blockers,
        decision_not_authorizes_runtime_adapter,
        "decision_not_authorized_missing_runtime_adapter",
    );
    push_string_blocker(
        &mut blockers,
        decision_not_authorizes_default_order,
        "decision_not_authorized_missing_default_order",
    );
    push_string_blocker(
        &mut blockers,
        decision_not_authorizes_production_use,
        "decision_not_authorized_missing_production_use_gate",
    );
    push_string_blocker(&mut blockers, decision_fts_only, "decision_not_fts_only");
    push_string_blocker(
        &mut blockers,
        decision_per_call_surface,
        "decision_missing_per_call_surface",
    );
    push_string_blocker(
        &mut blockers,
        decision_runtime_env_ok,
        "decision_runtime_env_mismatch",
    );
    push_string_blocker(
        &mut blockers,
        decision_kill_switch_ok,
        "decision_kill_switch_mismatch",
    );
    push_string_blocker(
        &mut blockers,
        decision_must_return_baseline_without_opt_in,
        "decision_missing_baseline_without_opt_in_rule",
    );
    push_string_blocker(
        &mut blockers,
        decision_must_fail_open,
        "decision_missing_fail_open_rule",
    );
    push_string_blocker(&mut blockers, request_schema_ok, "request_schema_invalid");
    push_string_blocker(&mut blockers, request_scope_ok, "request_scope_not_opt_in");
    push_string_blocker(
        &mut blockers,
        request_reflects_implementation_auth,
        "request_not_implementation_authorized",
    );
    push_string_blocker(
        &mut blockers,
        request_implementation_allowed,
        "request_implementation_not_allowed",
    );
    push_string_blocker(
        &mut blockers,
        request_runtime_adapter_not_approved,
        "request_runtime_adapter_approved",
    );
    push_string_blocker(
        &mut blockers,
        request_default_order_not_allowed,
        "request_default_order_allowed",
    );
    push_string_blocker(
        &mut blockers,
        request_writes_approval_false,
        "request_writes_approval",
    );
    push_string_blocker(
        &mut blockers,
        request_current_permission_ok,
        "request_current_permission_missing",
    );
    push_string_blocker(
        &mut blockers,
        request_default_permission_false,
        "request_default_permission_allowed",
    );
    push_string_blocker(
        &mut blockers,
        request_not_requested_runtime_adapter,
        "request_not_requested_missing_runtime_adapter",
    );
    push_string_blocker(
        &mut blockers,
        request_not_requested_default_order,
        "request_not_requested_missing_default_order",
    );
    push_string_blocker(
        &mut blockers,
        request_plan_status_known,
        "request_plan_status_unknown",
    );

    let implementation_authorized = blockers.is_empty();

    json!({
        "schema": BIOCORTEX_RETRIEVAL_OPT_IN_AUTHORIZATION_DECISION_PACKET_SCHEMA,
        "generated_at": now_secs(),
        "read_only": true,
        "authorization_decision_consumer": true,
        "implementation_stage": "authorization_decision_consumer_only",
        "authorization_scope": "opt_in_experiment",
        "purpose": "Consume the human opt-in authorization decision as an implementation-only gate; this is not runtime adapter approval.",
        "input_contract": {
            "decision_schema": decision.get("schema").cloned().unwrap_or(Value::Null),
            "request_schema": request.get("schema").cloned().unwrap_or(Value::Null),
            "authorization_decision_included": false,
            "authorization_request_included": false,
            "unknown_fields_ignored": true,
            "raw_query_included": false,
            "raw_keys_included": false,
            "content_included": false,
        },
        "review_target": {
            "reviewer": required_or_value(opts.reviewer),
            "commit": required_or_value(opts.commit),
            "forum_post_id": required_or_value(opts.forum_post_id),
            "memory_key": required_or_value(opts.memory_key),
        },
        "decision_summary": {
            "decision": decision.get("decision").cloned().unwrap_or(Value::Null),
            "authorization_state": decision
                .get("authorization_state")
                .cloned()
                .unwrap_or(Value::Null),
            "authorized_scope": decision
                .get("authorized_scope")
                .cloned()
                .unwrap_or(Value::Null),
            "implementation_allowed": decision
                .get("implementation_allowed")
                .cloned()
                .unwrap_or(Value::Null),
            "runtime_adapter_approved": false,
            "default_search_order_change_allowed": false,
            "default_retrieval_influence_authorized": false,
            "hybrid_retrieval_influence_authorized": false,
            "semantic_retrieval_influence_authorized": false,
            "requires_post_implementation_review_before_use": decision
                .get("requires_post_implementation_review_before_use")
                .cloned()
                .unwrap_or(Value::Null),
        },
        "request_summary": {
            "approval_state": request.get("approval_state").cloned().unwrap_or(Value::Null),
            "authorization_state": request
                .get("authorization_state")
                .cloned()
                .unwrap_or(Value::Null),
            "request_scope": request.get("request_scope").cloned().unwrap_or(Value::Null),
            "implementation_allowed": request
                .get("implementation_allowed")
                .cloned()
                .unwrap_or(Value::Null),
            "runtime_adapter_approved": false,
            "default_search_order_change_allowed": false,
            "writes_approval": false,
            "opt_in_plan_status": request
                .pointer("/opt_in_plan/status")
                .cloned()
                .unwrap_or(Value::Null),
        },
        "authorized_implementation": {
            "may_implement_opt_in_experiment": implementation_authorized,
            "may_add_runtime_enable_env": BIOCORTEX_RETRIEVAL_OPT_IN_ENABLE_ENV,
            "may_add_per_call_opt_in_surface": decision_per_call_surface,
            "may_affect_only_explicitly_opted_in_fts_calls": decision_fts_only,
            "must_keep_operator_disable": BIOCORTEX_RETRIEVAL_DISABLE_ENV,
            "must_return_baseline_without_per_call_opt_in": decision_must_return_baseline_without_opt_in,
            "must_return_baseline_on_absent_error_timeout_low_coverage_malformed_rows": decision_must_fail_open,
            "requires_post_implementation_review_before_use": decision_post_review_required,
        },
        "not_authorized": [
            "runtime_adapter_approved",
            "default_search_order_change_allowed",
            "default_retrieval_influence_fts",
            "default_retrieval_influence_hybrid",
            "default_retrieval_influence_semantic",
            "production_use_without_post_implementation_review"
        ],
        "boundary_check": {
            "implementation_authorized": implementation_authorized,
            "blockers": blockers,
            "decision_schema_ok": decision_schema_ok,
            "decision_authorized": decision_authorized,
            "decision_scope_ok": decision_scope_ok,
            "request_schema_ok": request_schema_ok,
            "request_reflects_implementation_auth": request_reflects_implementation_auth,
            "request_plan_status_known": request_plan_status_known,
            "runtime_adapter_still_not_approved": decision_runtime_adapter_not_approved
                && request_runtime_adapter_not_approved,
            "default_order_still_not_allowed": decision_default_order_not_allowed
                && request_default_order_not_allowed,
        },
        "required_next_gate": {
            "post_implementation_review_before_use": true,
            "runtime_adapter_approval_required": true,
            "ordering_behavior_connection_required": true,
            "this_packet_approves_runtime_adapter": false,
            "this_packet_connects_ordering_behavior": false,
        },
        "approval_state": if implementation_authorized {
            "opt_in_implementation_authorized"
        } else {
            "not_approved"
        },
        "authorization_state": if implementation_authorized {
            "authorized_for_opt_in_implementation"
        } else {
            "not_authorized"
        },
        "runtime_adapter_approved": false,
        "approval_writes_allowed": false,
        "writes_approval": false,
        "calls_memory_search": false,
        "runs_biocortex": false,
        "registers_embedding_backend": false,
        "changes_memory_search_order": false,
        "default_search_order_change_allowed": false,
        "ordering_behavior_connected": false,
        "may_change_search_order_now": false,
        "may_implement_ordering_now": false,
        "default_calls_unchanged": true,
        "boundary": retrieval_boundary_payload(),
    })
}

pub fn biocortex_retrieval_opt_in_post_implementation_review_gate(
    opts: BioCortexRetrievalOptInPostImplementationReviewGateOptions,
) -> Value {
    let packet = opts.authorization_decision_packet;
    let plan = opts.opt_in_plan;

    let packet_schema_ok = value_str_eq(
        packet.get("schema"),
        BIOCORTEX_RETRIEVAL_OPT_IN_AUTHORIZATION_DECISION_PACKET_SCHEMA,
    );
    let packet_read_only = value_bool_is(packet.get("read_only"), true);
    let packet_is_decision_consumer =
        value_bool_is(packet.get("authorization_decision_consumer"), true);
    let packet_implementation_authorized = value_bool_is(
        packet.pointer("/boundary_check/implementation_authorized"),
        true,
    );
    let packet_approval_state_ok = value_str_eq(
        packet.get("approval_state"),
        "opt_in_implementation_authorized",
    );
    let packet_authorization_state_ok = value_str_eq(
        packet.get("authorization_state"),
        "authorized_for_opt_in_implementation",
    );
    let packet_review_required = value_bool_is(
        packet.pointer("/required_next_gate/post_implementation_review_before_use"),
        true,
    );
    let packet_runtime_gate_required = value_bool_is(
        packet.pointer("/required_next_gate/runtime_adapter_approval_required"),
        true,
    );
    let packet_order_gate_required = value_bool_is(
        packet.pointer("/required_next_gate/ordering_behavior_connection_required"),
        true,
    );
    let packet_not_runtime_approval = value_bool_is(
        packet.pointer("/required_next_gate/this_packet_approves_runtime_adapter"),
        false,
    );
    let packet_not_order_connection = value_bool_is(
        packet.pointer("/required_next_gate/this_packet_connects_ordering_behavior"),
        false,
    );
    let packet_runtime_not_approved = value_bool_is(packet.get("runtime_adapter_approved"), false);
    let packet_default_order_not_allowed =
        value_bool_is(packet.get("default_search_order_change_allowed"), false);
    let packet_approval_writes_false = value_bool_is(packet.get("approval_writes_allowed"), false);
    let packet_writes_false = value_bool_is(packet.get("writes_approval"), false);
    let packet_calls_memory_search_false = value_bool_is(packet.get("calls_memory_search"), false);
    let packet_runs_biocortex_false = value_bool_is(packet.get("runs_biocortex"), false);
    let packet_registers_backend_false =
        value_bool_is(packet.get("registers_embedding_backend"), false);
    let packet_changes_order_false =
        value_bool_is(packet.get("changes_memory_search_order"), false);
    let packet_ordering_connected_false =
        value_bool_is(packet.get("ordering_behavior_connected"), false);
    let packet_may_change_order_false =
        value_bool_is(packet.get("may_change_search_order_now"), false);
    let packet_may_implement_ordering_false =
        value_bool_is(packet.get("may_implement_ordering_now"), false);

    let plan_schema_ok = value_str_eq(
        plan.get("schema"),
        "agent_bridge.biocortex_retrieval.opt_in_experiment_plan.v0",
    );
    let plan_status_ok = plan
        .get("status")
        .and_then(Value::as_str)
        .map(|status| {
            status == "authorization_decision_consumer_implemented"
                || status == "post_implementation_review_gate_implemented"
                || status == "runtime_influence_review_request_implemented"
                || status == "runtime_influence_decision_packet_implemented"
                || status == "store_opt_in_order_connection_implemented"
                || status == "store_opt_in_runtime_adapter_connection_implemented"
                || status == "runtime_readiness_packet_implemented"
                || status == "post_runtime_semantic_diverse_live_candidate_evidence_ready"
                || status == "post_semantic_diverse_review_recorded"
                || status == "downstream_aio_integration_checkpoint_selected"
                || status == "downstream_aio_runtime_evidence_handoff_ready"
                || status == "ssb_lswr_action_result_review_fixture_ready"
                || status == "read_only_ssb_adapter_fixture_ready"
                || status == "live_lswr_action_result_runtime_evidence_observed_not_verified"
                || status == "loopback_lswr_action_result_verified_fixture_host_observed"
                || status == "loopback_lswr_host_attach_preflight_blocked"
        })
        .unwrap_or(false);
    let plan_implementation_allowed = value_bool_is(plan.get("implementation_allowed"), true);
    let plan_store_wrapper_implemented =
        value_bool_is(plan.get("store_opt_in_search_wrapper_implemented"), true);
    let plan_decision_consumer_implemented = value_bool_is(
        plan.get("authorization_decision_consumer_implemented"),
        true,
    );
    let plan_review_gate_implemented = value_bool_is(
        plan.get("post_implementation_review_gate_implemented"),
        true,
    );
    let plan_runtime_not_approved = value_bool_is(plan.get("runtime_adapter_approved"), false);
    let plan_default_order_not_allowed =
        value_bool_is(plan.get("default_search_order_change_allowed"), false);
    let plan_ordering_connected_false =
        value_bool_is(plan.get("ordering_behavior_connected"), false);
    let plan_default_memory_search_unchanged =
        value_bool_is(plan.get("default_memory_search_unchanged"), true);
    let plan_requested_default_influence_none =
        value_str_eq(plan.get("requested_default_influence_scope"), "none");
    let plan_wrapper_returns_baseline = value_bool_is(
        plan.pointer("/implemented_store_opt_in_search_wrapper/returns_baseline_order"),
        true,
    );
    let plan_wrapper_redacted_only = value_bool_is(
        plan.pointer("/implemented_store_opt_in_search_wrapper/redacted_audit_only"),
        true,
    );
    let plan_wrapper_runs_biocortex_false = value_bool_is(
        plan.pointer("/implemented_store_opt_in_search_wrapper/runs_biocortex"),
        false,
    );
    let plan_wrapper_changes_order_false = value_bool_is(
        plan.pointer("/implemented_store_opt_in_search_wrapper/changes_memory_search_order"),
        false,
    );
    let plan_wrapper_ordering_connected_false = value_bool_is(
        plan.pointer("/implemented_store_opt_in_search_wrapper/ordering_behavior_connected"),
        false,
    );
    let plan_gate_block = plan
        .get("implemented_post_implementation_review_gate")
        .unwrap_or(&Value::Null);
    let plan_gate_schema_ok = value_str_eq(
        plan_gate_block.get("schema"),
        BIOCORTEX_RETRIEVAL_OPT_IN_POST_IMPLEMENTATION_REVIEW_GATE_SCHEMA,
    );
    let plan_gate_cli_ok = value_str_eq(
        plan_gate_block.get("cli"),
        "agent-bridge bio-cortex retrieval-opt-in-post-implementation-review-gate",
    );
    let plan_gate_mcp_ok = value_str_eq(
        plan_gate_block.get("mcp_tool"),
        "biocortex_retrieval_opt_in_post_implementation_review_gate",
    );
    let plan_gate_read_only = value_bool_is(plan_gate_block.get("read_only"), true);
    let plan_gate_not_runtime_approval =
        value_bool_is(plan_gate_block.get("runtime_adapter_approved"), false);
    let plan_gate_not_default_order = value_bool_is(
        plan_gate_block.get("default_search_order_change_allowed"),
        false,
    );
    let plan_gate_calls_memory_search_false =
        value_bool_is(plan_gate_block.get("calls_memory_search"), false);
    let plan_gate_runs_biocortex_false =
        value_bool_is(plan_gate_block.get("runs_biocortex"), false);
    let plan_gate_changes_order_false =
        value_bool_is(plan_gate_block.get("changes_memory_search_order"), false);
    let plan_gate_ordering_connected_false =
        value_bool_is(plan_gate_block.get("ordering_behavior_connected"), false);
    let plan_gate_may_change_order_false =
        value_bool_is(plan_gate_block.get("may_change_search_order_now"), false);
    let plan_gate_may_implement_ordering_false =
        value_bool_is(plan_gate_block.get("may_implement_ordering_now"), false);

    let mut blockers = Vec::new();
    push_string_blocker(&mut blockers, packet_schema_ok, "packet_schema_invalid");
    push_string_blocker(&mut blockers, packet_read_only, "packet_not_read_only");
    push_string_blocker(
        &mut blockers,
        packet_is_decision_consumer,
        "packet_not_authorization_decision_consumer",
    );
    push_string_blocker(
        &mut blockers,
        packet_implementation_authorized,
        "packet_implementation_not_authorized",
    );
    push_string_blocker(
        &mut blockers,
        packet_approval_state_ok,
        "packet_approval_state_not_implementation_authorized",
    );
    push_string_blocker(
        &mut blockers,
        packet_authorization_state_ok,
        "packet_authorization_state_not_implementation_authorized",
    );
    push_string_blocker(
        &mut blockers,
        packet_review_required,
        "packet_missing_post_implementation_review_requirement",
    );
    push_string_blocker(
        &mut blockers,
        packet_runtime_gate_required,
        "packet_missing_runtime_adapter_review_gate",
    );
    push_string_blocker(
        &mut blockers,
        packet_order_gate_required,
        "packet_missing_ordering_connection_gate",
    );
    push_string_blocker(
        &mut blockers,
        packet_not_runtime_approval,
        "packet_claims_runtime_adapter_approval",
    );
    push_string_blocker(
        &mut blockers,
        packet_not_order_connection,
        "packet_claims_ordering_connection",
    );
    push_string_blocker(
        &mut blockers,
        packet_runtime_not_approved,
        "packet_runtime_adapter_approved",
    );
    push_string_blocker(
        &mut blockers,
        packet_default_order_not_allowed,
        "packet_default_order_allowed",
    );
    push_string_blocker(
        &mut blockers,
        packet_approval_writes_false,
        "packet_approval_writes_allowed",
    );
    push_string_blocker(&mut blockers, packet_writes_false, "packet_writes_approval");
    push_string_blocker(
        &mut blockers,
        packet_calls_memory_search_false,
        "packet_calls_memory_search",
    );
    push_string_blocker(
        &mut blockers,
        packet_runs_biocortex_false,
        "packet_runs_biocortex",
    );
    push_string_blocker(
        &mut blockers,
        packet_registers_backend_false,
        "packet_registers_embedding_backend",
    );
    push_string_blocker(
        &mut blockers,
        packet_changes_order_false,
        "packet_changes_memory_search_order",
    );
    push_string_blocker(
        &mut blockers,
        packet_ordering_connected_false,
        "packet_ordering_behavior_connected",
    );
    push_string_blocker(
        &mut blockers,
        packet_may_change_order_false,
        "packet_may_change_search_order_now",
    );
    push_string_blocker(
        &mut blockers,
        packet_may_implement_ordering_false,
        "packet_may_implement_ordering_now",
    );
    push_string_blocker(&mut blockers, plan_schema_ok, "plan_schema_invalid");
    push_string_blocker(&mut blockers, plan_status_ok, "plan_status_unknown");
    push_string_blocker(
        &mut blockers,
        plan_implementation_allowed,
        "plan_implementation_not_allowed",
    );
    push_string_blocker(
        &mut blockers,
        plan_store_wrapper_implemented,
        "plan_store_wrapper_not_implemented",
    );
    push_string_blocker(
        &mut blockers,
        plan_decision_consumer_implemented,
        "plan_decision_consumer_not_implemented",
    );
    push_string_blocker(
        &mut blockers,
        plan_review_gate_implemented,
        "plan_review_gate_not_recorded",
    );
    push_string_blocker(
        &mut blockers,
        plan_runtime_not_approved,
        "plan_runtime_adapter_approved",
    );
    push_string_blocker(
        &mut blockers,
        plan_default_order_not_allowed,
        "plan_default_order_allowed",
    );
    push_string_blocker(
        &mut blockers,
        plan_ordering_connected_false,
        "plan_ordering_behavior_connected",
    );
    push_string_blocker(
        &mut blockers,
        plan_default_memory_search_unchanged,
        "plan_default_memory_search_changed",
    );
    push_string_blocker(
        &mut blockers,
        plan_requested_default_influence_none,
        "plan_requested_default_influence_not_none",
    );
    push_string_blocker(
        &mut blockers,
        plan_wrapper_returns_baseline,
        "plan_wrapper_not_returning_baseline",
    );
    push_string_blocker(
        &mut blockers,
        plan_wrapper_redacted_only,
        "plan_wrapper_audit_not_redacted_only",
    );
    push_string_blocker(
        &mut blockers,
        plan_wrapper_runs_biocortex_false,
        "plan_wrapper_runs_biocortex",
    );
    push_string_blocker(
        &mut blockers,
        plan_wrapper_changes_order_false,
        "plan_wrapper_changes_memory_search_order",
    );
    push_string_blocker(
        &mut blockers,
        plan_wrapper_ordering_connected_false,
        "plan_wrapper_ordering_behavior_connected",
    );
    push_string_blocker(
        &mut blockers,
        plan_gate_schema_ok,
        "plan_gate_schema_invalid",
    );
    push_string_blocker(&mut blockers, plan_gate_cli_ok, "plan_gate_cli_mismatch");
    push_string_blocker(&mut blockers, plan_gate_mcp_ok, "plan_gate_mcp_mismatch");
    push_string_blocker(
        &mut blockers,
        plan_gate_read_only,
        "plan_gate_not_read_only",
    );
    push_string_blocker(
        &mut blockers,
        plan_gate_not_runtime_approval,
        "plan_gate_runtime_adapter_approved",
    );
    push_string_blocker(
        &mut blockers,
        plan_gate_not_default_order,
        "plan_gate_default_order_allowed",
    );
    push_string_blocker(
        &mut blockers,
        plan_gate_calls_memory_search_false,
        "plan_gate_calls_memory_search",
    );
    push_string_blocker(
        &mut blockers,
        plan_gate_runs_biocortex_false,
        "plan_gate_runs_biocortex",
    );
    push_string_blocker(
        &mut blockers,
        plan_gate_changes_order_false,
        "plan_gate_changes_memory_search_order",
    );
    push_string_blocker(
        &mut blockers,
        plan_gate_ordering_connected_false,
        "plan_gate_ordering_behavior_connected",
    );
    push_string_blocker(
        &mut blockers,
        plan_gate_may_change_order_false,
        "plan_gate_may_change_search_order_now",
    );
    push_string_blocker(
        &mut blockers,
        plan_gate_may_implement_ordering_false,
        "plan_gate_may_implement_ordering_now",
    );

    let ready_for_human_runtime_influence_review = blockers.is_empty();

    json!({
        "schema": BIOCORTEX_RETRIEVAL_OPT_IN_POST_IMPLEMENTATION_REVIEW_GATE_SCHEMA,
        "generated_at": now_secs(),
        "read_only": true,
        "post_implementation_review_gate": true,
        "implementation_stage": "post_implementation_review_gate_only",
        "authorization_scope": "opt_in_experiment",
        "purpose": "Check whether the implementation-only authorization evidence is ready for a separate human runtime-influence review; this packet does not approve runtime adapter influence or ordering behavior.",
        "input_contract": {
            "authorization_decision_packet_schema": packet.get("schema").cloned().unwrap_or(Value::Null),
            "opt_in_plan_schema": plan.get("schema").cloned().unwrap_or(Value::Null),
            "authorization_decision_packet_included": false,
            "opt_in_plan_included": false,
            "unknown_fields_ignored": true,
            "raw_query_included": false,
            "raw_keys_included": false,
            "content_included": false,
        },
        "review_target": {
            "reviewer": required_or_value(opts.reviewer),
            "commit": required_or_value(opts.commit),
            "forum_post_id": required_or_value(opts.forum_post_id),
            "memory_key": required_or_value(opts.memory_key),
        },
        "evidence_summary": {
            "authorization_decision_packet_schema": packet.get("schema").cloned().unwrap_or(Value::Null),
            "authorization_decision_consumer": packet.get("authorization_decision_consumer").cloned().unwrap_or(Value::Null),
            "implementation_authorized": packet
                .pointer("/boundary_check/implementation_authorized")
                .cloned()
                .unwrap_or(Value::Null),
            "approval_state": packet.get("approval_state").cloned().unwrap_or(Value::Null),
            "authorization_state": packet.get("authorization_state").cloned().unwrap_or(Value::Null),
            "runtime_adapter_approved": false,
            "default_search_order_change_allowed": false,
            "ordering_behavior_connected": false,
            "post_implementation_review_required": packet
                .pointer("/required_next_gate/post_implementation_review_before_use")
                .cloned()
                .unwrap_or(Value::Null),
        },
        "plan_summary": {
            "schema": plan.get("schema").cloned().unwrap_or(Value::Null),
            "status": plan.get("status").cloned().unwrap_or(Value::Null),
            "implementation_allowed": plan.get("implementation_allowed").cloned().unwrap_or(Value::Null),
            "store_opt_in_search_wrapper_implemented": plan.get("store_opt_in_search_wrapper_implemented").cloned().unwrap_or(Value::Null),
            "authorization_decision_consumer_implemented": plan.get("authorization_decision_consumer_implemented").cloned().unwrap_or(Value::Null),
            "post_implementation_review_gate_implemented": plan.get("post_implementation_review_gate_implemented").cloned().unwrap_or(Value::Null),
            "runtime_influence_review_request_implemented": plan.get("runtime_influence_review_request_implemented").cloned().unwrap_or(Value::Null),
            "runtime_influence_decision_packet_implemented": plan.get("runtime_influence_decision_packet_implemented").cloned().unwrap_or(Value::Null),
            "store_opt_in_order_connection_implemented": plan.get("store_opt_in_order_connection_implemented").cloned().unwrap_or(Value::Null),
            "store_opt_in_runtime_adapter_connection_implemented": plan.get("store_opt_in_runtime_adapter_connection_implemented").cloned().unwrap_or(Value::Null),
            "runtime_readiness_packet_implemented": plan.get("runtime_readiness_packet_implemented").cloned().unwrap_or(Value::Null),
            "explicit_opt_in_fts_runtime_adapter_connected": plan.get("explicit_opt_in_fts_runtime_adapter_connected").cloned().unwrap_or(Value::Null),
            "default_memory_search_unchanged": plan.get("default_memory_search_unchanged").cloned().unwrap_or(Value::Null),
            "runtime_adapter_approved": false,
            "default_search_order_change_allowed": false,
            "ordering_behavior_connected": false,
        },
        "review_readiness": {
            "ready_for_human_runtime_influence_review": ready_for_human_runtime_influence_review,
            "post_implementation_review_completed": false,
            "runtime_adapter_review_completed": false,
            "ordering_behavior_review_completed": false,
            "this_packet_approves_runtime_adapter": false,
            "this_packet_allows_default_search_order_change": false,
            "this_packet_connects_ordering_behavior": false,
        },
        "boundary_check": {
            "ready_for_human_runtime_influence_review": ready_for_human_runtime_influence_review,
            "blockers": blockers,
            "packet_schema_ok": packet_schema_ok,
            "packet_implementation_authorized": packet_implementation_authorized,
            "packet_runtime_adapter_still_not_approved": packet_runtime_not_approved,
            "packet_default_order_still_not_allowed": packet_default_order_not_allowed,
            "plan_schema_ok": plan_schema_ok,
            "plan_status_ok": plan_status_ok,
            "plan_review_gate_implemented": plan_review_gate_implemented,
            "plan_runtime_adapter_still_not_approved": plan_runtime_not_approved,
            "plan_default_order_still_not_allowed": plan_default_order_not_allowed,
            "plan_ordering_behavior_connected_false": plan_ordering_connected_false,
        },
        "required_human_review": [
            "Confirm the implementation matches the implementation-only authorization scope.",
            "Confirm any runtime adapter influence remains disabled until separately approved.",
            "Confirm default search order remains unchanged.",
            "Confirm ordering behavior is not connected by this packet.",
            "Record a separate human review decision before enabling any ordering path."
        ],
        "required_next_gate": {
            "human_runtime_influence_review_required": true,
            "runtime_adapter_approval_required": true,
            "ordering_behavior_connection_required": true,
            "this_packet_approves_runtime_adapter": false,
            "this_packet_connects_ordering_behavior": false,
            "this_packet_allows_default_search_order_change": false,
        },
        "review_state": if ready_for_human_runtime_influence_review {
            "ready_for_human_runtime_influence_review"
        } else {
            "blocked"
        },
        "approval_state": "not_approved",
        "authorization_state": "requires_separate_human_runtime_influence_review",
        "implementation_allowed": false,
        "runtime_adapter_approved": false,
        "approval_writes_allowed": false,
        "writes_approval": false,
        "calls_memory_search": false,
        "runs_biocortex": false,
        "registers_embedding_backend": false,
        "changes_memory_search_order": false,
        "default_search_order_change_allowed": false,
        "ordering_behavior_connected": false,
        "may_change_search_order_now": false,
        "may_implement_ordering_now": false,
        "default_calls_unchanged": true,
        "boundary": retrieval_boundary_payload(),
    })
}

pub fn biocortex_retrieval_opt_in_runtime_influence_review_request(
    opts: BioCortexRetrievalOptInRuntimeInfluenceReviewRequestOptions,
) -> Value {
    let gate = opts.post_implementation_review_gate;
    let artifact = opts.redacted_order_artifact;
    let aggregate = opts.redacted_evidence_aggregate;
    let evidence_summary = opts.evidence_summary;
    let capability_ledger = opts.capability_ledger_report_packet;
    let aggregate_ref = aggregate.as_ref();
    let aggregate_provided = aggregate_ref.is_some();
    let evidence_summary_ref = evidence_summary.as_ref();
    let evidence_summary_provided = evidence_summary_ref.is_some();
    let capability_ledger_ref = capability_ledger.as_ref();
    let capability_ledger_provided = capability_ledger_ref.is_some();

    let gate_schema_ok = value_str_eq(
        gate.get("schema"),
        BIOCORTEX_RETRIEVAL_OPT_IN_POST_IMPLEMENTATION_REVIEW_GATE_SCHEMA,
    );
    let gate_read_only = value_bool_is(gate.get("read_only"), true);
    let gate_is_post_impl = value_bool_is(gate.get("post_implementation_review_gate"), true);
    let gate_ready = value_bool_is(
        gate.pointer("/review_readiness/ready_for_human_runtime_influence_review"),
        true,
    ) && value_bool_is(
        gate.pointer("/boundary_check/ready_for_human_runtime_influence_review"),
        true,
    );
    let gate_review_state_ok = value_str_eq(
        gate.get("review_state"),
        "ready_for_human_runtime_influence_review",
    );
    let gate_approval_state_ok = value_str_eq(gate.get("approval_state"), "not_approved");
    let gate_authorization_state_ok = value_str_eq(
        gate.get("authorization_state"),
        "requires_separate_human_runtime_influence_review",
    );
    let gate_runtime_not_approved = value_bool_is(gate.get("runtime_adapter_approved"), false);
    let gate_default_order_not_allowed =
        value_bool_is(gate.get("default_search_order_change_allowed"), false);
    let gate_writes_false = value_bool_is(gate.get("writes_approval"), false);
    let gate_calls_memory_search_false = value_bool_is(gate.get("calls_memory_search"), false);
    let gate_runs_biocortex_false = value_bool_is(gate.get("runs_biocortex"), false);
    let gate_changes_order_false = value_bool_is(gate.get("changes_memory_search_order"), false);
    let gate_ordering_connected_false =
        value_bool_is(gate.get("ordering_behavior_connected"), false);
    let gate_may_change_order_false = value_bool_is(gate.get("may_change_search_order_now"), false);
    let gate_may_implement_ordering_false =
        value_bool_is(gate.get("may_implement_ordering_now"), false);
    let gate_next_runtime_required = value_bool_is(
        gate.pointer("/required_next_gate/runtime_adapter_approval_required"),
        true,
    );
    let gate_next_ordering_required = value_bool_is(
        gate.pointer("/required_next_gate/ordering_behavior_connection_required"),
        true,
    );
    let gate_next_not_runtime_approval = value_bool_is(
        gate.pointer("/required_next_gate/this_packet_approves_runtime_adapter"),
        false,
    );
    let gate_next_not_order_connection = value_bool_is(
        gate.pointer("/required_next_gate/this_packet_connects_ordering_behavior"),
        false,
    );

    let artifact_schema_ok = value_str_eq(
        artifact.get("schema"),
        BIOCORTEX_RETRIEVAL_OPT_IN_REDACTED_ORDER_ARTIFACT_SCHEMA,
    );
    let artifact_read_only = value_bool_is(artifact.get("read_only"), true);
    let artifact_ready = value_bool_is(artifact.pointer("/boundary_check/artifact_ready"), true);
    let artifact_approval_state_ok = value_str_eq(artifact.get("approval_state"), "not_approved");
    let artifact_runtime_not_approved =
        value_bool_is(artifact.get("runtime_adapter_approved"), false);
    let artifact_approval_writes_false =
        value_bool_is(artifact.get("approval_writes_allowed"), false);
    let artifact_writes_false = value_bool_is(artifact.get("writes_approval"), false);
    let artifact_calls_memory_search_false =
        value_bool_is(artifact.get("calls_memory_search"), false);
    let artifact_runs_biocortex_false = value_bool_is(artifact.get("runs_biocortex"), false);
    let artifact_changes_order_false =
        value_bool_is(artifact.get("changes_memory_search_order"), false);
    let artifact_default_order_false =
        value_bool_is(artifact.get("default_search_order_change_allowed"), false);
    let artifact_ordering_connected_false =
        value_bool_is(artifact.get("ordering_behavior_connected"), false);
    let artifact_actual_return_unchanged =
        value_bool_is(artifact.get("actual_return_order_changed"), false);
    let artifact_may_change_order_false =
        value_bool_is(artifact.get("may_change_search_order_now"), false);
    let artifact_may_implement_ordering_false =
        value_bool_is(artifact.get("may_implement_ordering_now"), false);
    let artifact_raw_query_false = value_bool_is(
        artifact.pointer("/input_contract/raw_query_included"),
        false,
    );
    let artifact_raw_keys_false =
        value_bool_is(artifact.pointer("/input_contract/raw_keys_included"), false);
    let artifact_content_false =
        value_bool_is(artifact.pointer("/input_contract/content_included"), false);
    let artifact_redacted_comparable = value_bool_is(
        artifact.pointer("/boundary_check/redacted_rows_comparable"),
        true,
    );
    let artifact_baseline_returned = value_bool_is(
        artifact.pointer("/redacted_order_comparison/returned_order/baseline_returned"),
        true,
    );
    let artifact_return_order_unchanged = value_bool_is(
        artifact.pointer("/redacted_order_comparison/returned_order/actual_return_order_changed"),
        false,
    );

    let aggregate_schema_ok = !aggregate_provided
        || value_str_eq(
            aggregate_ref.and_then(|value| value.pointer("/schema")),
            BIOCORTEX_RETRIEVAL_OPT_IN_REDACTED_EVIDENCE_AGGREGATE_SCHEMA,
        );
    let aggregate_read_only = !aggregate_provided
        || value_bool_is(
            aggregate_ref.and_then(|value| value.pointer("/read_only")),
            true,
        );
    let aggregate_is_redacted = !aggregate_provided
        || value_bool_is(
            aggregate_ref.and_then(|value| value.pointer("/redacted_evidence_aggregate")),
            true,
        );
    let aggregate_ready = aggregate_provided
        && value_bool_is(
            aggregate_ref
                .and_then(|value| value.pointer("/interpretation/aggregate_evidence_ready")),
            true,
        );
    let aggregate_default_influence_not_ready = !aggregate_provided
        || value_bool_is(
            aggregate_ref
                .and_then(|value| value.pointer("/interpretation/default_influence_ready")),
            false,
        );
    let aggregate_human_review_required = !aggregate_provided
        || value_bool_is(
            aggregate_ref.and_then(|value| value.pointer("/interpretation/human_review_required")),
            true,
        );
    let aggregate_controlled_rank_movement_observed = aggregate_provided
        && value_bool_is(
            aggregate_ref.and_then(|value| {
                value.pointer("/interpretation/controlled_rank_movement_observed")
            }),
            true,
        );
    let aggregate_expanded_coverage_without_additional_movement = aggregate_provided
        && value_bool_is(
            aggregate_ref.and_then(|value| {
                value.pointer("/interpretation/expanded_coverage_without_additional_movement")
            }),
            true,
        );
    let aggregate_approval_state_ok = !aggregate_provided
        || value_str_eq(
            aggregate_ref.and_then(|value| value.pointer("/approval_state")),
            "evidence_aggregate_only",
        );
    let aggregate_authorization_state_ok = !aggregate_provided
        || value_str_eq(
            aggregate_ref.and_then(|value| value.pointer("/authorization_state")),
            "does_not_grant_runtime_influence",
        );
    let aggregate_approval_writes_false = !aggregate_provided
        || value_bool_is(
            aggregate_ref.and_then(|value| value.pointer("/approval_writes_allowed")),
            false,
        );
    let aggregate_writes_false = !aggregate_provided
        || value_bool_is(
            aggregate_ref.and_then(|value| value.pointer("/writes_approval")),
            false,
        );
    let aggregate_calls_memory_search_false = !aggregate_provided
        || value_bool_is(
            aggregate_ref.and_then(|value| value.pointer("/calls_memory_search")),
            false,
        );
    let aggregate_runs_biocortex_false = !aggregate_provided
        || value_bool_is(
            aggregate_ref.and_then(|value| value.pointer("/runs_biocortex")),
            false,
        );
    let aggregate_registers_embedding_backend_false = !aggregate_provided
        || value_bool_is(
            aggregate_ref.and_then(|value| value.pointer("/registers_embedding_backend")),
            false,
        );
    let aggregate_changes_order_false = !aggregate_provided
        || value_bool_is(
            aggregate_ref.and_then(|value| value.pointer("/changes_memory_search_order")),
            false,
        );
    let aggregate_default_order_false = !aggregate_provided
        || value_bool_is(
            aggregate_ref.and_then(|value| value.pointer("/default_search_order_change_allowed")),
            false,
        );
    let aggregate_default_calls_unchanged = !aggregate_provided
        || value_bool_is(
            aggregate_ref.and_then(|value| value.pointer("/default_calls_unchanged")),
            true,
        );
    let aggregate_top_raw_flags_false = !aggregate_provided
        || (value_bool_is(
            aggregate_ref.and_then(|value| value.pointer("/raw_queries_included")),
            false,
        ) && value_bool_is(
            aggregate_ref.and_then(|value| value.pointer("/raw_keys_included")),
            false,
        ) && value_bool_is(
            aggregate_ref.and_then(|value| value.pointer("/content_included")),
            false,
        ) && value_bool_is(
            aggregate_ref.and_then(|value| value.pointer("/side_signal_raw_included")),
            false,
        ));
    let aggregate_input_raw_flags_false = !aggregate_provided
        || (value_bool_is(
            aggregate_ref.and_then(|value| value.pointer("/input_contract/raw_queries_included")),
            false,
        ) && value_bool_is(
            aggregate_ref.and_then(|value| value.pointer("/input_contract/raw_keys_included")),
            false,
        ) && value_bool_is(
            aggregate_ref.and_then(|value| value.pointer("/input_contract/content_included")),
            false,
        ) && value_bool_is(
            aggregate_ref
                .and_then(|value| value.pointer("/input_contract/side_signal_raw_included")),
            false,
        ));
    let aggregate_evidence_raw_flags_false = !aggregate_provided
        || (value_bool_is(
            aggregate_ref.and_then(|value| value.pointer("/movement_evidence/raw_flags_all_false")),
            true,
        ) && value_bool_is(
            aggregate_ref.and_then(|value| value.pointer("/coverage_evidence/raw_flags_all_false")),
            true,
        ));
    let aggregate_safe_for_review = !aggregate_provided
        || (aggregate_schema_ok
            && aggregate_read_only
            && aggregate_is_redacted
            && aggregate_ready
            && aggregate_default_influence_not_ready
            && aggregate_human_review_required
            && aggregate_controlled_rank_movement_observed
            && aggregate_expanded_coverage_without_additional_movement
            && aggregate_approval_state_ok
            && aggregate_authorization_state_ok
            && aggregate_approval_writes_false
            && aggregate_writes_false
            && aggregate_calls_memory_search_false
            && aggregate_runs_biocortex_false
            && aggregate_registers_embedding_backend_false
            && aggregate_changes_order_false
            && aggregate_default_order_false
            && aggregate_default_calls_unchanged
            && aggregate_top_raw_flags_false
            && aggregate_input_raw_flags_false
            && aggregate_evidence_raw_flags_false);

    let evidence_summary_schema_ok = !evidence_summary_provided
        || value_str_eq(
            evidence_summary_ref.and_then(|value| value.pointer("/schema")),
            BIOCORTEX_RETRIEVAL_OPT_IN_EVIDENCE_SUMMARY_SCHEMA,
        );
    let evidence_summary_read_only = !evidence_summary_provided
        || value_bool_is(
            evidence_summary_ref.and_then(|value| value.pointer("/read_only")),
            true,
        );
    let evidence_summary_is_summary = !evidence_summary_provided
        || value_bool_is(
            evidence_summary_ref.and_then(|value| value.pointer("/evidence_summary")),
            true,
        );
    let evidence_summary_ready = evidence_summary_provided
        && value_bool_is(
            evidence_summary_ref.and_then(|value| value.pointer("/interpretation/evidence_ready")),
            true,
        );
    let evidence_summary_review_state_ok = !evidence_summary_provided
        || value_str_eq(
            evidence_summary_ref.and_then(|value| value.pointer("/interpretation/review_state")),
            "post_runtime_evidence_ready",
        );
    let evidence_summary_controlled_rank_movement_observed = evidence_summary_provided
        && value_bool_is(
            evidence_summary_ref.and_then(|value| {
                value.pointer("/interpretation/controlled_rank_movement_observed")
            }),
            true,
        );
    let evidence_summary_default_influence_not_ready = !evidence_summary_provided
        || value_bool_is(
            evidence_summary_ref
                .and_then(|value| value.pointer("/interpretation/default_influence_ready")),
            false,
        );
    let evidence_summary_runtime_readiness_packet_provided = evidence_summary_provided
        && value_bool_is(
            evidence_summary_ref.and_then(|value| {
                value.pointer("/interpretation/runtime_readiness_packet_provided")
            }),
            true,
        );
    let evidence_summary_runtime_readiness_requirement_met = evidence_summary_provided
        && value_bool_is(
            evidence_summary_ref.and_then(|value| {
                value.pointer("/interpretation/runtime_readiness_requirement_met")
            }),
            true,
        );
    let evidence_summary_readiness_gated_batch_evidence_ready = evidence_summary_provided
        && value_bool_is(
            evidence_summary_ref.and_then(|value| {
                value.pointer("/interpretation/readiness_gated_batch_evidence_ready")
            }),
            true,
        );
    let evidence_summary_readiness_matches_batch = !evidence_summary_provided
        || value_bool_is(
            evidence_summary_ref.and_then(|value| {
                value.pointer("/interpretation/readiness_matches_batch_diagnostics")
            }),
            true,
        );
    let evidence_summary_batch_transition_gated = evidence_summary_provided
        && value_bool_is(
            evidence_summary_ref.and_then(|value| {
                value.pointer("/interpretation/batch_diagnostics_transition_gated")
            }),
            true,
        );
    let evidence_summary_batch_evidence_source = evidence_summary_ref
        .and_then(|value| value.pointer("/interpretation/batch_diagnostics_evidence_source"))
        .and_then(Value::as_str)
        .unwrap_or("");
    let evidence_summary_approval_state_ok = !evidence_summary_provided
        || value_str_eq(
            evidence_summary_ref.and_then(|value| value.pointer("/approval_state")),
            "evidence_summary_only",
        );
    let evidence_summary_authorization_state_ok = !evidence_summary_provided
        || value_str_eq(
            evidence_summary_ref.and_then(|value| value.pointer("/authorization_state")),
            "does_not_grant_runtime_influence",
        );
    let evidence_summary_approval_writes_false = !evidence_summary_provided
        || value_bool_is(
            evidence_summary_ref.and_then(|value| value.pointer("/approval_writes_allowed")),
            false,
        );
    let evidence_summary_writes_false = !evidence_summary_provided
        || value_bool_is(
            evidence_summary_ref.and_then(|value| value.pointer("/writes_approval")),
            false,
        );
    let evidence_summary_calls_memory_search_false = !evidence_summary_provided
        || value_bool_is(
            evidence_summary_ref.and_then(|value| value.pointer("/calls_memory_search")),
            false,
        );
    let evidence_summary_runs_biocortex_false = !evidence_summary_provided
        || value_bool_is(
            evidence_summary_ref.and_then(|value| value.pointer("/runs_biocortex")),
            false,
        );
    let evidence_summary_registers_embedding_backend_false = !evidence_summary_provided
        || value_bool_is(
            evidence_summary_ref.and_then(|value| value.pointer("/registers_embedding_backend")),
            false,
        );
    let evidence_summary_changes_order_false = !evidence_summary_provided
        || value_bool_is(
            evidence_summary_ref.and_then(|value| value.pointer("/changes_memory_search_order")),
            false,
        );
    let evidence_summary_default_order_false = !evidence_summary_provided
        || value_bool_is(
            evidence_summary_ref
                .and_then(|value| value.pointer("/default_search_order_change_allowed")),
            false,
        );
    let evidence_summary_default_calls_unchanged = !evidence_summary_provided
        || value_bool_is(
            evidence_summary_ref.and_then(|value| value.pointer("/default_calls_unchanged")),
            true,
        );
    let evidence_summary_top_raw_flags_false = !evidence_summary_provided
        || (value_bool_is(
            evidence_summary_ref.and_then(|value| value.pointer("/raw_queries_included")),
            false,
        ) && value_bool_is(
            evidence_summary_ref.and_then(|value| value.pointer("/raw_keys_included")),
            false,
        ) && value_bool_is(
            evidence_summary_ref.and_then(|value| value.pointer("/content_included")),
            false,
        ) && value_bool_is(
            evidence_summary_ref.and_then(|value| value.pointer("/side_signal_raw_included")),
            false,
        ));
    let evidence_summary_input_raw_flags_false = !evidence_summary_provided
        || (value_bool_is(
            evidence_summary_ref
                .and_then(|value| value.pointer("/input_contract/raw_queries_included")),
            false,
        ) && value_bool_is(
            evidence_summary_ref
                .and_then(|value| value.pointer("/input_contract/raw_keys_included")),
            false,
        ) && value_bool_is(
            evidence_summary_ref
                .and_then(|value| value.pointer("/input_contract/content_included")),
            false,
        ) && value_bool_is(
            evidence_summary_ref
                .and_then(|value| value.pointer("/input_contract/side_signal_raw_included")),
            false,
        ));
    let evidence_summary_component_raw_flags_false = !evidence_summary_provided
        || (value_bool_is(
            evidence_summary_ref
                .and_then(|value| value.pointer("/interpretation/batch_diagnostics_raw_safe")),
            true,
        ) && value_bool_is(
            evidence_summary_ref
                .and_then(|value| value.pointer("/interpretation/controlled_order_raw_safe")),
            true,
        ) && value_bool_is(
            evidence_summary_ref
                .and_then(|value| value.pointer("/runtime_readiness/raw_flags_all_false")),
            true,
        ));
    let evidence_summary_safe_for_review = !evidence_summary_provided
        || (evidence_summary_schema_ok
            && evidence_summary_read_only
            && evidence_summary_is_summary
            && evidence_summary_ready
            && evidence_summary_review_state_ok
            && evidence_summary_controlled_rank_movement_observed
            && evidence_summary_default_influence_not_ready
            && evidence_summary_runtime_readiness_packet_provided
            && evidence_summary_runtime_readiness_requirement_met
            && evidence_summary_readiness_gated_batch_evidence_ready
            && evidence_summary_readiness_matches_batch
            && evidence_summary_batch_transition_gated
            && evidence_summary_approval_state_ok
            && evidence_summary_authorization_state_ok
            && evidence_summary_approval_writes_false
            && evidence_summary_writes_false
            && evidence_summary_calls_memory_search_false
            && evidence_summary_runs_biocortex_false
            && evidence_summary_registers_embedding_backend_false
            && evidence_summary_changes_order_false
            && evidence_summary_default_order_false
            && evidence_summary_default_calls_unchanged
            && evidence_summary_top_raw_flags_false
            && evidence_summary_input_raw_flags_false
            && evidence_summary_component_raw_flags_false);

    let capability_ledger_schema_ok = !capability_ledger_provided
        || value_str_eq(
            capability_ledger_ref.and_then(|value| value.pointer("/schema")),
            BIOCORTEX_CAPABILITY_LEDGER_REPORT_PACKET_SCHEMA,
        );
    let capability_ledger_accepted = capability_ledger_provided
        && value_str_eq(
            capability_ledger_ref.and_then(|value| value.pointer("/verdict")),
            "accepted",
        );
    let capability_ledger_read_only = !capability_ledger_provided
        || value_bool_is(
            capability_ledger_ref.and_then(|value| value.pointer("/read_only_confirmed")),
            true,
        );
    let capability_ledger_static_artifact_only = !capability_ledger_provided
        || value_bool_is(
            capability_ledger_ref
                .and_then(|value| value.pointer("/safety/static_artifact_only")),
            true,
        );
    let capability_ledger_memory_writes_false = !capability_ledger_provided
        || value_bool_is(
            capability_ledger_ref
                .and_then(|value| value.pointer("/safety/memory_write_attempted")),
            false,
        );
    let capability_ledger_retrieval_order_false = !capability_ledger_provided
        || value_bool_is(
            capability_ledger_ref
                .and_then(|value| value.pointer("/safety/retrieval_order_change_attempted")),
            false,
        );
    let capability_ledger_runtime_false = !capability_ledger_provided
        || value_bool_is(
            capability_ledger_ref
                .and_then(|value| value.pointer("/safety/runtime_authority_observed")),
            false,
        );
    let capability_ledger_executor_false = !capability_ledger_provided
        || value_bool_is(
            capability_ledger_ref
                .and_then(|value| value.pointer("/safety/executor_enablement_observed")),
            false,
        );
    let capability_ledger_mcp_registration_false = !capability_ledger_provided
        || value_bool_is(
            capability_ledger_ref
                .and_then(|value| value.pointer("/safety/mcp_tool_registration")),
            false,
        );
    let capability_ledger_nexus_false = !capability_ledger_provided
        || value_bool_is(
            capability_ledger_ref
                .and_then(|value| value.pointer("/safety/nexus_world_tick_touched")),
            false,
        );
    let capability_ledger_aiot_false = !capability_ledger_provided
        || value_bool_is(
            capability_ledger_ref
                .and_then(|value| value.pointer("/safety/aiot_runtime_called")),
            false,
        );
    let capability_ledger_language_false = !capability_ledger_provided
        || value_bool_is(
            capability_ledger_ref
                .and_then(|value| value.pointer("/safety/language_generation_observed")),
            false,
        );
    let capability_ledger_cognition_false = !capability_ledger_provided
        || value_bool_is(
            capability_ledger_ref
                .and_then(|value| value.pointer("/safety/cognition_claim_observed")),
            false,
        );
    let capability_ledger_downstream_action_display_only = !capability_ledger_provided
        || value_str_eq(
            capability_ledger_ref.and_then(|value| value.pointer("/downstream_action")),
            "display_or_review_only",
        );
    let capability_ledger_integration_decision_display_only = !capability_ledger_provided
        || value_str_eq(
            capability_ledger_ref.and_then(|value| value.pointer("/integration_decision")),
            "shadow_only_no_runtime_admission",
        );
    let capability_ledger_decision_display_only = capability_ledger_downstream_action_display_only
        && capability_ledger_integration_decision_display_only;
    let capability_ledger_safe_for_review = !capability_ledger_provided
        || (capability_ledger_schema_ok
            && capability_ledger_accepted
            && capability_ledger_read_only
            && capability_ledger_static_artifact_only
            && capability_ledger_memory_writes_false
            && capability_ledger_retrieval_order_false
            && capability_ledger_runtime_false
            && capability_ledger_executor_false
            && capability_ledger_mcp_registration_false
            && capability_ledger_nexus_false
            && capability_ledger_aiot_false
            && capability_ledger_language_false
            && capability_ledger_cognition_false
            && capability_ledger_decision_display_only);

    let mut blockers = Vec::new();
    push_string_blocker(&mut blockers, gate_schema_ok, "gate_schema_invalid");
    push_string_blocker(&mut blockers, gate_read_only, "gate_not_read_only");
    push_string_blocker(
        &mut blockers,
        gate_is_post_impl,
        "gate_not_post_implementation_gate",
    );
    push_string_blocker(
        &mut blockers,
        gate_ready,
        "gate_not_ready_for_runtime_review",
    );
    push_string_blocker(
        &mut blockers,
        gate_review_state_ok,
        "gate_review_state_not_ready",
    );
    push_string_blocker(
        &mut blockers,
        gate_approval_state_ok,
        "gate_approval_state_changed",
    );
    push_string_blocker(
        &mut blockers,
        gate_authorization_state_ok,
        "gate_authorization_state_unexpected",
    );
    push_string_blocker(
        &mut blockers,
        gate_runtime_not_approved,
        "gate_runtime_adapter_approved",
    );
    push_string_blocker(
        &mut blockers,
        gate_default_order_not_allowed,
        "gate_default_order_allowed",
    );
    push_string_blocker(&mut blockers, gate_writes_false, "gate_writes_approval");
    push_string_blocker(
        &mut blockers,
        gate_calls_memory_search_false,
        "gate_calls_memory_search",
    );
    push_string_blocker(
        &mut blockers,
        gate_runs_biocortex_false,
        "gate_runs_biocortex",
    );
    push_string_blocker(
        &mut blockers,
        gate_changes_order_false,
        "gate_changes_memory_search_order",
    );
    push_string_blocker(
        &mut blockers,
        gate_ordering_connected_false,
        "gate_ordering_connected",
    );
    push_string_blocker(
        &mut blockers,
        gate_may_change_order_false,
        "gate_may_change_order_now",
    );
    push_string_blocker(
        &mut blockers,
        gate_may_implement_ordering_false,
        "gate_may_implement_ordering_now",
    );
    push_string_blocker(
        &mut blockers,
        gate_next_runtime_required,
        "gate_missing_runtime_review_requirement",
    );
    push_string_blocker(
        &mut blockers,
        gate_next_ordering_required,
        "gate_missing_ordering_review_requirement",
    );
    push_string_blocker(
        &mut blockers,
        gate_next_not_runtime_approval,
        "gate_claims_runtime_adapter_approval",
    );
    push_string_blocker(
        &mut blockers,
        gate_next_not_order_connection,
        "gate_claims_ordering_connection",
    );
    push_string_blocker(&mut blockers, artifact_schema_ok, "artifact_schema_invalid");
    push_string_blocker(&mut blockers, artifact_read_only, "artifact_not_read_only");
    push_string_blocker(&mut blockers, artifact_ready, "artifact_not_ready");
    push_string_blocker(
        &mut blockers,
        artifact_approval_state_ok,
        "artifact_approval_state_changed",
    );
    push_string_blocker(
        &mut blockers,
        artifact_runtime_not_approved,
        "artifact_runtime_adapter_approved",
    );
    push_string_blocker(
        &mut blockers,
        artifact_approval_writes_false,
        "artifact_approval_writes_allowed",
    );
    push_string_blocker(
        &mut blockers,
        artifact_writes_false,
        "artifact_writes_approval",
    );
    push_string_blocker(
        &mut blockers,
        artifact_calls_memory_search_false,
        "artifact_calls_memory_search",
    );
    push_string_blocker(
        &mut blockers,
        artifact_runs_biocortex_false,
        "artifact_runs_biocortex",
    );
    push_string_blocker(
        &mut blockers,
        artifact_changes_order_false,
        "artifact_changes_memory_search_order",
    );
    push_string_blocker(
        &mut blockers,
        artifact_default_order_false,
        "artifact_default_order_allowed",
    );
    push_string_blocker(
        &mut blockers,
        artifact_ordering_connected_false,
        "artifact_ordering_behavior_connected",
    );
    push_string_blocker(
        &mut blockers,
        artifact_actual_return_unchanged,
        "artifact_actual_return_order_changed",
    );
    push_string_blocker(
        &mut blockers,
        artifact_may_change_order_false,
        "artifact_may_change_search_order_now",
    );
    push_string_blocker(
        &mut blockers,
        artifact_may_implement_ordering_false,
        "artifact_may_implement_ordering_now",
    );
    push_string_blocker(
        &mut blockers,
        artifact_raw_query_false,
        "artifact_raw_query_included",
    );
    push_string_blocker(
        &mut blockers,
        artifact_raw_keys_false,
        "artifact_raw_keys_included",
    );
    push_string_blocker(
        &mut blockers,
        artifact_content_false,
        "artifact_content_included",
    );
    push_string_blocker(
        &mut blockers,
        artifact_redacted_comparable,
        "artifact_redacted_rows_not_comparable",
    );
    push_string_blocker(
        &mut blockers,
        artifact_baseline_returned,
        "artifact_returned_order_not_baseline",
    );
    push_string_blocker(
        &mut blockers,
        artifact_return_order_unchanged,
        "artifact_return_order_changed",
    );
    if aggregate_provided {
        push_string_blocker(
            &mut blockers,
            aggregate_schema_ok,
            "aggregate_schema_invalid",
        );
        push_string_blocker(
            &mut blockers,
            aggregate_read_only,
            "aggregate_not_read_only",
        );
        push_string_blocker(
            &mut blockers,
            aggregate_is_redacted,
            "aggregate_not_redacted_evidence",
        );
        push_string_blocker(&mut blockers, aggregate_ready, "aggregate_not_ready");
        push_string_blocker(
            &mut blockers,
            aggregate_default_influence_not_ready,
            "aggregate_default_influence_ready",
        );
        push_string_blocker(
            &mut blockers,
            aggregate_human_review_required,
            "aggregate_missing_human_review_requirement",
        );
        push_string_blocker(
            &mut blockers,
            aggregate_controlled_rank_movement_observed,
            "aggregate_missing_controlled_rank_movement",
        );
        push_string_blocker(
            &mut blockers,
            aggregate_expanded_coverage_without_additional_movement,
            "aggregate_missing_expanded_coverage",
        );
        push_string_blocker(
            &mut blockers,
            aggregate_approval_state_ok,
            "aggregate_approval_state_unexpected",
        );
        push_string_blocker(
            &mut blockers,
            aggregate_authorization_state_ok,
            "aggregate_authorization_state_unexpected",
        );
        push_string_blocker(
            &mut blockers,
            aggregate_approval_writes_false,
            "aggregate_approval_writes_allowed",
        );
        push_string_blocker(
            &mut blockers,
            aggregate_writes_false,
            "aggregate_writes_approval",
        );
        push_string_blocker(
            &mut blockers,
            aggregate_calls_memory_search_false,
            "aggregate_calls_memory_search",
        );
        push_string_blocker(
            &mut blockers,
            aggregate_runs_biocortex_false,
            "aggregate_runs_biocortex",
        );
        push_string_blocker(
            &mut blockers,
            aggregate_registers_embedding_backend_false,
            "aggregate_registers_embedding_backend",
        );
        push_string_blocker(
            &mut blockers,
            aggregate_changes_order_false,
            "aggregate_changes_memory_search_order",
        );
        push_string_blocker(
            &mut blockers,
            aggregate_default_order_false,
            "aggregate_default_order_allowed",
        );
        push_string_blocker(
            &mut blockers,
            aggregate_default_calls_unchanged,
            "aggregate_default_calls_changed",
        );
        push_string_blocker(
            &mut blockers,
            aggregate_top_raw_flags_false,
            "aggregate_top_raw_flags_included",
        );
        push_string_blocker(
            &mut blockers,
            aggregate_input_raw_flags_false,
            "aggregate_input_raw_flags_included",
        );
        push_string_blocker(
            &mut blockers,
            aggregate_evidence_raw_flags_false,
            "aggregate_evidence_raw_flags_included",
        );
    }
    if evidence_summary_provided {
        push_string_blocker(
            &mut blockers,
            evidence_summary_schema_ok,
            "evidence_summary_schema_invalid",
        );
        push_string_blocker(
            &mut blockers,
            evidence_summary_read_only,
            "evidence_summary_not_read_only",
        );
        push_string_blocker(
            &mut blockers,
            evidence_summary_is_summary,
            "evidence_summary_marker_missing",
        );
        push_string_blocker(
            &mut blockers,
            evidence_summary_ready,
            "evidence_summary_not_ready",
        );
        push_string_blocker(
            &mut blockers,
            evidence_summary_review_state_ok,
            "evidence_summary_review_state_not_ready",
        );
        push_string_blocker(
            &mut blockers,
            evidence_summary_controlled_rank_movement_observed,
            "evidence_summary_missing_controlled_rank_movement",
        );
        push_string_blocker(
            &mut blockers,
            evidence_summary_default_influence_not_ready,
            "evidence_summary_default_influence_ready",
        );
        push_string_blocker(
            &mut blockers,
            evidence_summary_runtime_readiness_packet_provided,
            "evidence_summary_runtime_readiness_packet_missing",
        );
        push_string_blocker(
            &mut blockers,
            evidence_summary_runtime_readiness_requirement_met,
            "evidence_summary_runtime_readiness_requirement_not_met",
        );
        push_string_blocker(
            &mut blockers,
            evidence_summary_readiness_gated_batch_evidence_ready,
            "evidence_summary_gated_batch_evidence_not_ready",
        );
        push_string_blocker(
            &mut blockers,
            evidence_summary_readiness_matches_batch,
            "evidence_summary_readiness_batch_mismatch",
        );
        push_string_blocker(
            &mut blockers,
            evidence_summary_batch_transition_gated,
            "evidence_summary_batch_not_transition_gated",
        );
        push_string_blocker(
            &mut blockers,
            evidence_summary_approval_state_ok,
            "evidence_summary_approval_state_unexpected",
        );
        push_string_blocker(
            &mut blockers,
            evidence_summary_authorization_state_ok,
            "evidence_summary_authorization_state_unexpected",
        );
        push_string_blocker(
            &mut blockers,
            evidence_summary_approval_writes_false,
            "evidence_summary_approval_writes_allowed",
        );
        push_string_blocker(
            &mut blockers,
            evidence_summary_writes_false,
            "evidence_summary_writes_approval",
        );
        push_string_blocker(
            &mut blockers,
            evidence_summary_calls_memory_search_false,
            "evidence_summary_calls_memory_search",
        );
        push_string_blocker(
            &mut blockers,
            evidence_summary_runs_biocortex_false,
            "evidence_summary_runs_biocortex",
        );
        push_string_blocker(
            &mut blockers,
            evidence_summary_registers_embedding_backend_false,
            "evidence_summary_registers_embedding_backend",
        );
        push_string_blocker(
            &mut blockers,
            evidence_summary_changes_order_false,
            "evidence_summary_changes_memory_search_order",
        );
        push_string_blocker(
            &mut blockers,
            evidence_summary_default_order_false,
            "evidence_summary_default_order_allowed",
        );
        push_string_blocker(
            &mut blockers,
            evidence_summary_default_calls_unchanged,
            "evidence_summary_default_calls_changed",
        );
        push_string_blocker(
            &mut blockers,
            evidence_summary_top_raw_flags_false,
            "evidence_summary_top_raw_flags_included",
        );
        push_string_blocker(
            &mut blockers,
            evidence_summary_input_raw_flags_false,
            "evidence_summary_input_raw_flags_included",
        );
        push_string_blocker(
            &mut blockers,
            evidence_summary_component_raw_flags_false,
            "evidence_summary_component_raw_flags_included",
        );
    }
    if capability_ledger_provided {
        push_string_blocker(
            &mut blockers,
            capability_ledger_schema_ok,
            "capability_ledger_schema_invalid",
        );
        push_string_blocker(
            &mut blockers,
            capability_ledger_accepted,
            "capability_ledger_not_accepted",
        );
        push_string_blocker(
            &mut blockers,
            capability_ledger_read_only,
            "capability_ledger_not_read_only",
        );
        push_string_blocker(
            &mut blockers,
            capability_ledger_static_artifact_only,
            "capability_ledger_not_static_artifact",
        );
        push_string_blocker(
            &mut blockers,
            capability_ledger_memory_writes_false,
            "capability_ledger_memory_write_attempted",
        );
        push_string_blocker(
            &mut blockers,
            capability_ledger_retrieval_order_false,
            "capability_ledger_retrieval_order_change_attempted",
        );
        push_string_blocker(
            &mut blockers,
            capability_ledger_runtime_false,
            "capability_ledger_runtime_authority_observed",
        );
        push_string_blocker(
            &mut blockers,
            capability_ledger_executor_false,
            "capability_ledger_executor_enablement_observed",
        );
        push_string_blocker(
            &mut blockers,
            capability_ledger_mcp_registration_false,
            "capability_ledger_mcp_tool_registration",
        );
        push_string_blocker(
            &mut blockers,
            capability_ledger_nexus_false,
            "capability_ledger_nexus_world_tick_touched",
        );
        push_string_blocker(
            &mut blockers,
            capability_ledger_aiot_false,
            "capability_ledger_aiot_runtime_called",
        );
        push_string_blocker(
            &mut blockers,
            capability_ledger_language_false,
            "capability_ledger_language_generation_observed",
        );
        push_string_blocker(
            &mut blockers,
            capability_ledger_cognition_false,
            "capability_ledger_cognition_claim_observed",
        );
        push_string_blocker(
            &mut blockers,
            capability_ledger_decision_display_only,
            "capability_ledger_decision_not_display_only",
        );
    }

    let request_ready = blockers.is_empty();

    json!({
        "schema": BIOCORTEX_RETRIEVAL_OPT_IN_RUNTIME_INFLUENCE_REVIEW_REQUEST_SCHEMA,
        "generated_at": now_secs(),
        "read_only": true,
        "runtime_influence_review_request": true,
        "implementation_stage": "runtime_influence_review_request_only",
        "request_scope": "explicit_opt_in_fts_runtime_influence_review",
        "purpose": "Prepare a separate human review request for explicit opt-in FTS runtime influence; this packet is not approval and does not connect ordering behavior.",
        "input_contract": {
            "post_implementation_review_gate_schema": gate.get("schema").cloned().unwrap_or(Value::Null),
            "redacted_order_artifact_schema": artifact.get("schema").cloned().unwrap_or(Value::Null),
            "redacted_evidence_aggregate_schema": aggregate_ref
                .and_then(|value| value.get("schema"))
                .cloned()
                .unwrap_or(Value::Null),
            "post_runtime_evidence_summary_schema": evidence_summary_ref
                .and_then(|value| value.get("schema"))
                .cloned()
                .unwrap_or(Value::Null),
            "capability_ledger_report_packet_schema": capability_ledger_ref
                .and_then(|value| value.get("schema"))
                .cloned()
                .unwrap_or(Value::Null),
            "accepts_optional_redacted_evidence_aggregate": true,
            "requires_aggregate_ready_when_provided": true,
            "accepts_optional_post_runtime_evidence_summary": true,
            "requires_post_runtime_evidence_summary_ready_when_provided": true,
            "accepts_optional_capability_ledger_report_packet": true,
            "requires_capability_ledger_accepted_when_provided": true,
            "post_implementation_review_gate_included": false,
            "redacted_order_artifact_included": false,
            "redacted_evidence_aggregate_included": false,
            "post_runtime_evidence_summary_included": false,
            "capability_ledger_report_packet_included": false,
            "unknown_fields_ignored": true,
            "raw_query_included": false,
            "raw_queries_included": false,
            "raw_keys_included": false,
            "content_included": false,
            "side_signal_raw_included": false,
        },
        "review_target": {
            "reviewer": required_or_value(opts.reviewer),
            "commit": required_or_value(opts.commit),
            "forum_post_id": required_or_value(opts.forum_post_id),
            "memory_key": required_or_value(opts.memory_key),
        },
        "requested_authorization": {
            "requested_scope": "explicit_opt_in_fts_runtime_influence_review",
            "request_runtime_adapter_review": true,
            "request_ordering_behavior_connection_review": true,
            "request_default_search_order_change": false,
            "request_hybrid_retrieval_influence": false,
            "request_semantic_retrieval_influence": false,
            "must_keep_per_call_opt_in_required": true,
            "must_keep_operator_disable": BIOCORTEX_RETRIEVAL_DISABLE_ENV,
            "must_return_baseline_without_per_call_opt_in": true,
            "must_fail_open_to_baseline": true,
            "accepts_redacted_evidence_aggregate": true,
            "requires_redacted_evidence_aggregate": false,
            "accepts_post_runtime_evidence_summary": true,
            "requires_post_runtime_evidence_summary": false,
            "accepts_capability_ledger_report_packet": true,
            "requires_capability_ledger_report_packet": false,
            "capability_ledger_can_authorize_runtime_influence": false,
            "this_packet_grants_request": false,
        },
        "evidence_summary": {
            "post_implementation_gate_ready": gate_ready,
            "gate_review_state": gate.get("review_state").cloned().unwrap_or(Value::Null),
            "redacted_order_artifact_ready": artifact_ready,
            "redacted_rows_comparable": artifact_redacted_comparable,
            "baseline_returned": artifact_baseline_returned,
            "actual_return_order_changed": false,
            "top_k_overlap": artifact.pointer("/redacted_order_comparison/top_k_overlap").cloned().unwrap_or(Value::Null),
            "rank_delta_distribution": artifact.pointer("/redacted_order_comparison/rank_delta_distribution").cloned().unwrap_or(Value::Null),
            "redacted_evidence_aggregate_provided": aggregate_provided,
            "redacted_evidence_aggregate_ready": aggregate_ready,
            "aggregate_review_state": aggregate_ref
                .and_then(|value| value.pointer("/interpretation/review_state"))
                .cloned()
                .unwrap_or(Value::Null),
            "controlled_rank_movement_observed": aggregate_controlled_rank_movement_observed,
            "expanded_coverage_without_additional_movement": aggregate_expanded_coverage_without_additional_movement,
            "aggregate_default_influence_ready": if aggregate_provided {
                aggregate_ref
                    .and_then(|value| value.pointer("/interpretation/default_influence_ready"))
                    .cloned()
                    .unwrap_or(Value::Bool(false))
            } else {
                Value::Bool(false)
            },
            "default_influence_ready": false,
            "aggregate_human_review_required": aggregate_provided && aggregate_human_review_required,
            "redacted_evidence_aggregate_summary_included": false,
            "post_runtime_evidence_summary_provided": evidence_summary_provided,
            "post_runtime_evidence_summary_ready": evidence_summary_ready,
            "post_runtime_evidence_summary_review_state": evidence_summary_ref
                .and_then(|value| value.pointer("/interpretation/review_state"))
                .cloned()
                .unwrap_or(Value::Null),
            "post_runtime_evidence_summary_default_influence_ready": if evidence_summary_provided {
                evidence_summary_ref
                    .and_then(|value| value.pointer("/interpretation/default_influence_ready"))
                    .cloned()
                    .unwrap_or(Value::Bool(false))
            } else {
                Value::Bool(false)
            },
            "post_runtime_controlled_rank_movement_observed": evidence_summary_controlled_rank_movement_observed,
            "post_runtime_runtime_readiness_packet_provided": evidence_summary_runtime_readiness_packet_provided,
            "post_runtime_runtime_readiness_requirement_met": evidence_summary_runtime_readiness_requirement_met,
            "post_runtime_readiness_gated_batch_evidence_ready": evidence_summary_readiness_gated_batch_evidence_ready,
            "post_runtime_batch_transition_gated": evidence_summary_batch_transition_gated,
            "post_runtime_batch_evidence_source": if evidence_summary_provided {
                Value::String(evidence_summary_batch_evidence_source.to_string())
            } else {
                Value::Null
            },
            "post_runtime_evidence_summary_included": false,
            "capability_ledger_report_packet_provided": capability_ledger_provided,
            "capability_ledger_report_packet_accepted": capability_ledger_accepted,
            "capability_ledger_read_only_confirmed": capability_ledger_provided && capability_ledger_read_only,
            "capability_ledger_input_schema": capability_ledger_ref
                .and_then(|value| value.pointer("/input_schema"))
                .cloned()
                .unwrap_or(Value::Null),
            "capability_ledger_input_schema_version": capability_ledger_ref
                .and_then(|value| value.pointer("/input_schema_version"))
                .cloned()
                .unwrap_or(Value::Null),
            "capability_ledger_downstream_action": capability_ledger_ref
                .and_then(|value| value.pointer("/downstream_action"))
                .cloned()
                .unwrap_or(Value::Null),
            "capability_ledger_integration_decision": capability_ledger_ref
                .and_then(|value| value.pointer("/integration_decision"))
                .cloned()
                .unwrap_or(Value::Null),
            "capability_ledger_report_packet_included": false,
            "runtime_adapter_approved": false,
            "default_search_order_change_allowed": false,
            "ordering_behavior_connected": false,
        },
        "boundary_check": {
            "runtime_influence_review_request_ready": request_ready,
            "blockers": blockers,
            "gate_schema_ok": gate_schema_ok,
            "gate_ready": gate_ready,
            "gate_runtime_adapter_still_not_approved": gate_runtime_not_approved,
            "gate_default_order_still_not_allowed": gate_default_order_not_allowed,
            "artifact_schema_ok": artifact_schema_ok,
            "artifact_ready": artifact_ready,
            "artifact_redacted_rows_comparable": artifact_redacted_comparable,
            "artifact_returned_baseline": artifact_baseline_returned,
            "artifact_return_order_unchanged": artifact_return_order_unchanged,
            "redacted_evidence_aggregate_provided": aggregate_provided,
            "redacted_evidence_aggregate_ready": aggregate_ready,
            "aggregate_schema_ok": aggregate_schema_ok,
            "aggregate_safe_for_review": aggregate_safe_for_review,
            "post_runtime_evidence_summary_provided": evidence_summary_provided,
            "post_runtime_evidence_summary_ready": evidence_summary_ready,
            "post_runtime_evidence_summary_schema_ok": evidence_summary_schema_ok,
            "post_runtime_evidence_summary_safe_for_review": evidence_summary_safe_for_review,
            "post_runtime_evidence_summary_gated_readiness_ready": evidence_summary_readiness_gated_batch_evidence_ready,
            "capability_ledger_report_packet_provided": capability_ledger_provided,
            "capability_ledger_report_packet_accepted": capability_ledger_accepted,
            "capability_ledger_report_packet_schema_ok": capability_ledger_schema_ok,
            "capability_ledger_report_packet_safe_for_review": capability_ledger_safe_for_review,
            "capability_ledger_read_only_confirmed": capability_ledger_provided && capability_ledger_read_only,
            "capability_ledger_decision_display_only": !capability_ledger_provided
                || capability_ledger_decision_display_only,
        },
        "required_human_decision": {
            "decision_schema": "agent_bridge.biocortex_retrieval.opt_in_runtime_influence_review_decision.v0",
            "decision_required_before_runtime_adapter": true,
            "decision_required_before_ordering_connection": true,
            "must_state_scope_explicit_opt_in_fts_only": true,
            "must_keep_default_search_order_change_allowed_false": true,
            "must_keep_hybrid_semantic_not_authorized": true,
        },
        "review_request_state": if request_ready {
            "ready_for_human_runtime_influence_review"
        } else {
            "blocked"
        },
        "approval_state": "not_approved",
        "authorization_state": "runtime_influence_review_requested_not_granted",
        "implementation_allowed": false,
        "runtime_adapter_approved": false,
        "approval_writes_allowed": false,
        "writes_approval": false,
        "calls_memory_search": false,
        "runs_biocortex": false,
        "registers_embedding_backend": false,
        "changes_memory_search_order": false,
        "default_search_order_change_allowed": false,
        "ordering_behavior_connected": false,
        "may_change_search_order_now": false,
        "may_implement_ordering_now": false,
        "default_calls_unchanged": true,
        "boundary": retrieval_boundary_payload(),
    })
}

pub fn biocortex_retrieval_opt_in_runtime_influence_decision_packet(
    opts: BioCortexRetrievalOptInRuntimeInfluenceDecisionPacketOptions,
) -> Value {
    let request = opts.runtime_influence_review_request;
    let decision = opts.runtime_influence_decision;

    let decision_schema_ok = value_str_eq(
        decision.get("schema"),
        "agent_bridge.biocortex_retrieval.opt_in_runtime_influence_review_decision.v0",
    );
    let decision_authorized = value_str_eq(decision.get("decision"), "authorized")
        && value_str_eq(decision.get("authorization_state"), "authorized");
    let decision_scope_ok = value_str_eq(
        decision.get("authorized_scope"),
        "explicit_opt_in_fts_runtime_influence",
    );
    let decision_runtime_adapter_approved =
        value_bool_is(decision.get("runtime_adapter_approved"), true);
    let decision_ordering_connection_authorized = value_bool_is(
        decision.get("ordering_behavior_connection_authorized"),
        true,
    );
    let decision_default_order_not_allowed =
        value_bool_is(decision.get("default_search_order_change_allowed"), false);
    let decision_default_influence_not_authorized = value_bool_is(
        decision.get("default_retrieval_influence_authorized"),
        false,
    );
    let decision_hybrid_not_authorized =
        value_bool_is(decision.get("hybrid_retrieval_influence_authorized"), false);
    let decision_semantic_not_authorized = value_bool_is(
        decision.get("semantic_retrieval_influence_authorized"),
        false,
    );
    let runtime = decision
        .get("authorized_runtime_influence")
        .unwrap_or(&Value::Null);
    let decision_runtime_adapter_fts = value_bool_is(
        runtime.get("may_run_runtime_adapter_for_explicit_opt_in_fts"),
        true,
    );
    let decision_ordering_fts = value_bool_is(
        runtime.get("may_connect_ordering_behavior_for_explicit_opt_in_fts"),
        true,
    );
    let decision_fts_only = value_bool_is(
        runtime.get("may_affect_only_explicitly_opted_in_fts_calls"),
        true,
    );
    let decision_per_call_required = value_bool_is(runtime.get("requires_per_call_opt_in"), true);
    let decision_baseline_recall =
        value_bool_is(runtime.get("must_keep_baseline_candidate_recall"), true);
    let decision_default_calls_unchanged =
        value_bool_is(runtime.get("must_keep_default_calls_unchanged"), true);
    let decision_redacted_audit = value_bool_is(runtime.get("must_keep_redacted_audit_only"), true);
    let decision_kill_switch_ok = value_str_eq(
        runtime.get("must_keep_operator_disable"),
        BIOCORTEX_RETRIEVAL_DISABLE_ENV,
    );
    let decision_baseline_without_opt_in = value_bool_is(
        runtime.get("must_return_baseline_without_per_call_opt_in"),
        true,
    );
    let decision_fail_open = value_bool_is(runtime.get("must_fail_open_to_baseline"), true);
    let decision_not_authorizes_default_order = array_contains_str(
        decision.get("not_authorized"),
        "default_search_order_change_allowed",
    );
    let decision_not_authorizes_default_fts = array_contains_str(
        decision.get("not_authorized"),
        "default_retrieval_influence_fts",
    );
    let decision_not_authorizes_hybrid =
        array_contains_str(decision.get("not_authorized"), "hybrid_retrieval_influence");
    let decision_not_authorizes_semantic = array_contains_str(
        decision.get("not_authorized"),
        "semantic_retrieval_influence",
    );
    let decision_not_authorizes_without_opt_in = array_contains_str(
        decision.get("not_authorized"),
        "affecting_calls_without_explicit_opt_in",
    );

    let request_schema_ok = value_str_eq(
        request.get("schema"),
        BIOCORTEX_RETRIEVAL_OPT_IN_RUNTIME_INFLUENCE_REVIEW_REQUEST_SCHEMA,
    );
    let request_read_only = value_bool_is(request.get("read_only"), true);
    let request_is_review_request =
        value_bool_is(request.get("runtime_influence_review_request"), true);
    let request_ready = value_bool_is(
        request.pointer("/boundary_check/runtime_influence_review_request_ready"),
        true,
    ) && value_str_eq(
        request.get("review_request_state"),
        "ready_for_human_runtime_influence_review",
    );
    let request_scope_ok = value_str_eq(
        request.get("request_scope"),
        "explicit_opt_in_fts_runtime_influence_review",
    );
    let request_approval_state_ok = value_str_eq(request.get("approval_state"), "not_approved");
    let request_authorization_state_ok = value_str_eq(
        request.get("authorization_state"),
        "runtime_influence_review_requested_not_granted",
    );
    let request_runtime_reviewed = value_bool_is(
        request.pointer("/requested_authorization/request_runtime_adapter_review"),
        true,
    );
    let request_ordering_reviewed = value_bool_is(
        request.pointer("/requested_authorization/request_ordering_behavior_connection_review"),
        true,
    );
    let request_default_order_not_requested = value_bool_is(
        request.pointer("/requested_authorization/request_default_search_order_change"),
        false,
    );
    let request_hybrid_not_requested = value_bool_is(
        request.pointer("/requested_authorization/request_hybrid_retrieval_influence"),
        false,
    );
    let request_semantic_not_requested = value_bool_is(
        request.pointer("/requested_authorization/request_semantic_retrieval_influence"),
        false,
    );
    let request_grants_nothing = value_bool_is(
        request.pointer("/requested_authorization/this_packet_grants_request"),
        false,
    );
    let request_per_call_required = value_bool_is(
        request.pointer("/requested_authorization/must_keep_per_call_opt_in_required"),
        true,
    );
    let request_kill_switch_ok = value_str_eq(
        request.pointer("/requested_authorization/must_keep_operator_disable"),
        BIOCORTEX_RETRIEVAL_DISABLE_ENV,
    );
    let request_baseline_without_opt_in = value_bool_is(
        request.pointer("/requested_authorization/must_return_baseline_without_per_call_opt_in"),
        true,
    );
    let request_fail_open = value_bool_is(
        request.pointer("/requested_authorization/must_fail_open_to_baseline"),
        true,
    );
    let request_runtime_not_approved =
        value_bool_is(request.get("runtime_adapter_approved"), false);
    let request_default_order_false =
        value_bool_is(request.get("default_search_order_change_allowed"), false);
    let request_writes_false = value_bool_is(request.get("writes_approval"), false);
    let request_calls_memory_false = value_bool_is(request.get("calls_memory_search"), false);
    let request_runs_biocortex_false = value_bool_is(request.get("runs_biocortex"), false);
    let request_changes_order_false =
        value_bool_is(request.get("changes_memory_search_order"), false);
    let request_ordering_connected_false =
        value_bool_is(request.get("ordering_behavior_connected"), false);
    let request_may_change_order_false =
        value_bool_is(request.get("may_change_search_order_now"), false);
    let request_may_implement_ordering_false =
        value_bool_is(request.get("may_implement_ordering_now"), false);
    let request_baseline_returned =
        value_bool_is(request.pointer("/evidence_summary/baseline_returned"), true);
    let request_return_order_unchanged = value_bool_is(
        request.pointer("/evidence_summary/actual_return_order_changed"),
        false,
    );
    let request_aggregate_provided = value_bool_is(
        request.pointer("/evidence_summary/redacted_evidence_aggregate_provided"),
        true,
    ) || value_bool_is(
        request.pointer("/boundary_check/redacted_evidence_aggregate_provided"),
        true,
    );
    let request_accepts_optional_aggregate = value_bool_is(
        request.pointer("/input_contract/accepts_optional_redacted_evidence_aggregate"),
        true,
    ) && value_bool_is(
        request.pointer("/requested_authorization/accepts_redacted_evidence_aggregate"),
        true,
    ) && value_bool_is(
        request.pointer("/requested_authorization/requires_redacted_evidence_aggregate"),
        false,
    );
    let request_aggregate_redacted = value_bool_is(
        request.pointer("/input_contract/redacted_evidence_aggregate_included"),
        false,
    ) && value_bool_is(
        request.pointer("/evidence_summary/redacted_evidence_aggregate_summary_included"),
        false,
    );
    let request_aggregate_ready = value_bool_is(
        request.pointer("/evidence_summary/redacted_evidence_aggregate_ready"),
        true,
    ) && value_bool_is(
        request.pointer("/boundary_check/redacted_evidence_aggregate_ready"),
        true,
    );
    let request_aggregate_review_state_ok = value_str_eq(
        request.pointer("/evidence_summary/aggregate_review_state"),
        "redacted_aggregate_ready",
    );
    let request_aggregate_movement_observed = value_bool_is(
        request.pointer("/evidence_summary/controlled_rank_movement_observed"),
        true,
    );
    let request_aggregate_coverage_observed = value_bool_is(
        request.pointer("/evidence_summary/expanded_coverage_without_additional_movement"),
        true,
    );
    let request_aggregate_default_influence_not_ready = value_bool_is(
        request.pointer("/evidence_summary/aggregate_default_influence_ready"),
        false,
    ) && value_bool_is(
        request.pointer("/evidence_summary/default_influence_ready"),
        false,
    );
    let request_aggregate_human_review_required = value_bool_is(
        request.pointer("/evidence_summary/aggregate_human_review_required"),
        true,
    );
    let request_aggregate_boundary_safe =
        value_bool_is(request.pointer("/boundary_check/aggregate_schema_ok"), true)
            && value_bool_is(
                request.pointer("/boundary_check/aggregate_safe_for_review"),
                true,
            );
    let request_aggregate_safe_for_decision = if request_aggregate_provided {
        request_accepts_optional_aggregate
            && request_aggregate_redacted
            && request_aggregate_ready
            && request_aggregate_review_state_ok
            && request_aggregate_movement_observed
            && request_aggregate_coverage_observed
            && request_aggregate_default_influence_not_ready
            && request_aggregate_human_review_required
            && request_aggregate_boundary_safe
    } else {
        true
    };
    let request_aggregate_review_evidence_state = if request_aggregate_provided {
        if request_aggregate_safe_for_decision {
            "redacted_aggregate_ready"
        } else {
            "blocked"
        }
    } else {
        "not_provided_legacy_compatible"
    };
    let request_post_runtime_evidence_provided = value_bool_is(
        request.pointer("/evidence_summary/post_runtime_evidence_summary_provided"),
        true,
    ) || value_bool_is(
        request.pointer("/boundary_check/post_runtime_evidence_summary_provided"),
        true,
    );
    let request_accepts_optional_post_runtime_evidence = value_bool_is(
        request.pointer("/input_contract/accepts_optional_post_runtime_evidence_summary"),
        true,
    ) && value_bool_is(
        request
            .pointer("/input_contract/requires_post_runtime_evidence_summary_ready_when_provided"),
        true,
    ) && value_bool_is(
        request.pointer("/requested_authorization/accepts_post_runtime_evidence_summary"),
        true,
    ) && value_bool_is(
        request.pointer("/requested_authorization/requires_post_runtime_evidence_summary"),
        false,
    );
    let request_post_runtime_evidence_redacted = value_bool_is(
        request.pointer("/input_contract/post_runtime_evidence_summary_included"),
        false,
    ) && value_bool_is(
        request.pointer("/evidence_summary/post_runtime_evidence_summary_included"),
        false,
    );
    let request_post_runtime_evidence_ready = value_bool_is(
        request.pointer("/evidence_summary/post_runtime_evidence_summary_ready"),
        true,
    ) && value_bool_is(
        request.pointer("/boundary_check/post_runtime_evidence_summary_ready"),
        true,
    );
    let request_post_runtime_evidence_review_state_ok = value_str_eq(
        request.pointer("/evidence_summary/post_runtime_evidence_summary_review_state"),
        "post_runtime_evidence_ready",
    );
    let request_post_runtime_evidence_movement_observed = value_bool_is(
        request.pointer("/evidence_summary/post_runtime_controlled_rank_movement_observed"),
        true,
    );
    let request_post_runtime_evidence_default_influence_not_ready = value_bool_is(
        request.pointer("/evidence_summary/post_runtime_evidence_summary_default_influence_ready"),
        false,
    ) && value_bool_is(
        request.pointer("/evidence_summary/default_influence_ready"),
        false,
    );
    let request_post_runtime_readiness_packet_provided = value_bool_is(
        request.pointer("/evidence_summary/post_runtime_runtime_readiness_packet_provided"),
        true,
    );
    let request_post_runtime_readiness_requirement_met = value_bool_is(
        request.pointer("/evidence_summary/post_runtime_runtime_readiness_requirement_met"),
        true,
    );
    let request_post_runtime_gated_batch_ready = value_bool_is(
        request.pointer("/evidence_summary/post_runtime_readiness_gated_batch_evidence_ready"),
        true,
    ) && value_bool_is(
        request.pointer("/boundary_check/post_runtime_evidence_summary_gated_readiness_ready"),
        true,
    );
    let request_post_runtime_batch_transition_gated = value_bool_is(
        request.pointer("/evidence_summary/post_runtime_batch_transition_gated"),
        true,
    ) && value_str_eq(
        request.pointer("/evidence_summary/post_runtime_batch_evidence_source"),
        "runtime_transition_gated_batch_diagnostics",
    );
    let request_post_runtime_evidence_boundary_safe = value_bool_is(
        request.pointer("/boundary_check/post_runtime_evidence_summary_schema_ok"),
        true,
    ) && value_bool_is(
        request.pointer("/boundary_check/post_runtime_evidence_summary_safe_for_review"),
        true,
    );
    let request_post_runtime_evidence_safe_for_decision = if request_post_runtime_evidence_provided
    {
        request_accepts_optional_post_runtime_evidence
            && request_post_runtime_evidence_redacted
            && request_post_runtime_evidence_ready
            && request_post_runtime_evidence_review_state_ok
            && request_post_runtime_evidence_movement_observed
            && request_post_runtime_evidence_default_influence_not_ready
            && request_post_runtime_readiness_packet_provided
            && request_post_runtime_readiness_requirement_met
            && request_post_runtime_gated_batch_ready
            && request_post_runtime_batch_transition_gated
            && request_post_runtime_evidence_boundary_safe
    } else {
        true
    };
    let request_post_runtime_evidence_state = if request_post_runtime_evidence_provided {
        if request_post_runtime_evidence_safe_for_decision {
            "post_runtime_evidence_ready"
        } else {
            "blocked"
        }
    } else {
        "not_provided_legacy_compatible"
    };
    let request_capability_ledger_provided = value_bool_is(
        request.pointer("/evidence_summary/capability_ledger_report_packet_provided"),
        true,
    ) || value_bool_is(
        request.pointer("/boundary_check/capability_ledger_report_packet_provided"),
        true,
    );
    let request_accepts_optional_capability_ledger = value_bool_is(
        request.pointer("/input_contract/accepts_optional_capability_ledger_report_packet"),
        true,
    ) && value_bool_is(
        request.pointer("/input_contract/requires_capability_ledger_accepted_when_provided"),
        true,
    ) && value_bool_is(
        request.pointer("/requested_authorization/accepts_capability_ledger_report_packet"),
        true,
    ) && value_bool_is(
        request.pointer("/requested_authorization/requires_capability_ledger_report_packet"),
        false,
    );
    let request_capability_ledger_redacted = value_bool_is(
        request.pointer("/input_contract/capability_ledger_report_packet_included"),
        false,
    ) && value_bool_is(
        request.pointer("/evidence_summary/capability_ledger_report_packet_included"),
        false,
    );
    let request_capability_ledger_accepted = value_bool_is(
        request.pointer("/evidence_summary/capability_ledger_report_packet_accepted"),
        true,
    ) && value_bool_is(
        request.pointer("/boundary_check/capability_ledger_report_packet_accepted"),
        true,
    );
    let request_capability_ledger_read_only = value_bool_is(
        request.pointer("/evidence_summary/capability_ledger_read_only_confirmed"),
        true,
    ) && value_bool_is(
        request.pointer("/boundary_check/capability_ledger_read_only_confirmed"),
        true,
    );
    let request_capability_ledger_boundary_safe = value_bool_is(
        request.pointer("/boundary_check/capability_ledger_report_packet_schema_ok"),
        true,
    ) && value_bool_is(
        request.pointer("/boundary_check/capability_ledger_report_packet_safe_for_review"),
        true,
    );
    let request_capability_ledger_authorizes_nothing = value_bool_is(
        request
            .pointer("/requested_authorization/capability_ledger_can_authorize_runtime_influence"),
        false,
    );
    let request_capability_ledger_downstream_action_display_only = value_str_eq(
        request.pointer("/evidence_summary/capability_ledger_downstream_action"),
        "display_or_review_only",
    );
    let request_capability_ledger_integration_decision_display_only = value_str_eq(
        request.pointer("/evidence_summary/capability_ledger_integration_decision"),
        "shadow_only_no_runtime_admission",
    );
    let request_capability_ledger_decision_display_only = if request_capability_ledger_provided {
        request_capability_ledger_downstream_action_display_only
            && request_capability_ledger_integration_decision_display_only
    } else {
        true
    };
    let request_capability_ledger_safe_for_decision = if request_capability_ledger_provided {
        request_accepts_optional_capability_ledger
            && request_capability_ledger_redacted
            && request_capability_ledger_accepted
            && request_capability_ledger_read_only
            && request_capability_ledger_boundary_safe
            && request_capability_ledger_authorizes_nothing
            && request_capability_ledger_decision_display_only
    } else {
        true
    };
    let request_capability_ledger_state = if request_capability_ledger_provided {
        if request_capability_ledger_safe_for_decision {
            "capability_ledger_accepted_for_review_only"
        } else {
            "blocked"
        }
    } else {
        "not_provided_legacy_compatible"
    };

    let mut blockers = Vec::new();
    push_string_blocker(&mut blockers, decision_schema_ok, "decision_schema_invalid");
    push_string_blocker(
        &mut blockers,
        decision_authorized,
        "decision_not_authorized",
    );
    push_string_blocker(
        &mut blockers,
        decision_scope_ok,
        "decision_scope_not_explicit_opt_in_fts",
    );
    push_string_blocker(
        &mut blockers,
        decision_runtime_adapter_approved,
        "decision_runtime_adapter_not_approved",
    );
    push_string_blocker(
        &mut blockers,
        decision_ordering_connection_authorized,
        "decision_ordering_connection_not_authorized",
    );
    push_string_blocker(
        &mut blockers,
        decision_default_order_not_allowed,
        "decision_default_order_allowed",
    );
    push_string_blocker(
        &mut blockers,
        decision_default_influence_not_authorized,
        "decision_default_influence_authorized",
    );
    push_string_blocker(
        &mut blockers,
        decision_hybrid_not_authorized,
        "decision_hybrid_influence_authorized",
    );
    push_string_blocker(
        &mut blockers,
        decision_semantic_not_authorized,
        "decision_semantic_influence_authorized",
    );
    push_string_blocker(
        &mut blockers,
        decision_runtime_adapter_fts,
        "decision_runtime_adapter_not_fts_only",
    );
    push_string_blocker(
        &mut blockers,
        decision_ordering_fts,
        "decision_ordering_not_fts_only",
    );
    push_string_blocker(&mut blockers, decision_fts_only, "decision_not_fts_only");
    push_string_blocker(
        &mut blockers,
        decision_per_call_required,
        "decision_missing_per_call_opt_in_requirement",
    );
    push_string_blocker(
        &mut blockers,
        decision_baseline_recall,
        "decision_missing_baseline_candidate_recall_rule",
    );
    push_string_blocker(
        &mut blockers,
        decision_default_calls_unchanged,
        "decision_missing_default_calls_unchanged_rule",
    );
    push_string_blocker(
        &mut blockers,
        decision_redacted_audit,
        "decision_missing_redacted_audit_rule",
    );
    push_string_blocker(
        &mut blockers,
        decision_kill_switch_ok,
        "decision_kill_switch_mismatch",
    );
    push_string_blocker(
        &mut blockers,
        decision_baseline_without_opt_in,
        "decision_missing_baseline_without_opt_in_rule",
    );
    push_string_blocker(
        &mut blockers,
        decision_fail_open,
        "decision_missing_fail_open_rule",
    );
    push_string_blocker(
        &mut blockers,
        decision_not_authorizes_default_order,
        "decision_not_authorized_missing_default_order",
    );
    push_string_blocker(
        &mut blockers,
        decision_not_authorizes_default_fts,
        "decision_not_authorized_missing_default_fts",
    );
    push_string_blocker(
        &mut blockers,
        decision_not_authorizes_hybrid,
        "decision_not_authorized_missing_hybrid",
    );
    push_string_blocker(
        &mut blockers,
        decision_not_authorizes_semantic,
        "decision_not_authorized_missing_semantic",
    );
    push_string_blocker(
        &mut blockers,
        decision_not_authorizes_without_opt_in,
        "decision_not_authorized_missing_without_opt_in",
    );
    push_string_blocker(&mut blockers, request_schema_ok, "request_schema_invalid");
    push_string_blocker(&mut blockers, request_read_only, "request_not_read_only");
    push_string_blocker(
        &mut blockers,
        request_is_review_request,
        "request_not_runtime_influence_review_request",
    );
    push_string_blocker(&mut blockers, request_ready, "request_not_ready");
    push_string_blocker(&mut blockers, request_scope_ok, "request_scope_unexpected");
    push_string_blocker(
        &mut blockers,
        request_approval_state_ok,
        "request_approval_state_unexpected",
    );
    push_string_blocker(
        &mut blockers,
        request_authorization_state_ok,
        "request_authorization_state_unexpected",
    );
    push_string_blocker(
        &mut blockers,
        request_runtime_reviewed,
        "request_missing_runtime_review_request",
    );
    push_string_blocker(
        &mut blockers,
        request_ordering_reviewed,
        "request_missing_ordering_review_request",
    );
    push_string_blocker(
        &mut blockers,
        request_default_order_not_requested,
        "request_requested_default_order_change",
    );
    push_string_blocker(
        &mut blockers,
        request_hybrid_not_requested,
        "request_requested_hybrid_influence",
    );
    push_string_blocker(
        &mut blockers,
        request_semantic_not_requested,
        "request_requested_semantic_influence",
    );
    push_string_blocker(
        &mut blockers,
        request_grants_nothing,
        "request_grants_approval",
    );
    push_string_blocker(
        &mut blockers,
        request_per_call_required,
        "request_missing_per_call_opt_in_requirement",
    );
    push_string_blocker(
        &mut blockers,
        request_kill_switch_ok,
        "request_kill_switch_mismatch",
    );
    push_string_blocker(
        &mut blockers,
        request_baseline_without_opt_in,
        "request_missing_baseline_without_opt_in_rule",
    );
    push_string_blocker(
        &mut blockers,
        request_fail_open,
        "request_missing_fail_open_rule",
    );
    push_string_blocker(
        &mut blockers,
        request_runtime_not_approved,
        "request_runtime_adapter_already_approved",
    );
    push_string_blocker(
        &mut blockers,
        request_default_order_false,
        "request_default_order_allowed",
    );
    push_string_blocker(
        &mut blockers,
        request_writes_false,
        "request_writes_approval",
    );
    push_string_blocker(
        &mut blockers,
        request_calls_memory_false,
        "request_calls_memory_search",
    );
    push_string_blocker(
        &mut blockers,
        request_runs_biocortex_false,
        "request_runs_biocortex",
    );
    push_string_blocker(
        &mut blockers,
        request_changes_order_false,
        "request_changes_memory_search_order",
    );
    push_string_blocker(
        &mut blockers,
        request_ordering_connected_false,
        "request_ordering_connected",
    );
    push_string_blocker(
        &mut blockers,
        request_may_change_order_false,
        "request_may_change_order_now",
    );
    push_string_blocker(
        &mut blockers,
        request_may_implement_ordering_false,
        "request_may_implement_ordering_now",
    );
    push_string_blocker(
        &mut blockers,
        request_baseline_returned,
        "request_baseline_not_returned",
    );
    push_string_blocker(
        &mut blockers,
        request_return_order_unchanged,
        "request_return_order_changed",
    );
    if request_aggregate_provided {
        push_string_blocker(
            &mut blockers,
            request_accepts_optional_aggregate,
            "request_aggregate_contract_unexpected",
        );
        push_string_blocker(
            &mut blockers,
            request_aggregate_redacted,
            "request_aggregate_summary_not_redacted",
        );
        push_string_blocker(
            &mut blockers,
            request_aggregate_ready,
            "request_aggregate_not_ready_for_decision",
        );
        push_string_blocker(
            &mut blockers,
            request_aggregate_review_state_ok,
            "request_aggregate_review_state_unexpected",
        );
        push_string_blocker(
            &mut blockers,
            request_aggregate_movement_observed,
            "request_aggregate_missing_controlled_rank_movement",
        );
        push_string_blocker(
            &mut blockers,
            request_aggregate_coverage_observed,
            "request_aggregate_missing_expanded_coverage",
        );
        push_string_blocker(
            &mut blockers,
            request_aggregate_default_influence_not_ready,
            "request_aggregate_default_influence_ready",
        );
        push_string_blocker(
            &mut blockers,
            request_aggregate_human_review_required,
            "request_aggregate_missing_human_review_requirement",
        );
        push_string_blocker(
            &mut blockers,
            request_aggregate_boundary_safe,
            "request_aggregate_boundary_not_safe",
        );
    }
    if request_post_runtime_evidence_provided {
        push_string_blocker(
            &mut blockers,
            request_accepts_optional_post_runtime_evidence,
            "request_post_runtime_evidence_contract_unexpected",
        );
        push_string_blocker(
            &mut blockers,
            request_post_runtime_evidence_redacted,
            "request_post_runtime_evidence_summary_not_redacted",
        );
        push_string_blocker(
            &mut blockers,
            request_post_runtime_evidence_ready,
            "request_post_runtime_evidence_not_ready_for_decision",
        );
        push_string_blocker(
            &mut blockers,
            request_post_runtime_evidence_review_state_ok,
            "request_post_runtime_evidence_review_state_unexpected",
        );
        push_string_blocker(
            &mut blockers,
            request_post_runtime_evidence_movement_observed,
            "request_post_runtime_evidence_missing_controlled_rank_movement",
        );
        push_string_blocker(
            &mut blockers,
            request_post_runtime_evidence_default_influence_not_ready,
            "request_post_runtime_evidence_default_influence_ready",
        );
        push_string_blocker(
            &mut blockers,
            request_post_runtime_readiness_packet_provided,
            "request_post_runtime_evidence_runtime_readiness_packet_missing",
        );
        push_string_blocker(
            &mut blockers,
            request_post_runtime_readiness_requirement_met,
            "request_post_runtime_evidence_runtime_readiness_requirement_not_met",
        );
        push_string_blocker(
            &mut blockers,
            request_post_runtime_gated_batch_ready,
            "request_post_runtime_evidence_gated_batch_not_ready",
        );
        push_string_blocker(
            &mut blockers,
            request_post_runtime_batch_transition_gated,
            "request_post_runtime_evidence_batch_not_transition_gated",
        );
        push_string_blocker(
            &mut blockers,
            request_post_runtime_evidence_boundary_safe,
            "request_post_runtime_evidence_boundary_not_safe",
        );
    }
    if request_capability_ledger_provided {
        push_string_blocker(
            &mut blockers,
            request_accepts_optional_capability_ledger,
            "request_capability_ledger_contract_unexpected",
        );
        push_string_blocker(
            &mut blockers,
            request_capability_ledger_redacted,
            "request_capability_ledger_summary_not_redacted",
        );
        push_string_blocker(
            &mut blockers,
            request_capability_ledger_accepted,
            "request_capability_ledger_not_accepted",
        );
        push_string_blocker(
            &mut blockers,
            request_capability_ledger_read_only,
            "request_capability_ledger_not_read_only",
        );
        push_string_blocker(
            &mut blockers,
            request_capability_ledger_boundary_safe,
            "request_capability_ledger_boundary_not_safe",
        );
        push_string_blocker(
            &mut blockers,
            request_capability_ledger_authorizes_nothing,
            "request_capability_ledger_authorizes_runtime_influence",
        );
        push_string_blocker(
            &mut blockers,
            request_capability_ledger_decision_display_only,
            "request_capability_ledger_decision_not_display_only",
        );
    }

    let runtime_influence_authorized = blockers.is_empty();

    json!({
        "schema": BIOCORTEX_RETRIEVAL_OPT_IN_RUNTIME_INFLUENCE_DECISION_PACKET_SCHEMA,
        "generated_at": now_secs(),
        "read_only": true,
        "runtime_influence_decision_consumer": true,
        "implementation_stage": "runtime_influence_decision_consumer_only",
        "authorization_scope": "explicit_opt_in_fts_runtime_influence",
        "purpose": "Consume a separate human runtime-influence review decision; this packet is read-only and does not connect ordering behavior itself.",
        "input_contract": {
            "runtime_influence_review_request_schema": request.get("schema").cloned().unwrap_or(Value::Null),
            "runtime_influence_decision_schema": decision.get("schema").cloned().unwrap_or(Value::Null),
            "runtime_influence_review_request_included": false,
            "runtime_influence_decision_included": false,
            "accepts_aggregate_backed_review_request": true,
            "requires_aggregate_ready_when_provided": true,
            "redacted_evidence_aggregate_included": false,
            "accepts_post_runtime_evidence_summary_review_request": true,
            "requires_post_runtime_evidence_summary_ready_when_provided": true,
            "post_runtime_evidence_summary_included": false,
            "accepts_capability_ledger_backed_review_request": true,
            "requires_capability_ledger_safe_when_provided": true,
            "capability_ledger_report_packet_included": false,
            "unknown_fields_ignored": true,
            "raw_query_included": false,
            "raw_keys_included": false,
            "content_included": false,
            "human_decision_text_included": false,
        },
        "review_target": {
            "reviewer": required_or_value(opts.reviewer),
            "commit": required_or_value(opts.commit),
            "forum_post_id": required_or_value(opts.forum_post_id),
            "memory_key": required_or_value(opts.memory_key),
        },
        "decision_summary": {
            "decision": decision.get("decision").cloned().unwrap_or(Value::Null),
            "authorization_state": decision
                .get("authorization_state")
                .cloned()
                .unwrap_or(Value::Null),
            "authorized_scope": decision
                .get("authorized_scope")
                .cloned()
                .unwrap_or(Value::Null),
            "runtime_adapter_approved": runtime_influence_authorized,
            "ordering_behavior_connection_authorized": runtime_influence_authorized,
            "default_search_order_change_allowed": false,
            "default_retrieval_influence_authorized": false,
            "hybrid_retrieval_influence_authorized": false,
            "semantic_retrieval_influence_authorized": false,
        },
        "request_summary": {
            "request_scope": request.get("request_scope").cloned().unwrap_or(Value::Null),
            "review_request_state": request
                .get("review_request_state")
                .cloned()
                .unwrap_or(Value::Null),
            "approval_state": request.get("approval_state").cloned().unwrap_or(Value::Null),
            "authorization_state": request.get("authorization_state").cloned().unwrap_or(Value::Null),
            "runtime_influence_review_request_ready": request
                .pointer("/boundary_check/runtime_influence_review_request_ready")
                .cloned()
                .unwrap_or(Value::Null),
            "requested_runtime_adapter_review": request
                .pointer("/requested_authorization/request_runtime_adapter_review")
                .cloned()
                .unwrap_or(Value::Null),
            "requested_ordering_behavior_connection_review": request
                .pointer("/requested_authorization/request_ordering_behavior_connection_review")
                .cloned()
                .unwrap_or(Value::Null),
            "requested_default_search_order_change": false,
            "requested_hybrid_retrieval_influence": false,
            "requested_semantic_retrieval_influence": false,
            "request_packet_granted_nothing": request_grants_nothing,
            "aggregate_backed_review_request": request_aggregate_provided,
            "aggregate_review_evidence_state": request_aggregate_review_evidence_state,
            "redacted_evidence_aggregate_provided": request_aggregate_provided,
            "redacted_evidence_aggregate_ready": request_aggregate_ready,
            "aggregate_review_state": request
                .pointer("/evidence_summary/aggregate_review_state")
                .cloned()
                .unwrap_or(Value::Null),
            "controlled_rank_movement_observed": request_aggregate_movement_observed,
            "expanded_coverage_without_additional_movement": request_aggregate_coverage_observed,
            "aggregate_default_influence_ready": if request_aggregate_provided {
                request
                    .pointer("/evidence_summary/aggregate_default_influence_ready")
                    .cloned()
                    .unwrap_or(Value::Bool(false))
            } else {
                Value::Bool(false)
            },
            "default_influence_ready": false,
            "aggregate_human_review_required": request_aggregate_human_review_required,
            "redacted_evidence_aggregate_summary_included": false,
            "post_runtime_evidence_summary_backed_review_request": request_post_runtime_evidence_provided,
            "post_runtime_evidence_summary_state": request_post_runtime_evidence_state,
            "post_runtime_evidence_summary_provided": request_post_runtime_evidence_provided,
            "post_runtime_evidence_summary_ready": request_post_runtime_evidence_ready,
            "post_runtime_evidence_summary_review_state": request
                .pointer("/evidence_summary/post_runtime_evidence_summary_review_state")
                .cloned()
                .unwrap_or(Value::Null),
            "post_runtime_controlled_rank_movement_observed": request_post_runtime_evidence_movement_observed,
            "post_runtime_runtime_readiness_packet_provided": request_post_runtime_readiness_packet_provided,
            "post_runtime_runtime_readiness_requirement_met": request_post_runtime_readiness_requirement_met,
            "post_runtime_readiness_gated_batch_evidence_ready": request_post_runtime_gated_batch_ready,
            "post_runtime_batch_transition_gated": request_post_runtime_batch_transition_gated,
            "post_runtime_batch_evidence_source": request
                .pointer("/evidence_summary/post_runtime_batch_evidence_source")
                .cloned()
                .unwrap_or(Value::Null),
            "post_runtime_evidence_summary_default_influence_ready": if request_post_runtime_evidence_provided {
                request
                    .pointer("/evidence_summary/post_runtime_evidence_summary_default_influence_ready")
                    .cloned()
                    .unwrap_or(Value::Bool(false))
            } else {
                Value::Bool(false)
            },
            "post_runtime_evidence_summary_included": false,
            "capability_ledger_backed_review_request": request_capability_ledger_provided,
            "capability_ledger_state": request_capability_ledger_state,
            "capability_ledger_report_packet_provided": request_capability_ledger_provided,
            "capability_ledger_report_packet_accepted": request_capability_ledger_accepted,
            "capability_ledger_read_only_confirmed": request_capability_ledger_read_only,
            "capability_ledger_input_schema": request
                .pointer("/evidence_summary/capability_ledger_input_schema")
                .cloned()
                .unwrap_or(Value::Null),
            "capability_ledger_input_schema_version": request
                .pointer("/evidence_summary/capability_ledger_input_schema_version")
                .cloned()
                .unwrap_or(Value::Null),
            "capability_ledger_downstream_action": request
                .pointer("/evidence_summary/capability_ledger_downstream_action")
                .cloned()
                .unwrap_or(Value::Null),
            "capability_ledger_integration_decision": request
                .pointer("/evidence_summary/capability_ledger_integration_decision")
                .cloned()
                .unwrap_or(Value::Null),
            "capability_ledger_can_authorize_runtime_influence": false,
            "capability_ledger_report_packet_included": false,
        },
        "authorized_runtime_influence": {
            "may_run_runtime_adapter_for_explicit_opt_in_fts": runtime_influence_authorized,
            "may_connect_ordering_behavior_for_explicit_opt_in_fts": runtime_influence_authorized,
            "may_affect_only_explicitly_opted_in_fts_calls": runtime_influence_authorized && decision_fts_only,
            "requires_per_call_opt_in": decision_per_call_required,
            "must_keep_baseline_candidate_recall": decision_baseline_recall,
            "must_keep_default_calls_unchanged": decision_default_calls_unchanged,
            "must_keep_redacted_audit_only": decision_redacted_audit,
            "must_keep_operator_disable": BIOCORTEX_RETRIEVAL_DISABLE_ENV,
            "must_return_baseline_without_per_call_opt_in": decision_baseline_without_opt_in,
            "must_fail_open_to_baseline": decision_fail_open,
        },
        "not_authorized": [
            "default_search_order_change_allowed",
            "default_retrieval_influence_fts",
            "default_retrieval_influence_hybrid",
            "default_retrieval_influence_semantic",
            "hybrid_retrieval_influence",
            "semantic_retrieval_influence",
            "affecting_calls_without_explicit_opt_in",
            "changing_candidate_recall_source",
            "copying_raw_query_keys_or_content"
        ],
        "boundary_check": {
            "runtime_influence_authorized": runtime_influence_authorized,
            "blockers": blockers,
            "decision_schema_ok": decision_schema_ok,
            "decision_authorized": decision_authorized,
            "decision_scope_ok": decision_scope_ok,
            "decision_runtime_adapter_approved": decision_runtime_adapter_approved,
            "decision_ordering_connection_authorized": decision_ordering_connection_authorized,
            "decision_default_order_still_not_allowed": decision_default_order_not_allowed,
            "request_schema_ok": request_schema_ok,
            "request_ready": request_ready,
            "request_grants_nothing": request_grants_nothing,
            "request_runtime_adapter_still_not_approved": request_runtime_not_approved,
            "request_default_order_still_not_allowed": request_default_order_false,
            "request_ordering_behavior_connected_false": request_ordering_connected_false,
            "request_return_order_unchanged": request_return_order_unchanged,
            "aggregate_backed_review_request": request_aggregate_provided,
            "aggregate_review_evidence_ready": request_aggregate_provided && request_aggregate_safe_for_decision,
            "legacy_review_request_without_aggregate_allowed": !request_aggregate_provided,
            "aggregate_contract_ok": !request_aggregate_provided || request_accepts_optional_aggregate,
            "aggregate_summary_redacted": !request_aggregate_provided || request_aggregate_redacted,
            "aggregate_safe_for_decision": request_aggregate_safe_for_decision,
            "aggregate_default_influence_still_not_ready": !request_aggregate_provided
                || request_aggregate_default_influence_not_ready,
            "aggregate_human_review_required": !request_aggregate_provided
                || request_aggregate_human_review_required,
            "post_runtime_evidence_summary_backed_review_request": request_post_runtime_evidence_provided,
            "post_runtime_evidence_summary_ready": request_post_runtime_evidence_provided
                && request_post_runtime_evidence_safe_for_decision,
            "legacy_review_request_without_post_runtime_evidence_summary_allowed": !request_post_runtime_evidence_provided,
            "post_runtime_evidence_summary_contract_ok": !request_post_runtime_evidence_provided
                || request_accepts_optional_post_runtime_evidence,
            "post_runtime_evidence_summary_redacted": !request_post_runtime_evidence_provided
                || request_post_runtime_evidence_redacted,
            "post_runtime_evidence_summary_safe_for_decision": request_post_runtime_evidence_safe_for_decision,
            "post_runtime_evidence_summary_default_influence_still_not_ready": !request_post_runtime_evidence_provided
                || request_post_runtime_evidence_default_influence_not_ready,
            "post_runtime_runtime_readiness_requirement_met": !request_post_runtime_evidence_provided
                || request_post_runtime_readiness_requirement_met,
            "post_runtime_readiness_gated_batch_evidence_ready": !request_post_runtime_evidence_provided
                || request_post_runtime_gated_batch_ready,
            "post_runtime_batch_transition_gated": !request_post_runtime_evidence_provided
                || request_post_runtime_batch_transition_gated,
            "capability_ledger_backed_review_request": request_capability_ledger_provided,
            "capability_ledger_safe_for_decision": request_capability_ledger_safe_for_decision,
            "legacy_review_request_without_capability_ledger_allowed": !request_capability_ledger_provided,
            "capability_ledger_contract_ok": !request_capability_ledger_provided
                || request_accepts_optional_capability_ledger,
            "capability_ledger_summary_redacted": !request_capability_ledger_provided
                || request_capability_ledger_redacted,
            "capability_ledger_accepted": !request_capability_ledger_provided
                || request_capability_ledger_accepted,
            "capability_ledger_read_only_confirmed": !request_capability_ledger_provided
                || request_capability_ledger_read_only,
            "capability_ledger_decision_display_only": request_capability_ledger_decision_display_only,
            "capability_ledger_authorizes_runtime_influence": request_capability_ledger_provided
                && !request_capability_ledger_authorizes_nothing,
        },
        "required_next_gate": {
            "implementation_may_add_runtime_adapter_for_explicit_opt_in_fts": runtime_influence_authorized,
            "implementation_may_connect_ordering_behavior_for_explicit_opt_in_fts": runtime_influence_authorized,
            "post_connection_verification_required": true,
            "this_packet_connects_ordering_behavior": false,
            "this_packet_changes_return_order": false,
            "this_packet_allows_default_search_order_change": false,
        },
        "approval_state": if runtime_influence_authorized {
            "runtime_influence_review_authorized"
        } else {
            "not_approved"
        },
        "authorization_state": if runtime_influence_authorized {
            "authorized_for_explicit_opt_in_fts_runtime_influence"
        } else {
            "not_authorized"
        },
        "implementation_allowed": runtime_influence_authorized,
        "runtime_adapter_approved": runtime_influence_authorized,
        "ordering_behavior_connection_authorized": runtime_influence_authorized,
        "approval_writes_allowed": false,
        "writes_approval": false,
        "calls_memory_search": false,
        "runs_biocortex": false,
        "registers_embedding_backend": false,
        "changes_memory_search_order": false,
        "default_search_order_change_allowed": false,
        "ordering_behavior_connected": false,
        "may_change_search_order_now": false,
        "may_implement_ordering_now": runtime_influence_authorized,
        "default_calls_unchanged": true,
        "boundary": retrieval_boundary_payload(),
    })
}

pub async fn biocortex_retrieval_opt_in_store_trial(
    store: &dyn StateStore,
    opts: BioCortexRetrievalOptInStoreTrialOptions,
) -> Value {
    let packet = opts.runtime_influence_decision_packet;
    let mode = normalize_token(&opts.mode);
    let query = opts.query.trim().to_string();
    let tags_any = opts
        .tags_any
        .into_iter()
        .map(|tag| tag.trim().to_string())
        .filter(|tag| !tag.is_empty())
        .collect::<Vec<_>>();
    let limit = opts.limit.clamp(1, 100);
    let timeout_ms = opts.timeout_ms.clamp(1_000, 600_000);
    let coverage_threshold = opts.coverage_threshold.clamp(0.0, 1.0);
    let blend_alpha = if opts.blend_alpha.is_finite() && opts.blend_alpha >= 0.0 {
        opts.blend_alpha.clamp(0.0, 1.0)
    } else {
        CANDIDATE_STRONG_RETRIEVAL_ALPHA
    };

    let packet_schema_ok = value_str_eq(
        packet.get("schema"),
        BIOCORTEX_RETRIEVAL_OPT_IN_RUNTIME_INFLUENCE_DECISION_PACKET_SCHEMA,
    );
    let packet_read_only = value_bool_is(packet.get("read_only"), true);
    let packet_consumer_ok = value_bool_is(packet.get("runtime_influence_decision_consumer"), true);
    let packet_scope_ok = value_str_eq(
        packet.get("authorization_scope"),
        "explicit_opt_in_fts_runtime_influence",
    );
    let packet_authorized = value_bool_is(
        packet.pointer("/boundary_check/runtime_influence_authorized"),
        true,
    ) && value_str_eq(
        packet.get("approval_state"),
        "runtime_influence_review_authorized",
    ) && value_str_eq(
        packet.get("authorization_state"),
        "authorized_for_explicit_opt_in_fts_runtime_influence",
    ) && value_bool_is(packet.get("implementation_allowed"), true)
        && value_bool_is(packet.get("runtime_adapter_approved"), true)
        && value_bool_is(packet.get("ordering_behavior_connection_authorized"), true)
        && value_bool_is(packet.get("may_implement_ordering_now"), true);
    let packet_default_order_not_allowed =
        value_bool_is(packet.get("default_search_order_change_allowed"), false);
    let packet_default_calls_unchanged = value_bool_is(packet.get("default_calls_unchanged"), true);
    let packet_did_not_already_call_memory =
        value_bool_is(packet.get("calls_memory_search"), false);
    let packet_did_not_already_run_biocortex = value_bool_is(packet.get("runs_biocortex"), false);
    let packet_did_not_change_order =
        value_bool_is(packet.get("changes_memory_search_order"), false);
    let packet_ordering_not_connected_yet =
        value_bool_is(packet.get("ordering_behavior_connected"), false);
    let packet_may_not_change_now = value_bool_is(packet.get("may_change_search_order_now"), false);
    let packet_runtime_fts = value_bool_is(
        packet.pointer(
            "/authorized_runtime_influence/may_run_runtime_adapter_for_explicit_opt_in_fts",
        ),
        true,
    );
    let packet_ordering_fts = value_bool_is(
        packet.pointer(
            "/authorized_runtime_influence/may_connect_ordering_behavior_for_explicit_opt_in_fts",
        ),
        true,
    );
    let packet_fts_only = value_bool_is(
        packet
            .pointer("/authorized_runtime_influence/may_affect_only_explicitly_opted_in_fts_calls"),
        true,
    );
    let packet_per_call_required = value_bool_is(
        packet.pointer("/authorized_runtime_influence/requires_per_call_opt_in"),
        true,
    );
    let packet_baseline_recall = value_bool_is(
        packet.pointer("/authorized_runtime_influence/must_keep_baseline_candidate_recall"),
        true,
    );
    let packet_redacted_audit = value_bool_is(
        packet.pointer("/authorized_runtime_influence/must_keep_redacted_audit_only"),
        true,
    );
    let packet_kill_switch_ok = value_str_eq(
        packet.pointer("/authorized_runtime_influence/must_keep_operator_disable"),
        BIOCORTEX_RETRIEVAL_DISABLE_ENV,
    );
    let packet_fail_open = value_bool_is(
        packet.pointer("/authorized_runtime_influence/must_fail_open_to_baseline"),
        true,
    );
    let packet_input_raw_absent =
        value_bool_is(
            packet.pointer("/input_contract/runtime_influence_decision_included"),
            false,
        ) && value_bool_is(
            packet.pointer("/input_contract/runtime_influence_review_request_included"),
            false,
        ) && value_bool_is(packet.pointer("/input_contract/raw_query_included"), false)
            && value_bool_is(packet.pointer("/input_contract/raw_keys_included"), false)
            && value_bool_is(packet.pointer("/input_contract/content_included"), false)
            && value_bool_is(
                packet.pointer("/input_contract/human_decision_text_included"),
                false,
            );
    let packet_aggregate_backed = value_bool_is(
        packet.pointer("/request_summary/aggregate_backed_review_request"),
        true,
    ) || value_bool_is(
        packet.pointer("/boundary_check/aggregate_backed_review_request"),
        true,
    );
    let packet_aggregate_contract_ok = value_bool_is(
        packet.pointer("/input_contract/accepts_aggregate_backed_review_request"),
        true,
    ) && value_bool_is(
        packet.pointer("/input_contract/requires_aggregate_ready_when_provided"),
        true,
    ) && value_bool_is(
        packet.pointer("/input_contract/redacted_evidence_aggregate_included"),
        false,
    );
    let packet_aggregate_ready = value_bool_is(
        packet.pointer("/boundary_check/aggregate_review_evidence_ready"),
        true,
    ) && value_bool_is(
        packet.pointer("/request_summary/redacted_evidence_aggregate_ready"),
        true,
    ) && value_str_eq(
        packet.pointer("/request_summary/aggregate_review_evidence_state"),
        "redacted_aggregate_ready",
    );
    let packet_aggregate_default_influence_not_ready = value_bool_is(
        packet.pointer("/request_summary/aggregate_default_influence_ready"),
        false,
    ) && value_bool_is(
        packet.pointer("/request_summary/default_influence_ready"),
        false,
    );
    let packet_aggregate_human_review_required = value_bool_is(
        packet.pointer("/request_summary/aggregate_human_review_required"),
        true,
    );
    let packet_aggregate_summary_redacted = value_bool_is(
        packet.pointer("/request_summary/redacted_evidence_aggregate_summary_included"),
        false,
    ) && value_bool_is(
        packet.pointer("/boundary_check/aggregate_summary_redacted"),
        true,
    );
    let packet_aggregate_safe_for_trial = if packet_aggregate_backed {
        packet_aggregate_contract_ok
            && packet_aggregate_ready
            && packet_aggregate_default_influence_not_ready
            && packet_aggregate_human_review_required
            && packet_aggregate_summary_redacted
            && value_bool_is(
                packet.pointer("/boundary_check/aggregate_safe_for_decision"),
                true,
            )
    } else {
        true
    };
    let packet_post_runtime_evidence_backed = value_bool_is(
        packet.pointer("/request_summary/post_runtime_evidence_summary_backed_review_request"),
        true,
    ) || value_bool_is(
        packet.pointer("/boundary_check/post_runtime_evidence_summary_backed_review_request"),
        true,
    );
    let packet_post_runtime_evidence_contract_ok = value_bool_is(
        packet.pointer("/input_contract/accepts_post_runtime_evidence_summary_review_request"),
        true,
    ) && value_bool_is(
        packet
            .pointer("/input_contract/requires_post_runtime_evidence_summary_ready_when_provided"),
        true,
    ) && value_bool_is(
        packet.pointer("/input_contract/post_runtime_evidence_summary_included"),
        false,
    );
    let packet_post_runtime_evidence_ready = value_bool_is(
        packet.pointer("/boundary_check/post_runtime_evidence_summary_ready"),
        true,
    ) && value_bool_is(
        packet.pointer("/request_summary/post_runtime_evidence_summary_ready"),
        true,
    ) && value_str_eq(
        packet.pointer("/request_summary/post_runtime_evidence_summary_state"),
        "post_runtime_evidence_ready",
    );
    let packet_post_runtime_evidence_default_influence_not_ready = value_bool_is(
        packet.pointer("/request_summary/post_runtime_evidence_summary_default_influence_ready"),
        false,
    ) && value_bool_is(
        packet.pointer("/request_summary/default_influence_ready"),
        false,
    );
    let packet_post_runtime_readiness_requirement_met = value_bool_is(
        packet.pointer("/boundary_check/post_runtime_runtime_readiness_requirement_met"),
        true,
    ) && value_bool_is(
        packet.pointer("/request_summary/post_runtime_runtime_readiness_requirement_met"),
        true,
    );
    let packet_post_runtime_gated_batch_ready = value_bool_is(
        packet.pointer("/boundary_check/post_runtime_readiness_gated_batch_evidence_ready"),
        true,
    ) && value_bool_is(
        packet.pointer("/request_summary/post_runtime_readiness_gated_batch_evidence_ready"),
        true,
    );
    let packet_post_runtime_batch_transition_gated = value_bool_is(
        packet.pointer("/boundary_check/post_runtime_batch_transition_gated"),
        true,
    ) && value_bool_is(
        packet.pointer("/request_summary/post_runtime_batch_transition_gated"),
        true,
    ) && value_str_eq(
        packet.pointer("/request_summary/post_runtime_batch_evidence_source"),
        "runtime_transition_gated_batch_diagnostics",
    );
    let packet_post_runtime_evidence_summary_redacted = value_bool_is(
        packet.pointer("/request_summary/post_runtime_evidence_summary_included"),
        false,
    ) && value_bool_is(
        packet.pointer("/boundary_check/post_runtime_evidence_summary_redacted"),
        true,
    );
    let packet_post_runtime_evidence_safe_for_trial = if packet_post_runtime_evidence_backed {
        packet_post_runtime_evidence_contract_ok
            && packet_post_runtime_evidence_ready
            && packet_post_runtime_evidence_default_influence_not_ready
            && packet_post_runtime_readiness_requirement_met
            && packet_post_runtime_gated_batch_ready
            && packet_post_runtime_batch_transition_gated
            && packet_post_runtime_evidence_summary_redacted
            && value_bool_is(
                packet.pointer("/boundary_check/post_runtime_evidence_summary_safe_for_decision"),
                true,
            )
    } else {
        true
    };

    let compile_feature_enabled = cfg!(feature = "biocortex-retrieval-opt-in");
    let runtime_enabled = env_truthy(BIOCORTEX_RETRIEVAL_OPT_IN_ENABLE_ENV);
    let operator_disabled = env_truthy(BIOCORTEX_RETRIEVAL_DISABLE_ENV);
    let mode_authorized = mode == "fts";
    let query_present = !query.is_empty();

    let query_hash = if query_present {
        sha256_json(&json!({"query": &query}))
    } else {
        sha256_json(&Value::Null)
    };

    let baseline_started = query_present;
    let (baseline_hits, baseline_error) = if baseline_started {
        match store.memory_search(&query, &tags_any, limit).await {
            Ok(hits) => (hits, None),
            Err(err) => (Vec::new(), Some(err.to_string())),
        }
    } else {
        (Vec::new(), None)
    };
    let baseline_completed = baseline_started && baseline_error.is_none();
    let baseline_non_empty = !baseline_hits.is_empty();
    let baseline_candidates = baseline_hits
        .iter()
        .map(|hit| BioCortexRetrievalCandidate {
            key: hit.record.key.clone(),
            content: hit.record.content.clone(),
        })
        .collect::<Vec<_>>();

    let mut blockers = Vec::new();
    push_string_blocker(
        &mut blockers,
        packet_schema_ok,
        "decision_packet_schema_invalid",
    );
    push_string_blocker(
        &mut blockers,
        packet_read_only,
        "decision_packet_not_read_only",
    );
    push_string_blocker(
        &mut blockers,
        packet_consumer_ok,
        "decision_packet_not_runtime_influence_consumer",
    );
    push_string_blocker(
        &mut blockers,
        packet_scope_ok,
        "decision_packet_scope_not_explicit_opt_in_fts",
    );
    push_string_blocker(
        &mut blockers,
        packet_authorized,
        "decision_packet_not_runtime_authorized",
    );
    push_string_blocker(
        &mut blockers,
        packet_default_order_not_allowed,
        "decision_packet_allows_default_order",
    );
    push_string_blocker(
        &mut blockers,
        packet_default_calls_unchanged,
        "decision_packet_default_calls_changed",
    );
    push_string_blocker(
        &mut blockers,
        packet_did_not_already_call_memory,
        "decision_packet_claims_memory_search",
    );
    push_string_blocker(
        &mut blockers,
        packet_did_not_already_run_biocortex,
        "decision_packet_claims_biocortex_run",
    );
    push_string_blocker(
        &mut blockers,
        packet_did_not_change_order,
        "decision_packet_claims_order_change",
    );
    push_string_blocker(
        &mut blockers,
        packet_ordering_not_connected_yet,
        "decision_packet_claims_ordering_connected",
    );
    push_string_blocker(
        &mut blockers,
        packet_may_not_change_now,
        "decision_packet_claims_may_change_now",
    );
    push_string_blocker(
        &mut blockers,
        packet_runtime_fts,
        "decision_packet_runtime_not_fts",
    );
    push_string_blocker(
        &mut blockers,
        packet_ordering_fts,
        "decision_packet_ordering_not_fts",
    );
    push_string_blocker(
        &mut blockers,
        packet_fts_only,
        "decision_packet_not_fts_only",
    );
    push_string_blocker(
        &mut blockers,
        packet_per_call_required,
        "decision_packet_missing_per_call_rule",
    );
    push_string_blocker(
        &mut blockers,
        packet_baseline_recall,
        "decision_packet_missing_baseline_recall_rule",
    );
    push_string_blocker(
        &mut blockers,
        packet_redacted_audit,
        "decision_packet_missing_redacted_audit_rule",
    );
    push_string_blocker(
        &mut blockers,
        packet_kill_switch_ok,
        "decision_packet_kill_switch_mismatch",
    );
    push_string_blocker(
        &mut blockers,
        packet_fail_open,
        "decision_packet_missing_fail_open_rule",
    );
    push_string_blocker(
        &mut blockers,
        packet_input_raw_absent,
        "decision_packet_raw_input_included",
    );
    if packet_aggregate_backed {
        push_string_blocker(
            &mut blockers,
            packet_aggregate_contract_ok,
            "decision_packet_aggregate_contract_unexpected",
        );
        push_string_blocker(
            &mut blockers,
            packet_aggregate_ready,
            "decision_packet_aggregate_review_evidence_not_ready",
        );
        push_string_blocker(
            &mut blockers,
            packet_aggregate_default_influence_not_ready,
            "decision_packet_aggregate_default_influence_ready",
        );
        push_string_blocker(
            &mut blockers,
            packet_aggregate_human_review_required,
            "decision_packet_aggregate_missing_human_review_requirement",
        );
        push_string_blocker(
            &mut blockers,
            packet_aggregate_summary_redacted,
            "decision_packet_aggregate_summary_not_redacted",
        );
        push_string_blocker(
            &mut blockers,
            packet_aggregate_safe_for_trial,
            "decision_packet_aggregate_not_safe_for_trial",
        );
    }
    if packet_post_runtime_evidence_backed {
        push_string_blocker(
            &mut blockers,
            packet_post_runtime_evidence_contract_ok,
            "decision_packet_post_runtime_evidence_contract_unexpected",
        );
        push_string_blocker(
            &mut blockers,
            packet_post_runtime_evidence_ready,
            "decision_packet_post_runtime_evidence_summary_not_ready",
        );
        push_string_blocker(
            &mut blockers,
            packet_post_runtime_evidence_default_influence_not_ready,
            "decision_packet_post_runtime_evidence_default_influence_ready",
        );
        push_string_blocker(
            &mut blockers,
            packet_post_runtime_readiness_requirement_met,
            "decision_packet_post_runtime_readiness_requirement_not_met",
        );
        push_string_blocker(
            &mut blockers,
            packet_post_runtime_gated_batch_ready,
            "decision_packet_post_runtime_gated_batch_not_ready",
        );
        push_string_blocker(
            &mut blockers,
            packet_post_runtime_batch_transition_gated,
            "decision_packet_post_runtime_batch_not_transition_gated",
        );
        push_string_blocker(
            &mut blockers,
            packet_post_runtime_evidence_summary_redacted,
            "decision_packet_post_runtime_evidence_summary_not_redacted",
        );
        push_string_blocker(
            &mut blockers,
            packet_post_runtime_evidence_safe_for_trial,
            "decision_packet_post_runtime_evidence_not_safe_for_trial",
        );
    }
    push_string_blocker(&mut blockers, mode_authorized, "mode_not_authorized");
    push_string_blocker(
        &mut blockers,
        opts.per_call_opt_in,
        "per_call_opt_in_missing",
    );
    push_string_blocker(
        &mut blockers,
        compile_feature_enabled,
        "compile_feature_disabled",
    );
    push_string_blocker(&mut blockers, runtime_enabled, "runtime_disabled");
    push_string_blocker(&mut blockers, !operator_disabled, "operator_disabled");
    push_string_blocker(&mut blockers, query_present, "query_missing");
    push_string_blocker(
        &mut blockers,
        baseline_completed,
        "baseline_memory_search_failed",
    );
    push_string_blocker(&mut blockers, baseline_non_empty, "baseline_empty");

    let adapter_allowed = blockers.is_empty();
    let mut side_status = if adapter_allowed {
        "not_run".to_string()
    } else {
        "not_run_preflight_blocked".to_string()
    };
    let mut side_attempted = false;
    let mut side_row_count = 0usize;
    let mut matched_candidate_count = 0usize;
    let mut latency_ms = 0.0f64;
    let mut side_signal_scores = Vec::new();

    if adapter_allowed {
        side_attempted = true;
        let started = Instant::now();
        match run_retrieval_side_signal(
            &query,
            &baseline_candidates,
            None,
            opts.checkout.as_deref(),
            timeout_ms,
        )
        .await
        {
            Ok(run) => {
                latency_ms = started.elapsed().as_secs_f64() * 1000.0;
                side_row_count = run.rows.len();
                let candidate_keys = baseline_candidates
                    .iter()
                    .map(|candidate| candidate.key.as_str())
                    .collect::<BTreeSet<_>>();
                let mut matched_keys = BTreeSet::new();
                for row in run.rows {
                    if row.query_id != "q_runtime_shadow" {
                        continue;
                    }
                    if candidate_keys.contains(row.candidate_key.as_str()) {
                        matched_keys.insert(row.candidate_key.clone());
                        side_signal_scores.push(BioCortexRetrievalOptInSideSignal {
                            candidate_key: row.candidate_key,
                            score: row.score,
                        });
                    }
                }
                matched_candidate_count = matched_keys.len();
                let coverage =
                    matched_candidate_count as f64 / baseline_candidates.len().max(1) as f64;
                side_status = if coverage >= coverage_threshold {
                    "ok".to_string()
                } else {
                    "coverage_below_threshold".to_string()
                };
            }
            Err(error) => {
                latency_ms = started.elapsed().as_secs_f64() * 1000.0;
                side_status = safe_side_signal_error_status(&error);
            }
        }
    }

    let wrapper_options = BioCortexRetrievalOptInSearchOptions {
        mode: mode.clone(),
        per_call_opt_in: opts.per_call_opt_in,
        compile_feature_enabled,
        runtime_enabled,
        operator_disabled,
        runtime_adapter_approved: packet_authorized,
        ordering_behavior_connected: packet_authorized,
        side_signal_scores,
        side_signal_alpha: blend_alpha,
        side_signal_coverage_threshold: coverage_threshold,
    };

    let wrapper_outcome = if baseline_started {
        store
            .memory_search_biocortex_opt_in(&query, &tags_any, limit, wrapper_options)
            .await
            .ok()
    } else {
        None
    };
    let wrapper_called = wrapper_outcome.is_some();
    let wrapper_audit = wrapper_outcome
        .as_ref()
        .map(|outcome| serde_json::to_value(outcome.redacted_audit()).unwrap_or(Value::Null))
        .unwrap_or(Value::Null);
    let returned_hits = wrapper_outcome
        .as_ref()
        .map(|outcome| outcome.returned_hits.as_slice())
        .unwrap_or(baseline_hits.as_slice());
    let baseline_order_hash = memory_hits_order_hash(&mode, &baseline_hits);
    let returned_order_hash = memory_hits_order_hash(&mode, returned_hits);
    let returned_hash_matches_baseline = baseline_order_hash == returned_order_hash;
    let response_contract = wrapper_outcome
        .as_ref()
        .map(|outcome| serde_json::to_value(&outcome.response_contract).unwrap_or(Value::Null))
        .unwrap_or(Value::Null);
    let returned_order_source = wrapper_outcome
        .as_ref()
        .map(|outcome| {
            serde_json::to_value(outcome.response_contract.returned_order_source)
                .unwrap_or_else(|_| json!("baseline"))
        })
        .unwrap_or_else(|| json!("baseline"));
    let contract_changes_order = wrapper_outcome
        .as_ref()
        .map(|outcome| outcome.response_contract.changes_memory_search_order)
        .unwrap_or(false);
    let baseline_returned = wrapper_outcome
        .as_ref()
        .map(|outcome| outcome.response_contract.baseline_returned)
        .unwrap_or(true);
    let fallback_reason = wrapper_outcome
        .as_ref()
        .and_then(|outcome| outcome.response_contract.fallback_reason)
        .map(|reason| serde_json::to_value(reason).unwrap_or(Value::Null))
        .unwrap_or(Value::Null);
    let side_signal_coverage =
        matched_candidate_count as f64 / baseline_candidates.len().max(1) as f64;
    let status = if !baseline_completed {
        "baseline_unavailable"
    } else if contract_changes_order {
        "experimental_order_returned"
    } else {
        "baseline_returned"
    };

    json!({
        "schema": BIOCORTEX_RETRIEVAL_OPT_IN_STORE_TRIAL_SCHEMA,
        "generated_at": now_secs(),
        "store_trial": true,
        "implementation_stage": "store_opt_in_runtime_adapter_connection",
        "authorization_scope": "explicit_opt_in_fts_runtime_influence",
        "purpose": "Call AB store baseline recall, run BioCortex side-signal only after runtime decision gates, and feed the side-signal into the protected opt-in store wrapper.",
        "status": status,
        "attempt": {
            "attempt_id": required_or_value(opts.attempt_id),
            "commit": required_or_value(opts.commit),
            "mode": mode,
            "per_call_opt_in": opts.per_call_opt_in,
            "limit": limit,
            "tag_filter_count": tags_any.len(),
        },
        "input_contract": {
            "runtime_influence_decision_packet_schema": packet.get("schema").cloned().unwrap_or(Value::Null),
            "runtime_influence_decision_packet_included": false,
            "accepts_aggregate_backed_decision_packet": true,
            "requires_aggregate_ready_when_provided": true,
            "redacted_evidence_aggregate_included": false,
            "aggregate_evidence_summary_included": false,
            "accepts_post_runtime_evidence_summary_decision_packet": true,
            "requires_post_runtime_evidence_summary_ready_when_provided": true,
            "post_runtime_evidence_summary_included": false,
            "unknown_fields_ignored": true,
            "raw_query_included": false,
            "raw_keys_included": false,
            "content_included": false,
            "side_signal_raw_included": false,
        },
        "query_hash": query_hash,
        "runtime_preflight": {
            "adapter_allowed": adapter_allowed,
            "blockers": blockers,
            "compile_feature_enabled": compile_feature_enabled,
            "runtime_enabled": runtime_enabled,
            "operator_disabled": operator_disabled,
            "decision_packet_authorized": packet_authorized,
            "decision_packet_aggregate_backed": packet_aggregate_backed,
            "decision_packet_aggregate_review_evidence_ready": packet_aggregate_backed
                && packet_aggregate_safe_for_trial,
            "legacy_decision_packet_without_aggregate_allowed": !packet_aggregate_backed,
            "decision_packet_aggregate_contract_ok": !packet_aggregate_backed
                || packet_aggregate_contract_ok,
            "decision_packet_aggregate_summary_redacted": !packet_aggregate_backed
                || packet_aggregate_summary_redacted,
            "decision_packet_aggregate_safe_for_trial": packet_aggregate_safe_for_trial,
            "decision_packet_aggregate_review_evidence_state": packet
                .pointer("/request_summary/aggregate_review_evidence_state")
                .cloned()
                .unwrap_or(Value::Null),
            "decision_packet_aggregate_default_influence_ready": if packet_aggregate_backed {
                packet
                    .pointer("/request_summary/aggregate_default_influence_ready")
                    .cloned()
                    .unwrap_or(Value::Bool(false))
            } else {
                Value::Bool(false)
            },
            "decision_packet_aggregate_human_review_required": !packet_aggregate_backed
                || packet_aggregate_human_review_required,
            "decision_packet_post_runtime_evidence_summary_backed": packet_post_runtime_evidence_backed,
            "decision_packet_post_runtime_evidence_summary_ready": packet_post_runtime_evidence_backed
                && packet_post_runtime_evidence_safe_for_trial,
            "legacy_decision_packet_without_post_runtime_evidence_summary_allowed": !packet_post_runtime_evidence_backed,
            "decision_packet_post_runtime_evidence_summary_contract_ok": !packet_post_runtime_evidence_backed
                || packet_post_runtime_evidence_contract_ok,
            "decision_packet_post_runtime_evidence_summary_redacted": !packet_post_runtime_evidence_backed
                || packet_post_runtime_evidence_summary_redacted,
            "decision_packet_post_runtime_evidence_summary_safe_for_trial": packet_post_runtime_evidence_safe_for_trial,
            "decision_packet_post_runtime_evidence_summary_state": packet
                .pointer("/request_summary/post_runtime_evidence_summary_state")
                .cloned()
                .unwrap_or(Value::Null),
            "decision_packet_post_runtime_evidence_summary_default_influence_ready": if packet_post_runtime_evidence_backed {
                packet
                    .pointer("/request_summary/post_runtime_evidence_summary_default_influence_ready")
                    .cloned()
                    .unwrap_or(Value::Bool(false))
            } else {
                Value::Bool(false)
            },
            "decision_packet_post_runtime_readiness_requirement_met": !packet_post_runtime_evidence_backed
                || packet_post_runtime_readiness_requirement_met,
            "decision_packet_post_runtime_gated_batch_evidence_ready": !packet_post_runtime_evidence_backed
                || packet_post_runtime_gated_batch_ready,
            "decision_packet_post_runtime_batch_transition_gated": !packet_post_runtime_evidence_backed
                || packet_post_runtime_batch_transition_gated,
            "mode_authorized": mode_authorized,
            "baseline_completed": baseline_completed,
            "baseline_error_redacted": baseline_error.is_some(),
        },
        "baseline_order": {
            "completed": baseline_completed,
            "key_count": baseline_hits.len(),
            "hash": baseline_order_hash,
            "top_key_hash": memory_hits_top_key_hash(&baseline_hits),
            "redacted_rank_rows": redacted_memory_hit_rank_rows(&baseline_hits, "baseline_rank"),
            "redacted_rank_rows_included": !baseline_hits.is_empty(),
            "raw_keys_included": false,
            "raw_order_keys_included": false,
            "content_included": false,
        },
        "protected_adapter_contract": {
            "candidate_recall_source": "store_memory_search_baseline_only",
            "can_add_new_candidates": false,
            "join_key": "candidate_key",
            "calls_memory_search": baseline_started,
            "writes_temp_corpus": side_attempted,
            "mutates_ab_memory": false,
            "registers_embedding_backend": false,
            "raw_query_included": false,
            "raw_keys_included": false,
            "content_included": false,
            "side_signal_raw_included": false,
        },
        "side_signal": {
            "attempted": side_attempted,
            "status": side_status,
            "timeout_ms": timeout_ms,
            "coverage_threshold": round3(coverage_threshold),
            "blend_alpha": blend_alpha,
            "row_count": side_row_count,
            "matched_candidate_count": matched_candidate_count,
            "coverage": round3(side_signal_coverage),
            "latency_ms": round3(latency_ms),
            "raw_included": false,
            "checkout_path_included": false,
            "candidate_keys_included": false,
            "content_included": false,
        },
        "store_wrapper": {
            "called": wrapper_called,
            "method": "StateStore::memory_search_biocortex_opt_in",
            "redacted_audit": wrapper_audit,
            "response_contract": response_contract,
        },
        "returned_order": {
            "source": returned_order_source,
            "baseline_returned": baseline_returned,
            "contract_changes_memory_search_order": contract_changes_order,
            "actual_return_order_changed": !returned_hash_matches_baseline,
            "hash_matches_baseline": returned_hash_matches_baseline,
            "fallback_reason": fallback_reason,
            "hash": returned_order_hash,
            "top_key_hash": memory_hits_top_key_hash(returned_hits),
            "redacted_rank_rows": redacted_memory_hit_rank_rows(returned_hits, "returned_rank"),
            "redacted_rank_rows_included": !returned_hits.is_empty(),
            "raw_keys_included": false,
            "raw_order_keys_included": false,
            "content_included": false,
        },
        "approval_state": if packet_authorized { "runtime_influence_review_authorized" } else { "not_approved" },
        "runtime_adapter_approved": packet_authorized,
        "approval_writes_allowed": false,
        "writes_approval": false,
        "calls_memory_search": baseline_started,
        "runs_biocortex": side_attempted,
        "registers_embedding_backend": false,
        "changes_memory_search_order": contract_changes_order,
        "actual_return_order_changed": !returned_hash_matches_baseline,
        "default_search_order_change_allowed": false,
        "ordering_behavior_connected": packet_authorized,
        "default_calls_unchanged": true,
        "raw_query_included": false,
        "raw_keys_included": false,
        "content_included": false,
        "side_signal_raw_included": false,
        "boundary": retrieval_runtime_trial_boundary_payload(side_attempted),
    })
}

pub async fn biocortex_retrieval_opt_in_gated_store_trial(
    store: &dyn StateStore,
    opts: BioCortexRetrievalOptInGatedStoreTrialOptions,
) -> Value {
    let gate = opts.runtime_transition_gate;
    let decision_packet = opts.runtime_influence_decision_packet;
    let mode = normalize_token(&opts.mode);
    let query = opts.query.trim().to_string();
    let tags_any = opts
        .tags_any
        .into_iter()
        .map(|tag| tag.trim().to_string())
        .filter(|tag| !tag.is_empty())
        .collect::<Vec<_>>();
    let limit = opts.limit.clamp(1, 100);
    let timeout_ms = opts.timeout_ms.clamp(1_000, 600_000);
    let coverage_threshold = opts.coverage_threshold.clamp(0.0, 1.0);
    let blend_alpha = if opts.blend_alpha.is_finite() && opts.blend_alpha >= 0.0 {
        opts.blend_alpha.clamp(0.0, 1.0)
    } else {
        CANDIDATE_STRONG_RETRIEVAL_ALPHA
    };
    let attempt_id = opts.attempt_id.clone();
    let commit = opts.commit.clone();
    let tag_filter_count = tags_any.len();
    let query_present = !query.is_empty();
    let query_hash = if query_present {
        sha256_json(&json!({"query": &query}))
    } else {
        sha256_json(&Value::Null)
    };

    let gate_requested_mode = gate
        .pointer("/requested_transition/mode")
        .and_then(Value::as_str)
        .map(normalize_token)
        .unwrap_or_default();
    let operator_disabled_now = env_truthy(BIOCORTEX_RETRIEVAL_DISABLE_ENV);
    let gate_schema_ok = value_str_eq(
        gate.get("schema"),
        BIOCORTEX_RETRIEVAL_OPT_IN_RUNTIME_TRANSITION_GATE_SCHEMA,
    );
    let gate_read_only = value_bool_is(gate.get("read_only"), true);
    let gate_marker_ok = value_bool_is(gate.get("runtime_transition_gate"), true);
    let gate_stage_ok = value_str_eq(
        gate.get("implementation_stage"),
        "readiness_gated_runtime_transition_gate",
    );
    let gate_scope_ok = value_str_eq(
        gate.get("authorization_scope"),
        "explicit_opt_in_fts_runtime_influence",
    );
    let gate_status_allowed = value_str_eq(gate.get("status"), "transition_allowed");
    let gate_boundary_allowed = value_bool_is(
        gate.pointer("/boundary_check/runtime_transition_allowed"),
        true,
    );
    let gate_boundary_blockers = json_string_array(gate.pointer("/boundary_check/blockers"));
    let gate_boundary_no_blockers = gate_boundary_blockers.is_empty();
    let gate_transition_allowed =
        value_bool_is(gate.pointer("/transition/transition_allowed"), true);
    let gate_may_call_store = value_bool_is(
        gate.pointer("/transition/may_call_controlled_store_trial"),
        true,
    );
    let gate_may_run_fts = value_bool_is(
        gate.pointer("/transition/may_run_runtime_adapter_for_explicit_opt_in_fts"),
        true,
    );
    let gate_may_connect_ordering = value_bool_is(
        gate.pointer("/transition/may_connect_ordering_behavior_for_explicit_opt_in_fts"),
        true,
    );
    let gate_fts_only = value_bool_is(
        gate.pointer("/transition/may_affect_only_explicitly_opted_in_fts_calls"),
        true,
    );
    let gate_requires_per_call =
        value_bool_is(gate.pointer("/transition/requires_per_call_opt_in"), true);
    let gate_kill_switch_ok = value_str_eq(
        gate.pointer("/transition/must_keep_operator_disable"),
        BIOCORTEX_RETRIEVAL_DISABLE_ENV,
    );
    let gate_baseline_without_opt_in = value_bool_is(
        gate.pointer("/transition/must_return_baseline_without_per_call_opt_in"),
        true,
    );
    let gate_fail_open =
        value_bool_is(gate.pointer("/transition/must_fail_open_to_baseline"), true);
    let gate_redacted_audit = value_bool_is(
        gate.pointer("/transition/must_keep_redacted_audit_only"),
        true,
    );
    let gate_baseline_recall = value_bool_is(
        gate.pointer("/transition/must_keep_baseline_candidate_recall"),
        true,
    );
    let gate_default_order_not_allowed =
        value_bool_is(
            gate.pointer("/transition/may_change_default_memory_search_order"),
            false,
        ) && value_bool_is(gate.pointer("/transition/default_influence_ready"), false);
    let gate_post_runtime_evidence_backed = value_bool_is(
        gate.pointer("/readiness_summary/post_runtime_evidence_summary_backed"),
        true,
    );
    let gate_post_runtime_evidence_ready = !gate_post_runtime_evidence_backed
        || (value_bool_is(
            gate.pointer("/readiness_summary/post_runtime_evidence_summary_ready"),
            true,
        ) && value_bool_is(
            gate.pointer(
                "/readiness_summary/legacy_decision_packet_without_post_runtime_evidence_summary_allowed",
            ),
            false,
        ) && value_bool_is(
            gate.pointer("/readiness_summary/post_runtime_readiness_gated_batch_evidence_ready"),
            true,
        ) && value_bool_is(
            gate.pointer("/readiness_summary/post_runtime_batch_transition_gated"),
            true,
        ) && value_bool_is(
            gate.pointer("/readiness_summary/store_post_runtime_evidence_preflight_ok"),
            true,
        ) && value_bool_is(
            gate.pointer("/readiness_summary/batch_post_runtime_evidence_preflight_ok"),
            true,
        ) && value_str_eq(
            gate.pointer("/readiness_summary/post_runtime_evidence_summary_state"),
            "post_runtime_evidence_ready",
        ) && value_str_eq(
            gate.pointer("/readiness_summary/post_runtime_batch_evidence_source"),
            "runtime_transition_gated_batch_diagnostics",
        ));
    let gate_capability_ledger_backed = value_bool_is(
        gate.pointer("/readiness_summary/capability_ledger_backed_review_request"),
        true,
    ) || value_bool_is(
        gate.pointer("/boundary_check/capability_ledger_backed_readiness_packet"),
        true,
    );
    let gate_capability_ledger_safe = value_bool_is(
        gate.pointer("/readiness_summary/capability_ledger_safe_for_transition"),
        true,
    ) && value_bool_is(
        gate.pointer("/boundary_check/capability_ledger_safe_for_transition"),
        true,
    );
    let gate_capability_ledger_authorizes_runtime_influence = value_bool_is(
        gate.pointer(
            "/readiness_summary/capability_ledger_can_authorize_runtime_influence",
        ),
        true,
    ) || value_bool_is(
        gate.pointer("/transition/capability_ledger_can_authorize_runtime_influence"),
        true,
    ) || value_bool_is(
        gate.pointer("/boundary_check/capability_ledger_authorizes_runtime_influence"),
        true,
    );
    let gate_capability_ledger_authorizes_nothing = value_bool_is(
        gate.pointer(
            "/readiness_summary/capability_ledger_can_authorize_runtime_influence",
        ),
        false,
    ) && value_bool_is(
        gate.pointer("/transition/capability_ledger_can_authorize_runtime_influence"),
        false,
    ) && value_bool_is(
        gate.pointer("/boundary_check/capability_ledger_authorizes_runtime_influence"),
        false,
    );
    let gate_capability_ledger_report_packet_included = value_bool_is(
        gate.pointer("/input_contract/capability_ledger_report_packet_included"),
        true,
    ) || value_bool_is(
        gate.pointer("/readiness_summary/capability_ledger_report_packet_included"),
        true,
    );
    let gate_capability_ledger_redacted = value_bool_is(
        gate.pointer("/input_contract/capability_ledger_report_packet_included"),
        false,
    ) && value_bool_is(
        gate.pointer("/readiness_summary/capability_ledger_report_packet_included"),
        false,
    );
    let gate_capability_ledger_ok = !gate_capability_ledger_backed
        || (gate_capability_ledger_safe
            && gate_capability_ledger_authorizes_nothing
            && gate_capability_ledger_redacted);
    let gate_requested_mode_matches = gate_requested_mode == mode;
    let gate_requested_mode_authorized =
        value_bool_is(gate.pointer("/requested_transition/mode_authorized"), true);
    let gate_requested_opt_in_matches = gate
        .pointer("/requested_transition/per_call_opt_in")
        .and_then(Value::as_bool)
        == Some(opts.per_call_opt_in);
    let gate_requested_operator_enabled = value_bool_is(
        gate.pointer("/requested_transition/operator_disabled"),
        false,
    );
    let gate_requested_no_default = value_bool_is(
        gate.pointer("/requested_transition/default_search_order_change_requested"),
        false,
    );
    let gate_requested_no_hybrid = value_bool_is(
        gate.pointer("/requested_transition/hybrid_retrieval_influence_requested"),
        false,
    );
    let gate_requested_no_semantic = value_bool_is(
        gate.pointer("/requested_transition/semantic_retrieval_influence_requested"),
        false,
    );
    let gate_input_raw_absent =
        value_bool_is(
            gate.pointer("/input_contract/runtime_readiness_packet_included"),
            false,
        ) && value_bool_is(gate.pointer("/input_contract/raw_queries_included"), false)
            && value_bool_is(gate.pointer("/input_contract/raw_keys_included"), false)
            && value_bool_is(gate.pointer("/input_contract/content_included"), false)
            && value_bool_is(
                gate.pointer("/input_contract/side_signal_raw_included"),
                false,
            )
            && value_bool_is(
                gate.pointer("/input_contract/human_decision_text_included"),
                false,
            );
    let gate_boundary_side_effects_absent = value_bool_is(
        gate.pointer("/boundary_check/this_packet_grants_new_authorization"),
        false,
    ) && value_bool_is(
        gate.pointer("/boundary_check/this_packet_calls_memory_search"),
        false,
    ) && value_bool_is(
        gate.pointer("/boundary_check/this_packet_runs_biocortex"),
        false,
    ) && value_bool_is(
        gate.pointer("/boundary_check/this_packet_changes_return_order"),
        false,
    ) && value_bool_is(
        gate.pointer("/boundary_check/this_packet_allows_default_search_order_change"),
        false,
    );
    let gate_top_side_effects_absent = value_bool_is(gate.get("approval_writes_allowed"), false)
        && value_bool_is(gate.get("writes_approval"), false)
        && value_bool_is(gate.get("calls_memory_search"), false)
        && value_bool_is(gate.get("runs_biocortex"), false)
        && value_bool_is(gate.get("registers_embedding_backend"), false)
        && value_bool_is(gate.get("changes_memory_search_order"), false)
        && value_bool_is(gate.get("default_search_order_change_allowed"), false)
        && value_bool_is(gate.get("default_calls_unchanged"), true)
        && value_bool_is(gate.get("raw_queries_included"), false)
        && value_bool_is(gate.get("raw_keys_included"), false)
        && value_bool_is(gate.get("content_included"), false)
        && value_bool_is(gate.get("side_signal_raw_included"), false)
        && value_bool_is(gate.get("human_decision_text_included"), false);

    let mut blockers = Vec::new();
    push_string_blocker(
        &mut blockers,
        gate_schema_ok,
        "transition_gate_schema_invalid",
    );
    push_string_blocker(
        &mut blockers,
        gate_read_only,
        "transition_gate_not_read_only",
    );
    push_string_blocker(
        &mut blockers,
        gate_marker_ok,
        "transition_gate_marker_missing",
    );
    push_string_blocker(
        &mut blockers,
        gate_stage_ok,
        "transition_gate_stage_invalid",
    );
    push_string_blocker(
        &mut blockers,
        gate_scope_ok,
        "transition_gate_scope_invalid",
    );
    push_string_blocker(
        &mut blockers,
        gate_status_allowed,
        "transition_gate_status_not_allowed",
    );
    push_string_blocker(
        &mut blockers,
        gate_boundary_allowed,
        "transition_gate_boundary_not_allowed",
    );
    push_string_blocker(
        &mut blockers,
        gate_boundary_no_blockers,
        "transition_gate_boundary_has_blockers",
    );
    push_string_blocker(
        &mut blockers,
        gate_transition_allowed,
        "transition_gate_transition_not_allowed",
    );
    push_string_blocker(
        &mut blockers,
        gate_may_call_store,
        "transition_gate_may_not_call_store_trial",
    );
    push_string_blocker(
        &mut blockers,
        gate_may_run_fts,
        "transition_gate_may_not_run_runtime_adapter",
    );
    push_string_blocker(
        &mut blockers,
        gate_may_connect_ordering,
        "transition_gate_may_not_connect_ordering",
    );
    push_string_blocker(&mut blockers, gate_fts_only, "transition_gate_not_fts_only");
    push_string_blocker(
        &mut blockers,
        gate_requires_per_call,
        "transition_gate_missing_per_call_rule",
    );
    push_string_blocker(
        &mut blockers,
        gate_kill_switch_ok,
        "transition_gate_kill_switch_mismatch",
    );
    push_string_blocker(
        &mut blockers,
        gate_baseline_without_opt_in,
        "transition_gate_missing_baseline_without_opt_in_rule",
    );
    push_string_blocker(
        &mut blockers,
        gate_fail_open,
        "transition_gate_missing_fail_open_rule",
    );
    push_string_blocker(
        &mut blockers,
        gate_redacted_audit,
        "transition_gate_missing_redacted_audit_rule",
    );
    push_string_blocker(
        &mut blockers,
        gate_baseline_recall,
        "transition_gate_missing_baseline_recall_rule",
    );
    push_string_blocker(
        &mut blockers,
        gate_default_order_not_allowed,
        "transition_gate_allows_default_order",
    );
    if gate_post_runtime_evidence_backed {
        push_string_blocker(
            &mut blockers,
            gate_post_runtime_evidence_ready,
            "transition_gate_post_runtime_evidence_summary_not_ready",
        );
    }
    if gate_capability_ledger_backed {
        push_string_blocker(
            &mut blockers,
            gate_capability_ledger_ok,
            "transition_gate_capability_ledger_not_safe",
        );
    }
    push_string_blocker(
        &mut blockers,
        gate_requested_mode_matches,
        "transition_gate_mode_mismatch",
    );
    push_string_blocker(
        &mut blockers,
        gate_requested_mode_authorized,
        "transition_gate_mode_not_authorized",
    );
    push_string_blocker(
        &mut blockers,
        gate_requested_opt_in_matches,
        "transition_gate_per_call_opt_in_mismatch",
    );
    push_string_blocker(
        &mut blockers,
        gate_requested_operator_enabled,
        "transition_gate_operator_disabled",
    );
    push_string_blocker(
        &mut blockers,
        gate_requested_no_default,
        "transition_gate_requested_default_order_change",
    );
    push_string_blocker(
        &mut blockers,
        gate_requested_no_hybrid,
        "transition_gate_requested_hybrid_influence",
    );
    push_string_blocker(
        &mut blockers,
        gate_requested_no_semantic,
        "transition_gate_requested_semantic_influence",
    );
    push_string_blocker(
        &mut blockers,
        gate_input_raw_absent,
        "transition_gate_raw_input_included",
    );
    push_string_blocker(
        &mut blockers,
        gate_boundary_side_effects_absent,
        "transition_gate_boundary_side_effect_claim_unexpected",
    );
    push_string_blocker(
        &mut blockers,
        gate_top_side_effects_absent,
        "transition_gate_side_effect_claim_unexpected",
    );
    push_string_blocker(&mut blockers, mode == "fts", "mode_not_authorized");
    push_string_blocker(
        &mut blockers,
        opts.per_call_opt_in,
        "per_call_opt_in_missing",
    );
    push_string_blocker(&mut blockers, query_present, "query_missing");
    push_string_blocker(
        &mut blockers,
        !operator_disabled_now,
        "operator_disabled_now",
    );

    let transition_gate_allowed = blockers.is_empty();
    let input_contract = json!({
        "runtime_transition_gate_schema": gate.get("schema").cloned().unwrap_or(Value::Null),
        "runtime_transition_gate_included": false,
        "runtime_influence_decision_packet_schema": decision_packet.get("schema").cloned().unwrap_or(Value::Null),
        "runtime_influence_decision_packet_included": false,
        "store_trial_included": false,
        "requires_transition_gate_allowed": true,
        "requires_mode_fts": true,
        "requires_per_call_opt_in": true,
        "requires_operator_disable_absent": true,
        "accepts_post_runtime_evidence_summary_decision_packet": true,
        "requires_post_runtime_evidence_summary_ready_when_provided": true,
        "post_runtime_evidence_summary_included": false,
        "accepts_capability_ledger_backed_transition_gate": true,
        "requires_capability_ledger_safe_when_provided": true,
        "capability_ledger_report_packet_included": false,
        "raw_query_included": false,
        "raw_queries_included": false,
        "raw_keys_included": false,
        "content_included": false,
        "side_signal_raw_included": false,
        "human_decision_text_included": false,
    });
    let transition_preflight = json!({
        "transition_gate_allowed": transition_gate_allowed,
        "blockers": blockers.clone(),
        "gate_schema_ok": gate_schema_ok,
        "gate_status_allowed": gate_status_allowed,
        "gate_boundary_allowed": gate_boundary_allowed,
        "gate_transition_allowed": gate_transition_allowed,
        "gate_may_call_controlled_store_trial": gate_may_call_store,
        "gate_may_run_runtime_adapter_for_explicit_opt_in_fts": gate_may_run_fts,
        "gate_may_connect_ordering_behavior_for_explicit_opt_in_fts": gate_may_connect_ordering,
        "gate_fts_only": gate_fts_only,
        "gate_boundary_blockers": gate_boundary_blockers,
        "gate_input_raw_absent": gate_input_raw_absent,
        "gate_side_effects_absent": gate_boundary_side_effects_absent && gate_top_side_effects_absent,
        "requested_mode": mode.clone(),
        "gate_requested_mode": gate_requested_mode.clone(),
        "requested_mode_authorized": mode == "fts",
        "gate_requested_mode_authorized": gate_requested_mode_authorized,
        "gate_post_runtime_evidence_summary_backed": gate_post_runtime_evidence_backed,
        "gate_post_runtime_evidence_summary_ready": gate_post_runtime_evidence_backed
            && gate_post_runtime_evidence_ready,
        "gate_legacy_decision_packet_without_post_runtime_evidence_summary_allowed": !gate_post_runtime_evidence_backed,
        "gate_post_runtime_evidence_summary_state": gate.pointer("/readiness_summary/post_runtime_evidence_summary_state").cloned().unwrap_or(Value::Null),
        "gate_post_runtime_batch_evidence_source": gate.pointer("/readiness_summary/post_runtime_batch_evidence_source").cloned().unwrap_or(Value::Null),
        "gate_post_runtime_readiness_gated_batch_evidence_ready": gate_post_runtime_evidence_backed
            && value_bool_is(
                gate.pointer("/readiness_summary/post_runtime_readiness_gated_batch_evidence_ready"),
                true,
            ),
        "gate_post_runtime_batch_transition_gated": !gate_post_runtime_evidence_backed
            || value_bool_is(
                gate.pointer("/readiness_summary/post_runtime_batch_transition_gated"),
                true,
            ),
        "gate_store_post_runtime_evidence_preflight_ok": !gate_post_runtime_evidence_backed
            || value_bool_is(
                gate.pointer("/readiness_summary/store_post_runtime_evidence_preflight_ok"),
                true,
            ),
        "gate_batch_post_runtime_evidence_preflight_ok": !gate_post_runtime_evidence_backed
            || value_bool_is(
                gate.pointer("/readiness_summary/batch_post_runtime_evidence_preflight_ok"),
                true,
            ),
        "gate_capability_ledger_backed_review_request": gate_capability_ledger_backed,
        "gate_capability_ledger_safe_for_transition": gate_capability_ledger_backed
            && gate_capability_ledger_safe,
        "gate_legacy_readiness_packet_without_capability_ledger_allowed": !gate_capability_ledger_backed,
        "gate_capability_ledger_input_schema": gate.pointer("/readiness_summary/capability_ledger_input_schema").cloned().unwrap_or(Value::Null),
        "gate_capability_ledger_input_schema_version": gate.pointer("/readiness_summary/capability_ledger_input_schema_version").cloned().unwrap_or(Value::Null),
        "gate_capability_ledger_can_authorize_runtime_influence": gate_capability_ledger_authorizes_runtime_influence,
        "gate_capability_ledger_report_packet_included": gate_capability_ledger_report_packet_included,
        "gate_capability_ledger_preflight_ok": gate_capability_ledger_ok,
        "per_call_opt_in": opts.per_call_opt_in,
        "gate_requested_per_call_opt_in_matches": gate_requested_opt_in_matches,
        "operator_disabled_now": operator_disabled_now,
        "query_present": query_present,
    });

    if !transition_gate_allowed {
        let attempt = json!({
            "attempt_id": required_or_value(attempt_id),
            "commit": required_or_value(commit),
            "mode": mode,
            "per_call_opt_in": opts.per_call_opt_in,
            "limit": limit,
            "tag_filter_count": tag_filter_count,
        });
        let boundary = json!({
            "mode": "runtime_transition_gated_store_trial",
            "gate_required": true,
            "gate_consumed": false,
            "calls_memory_search": false,
            "runs_external_side_signal": false,
            "writes_temp_corpus": false,
            "links_biocortex_into_ab_runtime": false,
            "registers_embedding_backend": false,
            "calls_set_default_backend": false,
            "mutates_ab_memory": false,
            "writes_embeddings": false,
            "writes_coactivation": false,
            "writes_graph_edges": false,
            "changes_memory_search_order": false,
            "default_search_order_changed": false,
        });
        return json!({
            "schema": BIOCORTEX_RETRIEVAL_OPT_IN_GATED_STORE_TRIAL_SCHEMA,
            "generated_at": now_secs(),
            "gated_store_trial": true,
            "implementation_stage": "runtime_transition_gated_store_trial",
            "authorization_scope": "explicit_opt_in_fts_runtime_influence",
            "purpose": "Require an allowed runtime transition gate before any controlled explicit opt-in FTS store trial can call memory_search or BioCortex.",
            "status": "transition_gate_blocked",
            "attempt": attempt,
            "input_contract": input_contract,
            "query_hash": query_hash,
            "runtime_transition_preflight": transition_preflight,
            "store_trial_summary": Value::Null,
            "store_trial_called": false,
            "approval_state": "transition_gate_blocked",
            "authorization_state": "blocked",
            "approval_writes_allowed": false,
            "writes_approval": false,
            "calls_memory_search": false,
            "runs_biocortex": false,
            "registers_embedding_backend": false,
            "changes_memory_search_order": false,
            "actual_return_order_changed": false,
            "default_search_order_change_allowed": false,
            "ordering_behavior_connected": false,
            "default_calls_unchanged": true,
            "raw_query_included": false,
            "raw_queries_included": false,
            "raw_keys_included": false,
            "content_included": false,
            "side_signal_raw_included": false,
            "human_decision_text_included": false,
            "boundary": boundary,
        });
    }

    let trial = biocortex_retrieval_opt_in_store_trial(
        store,
        BioCortexRetrievalOptInStoreTrialOptions {
            runtime_influence_decision_packet: decision_packet,
            query,
            tags_any,
            limit,
            mode: mode.clone(),
            per_call_opt_in: opts.per_call_opt_in,
            checkout: opts.checkout,
            timeout_ms,
            coverage_threshold,
            blend_alpha,
            attempt_id: attempt_id.clone(),
            commit: commit.clone(),
        },
    )
    .await;

    let calls_memory_search = value_bool_is(trial.get("calls_memory_search"), true);
    let runs_biocortex = value_bool_is(trial.get("runs_biocortex"), true);
    let changes_memory_search_order = value_bool_is(trial.get("changes_memory_search_order"), true);
    let actual_return_order_changed = value_bool_is(trial.get("actual_return_order_changed"), true);
    let default_calls_unchanged = value_bool_is(trial.get("default_calls_unchanged"), true);
    let ordering_behavior_connected = value_bool_is(trial.get("ordering_behavior_connected"), true);
    let store_trial_blocker_count = trial
        .pointer("/runtime_preflight/blockers")
        .and_then(Value::as_array)
        .map(|items| items.len())
        .unwrap_or(0);
    let store_trial_summary = json!({
        "schema": trial.get("schema").cloned().unwrap_or(Value::Null),
        "status": trial.get("status").cloned().unwrap_or(Value::Null),
        "runtime_adapter_allowed": trial.pointer("/runtime_preflight/adapter_allowed").cloned().unwrap_or(Value::Bool(false)),
        "runtime_preflight_blocker_count": store_trial_blocker_count,
        "compile_feature_enabled": trial.pointer("/runtime_preflight/compile_feature_enabled").cloned().unwrap_or(Value::Bool(false)),
        "runtime_enabled": trial.pointer("/runtime_preflight/runtime_enabled").cloned().unwrap_or(Value::Bool(false)),
        "operator_disabled": trial.pointer("/runtime_preflight/operator_disabled").cloned().unwrap_or(Value::Bool(false)),
        "decision_packet_authorized": trial.pointer("/runtime_preflight/decision_packet_authorized").cloned().unwrap_or(Value::Bool(false)),
        "decision_packet_post_runtime_evidence_summary_backed": trial.pointer("/runtime_preflight/decision_packet_post_runtime_evidence_summary_backed").cloned().unwrap_or(Value::Bool(false)),
        "decision_packet_post_runtime_evidence_summary_ready": trial.pointer("/runtime_preflight/decision_packet_post_runtime_evidence_summary_ready").cloned().unwrap_or(Value::Bool(false)),
        "legacy_decision_packet_without_post_runtime_evidence_summary_allowed": trial.pointer("/runtime_preflight/legacy_decision_packet_without_post_runtime_evidence_summary_allowed").cloned().unwrap_or(Value::Bool(true)),
        "decision_packet_post_runtime_evidence_summary_safe_for_trial": trial.pointer("/runtime_preflight/decision_packet_post_runtime_evidence_summary_safe_for_trial").cloned().unwrap_or(Value::Bool(true)),
        "decision_packet_post_runtime_evidence_summary_state": trial.pointer("/runtime_preflight/decision_packet_post_runtime_evidence_summary_state").cloned().unwrap_or(Value::Null),
        "baseline_completed": trial.pointer("/baseline_order/completed").cloned().unwrap_or(Value::Bool(false)),
        "baseline_key_count": trial.pointer("/baseline_order/key_count").cloned().unwrap_or(Value::from(0)),
        "side_signal_attempted": trial.pointer("/side_signal/attempted").cloned().unwrap_or(Value::Bool(false)),
        "side_signal_status": trial.pointer("/side_signal/status").cloned().unwrap_or(Value::Null),
        "side_signal_coverage": trial.pointer("/side_signal/coverage").cloned().unwrap_or(Value::Null),
        "store_wrapper_called": trial.pointer("/store_wrapper/called").cloned().unwrap_or(Value::Bool(false)),
        "returned_order_source": trial.pointer("/returned_order/source").cloned().unwrap_or(Value::Null),
        "baseline_returned": trial.pointer("/returned_order/baseline_returned").cloned().unwrap_or(Value::Bool(true)),
        "contract_changes_memory_search_order": trial.pointer("/returned_order/contract_changes_memory_search_order").cloned().unwrap_or(Value::Bool(false)),
        "actual_return_order_changed": trial.pointer("/returned_order/actual_return_order_changed").cloned().unwrap_or(Value::Bool(false)),
        "hash_matches_baseline": trial.pointer("/returned_order/hash_matches_baseline").cloned().unwrap_or(Value::Bool(true)),
        "fallback_reason": trial.pointer("/returned_order/fallback_reason").cloned().unwrap_or(Value::Null),
        "store_trial_included": false,
        "raw_query_included": false,
        "raw_keys_included": false,
        "content_included": false,
        "side_signal_raw_included": false,
    });
    let attempt = json!({
        "attempt_id": required_or_value(attempt_id),
        "commit": required_or_value(commit),
        "mode": mode,
        "per_call_opt_in": opts.per_call_opt_in,
        "limit": limit,
        "tag_filter_count": tag_filter_count,
    });
    let boundary = json!({
        "mode": "runtime_transition_gated_store_trial",
        "gate_required": true,
        "gate_consumed": true,
        "calls_memory_search": calls_memory_search,
        "runs_external_side_signal": runs_biocortex,
        "writes_temp_corpus": runs_biocortex,
        "links_biocortex_into_ab_runtime": false,
        "registers_embedding_backend": false,
        "calls_set_default_backend": false,
        "mutates_ab_memory": false,
        "writes_embeddings": false,
        "writes_coactivation": false,
        "writes_graph_edges": false,
        "changes_memory_search_order": changes_memory_search_order,
        "default_search_order_changed": false,
    });

    json!({
        "schema": BIOCORTEX_RETRIEVAL_OPT_IN_GATED_STORE_TRIAL_SCHEMA,
        "generated_at": now_secs(),
        "gated_store_trial": true,
        "implementation_stage": "runtime_transition_gated_store_trial",
        "authorization_scope": "explicit_opt_in_fts_runtime_influence",
        "purpose": "Require an allowed runtime transition gate before any controlled explicit opt-in FTS store trial can call memory_search or BioCortex.",
        "status": if calls_memory_search {
            "transition_gate_consumed"
        } else {
            "transition_gate_consumed_store_trial_not_called"
        },
        "attempt": attempt,
        "input_contract": input_contract,
        "query_hash": query_hash,
        "runtime_transition_preflight": transition_preflight,
        "store_trial_summary": store_trial_summary,
        "store_trial_called": true,
        "approval_state": "transition_gate_consumed",
        "authorization_state": "readiness_gated_explicit_opt_in_fts_runtime_entry",
        "approval_writes_allowed": false,
        "writes_approval": false,
        "calls_memory_search": calls_memory_search,
        "runs_biocortex": runs_biocortex,
        "registers_embedding_backend": false,
        "changes_memory_search_order": changes_memory_search_order,
        "actual_return_order_changed": actual_return_order_changed,
        "default_search_order_change_allowed": false,
        "ordering_behavior_connected": ordering_behavior_connected,
        "default_calls_unchanged": default_calls_unchanged,
        "raw_query_included": false,
        "raw_queries_included": false,
        "raw_keys_included": false,
        "content_included": false,
        "side_signal_raw_included": false,
        "human_decision_text_included": false,
        "boundary": boundary,
    })
}

pub async fn biocortex_retrieval_opt_in_batch_diagnostics(
    store: &dyn StateStore,
    opts: BioCortexRetrievalOptInBatchDiagnosticsOptions,
) -> Value {
    let queries = opts
        .queries
        .into_iter()
        .filter_map(|case| {
            let query = case.query.trim().to_string();
            if query.is_empty() {
                None
            } else {
                Some(BioCortexRetrievalOptInBatchQueryCase {
                    query,
                    class_label: case.class_label,
                })
            }
        })
        .take(50)
        .collect::<Vec<_>>();
    let mode = normalize_token(&opts.mode);
    let limit = opts.limit.clamp(1, 100);
    let timeout_ms = opts.timeout_ms.clamp(1_000, 600_000);
    let coverage_threshold = opts.coverage_threshold.clamp(0.0, 1.0);
    let blend_alpha = if opts.blend_alpha.is_finite() && opts.blend_alpha >= 0.0 {
        opts.blend_alpha.clamp(0.0, 1.0)
    } else {
        CANDIDATE_STRONG_RETRIEVAL_ALPHA
    };
    let tag_filter_count = opts
        .tags_any
        .iter()
        .map(|tag| tag.trim())
        .filter(|tag| !tag.is_empty())
        .count();
    let runtime_influence_decision_packet = opts.runtime_influence_decision_packet;
    let attempt_id = opts.attempt_id.clone();
    let commit = opts.commit.clone();

    let mut query_results = Vec::with_capacity(queries.len());
    let mut bucket_stats = BTreeMap::<String, BatchBucketStats>::new();
    let mut summary = BatchBucketStats::default();

    for (idx, case) in queries.into_iter().enumerate() {
        let class_label = safe_batch_class_label(case.class_label.as_deref());
        let trial_attempt_id = attempt_id.as_ref().map(|id| format!("{id}:q{}", idx + 1));
        let trial = biocortex_retrieval_opt_in_store_trial(
            store,
            BioCortexRetrievalOptInStoreTrialOptions {
                runtime_influence_decision_packet: runtime_influence_decision_packet.clone(),
                query: case.query,
                tags_any: opts.tags_any.clone(),
                limit,
                mode: mode.clone(),
                per_call_opt_in: opts.per_call_opt_in,
                checkout: opts.checkout.clone(),
                timeout_ms,
                coverage_threshold,
                blend_alpha,
                attempt_id: trial_attempt_id,
                commit: commit.clone(),
            },
        )
        .await;
        let movement_class = batch_movement_class(&trial).to_string();
        let result = batch_trial_summary(idx, &class_label, &movement_class, &trial);
        summary.add_trial(&trial);
        bucket_stats
            .entry(class_label)
            .or_default()
            .add_trial(&trial);
        query_results.push(result);
    }

    let bucket_summary = bucket_stats
        .into_iter()
        .map(|(class_label, stats)| stats.to_value(Some(class_label)))
        .collect::<Vec<_>>();
    let raw_flags_all_false = query_results.iter().all(|row| {
        value_bool_is(row.get("raw_query_included"), false)
            && value_bool_is(row.get("raw_keys_included"), false)
            && value_bool_is(row.get("content_included"), false)
            && value_bool_is(row.get("side_signal_raw_included"), false)
    });
    let query_count = query_results.len();
    let no_queries = query_count == 0;

    json!({
        "schema": BIOCORTEX_RETRIEVAL_OPT_IN_BATCH_DIAGNOSTICS_SCHEMA,
        "generated_at": now_secs(),
        "batch_diagnostics": true,
        "implementation_stage": "store_opt_in_batch_diagnostics",
        "authorization_scope": "explicit_opt_in_fts_runtime_influence",
        "purpose": "Batch redacted diagnostics for explicit opt-in BioCortex store trials. Each row reuses the protected store-trial gate and reports only hashes, counts, coverage, latency, and order-movement classes.",
        "status": if no_queries { "empty_batch" } else { "completed" },
        "attempt": {
            "attempt_id": required_or_value(attempt_id),
            "commit": required_or_value(commit),
            "mode": mode,
            "per_call_opt_in": opts.per_call_opt_in,
            "limit": limit,
            "query_count": query_count,
            "tag_filter_count": tag_filter_count,
            "coverage_threshold": round3(coverage_threshold),
            "blend_alpha": blend_alpha,
        },
        "input_contract": {
            "runtime_influence_decision_packet_schema": runtime_influence_decision_packet.get("schema").cloned().unwrap_or(Value::Null),
            "runtime_influence_decision_packet_included": false,
            "accepts_aggregate_backed_decision_packet": true,
            "requires_aggregate_ready_when_provided": true,
            "redacted_evidence_aggregate_included": false,
            "aggregate_evidence_summary_included": false,
            "accepts_post_runtime_evidence_summary_decision_packet": true,
            "requires_post_runtime_evidence_summary_ready_when_provided": true,
            "post_runtime_evidence_summary_included": false,
            "raw_queries_included": false,
            "raw_keys_included": false,
            "content_included": false,
            "side_signal_raw_included": false,
            "query_classes_sanitized": true,
        },
        "summary": summary.to_value(None),
        "bucket_summary": bucket_summary,
        "query_results": query_results,
        "safety": {
            "calls_memory_search_any": summary.calls_memory_search_count > 0,
            "calls_memory_search_all": query_count > 0 && summary.calls_memory_search_count == query_count,
            "runs_biocortex_any": summary.runs_biocortex_count > 0,
            "changes_memory_search_order_any": summary.contract_changes_order_count > 0,
            "actual_return_order_changed_any": summary.actual_order_changed_count > 0,
            "default_calls_unchanged_all": query_count == 0 || summary.default_calls_unchanged_count == query_count,
            "raw_query_included": false,
            "raw_keys_included": false,
            "content_included": false,
            "side_signal_raw_included": false,
            "raw_flags_all_false": raw_flags_all_false,
        },
        "approval_state": "batch_diagnostics_only",
        "approval_writes_allowed": false,
        "writes_approval": false,
        "registers_embedding_backend": false,
        "default_search_order_change_allowed": false,
        "default_calls_unchanged": query_count == 0 || summary.default_calls_unchanged_count == query_count,
        "raw_queries_included": false,
        "raw_keys_included": false,
        "content_included": false,
        "side_signal_raw_included": false,
        "boundary": retrieval_runtime_trial_boundary_payload(summary.runs_biocortex_count > 0),
    })
}

/// Options for the read-only relevance-lift eval — the "yardstick" the
/// hashed-movement diagnostics deliberately omit.
#[derive(Debug, Clone)]
pub struct RelevanceLiftEvalOptions {
    /// How many memories to sample (head of the chosen sort). Clamped 1..=30.
    pub sample_size: usize,
    /// Optional `kind` filter for the sampled memories.
    pub kind: Option<String>,
    /// Optional explicit downstream-query cases. When present, these replace
    /// self-retrieval sampling so the yardstick can measure harder recall
    /// tasks without deriving the query from the target memory.
    pub query_cases: Vec<RelevanceLiftQueryCase>,
    /// Sort used to pick the head sample.
    pub sort: MemoryListSort,
    /// `memory_search` candidate limit per derived query. Clamped 5..=100.
    pub limit: u32,
    /// Chars of (frontmatter-stripped) content used as the AND-style query
    /// (when `or_terms == 0`). Clamped 16..=400. Char-safe.
    pub query_chars: usize,
    /// When > 0, build a BROAD query from the first `or_terms` distinct
    /// sanitized tokens joined with ` OR ` (any-term match) instead of the
    /// precise AND-style char query. Broad queries return multi-candidate sets
    /// so the reorder actually has rank headroom to lift the source. Clamped
    /// 0..=24. Default 10.
    pub or_terms: usize,
    /// Blend alpha for the side-signal reorder (mirrors the production path).
    pub blend_alpha: f32,
    /// Coverage threshold for the reorder gate (mirrors production).
    pub coverage_threshold: f64,
    /// Fold each memory's `related_keys` into its relevant set (graph labels).
    pub include_related: bool,
    /// Optional explicit biocortex-rs checkout path.
    pub checkout: Option<PathBuf>,
    /// Per side-signal call timeout (ms). Clamped 1_000..=600_000.
    pub timeout_ms: u64,
}

/// Explicit relevance case for the read-only lift yardstick.
#[derive(Debug, Clone)]
pub struct RelevanceLiftQueryCase {
    pub query: String,
    pub relevant_keys: Vec<String>,
    pub class_label: Option<String>,
}

/// Strip a leading YAML frontmatter block (`---\n...\n---`) if present.
fn strip_leading_frontmatter(content: &str) -> &str {
    let trimmed = content.trim_start();
    if let Some(rest) = trimmed.strip_prefix("---") {
        if let Some(end) = rest.find("\n---") {
            return rest[end + 4..].trim_start();
        }
    }
    trimmed
}

/// Derive an **FTS5-safe** self-retrieval query from a memory's content:
/// strip frontmatter, replace every non-alphanumeric char with a space (so
/// FTS5 operators `* : " # ^ ( ) - +` and `col:term` column filters cannot
/// reach the parser), collapse whitespace, lowercase (so a literal `AND`/`OR`/
/// `NOT`/`NEAR` token degrades to a bareword, not an operator), then take the
/// first `max_chars` chars (char-safe — CJK is kept, never byte-sliced).
fn derive_self_retrieval_query(content: &str, max_chars: usize) -> String {
    let body = strip_leading_frontmatter(content);
    let cleaned = body
        .chars()
        .map(|c| if c.is_alphanumeric() { c } else { ' ' })
        .collect::<String>();
    let collapsed = cleaned
        .split_whitespace()
        .collect::<Vec<_>>()
        .join(" ")
        .to_lowercase();
    collapsed.chars().take(max_chars).collect()
}

/// Build a BROAD FTS5 query: the first `max_terms` distinct sanitized tokens
/// (alphanumeric incl. CJK, lowercased, length ≥ 2) joined with ` OR `. Any-term
/// matching returns a multi-candidate set so reorder has rank headroom. Returns
/// an empty string if no usable tokens exist.
fn derive_or_query(content: &str, max_terms: usize) -> String {
    let body = strip_leading_frontmatter(content);
    let normalized = body
        .chars()
        .map(|c| if c.is_alphanumeric() { c } else { ' ' })
        .collect::<String>()
        .to_lowercase();
    let mut seen = BTreeSet::new();
    let mut terms = Vec::new();
    for tok in normalized.split_whitespace() {
        if tok.chars().count() < 2 {
            continue;
        }
        if seen.insert(tok.to_string()) {
            terms.push(tok.to_string());
            if terms.len() >= max_terms {
                break;
            }
        }
    }
    terms.join(" OR ")
}

fn recall_pairs_to_json(pairs: &[(usize, f64)]) -> Value {
    Value::Array(
        pairs
            .iter()
            .map(|(k, v)| json!({ "k": k, "value": round3(*v) }))
            .collect(),
    )
}

fn relevance_lift_class_aggregate_to_json(
    class_label: String,
    samples: &[crate::biocortex_relevance_eval::SampleLift],
) -> Value {
    let agg = crate::biocortex_relevance_eval::aggregate_lift(samples);
    json!({
        "class_label": class_label,
        "evaluated_count": agg.sample_count,
        "source_found_count": agg.source_found_count,
        "mrr_baseline": round3(agg.mrr_baseline),
        "mrr_reordered": round3(agg.mrr_reordered),
        "mrr_lift": round3(agg.mrr_lift),
        "recall_baseline": recall_pairs_to_json(&agg.recall_baseline),
        "recall_reordered": recall_pairs_to_json(&agg.recall_reordered),
        "recall_lift": recall_pairs_to_json(&agg.recall_lift),
        "improved": agg.improved,
        "worsened": agg.worsened,
        "unchanged": agg.unchanged,
        "order_changed_count": agg.order_changed_count,
        "verdict": agg.verdict.as_str(),
    })
}

/// Read-only relevance-lift eval. Samples memories, derives a self-retrieval
/// query per sample, runs baseline FTS `memory_search`, computes the BioCortex
/// biomimetic side-signal, applies the **exact production reorder blend**
/// (eval-local only — never returned as live recall), and measures whether the
/// reorder lifts the rank of the true source via the pure ruler in
/// [`crate::biocortex_relevance_eval`].
///
/// This answers the question `_batch_diagnostics` cannot: not "how much did the
/// order move" but "did the right memory rise". Self-retrieval labels are a
/// PROXY and the verdict says so; regressions are reported as regressions.
pub async fn biocortex_retrieval_relevance_lift_eval(
    store: &dyn StateStore,
    opts: RelevanceLiftEvalOptions,
) -> Value {
    use crate::biocortex_relevance_eval as releval;

    let sample_size = opts.sample_size.clamp(1, 30);
    let limit = opts.limit.clamp(5, 100);
    let query_chars = opts.query_chars.clamp(16, 400);
    let or_terms = opts.or_terms.min(24);
    let query_mode = if or_terms > 0 {
        "or_broad"
    } else {
        "and_precise"
    };
    let timeout_ms = opts.timeout_ms.clamp(1_000, 600_000);
    let coverage_threshold = opts.coverage_threshold.clamp(0.0, 1.0);
    let blend_alpha = if opts.blend_alpha.is_finite() && opts.blend_alpha >= 0.0 {
        opts.blend_alpha.clamp(0.0, 1.0)
    } else {
        CANDIDATE_STRONG_RETRIEVAL_ALPHA
    };
    let sort_label = match opts.sort {
        MemoryListSort::Recent => "recent",
        MemoryListSort::Frequent => "frequent",
        MemoryListSort::Newest => "newest",
        MemoryListSort::ByImportance => "by_importance",
    };
    let explicit_cases = opts
        .query_cases
        .iter()
        .filter_map(|case| {
            let query = case.query.trim().to_string();
            let relevant_keys = case
                .relevant_keys
                .iter()
                .map(|key| key.trim())
                .filter(|key| !key.is_empty())
                .map(str::to_string)
                .collect::<Vec<_>>();
            if query.is_empty() || relevant_keys.is_empty() {
                None
            } else {
                Some(RelevanceLiftQueryCase {
                    query,
                    relevant_keys,
                    class_label: case.class_label.clone(),
                })
            }
        })
        .take(sample_size)
        .collect::<Vec<_>>();
    let explicit_case_count = explicit_cases.len();
    let invalid_query_case_count = opts.query_cases.len().saturating_sub(explicit_case_count);
    let using_explicit_cases = explicit_case_count > 0;

    let sampled: Vec<MemoryRecord> = if using_explicit_cases {
        Vec::new()
    } else {
        match store
            .list_memories(opts.kind.as_deref(), opts.sort, sample_size as u32)
            .await
        {
            Ok(rows) => rows,
            Err(err) => {
                return json!({
                    "schema": BIOCORTEX_RETRIEVAL_RELEVANCE_LIFT_EVAL_SCHEMA,
                    "status": "list_memories_failed",
                    "error": err.to_string(),
                });
            }
        }
    };

    let mut lift_samples: Vec<releval::SampleLift> = Vec::new();
    let mut sample_rows: Vec<Value> = Vec::new();
    let mut lift_samples_by_class = BTreeMap::<String, Vec<releval::SampleLift>>::new();
    let mut side_signal_unavailable = 0usize;
    let mut first_side_error: Option<Value> = None;
    let mut empty_query_skipped = 0usize;

    for (idx, case) in explicit_cases.iter().enumerate() {
        let class_label = safe_batch_class_label(case.class_label.as_deref());
        let baseline_hits = match store.memory_search(&case.query, &[], limit).await {
            Ok(hits) => hits,
            Err(err) => {
                sample_rows.push(json!({
                    "sample_index": idx,
                    "query_hash": sha256_json(&json!({"query": &case.query})),
                    "status": "baseline_search_failed",
                    "error": err.to_string(),
                    "relevant_key_count": case.relevant_keys.len(),
                    "class_label": class_label,
                }));
                continue;
            }
        };

        let relevant = case.relevant_keys.iter().cloned().collect::<BTreeSet<_>>();
        let source_key = case.relevant_keys[0].as_str();

        let baseline_candidates = baseline_hits
            .iter()
            .map(|hit| BioCortexRetrievalCandidate {
                key: hit.record.key.clone(),
                content: hit.record.content.clone(),
            })
            .collect::<Vec<_>>();

        let candidate_keys = baseline_candidates
            .iter()
            .map(|c| c.key.as_str())
            .collect::<BTreeSet<_>>();

        let run = match run_retrieval_side_signal(
            &case.query,
            &baseline_candidates,
            Some(source_key),
            opts.checkout.as_deref(),
            timeout_ms,
        )
        .await
        {
            Ok(run) => run,
            Err(error) => {
                side_signal_unavailable += 1;
                let status = safe_side_signal_error_status(&error);
                if first_side_error.is_none() {
                    first_side_error = Some(error);
                }
                sample_rows.push(json!({
                    "sample_index": idx,
                    "query_hash": sha256_json(&json!({"query": &case.query})),
                    "status": "side_signal_unavailable",
                    "side_signal_status": status,
                    "baseline_hit_count": baseline_hits.len(),
                    "relevant_key_count": relevant.len(),
                    "class_label": class_label,
                }));
                continue;
            }
        };

        let side_signal_scores = run
            .rows
            .into_iter()
            .filter(|row| row.query_id == "q_runtime_shadow")
            .filter(|row| candidate_keys.contains(row.candidate_key.as_str()))
            .map(|row| BioCortexRetrievalOptInSideSignal {
                candidate_key: row.candidate_key,
                score: row.score,
            })
            .collect::<Vec<_>>();

        let (reordered_hits, summary, _experimental_available) = biocortex_opt_in_apply_side_signal(
            &baseline_hits,
            &side_signal_scores,
            blend_alpha,
            coverage_threshold,
            true,
        );

        let baseline_ranking = baseline_hits
            .iter()
            .map(|hit| hit.record.key.clone())
            .collect::<Vec<_>>();
        let reordered_ranking = reordered_hits
            .iter()
            .map(|hit| hit.record.key.clone())
            .collect::<Vec<_>>();

        let lift =
            releval::sample_lift(&baseline_ranking, &reordered_ranking, source_key, &relevant);

        sample_rows.push(json!({
            "sample_index": idx,
            "query_hash": sha256_json(&json!({"query": &case.query})),
            "class_label": class_label.clone(),
            "query_chars": case.query.chars().count(),
            "relevant_set_size": relevant.len(),
            "baseline_hit_count": baseline_hits.len(),
            "status": "ok",
            "side_signal_matched": summary.matched_candidate_count,
            "side_signal_coverage": round3(summary.coverage),
            "side_signal_gate_available": summary.available,
            "baseline_rank_of_source": lift.baseline.rank_of_source,
            "reordered_rank_of_source": lift.reordered.rank_of_source,
            "rank_delta": lift.rank_delta,
            "rr_delta": round3(lift.rr_delta),
            "direction": lift.direction.as_str(),
            "order_changed": lift.order_changed,
        }));
        lift_samples_by_class
            .entry(class_label)
            .or_default()
            .push(lift.clone());
        lift_samples.push(lift);
    }

    if !using_explicit_cases {
        for (idx, record) in sampled.iter().enumerate() {
            let query = if or_terms > 0 {
                derive_or_query(&record.content, or_terms)
            } else {
                derive_self_retrieval_query(&record.content, query_chars)
            };
            if query.trim().is_empty() {
                empty_query_skipped += 1;
                continue;
            }

            let baseline_hits = match store.memory_search(&query, &[], limit).await {
                Ok(hits) => hits,
                Err(err) => {
                    sample_rows.push(json!({
                        "sample_index": idx,
                        "source_key": record.key,
                        "status": "baseline_search_failed",
                        "error": err.to_string(),
                    }));
                    continue;
                }
            };

            let mut relevant = BTreeSet::new();
            relevant.insert(record.key.clone());
            if opts.include_related {
                for rk in &record.related_keys {
                    relevant.insert(rk.clone());
                }
            }

            let baseline_candidates = baseline_hits
                .iter()
                .map(|hit| BioCortexRetrievalCandidate {
                    key: hit.record.key.clone(),
                    content: hit.record.content.clone(),
                })
                .collect::<Vec<_>>();

            let candidate_keys = baseline_candidates
                .iter()
                .map(|c| c.key.as_str())
                .collect::<BTreeSet<_>>();

            let run = match run_retrieval_side_signal(
                &query,
                &baseline_candidates,
                Some(record.key.as_str()),
                opts.checkout.as_deref(),
                timeout_ms,
            )
            .await
            {
                Ok(run) => run,
                Err(error) => {
                    side_signal_unavailable += 1;
                    let status = safe_side_signal_error_status(&error);
                    if first_side_error.is_none() {
                        first_side_error = Some(error);
                    }
                    sample_rows.push(json!({
                        "sample_index": idx,
                        "source_key": record.key,
                        "status": "side_signal_unavailable",
                        "side_signal_status": status,
                        "baseline_hit_count": baseline_hits.len(),
                    }));
                    continue;
                }
            };

            let side_signal_scores = run
                .rows
                .into_iter()
                .filter(|row| row.query_id == "q_runtime_shadow")
                .filter(|row| candidate_keys.contains(row.candidate_key.as_str()))
                .map(|row| BioCortexRetrievalOptInSideSignal {
                    candidate_key: row.candidate_key,
                    score: row.score,
                })
                .collect::<Vec<_>>();

            // Apply the EXACT production reorder blend. gate_allows_ordering=true is
            // eval-local: the reordered list is consumed only to measure rank lift —
            // it is never returned as live recall (see `safety` block below).
            let (reordered_hits, summary, _experimental_available) =
                biocortex_opt_in_apply_side_signal(
                    &baseline_hits,
                    &side_signal_scores,
                    blend_alpha,
                    coverage_threshold,
                    true,
                );

            let baseline_ranking = baseline_hits
                .iter()
                .map(|hit| hit.record.key.clone())
                .collect::<Vec<_>>();
            let reordered_ranking = reordered_hits
                .iter()
                .map(|hit| hit.record.key.clone())
                .collect::<Vec<_>>();

            let lift = releval::sample_lift(
                &baseline_ranking,
                &reordered_ranking,
                &record.key,
                &relevant,
            );

            sample_rows.push(json!({
                "sample_index": idx,
                "source_key": record.key,
                "kind": record.kind,
                "query_chars": query.chars().count(),
                "relevant_set_size": relevant.len(),
                "baseline_hit_count": baseline_hits.len(),
                "status": "ok",
                "side_signal_matched": summary.matched_candidate_count,
                "side_signal_coverage": round3(summary.coverage),
                "side_signal_gate_available": summary.available,
                "baseline_rank_of_source": lift.baseline.rank_of_source,
                "reordered_rank_of_source": lift.reordered.rank_of_source,
                "rank_delta": lift.rank_delta,
                "rr_delta": round3(lift.rr_delta),
                "direction": lift.direction.as_str(),
                "order_changed": lift.order_changed,
            }));
            lift_samples.push(lift);
        }
    }

    let agg = releval::aggregate_lift(&lift_samples);
    let class_aggregates = lift_samples_by_class
        .into_iter()
        .map(|(class_label, samples)| {
            relevance_lift_class_aggregate_to_json(class_label, &samples)
        })
        .collect::<Vec<_>>();

    json!({
        "schema": BIOCORTEX_RETRIEVAL_RELEVANCE_LIFT_EVAL_SCHEMA,
        "generated_at": now_secs(),
        "status": "completed",
        "purpose": "Read-only relevance-lift yardstick: does the BioCortex side-signal reorder lift the rank of the true source memory vs baseline FTS? Supplies the relevance label the hashed-movement diagnostics omit.",
        "verdict": agg.verdict.as_str(),
        "sampling": {
            "requested_sample_size": sample_size,
            "sampled_count": if using_explicit_cases { explicit_case_count } else { sampled.len() },
            "evaluated_count": agg.sample_count,
            "side_signal_unavailable": side_signal_unavailable,
            "empty_query_skipped": empty_query_skipped,
            "query_source": if using_explicit_cases { "explicit_cases" } else { "self_retrieval" },
            "query_cases_count": explicit_case_count,
            "invalid_query_cases": invalid_query_case_count,
            "sort": sort_label,
            "kind_filter": opts.kind.clone().map(Value::String).unwrap_or(Value::Null),
            "head_sample_not_random": !using_explicit_cases,
            "query_mode": query_mode,
            "or_terms": or_terms,
            "query_chars": query_chars,
            "search_limit": limit,
            "include_related": opts.include_related,
            "blend_alpha": blend_alpha,
            "coverage_threshold": round3(coverage_threshold),
        },
        "metrics": {
            "mrr_baseline": round3(agg.mrr_baseline),
            "mrr_reordered": round3(agg.mrr_reordered),
            "mrr_lift": round3(agg.mrr_lift),
            "recall_baseline": recall_pairs_to_json(&agg.recall_baseline),
            "recall_reordered": recall_pairs_to_json(&agg.recall_reordered),
            "recall_lift": recall_pairs_to_json(&agg.recall_lift),
            "source_found_count": agg.source_found_count,
            "improved": agg.improved,
            "worsened": agg.worsened,
            "unchanged": agg.unchanged,
            "order_changed_count": agg.order_changed_count,
        },
        "class_aggregates": class_aggregates,
        "samples": sample_rows,
        "first_side_signal_error": first_side_error.unwrap_or(Value::Null),
        "caveats": {
            "self_retrieval_labels_are_proxy": "Query is derived FROM the target memory, so this measures self-identification ranking, not a real downstream recall need. A lift here is necessary-not-sufficient evidence for real-recall lift.",
            "explicit_query_cases_are_operator_supplied": "When query_source=explicit_cases, relevance labels are supplied by the caller; raw queries and keys are kept out of the summary surface.",
            "head_sample_not_random": "Samples are the head of the chosen sort, not a uniform random draw.",
            "eval_local_reorder_only": "The production reorder blend is applied only to compute rank lift; the reordered list is never returned as live recall.",
            "regressions_reported": "A reorder that demotes the source yields a negative mrr_lift and a 'regression' verdict — never clamped to zero.",
        },
        "safety": {
            "mutates_ab_memory": false,
            "changes_prod_retrieval_order": false,
            "writes_state": false,
            "read_only": true,
            "runs_biocortex_adapter": agg.sample_count > 0 || side_signal_unavailable > 0,
        },
    })
}

pub async fn biocortex_retrieval_opt_in_gated_batch_diagnostics(
    store: &dyn StateStore,
    opts: BioCortexRetrievalOptInGatedBatchDiagnosticsOptions,
) -> Value {
    let queries = opts
        .queries
        .into_iter()
        .filter_map(|case| {
            let query = case.query.trim().to_string();
            if query.is_empty() {
                None
            } else {
                Some(BioCortexRetrievalOptInBatchQueryCase {
                    query,
                    class_label: case.class_label,
                })
            }
        })
        .take(50)
        .collect::<Vec<_>>();
    let mode = normalize_token(&opts.mode);
    let limit = opts.limit.clamp(1, 100);
    let timeout_ms = opts.timeout_ms.clamp(1_000, 600_000);
    let coverage_threshold = opts.coverage_threshold.clamp(0.0, 1.0);
    let blend_alpha = if opts.blend_alpha.is_finite() && opts.blend_alpha >= 0.0 {
        opts.blend_alpha.clamp(0.0, 1.0)
    } else {
        CANDIDATE_STRONG_RETRIEVAL_ALPHA
    };
    let tag_filter_count = opts
        .tags_any
        .iter()
        .map(|tag| tag.trim())
        .filter(|tag| !tag.is_empty())
        .count();
    let runtime_transition_gate = opts.runtime_transition_gate;
    let runtime_influence_decision_packet = opts.runtime_influence_decision_packet;
    let attempt_id = opts.attempt_id.clone();
    let commit = opts.commit.clone();

    let mut query_results = Vec::with_capacity(queries.len());
    let mut bucket_stats = BTreeMap::<String, GatedBatchBucketStats>::new();
    let mut summary = GatedBatchBucketStats::default();

    for (idx, case) in queries.into_iter().enumerate() {
        let class_label = safe_batch_class_label(case.class_label.as_deref());
        let trial_attempt_id = attempt_id.as_ref().map(|id| format!("{id}:q{}", idx + 1));
        let trial = biocortex_retrieval_opt_in_gated_store_trial(
            store,
            BioCortexRetrievalOptInGatedStoreTrialOptions {
                runtime_transition_gate: runtime_transition_gate.clone(),
                runtime_influence_decision_packet: runtime_influence_decision_packet.clone(),
                query: case.query,
                tags_any: opts.tags_any.clone(),
                limit,
                mode: mode.clone(),
                per_call_opt_in: opts.per_call_opt_in,
                checkout: opts.checkout.clone(),
                timeout_ms,
                coverage_threshold,
                blend_alpha,
                attempt_id: trial_attempt_id,
                commit: commit.clone(),
            },
        )
        .await;
        let movement_class = gated_batch_movement_class(&trial).to_string();
        let result = gated_batch_trial_summary(idx, &class_label, &movement_class, &trial);
        summary.add_gated_trial(&trial);
        bucket_stats
            .entry(class_label)
            .or_default()
            .add_gated_trial(&trial);
        query_results.push(result);
    }

    let bucket_summary = bucket_stats
        .into_iter()
        .map(|(class_label, stats)| stats.to_value(Some(class_label)))
        .collect::<Vec<_>>();
    let raw_flags_all_false = query_results.iter().all(|row| {
        value_bool_is(row.get("raw_query_included"), false)
            && value_bool_is(row.get("raw_queries_included"), false)
            && value_bool_is(row.get("raw_keys_included"), false)
            && value_bool_is(row.get("content_included"), false)
            && value_bool_is(row.get("side_signal_raw_included"), false)
    });
    let query_count = query_results.len();
    let no_queries = query_count == 0;
    let all_transition_blocked =
        query_count > 0 && summary.transition_gate_blocked_count == query_count;

    let status = if no_queries {
        "empty_batch"
    } else if all_transition_blocked {
        "transition_gate_blocked"
    } else {
        "completed"
    };
    let attempt = json!({
        "attempt_id": required_or_value(attempt_id),
        "commit": required_or_value(commit),
        "mode": mode,
        "per_call_opt_in": opts.per_call_opt_in,
        "limit": limit,
        "query_count": query_count,
        "tag_filter_count": tag_filter_count,
        "coverage_threshold": round3(coverage_threshold),
        "blend_alpha": blend_alpha,
    });
    let input_contract = json!({
        "runtime_transition_gate_schema": runtime_transition_gate.get("schema").cloned().unwrap_or(Value::Null),
        "runtime_transition_gate_included": false,
        "runtime_influence_decision_packet_schema": runtime_influence_decision_packet.get("schema").cloned().unwrap_or(Value::Null),
        "runtime_influence_decision_packet_included": false,
        "requires_transition_gate_allowed": true,
        "accepts_aggregate_backed_decision_packet": true,
        "requires_aggregate_ready_when_provided": true,
        "redacted_evidence_aggregate_included": false,
        "aggregate_evidence_summary_included": false,
        "accepts_post_runtime_evidence_summary_decision_packet": true,
        "requires_post_runtime_evidence_summary_ready_when_provided": true,
        "post_runtime_evidence_summary_included": false,
        "accepts_capability_ledger_backed_transition_gate": true,
        "requires_capability_ledger_safe_when_provided": true,
        "capability_ledger_report_packet_included": false,
        "raw_queries_included": false,
        "raw_keys_included": false,
        "content_included": false,
        "side_signal_raw_included": false,
        "query_classes_sanitized": true,
    });
    let summary_value = summary.to_value(None);
    let safety = json!({
        "transition_gate_blocked_any": summary.transition_gate_blocked_count > 0,
        "transition_gate_blocked_all": query_count > 0 && summary.transition_gate_blocked_count == query_count,
        "transition_gate_allowed_any": summary.transition_gate_allowed_count > 0,
        "transition_gate_allowed_all": query_count > 0 && summary.transition_gate_allowed_count == query_count,
        "store_trial_called_any": summary.store_trial_called_count > 0,
        "store_trial_called_all": query_count > 0 && summary.store_trial_called_count == query_count,
        "calls_memory_search_any": summary.calls_memory_search_count > 0,
        "calls_memory_search_all": query_count > 0 && summary.calls_memory_search_count == query_count,
        "runs_biocortex_any": summary.runs_biocortex_count > 0,
        "changes_memory_search_order_any": summary.contract_changes_order_count > 0,
        "actual_return_order_changed_any": summary.actual_order_changed_count > 0,
        "default_calls_unchanged_all": query_count == 0 || summary.default_calls_unchanged_count == query_count,
        "gate_capability_ledger_backed_any": summary.gate_capability_ledger_backed_count > 0,
        "gate_capability_ledger_backed_all": query_count > 0
            && summary.gate_capability_ledger_backed_count == query_count,
        "gate_capability_ledger_safe_for_transition_all": summary.gate_capability_ledger_safe_count
            == summary.gate_capability_ledger_backed_count,
        "gate_capability_ledger_authorizes_runtime_influence_any": summary.gate_capability_ledger_authorizes_runtime_influence_count > 0,
        "gate_capability_ledger_report_packet_included_any": summary.gate_capability_ledger_report_packet_included_count > 0,
        "raw_query_included": false,
        "raw_queries_included": false,
        "raw_keys_included": false,
        "content_included": false,
        "side_signal_raw_included": false,
        "raw_flags_all_false": raw_flags_all_false,
    });
    let approval_state = if all_transition_blocked {
        "transition_gate_blocked"
    } else {
        "transition_gate_consumed_batch_diagnostics"
    };
    let authorization_state = if all_transition_blocked {
        "blocked"
    } else {
        "readiness_gated_explicit_opt_in_fts_batch_runtime_entry"
    };
    let calls_memory_search = summary.calls_memory_search_count > 0;
    let runs_biocortex = summary.runs_biocortex_count > 0;
    let changes_memory_search_order = summary.contract_changes_order_count > 0;
    let actual_return_order_changed = summary.actual_order_changed_count > 0;
    let default_calls_unchanged =
        query_count == 0 || summary.default_calls_unchanged_count == query_count;
    let boundary = json!({
        "mode": "runtime_transition_gated_batch_diagnostics",
        "read_only": true,
        "gate_required": true,
        "gate_consumed": summary.transition_gate_allowed_count > 0,
        "calls_memory_search": calls_memory_search,
        "runs_external_side_signal": runs_biocortex,
        "writes_temp_corpus": runs_biocortex,
        "links_biocortex_into_ab_runtime": false,
        "registers_embedding_backend": false,
        "calls_set_default_backend": false,
        "mutates_ab_memory": false,
        "writes_embeddings": false,
        "writes_coactivation": false,
        "writes_graph_edges": false,
        "changes_memory_search_order": changes_memory_search_order,
        "default_search_order_changed": false,
    });

    json!({
        "schema": BIOCORTEX_RETRIEVAL_OPT_IN_GATED_BATCH_DIAGNOSTICS_SCHEMA,
        "generated_at": now_secs(),
        "gated_batch_diagnostics": true,
        "implementation_stage": "runtime_transition_gated_batch_diagnostics",
        "authorization_scope": "explicit_opt_in_fts_runtime_influence",
        "purpose": "Batch redacted diagnostics that consume a runtime transition gate before any query may call the protected explicit opt-in FTS store trial.",
        "status": status,
        "attempt": attempt,
        "input_contract": input_contract,
        "summary": summary_value,
        "bucket_summary": bucket_summary,
        "query_results": query_results,
        "safety": safety,
        "approval_state": approval_state,
        "authorization_state": authorization_state,
        "approval_writes_allowed": false,
        "writes_approval": false,
        "calls_memory_search": calls_memory_search,
        "runs_biocortex": runs_biocortex,
        "registers_embedding_backend": false,
        "changes_memory_search_order": changes_memory_search_order,
        "actual_return_order_changed": actual_return_order_changed,
        "default_search_order_change_allowed": false,
        "default_calls_unchanged": default_calls_unchanged,
        "raw_queries_included": false,
        "raw_keys_included": false,
        "content_included": false,
        "side_signal_raw_included": false,
        "boundary": boundary,
    })
}

pub fn biocortex_retrieval_opt_in_runtime_readiness_packet(
    opts: BioCortexRetrievalOptInRuntimeReadinessPacketOptions,
) -> Value {
    let decision = opts.runtime_influence_decision_packet;
    let store_trial = opts.store_trial;
    let batch = opts.batch_diagnostics;

    let decision_schema_ok = value_str_eq(
        decision.get("schema"),
        BIOCORTEX_RETRIEVAL_OPT_IN_RUNTIME_INFLUENCE_DECISION_PACKET_SCHEMA,
    );
    let decision_authorized = value_bool_is(
        decision.pointer("/boundary_check/runtime_influence_authorized"),
        true,
    ) && value_bool_is(decision.get("runtime_adapter_approved"), true)
        && value_bool_is(
            decision.get("ordering_behavior_connection_authorized"),
            true,
        )
        && value_str_eq(
            decision.get("authorization_scope"),
            "explicit_opt_in_fts_runtime_influence",
        );
    let decision_aggregate_backed = value_bool_is(
        decision.pointer("/request_summary/aggregate_backed_review_request"),
        true,
    ) || value_bool_is(
        decision.pointer("/boundary_check/aggregate_backed_review_request"),
        true,
    );
    let decision_aggregate_ready = value_bool_is(
        decision.pointer("/boundary_check/aggregate_review_evidence_ready"),
        true,
    ) && value_bool_is(
        decision.pointer("/request_summary/redacted_evidence_aggregate_ready"),
        true,
    ) && value_str_eq(
        decision.pointer("/request_summary/aggregate_review_evidence_state"),
        "redacted_aggregate_ready",
    );
    let decision_aggregate_safe = value_bool_is(
        decision.pointer("/boundary_check/aggregate_safe_for_decision"),
        true,
    );
    let decision_aggregate_default_influence_not_ready = value_bool_is(
        decision.pointer("/request_summary/aggregate_default_influence_ready"),
        false,
    ) && value_bool_is(
        decision.pointer("/request_summary/default_influence_ready"),
        false,
    );
    let decision_aggregate_human_review_required = value_bool_is(
        decision.pointer("/request_summary/aggregate_human_review_required"),
        true,
    );
    let decision_post_runtime_evidence_backed = value_bool_is(
        decision.pointer("/request_summary/post_runtime_evidence_summary_backed_review_request"),
        true,
    ) || value_bool_is(
        decision.pointer("/boundary_check/post_runtime_evidence_summary_backed_review_request"),
        true,
    );
    let decision_post_runtime_evidence_ready = value_bool_is(
        decision.pointer("/boundary_check/post_runtime_evidence_summary_ready"),
        true,
    ) && value_bool_is(
        decision.pointer("/request_summary/post_runtime_evidence_summary_ready"),
        true,
    ) && value_str_eq(
        decision.pointer("/request_summary/post_runtime_evidence_summary_state"),
        "post_runtime_evidence_ready",
    );
    let decision_post_runtime_evidence_safe = value_bool_is(
        decision.pointer("/boundary_check/post_runtime_evidence_summary_safe_for_decision"),
        true,
    );
    let decision_post_runtime_default_influence_not_ready = value_bool_is(
        decision.pointer("/request_summary/post_runtime_evidence_summary_default_influence_ready"),
        false,
    ) && value_bool_is(
        decision.pointer("/request_summary/default_influence_ready"),
        false,
    );
    let decision_post_runtime_readiness_requirement_met = value_bool_is(
        decision.pointer("/boundary_check/post_runtime_runtime_readiness_requirement_met"),
        true,
    ) && value_bool_is(
        decision.pointer("/request_summary/post_runtime_runtime_readiness_requirement_met"),
        true,
    );
    let decision_post_runtime_gated_batch_ready = value_bool_is(
        decision.pointer("/boundary_check/post_runtime_readiness_gated_batch_evidence_ready"),
        true,
    ) && value_bool_is(
        decision.pointer("/request_summary/post_runtime_readiness_gated_batch_evidence_ready"),
        true,
    );
    let decision_post_runtime_batch_transition_gated = value_bool_is(
        decision.pointer("/boundary_check/post_runtime_batch_transition_gated"),
        true,
    ) && value_bool_is(
        decision.pointer("/request_summary/post_runtime_batch_transition_gated"),
        true,
    ) && value_str_eq(
        decision.pointer("/request_summary/post_runtime_batch_evidence_source"),
        "runtime_transition_gated_batch_diagnostics",
    );
    let decision_post_runtime_evidence_summary_redacted = value_bool_is(
        decision.pointer("/request_summary/post_runtime_evidence_summary_included"),
        false,
    ) && value_bool_is(
        decision.pointer("/boundary_check/post_runtime_evidence_summary_redacted"),
        true,
    );
    let decision_post_runtime_evidence_ok = if decision_post_runtime_evidence_backed {
        decision_post_runtime_evidence_ready
            && decision_post_runtime_evidence_safe
            && decision_post_runtime_default_influence_not_ready
            && decision_post_runtime_readiness_requirement_met
            && decision_post_runtime_gated_batch_ready
            && decision_post_runtime_batch_transition_gated
            && decision_post_runtime_evidence_summary_redacted
    } else {
        true
    };
    let decision_capability_ledger_backed = value_bool_is(
        decision.pointer("/request_summary/capability_ledger_backed_review_request"),
        true,
    ) || value_bool_is(
        decision.pointer("/boundary_check/capability_ledger_backed_review_request"),
        true,
    );
    let decision_capability_ledger_safe = value_bool_is(
        decision.pointer("/boundary_check/capability_ledger_safe_for_decision"),
        true,
    );
    let decision_capability_ledger_authorizes_nothing = value_bool_is(
        decision.pointer("/request_summary/capability_ledger_can_authorize_runtime_influence"),
        false,
    ) && value_bool_is(
        decision.pointer("/boundary_check/capability_ledger_authorizes_runtime_influence"),
        false,
    );
    let decision_capability_ledger_ok = !decision_capability_ledger_backed
        || (decision_capability_ledger_safe && decision_capability_ledger_authorizes_nothing);
    let decision_raw_absent =
        value_bool_is(
            decision.pointer("/input_contract/runtime_influence_decision_included"),
            false,
        ) && value_bool_is(
            decision.pointer("/input_contract/runtime_influence_review_request_included"),
            false,
        ) && value_bool_is(
            decision.pointer("/input_contract/redacted_evidence_aggregate_included"),
            false,
        ) && value_bool_is(
            decision.pointer("/input_contract/capability_ledger_report_packet_included"),
            false,
        ) && value_bool_is(
            decision.pointer("/input_contract/raw_query_included"),
            false,
        ) && value_bool_is(decision.pointer("/input_contract/raw_keys_included"), false)
            && value_bool_is(decision.pointer("/input_contract/content_included"), false)
            && value_bool_is(
                decision.pointer("/input_contract/human_decision_text_included"),
                false,
            );
    let decision_default_safe =
        value_bool_is(decision.get("default_search_order_change_allowed"), false)
            && value_bool_is(decision.get("default_calls_unchanged"), true)
            && value_bool_is(decision.get("calls_memory_search"), false)
            && value_bool_is(decision.get("runs_biocortex"), false)
            && value_bool_is(decision.get("changes_memory_search_order"), false)
            && value_bool_is(decision.get("ordering_behavior_connected"), false);

    let store_schema_ok = value_str_eq(
        store_trial.get("schema"),
        BIOCORTEX_RETRIEVAL_OPT_IN_STORE_TRIAL_SCHEMA,
    );
    let store_input_contract_ok = value_bool_is(
        store_trial.pointer("/input_contract/accepts_aggregate_backed_decision_packet"),
        true,
    ) && value_bool_is(
        store_trial.pointer("/input_contract/requires_aggregate_ready_when_provided"),
        true,
    ) && value_bool_is(
        store_trial.pointer("/input_contract/redacted_evidence_aggregate_included"),
        false,
    ) && value_bool_is(
        store_trial.pointer("/input_contract/aggregate_evidence_summary_included"),
        false,
    );
    let store_post_runtime_input_contract_ok = !decision_post_runtime_evidence_backed
        || (value_bool_is(
            store_trial
                .pointer("/input_contract/accepts_post_runtime_evidence_summary_decision_packet"),
            true,
        ) && value_bool_is(
            store_trial.pointer(
                "/input_contract/requires_post_runtime_evidence_summary_ready_when_provided",
            ),
            true,
        ) && value_bool_is(
            store_trial.pointer("/input_contract/post_runtime_evidence_summary_included"),
            false,
        ));
    let store_input_contract_ok = store_input_contract_ok && store_post_runtime_input_contract_ok;
    let store_raw_absent = value_bool_is(store_trial.get("raw_query_included"), false)
        && value_bool_is(store_trial.get("raw_keys_included"), false)
        && value_bool_is(store_trial.get("content_included"), false)
        && value_bool_is(store_trial.get("side_signal_raw_included"), false)
        && value_bool_is(
            store_trial.pointer("/input_contract/raw_query_included"),
            false,
        )
        && value_bool_is(
            store_trial.pointer("/input_contract/raw_keys_included"),
            false,
        )
        && value_bool_is(
            store_trial.pointer("/input_contract/content_included"),
            false,
        )
        && value_bool_is(
            store_trial.pointer("/input_contract/side_signal_raw_included"),
            false,
        );
    let store_aggregate_preflight_ok = value_bool_is(
        store_trial.pointer("/runtime_preflight/decision_packet_authorized"),
        true,
    ) && value_bool_is(
        store_trial.pointer("/runtime_preflight/decision_packet_aggregate_backed"),
        true,
    ) && value_bool_is(
        store_trial.pointer("/runtime_preflight/decision_packet_aggregate_review_evidence_ready"),
        true,
    ) && value_bool_is(
        store_trial.pointer("/runtime_preflight/legacy_decision_packet_without_aggregate_allowed"),
        false,
    ) && value_bool_is(
        store_trial.pointer("/runtime_preflight/decision_packet_aggregate_safe_for_trial"),
        true,
    );
    let store_post_runtime_preflight_ok = !decision_post_runtime_evidence_backed
        || (value_bool_is(
            store_trial
                .pointer("/runtime_preflight/decision_packet_post_runtime_evidence_summary_backed"),
            true,
        ) && value_bool_is(
            store_trial
                .pointer("/runtime_preflight/decision_packet_post_runtime_evidence_summary_ready"),
            true,
        ) && value_bool_is(
            store_trial.pointer(
                "/runtime_preflight/legacy_decision_packet_without_post_runtime_evidence_summary_allowed",
            ),
            false,
        ) && value_bool_is(
            store_trial.pointer(
                "/runtime_preflight/decision_packet_post_runtime_evidence_summary_safe_for_trial",
            ),
            true,
        ) && value_str_eq(
            store_trial
                .pointer("/runtime_preflight/decision_packet_post_runtime_evidence_summary_state"),
            "post_runtime_evidence_ready",
        ));
    let store_blockers = json_string_array(store_trial.pointer("/runtime_preflight/blockers"));
    let store_blockers_without_live_data = store_blockers
        .iter()
        .filter(|blocker| blocker.as_str() != "baseline_empty")
        .cloned()
        .collect::<Vec<_>>();
    let store_baseline_empty = store_trial
        .pointer("/baseline_order/key_count")
        .and_then(Value::as_u64)
        == Some(0);
    let store_preflight_acceptable = value_bool_is(
        store_trial.pointer("/runtime_preflight/adapter_allowed"),
        true,
    ) || (store_baseline_empty
        && !store_blockers.is_empty()
        && store_blockers_without_live_data.is_empty());
    let store_default_safe = value_bool_is(
        store_trial.get("default_search_order_change_allowed"),
        false,
    ) && value_bool_is(store_trial.get("default_calls_unchanged"), true)
        && value_bool_is(store_trial.get("changes_memory_search_order"), false);

    let batch_legacy_schema_ok = value_str_eq(
        batch.get("schema"),
        BIOCORTEX_RETRIEVAL_OPT_IN_BATCH_DIAGNOSTICS_SCHEMA,
    );
    let batch_gated_schema_ok = value_str_eq(
        batch.get("schema"),
        BIOCORTEX_RETRIEVAL_OPT_IN_GATED_BATCH_DIAGNOSTICS_SCHEMA,
    );
    let batch_schema_ok = batch_legacy_schema_ok || batch_gated_schema_ok;
    let batch_transition_gated = batch_gated_schema_ok;
    let batch_evidence_source = if batch_transition_gated {
        "runtime_transition_gated_batch_diagnostics"
    } else {
        "store_opt_in_batch_diagnostics"
    };
    let batch_input_contract_ok = value_bool_is(
        batch.pointer("/input_contract/accepts_aggregate_backed_decision_packet"),
        true,
    ) && value_bool_is(
        batch.pointer("/input_contract/requires_aggregate_ready_when_provided"),
        true,
    ) && value_bool_is(
        batch.pointer("/input_contract/redacted_evidence_aggregate_included"),
        false,
    ) && value_bool_is(
        batch.pointer("/input_contract/aggregate_evidence_summary_included"),
        false,
    ) && (!batch_transition_gated
        || value_bool_is(
            batch.pointer("/input_contract/requires_transition_gate_allowed"),
            true,
        ));
    let batch_post_runtime_input_contract_ok = !decision_post_runtime_evidence_backed
        || (value_bool_is(
            batch.pointer("/input_contract/accepts_post_runtime_evidence_summary_decision_packet"),
            true,
        ) && value_bool_is(
            batch.pointer(
                "/input_contract/requires_post_runtime_evidence_summary_ready_when_provided",
            ),
            true,
        ) && value_bool_is(
            batch.pointer("/input_contract/post_runtime_evidence_summary_included"),
            false,
        ));
    let batch_input_contract_ok = batch_input_contract_ok && batch_post_runtime_input_contract_ok;
    let batch_query_results = batch
        .get("query_results")
        .and_then(Value::as_array)
        .cloned()
        .unwrap_or_default();
    let batch_query_count = batch
        .pointer("/summary/query_count")
        .and_then(Value::as_u64)
        .unwrap_or(batch_query_results.len() as u64);
    let batch_baseline_completed_count = batch
        .pointer("/summary/baseline_completed_count")
        .and_then(Value::as_u64)
        .unwrap_or(0);
    let batch_baseline_empty_count = batch
        .pointer("/summary/baseline_empty_count")
        .and_then(Value::as_u64)
        .unwrap_or(0);
    let batch_transition_gate_allowed_count = if batch_transition_gated {
        batch
            .pointer("/summary/transition_gate_allowed_count")
            .and_then(Value::as_u64)
            .unwrap_or(0)
    } else {
        0
    };
    let batch_transition_gate_blocked_count = if batch_transition_gated {
        batch
            .pointer("/summary/transition_gate_blocked_count")
            .and_then(Value::as_u64)
            .unwrap_or(0)
    } else {
        0
    };
    let batch_store_trial_called_count = if batch_transition_gated {
        batch
            .pointer("/summary/store_trial_called_count")
            .and_then(Value::as_u64)
            .unwrap_or(0)
    } else {
        0
    };
    let batch_adapter_allowed_count = if batch_transition_gated {
        batch
            .pointer("/summary/store_trial_adapter_allowed_count")
            .and_then(Value::as_u64)
            .unwrap_or(0)
    } else {
        batch
            .pointer("/summary/adapter_allowed_count")
            .and_then(Value::as_u64)
            .unwrap_or(0)
    };
    let batch_side_signal_ok_count = batch
        .pointer("/summary/side_signal_ok_count")
        .and_then(Value::as_u64)
        .unwrap_or(0);
    let batch_experimental_source_count = batch
        .pointer("/summary/experimental_source_count")
        .and_then(Value::as_u64)
        .unwrap_or(0);
    let batch_actual_order_changed_count = batch
        .pointer("/summary/actual_order_changed_count")
        .and_then(Value::as_u64)
        .unwrap_or(0);
    let batch_calls_memory_search_count = batch
        .pointer("/summary/calls_memory_search_count")
        .and_then(Value::as_u64)
        .unwrap_or(0);
    let batch_raw_absent = value_bool_is(batch.get("raw_queries_included"), false)
        && value_bool_is(batch.get("raw_keys_included"), false)
        && value_bool_is(batch.get("content_included"), false)
        && value_bool_is(batch.get("side_signal_raw_included"), false)
        && value_bool_is(batch.pointer("/safety/raw_flags_all_false"), true)
        && value_bool_is(batch.pointer("/input_contract/raw_queries_included"), false)
        && value_bool_is(batch.pointer("/input_contract/raw_keys_included"), false)
        && value_bool_is(batch.pointer("/input_contract/content_included"), false)
        && value_bool_is(
            batch.pointer("/input_contract/side_signal_raw_included"),
            false,
        );
    let batch_default_safe = value_bool_is(batch.get("default_search_order_change_allowed"), false)
        && value_bool_is(batch.get("default_calls_unchanged"), true)
        && value_bool_is(batch.pointer("/safety/default_calls_unchanged_all"), true);
    let batch_transition_gate_ok = !batch_transition_gated
        || (!batch_query_results.is_empty()
            && batch_transition_gate_allowed_count == batch_query_count
            && batch_transition_gate_blocked_count == 0
            && value_bool_is(batch.pointer("/safety/transition_gate_allowed_all"), true));
    let batch_aggregate_preflight_ok = if batch_transition_gated {
        !batch_query_results.is_empty()
            && batch_transition_gate_ok
            && batch_store_trial_called_count == batch_transition_gate_allowed_count
            && value_bool_is(batch.pointer("/safety/store_trial_called_all"), true)
    } else {
        !batch_query_results.is_empty()
            && batch_query_results.iter().all(|row| {
                value_bool_is(row.pointer("/preflight/decision_packet_authorized"), true)
                    && value_bool_is(
                        row.pointer("/preflight/decision_packet_aggregate_backed"),
                        true,
                    )
                    && value_bool_is(
                        row.pointer("/preflight/decision_packet_aggregate_review_evidence_ready"),
                        true,
                    )
                    && value_bool_is(
                        row.pointer("/preflight/legacy_decision_packet_without_aggregate_allowed"),
                        false,
                    )
                    && value_bool_is(
                        row.pointer("/preflight/decision_packet_aggregate_safe_for_trial"),
                        true,
                    )
            })
    };
    let row_post_runtime_evidence_preflight_ok = |row: &Value, prefix: &str| {
        value_bool_is(
            row.pointer(&format!(
                "{prefix}/decision_packet_post_runtime_evidence_summary_backed"
            )),
            true,
        ) && value_bool_is(
            row.pointer(&format!(
                "{prefix}/decision_packet_post_runtime_evidence_summary_ready"
            )),
            true,
        ) && value_bool_is(
            row.pointer(&format!(
                "{prefix}/legacy_decision_packet_without_post_runtime_evidence_summary_allowed"
            )),
            false,
        ) && value_bool_is(
            row.pointer(&format!(
                "{prefix}/decision_packet_post_runtime_evidence_summary_safe_for_trial"
            )),
            true,
        ) && value_str_eq(
            row.pointer(&format!(
                "{prefix}/decision_packet_post_runtime_evidence_summary_state"
            )),
            "post_runtime_evidence_ready",
        )
    };
    let batch_post_runtime_preflight_ok = !decision_post_runtime_evidence_backed
        || (!batch_query_results.is_empty()
            && batch_query_results.iter().all(|row| {
                if batch_transition_gated {
                    row_post_runtime_evidence_preflight_ok(row, "/store_trial")
                } else {
                    row_post_runtime_evidence_preflight_ok(row, "/preflight")
                }
            }));
    let batch_preflight_acceptable = if batch_transition_gated {
        !batch_query_results.is_empty()
            && batch_query_results.iter().all(|row| {
                let transition_allowed = value_bool_is(
                    row.pointer("/transition_preflight/transition_gate_allowed"),
                    true,
                );
                let store_trial_called = value_bool_is(row.pointer("/store_trial/called"), true);
                if !transition_allowed || !store_trial_called {
                    false
                } else if value_bool_is(row.pointer("/store_trial/runtime_adapter_allowed"), true) {
                    row.pointer("/store_trial/runtime_preflight_blocker_count")
                        .and_then(Value::as_u64)
                        .unwrap_or(0)
                        == 0
                } else {
                    row.pointer("/store_trial/baseline_key_count")
                        .and_then(Value::as_u64)
                        == Some(0)
                        && row
                            .pointer("/store_trial/runtime_preflight_blocker_count")
                            .and_then(Value::as_u64)
                            .unwrap_or(0)
                            >= 1
                }
            })
    } else {
        !batch_query_results.is_empty()
            && batch_query_results.iter().all(|row| {
                if value_bool_is(row.pointer("/preflight/adapter_allowed"), true) {
                    row.pointer("/preflight/blocker_count")
                        .and_then(Value::as_u64)
                        .unwrap_or(0)
                        == 0
                } else {
                    row.pointer("/baseline/key_count").and_then(Value::as_u64) == Some(0)
                        && row
                            .pointer("/preflight/blocker_count")
                            .and_then(Value::as_u64)
                            .unwrap_or(0)
                            == 1
                }
            })
    };

    let live_probe_has_candidates =
        batch_query_count > 0 && batch_baseline_empty_count < batch_query_count;
    let live_probe_allows_runtime = live_probe_has_candidates
        && batch_adapter_allowed_count > 0
        && batch_side_signal_ok_count > 0;
    let live_probe_state = if batch_query_count == 0 {
        "no_batch_queries"
    } else if batch_baseline_empty_count == batch_query_count {
        "control_plane_ready_no_live_candidates"
    } else if live_probe_allows_runtime
        && batch_adapter_allowed_count == batch_query_count - batch_baseline_empty_count
        && batch_side_signal_ok_count == batch_adapter_allowed_count
    {
        "live_probe_ready"
    } else {
        "live_probe_partial_or_blocked"
    };

    let mut blockers = Vec::new();
    push_string_blocker(
        &mut blockers,
        decision_schema_ok,
        "decision_packet_schema_invalid",
    );
    push_string_blocker(
        &mut blockers,
        decision_authorized,
        "decision_packet_not_runtime_authorized",
    );
    push_string_blocker(
        &mut blockers,
        decision_aggregate_backed,
        "decision_packet_not_aggregate_backed",
    );
    push_string_blocker(
        &mut blockers,
        decision_aggregate_ready,
        "decision_packet_aggregate_not_ready",
    );
    push_string_blocker(
        &mut blockers,
        decision_aggregate_safe,
        "decision_packet_aggregate_not_safe",
    );
    push_string_blocker(
        &mut blockers,
        decision_aggregate_default_influence_not_ready,
        "decision_packet_aggregate_default_influence_ready",
    );
    push_string_blocker(
        &mut blockers,
        decision_aggregate_human_review_required,
        "decision_packet_aggregate_missing_human_review_requirement",
    );
    if decision_post_runtime_evidence_backed {
        push_string_blocker(
            &mut blockers,
            decision_post_runtime_evidence_ok,
            "decision_packet_post_runtime_evidence_summary_not_ready",
        );
    }
    if decision_capability_ledger_backed {
        push_string_blocker(
            &mut blockers,
            decision_capability_ledger_ok,
            "decision_packet_capability_ledger_not_safe",
        );
    }
    push_string_blocker(
        &mut blockers,
        decision_raw_absent,
        "decision_packet_raw_input_included",
    );
    push_string_blocker(
        &mut blockers,
        decision_default_safe,
        "decision_packet_default_or_runtime_side_effect_unexpected",
    );
    push_string_blocker(&mut blockers, store_schema_ok, "store_trial_schema_invalid");
    push_string_blocker(
        &mut blockers,
        store_input_contract_ok,
        "store_trial_input_contract_unexpected",
    );
    push_string_blocker(
        &mut blockers,
        store_raw_absent,
        "store_trial_raw_input_included",
    );
    push_string_blocker(
        &mut blockers,
        store_aggregate_preflight_ok,
        "store_trial_aggregate_preflight_not_ready",
    );
    push_string_blocker(
        &mut blockers,
        store_post_runtime_preflight_ok,
        "store_trial_post_runtime_evidence_preflight_not_ready",
    );
    push_string_blocker(
        &mut blockers,
        store_preflight_acceptable,
        "store_trial_preflight_blocked",
    );
    push_string_blocker(
        &mut blockers,
        store_default_safe,
        "store_trial_default_order_or_side_effect_unexpected",
    );
    push_string_blocker(
        &mut blockers,
        batch_schema_ok,
        "batch_diagnostics_schema_invalid",
    );
    push_string_blocker(
        &mut blockers,
        batch_input_contract_ok,
        "batch_diagnostics_input_contract_unexpected",
    );
    push_string_blocker(
        &mut blockers,
        batch_raw_absent,
        "batch_diagnostics_raw_input_included",
    );
    push_string_blocker(
        &mut blockers,
        !batch_transition_gated || batch_transition_gate_ok,
        "batch_transition_gate_not_allowed",
    );
    push_string_blocker(
        &mut blockers,
        batch_aggregate_preflight_ok,
        "batch_query_aggregate_evidence_not_ready",
    );
    push_string_blocker(
        &mut blockers,
        batch_post_runtime_preflight_ok,
        "batch_query_post_runtime_evidence_not_ready",
    );
    push_string_blocker(
        &mut blockers,
        batch_preflight_acceptable,
        "batch_query_preflight_blocked",
    );
    push_string_blocker(
        &mut blockers,
        batch_default_safe,
        "batch_diagnostics_default_order_or_side_effect_unexpected",
    );

    let control_plane_ready = blockers.is_empty();
    let may_accept_controlled_opt_in_calls = control_plane_ready;
    let live_order_influence_ready = control_plane_ready && live_probe_allows_runtime;

    json!({
        "schema": BIOCORTEX_RETRIEVAL_OPT_IN_RUNTIME_READINESS_PACKET_SCHEMA,
        "generated_at": now_secs(),
        "read_only": true,
        "runtime_readiness_packet": true,
        "implementation_stage": "controlled_opt_in_runtime_readiness_packet",
        "authorization_scope": "explicit_opt_in_fts_runtime_influence",
        "purpose": "Consume the aggregate-backed runtime-influence decision packet plus downstream store-trial and batch-diagnostics summaries to report controlled opt-in runtime readiness without granting new authorization or changing default memory_search.",
        "status": if control_plane_ready { "completed" } else { "blocked" },
        "reviewer": optional_string_json(opts.reviewer),
        "commit": optional_string_json(opts.commit),
        "forum_post_id": optional_string_json(opts.forum_post_id),
        "memory_key": optional_string_json(opts.memory_key),
        "input_contract": {
            "runtime_influence_decision_packet_schema": decision.get("schema").cloned().unwrap_or(Value::Null),
            "store_trial_schema": store_trial.get("schema").cloned().unwrap_or(Value::Null),
            "batch_diagnostics_schema": batch.get("schema").cloned().unwrap_or(Value::Null),
            "batch_diagnostics_evidence_source": batch_evidence_source,
            "batch_diagnostics_transition_gated": batch_transition_gated,
            "runtime_influence_decision_packet_included": false,
            "store_trial_included": false,
            "batch_diagnostics_included": false,
            "requires_aggregate_backed_decision_packet": true,
            "requires_downstream_aggregate_preflight": true,
            "accepts_post_runtime_evidence_summary_decision_packet": true,
            "requires_post_runtime_evidence_summary_ready_when_provided": true,
            "post_runtime_evidence_summary_included": false,
            "accepts_capability_ledger_backed_decision_packet": true,
            "requires_capability_ledger_safe_when_provided": true,
            "capability_ledger_report_packet_included": false,
            "unknown_fields_ignored": true,
            "raw_queries_included": false,
            "raw_keys_included": false,
            "content_included": false,
            "side_signal_raw_included": false,
            "human_decision_text_included": false,
        },
        "decision_summary": {
            "schema_ok": decision_schema_ok,
            "runtime_influence_authorized": decision_authorized,
            "aggregate_backed_review_request": decision_aggregate_backed,
            "aggregate_review_evidence_ready": decision_aggregate_ready,
            "aggregate_safe_for_decision": decision_aggregate_safe,
            "aggregate_default_influence_ready": !decision_aggregate_default_influence_not_ready,
            "aggregate_human_review_required": decision_aggregate_human_review_required,
            "post_runtime_evidence_summary_backed_review_request": decision_post_runtime_evidence_backed,
            "post_runtime_evidence_summary_ready": decision_post_runtime_evidence_backed
                && decision_post_runtime_evidence_ok,
            "legacy_decision_packet_without_post_runtime_evidence_summary_allowed": !decision_post_runtime_evidence_backed,
            "post_runtime_evidence_summary_safe_for_decision": decision_post_runtime_evidence_safe,
            "post_runtime_evidence_summary_default_influence_ready": if decision_post_runtime_evidence_backed {
                decision
                    .pointer("/request_summary/post_runtime_evidence_summary_default_influence_ready")
                    .cloned()
                    .unwrap_or(Value::Bool(false))
            } else {
                Value::Bool(false)
            },
            "post_runtime_runtime_readiness_requirement_met": !decision_post_runtime_evidence_backed
                || decision_post_runtime_readiness_requirement_met,
            "post_runtime_readiness_gated_batch_evidence_ready": !decision_post_runtime_evidence_backed
                || decision_post_runtime_gated_batch_ready,
            "post_runtime_batch_transition_gated": !decision_post_runtime_evidence_backed
                || decision_post_runtime_batch_transition_gated,
            "post_runtime_batch_evidence_source": decision
                .pointer("/request_summary/post_runtime_batch_evidence_source")
                .cloned()
                .unwrap_or(Value::Null),
            "post_runtime_evidence_summary_state": decision
                .pointer("/request_summary/post_runtime_evidence_summary_state")
                .cloned()
                .unwrap_or(Value::Null),
            "capability_ledger_backed_review_request": decision_capability_ledger_backed,
            "capability_ledger_safe_for_decision": decision_capability_ledger_ok,
            "legacy_decision_packet_without_capability_ledger_allowed": !decision_capability_ledger_backed,
            "capability_ledger_input_schema": decision
                .pointer("/request_summary/capability_ledger_input_schema")
                .cloned()
                .unwrap_or(Value::Null),
            "capability_ledger_input_schema_version": decision
                .pointer("/request_summary/capability_ledger_input_schema_version")
                .cloned()
                .unwrap_or(Value::Null),
            "capability_ledger_can_authorize_runtime_influence": false,
            "capability_ledger_report_packet_included": false,
            "raw_inputs_absent": decision_raw_absent,
            "default_order_safe": decision_default_safe,
        },
        "store_trial_summary": {
            "schema_ok": store_schema_ok,
            "status": store_trial.get("status").cloned().unwrap_or(Value::Null),
            "input_contract_ok": store_input_contract_ok,
            "raw_inputs_absent": store_raw_absent,
            "aggregate_preflight_ok": store_aggregate_preflight_ok,
            "post_runtime_evidence_preflight_ok": store_post_runtime_preflight_ok,
            "preflight_acceptable": store_preflight_acceptable,
            "adapter_allowed": store_trial.pointer("/runtime_preflight/adapter_allowed").cloned().unwrap_or(Value::Bool(false)),
            "blockers": store_blockers,
            "blockers_without_live_data": store_blockers_without_live_data,
            "baseline_completed": store_trial.pointer("/baseline_order/completed").cloned().unwrap_or(Value::Bool(false)),
            "baseline_key_count": store_trial.pointer("/baseline_order/key_count").cloned().unwrap_or_else(|| json!(0)),
            "side_signal_attempted": store_trial.pointer("/side_signal/attempted").cloned().unwrap_or(Value::Bool(false)),
            "side_signal_status": store_trial.pointer("/side_signal/status").cloned().unwrap_or(Value::Null),
            "returned_order_source": store_trial.pointer("/returned_order/source").cloned().unwrap_or_else(|| json!("baseline")),
            "actual_return_order_changed": store_trial.pointer("/returned_order/actual_return_order_changed").cloned().unwrap_or(Value::Bool(false)),
            "default_order_safe": store_default_safe,
        },
        "batch_summary": {
            "schema_ok": batch_schema_ok,
            "legacy_schema_ok": batch_legacy_schema_ok,
            "gated_schema_ok": batch_gated_schema_ok,
            "evidence_source": batch_evidence_source,
            "transition_gated": batch_transition_gated,
            "transition_gate_ok": batch_transition_gate_ok,
            "input_contract_ok": batch_input_contract_ok,
            "raw_inputs_absent": batch_raw_absent,
            "aggregate_preflight_ok": batch_aggregate_preflight_ok,
            "post_runtime_evidence_preflight_ok": batch_post_runtime_preflight_ok,
            "preflight_acceptable": batch_preflight_acceptable,
            "query_count": batch_query_count,
            "transition_gate_allowed_count": batch_transition_gate_allowed_count,
            "transition_gate_blocked_count": batch_transition_gate_blocked_count,
            "store_trial_called_count": batch_store_trial_called_count,
            "baseline_completed_count": batch_baseline_completed_count,
            "baseline_empty_count": batch_baseline_empty_count,
            "adapter_allowed_count": batch_adapter_allowed_count,
            "side_signal_ok_count": batch_side_signal_ok_count,
            "experimental_source_count": batch_experimental_source_count,
            "actual_order_changed_count": batch_actual_order_changed_count,
            "calls_memory_search_count": batch_calls_memory_search_count,
            "default_order_safe": batch_default_safe,
        },
        "readiness": {
            "control_plane_ready": control_plane_ready,
            "live_probe_state": live_probe_state,
            "live_probe_has_candidates": live_probe_has_candidates,
            "live_order_influence_ready": live_order_influence_ready,
            "may_accept_controlled_explicit_opt_in_fts_calls": may_accept_controlled_opt_in_calls,
            "may_change_default_memory_search_order": false,
            "default_influence_ready": false,
            "why_not_default": "this packet only summarizes explicit per-call FTS opt-in readiness; default memory_search order remains unchanged and still requires separate authorization",
            "recommended_next_step": if control_plane_ready && live_probe_has_candidates {
                "operator_can_run_controlled_explicit_opt_in_fts_calls"
            } else if control_plane_ready {
                "control_plane_ready_waiting_for_live_candidates"
            } else {
                "fix_blockers_before_runtime_use"
            },
        },
        "boundary_check": {
            "runtime_readiness_ready": control_plane_ready,
            "blockers": blockers,
            "capability_ledger_backed_decision_packet": decision_capability_ledger_backed,
            "capability_ledger_safe_for_readiness": decision_capability_ledger_ok,
            "legacy_decision_packet_without_capability_ledger_allowed": !decision_capability_ledger_backed,
            "capability_ledger_authorizes_runtime_influence": decision_capability_ledger_backed
                && !decision_capability_ledger_authorizes_nothing,
            "requires_per_call_opt_in": true,
            "requires_operator_disable_absent": true,
            "requires_fail_open_to_baseline": true,
            "requires_redacted_audit_only": true,
            "requires_baseline_candidate_recall": true,
            "this_packet_grants_new_authorization": false,
            "this_packet_changes_return_order": false,
            "this_packet_allows_default_search_order_change": false,
        },
        "approval_state": "runtime_readiness_only",
        "authorization_state": if decision_authorized {
            "summarizes_existing_explicit_opt_in_runtime_influence_authorization"
        } else {
            "not_authorized"
        },
        "approval_writes_allowed": false,
        "writes_approval": false,
        "calls_memory_search": false,
        "runs_biocortex": false,
        "registers_embedding_backend": false,
        "changes_memory_search_order": false,
        "default_search_order_change_allowed": false,
        "default_calls_unchanged": true,
        "raw_queries_included": false,
        "raw_keys_included": false,
        "content_included": false,
        "side_signal_raw_included": false,
        "human_decision_text_included": false,
    })
}

pub fn biocortex_retrieval_opt_in_runtime_transition_gate(
    opts: BioCortexRetrievalOptInRuntimeTransitionGateOptions,
) -> Value {
    let readiness = opts.runtime_readiness_packet;
    let mode = normalize_token(&opts.mode);
    let requested_mode_authorized = mode == "fts";
    let requested_hybrid_influence = mode == "hybrid";
    let requested_semantic_influence = mode == "semantic";

    let readiness_schema_ok = value_str_eq(
        readiness.get("schema"),
        BIOCORTEX_RETRIEVAL_OPT_IN_RUNTIME_READINESS_PACKET_SCHEMA,
    );
    let readiness_read_only = value_bool_is(readiness.get("read_only"), true);
    let readiness_marker_ok = value_bool_is(readiness.get("runtime_readiness_packet"), true);
    let readiness_stage_ok = value_str_eq(
        readiness.get("implementation_stage"),
        "controlled_opt_in_runtime_readiness_packet",
    );
    let readiness_scope_ok = value_str_eq(
        readiness.get("authorization_scope"),
        "explicit_opt_in_fts_runtime_influence",
    );
    let readiness_completed = value_str_eq(readiness.get("status"), "completed");
    let readiness_control_plane_ready =
        value_bool_is(readiness.pointer("/readiness/control_plane_ready"), true);
    let readiness_may_accept_calls = value_bool_is(
        readiness.pointer("/readiness/may_accept_controlled_explicit_opt_in_fts_calls"),
        true,
    );
    let readiness_default_influence_not_ready = value_bool_is(
        readiness.pointer("/readiness/default_influence_ready"),
        false,
    ) && value_bool_is(
        readiness.pointer("/readiness/may_change_default_memory_search_order"),
        false,
    );
    let readiness_post_runtime_evidence_backed = value_bool_is(
        readiness.pointer("/decision_summary/post_runtime_evidence_summary_backed_review_request"),
        true,
    );
    let readiness_post_runtime_evidence_ready = !readiness_post_runtime_evidence_backed
        || (value_bool_is(
            readiness.pointer("/decision_summary/post_runtime_evidence_summary_ready"),
            true,
        ) && value_bool_is(
            readiness.pointer(
                "/decision_summary/legacy_decision_packet_without_post_runtime_evidence_summary_allowed",
            ),
            false,
        ) && value_bool_is(
            readiness.pointer("/decision_summary/post_runtime_evidence_summary_safe_for_decision"),
            true,
        ) && value_bool_is(
            readiness
                .pointer("/decision_summary/post_runtime_evidence_summary_default_influence_ready"),
            false,
        ) && value_bool_is(
            readiness.pointer(
                "/decision_summary/post_runtime_runtime_readiness_requirement_met",
            ),
            true,
        ) && value_bool_is(
            readiness.pointer(
                "/decision_summary/post_runtime_readiness_gated_batch_evidence_ready",
            ),
            true,
        ) && value_bool_is(
            readiness.pointer("/decision_summary/post_runtime_batch_transition_gated"),
            true,
        ) && value_str_eq(
            readiness.pointer("/decision_summary/post_runtime_batch_evidence_source"),
            "runtime_transition_gated_batch_diagnostics",
        ) && value_str_eq(
            readiness.pointer("/decision_summary/post_runtime_evidence_summary_state"),
            "post_runtime_evidence_ready",
        ));
    let readiness_store_post_runtime_preflight_ok = !readiness_post_runtime_evidence_backed
        || value_bool_is(
            readiness.pointer("/store_trial_summary/post_runtime_evidence_preflight_ok"),
            true,
        );
    let readiness_batch_post_runtime_preflight_ok = !readiness_post_runtime_evidence_backed
        || value_bool_is(
            readiness.pointer("/batch_summary/post_runtime_evidence_preflight_ok"),
            true,
        );
    let readiness_post_runtime_evidence_chain_ok = readiness_post_runtime_evidence_ready
        && readiness_store_post_runtime_preflight_ok
        && readiness_batch_post_runtime_preflight_ok;
    let readiness_capability_ledger_backed = value_bool_is(
        readiness.pointer("/decision_summary/capability_ledger_backed_review_request"),
        true,
    ) || value_bool_is(
        readiness.pointer("/boundary_check/capability_ledger_backed_decision_packet"),
        true,
    );
    let readiness_capability_ledger_safe = value_bool_is(
        readiness.pointer("/decision_summary/capability_ledger_safe_for_decision"),
        true,
    ) && value_bool_is(
        readiness.pointer("/boundary_check/capability_ledger_safe_for_readiness"),
        true,
    );
    let readiness_capability_ledger_authorizes_nothing = value_bool_is(
        readiness.pointer("/decision_summary/capability_ledger_can_authorize_runtime_influence"),
        false,
    ) && value_bool_is(
        readiness.pointer("/boundary_check/capability_ledger_authorizes_runtime_influence"),
        false,
    );
    let readiness_capability_ledger_redacted = value_bool_is(
        readiness.pointer("/input_contract/capability_ledger_report_packet_included"),
        false,
    ) && value_bool_is(
        readiness.pointer("/decision_summary/capability_ledger_report_packet_included"),
        false,
    );
    let readiness_capability_ledger_ok = !readiness_capability_ledger_backed
        || (readiness_capability_ledger_safe
            && readiness_capability_ledger_authorizes_nothing
            && readiness_capability_ledger_redacted);
    let boundary_ready = value_bool_is(
        readiness.pointer("/boundary_check/runtime_readiness_ready"),
        true,
    );
    let readiness_blockers = json_string_array(readiness.pointer("/boundary_check/blockers"));
    let readiness_no_blockers = readiness_blockers.is_empty();
    let boundary_requires_per_call = value_bool_is(
        readiness.pointer("/boundary_check/requires_per_call_opt_in"),
        true,
    );
    let boundary_requires_operator_enabled = value_bool_is(
        readiness.pointer("/boundary_check/requires_operator_disable_absent"),
        true,
    );
    let boundary_requires_fail_open = value_bool_is(
        readiness.pointer("/boundary_check/requires_fail_open_to_baseline"),
        true,
    );
    let boundary_requires_redacted_audit = value_bool_is(
        readiness.pointer("/boundary_check/requires_redacted_audit_only"),
        true,
    );
    let boundary_requires_baseline_recall = value_bool_is(
        readiness.pointer("/boundary_check/requires_baseline_candidate_recall"),
        true,
    );
    let boundary_grants_nothing = value_bool_is(
        readiness.pointer("/boundary_check/this_packet_grants_new_authorization"),
        false,
    ) && value_bool_is(
        readiness.pointer("/boundary_check/this_packet_changes_return_order"),
        false,
    ) && value_bool_is(
        readiness.pointer("/boundary_check/this_packet_allows_default_search_order_change"),
        false,
    );
    let readiness_input_raw_absent = value_bool_is(
        readiness.pointer("/input_contract/runtime_influence_decision_packet_included"),
        false,
    ) && value_bool_is(
        readiness.pointer("/input_contract/store_trial_included"),
        false,
    ) && value_bool_is(
        readiness.pointer("/input_contract/batch_diagnostics_included"),
        false,
    ) && value_bool_is(
        readiness.pointer("/input_contract/capability_ledger_report_packet_included"),
        false,
    ) && value_bool_is(
        readiness.pointer("/input_contract/raw_queries_included"),
        false,
    ) && value_bool_is(
        readiness.pointer("/input_contract/raw_keys_included"),
        false,
    ) && value_bool_is(
        readiness.pointer("/input_contract/content_included"),
        false,
    ) && value_bool_is(
        readiness.pointer("/input_contract/side_signal_raw_included"),
        false,
    ) && value_bool_is(
        readiness.pointer("/input_contract/human_decision_text_included"),
        false,
    );
    let readiness_side_effects_absent =
        value_bool_is(readiness.get("approval_writes_allowed"), false)
            && value_bool_is(readiness.get("writes_approval"), false)
            && value_bool_is(readiness.get("calls_memory_search"), false)
            && value_bool_is(readiness.get("runs_biocortex"), false)
            && value_bool_is(readiness.get("registers_embedding_backend"), false)
            && value_bool_is(readiness.get("changes_memory_search_order"), false)
            && value_bool_is(readiness.get("default_search_order_change_allowed"), false)
            && value_bool_is(readiness.get("default_calls_unchanged"), true)
            && value_bool_is(readiness.get("raw_queries_included"), false)
            && value_bool_is(readiness.get("raw_keys_included"), false)
            && value_bool_is(readiness.get("content_included"), false)
            && value_bool_is(readiness.get("side_signal_raw_included"), false)
            && value_bool_is(readiness.get("human_decision_text_included"), false);

    let mut blockers = Vec::new();
    push_string_blocker(
        &mut blockers,
        readiness_schema_ok,
        "readiness_packet_schema_invalid",
    );
    push_string_blocker(
        &mut blockers,
        readiness_read_only,
        "readiness_packet_not_read_only",
    );
    push_string_blocker(
        &mut blockers,
        readiness_marker_ok,
        "readiness_packet_marker_missing",
    );
    push_string_blocker(
        &mut blockers,
        readiness_stage_ok,
        "readiness_packet_stage_invalid",
    );
    push_string_blocker(
        &mut blockers,
        readiness_scope_ok,
        "readiness_packet_scope_invalid",
    );
    push_string_blocker(
        &mut blockers,
        readiness_completed,
        "readiness_packet_not_completed",
    );
    push_string_blocker(
        &mut blockers,
        readiness_control_plane_ready,
        "readiness_control_plane_not_ready",
    );
    push_string_blocker(
        &mut blockers,
        readiness_may_accept_calls,
        "readiness_does_not_accept_controlled_calls",
    );
    push_string_blocker(
        &mut blockers,
        readiness_default_influence_not_ready,
        "readiness_claims_default_influence",
    );
    if readiness_post_runtime_evidence_backed {
        push_string_blocker(
            &mut blockers,
            readiness_post_runtime_evidence_chain_ok,
            "readiness_post_runtime_evidence_summary_not_ready",
        );
    }
    if readiness_capability_ledger_backed {
        push_string_blocker(
            &mut blockers,
            readiness_capability_ledger_ok,
            "readiness_capability_ledger_not_safe",
        );
    }
    push_string_blocker(
        &mut blockers,
        boundary_ready,
        "readiness_boundary_not_ready",
    );
    push_string_blocker(
        &mut blockers,
        readiness_no_blockers,
        "readiness_boundary_has_blockers",
    );
    push_string_blocker(
        &mut blockers,
        boundary_requires_per_call,
        "readiness_missing_per_call_requirement",
    );
    push_string_blocker(
        &mut blockers,
        boundary_requires_operator_enabled,
        "readiness_missing_operator_disable_requirement",
    );
    push_string_blocker(
        &mut blockers,
        boundary_requires_fail_open,
        "readiness_missing_fail_open_requirement",
    );
    push_string_blocker(
        &mut blockers,
        boundary_requires_redacted_audit,
        "readiness_missing_redacted_audit_requirement",
    );
    push_string_blocker(
        &mut blockers,
        boundary_requires_baseline_recall,
        "readiness_missing_baseline_recall_requirement",
    );
    push_string_blocker(
        &mut blockers,
        boundary_grants_nothing,
        "readiness_packet_claims_runtime_or_default_change",
    );
    push_string_blocker(
        &mut blockers,
        readiness_input_raw_absent,
        "readiness_packet_raw_input_included",
    );
    push_string_blocker(
        &mut blockers,
        readiness_side_effects_absent,
        "readiness_packet_side_effect_claim_unexpected",
    );
    push_string_blocker(
        &mut blockers,
        requested_mode_authorized,
        "requested_mode_not_authorized",
    );
    push_string_blocker(
        &mut blockers,
        opts.per_call_opt_in,
        "per_call_opt_in_missing",
    );
    push_string_blocker(&mut blockers, !opts.operator_disabled, "operator_disabled");

    let transition_allowed = blockers.is_empty();

    json!({
        "schema": BIOCORTEX_RETRIEVAL_OPT_IN_RUNTIME_TRANSITION_GATE_SCHEMA,
        "generated_at": now_secs(),
        "read_only": true,
        "runtime_transition_gate": true,
        "implementation_stage": "readiness_gated_runtime_transition_gate",
        "authorization_scope": "explicit_opt_in_fts_runtime_influence",
        "purpose": "Consume a runtime-readiness packet and decide whether a requested explicit opt-in FTS runtime transition may proceed. This gate performs no retrieval, runs no BioCortex adapter, writes no approval, and does not alter default memory_search.",
        "status": if transition_allowed { "transition_allowed" } else { "blocked" },
        "reviewer": optional_string_json(opts.reviewer),
        "commit": optional_string_json(opts.commit),
        "forum_post_id": optional_string_json(opts.forum_post_id),
        "memory_key": optional_string_json(opts.memory_key),
        "input_contract": {
            "runtime_readiness_packet_schema": readiness.get("schema").cloned().unwrap_or(Value::Null),
            "runtime_readiness_packet_included": false,
            "requires_runtime_readiness_packet": true,
            "requires_control_plane_ready": true,
            "requires_per_call_opt_in": true,
            "requires_mode_fts": true,
            "requires_operator_disable_absent": true,
            "accepts_capability_ledger_backed_readiness_packet": true,
            "requires_capability_ledger_safe_when_provided": true,
            "capability_ledger_report_packet_included": false,
            "unknown_fields_ignored": true,
            "raw_queries_included": false,
            "raw_keys_included": false,
            "content_included": false,
            "side_signal_raw_included": false,
            "human_decision_text_included": false,
        },
        "requested_transition": {
            "mode": mode,
            "mode_authorized": requested_mode_authorized,
            "per_call_opt_in": opts.per_call_opt_in,
            "operator_disabled": opts.operator_disabled,
            "default_search_order_change_requested": false,
            "hybrid_retrieval_influence_requested": requested_hybrid_influence,
            "semantic_retrieval_influence_requested": requested_semantic_influence,
        },
        "readiness_summary": {
            "schema_ok": readiness_schema_ok,
            "read_only": readiness_read_only,
            "runtime_readiness_packet": readiness_marker_ok,
            "status_completed": readiness_completed,
            "control_plane_ready": readiness_control_plane_ready,
            "may_accept_controlled_explicit_opt_in_fts_calls": readiness_may_accept_calls,
            "live_probe_state": readiness.pointer("/readiness/live_probe_state").cloned().unwrap_or(Value::Null),
            "live_probe_has_candidates": readiness.pointer("/readiness/live_probe_has_candidates").cloned().unwrap_or(Value::Bool(false)),
            "live_order_influence_ready": readiness.pointer("/readiness/live_order_influence_ready").cloned().unwrap_or(Value::Bool(false)),
            "default_influence_ready": readiness.pointer("/readiness/default_influence_ready").cloned().unwrap_or(Value::Bool(false)),
            "post_runtime_evidence_summary_backed": readiness_post_runtime_evidence_backed,
            "post_runtime_evidence_summary_ready": readiness_post_runtime_evidence_backed
                && readiness_post_runtime_evidence_chain_ok,
            "legacy_decision_packet_without_post_runtime_evidence_summary_allowed": !readiness_post_runtime_evidence_backed,
            "post_runtime_evidence_summary_state": readiness.pointer("/decision_summary/post_runtime_evidence_summary_state").cloned().unwrap_or(Value::Null),
            "post_runtime_batch_evidence_source": readiness.pointer("/decision_summary/post_runtime_batch_evidence_source").cloned().unwrap_or(Value::Null),
            "post_runtime_readiness_gated_batch_evidence_ready": readiness_post_runtime_evidence_backed
                && value_bool_is(
                    readiness.pointer(
                        "/decision_summary/post_runtime_readiness_gated_batch_evidence_ready",
                    ),
                    true,
                ),
            "post_runtime_batch_transition_gated": !readiness_post_runtime_evidence_backed
                || value_bool_is(
                    readiness.pointer("/decision_summary/post_runtime_batch_transition_gated"),
                    true,
                ),
            "store_post_runtime_evidence_preflight_ok": readiness_store_post_runtime_preflight_ok,
            "batch_post_runtime_evidence_preflight_ok": readiness_batch_post_runtime_preflight_ok,
            "capability_ledger_backed_review_request": readiness_capability_ledger_backed,
            "capability_ledger_safe_for_transition": readiness_capability_ledger_ok,
            "legacy_readiness_packet_without_capability_ledger_allowed": !readiness_capability_ledger_backed,
            "capability_ledger_input_schema": readiness
                .pointer("/decision_summary/capability_ledger_input_schema")
                .cloned()
                .unwrap_or(Value::Null),
            "capability_ledger_input_schema_version": readiness
                .pointer("/decision_summary/capability_ledger_input_schema_version")
                .cloned()
                .unwrap_or(Value::Null),
            "capability_ledger_can_authorize_runtime_influence": false,
            "capability_ledger_report_packet_included": false,
            "boundary_ready": boundary_ready,
            "readiness_blockers": readiness_blockers,
            "raw_inputs_absent": readiness_input_raw_absent,
            "side_effects_absent": readiness_side_effects_absent,
        },
        "transition": {
            "transition_allowed": transition_allowed,
            "may_call_controlled_store_trial": transition_allowed,
            "may_run_runtime_adapter_for_explicit_opt_in_fts": transition_allowed,
            "may_connect_ordering_behavior_for_explicit_opt_in_fts": transition_allowed,
            "may_affect_only_explicitly_opted_in_fts_calls": transition_allowed,
            "requires_per_call_opt_in": true,
            "must_keep_operator_disable": BIOCORTEX_RETRIEVAL_DISABLE_ENV,
            "must_return_baseline_without_per_call_opt_in": true,
            "must_fail_open_to_baseline": true,
            "must_keep_redacted_audit_only": true,
            "must_keep_baseline_candidate_recall": true,
            "capability_ledger_can_authorize_runtime_influence": false,
            "may_change_default_memory_search_order": false,
            "default_influence_ready": false,
            "recommended_next_step": if transition_allowed {
                "run_controlled_explicit_opt_in_fts_store_trial_with_this_gate"
            } else {
                "fix_transition_gate_blockers_before_runtime_use"
            },
        },
        "boundary_check": {
            "runtime_transition_allowed": transition_allowed,
            "blockers": blockers,
            "capability_ledger_backed_readiness_packet": readiness_capability_ledger_backed,
            "capability_ledger_safe_for_transition": readiness_capability_ledger_ok,
            "legacy_readiness_packet_without_capability_ledger_allowed": !readiness_capability_ledger_backed,
            "capability_ledger_authorizes_runtime_influence": readiness_capability_ledger_backed
                && !readiness_capability_ledger_authorizes_nothing,
            "this_packet_grants_new_authorization": false,
            "this_packet_calls_memory_search": false,
            "this_packet_runs_biocortex": false,
            "this_packet_changes_return_order": false,
            "this_packet_allows_default_search_order_change": false,
        },
        "approval_state": "runtime_transition_gate_only",
        "authorization_state": if transition_allowed {
            "readiness_gated_explicit_opt_in_fts_transition_allowed"
        } else {
            "blocked"
        },
        "approval_writes_allowed": false,
        "writes_approval": false,
        "calls_memory_search": false,
        "runs_biocortex": false,
        "registers_embedding_backend": false,
        "changes_memory_search_order": false,
        "default_search_order_change_allowed": false,
        "default_calls_unchanged": true,
        "raw_queries_included": false,
        "raw_keys_included": false,
        "content_included": false,
        "side_signal_raw_included": false,
        "human_decision_text_included": false,
    })
}

pub fn biocortex_retrieval_downstream_aio_runtime_evidence_handoff(
    opts: BioCortexRetrievalDownstreamAioRuntimeEvidenceHandoffOptions,
) -> Value {
    let checkpoint = opts.checkpoint_selection;
    let review = opts.post_semantic_diverse_review;
    let controlled_trial_readiness = opts.controlled_trial_readiness;
    let controlled_trial_readiness_ref = controlled_trial_readiness.as_ref();

    let checkpoint_schema_ok = value_str_eq(
        checkpoint.get("schema"),
        BIOCORTEX_RETRIEVAL_DOWNSTREAM_AIO_CHECKPOINT_SELECTION_SCHEMA,
    );
    let checkpoint_status_ok = value_str_eq(
        checkpoint.get("status"),
        "downstream_aio_integration_checkpoint_selected",
    );
    let selected_checkpoint_ok = value_str_eq(
        checkpoint.pointer("/selected_checkpoint/id"),
        "semantic_system_bus_lswr_action_result_runtime_evidence_checkpoint",
    );
    let selected_family_ok = value_str_eq(
        checkpoint.pointer("/selected_checkpoint/family"),
        "semantic_system_bus",
    );
    let selected_surface_ok = value_str_eq(
        checkpoint.pointer("/selected_checkpoint/surface"),
        "lswr_action_result_runtime_evidence",
    );
    let first_consumer_ok = value_str_eq(
        checkpoint.pointer("/selected_checkpoint/first_consumer"),
        "agent_bridge_semantic_system_bus",
    );
    let direct_aiot_not_selected = value_bool_is(
        checkpoint.pointer("/selected_checkpoint/direct_aiot_consumption_selected"),
        false,
    );
    let checkpoint_contract_read_only = value_bool_is(
        checkpoint.pointer("/checkpoint_contract/checkpoint_must_be_read_only"),
        true,
    );
    let checkpoint_handoff_schema_ok = value_str_eq(
        checkpoint.pointer("/checkpoint_contract/first_handoff_schema"),
        BIOCORTEX_RETRIEVAL_DOWNSTREAM_AIO_RUNTIME_EVIDENCE_HANDOFF_SCHEMA,
    );
    let checkpoint_may_build_handoff = value_bool_is(
        checkpoint.pointer("/checkpoint_contract/may_build_handoff_packet"),
        true,
    );
    let checkpoint_may_compare_ssb = value_bool_is(
        checkpoint
            .pointer("/checkpoint_contract/may_compare_against_ssb_runtime_evidence_contract"),
        true,
    );
    let checkpoint_boundary_ok = value_bool_is(
        checkpoint.pointer("/checkpoint_contract/may_enable_default_retrieval"),
        false,
    ) && value_bool_is(
        checkpoint.pointer("/checkpoint_contract/may_enable_hybrid_retrieval"),
        false,
    ) && value_bool_is(
        checkpoint.pointer("/checkpoint_contract/may_enable_semantic_retrieval"),
        false,
    ) && value_bool_is(
        checkpoint.pointer("/checkpoint_contract/may_write_approval"),
        false,
    ) && value_bool_is(
        checkpoint.pointer("/checkpoint_contract/may_mutate_default_agent_bridge_db"),
        false,
    ) && value_bool_is(
        checkpoint.pointer("/checkpoint_contract/may_call_aiot_runtime"),
        false,
    ) && value_bool_is(
        checkpoint.pointer("/checkpoint_contract/may_execute_lswr_actions_from_biocortex_evidence"),
        false,
    ) && value_bool_is(
        checkpoint.pointer("/boundary/default_search_order_change_allowed"),
        false,
    ) && value_bool_is(
        checkpoint.pointer("/boundary/default_retrieval_influence_authorized"),
        false,
    ) && value_bool_is(
        checkpoint.pointer("/boundary/hybrid_retrieval_influence_authorized"),
        false,
    ) && value_bool_is(
        checkpoint.pointer("/boundary/semantic_retrieval_influence_authorized"),
        false,
    ) && value_bool_is(
        checkpoint.pointer("/boundary/direct_aiot_runtime_use_authorized"),
        false,
    );
    let checkpoint_raw_absent =
        value_bool_is(checkpoint.pointer("/boundary/raw_queries_included"), false)
            && value_bool_is(checkpoint.pointer("/boundary/raw_keys_included"), false)
            && value_bool_is(checkpoint.pointer("/boundary/content_included"), false)
            && value_bool_is(
                checkpoint.pointer("/boundary/side_signal_raw_included"),
                false,
            )
            && value_bool_is(
                checkpoint.pointer("/boundary/human_decision_text_included"),
                false,
            );
    let ssb_alignment_ok = value_bool_is(
        checkpoint.pointer("/ssb_alignment/runtime_backed_evidence"),
        true,
    ) && value_bool_is(
        checkpoint.pointer("/ssb_alignment/redacted_evidence_only"),
        true,
    ) && value_bool_is(
        checkpoint.pointer("/ssb_alignment/no_laundering_boundary_required"),
        true,
    ) && value_bool_is(
        checkpoint.pointer("/ssb_alignment/verification_boundary_required"),
        true,
    ) && value_bool_is(
        checkpoint.pointer("/ssb_alignment/recover_field_required"),
        true,
    ) && value_bool_is(
        checkpoint.pointer("/ssb_alignment/raw_available_must_not_expose_raw_payload"),
        true,
    );

    let review_schema_ok = value_str_eq(
        review.get("schema"),
        BIOCORTEX_RETRIEVAL_POST_SEMANTIC_DIVERSE_REVIEW_SCHEMA,
    );
    let review_status_ok = value_str_eq(
        review.get("status"),
        "post_semantic_diverse_review_recorded",
    );
    let review_evidence_accepted =
        value_bool_is(review.pointer("/review_result/evidence_accepted"), true);
    let review_ready_for_checkpoint = value_bool_is(
        review.pointer("/review_result/ready_for_downstream_aio_checkpoint_selection"),
        true,
    );
    let review_authorization_scope_ok = value_str_eq(
        review.pointer("/accepted_evidence_summary/authorization_scope"),
        "explicit_opt_in_fts_runtime_influence",
    );
    let review_expected_met = value_bool_is(
        review.pointer("/accepted_evidence_summary/expected_met"),
        true,
    );
    let review_all_cases_ready = value_bool_is(
        review.pointer("/accepted_evidence_summary/all_cases_evidence_ready"),
        true,
    );
    let review_status_surfaces_safe = value_bool_is(
        review.pointer("/accepted_evidence_summary/all_status_surfaces_blocked"),
        true,
    ) && value_bool_is(
        review.pointer("/accepted_evidence_summary/all_status_surfaces_side_effect_free"),
        true,
    );
    let review_default_safe =
        value_bool_is(
            review.pointer("/accepted_evidence_summary/default_memory_search_unchanged"),
            true,
        ) && value_bool_is(
            review.pointer("/accepted_evidence_summary/hybrid_retrieval_unchanged"),
            true,
        ) && value_bool_is(
            review.pointer("/accepted_evidence_summary/semantic_retrieval_unchanged"),
            true,
        ) && value_bool_is(
            review.pointer("/boundary/default_search_order_change_allowed"),
            false,
        ) && value_bool_is(
            review.pointer("/boundary/default_retrieval_influence_authorized"),
            false,
        ) && value_bool_is(
            review.pointer("/boundary/hybrid_retrieval_influence_authorized"),
            false,
        ) && value_bool_is(
            review.pointer("/boundary/semantic_retrieval_influence_authorized"),
            false,
        ) && value_bool_is(review.pointer("/boundary/production_use_authorized"), false);
    let review_raw_absent = value_bool_is(review.pointer("/boundary/raw_queries_included"), false)
        && value_bool_is(review.pointer("/boundary/raw_keys_included"), false)
        && value_bool_is(review.pointer("/boundary/content_included"), false)
        && value_bool_is(review.pointer("/boundary/side_signal_raw_included"), false);
    let review_gate_requirements_preserved = value_str_eq(
        review.pointer("/required_gates_preserved/compile_feature"),
        "biocortex-retrieval-opt-in",
    ) && value_str_eq(
        review.pointer("/required_gates_preserved/runtime_env"),
        BIOCORTEX_RETRIEVAL_OPT_IN_ENABLE_ENV,
    ) && value_str_eq(
        review.pointer("/required_gates_preserved/operator_disable"),
        BIOCORTEX_RETRIEVAL_DISABLE_ENV,
    ) && value_bool_is(
        review.pointer("/required_gates_preserved/per_call_opt_in_required"),
        true,
    ) && value_bool_is(
        review.pointer("/required_gates_preserved/post_runtime_transition_gate_required"),
        true,
    ) && value_bool_is(
        review.pointer("/required_gates_preserved/fail_open_to_baseline_required"),
        true,
    );

    let fixture_count = review
        .pointer("/accepted_evidence_summary/fixture_count")
        .and_then(Value::as_u64)
        .unwrap_or(0);
    let total_query_count = review
        .pointer("/accepted_evidence_summary/total_query_count")
        .and_then(Value::as_u64)
        .unwrap_or(0);
    let total_runs_biocortex_count = review
        .pointer("/accepted_evidence_summary/total_runs_biocortex_count")
        .and_then(Value::as_u64)
        .unwrap_or(0);
    let total_actual_order_changed_count = review
        .pointer("/accepted_evidence_summary/total_actual_order_changed_count")
        .and_then(Value::as_u64)
        .unwrap_or(0);
    let evidence_counts_ok = fixture_count >= 4
        && total_query_count >= 8
        && total_runs_biocortex_count >= 8
        && total_actual_order_changed_count >= 8;

    let controlled_trial_readiness_provided = controlled_trial_readiness_ref.is_some();
    let controlled_trial_readiness_schema_ok = controlled_trial_readiness_ref
        .map(|summary| {
            value_str_eq(
                summary.get("schema"),
                "agent_bridge.biocortex_retrieval.controlled_trial_readiness_summary.v0",
            ) && value_bool_is(summary.get("read_only"), true)
        })
        .unwrap_or(false);
    let controlled_trial_readiness_ready = controlled_trial_readiness_ref
        .map(|summary| {
            value_str_eq(summary.get("status"), "ready_for_controlled_explicit_opt_in_fts_trial")
                && value_bool_is(summary.get("ready_for_controlled_trial"), true)
                && json_string_array(summary.get("blockers")).is_empty()
        })
        .unwrap_or(false);
    let controlled_trial_capability_ledger_backed = controlled_trial_readiness_ref
        .map(|summary| {
            value_bool_is(summary.pointer("/capability_ledger/backed_evidence"), true)
        })
        .unwrap_or(false);
    let controlled_trial_capability_ledger_ready = controlled_trial_readiness_ref
        .map(|summary| {
            value_bool_is(summary.pointer("/capability_ledger/ready"), true)
                && value_bool_is(
                    summary.pointer("/capability_ledger/can_authorize_runtime_influence"),
                    false,
                )
                && value_bool_is(
                    summary.pointer("/capability_ledger/report_packet_included"),
                    false,
                )
                && value_bool_is(
                    summary.pointer("/capability_ledger/may_grant_new_authorization"),
                    false,
                )
                && value_bool_is(
                    summary.pointer("/capability_ledger/may_change_default_retrieval"),
                    false,
                )
                && value_bool_is(summary.pointer("/capability_ledger/raw_report_included"), false)
        })
        .unwrap_or(false);
    let controlled_trial_capability_ledger_authorizes_runtime_influence =
        controlled_trial_readiness_ref
            .map(|summary| {
                value_bool_is(
                    summary.pointer("/capability_ledger/can_authorize_runtime_influence"),
                    true,
                )
            })
            .unwrap_or(false);
    let controlled_trial_capability_ledger_report_packet_included =
        controlled_trial_readiness_ref
            .map(|summary| {
                value_bool_is(
                    summary.pointer("/capability_ledger/report_packet_included"),
                    true,
                )
            })
            .unwrap_or(false);
    let controlled_trial_capability_ledger_safe_for_handoff =
        !controlled_trial_capability_ledger_backed
            || (controlled_trial_capability_ledger_ready
                && !controlled_trial_capability_ledger_authorizes_runtime_influence
                && !controlled_trial_capability_ledger_report_packet_included);

    let mut blockers = Vec::new();
    push_string_blocker(
        &mut blockers,
        checkpoint_schema_ok,
        "checkpoint_schema_invalid",
    );
    push_string_blocker(
        &mut blockers,
        checkpoint_status_ok,
        "checkpoint_status_invalid",
    );
    push_string_blocker(
        &mut blockers,
        selected_checkpoint_ok,
        "selected_checkpoint_unexpected",
    );
    push_string_blocker(
        &mut blockers,
        selected_family_ok,
        "selected_checkpoint_family_unexpected",
    );
    push_string_blocker(
        &mut blockers,
        selected_surface_ok,
        "selected_checkpoint_surface_unexpected",
    );
    push_string_blocker(
        &mut blockers,
        first_consumer_ok,
        "first_consumer_unexpected",
    );
    push_string_blocker(
        &mut blockers,
        direct_aiot_not_selected,
        "direct_aiot_runtime_selected",
    );
    push_string_blocker(
        &mut blockers,
        checkpoint_contract_read_only,
        "checkpoint_not_read_only",
    );
    push_string_blocker(
        &mut blockers,
        checkpoint_handoff_schema_ok,
        "handoff_schema_not_selected",
    );
    push_string_blocker(
        &mut blockers,
        checkpoint_may_build_handoff,
        "handoff_packet_not_allowed",
    );
    push_string_blocker(
        &mut blockers,
        checkpoint_may_compare_ssb,
        "ssb_contract_compare_not_allowed",
    );
    push_string_blocker(
        &mut blockers,
        checkpoint_boundary_ok,
        "checkpoint_boundary_not_safe",
    );
    push_string_blocker(
        &mut blockers,
        checkpoint_raw_absent,
        "checkpoint_raw_input_included",
    );
    push_string_blocker(&mut blockers, ssb_alignment_ok, "ssb_alignment_not_ready");
    push_string_blocker(&mut blockers, review_schema_ok, "review_schema_invalid");
    push_string_blocker(&mut blockers, review_status_ok, "review_status_invalid");
    push_string_blocker(
        &mut blockers,
        review_evidence_accepted,
        "review_evidence_not_accepted",
    );
    push_string_blocker(
        &mut blockers,
        review_ready_for_checkpoint,
        "review_not_ready_for_checkpoint",
    );
    push_string_blocker(
        &mut blockers,
        review_authorization_scope_ok,
        "review_scope_unexpected",
    );
    push_string_blocker(
        &mut blockers,
        review_expected_met,
        "review_expected_not_met",
    );
    push_string_blocker(
        &mut blockers,
        review_all_cases_ready,
        "review_cases_not_ready",
    );
    push_string_blocker(
        &mut blockers,
        review_status_surfaces_safe,
        "review_status_surfaces_not_safe",
    );
    push_string_blocker(
        &mut blockers,
        review_default_safe,
        "review_default_boundary_not_safe",
    );
    push_string_blocker(
        &mut blockers,
        review_raw_absent,
        "review_raw_input_included",
    );
    push_string_blocker(
        &mut blockers,
        review_gate_requirements_preserved,
        "review_required_gates_not_preserved",
    );
    push_string_blocker(
        &mut blockers,
        evidence_counts_ok,
        "review_evidence_counts_insufficient",
    );
    if controlled_trial_readiness_provided {
        push_string_blocker(
            &mut blockers,
            controlled_trial_readiness_schema_ok,
            "controlled_trial_readiness_schema_invalid",
        );
        push_string_blocker(
            &mut blockers,
            controlled_trial_readiness_ready,
            "controlled_trial_readiness_not_ready",
        );
        if controlled_trial_capability_ledger_backed {
            push_string_blocker(
                &mut blockers,
                controlled_trial_capability_ledger_safe_for_handoff,
                "controlled_trial_capability_ledger_not_ready",
            );
        }
    }

    let ready = blockers.is_empty();

    json!({
        "schema": BIOCORTEX_RETRIEVAL_DOWNSTREAM_AIO_RUNTIME_EVIDENCE_HANDOFF_SCHEMA,
        "generated_at": now_secs(),
        "read_only": true,
        "downstream_aio_runtime_evidence_handoff": true,
        "implementation_stage": "downstream_aio_runtime_evidence_handoff_packet",
        "status": if ready { "ready" } else { "blocked" },
        "authorization_scope": "explicit_opt_in_fts_runtime_influence",
        "purpose": "Represent BioCortex runtime-backed retrieval evidence as a redacted downstream AIO/SSB handoff packet without enabling default retrieval, AiOT runtime consumption, or LSWR action execution.",
        "reviewer": optional_string_json(opts.reviewer),
        "commit": optional_string_json(opts.commit),
        "forum_post_id": optional_string_json(opts.forum_post_id),
        "memory_key": optional_string_json(opts.memory_key),
        "input_contract": {
            "checkpoint_selection_schema": checkpoint.get("schema").cloned().unwrap_or(Value::Null),
            "post_semantic_diverse_review_schema": review.get("schema").cloned().unwrap_or(Value::Null),
            "controlled_trial_readiness_schema": controlled_trial_readiness_ref
                .and_then(|summary| summary.get("schema"))
                .cloned()
                .unwrap_or(Value::Null),
            "checkpoint_selection_included": false,
            "post_semantic_diverse_review_included": false,
            "controlled_trial_readiness_included": false,
            "requires_checkpoint_status": "downstream_aio_integration_checkpoint_selected",
            "requires_review_status": "post_semantic_diverse_review_recorded",
            "accepts_controlled_trial_readiness_summary": true,
            "requires_controlled_trial_ready_when_provided": true,
            "accepts_capability_ledger_backed_controlled_readiness": true,
            "requires_capability_ledger_safe_when_provided": true,
            "capability_ledger_report_packet_included": false,
            "raw_queries_included": false,
            "raw_keys_included": false,
            "content_included": false,
            "side_signal_raw_included": false,
            "human_decision_text_included": false,
        },
        "checkpoint_summary": {
            "checkpoint_schema_ok": checkpoint_schema_ok,
            "checkpoint_status_ok": checkpoint_status_ok,
            "selected_checkpoint": checkpoint.pointer("/selected_checkpoint/id").cloned().unwrap_or(Value::Null),
            "selected_checkpoint_family": checkpoint.pointer("/selected_checkpoint/family").cloned().unwrap_or(Value::Null),
            "selected_surface": checkpoint.pointer("/selected_checkpoint/surface").cloned().unwrap_or(Value::Null),
            "first_consumer": checkpoint.pointer("/selected_checkpoint/first_consumer").cloned().unwrap_or(Value::Null),
            "direct_aiot_consumption_selected": !direct_aiot_not_selected,
            "checkpoint_must_be_read_only": checkpoint_contract_read_only,
            "first_handoff_schema": checkpoint.pointer("/checkpoint_contract/first_handoff_schema").cloned().unwrap_or(Value::Null),
            "may_compare_against_ssb_runtime_evidence_contract": checkpoint_may_compare_ssb,
            "boundary_safe": checkpoint_boundary_ok,
            "raw_inputs_absent": checkpoint_raw_absent,
        },
        "source_review_summary": {
            "review_schema_ok": review_schema_ok,
            "review_status": review.get("status").cloned().unwrap_or(Value::Null),
            "evidence_accepted": review_evidence_accepted,
            "ready_for_downstream_aio_checkpoint_selection": review_ready_for_checkpoint,
            "authorization_scope": review.pointer("/accepted_evidence_summary/authorization_scope").cloned().unwrap_or(Value::Null),
            "expected_met": review_expected_met,
            "all_cases_evidence_ready": review_all_cases_ready,
            "all_status_surfaces_blocked": value_bool_is(
                review.pointer("/accepted_evidence_summary/all_status_surfaces_blocked"),
                true,
            ),
            "all_status_surfaces_side_effect_free": value_bool_is(
                review.pointer("/accepted_evidence_summary/all_status_surfaces_side_effect_free"),
                true,
            ),
            "default_boundary_safe": review_default_safe,
            "raw_inputs_absent": review_raw_absent,
            "required_gates_preserved": review_gate_requirements_preserved,
        },
        "redacted_evidence_summary": {
            "fixture_count": fixture_count,
            "total_query_count": total_query_count,
            "total_baseline_empty_count": review.pointer("/accepted_evidence_summary/total_baseline_empty_count").cloned().unwrap_or(Value::Null),
            "total_runs_biocortex_count": total_runs_biocortex_count,
            "total_side_signal_ok_count": review.pointer("/accepted_evidence_summary/total_side_signal_ok_count").cloned().unwrap_or(Value::Null),
            "total_experimental_source_count": review.pointer("/accepted_evidence_summary/total_experimental_source_count").cloned().unwrap_or(Value::Null),
            "total_actual_order_changed_count": total_actual_order_changed_count,
            "expected_met": review_expected_met,
            "evidence_counts_ok": evidence_counts_ok,
            "raw_queries_included": false,
            "raw_keys_included": false,
            "content_included": false,
            "side_signal_raw_included": false,
        },
        "controlled_trial_readiness_summary": {
            "provided": controlled_trial_readiness_provided,
            "schema_ok": controlled_trial_readiness_schema_ok,
            "ready_for_controlled_trial": controlled_trial_readiness_ready,
            "status": controlled_trial_readiness_ref
                .and_then(|summary| summary.get("status"))
                .cloned()
                .unwrap_or(Value::Null),
            "blocker_count": controlled_trial_readiness_ref
                .and_then(|summary| summary.get("blockers"))
                .and_then(Value::as_array)
                .map(|items| items.len())
                .unwrap_or(0),
            "capability_ledger_backed_evidence": controlled_trial_capability_ledger_backed,
            "capability_ledger_safe_for_handoff": controlled_trial_capability_ledger_backed
                && controlled_trial_capability_ledger_safe_for_handoff,
            "legacy_controlled_readiness_without_capability_ledger_allowed": !controlled_trial_capability_ledger_backed,
            "capability_ledger_can_authorize_runtime_influence": controlled_trial_capability_ledger_authorizes_runtime_influence,
            "capability_ledger_report_packet_included": controlled_trial_capability_ledger_report_packet_included,
            "capability_ledger_raw_report_included": false,
        },
        "ssb_handoff": {
            "target_schema_family": "agent_bridge.semantic_bus.action_result.v0",
            "target_checkpoint": "semantic_system_bus_lswr_action_result_runtime_evidence_checkpoint",
            "runtime_backed_evidence": true,
            "verification_boundary_required": true,
            "no_laundering_boundary_required": true,
            "capability_ledger_backed_audit_context": controlled_trial_capability_ledger_backed,
            "capability_ledger_safe_for_handoff": controlled_trial_capability_ledger_backed
                && controlled_trial_capability_ledger_safe_for_handoff,
            "capability_ledger_can_authorize_runtime_influence": controlled_trial_capability_ledger_authorizes_runtime_influence,
            "capability_ledger_report_packet_included": controlled_trial_capability_ledger_report_packet_included,
            "may_use_capability_ledger_as_runtime_authority": false,
            "recover": if ready { "proceed_to_read_only_ssb_review" } else { "fix_handoff_blockers" },
            "raw_available": false,
            "raw_available_must_not_expose_raw_payload": true,
            "may_compare_against_ssb_runtime_evidence_contract": ready,
            "may_emit_ssb_adapter_fixture": ready,
            "may_execute_lswr_actions": false,
            "may_call_aiot_runtime": false,
            "may_mutate_default_agent_bridge_db": false,
        },
        "boundary_check": {
            "handoff_ready": ready,
            "blockers": blockers,
            "this_packet_grants_new_authorization": false,
            "this_packet_calls_memory_search": false,
            "this_packet_runs_biocortex": false,
            "this_packet_changes_return_order": false,
            "this_packet_allows_default_search_order_change": false,
            "this_packet_calls_aiot_runtime": false,
            "this_packet_executes_lswr_actions": false,
            "capability_ledger_backed_controlled_readiness": controlled_trial_capability_ledger_backed,
            "capability_ledger_safe_for_handoff": !controlled_trial_capability_ledger_backed
                || controlled_trial_capability_ledger_safe_for_handoff,
            "capability_ledger_authorizes_runtime_influence": controlled_trial_capability_ledger_authorizes_runtime_influence,
            "capability_ledger_report_packet_included": controlled_trial_capability_ledger_report_packet_included,
        },
        "approval_state": "downstream_aio_handoff_only",
        "authorization_state": if ready {
            "ready_for_read_only_ssb_runtime_evidence_review"
        } else {
            "blocked"
        },
        "next_step": if ready {
            "connect_handoff_packet_to_ssb_lswr_action_result_review_fixture"
        } else {
            "fix_downstream_aio_handoff_blockers"
        },
        "approval_writes_allowed": false,
        "writes_approval": false,
        "calls_memory_search": false,
        "runs_biocortex": false,
        "registers_embedding_backend": false,
        "changes_memory_search_order": false,
        "default_search_order_change_allowed": false,
        "default_calls_unchanged": true,
        "raw_queries_included": false,
        "raw_keys_included": false,
        "content_included": false,
        "side_signal_raw_included": false,
        "human_decision_text_included": false,
    })
}

#[derive(Default)]
struct BatchBucketStats {
    query_count: usize,
    baseline_completed_count: usize,
    baseline_empty_count: usize,
    adapter_allowed_count: usize,
    side_signal_attempted_count: usize,
    side_signal_ok_count: usize,
    experimental_source_count: usize,
    baseline_returned_count: usize,
    hash_matches_baseline_count: usize,
    contract_changes_order_count: usize,
    actual_order_changed_count: usize,
    calls_memory_search_count: usize,
    runs_biocortex_count: usize,
    default_calls_unchanged_count: usize,
    raw_flagged_count: usize,
    coverage_sum: f64,
    coverage_count: usize,
    latency_sum: f64,
    latency_count: usize,
}

impl BatchBucketStats {
    fn add_trial(&mut self, trial: &Value) {
        self.query_count += 1;
        if value_bool_is(trial.pointer("/runtime_preflight/baseline_completed"), true) {
            self.baseline_completed_count += 1;
        }
        if trial
            .pointer("/baseline_order/key_count")
            .and_then(Value::as_u64)
            == Some(0)
        {
            self.baseline_empty_count += 1;
        }
        if value_bool_is(trial.pointer("/runtime_preflight/adapter_allowed"), true) {
            self.adapter_allowed_count += 1;
        }
        if value_bool_is(trial.pointer("/side_signal/attempted"), true) {
            self.side_signal_attempted_count += 1;
        }
        if value_str_eq(trial.pointer("/side_signal/status"), "ok") {
            self.side_signal_ok_count += 1;
        }
        if value_str_eq(trial.pointer("/returned_order/source"), "experimental") {
            self.experimental_source_count += 1;
        }
        if value_bool_is(trial.pointer("/returned_order/baseline_returned"), true) {
            self.baseline_returned_count += 1;
        }
        if value_bool_is(trial.pointer("/returned_order/hash_matches_baseline"), true) {
            self.hash_matches_baseline_count += 1;
        }
        if value_bool_is(
            trial.pointer("/returned_order/contract_changes_memory_search_order"),
            true,
        ) {
            self.contract_changes_order_count += 1;
        }
        if value_bool_is(
            trial.pointer("/returned_order/actual_return_order_changed"),
            true,
        ) {
            self.actual_order_changed_count += 1;
        }
        if value_bool_is(trial.get("calls_memory_search"), true) {
            self.calls_memory_search_count += 1;
        }
        if value_bool_is(trial.get("runs_biocortex"), true) {
            self.runs_biocortex_count += 1;
        }
        if value_bool_is(trial.get("default_calls_unchanged"), true) {
            self.default_calls_unchanged_count += 1;
        }
        let raw_flagged = value_bool_is(trial.get("raw_query_included"), true)
            || value_bool_is(trial.get("raw_keys_included"), true)
            || value_bool_is(trial.get("content_included"), true)
            || value_bool_is(trial.get("side_signal_raw_included"), true);
        if raw_flagged {
            self.raw_flagged_count += 1;
        }
        if let Some(coverage) = trial
            .pointer("/side_signal/coverage")
            .and_then(Value::as_f64)
        {
            self.coverage_sum += coverage;
            self.coverage_count += 1;
        }
        if let Some(latency) = trial
            .pointer("/side_signal/latency_ms")
            .and_then(Value::as_f64)
        {
            self.latency_sum += latency;
            self.latency_count += 1;
        }
    }

    fn to_value(&self, class_label: Option<String>) -> Value {
        let avg_coverage = if self.coverage_count > 0 {
            round3(self.coverage_sum / self.coverage_count as f64)
        } else {
            0.0
        };
        let avg_latency_ms = if self.latency_count > 0 {
            round3(self.latency_sum / self.latency_count as f64)
        } else {
            0.0
        };
        let mut value = json!({
            "query_count": self.query_count,
            "baseline_completed_count": self.baseline_completed_count,
            "baseline_empty_count": self.baseline_empty_count,
            "adapter_allowed_count": self.adapter_allowed_count,
            "side_signal_attempted_count": self.side_signal_attempted_count,
            "side_signal_ok_count": self.side_signal_ok_count,
            "experimental_source_count": self.experimental_source_count,
            "baseline_returned_count": self.baseline_returned_count,
            "hash_matches_baseline_count": self.hash_matches_baseline_count,
            "contract_changes_order_count": self.contract_changes_order_count,
            "actual_order_changed_count": self.actual_order_changed_count,
            "calls_memory_search_count": self.calls_memory_search_count,
            "runs_biocortex_count": self.runs_biocortex_count,
            "default_calls_unchanged_count": self.default_calls_unchanged_count,
            "raw_flagged_count": self.raw_flagged_count,
            "avg_coverage": avg_coverage,
            "avg_latency_ms": avg_latency_ms,
        });
        if let Some(class_label) = class_label {
            value["class_label"] = json!(class_label);
        }
        value
    }
}

#[derive(Default)]
struct GatedBatchBucketStats {
    query_count: usize,
    transition_gate_allowed_count: usize,
    transition_gate_blocked_count: usize,
    gate_capability_ledger_backed_count: usize,
    gate_capability_ledger_safe_count: usize,
    gate_capability_ledger_authorizes_runtime_influence_count: usize,
    gate_capability_ledger_report_packet_included_count: usize,
    store_trial_called_count: usize,
    store_trial_adapter_allowed_count: usize,
    store_trial_preflight_blocked_count: usize,
    baseline_completed_count: usize,
    baseline_empty_count: usize,
    side_signal_attempted_count: usize,
    side_signal_ok_count: usize,
    experimental_source_count: usize,
    baseline_returned_count: usize,
    hash_matches_baseline_count: usize,
    contract_changes_order_count: usize,
    actual_order_changed_count: usize,
    calls_memory_search_count: usize,
    runs_biocortex_count: usize,
    default_calls_unchanged_count: usize,
    raw_flagged_count: usize,
    coverage_sum: f64,
    coverage_count: usize,
}

impl GatedBatchBucketStats {
    fn add_gated_trial(&mut self, trial: &Value) {
        self.query_count += 1;
        if value_bool_is(
            trial.pointer("/runtime_transition_preflight/transition_gate_allowed"),
            true,
        ) {
            self.transition_gate_allowed_count += 1;
        } else {
            self.transition_gate_blocked_count += 1;
        }
        if value_bool_is(
            trial.pointer(
                "/runtime_transition_preflight/gate_capability_ledger_backed_review_request",
            ),
            true,
        ) {
            self.gate_capability_ledger_backed_count += 1;
        }
        if value_bool_is(
            trial.pointer("/runtime_transition_preflight/gate_capability_ledger_safe_for_transition"),
            true,
        ) {
            self.gate_capability_ledger_safe_count += 1;
        }
        if value_bool_is(
            trial.pointer(
                "/runtime_transition_preflight/gate_capability_ledger_can_authorize_runtime_influence",
            ),
            true,
        ) {
            self.gate_capability_ledger_authorizes_runtime_influence_count += 1;
        }
        if value_bool_is(
            trial.pointer(
                "/runtime_transition_preflight/gate_capability_ledger_report_packet_included",
            ),
            true,
        ) {
            self.gate_capability_ledger_report_packet_included_count += 1;
        }
        if value_bool_is(trial.get("store_trial_called"), true) {
            self.store_trial_called_count += 1;
        }
        if value_bool_is(
            trial.pointer("/store_trial_summary/runtime_adapter_allowed"),
            true,
        ) {
            self.store_trial_adapter_allowed_count += 1;
        }
        let blocker_count = trial
            .pointer("/store_trial_summary/runtime_preflight_blocker_count")
            .and_then(Value::as_u64)
            .unwrap_or(0);
        if value_bool_is(trial.get("store_trial_called"), true) && blocker_count > 0 {
            self.store_trial_preflight_blocked_count += 1;
        }
        if value_bool_is(
            trial.pointer("/store_trial_summary/baseline_completed"),
            true,
        ) {
            self.baseline_completed_count += 1;
        }
        if trial
            .pointer("/store_trial_summary/baseline_key_count")
            .and_then(Value::as_u64)
            == Some(0)
        {
            self.baseline_empty_count += 1;
        }
        if value_bool_is(
            trial.pointer("/store_trial_summary/side_signal_attempted"),
            true,
        ) {
            self.side_signal_attempted_count += 1;
        }
        if value_str_eq(
            trial.pointer("/store_trial_summary/side_signal_status"),
            "ok",
        ) {
            self.side_signal_ok_count += 1;
        }
        if value_str_eq(
            trial.pointer("/store_trial_summary/returned_order_source"),
            "experimental",
        ) {
            self.experimental_source_count += 1;
        }
        if value_bool_is(
            trial.pointer("/store_trial_summary/baseline_returned"),
            true,
        ) {
            self.baseline_returned_count += 1;
        }
        if value_bool_is(
            trial.pointer("/store_trial_summary/hash_matches_baseline"),
            true,
        ) {
            self.hash_matches_baseline_count += 1;
        }
        if value_bool_is(
            trial.pointer("/store_trial_summary/contract_changes_memory_search_order"),
            true,
        ) {
            self.contract_changes_order_count += 1;
        }
        if value_bool_is(
            trial.pointer("/store_trial_summary/actual_return_order_changed"),
            true,
        ) {
            self.actual_order_changed_count += 1;
        }
        if value_bool_is(trial.get("calls_memory_search"), true) {
            self.calls_memory_search_count += 1;
        }
        if value_bool_is(trial.get("runs_biocortex"), true) {
            self.runs_biocortex_count += 1;
        }
        if value_bool_is(trial.get("default_calls_unchanged"), true) {
            self.default_calls_unchanged_count += 1;
        }
        let raw_flagged = value_bool_is(trial.get("raw_query_included"), true)
            || value_bool_is(trial.get("raw_queries_included"), true)
            || value_bool_is(trial.get("raw_keys_included"), true)
            || value_bool_is(trial.get("content_included"), true)
            || value_bool_is(trial.get("side_signal_raw_included"), true);
        if raw_flagged {
            self.raw_flagged_count += 1;
        }
        if let Some(coverage) = trial
            .pointer("/store_trial_summary/side_signal_coverage")
            .and_then(Value::as_f64)
        {
            self.coverage_sum += coverage;
            self.coverage_count += 1;
        }
    }

    fn to_value(&self, class_label: Option<String>) -> Value {
        let avg_coverage = if self.coverage_count > 0 {
            round3(self.coverage_sum / self.coverage_count as f64)
        } else {
            0.0
        };
        let mut value = json!({
            "query_count": self.query_count,
            "transition_gate_allowed_count": self.transition_gate_allowed_count,
            "transition_gate_blocked_count": self.transition_gate_blocked_count,
            "gate_capability_ledger_backed_count": self.gate_capability_ledger_backed_count,
            "gate_capability_ledger_safe_count": self.gate_capability_ledger_safe_count,
            "gate_capability_ledger_authorizes_runtime_influence_count": self.gate_capability_ledger_authorizes_runtime_influence_count,
            "gate_capability_ledger_report_packet_included_count": self.gate_capability_ledger_report_packet_included_count,
            "store_trial_called_count": self.store_trial_called_count,
            "store_trial_adapter_allowed_count": self.store_trial_adapter_allowed_count,
            "store_trial_preflight_blocked_count": self.store_trial_preflight_blocked_count,
            "baseline_completed_count": self.baseline_completed_count,
            "baseline_empty_count": self.baseline_empty_count,
            "side_signal_attempted_count": self.side_signal_attempted_count,
            "side_signal_ok_count": self.side_signal_ok_count,
            "experimental_source_count": self.experimental_source_count,
            "baseline_returned_count": self.baseline_returned_count,
            "hash_matches_baseline_count": self.hash_matches_baseline_count,
            "contract_changes_order_count": self.contract_changes_order_count,
            "actual_order_changed_count": self.actual_order_changed_count,
            "calls_memory_search_count": self.calls_memory_search_count,
            "runs_biocortex_count": self.runs_biocortex_count,
            "default_calls_unchanged_count": self.default_calls_unchanged_count,
            "raw_flagged_count": self.raw_flagged_count,
            "avg_coverage": avg_coverage,
        });
        if let Some(class_label) = class_label {
            value["class_label"] = json!(class_label);
        }
        value
    }
}

fn batch_trial_summary(
    idx: usize,
    class_label: &str,
    movement_class: &str,
    trial: &Value,
) -> Value {
    json!({
        "index": idx,
        "class_label": class_label,
        "query_hash": trial.get("query_hash").cloned().unwrap_or(Value::Null),
        "status": trial.get("status").cloned().unwrap_or(Value::Null),
        "movement_class": movement_class,
        "preflight": {
            "adapter_allowed": trial.pointer("/runtime_preflight/adapter_allowed").cloned().unwrap_or(Value::Bool(false)),
            "blocker_count": trial.pointer("/runtime_preflight/blockers").and_then(Value::as_array).map(|items| items.len()).unwrap_or(0),
            "compile_feature_enabled": trial.pointer("/runtime_preflight/compile_feature_enabled").cloned().unwrap_or(Value::Bool(false)),
            "runtime_enabled": trial.pointer("/runtime_preflight/runtime_enabled").cloned().unwrap_or(Value::Bool(false)),
            "operator_disabled": trial.pointer("/runtime_preflight/operator_disabled").cloned().unwrap_or(Value::Bool(false)),
            "decision_packet_authorized": trial.pointer("/runtime_preflight/decision_packet_authorized").cloned().unwrap_or(Value::Bool(false)),
            "decision_packet_aggregate_backed": trial.pointer("/runtime_preflight/decision_packet_aggregate_backed").cloned().unwrap_or(Value::Bool(false)),
            "decision_packet_aggregate_review_evidence_ready": trial.pointer("/runtime_preflight/decision_packet_aggregate_review_evidence_ready").cloned().unwrap_or(Value::Bool(false)),
            "legacy_decision_packet_without_aggregate_allowed": trial.pointer("/runtime_preflight/legacy_decision_packet_without_aggregate_allowed").cloned().unwrap_or(Value::Bool(true)),
            "decision_packet_aggregate_safe_for_trial": trial.pointer("/runtime_preflight/decision_packet_aggregate_safe_for_trial").cloned().unwrap_or(Value::Bool(true)),
            "decision_packet_post_runtime_evidence_summary_backed": trial.pointer("/runtime_preflight/decision_packet_post_runtime_evidence_summary_backed").cloned().unwrap_or(Value::Bool(false)),
            "decision_packet_post_runtime_evidence_summary_ready": trial.pointer("/runtime_preflight/decision_packet_post_runtime_evidence_summary_ready").cloned().unwrap_or(Value::Bool(false)),
            "legacy_decision_packet_without_post_runtime_evidence_summary_allowed": trial.pointer("/runtime_preflight/legacy_decision_packet_without_post_runtime_evidence_summary_allowed").cloned().unwrap_or(Value::Bool(true)),
            "decision_packet_post_runtime_evidence_summary_safe_for_trial": trial.pointer("/runtime_preflight/decision_packet_post_runtime_evidence_summary_safe_for_trial").cloned().unwrap_or(Value::Bool(true)),
            "decision_packet_post_runtime_evidence_summary_state": trial.pointer("/runtime_preflight/decision_packet_post_runtime_evidence_summary_state").cloned().unwrap_or(Value::Null),
        },
        "baseline": {
            "completed": trial.pointer("/baseline_order/completed").cloned().unwrap_or(Value::Bool(false)),
            "key_count": trial.pointer("/baseline_order/key_count").cloned().unwrap_or_else(|| json!(0)),
            "hash": trial.pointer("/baseline_order/hash").cloned().unwrap_or(Value::Null),
            "top_key_hash": trial.pointer("/baseline_order/top_key_hash").cloned().unwrap_or(Value::Null),
        },
        "side_signal": {
            "attempted": trial.pointer("/side_signal/attempted").cloned().unwrap_or(Value::Bool(false)),
            "status": trial.pointer("/side_signal/status").cloned().unwrap_or(Value::Null),
            "matched_candidate_count": trial.pointer("/side_signal/matched_candidate_count").cloned().unwrap_or_else(|| json!(0)),
            "coverage": trial.pointer("/side_signal/coverage").cloned().unwrap_or_else(|| json!(0.0)),
            "latency_ms": trial.pointer("/side_signal/latency_ms").cloned().unwrap_or_else(|| json!(0.0)),
        },
        "returned_order": {
            "source": trial.pointer("/returned_order/source").cloned().unwrap_or_else(|| json!("baseline")),
            "baseline_returned": trial.pointer("/returned_order/baseline_returned").cloned().unwrap_or(Value::Bool(true)),
            "contract_changes_memory_search_order": trial.pointer("/returned_order/contract_changes_memory_search_order").cloned().unwrap_or(Value::Bool(false)),
            "actual_return_order_changed": trial.pointer("/returned_order/actual_return_order_changed").cloned().unwrap_or(Value::Bool(false)),
            "hash_matches_baseline": trial.pointer("/returned_order/hash_matches_baseline").cloned().unwrap_or(Value::Bool(true)),
            "hash": trial.pointer("/returned_order/hash").cloned().unwrap_or(Value::Null),
            "top_key_hash": trial.pointer("/returned_order/top_key_hash").cloned().unwrap_or(Value::Null),
            "fallback_reason": trial.pointer("/returned_order/fallback_reason").cloned().unwrap_or(Value::Null),
        },
        "calls_memory_search": trial.get("calls_memory_search").cloned().unwrap_or(Value::Bool(false)),
        "runs_biocortex": trial.get("runs_biocortex").cloned().unwrap_or(Value::Bool(false)),
        "changes_memory_search_order": trial.get("changes_memory_search_order").cloned().unwrap_or(Value::Bool(false)),
        "default_calls_unchanged": trial.get("default_calls_unchanged").cloned().unwrap_or(Value::Bool(true)),
        "raw_query_included": false,
        "raw_keys_included": false,
        "content_included": false,
        "side_signal_raw_included": false,
    })
}

fn gated_batch_trial_summary(
    idx: usize,
    class_label: &str,
    movement_class: &str,
    trial: &Value,
) -> Value {
    json!({
        "index": idx,
        "class_label": class_label,
        "query_hash": trial.get("query_hash").cloned().unwrap_or(Value::Null),
        "status": trial.get("status").cloned().unwrap_or(Value::Null),
        "movement_class": movement_class,
        "transition_preflight": {
            "transition_gate_allowed": trial.pointer("/runtime_transition_preflight/transition_gate_allowed").cloned().unwrap_or(Value::Bool(false)),
            "blocker_count": trial.pointer("/runtime_transition_preflight/blockers").and_then(Value::as_array).map(|items| items.len()).unwrap_or(0),
            "gate_schema_ok": trial.pointer("/runtime_transition_preflight/gate_schema_ok").cloned().unwrap_or(Value::Bool(false)),
            "gate_status_allowed": trial.pointer("/runtime_transition_preflight/gate_status_allowed").cloned().unwrap_or(Value::Bool(false)),
            "gate_boundary_allowed": trial.pointer("/runtime_transition_preflight/gate_boundary_allowed").cloned().unwrap_or(Value::Bool(false)),
            "gate_transition_allowed": trial.pointer("/runtime_transition_preflight/gate_transition_allowed").cloned().unwrap_or(Value::Bool(false)),
            "gate_post_runtime_evidence_summary_backed": trial.pointer("/runtime_transition_preflight/gate_post_runtime_evidence_summary_backed").cloned().unwrap_or(Value::Bool(false)),
            "gate_post_runtime_evidence_summary_ready": trial.pointer("/runtime_transition_preflight/gate_post_runtime_evidence_summary_ready").cloned().unwrap_or(Value::Bool(false)),
            "gate_legacy_decision_packet_without_post_runtime_evidence_summary_allowed": trial.pointer("/runtime_transition_preflight/gate_legacy_decision_packet_without_post_runtime_evidence_summary_allowed").cloned().unwrap_or(Value::Bool(true)),
            "gate_post_runtime_evidence_summary_state": trial.pointer("/runtime_transition_preflight/gate_post_runtime_evidence_summary_state").cloned().unwrap_or(Value::Null),
            "gate_post_runtime_batch_evidence_source": trial.pointer("/runtime_transition_preflight/gate_post_runtime_batch_evidence_source").cloned().unwrap_or(Value::Null),
            "gate_post_runtime_readiness_gated_batch_evidence_ready": trial.pointer("/runtime_transition_preflight/gate_post_runtime_readiness_gated_batch_evidence_ready").cloned().unwrap_or(Value::Bool(false)),
            "gate_post_runtime_batch_transition_gated": trial.pointer("/runtime_transition_preflight/gate_post_runtime_batch_transition_gated").cloned().unwrap_or(Value::Bool(true)),
            "gate_store_post_runtime_evidence_preflight_ok": trial.pointer("/runtime_transition_preflight/gate_store_post_runtime_evidence_preflight_ok").cloned().unwrap_or(Value::Bool(true)),
            "gate_batch_post_runtime_evidence_preflight_ok": trial.pointer("/runtime_transition_preflight/gate_batch_post_runtime_evidence_preflight_ok").cloned().unwrap_or(Value::Bool(true)),
            "gate_capability_ledger_backed_review_request": trial.pointer("/runtime_transition_preflight/gate_capability_ledger_backed_review_request").cloned().unwrap_or(Value::Bool(false)),
            "gate_capability_ledger_safe_for_transition": trial.pointer("/runtime_transition_preflight/gate_capability_ledger_safe_for_transition").cloned().unwrap_or(Value::Bool(false)),
            "gate_legacy_readiness_packet_without_capability_ledger_allowed": trial.pointer("/runtime_transition_preflight/gate_legacy_readiness_packet_without_capability_ledger_allowed").cloned().unwrap_or(Value::Bool(true)),
            "gate_capability_ledger_input_schema": trial.pointer("/runtime_transition_preflight/gate_capability_ledger_input_schema").cloned().unwrap_or(Value::Null),
            "gate_capability_ledger_input_schema_version": trial.pointer("/runtime_transition_preflight/gate_capability_ledger_input_schema_version").cloned().unwrap_or(Value::Null),
            "gate_capability_ledger_can_authorize_runtime_influence": trial.pointer("/runtime_transition_preflight/gate_capability_ledger_can_authorize_runtime_influence").cloned().unwrap_or(Value::Bool(false)),
            "gate_capability_ledger_report_packet_included": trial.pointer("/runtime_transition_preflight/gate_capability_ledger_report_packet_included").cloned().unwrap_or(Value::Bool(false)),
            "gate_capability_ledger_preflight_ok": trial.pointer("/runtime_transition_preflight/gate_capability_ledger_preflight_ok").cloned().unwrap_or(Value::Bool(true)),
            "operator_disabled_now": trial.pointer("/runtime_transition_preflight/operator_disabled_now").cloned().unwrap_or(Value::Bool(false)),
            "query_present": trial.pointer("/runtime_transition_preflight/query_present").cloned().unwrap_or(Value::Bool(false)),
        },
        "store_trial": {
            "called": trial.get("store_trial_called").cloned().unwrap_or(Value::Bool(false)),
            "status": trial.pointer("/store_trial_summary/status").cloned().unwrap_or(Value::Null),
            "runtime_adapter_allowed": trial.pointer("/store_trial_summary/runtime_adapter_allowed").cloned().unwrap_or(Value::Bool(false)),
            "runtime_preflight_blocker_count": trial.pointer("/store_trial_summary/runtime_preflight_blocker_count").cloned().unwrap_or_else(|| json!(0)),
            "decision_packet_post_runtime_evidence_summary_backed": trial.pointer("/store_trial_summary/decision_packet_post_runtime_evidence_summary_backed").cloned().unwrap_or(Value::Bool(false)),
            "decision_packet_post_runtime_evidence_summary_ready": trial.pointer("/store_trial_summary/decision_packet_post_runtime_evidence_summary_ready").cloned().unwrap_or(Value::Bool(false)),
            "legacy_decision_packet_without_post_runtime_evidence_summary_allowed": trial.pointer("/store_trial_summary/legacy_decision_packet_without_post_runtime_evidence_summary_allowed").cloned().unwrap_or(Value::Bool(true)),
            "decision_packet_post_runtime_evidence_summary_safe_for_trial": trial.pointer("/store_trial_summary/decision_packet_post_runtime_evidence_summary_safe_for_trial").cloned().unwrap_or(Value::Bool(true)),
            "decision_packet_post_runtime_evidence_summary_state": trial.pointer("/store_trial_summary/decision_packet_post_runtime_evidence_summary_state").cloned().unwrap_or(Value::Null),
            "baseline_completed": trial.pointer("/store_trial_summary/baseline_completed").cloned().unwrap_or(Value::Bool(false)),
            "baseline_key_count": trial.pointer("/store_trial_summary/baseline_key_count").cloned().unwrap_or_else(|| json!(0)),
            "side_signal_attempted": trial.pointer("/store_trial_summary/side_signal_attempted").cloned().unwrap_or(Value::Bool(false)),
            "side_signal_status": trial.pointer("/store_trial_summary/side_signal_status").cloned().unwrap_or(Value::Null),
            "side_signal_coverage": trial.pointer("/store_trial_summary/side_signal_coverage").cloned().unwrap_or(Value::Null),
            "returned_order_source": trial.pointer("/store_trial_summary/returned_order_source").cloned().unwrap_or(Value::Null),
            "baseline_returned": trial.pointer("/store_trial_summary/baseline_returned").cloned().unwrap_or(Value::Bool(true)),
            "contract_changes_memory_search_order": trial.pointer("/store_trial_summary/contract_changes_memory_search_order").cloned().unwrap_or(Value::Bool(false)),
            "actual_return_order_changed": trial.pointer("/store_trial_summary/actual_return_order_changed").cloned().unwrap_or(Value::Bool(false)),
            "hash_matches_baseline": trial.pointer("/store_trial_summary/hash_matches_baseline").cloned().unwrap_or(Value::Bool(true)),
            "fallback_reason": trial.pointer("/store_trial_summary/fallback_reason").cloned().unwrap_or(Value::Null),
        },
        "calls_memory_search": trial.get("calls_memory_search").cloned().unwrap_or(Value::Bool(false)),
        "runs_biocortex": trial.get("runs_biocortex").cloned().unwrap_or(Value::Bool(false)),
        "changes_memory_search_order": trial.get("changes_memory_search_order").cloned().unwrap_or(Value::Bool(false)),
        "actual_return_order_changed": trial.get("actual_return_order_changed").cloned().unwrap_or(Value::Bool(false)),
        "default_calls_unchanged": trial.get("default_calls_unchanged").cloned().unwrap_or(Value::Bool(true)),
        "raw_query_included": false,
        "raw_queries_included": false,
        "raw_keys_included": false,
        "content_included": false,
        "side_signal_raw_included": false,
    })
}

fn batch_movement_class(trial: &Value) -> &'static str {
    if !value_bool_is(trial.pointer("/runtime_preflight/baseline_completed"), true) {
        "baseline_unavailable"
    } else if !value_bool_is(trial.pointer("/runtime_preflight/adapter_allowed"), true) {
        "preflight_blocked"
    } else if !value_str_eq(trial.pointer("/side_signal/status"), "ok") {
        "side_signal_unavailable"
    } else if value_bool_is(
        trial.pointer("/returned_order/actual_return_order_changed"),
        true,
    ) {
        "experimental_moved_order"
    } else if value_str_eq(trial.pointer("/returned_order/source"), "experimental") {
        "experimental_aligned_with_baseline"
    } else if value_bool_is(trial.pointer("/returned_order/baseline_returned"), true) {
        "baseline_returned"
    } else {
        "unknown"
    }
}

fn gated_batch_movement_class(trial: &Value) -> &'static str {
    if !value_bool_is(
        trial.pointer("/runtime_transition_preflight/transition_gate_allowed"),
        true,
    ) {
        "transition_gate_blocked"
    } else if !value_bool_is(trial.get("store_trial_called"), true) {
        "store_trial_not_called"
    } else if !value_bool_is(
        trial.pointer("/store_trial_summary/runtime_adapter_allowed"),
        true,
    ) {
        "store_trial_preflight_blocked"
    } else if !value_str_eq(
        trial.pointer("/store_trial_summary/side_signal_status"),
        "ok",
    ) {
        "side_signal_unavailable"
    } else if value_bool_is(
        trial.pointer("/store_trial_summary/actual_return_order_changed"),
        true,
    ) {
        "experimental_moved_order"
    } else if value_str_eq(
        trial.pointer("/store_trial_summary/returned_order_source"),
        "experimental",
    ) {
        "experimental_aligned_with_baseline"
    } else if value_bool_is(
        trial.pointer("/store_trial_summary/baseline_returned"),
        true,
    ) {
        "baseline_returned"
    } else {
        "unknown"
    }
}

fn safe_batch_class_label(label: Option<&str>) -> String {
    let normalized = label.map(normalize_token).unwrap_or_default();
    let safe = normalized
        .chars()
        .filter(|c| c.is_ascii_alphanumeric() || *c == '_' || *c == '-')
        .take(64)
        .collect::<String>();
    if safe.is_empty() {
        "unlabeled".to_string()
    } else {
        safe
    }
}

fn advisory_order_summary(
    mode: &str,
    baseline: &[RetrievalBaselineScore],
    side_by_key: &BTreeMap<String, f32>,
    evidence_by_key: &BTreeMap<String, String>,
    alpha: &RetrievalAlphaConfig,
    expected_key: Option<&str>,
    available: bool,
) -> Value {
    let mut advisory_rows = baseline
        .iter()
        .map(|row| {
            let side_score = side_by_key.get(&row.key).copied();
            let advisory_score = row.score + alpha.alpha * side_score.unwrap_or(0.0);
            (row.key.clone(), advisory_score)
        })
        .collect::<Vec<_>>();
    advisory_rows.sort_by(|a, b| b.1.partial_cmp(&a.1).unwrap_or(std::cmp::Ordering::Equal));
    let advisory_order_keys = advisory_rows
        .iter()
        .map(|(key, _)| key.clone())
        .collect::<Vec<_>>();
    let advisory_rank_by_key = advisory_rows
        .iter()
        .enumerate()
        .map(|(idx, (key, _))| (key.clone(), idx + 1))
        .collect::<BTreeMap<_, _>>();
    let expected = expected_key
        .map(|key| {
            let baseline_rank = baseline
                .iter()
                .find(|row| row.key == key)
                .map(|row| row.rank);
            let advisory_rank = advisory_rank_by_key.get(key).copied();
            json!({
                "key_hash": candidate_key_hash(key),
                "baseline_rank": baseline_rank,
                "advisory_rank": advisory_rank,
                "regressed": match (baseline_rank, advisory_rank) {
                    (Some(baseline_rank), Some(advisory_rank)) => advisory_rank > baseline_rank,
                    _ => false,
                },
            })
        })
        .unwrap_or(Value::Null);
    let evidence_count = evidence_by_key.len();

    json!({
        "available": available,
        "used_for_return_order": false,
        "alpha_policy": alpha.policy,
        "blend_alpha": alpha.alpha,
        "explicit_alpha": alpha.explicit_alpha,
        "order_hash": if available {
            Value::String(sha256_json(&json!({
                "mode": mode,
                "advisory_keys": advisory_order_keys,
            })))
        } else {
            Value::Null
        },
        "top_key_hash": if available {
            advisory_rows
                .first()
                .map(|(key, _)| candidate_key_hash(key))
                .map(Value::String)
                .unwrap_or(Value::Null)
        } else {
            Value::Null
        },
        "redacted_rank_rows": redacted_advisory_rank_rows(&advisory_rows, available),
        "redacted_rank_rows_included": available && !advisory_rows.is_empty(),
        "matched_side_signal_count": side_by_key.len(),
        "evidence_count": evidence_count,
        "expected": expected,
        "raw_keys_included": false,
        "raw_order_keys_included": false,
        "content_included": false,
        "side_signal_raw_included": false,
    })
}

fn safe_side_signal_error_status(error: &Value) -> String {
    error
        .get("status")
        .and_then(Value::as_str)
        .map(str::to_string)
        .unwrap_or_else(|| "side_signal_unavailable".to_string())
}

fn retrieval_fail_open_report(
    status: &str,
    query: String,
    candidates: Vec<BioCortexRetrievalCandidate>,
    expected_key: Option<String>,
    baseline: Vec<RetrievalBaselineScore>,
    alpha: RetrievalAlphaConfig,
    gates: Value,
    latency_ms: f64,
    side_error: Value,
    include_raw: bool,
) -> Value {
    let report = retrieval_rank_report(
        status,
        query,
        candidates,
        expected_key,
        baseline,
        &BTreeMap::new(),
        &BTreeMap::new(),
        alpha,
        gates,
        latency_ms,
        Some(side_error.clone()),
        include_raw.then_some(json!({"side_signal_error": side_error})),
    );
    report
}

#[allow(clippy::too_many_arguments)]
fn retrieval_rank_report(
    status: &str,
    query: String,
    candidates: Vec<BioCortexRetrievalCandidate>,
    expected_key: Option<String>,
    baseline: Vec<RetrievalBaselineScore>,
    side_by_key: &BTreeMap<String, f32>,
    evidence_by_key: &BTreeMap<String, String>,
    alpha: RetrievalAlphaConfig,
    gates: Value,
    latency_ms: f64,
    side_signal: Option<Value>,
    raw: Option<Value>,
) -> Value {
    let mut advisory_rows = baseline
        .iter()
        .map(|row| {
            let side_score = side_by_key.get(&row.key).copied();
            let advisory_score = row.score + alpha.alpha * side_score.unwrap_or(0.0);
            (row.key.clone(), advisory_score)
        })
        .collect::<Vec<_>>();
    advisory_rows.sort_by(|a, b| b.1.partial_cmp(&a.1).unwrap_or(std::cmp::Ordering::Equal));
    let advisory_rank_by_key = advisory_rows
        .iter()
        .enumerate()
        .map(|(idx, (key, score))| (key.clone(), (idx + 1, *score)))
        .collect::<BTreeMap<_, _>>();
    let baseline_top = baseline
        .first()
        .map(|row| row.key.clone())
        .unwrap_or_else(|| "<none>".to_string());
    let advisory_top = advisory_rows
        .first()
        .map(|row| row.0.clone())
        .unwrap_or_else(|| "<none>".to_string());
    let coverage = side_by_key.len() as f64 / candidates.len().max(1) as f64;
    let expected = expected_key
        .as_ref()
        .and_then(|key| baseline.iter().find(|row| &row.key == key))
        .map(|row| {
            let advisory_rank = advisory_rank_by_key
                .get(&row.key)
                .map(|(rank, _)| *rank)
                .unwrap_or(row.rank);
            json!({
                "key": row.key,
                "baseline_rank": row.rank,
                "advisory_rank": advisory_rank,
                "regressed": advisory_rank > row.rank,
            })
        })
        .unwrap_or(Value::Null);
    let expected_regressions = expected
        .get("regressed")
        .and_then(Value::as_bool)
        .map(|regressed| usize::from(regressed))
        .unwrap_or(0);

    let hits = baseline
        .iter()
        .map(|row| {
            let (advisory_rank, advisory_score) = advisory_rank_by_key
                .get(&row.key)
                .copied()
                .unwrap_or((row.rank, row.score));
            json!({
                "key": row.key,
                "content": row.content,
                "baseline_rank": row.rank,
                "baseline_score": row.score,
                "advisory_rank": advisory_rank,
                "advisory_score": advisory_score,
                "side_signal_score": side_by_key.get(&row.key).copied(),
                "side_signal_evidence": evidence_by_key.get(&row.key),
            })
        })
        .collect::<Vec<_>>();
    let query_hash = sha256_json(&json!({"query": query}));

    let mut payload = json!({
        "schema": BIOCORTEX_RETRIEVAL_SHADOW_SCHEMA,
        "generated_at": now_secs(),
        "read_only": true,
        "runtime_adapter_approved": false,
        "status": status,
        "query_hash": query_hash,
        "candidate_count": candidates.len(),
        "alpha_policy": alpha.policy,
        "blend_alpha": alpha.alpha,
        "explicit_alpha": alpha.explicit_alpha,
        "side_signal_coverage": round3(coverage),
        "baseline_top_key": baseline_top,
        "advisory_top_key": advisory_top,
        "expected": expected,
        "expected_regressions": expected_regressions,
        "latency_ms": round3(latency_ms),
        "default_search_order_changed": false,
        "hits": hits,
        "side_signal": side_signal.unwrap_or(Value::Null),
        "boundary": retrieval_boundary_payload(),
        "gates": gates,
    });
    if let Some(raw) = raw {
        payload["raw"] = raw;
    }
    payload
}

fn retrieval_baseline_scores(
    query: &str,
    candidates: &[BioCortexRetrievalCandidate],
) -> Vec<RetrievalBaselineScore> {
    let backend = default_backend();
    let query_vec = backend.embed(query);
    let mut rows = candidates
        .iter()
        .map(|candidate| RetrievalBaselineScore {
            key: candidate.key.clone(),
            content: candidate.content.clone(),
            score: cosine_similarity(&query_vec, &backend.embed(&candidate.content)),
            rank: 0,
        })
        .collect::<Vec<_>>();
    rows.sort_by(|a, b| {
        b.score
            .partial_cmp(&a.score)
            .unwrap_or(std::cmp::Ordering::Equal)
    });
    for (idx, row) in rows.iter_mut().enumerate() {
        row.rank = idx + 1;
    }
    rows
}

/// Run the local BioCortex retrieval side-signal adapter for diagnostics.
///
/// This helper exists so fixture examples can inspect score saturation and
/// ranking behavior directly without widening the MCP API surface.
pub async fn run_retrieval_side_signal(
    query: &str,
    candidates: &[BioCortexRetrievalCandidate],
    expected_key: Option<&str>,
    explicit_checkout: Option<&Path>,
    timeout_ms: u64,
) -> Result<RetrievalSideSignalRun, Value> {
    let checkout_candidates = checkout_candidates(explicit_checkout);
    let checkout = resolve_checkout(&checkout_candidates).ok_or_else(|| {
        json!({
            "status": "checkout_unavailable",
            "reason": "no local biocortex-rs checkout found",
            "checkout_env": BIOCORTEX_CHECKOUT_ENV,
            "candidates": checkout_candidates
                .iter()
                .map(|path| display_path(path.as_path()))
                .collect::<Vec<_>>(),
        })
    })?;
    let manifest = checkout.join("Cargo.toml");
    let corpus_path = std::env::temp_dir().join(format!(
        "ab-biocortex-retrieval-shadow-{}-{}.jsonl",
        std::process::id(),
        now_nanos()
    ));
    let corpus = json!({
        "id": "q_runtime_shadow",
        "query": query,
        "expected_key": expected_key
            .map(str::to_string)
            .or_else(|| candidates.first().map(|candidate| candidate.key.clone()))
            .unwrap_or_else(|| "candidate".to_string()),
        "candidates": candidates,
    });
    let corpus_line = serde_json::to_string(&corpus).map_err(|err| {
        json!({
            "status": "corpus_encode_error",
            "error": err.to_string(),
        })
    })?;
    std::fs::write(&corpus_path, format!("{corpus_line}\n")).map_err(|err| {
        json!({
            "status": "corpus_write_error",
            "error": err.to_string(),
            "corpus_path": display_path(&corpus_path),
        })
    })?;

    let timeout_ms = timeout_ms.clamp(1_000, 600_000);
    let mut cmd = TokioCommand::new("cargo");
    cmd.arg("run")
        .arg("--offline")
        .arg("--quiet")
        .arg("--manifest-path")
        .arg(&manifest)
        .arg("--example")
        .arg("ab_retrieval_side_signal_adapter")
        .arg("--")
        .arg(&corpus_path)
        .kill_on_drop(true);
    let output_result = tokio::time::timeout(Duration::from_millis(timeout_ms), cmd.output()).await;
    let _ = std::fs::remove_file(&corpus_path);

    let output = match output_result {
        Ok(Ok(output)) => output,
        Ok(Err(err)) => {
            return Err(json!({
                "status": "spawn_error",
                "error": err.to_string(),
                "checkout_path": display_path(&checkout),
                "manifest_path": display_path(&manifest),
            }));
        }
        Err(_) => {
            return Err(json!({
                "status": "timeout",
                "timeout_ms": timeout_ms,
                "checkout_path": display_path(&checkout),
                "manifest_path": display_path(&manifest),
            }));
        }
    };

    let stdout = String::from_utf8_lossy(&output.stdout).to_string();
    let stderr = String::from_utf8_lossy(&output.stderr).to_string();
    if !output.status.success() {
        return Err(json!({
            "status": "command_failed",
            "exit_code": output.status.code(),
            "checkout_path": display_path(&checkout),
            "manifest_path": display_path(&manifest),
            "stderr_preview": stderr.chars().take(1200).collect::<String>(),
        }));
    }

    let mut rows = Vec::new();
    for line in stdout
        .lines()
        .map(str::trim)
        .filter(|line| !line.is_empty())
    {
        let row: RetrievalSideSignalRow = serde_json::from_str(line).map_err(|err| {
            json!({
                "status": "parse_error",
                "error": err.to_string(),
                "line": line,
            })
        })?;
        if !(-1.0..=1.0).contains(&row.score) {
            return Err(json!({
                "status": "score_out_of_bounds",
                "candidate_key": row.candidate_key,
                "score": row.score,
            }));
        }
        rows.push(row);
    }

    let payload = json!({
        "status": "ok",
        "checkout_path": display_path(&checkout),
        "manifest_path": display_path(&manifest),
        "example": "ab_retrieval_side_signal_adapter",
        "timeout_ms": timeout_ms,
        "exit_code": output.status.code(),
        "row_count": rows.len(),
        "writes_temp_corpus": true,
        "mutates_ab_memory": false,
        "changes_retrieval_vector": false,
    });
    let raw = json!({
        "stdout": stdout,
        "stderr": stderr,
    });
    Ok(RetrievalSideSignalRun { rows, payload, raw })
}

fn retrieval_alpha_config() -> RetrievalAlphaConfig {
    if let Some(raw) = std::env::var("AB_BIOCORTEX_RETRIEVAL_BLEND_ALPHA")
        .ok()
        .or_else(|| std::env::var("BIOCORTEX_RETRIEVAL_BLEND_ALPHA").ok())
    {
        if let Ok(alpha) = raw.parse::<f32>() {
            return RetrievalAlphaConfig {
                policy: "manual".to_string(),
                alpha: alpha.clamp(0.0, 1.0),
                explicit_alpha: true,
            };
        }
    }

    let policy = std::env::var("AB_BIOCORTEX_RETRIEVAL_ALPHA_POLICY")
        .ok()
        .or_else(|| std::env::var("BIOCORTEX_RETRIEVAL_ALPHA_POLICY").ok())
        .unwrap_or_else(|| "candidate-strong".to_string());
    let normalized = normalize_token(&policy).replace('_', "-");
    let alpha = match normalized.as_str() {
        "conservative" => CONSERVATIVE_RETRIEVAL_ALPHA,
        "" | "candidate-strong" => CANDIDATE_STRONG_RETRIEVAL_ALPHA,
        _ => CANDIDATE_STRONG_RETRIEVAL_ALPHA,
    };
    RetrievalAlphaConfig {
        policy: if normalized.is_empty() {
            "candidate-strong".to_string()
        } else {
            normalized
        },
        alpha,
        explicit_alpha: false,
    }
}

fn retrieval_gate_state() -> Value {
    json!({
        "compile_feature": "biocortex-retrieval-shadow",
        "compile_feature_enabled": cfg!(feature = "biocortex-retrieval-shadow"),
        "runtime_enable_env": BIOCORTEX_RETRIEVAL_SHADOW_ENABLE_ENV,
        "runtime_enabled": env_truthy(BIOCORTEX_RETRIEVAL_SHADOW_ENABLE_ENV),
        "operator_disable_env": BIOCORTEX_RETRIEVAL_DISABLE_ENV,
        "operator_disabled": env_truthy(BIOCORTEX_RETRIEVAL_DISABLE_ENV),
    })
}

fn retrieval_boundary_payload() -> Value {
    json!({
        "mode": "retrieval_shadow_advisory_only",
        "read_only": true,
        "links_biocortex_into_ab_runtime": false,
        "registers_embedding_backend": false,
        "calls_set_default_backend": false,
        "mutates_ab_memory": false,
        "writes_embeddings": false,
        "writes_coactivation": false,
        "writes_graph_edges": false,
        "changes_memory_search_order": false,
        "default_search_order_changed": false,
        "runtime_adapter_approved": false,
    })
}

fn retrieval_runtime_trial_boundary_payload(runs_external_side_signal: bool) -> Value {
    json!({
        "mode": "retrieval_opt_in_runtime_trial_baseline_preserving",
        "read_only": true,
        "runs_external_side_signal": runs_external_side_signal,
        "writes_temp_corpus": runs_external_side_signal,
        "links_biocortex_into_ab_runtime": false,
        "registers_embedding_backend": false,
        "calls_set_default_backend": false,
        "calls_memory_search": false,
        "mutates_ab_memory": false,
        "writes_embeddings": false,
        "writes_coactivation": false,
        "writes_graph_edges": false,
        "changes_memory_search_order": false,
        "default_search_order_changed": false,
        "runtime_adapter_approved": false,
    })
}

fn retrieval_runtime_trial_review_boundary_payload() -> Value {
    json!({
        "mode": "retrieval_opt_in_runtime_trial_review_packet",
        "read_only": true,
        "runs_external_side_signal": false,
        "writes_temp_corpus": false,
        "links_biocortex_into_ab_runtime": false,
        "registers_embedding_backend": false,
        "calls_set_default_backend": false,
        "calls_memory_search": false,
        "mutates_ab_memory": false,
        "writes_embeddings": false,
        "writes_coactivation": false,
        "writes_graph_edges": false,
        "changes_memory_search_order": false,
        "default_search_order_changed": false,
        "runtime_adapter_approved": false,
    })
}

fn retrieval_order_diff_boundary_payload() -> Value {
    json!({
        "mode": "retrieval_opt_in_order_diff_packet",
        "read_only": true,
        "runs_external_side_signal": false,
        "writes_temp_corpus": false,
        "links_biocortex_into_ab_runtime": false,
        "registers_embedding_backend": false,
        "calls_set_default_backend": false,
        "calls_memory_search": false,
        "mutates_ab_memory": false,
        "writes_embeddings": false,
        "writes_coactivation": false,
        "writes_graph_edges": false,
        "changes_memory_search_order": false,
        "default_search_order_changed": false,
        "runtime_adapter_approved": false,
    })
}

fn retrieval_redacted_order_artifact_boundary_payload() -> Value {
    json!({
        "mode": "retrieval_opt_in_redacted_order_artifact",
        "read_only": true,
        "runs_external_side_signal": false,
        "writes_temp_corpus": false,
        "links_biocortex_into_ab_runtime": false,
        "registers_embedding_backend": false,
        "calls_set_default_backend": false,
        "calls_memory_search": false,
        "mutates_ab_memory": false,
        "writes_embeddings": false,
        "writes_coactivation": false,
        "writes_graph_edges": false,
        "changes_memory_search_order": false,
        "default_search_order_changed": false,
        "actual_return_order_changed": false,
        "raw_query_included": false,
        "raw_keys_included": false,
        "raw_order_keys_included": false,
        "content_included": false,
        "side_signal_raw_included": false,
        "redacted_key_hashes_included": true,
        "runtime_adapter_approved": false,
    })
}

fn required_or_value(value: Option<String>) -> Value {
    value
        .map(|s| s.trim().to_string())
        .filter(|s| !s.is_empty())
        .map(Value::String)
        .unwrap_or_else(|| json!("<required>"))
}

fn optional_string_json(value: Option<String>) -> Value {
    value
        .map(|s| s.trim().to_string())
        .filter(|s| !s.is_empty())
        .map(Value::String)
        .unwrap_or(Value::Null)
}

fn json_string_array(value: Option<&Value>) -> Vec<String> {
    value
        .and_then(Value::as_array)
        .map(|items| {
            items
                .iter()
                .filter_map(Value::as_str)
                .map(str::to_string)
                .collect::<Vec<_>>()
        })
        .unwrap_or_default()
}

fn value_bool_is(value: Option<&Value>, expected: bool) -> bool {
    value.and_then(Value::as_bool) == Some(expected)
}

fn value_str_eq(value: Option<&Value>, expected: &str) -> bool {
    value.and_then(Value::as_str) == Some(expected)
}

fn array_contains_str(value: Option<&Value>, expected: &str) -> bool {
    value
        .and_then(Value::as_array)
        .map(|items| items.iter().any(|item| item.as_str() == Some(expected)))
        .unwrap_or(false)
}

fn push_violation(violations: &mut Vec<&'static str>, ok: bool, violation: &'static str) {
    if !ok {
        violations.push(violation);
    }
}

fn push_string_blocker(blockers: &mut Vec<String>, ok: bool, blocker: &str) {
    if !ok {
        blockers.push(blocker.to_string());
    }
}

fn missing_required_paths(value: &Value) -> Vec<String> {
    let mut paths = Vec::new();
    collect_missing_required_paths(value, "$", &mut paths);
    paths
}

fn collect_missing_required_paths(value: &Value, path: &str, paths: &mut Vec<String>) {
    match value {
        Value::String(s) if s.starts_with("<required") => paths.push(path.to_string()),
        Value::Array(items) => {
            for (idx, item) in items.iter().enumerate() {
                collect_missing_required_paths(item, &format!("{path}[{idx}]"), paths);
            }
        }
        Value::Object(map) => {
            for (key, item) in map {
                collect_missing_required_paths(item, &format!("{path}.{key}"), paths);
            }
        }
        _ => {}
    }
}

fn env_truthy(key: &str) -> bool {
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

pub fn biocortex_replay_fixture_projection(
    fixture: &ShadowCortexReplayFixture,
    include_events: bool,
) -> Value {
    let mut source_counts: BTreeMap<String, usize> = BTreeMap::new();
    let mut scope_counts: BTreeMap<String, usize> = BTreeMap::new();
    let mut feature_key_counts: BTreeMap<String, usize> = BTreeMap::new();

    for event in &fixture.events {
        *source_counts.entry(event.source.clone()).or_default() += 1;
        *scope_counts
            .entry(scope_label(event.scope).to_string())
            .or_default() += 1;
        if let Some(obj) = event.features.as_object() {
            for key in obj.keys() {
                *feature_key_counts.entry(key.clone()).or_default() += 1;
            }
        }
    }

    let event_projection: Vec<Value> = fixture
        .events
        .iter()
        .map(|event| {
            let feature_keys = event
                .features
                .as_object()
                .map(|obj| obj.keys().cloned().collect::<Vec<_>>())
                .unwrap_or_default();
            json!({
                "event_id": event.event_id,
                "at": event.at,
                "source": event.source,
                "scope": scope_label(event.scope),
                "subject_id": event.subject_id,
                "feature_keys": feature_keys,
            })
        })
        .collect();
    let fixture_hash = sha256_json(&json!({
        "agent_shadow_cortex": fixture.agent_shadow_cortex,
        "mode": fixture.mode,
        "captured_at": fixture.captured_at,
        "window_days": fixture.window_days,
        "window_secs": fixture.window_secs,
        "requested_source": fixture.requested_source,
        "sources": fixture.sources,
        "events": event_projection,
    }));
    let substrate_replay_plan =
        substrate_replay_plan_for_fixture(fixture, &fixture_hash, include_events);

    let recommended_benchmark = recommended_benchmark_for_sources(&source_counts);
    let mut projection = json!({
        "schema": "agent_bridge.biocortex_ab_fixture_projection.v0",
        "fixture_hash": fixture_hash,
        "agent_shadow_cortex": fixture.agent_shadow_cortex,
        "mode": fixture.mode,
        "captured_at": fixture.captured_at,
        "window_days": fixture.window_days,
        "window_secs": fixture.window_secs,
        "requested_source": fixture.requested_source,
        "sources": fixture.sources,
        "event_count": fixture.events.len(),
        "source_counts": source_counts,
        "scope_counts": scope_counts,
        "feature_key_counts": feature_key_counts,
        "recommended_benchmark": recommended_benchmark,
        "substrate_replay_plan": substrate_replay_plan,
        "replay_feasibility": {
            "has_ab_events": !fixture.events.is_empty(),
            "current_biocortex_examples_accept_ab_input": true,
            "comparison_mode": "side_by_side_fixture_projection",
            "substrate_replay_plan_available": true,
            "next_adapter_needed": "BioCortex example that consumes substrate_replay_plan and reports substrate replay predicates"
        }
    });

    if include_events {
        projection["events"] = json!(event_projection);
    } else {
        projection["event_preview"] =
            json!(event_projection.into_iter().take(12).collect::<Vec<_>>());
        projection["events_omitted"] = json!(fixture.events.len().saturating_sub(12));
    }

    projection
}

fn substrate_replay_plan_for_fixture(
    fixture: &ShadowCortexReplayFixture,
    fixture_hash: &str,
    include_events: bool,
) -> Value {
    let pulses: Vec<Value> = fixture
        .events
        .iter()
        .enumerate()
        .map(|(idx, event)| substrate_replay_pulse(idx, event))
        .collect();
    let plan_hash = sha256_json(&json!({
        "schema": BIOCORTEX_SUBSTRATE_REPLAY_PLAN_SCHEMA,
        "fixture_hash": fixture_hash,
        "pulses": pulses,
        "neuron_map": substrate_neuron_map(),
        "synapse_plan": substrate_synapse_plan(),
    }));
    let mut plan = json!({
        "schema": BIOCORTEX_SUBSTRATE_REPLAY_PLAN_SCHEMA,
        "plan_hash": plan_hash,
        "fixture_hash": fixture_hash,
        "read_only": true,
        "replay_mode": "deterministic_open_loop_pulse_plan",
        "event_count": fixture.events.len(),
        "pulse_count": pulses.len(),
        "step_ms": 10,
        "current_unit": "nA",
        "ordering": "fixture_event_order",
        "neuron_map": substrate_neuron_map(),
        "synapse_plan": substrate_synapse_plan(),
        "adapter_contract": {
            "input_field": "substrate_replay_plan",
            "expected_input_schema": BIOCORTEX_SUBSTRATE_REPLAY_PLAN_SCHEMA,
            "expected_output_keys": [
                "substrate_replay_consumed",
                "event_pulses_applied",
                "integration_trace_bounded",
                "adapter_demonstrated"
            ],
            "comparison_claim": "AB events were replayed through a local BioCortex fixture, not used to mutate AB retrieval"
        },
        "boundary": {
            "open_loop": true,
            "read_only": true,
            "injects_reward": false,
            "mutates_structure": false,
            "mutates_ab_memory": false,
            "changes_retrieval_vector": false,
            "writes_global_substrate": false
        }
    });

    if include_events {
        plan["event_pulses"] = json!(pulses);
    } else {
        plan["event_pulse_preview"] = json!(pulses.into_iter().take(12).collect::<Vec<_>>());
        plan["event_pulses_omitted"] = json!(fixture.events.len().saturating_sub(12));
    }

    plan
}

fn substrate_replay_pulse(idx: usize, event: &ShadowCortexEvent) -> Value {
    let feature_keys = event
        .features
        .as_object()
        .map(|obj| obj.keys().cloned().collect::<Vec<_>>())
        .unwrap_or_default();
    let scope = scope_label(event.scope);
    json!({
        "step_index": idx,
        "time_ms": idx * 10,
        "event_id": event.event_id,
        "source": event.source,
        "scope": scope,
        "subject_id": event.subject_id,
        "input_neuron": substrate_input_neuron(event.scope),
        "target_neuron": "ab_integration_sink",
        "current_na": event_current_na(event),
        "duration_ms": event_duration_ms(event),
        "feature_keys": feature_keys,
        "pulse_kind": pulse_kind(event),
    })
}

fn substrate_neuron_map() -> Value {
    json!({
        "tool": {
            "label": "ab_tool_input",
            "scope": "tool",
            "role": "sensory_input"
        },
        "memory": {
            "label": "ab_memory_input",
            "scope": "memory",
            "role": "sensory_input"
        },
        "forum": {
            "label": "ab_forum_input",
            "scope": "forum",
            "role": "sensory_input"
        },
        "system": {
            "label": "ab_system_input",
            "scope": "system",
            "role": "sensory_input"
        },
        "integration": {
            "label": "ab_integration_sink",
            "scope": "integration",
            "role": "readout"
        }
    })
}

fn substrate_synapse_plan() -> Value {
    json!([
        substrate_synapse("ab_tool_input", "ab_integration_sink", 0.42, 1),
        substrate_synapse("ab_memory_input", "ab_integration_sink", 0.46, 2),
        substrate_synapse("ab_forum_input", "ab_integration_sink", 0.36, 3),
        substrate_synapse("ab_system_input", "ab_integration_sink", 0.32, 1)
    ])
}

fn substrate_synapse(from: &str, to: &str, weight: f64, delay_ms: u64) -> Value {
    json!({
        "from": from,
        "to": to,
        "weight": weight,
        "delay_ms": delay_ms,
        "plasticity": "disabled_for_replay"
    })
}

fn substrate_input_neuron(scope: SignalScope) -> &'static str {
    match scope {
        SignalScope::Tool => "ab_tool_input",
        SignalScope::Memory => "ab_memory_input",
        SignalScope::Forum => "ab_forum_input",
        SignalScope::System => "ab_system_input",
    }
}

fn event_current_na(event: &ShadowCortexEvent) -> f64 {
    let mut current = match event.scope {
        SignalScope::Tool => 0.68,
        SignalScope::Memory => 0.72,
        SignalScope::Forum => 0.60,
        SignalScope::System => 0.55,
    };

    current += numeric_feature(&event.features, "error_rate").unwrap_or(0.0) * 0.25;
    if let Some(hit_rate) = numeric_feature(&event.features, "hit_rate") {
        current += (0.60 - hit_rate).max(0.0) * 0.20;
    }
    if let Some(miss_count) = numeric_feature(&event.features, "miss_count")
        .or_else(|| numeric_feature(&event.features, "misses"))
    {
        current += (miss_count / 10.0).min(0.14);
    }
    if let Some(p95_ms) = numeric_feature(&event.features, "p95_duration_ms") {
        current += (p95_ms / 10_000.0).min(0.12);
    }
    if let Some(p95_us) = numeric_feature(&event.features, "p95_duration_us") {
        current += (p95_us / 1_000_000.0).min(0.10);
    }
    if let Some(call_count) = numeric_feature(&event.features, "call_count").filter(|v| *v > 0.0) {
        current += (call_count.log10() / 24.0).min(0.08);
    }
    if let Some(forum_posts) = numeric_feature(&event.features, "forum_posts").filter(|v| *v > 0.0)
    {
        current += (forum_posts.log10() / 20.0).min(0.08);
    }

    round3(current.clamp(0.25, 1.25))
}

fn event_duration_ms(event: &ShadowCortexEvent) -> u64 {
    let feature_count = event
        .features
        .as_object()
        .map(|obj| obj.len() as u64)
        .unwrap_or(0);
    5 + feature_count.min(5)
}

fn pulse_kind(event: &ShadowCortexEvent) -> &'static str {
    if event.event_id.contains(":errors") || event.event_id.contains(":miss") {
        "pressure"
    } else if event.event_id.contains(":latency") || event.event_id.contains(":result_size") {
        "load"
    } else if event.scope == SignalScope::Forum {
        "coordination"
    } else {
        "observation"
    }
}

fn numeric_feature(value: &Value, key: &str) -> Option<f64> {
    value.get(key).and_then(Value::as_f64)
}

fn round3(value: f64) -> f64 {
    (value * 1000.0).round() / 1000.0
}

fn benchmark_spec(name: &str) -> Option<BenchmarkSpec> {
    let normalized = normalize_token(name);
    BENCHMARKS
        .iter()
        .copied()
        .find(|spec| normalize_token(spec.benchmark) == normalized)
}

fn checkout_candidates(explicit: Option<&Path>) -> Vec<PathBuf> {
    let mut out = Vec::new();
    if let Some(path) = explicit {
        out.push(path.to_path_buf());
    }
    if let Ok(path) = std::env::var(BIOCORTEX_CHECKOUT_ENV) {
        if !path.trim().is_empty() {
            out.push(PathBuf::from(path));
        }
    }
    if let Ok(cwd) = std::env::current_dir() {
        out.push(cwd.join("biocortex-rs"));
        if let Some(parent) = cwd.parent() {
            out.push(parent.join("biocortex-rs"));
        }
    }
    out.push(PathBuf::from(
        "/Programs/Users/Pallasting/Documents/CascadeProjects/biocortex-rs",
    ));
    out.push(PathBuf::from("/Data/CascadeProjects/biocortex-rs"));
    out.push(PathBuf::from("/tmp/biocortex-rs-ab-eval"));
    dedupe_paths(out)
}

fn resolve_checkout(candidates: &[PathBuf]) -> Option<PathBuf> {
    candidates
        .iter()
        .find(|path| path.join("Cargo.toml").is_file() && path.join("src/lib.rs").is_file())
        .cloned()
}

fn dedupe_paths(paths: Vec<PathBuf>) -> Vec<PathBuf> {
    let mut out = Vec::new();
    for path in paths {
        if !out.iter().any(|p| p == &path) {
            out.push(path);
        }
    }
    out
}

pub fn parse_key_value_report(stdout: &str) -> Value {
    let mut map = Map::new();
    for line in stdout.lines() {
        let Some((raw_key, raw_value)) = line.split_once('=') else {
            continue;
        };
        let key = raw_key.trim();
        if key.is_empty() {
            continue;
        }
        map.insert(key.to_string(), parse_scalar(raw_value.trim()));
    }
    Value::Object(map)
}

fn parse_scalar(raw: &str) -> Value {
    match raw {
        "true" => Value::Bool(true),
        "false" => Value::Bool(false),
        _ => {
            if let Ok(n) = raw.parse::<i64>() {
                return Value::Number(Number::from(n));
            }
            if let Ok(n) = raw.parse::<f64>() {
                if let Some(num) = Number::from_f64(n) {
                    return Value::Number(num);
                }
            }
            Value::String(raw.to_string())
        }
    }
}

fn summarize_report(report: &Value) -> Value {
    let Some(obj) = report.as_object() else {
        return json!({
            "verdict": "empty",
            "demonstrated": false,
        });
    };
    let demonstrated: Vec<_> = obj
        .iter()
        .filter(|(key, value)| key.ends_with("_demonstrated") && value.as_bool() == Some(true))
        .map(|(key, _)| key.clone())
        .collect();
    let failed_predicates: Vec<_> = obj
        .iter()
        .filter(|(key, value)| {
            (key.ends_with("_demonstrated")
                || key.ends_with("_holds")
                || key.ends_with("_clean")
                || key.ends_with("_preserved")
                || key.ends_with("_bounded"))
                && value.as_bool() == Some(false)
        })
        .map(|(key, _)| key.clone())
        .collect();
    let open_limitations: Vec<_> = obj
        .iter()
        .filter(|(key, _)| key.as_str() == "open_limitation" || key.as_str() == "open_limitations")
        .map(|(_, value)| value.clone())
        .collect();
    let verdict = if obj.is_empty() {
        "empty"
    } else if failed_predicates.is_empty() {
        "shadow_pass"
    } else {
        "attention"
    };
    json!({
        "verdict": verdict,
        "field_count": obj.len(),
        "demonstrated": !demonstrated.is_empty(),
        "demonstrated_keys": demonstrated,
        "failed_predicates": failed_predicates,
        "open_limitations": open_limitations,
        "crate": obj.get("crate").cloned().unwrap_or(Value::Null),
        "generated_by": obj.get("generated_by").cloned().unwrap_or(Value::Null),
        "benchmark": obj.get("benchmark").cloned().unwrap_or(Value::Null),
    })
}

fn boundary_payload(runs_external_benchmark: bool, writes_temp_fixture_projection: bool) -> Value {
    json!({
        "mode": "shadow_only",
        "runs_external_benchmark": runs_external_benchmark,
        "writes_temp_fixture_projection": writes_temp_fixture_projection,
        "links_biocortex_into_ab_runtime": false,
        "mutates_ab_memory": false,
        "mutates_biocortex_source": false,
        "mutates_global_substrate": false,
        "changes_retrieval_vector": false,
        "accepts_reward_injection_from_ab": false,
        "network_required": false,
        "writes_build_cache": runs_external_benchmark,
    })
}

fn replay_boundary_payload() -> Value {
    json!({
        "mode": "shadow_replay_comparison",
        "read_only": true,
        "links_biocortex_into_ab_runtime": false,
        "mutates_ab_memory": false,
        "mutates_biocortex_source": false,
        "mutates_global_substrate": false,
        "changes_retrieval_vector": false,
        "biocortex_consumes_ab_fixture": true,
        "comparison_claim": "fixture_projection_consumed_by_external_biocortex_shadow_adapter",
    })
}

fn replay_comparison_summary(projection: &Value, digest: &Value) -> Value {
    let event_count = projection
        .get("event_count")
        .and_then(Value::as_u64)
        .unwrap_or(0);
    let digest_status = digest
        .get("status")
        .and_then(Value::as_str)
        .unwrap_or("unknown");
    let demonstrated = digest
        .pointer("/summary/demonstrated")
        .and_then(Value::as_bool)
        .unwrap_or(false);
    let failed_predicates = digest
        .pointer("/summary/failed_predicates")
        .and_then(Value::as_array)
        .map(|arr| arr.len())
        .unwrap_or(0);
    let benchmark = digest
        .get("benchmark")
        .and_then(Value::as_str)
        .unwrap_or("unknown");
    let recommended = projection
        .get("recommended_benchmark")
        .and_then(Value::as_str)
        .unwrap_or("scaled_morphology");
    let benchmark_alignment = if benchmark == recommended {
        "aligned"
    } else {
        "usable_but_not_source_matched"
    };
    let status = if digest_status != "ok" {
        "biocortex_unavailable"
    } else if event_count == 0 {
        "no_ab_events"
    } else if !demonstrated || failed_predicates > 0 {
        "biocortex_attention"
    } else {
        "shadow_comparable"
    };
    let next_step = if status == "shadow_comparable" {
        "add substrate-level replay that maps projected AB events into BioCortex mechanisms"
    } else if status == "no_ab_events" {
        "collect a non-empty shadow-cortex fixture window before judging replay value"
    } else {
        "fix the external BioCortex shadow benchmark or inspect failed predicates"
    };

    json!({
        "status": status,
        "benchmark_alignment": benchmark_alignment,
        "event_count": event_count,
        "biocortex_status": digest_status,
        "biocortex_demonstrated": demonstrated,
        "biocortex_failed_predicates": failed_predicates,
        "current_adapter_consumes_ab_events": digest.get("benchmark").and_then(Value::as_str) == Some("ab_fixture_projection"),
        "retrieval_mutation": false,
        "next_step": next_step,
    })
}

fn recommended_benchmark_for_sources(source_counts: &BTreeMap<String, usize>) -> &'static str {
    if source_counts.contains_key("memory_query_log") {
        "ab_fixture_projection"
    } else if source_counts.contains_key("forum_posts") {
        "ab_fixture_projection"
    } else {
        "ab_fixture_projection"
    }
}

fn fixture_projection_summary(projection: Option<&Value>) -> Value {
    let Some(projection) = projection else {
        return json!({"provided": false});
    };
    json!({
        "provided": true,
        "fixture_hash": projection.get("fixture_hash").cloned().unwrap_or(Value::Null),
        "event_count": projection.get("event_count").cloned().unwrap_or(Value::Null),
        "schema": projection.get("schema").cloned().unwrap_or(Value::Null),
    })
}

fn scope_label(scope: SignalScope) -> &'static str {
    match scope {
        SignalScope::Memory => "memory",
        SignalScope::Tool => "tool",
        SignalScope::Forum => "forum",
        SignalScope::System => "system",
    }
}

fn sha256_json(value: &Value) -> String {
    let encoded = serde_json::to_vec(value).unwrap_or_default();
    let mut hasher = Sha256::new();
    hasher.update(encoded);
    format!("sha256:{:x}", hasher.finalize())
}

fn candidate_key_hash(key: &str) -> String {
    sha256_json(&json!({"candidate_key": key}))
}

fn redacted_baseline_rank_rows(baseline: &[RetrievalBaselineScore]) -> Value {
    let rows = baseline
        .iter()
        .map(|row| (candidate_key_hash(&row.key), row.rank))
        .collect::<Vec<_>>();
    redacted_rank_rows_value(&rows, "baseline_rank")
}

fn redacted_advisory_rank_rows(advisory_rows: &[(String, f32)], available: bool) -> Value {
    if !available {
        return Value::Array(Vec::new());
    }
    let rows = advisory_rows
        .iter()
        .enumerate()
        .map(|(idx, (key, _))| (candidate_key_hash(key), idx + 1))
        .collect::<Vec<_>>();
    redacted_rank_rows_value(&rows, "advisory_rank")
}

fn memory_hits_order_hash(mode: &str, hits: &[MemorySearchHit]) -> String {
    let keys = hits
        .iter()
        .map(|hit| hit.record.key.as_str())
        .collect::<Vec<_>>();
    sha256_json(&json!({
        "mode": mode,
        "keys": keys,
    }))
}

fn memory_hits_top_key_hash(hits: &[MemorySearchHit]) -> Value {
    hits.first()
        .map(|hit| candidate_key_hash(&hit.record.key))
        .map(Value::String)
        .unwrap_or(Value::Null)
}

fn redacted_memory_hit_rank_rows(hits: &[MemorySearchHit], rank_field: &str) -> Value {
    let rows = hits
        .iter()
        .enumerate()
        .map(|(idx, hit)| (candidate_key_hash(&hit.record.key), idx + 1))
        .collect::<Vec<_>>();
    redacted_rank_rows_value(&rows, rank_field)
}

fn redacted_rank_rows_value(rows: &[(String, usize)], rank_field: &str) -> Value {
    Value::Array(
        rows.iter()
            .map(|(key_hash, rank)| {
                let mut row = Map::new();
                row.insert("key_hash".to_string(), Value::String(key_hash.clone()));
                row.insert(rank_field.to_string(), json!(rank));
                Value::Object(row)
            })
            .collect(),
    )
}

fn sanitized_redacted_rank_rows(value: Option<&Value>, rank_field: &str) -> Vec<(String, usize)> {
    let mut rows = value
        .and_then(Value::as_array)
        .map(|items| {
            items
                .iter()
                .filter_map(|item| {
                    let key_hash = item.get("key_hash").and_then(Value::as_str)?;
                    let rank = item.get(rank_field).and_then(Value::as_u64)?;
                    if !safe_redacted_key_hash(key_hash) || rank == 0 {
                        return None;
                    }
                    Some((key_hash.to_string(), rank as usize))
                })
                .collect::<Vec<_>>()
        })
        .unwrap_or_default();
    rows.sort_by(|left, right| left.1.cmp(&right.1).then_with(|| left.0.cmp(&right.0)));
    rows
}

fn safe_redacted_key_hash(value: &str) -> bool {
    let Some(hex) = value.strip_prefix("sha256:") else {
        return false;
    };
    hex.len() == 64 && hex.chars().all(|ch| ch.is_ascii_hexdigit())
}

fn redacted_rank_rows_have_duplicate_hash(rows: &[(String, usize)]) -> bool {
    let mut seen = BTreeSet::new();
    rows.iter()
        .any(|(key_hash, _)| !seen.insert(key_hash.as_str()))
}

fn redacted_rank_map(rows: &[(String, usize)]) -> BTreeMap<String, usize> {
    rows.iter()
        .map(|(key_hash, rank)| (key_hash.clone(), *rank))
        .collect()
}

fn redacted_top_k_overlap_value(
    baseline_rows: &[(String, usize)],
    advisory_rows: &[(String, usize)],
) -> Value {
    let ks = [1usize, 3, 10];
    Value::Array(
        ks.iter()
            .map(|k| {
                let baseline_top = baseline_rows
                    .iter()
                    .filter(|(_, rank)| rank <= k)
                    .map(|(key_hash, _)| key_hash.clone())
                    .collect::<BTreeSet<_>>();
                let advisory_top = advisory_rows
                    .iter()
                    .filter(|(_, rank)| rank <= k)
                    .map(|(key_hash, _)| key_hash.clone())
                    .collect::<BTreeSet<_>>();
                let overlap_count = baseline_top.intersection(&advisory_top).count();
                let union_count = baseline_top.union(&advisory_top).count();
                let jaccard = if union_count == 0 {
                    Value::Null
                } else {
                    json!(round3(overlap_count as f64 / union_count as f64))
                };
                let overlap_ratio_of_baseline_top_k = if baseline_top.is_empty() {
                    Value::Null
                } else {
                    json!(round3(overlap_count as f64 / baseline_top.len() as f64))
                };
                json!({
                    "k": k,
                    "baseline_count": baseline_top.len(),
                    "advisory_count": advisory_top.len(),
                    "overlap_count": overlap_count,
                    "union_count": union_count,
                    "jaccard": jaccard,
                    "overlap_ratio_of_baseline_top_k": overlap_ratio_of_baseline_top_k,
                })
            })
            .collect(),
    )
}

fn redacted_rank_movement_values(
    baseline_rows: &[(String, usize)],
    advisory_rows: &[(String, usize)],
) -> (Value, Value) {
    let baseline_map = redacted_rank_map(baseline_rows);
    let advisory_map = redacted_rank_map(advisory_rows);
    let mut keys = baseline_map
        .keys()
        .chain(advisory_map.keys())
        .cloned()
        .collect::<BTreeSet<_>>()
        .into_iter()
        .collect::<Vec<_>>();
    keys.sort_by(|left, right| {
        let left_baseline = baseline_map.get(left).copied().unwrap_or(usize::MAX);
        let right_baseline = baseline_map.get(right).copied().unwrap_or(usize::MAX);
        let left_advisory = advisory_map.get(left).copied().unwrap_or(usize::MAX);
        let right_advisory = advisory_map.get(right).copied().unwrap_or(usize::MAX);
        left_baseline
            .cmp(&right_baseline)
            .then_with(|| left_advisory.cmp(&right_advisory))
            .then_with(|| left.cmp(right))
    });

    let mut improved_count = 0usize;
    let mut regressed_count = 0usize;
    let mut unchanged_count = 0usize;
    let mut missing_baseline_count = 0usize;
    let mut missing_advisory_count = 0usize;
    let mut max_abs_delta = 0i64;
    let movements = keys
        .into_iter()
        .map(|key_hash| {
            let baseline_rank = baseline_map.get(&key_hash).copied();
            let advisory_rank = advisory_map.get(&key_hash).copied();
            let delta = match (baseline_rank, advisory_rank) {
                (Some(baseline_rank), Some(advisory_rank)) => {
                    Some(advisory_rank as i64 - baseline_rank as i64)
                }
                _ => None,
            };
            let direction = match delta {
                Some(delta) if delta < 0 => {
                    improved_count += 1;
                    "improved"
                }
                Some(delta) if delta > 0 => {
                    regressed_count += 1;
                    "regressed"
                }
                Some(_) => {
                    unchanged_count += 1;
                    "unchanged"
                }
                None if baseline_rank.is_none() => {
                    missing_baseline_count += 1;
                    "missing_baseline"
                }
                None => {
                    missing_advisory_count += 1;
                    "missing_advisory"
                }
            };
            if let Some(delta) = delta {
                max_abs_delta = max_abs_delta.max(delta.abs());
            }
            json!({
                "key_hash": key_hash,
                "baseline_rank": baseline_rank.map(|rank| json!(rank)).unwrap_or(Value::Null),
                "advisory_rank": advisory_rank.map(|rank| json!(rank)).unwrap_or(Value::Null),
                "rank_delta_advisory_minus_baseline": delta
                    .map(|delta| json!(delta))
                    .unwrap_or(Value::Null),
                "direction": direction,
            })
        })
        .collect::<Vec<_>>();

    (
        json!({
            "improved_count": improved_count,
            "regressed_count": regressed_count,
            "unchanged_count": unchanged_count,
            "missing_baseline_count": missing_baseline_count,
            "missing_advisory_count": missing_advisory_count,
            "max_abs_delta": max_abs_delta,
            "comparable_key_count": improved_count + regressed_count + unchanged_count,
        }),
        Value::Array(movements),
    )
}

fn display_path(path: &Path) -> String {
    path.to_string_lossy().to_string()
}

fn normalize_token(value: &str) -> String {
    value
        .trim()
        .to_ascii_lowercase()
        .replace('-', "_")
        .replace(' ', "_")
}

fn now_secs() -> i64 {
    SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map(|d| d.as_secs() as i64)
        .unwrap_or(0)
}

fn now_nanos() -> u128 {
    SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map(|d| d.as_nanos())
        .unwrap_or(0)
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::sync::Mutex;

    static ENV_LOCK: Mutex<()> = Mutex::new(());

    #[test]
    fn strip_frontmatter_removes_leading_yaml_block() {
        let c = "---\nname: x\ntype: project\n---\nbody text here";
        assert_eq!(strip_leading_frontmatter(c), "body text here");
        // no frontmatter -> returned trimmed as-is
        assert_eq!(strip_leading_frontmatter("  hello world"), "hello world");
        // a stray leading "---" with no closing fence stays put
        assert!(strip_leading_frontmatter("--- not a fence").starts_with("---"));
    }

    #[test]
    fn derive_query_is_char_safe_on_cjk() {
        // CJK content: char-safe truncation must NOT panic mid-codepoint and
        // must return exactly max_chars characters (not bytes).
        let content = "中文记忆内容：语义系统总线与生物皮层检索的关系非常重要".repeat(3);
        let q = derive_self_retrieval_query(&content, 10);
        assert_eq!(q.chars().count(), 10, "must take 10 chars, not 10 bytes");
        // collapses whitespace from a frontmatter + multiline body
        let multi = "---\nname: y\n---\n第一行\n第二行   第三行";
        let q2 = derive_self_retrieval_query(multi, 100);
        assert_eq!(q2, "第一行 第二行 第三行");

        // FTS5-special chars must be neutralized (the live-eval bug: raw content
        // like "seed:" / "#" / "*" / "S10a:" broke the FTS5 parser and failed
        // every baseline search).
        let nasty = "S10a: seed:robustness *wild #hash \"quote\" (paren) AND NOT";
        let q3 = derive_self_retrieval_query(nasty, 200);
        for bad in [':', '*', '#', '"', '(', ')', '^'] {
            assert!(!q3.contains(bad), "FTS-special {bad:?} survived: {q3}");
        }
        assert!(
            !q3.contains("AND") && !q3.contains("NOT"),
            "uppercase operators must be lowercased to barewords: {q3}"
        );
        assert_eq!(q3, "s10a seed robustness wild hash quote paren and not");
    }

    #[test]
    fn relevance_lift_class_aggregate_reports_redacted_bucket_metrics() {
        let relevant = BTreeSet::from(["src".to_string()]);
        let improved = crate::biocortex_relevance_eval::sample_lift(
            &["decoy".to_string(), "src".to_string()],
            &["src".to_string(), "decoy".to_string()],
            "src",
            &relevant,
        );
        let unchanged = crate::biocortex_relevance_eval::sample_lift(
            &["src".to_string(), "decoy".to_string()],
            &["src".to_string(), "decoy".to_string()],
            "src",
            &relevant,
        );

        let value =
            relevance_lift_class_aggregate_to_json("hard".to_string(), &[improved, unchanged]);

        assert_eq!(value["class_label"], json!("hard"));
        assert_eq!(value["evaluated_count"], json!(2));
        assert_eq!(value["source_found_count"], json!(2));
        assert_eq!(value["improved"], json!(1));
        assert_eq!(value["worsened"], json!(0));
        assert_eq!(value["unchanged"], json!(1));
        assert_eq!(value["order_changed_count"], json!(1));
        assert_eq!(value["mrr_baseline"], json!(0.75));
        assert_eq!(value["mrr_reordered"], json!(1.0));
        assert_eq!(value["mrr_lift"], json!(0.25));
        assert_eq!(value["verdict"], json!("lift_demonstrated"));

        let serialized = serde_json::to_string(&value).expect("serialize");
        assert!(!serialized.contains("query"));
        assert!(!serialized.contains("key"));
        assert!(!serialized.contains("content"));
    }

    #[test]
    fn parse_key_value_report_types_scalars() {
        let report = parse_key_value_report(
            "schema_version=2\ncrate=biocortex-rs\nok=true\nn=42\nratio=0.125\n",
        );

        assert_eq!(report["schema_version"], json!(2));
        assert_eq!(report["crate"], json!("biocortex-rs"));
        assert_eq!(report["ok"], json!(true));
        assert_eq!(report["n"], json!(42));
        assert_eq!(report["ratio"], json!(0.125));
    }

    #[test]
    fn summarize_report_flags_failed_predicates() {
        let report = json!({
            "benchmark": "scaled_morphology",
            "scaled_morphology_demonstrated": true,
            "executor_clean": false,
            "open_limitation": "outcomes_injected"
        });
        let summary = summarize_report(&report);

        assert_eq!(summary["verdict"], json!("attention"));
        assert_eq!(summary["demonstrated"], json!(true));
        assert_eq!(summary["failed_predicates"], json!(["executor_clean"]));
        assert_eq!(summary["open_limitations"], json!(["outcomes_injected"]));
    }

    #[test]
    fn replay_projection_full_carries_all_pulses_preview_caps_at_12() {
        // Regression for the adapter-starve footgun: the external BioCortex adapter
        // applies the plan's pulse list to demonstrate; if it only receives the
        // 12-pulse preview it reports command_failed → a healthy integration
        // misread as `biocortex_unavailable`. biocortex_replay_comparison therefore
        // always feeds the adapter the FULL plan. This pins the two projection
        // shapes that guarantee lets it rely on.
        let events: Vec<_> = (0..15)
            .map(|i| crate::shadow_cortex::ShadowCortexEvent {
                agent_shadow_cortex: 1,
                event_id: format!("mcp_dispatch:tool{i}:errors"),
                at: 1_780_000_000,
                source: "mcp_dispatch".to_string(),
                scope: SignalScope::Tool,
                subject_id: format!("tool{i}"),
                features: json!({"error_count": 1, "call_count": 2}),
            })
            .collect();
        let fixture = ShadowCortexReplayFixture {
            agent_shadow_cortex: 1,
            mode: crate::shadow_cortex::ShadowCortexMode::Heuristic,
            captured_at: 1_780_000_000,
            window_days: 7,
            window_secs: 604_800,
            requested_source: "all".to_string(),
            sources: vec!["mcp_dispatch".to_string()],
            mcp_dispatch: None,
            memory_query_log: None,
            forum_window: None,
            events,
        };

        // Full plan (what the adapter is now always fed): every pulse present.
        let full = biocortex_replay_fixture_projection(&fixture, true);
        let plan_full = &full["substrate_replay_plan"];
        assert_eq!(plan_full["pulse_count"], json!(15));
        assert_eq!(plan_full["event_pulses"].as_array().unwrap().len(), 15);
        assert!(
            plan_full.get("event_pulse_preview").is_none(),
            "full plan must not truncate to a preview"
        );

        // Preview plan (echoed by default for token budget): capped at 12, and
        // crucially carries NO full `event_pulses` — feeding THIS to the adapter is
        // exactly what starved it before the fix.
        let preview = biocortex_replay_fixture_projection(&fixture, false);
        let plan_prev = &preview["substrate_replay_plan"];
        assert_eq!(plan_prev["pulse_count"], json!(15));
        assert_eq!(
            plan_prev["event_pulse_preview"].as_array().unwrap().len(),
            12
        );
        assert_eq!(plan_prev["event_pulses_omitted"], json!(3));
        assert!(
            plan_prev.get("event_pulses").is_none(),
            "preview plan must not carry the full pulse list"
        );
    }

    #[test]
    fn replay_fixture_projection_counts_sources_and_scopes() {
        let fixture = ShadowCortexReplayFixture {
            agent_shadow_cortex: 1,
            mode: crate::shadow_cortex::ShadowCortexMode::Heuristic,
            captured_at: 1_780_000_000,
            window_days: 7,
            window_secs: 604_800,
            requested_source: "all".to_string(),
            sources: vec!["mcp_dispatch".to_string(), "memory_query_log".to_string()],
            mcp_dispatch: None,
            memory_query_log: None,
            forum_window: None,
            events: vec![
                crate::shadow_cortex::ShadowCortexEvent {
                    agent_shadow_cortex: 1,
                    event_id: "mcp_dispatch:tool:errors".to_string(),
                    at: 1_780_000_000,
                    source: "mcp_dispatch".to_string(),
                    scope: SignalScope::Tool,
                    subject_id: "tool".to_string(),
                    features: json!({"error_count": 2, "call_count": 4}),
                },
                crate::shadow_cortex::ShadowCortexEvent {
                    agent_shadow_cortex: 1,
                    event_id: "memory_query_log:window:hit_rate".to_string(),
                    at: 1_780_000_000,
                    source: "memory_query_log".to_string(),
                    scope: SignalScope::Memory,
                    subject_id: "memory_query_log".to_string(),
                    features: json!({"total_queries": 3, "misses": 1}),
                },
            ],
        };

        let projection = biocortex_replay_fixture_projection(&fixture, false);

        assert_eq!(projection["event_count"], json!(2));
        assert_eq!(projection["source_counts"]["mcp_dispatch"], json!(1));
        assert_eq!(projection["source_counts"]["memory_query_log"], json!(1));
        assert_eq!(projection["scope_counts"]["tool"], json!(1));
        assert_eq!(projection["scope_counts"]["memory"], json!(1));
        assert_eq!(
            projection["recommended_benchmark"],
            json!("ab_fixture_projection")
        );
        assert_eq!(
            projection["substrate_replay_plan"]["schema"],
            json!(BIOCORTEX_SUBSTRATE_REPLAY_PLAN_SCHEMA)
        );
        assert_eq!(projection["substrate_replay_plan"]["pulse_count"], json!(2));
        assert_eq!(
            projection["substrate_replay_plan"]["event_pulse_preview"][0]["input_neuron"],
            json!("ab_tool_input")
        );
        assert_eq!(
            projection["substrate_replay_plan"]["event_pulse_preview"][1]["input_neuron"],
            json!("ab_memory_input")
        );
        assert_eq!(
            projection["substrate_replay_plan"]["boundary"]["injects_reward"],
            json!(false)
        );
        assert_eq!(
            projection["substrate_replay_plan"]["boundary"]["mutates_structure"],
            json!(false)
        );
        assert_eq!(
            projection["substrate_replay_plan"]["boundary"]["changes_retrieval_vector"],
            json!(false)
        );
        assert_eq!(
            projection["replay_feasibility"]["current_biocortex_examples_accept_ab_input"],
            json!(true)
        );
        assert_eq!(
            projection["replay_feasibility"]["substrate_replay_plan_available"],
            json!(true)
        );
        assert!(projection["fixture_hash"]
            .as_str()
            .unwrap_or_default()
            .starts_with("sha256:"));
    }

    #[test]
    fn retrieval_boundary_payload_keeps_runtime_mutation_forbidden() {
        let boundary = retrieval_boundary_payload();

        assert_eq!(boundary["mode"], json!("retrieval_shadow_advisory_only"));
        assert_eq!(boundary["read_only"], json!(true));
        assert_eq!(boundary["runtime_adapter_approved"], json!(false));
        assert_eq!(boundary["registers_embedding_backend"], json!(false));
        assert_eq!(boundary["calls_set_default_backend"], json!(false));
        assert_eq!(boundary["mutates_ab_memory"], json!(false));
        assert_eq!(boundary["writes_embeddings"], json!(false));
        assert_eq!(boundary["writes_coactivation"], json!(false));
        assert_eq!(boundary["writes_graph_edges"], json!(false));
        assert_eq!(boundary["changes_memory_search_order"], json!(false));
        assert_eq!(boundary["default_search_order_changed"], json!(false));
    }

    #[test]
    fn retrieval_rank_report_is_advisory_even_when_side_signal_changes_top() {
        let baseline = vec![
            RetrievalBaselineScore {
                key: "baseline_top".to_string(),
                content: "baseline candidate".to_string(),
                score: 0.9,
                rank: 1,
            },
            RetrievalBaselineScore {
                key: "side_signal_top".to_string(),
                content: "side signal candidate".to_string(),
                score: 0.2,
                rank: 2,
            },
        ];
        let candidates = baseline
            .iter()
            .map(|row| BioCortexRetrievalCandidate {
                key: row.key.clone(),
                content: row.content.clone(),
            })
            .collect::<Vec<_>>();
        let side_by_key = BTreeMap::from([
            ("baseline_top".to_string(), 0.0_f32),
            ("side_signal_top".to_string(), 1.0_f32),
        ]);
        let evidence_by_key =
            BTreeMap::from([("side_signal_top".to_string(), "overlap=1.000".to_string())]);

        let report = retrieval_rank_report(
            "ok",
            "query".to_string(),
            candidates,
            Some("baseline_top".to_string()),
            baseline,
            &side_by_key,
            &evidence_by_key,
            RetrievalAlphaConfig {
                policy: "candidate-strong".to_string(),
                alpha: 0.8,
                explicit_alpha: false,
            },
            json!({"compile_feature_enabled": true}),
            3.2,
            None,
            None,
        );

        assert_eq!(report["schema"], json!(BIOCORTEX_RETRIEVAL_SHADOW_SCHEMA));
        assert_eq!(report["read_only"], json!(true));
        assert_eq!(report["runtime_adapter_approved"], json!(false));
        assert_eq!(report["default_search_order_changed"], json!(false));
        assert_eq!(report["baseline_top_key"], json!("baseline_top"));
        assert_eq!(report["advisory_top_key"], json!("side_signal_top"));
        assert_eq!(report["expected"]["baseline_rank"], json!(1));
        assert_eq!(report["expected"]["advisory_rank"], json!(2));
        assert_eq!(report["expected"]["regressed"], json!(true));
        assert_eq!(report["expected_regressions"], json!(1));
        assert_eq!(report["side_signal_coverage"], json!(1.0));
        assert_eq!(
            report["hits"][1]["side_signal_evidence"],
            json!("overlap=1.000")
        );
        assert_eq!(
            report["boundary"]["changes_memory_search_order"],
            json!(false)
        );
    }

    #[test]
    fn retrieval_runtime_approval_packet_preview_is_not_approval_state() {
        let packet = biocortex_retrieval_runtime_approval_packet_preview(
            BioCortexRetrievalApprovalPacketOptions {
                commit: Some("abc123".to_string()),
                verification_status: Some("pass".to_string()),
                agent_attestor: Some("codex".to_string()),
                agent_attestation_decision: Some("technical_review_pending".to_string()),
                human_authorization_scope: Some("none".to_string()),
                ..Default::default()
            },
        );

        assert_eq!(
            packet["schema"],
            json!(BIOCORTEX_RETRIEVAL_RUNTIME_APPROVAL_PACKET_SCHEMA)
        );
        assert_eq!(packet["approval_state"], json!("not_approved"));
        assert_eq!(packet["default_decision"], json!("keep_shadow_only"));
        assert_eq!(packet["runtime_adapter_approved"], json!(false));
        assert_eq!(packet["writes_approval"], json!(false));
        assert_eq!(packet["approval_writes_allowed"], json!(false));
        assert_eq!(packet["default_search_order_change_allowed"], json!(false));
        assert_eq!(packet["requires_separate_human_approval"], json!(true));
        assert_eq!(packet["ready_for_human_approval_review"], json!(false));
        assert_eq!(
            packet["approval_model"]["agent_technical_attestation_required"],
            json!(true)
        );
        assert_eq!(
            packet["approval_model"]["human_authorization_required"],
            json!(true)
        );
        assert_eq!(
            packet["approval_model"]["agent_attestation_can_replace_human_authorization"],
            json!(false)
        );
        assert_eq!(
            packet["agent_technical_attestation"]["attestor"],
            json!("codex")
        );
        assert_eq!(
            packet["agent_technical_attestation"]["decision"],
            json!("technical_review_pending")
        );
        assert_eq!(
            packet["agent_technical_attestation"]["can_authorize_runtime_influence"],
            json!(false)
        );
        assert_eq!(
            packet["human_authorization"]["status"],
            json!("not_authorized")
        );
        assert_eq!(
            packet["human_authorization"]["can_be_replaced_by_agent_attestation"],
            json!(false)
        );
        assert_eq!(packet["evidence"]["commit"], json!("abc123"));
        assert_eq!(
            packet["evidence"]["verification_bundle"]["status"],
            json!("pass")
        );
        let missing = packet["missing_evidence"]
            .as_array()
            .expect("missing paths");
        assert!(missing.iter().any(|path| path == "$.target_host"));
        assert!(missing
            .iter()
            .any(|path| path == "$.ordering_change_design.exact_call_site"));
        let missing_attestation = packet["missing_attestation"]
            .as_array()
            .expect("missing attestation paths");
        assert!(missing_attestation.iter().any(|path| path == "$.summary"));
        assert_eq!(
            packet["gates"]["compile_feature"],
            json!("biocortex-retrieval-shadow")
        );
    }

    #[test]
    fn retrieval_opt_in_gate_requires_feature_runtime_and_call_opt_in() {
        let _lock = ENV_LOCK.lock().expect("env lock");
        let _guard = EnvRestore::capture(&[
            BIOCORTEX_RETRIEVAL_OPT_IN_ENABLE_ENV,
            BIOCORTEX_RETRIEVAL_DISABLE_ENV,
        ]);
        std::env::remove_var(BIOCORTEX_RETRIEVAL_OPT_IN_ENABLE_ENV);
        std::env::remove_var(BIOCORTEX_RETRIEVAL_DISABLE_ENV);

        let runtime_missing = biocortex_retrieval_opt_in_gate_report(true);
        assert_eq!(
            runtime_missing["schema"],
            json!(BIOCORTEX_RETRIEVAL_OPT_IN_GATE_SCHEMA)
        );
        assert_eq!(runtime_missing["read_only"], json!(true));
        assert_eq!(runtime_missing["runtime_adapter_approved"], json!(false));
        assert_eq!(
            runtime_missing["default_search_order_change_allowed"],
            json!(false)
        );
        assert_eq!(runtime_missing["default_calls_unchanged"], json!(true));
        assert_eq!(runtime_missing["may_change_search_order_now"], json!(false));
        assert_eq!(runtime_missing["ordering_behavior_connected"], json!(false));
        assert_eq!(
            runtime_missing["ready_for_explicit_opt_in_experiment"],
            json!(false)
        );
        if cfg!(feature = "biocortex-retrieval-opt-in") {
            assert_eq!(runtime_missing["status"], json!("runtime_disabled"));
        } else {
            assert_eq!(runtime_missing["status"], json!("compile_feature_disabled"));
        }

        std::env::set_var(BIOCORTEX_RETRIEVAL_OPT_IN_ENABLE_ENV, "1");
        let call_opt_in_missing = biocortex_retrieval_opt_in_gate_report(false);
        if cfg!(feature = "biocortex-retrieval-opt-in") {
            assert_eq!(
                call_opt_in_missing["status"],
                json!("per_call_opt_in_missing")
            );
        } else {
            assert_eq!(
                call_opt_in_missing["status"],
                json!("compile_feature_disabled")
            );
        }
        assert_eq!(
            call_opt_in_missing["ready_for_explicit_opt_in_experiment"],
            json!(false)
        );

        let ready = biocortex_retrieval_opt_in_gate_report(true);
        assert_eq!(ready["may_change_search_order_now"], json!(false));
        assert_eq!(ready["ordering_behavior_connected"], json!(false));
        if cfg!(feature = "biocortex-retrieval-opt-in") {
            assert_eq!(
                ready["status"],
                json!("ready_for_explicit_opt_in_experiment")
            );
            assert_eq!(ready["ready_for_explicit_opt_in_experiment"], json!(true));
        } else {
            assert_eq!(ready["status"], json!("compile_feature_disabled"));
            assert_eq!(ready["ready_for_explicit_opt_in_experiment"], json!(false));
        }

        std::env::set_var(BIOCORTEX_RETRIEVAL_DISABLE_ENV, "1");
        let disabled = biocortex_retrieval_opt_in_gate_report(true);
        if cfg!(feature = "biocortex-retrieval-opt-in") {
            assert_eq!(disabled["status"], json!("operator_disabled"));
        } else {
            assert_eq!(disabled["status"], json!("compile_feature_disabled"));
        }
        assert_eq!(
            disabled["ready_for_explicit_opt_in_experiment"],
            json!(false)
        );
    }

    #[test]
    fn opt_in_audit_shape_keeps_baseline_order_hashed() {
        let _lock = ENV_LOCK.lock().expect("env lock");
        let _guard = EnvRestore::capture(&[
            BIOCORTEX_RETRIEVAL_OPT_IN_ENABLE_ENV,
            BIOCORTEX_RETRIEVAL_DISABLE_ENV,
        ]);
        std::env::set_var(BIOCORTEX_RETRIEVAL_OPT_IN_ENABLE_ENV, "1");
        std::env::remove_var(BIOCORTEX_RETRIEVAL_DISABLE_ENV);

        let audit = biocortex_retrieval_opt_in_audit_report(BioCortexRetrievalOptInAuditOptions {
            mode: "fts".to_string(),
            per_call_opt_in: true,
            query: Some("find the runtime boundary proof".to_string()),
            baseline_keys: vec![
                "baseline_top_key".to_string(),
                "side_signal_candidate_key".to_string(),
            ],
            side_signal_status: None,
            fallback_reason: None,
            latency_ms: Some(3.4567),
            runtime_readiness_packet: None,
            runtime_transition_gate: None,
            gated_store_trial: None,
            gated_batch_diagnostics: None,
        });

        assert_eq!(
            audit["schema"],
            json!(BIOCORTEX_RETRIEVAL_OPT_IN_AUDIT_SCHEMA)
        );
        assert_eq!(audit["read_only"], json!(true));
        assert_eq!(audit["implementation_stage"], json!("audit_shape_only"));
        assert_eq!(audit["authorization_scope"], json!("opt_in_experiment"));
        assert_eq!(audit["mode"], json!("fts"));
        assert_eq!(audit["mode_authorized"], json!(true));
        assert_eq!(audit["per_call_opt_in"]["present"], json!(true));
        assert_eq!(audit["baseline_order"]["key_count"], json!(2));
        assert_eq!(audit["baseline_order"]["raw_keys_included"], json!(false));
        assert_eq!(audit["baseline_order"]["content_included"], json!(false));
        assert!(audit["baseline_order"]["hash"]
            .as_str()
            .unwrap_or_default()
            .starts_with("sha256:"));
        assert_eq!(audit["experimental_order"]["available"], json!(false));
        assert_eq!(
            audit["returned_order"]["hash_matches_baseline"],
            json!(true)
        );
        assert_eq!(audit["fallback"]["baseline_returned"], json!(true));
        assert_eq!(audit["side_signal"]["raw_included"], json!(false));
        assert_eq!(audit["latency_ms"], json!(3.457));
        assert_eq!(audit["runtime_adapter_approved"], json!(false));
        assert_eq!(audit["default_search_order_change_allowed"], json!(false));
        assert_eq!(audit["default_calls_unchanged"], json!(true));
        assert_eq!(audit["may_change_search_order_now"], json!(false));
        assert_eq!(audit["ordering_behavior_connected"], json!(false));
        assert_eq!(audit["changes_memory_search_order"], json!(false));
        assert_eq!(
            audit["controlled_trial_readiness"]["status"],
            json!("evidence_not_provided")
        );
        assert_eq!(
            audit["controlled_trial_readiness"]["ready_for_controlled_trial"],
            json!(false)
        );
        assert_eq!(
            audit["store_contract"]["schema"],
            json!("agent_bridge.store.memory_search.biocortex_opt_in_contract.v0")
        );
        assert_eq!(
            audit["store_contract"]["returned_order_source"],
            json!("baseline")
        );
        assert_eq!(audit["store_contract"]["baseline_returned"], json!(true));
        assert_eq!(
            audit["store_contract"]["changes_memory_search_order"],
            json!(false)
        );
        assert_eq!(
            audit["store_contract"]["decision"]["audit_requirements"]["raw_keys_included"],
            json!(false)
        );
        assert_eq!(
            audit["store_contract"]["decision"]["audit_requirements"]["content_included"],
            json!(false)
        );

        if cfg!(feature = "biocortex-retrieval-opt-in") {
            assert_eq!(
                audit["gate"]["status"],
                json!("ready_for_explicit_opt_in_experiment")
            );
            assert_eq!(
                audit["fallback"]["reason"],
                json!("ordering_behavior_not_connected")
            );
            assert_eq!(
                audit["side_signal"]["status"],
                json!("not_run_ordering_behavior_not_connected")
            );
        } else {
            assert_eq!(audit["gate"]["status"], json!("compile_feature_disabled"));
            assert_eq!(
                audit["fallback"]["reason"],
                json!("compile_feature_disabled")
            );
            assert_eq!(
                audit["side_signal"]["status"],
                json!("not_run_gate_unavailable")
            );
        }

        let serialized = serde_json::to_string(&audit).expect("audit json");
        assert!(!serialized.contains("baseline_top_key"));
        assert!(!serialized.contains("side_signal_candidate_key"));
        assert!(!serialized.contains("find the runtime boundary proof"));
    }

    #[test]
    fn opt_in_audit_shape_rejects_non_fts_modes() {
        let _lock = ENV_LOCK.lock().expect("env lock");
        let _guard = EnvRestore::capture(&[
            BIOCORTEX_RETRIEVAL_OPT_IN_ENABLE_ENV,
            BIOCORTEX_RETRIEVAL_DISABLE_ENV,
        ]);
        std::env::set_var(BIOCORTEX_RETRIEVAL_OPT_IN_ENABLE_ENV, "1");
        std::env::remove_var(BIOCORTEX_RETRIEVAL_DISABLE_ENV);

        for mode in ["hybrid", "semantic"] {
            let audit =
                biocortex_retrieval_opt_in_audit_report(BioCortexRetrievalOptInAuditOptions {
                    mode: mode.to_string(),
                    per_call_opt_in: true,
                    baseline_keys: vec!["candidate".to_string()],
                    ..Default::default()
                });

            assert_eq!(audit["mode"], json!(mode));
            assert_eq!(audit["mode_authorized"], json!(false));
            assert_eq!(audit["affected_call_site"], Value::Null);
            assert_eq!(audit["fallback"]["baseline_returned"], json!(true));
            assert_eq!(audit["fallback"]["reason"], json!("mode_not_authorized"));
            assert_eq!(
                audit["store_contract"]["fallback_reason"],
                json!("mode_not_authorized")
            );
            assert_eq!(
                audit["store_contract"]["decision"]["mode_authorized"],
                json!(false)
            );
            assert_eq!(audit["changes_memory_search_order"], json!(false));
            assert_eq!(audit["ordering_behavior_connected"], json!(false));
            let unaffected_modes = audit["unaffected_modes"]
                .as_array()
                .expect("unaffected modes");
            assert!(unaffected_modes
                .iter()
                .any(|entry| entry.as_str() == Some(mode)));
        }
    }

    #[test]
    fn opt_in_dry_run_plan_is_readonly_and_baseline_only() {
        let _lock = ENV_LOCK.lock().expect("env lock");
        let _guard = EnvRestore::capture(&[
            BIOCORTEX_RETRIEVAL_OPT_IN_ENABLE_ENV,
            BIOCORTEX_RETRIEVAL_DISABLE_ENV,
        ]);
        std::env::set_var(BIOCORTEX_RETRIEVAL_OPT_IN_ENABLE_ENV, "1");
        std::env::remove_var(BIOCORTEX_RETRIEVAL_DISABLE_ENV);

        let plan = biocortex_retrieval_opt_in_dry_run_plan(BioCortexRetrievalOptInDryRunOptions {
            mode: "fts".to_string(),
            per_call_opt_in: true,
            query: Some("secret dry run query".to_string()),
            baseline_keys: vec!["secret_baseline_a".to_string()],
            baseline_completed: true,
            timeout_ms: 1234,
            coverage_threshold: 0.81234,
        });

        assert_eq!(
            plan["schema"],
            json!(BIOCORTEX_RETRIEVAL_OPT_IN_DRY_RUN_SCHEMA)
        );
        assert_eq!(plan["read_only"], json!(true));
        assert_eq!(plan["dry_run"], json!(true));
        assert_eq!(plan["calls_memory_search"], json!(false));
        assert_eq!(plan["runs_biocortex"], json!(false));
        assert_eq!(plan["changes_memory_search_order"], json!(false));
        assert_eq!(plan["baseline_order"]["key_count"], json!(1));
        assert_eq!(plan["baseline_order"]["raw_keys_included"], json!(false));
        assert_eq!(plan["baseline_order"]["content_included"], json!(false));
        assert_eq!(
            plan["planner_result"]["returned_order_source"],
            json!("baseline")
        );
        assert_eq!(
            plan["planned_side_signal"]["status"],
            json!("not_run_dry_run")
        );
        assert_eq!(plan["planned_side_signal"]["timeout_ms"], json!(1234));
        assert_eq!(
            plan["planned_side_signal"]["coverage_threshold"],
            json!(0.812)
        );
        assert_eq!(
            plan["store_contract"]["schema"],
            json!("agent_bridge.store.memory_search.biocortex_opt_in_contract.v0")
        );
        assert_eq!(
            plan["store_contract"]["returned_order_source"],
            json!("baseline")
        );
        assert_eq!(plan["store_contract"]["baseline_returned"], json!(true));
        assert_eq!(
            plan["store_contract"]["changes_memory_search_order"],
            json!(false)
        );

        if cfg!(feature = "biocortex-retrieval-opt-in") {
            assert_eq!(
                plan["planner_result"]["fallback_reason"],
                json!("ordering_behavior_not_connected")
            );
        } else {
            assert_eq!(
                plan["planner_result"]["fallback_reason"],
                json!("compile_feature_disabled")
            );
        }

        let serialized = serde_json::to_string(&plan).expect("plan json");
        assert!(!serialized.contains("secret dry run query"));
        assert!(!serialized.contains("secret_baseline_a"));
    }

    #[test]
    fn opt_in_dry_run_plan_rejects_non_fts_without_raw_keys() {
        let _lock = ENV_LOCK.lock().expect("env lock");
        let _guard = EnvRestore::capture(&[
            BIOCORTEX_RETRIEVAL_OPT_IN_ENABLE_ENV,
            BIOCORTEX_RETRIEVAL_DISABLE_ENV,
        ]);
        std::env::set_var(BIOCORTEX_RETRIEVAL_OPT_IN_ENABLE_ENV, "1");
        std::env::remove_var(BIOCORTEX_RETRIEVAL_DISABLE_ENV);

        let plan = biocortex_retrieval_opt_in_dry_run_plan(BioCortexRetrievalOptInDryRunOptions {
            mode: "semantic".to_string(),
            per_call_opt_in: true,
            query: Some("another secret query".to_string()),
            baseline_keys: vec!["secret_semantic_key".to_string()],
            ..Default::default()
        });

        assert_eq!(plan["mode"], json!("semantic"));
        assert_eq!(plan["mode_authorized"], json!(false));
        assert_eq!(
            plan["planner_result"]["fallback_reason"],
            json!("mode_not_authorized")
        );
        assert_eq!(
            plan["store_contract"]["decision"]["mode_authorized"],
            json!(false)
        );
        assert_eq!(plan["calls_memory_search"], json!(false));
        assert_eq!(plan["runs_biocortex"], json!(false));
        assert_eq!(plan["changes_memory_search_order"], json!(false));

        let serialized = serde_json::to_string(&plan).expect("plan json");
        assert!(!serialized.contains("another secret query"));
        assert!(!serialized.contains("secret_semantic_key"));
    }

    #[test]
    fn opt_in_review_packet_consumes_dry_run_without_approval() {
        let _lock = ENV_LOCK.lock().expect("env lock");
        let _guard = EnvRestore::capture(&[
            BIOCORTEX_RETRIEVAL_OPT_IN_ENABLE_ENV,
            BIOCORTEX_RETRIEVAL_DISABLE_ENV,
        ]);
        std::env::set_var(BIOCORTEX_RETRIEVAL_OPT_IN_ENABLE_ENV, "1");
        std::env::remove_var(BIOCORTEX_RETRIEVAL_DISABLE_ENV);

        let plan = biocortex_retrieval_opt_in_dry_run_plan(BioCortexRetrievalOptInDryRunOptions {
            mode: "fts".to_string(),
            per_call_opt_in: true,
            query: Some("review secret query".to_string()),
            baseline_keys: vec!["review_secret_key".to_string()],
            ..Default::default()
        });
        let packet =
            biocortex_retrieval_opt_in_review_packet(BioCortexRetrievalOptInReviewPacketOptions {
                dry_run_plan: plan,
                reviewer: Some("codex".to_string()),
                commit: Some("test-commit".to_string()),
                forum_post_id: Some("103".to_string()),
                memory_key: Some("memory-key".to_string()),
            });

        assert_eq!(
            packet["schema"],
            json!(BIOCORTEX_RETRIEVAL_OPT_IN_REVIEW_PACKET_SCHEMA)
        );
        assert_eq!(packet["read_only"], json!(true));
        assert_eq!(packet["dry_run_consumer"], json!(true));
        assert_eq!(packet["approval_state"], json!("not_approved"));
        assert_eq!(packet["runtime_adapter_approved"], json!(false));
        assert_eq!(packet["approval_writes_allowed"], json!(false));
        assert_eq!(packet["calls_memory_search"], json!(false));
        assert_eq!(packet["runs_biocortex"], json!(false));
        assert_eq!(packet["changes_memory_search_order"], json!(false));
        assert_eq!(packet["may_implement_ordering_now"], json!(false));
        assert_eq!(
            packet["input_contract"]["dry_run_plan_included"],
            json!(false)
        );
        assert_eq!(
            packet["dry_run_summary"]["baseline_order"]["key_count"],
            json!(1)
        );
        assert_eq!(
            packet["boundary_check"]["violations"]
                .as_array()
                .expect("violations")
                .len(),
            0
        );

        let serialized = serde_json::to_string(&packet).expect("packet json");
        assert!(!serialized.contains("review secret query"));
        assert!(!serialized.contains("review_secret_key"));
    }

    #[test]
    fn opt_in_review_packet_rejects_executing_or_raw_plan_without_echoing_it() {
        let packet =
            biocortex_retrieval_opt_in_review_packet(BioCortexRetrievalOptInReviewPacketOptions {
                dry_run_plan: json!({
                    "schema": BIOCORTEX_RETRIEVAL_OPT_IN_DRY_RUN_SCHEMA,
                    "read_only": true,
                    "dry_run": true,
                    "mode": "fts",
                    "mode_authorized": true,
                    "query": "do not echo raw query",
                    "baseline_keys": ["do_not_echo_key"],
                    "baseline_order": {
                        "key_count": 1,
                        "hash": "sha256:test",
                        "raw_keys_included": true,
                        "content_included": true
                    },
                    "planned_side_signal": {
                        "status": "ran",
                        "raw_included": true
                    },
                    "planner_result": {
                        "returned_order_source": "experimental",
                        "baseline_returned": false,
                        "fallback_reason": null,
                        "blocking_reasons": [],
                        "execution_ready": true
                    },
                    "calls_memory_search": true,
                    "runs_biocortex": true,
                    "registers_embedding_backend": true,
                    "changes_memory_search_order": true,
                    "default_search_order_change_allowed": true,
                    "ordering_behavior_connected": true,
                    "may_change_search_order_now": true
                }),
                ..Default::default()
            });

        assert_eq!(packet["boundary_check"]["review_ready"], json!(false));
        let violations = packet["boundary_check"]["violations"]
            .as_array()
            .expect("violations");
        assert!(violations.contains(&json!("calls_memory_search_true_or_missing")));
        assert!(violations.contains(&json!("runs_biocortex_true_or_missing")));
        assert!(violations.contains(&json!("baseline_raw_keys_included_or_missing")));
        assert!(violations.contains(&json!("returned_order_not_baseline")));
        assert_eq!(
            packet["input_contract"]["dry_run_plan_included"],
            json!(false)
        );
        assert_eq!(packet["approval_state"], json!("not_approved"));
        assert_eq!(packet["changes_memory_search_order"], json!(false));

        let serialized = serde_json::to_string(&packet).expect("packet json");
        assert!(!serialized.contains("do not echo raw query"));
        assert!(!serialized.contains("do_not_echo_key"));
    }

    #[test]
    fn opt_in_execution_packet_preflights_review_without_execution() {
        let _lock = ENV_LOCK.lock().expect("env lock");
        let _guard = EnvRestore::capture(&[
            BIOCORTEX_RETRIEVAL_OPT_IN_ENABLE_ENV,
            BIOCORTEX_RETRIEVAL_DISABLE_ENV,
        ]);
        std::env::set_var(BIOCORTEX_RETRIEVAL_OPT_IN_ENABLE_ENV, "1");
        std::env::remove_var(BIOCORTEX_RETRIEVAL_DISABLE_ENV);

        let plan = biocortex_retrieval_opt_in_dry_run_plan(BioCortexRetrievalOptInDryRunOptions {
            mode: "fts".to_string(),
            per_call_opt_in: true,
            query: Some("execution secret query".to_string()),
            baseline_keys: vec!["execution_secret_key".to_string()],
            ..Default::default()
        });
        let review =
            biocortex_retrieval_opt_in_review_packet(BioCortexRetrievalOptInReviewPacketOptions {
                dry_run_plan: plan,
                reviewer: Some("codex".to_string()),
                commit: Some("test-commit".to_string()),
                ..Default::default()
            });
        let packet = biocortex_retrieval_opt_in_execution_packet(
            BioCortexRetrievalOptInExecutionPacketOptions {
                review_packet: review,
                per_call_opt_in: true,
                attempt_id: Some("attempt-1".to_string()),
                commit: Some("test-commit".to_string()),
            },
        );

        assert_eq!(
            packet["schema"],
            json!(BIOCORTEX_RETRIEVAL_OPT_IN_EXECUTION_PACKET_SCHEMA)
        );
        assert_eq!(packet["read_only"], json!(true));
        assert_eq!(packet["execution_packet"], json!(true));
        assert_eq!(packet["approval_state"], json!("not_approved"));
        assert_eq!(packet["runtime_adapter_approved"], json!(false));
        assert_eq!(packet["calls_memory_search"], json!(false));
        assert_eq!(packet["runs_biocortex"], json!(false));
        assert_eq!(packet["changes_memory_search_order"], json!(false));
        assert_eq!(
            packet["execution_decision"]["baseline_returned"],
            json!(true)
        );
        assert_eq!(
            packet["execution_decision"]["returned_order_source"],
            json!("baseline")
        );
        assert_eq!(
            packet["preflight"]["preflight_passed_for_baseline_only_contract"],
            json!(true)
        );
        assert_eq!(packet["preflight"]["execution_allowed"], json!(false));
        assert_eq!(
            packet["preflight"]["packet_blockers"]
                .as_array()
                .expect("packet blockers")
                .len(),
            0
        );
        assert_eq!(
            packet["store_contract"]["returned_order_source"],
            json!("baseline")
        );
        assert_eq!(
            packet["store_contract"]["changes_memory_search_order"],
            json!(false)
        );

        let serialized = serde_json::to_string(&packet).expect("packet json");
        assert!(!serialized.contains("execution secret query"));
        assert!(!serialized.contains("execution_secret_key"));
    }

    #[test]
    fn opt_in_execution_packet_rejects_bad_review_without_echoing_raw_fields() {
        let packet = biocortex_retrieval_opt_in_execution_packet(
            BioCortexRetrievalOptInExecutionPacketOptions {
                review_packet: json!({
                    "schema": BIOCORTEX_RETRIEVAL_OPT_IN_REVIEW_PACKET_SCHEMA,
                    "read_only": true,
                    "dry_run_consumer": true,
                    "approval_state": "approved",
                    "query": "bad review raw query",
                    "baseline_keys": ["bad_review_raw_key"],
                    "review_target": {
                        "mode": "fts"
                    },
                    "input_contract": {
                        "dry_run_plan_included": true,
                        "raw_query_included": true,
                        "raw_keys_included": true,
                        "content_included": true
                    },
                    "boundary_check": {
                        "review_ready": false,
                        "violations": ["bad"]
                    },
                    "dry_run_summary": {
                        "baseline_order": {
                            "completed": true,
                            "key_count": 1,
                            "hash": "sha256:bad"
                        }
                    },
                    "calls_memory_search": true,
                    "runs_biocortex": true,
                    "changes_memory_search_order": true,
                    "ordering_behavior_connected": true
                }),
                per_call_opt_in: true,
                ..Default::default()
            },
        );

        assert_eq!(
            packet["preflight"]["preflight_passed_for_baseline_only_contract"],
            json!(false)
        );
        assert_eq!(packet["preflight"]["execution_allowed"], json!(false));
        let blockers = packet["preflight"]["packet_blockers"]
            .as_array()
            .expect("packet blockers");
        assert!(blockers.contains(&json!("review_packet_approval_state_changed")));
        assert!(blockers.contains(&json!("review_packet_not_ready")));
        assert!(blockers.contains(&json!("raw_query_included")));
        assert!(blockers.contains(&json!("review_packet_claims_memory_search")));
        assert_eq!(packet["approval_state"], json!("not_approved"));
        assert_eq!(packet["changes_memory_search_order"], json!(false));

        let serialized = serde_json::to_string(&packet).expect("packet json");
        assert!(!serialized.contains("bad review raw query"));
        assert!(!serialized.contains("bad_review_raw_key"));
    }

    #[tokio::test]
    async fn opt_in_runtime_trial_blocks_without_feature_and_sanitizes_inputs() {
        let _lock = ENV_LOCK.lock().expect("env lock");
        let _guard = EnvRestore::capture(&[
            BIOCORTEX_RETRIEVAL_OPT_IN_ENABLE_ENV,
            BIOCORTEX_RETRIEVAL_DISABLE_ENV,
        ]);
        std::env::set_var(BIOCORTEX_RETRIEVAL_OPT_IN_ENABLE_ENV, "1");
        std::env::remove_var(BIOCORTEX_RETRIEVAL_DISABLE_ENV);

        let plan = biocortex_retrieval_opt_in_dry_run_plan(BioCortexRetrievalOptInDryRunOptions {
            mode: "fts".to_string(),
            per_call_opt_in: true,
            query: Some("runtime trial dry-run secret query".to_string()),
            baseline_keys: vec!["runtime_trial_secret_key".to_string()],
            ..Default::default()
        });
        let review =
            biocortex_retrieval_opt_in_review_packet(BioCortexRetrievalOptInReviewPacketOptions {
                dry_run_plan: plan,
                reviewer: Some("codex".to_string()),
                commit: Some("test-commit".to_string()),
                ..Default::default()
            });
        let execution_packet = biocortex_retrieval_opt_in_execution_packet(
            BioCortexRetrievalOptInExecutionPacketOptions {
                review_packet: review,
                per_call_opt_in: true,
                attempt_id: Some("attempt-runtime".to_string()),
                commit: Some("test-commit".to_string()),
            },
        );
        let trial =
            biocortex_retrieval_opt_in_runtime_trial(BioCortexRetrievalOptInRuntimeTrialOptions {
                execution_packet,
                query: "runtime trial live secret query".to_string(),
                candidates: vec![BioCortexRetrievalCandidate {
                    key: "runtime_trial_secret_key".to_string(),
                    content: "runtime trial secret content".to_string(),
                }],
                expected_key: Some("runtime_trial_secret_key".to_string()),
                attempt_id: Some("trial-attempt".to_string()),
                commit: Some("test-commit".to_string()),
                ..Default::default()
            })
            .await;

        assert_eq!(
            trial["schema"],
            json!(BIOCORTEX_RETRIEVAL_OPT_IN_RUNTIME_TRIAL_SCHEMA)
        );
        assert_eq!(trial["read_only"], json!(true));
        assert_eq!(trial["runtime_trial"], json!(true));
        assert_eq!(trial["approval_state"], json!("not_approved"));
        assert_eq!(trial["runtime_adapter_approved"], json!(false));
        assert_eq!(trial["calls_memory_search"], json!(false));
        assert_eq!(trial["changes_memory_search_order"], json!(false));
        assert_eq!(trial["returned_order"]["source"], json!("baseline"));
        assert_eq!(trial["returned_order"]["baseline_returned"], json!(true));
        assert_eq!(trial["baseline_order"]["raw_keys_included"], json!(false));
        assert_eq!(trial["baseline_order"]["content_included"], json!(false));
        assert_eq!(trial["advisory_result"]["raw_keys_included"], json!(false));
        assert_eq!(trial["advisory_result"]["content_included"], json!(false));

        if cfg!(feature = "biocortex-retrieval-opt-in") {
            assert_eq!(
                trial["runtime_preflight"]["side_signal_trial_allowed"],
                json!(true)
            );
        } else {
            assert_eq!(
                trial["runtime_preflight"]["side_signal_trial_allowed"],
                json!(false)
            );
            assert_eq!(trial["side_signal"]["attempted"], json!(false));
            assert_eq!(trial["runs_biocortex"], json!(false));
            let blockers = trial["runtime_preflight"]["blockers"]
                .as_array()
                .expect("blockers");
            assert!(blockers.contains(&json!("opt_in_gate_not_ready")));
        }

        let serialized = serde_json::to_string(&trial).expect("trial json");
        assert!(!serialized.contains("runtime trial dry-run secret query"));
        assert!(!serialized.contains("runtime trial live secret query"));
        assert!(!serialized.contains("runtime_trial_secret_key"));
        assert!(!serialized.contains("runtime trial secret content"));
    }

    #[tokio::test]
    async fn opt_in_runtime_trial_rejects_bad_execution_packet_without_echoing_raw_fields() {
        let trial =
            biocortex_retrieval_opt_in_runtime_trial(BioCortexRetrievalOptInRuntimeTrialOptions {
                execution_packet: json!({
                    "schema": BIOCORTEX_RETRIEVAL_OPT_IN_EXECUTION_PACKET_SCHEMA,
                    "read_only": true,
                    "execution_packet": true,
                    "approval_state": "approved",
                    "runtime_adapter_approved": true,
                    "query": "bad execution raw query",
                    "candidate_keys": ["bad_execution_raw_key"],
                    "attempt": {
                        "mode": "fts",
                        "per_call_opt_in": true
                    },
                    "input_contract": {
                        "review_packet_included": true,
                        "raw_query_included": true,
                        "raw_keys_included": true,
                        "content_included": true
                    },
                    "review_summary": {
                        "baseline_order": {
                            "completed": true,
                            "key_count": 1
                        }
                    },
                    "preflight": {
                        "preflight_passed_for_baseline_only_contract": false,
                        "execution_allowed": true
                    },
                    "calls_memory_search": true,
                    "changes_memory_search_order": true,
                    "ordering_behavior_connected": true
                }),
                query: "bad runtime trial raw query".to_string(),
                candidates: vec![BioCortexRetrievalCandidate {
                    key: "bad_execution_raw_key".to_string(),
                    content: "bad runtime trial raw content".to_string(),
                }],
                ..Default::default()
            })
            .await;

        assert_eq!(
            trial["runtime_preflight"]["side_signal_trial_allowed"],
            json!(false)
        );
        let blockers = trial["runtime_preflight"]["blockers"]
            .as_array()
            .expect("blockers");
        assert!(blockers.contains(&json!("execution_packet_preflight_failed")));
        assert!(blockers.contains(&json!("execution_packet_allows_ordering_execution")));
        assert!(blockers.contains(&json!("execution_packet_approval_state_changed")));
        assert!(blockers.contains(&json!("raw_query_included")));
        assert!(blockers.contains(&json!("execution_packet_claims_memory_search")));
        assert_eq!(trial["side_signal"]["attempted"], json!(false));
        assert_eq!(trial["runs_biocortex"], json!(false));
        assert_eq!(trial["calls_memory_search"], json!(false));
        assert_eq!(trial["changes_memory_search_order"], json!(false));

        let serialized = serde_json::to_string(&trial).expect("trial json");
        assert!(!serialized.contains("bad execution raw query"));
        assert!(!serialized.contains("bad runtime trial raw query"));
        assert!(!serialized.contains("bad_execution_raw_key"));
        assert!(!serialized.contains("bad runtime trial raw content"));
    }

    #[test]
    fn opt_in_runtime_trial_review_packet_consumes_trial_without_approval() {
        let packet = biocortex_retrieval_opt_in_runtime_trial_review_packet(
            BioCortexRetrievalOptInRuntimeTrialReviewPacketOptions {
                runtime_trial: json!({
                    "schema": BIOCORTEX_RETRIEVAL_OPT_IN_RUNTIME_TRIAL_SCHEMA,
                    "read_only": true,
                    "runtime_trial": true,
                    "implementation_stage": "baseline_preserving_runtime_trial",
                    "approval_state": "not_approved",
                    "runtime_adapter_approved": false,
                    "approval_writes_allowed": false,
                    "writes_approval": false,
                    "query": "runtime trial review raw query",
                    "candidate_keys": ["runtime_trial_review_raw_key"],
                    "attempt": {
                        "mode": "fts",
                        "per_call_opt_in": true,
                        "attempt_id": "trial-attempt",
                        "commit": "trial-commit"
                    },
                    "input_contract": {
                        "execution_packet_included": false,
                        "raw_query_included": false,
                        "raw_keys_included": false,
                        "content_included": false
                    },
                    "query_hash": "sha256:query",
                    "baseline_order": {
                        "completed": true,
                        "key_count": 1,
                        "hash": "sha256:baseline",
                        "top_key_hash": "sha256:top",
                        "raw_keys_included": false,
                        "content_included": false
                    },
                    "runtime_preflight": {
                        "side_signal_trial_allowed": true,
                        "blockers": [],
                        "execution_packet_preflight_passed": true,
                        "gate_ready": true,
                        "candidate_count_matches_packet": true,
                        "ordering_execution_allowed": false
                    },
                    "side_signal": {
                        "attempted": true,
                        "status": "ok",
                        "timeout_ms": 30000,
                        "coverage_threshold": 0.5,
                        "row_count": 1,
                        "matched_candidate_count": 1,
                        "coverage": 1.0,
                        "latency_ms": 12.345,
                        "raw_included": false,
                        "candidate_keys_included": false,
                        "content_included": false
                    },
                    "advisory_result": {
                        "available": true,
                        "used_for_return_order": false,
                        "order_hash": "sha256:advisory",
                        "top_key_hash": "sha256:advisory-top",
                        "matched_side_signal_count": 1,
                        "evidence_count": 1,
                        "expected": {
                            "key_hash": "sha256:expected",
                            "baseline_rank": 1,
                            "advisory_rank": 1,
                            "regressed": false
                        },
                        "raw_keys_included": false,
                        "content_included": false,
                        "side_signal_raw_included": false
                    },
                    "returned_order": {
                        "source": "baseline",
                        "baseline_returned": true,
                        "hash_matches_baseline": true,
                        "fallback_reason": "ordering_behavior_not_connected"
                    },
                    "calls_memory_search": false,
                    "runs_biocortex": true,
                    "registers_embedding_backend": false,
                    "changes_memory_search_order": false,
                    "default_search_order_change_allowed": false,
                    "ordering_behavior_connected": false,
                    "may_change_search_order_now": false,
                    "may_implement_ordering_now": false,
                    "boundary": {
                        "calls_memory_search": false,
                        "changes_memory_search_order": false,
                        "mutates_ab_memory": false
                    }
                }),
                reviewer: Some("codex".to_string()),
                commit: Some("review-commit".to_string()),
                forum_post_id: Some("103".to_string()),
                memory_key: Some("memory-key".to_string()),
            },
        );

        assert_eq!(
            packet["schema"],
            json!(BIOCORTEX_RETRIEVAL_OPT_IN_RUNTIME_TRIAL_REVIEW_PACKET_SCHEMA)
        );
        assert_eq!(packet["read_only"], json!(true));
        assert_eq!(packet["runtime_trial_consumer"], json!(true));
        assert_eq!(packet["approval_state"], json!("not_approved"));
        assert_eq!(packet["runtime_adapter_approved"], json!(false));
        assert_eq!(packet["calls_memory_search"], json!(false));
        assert_eq!(packet["runs_biocortex"], json!(false));
        assert_eq!(packet["changes_memory_search_order"], json!(false));
        assert_eq!(packet["may_implement_ordering_now"], json!(false));
        assert_eq!(
            packet["input_contract"]["runtime_trial_packet_included"],
            json!(false)
        );
        assert_eq!(
            packet["boundary_check"]["review_ready_for_baseline_runtime_trial"],
            json!(true)
        );
        assert_eq!(
            packet["boundary_check"]["violations"]
                .as_array()
                .expect("violations")
                .len(),
            0
        );
        assert_eq!(
            packet["runtime_trial_summary"]["side_signal"]["status"],
            json!("ok")
        );
        assert_eq!(
            packet["runtime_trial_summary"]["returned_order"]["source"],
            json!("baseline")
        );

        let serialized = serde_json::to_string(&packet).expect("packet json");
        assert!(!serialized.contains("runtime trial review raw query"));
        assert!(!serialized.contains("runtime_trial_review_raw_key"));
    }

    #[test]
    fn opt_in_runtime_trial_review_packet_reports_violations_without_echoing_raw_fields() {
        let packet = biocortex_retrieval_opt_in_runtime_trial_review_packet(
            BioCortexRetrievalOptInRuntimeTrialReviewPacketOptions {
                runtime_trial: json!({
                    "schema": BIOCORTEX_RETRIEVAL_OPT_IN_RUNTIME_TRIAL_SCHEMA,
                    "read_only": true,
                    "runtime_trial": true,
                    "implementation_stage": "baseline_preserving_runtime_trial",
                    "approval_state": "approved",
                    "runtime_adapter_approved": true,
                    "query": "bad runtime trial review raw query",
                    "candidate_keys": ["bad_runtime_trial_review_raw_key"],
                    "input_contract": {
                        "execution_packet_included": true,
                        "raw_query_included": true,
                        "raw_keys_included": true,
                        "content_included": true
                    },
                    "baseline_order": {
                        "raw_keys_included": true,
                        "content_included": true
                    },
                    "runtime_preflight": {
                        "side_signal_trial_allowed": false,
                        "blockers": ["bad"]
                    },
                    "side_signal": {
                        "attempted": false,
                        "status": "not_run",
                        "raw_included": true,
                        "candidate_keys_included": true,
                        "content_included": true
                    },
                    "advisory_result": {
                        "used_for_return_order": true,
                        "raw_keys_included": true,
                        "content_included": true,
                        "side_signal_raw_included": true
                    },
                    "returned_order": {
                        "source": "experimental",
                        "baseline_returned": false,
                        "hash_matches_baseline": false
                    },
                    "calls_memory_search": true,
                    "registers_embedding_backend": true,
                    "changes_memory_search_order": true,
                    "default_search_order_change_allowed": true,
                    "ordering_behavior_connected": true,
                    "may_change_search_order_now": true,
                    "may_implement_ordering_now": true,
                    "approval_writes_allowed": true,
                    "writes_approval": true,
                    "boundary": {
                        "calls_memory_search": true,
                        "changes_memory_search_order": true,
                        "mutates_ab_memory": true
                    }
                }),
                ..Default::default()
            },
        );

        assert_eq!(
            packet["boundary_check"]["review_ready_for_baseline_runtime_trial"],
            json!(false)
        );
        let violations = packet["boundary_check"]["violations"]
            .as_array()
            .expect("violations");
        assert!(violations.contains(&json!("runtime_trial_packet_included")));
        assert!(violations.contains(&json!("input_raw_query_included")));
        assert!(violations.contains(&json!("side_signal_raw_included")));
        assert!(violations.contains(&json!("returned_order_not_baseline")));
        assert!(violations.contains(&json!("calls_memory_search_true_or_missing")));
        assert!(violations.contains(&json!("runtime_adapter_approved")));
        assert_eq!(packet["approval_state"], json!("not_approved"));
        assert_eq!(packet["runs_biocortex"], json!(false));
        assert_eq!(packet["changes_memory_search_order"], json!(false));

        let serialized = serde_json::to_string(&packet).expect("packet json");
        assert!(!serialized.contains("bad runtime trial review raw query"));
        assert!(!serialized.contains("bad_runtime_trial_review_raw_key"));
    }

    #[test]
    fn opt_in_order_diff_packet_compares_hashes_without_approval() {
        let packet = biocortex_retrieval_opt_in_order_diff_packet(
            BioCortexRetrievalOptInOrderDiffPacketOptions {
                source_packet: json!({
                    "schema": BIOCORTEX_RETRIEVAL_OPT_IN_RUNTIME_TRIAL_SCHEMA,
                    "read_only": true,
                    "runtime_trial": true,
                    "implementation_stage": "baseline_preserving_runtime_trial",
                    "approval_state": "not_approved",
                    "runtime_adapter_approved": false,
                    "approval_writes_allowed": false,
                    "writes_approval": false,
                    "query": "order diff secret query",
                    "candidate_keys": ["order_diff_secret_key"],
                    "candidate_content": "order diff secret content",
                    "input_contract": {
                        "execution_packet_included": false,
                        "raw_query_included": false,
                        "raw_keys_included": false,
                        "content_included": false
                    },
                    "baseline_order": {
                        "key_count": 3,
                        "hash": "sha256:baseline-order",
                        "top_key_hash": "sha256:baseline-top",
                        "raw_keys_included": false,
                        "content_included": false
                    },
                    "runtime_preflight": {
                        "side_signal_trial_allowed": true,
                        "blockers": [],
                        "ordering_execution_allowed": false
                    },
                    "side_signal": {
                        "attempted": true,
                        "status": "ok",
                        "matched_candidate_count": 3,
                        "raw_included": false,
                        "candidate_keys_included": false,
                        "content_included": false
                    },
                    "advisory_result": {
                        "available": true,
                        "used_for_return_order": false,
                        "order_hash": "sha256:advisory-order",
                        "top_key_hash": "sha256:advisory-top",
                        "matched_side_signal_count": 3,
                        "evidence_count": 2,
                        "expected": {
                            "key_hash": "sha256:expected",
                            "baseline_rank": 3,
                            "advisory_rank": 1,
                            "regressed": false
                        },
                        "raw_keys_included": false,
                        "content_included": false,
                        "side_signal_raw_included": false
                    },
                    "returned_order": {
                        "source": "baseline",
                        "baseline_returned": true,
                        "hash_matches_baseline": true
                    },
                    "calls_memory_search": false,
                    "runs_biocortex": true,
                    "registers_embedding_backend": false,
                    "changes_memory_search_order": false,
                    "default_search_order_change_allowed": false,
                    "ordering_behavior_connected": false,
                    "may_change_search_order_now": false,
                    "may_implement_ordering_now": false
                }),
                reviewer: Some("codex".to_string()),
                commit: Some("order-diff-commit".to_string()),
                forum_post_id: Some("103".to_string()),
                memory_key: Some("order-diff-memory".to_string()),
            },
        );

        assert_eq!(
            packet["schema"],
            json!(BIOCORTEX_RETRIEVAL_OPT_IN_ORDER_DIFF_PACKET_SCHEMA)
        );
        assert_eq!(packet["read_only"], json!(true));
        assert_eq!(packet["order_diff_packet"], json!(true));
        assert_eq!(packet["source_packet_consumer"], json!(true));
        assert_eq!(packet["approval_state"], json!("not_approved"));
        assert_eq!(packet["runtime_adapter_approved"], json!(false));
        assert_eq!(packet["calls_memory_search"], json!(false));
        assert_eq!(packet["runs_biocortex"], json!(false));
        assert_eq!(packet["changes_memory_search_order"], json!(false));
        assert_eq!(packet["may_implement_ordering_now"], json!(false));
        assert_eq!(
            packet["review_target"]["source_kind"],
            json!("runtime_trial")
        );
        assert_eq!(packet["boundary_check"]["diff_ready"], json!(true));
        assert_eq!(
            packet["boundary_check"]["violations"]
                .as_array()
                .expect("violations")
                .len(),
            0
        );
        assert_eq!(
            packet["order_comparison"]["hash_diff"]["order_hash_changed"],
            json!(true)
        );
        assert_eq!(
            packet["order_comparison"]["hash_diff"]["top_key_changed"],
            json!(true)
        );
        assert_eq!(
            packet["order_comparison"]["expected_key_rank"]["rank_delta_advisory_minus_baseline"],
            json!(-2)
        );
        assert_eq!(
            packet["order_comparison"]["expected_key_rank"]["direction"],
            json!("improved")
        );
        assert_eq!(
            packet["order_comparison"]["returned_order"]["actual_return_order_changed"],
            json!(false)
        );
        assert_eq!(
            packet["source_execution_summary"]["source_runs_biocortex"],
            json!(true)
        );
        assert_eq!(
            packet["source_execution_summary"]["order_diff_packet_runs_biocortex"],
            json!(false)
        );
        assert_eq!(
            packet["order_comparison"]["unavailable_metrics"]["top_k_overlap"],
            json!("not_computed_no_raw_order_keys")
        );

        let serialized = serde_json::to_string(&packet).expect("packet json");
        assert!(!serialized.contains("order diff secret query"));
        assert!(!serialized.contains("order_diff_secret_key"));
        assert!(!serialized.contains("order diff secret content"));
    }

    #[test]
    fn opt_in_order_diff_packet_reports_violations_without_echoing_raw_fields() {
        let packet = biocortex_retrieval_opt_in_order_diff_packet(
            BioCortexRetrievalOptInOrderDiffPacketOptions {
                source_packet: json!({
                    "schema": BIOCORTEX_RETRIEVAL_OPT_IN_RUNTIME_TRIAL_SCHEMA,
                    "read_only": true,
                    "runtime_trial": true,
                    "approval_state": "approved",
                    "runtime_adapter_approved": true,
                    "approval_writes_allowed": true,
                    "writes_approval": true,
                    "query": "bad order diff secret query",
                    "candidate_keys": ["bad_order_diff_secret_key"],
                    "candidate_content": "bad order diff secret content",
                    "input_contract": {
                        "execution_packet_included": true,
                        "raw_query_included": true,
                        "raw_keys_included": true,
                        "content_included": true,
                        "side_signal_raw_included": true
                    },
                    "baseline_order": {
                        "raw_keys_included": true,
                        "content_included": true
                    },
                    "runtime_preflight": {
                        "side_signal_trial_allowed": false,
                        "ordering_execution_allowed": true
                    },
                    "side_signal": {
                        "attempted": false,
                        "status": "not_run",
                        "raw_included": true,
                        "candidate_keys_included": true,
                        "content_included": true
                    },
                    "advisory_result": {
                        "available": false,
                        "used_for_return_order": true,
                        "raw_keys_included": true,
                        "content_included": true,
                        "side_signal_raw_included": true
                    },
                    "returned_order": {
                        "source": "experimental",
                        "baseline_returned": false,
                        "hash_matches_baseline": false
                    },
                    "calls_memory_search": true,
                    "runs_biocortex": true,
                    "registers_embedding_backend": true,
                    "changes_memory_search_order": true,
                    "default_search_order_change_allowed": true,
                    "ordering_behavior_connected": true,
                    "may_change_search_order_now": true,
                    "may_implement_ordering_now": true
                }),
                ..Default::default()
            },
        );

        assert_eq!(packet["boundary_check"]["diff_ready"], json!(false));
        let violations = packet["boundary_check"]["violations"]
            .as_array()
            .expect("violations");
        assert!(violations.contains(&json!("source_packet_included")));
        assert!(violations.contains(&json!("input_raw_query_included")));
        assert!(violations.contains(&json!("advisory_order_unavailable")));
        assert!(violations.contains(&json!("advisory_used_for_return_order")));
        assert!(violations.contains(&json!("returned_order_not_baseline")));
        assert!(violations.contains(&json!("calls_memory_search_true_or_missing")));
        assert!(violations.contains(&json!("approval_state_changed")));
        assert_eq!(packet["approval_state"], json!("not_approved"));
        assert_eq!(packet["runtime_adapter_approved"], json!(false));
        assert_eq!(packet["runs_biocortex"], json!(false));
        assert_eq!(packet["changes_memory_search_order"], json!(false));
        assert_eq!(packet["may_implement_ordering_now"], json!(false));

        let serialized = serde_json::to_string(&packet).expect("packet json");
        assert!(!serialized.contains("bad order diff secret query"));
        assert!(!serialized.contains("bad_order_diff_secret_key"));
        assert!(!serialized.contains("bad order diff secret content"));
    }

    #[test]
    fn opt_in_redacted_order_artifact_computes_overlap_and_movements_without_approval() {
        let key_a = candidate_key_hash("redacted_order_a");
        let key_b = candidate_key_hash("redacted_order_b");
        let key_c = candidate_key_hash("redacted_order_c");
        let packet = biocortex_retrieval_opt_in_redacted_order_artifact(
            BioCortexRetrievalOptInRedactedOrderArtifactOptions {
                source_packet: json!({
                    "schema": BIOCORTEX_RETRIEVAL_OPT_IN_RUNTIME_TRIAL_REVIEW_PACKET_SCHEMA,
                    "read_only": true,
                    "runtime_trial_consumer": true,
                    "implementation_stage": "runtime_trial_review_packet_only",
                    "approval_state": "not_approved",
                    "runtime_adapter_approved": false,
                    "approval_writes_allowed": false,
                    "writes_approval": false,
                    "query": "redacted artifact secret query",
                    "candidate_keys": ["redacted_artifact_secret_key"],
                    "candidate_content": "redacted artifact secret content",
                    "input_contract": {
                        "runtime_trial_packet_included": false,
                        "raw_query_included": false,
                        "raw_keys_included": false,
                        "content_included": false,
                        "side_signal_raw_included": false
                    },
                    "runtime_trial_summary": {
                        "baseline_order": {
                            "key_count": 3,
                            "hash": "sha256:baseline",
                            "top_key_hash": key_a,
                            "redacted_rank_rows": [
                                {"key_hash": key_a, "baseline_rank": 1},
                                {"key_hash": key_b, "baseline_rank": 2},
                                {"key_hash": key_c, "baseline_rank": 3}
                            ],
                            "redacted_rank_rows_included": true,
                            "raw_keys_included": false,
                            "raw_order_keys_included": false,
                            "content_included": false
                        },
                        "side_signal": {
                            "status": "ok",
                            "matched_candidate_count": 3,
                            "raw_included": false,
                            "candidate_keys_included": false,
                            "content_included": false
                        },
                        "advisory_result": {
                            "available": true,
                            "used_for_return_order": false,
                            "order_hash": "sha256:advisory",
                            "top_key_hash": key_b,
                            "matched_side_signal_count": 3,
                            "evidence_count": 2,
                            "redacted_rank_rows": [
                                {"key_hash": key_b, "advisory_rank": 1},
                                {"key_hash": key_a, "advisory_rank": 2},
                                {"key_hash": key_c, "advisory_rank": 3}
                            ],
                            "redacted_rank_rows_included": true,
                            "raw_keys_included": false,
                            "raw_order_keys_included": false,
                            "content_included": false,
                            "side_signal_raw_included": false
                        },
                        "returned_order": {
                            "source": "baseline",
                            "baseline_returned": true,
                            "hash_matches_baseline": true
                        }
                    },
                    "boundary_check": {
                        "review_ready_for_baseline_runtime_trial": true,
                        "violations": []
                    },
                    "calls_memory_search": false,
                    "runs_biocortex": false,
                    "registers_embedding_backend": false,
                    "changes_memory_search_order": false,
                    "default_search_order_change_allowed": false,
                    "ordering_behavior_connected": false,
                    "may_change_search_order_now": false,
                    "may_implement_ordering_now": false
                }),
                reviewer: Some("codex".to_string()),
                commit: Some("redacted-order-commit".to_string()),
                forum_post_id: Some("103".to_string()),
                memory_key: Some("redacted-order-memory".to_string()),
            },
        );

        assert_eq!(
            packet["schema"],
            json!(BIOCORTEX_RETRIEVAL_OPT_IN_REDACTED_ORDER_ARTIFACT_SCHEMA)
        );
        assert_eq!(packet["read_only"], json!(true));
        assert_eq!(packet["redacted_order_artifact"], json!(true));
        assert_eq!(packet["source_packet_consumer"], json!(true));
        assert_eq!(packet["approval_state"], json!("not_approved"));
        assert_eq!(packet["runtime_adapter_approved"], json!(false));
        assert_eq!(packet["calls_memory_search"], json!(false));
        assert_eq!(packet["runs_biocortex"], json!(false));
        assert_eq!(packet["changes_memory_search_order"], json!(false));
        assert_eq!(packet["may_implement_ordering_now"], json!(false));
        assert_eq!(packet["boundary_check"]["artifact_ready"], json!(true));
        assert_eq!(
            packet["boundary_check"]["redacted_rows_comparable"],
            json!(true)
        );

        let overlap = packet["redacted_order_comparison"]["top_k_overlap"]
            .as_array()
            .expect("overlap rows");
        assert_eq!(overlap[0]["k"], json!(1));
        assert_eq!(overlap[0]["overlap_count"], json!(0));
        assert_eq!(overlap[0]["jaccard"], json!(0.0));
        assert_eq!(overlap[1]["k"], json!(3));
        assert_eq!(overlap[1]["overlap_count"], json!(3));
        assert_eq!(overlap[1]["jaccard"], json!(1.0));
        assert_eq!(
            packet["redacted_order_comparison"]["rank_delta_distribution"]["improved_count"],
            json!(1)
        );
        assert_eq!(
            packet["redacted_order_comparison"]["rank_delta_distribution"]["regressed_count"],
            json!(1)
        );
        assert_eq!(
            packet["redacted_order_comparison"]["rank_delta_distribution"]["unchanged_count"],
            json!(1)
        );
        assert_eq!(
            packet["redacted_order_comparison"]["rank_delta_distribution"]["max_abs_delta"],
            json!(1)
        );
        assert_eq!(
            packet["redacted_order_comparison"]["per_key_movements"][0]["direction"],
            json!("regressed")
        );
        assert_eq!(
            packet["redacted_order_comparison"]["per_key_movements"][1]["direction"],
            json!("improved")
        );
        assert_eq!(
            packet["redacted_order_comparison"]["returned_order"]["actual_return_order_changed"],
            json!(false)
        );

        let serialized = serde_json::to_string(&packet).expect("packet json");
        assert!(!serialized.contains("redacted artifact secret query"));
        assert!(!serialized.contains("redacted_artifact_secret_key"));
        assert!(!serialized.contains("redacted artifact secret content"));
    }

    #[test]
    fn opt_in_redacted_order_artifact_reports_violations_without_echoing_raw_fields() {
        let packet = biocortex_retrieval_opt_in_redacted_order_artifact(
            BioCortexRetrievalOptInRedactedOrderArtifactOptions {
                source_packet: json!({
                    "schema": BIOCORTEX_RETRIEVAL_OPT_IN_RUNTIME_TRIAL_SCHEMA,
                    "read_only": true,
                    "runtime_trial": true,
                    "approval_state": "approved",
                    "runtime_adapter_approved": true,
                    "approval_writes_allowed": true,
                    "writes_approval": true,
                    "query": "bad redacted artifact secret query",
                    "candidate_keys": ["bad_redacted_artifact_secret_key"],
                    "candidate_content": "bad redacted artifact secret content",
                    "input_contract": {
                        "execution_packet_included": true,
                        "raw_query_included": true,
                        "raw_keys_included": true,
                        "content_included": true,
                        "side_signal_raw_included": true
                    },
                    "baseline_order": {
                        "redacted_rank_rows": [
                            {
                                "key_hash": "not-a-safe-hash",
                                "baseline_rank": 1,
                                "key": "bad_redacted_artifact_secret_key"
                            }
                        ],
                        "raw_keys_included": true,
                        "raw_order_keys_included": true,
                        "content_included": true
                    },
                    "runtime_preflight": {
                        "side_signal_trial_allowed": false,
                        "ordering_execution_allowed": true
                    },
                    "side_signal": {
                        "attempted": false,
                        "status": "not_run",
                        "raw_included": true,
                        "candidate_keys_included": true,
                        "content_included": true
                    },
                    "advisory_result": {
                        "available": false,
                        "used_for_return_order": true,
                        "redacted_rank_rows": [
                            {
                                "key_hash": "not-a-safe-hash",
                                "advisory_rank": 1,
                                "key": "bad_redacted_artifact_secret_key"
                            }
                        ],
                        "raw_keys_included": true,
                        "raw_order_keys_included": true,
                        "content_included": true,
                        "side_signal_raw_included": true
                    },
                    "returned_order": {
                        "source": "experimental",
                        "baseline_returned": false,
                        "hash_matches_baseline": false
                    },
                    "calls_memory_search": true,
                    "runs_biocortex": true,
                    "registers_embedding_backend": true,
                    "changes_memory_search_order": true,
                    "default_search_order_change_allowed": true,
                    "ordering_behavior_connected": true,
                    "may_change_search_order_now": true,
                    "may_implement_ordering_now": true
                }),
                ..Default::default()
            },
        );

        assert_eq!(packet["boundary_check"]["artifact_ready"], json!(false));
        let violations = packet["boundary_check"]["violations"]
            .as_array()
            .expect("violations");
        assert!(violations.contains(&json!("source_packet_included")));
        assert!(violations.contains(&json!("input_raw_query_included")));
        assert!(violations.contains(&json!("baseline_raw_order_keys_included")));
        assert!(violations.contains(&json!("advisory_order_unavailable")));
        assert!(violations.contains(&json!("advisory_used_for_return_order")));
        assert!(violations.contains(&json!("returned_order_not_baseline")));
        assert!(violations.contains(&json!("calls_memory_search_true_or_missing")));
        assert!(violations.contains(&json!("approval_state_changed")));
        assert!(violations.contains(&json!("baseline_redacted_rank_rows_missing")));
        assert!(violations.contains(&json!("advisory_redacted_rank_rows_missing")));
        assert_eq!(packet["approval_state"], json!("not_approved"));
        assert_eq!(packet["runtime_adapter_approved"], json!(false));
        assert_eq!(packet["runs_biocortex"], json!(false));
        assert_eq!(packet["changes_memory_search_order"], json!(false));
        assert_eq!(packet["may_implement_ordering_now"], json!(false));

        let serialized = serde_json::to_string(&packet).expect("packet json");
        assert!(!serialized.contains("bad redacted artifact secret query"));
        assert!(!serialized.contains("bad_redacted_artifact_secret_key"));
        assert!(!serialized.contains("bad redacted artifact secret content"));
    }

    fn opt_in_authorization_decision_fixture() -> Value {
        json!({
            "schema": "agent_bridge.biocortex_retrieval.opt_in_authorization_decision.v0",
            "decision": "authorized",
            "authorization_state": "authorized",
            "authorized_scope": "opt_in_experiment",
            "human_decision_text": "secret human authorization wording",
            "implementation_allowed": true,
            "runtime_adapter_approved": false,
            "default_search_order_change_allowed": false,
            "default_retrieval_influence_authorized": false,
            "hybrid_retrieval_influence_authorized": false,
            "semantic_retrieval_influence_authorized": false,
            "authorized_implementation": {
                "may_add_runtime_enable_env": BIOCORTEX_RETRIEVAL_OPT_IN_ENABLE_ENV,
                "may_add_per_call_opt_in_surface": true,
                "may_affect_only_explicitly_opted_in_fts_calls": true,
                "must_keep_operator_disable": BIOCORTEX_RETRIEVAL_DISABLE_ENV,
                "must_return_baseline_without_per_call_opt_in": true,
                "must_return_baseline_on_absent_error_timeout_low_coverage_malformed_rows": true
            },
            "not_authorized": [
                "runtime_adapter_approved",
                "default_search_order_change_allowed",
                "production_use_without_post_implementation_review"
            ],
            "requires_post_implementation_review_before_use": true,
            "raw_query": "secret decision raw query",
            "raw_key": "secret_decision_key"
        })
    }

    fn opt_in_authorization_request_fixture() -> Value {
        json!({
            "schema": "agent_bridge.biocortex_retrieval.opt_in_authorization_request.v0",
            "status": "request_prepared",
            "approval_state": "opt_in_implementation_authorized",
            "authorization_state": "authorized_for_opt_in_implementation",
            "request_scope": "opt_in_experiment",
            "implementation_allowed": true,
            "runtime_adapter_approved": false,
            "default_search_order_change_allowed": false,
            "writes_approval": false,
            "current_permissions": {
                "may_implement_opt_in_experiment": true,
                "may_change_default_retrieval_order": false
            },
            "opt_in_plan": {
                "status": "store_opt_in_search_wrapper_implemented"
            },
            "not_requested": [
                "runtime_adapter_approved",
                "default_search_order_change_allowed"
            ],
            "raw_query": "secret request raw query",
            "raw_key": "secret_request_key",
            "content": "secret request content"
        })
    }

    fn opt_in_post_implementation_review_plan_fixture() -> Value {
        json!({
            "schema": "agent_bridge.biocortex_retrieval.opt_in_experiment_plan.v0",
            "status": "post_implementation_review_gate_implemented",
            "approval_state": "opt_in_implementation_authorized",
            "runtime_adapter_approved": false,
            "default_search_order_change_allowed": false,
            "implementation_allowed": true,
            "store_opt_in_search_wrapper_implemented": true,
            "authorization_decision_consumer_implemented": true,
            "post_implementation_review_gate_implemented": true,
            "ordering_behavior_connected": false,
            "requested_default_influence_scope": "none",
            "default_memory_search_unchanged": true,
            "implemented_store_opt_in_search_wrapper": {
                "returns_baseline_order": true,
                "redacted_audit_only": true,
                "runs_biocortex": false,
                "changes_memory_search_order": false,
                "ordering_behavior_connected": false
            },
            "implemented_post_implementation_review_gate": {
                "cli": "agent-bridge bio-cortex retrieval-opt-in-post-implementation-review-gate",
                "mcp_tool": "biocortex_retrieval_opt_in_post_implementation_review_gate",
                "schema": BIOCORTEX_RETRIEVAL_OPT_IN_POST_IMPLEMENTATION_REVIEW_GATE_SCHEMA,
                "read_only": true,
                "post_implementation_review_gate": true,
                "runtime_adapter_approved": false,
                "default_search_order_change_allowed": false,
                "calls_memory_search": false,
                "runs_biocortex": false,
                "registers_embedding_backend": false,
                "changes_memory_search_order": false,
                "ordering_behavior_connected": false,
                "may_change_search_order_now": false,
                "may_implement_ordering_now": false
            },
            "raw_query": "secret plan raw query",
            "raw_key": "secret_plan_key",
            "content": "secret plan content"
        })
    }

    fn opt_in_runtime_influence_redacted_artifact_fixture() -> Value {
        json!({
            "schema": BIOCORTEX_RETRIEVAL_OPT_IN_REDACTED_ORDER_ARTIFACT_SCHEMA,
            "read_only": true,
            "implementation_stage": "redacted_order_artifact_only",
            "input_contract": {
                "source_packet_included": false,
                "raw_query_included": false,
                "raw_keys_included": false,
                "content_included": false
            },
            "redacted_order_comparison": {
                "top_k_overlap": [
                    {"k": 1, "overlap_count": 1, "jaccard": 1.0}
                ],
                "rank_delta_distribution": {
                    "improved_count": 0,
                    "regressed_count": 0,
                    "unchanged_count": 1,
                    "max_abs_delta": 0
                },
                "returned_order": {
                    "baseline_returned": true,
                    "actual_return_order_changed": false
                }
            },
            "boundary_check": {
                "artifact_ready": true,
                "violations": [],
                "redacted_rows_comparable": true,
                "baseline_rows_present": true,
                "advisory_rows_present": true
            },
            "approval_state": "not_approved",
            "runtime_adapter_approved": false,
            "approval_writes_allowed": false,
            "writes_approval": false,
            "calls_memory_search": false,
            "runs_biocortex": false,
            "registers_embedding_backend": false,
            "changes_memory_search_order": false,
            "actual_return_order_changed": false,
            "default_search_order_change_allowed": false,
            "ordering_behavior_connected": false,
            "may_change_search_order_now": false,
            "may_implement_ordering_now": false,
            "raw_query": "secret artifact raw query",
            "raw_key": "secret_artifact_key",
            "content": "secret artifact content"
        })
    }

    fn opt_in_redacted_evidence_aggregate_fixture() -> Value {
        json!({
            "schema": BIOCORTEX_RETRIEVAL_OPT_IN_REDACTED_EVIDENCE_AGGREGATE_SCHEMA,
            "read_only": true,
            "redacted_evidence_aggregate": true,
            "implementation_stage": "post_runtime_redacted_evidence_aggregate",
            "input_contract": {
                "movement_fixture_run_included": false,
                "coverage_fixture_run_included": false,
                "raw_queries_included": false,
                "raw_keys_included": false,
                "content_included": false,
                "side_signal_raw_included": false
            },
            "movement_evidence": {
                "raw_flags_all_false": true,
                "movement_observed": true
            },
            "coverage_evidence": {
                "raw_flags_all_false": true,
                "expanded_coverage_observed": true
            },
            "interpretation": {
                "aggregate_evidence_ready": true,
                "controlled_rank_movement_observed": true,
                "expanded_coverage_without_additional_movement": true,
                "default_influence_ready": false,
                "human_review_required": true,
                "review_state": "redacted_aggregate_ready"
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
            "raw_queries_included": false,
            "raw_keys_included": false,
            "content_included": false,
            "side_signal_raw_included": false,
            "raw_query": "secret aggregate raw query",
            "raw_key": "secret_aggregate_key",
            "content": "secret aggregate content"
        })
    }

    fn opt_in_gated_readiness_evidence_summary_fixture() -> Value {
        json!({
            "schema": BIOCORTEX_RETRIEVAL_OPT_IN_EVIDENCE_SUMMARY_SCHEMA,
            "read_only": true,
            "evidence_summary": true,
            "implementation_stage": "post_runtime_evidence_summary",
            "input_contract": {
                "batch_diagnostics_schema": BIOCORTEX_RETRIEVAL_OPT_IN_GATED_BATCH_DIAGNOSTICS_SCHEMA,
                "batch_diagnostics_evidence_source": "runtime_transition_gated_batch_diagnostics",
                "batch_diagnostics_transition_gated": true,
                "runtime_readiness_packet_schema": BIOCORTEX_RETRIEVAL_OPT_IN_RUNTIME_READINESS_PACKET_SCHEMA,
                "batch_diagnostics_included": false,
                "controlled_order_fixture_run_included": false,
                "runtime_readiness_packet_included": false,
                "runtime_readiness_packet_provided": true,
                "raw_queries_included": false,
                "raw_keys_included": false,
                "content_included": false,
                "side_signal_raw_included": false
            },
            "batch_diagnostics": {
                "schema_ok": true,
                "gated_schema_ok": true,
                "evidence_source": "runtime_transition_gated_batch_diagnostics",
                "transition_gated": true,
                "transition_gate_ok": true,
                "raw_flags_all_false": true
            },
            "controlled_order": {
                "schema_ok": true,
                "expected_met": true,
                "raw_flags_all_false": true,
                "movement_observed": true
            },
            "runtime_readiness": {
                "provided": true,
                "schema_ok": true,
                "runtime_readiness_packet": true,
                "runtime_readiness_ready": true,
                "control_plane_ready": true,
                "may_accept_controlled_explicit_opt_in_fts_calls": true,
                "default_influence_ready": false,
                "batch_evidence_source": "runtime_transition_gated_batch_diagnostics",
                "batch_transition_gated": true,
                "batch_schema_ok": true,
                "batch_transition_gate_ok": true,
                "raw_flags_all_false": true,
                "default_order_safe": true,
                "matches_batch_diagnostics": true,
                "gated_batch_evidence_ready": true
            },
            "interpretation": {
                "batch_diagnostics_raw_safe": true,
                "batch_diagnostics_transition_gated": true,
                "batch_diagnostics_evidence_source": "runtime_transition_gated_batch_diagnostics",
                "gated_batch_diagnostics_ready": true,
                "controlled_order_raw_safe": true,
                "runtime_readiness_packet_provided": true,
                "runtime_readiness_packet_ready": true,
                "runtime_readiness_requirement_met": true,
                "readiness_batch_evidence_source": "runtime_transition_gated_batch_diagnostics",
                "readiness_batch_transition_gated": true,
                "readiness_matches_batch_diagnostics": true,
                "readiness_gated_batch_evidence_ready": true,
                "runtime_adapter_connection_evidence": true,
                "controlled_rank_movement_observed": true,
                "evidence_ready": true,
                "default_influence_ready": false,
                "review_state": "post_runtime_evidence_ready"
            },
            "approval_state": "evidence_summary_only",
            "authorization_state": "does_not_grant_runtime_influence",
            "approval_writes_allowed": false,
            "writes_approval": false,
            "calls_memory_search": false,
            "runs_biocortex": false,
            "registers_embedding_backend": false,
            "changes_memory_search_order": false,
            "default_search_order_change_allowed": false,
            "default_calls_unchanged": true,
            "raw_queries_included": false,
            "raw_keys_included": false,
            "content_included": false,
            "side_signal_raw_included": false,
            "raw_query": "secret evidence summary raw query",
            "raw_key": "secret_evidence_summary_key",
            "content": "secret evidence summary content"
        })
    }

    fn opt_in_capability_ledger_report_packet_fixture() -> Value {
        json!({
            "schema": BIOCORTEX_CAPABILITY_LEDGER_REPORT_PACKET_SCHEMA,
            "summary_schema": "agent_bridge.biocortex_capability_ledger.consumer_dry_run.v0",
            "report_schema": "agent_bridge.biocortex_capability_ledger.review_artifact.v0",
            "input_schema": "biocortex.capability_ledger.v3",
            "input_schema_version": "3",
            "input_mode": "read_only_shadow",
            "input_generated_by": "capability_ledger_shadow_adapter",
            "verdict": "accepted",
            "read_only_confirmed": true,
            "downstream_action": "display_or_review_only",
            "integration_decision": "shadow_only_no_runtime_admission",
            "safety": {
                "static_artifact_only": true,
                "memory_write_attempted": false,
                "retrieval_order_change_attempted": false,
                "runtime_authority_observed": false,
                "executor_enablement_observed": false,
                "mcp_tool_registration": false,
                "nexus_world_tick_touched": false,
                "aiot_runtime_called": false,
                "language_generation_observed": false,
                "cognition_claim_observed": false
            },
            "summary": {
                "schema": "agent_bridge.biocortex_capability_ledger.consumer_dry_run.v0",
                "verdict": "accepted"
            },
            "report_markdown": "secret ledger markdown should not be echoed",
            "raw_query": "secret ledger raw query",
            "raw_key": "secret_ledger_key",
            "content": "secret ledger content"
        })
    }

    fn opt_in_runtime_influence_decision_fixture() -> Value {
        json!({
            "schema": "agent_bridge.biocortex_retrieval.opt_in_runtime_influence_review_decision.v0",
            "decision": "authorized",
            "authorization_state": "authorized",
            "authorized_scope": "explicit_opt_in_fts_runtime_influence",
            "human_decision_text": "secret runtime influence decision wording",
            "runtime_adapter_approved": true,
            "ordering_behavior_connection_authorized": true,
            "default_search_order_change_allowed": false,
            "default_retrieval_influence_authorized": false,
            "hybrid_retrieval_influence_authorized": false,
            "semantic_retrieval_influence_authorized": false,
            "authorized_runtime_influence": {
                "may_run_runtime_adapter_for_explicit_opt_in_fts": true,
                "may_connect_ordering_behavior_for_explicit_opt_in_fts": true,
                "may_affect_only_explicitly_opted_in_fts_calls": true,
                "requires_per_call_opt_in": true,
                "must_keep_baseline_candidate_recall": true,
                "must_keep_default_calls_unchanged": true,
                "must_keep_redacted_audit_only": true,
                "must_keep_operator_disable": BIOCORTEX_RETRIEVAL_DISABLE_ENV,
                "must_return_baseline_without_per_call_opt_in": true,
                "must_fail_open_to_baseline": true
            },
            "not_authorized": [
                "default_search_order_change_allowed",
                "default_retrieval_influence_fts",
                "default_retrieval_influence_hybrid",
                "default_retrieval_influence_semantic",
                "hybrid_retrieval_influence",
                "semantic_retrieval_influence",
                "affecting_calls_without_explicit_opt_in"
            ],
            "raw_query": "secret runtime decision raw query",
            "raw_key": "secret_runtime_decision_key",
            "content": "secret runtime decision content"
        })
    }

    fn opt_in_runtime_influence_review_gate_fixture() -> Value {
        let mut request = opt_in_authorization_request_fixture();
        request["opt_in_plan"]["status"] = json!("runtime_influence_review_request_implemented");
        let decision_packet = biocortex_retrieval_opt_in_authorization_decision_packet(
            BioCortexRetrievalOptInAuthorizationDecisionPacketOptions {
                authorization_decision: opt_in_authorization_decision_fixture(),
                authorization_request: request,
                reviewer: Some("codex".to_string()),
                commit: Some("decision-commit".to_string()),
                forum_post_id: Some("103".to_string()),
                memory_key: Some("decision-memory".to_string()),
            },
        );
        let mut plan = opt_in_post_implementation_review_plan_fixture();
        plan["status"] = json!("runtime_influence_review_request_implemented");
        biocortex_retrieval_opt_in_post_implementation_review_gate(
            BioCortexRetrievalOptInPostImplementationReviewGateOptions {
                authorization_decision_packet: decision_packet,
                opt_in_plan: plan,
                reviewer: Some("codex".to_string()),
                commit: Some("review-gate-commit".to_string()),
                forum_post_id: Some("103".to_string()),
                memory_key: Some("review-gate-memory".to_string()),
            },
        )
    }

    fn opt_in_runtime_influence_review_request_fixture() -> Value {
        biocortex_retrieval_opt_in_runtime_influence_review_request(
            BioCortexRetrievalOptInRuntimeInfluenceReviewRequestOptions {
                post_implementation_review_gate: opt_in_runtime_influence_review_gate_fixture(),
                redacted_order_artifact: opt_in_runtime_influence_redacted_artifact_fixture(),
                redacted_evidence_aggregate: None,
                evidence_summary: None,
                capability_ledger_report_packet: None,
                reviewer: Some("codex".to_string()),
                commit: Some("runtime-review-request-commit".to_string()),
                forum_post_id: Some("103".to_string()),
                memory_key: Some("runtime-review-request-memory".to_string()),
            },
        )
    }

    fn opt_in_aggregate_backed_runtime_influence_review_request_fixture() -> Value {
        let mut request = opt_in_authorization_request_fixture();
        request["opt_in_plan"]["status"] = json!("runtime_influence_review_request_implemented");
        let decision_packet = biocortex_retrieval_opt_in_authorization_decision_packet(
            BioCortexRetrievalOptInAuthorizationDecisionPacketOptions {
                authorization_decision: opt_in_authorization_decision_fixture(),
                authorization_request: request,
                reviewer: Some("codex".to_string()),
                commit: Some("decision-commit".to_string()),
                forum_post_id: Some("103".to_string()),
                memory_key: Some("decision-memory".to_string()),
            },
        );
        let mut plan = opt_in_post_implementation_review_plan_fixture();
        plan["status"] = json!("runtime_influence_review_request_implemented");
        let gate = biocortex_retrieval_opt_in_post_implementation_review_gate(
            BioCortexRetrievalOptInPostImplementationReviewGateOptions {
                authorization_decision_packet: decision_packet,
                opt_in_plan: plan,
                reviewer: Some("codex".to_string()),
                commit: Some("review-gate-commit".to_string()),
                forum_post_id: Some("103".to_string()),
                memory_key: Some("review-gate-memory".to_string()),
            },
        );
        biocortex_retrieval_opt_in_runtime_influence_review_request(
            BioCortexRetrievalOptInRuntimeInfluenceReviewRequestOptions {
                post_implementation_review_gate: gate,
                redacted_order_artifact: opt_in_runtime_influence_redacted_artifact_fixture(),
                redacted_evidence_aggregate: Some(opt_in_redacted_evidence_aggregate_fixture()),
                evidence_summary: None,
                capability_ledger_report_packet: None,
                reviewer: Some("codex".to_string()),
                commit: Some("runtime-review-request-commit".to_string()),
                forum_post_id: Some("103".to_string()),
                memory_key: Some("runtime-review-request-memory".to_string()),
            },
        )
    }

    fn opt_in_aggregate_and_ledger_backed_runtime_influence_review_request_fixture() -> Value {
        let mut request = opt_in_authorization_request_fixture();
        request["opt_in_plan"]["status"] = json!("runtime_influence_review_request_implemented");
        let decision_packet = biocortex_retrieval_opt_in_authorization_decision_packet(
            BioCortexRetrievalOptInAuthorizationDecisionPacketOptions {
                authorization_decision: opt_in_authorization_decision_fixture(),
                authorization_request: request,
                reviewer: Some("codex".to_string()),
                commit: Some("decision-commit".to_string()),
                forum_post_id: Some("103".to_string()),
                memory_key: Some("decision-memory".to_string()),
            },
        );
        let mut plan = opt_in_post_implementation_review_plan_fixture();
        plan["status"] = json!("runtime_influence_review_request_implemented");
        let gate = biocortex_retrieval_opt_in_post_implementation_review_gate(
            BioCortexRetrievalOptInPostImplementationReviewGateOptions {
                authorization_decision_packet: decision_packet,
                opt_in_plan: plan,
                reviewer: Some("codex".to_string()),
                commit: Some("review-gate-commit".to_string()),
                forum_post_id: Some("103".to_string()),
                memory_key: Some("review-gate-memory".to_string()),
            },
        );
        biocortex_retrieval_opt_in_runtime_influence_review_request(
            BioCortexRetrievalOptInRuntimeInfluenceReviewRequestOptions {
                post_implementation_review_gate: gate,
                redacted_order_artifact: opt_in_runtime_influence_redacted_artifact_fixture(),
                redacted_evidence_aggregate: Some(opt_in_redacted_evidence_aggregate_fixture()),
                evidence_summary: None,
                capability_ledger_report_packet: Some(
                    opt_in_capability_ledger_report_packet_fixture(),
                ),
                reviewer: Some("codex".to_string()),
                commit: Some("runtime-review-request-commit".to_string()),
                forum_post_id: Some("103".to_string()),
                memory_key: Some("runtime-review-request-memory".to_string()),
            },
        )
    }

    fn opt_in_post_runtime_evidence_runtime_influence_review_request_fixture() -> Value {
        let mut request = opt_in_authorization_request_fixture();
        request["opt_in_plan"]["status"] = json!("runtime_influence_review_request_implemented");
        let decision_packet = biocortex_retrieval_opt_in_authorization_decision_packet(
            BioCortexRetrievalOptInAuthorizationDecisionPacketOptions {
                authorization_decision: opt_in_authorization_decision_fixture(),
                authorization_request: request,
                reviewer: Some("codex".to_string()),
                commit: Some("decision-commit".to_string()),
                forum_post_id: Some("103".to_string()),
                memory_key: Some("decision-memory".to_string()),
            },
        );
        let mut plan = opt_in_post_implementation_review_plan_fixture();
        plan["status"] = json!("runtime_influence_review_request_implemented");
        let gate = biocortex_retrieval_opt_in_post_implementation_review_gate(
            BioCortexRetrievalOptInPostImplementationReviewGateOptions {
                authorization_decision_packet: decision_packet,
                opt_in_plan: plan,
                reviewer: Some("codex".to_string()),
                commit: Some("review-gate-commit".to_string()),
                forum_post_id: Some("103".to_string()),
                memory_key: Some("review-gate-memory".to_string()),
            },
        );
        biocortex_retrieval_opt_in_runtime_influence_review_request(
            BioCortexRetrievalOptInRuntimeInfluenceReviewRequestOptions {
                post_implementation_review_gate: gate,
                redacted_order_artifact: opt_in_runtime_influence_redacted_artifact_fixture(),
                redacted_evidence_aggregate: Some(opt_in_redacted_evidence_aggregate_fixture()),
                evidence_summary: Some(opt_in_gated_readiness_evidence_summary_fixture()),
                capability_ledger_report_packet: None,
                reviewer: Some("codex".to_string()),
                commit: Some("runtime-review-request-commit".to_string()),
                forum_post_id: Some("103".to_string()),
                memory_key: Some("runtime-review-request-memory".to_string()),
            },
        )
    }

    #[test]
    fn opt_in_authorization_decision_packet_authorizes_implementation_only() {
        let packet = biocortex_retrieval_opt_in_authorization_decision_packet(
            BioCortexRetrievalOptInAuthorizationDecisionPacketOptions {
                authorization_decision: opt_in_authorization_decision_fixture(),
                authorization_request: opt_in_authorization_request_fixture(),
                reviewer: Some("codex".to_string()),
                commit: Some("decision-commit".to_string()),
                forum_post_id: Some("103".to_string()),
                memory_key: Some("decision-memory".to_string()),
            },
        );

        assert_eq!(
            packet["schema"],
            json!(BIOCORTEX_RETRIEVAL_OPT_IN_AUTHORIZATION_DECISION_PACKET_SCHEMA)
        );
        assert_eq!(packet["read_only"], json!(true));
        assert_eq!(packet["authorization_decision_consumer"], json!(true));
        assert_eq!(
            packet["implementation_stage"],
            json!("authorization_decision_consumer_only")
        );
        assert_eq!(
            packet["approval_state"],
            json!("opt_in_implementation_authorized")
        );
        assert_eq!(
            packet["authorization_state"],
            json!("authorized_for_opt_in_implementation")
        );
        assert_eq!(packet["runtime_adapter_approved"], json!(false));
        assert_eq!(packet["default_search_order_change_allowed"], json!(false));
        assert_eq!(packet["approval_writes_allowed"], json!(false));
        assert_eq!(packet["writes_approval"], json!(false));
        assert_eq!(packet["calls_memory_search"], json!(false));
        assert_eq!(packet["runs_biocortex"], json!(false));
        assert_eq!(packet["changes_memory_search_order"], json!(false));
        assert_eq!(packet["ordering_behavior_connected"], json!(false));
        assert_eq!(packet["may_change_search_order_now"], json!(false));
        assert_eq!(packet["may_implement_ordering_now"], json!(false));
        assert_eq!(
            packet["authorized_implementation"]["may_implement_opt_in_experiment"],
            json!(true)
        );
        assert_eq!(
            packet["required_next_gate"]["post_implementation_review_before_use"],
            json!(true)
        );
        assert_eq!(
            packet["required_next_gate"]["this_packet_approves_runtime_adapter"],
            json!(false)
        );
        assert_eq!(
            packet["boundary_check"]["implementation_authorized"],
            json!(true)
        );
        assert_eq!(
            packet["boundary_check"]["blockers"]
                .as_array()
                .expect("blockers")
                .len(),
            0
        );

        let serialized = serde_json::to_string(&packet).expect("packet json");
        assert!(!serialized.contains("secret human authorization wording"));
        assert!(!serialized.contains("secret decision raw query"));
        assert!(!serialized.contains("secret_decision_key"));
        assert!(!serialized.contains("secret request raw query"));
        assert!(!serialized.contains("secret_request_key"));
        assert!(!serialized.contains("secret request content"));
    }

    #[test]
    fn opt_in_authorization_decision_packet_rejects_runtime_influence_claims() {
        let mut decision = opt_in_authorization_decision_fixture();
        decision["runtime_adapter_approved"] = json!(true);
        decision["default_search_order_change_allowed"] = json!(true);
        decision["default_retrieval_influence_authorized"] = json!(true);
        decision["requires_post_implementation_review_before_use"] = json!(false);
        decision["not_authorized"] = json!(["production_use_without_post_implementation_review"]);

        let mut request = opt_in_authorization_request_fixture();
        request["runtime_adapter_approved"] = json!(true);
        request["default_search_order_change_allowed"] = json!(true);
        request["writes_approval"] = json!(true);

        let packet = biocortex_retrieval_opt_in_authorization_decision_packet(
            BioCortexRetrievalOptInAuthorizationDecisionPacketOptions {
                authorization_decision: decision,
                authorization_request: request,
                reviewer: None,
                commit: None,
                forum_post_id: None,
                memory_key: None,
            },
        );

        assert_eq!(
            packet["boundary_check"]["implementation_authorized"],
            json!(false)
        );
        let blockers = packet["boundary_check"]["blockers"]
            .as_array()
            .expect("blockers");
        assert!(blockers.contains(&json!("decision_runtime_adapter_approved")));
        assert!(blockers.contains(&json!("decision_default_order_allowed")));
        assert!(blockers.contains(&json!("decision_default_influence_authorized")));
        assert!(blockers.contains(&json!(
            "decision_missing_post_implementation_review_requirement"
        )));
        assert!(blockers.contains(&json!("decision_not_authorized_missing_runtime_adapter")));
        assert!(blockers.contains(&json!("decision_not_authorized_missing_default_order")));
        assert!(blockers.contains(&json!("request_runtime_adapter_approved")));
        assert!(blockers.contains(&json!("request_default_order_allowed")));
        assert!(blockers.contains(&json!("request_writes_approval")));
        assert_eq!(packet["approval_state"], json!("not_approved"));
        assert_eq!(packet["runtime_adapter_approved"], json!(false));
        assert_eq!(packet["default_search_order_change_allowed"], json!(false));
        assert_eq!(packet["writes_approval"], json!(false));
        assert_eq!(packet["may_implement_ordering_now"], json!(false));
    }

    #[test]
    fn opt_in_post_implementation_review_gate_prepares_review_without_approval() {
        let mut request = opt_in_authorization_request_fixture();
        request["opt_in_plan"]["status"] = json!("post_implementation_review_gate_implemented");
        let decision_packet = biocortex_retrieval_opt_in_authorization_decision_packet(
            BioCortexRetrievalOptInAuthorizationDecisionPacketOptions {
                authorization_decision: opt_in_authorization_decision_fixture(),
                authorization_request: request,
                reviewer: Some("codex".to_string()),
                commit: Some("decision-commit".to_string()),
                forum_post_id: Some("103".to_string()),
                memory_key: Some("decision-memory".to_string()),
            },
        );
        assert_eq!(
            decision_packet["boundary_check"]["implementation_authorized"],
            json!(true)
        );

        let packet = biocortex_retrieval_opt_in_post_implementation_review_gate(
            BioCortexRetrievalOptInPostImplementationReviewGateOptions {
                authorization_decision_packet: decision_packet,
                opt_in_plan: opt_in_post_implementation_review_plan_fixture(),
                reviewer: Some("codex".to_string()),
                commit: Some("review-gate-commit".to_string()),
                forum_post_id: Some("103".to_string()),
                memory_key: Some("review-gate-memory".to_string()),
            },
        );

        assert_eq!(
            packet["schema"],
            json!(BIOCORTEX_RETRIEVAL_OPT_IN_POST_IMPLEMENTATION_REVIEW_GATE_SCHEMA)
        );
        assert_eq!(packet["read_only"], json!(true));
        assert_eq!(packet["post_implementation_review_gate"], json!(true));
        assert_eq!(
            packet["implementation_stage"],
            json!("post_implementation_review_gate_only")
        );
        assert_eq!(
            packet["review_readiness"]["ready_for_human_runtime_influence_review"],
            json!(true)
        );
        assert_eq!(
            packet["review_readiness"]["post_implementation_review_completed"],
            json!(false)
        );
        assert_eq!(
            packet["review_readiness"]["this_packet_approves_runtime_adapter"],
            json!(false)
        );
        assert_eq!(
            packet["boundary_check"]["ready_for_human_runtime_influence_review"],
            json!(true)
        );
        assert_eq!(
            packet["boundary_check"]["blockers"]
                .as_array()
                .expect("blockers")
                .len(),
            0
        );
        assert_eq!(
            packet["review_state"],
            json!("ready_for_human_runtime_influence_review")
        );
        assert_eq!(packet["approval_state"], json!("not_approved"));
        assert_eq!(
            packet["authorization_state"],
            json!("requires_separate_human_runtime_influence_review")
        );
        assert_eq!(packet["implementation_allowed"], json!(false));
        assert_eq!(packet["runtime_adapter_approved"], json!(false));
        assert_eq!(packet["default_search_order_change_allowed"], json!(false));
        assert_eq!(packet["approval_writes_allowed"], json!(false));
        assert_eq!(packet["writes_approval"], json!(false));
        assert_eq!(packet["calls_memory_search"], json!(false));
        assert_eq!(packet["runs_biocortex"], json!(false));
        assert_eq!(packet["changes_memory_search_order"], json!(false));
        assert_eq!(packet["ordering_behavior_connected"], json!(false));
        assert_eq!(packet["may_change_search_order_now"], json!(false));
        assert_eq!(packet["may_implement_ordering_now"], json!(false));
        assert_eq!(
            packet["required_next_gate"]["this_packet_approves_runtime_adapter"],
            json!(false)
        );
        assert_eq!(
            packet["required_next_gate"]["this_packet_connects_ordering_behavior"],
            json!(false)
        );

        let serialized = serde_json::to_string(&packet).expect("packet json");
        assert!(!serialized.contains("secret decision raw query"));
        assert!(!serialized.contains("secret_decision_key"));
        assert!(!serialized.contains("secret request raw query"));
        assert!(!serialized.contains("secret_request_key"));
        assert!(!serialized.contains("secret plan raw query"));
        assert!(!serialized.contains("secret_plan_key"));
        assert!(!serialized.contains("secret plan content"));
    }

    #[test]
    fn opt_in_post_implementation_review_gate_blocks_runtime_influence_claims() {
        let decision_packet = biocortex_retrieval_opt_in_authorization_decision_packet(
            BioCortexRetrievalOptInAuthorizationDecisionPacketOptions {
                authorization_decision: opt_in_authorization_decision_fixture(),
                authorization_request: opt_in_authorization_request_fixture(),
                reviewer: None,
                commit: None,
                forum_post_id: None,
                memory_key: None,
            },
        );
        let mut decision_packet = decision_packet;
        decision_packet["runtime_adapter_approved"] = json!(true);
        decision_packet["default_search_order_change_allowed"] = json!(true);
        decision_packet["ordering_behavior_connected"] = json!(true);
        decision_packet["may_change_search_order_now"] = json!(true);

        let mut plan = opt_in_post_implementation_review_plan_fixture();
        plan["runtime_adapter_approved"] = json!(true);
        plan["default_search_order_change_allowed"] = json!(true);
        plan["ordering_behavior_connected"] = json!(true);
        plan["implemented_post_implementation_review_gate"]["runtime_adapter_approved"] =
            json!(true);

        let packet = biocortex_retrieval_opt_in_post_implementation_review_gate(
            BioCortexRetrievalOptInPostImplementationReviewGateOptions {
                authorization_decision_packet: decision_packet,
                opt_in_plan: plan,
                reviewer: None,
                commit: None,
                forum_post_id: None,
                memory_key: None,
            },
        );

        assert_eq!(
            packet["boundary_check"]["ready_for_human_runtime_influence_review"],
            json!(false)
        );
        let blockers = packet["boundary_check"]["blockers"]
            .as_array()
            .expect("blockers");
        assert!(blockers.contains(&json!("packet_runtime_adapter_approved")));
        assert!(blockers.contains(&json!("packet_default_order_allowed")));
        assert!(blockers.contains(&json!("packet_ordering_behavior_connected")));
        assert!(blockers.contains(&json!("packet_may_change_search_order_now")));
        assert!(blockers.contains(&json!("plan_runtime_adapter_approved")));
        assert!(blockers.contains(&json!("plan_default_order_allowed")));
        assert!(blockers.contains(&json!("plan_ordering_behavior_connected")));
        assert!(blockers.contains(&json!("plan_gate_runtime_adapter_approved")));
        assert_eq!(packet["review_state"], json!("blocked"));
        assert_eq!(packet["approval_state"], json!("not_approved"));
        assert_eq!(packet["runtime_adapter_approved"], json!(false));
        assert_eq!(packet["default_search_order_change_allowed"], json!(false));
        assert_eq!(packet["changes_memory_search_order"], json!(false));
        assert_eq!(packet["ordering_behavior_connected"], json!(false));
        assert_eq!(packet["may_change_search_order_now"], json!(false));
        assert_eq!(packet["may_implement_ordering_now"], json!(false));
    }

    #[test]
    fn opt_in_runtime_influence_review_request_prepares_request_without_approval() {
        let mut request = opt_in_authorization_request_fixture();
        request["opt_in_plan"]["status"] = json!("runtime_influence_review_request_implemented");
        let decision_packet = biocortex_retrieval_opt_in_authorization_decision_packet(
            BioCortexRetrievalOptInAuthorizationDecisionPacketOptions {
                authorization_decision: opt_in_authorization_decision_fixture(),
                authorization_request: request,
                reviewer: Some("codex".to_string()),
                commit: Some("decision-commit".to_string()),
                forum_post_id: Some("103".to_string()),
                memory_key: Some("decision-memory".to_string()),
            },
        );
        let mut plan = opt_in_post_implementation_review_plan_fixture();
        plan["status"] = json!("runtime_influence_review_request_implemented");
        let gate = biocortex_retrieval_opt_in_post_implementation_review_gate(
            BioCortexRetrievalOptInPostImplementationReviewGateOptions {
                authorization_decision_packet: decision_packet,
                opt_in_plan: plan,
                reviewer: Some("codex".to_string()),
                commit: Some("review-gate-commit".to_string()),
                forum_post_id: Some("103".to_string()),
                memory_key: Some("review-gate-memory".to_string()),
            },
        );
        assert_eq!(
            gate["boundary_check"]["ready_for_human_runtime_influence_review"],
            json!(true)
        );

        let packet = biocortex_retrieval_opt_in_runtime_influence_review_request(
            BioCortexRetrievalOptInRuntimeInfluenceReviewRequestOptions {
                post_implementation_review_gate: gate,
                redacted_order_artifact: opt_in_runtime_influence_redacted_artifact_fixture(),
                redacted_evidence_aggregate: None,
                evidence_summary: None,
                capability_ledger_report_packet: None,
                reviewer: Some("codex".to_string()),
                commit: Some("runtime-review-request-commit".to_string()),
                forum_post_id: Some("103".to_string()),
                memory_key: Some("runtime-review-request-memory".to_string()),
            },
        );

        assert_eq!(
            packet["schema"],
            json!(BIOCORTEX_RETRIEVAL_OPT_IN_RUNTIME_INFLUENCE_REVIEW_REQUEST_SCHEMA)
        );
        assert_eq!(packet["read_only"], json!(true));
        assert_eq!(packet["runtime_influence_review_request"], json!(true));
        assert_eq!(
            packet["implementation_stage"],
            json!("runtime_influence_review_request_only")
        );
        assert_eq!(
            packet["request_scope"],
            json!("explicit_opt_in_fts_runtime_influence_review")
        );
        assert_eq!(
            packet["boundary_check"]["runtime_influence_review_request_ready"],
            json!(true)
        );
        assert_eq!(
            packet["boundary_check"]["blockers"]
                .as_array()
                .expect("blockers")
                .len(),
            0
        );
        assert_eq!(
            packet["requested_authorization"]["request_runtime_adapter_review"],
            json!(true)
        );
        assert_eq!(
            packet["requested_authorization"]["request_ordering_behavior_connection_review"],
            json!(true)
        );
        assert_eq!(
            packet["requested_authorization"]["request_default_search_order_change"],
            json!(false)
        );
        assert_eq!(
            packet["requested_authorization"]["this_packet_grants_request"],
            json!(false)
        );
        assert_eq!(
            packet["requested_authorization"]["accepts_redacted_evidence_aggregate"],
            json!(true)
        );
        assert_eq!(
            packet["requested_authorization"]["requires_redacted_evidence_aggregate"],
            json!(false)
        );
        assert_eq!(
            packet["input_contract"]["redacted_evidence_aggregate_schema"],
            Value::Null
        );
        assert_eq!(
            packet["input_contract"]["redacted_evidence_aggregate_included"],
            json!(false)
        );
        assert_eq!(
            packet["evidence_summary"]["redacted_evidence_aggregate_provided"],
            json!(false)
        );
        assert_eq!(
            packet["evidence_summary"]["redacted_evidence_aggregate_ready"],
            json!(false)
        );
        assert_eq!(
            packet["review_request_state"],
            json!("ready_for_human_runtime_influence_review")
        );
        assert_eq!(packet["approval_state"], json!("not_approved"));
        assert_eq!(
            packet["authorization_state"],
            json!("runtime_influence_review_requested_not_granted")
        );
        assert_eq!(packet["implementation_allowed"], json!(false));
        assert_eq!(packet["runtime_adapter_approved"], json!(false));
        assert_eq!(packet["default_search_order_change_allowed"], json!(false));
        assert_eq!(packet["writes_approval"], json!(false));
        assert_eq!(packet["calls_memory_search"], json!(false));
        assert_eq!(packet["runs_biocortex"], json!(false));
        assert_eq!(packet["changes_memory_search_order"], json!(false));
        assert_eq!(packet["ordering_behavior_connected"], json!(false));
        assert_eq!(packet["may_change_search_order_now"], json!(false));
        assert_eq!(packet["may_implement_ordering_now"], json!(false));

        let serialized = serde_json::to_string(&packet).expect("packet json");
        assert!(!serialized.contains("secret decision raw query"));
        assert!(!serialized.contains("secret request raw query"));
        assert!(!serialized.contains("secret artifact raw query"));
        assert!(!serialized.contains("secret_artifact_key"));
        assert!(!serialized.contains("secret artifact content"));
    }

    #[test]
    fn opt_in_runtime_influence_review_request_accepts_redacted_aggregate_evidence() {
        let mut request = opt_in_authorization_request_fixture();
        request["opt_in_plan"]["status"] = json!("runtime_influence_review_request_implemented");
        let decision_packet = biocortex_retrieval_opt_in_authorization_decision_packet(
            BioCortexRetrievalOptInAuthorizationDecisionPacketOptions {
                authorization_decision: opt_in_authorization_decision_fixture(),
                authorization_request: request,
                reviewer: Some("codex".to_string()),
                commit: Some("decision-commit".to_string()),
                forum_post_id: Some("103".to_string()),
                memory_key: Some("decision-memory".to_string()),
            },
        );
        let mut plan = opt_in_post_implementation_review_plan_fixture();
        plan["status"] = json!("runtime_influence_review_request_implemented");
        let gate = biocortex_retrieval_opt_in_post_implementation_review_gate(
            BioCortexRetrievalOptInPostImplementationReviewGateOptions {
                authorization_decision_packet: decision_packet,
                opt_in_plan: plan,
                reviewer: Some("codex".to_string()),
                commit: Some("review-gate-commit".to_string()),
                forum_post_id: Some("103".to_string()),
                memory_key: Some("review-gate-memory".to_string()),
            },
        );

        let packet = biocortex_retrieval_opt_in_runtime_influence_review_request(
            BioCortexRetrievalOptInRuntimeInfluenceReviewRequestOptions {
                post_implementation_review_gate: gate,
                redacted_order_artifact: opt_in_runtime_influence_redacted_artifact_fixture(),
                redacted_evidence_aggregate: Some(opt_in_redacted_evidence_aggregate_fixture()),
                evidence_summary: None,
                capability_ledger_report_packet: None,
                reviewer: Some("codex".to_string()),
                commit: Some("runtime-review-request-commit".to_string()),
                forum_post_id: Some("103".to_string()),
                memory_key: Some("runtime-review-request-memory".to_string()),
            },
        );

        assert_eq!(
            packet["input_contract"]["redacted_evidence_aggregate_schema"],
            json!(BIOCORTEX_RETRIEVAL_OPT_IN_REDACTED_EVIDENCE_AGGREGATE_SCHEMA)
        );
        assert_eq!(
            packet["input_contract"]["redacted_evidence_aggregate_included"],
            json!(false)
        );
        assert_eq!(
            packet["evidence_summary"]["redacted_evidence_aggregate_provided"],
            json!(true)
        );
        assert_eq!(
            packet["evidence_summary"]["redacted_evidence_aggregate_ready"],
            json!(true)
        );
        assert_eq!(
            packet["evidence_summary"]["aggregate_review_state"],
            json!("redacted_aggregate_ready")
        );
        assert_eq!(
            packet["evidence_summary"]["controlled_rank_movement_observed"],
            json!(true)
        );
        assert_eq!(
            packet["evidence_summary"]["expanded_coverage_without_additional_movement"],
            json!(true)
        );
        assert_eq!(
            packet["evidence_summary"]["aggregate_default_influence_ready"],
            json!(false)
        );
        assert_eq!(
            packet["evidence_summary"]["aggregate_human_review_required"],
            json!(true)
        );
        assert_eq!(
            packet["boundary_check"]["runtime_influence_review_request_ready"],
            json!(true)
        );
        assert_eq!(
            packet["boundary_check"]["redacted_evidence_aggregate_provided"],
            json!(true)
        );
        assert_eq!(
            packet["boundary_check"]["redacted_evidence_aggregate_ready"],
            json!(true)
        );
        assert_eq!(
            packet["boundary_check"]["aggregate_safe_for_review"],
            json!(true)
        );
        assert_eq!(packet["approval_state"], json!("not_approved"));
        assert_eq!(packet["runtime_adapter_approved"], json!(false));
        assert_eq!(packet["default_search_order_change_allowed"], json!(false));
        assert_eq!(packet["changes_memory_search_order"], json!(false));

        let serialized = serde_json::to_string(&packet).expect("packet json");
        assert!(!serialized.contains("secret aggregate raw query"));
        assert!(!serialized.contains("secret_aggregate_key"));
        assert!(!serialized.contains("secret aggregate content"));
    }

    #[test]
    fn opt_in_runtime_influence_review_request_accepts_gated_evidence_summary() {
        let mut request = opt_in_authorization_request_fixture();
        request["opt_in_plan"]["status"] = json!("runtime_influence_review_request_implemented");
        let decision_packet = biocortex_retrieval_opt_in_authorization_decision_packet(
            BioCortexRetrievalOptInAuthorizationDecisionPacketOptions {
                authorization_decision: opt_in_authorization_decision_fixture(),
                authorization_request: request,
                reviewer: Some("codex".to_string()),
                commit: Some("decision-commit".to_string()),
                forum_post_id: Some("103".to_string()),
                memory_key: Some("decision-memory".to_string()),
            },
        );
        let mut plan = opt_in_post_implementation_review_plan_fixture();
        plan["status"] = json!("runtime_influence_review_request_implemented");
        let gate = biocortex_retrieval_opt_in_post_implementation_review_gate(
            BioCortexRetrievalOptInPostImplementationReviewGateOptions {
                authorization_decision_packet: decision_packet,
                opt_in_plan: plan,
                reviewer: Some("codex".to_string()),
                commit: Some("review-gate-commit".to_string()),
                forum_post_id: Some("103".to_string()),
                memory_key: Some("review-gate-memory".to_string()),
            },
        );

        let packet = biocortex_retrieval_opt_in_runtime_influence_review_request(
            BioCortexRetrievalOptInRuntimeInfluenceReviewRequestOptions {
                post_implementation_review_gate: gate,
                redacted_order_artifact: opt_in_runtime_influence_redacted_artifact_fixture(),
                redacted_evidence_aggregate: Some(opt_in_redacted_evidence_aggregate_fixture()),
                evidence_summary: Some(opt_in_gated_readiness_evidence_summary_fixture()),
                capability_ledger_report_packet: None,
                reviewer: Some("codex".to_string()),
                commit: Some("runtime-review-request-commit".to_string()),
                forum_post_id: Some("103".to_string()),
                memory_key: Some("runtime-review-request-memory".to_string()),
            },
        );

        assert_eq!(
            packet["input_contract"]["post_runtime_evidence_summary_schema"],
            json!(BIOCORTEX_RETRIEVAL_OPT_IN_EVIDENCE_SUMMARY_SCHEMA)
        );
        assert_eq!(
            packet["input_contract"]["post_runtime_evidence_summary_included"],
            json!(false)
        );
        assert_eq!(
            packet["requested_authorization"]["accepts_post_runtime_evidence_summary"],
            json!(true)
        );
        assert_eq!(
            packet["requested_authorization"]["requires_post_runtime_evidence_summary"],
            json!(false)
        );
        assert_eq!(
            packet["evidence_summary"]["post_runtime_evidence_summary_provided"],
            json!(true)
        );
        assert_eq!(
            packet["evidence_summary"]["post_runtime_evidence_summary_ready"],
            json!(true)
        );
        assert_eq!(
            packet["evidence_summary"]["post_runtime_evidence_summary_review_state"],
            json!("post_runtime_evidence_ready")
        );
        assert_eq!(
            packet["evidence_summary"]["post_runtime_evidence_summary_default_influence_ready"],
            json!(false)
        );
        assert_eq!(
            packet["evidence_summary"]["post_runtime_controlled_rank_movement_observed"],
            json!(true)
        );
        assert_eq!(
            packet["evidence_summary"]["post_runtime_runtime_readiness_packet_provided"],
            json!(true)
        );
        assert_eq!(
            packet["evidence_summary"]["post_runtime_runtime_readiness_requirement_met"],
            json!(true)
        );
        assert_eq!(
            packet["evidence_summary"]["post_runtime_readiness_gated_batch_evidence_ready"],
            json!(true)
        );
        assert_eq!(
            packet["evidence_summary"]["post_runtime_batch_transition_gated"],
            json!(true)
        );
        assert_eq!(
            packet["evidence_summary"]["post_runtime_batch_evidence_source"],
            json!("runtime_transition_gated_batch_diagnostics")
        );
        assert_eq!(
            packet["evidence_summary"]["post_runtime_evidence_summary_included"],
            json!(false)
        );
        assert_eq!(
            packet["boundary_check"]["runtime_influence_review_request_ready"],
            json!(true)
        );
        assert_eq!(
            packet["boundary_check"]["post_runtime_evidence_summary_provided"],
            json!(true)
        );
        assert_eq!(
            packet["boundary_check"]["post_runtime_evidence_summary_ready"],
            json!(true)
        );
        assert_eq!(
            packet["boundary_check"]["post_runtime_evidence_summary_schema_ok"],
            json!(true)
        );
        assert_eq!(
            packet["boundary_check"]["post_runtime_evidence_summary_safe_for_review"],
            json!(true)
        );
        assert_eq!(
            packet["boundary_check"]["post_runtime_evidence_summary_gated_readiness_ready"],
            json!(true)
        );
        assert_eq!(
            packet["boundary_check"]["blockers"]
                .as_array()
                .expect("blockers")
                .len(),
            0
        );
        assert_eq!(packet["approval_state"], json!("not_approved"));
        assert_eq!(packet["runtime_adapter_approved"], json!(false));
        assert_eq!(packet["default_search_order_change_allowed"], json!(false));
        assert_eq!(packet["changes_memory_search_order"], json!(false));

        let serialized = serde_json::to_string(&packet).expect("packet json");
        assert!(!serialized.contains("secret evidence summary raw query"));
        assert!(!serialized.contains("secret_evidence_summary_key"));
        assert!(!serialized.contains("secret evidence summary content"));
    }

    #[test]
    fn opt_in_runtime_influence_review_request_accepts_capability_ledger_packet() {
        let mut request = opt_in_authorization_request_fixture();
        request["opt_in_plan"]["status"] = json!("runtime_influence_review_request_implemented");
        let decision_packet = biocortex_retrieval_opt_in_authorization_decision_packet(
            BioCortexRetrievalOptInAuthorizationDecisionPacketOptions {
                authorization_decision: opt_in_authorization_decision_fixture(),
                authorization_request: request,
                reviewer: Some("codex".to_string()),
                commit: Some("decision-commit".to_string()),
                forum_post_id: Some("103".to_string()),
                memory_key: Some("decision-memory".to_string()),
            },
        );
        let mut plan = opt_in_post_implementation_review_plan_fixture();
        plan["status"] = json!("runtime_influence_review_request_implemented");
        let gate = biocortex_retrieval_opt_in_post_implementation_review_gate(
            BioCortexRetrievalOptInPostImplementationReviewGateOptions {
                authorization_decision_packet: decision_packet,
                opt_in_plan: plan,
                reviewer: Some("codex".to_string()),
                commit: Some("review-gate-commit".to_string()),
                forum_post_id: Some("103".to_string()),
                memory_key: Some("review-gate-memory".to_string()),
            },
        );

        let packet = biocortex_retrieval_opt_in_runtime_influence_review_request(
            BioCortexRetrievalOptInRuntimeInfluenceReviewRequestOptions {
                post_implementation_review_gate: gate,
                redacted_order_artifact: opt_in_runtime_influence_redacted_artifact_fixture(),
                redacted_evidence_aggregate: None,
                evidence_summary: None,
                capability_ledger_report_packet: Some(
                    opt_in_capability_ledger_report_packet_fixture(),
                ),
                reviewer: Some("codex".to_string()),
                commit: Some("runtime-review-request-commit".to_string()),
                forum_post_id: Some("103".to_string()),
                memory_key: Some("runtime-review-request-memory".to_string()),
            },
        );

        assert_eq!(
            packet["input_contract"]["capability_ledger_report_packet_schema"],
            json!(BIOCORTEX_CAPABILITY_LEDGER_REPORT_PACKET_SCHEMA)
        );
        assert_eq!(
            packet["input_contract"]["capability_ledger_report_packet_included"],
            json!(false)
        );
        assert_eq!(
            packet["requested_authorization"]["accepts_capability_ledger_report_packet"],
            json!(true)
        );
        assert_eq!(
            packet["requested_authorization"]["requires_capability_ledger_report_packet"],
            json!(false)
        );
        assert_eq!(
            packet["requested_authorization"]["capability_ledger_can_authorize_runtime_influence"],
            json!(false)
        );
        assert_eq!(
            packet["evidence_summary"]["capability_ledger_report_packet_provided"],
            json!(true)
        );
        assert_eq!(
            packet["evidence_summary"]["capability_ledger_report_packet_accepted"],
            json!(true)
        );
        assert_eq!(
            packet["evidence_summary"]["capability_ledger_read_only_confirmed"],
            json!(true)
        );
        assert_eq!(
            packet["evidence_summary"]["capability_ledger_input_schema_version"],
            json!("3")
        );
        assert_eq!(
            packet["evidence_summary"]["capability_ledger_report_packet_included"],
            json!(false)
        );
        assert_eq!(
            packet["boundary_check"]["runtime_influence_review_request_ready"],
            json!(true)
        );
        assert_eq!(
            packet["boundary_check"]["capability_ledger_report_packet_provided"],
            json!(true)
        );
        assert_eq!(
            packet["boundary_check"]["capability_ledger_report_packet_safe_for_review"],
            json!(true)
        );
        assert_eq!(
            packet["boundary_check"]["blockers"]
                .as_array()
                .expect("blockers")
                .len(),
            0
        );
        assert_eq!(packet["runtime_adapter_approved"], json!(false));
        assert_eq!(packet["changes_memory_search_order"], json!(false));

        let serialized = serde_json::to_string(&packet).expect("packet json");
        assert!(!serialized.contains("secret ledger markdown"));
        assert!(!serialized.contains("secret ledger raw query"));
        assert!(!serialized.contains("secret_ledger_key"));
        assert!(!serialized.contains("secret ledger content"));
    }

    #[test]
    fn opt_in_runtime_influence_review_request_rejects_capability_ledger_runtime_decision_words() {
        let mut capability_ledger = opt_in_capability_ledger_report_packet_fixture();
        capability_ledger["downstream_action"] = json!("enable_runtime");
        capability_ledger["integration_decision"] = json!("runtime_admission");

        let packet = biocortex_retrieval_opt_in_runtime_influence_review_request(
            BioCortexRetrievalOptInRuntimeInfluenceReviewRequestOptions {
                post_implementation_review_gate: opt_in_runtime_influence_review_gate_fixture(),
                redacted_order_artifact: opt_in_runtime_influence_redacted_artifact_fixture(),
                redacted_evidence_aggregate: None,
                evidence_summary: None,
                capability_ledger_report_packet: Some(capability_ledger),
                reviewer: Some("codex".to_string()),
                commit: Some("runtime-review-request-commit".to_string()),
                forum_post_id: Some("103".to_string()),
                memory_key: Some("runtime-review-request-memory".to_string()),
            },
        );

        assert_eq!(
            packet["boundary_check"]["runtime_influence_review_request_ready"],
            json!(false)
        );
        assert_eq!(
            packet["boundary_check"]["capability_ledger_report_packet_safe_for_review"],
            json!(false)
        );
        let blockers = packet["boundary_check"]["blockers"]
            .as_array()
            .expect("blockers");
        assert!(blockers.contains(&json!("capability_ledger_decision_not_display_only")));
        assert_eq!(packet["review_request_state"], json!("blocked"));
        assert_eq!(packet["runtime_adapter_approved"], json!(false));
        assert_eq!(packet["changes_memory_search_order"], json!(false));
    }

    #[test]
    fn opt_in_runtime_influence_review_request_blocks_approval_claims() {
        let mut gate = json!({
            "schema": BIOCORTEX_RETRIEVAL_OPT_IN_POST_IMPLEMENTATION_REVIEW_GATE_SCHEMA,
            "read_only": true,
            "post_implementation_review_gate": true,
            "review_readiness": {
                "ready_for_human_runtime_influence_review": true
            },
            "boundary_check": {
                "ready_for_human_runtime_influence_review": true
            },
            "review_state": "ready_for_human_runtime_influence_review",
            "approval_state": "not_approved",
            "authorization_state": "requires_separate_human_runtime_influence_review",
            "required_next_gate": {
                "runtime_adapter_approval_required": true,
                "ordering_behavior_connection_required": true,
                "this_packet_approves_runtime_adapter": false,
                "this_packet_connects_ordering_behavior": false
            },
            "runtime_adapter_approved": false,
            "default_search_order_change_allowed": false,
            "writes_approval": false,
            "calls_memory_search": false,
            "runs_biocortex": false,
            "changes_memory_search_order": false,
            "ordering_behavior_connected": false,
            "may_change_search_order_now": false,
            "may_implement_ordering_now": false
        });
        gate["runtime_adapter_approved"] = json!(true);
        gate["ordering_behavior_connected"] = json!(true);

        let mut artifact = opt_in_runtime_influence_redacted_artifact_fixture();
        artifact["changes_memory_search_order"] = json!(true);
        artifact["default_search_order_change_allowed"] = json!(true);
        artifact["redacted_order_comparison"]["returned_order"]["actual_return_order_changed"] =
            json!(true);

        let packet = biocortex_retrieval_opt_in_runtime_influence_review_request(
            BioCortexRetrievalOptInRuntimeInfluenceReviewRequestOptions {
                post_implementation_review_gate: gate,
                redacted_order_artifact: artifact,
                redacted_evidence_aggregate: None,
                evidence_summary: None,
                capability_ledger_report_packet: None,
                reviewer: None,
                commit: None,
                forum_post_id: None,
                memory_key: None,
            },
        );

        assert_eq!(
            packet["boundary_check"]["runtime_influence_review_request_ready"],
            json!(false)
        );
        let blockers = packet["boundary_check"]["blockers"]
            .as_array()
            .expect("blockers");
        assert!(blockers.contains(&json!("gate_runtime_adapter_approved")));
        assert!(blockers.contains(&json!("gate_ordering_connected")));
        assert!(blockers.contains(&json!("artifact_changes_memory_search_order")));
        assert!(blockers.contains(&json!("artifact_default_order_allowed")));
        assert!(blockers.contains(&json!("artifact_return_order_changed")));
        assert_eq!(packet["review_request_state"], json!("blocked"));
        assert_eq!(packet["approval_state"], json!("not_approved"));
        assert_eq!(packet["runtime_adapter_approved"], json!(false));
        assert_eq!(packet["default_search_order_change_allowed"], json!(false));
        assert_eq!(packet["changes_memory_search_order"], json!(false));
        assert_eq!(packet["ordering_behavior_connected"], json!(false));
        assert_eq!(packet["may_change_search_order_now"], json!(false));
        assert_eq!(packet["may_implement_ordering_now"], json!(false));
    }

    #[test]
    fn opt_in_runtime_influence_decision_packet_authorizes_fts_only_implementation() {
        let packet = biocortex_retrieval_opt_in_runtime_influence_decision_packet(
            BioCortexRetrievalOptInRuntimeInfluenceDecisionPacketOptions {
                runtime_influence_review_request: opt_in_runtime_influence_review_request_fixture(),
                runtime_influence_decision: opt_in_runtime_influence_decision_fixture(),
                reviewer: Some("codex".to_string()),
                commit: Some("runtime-decision-commit".to_string()),
                forum_post_id: Some("104".to_string()),
                memory_key: Some("runtime-decision-memory".to_string()),
            },
        );

        assert_eq!(
            packet["schema"],
            json!(BIOCORTEX_RETRIEVAL_OPT_IN_RUNTIME_INFLUENCE_DECISION_PACKET_SCHEMA)
        );
        assert_eq!(packet["read_only"], json!(true));
        assert_eq!(packet["runtime_influence_decision_consumer"], json!(true));
        assert_eq!(
            packet["implementation_stage"],
            json!("runtime_influence_decision_consumer_only")
        );
        assert_eq!(
            packet["authorization_scope"],
            json!("explicit_opt_in_fts_runtime_influence")
        );
        assert_eq!(
            packet["boundary_check"]["runtime_influence_authorized"],
            json!(true)
        );
        assert_eq!(
            packet["boundary_check"]["blockers"]
                .as_array()
                .expect("blockers")
                .len(),
            0
        );
        assert_eq!(
            packet["approval_state"],
            json!("runtime_influence_review_authorized")
        );
        assert_eq!(
            packet["authorization_state"],
            json!("authorized_for_explicit_opt_in_fts_runtime_influence")
        );
        assert_eq!(packet["implementation_allowed"], json!(true));
        assert_eq!(packet["runtime_adapter_approved"], json!(true));
        assert_eq!(
            packet["ordering_behavior_connection_authorized"],
            json!(true)
        );
        assert_eq!(packet["default_search_order_change_allowed"], json!(false));
        assert_eq!(packet["approval_writes_allowed"], json!(false));
        assert_eq!(packet["writes_approval"], json!(false));
        assert_eq!(packet["calls_memory_search"], json!(false));
        assert_eq!(packet["runs_biocortex"], json!(false));
        assert_eq!(packet["changes_memory_search_order"], json!(false));
        assert_eq!(packet["ordering_behavior_connected"], json!(false));
        assert_eq!(packet["may_change_search_order_now"], json!(false));
        assert_eq!(packet["may_implement_ordering_now"], json!(true));
        assert_eq!(
            packet["authorized_runtime_influence"]
                ["may_run_runtime_adapter_for_explicit_opt_in_fts"],
            json!(true)
        );
        assert_eq!(
            packet["authorized_runtime_influence"]
                ["may_connect_ordering_behavior_for_explicit_opt_in_fts"],
            json!(true)
        );
        assert_eq!(
            packet["required_next_gate"]["this_packet_connects_ordering_behavior"],
            json!(false)
        );
        assert_eq!(
            packet["required_next_gate"]["this_packet_changes_return_order"],
            json!(false)
        );
        assert_eq!(
            packet["input_contract"]["accepts_aggregate_backed_review_request"],
            json!(true)
        );
        assert_eq!(
            packet["input_contract"]["requires_aggregate_ready_when_provided"],
            json!(true)
        );
        assert_eq!(
            packet["input_contract"]["redacted_evidence_aggregate_included"],
            json!(false)
        );
        assert_eq!(
            packet["request_summary"]["aggregate_backed_review_request"],
            json!(false)
        );
        assert_eq!(
            packet["request_summary"]["aggregate_review_evidence_state"],
            json!("not_provided_legacy_compatible")
        );
        assert_eq!(
            packet["boundary_check"]["legacy_review_request_without_aggregate_allowed"],
            json!(true)
        );
        assert_eq!(
            packet["boundary_check"]["aggregate_safe_for_decision"],
            json!(true)
        );

        let serialized = serde_json::to_string(&packet).expect("packet json");
        assert!(!serialized.contains("secret runtime influence decision wording"));
        assert!(!serialized.contains("secret runtime decision raw query"));
        assert!(!serialized.contains("secret_runtime_decision_key"));
        assert!(!serialized.contains("secret runtime decision content"));
        assert!(!serialized.contains("secret artifact raw query"));
        assert!(!serialized.contains("secret_artifact_key"));
    }

    #[test]
    fn opt_in_runtime_influence_decision_packet_blocks_scope_and_request_claims() {
        let mut decision = opt_in_runtime_influence_decision_fixture();
        decision["authorized_scope"] = json!("default_retrieval_influence");
        decision["default_search_order_change_allowed"] = json!(true);
        decision["default_retrieval_influence_authorized"] = json!(true);
        decision["hybrid_retrieval_influence_authorized"] = json!(true);
        decision["authorized_runtime_influence"]["requires_per_call_opt_in"] = json!(false);
        decision["not_authorized"] = json!(["semantic_retrieval_influence"]);

        let mut request = opt_in_runtime_influence_review_request_fixture();
        request["runtime_adapter_approved"] = json!(true);
        request["default_search_order_change_allowed"] = json!(true);
        request["changes_memory_search_order"] = json!(true);
        request["ordering_behavior_connected"] = json!(true);
        request["requested_authorization"]["request_default_search_order_change"] = json!(true);
        request["requested_authorization"]["this_packet_grants_request"] = json!(true);

        let packet = biocortex_retrieval_opt_in_runtime_influence_decision_packet(
            BioCortexRetrievalOptInRuntimeInfluenceDecisionPacketOptions {
                runtime_influence_review_request: request,
                runtime_influence_decision: decision,
                reviewer: None,
                commit: None,
                forum_post_id: None,
                memory_key: None,
            },
        );

        assert_eq!(
            packet["boundary_check"]["runtime_influence_authorized"],
            json!(false)
        );
        let blockers = packet["boundary_check"]["blockers"]
            .as_array()
            .expect("blockers");
        assert!(blockers.contains(&json!("decision_scope_not_explicit_opt_in_fts")));
        assert!(blockers.contains(&json!("decision_default_order_allowed")));
        assert!(blockers.contains(&json!("decision_default_influence_authorized")));
        assert!(blockers.contains(&json!("decision_hybrid_influence_authorized")));
        assert!(blockers.contains(&json!("decision_missing_per_call_opt_in_requirement")));
        assert!(blockers.contains(&json!("decision_not_authorized_missing_default_order")));
        assert!(blockers.contains(&json!("decision_not_authorized_missing_default_fts")));
        assert!(blockers.contains(&json!("decision_not_authorized_missing_hybrid")));
        assert!(blockers.contains(&json!("decision_not_authorized_missing_without_opt_in")));
        assert!(blockers.contains(&json!("request_requested_default_order_change")));
        assert!(blockers.contains(&json!("request_grants_approval")));
        assert!(blockers.contains(&json!("request_runtime_adapter_already_approved")));
        assert!(blockers.contains(&json!("request_default_order_allowed")));
        assert!(blockers.contains(&json!("request_changes_memory_search_order")));
        assert!(blockers.contains(&json!("request_ordering_connected")));
        assert_eq!(packet["approval_state"], json!("not_approved"));
        assert_eq!(packet["authorization_state"], json!("not_authorized"));
        assert_eq!(packet["implementation_allowed"], json!(false));
        assert_eq!(packet["runtime_adapter_approved"], json!(false));
        assert_eq!(
            packet["ordering_behavior_connection_authorized"],
            json!(false)
        );
        assert_eq!(packet["default_search_order_change_allowed"], json!(false));
        assert_eq!(packet["writes_approval"], json!(false));
        assert_eq!(packet["changes_memory_search_order"], json!(false));
        assert_eq!(packet["ordering_behavior_connected"], json!(false));
        assert_eq!(packet["may_change_search_order_now"], json!(false));
        assert_eq!(packet["may_implement_ordering_now"], json!(false));
    }

    #[test]
    fn opt_in_runtime_influence_decision_packet_consumes_aggregate_review_evidence() {
        let packet = biocortex_retrieval_opt_in_runtime_influence_decision_packet(
            BioCortexRetrievalOptInRuntimeInfluenceDecisionPacketOptions {
                runtime_influence_review_request:
                    opt_in_aggregate_backed_runtime_influence_review_request_fixture(),
                runtime_influence_decision: opt_in_runtime_influence_decision_fixture(),
                reviewer: Some("codex".to_string()),
                commit: Some("runtime-decision-commit".to_string()),
                forum_post_id: Some("104".to_string()),
                memory_key: Some("runtime-decision-memory".to_string()),
            },
        );

        assert_eq!(
            packet["boundary_check"]["runtime_influence_authorized"],
            json!(true)
        );
        assert_eq!(
            packet["boundary_check"]["aggregate_backed_review_request"],
            json!(true)
        );
        assert_eq!(
            packet["boundary_check"]["aggregate_review_evidence_ready"],
            json!(true)
        );
        assert_eq!(
            packet["boundary_check"]["legacy_review_request_without_aggregate_allowed"],
            json!(false)
        );
        assert_eq!(
            packet["boundary_check"]["aggregate_contract_ok"],
            json!(true)
        );
        assert_eq!(
            packet["boundary_check"]["aggregate_summary_redacted"],
            json!(true)
        );
        assert_eq!(
            packet["boundary_check"]["aggregate_safe_for_decision"],
            json!(true)
        );
        assert_eq!(
            packet["request_summary"]["aggregate_backed_review_request"],
            json!(true)
        );
        assert_eq!(
            packet["request_summary"]["aggregate_review_evidence_state"],
            json!("redacted_aggregate_ready")
        );
        assert_eq!(
            packet["request_summary"]["redacted_evidence_aggregate_provided"],
            json!(true)
        );
        assert_eq!(
            packet["request_summary"]["redacted_evidence_aggregate_ready"],
            json!(true)
        );
        assert_eq!(
            packet["request_summary"]["aggregate_review_state"],
            json!("redacted_aggregate_ready")
        );
        assert_eq!(
            packet["request_summary"]["controlled_rank_movement_observed"],
            json!(true)
        );
        assert_eq!(
            packet["request_summary"]["expanded_coverage_without_additional_movement"],
            json!(true)
        );
        assert_eq!(
            packet["request_summary"]["aggregate_default_influence_ready"],
            json!(false)
        );
        assert_eq!(
            packet["request_summary"]["default_influence_ready"],
            json!(false)
        );
        assert_eq!(
            packet["request_summary"]["aggregate_human_review_required"],
            json!(true)
        );
        assert_eq!(
            packet["request_summary"]["redacted_evidence_aggregate_summary_included"],
            json!(false)
        );
        assert_eq!(
            packet["decision_summary"]["default_retrieval_influence_authorized"],
            json!(false)
        );
        assert_eq!(
            packet["decision_summary"]["hybrid_retrieval_influence_authorized"],
            json!(false)
        );
        assert_eq!(
            packet["decision_summary"]["semantic_retrieval_influence_authorized"],
            json!(false)
        );
        assert_eq!(packet["changes_memory_search_order"], json!(false));
        assert_eq!(packet["ordering_behavior_connected"], json!(false));
        assert_eq!(packet["may_change_search_order_now"], json!(false));

        let serialized = serde_json::to_string(&packet).expect("packet json");
        assert!(!serialized.contains("secret aggregate raw query"));
        assert!(!serialized.contains("secret_aggregate_key"));
        assert!(!serialized.contains("secret aggregate content"));
    }

    #[test]
    fn opt_in_runtime_influence_decision_packet_preserves_capability_ledger_context() {
        let packet = biocortex_retrieval_opt_in_runtime_influence_decision_packet(
            BioCortexRetrievalOptInRuntimeInfluenceDecisionPacketOptions {
                runtime_influence_review_request:
                    opt_in_aggregate_and_ledger_backed_runtime_influence_review_request_fixture(),
                runtime_influence_decision: opt_in_runtime_influence_decision_fixture(),
                reviewer: Some("codex".to_string()),
                commit: Some("runtime-decision-commit".to_string()),
                forum_post_id: Some("104".to_string()),
                memory_key: Some("runtime-decision-memory".to_string()),
            },
        );

        assert_eq!(
            packet["input_contract"]["accepts_capability_ledger_backed_review_request"],
            json!(true)
        );
        assert_eq!(
            packet["input_contract"]["requires_capability_ledger_safe_when_provided"],
            json!(true)
        );
        assert_eq!(
            packet["input_contract"]["capability_ledger_report_packet_included"],
            json!(false)
        );
        assert_eq!(
            packet["request_summary"]["capability_ledger_backed_review_request"],
            json!(true)
        );
        assert_eq!(
            packet["request_summary"]["capability_ledger_state"],
            json!("capability_ledger_accepted_for_review_only")
        );
        assert_eq!(
            packet["request_summary"]["capability_ledger_report_packet_provided"],
            json!(true)
        );
        assert_eq!(
            packet["request_summary"]["capability_ledger_report_packet_accepted"],
            json!(true)
        );
        assert_eq!(
            packet["request_summary"]["capability_ledger_read_only_confirmed"],
            json!(true)
        );
        assert_eq!(
            packet["request_summary"]["capability_ledger_input_schema"],
            json!("biocortex.capability_ledger.v3")
        );
        assert_eq!(
            packet["request_summary"]["capability_ledger_input_schema_version"],
            json!("3")
        );
        assert_eq!(
            packet["request_summary"]["capability_ledger_can_authorize_runtime_influence"],
            json!(false)
        );
        assert_eq!(
            packet["request_summary"]["capability_ledger_report_packet_included"],
            json!(false)
        );
        assert_eq!(
            packet["boundary_check"]["capability_ledger_backed_review_request"],
            json!(true)
        );
        assert_eq!(
            packet["boundary_check"]["capability_ledger_safe_for_decision"],
            json!(true)
        );
        assert_eq!(
            packet["boundary_check"]["legacy_review_request_without_capability_ledger_allowed"],
            json!(false)
        );
        assert_eq!(
            packet["boundary_check"]["capability_ledger_contract_ok"],
            json!(true)
        );
        assert_eq!(
            packet["boundary_check"]["capability_ledger_summary_redacted"],
            json!(true)
        );
        assert_eq!(
            packet["boundary_check"]["capability_ledger_accepted"],
            json!(true)
        );
        assert_eq!(
            packet["boundary_check"]["capability_ledger_read_only_confirmed"],
            json!(true)
        );
        assert_eq!(
            packet["boundary_check"]["capability_ledger_authorizes_runtime_influence"],
            json!(false)
        );
        assert_eq!(packet["implementation_allowed"], json!(true));
        assert_eq!(packet["runtime_adapter_approved"], json!(true));
        assert_eq!(packet["default_search_order_change_allowed"], json!(false));

        let serialized = serde_json::to_string(&packet).expect("packet json");
        assert!(!serialized.contains("secret ledger markdown"));
        assert!(!serialized.contains("secret ledger raw query"));
        assert!(!serialized.contains("secret_ledger_key"));
        assert!(!serialized.contains("secret ledger content"));
        assert!(!serialized.contains("report_markdown"));
    }

    #[test]
    fn opt_in_runtime_influence_decision_packet_rejects_capability_ledger_runtime_decision_words() {
        let mut request =
            opt_in_aggregate_and_ledger_backed_runtime_influence_review_request_fixture();
        request["evidence_summary"]["capability_ledger_downstream_action"] =
            json!("enable_runtime");
        request["evidence_summary"]["capability_ledger_integration_decision"] =
            json!("runtime_admission");

        let packet = biocortex_retrieval_opt_in_runtime_influence_decision_packet(
            BioCortexRetrievalOptInRuntimeInfluenceDecisionPacketOptions {
                runtime_influence_review_request: request,
                runtime_influence_decision: opt_in_runtime_influence_decision_fixture(),
                reviewer: Some("codex".to_string()),
                commit: Some("runtime-decision-commit".to_string()),
                forum_post_id: Some("104".to_string()),
                memory_key: Some("runtime-decision-memory".to_string()),
            },
        );

        assert_eq!(
            packet["boundary_check"]["runtime_influence_authorized"],
            json!(false)
        );
        assert_eq!(
            packet["boundary_check"]["capability_ledger_safe_for_decision"],
            json!(false)
        );
        let blockers = packet["boundary_check"]["blockers"]
            .as_array()
            .expect("blockers");
        assert!(blockers.contains(&json!(
            "request_capability_ledger_decision_not_display_only"
        )));
        assert_eq!(packet["implementation_allowed"], json!(false));
        assert_eq!(packet["runtime_adapter_approved"], json!(false));
        assert_eq!(packet["default_search_order_change_allowed"], json!(false));
    }

    #[test]
    fn opt_in_runtime_influence_decision_packet_consumes_post_runtime_evidence_summary() {
        let packet = biocortex_retrieval_opt_in_runtime_influence_decision_packet(
            BioCortexRetrievalOptInRuntimeInfluenceDecisionPacketOptions {
                runtime_influence_review_request:
                    opt_in_post_runtime_evidence_runtime_influence_review_request_fixture(),
                runtime_influence_decision: opt_in_runtime_influence_decision_fixture(),
                reviewer: Some("codex".to_string()),
                commit: Some("runtime-decision-commit".to_string()),
                forum_post_id: Some("104".to_string()),
                memory_key: Some("runtime-decision-memory".to_string()),
            },
        );

        assert_eq!(
            packet["boundary_check"]["runtime_influence_authorized"],
            json!(true)
        );
        assert_eq!(
            packet["input_contract"]["accepts_post_runtime_evidence_summary_review_request"],
            json!(true)
        );
        assert_eq!(
            packet["input_contract"]["requires_post_runtime_evidence_summary_ready_when_provided"],
            json!(true)
        );
        assert_eq!(
            packet["input_contract"]["post_runtime_evidence_summary_included"],
            json!(false)
        );
        assert_eq!(
            packet["request_summary"]["post_runtime_evidence_summary_backed_review_request"],
            json!(true)
        );
        assert_eq!(
            packet["request_summary"]["post_runtime_evidence_summary_state"],
            json!("post_runtime_evidence_ready")
        );
        assert_eq!(
            packet["request_summary"]["post_runtime_evidence_summary_provided"],
            json!(true)
        );
        assert_eq!(
            packet["request_summary"]["post_runtime_evidence_summary_ready"],
            json!(true)
        );
        assert_eq!(
            packet["request_summary"]["post_runtime_evidence_summary_review_state"],
            json!("post_runtime_evidence_ready")
        );
        assert_eq!(
            packet["request_summary"]["post_runtime_controlled_rank_movement_observed"],
            json!(true)
        );
        assert_eq!(
            packet["request_summary"]["post_runtime_runtime_readiness_packet_provided"],
            json!(true)
        );
        assert_eq!(
            packet["request_summary"]["post_runtime_runtime_readiness_requirement_met"],
            json!(true)
        );
        assert_eq!(
            packet["request_summary"]["post_runtime_readiness_gated_batch_evidence_ready"],
            json!(true)
        );
        assert_eq!(
            packet["request_summary"]["post_runtime_batch_transition_gated"],
            json!(true)
        );
        assert_eq!(
            packet["request_summary"]["post_runtime_batch_evidence_source"],
            json!("runtime_transition_gated_batch_diagnostics")
        );
        assert_eq!(
            packet["request_summary"]["post_runtime_evidence_summary_default_influence_ready"],
            json!(false)
        );
        assert_eq!(
            packet["request_summary"]["post_runtime_evidence_summary_included"],
            json!(false)
        );
        assert_eq!(
            packet["boundary_check"]["post_runtime_evidence_summary_backed_review_request"],
            json!(true)
        );
        assert_eq!(
            packet["boundary_check"]["post_runtime_evidence_summary_ready"],
            json!(true)
        );
        assert_eq!(
            packet["boundary_check"]
                ["legacy_review_request_without_post_runtime_evidence_summary_allowed"],
            json!(false)
        );
        assert_eq!(
            packet["boundary_check"]["post_runtime_evidence_summary_contract_ok"],
            json!(true)
        );
        assert_eq!(
            packet["boundary_check"]["post_runtime_evidence_summary_redacted"],
            json!(true)
        );
        assert_eq!(
            packet["boundary_check"]["post_runtime_evidence_summary_safe_for_decision"],
            json!(true)
        );
        assert_eq!(
            packet["boundary_check"]
                ["post_runtime_evidence_summary_default_influence_still_not_ready"],
            json!(true)
        );
        assert_eq!(
            packet["boundary_check"]["post_runtime_runtime_readiness_requirement_met"],
            json!(true)
        );
        assert_eq!(
            packet["boundary_check"]["post_runtime_readiness_gated_batch_evidence_ready"],
            json!(true)
        );
        assert_eq!(
            packet["boundary_check"]["post_runtime_batch_transition_gated"],
            json!(true)
        );
        assert_eq!(
            packet["boundary_check"]["aggregate_safe_for_decision"],
            json!(true)
        );
        assert_eq!(packet["implementation_allowed"], json!(true));
        assert_eq!(packet["runtime_adapter_approved"], json!(true));
        assert_eq!(packet["may_implement_ordering_now"], json!(true));

        let serialized = serde_json::to_string(&packet).expect("packet json");
        assert!(!serialized.contains("secret evidence summary raw query"));
        assert!(!serialized.contains("secret_evidence_summary_key"));
        assert!(!serialized.contains("secret evidence summary content"));
        assert!(!serialized.contains("secret aggregate raw query"));
        assert!(!serialized.contains("secret_aggregate_key"));
        assert!(!serialized.contains("secret aggregate content"));
    }

    #[test]
    fn opt_in_runtime_influence_decision_packet_blocks_unready_post_runtime_evidence_summary() {
        let mut request = opt_in_post_runtime_evidence_runtime_influence_review_request_fixture();
        request["evidence_summary"]["post_runtime_evidence_summary_ready"] = json!(false);
        request["boundary_check"]["post_runtime_evidence_summary_ready"] = json!(false);

        let packet = biocortex_retrieval_opt_in_runtime_influence_decision_packet(
            BioCortexRetrievalOptInRuntimeInfluenceDecisionPacketOptions {
                runtime_influence_review_request: request,
                runtime_influence_decision: opt_in_runtime_influence_decision_fixture(),
                reviewer: None,
                commit: None,
                forum_post_id: None,
                memory_key: None,
            },
        );

        assert_eq!(
            packet["boundary_check"]["runtime_influence_authorized"],
            json!(false)
        );
        assert_eq!(
            packet["request_summary"]["post_runtime_evidence_summary_state"],
            json!("blocked")
        );
        assert_eq!(
            packet["boundary_check"]["post_runtime_evidence_summary_safe_for_decision"],
            json!(false)
        );
        let blockers = packet["boundary_check"]["blockers"]
            .as_array()
            .expect("blockers");
        assert!(blockers.contains(&json!(
            "request_post_runtime_evidence_not_ready_for_decision"
        )));
        assert_eq!(packet["implementation_allowed"], json!(false));
        assert_eq!(packet["runtime_adapter_approved"], json!(false));
        assert_eq!(
            packet["ordering_behavior_connection_authorized"],
            json!(false)
        );
        assert_eq!(packet["may_implement_ordering_now"], json!(false));
    }

    #[test]
    fn opt_in_runtime_influence_decision_packet_blocks_unready_aggregate_evidence() {
        let mut request = opt_in_aggregate_backed_runtime_influence_review_request_fixture();
        request["evidence_summary"]["redacted_evidence_aggregate_ready"] = json!(false);
        request["boundary_check"]["redacted_evidence_aggregate_ready"] = json!(false);

        let packet = biocortex_retrieval_opt_in_runtime_influence_decision_packet(
            BioCortexRetrievalOptInRuntimeInfluenceDecisionPacketOptions {
                runtime_influence_review_request: request,
                runtime_influence_decision: opt_in_runtime_influence_decision_fixture(),
                reviewer: None,
                commit: None,
                forum_post_id: None,
                memory_key: None,
            },
        );

        assert_eq!(
            packet["boundary_check"]["runtime_influence_authorized"],
            json!(false)
        );
        assert_eq!(
            packet["request_summary"]["aggregate_review_evidence_state"],
            json!("blocked")
        );
        assert_eq!(
            packet["boundary_check"]["aggregate_safe_for_decision"],
            json!(false)
        );
        let blockers = packet["boundary_check"]["blockers"]
            .as_array()
            .expect("blockers");
        assert!(blockers.contains(&json!("request_aggregate_not_ready_for_decision")));
        assert_eq!(packet["implementation_allowed"], json!(false));
        assert_eq!(packet["runtime_adapter_approved"], json!(false));
        assert_eq!(
            packet["ordering_behavior_connection_authorized"],
            json!(false)
        );
        assert_eq!(packet["may_implement_ordering_now"], json!(false));
    }

    async fn empty_sqlite_store(label: &str) -> (ab_store::SqliteStore, std::path::PathBuf) {
        let dir = std::env::temp_dir().join(format!(
            "ab-biocortex-shadow-{label}-{}-{}",
            std::process::id(),
            std::time::SystemTime::now()
                .duration_since(std::time::UNIX_EPOCH)
                .map(|d| d.as_nanos())
                .unwrap_or(0)
        ));
        tokio::fs::create_dir_all(&dir).await.expect("mkdir");
        let store = ab_store::SqliteStore::open(&dir.join("state.db"))
            .await
            .expect("open sqlite store");
        (store, dir)
    }

    #[tokio::test]
    async fn opt_in_store_trial_reports_aggregate_backed_decision_packet_preflight() {
        let packet = biocortex_retrieval_opt_in_runtime_influence_decision_packet(
            BioCortexRetrievalOptInRuntimeInfluenceDecisionPacketOptions {
                runtime_influence_review_request:
                    opt_in_aggregate_backed_runtime_influence_review_request_fixture(),
                runtime_influence_decision: opt_in_runtime_influence_decision_fixture(),
                reviewer: Some("codex".to_string()),
                commit: Some("runtime-decision-commit".to_string()),
                forum_post_id: Some("104".to_string()),
                memory_key: Some("runtime-decision-memory".to_string()),
            },
        );
        let (store, dir) = empty_sqlite_store("aggregate-store-trial").await;

        let trial = biocortex_retrieval_opt_in_store_trial(
            &store,
            BioCortexRetrievalOptInStoreTrialOptions {
                runtime_influence_decision_packet: packet,
                query: "secret aggregate-backed store trial query".to_string(),
                tags_any: vec![],
                limit: 3,
                mode: "fts".to_string(),
                per_call_opt_in: true,
                checkout: None,
                timeout_ms: 1_000,
                coverage_threshold: 0.5,
                blend_alpha: CANDIDATE_STRONG_RETRIEVAL_ALPHA,
                attempt_id: Some("aggregate-store-trial".to_string()),
                commit: Some("runtime-decision-commit".to_string()),
            },
        )
        .await;

        assert_eq!(
            trial["input_contract"]["accepts_aggregate_backed_decision_packet"],
            json!(true)
        );
        assert_eq!(
            trial["input_contract"]["redacted_evidence_aggregate_included"],
            json!(false)
        );
        assert_eq!(
            trial["input_contract"]["aggregate_evidence_summary_included"],
            json!(false)
        );
        assert_eq!(
            trial["runtime_preflight"]["decision_packet_authorized"],
            json!(true)
        );
        assert_eq!(
            trial["runtime_preflight"]["decision_packet_aggregate_backed"],
            json!(true)
        );
        assert_eq!(
            trial["runtime_preflight"]["decision_packet_aggregate_review_evidence_ready"],
            json!(true)
        );
        assert_eq!(
            trial["runtime_preflight"]["legacy_decision_packet_without_aggregate_allowed"],
            json!(false)
        );
        assert_eq!(
            trial["runtime_preflight"]["decision_packet_aggregate_safe_for_trial"],
            json!(true)
        );
        assert_eq!(
            trial["runtime_preflight"]["decision_packet_aggregate_review_evidence_state"],
            json!("redacted_aggregate_ready")
        );
        assert_eq!(
            trial["runtime_preflight"]["decision_packet_aggregate_default_influence_ready"],
            json!(false)
        );
        assert_eq!(
            trial["runtime_preflight"]["decision_packet_aggregate_human_review_required"],
            json!(true)
        );
        assert_eq!(trial["runtime_preflight"]["adapter_allowed"], json!(false));
        assert!(trial["runtime_preflight"]["blockers"]
            .as_array()
            .expect("blockers")
            .contains(&json!("baseline_empty")));
        assert_eq!(trial["runs_biocortex"], json!(false));

        let serialized = serde_json::to_string(&trial).expect("trial json");
        assert!(!serialized.contains("secret aggregate-backed store trial query"));
        let _ = tokio::fs::remove_dir_all(dir).await;
    }

    #[tokio::test]
    async fn opt_in_store_trial_blocks_bad_aggregate_backed_decision_packet() {
        let mut packet = biocortex_retrieval_opt_in_runtime_influence_decision_packet(
            BioCortexRetrievalOptInRuntimeInfluenceDecisionPacketOptions {
                runtime_influence_review_request:
                    opt_in_aggregate_backed_runtime_influence_review_request_fixture(),
                runtime_influence_decision: opt_in_runtime_influence_decision_fixture(),
                reviewer: None,
                commit: None,
                forum_post_id: None,
                memory_key: None,
            },
        );
        packet["boundary_check"]["aggregate_review_evidence_ready"] = json!(false);
        packet["boundary_check"]["aggregate_safe_for_decision"] = json!(false);
        let (store, dir) = empty_sqlite_store("bad-aggregate-store-trial").await;

        let trial = biocortex_retrieval_opt_in_store_trial(
            &store,
            BioCortexRetrievalOptInStoreTrialOptions {
                runtime_influence_decision_packet: packet,
                query: "secret bad aggregate store trial query".to_string(),
                tags_any: vec![],
                limit: 3,
                mode: "fts".to_string(),
                per_call_opt_in: true,
                checkout: None,
                timeout_ms: 1_000,
                coverage_threshold: 0.5,
                blend_alpha: CANDIDATE_STRONG_RETRIEVAL_ALPHA,
                attempt_id: Some("bad-aggregate-store-trial".to_string()),
                commit: None,
            },
        )
        .await;

        assert_eq!(
            trial["runtime_preflight"]["decision_packet_aggregate_backed"],
            json!(true)
        );
        assert_eq!(
            trial["runtime_preflight"]["decision_packet_aggregate_review_evidence_ready"],
            json!(false)
        );
        assert_eq!(
            trial["runtime_preflight"]["decision_packet_aggregate_safe_for_trial"],
            json!(false)
        );
        let blockers = trial["runtime_preflight"]["blockers"]
            .as_array()
            .expect("blockers");
        assert!(blockers.contains(&json!(
            "decision_packet_aggregate_review_evidence_not_ready"
        )));
        assert!(blockers.contains(&json!("decision_packet_aggregate_not_safe_for_trial")));
        assert_eq!(trial["runtime_preflight"]["adapter_allowed"], json!(false));
        assert_eq!(trial["runs_biocortex"], json!(false));

        let serialized = serde_json::to_string(&trial).expect("trial json");
        assert!(!serialized.contains("secret bad aggregate store trial query"));
        let _ = tokio::fs::remove_dir_all(dir).await;
    }

    #[tokio::test]
    async fn opt_in_store_trial_reports_post_runtime_evidence_summary_decision_packet_preflight() {
        let packet = biocortex_retrieval_opt_in_runtime_influence_decision_packet(
            BioCortexRetrievalOptInRuntimeInfluenceDecisionPacketOptions {
                runtime_influence_review_request:
                    opt_in_post_runtime_evidence_runtime_influence_review_request_fixture(),
                runtime_influence_decision: opt_in_runtime_influence_decision_fixture(),
                reviewer: Some("codex".to_string()),
                commit: Some("runtime-decision-commit".to_string()),
                forum_post_id: Some("104".to_string()),
                memory_key: Some("runtime-decision-memory".to_string()),
            },
        );
        let (store, dir) = empty_sqlite_store("post-runtime-evidence-store-trial").await;

        let trial = biocortex_retrieval_opt_in_store_trial(
            &store,
            BioCortexRetrievalOptInStoreTrialOptions {
                runtime_influence_decision_packet: packet,
                query: "secret post-runtime evidence store trial query".to_string(),
                tags_any: vec![],
                limit: 3,
                mode: "fts".to_string(),
                per_call_opt_in: true,
                checkout: None,
                timeout_ms: 1_000,
                coverage_threshold: 0.5,
                blend_alpha: CANDIDATE_STRONG_RETRIEVAL_ALPHA,
                attempt_id: Some("post-runtime-evidence-store-trial".to_string()),
                commit: Some("runtime-decision-commit".to_string()),
            },
        )
        .await;

        assert_eq!(
            trial["input_contract"]["accepts_post_runtime_evidence_summary_decision_packet"],
            json!(true)
        );
        assert_eq!(
            trial["input_contract"]["requires_post_runtime_evidence_summary_ready_when_provided"],
            json!(true)
        );
        assert_eq!(
            trial["input_contract"]["post_runtime_evidence_summary_included"],
            json!(false)
        );
        assert_eq!(
            trial["runtime_preflight"]["decision_packet_authorized"],
            json!(true)
        );
        assert_eq!(
            trial["runtime_preflight"]["decision_packet_post_runtime_evidence_summary_backed"],
            json!(true)
        );
        assert_eq!(
            trial["runtime_preflight"]["decision_packet_post_runtime_evidence_summary_ready"],
            json!(true)
        );
        assert_eq!(
            trial["runtime_preflight"]
                ["legacy_decision_packet_without_post_runtime_evidence_summary_allowed"],
            json!(false)
        );
        assert_eq!(
            trial["runtime_preflight"]["decision_packet_post_runtime_evidence_summary_contract_ok"],
            json!(true)
        );
        assert_eq!(
            trial["runtime_preflight"]["decision_packet_post_runtime_evidence_summary_redacted"],
            json!(true)
        );
        assert_eq!(
            trial["runtime_preflight"]
                ["decision_packet_post_runtime_evidence_summary_safe_for_trial"],
            json!(true)
        );
        assert_eq!(
            trial["runtime_preflight"]["decision_packet_post_runtime_evidence_summary_state"],
            json!("post_runtime_evidence_ready")
        );
        assert_eq!(
            trial["runtime_preflight"]
                ["decision_packet_post_runtime_evidence_summary_default_influence_ready"],
            json!(false)
        );
        assert_eq!(
            trial["runtime_preflight"]["decision_packet_post_runtime_readiness_requirement_met"],
            json!(true)
        );
        assert_eq!(
            trial["runtime_preflight"]["decision_packet_post_runtime_gated_batch_evidence_ready"],
            json!(true)
        );
        assert_eq!(
            trial["runtime_preflight"]["decision_packet_post_runtime_batch_transition_gated"],
            json!(true)
        );
        assert_eq!(trial["runtime_preflight"]["adapter_allowed"], json!(false));
        assert!(trial["runtime_preflight"]["blockers"]
            .as_array()
            .expect("blockers")
            .contains(&json!("baseline_empty")));
        assert_eq!(trial["runs_biocortex"], json!(false));

        let serialized = serde_json::to_string(&trial).expect("trial json");
        assert!(!serialized.contains("secret post-runtime evidence store trial query"));
        assert!(!serialized.contains("secret evidence summary raw query"));
        assert!(!serialized.contains("secret_evidence_summary_key"));
        assert!(!serialized.contains("secret evidence summary content"));
        let _ = tokio::fs::remove_dir_all(dir).await;
    }

    #[tokio::test]
    async fn opt_in_store_trial_blocks_bad_post_runtime_evidence_summary_decision_packet() {
        let mut packet = biocortex_retrieval_opt_in_runtime_influence_decision_packet(
            BioCortexRetrievalOptInRuntimeInfluenceDecisionPacketOptions {
                runtime_influence_review_request:
                    opt_in_post_runtime_evidence_runtime_influence_review_request_fixture(),
                runtime_influence_decision: opt_in_runtime_influence_decision_fixture(),
                reviewer: None,
                commit: None,
                forum_post_id: None,
                memory_key: None,
            },
        );
        packet["request_summary"]["post_runtime_evidence_summary_ready"] = json!(false);
        packet["boundary_check"]["post_runtime_evidence_summary_ready"] = json!(false);
        packet["boundary_check"]["post_runtime_evidence_summary_safe_for_decision"] = json!(false);
        let (store, dir) = empty_sqlite_store("bad-post-runtime-evidence-store-trial").await;

        let trial = biocortex_retrieval_opt_in_store_trial(
            &store,
            BioCortexRetrievalOptInStoreTrialOptions {
                runtime_influence_decision_packet: packet,
                query: "secret bad post-runtime evidence store trial query".to_string(),
                tags_any: vec![],
                limit: 3,
                mode: "fts".to_string(),
                per_call_opt_in: true,
                checkout: None,
                timeout_ms: 1_000,
                coverage_threshold: 0.5,
                blend_alpha: CANDIDATE_STRONG_RETRIEVAL_ALPHA,
                attempt_id: Some("bad-post-runtime-evidence-store-trial".to_string()),
                commit: None,
            },
        )
        .await;

        assert_eq!(
            trial["runtime_preflight"]["decision_packet_post_runtime_evidence_summary_backed"],
            json!(true)
        );
        assert_eq!(
            trial["runtime_preflight"]["decision_packet_post_runtime_evidence_summary_ready"],
            json!(false)
        );
        assert_eq!(
            trial["runtime_preflight"]
                ["decision_packet_post_runtime_evidence_summary_safe_for_trial"],
            json!(false)
        );
        let blockers = trial["runtime_preflight"]["blockers"]
            .as_array()
            .expect("blockers");
        assert!(blockers.contains(&json!(
            "decision_packet_post_runtime_evidence_summary_not_ready"
        )));
        assert!(blockers.contains(&json!(
            "decision_packet_post_runtime_evidence_not_safe_for_trial"
        )));
        assert_eq!(trial["runtime_preflight"]["adapter_allowed"], json!(false));
        assert_eq!(trial["runs_biocortex"], json!(false));

        let serialized = serde_json::to_string(&trial).expect("trial json");
        assert!(!serialized.contains("secret bad post-runtime evidence store trial query"));
        assert!(!serialized.contains("secret evidence summary raw query"));
        assert!(!serialized.contains("secret_evidence_summary_key"));
        assert!(!serialized.contains("secret evidence summary content"));
        let _ = tokio::fs::remove_dir_all(dir).await;
    }

    fn opt_in_runtime_readiness_store_trial_fixture() -> Value {
        json!({
            "schema": BIOCORTEX_RETRIEVAL_OPT_IN_STORE_TRIAL_SCHEMA,
            "store_trial": true,
            "status": "baseline_returned",
            "input_contract": {
                "runtime_influence_decision_packet_schema": BIOCORTEX_RETRIEVAL_OPT_IN_RUNTIME_INFLUENCE_DECISION_PACKET_SCHEMA,
                "runtime_influence_decision_packet_included": false,
                "accepts_aggregate_backed_decision_packet": true,
                "requires_aggregate_ready_when_provided": true,
                "redacted_evidence_aggregate_included": false,
                "aggregate_evidence_summary_included": false,
                "raw_query_included": false,
                "raw_keys_included": false,
                "content_included": false,
                "side_signal_raw_included": false
            },
            "runtime_preflight": {
                "adapter_allowed": false,
                "blockers": ["baseline_empty"],
                "compile_feature_enabled": true,
                "runtime_enabled": true,
                "operator_disabled": false,
                "decision_packet_authorized": true,
                "decision_packet_aggregate_backed": true,
                "decision_packet_aggregate_review_evidence_ready": true,
                "legacy_decision_packet_without_aggregate_allowed": false,
                "decision_packet_aggregate_contract_ok": true,
                "decision_packet_aggregate_summary_redacted": true,
                "decision_packet_aggregate_safe_for_trial": true
            },
            "baseline_order": {
                "completed": true,
                "key_count": 0,
                "raw_keys_included": false,
                "content_included": false
            },
            "side_signal": {
                "attempted": false,
                "status": "not_run_preflight_blocked",
                "raw_included": false,
                "candidate_keys_included": false,
                "content_included": false
            },
            "returned_order": {
                "source": "baseline",
                "baseline_returned": true,
                "contract_changes_memory_search_order": false,
                "actual_return_order_changed": false,
                "hash_matches_baseline": true
            },
            "calls_memory_search": true,
            "runs_biocortex": false,
            "registers_embedding_backend": false,
            "changes_memory_search_order": false,
            "default_search_order_change_allowed": false,
            "default_calls_unchanged": true,
            "raw_query_included": false,
            "raw_keys_included": false,
            "content_included": false,
            "side_signal_raw_included": false,
            "raw_query": "secret readiness store query",
            "raw_key": "secret_readiness_store_key",
            "content": "secret readiness store content"
        })
    }

    fn opt_in_runtime_readiness_post_runtime_store_trial_fixture() -> Value {
        let mut trial = opt_in_runtime_readiness_store_trial_fixture();
        trial["input_contract"]["accepts_post_runtime_evidence_summary_decision_packet"] =
            json!(true);
        trial["input_contract"]["requires_post_runtime_evidence_summary_ready_when_provided"] =
            json!(true);
        trial["input_contract"]["post_runtime_evidence_summary_included"] = json!(false);
        trial["runtime_preflight"]["decision_packet_post_runtime_evidence_summary_backed"] =
            json!(true);
        trial["runtime_preflight"]["decision_packet_post_runtime_evidence_summary_ready"] =
            json!(true);
        trial["runtime_preflight"]
            ["legacy_decision_packet_without_post_runtime_evidence_summary_allowed"] = json!(false);
        trial["runtime_preflight"]
            ["decision_packet_post_runtime_evidence_summary_safe_for_trial"] = json!(true);
        trial["runtime_preflight"]["decision_packet_post_runtime_evidence_summary_state"] =
            json!("post_runtime_evidence_ready");
        trial
    }

    fn opt_in_runtime_readiness_batch_fixture() -> Value {
        let row = |index: usize| {
            json!({
                "index": index,
                "class_label": "empty_live_probe",
                "status": "baseline_returned",
                "movement_class": "preflight_blocked",
                "preflight": {
                    "adapter_allowed": false,
                    "blocker_count": 1,
                    "compile_feature_enabled": true,
                    "runtime_enabled": true,
                    "operator_disabled": false,
                    "decision_packet_authorized": true,
                    "decision_packet_aggregate_backed": true,
                    "decision_packet_aggregate_review_evidence_ready": true,
                    "legacy_decision_packet_without_aggregate_allowed": false,
                    "decision_packet_aggregate_safe_for_trial": true
                },
                "baseline": {
                    "completed": true,
                    "key_count": 0
                },
                "side_signal": {
                    "attempted": false,
                    "status": "not_run_preflight_blocked",
                    "matched_candidate_count": 0,
                    "coverage": 0.0,
                    "latency_ms": 0.0
                },
                "returned_order": {
                    "source": "baseline",
                    "baseline_returned": true,
                    "contract_changes_memory_search_order": false,
                    "actual_return_order_changed": false,
                    "hash_matches_baseline": true
                },
                "calls_memory_search": true,
                "runs_biocortex": false,
                "changes_memory_search_order": false,
                "default_calls_unchanged": true,
                "raw_query_included": false,
                "raw_keys_included": false,
                "content_included": false,
                "side_signal_raw_included": false
            })
        };
        json!({
            "schema": BIOCORTEX_RETRIEVAL_OPT_IN_BATCH_DIAGNOSTICS_SCHEMA,
            "batch_diagnostics": true,
            "status": "completed",
            "input_contract": {
                "runtime_influence_decision_packet_schema": BIOCORTEX_RETRIEVAL_OPT_IN_RUNTIME_INFLUENCE_DECISION_PACKET_SCHEMA,
                "runtime_influence_decision_packet_included": false,
                "accepts_aggregate_backed_decision_packet": true,
                "requires_aggregate_ready_when_provided": true,
                "redacted_evidence_aggregate_included": false,
                "aggregate_evidence_summary_included": false,
                "raw_queries_included": false,
                "raw_keys_included": false,
                "content_included": false,
                "side_signal_raw_included": false
            },
            "summary": {
                "query_count": 2,
                "baseline_completed_count": 2,
                "baseline_empty_count": 2,
                "adapter_allowed_count": 0,
                "side_signal_attempted_count": 0,
                "side_signal_ok_count": 0,
                "experimental_source_count": 0,
                "actual_order_changed_count": 0,
                "calls_memory_search_count": 2,
                "runs_biocortex_count": 0,
                "default_calls_unchanged_count": 2,
                "raw_flagged_count": 0
            },
            "query_results": [row(0), row(1)],
            "safety": {
                "calls_memory_search_all": true,
                "runs_biocortex_any": false,
                "changes_memory_search_order_any": false,
                "actual_return_order_changed_any": false,
                "default_calls_unchanged_all": true,
                "raw_flags_all_false": true
            },
            "approval_writes_allowed": false,
            "writes_approval": false,
            "registers_embedding_backend": false,
            "default_search_order_change_allowed": false,
            "default_calls_unchanged": true,
            "raw_queries_included": false,
            "raw_keys_included": false,
            "content_included": false,
            "side_signal_raw_included": false,
            "raw_query": "secret readiness batch query",
            "raw_key": "secret_readiness_batch_key",
            "content": "secret readiness batch content"
        })
    }

    #[test]
    fn opt_in_runtime_readiness_packet_accepts_empty_live_probe_with_aggregate_evidence() {
        let decision_packet = biocortex_retrieval_opt_in_runtime_influence_decision_packet(
            BioCortexRetrievalOptInRuntimeInfluenceDecisionPacketOptions {
                runtime_influence_review_request:
                    opt_in_aggregate_backed_runtime_influence_review_request_fixture(),
                runtime_influence_decision: opt_in_runtime_influence_decision_fixture(),
                reviewer: Some("codex".to_string()),
                commit: Some("runtime-decision-commit".to_string()),
                forum_post_id: Some("104".to_string()),
                memory_key: Some("runtime-decision-memory".to_string()),
            },
        );

        let packet = biocortex_retrieval_opt_in_runtime_readiness_packet(
            BioCortexRetrievalOptInRuntimeReadinessPacketOptions {
                runtime_influence_decision_packet: decision_packet,
                store_trial: opt_in_runtime_readiness_store_trial_fixture(),
                batch_diagnostics: opt_in_runtime_readiness_batch_fixture(),
                reviewer: Some("codex".to_string()),
                commit: Some("runtime-readiness-commit".to_string()),
                forum_post_id: Some("104".to_string()),
                memory_key: Some("runtime-readiness-memory".to_string()),
            },
        );

        assert_eq!(
            packet["schema"],
            json!(BIOCORTEX_RETRIEVAL_OPT_IN_RUNTIME_READINESS_PACKET_SCHEMA)
        );
        assert_eq!(packet["runtime_readiness_packet"], json!(true));
        assert_eq!(packet["readiness"]["control_plane_ready"], json!(true));
        assert_eq!(
            packet["readiness"]["live_probe_state"],
            json!("control_plane_ready_no_live_candidates")
        );
        assert_eq!(
            packet["readiness"]["may_accept_controlled_explicit_opt_in_fts_calls"],
            json!(true)
        );
        assert_eq!(
            packet["readiness"]["live_order_influence_ready"],
            json!(false)
        );
        assert_eq!(packet["readiness"]["default_influence_ready"], json!(false));
        assert_eq!(
            packet["boundary_check"]["runtime_readiness_ready"],
            json!(true)
        );
        assert_eq!(
            packet["boundary_check"]["blockers"]
                .as_array()
                .expect("blockers")
                .len(),
            0
        );
        assert_eq!(
            packet["input_contract"]["runtime_influence_decision_packet_included"],
            json!(false)
        );
        assert_eq!(
            packet["input_contract"]["store_trial_included"],
            json!(false)
        );
        assert_eq!(
            packet["input_contract"]["batch_diagnostics_included"],
            json!(false)
        );
        assert_eq!(packet["calls_memory_search"], json!(false));
        assert_eq!(packet["runs_biocortex"], json!(false));
        assert_eq!(packet["changes_memory_search_order"], json!(false));
        assert_eq!(packet["default_search_order_change_allowed"], json!(false));

        let serialized = serde_json::to_string(&packet).expect("readiness json");
        assert!(!serialized.contains("secret readiness store query"));
        assert!(!serialized.contains("secret_readiness_store_key"));
        assert!(!serialized.contains("secret readiness store content"));
        assert!(!serialized.contains("secret readiness batch query"));
        assert!(!serialized.contains("secret_readiness_batch_key"));
        assert!(!serialized.contains("secret readiness batch content"));
    }

    #[test]
    fn opt_in_runtime_readiness_packet_preserves_capability_ledger_context() {
        let decision_packet = biocortex_retrieval_opt_in_runtime_influence_decision_packet(
            BioCortexRetrievalOptInRuntimeInfluenceDecisionPacketOptions {
                runtime_influence_review_request:
                    opt_in_aggregate_and_ledger_backed_runtime_influence_review_request_fixture(),
                runtime_influence_decision: opt_in_runtime_influence_decision_fixture(),
                reviewer: Some("codex".to_string()),
                commit: Some("runtime-decision-commit".to_string()),
                forum_post_id: Some("104".to_string()),
                memory_key: Some("runtime-decision-memory".to_string()),
            },
        );

        let packet = biocortex_retrieval_opt_in_runtime_readiness_packet(
            BioCortexRetrievalOptInRuntimeReadinessPacketOptions {
                runtime_influence_decision_packet: decision_packet,
                store_trial: opt_in_runtime_readiness_store_trial_fixture(),
                batch_diagnostics: opt_in_runtime_readiness_batch_fixture(),
                reviewer: Some("codex".to_string()),
                commit: Some("runtime-readiness-commit".to_string()),
                forum_post_id: Some("104".to_string()),
                memory_key: Some("runtime-readiness-memory".to_string()),
            },
        );

        assert_eq!(packet["readiness"]["control_plane_ready"], json!(true));
        assert_eq!(
            packet["input_contract"]["accepts_capability_ledger_backed_decision_packet"],
            json!(true)
        );
        assert_eq!(
            packet["input_contract"]["requires_capability_ledger_safe_when_provided"],
            json!(true)
        );
        assert_eq!(
            packet["input_contract"]["capability_ledger_report_packet_included"],
            json!(false)
        );
        assert_eq!(
            packet["decision_summary"]["capability_ledger_backed_review_request"],
            json!(true)
        );
        assert_eq!(
            packet["decision_summary"]["capability_ledger_safe_for_decision"],
            json!(true)
        );
        assert_eq!(
            packet["decision_summary"]["legacy_decision_packet_without_capability_ledger_allowed"],
            json!(false)
        );
        assert_eq!(
            packet["decision_summary"]["capability_ledger_input_schema"],
            json!("biocortex.capability_ledger.v3")
        );
        assert_eq!(
            packet["decision_summary"]["capability_ledger_input_schema_version"],
            json!("3")
        );
        assert_eq!(
            packet["decision_summary"]["capability_ledger_can_authorize_runtime_influence"],
            json!(false)
        );
        assert_eq!(
            packet["decision_summary"]["capability_ledger_report_packet_included"],
            json!(false)
        );
        assert_eq!(
            packet["boundary_check"]["capability_ledger_backed_decision_packet"],
            json!(true)
        );
        assert_eq!(
            packet["boundary_check"]["capability_ledger_safe_for_readiness"],
            json!(true)
        );
        assert_eq!(
            packet["boundary_check"]["legacy_decision_packet_without_capability_ledger_allowed"],
            json!(false)
        );
        assert_eq!(
            packet["boundary_check"]["capability_ledger_authorizes_runtime_influence"],
            json!(false)
        );
        assert_eq!(packet["boundary_check"]["blockers"], json!([]));
        assert_eq!(packet["calls_memory_search"], json!(false));
        assert_eq!(packet["runs_biocortex"], json!(false));
        assert_eq!(packet["default_search_order_change_allowed"], json!(false));

        let serialized = serde_json::to_string(&packet).expect("readiness json");
        assert!(!serialized.contains("secret ledger markdown"));
        assert!(!serialized.contains("secret ledger raw query"));
        assert!(!serialized.contains("secret_ledger_key"));
        assert!(!serialized.contains("secret ledger content"));
        assert!(!serialized.contains("report_markdown"));
        assert!(!serialized.contains("secret readiness store query"));
        assert!(!serialized.contains("secret_readiness_store_key"));
        assert!(!serialized.contains("secret readiness batch query"));
        assert!(!serialized.contains("secret_readiness_batch_key"));
    }

    #[tokio::test]
    async fn opt_in_runtime_readiness_packet_accepts_gated_batch_evidence() {
        let _env = EnvRestore::capture(&[BIOCORTEX_RETRIEVAL_DISABLE_ENV]);
        std::env::remove_var(BIOCORTEX_RETRIEVAL_DISABLE_ENV);
        let decision_packet = biocortex_retrieval_opt_in_runtime_influence_decision_packet(
            BioCortexRetrievalOptInRuntimeInfluenceDecisionPacketOptions {
                runtime_influence_review_request:
                    opt_in_aggregate_backed_runtime_influence_review_request_fixture(),
                runtime_influence_decision: opt_in_runtime_influence_decision_fixture(),
                reviewer: Some("codex".to_string()),
                commit: Some("runtime-decision-commit".to_string()),
                forum_post_id: Some("104".to_string()),
                memory_key: Some("runtime-decision-memory".to_string()),
            },
        );
        let (store, dir) = empty_sqlite_store("runtime-readiness-gated-batch").await;
        let gated_batch = biocortex_retrieval_opt_in_gated_batch_diagnostics(
            &store,
            BioCortexRetrievalOptInGatedBatchDiagnosticsOptions {
                runtime_transition_gate: opt_in_runtime_transition_gate_fixture(),
                runtime_influence_decision_packet: decision_packet.clone(),
                queries: vec![
                    BioCortexRetrievalOptInBatchQueryCase {
                        query: "secret readiness gated batch query one".to_string(),
                        class_label: Some("Gated One".to_string()),
                    },
                    BioCortexRetrievalOptInBatchQueryCase {
                        query: "secret readiness gated batch query two".to_string(),
                        class_label: Some("Gated Two".to_string()),
                    },
                ],
                tags_any: vec![],
                limit: 3,
                mode: "fts".to_string(),
                per_call_opt_in: true,
                checkout: None,
                timeout_ms: 1_000,
                coverage_threshold: 0.5,
                blend_alpha: CANDIDATE_STRONG_RETRIEVAL_ALPHA,
                attempt_id: Some("readiness-gated-batch".to_string()),
                commit: Some("runtime-transition-commit".to_string()),
            },
        )
        .await;

        let packet = biocortex_retrieval_opt_in_runtime_readiness_packet(
            BioCortexRetrievalOptInRuntimeReadinessPacketOptions {
                runtime_influence_decision_packet: decision_packet,
                store_trial: opt_in_runtime_readiness_store_trial_fixture(),
                batch_diagnostics: gated_batch,
                reviewer: Some("codex".to_string()),
                commit: Some("runtime-readiness-gated-batch-commit".to_string()),
                forum_post_id: Some("104".to_string()),
                memory_key: Some("runtime-readiness-gated-batch-memory".to_string()),
            },
        );

        assert_eq!(packet["readiness"]["control_plane_ready"], json!(true));
        assert_eq!(
            packet["input_contract"]["batch_diagnostics_evidence_source"],
            json!("runtime_transition_gated_batch_diagnostics")
        );
        assert_eq!(
            packet["input_contract"]["batch_diagnostics_transition_gated"],
            json!(true)
        );
        assert_eq!(packet["batch_summary"]["gated_schema_ok"], json!(true));
        assert_eq!(
            packet["batch_summary"]["evidence_source"],
            json!("runtime_transition_gated_batch_diagnostics")
        );
        assert_eq!(packet["batch_summary"]["transition_gated"], json!(true));
        assert_eq!(packet["batch_summary"]["transition_gate_ok"], json!(true));
        assert_eq!(
            packet["batch_summary"]["transition_gate_allowed_count"],
            json!(2)
        );
        assert_eq!(
            packet["batch_summary"]["transition_gate_blocked_count"],
            json!(0)
        );
        assert_eq!(
            packet["batch_summary"]["store_trial_called_count"],
            json!(2)
        );
        assert_eq!(
            packet["batch_summary"]["calls_memory_search_count"],
            json!(2)
        );
        assert_eq!(
            packet["readiness"]["live_probe_state"],
            json!("control_plane_ready_no_live_candidates")
        );
        assert_eq!(packet["calls_memory_search"], json!(false));
        assert_eq!(packet["runs_biocortex"], json!(false));
        assert_eq!(packet["changes_memory_search_order"], json!(false));
        assert_eq!(packet["default_search_order_change_allowed"], json!(false));

        let serialized = serde_json::to_string(&packet).expect("readiness json");
        assert!(!serialized.contains("secret readiness gated batch query one"));
        assert!(!serialized.contains("secret readiness gated batch query two"));
        let _ = tokio::fs::remove_dir_all(dir).await;
    }

    #[tokio::test]
    async fn opt_in_runtime_readiness_packet_consumes_post_runtime_evidence_summary_preflight() {
        let _env = EnvRestore::capture(&[BIOCORTEX_RETRIEVAL_DISABLE_ENV]);
        std::env::remove_var(BIOCORTEX_RETRIEVAL_DISABLE_ENV);
        let decision_packet = biocortex_retrieval_opt_in_runtime_influence_decision_packet(
            BioCortexRetrievalOptInRuntimeInfluenceDecisionPacketOptions {
                runtime_influence_review_request:
                    opt_in_post_runtime_evidence_runtime_influence_review_request_fixture(),
                runtime_influence_decision: opt_in_runtime_influence_decision_fixture(),
                reviewer: Some("codex".to_string()),
                commit: Some("runtime-decision-commit".to_string()),
                forum_post_id: Some("104".to_string()),
                memory_key: Some("runtime-decision-memory".to_string()),
            },
        );
        let (store, dir) = empty_sqlite_store("runtime-readiness-post-runtime-evidence").await;
        let gated_batch = biocortex_retrieval_opt_in_gated_batch_diagnostics(
            &store,
            BioCortexRetrievalOptInGatedBatchDiagnosticsOptions {
                runtime_transition_gate: opt_in_runtime_transition_gate_fixture(),
                runtime_influence_decision_packet: decision_packet.clone(),
                queries: vec![
                    BioCortexRetrievalOptInBatchQueryCase {
                        query: "secret post-runtime readiness batch query one".to_string(),
                        class_label: Some("Evidence One".to_string()),
                    },
                    BioCortexRetrievalOptInBatchQueryCase {
                        query: "secret post-runtime readiness batch query two".to_string(),
                        class_label: Some("Evidence Two".to_string()),
                    },
                ],
                tags_any: vec![],
                limit: 3,
                mode: "fts".to_string(),
                per_call_opt_in: true,
                checkout: None,
                timeout_ms: 1_000,
                coverage_threshold: 0.5,
                blend_alpha: CANDIDATE_STRONG_RETRIEVAL_ALPHA,
                attempt_id: Some("readiness-post-runtime-evidence".to_string()),
                commit: Some("runtime-transition-commit".to_string()),
            },
        )
        .await;

        let packet = biocortex_retrieval_opt_in_runtime_readiness_packet(
            BioCortexRetrievalOptInRuntimeReadinessPacketOptions {
                runtime_influence_decision_packet: decision_packet,
                store_trial: opt_in_runtime_readiness_post_runtime_store_trial_fixture(),
                batch_diagnostics: gated_batch,
                reviewer: Some("codex".to_string()),
                commit: Some("runtime-readiness-post-runtime-evidence-commit".to_string()),
                forum_post_id: Some("104".to_string()),
                memory_key: Some("runtime-readiness-post-runtime-evidence-memory".to_string()),
            },
        );

        assert_eq!(packet["readiness"]["control_plane_ready"], json!(true));
        assert_eq!(
            packet["input_contract"]["accepts_post_runtime_evidence_summary_decision_packet"],
            json!(true)
        );
        assert_eq!(
            packet["input_contract"]["requires_post_runtime_evidence_summary_ready_when_provided"],
            json!(true)
        );
        assert_eq!(
            packet["input_contract"]["post_runtime_evidence_summary_included"],
            json!(false)
        );
        assert_eq!(
            packet["decision_summary"]["post_runtime_evidence_summary_backed_review_request"],
            json!(true)
        );
        assert_eq!(
            packet["decision_summary"]["post_runtime_evidence_summary_ready"],
            json!(true)
        );
        assert_eq!(
            packet["decision_summary"]
                ["legacy_decision_packet_without_post_runtime_evidence_summary_allowed"],
            json!(false)
        );
        assert_eq!(
            packet["decision_summary"]["post_runtime_evidence_summary_safe_for_decision"],
            json!(true)
        );
        assert_eq!(
            packet["decision_summary"]["post_runtime_readiness_gated_batch_evidence_ready"],
            json!(true)
        );
        assert_eq!(
            packet["decision_summary"]["post_runtime_batch_transition_gated"],
            json!(true)
        );
        assert_eq!(
            packet["decision_summary"]["post_runtime_evidence_summary_state"],
            json!("post_runtime_evidence_ready")
        );
        assert_eq!(
            packet["store_trial_summary"]["post_runtime_evidence_preflight_ok"],
            json!(true)
        );
        assert_eq!(
            packet["batch_summary"]["post_runtime_evidence_preflight_ok"],
            json!(true)
        );
        assert_eq!(
            packet["batch_summary"]["evidence_source"],
            json!("runtime_transition_gated_batch_diagnostics")
        );
        assert_eq!(
            packet["boundary_check"]["runtime_readiness_ready"],
            json!(true)
        );
        assert_eq!(packet["boundary_check"]["blockers"], json!([]));
        assert_eq!(packet["calls_memory_search"], json!(false));
        assert_eq!(packet["runs_biocortex"], json!(false));
        assert_eq!(packet["changes_memory_search_order"], json!(false));
        assert_eq!(packet["default_search_order_change_allowed"], json!(false));

        let serialized = serde_json::to_string(&packet).expect("readiness json");
        assert!(!serialized.contains("secret post-runtime readiness batch query one"));
        assert!(!serialized.contains("secret post-runtime readiness batch query two"));
        assert!(!serialized.contains("secret evidence summary raw query"));
        assert!(!serialized.contains("secret_evidence_summary_key"));
        assert!(!serialized.contains("secret evidence summary content"));
        let _ = tokio::fs::remove_dir_all(dir).await;
    }

    #[test]
    fn opt_in_runtime_readiness_packet_blocks_missing_post_runtime_evidence_summary_preflight() {
        let decision_packet = biocortex_retrieval_opt_in_runtime_influence_decision_packet(
            BioCortexRetrievalOptInRuntimeInfluenceDecisionPacketOptions {
                runtime_influence_review_request:
                    opt_in_post_runtime_evidence_runtime_influence_review_request_fixture(),
                runtime_influence_decision: opt_in_runtime_influence_decision_fixture(),
                reviewer: None,
                commit: None,
                forum_post_id: None,
                memory_key: None,
            },
        );
        let mut batch = opt_in_runtime_readiness_batch_fixture();
        batch["raw_query"] = json!("secret missing post-runtime readiness batch query");

        let packet = biocortex_retrieval_opt_in_runtime_readiness_packet(
            BioCortexRetrievalOptInRuntimeReadinessPacketOptions {
                runtime_influence_decision_packet: decision_packet,
                store_trial: opt_in_runtime_readiness_post_runtime_store_trial_fixture(),
                batch_diagnostics: batch,
                reviewer: None,
                commit: None,
                forum_post_id: None,
                memory_key: None,
            },
        );

        assert_eq!(packet["readiness"]["control_plane_ready"], json!(false));
        assert_eq!(
            packet["boundary_check"]["runtime_readiness_ready"],
            json!(false)
        );
        assert_eq!(
            packet["batch_summary"]["post_runtime_evidence_preflight_ok"],
            json!(false)
        );
        let blockers = packet["boundary_check"]["blockers"]
            .as_array()
            .expect("blockers");
        assert!(blockers.contains(&json!("batch_diagnostics_input_contract_unexpected")));
        assert!(blockers.contains(&json!("batch_query_post_runtime_evidence_not_ready")));
        assert_eq!(
            packet["readiness"]["may_accept_controlled_explicit_opt_in_fts_calls"],
            json!(false)
        );

        let serialized = serde_json::to_string(&packet).expect("readiness json");
        assert!(!serialized.contains("secret missing post-runtime readiness batch query"));
        assert!(!serialized.contains("secret evidence summary raw query"));
        assert!(!serialized.contains("secret_evidence_summary_key"));
        assert!(!serialized.contains("secret evidence summary content"));
    }

    #[test]
    fn opt_in_runtime_readiness_packet_blocks_bad_downstream_aggregate_preflight() {
        let decision_packet = biocortex_retrieval_opt_in_runtime_influence_decision_packet(
            BioCortexRetrievalOptInRuntimeInfluenceDecisionPacketOptions {
                runtime_influence_review_request:
                    opt_in_aggregate_backed_runtime_influence_review_request_fixture(),
                runtime_influence_decision: opt_in_runtime_influence_decision_fixture(),
                reviewer: None,
                commit: None,
                forum_post_id: None,
                memory_key: None,
            },
        );
        let store_trial = opt_in_runtime_readiness_store_trial_fixture();
        let mut batch = opt_in_runtime_readiness_batch_fixture();
        batch["query_results"][0]["preflight"]["decision_packet_aggregate_review_evidence_ready"] =
            json!(false);
        batch["safety"]["raw_flags_all_false"] = json!(false);
        batch["raw_query"] = json!("secret bad readiness batch query");

        let packet = biocortex_retrieval_opt_in_runtime_readiness_packet(
            BioCortexRetrievalOptInRuntimeReadinessPacketOptions {
                runtime_influence_decision_packet: decision_packet,
                store_trial,
                batch_diagnostics: batch,
                reviewer: None,
                commit: None,
                forum_post_id: None,
                memory_key: None,
            },
        );

        assert_eq!(packet["readiness"]["control_plane_ready"], json!(false));
        assert_eq!(
            packet["boundary_check"]["runtime_readiness_ready"],
            json!(false)
        );
        let blockers = packet["boundary_check"]["blockers"]
            .as_array()
            .expect("blockers");
        assert!(blockers.contains(&json!("batch_query_aggregate_evidence_not_ready")));
        assert!(blockers.contains(&json!("batch_diagnostics_raw_input_included")));
        assert_eq!(
            packet["readiness"]["may_accept_controlled_explicit_opt_in_fts_calls"],
            json!(false)
        );

        let serialized = serde_json::to_string(&packet).expect("readiness json");
        assert!(!serialized.contains("secret bad readiness batch query"));
    }

    fn opt_in_runtime_transition_readiness_fixture() -> Value {
        let decision_packet = biocortex_retrieval_opt_in_runtime_influence_decision_packet(
            BioCortexRetrievalOptInRuntimeInfluenceDecisionPacketOptions {
                runtime_influence_review_request:
                    opt_in_aggregate_backed_runtime_influence_review_request_fixture(),
                runtime_influence_decision: opt_in_runtime_influence_decision_fixture(),
                reviewer: Some("codex".to_string()),
                commit: Some("runtime-decision-commit".to_string()),
                forum_post_id: Some("104".to_string()),
                memory_key: Some("runtime-decision-memory".to_string()),
            },
        );
        biocortex_retrieval_opt_in_runtime_readiness_packet(
            BioCortexRetrievalOptInRuntimeReadinessPacketOptions {
                runtime_influence_decision_packet: decision_packet,
                store_trial: opt_in_runtime_readiness_store_trial_fixture(),
                batch_diagnostics: opt_in_runtime_readiness_batch_fixture(),
                reviewer: Some("codex".to_string()),
                commit: Some("runtime-readiness-commit".to_string()),
                forum_post_id: Some("104".to_string()),
                memory_key: Some("runtime-readiness-memory".to_string()),
            },
        )
    }

    fn opt_in_runtime_transition_gate_fixture() -> Value {
        biocortex_retrieval_opt_in_runtime_transition_gate(
            BioCortexRetrievalOptInRuntimeTransitionGateOptions {
                runtime_readiness_packet: opt_in_runtime_transition_readiness_fixture(),
                mode: "fts".to_string(),
                per_call_opt_in: true,
                operator_disabled: false,
                reviewer: Some("codex".to_string()),
                commit: Some("runtime-transition-commit".to_string()),
                forum_post_id: Some("104".to_string()),
                memory_key: Some("runtime-transition-memory".to_string()),
            },
        )
    }

    fn downstream_aio_checkpoint_selection_fixture() -> Value {
        json!({
            "schema": BIOCORTEX_RETRIEVAL_DOWNSTREAM_AIO_CHECKPOINT_SELECTION_SCHEMA,
            "status": "downstream_aio_integration_checkpoint_selected",
            "selected_checkpoint": {
                "id": "semantic_system_bus_lswr_action_result_runtime_evidence_checkpoint",
                "family": "semantic_system_bus",
                "surface": "lswr_action_result_runtime_evidence",
                "first_consumer": "agent_bridge_semantic_system_bus",
                "direct_aiot_consumption_selected": false
            },
            "checkpoint_contract": {
                "checkpoint_must_be_read_only": true,
                "first_handoff_schema": BIOCORTEX_RETRIEVAL_DOWNSTREAM_AIO_RUNTIME_EVIDENCE_HANDOFF_SCHEMA,
                "may_build_handoff_packet": true,
                "may_compare_against_ssb_runtime_evidence_contract": true,
                "may_enable_default_retrieval": false,
                "may_enable_hybrid_retrieval": false,
                "may_enable_semantic_retrieval": false,
                "may_write_approval": false,
                "may_mutate_default_agent_bridge_db": false,
                "may_call_aiot_runtime": false,
                "may_execute_lswr_actions_from_biocortex_evidence": false
            },
            "ssb_alignment": {
                "runtime_backed_evidence": true,
                "redacted_evidence_only": true,
                "no_laundering_boundary_required": true,
                "verification_boundary_required": true,
                "recover_field_required": true,
                "raw_available_must_not_expose_raw_payload": true
            },
            "boundary": {
                "default_search_order_change_allowed": false,
                "default_retrieval_influence_authorized": false,
                "hybrid_retrieval_influence_authorized": false,
                "semantic_retrieval_influence_authorized": false,
                "direct_aiot_runtime_use_authorized": false,
                "raw_queries_included": false,
                "raw_keys_included": false,
                "content_included": false,
                "side_signal_raw_included": false,
                "human_decision_text_included": false
            }
        })
    }

    fn downstream_aio_post_semantic_diverse_review_fixture() -> Value {
        json!({
            "schema": BIOCORTEX_RETRIEVAL_POST_SEMANTIC_DIVERSE_REVIEW_SCHEMA,
            "status": "post_semantic_diverse_review_recorded",
            "review_result": {
                "evidence_accepted": true,
                "ready_for_downstream_aio_checkpoint_selection": true
            },
            "accepted_evidence_summary": {
                "authorization_scope": "explicit_opt_in_fts_runtime_influence",
                "fixture_count": 4,
                "total_query_count": 8,
                "total_baseline_empty_count": 0,
                "total_runs_biocortex_count": 8,
                "total_side_signal_ok_count": 8,
                "total_experimental_source_count": 8,
                "total_actual_order_changed_count": 8,
                "expected_met": true,
                "all_cases_evidence_ready": true,
                "all_status_surfaces_blocked": true,
                "all_status_surfaces_side_effect_free": true,
                "default_memory_search_unchanged": true,
                "hybrid_retrieval_unchanged": true,
                "semantic_retrieval_unchanged": true
            },
            "boundary": {
                "default_search_order_change_allowed": false,
                "default_retrieval_influence_authorized": false,
                "hybrid_retrieval_influence_authorized": false,
                "semantic_retrieval_influence_authorized": false,
                "production_use_authorized": false,
                "raw_queries_included": false,
                "raw_keys_included": false,
                "content_included": false,
                "side_signal_raw_included": false
            },
            "required_gates_preserved": {
                "compile_feature": "biocortex-retrieval-opt-in",
                "runtime_env": BIOCORTEX_RETRIEVAL_OPT_IN_ENABLE_ENV,
                "operator_disable": BIOCORTEX_RETRIEVAL_DISABLE_ENV,
                "per_call_opt_in_required": true,
                "post_runtime_transition_gate_required": true,
                "fail_open_to_baseline_required": true
            }
        })
    }

    #[test]
    fn downstream_aio_runtime_evidence_handoff_accepts_redacted_ready_checkpoint() {
        let packet = biocortex_retrieval_downstream_aio_runtime_evidence_handoff(
            BioCortexRetrievalDownstreamAioRuntimeEvidenceHandoffOptions {
                checkpoint_selection: downstream_aio_checkpoint_selection_fixture(),
                post_semantic_diverse_review: downstream_aio_post_semantic_diverse_review_fixture(),
                controlled_trial_readiness: None,
                reviewer: Some("codex".to_string()),
                commit: Some("downstream-aio-handoff-commit".to_string()),
                forum_post_id: Some("104".to_string()),
                memory_key: Some("downstream-aio-handoff-memory".to_string()),
            },
        );

        assert_eq!(
            packet["schema"],
            json!(BIOCORTEX_RETRIEVAL_DOWNSTREAM_AIO_RUNTIME_EVIDENCE_HANDOFF_SCHEMA)
        );
        assert_eq!(packet["read_only"], json!(true));
        assert_eq!(
            packet["downstream_aio_runtime_evidence_handoff"],
            json!(true)
        );
        assert_eq!(packet["status"], json!("ready"));
        assert_eq!(
            packet["authorization_state"],
            json!("ready_for_read_only_ssb_runtime_evidence_review")
        );
        assert_eq!(packet["boundary_check"]["handoff_ready"], json!(true));
        assert_eq!(
            packet["boundary_check"]["blockers"]
                .as_array()
                .expect("blockers")
                .len(),
            0
        );
        assert_eq!(
            packet["checkpoint_summary"]["selected_checkpoint"],
            json!("semantic_system_bus_lswr_action_result_runtime_evidence_checkpoint")
        );
        assert_eq!(
            packet["checkpoint_summary"]["first_consumer"],
            json!("agent_bridge_semantic_system_bus")
        );
        assert_eq!(
            packet["redacted_evidence_summary"]["fixture_count"],
            json!(4)
        );
        assert_eq!(
            packet["redacted_evidence_summary"]["total_query_count"],
            json!(8)
        );
        assert_eq!(
            packet["redacted_evidence_summary"]["total_actual_order_changed_count"],
            json!(8)
        );
        assert_eq!(
            packet["ssb_handoff"]["recover"],
            json!("proceed_to_read_only_ssb_review")
        );
        assert_eq!(
            packet["ssb_handoff"]["may_emit_ssb_adapter_fixture"],
            json!(true)
        );
        assert_eq!(packet["calls_memory_search"], json!(false));
        assert_eq!(packet["runs_biocortex"], json!(false));
        assert_eq!(
            packet["boundary_check"]["this_packet_calls_aiot_runtime"],
            json!(false)
        );
        assert_eq!(
            packet["boundary_check"]["this_packet_executes_lswr_actions"],
            json!(false)
        );
        assert_eq!(
            packet["next_step"],
            json!("connect_handoff_packet_to_ssb_lswr_action_result_review_fixture")
        );
    }

    #[test]
    fn downstream_aio_runtime_evidence_handoff_blocks_unsafe_inputs_without_echoing_raw() {
        let mut checkpoint = downstream_aio_checkpoint_selection_fixture();
        checkpoint["selected_checkpoint"]["direct_aiot_consumption_selected"] = json!(true);
        checkpoint["checkpoint_contract"]["may_call_aiot_runtime"] = json!(true);
        checkpoint["boundary"]["raw_queries_included"] = json!(true);
        checkpoint["debug_raw_query"] = json!("secret downstream aio checkpoint raw query");

        let mut review = downstream_aio_post_semantic_diverse_review_fixture();
        review["accepted_evidence_summary"]["fixture_count"] = json!(1);
        review["accepted_evidence_summary"]["total_query_count"] = json!(1);
        review["boundary"]["default_search_order_change_allowed"] = json!(true);
        review["boundary"]["raw_keys_included"] = json!(true);
        review["debug_raw_key"] = json!("secret_downstream_aio_review_key");
        review["debug_content"] = json!("secret downstream aio review content");

        let packet = biocortex_retrieval_downstream_aio_runtime_evidence_handoff(
            BioCortexRetrievalDownstreamAioRuntimeEvidenceHandoffOptions {
                checkpoint_selection: checkpoint,
                post_semantic_diverse_review: review,
                controlled_trial_readiness: None,
                reviewer: None,
                commit: None,
                forum_post_id: None,
                memory_key: None,
            },
        );

        assert_eq!(packet["status"], json!("blocked"));
        assert_eq!(packet["boundary_check"]["handoff_ready"], json!(false));
        let blockers = packet["boundary_check"]["blockers"]
            .as_array()
            .expect("blockers");
        assert!(blockers.contains(&json!("direct_aiot_runtime_selected")));
        assert!(blockers.contains(&json!("checkpoint_boundary_not_safe")));
        assert!(blockers.contains(&json!("checkpoint_raw_input_included")));
        assert!(blockers.contains(&json!("review_default_boundary_not_safe")));
        assert!(blockers.contains(&json!("review_raw_input_included")));
        assert!(blockers.contains(&json!("review_evidence_counts_insufficient")));
        assert_eq!(
            packet["ssb_handoff"]["recover"],
            json!("fix_handoff_blockers")
        );
        assert_eq!(
            packet["ssb_handoff"]["may_emit_ssb_adapter_fixture"],
            json!(false)
        );
        assert_eq!(packet["calls_memory_search"], json!(false));
        assert_eq!(packet["runs_biocortex"], json!(false));
        assert_eq!(
            packet["boundary_check"]["this_packet_calls_aiot_runtime"],
            json!(false)
        );
        assert_eq!(
            packet["boundary_check"]["this_packet_executes_lswr_actions"],
            json!(false)
        );

        let serialized = serde_json::to_string(&packet).expect("handoff json");
        assert!(!serialized.contains("secret downstream aio checkpoint raw query"));
        assert!(!serialized.contains("secret_downstream_aio_review_key"));
        assert!(!serialized.contains("secret downstream aio review content"));
    }

    #[test]
    fn opt_in_runtime_transition_gate_allows_only_readiness_gated_fts_opt_in() {
        let gate = biocortex_retrieval_opt_in_runtime_transition_gate(
            BioCortexRetrievalOptInRuntimeTransitionGateOptions {
                runtime_readiness_packet: opt_in_runtime_transition_readiness_fixture(),
                mode: "fts".to_string(),
                per_call_opt_in: true,
                operator_disabled: false,
                reviewer: Some("codex".to_string()),
                commit: Some("runtime-transition-commit".to_string()),
                forum_post_id: Some("104".to_string()),
                memory_key: Some("runtime-transition-memory".to_string()),
            },
        );

        assert_eq!(
            gate["schema"],
            json!(BIOCORTEX_RETRIEVAL_OPT_IN_RUNTIME_TRANSITION_GATE_SCHEMA)
        );
        assert_eq!(gate["read_only"], json!(true));
        assert_eq!(gate["runtime_transition_gate"], json!(true));
        assert_eq!(gate["status"], json!("transition_allowed"));
        assert_eq!(gate["requested_transition"]["mode_authorized"], json!(true));
        assert_eq!(gate["requested_transition"]["per_call_opt_in"], json!(true));
        assert_eq!(
            gate["requested_transition"]["hybrid_retrieval_influence_requested"],
            json!(false)
        );
        assert_eq!(
            gate["requested_transition"]["semantic_retrieval_influence_requested"],
            json!(false)
        );
        assert_eq!(
            gate["readiness_summary"]["control_plane_ready"],
            json!(true)
        );
        assert_eq!(
            gate["readiness_summary"]["live_probe_state"],
            json!("control_plane_ready_no_live_candidates")
        );
        assert_eq!(gate["transition"]["transition_allowed"], json!(true));
        assert_eq!(
            gate["transition"]["may_run_runtime_adapter_for_explicit_opt_in_fts"],
            json!(true)
        );
        assert_eq!(
            gate["transition"]["may_change_default_memory_search_order"],
            json!(false)
        );
        assert_eq!(
            gate["boundary_check"]["runtime_transition_allowed"],
            json!(true)
        );
        assert_eq!(
            gate["boundary_check"]["blockers"]
                .as_array()
                .expect("blockers")
                .len(),
            0
        );
        assert_eq!(gate["calls_memory_search"], json!(false));
        assert_eq!(gate["runs_biocortex"], json!(false));
        assert_eq!(gate["changes_memory_search_order"], json!(false));
        assert_eq!(gate["default_search_order_change_allowed"], json!(false));
    }

    #[test]
    fn opt_in_runtime_transition_gate_preserves_capability_ledger_context() {
        let decision_packet = biocortex_retrieval_opt_in_runtime_influence_decision_packet(
            BioCortexRetrievalOptInRuntimeInfluenceDecisionPacketOptions {
                runtime_influence_review_request:
                    opt_in_aggregate_and_ledger_backed_runtime_influence_review_request_fixture(),
                runtime_influence_decision: opt_in_runtime_influence_decision_fixture(),
                reviewer: Some("codex".to_string()),
                commit: Some("runtime-decision-commit".to_string()),
                forum_post_id: Some("104".to_string()),
                memory_key: Some("runtime-decision-memory".to_string()),
            },
        );
        let readiness = biocortex_retrieval_opt_in_runtime_readiness_packet(
            BioCortexRetrievalOptInRuntimeReadinessPacketOptions {
                runtime_influence_decision_packet: decision_packet,
                store_trial: opt_in_runtime_readiness_store_trial_fixture(),
                batch_diagnostics: opt_in_runtime_readiness_batch_fixture(),
                reviewer: Some("codex".to_string()),
                commit: Some("runtime-readiness-commit".to_string()),
                forum_post_id: Some("104".to_string()),
                memory_key: Some("runtime-readiness-memory".to_string()),
            },
        );

        let gate = biocortex_retrieval_opt_in_runtime_transition_gate(
            BioCortexRetrievalOptInRuntimeTransitionGateOptions {
                runtime_readiness_packet: readiness,
                mode: "fts".to_string(),
                per_call_opt_in: true,
                operator_disabled: false,
                reviewer: Some("codex".to_string()),
                commit: Some("runtime-transition-commit".to_string()),
                forum_post_id: Some("104".to_string()),
                memory_key: Some("runtime-transition-memory".to_string()),
            },
        );

        assert_eq!(gate["status"], json!("transition_allowed"));
        assert_eq!(
            gate["input_contract"]["accepts_capability_ledger_backed_readiness_packet"],
            json!(true)
        );
        assert_eq!(
            gate["input_contract"]["requires_capability_ledger_safe_when_provided"],
            json!(true)
        );
        assert_eq!(
            gate["input_contract"]["capability_ledger_report_packet_included"],
            json!(false)
        );
        assert_eq!(
            gate["readiness_summary"]["capability_ledger_backed_review_request"],
            json!(true)
        );
        assert_eq!(
            gate["readiness_summary"]["capability_ledger_safe_for_transition"],
            json!(true)
        );
        assert_eq!(
            gate["readiness_summary"]["legacy_readiness_packet_without_capability_ledger_allowed"],
            json!(false)
        );
        assert_eq!(
            gate["readiness_summary"]["capability_ledger_input_schema"],
            json!("biocortex.capability_ledger.v3")
        );
        assert_eq!(
            gate["readiness_summary"]["capability_ledger_input_schema_version"],
            json!("3")
        );
        assert_eq!(
            gate["readiness_summary"]["capability_ledger_can_authorize_runtime_influence"],
            json!(false)
        );
        assert_eq!(
            gate["readiness_summary"]["capability_ledger_report_packet_included"],
            json!(false)
        );
        assert_eq!(
            gate["transition"]["capability_ledger_can_authorize_runtime_influence"],
            json!(false)
        );
        assert_eq!(
            gate["boundary_check"]["capability_ledger_backed_readiness_packet"],
            json!(true)
        );
        assert_eq!(
            gate["boundary_check"]["capability_ledger_safe_for_transition"],
            json!(true)
        );
        assert_eq!(
            gate["boundary_check"]["legacy_readiness_packet_without_capability_ledger_allowed"],
            json!(false)
        );
        assert_eq!(
            gate["boundary_check"]["capability_ledger_authorizes_runtime_influence"],
            json!(false)
        );
        assert_eq!(gate["boundary_check"]["blockers"], json!([]));
        assert_eq!(gate["calls_memory_search"], json!(false));
        assert_eq!(gate["runs_biocortex"], json!(false));
        assert_eq!(gate["default_search_order_change_allowed"], json!(false));

        let serialized = serde_json::to_string(&gate).expect("transition gate json");
        assert!(!serialized.contains("secret ledger markdown"));
        assert!(!serialized.contains("secret ledger raw query"));
        assert!(!serialized.contains("secret_ledger_key"));
        assert!(!serialized.contains("secret ledger content"));
        assert!(!serialized.contains("report_markdown"));
        assert!(!serialized.contains("secret readiness store query"));
        assert!(!serialized.contains("secret_readiness_store_key"));
        assert!(!serialized.contains("secret readiness batch query"));
        assert!(!serialized.contains("secret_readiness_batch_key"));
    }

    #[test]
    fn opt_in_runtime_transition_gate_blocks_bad_capability_ledger_readiness() {
        let mut readiness = opt_in_runtime_transition_readiness_fixture();
        readiness["decision_summary"]["capability_ledger_backed_review_request"] = json!(true);
        readiness["decision_summary"]["capability_ledger_safe_for_decision"] = json!(false);
        readiness["decision_summary"]["legacy_decision_packet_without_capability_ledger_allowed"] =
            json!(false);
        readiness["decision_summary"]["capability_ledger_can_authorize_runtime_influence"] =
            json!(true);
        readiness["decision_summary"]["capability_ledger_report_packet_included"] = json!(false);
        readiness["boundary_check"]["capability_ledger_backed_decision_packet"] = json!(true);
        readiness["boundary_check"]["capability_ledger_safe_for_readiness"] = json!(false);
        readiness["boundary_check"]["legacy_decision_packet_without_capability_ledger_allowed"] =
            json!(false);
        readiness["boundary_check"]["capability_ledger_authorizes_runtime_influence"] = json!(true);

        let gate = biocortex_retrieval_opt_in_runtime_transition_gate(
            BioCortexRetrievalOptInRuntimeTransitionGateOptions {
                runtime_readiness_packet: readiness,
                mode: "fts".to_string(),
                per_call_opt_in: true,
                operator_disabled: false,
                reviewer: None,
                commit: None,
                forum_post_id: None,
                memory_key: None,
            },
        );

        assert_eq!(gate["status"], json!("blocked"));
        assert_eq!(gate["transition"]["transition_allowed"], json!(false));
        assert_eq!(
            gate["readiness_summary"]["capability_ledger_backed_review_request"],
            json!(true)
        );
        assert_eq!(
            gate["readiness_summary"]["capability_ledger_safe_for_transition"],
            json!(false)
        );
        assert_eq!(
            gate["boundary_check"]["capability_ledger_authorizes_runtime_influence"],
            json!(true)
        );
        let blockers = gate["boundary_check"]["blockers"]
            .as_array()
            .expect("blockers");
        assert!(blockers.contains(&json!("readiness_capability_ledger_not_safe")));
        assert_eq!(gate["calls_memory_search"], json!(false));
        assert_eq!(gate["runs_biocortex"], json!(false));
        assert_eq!(gate["changes_memory_search_order"], json!(false));
        assert_eq!(gate["default_search_order_change_allowed"], json!(false));
    }

    #[tokio::test]
    async fn opt_in_runtime_transition_gate_reports_post_runtime_evidence_summary_readiness() {
        let _env = EnvRestore::capture(&[BIOCORTEX_RETRIEVAL_DISABLE_ENV]);
        std::env::remove_var(BIOCORTEX_RETRIEVAL_DISABLE_ENV);
        let decision_packet = biocortex_retrieval_opt_in_runtime_influence_decision_packet(
            BioCortexRetrievalOptInRuntimeInfluenceDecisionPacketOptions {
                runtime_influence_review_request:
                    opt_in_post_runtime_evidence_runtime_influence_review_request_fixture(),
                runtime_influence_decision: opt_in_runtime_influence_decision_fixture(),
                reviewer: Some("codex".to_string()),
                commit: Some("runtime-decision-commit".to_string()),
                forum_post_id: Some("104".to_string()),
                memory_key: Some("runtime-decision-memory".to_string()),
            },
        );
        let (store, dir) = empty_sqlite_store("runtime-transition-post-runtime-evidence").await;
        let gated_batch = biocortex_retrieval_opt_in_gated_batch_diagnostics(
            &store,
            BioCortexRetrievalOptInGatedBatchDiagnosticsOptions {
                runtime_transition_gate: opt_in_runtime_transition_gate_fixture(),
                runtime_influence_decision_packet: decision_packet.clone(),
                queries: vec![
                    BioCortexRetrievalOptInBatchQueryCase {
                        query: "secret post-runtime transition batch query one".to_string(),
                        class_label: Some("Evidence One".to_string()),
                    },
                    BioCortexRetrievalOptInBatchQueryCase {
                        query: "secret post-runtime transition batch query two".to_string(),
                        class_label: Some("Evidence Two".to_string()),
                    },
                ],
                tags_any: vec![],
                limit: 3,
                mode: "fts".to_string(),
                per_call_opt_in: true,
                checkout: None,
                timeout_ms: 1_000,
                coverage_threshold: 0.5,
                blend_alpha: CANDIDATE_STRONG_RETRIEVAL_ALPHA,
                attempt_id: Some("transition-post-runtime-evidence".to_string()),
                commit: Some("runtime-transition-commit".to_string()),
            },
        )
        .await;
        let readiness = biocortex_retrieval_opt_in_runtime_readiness_packet(
            BioCortexRetrievalOptInRuntimeReadinessPacketOptions {
                runtime_influence_decision_packet: decision_packet,
                store_trial: opt_in_runtime_readiness_post_runtime_store_trial_fixture(),
                batch_diagnostics: gated_batch,
                reviewer: Some("codex".to_string()),
                commit: Some("runtime-readiness-post-runtime-evidence-commit".to_string()),
                forum_post_id: Some("104".to_string()),
                memory_key: Some("runtime-readiness-post-runtime-evidence-memory".to_string()),
            },
        );

        let gate = biocortex_retrieval_opt_in_runtime_transition_gate(
            BioCortexRetrievalOptInRuntimeTransitionGateOptions {
                runtime_readiness_packet: readiness,
                mode: "fts".to_string(),
                per_call_opt_in: true,
                operator_disabled: false,
                reviewer: Some("codex".to_string()),
                commit: Some("runtime-transition-post-runtime-evidence-commit".to_string()),
                forum_post_id: Some("104".to_string()),
                memory_key: Some("runtime-transition-post-runtime-evidence-memory".to_string()),
            },
        );

        assert_eq!(gate["status"], json!("transition_allowed"));
        assert_eq!(gate["transition"]["transition_allowed"], json!(true));
        assert_eq!(
            gate["readiness_summary"]["post_runtime_evidence_summary_backed"],
            json!(true)
        );
        assert_eq!(
            gate["readiness_summary"]["post_runtime_evidence_summary_ready"],
            json!(true)
        );
        assert_eq!(
            gate["readiness_summary"]
                ["legacy_decision_packet_without_post_runtime_evidence_summary_allowed"],
            json!(false)
        );
        assert_eq!(
            gate["readiness_summary"]["post_runtime_evidence_summary_state"],
            json!("post_runtime_evidence_ready")
        );
        assert_eq!(
            gate["readiness_summary"]["post_runtime_batch_evidence_source"],
            json!("runtime_transition_gated_batch_diagnostics")
        );
        assert_eq!(
            gate["readiness_summary"]["post_runtime_readiness_gated_batch_evidence_ready"],
            json!(true)
        );
        assert_eq!(
            gate["readiness_summary"]["post_runtime_batch_transition_gated"],
            json!(true)
        );
        assert_eq!(
            gate["readiness_summary"]["store_post_runtime_evidence_preflight_ok"],
            json!(true)
        );
        assert_eq!(
            gate["readiness_summary"]["batch_post_runtime_evidence_preflight_ok"],
            json!(true)
        );
        assert_eq!(gate["boundary_check"]["blockers"], json!([]));
        assert_eq!(gate["calls_memory_search"], json!(false));
        assert_eq!(gate["runs_biocortex"], json!(false));
        assert_eq!(gate["changes_memory_search_order"], json!(false));
        assert_eq!(gate["default_search_order_change_allowed"], json!(false));

        let serialized = serde_json::to_string(&gate).expect("transition gate json");
        assert!(!serialized.contains("secret post-runtime transition batch query one"));
        assert!(!serialized.contains("secret post-runtime transition batch query two"));
        assert!(!serialized.contains("secret evidence summary raw query"));
        assert!(!serialized.contains("secret_evidence_summary_key"));
        assert!(!serialized.contains("secret evidence summary content"));
        let _ = tokio::fs::remove_dir_all(dir).await;
    }

    #[test]
    fn opt_in_runtime_transition_gate_blocks_bad_post_runtime_evidence_summary_readiness() {
        let mut readiness = opt_in_runtime_transition_readiness_fixture();
        readiness["decision_summary"]["post_runtime_evidence_summary_backed_review_request"] =
            json!(true);
        readiness["decision_summary"]["post_runtime_evidence_summary_ready"] = json!(false);
        readiness["decision_summary"]
            ["legacy_decision_packet_without_post_runtime_evidence_summary_allowed"] = json!(false);
        readiness["decision_summary"]["post_runtime_evidence_summary_safe_for_decision"] =
            json!(false);
        readiness["decision_summary"]["post_runtime_evidence_summary_default_influence_ready"] =
            json!(false);
        readiness["decision_summary"]["post_runtime_runtime_readiness_requirement_met"] =
            json!(true);
        readiness["decision_summary"]["post_runtime_readiness_gated_batch_evidence_ready"] =
            json!(false);
        readiness["decision_summary"]["post_runtime_batch_transition_gated"] = json!(false);
        readiness["decision_summary"]["post_runtime_batch_evidence_source"] =
            json!("legacy_batch_diagnostics");
        readiness["decision_summary"]["post_runtime_evidence_summary_state"] =
            json!("post_runtime_evidence_missing");
        readiness["store_trial_summary"]["post_runtime_evidence_preflight_ok"] = json!(false);
        readiness["batch_summary"]["post_runtime_evidence_preflight_ok"] = json!(false);

        let gate = biocortex_retrieval_opt_in_runtime_transition_gate(
            BioCortexRetrievalOptInRuntimeTransitionGateOptions {
                runtime_readiness_packet: readiness,
                mode: "fts".to_string(),
                per_call_opt_in: true,
                operator_disabled: false,
                reviewer: None,
                commit: None,
                forum_post_id: None,
                memory_key: None,
            },
        );

        assert_eq!(gate["status"], json!("blocked"));
        assert_eq!(gate["transition"]["transition_allowed"], json!(false));
        assert_eq!(
            gate["readiness_summary"]["post_runtime_evidence_summary_backed"],
            json!(true)
        );
        assert_eq!(
            gate["readiness_summary"]["post_runtime_evidence_summary_ready"],
            json!(false)
        );
        assert_eq!(
            gate["readiness_summary"]["store_post_runtime_evidence_preflight_ok"],
            json!(false)
        );
        assert_eq!(
            gate["readiness_summary"]["batch_post_runtime_evidence_preflight_ok"],
            json!(false)
        );
        let blockers = gate["boundary_check"]["blockers"]
            .as_array()
            .expect("blockers");
        assert!(blockers.contains(&json!("readiness_post_runtime_evidence_summary_not_ready")));
        assert_eq!(gate["calls_memory_search"], json!(false));
        assert_eq!(gate["runs_biocortex"], json!(false));
        assert_eq!(gate["changes_memory_search_order"], json!(false));
        assert_eq!(gate["default_search_order_change_allowed"], json!(false));
    }

    #[test]
    fn opt_in_runtime_transition_gate_blocks_without_explicit_fts_opt_in() {
        let mut readiness = opt_in_runtime_transition_readiness_fixture();
        readiness["raw_query"] = json!("secret transition readiness query");
        readiness["raw_key"] = json!("secret_transition_readiness_key");
        readiness["content"] = json!("secret transition readiness content");

        let gate = biocortex_retrieval_opt_in_runtime_transition_gate(
            BioCortexRetrievalOptInRuntimeTransitionGateOptions {
                runtime_readiness_packet: readiness,
                mode: "hybrid".to_string(),
                per_call_opt_in: false,
                operator_disabled: true,
                reviewer: None,
                commit: None,
                forum_post_id: None,
                memory_key: None,
            },
        );

        assert_eq!(gate["status"], json!("blocked"));
        assert_eq!(
            gate["requested_transition"]["hybrid_retrieval_influence_requested"],
            json!(true)
        );
        assert_eq!(
            gate["requested_transition"]["semantic_retrieval_influence_requested"],
            json!(false)
        );
        assert_eq!(gate["transition"]["transition_allowed"], json!(false));
        assert_eq!(
            gate["boundary_check"]["runtime_transition_allowed"],
            json!(false)
        );
        let blockers = gate["boundary_check"]["blockers"]
            .as_array()
            .expect("blockers");
        assert!(blockers.contains(&json!("requested_mode_not_authorized")));
        assert!(blockers.contains(&json!("per_call_opt_in_missing")));
        assert!(blockers.contains(&json!("operator_disabled")));
        assert_eq!(gate["calls_memory_search"], json!(false));
        assert_eq!(gate["runs_biocortex"], json!(false));
        assert_eq!(gate["changes_memory_search_order"], json!(false));
        assert_eq!(gate["default_search_order_change_allowed"], json!(false));

        let serialized = serde_json::to_string(&gate).expect("transition gate json");
        assert!(!serialized.contains("secret transition readiness query"));
        assert!(!serialized.contains("secret_transition_readiness_key"));
        assert!(!serialized.contains("secret transition readiness content"));
    }

    #[test]
    fn downstream_aio_runtime_evidence_handoff_accepts_selected_ssb_checkpoint() {
        let checkpoint_selection = json!({
            "schema": BIOCORTEX_RETRIEVAL_DOWNSTREAM_AIO_CHECKPOINT_SELECTION_SCHEMA,
            "status": "downstream_aio_integration_checkpoint_selected",
            "selected_checkpoint": {
                "id": "semantic_system_bus_lswr_action_result_runtime_evidence_checkpoint",
                "family": "semantic_system_bus",
                "surface": "lswr_action_result_runtime_evidence",
                "first_consumer": "agent_bridge_semantic_system_bus",
                "direct_aiot_consumption_selected": false
            },
            "checkpoint_contract": {
                "checkpoint_must_be_read_only": true,
                "first_handoff_schema": BIOCORTEX_RETRIEVAL_DOWNSTREAM_AIO_RUNTIME_EVIDENCE_HANDOFF_SCHEMA,
                "may_build_handoff_packet": true,
                "may_compare_against_ssb_runtime_evidence_contract": true,
                "may_enable_default_retrieval": false,
                "may_enable_hybrid_retrieval": false,
                "may_enable_semantic_retrieval": false,
                "may_write_approval": false,
                "may_mutate_default_agent_bridge_db": false,
                "may_call_aiot_runtime": false,
                "may_execute_lswr_actions_from_biocortex_evidence": false
            },
            "ssb_alignment": {
                "runtime_backed_evidence": true,
                "redacted_evidence_only": true,
                "no_laundering_boundary_required": true,
                "verification_boundary_required": true,
                "recover_field_required": true,
                "raw_available_must_not_expose_raw_payload": true
            },
            "boundary": {
                "default_search_order_change_allowed": false,
                "default_retrieval_influence_authorized": false,
                "hybrid_retrieval_influence_authorized": false,
                "semantic_retrieval_influence_authorized": false,
                "direct_aiot_runtime_use_authorized": false,
                "raw_queries_included": false,
                "raw_keys_included": false,
                "content_included": false,
                "side_signal_raw_included": false,
                "human_decision_text_included": false
            }
        });
        let review = json!({
            "schema": BIOCORTEX_RETRIEVAL_POST_SEMANTIC_DIVERSE_REVIEW_SCHEMA,
            "status": "post_semantic_diverse_review_recorded",
            "review_result": {
                "evidence_accepted": true,
                "ready_for_downstream_aio_checkpoint_selection": true
            },
            "accepted_evidence_summary": {
                "authorization_scope": "explicit_opt_in_fts_runtime_influence",
                "fixture_count": 4,
                "total_query_count": 8,
                "total_baseline_empty_count": 0,
                "total_runs_biocortex_count": 8,
                "total_side_signal_ok_count": 8,
                "total_experimental_source_count": 8,
                "total_actual_order_changed_count": 8,
                "expected_met": true,
                "all_cases_evidence_ready": true,
                "all_status_surfaces_blocked": true,
                "all_status_surfaces_side_effect_free": true,
                "default_memory_search_unchanged": true,
                "hybrid_retrieval_unchanged": true,
                "semantic_retrieval_unchanged": true
            },
            "boundary": {
                "default_search_order_change_allowed": false,
                "default_retrieval_influence_authorized": false,
                "hybrid_retrieval_influence_authorized": false,
                "semantic_retrieval_influence_authorized": false,
                "production_use_authorized": false,
                "raw_queries_included": false,
                "raw_keys_included": false,
                "content_included": false,
                "side_signal_raw_included": false
            },
            "required_gates_preserved": {
                "compile_feature": "biocortex-retrieval-opt-in",
                "runtime_env": BIOCORTEX_RETRIEVAL_OPT_IN_ENABLE_ENV,
                "operator_disable": BIOCORTEX_RETRIEVAL_DISABLE_ENV,
                "per_call_opt_in_required": true,
                "post_runtime_transition_gate_required": true,
                "fail_open_to_baseline_required": true
            }
        });

        let handoff = biocortex_retrieval_downstream_aio_runtime_evidence_handoff(
            BioCortexRetrievalDownstreamAioRuntimeEvidenceHandoffOptions {
                checkpoint_selection,
                post_semantic_diverse_review: review,
                controlled_trial_readiness: None,
                reviewer: Some("codex".to_string()),
                commit: Some("handoff-commit".to_string()),
                forum_post_id: Some("104".to_string()),
                memory_key: Some("handoff-memory".to_string()),
            },
        );

        assert_eq!(
            handoff["schema"],
            json!(BIOCORTEX_RETRIEVAL_DOWNSTREAM_AIO_RUNTIME_EVIDENCE_HANDOFF_SCHEMA)
        );
        assert_eq!(handoff["status"], json!("ready"));
        assert_eq!(handoff["boundary_check"]["handoff_ready"], json!(true));
        assert_eq!(handoff["boundary_check"]["blockers"], json!([]));
        assert_eq!(
            handoff["ssb_handoff"]["target_checkpoint"],
            json!("semantic_system_bus_lswr_action_result_runtime_evidence_checkpoint")
        );
        assert_eq!(
            handoff["ssb_handoff"]["may_compare_against_ssb_runtime_evidence_contract"],
            json!(true)
        );
        assert_eq!(
            handoff["ssb_handoff"]["may_call_aiot_runtime"],
            json!(false)
        );
        assert_eq!(
            handoff["ssb_handoff"]["may_execute_lswr_actions"],
            json!(false)
        );
        assert_eq!(handoff["calls_memory_search"], json!(false));
        assert_eq!(handoff["runs_biocortex"], json!(false));
        assert_eq!(handoff["changes_memory_search_order"], json!(false));
        assert_eq!(handoff["default_search_order_change_allowed"], json!(false));
    }

    #[tokio::test]
    async fn opt_in_gated_store_trial_blocks_before_memory_search_without_allowed_gate() {
        let mut gate = opt_in_runtime_transition_gate_fixture();
        gate["status"] = json!("blocked");
        gate["transition"]["transition_allowed"] = json!(false);
        gate["transition"]["may_call_controlled_store_trial"] = json!(false);
        gate["boundary_check"]["runtime_transition_allowed"] = json!(false);
        gate["boundary_check"]["blockers"] = json!(["forced_transition_block"]);
        let (store, dir) = empty_sqlite_store("gated-store-trial-blocked").await;

        let trial = biocortex_retrieval_opt_in_gated_store_trial(
            &store,
            BioCortexRetrievalOptInGatedStoreTrialOptions {
                runtime_transition_gate: gate,
                runtime_influence_decision_packet: Value::Null,
                query: "secret gated store trial blocked query".to_string(),
                tags_any: vec![],
                limit: 3,
                mode: "fts".to_string(),
                per_call_opt_in: true,
                checkout: None,
                timeout_ms: 1_000,
                coverage_threshold: 0.5,
                blend_alpha: CANDIDATE_STRONG_RETRIEVAL_ALPHA,
                attempt_id: Some("gated-store-trial-blocked".to_string()),
                commit: None,
            },
        )
        .await;

        assert_eq!(
            trial["schema"],
            json!(BIOCORTEX_RETRIEVAL_OPT_IN_GATED_STORE_TRIAL_SCHEMA)
        );
        assert_eq!(trial["status"], json!("transition_gate_blocked"));
        assert_eq!(trial["store_trial_called"], json!(false));
        assert_eq!(trial["calls_memory_search"], json!(false));
        assert_eq!(trial["runs_biocortex"], json!(false));
        assert_eq!(trial["changes_memory_search_order"], json!(false));
        let blockers = trial["runtime_transition_preflight"]["blockers"]
            .as_array()
            .expect("blockers");
        assert!(blockers.contains(&json!("transition_gate_status_not_allowed")));
        assert!(blockers.contains(&json!("transition_gate_boundary_not_allowed")));
        assert!(blockers.contains(&json!("transition_gate_boundary_has_blockers")));
        assert!(blockers.contains(&json!("transition_gate_transition_not_allowed")));
        assert!(blockers.contains(&json!("transition_gate_may_not_call_store_trial")));

        let serialized = serde_json::to_string(&trial).expect("gated trial json");
        assert!(!serialized.contains("secret gated store trial blocked query"));
        let _ = tokio::fs::remove_dir_all(dir).await;
    }

    #[tokio::test]
    async fn opt_in_gated_store_trial_consumes_gate_before_store_trial() {
        let _env = EnvRestore::capture(&[BIOCORTEX_RETRIEVAL_DISABLE_ENV]);
        std::env::remove_var(BIOCORTEX_RETRIEVAL_DISABLE_ENV);
        let decision_packet = biocortex_retrieval_opt_in_runtime_influence_decision_packet(
            BioCortexRetrievalOptInRuntimeInfluenceDecisionPacketOptions {
                runtime_influence_review_request:
                    opt_in_aggregate_backed_runtime_influence_review_request_fixture(),
                runtime_influence_decision: opt_in_runtime_influence_decision_fixture(),
                reviewer: Some("codex".to_string()),
                commit: Some("runtime-decision-commit".to_string()),
                forum_post_id: Some("104".to_string()),
                memory_key: Some("runtime-decision-memory".to_string()),
            },
        );
        let (store, dir) = empty_sqlite_store("gated-store-trial-allowed").await;

        let trial = biocortex_retrieval_opt_in_gated_store_trial(
            &store,
            BioCortexRetrievalOptInGatedStoreTrialOptions {
                runtime_transition_gate: opt_in_runtime_transition_gate_fixture(),
                runtime_influence_decision_packet: decision_packet,
                query: "secret gated store trial allowed query".to_string(),
                tags_any: vec![],
                limit: 3,
                mode: "fts".to_string(),
                per_call_opt_in: true,
                checkout: None,
                timeout_ms: 1_000,
                coverage_threshold: 0.5,
                blend_alpha: CANDIDATE_STRONG_RETRIEVAL_ALPHA,
                attempt_id: Some("gated-store-trial-allowed".to_string()),
                commit: Some("runtime-transition-commit".to_string()),
            },
        )
        .await;

        assert_eq!(trial["status"], json!("transition_gate_consumed"));
        assert_eq!(
            trial["runtime_transition_preflight"]["transition_gate_allowed"],
            json!(true)
        );
        assert_eq!(
            trial["runtime_transition_preflight"]["gate_post_runtime_evidence_summary_backed"],
            json!(false)
        );
        assert_eq!(
            trial["runtime_transition_preflight"]["gate_post_runtime_evidence_summary_ready"],
            json!(false)
        );
        assert_eq!(
            trial["runtime_transition_preflight"]
                ["gate_legacy_decision_packet_without_post_runtime_evidence_summary_allowed"],
            json!(true)
        );
        assert_eq!(
            trial["runtime_transition_preflight"]["blockers"]
                .as_array()
                .expect("blockers")
                .len(),
            0
        );
        assert_eq!(trial["store_trial_called"], json!(true));
        assert_eq!(trial["calls_memory_search"], json!(true));
        assert_eq!(trial["runs_biocortex"], json!(false));
        assert_eq!(trial["changes_memory_search_order"], json!(false));
        assert_eq!(
            trial["store_trial_summary"]["status"],
            json!("baseline_returned")
        );
        assert_eq!(trial["store_trial_summary"]["baseline_key_count"], json!(0));
        assert!(
            trial["store_trial_summary"]["runtime_preflight_blocker_count"]
                .as_u64()
                .unwrap_or(0)
                > 0
        );
        assert_eq!(
            trial["store_trial_summary"]["store_trial_included"],
            json!(false)
        );

        let serialized = serde_json::to_string(&trial).expect("gated trial json");
        assert!(!serialized.contains("secret gated store trial allowed query"));
        let _ = tokio::fs::remove_dir_all(dir).await;
    }

    #[tokio::test]
    async fn opt_in_gated_store_trial_blocks_bad_capability_ledger_transition_gate() {
        let mut gate = opt_in_runtime_transition_gate_fixture();
        gate["readiness_summary"]["capability_ledger_backed_review_request"] = json!(true);
        gate["readiness_summary"]["capability_ledger_safe_for_transition"] = json!(false);
        gate["readiness_summary"]["legacy_readiness_packet_without_capability_ledger_allowed"] =
            json!(false);
        gate["readiness_summary"]["capability_ledger_input_schema"] =
            json!("biocortex.capability_ledger.v3");
        gate["readiness_summary"]["capability_ledger_input_schema_version"] = json!("3");
        gate["readiness_summary"]["capability_ledger_can_authorize_runtime_influence"] =
            json!(true);
        gate["readiness_summary"]["capability_ledger_report_packet_included"] = json!(false);
        gate["transition"]["capability_ledger_can_authorize_runtime_influence"] = json!(true);
        gate["boundary_check"]["capability_ledger_backed_readiness_packet"] = json!(true);
        gate["boundary_check"]["capability_ledger_safe_for_transition"] = json!(false);
        gate["boundary_check"]["legacy_readiness_packet_without_capability_ledger_allowed"] =
            json!(false);
        gate["boundary_check"]["capability_ledger_authorizes_runtime_influence"] = json!(true);
        let (store, dir) = empty_sqlite_store("gated-store-trial-bad-ledger-gate").await;

        let trial = biocortex_retrieval_opt_in_gated_store_trial(
            &store,
            BioCortexRetrievalOptInGatedStoreTrialOptions {
                runtime_transition_gate: gate,
                runtime_influence_decision_packet: Value::Null,
                query: "secret bad capability ledger gated store query".to_string(),
                tags_any: vec![],
                limit: 3,
                mode: "fts".to_string(),
                per_call_opt_in: true,
                checkout: None,
                timeout_ms: 1_000,
                coverage_threshold: 0.5,
                blend_alpha: CANDIDATE_STRONG_RETRIEVAL_ALPHA,
                attempt_id: Some("gated-store-trial-bad-ledger-gate".to_string()),
                commit: None,
            },
        )
        .await;

        assert_eq!(trial["status"], json!("transition_gate_blocked"));
        assert_eq!(trial["store_trial_called"], json!(false));
        assert_eq!(trial["calls_memory_search"], json!(false));
        assert_eq!(trial["runs_biocortex"], json!(false));
        assert_eq!(
            trial["runtime_transition_preflight"]["gate_capability_ledger_backed_review_request"],
            json!(true)
        );
        assert_eq!(
            trial["runtime_transition_preflight"]["gate_capability_ledger_safe_for_transition"],
            json!(false)
        );
        assert_eq!(
            trial["runtime_transition_preflight"]
                ["gate_capability_ledger_can_authorize_runtime_influence"],
            json!(true)
        );
        assert_eq!(
            trial["runtime_transition_preflight"]["gate_capability_ledger_preflight_ok"],
            json!(false)
        );
        let blockers = trial["runtime_transition_preflight"]["blockers"]
            .as_array()
            .expect("blockers");
        assert!(blockers.contains(&json!("transition_gate_capability_ledger_not_safe")));

        let serialized = serde_json::to_string(&trial).expect("gated trial json");
        assert!(!serialized.contains("secret bad capability ledger gated store query"));
        let _ = tokio::fs::remove_dir_all(dir).await;
    }

    #[tokio::test]
    async fn opt_in_gated_store_and_batch_report_post_runtime_evidence_transition_gate() {
        let _env = EnvRestore::capture(&[BIOCORTEX_RETRIEVAL_DISABLE_ENV]);
        std::env::remove_var(BIOCORTEX_RETRIEVAL_DISABLE_ENV);
        let decision_packet = biocortex_retrieval_opt_in_runtime_influence_decision_packet(
            BioCortexRetrievalOptInRuntimeInfluenceDecisionPacketOptions {
                runtime_influence_review_request:
                    opt_in_post_runtime_evidence_runtime_influence_review_request_fixture(),
                runtime_influence_decision: opt_in_runtime_influence_decision_fixture(),
                reviewer: Some("codex".to_string()),
                commit: Some("runtime-decision-commit".to_string()),
                forum_post_id: Some("104".to_string()),
                memory_key: Some("runtime-decision-memory".to_string()),
            },
        );
        let (store, dir) = empty_sqlite_store("gated-consumer-post-runtime-evidence").await;
        let readiness_batch = biocortex_retrieval_opt_in_gated_batch_diagnostics(
            &store,
            BioCortexRetrievalOptInGatedBatchDiagnosticsOptions {
                runtime_transition_gate: opt_in_runtime_transition_gate_fixture(),
                runtime_influence_decision_packet: decision_packet.clone(),
                queries: vec![
                    BioCortexRetrievalOptInBatchQueryCase {
                        query: "secret gated consumer readiness query one".to_string(),
                        class_label: Some("Evidence One".to_string()),
                    },
                    BioCortexRetrievalOptInBatchQueryCase {
                        query: "secret gated consumer readiness query two".to_string(),
                        class_label: Some("Evidence Two".to_string()),
                    },
                ],
                tags_any: vec![],
                limit: 3,
                mode: "fts".to_string(),
                per_call_opt_in: true,
                checkout: None,
                timeout_ms: 1_000,
                coverage_threshold: 0.5,
                blend_alpha: CANDIDATE_STRONG_RETRIEVAL_ALPHA,
                attempt_id: Some("gated-consumer-readiness-evidence".to_string()),
                commit: Some("runtime-transition-commit".to_string()),
            },
        )
        .await;
        let readiness = biocortex_retrieval_opt_in_runtime_readiness_packet(
            BioCortexRetrievalOptInRuntimeReadinessPacketOptions {
                runtime_influence_decision_packet: decision_packet.clone(),
                store_trial: opt_in_runtime_readiness_post_runtime_store_trial_fixture(),
                batch_diagnostics: readiness_batch,
                reviewer: Some("codex".to_string()),
                commit: Some("runtime-readiness-post-runtime-evidence-commit".to_string()),
                forum_post_id: Some("104".to_string()),
                memory_key: Some("runtime-readiness-post-runtime-evidence-memory".to_string()),
            },
        );
        let transition_gate = biocortex_retrieval_opt_in_runtime_transition_gate(
            BioCortexRetrievalOptInRuntimeTransitionGateOptions {
                runtime_readiness_packet: readiness.clone(),
                mode: "fts".to_string(),
                per_call_opt_in: true,
                operator_disabled: false,
                reviewer: Some("codex".to_string()),
                commit: Some("runtime-transition-post-runtime-evidence-commit".to_string()),
                forum_post_id: Some("104".to_string()),
                memory_key: Some("runtime-transition-post-runtime-evidence-memory".to_string()),
            },
        );

        let trial = biocortex_retrieval_opt_in_gated_store_trial(
            &store,
            BioCortexRetrievalOptInGatedStoreTrialOptions {
                runtime_transition_gate: transition_gate.clone(),
                runtime_influence_decision_packet: decision_packet.clone(),
                query: "secret gated consumer store query".to_string(),
                tags_any: vec![],
                limit: 3,
                mode: "fts".to_string(),
                per_call_opt_in: true,
                checkout: None,
                timeout_ms: 1_000,
                coverage_threshold: 0.5,
                blend_alpha: CANDIDATE_STRONG_RETRIEVAL_ALPHA,
                attempt_id: Some("gated-consumer-store".to_string()),
                commit: Some("runtime-transition-commit".to_string()),
            },
        )
        .await;

        assert_eq!(trial["status"], json!("transition_gate_consumed"));
        assert_eq!(
            trial["runtime_transition_preflight"]["gate_post_runtime_evidence_summary_backed"],
            json!(true)
        );
        assert_eq!(
            trial["runtime_transition_preflight"]["gate_post_runtime_evidence_summary_ready"],
            json!(true)
        );
        assert_eq!(
            trial["runtime_transition_preflight"]
                ["gate_legacy_decision_packet_without_post_runtime_evidence_summary_allowed"],
            json!(false)
        );
        assert_eq!(
            trial["runtime_transition_preflight"]["gate_post_runtime_evidence_summary_state"],
            json!("post_runtime_evidence_ready")
        );
        assert_eq!(
            trial["runtime_transition_preflight"]["gate_post_runtime_batch_evidence_source"],
            json!("runtime_transition_gated_batch_diagnostics")
        );
        assert_eq!(
            trial["runtime_transition_preflight"]
                ["gate_post_runtime_readiness_gated_batch_evidence_ready"],
            json!(true)
        );
        assert_eq!(
            trial["runtime_transition_preflight"]["gate_post_runtime_batch_transition_gated"],
            json!(true)
        );
        assert_eq!(
            trial["runtime_transition_preflight"]["gate_store_post_runtime_evidence_preflight_ok"],
            json!(true)
        );
        assert_eq!(
            trial["runtime_transition_preflight"]["gate_batch_post_runtime_evidence_preflight_ok"],
            json!(true)
        );
        assert_eq!(
            trial["store_trial_summary"]["decision_packet_post_runtime_evidence_summary_backed"],
            json!(true)
        );
        assert_eq!(
            trial["store_trial_summary"]["decision_packet_post_runtime_evidence_summary_ready"],
            json!(true)
        );

        let batch = biocortex_retrieval_opt_in_gated_batch_diagnostics(
            &store,
            BioCortexRetrievalOptInGatedBatchDiagnosticsOptions {
                runtime_transition_gate: transition_gate,
                runtime_influence_decision_packet: decision_packet,
                queries: vec![BioCortexRetrievalOptInBatchQueryCase {
                    query: "secret gated consumer batch query".to_string(),
                    class_label: Some("Evidence Batch".to_string()),
                }],
                tags_any: vec![],
                limit: 3,
                mode: "fts".to_string(),
                per_call_opt_in: true,
                checkout: None,
                timeout_ms: 1_000,
                coverage_threshold: 0.5,
                blend_alpha: CANDIDATE_STRONG_RETRIEVAL_ALPHA,
                attempt_id: Some("gated-consumer-batch".to_string()),
                commit: Some("runtime-transition-commit".to_string()),
            },
        )
        .await;
        let first = &batch["query_results"][0];
        assert_eq!(
            first["transition_preflight"]["gate_post_runtime_evidence_summary_backed"],
            json!(true)
        );
        assert_eq!(
            first["transition_preflight"]["gate_post_runtime_evidence_summary_ready"],
            json!(true)
        );
        assert_eq!(
            first["transition_preflight"]["gate_post_runtime_evidence_summary_state"],
            json!("post_runtime_evidence_ready")
        );
        assert_eq!(
            first["transition_preflight"]["gate_post_runtime_batch_evidence_source"],
            json!("runtime_transition_gated_batch_diagnostics")
        );
        assert_eq!(
            first["transition_preflight"]["gate_store_post_runtime_evidence_preflight_ok"],
            json!(true)
        );
        assert_eq!(
            first["transition_preflight"]["gate_batch_post_runtime_evidence_preflight_ok"],
            json!(true)
        );

        let serialized = serde_json::to_string(&json!({
            "trial": trial,
            "batch": batch,
        }))
        .expect("gated consumer json");
        assert!(!serialized.contains("secret gated consumer readiness query one"));
        assert!(!serialized.contains("secret gated consumer readiness query two"));
        assert!(!serialized.contains("secret gated consumer store query"));
        assert!(!serialized.contains("secret gated consumer batch query"));
        assert!(!serialized.contains("secret evidence summary raw query"));
        assert!(!serialized.contains("secret_evidence_summary_key"));
        assert!(!serialized.contains("secret evidence summary content"));
        let _ = tokio::fs::remove_dir_all(dir).await;
    }

    #[tokio::test]
    async fn opt_in_gated_store_and_batch_report_capability_ledger_transition_gate() {
        let _env = EnvRestore::capture(&[BIOCORTEX_RETRIEVAL_DISABLE_ENV]);
        std::env::remove_var(BIOCORTEX_RETRIEVAL_DISABLE_ENV);
        let decision_packet = biocortex_retrieval_opt_in_runtime_influence_decision_packet(
            BioCortexRetrievalOptInRuntimeInfluenceDecisionPacketOptions {
                runtime_influence_review_request:
                    opt_in_aggregate_and_ledger_backed_runtime_influence_review_request_fixture(),
                runtime_influence_decision: opt_in_runtime_influence_decision_fixture(),
                reviewer: Some("codex".to_string()),
                commit: Some("runtime-decision-commit".to_string()),
                forum_post_id: Some("104".to_string()),
                memory_key: Some("runtime-decision-memory".to_string()),
            },
        );
        let readiness = biocortex_retrieval_opt_in_runtime_readiness_packet(
            BioCortexRetrievalOptInRuntimeReadinessPacketOptions {
                runtime_influence_decision_packet: decision_packet.clone(),
                store_trial: opt_in_runtime_readiness_store_trial_fixture(),
                batch_diagnostics: opt_in_runtime_readiness_batch_fixture(),
                reviewer: Some("codex".to_string()),
                commit: Some("runtime-readiness-ledger-commit".to_string()),
                forum_post_id: Some("104".to_string()),
                memory_key: Some("runtime-readiness-ledger-memory".to_string()),
            },
        );
        let transition_gate = biocortex_retrieval_opt_in_runtime_transition_gate(
            BioCortexRetrievalOptInRuntimeTransitionGateOptions {
                runtime_readiness_packet: readiness.clone(),
                mode: "fts".to_string(),
                per_call_opt_in: true,
                operator_disabled: false,
                reviewer: Some("codex".to_string()),
                commit: Some("runtime-transition-ledger-commit".to_string()),
                forum_post_id: Some("104".to_string()),
                memory_key: Some("runtime-transition-ledger-memory".to_string()),
            },
        );
        let (store, dir) = empty_sqlite_store("gated-consumer-capability-ledger").await;

        let trial = biocortex_retrieval_opt_in_gated_store_trial(
            &store,
            BioCortexRetrievalOptInGatedStoreTrialOptions {
                runtime_transition_gate: transition_gate.clone(),
                runtime_influence_decision_packet: decision_packet.clone(),
                query: "secret gated capability ledger store query".to_string(),
                tags_any: vec![],
                limit: 3,
                mode: "fts".to_string(),
                per_call_opt_in: true,
                checkout: None,
                timeout_ms: 1_000,
                coverage_threshold: 0.5,
                blend_alpha: CANDIDATE_STRONG_RETRIEVAL_ALPHA,
                attempt_id: Some("gated-consumer-ledger-store".to_string()),
                commit: Some("runtime-transition-ledger-commit".to_string()),
            },
        )
        .await;

        assert_eq!(trial["status"], json!("transition_gate_consumed"));
        assert_eq!(
            trial["input_contract"]["accepts_capability_ledger_backed_transition_gate"],
            json!(true)
        );
        assert_eq!(
            trial["input_contract"]["requires_capability_ledger_safe_when_provided"],
            json!(true)
        );
        assert_eq!(
            trial["input_contract"]["capability_ledger_report_packet_included"],
            json!(false)
        );
        assert_eq!(
            trial["runtime_transition_preflight"]["gate_capability_ledger_backed_review_request"],
            json!(true)
        );
        assert_eq!(
            trial["runtime_transition_preflight"]["gate_capability_ledger_safe_for_transition"],
            json!(true)
        );
        assert_eq!(
            trial["runtime_transition_preflight"]
                ["gate_legacy_readiness_packet_without_capability_ledger_allowed"],
            json!(false)
        );
        assert_eq!(
            trial["runtime_transition_preflight"]["gate_capability_ledger_input_schema"],
            json!("biocortex.capability_ledger.v3")
        );
        assert_eq!(
            trial["runtime_transition_preflight"]["gate_capability_ledger_input_schema_version"],
            json!("3")
        );
        assert_eq!(
            trial["runtime_transition_preflight"]
                ["gate_capability_ledger_can_authorize_runtime_influence"],
            json!(false)
        );
        assert_eq!(
            trial["runtime_transition_preflight"]["gate_capability_ledger_report_packet_included"],
            json!(false)
        );
        assert_eq!(
            trial["runtime_transition_preflight"]["gate_capability_ledger_preflight_ok"],
            json!(true)
        );

        let batch = biocortex_retrieval_opt_in_gated_batch_diagnostics(
            &store,
            BioCortexRetrievalOptInGatedBatchDiagnosticsOptions {
                runtime_transition_gate: transition_gate.clone(),
                runtime_influence_decision_packet: decision_packet.clone(),
                queries: vec![BioCortexRetrievalOptInBatchQueryCase {
                    query: "secret gated capability ledger batch query".to_string(),
                    class_label: Some("Capability Ledger".to_string()),
                }],
                tags_any: vec![],
                limit: 3,
                mode: "fts".to_string(),
                per_call_opt_in: true,
                checkout: None,
                timeout_ms: 1_000,
                coverage_threshold: 0.5,
                blend_alpha: CANDIDATE_STRONG_RETRIEVAL_ALPHA,
                attempt_id: Some("gated-consumer-ledger-batch".to_string()),
                commit: Some("runtime-transition-ledger-commit".to_string()),
            },
        )
        .await;
        assert_eq!(
            batch["input_contract"]["accepts_capability_ledger_backed_transition_gate"],
            json!(true)
        );
        assert_eq!(batch["summary"]["gate_capability_ledger_backed_count"], json!(1));
        assert_eq!(batch["summary"]["gate_capability_ledger_safe_count"], json!(1));
        assert_eq!(
            batch["summary"]["gate_capability_ledger_authorizes_runtime_influence_count"],
            json!(0)
        );
        assert_eq!(
            batch["summary"]["gate_capability_ledger_report_packet_included_count"],
            json!(0)
        );
        assert_eq!(batch["safety"]["gate_capability_ledger_backed_all"], json!(true));
        assert_eq!(
            batch["safety"]["gate_capability_ledger_safe_for_transition_all"],
            json!(true)
        );
        assert_eq!(
            batch["safety"]["gate_capability_ledger_authorizes_runtime_influence_any"],
            json!(false)
        );
        assert_eq!(
            batch["safety"]["gate_capability_ledger_report_packet_included_any"],
            json!(false)
        );

        let first = &batch["query_results"][0];
        assert_eq!(
            first["transition_preflight"]["gate_capability_ledger_backed_review_request"],
            json!(true)
        );
        assert_eq!(
            first["transition_preflight"]["gate_capability_ledger_safe_for_transition"],
            json!(true)
        );
        assert_eq!(
            first["transition_preflight"]
                ["gate_legacy_readiness_packet_without_capability_ledger_allowed"],
            json!(false)
        );
        assert_eq!(
            first["transition_preflight"]["gate_capability_ledger_input_schema"],
            json!("biocortex.capability_ledger.v3")
        );
        assert_eq!(
            first["transition_preflight"]["gate_capability_ledger_input_schema_version"],
            json!("3")
        );
        assert_eq!(
            first["transition_preflight"]
                ["gate_capability_ledger_can_authorize_runtime_influence"],
            json!(false)
        );
        assert_eq!(
            first["transition_preflight"]["gate_capability_ledger_report_packet_included"],
            json!(false)
        );
        assert_eq!(
            first["transition_preflight"]["gate_capability_ledger_preflight_ok"],
            json!(true)
        );

        let controlled_readiness = biocortex_retrieval_controlled_trial_readiness_summary(
            "fts",
            true,
            Some(&readiness),
            Some(&transition_gate),
            Some(&trial),
            Some(&batch),
        );
        assert_eq!(
            controlled_readiness["status"],
            json!("ready_for_controlled_explicit_opt_in_fts_trial")
        );
        assert_eq!(
            controlled_readiness["capability_ledger"]["backed_evidence"],
            json!(true)
        );
        assert_eq!(
            controlled_readiness["capability_ledger"]["ready"],
            json!(true)
        );
        assert_eq!(
            controlled_readiness["capability_ledger"]["can_authorize_runtime_influence"],
            json!(false)
        );
        assert_eq!(
            controlled_readiness["capability_ledger"]["report_packet_included"],
            json!(false)
        );
        assert_eq!(
            controlled_readiness["runtime_transition_gate"]
                ["capability_ledger_safe_for_transition"],
            json!(true)
        );
        assert_eq!(
            controlled_readiness["gated_store_trial"]["capability_ledger_preflight_ok"],
            json!(true)
        );
        assert_eq!(
            controlled_readiness["gated_batch_diagnostics"]["capability_ledger_backed_count"],
            json!(1)
        );

        let handoff = biocortex_retrieval_downstream_aio_runtime_evidence_handoff(
            BioCortexRetrievalDownstreamAioRuntimeEvidenceHandoffOptions {
                checkpoint_selection: downstream_aio_checkpoint_selection_fixture(),
                post_semantic_diverse_review: downstream_aio_post_semantic_diverse_review_fixture(),
                controlled_trial_readiness: Some(controlled_readiness.clone()),
                reviewer: Some("codex".to_string()),
                commit: Some("runtime-transition-ledger-commit".to_string()),
                forum_post_id: Some("104".to_string()),
                memory_key: Some("downstream-aio-ledger-handoff-memory".to_string()),
            },
        );
        assert_eq!(handoff["status"], json!("ready"));
        assert_eq!(
            handoff["input_contract"]["accepts_capability_ledger_backed_controlled_readiness"],
            json!(true)
        );
        assert_eq!(
            handoff["input_contract"]["capability_ledger_report_packet_included"],
            json!(false)
        );
        assert_eq!(
            handoff["controlled_trial_readiness_summary"]
                ["capability_ledger_backed_evidence"],
            json!(true)
        );
        assert_eq!(
            handoff["controlled_trial_readiness_summary"]
                ["capability_ledger_safe_for_handoff"],
            json!(true)
        );
        assert_eq!(
            handoff["controlled_trial_readiness_summary"]
                ["capability_ledger_can_authorize_runtime_influence"],
            json!(false)
        );
        assert_eq!(
            handoff["ssb_handoff"]["capability_ledger_backed_audit_context"],
            json!(true)
        );
        assert_eq!(
            handoff["ssb_handoff"]["capability_ledger_safe_for_handoff"],
            json!(true)
        );
        assert_eq!(
            handoff["ssb_handoff"]["may_use_capability_ledger_as_runtime_authority"],
            json!(false)
        );
        assert_eq!(
            handoff["boundary_check"]["capability_ledger_authorizes_runtime_influence"],
            json!(false)
        );

        let mut bad_controlled_readiness = controlled_readiness.clone();
        bad_controlled_readiness["capability_ledger"]["ready"] = json!(false);
        bad_controlled_readiness["capability_ledger"]["can_authorize_runtime_influence"] =
            json!(true);
        let blocked_handoff = biocortex_retrieval_downstream_aio_runtime_evidence_handoff(
            BioCortexRetrievalDownstreamAioRuntimeEvidenceHandoffOptions {
                checkpoint_selection: downstream_aio_checkpoint_selection_fixture(),
                post_semantic_diverse_review: downstream_aio_post_semantic_diverse_review_fixture(),
                controlled_trial_readiness: Some(bad_controlled_readiness),
                reviewer: Some("codex".to_string()),
                commit: Some("runtime-transition-ledger-commit".to_string()),
                forum_post_id: Some("104".to_string()),
                memory_key: Some("downstream-aio-ledger-blocked-memory".to_string()),
            },
        );
        assert_eq!(blocked_handoff["status"], json!("blocked"));
        let blockers = blocked_handoff["boundary_check"]["blockers"]
            .as_array()
            .expect("handoff blockers");
        assert!(blockers.contains(&json!("controlled_trial_capability_ledger_not_ready")));
        assert_eq!(
            blocked_handoff["ssb_handoff"]["may_emit_ssb_adapter_fixture"],
            json!(false)
        );
        assert_eq!(
            blocked_handoff["boundary_check"]["capability_ledger_authorizes_runtime_influence"],
            json!(true)
        );

        let serialized = serde_json::to_string(&json!({
            "trial": trial,
            "batch": batch,
            "controlled_readiness": controlled_readiness,
            "handoff": handoff,
            "blocked_handoff": blocked_handoff,
        }))
        .expect("gated ledger consumer json");
        assert!(!serialized.contains("secret gated capability ledger store query"));
        assert!(!serialized.contains("secret gated capability ledger batch query"));
        assert!(!serialized.contains("secret ledger markdown"));
        assert!(!serialized.contains("secret ledger raw query"));
        assert!(!serialized.contains("secret_ledger_key"));
        assert!(!serialized.contains("secret ledger content"));
        assert!(!serialized.contains("report_markdown"));
        let _ = tokio::fs::remove_dir_all(dir).await;
    }

    #[tokio::test]
    async fn opt_in_gated_batch_diagnostics_blocks_all_queries_before_memory_search() {
        let mut gate = opt_in_runtime_transition_gate_fixture();
        gate["status"] = json!("blocked");
        gate["transition"]["transition_allowed"] = json!(false);
        gate["transition"]["may_call_controlled_store_trial"] = json!(false);
        gate["boundary_check"]["runtime_transition_allowed"] = json!(false);
        gate["boundary_check"]["blockers"] = json!(["forced_transition_block"]);
        let (store, dir) = empty_sqlite_store("gated-batch-diagnostics-blocked").await;

        let batch = biocortex_retrieval_opt_in_gated_batch_diagnostics(
            &store,
            BioCortexRetrievalOptInGatedBatchDiagnosticsOptions {
                runtime_transition_gate: gate,
                runtime_influence_decision_packet: Value::Null,
                queries: vec![
                    BioCortexRetrievalOptInBatchQueryCase {
                        query: "secret gated batch blocked query one".to_string(),
                        class_label: Some("Blocked One".to_string()),
                    },
                    BioCortexRetrievalOptInBatchQueryCase {
                        query: "secret gated batch blocked query two".to_string(),
                        class_label: Some("Blocked Two".to_string()),
                    },
                ],
                tags_any: vec![],
                limit: 3,
                mode: "fts".to_string(),
                per_call_opt_in: true,
                checkout: None,
                timeout_ms: 1_000,
                coverage_threshold: 0.5,
                blend_alpha: CANDIDATE_STRONG_RETRIEVAL_ALPHA,
                attempt_id: Some("gated-batch-blocked".to_string()),
                commit: None,
            },
        )
        .await;

        assert_eq!(
            batch["schema"],
            json!(BIOCORTEX_RETRIEVAL_OPT_IN_GATED_BATCH_DIAGNOSTICS_SCHEMA)
        );
        assert_eq!(batch["status"], json!("transition_gate_blocked"));
        assert_eq!(batch["summary"]["query_count"], json!(2));
        assert_eq!(batch["summary"]["transition_gate_blocked_count"], json!(2));
        assert_eq!(batch["summary"]["store_trial_called_count"], json!(0));
        assert_eq!(batch["summary"]["calls_memory_search_count"], json!(0));
        assert_eq!(batch["safety"]["transition_gate_blocked_all"], json!(true));
        assert_eq!(batch["safety"]["store_trial_called_any"], json!(false));
        assert_eq!(batch["calls_memory_search"], json!(false));
        assert_eq!(batch["runs_biocortex"], json!(false));
        assert_eq!(batch["changes_memory_search_order"], json!(false));
        assert_eq!(batch["boundary"]["gate_consumed"], json!(false));

        let first = &batch["query_results"][0];
        assert_eq!(first["movement_class"], json!("transition_gate_blocked"));
        assert_eq!(first["store_trial"]["called"], json!(false));
        assert_eq!(
            first["transition_preflight"]["transition_gate_allowed"],
            json!(false)
        );

        let serialized = serde_json::to_string(&batch).expect("gated batch json");
        assert!(!serialized.contains("secret gated batch blocked query one"));
        assert!(!serialized.contains("secret gated batch blocked query two"));
        let _ = tokio::fs::remove_dir_all(dir).await;
    }

    #[tokio::test]
    async fn opt_in_gated_batch_diagnostics_consumes_gate_per_query() {
        let _env = EnvRestore::capture(&[BIOCORTEX_RETRIEVAL_DISABLE_ENV]);
        std::env::remove_var(BIOCORTEX_RETRIEVAL_DISABLE_ENV);
        let decision_packet = biocortex_retrieval_opt_in_runtime_influence_decision_packet(
            BioCortexRetrievalOptInRuntimeInfluenceDecisionPacketOptions {
                runtime_influence_review_request:
                    opt_in_aggregate_backed_runtime_influence_review_request_fixture(),
                runtime_influence_decision: opt_in_runtime_influence_decision_fixture(),
                reviewer: Some("codex".to_string()),
                commit: Some("runtime-decision-commit".to_string()),
                forum_post_id: Some("104".to_string()),
                memory_key: Some("runtime-decision-memory".to_string()),
            },
        );
        let (store, dir) = empty_sqlite_store("gated-batch-diagnostics-allowed").await;

        let batch = biocortex_retrieval_opt_in_gated_batch_diagnostics(
            &store,
            BioCortexRetrievalOptInGatedBatchDiagnosticsOptions {
                runtime_transition_gate: opt_in_runtime_transition_gate_fixture(),
                runtime_influence_decision_packet: decision_packet,
                queries: vec![
                    BioCortexRetrievalOptInBatchQueryCase {
                        query: "secret gated batch allowed query one".to_string(),
                        class_label: Some("Allowed One".to_string()),
                    },
                    BioCortexRetrievalOptInBatchQueryCase {
                        query: "secret gated batch allowed query two".to_string(),
                        class_label: Some("Allowed Two".to_string()),
                    },
                ],
                tags_any: vec![],
                limit: 3,
                mode: "fts".to_string(),
                per_call_opt_in: true,
                checkout: None,
                timeout_ms: 1_000,
                coverage_threshold: 0.5,
                blend_alpha: CANDIDATE_STRONG_RETRIEVAL_ALPHA,
                attempt_id: Some("gated-batch-allowed".to_string()),
                commit: Some("runtime-transition-commit".to_string()),
            },
        )
        .await;

        assert_eq!(batch["status"], json!("completed"));
        assert_eq!(batch["summary"]["query_count"], json!(2));
        assert_eq!(batch["summary"]["transition_gate_allowed_count"], json!(2));
        assert_eq!(batch["summary"]["transition_gate_blocked_count"], json!(0));
        assert_eq!(batch["summary"]["store_trial_called_count"], json!(2));
        assert_eq!(batch["summary"]["calls_memory_search_count"], json!(2));
        assert_eq!(batch["safety"]["transition_gate_allowed_all"], json!(true));
        assert_eq!(batch["safety"]["store_trial_called_all"], json!(true));
        assert_eq!(batch["safety"]["calls_memory_search_all"], json!(true));
        assert_eq!(batch["calls_memory_search"], json!(true));
        assert_eq!(batch["runs_biocortex"], json!(false));
        assert_eq!(batch["changes_memory_search_order"], json!(false));
        assert_eq!(batch["boundary"]["gate_consumed"], json!(true));

        let first = &batch["query_results"][0];
        assert_eq!(
            first["movement_class"],
            json!("store_trial_preflight_blocked")
        );
        assert_eq!(first["store_trial"]["called"], json!(true));
        assert_eq!(
            first["transition_preflight"]["transition_gate_allowed"],
            json!(true)
        );
        assert_eq!(first["store_trial"]["baseline_key_count"], json!(0));

        let serialized = serde_json::to_string(&batch).expect("gated batch json");
        assert!(!serialized.contains("secret gated batch allowed query one"));
        assert!(!serialized.contains("secret gated batch allowed query two"));
        let _ = tokio::fs::remove_dir_all(dir).await;
    }

    struct EnvRestore {
        values: Vec<(&'static str, Option<std::ffi::OsString>)>,
    }

    impl EnvRestore {
        fn capture(keys: &[&'static str]) -> Self {
            Self {
                values: keys
                    .iter()
                    .copied()
                    .map(|key| (key, std::env::var_os(key)))
                    .collect(),
            }
        }
    }

    impl Drop for EnvRestore {
        fn drop(&mut self) {
            for (key, value) in self.values.iter().rev() {
                if let Some(value) = value {
                    std::env::set_var(key, value);
                } else {
                    std::env::remove_var(key);
                }
            }
        }
    }
}
