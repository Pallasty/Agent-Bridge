use std::process::Command;

use ab_codebase_arrow_a0::{
    AssessmentStatus, EvaluationMode, EvaluationReceipt, EvidenceClass, Recommendation,
    SuiteReceipt, SEMANTIC_SCHEMA,
};

#[test]
fn run_subcommand_emits_one_machine_readable_receipt() {
    let output = Command::new(env!("CARGO_BIN_EXE_ab-codebase-arrow-a0"))
        .args([
            "run",
            "--mode",
            "native-chunk",
            "--documents",
            "8",
            "--batch-rows",
            "3",
        ])
        .output()
        .unwrap();

    assert!(output.status.success(), "{:?}", output);
    assert!(output.stderr.is_empty(), "{:?}", output);
    let receipt: EvaluationReceipt = serde_json::from_slice(&output.stdout).unwrap();
    assert_eq!(receipt.mode, EvaluationMode::NativeChunk);
    assert!(!receipt.build.revision.is_empty());
    assert!(!receipt.build.profile.is_empty());
    assert_eq!(receipt.semantic.schema, SEMANTIC_SCHEMA);
    assert!(receipt.max_accumulator_rows <= 3);
    assert!(!receipt.sqlite_accessed);
    assert!(!receipt.production_write);
}

#[test]
fn suite_subcommand_runs_each_mode_in_a_fresh_process() {
    let output = Command::new(env!("CARGO_BIN_EXE_ab-codebase-arrow-a0"))
        .args([
            "diagnostic-suite",
            "--documents",
            "12",
            "--batch-rows",
            "4",
            "--trials",
            "1",
        ])
        .output()
        .unwrap();

    assert!(output.status.success(), "{:?}", output);
    assert!(output.stderr.is_empty(), "{:?}", output);
    let receipt: SuiteReceipt = serde_json::from_slice(&output.stdout).unwrap();
    assert_eq!(receipt.receipts.len(), 3);
    assert_eq!(receipt.evidence_class, EvidenceClass::Diagnostic);
    assert!(receipt.fresh_process_per_trial);
    assert!(receipt.assessment.semantic_equivalent);
    assert_eq!(receipt.assessment.evidence_class, EvidenceClass::Diagnostic);
    assert!(receipt.assessment.measurement_complete);
    assert!(!receipt.assessment.evidence_complete);
    assert_eq!(receipt.assessment.status, AssessmentStatus::DiagnosticOnly);
    assert_eq!(
        receipt.assessment.recommendation,
        Recommendation::NoCandidate
    );
    assert!(!receipt.assessment.native_chunk.eligible);
    assert!(!receipt.assessment.arrow_record_batch.eligible);
    assert!(receipt
        .receipts
        .iter()
        .all(|row| row.build == receipt.build));
    assert!(receipt
        .receipts
        .iter()
        .all(|row| row.trial_index == Some(0) && row.order_position.is_some()));
}

#[test]
fn canonical_suite_fails_closed_for_a_dirty_debug_build() {
    let output = Command::new(env!("CARGO_BIN_EXE_ab-codebase-arrow-a0"))
        .arg("suite")
        .output()
        .unwrap();

    assert!(!output.status.success(), "{:?}", output);
    assert!(output.stdout.is_empty(), "{:?}", output);
    assert!(
        String::from_utf8_lossy(&output.stderr).contains("clean release build"),
        "{:?}",
        output
    );
}
