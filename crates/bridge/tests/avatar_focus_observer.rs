use std::collections::BTreeSet;

use ab_bridge::avatar_focus_observer::{
    focus_observer_plan_json, FocusAttemptOutcome, FocusObserverContext, FocusObserverDecisionKind,
    FocusObserverPolicy, FocusObserverReason, FocusObserverState, FocusObserverStateError,
    FocusObserverTerminalReason, FocusTargetIdentity, DEFAULT_COOLDOWN_SECS, DEFAULT_DURATION_MS,
    DEFAULT_DWELL_MS, DEFAULT_FAILURE_BACKOFF_SECS, DEFAULT_MAX_ATTEMPTS, DEFAULT_MAX_TRAVEL_PX,
    DEFAULT_MIN_TRAVEL_PX, DEFAULT_POLL_MS, DEFAULT_SENSITIVE_WAYLAND_APP_IDS,
    DEFAULT_SENSITIVE_XWAYLAND_CLASSES, FOCUS_OBSERVER_DECISION_SCHEMA, FOCUS_OBSERVER_PLAN_SCHEMA,
    FOCUS_OBSERVER_RECEIPT_SCHEMA,
};
use serde_json::json;

fn context(now_ms: u64, target_node_id: i64) -> FocusObserverContext {
    FocusObserverContext {
        observed_at_ms: now_ms,
        plan_actionable: true,
        target_node_id: Some(target_node_id),
        travel_px: Some(240),
        fullscreen: false,
        sensitive_mark: false,
        identity: FocusTargetIdentity::WaylandAppId("com.example.Editor".to_string()),
        acknowledged_target_node_id: None,
        paused: false,
        action_busy: false,
    }
}

fn state_with_baseline(policy: FocusObserverPolicy) -> FocusObserverState {
    let mut state = FocusObserverState::new(policy, 0);
    let first = state.observe(&context(0, 1));
    assert_eq!(first.kind, FocusObserverDecisionKind::Suppress);
    assert_eq!(first.reason, FocusObserverReason::InitialBaseline);
    state
}

fn stable_dispatch(
    state: &mut FocusObserverState,
    target_node_id: i64,
    first_seen_at_ms: u64,
) -> u64 {
    let first = state.observe(&context(first_seen_at_ms, target_node_id));
    assert_eq!(first.reason, FocusObserverReason::UnstableTarget);
    let ready_at_ms = first_seen_at_ms + state.policy().dwell_ms;
    let ready = state.observe(&context(ready_at_ms, target_node_id));
    assert_eq!(ready.kind, FocusObserverDecisionKind::Dispatch);
    assert_eq!(ready.reason, FocusObserverReason::StableFocusTransition);
    assert_eq!(ready.target_node_id, Some(target_node_id));
    ready_at_ms
}

#[test]
fn defaults_and_plan_are_bounded_reviewable_and_privacy_safe() {
    let mut policy = FocusObserverPolicy::default();
    assert_eq!(policy.duration_ms, DEFAULT_DURATION_MS);
    assert_eq!(policy.poll_ms, DEFAULT_POLL_MS);
    assert_eq!(policy.dwell_ms, DEFAULT_DWELL_MS);
    assert_eq!(policy.cooldown_secs, DEFAULT_COOLDOWN_SECS);
    assert_eq!(policy.failure_backoff_secs, DEFAULT_FAILURE_BACKOFF_SECS);
    assert_eq!(policy.min_travel_px, DEFAULT_MIN_TRAVEL_PX);
    assert_eq!(policy.max_travel_px, DEFAULT_MAX_TRAVEL_PX);
    assert_eq!(policy.max_attempts, DEFAULT_MAX_ATTEMPTS);
    for identity in DEFAULT_SENSITIVE_WAYLAND_APP_IDS {
        assert!(policy.sensitive_wayland_app_ids.contains(*identity));
    }
    for identity in DEFAULT_SENSITIVE_XWAYLAND_CLASSES {
        assert!(policy.sensitive_xwayland_classes.contains(*identity));
    }

    policy.duration_ms = 1;
    policy.poll_ms = 1;
    policy.dwell_ms = 1;
    policy.cooldown_secs = 1;
    policy.failure_backoff_secs = 0;
    policy.failure_backoff_max_secs = 0;
    policy.min_travel_px = 1;
    policy.max_travel_px = i64::MAX;
    policy.max_attempts = 99;
    policy
        .sensitive_wayland_app_ids
        .insert(" secret.window.identifier ".to_string());
    let plan = focus_observer_plan_json(&policy, true, true);
    assert_eq!(plan["schema"], FOCUS_OBSERVER_PLAN_SCHEMA);
    assert_eq!(plan["status"], "ready");
    assert_eq!(plan["ready"], true);
    assert_eq!(plan["bounds"]["duration_ms"], 1_000);
    assert_eq!(plan["bounds"]["poll_ms"], 250);
    assert_eq!(plan["bounds"]["dwell_ms"], 500);
    assert_eq!(plan["bounds"]["cooldown_secs"], 30);
    assert_eq!(plan["bounds"]["failure_backoff_secs"], 5);
    assert_eq!(plan["bounds"]["max_travel_px"], 2_048);
    assert_eq!(plan["bounds"]["max_attempts"], 3);
    assert_eq!(plan["effects"]["moves_pointer"], false);
    assert_eq!(plan["effects"]["changes_focus"], false);
    assert_eq!(plan["effects"]["emits_input"], false);
    assert_eq!(plan["effects"]["shows_prompt"], false);
    assert_eq!(plan["effects"]["emits_audio"], false);
    assert!(!plan.to_string().contains("secret.window.identifier"));

    let dry_run = focus_observer_plan_json(&FocusObserverPolicy::default(), false, true);
    assert_eq!(dry_run["status"], "dry_run");
    assert_eq!(dry_run["effects"]["moves_avatar_when_executing"], true);
    assert_eq!(dry_run["effects"]["moves_avatar_this_invocation"], false);
    let blocked = focus_observer_plan_json(&FocusObserverPolicy::default(), true, false);
    assert_eq!(blocked["status"], "blocked");
    assert_eq!(blocked["ready"], false);
}

#[test]
fn initial_focus_is_baseline_and_stable_new_focus_dispatches_after_dwell() {
    let mut state = state_with_baseline(FocusObserverPolicy::default());

    let early = state.observe(&context(1_000, 2));
    assert_eq!(early.reason, FocusObserverReason::UnstableTarget);
    assert_eq!(early.retry_after_ms, Some(2_000));
    let still_early = state.observe(&context(2_999, 2));
    assert_eq!(still_early.reason, FocusObserverReason::UnstableTarget);
    assert_eq!(still_early.retry_after_ms, Some(1));
    let ready = state.observe(&context(3_000, 2));
    assert_eq!(ready.kind, FocusObserverDecisionKind::Dispatch);
    assert_eq!(ready.target_node_id, Some(2));

    state.start_attempt(2).expect("start stable attempt");
    assert_eq!(state.attempt_count(), 1);
    assert_eq!(state.remaining_attempts(), 2);
    assert_eq!(
        state.start_attempt(2),
        Err(FocusObserverStateError::AttemptAlreadyInFlight)
    );
    state
        .finish_attempt(2, FocusAttemptOutcome::CompletedVerified, 3_100)
        .expect("finish verified attempt");

    let cooling = state.observe(&context(3_101, 3));
    assert_eq!(cooling.reason, FocusObserverReason::CooldownActive);
    assert_eq!(cooling.retry_after_ms, Some(299_999));
    let baseline_again = state.observe(&context(303_101, 1));
    assert_eq!(baseline_again.reason, FocusObserverReason::InitialBaseline);
}

#[test]
fn first_non_actionable_focus_is_still_the_session_baseline() {
    let mut state = FocusObserverState::new(FocusObserverPolicy::default(), 0);
    let mut first = context(0, 1);
    first.plan_actionable = false;
    assert_eq!(
        state.observe(&first).reason,
        FocusObserverReason::PlanNotActionable
    );

    assert_eq!(
        state.observe(&context(1_000, 2)).reason,
        FocusObserverReason::UnstableTarget
    );
    assert_eq!(
        state.observe(&context(3_000, 2)).kind,
        FocusObserverDecisionKind::Dispatch
    );
}

#[test]
fn focus_jitter_resets_dwell_and_never_dispatches_early() {
    let mut state = state_with_baseline(FocusObserverPolicy::default());
    assert_eq!(
        state.observe(&context(1_000, 2)).reason,
        FocusObserverReason::UnstableTarget
    );
    assert_eq!(
        state.observe(&context(2_000, 3)).reason,
        FocusObserverReason::UnstableTarget
    );
    assert_eq!(
        state.observe(&context(3_000, 2)).reason,
        FocusObserverReason::UnstableTarget
    );
    assert_eq!(
        state.observe(&context(4_999, 2)).reason,
        FocusObserverReason::UnstableTarget
    );
    assert_eq!(
        state.observe(&context(5_000, 2)).kind,
        FocusObserverDecisionKind::Dispatch
    );
}

#[test]
fn all_structural_suppression_gates_fail_closed() {
    let policy = FocusObserverPolicy {
        sensitive_wayland_app_ids: BTreeSet::from(["org.example.Secret".to_string()]),
        sensitive_xwayland_classes: BTreeSet::from(["LegacySecret".to_string()]),
        ..FocusObserverPolicy::default()
    };

    let cases = [
        (
            {
                let mut value = context(1_000, 2);
                value.plan_actionable = false;
                value
            },
            FocusObserverReason::PlanNotActionable,
        ),
        (
            {
                let mut value = context(1_000, 2);
                value.target_node_id = None;
                value
            },
            FocusObserverReason::FocusTargetMissing,
        ),
        (
            {
                let mut value = context(1_000, 2);
                value.fullscreen = true;
                value
            },
            FocusObserverReason::FullscreenTarget,
        ),
        (
            {
                let mut value = context(1_000, 2);
                value.sensitive_mark = true;
                value
            },
            FocusObserverReason::SensitiveTarget,
        ),
        (
            {
                let mut value = context(1_000, 2);
                value.identity = FocusTargetIdentity::Missing;
                value
            },
            FocusObserverReason::TargetIdentityUnknown,
        ),
        (
            {
                let mut value = context(1_000, 2);
                value.identity =
                    FocusTargetIdentity::WaylandAppId("org.example.Secret".to_string());
                value
            },
            FocusObserverReason::SensitiveTarget,
        ),
        (
            {
                let mut value = context(1_000, 2);
                value.identity = FocusTargetIdentity::XwaylandClass("LegacySecret".to_string());
                value
            },
            FocusObserverReason::SensitiveTarget,
        ),
        (
            {
                let mut value = context(1_000, 2);
                value.acknowledged_target_node_id = Some(2);
                value
            },
            FocusObserverReason::AcknowledgedTarget,
        ),
        (
            {
                let mut value = context(1_000, 2);
                value.travel_px = Some(95);
                value
            },
            FocusObserverReason::BelowMinTravel,
        ),
        (
            {
                let mut value = context(1_000, 2);
                value.travel_px = Some(901);
                value
            },
            FocusObserverReason::AboveMaxTravel,
        ),
        (
            {
                let mut value = context(1_000, 2);
                value.paused = true;
                value
            },
            FocusObserverReason::Paused,
        ),
        (
            {
                let mut value = context(1_000, 2);
                value.action_busy = true;
                value
            },
            FocusObserverReason::ActionInProgress,
        ),
    ];

    for (sample, expected) in cases {
        let mut state = state_with_baseline(policy.clone());
        let decision = state.observe(&sample);
        assert_eq!(decision.kind, FocusObserverDecisionKind::Suppress);
        assert_eq!(decision.reason, expected);
        assert!(decision.target_node_id.is_none() || decision.target_node_id == Some(2));
    }
}

#[test]
fn failed_attempt_uses_backoff_cooldown_and_one_target_one_attempt() {
    let mut state = state_with_baseline(FocusObserverPolicy::default());
    let ready_at = stable_dispatch(&mut state, 2, 1_000);
    state.start_attempt(2).expect("start failed attempt");
    state
        .finish_attempt(2, FocusAttemptOutcome::Failed, ready_at + 100)
        .expect("record failed attempt");
    assert_eq!(state.backoff_remaining_ms(ready_at + 100), 30_000);

    let backed_off = state.observe(&context(ready_at + 101, 3));
    assert_eq!(backed_off.reason, FocusObserverReason::FailureBackoffActive);
    assert_eq!(backed_off.retry_after_ms, Some(29_999));
    let cooling = state.observe(&context(ready_at + 30_100, 3));
    assert_eq!(cooling.reason, FocusObserverReason::CooldownActive);

    let after_cooldown = ready_at + 300_101;
    let attempted_again = state.observe(&context(after_cooldown, 2));
    assert_eq!(
        attempted_again.reason,
        FocusObserverReason::AlreadyAttempted
    );

    assert_eq!(
        state.finish_attempt(99, FocusAttemptOutcome::Cancelled, after_cooldown),
        Err(FocusObserverStateError::AttemptTargetMismatch)
    );
}

#[test]
fn proven_unstarted_dispatch_releases_budget_and_requires_fresh_dwell() {
    let mut state = state_with_baseline(FocusObserverPolicy::default());
    let ready_at = stable_dispatch(&mut state, 2, 1_000);
    state.start_attempt(2).expect("reserve dispatch");
    state
        .discard_unstarted_attempt(2)
        .expect("release proven unstarted dispatch");
    assert_eq!(state.attempt_count(), 0);
    assert_eq!(state.remaining_attempts(), 3);
    assert_eq!(
        state.observe(&context(ready_at + 1, 2)).reason,
        FocusObserverReason::UnstableTarget
    );
}

#[test]
fn validated_prior_ack_can_seed_only_bounded_cross_run_cooldown() {
    let mut state = state_with_baseline(FocusObserverPolicy::default());
    state.seed_cooldown_remaining(1_000, u64::MAX);
    let cooling = state.observe(&context(2_000, 2));
    assert_eq!(cooling.reason, FocusObserverReason::CooldownActive);
    assert_eq!(cooling.retry_after_ms, Some(299_000));
}

#[test]
fn observation_failures_back_off_exponentially_without_raw_errors() {
    let mut state = state_with_baseline(FocusObserverPolicy::default());
    let first = state.record_observation_failure(1_000);
    assert_eq!(first.reason, FocusObserverReason::ObservationReadFailed);
    assert_eq!(first.retry_after_ms, Some(30_000));
    assert_eq!(state.backoff_remaining_ms(1_001), 29_999);

    let second = state.record_observation_failure(2_000);
    assert_eq!(second.reason, FocusObserverReason::ObservationReadFailed);
    assert_eq!(second.retry_after_ms, Some(60_000));
    assert_eq!(state.backoff_remaining_ms(2_000), 60_000);
    assert!(!second.privacy_json().to_string().contains("error"));
}

#[test]
fn successful_observation_resets_only_sensor_failure_exponent() {
    let mut state = FocusObserverState::new(FocusObserverPolicy::default(), 0);
    let first = state.record_observation_failure(0);
    assert_eq!(first.retry_after_ms, Some(30_000));
    state.record_observation_success();
    let later = state.record_observation_failure(60_000);
    assert_eq!(later.retry_after_ms, Some(30_000));
}

#[test]
fn prestart_runtime_failures_have_distinct_truth_and_backoff() {
    let mut state = FocusObserverState::new(FocusObserverPolicy::default(), 0);
    let first = state.record_prestart_runtime_failure(1_000);
    assert_eq!(first.reason, FocusObserverReason::PrestartRuntimeFailed);
    assert_eq!(first.retry_after_ms, Some(30_000));
    let receipt = state.receipt_json(1_000);
    assert_eq!(receipt["tree_read_failure_count"], 0);
    assert_eq!(receipt["prestart_runtime_failure_count"], 1);
    assert_eq!(receipt["suppressed"]["prestart_runtime_failed"], 1);
    assert_eq!(receipt["suppressed"]["observation_read_failed"], 0);

    state.record_prestart_runtime_success();
    let later = state.record_prestart_runtime_failure(60_000);
    assert_eq!(later.retry_after_ms, Some(30_000));
}

#[test]
fn budget_and_duration_are_terminal_and_receipt_counts_outcomes() {
    let policy = FocusObserverPolicy {
        max_attempts: 1,
        ..FocusObserverPolicy::default()
    };
    let mut state = state_with_baseline(policy);
    let ready_at = stable_dispatch(&mut state, 2, 1_000);
    state.start_attempt(2).expect("start only attempt");
    state
        .finish_attempt(2, FocusAttemptOutcome::Cancelled, ready_at + 1)
        .expect("finish cancelled attempt");
    let stopped = state.observe(&context(ready_at + 2, 3));
    assert_eq!(stopped.kind, FocusObserverDecisionKind::Stop);
    assert_eq!(stopped.reason, FocusObserverReason::BudgetExhausted);
    assert_eq!(
        state.terminal_reason(),
        Some(FocusObserverTerminalReason::BudgetExhausted)
    );

    let receipt = state.receipt_json(999_999);
    assert_eq!(receipt["schema"], FOCUS_OBSERVER_RECEIPT_SCHEMA);
    assert_eq!(receipt["status"], "completed");
    assert_eq!(receipt["terminal_reason"], "budget_exhausted");
    assert_eq!(receipt["attempt_count"], 1);
    assert_eq!(receipt["completed_count"], 0);
    assert_eq!(receipt["cancelled_count"], 1);
    assert_eq!(receipt["failed_count"], 0);
    assert_eq!(receipt["effects"]["moves_pointer"], false);
    assert_eq!(receipt["effects"]["moves_avatar_when_executing"], true);

    let mut duration_state = FocusObserverState::new(FocusObserverPolicy::default(), 10);
    let duration = duration_state.policy().duration_ms;
    let expired = duration_state.observe(&context(10 + duration, 1));
    assert_eq!(expired.kind, FocusObserverDecisionKind::Stop);
    assert_eq!(expired.reason, FocusObserverReason::DurationElapsed);
}

#[test]
fn cancellation_and_fatal_runtime_stop_are_closed_terminal_reasons() {
    let mut cancelled = FocusObserverState::new(FocusObserverPolicy::default(), 100);
    let decision = cancelled.cancel(200);
    assert_eq!(decision.reason, FocusObserverReason::Cancelled);
    assert_eq!(cancelled.receipt_json(999)["elapsed_ms"], 100);
    assert_eq!(cancelled.receipt_json(999)["status"], "cancelled");

    let mut failed = FocusObserverState::new(FocusObserverPolicy::default(), 100);
    let decision = failed.fail_runtime(250);
    assert_eq!(decision.reason, FocusObserverReason::FatalRuntimeError);
    assert_eq!(failed.receipt_json(999)["status"], "failed");
    assert_eq!(
        failed.receipt_json(999)["terminal_reason"],
        "fatal_runtime_error"
    );
}

#[test]
fn json_context_denies_titles_and_projectors_never_emit_identity_or_target() {
    let fixture = json!({
        "observed_at_ms": 1000,
        "plan_actionable": true,
        "target_node_id": 42,
        "travel_px": 240,
        "fullscreen": false,
        "sensitive_mark": false,
        "identity": {"kind": "wayland_app_id", "value": "SECRET_APP_ID"},
        "acknowledged_target_node_id": null,
        "paused": false,
        "action_busy": false
    });
    let context: FocusObserverContext =
        serde_json::from_value(fixture.clone()).expect("typed context fixture");
    assert_eq!(context.target_node_id, Some(42));

    let mut with_title = fixture;
    with_title["title"] = json!("SECRET_TITLE_SHOULD_NEVER_ENTER_POLICY");
    assert!(serde_json::from_value::<FocusObserverContext>(with_title).is_err());

    let policy = FocusObserverPolicy {
        sensitive_wayland_app_ids: BTreeSet::from(["SECRET_APP_ID".to_string()]),
        ..FocusObserverPolicy::default()
    };
    let mut state = state_with_baseline(policy.clone());
    let decision = state.observe(&context);
    assert_eq!(decision.reason, FocusObserverReason::SensitiveTarget);
    let projected = decision.privacy_json();
    assert_eq!(projected["schema"], FOCUS_OBSERVER_DECISION_SCHEMA);
    assert!(!projected.to_string().contains("SECRET_APP_ID"));
    assert!(!projected.to_string().contains("42"));

    let plan = focus_observer_plan_json(&policy, true, true);
    let receipt = state.cancel(2_000);
    assert_eq!(receipt.kind, FocusObserverDecisionKind::Stop);
    let receipt = state.receipt_json(2_000);
    for output in [plan, projected, receipt] {
        let encoded = output.to_string();
        assert!(!encoded.contains("SECRET_APP_ID"));
        assert!(!encoded.contains("SECRET_TITLE"));
        assert!(!encoded.contains("com.example.Editor"));
    }
}
