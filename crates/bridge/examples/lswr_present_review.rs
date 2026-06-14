//! LSWR Step D D1 fixture review artifact runner.
//!
//! Reads the canonical D1 fixture JSON and writes one self-describing
//! `present/v0` HTML review artifact per case, plus a manifest. This is a
//! manual acceptance aid only: it does not register MCP tools, launch Onsen,
//! self-verify in a browser, or ingest #94 outcomes.
//!
//! Example:
//!   cargo run -p ab-bridge --example lswr_present_review -- \
//!     --fixtures docs/design/fixtures/lswr-step-d-d1-review-packets.json \
//!     --out-dir /tmp/lswr-step-d-d1-review

use ab_bridge::lswr_present::{
    present_packet_review_id, world_envelope_to_present_packet, write_present_packet_review_file,
    PresentPacketOptions,
};
use anyhow::{bail, Context, Result};
use serde_json::{json, Value};
use std::path::{Path, PathBuf};

fn main() -> Result<()> {
    let args: Vec<String> = std::env::args().collect();
    let fixture_path = arg_value(&args, "--fixtures")
        .map(PathBuf::from)
        .unwrap_or_else(|| {
            PathBuf::from("docs/design/fixtures/lswr-step-d-d1-review-packets.json")
        });
    let out_dir = arg_value(&args, "--out-dir")
        .map(PathBuf::from)
        .unwrap_or_else(|| {
            std::env::temp_dir().join(format!(
                "agent-bridge-lswr-step-d-d1-review-{}",
                std::process::id()
            ))
        });

    let manifest = render_fixture_review_set(&fixture_path, &out_dir)?;
    let manifest_path = out_dir.join("manifest.json");
    std::fs::create_dir_all(&out_dir)?;
    std::fs::write(&manifest_path, serde_json::to_string_pretty(&manifest)?)?;

    println!("{}", serde_json::to_string_pretty(&manifest)?);
    eprintln!("manifest: {}", manifest_path.display());
    Ok(())
}

fn arg_value(args: &[String], flag: &str) -> Option<String> {
    args.windows(2)
        .find(|pair| pair[0] == flag)
        .map(|pair| pair[1].clone())
}

fn render_fixture_review_set(fixture_path: &Path, out_dir: &Path) -> Result<Value> {
    let raw = std::fs::read_to_string(fixture_path)
        .with_context(|| format!("read fixtures {}", fixture_path.display()))?;
    let fixtures: Value = serde_json::from_str(&raw)
        .with_context(|| format!("parse fixtures {}", fixture_path.display()))?;
    let generated_at = fixtures
        .get("generated_at")
        .and_then(Value::as_str)
        .unwrap_or("unknown");
    let cases = fixtures
        .get("cases")
        .and_then(Value::as_array)
        .context("fixtures.cases must be an array")?;
    if cases.is_empty() {
        bail!("fixtures.cases is empty");
    }

    let mut rows = Vec::new();
    for case in cases {
        let case_id = case
            .get("id")
            .and_then(Value::as_str)
            .context("case.id is required")?;
        let world_tool = case
            .get("world_tool")
            .and_then(Value::as_str)
            .context("case.world_tool is required")?;
        let envelope = case
            .get("source_envelope")
            .context("case.source_envelope is required")?;
        let commit = case
            .get("expected_packet")
            .and_then(|v| v.get("provenance"))
            .and_then(|v| v.get("commit"))
            .and_then(Value::as_str);
        let mut options = PresentPacketOptions::new(generated_at);
        if let Some(commit) = commit {
            options = options.with_commit(commit);
        }

        let packet = world_envelope_to_present_packet(world_tool, envelope, options);
        let file = write_present_packet_review_file(&packet, out_dir)
            .with_context(|| format!("write review artifact for case {case_id}"))?;
        let expected = case.get("expected_packet").unwrap_or(&Value::Null);
        rows.push(json!({
            "case_id": case_id,
            "world_tool": world_tool,
            "artifact_id": file.id,
            "artifact_path": file.artifact_path.display().to_string(),
            "bytes": file.bytes,
            "dual_encoding": file.dual_encoding,
            "static_render_status": file.static_render_status,
            "expected_artifact_id": present_packet_review_id(&packet),
            "packet": {
                "schema": packet.get("schema").cloned().unwrap_or(Value::Null),
                "verdict": packet.get("verdict").cloned().unwrap_or(Value::Null),
                "reason": packet.get("reason").cloned().unwrap_or(Value::Null),
                "ingestion_allowed": packet
                    .get("ingestion")
                    .and_then(|v| v.get("allowed"))
                    .cloned()
                    .unwrap_or(Value::Null),
            },
            "expected_match": {
                "verdict": packet.get("verdict") == expected.get("verdict"),
                "reason": packet.get("reason") == expected.get("reason"),
                "ingestion_allowed": packet
                    .get("ingestion")
                    .and_then(|v| v.get("allowed"))
                    == expected.get("ingestion").and_then(|v| v.get("allowed")),
            },
        }));
    }

    let discovered = ab_bridge::present::list_artifacts(out_dir, rows.len() + 4, Some("html"));
    Ok(json!({
        "schema": "agent_bridge.lswr.step_d.d1_review_manifest.v0",
        "source_fixture_path": fixture_path.display().to_string(),
        "out_dir": out_dir.display().to_string(),
        "case_count": rows.len(),
        "artifact_count": discovered.len(),
        "all_dual_encoded": rows.iter().all(|row| {
            row.get("dual_encoding").and_then(Value::as_bool).unwrap_or(false)
        }),
        "all_static_rendered": rows.iter().all(|row| {
            row.get("static_render_status").and_then(Value::as_str) == Some("rendered_static")
        }),
        "all_expected_semantics_match": rows.iter().all(|row| {
            let Some(matches) = row.get("expected_match") else {
                return false;
            };
            matches.get("verdict").and_then(Value::as_bool).unwrap_or(false)
                && matches.get("reason").and_then(Value::as_bool).unwrap_or(false)
                && matches
                    .get("ingestion_allowed")
                    .and_then(Value::as_bool)
                    .unwrap_or(false)
        }),
        "cases": rows,
        "artifacts_discovered": discovered
            .into_iter()
            .map(|a| json!({
                "artifact_id": a.id,
                "artifact_path": a.artifact_path,
                "kind": a.kind,
                "dual_encoding": a.dual_encoding,
                "bytes": a.bytes,
            }))
            .collect::<Vec<_>>(),
    }))
}
