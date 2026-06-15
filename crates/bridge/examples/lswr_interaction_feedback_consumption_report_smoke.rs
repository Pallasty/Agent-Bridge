//! Repeatable LSWR interaction-feedback consumption report smoke.
//!
//! This renders the checked-in interaction feedback fixture through the pure
//! consumption-preflight report path. It writes no memory rows, registers no MCP
//! tool, and does not touch live world/runtime state.

use ab_bridge::lswr_interaction_feedback::{
    build_interaction_feedback_consumption_report,
    build_interaction_feedback_packet_consumption_preflight,
    render_interaction_feedback_consumption_preflight_report,
};
use anyhow::{bail, Context, Result};
use serde_json::Value;

const FIXTURE_JSON: &str =
    include_str!("../tests/fixtures/lswr_interaction_feedback_fixture_v0.json");
const EXPECTED_MARKDOWN: &str =
    include_str!("../tests/fixtures/lswr_interaction_feedback_consumption_report_v0.md");

fn main() -> Result<()> {
    let args = Args::parse(std::env::args().skip(1))?;
    let fixture: Value =
        serde_json::from_str(FIXTURE_JSON).context("parse interaction feedback fixture JSON")?;
    let preflight = build_interaction_feedback_packet_consumption_preflight(&fixture);
    let markdown = render_interaction_feedback_consumption_preflight_report(&preflight);
    let report = build_interaction_feedback_consumption_report(&preflight);

    if args.assert_golden && markdown != EXPECTED_MARKDOWN {
        bail!("rendered consumption Markdown does not match golden fixture");
    }
    if args.assert_read_only {
        assert_read_only_contract(&report)?;
    }

    match args.format {
        OutputFormat::Markdown => println!("{markdown}"),
        OutputFormat::Json => println!("{}", serde_json::to_string_pretty(&report)?),
        OutputFormat::Both => {
            println!("{markdown}");
            println!("{}", serde_json::to_string_pretty(&report)?);
        }
    }

    Ok(())
}

fn assert_read_only_contract(report: &Value) -> Result<()> {
    for (key, expected) in [
        ("writes_state", false),
        ("store_access_required", false),
        ("mcp_tool_registered", false),
    ] {
        if report.get(key).and_then(Value::as_bool) != Some(expected) {
            bail!("report {key} must be {expected}");
        }
    }

    let guardrails = &report["guardrails"];
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
    ] {
        if guardrails.get(key).and_then(Value::as_bool) != Some(expected) {
            bail!("guardrail {key} must be {expected}");
        }
    }
    if guardrails.get("mutation_surface").and_then(Value::as_str) != Some("none") {
        bail!("guardrail mutation_surface must be none");
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
    "usage: cargo run -p ab-bridge --example lswr_interaction_feedback_consumption_report_smoke -- [--format markdown|json|both] [--assert-golden] [--assert-read-only]"
}
