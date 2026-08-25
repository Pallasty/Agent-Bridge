//! Pure policy state machine for a bounded, foreground Avatar focus observer.
//!
//! This module deliberately owns no compositor, clock, process, file, prompt,
//! audio, or input authority. Callers provide already-reduced observations and
//! explicit monotonic milliseconds. The only JSON emitted here is a closed,
//! privacy-reduced plan, decision, or aggregate receipt: target titles, raw
//! application identifiers, raw compositor trees, paths, and free-form reasons
//! never cross the projection boundary.

use std::collections::{BTreeMap, BTreeSet};

use serde::Deserialize;
use serde_json::{json, Value};

pub const FOCUS_OBSERVER_PLAN_SCHEMA: &str = "agent_bridge.avatar_focus_follow_observer_plan.v1";
pub const FOCUS_OBSERVER_DECISION_SCHEMA: &str =
    "agent_bridge.avatar_focus_follow_observer_decision.v1";
pub const FOCUS_OBSERVER_RECEIPT_SCHEMA: &str =
    "agent_bridge.avatar_focus_follow_observer_receipt.v1";

pub const DEFAULT_DURATION_MS: u64 = 30 * 60 * 1_000;
pub const DEFAULT_POLL_MS: u64 = 1_000;
pub const DEFAULT_DWELL_MS: u64 = 2_000;
pub const DEFAULT_COOLDOWN_SECS: u64 = 300;
pub const DEFAULT_FAILURE_BACKOFF_SECS: u64 = 30;
pub const DEFAULT_FAILURE_BACKOFF_MAX_SECS: u64 = 900;
pub const DEFAULT_MIN_TRAVEL_PX: i64 = 96;
pub const DEFAULT_MAX_TRAVEL_PX: i64 = 900;
pub const DEFAULT_MAX_ATTEMPTS: u32 = 3;

/// Small built-in denylist for authentication and password-manager windows.
/// Matching remains exact and case-sensitive; callers may extend these sets.
pub const DEFAULT_SENSITIVE_WAYLAND_APP_IDS: &[&str] = &[
    "com.1password.1password",
    "com.bitwarden.desktop",
    "org.keepassxc.KeePassXC",
    "org.gnome.seahorse.Application",
];
pub const DEFAULT_SENSITIVE_XWAYLAND_CLASSES: &[&str] = &["1Password", "Bitwarden", "KeePassXC"];

/// Session-local observer policy. Sensitive identities are exact,
/// case-sensitive matches and are never included in a JSON projection.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct FocusObserverPolicy {
    pub duration_ms: u64,
    pub poll_ms: u64,
    pub dwell_ms: u64,
    pub cooldown_secs: u64,
    pub failure_backoff_secs: u64,
    pub failure_backoff_max_secs: u64,
    pub min_travel_px: i64,
    pub max_travel_px: i64,
    pub max_attempts: u32,
    pub sensitive_wayland_app_ids: BTreeSet<String>,
    pub sensitive_xwayland_classes: BTreeSet<String>,
}

impl Default for FocusObserverPolicy {
    fn default() -> Self {
        Self {
            duration_ms: DEFAULT_DURATION_MS,
            poll_ms: DEFAULT_POLL_MS,
            dwell_ms: DEFAULT_DWELL_MS,
            cooldown_secs: DEFAULT_COOLDOWN_SECS,
            failure_backoff_secs: DEFAULT_FAILURE_BACKOFF_SECS,
            failure_backoff_max_secs: DEFAULT_FAILURE_BACKOFF_MAX_SECS,
            min_travel_px: DEFAULT_MIN_TRAVEL_PX,
            max_travel_px: DEFAULT_MAX_TRAVEL_PX,
            max_attempts: DEFAULT_MAX_ATTEMPTS,
            sensitive_wayland_app_ids: DEFAULT_SENSITIVE_WAYLAND_APP_IDS
                .iter()
                .map(|value| (*value).to_string())
                .collect(),
            sensitive_xwayland_classes: DEFAULT_SENSITIVE_XWAYLAND_CLASSES
                .iter()
                .map(|value| (*value).to_string())
                .collect(),
        }
    }
}

impl FocusObserverPolicy {
    /// Bound caller-controlled values before they influence a foreground loop.
    pub fn normalized(&self) -> Self {
        let failure_backoff_secs = self.failure_backoff_secs.clamp(5, 900);
        Self {
            duration_ms: self.duration_ms.clamp(1_000, DEFAULT_DURATION_MS),
            poll_ms: self.poll_ms.clamp(250, 5_000),
            dwell_ms: self.dwell_ms.clamp(500, 30_000),
            cooldown_secs: self.cooldown_secs.clamp(30, 3_600),
            failure_backoff_secs,
            failure_backoff_max_secs: self
                .failure_backoff_max_secs
                .clamp(failure_backoff_secs, 900),
            min_travel_px: self.min_travel_px.clamp(24, 512),
            max_travel_px: self.max_travel_px.clamp(48, 2_048),
            max_attempts: self.max_attempts.clamp(1, DEFAULT_MAX_ATTEMPTS),
            sensitive_wayland_app_ids: normalize_exact_identities(&self.sensitive_wayland_app_ids),
            sensitive_xwayland_classes: normalize_exact_identities(
                &self.sensitive_xwayland_classes,
            ),
        }
    }

    fn cooldown_ms(&self) -> u64 {
        self.cooldown_secs.saturating_mul(1_000)
    }

    fn failure_backoff_ms(&self, consecutive_failures: u32) -> u64 {
        let exponent = consecutive_failures.saturating_sub(1).min(20);
        let multiplier = 1_u64.checked_shl(exponent).unwrap_or(u64::MAX);
        self.failure_backoff_secs
            .saturating_mul(1_000)
            .saturating_mul(multiplier)
            .min(self.failure_backoff_max_secs.saturating_mul(1_000))
    }
}

fn normalize_exact_identities(values: &BTreeSet<String>) -> BTreeSet<String> {
    values
        .iter()
        .map(|value| value.trim())
        .filter(|value| !value.is_empty())
        .map(str::to_string)
        .collect()
}

/// Structure-only target identity used for exact policy matching. A title is
/// intentionally not representable.
#[derive(Debug, Clone, Deserialize, PartialEq, Eq)]
#[serde(tag = "kind", content = "value", rename_all = "snake_case")]
pub enum FocusTargetIdentity {
    WaylandAppId(String),
    XwaylandClass(String),
    Missing,
}

impl FocusTargetIdentity {
    pub fn is_missing(&self) -> bool {
        match self {
            Self::Missing => true,
            Self::WaylandAppId(value) | Self::XwaylandClass(value) => value.trim().is_empty(),
        }
    }

    pub fn is_sensitive(&self, policy: &FocusObserverPolicy) -> bool {
        match self {
            Self::WaylandAppId(value) => policy.sensitive_wayland_app_ids.contains(value.trim()),
            Self::XwaylandClass(value) => policy.sensitive_xwayland_classes.contains(value.trim()),
            Self::Missing => false,
        }
    }
}

/// One privacy-reduced compositor observation. Unknown JSON fields are denied,
/// so a raw `title` or raw tree cannot accidentally enter the policy layer.
#[derive(Debug, Clone, Deserialize, PartialEq, Eq)]
#[serde(deny_unknown_fields)]
pub struct FocusObserverContext {
    /// Monotonic milliseconds supplied by the runtime.
    pub observed_at_ms: u64,
    pub plan_actionable: bool,
    pub target_node_id: Option<i64>,
    pub travel_px: Option<i64>,
    /// True when the target or any relevant ancestor is fullscreen.
    pub fullscreen: bool,
    /// True when the target or an ancestor carries the exact `ab-sensitive`
    /// compositor mark. The raw mark list never enters this policy layer.
    pub sensitive_mark: bool,
    pub identity: FocusTargetIdentity,
    pub acknowledged_target_node_id: Option<i64>,
    pub paused: bool,
    /// True when another process owns the full-duration Avatar action lock.
    pub action_busy: bool,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum FocusObserverDecisionKind {
    Suppress,
    Dispatch,
    Stop,
}

impl FocusObserverDecisionKind {
    pub const fn as_str(self) -> &'static str {
        match self {
            Self::Suppress => "suppress",
            Self::Dispatch => "dispatch",
            Self::Stop => "stop",
        }
    }
}

/// Closed policy reason set. Values are safe to count and project verbatim.
#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord)]
pub enum FocusObserverReason {
    InitialBaseline,
    PlanNotActionable,
    FocusTargetMissing,
    UnstableTarget,
    AcknowledgedTarget,
    BelowMinTravel,
    AboveMaxTravel,
    FullscreenTarget,
    SensitiveTarget,
    TargetIdentityUnknown,
    Paused,
    ActionInProgress,
    CooldownActive,
    FailureBackoffActive,
    ObservationReadFailed,
    PrestartRuntimeFailed,
    AlreadyAttempted,
    BudgetExhausted,
    RuntimeUnavailable,
    StableFocusTransition,
    DurationElapsed,
    Cancelled,
    FatalRuntimeError,
}

impl FocusObserverReason {
    pub const fn as_str(self) -> &'static str {
        match self {
            Self::InitialBaseline => "initial_baseline",
            Self::PlanNotActionable => "plan_not_actionable",
            Self::FocusTargetMissing => "focus_target_missing",
            Self::UnstableTarget => "unstable_target",
            Self::AcknowledgedTarget => "acknowledged_target",
            Self::BelowMinTravel => "below_min_travel",
            Self::AboveMaxTravel => "above_max_travel",
            Self::FullscreenTarget => "fullscreen_target",
            Self::SensitiveTarget => "sensitive_target",
            Self::TargetIdentityUnknown => "target_identity_unknown",
            Self::Paused => "paused",
            Self::ActionInProgress => "action_in_progress",
            Self::CooldownActive => "cooldown_active",
            Self::FailureBackoffActive => "failure_backoff_active",
            Self::ObservationReadFailed => "observation_read_failed",
            Self::PrestartRuntimeFailed => "prestart_runtime_failed",
            Self::AlreadyAttempted => "already_attempted",
            Self::BudgetExhausted => "budget_exhausted",
            Self::RuntimeUnavailable => "runtime_unavailable",
            Self::StableFocusTransition => "stable_focus_transition",
            Self::DurationElapsed => "duration_elapsed",
            Self::Cancelled => "cancelled",
            Self::FatalRuntimeError => "fatal_runtime_error",
        }
    }

    const fn is_suppression(self) -> bool {
        matches!(
            self,
            Self::InitialBaseline
                | Self::PlanNotActionable
                | Self::FocusTargetMissing
                | Self::UnstableTarget
                | Self::AcknowledgedTarget
                | Self::BelowMinTravel
                | Self::AboveMaxTravel
                | Self::FullscreenTarget
                | Self::SensitiveTarget
                | Self::TargetIdentityUnknown
                | Self::Paused
                | Self::ActionInProgress
                | Self::CooldownActive
                | Self::FailureBackoffActive
                | Self::ObservationReadFailed
                | Self::PrestartRuntimeFailed
                | Self::AlreadyAttempted
                | Self::BudgetExhausted
                | Self::RuntimeUnavailable
        )
    }
}

const SUPPRESSION_REASONS: [FocusObserverReason; 19] = [
    FocusObserverReason::InitialBaseline,
    FocusObserverReason::PlanNotActionable,
    FocusObserverReason::FocusTargetMissing,
    FocusObserverReason::UnstableTarget,
    FocusObserverReason::AcknowledgedTarget,
    FocusObserverReason::BelowMinTravel,
    FocusObserverReason::AboveMaxTravel,
    FocusObserverReason::FullscreenTarget,
    FocusObserverReason::SensitiveTarget,
    FocusObserverReason::TargetIdentityUnknown,
    FocusObserverReason::Paused,
    FocusObserverReason::ActionInProgress,
    FocusObserverReason::CooldownActive,
    FocusObserverReason::FailureBackoffActive,
    FocusObserverReason::ObservationReadFailed,
    FocusObserverReason::PrestartRuntimeFailed,
    FocusObserverReason::AlreadyAttempted,
    FocusObserverReason::BudgetExhausted,
    FocusObserverReason::RuntimeUnavailable,
];

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct FocusObserverDecision {
    pub kind: FocusObserverDecisionKind,
    pub reason: FocusObserverReason,
    /// Internal dispatch identity. Privacy JSON deliberately omits it.
    pub target_node_id: Option<i64>,
    pub retry_after_ms: Option<u64>,
    pub attempt_count: u32,
    pub remaining_attempts: u32,
}

impl FocusObserverDecision {
    /// Closed, effect-free projection suitable for stdout or bounded receipts.
    pub fn privacy_json(&self) -> Value {
        json!({
            "schema": FOCUS_OBSERVER_DECISION_SCHEMA,
            "decision": self.kind.as_str(),
            "reason": self.reason.as_str(),
            "retry_after_ms": self.retry_after_ms,
            "attempt_count": self.attempt_count,
            "remaining_attempts": self.remaining_attempts,
            "requests_avatar_action": self.kind == FocusObserverDecisionKind::Dispatch,
            "decision_is_effect_free": true,
            "moves_pointer": false,
            "changes_focus": false,
            "emits_input": false,
            "shows_prompt": false,
            "emits_audio": false,
        })
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum FocusAttemptOutcome {
    CompletedVerified,
    Cancelled,
    Failed,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum FocusObserverTerminalReason {
    DurationElapsed,
    BudgetExhausted,
    Cancelled,
    FatalRuntimeError,
}

impl FocusObserverTerminalReason {
    pub const fn as_str(self) -> &'static str {
        match self {
            Self::DurationElapsed => "duration_elapsed",
            Self::BudgetExhausted => "budget_exhausted",
            Self::Cancelled => "cancelled",
            Self::FatalRuntimeError => "fatal_runtime_error",
        }
    }

    const fn decision_reason(self) -> FocusObserverReason {
        match self {
            Self::DurationElapsed => FocusObserverReason::DurationElapsed,
            Self::BudgetExhausted => FocusObserverReason::BudgetExhausted,
            Self::Cancelled => FocusObserverReason::Cancelled,
            Self::FatalRuntimeError => FocusObserverReason::FatalRuntimeError,
        }
    }
}

#[derive(Debug, thiserror::Error, PartialEq, Eq)]
pub enum FocusObserverStateError {
    #[error("target is not ready for a focus observer attempt")]
    TargetNotReady,
    #[error("another focus observer attempt is already in flight")]
    AttemptAlreadyInFlight,
    #[error("focus observer attempt budget is exhausted")]
    AttemptBudgetExhausted,
    #[error("focus observer attempt target does not match the in-flight target")]
    AttemptTargetMismatch,
}

#[derive(Debug, Clone)]
struct DwellCandidate {
    target_node_id: i64,
    first_seen_at_ms: u64,
    samples: u32,
}

#[derive(Debug, Clone)]
pub struct FocusObserverState {
    policy: FocusObserverPolicy,
    started_at_ms: u64,
    stopped_at_ms: Option<u64>,
    terminal_reason: Option<FocusObserverTerminalReason>,
    baseline_target_node_id: Option<i64>,
    last_observed_target_node_id: Option<i64>,
    candidate: Option<DwellCandidate>,
    dispatch_ready_target_node_id: Option<i64>,
    in_flight_target_node_id: Option<i64>,
    attempted_targets: BTreeSet<i64>,
    cooldown_until_ms: Option<u64>,
    failure_backoff_until_ms: Option<u64>,
    consecutive_attempt_failures: u32,
    consecutive_observation_failures: u32,
    consecutive_prestart_runtime_failures: u32,
    poll_count: u64,
    tree_read_failure_count: u64,
    prestart_runtime_failure_count: u64,
    focus_transition_count: u64,
    stable_candidate_count: u64,
    attempt_count: u32,
    completed_count: u32,
    cancelled_count: u32,
    failed_count: u32,
    suppression_counts: BTreeMap<FocusObserverReason, u64>,
}

impl FocusObserverState {
    pub fn new(policy: FocusObserverPolicy, started_at_ms: u64) -> Self {
        Self {
            policy: policy.normalized(),
            started_at_ms,
            stopped_at_ms: None,
            terminal_reason: None,
            baseline_target_node_id: None,
            last_observed_target_node_id: None,
            candidate: None,
            dispatch_ready_target_node_id: None,
            in_flight_target_node_id: None,
            attempted_targets: BTreeSet::new(),
            cooldown_until_ms: None,
            failure_backoff_until_ms: None,
            consecutive_attempt_failures: 0,
            consecutive_observation_failures: 0,
            consecutive_prestart_runtime_failures: 0,
            poll_count: 0,
            tree_read_failure_count: 0,
            prestart_runtime_failure_count: 0,
            focus_transition_count: 0,
            stable_candidate_count: 0,
            attempt_count: 0,
            completed_count: 0,
            cancelled_count: 0,
            failed_count: 0,
            suppression_counts: BTreeMap::new(),
        }
    }

    pub fn policy(&self) -> &FocusObserverPolicy {
        &self.policy
    }

    pub fn terminal_reason(&self) -> Option<FocusObserverTerminalReason> {
        self.terminal_reason
    }

    pub fn attempt_count(&self) -> u32 {
        self.attempt_count
    }

    pub fn remaining_attempts(&self) -> u32 {
        self.policy.max_attempts.saturating_sub(self.attempt_count)
    }

    pub fn backoff_remaining_ms(&self, now_ms: u64) -> u64 {
        self.failure_backoff_until_ms
            .unwrap_or(0)
            .saturating_sub(now_ms)
    }

    /// Seed only the bounded remainder of a previously validated completed
    /// action ACK. The runtime is responsible for binding that ACK to the
    /// current compositor session and exact Avatar node before calling this.
    pub fn seed_cooldown_remaining(&mut self, now_ms: u64, remaining_ms: u64) {
        let bounded = remaining_ms.min(self.policy.cooldown_ms());
        if bounded > 0 {
            self.cooldown_until_ms = Some(now_ms.saturating_add(bounded));
        }
    }

    /// Observe one already-reduced compositor sample and advance only policy
    /// state. A `Dispatch` decision still has no side effect; the runtime must
    /// acquire its full-duration action lock, re-observe, and then call
    /// [`Self::start_attempt`].
    pub fn observe(&mut self, context: &FocusObserverContext) -> FocusObserverDecision {
        self.poll_count = self.poll_count.saturating_add(1);
        if let Some(decision) = self.terminal_decision() {
            return decision;
        }
        if context.observed_at_ms.saturating_sub(self.started_at_ms) >= self.policy.duration_ms {
            return self.stop_at(
                context.observed_at_ms,
                FocusObserverTerminalReason::DurationElapsed,
            );
        }
        if self.attempt_count >= self.policy.max_attempts {
            self.increment_suppression(FocusObserverReason::BudgetExhausted);
            return self.stop_at(
                context.observed_at_ms,
                FocusObserverTerminalReason::BudgetExhausted,
            );
        }

        self.track_focus_transition(context.target_node_id);
        if self.baseline_target_node_id.is_none() && context.target_node_id.is_some() {
            self.baseline_target_node_id = context.target_node_id;
        }

        if context.paused {
            return self.suppress(FocusObserverReason::Paused, None, None);
        }
        if self.in_flight_target_node_id.is_some() || context.action_busy {
            return self.suppress(FocusObserverReason::ActionInProgress, None, None);
        }
        let Some(target_node_id) = context.target_node_id else {
            if !context.plan_actionable {
                return self.suppress(FocusObserverReason::PlanNotActionable, None, None);
            }
            return self.suppress(FocusObserverReason::FocusTargetMissing, None, None);
        };
        if context.fullscreen {
            return self.suppress(
                FocusObserverReason::FullscreenTarget,
                Some(target_node_id),
                None,
            );
        }
        if context.sensitive_mark {
            return self.suppress(
                FocusObserverReason::SensitiveTarget,
                Some(target_node_id),
                None,
            );
        }
        if context.identity.is_missing() {
            return self.suppress(
                FocusObserverReason::TargetIdentityUnknown,
                Some(target_node_id),
                None,
            );
        }
        if context.identity.is_sensitive(&self.policy) {
            return self.suppress(
                FocusObserverReason::SensitiveTarget,
                Some(target_node_id),
                None,
            );
        }
        if !context.plan_actionable {
            return self.suppress(
                FocusObserverReason::PlanNotActionable,
                Some(target_node_id),
                None,
            );
        }
        if context.acknowledged_target_node_id == Some(target_node_id) {
            return self.suppress(
                FocusObserverReason::AcknowledgedTarget,
                Some(target_node_id),
                None,
            );
        }
        if context
            .travel_px
            .is_none_or(|travel_px| travel_px < self.policy.min_travel_px)
        {
            return self.suppress(
                FocusObserverReason::BelowMinTravel,
                Some(target_node_id),
                None,
            );
        }
        if context
            .travel_px
            .is_some_and(|travel_px| travel_px > self.policy.max_travel_px)
        {
            return self.suppress(
                FocusObserverReason::AboveMaxTravel,
                Some(target_node_id),
                None,
            );
        }
        if let Some(until_ms) = self.failure_backoff_until_ms {
            let remaining_ms = until_ms.saturating_sub(context.observed_at_ms);
            if remaining_ms > 0 {
                return self.suppress(
                    FocusObserverReason::FailureBackoffActive,
                    Some(target_node_id),
                    Some(remaining_ms),
                );
            }
        }
        if let Some(until_ms) = self.cooldown_until_ms {
            let remaining_ms = until_ms.saturating_sub(context.observed_at_ms);
            if remaining_ms > 0 {
                return self.suppress(
                    FocusObserverReason::CooldownActive,
                    Some(target_node_id),
                    Some(remaining_ms),
                );
            }
        }
        if self.attempted_targets.contains(&target_node_id) {
            return self.suppress(
                FocusObserverReason::AlreadyAttempted,
                Some(target_node_id),
                None,
            );
        }
        if self.baseline_target_node_id == Some(target_node_id) {
            return self.suppress(
                FocusObserverReason::InitialBaseline,
                Some(target_node_id),
                None,
            );
        }

        let candidate_changed = self
            .candidate
            .as_ref()
            .is_none_or(|candidate| candidate.target_node_id != target_node_id);
        if candidate_changed {
            self.candidate = Some(DwellCandidate {
                target_node_id,
                first_seen_at_ms: context.observed_at_ms,
                samples: 1,
            });
            self.dispatch_ready_target_node_id = None;
            return self.suppress(
                FocusObserverReason::UnstableTarget,
                Some(target_node_id),
                Some(self.policy.dwell_ms),
            );
        }

        let candidate = self
            .candidate
            .as_mut()
            .expect("candidate established above");
        candidate.samples = candidate.samples.saturating_add(1);
        let elapsed_ms = context
            .observed_at_ms
            .saturating_sub(candidate.first_seen_at_ms);
        if candidate.samples < 2 || elapsed_ms < self.policy.dwell_ms {
            return self.suppress(
                FocusObserverReason::UnstableTarget,
                Some(target_node_id),
                Some(self.policy.dwell_ms.saturating_sub(elapsed_ms)),
            );
        }

        if self.dispatch_ready_target_node_id != Some(target_node_id) {
            self.stable_candidate_count = self.stable_candidate_count.saturating_add(1);
        }
        self.dispatch_ready_target_node_id = Some(target_node_id);
        self.decision(
            FocusObserverDecisionKind::Dispatch,
            FocusObserverReason::StableFocusTransition,
            Some(target_node_id),
            None,
        )
    }

    /// Reserve the previously returned dispatch while the runtime enters the
    /// action core. A structured proof that no durable action started may
    /// release this reservation with [`Self::discard_unstarted_attempt`].
    pub fn start_attempt(&mut self, target_node_id: i64) -> Result<(), FocusObserverStateError> {
        if self.in_flight_target_node_id.is_some() {
            return Err(FocusObserverStateError::AttemptAlreadyInFlight);
        }
        if self.attempt_count >= self.policy.max_attempts {
            return Err(FocusObserverStateError::AttemptBudgetExhausted);
        }
        if self.dispatch_ready_target_node_id != Some(target_node_id)
            || self.attempted_targets.contains(&target_node_id)
        {
            return Err(FocusObserverStateError::TargetNotReady);
        }
        self.attempt_count = self.attempt_count.saturating_add(1);
        self.attempted_targets.insert(target_node_id);
        self.in_flight_target_node_id = Some(target_node_id);
        self.dispatch_ready_target_node_id = None;
        self.candidate = None;
        Ok(())
    }

    pub fn finish_attempt(
        &mut self,
        target_node_id: i64,
        outcome: FocusAttemptOutcome,
        observed_at_ms: u64,
    ) -> Result<(), FocusObserverStateError> {
        if self.in_flight_target_node_id != Some(target_node_id) {
            return Err(FocusObserverStateError::AttemptTargetMismatch);
        }
        self.in_flight_target_node_id = None;
        self.cooldown_until_ms = Some(observed_at_ms.saturating_add(self.policy.cooldown_ms()));
        match outcome {
            FocusAttemptOutcome::CompletedVerified => {
                self.completed_count = self.completed_count.saturating_add(1);
                self.consecutive_attempt_failures = 0;
                self.failure_backoff_until_ms = None;
            }
            FocusAttemptOutcome::Cancelled => {
                self.cancelled_count = self.cancelled_count.saturating_add(1);
            }
            FocusAttemptOutcome::Failed => {
                self.failed_count = self.failed_count.saturating_add(1);
                self.consecutive_attempt_failures =
                    self.consecutive_attempt_failures.saturating_add(1);
                self.failure_backoff_until_ms = Some(
                    observed_at_ms.saturating_add(
                        self.policy
                            .failure_backoff_ms(self.consecutive_attempt_failures),
                    ),
                );
            }
        }
        Ok(())
    }

    /// Release a dispatch reservation only when the runtime received a
    /// structured action result proving that no durable `started` record was
    /// written. Ambiguous I/O errors must not use this path: they remain
    /// attempts so a possibly-started movement cannot be retried.
    pub fn discard_unstarted_attempt(
        &mut self,
        target_node_id: i64,
    ) -> Result<(), FocusObserverStateError> {
        if self.in_flight_target_node_id != Some(target_node_id) {
            return Err(FocusObserverStateError::AttemptTargetMismatch);
        }
        self.in_flight_target_node_id = None;
        self.attempt_count = self.attempt_count.saturating_sub(1);
        self.attempted_targets.remove(&target_node_id);
        self.reset_candidate();
        Ok(())
    }

    /// Record one failed tree/sensor observation without accepting a raw error.
    /// Callers can use [`Self::backoff_remaining_ms`] before the next read.
    pub fn record_observation_failure(&mut self, observed_at_ms: u64) -> FocusObserverDecision {
        self.poll_count = self.poll_count.saturating_add(1);
        self.tree_read_failure_count = self.tree_read_failure_count.saturating_add(1);
        self.consecutive_observation_failures =
            self.consecutive_observation_failures.saturating_add(1);
        let backoff_ms = self
            .policy
            .failure_backoff_ms(self.consecutive_observation_failures);
        self.failure_backoff_until_ms = Some(observed_at_ms.saturating_add(backoff_ms));
        self.suppress(
            FocusObserverReason::ObservationReadFailed,
            None,
            Some(backoff_ms),
        )
    }

    pub fn record_observation_success(&mut self) {
        self.consecutive_observation_failures = 0;
    }

    /// Record a closed pre-action runtime failure without misclassifying it as
    /// a compositor tree-read failure or a real movement attempt.
    pub fn record_prestart_runtime_failure(
        &mut self,
        observed_at_ms: u64,
    ) -> FocusObserverDecision {
        self.prestart_runtime_failure_count = self.prestart_runtime_failure_count.saturating_add(1);
        self.consecutive_prestart_runtime_failures =
            self.consecutive_prestart_runtime_failures.saturating_add(1);
        let backoff_ms = self
            .policy
            .failure_backoff_ms(self.consecutive_prestart_runtime_failures);
        self.failure_backoff_until_ms = Some(observed_at_ms.saturating_add(backoff_ms));
        self.suppress(
            FocusObserverReason::PrestartRuntimeFailed,
            None,
            Some(backoff_ms),
        )
    }

    pub fn record_prestart_runtime_success(&mut self) {
        self.consecutive_prestart_runtime_failures = 0;
    }

    pub fn cancel(&mut self, observed_at_ms: u64) -> FocusObserverDecision {
        self.stop_at(observed_at_ms, FocusObserverTerminalReason::Cancelled)
    }

    pub fn fail_runtime(&mut self, observed_at_ms: u64) -> FocusObserverDecision {
        self.stop_at(
            observed_at_ms,
            FocusObserverTerminalReason::FatalRuntimeError,
        )
    }

    pub fn receipt_json(&self, observed_at_ms: u64) -> Value {
        let effective_stop_ms = self.stopped_at_ms.unwrap_or(observed_at_ms);
        let terminal_reason = self
            .terminal_reason
            .map(FocusObserverTerminalReason::as_str);
        let status = match self.terminal_reason {
            Some(FocusObserverTerminalReason::Cancelled) => "cancelled",
            Some(FocusObserverTerminalReason::FatalRuntimeError) => "failed",
            Some(_) => "completed",
            None => "running",
        };
        let suppressed = SUPPRESSION_REASONS
            .into_iter()
            .map(|reason| {
                (
                    reason.as_str().to_string(),
                    Value::from(self.suppression_counts.get(&reason).copied().unwrap_or(0)),
                )
            })
            .collect::<serde_json::Map<String, Value>>();
        json!({
            "schema": FOCUS_OBSERVER_RECEIPT_SCHEMA,
            "status": status,
            "completed": self.terminal_reason.is_some(),
            "terminal_reason": terminal_reason,
            "elapsed_ms": effective_stop_ms.saturating_sub(self.started_at_ms),
            "poll_count": self.poll_count,
            "tree_read_failure_count": self.tree_read_failure_count,
            "prestart_runtime_failure_count": self.prestart_runtime_failure_count,
            "focus_transition_count": self.focus_transition_count,
            "stable_candidate_count": self.stable_candidate_count,
            "attempt_count": self.attempt_count,
            "completed_count": self.completed_count,
            "cancelled_count": self.cancelled_count,
            "failed_count": self.failed_count,
            "suppressed": Value::Object(suppressed),
            "bounds": {
                "duration_ms": self.policy.duration_ms,
                "poll_ms": self.policy.poll_ms,
                "dwell_ms": self.policy.dwell_ms,
                "cooldown_secs": self.policy.cooldown_secs,
                "failure_backoff_secs": self.policy.failure_backoff_secs,
                "failure_backoff_max_secs": self.policy.failure_backoff_max_secs,
                "min_travel_px": self.policy.min_travel_px,
                "max_travel_px": self.policy.max_travel_px,
                "max_attempts": self.policy.max_attempts,
            },
            "privacy": privacy_contract_json(),
            "effects": effect_contract_json(true),
        })
    }

    fn track_focus_transition(&mut self, target_node_id: Option<i64>) {
        if self.last_observed_target_node_id != target_node_id {
            if self.last_observed_target_node_id.is_some() {
                self.focus_transition_count = self.focus_transition_count.saturating_add(1);
            }
            self.last_observed_target_node_id = target_node_id;
            self.reset_candidate();
        }
    }

    fn reset_candidate(&mut self) {
        self.candidate = None;
        self.dispatch_ready_target_node_id = None;
    }

    fn suppress(
        &mut self,
        reason: FocusObserverReason,
        target_node_id: Option<i64>,
        retry_after_ms: Option<u64>,
    ) -> FocusObserverDecision {
        // Dwell is itself represented by repeated `unstable_target`
        // suppressions. Every other gate invalidates the candidate and requires
        // a fresh full dwell after that gate clears.
        if reason != FocusObserverReason::UnstableTarget {
            self.reset_candidate();
        }
        self.increment_suppression(reason);
        self.decision(
            FocusObserverDecisionKind::Suppress,
            reason,
            target_node_id,
            retry_after_ms,
        )
    }

    fn increment_suppression(&mut self, reason: FocusObserverReason) {
        if reason.is_suppression() {
            let count = self.suppression_counts.entry(reason).or_default();
            *count = count.saturating_add(1);
        }
    }

    fn stop_at(
        &mut self,
        observed_at_ms: u64,
        reason: FocusObserverTerminalReason,
    ) -> FocusObserverDecision {
        if self.terminal_reason.is_none() {
            self.terminal_reason = Some(reason);
            self.stopped_at_ms = Some(observed_at_ms);
            self.reset_candidate();
        }
        self.terminal_decision()
            .expect("stop_at always establishes a terminal reason")
    }

    fn terminal_decision(&self) -> Option<FocusObserverDecision> {
        let reason = self.terminal_reason?;
        Some(self.decision(
            FocusObserverDecisionKind::Stop,
            reason.decision_reason(),
            None,
            None,
        ))
    }

    fn decision(
        &self,
        kind: FocusObserverDecisionKind,
        reason: FocusObserverReason,
        target_node_id: Option<i64>,
        retry_after_ms: Option<u64>,
    ) -> FocusObserverDecision {
        FocusObserverDecision {
            kind,
            reason,
            target_node_id,
            retry_after_ms,
            attempt_count: self.attempt_count,
            remaining_attempts: self.remaining_attempts(),
        }
    }
}

/// Privacy-safe preflight projection. `runtime_ready` is supplied by the I/O
/// layer after checking compositor/runtime paths and locks.
pub fn focus_observer_plan_json(
    policy: &FocusObserverPolicy,
    execute_requested: bool,
    runtime_ready: bool,
) -> Value {
    let policy = policy.normalized();
    json!({
        "schema": FOCUS_OBSERVER_PLAN_SCHEMA,
        "status": if !runtime_ready { "blocked" } else if execute_requested { "ready" } else { "dry_run" },
        "ready": runtime_ready,
        "execute_requested": execute_requested,
        "default_enabled": false,
        "authorization_mode": "agent_reversible_expression",
        "bounds": {
            "duration_ms": policy.duration_ms,
            "poll_ms": policy.poll_ms,
            "dwell_ms": policy.dwell_ms,
            "cooldown_secs": policy.cooldown_secs,
            "failure_backoff_secs": policy.failure_backoff_secs,
            "failure_backoff_max_secs": policy.failure_backoff_max_secs,
            "min_travel_px": policy.min_travel_px,
            "max_travel_px": policy.max_travel_px,
            "max_attempts": policy.max_attempts,
        },
        "policy": {
            "initial_target_is_baseline": true,
            "stable_target_required": true,
            "minimum_stable_samples": 2,
            "acknowledged_target_suppression": true,
            "fullscreen_suppression": true,
            "structured_identity_required": true,
            "exact_sensitive_identity_suppression": true,
            "pause_suppression": true,
            "action_lock_suppression": true,
            "one_attempt_per_target_per_run": true,
            "cooldown_after_any_attempt": true,
            "exponential_failure_backoff": true,
        },
        "effects": effect_contract_json(execute_requested),
        "privacy": privacy_contract_json(),
    })
}

fn effect_contract_json(execute_requested: bool) -> Value {
    json!({
        "moves_avatar_when_executing": true,
        "moves_avatar_this_invocation": execute_requested,
        "moves_pointer": false,
        "changes_focus": false,
        "emits_input": false,
        "shows_prompt": false,
        "emits_audio": false,
        "installs_service": false,
    })
}

fn privacy_contract_json() -> Value {
    json!({
        "persists_window_title": false,
        "projects_app_id": false,
        "projects_xwayland_class": false,
        "projects_raw_tree": false,
        "projects_free_reason": false,
        "projects_target_node_id": false,
    })
}
