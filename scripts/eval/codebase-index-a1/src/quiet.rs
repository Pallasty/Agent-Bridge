//! Fail-closed Linux host-interference evidence for the A1 benchmark.

use std::collections::BTreeSet;
use std::fs;
use std::io;
use std::path::{Component, Path, PathBuf};
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

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq, PartialOrd, Ord)]
pub struct CompetingProcessEvidence {
    pub pid: u32,
    pub comm: String,
    pub start_ticks: u64,
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
    pub cpu: u32,
    pub excluded_smt_sibling: u32,
    pub cpu_total_ticks: u64,
    pub cpu_idle_ticks: u64,
    pub excluded_smt_total_ticks: u64,
    pub excluded_smt_idle_ticks: u64,
    pub process_ticks_before_cpu_sample: u64,
    pub process_ticks_after_cpu_sample: u64,
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
    pub external_cpu39_busy_bps: u64,
    pub excluded_smt_sibling_busy_bps: u64,
}

/// Observe one fail-closed sample of CPU, process, pressure, affinity, cpuset,
/// and competing Rust build activity from Linux procfs/cgroupfs.
pub fn cpu_process_sample(cpu: u32) -> io::Result<CpuProcessSample> {
    let (process_ticks_before_cpu_sample, _) =
        parse_process_stat_ticks(&fs::read_to_string("/proc/self/stat")?)?;
    let cpu_stat = fs::read_to_string("/proc/stat")?;
    let (process_ticks_after_cpu_sample, _) =
        parse_process_stat_ticks(&fs::read_to_string("/proc/self/stat")?)?;
    if process_ticks_after_cpu_sample < process_ticks_before_cpu_sample {
        return Err(invalid_data(
            "process tick counter moved backwards across the CPU sample",
        ));
    }
    let (cpu_total_ticks, cpu_idle_ticks) = parse_cpu_stat(&cpu_stat, cpu)?;
    let excluded_smt_sibling = read_excluded_smt_sibling(cpu)?;
    let (excluded_smt_total_ticks, excluded_smt_idle_ticks) =
        parse_cpu_stat(&cpu_stat, excluded_smt_sibling)?;
    let pressure = parse_pressure_totals(
        &fs::read_to_string("/proc/pressure/cpu")?,
        &fs::read_to_string("/proc/pressure/memory")?,
        &fs::read_to_string("/proc/pressure/io")?,
    )?;
    let actual_affinity = status_value(
        &fs::read_to_string("/proc/self/status")?,
        "Cpus_allowed_list:",
    )?;
    let actual_cpus = parse_cpu_list(&actual_affinity)?;
    if !actual_cpus.contains(&cpu) {
        return Err(invalid_data(format!(
            "requested cpu{cpu} is absent from Cpus_allowed_list={actual_affinity}"
        )));
    }

    let cgroup_path = unified_cgroup_path(&fs::read_to_string("/proc/self/cgroup")?)?;
    let (effective_cpuset, cpuset_path) = read_effective_cpuset(&cgroup_path)?;
    let effective_cpus = parse_cpu_list(&effective_cpuset)?;
    if !effective_cpus.contains(&cpu) {
        return Err(invalid_data(format!(
            "requested cpu{cpu} is absent from {}={effective_cpuset}",
            cpuset_path.display()
        )));
    }

    Ok(CpuProcessSample {
        sampled_unix_ns: unix_time_ns()?,
        cpu,
        excluded_smt_sibling,
        cpu_total_ticks,
        cpu_idle_ticks,
        excluded_smt_total_ticks,
        excluded_smt_idle_ticks,
        process_ticks_before_cpu_sample,
        process_ticks_after_cpu_sample,
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
) -> io::Result<ChildInterferenceEvidence> {
    checked_delta(
        end.sampled_unix_ns,
        start.sampled_unix_ns,
        "child sample unix time",
    )?;
    validate_pressure_monotonic(start.pressure, end.pressure)?;
    let start_affinity = parse_cpu_list(&start.actual_affinity)?;
    let end_affinity = parse_cpu_list(&end.actual_affinity)?;
    let expected_affinity = BTreeSet::from([39]);
    if start_affinity != expected_affinity || end_affinity != expected_affinity {
        return Err(invalid_data(
            "child-interference samples must both be pinned exclusively to cpu39",
        ));
    }
    if start.actual_affinity != end.actual_affinity
        || start.effective_cpuset != end.effective_cpuset
        || start.cpu != 39
        || end.cpu != 39
        || start.excluded_smt_sibling != 79
        || end.excluded_smt_sibling != 79
    {
        return Err(invalid_data(
            "affinity or effective cpuset changed during child measurement",
        ));
    }
    let effective_cpus = parse_cpu_list(&start.effective_cpuset)?;
    if !effective_cpus.contains(&39) {
        return Err(invalid_data(
            "cpu39 is absent from the child effective cpuset",
        ));
    }

    let total_delta = checked_delta(
        end.cpu_total_ticks,
        start.cpu_total_ticks,
        "cpu total ticks",
    )?;
    let idle_delta = checked_delta(end.cpu_idle_ticks, start.cpu_idle_ticks, "cpu idle ticks")?;
    if idle_delta > total_delta {
        return Err(invalid_data("cpu idle delta exceeds cpu total delta"));
    }
    let nonidle_delta = total_delta - idle_delta;
    let process_delta = conservative_inner_process_delta(
        start.process_ticks_before_cpu_sample,
        start.process_ticks_after_cpu_sample,
        end.process_ticks_before_cpu_sample,
        end.process_ticks_after_cpu_sample,
    )?;
    let external_delta = nonidle_delta
        .checked_sub(process_delta)
        .ok_or_else(|| invalid_data("process tick delta exceeds cpu39 non-idle tick delta"))?;
    let external_cpu39_busy_bps = ratio_bps(external_delta, total_delta)?;
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
    let sibling_busy_delta = sibling_total_delta
        .checked_sub(sibling_idle_delta)
        .ok_or_else(|| invalid_data("excluded SMT sibling idle exceeds total ticks"))?;
    let excluded_smt_sibling_busy_bps = ratio_bps(sibling_busy_delta, sibling_total_delta)?;

    Ok(ChildInterferenceEvidence {
        start: start.clone(),
        end: end.clone(),
        external_cpu39_busy_bps,
        excluded_smt_sibling_busy_bps,
    })
}

/// Return only process ticks whose observation interval is provably contained
/// by the two CPU-counter observations. This intentionally undercounts the
/// measured process at both boundaries, so any sampling-boundary ambiguity is
/// charged to external CPU activity rather than hidden from the interference
/// gate.
pub(crate) fn conservative_inner_process_delta(
    start_process_before_cpu: u64,
    start_process_after_cpu: u64,
    end_process_before_cpu: u64,
    end_process_after_cpu: u64,
) -> io::Result<u64> {
    checked_delta(
        start_process_after_cpu,
        start_process_before_cpu,
        "start process ticks across CPU sample",
    )?;
    checked_delta(
        end_process_after_cpu,
        end_process_before_cpu,
        "end process ticks across CPU sample",
    )?;
    checked_delta(
        end_process_before_cpu,
        start_process_after_cpu,
        "inner process ticks",
    )
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

fn parse_cpu_stat(contents: &str, cpu: u32) -> io::Result<(u64, u64)> {
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
        match_value = Some((total, idle));
    }
    match_value.ok_or_else(|| invalid_data(format!("missing {label} line in /proc/stat")))
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

fn parse_process_stat_ticks(contents: &str) -> io::Result<(u64, u64)> {
    let (_, ticks, start_ticks) = parse_process_stat(contents)?;
    Ok((ticks, start_ticks))
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

    fn sample(total: u64, idle: u64, process: u64) -> CpuProcessSample {
        CpuProcessSample {
            sampled_unix_ns: total.saturating_mul(1_000_000),
            cpu: 39,
            excluded_smt_sibling: 79,
            cpu_total_ticks: total,
            cpu_idle_ticks: idle,
            excluded_smt_total_ticks: total,
            excluded_smt_idle_ticks: idle,
            process_ticks_before_cpu_sample: process,
            process_ticks_after_cpu_sample: process,
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

        assert_eq!(parse_process_stat_ticks(stat).ok(), Some((23, 4242)));
        assert!(parse_process_stat_ticks("42 malformed").is_err());
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
    fn child_interference_subtracts_only_the_measured_process_ticks() {
        let start = sample(1_000, 900, 50);
        let end = sample(1_200, 1_080, 60);
        let evidence = child_interference(&start, &end);

        assert_eq!(
            evidence.ok().map(|item| item.external_cpu39_busy_bps),
            Some(500)
        );
        assert_eq!(
            child_interference(&start, &end)
                .ok()
                .map(|item| item.excluded_smt_sibling_busy_bps),
            Some(1_000)
        );
        assert!(child_interference(&start, &sample(1_200, 1_080, 80)).is_err());

        let mut bracketed_start = sample(1_000, 900, 50);
        bracketed_start.process_ticks_after_cpu_sample = 51;
        let mut bracketed_end = sample(1_200, 1_080, 71);
        bracketed_end.process_ticks_after_cpu_sample = 72;
        assert_eq!(
            child_interference(&bracketed_start, &bracketed_end)
                .ok()
                .map(|item| item.external_cpu39_busy_bps),
            Some(0),
            "the outer process delta may exceed CPU non-idle ticks while the conservative inner interval remains valid"
        );
    }

    #[test]
    fn child_interference_uses_a_process_interval_bracketed_by_cpu_samples() {
        assert_eq!(
            conservative_inner_process_delta(50, 51, 71, 72).ok(),
            Some(20)
        );
        assert!(conservative_inner_process_delta(50, 71, 70, 72).is_err());
        assert!(conservative_inner_process_delta(51, 50, 71, 72).is_err());
        assert!(conservative_inner_process_delta(50, 51, 72, 71).is_err());
    }
}
