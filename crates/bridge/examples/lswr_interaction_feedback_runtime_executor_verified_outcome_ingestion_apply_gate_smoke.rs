#![recursion_limit = "256"]

//! Repeatable LSWR verified-outcome ingestion apply gate smoke.
//!
//! This validates an explicit apply decision over a minimal accepted G20
//! verified outcome ingestion execution commit package. It emits a bounded
//! writer-ready package only. It never writes durable outcome records, touches
//! memory/store rows, registers MCP tools, persists world verdicts, or executes
//! verified outcome ingestion.

use ab_bridge::lswr_interaction_feedback::{
    build_interaction_feedback_runtime_executor_verified_outcome_ingestion_apply_gate,
    render_interaction_feedback_runtime_executor_verified_outcome_ingestion_apply_gate,
    LSWR_INTERACTION_FEEDBACK_RUNTIME_EXECUTOR_VERIFIED_OUTCOME_INGESTION_EXECUTION_COMMIT_SCHEMA,
    LSWR_RUNTIME_EXECUTOR_VERIFIED_OUTCOME_INGESTION_APPLY_DECISION_SCHEMA,
};
use anyhow::{bail, Context, Result};
use serde_json::{json, Value};

fn main() -> Result<()> {
    let args = Args::parse(std::env::args().skip(1))?;
    let commit = if args.from_verified_outcome_ingestion_admission_source_commit {
        fixture_verified_outcome_ingestion_execution_commit_from_admission_source()
    } else {
        fixture_verified_outcome_ingestion_execution_commit()
    };
    let input = if args.with_verified_outcome_ingestion_apply_decision {
        let decision = if args.from_verified_outcome_ingestion_admission_source_commit {
            fixture_verified_outcome_ingestion_apply_decision_from_admission_source_commit()
        } else {
            fixture_verified_outcome_ingestion_apply_decision()
        };
        json!({
            "verified_outcome_ingestion_execution_commit": commit,
            "verified_outcome_ingestion_apply_decision": decision
        })
    } else {
        commit
    };
    let apply =
        build_interaction_feedback_runtime_executor_verified_outcome_ingestion_apply_gate(&input);
    let markdown =
        render_interaction_feedback_runtime_executor_verified_outcome_ingestion_apply_gate(&apply);

    if args.assert_blocked_without_verified_outcome_ingestion_apply_decision {
        assert_blocked_without_verified_outcome_ingestion_apply_decision(&apply)?;
    }
    if args.assert_ready_for_verified_outcome_ingestion_writer {
        assert_ready_for_verified_outcome_ingestion_writer(&apply)?;
    }
    if args.assert_output_only {
        assert_output_only_contract(&apply)?;
    }

    match args.format {
        OutputFormat::Markdown => println!("{markdown}"),
        OutputFormat::Json => println!("{}", serde_json::to_string_pretty(&apply)?),
        OutputFormat::Both => {
            println!("{markdown}");
            println!("{}", serde_json::to_string_pretty(&apply)?);
        }
    }

    Ok(())
}

fn fixture_verified_outcome_ingestion_execution_commit() -> Value {
    let scope = fixture_apply_scope();
    json!({
        "schema": LSWR_INTERACTION_FEEDBACK_RUNTIME_EXECUTOR_VERIFIED_OUTCOME_INGESTION_EXECUTION_COMMIT_SCHEMA,
        "verified_outcome_ingestion_execution_commit_verdict": "ready_for_verified_outcome_ingestion_apply",
        "status": "ready",
        "reason": "verified_outcome_ingestion_execution_commit_ready_for_apply",
        "next_allowed_gate": "verified_outcome_ingestion_apply",
        "guardrails": {
            "read_only": true,
            "mutation_surface": "output_only",
            "writes_state": false,
            "store_access_required": false,
            "mcp_tool_registered": false,
            "queries_live_runtime": false,
            "requires_ready_verified_outcome_ingestion_execution_preflight": true,
            "requires_explicit_verified_outcome_ingestion_execution_commit_decision": true,
            "decision_kind": "verified_outcome_ingestion_execution_commit",
            "performs_verified_outcome_ingestion_execution_commit_gate": true,
            "performs_verified_outcome_ingestion": false,
            "persists_world_verdict": false,
            "durable_outcome_record_written": false,
            "memory_write_allowed": false,
            "outcome_ingestion_allowed": false,
            "verified_outcome_ingestion_allowed": false,
            "persists_outcome_record": false,
            "runtime_executor_verified_outcome_ingestion_execution_commit_only": true
        },
        "verified_outcome_ingestion_execution_commit": {
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
            "execution_preflight_package_confirmed": true,
            "verified_outcome_package_confirmed": true,
            "reviewer_attestation_present": true,
            "evidence_lineage_preserved": true,
            "ready_for_verified_outcome_ingestion_apply": true,
            "verified_outcome_ingestion_execution_commit_output_only": true,
            "verified_outcome_ingested_by_this_tool": false,
            "world_verdict_persisted_by_this_tool": false,
            "durable_outcome_record_written_by_this_tool": false,
            "memory_write_allowed": false,
            "outcome_ingestion_allowed": false
        },
        "agent_action_contract": {
            "mode": "runtime_executor_verified_outcome_ingestion_execution_commit_only",
            "may_enter_verified_outcome_ingestion_apply_after_commit": true,
            "may_execute_verified_outcome_ingestion": false,
            "do_not_ingest_outcome": true,
            "do_not_write_memory": true,
            "do_not_persist_world_verdict": true,
            "do_not_persist_outcome_record": true,
            "require_separate_verified_outcome_ingestion_apply": true
        },
        "verified_outcome_ingestion_execution_commit_performed_by_this_tool": true,
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

fn fixture_verified_outcome_ingestion_execution_commit_from_admission_source() -> Value {
    let scope = fixture_apply_scope_from_admission_source_commit();
    json!({
        "schema": LSWR_INTERACTION_FEEDBACK_RUNTIME_EXECUTOR_VERIFIED_OUTCOME_INGESTION_EXECUTION_COMMIT_SCHEMA,
        "source_verified_outcome_ingestion_admission_preflight_verdict": "ready_for_verified_outcome_ingestion_execution",
        "verified_outcome_ingestion_execution_commit_verdict": "ready_for_verified_outcome_ingestion_apply",
        "status": "ready",
        "reason": "verified_outcome_ingestion_execution_commit_ready_for_apply",
        "next_allowed_gate": "verified_outcome_ingestion_apply",
        "guardrails": {
            "read_only": true,
            "mutation_surface": "output_only",
            "writes_state": false,
            "store_access_required": false,
            "mcp_tool_registered": false,
            "queries_live_runtime": false,
            "requires_ready_verified_outcome_ingestion_execution_preflight": true,
            "accepts_admission_source_verified_outcome_ingestion_execution_preflight": true,
            "preserves_verified_outcome_ingestion_admission_lineage": true,
            "requires_explicit_verified_outcome_ingestion_execution_commit_decision": true,
            "decision_kind": "verified_outcome_ingestion_execution_commit",
            "performs_verified_outcome_ingestion_execution_commit_gate": true,
            "performs_verified_outcome_ingestion": false,
            "persists_world_verdict": false,
            "durable_outcome_record_written": false,
            "memory_write_allowed": false,
            "outcome_ingestion_allowed": false,
            "verified_outcome_ingestion_allowed": false,
            "persists_outcome_record": false,
            "runtime_executor_verified_outcome_ingestion_execution_commit_only": true
        },
        "verified_outcome_ingestion_execution_commit": {
            "commit_decision_id": scope["commit_decision_id"],
            "source_execution_decision_id": scope["source_execution_decision_id"],
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
            "apply_decision_id": scope["source_apply_decision_id"],
            "source_commit_decision_id": scope["source_commit_decision_id"],
            "source_prior_execution_decision_id": scope["source_prior_execution_decision_id"],
            "source_write_evidence_id": scope["source_write_evidence_id"],
            "world_id": scope["world_id"],
            "branch_id": scope["branch_id"],
            "runtime_generation": scope["runtime_generation"],
            "patch_id": scope["patch_id"],
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
            "execution_preflight_package_confirmed": true,
            "verified_outcome_package_confirmed": true,
            "admission_preflight_confirmed": true,
            "admission_decision_confirmed": true,
            "reviewer_attestation_present": true,
            "evidence_lineage_preserved": true,
            "ready_for_verified_outcome_ingestion_apply": true,
            "verified_outcome_ingestion_execution_commit_output_only": true,
            "verified_outcome_ingested_by_this_tool": false,
            "world_verdict_persisted_by_this_tool": false,
            "durable_outcome_record_written_by_this_tool": false,
            "memory_write_allowed": false,
            "outcome_ingestion_allowed": false
        },
        "agent_action_contract": {
            "mode": "runtime_executor_verified_outcome_ingestion_execution_commit_only",
            "may_enter_verified_outcome_ingestion_apply_after_commit": true,
            "may_execute_verified_outcome_ingestion": false,
            "do_not_ingest_outcome": true,
            "do_not_write_memory": true,
            "do_not_persist_world_verdict": true,
            "do_not_persist_outcome_record": true,
            "require_separate_verified_outcome_ingestion_apply": true
        },
        "verified_outcome_ingestion_execution_commit_performed_by_this_tool": true,
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

fn fixture_verified_outcome_ingestion_apply_decision() -> Value {
    json!({
        "schema": LSWR_RUNTIME_EXECUTOR_VERIFIED_OUTCOME_INGESTION_APPLY_DECISION_SCHEMA,
        "apply_decision_id": "verified_outcome_ingestion_apply_arrival_bath_move_002",
        "decision_kind": "verified_outcome_ingestion_apply",
        "source_verified_outcome_ingestion_execution_commit_scope": fixture_apply_scope(),
        "decision": "approved_for_verified_outcome_ingestion_writer",
        "apply_reason": "verified_outcome_ingestion_execution_commit_is_scoped_and_ready_for_separate_writer",
        "source_world_verdict": "not_verified",
        "verified_world_verdict": "verified",
        "reviewed_verified_outcome_ingestion_execution_commit_verdict": "ready_for_verified_outcome_ingestion_apply",
        "commit_package_confirmed": true,
        "execution_preflight_package_confirmed": true,
        "verified_outcome_package_confirmed": true,
        "reviewer_attestation_present": true,
        "evidence_lineage_preserved": true,
        "outcome_record_digest_confirmed": true,
        "idempotency_key_confirmed": true,
        "persisted_key_confirmed": true,
        "persisted_digest_confirmed": true,
        "writer_boundary_acknowledged": true,
        "outcome_ingestion_allowed_by_this_tool": false,
        "memory_write_allowed": false,
        "verified_outcome_ingested_by_this_tool": false,
        "durable_outcome_record_written_by_this_tool": false,
        "world_verdict_persisted_by_this_tool": false
    })
}

fn fixture_verified_outcome_ingestion_apply_decision_from_admission_source_commit() -> Value {
    json!({
        "schema": LSWR_RUNTIME_EXECUTOR_VERIFIED_OUTCOME_INGESTION_APPLY_DECISION_SCHEMA,
        "apply_decision_id": "verified_outcome_ingestion_apply_from_admission_arrival_bath_move_002",
        "decision_kind": "verified_outcome_ingestion_apply",
        "source_verified_outcome_ingestion_execution_commit_scope":
            fixture_apply_scope_from_admission_source_commit(),
        "decision": "approved_for_verified_outcome_ingestion_writer",
        "apply_reason": "admission_source_verified_outcome_ingestion_execution_commit_is_scoped_and_ready_for_separate_writer",
        "source_world_verdict": "not_verified",
        "verified_world_verdict": "verified",
        "reviewed_verified_outcome_ingestion_execution_commit_verdict": "ready_for_verified_outcome_ingestion_apply",
        "commit_package_confirmed": true,
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
        "writer_boundary_acknowledged": true,
        "outcome_ingestion_allowed_by_this_tool": false,
        "memory_write_allowed": false,
        "verified_outcome_ingested_by_this_tool": false,
        "durable_outcome_record_written_by_this_tool": false,
        "world_verdict_persisted_by_this_tool": false
    })
}

fn fixture_apply_scope() -> Value {
    json!({
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

fn fixture_apply_scope_from_admission_source_commit() -> Value {
    json!({
        "commit_decision_id": "verified_outcome_ingestion_execution_commit_from_admission_arrival_bath_move_002",
        "source_execution_decision_id": "verified_outcome_ingestion_execution_from_admission_arrival_bath_move_002",
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
        "source_apply_decision_id": "verified_outcome_ingestion_apply_arrival_bath_move_002",
        "source_commit_decision_id": "verified_outcome_ingestion_execution_commit_arrival_bath_move_002",
        "source_prior_execution_decision_id": "verified_outcome_ingestion_execution_arrival_bath_move_002",
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

fn assert_blocked_without_verified_outcome_ingestion_apply_decision(apply: &Value) -> Result<()> {
    assert_eq(apply, "verified_outcome_ingestion_apply_verdict", "blocked")?;
    assert_eq(
        apply,
        "reason",
        "explicit_verified_outcome_ingestion_apply_decision_required",
    )?;
    Ok(())
}

fn assert_ready_for_verified_outcome_ingestion_writer(apply: &Value) -> Result<()> {
    assert_eq(
        apply,
        "verified_outcome_ingestion_apply_verdict",
        "ready_for_verified_outcome_ingestion_writer",
    )?;
    assert_eq(
        apply,
        "next_allowed_gate",
        "verified_outcome_ingestion_writer",
    )?;
    if apply["verified_outcome_ingestion_apply"]["previous_world_verdict"] != "not_verified" {
        bail!("expected previous_world_verdict=not_verified");
    }
    if apply["verified_outcome_ingestion_apply"]["verified_world_verdict"] != "verified" {
        bail!("expected verified_world_verdict=verified");
    }
    if apply["verified_outcome_ingestion_apply"]["ready_for_verified_outcome_ingestion_writer"]
        != true
    {
        bail!("expected ready_for_verified_outcome_ingestion_writer=true");
    }
    if apply["source_verified_outcome_ingestion_admission_preflight_verdict"] != Value::Null {
        assert_eq(
            apply,
            "source_verified_outcome_ingestion_admission_preflight_verdict",
            "ready_for_verified_outcome_ingestion_execution",
        )?;
        if apply["verified_outcome_ingestion_apply"]["source_admission_decision_id"]
            .as_str()
            .is_none()
        {
            bail!("expected admission-source lineage in apply output");
        }
        if apply["verified_outcome_ingestion_apply"]["admission_preflight_confirmed"] != true {
            bail!("expected admission_preflight_confirmed=true");
        }
        if apply["verified_outcome_ingestion_apply"]["admission_decision_confirmed"] != true {
            bail!("expected admission_decision_confirmed=true");
        }
    }
    Ok(())
}

fn assert_output_only_contract(apply: &Value) -> Result<()> {
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
        if apply[key] != false {
            bail!("expected {key}=false");
        }
    }

    for key in [
        "read_only",
        "requires_ready_verified_outcome_ingestion_execution_commit",
        "accepts_admission_source_verified_outcome_ingestion_execution_commit",
        "preserves_verified_outcome_ingestion_admission_lineage",
        "requires_explicit_verified_outcome_ingestion_apply_decision",
        "performs_verified_outcome_ingestion_apply_gate",
    ] {
        if apply["guardrails"][key] != true {
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
        "outcome_ingestion_allowed_by_this_tool",
        "persists_outcome_record",
    ] {
        if apply["guardrails"][key] != false {
            bail!("expected guardrails.{key}=false");
        }
    }

    if apply["guardrails"]["mutation_surface"] != "output_only" {
        bail!("expected guardrails.mutation_surface=output_only");
    }

    for key in [
        "do_not_ingest_outcome",
        "do_not_write_memory",
        "do_not_persist_world_verdict",
        "do_not_persist_outcome_record",
        "require_separate_verified_outcome_ingestion_writer",
    ] {
        if apply["agent_action_contract"][key] != true {
            bail!("expected agent_action_contract.{key}=true");
        }
    }
    if apply["agent_action_contract"]["may_execute_verified_outcome_ingestion_by_this_tool"]
        != false
    {
        bail!("expected may_execute_verified_outcome_ingestion_by_this_tool=false");
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
    from_verified_outcome_ingestion_admission_source_commit: bool,
    with_verified_outcome_ingestion_apply_decision: bool,
    assert_blocked_without_verified_outcome_ingestion_apply_decision: bool,
    assert_ready_for_verified_outcome_ingestion_writer: bool,
    assert_output_only: bool,
    format: OutputFormat,
}

impl Args {
    fn parse(args: impl Iterator<Item = String>) -> Result<Self> {
        let mut parsed = Self {
            from_verified_outcome_ingestion_admission_source_commit: false,
            with_verified_outcome_ingestion_apply_decision: false,
            assert_blocked_without_verified_outcome_ingestion_apply_decision: false,
            assert_ready_for_verified_outcome_ingestion_writer: false,
            assert_output_only: false,
            format: OutputFormat::Markdown,
        };

        let mut args = args.peekable();
        while let Some(arg) = args.next() {
            match arg.as_str() {
                "--from-verified-outcome-ingestion-admission-source-commit" => {
                    parsed.from_verified_outcome_ingestion_admission_source_commit = true;
                }
                "--with-verified-outcome-ingestion-apply-decision" => {
                    parsed.with_verified_outcome_ingestion_apply_decision = true;
                }
                "--assert-blocked-without-verified-outcome-ingestion-apply-decision" => {
                    parsed.assert_blocked_without_verified_outcome_ingestion_apply_decision = true;
                }
                "--assert-ready-for-verified-outcome-ingestion-writer" => {
                    parsed.assert_ready_for_verified_outcome_ingestion_writer = true;
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
    r#"Usage: cargo run -q -p ab-bridge --example lswr_interaction_feedback_runtime_executor_verified_outcome_ingestion_apply_gate_smoke -- [options]

Options:
  --from-verified-outcome-ingestion-admission-source-commit
  --with-verified-outcome-ingestion-apply-decision
  --assert-blocked-without-verified-outcome-ingestion-apply-decision
  --assert-ready-for-verified-outcome-ingestion-writer
  --assert-output-only
  --format=json|markdown|both
"#
}
