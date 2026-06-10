//! Read-only BioCortex shadow report adapter.
//!
//! This module intentionally does not link `biocortex-rs` into the AB runtime.
//! It runs a local checkout's sanctioned shadow examples and projects their
//! deterministic `key=value` output into AB status JSON.

use crate::shadow_cortex::{ShadowCortexEvent, ShadowCortexReplayFixture, SignalScope};
use ab_store::{cosine_similarity, embedding::default_backend};
use serde::{Deserialize, Serialize};
use serde_json::{json, Map, Number, Value};
use sha2::{Digest, Sha256};
use std::collections::BTreeMap;
use std::path::{Path, PathBuf};
use std::time::{Duration, Instant, SystemTime, UNIX_EPOCH};
use tokio::process::Command as TokioCommand;

pub const BIOCORTEX_SHADOW_SCHEMA: &str = "agent_bridge.biocortex_shadow_digest.v0";
pub const BIOCORTEX_REPLAY_COMPARISON_SCHEMA: &str = "agent_bridge.biocortex_replay_comparison.v0";
pub const BIOCORTEX_RETRIEVAL_SHADOW_SCHEMA: &str =
    "agent_bridge.biocortex_retrieval_shadow_report.v0";
pub const BIOCORTEX_SUBSTRATE_REPLAY_PLAN_SCHEMA: &str =
    "agent_bridge.biocortex_substrate_replay_plan.v0";
pub const BIOCORTEX_CHECKOUT_ENV: &str = "AB_BIOCORTEX_RS";
pub const BIOCORTEX_RETRIEVAL_SHADOW_ENABLE_ENV: &str = "AB_BIOCORTEX_RETRIEVAL_SHADOW";
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
            })
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
            })
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
                })
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
            })
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
            })
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
            )
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
    rows.sort_by(|a, b| b.score.partial_cmp(&a.score).unwrap_or(std::cmp::Ordering::Equal));
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
            }))
        }
        Err(_) => {
            return Err(json!({
                "status": "timeout",
                "timeout_ms": timeout_ms,
                "checkout_path": display_path(&checkout),
                "manifest_path": display_path(&manifest),
            }))
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
    for line in stdout.lines().map(str::trim).filter(|line| !line.is_empty()) {
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
}
