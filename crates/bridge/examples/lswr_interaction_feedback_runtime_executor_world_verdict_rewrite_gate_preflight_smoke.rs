#![recursion_limit = "256"]

//! Repeatable LSWR world-verdict rewrite gate preflight smoke.
//!
//! This validates an explicit gate decision over a minimal accepted G16
//! write-evidence review preflight. It never writes durable outcome records,
//! touches memory/store rows, registers MCP tools, ingests outcomes, or rewrites
//! world verdicts.

use ab_bridge::lswr_interaction_feedback::{
    LSWR_INTERACTION_FEEDBACK_RUNTIME_EXECUTOR_DURABLE_OUTCOME_RECORD_WRITE_EVIDENCE_REVIEW_PREFLIGHT_SCHEMA,
    LSWR_RUNTIME_EXECUTOR_WORLD_VERDICT_REWRITE_GATE_DECISION_SCHEMA,
    build_interaction_feedback_runtime_executor_world_verdict_rewrite_gate_preflight,
    render_interaction_feedback_runtime_executor_world_verdict_rewrite_gate_preflight,
};
use anyhow::{Context, Result, bail};
use serde_json::{Value, json};

fn main() -> Result<()> {
    let args = Args::parse(std::env::args().skip(1))?;
    let review_preflight = fixture_write_evidence_review_preflight();
    let input = if args.with_world_verdict_rewrite_gate_decision {
        json!({
            "durable_outcome_record_write_evidence_review_preflight": review_preflight,
            "world_verdict_rewrite_gate_decision": fixture_world_verdict_rewrite_gate_decision()
        })
    } else {
        review_preflight
    };
    let gate_preflight =
        build_interaction_feedback_runtime_executor_world_verdict_rewrite_gate_preflight(&input);
    let markdown =
        render_interaction_feedback_runtime_executor_world_verdict_rewrite_gate_preflight(
            &gate_preflight,
        );

    if args.assert_blocked_without_world_verdict_rewrite_gate_decision {
        assert_blocked_without_world_verdict_rewrite_gate_decision(&gate_preflight)?;
    }
    if args.assert_ready_for_world_verdict_rewrite_execution {
        assert_ready_for_world_verdict_rewrite_execution(&gate_preflight)?;
    }
    if args.assert_read_only {
        assert_read_only_contract(&gate_preflight)?;
    }

    match args.format {
        OutputFormat::Markdown => println!("{markdown}"),
        OutputFormat::Json => println!("{}", serde_json::to_string_pretty(&gate_preflight)?),
        OutputFormat::Both => {
            println!("{markdown}");
            println!("{}", serde_json::to_string_pretty(&gate_preflight)?);
        }
    }

    Ok(())
}

fn fixture_write_evidence_review_preflight() -> Value {
    let scope = fixture_record_scope();
    json!({
        "schema": LSWR_INTERACTION_FEEDBACK_RUNTIME_EXECUTOR_DURABLE_OUTCOME_RECORD_WRITE_EVIDENCE_REVIEW_PREFLIGHT_SCHEMA,
        "durable_outcome_record_write_evidence_review_preflight_verdict": "ready_for_world_verdict_rewrite_gate",
        "status": "ready",
        "reason": "durable_outcome_record_write_evidence_review_preflight_ready_for_world_verdict_rewrite_gate",
        "source_world_verdict": "not_verified",
        "failure_reasons": [],
        "guardrails": {
            "read_only": true,
            "mutation_surface": "none",
            "writes_state": false,
            "store_access_required": false,
            "mcp_tool_registered": false,
            "queries_live_runtime": false,
            "requires_ready_durable_outcome_record_write_evidence_preflight": true,
            "requires_explicit_durable_outcome_record_write_evidence_review_decision": true,
            "review_kind": "durable_outcome_record_write_evidence_review",
            "performs_durable_outcome_record_write_evidence_review_preflight": true,
            "performs_durable_outcome_record_write_evidence_review": false,
            "durable_outcome_record_written": false,
            "memory_write_allowed": false,
            "outcome_ingestion_allowed": false,
            "persists_outcome_record": false,
            "feedback_changes_world_verdict_allowed": false,
            "runtime_executor_durable_outcome_record_write_evidence_review_preflight_only": true
        },
        "agent_action_contract": {
            "mode": "runtime_executor_durable_outcome_record_write_evidence_review_preflight_only",
            "may_enter_world_verdict_rewrite_gate_after_preflight": true,
            "do_not_ingest_outcome": true,
            "do_not_write_memory": true,
            "do_not_rewrite_world_verdict": true,
            "do_not_persist_outcome_record": true,
            "require_separate_world_verdict_rewrite_gate": true
        },
        "durable_outcome_record_write_evidence_review": {
            "review_decision_id": "durable_outcome_record_write_evidence_review_arrival_bath_move_002",
            "write_evidence_id": "durable_outcome_record_write_evidence_arrival_bath_move_002",
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
            "review_kind": "durable_outcome_record_write_evidence_review",
            "decision": "approved_for_world_verdict_rewrite_gate",
            "review_reason": "external_write_evidence_is_scoped_acknowledged_readback_and_digest_checked",
            "outcome_record_candidate_id": scope["outcome_record_candidate_id"],
            "outcome_record_schema": scope["outcome_record_schema"],
            "idempotency_key": scope["idempotency_key"],
            "outcome_payload_digest": scope["outcome_payload_digest"],
            "write_plan_id": scope["write_plan_id"],
            "write_destination": scope["write_destination"],
            "outcome_record_key": scope["outcome_record_key"],
            "outcome_record_digest": scope["outcome_record_digest"],
            "persisted_outcome_record_key": scope["outcome_record_key"],
            "persisted_outcome_record_digest": scope["outcome_record_digest"],
            "durable_outcome_record_write_confirmed": true,
            "store_ack_confirmed": true,
            "record_readback_confirmed": true,
            "outcome_record_digest_confirmed": true,
            "idempotency_key_confirmed": true,
            "persisted_key_confirmed": true,
            "persisted_digest_confirmed": true,
            "reviewer_attestation_present": true,
            "ready_for_world_verdict_rewrite_gate": true,
            "durable_outcome_record_written_by_this_tool": false,
            "memory_write_allowed": false,
            "outcome_ingestion_allowed": false,
            "world_verdict_rewrite_allowed": false
        },
        "writes_state": false,
        "store_access_required": false,
        "mcp_tool_registered": false
    })
}

fn fixture_world_verdict_rewrite_gate_decision() -> Value {
    let scope = fixture_record_scope();
    json!({
        "schema": LSWR_RUNTIME_EXECUTOR_WORLD_VERDICT_REWRITE_GATE_DECISION_SCHEMA,
        "rewrite_gate_decision_id": "world_verdict_rewrite_gate_arrival_bath_move_002",
        "gate_kind": "world_verdict_rewrite_gate",
        "source_world_verdict_rewrite_gate_scope": {
            "review_decision_id": "durable_outcome_record_write_evidence_review_arrival_bath_move_002",
            "write_evidence_id": "durable_outcome_record_write_evidence_arrival_bath_move_002",
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
            "outcome_record_digest": scope["outcome_record_digest"],
            "persisted_outcome_record_key": scope["outcome_record_key"],
            "persisted_outcome_record_digest": scope["outcome_record_digest"]
        },
        "decision": "approved_for_world_verdict_rewrite_execution",
        "gate_reason": "reviewed_durable_write_evidence_supports_later_verified_rewrite_execution",
        "source_world_verdict": "not_verified",
        "target_world_verdict": "verified",
        "reviewed_write_evidence_review_preflight_verdict": "ready_for_world_verdict_rewrite_gate",
        "durable_outcome_record_write_confirmed": true,
        "write_evidence_review_confirmed": true,
        "world_verdict_transition_authorized": true,
        "source_world_verdict_confirmed": true,
        "target_world_verdict_confirmed": true,
        "reviewer_attestation_present": true,
        "world_verdict_rewrite_allowed": false,
        "world_verdict_rewrite_performed_by_this_tool": false,
        "outcome_ingestion_allowed": false,
        "memory_write_allowed": false,
        "durable_outcome_record_written_by_this_tool": false
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

fn assert_blocked_without_world_verdict_rewrite_gate_decision(preflight: &Value) -> Result<()> {
    assert_eq(
        preflight,
        "world_verdict_rewrite_gate_preflight_verdict",
        "blocked",
    )?;
    assert_eq(
        preflight,
        "reason",
        "explicit_world_verdict_rewrite_gate_decision_required",
    )?;
    Ok(())
}

fn assert_ready_for_world_verdict_rewrite_execution(preflight: &Value) -> Result<()> {
    assert_eq(
        preflight,
        "world_verdict_rewrite_gate_preflight_verdict",
        "ready_for_world_verdict_rewrite_execution",
    )?;
    assert_eq(
        preflight,
        "next_allowed_gate",
        "world_verdict_rewrite_execution",
    )?;
    if preflight["world_verdict_rewrite_gate"]["ready_for_world_verdict_rewrite_execution"] != true
    {
        bail!("expected ready_for_world_verdict_rewrite_execution=true");
    }
    Ok(())
}

fn assert_read_only_contract(preflight: &Value) -> Result<()> {
    for key in [
        "writes_state",
        "store_access_required",
        "mcp_tool_registered",
        "durable_outcome_record_written_by_this_tool",
        "durable_outcome_ingestion_performed_by_this_tool",
        "world_verdict_rewrite_performed_by_this_tool",
    ] {
        if preflight[key] != false {
            bail!("{key} must be false");
        }
    }
    if preflight["world_verdict_rewrite_gate_preflight_performed_by_this_tool"] != true {
        bail!("preflight marker must be true");
    }
    for key in [
        "read_only",
        "requires_ready_durable_outcome_record_write_evidence_review_preflight",
        "requires_explicit_world_verdict_rewrite_gate_decision",
        "performs_world_verdict_rewrite_gate_preflight",
    ] {
        if preflight["guardrails"][key] != true {
            bail!("guardrail {key} must be true");
        }
    }
    for key in [
        "writes_state",
        "store_access_required",
        "mcp_tool_registered",
        "world_verdict_rewrite_allowed",
        "world_verdict_rewrite_performed_by_this_tool",
        "memory_write_allowed",
        "outcome_ingestion_allowed",
        "persists_outcome_record",
        "feedback_changes_world_verdict_allowed",
    ] {
        if preflight["guardrails"][key] != false {
            bail!("guardrail {key} must be false");
        }
    }
    for key in [
        "do_not_ingest_outcome",
        "do_not_write_memory",
        "do_not_rewrite_world_verdict",
        "do_not_persist_outcome_record",
        "require_separate_world_verdict_rewrite_execution",
    ] {
        if preflight["agent_action_contract"][key] != true {
            bail!("agent action contract {key} must be true");
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
    with_world_verdict_rewrite_gate_decision: bool,
    assert_blocked_without_world_verdict_rewrite_gate_decision: bool,
    assert_ready_for_world_verdict_rewrite_execution: bool,
    assert_read_only: bool,
    format: OutputFormat,
}

impl Args {
    fn parse(args: impl Iterator<Item = String>) -> Result<Self> {
        let mut parsed = Self {
            with_world_verdict_rewrite_gate_decision: false,
            assert_blocked_without_world_verdict_rewrite_gate_decision: false,
            assert_ready_for_world_verdict_rewrite_execution: false,
            assert_read_only: false,
            format: OutputFormat::Markdown,
        };
        let mut args = args.peekable();
        while let Some(arg) = args.next() {
            match arg.as_str() {
                "--with-world-verdict-rewrite-gate-decision" => {
                    parsed.with_world_verdict_rewrite_gate_decision = true;
                }
                "--assert-blocked-without-world-verdict-rewrite-gate-decision" => {
                    parsed.assert_blocked_without_world_verdict_rewrite_gate_decision = true;
                }
                "--assert-ready-for-world-verdict-rewrite-execution" => {
                    parsed.assert_ready_for_world_verdict_rewrite_execution = true;
                }
                "--assert-read-only" => parsed.assert_read_only = true,
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
        "Usage: cargo run -p ab-bridge --example lswr_interaction_feedback_runtime_executor_world_verdict_rewrite_gate_preflight_smoke -- [flags]\n\
\n\
Flags:\n\
  --with-world-verdict-rewrite-gate-decision\n\
  --assert-blocked-without-world-verdict-rewrite-gate-decision\n\
  --assert-ready-for-world-verdict-rewrite-execution\n\
  --assert-read-only\n\
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
