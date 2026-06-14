//! GoS-lite belief graph projections for Agent-Bridge diagnostics.
//!
//! This is a small, read-only adaptation of the Graph-of-States idea for
//! operational telemetry: convert grounded Tool Atlas facts into explicit
//! Signal/Evidence/Hypothesis nodes plus support/refines edges. It does not
//! call tools, write state, or ask an LLM to fill missing evidence.

use crate::tool_atlas::{ToolAtlasEntry, ToolAtlasSnapshot};
use serde::{Deserialize, Serialize};
use serde_json::{json, Value};

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

    if tool.risk_flags.iter().any(|flag| flag == "large_result") {
        let evidence_id = format!("evidence:tool:{}:large_result", tool.tool_name);
        nodes.push(GosLiteNode {
            id: evidence_id.clone(),
            node_type: "Evidence".to_string(),
            label: format!("average result size is {:.0} bytes", tool.avg_result_size),
            score: 1.0,
            attrs: json!({
                "provenance_source": "tool_atlas.risk_flags",
                "risk_flag": "large_result",
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
