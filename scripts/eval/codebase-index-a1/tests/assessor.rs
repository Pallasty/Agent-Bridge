use ab_codebase_index_a1::{
    assess_suite, canonical_workload, AuthoritativePragmaEvidence, AuthorityEvidence,
    BaseFixturePreflightReceipt, BuildIdentity, ChildExecutionEvidence, DatabaseEvidence,
    EvidenceClass, FailureAtomicityReceipt, FailureCase, FixtureEvidence, FullVecEvidence,
    HostStorageContext, Measurement, Mode, PostFaultQueryEvidence, Provenance,
    RollbackStateEvidence, RunReceipt, RuntimeEnvironmentEvidence, StorageEvidence, SuiteInput,
    TrialOrder, TrialPair, WalResetEvidence, Workload, CANONICAL_BATCH_ROWS, CANONICAL_PAIRS,
    CANONICAL_TOTAL_ROWS,
};
use sha2::{Digest, Sha256};

const WAL_PAGE_SIZE: u64 = 4_096;
const WAL_FRAMES: u64 = 2_400;

fn wal_bytes(frames: u64) -> u64 {
    32 + frames * (24 + WAL_PAGE_SIZE)
}

fn sha256_json<T: serde::Serialize>(value: &T) -> String {
    let bytes = serde_json::to_vec(value).expect("test evidence must serialize");
    format!("{:x}", Sha256::digest(bytes))
}

fn identity(clean: bool) -> BuildIdentity {
    BuildIdentity {
        revision: "0123456789abcdef0123456789abcdef01234567".into(),
        tree_clean: clean,
        profile: "release".into(),
        cargo_lock_sha256: "a".repeat(64),
        tracked_source_sha256: "b".repeat(64),
        executable_sha256: Some("c".repeat(64)),
        target: "x86_64-unknown-linux-gnu".into(),
        opt_level: "3".into(),
        debug_assertions: false,
        encoded_rustflags_sha256:
            "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855".into(),
        profile_overrides_present: false,
        rustc_version: "rustc 1.85.0".into(),
        build_features: "staged-native".into(),
    }
}

fn provenance(clean: bool) -> Provenance {
    let build = identity(clean);
    Provenance {
        build: build.clone(),
        runtime_before: build.clone(),
        runtime_after: build,
    }
}

fn workload() -> Workload {
    canonical_workload()
}

fn runtime_environment() -> RuntimeEnvironmentEvidence {
    RuntimeEnvironmentEvidence {
        kernel_release: "6.14.0-test".into(),
        cpu_model: "Intel(R) Xeon(R) Gold 6138 CPU @ 2.00GHz".into(),
        cpu_microcode: "0x2007107".into(),
        process_affinity: "39".into(),
        canonical_cpu: 39,
        excluded_smt_sibling: 79,
        canonical_cpu_siblings: "39,79".into(),
        libc: "glibc 2.41".into(),
        allocator: "system".into(),
        systemd_version: "systemd 257".into(),
        loadavg: "0.10 0.20 0.30 1/100 1".into(),
        cpu_pressure: "some avg10=0.00".into(),
        memory_pressure: "some avg10=0.00".into(),
        io_pressure: "some avg10=0.00".into(),
    }
}

fn evidence(seed: usize) -> DatabaseEvidence {
    DatabaseEvidence {
        schema_sha256: Some("1".repeat(64)),
        semantic_sha256: Some(
            "c26dd0d5f2b3844113f1030128cbfad1506b81cec2d13b585649c5b4057a3099".into(),
        ),
        page_count: Some(50_000 + seed as u64),
        freelist_count: Some(0),
        wal_bytes: Some(wal_bytes(WAL_FRAMES)),
        database_bytes: Some(20_000_000),
        shm_bytes: Some(32_768),
        wal_frames: Some(WAL_FRAMES),
        wal_checkpoint_log_frames: Some(WAL_FRAMES),
        wal_checkpointed_frames: Some(WAL_FRAMES),
        wal_checkpoint_busy: Some(0),
        wal_layout_valid: Some(true),
        page_size: Some(WAL_PAGE_SIZE),
        journal_mode: Some("wal".into()),
        root_rows: Some(CANONICAL_TOTAL_ROWS),
        null_embeddings: Some(500_000),
        indexed_at_values: Some(1),
        sqlite_version: Some("3.50.2".into()),
        sqlite_compile_options_sha256: Some("3".repeat(64)),
        generation_sha256: Some("6".repeat(64)),
        integrity_check: Some("ok".into()),
        foreign_key_violations: Some(0),
        schema_meta_version: Some("57".into()),
        schema_meta_sha256: Some("9".repeat(64)),
        schema_version: Some(100),
        user_version: Some(0),
        synchronous: Some(2),
        wal_autocheckpoint: Some(1_000),
        cache_size: Some(-2_000),
        cache_spill: Some(483),
        temp_store: Some(0),
        mmap_size: Some(0),
        foreign_keys: Some(0),
        busy_timeout_ms: Some(5_000),
        locking_mode: Some("normal".into()),
    }
}

fn pragmas(trial_root: &str) -> AuthoritativePragmaEvidence {
    AuthoritativePragmaEvidence {
        journal_mode: "wal".into(),
        synchronous: 2,
        wal_autocheckpoint: 1_000,
        cache_size: -2_000,
        cache_spill: 483,
        temp_store: 0,
        mmap_size: 0,
        foreign_keys: 1,
        busy_timeout_ms: 5_000,
        locking_mode: "normal".into(),
        autocommit: true,
        database_names: vec!["main".into(), "temp".into()],
        database_files: vec![format!("{trial_root}/database/state.db").into(), "".into()],
    }
}

fn execution(mode: Mode, pair: usize) -> ChildExecutionEvidence {
    let first = if pair % 2 == 0 {
        Mode::FullVec
    } else {
        Mode::StagedNative
    };
    let position = usize::from(mode != first);
    let sequence = pair * 2 + position;
    let started_unix_ns = 10_000 + sequence as u64 * 10;
    ChildExecutionEvidence {
        mode,
        sequence,
        process_id: 1_000 + sequence as u32,
        started_unix_ns,
        finished_unix_ns: started_unix_ns + 5,
    }
}

fn run(mode: Mode, pair: usize) -> RunReceipt {
    let candidate = mode == Mode::StagedNative;
    let mode_name = if candidate {
        "staged-native"
    } else {
        "full-vec"
    };
    let trial_root =
        format!("/home/pallasting/eval/codebase-index-a1/trials/pair-{pair:02}-{mode_name}");
    let authoritative_pragmas = pragmas(&trial_root);
    RunReceipt {
        schema: "agent_bridge.codebase_index.a1.run_receipt.v0".into(),
        mode,
        execution: execution(mode, pair),
        build_identity: identity(true),
        workload: workload(),
        measurement: Measurement {
            elapsed_ns: Some(if candidate { 105 } else { 100 }),
            peak_rss_bytes: Some(if candidate { 69 } else { 100 }),
            vm_hwm_bytes: Some(if candidate { 68 } else { 99 }),
            authoritative_transaction_ns: Some(if candidate { 105 } else { 100 }),
            cgroup_path: Some(format!(
                "/user.slice/ab-codebase-index-a1-pair-{pair:02}-{mode_name}.service"
            )),
            cgroup_memory_current_before_bytes: Some(0),
            cgroup_memory_current_after_bytes: Some(if candidate { 67 } else { 100 }),
            cgroup_memory_peak_before_bytes: Some(0),
            cgroup_memory_peak_after_bytes: Some(if candidate { 69 } else { 100 }),
            cgroup_memory_max: Some("max".into()),
            cgroup_process_count: Some(1),
            cgroup_is_shared: Some(false),
            cgroup_isolated_for_trial: Some(true),
            cgroup_memory_anon_before_bytes: Some(0),
            cgroup_memory_anon_after_bytes: Some(if candidate { 40 } else { 60 }),
            cgroup_memory_file_before_bytes: Some(0),
            cgroup_memory_file_after_bytes: Some(if candidate { 20 } else { 30 }),
            cgroup_memory_shmem_before_bytes: Some(0),
            cgroup_memory_shmem_after_bytes: Some(if candidate { 7 } else { 10 }),
            cgroup_memory_anon_delta_bytes: Some(if candidate { 40 } else { 60 }),
            cgroup_memory_file_delta_bytes: Some(if candidate { 20 } else { 30 }),
            cgroup_memory_shmem_delta_bytes: Some(if candidate { 7 } else { 10 }),
            proc_io_read_bytes_before: Some(1),
            proc_io_read_bytes_after: Some(2),
            proc_io_write_bytes_before: Some(3),
            proc_io_write_bytes_after: Some(4),
            rusage_minor_faults_before: Some(5),
            rusage_minor_faults_after: Some(6),
            rusage_major_faults_before: Some(0),
            rusage_major_faults_after: Some(0),
            getrusage_max_rss_bytes: Some(if candidate { 69 } else { 100 }),
            parent_wait4_max_rss_bytes: Some(if candidate { 69 } else { 100 }),
        },
        database: evidence(pair),
        fixture: FixtureEvidence {
            base_fixture_sha256: "4".repeat(64),
            database_copy_sha256_before: "4".repeat(64),
            base_sidecars_absent_before: true,
            target_rows_before: CANONICAL_TOTAL_ROWS,
            target_nonnull_embeddings_before: 500_000,
            target_generation_sha256_before: "5".repeat(64),
            target_generation_sha256_after: "6".repeat(64),
            target_raw_sha256_before: "a".repeat(64),
            target_raw_sha256_after: "b".repeat(64),
            other_root_sha256_before: "7".repeat(64),
            other_root_sha256_after: "7".repeat(64),
            non_codebase_sentinel_sha256_before: "8".repeat(64),
            non_codebase_sentinel_sha256_after: "8".repeat(64),
        },
        authoritative_pragmas_before: authoritative_pragmas.clone(),
        authoritative_pragmas_after: authoritative_pragmas,
        wal_reset: WalResetEvidence {
            busy: 0,
            log_frames: 0,
            checkpointed_frames: 0,
            wal_bytes: 0,
            proven_empty: true,
        },
        storage: StorageEvidence {
            trial_root: trial_root.clone().into(),
            mount_point: Some("/home".into()),
            filesystem_type: Some("ext4".into()),
            trial_device: Some(1),
            database_device: Some(1),
            staging_device: candidate.then_some(1),
        },
        authority: AuthorityEvidence {
            isolated_sqlite_accessed: true,
            live_database_touched: false,
            production_write: false,
            runtime_adoption_authorized: false,
        },
        full_vec: (!candidate).then_some(FullVecEvidence {
            strategy: "full_vec".into(),
            extraction_and_accumulation_ns: 1,
            autocommit_before: true,
            autocommit_during: false,
            autocommit_after: true,
        }),
        staged_native: candidate.then_some(ab_codebase_index_a1::StagedNativeEvidence {
            strategy: "native_chunk_staged_v0".into(),
            batch_rows: CANONICAL_BATCH_ROWS,
            emitted_batches: 342,
            staging_file_bytes: 1,
            staging_file_path: format!("{trial_root}/staging/rows.sqlite3").into(),
            staging_file_device: 1,
            staging_file_mount_point: "/home".into(),
            staging_file_filesystem_type: "ext4".into(),
            declared_live_row_bound: 4_113,
            max_accumulator_rows: 4_096,
            max_extractor_output_rows: 18,
            staging_rows: CANONICAL_TOTAL_ROWS,
            staging_cleanup_succeeded: true,
            staging_transaction_committed: true,
            authoritative_transaction_committed: true,
            staging_parent_was_explicit: true,
            autocommit_before: true,
            autocommit_during: false,
            autocommit_after: true,
        }),
    }
}

fn rollback_state() -> RollbackStateEvidence {
    RollbackStateEvidence {
        target_raw_sha256: "a".repeat(64),
        other_root_sha256: "7".repeat(64),
        non_codebase_sentinel_sha256: "8".repeat(64),
        schema_sha256: "1".repeat(64),
        schema_meta_sha256: "9".repeat(64),
        schema_version: 100,
        user_version: 0,
        page_count: 50_000,
        freelist_count: 0,
        integrity_check: "ok".into(),
        foreign_key_violations: 0,
    }
}

fn base_fixture_preflight() -> BaseFixturePreflightReceipt {
    let mut database = evidence(0);
    database.null_embeddings = Some(0);
    database.generation_sha256 = Some("5".repeat(64));
    BaseFixturePreflightReceipt {
        schema: "agent_bridge.codebase_index.a1.base_preflight.v0".into(),
        build_identity: identity(true),
        runtime_environment: runtime_environment(),
        workload: workload(),
        base_fixture_sha256: "4".repeat(64),
        database_copy_sha256: "4".repeat(64),
        sidecars_absent: true,
        target_rows: CANONICAL_TOTAL_ROWS,
        target_nonnull_embeddings: 500_000,
        target_generation_sha256: "5".repeat(64),
        target_raw_sha256: "a".repeat(64),
        other_root_sha256: "7".repeat(64),
        non_codebase_sentinel_sha256: "8".repeat(64),
        database,
    }
}

fn canonical_input() -> SuiteInput {
    let pairs = (0..CANONICAL_PAIRS)
        .map(|pair| {
            let order = if pair % 2 == 0 {
                TrialOrder::Ab
            } else {
                TrialOrder::Ba
            };
            let full_vec = run(Mode::FullVec, pair);
            let staged_native = run(Mode::StagedNative, pair);
            let observed_execution = if order == TrialOrder::Ab {
                [full_vec.execution.clone(), staged_native.execution.clone()]
            } else {
                [staged_native.execution.clone(), full_vec.execution.clone()]
            };
            TrialPair {
                pair_index: pair,
                order,
                observed_order: order.modes(),
                observed_execution,
                full_vec,
                staged_native,
            }
        })
        .collect();
    let failure_atomicity = [
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
    .map(|case| {
        let trial_root = format!("/home/pallasting/eval/codebase-index-a1/fault-{case:?}");
        let authoritative_pragmas = pragmas(&trial_root);
        FailureAtomicityReceipt {
            case,
            build_identity: identity(true),
            expected_error_observed: true,
            expected_error_marker: case.expected_error_marker().into(),
            observed_error: format!("store failure: {}", case.expected_error_marker()),
            target_generation_sha256_before: "5".repeat(64),
            target_generation_sha256_after: "5".repeat(64),
            other_root_sha256_before: "7".repeat(64),
            other_root_sha256_after: "7".repeat(64),
            non_codebase_sentinel_sha256_before: "8".repeat(64),
            non_codebase_sentinel_sha256_after: "8".repeat(64),
            rollback_before: rollback_state(),
            rollback_after: rollback_state(),
            authoritative_pragmas_before: authoritative_pragmas.clone(),
            authoritative_pragmas_after: authoritative_pragmas.clone(),
            connection_usable_after: true,
            post_fault_query: PostFaultQueryEvidence {
                query: "codebase_index_pragmas_a1".into(),
                succeeded: true,
                result_sha256: sha256_json(&authoritative_pragmas),
            },
            staging_cleanup_succeeded: true,
            base_fixture_sha256: "4".repeat(64),
            database_copy_sha256_before: "4".repeat(64),
        }
    })
    .collect();
    SuiteInput {
        evidence_class: EvidenceClass::Canonical,
        provenance: provenance(true),
        runtime_environment: runtime_environment(),
        trial_root: Some("/home/pallasting/eval/codebase-index-a1".into()),
        cache_policy: "warm_shared_corpus_after_single_base_fixture".into(),
        host_storage_context: HostStorageContext {
            configured_default_db_path: "/home/pallasting/.local/share/agent-bridge/state.db"
                .into(),
            resolved_default_db_path: Some(
                "/Media/Ubuntu/Documents/.local/share/agent-bridge/state.db".into(),
            ),
            mount_point: Some("/Media/Ubuntu/Documents".into()),
            filesystem_type: Some("fuseblk".into()),
            device: Some(2_054),
            live_substrate_is_canonical_gate: false,
        },
        base_fixture_preflight: base_fixture_preflight(),
        pairs,
        failure_atomicity,
    }
}

#[test]
fn canonical_accepts_complete_balanced_threshold_passing_evidence() {
    let assessment = assess_suite(&canonical_input());
    assert!(assessment.eligible, "{:#?}", assessment.reasons);
    assert!(assessment.decision_pass);
    assert_eq!(assessment.passing_pairs, CANONICAL_PAIRS);
}

#[test]
fn diagnostic_is_never_promotable_even_when_measurements_pass() {
    let mut input = canonical_input();
    input.evidence_class = EvidenceClass::Diagnostic;
    input.provenance = provenance(false);
    let assessment = assess_suite(&input);
    assert!(!assessment.eligible);
    assert!(!assessment.decision_pass);
    assert!(assessment
        .reasons
        .iter()
        .any(|reason| reason.contains("diagnostic")));
}

#[test]
fn canonical_rejects_dirty_or_runtime_source_identity_drift() {
    let mut dirty = canonical_input();
    dirty.provenance.build.tree_clean = false;
    assert!(!assess_suite(&dirty).eligible);

    let mut drifted = canonical_input();
    drifted.provenance.runtime_after.tracked_source_sha256 = "d".repeat(64);
    let assessment = assess_suite(&drifted);
    assert!(!assessment.eligible);
    assert!(assessment
        .reasons
        .iter()
        .any(|reason| reason.contains("source identity")));
}

#[test]
fn canonical_rejects_missing_required_measurement_or_database_field() {
    let mut missing_rss = canonical_input();
    missing_rss.pairs[0].full_vec.measurement.peak_rss_bytes = None;
    assert!(!assess_suite(&missing_rss).eligible);

    let mut missing_wal = canonical_input();
    missing_wal.pairs[0].staged_native.database.wal_bytes = None;
    assert!(!assess_suite(&missing_wal).eligible);

    let mut missing_txn = canonical_input();
    missing_txn.pairs[0]
        .full_vec
        .measurement
        .authoritative_transaction_ns = None;
    assert!(!assess_suite(&missing_txn).eligible);

    let mut missing_cgroup = canonical_input();
    missing_cgroup.pairs[0].full_vec.measurement.cgroup_path = None;
    assert!(!assess_suite(&missing_cgroup).eligible);
}

#[test]
fn canonical_requires_exact_workload_and_five_five_ab_ba_balance() {
    let mut wrong_docs = canonical_input();
    wrong_docs.pairs[0].full_vec.workload.documents -= 1;
    assert!(!assess_suite(&wrong_docs).eligible);

    let mut unbalanced = canonical_input();
    unbalanced.pairs[1].order = TrialOrder::Ab;
    let assessment = assess_suite(&unbalanced);
    assert!(!assessment.eligible);
    assert!(assessment
        .reasons
        .iter()
        .any(|reason| reason.contains("AB/BA")));
}

#[test]
fn decision_uses_338_thresholds_and_requires_eight_passing_pairs() {
    let mut input = canonical_input();
    for pair in &mut input.pairs[0..3] {
        pair.staged_native.measurement.peak_rss_bytes = Some(71);
        pair.staged_native.measurement.getrusage_max_rss_bytes = Some(71);
        pair.staged_native
            .measurement
            .cgroup_memory_peak_after_bytes = Some(71);
    }
    let assessment = assess_suite(&input);
    assert!(assessment.eligible);
    assert!(!assessment.decision_pass);
    assert_eq!(assessment.passing_pairs, 7);

    let mut edge = canonical_input();
    edge.pairs[0].staged_native.measurement.peak_rss_bytes = Some(70);
    edge.pairs[0]
        .staged_native
        .measurement
        .getrusage_max_rss_bytes = Some(70);
    edge.pairs[0]
        .staged_native
        .measurement
        .cgroup_memory_peak_after_bytes = Some(70);
    edge.pairs[0].staged_native.measurement.elapsed_ns = Some(110);
    edge.pairs[0]
        .staged_native
        .measurement
        .authoritative_transaction_ns = Some(110);
    edge.pairs[0].staged_native.database.wal_frames = Some(2_520);
    edge.pairs[0]
        .staged_native
        .database
        .wal_checkpoint_log_frames = Some(2_520);
    edge.pairs[0].staged_native.database.wal_checkpointed_frames = Some(2_520);
    edge.pairs[0].staged_native.database.wal_bytes = Some(wal_bytes(2_520));
    assert!(assess_suite(&edge).decision_pass);

    let mut transaction_pairs = canonical_input();
    for pair in &mut transaction_pairs.pairs[0..3] {
        pair.staged_native.measurement.authoritative_transaction_ns = Some(121);
    }
    let assessment = assess_suite(&transaction_pairs);
    assert!(assessment.eligible);
    assert_eq!(assessment.transaction_passing_pairs, 7);
    assert!(!assessment.decision_pass);

    let mut wal_pairs = canonical_input();
    for pair in &mut wal_pairs.pairs[0..3] {
        pair.staged_native.database.wal_frames = Some(2_521);
        pair.staged_native.database.wal_checkpoint_log_frames = Some(2_521);
        pair.staged_native.database.wal_checkpointed_frames = Some(2_521);
        pair.staged_native.database.wal_bytes = Some(wal_bytes(2_521));
    }
    let assessment = assess_suite(&wal_pairs);
    assert!(assessment.eligible);
    assert_eq!(assessment.wal_passing_pairs, 7);
    assert!(!assessment.decision_pass);
}

#[test]
fn canonical_rejects_semantic_schema_page_or_freelist_divergence() {
    for mutate in 0..4 {
        let mut input = canonical_input();
        match mutate {
            0 => input.pairs[0].staged_native.database.semantic_sha256 = Some("9".repeat(64)),
            1 => input.pairs[0].staged_native.database.schema_sha256 = Some("9".repeat(64)),
            2 => input.pairs[0].staged_native.database.page_count = Some(7),
            _ => input.pairs[0].staged_native.database.freelist_count = Some(7),
        }
        assert!(!assess_suite(&input).eligible);
    }
}

#[test]
fn canonical_rejects_tmpfs_or_missing_mount_identity() {
    let mut tmpfs = canonical_input();
    tmpfs.pairs[0].staged_native.storage.filesystem_type = Some("tmpfs".into());
    assert!(!assess_suite(&tmpfs).eligible);

    let mut missing_mount = canonical_input();
    missing_mount.pairs[0].full_vec.storage.mount_point = None;
    assert!(!assess_suite(&missing_mount).eligible);
}

#[test]
fn canonical_rejects_missing_extended_runtime_and_sqlite_custody() {
    let mut missing_io = canonical_input();
    missing_io.pairs[0]
        .full_vec
        .measurement
        .proc_io_read_bytes_before = None;
    assert!(!assess_suite(&missing_io).eligible);

    let mut bad_integrity = canonical_input();
    bad_integrity.pairs[0]
        .staged_native
        .database
        .integrity_check = Some("corrupt".into());
    assert!(!assess_suite(&bad_integrity).eligible);

    let mut changed_sentinel = canonical_input();
    changed_sentinel.pairs[0]
        .staged_native
        .fixture
        .non_codebase_sentinel_sha256_after = "f".repeat(64);
    assert!(!assess_suite(&changed_sentinel).eligible);

    let mut missing_stage_shape = canonical_input();
    missing_stage_shape.pairs[0]
        .staged_native
        .staged_native
        .as_mut()
        .unwrap()
        .emitted_batches = 0;
    assert!(!assess_suite(&missing_stage_shape).eligible);
}

#[test]
fn paired_log_ratio_median_blocks_heteroscedastic_false_green() {
    let mut input = canonical_input();
    for (index, pair) in input.pairs.iter_mut().enumerate() {
        let (baseline, candidate) = if index < 5 {
            (100, 130)
        } else {
            (10_000, 10_900)
        };
        pair.full_vec.measurement.elapsed_ns = Some(baseline);
        pair.staged_native.measurement.elapsed_ns = Some(candidate);
    }

    // Independently sorting each population gives 5515 / 5050 = 1.092,
    // which would incorrectly pass the 1.10 threshold. The paired geometric
    // median is sqrt(1.30 * 1.09) = 1.190..., which must fail.
    let assessment = assess_suite(&input);
    assert!(assessment.eligible, "{:#?}", assessment.reasons);
    assert!(!assessment.median_elapsed_pass);
    assert!(!assessment.decision_pass);
}

#[test]
fn canonical_rejects_cache_accounting_cgroup_and_rss_false_wins() {
    let mut inconsistent_cache = canonical_input();
    inconsistent_cache.pairs[0]
        .staged_native
        .measurement
        .cgroup_memory_file_delta_bytes = Some(21);
    let assessment = assess_suite(&inconsistent_cache);
    assert!(!assessment.eligible);
    assert!(assessment
        .reasons
        .iter()
        .any(|reason| reason.contains("memory.stat deltas")));

    let mut hidden_cgroup_growth = canonical_input();
    for pair in &mut hidden_cgroup_growth.pairs[0..3] {
        pair.staged_native
            .measurement
            .cgroup_memory_peak_after_bytes = Some(106);
    }
    let assessment = assess_suite(&hidden_cgroup_growth);
    assert!(assessment.eligible, "{:#?}", assessment.reasons);
    assert_eq!(assessment.cgroup_passing_pairs, 7);
    assert!(!assessment.decision_pass);

    let mut inconsistent_rss = canonical_input();
    inconsistent_rss.pairs[0]
        .staged_native
        .measurement
        .peak_rss_bytes = Some(70);
    let assessment = assess_suite(&inconsistent_rss);
    assert!(!assessment.eligible);
    assert!(assessment
        .reasons
        .iter()
        .any(|reason| reason.contains("max(VmHWM,getrusage)")));

    let mut shared_cgroup = canonical_input();
    shared_cgroup.pairs[0]
        .full_vec
        .measurement
        .cgroup_process_count = Some(2);
    shared_cgroup.pairs[0].full_vec.measurement.cgroup_is_shared = Some(true);
    shared_cgroup.pairs[0]
        .full_vec
        .measurement
        .cgroup_isolated_for_trial = Some(false);
    assert!(!assess_suite(&shared_cgroup).eligible);
}

#[test]
fn canonical_rejects_fault_marker_raw_snapshot_and_global_base_sha_drift() {
    let mut wrong_marker = canonical_input();
    wrong_marker.failure_atomicity[0].expected_error_marker = "wrong marker".into();
    wrong_marker.failure_atomicity[0].observed_error = "wrong marker".into();
    assert!(!assess_suite(&wrong_marker).eligible);

    let mut changed_raw_rollback = canonical_input();
    changed_raw_rollback.failure_atomicity[1]
        .rollback_after
        .target_raw_sha256 = "e".repeat(64);
    assert!(!assess_suite(&changed_raw_rollback).eligible);

    let mut unbound_fault_copy = canonical_input();
    unbound_fault_copy.failure_atomicity[2].base_fixture_sha256 = "e".repeat(64);
    unbound_fault_copy.failure_atomicity[2].database_copy_sha256_before = "e".repeat(64);
    let assessment = assess_suite(&unbound_fault_copy);
    assert!(!assessment.eligible);
    assert!(assessment
        .reasons
        .iter()
        .any(|reason| reason.contains("20 performance plus 8 fault SHA custody")));

    let mut missing_case = canonical_input();
    missing_case.failure_atomicity.pop();
    assert!(!assess_suite(&missing_case).eligible);
}

fn assert_canonical_rejected(input: SuiteInput) {
    let assessment = assess_suite(&input);
    assert!(
        !assessment.eligible,
        "canonical counterexample was unexpectedly eligible: {:#?}",
        assessment
    );
    assert!(
        !assessment.decision_pass,
        "canonical counterexample unexpectedly passed: {:#?}",
        assessment
    );
}

#[test]
fn canonical_rejects_zero_authoritative_transaction_measurement() {
    let mut input = canonical_input();
    input.pairs[0]
        .full_vec
        .measurement
        .authoritative_transaction_ns = Some(0);
    assert_canonical_rejected(input);
}

#[test]
fn canonical_rejects_zero_cgroup_peak_measurement() {
    let mut input = canonical_input();
    input.pairs[0]
        .full_vec
        .measurement
        .cgroup_memory_peak_before_bytes = Some(0);
    input.pairs[0]
        .full_vec
        .measurement
        .cgroup_memory_peak_after_bytes = Some(0);
    input.pairs[0]
        .full_vec
        .measurement
        .cgroup_memory_current_before_bytes = Some(0);
    input.pairs[0]
        .full_vec
        .measurement
        .cgroup_memory_current_after_bytes = Some(0);
    assert_canonical_rejected(input);
}

#[test]
fn canonical_rejects_cgroup_peak_below_current_usage() {
    let mut input = canonical_input();
    input.pairs[0]
        .staged_native
        .measurement
        .cgroup_memory_peak_after_bytes = Some(66);
    assert_canonical_rejected(input);
}

#[test]
fn canonical_rejects_wal_bytes_that_violate_the_physical_frame_formula() {
    let mut input = canonical_input();
    input.pairs[0].staged_native.database.wal_bytes = Some(wal_bytes(WAL_FRAMES) + 1);
    assert_canonical_rejected(input);
}

#[test]
fn canonical_rejects_unbound_runtime_environment_values() {
    let mut input = canonical_input();
    input.runtime_environment.kernel_release = "UNBOUND".into();
    input.base_fixture_preflight.runtime_environment = input.runtime_environment.clone();
    assert_canonical_rejected(input);
}

#[test]
fn canonical_rejects_reused_child_cgroup_path() {
    let mut input = canonical_input();
    input.pairs[1].full_vec.measurement.cgroup_path =
        input.pairs[0].full_vec.measurement.cgroup_path.clone();
    assert_canonical_rejected(input);
}

#[test]
fn canonical_rejects_reused_child_trial_root_and_database_path() {
    let mut input = canonical_input();
    let duplicate_root = input.pairs[0].full_vec.storage.trial_root.clone();
    let duplicate_database = duplicate_root.join("database/state.db");
    let duplicate = &mut input.pairs[1].full_vec;
    duplicate.storage.trial_root = duplicate_root;
    duplicate.authoritative_pragmas_before.database_files[0] = duplicate_database.clone();
    duplicate.authoritative_pragmas_after.database_files[0] = duplicate_database;
    assert_canonical_rejected(input);
}

#[test]
fn canonical_rejects_reused_child_process_id_across_pairs() {
    let mut input = canonical_input();
    let duplicate_pid = input.pairs[0].full_vec.execution.process_id;
    let duplicate = &mut input.pairs[1];
    duplicate.full_vec.execution.process_id = duplicate_pid;
    for observed in &mut duplicate.observed_execution {
        if observed.mode == Mode::FullVec {
            observed.process_id = duplicate_pid;
        }
    }
    assert_canonical_rejected(input);
}

#[test]
fn canonical_rejects_child_execution_overlap_across_pair_boundaries() {
    let mut input = canonical_input();
    let previous_finished = input.pairs[0].observed_execution[1].finished_unix_ns;
    let pair = &mut input.pairs[1];
    pair.observed_execution[0].started_unix_ns = previous_finished - 1;
    pair.observed_execution[0].finished_unix_ns = previous_finished + 4;
    pair.observed_execution[1].started_unix_ns = previous_finished + 5;
    pair.observed_execution[1].finished_unix_ns = previous_finished + 10;
    for observed in &pair.observed_execution {
        match observed.mode {
            Mode::FullVec => pair.full_vec.execution = observed.clone(),
            Mode::StagedNative => pair.staged_native.execution = observed.clone(),
        }
    }
    assert_canonical_rejected(input);
}

#[test]
fn canonical_rejects_fault_generation_not_bound_to_the_base() {
    let mut input = canonical_input();
    input.failure_atomicity[0].target_generation_sha256_before = "e".repeat(64);
    input.failure_atomicity[0].target_generation_sha256_after = "e".repeat(64);
    assert_canonical_rejected(input);
}

#[test]
fn canonical_rejects_fault_rollback_schema_not_bound_to_the_base() {
    let mut input = canonical_input();
    input.failure_atomicity[0].rollback_before.schema_sha256 = "e".repeat(64);
    input.failure_atomicity[0].rollback_after.schema_sha256 = "e".repeat(64);
    assert_canonical_rejected(input);
}

#[test]
fn canonical_rejects_fault_database_path_not_bound_to_its_case() {
    let mut input = canonical_input();
    let fault = &mut input.failure_atomicity[0];
    let wrong_database =
        "/home/pallasting/eval/codebase-index-a1/fault-wrong/database/state.db".into();
    fault.authoritative_pragmas_before.database_files[0] = wrong_database;
    fault.authoritative_pragmas_after = fault.authoritative_pragmas_before.clone();
    fault.post_fault_query.result_sha256 = sha256_json(&fault.authoritative_pragmas_after);
    assert_canonical_rejected(input);
}

#[test]
fn canonical_rejects_unbound_post_fault_query_digest() {
    let mut input = canonical_input();
    input.failure_atomicity[0].post_fault_query.result_sha256 = "e".repeat(64);
    assert_canonical_rejected(input);
}
