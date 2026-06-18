//! Repeatable LSWR interaction-feedback durable outcome record persistence preflight smoke.
//!
//! This validates an explicit durable outcome record persistence decision
//! against a minimal accepted G12 durable outcome record-write execution
//! preflight. It never writes durable outcome records, touches memory/store
//! rows, registers MCP tools, or rewrites world verdicts.

use ab_bridge::lswr_interaction_feedback::{
    build_interaction_feedback_runtime_executor_durable_outcome_record_persistence_preflight,
    render_interaction_feedback_runtime_executor_durable_outcome_record_persistence_preflight,
    LSWR_INTERACTION_FEEDBACK_RUNTIME_EXECUTOR_DURABLE_OUTCOME_RECORD_WRITE_EXECUTION_PREFLIGHT_SCHEMA,
    LSWR_RUNTIME_EXECUTOR_DURABLE_OUTCOME_RECORD_PERSISTENCE_DECISION_SCHEMA,
    LSWR_RUNTIME_EXECUTOR_DURABLE_OUTCOME_RECORD_WRITE_EXECUTION_DECISION_SCHEMA,
};
use anyhow::{bail, Context, Result};
use serde_json::{json, Value};

fn main() -> Result<()> {
    let args = Args::parse(std::env::args().skip(1))?;
    let execution_preflight = fixture_durable_outcome_record_write_execution_preflight();
    let input = if args.with_durable_outcome_record_persistence_decision {
        json!({
            "durable_outcome_record_write_execution_preflight": execution_preflight,
            "durable_outcome_record_persistence_decision": fixture_durable_outcome_record_persistence_decision()
        })
    } else {
        execution_preflight
    };
    let persistence_preflight =
        build_interaction_feedback_runtime_executor_durable_outcome_record_persistence_preflight(
            &input,
        );
    let markdown =
        render_interaction_feedback_runtime_executor_durable_outcome_record_persistence_preflight(
            &persistence_preflight,
        );

    if args.assert_blocked_without_durable_outcome_record_persistence_decision {
        assert_blocked_without_durable_outcome_record_persistence_decision(&persistence_preflight)?;
    }
    if args.assert_ready_for_durable_outcome_record_persistence_execution {
        assert_ready_for_durable_outcome_record_persistence_execution(&persistence_preflight)?;
    }
    if args.assert_read_only {
        assert_read_only_contract(&persistence_preflight)?;
    }

    match args.format {
        OutputFormat::Markdown => println!("{markdown}"),
        OutputFormat::Json => println!("{}", serde_json::to_string_pretty(&persistence_preflight)?),
        OutputFormat::Both => {
            println!("{markdown}");
            println!("{}", serde_json::to_string_pretty(&persistence_preflight)?);
        }
    }

    Ok(())
}

fn fixture_durable_outcome_record_write_execution_preflight() -> Value {
    json!({
        "schema": LSWR_INTERACTION_FEEDBACK_RUNTIME_EXECUTOR_DURABLE_OUTCOME_RECORD_WRITE_EXECUTION_PREFLIGHT_SCHEMA,
        "source_world_verdict": "not_verified",
        "durable_outcome_record_write_execution_preflight_verdict": "ready_for_durable_outcome_record_persistence",
        "status": "ready",
        "reason": "durable_outcome_record_write_execution_preflight_ready_for_persistence",
        "failure_reasons": [],
        "guardrails": {
            "read_only": true,
            "mutation_surface": "none",
            "writes_state": false,
            "store_access_required": false,
            "mcp_tool_registered": false,
            "queries_live_runtime": false,
            "requires_ready_durable_outcome_record_write_preflight": true,
            "requires_explicit_durable_outcome_record_write_execution_decision": true,
            "record_write_execution_kind": "durable_outcome_record_write_execution",
            "performs_durable_outcome_record_write_execution_preflight": true,
            "durable_record_persistence_allowed": false,
            "durable_outcome_record_written": false,
            "memory_write_allowed": false,
            "persists_outcome_record": false,
            "feedback_changes_world_verdict_allowed": false,
            "runtime_executor_durable_outcome_record_write_execution_preflight_only": true
        },
        "agent_action_contract": {
            "mode": "runtime_executor_durable_outcome_record_write_execution_preflight_only",
            "may_persist_durable_outcome_record_after_preflight": true,
            "do_not_ingest_outcome": true,
            "do_not_write_memory": true,
            "do_not_rewrite_world_verdict": true,
            "do_not_persist_outcome_record": true,
            "require_separate_durable_outcome_record_persistence": true,
            "require_world_verdict_rewrite_gate_after_ingestion": true
        },
        "durable_outcome_record_write_execution": {
            "record_write_execution_id": "durable_outcome_record_write_execution_arrival_bath_move_002",
            "record_write_id": "durable_outcome_record_write_arrival_bath_move_002",
            "write_implementation_id": "durable_outcome_write_impl_arrival_bath_move_002",
            "execution_id": "durable_outcome_ingestion_execution_arrival_bath_move_002",
            "gate_id": "durable_outcome_ingestion_gate_arrival_bath_move_002",
            "review_id": "outcome_ingestion_review_arrival_bath_move_002",
            "verification_id": "post_apply_verification_arrival_bath_move_002",
            "runtime_application_evidence_id": "runtime_application_evidence_arrival_bath_move_002",
            "source_invocation_request_id": "patch_executor_invocation_arrival_bath_move_002",
            "world_id": "onsen_live_session",
            "branch_id": "main",
            "runtime_generation": "runtime_gen_1284",
            "patch_id": "patch_arrival_bath_move_002",
            "decision": "approved_for_durable_outcome_record_persistence",
            "record_write_execution_reason": "record_write_preflight_ready_for_later_durable_persistence",
            "outcome_record_candidate_id": "outcome_record_candidate_arrival_bath_move_002",
            "outcome_record_schema": "agent_bridge.lswr.outcome_record_candidate.v0",
            "idempotency_key": "onsen_live_session/main/runtime_gen_1284/patch_arrival_bath_move_002/outcome_ingestion_review_arrival_bath_move_002",
            "outcome_payload_digest": "sha256:arrival-bath-move-002-outcome-payload",
            "write_plan_id": "durable_outcome_write_plan_arrival_bath_move_002",
            "write_destination": "agent_bridge_store_outcome_records",
            "outcome_record_key": "onsen_live_session/main/runtime_gen_1284/patch_arrival_bath_move_002/outcome_record_candidate_arrival_bath_move_002",
            "outcome_record_digest": "sha256:arrival-bath-move-002-outcome-record",
            "write_destination_verified": true,
            "outcome_record_digest_verified": true,
            "idempotent_upsert_confirmed": true,
            "store_transaction_plan_complete": true,
            "ready_for_durable_outcome_record_persistence": true,
            "durable_record_persistence_allowed": false,
            "durable_outcome_record_written_by_this_tool": false,
            "memory_write_allowed": false,
            "world_verdict_rewrite_allowed": false
        },
        "durable_outcome_record_write_execution_decision": {
            "schema": LSWR_RUNTIME_EXECUTOR_DURABLE_OUTCOME_RECORD_WRITE_EXECUTION_DECISION_SCHEMA
        }
    })
}

fn fixture_durable_outcome_record_persistence_decision() -> Value {
    json!({
        "schema": LSWR_RUNTIME_EXECUTOR_DURABLE_OUTCOME_RECORD_PERSISTENCE_DECISION_SCHEMA,
        "record_persistence_id": "durable_outcome_record_persistence_arrival_bath_move_002",
        "record_persistence_kind": "durable_outcome_record_persistence",
        "record_persistence_preflighted_at": "2026-06-16T07:55:00Z",
        "source_durable_outcome_record_write_execution_scope": {
            "record_write_execution_id": "durable_outcome_record_write_execution_arrival_bath_move_002",
            "record_write_id": "durable_outcome_record_write_arrival_bath_move_002",
            "write_implementation_id": "durable_outcome_write_impl_arrival_bath_move_002",
            "execution_id": "durable_outcome_ingestion_execution_arrival_bath_move_002",
            "gate_id": "durable_outcome_ingestion_gate_arrival_bath_move_002",
            "review_id": "outcome_ingestion_review_arrival_bath_move_002",
            "verification_id": "post_apply_verification_arrival_bath_move_002",
            "runtime_application_evidence_id": "runtime_application_evidence_arrival_bath_move_002",
            "source_invocation_request_id": "patch_executor_invocation_arrival_bath_move_002",
            "world_id": "onsen_live_session",
            "branch_id": "main",
            "runtime_generation": "runtime_gen_1284",
            "patch_id": "patch_arrival_bath_move_002",
            "outcome_record_candidate_id": "outcome_record_candidate_arrival_bath_move_002",
            "outcome_record_schema": "agent_bridge.lswr.outcome_record_candidate.v0",
            "idempotency_key": "onsen_live_session/main/runtime_gen_1284/patch_arrival_bath_move_002/outcome_ingestion_review_arrival_bath_move_002",
            "outcome_payload_digest": "sha256:arrival-bath-move-002-outcome-payload",
            "write_plan_id": "durable_outcome_write_plan_arrival_bath_move_002",
            "write_destination": "agent_bridge_store_outcome_records",
            "outcome_record_key": "onsen_live_session/main/runtime_gen_1284/patch_arrival_bath_move_002/outcome_record_candidate_arrival_bath_move_002",
            "outcome_record_digest": "sha256:arrival-bath-move-002-outcome-record"
        },
        "decision": "approved_for_durable_outcome_record_persistence_execution",
        "record_persistence_reason": "record_write_execution_preflight_ready_for_later_persistence_execution",
        "source_world_verdict": "not_verified",
        "reviewed_record_write_execution_decision": "approved_for_durable_outcome_record_persistence",
        "write_destination_verified": true,
        "outcome_record_digest_verified": true,
        "idempotent_upsert_confirmed": true,
        "store_transaction_plan_complete": true,
        "write_destination": "agent_bridge_store_outcome_records",
        "outcome_record_key": "onsen_live_session/main/runtime_gen_1284/patch_arrival_bath_move_002/outcome_record_candidate_arrival_bath_move_002",
        "outcome_record_digest": "sha256:arrival-bath-move-002-outcome-record",
        "durable_record_persistence_execution_allowed": false,
        "durable_outcome_record_written": false,
        "memory_write_allowed": false,
        "world_verdict_rewrite_allowed": false
    })
}

fn assert_blocked_without_durable_outcome_record_persistence_decision(
    preflight: &Value,
) -> Result<()> {
    if preflight
        .get("durable_outcome_record_persistence_preflight_verdict")
        .and_then(Value::as_str)
        != Some("blocked")
    {
        bail!("durable outcome record persistence preflight must block without decision");
    }
    if preflight.get("reason").and_then(Value::as_str)
        != Some("explicit_durable_outcome_record_persistence_decision_required")
    {
        bail!(
            "blocked preflight must require explicit durable outcome record persistence decision"
        );
    }
    Ok(())
}

fn assert_ready_for_durable_outcome_record_persistence_execution(preflight: &Value) -> Result<()> {
    if preflight
        .get("durable_outcome_record_persistence_preflight_verdict")
        .and_then(Value::as_str)
        != Some("ready_for_durable_outcome_record_persistence_execution")
    {
        bail!("durable outcome record persistence preflight must be ready for execution");
    }
    if preflight["durable_outcome_record_persistence"]["decision"].as_str()
        != Some("approved_for_durable_outcome_record_persistence_execution")
    {
        bail!("ready preflight must carry explicit record persistence execution decision");
    }
    if preflight["durable_outcome_record_persistence"]
        ["durable_record_persistence_execution_allowed"]
        .as_bool()
        != Some(false)
    {
        bail!("durable outcome record persistence preflight must not allow execution");
    }
    if preflight["durable_outcome_record_persistence"]
        ["durable_outcome_record_written_by_this_tool"]
        .as_bool()
        != Some(false)
    {
        bail!("durable outcome record persistence preflight must not write outcome records");
    }
    Ok(())
}

fn assert_read_only_contract(preflight: &Value) -> Result<()> {
    for key in [
        "durable_outcome_record_written_by_this_tool",
        "durable_outcome_ingestion_performed_by_this_tool",
        "world_verdict_rewrite_performed_by_this_tool",
        "writes_state",
        "store_access_required",
        "mcp_tool_registered",
    ] {
        if preflight.get(key).and_then(Value::as_bool) != Some(false) {
            bail!("durable outcome record persistence preflight {key} must be false");
        }
    }
    Ok(())
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
enum OutputFormat {
    Markdown,
    Json,
    Both,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
struct Args {
    with_durable_outcome_record_persistence_decision: bool,
    assert_blocked_without_durable_outcome_record_persistence_decision: bool,
    assert_ready_for_durable_outcome_record_persistence_execution: bool,
    assert_read_only: bool,
    format: OutputFormat,
}

impl Args {
    fn parse(args: impl IntoIterator<Item = String>) -> Result<Self> {
        let mut with_durable_outcome_record_persistence_decision = false;
        let mut assert_blocked_without_durable_outcome_record_persistence_decision = false;
        let mut assert_ready_for_durable_outcome_record_persistence_execution = false;
        let mut assert_read_only = false;
        let mut format = OutputFormat::Markdown;
        let mut iter = args.into_iter();

        while let Some(arg) = iter.next() {
            match arg.as_str() {
                "--with-durable-outcome-record-persistence-decision" => {
                    with_durable_outcome_record_persistence_decision = true
                }
                "--assert-blocked-without-durable-outcome-record-persistence-decision" => {
                    assert_blocked_without_durable_outcome_record_persistence_decision = true
                }
                "--assert-ready-for-durable-outcome-record-persistence-execution" => {
                    assert_ready_for_durable_outcome_record_persistence_execution = true
                }
                "--assert-read-only" => assert_read_only = true,
                "--format" => {
                    let value = iter
                        .next()
                        .context("--format requires markdown|json|both")?;
                    format = match value.as_str() {
                        "markdown" => OutputFormat::Markdown,
                        "json" => OutputFormat::Json,
                        "both" => OutputFormat::Both,
                        other => bail!("unsupported format {other:?}"),
                    };
                }
                "-h" | "--help" => {
                    print_help();
                    std::process::exit(0);
                }
                other => bail!("unknown argument {other:?}"),
            }
        }

        Ok(Self {
            with_durable_outcome_record_persistence_decision,
            assert_blocked_without_durable_outcome_record_persistence_decision,
            assert_ready_for_durable_outcome_record_persistence_execution,
            assert_read_only,
            format,
        })
    }
}

fn print_help() {
    println!(
        "Usage: cargo run -p ab-bridge --example lswr_interaction_feedback_runtime_executor_durable_outcome_record_persistence_preflight_smoke -- [flags]\n\
\n\
Flags:\n\
  --with-durable-outcome-record-persistence-decision\n\
  --assert-blocked-without-durable-outcome-record-persistence-decision\n\
  --assert-ready-for-durable-outcome-record-persistence-execution\n\
  --assert-read-only\n\
  --format markdown|json|both\n"
    );
}
