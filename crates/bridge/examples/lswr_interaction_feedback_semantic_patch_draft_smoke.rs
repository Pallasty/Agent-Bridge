//! Repeatable LSWR interaction-feedback semantic patch draft smoke.
//!
//! This consumes the checked-in interaction feedback fixture through the pure
//! next-revision plan and derives a draft-only semantic patch target. It does
//! not resolve live-world arguments, apply patches, register MCP tools, query
//! runtime state, or write memory/store rows.

use ab_bridge::lswr_interaction_feedback::{
    build_interaction_feedback_next_revision_plan, build_interaction_feedback_semantic_patch_draft,
    render_interaction_feedback_semantic_patch_draft,
};
use anyhow::{bail, Context, Result};
use serde_json::Value;

const FIXTURE_JSON: &str =
    include_str!("../tests/fixtures/lswr_interaction_feedback_fixture_v0.json");

fn main() -> Result<()> {
    let args = Args::parse(std::env::args().skip(1))?;
    let fixture: Value =
        serde_json::from_str(FIXTURE_JSON).context("parse interaction feedback fixture JSON")?;
    let plan = build_interaction_feedback_next_revision_plan(&fixture);
    let draft = build_interaction_feedback_semantic_patch_draft(&plan);
    let markdown = render_interaction_feedback_semantic_patch_draft(&draft);

    if args.assert_drafted {
        assert_drafted(&draft)?;
    }
    if args.assert_read_only {
        assert_read_only_contract(&draft)?;
    }

    match args.format {
        OutputFormat::Markdown => println!("{markdown}"),
        OutputFormat::Json => println!("{}", serde_json::to_string_pretty(&draft)?),
        OutputFormat::Both => {
            println!("{markdown}");
            println!("{}", serde_json::to_string_pretty(&draft)?);
        }
    }

    Ok(())
}

fn assert_drafted(draft: &Value) -> Result<()> {
    if draft.get("draft_verdict").and_then(Value::as_str) != Some("drafted") {
        bail!("semantic patch draft verdict must be drafted");
    }
    if draft.get("source_world_verdict").and_then(Value::as_str) != Some("not_verified") {
        bail!("source_world_verdict must remain not_verified");
    }

    let patch = &draft["semantic_patch_draft"];
    if patch.get("patch_id").and_then(Value::as_str) != Some("patch_arrival_bath_move_002") {
        bail!("patch_id must come from the accepted next-revision plan");
    }
    if patch.get("operation_hint").and_then(Value::as_str)
        != Some("increase_walkway_clearance_by_repositioning_entity")
    {
        bail!("operation_hint must reflect failed walkway clearance and density feedback");
    }
    if patch["revision_sources"]
        != serde_json::json!([
            "verify_patch_arrival_bath_move_001",
            "fb_arrival_crowded_001"
        ])
    {
        bail!("semantic patch draft must cite failed verification and feedback ids");
    }
    if patch.get("apply_allowed").and_then(Value::as_bool) != Some(false) {
        bail!("semantic patch draft must not be directly applicable");
    }
    if patch
        .get("requires_live_world_state_for_arguments")
        .and_then(Value::as_bool)
        != Some(true)
    {
        bail!("semantic patch draft must require live world state before arguments resolve");
    }
    if patch
        .get("live_world_state_queried")
        .and_then(Value::as_bool)
        != Some(false)
    {
        bail!("semantic patch draft smoke must not query live world state");
    }
    Ok(())
}

fn assert_read_only_contract(draft: &Value) -> Result<()> {
    for (key, expected) in [
        ("writes_state", false),
        ("store_access_required", false),
        ("mcp_tool_registered", false),
        ("implicit_live_runtime_lookup_attempted", false),
    ] {
        if draft.get(key).and_then(Value::as_bool) != Some(expected) {
            bail!("draft {key} must be {expected}");
        }
    }

    let guardrails = &draft["guardrails"];
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

    let contract = &draft["agent_action_contract"];
    for key in [
        "resolve_arguments_before_apply",
        "do_not_apply_patch",
        "do_not_ingest_outcome",
        "do_not_write_memory",
        "do_not_query_live_runtime",
        "do_not_rewrite_world_verdict",
        "cite_revision_sources",
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
    assert_drafted: bool,
    assert_read_only: bool,
}

impl Args {
    fn parse(raw_args: impl IntoIterator<Item = String>) -> Result<Self> {
        let mut format = OutputFormat::Markdown;
        let mut assert_drafted = false;
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
                "--assert-drafted" => assert_drafted = true,
                "--assert-read-only" => assert_read_only = true,
                "--help" | "-h" => bail!("{}", usage()),
                _ => bail!("unknown argument: {arg}\n\n{}", usage()),
            }
        }

        Ok(Self {
            format,
            assert_drafted,
            assert_read_only,
        })
    }
}

fn usage() -> &'static str {
    "usage: cargo run -p ab-bridge --example lswr_interaction_feedback_semantic_patch_draft_smoke -- [--format markdown|json|both] [--assert-drafted] [--assert-read-only]"
}
