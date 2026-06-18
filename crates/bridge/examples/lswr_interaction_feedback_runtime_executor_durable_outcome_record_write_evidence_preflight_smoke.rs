//! Repeatable LSWR durable outcome record write-evidence preflight smoke.
//!
//! This validates supplied external durable outcome record write evidence
//! against a minimal accepted G14 store-write execution preflight. It never
//! writes durable outcome records, touches memory/store rows, registers MCP
//! tools, ingests outcomes, or rewrites world verdicts.

use ab_bridge::lswr_interaction_feedback::{
    build_interaction_feedback_runtime_executor_durable_outcome_record_write_evidence_preflight,
    render_interaction_feedback_runtime_executor_durable_outcome_record_write_evidence_preflight,
    LSWR_INTERACTION_FEEDBACK_RUNTIME_EXECUTOR_DURABLE_OUTCOME_RECORD_STORE_WRITE_EXECUTION_PREFLIGHT_SCHEMA,
    LSWR_RUNTIME_EXECUTOR_DURABLE_OUTCOME_RECORD_WRITE_EVIDENCE_SCHEMA,
};
use anyhow::{bail, Context, Result};
use serde_json::{json, Value};

fn main() -> Result<()> {
    let args = Args::parse(std::env::args().skip(1))?;
    let store_write_preflight = fixture_durable_outcome_record_store_write_execution_preflight();
    let input = if args.with_durable_outcome_record_write_evidence {
        json!({
            "durable_outcome_record_store_write_execution_preflight": store_write_preflight,
            "durable_outcome_record_write_evidence":
                fixture_durable_outcome_record_write_evidence()
        })
    } else {
        store_write_preflight
    };
    let write_evidence_preflight =
        build_interaction_feedback_runtime_executor_durable_outcome_record_write_evidence_preflight(
            &input,
        );
    let markdown =
        render_interaction_feedback_runtime_executor_durable_outcome_record_write_evidence_preflight(
            &write_evidence_preflight,
        );

    if args.assert_blocked_without_durable_outcome_record_write_evidence {
        assert_blocked_without_durable_outcome_record_write_evidence(&write_evidence_preflight)?;
    }
    if args.assert_ready_for_durable_outcome_record_write_evidence_review {
        assert_ready_for_durable_outcome_record_write_evidence_review(&write_evidence_preflight)?;
    }
    if args.assert_read_only {
        assert_read_only_contract(&write_evidence_preflight)?;
    }

    match args.format {
        OutputFormat::Markdown => println!("{markdown}"),
        OutputFormat::Json => println!(
            "{}",
            serde_json::to_string_pretty(&write_evidence_preflight)?
        ),
        OutputFormat::Both => {
            println!("{markdown}");
            println!(
                "{}",
                serde_json::to_string_pretty(&write_evidence_preflight)?
            );
        }
    }

    Ok(())
}

fn fixture_durable_outcome_record_store_write_execution_preflight() -> Value {
    let scope = fixture_record_scope();
    json!({
        "schema": LSWR_INTERACTION_FEEDBACK_RUNTIME_EXECUTOR_DURABLE_OUTCOME_RECORD_STORE_WRITE_EXECUTION_PREFLIGHT_SCHEMA,
        "durable_outcome_record_store_write_execution_preflight_verdict": "ready_for_durable_outcome_record_write_evidence",
        "status": "ready",
        "reason": "durable_outcome_record_store_write_execution_preflight_ready_for_write_evidence",
        "source_world_verdict": "not_verified",
        "failure_reasons": [],
        "guardrails": {
            "read_only": true,
            "mutation_surface": "none",
            "writes_state": false,
            "store_access_required": false,
            "mcp_tool_registered": false,
            "queries_live_runtime": false,
            "requires_ready_durable_outcome_record_persistence_preflight": true,
            "requires_explicit_durable_outcome_record_store_write_execution_decision": true,
            "store_write_execution_kind": "durable_outcome_record_store_write_execution",
            "performs_durable_outcome_record_store_write_execution_preflight": true,
            "durable_store_write_execution_allowed": false,
            "durable_outcome_record_written": false,
            "memory_write_allowed": false,
            "persists_outcome_record": false,
            "feedback_changes_world_verdict_allowed": false,
            "runtime_executor_durable_outcome_record_store_write_execution_preflight_only": true
        },
        "agent_action_contract": {
            "mode": "runtime_executor_durable_outcome_record_store_write_execution_preflight_only",
            "may_execute_durable_outcome_record_store_write_after_preflight": true,
            "do_not_ingest_outcome": true,
            "do_not_write_memory": true,
            "do_not_rewrite_world_verdict": true,
            "do_not_persist_outcome_record": true,
            "require_separate_durable_outcome_record_store_write_execution": true,
            "require_world_verdict_rewrite_gate_after_ingestion": true
        },
        "durable_outcome_record_store_write_execution": {
            "store_write_execution_id": "durable_outcome_record_store_write_execution_arrival_bath_move_002",
            "persistence_id": scope["persistence_id"],
            "record_write_execution_id": scope["record_write_execution_id"],
            "record_write_id": scope["record_write_id"],
            "write_implementation_id": scope["write_implementation_id"],
            "execution_id": scope["execution_id"],
            "gate_id": scope["gate_id"],
            "review_id": scope["review_id"],
            "verification_id": scope["verification_id"],
            "runtime_application_evidence_id": scope["runtime_application_evidence_id"],
            "source_invocation_request_id": scope["source_invocation_request_id"],
            "world_id": scope["world_id"],
            "branch_id": scope["branch_id"],
            "runtime_generation": scope["runtime_generation"],
            "patch_id": scope["patch_id"],
            "decision": "approved_for_durable_outcome_record_write_evidence",
            "outcome_record_candidate_id": scope["outcome_record_candidate_id"],
            "outcome_record_schema": scope["outcome_record_schema"],
            "idempotency_key": scope["idempotency_key"],
            "outcome_payload_digest": scope["outcome_payload_digest"],
            "write_plan_id": scope["write_plan_id"],
            "write_destination": scope["write_destination"],
            "outcome_record_key": scope["outcome_record_key"],
            "outcome_record_digest": scope["outcome_record_digest"],
            "ready_for_durable_outcome_record_write_evidence": true,
            "durable_store_write_execution_allowed": false,
            "durable_outcome_record_written_by_this_tool": false,
            "memory_write_allowed": false,
            "world_verdict_rewrite_allowed": false
        },
        "writes_state": false,
        "store_access_required": false,
        "mcp_tool_registered": false
    })
}

fn fixture_durable_outcome_record_write_evidence() -> Value {
    let scope = fixture_record_scope();
    json!({
        "schema": LSWR_RUNTIME_EXECUTOR_DURABLE_OUTCOME_RECORD_WRITE_EVIDENCE_SCHEMA,
        "write_evidence_id": "durable_outcome_record_write_evidence_arrival_bath_move_002",
        "evidence_kind": "durable_outcome_record_write_evidence",
        "write_evidence_observed_at": "2026-06-16T08:05:00Z",
        "source_durable_outcome_record_store_write_execution_scope": {
            "store_write_execution_id": "durable_outcome_record_store_write_execution_arrival_bath_move_002",
            "persistence_id": scope["persistence_id"],
            "record_write_execution_id": scope["record_write_execution_id"],
            "record_write_id": scope["record_write_id"],
            "write_implementation_id": scope["write_implementation_id"],
            "execution_id": scope["execution_id"],
            "gate_id": scope["gate_id"],
            "review_id": scope["review_id"],
            "verification_id": scope["verification_id"],
            "runtime_application_evidence_id": scope["runtime_application_evidence_id"],
            "source_invocation_request_id": scope["source_invocation_request_id"],
            "world_id": scope["world_id"],
            "branch_id": scope["branch_id"],
            "runtime_generation": scope["runtime_generation"],
            "patch_id": scope["patch_id"],
            "outcome_record_candidate_id": scope["outcome_record_candidate_id"],
            "outcome_record_schema": scope["outcome_record_schema"],
            "idempotency_key": scope["idempotency_key"],
            "outcome_payload_digest": scope["outcome_payload_digest"],
            "write_plan_id": scope["write_plan_id"],
            "write_destination": scope["write_destination"],
            "outcome_record_key": scope["outcome_record_key"],
            "outcome_record_digest": scope["outcome_record_digest"]
        },
        "write_evidence_reason": "external_store_ack_and_readback_confirm_scoped_outcome_record",
        "source_world_verdict": "not_verified",
        "reviewed_store_write_execution_decision": "approved_for_durable_outcome_record_write_evidence",
        "durable_outcome_record_write_observed": true,
        "store_write_acknowledged": true,
        "record_readback_verified": true,
        "outcome_record_digest_verified": true,
        "idempotency_key_confirmed": true,
        "write_destination": scope["write_destination"],
        "outcome_record_key": scope["outcome_record_key"],
        "outcome_record_digest": scope["outcome_record_digest"],
        "persisted_outcome_record_key": scope["outcome_record_key"],
        "persisted_outcome_record_digest": scope["outcome_record_digest"],
        "durable_outcome_record_written_by_this_tool": false,
        "memory_write_allowed": false,
        "outcome_ingestion_allowed": false,
        "world_verdict_rewrite_allowed": false
    })
}

fn fixture_record_scope() -> Value {
    json!({
        "persistence_id": "durable_outcome_record_persistence_arrival_bath_move_002",
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
    })
}

fn assert_blocked_without_durable_outcome_record_write_evidence(preflight: &Value) -> Result<()> {
    assert_eq(
        &preflight["durable_outcome_record_write_evidence_preflight_verdict"],
        "blocked",
        "write-evidence preflight verdict",
    )?;
    assert_eq(
        &preflight["reason"],
        "explicit_durable_outcome_record_write_evidence_required",
        "blocked reason",
    )?;
    Ok(())
}

fn assert_ready_for_durable_outcome_record_write_evidence_review(preflight: &Value) -> Result<()> {
    assert_eq(
        &preflight["durable_outcome_record_write_evidence_preflight_verdict"],
        "ready_for_durable_outcome_record_write_evidence_review",
        "write-evidence preflight verdict",
    )?;
    assert_eq(&preflight["status"], "ready", "status")?;
    assert_eq(
        &preflight["durable_outcome_record_write_evidence"]
            ["ready_for_durable_outcome_record_write_evidence_review"],
        true,
        "ready flag",
    )?;
    assert_eq(
        &preflight["durable_outcome_record_write_evidence"]
            ["durable_outcome_record_write_observed"],
        true,
        "write observed",
    )?;
    assert_eq(
        &preflight["durable_outcome_record_write_evidence"]["store_write_execution_id"],
        "durable_outcome_record_store_write_execution_arrival_bath_move_002",
        "store write execution id",
    )?;
    Ok(())
}

fn assert_read_only_contract(preflight: &Value) -> Result<()> {
    for (path, actual) in [
        ("writes_state", &preflight["writes_state"]),
        ("store_access_required", &preflight["store_access_required"]),
        ("mcp_tool_registered", &preflight["mcp_tool_registered"]),
        (
            "durable_outcome_record_written_by_this_tool",
            &preflight["durable_outcome_record_written_by_this_tool"],
        ),
        (
            "durable_outcome_ingestion_performed_by_this_tool",
            &preflight["durable_outcome_ingestion_performed_by_this_tool"],
        ),
        (
            "world_verdict_rewrite_performed_by_this_tool",
            &preflight["world_verdict_rewrite_performed_by_this_tool"],
        ),
        (
            "guardrails.writes_state",
            &preflight["guardrails"]["writes_state"],
        ),
        (
            "guardrails.store_access_required",
            &preflight["guardrails"]["store_access_required"],
        ),
        (
            "guardrails.persists_outcome_record",
            &preflight["guardrails"]["persists_outcome_record"],
        ),
        (
            "durable_outcome_record_write_evidence.durable_outcome_record_written_by_this_tool",
            &preflight["durable_outcome_record_write_evidence"]
                ["durable_outcome_record_written_by_this_tool"],
        ),
        (
            "durable_outcome_record_write_evidence.memory_write_allowed",
            &preflight["durable_outcome_record_write_evidence"]["memory_write_allowed"],
        ),
        (
            "durable_outcome_record_write_evidence.outcome_ingestion_allowed",
            &preflight["durable_outcome_record_write_evidence"]["outcome_ingestion_allowed"],
        ),
        (
            "durable_outcome_record_write_evidence.world_verdict_rewrite_allowed",
            &preflight["durable_outcome_record_write_evidence"]["world_verdict_rewrite_allowed"],
        ),
    ] {
        assert_eq(actual, false, path)?;
    }
    assert_eq(
        &preflight["guardrails"]["read_only"],
        true,
        "guardrails.read_only",
    )?;
    assert_eq(
        &preflight["agent_action_contract"]["do_not_persist_outcome_record"],
        true,
        "agent_action_contract.do_not_persist_outcome_record",
    )?;
    Ok(())
}

fn assert_eq(actual: &Value, expected: impl Into<Value>, label: &str) -> Result<()> {
    let expected = expected.into();
    if actual != &expected {
        bail!("{label}: expected {expected}, got {actual}");
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
    with_durable_outcome_record_write_evidence: bool,
    assert_blocked_without_durable_outcome_record_write_evidence: bool,
    assert_ready_for_durable_outcome_record_write_evidence_review: bool,
    assert_read_only: bool,
    format: OutputFormat,
}

impl Args {
    fn parse(args: impl IntoIterator<Item = String>) -> Result<Self> {
        let mut with_durable_outcome_record_write_evidence = false;
        let mut assert_blocked_without_durable_outcome_record_write_evidence = false;
        let mut assert_ready_for_durable_outcome_record_write_evidence_review = false;
        let mut assert_read_only = false;
        let mut format = OutputFormat::Markdown;

        let mut args = args.into_iter();
        while let Some(arg) = args.next() {
            match arg.as_str() {
                "--with-durable-outcome-record-write-evidence" => {
                    with_durable_outcome_record_write_evidence = true;
                }
                "--assert-blocked-without-durable-outcome-record-write-evidence" => {
                    assert_blocked_without_durable_outcome_record_write_evidence = true;
                }
                "--assert-ready-for-durable-outcome-record-write-evidence-review" => {
                    assert_ready_for_durable_outcome_record_write_evidence_review = true;
                }
                "--assert-read-only" => assert_read_only = true,
                "--format" => {
                    let value = args
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
            with_durable_outcome_record_write_evidence,
            assert_blocked_without_durable_outcome_record_write_evidence,
            assert_ready_for_durable_outcome_record_write_evidence_review,
            assert_read_only,
            format,
        })
    }
}

fn print_help() {
    println!(
        "Usage: cargo run -p ab-bridge --example lswr_interaction_feedback_runtime_executor_durable_outcome_record_write_evidence_preflight_smoke -- [flags]\n\
\n\
Flags:\n\
  --with-durable-outcome-record-write-evidence\n\
  --assert-blocked-without-durable-outcome-record-write-evidence\n\
  --assert-ready-for-durable-outcome-record-write-evidence-review\n\
  --assert-read-only\n\
  --format markdown|json|both\n"
    );
}
