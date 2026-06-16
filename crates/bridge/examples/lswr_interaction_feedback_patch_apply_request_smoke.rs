//! Repeatable LSWR interaction-feedback patch apply request boundary smoke.
//!
//! This consumes the checked-in interaction feedback fixture through the pure
//! semantic patch draft and patch execution preflight, then emits an external
//! executor request envelope. It never submits the request, applies patches,
//! registers MCP tools, ingests outcomes, queries live runtime state, or writes
//! memory/store rows.

use ab_bridge::lswr_interaction_feedback::{
    build_interaction_feedback_next_revision_plan, build_interaction_feedback_patch_apply_request,
    build_interaction_feedback_patch_execution_preflight,
    build_interaction_feedback_semantic_patch_draft,
    render_interaction_feedback_patch_apply_request,
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
    let request = build_interaction_feedback_patch_apply_request(&preflight);
    let markdown = render_interaction_feedback_patch_apply_request(&request);

    if args.assert_blocked_without_ready_preflight {
        assert_blocked_without_ready_preflight(&request)?;
    }
    if args.assert_ready_with_context {
        assert_ready_with_context(&request)?;
    }
    if args.assert_read_only {
        assert_read_only_contract(&request)?;
    }

    match args.format {
        OutputFormat::Markdown => println!("{markdown}"),
        OutputFormat::Json => println!("{}", serde_json::to_string_pretty(&request)?),
        OutputFormat::Both => {
            println!("{markdown}");
            println!("{}", serde_json::to_string_pretty(&request)?);
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

fn assert_blocked_without_ready_preflight(request: &Value) -> Result<()> {
    if request.get("apply_request_verdict").and_then(Value::as_str) != Some("blocked") {
        bail!("apply request must be blocked without a ready preflight");
    }
    if request.get("reason").and_then(Value::as_str) != Some("source_preflight_not_ready") {
        bail!("apply request reason must require a ready preflight");
    }
    if request["apply_request"]
        .get("ready_for_external_submission")
        .and_then(Value::as_bool)
        != Some(false)
    {
        bail!("apply request must not be externally submittable without ready preflight");
    }
    Ok(())
}

fn assert_ready_with_context(request: &Value) -> Result<()> {
    if request.get("apply_request_verdict").and_then(Value::as_str)
        != Some("ready_for_external_executor")
    {
        bail!("apply request must be ready_for_external_executor with explicit context");
    }
    if request["source_world_verdict"].as_str() != Some("not_verified") {
        bail!("source_world_verdict must remain not_verified");
    }
    if request["apply_request"]["patch"]["args"]["cell"] != json!([5, 2]) {
        bail!("apply request patch args.cell must come from explicit argument context");
    }
    if request["apply_request"]["patch"]["required_citations"]
        != json!([
            "verify_patch_arrival_bath_move_001",
            "fb_arrival_crowded_001"
        ])
    {
        bail!("apply request must preserve required citations");
    }
    if request["apply_request"]
        .get("submitted_by_this_tool")
        .and_then(Value::as_bool)
        != Some(false)
    {
        bail!("apply request boundary must not submit the patch");
    }
    Ok(())
}

fn assert_read_only_contract(request: &Value) -> Result<()> {
    for (key, expected) in [
        ("writes_state", false),
        ("store_access_required", false),
        ("mcp_tool_registered", false),
        ("implicit_live_runtime_lookup_attempted", false),
    ] {
        if request.get(key).and_then(Value::as_bool) != Some(expected) {
            bail!("apply request boundary {key} must be {expected}");
        }
    }

    let guardrails = &request["guardrails"];
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
    ] {
        if guardrails.get(key).and_then(Value::as_bool) != Some(expected) {
            bail!("guardrail {key} must be {expected}");
        }
    }
    if guardrails.get("mutation_surface").and_then(Value::as_str) != Some("none") {
        bail!("guardrail mutation_surface must be none");
    }

    let apply_request = &request["apply_request"];
    for key in [
        "apply_performed",
        "submitted_by_this_tool",
        "outcome_ingestion_allowed_by_this_tool",
    ] {
        if apply_request.get(key).and_then(Value::as_bool) != Some(false) {
            bail!("apply_request {key} must be false");
        }
    }

    let contract = &request["agent_action_contract"];
    for key in [
        "do_not_apply_patch",
        "do_not_submit_patch_from_this_tool",
        "do_not_ingest_outcome",
        "do_not_write_memory",
        "do_not_query_live_runtime",
        "do_not_rewrite_world_verdict",
        "external_executor_required",
        "preserve_required_citations",
        "require_post_apply_verification",
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
    assert_blocked_without_ready_preflight: bool,
    assert_ready_with_context: bool,
    assert_read_only: bool,
}

impl Args {
    fn parse(raw_args: impl IntoIterator<Item = String>) -> Result<Self> {
        let mut format = OutputFormat::Markdown;
        let mut with_fixture_context = false;
        let mut assert_blocked_without_ready_preflight = false;
        let mut assert_ready_with_context = false;
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
                "--assert-blocked-without-ready-preflight" => {
                    assert_blocked_without_ready_preflight = true
                }
                "--assert-ready-with-context" => assert_ready_with_context = true,
                "--assert-read-only" => assert_read_only = true,
                "--help" | "-h" => bail!("{}", usage()),
                _ => bail!("unknown argument: {arg}\n\n{}", usage()),
            }
        }

        if assert_ready_with_context && !with_fixture_context {
            bail!("--assert-ready-with-context requires --with-fixture-context");
        }
        if assert_blocked_without_ready_preflight && with_fixture_context {
            bail!(
                "--assert-blocked-without-ready-preflight requires omitting --with-fixture-context"
            );
        }

        Ok(Self {
            format,
            with_fixture_context,
            assert_blocked_without_ready_preflight,
            assert_ready_with_context,
            assert_read_only,
        })
    }
}

fn usage() -> &'static str {
    "usage: cargo run -p ab-bridge --example lswr_interaction_feedback_patch_apply_request_smoke -- [--with-fixture-context] [--format markdown|json|both] [--assert-blocked-without-ready-preflight] [--assert-ready-with-context] [--assert-read-only]"
}
