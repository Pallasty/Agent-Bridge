//! Repeatable LSWR interaction-feedback G2 operator submission token preflight smoke.
//!
//! This consumes the checked-in interaction feedback fixture through the pure
//! G1 live lookup preflight, then validates an explicit operator decision. It
//! emits a scoped token candidate for G3 review, but never submits apply
//! requests, applies patches, verifies post-apply results, ingests outcomes,
//! registers MCP tools, persists tokens, or writes memory/store rows.

use ab_bridge::lswr_interaction_feedback::{
    build_interaction_feedback_next_revision_plan, build_interaction_feedback_patch_apply_request,
    build_interaction_feedback_patch_execution_preflight,
    build_interaction_feedback_runtime_executor_design_preflight,
    build_interaction_feedback_runtime_executor_live_lookup_preflight,
    build_interaction_feedback_runtime_executor_operator_submission_token_preflight,
    build_interaction_feedback_semantic_patch_draft,
    render_interaction_feedback_runtime_executor_operator_submission_token_preflight,
    LSWR_INTERACTION_FEEDBACK_ARGUMENT_CONTEXT_SCHEMA,
    LSWR_RUNTIME_EXECUTOR_LIVE_LOOKUP_SNAPSHOT_SCHEMA,
    LSWR_RUNTIME_EXECUTOR_OPERATOR_SUBMISSION_DECISION_SCHEMA,
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
    let submission_input = if args.with_operator_decision {
        json!({
            "lookup_preflight": lookup_preflight,
            "operator_decision": fixture_operator_decision()
        })
    } else {
        lookup_preflight
    };
    let submission_preflight =
        build_interaction_feedback_runtime_executor_operator_submission_token_preflight(
            &submission_input,
        );
    let markdown = render_interaction_feedback_runtime_executor_operator_submission_token_preflight(
        &submission_preflight,
    );

    if args.assert_blocked_without_operator_decision {
        assert_blocked_without_operator_decision(&submission_preflight)?;
    }
    if args.assert_ready_for_patch_application_gate_review {
        assert_ready_for_patch_application_gate_review(&submission_preflight)?;
    }
    if args.assert_read_only {
        assert_read_only_contract(&submission_preflight)?;
    }

    match args.format {
        OutputFormat::Markdown => println!("{markdown}"),
        OutputFormat::Json => println!("{}", serde_json::to_string_pretty(&submission_preflight)?),
        OutputFormat::Both => {
            println!("{markdown}");
            println!("{}", serde_json::to_string_pretty(&submission_preflight)?);
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

fn assert_blocked_without_operator_decision(preflight: &Value) -> Result<()> {
    if preflight
        .get("submission_token_preflight_verdict")
        .and_then(Value::as_str)
        != Some("blocked")
    {
        bail!("G2 operator submission preflight must block without an explicit operator decision");
    }
    if preflight.get("reason").and_then(Value::as_str)
        != Some("explicit_operator_submission_decision_required")
    {
        bail!("G2 preflight reason must require an explicit operator decision");
    }
    if preflight["operator_submission_token"]["ready_for_patch_application_gate_review"].as_bool()
        != Some(false)
    {
        bail!("blocked G2 preflight must not be ready for patch application gate review");
    }
    Ok(())
}

fn assert_ready_for_patch_application_gate_review(preflight: &Value) -> Result<()> {
    if preflight
        .get("submission_token_preflight_verdict")
        .and_then(Value::as_str)
        != Some("ready_for_patch_application_gate_review")
    {
        bail!("G2 operator submission preflight must be ready for patch application gate review");
    }
    if preflight["operator_submission_token"]["token_id"].as_str()
        != Some("submit_patch_arrival_bath_move_002")
    {
        bail!("operator submission token id must derive from the patch id");
    }
    if preflight["operator_submission_token"]["idempotency_key"].as_str()
        != Some(
            "patch_arrival_bath_move_002/runtime_gen_1284/operator_decision_arrival_bath_move_002",
        )
    {
        bail!("operator submission token must carry a scoped idempotency key");
    }
    if preflight["operator_submission_token"]["ready_for_executor_submission"].as_bool()
        != Some(false)
    {
        bail!("G2 preflight must not submit to the executor");
    }
    Ok(())
}

fn assert_read_only_contract(preflight: &Value) -> Result<()> {
    for (key, expected) in [
        ("writes_state", false),
        ("store_access_required", false),
        ("mcp_tool_registered", false),
        ("submission_performed_by_this_tool", false),
        ("apply_request_submitted_by_this_tool", false),
        ("patch_application_performed_by_this_tool", false),
    ] {
        if preflight.get(key).and_then(Value::as_bool) != Some(expected) {
            bail!("G2 operator submission preflight {key} must be {expected}");
        }
    }

    let guardrails = &preflight["guardrails"];
    for (key, expected) in [
        ("read_only", true),
        ("writes_state", false),
        ("store_access_required", false),
        ("mcp_tool_registered", false),
        ("requires_ready_live_lookup_preflight", true),
        ("requires_explicit_operator_decision", true),
        ("submits_apply_request", false),
        ("applies_patch", false),
        ("verifies_post_apply_result", false),
        ("outcome_ingestion_allowed", false),
        ("persists_submission_token", false),
    ] {
        if guardrails.get(key).and_then(Value::as_bool) != Some(expected) {
            bail!("guardrail {key} must be {expected}");
        }
    }
    if guardrails.get("mutation_surface").and_then(Value::as_str) != Some("none") {
        bail!("guardrail mutation_surface must be none");
    }

    let token = &preflight["operator_submission_token"];
    for key in [
        "submission_token_persisted",
        "ready_for_executor_submission",
        "apply_request_submitted",
        "patch_application_performed",
        "verification_performed",
        "outcome_ingestion_allowed",
    ] {
        if token.get(key).and_then(Value::as_bool) != Some(false) {
            bail!("operator_submission_token {key} must be false");
        }
    }

    let contract = &preflight["agent_action_contract"];
    for key in [
        "do_not_submit_apply_request",
        "do_not_apply_patch",
        "do_not_ingest_outcome",
        "do_not_write_memory",
        "do_not_rewrite_world_verdict",
        "do_not_verify_post_apply_result",
        "do_not_persist_submission_token",
        "require_patch_application_gate_after_submission_token",
        "require_post_apply_verification_after_application",
        "require_separate_outcome_ingestion_review",
    ] {
        if contract.get(key).and_then(Value::as_bool) != Some(true) {
            bail!("agent_action_contract {key} must be true");
        }
    }
    Ok(())
}

#[derive(Clone, Copy)]
enum OutputFormat {
    Markdown,
    Json,
    Both,
}

struct Args {
    with_operator_decision: bool,
    format: OutputFormat,
    assert_blocked_without_operator_decision: bool,
    assert_ready_for_patch_application_gate_review: bool,
    assert_read_only: bool,
}

impl Args {
    fn parse<I>(args: I) -> Result<Self>
    where
        I: IntoIterator<Item = String>,
    {
        let mut with_operator_decision = false;
        let mut format = OutputFormat::Markdown;
        let mut assert_blocked_without_operator_decision = false;
        let mut assert_ready_for_patch_application_gate_review = false;
        let mut assert_read_only = false;
        let mut iter = args.into_iter();
        while let Some(arg) = iter.next() {
            match arg.as_str() {
                "--with-operator-decision" => with_operator_decision = true,
                "--format" => {
                    let value = iter
                        .next()
                        .context("--format requires markdown|json|both")?;
                    format = match value.as_str() {
                        "markdown" => OutputFormat::Markdown,
                        "json" => OutputFormat::Json,
                        "both" => OutputFormat::Both,
                        other => bail!("unsupported format {other}"),
                    };
                }
                "--assert-blocked-without-operator-decision" => {
                    assert_blocked_without_operator_decision = true
                }
                "--assert-ready-for-patch-application-gate-review" => {
                    assert_ready_for_patch_application_gate_review = true
                }
                "--assert-read-only" => assert_read_only = true,
                "-h" | "--help" => {
                    println!("{}", usage());
                    std::process::exit(0);
                }
                other => bail!("unknown argument {other}\n{}", usage()),
            }
        }
        if assert_ready_for_patch_application_gate_review && !with_operator_decision {
            bail!("--assert-ready-for-patch-application-gate-review requires --with-operator-decision");
        }
        if assert_blocked_without_operator_decision && with_operator_decision {
            bail!("--assert-blocked-without-operator-decision cannot be used with --with-operator-decision");
        }
        Ok(Self {
            with_operator_decision,
            format,
            assert_blocked_without_operator_decision,
            assert_ready_for_patch_application_gate_review,
            assert_read_only,
        })
    }
}

fn usage() -> &'static str {
    "usage: cargo run -p ab-bridge --example lswr_interaction_feedback_runtime_executor_operator_submission_token_preflight_smoke -- [--with-operator-decision] [--format markdown|json|both] [--assert-blocked-without-operator-decision] [--assert-ready-for-patch-application-gate-review] [--assert-read-only]"
}
