//! Repeatable LSWR interaction-feedback post-apply verification preflight smoke.
//!
//! This validates explicit post-apply verification evidence against a minimal
//! accepted G5 runtime application evidence preflight. It never ingests
//! outcomes, writes memory/store rows, registers MCP tools, or rewrites world
//! verdicts.

use ab_bridge::lswr_interaction_feedback::{
    build_interaction_feedback_runtime_executor_post_apply_verification_preflight,
    render_interaction_feedback_runtime_executor_post_apply_verification_preflight,
    LSWR_INTERACTION_FEEDBACK_RUNTIME_EXECUTOR_PATCH_RUNTIME_APPLICATION_EVIDENCE_PREFLIGHT_SCHEMA,
    LSWR_RUNTIME_EXECUTOR_POST_APPLY_VERIFICATION_EVIDENCE_SCHEMA,
};
use anyhow::{bail, Context, Result};
use serde_json::{json, Value};

fn main() -> Result<()> {
    let args = Args::parse(std::env::args().skip(1))?;
    let application_preflight = fixture_application_preflight();
    let input = if args.with_post_apply_verification_evidence {
        json!({
            "patch_runtime_application_evidence_preflight": application_preflight,
            "post_apply_verification_evidence": fixture_post_apply_verification_evidence()
        })
    } else {
        application_preflight
    };
    let verification_preflight =
        build_interaction_feedback_runtime_executor_post_apply_verification_preflight(&input);
    let markdown = render_interaction_feedback_runtime_executor_post_apply_verification_preflight(
        &verification_preflight,
    );

    if args.assert_blocked_without_post_apply_verification_evidence {
        assert_blocked_without_post_apply_verification_evidence(&verification_preflight)?;
    }
    if args.assert_ready_for_outcome_ingestion_review {
        assert_ready_for_outcome_ingestion_review(&verification_preflight)?;
    }
    if args.assert_read_only {
        assert_read_only_contract(&verification_preflight)?;
    }

    match args.format {
        OutputFormat::Markdown => println!("{markdown}"),
        OutputFormat::Json => {
            println!("{}", serde_json::to_string_pretty(&verification_preflight)?)
        }
        OutputFormat::Both => {
            println!("{markdown}");
            println!("{}", serde_json::to_string_pretty(&verification_preflight)?);
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

fn assert_blocked_without_post_apply_verification_evidence(preflight: &Value) -> Result<()> {
    if preflight
        .get("post_apply_verification_preflight_verdict")
        .and_then(Value::as_str)
        != Some("blocked")
    {
        bail!("post-apply verification preflight must block without evidence");
    }
    if preflight.get("reason").and_then(Value::as_str)
        != Some("explicit_post_apply_verification_evidence_required")
    {
        bail!("blocked preflight must require explicit post-apply verification evidence");
    }
    Ok(())
}

fn assert_ready_for_outcome_ingestion_review(preflight: &Value) -> Result<()> {
    if preflight
        .get("post_apply_verification_preflight_verdict")
        .and_then(Value::as_str)
        != Some("ready_for_outcome_ingestion_review")
    {
        bail!("post-apply verification preflight must be ready for outcome review");
    }
    if preflight["post_apply_verification"]["verification_verdict"].as_str() != Some("verified") {
        bail!("ready preflight must carry explicit verification verdict");
    }
    if preflight["post_apply_verification"]["outcome_ingestion_allowed"].as_bool() != Some(false) {
        bail!("post-apply verification preflight must not allow ingestion");
    }
    if preflight["post_apply_verification"]["world_verdict_rewrite_allowed"].as_bool()
        != Some(false)
    {
        bail!("post-apply verification preflight must not rewrite world verdict");
    }
    Ok(())
}

fn assert_read_only_contract(preflight: &Value) -> Result<()> {
    for key in [
        "post_apply_verification_performed_by_this_tool",
        "outcome_ingestion_performed_by_this_tool",
        "world_verdict_rewrite_performed_by_this_tool",
        "writes_state",
        "store_access_required",
        "mcp_tool_registered",
    ] {
        if preflight.get(key).and_then(Value::as_bool) != Some(false) {
            bail!("post-apply verification preflight {key} must be false");
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
    with_post_apply_verification_evidence: bool,
    assert_blocked_without_post_apply_verification_evidence: bool,
    assert_ready_for_outcome_ingestion_review: bool,
    assert_read_only: bool,
    format: OutputFormat,
}

impl Args {
    fn parse(args: impl IntoIterator<Item = String>) -> Result<Self> {
        let mut with_post_apply_verification_evidence = false;
        let mut assert_blocked_without_post_apply_verification_evidence = false;
        let mut assert_ready_for_outcome_ingestion_review = false;
        let mut assert_read_only = false;
        let mut format = OutputFormat::Markdown;
        let mut iter = args.into_iter();

        while let Some(arg) = iter.next() {
            match arg.as_str() {
                "--with-post-apply-verification-evidence" => {
                    with_post_apply_verification_evidence = true
                }
                "--assert-blocked-without-post-apply-verification-evidence" => {
                    assert_blocked_without_post_apply_verification_evidence = true
                }
                "--assert-ready-for-outcome-ingestion-review" => {
                    assert_ready_for_outcome_ingestion_review = true
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

        if assert_blocked_without_post_apply_verification_evidence
            && with_post_apply_verification_evidence
        {
            bail!(
                "--assert-blocked-without-post-apply-verification-evidence cannot be combined with --with-post-apply-verification-evidence"
            );
        }
        if assert_ready_for_outcome_ingestion_review && !with_post_apply_verification_evidence {
            bail!(
                "--assert-ready-for-outcome-ingestion-review requires --with-post-apply-verification-evidence"
            );
        }

        Ok(Self {
            with_post_apply_verification_evidence,
            assert_blocked_without_post_apply_verification_evidence,
            assert_ready_for_outcome_ingestion_review,
            assert_read_only,
            format,
        })
    }
}

fn usage() -> &'static str {
    "usage: cargo run -p ab-bridge --example lswr_interaction_feedback_runtime_executor_post_apply_verification_preflight_smoke -- [--with-post-apply-verification-evidence] [--format markdown|json|both] [--assert-blocked-without-post-apply-verification-evidence] [--assert-ready-for-outcome-ingestion-review] [--assert-read-only]"
}
