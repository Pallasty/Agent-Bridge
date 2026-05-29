//! Read-only Tool Atlas projection over MCP dispatch telemetry.

use ab_store::{McpToolCallStats, McpToolErrorRecord};
use serde::{Deserialize, Serialize};
use std::collections::{BTreeMap, BTreeSet, HashMap};

const HOT_CALL_THRESHOLD: u64 = 10;
const SLOW_P95_MS: u32 = 1_000;
const LARGE_AVG_RESULT_SIZE: f64 = 24_000.0;

#[derive(Debug, Clone)]
pub struct ToolAtlasInput {
    pub generated_at: i64,
    pub window_secs: i64,
    pub current_tools: Vec<String>,
    pub stats: Vec<McpToolCallStats>,
    pub recent_errors: Vec<McpToolErrorRecord>,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub struct ToolAtlasSnapshot {
    pub schema_version: u32,
    pub generated_at: i64,
    pub window_secs: i64,
    pub summary: ToolAtlasSummary,
    pub tools: Vec<ToolAtlasEntry>,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct ToolAtlasViewOptions {
    pub include_tools: bool,
    pub limit: usize,
}

impl Default for ToolAtlasViewOptions {
    fn default() -> Self {
        Self {
            include_tools: true,
            limit: 20,
        }
    }
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct ToolAtlasSummary {
    pub current_tool_count: usize,
    pub observed_tool_count: usize,
    pub failing_tool_count: usize,
    pub cold_tool_count: usize,
    pub hot_tool_count: usize,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub struct ToolAtlasEntry {
    pub tool_name: String,
    pub exposed: bool,
    pub observed: bool,
    pub usage_class: String,
    pub health: String,
    pub recommendation: String,
    pub call_count: u64,
    pub error_count: u64,
    pub error_rate: f64,
    pub avg_duration_ms: f64,
    pub p95_duration_ms: u32,
    pub max_duration_ms: u32,
    pub avg_result_size: f64,
    pub risk_flags: Vec<String>,
    pub failure_samples: Vec<ToolAtlasFailureSample>,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct ToolAtlasFailureSample {
    pub ts: i64,
    pub message: String,
}

pub fn build_tool_atlas_snapshot(input: ToolAtlasInput) -> ToolAtlasSnapshot {
    let current: BTreeSet<String> = input
        .current_tools
        .into_iter()
        .map(|name| name.trim().to_string())
        .filter(|name| !name.is_empty())
        .collect();
    let stats_by_tool: HashMap<String, McpToolCallStats> = input
        .stats
        .into_iter()
        .map(|stat| (stat.tool_name.clone(), stat))
        .collect();
    let failures_by_tool = group_recent_errors(
        input.recent_errors,
        input.generated_at.saturating_sub(input.window_secs.max(0)),
    );

    let mut names = current.clone();
    names.extend(stats_by_tool.keys().cloned());
    names.extend(failures_by_tool.keys().cloned());

    let mut tools = names
        .into_iter()
        .map(|tool_name| {
            let stat = stats_by_tool.get(&tool_name);
            let failures = failures_by_tool
                .get(&tool_name)
                .cloned()
                .unwrap_or_default();
            atlas_entry(&tool_name, current.contains(&tool_name), stat, failures)
        })
        .collect::<Vec<_>>();
    tools.sort_by(|a, b| {
        tool_sort_key(a)
            .cmp(&tool_sort_key(b))
            .then_with(|| a.tool_name.cmp(&b.tool_name))
    });

    let summary = ToolAtlasSummary {
        current_tool_count: current.len(),
        observed_tool_count: tools.iter().filter(|tool| tool.observed).count(),
        failing_tool_count: tools.iter().filter(|tool| tool.health == "failing").count(),
        cold_tool_count: tools
            .iter()
            .filter(|tool| tool.usage_class == "cold")
            .count(),
        hot_tool_count: tools
            .iter()
            .filter(|tool| tool.usage_class == "hot")
            .count(),
    };

    ToolAtlasSnapshot {
        schema_version: 1,
        generated_at: input.generated_at,
        window_secs: input.window_secs.clamp(60, 31_536_000),
        summary,
        tools,
    }
}

pub fn project_tool_atlas_snapshot(
    snapshot: &ToolAtlasSnapshot,
    options: ToolAtlasViewOptions,
) -> serde_json::Value {
    let limit = options.limit.clamp(1, 500);
    let tools_total = snapshot.tools.len();
    let tools_included = if options.include_tools {
        tools_total.min(limit)
    } else {
        0
    };
    let mut payload = serde_json::to_value(snapshot).unwrap_or_else(|_| serde_json::json!({}));
    if let Some(obj) = payload.as_object_mut() {
        obj.insert(
            "tools".to_string(),
            serde_json::to_value(&snapshot.tools[..tools_included])
                .unwrap_or_else(|_| serde_json::json!([])),
        );
        obj.insert(
            "tools_included".to_string(),
            serde_json::json!(tools_included),
        );
        obj.insert(
            "tools_omitted".to_string(),
            serde_json::json!(tools_total.saturating_sub(tools_included)),
        );
        obj.insert(
            "tool_limit".to_string(),
            serde_json::json!(if options.include_tools { limit } else { 0 }),
        );
    }
    payload
}

fn group_recent_errors(
    errors: Vec<McpToolErrorRecord>,
    cutoff: i64,
) -> BTreeMap<String, Vec<ToolAtlasFailureSample>> {
    let mut by_tool = BTreeMap::<String, Vec<ToolAtlasFailureSample>>::new();
    for error in errors.into_iter().filter(|error| error.ts >= cutoff) {
        let samples = by_tool.entry(error.tool_name).or_default();
        if samples.len() < 3 {
            samples.push(ToolAtlasFailureSample {
                ts: error.ts,
                message: error.message,
            });
        }
    }
    by_tool
}

fn atlas_entry(
    tool_name: &str,
    exposed: bool,
    stat: Option<&McpToolCallStats>,
    failure_samples: Vec<ToolAtlasFailureSample>,
) -> ToolAtlasEntry {
    let call_count = stat.map(|s| s.call_count).unwrap_or(0);
    let error_count = stat.map(|s| s.error_count).unwrap_or(0);
    let observed = call_count > 0;
    let error_rate = if call_count == 0 {
        0.0
    } else {
        error_count as f64 / call_count as f64
    };
    let avg_duration_ms = stat.map(|s| s.avg_duration_ms).unwrap_or(0.0);
    let p95_duration_ms = stat.map(|s| s.p95_duration_ms).unwrap_or(0);
    let max_duration_ms = stat.map(|s| s.max_duration_ms).unwrap_or(0);
    let avg_result_size = stat.map(|s| s.avg_result_size).unwrap_or(0.0);
    let usage_class = usage_class(call_count).to_string();
    let has_expected_confirmation_errors =
        has_expected_confirmation_errors(tool_name, &failure_samples);
    let actionable_error_count = if has_expected_confirmation_errors {
        0
    } else {
        error_count
    };
    let risk_flags = risk_flags(
        tool_name,
        actionable_error_count,
        p95_duration_ms,
        avg_result_size,
        has_expected_confirmation_errors,
    );
    let health = health(
        observed,
        actionable_error_count,
        !failure_samples.is_empty() && !has_expected_confirmation_errors,
        &risk_flags,
    )
    .to_string();
    let recommendation = recommendation(&usage_class, &health, &risk_flags).to_string();

    ToolAtlasEntry {
        tool_name: tool_name.to_string(),
        exposed,
        observed,
        usage_class,
        health,
        recommendation,
        call_count,
        error_count,
        error_rate,
        avg_duration_ms,
        p95_duration_ms,
        max_duration_ms,
        avg_result_size,
        risk_flags,
        failure_samples,
    }
}

fn usage_class(call_count: u64) -> &'static str {
    if call_count == 0 {
        "cold"
    } else if call_count >= HOT_CALL_THRESHOLD {
        "hot"
    } else {
        "warm"
    }
}

fn risk_flags(
    tool_name: &str,
    error_count: u64,
    p95_duration_ms: u32,
    avg_result_size: f64,
    has_expected_confirmation_errors: bool,
) -> Vec<String> {
    let mut flags = Vec::new();
    if error_count > 0 {
        flags.push("has_errors".to_string());
    }
    if has_expected_confirmation_errors {
        flags.push("expected_confirmation".to_string());
    }
    if p95_duration_ms >= SLOW_P95_MS {
        if is_expected_wait_tool(tool_name) {
            flags.push("expected_wait".to_string());
        } else {
            flags.push("slow_p95".to_string());
        }
    }
    if avg_result_size >= LARGE_AVG_RESULT_SIZE {
        flags.push("large_average_result".to_string());
    }
    flags
}

fn is_expected_wait_tool(tool_name: &str) -> bool {
    matches!(tool_name, "agent_session_wait")
}

fn has_expected_confirmation_errors(tool_name: &str, samples: &[ToolAtlasFailureSample]) -> bool {
    !samples.is_empty()
        && samples
            .iter()
            .all(|sample| is_expected_confirmation_error(tool_name, &sample.message))
}

fn is_expected_confirmation_error(tool_name: &str, message: &str) -> bool {
    tool_name == "agent_session_reconcile"
        && message.contains("requires apply_confirmation=\"finalise_stale_sessions\"")
}

fn has_actionable_risk_flags(risk_flags: &[String]) -> bool {
    risk_flags
        .iter()
        .any(|flag| !matches!(flag.as_str(), "expected_wait" | "expected_confirmation"))
}

fn health(
    observed: bool,
    error_count: u64,
    has_failure_samples: bool,
    risk_flags: &[String],
) -> &'static str {
    if error_count > 0 || has_failure_samples {
        "failing"
    } else if !observed {
        "unobserved"
    } else if !has_actionable_risk_flags(risk_flags) {
        "healthy"
    } else {
        "degraded"
    }
}

fn recommendation(usage_class: &str, health: &str, risk_flags: &[String]) -> &'static str {
    if health == "failing" {
        "fix_failure_mode"
    } else if risk_flags.iter().any(|flag| flag == "slow_p95") {
        "optimize_latency"
    } else if risk_flags.iter().any(|flag| flag == "large_average_result") {
        "reduce_payload"
    } else if usage_class == "cold" {
        "watch"
    } else {
        "keep"
    }
}

fn tool_sort_key(tool: &ToolAtlasEntry) -> (u8, std::cmp::Reverse<u64>) {
    let bucket = match tool.health.as_str() {
        "failing" => 0,
        "degraded" => 1,
        "healthy" => 2,
        "unobserved" => 3,
        _ => 4,
    };
    (bucket, std::cmp::Reverse(tool.call_count))
}
