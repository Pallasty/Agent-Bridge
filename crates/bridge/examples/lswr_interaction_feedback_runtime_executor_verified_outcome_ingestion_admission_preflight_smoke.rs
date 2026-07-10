#![recursion_limit = "256"]

//! Repeatable LSWR verified-outcome ingestion admission preflight smoke.
//!
//! This validates an explicit admission decision over a minimal accepted G27
//! verified-outcome ingestion write-evidence review preflight. It never writes
//! store rows, touches memory, registers MCP tools, persists world verdicts, or
//! ingests verified outcomes.

use ab_bridge::lswr_interaction_feedback::{
    build_interaction_feedback_runtime_executor_verified_outcome_ingestion_admission_preflight,
    render_interaction_feedback_runtime_executor_verified_outcome_ingestion_admission_preflight,
    LSWR_INTERACTION_FEEDBACK_RUNTIME_EXECUTOR_VERIFIED_OUTCOME_INGESTION_WRITE_EVIDENCE_REVIEW_PREFLIGHT_SCHEMA,
    LSWR_RUNTIME_EXECUTOR_VERIFIED_OUTCOME_INGESTION_ADMISSION_DECISION_SCHEMA,
};
use anyhow::{bail, Context, Result};
use serde_json::{json, Value};

fn main() -> Result<()> {
    let args = Args::parse(std::env::args().skip(1))?;
    let review_preflight = fixture_verified_outcome_ingestion_write_evidence_review_preflight();
    let input = if args.with_verified_outcome_ingestion_admission_decision {
        json!({
            "verified_outcome_ingestion_write_evidence_review_preflight": review_preflight,
            "verified_outcome_ingestion_admission_decision":
                fixture_verified_outcome_ingestion_admission_decision()
        })
    } else {
        review_preflight
    };
    let admission_preflight =
        build_interaction_feedback_runtime_executor_verified_outcome_ingestion_admission_preflight(
            &input,
        );
    let markdown =
        render_interaction_feedback_runtime_executor_verified_outcome_ingestion_admission_preflight(
            &admission_preflight,
        );

    if args.assert_blocked_without_verified_outcome_ingestion_admission_decision {
        assert_blocked_without_verified_outcome_ingestion_admission_decision(&admission_preflight)?;
    }
    if args.assert_ready_for_verified_outcome_ingestion_execution {
        assert_ready_for_verified_outcome_ingestion_execution(&admission_preflight)?;
    }
    if args.assert_output_only {
        assert_output_only_contract(&admission_preflight)?;
    }

    match args.format {
        OutputFormat::Markdown => println!("{markdown}"),
        OutputFormat::Json => println!("{}", serde_json::to_string_pretty(&admission_preflight)?),
        OutputFormat::Both => {
            println!("{markdown}");
            println!("{}", serde_json::to_string_pretty(&admission_preflight)?);
        }
    }

    Ok(())
}

fn fixture_verified_outcome_ingestion_write_evidence_review_preflight() -> Value {
    let scope = fixture_scope();
    json!({
        "schema": LSWR_INTERACTION_FEEDBACK_RUNTIME_EXECUTOR_VERIFIED_OUTCOME_INGESTION_WRITE_EVIDENCE_REVIEW_PREFLIGHT_SCHEMA,
        "input_kind": "verified_outcome_ingestion_write_evidence_preflight_with_review_decision_wrapper",
        "source_schema": "agent_bridge.lswr.interaction_feedback_runtime_executor_verified_outcome_ingestion_write_evidence_preflight.v0",
        "source_verified_outcome_ingestion_write_evidence_preflight_verdict": "ready_for_verified_outcome_ingestion_write_evidence_review",
        "source_world_verdict": "not_verified",
        "verified_world_verdict": "verified",
        "verified_outcome_ingestion_write_evidence_review_decision_schema": "agent_bridge.lswr.runtime_executor.verified_outcome_ingestion_write_evidence_review_decision.v0",
        "verified_outcome_ingestion_write_evidence_review_preflight_verdict": "ready_for_verified_outcome_ingestion_admission",
        "status": "ready",
        "reason": "verified_outcome_ingestion_write_evidence_review_preflight_ready_for_admission",
        "failure_reasons": [],
        "guardrails": {
            "read_only": true,
            "mutation_surface": "output_only",
            "writes_state": false,
            "store_access_required": false,
            "mcp_tool_registered": false,
            "queries_live_runtime": false,
            "requires_ready_verified_outcome_ingestion_write_evidence_preflight": true,
            "requires_explicit_verified_outcome_ingestion_write_evidence_review_decision": true,
            "review_kind": "verified_outcome_ingestion_write_evidence_review",
            "performs_verified_outcome_ingestion_write_evidence_review_preflight": true,
            "performs_verified_outcome_admission": false,
            "performs_verified_outcome_store_write": false,
            "performs_verified_outcome_ingestion": false,
            "persists_world_verdict": false,
            "durable_outcome_record_written": false,
            "memory_write_allowed": false,
            "outcome_ingestion_allowed_by_this_tool": false,
            "verified_outcome_admission_allowed": false,
            "verified_outcome_store_written_by_this_tool": false,
            "persists_outcome_record": false,
            "runtime_executor_verified_outcome_ingestion_write_evidence_review_preflight_only": true
        },
        "verified_outcome_ingestion_write_evidence_review": {
            "review_decision_id": "verified_outcome_ingestion_write_evidence_review_arrival_bath_move_002",
            "write_evidence_id": "verified_outcome_ingestion_write_evidence_arrival_bath_move_002",
            "store_write_execution_id": scope["store_write_execution_id"],
            "persistence_decision_id": scope["persistence_decision_id"],
            "persistence_source_execution_id": scope["persistence_source_execution_id"],
            "writer_decision_id": scope["writer_decision_id"],
            "apply_decision_id": scope["apply_decision_id"],
            "commit_decision_id": scope["commit_decision_id"],
            "source_execution_decision_id": scope["source_execution_decision_id"],
            "source_ingestion_decision_id": scope["source_ingestion_decision_id"],
            "source_rewrite_decision_id": scope["source_rewrite_decision_id"],
            "source_review_decision_id": scope["source_review_decision_id"],
            "source_write_evidence_id": scope["source_write_evidence_id"],
            "world_id": scope["world_id"],
            "branch_id": scope["branch_id"],
            "runtime_generation": scope["runtime_generation"],
            "patch_id": scope["patch_id"],
            "review_kind": "verified_outcome_ingestion_write_evidence_review",
            "decision": "approved_for_verified_outcome_ingestion_admission",
            "review_reason": "verified_outcome_ingestion_write_evidence_is_scoped_and_ready_for_separate_admission",
            "previous_world_verdict": "not_verified",
            "verified_world_verdict": "verified",
            "outcome_record_candidate_id": scope["outcome_record_candidate_id"],
            "outcome_record_schema": scope["outcome_record_schema"],
            "idempotency_key": scope["idempotency_key"],
            "outcome_payload_digest": scope["outcome_payload_digest"],
            "write_destination": scope["write_destination"],
            "outcome_record_key": scope["outcome_record_key"],
            "outcome_record_digest": scope["outcome_record_digest"],
            "persisted_outcome_record_key": scope["persisted_outcome_record_key"],
            "persisted_outcome_record_digest": scope["persisted_outcome_record_digest"],
            "verified_outcome_store_write_confirmed": true,
            "store_ack_confirmed": true,
            "record_readback_confirmed": true,
            "outcome_record_digest_confirmed": true,
            "idempotency_key_confirmed": true,
            "persisted_key_confirmed": true,
            "persisted_digest_confirmed": true,
            "reviewer_attestation_present": true,
            "ready_for_verified_outcome_ingestion_admission": true,
            "verified_outcome_admission_allowed": false,
            "verified_outcome_store_written_by_this_tool": false,
            "verified_outcome_ingested_by_this_tool": false,
            "world_verdict_persisted_by_this_tool": false,
            "durable_outcome_record_written_by_this_tool": false,
            "memory_write_allowed": false,
            "outcome_ingestion_allowed_by_this_tool": false
        },
        "next_allowed_gate": "verified_outcome_ingestion_admission",
        "agent_action_contract": {
            "mode": "runtime_executor_verified_outcome_ingestion_write_evidence_review_preflight_only",
            "may_enter_verified_outcome_ingestion_admission_after_preflight": true,
            "may_execute_verified_outcome_admission_by_this_tool": false,
            "may_execute_verified_outcome_ingestion_by_this_tool": false,
            "do_not_ingest_outcome": true,
            "do_not_write_memory": true,
            "do_not_persist_world_verdict": true,
            "do_not_persist_outcome_record": true,
            "require_separate_verified_outcome_ingestion_admission": true
        },
        "verified_outcome_ingestion_write_evidence_review_preflight_performed_by_this_tool": true,
        "verified_outcome_store_written_by_this_tool": false,
        "verified_outcome_ingestion_performed_by_this_tool": false,
        "verified_outcome_ingested_by_this_tool": false,
        "world_verdict_persisted_by_this_tool": false,
        "durable_outcome_record_written_by_this_tool": false,
        "durable_outcome_ingestion_performed_by_this_tool": false,
        "writes_state": false,
        "store_access_required": false,
        "mcp_tool_registered": false
    })
}

fn fixture_verified_outcome_ingestion_admission_decision() -> Value {
    let scope = fixture_scope();
    json!({
        "schema": LSWR_RUNTIME_EXECUTOR_VERIFIED_OUTCOME_INGESTION_ADMISSION_DECISION_SCHEMA,
        "admission_decision_id": "verified_outcome_ingestion_admission_arrival_bath_move_002",
        "admission_kind": "verified_outcome_ingestion_admission",
        "source_verified_outcome_ingestion_admission_scope": {
            "review_decision_id": "verified_outcome_ingestion_write_evidence_review_arrival_bath_move_002",
            "write_evidence_id": "verified_outcome_ingestion_write_evidence_arrival_bath_move_002",
            "store_write_execution_id": scope["store_write_execution_id"],
            "persistence_decision_id": scope["persistence_decision_id"],
            "persistence_source_execution_id": scope["persistence_source_execution_id"],
            "writer_decision_id": scope["writer_decision_id"],
            "apply_decision_id": scope["apply_decision_id"],
            "commit_decision_id": scope["commit_decision_id"],
            "source_execution_decision_id": scope["source_execution_decision_id"],
            "source_ingestion_decision_id": scope["source_ingestion_decision_id"],
            "source_rewrite_decision_id": scope["source_rewrite_decision_id"],
            "source_review_decision_id": scope["source_review_decision_id"],
            "source_write_evidence_id": scope["source_write_evidence_id"],
            "world_id": scope["world_id"],
            "branch_id": scope["branch_id"],
            "runtime_generation": scope["runtime_generation"],
            "patch_id": scope["patch_id"],
            "outcome_record_candidate_id": scope["outcome_record_candidate_id"],
            "outcome_record_schema": scope["outcome_record_schema"],
            "idempotency_key": scope["idempotency_key"],
            "outcome_payload_digest": scope["outcome_payload_digest"],
            "write_destination": scope["write_destination"],
            "outcome_record_key": scope["outcome_record_key"],
            "outcome_record_digest": scope["outcome_record_digest"],
            "persisted_outcome_record_key": scope["persisted_outcome_record_key"],
            "persisted_outcome_record_digest": scope["persisted_outcome_record_digest"]
        },
        "decision": "approved_for_verified_outcome_ingestion_execution",
        "admission_reason": "verified_outcome_ingestion_write_evidence_review_is_scoped_and_ready_for_separate_execution",
        "source_world_verdict": "not_verified",
        "verified_world_verdict": "verified",
        "reviewed_admission_preflight_verdict": "ready_for_verified_outcome_ingestion_admission",
        "write_evidence_review_preflight_confirmed": true,
        "write_evidence_review_decision_confirmed": true,
        "verified_outcome_store_write_confirmed": true,
        "store_ack_confirmed": true,
        "record_readback_confirmed": true,
        "outcome_record_digest_confirmed": true,
        "idempotency_key_confirmed": true,
        "persisted_key_confirmed": true,
        "persisted_digest_confirmed": true,
        "operator_attestation_present": true,
        "verified_outcome_ingestion_execution_allowed": false,
        "outcome_ingestion_allowed_by_this_tool": false,
        "memory_write_allowed": false,
        "world_verdict_persisted_by_this_tool": false,
        "verified_outcome_ingested_by_this_tool": false,
        "verified_outcome_store_written_by_this_tool": false,
        "durable_outcome_record_written_by_this_tool": false
    })
}

fn fixture_scope() -> Value {
    json!({
        "store_write_execution_id": "verified_outcome_ingestion_store_write_execution_arrival_bath_move_002",
        "persistence_decision_id": "verified_outcome_ingestion_persistence_arrival_bath_move_002",
        "persistence_source_execution_id": "verified_outcome_ingestion_writer_execution_arrival_bath_move_002",
        "writer_decision_id": "verified_outcome_ingestion_writer_arrival_bath_move_002",
        "apply_decision_id": "verified_outcome_ingestion_apply_arrival_bath_move_002",
        "commit_decision_id": "verified_outcome_ingestion_execution_commit_arrival_bath_move_002",
        "source_execution_decision_id": "verified_outcome_ingestion_execution_arrival_bath_move_002",
        "source_ingestion_decision_id": "verified_outcome_ingestion_arrival_bath_move_002",
        "source_rewrite_decision_id": "world_verdict_rewrite_arrival_bath_move_002",
        "source_review_decision_id": "durable_outcome_record_write_evidence_review_arrival_bath_move_002",
        "source_write_evidence_id": "durable_outcome_record_write_evidence_arrival_bath_move_002",
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

fn assert_blocked_without_verified_outcome_ingestion_admission_decision(
    preflight: &Value,
) -> Result<()> {
    assert_eq(
        preflight,
        "verified_outcome_ingestion_admission_preflight_verdict",
        "blocked",
    )?;
    assert_eq(
        preflight,
        "reason",
        "explicit_verified_outcome_ingestion_admission_decision_required",
    )?;
    Ok(())
}

fn assert_ready_for_verified_outcome_ingestion_execution(preflight: &Value) -> Result<()> {
    assert_eq(
        preflight,
        "verified_outcome_ingestion_admission_preflight_verdict",
        "ready_for_verified_outcome_ingestion_execution",
    )?;
    assert_eq(
        preflight,
        "next_allowed_gate",
        "verified_outcome_ingestion_execution",
    )?;
    if preflight["verified_outcome_ingestion_admission"]
        ["ready_for_verified_outcome_ingestion_execution"]
        != true
    {
        bail!("expected ready_for_verified_outcome_ingestion_execution=true");
    }
    Ok(())
}

fn assert_output_only_contract(preflight: &Value) -> Result<()> {
    for key in [
        "writes_state",
        "store_access_required",
        "mcp_tool_registered",
        "verified_outcome_admission_performed_by_this_tool",
        "verified_outcome_store_written_by_this_tool",
        "verified_outcome_ingestion_performed_by_this_tool",
        "verified_outcome_ingested_by_this_tool",
        "world_verdict_persisted_by_this_tool",
        "durable_outcome_record_written_by_this_tool",
        "durable_outcome_ingestion_performed_by_this_tool",
    ] {
        if preflight[key] != false {
            bail!("{key} must be false");
        }
    }
    if preflight["verified_outcome_ingestion_admission_preflight_performed_by_this_tool"] != true {
        bail!("preflight marker must be true");
    }
    for key in [
        "read_only",
        "requires_ready_verified_outcome_ingestion_write_evidence_review_preflight",
        "requires_explicit_verified_outcome_ingestion_admission_decision",
    ] {
        if preflight["guardrails"][key] != true {
            bail!("guardrail {key} must be true");
        }
    }
    for key in [
        "writes_state",
        "store_access_required",
        "mcp_tool_registered",
        "performs_verified_outcome_admission",
        "performs_verified_outcome_store_write",
        "performs_verified_outcome_ingestion",
        "persists_world_verdict",
        "durable_outcome_record_written",
        "memory_write_allowed",
        "outcome_ingestion_allowed_by_this_tool",
        "verified_outcome_ingestion_execution_allowed",
        "verified_outcome_admission_performed_by_this_tool",
        "verified_outcome_store_written_by_this_tool",
        "persists_outcome_record",
    ] {
        if preflight["guardrails"][key] != false {
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
        if preflight["agent_action_contract"][key] != true {
            bail!("agent action contract {key} must be true");
        }
    }
    for key in [
        "may_execute_verified_outcome_admission_by_this_tool",
        "may_execute_verified_outcome_ingestion_by_this_tool",
    ] {
        if preflight["agent_action_contract"][key] != false {
            bail!("agent action contract {key} must be false");
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
    with_verified_outcome_ingestion_admission_decision: bool,
    assert_blocked_without_verified_outcome_ingestion_admission_decision: bool,
    assert_ready_for_verified_outcome_ingestion_execution: bool,
    assert_output_only: bool,
    format: OutputFormat,
}

impl Args {
    fn parse(args: impl Iterator<Item = String>) -> Result<Self> {
        let mut parsed = Self {
            with_verified_outcome_ingestion_admission_decision: false,
            assert_blocked_without_verified_outcome_ingestion_admission_decision: false,
            assert_ready_for_verified_outcome_ingestion_execution: false,
            assert_output_only: false,
            format: OutputFormat::Markdown,
        };
        let mut args = args.peekable();
        while let Some(arg) = args.next() {
            match arg.as_str() {
                "--with-verified-outcome-ingestion-admission"
                | "--with-verified-outcome-ingestion-admission-decision" => {
                    parsed.with_verified_outcome_ingestion_admission_decision = true;
                }
                "--assert-blocked-without-verified-outcome-ingestion-admission"
                | "--assert-blocked-without-verified-outcome-ingestion-admission-decision" => {
                    parsed.assert_blocked_without_verified_outcome_ingestion_admission_decision =
                        true;
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
        "Usage: cargo run -p ab-bridge --example lswr_interaction_feedback_runtime_executor_verified_outcome_ingestion_admission_preflight_smoke -- [flags]\n\
\n\
Flags:\n\
  --with-verified-outcome-ingestion-admission-decision\n\
  --assert-blocked-without-verified-outcome-ingestion-admission-decision\n\
  --assert-ready-for-verified-outcome-ingestion-execution\n\
  --assert-output-only\n\
  --format markdown|json|both\n"
    );
}

fn assert_eq(value: &Value, key: &str, expected: &str) -> Result<()> {
    let actual = value
        .get(key)
        .and_then(Value::as_str)
        .with_context(|| format!("missing string key {key}"))?;
    if actual != expected {
        bail!("{key}: expected {expected}, got {actual}");
    }
    Ok(())
}
