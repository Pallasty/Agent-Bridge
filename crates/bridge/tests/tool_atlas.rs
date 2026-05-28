use ab_bridge::tool_atlas::{
    build_tool_atlas_snapshot, project_tool_atlas_snapshot, ToolAtlasInput, ToolAtlasViewOptions,
};
use ab_store::{McpToolCallStats, McpToolErrorRecord};

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

#[test]
fn tool_atlas_classifies_hot_cold_and_failing_tools() {
    let snapshot = build_tool_atlas_snapshot(ToolAtlasInput {
        generated_at: 1_779_910_000,
        window_secs: 600,
        current_tools: vec![
            "memory_search".to_string(),
            "agent_spawn".to_string(),
            "event_spine_snapshot".to_string(),
        ],
        stats: vec![
            stat("memory_search", 12, 0, 80, 4_000.0),
            stat("agent_spawn", 5, 2, 1_500, 900.0),
        ],
        recent_errors: vec![McpToolErrorRecord {
            ts: 1_779_909_990,
            tool_name: "agent_spawn".to_string(),
            message: "spawn kilo: No such file or directory".to_string(),
        }],
    });

    assert_eq!(snapshot.summary.current_tool_count, 3);
    assert_eq!(snapshot.summary.observed_tool_count, 2);
    assert_eq!(snapshot.summary.failing_tool_count, 1);
    assert_eq!(snapshot.summary.cold_tool_count, 1);

    let memory = snapshot
        .tools
        .iter()
        .find(|tool| tool.tool_name == "memory_search")
        .expect("memory_search");
    assert_eq!(memory.usage_class, "hot");
    assert_eq!(memory.health, "healthy");
    assert_eq!(memory.recommendation, "keep");

    let spawn = snapshot
        .tools
        .iter()
        .find(|tool| tool.tool_name == "agent_spawn")
        .expect("agent_spawn");
    assert_eq!(spawn.health, "failing");
    assert_eq!(spawn.error_rate, 0.4);
    assert_eq!(spawn.recommendation, "fix_failure_mode");
    assert_eq!(
        spawn.failure_samples[0].message,
        "spawn kilo: No such file or directory"
    );

    let event_spine = snapshot
        .tools
        .iter()
        .find(|tool| tool.tool_name == "event_spine_snapshot")
        .expect("event_spine_snapshot");
    assert_eq!(event_spine.usage_class, "cold");
    assert_eq!(event_spine.health, "unobserved");
    assert_eq!(event_spine.recommendation, "watch");
}

#[test]
fn tool_atlas_projection_limits_rows_and_reports_omissions() {
    let snapshot = build_tool_atlas_snapshot(ToolAtlasInput {
        generated_at: 1_779_910_000,
        window_secs: 600,
        current_tools: vec![
            "memory_search".to_string(),
            "agent_spawn".to_string(),
            "event_spine_snapshot".to_string(),
        ],
        stats: vec![
            stat("memory_search", 12, 0, 80, 4_000.0),
            stat("agent_spawn", 5, 2, 1_500, 900.0),
        ],
        recent_errors: vec![McpToolErrorRecord {
            ts: 1_779_909_990,
            tool_name: "agent_spawn".to_string(),
            message: "spawn kilo: No such file or directory".to_string(),
        }],
    });

    let payload = project_tool_atlas_snapshot(
        &snapshot,
        ToolAtlasViewOptions {
            include_tools: true,
            limit: 1,
        },
    );

    assert_eq!(payload["tools"].as_array().expect("tools").len(), 1);
    assert_eq!(payload["tools_included"], 1);
    assert_eq!(payload["tools_omitted"], 2);
    assert_eq!(payload["tools"][0]["tool_name"], "agent_spawn");
}

#[test]
fn tool_atlas_projection_can_return_summary_only() {
    let snapshot = build_tool_atlas_snapshot(ToolAtlasInput {
        generated_at: 1_779_910_000,
        window_secs: 600,
        current_tools: vec![
            "memory_search".to_string(),
            "agent_spawn".to_string(),
            "event_spine_snapshot".to_string(),
        ],
        stats: vec![stat("memory_search", 12, 0, 80, 4_000.0)],
        recent_errors: Vec::new(),
    });

    let payload = project_tool_atlas_snapshot(
        &snapshot,
        ToolAtlasViewOptions {
            include_tools: false,
            limit: 20,
        },
    );

    assert_eq!(payload["summary"]["current_tool_count"], 3);
    assert_eq!(payload["tools"].as_array().expect("tools").len(), 0);
    assert_eq!(payload["tools_included"], 0);
    assert_eq!(payload["tools_omitted"], 3);
}
