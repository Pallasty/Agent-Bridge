#![recursion_limit = "256"]

//! Repeatable LSWR verified-outcome ingestion execution commit smoke.
//!
//! This validates an explicit commit decision over a minimal accepted G19
//! verified outcome ingestion execution preflight package, including the G29
//! admission-source variant. It emits a bounded apply-ready package only. It
//! never writes durable outcome records, touches memory/store rows, registers
//! MCP tools, persists world verdicts, or executes verified outcome ingestion.

use ab_bridge::lswr_interaction_feedback::{
    build_interaction_feedback_runtime_executor_verified_outcome_ingestion_execution_commit,
    render_interaction_feedback_runtime_executor_verified_outcome_ingestion_execution_commit,
    LSWR_INTERACTION_FEEDBACK_RUNTIME_EXECUTOR_VERIFIED_OUTCOME_INGESTION_EXECUTION_PREFLIGHT_SCHEMA,
    LSWR_RUNTIME_EXECUTOR_VERIFIED_OUTCOME_INGESTION_EXECUTION_COMMIT_DECISION_SCHEMA,
};
use anyhow::{bail, Context, Result};
use serde_json::{json, Value};

fn main() -> Result<()> {
    let args = Args::parse(std::env::args().skip(1))?;
    let execution_preflight = if args.from_verified_outcome_ingestion_admission_preflight {
        fixture_verified_outcome_ingestion_execution_preflight_from_admission_preflight()
    } else {
        fixture_verified_outcome_ingestion_execution_preflight()
    };
    let input = if args.with_verified_outcome_ingestion_execution_commit_decision {
        let commit_decision = if args.from_verified_outcome_ingestion_admission_preflight {
            fixture_verified_outcome_ingestion_execution_commit_decision_from_admission_preflight()
        } else {
            fixture_verified_outcome_ingestion_execution_commit_decision()
        };
        json!({
            "verified_outcome_ingestion_execution_preflight": execution_preflight,
            "verified_outcome_ingestion_execution_commit_decision": commit_decision
        })
    } else {
        execution_preflight
    };
    let commit =
        build_interaction_feedback_runtime_executor_verified_outcome_ingestion_execution_commit(
            &input,
        );
    let markdown =
        render_interaction_feedback_runtime_executor_verified_outcome_ingestion_execution_commit(
            &commit,
        );

    if args.assert_blocked_without_verified_outcome_ingestion_execution_commit_decision {
        assert_blocked_without_verified_outcome_ingestion_execution_commit_decision(&commit)?;
    }
    if args.assert_ready_for_verified_outcome_ingestion_apply {
        assert_ready_for_verified_outcome_ingestion_apply(&commit)?;
    }
    if args.assert_output_only {
        assert_output_only_contract(&commit)?;
    }

    match args.format {
        OutputFormat::Markdown => println!("{markdown}"),
        OutputFormat::Json => println!("{}", serde_json::to_string_pretty(&commit)?),
        OutputFormat::Both => {
            println!("{markdown}");
            println!("{}", serde_json::to_string_pretty(&commit)?);
        }
    }

    Ok(())
}

fn fixture_verified_outcome_ingestion_execution_preflight() -> Value {
    let scope = fixture_commit_scope();
    json!({
        "schema": LSWR_INTERACTION_FEEDBACK_RUNTIME_EXECUTOR_VERIFIED_OUTCOME_INGESTION_EXECUTION_PREFLIGHT_SCHEMA,
        "input_kind": "verified_outcome_ingestion_gate_with_verified_outcome_ingestion_execution_decision_wrapper",
        "source_schema": "agent_bridge.lswr.interaction_feedback_runtime_executor_verified_outcome_ingestion_gate.v0",
        "source_verified_outcome_ingestion_gate_verdict": "ready_for_verified_outcome_ingestion_execution",
        "source_world_verdict": "not_verified",
        "verified_world_verdict": "verified",
        "verified_outcome_ingestion_execution_decision_schema": "agent_bridge.lswr.runtime_executor.verified_outcome_ingestion_execution_decision.v0",
        "verified_outcome_ingestion_execution_preflight_verdict": "ready_for_verified_outcome_ingestion_execution_commit",
        "status": "ready",
        "reason": "verified_outcome_ingestion_execution_preflight_ready_for_execution_commit",
        "failure_reasons": [],
        "guardrails": {
            "read_only": true,
            "mutation_surface": "output_only",
            "writes_state": false,
            "store_access_required": false,
            "mcp_tool_registered": false,
            "queries_live_runtime": false,
            "requires_ready_verified_outcome_ingestion_gate": true,
            "requires_explicit_verified_outcome_ingestion_execution_decision": true,
            "decision_kind": "verified_outcome_ingestion_execution",
            "performs_verified_outcome_ingestion_execution_preflight": true,
            "performs_verified_outcome_ingestion": false,
            "persists_world_verdict": false,
            "durable_outcome_record_written": false,
            "memory_write_allowed": false,
            "outcome_ingestion_allowed": false,
            "verified_outcome_ingestion_allowed": false,
            "persists_outcome_record": false,
            "runtime_executor_verified_outcome_ingestion_execution_preflight_only": true
        },
        "verified_outcome_ingestion_execution": {
            "execution_decision_id": scope["execution_decision_id"],
            "source_ingestion_decision_id": scope["source_ingestion_decision_id"],
            "source_rewrite_decision_id": scope["source_rewrite_decision_id"],
            "source_review_decision_id": scope["source_review_decision_id"],
            "write_evidence_id": scope["write_evidence_id"],
            "world_id": scope["world_id"],
            "branch_id": scope["branch_id"],
            "runtime_generation": scope["runtime_generation"],
            "patch_id": scope["patch_id"],
            "decision_kind": "verified_outcome_ingestion_execution",
            "decision": "approved_for_verified_outcome_ingestion_execution_preflight",
            "execution_reason": "verified_outcome_ingestion_gate_package_is_scoped_and_ready_for_separate_commit_execution",
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
            "verified_outcome_package_confirmed": true,
            "ingestion_gate_output_confirmed": true,
            "reviewer_attestation_present": true,
            "evidence_lineage_preserved": true,
            "ready_for_verified_outcome_ingestion_execution_commit": true,
            "verified_outcome_ingestion_execution_preflight_output_only": true,
            "verified_outcome_ingested_by_this_tool": false,
            "world_verdict_persisted_by_this_tool": false,
            "durable_outcome_record_written_by_this_tool": false,
            "memory_write_allowed": false,
            "outcome_ingestion_allowed": false
        },
        "next_allowed_gate": "verified_outcome_ingestion_execution_commit",
        "agent_action_contract": {
            "mode": "runtime_executor_verified_outcome_ingestion_execution_preflight_only",
            "may_enter_verified_outcome_ingestion_execution_commit_after_preflight": true,
            "may_execute_verified_outcome_ingestion": false,
            "do_not_ingest_outcome": true,
            "do_not_write_memory": true,
            "do_not_persist_world_verdict": true,
            "do_not_persist_outcome_record": true,
            "require_separate_verified_outcome_ingestion_execution_commit": true
        },
        "verified_outcome_ingestion_execution_preflight_performed_by_this_tool": true,
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

fn fixture_verified_outcome_ingestion_execution_preflight_from_admission_preflight() -> Value {
    let scope = fixture_commit_scope_from_admission_preflight();
    json!({
        "schema": LSWR_INTERACTION_FEEDBACK_RUNTIME_EXECUTOR_VERIFIED_OUTCOME_INGESTION_EXECUTION_PREFLIGHT_SCHEMA,
        "input_kind": "verified_outcome_ingestion_admission_preflight_with_verified_outcome_ingestion_execution_decision_wrapper",
        "source_schema": "agent_bridge.lswr.interaction_feedback_runtime_executor_verified_outcome_ingestion_admission_preflight.v0",
        "source_verified_outcome_ingestion_gate_verdict": null,
        "source_verified_outcome_ingestion_admission_preflight_verdict": "ready_for_verified_outcome_ingestion_execution",
        "source_world_verdict": "not_verified",
        "verified_world_verdict": "verified",
        "verified_outcome_ingestion_execution_decision_schema": "agent_bridge.lswr.runtime_executor.verified_outcome_ingestion_execution_decision.v0",
        "verified_outcome_ingestion_execution_preflight_verdict": "ready_for_verified_outcome_ingestion_execution_commit",
        "status": "ready",
        "reason": "verified_outcome_ingestion_execution_preflight_ready_for_execution_commit",
        "failure_reasons": [],
        "guardrails": {
            "read_only": true,
            "mutation_surface": "output_only",
            "writes_state": false,
            "store_access_required": false,
            "mcp_tool_registered": false,
            "queries_live_runtime": false,
            "requires_ready_verified_outcome_ingestion_gate": true,
            "accepts_ready_verified_outcome_ingestion_admission_preflight": true,
            "requires_explicit_verified_outcome_ingestion_execution_decision": true,
            "decision_kind": "verified_outcome_ingestion_execution",
            "performs_verified_outcome_ingestion_execution_preflight": true,
            "performs_verified_outcome_ingestion": false,
            "persists_world_verdict": false,
            "durable_outcome_record_written": false,
            "memory_write_allowed": false,
            "outcome_ingestion_allowed": false,
            "verified_outcome_ingestion_allowed": false,
            "persists_outcome_record": false,
            "runtime_executor_verified_outcome_ingestion_execution_preflight_only": true
        },
        "verified_outcome_ingestion_execution": {
            "execution_decision_id": scope["execution_decision_id"],
            "source_admission_decision_id": scope["source_admission_decision_id"],
            "source_write_evidence_review_decision_id": scope["source_write_evidence_review_decision_id"],
            "source_ingestion_decision_id": scope["source_ingestion_decision_id"],
            "source_rewrite_decision_id": scope["source_rewrite_decision_id"],
            "source_review_decision_id": scope["source_review_decision_id"],
            "write_evidence_id": scope["write_evidence_id"],
            "store_write_execution_id": scope["store_write_execution_id"],
            "persistence_decision_id": scope["persistence_decision_id"],
            "persistence_source_execution_id": scope["persistence_source_execution_id"],
            "writer_decision_id": scope["writer_decision_id"],
            "apply_decision_id": scope["apply_decision_id"],
            "commit_decision_id": scope["commit_decision_id"],
            "source_execution_decision_id": scope["source_execution_decision_id"],
            "source_write_evidence_id": scope["source_write_evidence_id"],
            "world_id": scope["world_id"],
            "branch_id": scope["branch_id"],
            "runtime_generation": scope["runtime_generation"],
            "patch_id": scope["patch_id"],
            "decision_kind": "verified_outcome_ingestion_execution",
            "decision": "approved_for_verified_outcome_ingestion_execution_preflight",
            "execution_reason": "verified_outcome_ingestion_admission_preflight_is_scoped_and_ready_for_separate_commit_execution",
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
            "verified_outcome_package_confirmed": true,
            "ingestion_gate_output_confirmed": null,
            "admission_preflight_confirmed": true,
            "admission_decision_confirmed": true,
            "reviewer_attestation_present": true,
            "evidence_lineage_preserved": true,
            "ready_for_verified_outcome_ingestion_execution_commit": true,
            "verified_outcome_ingestion_execution_preflight_output_only": true,
            "verified_outcome_ingested_by_this_tool": false,
            "world_verdict_persisted_by_this_tool": false,
            "durable_outcome_record_written_by_this_tool": false,
            "memory_write_allowed": false,
            "outcome_ingestion_allowed": false
        },
        "next_allowed_gate": "verified_outcome_ingestion_execution_commit",
        "agent_action_contract": {
            "mode": "runtime_executor_verified_outcome_ingestion_execution_preflight_only",
            "may_enter_verified_outcome_ingestion_execution_commit_after_preflight": true,
            "may_execute_verified_outcome_ingestion": false,
            "do_not_ingest_outcome": true,
            "do_not_write_memory": true,
            "do_not_persist_world_verdict": true,
            "do_not_persist_outcome_record": true,
            "require_separate_verified_outcome_ingestion_execution_commit": true
        },
        "source_verified_outcome_ingestion_gate": null,
        "source_verified_outcome_ingestion_admission_preflight": {
            "schema": "agent_bridge.lswr.interaction_feedback_runtime_executor_verified_outcome_ingestion_admission_preflight.v0",
            "verified_outcome_ingestion_admission_preflight_verdict": "ready_for_verified_outcome_ingestion_execution"
        },
        "verified_outcome_ingestion_execution_preflight_performed_by_this_tool": true,
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

fn fixture_verified_outcome_ingestion_execution_commit_decision() -> Value {
    json!({
        "schema": LSWR_RUNTIME_EXECUTOR_VERIFIED_OUTCOME_INGESTION_EXECUTION_COMMIT_DECISION_SCHEMA,
        "commit_decision_id": "verified_outcome_ingestion_execution_commit_arrival_bath_move_002",
        "decision_kind": "verified_outcome_ingestion_execution_commit",
        "source_verified_outcome_ingestion_execution_preflight_scope": fixture_commit_scope(),
        "decision": "approved_for_verified_outcome_ingestion_apply",
        "commit_reason": "verified_outcome_ingestion_execution_preflight_is_scoped_and_ready_for_separate_apply",
        "source_world_verdict": "not_verified",
        "verified_world_verdict": "verified",
        "reviewed_verified_outcome_ingestion_execution_preflight_verdict": "ready_for_verified_outcome_ingestion_execution_commit",
        "execution_preflight_package_confirmed": true,
        "verified_outcome_package_confirmed": true,
        "reviewer_attestation_present": true,
        "evidence_lineage_preserved": true,
        "outcome_record_digest_confirmed": true,
        "idempotency_key_confirmed": true,
        "persisted_key_confirmed": true,
        "persisted_digest_confirmed": true,
        "apply_boundary_acknowledged": true,
        "outcome_ingestion_allowed": false,
        "memory_write_allowed": false,
        "verified_outcome_ingested_by_this_tool": false,
        "durable_outcome_record_written_by_this_tool": false,
        "world_verdict_persisted_by_this_tool": false
    })
}

fn fixture_verified_outcome_ingestion_execution_commit_decision_from_admission_preflight() -> Value
{
    json!({
        "schema": LSWR_RUNTIME_EXECUTOR_VERIFIED_OUTCOME_INGESTION_EXECUTION_COMMIT_DECISION_SCHEMA,
        "commit_decision_id": "verified_outcome_ingestion_execution_commit_from_admission_arrival_bath_move_002",
        "decision_kind": "verified_outcome_ingestion_execution_commit",
        "source_verified_outcome_ingestion_execution_preflight_scope":
            fixture_commit_scope_from_admission_preflight(),
        "decision": "approved_for_verified_outcome_ingestion_apply",
        "commit_reason": "admission_source_verified_outcome_ingestion_execution_preflight_is_scoped_and_ready_for_separate_apply",
        "source_world_verdict": "not_verified",
        "verified_world_verdict": "verified",
        "reviewed_verified_outcome_ingestion_execution_preflight_verdict": "ready_for_verified_outcome_ingestion_execution_commit",
        "execution_preflight_package_confirmed": true,
        "verified_outcome_package_confirmed": true,
        "admission_preflight_confirmed": true,
        "admission_decision_confirmed": true,
        "reviewer_attestation_present": true,
        "evidence_lineage_preserved": true,
        "outcome_record_digest_confirmed": true,
        "idempotency_key_confirmed": true,
        "persisted_key_confirmed": true,
        "persisted_digest_confirmed": true,
        "apply_boundary_acknowledged": true,
        "outcome_ingestion_allowed": false,
        "memory_write_allowed": false,
        "verified_outcome_ingested_by_this_tool": false,
        "durable_outcome_record_written_by_this_tool": false,
        "world_verdict_persisted_by_this_tool": false
    })
}

fn fixture_commit_scope() -> Value {
    json!({
        "execution_decision_id": "verified_outcome_ingestion_execution_arrival_bath_move_002",
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

fn fixture_commit_scope_from_admission_preflight() -> Value {
    json!({
        "execution_decision_id": "verified_outcome_ingestion_execution_from_admission_arrival_bath_move_002",
        "source_admission_decision_id": "verified_outcome_ingestion_admission_arrival_bath_move_002",
        "source_write_evidence_review_decision_id": "verified_outcome_ingestion_write_evidence_review_arrival_bath_move_002",
        "source_ingestion_decision_id": "verified_outcome_ingestion_arrival_bath_move_002",
        "source_rewrite_decision_id": "world_verdict_rewrite_arrival_bath_move_002",
        "source_review_decision_id": "durable_outcome_record_write_evidence_review_arrival_bath_move_002",
        "write_evidence_id": "verified_outcome_ingestion_write_evidence_arrival_bath_move_002",
        "store_write_execution_id": "verified_outcome_ingestion_store_write_execution_arrival_bath_move_002",
        "persistence_decision_id": "verified_outcome_ingestion_persistence_arrival_bath_move_002",
        "persistence_source_execution_id": "verified_outcome_ingestion_writer_execution_arrival_bath_move_002",
        "writer_decision_id": "verified_outcome_ingestion_writer_arrival_bath_move_002",
        "apply_decision_id": "verified_outcome_ingestion_apply_arrival_bath_move_002",
        "commit_decision_id": "verified_outcome_ingestion_execution_commit_arrival_bath_move_002",
        "source_execution_decision_id": "verified_outcome_ingestion_execution_arrival_bath_move_002",
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

fn assert_blocked_without_verified_outcome_ingestion_execution_commit_decision(
    commit: &Value,
) -> Result<()> {
    assert_eq(
        commit,
        "verified_outcome_ingestion_execution_commit_verdict",
        "blocked",
    )?;
    assert_eq(
        commit,
        "reason",
        "explicit_verified_outcome_ingestion_execution_commit_decision_required",
    )?;
    Ok(())
}

fn assert_ready_for_verified_outcome_ingestion_apply(commit: &Value) -> Result<()> {
    assert_eq(
        commit,
        "verified_outcome_ingestion_execution_commit_verdict",
        "ready_for_verified_outcome_ingestion_apply",
    )?;
    assert_eq(
        commit,
        "next_allowed_gate",
        "verified_outcome_ingestion_apply",
    )?;
    if commit["verified_outcome_ingestion_execution_commit"]["previous_world_verdict"]
        != "not_verified"
    {
        bail!("expected previous_world_verdict=not_verified");
    }
    if commit["verified_outcome_ingestion_execution_commit"]["verified_world_verdict"] != "verified"
    {
        bail!("expected verified_world_verdict=verified");
    }
    if commit["verified_outcome_ingestion_execution_commit"]
        ["ready_for_verified_outcome_ingestion_apply"]
        != true
    {
        bail!("expected ready_for_verified_outcome_ingestion_apply=true");
    }
    Ok(())
}

fn assert_output_only_contract(commit: &Value) -> Result<()> {
    for key in [
        "writes_state",
        "store_access_required",
        "mcp_tool_registered",
        "world_verdict_persisted_by_this_tool",
        "durable_outcome_record_written_by_this_tool",
        "durable_outcome_ingestion_performed_by_this_tool",
        "verified_outcome_ingestion_performed_by_this_tool",
        "verified_outcome_ingested_by_this_tool",
    ] {
        if commit[key] != false {
            bail!("expected {key}=false");
        }
    }

    for key in [
        "read_only",
        "requires_ready_verified_outcome_ingestion_execution_preflight",
        "requires_explicit_verified_outcome_ingestion_execution_commit_decision",
        "performs_verified_outcome_ingestion_execution_commit_gate",
    ] {
        if commit["guardrails"][key] != true {
            bail!("expected guardrails.{key}=true");
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
        if commit["guardrails"][key] != false {
            bail!("expected guardrails.{key}=false");
        }
    }

    if commit["guardrails"]["mutation_surface"] != "output_only" {
        bail!("expected guardrails.mutation_surface=output_only");
    }

    for key in [
        "may_execute_verified_outcome_ingestion",
        "do_not_ingest_outcome",
        "do_not_write_memory",
        "do_not_persist_world_verdict",
        "do_not_persist_outcome_record",
        "require_separate_verified_outcome_ingestion_apply",
    ] {
        let expected = key != "may_execute_verified_outcome_ingestion";
        if commit["agent_action_contract"][key] != expected {
            bail!("unexpected agent_action_contract.{key}");
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
    from_verified_outcome_ingestion_admission_preflight: bool,
    with_verified_outcome_ingestion_execution_commit_decision: bool,
    assert_blocked_without_verified_outcome_ingestion_execution_commit_decision: bool,
    assert_ready_for_verified_outcome_ingestion_apply: bool,
    assert_output_only: bool,
    format: OutputFormat,
}

impl Args {
    fn parse(args: impl Iterator<Item = String>) -> Result<Self> {
        let mut parsed = Self {
            from_verified_outcome_ingestion_admission_preflight: false,
            with_verified_outcome_ingestion_execution_commit_decision: false,
            assert_blocked_without_verified_outcome_ingestion_execution_commit_decision: false,
            assert_ready_for_verified_outcome_ingestion_apply: false,
            assert_output_only: false,
            format: OutputFormat::Markdown,
        };

        let mut args = args.peekable();
        while let Some(arg) = args.next() {
            match arg.as_str() {
                "--from-verified-outcome-ingestion-admission-preflight" => {
                    parsed.from_verified_outcome_ingestion_admission_preflight = true;
                }
                "--with-verified-outcome-ingestion-execution-commit-decision" => {
                    parsed.with_verified_outcome_ingestion_execution_commit_decision = true;
                }
                "--assert-blocked-without-verified-outcome-ingestion-execution-commit-decision" => {
                    parsed.assert_blocked_without_verified_outcome_ingestion_execution_commit_decision = true;
                }
                "--assert-ready-for-verified-outcome-ingestion-apply" => {
                    parsed.assert_ready_for_verified_outcome_ingestion_apply = true;
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
    r#"Usage: cargo run -q -p ab-bridge --example lswr_interaction_feedback_runtime_executor_verified_outcome_ingestion_execution_commit_smoke -- [options]

Options:
  --from-verified-outcome-ingestion-admission-preflight
  --with-verified-outcome-ingestion-execution-commit-decision
  --assert-blocked-without-verified-outcome-ingestion-execution-commit-decision
  --assert-ready-for-verified-outcome-ingestion-apply
  --assert-output-only
  --format=json|markdown|both
"#
}
