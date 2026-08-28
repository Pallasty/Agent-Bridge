//! Platform-neutral, read-only body telemetry primitives.
//!
//! This module deliberately does not know how to query a host. Platform
//! adapters supply [`BodySample`] values; this core owns their truth semantics:
//! bounded history, stale/unsupported states, and pressure hysteresis. Keeping
//! those rules here prevents macOS, Linux, and test adapters from disagreeing
//! about what the agent's body currently knows.

use serde::{Deserialize, Serialize};
use serde_json::{json, Value};
use sha2::{Digest, Sha256};
use std::collections::{BTreeMap, VecDeque};
use std::fs;
use std::sync::{Mutex, OnceLock};
use std::time::{SystemTime, UNIX_EPOCH};

#[cfg(target_os = "linux")]
pub mod linux;
#[cfg(target_os = "macos")]
pub mod macos;

pub const BODY_STATUS_SCHEMA_V0: &str = "agent_bridge.body_status.v0";
pub const BODY_STATUS_SCHEMA_V1: &str = "agent_bridge.body_status.v1";
pub const TASK_RESOURCE_SPAN_SCHEMA_V0: &str = "agent_bridge.task_resource_span.v0";
pub const TASK_RESOURCE_SPAN_SCHEMA_V1: &str = "agent_bridge.task_resource_span.v1";
pub const TASK_RESOURCE_SPAN_SCHEMA_V2: &str = "agent_bridge.task_resource_span.v2";
pub const TASK_RESOURCE_SPAN_SCHEMA_V3: &str = "agent_bridge.task_resource_span.v3";
pub const TASK_TERMINAL_RESOURCES_SCHEMA_V0: &str =
    "agent_bridge.task_terminal_resources.v0";
pub const TASK_WORKLOAD_RESOURCES_SCHEMA_V0: &str =
    "agent_bridge.task_workload_resources.v0";
pub const SHADOW_REFLEX_ADVICE_SCHEMA_V0: &str = "agent_bridge.shadow_reflex_advice.v0";
pub const BODY_SCHEDULING_ADVICE_SCHEMA_V0: &str = "agent_bridge.body_scheduling_advice.v0";
pub const BODY_SCHEDULING_REPORT_SCHEMA_V0: &str = "agent_bridge.body_scheduling_report.v0";

/// Whether a metric is safe to treat as current.
///
/// A stale or unavailable metric must not expose its last value as if it were
/// live. `NotApplicable` is distinct from `Unsupported`: unified-memory hosts,
/// for example, do not have a separate VRAM pool to query.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum MetricStatus {
    Fresh,
    Stale,
    Unsupported,
    NotApplicable,
    Unknown,
}

impl MetricStatus {
    pub fn is_live(self) -> bool {
        matches!(self, Self::Fresh)
    }
}

/// A metric with an explicit source and freshness state.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct MetricValue<T> {
    /// Present only when `status` is `fresh`.
    pub value: Option<T>,
    pub status: MetricStatus,
    pub source: String,
}

impl<T> MetricValue<T> {
    pub fn fresh(value: T, source: impl Into<String>) -> Self {
        Self {
            value: Some(value),
            status: MetricStatus::Fresh,
            source: source.into(),
        }
    }

    pub fn unavailable(status: MetricStatus, source: impl Into<String>) -> Self {
        debug_assert!(
            !status.is_live(),
            "fresh metrics must carry a concrete value"
        );
        Self {
            value: None,
            status,
            source: source.into(),
        }
    }

    pub fn live(&self) -> Option<&T> {
        self.status
            .is_live()
            .then_some(self.value.as_ref())
            .flatten()
    }
}

fn unavailable_metric<T>(status: MetricStatus, source: impl Into<String>) -> MetricValue<T> {
    MetricValue::unavailable(status, source)
}

/// How the host presents graphics memory to the operating system.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum MemoryArchitecture {
    Unified,
    Discrete,
    Unknown,
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct MemorySample {
    pub architecture: MemoryArchitecture,
    pub total_bytes: MetricValue<u64>,
    pub available_bytes: MetricValue<u64>,
    /// Swap is a separate pressure surface. A healthy `MemAvailable` value does
    /// not make heavy swap use disappear.
    pub swap_total_bytes: MetricValue<u64>,
    pub swap_available_bytes: MetricValue<u64>,
    /// Separate VRAM is intentionally `not_applicable` on unified-memory hosts.
    pub vram_total_bytes: MetricValue<u64>,
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct StorageSample {
    /// Compatibility projection for the root mount.
    pub total_bytes: MetricValue<u64>,
    pub available_bytes: MetricValue<u64>,
    /// Explicit critical mounts. Pressure uses the most constrained live mount
    /// rather than silently treating `/` as the whole body.
    #[serde(default)]
    pub critical_mounts: Vec<StorageMountSample>,
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct StorageMountSample {
    pub path: String,
    pub total_bytes: MetricValue<u64>,
    pub available_bytes: MetricValue<u64>,
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct ProcessFootprint {
    /// `collector_process` in v1. Task/cgroup footprint must use a separately
    /// bound process-tree adapter and must never be inferred from this value.
    pub scope: String,
    pub resident_bytes: MetricValue<u64>,
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct KernelPressureSample {
    pub cpu_some_avg10_ratio: MetricValue<f64>,
    pub memory_some_avg10_ratio: MetricValue<f64>,
    pub memory_full_avg10_ratio: MetricValue<f64>,
    pub io_some_avg10_ratio: MetricValue<f64>,
    pub io_full_avg10_ratio: MetricValue<f64>,
}

impl KernelPressureSample {
    pub fn unsupported(source: &str) -> Self {
        Self {
            cpu_some_avg10_ratio: MetricValue::unavailable(MetricStatus::Unsupported, source),
            memory_some_avg10_ratio: MetricValue::unavailable(MetricStatus::Unsupported, source),
            memory_full_avg10_ratio: MetricValue::unavailable(MetricStatus::Unsupported, source),
            io_some_avg10_ratio: MetricValue::unavailable(MetricStatus::Unsupported, source),
            io_full_avg10_ratio: MetricValue::unavailable(MetricStatus::Unsupported, source),
        }
    }

    fn peak_live_ratio(&self) -> Option<f64> {
        [
            self.cpu_some_avg10_ratio.live().copied(),
            self.memory_some_avg10_ratio.live().copied(),
            self.memory_full_avg10_ratio.live().copied(),
            self.io_some_avg10_ratio.live().copied(),
            self.io_full_avg10_ratio.live().copied(),
        ]
        .into_iter()
        .flatten()
        .filter_map(finite_ratio)
        .max_by(f64::total_cmp)
    }
}

/// One point-in-time host observation. `observed_at_mono_ms` is monotonic and
/// should be used for ordering and age; `observed_at_unix_ms` is for display.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct BodySample {
    pub sequence: u64,
    pub observed_at_mono_ms: u64,
    pub observed_at_unix_ms: i64,
    /// Normalized [0, 1] host-aggregate CPU utilization, never a raw counter.
    pub cpu_utilization_ratio: MetricValue<f64>,
    pub memory: MemorySample,
    pub storage: StorageSample,
    pub process: ProcessFootprint,
    pub kernel_pressure: KernelPressureSample,
}

impl BodySample {
    pub fn unknown(sequence: u64, observed_at_mono_ms: u64, observed_at_unix_ms: i64) -> Self {
        Self {
            sequence,
            observed_at_mono_ms,
            observed_at_unix_ms,
            cpu_utilization_ratio: unavailable_metric(MetricStatus::Unknown, "no_sample"),
            memory: MemorySample {
                architecture: MemoryArchitecture::Unknown,
                total_bytes: unavailable_metric(MetricStatus::Unknown, "no_sample"),
                available_bytes: unavailable_metric(MetricStatus::Unknown, "no_sample"),
                swap_total_bytes: unavailable_metric(MetricStatus::Unknown, "no_sample"),
                swap_available_bytes: unavailable_metric(MetricStatus::Unknown, "no_sample"),
                vram_total_bytes: unavailable_metric(MetricStatus::Unknown, "no_sample"),
            },
            storage: StorageSample {
                total_bytes: unavailable_metric(MetricStatus::Unknown, "no_sample"),
                available_bytes: unavailable_metric(MetricStatus::Unknown, "no_sample"),
                critical_mounts: Vec::new(),
            },
            process: ProcessFootprint {
                scope: "collector_process".into(),
                resident_bytes: unavailable_metric(MetricStatus::Unknown, "no_sample"),
            },
            kernel_pressure: KernelPressureSample::unsupported("no_sample"),
        }
    }
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct BodyIdentity {
    pub body_id: String,
    pub body_instance_id: String,
    pub platform: String,
    pub identity_source: String,
    pub lifecycle_epoch_source: String,
}

fn short_digest(value: &str) -> String {
    let digest = Sha256::digest(value.as_bytes());
    format!("{:x}", digest)[..16].to_string()
}

/// Stable body identity plus a boot/process lifecycle epoch. Raw machine-id and
/// boot-id values never leave the adapter.
pub fn local_body_identity() -> BodyIdentity {
    static IDENTITY: OnceLock<BodyIdentity> = OnceLock::new();
    IDENTITY
        .get_or_init(|| {
            let platform = std::env::consts::OS.to_string();
            let configured = std::env::var("AGENT_BRIDGE_BODY_ID")
                .ok()
                .map(|value| value.trim().to_string())
                .filter(|value| !value.is_empty());
            #[cfg(target_os = "linux")]
            let machine_seed = fs::read_to_string("/etc/machine-id")
                .ok()
                .map(|value| value.trim().to_string())
                .filter(|value| !value.is_empty());
            #[cfg(not(target_os = "linux"))]
            let machine_seed: Option<String> = None;
            let (body_id, identity_source) = if let Some(configured) = configured {
                (configured, "configured_env".to_string())
            } else if let Some(seed) = machine_seed {
                (
                    format!("body-{platform}-{}", short_digest(&seed)),
                    "hashed_machine_id".to_string(),
                )
            } else {
                (
                    format!("body-{platform}-local"),
                    "platform_local_fallback".to_string(),
                )
            };
            #[cfg(target_os = "linux")]
            let lifecycle_seed = fs::read_to_string("/proc/sys/kernel/random/boot_id")
                .ok()
                .map(|value| value.trim().to_string())
                .filter(|value| !value.is_empty());
            #[cfg(not(target_os = "linux"))]
            let lifecycle_seed: Option<String> = None;
            let (epoch, lifecycle_epoch_source) = lifecycle_seed.map_or_else(
                || {
                    (
                        format!("process-{}", process_monotonic_epoch()),
                        "process_epoch".to_string(),
                    )
                },
                |seed| (short_digest(&seed), "hashed_boot_id".to_string()),
            );
            BodyIdentity {
                body_instance_id: format!("{body_id}@{epoch}"),
                body_id,
                platform,
                identity_source,
                lifecycle_epoch_source,
            }
        })
        .clone()
}

fn process_monotonic_epoch() -> u64 {
    static EPOCH: OnceLock<u64> = OnceLock::new();
    *EPOCH.get_or_init(|| {
        let unix_nanos = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .map(|duration| duration.as_nanos())
            .unwrap_or_default();
        let seed = format!("{}:{unix_nanos}", std::process::id());
        let digest = Sha256::digest(seed.as_bytes());
        u64::from_be_bytes(
            digest[..8]
                .try_into()
                .expect("sha256 prefix is eight bytes"),
        )
    })
}

#[derive(Debug, Clone, PartialEq, Serialize)]
pub struct SampleCoverage {
    pub status: &'static str,
    pub required_fresh: usize,
    pub required_total: usize,
    pub required_ratio: f64,
    pub unknown_required: Vec<&'static str>,
}

pub fn sample_coverage(sample: &BodySample) -> SampleCoverage {
    let required = [
        ("host_cpu", sample.cpu_utilization_ratio.status),
        ("memory_total", sample.memory.total_bytes.status),
        ("memory_available", sample.memory.available_bytes.status),
        ("root_storage_total", sample.storage.total_bytes.status),
        (
            "root_storage_available",
            sample.storage.available_bytes.status,
        ),
        ("collector_rss", sample.process.resident_bytes.status),
    ];
    let required_fresh = required
        .iter()
        .filter(|(_, status)| status.is_live())
        .count();
    let unknown_required = required
        .iter()
        .filter(|(_, status)| !status.is_live())
        .map(|(name, _)| *name)
        .collect::<Vec<_>>();
    let status = if required_fresh == required.len() {
        "ok"
    } else if required_fresh == 0 {
        "unavailable"
    } else {
        "partial"
    };
    SampleCoverage {
        status,
        required_fresh,
        required_total: required.len(),
        required_ratio: required_fresh as f64 / required.len() as f64,
        unknown_required,
    }
}

/// A source of samples. Adapters are read-only by contract; they do not take
/// actions or persist raw observations.
pub trait BodySensorAdapter {
    fn adapter_id(&self) -> &str;
    fn sample(&mut self, observed_at_mono_ms: u64, observed_at_unix_ms: i64) -> BodySample;
}

/// Deterministic test adapter. Once its queue is drained it returns a new
/// `unknown` sample rather than repeating an old value.
#[derive(Debug, Clone)]
pub struct FakeBodySensorAdapter {
    adapter_id: String,
    samples: VecDeque<BodySample>,
    next_sequence: u64,
}

impl FakeBodySensorAdapter {
    pub fn new(
        adapter_id: impl Into<String>,
        samples: impl IntoIterator<Item = BodySample>,
    ) -> Self {
        let samples = samples.into_iter().collect::<VecDeque<_>>();
        let next_sequence = samples
            .back()
            .map(|sample| sample.sequence.saturating_add(1))
            .unwrap_or(0);
        Self {
            adapter_id: adapter_id.into(),
            samples,
            next_sequence,
        }
    }

    pub fn push(&mut self, sample: BodySample) {
        self.next_sequence = self.next_sequence.max(sample.sequence.saturating_add(1));
        self.samples.push_back(sample);
    }
}

impl BodySensorAdapter for FakeBodySensorAdapter {
    fn adapter_id(&self) -> &str {
        &self.adapter_id
    }

    fn sample(&mut self, observed_at_mono_ms: u64, observed_at_unix_ms: i64) -> BodySample {
        self.samples.pop_front().unwrap_or_else(|| {
            let sample =
                BodySample::unknown(self.next_sequence, observed_at_mono_ms, observed_at_unix_ms);
            self.next_sequence = self.next_sequence.saturating_add(1);
            sample
        })
    }
}

/// In-memory only, bounded sample history. Capacity zero is normalized to one
/// so callers cannot accidentally create an unbounded or permanently empty
/// telemetry stream.
#[derive(Debug, Clone)]
pub struct SampleHistory {
    capacity: usize,
    samples: VecDeque<BodySample>,
}

impl SampleHistory {
    pub fn new(capacity: usize) -> Self {
        Self {
            capacity: capacity.max(1),
            samples: VecDeque::with_capacity(capacity.max(1)),
        }
    }

    pub fn push(&mut self, sample: BodySample) {
        if self.samples.len() == self.capacity {
            self.samples.pop_front();
        }
        self.samples.push_back(sample);
    }

    pub fn latest(&self) -> Option<&BodySample> {
        self.samples.back()
    }

    pub fn len(&self) -> usize {
        self.samples.len()
    }

    pub fn is_empty(&self) -> bool {
        self.samples.is_empty()
    }

    pub fn iter(&self) -> impl ExactSizeIterator<Item = &BodySample> {
        self.samples.iter()
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum PressureLevel {
    Unknown,
    Nominal,
    Elevated,
    High,
    Critical,
}

#[derive(Debug, Clone, Copy, PartialEq)]
pub struct PressurePolicy {
    pub elevated_at: f64,
    pub high_at: f64,
    pub critical_at: f64,
    pub recovery_margin: f64,
    pub rise_samples: u8,
    pub fall_samples: u8,
}

impl Default for PressurePolicy {
    fn default() -> Self {
        Self {
            elevated_at: 0.70,
            high_at: 0.85,
            critical_at: 0.95,
            recovery_margin: 0.05,
            rise_samples: 2,
            fall_samples: 3,
        }
    }
}

impl PressurePolicy {
    fn normalized(self) -> Self {
        let elevated_at = finite_ratio(self.elevated_at).unwrap_or(0.70);
        let high_at = finite_ratio(self.high_at).unwrap_or(0.85).max(elevated_at);
        let critical_at = finite_ratio(self.critical_at).unwrap_or(0.95).max(high_at);
        Self {
            elevated_at,
            high_at,
            critical_at,
            recovery_margin: finite_ratio(self.recovery_margin).unwrap_or(0.05),
            rise_samples: self.rise_samples.max(1),
            fall_samples: self.fall_samples.max(1),
        }
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Default)]
pub struct PressureInput {
    pub cpu_ratio: Option<f64>,
    pub memory_ratio: Option<f64>,
    pub swap_ratio: Option<f64>,
    pub storage_ratio: Option<f64>,
    pub kernel_stall_ratio: Option<f64>,
}

impl PressureInput {
    pub fn from_sample(sample: &BodySample) -> Self {
        Self {
            cpu_ratio: sample.cpu_utilization_ratio.live().copied(),
            memory_ratio: used_ratio(&sample.memory.total_bytes, &sample.memory.available_bytes),
            swap_ratio: used_ratio(
                &sample.memory.swap_total_bytes,
                &sample.memory.swap_available_bytes,
            ),
            storage_ratio: sample
                .storage
                .critical_mounts
                .iter()
                .filter_map(|mount| used_ratio(&mount.total_bytes, &mount.available_bytes))
                .chain(used_ratio(
                    &sample.storage.total_bytes,
                    &sample.storage.available_bytes,
                ))
                .max_by(f64::total_cmp),
            kernel_stall_ratio: sample.kernel_pressure.peak_live_ratio(),
        }
    }

    fn peak(self) -> Option<f64> {
        [
            self.cpu_ratio,
            self.memory_ratio,
            self.swap_ratio,
            self.storage_ratio,
            self.kernel_stall_ratio,
        ]
        .into_iter()
        .flatten()
        .filter_map(finite_ratio)
        .max_by(f64::total_cmp)
    }
}

/// Hysteretic pressure reducer. Escalation and recovery require consecutive
/// observations, and recovery has a separate margin to avoid a boundary flap.
#[derive(Debug, Clone)]
pub struct PressureReducer {
    policy: PressurePolicy,
    current: PressureLevel,
    pending: Option<PressureLevel>,
    pending_samples: u8,
}

impl PressureReducer {
    pub fn new(policy: PressurePolicy) -> Self {
        Self {
            policy: policy.normalized(),
            current: PressureLevel::Unknown,
            pending: None,
            pending_samples: 0,
        }
    }

    pub fn current(&self) -> PressureLevel {
        self.current
    }

    pub fn update(&mut self, input: PressureInput) -> PressureLevel {
        let Some(peak) = input.peak() else {
            self.current = PressureLevel::Unknown;
            self.pending = None;
            self.pending_samples = 0;
            return self.current;
        };

        let target = self.target_for(peak);
        if self.current == PressureLevel::Unknown {
            self.current = target;
            self.pending = None;
            self.pending_samples = 0;
            return self.current;
        }

        if target == self.current {
            self.pending = None;
            self.pending_samples = 0;
            return self.current;
        }

        let required = if target > self.current {
            self.policy.rise_samples
        } else {
            self.policy.fall_samples
        };
        if self.pending == Some(target) {
            self.pending_samples = self.pending_samples.saturating_add(1);
        } else {
            self.pending = Some(target);
            self.pending_samples = 1;
        }
        if self.pending_samples >= required {
            self.current = target;
            self.pending = None;
            self.pending_samples = 0;
        }
        self.current
    }

    fn target_for(&self, peak: f64) -> PressureLevel {
        let p = &self.policy;
        match self.current {
            PressureLevel::Critical if peak >= p.critical_at - p.recovery_margin => {
                PressureLevel::Critical
            }
            PressureLevel::High if peak >= p.high_at - p.recovery_margin => PressureLevel::High,
            PressureLevel::Elevated if peak >= p.elevated_at - p.recovery_margin => {
                PressureLevel::Elevated
            }
            _ if peak >= p.critical_at => PressureLevel::Critical,
            _ if peak >= p.high_at => PressureLevel::High,
            _ if peak >= p.elevated_at => PressureLevel::Elevated,
            _ => PressureLevel::Nominal,
        }
    }
}

/// Small platform-independent coordinator used by future runtime services.
#[derive(Debug, Clone)]
pub struct BodyTelemetryCore {
    history: SampleHistory,
    pressure: PressureReducer,
}

impl BodyTelemetryCore {
    pub fn new(history_capacity: usize, pressure_policy: PressurePolicy) -> Self {
        Self {
            history: SampleHistory::new(history_capacity),
            pressure: PressureReducer::new(pressure_policy),
        }
    }

    pub fn ingest(&mut self, sample: BodySample) -> PressureLevel {
        let pressure = self.pressure.update(PressureInput::from_sample(&sample));
        self.history.push(sample);
        pressure
    }

    pub fn history(&self) -> &SampleHistory {
        &self.history
    }

    pub fn pressure(&self) -> PressureLevel {
        self.pressure.current()
    }
}

/// Whether the host collector may observe the local machine. The default is
/// deliberately off so merely updating Agent-Bridge cannot begin a new local
/// telemetry stream.
pub fn body_telemetry_enabled() -> bool {
    matches!(
        std::env::var("AGENT_BRIDGE_BODY_TELEMETRY")
            .ok()
            .as_deref()
            .map(str::trim)
            .map(str::to_ascii_lowercase)
            .as_deref(),
        Some("1" | "true" | "yes" | "on")
    )
}

/// Read-only status projection used by the MCP surface. It intentionally
/// performs no sampling when the feature flag is disabled.
pub fn body_status_snapshot() -> Value {
    if !body_telemetry_enabled() {
        return disabled_body_status();
    }

    #[cfg(target_os = "macos")]
    {
        return macos::body_status_snapshot();
    }

    #[cfg(target_os = "linux")]
    {
        return linux::body_status_snapshot();
    }

    #[cfg(not(any(target_os = "macos", target_os = "linux")))]
    {
        json!({
            "schema_version": BODY_STATUS_SCHEMA_V1,
            "compatible_with": [BODY_STATUS_SCHEMA_V0],
            "mode": "shadow_only",
            "enabled": true,
            "status": "unsupported",
            "reason": "a host sensor adapter has not been implemented for this platform",
            "platform": std::env::consts::OS,
            "read_only": true,
            "persists_raw_samples": false,
        })
    }
}

/// Produce a non-executing recommendation from the current pressure projection.
/// The reducer behind `body_status_snapshot` already applies hysteresis; this
/// function deliberately adds no background loop, persistence, or actuator.
pub fn body_reflex_advice_snapshot() -> Value {
    let status = body_status_snapshot();
    shadow_reflex_advice_from_status(&status)
}

pub(crate) fn shadow_reflex_advice_from_status(status: &Value) -> Value {
    let enabled = status
        .get("enabled")
        .and_then(Value::as_bool)
        .unwrap_or(false);
    let pressure = status
        .get("pressure")
        .and_then(Value::as_str)
        .unwrap_or("unknown");
    let (recommendation, reason) = match (enabled, pressure) {
        (false, _) => (
            "observe_only",
            "telemetry is disabled, so no resource-based recommendation is available",
        ),
        (_, "nominal") => (
            "continue_with_normal_scope",
            "pressure is nominal after the collector's hysteresis reduction",
        ),
        (_, "elevated") => (
            "prefer_lightweight_next_step",
            "pressure is elevated; defer optional heavyweight work when practical",
        ),
        (_, "high") => (
            "defer_new_heavy_work",
            "pressure is high; avoid starting new heavyweight work until pressure recovers",
        ),
        (_, "critical") => (
            "request_operator_review_before_heavy_work",
            "pressure is critical; this is advisory only and never pauses or changes host work",
        ),
        _ => (
            "observe_only",
            "pressure is unknown or unsupported, so the reflex fails closed",
        ),
    };

    json!({
        "schema_version": SHADOW_REFLEX_ADVICE_SCHEMA_V0,
        "mode": "advisory_only",
        "read_only": true,
        "executes_actions": false,
        "persists_raw_samples": false,
        "pressure": pressure,
        "recommendation": recommendation,
        "reason": reason,
        "safety": {
            "does_not_pause_tasks": true,
            "does_not_change_system_settings": true,
            "does_not_spawn_or_stop_processes": true,
            "operator_confirmation_required_for_execution": true,
        }
    })
}

/// Produce workload-aware, report-only scheduling guidance. The caller remains
/// authoritative: this projection never changes concurrency, routing, or task
/// admission.
pub fn body_scheduling_advice_snapshot(workload_class: &str, requested_parallelism: u64) -> Value {
    let status = body_status_snapshot();
    body_scheduling_advice_from_status(&status, workload_class, requested_parallelism)
}

pub(crate) fn body_scheduling_advice_from_status(
    status: &Value,
    workload_class: &str,
    requested_parallelism: u64,
) -> Value {
    let enabled = status
        .get("enabled")
        .and_then(Value::as_bool)
        .unwrap_or(false);
    let pressure = status
        .get("pressure")
        .and_then(Value::as_str)
        .unwrap_or("unknown");
    let workload_class = match workload_class.trim() {
        "light" => "light",
        "standard" => "standard",
        "heavy" => "heavy",
        "sustained" => "sustained",
        "remote_heavy" => "remote_heavy",
        _ => "standard",
    };
    let requested_parallelism = requested_parallelism.max(1);
    let is_heavy = matches!(workload_class, "heavy" | "sustained");
    let is_remote = workload_class == "remote_heavy";

    let (recommendation, reason, suggested_max_parallelism) = if !enabled {
        (
            "observe_only",
            "telemetry is disabled, so scheduling remains caller-directed",
            requested_parallelism,
        )
    } else {
        match pressure {
            "nominal" => (
                "start_as_requested",
                "pressure is nominal after hysteresis reduction",
                requested_parallelism,
            ),
            "elevated" if is_remote => (
                "start_remote_as_requested",
                "the heavyweight work is remote, so local pressure only warrants observation",
                requested_parallelism,
            ),
            "elevated" if is_heavy => (
                "prefer_single_heavy_task",
                "pressure is elevated; avoid optional local heavyweight concurrency",
                1,
            ),
            "elevated" => (
                "prefer_lightweight_next_step",
                "pressure is elevated; keep optional local concurrency bounded",
                requested_parallelism.min(1),
            ),
            "high" if is_remote => (
                "prefer_remote_execution",
                "pressure is high locally, while the requested heavyweight work is remote",
                requested_parallelism,
            ),
            "high" if is_heavy => (
                "defer_optional_heavy_work",
                "pressure is high; defer new optional local heavyweight work until recovery",
                1,
            ),
            "high" => (
                "avoid_optional_parallelism",
                "pressure is high; keep the next local step lightweight and serial",
                1,
            ),
            "critical" if is_remote => (
                "prefer_remote_execution",
                "pressure is critical locally, while remote execution avoids most local load",
                requested_parallelism,
            ),
            "critical" if is_heavy => (
                "request_operator_review_before_heavy_work",
                "pressure is critical; review new local heavyweight work before proceeding",
                1,
            ),
            "critical" => (
                "continue_lightweight_only",
                "pressure is critical; prefer only bounded lightweight local work",
                1,
            ),
            _ => (
                "observe_only",
                "pressure is unknown or unsupported, so scheduling remains caller-directed",
                requested_parallelism,
            ),
        }
    };

    json!({
        "schema_version": BODY_SCHEDULING_ADVICE_SCHEMA_V0,
        "mode": "shadow_only",
        "read_only": true,
        "blocked": false,
        "execution_changed": false,
        "changes_routing": false,
        "changes_parallelism": false,
        "pressure": pressure,
        "workload_class": workload_class,
        "requested_parallelism": requested_parallelism,
        "suggested_max_parallelism": suggested_max_parallelism,
        "recommendation": recommendation,
        "reason": reason,
    })
}

fn disabled_body_status() -> Value {
    json!({
        "schema_version": BODY_STATUS_SCHEMA_V1,
        "compatible_with": [BODY_STATUS_SCHEMA_V0],
        "mode": "shadow_only",
        "enabled": false,
        "status": "disabled",
        "reason": "set AGENT_BRIDGE_BODY_TELEMETRY=1 to enable read-only host sampling",
        "read_only": true,
        "persists_raw_samples": false,
    })
}

/// Terminal state of one task-resource observation span. A span is only
/// `closed` when it has both its before and after observations; otherwise it
/// is `abandoned` rather than fabricating an after-state.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum TaskResourceSpanState {
    Active,
    Closed,
    Abandoned,
}

#[derive(Debug, Clone, PartialEq, Serialize)]
pub struct TaskResourceSpan {
    pub schema_version: String,
    pub span_id: String,
    pub task_kind: String,
    /// Opaque caller-provided reference, such as an agent session ID. Never a
    /// prompt, tool arguments, or transcript.
    pub task_ref: Option<String>,
    pub state: TaskResourceSpanState,
    pub started_at_unix_ms: i64,
    pub ended_at_unix_ms: Option<i64>,
    pub before: Value,
    pub checkpoints: Vec<Value>,
    pub after: Option<Value>,
    pub task_process_before: Option<TaskProcessTreeSample>,
    pub task_process_after: Option<TaskProcessTreeSample>,
    /// Whether a procfs baseline was actually attached or a post-spawn
    /// attempt failed before a safe process scope could be established.
    pub task_process_binding_status: Option<String>,
    pub task_process_binding_reason: Option<String>,
    /// Whether the process baseline was captured at span start or only after
    /// the runtime had successfully spawned its child.
    pub task_process_baseline_phase: Option<String>,
    /// A post-spawn attach cannot account for the short prefix between the
    /// host-body baseline and the child becoming observable.
    pub task_process_whole_task_prefix_covered: bool,
    /// PID-free lifetime aggregates observed immediately before the runtime's
    /// sole child reaper ran. This is independent of procfs endpoint samples.
    pub task_terminal_resources: Option<TaskTerminalResourceUsage>,
    /// PID-free, terminal aggregates for the delegated workload cgroup. The
    /// supervisor is outside this accounting cgroup and does not publish a
    /// receipt until the recursively observed `populated` state reaches zero.
    pub task_workload_resources: Option<TaskWorkloadResourceUsage>,
    #[serde(skip)]
    process_scope: Option<TaskProcessScopeBinding>,
    pub sampling_gaps: u32,
    pub abandonment_reason: Option<String>,
}

/// Bounded, derived receipt suitable for persistent event history. Raw body
/// snapshots remain process-local and are deliberately excluded here.
#[derive(Debug, Clone, PartialEq, Serialize)]
pub struct TaskResourceSpanReceipt {
    pub schema_version: String,
    pub span_id: String,
    pub task_kind: String,
    pub state: TaskResourceSpanState,
    pub started_at_unix_ms: i64,
    pub ended_at_unix_ms: Option<i64>,
    pub duration_ms: Option<i64>,
    pub checkpoint_count: usize,
    pub sampling_gaps: u32,
    pub before_pressure: Option<String>,
    pub after_pressure: Option<String>,
    pub memory_available_delta_bytes: Option<i64>,
    pub storage_available_delta_bytes: Option<i64>,
    pub process_resident_delta_bytes: Option<i64>,
    pub task_process_scope: Option<String>,
    pub task_process_capture_complete: bool,
    pub task_process_count_before: Option<u32>,
    pub task_process_count_after: Option<u32>,
    pub task_process_resident_delta_bytes: Option<i64>,
    pub task_process_sampling_gaps: u32,
    pub task_process_binding_status: Option<String>,
    pub task_process_binding_reason: Option<String>,
    pub task_process_baseline_phase: Option<String>,
    pub task_process_whole_task_prefix_covered: bool,
    pub task_process_terminal_status: Option<String>,
    pub task_process_endpoint_semantics: Option<String>,
    pub task_terminal_resources: Option<TaskTerminalResourceUsage>,
    pub task_workload_resources: Option<TaskWorkloadResourceUsage>,
    pub abandonment_reason: Option<String>,
}

/// Bounded terminal accounting safe for durable receipts. The `known_*`
/// prefix is intentional: when one child generation was missed, these values
/// are a trustworthy subtotal rather than a fabricated session total.
#[derive(Debug, Clone, PartialEq, Eq, Serialize)]
pub struct TaskTerminalResourceUsage {
    pub schema_version: String,
    pub accounting_status: String,
    pub source: String,
    pub scope: String,
    pub descendant_coverage: String,
    pub workload_lifetime_covered: bool,
    pub spawned_attempt_count: u32,
    pub captured_attempt_count: u32,
    pub known_user_cpu_us: Option<u64>,
    pub known_system_cpu_us: Option<u64>,
    pub known_peak_resident_bytes: Option<u64>,
    pub complete_for_spawned_attempts: bool,
    pub complete_for_workload_tree: bool,
    pub terminal_condition: String,
    pub peak_resident_semantics: String,
}

/// Bounded terminal accounting for a delegated local workload tree. Unit
/// names, cgroup paths, PIDs, pidfds, nonces, and control-channel details are
/// deliberately absent from this durable projection.
#[derive(Debug, Clone, PartialEq, Eq, Serialize)]
pub struct TaskWorkloadResourceUsage {
    pub schema_version: String,
    pub accounting_status: String,
    pub source: String,
    pub scope: String,
    pub controllers: Vec<String>,
    pub workload_lifetime_covered: bool,
    pub generation_count: u32,
    pub captured_generation_count: u32,
    pub known_total_cpu_us: Option<u64>,
    pub known_user_cpu_us: Option<u64>,
    pub known_system_cpu_us: Option<u64>,
    pub known_peak_memory_bytes: Option<u64>,
    pub known_peak_pids: Option<u64>,
    pub known_oom_event_count: Option<u64>,
    pub known_oom_kill_count: Option<u64>,
    pub start_before_exec: bool,
    pub final_populated_zero: bool,
    pub complete_for_cpu_memory_workload_tree: bool,
    pub complete_for_pids_workload_tree: bool,
    pub io_accounting_status: String,
    pub terminal_condition: String,
    pub failure_reason: Option<String>,
    pub trust_boundary: String,
}

impl TaskWorkloadResourceUsage {
    /// Redundant durable gate: no single deserialized boolean is sufficient to
    /// turn a task event into Verified whole-tree CPU/memory evidence.
    pub fn proves_complete_cpu_memory_workload_tree(&self) -> bool {
        self.schema_version == TASK_WORKLOAD_RESOURCES_SCHEMA_V0
            && self.accounting_status == "complete"
            && self.source == "linux_cgroup_v2_systemd_delegated_scope"
            && self.scope == "delegated_session_workload_tree"
            && self.workload_lifetime_covered
            && self.generation_count > 0
            && self.captured_generation_count == self.generation_count
            && self.known_total_cpu_us.is_some()
            && self.known_user_cpu_us.is_some()
            && self.known_system_cpu_us.is_some()
            && self.known_peak_memory_bytes.is_some()
            && self.start_before_exec
            && self.final_populated_zero
            && self.complete_for_cpu_memory_workload_tree
            && self.controllers.iter().any(|value| value == "cpu")
            && self.controllers.iter().any(|value| value == "memory")
            && self.io_accounting_status == "unknown_not_delegated"
            && self.trust_boundary == "same_uid_non_adversarial_cgroup_membership"
    }
}

#[derive(Clone, PartialEq, Eq)]
struct TaskProcessScopeBinding {
    root_pid: u32,
    root_start_ticks: u64,
    owner_uid: u32,
}

impl std::fmt::Debug for TaskProcessScopeBinding {
    fn fmt(&self, formatter: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        formatter
            .debug_struct("TaskProcessScopeBinding")
            .field("identity_bound", &true)
            .finish_non_exhaustive()
    }
}

#[derive(Debug, Clone, PartialEq, Serialize)]
pub struct TaskProcessTreeSample {
    pub scope: String,
    pub status: String,
    pub process_count: Option<u32>,
    pub resident_bytes: Option<u64>,
    pub sampling_gaps: u32,
    pub source: String,
}

impl TaskProcessTreeSample {
    fn is_complete(&self) -> bool {
        self.status == "fresh"
            && self.process_count.is_some()
            && self.resident_bytes.is_some()
            && self.sampling_gaps == 0
    }
}

impl TaskResourceSpan {
    fn active(
        span_id: String,
        task_kind: String,
        task_ref: Option<String>,
        before: Value,
        process_scope: Option<TaskProcessScopeBinding>,
        task_process_before: Option<TaskProcessTreeSample>,
    ) -> Self {
        Self {
            schema_version: TASK_RESOURCE_SPAN_SCHEMA_V3.to_string(),
            span_id,
            task_kind,
            task_ref,
            state: TaskResourceSpanState::Active,
            started_at_unix_ms: unix_now_ms(),
            ended_at_unix_ms: None,
            before,
            checkpoints: Vec::new(),
            after: None,
            task_process_before,
            task_process_after: None,
            task_process_binding_status: None,
            task_process_binding_reason: None,
            task_process_baseline_phase: None,
            task_process_whole_task_prefix_covered: false,
            task_terminal_resources: None,
            task_workload_resources: None,
            process_scope,
            sampling_gaps: 0,
            abandonment_reason: None,
        }
    }

    fn finish(mut self, after: Option<Value>, reason: Option<String>) -> Self {
        self.ended_at_unix_ms = Some(unix_now_ms());
        self.after = after;
        self.task_process_after = self
            .after
            .as_ref()
            .and_then(|_| self.process_scope.as_ref().map(sample_task_process_tree));
        self.abandonment_reason = reason;
        self.state = if self.after.is_some() {
            TaskResourceSpanState::Closed
        } else {
            TaskResourceSpanState::Abandoned
        };
        self
    }

    pub fn has_complete_capture(&self) -> bool {
        let Some(after) = self.after.as_ref() else {
            return false;
        };
        let delegated_workload_complete = self
            .task_workload_resources
            .as_ref()
            .is_some_and(|usage| {
                usage.proves_complete_cpu_memory_workload_tree()
                    && self.task_terminal_resources.as_ref().is_some_and(|terminal| {
                        terminal.spawned_attempt_count == usage.generation_count
                    })
            });
        self.state == TaskResourceSpanState::Closed
            && snapshot_is_verified(&self.before)
            && snapshot_is_verified(after)
            && self.before.pointer("/identity/body_id") == after.pointer("/identity/body_id")
            && self.before.pointer("/identity/body_instance_id")
                == after.pointer("/identity/body_instance_id")
            && self.before.pointer("/sample/sequence") != after.pointer("/sample/sequence")
            && (delegated_workload_complete
                || (self.task_workload_resources.is_none()
                    && self
                        .task_terminal_resources
                        .as_ref()
                        .is_none_or(|usage| usage.complete_for_workload_tree)))
            && (delegated_workload_complete
                || self.process_scope.is_none()
                || (self.task_process_whole_task_prefix_covered
                    && self
                    .task_process_before
                    .as_ref()
                    .is_some_and(TaskProcessTreeSample::is_complete)
                    && self
                        .task_process_after
                        .as_ref()
                        .is_some_and(TaskProcessTreeSample::is_complete)))
    }

    /// Produce the only form of a span that may enter durable event history.
    /// It contains lifecycle coverage and derived deltas, never raw samples.
    pub fn receipt(&self) -> TaskResourceSpanReceipt {
        let after = self.after.as_ref();
        TaskResourceSpanReceipt {
            schema_version: self.schema_version.clone(),
            span_id: self.span_id.clone(),
            task_kind: self.task_kind.clone(),
            state: self.state,
            started_at_unix_ms: self.started_at_unix_ms,
            ended_at_unix_ms: self.ended_at_unix_ms,
            duration_ms: self
                .ended_at_unix_ms
                .map(|ended| ended.saturating_sub(self.started_at_unix_ms)),
            checkpoint_count: self.checkpoints.len(),
            sampling_gaps: self.sampling_gaps,
            before_pressure: pressure_label(&self.before),
            after_pressure: after.and_then(pressure_label),
            memory_available_delta_bytes: after.and_then(|after| {
                snapshot_delta(&self.before, after, "/sample/memory/available_bytes/value")
            }),
            storage_available_delta_bytes: after.and_then(|after| {
                snapshot_delta(&self.before, after, "/sample/storage/available_bytes/value")
            }),
            process_resident_delta_bytes: after.and_then(|after| {
                snapshot_delta(&self.before, after, "/sample/process/resident_bytes/value")
            }),
            task_process_scope: self
                .process_scope
                .as_ref()
                .map(|_| "best_effort_linux_same_user_process_tree".into()),
            task_process_capture_complete: self.process_scope.is_some()
                && self
                    .task_process_before
                    .as_ref()
                    .is_some_and(TaskProcessTreeSample::is_complete)
                && self
                    .task_process_after
                    .as_ref()
                    .is_some_and(TaskProcessTreeSample::is_complete),
            task_process_count_before: self
                .task_process_before
                .as_ref()
                .and_then(|sample| sample.process_count),
            task_process_count_after: self
                .task_process_after
                .as_ref()
                .and_then(|sample| sample.process_count),
            task_process_resident_delta_bytes: process_tree_delta(
                self.task_process_before.as_ref(),
                self.task_process_after.as_ref(),
            ),
            task_process_sampling_gaps: self
                .task_process_before
                .as_ref()
                .map_or(0, |sample| sample.sampling_gaps)
                .saturating_add(
                    self.task_process_after
                        .as_ref()
                        .map_or(0, |sample| sample.sampling_gaps),
                ),
            task_process_binding_status: self.task_process_binding_status.clone(),
            task_process_binding_reason: self.task_process_binding_reason.clone(),
            task_process_baseline_phase: self.task_process_baseline_phase.clone(),
            task_process_whole_task_prefix_covered: self.task_process_whole_task_prefix_covered,
            task_process_terminal_status: self
                .task_process_after
                .as_ref()
                .map(|sample| sample.status.clone()),
            task_process_endpoint_semantics: if self.process_scope.is_some() {
                Some(
                    if self.task_process_after.is_some() {
                        "procfs_sample_attempt_at_finish"
                    } else {
                        "not_attempted_without_body_after_observation"
                    }
                    .to_string()
                )
            } else if self.task_process_binding_status.as_deref() == Some("unavailable") {
                Some("post_spawn_baseline_attempt_failed_before_scope_binding".to_string())
            } else {
                None
            },
            task_terminal_resources: self.task_terminal_resources.clone(),
            task_workload_resources: self.task_workload_resources.clone(),
            abandonment_reason: self.abandonment_reason.clone(),
        }
    }
}

fn terminal_resource_usage(
    snapshot: ab_agent::TerminalResourceSnapshot,
) -> TaskTerminalResourceUsage {
    let accounting_status = match snapshot.status() {
        ab_agent::TerminalResourceStatus::Pending => "pending",
        ab_agent::TerminalResourceStatus::Complete => "complete",
        ab_agent::TerminalResourceStatus::Partial => "partial",
        ab_agent::TerminalResourceStatus::Unsupported => "unsupported",
        ab_agent::TerminalResourceStatus::Unavailable => "unavailable",
    };
    let terminal_condition = match snapshot.status() {
        ab_agent::TerminalResourceStatus::Pending => "child_generations_pending",
        ab_agent::TerminalResourceStatus::Complete => "all_spawned_children_observed_before_reap",
        ab_agent::TerminalResourceStatus::Partial => "some_spawned_children_not_observed",
        ab_agent::TerminalResourceStatus::Unsupported => "platform_not_supported",
        ab_agent::TerminalResourceStatus::Unavailable => "wait_observation_unavailable",
    };
    TaskTerminalResourceUsage {
        schema_version: TASK_TERMINAL_RESOURCES_SCHEMA_V0.to_string(),
        accounting_status: accounting_status.to_string(),
        source: snapshot.source().to_string(),
        scope: snapshot.scope().to_string(),
        descendant_coverage: "not_proven".to_string(),
        workload_lifetime_covered: false,
        spawned_attempt_count: snapshot.spawned_attempts(),
        captured_attempt_count: snapshot.observed_attempts(),
        known_user_cpu_us: snapshot.known_user_cpu_micros(),
        known_system_cpu_us: snapshot.known_system_cpu_micros(),
        known_peak_resident_bytes: snapshot.known_max_rss_bytes(),
        complete_for_spawned_attempts: snapshot.complete_for_spawned_attempts(),
        complete_for_workload_tree: snapshot.complete_for_workload_tree(),
        terminal_condition: terminal_condition.to_string(),
        peak_resident_semantics:
            "max_ru_maxrss_across_attempts_not_concurrent_tree_peak".to_string(),
    }
}

fn workload_resource_usage(
    snapshot: ab_agent::WorkloadResourceSnapshot,
) -> TaskWorkloadResourceUsage {
    let accounting_status = match snapshot.status {
        ab_agent::WorkloadResourceStatus::Pending => "pending",
        ab_agent::WorkloadResourceStatus::Complete => "complete",
        ab_agent::WorkloadResourceStatus::Partial => "partial",
        ab_agent::WorkloadResourceStatus::Unavailable => "unavailable",
        ab_agent::WorkloadResourceStatus::Unsupported => "unsupported",
    };
    let terminal_condition = match snapshot.status {
        ab_agent::WorkloadResourceStatus::Pending => "workload_generations_pending",
        ab_agent::WorkloadResourceStatus::Complete => "all_generations_populated_zero",
        ab_agent::WorkloadResourceStatus::Partial => "one_or_more_generation_receipts_incomplete",
        ab_agent::WorkloadResourceStatus::Unavailable => "terminal_cgroup_receipt_unavailable",
        ab_agent::WorkloadResourceStatus::Unsupported => "delegated_cgroup_custody_not_active",
    };
    let failure_reason = (!snapshot.incomplete_reasons.is_empty())
        .then(|| snapshot.incomplete_reasons.join("; "));
    TaskWorkloadResourceUsage {
        schema_version: TASK_WORKLOAD_RESOURCES_SCHEMA_V0.to_string(),
        accounting_status: accounting_status.to_string(),
        source: snapshot
            .source
            .unwrap_or_else(|| "unsupported_or_unprepared_platform".to_string()),
        scope: snapshot
            .scope
            .unwrap_or_else(|| "no_delegated_workload_scope".to_string()),
        controllers: snapshot.controllers,
        workload_lifetime_covered: snapshot.populated_zero_observed,
        generation_count: snapshot.generation_count,
        captured_generation_count: snapshot.captured_generation_count,
        known_total_cpu_us: snapshot.cpu_usage_usec,
        known_user_cpu_us: snapshot.cpu_user_usec,
        known_system_cpu_us: snapshot.cpu_system_usec,
        known_peak_memory_bytes: snapshot.memory_peak_bytes,
        known_peak_pids: snapshot.pids_peak,
        known_oom_event_count: snapshot.oom_events,
        known_oom_kill_count: snapshot.oom_kill_events,
        start_before_exec: snapshot.start_before_exec,
        final_populated_zero: snapshot.populated_zero_observed,
        complete_for_cpu_memory_workload_tree: snapshot
            .complete_for_cpu_memory_workload_tree,
        complete_for_pids_workload_tree: snapshot.complete_for_pids_workload_tree,
        io_accounting_status: "unknown_not_delegated".to_string(),
        terminal_condition: terminal_condition.to_string(),
        failure_reason,
        trust_boundary: "same_uid_non_adversarial_cgroup_membership".to_string(),
    }
}

fn refresh_task_custody_resources(
    span: &mut TaskResourceSpan,
    custody: &ab_agent::SpawnedProcessCustody,
) {
    span.task_terminal_resources = Some(terminal_resource_usage(custody.terminal_resources()));
    span.task_workload_resources = Some(workload_resource_usage(custody.workload_resources()));
}

fn process_tree_delta(
    before: Option<&TaskProcessTreeSample>,
    after: Option<&TaskProcessTreeSample>,
) -> Option<i64> {
    let before = before?.resident_bytes?;
    let after = after?.resident_bytes?;
    i64::try_from(i128::from(after) - i128::from(before)).ok()
}

#[cfg(target_os = "linux")]
fn bind_task_process_tree(root_pid: u32) -> Result<TaskProcessScopeBinding, String> {
    linux::bind_process_tree(root_pid)
}

#[cfg(target_os = "linux")]
fn bind_task_process_tree_expected(
    root_pid: u32,
    expected_start_ticks: u64,
) -> Result<TaskProcessScopeBinding, String> {
    linux::bind_process_tree_expected(root_pid, expected_start_ticks)
}

#[cfg(not(target_os = "linux"))]
fn bind_task_process_tree(_root_pid: u32) -> Result<TaskProcessScopeBinding, String> {
    Err("process-tree task scope is only supported on Linux".into())
}

#[cfg(not(target_os = "linux"))]
fn bind_task_process_tree_expected(
    _root_pid: u32,
    _expected_start_ticks: u64,
) -> Result<TaskProcessScopeBinding, String> {
    Err("process-tree task scope is only supported on Linux".into())
}

#[cfg(target_os = "linux")]
fn sample_task_process_tree(binding: &TaskProcessScopeBinding) -> TaskProcessTreeSample {
    linux::sample_process_tree(binding)
}

#[cfg(not(target_os = "linux"))]
fn sample_task_process_tree(_binding: &TaskProcessScopeBinding) -> TaskProcessTreeSample {
    TaskProcessTreeSample {
        scope: "process_tree".into(),
        status: "unsupported".into(),
        process_count: None,
        resident_bytes: None,
        sampling_gaps: 0,
        source: "unsupported_platform".into(),
    }
}

fn pressure_label(snapshot: &Value) -> Option<String> {
    snapshot
        .pointer("/pressure")
        .and_then(Value::as_str)
        .map(str::to_owned)
}

fn snapshot_delta(before: &Value, after: &Value, pointer: &str) -> Option<i64> {
    let before = before.pointer(pointer)?.as_u64()?;
    let after = after.pointer(pointer)?.as_u64()?;
    let delta = i128::from(after) - i128::from(before);
    i64::try_from(delta).ok()
}

#[derive(Debug, Default)]
struct TaskResourceSpanTracker {
    active: BTreeMap<String, TaskResourceSpan>,
    /// Runtime-minted, non-serializable handles. They are held only until the
    /// corresponding span terminalizes, then projected into the PID-free
    /// aggregate stored on the span.
    terminal_resource_handles: BTreeMap<String, ab_agent::SpawnedProcessCustody>,
    session_spans: BTreeMap<String, String>,
    /// Terminal receipts completed by the background session observer and not
    /// yet collected by `agent_session_wait`.
    terminal_session_spans: BTreeMap<String, TaskResourceSpan>,
}

const TASK_SPAN_CHECKPOINT_CAP: usize = 8;
const TASK_SPAN_ACTIVE_CAP: usize = 128;
const TASK_SPAN_TERMINAL_CACHE_CAP: usize = 128;
static TASK_SPANS: OnceLock<Mutex<TaskResourceSpanTracker>> = OnceLock::new();

/// Start a task span from one grounded before-observation. Starting is refused
/// when telemetry is disabled or unavailable; callers cannot create a span
/// whose start state is merely inferred.
pub fn start_task_resource_span(
    span_id: String,
    task_kind: String,
    task_ref: Option<String>,
) -> std::result::Result<TaskResourceSpan, String> {
    start_task_resource_span_scoped(span_id, task_kind, task_ref, None)
}

/// Start a span with an optional explicit same-user process-tree scope. The
/// PID is used only to establish a start-time/uid-bound procfs identity; no
/// command line, environment, file descriptor, or content is collected.
pub fn start_task_resource_span_scoped(
    span_id: String,
    task_kind: String,
    task_ref: Option<String>,
    root_pid: Option<u32>,
) -> std::result::Result<TaskResourceSpan, String> {
    let before = live_body_snapshot().ok_or_else(|| {
        "body telemetry is not live; set AGENT_BRIDGE_BODY_TELEMETRY=1 on a supported host"
            .to_string()
    })?;
    let process_scope = root_pid.map(bind_task_process_tree).transpose()?;
    let task_process_before = process_scope.as_ref().map(sample_task_process_tree);
    if task_process_before
        .as_ref()
        .is_some_and(|sample| !sample.is_complete())
    {
        return Err("initial process-tree sample is incomplete".into());
    }
    let tracker = TASK_SPANS.get_or_init(|| Mutex::new(TaskResourceSpanTracker::default()));
    let mut tracker = tracker
        .lock()
        .map_err(|_| "body task-span tracker mutex poisoned".to_string())?;
    if tracker.active.contains_key(&span_id) {
        return Err(format!("task span '{span_id}' is already active"));
    }
    if tracker.active.len() >= TASK_SPAN_ACTIVE_CAP {
        return Err(format!(
            "active task span capacity {TASK_SPAN_ACTIVE_CAP} reached"
        ));
    }
    let mut span = TaskResourceSpan::active(
        span_id.clone(),
        task_kind,
        task_ref,
        before,
        process_scope,
        task_process_before,
    );
    if span.process_scope.is_some() {
        span.task_process_binding_status = Some("attached".to_string());
        span.task_process_baseline_phase = Some("span_start".to_string());
        span.task_process_whole_task_prefix_covered = true;
    }
    tracker.active.insert(span_id, span.clone());
    Ok(span)
}

/// Attach a runtime-minted process identity to an already-active body span.
///
/// This is intentionally stricter than accepting a PID: the Linux procfs
/// birth token captured at the actual spawn point must still match, and the
/// root must belong to the bridge's effective uid. The first process sample is
/// therefore a trustworthy post-spawn baseline, not a claim that the short
/// pre-attach prefix was observed.
pub fn attach_task_resource_span_process_tree(
    span_id: &str,
    root_pid: u32,
    expected_start_ticks: u64,
) -> std::result::Result<TaskResourceSpan, String> {
    let tracker = TASK_SPANS.get_or_init(|| Mutex::new(TaskResourceSpanTracker::default()));
    {
        let tracker = tracker
            .lock()
            .map_err(|_| "body task-span tracker mutex poisoned".to_string())?;
        let span = tracker
            .active
            .get(span_id)
            .ok_or_else(|| format!("unknown active task span '{span_id}'"))?;
        if let Some(existing) = &span.process_scope {
            if existing.root_pid == root_pid && existing.root_start_ticks == expected_start_ticks {
                return Ok(span.clone());
            }
            return Err(format!(
                "task span '{span_id}' is already attached to another process identity"
            ));
        }
    }

    let binding = bind_task_process_tree_expected(root_pid, expected_start_ticks)?;
    let baseline = sample_task_process_tree(&binding);
    if !baseline.is_complete() {
        return Err(format!(
            "post-spawn process-tree baseline is incomplete: {}",
            baseline.status
        ));
    }

    let mut tracker = tracker
        .lock()
        .map_err(|_| "body task-span tracker mutex poisoned".to_string())?;
    let span = tracker
        .active
        .get_mut(span_id)
        .ok_or_else(|| format!("unknown active task span '{span_id}'"))?;
    if let Some(existing) = &span.process_scope {
        if existing == &binding {
            return Ok(span.clone());
        }
        return Err(format!(
            "task span '{span_id}' was concurrently attached to another process identity"
        ));
    }
    span.process_scope = Some(binding);
    span.task_process_before = Some(baseline);
    span.task_process_binding_status = Some("attached".to_string());
    span.task_process_binding_reason = None;
    span.task_process_baseline_phase = Some("post_spawn".to_string());
    span.task_process_whole_task_prefix_covered = false;
    Ok(span.clone())
}

/// Persist a normalized, PID-free reason when the runtime supplied custody
/// but procfs could not establish a trustworthy post-spawn baseline.
pub fn mark_task_resource_span_process_binding_unavailable(
    span_id: &str,
) -> std::result::Result<TaskResourceSpan, String> {
    let tracker = TASK_SPANS.get_or_init(|| Mutex::new(TaskResourceSpanTracker::default()));
    let mut tracker = tracker
        .lock()
        .map_err(|_| "body task-span tracker mutex poisoned".to_string())?;
    let span = tracker
        .active
        .get_mut(span_id)
        .ok_or_else(|| format!("unknown active task span '{span_id}'"))?;
    if span.process_scope.is_some() {
        return Err(format!(
            "task span '{span_id}' already has an attached process scope"
        ));
    }
    span.task_process_binding_status = Some("unavailable".to_string());
    span.task_process_binding_reason =
        Some("post_spawn_procfs_baseline_unavailable".to_string());
    Ok(span.clone())
}

/// Attach the runtime's private terminal-accounting handle independently of
/// procfs endpoint sampling. A child may exit too quickly for a post-spawn
/// `/proc` baseline while its waitable rusage remains available to the sole
/// runtime reaper.
pub fn attach_task_resource_span_process_custody(
    span_id: &str,
    custody: ab_agent::SpawnedProcessCustody,
) -> std::result::Result<TaskResourceSpan, String> {
    if !custody.is_local_workload_root() {
        return Err("terminal accounting custody is not a local workload root".to_string());
    }
    let tracker = TASK_SPANS.get_or_init(|| Mutex::new(TaskResourceSpanTracker::default()));
    let mut tracker = tracker
        .lock()
        .map_err(|_| "body task-span tracker mutex poisoned".to_string())?;
    if let Some(existing) = tracker.terminal_resource_handles.get(span_id) {
        if existing.pid() != custody.pid()
            || existing.start_ticks() != custody.start_ticks()
            || existing.scope() != custody.scope()
        {
            return Err(format!(
                "task span '{span_id}' is already attached to another terminal accounting handle"
            ));
        }
        return tracker
            .active
            .get(span_id)
            .cloned()
            .ok_or_else(|| format!("unknown active task span '{span_id}'"));
    }
    let span = tracker
        .active
        .get_mut(span_id)
        .ok_or_else(|| format!("unknown active task span '{span_id}'"))?;
    refresh_task_custody_resources(span, &custody);
    let result = span.clone();
    tracker
        .terminal_resource_handles
        .insert(span_id.to_string(), custody);
    Ok(result)
}

/// Capture an in-flight checkpoint. A failed capture becomes an explicit gap;
/// it never duplicates the last good sample or alters the active span state.
pub fn checkpoint_task_resource_span(
    span_id: &str,
) -> std::result::Result<TaskResourceSpan, String> {
    let tracker = TASK_SPANS.get_or_init(|| Mutex::new(TaskResourceSpanTracker::default()));
    let mut tracker = tracker
        .lock()
        .map_err(|_| "body task-span tracker mutex poisoned".to_string())?;
    let span = tracker
        .active
        .get_mut(span_id)
        .ok_or_else(|| format!("unknown active task span '{span_id}'"))?;
    match live_body_snapshot() {
        Some(snapshot) => {
            if span.checkpoints.len() == TASK_SPAN_CHECKPOINT_CAP {
                span.checkpoints.remove(0);
            }
            span.checkpoints.push(snapshot);
        }
        None => span.sampling_gaps = span.sampling_gaps.saturating_add(1),
    }
    Ok(span.clone())
}

/// End a task span. If the final observation cannot be captured, the returned
/// span is abandoned and `after` remains absent.
pub fn finish_task_resource_span(span_id: &str) -> std::result::Result<TaskResourceSpan, String> {
    let tracker = TASK_SPANS.get_or_init(|| Mutex::new(TaskResourceSpanTracker::default()));
    let mut tracker = tracker
        .lock()
        .map_err(|_| "body task-span tracker mutex poisoned".to_string())?;
    finish_active_task_resource_span(&mut tracker, span_id)
}

fn finish_active_task_resource_span(
    tracker: &mut TaskResourceSpanTracker,
    span_id: &str,
) -> std::result::Result<TaskResourceSpan, String> {
    let mut span = tracker
        .active
        .remove(span_id)
        .ok_or_else(|| format!("unknown active task span '{span_id}'"))?;
    if let Some(custody) = tracker.terminal_resource_handles.remove(span_id) {
        refresh_task_custody_resources(&mut span, &custody);
    }
    tracker.session_spans.retain(|_, id| id != span_id);
    let after = live_body_snapshot();
    let reason = after
        .is_none()
        .then(|| "after_observation_unavailable".to_string());
    Ok(span.finish(after, reason))
}

/// Associate an agent session with an already-started body span. One-shot and
/// interactive runtimes both outlive `spawn()`, so terminalization is driven
/// by the stored session lifecycle. The id is opaque and contains no content.
pub fn bind_task_resource_span_to_session(
    session_id: String,
    span_id: String,
) -> std::result::Result<(), String> {
    let tracker = TASK_SPANS.get_or_init(|| Mutex::new(TaskResourceSpanTracker::default()));
    let mut tracker = tracker
        .lock()
        .map_err(|_| "body task-span tracker mutex poisoned".to_string())?;
    if !tracker.active.contains_key(&span_id) {
        return Err(format!("unknown active task span '{span_id}'"));
    }
    if let Some(existing) = tracker.session_spans.get(&session_id) {
        if existing != &span_id {
            return Err(format!(
                "session '{session_id}' is already bound to another task span"
            ));
        }
        return Ok(());
    }
    tracker.session_spans.insert(session_id, span_id);
    Ok(())
}

/// Automatically finish an agent session's active span and retain one bounded
/// terminal receipt for a later `agent_session_wait`. Returning `Some` claims
/// responsibility for recording the terminal event; repeated observers get
/// `None` and cannot duplicate it.
pub fn complete_task_resource_span_for_session(
    session_id: &str,
) -> std::result::Result<Option<TaskResourceSpan>, String> {
    let tracker = TASK_SPANS.get_or_init(|| Mutex::new(TaskResourceSpanTracker::default()));
    let mut tracker = tracker
        .lock()
        .map_err(|_| "body task-span tracker mutex poisoned".to_string())?;
    if tracker.terminal_session_spans.contains_key(session_id) {
        return Ok(None);
    }
    let Some(span_id) = tracker.session_spans.remove(session_id) else {
        return Ok(None);
    };
    let span = finish_active_task_resource_span(&mut tracker, &span_id)?;
    cache_terminal_session_span(&mut tracker, session_id, span.clone());
    Ok(Some(span))
}

fn cache_terminal_session_span(
    tracker: &mut TaskResourceSpanTracker,
    session_id: &str,
    span: TaskResourceSpan,
) {
    if tracker.terminal_session_spans.len() >= TASK_SPAN_TERMINAL_CACHE_CAP {
        let oldest = tracker
            .terminal_session_spans
            .iter()
            .min_by_key(|(_, span)| span.ended_at_unix_ms.unwrap_or(i64::MAX))
            .map(|(session_id, _)| session_id.clone());
        if let Some(oldest) = oldest {
            tracker.terminal_session_spans.remove(&oldest);
        }
    }
    tracker
        .terminal_session_spans
        .insert(session_id.to_string(), span);
}

/// Abandon and cache a session span after the bounded observer lifetime. This
/// frees active capacity without inventing a terminal observation.
pub fn abandon_task_resource_span_for_session(
    session_id: &str,
    reason: String,
) -> std::result::Result<Option<TaskResourceSpan>, String> {
    let tracker = TASK_SPANS.get_or_init(|| Mutex::new(TaskResourceSpanTracker::default()));
    let mut tracker = tracker
        .lock()
        .map_err(|_| "body task-span tracker mutex poisoned".to_string())?;
    if tracker.terminal_session_spans.contains_key(session_id) {
        return Ok(None);
    }
    let Some(span_id) = tracker.session_spans.remove(session_id) else {
        return Ok(None);
    };
    let mut span = tracker
        .active
        .remove(&span_id)
        .ok_or_else(|| format!("unknown active task span '{span_id}'"))?;
    if let Some(custody) = tracker.terminal_resource_handles.remove(&span_id) {
        refresh_task_custody_resources(&mut span, &custody);
    }
    let span = span.finish(None, Some(reason));
    tracker.session_spans.retain(|_, id| id != &span_id);
    cache_terminal_session_span(&mut tracker, session_id, span.clone());
    Ok(Some(span))
}

/// Collect the terminal span bound to an agent session. The boolean is true
/// only when this call performed the finish itself and must record the event;
/// a cached span was already recorded by the background observer.
pub fn finish_task_resource_span_for_session(
    session_id: &str,
) -> std::result::Result<Option<(TaskResourceSpan, bool)>, String> {
    let tracker = TASK_SPANS.get_or_init(|| Mutex::new(TaskResourceSpanTracker::default()));
    let mut tracker = tracker
        .lock()
        .map_err(|_| "body task-span tracker mutex poisoned".to_string())?;
    if let Some(span) = tracker.terminal_session_spans.remove(session_id) {
        return Ok(Some((span, false)));
    }
    let Some(span_id) = tracker.session_spans.remove(session_id) else {
        return Ok(None);
    };
    finish_active_task_resource_span(&mut tracker, &span_id)
        .map(|span| Some((span, true)))
}

/// Explicitly abandon a task span, e.g. when a child is lost during a daemon
/// restart. This preserves the before state but guarantees no fabricated after.
pub fn abandon_task_resource_span(
    span_id: &str,
    reason: String,
) -> std::result::Result<TaskResourceSpan, String> {
    let tracker = TASK_SPANS.get_or_init(|| Mutex::new(TaskResourceSpanTracker::default()));
    let mut tracker = tracker
        .lock()
        .map_err(|_| "body task-span tracker mutex poisoned".to_string())?;
    let mut span = tracker
        .active
        .remove(span_id)
        .ok_or_else(|| format!("unknown active task span '{span_id}'"))?;
    if let Some(custody) = tracker.terminal_resource_handles.remove(span_id) {
        refresh_task_custody_resources(&mut span, &custody);
    }
    tracker.session_spans.retain(|_, id| id != span_id);
    Ok(span.finish(None, Some(reason)))
}

fn live_body_snapshot() -> Option<Value> {
    let snapshot = body_status_snapshot();
    (matches!(
        snapshot.get("status").and_then(Value::as_str),
        Some("ok" | "partial")
    ) && snapshot
        .pointer("/freshness/status")
        .and_then(Value::as_str)
        == Some("fresh"))
    .then_some(snapshot)
}

fn snapshot_is_verified(snapshot: &Value) -> bool {
    snapshot.get("status").and_then(Value::as_str) == Some("ok")
        && snapshot
            .pointer("/freshness/status")
            .and_then(Value::as_str)
            == Some("fresh")
        && snapshot
            .pointer("/coverage/required_ratio")
            .and_then(Value::as_f64)
            == Some(1.0)
}

fn unix_now_ms() -> i64 {
    SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map(|duration| duration.as_millis().try_into().unwrap_or(i64::MAX))
        .unwrap_or(0)
}

fn finite_ratio(value: f64) -> Option<f64> {
    (value.is_finite() && (0.0..=1.0).contains(&value)).then_some(value)
}

fn used_ratio(total: &MetricValue<u64>, available: &MetricValue<u64>) -> Option<f64> {
    let total = *total.live()?;
    let available = *available.live()?;
    if total == 0 || available > total {
        return None;
    }
    Some(1.0 - (available as f64 / total as f64))
}

#[cfg(test)]
mod tests {
    use super::*;

    fn sample(sequence: u64, cpu: Option<f64>, memory_free: Option<u64>) -> BodySample {
        let ratio_metric = |value: Option<f64>| match value {
            Some(value) => MetricValue::fresh(value, "fake"),
            None => MetricValue::unavailable(MetricStatus::Unknown, "fake"),
        };
        let bytes_metric = |value: Option<u64>| match value {
            Some(value) => MetricValue::fresh(value, "fake"),
            None => MetricValue::unavailable(MetricStatus::Unknown, "fake"),
        };
        BodySample {
            sequence,
            observed_at_mono_ms: sequence * 1_000,
            observed_at_unix_ms: sequence as i64 * 1_000,
            cpu_utilization_ratio: ratio_metric(cpu),
            memory: MemorySample {
                architecture: MemoryArchitecture::Unified,
                total_bytes: bytes_metric(Some(100)),
                available_bytes: bytes_metric(memory_free),
                swap_total_bytes: bytes_metric(Some(0)),
                swap_available_bytes: bytes_metric(Some(0)),
                vram_total_bytes: MetricValue::unavailable(
                    MetricStatus::NotApplicable,
                    "unified_memory",
                ),
            },
            storage: StorageSample {
                total_bytes: bytes_metric(Some(100)),
                available_bytes: bytes_metric(Some(80)),
                critical_mounts: vec![StorageMountSample {
                    path: "/".to_string(),
                    total_bytes: bytes_metric(Some(100)),
                    available_bytes: bytes_metric(Some(80)),
                }],
            },
            process: ProcessFootprint {
                resident_bytes: bytes_metric(Some(10)),
                scope: "collector_process".to_string(),
            },
            kernel_pressure: KernelPressureSample::unsupported("fake"),
        }
    }

    #[test]
    fn unavailable_metrics_never_expose_a_last_known_value() {
        let metric = MetricValue::<u64>::unavailable(MetricStatus::Stale, "test");
        assert_eq!(metric.live(), None);
        assert_eq!(metric.value, None);
        assert!(!metric.status.is_live());
    }

    #[test]
    fn unified_memory_marks_vram_not_applicable() {
        let sample = sample(1, Some(0.2), Some(80));
        assert_eq!(sample.memory.architecture, MemoryArchitecture::Unified);
        assert_eq!(
            sample.memory.vram_total_bytes.status,
            MetricStatus::NotApplicable
        );
        assert_eq!(sample.memory.vram_total_bytes.live(), None);
    }

    #[test]
    fn history_is_bounded_and_keeps_newest_samples() {
        let mut history = SampleHistory::new(2);
        history.push(sample(1, Some(0.1), Some(90)));
        history.push(sample(2, Some(0.2), Some(80)));
        history.push(sample(3, Some(0.3), Some(70)));
        assert_eq!(history.len(), 2);
        assert_eq!(
            history.iter().map(|s| s.sequence).collect::<Vec<_>>(),
            vec![2, 3]
        );
    }

    #[test]
    fn zero_capacity_still_retains_the_current_sample() {
        let mut history = SampleHistory::new(0);
        history.push(sample(1, Some(0.1), Some(90)));
        history.push(sample(2, Some(0.2), Some(80)));
        assert_eq!(history.len(), 1);
        assert_eq!(history.latest().map(|s| s.sequence), Some(2));
    }

    #[test]
    fn reducer_requires_consecutive_rise_and_hysteretic_recovery() {
        let mut reducer = PressureReducer::new(PressurePolicy::default());
        assert_eq!(
            reducer.update(PressureInput {
                cpu_ratio: Some(0.10),
                memory_ratio: None,
                storage_ratio: None,
                ..PressureInput::default()
            }),
            PressureLevel::Nominal
        );
        assert_eq!(
            reducer.update(PressureInput {
                cpu_ratio: Some(0.90),
                memory_ratio: None,
                storage_ratio: None,
                ..PressureInput::default()
            }),
            PressureLevel::Nominal
        );
        assert_eq!(
            reducer.update(PressureInput {
                cpu_ratio: Some(0.90),
                memory_ratio: None,
                storage_ratio: None,
                ..PressureInput::default()
            }),
            PressureLevel::High
        );
        // 0.82 is below high_at but within its recovery margin, so it remains high.
        assert_eq!(
            reducer.update(PressureInput {
                cpu_ratio: Some(0.82),
                memory_ratio: None,
                storage_ratio: None,
                ..PressureInput::default()
            }),
            PressureLevel::High
        );
        // Sustained 0.70 has cleared high recovery, but needs three samples to recover.
        assert_eq!(
            reducer.update(PressureInput {
                cpu_ratio: Some(0.70),
                memory_ratio: None,
                storage_ratio: None,
                ..PressureInput::default()
            }),
            PressureLevel::High
        );
        assert_eq!(
            reducer.update(PressureInput {
                cpu_ratio: Some(0.70),
                memory_ratio: None,
                storage_ratio: None,
                ..PressureInput::default()
            }),
            PressureLevel::High
        );
        assert_eq!(
            reducer.update(PressureInput {
                cpu_ratio: Some(0.70),
                memory_ratio: None,
                storage_ratio: None,
                ..PressureInput::default()
            }),
            PressureLevel::Elevated
        );
    }

    #[test]
    fn invalid_or_missing_ratios_fail_closed_to_unknown() {
        let mut reducer = PressureReducer::new(PressurePolicy::default());
        assert_eq!(
            reducer.update(PressureInput {
                cpu_ratio: Some(f64::NAN),
                memory_ratio: Some(-0.1),
                storage_ratio: Some(1.1),
                ..PressureInput::default()
            }),
            PressureLevel::Unknown
        );
        assert_eq!(
            reducer.update(PressureInput {
                cpu_ratio: None,
                memory_ratio: None,
                storage_ratio: None,
                ..PressureInput::default()
            }),
            PressureLevel::Unknown
        );
    }

    #[test]
    fn impossible_memory_counter_pair_is_not_used_for_pressure() {
        let mut broken = sample(1, None, Some(200));
        broken.memory.total_bytes = MetricValue::fresh(100, "fake");
        let input = PressureInput::from_sample(&broken);
        assert_eq!(input.memory_ratio, None);
        assert_eq!(
            PressureReducer::new(PressurePolicy::default()).update(input),
            PressureLevel::Nominal
        );
    }

    #[test]
    fn coverage_never_calls_an_all_unknown_sample_ok() {
        let coverage = sample_coverage(&BodySample::unknown(1, 1, 1));
        assert_eq!(coverage.status, "unavailable");
        assert_eq!(coverage.required_ratio, 0.0);
    }

    #[test]
    fn verified_span_requires_fresh_full_distinct_samples_from_one_body_epoch() {
        let snapshot = |sequence| {
            json!({
                "status": "ok",
                "freshness": {"status":"fresh"},
                "coverage": {"required_ratio":1.0},
                "identity": {"body_id":"body-test", "body_instance_id":"body-test@boot"},
                "sample": {"sequence":sequence}
            })
        };
        let reused =
            TaskResourceSpan::active("a".into(), "test".into(), None, snapshot(1), None, None)
                .finish(Some(snapshot(1)), None);
        assert!(!reused.has_complete_capture());
        let distinct =
            TaskResourceSpan::active("b".into(), "test".into(), None, snapshot(1), None, None)
                .finish(Some(snapshot(2)), None);
        assert!(distinct.has_complete_capture());
        let partial =
            TaskResourceSpan::active("c".into(), "test".into(), None, snapshot(1), None, None)
                .finish(
                    Some(json!({
                        "status":"partial", "freshness":{"status":"fresh"},
                        "coverage":{"required_ratio":0.8},
                        "identity":{"body_id":"body-test", "body_instance_id":"body-test@boot"},
                        "sample":{"sequence":2}
                    })),
                    None,
                );
        assert!(!partial.has_complete_capture());
    }

    #[test]
    fn fake_adapter_does_not_repeat_exhausted_samples() {
        let mut adapter = FakeBodySensorAdapter::new("fake", [sample(7, Some(0.3), Some(70))]);
        assert_eq!(adapter.sample(1, 1).sequence, 7);
        let exhausted = adapter.sample(2, 2);
        assert_eq!(exhausted.sequence, 8);
        assert_eq!(
            exhausted.cpu_utilization_ratio.status,
            MetricStatus::Unknown
        );
    }

    #[test]
    fn core_retains_pressure_and_history_together() {
        let mut core = BodyTelemetryCore::new(2, PressurePolicy::default());
        assert_eq!(
            core.ingest(sample(1, Some(0.2), Some(80))),
            PressureLevel::Nominal
        );
        assert_eq!(core.pressure(), PressureLevel::Nominal);
        assert_eq!(core.history().latest().map(|s| s.sequence), Some(1));
    }

    #[test]
    fn disabled_projection_has_no_live_sample() {
        let value = disabled_body_status();
        assert_eq!(value["schema_version"], BODY_STATUS_SCHEMA_V1);
        assert_eq!(value["status"], "disabled");
        assert_eq!(value["enabled"], false);
        assert!(value.get("sample").is_none());
    }

    #[test]
    fn shadow_reflex_is_advisory_and_fails_closed_without_pressure() {
        let disabled = shadow_reflex_advice_from_status(&disabled_body_status());
        assert_eq!(disabled["mode"], "advisory_only");
        assert_eq!(disabled["recommendation"], "observe_only");
        assert_eq!(disabled["executes_actions"], false);

        let critical = shadow_reflex_advice_from_status(&json!({
            "enabled": true,
            "pressure": "critical",
        }));
        assert_eq!(
            critical["recommendation"],
            "request_operator_review_before_heavy_work"
        );
        assert_eq!(critical["safety"]["does_not_pause_tasks"], true);
        assert_eq!(
            critical["safety"]["operator_confirmation_required_for_execution"],
            true
        );
    }

    #[test]
    fn scheduling_advice_is_workload_aware_but_never_changes_execution() {
        let critical = json!({
            "enabled": true,
            "pressure": "critical",
        });
        let local = body_scheduling_advice_from_status(&critical, "heavy", 4);
        assert_eq!(local["schema_version"], BODY_SCHEDULING_ADVICE_SCHEMA_V0);
        assert_eq!(
            local["recommendation"],
            "request_operator_review_before_heavy_work"
        );
        assert_eq!(local["suggested_max_parallelism"], 1);
        assert_eq!(local["blocked"], false);
        assert_eq!(local["execution_changed"], false);
        assert_eq!(local["changes_routing"], false);
        assert_eq!(local["changes_parallelism"], false);

        let remote = body_scheduling_advice_from_status(&critical, "remote_heavy", 4);
        assert_eq!(remote["recommendation"], "prefer_remote_execution");
        assert_eq!(remote["suggested_max_parallelism"], 4);
        assert_eq!(remote["blocked"], false);
        assert_eq!(remote["execution_changed"], false);
    }

    #[test]
    fn scheduling_advice_normalizes_unknown_workloads_and_disabled_telemetry() {
        let advice = body_scheduling_advice_from_status(&disabled_body_status(), "surprise", 0);
        assert_eq!(advice["workload_class"], "standard");
        assert_eq!(advice["requested_parallelism"], 1);
        assert_eq!(advice["recommendation"], "observe_only");
        assert_eq!(advice["blocked"], false);
        assert_eq!(advice["execution_changed"], false);
    }

    #[test]
    fn persistent_receipt_excludes_raw_snapshots() {
        let before = json!({
            "pressure": "nominal",
            "sample": {
                "memory": { "available_bytes": { "value": 80 } },
                "storage": { "available_bytes": { "value": 70 } },
                "process": { "resident_bytes": { "value": 10 } },
            },
        });
        let after = json!({
            "pressure": "elevated",
            "sample": {
                "memory": { "available_bytes": { "value": 60 } },
                "storage": { "available_bytes": { "value": 65 } },
                "process": { "resident_bytes": { "value": 15 } },
            },
        });
        let span = TaskResourceSpan::active(
            "span-1".to_string(),
            "test".to_string(),
            Some("opaque-ref".to_string()),
            before,
            None,
            None,
        )
        .finish(Some(after), None);

        let value = serde_json::to_value(span.receipt()).expect("receipt serializes");
        assert!(value.get("before").is_none());
        assert!(value.get("checkpoints").is_none());
        assert!(value.get("after").is_none());
        assert!(value.get("task_ref").is_none());
        assert_eq!(value["memory_available_delta_bytes"], -20);
        assert_eq!(value["storage_available_delta_bytes"], -5);
        assert_eq!(value["process_resident_delta_bytes"], 5);
    }

    #[test]
    fn scoped_receipt_excludes_root_pid_and_keeps_only_aggregate_deltas() {
        let body = |sequence| {
            json!({
                "status":"ok", "freshness":{"status":"fresh"},
                "coverage":{"required_ratio":1.0},
                "identity":{"body_id":"body-test", "body_instance_id":"body-test@boot"},
                "sample":{"sequence":sequence}
            })
        };
        let tree = |resident_bytes| TaskProcessTreeSample {
            scope: "same_user_process_tree".into(),
            status: "fresh".into(),
            process_count: Some(2),
            resident_bytes: Some(resident_bytes),
            sampling_gaps: 0,
            source: "test".into(),
        };
        let mut span = TaskResourceSpan::active(
            "scoped".into(),
            "test".into(),
            None,
            body(1),
            Some(TaskProcessScopeBinding {
                root_pid: 4_242,
                root_start_ticks: 99,
                owner_uid: 1_000,
            }),
            Some(tree(100)),
        );
        span.after = Some(body(2));
        span.task_process_after = Some(tree(140));
        span.task_process_whole_task_prefix_covered = true;
        span.state = TaskResourceSpanState::Closed;
        assert!(span.has_complete_capture());
        let receipt = serde_json::to_value(span.receipt()).expect("receipt serializes");
        assert_eq!(receipt["task_process_resident_delta_bytes"], 40);
        assert_eq!(receipt["task_process_capture_complete"], true);
        assert!(!receipt.to_string().contains("4242"));
        assert!(receipt.get("task_process_before").is_none());
    }

    #[test]
    fn post_spawn_baseline_never_claims_whole_task_even_with_fresh_endpoints() {
        let body = |sequence| {
            json!({
                "status":"ok", "freshness":{"status":"fresh"},
                "coverage":{"required_ratio":1.0},
                "identity":{"body_id":"body-test", "body_instance_id":"body-test@boot"},
                "sample":{"sequence":sequence}
            })
        };
        let mut span = TaskResourceSpan::active(
            "post-spawn".into(),
            "agent_spawn".into(),
            None,
            body(1),
            Some(TaskProcessScopeBinding {
                root_pid: 7_777,
                root_start_ticks: 123,
                owner_uid: 1_000,
            }),
            Some(TaskProcessTreeSample {
                scope: "same_user_process_tree".into(),
                status: "fresh".into(),
                process_count: Some(1),
                resident_bytes: Some(100),
                sampling_gaps: 0,
                source: "test".into(),
            }),
        );
        span.task_process_baseline_phase = Some("post_spawn".into());
        span.task_process_whole_task_prefix_covered = false;
        span.after = Some(body(2));
        span.task_process_after = Some(TaskProcessTreeSample {
            scope: "same_user_process_tree".into(),
            status: "fresh".into(),
            process_count: Some(1),
            resident_bytes: Some(120),
            sampling_gaps: 0,
            source: "test".into(),
        });
        span.state = TaskResourceSpanState::Closed;

        assert!(!span.has_complete_capture());
        let receipt = serde_json::to_value(span.receipt()).expect("receipt serializes");
        assert_eq!(receipt["state"], "closed");
        assert_eq!(receipt["task_process_baseline_phase"], "post_spawn");
        assert_eq!(receipt["task_process_whole_task_prefix_covered"], false);
        assert_eq!(receipt["task_process_terminal_status"], "fresh");
        assert_eq!(receipt["task_process_capture_complete"], true);
        assert_eq!(receipt["task_process_resident_delta_bytes"], 20);
        assert!(!receipt.to_string().contains("7777"));
    }

    #[test]
    fn terminal_child_rusage_is_durable_but_never_proves_the_workload_tree() {
        let body = |sequence| {
            json!({
                "status":"ok", "freshness":{"status":"fresh"},
                "coverage":{"required_ratio":1.0},
                "identity":{"body_id":"body-test", "body_instance_id":"body-test@boot"},
                "sample":{"sequence":sequence}
            })
        };
        let mut span = TaskResourceSpan::active(
            "terminal-rusage".into(),
            "agent_spawn".into(),
            None,
            body(1),
            None,
            None,
        );
        span.after = Some(body(2));
        span.state = TaskResourceSpanState::Closed;
        assert!(span.has_complete_capture());

        span.task_process_binding_status = Some("unavailable".into());
        span.task_process_binding_reason =
            Some("post_spawn_procfs_baseline_unavailable".into());
        span.task_terminal_resources = Some(TaskTerminalResourceUsage {
            schema_version: TASK_TERMINAL_RESOURCES_SCHEMA_V0.into(),
            accounting_status: "complete".into(),
            source: "linux_raw_waitid_wnowait_rusage".into(),
            scope: "waited_child_generations".into(),
            descendant_coverage: "not_proven".into(),
            workload_lifetime_covered: false,
            spawned_attempt_count: 2,
            captured_attempt_count: 2,
            known_user_cpu_us: Some(11),
            known_system_cpu_us: Some(7),
            known_peak_resident_bytes: Some(4096),
            complete_for_spawned_attempts: true,
            complete_for_workload_tree: false,
            terminal_condition: "all_spawned_children_observed_before_reap".into(),
            peak_resident_semantics:
                "max_ru_maxrss_across_attempts_not_concurrent_tree_peak".into(),
        });

        assert!(!span.has_complete_capture());
        let receipt = serde_json::to_value(span.receipt()).expect("receipt serializes");
        assert_eq!(receipt["schema_version"], TASK_RESOURCE_SPAN_SCHEMA_V3);
        assert_eq!(receipt["task_process_binding_status"], "unavailable");
        assert_eq!(
            receipt["task_process_binding_reason"],
            "post_spawn_procfs_baseline_unavailable"
        );
        assert_eq!(
            receipt["task_process_endpoint_semantics"],
            "post_spawn_baseline_attempt_failed_before_scope_binding"
        );
        assert_eq!(
            receipt["task_terminal_resources"]["known_user_cpu_us"],
            11
        );
        assert_eq!(
            receipt["task_terminal_resources"]["complete_for_workload_tree"],
            false
        );
        assert!(!receipt.to_string().contains("pid"));
    }

    #[test]
    fn delegated_cgroup_receipt_supersedes_procfs_endpoints_for_cpu_memory_tree() {
        let body = |sequence| {
            json!({
                "status":"ok", "freshness":{"status":"fresh"},
                "coverage":{"required_ratio":1.0},
                "identity":{"body_id":"body-test", "body_instance_id":"body-test@boot"},
                "sample":{"sequence":sequence}
            })
        };
        let mut span = TaskResourceSpan::active(
            "delegated-tree".into(),
            "agent_spawn".into(),
            None,
            body(1),
            Some(TaskProcessScopeBinding {
                root_pid: 8_888,
                root_start_ticks: 456,
                owner_uid: 1_000,
            }),
            None,
        );
        span.after = Some(body(2));
        span.state = TaskResourceSpanState::Closed;
        span.task_process_baseline_phase = Some("post_spawn".into());
        span.task_process_whole_task_prefix_covered = false;
        span.task_terminal_resources = Some(TaskTerminalResourceUsage {
            schema_version: TASK_TERMINAL_RESOURCES_SCHEMA_V0.into(),
            accounting_status: "complete".into(),
            source: "linux_raw_waitid_wnowait_rusage".into(),
            scope: "waited_child_generations".into(),
            descendant_coverage: "not_proven".into(),
            workload_lifetime_covered: false,
            spawned_attempt_count: 1,
            captured_attempt_count: 1,
            known_user_cpu_us: Some(5),
            known_system_cpu_us: Some(3),
            known_peak_resident_bytes: Some(4096),
            complete_for_spawned_attempts: true,
            complete_for_workload_tree: false,
            terminal_condition: "all_spawned_children_observed_before_reap".into(),
            peak_resident_semantics:
                "max_ru_maxrss_across_attempts_not_concurrent_tree_peak".into(),
        });
        span.task_workload_resources = Some(TaskWorkloadResourceUsage {
            schema_version: TASK_WORKLOAD_RESOURCES_SCHEMA_V0.into(),
            accounting_status: "complete".into(),
            source: "linux_cgroup_v2_systemd_delegated_scope".into(),
            scope: "delegated_session_workload_tree".into(),
            controllers: vec!["cpu".into(), "memory".into(), "pids".into()],
            workload_lifetime_covered: true,
            generation_count: 1,
            captured_generation_count: 1,
            known_total_cpu_us: Some(8),
            known_user_cpu_us: Some(5),
            known_system_cpu_us: Some(3),
            known_peak_memory_bytes: Some(8192),
            known_peak_pids: Some(2),
            known_oom_event_count: Some(0),
            known_oom_kill_count: Some(0),
            start_before_exec: true,
            final_populated_zero: true,
            complete_for_cpu_memory_workload_tree: true,
            complete_for_pids_workload_tree: true,
            io_accounting_status: "unknown_not_delegated".into(),
            terminal_condition: "all_generations_populated_zero".into(),
            failure_reason: None,
            trust_boundary: "same_uid_non_adversarial_cgroup_membership".into(),
        });

        let debug = format!("{span:?}");
        assert!(!debug.contains("8888"));
        assert!(!debug.contains("root_start_ticks"));
        assert!(span.has_complete_capture());
        let receipt = serde_json::to_value(span.receipt()).expect("receipt serializes");
        assert_eq!(receipt["schema_version"], TASK_RESOURCE_SPAN_SCHEMA_V3);
        assert_eq!(
            receipt["task_workload_resources"]
                ["complete_for_cpu_memory_workload_tree"],
            true
        );
        assert_eq!(
            receipt["task_workload_resources"]["io_accounting_status"],
            "unknown_not_delegated"
        );
        for private_key in ["pid", "pidfd", "cgroup_path", "unit", "nonce"] {
            assert!(receipt.get(private_key).is_none());
            assert!(receipt["task_workload_resources"].get(private_key).is_none());
        }

        let baseline = span
            .task_workload_resources
            .clone()
            .expect("workload receipt");
        let mut tampered = baseline.clone();
        tampered.captured_generation_count = 0;
        assert!(!tampered.proves_complete_cpu_memory_workload_tree());
        tampered = baseline.clone();
        tampered.trust_boundary = "hostile_same_uid_containment".into();
        assert!(!tampered.proves_complete_cpu_memory_workload_tree());
        tampered = baseline.clone();
        tampered.controllers.retain(|controller| controller != "memory");
        assert!(!tampered.proves_complete_cpu_memory_workload_tree());

        span.task_terminal_resources
            .as_mut()
            .expect("terminal receipt")
            .spawned_attempt_count = 2;
        assert!(!span.has_complete_capture());
        span.task_terminal_resources
            .as_mut()
            .expect("terminal receipt")
            .spawned_attempt_count = 1;
        span.task_workload_resources
            .as_mut()
            .expect("workload receipt")
            .complete_for_cpu_memory_workload_tree = false;
        assert!(!span.has_complete_capture());
    }

    #[test]
    fn abandoned_process_span_does_not_claim_a_terminal_procfs_attempt() {
        let mut span = TaskResourceSpan::active(
            "abandoned-process".into(),
            "test".into(),
            None,
            json!({}),
            Some(TaskProcessScopeBinding {
                root_pid: 7_778,
                root_start_ticks: 124,
                owner_uid: 1_000,
            }),
            None,
        );
        span = span.finish(None, Some("observer_ttl_elapsed".into()));

        let receipt = serde_json::to_value(span.receipt()).expect("receipt serializes");
        assert_eq!(
            receipt["task_process_endpoint_semantics"],
            "not_attempted_without_body_after_observation"
        );
        assert!(receipt["task_process_terminal_status"].is_null());
    }

    #[cfg(target_os = "linux")]
    #[test]
    fn process_tree_expected_birth_token_fails_closed_on_mismatch() {
        let pid = std::process::id();
        let binding = linux::bind_process_tree(pid).expect("bind current process");
        linux::bind_process_tree_expected(pid, binding.root_start_ticks)
            .expect("matching birth token");
        let mismatch = binding.root_start_ticks.wrapping_add(1);
        let error = linux::bind_process_tree_expected(pid, mismatch)
            .expect_err("mismatched birth token must fail closed");
        assert!(error.contains("birth token mismatch"));
    }

    #[test]
    fn terminal_session_span_cache_is_bounded_and_evicts_oldest() {
        let mut tracker = TaskResourceSpanTracker::default();
        for index in 0..=TASK_SPAN_TERMINAL_CACHE_CAP {
            let mut span = TaskResourceSpan::active(
                format!("span-{index}"),
                "test".into(),
                None,
                json!({}),
                None,
                None,
            );
            span.state = TaskResourceSpanState::Closed;
            span.ended_at_unix_ms = Some(index as i64);
            cache_terminal_session_span(&mut tracker, &format!("session-{index}"), span);
        }
        assert_eq!(
            tracker.terminal_session_spans.len(),
            TASK_SPAN_TERMINAL_CACHE_CAP
        );
        assert!(!tracker.terminal_session_spans.contains_key("session-0"));
        assert!(tracker
            .terminal_session_spans
            .contains_key(&format!("session-{TASK_SPAN_TERMINAL_CACHE_CAP}")));
    }
}
