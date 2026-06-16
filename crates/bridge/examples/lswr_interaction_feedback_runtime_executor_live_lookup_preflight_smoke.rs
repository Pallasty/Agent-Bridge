//! Repeatable LSWR interaction-feedback G1 live lookup preflight smoke.
//!
//! This consumes the checked-in interaction feedback fixture through the pure
//! runtime executor design preflight, then validates an explicit read-only
//! lookup snapshot. It never queries live runtime state itself, submits apply
//! requests, applies patches, verifies post-apply results, ingests outcomes,
//! registers MCP tools, or writes memory/store rows.

use ab_bridge::lswr_interaction_feedback::{
    build_interaction_feedback_next_revision_plan, build_interaction_feedback_patch_apply_request,
    build_interaction_feedback_patch_execution_preflight,
    build_interaction_feedback_runtime_executor_design_preflight,
    build_interaction_feedback_runtime_executor_live_lookup_preflight,
    build_interaction_feedback_semantic_patch_draft,
    render_interaction_feedback_runtime_executor_live_lookup_preflight,
    LSWR_INTERACTION_FEEDBACK_ARGUMENT_CONTEXT_SCHEMA,
    LSWR_RUNTIME_EXECUTOR_LIVE_LOOKUP_SNAPSHOT_SCHEMA,
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
    let lookup_input = if args.with_lookup_snapshot {
        json!({
            "design_preflight": design_preflight,
            "lookup_snapshot": fixture_lookup_snapshot()
        })
    } else {
        design_preflight
    };
    let lookup_preflight =
        build_interaction_feedback_runtime_executor_live_lookup_preflight(&lookup_input);
    let markdown =
        render_interaction_feedback_runtime_executor_live_lookup_preflight(&lookup_preflight);

    if args.assert_blocked_without_lookup_snapshot {
        assert_blocked_without_lookup_snapshot(&lookup_preflight)?;
    }
    if args.assert_ready_for_operator_submission_review {
        assert_ready_for_operator_submission_review(&lookup_preflight)?;
    }
    if args.assert_read_only {
        assert_read_only_contract(&lookup_preflight)?;
    }

    match args.format {
        OutputFormat::Markdown => println!("{markdown}"),
        OutputFormat::Json => println!("{}", serde_json::to_string_pretty(&lookup_preflight)?),
        OutputFormat::Both => {
            println!("{markdown}");
            println!("{}", serde_json::to_string_pretty(&lookup_preflight)?);
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

fn assert_blocked_without_lookup_snapshot(preflight: &Value) -> Result<()> {
    if preflight
        .get("lookup_preflight_verdict")
        .and_then(Value::as_str)
        != Some("blocked")
    {
        bail!("G1 live lookup preflight must block without an explicit lookup snapshot");
    }
    if preflight.get("reason").and_then(Value::as_str) != Some("explicit_lookup_snapshot_required")
    {
        bail!("G1 live lookup preflight reason must require an explicit lookup snapshot");
    }
    if preflight["lookup_evidence"]
        .get("ready_for_operator_submission_review")
        .and_then(Value::as_bool)
        != Some(false)
    {
        bail!("blocked G1 preflight must not be ready for operator submission review");
    }
    Ok(())
}

fn assert_ready_for_operator_submission_review(preflight: &Value) -> Result<()> {
    if preflight
        .get("lookup_preflight_verdict")
        .and_then(Value::as_str)
        != Some("ready_for_operator_submission_review")
    {
        bail!("G1 live lookup preflight must be ready for operator submission review");
    }
    if preflight["source_design_preflight_verdict"].as_str()
        != Some("ready_for_runtime_executor_design")
    {
        bail!("source design preflight must be ready_for_runtime_executor_design");
    }
    if preflight["source_world_verdict"].as_str() != Some("not_verified") {
        bail!("source_world_verdict must remain not_verified");
    }
    if preflight["lookup_evidence"]["lookup_evidence_id"].as_str()
        != Some("live_lookup_arrival_bath_move_002")
    {
        bail!("lookup evidence id must derive from the design request id");
    }
    if preflight["lookup_evidence"]["runtime_generation"].as_str() != Some("runtime_gen_1284") {
        bail!("lookup evidence must preserve runtime_generation");
    }
    if preflight["lookup_evidence"]["target_entities"] != json!(["bath"]) {
        bail!("lookup evidence must preserve target entities");
    }
    if preflight["lookup_evidence"]["ready_for_submission"].as_bool() != Some(false) {
        bail!("G1 live lookup preflight must not allow submission");
    }
    if preflight["lookup_evidence"]["ready_for_patch_application"].as_bool() != Some(false) {
        bail!("G1 live lookup preflight must not allow patch application");
    }
    Ok(())
}

fn assert_read_only_contract(preflight: &Value) -> Result<()> {
    for (key, expected) in [
        ("writes_state", false),
        ("store_access_required", false),
        ("mcp_tool_registered", false),
        ("implicit_live_runtime_lookup_attempted", false),
        ("lookup_performed_by_this_tool", false),
    ] {
        if preflight.get(key).and_then(Value::as_bool) != Some(expected) {
            bail!("G1 live lookup preflight {key} must be {expected}");
        }
    }

    let guardrails = &preflight["guardrails"];
    for (key, expected) in [
        ("read_only", true),
        ("writes_state", false),
        ("store_access_required", false),
        ("mcp_tool_registered", false),
        ("queries_live_runtime", false),
        ("requires_explicit_lookup_snapshot", true),
        ("lookup_performed_by_this_tool", false),
        ("implicit_live_runtime_lookup_allowed", false),
        ("default_profile_exposure_allowed", false),
        ("submits_apply_request", false),
        ("outcome_ingestion_allowed", false),
        ("feedback_changes_world_verdict_allowed", false),
        ("applies_patch", false),
        ("verifies_post_apply_result", false),
        ("runtime_executor_live_lookup_preflight_only", true),
    ] {
        if guardrails.get(key).and_then(Value::as_bool) != Some(expected) {
            bail!("guardrail {key} must be {expected}");
        }
    }
    if guardrails.get("mutation_surface").and_then(Value::as_str) != Some("none") {
        bail!("guardrail mutation_surface must be none");
    }

    let evidence = &preflight["lookup_evidence"];
    for key in [
        "ready_for_submission",
        "ready_for_patch_application",
        "mutation_performed",
        "verification_performed",
        "outcome_ingestion_allowed",
    ] {
        if evidence.get(key).and_then(Value::as_bool) != Some(false) {
            bail!("lookup_evidence {key} must be false");
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
        "require_operator_gate_before_submission",
        "require_patch_application_gate_after_submission",
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
    format: OutputFormat,
    with_lookup_snapshot: bool,
    assert_blocked_without_lookup_snapshot: bool,
    assert_ready_for_operator_submission_review: bool,
    assert_read_only: bool,
}

impl Args {
    fn parse(raw_args: impl IntoIterator<Item = String>) -> Result<Self> {
        let mut format = OutputFormat::Markdown;
        let mut with_lookup_snapshot = false;
        let mut assert_blocked_without_lookup_snapshot = false;
        let mut assert_ready_for_operator_submission_review = false;
        let mut assert_read_only = false;
        let mut iter = raw_args.into_iter();
        while let Some(arg) = iter.next() {
            match arg.as_str() {
                "--format" => {
                    let value = iter.next().ok_or_else(|| {
                        anyhow::anyhow!("--format requires markdown, json, or both")
                    })?;
                    format = match value.as_str() {
                        "markdown" => OutputFormat::Markdown,
                        "json" => OutputFormat::Json,
                        "both" => OutputFormat::Both,
                        _ => bail!("unknown --format value: {value}\n\n{}", usage()),
                    };
                }
                "--with-lookup-snapshot" => with_lookup_snapshot = true,
                "--assert-blocked-without-lookup-snapshot" => {
                    assert_blocked_without_lookup_snapshot = true
                }
                "--assert-ready-for-operator-submission-review" => {
                    assert_ready_for_operator_submission_review = true
                }
                "--assert-read-only" => assert_read_only = true,
                "--help" | "-h" => bail!("{}", usage()),
                _ => bail!("unknown argument: {arg}\n\n{}", usage()),
            }
        }

        if assert_ready_for_operator_submission_review && !with_lookup_snapshot {
            bail!("--assert-ready-for-operator-submission-review requires --with-lookup-snapshot");
        }
        if assert_blocked_without_lookup_snapshot && with_lookup_snapshot {
            bail!(
                "--assert-blocked-without-lookup-snapshot requires omitting --with-lookup-snapshot"
            );
        }

        Ok(Self {
            format,
            with_lookup_snapshot,
            assert_blocked_without_lookup_snapshot,
            assert_ready_for_operator_submission_review,
            assert_read_only,
        })
    }
}

fn usage() -> &'static str {
    "usage: cargo run -p ab-bridge --example lswr_interaction_feedback_runtime_executor_live_lookup_preflight_smoke -- [--with-lookup-snapshot] [--format markdown|json|both] [--assert-blocked-without-lookup-snapshot] [--assert-ready-for-operator-submission-review] [--assert-read-only]"
}
