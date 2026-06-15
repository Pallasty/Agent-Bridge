//! Repeatable LSWR interaction-feedback Markdown report smoke.
//!
//! This renders the checked-in interaction feedback fixture through the pure
//! validation-envelope path. It writes no memory rows, registers no MCP tool,
//! and does not touch live world/runtime state.

use ab_bridge::lswr_interaction_feedback::{
    build_interaction_feedback_evidence_packet, build_interaction_feedback_validation_envelope,
    render_interaction_feedback_validation_envelope,
};
use anyhow::{bail, Context, Result};
use serde_json::Value;

const FIXTURE_JSON: &str =
    include_str!("../tests/fixtures/lswr_interaction_feedback_fixture_v0.json");
const EXPECTED_MARKDOWN: &str =
    include_str!("../tests/fixtures/lswr_interaction_feedback_validation_envelope_v0.md");

fn main() -> Result<()> {
    let args = Args::parse(std::env::args().skip(1))?;
    let fixture: Value =
        serde_json::from_str(FIXTURE_JSON).context("parse interaction feedback fixture JSON")?;
    let envelope = build_interaction_feedback_validation_envelope(&fixture);
    let markdown = render_interaction_feedback_validation_envelope(&envelope);
    let packet = build_interaction_feedback_evidence_packet(&fixture);

    if args.assert_golden && markdown != EXPECTED_MARKDOWN {
        bail!("rendered Markdown does not match golden fixture");
    }
    if args.assert_read_only {
        assert_read_only_contract(&envelope)?;
    }

    match args.format {
        OutputFormat::Markdown => println!("{markdown}"),
        OutputFormat::Json => println!("{}", serde_json::to_string_pretty(&packet)?),
        OutputFormat::Both => {
            println!("{markdown}");
            println!("{}", serde_json::to_string_pretty(&packet)?);
        }
    }

    Ok(())
}

fn assert_read_only_contract(envelope: &Value) -> Result<()> {
    let guardrails = &envelope["guardrails"];
    for (key, expected) in [
        ("read_only", true),
        ("writes_state", false),
        ("store_access_required", false),
        ("mcp_tool_registered", false),
        ("primary_readback_requires_screenshot", false),
        ("feedback_changes_world_verdict_allowed", false),
    ] {
        if guardrails.get(key).and_then(Value::as_bool) != Some(expected) {
            bail!("guardrail {key} must be {expected}");
        }
    }
    if guardrails.get("mutation_surface").and_then(Value::as_str) != Some("none") {
        bail!("guardrail mutation_surface must be none");
    }
    if envelope
        .get("requires_screenshot_for_primary_readback")
        .and_then(Value::as_bool)
        != Some(false)
    {
        bail!("primary readback must not require screenshot");
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
    assert_golden: bool,
    assert_read_only: bool,
}

impl Args {
    fn parse(raw_args: impl IntoIterator<Item = String>) -> Result<Self> {
        let mut format = OutputFormat::Markdown;
        let mut assert_golden = false;
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
                "--assert-golden" => assert_golden = true,
                "--assert-read-only" => assert_read_only = true,
                "--help" | "-h" => bail!("{}", usage()),
                _ => bail!("unknown argument: {arg}\n\n{}", usage()),
            }
        }

        Ok(Self {
            format,
            assert_golden,
            assert_read_only,
        })
    }
}

fn usage() -> &'static str {
    "usage: cargo run -p ab-bridge --example lswr_interaction_feedback_report_smoke -- [--format markdown|json|both] [--assert-golden] [--assert-read-only]"
}
