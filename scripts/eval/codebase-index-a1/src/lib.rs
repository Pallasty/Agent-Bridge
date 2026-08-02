//! Fail-closed assessor and evidence types for the codebase-index A1 experiment.
//!
//! This crate is an evaluation-only nested workspace. It has no runtime or
//! deployment authority and does not change the production `codebase_index`
//! dispatch path.

use std::path::{Path, PathBuf};

use serde::{Deserialize, Serialize};
use sha2::{Digest, Sha256};

pub mod provenance;
pub mod snapshot;
pub mod workload;

pub const RUN_RECEIPT_SCHEMA: &str = "agent_bridge.codebase_index.a1.run_receipt.v0";
pub const SUITE_RECEIPT_SCHEMA: &str = "agent_bridge.codebase_index.a1.suite_receipt.v0";
pub const CANONICAL_DOCUMENTS: u64 = 100_000;
pub const CANONICAL_TOTAL_ROWS: u64 = 1_400_000;
pub const CANONICAL_BATCH_ROWS: usize = 4_096;
pub const CANONICAL_PAIRS: usize = 10;
pub const REQUIRED_JOINT_RESOURCE_PAIRS: usize = 8;
pub const REQUIRED_TX_PAIRS: usize = 8;
pub const REQUIRED_WAL_PAIRS: usize = 8;
pub const RSS_REDUCTION_BPS: u64 = 3_000;
pub const ELAPSED_REGRESSION_BPS: u64 = 1_000;
pub const TX_MEDIAN_REGRESSION_BPS: u64 = 1_000;
pub const TX_PAIR_REGRESSION_BPS: u64 = 2_000;
pub const WAL_REGRESSION_BPS: u64 = 500;
pub const CGROUP_PEAK_REGRESSION_BPS: u64 = 500;

#[derive(Debug, Clone, Copy, Serialize, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "kebab-case")]
pub enum Mode {
    FullVec,
    StagedNative,
}

#[derive(Debug, Clone, Copy, Serialize, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "snake_case")]
pub enum EvidenceClass {
    Diagnostic,
    Canonical,
}

#[derive(Debug, Clone, Copy, Serialize, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "UPPERCASE")]
pub enum TrialOrder {
    Ab,
    Ba,
}

impl TrialOrder {
    pub fn modes(self) -> [Mode; 2] {
        match self {
            Self::Ab => [Mode::FullVec, Mode::StagedNative],
            Self::Ba => [Mode::StagedNative, Mode::FullVec],
        }
    }
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct BuildIdentity {
    pub revision: String,
    pub tree_clean: bool,
    pub profile: String,
    pub cargo_lock_sha256: String,
    pub tracked_source_sha256: String,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub executable_sha256: Option<String>,
    pub target: String,
    pub opt_level: String,
    pub debug_assertions: bool,
    pub encoded_rustflags_sha256: String,
    pub profile_overrides_present: bool,
    pub rustc_version: String,
    pub build_features: String,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct Provenance {
    pub build: BuildIdentity,
    pub runtime_before: BuildIdentity,
    pub runtime_after: BuildIdentity,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct RuntimeEnvironmentEvidence {
    pub kernel_release: String,
    pub cpu_model: String,
    pub cpu_microcode: String,
    pub process_affinity: String,
    pub canonical_cpu: u32,
    pub excluded_smt_sibling: u32,
    pub canonical_cpu_siblings: String,
    pub libc: String,
    pub allocator: String,
    pub systemd_version: String,
    pub loadavg: String,
    pub cpu_pressure: String,
    pub memory_pressure: String,
    pub io_pressure: String,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct Workload {
    pub schema: String,
    pub generator_revision: String,
    pub manifest_sha256: String,
    /// Digest of the actual generated relative paths and bytes, not merely the
    /// generator templates.
    pub corpus_sha256: String,
    pub documents: u64,
    pub symbols: u64,
    pub imports: u64,
    pub calls: u64,
    pub total_rows: u64,
    pub batch_rows: usize,
    pub max_extractor_output_rows: usize,
    pub symbols_sha256: String,
    pub imports_sha256: String,
    pub calls_sha256: String,
    pub combined_sha256: String,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct Measurement {
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub elapsed_ns: Option<u64>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub peak_rss_bytes: Option<u64>,
    /// `/proc/self/status` VmHWM, retained separately so the assessor can
    /// prove the primary RSS value is `max(VmHWM, getrusage)`.
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub vm_hwm_bytes: Option<u64>,
    /// Measured inside the authoritative SQLite transaction. The current
    /// FullVec API does not expose this; canonical evidence must reject that
    /// gap instead of substituting end-to-end elapsed time.
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub authoritative_transaction_ns: Option<u64>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub cgroup_path: Option<String>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub cgroup_memory_current_before_bytes: Option<u64>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub cgroup_memory_current_after_bytes: Option<u64>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub cgroup_memory_peak_before_bytes: Option<u64>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub cgroup_memory_peak_after_bytes: Option<u64>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub cgroup_memory_max: Option<String>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub cgroup_process_count: Option<u64>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub cgroup_is_shared: Option<bool>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub cgroup_isolated_for_trial: Option<bool>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub cgroup_memory_anon_before_bytes: Option<u64>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub cgroup_memory_anon_after_bytes: Option<u64>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub cgroup_memory_file_before_bytes: Option<u64>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub cgroup_memory_file_after_bytes: Option<u64>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub cgroup_memory_shmem_before_bytes: Option<u64>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub cgroup_memory_shmem_after_bytes: Option<u64>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub cgroup_memory_anon_delta_bytes: Option<i64>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub cgroup_memory_file_delta_bytes: Option<i64>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub cgroup_memory_shmem_delta_bytes: Option<i64>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub proc_io_read_bytes_before: Option<u64>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub proc_io_read_bytes_after: Option<u64>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub proc_io_write_bytes_before: Option<u64>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub proc_io_write_bytes_after: Option<u64>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub rusage_minor_faults_before: Option<u64>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub rusage_minor_faults_after: Option<u64>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub rusage_major_faults_before: Option<u64>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub rusage_major_faults_after: Option<u64>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub getrusage_max_rss_bytes: Option<u64>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub parent_wait4_max_rss_bytes: Option<u64>,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct DatabaseEvidence {
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub schema_sha256: Option<String>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub semantic_sha256: Option<String>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub page_count: Option<u64>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub freelist_count: Option<u64>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub wal_bytes: Option<u64>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub database_bytes: Option<u64>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub shm_bytes: Option<u64>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub wal_frames: Option<u64>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub wal_checkpoint_log_frames: Option<u64>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub wal_checkpointed_frames: Option<u64>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub wal_checkpoint_busy: Option<u64>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub wal_layout_valid: Option<bool>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub page_size: Option<u64>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub journal_mode: Option<String>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub root_rows: Option<u64>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub null_embeddings: Option<u64>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub indexed_at_values: Option<u64>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub sqlite_version: Option<String>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub sqlite_compile_options_sha256: Option<String>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub generation_sha256: Option<String>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub integrity_check: Option<String>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub foreign_key_violations: Option<u64>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub schema_meta_version: Option<String>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub schema_meta_sha256: Option<String>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub schema_version: Option<u64>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub user_version: Option<u64>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub synchronous: Option<i64>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub wal_autocheckpoint: Option<i64>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub cache_size: Option<i64>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub cache_spill: Option<i64>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub temp_store: Option<i64>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub mmap_size: Option<i64>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub foreign_keys: Option<i64>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub busy_timeout_ms: Option<i64>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub locking_mode: Option<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct FixtureEvidence {
    pub base_fixture_sha256: String,
    pub database_copy_sha256_before: String,
    pub base_sidecars_absent_before: bool,
    pub target_rows_before: u64,
    pub target_nonnull_embeddings_before: u64,
    pub target_generation_sha256_before: String,
    pub target_generation_sha256_after: String,
    /// Exact target rows, including every raw field, row id, embedding bytes,
    /// and the real indexed_at value. This is deliberately not normalized.
    pub target_raw_sha256_before: String,
    pub target_raw_sha256_after: String,
    pub other_root_sha256_before: String,
    pub other_root_sha256_after: String,
    pub non_codebase_sentinel_sha256_before: String,
    pub non_codebase_sentinel_sha256_after: String,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct BaseFixturePreflightReceipt {
    pub schema: String,
    pub build_identity: BuildIdentity,
    pub runtime_environment: RuntimeEnvironmentEvidence,
    pub workload: Workload,
    pub base_fixture_sha256: String,
    pub database_copy_sha256: String,
    pub sidecars_absent: bool,
    pub target_rows: u64,
    pub target_nonnull_embeddings: u64,
    pub target_generation_sha256: String,
    pub target_raw_sha256: String,
    pub other_root_sha256: String,
    pub non_codebase_sentinel_sha256: String,
    pub database: DatabaseEvidence,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct AuthoritativePragmaEvidence {
    pub journal_mode: String,
    pub synchronous: i64,
    pub wal_autocheckpoint: i64,
    pub cache_size: i64,
    pub cache_spill: i64,
    pub temp_store: i64,
    pub mmap_size: i64,
    pub foreign_keys: i64,
    pub busy_timeout_ms: i64,
    pub locking_mode: String,
    pub autocommit: bool,
    pub database_names: Vec<String>,
    pub database_files: Vec<PathBuf>,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct StorageEvidence {
    pub trial_root: PathBuf,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub mount_point: Option<PathBuf>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub filesystem_type: Option<String>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub trial_device: Option<u64>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub database_device: Option<u64>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub staging_device: Option<u64>,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct AuthorityEvidence {
    pub isolated_sqlite_accessed: bool,
    pub live_database_touched: bool,
    pub production_write: bool,
    pub runtime_adoption_authorized: bool,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct HostStorageContext {
    pub configured_default_db_path: PathBuf,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub resolved_default_db_path: Option<PathBuf>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub mount_point: Option<PathBuf>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub filesystem_type: Option<String>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub device: Option<u64>,
    pub live_substrate_is_canonical_gate: bool,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct StagedNativeEvidence {
    pub strategy: String,
    pub batch_rows: usize,
    pub emitted_batches: u64,
    pub staging_file_bytes: u64,
    pub staging_file_path: PathBuf,
    pub staging_file_device: u64,
    pub staging_file_mount_point: PathBuf,
    pub staging_file_filesystem_type: String,
    pub declared_live_row_bound: usize,
    pub max_accumulator_rows: usize,
    pub max_extractor_output_rows: usize,
    pub staging_rows: u64,
    pub staging_cleanup_succeeded: bool,
    pub staging_transaction_committed: bool,
    pub authoritative_transaction_committed: bool,
    pub staging_parent_was_explicit: bool,
    pub autocommit_before: bool,
    pub autocommit_during: bool,
    pub autocommit_after: bool,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct FullVecEvidence {
    pub strategy: String,
    pub extraction_and_accumulation_ns: u64,
    pub autocommit_before: bool,
    pub autocommit_during: bool,
    pub autocommit_after: bool,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct RunReceipt {
    pub schema: String,
    pub mode: Mode,
    pub execution: ChildExecutionEvidence,
    pub build_identity: BuildIdentity,
    pub workload: Workload,
    pub measurement: Measurement,
    pub database: DatabaseEvidence,
    pub fixture: FixtureEvidence,
    pub authoritative_pragmas_before: AuthoritativePragmaEvidence,
    pub authoritative_pragmas_after: AuthoritativePragmaEvidence,
    pub wal_reset: WalResetEvidence,
    pub storage: StorageEvidence,
    pub authority: AuthorityEvidence,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub full_vec: Option<FullVecEvidence>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub staged_native: Option<StagedNativeEvidence>,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct ChildExecutionEvidence {
    pub mode: Mode,
    pub sequence: usize,
    pub process_id: u32,
    pub started_unix_ns: u64,
    pub finished_unix_ns: u64,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct WalResetEvidence {
    pub busy: u64,
    pub log_frames: u64,
    pub checkpointed_frames: u64,
    pub wal_bytes: u64,
    pub proven_empty: bool,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct TrialPair {
    pub pair_index: usize,
    pub order: TrialOrder,
    pub observed_order: [Mode; 2],
    pub observed_execution: [ChildExecutionEvidence; 2],
    pub full_vec: RunReceipt,
    pub staged_native: RunReceipt,
}

#[derive(Debug, Clone, Copy, Serialize, Deserialize, PartialEq, Eq, PartialOrd, Ord)]
#[serde(rename_all = "snake_case")]
pub enum FailureCase {
    AfterStagingBatch,
    AfterDeleteSymbols,
    AfterDeleteImports,
    AfterDeleteCalls,
    AfterSymbolRows,
    AfterImportRows,
    AfterCallRows,
    BeforeCommit,
}

impl FailureCase {
    pub const fn expected_error_marker(self) -> &'static str {
        match self {
            Self::AfterStagingBatch => "A1 injected failpoint: after_staging_batch 1",
            Self::AfterDeleteSymbols => "A1 injected failpoint: after_delete_symbols",
            Self::AfterDeleteImports => "A1 injected failpoint: after_delete_imports",
            Self::AfterDeleteCalls => "A1 injected failpoint: after_delete_calls",
            Self::AfterSymbolRows => "A1 injected failpoint: after_symbol_rows",
            Self::AfterImportRows => "A1 injected failpoint: after_import_rows",
            Self::AfterCallRows => "A1 injected failpoint: after_call_rows",
            Self::BeforeCommit => "A1 injected failpoint: before_commit",
        }
    }
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct RollbackStateEvidence {
    pub target_raw_sha256: String,
    pub other_root_sha256: String,
    pub non_codebase_sentinel_sha256: String,
    pub schema_sha256: String,
    pub schema_meta_sha256: String,
    pub schema_version: u64,
    pub user_version: u64,
    pub page_count: u64,
    pub freelist_count: u64,
    pub integrity_check: String,
    pub foreign_key_violations: u64,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct PostFaultQueryEvidence {
    pub query: String,
    pub succeeded: bool,
    pub result_sha256: String,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct FailureAtomicityReceipt {
    pub case: FailureCase,
    pub build_identity: BuildIdentity,
    pub expected_error_observed: bool,
    pub expected_error_marker: String,
    pub observed_error: String,
    pub target_generation_sha256_before: String,
    pub target_generation_sha256_after: String,
    pub other_root_sha256_before: String,
    pub other_root_sha256_after: String,
    pub non_codebase_sentinel_sha256_before: String,
    pub non_codebase_sentinel_sha256_after: String,
    pub rollback_before: RollbackStateEvidence,
    pub rollback_after: RollbackStateEvidence,
    pub authoritative_pragmas_before: AuthoritativePragmaEvidence,
    pub authoritative_pragmas_after: AuthoritativePragmaEvidence,
    pub connection_usable_after: bool,
    pub post_fault_query: PostFaultQueryEvidence,
    pub staging_cleanup_succeeded: bool,
    pub base_fixture_sha256: String,
    pub database_copy_sha256_before: String,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct SuiteInput {
    pub evidence_class: EvidenceClass,
    pub provenance: Provenance,
    pub runtime_environment: RuntimeEnvironmentEvidence,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub trial_root: Option<PathBuf>,
    pub cache_policy: String,
    pub host_storage_context: HostStorageContext,
    pub base_fixture_preflight: BaseFixturePreflightReceipt,
    pub pairs: Vec<TrialPair>,
    pub failure_atomicity: Vec<FailureAtomicityReceipt>,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct PairAssessment {
    pub pair_index: usize,
    pub rss_pass: bool,
    pub elapsed_pass: bool,
    pub cgroup_peak_pass: bool,
    pub cache_shift_guard_pass: bool,
    pub joint_resource_pass: bool,
    pub transaction_pair_pass: bool,
    pub wal_bytes_pass: bool,
    pub wal_frames_pass: bool,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct Assessment {
    pub schema: String,
    pub evidence_class: EvidenceClass,
    pub evidence_valid: bool,
    pub eligible: bool,
    pub decision_pass: bool,
    pub passing_pairs: usize,
    pub cgroup_passing_pairs: usize,
    pub cache_guard_passing_pairs: usize,
    pub transaction_passing_pairs: usize,
    pub wal_passing_pairs: usize,
    pub median_rss_pass: bool,
    pub median_elapsed_pass: bool,
    pub median_cgroup_peak_pass: bool,
    pub median_cache_shift_guard_pass: bool,
    pub median_transaction_pass: bool,
    pub median_wal_bytes_pass: bool,
    pub median_wal_frames_pass: bool,
    pub pair_assessments: Vec<PairAssessment>,
    pub reasons: Vec<String>,
}

pub fn canonical_workload() -> Workload {
    static CORPUS_SHA256: std::sync::OnceLock<String> = std::sync::OnceLock::new();
    Workload {
        schema: workload::FROZEN_WORKLOAD_SCHEMA.to_string(),
        generator_revision: workload::WORKLOAD_GENERATOR_REVISION.to_string(),
        manifest_sha256: "91c2ea6f081ede4d31c08a03f7365e4b93b5f8f70f1e1a001f1f7d5099405fa8"
            .to_string(),
        corpus_sha256: CORPUS_SHA256
            .get_or_init(|| workload::frozen_corpus_sha256(CANONICAL_DOCUMENTS))
            .clone(),
        documents: CANONICAL_DOCUMENTS,
        symbols: 500_000,
        imports: 225_000,
        calls: 675_000,
        total_rows: CANONICAL_TOTAL_ROWS,
        batch_rows: CANONICAL_BATCH_ROWS,
        max_extractor_output_rows: 18,
        symbols_sha256: "7084c185e49cae300f17e937cbf4947af65564fef6059ab45641f363c45aedcb"
            .to_string(),
        imports_sha256: "543f4aa62adf2e623703154ee8aec3743c7f6fa3740f753e8c02f3ca1851f127"
            .to_string(),
        calls_sha256: "82a2cd66302c6e090bd848cf5ea8e9b673e7029729f77b4e3e5998b7f808763f"
            .to_string(),
        combined_sha256: "c26dd0d5f2b3844113f1030128cbfad1506b81cec2d13b585649c5b4057a3099"
            .to_string(),
    }
}

/// Assess a suite without trusting self-attested labels. Missing canonical
/// fields are structural evidence failures, never zero-valued measurements.
pub fn assess_suite(input: &SuiteInput) -> Assessment {
    let mut reasons = Vec::new();
    let canonical = input.evidence_class == EvidenceClass::Canonical;
    if !canonical {
        reasons.push("diagnostic evidence is never promotion eligible".to_string());
    }

    if canonical {
        validate_provenance(&input.provenance, &mut reasons);
        validate_runtime_environment(&input.runtime_environment, &mut reasons);
        validate_canonical_trial_root(input.trial_root.as_deref(), &mut reasons);
        validate_canonical_plan(&input.pairs, &mut reasons);
        validate_canonical_child_custody(input, &mut reasons);
        if input.cache_policy != "warm_shared_corpus_after_single_base_fixture" {
            reasons.push("canonical warm-cache policy is not frozen".to_string());
        }
        if input.host_storage_context.live_substrate_is_canonical_gate
            || input
                .host_storage_context
                .filesystem_type
                .as_deref()
                .is_none_or(str::is_empty)
            || input.host_storage_context.mount_point.is_none()
            || input.host_storage_context.device.is_none()
        {
            reasons.push(
                "host live-substrate storage context is missing or mis-authorized".to_string(),
            );
        }
        validate_failure_atomicity(
            &input.failure_atomicity,
            &input.provenance.build,
            &input.base_fixture_preflight,
            input.trial_root.as_deref(),
            &mut reasons,
        );
        validate_base_fixture_custody(input, &mut reasons);
    } else if input.pairs.is_empty() {
        reasons.push("diagnostic suite must contain at least one pair".to_string());
    }

    let mut pair_assessments = Vec::with_capacity(input.pairs.len());
    let mut full_rss = Vec::new();
    let mut staged_rss = Vec::new();
    let mut full_elapsed = Vec::new();
    let mut staged_elapsed = Vec::new();
    let mut full_cgroup_peak = Vec::new();
    let mut staged_cgroup_peak = Vec::new();
    let mut full_tx = Vec::new();
    let mut staged_tx = Vec::new();
    let mut full_wal_bytes = Vec::new();
    let mut staged_wal_bytes = Vec::new();
    let mut full_wal_frames = Vec::new();
    let mut staged_wal_frames = Vec::new();

    for pair in &input.pairs {
        validate_pair(pair, canonical, &mut reasons);
        if pair.full_vec.build_identity != input.provenance.build
            || pair.staged_native.build_identity != input.provenance.build
        {
            reasons.push(format!(
                "pair {} child build/executable identity differs from the suite",
                pair.pair_index
            ));
        }
        let full = &pair.full_vec;
        let staged = &pair.staged_native;
        let rss_pass = metric_gate(
            full.measurement.peak_rss_bytes,
            staged.measurement.peak_rss_bytes,
            10_000 - RSS_REDUCTION_BPS,
        );
        let elapsed_pass = metric_gate(
            full.measurement.elapsed_ns,
            staged.measurement.elapsed_ns,
            10_000 + ELAPSED_REGRESSION_BPS,
        );
        let cgroup_peak_pass = metric_gate(
            full.measurement.cgroup_memory_peak_after_bytes,
            staged.measurement.cgroup_memory_peak_after_bytes,
            10_000 + CGROUP_PEAK_REGRESSION_BPS,
        );
        let cache_shift_guard_pass = memory_component_deltas_valid(&full.measurement)
            && memory_component_deltas_valid(&staged.measurement);
        let transaction_pair_pass = metric_gate(
            full.measurement.authoritative_transaction_ns,
            staged.measurement.authoritative_transaction_ns,
            10_000 + TX_PAIR_REGRESSION_BPS,
        );
        let wal_bytes_pass = metric_gate(
            full.database.wal_bytes,
            staged.database.wal_bytes,
            10_000 + WAL_REGRESSION_BPS,
        );
        let wal_frames_pass = metric_gate(
            full.database.wal_frames,
            staged.database.wal_frames,
            10_000 + WAL_REGRESSION_BPS,
        );
        pair_assessments.push(PairAssessment {
            pair_index: pair.pair_index,
            rss_pass,
            elapsed_pass,
            cgroup_peak_pass,
            cache_shift_guard_pass,
            joint_resource_pass: rss_pass && elapsed_pass && cgroup_peak_pass,
            transaction_pair_pass,
            wal_bytes_pass,
            wal_frames_pass,
        });

        push_pair_metric(
            &mut full_rss,
            &mut staged_rss,
            full.measurement.peak_rss_bytes,
            staged.measurement.peak_rss_bytes,
        );
        push_pair_metric(
            &mut full_elapsed,
            &mut staged_elapsed,
            full.measurement.elapsed_ns,
            staged.measurement.elapsed_ns,
        );
        push_pair_metric(
            &mut full_cgroup_peak,
            &mut staged_cgroup_peak,
            full.measurement.cgroup_memory_peak_after_bytes,
            staged.measurement.cgroup_memory_peak_after_bytes,
        );
        push_pair_metric(
            &mut full_tx,
            &mut staged_tx,
            full.measurement.authoritative_transaction_ns,
            staged.measurement.authoritative_transaction_ns,
        );
        push_pair_metric(
            &mut full_wal_bytes,
            &mut staged_wal_bytes,
            full.database.wal_bytes,
            staged.database.wal_bytes,
        );
        push_pair_metric(
            &mut full_wal_frames,
            &mut staged_wal_frames,
            full.database.wal_frames,
            staged.database.wal_frames,
        );
    }

    let passing_pairs = pair_assessments
        .iter()
        .filter(|pair| pair.joint_resource_pass)
        .count();
    let transaction_passing_pairs = pair_assessments
        .iter()
        .filter(|pair| pair.transaction_pair_pass)
        .count();
    let cgroup_passing_pairs = pair_assessments
        .iter()
        .filter(|pair| pair.cgroup_peak_pass)
        .count();
    let cache_guard_passing_pairs = pair_assessments
        .iter()
        .filter(|pair| pair.cache_shift_guard_pass)
        .count();
    let wal_passing_pairs = pair_assessments
        .iter()
        .filter(|pair| pair.wal_bytes_pass && pair.wal_frames_pass)
        .count();
    let expected_metrics = input.pairs.len();
    let median_rss_pass = median_gate(
        &full_rss,
        &staged_rss,
        expected_metrics,
        10_000 - RSS_REDUCTION_BPS,
    );
    let median_elapsed_pass = median_gate(
        &full_elapsed,
        &staged_elapsed,
        expected_metrics,
        10_000 + ELAPSED_REGRESSION_BPS,
    );
    let median_cgroup_peak_pass = median_gate(
        &full_cgroup_peak,
        &staged_cgroup_peak,
        expected_metrics,
        10_000 + CGROUP_PEAK_REGRESSION_BPS,
    );
    let median_cache_shift_guard_pass = cache_guard_passing_pairs == input.pairs.len();
    let median_transaction_pass = median_gate(
        &full_tx,
        &staged_tx,
        expected_metrics,
        10_000 + TX_MEDIAN_REGRESSION_BPS,
    );
    let median_wal_bytes_pass = median_gate(
        &full_wal_bytes,
        &staged_wal_bytes,
        expected_metrics,
        10_000 + WAL_REGRESSION_BPS,
    );
    let median_wal_frames_pass = median_gate(
        &full_wal_frames,
        &staged_wal_frames,
        expected_metrics,
        10_000 + WAL_REGRESSION_BPS,
    );

    let evidence_valid = reasons
        .iter()
        .all(|reason| reason == "diagnostic evidence is never promotion eligible");
    let eligible = canonical && evidence_valid;
    let decision_pass = eligible
        && passing_pairs >= REQUIRED_JOINT_RESOURCE_PAIRS
        && transaction_passing_pairs >= REQUIRED_TX_PAIRS
        && wal_passing_pairs >= REQUIRED_WAL_PAIRS
        && median_rss_pass
        && median_elapsed_pass
        && cgroup_passing_pairs >= REQUIRED_JOINT_RESOURCE_PAIRS
        && median_cgroup_peak_pass
        && median_transaction_pass
        && median_wal_bytes_pass
        && median_wal_frames_pass;

    Assessment {
        schema: SUITE_RECEIPT_SCHEMA.to_string(),
        evidence_class: input.evidence_class,
        evidence_valid,
        eligible,
        decision_pass,
        passing_pairs,
        cgroup_passing_pairs,
        cache_guard_passing_pairs,
        transaction_passing_pairs,
        wal_passing_pairs,
        median_rss_pass,
        median_elapsed_pass,
        median_cgroup_peak_pass,
        median_cache_shift_guard_pass,
        median_transaction_pass,
        median_wal_bytes_pass,
        median_wal_frames_pass,
        pair_assessments,
        reasons,
    }
}

fn validate_provenance(provenance: &Provenance, reasons: &mut Vec<String>) {
    let build = &provenance.build;
    if !build.tree_clean
        || build.profile != "release"
        || build.opt_level != "3"
        || build.debug_assertions
        || build.profile_overrides_present
        || build.build_features != "staged-native"
        || build.encoded_rustflags_sha256
            != "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
        || !is_lower_hex(&build.revision, 40)
        || !is_lower_hex(&build.cargo_lock_sha256, 64)
        || !is_lower_hex(&build.tracked_source_sha256, 64)
        || !build
            .executable_sha256
            .as_deref()
            .is_some_and(|value| is_lower_hex(value, 64))
        || build.target == "UNBOUND"
        || build.target.trim().is_empty()
        || build.rustc_version == "UNBOUND"
        || build.rustc_version.trim().is_empty()
    {
        reasons.push("canonical build identity is dirty, unbound, or non-release".to_string());
    }
    if provenance.runtime_before != *build || provenance.runtime_after != *build {
        reasons.push("canonical source identity or executable identity drifted".to_string());
    }
}

fn validate_runtime_environment(
    environment: &RuntimeEnvironmentEvidence,
    reasons: &mut Vec<String>,
) {
    let expected_siblings = [39_u32, 79_u32].into_iter().collect();
    if !is_bound_text(&environment.kernel_release)
        || !is_bound_text(&environment.cpu_model)
        || !is_bound_text(&environment.cpu_microcode)
        || environment.process_affinity != "39"
        || environment.canonical_cpu != 39
        || environment.excluded_smt_sibling != 79
        || parse_cpu_list(&environment.canonical_cpu_siblings).as_ref() != Some(&expected_siblings)
        || !is_bound_text(&environment.libc)
        || !is_bound_text(&environment.allocator)
        || !is_bound_text(&environment.systemd_version)
        || !is_bound_text(&environment.loadavg)
        || !is_bound_text(&environment.cpu_pressure)
        || !is_bound_text(&environment.memory_pressure)
        || !is_bound_text(&environment.io_pressure)
    {
        reasons.push(
            "canonical kernel/CPU/affinity/libc/systemd/load environment is incomplete".to_string(),
        );
    }
}

fn is_bound_text(value: &str) -> bool {
    let value = value.trim();
    !value.is_empty() && value != "UNBOUND"
}

fn parse_cpu_list(value: &str) -> Option<std::collections::BTreeSet<u32>> {
    let mut cpus = std::collections::BTreeSet::new();
    for part in value.split(',') {
        let part = part.trim();
        if part.is_empty() {
            return None;
        }
        if let Some((start, end)) = part.split_once('-') {
            let start = start.parse::<u32>().ok()?;
            let end = end.parse::<u32>().ok()?;
            if start > end || end.saturating_sub(start) > 4_096 {
                return None;
            }
            cpus.extend(start..=end);
        } else {
            cpus.insert(part.parse::<u32>().ok()?);
        }
    }
    (!cpus.is_empty()).then_some(cpus)
}

fn validate_canonical_trial_root(root: Option<&Path>, reasons: &mut Vec<String>) {
    let Some(root) = root else {
        reasons.push("canonical trial root is missing".to_string());
        return;
    };
    if !root.is_absolute() || !root.starts_with("/home") {
        reasons.push("canonical trial root must be an absolute /home path".to_string());
    }
}

fn validate_canonical_plan(pairs: &[TrialPair], reasons: &mut Vec<String>) {
    if pairs.len() != CANONICAL_PAIRS {
        reasons.push(format!(
            "canonical suite requires exactly {CANONICAL_PAIRS} pairs"
        ));
        return;
    }
    let mut ab = 0;
    let mut ba = 0;
    for (expected_index, pair) in pairs.iter().enumerate() {
        if pair.pair_index != expected_index {
            reasons.push("canonical pair indexes are not contiguous".to_string());
        }
        let expected = if expected_index % 2 == 0 {
            TrialOrder::Ab
        } else {
            TrialOrder::Ba
        };
        if pair.order != expected {
            reasons.push("canonical AB/BA order is not alternating".to_string());
        }
        if pair.observed_order != pair.order.modes() {
            reasons.push("canonical observed child order does not match AB/BA plan".to_string());
        }
        let expected_sequences = [expected_index * 2, expected_index * 2 + 1];
        if pair.observed_execution[0].mode != pair.observed_order[0]
            || pair.observed_execution[1].mode != pair.observed_order[1]
            || pair.observed_execution[0].sequence != expected_sequences[0]
            || pair.observed_execution[1].sequence != expected_sequences[1]
            || pair.observed_execution[0].process_id == 0
            || pair.observed_execution[1].process_id == 0
            || pair.observed_execution[0].process_id == pair.observed_execution[1].process_id
            || pair.observed_execution[0].started_unix_ns
                >= pair.observed_execution[0].finished_unix_ns
            || pair.observed_execution[1].started_unix_ns
                >= pair.observed_execution[1].finished_unix_ns
            || pair.observed_execution[0].finished_unix_ns
                > pair.observed_execution[1].started_unix_ns
        {
            reasons
                .push("canonical observed child PID/time/sequence evidence is invalid".to_string());
        }
        match pair.order {
            TrialOrder::Ab => ab += 1,
            TrialOrder::Ba => ba += 1,
        }
    }
    if ab != 5 || ba != 5 {
        reasons.push("canonical AB/BA first-position balance must be 5/5".to_string());
    }
}

fn validate_canonical_child_custody(input: &SuiteInput, reasons: &mut Vec<String>) {
    let Some(suite_root) = input.trial_root.as_deref() else {
        return;
    };
    let mut executions = Vec::with_capacity(CANONICAL_PAIRS * 2);
    let mut process_ids = std::collections::BTreeSet::new();
    let mut cgroups = std::collections::BTreeSet::new();
    let mut trial_roots = std::collections::BTreeSet::new();
    let mut database_paths = std::collections::BTreeSet::new();
    let mut valid = true;

    for pair in &input.pairs {
        for run in [&pair.full_vec, &pair.staged_native] {
            executions.push(&run.execution);
            valid &= process_ids.insert(run.execution.process_id);
            valid &= run
                .measurement
                .cgroup_path
                .as_ref()
                .is_some_and(|path| cgroups.insert(path.clone()));
            valid &= run.storage.trial_root.starts_with(suite_root)
                && trial_roots.insert(run.storage.trial_root.clone());
            let expected_database = run.storage.trial_root.join("database/state.db");
            valid &= run.authoritative_pragmas_before.database_files.first()
                == Some(&expected_database)
                && database_paths.insert(expected_database);
        }
    }

    executions.sort_by_key(|execution| execution.sequence);
    valid &= executions.len() == CANONICAL_PAIRS * 2;
    for (expected_sequence, execution) in executions.iter().enumerate() {
        valid &= execution.sequence == expected_sequence;
        if expected_sequence > 0 {
            valid &=
                executions[expected_sequence - 1].finished_unix_ns <= execution.started_unix_ns;
        }
    }

    if !valid {
        reasons.push(
            "canonical child PID/cgroup/trial/database identities or global timeline are not unique"
                .to_string(),
        );
    }
}

fn validate_pair(pair: &TrialPair, canonical: bool, reasons: &mut Vec<String>) {
    if pair.observed_order != pair.order.modes() {
        reasons.push(format!(
            "pair {} observed order is invalid",
            pair.pair_index
        ));
    }
    if pair.observed_execution[0] != pair_receipt_execution(pair, pair.observed_order[0])
        || pair.observed_execution[1] != pair_receipt_execution(pair, pair.observed_order[1])
    {
        reasons.push(format!(
            "pair {} observed execution is not bound to child receipts",
            pair.pair_index
        ));
    }
    if pair.full_vec.schema != RUN_RECEIPT_SCHEMA || pair.staged_native.schema != RUN_RECEIPT_SCHEMA
    {
        reasons.push(format!(
            "pair {} has an unknown run schema",
            pair.pair_index
        ));
    }
    if pair.full_vec.mode != Mode::FullVec || pair.staged_native.mode != Mode::StagedNative {
        reasons.push(format!("pair {} mode labels are invalid", pair.pair_index));
    }
    if pair.full_vec.workload != pair.staged_native.workload {
        reasons.push(format!(
            "pair {} workload identities differ",
            pair.pair_index
        ));
    }
    if canonical
        && (pair.full_vec.workload != canonical_workload()
            || pair.staged_native.workload != canonical_workload())
    {
        reasons.push(format!(
            "pair {} does not use the frozen canonical workload",
            pair.pair_index
        ));
    }
    validate_run(&pair.full_vec, canonical, reasons, pair.pair_index);
    validate_run(&pair.staged_native, canonical, reasons, pair.pair_index);
    validate_database_equivalence(pair, reasons);
}

fn pair_receipt_execution(pair: &TrialPair, mode: Mode) -> ChildExecutionEvidence {
    match mode {
        Mode::FullVec => pair.full_vec.execution.clone(),
        Mode::StagedNative => pair.staged_native.execution.clone(),
    }
}

fn validate_run(run: &RunReceipt, canonical: bool, reasons: &mut Vec<String>, pair_index: usize) {
    if run.execution.mode != run.mode
        || run.execution.process_id == 0
        || run.execution.started_unix_ns >= run.execution.finished_unix_ns
    {
        reasons.push(format!(
            "pair {pair_index} {:?} execution identity is invalid",
            run.mode
        ));
    }
    if run.workload.total_rows
        != run
            .workload
            .symbols
            .saturating_add(run.workload.imports)
            .saturating_add(run.workload.calls)
        || run.workload.documents == 0
        || run.workload.batch_rows == 0
        || run.workload.max_extractor_output_rows == 0
    {
        reasons.push(format!("pair {pair_index} has an invalid workload shape"));
    }
    let required_metrics = [
        run.measurement.elapsed_ns,
        run.measurement.peak_rss_bytes,
        run.database.page_count,
        run.database.freelist_count,
        run.database.wal_bytes,
        run.database.database_bytes,
        run.database.shm_bytes,
        run.database.wal_frames,
        run.database.wal_checkpoint_log_frames,
        run.database.wal_checkpointed_frames,
        run.database.wal_checkpoint_busy,
        run.database.page_size,
        run.database.root_rows,
        run.database.null_embeddings,
        run.database.indexed_at_values,
    ];
    if required_metrics.iter().any(Option::is_none)
        || run
            .database
            .schema_sha256
            .as_deref()
            .is_none_or(|v| !is_lower_hex(v, 64))
        || run
            .database
            .semantic_sha256
            .as_deref()
            .is_none_or(|v| !is_lower_hex(v, 64))
        || run
            .database
            .sqlite_compile_options_sha256
            .as_deref()
            .is_none_or(|v| !is_lower_hex(v, 64))
        || run
            .database
            .sqlite_version
            .as_deref()
            .is_none_or(str::is_empty)
        || run.database.journal_mode.as_deref() != Some("wal")
        || run
            .database
            .generation_sha256
            .as_deref()
            .is_none_or(|v| !is_lower_hex(v, 64))
        || run.database.integrity_check.as_deref() != Some("ok")
        || run.database.foreign_key_violations != Some(0)
        || run
            .database
            .schema_meta_version
            .as_deref()
            .is_none_or(str::is_empty)
        || run
            .database
            .schema_meta_sha256
            .as_deref()
            .is_none_or(|v| !is_lower_hex(v, 64))
        || run.database.schema_version.is_none()
        || run.database.user_version.is_none()
        || run.database.synchronous.is_none()
        || run.database.wal_autocheckpoint.is_none()
        || run.database.cache_size.is_none()
        || run.database.cache_spill.is_none()
        || run.database.temp_store.is_none()
        || run.database.mmap_size.is_none()
        || run.database.foreign_keys.is_none()
        || run.database.busy_timeout_ms.is_none()
        || run
            .database
            .locking_mode
            .as_deref()
            .is_none_or(str::is_empty)
    {
        reasons.push(format!(
            "pair {pair_index} {:?} is missing database evidence",
            run.mode
        ));
    }
    if run.database.wal_checkpoint_busy != Some(0)
        || run.database.wal_layout_valid != Some(true)
        || run.database.wal_checkpointed_frames != run.database.wal_checkpoint_log_frames
        || run.database.wal_checkpointed_frames != run.database.wal_frames
        || !wal_physical_layout_valid(&run.database)
        || !run.wal_reset.proven_empty
        || run.wal_reset.busy != 0
        || run.wal_reset.log_frames != 0
        || run.wal_reset.checkpointed_frames != 0
        || run.wal_reset.wal_bytes != 0
    {
        reasons.push(format!(
            "pair {pair_index} {:?} WAL reset/layout/checkpoint custody is invalid",
            run.mode
        ));
    }
    if [
        run.measurement.elapsed_ns,
        run.measurement.peak_rss_bytes,
        run.database.page_count,
        run.database.database_bytes,
        run.database.wal_bytes,
        run.database.wal_frames,
        run.database.wal_checkpoint_log_frames,
        run.database.page_size,
        run.database.root_rows,
    ]
    .into_iter()
    .flatten()
    .any(|value| value == 0)
        || run.database.root_rows != Some(run.workload.total_rows)
        || run.database.null_embeddings != Some(run.workload.symbols)
        || run.database.indexed_at_values != Some(1)
        || run.database.semantic_sha256.as_deref() != Some(run.workload.combined_sha256.as_str())
    {
        reasons.push(format!(
            "pair {pair_index} {:?} database summary is invalid",
            run.mode
        ));
    }
    validate_fixture(run, reasons, pair_index);
    validate_authoritative_pragmas(run, reasons, pair_index);
    if !run.authority.isolated_sqlite_accessed
        || run.authority.live_database_touched
        || run.authority.production_write
        || run.authority.runtime_adoption_authorized
    {
        reasons.push(format!(
            "pair {pair_index} {:?} exceeds evaluation authority",
            run.mode
        ));
    }

    match (run.mode, run.full_vec.as_ref(), run.staged_native.as_ref()) {
        (Mode::FullVec, Some(full), None)
            if full.strategy == "full_vec"
                && full.extraction_and_accumulation_ns > 0
                && full.autocommit_before
                && !full.autocommit_during
                && full.autocommit_after => {}
        (Mode::StagedNative, None, Some(staged))
            if staged.strategy == "native_chunk_staged_v0"
                && staged.batch_rows == run.workload.batch_rows
                && staged.emitted_batches
                    == run
                        .workload
                        .total_rows
                        .div_ceil(run.workload.batch_rows as u64)
                && staged.staging_file_bytes > 0
                && staged.staging_file_path.is_absolute()
                && staged
                    .staging_file_path
                    .starts_with(run.storage.trial_root.join("staging"))
                && Some(staged.staging_file_filesystem_type.as_str())
                    == run.storage.filesystem_type.as_deref()
                && run.storage.database_device == Some(staged.staging_file_device)
                && run.storage.staging_device == Some(staged.staging_file_device)
                && run.storage.trial_device == Some(staged.staging_file_device)
                && Some(&staged.staging_file_mount_point) == run.storage.mount_point.as_ref()
                && staged.max_accumulator_rows <= run.workload.batch_rows
                && staged.max_extractor_output_rows == run.workload.max_extractor_output_rows
                && staged.declared_live_row_bound
                    == run
                        .workload
                        .batch_rows
                        .saturating_add(staged.max_extractor_output_rows.saturating_sub(1))
                && staged.staging_rows == run.workload.total_rows
                && staged.staging_cleanup_succeeded
                && staged.staging_transaction_committed
                && staged.authoritative_transaction_committed
                && staged.staging_parent_was_explicit
                && staged.autocommit_before
                && !staged.autocommit_during
                && staged.autocommit_after => {}
        _ => reasons.push(format!(
            "pair {pair_index} {:?} algorithm proof is invalid",
            run.mode
        )),
    }

    if canonical {
        if run.measurement.authoritative_transaction_ns.is_none()
            || run
                .measurement
                .cgroup_path
                .as_deref()
                .is_none_or(str::is_empty)
            || run.measurement.cgroup_memory_current_before_bytes.is_none()
            || run.measurement.cgroup_memory_current_after_bytes.is_none()
            || run.measurement.cgroup_memory_peak_before_bytes.is_none()
            || run.measurement.cgroup_memory_peak_after_bytes.is_none()
            || run
                .measurement
                .cgroup_memory_max
                .as_deref()
                .is_none_or(str::is_empty)
            || run.measurement.cgroup_process_count.is_none()
            || run.measurement.cgroup_is_shared.is_none()
            || run.measurement.cgroup_isolated_for_trial != Some(true)
            || run.measurement.cgroup_memory_anon_before_bytes.is_none()
            || run.measurement.cgroup_memory_anon_after_bytes.is_none()
            || run.measurement.cgroup_memory_file_before_bytes.is_none()
            || run.measurement.cgroup_memory_file_after_bytes.is_none()
            || run.measurement.cgroup_memory_shmem_before_bytes.is_none()
            || run.measurement.cgroup_memory_shmem_after_bytes.is_none()
            || run.measurement.cgroup_memory_anon_delta_bytes.is_none()
            || run.measurement.cgroup_memory_file_delta_bytes.is_none()
            || run.measurement.cgroup_memory_shmem_delta_bytes.is_none()
            || run.measurement.proc_io_read_bytes_before.is_none()
            || run.measurement.proc_io_read_bytes_after.is_none()
            || run.measurement.proc_io_write_bytes_before.is_none()
            || run.measurement.proc_io_write_bytes_after.is_none()
            || run.measurement.rusage_minor_faults_before.is_none()
            || run.measurement.rusage_minor_faults_after.is_none()
            || run.measurement.rusage_major_faults_before.is_none()
            || run.measurement.rusage_major_faults_after.is_none()
            || run.measurement.getrusage_max_rss_bytes.is_none()
            || run.measurement.vm_hwm_bytes.is_none()
        {
            reasons.push(format!(
                "pair {pair_index} {:?} is missing transaction or cgroup-memory evidence",
                run.mode
            ));
        }
        if [
            run.measurement.authoritative_transaction_ns,
            run.measurement.cgroup_memory_current_after_bytes,
            run.measurement.cgroup_memory_peak_after_bytes,
        ]
        .into_iter()
        .any(|value| value.is_none_or(|value| value == 0))
        {
            reasons.push(format!(
                "pair {pair_index} {:?} has a zero canonical transaction or cgroup metric",
                run.mode
            ));
        }
        if !memory_component_deltas_valid(&run.measurement) {
            reasons.push(format!(
                "pair {pair_index} {:?} cgroup memory.stat deltas are inconsistent",
                run.mode
            ));
        }
        if run.measurement.peak_rss_bytes
            != run
                .measurement
                .vm_hwm_bytes
                .zip(run.measurement.getrusage_max_rss_bytes)
                .map(|(vm_hwm, rusage)| vm_hwm.max(rusage))
        {
            reasons.push(format!(
                "pair {pair_index} {:?} primary RSS is not max(VmHWM,getrusage)",
                run.mode
            ));
        }
        if matches!(
            (
                run.measurement.cgroup_memory_peak_before_bytes,
                run.measurement.cgroup_memory_peak_after_bytes,
            ),
            (Some(before), Some(after)) if after < before
        ) {
            reasons.push(format!(
                "pair {pair_index} {:?} cgroup memory peak regressed monotonically",
                run.mode
            ));
        }
        if matches!(
            (
                run.measurement.cgroup_memory_current_before_bytes,
                run.measurement.cgroup_memory_peak_before_bytes,
                run.measurement.cgroup_memory_current_after_bytes,
                run.measurement.cgroup_memory_peak_after_bytes,
                run.measurement.peak_rss_bytes,
            ),
            (
                Some(current_before),
                Some(peak_before),
                Some(current_after),
                Some(peak_after),
                Some(process_peak),
            ) if peak_before < current_before
                || peak_after < current_after
                || peak_after < process_peak
        ) {
            reasons.push(format!(
                "pair {pair_index} {:?} cgroup peak is below observed current/process memory",
                run.mode
            ));
        }
        for (before, after) in [
            (
                run.measurement.proc_io_read_bytes_before,
                run.measurement.proc_io_read_bytes_after,
            ),
            (
                run.measurement.proc_io_write_bytes_before,
                run.measurement.proc_io_write_bytes_after,
            ),
            (
                run.measurement.rusage_minor_faults_before,
                run.measurement.rusage_minor_faults_after,
            ),
            (
                run.measurement.rusage_major_faults_before,
                run.measurement.rusage_major_faults_after,
            ),
        ] {
            if matches!((before, after), (Some(before), Some(after)) if after < before) {
                reasons.push(format!(
                    "pair {pair_index} {:?} I/O or fault counters are non-monotonic",
                    run.mode
                ));
            }
        }
        if run.measurement.cgroup_process_count == Some(0)
            || run.measurement.cgroup_is_shared
                != run.measurement.cgroup_process_count.map(|count| count > 1)
            || run.measurement.cgroup_is_shared != Some(false)
        {
            reasons.push(format!(
                "pair {pair_index} {:?} cgroup sharing evidence is invalid",
                run.mode
            ));
        }
        validate_storage(&run.storage, run.mode, reasons, pair_index);
    }
}

fn validate_fixture(run: &RunReceipt, reasons: &mut Vec<String>, pair_index: usize) {
    let fixture = &run.fixture;
    if !is_lower_hex(&fixture.base_fixture_sha256, 64)
        || fixture.database_copy_sha256_before != fixture.base_fixture_sha256
        || !fixture.base_sidecars_absent_before
        || fixture.target_rows_before != run.workload.total_rows
        || fixture.target_nonnull_embeddings_before != run.workload.symbols
        || !is_lower_hex(&fixture.target_generation_sha256_before, 64)
        || !is_lower_hex(&fixture.target_generation_sha256_after, 64)
        || fixture.target_generation_sha256_before == fixture.target_generation_sha256_after
        || !is_lower_hex(&fixture.target_raw_sha256_before, 64)
        || !is_lower_hex(&fixture.target_raw_sha256_after, 64)
        || fixture.target_raw_sha256_before == fixture.target_raw_sha256_after
        || run.database.generation_sha256.as_deref()
            != Some(fixture.target_generation_sha256_after.as_str())
        || !is_lower_hex(&fixture.other_root_sha256_before, 64)
        || fixture.other_root_sha256_before != fixture.other_root_sha256_after
        || !is_lower_hex(&fixture.non_codebase_sentinel_sha256_before, 64)
        || fixture.non_codebase_sentinel_sha256_before != fixture.non_codebase_sentinel_sha256_after
    {
        reasons.push(format!(
            "pair {pair_index} {:?} base fixture/sentinel custody is invalid",
            run.mode
        ));
    }
}

fn validate_authoritative_pragmas(run: &RunReceipt, reasons: &mut Vec<String>, pair_index: usize) {
    let before = &run.authoritative_pragmas_before;
    if before != &run.authoritative_pragmas_after
        || !pragma_contract_valid(before)
        || before.database_names != ["main", "temp"]
        || before.database_files.len() != 2
        || before.database_files[0] != run.storage.trial_root.join("database/state.db")
        || !before.database_files[1].as_os_str().is_empty()
    {
        reasons.push(format!(
            "pair {pair_index} {:?} authoritative connection PRAGMAs drifted",
            run.mode
        ));
    }
}

fn pragma_contract_valid(value: &AuthoritativePragmaEvidence) -> bool {
    value.journal_mode == "wal"
        && value.synchronous == 2
        && value.wal_autocheckpoint == 1_000
        && value.foreign_keys == 1
        && value.busy_timeout_ms == 5_000
        && value.locking_mode == "normal"
        && value.autocommit
        && value.database_names == ["main", "temp"]
        && value.database_files.len() == 2
        && value.database_files[0].is_absolute()
        && value.database_files[1].as_os_str().is_empty()
}

fn validate_failure_atomicity(
    receipts: &[FailureAtomicityReceipt],
    expected_build: &BuildIdentity,
    base: &BaseFixturePreflightReceipt,
    suite_root: Option<&Path>,
    reasons: &mut Vec<String>,
) {
    let expected = [
        FailureCase::AfterStagingBatch,
        FailureCase::AfterDeleteSymbols,
        FailureCase::AfterDeleteImports,
        FailureCase::AfterDeleteCalls,
        FailureCase::AfterSymbolRows,
        FailureCase::AfterImportRows,
        FailureCase::AfterCallRows,
        FailureCase::BeforeCommit,
    ];
    let mut observed = std::collections::BTreeSet::new();
    let valid = receipts.len() == expected.len()
        && receipts.iter().all(|receipt| {
            let expected_database = suite_root
                .map(|root| root.join(format!("fault-{:?}/database/state.db", receipt.case)));
            observed.insert(receipt.case)
                && &receipt.build_identity == expected_build
                && receipt.expected_error_observed
                && receipt.expected_error_marker == receipt.case.expected_error_marker()
                && receipt
                    .observed_error
                    .contains(receipt.case.expected_error_marker())
                && is_lower_hex(&receipt.base_fixture_sha256, 64)
                && receipt.database_copy_sha256_before == receipt.base_fixture_sha256
                && receipt.target_generation_sha256_before == base.target_generation_sha256
                && receipt.target_generation_sha256_after == base.target_generation_sha256
                && receipt.other_root_sha256_before == base.other_root_sha256
                && receipt.other_root_sha256_after == base.other_root_sha256
                && receipt.non_codebase_sentinel_sha256_before == base.non_codebase_sentinel_sha256
                && receipt.non_codebase_sentinel_sha256_after == base.non_codebase_sentinel_sha256
                && receipt.target_generation_sha256_before == receipt.target_generation_sha256_after
                && receipt.other_root_sha256_before == receipt.other_root_sha256_after
                && receipt.non_codebase_sentinel_sha256_before
                    == receipt.non_codebase_sentinel_sha256_after
                && receipt.rollback_before == receipt.rollback_after
                && rollback_state_valid(&receipt.rollback_before)
                && rollback_state_matches_base(&receipt.rollback_before, base)
                && receipt.other_root_sha256_before == receipt.rollback_before.other_root_sha256
                && receipt.non_codebase_sentinel_sha256_before
                    == receipt.rollback_before.non_codebase_sentinel_sha256
                && receipt.authoritative_pragmas_before == receipt.authoritative_pragmas_after
                && pragma_contract_valid(&receipt.authoritative_pragmas_before)
                && expected_database.as_ref().is_some_and(|expected| {
                    receipt.authoritative_pragmas_before.database_files.first() == Some(expected)
                })
                && receipt.post_fault_query.query == "codebase_index_pragmas_a1"
                && receipt.post_fault_query.succeeded
                && serialized_sha256(&receipt.authoritative_pragmas_after).as_deref()
                    == Some(receipt.post_fault_query.result_sha256.as_str())
                && receipt.connection_usable_after == receipt.post_fault_query.succeeded
                && receipt.staging_cleanup_succeeded
        })
        && expected.into_iter().all(|case| observed.contains(&case));
    if !valid {
        reasons.push("canonical failure-atomicity matrix is missing or invalid".to_string());
    }
}

fn rollback_state_matches_base(
    state: &RollbackStateEvidence,
    base: &BaseFixturePreflightReceipt,
) -> bool {
    state.target_raw_sha256 == base.target_raw_sha256
        && state.other_root_sha256 == base.other_root_sha256
        && state.non_codebase_sentinel_sha256 == base.non_codebase_sentinel_sha256
        && Some(state.schema_sha256.as_str()) == base.database.schema_sha256.as_deref()
        && Some(state.schema_meta_sha256.as_str()) == base.database.schema_meta_sha256.as_deref()
        && Some(state.schema_version) == base.database.schema_version
        && Some(state.user_version) == base.database.user_version
        && Some(state.page_count) == base.database.page_count
        && Some(state.freelist_count) == base.database.freelist_count
        && Some(state.integrity_check.as_str()) == base.database.integrity_check.as_deref()
        && Some(state.foreign_key_violations) == base.database.foreign_key_violations
}

fn serialized_sha256<T: Serialize>(value: &T) -> Option<String> {
    let bytes = serde_json::to_vec(value).ok()?;
    let mut digest = Sha256::new();
    digest.update(bytes);
    Some(format!("{:x}", digest.finalize()))
}

fn rollback_state_valid(state: &RollbackStateEvidence) -> bool {
    is_lower_hex(&state.target_raw_sha256, 64)
        && is_lower_hex(&state.other_root_sha256, 64)
        && is_lower_hex(&state.non_codebase_sentinel_sha256, 64)
        && is_lower_hex(&state.schema_sha256, 64)
        && is_lower_hex(&state.schema_meta_sha256, 64)
        && state.page_count > 0
        && state.integrity_check == "ok"
        && state.foreign_key_violations == 0
}

fn validate_base_fixture_custody(input: &SuiteInput, reasons: &mut Vec<String>) {
    let base = &input.base_fixture_preflight;
    let base_valid = base.schema == "agent_bridge.codebase_index.a1.base_preflight.v0"
        && base.build_identity == input.provenance.build
        && base.runtime_environment == input.runtime_environment
        && base.workload == canonical_workload()
        && is_lower_hex(&base.base_fixture_sha256, 64)
        && base.database_copy_sha256 == base.base_fixture_sha256
        && base.sidecars_absent
        && base.target_rows == base.workload.total_rows
        && base.target_nonnull_embeddings == base.workload.symbols
        && is_lower_hex(&base.target_generation_sha256, 64)
        && is_lower_hex(&base.target_raw_sha256, 64)
        && is_lower_hex(&base.other_root_sha256, 64)
        && is_lower_hex(&base.non_codebase_sentinel_sha256, 64)
        && base.database.root_rows == Some(base.workload.total_rows)
        && base.database.null_embeddings == Some(0)
        && base.database.semantic_sha256.as_deref() == Some(base.workload.combined_sha256.as_str())
        && base.database.integrity_check.as_deref() == Some("ok")
        && base.database.foreign_key_violations == Some(0);
    let all_perf_bound = input.pairs.iter().flat_map(|pair| {
        [&pair.full_vec, &pair.staged_native]
            .into_iter()
            .map(|run| {
                run.fixture.base_fixture_sha256 == base.base_fixture_sha256
                    && run.fixture.database_copy_sha256_before == base.base_fixture_sha256
                    && run.fixture.target_generation_sha256_before == base.target_generation_sha256
                    && run.fixture.target_raw_sha256_before == base.target_raw_sha256
                    && run.fixture.other_root_sha256_before == base.other_root_sha256
                    && run.fixture.non_codebase_sentinel_sha256_before
                        == base.non_codebase_sentinel_sha256
                    && run.database.schema_sha256 == base.database.schema_sha256
            })
    });
    let all_faults_bound = input.failure_atomicity.iter().map(|receipt| {
        receipt.base_fixture_sha256 == base.base_fixture_sha256
            && receipt.database_copy_sha256_before == base.base_fixture_sha256
            && receipt.rollback_before.target_raw_sha256 == base.target_raw_sha256
            && receipt.rollback_before.other_root_sha256 == base.other_root_sha256
            && receipt.rollback_before.non_codebase_sentinel_sha256
                == base.non_codebase_sentinel_sha256
    });
    if !base_valid || !all_perf_bound.chain(all_faults_bound).all(|bound| bound) {
        reasons.push(
            "canonical base preflight or 20 performance plus 8 fault SHA custody is invalid"
                .to_string(),
        );
    }
}

fn validate_storage(
    storage: &StorageEvidence,
    mode: Mode,
    reasons: &mut Vec<String>,
    pair_index: usize,
) {
    let invalid_type = storage.filesystem_type.as_deref() != Some("ext4");
    if !storage.trial_root.is_absolute()
        || storage.mount_point.is_none()
        || invalid_type
        || storage.trial_device.is_none()
        || storage.database_device != storage.trial_device
        || (mode == Mode::StagedNative && storage.staging_device != storage.trial_device)
    {
        reasons.push(format!(
            "pair {pair_index} {mode:?} is missing same-device ext4 mount custody"
        ));
    }
}

fn validate_database_equivalence(pair: &TrialPair, reasons: &mut Vec<String>) {
    let full = &pair.full_vec.database;
    let staged = &pair.staged_native.database;
    if full.schema_sha256 != staged.schema_sha256
        || full.semantic_sha256 != staged.semantic_sha256
        || full.generation_sha256 != staged.generation_sha256
        || full.page_count != staged.page_count
        || full.freelist_count != staged.freelist_count
        || full.database_bytes != staged.database_bytes
        || full.shm_bytes != staged.shm_bytes
        || full.page_size != staged.page_size
        || full.sqlite_version != staged.sqlite_version
        || full.sqlite_compile_options_sha256 != staged.sqlite_compile_options_sha256
        || full.schema_meta_version != staged.schema_meta_version
        || full.schema_meta_sha256 != staged.schema_meta_sha256
        || full.schema_version != staged.schema_version
        || full.user_version != staged.user_version
        || !pragma_settings_equivalent(
            &pair.full_vec.authoritative_pragmas_before,
            &pair.staged_native.authoritative_pragmas_before,
        )
        || pair.full_vec.fixture.base_fixture_sha256
            != pair.staged_native.fixture.base_fixture_sha256
        || pair.full_vec.fixture.target_generation_sha256_before
            != pair.staged_native.fixture.target_generation_sha256_before
        || pair.full_vec.fixture.other_root_sha256_after
            != pair.staged_native.fixture.other_root_sha256_after
        || pair.full_vec.fixture.non_codebase_sentinel_sha256_after
            != pair
                .staged_native
                .fixture
                .non_codebase_sentinel_sha256_after
    {
        reasons.push(format!(
            "pair {} schema/semantic/page/freelist SQLite evidence differs",
            pair.pair_index
        ));
    }
}

fn pragma_settings_equivalent(
    left: &AuthoritativePragmaEvidence,
    right: &AuthoritativePragmaEvidence,
) -> bool {
    let mut left = left.clone();
    let mut right = right.clone();
    left.database_files.clear();
    right.database_files.clear();
    left == right
}

fn wal_physical_layout_valid(database: &DatabaseEvidence) -> bool {
    let (Some(bytes), Some(frames), Some(page_size)) =
        (database.wal_bytes, database.wal_frames, database.page_size)
    else {
        return false;
    };
    if frames == 0 || page_size == 0 {
        return bytes == 0 && frames == 0;
    }
    let expected = u128::from(frames)
        .checked_mul(u128::from(page_size).saturating_add(24))
        .and_then(|value| value.checked_add(32));
    expected == Some(u128::from(bytes))
}

fn push_pair_metric(
    baselines: &mut Vec<u64>,
    candidates: &mut Vec<u64>,
    baseline: Option<u64>,
    candidate: Option<u64>,
) {
    if let (Some(baseline), Some(candidate)) = (baseline, candidate) {
        if baseline > 0 && candidate > 0 {
            baselines.push(baseline);
            candidates.push(candidate);
        }
    }
}

fn metric_gate(baseline: Option<u64>, candidate: Option<u64>, ratio_bps: u64) -> bool {
    let (Some(baseline), Some(candidate)) = (baseline, candidate) else {
        return false;
    };
    baseline > 0
        && candidate > 0
        && u128::from(candidate) * 10_000 <= u128::from(baseline) * u128::from(ratio_bps)
}

fn median_gate(baselines: &[u64], candidates: &[u64], expected_len: usize, ratio_bps: u64) -> bool {
    if baselines.len() != expected_len || candidates.len() != expected_len || baselines.is_empty() {
        return false;
    }
    let mut paired_log_ratios = baselines
        .iter()
        .zip(candidates)
        .filter(|(baseline, _)| **baseline > 0)
        .map(|(&baseline, &candidate)| (candidate as f64).ln() - (baseline as f64).ln())
        .collect::<Vec<_>>();
    if paired_log_ratios.len() != baselines.len() {
        return false;
    }
    paired_log_ratios.sort_by(f64::total_cmp);
    let middle = paired_log_ratios.len() / 2;
    let median_log_ratio = if paired_log_ratios.len() % 2 == 1 {
        paired_log_ratios[middle]
    } else {
        (paired_log_ratios[middle - 1] + paired_log_ratios[middle]) / 2.0
    };
    median_log_ratio <= (ratio_bps as f64 / 10_000.0).ln() + f64::EPSILON * 8.0
}

fn memory_component_deltas_valid(measurement: &Measurement) -> bool {
    fn exact(before: Option<u64>, after: Option<u64>, delta: Option<i64>) -> bool {
        let (Some(before), Some(after), Some(delta)) = (before, after, delta) else {
            return false;
        };
        i128::from(after) - i128::from(before) == i128::from(delta)
    }
    exact(
        measurement.cgroup_memory_anon_before_bytes,
        measurement.cgroup_memory_anon_after_bytes,
        measurement.cgroup_memory_anon_delta_bytes,
    ) && exact(
        measurement.cgroup_memory_file_before_bytes,
        measurement.cgroup_memory_file_after_bytes,
        measurement.cgroup_memory_file_delta_bytes,
    ) && exact(
        measurement.cgroup_memory_shmem_before_bytes,
        measurement.cgroup_memory_shmem_after_bytes,
        measurement.cgroup_memory_shmem_delta_bytes,
    )
}

fn is_lower_hex(value: &str, expected_len: usize) -> bool {
    value.len() == expected_len
        && value
            .bytes()
            .all(|byte| byte.is_ascii_digit() || (b'a'..=b'f').contains(&byte))
}
