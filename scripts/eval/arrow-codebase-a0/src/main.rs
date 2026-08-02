use std::{
    error::Error,
    fs::{File, OpenOptions},
    io::{self, BufWriter, Read, Write},
    path::{Path, PathBuf},
    process::{Command as ProcessCommand, ExitCode},
};

use ab_codebase_arrow_a0::{
    arrow_schema_fingerprints, assess_trials, embedded_build_identity, evaluate_frozen_workload,
    frozen_workload_identity, validate_evaluation_receipt, AssessmentContext, BuildIdentity,
    EnvironmentReceipt, EvaluationConfig, EvaluationMode, EvaluationReceipt, EvidenceClass,
    PromotionThresholds, RuntimeSourceIdentity, SuiteReceipt, ARROW_SCHEMA_CONTRACT,
    CANONICAL_BATCH_ROWS, CANONICAL_DOCUMENTS, CANONICAL_TRIALS_PER_MODE, EMPTY_SHA256,
    EVALUATION_RECEIPT_SCHEMA, FROZEN_WORKLOAD_SCHEMA, SEMANTIC_SCHEMA, SUITE_RECEIPT_SCHEMA,
};
use clap::{Parser, Subcommand};
use sha2::{Digest, Sha256};

#[derive(Debug, Parser)]
#[command(
    name = "ab-codebase-arrow-a0",
    about = "Evaluation-only Agent-Bridge codebase-index Arrow A0 harness"
)]
struct Cli {
    #[command(subcommand)]
    command: CliCommand,
}

#[derive(Debug, Subcommand)]
enum CliCommand {
    /// Run exactly one materialization mode in the current process.
    Run {
        #[arg(long, value_enum)]
        mode: EvaluationMode,
        #[arg(long)]
        documents: usize,
        #[arg(long)]
        batch_rows: usize,
    },
    /// Run the one frozen, clean-release promotion suite.
    Suite {
        /// Write the receipt to a new file instead of stdout.
        #[arg(long)]
        output: Option<PathBuf>,
    },
    /// Run a non-promotable sensitivity or smoke suite.
    DiagnosticSuite {
        #[arg(long)]
        documents: usize,
        #[arg(long)]
        batch_rows: usize,
        #[arg(long, default_value_t = 1)]
        trials: usize,
        #[arg(long, default_value_t = 30)]
        min_rss_reduction_percent: u32,
        #[arg(long, default_value_t = 10)]
        max_elapsed_regression_percent: u32,
        /// Write the receipt to a new file instead of stdout.
        #[arg(long)]
        output: Option<PathBuf>,
    },
}

fn main() -> ExitCode {
    match execute(Cli::parse()) {
        Ok(()) => ExitCode::SUCCESS,
        Err(error) => {
            eprintln!("ab-codebase-arrow-a0: {error}");
            ExitCode::FAILURE
        }
    }
}

fn execute(cli: Cli) -> Result<(), Box<dyn Error>> {
    let (receipt, output_path) = match cli.command {
        CliCommand::Run {
            mode,
            documents,
            batch_rows,
        } => {
            let executable = std::env::current_exe()?;
            let mut receipt = evaluate_frozen_workload(
                mode,
                EvaluationConfig {
                    documents,
                    batch_rows,
                },
            )?;
            receipt.executable_sha256 = Some(sha256_file(&executable)?);
            return write_json(&receipt);
        }
        CliCommand::Suite { output } => (
            run_suite(
                EvaluationConfig {
                    documents: CANONICAL_DOCUMENTS,
                    batch_rows: CANONICAL_BATCH_ROWS,
                },
                CANONICAL_TRIALS_PER_MODE,
                EvidenceClass::CanonicalPromotion,
                PromotionThresholds::default(),
            )?,
            output,
        ),
        CliCommand::DiagnosticSuite {
            documents,
            batch_rows,
            trials,
            min_rss_reduction_percent,
            max_elapsed_regression_percent,
            output,
        } => (
            run_suite(
                EvaluationConfig {
                    documents,
                    batch_rows,
                },
                trials,
                EvidenceClass::Diagnostic,
                PromotionThresholds {
                    min_rss_reduction_basis_points: percent_to_basis_points(
                        min_rss_reduction_percent,
                    )?,
                    max_elapsed_regression_basis_points: percent_to_basis_points(
                        max_elapsed_regression_percent,
                    )?,
                },
            )?,
            output,
        ),
    };
    write_json_destination(&receipt, output_path.as_deref())
}

fn write_json<T: serde::Serialize>(value: &T) -> Result<(), Box<dyn Error>> {
    let stdout = io::stdout();
    let mut output = stdout.lock();
    serde_json::to_writer_pretty(&mut output, value)?;
    writeln!(output)?;
    Ok(())
}

fn write_json_destination<T: serde::Serialize>(
    value: &T,
    path: Option<&Path>,
) -> Result<(), Box<dyn Error>> {
    let Some(path) = path else {
        return write_json(value);
    };
    let file = OpenOptions::new().write(true).create_new(true).open(path)?;
    let mut output = BufWriter::new(file);
    serde_json::to_writer_pretty(&mut output, value)?;
    writeln!(output)?;
    output.flush()?;
    Ok(())
}

fn run_suite(
    config: EvaluationConfig,
    trials: usize,
    evidence_class: EvidenceClass,
    thresholds: PromotionThresholds,
) -> Result<SuiteReceipt, Box<dyn Error>> {
    if trials == 0 {
        return Err(invalid_input("trials must be greater than zero").into());
    }

    let executable = std::env::current_exe()?;
    let executable_sha256 = sha256_file(&executable)?;
    let build = embedded_build_identity();
    let canonical = evidence_class == EvidenceClass::CanonicalPromotion;
    let runtime_source = runtime_source_identity(&build, canonical)?;
    let executable_sha256_bound = is_lower_hex(&executable_sha256, 64);
    if canonical
        && (!runtime_source.build_matches_runtime
            || !canonical_build_ready(&build)
            || !executable_sha256_bound)
    {
        return Err(io::Error::other(
            "canonical suite requires a clean release build whose Git revision and Cargo.lock match the runtime worktree",
        )
        .into());
    }

    let modes = [
        EvaluationMode::FullVec,
        EvaluationMode::NativeChunk,
        EvaluationMode::ArrowRecordBatch,
    ];
    let mut receipts = Vec::with_capacity(trials.saturating_mul(modes.len()));
    for trial in 0..trials {
        for order_position in 0..modes.len() {
            let mode = modes[(trial + order_position) % modes.len()];
            let mut receipt = run_child(&executable, mode, config, &build, &executable_sha256)?;
            receipt.trial_index = Some(trial);
            receipt.order_position = Some(order_position);
            receipts.push(receipt);
        }
    }

    let post_run_identity_stable = if canonical {
        let post_run_executable_sha256 = sha256_file(&executable)?;
        let post_run_source = runtime_source_identity(&build, true)?;
        post_run_executable_sha256 == executable_sha256
            && post_run_source == runtime_source
            && post_run_source.build_matches_runtime
    } else {
        false
    };
    let assessment = assess_trials(
        &receipts,
        thresholds,
        AssessmentContext {
            evidence_class,
            runtime_source_bound: runtime_source.build_matches_runtime,
            executable_sha256_bound,
            runtime_identity_stable: post_run_identity_stable,
        },
    )?;
    Ok(SuiteReceipt {
        schema: SUITE_RECEIPT_SCHEMA.to_string(),
        config,
        trials_per_mode: trials,
        evidence_class,
        build,
        runtime_source,
        executable_sha256,
        post_run_identity_stable,
        fresh_process_per_trial: true,
        interleaved_mode_order: true,
        environment: environment_receipt(),
        receipts,
        assessment,
    })
}

fn run_child(
    executable: &Path,
    mode: EvaluationMode,
    config: EvaluationConfig,
    expected_build: &BuildIdentity,
    expected_executable_sha256: &str,
) -> Result<EvaluationReceipt, Box<dyn Error>> {
    let output = ProcessCommand::new(executable)
        .arg("run")
        .arg("--mode")
        .arg(mode_arg(mode))
        .arg("--documents")
        .arg(config.documents.to_string())
        .arg("--batch-rows")
        .arg(config.batch_rows.to_string())
        .output()?;
    if !output.status.success() {
        return Err(io::Error::other(format!(
            "child mode {} failed with {}: {}",
            mode_arg(mode),
            output.status,
            String::from_utf8_lossy(&output.stderr)
        ))
        .into());
    }
    let receipt: EvaluationReceipt = serde_json::from_slice(&output.stdout).map_err(|error| {
        io::Error::new(
            io::ErrorKind::InvalidData,
            format!(
                "child mode {} emitted invalid JSON: {error}; stderr={}",
                mode_arg(mode),
                String::from_utf8_lossy(&output.stderr)
            ),
        )
    })?;
    validate_child_receipt(
        &receipt,
        mode,
        config,
        expected_build,
        expected_executable_sha256,
    )?;
    Ok(receipt)
}

fn validate_child_receipt(
    receipt: &EvaluationReceipt,
    mode: EvaluationMode,
    config: EvaluationConfig,
    expected_build: &BuildIdentity,
    expected_executable_sha256: &str,
) -> Result<(), io::Error> {
    let common_valid = receipt.mode == mode
        && receipt.schema == EVALUATION_RECEIPT_SCHEMA
        && receipt.workload == frozen_workload_identity(config.documents)
        && receipt.workload.schema == FROZEN_WORKLOAD_SCHEMA
        && receipt.semantic.schema == SEMANTIC_SCHEMA
        && receipt.batch_rows == config.batch_rows
        && receipt.build == *expected_build
        && receipt.executable_sha256.as_deref() == Some(expected_executable_sha256)
        && receipt.trial_index.is_none()
        && receipt.order_position.is_none()
        && !receipt.sqlite_accessed
        && !receipt.production_write;
    let mode_valid = match mode {
        EvaluationMode::ArrowRecordBatch => {
            receipt.arrow_record_batches.is_some()
                && receipt.arrow_schema_fingerprints.as_ref() == Some(&arrow_schema_fingerprints())
        }
        EvaluationMode::FullVec | EvaluationMode::NativeChunk => {
            receipt.arrow_record_batches.is_none() && receipt.arrow_schema_fingerprints.is_none()
        }
    };
    if common_valid && mode_valid && validate_evaluation_receipt(receipt).is_ok() {
        return Ok(());
    }
    Err(io::Error::new(
        io::ErrorKind::InvalidData,
        format!(
            "child receipt contract mismatch for mode {}; expected schema {EVALUATION_RECEIPT_SCHEMA}, workload {FROZEN_WORKLOAD_SCHEMA}, semantic {SEMANTIC_SCHEMA}, Arrow contract {ARROW_SCHEMA_CONTRACT}",
            mode_arg(mode)
        ),
    ))
}

fn runtime_source_identity(
    build: &BuildIdentity,
    verify_tracked_source: bool,
) -> Result<RuntimeSourceIdentity, Box<dyn Error>> {
    let repository = repository_root()?;
    let revision = git_text(&repository, &["rev-parse", "HEAD"])
        .filter(|value| is_lower_hex(value, 40))
        .unwrap_or_else(|| "UNBOUND".to_string());
    let tree_clean = git_text(
        &repository,
        &["status", "--porcelain=v1", "--untracked-files=all"],
    )
    .is_some_and(|value| value.is_empty());
    let cargo_lock_sha256 = sha256_file(Path::new(env!("CARGO_MANIFEST_DIR")).join("Cargo.lock"))?;
    let tracked_source_sha256 = if verify_tracked_source {
        sha256_git_index(&repository)?
    } else {
        "NOT_CHECKED_DIAGNOSTIC".to_string()
    };
    let build_matches_runtime = verify_tracked_source
        && tree_clean
        && build.tree_clean
        && build.profile == "release"
        && revision == build.revision
        && cargo_lock_sha256 == build.cargo_lock_sha256
        && tracked_source_sha256 == build.tracked_source_sha256
        && is_lower_hex(&revision, 40)
        && is_lower_hex(&cargo_lock_sha256, 64)
        && is_lower_hex(&tracked_source_sha256, 64);
    Ok(RuntimeSourceIdentity {
        revision,
        tree_clean,
        cargo_lock_sha256,
        tracked_source_sha256,
        build_matches_runtime,
    })
}

fn repository_root() -> Result<PathBuf, io::Error> {
    Path::new(env!("CARGO_MANIFEST_DIR"))
        .join("../../..")
        .canonicalize()
}

fn git_text(repository: &Path, args: &[&str]) -> Option<String> {
    let output = ProcessCommand::new("git")
        .arg("-C")
        .arg(repository)
        .args(args)
        .output()
        .ok()?;
    if !output.status.success() {
        return None;
    }
    String::from_utf8(output.stdout)
        .ok()
        .map(|value| value.trim().to_string())
}

fn sha256_file(path: impl AsRef<Path>) -> Result<String, io::Error> {
    let mut file = File::open(path)?;
    let mut hasher = Sha256::new();
    let mut buffer = [0_u8; 64 * 1024];
    loop {
        let read = file.read(&mut buffer)?;
        if read == 0 {
            break;
        }
        hasher.update(&buffer[..read]);
    }
    Ok(format!("{:x}", hasher.finalize()))
}

fn sha256_git_index(repository: &Path) -> Result<String, io::Error> {
    let output = ProcessCommand::new("git")
        .arg("-C")
        .arg(repository)
        .args(["ls-files", "-s", "-z"])
        .output()?;
    if !output.status.success() || output.stdout.is_empty() {
        return Err(io::Error::other(format!(
            "git ls-files -s failed with {}",
            output.status
        )));
    }
    let mut hasher = Sha256::new();
    hasher.update(output.stdout);
    Ok(format!("{:x}", hasher.finalize()))
}

fn is_lower_hex(value: &str, expected_len: usize) -> bool {
    value.len() == expected_len
        && value
            .bytes()
            .all(|byte| byte.is_ascii_digit() || (b'a'..=b'f').contains(&byte))
}

fn canonical_build_ready(build: &BuildIdentity) -> bool {
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

fn mode_arg(mode: EvaluationMode) -> &'static str {
    match mode {
        EvaluationMode::FullVec => "full-vec",
        EvaluationMode::NativeChunk => "native-chunk",
        EvaluationMode::ArrowRecordBatch => "arrow-record-batch",
    }
}

fn percent_to_basis_points(percent: u32) -> Result<i64, io::Error> {
    let value = i64::from(percent)
        .checked_mul(100)
        .ok_or_else(|| invalid_input("percentage overflows basis points"))?;
    Ok(value)
}

fn invalid_input(message: &str) -> io::Error {
    io::Error::new(io::ErrorKind::InvalidInput, message)
}

fn environment_receipt() -> EnvironmentReceipt {
    EnvironmentReceipt {
        target_os: std::env::consts::OS.to_string(),
        target_arch: std::env::consts::ARCH.to_string(),
        kernel_release: read_trimmed("/proc/sys/kernel/osrelease"),
        cpu_model: linux_cpu_model(),
        logical_cpus: std::thread::available_parallelism()
            .ok()
            .map(|value| value.get()),
        total_memory_kib: linux_total_memory_kib(),
    }
}

fn read_trimmed(path: &str) -> Option<String> {
    let value = std::fs::read_to_string(path).ok()?;
    let trimmed = value.trim();
    (!trimmed.is_empty()).then(|| trimmed.to_string())
}

fn linux_cpu_model() -> Option<String> {
    let cpuinfo = std::fs::read_to_string("/proc/cpuinfo").ok()?;
    cpuinfo.lines().find_map(|line| {
        let (key, value) = line.split_once(':')?;
        (key.trim() == "model name")
            .then(|| value.trim().to_string())
            .filter(|value| !value.is_empty())
    })
}

fn linux_total_memory_kib() -> Option<u64> {
    let meminfo = std::fs::read_to_string("/proc/meminfo").ok()?;
    let line = meminfo.lines().find(|line| line.starts_with("MemTotal:"))?;
    line.split_whitespace().nth(1)?.parse().ok()
}
