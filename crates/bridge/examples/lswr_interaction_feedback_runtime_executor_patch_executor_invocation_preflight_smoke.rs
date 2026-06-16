//! Repeatable LSWR interaction-feedback G4 patch executor invocation preflight smoke.
//!
//! This consumes the checked-in interaction feedback fixture through the pure
//! G3 patch application gate preflight, then validates an explicit patch
//! executor invocation decision. It emits a reviewable invocation request
//! envelope, but never invokes the executor, submits queue work, submits apply
//! requests, applies patches, verifies post-apply results, ingests outcomes,
//! registers MCP tools, or writes memory/store rows.

use ab_bridge::lswr_interaction_feedback::{
    build_interaction_feedback_next_revision_plan, build_interaction_feedback_patch_apply_request,
    build_interaction_feedback_patch_execution_preflight,
    build_interaction_feedback_runtime_executor_design_preflight,
    build_interaction_feedback_runtime_executor_live_lookup_preflight,
    build_interaction_feedback_runtime_executor_operator_submission_token_preflight,
    build_interaction_feedback_runtime_executor_patch_application_gate_preflight,
    build_interaction_feedback_runtime_executor_patch_executor_invocation_preflight,
    build_interaction_feedback_semantic_patch_draft,
    render_interaction_feedback_runtime_executor_patch_executor_invocation_preflight,
    LSWR_INTERACTION_FEEDBACK_ARGUMENT_CONTEXT_SCHEMA,
    LSWR_RUNTIME_EXECUTOR_LIVE_LOOKUP_SNAPSHOT_SCHEMA,
    LSWR_RUNTIME_EXECUTOR_OPERATOR_SUBMISSION_DECISION_SCHEMA,
    LSWR_RUNTIME_EXECUTOR_PATCH_APPLICATION_GATE_DECISION_SCHEMA,
    LSWR_RUNTIME_EXECUTOR_PATCH_EXECUTOR_INVOCATION_DECISION_SCHEMA,
};
use anyhow::{bail, Context, Result};
use serde_json::{json, Value};

const FIXTURE_JSON: &str =
    include_str!("../tests/fixtures/lswr_interaction_feedback_fixture_v0.json");

fn main() -> Result<()> {
    let args = Args::parse(std::env::args().skip(1))?;
    let fixture: Value =
        serde_json::from_str(FIXTURE_JSON).context("parse interaction feedback fixture JSON")?;
    let plan = build_interaction_feedback_next_revision_plan(&fixture);
    let draft = build_interaction_feedback_semantic_patch_draft(&plan);
    let preflight = build_interaction_feedback_patch_execution_preflight(&json!({
        "draft": draft,
        "argument_context": fixture_argument_context()
    }));
    let apply_request = build_interaction_feedback_patch_apply_request(&preflight);
    let design_preflight =
        build_interaction_feedback_runtime_executor_design_preflight(&apply_request);
    let lookup_preflight =
        build_interaction_feedback_runtime_executor_live_lookup_preflight(&json!({
            "design_preflight": design_preflight,
            "lookup_snapshot": fixture_lookup_snapshot()
        }));
    let submission_preflight =
        build_interaction_feedback_runtime_executor_operator_submission_token_preflight(&json!({
            "lookup_preflight": lookup_preflight,
            "operator_decision": fixture_operator_decision()
        }));
    let gate_preflight =
        build_interaction_feedback_runtime_executor_patch_application_gate_preflight(&json!({
            "submission_token_preflight": submission_preflight,
            "patch_application_gate_decision": fixture_patch_application_gate_decision()
        }));
    let invocation_input = if args.with_patch_executor_invocation_decision {
        json!({
            "patch_application_gate_preflight": gate_preflight,
            "patch_executor_invocation_decision": fixture_patch_executor_invocation_decision()
        })
    } else {
        gate_preflight
    };
    let invocation_preflight =
        build_interaction_feedback_runtime_executor_patch_executor_invocation_preflight(
            &invocation_input,
        );
    let markdown = render_interaction_feedback_runtime_executor_patch_executor_invocation_preflight(
        &invocation_preflight,
    );

    if args.assert_blocked_without_patch_executor_invocation_decision {
        assert_blocked_without_patch_executor_invocation_decision(&invocation_preflight)?;
    }
    if args.assert_ready_for_separate_patch_executor_invocation_request {
        assert_ready_for_separate_patch_executor_invocation_request(&invocation_preflight)?;
    }
    if args.assert_read_only {
        assert_read_only_contract(&invocation_preflight)?;
    }

    match args.format {
        OutputFormat::Markdown => println!("{markdown}"),
        OutputFormat::Json => println!("{}", serde_json::to_string_pretty(&invocation_preflight)?),
        OutputFormat::Both => {
            println!("{markdown}");
            println!("{}", serde_json::to_string_pretty(&invocation_preflight)?);
        }
    }

    Ok(())
}

fn fixture_argument_context() -> Value {
    json!({
        "schema": LSWR_INTERACTION_FEEDBACK_ARGUMENT_CONTEXT_SCHEMA,
        "world_id": "onsen_live_session",
        "branch_id": "main",
        "source": "explicit_fixture_context",
        "live_runtime_queried_by_preflight": false,
        "candidate_arguments": [{
            "argument_path": "patch.args.cell",
            "value": [5, 2],
            "satisfies_expected_effect": true,
            "evidence": {
                "walkway_clearance_cells": 2,
                "screen_area_after_estimate": 0.01,
                "source": "explicit_test_context"
            }
        }]
    })
}

fn fixture_lookup_snapshot() -> Value {
    json!({
        "schema": LSWR_RUNTIME_EXECUTOR_LIVE_LOOKUP_SNAPSHOT_SCHEMA,
        "runtime_family": "lswr",
        "world_id": "onsen_live_session",
        "branch_id": "main",
        "runtime_generation": "runtime_gen_1284",
        "tick": 1284,
        "lookup_read_only": true,
        "mutation_performed": false,
        "submission_performed": false,
        "application_performed": false,
        "verification_performed": false,
        "outcome_ingestion_allowed": false,
        "target_entities_present": true,
        "patch_target_still_valid": true,
        "entities_present": ["bath"],
        "entity_state": {
            "bath": {
                "entity_id": "bath",
                "space": "arrival_area",
                "cell": [4, 2],
                "visible": true
            }
        },
        "verification_ledger_cursor": "verify_patch_arrival_bath_move_001",
        "presentation_state": {
            "viewport": "onsen_live_root_viewport",
            "render_fresh": true,
            "selected_entities": ["bath"]
        }
    })
}

fn fixture_operator_decision() -> Value {
    json!({
        "schema": LSWR_RUNTIME_EXECUTOR_OPERATOR_SUBMISSION_DECISION_SCHEMA,
        "decision_id": "operator_decision_arrival_bath_move_002",
        "decision": "approved",
        "operator_id": "human:owner",
        "approved_at": "2026-06-16T06:30:00Z",
        "expires_at": "2026-06-16T23:59:59Z",
        "requested_authority": "operator_submission_token_only",
        "approved_scope": {
            "lookup_evidence_id": "live_lookup_arrival_bath_move_002",
            "world_id": "onsen_live_session",
            "branch_id": "main",
            "runtime_generation": "runtime_gen_1284",
            "patch_id": "patch_arrival_bath_move_002",
            "source_apply_request_id": "apply_request_arrival_bath_move_002"
        },
        "submission_performed": false,
        "apply_request_submitted": false,
        "patch_application_allowed": false,
        "verification_allowed": false,
        "outcome_ingestion_allowed": false,
        "writes_state": false
    })
}

fn fixture_patch_application_gate_decision() -> Value {
    json!({
        "schema": LSWR_RUNTIME_EXECUTOR_PATCH_APPLICATION_GATE_DECISION_SCHEMA,
        "decision_id": "patch_application_gate_decision_arrival_bath_move_002",
        "decision": "approved",
        "operator_id": "human:owner",
        "approved_at": "2026-06-16T07:00:00Z",
        "expires_at": "2026-06-16T23:59:59Z",
        "requested_authority": "patch_application_executor_invocation_gate_only",
        "approved_scope": {
            "token_id": "submit_patch_arrival_bath_move_002",
            "idempotency_key": "patch_arrival_bath_move_002/runtime_gen_1284/operator_decision_arrival_bath_move_002",
            "operator_submission_decision_id": "operator_decision_arrival_bath_move_002",
            "world_id": "onsen_live_session",
            "branch_id": "main",
            "runtime_generation": "runtime_gen_1284",
            "patch_id": "patch_arrival_bath_move_002",
            "source_apply_request_id": "apply_request_arrival_bath_move_002"
        },
        "separate_patch_executor_invocation_allowed": true,
        "executor_invocation_performed": false,
        "apply_request_submitted": false,
        "patch_application_performed": false,
        "verification_allowed": false,
        "outcome_ingestion_allowed": false,
        "writes_state": false
    })
}

fn fixture_patch_executor_invocation_decision() -> Value {
    json!({
        "schema": LSWR_RUNTIME_EXECUTOR_PATCH_EXECUTOR_INVOCATION_DECISION_SCHEMA,
        "decision_id": "patch_executor_invocation_decision_arrival_bath_move_002",
        "decision": "approved",
        "operator_id": "human:owner",
        "approved_at": "2026-06-16T07:30:00Z",
        "expires_at": "2026-06-16T23:59:59Z",
        "requested_authority": "separate_patch_executor_invocation_only",
        "approved_scope": {
            "gate_id": "patch_application_gate_arrival_bath_move_002",
            "gate_decision_id": "patch_application_gate_decision_arrival_bath_move_002",
            "gate_idempotency_key": "patch_arrival_bath_move_002/runtime_gen_1284/submit_patch_arrival_bath_move_002/patch_application_gate_decision_arrival_bath_move_002",
            "operator_submission_token_id": "submit_patch_arrival_bath_move_002",
            "world_id": "onsen_live_session",
            "branch_id": "main",
            "runtime_generation": "runtime_gen_1284",
            "patch_id": "patch_arrival_bath_move_002",
            "source_apply_request_id": "apply_request_arrival_bath_move_002"
        },
        "separate_patch_executor_invocation_allowed": true,
        "executor_invocation_performed": false,
        "executor_queue_submission_performed": false,
        "apply_request_submitted": false,
        "patch_application_performed": false,
        "verification_allowed": false,
        "outcome_ingestion_allowed": false,
        "writes_state": false
    })
}

fn assert_blocked_without_patch_executor_invocation_decision(preflight: &Value) -> Result<()> {
    if preflight
        .get("patch_executor_invocation_preflight_verdict")
        .and_then(Value::as_str)
        != Some("blocked")
    {
        bail!("G4 patch executor invocation preflight must block without an explicit decision");
    }
    if preflight.get("reason").and_then(Value::as_str)
        != Some("explicit_patch_executor_invocation_decision_required")
    {
        bail!("G4 preflight reason must require an explicit patch executor invocation decision");
    }
    if preflight["patch_executor_invocation_request"]
        ["ready_for_separate_patch_executor_invocation_request"]
        .as_bool()
        != Some(false)
    {
        bail!("blocked G4 preflight must not be ready for an invocation request");
    }
    Ok(())
}

fn assert_ready_for_separate_patch_executor_invocation_request(preflight: &Value) -> Result<()> {
    if preflight
        .get("patch_executor_invocation_preflight_verdict")
        .and_then(Value::as_str)
        != Some("ready_for_separate_patch_executor_invocation_request")
    {
        bail!("G4 patch executor invocation preflight must be ready for invocation request");
    }
    if preflight["patch_executor_invocation_request"]["request_id"].as_str()
        != Some("patch_executor_invocation_arrival_bath_move_002")
    {
        bail!("patch executor invocation request id must derive from the patch id");
    }
    if preflight["patch_executor_invocation_request"]["invocation_request_emitted_by_this_tool"]
        .as_bool()
        != Some(true)
    {
        bail!("ready G4 preflight must emit a reviewable invocation request envelope");
    }
    if preflight["patch_executor_invocation_request"]["executor_invocation_performed_by_this_tool"]
        .as_bool()
        != Some(false)
    {
        bail!("G4 preflight must not invoke the executor");
    }
    Ok(())
}

fn assert_read_only_contract(preflight: &Value) -> Result<()> {
    for key in [
        "executor_invocation_performed_by_this_tool",
        "executor_queue_submission_performed_by_this_tool",
        "apply_request_submitted_by_this_tool",
        "patch_application_performed_by_this_tool",
        "writes_state",
        "store_access_required",
        "mcp_tool_registered",
    ] {
        if preflight.get(key).and_then(Value::as_bool) != Some(false) {
            bail!("G4 patch executor invocation preflight {key} must be false");
        }
    }
    for key in [
        "executor_invocation_performed_by_this_tool",
        "executor_queue_submission_performed",
        "apply_request_submitted",
        "patch_application_performed",
        "verification_performed",
        "outcome_ingestion_allowed",
    ] {
        if preflight["patch_executor_invocation_request"]
            .get(key)
            .and_then(Value::as_bool)
            != Some(false)
        {
            bail!("G4 patch executor invocation request {key} must be false");
        }
    }
    for key in [
        "invokes_patch_executor",
        "submits_executor_queue",
        "submits_apply_request",
        "applies_patch",
        "verifies_post_apply_result",
        "outcome_ingestion_allowed",
    ] {
        if preflight["guardrails"].get(key).and_then(Value::as_bool) != Some(false) {
            bail!("G4 guardrail {key} must be false");
        }
    }
    Ok(())
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
enum OutputFormat {
    Markdown,
    Json,
    Both,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
struct Args {
    with_patch_executor_invocation_decision: bool,
    assert_blocked_without_patch_executor_invocation_decision: bool,
    assert_ready_for_separate_patch_executor_invocation_request: bool,
    assert_read_only: bool,
    format: OutputFormat,
}

impl Args {
    fn parse(args: impl IntoIterator<Item = String>) -> Result<Self> {
        let mut with_patch_executor_invocation_decision = false;
        let mut assert_blocked_without_patch_executor_invocation_decision = false;
        let mut assert_ready_for_separate_patch_executor_invocation_request = false;
        let mut assert_read_only = false;
        let mut format = OutputFormat::Markdown;
        let mut iter = args.into_iter();

        while let Some(arg) = iter.next() {
            match arg.as_str() {
                "--with-patch-executor-invocation-decision" => {
                    with_patch_executor_invocation_decision = true
                }
                "--assert-blocked-without-patch-executor-invocation-decision" => {
                    assert_blocked_without_patch_executor_invocation_decision = true
                }
                "--assert-ready-for-separate-patch-executor-invocation-request" => {
                    assert_ready_for_separate_patch_executor_invocation_request = true
                }
                "--assert-read-only" => assert_read_only = true,
                "--format" => {
                    let value = iter
                        .next()
                        .context("--format requires markdown|json|both")?;
                    format = match value.as_str() {
                        "markdown" => OutputFormat::Markdown,
                        "json" => OutputFormat::Json,
                        "both" => OutputFormat::Both,
                        other => bail!("unsupported --format value: {other}"),
                    };
                }
                "-h" | "--help" => bail!(usage()),
                other => bail!("unknown argument: {other}\n{}", usage()),
            }
        }

        if assert_blocked_without_patch_executor_invocation_decision
            && with_patch_executor_invocation_decision
        {
            bail!(
                "--assert-blocked-without-patch-executor-invocation-decision cannot be combined with --with-patch-executor-invocation-decision"
            );
        }
        if assert_ready_for_separate_patch_executor_invocation_request
            && !with_patch_executor_invocation_decision
        {
            bail!(
                "--assert-ready-for-separate-patch-executor-invocation-request requires --with-patch-executor-invocation-decision"
            );
        }

        Ok(Self {
            with_patch_executor_invocation_decision,
            assert_blocked_without_patch_executor_invocation_decision,
            assert_ready_for_separate_patch_executor_invocation_request,
            assert_read_only,
            format,
        })
    }
}

fn usage() -> &'static str {
    "usage: cargo run -p ab-bridge --example lswr_interaction_feedback_runtime_executor_patch_executor_invocation_preflight_smoke -- [--with-patch-executor-invocation-decision] [--format markdown|json|both] [--assert-blocked-without-patch-executor-invocation-decision] [--assert-ready-for-separate-patch-executor-invocation-request] [--assert-read-only]"
}
