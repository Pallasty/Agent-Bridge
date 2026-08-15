use std::{
    fs::{self, OpenOptions},
    io::{Read, Write},
    path::{Path, PathBuf},
    process::{Command, Stdio},
    time::Instant,
};

use ab_codebase_index_a1::{
    assess_suite,
    provenance::{embedded_build_identity, executable_sha256, runtime_identity},
    quiet::{
        child_interference as compute_child_interference, cpu_process_sample, monotonic_time_ns,
        observe_host_quiet_window,
    },
    snapshot::{
        cgroup_memory_snapshot, database_evidence, fixture_state, peak_rss_bytes, proc_io_snapshot,
        reset_main_wal, rollback_state, rusage_snapshot, seed_base_fixture, sidecars_absent,
        storage_evidence, wal_header_layout_evidence,
    },
    workload::materialize,
    Assessment, AuthoritativePragmaEvidence, AuthorityEvidence, BaseFixturePreflightReceipt,
    CanonicalRawPacket, ChildExecutionEvidence, EvidenceClass, FailureAtomicityReceipt,
    FailureCase, FixtureEvidence, FullVecEvidence, HostStorageContext, Measurement, Mode,
    PostFaultQueryEvidence, Provenance, RunReceipt, RuntimeEnvironmentEvidence,
    StagedNativeEvidence, SuiteInput, TrialOrder, TrialPair, Workload, CANONICAL_BATCH_ROWS,
    CANONICAL_DOCUMENTS, CANONICAL_PAIRS, FAILURE_RECEIPT_SCHEMA, RAW_PACKET_SCHEMA,
    RUN_RECEIPT_SCHEMA, SUITE_RECEIPT_SCHEMA,
};
use clap::{Parser, Subcommand, ValueEnum};
use serde::{Deserialize, Serialize};
use sha2::{Digest, Sha256};
use thiserror::Error;

#[derive(Debug, Parser)]
#[command(about = "Evaluation-only codebase-index A1 assessor")]
struct Cli {
    #[command(subcommand)]
    command: Commands,
}

#[derive(Debug, Subcommand)]
enum Commands {
    /// Run a small, explicitly non-promotable paired suite.
    DiagnosticSuite {
        #[arg(long, default_value_t = 8)]
        documents: u64,
        #[arg(long, default_value_t = 32)]
        batch_rows: usize,
        #[arg(long, default_value_t = 2)]
        pairs: usize,
        #[arg(long, default_value = "/Data/CascadeProjects")]
        trial_root: PathBuf,
        #[arg(long)]
        output: Option<PathBuf>,
    },
    /// Run the frozen #338 canonical plan. Fails before execution on dirty or
    /// source/artifact identity drift.
    CanonicalSuite {
        #[arg(long)]
        trial_root: PathBuf,
        #[arg(long)]
        output: PathBuf,
    },
    /// Internal fresh-process entrypoint used by the suite orchestrator.
    #[command(hide = true)]
    Run {
        #[arg(long, value_enum)]
        mode: CliMode,
        #[arg(long)]
        source_root: PathBuf,
        #[arg(long)]
        trial_dir: PathBuf,
        #[arg(long)]
        workload: PathBuf,
        #[arg(long)]
        base_fixture_sha256: String,
        #[arg(long)]
        base_fixture: PathBuf,
        #[arg(long)]
        expected_cgroup_unit: Option<String>,
        #[arg(long)]
        base_preflight: PathBuf,
        #[arg(long)]
        sequence: usize,
    },
    #[command(hide = true)]
    BasePreflight {
        #[arg(long)]
        source_root: PathBuf,
        #[arg(long)]
        database: PathBuf,
        #[arg(long)]
        workload: PathBuf,
        #[arg(long)]
        base_fixture_sha256: String,
    },
    #[command(hide = true)]
    FaultRun {
        #[arg(long, value_enum)]
        case: CliFailureCase,
        #[arg(long)]
        source_root: PathBuf,
        #[arg(long)]
        trial_dir: PathBuf,
        #[arg(long)]
        workload: PathBuf,
        #[arg(long)]
        base_fixture_sha256: String,
        #[arg(long)]
        base_fixture: PathBuf,
        #[arg(long)]
        expected_cgroup_unit: String,
        #[arg(long)]
        base_preflight: PathBuf,
        #[arg(long)]
        sequence: usize,
    },
}

#[derive(Debug, Clone, Copy, ValueEnum)]
enum CliMode {
    FullVec,
    StagedNative,
}

#[derive(Debug, Clone, Copy, ValueEnum)]
enum CliFailureCase {
    AfterStagingBatch,
    AfterDeleteSymbols,
    AfterDeleteImports,
    AfterDeleteCalls,
    AfterSymbolRows,
    AfterImportRows,
    AfterCallRows,
    BeforeCommit,
}

impl From<CliFailureCase> for FailureCase {
    fn from(value: CliFailureCase) -> Self {
        match value {
            CliFailureCase::AfterStagingBatch => Self::AfterStagingBatch,
            CliFailureCase::AfterDeleteSymbols => Self::AfterDeleteSymbols,
            CliFailureCase::AfterDeleteImports => Self::AfterDeleteImports,
            CliFailureCase::AfterDeleteCalls => Self::AfterDeleteCalls,
            CliFailureCase::AfterSymbolRows => Self::AfterSymbolRows,
            CliFailureCase::AfterImportRows => Self::AfterImportRows,
            CliFailureCase::AfterCallRows => Self::AfterCallRows,
            CliFailureCase::BeforeCommit => Self::BeforeCommit,
        }
    }
}

impl From<CliMode> for Mode {
    fn from(value: CliMode) -> Self {
        match value {
            CliMode::FullVec => Self::FullVec,
            CliMode::StagedNative => Self::StagedNative,
        }
    }
}

#[derive(Debug, Serialize, Deserialize)]
struct SuiteReceipt {
    schema: String,
    input: SuiteInput,
    assessment: Assessment,
    suite_cleanup_succeeded: bool,
    suite_artifacts_retained: bool,
    raw_packet: Option<RawPacketCustody>,
}

#[derive(Debug, Serialize, Deserialize)]
struct RawPacketCustody {
    path: PathBuf,
    sha256: String,
    retained: bool,
    synced_before_suite_cleanup: bool,
}

#[derive(Debug, Error)]
enum AppError {
    #[error("the real runner requires --features staged-native")]
    FeatureMissing,
    #[error("documents, batch_rows, and pairs must all be positive")]
    EmptyConfiguration,
    #[error("canonical preflight rejected build/runtime identity: {0}")]
    CanonicalPreflight(String),
    #[error("trial root must already exist and be a directory: {0}")]
    TrialRoot(String),
    #[error("child {mode:?} failed: {stderr}")]
    ChildFailure { mode: Mode, stderr: String },
    #[error("child {mode:?} exceeded the frozen timeout")]
    ChildTimeout { mode: Mode },
    #[error("child {mode:?} emitted invalid JSON: {source}")]
    ChildJson {
        mode: Mode,
        source: serde_json::Error,
    },
    #[error("child receipt contract mismatch: {0}")]
    ChildContract(String),
    #[error("index result contract mismatch: {0}")]
    IndexContract(String),
    #[error("base fixture contract failed: {0}")]
    BaseFixture(String),
    #[error("canonical evidence is invalid")]
    EvidenceInvalid,
    #[error("canonical candidate failed frozen decision thresholds")]
    DecisionFailed,
    #[error("refusing to overwrite existing output: {0}")]
    OutputExists(String),
    #[error("suite failed ({operation}) and explicit suite cleanup also failed: {cleanup}")]
    SuiteCleanup {
        operation: String,
        cleanup: std::io::Error,
    },
    #[error(transparent)]
    Io(#[from] std::io::Error),
    #[error(transparent)]
    Json(#[from] serde_json::Error),
    #[error(transparent)]
    Workload(#[from] ab_codebase_index_a1::workload::WorkloadError),
    #[error(transparent)]
    Snapshot(#[from] ab_codebase_index_a1::snapshot::SnapshotError),
    #[error("store operation failed: {0}")]
    Store(String),
}

#[tokio::main]
async fn main() -> std::process::ExitCode {
    match async_main().await {
        Ok(()) => std::process::ExitCode::SUCCESS,
        Err(error) => {
            eprintln!("Error: {error}");
            std::process::ExitCode::from(error.exit_code())
        }
    }
}

async fn async_main() -> Result<(), AppError> {
    match Cli::parse().command {
        Commands::DiagnosticSuite {
            documents,
            batch_rows,
            pairs,
            trial_root,
            output,
        } => {
            let receipt = run_suite(
                EvidenceClass::Diagnostic,
                documents,
                batch_rows,
                pairs,
                &trial_root,
                None,
            )
            .await?;
            emit_json(&receipt, output.as_deref())?;
        }
        Commands::CanonicalSuite { trial_root, output } => {
            let receipt = run_suite(
                EvidenceClass::Canonical,
                CANONICAL_DOCUMENTS,
                CANONICAL_BATCH_ROWS,
                CANONICAL_PAIRS,
                &trial_root,
                Some(&output),
            )
            .await?;
            emit_json(&receipt, Some(&output))?;
            if !receipt.assessment.evidence_valid {
                return Err(AppError::EvidenceInvalid);
            }
            if !receipt.assessment.decision_pass {
                return Err(AppError::DecisionFailed);
            }
        }
        Commands::Run {
            mode,
            source_root,
            trial_dir,
            workload,
            base_fixture_sha256,
            base_fixture,
            expected_cgroup_unit,
            base_preflight,
            sequence,
        } => {
            let expected: Workload = serde_json::from_slice(&fs::read(workload)?)?;
            let receipt = run_one(
                mode.into(),
                &source_root,
                &trial_dir,
                expected,
                base_fixture_sha256,
                &base_fixture,
                expected_cgroup_unit.as_deref(),
                &base_preflight,
                sequence,
            )
            .await?;
            serde_json::to_writer(std::io::stdout().lock(), &receipt)?;
        }
        Commands::BasePreflight {
            source_root,
            database,
            workload,
            base_fixture_sha256,
        } => {
            let expected: Workload = serde_json::from_slice(&fs::read(workload)?)?;
            let receipt =
                base_fixture_preflight(&source_root, &database, expected, base_fixture_sha256)?;
            serde_json::to_writer(std::io::stdout().lock(), &receipt)?;
        }
        Commands::FaultRun {
            case,
            source_root,
            trial_dir,
            workload,
            base_fixture_sha256,
            base_fixture,
            expected_cgroup_unit,
            base_preflight,
            sequence,
        } => {
            let expected: Workload = serde_json::from_slice(&fs::read(workload)?)?;
            let receipt = run_fault_one(
                case.into(),
                &source_root,
                &trial_dir,
                expected,
                base_fixture_sha256,
                &base_fixture,
                &expected_cgroup_unit,
                &base_preflight,
                sequence,
            )
            .await?;
            serde_json::to_writer(std::io::stdout().lock(), &receipt)?;
        }
    }
    Ok(())
}

impl AppError {
    fn exit_code(&self) -> u8 {
        match self {
            Self::EvidenceInvalid => 2,
            Self::DecisionFailed => 3,
            _ => 1,
        }
    }
}

async fn run_suite(
    evidence_class: EvidenceClass,
    documents: u64,
    batch_rows: usize,
    pairs: usize,
    trial_root: &Path,
    canonical_output: Option<&Path>,
) -> Result<SuiteReceipt, AppError> {
    if !cfg!(feature = "staged-native") {
        return Err(AppError::FeatureMissing);
    }
    if documents == 0 || batch_rows == 0 || pairs == 0 {
        return Err(AppError::EmptyConfiguration);
    }
    if !trial_root.is_dir() {
        return Err(AppError::TrialRoot(trial_root.display().to_string()));
    }
    let canonical_output_paths = if evidence_class == EvidenceClass::Canonical {
        let output = canonical_output.ok_or_else(|| {
            AppError::CanonicalPreflight("canonical output path is missing".to_string())
        })?;
        Some(canonical_output_preflight(output, trial_root)?)
    } else {
        None
    };

    let executable_sha_before = executable_sha256()?;
    let build = embedded_build_identity(Some(executable_sha_before.clone()));
    let runtime_before = runtime_identity(executable_sha_before.clone());
    if evidence_class == EvidenceClass::Canonical {
        canonical_preflight(&build, &runtime_before, trial_root)?;
    }

    let canonical_trial_root = trial_root.canonicalize()?;
    let suite_dir = tempfile::Builder::new()
        .prefix("ab-codebase-index-a1-suite-")
        .tempdir_in(&canonical_trial_root)?;
    let suite_path = suite_dir.path().to_path_buf();
    let execution_result = async {
        let corpus_path = suite_path.join("corpus");
        fs::create_dir(&corpus_path)?;
        let workload = materialize(&corpus_path, documents, batch_rows)?;
        let workload_path = suite_path.join("workload.json");
        fs::write(&workload_path, serde_json::to_vec(&workload)?)?;
        let (base_fixture_path, base_fixture_sha256) =
            build_base_fixture(&suite_path, &corpus_path, &workload).await?;

        let current_exe = std::env::current_exe()?;
        let base_preflight = run_base_preflight_child(
            &current_exe,
            &corpus_path,
            &base_fixture_path,
            &workload_path,
            &base_fixture_sha256,
            evidence_class,
        )?;
        if !sidecars_absent(&base_fixture_path)?
            || ab_codebase_index_a1::provenance::sha256_file(&base_fixture_path)?
                != base_fixture_sha256
        {
            return Err(AppError::BaseFixture(
                "base changed or retained sidecars after preflight child".to_string(),
            ));
        }
        let base_preflight_path = suite_path.join("base-preflight.json");
        emit_json(&base_preflight, Some(&base_preflight_path))?;
        let host_quiet_window = if evidence_class == EvidenceClass::Canonical {
            let evidence = observe_host_quiet_window(
                39,
                std::time::Duration::from_secs(30),
                std::time::Duration::from_secs(1),
            )
            .map_err(|error| {
                AppError::CanonicalPreflight(format!(
                    "host quiet-window evidence could not be collected: {error}"
                ))
            })?;
            if !evidence.passed {
                return Err(AppError::CanonicalPreflight(format!(
                    "host quiet-window gate rejected competing activity: {evidence:?}"
                )));
            }
            Some(evidence)
        } else {
            None
        };
        let mut raw = Vec::with_capacity(pairs);
        for pair_index in 0..pairs {
            let order = if pair_index % 2 == 0 {
                TrialOrder::Ab
            } else {
                TrialOrder::Ba
            };
            let mut full_vec = None;
            let mut staged_native = None;
            for (position, mode) in order.modes().into_iter().enumerate() {
                let trial_dir = suite_path.join(format!(
                    "pair-{pair_index:02}-position-{position}-{}",
                    match mode {
                        Mode::FullVec => "full-vec",
                        Mode::StagedNative => "staged-native",
                    }
                ));
                fs::create_dir(&trial_dir)?;
                let database_dir = trial_dir.join("database");
                fs::create_dir(&database_dir)?;
                let receipt = run_child(
                    &current_exe,
                    mode,
                    &corpus_path,
                    &trial_dir,
                    &workload_path,
                    &base_fixture_path,
                    &base_fixture_sha256,
                    evidence_class,
                    pair_index,
                    position,
                    &base_preflight_path,
                    pair_index * 2 + position,
                )?;
                validate_child(
                    &receipt,
                    mode,
                    &workload,
                    &build,
                    &trial_dir,
                    pair_index * 2 + position,
                )?;
                match mode {
                    Mode::FullVec => full_vec = Some(receipt),
                    Mode::StagedNative => staged_native = Some(receipt),
                }
            }
            let full_vec = full_vec.ok_or_else(|| {
                AppError::ChildContract(format!("pair {pair_index} lacks FullVec"))
            })?;
            let staged_native = staged_native.ok_or_else(|| {
                AppError::ChildContract(format!("pair {pair_index} lacks staged-native"))
            })?;
            let observed_execution = match order {
                TrialOrder::Ab => [full_vec.execution.clone(), staged_native.execution.clone()],
                TrialOrder::Ba => [staged_native.execution.clone(), full_vec.execution.clone()],
            };
            raw.push(TrialPair {
                pair_index,
                order,
                observed_order: order.modes(),
                observed_execution,
                full_vec,
                staged_native,
            });
        }

        let mut failure_atomicity = Vec::new();
        if evidence_class == EvidenceClass::Canonical {
            for (fault_index, case) in [
                FailureCase::AfterStagingBatch,
                FailureCase::AfterDeleteSymbols,
                FailureCase::AfterDeleteImports,
                FailureCase::AfterDeleteCalls,
                FailureCase::AfterSymbolRows,
                FailureCase::AfterImportRows,
                FailureCase::AfterCallRows,
                FailureCase::BeforeCommit,
            ]
            .into_iter()
            .enumerate()
            {
                let trial_dir = suite_path.join(format!("fault-{case:?}"));
                let database_dir = trial_dir.join("database");
                fs::create_dir_all(&database_dir)?;
                failure_atomicity.push(run_fault_child(
                    &current_exe,
                    case,
                    &corpus_path,
                    &trial_dir,
                    &workload_path,
                    &base_fixture_path,
                    &base_fixture_sha256,
                    &base_preflight_path,
                    CANONICAL_PAIRS * 2 + fault_index,
                )?);
            }
        }

        let executable_sha_after = executable_sha256()?;
        let runtime_after = runtime_identity(executable_sha_after);
        let runtime_environment = base_preflight.runtime_environment.clone();
        let provenance = Provenance {
            build,
            runtime_before,
            runtime_after,
        };
        let input = SuiteInput {
            evidence_class,
            provenance,
            runtime_environment,
            host_quiet_window,
            trial_root: Some(suite_path),
            cache_policy: "warm_shared_corpus_after_single_base_fixture".to_string(),
            host_storage_context: host_storage_context(),
            base_fixture_preflight: base_preflight,
            pairs: raw,
            failure_atomicity,
        };
        let assessment = assess_suite(&input);
        let raw_packet = if evidence_class == EvidenceClass::Canonical {
            let output_paths = canonical_output_paths.as_ref().ok_or_else(|| {
                AppError::CanonicalPreflight("canonical output custody path is missing".to_string())
            })?;
            if canonical_output != Some(output_paths.terminal.as_path()) {
                return Err(AppError::CanonicalPreflight(
                    "canonical output custody changed after preflight".to_string(),
                ));
            }
            let path = output_paths.raw.clone();
            let packet = CanonicalRawPacket {
                schema: RAW_PACKET_SCHEMA.to_string(),
                input: input.clone(),
                assessment: assessment.clone(),
            };
            emit_json(&packet, Some(&path))?;
            let sha256 = ab_codebase_index_a1::provenance::sha256_file(&path)?;
            Some(RawPacketCustody {
                path,
                sha256,
                retained: true,
                synced_before_suite_cleanup: true,
            })
        } else {
            None
        };
        Ok::<SuiteReceipt, AppError>(SuiteReceipt {
            schema: SUITE_RECEIPT_SCHEMA.to_string(),
            input,
            assessment,
            suite_cleanup_succeeded: false,
            suite_artifacts_retained: true,
            raw_packet,
        })
    }
    .await;
    match (execution_result, suite_dir.close()) {
        (Ok(mut receipt), Ok(())) => {
            receipt.suite_cleanup_succeeded = true;
            receipt.suite_artifacts_retained = false;
            Ok(receipt)
        }
        (Err(error), Ok(())) => Err(error),
        (Ok(_), Err(cleanup)) => Err(AppError::Io(cleanup)),
        (Err(error), Err(cleanup)) => Err(AppError::SuiteCleanup {
            operation: error.to_string(),
            cleanup,
        }),
    }
}

#[derive(Debug)]
struct CanonicalOutputPaths {
    terminal: PathBuf,
    raw: PathBuf,
}

fn canonical_output_preflight(
    output: &Path,
    trial_root: &Path,
) -> Result<CanonicalOutputPaths, AppError> {
    if !output.is_absolute() {
        return Err(AppError::CanonicalPreflight(
            "canonical output must be an absolute path".to_string(),
        ));
    }
    let file_name = output.file_name().ok_or_else(|| {
        AppError::CanonicalPreflight("canonical output must name a file".to_string())
    })?;
    let parent = output.parent().ok_or_else(|| {
        AppError::CanonicalPreflight("canonical output parent is missing".to_string())
    })?;
    if !parent.is_dir() {
        return Err(AppError::CanonicalPreflight(
            "canonical output parent must already exist".to_string(),
        ));
    }
    let parent = parent.canonicalize()?;
    let terminal = parent.join(file_name);
    if terminal != output {
        return Err(AppError::CanonicalPreflight(
            "canonical output parent must already be canonical (no symlink or '..')".to_string(),
        ));
    }
    let canonical_trial_root = trial_root.canonicalize()?;
    let repository = ab_codebase_index_a1::provenance::repository_dir().canonicalize()?;
    if !terminal.starts_with("/home") {
        return Err(AppError::CanonicalPreflight(
            "canonical output must be retained on an absolute /home path".to_string(),
        ));
    }
    if terminal.starts_with(&repository) || terminal.starts_with(&canonical_trial_root) {
        return Err(AppError::CanonicalPreflight(
            "canonical output must be outside both the source tree and trial root".to_string(),
        ));
    }
    let storage = storage_evidence(&parent, &terminal, &parent, Mode::FullVec);
    if storage.mount_point.is_none() || storage.filesystem_type.as_deref() != Some("ext4") {
        return Err(AppError::CanonicalPreflight(
            "canonical output parent is not on the frozen persistent ext4 filesystem class"
                .to_string(),
        ));
    }
    let mut raw = terminal.as_os_str().to_os_string();
    raw.push(".raw.json");
    let raw = PathBuf::from(raw);
    for path in [&terminal, &raw] {
        match path.try_exists() {
            Ok(false) => {}
            Ok(true) => return Err(AppError::OutputExists(path.display().to_string())),
            Err(error) => return Err(AppError::Io(error)),
        }
    }
    Ok(CanonicalOutputPaths { terminal, raw })
}

#[cfg(feature = "staged-native")]
async fn build_base_fixture(
    suite_path: &Path,
    corpus_path: &Path,
    workload: &Workload,
) -> Result<(PathBuf, String), AppError> {
    let base_dir = suite_path.join("base-fixture");
    fs::create_dir(&base_dir)?;
    let database_path = base_dir.join("state.db");
    let store = ab_store::SqliteStore::open(&database_path)
        .await
        .map_err(|error| AppError::Store(error.to_string()))?;
    let languages = vec![
        "rust".to_string(),
        "python".to_string(),
        "typescript".to_string(),
        "go".to_string(),
    ];
    let outcome = store
        .codebase_index_full_vec_a1(corpus_path.to_string_lossy().as_ref(), &languages)
        .await
        .map_err(|error| AppError::Store(error.to_string()))?;
    validate_stats(&outcome.stats, workload, corpus_path)?;
    drop(store);
    std::thread::sleep(std::time::Duration::from_millis(50));
    seed_base_fixture(&database_path, corpus_path)?;
    for _ in 0..20 {
        if sidecars_absent(&database_path)? {
            break;
        }
        std::thread::sleep(std::time::Duration::from_millis(25));
    }
    if !sidecars_absent(&database_path)? {
        return Err(AppError::BaseFixture(
            "closed/checkpointed base retained WAL or SHM sidecars".to_string(),
        ));
    }
    let sha256 = ab_codebase_index_a1::provenance::sha256_file(&database_path)?;
    Ok((database_path, sha256))
}

fn base_fixture_preflight(
    source_root: &Path,
    database_path: &Path,
    workload: Workload,
    base_fixture_sha256: String,
) -> Result<BaseFixturePreflightReceipt, AppError> {
    let source_root = source_root.canonicalize()?;
    let database_path = database_path.canonicalize()?;
    let database_copy_sha256 = ab_codebase_index_a1::provenance::sha256_file(&database_path)?;
    let sidecars_absent = sidecars_absent(&database_path)?;
    if database_copy_sha256 != base_fixture_sha256
        || ab_codebase_index_a1::workload::actual_corpus_sha256(&source_root, workload.documents)?
            != workload.corpus_sha256
    {
        return Err(AppError::BaseFixture(
            "base SHA or actual generated corpus path/content digest drifted".to_string(),
        ));
    }
    let fixture = fixture_state(&database_path, &source_root)?;
    let database = database_evidence(&database_path, &source_root)?;
    let rollback_state = rollback_state(&database_path, &source_root)?;
    if fixture.target_rows != workload.total_rows
        || fixture.target_nonnull_embeddings != workload.symbols
        || database.root_rows != Some(workload.total_rows)
        || database.null_embeddings != Some(0)
        || database.semantic_sha256.as_deref() != Some(workload.combined_sha256.as_str())
        || database.integrity_check.as_deref() != Some("ok")
        || database.foreign_key_violations != Some(0)
    {
        return Err(AppError::BaseFixture(
            "base preflight row/semantic/integrity contract failed".to_string(),
        ));
    }
    Ok(BaseFixturePreflightReceipt {
        schema: "agent_bridge.codebase_index.a1.base_preflight.v0".to_string(),
        build_identity: embedded_build_identity(Some(executable_sha256()?)),
        runtime_environment: runtime_environment(),
        workload,
        base_fixture_sha256,
        database_copy_sha256,
        sidecars_absent,
        target_rows: fixture.target_rows,
        target_nonnull_embeddings: fixture.target_nonnull_embeddings,
        target_generation_sha256: fixture.target_generation_sha256,
        target_raw_sha256: fixture.target_raw_sha256,
        other_root_sha256: fixture.other_root_sha256,
        non_codebase_sentinel_sha256: fixture.non_codebase_sentinel_sha256,
        database,
        rollback_state,
    })
}

fn run_base_preflight_child(
    executable: &Path,
    source_root: &Path,
    database: &Path,
    workload: &Path,
    base_fixture_sha256: &str,
    evidence_class: EvidenceClass,
) -> Result<BaseFixturePreflightReceipt, AppError> {
    let unit = format!("ab-codebase-index-a1-{}-base-preflight", std::process::id());
    let mut command = if evidence_class == EvidenceClass::Canonical {
        transient_service_command(&unit, executable)
    } else {
        Command::new(executable)
    };
    command
        .arg("base-preflight")
        .arg("--source-root")
        .arg(source_root)
        .arg("--database")
        .arg(database)
        .arg("--workload")
        .arg(workload)
        .arg("--base-fixture-sha256")
        .arg(base_fixture_sha256);
    let unit_ref = (evidence_class == EvidenceClass::Canonical).then_some(unit.as_str());
    let output = output_with_timeout(command, std::time::Duration::from_secs(1_800), unit_ref)
        .map_err(|error| timed_child_error(error, Mode::FullVec))?;
    if !output.success {
        return Err(AppError::ChildFailure {
            mode: Mode::FullVec,
            stderr: String::from_utf8_lossy(&output.stderr).trim().to_string(),
        });
    }
    serde_json::from_slice(&output.stdout).map_err(|source| AppError::ChildJson {
        mode: Mode::FullVec,
        source,
    })
}

fn current_process_affinity() -> String {
    fs::read_to_string("/proc/self/status")
        .ok()
        .and_then(|contents| {
            contents
                .lines()
                .find_map(|line| line.strip_prefix("Cpus_allowed_list:").map(str::trim))
                .map(str::to_string)
        })
        .unwrap_or_else(|| "UNBOUND".to_string())
}

fn allocator_environment() -> String {
    let values = [
        "MALLOC_CONF",
        "LD_PRELOAD",
        "GLIBC_TUNABLES",
        "MALLOC_ARENA_MAX",
    ]
    .map(|key| (key, std::env::var(key).ok()));
    serde_json::to_string(&values).unwrap_or_else(|_| "UNBOUND".to_string())
}

fn runtime_environment() -> RuntimeEnvironmentEvidence {
    fn read(path: &str) -> String {
        fs::read_to_string(path)
            .map(|value| value.trim().to_string())
            .unwrap_or_else(|_| "UNBOUND".to_string())
    }
    fn cpuinfo_value(key: &str) -> String {
        fs::read_to_string("/proc/cpuinfo")
            .ok()
            .and_then(|contents| {
                contents.lines().find_map(|line| {
                    line.split_once(':')
                        .filter(|(name, _)| name.trim() == key)
                        .map(|(_, value)| value.trim().to_string())
                })
            })
            .unwrap_or_else(|| "UNBOUND".to_string())
    }
    fn command_first_line(program: &str, args: &[&str]) -> String {
        Command::new(program)
            .args(args)
            .output()
            .ok()
            .filter(|output| output.status.success())
            .and_then(|output| String::from_utf8(output.stdout).ok())
            .and_then(|output| output.lines().next().map(str::to_string))
            .unwrap_or_else(|| "UNBOUND".to_string())
    }
    RuntimeEnvironmentEvidence {
        kernel_release: read("/proc/sys/kernel/osrelease"),
        cpu_model: cpuinfo_value("model name"),
        cpu_microcode: cpuinfo_value("microcode"),
        process_affinity: current_process_affinity(),
        canonical_cpu: 39,
        excluded_smt_sibling: 79,
        canonical_cpu_siblings: read("/sys/devices/system/cpu/cpu39/topology/thread_siblings_list"),
        libc: command_first_line("getconf", &["GNU_LIBC_VERSION"]),
        allocator: allocator_environment(),
        systemd_version: command_first_line("systemctl", &["--version"]),
        loadavg: read("/proc/loadavg"),
        cpu_pressure: read("/proc/pressure/cpu"),
        memory_pressure: read("/proc/pressure/memory"),
        io_pressure: read("/proc/pressure/io"),
    }
}

#[cfg(not(feature = "staged-native"))]
async fn build_base_fixture(
    _suite_path: &Path,
    _corpus_path: &Path,
    _workload: &Workload,
) -> Result<(PathBuf, String), AppError> {
    Err(AppError::FeatureMissing)
}

fn host_storage_context() -> HostStorageContext {
    let configured = ab_store::default_db_path();
    let resolved = configured.canonicalize().ok();
    let target = resolved.as_deref().unwrap_or(&configured);
    let parent = target.parent().unwrap_or_else(|| Path::new("/"));
    let probe = storage_evidence(parent, target, parent, Mode::FullVec);
    HostStorageContext {
        configured_default_db_path: configured,
        resolved_default_db_path: resolved,
        mount_point: probe.mount_point,
        filesystem_type: probe.filesystem_type,
        device: probe.database_device.or(probe.trial_device),
        live_substrate_is_canonical_gate: false,
    }
}

fn canonical_preflight(
    build: &ab_codebase_index_a1::BuildIdentity,
    runtime: &ab_codebase_index_a1::BuildIdentity,
    trial_root: &Path,
) -> Result<(), AppError> {
    if build != runtime {
        return Err(AppError::CanonicalPreflight(
            "build and runtime source/executable identities differ".to_string(),
        ));
    }
    if !build.tree_clean
        || build.profile != "release"
        || build.opt_level != "3"
        || build.debug_assertions
        || build.profile_overrides_present
        || build.build_features != "staged-native"
        || build.target == "UNBOUND"
        || build.rustc_version == "UNBOUND"
        || build.encoded_rustflags_sha256
            != "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
    {
        return Err(AppError::CanonicalPreflight(
            "build is dirty, non-release, overridden, or lacks staged-native".to_string(),
        ));
    }
    let canonical_root = trial_root.canonicalize()?;
    if !canonical_root.starts_with("/home") {
        return Err(AppError::CanonicalPreflight(
            "trial root must be an isolated absolute /home path".to_string(),
        ));
    }
    let probe = storage_evidence(
        &canonical_root,
        &canonical_root.join("not-created.db"),
        &canonical_root,
        Mode::FullVec,
    );
    if probe.mount_point.is_none() || probe.filesystem_type.as_deref() != Some("ext4") {
        return Err(AppError::CanonicalPreflight(
            "trial root is not on the frozen ext4 filesystem class".to_string(),
        ));
    }
    Ok(())
}

// The child boundary intentionally spells out every custody identity rather
// than hiding them in a mutable options bag.
#[allow(clippy::too_many_arguments)]
fn run_child(
    executable: &Path,
    mode: Mode,
    source_root: &Path,
    trial_dir: &Path,
    workload_path: &Path,
    base_fixture_path: &Path,
    base_fixture_sha256: &str,
    evidence_class: EvidenceClass,
    pair_index: usize,
    position: usize,
    base_preflight: &Path,
    sequence: usize,
) -> Result<RunReceipt, AppError> {
    let mode_arg = match mode {
        Mode::FullVec => "full-vec",
        Mode::StagedNative => "staged-native",
    };
    let unit = format!(
        "ab-codebase-index-a1-{}-{pair_index}-{position}-{}",
        std::process::id(),
        match mode {
            Mode::FullVec => "full",
            Mode::StagedNative => "staged",
        }
    );
    let mut command = if evidence_class == EvidenceClass::Canonical {
        transient_service_command(&unit, executable)
    } else {
        Command::new(executable)
    };
    command
        .arg("run")
        .arg("--mode")
        .arg(mode_arg)
        .arg("--source-root")
        .arg(source_root)
        .arg("--trial-dir")
        .arg(trial_dir)
        .arg("--workload")
        .arg(workload_path)
        .arg("--base-fixture")
        .arg(base_fixture_path)
        .arg("--base-fixture-sha256")
        .arg(base_fixture_sha256)
        .arg("--base-preflight")
        .arg(base_preflight)
        .arg("--sequence")
        .arg(sequence.to_string());
    if evidence_class == EvidenceClass::Canonical {
        command.arg("--expected-cgroup-unit").arg(&unit);
    }
    let unit_ref = (evidence_class == EvidenceClass::Canonical).then_some(unit.as_str());
    let output = output_with_timeout(command, std::time::Duration::from_secs(1_800), unit_ref)
        .map_err(|error| timed_child_error(error, mode))?;
    if !output.success {
        return Err(AppError::ChildFailure {
            mode,
            stderr: String::from_utf8_lossy(&output.stderr).trim().to_string(),
        });
    }
    serde_json::from_slice(&output.stdout).map_err(|source| AppError::ChildJson { mode, source })
}

// Keep every fault-child custody identity explicit at the process boundary.
#[allow(clippy::too_many_arguments)]
fn run_fault_child(
    executable: &Path,
    case: FailureCase,
    source_root: &Path,
    trial_dir: &Path,
    workload_path: &Path,
    base_fixture_path: &Path,
    base_fixture_sha256: &str,
    base_preflight: &Path,
    sequence: usize,
) -> Result<FailureAtomicityReceipt, AppError> {
    let case_arg = match case {
        FailureCase::AfterStagingBatch => "after-staging-batch",
        FailureCase::AfterDeleteSymbols => "after-delete-symbols",
        FailureCase::AfterDeleteImports => "after-delete-imports",
        FailureCase::AfterDeleteCalls => "after-delete-calls",
        FailureCase::AfterSymbolRows => "after-symbol-rows",
        FailureCase::AfterImportRows => "after-import-rows",
        FailureCase::AfterCallRows => "after-call-rows",
        FailureCase::BeforeCommit => "before-commit",
    };
    let unit = format!(
        "ab-codebase-index-a1-{}-fault-{case_arg}",
        std::process::id()
    );
    let mut command = transient_service_command(&unit, executable);
    command
        .arg("fault-run")
        .arg("--case")
        .arg(case_arg)
        .arg("--source-root")
        .arg(source_root)
        .arg("--trial-dir")
        .arg(trial_dir)
        .arg("--workload")
        .arg(workload_path)
        .arg("--base-fixture")
        .arg(base_fixture_path)
        .arg("--base-fixture-sha256")
        .arg(base_fixture_sha256)
        .arg("--expected-cgroup-unit")
        .arg(&unit)
        .arg("--base-preflight")
        .arg(base_preflight)
        .arg("--sequence")
        .arg(sequence.to_string());
    let output = output_with_timeout(command, std::time::Duration::from_secs(1_800), Some(&unit))
        .map_err(|error| timed_child_error(error, Mode::StagedNative))?;
    if !output.success {
        return Err(AppError::ChildFailure {
            mode: Mode::StagedNative,
            stderr: String::from_utf8_lossy(&output.stderr).trim().to_string(),
        });
    }
    let receipt: FailureAtomicityReceipt =
        serde_json::from_slice(&output.stdout).map_err(|source| AppError::ChildJson {
            mode: Mode::StagedNative,
            source,
        })?;
    if receipt.case != case {
        return Err(AppError::ChildContract(
            "failure child case identity mismatch".to_string(),
        ));
    }
    Ok(receipt)
}

struct CapturedOutput {
    success: bool,
    stdout: Vec<u8>,
    stderr: Vec<u8>,
}

#[derive(Debug)]
enum TimedOutputError {
    Timeout,
    OrphanedUnit(String),
    Io(std::io::Error),
}

fn timed_child_error(error: TimedOutputError, mode: Mode) -> AppError {
    match error {
        TimedOutputError::Timeout => AppError::ChildTimeout { mode },
        TimedOutputError::OrphanedUnit(unit) => AppError::ChildContract(format!(
            "timed-out transient service {unit} remained active after stop"
        )),
        TimedOutputError::Io(error) => AppError::Io(error),
    }
}

fn transient_service_command(unit: &str, executable: &Path) -> Command {
    transient_service_command_with_env(unit, executable, &[])
}

fn transient_service_command_with_env(
    unit: &str,
    executable: &Path,
    environment: &[(&str, &str)],
) -> Command {
    let mut command = Command::new("systemd-run");
    command.args([
        "--user",
        "--wait",
        "--pipe",
        "--quiet",
        "--collect",
        "--expand-environment=no",
        "--property=RuntimeMaxSec=1800s",
        "--property=KillMode=control-group",
        "--property=TimeoutStopSec=30s",
        "--property=CPUAffinity=39",
        "--property=CPUWeight=100",
        "--property=NoNewPrivileges=yes",
        "--property=SystemCallArchitectures=native",
        "--property=SystemCallErrorNumber=EPERM",
        "--property=SystemCallFilter=~sched_setaffinity",
        "--unit",
        unit,
    ]);
    for (key, value) in environment {
        command.arg(format!("--setenv={key}={value}"));
    }
    command.arg(executable);
    command
}

fn stop_and_verify_transient_unit(unit: &str) -> Result<(), TimedOutputError> {
    // Every systemctl client is independently bounded. A failed stop request is
    // not an early return: the verifier still attempts a control-group kill and
    // proves the unit collected/unpopulated before releasing custody.
    let _ = bounded_systemctl_output(&["--user", "stop", "--no-block", unit]);

    let started = Instant::now();
    let mut kill_requested = false;
    while started.elapsed() < std::time::Duration::from_secs(30) {
        if !kill_requested && started.elapsed() >= std::time::Duration::from_secs(5) {
            let _ = bounded_systemctl_output(&[
                "--user",
                "kill",
                "--kill-whom=all",
                "--signal=KILL",
                unit,
            ]);
            kill_requested = true;
        }
        if let Ok(output) = bounded_systemctl_output(&[
            "--user",
            "show",
            unit,
            "--property=LoadState",
            "--property=ActiveState",
            "--property=SubState",
            "--property=ControlGroup",
            "--no-pager",
        ]) {
            if String::from_utf8(output.stdout)
                .ok()
                .and_then(|value| parse_transient_unit_state(&value))
                .is_some_and(|state| transient_unit_is_quiescent(&state))
            {
                return Ok(());
            }
        }
        std::thread::sleep(std::time::Duration::from_millis(100));
    }
    Err(TimedOutputError::OrphanedUnit(unit.to_string()))
}

fn bounded_systemctl_output(args: &[&str]) -> Result<std::process::Output, TimedOutputError> {
    Command::new("/usr/bin/timeout")
        .args(["--kill-after=1s", "2s", "systemctl"])
        .args(args)
        .output()
        .map_err(TimedOutputError::Io)
}

#[derive(Debug, PartialEq, Eq)]
struct TransientUnitState {
    load_state: String,
    active_state: String,
    sub_state: String,
    control_group: String,
}

fn parse_transient_unit_state(value: &str) -> Option<TransientUnitState> {
    fn property(value: &str, name: &str) -> Option<String> {
        value
            .lines()
            .find_map(|line| line.strip_prefix(name))
            .map(str::trim)
            .map(str::to_string)
    }
    Some(TransientUnitState {
        load_state: property(value, "LoadState=")?,
        active_state: property(value, "ActiveState=")?,
        sub_state: property(value, "SubState=")?,
        control_group: property(value, "ControlGroup=")?,
    })
}

fn transient_unit_is_quiescent(state: &TransientUnitState) -> bool {
    if state.load_state == "not-found" {
        return true;
    }
    matches!(state.active_state.as_str(), "inactive" | "failed")
        && matches!(state.sub_state.as_str(), "dead" | "failed")
        && cgroup_is_unpopulated(&state.control_group)
}

fn cgroup_is_unpopulated(relative: &str) -> bool {
    if relative.is_empty() {
        return true;
    }
    let relative = Path::new(relative.trim_start_matches('/'));
    if relative
        .components()
        .any(|component| !matches!(component, std::path::Component::Normal(_)))
    {
        return false;
    }
    let directory = Path::new("/sys/fs/cgroup").join(relative);
    match directory.try_exists() {
        Ok(false) => return true,
        Ok(true) => {}
        Err(_) => return false,
    }
    let processes_empty = fs::read_to_string(directory.join("cgroup.procs"))
        .is_ok_and(|value| value.trim().is_empty());
    let explicitly_unpopulated =
        fs::read_to_string(directory.join("cgroup.events")).is_ok_and(|value| {
            value
                .lines()
                .any(|line| line.split_whitespace().eq(["populated", "0"]))
        });
    processes_empty && explicitly_unpopulated
}

fn output_with_timeout(
    mut command: Command,
    timeout: std::time::Duration,
    transient_unit: Option<&str>,
) -> Result<CapturedOutput, TimedOutputError> {
    command.stdout(Stdio::piped()).stderr(Stdio::piped());
    let mut child = command.spawn().map_err(TimedOutputError::Io)?;
    let Some(mut stdout_pipe) = child.stdout.take() else {
        let cleanup = transient_unit
            .map(stop_and_verify_transient_unit)
            .transpose();
        let _ = child.kill();
        let _ = child.wait();
        cleanup?;
        return Err(TimedOutputError::Io(std::io::Error::other(
            "child stdout pipe missing",
        )));
    };
    let Some(mut stderr_pipe) = child.stderr.take() else {
        let cleanup = transient_unit
            .map(stop_and_verify_transient_unit)
            .transpose();
        let _ = child.kill();
        let _ = child.wait();
        cleanup?;
        return Err(TimedOutputError::Io(std::io::Error::other(
            "child stderr pipe missing",
        )));
    };
    let stdout_reader = std::thread::spawn(move || {
        let mut bytes = Vec::new();
        stdout_pipe.read_to_end(&mut bytes).map(|_| bytes)
    });
    let stderr_reader = std::thread::spawn(move || {
        let mut bytes = Vec::new();
        stderr_pipe.read_to_end(&mut bytes).map(|_| bytes)
    });
    let started = Instant::now();
    loop {
        let status = match child.try_wait() {
            Ok(status) => status,
            Err(error) => {
                let cleanup = transient_unit
                    .map(stop_and_verify_transient_unit)
                    .transpose();
                let _ = child.kill();
                let _ = child.wait();
                let _ = stdout_reader.join();
                let _ = stderr_reader.join();
                return cleanup.and(Err(TimedOutputError::Io(error)));
            }
        };
        if let Some(status) = status {
            let cleanup = transient_unit
                .map(stop_and_verify_transient_unit)
                .transpose();
            let stdout = join_output_reader(stdout_reader, "stdout");
            let stderr = join_output_reader(stderr_reader, "stderr");
            cleanup?;
            let stdout = stdout?;
            let stderr = stderr?;
            return Ok(CapturedOutput {
                success: status.success(),
                stdout,
                stderr,
            });
        }
        if started.elapsed() >= timeout {
            let cleanup = transient_unit
                .map(stop_and_verify_transient_unit)
                .transpose();
            let _ = child.kill();
            let _ = child.wait();
            let _ = stdout_reader.join();
            let _ = stderr_reader.join();
            cleanup?;
            return Err(TimedOutputError::Timeout);
        }
        std::thread::sleep(std::time::Duration::from_millis(50));
    }
}

fn join_output_reader(
    reader: std::thread::JoinHandle<std::io::Result<Vec<u8>>>,
    name: &str,
) -> Result<Vec<u8>, TimedOutputError> {
    reader
        .join()
        .map_err(|_| {
            TimedOutputError::Io(std::io::Error::other(format!("{name} reader panicked")))
        })?
        .map_err(TimedOutputError::Io)
}

fn validate_child(
    receipt: &RunReceipt,
    expected_mode: Mode,
    expected_workload: &Workload,
    expected_build: &ab_codebase_index_a1::BuildIdentity,
    expected_trial_dir: &Path,
    expected_sequence: usize,
) -> Result<(), AppError> {
    if receipt.schema != RUN_RECEIPT_SCHEMA
        || receipt.mode != expected_mode
        || receipt.workload != *expected_workload
        || receipt.build_identity != *expected_build
        || receipt.storage.trial_root != expected_trial_dir.canonicalize()?
        || receipt.execution.mode != expected_mode
        || receipt.execution.sequence != expected_sequence
        || receipt.execution.process_id == 0
        || receipt.execution.started_unix_ns >= receipt.execution.finished_unix_ns
    {
        return Err(AppError::ChildContract(format!(
            "mode {expected_mode:?} did not bind schema/workload/build/trial identity"
        )));
    }
    Ok(())
}

// This internal CLI entrypoint mirrors the explicit child custody arguments.
#[allow(clippy::too_many_arguments)]
async fn run_one(
    mode: Mode,
    source_root: &Path,
    trial_dir: &Path,
    workload: Workload,
    base_fixture_sha256: String,
    base_fixture_path: &Path,
    expected_cgroup_unit: Option<&str>,
    base_preflight_path: &Path,
    sequence: usize,
) -> Result<RunReceipt, AppError> {
    #[cfg(not(feature = "staged-native"))]
    {
        let _ = (
            mode,
            source_root,
            trial_dir,
            workload,
            base_fixture_sha256,
            base_fixture_path,
            expected_cgroup_unit,
            base_preflight_path,
            sequence,
        );
        return Err(AppError::FeatureMissing);
    }

    #[cfg(feature = "staged-native")]
    {
        let child_started_unix_ns = unix_time_ns()?;
        let source_root = source_root.canonicalize()?;
        let trial_dir = trial_dir.canonicalize()?;
        let base_fixture_path = base_fixture_path.canonicalize()?;
        let database_dir = trial_dir.join("database");
        let staging_dir = trial_dir.join("staging");
        fs::create_dir_all(&database_dir)?;
        fs::create_dir_all(&staging_dir)?;
        let database_path = database_dir.join("state.db");
        if database_path.try_exists()? {
            return Err(AppError::BaseFixture(
                "measured child target database already exists before child-local copy".to_string(),
            ));
        }
        fs::copy(&base_fixture_path, &database_path)?;
        let database_path = database_path.canonicalize()?;
        let database_copy_sha256_before =
            ab_codebase_index_a1::provenance::sha256_file(&database_path)?;
        let base_sidecars_absent_before = sidecars_absent(&database_path)?;
        let base_preflight: BaseFixturePreflightReceipt =
            serde_json::from_slice(&fs::read(base_preflight_path)?)?;
        if base_preflight.base_fixture_sha256 != base_fixture_sha256
            || base_preflight.database_copy_sha256 != base_fixture_sha256
            || base_preflight.workload != workload
            || database_copy_sha256_before != base_fixture_sha256
        {
            return Err(AppError::BaseFixture(
                "measured child is not bound to the preflight base/workload".to_string(),
            ));
        }
        let store = ab_store::SqliteStore::open(&database_path)
            .await
            .map_err(|error| AppError::Store(error.to_string()))?;
        let authoritative_pragmas_before = authoritative_pragmas(&store).await?;
        let wal_reset = reset_main_wal(&database_path)?;
        if !wal_reset.proven_empty {
            return Err(AppError::BaseFixture(
                "measured child WAL reset did not prove an empty WAL".to_string(),
            ));
        }
        let languages = vec![
            "rust".to_string(),
            "python".to_string(),
            "typescript".to_string(),
            "go".to_string(),
        ];
        let cgroup_before = cgroup_memory_snapshot();
        let proc_io_before = proc_io_snapshot();
        let rusage_before = rusage_snapshot();
        let interference_start = expected_cgroup_unit
            .map(|_| cpu_process_sample(39))
            .transpose()?;
        let operation_started_monotonic_ns = monotonic_time_ns()?;
        let (stats, authoritative_transaction_ns, full_vec, staged_native) = match mode {
            Mode::FullVec => {
                let outcome = store
                    .codebase_index_full_vec_a1(source_root.to_string_lossy().as_ref(), &languages)
                    .await
                    .map_err(|error| AppError::Store(error.to_string()))?;
                let telemetry = outcome.telemetry;
                (
                    outcome.stats,
                    telemetry.authoritative_transaction_ns,
                    Some(FullVecEvidence {
                        strategy: telemetry.strategy,
                        extraction_and_accumulation_ns: telemetry.extraction_and_accumulation_ns,
                        autocommit_before: telemetry.autocommit_before,
                        autocommit_during: telemetry.autocommit_during,
                        autocommit_after: telemetry.autocommit_after,
                    }),
                    None,
                )
            }
            Mode::StagedNative => {
                let outcome = store
                    .codebase_index_bounded_native_a1(
                        source_root.to_string_lossy().as_ref(),
                        &languages,
                        ab_store::CodebaseIndexA1Options {
                            batch_rows: workload.batch_rows,
                            failpoint: None,
                            staging_parent: Some(staging_dir.clone()),
                        },
                    )
                    .await
                    .map_err(|error| AppError::Store(error.to_string()))?;
                let telemetry = outcome.telemetry;
                (
                    outcome.stats,
                    telemetry.authoritative_transaction_ns,
                    None,
                    Some(StagedNativeEvidence {
                        strategy: telemetry.strategy,
                        batch_rows: telemetry.batch_rows,
                        emitted_batches: telemetry.emitted_batches,
                        staging_file_bytes: telemetry.staging_file_bytes,
                        staging_file_path: telemetry.staging_file_path,
                        staging_file_device: telemetry.staging_file_device,
                        staging_file_mount_point: telemetry.staging_file_mount_point,
                        staging_file_filesystem_type: telemetry.staging_file_filesystem_type,
                        declared_live_row_bound: telemetry.declared_live_row_bound,
                        max_accumulator_rows: telemetry.max_accumulator_rows,
                        max_extractor_output_rows: telemetry.max_extractor_output_rows,
                        staging_rows: telemetry.staging_rows,
                        staging_cleanup_succeeded: telemetry.staging_cleanup_succeeded,
                        staging_transaction_committed: telemetry.staging_transaction_committed,
                        authoritative_transaction_committed: telemetry
                            .authoritative_transaction_committed,
                        staging_parent_was_explicit: telemetry.staging_parent_was_explicit,
                        autocommit_before: telemetry.autocommit_before,
                        autocommit_during: telemetry.autocommit_during,
                        autocommit_after: telemetry.autocommit_after,
                    }),
                )
            }
        };
        let operation_finished_monotonic_ns = monotonic_time_ns()?;
        let elapsed_ns = operation_finished_monotonic_ns
            .checked_sub(operation_started_monotonic_ns)
            .ok_or_else(|| {
                std::io::Error::new(
                    std::io::ErrorKind::InvalidData,
                    "measured operation monotonic clock moved backwards",
                )
            })?;
        let interference_end = expected_cgroup_unit
            .map(|_| cpu_process_sample(39))
            .transpose()?;
        let child_interference = interference_start
            .as_ref()
            .zip(interference_end.as_ref())
            .map(|(start, end)| {
                compute_child_interference(
                    start,
                    end,
                    operation_started_monotonic_ns,
                    operation_finished_monotonic_ns,
                )
            })
            .transpose()?;
        let vm_hwm = peak_rss_bytes();
        let cgroup_after = cgroup_memory_snapshot();
        let proc_io_after = proc_io_snapshot();
        let rusage_after = rusage_snapshot();
        let peak_rss = vm_hwm
            .zip(rusage_after.map(|value| value.max_rss_bytes))
            .map(|(vm_hwm, rusage)| vm_hwm.max(rusage));
        let authoritative_pragmas_after = authoritative_pragmas(&store).await?;
        validate_stats(&stats, &workload, &source_root)?;
        let database = database_evidence(&database_path, &source_root)?;
        let fixture_after = fixture_state(&database_path, &source_root)?;
        let storage = storage_evidence(&trial_dir, &database_path, &staging_dir, mode);
        let executable_sha = executable_sha256()?;
        let build_identity = embedded_build_identity(Some(executable_sha));
        let (
            cgroup_path,
            current_before,
            current_after,
            peak_before,
            peak_after,
            memory_max,
            process_count,
            process_ids_before,
            process_ids_after,
            cgroup_is_shared,
            cgroup_isolated_for_trial,
            anon_after,
            anon_before,
            file_after,
            file_before,
            shmem_after,
            shmem_before,
        ) = match (cgroup_before, cgroup_after) {
            (Some(before), Some(after)) if before.path == after.path => (
                Some(before.path.clone()),
                Some(before.current_bytes),
                Some(after.current_bytes),
                Some(before.peak_bytes),
                Some(after.peak_bytes),
                Some(after.max),
                Some(after.process_count),
                Some(before.process_ids.clone()),
                Some(after.process_ids.clone()),
                Some(after.process_count > 1),
                Some(
                    expected_cgroup_unit
                        .is_some_and(|unit| after.path.ends_with(&format!("/{unit}.service")))
                        && before.process_ids == [std::process::id()]
                        && after.process_ids == [std::process::id()],
                ),
                Some(after.anon_bytes),
                Some(before.anon_bytes),
                Some(after.file_bytes),
                Some(before.file_bytes),
                Some(after.shmem_bytes),
                Some(before.shmem_bytes),
            ),
            _ => (
                None, None, None, None, None, None, None, None, None, None, None, None, None, None,
                None, None, None,
            ),
        };

        let child_finished_unix_ns = unix_time_ns()?;

        Ok(RunReceipt {
            schema: RUN_RECEIPT_SCHEMA.to_string(),
            mode,
            execution: ChildExecutionEvidence {
                mode,
                sequence,
                process_id: std::process::id(),
                started_unix_ns: child_started_unix_ns,
                finished_unix_ns: child_finished_unix_ns,
            },
            expected_cgroup_unit: expected_cgroup_unit.map(str::to_string),
            build_identity,
            workload,
            measurement: Measurement {
                elapsed_ns: Some(elapsed_ns),
                peak_rss_bytes: peak_rss,
                vm_hwm_bytes: vm_hwm,
                authoritative_transaction_ns: Some(authoritative_transaction_ns),
                cgroup_path,
                cgroup_memory_current_before_bytes: current_before,
                cgroup_memory_current_after_bytes: current_after,
                cgroup_memory_peak_before_bytes: peak_before,
                cgroup_memory_peak_after_bytes: peak_after,
                cgroup_memory_max: memory_max,
                cgroup_process_count: process_count,
                cgroup_process_ids_before: process_ids_before,
                cgroup_process_ids_after: process_ids_after,
                cgroup_is_shared,
                cgroup_isolated_for_trial,
                cgroup_memory_anon_before_bytes: anon_before,
                cgroup_memory_anon_after_bytes: anon_after,
                cgroup_memory_file_before_bytes: file_before,
                cgroup_memory_file_after_bytes: file_after,
                cgroup_memory_shmem_before_bytes: shmem_before,
                cgroup_memory_shmem_after_bytes: shmem_after,
                cgroup_memory_anon_delta_bytes: signed_delta(anon_before, anon_after),
                cgroup_memory_file_delta_bytes: signed_delta(file_before, file_after),
                cgroup_memory_shmem_delta_bytes: signed_delta(shmem_before, shmem_after),
                proc_io_read_bytes_before: proc_io_before.map(|value| value.read_bytes),
                proc_io_read_bytes_after: proc_io_after.map(|value| value.read_bytes),
                proc_io_write_bytes_before: proc_io_before.map(|value| value.write_bytes),
                proc_io_write_bytes_after: proc_io_after.map(|value| value.write_bytes),
                rusage_minor_faults_before: rusage_before.map(|value| value.minor_faults),
                rusage_minor_faults_after: rusage_after.map(|value| value.minor_faults),
                rusage_major_faults_before: rusage_before.map(|value| value.major_faults),
                rusage_major_faults_after: rusage_after.map(|value| value.major_faults),
                getrusage_max_rss_bytes: rusage_after.map(|value| value.max_rss_bytes),
                parent_wait4_max_rss_bytes: None,
            },
            child_interference,
            database,
            fixture: FixtureEvidence {
                base_fixture_sha256,
                database_copy_sha256_before,
                base_sidecars_absent_before,
                target_rows_before: base_preflight.target_rows,
                target_nonnull_embeddings_before: base_preflight.target_nonnull_embeddings,
                target_generation_sha256_before: base_preflight.target_generation_sha256,
                target_generation_sha256_after: fixture_after.target_generation_sha256,
                target_raw_sha256_before: base_preflight.target_raw_sha256,
                target_raw_sha256_after: fixture_after.target_raw_sha256,
                other_root_sha256_before: base_preflight.other_root_sha256,
                other_root_sha256_after: fixture_after.other_root_sha256,
                non_codebase_sentinel_sha256_before: base_preflight.non_codebase_sentinel_sha256,
                non_codebase_sentinel_sha256_after: fixture_after.non_codebase_sentinel_sha256,
            },
            authoritative_pragmas_before,
            authoritative_pragmas_after,
            wal_reset,
            storage,
            authority: AuthorityEvidence {
                isolated_sqlite_accessed: true,
                live_database_touched: false,
                production_write: false,
                runtime_adoption_authorized: false,
            },
            full_vec,
            staged_native,
        })
    }
}

#[cfg(feature = "staged-native")]
// Mirrors the hidden CLI boundary so no path/sequence/cgroup authority is implicit.
#[allow(clippy::too_many_arguments)]
async fn run_fault_one(
    case: FailureCase,
    source_root: &Path,
    trial_dir: &Path,
    workload: Workload,
    base_fixture_sha256: String,
    base_fixture_path: &Path,
    expected_cgroup_unit: &str,
    base_preflight_path: &Path,
    sequence: usize,
) -> Result<FailureAtomicityReceipt, AppError> {
    let child_started_unix_ns = unix_time_ns()?;
    let source_root = source_root.canonicalize()?;
    let trial_dir = trial_dir.canonicalize()?;
    let base_fixture_path = base_fixture_path.canonicalize()?;
    let database_path = trial_dir.join("database/state.db");
    if database_path.try_exists()? {
        return Err(AppError::BaseFixture(
            "fault child target database already exists before child-local copy".to_string(),
        ));
    }
    fs::copy(&base_fixture_path, &database_path)?;
    let database_path = database_path.canonicalize()?;
    let staging_dir = trial_dir.join("staging");
    fs::create_dir_all(&staging_dir)?;
    let database_copy_sha256_before =
        ab_codebase_index_a1::provenance::sha256_file(&database_path)?;
    let base_preflight: BaseFixturePreflightReceipt =
        serde_json::from_slice(&fs::read(base_preflight_path)?)?;
    if base_preflight.base_fixture_sha256 != base_fixture_sha256
        || base_preflight.database_copy_sha256 != base_fixture_sha256
        || base_preflight.workload != workload
        || database_copy_sha256_before != base_fixture_sha256
    {
        return Err(AppError::BaseFixture(
            "fault child is not bound to the preflight base/workload".to_string(),
        ));
    }
    let store = ab_store::SqliteStore::open(&database_path)
        .await
        .map_err(|error| AppError::Store(error.to_string()))?;
    let authoritative_pragmas_before = authoritative_pragmas(&store).await?;
    let wal_reset = reset_main_wal(&database_path)?;
    if wal_reset.busy != 0
        || wal_reset.log_frames != 0
        || wal_reset.checkpointed_frames != 0
        || wal_reset.wal_bytes != 0
        || !wal_reset.proven_empty
    {
        return Err(AppError::BaseFixture(
            "fault child WAL reset did not prove an empty WAL".to_string(),
        ));
    }
    let main_wal_bytes_before = sqlite_sidecar_bytes(&database_path, "-wal")?;
    let main_shm_bytes_before = sqlite_sidecar_bytes(&database_path, "-shm")?;
    let before = fixture_state(&database_path, &source_root)?;
    let rollback_before = rollback_state(&database_path, &source_root)?;
    if rollback_before != base_preflight.rollback_state {
        return Err(AppError::BaseFixture(
            "fault child rollback baseline differs from preflight".to_string(),
        ));
    }
    let cgroup_before = cgroup_memory_snapshot();
    let actual_process_affinity = current_process_affinity();
    let failpoint = match case {
        FailureCase::AfterStagingBatch => ab_store::CodebaseIndexA1Failpoint::AfterStagingBatch(1),
        FailureCase::AfterDeleteSymbols => ab_store::CodebaseIndexA1Failpoint::AfterDeleteSymbols,
        FailureCase::AfterDeleteImports => ab_store::CodebaseIndexA1Failpoint::AfterDeleteImports,
        FailureCase::AfterDeleteCalls => ab_store::CodebaseIndexA1Failpoint::AfterDeleteCalls,
        FailureCase::AfterSymbolRows => ab_store::CodebaseIndexA1Failpoint::AfterSymbolRows(1),
        FailureCase::AfterImportRows => ab_store::CodebaseIndexA1Failpoint::AfterImportRows(1),
        FailureCase::AfterCallRows => ab_store::CodebaseIndexA1Failpoint::AfterCallRows(1),
        FailureCase::BeforeCommit => ab_store::CodebaseIndexA1Failpoint::BeforeCommit,
    };
    let languages = vec![
        "rust".to_string(),
        "python".to_string(),
        "typescript".to_string(),
        "go".to_string(),
    ];
    let result = store
        .codebase_index_bounded_native_a1(
            source_root.to_string_lossy().as_ref(),
            &languages,
            ab_store::CodebaseIndexA1Options {
                batch_rows: workload.batch_rows,
                failpoint: Some(failpoint),
                staging_parent: Some(staging_dir.clone()),
            },
        )
        .await;
    let observed_error = result
        .as_ref()
        .err()
        .map(ToString::to_string)
        .unwrap_or_else(|| "UNEXPECTED_SUCCESS".to_string());
    let expected_error_marker = case.expected_error_marker().to_string();
    let post_fault_pragmas = authoritative_pragmas(&store).await?;
    let post_fault_result_bytes = serde_json::to_vec(&post_fault_pragmas)?;
    let post_fault_query = PostFaultQueryEvidence {
        query: "codebase_index_pragmas_a1".to_string(),
        succeeded: true,
        result_sha256: sha256_bytes(&post_fault_result_bytes),
    };
    let authoritative_pragmas_after = post_fault_pragmas;
    let after = fixture_state(&database_path, &source_root)?;
    let rollback_after = rollback_state(&database_path, &source_root)?;
    let main_wal_bytes_after = sqlite_sidecar_bytes(&database_path, "-wal")?;
    let post_fault_wal_header_layout = wal_header_layout_evidence(
        &database_path,
        base_preflight.database.page_size.ok_or_else(|| {
            AppError::BaseFixture("base preflight lacks SQLite page size".to_string())
        })?,
    )?;
    let main_shm_bytes_after = sqlite_sidecar_bytes(&database_path, "-shm")?;
    let wal_cleanup = reset_main_wal(&database_path)?;
    if !wal_cleanup.proven_empty {
        return Err(AppError::BaseFixture(
            "fault child post-rollback WAL cleanup did not prove an empty WAL".to_string(),
        ));
    }
    let main_wal_bytes_after_cleanup = sqlite_sidecar_bytes(&database_path, "-wal")?;
    let main_shm_bytes_after_cleanup = sqlite_sidecar_bytes(&database_path, "-shm")?;
    let rollback_after_cleanup = rollback_state(&database_path, &source_root)?;
    if !rollback_semantics_equal(&rollback_after_cleanup, &rollback_after) {
        return Err(AppError::BaseFixture(
            format!(
                "fault child post-rollback WAL cleanup changed authoritative state: before={rollback_after:?}, after={rollback_after_cleanup:?}"
            ),
        ));
    }
    let cgroup_after = cgroup_memory_snapshot();
    let (
        cgroup_path,
        cgroup_process_count,
        cgroup_process_ids_before,
        cgroup_process_ids_after,
        cgroup_isolated_for_trial,
    ) = match (cgroup_before, cgroup_after) {
        (Some(before), Some(after)) if before.path == after.path => {
            let isolated = before.process_count == 1
                && after.process_count == 1
                && before.process_ids == [std::process::id()]
                && after.process_ids == [std::process::id()]
                && after
                    .path
                    .ends_with(&format!("/{expected_cgroup_unit}.service"))
                && actual_process_affinity == "39";
            (
                after.path,
                after.process_count,
                before.process_ids,
                after.process_ids,
                isolated,
            )
        }
        _ => ("UNBOUND".to_string(), 0, Vec::new(), Vec::new(), false),
    };
    let staging_cleanup_succeeded = fs::read_dir(&staging_dir)?.next().is_none();
    let executable_sha = executable_sha256()?;
    let child_finished_unix_ns = unix_time_ns()?;
    Ok(FailureAtomicityReceipt {
        schema: FAILURE_RECEIPT_SCHEMA.to_string(),
        case,
        workload,
        execution: ChildExecutionEvidence {
            mode: Mode::StagedNative,
            sequence,
            process_id: std::process::id(),
            started_unix_ns: child_started_unix_ns,
            finished_unix_ns: child_finished_unix_ns,
        },
        build_identity: embedded_build_identity(Some(executable_sha)),
        trial_root: trial_dir,
        database_path,
        expected_cgroup_unit: expected_cgroup_unit.to_string(),
        cgroup_path,
        cgroup_process_count,
        cgroup_process_ids_before,
        cgroup_process_ids_after,
        cgroup_isolated_for_trial,
        actual_process_affinity,
        wal_reset,
        wal_cleanup,
        post_fault_wal_header_layout,
        main_wal_bytes_before,
        main_wal_bytes_after,
        main_wal_bytes_after_cleanup,
        main_shm_bytes_before,
        main_shm_bytes_after,
        main_shm_bytes_after_cleanup,
        expected_error_observed: observed_error.contains(&expected_error_marker),
        expected_error_marker,
        observed_error,
        target_generation_sha256_before: before.target_generation_sha256,
        target_generation_sha256_after: after.target_generation_sha256,
        other_root_sha256_before: before.other_root_sha256,
        other_root_sha256_after: after.other_root_sha256,
        non_codebase_sentinel_sha256_before: before.non_codebase_sentinel_sha256,
        non_codebase_sentinel_sha256_after: after.non_codebase_sentinel_sha256,
        rollback_before,
        rollback_after,
        rollback_after_cleanup,
        authoritative_pragmas_before,
        authoritative_pragmas_after,
        connection_usable_after: post_fault_query.succeeded,
        post_fault_query,
        staging_cleanup_succeeded,
        base_fixture_sha256,
        database_copy_sha256_before,
    })
}

#[cfg(not(feature = "staged-native"))]
async fn run_fault_one(
    _case: FailureCase,
    _source_root: &Path,
    _trial_dir: &Path,
    _workload: Workload,
    _base_fixture_sha256: String,
    _base_fixture_path: &Path,
    _expected_cgroup_unit: &str,
    _base_preflight_path: &Path,
    _sequence: usize,
) -> Result<FailureAtomicityReceipt, AppError> {
    Err(AppError::FeatureMissing)
}

#[cfg(feature = "staged-native")]
async fn authoritative_pragmas(
    store: &ab_store::SqliteStore,
) -> Result<AuthoritativePragmaEvidence, AppError> {
    let value = store
        .codebase_index_pragmas_a1()
        .await
        .map_err(|error| AppError::Store(error.to_string()))?;
    Ok(AuthoritativePragmaEvidence {
        journal_mode: value.journal_mode,
        synchronous: value.synchronous,
        wal_autocheckpoint: value.wal_autocheckpoint,
        cache_size: value.cache_size,
        cache_spill: value.cache_spill,
        temp_store: value.temp_store,
        mmap_size: value.mmap_size,
        foreign_keys: value.foreign_keys,
        busy_timeout_ms: value.busy_timeout_ms,
        locking_mode: value.locking_mode,
        autocommit: value.autocommit,
        database_names: value.database_names,
        database_files: value.database_files,
    })
}

#[cfg(feature = "staged-native")]
fn validate_stats(
    stats: &ab_store::CodebaseIndexStats,
    workload: &Workload,
    source_root: &Path,
) -> Result<(), AppError> {
    if u64::from(stats.indexed_files) != workload.documents
        || u64::from(stats.symbols) != workload.symbols
        || u64::from(stats.imports) != workload.imports
        || u64::from(stats.calls) != workload.calls
        || stats.root_path != source_root.to_string_lossy()
    {
        return Err(AppError::IndexContract(format!(
            "stats {:?} do not match frozen workload {:?}",
            stats, workload
        )));
    }
    Ok(())
}

fn duration_ns(duration: std::time::Duration) -> u64 {
    u64::try_from(duration.as_nanos()).unwrap_or(u64::MAX)
}

fn unix_time_ns() -> Result<u64, AppError> {
    let duration = std::time::SystemTime::now()
        .duration_since(std::time::UNIX_EPOCH)
        .map_err(|error| {
            AppError::ChildContract(format!("system clock precedes epoch: {error}"))
        })?;
    Ok(duration_ns(duration))
}

fn signed_delta(before: Option<u64>, after: Option<u64>) -> Option<i64> {
    let delta = i128::from(after?) - i128::from(before?);
    i64::try_from(delta).ok()
}

fn rollback_semantics_equal(
    left: &ab_codebase_index_a1::RollbackStateEvidence,
    right: &ab_codebase_index_a1::RollbackStateEvidence,
) -> bool {
    let mut left = left.clone();
    let mut right = right.clone();
    left.database_sha256.clear();
    right.database_sha256.clear();
    left == right
}

fn sqlite_sidecar_bytes(database_path: &Path, suffix: &str) -> Result<u64, AppError> {
    let mut sidecar = database_path.as_os_str().to_os_string();
    sidecar.push(suffix);
    match fs::metadata(PathBuf::from(sidecar)) {
        Ok(metadata) => Ok(metadata.len()),
        Err(error) if error.kind() == std::io::ErrorKind::NotFound => Ok(0),
        Err(error) => Err(AppError::Io(error)),
    }
}

fn sha256_bytes(bytes: &[u8]) -> String {
    let mut digest = Sha256::new();
    digest.update(bytes);
    format!("{:x}", digest.finalize())
}

fn emit_json<T: Serialize>(value: &T, output: Option<&Path>) -> Result<(), AppError> {
    let bytes = serde_json::to_vec_pretty(value)?;
    if let Some(path) = output {
        let mut file = OpenOptions::new()
            .write(true)
            .create_new(true)
            .open(path)
            .map_err(|error| {
                if error.kind() == std::io::ErrorKind::AlreadyExists {
                    AppError::OutputExists(path.display().to_string())
                } else {
                    AppError::Io(error)
                }
            })?;
        file.write_all(&bytes)?;
        file.write_all(b"\n")?;
        file.sync_all()?;
        if let Some(parent) = path.parent() {
            let parent = if parent.as_os_str().is_empty() {
                Path::new(".")
            } else {
                parent
            };
            fs::File::open(parent)?.sync_all()?;
        }
    } else {
        let mut stdout = std::io::stdout().lock();
        stdout.write_all(&bytes)?;
        stdout.write_all(b"\n")?;
    }
    Ok(())
}

#[cfg(test)]
mod tests {
    use std::{ffi::OsStr, fs, path::Path};

    use super::{
        base_fixture_preflight, build_base_fixture, canonical_output_preflight, emit_json,
        output_with_timeout, parse_transient_unit_state, rollback_semantics_equal, run_fault_one,
        transient_service_command, transient_service_command_with_env, transient_unit_is_quiescent,
        AppError,
    };
    use ab_codebase_index_a1::{
        quiet::{child_interference, cpu_process_sample, monotonic_time_ns},
        snapshot::cgroup_memory_snapshot,
        workload::materialize,
        FailureCase,
    };

    #[test]
    fn canonical_terminal_failures_have_distinct_nonzero_exit_codes() {
        assert_eq!(AppError::EvidenceInvalid.exit_code(), 2);
        assert_eq!(AppError::DecisionFailed.exit_code(), 3);
        assert_ne!(
            AppError::EvidenceInvalid.exit_code(),
            AppError::DecisionFailed.exit_code()
        );
    }

    #[test]
    fn runtime_environment_binds_installed_systemd_version() {
        let environment = super::runtime_environment();
        assert_ne!(environment.systemd_version, "UNBOUND");
        assert!(environment.systemd_version.starts_with("systemd "));
    }

    #[test]
    fn canonical_output_custody_rejects_relative_paths_before_touching_storage() {
        let error = canonical_output_preflight(
            Path::new("relative-result.json"),
            Path::new("relative-trials"),
        )
        .unwrap_err();
        assert!(error.to_string().contains("absolute path"));
    }

    #[test]
    fn transient_service_command_has_one_executable_and_frozen_kill_cpu_contract() {
        let executable = Path::new("/opt/ab-codebase-index-a1");
        let command = transient_service_command("ab-a1-test", executable);
        let args = command.get_args().collect::<Vec<_>>();
        assert_eq!(
            args.iter()
                .filter(|arg| **arg == OsStr::new("/opt/ab-codebase-index-a1"))
                .count(),
            1
        );
        for required in [
            "--property=RuntimeMaxSec=1800s",
            "--property=KillMode=control-group",
            "--property=TimeoutStopSec=30s",
            "--property=CPUAffinity=39",
            "--property=CPUWeight=100",
            "--property=NoNewPrivileges=yes",
            "--property=SystemCallArchitectures=native",
            "--property=SystemCallErrorNumber=EPERM",
            "--property=SystemCallFilter=~sched_setaffinity",
            "--collect",
        ] {
            assert!(args.iter().any(|arg| *arg == OsStr::new(required)));
        }
        assert_eq!(
            args.last().copied(),
            Some(OsStr::new("/opt/ab-codebase-index-a1"))
        );
    }

    #[test]
    fn transient_service_environment_is_propagated_before_the_executable() {
        let executable = Path::new("/opt/ab-codebase-index-a1");
        let command = transient_service_command_with_env(
            "ab-a1-test",
            executable,
            &[("AB_A1_CHILD", "1"), ("AB_A1_UNIT", "ab-a1-test")],
        );
        let args = command.get_args().collect::<Vec<_>>();
        let executable_index = args
            .iter()
            .position(|arg| *arg == OsStr::new("/opt/ab-codebase-index-a1"))
            .unwrap();
        for required in ["--setenv=AB_A1_CHILD=1", "--setenv=AB_A1_UNIT=ab-a1-test"] {
            let index = args
                .iter()
                .position(|arg| *arg == OsStr::new(required))
                .unwrap();
            assert!(index < executable_index);
        }
    }

    #[test]
    fn transient_unit_state_requires_inactive_dead_or_collected() {
        let active = parse_transient_unit_state(
            "LoadState=loaded\nActiveState=deactivating\nSubState=stop-sigterm\nControlGroup=/user.slice/test.service\n",
        )
        .unwrap();
        assert!(!transient_unit_is_quiescent(&active));

        let collected = parse_transient_unit_state(
            "LoadState=not-found\nActiveState=inactive\nSubState=dead\nControlGroup=\n",
        )
        .unwrap();
        assert!(transient_unit_is_quiescent(&collected));
    }

    #[test]
    fn real_transient_child_binds_cpu39_and_exact_cgroup_membership() {
        const CHILD_ENV: &str = "AB_A1_TRANSIENT_CGROUP_SMOKE_CHILD";
        const UNIT_ENV: &str = "AB_A1_TRANSIENT_CGROUP_SMOKE_UNIT";
        if std::env::var(CHILD_ENV).as_deref() == Ok("1") {
            let expected_unit = std::env::var(UNIT_ENV).unwrap();
            let snapshot = cgroup_memory_snapshot().unwrap();
            assert!(snapshot
                .path
                .ends_with(&format!("/{expected_unit}.service")));
            assert_eq!(snapshot.process_ids, [std::process::id()]);
            let blocked_affinity_change = std::process::Command::new("/usr/bin/taskset")
                .args(["-pc", "39", "0"])
                .status()
                .unwrap();
            assert!(
                !blocked_affinity_change.success(),
                "the transient seccomp contract must reject sched_setaffinity even when the requested mask is unchanged"
            );
            let start = cpu_process_sample(39).unwrap();
            assert_eq!(start.actual_affinity, "39");
            assert!(start.no_new_privileges);
            assert_eq!(start.seccomp_mode, 2);
            assert!(start.seccomp_filter_count > 0);
            assert!(start
                .thread_affinities
                .iter()
                .all(|thread| thread.allowed_cpus == "39"));
            let operation_started_monotonic_ns = monotonic_time_ns().unwrap();
            let deadline = std::time::Instant::now() + std::time::Duration::from_millis(250);
            let mut accumulator = 0_u64;
            while std::time::Instant::now() < deadline {
                accumulator = std::hint::black_box(accumulator.wrapping_add(1));
            }
            std::hint::black_box(accumulator);
            let operation_finished_monotonic_ns = monotonic_time_ns().unwrap();
            let end = cpu_process_sample(39).unwrap();
            let evidence = child_interference(
                &start,
                &end,
                operation_started_monotonic_ns,
                operation_finished_monotonic_ns,
            )
            .unwrap();
            assert_eq!(start.clock_ticks_per_second, 100);
            assert!(start.monotonic_clock_resolution_ns > 0);
            assert!(evidence.cgroup_cpu_inner_delta_usec > 0);
            assert!(evidence.cpu39_scheduled_runtime_outer_ns > 0);
            return;
        }

        let unit = format!("ab-codebase-index-a1-{}-cgroup-smoke", std::process::id());
        let executable = std::env::current_exe().unwrap();
        let mut command = transient_service_command_with_env(
            &unit,
            &executable,
            &[(CHILD_ENV, "1"), (UNIT_ENV, unit.as_str())],
        );
        command.args([
            "--exact",
            "tests::real_transient_child_binds_cpu39_and_exact_cgroup_membership",
            "--nocapture",
        ]);
        let output =
            output_with_timeout(command, std::time::Duration::from_secs(30), Some(&unit)).unwrap();
        assert!(
            output.success,
            "stdout={} stderr={}",
            String::from_utf8_lossy(&output.stdout),
            String::from_utf8_lossy(&output.stderr),
        );
    }

    #[test]
    fn real_transient_timeout_collects_the_service_before_returning() {
        let unit = format!("ab-codebase-index-a1-{}-timeout-smoke", std::process::id());
        let mut command = transient_service_command(&unit, Path::new("/bin/sleep"));
        command.arg("60");
        let result =
            output_with_timeout(command, std::time::Duration::from_millis(150), Some(&unit));
        assert!(matches!(result, Err(super::TimedOutputError::Timeout)));
    }

    #[cfg(feature = "staged-native")]
    #[tokio::test(flavor = "current_thread")]
    async fn real_fault_path_starts_and_finishes_with_empty_wal_and_exact_rollback() {
        let root = tempfile::tempdir_in("/Data/CascadeProjects").unwrap();
        let suite = root.path().join("suite");
        let corpus = suite.join("corpus");
        fs::create_dir_all(&corpus).unwrap();
        let workload = materialize(&corpus, 1, 16).unwrap();
        let (base_path, base_sha) = build_base_fixture(&suite, &corpus, &workload)
            .await
            .unwrap();
        let preflight =
            base_fixture_preflight(&corpus, &base_path, workload.clone(), base_sha.clone())
                .unwrap();
        let preflight_path = suite.join("base-preflight.json");
        emit_json(&preflight, Some(&preflight_path)).unwrap();

        let trial = suite.join("fault-smoke");
        fs::create_dir_all(trial.join("database")).unwrap();
        let receipt = run_fault_one(
            FailureCase::AfterSymbolRows,
            &corpus,
            &trial,
            workload,
            base_sha,
            &base_path,
            "ab-codebase-index-a1-test-fault-after-symbol-rows",
            &preflight_path,
            20,
        )
        .await
        .unwrap();

        assert!(receipt.expected_error_observed, "{receipt:#?}");
        assert!(receipt.wal_reset.proven_empty);
        assert_eq!(receipt.main_wal_bytes_before, 0);
        assert_eq!(receipt.main_wal_bytes_after, 4_152);
        assert_eq!(receipt.post_fault_wal_header_layout.bytes, 4_152);
        assert!(matches!(
            receipt.post_fault_wal_header_layout.magic,
            Some(0x377f_0682) | Some(0x377f_0683)
        ));
        assert_eq!(
            receipt.post_fault_wal_header_layout.format_version,
            Some(3_007_000)
        );
        assert_eq!(
            receipt.post_fault_wal_header_layout.encoded_page_size,
            Some(4_096)
        );
        assert_eq!(receipt.post_fault_wal_header_layout.frame_count, 1);
        assert!(receipt.post_fault_wal_header_layout.header_layout_valid);
        assert!(receipt.wal_cleanup.proven_empty);
        assert_eq!(receipt.main_wal_bytes_after_cleanup, 0);
        assert_eq!(receipt.rollback_before, preflight.rollback_state);
        assert_eq!(receipt.rollback_after, preflight.rollback_state);
        assert!(rollback_semantics_equal(
            &receipt.rollback_after_cleanup,
            &preflight.rollback_state,
        ));
        assert_ne!(
            receipt.rollback_after_cleanup.database_sha256,
            preflight.rollback_state.database_sha256
        );
        assert!(receipt.connection_usable_after);
        assert!(receipt.staging_cleanup_succeeded);
    }
}
