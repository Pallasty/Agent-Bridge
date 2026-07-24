//! Linux read-only body sensor adapter.
//!
//! The core sample uses stable procfs and libc surfaces only. PSI is exposed as
//! an additional status projection, while GPU values remain explicitly
//! unsupported until a separately validated ROCm adapter exists.

use super::{
    BodySample, BodySensorAdapter, BodyTelemetryCore, MemoryArchitecture, MemorySample,
    MetricStatus, MetricValue, PressurePolicy, ProcessFootprint, StorageSample,
    BODY_STATUS_SCHEMA_V0,
};
use serde::Serialize;
use serde_json::{json, Value};
use std::fs;
use std::mem::MaybeUninit;
use std::sync::{Mutex, OnceLock};
use std::time::{Instant, SystemTime, UNIX_EPOCH};

const ADAPTER_ID: &str = "linux_procfs_v0";

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
struct CpuTicks {
    active: u64,
    total: u64,
}

fn cpu_ratio(previous: CpuTicks, current: CpuTicks) -> Option<f64> {
    let total = current.total.checked_sub(previous.total)?;
    let active = current.active.checked_sub(previous.active)?;
    (total > 0 && active <= total).then_some(active as f64 / total as f64)
}

fn monotonic_ms() -> u64 {
    static START: OnceLock<Instant> = OnceLock::new();
    START
        .get_or_init(Instant::now)
        .elapsed()
        .as_millis()
        .try_into()
        .unwrap_or(u64::MAX)
}

fn unix_ms() -> i64 {
    SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map(|duration| duration.as_millis().try_into().unwrap_or(i64::MAX))
        .unwrap_or(0)
}

fn unknown_bytes(source: &str) -> MetricValue<u64> {
    MetricValue::unavailable(MetricStatus::Unknown, source)
}

fn parse_cpu_ticks(content: &str) -> Option<CpuTicks> {
    let line = content.lines().find(|line| line.starts_with("cpu "))?;
    let fields = line.split_whitespace().skip(1).collect::<Vec<_>>();
    if fields.len() < 4 {
        return None;
    }
    let values = fields
        .iter()
        .map(|field| field.parse::<u64>().ok())
        .collect::<Option<Vec<_>>>()?;
    // guest and guest_nice, when present, are already included in user/nice.
    // Sum only the documented eight non-overlapping aggregate tick fields.
    let total = values
        .iter()
        .take(8)
        .copied()
        .fold(0u64, u64::saturating_add);
    let idle = values[3];
    let iowait = values.get(4).copied().unwrap_or(0);
    Some(CpuTicks {
        active: total.saturating_sub(idle.saturating_add(iowait)),
        total,
    })
}

fn read_cpu_ticks() -> Option<CpuTicks> {
    fs::read_to_string("/proc/stat")
        .ok()
        .and_then(|content| parse_cpu_ticks(&content))
}

fn meminfo_bytes(content: &str, key: &str) -> Option<u64> {
    let line = content
        .lines()
        .find(|line| line.split_once(':').map(|(name, _)| name) == Some(key))?;
    let (_, value) = line.split_once(':')?;
    let mut fields = value.split_whitespace();
    let kib = fields.next()?.parse::<u64>().ok()?;
    match fields.next() {
        None | Some("kB") => kib.checked_mul(1024),
        _ => None,
    }
}

fn read_memory_bytes() -> Option<(u64, u64)> {
    let content = fs::read_to_string("/proc/meminfo").ok()?;
    let total = meminfo_bytes(&content, "MemTotal")?;
    let available = meminfo_bytes(&content, "MemAvailable")?;
    (available <= total).then_some((total, available))
}

fn read_storage_bytes() -> Option<(u64, u64)> {
    let path = b"/\0";
    let mut stats = MaybeUninit::<libc::statvfs>::zeroed();
    // SAFETY: the literal path is NUL-terminated and stats is valid writable storage.
    if unsafe { libc::statvfs(path.as_ptr().cast(), stats.as_mut_ptr()) } != 0 {
        return None;
    }
    // SAFETY: successful statvfs initialized stats.
    let stats = unsafe { stats.assume_init() };
    let block_size = if stats.f_frsize > 0 {
        stats.f_frsize as u64
    } else {
        stats.f_bsize as u64
    };
    (block_size > 0)
        .then(|| {
            let total = stats.f_blocks.checked_mul(block_size)?;
            let available = stats.f_bavail.checked_mul(block_size)?;
            (available <= total).then_some((total, available))
        })
        .flatten()
}

fn read_process_resident_bytes() -> Option<u64> {
    let content = fs::read_to_string("/proc/self/statm").ok()?;
    let resident_pages = content.split_whitespace().nth(1)?.parse::<u64>().ok()?;
    // SAFETY: sysconf with _SC_PAGESIZE has no memory-safety preconditions.
    let page_size = unsafe { libc::sysconf(libc::_SC_PAGESIZE) };
    (page_size > 0).then(|| resident_pages.checked_mul(page_size as u64))?
}

#[derive(Debug, Clone, PartialEq, Serialize)]
struct PsiResource {
    some_avg10_ratio: MetricValue<f64>,
    full_avg10_ratio: MetricValue<f64>,
}

fn parse_psi_ratio(content: &str, category: &str) -> Option<f64> {
    let line = content
        .lines()
        .find(|line| line.split_whitespace().next() == Some(category))?;
    let avg10 = line
        .split_whitespace()
        .find_map(|field| field.strip_prefix("avg10="))?
        .parse::<f64>()
        .ok()?;
    (avg10.is_finite() && (0.0..=100.0).contains(&avg10)).then_some(avg10 / 100.0)
}

fn read_psi(path: &str) -> PsiResource {
    let source = "linux_psi_avg10";
    let content = fs::read_to_string(path).ok();
    let metric = |category| {
        content
            .as_deref()
            .and_then(|content| parse_psi_ratio(content, category))
            .map(|ratio| MetricValue::fresh(ratio, source))
            .unwrap_or_else(|| MetricValue::unavailable(MetricStatus::Unknown, source))
    };
    PsiResource {
        some_avg10_ratio: metric("some"),
        full_avg10_ratio: metric("full"),
    }
}

#[derive(Debug)]
pub struct LinuxBodySensor {
    previous_cpu: Option<CpuTicks>,
    next_sequence: u64,
}

impl Default for LinuxBodySensor {
    fn default() -> Self {
        Self {
            previous_cpu: None,
            next_sequence: 0,
        }
    }
}

impl BodySensorAdapter for LinuxBodySensor {
    fn adapter_id(&self) -> &str {
        ADAPTER_ID
    }

    fn sample(&mut self, observed_at_mono_ms: u64, observed_at_unix_ms: i64) -> BodySample {
        let sequence = self.next_sequence;
        self.next_sequence = self.next_sequence.saturating_add(1);

        let cpu_ticks = read_cpu_ticks();
        let cpu_utilization_ratio = match (self.previous_cpu, cpu_ticks) {
            (Some(previous), Some(current)) => cpu_ratio(previous, current)
                .map(|ratio| MetricValue::fresh(ratio, "linux_proc_stat"))
                .unwrap_or_else(|| {
                    MetricValue::unavailable(MetricStatus::Unknown, "linux_cpu_counter_reset")
                }),
            (None, Some(_)) => MetricValue::unavailable(MetricStatus::Unknown, "linux_cpu_warmup"),
            (_, None) => MetricValue::unavailable(MetricStatus::Unknown, "linux_proc_stat"),
        };
        self.previous_cpu = cpu_ticks;

        let (memory_total, memory_available) = match read_memory_bytes() {
            Some((total, available)) => (
                MetricValue::fresh(total, "linux_proc_meminfo"),
                MetricValue::fresh(available, "linux_proc_meminfo"),
            ),
            None => (
                unknown_bytes("linux_proc_meminfo"),
                unknown_bytes("linux_proc_meminfo"),
            ),
        };
        let (storage_total, storage_available) = match read_storage_bytes() {
            Some((total, available)) => (
                MetricValue::fresh(total, "linux_statvfs_root"),
                MetricValue::fresh(available, "linux_statvfs_root"),
            ),
            None => (
                unknown_bytes("linux_statvfs_root"),
                unknown_bytes("linux_statvfs_root"),
            ),
        };
        let resident_bytes = read_process_resident_bytes()
            .map(|bytes| MetricValue::fresh(bytes, "linux_proc_self_statm"))
            .unwrap_or_else(|| unknown_bytes("linux_proc_self_statm"));

        BodySample {
            sequence,
            observed_at_mono_ms,
            observed_at_unix_ms,
            cpu_utilization_ratio,
            memory: MemorySample {
                // Do not infer a memory topology merely from running on Linux.
                architecture: MemoryArchitecture::Unknown,
                total_bytes: memory_total,
                available_bytes: memory_available,
                vram_total_bytes: MetricValue::unavailable(
                    MetricStatus::Unsupported,
                    "no_rocm_userspace_adapter_v0",
                ),
            },
            storage: StorageSample {
                total_bytes: storage_total,
                available_bytes: storage_available,
            },
            process: ProcessFootprint { resident_bytes },
        }
    }
}

#[derive(Debug)]
struct BodyStatusService {
    sensor: LinuxBodySensor,
    core: BodyTelemetryCore,
}

impl Default for BodyStatusService {
    fn default() -> Self {
        Self {
            sensor: LinuxBodySensor::default(),
            core: BodyTelemetryCore::new(72, PressurePolicy::default()),
        }
    }
}

static SERVICE: OnceLock<Mutex<BodyStatusService>> = OnceLock::new();

pub fn body_status_snapshot() -> Value {
    let service = SERVICE.get_or_init(|| Mutex::new(BodyStatusService::default()));
    let Ok(mut service) = service.lock() else {
        return json!({
            "schema_version": BODY_STATUS_SCHEMA_V0,
            "mode": "shadow_only",
            "enabled": true,
            "status": "unknown",
            "reason": "body telemetry service mutex poisoned",
            "read_only": true,
            "persists_raw_samples": false,
        });
    };
    let sample = service.sensor.sample(monotonic_ms(), unix_ms());
    let pressure = service.core.ingest(sample);
    let sample = service
        .core
        .history()
        .latest()
        .expect("sample just ingested");
    json!({
        "schema_version": BODY_STATUS_SCHEMA_V0,
        "mode": "shadow_only",
        "enabled": true,
        "status": "ok",
        "read_only": true,
        "persists_raw_samples": false,
        "collector": {
            "adapter_id": ADAPTER_ID,
            "sampling": "on_demand",
            "background_sampler": false,
            "raw_history_capacity": 72,
        },
        "pressure": pressure,
        "sample": sample,
        "history_len": service.core.history().len(),
        "linux_psi": {
            "cpu": read_psi("/proc/pressure/cpu"),
            "memory": read_psi("/proc/pressure/memory"),
            "io": read_psi("/proc/pressure/io"),
        },
        "gpu": {
            "status": "unsupported",
            "source": "no_rocm_userspace_adapter_v0",
            "reason": "GPU utilization and VRAM require a separately validated ROCm adapter",
        },
        "known_limitations": [
            "cpu utilization is unknown until a second sample establishes a counter delta",
            "PSI avg10 is a short-window stall ratio and does not identify a process",
            "GPU utilization, VRAM, thermal, power, disk throughput, and network throughput are unavailable in v0",
        ],
    })
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn cpu_ticks_use_only_the_aggregate_cpu_line() {
        let ticks = parse_cpu_ticks("cpu  10 2 3 80 5 1 1 1 7 9\ncpu0 1 0 0 9\n")
            .expect("aggregate cpu line");
        assert_eq!(ticks.total, 103);
        assert_eq!(ticks.active, 18);
    }

    #[test]
    fn cpu_ratio_uses_counter_deltas() {
        assert_eq!(
            cpu_ratio(
                CpuTicks {
                    active: 10,
                    total: 100
                },
                CpuTicks {
                    active: 30,
                    total: 150
                },
            ),
            Some(0.4)
        );
    }

    #[test]
    fn meminfo_requires_kib_and_bounds_available_memory() {
        let valid = "MemTotal:       1024 kB\nMemAvailable:    512 kB\n";
        assert_eq!(read_memory_bytes_from(valid), Some((1_048_576, 524_288)));
        let invalid = "MemTotal:       1024 kB\nMemAvailable:   2048 kB\n";
        assert_eq!(read_memory_bytes_from(invalid), None);
    }

    #[test]
    fn psi_parser_normalizes_percent_and_rejects_invalid_values() {
        let psi = "some avg10=12.50 avg60=1.00 avg300=0.50 total=1\nfull avg10=0.00 avg60=0.00 avg300=0.00 total=2\n";
        assert_eq!(parse_psi_ratio(psi, "some"), Some(0.125));
        assert_eq!(parse_psi_ratio(psi, "full"), Some(0.0));
        assert_eq!(parse_psi_ratio("some avg10=101.0", "some"), None);
    }

    fn read_memory_bytes_from(content: &str) -> Option<(u64, u64)> {
        let total = meminfo_bytes(content, "MemTotal")?;
        let available = meminfo_bytes(content, "MemAvailable")?;
        (available <= total).then_some((total, available))
    }
}
