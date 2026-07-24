//! Platform-neutral, read-only body telemetry primitives.
//!
//! This module deliberately does not know how to query a host. Platform
//! adapters supply [`BodySample`] values; this core owns their truth semantics:
//! bounded history, stale/unsupported states, and pressure hysteresis. Keeping
//! those rules here prevents macOS, Linux, and test adapters from disagreeing
//! about what the agent's body currently knows.

use serde::{Deserialize, Serialize};
use serde_json::{json, Value};
use std::collections::VecDeque;

#[cfg(target_os = "macos")]
pub mod macos;

pub const BODY_STATUS_SCHEMA_V0: &str = "agent_bridge.body_status.v0";

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
    /// Separate VRAM is intentionally `not_applicable` on unified-memory hosts.
    pub vram_total_bytes: MetricValue<u64>,
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct StorageSample {
    pub total_bytes: MetricValue<u64>,
    pub available_bytes: MetricValue<u64>,
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct ProcessFootprint {
    pub resident_bytes: MetricValue<u64>,
}

/// One point-in-time host observation. `observed_at_mono_ms` is monotonic and
/// should be used for ordering and age; `observed_at_unix_ms` is for display.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct BodySample {
    pub sequence: u64,
    pub observed_at_mono_ms: u64,
    pub observed_at_unix_ms: i64,
    /// Normalized [0, 1] process-wide CPU pressure, never a raw counter.
    pub cpu_utilization_ratio: MetricValue<f64>,
    pub memory: MemorySample,
    pub storage: StorageSample,
    pub process: ProcessFootprint,
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
                vram_total_bytes: unavailable_metric(MetricStatus::Unknown, "no_sample"),
            },
            storage: StorageSample {
                total_bytes: unavailable_metric(MetricStatus::Unknown, "no_sample"),
                available_bytes: unavailable_metric(MetricStatus::Unknown, "no_sample"),
            },
            process: ProcessFootprint {
                resident_bytes: unavailable_metric(MetricStatus::Unknown, "no_sample"),
            },
        }
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

#[derive(Debug, Clone, Copy, PartialEq)]
pub struct PressureInput {
    pub cpu_ratio: Option<f64>,
    pub memory_ratio: Option<f64>,
    pub storage_ratio: Option<f64>,
}

impl PressureInput {
    pub fn from_sample(sample: &BodySample) -> Self {
        Self {
            cpu_ratio: sample.cpu_utilization_ratio.live().copied(),
            memory_ratio: used_ratio(&sample.memory.total_bytes, &sample.memory.available_bytes),
            storage_ratio: used_ratio(&sample.storage.total_bytes, &sample.storage.available_bytes),
        }
    }

    fn peak(self) -> Option<f64> {
        [self.cpu_ratio, self.memory_ratio, self.storage_ratio]
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

    #[cfg(not(target_os = "macos"))]
    {
        json!({
            "schema_version": BODY_STATUS_SCHEMA_V0,
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

fn disabled_body_status() -> Value {
    json!({
        "schema_version": BODY_STATUS_SCHEMA_V0,
        "mode": "shadow_only",
        "enabled": false,
        "status": "disabled",
        "reason": "set AGENT_BRIDGE_BODY_TELEMETRY=1 to enable read-only host sampling",
        "read_only": true,
        "persists_raw_samples": false,
    })
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
                vram_total_bytes: MetricValue::unavailable(
                    MetricStatus::NotApplicable,
                    "unified_memory",
                ),
            },
            storage: StorageSample {
                total_bytes: bytes_metric(Some(100)),
                available_bytes: bytes_metric(Some(80)),
            },
            process: ProcessFootprint {
                resident_bytes: bytes_metric(Some(10)),
            },
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
                storage_ratio: None
            }),
            PressureLevel::Nominal
        );
        assert_eq!(
            reducer.update(PressureInput {
                cpu_ratio: Some(0.90),
                memory_ratio: None,
                storage_ratio: None
            }),
            PressureLevel::Nominal
        );
        assert_eq!(
            reducer.update(PressureInput {
                cpu_ratio: Some(0.90),
                memory_ratio: None,
                storage_ratio: None
            }),
            PressureLevel::High
        );
        // 0.82 is below high_at but within its recovery margin, so it remains high.
        assert_eq!(
            reducer.update(PressureInput {
                cpu_ratio: Some(0.82),
                memory_ratio: None,
                storage_ratio: None
            }),
            PressureLevel::High
        );
        // Sustained 0.70 has cleared high recovery, but needs three samples to recover.
        assert_eq!(
            reducer.update(PressureInput {
                cpu_ratio: Some(0.70),
                memory_ratio: None,
                storage_ratio: None
            }),
            PressureLevel::High
        );
        assert_eq!(
            reducer.update(PressureInput {
                cpu_ratio: Some(0.70),
                memory_ratio: None,
                storage_ratio: None
            }),
            PressureLevel::High
        );
        assert_eq!(
            reducer.update(PressureInput {
                cpu_ratio: Some(0.70),
                memory_ratio: None,
                storage_ratio: None
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
                storage_ratio: Some(1.1)
            }),
            PressureLevel::Unknown
        );
        assert_eq!(
            reducer.update(PressureInput {
                cpu_ratio: None,
                memory_ratio: None,
                storage_ratio: None
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
        assert_eq!(value["schema_version"], BODY_STATUS_SCHEMA_V0);
        assert_eq!(value["status"], "disabled");
        assert_eq!(value["enabled"], false);
        assert!(value.get("sample").is_none());
    }
}
