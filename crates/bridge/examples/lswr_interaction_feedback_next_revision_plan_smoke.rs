//! Repeatable LSWR interaction-feedback next-revision plan smoke.
//!
//! This consumes the checked-in interaction feedback fixture through the pure
//! consumption report and derives an AI-readable next-revision plan. It does
//! not apply patches, register MCP tools, query live runtime state, or write
//! memory/store rows.

use ab_bridge::lswr_interaction_feedback::{
    build_interaction_feedback_consumption_report, build_interaction_feedback_next_revision_plan,
    render_interaction_feedback_next_revision_plan,
};
use anyhow::{bail, Context, Result};
use serde_json::Value;

const FIXTURE_JSON: &str =
    include_str!("../tests/fixtures/lswr_interaction_feedback_fixture_v0.json");

fn main() -> Result<()> {
    let args = Args::parse(std::env::args().skip(1))?;
    let fixture: Value =
        serde_json::from_str(FIXTURE_JSON).context("parse interaction feedback fixture JSON")?;
    let report = build_interaction_feedback_consumption_report(&fixture);
    let plan = build_interaction_feedback_next_revision_plan(&report);
    let markdown = render_interaction_feedback_next_revision_plan(&plan);

    if args.assert_ready {
        assert_ready_plan(&plan)?;
    }
    if args.assert_read_only {
        assert_read_only_contract(&plan)?;
    }

    match args.format {
        OutputFormat::Markdown => println!("{markdown}"),
        OutputFormat::Json => println!("{}", serde_json::to_string_pretty(&plan)?),
        OutputFormat::Both => {
            println!("{markdown}");
            println!("{}", serde_json::to_string_pretty(&plan)?);
        }
    }

    Ok(())
}

fn assert_ready_plan(plan: &Value) -> Result<()> {
    if plan.get("plan_verdict").and_then(Value::as_str) != Some("ready_for_revision") {
        bail!("next-revision plan must be ready_for_revision");
    }
    if plan.get("source_world_verdict").and_then(Value::as_str) != Some("not_verified") {
        bail!("source_world_verdict must remain not_verified");
    }
    let next_revision = &plan["next_revision"];
    if next_revision.get("patch_id").and_then(Value::as_str) != Some("patch_arrival_bath_move_002")
    {
        bail!("next_revision patch_id must come from the feedback readback");
    }
    if next_revision["must_cite"]
        != serde_json::json!([
            "verify_patch_arrival_bath_move_001",
            "fb_arrival_crowded_001"
        ])
    {
        bail!("next_revision must cite the failed verification and feedback ids");
    }
    if next_revision
        .get("allowed_to_apply")
        .and_then(Value::as_bool)
        != Some(false)
    {
        bail!("next_revision must not apply the patch");
    }
    Ok(())
}

fn assert_read_only_contract(plan: &Value) -> Result<()> {
    for (key, expected) in [
        ("writes_state", false),
        ("store_access_required", false),
        ("mcp_tool_registered", false),
        ("implicit_live_runtime_lookup_attempted", false),
    ] {
        if plan.get(key).and_then(Value::as_bool) != Some(expected) {
            bail!("plan {key} must be {expected}");
        }
    }

    let guardrails = &plan["guardrails"];
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

    let contract = &plan["agent_action_contract"];
    for key in [
        "do_not_apply_patch",
        "do_not_ingest_outcome",
        "do_not_write_memory",
        "do_not_query_live_runtime",
        "do_not_rewrite_world_verdict",
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
    assert_ready: bool,
    assert_read_only: bool,
}

impl Args {
    fn parse(raw_args: impl IntoIterator<Item = String>) -> Result<Self> {
        let mut format = OutputFormat::Markdown;
        let mut assert_ready = false;
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
                "--assert-ready" => assert_ready = true,
                "--assert-read-only" => assert_read_only = true,
                "--help" | "-h" => bail!("{}", usage()),
                _ => bail!("unknown argument: {arg}\n\n{}", usage()),
            }
        }

        Ok(Self {
            format,
            assert_ready,
            assert_read_only,
        })
    }
}

fn usage() -> &'static str {
    "usage: cargo run -p ab-bridge --example lswr_interaction_feedback_next_revision_plan_smoke -- [--format markdown|json|both] [--assert-ready] [--assert-read-only]"
}
