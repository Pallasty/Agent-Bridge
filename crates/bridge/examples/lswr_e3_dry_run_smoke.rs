//! Repeatable LSWR Step E3 non-empty dry-run smoke.
//!
//! This creates a temporary Step D LSWR review artifact plus an output-lane
//! outcome sidecar, then runs the E2 projection and E3 dry-run adapter over the
//! files. It writes no memory rows and does not call MCP.

use ab_bridge::lswr_outcome_admission::{
    outcome_admission_dry_run_candidates, outcome_admissions_projection,
};
use ab_bridge::lswr_present::{
    world_envelope_to_present_packet, write_present_packet_review_file, PresentPacketOptions,
    WORLD_TOOL_SCHEMA,
};
use ab_bridge::present::{list_artifacts, write_outcome_sidecar};
use ab_bridge::present_ingest::OUTCOME_MEMORY_KIND;
use anyhow::{bail, Context, Result};
use serde_json::{json, Value};
use std::path::PathBuf;

const GENERATED_AT: &str = "2026-06-15T00:00:00Z";
const GENERATED_AT_UNIX: u64 = 1_781_510_000;
const WINDOW_SECS: u64 = 31_536_000;

fn main() -> Result<()> {
    let args = Args::parse(std::env::args().skip(1))?;
    std::fs::create_dir_all(&args.out_dir)
        .with_context(|| format!("create {}", args.out_dir.display()))?;

    let packet = world_envelope_to_present_packet(
        "world_patch",
        &verified_patch_envelope(),
        PresentPacketOptions::new(GENERATED_AT).with_commit("lswr-e3-smoke"),
    );
    let review_file = write_present_packet_review_file(&packet, &args.out_dir)
        .with_context(|| format!("write Step D review file in {}", args.out_dir.display()))?;

    write_outcome_sidecar(
        &args.out_dir,
        &review_file.id,
        &expression_record(&review_file.id),
    )
    .with_context(|| format!("write outcome sidecar for {}", review_file.id))?;

    let artifacts = list_artifacts(&args.out_dir, 25, Some("html"));
    let projection =
        outcome_admissions_projection(&artifacts, false, GENERATED_AT_UNIX, WINDOW_SECS);
    let admissions = projection
        .get("admissions")
        .and_then(Value::as_array)
        .cloned()
        .unwrap_or_default();
    let dry_run =
        outcome_admission_dry_run_candidates(&admissions, GENERATED_AT_UNIX, WINDOW_SECS, 3);

    let candidate_count = dry_run
        .get("candidate_count")
        .and_then(Value::as_u64)
        .unwrap_or(0);
    let writes_state = dry_run
        .get("writes_state")
        .and_then(Value::as_bool)
        .unwrap_or(true);
    let dry_run_flag = dry_run
        .get("dry_run")
        .and_then(Value::as_bool)
        .unwrap_or(false);
    if args.assert_non_empty {
        if candidate_count == 0 {
            bail!("expected at least one E3 dry-run candidate");
        }
        if !dry_run_flag || writes_state {
            bail!("E3 smoke must stay dry-run-only");
        }
    }

    let first_candidate = dry_run
        .get("candidates")
        .and_then(Value::as_array)
        .and_then(|rows| rows.first())
        .cloned()
        .unwrap_or(Value::Null);

    let summary = json!({
        "schema": "agent_bridge.lswr.e3_dry_run_smoke.v0",
        "out_dir": args.out_dir.display().to_string(),
        "artifact_id": review_file.id,
        "artifact_path": review_file.artifact_path.display().to_string(),
        "dual_encoding": review_file.dual_encoding,
        "static_render_status": review_file.static_render_status,
        "projection": {
            "schema": projection.get("schema").cloned().unwrap_or(Value::Null),
            "scanned_artifacts": projection.get("scanned_artifacts").cloned().unwrap_or(Value::Null),
            "training_eligible_count": projection.get("training_eligible_count").cloned().unwrap_or(Value::Null),
            "audit_only_count": projection.get("audit_only_count").cloned().unwrap_or(Value::Null),
            "rejected_count": projection.get("rejected_count").cloned().unwrap_or(Value::Null),
            "reason_counts": projection.get("reason_counts").cloned().unwrap_or(Value::Null),
        },
        "dry_run": {
            "schema": dry_run.get("schema").cloned().unwrap_or(Value::Null),
            "dry_run": dry_run_flag,
            "writes_state": writes_state,
            "candidate_count": candidate_count,
            "memory_kind": dry_run.get("memory_kind").cloned().unwrap_or(Value::Null),
            "first_candidate_key": first_candidate
                .get("memory")
                .and_then(|m| m.get("key"))
                .cloned()
                .unwrap_or(Value::Null),
            "first_candidate_scope": first_candidate
                .get("memory")
                .and_then(|m| m.get("scope"))
                .cloned()
                .unwrap_or(Value::Null),
        },
        "assertions": {
            "non_empty": candidate_count > 0,
            "dry_run_only": dry_run_flag && !writes_state,
            "memory_kind": OUTCOME_MEMORY_KIND,
        },
        "note": "local smoke only: generated Step D files and E3 candidates; no MCP call and no memory write",
    });

    println!("{}", serde_json::to_string_pretty(&summary)?);
    Ok(())
}

fn verified_patch_envelope() -> Value {
    json!({
        "schema": WORLD_TOOL_SCHEMA,
        "ok": true,
        "verified": true,
        "request": {
            "world.patch": {
                "op": "move",
                "entity": "bath",
                "args": {"cell": [8, 0]},
                "expected_effect": {
                    "target": "bath",
                    "metric": "screen_area",
                    "to_op": ">=",
                    "to_value": 0.001
                }
            }
        },
        "verify": {
            "method": "live_viewport_pixel_coverage",
            "verified_to": "lswr_e3_smoke_viewport",
            "evidence": {"screen_area": 0.003}
        },
        "host_response": {
            "world.patch": {
                "applied": true,
                "entity": "bath",
                "op": "move"
            },
            "expected_effect": {
                "verified": true,
                "metric": "screen_area",
                "actual": 0.003,
                "clauses": [{
                    "metric": "screen_area",
                    "actual": 0.003,
                    "to_op": ">=",
                    "to_value": 0.001,
                    "verified": true
                }]
            }
        }
    })
}

fn expression_record(artifact_id: &str) -> Value {
    json!({
        "artifact_id": artifact_id,
        "present_artifact_id": artifact_id,
        "verify_status": "rendered_ok",
        "embody_status": "not_applicable",
        "interactive_status": "not_applicable",
        "decision": "approved",
        "token_match": true,
        "ts": GENERATED_AT_UNIX,
    })
}

struct Args {
    out_dir: PathBuf,
    assert_non_empty: bool,
}

impl Args {
    fn parse(raw_args: impl IntoIterator<Item = String>) -> Result<Self> {
        let mut out_dir = None;
        let mut assert_non_empty = false;
        let mut iter = raw_args.into_iter();
        while let Some(arg) = iter.next() {
            match arg.as_str() {
                "--out-dir" => {
                    let value = iter
                        .next()
                        .ok_or_else(|| anyhow::anyhow!("--out-dir requires a path"))?;
                    out_dir = Some(PathBuf::from(value));
                }
                "--assert-non-empty" => assert_non_empty = true,
                "--help" | "-h" => bail!("{}", usage()),
                _ => bail!("unknown argument: {arg}\n\n{}", usage()),
            }
        }

        Ok(Self {
            out_dir: out_dir.unwrap_or_else(default_out_dir),
            assert_non_empty,
        })
    }
}

fn default_out_dir() -> PathBuf {
    std::env::temp_dir().join(format!(
        "agent-bridge-lswr-e3-dry-run-smoke-{}",
        std::process::id()
    ))
}

fn usage() -> &'static str {
    "usage: cargo run -p ab-bridge --example lswr_e3_dry_run_smoke -- [--out-dir PATH] [--assert-non-empty]"
}
