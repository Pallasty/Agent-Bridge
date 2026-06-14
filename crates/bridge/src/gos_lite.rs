//! GoS-lite belief graph projections for Agent-Bridge diagnostics.
//!
//! This is a small, read-only adaptation of the Graph-of-States idea for
//! operational telemetry: convert grounded Tool Atlas facts into explicit
//! Signal/Evidence/Hypothesis nodes plus support/refines edges. It does not
//! call tools, write state, or ask an LLM to fill missing evidence.

use crate::{
    event_spine::{EventSpineEvent, EventSpineSnapshot},
    tool_atlas::{ToolAtlasEntry, ToolAtlasSnapshot},
};
use serde::{Deserialize, Serialize};
use serde_json::{json, Value};
use std::collections::{BTreeSet, HashSet};

const SLOW_P95_MS: u64 = 1_000;
const LARGE_RESULT_SIZE: u64 = 24_000;

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub struct GosLiteSnapshot {
    pub schema_version: u32,
    pub generated_at: i64,
    pub window_secs: i64,
    pub status: String,
    pub next_action: String,
    pub summary: GosLiteSummary,
    pub nodes: Vec<GosLiteNode>,
    pub edges: Vec<GosLiteEdge>,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct GosLiteSummary {
    pub signals: usize,
    pub evidence: usize,
    pub hypotheses: usize,
    pub support_edges: usize,
    pub refute_edges: usize,
    pub refines_edges: usize,
    pub failing_tools: usize,
    pub degraded_tools: usize,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub struct GosLiteNode {
    pub id: String,
    pub node_type: String,
    pub label: String,
    pub score: f64,
    pub attrs: Value,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub struct GosLiteEdge {
    pub src: String,
    pub dst: String,
    pub edge_type: String,
    pub confidence: f64,
    pub attrs: Value,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct GosLiteReplayReport {
    pub schema_version: u32,
    pub event_chain_verified: bool,
    pub event_count: usize,
    pub truncated_count: usize,
    pub replay_ready: bool,
    pub summary: GosLiteReplaySummary,
    pub checks: Vec<GosLiteReplayCheck>,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct GosLiteReplaySummary {
    pub hypotheses_checked: usize,
    pub supported: usize,
    pub falsifier_candidates: usize,
    pub inconclusive: usize,
    pub chain_unverified: usize,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct GosLiteReplayCheck {
    pub hypothesis_id: String,
    pub hypothesis_kind: String,
    pub tool_name: String,
    pub verdict: String,
    pub review_action: String,
    pub supporting_event_ids: Vec<String>,
    pub supporting_sources: Vec<String>,
    pub refuting_event_ids: Vec<String>,
    pub notes: Vec<String>,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct GosLiteViewOptions {
    pub include_graph: bool,
    pub limit: usize,
}

impl Default for GosLiteViewOptions {
    fn default() -> Self {
        Self {
            include_graph: true,
            limit: 100,
        }
    }
}

pub fn build_gos_lite_snapshot_from_tool_atlas(atlas: &ToolAtlasSnapshot) -> GosLiteSnapshot {
    let mut nodes = vec![GosLiteNode {
        id: "signal:tool_atlas_window".to_string(),
        node_type: "Signal".to_string(),
        label: format!("Tool Atlas telemetry window: {}s", atlas.window_secs),
        score: 1.0,
        attrs: json!({
            "provenance_source": "tool_atlas.summary",
            "current_tool_count": atlas.summary.current_tool_count,
            "observed_tool_count": atlas.summary.observed_tool_count,
            "failing_tool_count": atlas.summary.failing_tool_count,
            "cold_tool_count": atlas.summary.cold_tool_count,
            "hot_tool_count": atlas.summary.hot_tool_count,
        }),
    }];
    let mut edges = Vec::new();

    let mut failing_tools = 0usize;
    let mut degraded_tools = 0usize;
    for tool in &atlas.tools {
        match tool.health.as_str() {
            "failing" => {
                failing_tools += 1;
                add_failing_tool_projection(tool, &mut nodes, &mut edges);
            }
            "degraded" => {
                degraded_tools += 1;
                add_degraded_tool_projection(tool, &mut nodes, &mut edges);
            }
            _ => {}
        }
    }

    let summary = GosLiteSummary {
        signals: nodes
            .iter()
            .filter(|node| node.node_type == "Signal")
            .count(),
        evidence: nodes
            .iter()
            .filter(|node| node.node_type == "Evidence")
            .count(),
        hypotheses: nodes
            .iter()
            .filter(|node| node.node_type == "Hypothesis")
            .count(),
        support_edges: edges
            .iter()
            .filter(|edge| edge.edge_type == "support")
            .count(),
        refute_edges: edges
            .iter()
            .filter(|edge| edge.edge_type == "refute")
            .count(),
        refines_edges: edges
            .iter()
            .filter(|edge| edge.edge_type == "refines")
            .count(),
        failing_tools,
        degraded_tools,
    };
    let (status, next_action) = if failing_tools > 0 {
        ("needs_investigation", "investigate_failure")
    } else if degraded_tools > 0 {
        ("needs_optimization", "optimize_degraded_tools")
    } else {
        ("monitor", "watch")
    };

    GosLiteSnapshot {
        schema_version: 1,
        generated_at: atlas.generated_at,
        window_secs: atlas.window_secs,
        status: status.to_string(),
        next_action: next_action.to_string(),
        summary,
        nodes,
        edges,
    }
}

pub fn project_gos_lite_snapshot(snapshot: &GosLiteSnapshot, options: GosLiteViewOptions) -> Value {
    let limit = options.limit.clamp(1, 500);
    let nodes_total = snapshot.nodes.len();
    let edges_total = snapshot.edges.len();
    let nodes_included = if options.include_graph {
        nodes_total.min(limit)
    } else {
        0
    };
    let included_node_ids = snapshot.nodes[..nodes_included]
        .iter()
        .map(|node| node.id.as_str())
        .collect::<HashSet<_>>();
    let included_edges = if options.include_graph {
        snapshot
            .edges
            .iter()
            .filter(|edge| {
                included_node_ids.contains(edge.src.as_str())
                    && included_node_ids.contains(edge.dst.as_str())
            })
            .cloned()
            .collect::<Vec<_>>()
    } else {
        Vec::new()
    };
    let edges_included = included_edges.len();

    let mut payload = serde_json::to_value(snapshot).unwrap_or_else(|_| json!({}));
    if let Some(obj) = payload.as_object_mut() {
        obj.insert(
            "nodes".to_string(),
            serde_json::to_value(&snapshot.nodes[..nodes_included]).unwrap_or_else(|_| json!([])),
        );
        obj.insert(
            "edges".to_string(),
            serde_json::to_value(&included_edges).unwrap_or_else(|_| json!([])),
        );
        obj.insert("nodes_total".to_string(), json!(nodes_total));
        obj.insert("nodes_included".to_string(), json!(nodes_included));
        obj.insert(
            "nodes_omitted".to_string(),
            json!(nodes_total.saturating_sub(nodes_included)),
        );
        obj.insert("edges_total".to_string(), json!(edges_total));
        obj.insert("edges_included".to_string(), json!(edges_included));
        obj.insert(
            "edges_omitted".to_string(),
            json!(edges_total.saturating_sub(edges_included)),
        );
        obj.insert(
            "graph_limit".to_string(),
            json!(if options.include_graph { limit } else { 0 }),
        );
        obj.insert("graph_included".to_string(), json!(options.include_graph));
        obj.insert(
            "human_gate".to_string(),
            gos_lite_human_gate_packet(snapshot),
        );
    }
    payload
}

pub fn build_gos_lite_replay_report(
    snapshot: &GosLiteSnapshot,
    event_spine: &EventSpineSnapshot,
) -> GosLiteReplayReport {
    let checks = snapshot
        .nodes
        .iter()
        .filter(|node| node.node_type == "Hypothesis")
        .map(|node| gos_lite_replay_check(node, event_spine))
        .collect::<Vec<_>>();
    let summary = GosLiteReplaySummary {
        hypotheses_checked: checks.len(),
        supported: checks
            .iter()
            .filter(|check| check.verdict == "supported")
            .count(),
        falsifier_candidates: checks
            .iter()
            .filter(|check| check.verdict == "falsifier_candidate")
            .count(),
        inconclusive: checks
            .iter()
            .filter(|check| check.verdict == "inconclusive")
            .count(),
        chain_unverified: checks
            .iter()
            .filter(|check| check.verdict == "chain_unverified")
            .count(),
    };

    GosLiteReplayReport {
        schema_version: 1,
        event_chain_verified: event_spine.integrity.verified,
        event_count: event_spine.event_count,
        truncated_count: event_spine.truncated_count,
        replay_ready: event_spine.integrity.verified && event_spine.truncated_count == 0,
        summary,
        checks,
    }
}

fn gos_lite_replay_check(
    hypothesis: &GosLiteNode,
    event_spine: &EventSpineSnapshot,
) -> GosLiteReplayCheck {
    let tool_name = hypothesis.attrs["tool_name"]
        .as_str()
        .unwrap_or("unknown")
        .to_string();
    let hypothesis_kind = if hypothesis.id.ends_with(":failure_mode") {
        "failure_mode"
    } else if hypothesis.id.ends_with(":latency_or_size_degradation") {
        "latency_or_size_degradation"
    } else {
        "unknown"
    }
    .to_string();
    let mut supporting_event_ids = Vec::new();
    let mut supporting_sources = BTreeSet::new();
    let mut refuting_event_ids = Vec::new();
    let mut same_tool_events = 0usize;

    for event in &event_spine.events {
        if event_tool_name(event) != Some(tool_name.as_str()) {
            continue;
        }
        same_tool_events += 1;
        if event_supports_hypothesis(&hypothesis_kind, hypothesis, event) {
            supporting_event_ids.push(event.event_id.clone());
            supporting_sources.insert(event.source.clone());
        } else if event_refutes_hypothesis(&hypothesis_kind, hypothesis, event) {
            refuting_event_ids.push(event.event_id.clone());
        }
    }

    let replay_ready = event_spine.integrity.verified && event_spine.truncated_count == 0;
    let verdict = if !event_spine.integrity.verified {
        "chain_unverified"
    } else if !supporting_event_ids.is_empty() {
        "supported"
    } else if replay_ready && !refuting_event_ids.is_empty() {
        "falsifier_candidate"
    } else {
        "inconclusive"
    }
    .to_string();
    let review_action = match verdict.as_str() {
        "chain_unverified" => "verify_event_spine",
        "supported" => "review_support",
        "falsifier_candidate" => "replay_or_refute",
        _ if event_spine.truncated_count > 0 => "increase_event_limit_or_window",
        _ => "collect_more_events",
    }
    .to_string();

    let mut notes = Vec::new();
    if same_tool_events == 0 {
        notes.push("no same-tool events were present in the Event Spine window".to_string());
    }
    if supporting_event_ids.is_empty() {
        let support_kind = match hypothesis_kind.as_str() {
            "failure_mode" => "failure",
            "latency_or_size_degradation" => "degradation",
            _ => "matching",
        };
        notes.push(format!("no event-level {support_kind} support was found"));
    }
    if event_spine.truncated_count > 0 {
        notes.push(
            "Event Spine was truncated; missing older events may change the verdict".to_string(),
        );
    }
    if !event_spine.integrity.verified {
        notes.push("Event Spine hash chain did not verify".to_string());
    }

    GosLiteReplayCheck {
        hypothesis_id: hypothesis.id.clone(),
        hypothesis_kind,
        tool_name,
        verdict,
        review_action,
        supporting_event_ids,
        supporting_sources: supporting_sources.into_iter().collect(),
        refuting_event_ids,
        notes,
    }
}

fn event_tool_name(event: &EventSpineEvent) -> Option<&str> {
    event.facts["tool_name"].as_str()
}

fn event_supports_hypothesis(
    hypothesis_kind: &str,
    hypothesis: &GosLiteNode,
    event: &EventSpineEvent,
) -> bool {
    match hypothesis_kind {
        "failure_mode" => {
            event.kind == "tool_error" || (event.kind == "tool_call" && event.ok == Some(false))
        }
        "latency_or_size_degradation" => {
            event.kind == "tool_call"
                && ((has_risk_flag(hypothesis, "slow_p95")
                    && event.facts["duration_ms"].as_u64().unwrap_or(0) >= SLOW_P95_MS)
                    || (has_risk_flag(hypothesis, "large_result")
                        && event.facts["result_size"].as_u64().unwrap_or(0) >= LARGE_RESULT_SIZE))
        }
        _ => false,
    }
}

fn event_refutes_hypothesis(
    hypothesis_kind: &str,
    hypothesis: &GosLiteNode,
    event: &EventSpineEvent,
) -> bool {
    match hypothesis_kind {
        "failure_mode" => event.kind == "tool_call" && event.ok == Some(true),
        "latency_or_size_degradation" => {
            event.kind == "tool_call"
                && (!has_risk_flag(hypothesis, "slow_p95")
                    || event.facts["duration_ms"].as_u64().unwrap_or(0) < SLOW_P95_MS)
                && (!has_risk_flag(hypothesis, "large_result")
                    || event.facts["result_size"].as_u64().unwrap_or(0) < LARGE_RESULT_SIZE)
        }
        _ => false,
    }
}

fn has_risk_flag(hypothesis: &GosLiteNode, flag: &str) -> bool {
    hypothesis.attrs["risk_flags"]
        .as_array()
        .map(|flags| flags.iter().any(|value| value.as_str() == Some(flag)))
        .unwrap_or(false)
}

fn gos_lite_human_gate_packet(snapshot: &GosLiteSnapshot) -> Value {
    let required = snapshot.summary.hypotheses > 0;
    json!({
        "required": required,
        "reason": if required {
            "GoS-lite hypotheses are diagnostic candidates, not durable decisions."
        } else {
            "No hypotheses were generated for the selected telemetry window."
        },
        "forum": {
            "board": "design",
            "kind": "finding",
            "title": format!(
                "Review GoS-lite hypotheses: {} failing, {} degraded tools",
                snapshot.summary.failing_tools,
                snapshot.summary.degraded_tools
            ),
        },
        "promotion_allowed": false,
        "promotion_policy": "Human reviewer must confirm, refute, or defer GoS-lite hypotheses before saving them as durable decisions, changing tool profiles, or treating them as research conclusions.",
        "review_questions": [
            "Which evidence nodes directly support each hypothesis?",
            "Is any support edge weak, stale, duplicated, or missing contradictory evidence?",
            "Should the hypothesis be confirmed, refuted, deferred, or converted into a replay/falsifier test?",
        ],
    })
}

fn add_failing_tool_projection(
    tool: &ToolAtlasEntry,
    nodes: &mut Vec<GosLiteNode>,
    edges: &mut Vec<GosLiteEdge>,
) {
    let hypothesis_id = format!("hypothesis:tool:{}:failure_mode", tool.tool_name);
    let confidence = tool.error_rate.max(0.6).min(1.0);
    nodes.push(GosLiteNode {
        id: hypothesis_id.clone(),
        node_type: "Hypothesis".to_string(),
        label: format!("Tool `{}` has an actionable failure mode", tool.tool_name),
        score: confidence,
        attrs: tool_attrs(tool, "tool_atlas.tool.health"),
    });
    edges.push(refines_edge(&hypothesis_id, confidence));

    for (idx, sample) in tool.failure_samples.iter().enumerate() {
        let evidence_id = format!(
            "evidence:tool:{}:failure_sample:{}",
            tool.tool_name,
            idx + 1
        );
        nodes.push(GosLiteNode {
            id: evidence_id.clone(),
            node_type: "Evidence".to_string(),
            label: sample.message.clone(),
            score: 1.0,
            attrs: json!({
                "provenance_source": "tool_atlas.failure_samples",
                "tool_name": tool.tool_name,
                "ts": sample.ts,
            }),
        });
        edges.push(support_edge(&evidence_id, &hypothesis_id, 1.0));
    }
}

fn add_degraded_tool_projection(
    tool: &ToolAtlasEntry,
    nodes: &mut Vec<GosLiteNode>,
    edges: &mut Vec<GosLiteEdge>,
) {
    let hypothesis_id = format!(
        "hypothesis:tool:{}:latency_or_size_degradation",
        tool.tool_name
    );
    nodes.push(GosLiteNode {
        id: hypothesis_id.clone(),
        node_type: "Hypothesis".to_string(),
        label: format!(
            "Tool `{}` is degraded and may need optimization",
            tool.tool_name
        ),
        score: 0.55,
        attrs: tool_attrs(tool, "tool_atlas.tool.health"),
    });
    edges.push(refines_edge(&hypothesis_id, 0.55));

    if tool.risk_flags.iter().any(|flag| flag == "slow_p95") {
        let evidence_id = format!("evidence:tool:{}:slow_p95", tool.tool_name);
        nodes.push(GosLiteNode {
            id: evidence_id.clone(),
            node_type: "Evidence".to_string(),
            label: format!("p95 latency is {}ms", tool.p95_duration_ms),
            score: 1.0,
            attrs: json!({
                "provenance_source": "tool_atlas.risk_flags",
                "risk_flag": "slow_p95",
                "tool_name": tool.tool_name,
                "p95_duration_ms": tool.p95_duration_ms,
            }),
        });
        edges.push(support_edge(&evidence_id, &hypothesis_id, 0.8));
    }

    if tool
        .risk_flags
        .iter()
        .any(|flag| flag == "large_average_result" || flag == "large_result")
    {
        let evidence_id = format!("evidence:tool:{}:large_result", tool.tool_name);
        nodes.push(GosLiteNode {
            id: evidence_id.clone(),
            node_type: "Evidence".to_string(),
            label: format!("average result size is {:.0} bytes", tool.avg_result_size),
            score: 1.0,
            attrs: json!({
                "provenance_source": "tool_atlas.risk_flags",
                "risk_flag": "large_average_result",
                "tool_name": tool.tool_name,
                "avg_result_size": tool.avg_result_size,
            }),
        });
        edges.push(support_edge(&evidence_id, &hypothesis_id, 0.7));
    }
}

fn tool_attrs(tool: &ToolAtlasEntry, provenance_source: &str) -> Value {
    json!({
        "provenance_source": provenance_source,
        "tool_name": tool.tool_name,
        "health": tool.health,
        "recommendation": tool.recommendation,
        "exposed": tool.exposed,
        "observed": tool.observed,
        "call_count": tool.call_count,
        "error_count": tool.error_count,
        "error_rate": tool.error_rate,
        "risk_flags": tool.risk_flags,
    })
}

fn refines_edge(dst: &str, confidence: f64) -> GosLiteEdge {
    GosLiteEdge {
        src: "signal:tool_atlas_window".to_string(),
        dst: dst.to_string(),
        edge_type: "refines".to_string(),
        confidence,
        attrs: json!({
            "provenance_source": "tool_atlas.projection",
        }),
    }
}

fn support_edge(src: &str, dst: &str, confidence: f64) -> GosLiteEdge {
    GosLiteEdge {
        src: src.to_string(),
        dst: dst.to_string(),
        edge_type: "support".to_string(),
        confidence,
        attrs: json!({
            "provenance_source": "tool_atlas.projection",
        }),
    }
}
