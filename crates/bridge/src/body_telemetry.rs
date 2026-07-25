//! Platform-neutral, read-only body telemetry primitives.
//!
//! This module deliberately does not know how to query a host. Platform
//! adapters supply [`BodySample`] values; this core owns their truth semantics:
//! bounded history, stale/unsupported states, and pressure hysteresis. Keeping
//! those rules here prevents macOS, Linux, and test adapters from disagreeing
//! about what the agent's body currently knows.

use serde::{Deserialize, Serialize};
use serde_json::{json, Value};
use std::collections::{BTreeMap, VecDeque};
use std::sync::{Mutex, OnceLock};
use std::time::{SystemTime, UNIX_EPOCH};

#[cfg(target_os = "linux")]
pub mod linux;
#[cfg(target_os = "macos")]
pub mod macos;

pub const BODY_STATUS_SCHEMA_V0: &str = "agent_bridge.body_status.v0";
pub const TASK_RESOURCE_SPAN_SCHEMA_V0: &str = "agent_bridge.task_resource_span.v0";
pub const SHADOW_REFLEX_ADVICE_SCHEMA_V0: &str = "agent_bridge.shadow_reflex_advice.v0";

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

    #[cfg(target_os = "linux")]
    {
        return linux::body_status_snapshot();
    }

    #[cfg(not(any(target_os = "macos", target_os = "linux")))]
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

/// Produce a non-executing recommendation from the current pressure projection.
/// The reducer behind `body_status_snapshot` already applies hysteresis; this
/// function deliberately adds no background loop, persistence, or actuator.
pub fn body_reflex_advice_snapshot() -> Value {
    let status = body_status_snapshot();
    shadow_reflex_advice_from_status(&status)
}

fn shadow_reflex_advice_from_status(status: &Value) -> Value {
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
    pub abandonment_reason: Option<String>,
}

impl TaskResourceSpan {
    fn active(span_id: String, task_kind: String, task_ref: Option<String>, before: Value) -> Self {
        Self {
            schema_version: TASK_RESOURCE_SPAN_SCHEMA_V0.to_string(),
            span_id,
            task_kind,
            task_ref,
            state: TaskResourceSpanState::Active,
            started_at_unix_ms: unix_now_ms(),
            ended_at_unix_ms: None,
            before,
            checkpoints: Vec::new(),
            after: None,
            sampling_gaps: 0,
            abandonment_reason: None,
        }
    }

    fn finish(mut self, after: Option<Value>, reason: Option<String>) -> Self {
        self.ended_at_unix_ms = Some(unix_now_ms());
        self.after = after;
        self.abandonment_reason = reason;
        self.state = if self.after.is_some() {
            TaskResourceSpanState::Closed
        } else {
            TaskResourceSpanState::Abandoned
        };
        self
    }

    pub fn has_complete_capture(&self) -> bool {
        self.state == TaskResourceSpanState::Closed && self.after.is_some()
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
            abandonment_reason: self.abandonment_reason.clone(),
        }
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
    session_spans: BTreeMap<String, String>,
}

const TASK_SPAN_CHECKPOINT_CAP: usize = 8;
static TASK_SPANS: OnceLock<Mutex<TaskResourceSpanTracker>> = OnceLock::new();

/// Start a task span from one grounded before-observation. Starting is refused
/// when telemetry is disabled or unavailable; callers cannot create a span
/// whose start state is merely inferred.
pub fn start_task_resource_span(
    span_id: String,
    task_kind: String,
    task_ref: Option<String>,
) -> std::result::Result<TaskResourceSpan, String> {
    let before = live_body_snapshot().ok_or_else(|| {
        "body telemetry is not live; set AGENT_BRIDGE_BODY_TELEMETRY=1 on a supported host"
            .to_string()
    })?;
    let tracker = TASK_SPANS.get_or_init(|| Mutex::new(TaskResourceSpanTracker::default()));
    let mut tracker = tracker
        .lock()
        .map_err(|_| "body task-span tracker mutex poisoned".to_string())?;
    if tracker.active.contains_key(&span_id) {
        return Err(format!("task span '{span_id}' is already active"));
    }
    let span = TaskResourceSpan::active(span_id.clone(), task_kind, task_ref, before);
    tracker.active.insert(span_id, span.clone());
    Ok(span)
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
    let span = tracker
        .active
        .remove(span_id)
        .ok_or_else(|| format!("unknown active task span '{span_id}'"))?;
    let after = live_body_snapshot();
    let reason = after
        .is_none()
        .then(|| "after_observation_unavailable".to_string());
    Ok(span.finish(after, reason))
}

/// Associate an interactive agent session with an already-started body span.
/// The session id is opaque and contains no prompt or transcript data.
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
    tracker.session_spans.insert(session_id, span_id);
    Ok(())
}

/// Finish the body span bound to an interactive session, if one exists.
pub fn finish_task_resource_span_for_session(
    session_id: &str,
) -> std::result::Result<Option<TaskResourceSpan>, String> {
    let tracker = TASK_SPANS.get_or_init(|| Mutex::new(TaskResourceSpanTracker::default()));
    let span_id = {
        let mut tracker = tracker
            .lock()
            .map_err(|_| "body task-span tracker mutex poisoned".to_string())?;
        tracker.session_spans.remove(session_id)
    };
    span_id.map(|id| finish_task_resource_span(&id)).transpose()
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
    let span = tracker
        .active
        .remove(span_id)
        .ok_or_else(|| format!("unknown active task span '{span_id}'"))?;
    tracker.session_spans.retain(|_, id| id != span_id);
    Ok(span.finish(None, Some(reason)))
}

fn live_body_snapshot() -> Option<Value> {
    let snapshot = body_status_snapshot();
    (snapshot.get("status").and_then(Value::as_str) == Some("ok")).then_some(snapshot)
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
}
