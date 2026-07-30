use ab_bridge::biocortex_capability_ledger::{
    build_biocortex_capability_ledger_report_packet, consume_biocortex_capability_ledger,
};
use ab_bridge::biocortex_shadow::{
    biocortex_retrieval_opt_in_audit_report,
    biocortex_retrieval_opt_in_authorization_decision_packet,
    biocortex_retrieval_opt_in_dry_run_plan, biocortex_retrieval_opt_in_execution_packet,
    biocortex_retrieval_opt_in_order_diff_packet,
    biocortex_retrieval_opt_in_redacted_order_artifact, biocortex_retrieval_opt_in_review_packet,
    biocortex_retrieval_opt_in_runtime_trial_review_packet,
    biocortex_retrieval_runtime_approval_packet_preview, biocortex_shadow_digest,
    supported_benchmarks, BioCortexRetrievalApprovalPacketOptions,
    BioCortexRetrievalOptInAuditOptions, BioCortexRetrievalOptInAuthorizationDecisionPacketOptions,
    BioCortexRetrievalOptInDryRunOptions, BioCortexRetrievalOptInExecutionPacketOptions,
    BioCortexRetrievalOptInOrderDiffPacketOptions,
    BioCortexRetrievalOptInRedactedOrderArtifactOptions,
    BioCortexRetrievalOptInReviewPacketOptions,
    BioCortexRetrievalOptInRuntimeTrialReviewPacketOptions, BioCortexShadowOptions,
};
use anyhow::Result;
use serde_json::Value;
use std::path::PathBuf;

pub(crate) async fn run_biocortex_shadow_digest(
    checkout: Option<PathBuf>,
    benchmark: String,
    timeout_ms: u64,
    include_raw: bool,
    as_json: bool,
) -> Result<()> {
    let payload = biocortex_shadow_digest(BioCortexShadowOptions {
        checkout,
        benchmark,
        timeout_ms,
        include_raw,
        fixture_projection: None,
    })
    .await;

    if as_json {
        println!("{}", serde_json::to_string_pretty(&payload)?);
        return Ok(());
    }

    println!("# BioCortex shadow digest");
    println!("schema={}", shadow_json_display(payload.get("schema"), "-"));
    println!("status={}", shadow_json_display(payload.get("status"), "-"));
    println!(
        "benchmark={} example={}",
        shadow_json_display(payload.get("benchmark"), "-"),
        shadow_json_display(payload.get("example"), "-")
    );
    if let Some(path) = payload.get("checkout_path") {
        println!("checkout={}", shadow_json_display(Some(path), "-"));
    }
    if let Some(reason) = payload.get("reason").or_else(|| payload.get("error")) {
        println!("reason={}", shadow_json_display(Some(reason), "-"));
    }

    let summary = payload.get("summary").unwrap_or(&Value::Null);
    println!(
        "verdict={} demonstrated={}",
        shadow_json_display(summary.get("verdict"), "-"),
        shadow_json_display(summary.get("demonstrated"), "false")
    );
    println!(
        "demonstrated_keys={}",
        shadow_json_display(summary.get("demonstrated_keys"), "[]")
    );
    println!(
        "failed_predicates={}",
        shadow_json_display(summary.get("failed_predicates"), "[]")
    );
    println!(
        "open_limitations={}",
        shadow_json_display(summary.get("open_limitations"), "[]")
    );
    println!("supported_benchmarks={}", supported_benchmarks().join(","));

    let boundary = payload.get("boundary").unwrap_or(&Value::Null);
    println!(
        "boundary=shadow_only links_runtime={} mutates_ab_memory={} mutates_retrieval={}",
        shadow_json_display(boundary.get("links_biocortex_into_ab_runtime"), "false"),
        shadow_json_display(boundary.get("mutates_ab_memory"), "false"),
        shadow_json_display(boundary.get("changes_retrieval_vector"), "false")
    );
    Ok(())
}

pub(crate) async fn run_biocortex_capability_ledger_report_packet(
    ledger: &std::path::Path,
    as_json: bool,
) -> Result<()> {
    let ledger_body = std::fs::read_to_string(ledger)
        .map_err(|e| anyhow::anyhow!("read BioCortex capability ledger at {ledger:?}: {e}"))?;
    let summary = consume_biocortex_capability_ledger(&ledger_body);
    let packet = build_biocortex_capability_ledger_report_packet(&summary);

    if as_json {
        println!("{}", serde_json::to_string_pretty(&packet)?);
        return Ok(());
    }

    println!("# BioCortex capability ledger report packet");
    println!("schema={}", packet.schema);
    println!("input_schema={}", packet.input_schema);
    println!(
        "input_schema_version={}",
        packet.input_schema_version.as_deref().unwrap_or("-")
    );
    println!("verdict={}", packet.verdict);
    println!("read_only_confirmed={}", packet.read_only_confirmed);
    println!("downstream_action={}", packet.downstream_action);
    println!("integration_decision={}", packet.integration_decision);
    println!(
        "static_artifact_only={} memory_write_attempted={} retrieval_order_change_attempted={} runtime_authority_observed={}",
        packet.safety.static_artifact_only,
        packet.safety.memory_write_attempted,
        packet.safety.retrieval_order_change_attempted,
        packet.safety.runtime_authority_observed
    );
    println!(
        "executor_enablement_observed={} mcp_tool_registration={} language_generation_observed={} cognition_claim_observed={}",
        packet.safety.executor_enablement_observed,
        packet.safety.mcp_tool_registration,
        packet.safety.language_generation_observed,
        packet.safety.cognition_claim_observed
    );
    Ok(())
}

pub(crate) async fn run_biocortex_retrieval_approval_packet(
    opts: BioCortexRetrievalApprovalPacketOptions,
    as_json: bool,
) -> Result<()> {
    let payload = biocortex_retrieval_runtime_approval_packet_preview(opts);
    if as_json {
        println!("{}", serde_json::to_string_pretty(&payload)?);
        return Ok(());
    }

    println!("# BioCortex retrieval runtime approval packet preview");
    println!("schema={}", shadow_json_display(payload.get("schema"), "-"));
    println!(
        "approval_state={} default_decision={}",
        shadow_json_display(payload.get("approval_state"), "-"),
        shadow_json_display(payload.get("default_decision"), "-")
    );
    println!(
        "runtime_adapter_approved={} approval_writes_allowed={} default_search_order_change_allowed={}",
        shadow_json_display(payload.get("runtime_adapter_approved"), "false"),
        shadow_json_display(payload.get("approval_writes_allowed"), "false"),
        shadow_json_display(payload.get("default_search_order_change_allowed"), "false")
    );
    println!(
        "requires_separate_human_approval={} ready_for_human_approval_review={}",
        shadow_json_display(payload.get("requires_separate_human_approval"), "true"),
        shadow_json_display(payload.get("ready_for_human_approval_review"), "false")
    );
    let attestation = payload
        .get("agent_technical_attestation")
        .unwrap_or(&Value::Null);
    let authorization = payload.get("human_authorization").unwrap_or(&Value::Null);
    println!(
        "agent_attestation_decision={} agent_can_authorize_runtime_influence={}",
        shadow_json_display(attestation.get("decision"), "-"),
        shadow_json_display(attestation.get("can_authorize_runtime_influence"), "false")
    );
    println!(
        "human_authorization_status={} human_authorization_scope={}",
        shadow_json_display(authorization.get("status"), "not_authorized"),
        shadow_json_display(authorization.get("scope"), "-")
    );
    let gates = payload.get("gates").unwrap_or(&Value::Null);
    println!(
        "gates feature_enabled={} runtime_enabled={} operator_disabled={}",
        shadow_json_display(gates.get("compile_feature_enabled"), "false"),
        shadow_json_display(gates.get("runtime_enabled"), "false"),
        shadow_json_display(gates.get("operator_disabled"), "false")
    );
    let missing_count = payload
        .get("missing_evidence")
        .and_then(Value::as_array)
        .map(Vec::len)
        .unwrap_or(0);
    println!("missing_evidence_count={missing_count}");
    if let Some(paths) = payload.get("missing_evidence").and_then(Value::as_array) {
        for path in paths.iter().take(8).filter_map(Value::as_str) {
            println!("missing={path}");
        }
        if paths.len() > 8 {
            println!("missing=...{} more", paths.len() - 8);
        }
    }
    Ok(())
}

pub(crate) async fn run_biocortex_retrieval_opt_in_status(
    opts: BioCortexRetrievalOptInAuditOptions,
    as_json: bool,
) -> Result<()> {
    let payload = biocortex_retrieval_opt_in_audit_report(opts);
    if as_json {
        println!("{}", serde_json::to_string_pretty(&payload)?);
        return Ok(());
    }

    println!("# BioCortex retrieval opt-in status");
    println!("schema={}", shadow_json_display(payload.get("schema"), "-"));
    println!(
        "mode={} mode_authorized={} implementation_stage={}",
        shadow_json_display(payload.get("mode"), "-"),
        shadow_json_display(payload.get("mode_authorized"), "false"),
        shadow_json_display(payload.get("implementation_stage"), "-")
    );
    let gate = payload.get("gate").unwrap_or(&Value::Null);
    println!(
        "gate_status={} gate_ready={} per_call_opt_in={}",
        shadow_json_display(gate.get("status"), "-"),
        shadow_json_display(gate.get("ready_for_explicit_opt_in_experiment"), "false"),
        shadow_json_display(
            payload
                .get("per_call_opt_in")
                .and_then(|value| value.get("present")),
            "false"
        )
    );
    println!(
        "runtime_enabled={} operator_disabled={}",
        shadow_json_display(gate.get("runtime_enabled"), "false"),
        shadow_json_display(gate.get("operator_disabled"), "false")
    );
    let baseline = payload.get("baseline_order").unwrap_or(&Value::Null);
    println!(
        "baseline_key_count={} baseline_hash={} raw_keys_included={} content_included={}",
        shadow_json_display(baseline.get("key_count"), "0"),
        shadow_json_display(baseline.get("hash"), "-"),
        shadow_json_display(baseline.get("raw_keys_included"), "false"),
        shadow_json_display(baseline.get("content_included"), "false")
    );
    let fallback = payload.get("fallback").unwrap_or(&Value::Null);
    println!(
        "returned_order={} fallback_reason={}",
        shadow_json_display(
            payload
                .get("returned_order")
                .and_then(|value| value.get("source")),
            "baseline"
        ),
        shadow_json_display(fallback.get("reason"), "-")
    );
    println!(
        "ordering_behavior_connected={} may_change_search_order_now={} changes_memory_search_order={}",
        shadow_json_display(payload.get("ordering_behavior_connected"), "false"),
        shadow_json_display(payload.get("may_change_search_order_now"), "false"),
        shadow_json_display(payload.get("changes_memory_search_order"), "false")
    );
    let controlled = payload
        .get("controlled_trial_readiness")
        .unwrap_or(&Value::Null);
    println!(
        "controlled_trial_status={} ready={} evidence_provided={} blockers={}",
        shadow_json_display(controlled.get("status"), "-"),
        shadow_json_display(controlled.get("ready_for_controlled_trial"), "false"),
        shadow_json_display(controlled.get("evidence_provided"), "false"),
        controlled
            .get("blockers")
            .and_then(Value::as_array)
            .map(|items| items.len().to_string())
            .unwrap_or_else(|| "0".to_string())
    );
    Ok(())
}

pub(crate) async fn run_biocortex_retrieval_opt_in_dry_run(
    opts: BioCortexRetrievalOptInDryRunOptions,
    as_json: bool,
) -> Result<()> {
    let payload = biocortex_retrieval_opt_in_dry_run_plan(opts);
    if as_json {
        println!("{}", serde_json::to_string_pretty(&payload)?);
        return Ok(());
    }

    println!("# BioCortex retrieval opt-in dry run");
    println!("schema={}", shadow_json_display(payload.get("schema"), "-"));
    println!(
        "mode={} mode_authorized={} dry_run={} implementation_stage={}",
        shadow_json_display(payload.get("mode"), "-"),
        shadow_json_display(payload.get("mode_authorized"), "false"),
        shadow_json_display(payload.get("dry_run"), "true"),
        shadow_json_display(payload.get("implementation_stage"), "-")
    );
    let baseline = payload.get("baseline_order").unwrap_or(&Value::Null);
    println!(
        "baseline_completed={} baseline_key_count={} baseline_hash={} raw_keys_included={} content_included={}",
        shadow_json_display(baseline.get("completed"), "false"),
        shadow_json_display(baseline.get("key_count"), "0"),
        shadow_json_display(baseline.get("hash"), "-"),
        shadow_json_display(baseline.get("raw_keys_included"), "false"),
        shadow_json_display(baseline.get("content_included"), "false")
    );
    let planner = payload.get("planner_result").unwrap_or(&Value::Null);
    println!(
        "returned_order={} fallback_reason={} execution_ready={}",
        shadow_json_display(planner.get("returned_order_source"), "baseline"),
        shadow_json_display(planner.get("fallback_reason"), "-"),
        shadow_json_display(planner.get("execution_ready"), "false")
    );
    let side_signal = payload.get("planned_side_signal").unwrap_or(&Value::Null);
    println!(
        "side_signal_status={} timeout_ms={} coverage_threshold={} runs_biocortex={}",
        shadow_json_display(side_signal.get("status"), "-"),
        shadow_json_display(side_signal.get("timeout_ms"), "-"),
        shadow_json_display(side_signal.get("coverage_threshold"), "-"),
        shadow_json_display(payload.get("runs_biocortex"), "false")
    );
    println!(
        "calls_memory_search={} ordering_behavior_connected={} changes_memory_search_order={}",
        shadow_json_display(payload.get("calls_memory_search"), "false"),
        shadow_json_display(payload.get("ordering_behavior_connected"), "false"),
        shadow_json_display(payload.get("changes_memory_search_order"), "false")
    );
    Ok(())
}

pub(crate) async fn run_biocortex_retrieval_opt_in_review_packet(
    opts: BioCortexRetrievalOptInReviewPacketOptions,
    as_json: bool,
) -> Result<()> {
    let payload = biocortex_retrieval_opt_in_review_packet(opts);
    if as_json {
        println!("{}", serde_json::to_string_pretty(&payload)?);
        return Ok(());
    }

    println!("# BioCortex retrieval opt-in review packet");
    println!("schema={}", shadow_json_display(payload.get("schema"), "-"));
    println!(
        "review_ready={} approval_state={} may_implement_ordering_now={}",
        shadow_json_display(
            payload
                .get("boundary_check")
                .and_then(|value| value.get("review_ready")),
            "false"
        ),
        shadow_json_display(payload.get("approval_state"), "not_approved"),
        shadow_json_display(payload.get("may_implement_ordering_now"), "false")
    );
    let target = payload.get("review_target").unwrap_or(&Value::Null);
    println!(
        "mode={} mode_authorized={} commit={}",
        shadow_json_display(target.get("mode"), "-"),
        shadow_json_display(target.get("mode_authorized"), "false"),
        shadow_json_display(target.get("commit"), "-")
    );
    let summary = payload.get("dry_run_summary").unwrap_or(&Value::Null);
    let baseline = summary.get("baseline_order").unwrap_or(&Value::Null);
    let planner = summary.get("planner_result").unwrap_or(&Value::Null);
    println!(
        "baseline_key_count={} baseline_hash={} returned_order={} fallback_reason={}",
        shadow_json_display(baseline.get("key_count"), "0"),
        shadow_json_display(baseline.get("hash"), "-"),
        shadow_json_display(planner.get("returned_order_source"), "baseline"),
        shadow_json_display(planner.get("fallback_reason"), "-")
    );
    let boundary = payload.get("boundary_check").unwrap_or(&Value::Null);
    println!(
        "violations={}",
        boundary
            .get("violations")
            .and_then(Value::as_array)
            .map(|items| items.len().to_string())
            .unwrap_or_else(|| "0".to_string())
    );
    println!(
        "calls_memory_search={} runs_biocortex={} changes_memory_search_order={}",
        shadow_json_display(payload.get("calls_memory_search"), "false"),
        shadow_json_display(payload.get("runs_biocortex"), "false"),
        shadow_json_display(payload.get("changes_memory_search_order"), "false")
    );
    Ok(())
}

pub(crate) async fn run_biocortex_retrieval_opt_in_execution_packet(
    opts: BioCortexRetrievalOptInExecutionPacketOptions,
    as_json: bool,
) -> Result<()> {
    let payload = biocortex_retrieval_opt_in_execution_packet(opts);
    if as_json {
        println!("{}", serde_json::to_string_pretty(&payload)?);
        return Ok(());
    }

    println!("# BioCortex retrieval opt-in execution packet");
    println!("schema={}", shadow_json_display(payload.get("schema"), "-"));
    println!(
        "execution_allowed={} approval_state={} may_change_search_order_now={}",
        shadow_json_display(
            payload
                .get("preflight")
                .and_then(|value| value.get("execution_allowed")),
            "false"
        ),
        shadow_json_display(payload.get("approval_state"), "not_approved"),
        shadow_json_display(payload.get("may_change_search_order_now"), "false")
    );
    let attempt = payload.get("attempt").unwrap_or(&Value::Null);
    println!(
        "attempt_id={} mode={} per_call_opt_in={}",
        shadow_json_display(attempt.get("attempt_id"), "-"),
        shadow_json_display(attempt.get("mode"), "-"),
        shadow_json_display(attempt.get("per_call_opt_in"), "false")
    );
    let preflight = payload.get("preflight").unwrap_or(&Value::Null);
    println!(
        "baseline_preflight={} fallback_reason={} packet_blockers={} store_blockers={}",
        shadow_json_display(
            preflight.get("preflight_passed_for_baseline_only_contract"),
            "false"
        ),
        shadow_json_display(preflight.get("fallback_reason"), "-"),
        preflight
            .get("packet_blockers")
            .and_then(Value::as_array)
            .map(|items| items.len().to_string())
            .unwrap_or_else(|| "0".to_string()),
        preflight
            .get("store_blockers")
            .and_then(Value::as_array)
            .map(|items| items.len().to_string())
            .unwrap_or_else(|| "0".to_string())
    );
    let execution = payload.get("execution_decision").unwrap_or(&Value::Null);
    println!(
        "returned_order={} baseline_returned={} calls_memory_search={} runs_biocortex={}",
        shadow_json_display(execution.get("returned_order_source"), "baseline"),
        shadow_json_display(execution.get("baseline_returned"), "true"),
        shadow_json_display(execution.get("calls_memory_search_now"), "false"),
        shadow_json_display(execution.get("runs_biocortex_now"), "false")
    );
    Ok(())
}

pub(crate) async fn run_biocortex_retrieval_opt_in_runtime_trial_review_packet(
    opts: BioCortexRetrievalOptInRuntimeTrialReviewPacketOptions,
    as_json: bool,
) -> Result<()> {
    let payload = biocortex_retrieval_opt_in_runtime_trial_review_packet(opts);
    if as_json {
        println!("{}", serde_json::to_string_pretty(&payload)?);
        return Ok(());
    }

    println!("# BioCortex retrieval opt-in runtime trial review packet");
    println!("schema={}", shadow_json_display(payload.get("schema"), "-"));
    let boundary = payload.get("boundary_check").unwrap_or(&Value::Null);
    println!(
        "review_ready={} approval_state={} may_implement_ordering_now={}",
        shadow_json_display(
            boundary.get("review_ready_for_baseline_runtime_trial"),
            "false"
        ),
        shadow_json_display(payload.get("approval_state"), "not_approved"),
        shadow_json_display(payload.get("may_implement_ordering_now"), "false")
    );
    let target = payload.get("review_target").unwrap_or(&Value::Null);
    println!(
        "mode={} per_call_opt_in={} commit={}",
        shadow_json_display(target.get("mode"), "-"),
        shadow_json_display(target.get("per_call_opt_in"), "false"),
        shadow_json_display(target.get("commit"), "-")
    );
    let summary = payload.get("runtime_trial_summary").unwrap_or(&Value::Null);
    let side_signal = summary.get("side_signal").unwrap_or(&Value::Null);
    println!(
        "side_signal_status={} attempted={} coverage={} latency_ms={}",
        shadow_json_display(side_signal.get("status"), "-"),
        shadow_json_display(side_signal.get("attempted"), "false"),
        shadow_json_display(side_signal.get("coverage"), "0"),
        shadow_json_display(side_signal.get("latency_ms"), "0")
    );
    let returned = summary.get("returned_order").unwrap_or(&Value::Null);
    println!(
        "returned_order={} baseline_returned={} violations={}",
        shadow_json_display(returned.get("source"), "baseline"),
        shadow_json_display(returned.get("baseline_returned"), "true"),
        boundary
            .get("violations")
            .and_then(Value::as_array)
            .map(|items| items.len().to_string())
            .unwrap_or_else(|| "0".to_string())
    );
    println!(
        "calls_memory_search={} runs_biocortex={} changes_memory_search_order={}",
        shadow_json_display(payload.get("calls_memory_search"), "false"),
        shadow_json_display(payload.get("runs_biocortex"), "false"),
        shadow_json_display(payload.get("changes_memory_search_order"), "false")
    );
    Ok(())
}

pub(crate) async fn run_biocortex_retrieval_opt_in_order_diff_packet(
    opts: BioCortexRetrievalOptInOrderDiffPacketOptions,
    as_json: bool,
) -> Result<()> {
    let payload = biocortex_retrieval_opt_in_order_diff_packet(opts);
    if as_json {
        println!("{}", serde_json::to_string_pretty(&payload)?);
        return Ok(());
    }

    println!("# BioCortex retrieval opt-in order diff packet");
    println!("schema={}", shadow_json_display(payload.get("schema"), "-"));
    let boundary = payload.get("boundary_check").unwrap_or(&Value::Null);
    println!(
        "diff_ready={} approval_state={} may_implement_ordering_now={}",
        shadow_json_display(boundary.get("diff_ready"), "false"),
        shadow_json_display(payload.get("approval_state"), "not_approved"),
        shadow_json_display(payload.get("may_implement_ordering_now"), "false")
    );
    let comparison = payload.get("order_comparison").unwrap_or(&Value::Null);
    let hash_diff = comparison.get("hash_diff").unwrap_or(&Value::Null);
    println!(
        "order_hash_changed={} top_key_changed={} order_hashes_comparable={}",
        shadow_json_display(hash_diff.get("order_hash_changed"), "-"),
        shadow_json_display(hash_diff.get("top_key_changed"), "-"),
        shadow_json_display(hash_diff.get("order_hashes_comparable"), "false")
    );
    let expected = comparison.get("expected_key_rank").unwrap_or(&Value::Null);
    println!(
        "expected_rank_delta={} direction={} regressed={}",
        shadow_json_display(expected.get("rank_delta_advisory_minus_baseline"), "-"),
        shadow_json_display(expected.get("direction"), "unknown"),
        shadow_json_display(expected.get("regressed"), "false")
    );
    let returned = comparison.get("returned_order").unwrap_or(&Value::Null);
    println!(
        "returned_order={} actual_return_order_changed={} violations={}",
        shadow_json_display(returned.get("source"), "baseline"),
        shadow_json_display(returned.get("actual_return_order_changed"), "false"),
        boundary
            .get("violations")
            .and_then(Value::as_array)
            .map(|items| items.len().to_string())
            .unwrap_or_else(|| "0".to_string())
    );
    println!(
        "calls_memory_search={} runs_biocortex={} changes_memory_search_order={}",
        shadow_json_display(payload.get("calls_memory_search"), "false"),
        shadow_json_display(payload.get("runs_biocortex"), "false"),
        shadow_json_display(payload.get("changes_memory_search_order"), "false")
    );
    Ok(())
}

pub(crate) async fn run_biocortex_retrieval_opt_in_redacted_order_artifact(
    opts: BioCortexRetrievalOptInRedactedOrderArtifactOptions,
    as_json: bool,
) -> Result<()> {
    let payload = biocortex_retrieval_opt_in_redacted_order_artifact(opts);
    if as_json {
        println!("{}", serde_json::to_string_pretty(&payload)?);
        return Ok(());
    }

    println!("# BioCortex retrieval opt-in redacted order artifact");
    println!("schema={}", shadow_json_display(payload.get("schema"), "-"));
    let boundary = payload.get("boundary_check").unwrap_or(&Value::Null);
    println!(
        "artifact_ready={} approval_state={} may_implement_ordering_now={}",
        shadow_json_display(boundary.get("artifact_ready"), "false"),
        shadow_json_display(payload.get("approval_state"), "not_approved"),
        shadow_json_display(payload.get("may_implement_ordering_now"), "false")
    );
    let comparison = payload
        .get("redacted_order_comparison")
        .unwrap_or(&Value::Null);
    let distribution = comparison
        .get("rank_delta_distribution")
        .unwrap_or(&Value::Null);
    println!(
        "improved={} regressed={} unchanged={} max_abs_delta={}",
        shadow_json_display(distribution.get("improved_count"), "0"),
        shadow_json_display(distribution.get("regressed_count"), "0"),
        shadow_json_display(distribution.get("unchanged_count"), "0"),
        shadow_json_display(distribution.get("max_abs_delta"), "0")
    );
    let overlap_k1 = comparison
        .get("top_k_overlap")
        .and_then(Value::as_array)
        .and_then(|rows| {
            rows.iter()
                .find(|row| row.get("k").and_then(Value::as_u64) == Some(1))
        })
        .unwrap_or(&Value::Null);
    println!(
        "top1_overlap={} top1_jaccard={} redacted_rows_comparable={} violations={}",
        shadow_json_display(overlap_k1.get("overlap_count"), "0"),
        shadow_json_display(overlap_k1.get("jaccard"), "-"),
        shadow_json_display(boundary.get("redacted_rows_comparable"), "false"),
        boundary
            .get("violations")
            .and_then(Value::as_array)
            .map(|items| items.len().to_string())
            .unwrap_or_else(|| "0".to_string())
    );
    println!(
        "calls_memory_search={} runs_biocortex={} changes_memory_search_order={}",
        shadow_json_display(payload.get("calls_memory_search"), "false"),
        shadow_json_display(payload.get("runs_biocortex"), "false"),
        shadow_json_display(payload.get("changes_memory_search_order"), "false")
    );
    Ok(())
}

pub(crate) async fn run_biocortex_retrieval_opt_in_authorization_decision_packet(
    opts: BioCortexRetrievalOptInAuthorizationDecisionPacketOptions,
    as_json: bool,
) -> Result<()> {
    let payload = biocortex_retrieval_opt_in_authorization_decision_packet(opts);
    if as_json {
        println!("{}", serde_json::to_string_pretty(&payload)?);
        return Ok(());
    }

    println!("# BioCortex retrieval opt-in authorization decision packet");
    println!("schema={}", shadow_json_display(payload.get("schema"), "-"));
    let boundary = payload.get("boundary_check").unwrap_or(&Value::Null);
    println!(
        "implementation_authorized={} approval_state={} authorization_state={}",
        shadow_json_display(boundary.get("implementation_authorized"), "false"),
        shadow_json_display(payload.get("approval_state"), "not_approved"),
        shadow_json_display(payload.get("authorization_state"), "not_authorized")
    );
    println!(
        "runtime_adapter_approved={} default_search_order_change_allowed={} may_implement_ordering_now={}",
        shadow_json_display(payload.get("runtime_adapter_approved"), "false"),
        shadow_json_display(payload.get("default_search_order_change_allowed"), "false"),
        shadow_json_display(payload.get("may_implement_ordering_now"), "false")
    );
    let authorized = payload
        .get("authorized_implementation")
        .unwrap_or(&Value::Null);
    println!(
        "fts_only={} per_call_surface={} post_review_required={}",
        shadow_json_display(
            authorized.get("may_affect_only_explicitly_opted_in_fts_calls"),
            "false"
        ),
        shadow_json_display(authorized.get("may_add_per_call_opt_in_surface"), "false"),
        shadow_json_display(
            authorized.get("requires_post_implementation_review_before_use"),
            "true"
        )
    );
    println!(
        "blockers={} calls_memory_search={} runs_biocortex={} changes_memory_search_order={}",
        boundary
            .get("blockers")
            .and_then(Value::as_array)
            .map(|items| items.len().to_string())
            .unwrap_or_else(|| "0".to_string()),
        shadow_json_display(payload.get("calls_memory_search"), "false"),
        shadow_json_display(payload.get("runs_biocortex"), "false"),
        shadow_json_display(payload.get("changes_memory_search_order"), "false")
    );
    Ok(())
}

pub(crate) fn shadow_json_display(value: Option<&Value>, default: &str) -> String {
    match value {
        Some(Value::String(s)) => s.clone(),
        Some(Value::Bool(b)) => b.to_string(),
        Some(Value::Number(n)) => n.to_string(),
        Some(Value::Array(items)) => {
            if items.is_empty() {
                "[]".to_string()
            } else {
                items
                    .iter()
                    .map(|v| shadow_json_display(Some(v), "null"))
                    .collect::<Vec<_>>()
                    .join(",")
            }
        }
        Some(Value::Null) | None => default.to_string(),
        Some(other) => other.to_string(),
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::json;

    #[test]
    fn shadow_json_display_preserves_scalar_rendering() {
        assert_eq!(
            shadow_json_display(Some(&Value::String("ready".into())), "-"),
            "ready"
        );
        assert_eq!(shadow_json_display(Some(&json!(true)), "-"), "true");
        assert_eq!(shadow_json_display(Some(&json!(42)), "-"), "42");
    }

    #[test]
    fn shadow_json_display_flattens_arrays_and_uses_defaults() {
        assert_eq!(
            shadow_json_display(Some(&json!(["a", 2, false])), "-"),
            "a,2,false"
        );
        assert_eq!(shadow_json_display(Some(&json!([])), "-"), "[]");
        assert_eq!(shadow_json_display(Some(&Value::Null), "-"), "-");
        assert_eq!(shadow_json_display(None, "missing"), "missing");
    }
}
