//! Repeatable LSWR interaction-feedback runtime executor design preflight smoke.
//!
//! This consumes the checked-in interaction feedback fixture through the pure
//! semantic patch draft, patch execution preflight, and patch apply request
//! boundary, then emits a design-only runtime executor preflight. It never
//! queries live runtime state, submits apply requests, applies patches, ingests
//! outcomes, registers MCP tools, or writes memory/store rows.

use ab_bridge::lswr_interaction_feedback::{
    build_interaction_feedback_next_revision_plan, build_interaction_feedback_patch_apply_request,
    build_interaction_feedback_patch_execution_preflight,
    build_interaction_feedback_runtime_executor_design_preflight,
    build_interaction_feedback_semantic_patch_draft,
    render_interaction_feedback_runtime_executor_design_preflight,
    LSWR_INTERACTION_FEEDBACK_ARGUMENT_CONTEXT_SCHEMA,
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
    let preflight_input = if args.with_fixture_context {
        json!({
            "draft": draft,
            "argument_context": fixture_argument_context()
        })
    } else {
        draft
    };
    let preflight = build_interaction_feedback_patch_execution_preflight(&preflight_input);
    let apply_request = build_interaction_feedback_patch_apply_request(&preflight);
    let design_preflight =
        build_interaction_feedback_runtime_executor_design_preflight(&apply_request);
    let markdown = render_interaction_feedback_runtime_executor_design_preflight(&design_preflight);

    if args.assert_blocked_without_ready_apply_request {
        assert_blocked_without_ready_apply_request(&design_preflight)?;
    }
    if args.assert_ready_for_design_review {
        assert_ready_for_design_review(&design_preflight)?;
    }
    if args.assert_read_only {
        assert_read_only_contract(&design_preflight)?;
    }

    match args.format {
        OutputFormat::Markdown => println!("{markdown}"),
        OutputFormat::Json => println!("{}", serde_json::to_string_pretty(&design_preflight)?),
        OutputFormat::Both => {
            println!("{markdown}");
            println!("{}", serde_json::to_string_pretty(&design_preflight)?);
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

fn assert_blocked_without_ready_apply_request(preflight: &Value) -> Result<()> {
    if preflight
        .get("design_preflight_verdict")
        .and_then(Value::as_str)
        != Some("blocked")
    {
        bail!("runtime executor design preflight must block without a ready apply request");
    }
    if preflight.get("reason").and_then(Value::as_str) != Some("source_apply_request_not_ready") {
        bail!("runtime executor design preflight reason must require a ready apply request");
    }
    if preflight["executor_design_request"]
        .get("ready_for_design_review")
        .and_then(Value::as_bool)
        != Some(false)
    {
        bail!("blocked design preflight must not be ready for design review");
    }
    Ok(())
}

fn assert_ready_for_design_review(preflight: &Value) -> Result<()> {
    if preflight
        .get("design_preflight_verdict")
        .and_then(Value::as_str)
        != Some("ready_for_runtime_executor_design")
    {
        bail!("runtime executor design preflight must be ready for design review");
    }
    if preflight["source_apply_request_verdict"].as_str() != Some("ready_for_external_executor") {
        bail!("source apply request must be ready_for_external_executor");
    }
    if preflight["source_world_verdict"].as_str() != Some("not_verified") {
        bail!("source_world_verdict must remain not_verified");
    }
    if preflight["executor_design_request"]["design_request_id"].as_str()
        != Some("runtime_executor_design_arrival_bath_move_002")
    {
        bail!("design request id must derive from the apply request id");
    }
    if preflight["executor_design_request"]["patch"]["args"]["cell"] != json!([5, 2]) {
        bail!("design preflight must preserve the explicit patch args");
    }
    if preflight["executor_design_request"]["ready_for_live_runtime_lookup"].as_bool()
        != Some(false)
    {
        bail!("design preflight must not allow live runtime lookup");
    }
    if preflight["executor_design_request"]["ready_for_submission"].as_bool() != Some(false) {
        bail!("design preflight must not allow apply request submission");
    }
    if preflight["executor_design_request"]["ready_for_patch_application"].as_bool() != Some(false)
    {
        bail!("design preflight must not allow patch application");
    }
    Ok(())
}

fn assert_read_only_contract(preflight: &Value) -> Result<()> {
    for (key, expected) in [
        ("writes_state", false),
        ("store_access_required", false),
        ("mcp_tool_registered", false),
        ("implicit_live_runtime_lookup_attempted", false),
    ] {
        if preflight.get(key).and_then(Value::as_bool) != Some(expected) {
            bail!("runtime executor design preflight {key} must be {expected}");
        }
    }

    let guardrails = &preflight["guardrails"];
    for (key, expected) in [
        ("read_only", true),
        ("writes_state", false),
        ("store_access_required", false),
        ("mcp_tool_registered", false),
        ("queries_live_runtime", false),
        ("implicit_live_runtime_lookup_allowed", false),
        ("default_profile_exposure_allowed", false),
        ("submits_apply_request", false),
        ("outcome_ingestion_allowed", false),
        ("feedback_changes_world_verdict_allowed", false),
        ("applies_patch", false),
        ("runtime_executor_design_only", true),
    ] {
        if guardrails.get(key).and_then(Value::as_bool) != Some(expected) {
            bail!("guardrail {key} must be {expected}");
        }
    }
    if guardrails.get("mutation_surface").and_then(Value::as_str) != Some("none") {
        bail!("guardrail mutation_surface must be none");
    }

    let request = &preflight["executor_design_request"];
    for key in [
        "ready_for_live_runtime_lookup",
        "ready_for_submission",
        "ready_for_patch_application",
        "execution_performed",
        "outcome_ingestion_allowed_by_this_tool",
    ] {
        if request.get(key).and_then(Value::as_bool) != Some(false) {
            bail!("executor_design_request {key} must be false");
        }
    }

    let contract = &preflight["agent_action_contract"];
    for key in [
        "do_not_query_live_runtime",
        "do_not_submit_apply_request",
        "do_not_apply_patch",
        "do_not_ingest_outcome",
        "do_not_write_memory",
        "do_not_rewrite_world_verdict",
        "require_operator_gate_before_submission",
        "require_post_apply_verification_design",
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
    with_fixture_context: bool,
    assert_blocked_without_ready_apply_request: bool,
    assert_ready_for_design_review: bool,
    assert_read_only: bool,
}

impl Args {
    fn parse(raw_args: impl IntoIterator<Item = String>) -> Result<Self> {
        let mut format = OutputFormat::Markdown;
        let mut with_fixture_context = false;
        let mut assert_blocked_without_ready_apply_request = false;
        let mut assert_ready_for_design_review = false;
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
                "--with-fixture-context" => with_fixture_context = true,
                "--assert-blocked-without-ready-apply-request" => {
                    assert_blocked_without_ready_apply_request = true
                }
                "--assert-ready-for-design-review" => assert_ready_for_design_review = true,
                "--assert-read-only" => assert_read_only = true,
                "--help" | "-h" => bail!("{}", usage()),
                _ => bail!("unknown argument: {arg}\n\n{}", usage()),
            }
        }

        if assert_ready_for_design_review && !with_fixture_context {
            bail!("--assert-ready-for-design-review requires --with-fixture-context");
        }
        if assert_blocked_without_ready_apply_request && with_fixture_context {
            bail!(
                "--assert-blocked-without-ready-apply-request requires omitting --with-fixture-context"
            );
        }

        Ok(Self {
            format,
            with_fixture_context,
            assert_blocked_without_ready_apply_request,
            assert_ready_for_design_review,
            assert_read_only,
        })
    }
}

fn usage() -> &'static str {
    "usage: cargo run -p ab-bridge --example lswr_interaction_feedback_runtime_executor_design_preflight_smoke -- [--with-fixture-context] [--format markdown|json|both] [--assert-blocked-without-ready-apply-request] [--assert-ready-for-design-review] [--assert-read-only]"
}
