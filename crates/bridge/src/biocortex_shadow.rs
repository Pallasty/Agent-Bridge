//! Read-only BioCortex shadow report adapter.
//!
//! This module intentionally does not link `biocortex-rs` into the AB runtime.
//! It runs a local checkout's sanctioned shadow examples and projects their
//! deterministic `key=value` output into AB status JSON.

use crate::shadow_cortex::{ShadowCortexEvent, ShadowCortexReplayFixture, SignalScope};
use ab_store::{cosine_similarity, embedding::default_backend, BioCortexRetrievalOptInRequest};
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

#[derive(Debug, Clone)]
struct RetrievalAlphaConfig {
    policy: String,
    alpha: f32,
    explicit_alpha: bool,
}

#[derive(Debug, Deserialize)]
struct RetrievalSideSignalRow {
    query_id: String,
    candidate_key: String,
    score: f32,
    #[serde(default)]
    evidence: Option<String>,
}

#[derive(Debug, Clone)]
struct RetrievalBaselineScore {
    key: String,
    content: String,
    score: f32,
    rank: usize,
}

#[derive(Debug)]
struct RetrievalSideSignalRun {
    rows: Vec<RetrievalSideSignalRow>,
    payload: Value,
    raw: Value,
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
    let projection = biocortex_replay_fixture_projection(fixture, opts.include_events);
    let digest = biocortex_shadow_digest(BioCortexShadowOptions {
        checkout: opts.checkout,
        benchmark: opts.benchmark,
        timeout_ms: opts.timeout_ms,
        include_raw: opts.include_raw,
        fixture_projection: Some(projection.clone()),
    })
    .await;
    let comparison = replay_comparison_summary(&projection, &digest);

    json!({
        "schema": BIOCORTEX_REPLAY_COMPARISON_SCHEMA,
        "generated_at": now_secs(),
        "read_only": true,
        "status": comparison.get("status").cloned().unwrap_or_else(|| json!("unknown")),
        "ab_fixture_projection": projection,
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
    let decision_default_influence_not_authorized =
        value_bool_is(decision.get("default_retrieval_influence_authorized"), false);
    let decision_hybrid_not_authorized =
        value_bool_is(decision.get("hybrid_retrieval_influence_authorized"), false);
    let decision_semantic_not_authorized =
        value_bool_is(decision.get("semantic_retrieval_influence_authorized"), false);
    let decision_post_review_required = value_bool_is(
        decision.get("requires_post_implementation_review_before_use"),
        true,
    );
    let decision_not_authorizes_runtime_adapter =
        array_contains_str(decision.get("not_authorized"), "runtime_adapter_approved");
    let decision_not_authorizes_default_order =
        array_contains_str(decision.get("not_authorized"), "default_search_order_change_allowed");
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
        authorized_impl.get("must_return_baseline_on_absent_error_timeout_low_coverage_malformed_rows"),
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
    let request_implementation_allowed =
        value_bool_is(request.get("implementation_allowed"), true);
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
    let request_not_requested_default_order =
        array_contains_str(request.get("not_requested"), "default_search_order_change_allowed");
    let request_plan_status_known =
        request
            .pointer("/opt_in_plan/status")
            .and_then(Value::as_str)
            .map(|status| {
                status == "store_opt_in_search_wrapper_implemented"
                    || status == "authorization_decision_consumer_implemented"
                    || status == "post_implementation_review_gate_implemented"
            })
            .unwrap_or(false);

    let mut blockers = Vec::new();
    push_string_blocker(&mut blockers, decision_schema_ok, "decision_schema_invalid");
    push_string_blocker(&mut blockers, decision_authorized, "decision_not_authorized");
    push_string_blocker(&mut blockers, decision_scope_ok, "decision_scope_not_opt_in");
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
    push_string_blocker(&mut blockers, request_plan_status_known, "request_plan_status_unknown");

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
    let packet_implementation_authorized =
        value_bool_is(packet.pointer("/boundary_check/implementation_authorized"), true);
    let packet_approval_state_ok = value_str_eq(
        packet.get("approval_state"),
        "opt_in_implementation_authorized",
    );
    let packet_authorization_state_ok = value_str_eq(
        packet.get("authorization_state"),
        "authorized_for_opt_in_implementation",
    );
    let packet_review_required =
        value_bool_is(packet.pointer("/required_next_gate/post_implementation_review_before_use"), true);
    let packet_runtime_gate_required =
        value_bool_is(packet.pointer("/required_next_gate/runtime_adapter_approval_required"), true);
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
    let packet_runtime_not_approved =
        value_bool_is(packet.get("runtime_adapter_approved"), false);
    let packet_default_order_not_allowed =
        value_bool_is(packet.get("default_search_order_change_allowed"), false);
    let packet_approval_writes_false =
        value_bool_is(packet.get("approval_writes_allowed"), false);
    let packet_writes_false = value_bool_is(packet.get("writes_approval"), false);
    let packet_calls_memory_search_false =
        value_bool_is(packet.get("calls_memory_search"), false);
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
        })
        .unwrap_or(false);
    let plan_implementation_allowed =
        value_bool_is(plan.get("implementation_allowed"), true);
    let plan_store_wrapper_implemented =
        value_bool_is(plan.get("store_opt_in_search_wrapper_implemented"), true);
    let plan_decision_consumer_implemented =
        value_bool_is(plan.get("authorization_decision_consumer_implemented"), true);
    let plan_review_gate_implemented =
        value_bool_is(plan.get("post_implementation_review_gate_implemented"), true);
    let plan_runtime_not_approved =
        value_bool_is(plan.get("runtime_adapter_approved"), false);
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
    let plan_gate_read_only =
        value_bool_is(plan_gate_block.get("read_only"), true);
    let plan_gate_not_runtime_approval =
        value_bool_is(plan_gate_block.get("runtime_adapter_approved"), false);
    let plan_gate_not_default_order =
        value_bool_is(plan_gate_block.get("default_search_order_change_allowed"), false);
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
    push_string_blocker(&mut blockers, plan_gate_schema_ok, "plan_gate_schema_invalid");
    push_string_blocker(&mut blockers, plan_gate_cli_ok, "plan_gate_cli_mismatch");
    push_string_blocker(&mut blockers, plan_gate_mcp_ok, "plan_gate_mcp_mismatch");
    push_string_blocker(&mut blockers, plan_gate_read_only, "plan_gate_not_read_only");
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

async fn run_retrieval_side_signal(
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
        assert!(blockers.contains(&json!(
            "decision_not_authorized_missing_runtime_adapter"
        )));
        assert!(blockers.contains(&json!(
            "decision_not_authorized_missing_default_order"
        )));
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
        assert_eq!(packet["review_state"], json!("ready_for_human_runtime_influence_review"));
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
