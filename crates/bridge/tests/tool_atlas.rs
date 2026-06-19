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

#[test]
fn tool_atlas_treats_agent_session_wait_latency_as_expected() {
    let snapshot = build_tool_atlas_snapshot(ToolAtlasInput {
        generated_at: 1_779_910_000,
        window_secs: 600,
        current_tools: vec!["agent_session_wait".to_string()],
        stats: vec![stat("agent_session_wait", 1, 0, 25_000, 600.0)],
        recent_errors: Vec::new(),
    });

    let wait = snapshot
        .tools
        .iter()
        .find(|tool| tool.tool_name == "agent_session_wait")
        .expect("agent_session_wait");

    assert_eq!(wait.health, "healthy");
    assert_eq!(wait.recommendation, "keep");
    assert!(wait.risk_flags.contains(&"expected_wait".to_string()));
    assert!(!wait.risk_flags.contains(&"slow_p95".to_string()));
}

#[test]
fn tool_atlas_treats_unexposed_slow_tools_as_historical() {
    let snapshot = build_tool_atlas_snapshot(ToolAtlasInput {
        generated_at: 1_779_910_000,
        window_secs: 600,
        current_tools: vec!["tool_atlas_snapshot".to_string()],
        stats: vec![stat("session_lifecycle_step", 10, 0, 2_048, 1_734.0)],
        recent_errors: Vec::new(),
    });

    let lifecycle = snapshot
        .tools
        .iter()
        .find(|tool| tool.tool_name == "session_lifecycle_step")
        .expect("session_lifecycle_step");

    assert!(!lifecycle.exposed);
    assert_eq!(lifecycle.health, "healthy");
    assert_eq!(lifecycle.recommendation, "keep");
    assert!(lifecycle
        .risk_flags
        .contains(&"historical_unexposed_latency".to_string()));
    assert!(!lifecycle.risk_flags.contains(&"slow_p95".to_string()));
}

#[test]
fn tool_atlas_treats_event_spine_explicit_events_as_expected_detail_payload() {
    let snapshot = build_tool_atlas_snapshot(ToolAtlasInput {
        generated_at: 1_779_910_000,
        window_secs: 600,
        current_tools: vec!["event_spine_snapshot".to_string()],
        stats: vec![stat("event_spine_snapshot", 1, 0, 8, 32_630.0)],
        recent_errors: Vec::new(),
    });

    let event_spine = snapshot
        .tools
        .iter()
        .find(|tool| tool.tool_name == "event_spine_snapshot")
        .expect("event_spine_snapshot");

    assert_eq!(event_spine.health, "healthy");
    assert_eq!(event_spine.recommendation, "keep");
    assert!(event_spine
        .risk_flags
        .contains(&"expected_detail_payload".to_string()));
    assert!(!event_spine
        .risk_flags
        .contains(&"large_average_result".to_string()));
}

#[test]
fn tool_atlas_treats_forum_read_long_deep_dive_as_expected_detail_payload() {
    let snapshot = build_tool_atlas_snapshot(ToolAtlasInput {
        generated_at: 1_779_910_000,
        window_secs: 600,
        current_tools: vec!["forum_read".to_string()],
        stats: vec![stat("forum_read", 3, 0, 2, 29_160.0)],
        recent_errors: Vec::new(),
    });

    let forum_read = snapshot
        .tools
        .iter()
        .find(|tool| tool.tool_name == "forum_read")
        .expect("forum_read");

    assert_eq!(forum_read.health, "healthy");
    assert_eq!(forum_read.recommendation, "keep");
    assert!(forum_read
        .risk_flags
        .contains(&"expected_detail_payload".to_string()));
    assert!(!forum_read
        .risk_flags
        .contains(&"large_average_result".to_string()));
}

#[test]
fn tool_atlas_treats_biocortex_replay_compare_as_expected_eval_payload() {
    let snapshot = build_tool_atlas_snapshot(ToolAtlasInput {
        generated_at: 1_779_910_000,
        window_secs: 600,
        current_tools: vec!["biocortex_replay_compare".to_string()],
        stats: vec![stat("biocortex_replay_compare", 4, 0, 8_104, 25_297.75)],
        recent_errors: Vec::new(),
    });

    let replay = snapshot
        .tools
        .iter()
        .find(|tool| tool.tool_name == "biocortex_replay_compare")
        .expect("biocortex_replay_compare");

    assert_eq!(replay.health, "healthy");
    assert_eq!(replay.recommendation, "keep");
    assert!(replay
        .risk_flags
        .contains(&"expected_eval_workload".to_string()));
    assert!(replay
        .risk_flags
        .contains(&"expected_detail_payload".to_string()));
    assert!(!replay.risk_flags.contains(&"slow_p95".to_string()));
    assert!(!replay
        .risk_flags
        .contains(&"large_average_result".to_string()));
}

#[test]
fn tool_atlas_treats_biocortex_relevance_lift_as_expected_eval_latency() {
    let snapshot = build_tool_atlas_snapshot(ToolAtlasInput {
        generated_at: 1_779_910_000,
        window_secs: 600,
        current_tools: vec!["biocortex_retrieval_relevance_lift_eval".to_string()],
        stats: vec![stat(
            "biocortex_retrieval_relevance_lift_eval",
            3,
            0,
            5_984,
            4_096.0,
        )],
        recent_errors: Vec::new(),
    });

    let relevance = snapshot
        .tools
        .iter()
        .find(|tool| tool.tool_name == "biocortex_retrieval_relevance_lift_eval")
        .expect("biocortex_retrieval_relevance_lift_eval");

    assert_eq!(relevance.health, "healthy");
    assert_eq!(relevance.recommendation, "keep");
    assert!(relevance
        .risk_flags
        .contains(&"expected_eval_workload".to_string()));
    assert!(!relevance.risk_flags.contains(&"slow_p95".to_string()));
}

#[test]
fn tool_atlas_treats_session_reconcile_confirmation_gate_as_expected() {
    let snapshot = build_tool_atlas_snapshot(ToolAtlasInput {
        generated_at: 1_779_910_000,
        window_secs: 600,
        current_tools: vec!["agent_session_reconcile".to_string()],
        stats: vec![stat("agent_session_reconcile", 4, 1, 40, 500.0)],
        recent_errors: vec![McpToolErrorRecord {
            ts: 1_779_909_990,
            tool_name: "agent_session_reconcile".to_string(),
            message: "dry_run=false requires apply_confirmation=\"finalise_stale_sessions\" after reviewing dry-run candidates".to_string(),
        }],
    });

    assert_eq!(snapshot.summary.failing_tool_count, 0);

    let reconcile = snapshot
        .tools
        .iter()
        .find(|tool| tool.tool_name == "agent_session_reconcile")
        .expect("agent_session_reconcile");

    assert_eq!(reconcile.error_count, 1);
    assert_eq!(reconcile.failure_samples.len(), 1);
    assert_eq!(reconcile.health, "healthy");
    assert_eq!(reconcile.recommendation, "keep");
    assert!(reconcile
        .risk_flags
        .contains(&"expected_confirmation".to_string()));
    assert!(!reconcile.risk_flags.contains(&"has_errors".to_string()));
}

#[test]
fn tool_atlas_treats_desktop_host_mutation_refusal_as_expected_safety_gate() {
    let snapshot = build_tool_atlas_snapshot(ToolAtlasInput {
        generated_at: 1_779_910_000,
        window_secs: 600,
        current_tools: vec!["desktop_action".to_string()],
        stats: vec![stat("desktop_action", 2, 1, 256, 846.0)],
        recent_errors: vec![McpToolErrorRecord {
            ts: 1_779_909_990,
            tool_name: "desktop_action".to_string(),
            message: "host_mutation_not_exposed: this MCP injects only dry_run or isolated actions"
                .to_string(),
        }],
    });

    assert_eq!(snapshot.summary.failing_tool_count, 0);

    let desktop = snapshot
        .tools
        .iter()
        .find(|tool| tool.tool_name == "desktop_action")
        .expect("desktop_action");

    assert_eq!(desktop.error_count, 1);
    assert_eq!(desktop.health, "healthy");
    assert_eq!(desktop.recommendation, "keep");
    assert!(desktop
        .risk_flags
        .contains(&"expected_safety_gate".to_string()));
    assert!(!desktop.risk_flags.contains(&"has_errors".to_string()));
}

#[test]
fn tool_atlas_marks_errors_without_recent_samples_as_observability_gap() {
    let snapshot = build_tool_atlas_snapshot(ToolAtlasInput {
        generated_at: 1_779_910_000,
        window_secs: 600,
        current_tools: vec!["shell_exec".to_string()],
        stats: vec![stat("shell_exec", 89, 41, 2_040, 233.0)],
        recent_errors: Vec::new(),
    });

    let shell = snapshot
        .tools
        .iter()
        .find(|tool| tool.tool_name == "shell_exec")
        .expect("shell_exec");

    assert_eq!(shell.health, "failing");
    assert!(shell.risk_flags.contains(&"has_errors".to_string()));
    assert!(shell
        .risk_flags
        .contains(&"missing_error_samples".to_string()));
}

#[test]
fn tool_atlas_isolates_external_batch_failures() {
    let mut s = stat("shell_exec", 89, 41, 2_040, 233.0);
    s.source = Some("other".to_string());

    let snapshot = build_tool_atlas_snapshot(ToolAtlasInput {
        generated_at: 1_779_910_000,
        window_secs: 600,
        current_tools: vec!["shell_exec".to_string()],
        stats: vec![s],
        recent_errors: Vec::new(),
    });

    let shell = snapshot
        .tools
        .iter()
        .find(|tool| tool.tool_name == "shell_exec")
        .expect("shell_exec");

    assert_eq!(shell.health, "failing");
    assert_eq!(shell.recommendation, "isolate_external_batch");
    assert!(shell.risk_flags.contains(&"has_errors".to_string()));
    assert!(shell
        .risk_flags
        .contains(&"missing_error_samples".to_string()));
    assert!(shell
        .risk_flags
        .contains(&"external_batch_load".to_string()));
    assert!(shell
        .risk_flags
        .contains(&"external_batch_failure".to_string()));
}

#[test]
fn tool_atlas_marks_external_bulk_latency() {
    let mut s = stat("memory_search", 120, 0, 4_412, 13_972.0);
    s.client_name = Some("p".to_string());
    s.profile = Some("all".to_string());
    s.source = Some("other".to_string());

    let snapshot = build_tool_atlas_snapshot(ToolAtlasInput {
        generated_at: 1_779_910_000,
        window_secs: 600,
        current_tools: vec!["memory_search".to_string()],
        stats: vec![s],
        recent_errors: Vec::new(),
    });

    let memory_search = snapshot
        .tools
        .iter()
        .find(|tool| tool.tool_name == "memory_search")
        .expect("memory_search");

    assert_eq!(memory_search.health, "degraded");
    assert!(memory_search.risk_flags.contains(&"slow_p95".to_string()));
    assert!(memory_search
        .risk_flags
        .contains(&"external_batch_load".to_string()));
}

#[test]
fn tool_atlas_marks_external_bulk_latency_without_profile_filter() {
    let mut s = stat("memory_search", 120, 0, 4_412, 13_972.0);
    s.source = Some("other".to_string());

    let snapshot = build_tool_atlas_snapshot(ToolAtlasInput {
        generated_at: 1_779_910_000,
        window_secs: 600,
        current_tools: vec!["memory_search".to_string()],
        stats: vec![s],
        recent_errors: Vec::new(),
    });

    let memory_search = snapshot
        .tools
        .iter()
        .find(|tool| tool.tool_name == "memory_search")
        .expect("memory_search");

    assert_eq!(memory_search.health, "degraded");
    assert!(memory_search.risk_flags.contains(&"slow_p95".to_string()));
    assert!(memory_search
        .risk_flags
        .contains(&"external_batch_load".to_string()));
}

#[test]
fn tool_atlas_treats_low_sample_max_p95_latency_as_sample_sensitive() {
    let mut s = stat("memory_search", 16, 0, 2_353, 16_386.0);
    s.client_name = Some("claude-code".to_string());
    s.profile = Some("all".to_string());
    s.source = Some("claude".to_string());

    let snapshot = build_tool_atlas_snapshot(ToolAtlasInput {
        generated_at: 1_779_910_000,
        window_secs: 86_400,
        current_tools: vec!["memory_search".to_string()],
        stats: vec![s],
        recent_errors: Vec::new(),
    });

    let memory_search = snapshot
        .tools
        .iter()
        .find(|tool| tool.tool_name == "memory_search")
        .expect("memory_search");

    assert_eq!(memory_search.health, "healthy");
    assert_eq!(memory_search.recommendation, "keep");
    assert!(memory_search
        .risk_flags
        .contains(&"sample_sensitive_p95".to_string()));
    assert!(!memory_search.risk_flags.contains(&"slow_p95".to_string()));
}

#[test]
fn tool_atlas_treats_memory_save_missing_required_key_as_expected_input_validation() {
    let snapshot = build_tool_atlas_snapshot(ToolAtlasInput {
        generated_at: 1_779_910_000,
        window_secs: 600,
        current_tools: vec!["memory_save".to_string()],
        stats: vec![stat("memory_save", 15, 1, 2_586, 872.0)],
        recent_errors: vec![McpToolErrorRecord {
            ts: 1_779_909_990,
            tool_name: "memory_save".to_string(),
            message: "missing or empty 'key'".to_string(),
        }],
    });

    assert_eq!(snapshot.summary.failing_tool_count, 0);

    let memory_save = snapshot
        .tools
        .iter()
        .find(|tool| tool.tool_name == "memory_save")
        .expect("memory_save");

    assert_eq!(memory_save.error_count, 1);
    assert_eq!(memory_save.health, "degraded");
    assert_eq!(memory_save.recommendation, "optimize_latency");
    assert!(memory_save
        .risk_flags
        .contains(&"expected_input_validation".to_string()));
    assert!(!memory_save.risk_flags.contains(&"has_errors".to_string()));
}

#[test]
fn tool_atlas_treats_work_memory_missing_key_as_expected_input_validation() {
    let snapshot = build_tool_atlas_snapshot(ToolAtlasInput {
        generated_at: 1_779_910_000,
        window_secs: 600,
        current_tools: vec!["work_memory".to_string()],
        stats: vec![stat("work_memory", 3, 1, 23, 629.0)],
        recent_errors: vec![McpToolErrorRecord {
            ts: 1_779_909_990,
            tool_name: "work_memory".to_string(),
            message: "get requires key".to_string(),
        }],
    });

    assert_eq!(snapshot.summary.failing_tool_count, 0);

    let work_memory = snapshot
        .tools
        .iter()
        .find(|tool| tool.tool_name == "work_memory")
        .expect("work_memory");

    assert_eq!(work_memory.error_count, 1);
    assert_eq!(work_memory.health, "healthy");
    assert_eq!(work_memory.recommendation, "keep");
    assert!(work_memory
        .risk_flags
        .contains(&"expected_input_validation".to_string()));
    assert!(!work_memory.risk_flags.contains(&"has_errors".to_string()));
}

#[test]
fn tool_atlas_treats_plan_load_missing_plan_as_expected_lookup_miss() {
    let snapshot = build_tool_atlas_snapshot(ToolAtlasInput {
        generated_at: 1_779_910_000,
        window_secs: 600,
        current_tools: vec!["plan_load".to_string()],
        stats: vec![stat("plan_load", 3, 1, 4, 1_979.0)],
        recent_errors: vec![McpToolErrorRecord {
            ts: 1_779_909_990,
            tool_name: "plan_load".to_string(),
            message: "plan not found: 'ab_tool_surface_cleanup_20260618'".to_string(),
        }],
    });

    assert_eq!(snapshot.summary.failing_tool_count, 0);

    let plan_load = snapshot
        .tools
        .iter()
        .find(|tool| tool.tool_name == "plan_load")
        .expect("plan_load");

    assert_eq!(plan_load.error_count, 1);
    assert_eq!(plan_load.health, "healthy");
    assert_eq!(plan_load.recommendation, "keep");
    assert!(plan_load
        .risk_flags
        .contains(&"expected_lookup_miss".to_string()));
    assert!(!plan_load.risk_flags.contains(&"has_errors".to_string()));
}

#[test]
fn tool_atlas_treats_mobile_adb_missing_as_expected_runtime_unavailable() {
    let snapshot = build_tool_atlas_snapshot(ToolAtlasInput {
        generated_at: 1_779_910_000,
        window_secs: 600,
        current_tools: vec!["mobile_click".to_string()],
        stats: vec![stat("mobile_click", 1, 1, 15, 215.0)],
        recent_errors: vec![McpToolErrorRecord {
            ts: 1_779_909_990,
            tool_name: "mobile_click".to_string(),
            message: "spawn adb failed: No such file or directory (os error 2)".to_string(),
        }],
    });

    assert_eq!(snapshot.summary.failing_tool_count, 0);

    let mobile_click = snapshot
        .tools
        .iter()
        .find(|tool| tool.tool_name == "mobile_click")
        .expect("mobile_click");

    assert_eq!(mobile_click.error_count, 1);
    assert_eq!(mobile_click.health, "healthy");
    assert_eq!(mobile_click.recommendation, "keep");
    assert!(mobile_click
        .risk_flags
        .contains(&"expected_runtime_unavailable".to_string()));
    assert!(!mobile_click.risk_flags.contains(&"has_errors".to_string()));
}

#[test]
fn tool_atlas_treats_unexposed_browser_input_errors_as_historical() {
    let snapshot = build_tool_atlas_snapshot(ToolAtlasInput {
        generated_at: 1_779_910_000,
        window_secs: 600,
        current_tools: vec!["tool_atlas_snapshot".to_string()],
        stats: vec![
            stat("browser_click", 5, 3, 32, 187.0),
            stat("browser_snapshot", 3, 1, 25, 850.0),
        ],
        recent_errors: vec![
            McpToolErrorRecord {
                ts: 1_779_909_990,
                tool_name: "browser_click".to_string(),
                message: "missing 'page'".to_string(),
            },
            McpToolErrorRecord {
                ts: 1_779_909_991,
                tool_name: "browser_click".to_string(),
                message:
                    "browser: invalid argument: ref @e2 element is disabled — click refused (it would no-op)"
                        .to_string(),
            },
            McpToolErrorRecord {
                ts: 1_779_909_992,
                tool_name: "browser_snapshot".to_string(),
                message: "missing 'page'".to_string(),
            },
        ],
    });

    assert_eq!(snapshot.summary.failing_tool_count, 0);

    let browser_click = snapshot
        .tools
        .iter()
        .find(|tool| tool.tool_name == "browser_click")
        .expect("browser_click");
    assert!(!browser_click.exposed);
    assert_eq!(browser_click.error_count, 3);
    assert_eq!(browser_click.health, "healthy");
    assert_eq!(browser_click.recommendation, "keep");
    assert!(browser_click
        .risk_flags
        .contains(&"historical_unexposed_failure".to_string()));
    assert!(!browser_click.risk_flags.contains(&"has_errors".to_string()));

    let browser_snapshot = snapshot
        .tools
        .iter()
        .find(|tool| tool.tool_name == "browser_snapshot")
        .expect("browser_snapshot");
    assert!(!browser_snapshot.exposed);
    assert_eq!(browser_snapshot.error_count, 1);
    assert_eq!(browser_snapshot.health, "healthy");
    assert_eq!(browser_snapshot.recommendation, "keep");
    assert!(browser_snapshot
        .risk_flags
        .contains(&"historical_unexposed_failure".to_string()));
    assert!(!browser_snapshot
        .risk_flags
        .contains(&"has_errors".to_string()));
}
