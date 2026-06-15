//! Repeatable LSWR interaction-feedback patch execution preflight smoke.
//!
//! This consumes the checked-in interaction feedback fixture through the pure
//! semantic patch draft and optionally supplies explicit argument context. It
//! never queries live runtime state, applies patches, registers MCP tools,
//! ingests outcomes, or writes memory/store rows.

use ab_bridge::lswr_interaction_feedback::{
    build_interaction_feedback_next_revision_plan,
    build_interaction_feedback_patch_execution_preflight,
    build_interaction_feedback_semantic_patch_draft,
    render_interaction_feedback_patch_execution_preflight,
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
    let input = if args.with_fixture_context {
        json!({
            "draft": draft,
            "argument_context": fixture_argument_context()
        })
    } else {
        draft
    };
    let preflight = build_interaction_feedback_patch_execution_preflight(&input);
    let markdown = render_interaction_feedback_patch_execution_preflight(&preflight);

    if args.assert_blocked_without_context {
        assert_blocked_without_context(&preflight)?;
    }
    if args.assert_ready_with_context {
        assert_ready_with_context(&preflight)?;
    }
    if args.assert_read_only {
        assert_read_only_contract(&preflight)?;
    }

    match args.format {
        OutputFormat::Markdown => println!("{markdown}"),
        OutputFormat::Json => println!("{}", serde_json::to_string_pretty(&preflight)?),
        OutputFormat::Both => {
            println!("{markdown}");
            println!("{}", serde_json::to_string_pretty(&preflight)?);
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

fn assert_blocked_without_context(preflight: &Value) -> Result<()> {
    if preflight.get("preflight_verdict").and_then(Value::as_str) != Some("blocked") {
        bail!("preflight must be blocked without explicit argument context");
    }
    if preflight.get("reason").and_then(Value::as_str) != Some("explicit_argument_context_required")
    {
        bail!("preflight reason must require explicit argument context");
    }
    if preflight["resolved_patch"]
        .get("ready_for_execution_request")
        .and_then(Value::as_bool)
        != Some(false)
    {
        bail!("preflight must not be ready without explicit argument context");
    }
    Ok(())
}

fn assert_ready_with_context(preflight: &Value) -> Result<()> {
    if preflight.get("preflight_verdict").and_then(Value::as_str)
        != Some("ready_for_execution_request")
    {
        bail!("preflight must be ready_for_execution_request with explicit context");
    }
    if preflight["source_world_verdict"].as_str() != Some("not_verified") {
        bail!("source_world_verdict must remain not_verified");
    }
    if preflight["resolved_patch"]["args"]["cell"] != json!([5, 2]) {
        bail!("resolved patch args.cell must come from explicit argument context");
    }
    if preflight["resolved_patch"]["required_citations"]
        != json!([
            "verify_patch_arrival_bath_move_001",
            "fb_arrival_crowded_001"
        ])
    {
        bail!("resolved patch must preserve required citations");
    }
    if preflight["resolved_patch"]
        .get("execution_performed")
        .and_then(Value::as_bool)
        != Some(false)
    {
        bail!("preflight must not execute the patch");
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
            bail!("preflight {key} must be {expected}");
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

    let resolved_patch = &preflight["resolved_patch"];
    for key in [
        "execution_performed",
        "apply_allowed_by_this_tool",
        "ingest_allowed_by_this_tool",
    ] {
        if resolved_patch.get(key).and_then(Value::as_bool) != Some(false) {
            bail!("resolved_patch {key} must be false");
        }
    }

    let contract = &preflight["agent_action_contract"];
    for key in [
        "do_not_apply_patch",
        "do_not_ingest_outcome",
        "do_not_write_memory",
        "do_not_query_live_runtime",
        "do_not_rewrite_world_verdict",
        "preserve_required_citations",
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
    assert_blocked_without_context: bool,
    assert_ready_with_context: bool,
    assert_read_only: bool,
}

impl Args {
    fn parse(raw_args: impl IntoIterator<Item = String>) -> Result<Self> {
        let mut format = OutputFormat::Markdown;
        let mut with_fixture_context = false;
        let mut assert_blocked_without_context = false;
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
                "--assert-blocked-without-context" => assert_blocked_without_context = true,
                "--assert-ready-with-context" => assert_ready_with_context = true,
                "--assert-read-only" => assert_read_only = true,
                "--help" | "-h" => bail!("{}", usage()),
                _ => bail!("unknown argument: {arg}\n\n{}", usage()),
            }
        }

        if assert_ready_with_context && !with_fixture_context {
            bail!("--assert-ready-with-context requires --with-fixture-context");
        }
        if assert_blocked_without_context && with_fixture_context {
            bail!("--assert-blocked-without-context requires omitting --with-fixture-context");
        }

        Ok(Self {
            format,
            with_fixture_context,
            assert_blocked_without_context,
            assert_ready_with_context,
            assert_read_only,
        })
    }
}

fn usage() -> &'static str {
    "usage: cargo run -p ab-bridge --example lswr_interaction_feedback_patch_execution_preflight_smoke -- [--with-fixture-context] [--format markdown|json|both] [--assert-blocked-without-context] [--assert-ready-with-context] [--assert-read-only]"
}
