use ab_codebase_arrow_a0::{
    arrow_schema_fingerprints, arrow_schemas, assess_trials, evaluate_frozen_workload,
    frozen_workload_identity, validate_evaluation_receipt, AssessmentContext, AssessmentStatus,
    BuildIdentity, EvaluationConfig, EvaluationError, EvaluationMode, EvidenceClass,
    PromotionThresholds, Recommendation, ARROW_SCHEMA_CONTRACT, CANONICAL_BATCH_ROWS,
    CANONICAL_DOCUMENTS, CANONICAL_TRIALS_PER_MODE, EMPTY_SHA256,
};

fn bind_test_receipt(
    receipt: &mut ab_codebase_arrow_a0::EvaluationReceipt,
    trial_index: usize,
    order_position: usize,
) {
    receipt.build = BuildIdentity {
        revision: "a".repeat(40),
        tree_clean: true,
        profile: "release".to_string(),
        cargo_lock_sha256: "b".repeat(64),
        tracked_source_sha256: "c".repeat(64),
        target: "x86_64-unknown-linux-gnu".to_string(),
        opt_level: "3".to_string(),
        debug_assertions: false,
        encoded_rustflags_sha256: EMPTY_SHA256.to_string(),
        profile_overrides_present: false,
        rustc_version: "rustc 1.85.0 (test)".to_string(),
    };
    receipt.executable_sha256 = Some("d".repeat(64));
    receipt.trial_index = Some(trial_index);
    receipt.order_position = Some(order_position);
}

fn diagnostic_context() -> AssessmentContext {
    AssessmentContext {
        evidence_class: EvidenceClass::Diagnostic,
        runtime_source_bound: true,
        executable_sha256_bound: true,
        runtime_identity_stable: true,
    }
}

#[test]
fn three_paths_preserve_exact_codebase_index_semantics() {
    let config = EvaluationConfig {
        documents: 32,
        batch_rows: 7,
    };

    let full = evaluate_frozen_workload(EvaluationMode::FullVec, config).unwrap();
    let native = evaluate_frozen_workload(EvaluationMode::NativeChunk, config).unwrap();
    let arrow = evaluate_frozen_workload(EvaluationMode::ArrowRecordBatch, config).unwrap();

    assert_eq!(full.semantic, native.semantic);
    assert_eq!(full.semantic, arrow.semantic);
}

#[test]
fn native_chunk_wins_when_arrow_misses_the_elapsed_gate() {
    let config = EvaluationConfig {
        documents: 8,
        batch_rows: 5,
    };
    let mut full = evaluate_frozen_workload(EvaluationMode::FullVec, config).unwrap();
    let mut native = evaluate_frozen_workload(EvaluationMode::NativeChunk, config).unwrap();
    let mut arrow = evaluate_frozen_workload(EvaluationMode::ArrowRecordBatch, config).unwrap();

    bind_test_receipt(&mut full, 0, 0);
    bind_test_receipt(&mut native, 0, 1);
    bind_test_receipt(&mut arrow, 0, 2);
    full.peak_rss_kib = Some(1_000);
    full.elapsed_ns = 100;
    native.peak_rss_kib = Some(600);
    native.elapsed_ns = 105;
    arrow.peak_rss_kib = Some(650);
    arrow.elapsed_ns = 120;

    let assessment = assess_trials(
        &[full, native, arrow],
        PromotionThresholds::default(),
        diagnostic_context(),
    )
    .unwrap();

    assert!(assessment.semantic_equivalent);
    assert!(assessment.measurement_complete);
    assert!(assessment.native_chunk.resource_gates_passed);
    assert!(!assessment.native_chunk.eligible);
    assert!(!assessment.arrow_record_batch.eligible);
    assert!(!assessment.arrow_incremental_value);
    assert_eq!(assessment.recommendation, Recommendation::NoCandidate);
    assert_eq!(assessment.status, AssessmentStatus::DiagnosticOnly);
}

#[test]
fn bounded_paths_respect_one_shared_typed_accumulator_limit() {
    for batch_rows in [1, 2, 7, 64] {
        let config = EvaluationConfig {
            documents: 17,
            batch_rows,
        };
        let full = evaluate_frozen_workload(EvaluationMode::FullVec, config).unwrap();
        let native = evaluate_frozen_workload(EvaluationMode::NativeChunk, config).unwrap();
        let arrow = evaluate_frozen_workload(EvaluationMode::ArrowRecordBatch, config).unwrap();
        validate_evaluation_receipt(&full).unwrap();
        validate_evaluation_receipt(&native).unwrap();
        validate_evaluation_receipt(&arrow).unwrap();
        let total_rows = full.semantic.counts.total() as usize;
        let expected_batches = total_rows.div_ceil(batch_rows) as u64;

        assert_eq!(full.max_estimated_live_rows, total_rows);
        assert!(native.max_accumulator_rows <= batch_rows);
        assert!(arrow.max_accumulator_rows <= batch_rows);
        assert!(native.max_estimated_live_rows <= native.declared_live_row_bound);
        assert!(arrow.max_estimated_live_rows <= arrow.declared_live_row_bound);
        assert_eq!(native.emitted_flushes, expected_batches);
        assert_eq!(arrow.emitted_flushes, expected_batches);
        assert_eq!(
            native.max_extractor_output_rows,
            arrow.max_extractor_output_rows
        );
        assert!(native.max_extractor_output_rows > 0);
        assert_eq!(
            native.declared_live_row_bound,
            batch_rows + native.max_extractor_output_rows - 1
        );
        assert_eq!(
            arrow.declared_live_row_bound,
            2 * batch_rows + arrow.max_extractor_output_rows - 1
        );
        assert!(native.arrow_record_batches.is_none());
        assert!(native.max_arrow_batch_rows.is_none());
        assert!(native.arrow_schema_fingerprints.is_none());
        assert!(arrow
            .arrow_record_batches
            .as_ref()
            .is_some_and(|counts| counts.total() >= arrow.emitted_flushes));
        assert_eq!(
            arrow.arrow_schema_fingerprints,
            Some(arrow_schema_fingerprints())
        );
        assert!(arrow
            .max_arrow_batch_rows
            .is_some_and(|rows| rows > 0 && rows <= batch_rows));
    }
}

#[test]
fn frozen_fixture_and_three_table_contract_match_golden_digests() {
    let config = EvaluationConfig {
        documents: 4,
        batch_rows: 7,
    };
    let receipt = evaluate_frozen_workload(EvaluationMode::ArrowRecordBatch, config).unwrap();

    assert_eq!(
        frozen_workload_identity(4).manifest_sha256,
        "30131e41445986a6db0e635212ed0af6f5027e9c9bad8a826615042abd387eb8"
    );
    assert_eq!(receipt.semantic.counts.symbols, 20);
    assert_eq!(receipt.semantic.counts.imports, 9);
    assert_eq!(receipt.semantic.counts.calls, 27);
    assert_eq!(
        receipt.semantic.symbols_sha256,
        "df0954e8a117833e694742b0aaf2fd57bef6475ce2d6d9d16c2a119eba7e782a"
    );
    assert_eq!(
        receipt.semantic.imports_sha256,
        "e2ef88eb9f6064d670aa4a92948e665ad2eddda8cd97f5cb910c34699aa920de"
    );
    assert_eq!(
        receipt.semantic.calls_sha256,
        "200368c3bb4c75c67734459559e7a9c5ec7426a1da65f45d6b741e9d349c8df0"
    );
    assert_eq!(
        receipt.semantic.combined_sha256,
        "dece676cca475b92f9a9abcfe7bfd682557059cc9ac460bcd3380d1a64bb522e"
    );
    let fingerprints = receipt.arrow_schema_fingerprints.unwrap();
    assert_eq!(
        fingerprints.symbols_sha256,
        "d2e58dd3b51cbc07961f8030047f714da4d7c188bbcdfd1aa87ee37a1b70daca"
    );
    assert_eq!(
        fingerprints.imports_sha256,
        "14edf86e7ab3fa80069a8e80a37a53ef4936311fe1a66c826e386029220f093c"
    );
    assert_eq!(
        fingerprints.calls_sha256,
        "2177a1bcf398af49659becb03d682d2b2fa869ff8524cdd1faf19e570eda70e4"
    );
    assert_eq!(
        fingerprints.combined_sha256,
        "76db54f5f3a2938c88aa6a82b378503d5919293a08d24c4ff5e7297e78f84cda"
    );
}

#[test]
fn receipt_contract_rejects_relabelled_small_run() {
    let mut receipt = evaluate_frozen_workload(
        EvaluationMode::NativeChunk,
        EvaluationConfig {
            documents: 4,
            batch_rows: 3,
        },
    )
    .unwrap();
    receipt.workload = frozen_workload_identity(CANONICAL_DOCUMENTS);
    receipt.batch_rows = CANONICAL_BATCH_ROWS;

    assert!(validate_evaluation_receipt(&receipt).is_err());
}

#[test]
fn invalid_workload_and_batch_bounds_fail_closed() {
    assert!(matches!(
        evaluate_frozen_workload(
            EvaluationMode::FullVec,
            EvaluationConfig {
                documents: 0,
                batch_rows: 1,
            },
        ),
        Err(EvaluationError::EmptyWorkload)
    ));
    assert!(matches!(
        evaluate_frozen_workload(
            EvaluationMode::NativeChunk,
            EvaluationConfig {
                documents: 1,
                batch_rows: 0,
            },
        ),
        Err(EvaluationError::EmptyBatch)
    ));
}

#[test]
fn arrow_schema_contract_is_explicit_and_stable() {
    let schemas = arrow_schemas();
    assert!(std::ptr::eq(schemas, arrow_schemas()));
    let symbol_names: Vec<_> = schemas
        .symbols
        .fields()
        .iter()
        .map(|field| field.name())
        .collect();
    let import_names: Vec<_> = schemas
        .imports
        .fields()
        .iter()
        .map(|field| field.name())
        .collect();
    let call_names: Vec<_> = schemas
        .calls
        .fields()
        .iter()
        .map(|field| field.name())
        .collect();
    assert_eq!(
        symbol_names,
        [
            "file_path",
            "line",
            "col",
            "kind",
            "name",
            "signature",
            "language",
            "score",
        ]
    );
    assert_eq!(
        import_names,
        ["file_path", "line", "language", "raw", "target", "alias"]
    );
    assert_eq!(
        call_names,
        ["file_path", "line", "language", "caller", "callee"]
    );
    for (schema, table) in [
        (&schemas.symbols, "symbols"),
        (&schemas.imports, "imports"),
        (&schemas.calls, "calls"),
    ] {
        assert_eq!(
            schema
                .metadata()
                .get("ab.schema_contract")
                .map(String::as_str),
            Some(ARROW_SCHEMA_CONTRACT)
        );
        assert_eq!(
            schema
                .metadata()
                .get("ab.logical_table")
                .map(String::as_str),
            Some(table)
        );
    }
}

#[test]
fn unbound_source_revision_invalidates_promotion_evidence() {
    let config = EvaluationConfig {
        documents: 4,
        batch_rows: 3,
    };
    let mut receipts = Vec::new();
    for mode in [
        EvaluationMode::FullVec,
        EvaluationMode::NativeChunk,
        EvaluationMode::ArrowRecordBatch,
    ] {
        let mut receipt = evaluate_frozen_workload(mode, config).unwrap();
        receipt.build = BuildIdentity {
            revision: "UNBOUND".to_string(),
            tree_clean: false,
            profile: "debug".to_string(),
            cargo_lock_sha256: "UNBOUND".to_string(),
            tracked_source_sha256: "UNBOUND".to_string(),
            target: "x86_64-unknown-linux-gnu".to_string(),
            opt_level: "0".to_string(),
            debug_assertions: true,
            encoded_rustflags_sha256: EMPTY_SHA256.to_string(),
            profile_overrides_present: false,
            rustc_version: "rustc 1.85.0 (test)".to_string(),
        };
        receipt.executable_sha256 = Some("d".repeat(64));
        receipt.trial_index = Some(0);
        receipt.order_position = Some(receipts.len());
        receipt.peak_rss_kib = Some(match mode {
            EvaluationMode::FullVec => 1_000,
            EvaluationMode::NativeChunk => 600,
            EvaluationMode::ArrowRecordBatch => 500,
        });
        receipt.elapsed_ns = 100;
        receipts.push(receipt);
    }

    let assessment = assess_trials(
        &receipts,
        PromotionThresholds::default(),
        AssessmentContext {
            evidence_class: EvidenceClass::CanonicalPromotion,
            runtime_source_bound: false,
            executable_sha256_bound: false,
            runtime_identity_stable: false,
        },
    )
    .unwrap();
    assert!(!assessment.evidence_complete);
    assert_eq!(assessment.status, AssessmentStatus::InvalidEvidence);
    assert_eq!(assessment.recommendation, Recommendation::NoCandidate);
}

#[test]
fn canonical_promotion_rejects_noncanonical_scale_and_single_trial() {
    let config = EvaluationConfig {
        documents: 8,
        batch_rows: 5,
    };
    let mut receipts = Vec::new();
    for (position, mode) in [
        EvaluationMode::FullVec,
        EvaluationMode::NativeChunk,
        EvaluationMode::ArrowRecordBatch,
    ]
    .into_iter()
    .enumerate()
    {
        let mut receipt = evaluate_frozen_workload(mode, config).unwrap();
        bind_test_receipt(&mut receipt, 0, position);
        receipt.peak_rss_kib = Some(match mode {
            EvaluationMode::FullVec => 1_000,
            EvaluationMode::NativeChunk => 600,
            EvaluationMode::ArrowRecordBatch => 500,
        });
        receipt.elapsed_ns = 100;
        receipts.push(receipt);
    }

    let assessment = assess_trials(
        &receipts,
        PromotionThresholds::default(),
        AssessmentContext {
            evidence_class: EvidenceClass::CanonicalPromotion,
            runtime_source_bound: true,
            executable_sha256_bound: true,
            runtime_identity_stable: true,
        },
    )
    .unwrap();

    assert!(!assessment.canonical_config);
    assert!(!assessment.canonical_trial_plan);
    assert!(!assessment.evidence_complete);
    assert_eq!(assessment.status, AssessmentStatus::InvalidEvidence);
    assert_eq!(assessment.recommendation, Recommendation::NoCandidate);
}

#[test]
fn canonical_stability_requires_seven_of_nine_paired_passes() {
    let receipts = synthetic_canonical_receipts(9, 6);
    let assessment = assess_trials(
        &receipts,
        PromotionThresholds::default(),
        AssessmentContext {
            evidence_class: EvidenceClass::CanonicalPromotion,
            runtime_source_bound: true,
            executable_sha256_bound: true,
            runtime_identity_stable: true,
        },
    )
    .unwrap();

    assert!(assessment.canonical_config);
    assert!(assessment.canonical_trial_plan);
    assert!(assessment.evidence_complete);
    assert_eq!(assessment.native_chunk.paired_gate_passes, 9);
    assert_eq!(assessment.arrow_record_batch.paired_gate_passes, 6);
    assert!(assessment.native_chunk.stable);
    assert!(!assessment.arrow_record_batch.stable);
    assert!(assessment.native_chunk.eligible);
    assert!(!assessment.arrow_record_batch.eligible);
    assert_eq!(assessment.recommendation, Recommendation::NativeChunk);
    assert_eq!(assessment.status, AssessmentStatus::NativeChunkPreferred);
}

#[test]
fn arrow_is_selected_when_it_is_the_only_stable_eligible_candidate() {
    let receipts = synthetic_canonical_receipts(6, 7);
    let assessment = assess_trials(
        &receipts,
        PromotionThresholds::default(),
        AssessmentContext {
            evidence_class: EvidenceClass::CanonicalPromotion,
            runtime_source_bound: true,
            executable_sha256_bound: true,
            runtime_identity_stable: true,
        },
    )
    .unwrap();

    assert!(!assessment.native_chunk.stable);
    assert!(assessment.arrow_record_batch.stable);
    assert!(assessment.arrow_record_batch.eligible);
    assert!(assessment.arrow_incremental_value);
    assert_eq!(assessment.recommendation, Recommendation::ArrowRecordBatch);
    assert_eq!(assessment.status, AssessmentStatus::ArrowAdoptCandidate);
}

#[test]
fn canonical_thresholds_cannot_be_relaxed_by_the_pure_assessor() {
    let receipts = synthetic_canonical_receipts(9, 9);
    let assessment = assess_trials(
        &receipts,
        PromotionThresholds {
            min_rss_reduction_basis_points: 2_999,
            max_elapsed_regression_basis_points: 1_000,
        },
        AssessmentContext {
            evidence_class: EvidenceClass::CanonicalPromotion,
            runtime_source_bound: true,
            executable_sha256_bound: true,
            runtime_identity_stable: true,
        },
    )
    .unwrap();

    assert!(assessment.measurement_complete);
    assert!(!assessment.canonical_thresholds);
    assert!(!assessment.evidence_complete);
    assert_eq!(assessment.recommendation, Recommendation::NoCandidate);
    assert_eq!(assessment.status, AssessmentStatus::InvalidEvidence);
}

#[test]
fn sub_five_percent_arrow_advantage_defaults_to_native() {
    let mut receipts = synthetic_canonical_receipts(9, 9);
    for receipt in &mut receipts {
        if receipt.mode == EvaluationMode::ArrowRecordBatch {
            receipt.peak_rss_kib = Some(599);
            receipt.elapsed_ns = 105;
        }
    }
    let assessment = canonical_assessment(&receipts);

    assert!(assessment.native_chunk.eligible);
    assert!(assessment.arrow_record_batch.eligible);
    assert_eq!(assessment.arrow_vs_native_paired_value_passes, 0);
    assert!(!assessment.arrow_incremental_value);
    assert_eq!(assessment.recommendation, Recommendation::NativeChunk);
}

#[test]
fn material_arrow_advantage_must_repeat_in_seven_paired_trials() {
    let mut receipts = synthetic_canonical_receipts(9, 9);
    for receipt in &mut receipts {
        if receipt.mode == EvaluationMode::ArrowRecordBatch {
            receipt.peak_rss_kib = Some(if receipt.trial_index.unwrap() < 7 {
                570
            } else {
                590
            });
            receipt.elapsed_ns = 105;
        }
    }
    let assessment = canonical_assessment(&receipts);

    assert_eq!(assessment.arrow_vs_native_paired_value_passes, 7);
    assert!(assessment.arrow_incremental_value);
    assert_eq!(assessment.recommendation, Recommendation::ArrowRecordBatch);
}

fn canonical_assessment(
    receipts: &[ab_codebase_arrow_a0::EvaluationReceipt],
) -> ab_codebase_arrow_a0::SuiteAssessment {
    assess_trials(
        receipts,
        PromotionThresholds::default(),
        AssessmentContext {
            evidence_class: EvidenceClass::CanonicalPromotion,
            runtime_source_bound: true,
            executable_sha256_bound: true,
            runtime_identity_stable: true,
        },
    )
    .unwrap()
}

fn synthetic_canonical_receipts(
    native_paired_passes: usize,
    arrow_paired_passes: usize,
) -> Vec<ab_codebase_arrow_a0::EvaluationReceipt> {
    let seed_config = EvaluationConfig {
        documents: 4,
        batch_rows: 3,
    };
    let canonical_workload = frozen_workload_identity(CANONICAL_DOCUMENTS);
    let total_rows = 1_400_000;
    let emitted_flushes = 342;
    let max_extractor_output_rows = 18;
    let modes = [
        EvaluationMode::FullVec,
        EvaluationMode::NativeChunk,
        EvaluationMode::ArrowRecordBatch,
    ];
    let mut receipts = Vec::with_capacity(CANONICAL_TRIALS_PER_MODE * modes.len());

    for trial_index in 0..CANONICAL_TRIALS_PER_MODE {
        for order_position in 0..modes.len() {
            let mode = modes[(trial_index + order_position) % modes.len()];
            let mut receipt = evaluate_frozen_workload(mode, seed_config).unwrap();
            receipt.workload = canonical_workload.clone();
            receipt.semantic.counts.symbols = 500_000;
            receipt.semantic.counts.imports = 225_000;
            receipt.semantic.counts.calls = 675_000;
            receipt.batch_rows = CANONICAL_BATCH_ROWS;
            receipt.max_extractor_output_rows = max_extractor_output_rows;
            match mode {
                EvaluationMode::FullVec => {
                    receipt.emitted_flushes = 1;
                    receipt.max_accumulator_rows = total_rows;
                    receipt.max_estimated_live_rows = total_rows;
                    receipt.declared_live_row_bound = total_rows;
                    receipt.arrow_record_batches = None;
                    receipt.max_arrow_batch_rows = None;
                    receipt.arrow_schema_fingerprints = None;
                }
                EvaluationMode::NativeChunk => {
                    receipt.emitted_flushes = emitted_flushes;
                    receipt.max_accumulator_rows = CANONICAL_BATCH_ROWS;
                    receipt.max_estimated_live_rows = 4_113;
                    receipt.declared_live_row_bound = 4_113;
                    receipt.arrow_record_batches = None;
                    receipt.max_arrow_batch_rows = None;
                    receipt.arrow_schema_fingerprints = None;
                }
                EvaluationMode::ArrowRecordBatch => {
                    receipt.emitted_flushes = emitted_flushes;
                    receipt.max_accumulator_rows = CANONICAL_BATCH_ROWS;
                    receipt.max_estimated_live_rows = 8_209;
                    receipt.declared_live_row_bound = 8_209;
                    receipt.arrow_record_batches = Some(ab_codebase_arrow_a0::ArrowBatchCounts {
                        symbols: 123,
                        imports: 55,
                        calls: 165,
                    });
                    receipt.max_arrow_batch_rows = Some(CANONICAL_BATCH_ROWS);
                    receipt.arrow_schema_fingerprints = Some(arrow_schema_fingerprints());
                }
            }
            bind_test_receipt(&mut receipt, trial_index, order_position);
            receipt.elapsed_ns = match mode {
                EvaluationMode::FullVec => 100,
                EvaluationMode::NativeChunk | EvaluationMode::ArrowRecordBatch => 105,
            };
            receipt.peak_rss_kib = Some(match mode {
                EvaluationMode::FullVec => 1_000,
                EvaluationMode::NativeChunk if trial_index < native_paired_passes => 600,
                EvaluationMode::ArrowRecordBatch if trial_index < arrow_paired_passes => 600,
                EvaluationMode::NativeChunk | EvaluationMode::ArrowRecordBatch => 900,
            });
            receipts.push(receipt);
        }
    }
    receipts
}
