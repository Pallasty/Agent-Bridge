//! Repeatable LSWR interaction-feedback runtime application evidence preflight smoke.
//!
//! This validates an explicit external runtime application evidence packet
//! against a minimal accepted G4 patch executor invocation preflight. It never
//! invokes an executor, submits queue work, applies patches, verifies
//! post-apply results, ingests outcomes, registers MCP tools, or writes
//! memory/store rows.

use ab_bridge::lswr_interaction_feedback::{
    build_interaction_feedback_runtime_executor_patch_runtime_application_evidence_preflight,
    render_interaction_feedback_runtime_executor_patch_runtime_application_evidence_preflight,
    LSWR_INTERACTION_FEEDBACK_RUNTIME_EXECUTOR_PATCH_EXECUTOR_INVOCATION_PREFLIGHT_SCHEMA,
    LSWR_RUNTIME_EXECUTOR_PATCH_RUNTIME_APPLICATION_EVIDENCE_SCHEMA,
};
use anyhow::{bail, Context, Result};
use serde_json::{json, Value};

fn main() -> Result<()> {
    let args = Args::parse(std::env::args().skip(1))?;
    let invocation_preflight = fixture_invocation_preflight();
    let input = if args.with_runtime_application_evidence {
        json!({
            "patch_executor_invocation_preflight": invocation_preflight,
            "patch_runtime_application_evidence": fixture_runtime_application_evidence()
        })
    } else {
        invocation_preflight
    };
    let evidence_preflight =
        build_interaction_feedback_runtime_executor_patch_runtime_application_evidence_preflight(
            &input,
        );
    let markdown =
        render_interaction_feedback_runtime_executor_patch_runtime_application_evidence_preflight(
            &evidence_preflight,
        );

    if args.assert_blocked_without_runtime_application_evidence {
        assert_blocked_without_runtime_application_evidence(&evidence_preflight)?;
    }
    if args.assert_ready_for_post_apply_verification_review {
        assert_ready_for_post_apply_verification_review(&evidence_preflight)?;
    }
    if args.assert_read_only {
        assert_read_only_contract(&evidence_preflight)?;
    }

    match args.format {
        OutputFormat::Markdown => println!("{markdown}"),
        OutputFormat::Json => println!("{}", serde_json::to_string_pretty(&evidence_preflight)?),
        OutputFormat::Both => {
            println!("{markdown}");
            println!("{}", serde_json::to_string_pretty(&evidence_preflight)?);
        }
    }

    Ok(())
}

fn fixture_invocation_preflight() -> Value {
    json!({
        "schema": LSWR_INTERACTION_FEEDBACK_RUNTIME_EXECUTOR_PATCH_EXECUTOR_INVOCATION_PREFLIGHT_SCHEMA,
        "patch_executor_invocation_preflight_verdict": "ready_for_separate_patch_executor_invocation_request",
        "status": "ready",
        "reason": "patch_executor_invocation_preflight_ready_for_invocation_request",
        "source_world_verdict": "not_verified",
        "failure_reasons": [],
        "guardrails": {
            "read_only": true,
            "mutation_surface": "none",
            "writes_state": false,
            "store_access_required": false,
            "mcp_tool_registered": false,
            "queries_live_runtime": false,
            "requires_ready_patch_application_gate_preflight": true,
            "requires_explicit_patch_executor_invocation_decision": true,
            "patch_executor_invocation_authority_scope": "separate_patch_executor_invocation_only",
            "emits_invocation_request_envelope": true,
            "invokes_patch_executor": false,
            "submits_executor_queue": false,
            "submits_apply_request": false,
            "applies_patch": false,
            "verifies_post_apply_result": false,
            "outcome_ingestion_allowed": false,
            "persists_submission_token": false,
            "feedback_changes_world_verdict_allowed": false,
            "runtime_executor_patch_executor_invocation_preflight_only": true
        },
        "agent_action_contract": {
            "mode": "runtime_executor_patch_executor_invocation_preflight_only",
            "may_emit_invocation_request_envelope_after_gate": true,
            "do_not_invoke_patch_executor": true,
            "do_not_submit_executor_queue": true,
            "do_not_submit_apply_request": true,
            "do_not_apply_patch": true,
            "do_not_ingest_outcome": true,
            "do_not_write_memory": true,
            "do_not_rewrite_world_verdict": true,
            "do_not_verify_post_apply_result": true,
            "require_runtime_application_evidence_after_invocation": true,
            "require_post_apply_verification_after_application": true,
            "require_separate_outcome_ingestion_review": true
        },
        "patch_executor_invocation_request": {
            "request_id": "patch_executor_invocation_arrival_bath_move_002",
            "target_executor": "separate_lswr_patch_executor",
            "request_type": "patch_executor_invocation_request",
            "invocation_decision_id": "patch_executor_invocation_decision_arrival_bath_move_002",
            "operator_id": "human:owner",
            "approved_at": "2026-06-16T07:30:00Z",
            "expires_at": "2026-06-16T23:59:59Z",
            "patch_application_gate_id": "patch_application_gate_arrival_bath_move_002",
            "patch_application_gate_decision_id": "patch_application_gate_decision_arrival_bath_move_002",
            "patch_application_gate_idempotency_key": "patch_arrival_bath_move_002/runtime_gen_1284/submit_patch_arrival_bath_move_002/patch_application_gate_decision_arrival_bath_move_002",
            "operator_submission_token_id": "submit_patch_arrival_bath_move_002",
            "operator_submission_decision_id": "operator_decision_arrival_bath_move_002",
            "lookup_evidence_id": "live_lookup_arrival_bath_move_002",
            "source_apply_request_id": "apply_request_arrival_bath_move_002",
            "world_id": "onsen_live_session",
            "branch_id": "main",
            "runtime_generation": "runtime_gen_1284",
            "patch_id": "patch_arrival_bath_move_002",
            "target_entities": ["bath"],
            "idempotency_key": "patch_arrival_bath_move_002/runtime_gen_1284/patch_application_gate_arrival_bath_move_002/patch_executor_invocation_decision_arrival_bath_move_002",
            "ready_for_separate_patch_executor_invocation_request": true,
            "invocation_request_emitted_by_this_tool": true,
            "executor_invocation_performed_by_this_tool": false,
            "executor_queue_submission_performed": false,
            "apply_request_submitted": false,
            "patch_application_performed": false,
            "verification_performed": false,
            "outcome_ingestion_allowed": false
        }
    })
}

fn fixture_runtime_application_evidence() -> Value {
    json!({
        "schema": LSWR_RUNTIME_EXECUTOR_PATCH_RUNTIME_APPLICATION_EVIDENCE_SCHEMA,
        "evidence_id": "runtime_application_evidence_arrival_bath_move_002",
        "evidence_kind": "external_executor_claim",
        "target_executor": "separate_lswr_patch_executor",
        "executor_id": "executor:lswr_patch_worker_fixture",
        "executor_invoked_at": "2026-06-16T07:31:00Z",
        "patch_applied_at": "2026-06-16T07:31:02Z",
        "source_invocation_request_scope": {
            "request_id": "patch_executor_invocation_arrival_bath_move_002",
            "idempotency_key": "patch_arrival_bath_move_002/runtime_gen_1284/patch_application_gate_arrival_bath_move_002/patch_executor_invocation_decision_arrival_bath_move_002",
            "invocation_decision_id": "patch_executor_invocation_decision_arrival_bath_move_002",
            "world_id": "onsen_live_session",
            "branch_id": "main",
            "runtime_generation": "runtime_gen_1284",
            "patch_id": "patch_arrival_bath_move_002",
            "source_apply_request_id": "apply_request_arrival_bath_move_002"
        },
        "executor_invocation_observed": true,
        "patch_application_claimed": true,
        "runtime_mutation_claimed": true,
        "application_status": "applied_claimed_not_verified",
        "post_apply_verification_performed": false,
        "outcome_ingestion_allowed": false,
        "world_verdict_rewrite_allowed": false,
        "evidence_record_persisted": false
    })
}

fn assert_blocked_without_runtime_application_evidence(preflight: &Value) -> Result<()> {
    if preflight
        .get("patch_runtime_application_evidence_preflight_verdict")
        .and_then(Value::as_str)
        != Some("blocked")
    {
        bail!("runtime application evidence preflight must block without evidence");
    }
    if preflight.get("reason").and_then(Value::as_str)
        != Some("explicit_patch_runtime_application_evidence_required")
    {
        bail!("blocked preflight must require explicit runtime application evidence");
    }
    Ok(())
}

fn assert_ready_for_post_apply_verification_review(preflight: &Value) -> Result<()> {
    if preflight
        .get("patch_runtime_application_evidence_preflight_verdict")
        .and_then(Value::as_str)
        != Some("ready_for_post_apply_verification_review")
    {
        bail!("runtime application evidence preflight must be ready for verification review");
    }
    if preflight["runtime_application_evidence"]["external_patch_application_claimed"].as_bool()
        != Some(true)
    {
        bail!("ready preflight must carry external patch application claim");
    }
    if preflight["runtime_application_evidence"]["post_apply_verification_performed_by_this_tool"]
        .as_bool()
        != Some(false)
    {
        bail!("evidence preflight must not verify post-apply result");
    }
    Ok(())
}

fn assert_read_only_contract(preflight: &Value) -> Result<()> {
    for key in [
        "executor_invocation_performed_by_this_tool",
        "executor_queue_submission_performed_by_this_tool",
        "apply_request_submitted_by_this_tool",
        "patch_application_performed_by_this_tool",
        "post_apply_verification_performed_by_this_tool",
        "outcome_ingestion_performed_by_this_tool",
        "writes_state",
        "store_access_required",
        "mcp_tool_registered",
    ] {
        if preflight.get(key).and_then(Value::as_bool) != Some(false) {
            bail!("runtime application evidence preflight {key} must be false");
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
    with_runtime_application_evidence: bool,
    assert_blocked_without_runtime_application_evidence: bool,
    assert_ready_for_post_apply_verification_review: bool,
    assert_read_only: bool,
    format: OutputFormat,
}

impl Args {
    fn parse(args: impl IntoIterator<Item = String>) -> Result<Self> {
        let mut with_runtime_application_evidence = false;
        let mut assert_blocked_without_runtime_application_evidence = false;
        let mut assert_ready_for_post_apply_verification_review = false;
        let mut assert_read_only = false;
        let mut format = OutputFormat::Markdown;
        let mut iter = args.into_iter();

        while let Some(arg) = iter.next() {
            match arg.as_str() {
                "--with-runtime-application-evidence" => with_runtime_application_evidence = true,
                "--assert-blocked-without-runtime-application-evidence" => {
                    assert_blocked_without_runtime_application_evidence = true
                }
                "--assert-ready-for-post-apply-verification-review" => {
                    assert_ready_for_post_apply_verification_review = true
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

        if assert_blocked_without_runtime_application_evidence && with_runtime_application_evidence
        {
            bail!(
                "--assert-blocked-without-runtime-application-evidence cannot be combined with --with-runtime-application-evidence"
            );
        }
        if assert_ready_for_post_apply_verification_review && !with_runtime_application_evidence {
            bail!(
                "--assert-ready-for-post-apply-verification-review requires --with-runtime-application-evidence"
            );
        }

        Ok(Self {
            with_runtime_application_evidence,
            assert_blocked_without_runtime_application_evidence,
            assert_ready_for_post_apply_verification_review,
            assert_read_only,
            format,
        })
    }
}

fn usage() -> &'static str {
    "usage: cargo run -p ab-bridge --example lswr_interaction_feedback_runtime_executor_patch_runtime_application_evidence_preflight_smoke -- [--with-runtime-application-evidence] [--format markdown|json|both] [--assert-blocked-without-runtime-application-evidence] [--assert-ready-for-post-apply-verification-review] [--assert-read-only]"
}
