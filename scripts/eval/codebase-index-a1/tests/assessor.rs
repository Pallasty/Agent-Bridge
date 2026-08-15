use ab_codebase_index_a1::quiet::{
    ChildInterferenceEvidence, CpuProcessSample, HostQuietWindowEvidence, PressureTotals,
    SchedstatCpuSample, ThreadAffinityEvidence,
};
use ab_codebase_index_a1::{
    assess_suite, canonical_workload, AuthoritativePragmaEvidence, AuthorityEvidence,
    BaseFixturePreflightReceipt, BuildIdentity, CanonicalRawPacket, ChildExecutionEvidence,
    DatabaseEvidence, EvidenceClass, FailureAtomicityReceipt, FailureCase, FixtureEvidence,
    FullVecEvidence, HostStorageContext, Measurement, Mode, PostFaultQueryEvidence, Provenance,
    RollbackStateEvidence, RunReceipt, RuntimeEnvironmentEvidence, StorageEvidence, SuiteInput,
    TrialOrder, TrialPair, WalHeaderLayoutEvidence, WalResetEvidence, Workload,
    CANONICAL_BATCH_ROWS, CANONICAL_PAIRS, CANONICAL_TOTAL_ROWS, FAILURE_RECEIPT_SCHEMA,
    RAW_PACKET_SCHEMA,
};
use sha2::{Digest, Sha256};

const WAL_PAGE_SIZE: u64 = 4_096;
const WAL_FRAMES: u64 = 2_400;
const QUIET_STARTED_UNIX_NS: u64 = 1_000_000_000;
const QUIET_FINISHED_UNIX_NS: u64 = 31_000_000_000;
const CHILDREN_STARTED_UNIX_NS: u64 = 32_000_000_000;
const CHILD_SEQUENCE_SPACING_NS: u64 = 3_000_000_000;
const CHILD_EXECUTION_DURATION_NS: u64 = 2_500_000_000;
const FULL_ELAPSED_NS: u64 = 2_000_000_000;
const STAGED_ELAPSED_NS: u64 = 2_100_000_000;
const ORCHESTRATOR_PID: u32 = 777;

fn wal_bytes(frames: u64) -> u64 {
    32 + frames * (24 + WAL_PAGE_SIZE)
}

fn wal_header_layout(frames: u64) -> WalHeaderLayoutEvidence {
    if frames == 0 {
        return WalHeaderLayoutEvidence {
            bytes: 0,
            header_hex: None,
            magic: None,
            format_version: None,
            encoded_page_size: None,
            frame_count: 0,
            header_layout_valid: true,
        };
    }
    let mut header = [0_u8; 32];
    header[0..4].copy_from_slice(&0x377f_0682_u32.to_be_bytes());
    header[4..8].copy_from_slice(&3_007_000_u32.to_be_bytes());
    header[8..12].copy_from_slice(&(WAL_PAGE_SIZE as u32).to_be_bytes());
    WalHeaderLayoutEvidence {
        bytes: wal_bytes(frames),
        header_hex: Some(
            header
                .iter()
                .map(|byte| format!("{byte:02x}"))
                .collect::<Vec<_>>()
                .join(""),
        ),
        magic: Some(0x377f_0682),
        format_version: Some(3_007_000),
        encoded_page_size: Some(WAL_PAGE_SIZE),
        frame_count: frames,
        header_layout_valid: true,
    }
}

fn set_database_wal_frames(database: &mut DatabaseEvidence, frames: u64) {
    database.wal_bytes = Some(if frames == 0 { 0 } else { wal_bytes(frames) });
    database.wal_frames = Some(frames);
    database.wal_checkpoint_log_frames = Some(frames);
    database.wal_checkpointed_frames = Some(frames);
    database.wal_header_layout = Some(wal_header_layout(frames));
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
        wal_header_layout: Some(wal_header_layout(WAL_FRAMES)),
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
    let started_unix_ns = CHILDREN_STARTED_UNIX_NS + sequence as u64 * CHILD_SEQUENCE_SPACING_NS;
    ChildExecutionEvidence {
        mode,
        sequence,
        process_id: 1_000 + sequence as u32,
        started_unix_ns,
        finished_unix_ns: started_unix_ns + CHILD_EXECUTION_DURATION_NS,
    }
}

fn process_sample(
    sample_started_monotonic_ns: u64,
    end: bool,
    process_id: u32,
    cgroup_path: &str,
) -> CpuProcessSample {
    let blocking_sleep_started_monotonic_ns = sample_started_monotonic_ns + 100;
    let blocking_sleep_deadline_monotonic_ns = blocking_sleep_started_monotonic_ns + 1_000_000;
    let blocking_sleep_returned_monotonic_ns = blocking_sleep_deadline_monotonic_ns + 100;
    let host_sample_before_monotonic_ns = blocking_sleep_returned_monotonic_ns + 100;
    let schedstat_read_finished_monotonic_ns = host_sample_before_monotonic_ns + 100;
    let host_sample_after_monotonic_ns = schedstat_read_finished_monotonic_ns + 100;
    CpuProcessSample {
        sampled_unix_ns: sample_started_monotonic_ns + 1_000_000,
        sample_started_monotonic_ns,
        sample_finished_monotonic_ns: host_sample_after_monotonic_ns + 100,
        blocking_sleep_started_monotonic_ns,
        blocking_sleep_deadline_monotonic_ns,
        blocking_sleep_returned_monotonic_ns,
        schedstat_read_finished_monotonic_ns,
        host_sample_before_monotonic_ns,
        host_sample_after_monotonic_ns,
        monotonic_clock_resolution_ns: 1,
        cpu: 39,
        sampled_cpu: 39,
        excluded_smt_sibling: 79,
        cpu_total_ticks: if end { 1_100 } else { 1_000 },
        cpu_idle_ticks: if end { 990 } else { 900 },
        cpu_irq_ticks: 0,
        cpu_softirq_ticks: 0,
        cpu_steal_ticks: 0,
        excluded_smt_total_ticks: if end { 2_200 } else { 2_000 },
        excluded_smt_idle_ticks: if end { 2_100 } else { 1_900 },
        cpu_schedstat: SchedstatCpuSample {
            version: 17,
            timestamp: if end { 124 } else { 123 },
            runtime_ns: if end { 1_080_000_000 } else { 1_000_000_000 },
            wait_ns: if end { 20 } else { 10 },
            timeslices: if end { 43 } else { 42 },
        },
        cgroup_path: cgroup_path.into(),
        cgroup_inode: 77,
        cgroup_type: "domain".into(),
        cgroup_cpu_usage_usec_before_host_sample: if end { 160_000 } else { 99_000 },
        cgroup_cpu_usage_usec_after_host_sample: if end { 161_000 } else { 100_000 },
        cgroup_nr_periods_before_host_sample: if end { 101 } else { 100 },
        cgroup_nr_periods_after_host_sample: if end { 101 } else { 100 },
        cgroup_nr_throttled_before_host_sample: 0,
        cgroup_nr_throttled_after_host_sample: 0,
        cgroup_throttled_usec_before_host_sample: 0,
        cgroup_throttled_usec_after_host_sample: 0,
        cgroup_process_ids: vec![process_id],
        cgroup_thread_ids: vec![process_id],
        cgroup_nr_descendants: 0,
        cgroup_nr_dying_descendants: 0,
        accounting_flush_tid: process_id,
        accounting_flush_requested_ns: 1_000_000,
        accounting_flush_observed_ns: 1_000_100,
        accounting_flush_voluntary_switches_before: if end { 20 } else { 10 },
        accounting_flush_voluntary_switches_after: if end { 21 } else { 11 },
        clock_ticks_per_second: 100,
        no_new_privileges: true,
        seccomp_mode: 2,
        seccomp_filter_count: 1,
        thread_affinities: vec![ThreadAffinityEvidence {
            tid: process_id,
            allowed_cpus: "39".into(),
        }],
        pressure: PressureTotals {
            cpu_some_us: 0,
            memory_some_us: 0,
            memory_full_us: 0,
            io_some_us: 0,
            io_full_us: 0,
        },
        actual_affinity: "39".into(),
        effective_cpuset: "0-79".into(),
        competing_build_processes: Vec::new(),
    }
}

fn child_interference(
    execution: &ChildExecutionEvidence,
    cgroup_path: &str,
) -> ChildInterferenceEvidence {
    let operation_elapsed_ns = if execution.mode == Mode::StagedNative {
        STAGED_ELAPSED_NS
    } else {
        FULL_ELAPSED_NS
    };
    let operation_started_monotonic_ns = execution.started_unix_ns + 10_000_000;
    let operation_finished_monotonic_ns = operation_started_monotonic_ns + operation_elapsed_ns;
    let end_current_pending_upper_bound_ns = 302;
    let cgroup_cpu_usage_floor_lower_bound_ns = 59_999_001;
    let own_cpu_lower_bound_ns = 59_998_699;
    let cpu39_external_scheduled_runtime_upper_bound_ns = 20_001_301;
    let cpu39_combined_external_upper_bound_ns = 50_001_301;
    let operation_elapsed_lower_bound_ns = operation_elapsed_ns - 2;
    ChildInterferenceEvidence {
        start: process_sample(
            execution.started_unix_ns + 1_000_000,
            false,
            execution.process_id,
            cgroup_path,
        ),
        end: process_sample(
            execution.started_unix_ns + 2_300_000_000,
            true,
            execution.process_id,
            cgroup_path,
        ),
        operation_started_monotonic_ns,
        operation_finished_monotonic_ns,
        operation_elapsed_ns,
        operation_elapsed_lower_bound_ns,
        cgroup_cpu_inner_delta_usec: 60_000,
        cgroup_cpu_usage_floor_lower_bound_ns,
        end_current_pending_upper_bound_ns,
        own_cpu_lower_bound_ns,
        cpu39_scheduled_runtime_outer_ns: 80_000_000,
        cpu39_external_scheduled_runtime_upper_bound_ns,
        cpu39_proc_stat_side_charge_upper_bound_ns: 30_000_000,
        cpu39_combined_external_upper_bound_ns,
        external_cpu39_busy_upper_bound_bps: if execution.mode == Mode::StagedNative {
            239
        } else {
            251
        },
        excluded_smt_nonidle_upper_bound_ns: 60_000_000,
        excluded_smt_sibling_busy_upper_bound_bps: if execution.mode == Mode::StagedNative {
            286
        } else {
            301
        },
    }
}

fn set_run_elapsed(run: &mut RunReceipt, elapsed_ns: u64) {
    run.measurement.elapsed_ns = Some(elapsed_ns);
    let evidence = run
        .child_interference
        .as_mut()
        .expect("canonical fixture has child interference evidence");
    evidence.operation_finished_monotonic_ns = evidence.operation_started_monotonic_ns + elapsed_ns;
    evidence.operation_elapsed_ns = elapsed_ns;
    evidence.operation_elapsed_lower_bound_ns = elapsed_ns - 2;
    evidence.external_cpu39_busy_upper_bound_bps = ceil_bps(
        evidence.cpu39_combined_external_upper_bound_ns,
        elapsed_ns - 2,
    );
    evidence.excluded_smt_sibling_busy_upper_bound_bps =
        ceil_bps(evidence.excluded_smt_nonidle_upper_bound_ns, elapsed_ns - 2);
}

fn shift_sample_monotonic(sample: &mut CpuProcessSample, delta_ns: u64) {
    sample.sample_started_monotonic_ns += delta_ns;
    sample.sample_finished_monotonic_ns += delta_ns;
    sample.blocking_sleep_started_monotonic_ns += delta_ns;
    sample.blocking_sleep_deadline_monotonic_ns += delta_ns;
    sample.blocking_sleep_returned_monotonic_ns += delta_ns;
    sample.schedstat_read_finished_monotonic_ns += delta_ns;
    sample.host_sample_before_monotonic_ns += delta_ns;
    sample.host_sample_after_monotonic_ns += delta_ns;
}

fn ceil_bps(numerator: u64, denominator: u64) -> u64 {
    let scaled = u128::from(numerator) * 10_000;
    u64::try_from((scaled + u128::from(denominator - 1)) / u128::from(denominator)).unwrap()
}

fn host_quiet_window() -> HostQuietWindowEvidence {
    HostQuietWindowEvidence {
        cpu: 39,
        excluded_smt_sibling: 79,
        started_unix_ns: QUIET_STARTED_UNIX_NS,
        finished_unix_ns: QUIET_FINISHED_UNIX_NS,
        duration_ms: 30_000,
        duration_us: 30_000_000,
        sample_count: 31,
        cpu_total_delta_ticks: 3_000,
        cpu_idle_delta_ticks: 2_880,
        overall_idle_bps: 9_600,
        worst_bucket_idle_bps: 9_600,
        bucket_total_delta_ticks: vec![100; 30],
        bucket_idle_delta_ticks: vec![96; 30],
        excluded_smt_total_delta_ticks: 3_000,
        excluded_smt_idle_delta_ticks: 2_880,
        excluded_smt_overall_idle_bps: 9_600,
        excluded_smt_worst_bucket_idle_bps: 9_600,
        excluded_smt_bucket_total_delta_ticks: vec![100; 30],
        excluded_smt_bucket_idle_delta_ticks: vec![96; 30],
        pressure_start: PressureTotals {
            cpu_some_us: 0,
            memory_some_us: 0,
            memory_full_us: 0,
            io_some_us: 0,
            io_full_us: 0,
        },
        pressure_end: PressureTotals {
            cpu_some_us: 0,
            memory_some_us: 0,
            memory_full_us: 0,
            io_some_us: 0,
            io_full_us: 0,
        },
        cpu_some_pressure_delta_bps: 0,
        memory_some_pressure_delta_bps: 0,
        memory_full_pressure_delta_bps: 0,
        io_some_pressure_delta_bps: 0,
        io_full_pressure_delta_bps: 0,
        competing_build_processes: Vec::new(),
        actual_affinity: "0-79".into(),
        effective_cpuset: "0-79".into(),
        passed: true,
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
    let execution = execution(mode, pair);
    let position = execution.sequence % 2;
    let expected_cgroup_unit = format!(
        "ab-codebase-index-a1-{ORCHESTRATOR_PID}-{pair}-{position}-{}",
        if candidate { "staged" } else { "full" }
    );
    RunReceipt {
        schema: "agent_bridge.codebase_index.a1.run_receipt.v0".into(),
        mode,
        execution: execution.clone(),
        expected_cgroup_unit: Some(expected_cgroup_unit.clone()),
        build_identity: identity(true),
        workload: workload(),
        measurement: Measurement {
            elapsed_ns: Some(if candidate {
                STAGED_ELAPSED_NS
            } else {
                FULL_ELAPSED_NS
            }),
            peak_rss_bytes: Some(if candidate { 69 } else { 100 }),
            vm_hwm_bytes: Some(if candidate { 68 } else { 99 }),
            authoritative_transaction_ns: Some(if candidate { 105 } else { 100 }),
            cgroup_path: Some(format!("/user.slice/{expected_cgroup_unit}.service")),
            cgroup_memory_current_before_bytes: Some(0),
            cgroup_memory_current_after_bytes: Some(if candidate { 67 } else { 100 }),
            cgroup_memory_peak_before_bytes: Some(0),
            cgroup_memory_peak_after_bytes: Some(if candidate { 69 } else { 100 }),
            cgroup_memory_max: Some("max".into()),
            cgroup_process_count: Some(1),
            cgroup_process_ids_before: Some(vec![execution.process_id]),
            cgroup_process_ids_after: Some(vec![execution.process_id]),
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
        child_interference: Some(child_interference(
            &execution,
            &format!("/user.slice/{expected_cgroup_unit}.service"),
        )),
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
        database_sha256: "4".repeat(64),
        all_codebase_sha256: "b".repeat(64),
        sqlite_sequence_sha256: "c".repeat(64),
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
    set_database_wal_frames(&mut database, 0);
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
        rollback_state: rollback_state(),
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
    .enumerate()
    .map(|(fault_index, case)| {
        let trial_root = format!("/home/pallasting/eval/codebase-index-a1/fault-{case:?}");
        let database_path = format!("{trial_root}/database/state.db");
        let sequence = CANONICAL_PAIRS * 2 + fault_index;
        let process_id = 1_000 + sequence as u32;
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
        let expected_cgroup_unit =
            format!("ab-codebase-index-a1-{ORCHESTRATOR_PID}-fault-{case_arg}");
        let started_unix_ns =
            CHILDREN_STARTED_UNIX_NS + sequence as u64 * CHILD_SEQUENCE_SPACING_NS;
        let authoritative_pragmas = pragmas(&trial_root);
        let mut rollback_after_cleanup = rollback_state();
        rollback_after_cleanup.database_sha256 = "d".repeat(64);
        FailureAtomicityReceipt {
            schema: FAILURE_RECEIPT_SCHEMA.into(),
            case,
            workload: workload(),
            execution: ChildExecutionEvidence {
                mode: Mode::StagedNative,
                sequence,
                process_id,
                started_unix_ns,
                finished_unix_ns: started_unix_ns + CHILD_EXECUTION_DURATION_NS,
            },
            build_identity: identity(true),
            trial_root: trial_root.clone().into(),
            database_path: database_path.into(),
            expected_cgroup_unit: expected_cgroup_unit.clone(),
            cgroup_path: format!("/user.slice/{expected_cgroup_unit}.service"),
            cgroup_process_count: 1,
            cgroup_process_ids_before: vec![process_id],
            cgroup_process_ids_after: vec![process_id],
            cgroup_isolated_for_trial: true,
            actual_process_affinity: "39".into(),
            wal_reset: WalResetEvidence {
                busy: 0,
                log_frames: 0,
                checkpointed_frames: 0,
                wal_bytes: 0,
                proven_empty: true,
            },
            wal_cleanup: WalResetEvidence {
                busy: 0,
                log_frames: 0,
                checkpointed_frames: 0,
                wal_bytes: 0,
                proven_empty: true,
            },
            post_fault_wal_header_layout: wal_header_layout(1),
            main_wal_bytes_before: 0,
            main_wal_bytes_after: 4_152,
            main_wal_bytes_after_cleanup: 0,
            main_shm_bytes_before: 32_768,
            main_shm_bytes_after: 32_768,
            main_shm_bytes_after_cleanup: 32_768,
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
            rollback_after_cleanup,
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
        host_quiet_window: Some(host_quiet_window()),
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
fn canonical_accepts_structural_wal_index_growth_after_fault_rollback() {
    let mut input = canonical_input();
    let receipt = &mut input.failure_atomicity[1];
    let frames = 4_063;
    receipt.post_fault_wal_header_layout = wal_header_layout(frames);
    receipt.main_wal_bytes_after = wal_bytes(frames);
    receipt.main_shm_bytes_after = 65_536;
    receipt.main_shm_bytes_after_cleanup = 65_536;

    let assessment = assess_suite(&input);
    assert!(assessment.eligible, "{:#?}", assessment.reasons);
    assert!(assessment.decision_pass);
}

#[test]
fn canonical_treats_operation_window_system_pressure_as_observational() {
    let mut input = canonical_input();
    let evidence = input.pairs[0]
        .staged_native
        .child_interference
        .as_mut()
        .unwrap();
    evidence.end.pressure.cpu_some_us = 1_000_000;
    evidence.end.pressure.memory_some_us = 1_000_000;
    evidence.end.pressure.memory_full_us = 1_000_000;
    evidence.end.pressure.io_some_us = 1_000_000;
    evidence.end.pressure.io_full_us = 1_000_000;

    let assessment = assess_suite(&input);
    assert!(assessment.eligible, "{:#?}", assessment.reasons);
    assert!(assessment.decision_pass);
}

#[test]
fn canonical_raw_packet_round_trips_complete_input_and_recomputes_assessment() {
    let input = canonical_input();
    let assessment = assess_suite(&input);
    let packet = CanonicalRawPacket {
        schema: RAW_PACKET_SCHEMA.into(),
        input: input.clone(),
        assessment: assessment.clone(),
    };

    let encoded = serde_json::to_vec(&packet).expect("canonical raw packet must serialize");
    let decoded: CanonicalRawPacket =
        serde_json::from_slice(&encoded).expect("canonical raw packet must deserialize");

    assert_eq!(decoded.schema, RAW_PACKET_SCHEMA);
    assert_eq!(decoded.input, input);
    assert_eq!(decoded.assessment, assessment);
    assert_eq!(assess_suite(&decoded.input), decoded.assessment);
    assert_eq!(decoded.input.evidence_class, EvidenceClass::Canonical);
    assert_eq!(
        decoded.input.trial_root.as_deref(),
        Some(std::path::Path::new(
            "/home/pallasting/eval/codebase-index-a1"
        ))
    );
    assert_eq!(
        decoded.input.cache_policy,
        "warm_shared_corpus_after_single_base_fixture"
    );
    assert_eq!(
        decoded
            .input
            .host_storage_context
            .filesystem_type
            .as_deref(),
        Some("fuseblk")
    );
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

    let mut missing_wal_header = canonical_input();
    missing_wal_header.pairs[0]
        .staged_native
        .database
        .wal_header_layout = None;
    assert!(!assess_suite(&missing_wal_header).eligible);

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
    set_run_elapsed(&mut edge.pairs[0].staged_native, 2_200_000_000);
    edge.pairs[0]
        .staged_native
        .measurement
        .authoritative_transaction_ns = Some(110);
    set_database_wal_frames(&mut edge.pairs[0].staged_native.database, 2_520);
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
        set_database_wal_frames(&mut pair.staged_native.database, 2_521);
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
            (1_500_000_000, 1_950_000_000)
        } else {
            (2_000_000_000, 2_180_000_000)
        };
        set_run_elapsed(&mut pair.full_vec, baseline);
        set_run_elapsed(&mut pair.staged_native, candidate);
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

    let mut forged_header = canonical_input();
    forged_header.pairs[0]
        .staged_native
        .database
        .wal_header_layout
        .as_mut()
        .unwrap()
        .header_hex = Some("0".repeat(64));
    assert_canonical_rejected(forged_header);
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
fn canonical_rejects_self_attested_cgroup_unit_or_process_membership() {
    let mut wrong_unit = canonical_input();
    wrong_unit.pairs[0].full_vec.expected_cgroup_unit = Some("forged-unit".into());
    assert_canonical_rejected(wrong_unit);

    let mut extra_process = canonical_input();
    extra_process.pairs[0]
        .staged_native
        .measurement
        .cgroup_process_ids_before
        .as_mut()
        .unwrap()
        .push(99_999);
    assert_canonical_rejected(extra_process);

    let mut fault_owner_drift = canonical_input();
    fault_owner_drift.failure_atomicity[0].expected_cgroup_unit =
        "ab-codebase-index-a1-778-fault-after-staging-batch".into();
    fault_owner_drift.failure_atomicity[0].cgroup_path =
        "/user.slice/ab-codebase-index-a1-778-fault-after-staging-batch.service".into();
    assert_canonical_rejected(fault_owner_drift);
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

#[test]
fn canonical_rejects_missing_or_internally_inconsistent_host_quiet_window() {
    let mut missing = canonical_input();
    missing.host_quiet_window = None;
    assert_canonical_rejected(missing);

    let mut forged_worst_bucket = canonical_input();
    let quiet = forged_worst_bucket.host_quiet_window.as_mut().unwrap();
    quiet.bucket_idle_delta_ticks[0] = 80;
    quiet.cpu_idle_delta_ticks -= 16;
    assert_canonical_rejected(forged_worst_bucket);

    let mut forged_smt_bucket = canonical_input();
    let quiet = forged_smt_bucket.host_quiet_window.as_mut().unwrap();
    quiet.excluded_smt_bucket_idle_delta_ticks[0] = 80;
    quiet.excluded_smt_idle_delta_ticks -= 16;
    assert_canonical_rejected(forged_smt_bucket);

    let mut wrong_smt_identity = canonical_input();
    wrong_smt_identity
        .host_quiet_window
        .as_mut()
        .unwrap()
        .excluded_smt_sibling = 78;
    assert_canonical_rejected(wrong_smt_identity);

    let mut forged_memory_some_rate = canonical_input();
    forged_memory_some_rate
        .host_quiet_window
        .as_mut()
        .unwrap()
        .memory_some_pressure_delta_bps = 1;
    assert_canonical_rejected(forged_memory_some_rate);

    let mut noisy_io_some = canonical_input();
    let quiet = noisy_io_some.host_quiet_window.as_mut().unwrap();
    quiet.pressure_end.io_some_us = 303_000;
    quiet.io_some_pressure_delta_bps = 101;
    assert_canonical_rejected(noisy_io_some);
}

#[test]
fn canonical_rejects_noisy_or_forged_child_interference_evidence() {
    let mut noisy = canonical_input();
    noisy.pairs[0]
        .full_vec
        .child_interference
        .as_mut()
        .unwrap()
        .external_cpu39_busy_upper_bound_bps = 501;
    assert_canonical_rejected(noisy);

    let mut wrong_affinity = canonical_input();
    wrong_affinity.pairs[0]
        .staged_native
        .child_interference
        .as_mut()
        .unwrap()
        .end
        .actual_affinity = "38-39".into();
    assert_canonical_rejected(wrong_affinity);

    let mut forged_smt_busy = canonical_input();
    forged_smt_busy.pairs[0]
        .full_vec
        .child_interference
        .as_mut()
        .unwrap()
        .excluded_smt_sibling_busy_upper_bound_bps = 499;
    assert_canonical_rejected(forged_smt_busy);

    let mut forged_cpu39_bound = canonical_input();
    forged_cpu39_bound.pairs[0]
        .full_vec
        .child_interference
        .as_mut()
        .unwrap()
        .cpu39_combined_external_upper_bound_ns += 1;
    assert_canonical_rejected(forged_cpu39_bound);

    let mut forged_process_lower_bound = canonical_input();
    forged_process_lower_bound.pairs[0]
        .staged_native
        .child_interference
        .as_mut()
        .unwrap()
        .own_cpu_lower_bound_ns -= 1;
    assert_canonical_rejected(forged_process_lower_bound);

    let mut changed_clock_resolution = canonical_input();
    changed_clock_resolution.pairs[0]
        .full_vec
        .child_interference
        .as_mut()
        .unwrap()
        .end
        .monotonic_clock_resolution_ns = 2;
    assert_canonical_rejected(changed_clock_resolution);

    let mut unconfined_thread = canonical_input();
    unconfined_thread.pairs[0]
        .staged_native
        .child_interference
        .as_mut()
        .unwrap()
        .end
        .thread_affinities[0]
        .allowed_cpus = "0-79".into();
    assert_canonical_rejected(unconfined_thread);

    let mut missing_seccomp_custody = canonical_input();
    missing_seccomp_custody.pairs[0]
        .full_vec
        .child_interference
        .as_mut()
        .unwrap()
        .start
        .no_new_privileges = false;
    assert_canonical_rejected(missing_seccomp_custody);

    let mut noisy_smt_sibling = canonical_input();
    let sibling = noisy_smt_sibling.pairs[0]
        .staged_native
        .child_interference
        .as_mut()
        .unwrap();
    sibling.end.excluded_smt_idle_ticks = 1_990;
    sibling.excluded_smt_sibling_busy_upper_bound_bps = 1_000;
    assert_canonical_rejected(noisy_smt_sibling);

    let mut continuous_current_sibling = canonical_input();
    let sibling = continuous_current_sibling.pairs[0]
        .full_vec
        .child_interference
        .as_mut()
        .unwrap();
    sibling.end.excluded_smt_total_ticks += 100;
    sibling.excluded_smt_nonidle_upper_bound_ns = 1_060_000_000;
    sibling.excluded_smt_sibling_busy_upper_bound_bps = 5_301;
    assert_canonical_rejected(continuous_current_sibling);

    let mut reversed_system_pressure = canonical_input();
    reversed_system_pressure.pairs[0]
        .staged_native
        .child_interference
        .as_mut()
        .unwrap()
        .start
        .pressure
        .io_full_us = 1;
    assert_canonical_rejected(reversed_system_pressure);

    let mut forged_sleep_deadline = canonical_input();
    let start = &mut forged_sleep_deadline.pairs[0]
        .full_vec
        .child_interference
        .as_mut()
        .unwrap()
        .start;
    start.blocking_sleep_deadline_monotonic_ns += 1;
    assert_canonical_rejected(forged_sleep_deadline);

    let mut descendant_cgroup = canonical_input();
    descendant_cgroup.pairs[0]
        .full_vec
        .child_interference
        .as_mut()
        .unwrap()
        .end
        .cgroup_nr_descendants = 1;
    assert_canonical_rejected(descendant_cgroup);

    let mut extra_cgroup_process = canonical_input();
    extra_cgroup_process.pairs[0]
        .staged_native
        .child_interference
        .as_mut()
        .unwrap()
        .start
        .cgroup_process_ids
        .push(99_999);
    assert_canonical_rejected(extra_cgroup_process);

    let mut stagnant_timeslices = canonical_input();
    let evidence = stagnant_timeslices.pairs[0]
        .full_vec
        .child_interference
        .as_mut()
        .unwrap();
    evidence.end.cpu_schedstat.timeslices = evidence.start.cpu_schedstat.timeslices;
    assert_canonical_rejected(stagnant_timeslices);

    let mut throttled_cgroup = canonical_input();
    let end = &mut throttled_cgroup.pairs[0]
        .staged_native
        .child_interference
        .as_mut()
        .unwrap()
        .end;
    end.cgroup_nr_throttled_before_host_sample = 1;
    end.cgroup_nr_throttled_after_host_sample = 1;
    end.cgroup_throttled_usec_before_host_sample = 100;
    end.cgroup_throttled_usec_after_host_sample = 100;
    assert_canonical_rejected(throttled_cgroup);

    let mut coherent_cross_clock_forgery = canonical_input();
    let forged_run = &mut coherent_cross_clock_forgery.pairs[0].full_vec;
    set_run_elapsed(forged_run, 2_400_000_000);
    shift_sample_monotonic(
        &mut forged_run.child_interference.as_mut().unwrap().end,
        200_000_000,
    );
    assert_canonical_rejected(coherent_cross_clock_forgery);

    let mut forged_operation_elapsed = canonical_input();
    forged_operation_elapsed.pairs[0]
        .full_vec
        .child_interference
        .as_mut()
        .unwrap()
        .operation_elapsed_ns += 1;
    assert_canonical_rejected(forged_operation_elapsed);
}

#[test]
fn canonical_rejects_fault_wal_reset_or_sidecar_drift() {
    let mut nonempty_reset = canonical_input();
    nonempty_reset.failure_atomicity[0].wal_reset.log_frames = 1;
    nonempty_reset.failure_atomicity[0].wal_reset.wal_bytes = wal_bytes(1);
    nonempty_reset.failure_atomicity[0].wal_reset.proven_empty = false;
    assert_canonical_rejected(nonempty_reset);

    let mut changed_wal_sidecar = canonical_input();
    changed_wal_sidecar.failure_atomicity[1].main_wal_bytes_after = wal_bytes(1) + 1;
    assert_canonical_rejected(changed_wal_sidecar);

    let mut forged_header_binding = canonical_input();
    forged_header_binding.failure_atomicity[1]
        .post_fault_wal_header_layout
        .header_hex = Some(format!("00000000{}", "0".repeat(56)));
    forged_header_binding.failure_atomicity[1]
        .post_fault_wal_header_layout
        .magic = Some(0);
    assert_canonical_rejected(forged_header_binding);

    let mut forged_page_size = canonical_input();
    forged_page_size.failure_atomicity[1]
        .post_fault_wal_header_layout
        .encoded_page_size = Some(8_192);
    assert_canonical_rejected(forged_page_size);

    let mut failed_cleanup = canonical_input();
    failed_cleanup.failure_atomicity[1].wal_cleanup.proven_empty = false;
    failed_cleanup.failure_atomicity[1].main_wal_bytes_after_cleanup = wal_bytes(1);
    assert_canonical_rejected(failed_cleanup);

    let mut changed_shm_sidecar = canonical_input();
    changed_shm_sidecar.failure_atomicity[2].main_shm_bytes_after += 1;
    assert_canonical_rejected(changed_shm_sidecar);
}

#[test]
fn canonical_binds_each_fault_case_to_its_frozen_sequence() {
    let mut swapped = canonical_input();
    let first = swapped.failure_atomicity[0].execution.clone();
    let second = swapped.failure_atomicity[1].execution.clone();
    swapped.failure_atomicity[0].execution = second;
    swapped.failure_atomicity[1].execution = first;
    for receipt in &mut swapped.failure_atomicity[0..2] {
        receipt.cgroup_process_ids_before = vec![receipt.execution.process_id];
        receipt.cgroup_process_ids_after = vec![receipt.execution.process_id];
    }
    assert_canonical_rejected(swapped);
}

#[test]
fn canonical_rejects_fault_complete_rollback_digest_drift() {
    for digest_index in 0..3 {
        let mut input = canonical_input();
        let before = &mut input.failure_atomicity[0].rollback_before;
        match digest_index {
            0 => before.database_sha256 = "e".repeat(64),
            1 => before.all_codebase_sha256 = "e".repeat(64),
            _ => before.sqlite_sequence_sha256 = "e".repeat(64),
        }
        input.failure_atomicity[0].rollback_after = before.clone();
        assert_canonical_rejected(input);
    }
}
