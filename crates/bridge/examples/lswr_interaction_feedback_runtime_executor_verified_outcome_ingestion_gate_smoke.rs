#![recursion_limit = "256"]

//! Repeatable LSWR verified-outcome ingestion gate smoke.
//!
//! This validates an explicit ingestion-gate decision over a minimal accepted
//! G17 world-verdict rewrite gate package. It emits a bounded verified outcome
//! ingestion package only. It never writes durable outcome records, touches
//! memory/store rows, registers MCP tools, persists world verdicts, or executes
//! verified outcome ingestion.

use ab_bridge::lswr_interaction_feedback::{
    LSWR_INTERACTION_FEEDBACK_RUNTIME_EXECUTOR_WORLD_VERDICT_REWRITE_GATE_SCHEMA,
    LSWR_RUNTIME_EXECUTOR_VERIFIED_OUTCOME_INGESTION_DECISION_SCHEMA,
    build_interaction_feedback_runtime_executor_verified_outcome_ingestion_gate,
    render_interaction_feedback_runtime_executor_verified_outcome_ingestion_gate,
};
use anyhow::{Context, Result, bail};
use serde_json::{Value, json};

fn main() -> Result<()> {
    let args = Args::parse(std::env::args().skip(1))?;
    let rewrite_gate = fixture_world_verdict_rewrite_gate();
    let input = if args.with_verified_outcome_ingestion_decision {
        json!({
            "world_verdict_rewrite_gate": rewrite_gate,
            "verified_outcome_ingestion_decision": fixture_verified_outcome_ingestion_decision()
        })
    } else {
        rewrite_gate
    };
    let ingestion_gate =
        build_interaction_feedback_runtime_executor_verified_outcome_ingestion_gate(&input);
    let markdown = render_interaction_feedback_runtime_executor_verified_outcome_ingestion_gate(
        &ingestion_gate,
    );

    if args.assert_blocked_without_verified_outcome_ingestion_decision {
        assert_blocked_without_verified_outcome_ingestion_decision(&ingestion_gate)?;
    }
    if args.assert_ready_for_verified_outcome_ingestion_execution {
        assert_ready_for_verified_outcome_ingestion_execution(&ingestion_gate)?;
    }
    if args.assert_output_only {
        assert_output_only_contract(&ingestion_gate)?;
    }

    match args.format {
        OutputFormat::Markdown => println!("{markdown}"),
        OutputFormat::Json => println!("{}", serde_json::to_string_pretty(&ingestion_gate)?),
        OutputFormat::Both => {
            println!("{markdown}");
            println!("{}", serde_json::to_string_pretty(&ingestion_gate)?);
        }
    }

    Ok(())
}

fn fixture_world_verdict_rewrite_gate() -> Value {
    let scope = fixture_rewrite_scope();
    json!({
        "schema": LSWR_INTERACTION_FEEDBACK_RUNTIME_EXECUTOR_WORLD_VERDICT_REWRITE_GATE_SCHEMA,
        "input_kind": "durable_outcome_record_write_evidence_review_preflight_with_world_verdict_rewrite_decision_wrapper",
        "source_schema": "agent_bridge.lswr.interaction_feedback_runtime_executor_durable_outcome_record_write_evidence_review_preflight.v0",
        "source_durable_outcome_record_write_evidence_review_preflight_verdict": "ready_for_world_verdict_rewrite_gate",
        "source_world_verdict": "not_verified",
        "world_verdict_rewrite_decision_schema": "agent_bridge.lswr.runtime_executor.world_verdict_rewrite_decision.v0",
        "world_verdict_rewrite_gate_verdict": "ready_for_verified_outcome_ingestion_gate",
        "status": "ready",
        "reason": "world_verdict_rewrite_gate_ready_for_verified_outcome_ingestion_gate",
        "failure_reasons": [],
        "guardrails": {
            "read_only": true,
            "mutation_surface": "output_only",
            "writes_state": false,
            "store_access_required": false,
            "mcp_tool_registered": false,
            "queries_live_runtime": false,
            "requires_ready_durable_outcome_record_write_evidence_review_preflight": true,
            "requires_explicit_world_verdict_rewrite_decision": true,
            "decision_kind": "world_verdict_rewrite",
            "performs_world_verdict_rewrite_gate": true,
            "performs_world_verdict_rewrite_output": true,
            "persists_world_verdict": false,
            "durable_outcome_record_written": false,
            "memory_write_allowed": false,
            "outcome_ingestion_allowed": false,
            "verified_outcome_ingestion_allowed": false,
            "persists_outcome_record": false,
            "runtime_executor_world_verdict_rewrite_gate_only": true
        },
        "world_verdict_rewrite": {
            "rewrite_decision_id": scope["rewrite_decision_id"],
            "source_review_decision_id": scope["source_review_decision_id"],
            "write_evidence_id": scope["write_evidence_id"],
            "world_id": scope["world_id"],
            "branch_id": scope["branch_id"],
            "runtime_generation": scope["runtime_generation"],
            "patch_id": scope["patch_id"],
            "decision_kind": "world_verdict_rewrite",
            "decision": "rewrite_world_verdict_to_verified",
            "rewrite_reason": "reviewed_durable_outcome_record_write_evidence_supports_verified_world_verdict",
            "previous_world_verdict": "not_verified",
            "rewritten_world_verdict": "verified",
            "outcome_record_candidate_id": scope["outcome_record_candidate_id"],
            "outcome_record_schema": scope["outcome_record_schema"],
            "idempotency_key": scope["idempotency_key"],
            "outcome_payload_digest": scope["outcome_payload_digest"],
            "write_destination": scope["write_destination"],
            "outcome_record_key": scope["outcome_record_key"],
            "outcome_record_digest": scope["outcome_record_digest"],
            "persisted_outcome_record_key": scope["persisted_outcome_record_key"],
            "persisted_outcome_record_digest": scope["persisted_outcome_record_digest"],
            "verified_outcome_claim_present": true,
            "reviewer_attestation_present": true,
            "evidence_lineage_preserved": true,
            "ready_for_verified_outcome_ingestion_gate": true,
            "world_verdict_rewrite_allowed": true,
            "world_verdict_rewrite_output_only": true,
            "world_verdict_persisted_by_this_tool": false,
            "durable_outcome_record_written_by_this_tool": false,
            "memory_write_allowed": false,
            "outcome_ingestion_allowed": false
        },
        "next_allowed_gate": "verified_outcome_ingestion_gate",
        "agent_action_contract": {
            "mode": "runtime_executor_world_verdict_rewrite_gate_only",
            "may_enter_verified_outcome_ingestion_gate_after_rewrite": true,
            "may_emit_verified_outcome_package": true,
            "do_not_ingest_outcome": true,
            "do_not_write_memory": true,
            "do_not_persist_world_verdict": true,
            "do_not_persist_outcome_record": true,
            "require_separate_verified_outcome_ingestion_gate": true
        },
        "world_verdict_rewrite_gate_performed_by_this_tool": true,
        "world_verdict_rewrite_performed_by_this_tool": true,
        "world_verdict_persisted_by_this_tool": false,
        "durable_outcome_record_written_by_this_tool": false,
        "durable_outcome_ingestion_performed_by_this_tool": false,
        "verified_outcome_ingestion_performed_by_this_tool": false,
        "writes_state": false,
        "store_access_required": false,
        "mcp_tool_registered": false
    })
}

fn fixture_verified_outcome_ingestion_decision() -> Value {
    let scope = fixture_rewrite_scope();
    json!({
        "schema": LSWR_RUNTIME_EXECUTOR_VERIFIED_OUTCOME_INGESTION_DECISION_SCHEMA,
        "ingestion_decision_id": "verified_outcome_ingestion_arrival_bath_move_002",
        "decision_kind": "verified_outcome_ingestion_gate",
        "source_world_verdict_rewrite_scope": scope,
        "decision": "approved_for_verified_outcome_ingestion_gate",
        "ingestion_reason": "world_verdict_rewrite_output_is_scoped_and_ready_for_separate_ingestion_execution",
        "source_world_verdict": "not_verified",
        "rewritten_world_verdict": "verified",
        "reviewed_world_verdict_rewrite_gate_verdict": "ready_for_verified_outcome_ingestion_gate",
        "verified_outcome_claim_present": true,
        "world_verdict_rewrite_output_confirmed": true,
        "reviewer_attestation_present": true,
        "evidence_lineage_preserved": true,
        "outcome_record_digest_confirmed": true,
        "idempotency_key_confirmed": true,
        "persisted_key_confirmed": true,
        "persisted_digest_confirmed": true,
        "ingestion_boundary_acknowledged": true,
        "outcome_ingestion_allowed": false,
        "memory_write_allowed": false,
        "verified_outcome_ingested_by_this_tool": false,
        "durable_outcome_record_written_by_this_tool": false,
        "world_verdict_persisted_by_this_tool": false
    })
}

fn fixture_rewrite_scope() -> Value {
    json!({
        "rewrite_decision_id": "world_verdict_rewrite_arrival_bath_move_002",
        "source_review_decision_id": "durable_outcome_record_write_evidence_review_arrival_bath_move_002",
        "write_evidence_id": "durable_outcome_record_write_evidence_arrival_bath_move_002",
        "world_id": "onsen_live_session",
        "branch_id": "main",
        "runtime_generation": "runtime_gen_1284",
        "patch_id": "patch_arrival_bath_move_002",
        "outcome_record_candidate_id": "outcome_record_candidate_arrival_bath_move_002",
        "outcome_record_schema": "agent_bridge.lswr.outcome_record_candidate.v0",
        "idempotency_key": "onsen_live_session/main/runtime_gen_1284/patch_arrival_bath_move_002/outcome_ingestion_review_arrival_bath_move_002",
        "outcome_payload_digest": "sha256:arrival-bath-move-002-outcome-payload",
        "write_destination": "agent_bridge_store_outcome_records",
        "outcome_record_key": "onsen_live_session/main/runtime_gen_1284/patch_arrival_bath_move_002/outcome_record_candidate_arrival_bath_move_002",
        "outcome_record_digest": "sha256:arrival-bath-move-002-outcome-record",
        "persisted_outcome_record_key": "onsen_live_session/main/runtime_gen_1284/patch_arrival_bath_move_002/outcome_record_candidate_arrival_bath_move_002",
        "persisted_outcome_record_digest": "sha256:arrival-bath-move-002-outcome-record"
    })
}

fn assert_blocked_without_verified_outcome_ingestion_decision(gate: &Value) -> Result<()> {
    assert_eq(gate, "verified_outcome_ingestion_gate_verdict", "blocked")?;
    assert_eq(
        gate,
        "reason",
        "explicit_verified_outcome_ingestion_decision_required",
    )?;
    Ok(())
}

fn assert_ready_for_verified_outcome_ingestion_execution(gate: &Value) -> Result<()> {
    assert_eq(
        gate,
        "verified_outcome_ingestion_gate_verdict",
        "ready_for_verified_outcome_ingestion_execution",
    )?;
    assert_eq(
        gate,
        "next_allowed_gate",
        "verified_outcome_ingestion_execution",
    )?;
    if gate["verified_outcome_ingestion_gate"]["previous_world_verdict"] != "not_verified" {
        bail!("expected previous_world_verdict=not_verified");
    }
    if gate["verified_outcome_ingestion_gate"]["verified_world_verdict"] != "verified" {
        bail!("expected verified_world_verdict=verified");
    }
    if gate["verified_outcome_ingestion_gate"]["ready_for_verified_outcome_ingestion_execution"]
        != true
    {
        bail!("expected ready_for_verified_outcome_ingestion_execution=true");
    }
    Ok(())
}

fn assert_output_only_contract(gate: &Value) -> Result<()> {
    for key in [
        "writes_state",
        "store_access_required",
        "mcp_tool_registered",
        "world_verdict_persisted_by_this_tool",
        "durable_outcome_record_written_by_this_tool",
        "durable_outcome_ingestion_performed_by_this_tool",
        "verified_outcome_ingestion_performed_by_this_tool",
    ] {
        if gate[key] != false {
            bail!("{key} must be false");
        }
    }
    if gate["verified_outcome_ingestion_gate_performed_by_this_tool"] != true {
        bail!("ingestion gate marker must be true");
    }
    for key in [
        "read_only",
        "requires_ready_world_verdict_rewrite_gate",
        "requires_explicit_verified_outcome_ingestion_decision",
        "performs_verified_outcome_ingestion_gate",
        "performs_verified_outcome_package_output",
    ] {
        if gate["guardrails"][key] != true {
            bail!("guardrail {key} must be true");
        }
    }
    for key in [
        "writes_state",
        "store_access_required",
        "mcp_tool_registered",
        "performs_verified_outcome_ingestion",
        "persists_world_verdict",
        "durable_outcome_record_written",
        "memory_write_allowed",
        "outcome_ingestion_allowed",
        "verified_outcome_ingestion_allowed",
        "persists_outcome_record",
    ] {
        if gate["guardrails"][key] != false {
            bail!("guardrail {key} must be false");
        }
    }
    for key in [
        "do_not_ingest_outcome",
        "do_not_write_memory",
        "do_not_persist_world_verdict",
        "do_not_persist_outcome_record",
        "require_separate_verified_outcome_ingestion_execution",
    ] {
        if gate["agent_action_contract"][key] != true {
            bail!("agent action contract {key} must be true");
        }
    }
    Ok(())
}

fn assert_eq(value: &Value, key: &str, expected: &str) -> Result<()> {
    if value[key] != expected {
        bail!("expected {key}={expected}, got {}", value[key]);
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
    with_verified_outcome_ingestion_decision: bool,
    assert_blocked_without_verified_outcome_ingestion_decision: bool,
    assert_ready_for_verified_outcome_ingestion_execution: bool,
    assert_output_only: bool,
    format: OutputFormat,
}

impl Args {
    fn parse(args: impl Iterator<Item = String>) -> Result<Self> {
        let mut parsed = Self {
            with_verified_outcome_ingestion_decision: false,
            assert_blocked_without_verified_outcome_ingestion_decision: false,
            assert_ready_for_verified_outcome_ingestion_execution: false,
            assert_output_only: false,
            format: OutputFormat::Markdown,
        };
        let mut args = args.peekable();
        while let Some(arg) = args.next() {
            match arg.as_str() {
                "--with-verified-outcome-ingestion-decision" => {
                    parsed.with_verified_outcome_ingestion_decision = true;
                }
                "--assert-blocked-without-verified-outcome-ingestion-decision" => {
                    parsed.assert_blocked_without_verified_outcome_ingestion_decision = true;
                }
                "--assert-ready-for-verified-outcome-ingestion-execution" => {
                    parsed.assert_ready_for_verified_outcome_ingestion_execution = true;
                }
                "--assert-output-only" => parsed.assert_output_only = true,
                "--format" => {
                    let value = args
                        .next()
                        .context("--format requires markdown|json|both")?;
                    parsed.format = parse_format(&value)?;
                }
                "--format=json" => parsed.format = OutputFormat::Json,
                "--format=both" => parsed.format = OutputFormat::Both,
                "--format=markdown" => parsed.format = OutputFormat::Markdown,
                "-h" | "--help" => {
                    print_help();
                    std::process::exit(0);
                }
                other => bail!("unknown argument: {other}"),
            }
        }
        Ok(parsed)
    }
}

fn parse_format(value: &str) -> Result<OutputFormat> {
    match value {
        "markdown" => Ok(OutputFormat::Markdown),
        "json" => Ok(OutputFormat::Json),
        "both" => Ok(OutputFormat::Both),
        other => bail!("unknown format: {other}"),
    }
}

fn print_help() {
    println!(
        "\
Usage: cargo run -q -p ab-bridge --example lswr_interaction_feedback_runtime_executor_verified_outcome_ingestion_gate_smoke -- [options]

Options:
  --with-verified-outcome-ingestion-decision
  --assert-blocked-without-verified-outcome-ingestion-decision
  --assert-ready-for-verified-outcome-ingestion-execution
  --assert-output-only
  --format markdown|json|both
"
    );
}
