//! Repeatable LSWR interaction-feedback outcome-ingestion review preflight smoke.
//!
//! This validates an explicit outcome-ingestion review decision against a
//! minimal accepted G6 post-apply verification preflight. It never performs
//! durable outcome ingestion, writes memory/store rows, registers MCP tools, or
//! rewrites world verdicts.

use ab_bridge::lswr_interaction_feedback::{
    build_interaction_feedback_runtime_executor_outcome_ingestion_review_preflight,
    build_interaction_feedback_runtime_executor_post_apply_verification_preflight,
    render_interaction_feedback_runtime_executor_outcome_ingestion_review_preflight,
    LSWR_INTERACTION_FEEDBACK_RUNTIME_EXECUTOR_PATCH_RUNTIME_APPLICATION_EVIDENCE_PREFLIGHT_SCHEMA,
    LSWR_RUNTIME_EXECUTOR_OUTCOME_INGESTION_REVIEW_DECISION_SCHEMA,
    LSWR_RUNTIME_EXECUTOR_POST_APPLY_VERIFICATION_EVIDENCE_SCHEMA,
};
use anyhow::{bail, Context, Result};
use serde_json::{json, Value};

fn main() -> Result<()> {
    let args = Args::parse(std::env::args().skip(1))?;
    let verification_preflight =
        build_interaction_feedback_runtime_executor_post_apply_verification_preflight(&json!({
            "patch_runtime_application_evidence_preflight": fixture_application_preflight(),
            "post_apply_verification_evidence": fixture_post_apply_verification_evidence()
        }));
    let input = if args.with_outcome_ingestion_review_decision {
        json!({
            "post_apply_verification_preflight": verification_preflight,
            "outcome_ingestion_review_decision": fixture_outcome_ingestion_review_decision()
        })
    } else {
        verification_preflight
    };
    let ingestion_preflight =
        build_interaction_feedback_runtime_executor_outcome_ingestion_review_preflight(&input);
    let markdown = render_interaction_feedback_runtime_executor_outcome_ingestion_review_preflight(
        &ingestion_preflight,
    );

    if args.assert_blocked_without_outcome_ingestion_review_decision {
        assert_blocked_without_outcome_ingestion_review_decision(&ingestion_preflight)?;
    }
    if args.assert_ready_for_durable_ingestion_gate {
        assert_ready_for_durable_ingestion_gate(&ingestion_preflight)?;
    }
    if args.assert_read_only {
        assert_read_only_contract(&ingestion_preflight)?;
    }

    match args.format {
        OutputFormat::Markdown => println!("{markdown}"),
        OutputFormat::Json => {
            println!("{}", serde_json::to_string_pretty(&ingestion_preflight)?)
        }
        OutputFormat::Both => {
            println!("{markdown}");
            println!("{}", serde_json::to_string_pretty(&ingestion_preflight)?);
        }
    }

    Ok(())
}

fn fixture_application_preflight() -> Value {
    json!({
        "schema": LSWR_INTERACTION_FEEDBACK_RUNTIME_EXECUTOR_PATCH_RUNTIME_APPLICATION_EVIDENCE_PREFLIGHT_SCHEMA,
        "patch_runtime_application_evidence_preflight_verdict": "ready_for_post_apply_verification_review",
        "status": "ready",
        "reason": "patch_runtime_application_evidence_preflight_ready_for_post_apply_verification_review",
        "source_world_verdict": "not_verified",
        "failure_reasons": [],
        "guardrails": {
            "read_only": true,
            "mutation_surface": "none",
            "writes_state": false,
            "store_access_required": false,
            "mcp_tool_registered": false,
            "queries_live_runtime": false,
            "requires_ready_patch_executor_invocation_preflight": true,
            "requires_explicit_patch_runtime_application_evidence": true,
            "evidence_kind": "external_executor_claim",
            "invokes_patch_executor": false,
            "submits_executor_queue": false,
            "submits_apply_request": false,
            "applies_patch": false,
            "verifies_post_apply_result": false,
            "outcome_ingestion_allowed": false,
            "persists_evidence_record": false,
            "feedback_changes_world_verdict_allowed": false,
            "runtime_executor_patch_runtime_application_evidence_preflight_only": true
        },
        "agent_action_contract": {
            "mode": "runtime_executor_patch_runtime_application_evidence_preflight_only",
            "may_review_post_apply_verification_after_evidence": true,
            "do_not_invoke_patch_executor": true,
            "do_not_submit_executor_queue": true,
            "do_not_submit_apply_request": true,
            "do_not_apply_patch": true,
            "do_not_verify_post_apply_result": true,
            "do_not_ingest_outcome": true,
            "do_not_write_memory": true,
            "do_not_rewrite_world_verdict": true,
            "require_post_apply_verification_after_application": true,
            "require_separate_outcome_ingestion_review": true
        },
        "runtime_application_evidence": {
            "evidence_id": "runtime_application_evidence_arrival_bath_move_002",
            "source_invocation_request_id": "patch_executor_invocation_arrival_bath_move_002",
            "target_executor": "separate_lswr_patch_executor",
            "executor_id": "executor:lswr_patch_worker_fixture",
            "executor_invoked_at": "2026-06-16T07:31:00Z",
            "patch_applied_at": "2026-06-16T07:31:02Z",
            "world_id": "onsen_live_session",
            "branch_id": "main",
            "runtime_generation": "runtime_gen_1284",
            "patch_id": "patch_arrival_bath_move_002",
            "source_apply_request_id": "apply_request_arrival_bath_move_002",
            "external_executor_invocation_observed": true,
            "external_patch_application_claimed": true,
            "external_runtime_mutation_claimed": true,
            "application_status": "applied_claimed_not_verified",
            "post_apply_verification_performed_by_this_tool": false,
            "post_apply_verification_performed_by_evidence": false,
            "outcome_ingestion_allowed": false,
            "world_verdict_rewrite_allowed": false,
            "evidence_record_persisted_by_this_tool": false
        }
    })
}

fn fixture_post_apply_verification_evidence() -> Value {
    json!({
        "schema": LSWR_RUNTIME_EXECUTOR_POST_APPLY_VERIFICATION_EVIDENCE_SCHEMA,
        "verification_id": "post_apply_verification_arrival_bath_move_002",
        "evidence_kind": "post_apply_verification",
        "verified_at": "2026-06-16T07:32:00Z",
        "source_runtime_application_evidence_scope": {
            "runtime_application_evidence_id": "runtime_application_evidence_arrival_bath_move_002",
            "source_invocation_request_id": "patch_executor_invocation_arrival_bath_move_002",
            "world_id": "onsen_live_session",
            "branch_id": "main",
            "runtime_generation": "runtime_gen_1284",
            "patch_id": "patch_arrival_bath_move_002"
        },
        "verification_verdict": "verified",
        "verification_reason": "expected_effect_and_presentation_readback_match",
        "expected_effect_checked": true,
        "expected_effect_passed": true,
        "presentation_readback_checked": true,
        "presentation_readback_consistent": true,
        "failed_clause_ids": [],
        "outcome_ingestion_allowed": false,
        "world_verdict_rewrite_allowed": false,
        "verification_record_persisted": false
    })
}

fn fixture_outcome_ingestion_review_decision() -> Value {
    json!({
        "schema": LSWR_RUNTIME_EXECUTOR_OUTCOME_INGESTION_REVIEW_DECISION_SCHEMA,
        "review_id": "outcome_ingestion_review_arrival_bath_move_002",
        "review_kind": "outcome_ingestion_review",
        "reviewed_at": "2026-06-16T07:33:00Z",
        "source_post_apply_verification_scope": {
            "verification_id": "post_apply_verification_arrival_bath_move_002",
            "runtime_application_evidence_id": "runtime_application_evidence_arrival_bath_move_002",
            "source_invocation_request_id": "patch_executor_invocation_arrival_bath_move_002",
            "world_id": "onsen_live_session",
            "branch_id": "main",
            "runtime_generation": "runtime_gen_1284",
            "patch_id": "patch_arrival_bath_move_002"
        },
        "decision": "approved_for_durable_ingestion_gate",
        "review_reason": "verified_effect_and_presentation_evidence_ready_for_durable_gate",
        "source_world_verdict": "not_verified",
        "reviewed_verification_verdict": "verified",
        "expected_effect_confirmed_for_ingestion": true,
        "presentation_readback_confirmed_for_ingestion": true,
        "durable_ingestion_allowed": false,
        "world_verdict_rewrite_allowed": false,
        "outcome_record_persisted": false
    })
}

fn assert_blocked_without_outcome_ingestion_review_decision(preflight: &Value) -> Result<()> {
    if preflight
        .get("outcome_ingestion_review_preflight_verdict")
        .and_then(Value::as_str)
        != Some("blocked")
    {
        bail!("outcome-ingestion review preflight must block without decision");
    }
    if preflight.get("reason").and_then(Value::as_str)
        != Some("explicit_outcome_ingestion_review_decision_required")
    {
        bail!("blocked preflight must require explicit outcome-ingestion review decision");
    }
    Ok(())
}

fn assert_ready_for_durable_ingestion_gate(preflight: &Value) -> Result<()> {
    if preflight
        .get("outcome_ingestion_review_preflight_verdict")
        .and_then(Value::as_str)
        != Some("ready_for_durable_ingestion_gate")
    {
        bail!("outcome-ingestion review preflight must be ready for durable ingestion gate");
    }
    if preflight["outcome_ingestion_review"]["decision"].as_str()
        != Some("approved_for_durable_ingestion_gate")
    {
        bail!("ready preflight must carry explicit review decision");
    }
    if preflight["outcome_ingestion_review"]["durable_ingestion_allowed"].as_bool() != Some(false) {
        bail!("outcome-ingestion review preflight must not allow durable ingestion");
    }
    if preflight["outcome_ingestion_review"]["world_verdict_rewrite_allowed"].as_bool()
        != Some(false)
    {
        bail!("outcome-ingestion review preflight must not rewrite world verdict");
    }
    Ok(())
}

fn assert_read_only_contract(preflight: &Value) -> Result<()> {
    for key in [
        "outcome_ingestion_review_performed_by_this_tool",
        "durable_outcome_ingestion_performed_by_this_tool",
        "world_verdict_rewrite_performed_by_this_tool",
        "writes_state",
        "store_access_required",
        "mcp_tool_registered",
    ] {
        if preflight.get(key).and_then(Value::as_bool) != Some(false) {
            bail!("outcome-ingestion review preflight {key} must be false");
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
    with_outcome_ingestion_review_decision: bool,
    assert_blocked_without_outcome_ingestion_review_decision: bool,
    assert_ready_for_durable_ingestion_gate: bool,
    assert_read_only: bool,
    format: OutputFormat,
}

impl Args {
    fn parse(args: impl IntoIterator<Item = String>) -> Result<Self> {
        let mut with_outcome_ingestion_review_decision = false;
        let mut assert_blocked_without_outcome_ingestion_review_decision = false;
        let mut assert_ready_for_durable_ingestion_gate = false;
        let mut assert_read_only = false;
        let mut format = OutputFormat::Markdown;
        let mut iter = args.into_iter();

        while let Some(arg) = iter.next() {
            match arg.as_str() {
                "--with-outcome-ingestion-review-decision" => {
                    with_outcome_ingestion_review_decision = true
                }
                "--assert-blocked-without-outcome-ingestion-review-decision" => {
                    assert_blocked_without_outcome_ingestion_review_decision = true
                }
                "--assert-ready-for-durable-ingestion-gate" => {
                    assert_ready_for_durable_ingestion_gate = true
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

        if assert_blocked_without_outcome_ingestion_review_decision
            && with_outcome_ingestion_review_decision
        {
            bail!(
                "--assert-blocked-without-outcome-ingestion-review-decision cannot be combined with --with-outcome-ingestion-review-decision"
            );
        }
        if assert_ready_for_durable_ingestion_gate && !with_outcome_ingestion_review_decision {
            bail!(
                "--assert-ready-for-durable-ingestion-gate requires --with-outcome-ingestion-review-decision"
            );
        }

        Ok(Self {
            with_outcome_ingestion_review_decision,
            assert_blocked_without_outcome_ingestion_review_decision,
            assert_ready_for_durable_ingestion_gate,
            assert_read_only,
            format,
        })
    }
}

fn usage() -> &'static str {
    "usage: cargo run -p ab-bridge --example lswr_interaction_feedback_runtime_executor_outcome_ingestion_review_preflight_smoke -- [--with-outcome-ingestion-review-decision] [--format markdown|json|both] [--assert-blocked-without-outcome-ingestion-review-decision] [--assert-ready-for-durable-ingestion-gate] [--assert-read-only]"
}
