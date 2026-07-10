#![recursion_limit = "256"]

//! Repeatable LSWR verified-outcome ingestion store-write execution preflight smoke.
//!
//! This validates an explicit store-write execution decision against a minimal
//! accepted G24 verified-outcome ingestion persistence package. It emits a
//! bounded write-evidence package only. It never writes durable outcome
//! records, touches memory/store rows, registers MCP tools, persists world
//! verdicts, or ingests verified outcomes.

use ab_bridge::lswr_interaction_feedback::{
    build_interaction_feedback_runtime_executor_verified_outcome_ingestion_store_write_execution_preflight,
    render_interaction_feedback_runtime_executor_verified_outcome_ingestion_store_write_execution_preflight,
    LSWR_INTERACTION_FEEDBACK_RUNTIME_EXECUTOR_VERIFIED_OUTCOME_INGESTION_PERSISTENCE_SCHEMA,
    LSWR_RUNTIME_EXECUTOR_VERIFIED_OUTCOME_INGESTION_STORE_WRITE_EXECUTION_DECISION_SCHEMA,
};
use anyhow::{bail, Context, Result};
use serde_json::{json, Value};

fn main() -> Result<()> {
    let args = Args::parse(std::env::args().skip(1))?;
    let persistence = fixture_verified_outcome_ingestion_persistence();
    let input = if args.with_verified_outcome_ingestion_store_write_execution_decision {
        json!({
            "verified_outcome_ingestion_persistence": persistence,
            "verified_outcome_ingestion_store_write_execution_decision":
                fixture_verified_outcome_ingestion_store_write_execution_decision()
        })
    } else {
        persistence
    };
    let preflight =
        build_interaction_feedback_runtime_executor_verified_outcome_ingestion_store_write_execution_preflight(
            &input,
        );
    let markdown =
        render_interaction_feedback_runtime_executor_verified_outcome_ingestion_store_write_execution_preflight(
            &preflight,
        );

    if args.assert_blocked_without_verified_outcome_ingestion_store_write_execution_decision {
        assert_blocked_without_verified_outcome_ingestion_store_write_execution_decision(
            &preflight,
        )?;
    }
    if args.assert_ready_for_verified_outcome_ingestion_write_evidence {
        assert_ready_for_verified_outcome_ingestion_write_evidence(&preflight)?;
    }
    if args.assert_output_only {
        assert_output_only_contract(&preflight)?;
    }

    match args.format {
        OutputFormat::Markdown => println!("{markdown}"),
        OutputFormat::Json => println!("{}", serde_json::to_string_pretty(&preflight)?),
        OutputFormat::Both => {
            println!("{markdown}");
            println!("{}", serde_json::to_string_pretty(&preflight)?);
        }
    }

    Ok(())
}

fn fixture_verified_outcome_ingestion_persistence() -> Value {
    let scope = fixture_store_write_scope();
    json!({
        "schema": LSWR_INTERACTION_FEEDBACK_RUNTIME_EXECUTOR_VERIFIED_OUTCOME_INGESTION_PERSISTENCE_SCHEMA,
        "verified_outcome_ingestion_persistence_verdict": "ready_for_verified_outcome_ingestion_store_write",
        "status": "ready",
        "reason": "verified_outcome_ingestion_persistence_ready_for_store_write",
        "next_allowed_gate": "verified_outcome_ingestion_store_write",
        "source_world_verdict": "not_verified",
        "verified_world_verdict": "verified",
        "failure_reasons": [],
        "guardrails": {
            "read_only": true,
            "mutation_surface": "output_only",
            "writes_state": false,
            "store_access_required": false,
            "mcp_tool_registered": false,
            "queries_live_runtime": false,
            "requires_ready_verified_outcome_ingestion_writer_execution": true,
            "requires_explicit_verified_outcome_ingestion_persistence_decision": true,
            "persistence_kind": "verified_outcome_ingestion_persistence",
            "performs_verified_outcome_ingestion_persistence_gate": true,
            "performs_verified_outcome_ingestion": false,
            "performs_verified_outcome_store_write": false,
            "verified_outcome_store_write_allowed": false,
            "persists_world_verdict": false,
            "persists_outcome_record": false,
            "durable_outcome_record_written": false,
            "memory_write_allowed": false,
            "outcome_ingestion_allowed_by_this_tool": false,
            "runtime_executor_verified_outcome_ingestion_persistence_gate_only": true
        },
        "verified_outcome_ingestion_persistence": {
            "persistence_decision_id": scope["persistence_decision_id"],
            "persistence_source_execution_id": scope["persistence_source_execution_id"],
            "writer_decision_id": scope["writer_decision_id"],
            "apply_decision_id": scope["apply_decision_id"],
            "commit_decision_id": scope["commit_decision_id"],
            "source_execution_decision_id": scope["source_execution_decision_id"],
            "source_ingestion_decision_id": scope["source_ingestion_decision_id"],
            "source_rewrite_decision_id": scope["source_rewrite_decision_id"],
            "source_review_decision_id": scope["source_review_decision_id"],
            "write_evidence_id": scope["write_evidence_id"],
            "world_id": scope["world_id"],
            "branch_id": scope["branch_id"],
            "runtime_generation": scope["runtime_generation"],
            "patch_id": scope["patch_id"],
            "decision": "approved_for_verified_outcome_ingestion_store_write",
            "persistence_reason": "verified_outcome_ingestion_persistence_is_scoped_and_ready_for_separate_store_write",
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
            "writer_execution_package_confirmed": true,
            "writer_package_confirmed": true,
            "verified_outcome_package_confirmed": true,
            "persistence_target_verified": true,
            "outcome_record_digest_verified": true,
            "idempotent_upsert_confirmed": true,
            "store_transaction_plan_complete": true,
            "rollback_plan_confirmed": true,
            "ready_for_verified_outcome_ingestion_store_write": true,
            "verified_outcome_ingestion_persistence_output_only": true,
            "verified_outcome_ingestion_store_write_allowed_after_persistence": true,
            "verified_outcome_store_write_allowed": false,
            "verified_outcome_ingested_by_this_tool": false,
            "world_verdict_persisted_by_this_tool": false,
            "durable_outcome_record_written_by_this_tool": false,
            "memory_write_allowed": false,
            "outcome_ingestion_allowed_by_this_tool": false
        },
        "agent_action_contract": {
            "mode": "runtime_executor_verified_outcome_ingestion_persistence_gate_only",
            "may_execute_verified_outcome_ingestion_store_write_after_persistence": true,
            "may_execute_verified_outcome_ingestion_by_this_tool": false,
            "require_separate_verified_outcome_ingestion_store_write": true,
            "do_not_ingest_outcome": true,
            "do_not_write_memory": true,
            "do_not_persist_world_verdict": true,
            "do_not_persist_outcome_record": true
        },
        "verified_outcome_ingestion_persistence_performed_by_this_tool": true,
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

fn fixture_verified_outcome_ingestion_store_write_execution_decision() -> Value {
    json!({
        "schema": LSWR_RUNTIME_EXECUTOR_VERIFIED_OUTCOME_INGESTION_STORE_WRITE_EXECUTION_DECISION_SCHEMA,
        "store_write_execution_id": "verified_outcome_ingestion_store_write_execution_arrival_bath_move_002",
        "store_write_execution_kind": "verified_outcome_ingestion_store_write_execution",
        "source_verified_outcome_ingestion_persistence_scope": fixture_store_write_scope(),
        "decision": "approved_for_verified_outcome_ingestion_write_evidence",
        "store_write_execution_reason": "verified_outcome_ingestion_store_write_preflight_ready_for_later_write_evidence",
        "source_world_verdict": "not_verified",
        "verified_world_verdict": "verified",
        "reviewed_verified_outcome_ingestion_persistence_verdict": "ready_for_verified_outcome_ingestion_store_write",
        "persistence_package_confirmed": true,
        "writer_execution_package_confirmed": true,
        "verified_outcome_package_confirmed": true,
        "persistence_target_verified": true,
        "outcome_record_digest_verified": true,
        "idempotent_upsert_confirmed": true,
        "store_transaction_plan_complete": true,
        "rollback_plan_confirmed": true,
        "write_destination": "agent_bridge_store_outcome_records",
        "outcome_record_key": "onsen_live_session/main/runtime_gen_1284/patch_arrival_bath_move_002/outcome_record_candidate_arrival_bath_move_002",
        "outcome_record_digest": "sha256:arrival-bath-move-002-outcome-record",
        "verified_outcome_store_write_execution_allowed": false,
        "verified_outcome_store_written_by_this_tool": false,
        "outcome_ingestion_allowed_by_this_tool": false,
        "memory_write_allowed": false,
        "verified_outcome_ingested_by_this_tool": false,
        "durable_outcome_record_written_by_this_tool": false,
        "world_verdict_persisted_by_this_tool": false
    })
}

fn fixture_store_write_scope() -> Value {
    json!({
        "persistence_decision_id": "verified_outcome_ingestion_persistence_arrival_bath_move_002",
        "persistence_source_execution_id": "verified_outcome_ingestion_writer_execution_arrival_bath_move_002",
        "writer_decision_id": "verified_outcome_ingestion_writer_arrival_bath_move_002",
        "apply_decision_id": "verified_outcome_ingestion_apply_arrival_bath_move_002",
        "commit_decision_id": "verified_outcome_ingestion_execution_commit_arrival_bath_move_002",
        "source_execution_decision_id": "verified_outcome_ingestion_execution_arrival_bath_move_002",
        "source_ingestion_decision_id": "verified_outcome_ingestion_arrival_bath_move_002",
        "source_rewrite_decision_id": "world_verdict_rewrite_arrival_bath_move_002",
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

fn assert_blocked_without_verified_outcome_ingestion_store_write_execution_decision(
    preflight: &Value,
) -> Result<()> {
    assert_eq(
        preflight,
        "verified_outcome_ingestion_store_write_execution_preflight_verdict",
        "blocked",
    )?;
    assert_eq(
        preflight,
        "reason",
        "explicit_verified_outcome_ingestion_store_write_execution_decision_required",
    )?;
    Ok(())
}

fn assert_ready_for_verified_outcome_ingestion_write_evidence(preflight: &Value) -> Result<()> {
    assert_eq(
        preflight,
        "verified_outcome_ingestion_store_write_execution_preflight_verdict",
        "ready_for_verified_outcome_ingestion_write_evidence",
    )?;
    assert_eq(
        preflight,
        "next_allowed_gate",
        "verified_outcome_ingestion_write_evidence",
    )?;
    if preflight["verified_outcome_ingestion_store_write_execution"]
        ["ready_for_verified_outcome_ingestion_write_evidence"]
        != true
    {
        bail!("expected ready_for_verified_outcome_ingestion_write_evidence=true");
    }
    Ok(())
}

fn assert_output_only_contract(preflight: &Value) -> Result<()> {
    for key in [
        "writes_state",
        "store_access_required",
        "mcp_tool_registered",
        "world_verdict_persisted_by_this_tool",
        "durable_outcome_record_written_by_this_tool",
        "durable_outcome_ingestion_performed_by_this_tool",
        "verified_outcome_ingestion_performed_by_this_tool",
        "verified_outcome_ingested_by_this_tool",
        "verified_outcome_store_written_by_this_tool",
    ] {
        if preflight[key] != false {
            bail!("expected {key}=false");
        }
    }

    for key in [
        "read_only",
        "requires_ready_verified_outcome_ingestion_persistence",
        "requires_explicit_verified_outcome_ingestion_store_write_execution_decision",
        "performs_verified_outcome_ingestion_store_write_execution_preflight",
        "verified_outcome_write_evidence_allowed_after_store_write_preflight",
    ] {
        if preflight["guardrails"][key] != true {
            bail!("expected guardrails.{key}=true");
        }
    }

    for key in [
        "writes_state",
        "store_access_required",
        "mcp_tool_registered",
        "performs_verified_outcome_ingestion",
        "performs_verified_outcome_store_write",
        "verified_outcome_store_write_execution_allowed",
        "verified_outcome_store_written_by_this_tool",
        "persists_world_verdict",
        "durable_outcome_record_written",
        "memory_write_allowed",
        "outcome_ingestion_allowed_by_this_tool",
        "persists_outcome_record",
    ] {
        if preflight["guardrails"][key] != false {
            bail!("expected guardrails.{key}=false");
        }
    }

    if preflight["guardrails"]["mutation_surface"] != "output_only" {
        bail!("expected guardrails.mutation_surface=output_only");
    }

    for key in [
        "do_not_ingest_outcome",
        "do_not_write_memory",
        "do_not_persist_world_verdict",
        "do_not_persist_outcome_record",
        "require_separate_verified_outcome_store_write_execution",
        "require_verified_outcome_write_evidence_after_store_write",
    ] {
        if preflight["agent_action_contract"][key] != true {
            bail!("expected agent_action_contract.{key}=true");
        }
    }
    if preflight["agent_action_contract"]["may_execute_verified_outcome_store_write_by_this_tool"]
        != false
    {
        bail!("expected may_execute_verified_outcome_store_write_by_this_tool=false");
    }
    if preflight["agent_action_contract"]["may_execute_verified_outcome_ingestion_by_this_tool"]
        != false
    {
        bail!("expected may_execute_verified_outcome_ingestion_by_this_tool=false");
    }

    for key in [
        "verified_outcome_store_write_execution_allowed",
        "verified_outcome_store_written_by_this_tool",
        "verified_outcome_ingested_by_this_tool",
        "world_verdict_persisted_by_this_tool",
        "durable_outcome_record_written_by_this_tool",
        "memory_write_allowed",
        "outcome_ingestion_allowed_by_this_tool",
    ] {
        if preflight["verified_outcome_ingestion_store_write_execution"][key] != false {
            bail!("expected verified_outcome_ingestion_store_write_execution.{key}=false");
        }
    }

    Ok(())
}

fn assert_eq(root: &Value, key: &str, expected: &str) -> Result<()> {
    let actual = root
        .get(key)
        .and_then(Value::as_str)
        .with_context(|| format!("missing string field {key}"))?;
    if actual != expected {
        bail!("expected {key}={expected}, got {actual}");
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
    with_verified_outcome_ingestion_store_write_execution_decision: bool,
    assert_blocked_without_verified_outcome_ingestion_store_write_execution_decision: bool,
    assert_ready_for_verified_outcome_ingestion_write_evidence: bool,
    assert_output_only: bool,
    format: OutputFormat,
}

impl Args {
    fn parse(args: impl Iterator<Item = String>) -> Result<Self> {
        let mut parsed = Self {
            with_verified_outcome_ingestion_store_write_execution_decision: false,
            assert_blocked_without_verified_outcome_ingestion_store_write_execution_decision: false,
            assert_ready_for_verified_outcome_ingestion_write_evidence: false,
            assert_output_only: false,
            format: OutputFormat::Markdown,
        };

        let mut args = args.peekable();
        while let Some(arg) = args.next() {
            match arg.as_str() {
                "--with-verified-outcome-ingestion-store-write-execution-decision" => {
                    parsed.with_verified_outcome_ingestion_store_write_execution_decision = true;
                }
                "--assert-blocked-without-verified-outcome-ingestion-store-write-execution-decision" =>
                {
                    parsed.assert_blocked_without_verified_outcome_ingestion_store_write_execution_decision =
                        true;
                }
                "--assert-ready-for-verified-outcome-ingestion-write-evidence" => {
                    parsed.assert_ready_for_verified_outcome_ingestion_write_evidence = true;
                }
                "--assert-output-only" => parsed.assert_output_only = true,
                "--format" => {
                    let value = args
                        .next()
                        .context("--format requires a value: markdown|json|both")?;
                    parsed.format = parse_format(&value)?;
                }
                "--format=json" => parsed.format = OutputFormat::Json,
                "--format=markdown" => parsed.format = OutputFormat::Markdown,
                "--format=both" => parsed.format = OutputFormat::Both,
                "--help" | "-h" => {
                    println!("{}", usage());
                    std::process::exit(0);
                }
                other if other.starts_with("--format=") => {
                    let value = other.trim_start_matches("--format=");
                    parsed.format = parse_format(value)?;
                }
                other => bail!("unknown argument {other}\n{}", usage()),
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
        other => bail!("unknown format {other}; expected markdown|json|both"),
    }
}

fn usage() -> &'static str {
    r#"Usage: cargo run -q -p ab-bridge --example lswr_interaction_feedback_runtime_executor_verified_outcome_ingestion_store_write_execution_preflight_smoke -- [options]

Options:
  --with-verified-outcome-ingestion-store-write-execution-decision
  --assert-blocked-without-verified-outcome-ingestion-store-write-execution-decision
  --assert-ready-for-verified-outcome-ingestion-write-evidence
  --assert-output-only
  --format=json|markdown|both
"#
}
