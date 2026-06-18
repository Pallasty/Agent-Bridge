//! Repeatable LSWR interaction-feedback durable outcome-ingestion execution preflight smoke.
//!
//! This validates an explicit durable-ingestion execution decision against a
//! minimal accepted G8 durable outcome-ingestion gate preflight. It never
//! writes durable outcome records, touches memory/store rows, registers MCP
//! tools, or rewrites world verdicts.

use ab_bridge::lswr_interaction_feedback::{
    build_interaction_feedback_runtime_executor_durable_outcome_ingestion_execution_preflight,
    render_interaction_feedback_runtime_executor_durable_outcome_ingestion_execution_preflight,
    LSWR_INTERACTION_FEEDBACK_RUNTIME_EXECUTOR_DURABLE_OUTCOME_INGESTION_GATE_PREFLIGHT_SCHEMA,
    LSWR_RUNTIME_EXECUTOR_DURABLE_OUTCOME_INGESTION_EXECUTION_DECISION_SCHEMA,
};
use anyhow::{bail, Context, Result};
use serde_json::{json, Value};

fn main() -> Result<()> {
    let args = Args::parse(std::env::args().skip(1))?;
    let gate_preflight = fixture_durable_outcome_ingestion_gate_preflight();
    let input = if args.with_durable_outcome_ingestion_execution_decision {
        json!({
            "durable_outcome_ingestion_gate_preflight": gate_preflight,
            "durable_outcome_ingestion_execution_decision": fixture_durable_outcome_ingestion_execution_decision()
        })
    } else {
        gate_preflight
    };
    let execution_preflight =
        build_interaction_feedback_runtime_executor_durable_outcome_ingestion_execution_preflight(
            &input,
        );
    let markdown =
        render_interaction_feedback_runtime_executor_durable_outcome_ingestion_execution_preflight(
            &execution_preflight,
        );

    if args.assert_blocked_without_durable_outcome_ingestion_execution_decision {
        assert_blocked_without_durable_outcome_ingestion_execution_decision(&execution_preflight)?;
    }
    if args.assert_ready_for_durable_outcome_ingestion_write_implementation {
        assert_ready_for_durable_outcome_ingestion_write_implementation(&execution_preflight)?;
    }
    if args.assert_read_only {
        assert_read_only_contract(&execution_preflight)?;
    }

    match args.format {
        OutputFormat::Markdown => println!("{markdown}"),
        OutputFormat::Json => {
            println!("{}", serde_json::to_string_pretty(&execution_preflight)?)
        }
        OutputFormat::Both => {
            println!("{markdown}");
            println!("{}", serde_json::to_string_pretty(&execution_preflight)?);
        }
    }

    Ok(())
}

fn fixture_durable_outcome_ingestion_gate_preflight() -> Value {
    json!({
        "schema": LSWR_INTERACTION_FEEDBACK_RUNTIME_EXECUTOR_DURABLE_OUTCOME_INGESTION_GATE_PREFLIGHT_SCHEMA,
        "durable_outcome_ingestion_gate_preflight_verdict": "ready_for_durable_outcome_ingestion_execution",
        "status": "ready",
        "reason": "durable_outcome_ingestion_gate_preflight_ready_for_execution",
        "source_world_verdict": "not_verified",
        "failure_reasons": [],
        "guardrails": {
            "read_only": true,
            "mutation_surface": "none",
            "writes_state": false,
            "store_access_required": false,
            "mcp_tool_registered": false,
            "queries_live_runtime": false,
            "requires_ready_outcome_ingestion_review_preflight": true,
            "requires_explicit_durable_outcome_ingestion_gate_decision": true,
            "gate_kind": "durable_outcome_ingestion_gate",
            "performs_durable_outcome_ingestion_gate": false,
            "durable_ingestion_execution_allowed": false,
            "persists_outcome_record": false,
            "feedback_changes_world_verdict_allowed": false,
            "runtime_executor_durable_outcome_ingestion_gate_preflight_only": true
        },
        "agent_action_contract": {
            "mode": "runtime_executor_durable_outcome_ingestion_gate_preflight_only",
            "may_execute_durable_outcome_ingestion_after_gate": true,
            "do_not_ingest_outcome": true,
            "do_not_write_memory": true,
            "do_not_rewrite_world_verdict": true,
            "do_not_persist_outcome_record": true,
            "require_separate_durable_ingestion_execution": true,
            "require_world_verdict_rewrite_gate_after_ingestion": true
        },
        "durable_outcome_ingestion_gate": {
            "gate_id": "durable_outcome_ingestion_gate_arrival_bath_move_002",
            "review_id": "outcome_ingestion_review_arrival_bath_move_002",
            "verification_id": "post_apply_verification_arrival_bath_move_002",
            "runtime_application_evidence_id": "runtime_application_evidence_arrival_bath_move_002",
            "source_invocation_request_id": "patch_executor_invocation_arrival_bath_move_002",
            "world_id": "onsen_live_session",
            "branch_id": "main",
            "runtime_generation": "runtime_gen_1284",
            "patch_id": "patch_arrival_bath_move_002",
            "decision": "approved_for_durable_ingestion_execution",
            "gate_reason": "reviewed_outcome_ready_for_separate_durable_execution",
            "outcome_record_candidate_id": "outcome_record_candidate_arrival_bath_move_002",
            "outcome_record_schema": "agent_bridge.lswr.outcome_record_candidate.v0",
            "idempotency_key": "onsen_live_session/main/runtime_gen_1284/patch_arrival_bath_move_002/outcome_ingestion_review_arrival_bath_move_002",
            "outcome_payload_complete": true,
            "ready_for_durable_outcome_ingestion_execution": true,
            "durable_outcome_ingestion_gate_performed_by_this_tool": false,
            "durable_ingestion_execution_allowed": false,
            "world_verdict_rewrite_allowed": false,
            "outcome_record_persisted_by_this_tool": false
        }
    })
}

fn fixture_durable_outcome_ingestion_execution_decision() -> Value {
    json!({
        "schema": LSWR_RUNTIME_EXECUTOR_DURABLE_OUTCOME_INGESTION_EXECUTION_DECISION_SCHEMA,
        "execution_id": "durable_outcome_ingestion_execution_arrival_bath_move_002",
        "execution_kind": "durable_outcome_ingestion_execution",
        "execution_preflighted_at": "2026-06-16T07:35:00Z",
        "source_durable_outcome_ingestion_gate_scope": {
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
            "idempotency_key": "onsen_live_session/main/runtime_gen_1284/patch_arrival_bath_move_002/outcome_ingestion_review_arrival_bath_move_002"
        },
        "decision": "approved_for_durable_outcome_ingestion_write_implementation",
        "execution_reason": "gate_ready_and_payload_scoped_for_later_durable_write_implementation",
        "source_world_verdict": "not_verified",
        "reviewed_gate_decision": "approved_for_durable_ingestion_execution",
        "outcome_payload_digest": "sha256:arrival-bath-move-002-outcome-payload",
        "write_plan_id": "durable_outcome_write_plan_arrival_bath_move_002",
        "outcome_payload_complete": true,
        "write_plan_complete": true,
        "durable_write_implementation_allowed": false,
        "durable_outcome_ingestion_performed": false,
        "world_verdict_rewrite_allowed": false,
        "outcome_record_persisted": false
    })
}

fn assert_blocked_without_durable_outcome_ingestion_execution_decision(
    preflight: &Value,
) -> Result<()> {
    if preflight
        .get("durable_outcome_ingestion_execution_preflight_verdict")
        .and_then(Value::as_str)
        != Some("blocked")
    {
        bail!("durable outcome-ingestion execution preflight must block without decision");
    }
    if preflight.get("reason").and_then(Value::as_str)
        != Some("explicit_durable_outcome_ingestion_execution_decision_required")
    {
        bail!(
            "blocked preflight must require explicit durable outcome-ingestion execution decision"
        );
    }
    Ok(())
}

fn assert_ready_for_durable_outcome_ingestion_write_implementation(
    preflight: &Value,
) -> Result<()> {
    if preflight
        .get("durable_outcome_ingestion_execution_preflight_verdict")
        .and_then(Value::as_str)
        != Some("ready_for_durable_outcome_ingestion_write_implementation")
    {
        bail!(
            "durable outcome-ingestion execution preflight must be ready for write implementation"
        );
    }
    if preflight["durable_outcome_ingestion_execution"]["decision"].as_str()
        != Some("approved_for_durable_outcome_ingestion_write_implementation")
    {
        bail!("ready preflight must carry explicit execution decision");
    }
    if preflight["durable_outcome_ingestion_execution"]["durable_write_implementation_allowed"]
        .as_bool()
        != Some(false)
    {
        bail!("durable outcome-ingestion execution preflight must not allow write implementation");
    }
    if preflight["durable_outcome_ingestion_execution"]["outcome_record_persisted_by_this_tool"]
        .as_bool()
        != Some(false)
    {
        bail!("durable outcome-ingestion execution preflight must not persist outcome records");
    }
    Ok(())
}

fn assert_read_only_contract(preflight: &Value) -> Result<()> {
    for key in [
        "durable_outcome_ingestion_performed_by_this_tool",
        "world_verdict_rewrite_performed_by_this_tool",
        "writes_state",
        "store_access_required",
        "mcp_tool_registered",
    ] {
        if preflight.get(key).and_then(Value::as_bool) != Some(false) {
            bail!("durable outcome-ingestion execution preflight {key} must be false");
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
    with_durable_outcome_ingestion_execution_decision: bool,
    assert_blocked_without_durable_outcome_ingestion_execution_decision: bool,
    assert_ready_for_durable_outcome_ingestion_write_implementation: bool,
    assert_read_only: bool,
    format: OutputFormat,
}

impl Args {
    fn parse(args: impl IntoIterator<Item = String>) -> Result<Self> {
        let mut with_durable_outcome_ingestion_execution_decision = false;
        let mut assert_blocked_without_durable_outcome_ingestion_execution_decision = false;
        let mut assert_ready_for_durable_outcome_ingestion_write_implementation = false;
        let mut assert_read_only = false;
        let mut format = OutputFormat::Markdown;
        let mut iter = args.into_iter();

        while let Some(arg) = iter.next() {
            match arg.as_str() {
                "--with-durable-outcome-ingestion-execution-decision" => {
                    with_durable_outcome_ingestion_execution_decision = true
                }
                "--assert-blocked-without-durable-outcome-ingestion-execution-decision" => {
                    assert_blocked_without_durable_outcome_ingestion_execution_decision = true
                }
                "--assert-ready-for-durable-outcome-ingestion-write-implementation" => {
                    assert_ready_for_durable_outcome_ingestion_write_implementation = true
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
                        other => bail!("unsupported --format value: {other}"),
                    };
                }
                "-h" | "--help" => bail!(usage()),
                other => bail!("unknown argument: {other}\n{}", usage()),
            }
        }

        if assert_blocked_without_durable_outcome_ingestion_execution_decision
            && with_durable_outcome_ingestion_execution_decision
        {
            bail!(
                "--assert-blocked-without-durable-outcome-ingestion-execution-decision cannot be combined with --with-durable-outcome-ingestion-execution-decision"
            );
        }
        if assert_ready_for_durable_outcome_ingestion_write_implementation
            && !with_durable_outcome_ingestion_execution_decision
        {
            bail!(
                "--assert-ready-for-durable-outcome-ingestion-write-implementation requires --with-durable-outcome-ingestion-execution-decision"
            );
        }

        Ok(Self {
            with_durable_outcome_ingestion_execution_decision,
            assert_blocked_without_durable_outcome_ingestion_execution_decision,
            assert_ready_for_durable_outcome_ingestion_write_implementation,
            assert_read_only,
            format,
        })
    }
}

fn usage() -> &'static str {
    "usage: cargo run -p ab-bridge --example lswr_interaction_feedback_runtime_executor_durable_outcome_ingestion_execution_preflight_smoke -- [--with-durable-outcome-ingestion-execution-decision] [--format markdown|json|both] [--assert-blocked-without-durable-outcome-ingestion-execution-decision] [--assert-ready-for-durable-outcome-ingestion-write-implementation] [--assert-read-only]"
}
