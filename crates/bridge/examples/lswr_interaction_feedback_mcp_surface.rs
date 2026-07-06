//! Repeatable LSWR interaction-feedback MCP surface report smoke.
//!
//! This renders the registry-derived surface report for the
//! `lswr_interaction_feedback_consumption_report` MCP wrapper. It does not
//! call MCP stdio, query live runtime state, access the store, or write memory.

use ab_bridge::mcp_tools::lswr_interaction_feedback_consumption_report_mcp_surface_report;
use anyhow::{bail, Result};
use serde_json::Value;

fn main() -> Result<()> {
    let args = Args::parse(std::env::args().skip(1))?;
    let report = lswr_interaction_feedback_consumption_report_mcp_surface_report();

    if args.assert_passed {
        assert_passed_surface(&report)?;
    }
    if args.assert_niche_only {
        assert_niche_only(&report)?;
    }

    match args.format {
        OutputFormat::Markdown => {
            println!("{}", report["report_markdown"].as_str().unwrap_or_default())
        }
        OutputFormat::Json => println!("{}", serde_json::to_string_pretty(&report)?),
        OutputFormat::Both => {
            println!("{}", report["report_markdown"].as_str().unwrap_or_default());
            println!("{}", serde_json::to_string_pretty(&report)?);
        }
    }

    Ok(())
}

fn assert_passed_surface(report: &Value) -> Result<()> {
    if report.get("verdict").and_then(Value::as_str) != Some("passed") {
        bail!("surface report verdict must be passed");
    }
    let checks = report["checks"]
        .as_array()
        .ok_or_else(|| anyhow::anyhow!("surface report must include checks array"))?;
    for check in checks {
        if check.get("verdict").and_then(Value::as_str) != Some("passed") {
            bail!(
                "surface check {} must pass",
                check
                    .get("label")
                    .and_then(Value::as_str)
                    .unwrap_or("<unknown>")
            );
        }
    }
    Ok(())
}

fn assert_niche_only(report: &Value) -> Result<()> {
    let visible_in = report["visible_in"]
        .as_array()
        .ok_or_else(|| anyhow::anyhow!("surface report must include visible_in array"))?;
    let visible = visible_in
        .iter()
        .filter_map(Value::as_str)
        .collect::<Vec<_>>();
    if visible != ["all-dev"] {
        bail!("visible_in must be exactly [all-dev], got {visible:?}");
    }

    let safety = &report["safety_boundary"];
    for (key, expected) in [
        ("read_only", true),
        ("mcp_registry_change", false),
        ("store_access", false),
        ("memory_write", false),
        ("live_runtime_lookup", false),
        ("host_path", false),
        ("file_path", false),
        ("gui_capture", false),
        ("outcome_ingestion", false),
        ("onsen_mutation", false),
    ] {
        if safety.get(key).and_then(Value::as_bool) != Some(expected) {
            bail!("safety_boundary {key} must be {expected}");
        }
    }
    if safety.get("mutation_surface").and_then(Value::as_str) != Some("none") {
        bail!("safety_boundary mutation_surface must be none");
    }
    if report["expected_input"]["top_level_keys"] != serde_json::json!(["report_input"]) {
        bail!("expected_input top_level_keys must be [report_input]");
    }
    if report["expected_input"]["additional_properties"].as_bool() != Some(false) {
        bail!("expected_input additional_properties must be false");
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
    assert_passed: bool,
    assert_niche_only: bool,
}

impl Args {
    fn parse(raw_args: impl IntoIterator<Item = String>) -> Result<Self> {
        let mut format = OutputFormat::Markdown;
        let mut assert_passed = false;
        let mut assert_niche_only = false;
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
                "--assert-passed" => assert_passed = true,
                "--assert-niche-only" => assert_niche_only = true,
                "--help" | "-h" => bail!("{}", usage()),
                _ => bail!("unknown argument: {arg}\n\n{}", usage()),
            }
        }

        Ok(Self {
            format,
            assert_passed,
            assert_niche_only,
        })
    }
}

fn usage() -> &'static str {
    "usage: cargo run -p ab-bridge --example lswr_interaction_feedback_mcp_surface -- [--format markdown|json|both] [--assert-passed] [--assert-niche-only]"
}
