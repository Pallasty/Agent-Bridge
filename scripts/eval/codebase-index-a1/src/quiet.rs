//! Fail-closed Linux host-interference evidence for the A1 benchmark.

use std::collections::BTreeSet;
use std::fs;
use std::io;
use std::mem::MaybeUninit;
use std::os::unix::fs::MetadataExt;
use std::path::{Component, Path, PathBuf};
use std::ptr;
use std::thread;
use std::time::{Duration, Instant, SystemTime, UNIX_EPOCH};

use serde::{Deserialize, Serialize};

pub const QUIET_OVERALL_IDLE_BPS: u64 = 9_500;
pub const QUIET_BUCKET_IDLE_BPS: u64 = 9_000;
pub const QUIET_SMT_OVERALL_IDLE_BPS: u64 = 9_500;
pub const QUIET_SMT_BUCKET_IDLE_BPS: u64 = 9_000;
pub const QUIET_CPU_SOME_PRESSURE_BPS: u64 = 100;
pub const QUIET_MEMORY_SOME_PRESSURE_BPS: u64 = 100;
pub const QUIET_MEMORY_FULL_PRESSURE_BPS: u64 = 10;
pub const QUIET_IO_SOME_PRESSURE_BPS: u64 = 100;
pub const QUIET_IO_FULL_PRESSURE_BPS: u64 = 10;
pub const CHILD_EXTERNAL_CPU39_BUSY_BPS: u64 = 500;
pub const CHILD_SMT_SIBLING_BUSY_BPS: u64 = 500;

const BPS_SCALE: u64 = 10_000;
const MAX_PLAUSIBLE_CPU_ID: u32 = 1_048_575;
const NANOSECONDS_PER_SECOND: u64 = 1_000_000_000;
const REQUIRED_CLOCK_TICKS_PER_SECOND: u64 = 100;
const PROC_STAT_NONIDLE_COUNTERS: u64 = 6;
const PROC_STAT_IRQ_COUNTERS: u64 = 3;
const ACCOUNTING_FLUSH_DURATION: Duration = Duration::from_millis(1);

#[derive(Debug, Clone, Copy, Serialize, Deserialize, PartialEq, Eq)]
pub struct SchedstatCpuSample {
    pub version: u32,
    pub timestamp: u64,
    pub runtime_ns: u64,
    pub wait_ns: u64,
    pub timeslices: u64,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq, PartialOrd, Ord)]
pub struct CompetingProcessEvidence {
    pub pid: u32,
    pub comm: String,
    pub start_ticks: u64,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq, PartialOrd, Ord)]
pub struct ThreadAffinityEvidence {
    pub tid: u32,
    pub allowed_cpus: String,
}

#[derive(Debug, Clone, Copy, Serialize, Deserialize, PartialEq, Eq)]
pub struct PressureTotals {
    pub cpu_some_us: u64,
    pub memory_some_us: u64,
    pub memory_full_us: u64,
    pub io_some_us: u64,
    pub io_full_us: u64,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct CpuProcessSample {
    pub sampled_unix_ns: u64,
    pub sample_started_monotonic_ns: u64,
    pub sample_finished_monotonic_ns: u64,
    pub blocking_sleep_started_monotonic_ns: u64,
    pub blocking_sleep_deadline_monotonic_ns: u64,
    pub blocking_sleep_returned_monotonic_ns: u64,
    pub schedstat_read_finished_monotonic_ns: u64,
    pub host_sample_before_monotonic_ns: u64,
    pub host_sample_after_monotonic_ns: u64,
    pub monotonic_clock_resolution_ns: u64,
    pub cpu: u32,
    pub sampled_cpu: u32,
    pub excluded_smt_sibling: u32,
    pub cpu_total_ticks: u64,
    pub cpu_idle_ticks: u64,
    pub cpu_irq_ticks: u64,
    pub cpu_softirq_ticks: u64,
    pub cpu_steal_ticks: u64,
    pub excluded_smt_total_ticks: u64,
    pub excluded_smt_idle_ticks: u64,
    pub cpu_schedstat: SchedstatCpuSample,
    pub cgroup_path: String,
    pub cgroup_inode: u64,
    pub cgroup_type: String,
    pub cgroup_cpu_usage_usec_before_host_sample: u64,
    pub cgroup_cpu_usage_usec_after_host_sample: u64,
    pub cgroup_nr_periods_before_host_sample: u64,
    pub cgroup_nr_periods_after_host_sample: u64,
    pub cgroup_nr_throttled_before_host_sample: u64,
    pub cgroup_nr_throttled_after_host_sample: u64,
    pub cgroup_throttled_usec_before_host_sample: u64,
    pub cgroup_throttled_usec_after_host_sample: u64,
    pub cgroup_process_ids: Vec<u32>,
    pub cgroup_thread_ids: Vec<u32>,
    pub cgroup_nr_descendants: u64,
    pub cgroup_nr_dying_descendants: u64,
    pub accounting_flush_tid: u32,
    pub accounting_flush_requested_ns: u64,
    pub accounting_flush_observed_ns: u64,
    pub accounting_flush_voluntary_switches_before: u64,
    pub accounting_flush_voluntary_switches_after: u64,
    pub clock_ticks_per_second: u64,
    pub no_new_privileges: bool,
    pub seccomp_mode: u32,
    pub seccomp_filter_count: u32,
    pub thread_affinities: Vec<ThreadAffinityEvidence>,
    pub pressure: PressureTotals,
    pub actual_affinity: String,
    pub effective_cpuset: String,
    pub competing_build_processes: Vec<CompetingProcessEvidence>,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct HostQuietWindowEvidence {
    pub cpu: u32,
    pub excluded_smt_sibling: u32,
    pub started_unix_ns: u64,
    pub finished_unix_ns: u64,
    pub duration_ms: u64,
    pub duration_us: u64,
    pub sample_count: usize,
    pub cpu_total_delta_ticks: u64,
    pub cpu_idle_delta_ticks: u64,
    pub overall_idle_bps: u64,
    pub worst_bucket_idle_bps: u64,
    pub bucket_total_delta_ticks: Vec<u64>,
    pub bucket_idle_delta_ticks: Vec<u64>,
    pub excluded_smt_total_delta_ticks: u64,
    pub excluded_smt_idle_delta_ticks: u64,
    pub excluded_smt_overall_idle_bps: u64,
    pub excluded_smt_worst_bucket_idle_bps: u64,
    pub excluded_smt_bucket_total_delta_ticks: Vec<u64>,
    pub excluded_smt_bucket_idle_delta_ticks: Vec<u64>,
    pub pressure_start: PressureTotals,
    pub pressure_end: PressureTotals,
    pub cpu_some_pressure_delta_bps: u64,
    pub memory_some_pressure_delta_bps: u64,
    pub memory_full_pressure_delta_bps: u64,
    pub io_some_pressure_delta_bps: u64,
    pub io_full_pressure_delta_bps: u64,
    pub competing_build_processes: Vec<CompetingProcessEvidence>,
    pub actual_affinity: String,
    pub effective_cpuset: String,
    pub passed: bool,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct ChildInterferenceEvidence {
    pub start: CpuProcessSample,
    pub end: CpuProcessSample,
    pub operation_started_monotonic_ns: u64,
    pub operation_finished_monotonic_ns: u64,
    pub operation_elapsed_ns: u64,
    pub operation_elapsed_lower_bound_ns: u64,
    pub cgroup_cpu_inner_delta_usec: u64,
    pub cgroup_cpu_usage_floor_lower_bound_ns: u64,
    pub end_current_pending_upper_bound_ns: u64,
    pub own_cpu_lower_bound_ns: u64,
    pub cpu39_scheduled_runtime_outer_ns: u64,
    pub cpu39_external_scheduled_runtime_upper_bound_ns: u64,
    pub cpu39_proc_stat_side_charge_upper_bound_ns: u64,
    pub cpu39_combined_external_upper_bound_ns: u64,
    pub external_cpu39_busy_upper_bound_bps: u64,
    pub excluded_smt_nonidle_upper_bound_ns: u64,
    pub excluded_smt_sibling_busy_upper_bound_bps: u64,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub(crate) struct ScheduledInterferenceBounds {
    pub(crate) cgroup_cpu_usage_floor_lower_bound_ns: u64,
    pub(crate) own_cpu_lower_bound_ns: u64,
    pub(crate) external_scheduled_runtime_upper_ns: u64,
    pub(crate) proc_stat_side_charge_upper_bound_ns: u64,
    pub(crate) combined_external_upper_bound_ns: u64,
    pub(crate) operation_elapsed_lower_bound_ns: u64,
    pub(crate) busy_upper_bound_bps: u64,
}

/// Observe one fail-closed sample of scheduler, cgroup CPU, procfs CPU,
/// pressure, affinity, cpuset, and competing Rust build activity.
pub fn cpu_process_sample(cpu: u32) -> io::Result<CpuProcessSample> {
    let sample_started_monotonic_ns = monotonic_time_ns()?;
    let monotonic_clock_resolution_ns = monotonic_clock_resolution_ns()?;
    let clock_ticks_per_second = clock_ticks_per_second()?;
    let excluded_smt_sibling = read_excluded_smt_sibling(cpu)?;
    let cgroup_path = unified_cgroup_path(&fs::read_to_string("/proc/self/cgroup")?)?;
    let cgroup_directory = cgroup_directory(&cgroup_path);
    let cgroup_inode = fs::metadata(&cgroup_directory)?.ino();
    let cgroup_type = fs::read_to_string(cgroup_directory.join("cgroup.type"))?
        .trim()
        .to_string();

    let accounting_flush_tid = current_thread_id()?;
    let (accounting_flush_voluntary_switches_before, _) = current_thread_context_switches()?;
    let accounting_flush_requested_ns = u64::try_from(ACCOUNTING_FLUSH_DURATION.as_nanos())
        .map_err(|_| invalid_data("accounting flush duration does not fit in u64"))?;
    let blocking_sleep_started_monotonic_ns = monotonic_time_ns()?;
    let blocking_sleep_deadline_monotonic_ns = blocking_sleep_started_monotonic_ns
        .checked_add(accounting_flush_requested_ns)
        .ok_or_else(|| invalid_data("blocking sleep deadline overflow"))?;
    absolute_monotonic_sleep(blocking_sleep_deadline_monotonic_ns)?;
    let blocking_sleep_returned_monotonic_ns = monotonic_time_ns()?;
    let accounting_flush_observed_ns = checked_delta(
        blocking_sleep_returned_monotonic_ns,
        blocking_sleep_started_monotonic_ns,
        "blocking accounting flush",
    )?;
    let accounting_flush_tid_after = current_thread_id()?;
    let (accounting_flush_voluntary_switches_after, _) = current_thread_context_switches()?;
    if accounting_flush_tid_after != accounting_flush_tid
        || blocking_sleep_returned_monotonic_ns < blocking_sleep_deadline_monotonic_ns
        || accounting_flush_voluntary_switches_after <= accounting_flush_voluntary_switches_before
    {
        return Err(invalid_data(
            "blocking accounting flush did not prove a voluntary context switch",
        ));
    }

    let cgroup_cpu_before_host_sample =
        parse_cgroup_cpu_stat(&fs::read_to_string(cgroup_directory.join("cpu.stat"))?)?;
    let host_sample_before_monotonic_ns = monotonic_time_ns()?;
    let schedstat_contents = fs::read_to_string("/proc/schedstat")?;
    let schedstat_read_finished_monotonic_ns = monotonic_time_ns()?;
    let cpu_schedstat = parse_schedstat_cpu(&schedstat_contents, cpu)?;
    let cpu_stat = fs::read_to_string("/proc/stat")?;
    let host_sample_after_monotonic_ns = monotonic_time_ns()?;
    let sampled_cpu = current_cpu()?;
    let sampled_unix_ns = unix_time_ns()?;
    let cgroup_cpu_after_host_sample =
        parse_cgroup_cpu_stat(&fs::read_to_string(cgroup_directory.join("cpu.stat"))?)?;
    let cgroup_cpu_usage_usec_before_host_sample = cgroup_cpu_before_host_sample.usage_usec;
    let cgroup_cpu_usage_usec_after_host_sample = cgroup_cpu_after_host_sample.usage_usec;
    if cgroup_cpu_usage_usec_after_host_sample < cgroup_cpu_usage_usec_before_host_sample {
        return Err(invalid_data(
            "cgroup CPU usage moved backwards across the host sample",
        ));
    }
    let cgroup_path_after = unified_cgroup_path(&fs::read_to_string("/proc/self/cgroup")?)?;
    if cgroup_path_after != cgroup_path {
        return Err(invalid_data(
            "current task changed unified cgroup during the host sample",
        ));
    }

    let cpu_stat_sample = parse_cpu_stat_sample(&cpu_stat, cpu)?;
    let cpu_total_ticks = cpu_stat_sample.total_ticks;
    let cpu_idle_ticks = cpu_stat_sample.idle_ticks;
    let (excluded_smt_total_ticks, excluded_smt_idle_ticks) =
        parse_cpu_stat(&cpu_stat, excluded_smt_sibling)?;
    let cgroup_process_ids =
        parse_cgroup_process_ids(&fs::read_to_string(cgroup_directory.join("cgroup.procs"))?)?;
    let cgroup_thread_ids = parse_cgroup_process_ids(&fs::read_to_string(
        cgroup_directory.join("cgroup.threads"),
    )?)?;
    let (cgroup_nr_descendants, cgroup_nr_dying_descendants) =
        parse_cgroup_topology(&fs::read_to_string(cgroup_directory.join("cgroup.stat"))?)?;
    let pressure = parse_pressure_totals(
        &fs::read_to_string("/proc/pressure/cpu")?,
        &fs::read_to_string("/proc/pressure/memory")?,
        &fs::read_to_string("/proc/pressure/io")?,
    )?;
    let process_status = fs::read_to_string("/proc/self/status")?;
    let actual_affinity = status_value(&process_status, "Cpus_allowed_list:")?;
    let actual_cpus = parse_cpu_list(&actual_affinity)?;
    if !actual_cpus.contains(&cpu) {
        return Err(invalid_data(format!(
            "requested cpu{cpu} is absent from Cpus_allowed_list={actual_affinity}"
        )));
    }

    let (effective_cpuset, cpuset_path) = read_effective_cpuset(&cgroup_path)?;
    let effective_cpus = parse_cpu_list(&effective_cpuset)?;
    if !effective_cpus.contains(&cpu) {
        return Err(invalid_data(format!(
            "requested cpu{cpu} is absent from {}={effective_cpuset}",
            cpuset_path.display()
        )));
    }
    let no_new_privileges = parse_status_u32(&process_status, "NoNewPrivs:")? == 1;
    let seccomp_mode = parse_status_u32(&process_status, "Seccomp:")?;
    let seccomp_filter_count = parse_status_u32(&process_status, "Seccomp_filters:")?;
    let thread_affinities = scan_thread_affinities()?;
    let sample_finished_monotonic_ns = monotonic_time_ns()?;

    Ok(CpuProcessSample {
        sampled_unix_ns,
        sample_started_monotonic_ns,
        sample_finished_monotonic_ns,
        blocking_sleep_started_monotonic_ns,
        blocking_sleep_deadline_monotonic_ns,
        blocking_sleep_returned_monotonic_ns,
        schedstat_read_finished_monotonic_ns,
        host_sample_before_monotonic_ns,
        host_sample_after_monotonic_ns,
        monotonic_clock_resolution_ns,
        cpu,
        sampled_cpu,
        excluded_smt_sibling,
        cpu_total_ticks,
        cpu_idle_ticks,
        cpu_irq_ticks: cpu_stat_sample.irq_ticks,
        cpu_softirq_ticks: cpu_stat_sample.softirq_ticks,
        cpu_steal_ticks: cpu_stat_sample.steal_ticks,
        excluded_smt_total_ticks,
        excluded_smt_idle_ticks,
        cpu_schedstat,
        cgroup_path,
        cgroup_inode,
        cgroup_type,
        cgroup_cpu_usage_usec_before_host_sample,
        cgroup_cpu_usage_usec_after_host_sample,
        cgroup_nr_periods_before_host_sample: cgroup_cpu_before_host_sample.nr_periods,
        cgroup_nr_periods_after_host_sample: cgroup_cpu_after_host_sample.nr_periods,
        cgroup_nr_throttled_before_host_sample: cgroup_cpu_before_host_sample.nr_throttled,
        cgroup_nr_throttled_after_host_sample: cgroup_cpu_after_host_sample.nr_throttled,
        cgroup_throttled_usec_before_host_sample: cgroup_cpu_before_host_sample.throttled_usec,
        cgroup_throttled_usec_after_host_sample: cgroup_cpu_after_host_sample.throttled_usec,
        cgroup_process_ids,
        cgroup_thread_ids,
        cgroup_nr_descendants,
        cgroup_nr_dying_descendants,
        accounting_flush_tid,
        accounting_flush_requested_ns,
        accounting_flush_observed_ns,
        accounting_flush_voluntary_switches_before,
        accounting_flush_voluntary_switches_after,
        clock_ticks_per_second,
        no_new_privileges,
        seccomp_mode,
        seccomp_filter_count,
        thread_affinities,
        pressure,
        actual_affinity,
        effective_cpuset,
        competing_build_processes: scan_competing_build_processes()?,
    })
}

/// Observe a bounded host-quiet window. Canonical callers use CPU 39, a
/// 30-second duration, and one-second buckets.
pub fn observe_host_quiet_window(
    cpu: u32,
    duration: Duration,
    bucket: Duration,
) -> io::Result<HostQuietWindowEvidence> {
    if duration.is_zero() || bucket.is_zero() || bucket > duration {
        return Err(invalid_input(
            "quiet-window duration and bucket must be non-zero, with bucket <= duration",
        ));
    }

    let mut samples = vec![cpu_process_sample(cpu)?];
    let started_unix_ns = unix_time_ns()?;
    let started = Instant::now();
    let deadline = started
        .checked_add(duration)
        .ok_or_else(|| invalid_input("quiet-window duration overflows Instant"))?;
    let mut next_elapsed = bucket;

    while next_elapsed < duration {
        sleep_until(
            started
                .checked_add(next_elapsed)
                .ok_or_else(|| invalid_input("quiet-window bucket overflows Instant"))?,
        );
        samples.push(cpu_process_sample(cpu)?);
        next_elapsed = next_elapsed
            .checked_add(bucket)
            .ok_or_else(|| invalid_input("quiet-window bucket sequence overflows Duration"))?;
    }
    sleep_until(deadline);
    samples.push(cpu_process_sample(cpu)?);
    let observed_duration = started.elapsed();
    let finished_unix_ns = unix_time_ns()?;

    quiet_window_from_samples(
        started_unix_ns,
        finished_unix_ns,
        observed_duration,
        samples,
    )
}

/// Compute CPU 39 activity not attributable to the pinned benchmark process.
pub fn child_interference(
    start: &CpuProcessSample,
    end: &CpuProcessSample,
    operation_started_monotonic_ns: u64,
    operation_finished_monotonic_ns: u64,
) -> io::Result<ChildInterferenceEvidence> {
    let sample_elapsed_ns = checked_delta(
        end.sampled_unix_ns,
        start.sampled_unix_ns,
        "child sample unix time",
    )?;
    let operation_elapsed_ns = checked_delta(
        operation_finished_monotonic_ns,
        operation_started_monotonic_ns,
        "measured operation monotonic time",
    )?;
    if operation_elapsed_ns == 0
        || sample_elapsed_ns < operation_elapsed_ns
        || start.sample_finished_monotonic_ns > operation_started_monotonic_ns
        || operation_finished_monotonic_ns > end.sample_started_monotonic_ns
    {
        return Err(invalid_data(
            "child samples do not contain the non-zero measured operation interval",
        ));
    }
    validate_pressure_monotonic(start.pressure, end.pressure)?;
    let process_id = std::process::id();
    validate_child_endpoint(start, process_id)?;
    validate_child_endpoint(end, process_id)?;
    if start.actual_affinity != end.actual_affinity
        || start.effective_cpuset != end.effective_cpuset
        || start.cgroup_path != end.cgroup_path
        || start.cgroup_inode != end.cgroup_inode
        || start.clock_ticks_per_second != end.clock_ticks_per_second
        || start.cpu_schedstat.version != end.cpu_schedstat.version
        || start.monotonic_clock_resolution_ns != end.monotonic_clock_resolution_ns
        || start.seccomp_filter_count != end.seccomp_filter_count
    {
        return Err(invalid_data(
            "child confinement or accounting domain changed during measurement",
        ));
    }

    checked_delta(
        end.cpu_schedstat.timestamp,
        start.cpu_schedstat.timestamp,
        "schedstat timestamp",
    )?;
    checked_delta(
        end.cpu_schedstat.wait_ns,
        start.cpu_schedstat.wait_ns,
        "cpu39 schedstat wait time",
    )?;
    let timeslice_delta = checked_delta(
        end.cpu_schedstat.timeslices,
        start.cpu_schedstat.timeslices,
        "cpu39 schedstat timeslices",
    )?;
    if timeslice_delta == 0 {
        return Err(invalid_data(
            "cpu39 schedstat timeslices did not advance across the operation",
        ));
    }
    let cpu39_scheduled_runtime_outer_ns = checked_delta(
        end.cpu_schedstat.runtime_ns,
        start.cpu_schedstat.runtime_ns,
        "cpu39 scheduled runtime",
    )?;
    let cgroup_cpu_inner_delta_usec = checked_delta(
        end.cgroup_cpu_usage_usec_before_host_sample,
        start.cgroup_cpu_usage_usec_after_host_sample,
        "inner cgroup CPU usage",
    )?;
    checked_delta(
        end.cgroup_nr_periods_before_host_sample,
        start.cgroup_nr_periods_after_host_sample,
        "inner cgroup CPU periods",
    )?;
    if end.cgroup_nr_throttled_before_host_sample != start.cgroup_nr_throttled_after_host_sample
        || end.cgroup_throttled_usec_before_host_sample
            != start.cgroup_throttled_usec_after_host_sample
    {
        return Err(invalid_data(
            "child cgroup was CPU-throttled during the measured operation",
        ));
    }
    let irq_delta_ticks = checked_delta(end.cpu_irq_ticks, start.cpu_irq_ticks, "cpu39 IRQ ticks")?
        .checked_add(checked_delta(
            end.cpu_softirq_ticks,
            start.cpu_softirq_ticks,
            "cpu39 softirq ticks",
        )?)
        .and_then(|value| {
            value.checked_add(
                checked_delta(
                    end.cpu_steal_ticks,
                    start.cpu_steal_ticks,
                    "cpu39 steal ticks",
                )
                .ok()?,
            )
        })
        .ok_or_else(|| invalid_data("cpu39 IRQ/softirq/steal delta overflow"))?;
    let end_current_pending_upper_bound_ns = checked_delta(
        end.schedstat_read_finished_monotonic_ns,
        end.blocking_sleep_deadline_monotonic_ns,
        "end current scheduler slice upper bound",
    )?
    .checked_add(
        end.monotonic_clock_resolution_ns
            .checked_mul(2)
            .ok_or_else(|| invalid_data("monotonic resolution allowance overflow"))?,
    )
    .ok_or_else(|| invalid_data("end current scheduler slice upper bound overflow"))?;
    let cpu39_bounds = conservative_scheduled_interference_bounds(
        cpu39_scheduled_runtime_outer_ns,
        cgroup_cpu_inner_delta_usec,
        end_current_pending_upper_bound_ns,
        irq_delta_ticks,
        operation_elapsed_ns,
        start.monotonic_clock_resolution_ns,
        start.clock_ticks_per_second,
    )?;
    let sibling_total_delta = checked_delta(
        end.excluded_smt_total_ticks,
        start.excluded_smt_total_ticks,
        "excluded SMT sibling total ticks",
    )?;
    let sibling_idle_delta = checked_delta(
        end.excluded_smt_idle_ticks,
        start.excluded_smt_idle_ticks,
        "excluded SMT sibling idle ticks",
    )?;
    let excluded_smt_nonidle_upper_bound_ns = conservative_proc_stat_nonidle_upper_bound_ns(
        sibling_total_delta,
        sibling_idle_delta,
        start.clock_ticks_per_second,
    )?;
    let excluded_smt_sibling_busy_upper_bound_bps = ratio_bps_ceil(
        excluded_smt_nonidle_upper_bound_ns,
        cpu39_bounds.operation_elapsed_lower_bound_ns,
    )?;

    Ok(ChildInterferenceEvidence {
        start: start.clone(),
        end: end.clone(),
        operation_started_monotonic_ns,
        operation_finished_monotonic_ns,
        operation_elapsed_ns,
        operation_elapsed_lower_bound_ns: cpu39_bounds.operation_elapsed_lower_bound_ns,
        cgroup_cpu_inner_delta_usec,
        cgroup_cpu_usage_floor_lower_bound_ns: cpu39_bounds.cgroup_cpu_usage_floor_lower_bound_ns,
        end_current_pending_upper_bound_ns,
        own_cpu_lower_bound_ns: cpu39_bounds.own_cpu_lower_bound_ns,
        cpu39_scheduled_runtime_outer_ns,
        cpu39_external_scheduled_runtime_upper_bound_ns: cpu39_bounds
            .external_scheduled_runtime_upper_ns,
        cpu39_proc_stat_side_charge_upper_bound_ns: cpu39_bounds
            .proc_stat_side_charge_upper_bound_ns,
        cpu39_combined_external_upper_bound_ns: cpu39_bounds.combined_external_upper_bound_ns,
        external_cpu39_busy_upper_bound_bps: cpu39_bounds.busy_upper_bound_bps,
        excluded_smt_nonidle_upper_bound_ns,
        excluded_smt_sibling_busy_upper_bound_bps,
    })
}

fn validate_child_endpoint(sample: &CpuProcessSample, process_id: u32) -> io::Result<()> {
    let expected_affinity = BTreeSet::from([39]);
    let requested_flush_ns = u64::try_from(ACCOUNTING_FLUSH_DURATION.as_nanos())
        .map_err(|_| invalid_data("accounting flush duration does not fit in u64"))?;
    if sample.cpu != 39
        || sample.sampled_cpu != 39
        || sample.excluded_smt_sibling != 79
        || parse_cpu_list(&sample.actual_affinity)? != expected_affinity
        || !parse_cpu_list(&sample.effective_cpuset)?.contains(&39)
        || sample.clock_ticks_per_second != REQUIRED_CLOCK_TICKS_PER_SECOND
        || sample.cpu_schedstat.version != 17
    {
        return Err(invalid_data(format!(
            "child endpoint CPU contract is invalid: requested={}, sampled={}, sibling={}, affinity={}, cpuset={}, USER_HZ={}, schedstat={}",
            sample.cpu,
            sample.sampled_cpu,
            sample.excluded_smt_sibling,
            sample.actual_affinity,
            sample.effective_cpuset,
            sample.clock_ticks_per_second,
            sample.cpu_schedstat.version,
        )));
    }
    if sample.cgroup_path.is_empty()
        || sample.cgroup_inode == 0
        || sample.cgroup_type != "domain"
        || sample.cgroup_process_ids != [process_id]
        || sample.cgroup_nr_descendants != 0
        || sample.cgroup_nr_dying_descendants != 0
        || !sample
            .cgroup_thread_ids
            .contains(&sample.accounting_flush_tid)
    {
        return Err(invalid_data(format!(
            "child endpoint cgroup contract is invalid: path={:?}, inode={}, type={:?}, processes={:?}, threads={:?}, sampler_tid={}, descendants={}, dying_descendants={}",
            sample.cgroup_path,
            sample.cgroup_inode,
            sample.cgroup_type,
            sample.cgroup_process_ids,
            sample.cgroup_thread_ids,
            sample.accounting_flush_tid,
            sample.cgroup_nr_descendants,
            sample.cgroup_nr_dying_descendants,
        )));
    }
    if sample.accounting_flush_requested_ns != requested_flush_ns
        || sample.accounting_flush_observed_ns < sample.accounting_flush_requested_ns
        || sample.accounting_flush_voluntary_switches_after
            <= sample.accounting_flush_voluntary_switches_before
    {
        return Err(invalid_data(format!(
            "child endpoint blocking switch contract is invalid: requested={}, observed={}, nvcsw={}..{}",
            sample.accounting_flush_requested_ns,
            sample.accounting_flush_observed_ns,
            sample.accounting_flush_voluntary_switches_before,
            sample.accounting_flush_voluntary_switches_after,
        )));
    }
    let sampled_thread_ids = sample
        .thread_affinities
        .iter()
        .map(|thread| thread.tid)
        .collect::<Vec<_>>();
    if !sample.no_new_privileges
        || sample.seccomp_mode != 2
        || sample.seccomp_filter_count == 0
        || !thread_affinities_are_exact(&sample.thread_affinities, 39, process_id)
        || !sampled_thread_ids.contains(&sample.accounting_flush_tid)
        || sample.cgroup_thread_ids != sampled_thread_ids
    {
        return Err(invalid_data(format!(
            "child endpoint thread/seccomp contract is invalid: nnp={}, seccomp={}, filters={}, sampler_tid={}, cgroup_threads={:?}, affinity_threads={:?}",
            sample.no_new_privileges,
            sample.seccomp_mode,
            sample.seccomp_filter_count,
            sample.accounting_flush_tid,
            sample.cgroup_thread_ids,
            sample.thread_affinities,
        )));
    }
    checked_delta(
        sample.cgroup_cpu_usage_usec_after_host_sample,
        sample.cgroup_cpu_usage_usec_before_host_sample,
        "cgroup CPU usage across host sample",
    )?;
    checked_delta(
        sample.cgroup_nr_periods_after_host_sample,
        sample.cgroup_nr_periods_before_host_sample,
        "cgroup CPU periods across host sample",
    )?;
    if sample.cgroup_nr_throttled_after_host_sample != sample.cgroup_nr_throttled_before_host_sample
        || sample.cgroup_throttled_usec_after_host_sample
            != sample.cgroup_throttled_usec_before_host_sample
    {
        return Err(invalid_data(
            "child cgroup was CPU-throttled during an endpoint sample",
        ));
    }
    let expected_deadline = sample
        .blocking_sleep_started_monotonic_ns
        .checked_add(sample.accounting_flush_requested_ns)
        .ok_or_else(|| invalid_data("blocking sleep deadline overflow"))?;
    let observed_flush = checked_delta(
        sample.blocking_sleep_returned_monotonic_ns,
        sample.blocking_sleep_started_monotonic_ns,
        "blocking accounting flush",
    )?;
    if sample.sample_started_monotonic_ns > sample.blocking_sleep_started_monotonic_ns
        || expected_deadline != sample.blocking_sleep_deadline_monotonic_ns
        || sample.blocking_sleep_returned_monotonic_ns < sample.blocking_sleep_deadline_monotonic_ns
        || sample.accounting_flush_observed_ns != observed_flush
        || sample.blocking_sleep_returned_monotonic_ns > sample.host_sample_before_monotonic_ns
        || sample.host_sample_before_monotonic_ns > sample.schedstat_read_finished_monotonic_ns
        || sample.schedstat_read_finished_monotonic_ns > sample.host_sample_after_monotonic_ns
        || sample.host_sample_after_monotonic_ns > sample.sample_finished_monotonic_ns
        || sample.monotonic_clock_resolution_ns == 0
    {
        return Err(invalid_data(
            "child endpoint monotonic ordering or blocking deadline is invalid",
        ));
    }
    Ok(())
}

/// Bound non-idle `/proc/stat` time despite independent floor conversion of
/// its six cumulative non-idle fields to USER_HZ.
pub(crate) fn conservative_proc_stat_nonidle_upper_bound_ns(
    total_delta_ticks: u64,
    idle_delta_ticks: u64,
    ticks_per_second: u64,
) -> io::Result<u64> {
    if ticks_per_second != REQUIRED_CLOCK_TICKS_PER_SECOND
        || NANOSECONDS_PER_SECOND % ticks_per_second != 0
    {
        return Err(invalid_data(
            "the frozen evaluator requires USER_HZ=100 with an exact nanosecond tick",
        ));
    }
    if idle_delta_ticks > total_delta_ticks {
        return Err(invalid_data("CPU idle delta exceeds CPU total delta"));
    }
    let nonidle_delta_ticks = total_delta_ticks - idle_delta_ticks;
    let tick_ns = NANOSECONDS_PER_SECOND / ticks_per_second;
    let nonidle_upper_ticks = nonidle_delta_ticks
        .checked_add(PROC_STAT_NONIDLE_COUNTERS)
        .ok_or_else(|| invalid_data("CPU non-idle tick upper bound overflow"))?;
    u128::from(nonidle_upper_ticks)
        .checked_mul(u128::from(tick_ns))
        .and_then(|value| u64::try_from(value).ok())
        .ok_or_else(|| invalid_data("CPU non-idle nanosecond upper bound overflow"))
}

pub(crate) fn conservative_scheduled_interference_bounds(
    scheduled_runtime_outer_ns: u64,
    cgroup_cpu_inner_delta_usec: u64,
    end_endpoint_pending_upper_ns: u64,
    irq_softirq_steal_delta_ticks: u64,
    operation_elapsed_ns: u64,
    monotonic_clock_resolution_ns: u64,
    ticks_per_second: u64,
) -> io::Result<ScheduledInterferenceBounds> {
    if operation_elapsed_ns == 0 || monotonic_clock_resolution_ns == 0 {
        return Err(invalid_data("measured operation duration must be non-zero"));
    }
    if ticks_per_second != REQUIRED_CLOCK_TICKS_PER_SECOND
        || NANOSECONDS_PER_SECOND % ticks_per_second != 0
    {
        return Err(invalid_data(
            "the frozen evaluator requires USER_HZ=100 with an exact nanosecond tick",
        ));
    }
    let cgroup_cpu_usage_floor_lower_bound_ns = u128::from(cgroup_cpu_inner_delta_usec)
        .checked_mul(1_000)
        .and_then(|value| u64::try_from(value).ok())
        .ok_or_else(|| invalid_data("cgroup CPU lower bound overflow"))?
        .saturating_sub(999);
    let own_cpu_lower_bound_ns =
        cgroup_cpu_usage_floor_lower_bound_ns.saturating_sub(end_endpoint_pending_upper_ns);
    let external_scheduled_runtime_upper_ns = scheduled_runtime_outer_ns
        .checked_sub(own_cpu_lower_bound_ns)
        .ok_or_else(|| {
            invalid_data("cgroup CPU lower bound exceeds CPU39 scheduled runtime outer bound")
        })?;
    let tick_ns = NANOSECONDS_PER_SECOND / ticks_per_second;
    let proc_stat_side_charge_upper_bound_ns = u128::from(
        irq_softirq_steal_delta_ticks
            .checked_add(PROC_STAT_IRQ_COUNTERS)
            .ok_or_else(|| invalid_data("IRQ/softirq/steal tick upper bound overflow"))?,
    )
    .checked_mul(u128::from(tick_ns))
    .and_then(|value| u64::try_from(value).ok())
    .ok_or_else(|| invalid_data("IRQ/softirq/steal nanosecond upper bound overflow"))?;
    let combined_external_upper_bound_ns = external_scheduled_runtime_upper_ns
        .checked_add(proc_stat_side_charge_upper_bound_ns)
        .ok_or_else(|| invalid_data("combined CPU39 interference upper bound overflow"))?;
    let operation_clock_error_ns = monotonic_clock_resolution_ns
        .checked_mul(2)
        .ok_or_else(|| invalid_data("operation clock resolution allowance overflow"))?;
    let operation_elapsed_lower_bound_ns = operation_elapsed_ns
        .checked_sub(operation_clock_error_ns)
        .filter(|value| *value > 0)
        .ok_or_else(|| invalid_data("operation duration is below clock resolution"))?;
    let busy_upper_bound_bps = ratio_bps_ceil(
        combined_external_upper_bound_ns,
        operation_elapsed_lower_bound_ns,
    )?;
    Ok(ScheduledInterferenceBounds {
        cgroup_cpu_usage_floor_lower_bound_ns,
        own_cpu_lower_bound_ns,
        external_scheduled_runtime_upper_ns,
        proc_stat_side_charge_upper_bound_ns,
        combined_external_upper_bound_ns,
        operation_elapsed_lower_bound_ns,
        busy_upper_bound_bps,
    })
}

pub(crate) fn thread_affinities_are_exact(
    threads: &[ThreadAffinityEvidence],
    cpu: u32,
    required_tid: u32,
) -> bool {
    let expected = BTreeSet::from([cpu]);
    !threads.is_empty()
        && threads.iter().any(|thread| thread.tid == required_tid)
        && threads.windows(2).all(|pair| pair[0].tid < pair[1].tid)
        && threads
            .iter()
            .all(|thread| parse_cpu_list(&thread.allowed_cpus).is_ok_and(|cpus| cpus == expected))
}

fn quiet_window_from_samples(
    started_unix_ns: u64,
    finished_unix_ns: u64,
    observed_duration: Duration,
    samples: Vec<CpuProcessSample>,
) -> io::Result<HostQuietWindowEvidence> {
    if samples.len() < 2 {
        return Err(invalid_data(
            "quiet-window evidence requires at least two samples",
        ));
    }
    let unix_duration_ns =
        checked_delta(finished_unix_ns, started_unix_ns, "quiet-window unix time")?;
    let duration_ns = u64::try_from(observed_duration.as_nanos())
        .map_err(|_| invalid_data("quiet-window monotonic duration does not fit in u64"))?;
    let clock_delta_ns = unix_duration_ns.abs_diff(duration_ns);
    let clock_tolerance_ns = (duration_ns / 100).max(5_000_000);
    if clock_delta_ns > clock_tolerance_ns {
        return Err(invalid_data(format!(
            "Unix and monotonic quiet-window durations differ by {clock_delta_ns}ns"
        )));
    }
    let duration_us = duration_ns / 1_000;
    if duration_us == 0 {
        return Err(invalid_data(
            "quiet-window duration is below one microsecond",
        ));
    }

    let first = samples
        .first()
        .ok_or_else(|| invalid_data("missing first quiet-window sample"))?;
    let last = samples
        .last()
        .ok_or_else(|| invalid_data("missing last quiet-window sample"))?;
    let cpu_total_delta_ticks = checked_delta(
        last.cpu_total_ticks,
        first.cpu_total_ticks,
        "cpu total ticks",
    )?;
    let cpu_idle_delta_ticks =
        checked_delta(last.cpu_idle_ticks, first.cpu_idle_ticks, "cpu idle ticks")?;
    if cpu_idle_delta_ticks > cpu_total_delta_ticks {
        return Err(invalid_data("cpu idle delta exceeds cpu total delta"));
    }
    let overall_idle_bps = ratio_bps(cpu_idle_delta_ticks, cpu_total_delta_ticks)?;
    let excluded_smt_total_delta_ticks = checked_delta(
        last.excluded_smt_total_ticks,
        first.excluded_smt_total_ticks,
        "excluded SMT total ticks",
    )?;
    let excluded_smt_idle_delta_ticks = checked_delta(
        last.excluded_smt_idle_ticks,
        first.excluded_smt_idle_ticks,
        "excluded SMT idle ticks",
    )?;
    if excluded_smt_idle_delta_ticks > excluded_smt_total_delta_ticks {
        return Err(invalid_data("excluded SMT idle delta exceeds total delta"));
    }
    let excluded_smt_overall_idle_bps = ratio_bps(
        excluded_smt_idle_delta_ticks,
        excluded_smt_total_delta_ticks,
    )?;

    let mut worst_bucket_idle_bps = BPS_SCALE;
    let mut excluded_smt_worst_bucket_idle_bps = BPS_SCALE;
    let mut bucket_total_delta_ticks = Vec::with_capacity(samples.len().saturating_sub(1));
    let mut bucket_idle_delta_ticks = Vec::with_capacity(samples.len().saturating_sub(1));
    let mut excluded_smt_bucket_total_delta_ticks =
        Vec::with_capacity(samples.len().saturating_sub(1));
    let mut excluded_smt_bucket_idle_delta_ticks =
        Vec::with_capacity(samples.len().saturating_sub(1));
    let mut competing_build_processes = BTreeSet::new();
    for sample in &samples {
        if sample.actual_affinity != first.actual_affinity
            || sample.effective_cpuset != first.effective_cpuset
            || sample.cpu != first.cpu
            || sample.excluded_smt_sibling != first.excluded_smt_sibling
        {
            return Err(invalid_data(
                "affinity or effective cpuset changed during quiet window",
            ));
        }
        parse_cpu_list(&sample.actual_affinity)?;
        parse_cpu_list(&sample.effective_cpuset)?;
        competing_build_processes.extend(sample.competing_build_processes.iter().cloned());
    }
    for pair in samples.windows(2) {
        let total_delta = checked_delta(
            pair[1].cpu_total_ticks,
            pair[0].cpu_total_ticks,
            "bucket cpu total ticks",
        )?;
        let idle_delta = checked_delta(
            pair[1].cpu_idle_ticks,
            pair[0].cpu_idle_ticks,
            "bucket cpu idle ticks",
        )?;
        if idle_delta > total_delta {
            return Err(invalid_data(
                "bucket cpu idle delta exceeds cpu total delta",
            ));
        }
        bucket_total_delta_ticks.push(total_delta);
        bucket_idle_delta_ticks.push(idle_delta);
        worst_bucket_idle_bps = worst_bucket_idle_bps.min(ratio_bps(idle_delta, total_delta)?);
        let sibling_total_delta = checked_delta(
            pair[1].excluded_smt_total_ticks,
            pair[0].excluded_smt_total_ticks,
            "bucket excluded SMT total ticks",
        )?;
        let sibling_idle_delta = checked_delta(
            pair[1].excluded_smt_idle_ticks,
            pair[0].excluded_smt_idle_ticks,
            "bucket excluded SMT idle ticks",
        )?;
        if sibling_idle_delta > sibling_total_delta {
            return Err(invalid_data(
                "bucket excluded SMT idle delta exceeds total delta",
            ));
        }
        excluded_smt_bucket_total_delta_ticks.push(sibling_total_delta);
        excluded_smt_bucket_idle_delta_ticks.push(sibling_idle_delta);
        excluded_smt_worst_bucket_idle_bps = excluded_smt_worst_bucket_idle_bps
            .min(ratio_bps(sibling_idle_delta, sibling_total_delta)?);
        validate_pressure_monotonic(pair[0].pressure, pair[1].pressure)?;
    }

    let pressure_start = first.pressure;
    let pressure_end = last.pressure;
    let cpu_some_pressure_delta_bps = pressure_rate_bps(
        pressure_start.cpu_some_us,
        pressure_end.cpu_some_us,
        duration_us,
        "cpu some pressure",
    )?;
    let memory_full_pressure_delta_bps = pressure_rate_bps(
        pressure_start.memory_full_us,
        pressure_end.memory_full_us,
        duration_us,
        "memory full pressure",
    )?;
    let memory_some_pressure_delta_bps = pressure_rate_bps(
        pressure_start.memory_some_us,
        pressure_end.memory_some_us,
        duration_us,
        "memory some pressure",
    )?;
    let io_some_pressure_delta_bps = pressure_rate_bps(
        pressure_start.io_some_us,
        pressure_end.io_some_us,
        duration_us,
        "io some pressure",
    )?;
    let io_full_pressure_delta_bps = pressure_rate_bps(
        pressure_start.io_full_us,
        pressure_end.io_full_us,
        duration_us,
        "io full pressure",
    )?;
    let competing_build_processes = competing_build_processes.into_iter().collect::<Vec<_>>();
    let passed = overall_idle_bps >= QUIET_OVERALL_IDLE_BPS
        && worst_bucket_idle_bps >= QUIET_BUCKET_IDLE_BPS
        && excluded_smt_overall_idle_bps >= QUIET_SMT_OVERALL_IDLE_BPS
        && excluded_smt_worst_bucket_idle_bps >= QUIET_SMT_BUCKET_IDLE_BPS
        && cpu_some_pressure_delta_bps <= QUIET_CPU_SOME_PRESSURE_BPS
        && memory_some_pressure_delta_bps <= QUIET_MEMORY_SOME_PRESSURE_BPS
        && memory_full_pressure_delta_bps <= QUIET_MEMORY_FULL_PRESSURE_BPS
        && io_some_pressure_delta_bps <= QUIET_IO_SOME_PRESSURE_BPS
        && io_full_pressure_delta_bps <= QUIET_IO_FULL_PRESSURE_BPS
        && competing_build_processes.is_empty();

    Ok(HostQuietWindowEvidence {
        cpu: first.cpu,
        excluded_smt_sibling: first.excluded_smt_sibling,
        started_unix_ns,
        finished_unix_ns,
        duration_ms: duration_ns / 1_000_000,
        duration_us,
        sample_count: samples.len(),
        cpu_total_delta_ticks,
        cpu_idle_delta_ticks,
        overall_idle_bps,
        worst_bucket_idle_bps,
        bucket_total_delta_ticks,
        bucket_idle_delta_ticks,
        excluded_smt_total_delta_ticks,
        excluded_smt_idle_delta_ticks,
        excluded_smt_overall_idle_bps,
        excluded_smt_worst_bucket_idle_bps,
        excluded_smt_bucket_total_delta_ticks,
        excluded_smt_bucket_idle_delta_ticks,
        pressure_start,
        pressure_end,
        cpu_some_pressure_delta_bps,
        memory_some_pressure_delta_bps,
        memory_full_pressure_delta_bps,
        io_some_pressure_delta_bps,
        io_full_pressure_delta_bps,
        competing_build_processes,
        actual_affinity: first.actual_affinity.clone(),
        effective_cpuset: first.effective_cpuset.clone(),
        passed,
    })
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
struct ProcStatCpuSample {
    total_ticks: u64,
    idle_ticks: u64,
    irq_ticks: u64,
    softirq_ticks: u64,
    steal_ticks: u64,
}

fn parse_cpu_stat(contents: &str, cpu: u32) -> io::Result<(u64, u64)> {
    let sample = parse_cpu_stat_sample(contents, cpu)?;
    Ok((sample.total_ticks, sample.idle_ticks))
}

fn parse_cpu_stat_sample(contents: &str, cpu: u32) -> io::Result<ProcStatCpuSample> {
    let label = format!("cpu{cpu}");
    let mut match_value = None;
    for line in contents.lines() {
        let mut fields = line.split_whitespace();
        if fields.next() != Some(label.as_str()) {
            continue;
        }
        if match_value.is_some() {
            return Err(invalid_data(format!(
                "duplicate {label} line in /proc/stat"
            )));
        }
        let values = fields
            .map(|value| {
                value.parse::<u64>().map_err(|error| {
                    invalid_data(format!("invalid {label} counter {value:?}: {error}"))
                })
            })
            .collect::<io::Result<Vec<_>>>()?;
        if values.len() < 8 {
            return Err(invalid_data(format!(
                "{label} has fewer than eight required counters"
            )));
        }
        let total = values[..8].iter().try_fold(0_u64, |sum, value| {
            sum.checked_add(*value)
                .ok_or_else(|| invalid_data(format!("{label} total ticks overflow")))
        })?;
        let idle = values[3]
            .checked_add(values[4])
            .ok_or_else(|| invalid_data(format!("{label} idle ticks overflow")))?;
        match_value = Some(ProcStatCpuSample {
            total_ticks: total,
            idle_ticks: idle,
            irq_ticks: values[5],
            softirq_ticks: values[6],
            steal_ticks: values[7],
        });
    }
    match_value.ok_or_else(|| invalid_data(format!("missing {label} line in /proc/stat")))
}

pub(crate) fn parse_schedstat_cpu(contents: &str, cpu: u32) -> io::Result<SchedstatCpuSample> {
    let label = format!("cpu{cpu}");
    let mut version = None;
    let mut timestamp = None;
    let mut cpu_values = None;
    for line in contents.lines() {
        let mut fields = line.split_whitespace();
        let Some(first) = fields.next() else {
            continue;
        };
        if first == "version" {
            if version.is_some() {
                return Err(invalid_data("duplicate /proc/schedstat version line"));
            }
            let value = fields
                .next()
                .ok_or_else(|| invalid_data("missing /proc/schedstat version"))?;
            if fields.next().is_some() {
                return Err(invalid_data("invalid /proc/schedstat version line"));
            }
            version = Some(value.parse::<u32>().map_err(|error| {
                invalid_data(format!(
                    "invalid /proc/schedstat version {value:?}: {error}"
                ))
            })?);
            continue;
        }
        if first == "timestamp" {
            if timestamp.is_some() {
                return Err(invalid_data("duplicate /proc/schedstat timestamp line"));
            }
            let value = fields
                .next()
                .ok_or_else(|| invalid_data("missing /proc/schedstat timestamp"))?;
            if fields.next().is_some() {
                return Err(invalid_data("invalid /proc/schedstat timestamp line"));
            }
            timestamp = Some(value.parse::<u64>().map_err(|error| {
                invalid_data(format!(
                    "invalid /proc/schedstat timestamp {value:?}: {error}"
                ))
            })?);
            continue;
        }
        if first != label {
            continue;
        }
        if cpu_values.is_some() {
            return Err(invalid_data(format!(
                "duplicate {label} line in /proc/schedstat"
            )));
        }
        let values = fields
            .map(|value| {
                value.parse::<u64>().map_err(|error| {
                    invalid_data(format!(
                        "invalid {label} schedstat counter {value:?}: {error}"
                    ))
                })
            })
            .collect::<io::Result<Vec<_>>>()?;
        if values.len() != 9 || values[..6].iter().any(|value| *value != 0) {
            return Err(invalid_data(format!(
                "{label} does not match the frozen schedstat v17 nine-field layout"
            )));
        }
        cpu_values = Some((values[6], values[7], values[8]));
    }
    let version = version.ok_or_else(|| invalid_data("missing /proc/schedstat version line"))?;
    if version != 17 {
        return Err(invalid_data(format!(
            "the frozen evaluator requires /proc/schedstat version 17, found {version}"
        )));
    }
    let (runtime_ns, wait_ns, timeslices) = cpu_values
        .ok_or_else(|| invalid_data(format!("missing {label} line in /proc/schedstat")))?;
    Ok(SchedstatCpuSample {
        version,
        timestamp: timestamp
            .ok_or_else(|| invalid_data("missing /proc/schedstat timestamp line"))?,
        runtime_ns,
        wait_ns,
        timeslices,
    })
}

pub(crate) fn parse_cgroup_cpu_usage_usec(contents: &str) -> io::Result<u64> {
    let mut usage_usec = None;
    for line in contents.lines() {
        let mut fields = line.split_whitespace();
        let Some(key) = fields.next() else {
            continue;
        };
        let value = fields
            .next()
            .ok_or_else(|| invalid_data(format!("missing value for cgroup cpu.stat {key}")))?;
        if fields.next().is_some() {
            return Err(invalid_data(format!(
                "invalid cgroup cpu.stat line for {key}"
            )));
        }
        let value = value.parse::<u64>().map_err(|error| {
            invalid_data(format!("invalid cgroup cpu.stat {key} value: {error}"))
        })?;
        if key == "usage_usec" && usage_usec.replace(value).is_some() {
            return Err(invalid_data("duplicate cgroup cpu.stat usage_usec"));
        }
    }
    usage_usec.ok_or_else(|| invalid_data("missing cgroup cpu.stat usage_usec"))
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
struct CgroupCpuStatSample {
    usage_usec: u64,
    nr_periods: u64,
    nr_throttled: u64,
    throttled_usec: u64,
}

fn parse_cgroup_cpu_stat(contents: &str) -> io::Result<CgroupCpuStatSample> {
    let usage_usec = parse_cgroup_cpu_usage_usec(contents)?;
    Ok(CgroupCpuStatSample {
        usage_usec,
        nr_periods: parse_unique_keyed_u64(contents, "nr_periods", "cgroup cpu.stat")?,
        nr_throttled: parse_unique_keyed_u64(contents, "nr_throttled", "cgroup cpu.stat")?,
        throttled_usec: parse_unique_keyed_u64(contents, "throttled_usec", "cgroup cpu.stat")?,
    })
}

fn parse_unique_keyed_u64(contents: &str, wanted: &str, source: &str) -> io::Result<u64> {
    let mut result = None;
    for line in contents.lines() {
        let mut fields = line.split_whitespace();
        let Some(key) = fields.next() else {
            continue;
        };
        if key != wanted {
            continue;
        }
        let value = fields
            .next()
            .ok_or_else(|| invalid_data(format!("missing {wanted} value in {source}")))?;
        if fields.next().is_some() || result.is_some() {
            return Err(invalid_data(format!(
                "invalid or duplicate {wanted} in {source}"
            )));
        }
        result = Some(value.parse::<u64>().map_err(|error| {
            invalid_data(format!("invalid {wanted} value in {source}: {error}"))
        })?);
    }
    result.ok_or_else(|| invalid_data(format!("missing {wanted} in {source}")))
}

fn parse_cgroup_process_ids(contents: &str) -> io::Result<Vec<u32>> {
    let mut process_ids = BTreeSet::new();
    for line in contents.lines() {
        if line.is_empty() || line.trim() != line {
            return Err(invalid_data("invalid whitespace in cgroup.procs"));
        }
        let process_id = line
            .parse::<u32>()
            .map_err(|error| invalid_data(format!("invalid cgroup.procs pid: {error}")))?;
        if process_id == 0 || !process_ids.insert(process_id) {
            return Err(invalid_data("zero or duplicate pid in cgroup.procs"));
        }
    }
    if process_ids.is_empty() {
        return Err(invalid_data("cgroup.procs contains no processes"));
    }
    Ok(process_ids.into_iter().collect())
}

fn parse_cgroup_topology(contents: &str) -> io::Result<(u64, u64)> {
    let mut nr_descendants = None;
    let mut nr_dying_descendants = None;
    for line in contents.lines() {
        let mut fields = line.split_whitespace();
        let Some(key) = fields.next() else {
            continue;
        };
        let value = fields
            .next()
            .ok_or_else(|| invalid_data(format!("missing value for cgroup.stat {key}")))?;
        if fields.next().is_some() {
            return Err(invalid_data(format!("invalid cgroup.stat line for {key}")));
        }
        let value = value
            .parse::<u64>()
            .map_err(|error| invalid_data(format!("invalid cgroup.stat {key} value: {error}")))?;
        match key {
            "nr_descendants" if nr_descendants.replace(value).is_some() => {
                return Err(invalid_data("duplicate cgroup.stat nr_descendants"));
            }
            "nr_dying_descendants" if nr_dying_descendants.replace(value).is_some() => {
                return Err(invalid_data("duplicate cgroup.stat nr_dying_descendants"));
            }
            _ => {}
        }
    }
    Ok((
        nr_descendants.ok_or_else(|| invalid_data("missing cgroup.stat nr_descendants"))?,
        nr_dying_descendants
            .ok_or_else(|| invalid_data("missing cgroup.stat nr_dying_descendants"))?,
    ))
}

fn read_excluded_smt_sibling(cpu: u32) -> io::Result<u32> {
    let path = format!("/sys/devices/system/cpu/cpu{cpu}/topology/thread_siblings_list");
    let mut siblings = parse_cpu_list(&fs::read_to_string(&path)?)?;
    if siblings.len() != 2 || !siblings.remove(&cpu) {
        return Err(invalid_data(format!(
            "{path} must contain exactly cpu{cpu} and one SMT sibling"
        )));
    }
    siblings
        .into_iter()
        .next()
        .ok_or_else(|| invalid_data(format!("{path} lacks an excluded SMT sibling")))
}

fn parse_process_stat(contents: &str) -> io::Result<(u32, u64, u64)> {
    let open = contents
        .find('(')
        .ok_or_else(|| invalid_data("process stat is missing opening parenthesis"))?;
    let close = contents
        .rfind(')')
        .filter(|close| *close > open)
        .ok_or_else(|| invalid_data("process stat is missing closing parenthesis"))?;
    let pid = contents[..open]
        .trim()
        .parse::<u32>()
        .map_err(|error| invalid_data(format!("invalid process stat pid: {error}")))?;
    let suffix = contents
        .get(close + 1..)
        .ok_or_else(|| invalid_data("invalid process stat suffix"))?;
    if !suffix.starts_with(char::is_whitespace) {
        return Err(invalid_data(
            "process stat closing parenthesis is not followed by whitespace",
        ));
    }
    let fields = suffix.split_whitespace().collect::<Vec<_>>();
    if fields.len() < 20 || fields[0].len() != 1 {
        return Err(invalid_data(
            "process stat does not contain fields through starttime",
        ));
    }
    let utime = parse_stat_field(fields[11], "utime")?;
    let stime = parse_stat_field(fields[12], "stime")?;
    let ticks = utime
        .checked_add(stime)
        .ok_or_else(|| invalid_data("process CPU ticks overflow"))?;
    let start_ticks = parse_stat_field(fields[19], "starttime")?;
    Ok((pid, ticks, start_ticks))
}

fn parse_stat_field(value: &str, name: &str) -> io::Result<u64> {
    value
        .parse::<u64>()
        .map_err(|error| invalid_data(format!("invalid process stat {name}: {error}")))
}

fn parse_pressure_totals(cpu: &str, memory: &str, io_pressure: &str) -> io::Result<PressureTotals> {
    Ok(PressureTotals {
        cpu_some_us: parse_psi_total(cpu, "some", "cpu")?,
        memory_some_us: parse_psi_total(memory, "some", "memory")?,
        memory_full_us: parse_psi_total(memory, "full", "memory")?,
        io_some_us: parse_psi_total(io_pressure, "some", "io")?,
        io_full_us: parse_psi_total(io_pressure, "full", "io")?,
    })
}

fn parse_psi_total(contents: &str, kind: &str, resource: &str) -> io::Result<u64> {
    let mut result = None;
    for line in contents.lines() {
        let fields = line.split_whitespace().collect::<Vec<_>>();
        if fields.first().copied() != Some(kind) {
            continue;
        }
        if result.is_some() {
            return Err(invalid_data(format!(
                "duplicate {kind} line in {resource} PSI"
            )));
        }
        if fields.len() != 5 {
            return Err(invalid_data(format!(
                "invalid {kind} line field count in {resource} PSI"
            )));
        }
        for (index, prefix) in [(1, "avg10="), (2, "avg60="), (3, "avg300=")] {
            let value = fields[index]
                .strip_prefix(prefix)
                .ok_or_else(|| invalid_data(format!("missing {prefix} field in {resource} PSI")))?;
            let average = value.parse::<f64>().map_err(|error| {
                invalid_data(format!("invalid {prefix} field in {resource} PSI: {error}"))
            })?;
            if !average.is_finite() || average < 0.0 {
                return Err(invalid_data(format!(
                    "non-finite or negative {prefix} field in {resource} PSI"
                )));
            }
        }
        let total = fields[4]
            .strip_prefix("total=")
            .ok_or_else(|| invalid_data(format!("missing total field in {resource} PSI")))?;
        result = Some(total.parse::<u64>().map_err(|error| {
            invalid_data(format!("invalid total field in {resource} PSI: {error}"))
        })?);
    }
    result.ok_or_else(|| invalid_data(format!("missing {kind} line in {resource} PSI")))
}

fn parse_cpu_list(contents: &str) -> io::Result<BTreeSet<u32>> {
    let contents = contents.trim();
    if contents.is_empty() {
        return Err(invalid_data("CPU list is empty"));
    }
    let mut cpus = BTreeSet::new();
    for component in contents.split(',') {
        if component.is_empty() {
            return Err(invalid_data("CPU list contains an empty component"));
        }
        let mut range = component.split('-');
        let start = parse_cpu_id(
            range
                .next()
                .ok_or_else(|| invalid_data("CPU list component is empty"))?,
        )?;
        let end = match range.next() {
            Some(value) => parse_cpu_id(value)?,
            None => start,
        };
        if range.next().is_some() || start > end {
            return Err(invalid_data(format!(
                "invalid CPU list component {component:?}"
            )));
        }
        for cpu in start..=end {
            if !cpus.insert(cpu) {
                return Err(invalid_data(format!("duplicate cpu{cpu} in CPU list")));
            }
        }
    }
    Ok(cpus)
}

fn parse_cpu_id(value: &str) -> io::Result<u32> {
    let cpu = value
        .parse::<u32>()
        .map_err(|error| invalid_data(format!("invalid CPU id {value:?}: {error}")))?;
    if cpu > MAX_PLAUSIBLE_CPU_ID {
        return Err(invalid_data(format!("implausibly large CPU id {cpu}")));
    }
    Ok(cpu)
}

fn parse_competing_process(
    pid: u32,
    comm: &str,
    stat: &str,
) -> io::Result<Option<CompetingProcessEvidence>> {
    let comm = comm.trim_end_matches(['\r', '\n']);
    if !matches!(comm, "cargo" | "rustc" | "rustdoc") {
        return Ok(None);
    }
    if comm.is_empty() || comm.contains(['\r', '\n']) {
        return Err(invalid_data("invalid competing process comm"));
    }
    let (stat_pid, _, start_ticks) = parse_process_stat(stat)?;
    if stat_pid != pid {
        return Err(invalid_data(format!(
            "process identity changed while scanning pid {pid}: stat reports {stat_pid}"
        )));
    }
    Ok(Some(CompetingProcessEvidence {
        pid,
        comm: comm.to_string(),
        start_ticks,
    }))
}

fn scan_competing_build_processes() -> io::Result<Vec<CompetingProcessEvidence>> {
    let mut processes = BTreeSet::new();
    for entry in fs::read_dir("/proc")? {
        let entry = entry?;
        let Some(name) = entry.file_name().to_str().map(str::to_string) else {
            continue;
        };
        let Ok(pid) = name.parse::<u32>() else {
            continue;
        };
        let comm = match fs::read_to_string(entry.path().join("comm")) {
            Ok(value) => value,
            Err(error) if error.kind() == io::ErrorKind::NotFound => continue,
            Err(error) => return Err(error),
        };
        if !matches!(
            comm.trim_end_matches(['\r', '\n']),
            "cargo" | "rustc" | "rustdoc"
        ) {
            continue;
        }
        let stat = match fs::read_to_string(entry.path().join("stat")) {
            Ok(value) => value,
            Err(error) if error.kind() == io::ErrorKind::NotFound => continue,
            Err(error) => return Err(error),
        };
        if let Some(process) = parse_competing_process(pid, &comm, &stat)? {
            processes.insert(process);
        }
    }
    Ok(processes.into_iter().collect())
}

fn scan_thread_affinities() -> io::Result<Vec<ThreadAffinityEvidence>> {
    let mut threads = BTreeSet::new();
    for entry in fs::read_dir("/proc/self/task")? {
        let entry = entry?;
        let name = entry
            .file_name()
            .to_str()
            .ok_or_else(|| invalid_data("non-UTF-8 thread id in /proc/self/task"))?
            .to_string();
        let tid = name
            .parse::<u32>()
            .map_err(|error| invalid_data(format!("invalid thread id {name:?}: {error}")))?;
        let status = fs::read_to_string(entry.path().join("status"))?;
        let allowed_cpus = status_value(&status, "Cpus_allowed_list:")?;
        parse_cpu_list(&allowed_cpus)?;
        if !threads.insert(ThreadAffinityEvidence { tid, allowed_cpus }) {
            return Err(invalid_data(format!(
                "duplicate thread id {tid} in /proc/self/task"
            )));
        }
    }
    if threads.is_empty() {
        return Err(invalid_data("/proc/self/task contains no threads"));
    }
    Ok(threads.into_iter().collect())
}

fn parse_status_u32(contents: &str, key: &str) -> io::Result<u32> {
    status_value(contents, key)?
        .parse::<u32>()
        .map_err(|error| {
            invalid_data(format!(
                "invalid numeric {key} value in /proc/self/status: {error}"
            ))
        })
}

fn status_value(contents: &str, key: &str) -> io::Result<String> {
    let mut result = None;
    for line in contents.lines() {
        let Some(value) = line.strip_prefix(key) else {
            continue;
        };
        if result.is_some() {
            return Err(invalid_data(format!(
                "duplicate {key} line in /proc/self/status"
            )));
        }
        let value = value.trim();
        if value.is_empty() {
            return Err(invalid_data(format!("empty {key} value")));
        }
        result = Some(value.to_string());
    }
    result.ok_or_else(|| invalid_data(format!("missing {key} in /proc/self/status")))
}

fn unified_cgroup_path(contents: &str) -> io::Result<String> {
    let mut result = None;
    for line in contents.lines() {
        let Some(path) = line.strip_prefix("0::") else {
            continue;
        };
        if result.is_some() || !path.starts_with('/') || path.contains('\0') {
            return Err(invalid_data("invalid or duplicate unified cgroup path"));
        }
        if Path::new(path)
            .components()
            .any(|component| !matches!(component, Component::RootDir | Component::Normal(_)))
        {
            return Err(invalid_data(
                "unified cgroup path contains a non-normal component",
            ));
        }
        result = Some(path.to_string());
    }
    result.ok_or_else(|| invalid_data("missing unified cgroup v2 path"))
}

fn cgroup_directory(cgroup_path: &str) -> PathBuf {
    Path::new("/sys/fs/cgroup").join(cgroup_path.trim_start_matches('/'))
}

fn read_effective_cpuset(cgroup_path: &str) -> io::Result<(String, PathBuf)> {
    let cgroup_root = Path::new("/sys/fs/cgroup");
    let mut current = cgroup_root.join(cgroup_path.trim_start_matches('/'));
    loop {
        let candidate = current.join("cpuset.cpus.effective");
        match fs::read_to_string(&candidate) {
            Ok(value) => {
                let value = value.trim().to_string();
                parse_cpu_list(&value)?;
                return Ok((value, candidate));
            }
            Err(error) if error.kind() == io::ErrorKind::NotFound && current != cgroup_root => {
                if !current.pop() || !current.starts_with(cgroup_root) {
                    return Err(invalid_data(
                        "effective cpuset ancestor escaped the cgroup2 mount",
                    ));
                }
            }
            Err(error) => return Err(error),
        }
    }
}

fn validate_pressure_monotonic(start: PressureTotals, end: PressureTotals) -> io::Result<()> {
    checked_delta(end.cpu_some_us, start.cpu_some_us, "cpu some pressure")?;
    checked_delta(
        end.memory_some_us,
        start.memory_some_us,
        "memory some pressure",
    )?;
    checked_delta(
        end.memory_full_us,
        start.memory_full_us,
        "memory full pressure",
    )?;
    checked_delta(end.io_some_us, start.io_some_us, "io some pressure")?;
    checked_delta(end.io_full_us, start.io_full_us, "io full pressure")?;
    Ok(())
}

fn pressure_rate_bps(start: u64, end: u64, duration_us: u64, name: &str) -> io::Result<u64> {
    ratio_bps(checked_delta(end, start, name)?, duration_us)
}

fn ratio_bps(numerator: u64, denominator: u64) -> io::Result<u64> {
    if denominator == 0 {
        return Err(invalid_data("basis-point ratio denominator is zero"));
    }
    let scaled = u128::from(numerator)
        .checked_mul(u128::from(BPS_SCALE))
        .ok_or_else(|| invalid_data("basis-point ratio overflow"))?;
    u64::try_from(scaled / u128::from(denominator))
        .map_err(|_| invalid_data("basis-point ratio does not fit in u64"))
}

pub(crate) fn ratio_bps_ceil(numerator: u64, denominator: u64) -> io::Result<u64> {
    if denominator == 0 {
        return Err(invalid_data("basis-point ratio denominator is zero"));
    }
    let scaled = u128::from(numerator)
        .checked_mul(u128::from(BPS_SCALE))
        .ok_or_else(|| invalid_data("basis-point ratio overflow"))?;
    let rounded = scaled
        .checked_add(u128::from(denominator - 1))
        .ok_or_else(|| invalid_data("basis-point ceiling overflow"))?
        / u128::from(denominator);
    u64::try_from(rounded).map_err(|_| invalid_data("basis-point ratio does not fit in u64"))
}

fn checked_delta(end: u64, start: u64, name: &str) -> io::Result<u64> {
    end.checked_sub(start)
        .ok_or_else(|| invalid_data(format!("{name} counter moved backwards")))
}

fn unix_time_ns() -> io::Result<u64> {
    let duration = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map_err(|error| invalid_data(format!("system clock precedes Unix epoch: {error}")))?;
    u64::try_from(duration.as_nanos())
        .map_err(|_| invalid_data("Unix timestamp does not fit in u64 nanoseconds"))
}

pub fn monotonic_time_ns() -> io::Result<u64> {
    let mut value = MaybeUninit::<libc::timespec>::uninit();
    // SAFETY: clock_gettime initializes `value` on success and the pointer is
    // valid for one libc::timespec.
    if unsafe { libc::clock_gettime(libc::CLOCK_MONOTONIC, value.as_mut_ptr()) } != 0 {
        return Err(io::Error::last_os_error());
    }
    // SAFETY: the successful clock_gettime call initialized the value.
    timespec_to_ns(unsafe { value.assume_init() }, "monotonic clock")
}

fn monotonic_clock_resolution_ns() -> io::Result<u64> {
    let mut value = MaybeUninit::<libc::timespec>::uninit();
    // SAFETY: clock_getres initializes `value` on success and the pointer is
    // valid for one libc::timespec.
    if unsafe { libc::clock_getres(libc::CLOCK_MONOTONIC, value.as_mut_ptr()) } != 0 {
        return Err(io::Error::last_os_error());
    }
    // SAFETY: the successful clock_getres call initialized the value.
    let resolution = timespec_to_ns(unsafe { value.assume_init() }, "monotonic resolution")?;
    if resolution == 0 {
        return Err(invalid_data("monotonic clock resolution is zero"));
    }
    Ok(resolution)
}

fn absolute_monotonic_sleep(deadline_ns: u64) -> io::Result<()> {
    let deadline = ns_to_timespec(deadline_ns)?;
    // SAFETY: `deadline` is a valid immutable timespec and TIMER_ABSTIME does
    // not use a remainder pointer. Any interruption is rejected fail-closed.
    let result = unsafe {
        libc::clock_nanosleep(
            libc::CLOCK_MONOTONIC,
            libc::TIMER_ABSTIME,
            &deadline,
            ptr::null_mut(),
        )
    };
    if result != 0 {
        return Err(io::Error::from_raw_os_error(result));
    }
    Ok(())
}

fn current_thread_context_switches() -> io::Result<(u64, u64)> {
    let mut usage = MaybeUninit::<libc::rusage>::zeroed();
    // SAFETY: getrusage initializes the supplied rusage on success.
    if unsafe { libc::getrusage(libc::RUSAGE_THREAD, usage.as_mut_ptr()) } != 0 {
        return Err(io::Error::last_os_error());
    }
    // SAFETY: guarded by the successful getrusage call above.
    let usage = unsafe { usage.assume_init() };
    let voluntary = u64::try_from(usage.ru_nvcsw)
        .map_err(|_| invalid_data("negative RUSAGE_THREAD voluntary context switches"))?;
    let involuntary = u64::try_from(usage.ru_nivcsw)
        .map_err(|_| invalid_data("negative RUSAGE_THREAD involuntary context switches"))?;
    Ok((voluntary, involuntary))
}

fn current_thread_id() -> io::Result<u32> {
    // SAFETY: gettid has no pointer arguments.
    let value = unsafe { libc::syscall(libc::SYS_gettid) };
    if value <= 0 {
        return Err(io::Error::last_os_error());
    }
    u32::try_from(value).map_err(|_| invalid_data("current thread id does not fit in u32"))
}

fn current_cpu() -> io::Result<u32> {
    // SAFETY: sched_getcpu has no arguments and returns the current CPU or -1.
    let value = unsafe { libc::sched_getcpu() };
    if value < 0 {
        return Err(io::Error::last_os_error());
    }
    u32::try_from(value).map_err(|_| invalid_data("current CPU does not fit in u32"))
}

fn ns_to_timespec(value: u64) -> io::Result<libc::timespec> {
    Ok(libc::timespec {
        tv_sec: libc::time_t::try_from(value / NANOSECONDS_PER_SECOND)
            .map_err(|_| invalid_data("timespec seconds do not fit in time_t"))?,
        tv_nsec: libc::c_long::try_from(value % NANOSECONDS_PER_SECOND)
            .map_err(|_| invalid_data("timespec nanoseconds do not fit in c_long"))?,
    })
}

fn timespec_to_ns(value: libc::timespec, name: &str) -> io::Result<u64> {
    if value.tv_sec < 0 || value.tv_nsec < 0 || value.tv_nsec >= 1_000_000_000 {
        return Err(invalid_data(format!("invalid {name} timespec")));
    }
    let seconds = u64::try_from(value.tv_sec)
        .map_err(|_| invalid_data(format!("{name} seconds do not fit in u64")))?;
    let nanoseconds = u64::try_from(value.tv_nsec)
        .map_err(|_| invalid_data(format!("{name} nanoseconds do not fit in u64")))?;
    seconds
        .checked_mul(NANOSECONDS_PER_SECOND)
        .and_then(|result| result.checked_add(nanoseconds))
        .ok_or_else(|| invalid_data(format!("{name} does not fit in u64 nanoseconds")))
}

fn clock_ticks_per_second() -> io::Result<u64> {
    // SAFETY: sysconf has no pointer arguments and `_SC_CLK_TCK` is a valid
    // selector on the Linux target required by this evaluator.
    let value = unsafe { libc::sysconf(libc::_SC_CLK_TCK) };
    if value <= 0 {
        return Err(invalid_data("sysconf(_SC_CLK_TCK) returned no value"));
    }
    u64::try_from(value).map_err(|_| invalid_data("USER_HZ does not fit in u64"))
}

fn sleep_until(deadline: Instant) {
    if let Some(remaining) = deadline.checked_duration_since(Instant::now()) {
        thread::sleep(remaining);
    }
}

fn invalid_data(message: impl Into<String>) -> io::Error {
    io::Error::new(io::ErrorKind::InvalidData, message.into())
}

fn invalid_input(message: impl Into<String>) -> io::Error {
    io::Error::new(io::ErrorKind::InvalidInput, message.into())
}

#[cfg(test)]
mod tests {
    use super::*;

    fn sample(total: u64, idle: u64, cgroup_usage_usec: u64) -> CpuProcessSample {
        let monotonic = total.saturating_mul(1_000_000);
        let process_id = std::process::id();
        CpuProcessSample {
            sampled_unix_ns: total.saturating_mul(1_000_000),
            sample_started_monotonic_ns: monotonic,
            sample_finished_monotonic_ns: monotonic + 1_000_005,
            blocking_sleep_started_monotonic_ns: monotonic + 1,
            blocking_sleep_deadline_monotonic_ns: monotonic + 1_000_001,
            blocking_sleep_returned_monotonic_ns: monotonic + 1_000_001,
            schedstat_read_finished_monotonic_ns: monotonic + 1_000_003,
            host_sample_before_monotonic_ns: monotonic + 1_000_002,
            host_sample_after_monotonic_ns: monotonic + 1_000_004,
            monotonic_clock_resolution_ns: 1,
            cpu: 39,
            sampled_cpu: 39,
            excluded_smt_sibling: 79,
            cpu_total_ticks: total,
            cpu_idle_ticks: idle,
            cpu_irq_ticks: 0,
            cpu_softirq_ticks: 0,
            cpu_steal_ticks: 0,
            excluded_smt_total_ticks: total,
            excluded_smt_idle_ticks: idle,
            cpu_schedstat: SchedstatCpuSample {
                version: 17,
                timestamp: total,
                runtime_ns: monotonic,
                wait_ns: total,
                timeslices: total,
            },
            cgroup_path: "/test.service".to_string(),
            cgroup_inode: 1,
            cgroup_type: "domain".to_string(),
            cgroup_cpu_usage_usec_before_host_sample: cgroup_usage_usec,
            cgroup_cpu_usage_usec_after_host_sample: cgroup_usage_usec,
            cgroup_nr_periods_before_host_sample: total,
            cgroup_nr_periods_after_host_sample: total,
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
            accounting_flush_observed_ns: 1_000_000,
            accounting_flush_voluntary_switches_before: total,
            accounting_flush_voluntary_switches_after: total + 1,
            clock_ticks_per_second: 100,
            no_new_privileges: true,
            seccomp_mode: 2,
            seccomp_filter_count: 1,
            thread_affinities: vec![ThreadAffinityEvidence {
                tid: process_id,
                allowed_cpus: "39".to_string(),
            }],
            pressure: PressureTotals {
                cpu_some_us: 0,
                memory_some_us: 0,
                memory_full_us: 0,
                io_some_us: 0,
                io_full_us: 0,
            },
            actual_affinity: "39".to_string(),
            effective_cpuset: "0-79".to_string(),
            competing_build_processes: Vec::new(),
        }
    }

    #[test]
    fn parses_target_cpu_without_double_counting_guest_ticks() {
        let input = concat!(
            "cpu  1 2 3 4 5 6 7 8 9 10\n",
            "cpu38 10 1 2 80 3 4 5 6 7 8\n",
            "cpu39 100 2 30 800 40 5 6 7 50 3\n",
            "intr 0\n",
        );

        assert_eq!(parse_cpu_stat(input, 39).ok(), Some((990, 840)));
        assert!(parse_cpu_stat(input, 40).is_err());
    }

    #[test]
    fn parses_process_stat_with_spaces_and_parentheses_in_comm() {
        let stat = "42 (cargo worker) x) S 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15 16 17 18 4242 20";

        assert_eq!(parse_process_stat(stat).ok(), Some((42, 23, 4242)));
        assert!(parse_process_stat("42 malformed").is_err());
    }

    #[test]
    fn parses_pressure_totals_and_rejects_missing_full_line() {
        let cpu = "some avg10=0.00 avg60=0.01 avg300=0.02 total=12345\n";
        let memory = concat!(
            "some avg10=0.00 avg60=0.00 avg300=0.00 total=30\n",
            "full avg10=0.00 avg60=0.00 avg300=0.00 total=23\n",
        );
        let io = concat!(
            "some avg10=0.00 avg60=0.00 avg300=0.00 total=50\n",
            "full avg10=0.00 avg60=0.00 avg300=0.00 total=34\n",
        );

        assert_eq!(
            parse_pressure_totals(cpu, memory, io).ok(),
            Some(PressureTotals {
                cpu_some_us: 12_345,
                memory_some_us: 30,
                memory_full_us: 23,
                io_some_us: 50,
                io_full_us: 34,
            })
        );
        assert!(parse_pressure_totals(cpu, "some total=30\n", io).is_err());
        assert!(parse_pressure_totals(
            cpu,
            "full avg10=0.00 avg60=0.00 avg300=0.00 total=23\n",
            io,
        )
        .is_err());
        assert!(parse_pressure_totals(
            cpu,
            memory,
            "full avg10=0.00 avg60=0.00 avg300=0.00 total=34\n",
        )
        .is_err());
    }

    #[test]
    fn cpu_list_parser_is_strict_and_normalizes_membership() {
        assert_eq!(
            parse_cpu_list("0-2,4,39-40").ok(),
            Some([0, 1, 2, 4, 39, 40].into_iter().collect())
        );
        assert!(parse_cpu_list("0-2,,39").is_err());
        assert!(parse_cpu_list("4-2").is_err());
    }

    #[test]
    fn competing_process_identity_includes_start_ticks() {
        let stat = "811 (cargo) S 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15 16 17 18 998877 20";
        assert_eq!(
            parse_competing_process(811, "cargo\n", stat).ok().flatten(),
            Some(CompetingProcessEvidence {
                pid: 811,
                comm: "cargo".to_string(),
                start_ticks: 998_877,
            })
        );
        assert_eq!(
            parse_competing_process(812, "bash\n", stat).ok().flatten(),
            None
        );
    }

    #[test]
    fn quiet_thresholds_are_conjunctive_and_use_worst_bucket() {
        let pressure = PressureTotals {
            cpu_some_us: 0,
            memory_some_us: 0,
            memory_full_us: 0,
            io_some_us: 0,
            io_full_us: 0,
        };
        let start = sample(1_000, 900, 10);
        let middle = sample(1_100, 995, 12);
        let end = sample(1_200, 1_085, 14);

        let evidence = quiet_window_from_samples(
            10,
            200_000_010,
            Duration::from_millis(200),
            vec![start.clone(), middle, end],
        );
        assert_eq!(
            evidence.as_ref().ok().map(|item| item.overall_idle_bps),
            Some(9_250)
        );
        assert_eq!(
            evidence
                .as_ref()
                .ok()
                .map(|item| item.worst_bucket_idle_bps),
            Some(9_000)
        );
        assert_eq!(evidence.ok().map(|item| item.passed), Some(false));

        let passing = quiet_window_from_samples(
            10,
            200_000_010,
            Duration::from_millis(200),
            vec![
                CpuProcessSample {
                    pressure,
                    ..sample(1_000, 900, 10)
                },
                sample(1_100, 995, 12),
                sample(1_200, 1_090, 14),
            ],
        );
        assert_eq!(passing.ok().map(|item| item.passed), Some(true));
    }

    #[test]
    fn quiet_thresholds_include_memory_and_io_some_pressure() {
        let start = sample(1_000, 900, 10);
        let middle = sample(1_100, 995, 12);
        let mut end = sample(1_200, 1_090, 14);
        end.pressure.memory_some_us = 2_020;
        end.pressure.io_some_us = 2_020;

        let evidence = quiet_window_from_samples(
            10,
            200_000_010,
            Duration::from_millis(200),
            vec![start, middle, end],
        );

        assert_eq!(
            evidence
                .as_ref()
                .ok()
                .map(|item| item.memory_some_pressure_delta_bps),
            Some(101)
        );
        assert_eq!(
            evidence
                .as_ref()
                .ok()
                .map(|item| item.io_some_pressure_delta_bps),
            Some(101)
        );
        assert_eq!(evidence.ok().map(|item| item.passed), Some(false));
    }

    #[test]
    fn child_interference_aligns_schedstat_with_cgroup_cpu_and_charges_irq_fields() {
        let bounds = conservative_scheduled_interference_bounds(
            5_006_135_957,
            4_998_058,
            0,
            0,
            5_000_000_000,
            1,
            100,
        )
        .unwrap();

        assert_eq!(bounds.cgroup_cpu_usage_floor_lower_bound_ns, 4_998_057_001);
        assert_eq!(bounds.own_cpu_lower_bound_ns, 4_998_057_001);
        assert_eq!(bounds.external_scheduled_runtime_upper_ns, 8_078_956);
        assert_eq!(bounds.proc_stat_side_charge_upper_bound_ns, 30_000_000);
        assert_eq!(bounds.combined_external_upper_bound_ns, 38_078_956);
        assert_eq!(bounds.operation_elapsed_lower_bound_ns, 4_999_999_998);
        assert_eq!(bounds.busy_upper_bound_bps, 77);

        let pending = conservative_scheduled_interference_bounds(
            5_006_135_957,
            4_998_058,
            1_000_000,
            0,
            5_000_000_000,
            1,
            100,
        )
        .unwrap();
        assert_eq!(pending.own_cpu_lower_bound_ns, 4_997_057_001);
        assert_eq!(pending.external_scheduled_runtime_upper_ns, 9_078_956);

        let one_usec =
            conservative_scheduled_interference_bounds(1, 1, 0, 0, 1_000_000_000, 1, 100).unwrap();
        assert_eq!(one_usec.cgroup_cpu_usage_floor_lower_bound_ns, 1);

        assert!(conservative_scheduled_interference_bounds(
            4_998_056_999,
            4_998_058,
            0,
            0,
            5_000_000_000,
            1,
            100,
        )
        .is_err());
        assert!(conservative_scheduled_interference_bounds(1, 0, 0, 0, 0, 1, 100).is_err());
        assert!(conservative_scheduled_interference_bounds(1, 0, 0, 0, 1, 1, 128).is_err());

        assert_eq!(
            conservative_proc_stat_nonidle_upper_bound_ns(500, 499, 100).ok(),
            Some(70_000_000)
        );
        assert_eq!(ratio_bps_ceil(50_000_001, 1_000_000_000).ok(), Some(501));
    }

    #[test]
    fn parses_frozen_schedstat_and_cgroup_cpu_usage_contracts() {
        let schedstat = concat!(
            "version 17\n",
            "timestamp 123\n",
            "cpu39 0 0 0 0 0 0 5006135957 8078957 42\n",
            "domain0 SMT mask 0 0 0\n",
            "cpu79 0 0 0 0 0 0 7000000000 9000000 43\n",
        );
        assert_eq!(
            parse_schedstat_cpu(schedstat, 39).ok(),
            Some(SchedstatCpuSample {
                version: 17,
                timestamp: 123,
                runtime_ns: 5_006_135_957,
                wait_ns: 8_078_957,
                timeslices: 42,
            })
        );
        assert!(parse_schedstat_cpu(&schedstat.replace("version 17", "version 16"), 39).is_err());
        assert!(parse_schedstat_cpu(
            &schedstat.replace("cpu39 0 0 0 0 0 0", "cpu39 1 0 0 0 0 0"),
            39,
        )
        .is_err());

        assert_eq!(
            parse_cgroup_cpu_usage_usec("usage_usec 12345\nuser_usec 10000\nsystem_usec 2345\n")
                .ok(),
            Some(12_345)
        );
        assert!(parse_cgroup_cpu_usage_usec("user_usec 10000\n").is_err());
        assert!(parse_cgroup_cpu_usage_usec("usage_usec 1\nusage_usec 2\n").is_err());
        assert_eq!(
            parse_cgroup_cpu_stat(
                "usage_usec 12345\nnr_periods 7\nnr_throttled 0\nthrottled_usec 0\n"
            )
            .ok(),
            Some(CgroupCpuStatSample {
                usage_usec: 12_345,
                nr_periods: 7,
                nr_throttled: 0,
                throttled_usec: 0,
            })
        );
        assert!(parse_cgroup_cpu_stat("usage_usec 12345\nnr_periods 7\nnr_throttled 0\n").is_err());
    }
}
