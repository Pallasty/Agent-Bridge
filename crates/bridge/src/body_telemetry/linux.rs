//! Linux read-only body sensor adapter.
//!
//! The core sample uses stable procfs and libc surfaces only. PSI is exposed as
//! an additional status projection, while GPU values remain explicitly
//! unsupported until a separately validated ROCm adapter exists.

use super::{
    local_body_identity, sample_coverage, BodySample, BodySensorAdapter, BodyTelemetryCore,
    KernelPressureSample, MemoryArchitecture, MemorySample, MetricStatus, MetricValue,
    PressurePolicy, ProcessFootprint, StorageMountSample, StorageSample, TaskProcessScopeBinding,
    TaskProcessTreeSample, BODY_STATUS_SCHEMA_V0, BODY_STATUS_SCHEMA_V1,
};
use serde::Serialize;
use serde_json::{json, Value};
use std::collections::{BTreeMap, BTreeSet};
use std::ffi::CString;
use std::fs;
use std::mem::MaybeUninit;
use std::path::{Path, PathBuf};
use std::sync::{Mutex, OnceLock};
use std::time::{Instant, SystemTime, UNIX_EPOCH};

const ADAPTER_ID: &str = "linux_procfs_v1";
const DEFAULT_MIN_SAMPLE_INTERVAL_MS: u64 = 1_000;
const DEFAULT_SAMPLE_TTL_MS: u64 = 5_000;
const PROCESS_TREE_MEMBER_CAP: usize = 4_096;

#[derive(Debug, Clone, Copy)]
struct ProcIdentity {
    ppid: u32,
    start_ticks: u64,
    owner_uid: u32,
    resident_bytes: u64,
}

fn proc_identity(pid: u32) -> Option<ProcIdentity> {
    let status = fs::read_to_string(format!("/proc/{pid}/status")).ok()?;
    let owner_uid = status
        .lines()
        .find_map(|line| line.strip_prefix("Uid:"))?
        .split_whitespace()
        .next()?
        .parse()
        .ok()?;
    let stat = fs::read_to_string(format!("/proc/{pid}/stat")).ok()?;
    let tail = stat.get(stat.rfind(')')? + 1..)?;
    let fields = tail.split_whitespace().collect::<Vec<_>>();
    let ppid = fields.get(1)?.parse().ok()?;
    let start_ticks = fields.get(19)?.parse().ok()?;
    let statm = fs::read_to_string(format!("/proc/{pid}/statm")).ok()?;
    let resident_pages = statm.split_whitespace().nth(1)?.parse::<u64>().ok()?;
    // SAFETY: sysconf with _SC_PAGESIZE has no memory-safety preconditions.
    let page_size = unsafe { libc::sysconf(libc::_SC_PAGESIZE) };
    let resident_bytes =
        (page_size > 0).then(|| resident_pages.checked_mul(page_size as u64))??;
    Some(ProcIdentity {
        ppid,
        start_ticks,
        owner_uid,
        resident_bytes,
    })
}

pub(super) fn bind_process_tree(root_pid: u32) -> Result<TaskProcessScopeBinding, String> {
    if root_pid <= 1 || root_pid > libc::pid_t::MAX as u32 {
        return Err("process-tree root_pid must be a non-system pid representable by pid_t".into());
    }
    let identity = proc_identity(root_pid)
        .ok_or_else(|| format!("process-tree root pid {root_pid} is unavailable"))?;
    // SAFETY: geteuid has no preconditions and does not mutate process state.
    let effective_uid = unsafe { libc::geteuid() };
    if identity.owner_uid != effective_uid {
        return Err("process-tree root must be owned by the current effective user".into());
    }
    Ok(TaskProcessScopeBinding {
        root_pid,
        root_start_ticks: identity.start_ticks,
        owner_uid: identity.owner_uid,
    })
}

pub(super) fn bind_process_tree_expected(
    root_pid: u32,
    expected_start_ticks: u64,
) -> Result<TaskProcessScopeBinding, String> {
    if expected_start_ticks == 0 {
        return Err("process-tree root birth token must be non-zero".into());
    }
    let binding = bind_process_tree(root_pid)?;
    if binding.root_start_ticks != expected_start_ticks {
        return Err(format!(
            "process-tree root birth token mismatch for pid {root_pid}"
        ));
    }
    Ok(binding)
}

pub(super) fn sample_process_tree(binding: &TaskProcessScopeBinding) -> TaskProcessTreeSample {
    let source = "linux_proc_same_user_process_tree";
    let Some(root) = proc_identity(binding.root_pid) else {
        return unavailable_process_tree("root_unavailable", source);
    };
    if root.start_ticks != binding.root_start_ticks || root.owner_uid != binding.owner_uid {
        return unavailable_process_tree("root_identity_changed", source);
    }

    let mut rows = BTreeMap::new();
    let gaps = 0u32;
    let entries = match fs::read_dir("/proc") {
        Ok(entries) => entries,
        Err(_) => return unavailable_process_tree("procfs_unavailable", source),
    };
    for entry in entries.flatten() {
        let Some(pid) = entry
            .file_name()
            .to_str()
            .and_then(|name| name.parse::<u32>().ok())
        else {
            continue;
        };
        match proc_identity(pid) {
            Some(identity) if identity.owner_uid == binding.owner_uid => {
                rows.insert(pid, identity);
            }
            Some(_) => {}
            None => {}
        }
    }
    rows.insert(binding.root_pid, root);
    let mut members = BTreeSet::from([binding.root_pid]);
    loop {
        let before = members.len();
        for (&pid, identity) in &rows {
            if members.contains(&identity.ppid) {
                members.insert(pid);
                if members.len() >= PROCESS_TREE_MEMBER_CAP {
                    break;
                }
            }
        }
        if members.len() == before || members.len() >= PROCESS_TREE_MEMBER_CAP {
            break;
        }
    }
    let resident_bytes = members.iter().fold(0u64, |total, pid| {
        total.saturating_add(rows.get(pid).map_or(0, |row| row.resident_bytes))
    });
    TaskProcessTreeSample {
        scope: "same_user_process_tree".into(),
        status: if members.len() >= PROCESS_TREE_MEMBER_CAP {
            "partial"
        } else {
            "fresh"
        }
        .into(),
        process_count: Some(members.len().try_into().unwrap_or(u32::MAX)),
        resident_bytes: Some(resident_bytes),
        sampling_gaps: gaps,
        source: source.into(),
    }
}

fn unavailable_process_tree(reason: &str, source: &str) -> TaskProcessTreeSample {
    TaskProcessTreeSample {
        scope: "same_user_process_tree".into(),
        status: reason.into(),
        process_count: None,
        resident_bytes: None,
        sampling_gaps: 1,
        source: source.into(),
    }
}

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

fn read_memory_bytes() -> Option<(u64, u64, u64, u64)> {
    let content = fs::read_to_string("/proc/meminfo").ok()?;
    let total = meminfo_bytes(&content, "MemTotal")?;
    let available = meminfo_bytes(&content, "MemAvailable")?;
    let swap_total = meminfo_bytes(&content, "SwapTotal")?;
    let swap_available = meminfo_bytes(&content, "SwapFree")?;
    (available <= total && swap_available <= swap_total).then_some((
        total,
        available,
        swap_total,
        swap_available,
    ))
}

fn read_storage_bytes(path: &Path) -> Option<(u64, u64)> {
    let path = CString::new(path.to_string_lossy().as_bytes()).ok()?;
    let mut stats = MaybeUninit::<libc::statvfs>::zeroed();
    // SAFETY: CString is NUL-terminated and stats is valid writable storage.
    if unsafe { libc::statvfs(path.as_ptr(), stats.as_mut_ptr()) } != 0 {
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

fn critical_mount_paths() -> Vec<PathBuf> {
    let mut paths = BTreeSet::from([PathBuf::from("/")]);
    if let Ok(configured) = std::env::var("AGENT_BRIDGE_BODY_CRITICAL_MOUNTS") {
        for path in configured
            .split(',')
            .map(str::trim)
            .filter(|path| path.starts_with('/'))
        {
            paths.insert(PathBuf::from(path));
        }
    } else if Path::new("/Data").is_dir() {
        paths.insert(PathBuf::from("/Data"));
    }
    paths.into_iter().collect()
}

fn read_storage_mounts() -> Vec<StorageMountSample> {
    critical_mount_paths()
        .into_iter()
        .map(|path| {
            let label = path.to_string_lossy().into_owned();
            let (total_bytes, available_bytes) = read_storage_bytes(&path).map_or_else(
                || {
                    (
                        unknown_bytes("linux_statvfs_critical_mount"),
                        unknown_bytes("linux_statvfs_critical_mount"),
                    )
                },
                |(total, available)| {
                    (
                        MetricValue::fresh(total, "linux_statvfs_critical_mount"),
                        MetricValue::fresh(available, "linux_statvfs_critical_mount"),
                    )
                },
            );
            StorageMountSample {
                path: label,
                total_bytes,
                available_bytes,
            }
        })
        .collect()
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

fn read_kernel_pressure() -> KernelPressureSample {
    let cpu = read_psi("/proc/pressure/cpu");
    let memory = read_psi("/proc/pressure/memory");
    let io = read_psi("/proc/pressure/io");
    KernelPressureSample {
        cpu_some_avg10_ratio: cpu.some_avg10_ratio,
        memory_some_avg10_ratio: memory.some_avg10_ratio,
        memory_full_avg10_ratio: memory.full_avg10_ratio,
        io_some_avg10_ratio: io.some_avg10_ratio,
        io_full_avg10_ratio: io.full_avg10_ratio,
    }
}

fn read_thermal_status() -> Value {
    let Ok(entries) = fs::read_dir("/sys/class/thermal") else {
        return json!({"status":"unsupported","sensor_count":0});
    };
    let temperatures = entries
        .flatten()
        .filter(|entry| {
            entry
                .file_name()
                .to_string_lossy()
                .starts_with("thermal_zone")
        })
        .filter_map(|entry| fs::read_to_string(entry.path().join("temp")).ok())
        .filter_map(|value| value.trim().parse::<f64>().ok())
        .map(|milli_celsius| milli_celsius / 1_000.0)
        .filter(|celsius| celsius.is_finite() && (-50.0..=200.0).contains(celsius))
        .collect::<Vec<_>>();
    json!({
        "status": if temperatures.is_empty() { "unavailable" } else { "ok" },
        "sensor_count": temperatures.len(),
        "max_celsius": temperatures.into_iter().max_by(f64::total_cmp),
        "source": "linux_thermal_sysfs",
    })
}

fn read_power_status() -> Value {
    let root = Path::new("/sys/class/power_supply");
    let Ok(entries) = fs::read_dir(root) else {
        return json!({"status":"unsupported"});
    };
    let mut batteries = Vec::new();
    let mut ac_online = None;
    for entry in entries.flatten() {
        let path = entry.path();
        let kind = fs::read_to_string(path.join("type"))
            .ok()
            .map(|value| value.trim().to_string());
        match kind.as_deref() {
            Some("Battery") => batteries.push(json!({
                "capacity_percent": fs::read_to_string(path.join("capacity")).ok().and_then(|v| v.trim().parse::<u64>().ok()),
                "charging_status": fs::read_to_string(path.join("status")).ok().map(|v| v.trim().to_string()),
            })),
            Some("Mains" | "USB") => {
                let online = fs::read_to_string(path.join("online"))
                    .ok()
                    .and_then(|value| value.trim().parse::<u8>().ok())
                    .map(|value| value == 1);
                ac_online = Some(ac_online.unwrap_or(false) || online.unwrap_or(false));
            }
            _ => {}
        }
    }
    json!({
        "status": if batteries.is_empty() && ac_online.is_none() { "unavailable" } else { "ok" },
        "ac_online": ac_online,
        "batteries": batteries,
        "source": "linux_power_supply_sysfs",
    })
}

fn read_network_status() -> Value {
    let root = Path::new("/sys/class/net");
    let Ok(entries) = fs::read_dir(root) else {
        return json!({"status":"unsupported"});
    };
    let mut interface_count = 0_u64;
    let mut interfaces_up = 0_u64;
    let mut rx_bytes = 0_u64;
    let mut tx_bytes = 0_u64;
    for entry in entries.flatten() {
        if entry.file_name() == "lo" {
            continue;
        }
        interface_count += 1;
        let path = entry.path();
        if fs::read_to_string(path.join("operstate"))
            .ok()
            .is_some_and(|value| value.trim() == "up")
        {
            interfaces_up += 1;
        }
        rx_bytes = rx_bytes.saturating_add(
            fs::read_to_string(path.join("statistics/rx_bytes"))
                .ok()
                .and_then(|value| value.trim().parse::<u64>().ok())
                .unwrap_or(0),
        );
        tx_bytes = tx_bytes.saturating_add(
            fs::read_to_string(path.join("statistics/tx_bytes"))
                .ok()
                .and_then(|value| value.trim().parse::<u64>().ok())
                .unwrap_or(0),
        );
    }
    json!({
        "status": if interface_count == 0 { "unavailable" } else { "ok" },
        "interface_count": interface_count,
        "interfaces_up": interfaces_up,
        "rx_bytes_total": rx_bytes,
        "tx_bytes_total": tx_bytes,
        "throughput_available": false,
        "source": "linux_net_sysfs",
    })
}

fn detect_drm_driver() -> Option<String> {
    fs::read_dir("/sys/class/drm")
        .ok()?
        .flatten()
        .filter(|entry| entry.file_name().to_string_lossy().starts_with("card"))
        .find_map(|entry| {
            fs::read_link(entry.path().join("device/driver"))
                .ok()
                .and_then(|path| {
                    path.file_name()
                        .map(|name| name.to_string_lossy().into_owned())
                })
        })
}

fn sample_interval_ms() -> u64 {
    std::env::var("AGENT_BRIDGE_BODY_MIN_SAMPLE_INTERVAL_MS")
        .ok()
        .and_then(|value| value.parse::<u64>().ok())
        .unwrap_or(DEFAULT_MIN_SAMPLE_INTERVAL_MS)
        .clamp(250, 60_000)
}

fn sample_ttl_ms() -> u64 {
    std::env::var("AGENT_BRIDGE_BODY_SAMPLE_TTL_MS")
        .ok()
        .and_then(|value| value.parse::<u64>().ok())
        .unwrap_or(DEFAULT_SAMPLE_TTL_MS)
        .max(sample_interval_ms())
        .clamp(1_000, 300_000)
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

        let (memory_total, memory_available, swap_total, swap_available) = match read_memory_bytes()
        {
            Some((total, available, swap_total, swap_available)) => (
                MetricValue::fresh(total, "linux_proc_meminfo"),
                MetricValue::fresh(available, "linux_proc_meminfo"),
                MetricValue::fresh(swap_total, "linux_proc_meminfo"),
                MetricValue::fresh(swap_available, "linux_proc_meminfo"),
            ),
            None => (
                unknown_bytes("linux_proc_meminfo"),
                unknown_bytes("linux_proc_meminfo"),
                unknown_bytes("linux_proc_meminfo"),
                unknown_bytes("linux_proc_meminfo"),
            ),
        };
        let critical_mounts = read_storage_mounts();
        let root = critical_mounts.iter().find(|mount| mount.path == "/");
        let storage_total = root
            .map(|mount| mount.total_bytes.clone())
            .unwrap_or_else(|| unknown_bytes("linux_statvfs_root"));
        let storage_available = root
            .map(|mount| mount.available_bytes.clone())
            .unwrap_or_else(|| unknown_bytes("linux_statvfs_root"));
        let resident_bytes = read_process_resident_bytes()
            .map(|bytes| MetricValue::fresh(bytes, "linux_proc_self_statm"))
            .unwrap_or_else(|| unknown_bytes("linux_proc_self_statm"));
        let drm_driver = detect_drm_driver();
        let (architecture, vram_total_bytes) = if drm_driver.as_deref() == Some("i915") {
            (
                MemoryArchitecture::Unified,
                MetricValue::unavailable(MetricStatus::NotApplicable, "linux_i915_shared_memory"),
            )
        } else {
            (
                MemoryArchitecture::Unknown,
                MetricValue::unavailable(MetricStatus::Unsupported, "linux_drm_vram_unavailable"),
            )
        };

        BodySample {
            sequence,
            observed_at_mono_ms,
            observed_at_unix_ms,
            cpu_utilization_ratio,
            memory: MemorySample {
                architecture,
                total_bytes: memory_total,
                available_bytes: memory_available,
                swap_total_bytes: swap_total,
                swap_available_bytes: swap_available,
                vram_total_bytes,
            },
            storage: StorageSample {
                total_bytes: storage_total,
                available_bytes: storage_available,
                critical_mounts,
            },
            process: ProcessFootprint {
                scope: "collector_process".into(),
                resident_bytes,
            },
            kernel_pressure: read_kernel_pressure(),
        }
    }
}

#[derive(Debug)]
struct BodyStatusService {
    sensor: LinuxBodySensor,
    core: BodyTelemetryCore,
    last_sampled_mono_ms: Option<u64>,
}

impl Default for BodyStatusService {
    fn default() -> Self {
        Self {
            sensor: LinuxBodySensor::default(),
            core: BodyTelemetryCore::new(72, PressurePolicy::default()),
            last_sampled_mono_ms: None,
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
    let now_mono_ms = monotonic_ms();
    let now_unix_ms = unix_ms();
    let should_sample = service
        .last_sampled_mono_ms
        .is_none_or(|last| now_mono_ms.saturating_sub(last) >= sample_interval_ms());
    if should_sample {
        let sample = service.sensor.sample(now_mono_ms, now_unix_ms);
        service.core.ingest(sample);
        service.last_sampled_mono_ms = Some(now_mono_ms);
    }
    let pressure = service.core.pressure();
    let sample = service
        .core
        .history()
        .latest()
        .expect("sample just ingested");
    let coverage = sample_coverage(sample);
    let identity = local_body_identity();
    let sample_age_ms = now_mono_ms.saturating_sub(sample.observed_at_mono_ms);
    let expires_at_unix_ms = sample
        .observed_at_unix_ms
        .saturating_add(sample_ttl_ms().try_into().unwrap_or(i64::MAX));
    let drm_driver = detect_drm_driver();
    json!({
        "schema_version": BODY_STATUS_SCHEMA_V1,
        "compatible_with": [BODY_STATUS_SCHEMA_V0],
        "mode": "shadow_only",
        "enabled": true,
        "status": coverage.status,
        "read_only": true,
        "persists_raw_samples": false,
        "identity": identity,
        "organ_id": "interoception",
        "collector": {
            "adapter_id": ADAPTER_ID,
            "build_git_sha": crate::build_identity::GIT_SHA,
            "sampling": "on_demand",
            "background_sampler": false,
            "raw_history_capacity": 72,
            "min_sample_interval_ms": sample_interval_ms(),
            "sample_ttl_ms": sample_ttl_ms(),
            "sample_reused": !should_sample,
        },
        "freshness": {
            "captured_at_unix_ms": sample.observed_at_unix_ms,
            "received_at_unix_ms": now_unix_ms,
            "age_ms": sample_age_ms,
            "expires_at_unix_ms": expires_at_unix_ms,
            "status": if sample_age_ms <= sample_ttl_ms() { "fresh" } else { "stale" },
        },
        "coverage": coverage,
        "pressure": pressure,
        "sample": sample,
        "history_len": service.core.history().len(),
        "linux_psi": {
            "cpu": {"some_avg10_ratio": sample.kernel_pressure.cpu_some_avg10_ratio},
            "memory": {
                "some_avg10_ratio": sample.kernel_pressure.memory_some_avg10_ratio,
                "full_avg10_ratio": sample.kernel_pressure.memory_full_avg10_ratio,
            },
            "io": {
                "some_avg10_ratio": sample.kernel_pressure.io_some_avg10_ratio,
                "full_avg10_ratio": sample.kernel_pressure.io_full_avg10_ratio,
            },
        },
        "gpu": {
            "status": if drm_driver.is_some() { "identified_metrics_unavailable" } else { "unsupported" },
            "driver": drm_driver,
            "utilization_available": false,
            "source": "linux_drm_sysfs",
        },
        "thermal": read_thermal_status(),
        "power": read_power_status(),
        "network": read_network_status(),
        "known_limitations": [
            "cpu utilization is unknown until a second sample establishes a counter delta",
            "PSI avg10 is a short-window stall ratio and does not identify a process",
            "collector RSS is not task or process-tree footprint",
            "GPU utilization and disk/network throughput remain unavailable in v1",
        ],
    })
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::process::Command;

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

    #[test]
    fn process_tree_binding_is_same_user_and_includes_a_direct_child() {
        let binding = bind_process_tree(std::process::id()).expect("bind current process");
        let mut child = Command::new("sleep").arg("2").spawn().expect("spawn child");
        let sample = sample_process_tree(&binding);
        let _ = child.kill();
        let _ = child.wait();
        assert_eq!(sample.status, "fresh");
        assert!(sample.process_count.is_some_and(|count| count >= 2));
        assert!(sample.resident_bytes.is_some_and(|bytes| bytes > 0));
        assert_eq!(sample.scope, "same_user_process_tree");
    }

    #[test]
    fn process_tree_rejects_unsafe_pid_and_birth_token_values() {
        assert!(bind_process_tree(0).is_err());
        assert!(bind_process_tree(1).is_err());
        assert!(bind_process_tree(u32::MAX).is_err());
        assert!(bind_process_tree_expected(std::process::id(), 0).is_err());
    }

    fn read_memory_bytes_from(content: &str) -> Option<(u64, u64)> {
        let total = meminfo_bytes(content, "MemTotal")?;
        let available = meminfo_bytes(content, "MemAvailable")?;
        (available <= total).then_some((total, available))
    }
}
