use ab_bridge::gos_lite::{
    build_gos_lite_replay_report, build_gos_lite_snapshot_from_tool_atlas,
    project_gos_lite_snapshot, GosLiteViewOptions,
};
use ab_bridge::tool_atlas::{
    build_tool_atlas_snapshot, ToolAtlasFailureSample, ToolAtlasInput, ToolAtlasSnapshot,
};
use ab_store::{McpToolCallRow, McpToolCallStats, McpToolErrorRecord};

fn stat(name: &str, calls: u64, errors: u64, p95: u32, avg_result_size: f64) -> McpToolCallStats {
    McpToolCallStats {
        tool_name: name.to_string(),
        call_count: calls,
        error_count: errors,
        avg_duration_ms: f64::from(p95) / 2.0,
        p95_duration_ms: p95,
        max_duration_ms: p95,
        avg_result_size,
        client_name: None,
        profile: None,
        source: Some("codex".to_string()),
        model: None,
        model_reasoning_effort: None,
        codex_host: None,
    }
}

fn call(ts: i64, tool_name: &str, ok: bool, duration_ms: u32, result_size: u32) -> McpToolCallRow {
    McpToolCallRow {
        id: ts,
        ts,
        tool_name: tool_name.to_string(),
        source: None,
        mcp_session_id: None,
        duration_ms,
        ok,
        args_size: Some(4),
        result_size: Some(result_size),
    }
}

fn atlas_with_failure_and_latency() -> ToolAtlasSnapshot {
    build_tool_atlas_snapshot(ToolAtlasInput {
        generated_at: 1_781_450_000,
        window_secs: 86_400,
        current_tools: vec!["browser_click".to_string(), "memory_save".to_string()],
        stats: vec![
            stat("browser_click", 4, 3, 32, 191.0),
            stat("memory_save", 20, 0, 2_586, 561.0),
        ],
        recent_errors: vec![McpToolErrorRecord {
            ts: 1_781_448_517,
            tool_name: "browser_click".to_string(),
            message: "browser: invalid argument: ref @e2 element is disabled".to_string(),
        }],
    })
}

#[test]
fn gos_lite_projects_tool_failures_into_grounded_belief_graph() {
    let atlas = atlas_with_failure_and_latency();

    let snapshot = build_gos_lite_snapshot_from_tool_atlas(&atlas);

    assert_eq!(snapshot.schema_version, 1);
    assert_eq!(snapshot.status, "needs_investigation");
    assert_eq!(snapshot.next_action, "investigate_failure");
    assert_eq!(snapshot.summary.failing_tools, 1);
    assert_eq!(snapshot.summary.degraded_tools, 1);

    let failure_hypothesis = snapshot
        .nodes
        .iter()
        .find(|node| node.id == "hypothesis:tool:browser_click:failure_mode")
        .expect("browser_click failure hypothesis");
    assert_eq!(failure_hypothesis.node_type, "Hypothesis");

    let grounded_evidence = snapshot
        .nodes
        .iter()
        .find(|node| node.node_type == "Evidence" && node.label.contains("disabled"))
        .expect("failure sample evidence");
    assert_eq!(
        grounded_evidence.attrs["provenance_source"],
        "tool_atlas.failure_samples"
    );

    assert!(snapshot.edges.iter().any(|edge| {
        edge.src == grounded_evidence.id
            && edge.dst == failure_hypothesis.id
            && edge.edge_type == "support"
    }));
}

#[test]
fn gos_lite_uses_risk_flags_as_degradation_evidence_without_fabricating_failures() {
    let atlas = atlas_with_failure_and_latency();

    let snapshot = build_gos_lite_snapshot_from_tool_atlas(&atlas);

    let latency_hypothesis = snapshot
        .nodes
        .iter()
        .find(|node| node.id == "hypothesis:tool:memory_save:latency_or_size_degradation")
        .expect("memory_save degradation hypothesis");

    let latency_evidence = snapshot
        .nodes
        .iter()
        .find(|node| node.node_type == "Evidence" && node.label.contains("p95 latency"))
        .expect("latency evidence");
    assert_eq!(
        latency_evidence.attrs["provenance_source"],
        "tool_atlas.risk_flags"
    );

    assert!(snapshot.edges.iter().any(|edge| {
        edge.src == latency_evidence.id
            && edge.dst == latency_hypothesis.id
            && edge.edge_type == "support"
    }));

    let fabricated_memory_failures: Vec<&ToolAtlasFailureSample> = atlas
        .tools
        .iter()
        .find(|tool| tool.tool_name == "memory_save")
        .expect("memory_save")
        .failure_samples
        .iter()
        .collect();
    assert!(fabricated_memory_failures.is_empty());
}

#[test]
fn gos_lite_projection_includes_forum_backed_human_gate_packet() {
    let atlas = atlas_with_failure_and_latency();
    let snapshot = build_gos_lite_snapshot_from_tool_atlas(&atlas);

    let payload = project_gos_lite_snapshot(&snapshot, GosLiteViewOptions::default());

    assert_eq!(payload["human_gate"]["required"], true);
    assert_eq!(payload["human_gate"]["forum"]["board"], "design");
    assert_eq!(payload["human_gate"]["forum"]["kind"], "finding");
    assert_eq!(payload["human_gate"]["promotion_allowed"], false);
    assert!(payload["human_gate"]["promotion_policy"]
        .as_str()
        .expect("promotion policy")
        .contains("Human reviewer"));
    assert!(payload["human_gate"]["review_questions"]
        .as_array()
        .expect("review questions")
        .iter()
        .any(|q| q.as_str().unwrap_or("").contains("support")));
}

#[test]
fn gos_lite_projects_large_average_result_as_size_degradation_evidence() {
    let atlas = build_tool_atlas_snapshot(ToolAtlasInput {
        generated_at: 1_781_450_000,
        window_secs: 86_400,
        current_tools: vec!["tool_atlas_snapshot".to_string()],
        stats: vec![stat("tool_atlas_snapshot", 4, 0, 38, 28_826.0)],
        recent_errors: Vec::new(),
    });

    let snapshot = build_gos_lite_snapshot_from_tool_atlas(&atlas);

    assert_eq!(snapshot.status, "needs_optimization");
    assert_eq!(snapshot.summary.degraded_tools, 1);

    let size_evidence = snapshot
        .nodes
        .iter()
        .find(|node| {
            node.node_type == "Evidence"
                && node.attrs["risk_flag"].as_str() == Some("large_average_result")
        })
        .expect("large_average_result evidence");
    assert_eq!(
        size_evidence.attrs["provenance_source"],
        "tool_atlas.risk_flags"
    );

    assert!(snapshot.edges.iter().any(|edge| {
        edge.src == size_evidence.id
            && edge.dst == "hypothesis:tool:tool_atlas_snapshot:latency_or_size_degradation"
            && edge.edge_type == "support"
    }));
}

#[test]
fn gos_lite_replay_report_links_hypotheses_to_event_spine_support() {
    let atlas = atlas_with_failure_and_latency();
    let snapshot = build_gos_lite_snapshot_from_tool_atlas(&atlas);
    let spine = ab_bridge::event_spine::mcp_event_spine_snapshot(
        &[
            call(1_781_448_518, "browser_click", false, 32, 191),
            call(1_781_448_519, "memory_save", true, 2_586, 561),
        ],
        &[McpToolErrorRecord {
            ts: 1_781_448_517,
            tool_name: "browser_click".to_string(),
            message: "browser: invalid argument: ref @e2 element is disabled".to_string(),
        }],
        &[],
        &[],
        86_400,
        50,
        1_781_450_000,
    );

    let report = build_gos_lite_replay_report(&snapshot, &spine);

    assert_eq!(report.schema_version, 1);
    assert!(report.event_chain_verified);
    let failure_check = report
        .checks
        .iter()
        .find(|check| check.hypothesis_id == "hypothesis:tool:browser_click:failure_mode")
        .expect("browser_click check");
    assert_eq!(failure_check.verdict, "supported");
    assert_eq!(failure_check.tool_name, "browser_click");
    assert!(failure_check.supporting_event_ids.len() >= 2);
    assert!(failure_check
        .supporting_sources
        .iter()
        .any(|source| source == "mcp_tool_errors"));
}

#[test]
fn gos_lite_replay_report_flags_missing_support_as_falsifier_candidate() {
    let atlas = atlas_with_failure_and_latency();
    let snapshot = build_gos_lite_snapshot_from_tool_atlas(&atlas);
    let spine = ab_bridge::event_spine::mcp_event_spine_snapshot(
        &[call(1_781_448_518, "browser_click", true, 32, 191)],
        &[],
        &[],
        &[],
        86_400,
        50,
        1_781_450_000,
    );

    let report = build_gos_lite_replay_report(&snapshot, &spine);

    let failure_check = report
        .checks
        .iter()
        .find(|check| check.hypothesis_id == "hypothesis:tool:browser_click:failure_mode")
        .expect("browser_click check");
    assert_eq!(failure_check.verdict, "falsifier_candidate");
    assert_eq!(failure_check.review_action, "replay_or_refute");
    assert_eq!(failure_check.refuting_event_ids.len(), 1);
    assert!(failure_check
        .notes
        .iter()
        .any(|note| note.contains("no event-level failure support")));
}

#[test]
fn gos_lite_replay_report_supports_large_average_result_risk_flag() {
    let atlas = build_tool_atlas_snapshot(ToolAtlasInput {
        generated_at: 1_781_450_000,
        window_secs: 86_400,
        current_tools: vec!["tool_atlas_snapshot".to_string()],
        stats: vec![stat("tool_atlas_snapshot", 4, 0, 38, 28_826.0)],
        recent_errors: Vec::new(),
    });
    let snapshot = build_gos_lite_snapshot_from_tool_atlas(&atlas);
    let spine = ab_bridge::event_spine::mcp_event_spine_snapshot(
        &[call(1_781_448_518, "tool_atlas_snapshot", true, 38, 28_826)],
        &[],
        &[],
        &[],
        86_400,
        50,
        1_781_450_000,
    );

    let report = build_gos_lite_replay_report(&snapshot, &spine);

    let payload_check = report
        .checks
        .iter()
        .find(|check| {
            check.hypothesis_id == "hypothesis:tool:tool_atlas_snapshot:latency_or_size_degradation"
        })
        .expect("tool_atlas_snapshot degradation check");
    assert_eq!(payload_check.verdict, "supported");
    assert_eq!(payload_check.review_action, "review_support");
    assert_eq!(payload_check.supporting_event_ids.len(), 1);
    assert!(payload_check.refuting_event_ids.is_empty());
}
