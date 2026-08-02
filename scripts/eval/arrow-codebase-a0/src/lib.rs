//! Evaluation-only A0 harness for the Agent-Bridge codebase-index data plane.
//!
//! This crate deliberately lives in a nested workspace. It reads deterministic
//! synthetic source documents through the production `ab_store::codebase`
//! extractors, but it never opens SQLite and has no production runtime consumer.

use std::{
    collections::HashMap,
    path::Path,
    sync::{Arc, OnceLock},
    time::Instant,
};

use ab_store::{
    codebase::{detect_language, extract_calls, extract_imports, extract_symbols},
    CodebaseCall, CodebaseImport, CodebaseSymbol,
};
use arrow::{
    array::{Array, Float32Array, StringArray, UInt32Array},
    datatypes::{DataType, Field, Schema},
    error::ArrowError,
    record_batch::RecordBatch,
};
use clap::ValueEnum;
use serde::{Deserialize, Serialize};
use sha2::{Digest, Sha256};
use thiserror::Error;

/// Versioned workload generator used by every A0 evaluation mode.
pub const FROZEN_WORKLOAD_SCHEMA: &str = "agent_bridge.codebase_index.frozen_workload.v0";
/// Versioned semantic digest contract shared by native and Arrow paths.
pub const SEMANTIC_SCHEMA: &str = "agent_bridge.codebase_index.semantic_digest.v0";
/// Versioned contract shared by the three evaluation-only Arrow table schemas.
pub const ARROW_SCHEMA_CONTRACT: &str = "agent_bridge.codebase_index.arrow_tables.v0";
/// Versioned result emitted for one independently measured process.
pub const EVALUATION_RECEIPT_SCHEMA: &str =
    "agent_bridge.codebase_index.arrow_data_plane_a0.evaluation.v0";
/// Versioned comparison and recommendation contract over fresh-process trials.
pub const SUITE_ASSESSMENT_SCHEMA: &str =
    "agent_bridge.codebase_index.arrow_data_plane_a0.assessment.v0";
/// Versioned top-level receipt for an interleaved fresh-process suite.
pub const SUITE_RECEIPT_SCHEMA: &str = "agent_bridge.codebase_index.arrow_data_plane_a0.suite.v0";
/// Only this scale may produce canonical A0 promotion evidence.
pub const CANONICAL_DOCUMENTS: usize = 100_000;
/// Shared typed accumulator bound for canonical A0 evidence.
pub const CANONICAL_BATCH_ROWS: usize = 4_096;
/// Nine trials rotate every mode through every order position three times.
pub const CANONICAL_TRIALS_PER_MODE: usize = 9;
/// At least seven of nine paired trials must independently pass both gates.
pub const CANONICAL_REQUIRED_PAIRED_PASSES: usize = 7;
/// Arrow must improve one median resource by at least 5% without losing the other.
pub const ARROW_MIN_INCREMENTAL_IMPROVEMENT_BASIS_POINTS: i64 = 500;
/// Arrow's material native-relative advantage must hold in seven paired trials.
pub const CANONICAL_REQUIRED_ARROW_VALUE_PASSES: usize = 7;
/// SHA-256 of an empty byte string, used to freeze canonical rustflags.
pub const EMPTY_SHA256: &str = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855";

const ARROW_SCHEMA_META_KEY: &str = "ab.schema_contract";
const ARROW_PURPOSE_META_KEY: &str = "ab.purpose";
const WORKLOAD_GENERATOR_REVISION: &str = "frozen-source-templates-v0";

/// One independently evaluated materialization strategy.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize, ValueEnum)]
#[serde(rename_all = "snake_case")]
pub enum EvaluationMode {
    /// Mirrors the current indexer by retaining three complete vectors.
    FullVec,
    /// Retains at most `batch_rows` rows in a shared typed accumulator.
    NativeChunk,
    /// Converts a shared typed accumulator into up to three table-shaped
    /// RecordBatches, then computes the digest from Arrow arrays.
    ArrowRecordBatch,
}

/// Frozen-workload size and the shared bound for both streaming paths.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub struct EvaluationConfig {
    pub documents: usize,
    pub batch_rows: usize,
}

/// Per-table row counts from one evaluation.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct RowCounts {
    pub symbols: u64,
    pub imports: u64,
    pub calls: u64,
}

impl RowCounts {
    pub fn total(&self) -> u64 {
        self.symbols + self.imports + self.calls
    }
}

/// Exact, ordered, field-complete digest for the three logical tables.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct SemanticReceipt {
    pub schema: String,
    pub counts: RowCounts,
    pub symbols_sha256: String,
    pub imports_sha256: String,
    pub calls_sha256: String,
    pub combined_sha256: String,
}

/// Identity of the generated source workload.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct WorkloadIdentity {
    pub schema: String,
    pub generator_revision: String,
    pub documents: usize,
    pub template_count: usize,
    pub manifest_sha256: String,
}

/// Machine-readable receipt for one evaluation mode.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct EvaluationReceipt {
    pub schema: String,
    pub mode: EvaluationMode,
    pub workload: WorkloadIdentity,
    pub semantic: SemanticReceipt,
    pub batch_rows: usize,
    pub emitted_flushes: u64,
    pub max_accumulator_rows: usize,
    pub max_extractor_output_rows: usize,
    pub max_estimated_live_rows: usize,
    pub declared_live_row_bound: usize,
    pub elapsed_ns: u64,
    pub peak_rss_kib: Option<u64>,
    pub arrow_record_batches: Option<ArrowBatchCounts>,
    pub max_arrow_batch_rows: Option<usize>,
    pub arrow_schema_fingerprints: Option<ArrowSchemaFingerprints>,
    pub build: BuildIdentity,
    pub executable_sha256: Option<String>,
    pub trial_index: Option<usize>,
    pub order_position: Option<usize>,
    pub sqlite_accessed: bool,
    pub production_write: bool,
}

/// Source, profile, and lock identity embedded when the binary is built.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct BuildIdentity {
    pub revision: String,
    pub tree_clean: bool,
    pub profile: String,
    pub cargo_lock_sha256: String,
    pub tracked_source_sha256: String,
    pub target: String,
    pub opt_level: String,
    pub debug_assertions: bool,
    pub encoded_rustflags_sha256: String,
    pub profile_overrides_present: bool,
    pub rustc_version: String,
}

/// Runtime repository identity checked against the embedded build identity.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct RuntimeSourceIdentity {
    pub revision: String,
    pub tree_clean: bool,
    pub cargo_lock_sha256: String,
    pub tracked_source_sha256: String,
    pub build_matches_runtime: bool,
}

/// Return the build-time evidence compiled into this executable.
pub fn embedded_build_identity() -> BuildIdentity {
    BuildIdentity {
        revision: option_env!("AB_ARROW_A0_BUILD_REVISION")
            .unwrap_or("UNBOUND")
            .to_string(),
        tree_clean: option_env!("AB_ARROW_A0_BUILD_TREE_CLEAN") == Some("true"),
        profile: option_env!("AB_ARROW_A0_BUILD_PROFILE")
            .unwrap_or(if cfg!(debug_assertions) {
                "debug"
            } else {
                "release"
            })
            .to_string(),
        cargo_lock_sha256: option_env!("AB_ARROW_A0_CARGO_LOCK_SHA256")
            .unwrap_or("UNBOUND")
            .to_string(),
        tracked_source_sha256: option_env!("AB_ARROW_A0_TRACKED_SOURCE_SHA256")
            .unwrap_or("UNBOUND")
            .to_string(),
        target: option_env!("AB_ARROW_A0_BUILD_TARGET")
            .unwrap_or("UNBOUND")
            .to_string(),
        opt_level: option_env!("AB_ARROW_A0_BUILD_OPT_LEVEL")
            .unwrap_or("UNBOUND")
            .to_string(),
        debug_assertions: option_env!("AB_ARROW_A0_BUILD_DEBUG_ASSERTIONS") == Some("true"),
        encoded_rustflags_sha256: option_env!("AB_ARROW_A0_ENCODED_RUSTFLAGS_SHA256")
            .unwrap_or("UNBOUND")
            .to_string(),
        profile_overrides_present: option_env!("AB_ARROW_A0_PROFILE_OVERRIDES_PRESENT")
            == Some("true"),
        rustc_version: option_env!("AB_ARROW_A0_RUSTC_VERSION")
            .unwrap_or("UNBOUND")
            .to_string(),
    }
}

/// Number of table-shaped RecordBatches emitted by the Arrow path.
#[derive(Debug, Clone, Default, PartialEq, Eq, Serialize, Deserialize)]
pub struct ArrowBatchCounts {
    pub symbols: u64,
    pub imports: u64,
    pub calls: u64,
}

impl ArrowBatchCounts {
    pub fn total(&self) -> u64 {
        self.symbols + self.imports + self.calls
    }
}

/// Stable fingerprints for the three production-shaped Arrow schemas.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct ArrowSchemaFingerprints {
    pub symbols_sha256: String,
    pub imports_sha256: String,
    pub calls_sha256: String,
    pub combined_sha256: String,
}

/// The three table-shaped Arrow schemas used by A0.
#[derive(Debug, Clone)]
pub struct ArrowSchemas {
    pub symbols: Arc<Schema>,
    pub imports: Arc<Schema>,
    pub calls: Arc<Schema>,
}

/// Integer promotion thresholds. One hundred basis points equal one percent.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub struct PromotionThresholds {
    pub min_rss_reduction_basis_points: i64,
    pub max_elapsed_regression_basis_points: i64,
}

impl Default for PromotionThresholds {
    fn default() -> Self {
        Self {
            min_rss_reduction_basis_points: 3_000,
            max_elapsed_regression_basis_points: 1_000,
        }
    }
}

/// A0's deterministic choice after applying the frozen evidence gates.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum Recommendation {
    NoCandidate,
    NativeChunk,
    ArrowRecordBatch,
}

/// Terminal classification for an A0 suite.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum AssessmentStatus {
    InvalidEvidence,
    DiagnosticOnly,
    NoPromotionCandidate,
    TradeoffIndeterminate,
    NativeChunkPreferred,
    ArrowAdoptCandidate,
}

/// Whether an assessment is diagnostic or the one frozen promotion gate.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum EvidenceClass {
    Diagnostic,
    CanonicalPromotion,
}

/// Runtime evidence supplied by the suite orchestrator to the pure assessor.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub struct AssessmentContext {
    pub evidence_class: EvidenceClass,
    pub runtime_source_bound: bool,
    pub executable_sha256_bound: bool,
    pub runtime_identity_stable: bool,
}

/// Median metrics and promotion decision for one strategy.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct StrategyAssessment {
    pub mode: EvaluationMode,
    pub trials: usize,
    pub median_elapsed_ns: u64,
    pub median_peak_rss_kib: Option<u64>,
    pub rss_reduction_basis_points_vs_full_vec: Option<i64>,
    pub elapsed_regression_basis_points_vs_full_vec: i64,
    pub bound_respected: bool,
    pub paired_gate_passes: usize,
    pub required_paired_gate_passes: usize,
    pub stable: bool,
    pub resource_gates_passed: bool,
    pub eligible: bool,
}

/// Cross-mode assessment generated from equal-count fresh-process trials.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct SuiteAssessment {
    pub schema: String,
    pub evidence_class: EvidenceClass,
    pub thresholds: PromotionThresholds,
    pub semantic_equivalent: bool,
    pub workload_equivalent: bool,
    pub batch_config_equivalent: bool,
    pub measurement_complete: bool,
    pub receipt_contracts_valid: bool,
    pub build_consistent: bool,
    pub artifact_consistent: bool,
    pub source_revision_bound: bool,
    pub executable_sha256_bound: bool,
    pub runtime_identity_stable: bool,
    pub canonical_config: bool,
    pub canonical_trial_plan: bool,
    pub canonical_thresholds: bool,
    pub no_authority_side_effects: bool,
    pub evidence_complete: bool,
    pub full_vec: StrategyAssessment,
    pub native_chunk: StrategyAssessment,
    pub arrow_record_batch: StrategyAssessment,
    pub arrow_incremental_value: bool,
    pub arrow_vs_native_paired_value_passes: usize,
    pub required_arrow_vs_native_value_passes: usize,
    pub tradeoff_indeterminate: bool,
    pub recommendation: Recommendation,
    pub status: AssessmentStatus,
}

/// Non-identifying host facts needed to interpret one benchmark suite.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct EnvironmentReceipt {
    pub target_os: String,
    pub target_arch: String,
    pub kernel_release: Option<String>,
    pub cpu_model: Option<String>,
    pub logical_cpus: Option<usize>,
    pub total_memory_kib: Option<u64>,
}

/// Raw child receipts plus their deterministic gate assessment.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct SuiteReceipt {
    pub schema: String,
    pub config: EvaluationConfig,
    pub trials_per_mode: usize,
    pub evidence_class: EvidenceClass,
    pub build: BuildIdentity,
    pub runtime_source: RuntimeSourceIdentity,
    pub executable_sha256: String,
    pub post_run_identity_stable: bool,
    pub fresh_process_per_trial: bool,
    pub interleaved_mode_order: bool,
    pub environment: EnvironmentReceipt,
    pub receipts: Vec<EvaluationReceipt>,
    pub assessment: SuiteAssessment,
}

#[derive(Debug, Error)]
pub enum EvaluationError {
    #[error("documents must be greater than zero")]
    EmptyWorkload,
    #[error("batch_rows must be greater than zero")]
    EmptyBatch,
    #[error("frozen workload path has no supported language: {0}")]
    UnsupportedFixturePath(String),
    #[error("frozen workload language mismatch for {path}: expected {expected}, got {actual}")]
    FixtureLanguageMismatch {
        path: String,
        expected: &'static str,
        actual: &'static str,
    },
    #[error("Arrow schema contract violation: {0}")]
    ArrowContract(String),
    #[error("evaluation receipt contract violation: {0}")]
    ReceiptContract(String),
    #[error("frozen workload row count overflows the receipt representation")]
    WorkloadSizeOverflow,
    #[error("assessment is missing trials for mode {0:?}")]
    MissingMode(EvaluationMode),
    #[error(
        "assessment trial counts differ: full_vec={full_vec}, native_chunk={native_chunk}, arrow_record_batch={arrow_record_batch}"
    )]
    UnequalTrialCounts {
        full_vec: usize,
        native_chunk: usize,
        arrow_record_batch: usize,
    },
    #[error("full-Vec median elapsed time must be greater than zero")]
    ZeroElapsedBaseline,
    #[error("full-Vec median peak RSS must be greater than zero")]
    ZeroRssBaseline,
    #[error(transparent)]
    Arrow(#[from] ArrowError),
}

/// Run one A0 strategy against the deterministic source generator.
pub fn evaluate_frozen_workload(
    mode: EvaluationMode,
    config: EvaluationConfig,
) -> Result<EvaluationReceipt, EvaluationError> {
    validate_config(config)?;
    let started = Instant::now();
    let workload = frozen_workload_identity(config.documents);

    let materialization = match mode {
        EvaluationMode::FullVec => evaluate_full_vec(config.documents)?,
        EvaluationMode::NativeChunk => evaluate_native_chunk(config.documents, config.batch_rows)?,
        EvaluationMode::ArrowRecordBatch => {
            evaluate_arrow_batches(config.documents, config.batch_rows)?
        }
    };

    Ok(EvaluationReceipt {
        schema: EVALUATION_RECEIPT_SCHEMA.to_string(),
        mode,
        workload,
        semantic: materialization.semantic,
        batch_rows: config.batch_rows,
        emitted_flushes: materialization.emitted_flushes,
        max_accumulator_rows: materialization.max_accumulator_rows,
        max_extractor_output_rows: materialization.max_extractor_output_rows,
        max_estimated_live_rows: materialization.max_estimated_live_rows,
        declared_live_row_bound: materialization.declared_live_row_bound,
        elapsed_ns: saturating_u64(started.elapsed().as_nanos()),
        peak_rss_kib: peak_rss_kib(),
        arrow_record_batches: materialization.arrow_record_batches,
        max_arrow_batch_rows: materialization.max_arrow_batch_rows,
        arrow_schema_fingerprints: (mode == EvaluationMode::ArrowRecordBatch)
            .then(arrow_schema_fingerprints),
        build: embedded_build_identity(),
        executable_sha256: None,
        trial_index: None,
        order_position: None,
        sqlite_accessed: false,
        production_write: false,
    })
}

/// Assess equal-count fresh-process receipts using the frozen A0 gates.
pub fn assess_trials(
    receipts: &[EvaluationReceipt],
    thresholds: PromotionThresholds,
    context: AssessmentContext,
) -> Result<SuiteAssessment, EvaluationError> {
    let full_receipts: Vec<_> = receipts
        .iter()
        .filter(|receipt| receipt.mode == EvaluationMode::FullVec)
        .collect();
    let native_receipts: Vec<_> = receipts
        .iter()
        .filter(|receipt| receipt.mode == EvaluationMode::NativeChunk)
        .collect();
    let arrow_receipts: Vec<_> = receipts
        .iter()
        .filter(|receipt| receipt.mode == EvaluationMode::ArrowRecordBatch)
        .collect();

    require_mode(&full_receipts, EvaluationMode::FullVec)?;
    require_mode(&native_receipts, EvaluationMode::NativeChunk)?;
    require_mode(&arrow_receipts, EvaluationMode::ArrowRecordBatch)?;
    if full_receipts.len() != native_receipts.len() || full_receipts.len() != arrow_receipts.len() {
        return Err(EvaluationError::UnequalTrialCounts {
            full_vec: full_receipts.len(),
            native_chunk: native_receipts.len(),
            arrow_record_batch: arrow_receipts.len(),
        });
    }

    let reference = full_receipts[0];
    let semantic_equivalent = receipts
        .iter()
        .all(|receipt| receipt.semantic == reference.semantic);
    let workload_equivalent = receipts
        .iter()
        .all(|receipt| receipt.workload == reference.workload);
    let batch_config_equivalent = receipts
        .iter()
        .all(|receipt| receipt.batch_rows == reference.batch_rows);
    let build_consistent = receipts
        .iter()
        .all(|receipt| receipt.build == reference.build);
    let artifact_consistent = reference
        .executable_sha256
        .as_deref()
        .is_some_and(|value| is_lower_hex(value, 64))
        && receipts
            .iter()
            .all(|receipt| receipt.executable_sha256 == reference.executable_sha256);
    let source_revision_bound = context.runtime_source_bound
        && build_consistent
        && canonical_build_identity_valid(&reference.build);
    let canonical_workload = frozen_workload_identity(CANONICAL_DOCUMENTS);
    let canonical_config = receipts.iter().all(|receipt| {
        receipt.workload == canonical_workload && receipt.batch_rows == CANONICAL_BATCH_ROWS
    });
    let canonical_trial_plan = has_canonical_trial_plan(receipts);
    let canonical_thresholds = thresholds == PromotionThresholds::default();
    let no_authority_side_effects = receipts.iter().all(|receipt| {
        !receipt.sqlite_accessed
            && !receipt.production_write
            && receipt.schema == EVALUATION_RECEIPT_SCHEMA
    });

    let full_elapsed = median_required(&full_receipts, |receipt| receipt.elapsed_ns);
    if full_elapsed == 0 {
        return Err(EvaluationError::ZeroElapsedBaseline);
    }
    let native_elapsed = median_required(&native_receipts, |receipt| receipt.elapsed_ns);
    let arrow_elapsed = median_required(&arrow_receipts, |receipt| receipt.elapsed_ns);

    let full_rss = median_optional(&full_receipts, |receipt| receipt.peak_rss_kib);
    if full_rss == Some(0) {
        return Err(EvaluationError::ZeroRssBaseline);
    }
    let native_rss = median_optional(&native_receipts, |receipt| receipt.peak_rss_kib);
    let arrow_rss = median_optional(&arrow_receipts, |receipt| receipt.peak_rss_kib);

    let full_bound = full_receipts
        .iter()
        .all(|receipt| validate_evaluation_receipt(receipt).is_ok());
    let native_bound = native_receipts
        .iter()
        .all(|receipt| validate_evaluation_receipt(receipt).is_ok());
    let arrow_bound = arrow_receipts
        .iter()
        .all(|receipt| validate_evaluation_receipt(receipt).is_ok());
    let receipt_contracts_valid = full_bound && native_bound && arrow_bound;
    let rss_complete = receipts
        .iter()
        .all(|receipt| receipt.peak_rss_kib.is_some_and(|value| value > 0));
    let measurement_complete = semantic_equivalent
        && workload_equivalent
        && batch_config_equivalent
        && build_consistent
        && artifact_consistent
        && no_authority_side_effects
        && receipt_contracts_valid
        && rss_complete;
    let evidence_complete = context.evidence_class == EvidenceClass::CanonicalPromotion
        && measurement_complete
        && source_revision_bound
        && context.executable_sha256_bound
        && context.runtime_identity_stable
        && canonical_config
        && canonical_trial_plan
        && canonical_thresholds;

    let native_rss_reduction = rss_reduction_basis_points(full_rss, native_rss)?;
    let arrow_rss_reduction = rss_reduction_basis_points(full_rss, arrow_rss)?;
    let native_elapsed_regression = relative_change_basis_points(native_elapsed, full_elapsed);
    let arrow_elapsed_regression = relative_change_basis_points(arrow_elapsed, full_elapsed);
    let required_paired_gate_passes = match context.evidence_class {
        EvidenceClass::Diagnostic => usize::from(!full_receipts.is_empty()),
        EvidenceClass::CanonicalPromotion => CANONICAL_REQUIRED_PAIRED_PASSES,
    };
    let native_paired_gate_passes =
        paired_gate_passes(&full_receipts, &native_receipts, thresholds);
    let arrow_paired_gate_passes = paired_gate_passes(&full_receipts, &arrow_receipts, thresholds);
    let native_stable = native_paired_gate_passes >= required_paired_gate_passes;
    let arrow_stable = arrow_paired_gate_passes >= required_paired_gate_passes;
    let native_resource_gates_passed = measurement_complete
        && native_rss_reduction
            .is_some_and(|value| value >= thresholds.min_rss_reduction_basis_points)
        && native_elapsed_regression <= thresholds.max_elapsed_regression_basis_points
        && native_stable;
    let arrow_resource_gates_passed = measurement_complete
        && arrow_rss_reduction
            .is_some_and(|value| value >= thresholds.min_rss_reduction_basis_points)
        && arrow_elapsed_regression <= thresholds.max_elapsed_regression_basis_points
        && arrow_stable;
    let native_eligible = evidence_complete && native_resource_gates_passed;
    let arrow_eligible = evidence_complete && arrow_resource_gates_passed;

    let required_arrow_vs_native_value_passes = match context.evidence_class {
        EvidenceClass::Diagnostic => usize::from(!native_receipts.is_empty()),
        EvidenceClass::CanonicalPromotion => CANONICAL_REQUIRED_ARROW_VALUE_PASSES,
    };
    let arrow_vs_native_paired_value_passes =
        paired_incremental_value_passes(&native_receipts, &arrow_receipts);
    let arrow_median_incremental_value = match (native_rss, arrow_rss) {
        (Some(native_rss), Some(arrow_rss)) => {
            material_incremental_value(native_rss, native_elapsed, arrow_rss, arrow_elapsed)
        }
        _ => false,
    };
    let arrow_value_stable =
        arrow_vs_native_paired_value_passes >= required_arrow_vs_native_value_passes;
    let arrow_incremental_value = arrow_eligible
        && (!native_eligible || (arrow_median_incremental_value && arrow_value_stable));
    let resource_tradeoff = match (native_rss, arrow_rss) {
        (Some(native_rss), Some(arrow_rss)) => {
            (arrow_rss < native_rss && arrow_elapsed > native_elapsed)
                || (arrow_rss > native_rss && arrow_elapsed < native_elapsed)
        }
        _ => false,
    };
    let tradeoff_indeterminate =
        evidence_complete && native_eligible && arrow_eligible && resource_tradeoff;

    let recommendation = if !evidence_complete || tradeoff_indeterminate {
        Recommendation::NoCandidate
    } else if arrow_eligible && (!native_eligible || arrow_incremental_value) {
        Recommendation::ArrowRecordBatch
    } else if native_eligible {
        Recommendation::NativeChunk
    } else {
        Recommendation::NoCandidate
    };
    let status = if !measurement_complete {
        AssessmentStatus::InvalidEvidence
    } else if context.evidence_class == EvidenceClass::Diagnostic {
        AssessmentStatus::DiagnosticOnly
    } else if !evidence_complete {
        AssessmentStatus::InvalidEvidence
    } else if tradeoff_indeterminate {
        AssessmentStatus::TradeoffIndeterminate
    } else {
        match recommendation {
            Recommendation::ArrowRecordBatch => AssessmentStatus::ArrowAdoptCandidate,
            Recommendation::NativeChunk => AssessmentStatus::NativeChunkPreferred,
            Recommendation::NoCandidate => AssessmentStatus::NoPromotionCandidate,
        }
    };

    Ok(SuiteAssessment {
        schema: SUITE_ASSESSMENT_SCHEMA.to_string(),
        evidence_class: context.evidence_class,
        thresholds,
        semantic_equivalent,
        workload_equivalent,
        batch_config_equivalent,
        measurement_complete,
        receipt_contracts_valid,
        build_consistent,
        artifact_consistent,
        source_revision_bound,
        executable_sha256_bound: context.executable_sha256_bound,
        runtime_identity_stable: context.runtime_identity_stable,
        canonical_config,
        canonical_trial_plan,
        canonical_thresholds,
        no_authority_side_effects,
        evidence_complete,
        full_vec: StrategyAssessment {
            mode: EvaluationMode::FullVec,
            trials: full_receipts.len(),
            median_elapsed_ns: full_elapsed,
            median_peak_rss_kib: full_rss,
            rss_reduction_basis_points_vs_full_vec: Some(0),
            elapsed_regression_basis_points_vs_full_vec: 0,
            bound_respected: full_bound,
            paired_gate_passes: 0,
            required_paired_gate_passes: 0,
            stable: true,
            resource_gates_passed: false,
            eligible: false,
        },
        native_chunk: StrategyAssessment {
            mode: EvaluationMode::NativeChunk,
            trials: native_receipts.len(),
            median_elapsed_ns: native_elapsed,
            median_peak_rss_kib: native_rss,
            rss_reduction_basis_points_vs_full_vec: native_rss_reduction,
            elapsed_regression_basis_points_vs_full_vec: native_elapsed_regression,
            bound_respected: native_bound,
            paired_gate_passes: native_paired_gate_passes,
            required_paired_gate_passes,
            stable: native_stable,
            resource_gates_passed: native_resource_gates_passed,
            eligible: native_eligible,
        },
        arrow_record_batch: StrategyAssessment {
            mode: EvaluationMode::ArrowRecordBatch,
            trials: arrow_receipts.len(),
            median_elapsed_ns: arrow_elapsed,
            median_peak_rss_kib: arrow_rss,
            rss_reduction_basis_points_vs_full_vec: arrow_rss_reduction,
            elapsed_regression_basis_points_vs_full_vec: arrow_elapsed_regression,
            bound_respected: arrow_bound,
            paired_gate_passes: arrow_paired_gate_passes,
            required_paired_gate_passes,
            stable: arrow_stable,
            resource_gates_passed: arrow_resource_gates_passed,
            eligible: arrow_eligible,
        },
        arrow_incremental_value,
        arrow_vs_native_paired_value_passes,
        required_arrow_vs_native_value_passes,
        tradeoff_indeterminate,
        recommendation,
        status,
    })
}

fn is_lower_hex(value: &str, expected_len: usize) -> bool {
    value.len() == expected_len
        && value
            .bytes()
            .all(|byte| byte.is_ascii_digit() || (b'a'..=b'f').contains(&byte))
}

fn canonical_build_identity_valid(build: &BuildIdentity) -> bool {
    is_lower_hex(&build.revision, 40)
        && build.tree_clean
        && build.profile == "release"
        && is_lower_hex(&build.cargo_lock_sha256, 64)
        && is_lower_hex(&build.tracked_source_sha256, 64)
        && !build.target.is_empty()
        && build.target != "UNBOUND"
        && build.opt_level == "3"
        && !build.debug_assertions
        && build.encoded_rustflags_sha256 == EMPTY_SHA256
        && !build.profile_overrides_present
        && build.rustc_version.starts_with("rustc ")
}

fn has_canonical_trial_plan(receipts: &[EvaluationReceipt]) -> bool {
    if receipts.len() != CANONICAL_TRIALS_PER_MODE.saturating_mul(3) {
        return false;
    }

    let mut position_counts = [[0usize; 3]; 3];
    for trial_index in 0..CANONICAL_TRIALS_PER_MODE {
        let rows: Vec<_> = receipts
            .iter()
            .filter(|receipt| receipt.trial_index == Some(trial_index))
            .collect();
        if rows.len() != 3 {
            return false;
        }
        let mut seen_modes = [false; 3];
        let mut seen_positions = [false; 3];
        for receipt in rows {
            let mode_index = mode_index(receipt.mode);
            let Some(position) = receipt.order_position else {
                return false;
            };
            if position >= 3 || seen_modes[mode_index] || seen_positions[position] {
                return false;
            }
            seen_modes[mode_index] = true;
            seen_positions[position] = true;
            position_counts[mode_index][position] += 1;
        }
    }
    position_counts
        .iter()
        .all(|positions| positions.iter().all(|count| *count == 3))
}

fn mode_index(mode: EvaluationMode) -> usize {
    match mode {
        EvaluationMode::FullVec => 0,
        EvaluationMode::NativeChunk => 1,
        EvaluationMode::ArrowRecordBatch => 2,
    }
}

fn paired_gate_passes(
    full_receipts: &[&EvaluationReceipt],
    candidate_receipts: &[&EvaluationReceipt],
    thresholds: PromotionThresholds,
) -> usize {
    let mut passes = 0;
    for candidate in candidate_receipts {
        let Some(trial_index) = candidate.trial_index else {
            continue;
        };
        let Some(baseline) = full_receipts
            .iter()
            .find(|receipt| receipt.trial_index == Some(trial_index))
        else {
            continue;
        };
        let (Some(baseline_rss), Some(candidate_rss)) =
            (baseline.peak_rss_kib, candidate.peak_rss_kib)
        else {
            continue;
        };
        if baseline_rss == 0 || baseline.elapsed_ns == 0 {
            continue;
        }
        let rss_reduction = -relative_change_basis_points(candidate_rss, baseline_rss);
        let elapsed_regression =
            relative_change_basis_points(candidate.elapsed_ns, baseline.elapsed_ns);
        if rss_reduction >= thresholds.min_rss_reduction_basis_points
            && elapsed_regression <= thresholds.max_elapsed_regression_basis_points
        {
            passes += 1;
        }
    }
    passes
}

fn paired_incremental_value_passes(
    native_receipts: &[&EvaluationReceipt],
    arrow_receipts: &[&EvaluationReceipt],
) -> usize {
    let mut passes = 0;
    for arrow in arrow_receipts {
        let Some(trial_index) = arrow.trial_index else {
            continue;
        };
        let Some(native) = native_receipts
            .iter()
            .find(|receipt| receipt.trial_index == Some(trial_index))
        else {
            continue;
        };
        let (Some(native_rss), Some(arrow_rss)) = (native.peak_rss_kib, arrow.peak_rss_kib) else {
            continue;
        };
        if native_rss == 0 || native.elapsed_ns == 0 {
            continue;
        }
        if material_incremental_value(native_rss, native.elapsed_ns, arrow_rss, arrow.elapsed_ns) {
            passes += 1;
        }
    }
    passes
}

fn material_incremental_value(
    baseline_rss: u64,
    baseline_elapsed: u64,
    candidate_rss: u64,
    candidate_elapsed: u64,
) -> bool {
    if baseline_rss == 0 || baseline_elapsed == 0 {
        return false;
    }
    let rss_improvement = -relative_change_basis_points(candidate_rss, baseline_rss);
    let elapsed_improvement = -relative_change_basis_points(candidate_elapsed, baseline_elapsed);
    (rss_improvement >= ARROW_MIN_INCREMENTAL_IMPROVEMENT_BASIS_POINTS && elapsed_improvement >= 0)
        || (elapsed_improvement >= ARROW_MIN_INCREMENTAL_IMPROVEMENT_BASIS_POINTS
            && rss_improvement >= 0)
}

fn require_mode(
    receipts: &[&EvaluationReceipt],
    mode: EvaluationMode,
) -> Result<(), EvaluationError> {
    if receipts.is_empty() {
        return Err(EvaluationError::MissingMode(mode));
    }
    Ok(())
}

fn median_required<F>(receipts: &[&EvaluationReceipt], select: F) -> u64
where
    F: Fn(&EvaluationReceipt) -> u64,
{
    let mut values: Vec<_> = receipts.iter().map(|receipt| select(receipt)).collect();
    median(&mut values)
}

fn median_optional<F>(receipts: &[&EvaluationReceipt], select: F) -> Option<u64>
where
    F: Fn(&EvaluationReceipt) -> Option<u64>,
{
    let mut values: Vec<_> = receipts
        .iter()
        .map(|receipt| select(receipt))
        .collect::<Option<Vec<_>>>()?;
    Some(median(&mut values))
}

fn median(values: &mut [u64]) -> u64 {
    values.sort_unstable();
    let midpoint = values.len() / 2;
    if values.len() % 2 == 1 {
        values[midpoint]
    } else {
        values[midpoint - 1] / 2
            + values[midpoint] / 2
            + (values[midpoint - 1] % 2 + values[midpoint] % 2) / 2
    }
}

fn rss_reduction_basis_points(
    baseline: Option<u64>,
    candidate: Option<u64>,
) -> Result<Option<i64>, EvaluationError> {
    match (baseline, candidate) {
        (Some(0), _) => Err(EvaluationError::ZeroRssBaseline),
        (Some(baseline), Some(candidate)) => {
            Ok(Some(-relative_change_basis_points(candidate, baseline)))
        }
        _ => Ok(None),
    }
}

fn relative_change_basis_points(candidate: u64, baseline: u64) -> i64 {
    let numerator = i128::from(candidate) - i128::from(baseline);
    let value = numerator.saturating_mul(10_000) / i128::from(baseline);
    i64::try_from(value).unwrap_or_else(|_| {
        if value.is_negative() {
            i64::MIN
        } else {
            i64::MAX
        }
    })
}

fn validate_config(config: EvaluationConfig) -> Result<(), EvaluationError> {
    if config.documents == 0 {
        return Err(EvaluationError::EmptyWorkload);
    }
    if config.batch_rows == 0 {
        return Err(EvaluationError::EmptyBatch);
    }
    Ok(())
}

#[derive(Debug)]
struct MaterializationResult {
    semantic: SemanticReceipt,
    emitted_flushes: u64,
    max_accumulator_rows: usize,
    max_extractor_output_rows: usize,
    max_estimated_live_rows: usize,
    declared_live_row_bound: usize,
    arrow_record_batches: Option<ArrowBatchCounts>,
    max_arrow_batch_rows: Option<usize>,
}

#[derive(Default)]
struct FullRows {
    symbols: Vec<CodebaseSymbol>,
    imports: Vec<CodebaseImport>,
    calls: Vec<CodebaseCall>,
}

impl FullRows {
    fn len(&self) -> usize {
        self.symbols.len() + self.imports.len() + self.calls.len()
    }
}

struct ExtractedRows {
    symbols: Vec<CodebaseSymbol>,
    imports: Vec<CodebaseImport>,
    calls: Vec<CodebaseCall>,
}

impl ExtractedRows {
    fn len(&self) -> usize {
        self.symbols.len() + self.imports.len() + self.calls.len()
    }
}

fn evaluate_full_vec(documents: usize) -> Result<MaterializationResult, EvaluationError> {
    let mut all = FullRows::default();
    let mut max_extractor_output_rows = 0;

    for document_index in 0..documents {
        let rows = extract_frozen_document(document_index)?;
        max_extractor_output_rows = max_extractor_output_rows.max(rows.len());
        all.symbols.extend(rows.symbols);
        all.imports.extend(rows.imports);
        all.calls.extend(rows.calls);
    }

    let total_rows = all.len();
    let mut semantic = SemanticAccumulator::new();
    for row in &all.symbols {
        semantic.push_symbol(row);
    }
    for row in &all.imports {
        semantic.push_import(row);
    }
    for row in &all.calls {
        semantic.push_call(row);
    }

    Ok(MaterializationResult {
        semantic: semantic.finish(),
        emitted_flushes: u64::from(total_rows > 0),
        max_accumulator_rows: total_rows,
        max_extractor_output_rows,
        max_estimated_live_rows: total_rows,
        declared_live_row_bound: total_rows,
        arrow_record_batches: None,
        max_arrow_batch_rows: None,
    })
}

fn evaluate_native_chunk(
    documents: usize,
    batch_rows: usize,
) -> Result<MaterializationResult, EvaluationError> {
    evaluate_bounded(documents, batch_rows, BoundedMode::Native)
}

fn evaluate_arrow_batches(
    documents: usize,
    batch_rows: usize,
) -> Result<MaterializationResult, EvaluationError> {
    evaluate_bounded(documents, batch_rows, BoundedMode::Arrow)
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
enum BoundedMode {
    Native,
    Arrow,
}

#[derive(Default)]
struct TypedBatch {
    symbols: Vec<CodebaseSymbol>,
    imports: Vec<CodebaseImport>,
    calls: Vec<CodebaseCall>,
}

impl TypedBatch {
    fn len(&self) -> usize {
        self.symbols.len() + self.imports.len() + self.calls.len()
    }

    fn is_empty(&self) -> bool {
        self.len() == 0
    }

    fn clear(&mut self) {
        self.symbols.clear();
        self.imports.clear();
        self.calls.clear();
    }
}

#[derive(Default)]
struct BoundedMetrics {
    emitted_flushes: u64,
    max_accumulator_rows: usize,
    max_extractor_output_rows: usize,
    max_estimated_live_rows: usize,
    arrow_record_batches: ArrowBatchCounts,
    max_arrow_batch_rows: usize,
}

fn evaluate_bounded(
    documents: usize,
    batch_rows: usize,
    mode: BoundedMode,
) -> Result<MaterializationResult, EvaluationError> {
    let mut batch = TypedBatch::default();
    let mut semantic = SemanticAccumulator::new();
    let mut metrics = BoundedMetrics::default();

    for document_index in 0..documents {
        let extracted = extract_frozen_document(document_index)?;
        let mut remaining_extractor_rows = extracted.len();
        metrics.max_extractor_output_rows = metrics
            .max_extractor_output_rows
            .max(remaining_extractor_rows);
        metrics.max_estimated_live_rows = metrics
            .max_estimated_live_rows
            .max(batch.len().saturating_add(remaining_extractor_rows));

        let ExtractedRows {
            symbols,
            imports,
            calls,
        } = extracted;
        for row in symbols {
            batch.symbols.push(row);
            remaining_extractor_rows = remaining_extractor_rows.saturating_sub(1);
            flush_if_full(
                &mut batch,
                batch_rows,
                remaining_extractor_rows,
                mode,
                &mut semantic,
                &mut metrics,
            )?;
        }
        for row in imports {
            batch.imports.push(row);
            remaining_extractor_rows = remaining_extractor_rows.saturating_sub(1);
            flush_if_full(
                &mut batch,
                batch_rows,
                remaining_extractor_rows,
                mode,
                &mut semantic,
                &mut metrics,
            )?;
        }
        for row in calls {
            batch.calls.push(row);
            remaining_extractor_rows = remaining_extractor_rows.saturating_sub(1);
            flush_if_full(
                &mut batch,
                batch_rows,
                remaining_extractor_rows,
                mode,
                &mut semantic,
                &mut metrics,
            )?;
        }
    }

    if !batch.is_empty() {
        observe_and_consume(&mut batch, 0, mode, &mut semantic, &mut metrics)?;
    }

    let declared_live_row_bound = match mode {
        BoundedMode::Native => batch_rows
            .saturating_add(metrics.max_extractor_output_rows)
            .saturating_sub(1),
        BoundedMode::Arrow => batch_rows
            .saturating_mul(2)
            .saturating_add(metrics.max_extractor_output_rows)
            .saturating_sub(1),
    };
    Ok(MaterializationResult {
        semantic: semantic.finish(),
        emitted_flushes: metrics.emitted_flushes,
        max_accumulator_rows: metrics.max_accumulator_rows,
        max_extractor_output_rows: metrics.max_extractor_output_rows,
        max_estimated_live_rows: metrics.max_estimated_live_rows,
        declared_live_row_bound,
        arrow_record_batches: (mode == BoundedMode::Arrow).then_some(metrics.arrow_record_batches),
        max_arrow_batch_rows: (mode == BoundedMode::Arrow).then_some(metrics.max_arrow_batch_rows),
    })
}

fn flush_if_full(
    batch: &mut TypedBatch,
    batch_rows: usize,
    remaining_extractor_rows: usize,
    mode: BoundedMode,
    semantic: &mut SemanticAccumulator,
    metrics: &mut BoundedMetrics,
) -> Result<(), EvaluationError> {
    let accumulator_rows = batch.len();
    metrics.max_accumulator_rows = metrics.max_accumulator_rows.max(accumulator_rows);
    metrics.max_estimated_live_rows = metrics
        .max_estimated_live_rows
        .max(accumulator_rows.saturating_add(remaining_extractor_rows));
    if accumulator_rows == batch_rows {
        observe_and_consume(batch, remaining_extractor_rows, mode, semantic, metrics)?;
    }
    Ok(())
}

fn observe_and_consume(
    batch: &mut TypedBatch,
    remaining_extractor_rows: usize,
    mode: BoundedMode,
    semantic: &mut SemanticAccumulator,
    metrics: &mut BoundedMetrics,
) -> Result<(), EvaluationError> {
    let accumulator_rows = batch.len();
    let representation_multiplier = match mode {
        BoundedMode::Native => 1,
        BoundedMode::Arrow => 2,
    };
    metrics.max_estimated_live_rows = metrics.max_estimated_live_rows.max(
        accumulator_rows
            .saturating_mul(representation_multiplier)
            .saturating_add(remaining_extractor_rows),
    );

    match mode {
        BoundedMode::Native => consume_native_batch(batch, semantic),
        BoundedMode::Arrow => {
            metrics.max_arrow_batch_rows = metrics.max_arrow_batch_rows.max(
                batch
                    .symbols
                    .len()
                    .max(batch.imports.len())
                    .max(batch.calls.len()),
            );
            consume_arrow_batch(batch, semantic, &mut metrics.arrow_record_batches)?
        }
    }
    batch.clear();
    metrics.emitted_flushes += 1;
    Ok(())
}

fn consume_native_batch(batch: &TypedBatch, semantic: &mut SemanticAccumulator) {
    for row in &batch.symbols {
        semantic.push_symbol(row);
    }
    for row in &batch.imports {
        semantic.push_import(row);
    }
    for row in &batch.calls {
        semantic.push_call(row);
    }
}

fn consume_arrow_batch(
    batch: &TypedBatch,
    semantic: &mut SemanticAccumulator,
    counts: &mut ArrowBatchCounts,
) -> Result<(), EvaluationError> {
    if !batch.symbols.is_empty() {
        let record_batch = symbols_to_record_batch(&batch.symbols)?;
        consume_symbol_record_batch(&record_batch, semantic)?;
        counts.symbols += 1;
    }
    if !batch.imports.is_empty() {
        let record_batch = imports_to_record_batch(&batch.imports)?;
        consume_import_record_batch(&record_batch, semantic)?;
        counts.imports += 1;
    }
    if !batch.calls.is_empty() {
        let record_batch = calls_to_record_batch(&batch.calls)?;
        consume_call_record_batch(&record_batch, semantic)?;
        counts.calls += 1;
    }
    Ok(())
}

struct FrozenTemplate {
    language: &'static str,
    extension: &'static str,
    content: &'static str,
}

const FROZEN_TEMPLATES: &[FrozenTemplate] = &[
    FrozenTemplate {
        language: "rust",
        extension: "rs",
        content: r#"use std::{collections::HashMap, sync::Arc};
use crate::engine::Engine as LocalEngine;

pub struct Worker {
    jobs: HashMap<String, usize>,
}

impl Worker {
    pub fn new() -> Self {
        helper();
        Self { jobs: HashMap::new() }
    }

    pub fn run(&self) {
        self.prepare();
        execute();
        LocalEngine::new();
        Arc::new(1usize);
    }

    fn prepare(&self) {
        helper();
    }
}

pub fn execute() {
    helper();
}

fn helper() {}
"#,
    },
    FrozenTemplate {
        language: "python",
        extension: "py",
        content: r#"import os
from pathlib import Path as LocalPath

class Worker:
    def __init__(self):
        self.path = LocalPath(os.getcwd())

    def run(self):
        self.prepare()
        helper()

    def prepare(self):
        helper()

def execute():
    helper()

def helper():
    return os.getcwd()
"#,
    },
    FrozenTemplate {
        language: "typescript",
        extension: "ts",
        content: r#"import { Engine as LocalEngine } from './engine';
import * as path from 'node:path';

export class Worker {
  run(): void {
    this.prepare();
    execute();
    LocalEngine.create();
  }

  prepare(): void {
    helper();
  }
}

export function execute(): void {
  helper();
  path.join('a', 'b');
}

function helper(): void {}
"#,
    },
    FrozenTemplate {
        language: "go",
        extension: "go",
        content: r#"package fixture

import (
    "fmt"
    alias "path/filepath"
)

type Worker struct{}

func NewWorker() *Worker {
    helper()
    return &Worker{}
}

func (w *Worker) Run() {
    w.prepare()
    execute()
    fmt.Println(alias.Join("a", "b"))
}

func (w *Worker) prepare() {
    helper()
}

func execute() {
    helper()
}

func helper() {}
"#,
    },
];

fn extract_frozen_document(document_index: usize) -> Result<ExtractedRows, EvaluationError> {
    let template = &FROZEN_TEMPLATES[document_index % FROZEN_TEMPLATES.len()];
    let path = format!(
        "frozen-v0/{}/{document_index:08}.{}",
        template.language, template.extension
    );
    let detected = detect_language(Path::new(&path))
        .ok_or_else(|| EvaluationError::UnsupportedFixturePath(path.clone()))?;
    if detected != template.language {
        return Err(EvaluationError::FixtureLanguageMismatch {
            path,
            expected: template.language,
            actual: detected,
        });
    }

    Ok(ExtractedRows {
        symbols: extract_symbols(template.content, &path, detected),
        imports: extract_imports(template.content, &path, detected),
        calls: extract_calls(template.content, &path, detected),
    })
}

/// Return the exact frozen-workload identity without materializing extracted rows.
pub fn frozen_workload_identity(documents: usize) -> WorkloadIdentity {
    let mut digest = Sha256::new();
    frame_str(&mut digest, FROZEN_WORKLOAD_SCHEMA);
    frame_str(&mut digest, WORKLOAD_GENERATOR_REVISION);
    frame_u64(&mut digest, documents as u64);
    for template in FROZEN_TEMPLATES {
        frame_str(&mut digest, template.language);
        frame_str(&mut digest, template.extension);
        frame_str(&mut digest, template.content);
    }

    WorkloadIdentity {
        schema: FROZEN_WORKLOAD_SCHEMA.to_string(),
        generator_revision: WORKLOAD_GENERATOR_REVISION.to_string(),
        documents,
        template_count: FROZEN_TEMPLATES.len(),
        manifest_sha256: digest_hex(digest),
    }
}

#[derive(Debug)]
struct FrozenWorkloadShape {
    counts: RowCounts,
    max_extractor_output_rows: usize,
}

fn frozen_workload_shape(documents: usize) -> Result<FrozenWorkloadShape, EvaluationError> {
    if documents == 0 {
        return Err(EvaluationError::EmptyWorkload);
    }
    let complete_cycles = documents / FROZEN_TEMPLATES.len();
    let remainder = documents % FROZEN_TEMPLATES.len();
    let mut counts = RowCounts {
        symbols: 0,
        imports: 0,
        calls: 0,
    };
    let mut max_extractor_output_rows = 0;
    for template_index in 0..FROZEN_TEMPLATES.len() {
        let repetitions = complete_cycles + usize::from(template_index < remainder);
        if repetitions == 0 {
            continue;
        }
        let rows = extract_frozen_document(template_index)?;
        let repetitions =
            u64::try_from(repetitions).map_err(|_| EvaluationError::WorkloadSizeOverflow)?;
        counts.symbols = checked_scaled_add(counts.symbols, rows.symbols.len(), repetitions)?;
        counts.imports = checked_scaled_add(counts.imports, rows.imports.len(), repetitions)?;
        counts.calls = checked_scaled_add(counts.calls, rows.calls.len(), repetitions)?;
        max_extractor_output_rows = max_extractor_output_rows.max(rows.len());
    }
    Ok(FrozenWorkloadShape {
        counts,
        max_extractor_output_rows,
    })
}

fn checked_scaled_add(
    current: u64,
    rows_per_document: usize,
    repetitions: u64,
) -> Result<u64, EvaluationError> {
    let rows_per_document =
        u64::try_from(rows_per_document).map_err(|_| EvaluationError::WorkloadSizeOverflow)?;
    current
        .checked_add(
            rows_per_document
                .checked_mul(repetitions)
                .ok_or(EvaluationError::WorkloadSizeOverflow)?,
        )
        .ok_or(EvaluationError::WorkloadSizeOverflow)
}

/// Validate all deterministic and structural claims in one child receipt.
pub fn validate_evaluation_receipt(receipt: &EvaluationReceipt) -> Result<(), EvaluationError> {
    if receipt.workload.documents == 0 || receipt.batch_rows == 0 {
        return Err(EvaluationError::ReceiptContract(
            "documents and batch_rows must be positive".to_string(),
        ));
    }
    let shape = frozen_workload_shape(receipt.workload.documents)?;
    let total_rows =
        usize::try_from(shape.counts.total()).map_err(|_| EvaluationError::WorkloadSizeOverflow)?;
    let expected_workload = frozen_workload_identity(receipt.workload.documents);
    let common_valid = receipt.schema == EVALUATION_RECEIPT_SCHEMA
        && receipt.workload == expected_workload
        && receipt.semantic.schema == SEMANTIC_SCHEMA
        && receipt.semantic.counts == shape.counts
        && is_lower_hex(&receipt.semantic.symbols_sha256, 64)
        && is_lower_hex(&receipt.semantic.imports_sha256, 64)
        && is_lower_hex(&receipt.semantic.calls_sha256, 64)
        && is_lower_hex(&receipt.semantic.combined_sha256, 64)
        && receipt.max_extractor_output_rows == shape.max_extractor_output_rows
        && receipt.elapsed_ns > 0
        && !receipt.sqlite_accessed
        && !receipt.production_write;
    if !common_valid {
        return Err(EvaluationError::ReceiptContract(
            "common workload, semantic, metric, or authority fields are inconsistent".to_string(),
        ));
    }

    let mode_valid = match receipt.mode {
        EvaluationMode::FullVec => {
            receipt.emitted_flushes == u64::from(total_rows > 0)
                && receipt.max_accumulator_rows == total_rows
                && receipt.max_estimated_live_rows == total_rows
                && receipt.declared_live_row_bound == total_rows
                && receipt.arrow_record_batches.is_none()
                && receipt.max_arrow_batch_rows.is_none()
                && receipt.arrow_schema_fingerprints.is_none()
        }
        EvaluationMode::NativeChunk => {
            bounded_receipt_shape_valid(receipt, &shape, total_rows, false)
                && receipt.arrow_record_batches.is_none()
                && receipt.max_arrow_batch_rows.is_none()
                && receipt.arrow_schema_fingerprints.is_none()
        }
        EvaluationMode::ArrowRecordBatch => {
            bounded_receipt_shape_valid(receipt, &shape, total_rows, true)
                && arrow_batch_metrics_valid(receipt, &shape)
                && receipt.arrow_schema_fingerprints.as_ref() == Some(&arrow_schema_fingerprints())
        }
    };
    if mode_valid {
        Ok(())
    } else {
        Err(EvaluationError::ReceiptContract(format!(
            "mode-specific metrics are inconsistent for {:?}",
            receipt.mode
        )))
    }
}

fn bounded_receipt_shape_valid(
    receipt: &EvaluationReceipt,
    shape: &FrozenWorkloadShape,
    total_rows: usize,
    arrow: bool,
) -> bool {
    let expected_flushes = total_rows.div_ceil(receipt.batch_rows) as u64;
    let representation_rows = if arrow {
        receipt.batch_rows.saturating_mul(2)
    } else {
        receipt.batch_rows
    };
    let expected_bound = representation_rows
        .saturating_add(shape.max_extractor_output_rows)
        .saturating_sub(1);
    let minimum_observed_live_rows = if arrow {
        receipt.max_accumulator_rows.saturating_mul(2)
    } else {
        receipt.max_accumulator_rows
    }
    .max(shape.max_extractor_output_rows);
    receipt.emitted_flushes == expected_flushes
        && receipt.max_accumulator_rows == receipt.batch_rows.min(total_rows)
        && receipt.max_estimated_live_rows >= minimum_observed_live_rows
        && receipt.max_estimated_live_rows <= receipt.declared_live_row_bound
        && receipt.declared_live_row_bound == expected_bound
}

fn arrow_batch_metrics_valid(receipt: &EvaluationReceipt, shape: &FrozenWorkloadShape) -> bool {
    let Some(counts) = receipt.arrow_record_batches.as_ref() else {
        return false;
    };
    let Some(max_arrow_batch_rows) = receipt.max_arrow_batch_rows else {
        return false;
    };
    let batch_rows = receipt.batch_rows as u64;
    let min_symbol_batches = shape.counts.symbols.div_ceil(batch_rows);
    let min_import_batches = shape.counts.imports.div_ceil(batch_rows);
    let min_call_batches = shape.counts.calls.div_ceil(batch_rows);
    counts.symbols >= min_symbol_batches
        && counts.imports >= min_import_batches
        && counts.calls >= min_call_batches
        && counts.symbols <= receipt.emitted_flushes
        && counts.imports <= receipt.emitted_flushes
        && counts.calls <= receipt.emitted_flushes
        && counts.total() >= receipt.emitted_flushes
        && counts.total() <= receipt.emitted_flushes.saturating_mul(3)
        && max_arrow_batch_rows > 0
        && max_arrow_batch_rows <= receipt.batch_rows
}

/// Cached production-shaped schemas for the three logical codebase-index tables.
pub fn arrow_schemas() -> &'static ArrowSchemas {
    static SCHEMAS: OnceLock<ArrowSchemas> = OnceLock::new();
    SCHEMAS.get_or_init(|| ArrowSchemas {
        symbols: Arc::new(Schema::new_with_metadata(
            vec![
                Field::new("file_path", DataType::Utf8, false),
                Field::new("line", DataType::UInt32, false),
                Field::new("col", DataType::UInt32, false),
                Field::new("kind", DataType::Utf8, false),
                Field::new("name", DataType::Utf8, false),
                Field::new("signature", DataType::Utf8, false),
                Field::new("language", DataType::Utf8, false),
                Field::new("score", DataType::Float32, true),
            ],
            arrow_metadata("symbols"),
        )),
        imports: Arc::new(Schema::new_with_metadata(
            vec![
                Field::new("file_path", DataType::Utf8, false),
                Field::new("line", DataType::UInt32, false),
                Field::new("language", DataType::Utf8, false),
                Field::new("raw", DataType::Utf8, false),
                Field::new("target", DataType::Utf8, false),
                Field::new("alias", DataType::Utf8, true),
            ],
            arrow_metadata("imports"),
        )),
        calls: Arc::new(Schema::new_with_metadata(
            vec![
                Field::new("file_path", DataType::Utf8, false),
                Field::new("line", DataType::UInt32, false),
                Field::new("language", DataType::Utf8, false),
                Field::new("caller", DataType::Utf8, false),
                Field::new("callee", DataType::Utf8, false),
            ],
            arrow_metadata("calls"),
        )),
    })
}

fn arrow_metadata(logical_table: &str) -> HashMap<String, String> {
    HashMap::from([
        (
            ARROW_SCHEMA_META_KEY.to_string(),
            ARROW_SCHEMA_CONTRACT.to_string(),
        ),
        (
            ARROW_PURPOSE_META_KEY.to_string(),
            "evaluation_only_no_sqlite_authority".to_string(),
        ),
        ("ab.logical_table".to_string(), logical_table.to_string()),
    ])
}

fn symbols_to_record_batch(rows: &[CodebaseSymbol]) -> Result<RecordBatch, ArrowError> {
    let schemas = arrow_schemas();
    let file_path = StringArray::from_iter_values(rows.iter().map(|row| row.file_path.as_str()));
    let line = UInt32Array::from_iter_values(rows.iter().map(|row| row.line));
    let col = UInt32Array::from_iter_values(rows.iter().map(|row| row.col));
    let kind = StringArray::from_iter_values(rows.iter().map(|row| row.kind.as_str()));
    let name = StringArray::from_iter_values(rows.iter().map(|row| row.name.as_str()));
    let signature = StringArray::from_iter_values(rows.iter().map(|row| row.signature.as_str()));
    let language = StringArray::from_iter_values(rows.iter().map(|row| row.language.as_str()));
    let score: Float32Array = rows.iter().map(|row| row.score).collect();
    RecordBatch::try_new(
        Arc::clone(&schemas.symbols),
        vec![
            Arc::new(file_path),
            Arc::new(line),
            Arc::new(col),
            Arc::new(kind),
            Arc::new(name),
            Arc::new(signature),
            Arc::new(language),
            Arc::new(score),
        ],
    )
}

fn imports_to_record_batch(rows: &[CodebaseImport]) -> Result<RecordBatch, ArrowError> {
    let schemas = arrow_schemas();
    let file_path = StringArray::from_iter_values(rows.iter().map(|row| row.file_path.as_str()));
    let line = UInt32Array::from_iter_values(rows.iter().map(|row| row.line));
    let language = StringArray::from_iter_values(rows.iter().map(|row| row.language.as_str()));
    let raw = StringArray::from_iter_values(rows.iter().map(|row| row.raw.as_str()));
    let target = StringArray::from_iter_values(rows.iter().map(|row| row.target.as_str()));
    let alias: StringArray = rows.iter().map(|row| row.alias.as_deref()).collect();
    RecordBatch::try_new(
        Arc::clone(&schemas.imports),
        vec![
            Arc::new(file_path),
            Arc::new(line),
            Arc::new(language),
            Arc::new(raw),
            Arc::new(target),
            Arc::new(alias),
        ],
    )
}

fn calls_to_record_batch(rows: &[CodebaseCall]) -> Result<RecordBatch, ArrowError> {
    let schemas = arrow_schemas();
    let file_path = StringArray::from_iter_values(rows.iter().map(|row| row.file_path.as_str()));
    let line = UInt32Array::from_iter_values(rows.iter().map(|row| row.line));
    let language = StringArray::from_iter_values(rows.iter().map(|row| row.language.as_str()));
    let caller = StringArray::from_iter_values(rows.iter().map(|row| row.caller.as_str()));
    let callee = StringArray::from_iter_values(rows.iter().map(|row| row.callee.as_str()));
    RecordBatch::try_new(
        Arc::clone(&schemas.calls),
        vec![
            Arc::new(file_path),
            Arc::new(line),
            Arc::new(language),
            Arc::new(caller),
            Arc::new(callee),
        ],
    )
}

fn consume_symbol_record_batch(
    batch: &RecordBatch,
    semantic: &mut SemanticAccumulator,
) -> Result<(), EvaluationError> {
    ensure_schema(batch, &arrow_schemas().symbols, "symbols")?;
    let file_path = string_column(batch, 0, "file_path")?;
    let line = u32_column(batch, 1, "line")?;
    let col = u32_column(batch, 2, "col")?;
    let kind = string_column(batch, 3, "kind")?;
    let name = string_column(batch, 4, "name")?;
    let signature = string_column(batch, 5, "signature")?;
    let language = string_column(batch, 6, "language")?;
    let score = f32_column(batch, 7, "score")?;
    for index in 0..batch.num_rows() {
        semantic.push_symbol_fields(
            required_str(file_path, index, "file_path")?,
            required_u32(line, index, "line")?,
            required_u32(col, index, "col")?,
            required_str(kind, index, "kind")?,
            required_str(name, index, "name")?,
            required_str(signature, index, "signature")?,
            required_str(language, index, "language")?,
            optional_f32(score, index),
        );
    }
    Ok(())
}

fn consume_import_record_batch(
    batch: &RecordBatch,
    semantic: &mut SemanticAccumulator,
) -> Result<(), EvaluationError> {
    ensure_schema(batch, &arrow_schemas().imports, "imports")?;
    let file_path = string_column(batch, 0, "file_path")?;
    let line = u32_column(batch, 1, "line")?;
    let language = string_column(batch, 2, "language")?;
    let raw = string_column(batch, 3, "raw")?;
    let target = string_column(batch, 4, "target")?;
    let alias = string_column(batch, 5, "alias")?;
    for index in 0..batch.num_rows() {
        semantic.push_import_fields(
            required_str(file_path, index, "file_path")?,
            required_u32(line, index, "line")?,
            required_str(language, index, "language")?,
            required_str(raw, index, "raw")?,
            required_str(target, index, "target")?,
            optional_str(alias, index),
        );
    }
    Ok(())
}

fn consume_call_record_batch(
    batch: &RecordBatch,
    semantic: &mut SemanticAccumulator,
) -> Result<(), EvaluationError> {
    ensure_schema(batch, &arrow_schemas().calls, "calls")?;
    let file_path = string_column(batch, 0, "file_path")?;
    let line = u32_column(batch, 1, "line")?;
    let language = string_column(batch, 2, "language")?;
    let caller = string_column(batch, 3, "caller")?;
    let callee = string_column(batch, 4, "callee")?;
    for index in 0..batch.num_rows() {
        semantic.push_call_fields(
            required_str(file_path, index, "file_path")?,
            required_u32(line, index, "line")?,
            required_str(language, index, "language")?,
            required_str(caller, index, "caller")?,
            required_str(callee, index, "callee")?,
        );
    }
    Ok(())
}

fn ensure_schema(
    batch: &RecordBatch,
    expected: &Arc<Schema>,
    logical_table: &str,
) -> Result<(), EvaluationError> {
    if batch.schema().as_ref() != expected.as_ref() {
        return Err(EvaluationError::ArrowContract(format!(
            "unexpected {logical_table} schema or metadata"
        )));
    }
    Ok(())
}

/// Canonical fingerprints for all three table-shaped schemas.
pub fn arrow_schema_fingerprints() -> ArrowSchemaFingerprints {
    static FINGERPRINTS: OnceLock<ArrowSchemaFingerprints> = OnceLock::new();
    FINGERPRINTS
        .get_or_init(|| {
            let schemas = arrow_schemas();
            let symbols_sha256 = schema_fingerprint(&schemas.symbols);
            let imports_sha256 = schema_fingerprint(&schemas.imports);
            let calls_sha256 = schema_fingerprint(&schemas.calls);
            let mut combined = Sha256::new();
            frame_str(&mut combined, ARROW_SCHEMA_CONTRACT);
            frame_str(&mut combined, &symbols_sha256);
            frame_str(&mut combined, &imports_sha256);
            frame_str(&mut combined, &calls_sha256);
            ArrowSchemaFingerprints {
                symbols_sha256,
                imports_sha256,
                calls_sha256,
                combined_sha256: digest_hex(combined),
            }
        })
        .clone()
}

fn schema_fingerprint(schema: &Schema) -> String {
    let mut digest = Sha256::new();
    frame_str(&mut digest, ARROW_SCHEMA_CONTRACT);
    for field in schema.fields() {
        frame_str(&mut digest, field.name());
        frame_str(&mut digest, &format!("{:?}", field.data_type()));
        digest.update([u8::from(field.is_nullable())]);
    }
    let mut metadata: Vec<_> = schema.metadata().iter().collect();
    metadata.sort_by(|left, right| left.0.cmp(right.0));
    for (key, value) in metadata {
        frame_str(&mut digest, key);
        frame_str(&mut digest, value);
    }
    digest_hex(digest)
}

fn string_column<'a>(
    batch: &'a RecordBatch,
    index: usize,
    name: &str,
) -> Result<&'a StringArray, EvaluationError> {
    batch
        .column(index)
        .as_any()
        .downcast_ref::<StringArray>()
        .ok_or_else(|| EvaluationError::ArrowContract(format!("column {name} is not Utf8")))
}

fn u32_column<'a>(
    batch: &'a RecordBatch,
    index: usize,
    name: &str,
) -> Result<&'a UInt32Array, EvaluationError> {
    batch
        .column(index)
        .as_any()
        .downcast_ref::<UInt32Array>()
        .ok_or_else(|| EvaluationError::ArrowContract(format!("column {name} is not UInt32")))
}

fn f32_column<'a>(
    batch: &'a RecordBatch,
    index: usize,
    name: &str,
) -> Result<&'a Float32Array, EvaluationError> {
    batch
        .column(index)
        .as_any()
        .downcast_ref::<Float32Array>()
        .ok_or_else(|| EvaluationError::ArrowContract(format!("column {name} is not Float32")))
}

fn required_str<'a>(
    column: &'a StringArray,
    index: usize,
    name: &str,
) -> Result<&'a str, EvaluationError> {
    if column.is_null(index) {
        return Err(EvaluationError::ArrowContract(format!(
            "required column {name} is null at row {index}"
        )));
    }
    Ok(column.value(index))
}

fn optional_str(column: &StringArray, index: usize) -> Option<&str> {
    (!column.is_null(index)).then(|| column.value(index))
}

fn required_u32(column: &UInt32Array, index: usize, name: &str) -> Result<u32, EvaluationError> {
    if column.is_null(index) {
        return Err(EvaluationError::ArrowContract(format!(
            "required column {name} is null at row {index}"
        )));
    }
    Ok(column.value(index))
}

fn optional_f32(column: &Float32Array, index: usize) -> Option<f32> {
    (!column.is_null(index)).then(|| column.value(index))
}

struct SemanticAccumulator {
    symbols: Sha256,
    imports: Sha256,
    calls: Sha256,
    counts: RowCounts,
}

impl SemanticAccumulator {
    fn new() -> Self {
        let mut symbols = Sha256::new();
        let mut imports = Sha256::new();
        let mut calls = Sha256::new();
        frame_str(&mut symbols, "agent-bridge/codebase-index/symbols/v0");
        frame_str(&mut imports, "agent-bridge/codebase-index/imports/v0");
        frame_str(&mut calls, "agent-bridge/codebase-index/calls/v0");
        Self {
            symbols,
            imports,
            calls,
            counts: RowCounts {
                symbols: 0,
                imports: 0,
                calls: 0,
            },
        }
    }

    fn push_symbol(&mut self, value: &CodebaseSymbol) {
        self.push_symbol_fields(
            &value.file_path,
            value.line,
            value.col,
            &value.kind,
            &value.name,
            &value.signature,
            &value.language,
            value.score,
        );
    }

    #[allow(clippy::too_many_arguments)]
    fn push_symbol_fields(
        &mut self,
        file_path: &str,
        line: u32,
        col: u32,
        kind: &str,
        name: &str,
        signature: &str,
        language: &str,
        score: Option<f32>,
    ) {
        frame_str(&mut self.symbols, file_path);
        frame_u32(&mut self.symbols, line);
        frame_u32(&mut self.symbols, col);
        frame_str(&mut self.symbols, kind);
        frame_str(&mut self.symbols, name);
        frame_str(&mut self.symbols, signature);
        frame_str(&mut self.symbols, language);
        frame_optional_f32(&mut self.symbols, score);
        self.counts.symbols += 1;
    }

    fn push_import(&mut self, value: &CodebaseImport) {
        self.push_import_fields(
            &value.file_path,
            value.line,
            &value.language,
            &value.raw,
            &value.target,
            value.alias.as_deref(),
        );
    }

    fn push_import_fields(
        &mut self,
        file_path: &str,
        line: u32,
        language: &str,
        raw: &str,
        target: &str,
        alias: Option<&str>,
    ) {
        frame_str(&mut self.imports, file_path);
        frame_u32(&mut self.imports, line);
        frame_str(&mut self.imports, language);
        frame_str(&mut self.imports, raw);
        frame_str(&mut self.imports, target);
        frame_optional_str(&mut self.imports, alias);
        self.counts.imports += 1;
    }

    fn push_call(&mut self, value: &CodebaseCall) {
        self.push_call_fields(
            &value.file_path,
            value.line,
            &value.language,
            &value.caller,
            &value.callee,
        );
    }

    fn push_call_fields(
        &mut self,
        file_path: &str,
        line: u32,
        language: &str,
        caller: &str,
        callee: &str,
    ) {
        frame_str(&mut self.calls, file_path);
        frame_u32(&mut self.calls, line);
        frame_str(&mut self.calls, language);
        frame_str(&mut self.calls, caller);
        frame_str(&mut self.calls, callee);
        self.counts.calls += 1;
    }

    fn finish(self) -> SemanticReceipt {
        let symbols: [u8; 32] = self.symbols.finalize().into();
        let imports: [u8; 32] = self.imports.finalize().into();
        let calls: [u8; 32] = self.calls.finalize().into();
        let mut combined = Sha256::new();
        frame_str(&mut combined, SEMANTIC_SCHEMA);
        frame_u64(&mut combined, self.counts.symbols);
        combined.update(symbols);
        frame_u64(&mut combined, self.counts.imports);
        combined.update(imports);
        frame_u64(&mut combined, self.counts.calls);
        combined.update(calls);

        SemanticReceipt {
            schema: SEMANTIC_SCHEMA.to_string(),
            counts: self.counts,
            symbols_sha256: bytes_hex(&symbols),
            imports_sha256: bytes_hex(&imports),
            calls_sha256: bytes_hex(&calls),
            combined_sha256: digest_hex(combined),
        }
    }
}

fn frame_str(digest: &mut Sha256, value: &str) {
    frame_u64(digest, value.len() as u64);
    digest.update(value.as_bytes());
}

fn frame_optional_str(digest: &mut Sha256, value: Option<&str>) {
    match value {
        Some(value) => {
            digest.update([1]);
            frame_str(digest, value);
        }
        None => digest.update([0]),
    }
}

fn frame_optional_f32(digest: &mut Sha256, value: Option<f32>) {
    match value {
        Some(value) => {
            digest.update([1]);
            digest.update(value.to_bits().to_be_bytes());
        }
        None => digest.update([0]),
    }
}

fn frame_u32(digest: &mut Sha256, value: u32) {
    digest.update(value.to_be_bytes());
}

fn frame_u64(digest: &mut Sha256, value: u64) {
    digest.update(value.to_be_bytes());
}

fn digest_hex(digest: Sha256) -> String {
    bytes_hex(digest.finalize().as_slice())
}

fn bytes_hex(bytes: &[u8]) -> String {
    use std::fmt::Write as _;

    let mut output = String::with_capacity(bytes.len() * 2);
    for byte in bytes {
        let _ = write!(output, "{byte:02x}");
    }
    output
}

fn saturating_u64(value: u128) -> u64 {
    u64::try_from(value).unwrap_or(u64::MAX)
}

#[cfg(target_os = "linux")]
fn peak_rss_kib() -> Option<u64> {
    let status = std::fs::read_to_string("/proc/self/status").ok()?;
    let line = status.lines().find(|line| line.starts_with("VmHWM:"))?;
    line.split_whitespace().nth(1)?.parse().ok()
}

#[cfg(not(target_os = "linux"))]
fn peak_rss_kib() -> Option<u64> {
    None
}
