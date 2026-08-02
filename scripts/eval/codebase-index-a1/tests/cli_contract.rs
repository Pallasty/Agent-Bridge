use std::process::Command;

#[test]
fn diagnostic_runs_real_full_vec_and_staged_native_in_fresh_children() {
    let trial_root = tempfile::tempdir_in("/Data/CascadeProjects").unwrap();
    let output = Command::new(env!("CARGO_BIN_EXE_ab-codebase-index-a1"))
        .args([
            "diagnostic-suite",
            "--documents",
            "4",
            "--batch-rows",
            "7",
            "--pairs",
            "2",
            "--trial-root",
        ])
        .arg(trial_root.path())
        .output()
        .unwrap();
    assert!(
        output.status.success(),
        "stderr: {}",
        String::from_utf8_lossy(&output.stderr)
    );
    let receipt: serde_json::Value = serde_json::from_slice(&output.stdout).unwrap();
    assert_eq!(receipt["assessment"]["evidence_class"], "diagnostic");
    assert_eq!(
        receipt["assessment"]["evidence_valid"], true,
        "diagnostic reasons: {}",
        receipt["assessment"]["reasons"]
    );
    assert_eq!(receipt["assessment"]["eligible"], false);
    assert_eq!(receipt["assessment"]["decision_pass"], false);
    assert_eq!(receipt["suite_cleanup_succeeded"], true);
    assert_eq!(
        receipt["input"]["host_storage_context"]["live_substrate_is_canonical_gate"],
        false
    );
    assert_eq!(
        receipt["input"]["failure_atomicity"]
            .as_array()
            .unwrap()
            .len(),
        0
    );
    assert_eq!(receipt["input"]["pairs"].as_array().unwrap().len(), 2);
    let base_sha = &receipt["input"]["base_fixture_preflight"]["base_fixture_sha256"];
    let base_raw = &receipt["input"]["base_fixture_preflight"]["target_raw_sha256"];
    for pair in receipt["input"]["pairs"].as_array().unwrap() {
        assert_eq!(
            pair["full_vec"]["database"]["semantic_sha256"],
            pair["staged_native"]["database"]["semantic_sha256"]
        );
        assert_eq!(
            pair["staged_native"]["staged_native"]["staging_parent_was_explicit"],
            true
        );
        assert_eq!(
            &pair["full_vec"]["fixture"]["base_fixture_sha256"],
            base_sha
        );
        assert_eq!(
            &pair["staged_native"]["fixture"]["base_fixture_sha256"],
            base_sha
        );
        assert_eq!(
            &pair["full_vec"]["fixture"]["target_raw_sha256_before"],
            base_raw
        );
        assert_eq!(
            pair["full_vec"]["fixture"]["target_raw_sha256_after"],
            pair["staged_native"]["fixture"]["target_raw_sha256_after"]
        );
    }
}

#[test]
fn canonical_rejects_data_trial_root_before_workload_or_receipt_write() {
    let trial_root = tempfile::tempdir_in("/Data/CascadeProjects").unwrap();
    let receipt_path = trial_root.path().join("canonical.json");
    let output = Command::new(env!("CARGO_BIN_EXE_ab-codebase-index-a1"))
        .args(["canonical-suite", "--trial-root"])
        .arg(trial_root.path())
        .arg("--output")
        .arg(&receipt_path)
        .output()
        .unwrap();

    assert_eq!(output.status.code(), Some(1));
    assert!(output.stdout.is_empty());
    assert!(String::from_utf8_lossy(&output.stderr).contains("canonical preflight"));
    assert!(!receipt_path.exists());
}
