//! macOS read-only body sensor adapter.
//!
//! All values come from public Darwin/BSD APIs through the existing `libc`
//! dependency. The adapter intentionally leaves GPU, thermal, and power
//! metrics unavailable until an equally reliable, documented source exists.

use super::{
    BodySample, BodySensorAdapter, BodyTelemetryCore, KernelPressureSample, MemoryArchitecture,
    MemorySample, MetricStatus, MetricValue, PressurePolicy, ProcessFootprint, StorageMountSample,
    StorageSample, BODY_STATUS_SCHEMA_V0,
};
use serde_json::{json, Value};
use std::ffi::CString;
use std::mem::{size_of, MaybeUninit};
use std::sync::{Mutex, OnceLock};
use std::time::{Instant, SystemTime, UNIX_EPOCH};

const ADAPTER_ID: &str = "darwin_read_only_v0";

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
struct CpuTicks {
    user: u64,
    system: u64,
    idle: u64,
    nice: u64,
}

impl CpuTicks {
    fn total(self) -> u64 {
        self.user
            .saturating_add(self.system)
            .saturating_add(self.idle)
            .saturating_add(self.nice)
    }

    fn active(self) -> u64 {
        self.user
            .saturating_add(self.system)
            .saturating_add(self.nice)
    }
}

fn cpu_ratio(previous: CpuTicks, current: CpuTicks) -> Option<f64> {
    let total = current.total().checked_sub(previous.total())?;
    let active = current.active().checked_sub(previous.active())?;
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

#[allow(deprecated)] // libc retains these stable Darwin bindings; no extra Mach crate in v0.
fn read_cpu_ticks() -> Option<CpuTicks> {
    let mut info = MaybeUninit::<libc::host_cpu_load_info>::zeroed();
    let mut count = libc::HOST_CPU_LOAD_INFO_COUNT;
    // SAFETY: `info` and `count` provide the exact storage and count required
    // by HOST_CPU_LOAD_INFO; mach_host_self is a read-only host port lookup.
    let result = unsafe {
        libc::host_statistics(
            libc::mach_host_self(),
            libc::HOST_CPU_LOAD_INFO,
            info.as_mut_ptr().cast::<libc::integer_t>(),
            &mut count,
        )
    };
    if result != libc::KERN_SUCCESS || count < libc::HOST_CPU_LOAD_INFO_COUNT {
        return None;
    }
    // SAFETY: a successful host_statistics call initialized `info`.
    let info = unsafe { info.assume_init() };
    Some(CpuTicks {
        user: info.cpu_ticks[libc::CPU_STATE_USER as usize] as u64,
        system: info.cpu_ticks[libc::CPU_STATE_SYSTEM as usize] as u64,
        idle: info.cpu_ticks[libc::CPU_STATE_IDLE as usize] as u64,
        nice: info.cpu_ticks[libc::CPU_STATE_NICE as usize] as u64,
    })
}

fn sysctl_u64(name: &str) -> Option<u64> {
    let name = CString::new(name).ok()?;
    let mut value = 0u64;
    let mut size = size_of::<u64>();
    // SAFETY: both the NUL-terminated name and writable u64 buffer are valid.
    let result = unsafe {
        libc::sysctlbyname(
            name.as_ptr(),
            (&mut value as *mut u64).cast(),
            &mut size,
            std::ptr::null_mut(),
            0,
        )
    };
    (result == 0 && size == size_of::<u64>()).then_some(value)
}

#[allow(deprecated)] // libc retains these stable Darwin bindings; no extra Mach crate in v0.
fn read_available_memory_bytes() -> Option<u64> {
    let mut stats = MaybeUninit::<libc::vm_statistics64>::zeroed();
    let mut count = libc::HOST_VM_INFO64_COUNT;
    // SAFETY: `stats` and `count` match the documented HOST_VM_INFO64 layout.
    let result = unsafe {
        libc::host_statistics64(
            libc::mach_host_self(),
            libc::HOST_VM_INFO64,
            stats.as_mut_ptr().cast::<libc::integer_t>(),
            &mut count,
        )
    };
    if result != libc::KERN_SUCCESS || count < libc::HOST_VM_INFO64_COUNT {
        return None;
    }
    // SAFETY: success initializes the complete `vm_statistics64` value.
    let stats = unsafe { stats.assume_init() };
    // free + inactive + speculative is a documented reclaimable-memory proxy,
    // not a claim of macOS memory pressure or of application-owned memory.
    let reclaimable_pages = (stats.free_count as u64)
        .saturating_add(stats.inactive_count as u64)
        .saturating_add(stats.speculative_count as u64);
    // SAFETY: Darwin initializes this exported page-size global before user code.
    let page_size = unsafe { libc::vm_page_size };
    (page_size > 0).then_some(reclaimable_pages.saturating_mul(page_size as u64))
}

fn read_storage_bytes() -> Option<(u64, u64)> {
    let path = CString::new("/").expect("literal has no NUL");
    let mut stats = MaybeUninit::<libc::statfs>::zeroed();
    // SAFETY: `path` is NUL-terminated and `stats` is writable storage.
    if unsafe { libc::statfs(path.as_ptr(), stats.as_mut_ptr()) } != 0 {
        return None;
    }
    // SAFETY: successful statfs initialized `stats`.
    let stats = unsafe { stats.assume_init() };
    let block_size = stats.f_bsize;
    if block_size <= 0 {
        return None;
    }
    let block_size = block_size as u64;
    let total = (stats.f_blocks as u64).checked_mul(block_size)?;
    let available = (stats.f_bavail as u64).checked_mul(block_size)?;
    (available <= total).then_some((total, available))
}

#[allow(deprecated)] // libc retains these stable Darwin bindings; no extra Mach crate in v0.
fn read_process_resident_bytes() -> Option<u64> {
    let mut info = MaybeUninit::<libc::mach_task_basic_info>::zeroed();
    let mut count = libc::MACH_TASK_BASIC_INFO_COUNT;
    // SAFETY: task_info writes the documented basic-info struct for this task.
    let result = unsafe {
        libc::task_info(
            libc::mach_task_self(),
            libc::MACH_TASK_BASIC_INFO,
            info.as_mut_ptr().cast::<libc::integer_t>(),
            &mut count,
        )
    };
    if result != libc::KERN_SUCCESS || count < libc::MACH_TASK_BASIC_INFO_COUNT {
        return None;
    }
    // SAFETY: success initialized info. The Darwin struct is packed, so read
    // the field unaligned rather than forming an aligned reference to it.
    let info = unsafe { info.assume_init() };
    let resident = unsafe { std::ptr::addr_of!(info.resident_size).read_unaligned() };
    Some(resident as u64)
}

#[derive(Debug)]
pub struct MacOsBodySensor {
    previous_cpu: Option<CpuTicks>,
    next_sequence: u64,
}

impl Default for MacOsBodySensor {
    fn default() -> Self {
        Self {
            previous_cpu: None,
            next_sequence: 0,
        }
    }
}

impl BodySensorAdapter for MacOsBodySensor {
    fn adapter_id(&self) -> &str {
        ADAPTER_ID
    }

    fn sample(&mut self, observed_at_mono_ms: u64, observed_at_unix_ms: i64) -> BodySample {
        let sequence = self.next_sequence;
        self.next_sequence = self.next_sequence.saturating_add(1);

        let cpu_ticks = read_cpu_ticks();
        let cpu_utilization_ratio = match (self.previous_cpu, cpu_ticks) {
            (Some(previous), Some(current)) => match cpu_ratio(previous, current) {
                Some(ratio) => MetricValue::fresh(ratio, "darwin_host_statistics"),
                None => MetricValue::unavailable(MetricStatus::Unknown, "darwin_cpu_counter_reset"),
            },
            (None, Some(_)) => MetricValue::unavailable(MetricStatus::Unknown, "darwin_cpu_warmup"),
            (_, None) => MetricValue::unavailable(MetricStatus::Unknown, "darwin_host_statistics"),
        };
        self.previous_cpu = cpu_ticks;

        let total_memory = sysctl_u64("hw.memsize");
        let available_memory = read_available_memory_bytes();
        let (total_bytes, available_bytes) = match (total_memory, available_memory) {
            (Some(total), Some(available)) if available <= total => (
                MetricValue::fresh(total, "darwin_sysctl_hw_memsize"),
                MetricValue::fresh(available, "darwin_host_statistics64"),
            ),
            (Some(total), _) => (
                MetricValue::fresh(total, "darwin_sysctl_hw_memsize"),
                unknown_bytes("darwin_host_statistics64"),
            ),
            _ => (
                unknown_bytes("darwin_sysctl_hw_memsize"),
                unknown_bytes("darwin_host_statistics64"),
            ),
        };

        let (storage_total, storage_available) = match read_storage_bytes() {
            Some((total, available)) => (
                MetricValue::fresh(total, "darwin_statfs_root"),
                MetricValue::fresh(available, "darwin_statfs_root"),
            ),
            None => (
                unknown_bytes("darwin_statfs_root"),
                unknown_bytes("darwin_statfs_root"),
            ),
        };

        let (architecture, vram_total_bytes) = if cfg!(target_arch = "aarch64") {
            (
                MemoryArchitecture::Unified,
                MetricValue::unavailable(
                    MetricStatus::NotApplicable,
                    "apple_silicon_unified_memory",
                ),
            )
        } else {
            (
                MemoryArchitecture::Unknown,
                MetricValue::unavailable(MetricStatus::Unsupported, "no_gpu_adapter_v0"),
            )
        };

        let resident_bytes = read_process_resident_bytes()
            .map(|bytes| MetricValue::fresh(bytes, "darwin_task_info_resident_size"))
            .unwrap_or_else(|| unknown_bytes("darwin_task_info"));

        BodySample {
            sequence,
            observed_at_mono_ms,
            observed_at_unix_ms,
            cpu_utilization_ratio,
            memory: MemorySample {
                architecture,
                total_bytes,
                available_bytes,
                swap_total_bytes: unknown_bytes("no_darwin_swap_adapter_v1"),
                swap_available_bytes: unknown_bytes("no_darwin_swap_adapter_v1"),
                vram_total_bytes,
            },
            storage: StorageSample {
                total_bytes: storage_total.clone(),
                available_bytes: storage_available.clone(),
                critical_mounts: vec![StorageMountSample {
                    path: "/".into(),
                    total_bytes: storage_total,
                    available_bytes: storage_available,
                }],
            },
            process: ProcessFootprint {
                resident_bytes,
                scope: "collector_process".into(),
            },
            kernel_pressure: KernelPressureSample::unsupported("no_darwin_psi_adapter_v1"),
        }
    }
}

#[derive(Debug)]
struct BodyStatusService {
    sensor: MacOsBodySensor,
    core: BodyTelemetryCore,
}

impl Default for BodyStatusService {
    fn default() -> Self {
        Self {
            sensor: MacOsBodySensor::default(),
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
        "known_limitations": [
            "cpu utilization is unknown until a second sample establishes a counter delta",
            "available memory is a reclaimable-pages proxy, not macOS memory pressure",
            "gpu, thermal, and power metrics are unavailable in v0",
        ],
    })
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn cpu_ratio_uses_counter_deltas() {
        let previous = CpuTicks {
            user: 100,
            system: 30,
            idle: 870,
            nice: 0,
        };
        let current = CpuTicks {
            user: 120,
            system: 40,
            idle: 940,
            nice: 0,
        };
        assert_eq!(cpu_ratio(previous, current), Some(0.3));
    }

    #[test]
    fn cpu_counter_reset_is_unknown() {
        let previous = CpuTicks {
            user: 100,
            system: 30,
            idle: 870,
            nice: 0,
        };
        let reset = CpuTicks {
            user: 10,
            system: 3,
            idle: 87,
            nice: 0,
        };
        assert_eq!(cpu_ratio(previous, reset), None);
    }
}
