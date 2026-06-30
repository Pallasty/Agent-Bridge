//! Read-only workflow feedback report.
//!
//! This is the first report-first slice from
//! `docs/design/WORKFLOW_FEEDBACK_LOOP_RESEARCH_2026_06_30.md`: compose
//! existing Agent-Bridge state into a scorecard and an Experience Object v0
//! fixture. It does not write memory, alter retrieval, or authorize runtime
//! influence.

use ab_store::{McpToolCallStats, StateStore};
use anyhow::{Context, Result, bail};
use serde::Serialize;
use serde_json::{Value, json};
use std::collections::{BTreeMap, BTreeSet};
use std::path::PathBuf;

pub const WORKFLOW_FEEDBACK_REPORT_SCHEMA: &str = "agent_bridge.workflow_feedback_report.v0";
pub const EXPERIENCE_OBJECT_SCHEMA: &str = "agent_bridge.experience.v0";
pub const WORKFLOW_FEEDBACK_SHADOW_SCORE_SCHEMA: &str =
    "agent_bridge.workflow_feedback_shadow_score.v0";
pub const WORKFLOW_FEEDBACK_SHADOW_SCORE_SCENARIOS_SCHEMA: &str =
    "agent_bridge.workflow_feedback_shadow_score_scenarios.v0";
pub const WORKFLOW_FEEDBACK_PROMOTION_GATE_SCHEMA: &str =
    "agent_bridge.workflow_feedback_promotion_gate.v0";
pub const WORKFLOW_FEEDBACK_LIFT_EVIDENCE_SCHEMA: &str =
    "agent_bridge.workflow_feedback_lift_evidence.v0";

#[derive(Debug, Clone)]
pub struct WorkflowFeedbackReportOptions {
    pub window_secs: i64,
    pub top_tools: u32,
    pub scope: Option<String>,
}

impl Default for WorkflowFeedbackReportOptions {
    fn default() -> Self {
        Self {
            window_secs: 86_400,
            top_tools: 10,
            scope: None,
        }
    }
}

#[derive(Debug, Clone, Serialize)]
pub struct WorkflowFeedbackReport {
    pub schema: &'static str,
    pub read_only: bool,
    pub boundary: WorkflowFeedbackBoundary,
    pub source_anchors: Vec<String>,
    pub evidence: WorkflowFeedbackEvidence,
    pub scorecard: Vec<ScorecardAxis>,
    pub proposed_improvements: Vec<ProposedImprovement>,
    pub experience_object_fixture: Value,
}

#[derive(Debug, Clone, Serialize)]
pub struct WorkflowFeedbackBoundary {
    pub writes_memory: bool,
    pub mutates_runtime_policy: bool,
    pub changes_retrieval_order: bool,
    pub runtime_influence_allowed: bool,
    pub owner_gated_runtime_influence: bool,
}

#[derive(Debug, Clone, Serialize)]
pub struct WorkflowFeedbackEvidence {
    pub memory: MemoryEvidence,
    pub tool_telemetry: ToolTelemetryEvidence,
}

#[derive(Debug, Clone, Serialize)]
pub struct MemoryEvidence {
    pub active_rows: u64,
    pub feedback_rows: u64,
    pub feedback_fraction: f64,
    pub edge_count: u64,
    pub distinct_kinds: usize,
    pub distinct_scopes: usize,
    pub distinct_embedding_backends: usize,
    pub top_kinds: Vec<CountRow>,
    pub top_scopes: Vec<CountRow>,
    pub embedding_backends: Vec<CountRow>,
}

#[derive(Debug, Clone, Serialize)]
pub struct ToolTelemetryEvidence {
    pub window_secs: i64,
    pub tools_observed: usize,
    pub total_calls_in_top_window: u64,
    pub total_errors_in_top_window: u64,
    pub error_rate_in_top_window: f64,
    pub hot_tools: Vec<ToolRow>,
}

#[derive(Debug, Clone, Serialize)]
pub struct CountRow {
    pub name: String,
    pub count: u64,
}

#[derive(Debug, Clone, Serialize)]
pub struct ToolRow {
    pub tool_name: String,
    pub call_count: u64,
    pub error_count: u64,
    pub avg_duration_ms: f64,
    pub p95_duration_ms: u32,
    pub avg_result_size: f64,
}

#[derive(Debug, Clone, Serialize)]
pub struct ScorecardAxis {
    pub axis: &'static str,
    pub status: String,
    pub evidence: String,
    pub next_probe: &'static str,
}

#[derive(Debug, Clone, Serialize)]
pub struct ProposedImprovement {
    pub id: &'static str,
    pub title: &'static str,
    pub rationale: String,
    pub next_action: &'static str,
    pub runtime_influence_allowed: bool,
}

#[derive(Debug, Clone, Serialize)]
pub struct WorkflowFeedbackShadowScoreReport {
    pub schema: &'static str,
    pub read_only: bool,
    pub boundary: WorkflowFeedbackBoundary,
    pub candidate_count: usize,
    pub scenarios: Vec<String>,
    pub rankings: Vec<ShadowScenarioRanking>,
    pub non_goals: Vec<&'static str>,
}

#[derive(Debug, Clone, Serialize)]
pub struct ShadowScenarioRanking {
    pub scenario: String,
    pub ranked_candidates: Vec<ShadowCandidateScore>,
}

#[derive(Debug, Clone, Serialize)]
pub struct ShadowCandidateScore {
    pub experience_id: String,
    pub lane: Option<String>,
    pub source_path: Option<String>,
    pub shadow_score: u32,
    pub readiness_score: u32,
    pub relevance_score: u32,
    pub verdict: &'static str,
    pub matched_terms: Vec<String>,
    pub lesson: Option<String>,
    pub falsifier: Option<String>,
    pub runtime_influence_allowed: bool,
}

#[derive(Debug, Clone)]
pub struct WorkflowFeedbackPromotionGateOptions {
    pub owner_approval_refs: Vec<String>,
    pub rollback_refs: Vec<String>,
    pub behavior_lift_refs: Vec<String>,
    pub min_shadow_reports: usize,
    pub min_scenarios: usize,
    pub min_strong_scenarios: usize,
    pub min_top_shadow_score: u32,
}

impl Default for WorkflowFeedbackPromotionGateOptions {
    fn default() -> Self {
        Self {
            owner_approval_refs: Vec::new(),
            rollback_refs: Vec::new(),
            behavior_lift_refs: Vec::new(),
            min_shadow_reports: 2,
            min_scenarios: 2,
            min_strong_scenarios: 2,
            min_top_shadow_score: 65,
        }
    }
}

#[derive(Debug, Clone, Serialize)]
pub struct WorkflowFeedbackPromotionGateReport {
    pub schema: &'static str,
    pub read_only: bool,
    pub boundary: WorkflowFeedbackBoundary,
    pub gate_verdict: &'static str,
    pub ready_for_owner_review: bool,
    pub advisory_promotion_ready: bool,
    pub evidence: PromotionGateEvidence,
    pub checks: Vec<PromotionGateCheck>,
    pub scenario_evidence: Vec<PromotionGateScenarioEvidence>,
    pub recommended_next_actions: Vec<&'static str>,
    pub non_goals: Vec<&'static str>,
}

#[derive(Debug, Clone, Serialize)]
pub struct PromotionGateEvidence {
    pub shadow_report_count: usize,
    pub scenario_count: usize,
    pub strong_shadow_match_count: usize,
    pub unsafe_shadow_report_count: usize,
    pub min_required_shadow_reports: usize,
    pub min_required_scenarios: usize,
    pub min_required_strong_scenarios: usize,
    pub min_required_top_shadow_score: u32,
    pub top_experience_counts: Vec<PromotionGateExperienceCount>,
    pub owner_approval_refs: Vec<String>,
    pub rollback_refs: Vec<String>,
    pub behavior_lift_refs: Vec<String>,
}

#[derive(Debug, Clone, Serialize)]
pub struct PromotionGateCheck {
    pub id: &'static str,
    pub passed: bool,
    pub evidence: String,
    pub required: String,
}

#[derive(Debug, Clone, Serialize)]
pub struct PromotionGateScenarioEvidence {
    pub source_path: Option<String>,
    pub scenario: String,
    pub top_experience_id: String,
    pub shadow_score: u32,
    pub verdict: String,
    pub runtime_influence_allowed: bool,
    pub strong_match: bool,
}

#[derive(Debug, Clone, Serialize)]
pub struct PromotionGateExperienceCount {
    pub experience_id: String,
    pub top_rank_count: usize,
}

#[derive(Debug, Clone)]
pub struct WorkflowFeedbackLiftEvidenceOptions {
    pub baseline_correct: Option<u32>,
    pub baseline_total: Option<u32>,
    pub min_accuracy: f64,
    pub min_lift: f64,
}

impl Default for WorkflowFeedbackLiftEvidenceOptions {
    fn default() -> Self {
        Self {
            baseline_correct: None,
            baseline_total: None,
            min_accuracy: 0.75,
            min_lift: 0.10,
        }
    }
}

#[derive(Debug, Clone, Serialize)]
pub struct WorkflowFeedbackLiftEvidenceReport {
    pub schema: &'static str,
    pub read_only: bool,
    pub boundary: WorkflowFeedbackBoundary,
    pub lift_verdict: &'static str,
    pub metric_anchor_ref: String,
    pub measured_against_baseline: bool,
    pub evidence: LiftEvidenceSummary,
    pub checks: Vec<LiftEvidenceCheck>,
    pub scenario_observations: Vec<LiftScenarioObservation>,
    pub recommended_next_actions: Vec<&'static str>,
    pub non_goals: Vec<&'static str>,
}

#[derive(Debug, Clone, Serialize)]
pub struct LiftEvidenceSummary {
    pub scenario_fixture_path: Option<String>,
    pub shadow_report_count: usize,
    pub scenario_case_count: usize,
    pub observation_count: usize,
    pub expected_top_match_count: usize,
    pub missing_observation_count: usize,
    pub unsafe_shadow_report_count: usize,
    pub top1_accuracy: f64,
    pub baseline_correct: Option<u32>,
    pub baseline_total: Option<u32>,
    pub baseline_accuracy: Option<f64>,
    pub absolute_lift: Option<f64>,
    pub min_required_accuracy: f64,
    pub min_required_lift: f64,
}

#[derive(Debug, Clone, Serialize)]
pub struct LiftEvidenceCheck {
    pub id: &'static str,
    pub passed: bool,
    pub evidence: String,
    pub required: String,
}

#[derive(Debug, Clone, Serialize)]
pub struct LiftScenarioObservation {
    pub source_path: Option<String>,
    pub scenario_id: String,
    pub scenario: String,
    pub expected_top_experience_id: String,
    pub observed_top_experience_id: Option<String>,
    pub shadow_score: Option<u32>,
    pub verdict: Option<String>,
    pub matched_expected_top: bool,
    pub boundary_safe: bool,
    pub runtime_influence_allowed: bool,
}

pub async fn build_report(
    store: &dyn StateStore,
    options: WorkflowFeedbackReportOptions,
) -> Result<WorkflowFeedbackReport> {
    let memory_stats = store.memory_stats().await?;
    let kind_counts = store.memory_kind_counts().await?;
    let scope_counts = store.memory_scope_counts().await?;
    let backend_counts = store.memory_embedding_backend_counts().await?;
    let tool_stats = store.mcp_tool_call_stats(options.window_secs, 200).await?;

    let active_rows = memory_stats
        .counts_by_status
        .get("active")
        .copied()
        .unwrap_or(0);
    let feedback_rows = count_named(&kind_counts, "feedback");
    let feedback_fraction = fraction(feedback_rows, active_rows);

    let top_kinds = count_rows(kind_counts.iter().take(8));
    let top_scopes = count_rows(scope_counts.iter().take(8));
    let embedding_backends = count_rows(backend_counts.iter().take(8));

    let memory = MemoryEvidence {
        active_rows,
        feedback_rows,
        feedback_fraction,
        edge_count: memory_stats.edge_count,
        distinct_kinds: kind_counts.len(),
        distinct_scopes: scope_counts.len(),
        distinct_embedding_backends: backend_counts.len(),
        top_kinds,
        top_scopes,
        embedding_backends,
    };

    let total_calls: u64 = tool_stats.iter().map(|row| row.call_count).sum();
    let total_errors: u64 = tool_stats.iter().map(|row| row.error_count).sum();
    let top_tools = options.top_tools.clamp(1, 50) as usize;
    let hot_tools = tool_stats.iter().take(top_tools).map(tool_row).collect();
    let tool_telemetry = ToolTelemetryEvidence {
        window_secs: options.window_secs.max(0),
        tools_observed: tool_stats.len(),
        total_calls_in_top_window: total_calls,
        total_errors_in_top_window: total_errors,
        error_rate_in_top_window: fraction(total_errors, total_calls),
        hot_tools,
    };

    let evidence = WorkflowFeedbackEvidence {
        memory,
        tool_telemetry,
    };
    let scorecard = build_scorecard(&evidence);
    let proposed_improvements = build_improvements(&evidence);
    let experience_object_fixture =
        build_experience_fixture(&evidence, &scorecard, &proposed_improvements, options.scope);

    Ok(WorkflowFeedbackReport {
        schema: WORKFLOW_FEEDBACK_REPORT_SCHEMA,
        read_only: true,
        boundary: WorkflowFeedbackBoundary {
            writes_memory: false,
            mutates_runtime_policy: false,
            changes_retrieval_order: false,
            runtime_influence_allowed: false,
            owner_gated_runtime_influence: true,
        },
        source_anchors: vec![
            "docs/design/WORKFLOW_FEEDBACK_LOOP_RESEARCH_2026_06_30.md".to_string(),
            "memory:workflow_feedback_loop_research_20260630".to_string(),
            "forum:#108/#2658".to_string(),
        ],
        evidence,
        scorecard,
        proposed_improvements,
        experience_object_fixture,
    })
}

impl WorkflowFeedbackReport {
    pub fn to_json_value(&self) -> Value {
        serde_json::to_value(self).unwrap_or_else(|_| {
            json!({
                "schema": WORKFLOW_FEEDBACK_REPORT_SCHEMA,
                "read_only": true,
                "serialization_error": true
            })
        })
    }

    pub fn render_markdown(&self) -> String {
        let mut out = String::new();
        out.push_str("# Workflow Feedback Report\n");
        out.push_str(&format!("schema: {}\n", self.schema));
        out.push_str("mode: read-only report; no memory writes, no retrieval change, no runtime policy mutation\n\n");

        out.push_str("## Evidence\n");
        out.push_str(&format!(
            "- memory: active_rows={} feedback_rows={} ({:.1}%) edges={} distinct_kinds={} distinct_scopes={} embedding_backends={}\n",
            self.evidence.memory.active_rows,
            self.evidence.memory.feedback_rows,
            self.evidence.memory.feedback_fraction * 100.0,
            self.evidence.memory.edge_count,
            self.evidence.memory.distinct_kinds,
            self.evidence.memory.distinct_scopes,
            self.evidence.memory.distinct_embedding_backends
        ));
        out.push_str(&format!(
            "- tool telemetry: window_secs={} tools_observed={} calls={} errors={} ({:.1}%)\n\n",
            self.evidence.tool_telemetry.window_secs,
            self.evidence.tool_telemetry.tools_observed,
            self.evidence.tool_telemetry.total_calls_in_top_window,
            self.evidence.tool_telemetry.total_errors_in_top_window,
            self.evidence.tool_telemetry.error_rate_in_top_window * 100.0
        ));

        out.push_str("## Scorecard\n");
        out.push_str("| Axis | Status | Evidence | Next probe |\n");
        out.push_str("| --- | --- | --- | --- |\n");
        for axis in &self.scorecard {
            out.push_str(&format!(
                "| {} | {} | {} | {} |\n",
                axis.axis,
                pipe_safe(&axis.status),
                pipe_safe(&axis.evidence),
                axis.next_probe
            ));
        }
        out.push('\n');

        out.push_str("## Proposed Improvements\n");
        for improvement in &self.proposed_improvements {
            out.push_str(&format!(
                "- {}: {}. {} Next: {} Runtime influence: {}.\n",
                improvement.id,
                improvement.title,
                improvement.rationale,
                improvement.next_action,
                if improvement.runtime_influence_allowed {
                    "allowed"
                } else {
                    "blocked"
                }
            ));
        }
        out.push('\n');

        out.push_str("## Hot Tools\n");
        if self.evidence.tool_telemetry.hot_tools.is_empty() {
            out.push_str("- no MCP tool-call telemetry in the selected window\n");
        } else {
            for row in &self.evidence.tool_telemetry.hot_tools {
                out.push_str(&format!(
                    "- {}: calls={} errors={} avg_ms={:.1} p95_ms={} avg_result_size={:.1}\n",
                    row.tool_name,
                    row.call_count,
                    row.error_count,
                    row.avg_duration_ms,
                    row.p95_duration_ms,
                    row.avg_result_size
                ));
            }
        }
        out.push('\n');

        out.push_str("## Experience Object v0 Fixture\n");
        out.push_str("```json\n");
        out.push_str(
            &serde_json::to_string_pretty(&self.experience_object_fixture)
                .unwrap_or_else(|_| "{}".to_string()),
        );
        out.push_str("\n```\n");
        out
    }
}

impl WorkflowFeedbackShadowScoreReport {
    pub fn to_json_value(&self) -> Value {
        serde_json::to_value(self).unwrap_or_else(|_| {
            json!({
                "schema": WORKFLOW_FEEDBACK_SHADOW_SCORE_SCHEMA,
                "read_only": true,
                "serialization_error": true
            })
        })
    }

    pub fn render_markdown(&self) -> String {
        let mut out = String::new();
        out.push_str("# Workflow Feedback Shadow Score\n");
        out.push_str(&format!("schema: {}\n", self.schema));
        out.push_str("mode: read-only shadow scoring; no memory writes, no retrieval change, no tool-routing change, no runtime policy mutation\n\n");

        for ranking in &self.rankings {
            out.push_str("## Scenario\n");
            out.push_str(&format!("{}\n\n", ranking.scenario));
            out.push_str("| Rank | Experience | Shadow | Readiness | Relevance | Verdict | Matched terms |\n");
            out.push_str("| ---: | --- | ---: | ---: | ---: | --- | --- |\n");
            for (idx, candidate) in ranking.ranked_candidates.iter().enumerate() {
                out.push_str(&format!(
                    "| {} | {} | {} | {} | {} | {} | {} |\n",
                    idx + 1,
                    pipe_safe(&candidate.experience_id),
                    candidate.shadow_score,
                    candidate.readiness_score,
                    candidate.relevance_score,
                    candidate.verdict,
                    pipe_safe(&candidate.matched_terms.join(", "))
                ));
            }
            out.push('\n');
        }

        out.push_str("## Non-goals\n");
        for non_goal in &self.non_goals {
            out.push_str(&format!("- {non_goal}\n"));
        }
        out
    }
}

impl WorkflowFeedbackPromotionGateReport {
    pub fn to_json_value(&self) -> Value {
        serde_json::to_value(self).unwrap_or_else(|_| {
            json!({
                "schema": WORKFLOW_FEEDBACK_PROMOTION_GATE_SCHEMA,
                "read_only": true,
                "serialization_error": true
            })
        })
    }

    pub fn render_markdown(&self) -> String {
        let mut out = String::new();
        out.push_str("# Workflow Feedback Promotion Gate\n");
        out.push_str(&format!("schema: {}\n", self.schema));
        out.push_str(&format!("verdict: {}\n", self.gate_verdict));
        out.push_str("mode: read-only promotion review packet; no memory writes, no retrieval change, no tool-routing change, no runtime policy mutation\n\n");

        out.push_str("## Evidence\n");
        out.push_str(&format!(
            "- shadow reports: {} (required {})\n",
            self.evidence.shadow_report_count, self.evidence.min_required_shadow_reports
        ));
        out.push_str(&format!(
            "- scenarios: {} (required {})\n",
            self.evidence.scenario_count, self.evidence.min_required_scenarios
        ));
        out.push_str(&format!(
            "- strong shadow matches: {} (required {}, min top score {})\n",
            self.evidence.strong_shadow_match_count,
            self.evidence.min_required_strong_scenarios,
            self.evidence.min_required_top_shadow_score
        ));
        out.push_str(&format!(
            "- unsafe shadow reports: {}\n\n",
            self.evidence.unsafe_shadow_report_count
        ));

        out.push_str("## Checks\n");
        out.push_str("| Check | Status | Evidence | Required |\n");
        out.push_str("| --- | --- | --- | --- |\n");
        for check in &self.checks {
            out.push_str(&format!(
                "| {} | {} | {} | {} |\n",
                check.id,
                if check.passed { "pass" } else { "blocked" },
                pipe_safe(&check.evidence),
                pipe_safe(&check.required)
            ));
        }
        out.push('\n');

        out.push_str("## Top Experience Counts\n");
        if self.evidence.top_experience_counts.is_empty() {
            out.push_str("- no top-ranked experience evidence\n");
        } else {
            for count in &self.evidence.top_experience_counts {
                out.push_str(&format!(
                    "- {}: {} top-ranked scenario(s)\n",
                    count.experience_id, count.top_rank_count
                ));
            }
        }
        out.push('\n');

        out.push_str("## Scenario Evidence\n");
        out.push_str("| Scenario | Top Experience | Score | Verdict | Strong |\n");
        out.push_str("| --- | --- | ---: | --- | --- |\n");
        for scenario in &self.scenario_evidence {
            out.push_str(&format!(
                "| {} | {} | {} | {} | {} |\n",
                pipe_safe(&scenario.scenario),
                pipe_safe(&scenario.top_experience_id),
                scenario.shadow_score,
                pipe_safe(&scenario.verdict),
                scenario.strong_match
            ));
        }
        out.push('\n');

        out.push_str("## Recommended Next Actions\n");
        for action in &self.recommended_next_actions {
            out.push_str(&format!("- {action}\n"));
        }
        out.push('\n');

        out.push_str("## Non-goals\n");
        for non_goal in &self.non_goals {
            out.push_str(&format!("- {non_goal}\n"));
        }
        out
    }
}

impl WorkflowFeedbackLiftEvidenceReport {
    pub fn to_json_value(&self) -> Value {
        serde_json::to_value(self).unwrap_or_else(|_| {
            json!({
                "schema": WORKFLOW_FEEDBACK_LIFT_EVIDENCE_SCHEMA,
                "read_only": true,
                "serialization_error": true
            })
        })
    }

    pub fn render_markdown(&self) -> String {
        let mut out = String::new();
        out.push_str("# Workflow Feedback Lift Evidence\n");
        out.push_str(&format!("schema: {}\n", self.schema));
        out.push_str(&format!("verdict: {}\n", self.lift_verdict));
        out.push_str(&format!("metric_anchor_ref: {}\n", self.metric_anchor_ref));
        out.push_str("mode: read-only metric anchor; no memory writes, no retrieval change, no tool-routing change, no runtime policy mutation\n\n");

        out.push_str("## Evidence\n");
        out.push_str(&format!(
            "- shadow reports: {}\n",
            self.evidence.shadow_report_count
        ));
        out.push_str(&format!(
            "- scenario cases: {}\n",
            self.evidence.scenario_case_count
        ));
        out.push_str(&format!(
            "- observations: {} missing={}\n",
            self.evidence.observation_count, self.evidence.missing_observation_count
        ));
        out.push_str(&format!(
            "- expected top matches: {} ({:.1}%)\n",
            self.evidence.expected_top_match_count,
            self.evidence.top1_accuracy * 100.0
        ));
        if let Some(baseline_accuracy) = self.evidence.baseline_accuracy {
            out.push_str(&format!(
                "- baseline: {}/{} ({:.1}%)\n",
                self.evidence.baseline_correct.unwrap_or(0),
                self.evidence.baseline_total.unwrap_or(0),
                baseline_accuracy * 100.0
            ));
        } else {
            out.push_str("- baseline: not supplied\n");
        }
        if let Some(lift) = self.evidence.absolute_lift {
            out.push_str(&format!("- absolute lift: {:.1}%\n", lift * 100.0));
        }
        out.push('\n');

        out.push_str("## Checks\n");
        out.push_str("| Check | Status | Evidence | Required |\n");
        out.push_str("| --- | --- | --- | --- |\n");
        for check in &self.checks {
            out.push_str(&format!(
                "| {} | {} | {} | {} |\n",
                check.id,
                if check.passed { "pass" } else { "blocked" },
                pipe_safe(&check.evidence),
                pipe_safe(&check.required)
            ));
        }
        out.push('\n');

        out.push_str("## Scenario Observations\n");
        out.push_str("| Scenario | Expected | Observed | Score | Match | Safe |\n");
        out.push_str("| --- | --- | --- | ---: | --- | --- |\n");
        for observation in &self.scenario_observations {
            out.push_str(&format!(
                "| {} | {} | {} | {} | {} | {} |\n",
                pipe_safe(&observation.scenario_id),
                pipe_safe(&observation.expected_top_experience_id),
                pipe_safe(
                    observation
                        .observed_top_experience_id
                        .as_deref()
                        .unwrap_or("<missing>")
                ),
                observation
                    .shadow_score
                    .map(|score| score.to_string())
                    .unwrap_or_else(|| "-".to_string()),
                observation.matched_expected_top,
                observation.boundary_safe
            ));
        }
        out.push('\n');

        out.push_str("## Recommended Next Actions\n");
        for action in &self.recommended_next_actions {
            out.push_str(&format!("- {action}\n"));
        }
        out.push('\n');

        out.push_str("## Non-goals\n");
        for non_goal in &self.non_goals {
            out.push_str(&format!("- {non_goal}\n"));
        }
        out
    }
}

pub fn build_shadow_score_report_from_paths(
    fixture_paths: &[PathBuf],
    scenarios: Vec<String>,
) -> Result<WorkflowFeedbackShadowScoreReport> {
    let mut experiences = Vec::new();
    for path in fixture_paths {
        let raw = std::fs::read_to_string(path)
            .with_context(|| format!("reading experience fixture {}", path.display()))?;
        let value: Value = serde_json::from_str(&raw)
            .with_context(|| format!("parsing experience fixture {}", path.display()))?;
        experiences.push(ExperienceCandidate::from_value(
            value,
            Some(path.display().to_string()),
        )?);
    }
    build_shadow_score_report(experiences, scenarios)
}

pub fn build_promotion_gate_report_from_paths(
    shadow_score_paths: &[PathBuf],
    options: WorkflowFeedbackPromotionGateOptions,
) -> Result<WorkflowFeedbackPromotionGateReport> {
    if shadow_score_paths.is_empty() {
        bail!("at least one shadow score report is required");
    }
    let mut shadow_reports = Vec::new();
    for path in shadow_score_paths {
        let raw = std::fs::read_to_string(path)
            .with_context(|| format!("reading shadow score report {}", path.display()))?;
        let value: Value = serde_json::from_str(&raw)
            .with_context(|| format!("parsing shadow score report {}", path.display()))?;
        shadow_reports.push(ShadowScoreReportEvidence::from_value(
            value,
            Some(path.display().to_string()),
        )?);
    }
    build_promotion_gate_report(shadow_reports, options)
}

pub fn build_lift_evidence_report_from_paths(
    scenario_fixture_path: &PathBuf,
    shadow_score_paths: &[PathBuf],
    options: WorkflowFeedbackLiftEvidenceOptions,
) -> Result<WorkflowFeedbackLiftEvidenceReport> {
    if shadow_score_paths.is_empty() {
        bail!("at least one shadow score report is required");
    }
    let raw = std::fs::read_to_string(scenario_fixture_path).with_context(|| {
        format!(
            "reading scenario fixture {}",
            scenario_fixture_path.display()
        )
    })?;
    let scenario_value: Value = serde_json::from_str(&raw).with_context(|| {
        format!(
            "parsing scenario fixture {}",
            scenario_fixture_path.display()
        )
    })?;
    let scenario_fixture = ShadowScoreScenarioFixture::from_value(
        scenario_value,
        Some(scenario_fixture_path.display().to_string()),
    )?;

    let mut shadow_reports = Vec::new();
    for path in shadow_score_paths {
        let raw = std::fs::read_to_string(path)
            .with_context(|| format!("reading shadow score report {}", path.display()))?;
        let value: Value = serde_json::from_str(&raw)
            .with_context(|| format!("parsing shadow score report {}", path.display()))?;
        shadow_reports.push(ShadowScoreReportEvidence::from_value(
            value,
            Some(path.display().to_string()),
        )?);
    }

    build_lift_evidence_report(scenario_fixture, shadow_reports, options)
}

fn build_shadow_score_report(
    experiences: Vec<ExperienceCandidate>,
    scenarios: Vec<String>,
) -> Result<WorkflowFeedbackShadowScoreReport> {
    if experiences.is_empty() {
        bail!("at least one experience fixture is required");
    }
    let scenarios = if scenarios.is_empty() {
        vec!["Future Agent-Bridge session needs a reusable workflow lesson before changing runtime, retrieval, or tool policy.".to_string()]
    } else {
        scenarios
    };
    let rankings = scenarios
        .iter()
        .map(|scenario| score_scenario(scenario, &experiences))
        .collect::<Vec<_>>();
    Ok(WorkflowFeedbackShadowScoreReport {
        schema: WORKFLOW_FEEDBACK_SHADOW_SCORE_SCHEMA,
        read_only: true,
        boundary: WorkflowFeedbackBoundary {
            writes_memory: false,
            mutates_runtime_policy: false,
            changes_retrieval_order: false,
            runtime_influence_allowed: false,
            owner_gated_runtime_influence: true,
        },
        candidate_count: experiences.len(),
        scenarios,
        rankings,
        non_goals: vec![
            "Does not call memory_search or alter bootstrap.",
            "Does not change retrieval ranking, tool routing, or runtime policy.",
            "Does not claim causal behavior lift; it only ranks fixture/lesson fit for later review.",
            "Does not promote any lesson without owner-gated evidence and rollback path.",
        ],
    })
}

fn build_lift_evidence_report(
    scenario_fixture: ShadowScoreScenarioFixture,
    shadow_reports: Vec<ShadowScoreReportEvidence>,
    options: WorkflowFeedbackLiftEvidenceOptions,
) -> Result<WorkflowFeedbackLiftEvidenceReport> {
    if scenario_fixture.cases.is_empty() {
        bail!("at least one scenario case is required");
    }
    if shadow_reports.is_empty() {
        bail!("at least one shadow score report is required");
    }

    let min_accuracy = options.min_accuracy.clamp(0.0, 1.0);
    let min_lift = options.min_lift.clamp(0.0, 1.0);
    let baseline_total = options.baseline_total.filter(|total| *total > 0);
    let baseline_correct =
        baseline_total.map(|total| options.baseline_correct.unwrap_or(0).min(total));
    let baseline_accuracy = match (baseline_correct, baseline_total) {
        (Some(correct), Some(total)) if total > 0 => Some(correct as f64 / total as f64),
        _ => None,
    };

    let mut observations = Vec::new();
    let mut unsafe_shadow_report_count = 0_usize;
    for report in &shadow_reports {
        if !report.boundary_safe {
            unsafe_shadow_report_count += 1;
        }
        for case in &scenario_fixture.cases {
            let top = report
                .top_candidates
                .iter()
                .find(|candidate| candidate.scenario == case.scenario);
            let matched_expected_top = top
                .map(|candidate| candidate.experience_id == case.expected_top_experience_id)
                .unwrap_or(false);
            observations.push(LiftScenarioObservation {
                source_path: report.source_path.clone(),
                scenario_id: case.scenario_id.clone(),
                scenario: case.scenario.clone(),
                expected_top_experience_id: case.expected_top_experience_id.clone(),
                observed_top_experience_id: top.map(|candidate| candidate.experience_id.clone()),
                shadow_score: top.map(|candidate| candidate.shadow_score),
                verdict: top.map(|candidate| candidate.verdict.clone()),
                matched_expected_top,
                boundary_safe: report.boundary_safe,
                runtime_influence_allowed: top
                    .map(|candidate| candidate.runtime_influence_allowed)
                    .unwrap_or(false),
            });
        }
    }

    let observation_count = observations
        .iter()
        .filter(|observation| observation.observed_top_experience_id.is_some())
        .count();
    let missing_observation_count = observations.len().saturating_sub(observation_count);
    let expected_top_match_count = observations
        .iter()
        .filter(|observation| observation.matched_expected_top)
        .count();
    let top1_accuracy = if observation_count == 0 {
        0.0
    } else {
        expected_top_match_count as f64 / observation_count as f64
    };
    let absolute_lift = baseline_accuracy.map(|baseline| top1_accuracy - baseline);
    let safe_boundaries = unsafe_shadow_report_count == 0
        && observations
            .iter()
            .all(|observation| !observation.runtime_influence_allowed);
    let observations_complete = missing_observation_count == 0
        && observation_count == scenario_fixture.cases.len() * shadow_reports.len();
    let accuracy_passed = top1_accuracy >= min_accuracy;
    let baseline_supplied = baseline_accuracy.is_some();
    let lift_passed = absolute_lift.map(|lift| lift >= min_lift).unwrap_or(false);

    let lift_verdict = if !safe_boundaries {
        "blocked_shadow_boundary_violation"
    } else if !observations_complete {
        "blocked_incomplete_observations"
    } else if !accuracy_passed {
        "blocked_expected_top_accuracy"
    } else if !baseline_supplied {
        "metric_anchor_without_baseline"
    } else if !lift_passed {
        "blocked_no_positive_lift"
    } else {
        "measured_lift_anchor"
    };

    let checks = vec![
        LiftEvidenceCheck {
            id: "shadow_boundaries_safe",
            passed: safe_boundaries,
            evidence: format!(
                "{unsafe_shadow_report_count} unsafe report(s); {} top candidate(s) allow runtime influence",
                observations
                    .iter()
                    .filter(|observation| observation.runtime_influence_allowed)
                    .count()
            ),
            required:
                "all shadow reports read_only=true and all observed top candidates keep runtime influence disabled"
                    .to_string(),
        },
        LiftEvidenceCheck {
            id: "scenario_observations_complete",
            passed: observations_complete,
            evidence: format!(
                "{observation_count} observed top candidate(s), {missing_observation_count} missing"
            ),
            required: format!(
                "{} scenario case(s) across {} shadow report(s)",
                scenario_fixture.cases.len(),
                shadow_reports.len()
            ),
        },
        LiftEvidenceCheck {
            id: "expected_top_accuracy",
            passed: accuracy_passed,
            evidence: format!(
                "{} / {} observed top candidate(s) matched expected top ({:.1}%)",
                expected_top_match_count,
                observation_count,
                top1_accuracy * 100.0
            ),
            required: format!("top-1 expected match accuracy >= {:.1}%", min_accuracy * 100.0),
        },
        LiftEvidenceCheck {
            id: "baseline_supplied",
            passed: baseline_supplied,
            evidence: match (baseline_correct, baseline_total) {
                (Some(correct), Some(total)) => format!("{correct} / {total} baseline correct"),
                _ => "no baseline correct/total supplied".to_string(),
            },
            required: "baseline-correct and baseline-total for measured lift".to_string(),
        },
        LiftEvidenceCheck {
            id: "positive_lift",
            passed: lift_passed,
            evidence: absolute_lift
                .map(|lift| format!("{:.1}% absolute lift over baseline", lift * 100.0))
                .unwrap_or_else(|| "no baseline supplied; lift not measured".to_string()),
            required: format!("absolute lift >= {:.1}%", min_lift * 100.0),
        },
    ];

    let evidence = LiftEvidenceSummary {
        scenario_fixture_path: scenario_fixture.source_path.clone(),
        shadow_report_count: shadow_reports.len(),
        scenario_case_count: scenario_fixture.cases.len(),
        observation_count,
        expected_top_match_count,
        missing_observation_count,
        unsafe_shadow_report_count,
        top1_accuracy,
        baseline_correct,
        baseline_total,
        baseline_accuracy,
        absolute_lift,
        min_required_accuracy: min_accuracy,
        min_required_lift: min_lift,
    };
    let metric_anchor_ref = lift_metric_anchor_ref(lift_verdict, &evidence);

    Ok(WorkflowFeedbackLiftEvidenceReport {
        schema: WORKFLOW_FEEDBACK_LIFT_EVIDENCE_SCHEMA,
        read_only: true,
        boundary: WorkflowFeedbackBoundary {
            writes_memory: false,
            mutates_runtime_policy: false,
            changes_retrieval_order: false,
            runtime_influence_allowed: false,
            owner_gated_runtime_influence: true,
        },
        lift_verdict,
        metric_anchor_ref,
        measured_against_baseline: baseline_supplied,
        evidence,
        checks,
        scenario_observations: observations,
        recommended_next_actions: lift_recommended_next_actions(lift_verdict),
        non_goals: vec![
            "Does not promote memories, runbooks, skills, retrieval rules, or tool routing.",
            "Does not mutate runtime policy, prompts, profiles, bootstrap, or memory.",
            "Does not infer owner approval or rollback evidence.",
            "Does not claim real runtime behavior lift unless a baseline correct/total is supplied.",
        ],
    })
}

fn build_promotion_gate_report(
    shadow_reports: Vec<ShadowScoreReportEvidence>,
    options: WorkflowFeedbackPromotionGateOptions,
) -> Result<WorkflowFeedbackPromotionGateReport> {
    if shadow_reports.is_empty() {
        bail!("at least one shadow score report is required");
    }

    let min_shadow_reports = options.min_shadow_reports.max(1);
    let min_scenarios = options.min_scenarios.max(1);
    let min_strong_scenarios = options.min_strong_scenarios.max(1);
    let min_top_shadow_score = options.min_top_shadow_score.min(100);
    let owner_approval_refs = clean_refs(options.owner_approval_refs);
    let rollback_refs = clean_refs(options.rollback_refs);
    let behavior_lift_refs = clean_refs(options.behavior_lift_refs);

    let mut scenario_evidence = Vec::new();
    let mut top_counts = BTreeMap::<String, usize>::new();
    let mut unsafe_shadow_report_count = 0_usize;

    for report in &shadow_reports {
        if !report.boundary_safe {
            unsafe_shadow_report_count += 1;
        }
        for top in &report.top_candidates {
            let strong_match = !top.runtime_influence_allowed
                && top.shadow_score >= min_top_shadow_score
                && top.verdict == "likely_helpful_shadow_candidate";
            *top_counts.entry(top.experience_id.clone()).or_insert(0) += 1;
            scenario_evidence.push(PromotionGateScenarioEvidence {
                source_path: report.source_path.clone(),
                scenario: top.scenario.clone(),
                top_experience_id: top.experience_id.clone(),
                shadow_score: top.shadow_score,
                verdict: top.verdict.clone(),
                runtime_influence_allowed: top.runtime_influence_allowed,
                strong_match,
            });
        }
    }

    let shadow_report_count = shadow_reports.len();
    let scenario_count = scenario_evidence.len();
    let strong_shadow_match_count = scenario_evidence
        .iter()
        .filter(|scenario| scenario.strong_match)
        .count();
    let top_experience_counts = top_experience_counts(top_counts);

    let safe_boundaries = unsafe_shadow_report_count == 0
        && scenario_evidence
            .iter()
            .all(|scenario| !scenario.runtime_influence_allowed);
    let repeated_shadow_reports = shadow_report_count >= min_shadow_reports;
    let scenario_coverage = scenario_count >= min_scenarios;
    let strong_shadow_matches = strong_shadow_match_count >= min_strong_scenarios;
    let behavior_lift_anchor = !behavior_lift_refs.is_empty();
    let rollback_evidence = !rollback_refs.is_empty();
    let owner_approval = !owner_approval_refs.is_empty();

    let checks = vec![
        PromotionGateCheck {
            id: "shadow_boundaries_safe",
            passed: safe_boundaries,
            evidence: format!(
                "{unsafe_shadow_report_count} unsafe report(s); {} top candidate(s) allow runtime influence",
                scenario_evidence
                    .iter()
                    .filter(|scenario| scenario.runtime_influence_allowed)
                    .count()
            ),
            required:
                "all shadow reports read_only=true and all boundary/runtime influence flags safe"
                    .to_string(),
        },
        PromotionGateCheck {
            id: "repeated_shadow_reports",
            passed: repeated_shadow_reports,
            evidence: format!("{shadow_report_count} shadow report(s) supplied"),
            required: format!("at least {min_shadow_reports} shadow report(s)"),
        },
        PromotionGateCheck {
            id: "scenario_coverage",
            passed: scenario_coverage,
            evidence: format!("{scenario_count} scenario(s) scored"),
            required: format!("at least {min_scenarios} held-out scenario(s)"),
        },
        PromotionGateCheck {
            id: "strong_shadow_matches",
            passed: strong_shadow_matches,
            evidence: format!(
                "{strong_shadow_match_count} strong top match(es) at score >= {min_top_shadow_score}"
            ),
            required: format!("at least {min_strong_scenarios} likely_helpful top candidate(s)"),
        },
        PromotionGateCheck {
            id: "behavior_lift_anchor",
            passed: behavior_lift_anchor,
            evidence: format!("{} behavior-lift ref(s)", behavior_lift_refs.len()),
            required: "measured behavior-lift evidence or falsifiable metric anchor".to_string(),
        },
        PromotionGateCheck {
            id: "rollback_evidence",
            passed: rollback_evidence,
            evidence: format!("{} rollback ref(s)", rollback_refs.len()),
            required: "explicit rollback path or revert handle".to_string(),
        },
        PromotionGateCheck {
            id: "owner_approval",
            passed: owner_approval,
            evidence: format!("{} owner approval ref(s)", owner_approval_refs.len()),
            required: "explicit owner approval reference".to_string(),
        },
    ];

    let shadow_evidence_passed =
        safe_boundaries && repeated_shadow_reports && scenario_coverage && strong_shadow_matches;
    let ready_for_owner_review =
        shadow_evidence_passed && behavior_lift_anchor && rollback_evidence;
    let advisory_promotion_ready = ready_for_owner_review && owner_approval;
    let gate_verdict = if !safe_boundaries {
        "blocked_shadow_boundary_violation"
    } else if !repeated_shadow_reports {
        "blocked_insufficient_shadow_runs"
    } else if !scenario_coverage || !strong_shadow_matches {
        "blocked_insufficient_shadow_evidence"
    } else if !behavior_lift_anchor {
        "blocked_behavior_lift_anchor_required"
    } else if !rollback_evidence {
        "blocked_rollback_evidence_required"
    } else if !owner_approval {
        "ready_for_owner_review"
    } else {
        "owner_review_packet_complete"
    };

    Ok(WorkflowFeedbackPromotionGateReport {
        schema: WORKFLOW_FEEDBACK_PROMOTION_GATE_SCHEMA,
        read_only: true,
        boundary: WorkflowFeedbackBoundary {
            writes_memory: false,
            mutates_runtime_policy: false,
            changes_retrieval_order: false,
            runtime_influence_allowed: false,
            owner_gated_runtime_influence: true,
        },
        gate_verdict,
        ready_for_owner_review,
        advisory_promotion_ready,
        evidence: PromotionGateEvidence {
            shadow_report_count,
            scenario_count,
            strong_shadow_match_count,
            unsafe_shadow_report_count,
            min_required_shadow_reports: min_shadow_reports,
            min_required_scenarios: min_scenarios,
            min_required_strong_scenarios: min_strong_scenarios,
            min_required_top_shadow_score: min_top_shadow_score,
            top_experience_counts,
            owner_approval_refs,
            rollback_refs,
            behavior_lift_refs,
        },
        checks,
        scenario_evidence,
        recommended_next_actions: recommended_next_actions(gate_verdict),
        non_goals: vec![
            "Does not promote memories, runbooks, skills, or retrieval rules.",
            "Does not write owner approval or infer it from local evidence.",
            "Does not mutate runtime policy, tool routing, prompts, profiles, or bootstrap.",
            "Does not treat shadow-score correlation as causal behavior lift.",
        ],
    })
}

#[derive(Debug, Clone)]
struct ExperienceCandidate {
    source_path: Option<String>,
    experience_id: String,
    lane: Option<String>,
    lesson: Option<String>,
    falsifier: Option<String>,
    runtime_influence_allowed: bool,
    readiness_score: u32,
    search_text: String,
}

#[derive(Debug, Clone)]
struct ShadowScoreReportEvidence {
    source_path: Option<String>,
    boundary_safe: bool,
    top_candidates: Vec<TopShadowCandidate>,
}

#[derive(Debug, Clone)]
struct TopShadowCandidate {
    scenario: String,
    experience_id: String,
    shadow_score: u32,
    verdict: String,
    runtime_influence_allowed: bool,
}

#[derive(Debug, Clone)]
struct ShadowScoreScenarioFixture {
    source_path: Option<String>,
    cases: Vec<ShadowScoreScenarioCase>,
}

#[derive(Debug, Clone)]
struct ShadowScoreScenarioCase {
    scenario_id: String,
    scenario: String,
    expected_top_experience_id: String,
}

impl ShadowScoreScenarioFixture {
    fn from_value(value: Value, source_path: Option<String>) -> Result<Self> {
        let schema = value
            .get("schema")
            .and_then(Value::as_str)
            .unwrap_or_default();
        if schema != WORKFLOW_FEEDBACK_SHADOW_SCORE_SCENARIOS_SCHEMA {
            bail!(
                "scenario fixture {} has schema {schema:?}, expected {WORKFLOW_FEEDBACK_SHADOW_SCORE_SCENARIOS_SCHEMA}",
                source_path.as_deref().unwrap_or("<inline>")
            );
        }
        if value.get("read_only").and_then(Value::as_bool) != Some(true) {
            bail!(
                "scenario fixture {} must set read_only=true",
                source_path.as_deref().unwrap_or("<inline>")
            );
        }
        let cases = value
            .get("scenario_cases")
            .and_then(Value::as_array)
            .ok_or_else(|| {
                anyhow::anyhow!(
                    "scenario fixture {} missing scenario_cases array",
                    source_path.as_deref().unwrap_or("<inline>")
                )
            })?
            .iter()
            .map(|case| {
                let scenario_id = required_str(case, "scenario_id", "scenario case")?;
                let scenario = required_str(case, "scenario", "scenario case")?;
                let expected_top_experience_id =
                    required_str(case, "expected_top_experience_id", "scenario case")?;
                Ok(ShadowScoreScenarioCase {
                    scenario_id,
                    scenario,
                    expected_top_experience_id,
                })
            })
            .collect::<Result<Vec<_>>>()?;
        Ok(Self { source_path, cases })
    }
}

impl ShadowScoreReportEvidence {
    fn from_value(value: Value, source_path: Option<String>) -> Result<Self> {
        let schema = value
            .get("schema")
            .and_then(Value::as_str)
            .unwrap_or_default();
        if schema != WORKFLOW_FEEDBACK_SHADOW_SCORE_SCHEMA {
            bail!(
                "shadow score report {} has schema {schema:?}, expected {WORKFLOW_FEEDBACK_SHADOW_SCORE_SCHEMA}",
                source_path.as_deref().unwrap_or("<inline>")
            );
        }

        let read_only = value
            .get("read_only")
            .and_then(Value::as_bool)
            .unwrap_or(false);
        let boundary_safe = read_only
            && value
                .pointer("/boundary/writes_memory")
                .and_then(Value::as_bool)
                == Some(false)
            && value
                .pointer("/boundary/mutates_runtime_policy")
                .and_then(Value::as_bool)
                == Some(false)
            && value
                .pointer("/boundary/changes_retrieval_order")
                .and_then(Value::as_bool)
                == Some(false)
            && value
                .pointer("/boundary/runtime_influence_allowed")
                .and_then(Value::as_bool)
                == Some(false)
            && value
                .pointer("/boundary/owner_gated_runtime_influence")
                .and_then(Value::as_bool)
                == Some(true);

        let rankings = value
            .get("rankings")
            .and_then(Value::as_array)
            .ok_or_else(|| {
                anyhow::anyhow!(
                    "shadow score report {} missing rankings array",
                    source_path.as_deref().unwrap_or("<inline>")
                )
            })?;
        let mut top_candidates = Vec::new();
        for ranking in rankings {
            let scenario = ranking
                .get("scenario")
                .and_then(Value::as_str)
                .unwrap_or("<missing scenario>")
                .to_string();
            let Some(top) = ranking
                .get("ranked_candidates")
                .and_then(Value::as_array)
                .and_then(|items| items.first())
            else {
                continue;
            };
            top_candidates.push(TopShadowCandidate {
                scenario,
                experience_id: top
                    .get("experience_id")
                    .and_then(Value::as_str)
                    .unwrap_or("<missing experience_id>")
                    .to_string(),
                shadow_score: top
                    .get("shadow_score")
                    .and_then(Value::as_u64)
                    .unwrap_or(0)
                    .min(100) as u32,
                verdict: top
                    .get("verdict")
                    .and_then(Value::as_str)
                    .unwrap_or("<missing verdict>")
                    .to_string(),
                runtime_influence_allowed: top
                    .get("runtime_influence_allowed")
                    .and_then(Value::as_bool)
                    .unwrap_or(true),
            });
        }

        Ok(Self {
            source_path,
            boundary_safe,
            top_candidates,
        })
    }
}

fn required_str(value: &Value, key: &str, label: &str) -> Result<String> {
    value
        .get(key)
        .and_then(Value::as_str)
        .map(str::trim)
        .filter(|s| !s.is_empty())
        .map(str::to_string)
        .ok_or_else(|| anyhow::anyhow!("{label} missing non-empty {key}"))
}

fn clean_refs(refs: Vec<String>) -> Vec<String> {
    refs.into_iter()
        .map(|s| s.trim().to_string())
        .filter(|s| !s.is_empty())
        .collect()
}

fn top_experience_counts(counts: BTreeMap<String, usize>) -> Vec<PromotionGateExperienceCount> {
    let mut rows = counts
        .into_iter()
        .map(
            |(experience_id, top_rank_count)| PromotionGateExperienceCount {
                experience_id,
                top_rank_count,
            },
        )
        .collect::<Vec<_>>();
    rows.sort_by(|a, b| {
        b.top_rank_count
            .cmp(&a.top_rank_count)
            .then_with(|| a.experience_id.cmp(&b.experience_id))
    });
    rows
}

fn lift_metric_anchor_ref(verdict: &str, evidence: &LiftEvidenceSummary) -> String {
    let baseline = evidence
        .baseline_accuracy
        .map(|value| format!("{value:.3}"))
        .unwrap_or_else(|| "none".to_string());
    let lift = evidence
        .absolute_lift
        .map(|value| format!("{value:.3}"))
        .unwrap_or_else(|| "none".to_string());
    format!(
        "workflow-feedback-lift-evidence:v0;verdict={verdict};observations={};top1_accuracy={:.3};baseline_accuracy={baseline};absolute_lift={lift}",
        evidence.observation_count, evidence.top1_accuracy
    )
}

fn lift_recommended_next_actions(lift_verdict: &str) -> Vec<&'static str> {
    match lift_verdict {
        "blocked_shadow_boundary_violation" => vec![
            "Reject the lift anchor until all shadow reports are read-only and runtime influence remains false.",
            "Regenerate shadow-score reports from safe fixtures before comparing against baseline.",
        ],
        "blocked_incomplete_observations" => vec![
            "Re-run shadow scoring with every held-out scenario from the scenario fixture.",
            "Do not use a partial observation set as a behavior-lift anchor.",
        ],
        "blocked_expected_top_accuracy" => vec![
            "Improve fixture quality or scenario coverage before using this as a promotion input.",
            "Keep the lesson in audit-only mode until expected-top accuracy clears the threshold.",
        ],
        "metric_anchor_without_baseline" => vec![
            "Attach this packet as a falsifiable metric anchor only, not as measured lift.",
            "Collect a baseline correct/total from an unguided or previous-policy run before owner review.",
        ],
        "blocked_no_positive_lift" => vec![
            "Do not advance to owner review; the measured proxy does not beat baseline enough.",
            "Inspect mismatched scenarios and update the lesson or fixture before another run.",
        ],
        "measured_lift_anchor" => vec![
            "Use the metric_anchor_ref as the behavior-lift ref in the promotion gate packet.",
            "Still require rollback evidence and explicit owner approval before any separate promotion lane.",
        ],
        _ => vec!["Review the lift evidence packet manually before using it as a gate input."],
    }
}

fn recommended_next_actions(gate_verdict: &str) -> Vec<&'static str> {
    match gate_verdict {
        "blocked_shadow_boundary_violation" => vec![
            "Reject or repair unsafe shadow-score evidence before considering promotion.",
            "Re-run shadow scoring from read-only fixtures with runtime influence disabled.",
        ],
        "blocked_insufficient_shadow_runs" => vec![
            "Collect at least one more independent shadow-score report over held-out scenarios.",
            "Keep the experience as audit-only until repeated evidence exists.",
        ],
        "blocked_insufficient_shadow_evidence" => vec![
            "Add held-out scenarios that exercise the proposed lesson's actual trigger conditions.",
            "Require likely_helpful top rankings before preparing an owner review packet.",
        ],
        "blocked_behavior_lift_anchor_required" => vec![
            "Attach a measured behavior-lift anchor such as reduced recovery time, fewer failed tool loops, or improved held-out task completion.",
            "Keep shadow scores as correlation evidence, not causal proof.",
        ],
        "blocked_rollback_evidence_required" => vec![
            "Attach an explicit rollback path, revert handle, or disable switch for the proposed promotion.",
            "Prefer scoped runbook or memory promotion before any retrieval/tool/runtime influence.",
        ],
        "ready_for_owner_review" => vec![
            "Send the packet for explicit owner approval with the shadow, lift, and rollback evidence attached.",
            "Do not apply promotion until the owner approval reference is recorded.",
        ],
        "owner_review_packet_complete" => vec![
            "Apply any promotion only through a separate authorized lane and keep runtime influence off by default.",
            "Record the manual promotion result and rollback handle as durable memory after review.",
        ],
        _ => vec!["Review the gate packet manually before taking any promotion action."],
    }
}

impl ExperienceCandidate {
    fn from_value(value: Value, source_path: Option<String>) -> Result<Self> {
        let schema = value
            .get("schema")
            .and_then(Value::as_str)
            .unwrap_or_default();
        if schema != EXPERIENCE_OBJECT_SCHEMA {
            bail!(
                "fixture {} has schema {schema:?}, expected {EXPERIENCE_OBJECT_SCHEMA}",
                source_path.as_deref().unwrap_or("<inline>")
            );
        }
        let experience_id = value
            .get("experience_id")
            .and_then(Value::as_str)
            .filter(|s| !s.trim().is_empty())
            .ok_or_else(|| {
                anyhow::anyhow!(
                    "fixture {} missing non-empty experience_id",
                    source_path.as_deref().unwrap_or("<inline>")
                )
            })?
            .to_string();
        let lane = value
            .get("lane")
            .and_then(Value::as_str)
            .map(str::to_string);
        let lesson = value
            .pointer("/reflection/lesson")
            .and_then(Value::as_str)
            .map(str::to_string);
        let falsifier = value
            .pointer("/reflection/falsifier")
            .and_then(Value::as_str)
            .map(str::to_string);
        let runtime_influence_allowed = value
            .pointer("/promotion/runtime_influence_allowed")
            .and_then(Value::as_bool)
            .unwrap_or(true);
        let readiness_score = readiness_score(&value);
        let search_text = candidate_search_text(&value);
        Ok(Self {
            source_path,
            experience_id,
            lane,
            lesson,
            falsifier,
            runtime_influence_allowed,
            readiness_score,
            search_text,
        })
    }
}

fn score_scenario(scenario: &str, experiences: &[ExperienceCandidate]) -> ShadowScenarioRanking {
    let scenario_tokens = tokenize(scenario);
    let mut ranked_candidates = experiences
        .iter()
        .map(|candidate| score_candidate(candidate, &scenario_tokens))
        .collect::<Vec<_>>();
    ranked_candidates.sort_by(|a, b| {
        b.shadow_score
            .cmp(&a.shadow_score)
            .then_with(|| b.relevance_score.cmp(&a.relevance_score))
            .then_with(|| b.readiness_score.cmp(&a.readiness_score))
            .then_with(|| a.experience_id.cmp(&b.experience_id))
    });
    ShadowScenarioRanking {
        scenario: scenario.to_string(),
        ranked_candidates,
    }
}

fn score_candidate(
    candidate: &ExperienceCandidate,
    scenario_tokens: &BTreeSet<String>,
) -> ShadowCandidateScore {
    let candidate_tokens = tokenize(&candidate.search_text);
    let matched_terms = scenario_tokens
        .intersection(&candidate_tokens)
        .take(12)
        .cloned()
        .collect::<Vec<_>>();
    let relevance_score = if scenario_tokens.is_empty() {
        0
    } else {
        ((matched_terms.len() as f64 / scenario_tokens.len() as f64) * 100.0).round() as u32
    };
    let mut shadow_score = ((candidate.readiness_score as f64 * 0.35)
        + (relevance_score as f64 * 0.65))
        .round() as u32;
    if candidate.runtime_influence_allowed {
        shadow_score = shadow_score.saturating_sub(20);
    }
    let verdict = if candidate.runtime_influence_allowed {
        "blocked_runtime_influence_not_shadow_only"
    } else if candidate.readiness_score >= 75 && relevance_score >= 35 {
        "likely_helpful_shadow_candidate"
    } else if candidate.readiness_score >= 60 && relevance_score >= 15 {
        "possible_shadow_candidate"
    } else {
        "weak_match_needs_review"
    };
    ShadowCandidateScore {
        experience_id: candidate.experience_id.clone(),
        lane: candidate.lane.clone(),
        source_path: candidate.source_path.clone(),
        shadow_score: shadow_score.min(100),
        readiness_score: candidate.readiness_score,
        relevance_score,
        verdict,
        matched_terms,
        lesson: candidate.lesson.clone(),
        falsifier: candidate.falsifier.clone(),
        runtime_influence_allowed: candidate.runtime_influence_allowed,
    }
}

fn readiness_score(value: &Value) -> u32 {
    let mut score = 0_u32;
    if non_empty_str(value, "experience_id") {
        score += 8;
    }
    if non_empty_str(value, "goal") {
        score += 8;
    }
    if array_len(value, "plan") >= 2 {
        score += 8;
    }
    if array_len(
        value
            .pointer("/trajectory/tool_spans")
            .unwrap_or(&Value::Null),
        "",
    ) >= 2
    {
        score += 14;
    }
    if array_len(
        value
            .pointer("/trajectory/decision_points")
            .unwrap_or(&Value::Null),
        "",
    ) >= 1
    {
        score += 10;
    }
    if non_empty_str_at(value, "/reflection/lesson") {
        score += 12;
    }
    if non_empty_str_at(value, "/reflection/falsifier") {
        score += 8;
    }
    if array_len(
        value.pointer("/outcome/evidence").unwrap_or(&Value::Null),
        "",
    ) >= 2
    {
        score += 12;
    }
    if value
        .pointer("/promotion/runtime_influence_allowed")
        .and_then(Value::as_bool)
        == Some(false)
    {
        score += 10;
    }
    if safety_all_false(value) {
        score += 10;
    }
    score.min(100)
}

fn candidate_search_text(value: &Value) -> String {
    let mut parts = Vec::new();
    for pointer in [
        "/experience_id",
        "/lane",
        "/goal",
        "/reflection/lesson",
        "/reflection/falsifier",
        "/promotion/suggested_trigger",
    ] {
        if let Some(s) = value.pointer(pointer).and_then(Value::as_str) {
            parts.push(s.to_string());
        }
    }
    collect_array_strings(value.get("plan"), &mut parts);
    collect_array_strings(value.pointer("/reflection/reusable_workflow"), &mut parts);
    collect_array_strings(value.pointer("/outcome/evidence"), &mut parts);
    collect_nested_text(value.pointer("/trajectory/tool_spans"), &mut parts);
    collect_nested_text(value.pointer("/trajectory/decision_points"), &mut parts);
    parts.join(" ")
}

fn collect_array_strings(value: Option<&Value>, parts: &mut Vec<String>) {
    if let Some(Value::Array(items)) = value {
        for item in items {
            if let Some(s) = item.as_str() {
                parts.push(s.to_string());
            }
        }
    }
}

fn collect_nested_text(value: Option<&Value>, parts: &mut Vec<String>) {
    match value {
        Some(Value::String(s)) => parts.push(s.to_string()),
        Some(Value::Array(items)) => {
            for item in items {
                collect_nested_text(Some(item), parts);
            }
        }
        Some(Value::Object(map)) => {
            for (_key, item) in map {
                collect_nested_text(Some(item), parts);
            }
        }
        _ => {}
    }
}

fn non_empty_str(value: &Value, key: &str) -> bool {
    value
        .get(key)
        .and_then(Value::as_str)
        .map(|s| !s.trim().is_empty())
        .unwrap_or(false)
}

fn non_empty_str_at(value: &Value, pointer: &str) -> bool {
    value
        .pointer(pointer)
        .and_then(Value::as_str)
        .map(|s| !s.trim().is_empty())
        .unwrap_or(false)
}

fn array_len(value: &Value, key: &str) -> usize {
    let target = if key.is_empty() {
        value
    } else {
        value.get(key).unwrap_or(&Value::Null)
    };
    target.as_array().map(Vec::len).unwrap_or(0)
}

fn safety_all_false(value: &Value) -> bool {
    [
        "/safety/fixture_writes_memory",
        "/safety/fixture_changes_runtime",
        "/safety/fixture_changes_retrieval_order",
        "/safety/fixture_authorizes_future_runtime_influence",
    ]
    .iter()
    .all(|pointer| value.pointer(pointer).and_then(Value::as_bool) == Some(false))
}

fn tokenize(input: &str) -> BTreeSet<String> {
    const STOP: &[&str] = &[
        "a", "an", "and", "are", "as", "before", "by", "for", "from", "in", "into", "is", "it",
        "no", "not", "of", "or", "the", "to", "with", "without",
    ];
    input
        .split(|c: char| !c.is_alphanumeric() && c != '_')
        .filter_map(|raw| {
            let token = raw.trim().to_ascii_lowercase();
            if token.len() < 3 || STOP.contains(&token.as_str()) {
                None
            } else {
                Some(token)
            }
        })
        .collect()
}

fn build_scorecard(evidence: &WorkflowFeedbackEvidence) -> Vec<ScorecardAxis> {
    let memory = &evidence.memory;
    let tools = &evidence.tool_telemetry;
    let capture_status = if memory.active_rows > 0 && tools.total_calls_in_top_window > 0 {
        "partial"
    } else if memory.active_rows > 0 || tools.total_calls_in_top_window > 0 {
        "thin"
    } else {
        "empty"
    };
    let attribution_status = if memory.edge_count > 0 && tools.tools_observed > 0 {
        "partial"
    } else if memory.edge_count > 0 || tools.tools_observed > 0 {
        "weak"
    } else {
        "missing"
    };
    let feedback_status = if memory.feedback_fraction >= 0.10 {
        "usable"
    } else if memory.feedback_rows > 0 {
        "low"
    } else {
        "missing"
    };
    let behavior_status = if tools.total_calls_in_top_window >= 50 {
        "measurable"
    } else if tools.total_calls_in_top_window > 0 {
        "early"
    } else {
        "unmeasured"
    };

    vec![
        ScorecardAxis {
            axis: "Capture coverage",
            status: capture_status.to_string(),
            evidence: format!(
                "{} active memories and {} MCP calls in the selected window",
                memory.active_rows, tools.total_calls_in_top_window
            ),
            next_probe: "normalize work-loop episodes into Experience Object v0 fixtures",
        },
        ScorecardAxis {
            axis: "Attribution quality",
            status: attribution_status.to_string(),
            evidence: format!(
                "{} memory graph edges and {} observed tools",
                memory.edge_count, tools.tools_observed
            ),
            next_probe: "link outcomes to tool spans, memory keys, and forum decisions",
        },
        ScorecardAxis {
            axis: "Feedback density",
            status: feedback_status.to_string(),
            evidence: format!(
                "{} feedback rows out of {} active rows ({:.1}%)",
                memory.feedback_rows,
                memory.active_rows,
                memory.feedback_fraction * 100.0
            ),
            next_probe: "increase explicit useful/stale/harmful/missing labels before optimizing",
        },
        ScorecardAxis {
            axis: "Retrieval influence",
            status: "conservative".to_string(),
            evidence: "report observes feedback but does not alter bootstrap, ranking, or routing"
                .to_string(),
            next_probe: "shadow-score lesson influence before any owner-gated runtime change",
        },
        ScorecardAxis {
            axis: "Behavior lift",
            status: behavior_status.to_string(),
            evidence: format!(
                "{} calls, {} errors, {:.1}% error rate",
                tools.total_calls_in_top_window,
                tools.total_errors_in_top_window,
                tools.error_rate_in_top_window * 100.0
            ),
            next_probe: "define held-out workflow tasks and compare before/after recovery time",
        },
        ScorecardAxis {
            axis: "Governance",
            status: "strong".to_string(),
            evidence: "read-only report, runtime influence disabled, owner gate required"
                .to_string(),
            next_probe: "keep promotion rules explicit: fixture -> shadow score -> owner decision",
        },
    ]
}

fn build_improvements(evidence: &WorkflowFeedbackEvidence) -> Vec<ProposedImprovement> {
    let mut out = Vec::new();
    out.push(ProposedImprovement {
        id: "WF-1",
        title: "Curate Experience Object v0 fixtures",
        rationale: "The report can now emit a fixture shape; the next value is to fill it from completed AB lanes instead of synthetic examples.".to_string(),
        next_action: "create 1-2 fixture files from completed, evidence-backed lanes",
        runtime_influence_allowed: false,
    });

    if evidence.memory.feedback_fraction < 0.05 {
        out.push(ProposedImprovement {
            id: "WF-2",
            title: "Raise explicit feedback density",
            rationale: format!(
                "Feedback rows are only {:.1}% of active memory; optimization signals are sparse.",
                evidence.memory.feedback_fraction * 100.0
            ),
            next_action: "label stale/harmful/missing/useful retrieval outcomes during reviews",
            runtime_influence_allowed: false,
        });
    }

    if evidence.tool_telemetry.total_errors_in_top_window > 0 {
        let failing = evidence
            .tool_telemetry
            .hot_tools
            .iter()
            .find(|row| row.error_count > 0)
            .map(|row| row.tool_name.clone())
            .unwrap_or_else(|| "tool telemetry".to_string());
        out.push(ProposedImprovement {
            id: "WF-3",
            title: "Review tool-use friction",
            rationale: format!(
                "{} errors appeared in the selected window; first failing hot area: {}.",
                evidence.tool_telemetry.total_errors_in_top_window, failing
            ),
            next_action: "turn repeated tool failures into compact lessons or runbook edits",
            runtime_influence_allowed: false,
        });
    }

    if evidence.memory.distinct_scopes > 1 {
        out.push(ProposedImprovement {
            id: "WF-4",
            title: "Use scope fragmentation as a workflow signal",
            rationale: format!(
                "{} distinct active scopes can hide repeated lessons behind path variants.",
                evidence.memory.distinct_scopes
            ),
            next_action: "run memory_scope_survey before promoting scope-sensitive lessons",
            runtime_influence_allowed: false,
        });
    }

    out.push(ProposedImprovement {
        id: "WF-5",
        title: "Shadow-score before promotion",
        rationale: "A reusable lesson should prove it would have helped a held-out session before it changes defaults.".to_string(),
        next_action: "add a shadow scoring fixture that ranks proposed lessons without applying them",
        runtime_influence_allowed: false,
    });

    out.truncate(5);
    out
}

fn build_experience_fixture(
    evidence: &WorkflowFeedbackEvidence,
    scorecard: &[ScorecardAxis],
    improvements: &[ProposedImprovement],
    scope: Option<String>,
) -> Value {
    json!({
        "schema": EXPERIENCE_OBJECT_SCHEMA,
        "experience_id": "exp_20260630_workflow_feedback_report_v0",
        "scope": scope.unwrap_or_else(|| "project:agent-bridge".to_string()),
        "goal": "Build a read-only workflow feedback report for Agent-Bridge",
        "plan": [
            "read existing memory statistics",
            "read recent MCP tool-call telemetry",
            "emit maturity scorecard",
            "propose report-only improvements"
        ],
        "trajectory": {
            "source_report_schema": WORKFLOW_FEEDBACK_REPORT_SCHEMA,
            "tool_window_secs": evidence.tool_telemetry.window_secs,
            "observed_tools": evidence.tool_telemetry.tools_observed,
            "active_memory_rows": evidence.memory.active_rows,
            "scorecard_axes": scorecard.iter().map(|axis| axis.axis).collect::<Vec<_>>()
        },
        "outcome": {
            "status": "report_only",
            "evidence": [
                format!("{} active memory rows", evidence.memory.active_rows),
                format!("{} MCP calls in selected window", evidence.tool_telemetry.total_calls_in_top_window),
                format!("{} proposed improvements", improvements.len())
            ]
        },
        "reflection": {
            "lesson": "Agent-Bridge should close trajectory/outcome/reflection/retrieval loops with read-only scorecards before automatic policy mutation.",
            "falsifier": "If repeated reports do not produce adopted improvements or measurable behavior lift, redesign the workflow feedback loop."
        },
        "promotion": {
            "skill_candidate": false,
            "runbook_candidate": true,
            "runtime_influence_allowed": false,
            "owner_gate_required": true
        }
    })
}

fn count_named(rows: &[(String, u64)], name: &str) -> u64 {
    rows.iter()
        .find(|(k, _)| k == name)
        .map(|(_, n)| *n)
        .unwrap_or(0)
}

fn count_rows<'a>(rows: impl Iterator<Item = &'a (String, u64)>) -> Vec<CountRow> {
    rows.map(|(name, count)| CountRow {
        name: name.clone(),
        count: *count,
    })
    .collect()
}

fn tool_row(row: &McpToolCallStats) -> ToolRow {
    ToolRow {
        tool_name: row.tool_name.clone(),
        call_count: row.call_count,
        error_count: row.error_count,
        avg_duration_ms: row.avg_duration_ms,
        p95_duration_ms: row.p95_duration_ms,
        avg_result_size: row.avg_result_size,
    }
}

fn fraction(numerator: u64, denominator: u64) -> f64 {
    if denominator == 0 {
        0.0
    } else {
        numerator as f64 / denominator as f64
    }
}

fn pipe_safe(s: &str) -> String {
    s.replace('|', "\\|").replace('\n', " ")
}

#[cfg(test)]
mod tests {
    use super::*;
    use ab_store::{MemoryRecord, SqliteStore, StateStore};

    fn test_memory(key: &str, kind: &str, scope: Option<&str>, now: i64) -> MemoryRecord {
        MemoryRecord {
            key: key.to_string(),
            kind: kind.to_string(),
            content: format!("{kind} content for {key}"),
            tags: Vec::new(),
            related_keys: Vec::new(),
            scope: scope.map(str::to_string),
            created_at: now,
            updated_at: now,
            last_accessed_at: 0,
            access_count: 0,
            importance: 0.5,
            status: "active".to_string(),
            trigger_pattern: None,
            superseded_by: None,
        }
    }

    #[tokio::test]
    async fn workflow_feedback_report_is_read_only_and_emits_fixture() {
        let temp = tempfile::tempdir().expect("tempdir");
        let db_path = temp.path().join("state.db");
        let store = SqliteStore::open(&db_path).await.expect("open store");
        let now = std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)
            .unwrap_or_default()
            .as_secs() as i64;

        store
            .memory_save(&test_memory("wf-fact", "fact", Some("project:ab"), now))
            .await
            .expect("save fact");
        store
            .memory_save(&test_memory(
                "wf-feedback",
                "feedback",
                Some("project:ab"),
                now,
            ))
            .await
            .expect("save feedback");
        store
            .record_mcp_tool_call(
                "memory_search",
                42,
                true,
                Some(32),
                Some(128),
                Some("test-client".to_string()),
                Some("test-profile".to_string()),
                Some("test-source".to_string()),
                None,
                None,
                None,
            )
            .await
            .expect("record tool call");

        let report = build_report(
            &store,
            WorkflowFeedbackReportOptions {
                window_secs: 86_400,
                top_tools: 5,
                scope: Some("project:/tmp/agent-bridge-test".to_string()),
            },
        )
        .await
        .expect("build report");

        assert_eq!(report.schema, WORKFLOW_FEEDBACK_REPORT_SCHEMA);
        assert!(report.read_only);
        assert!(!report.boundary.writes_memory);
        assert!(!report.boundary.mutates_runtime_policy);
        assert_eq!(report.evidence.memory.active_rows, 2);
        assert_eq!(report.evidence.memory.feedback_rows, 1);
        assert_eq!(report.evidence.tool_telemetry.total_calls_in_top_window, 1);
        assert_eq!(
            report.experience_object_fixture["schema"],
            EXPERIENCE_OBJECT_SCHEMA
        );
        assert_eq!(
            report.experience_object_fixture["promotion"]["runtime_influence_allowed"],
            false
        );
        assert!(
            report
                .render_markdown()
                .contains("## Experience Object v0 Fixture")
        );
    }

    #[test]
    fn scorecard_marks_sparse_feedback_as_low() {
        let evidence = WorkflowFeedbackEvidence {
            memory: MemoryEvidence {
                active_rows: 100,
                feedback_rows: 2,
                feedback_fraction: 0.02,
                edge_count: 1,
                distinct_kinds: 3,
                distinct_scopes: 1,
                distinct_embedding_backends: 1,
                top_kinds: Vec::new(),
                top_scopes: Vec::new(),
                embedding_backends: Vec::new(),
            },
            tool_telemetry: ToolTelemetryEvidence {
                window_secs: 86_400,
                tools_observed: 2,
                total_calls_in_top_window: 10,
                total_errors_in_top_window: 0,
                error_rate_in_top_window: 0.0,
                hot_tools: Vec::new(),
            },
        };

        let scorecard = build_scorecard(&evidence);
        let feedback = scorecard
            .iter()
            .find(|axis| axis.axis == "Feedback density")
            .expect("feedback axis");
        assert_eq!(feedback.status, "low");
    }

    fn fixture_value(id: &str, lane: &str, lesson: &str, trigger: &str) -> Value {
        json!({
            "schema": EXPERIENCE_OBJECT_SCHEMA,
            "experience_id": id,
            "scope": "project:/Data/CascadeProjects/agent-bridge",
            "lane": lane,
            "goal": lesson,
            "plan": ["inspect", "verify", "record"],
            "trajectory": {
                "tool_spans": [
                    {"tool": "cargo test", "purpose": "verify", "outcome": "success"},
                    {"tool": "forum_post", "purpose": "record", "outcome": "success"}
                ],
                "decision_points": [
                    {"question": "policy?", "decision": "stay read-only"}
                ]
            },
            "outcome": {
                "status": "success",
                "evidence": ["commit landed", "tests passed"]
            },
            "reflection": {
                "lesson": lesson,
                "falsifier": "If the held-out scenario no longer matches, keep this as audit-only."
            },
            "promotion": {
                "skill_candidate": false,
                "runbook_candidate": true,
                "runtime_influence_allowed": false,
                "owner_gate_required": true,
                "suggested_trigger": trigger
            },
            "source_anchors": {
                "commits": ["0000000"]
            },
            "safety": {
                "fixture_writes_memory": false,
                "fixture_changes_runtime": false,
                "fixture_changes_retrieval_order": false,
                "fixture_authorizes_future_runtime_influence": false
            }
        })
    }

    #[test]
    fn shadow_score_ranks_matching_fixture_above_nonmatching_fixture() {
        let agent = ExperienceCandidate::from_value(
            fixture_value(
                "exp_agent_input",
                "agent_send_input",
                "Interactive agent runtime send_input fixes need post-reconnect binary verification and no chrome prompt.",
                "interactive claude code send_input runtime prompt",
            ),
            Some("agent.json".to_string()),
        )
        .expect("agent fixture");
        let report = ExperienceCandidate::from_value(
            fixture_value(
                "exp_workflow_report",
                "workflow_feedback",
                "Workflow feedback should mature from research to read-only report to fixture before default influence.",
                "workflow feedback report shadow scoring",
            ),
            Some("report.json".to_string()),
        )
        .expect("report fixture");

        let shadow = build_shadow_score_report(
            vec![agent, report],
            vec![
                "interactive Claude Code send_input stalls on chrome prompt after reconnect"
                    .to_string(),
            ],
        )
        .expect("shadow report");

        assert_eq!(shadow.schema, WORKFLOW_FEEDBACK_SHADOW_SCORE_SCHEMA);
        assert!(shadow.read_only);
        assert!(!shadow.boundary.writes_memory);
        assert_eq!(shadow.rankings.len(), 1);
        let ranked = &shadow.rankings[0].ranked_candidates;
        assert_eq!(ranked[0].experience_id, "exp_agent_input");
        assert!(ranked[0].shadow_score > ranked[1].shadow_score);
        assert!(!ranked[0].runtime_influence_allowed);
    }

    #[test]
    fn promotion_gate_prepares_owner_review_without_inventing_approval() {
        let workflow = ExperienceCandidate::from_value(
            fixture_value(
                "exp_workflow_report",
                "workflow_feedback",
                "Workflow feedback should mature from research to read-only report to fixture before default influence.",
                "workflow feedback report shadow scoring promotion evidence",
            ),
            Some("workflow.json".to_string()),
        )
        .expect("workflow fixture");
        let agent = ExperienceCandidate::from_value(
            fixture_value(
                "exp_agent_input",
                "agent_send_input",
                "Interactive agent runtime send_input fixes need post-reconnect binary verification and no chrome prompt.",
                "interactive claude code send_input runtime prompt",
            ),
            Some("agent.json".to_string()),
        )
        .expect("agent fixture");
        let shadow = build_shadow_score_report(
            vec![workflow, agent],
            vec![
                "workflow feedback report shadow scoring promotion evidence before default influence"
                    .to_string(),
                "workflow feedback lesson needs rollback evidence and behavior lift before promotion"
                    .to_string(),
            ],
        )
        .expect("shadow report");
        let evidence = ShadowScoreReportEvidence::from_value(
            shadow.to_json_value(),
            Some("shadow-a.json".to_string()),
        )
        .expect("shadow evidence");

        let gate = build_promotion_gate_report(
            vec![evidence.clone(), evidence],
            WorkflowFeedbackPromotionGateOptions {
                behavior_lift_refs: vec![
                    "metric:held-out workflow recovery time improved in replay".to_string(),
                ],
                rollback_refs: vec!["rollback:remove promoted runbook/memory key".to_string()],
                ..Default::default()
            },
        )
        .expect("promotion gate");

        assert_eq!(gate.schema, WORKFLOW_FEEDBACK_PROMOTION_GATE_SCHEMA);
        assert!(gate.read_only);
        assert!(!gate.boundary.writes_memory);
        assert!(!gate.boundary.mutates_runtime_policy);
        assert!(!gate.boundary.changes_retrieval_order);
        assert!(!gate.boundary.runtime_influence_allowed);
        assert!(gate.ready_for_owner_review);
        assert!(!gate.advisory_promotion_ready);
        assert_eq!(gate.gate_verdict, "ready_for_owner_review");
        assert_eq!(gate.evidence.shadow_report_count, 2);
        assert_eq!(gate.evidence.scenario_count, 4);
        assert!(gate.evidence.strong_shadow_match_count >= 2);
        assert!(gate.evidence.owner_approval_refs.is_empty());
        let owner_check = gate
            .checks
            .iter()
            .find(|check| check.id == "owner_approval")
            .expect("owner approval check");
        assert!(!owner_check.passed);
        assert!(gate.render_markdown().contains("ready_for_owner_review"));
    }

    #[test]
    fn promotion_gate_blocks_unsafe_shadow_boundary() {
        let workflow = ExperienceCandidate::from_value(
            fixture_value(
                "exp_workflow_report",
                "workflow_feedback",
                "Workflow feedback should mature from research to read-only report to fixture before default influence.",
                "workflow feedback report shadow scoring promotion evidence",
            ),
            Some("workflow.json".to_string()),
        )
        .expect("workflow fixture");
        let mut shadow_value = build_shadow_score_report(
            vec![workflow],
            vec!["workflow feedback report shadow scoring promotion evidence".to_string()],
        )
        .expect("shadow report")
        .to_json_value();
        shadow_value["boundary"]["runtime_influence_allowed"] = json!(true);
        let evidence = ShadowScoreReportEvidence::from_value(
            shadow_value,
            Some("unsafe-shadow.json".to_string()),
        )
        .expect("shadow evidence");

        let gate = build_promotion_gate_report(
            vec![evidence],
            WorkflowFeedbackPromotionGateOptions {
                owner_approval_refs: vec!["forum:#108/#owner-approval".to_string()],
                rollback_refs: vec!["rollback:disable promoted artifact".to_string()],
                behavior_lift_refs: vec!["metric:held-out replay lift".to_string()],
                min_shadow_reports: 1,
                min_scenarios: 1,
                min_strong_scenarios: 1,
                min_top_shadow_score: 65,
            },
        )
        .expect("promotion gate");

        assert_eq!(gate.gate_verdict, "blocked_shadow_boundary_violation");
        assert!(!gate.ready_for_owner_review);
        assert!(!gate.advisory_promotion_ready);
        assert_eq!(gate.evidence.unsafe_shadow_report_count, 1);
        let boundary_check = gate
            .checks
            .iter()
            .find(|check| check.id == "shadow_boundaries_safe")
            .expect("boundary check");
        assert!(!boundary_check.passed);
    }

    #[test]
    fn shadow_score_rejects_non_experience_schema() {
        let err = ExperienceCandidate::from_value(
            json!({"schema": "wrong.schema", "experience_id": "bad"}),
            None,
        )
        .expect_err("wrong schema must fail");
        assert!(
            err.to_string()
                .contains("expected agent_bridge.experience.v0")
        );
    }

    fn two_scenario_shadow_score_value() -> Value {
        let agent = ExperienceCandidate::from_value(
            fixture_value(
                "exp_agent_input",
                "agent_send_input",
                "Interactive agent runtime send_input fixes need post-reconnect binary verification and no chrome prompt.",
                "interactive claude code send_input runtime prompt",
            ),
            Some("agent.json".to_string()),
        )
        .expect("agent fixture");
        let report = ExperienceCandidate::from_value(
            fixture_value(
                "exp_workflow_report",
                "workflow_feedback",
                "Workflow feedback should mature from research to read-only report to fixture before default influence.",
                "workflow feedback report shadow scoring owner gate",
            ),
            Some("report.json".to_string()),
        )
        .expect("report fixture");

        build_shadow_score_report(
            vec![agent, report],
            vec![
                "interactive Claude Code send_input stalls on chrome prompt after reconnect"
                    .to_string(),
                "workflow feedback lessons should stay report first with shadow scoring and owner gate"
                    .to_string(),
            ],
        )
        .expect("shadow report")
        .to_json_value()
    }

    fn two_scenario_fixture_value() -> Value {
        json!({
            "schema": WORKFLOW_FEEDBACK_SHADOW_SCORE_SCENARIOS_SCHEMA,
            "read_only": true,
            "scenario_cases": [
                {
                    "scenario_id": "interactive_agent_send_input_stall",
                    "scenario": "interactive Claude Code send_input stalls on chrome prompt after reconnect",
                    "expected_top_experience_id": "exp_agent_input"
                },
                {
                    "scenario_id": "workflow_feedback_policy_pressure",
                    "scenario": "workflow feedback lessons should stay report first with shadow scoring and owner gate",
                    "expected_top_experience_id": "exp_workflow_report"
                }
            ]
        })
    }

    #[test]
    fn lift_evidence_reports_metric_anchor_without_baseline() {
        let scenarios = ShadowScoreScenarioFixture::from_value(
            two_scenario_fixture_value(),
            Some("scenarios.json".to_string()),
        )
        .expect("scenario fixture");
        let shadow = ShadowScoreReportEvidence::from_value(
            two_scenario_shadow_score_value(),
            Some("shadow.json".to_string()),
        )
        .expect("shadow evidence");
        let lift = build_lift_evidence_report(
            scenarios,
            vec![shadow],
            WorkflowFeedbackLiftEvidenceOptions {
                min_accuracy: 0.75,
                min_lift: 0.10,
                ..Default::default()
            },
        )
        .expect("lift evidence");

        assert_eq!(lift.schema, WORKFLOW_FEEDBACK_LIFT_EVIDENCE_SCHEMA);
        assert!(lift.read_only);
        assert!(!lift.boundary.writes_memory);
        assert!(!lift.boundary.mutates_runtime_policy);
        assert!(!lift.boundary.changes_retrieval_order);
        assert!(!lift.boundary.runtime_influence_allowed);
        assert_eq!(lift.lift_verdict, "metric_anchor_without_baseline");
        assert!(!lift.measured_against_baseline);
        assert_eq!(lift.evidence.observation_count, 2);
        assert_eq!(lift.evidence.expected_top_match_count, 2);
        assert!((lift.evidence.top1_accuracy - 1.0).abs() < f64::EPSILON);
        assert!(lift.metric_anchor_ref.contains("baseline_accuracy=none"));
    }

    #[test]
    fn lift_evidence_measures_positive_lift_against_baseline() {
        let scenarios = ShadowScoreScenarioFixture::from_value(
            two_scenario_fixture_value(),
            Some("scenarios.json".to_string()),
        )
        .expect("scenario fixture");
        let shadow_one = ShadowScoreReportEvidence::from_value(
            two_scenario_shadow_score_value(),
            Some("shadow-one.json".to_string()),
        )
        .expect("shadow one");
        let shadow_two = ShadowScoreReportEvidence::from_value(
            two_scenario_shadow_score_value(),
            Some("shadow-two.json".to_string()),
        )
        .expect("shadow two");
        let lift = build_lift_evidence_report(
            scenarios,
            vec![shadow_one, shadow_two],
            WorkflowFeedbackLiftEvidenceOptions {
                baseline_correct: Some(0),
                baseline_total: Some(4),
                min_accuracy: 0.75,
                min_lift: 0.50,
            },
        )
        .expect("lift evidence");

        assert_eq!(lift.lift_verdict, "measured_lift_anchor");
        assert!(lift.measured_against_baseline);
        assert_eq!(lift.evidence.observation_count, 4);
        assert_eq!(lift.evidence.expected_top_match_count, 4);
        assert_eq!(lift.evidence.baseline_accuracy, Some(0.0));
        assert_eq!(lift.evidence.absolute_lift, Some(1.0));
        assert!(lift.checks.iter().all(|check| check.passed));
        assert!(lift.metric_anchor_ref.contains("absolute_lift=1.000"));
    }

    #[test]
    fn lift_evidence_rejects_non_scenario_fixture_schema() {
        let err = ShadowScoreScenarioFixture::from_value(
            json!({"schema": "wrong.schema", "read_only": true, "scenario_cases": []}),
            None,
        )
        .expect_err("wrong schema must fail");
        assert!(
            err.to_string()
                .contains("expected agent_bridge.workflow_feedback_shadow_score_scenarios.v0")
        );
    }

    #[test]
    fn promotion_gate_blocks_without_lift_rollback_and_owner_refs() {
        let shadow = ShadowScoreReportEvidence::from_value(
            two_scenario_shadow_score_value(),
            Some("shadow.json".to_string()),
        )
        .expect("shadow evidence");
        let gate = build_promotion_gate_report(
            vec![shadow],
            WorkflowFeedbackPromotionGateOptions {
                min_shadow_reports: 1,
                min_scenarios: 2,
                min_strong_scenarios: 2,
                min_top_shadow_score: 60,
                ..WorkflowFeedbackPromotionGateOptions::default()
            },
        )
        .expect("promotion gate");

        assert_eq!(gate.schema, WORKFLOW_FEEDBACK_PROMOTION_GATE_SCHEMA);
        assert!(gate.read_only);
        assert!(!gate.boundary.writes_memory);
        assert!(!gate.boundary.mutates_runtime_policy);
        assert!(!gate.boundary.changes_retrieval_order);
        assert!(!gate.boundary.runtime_influence_allowed);
        assert_eq!(gate.gate_verdict, "blocked_behavior_lift_anchor_required");
        assert!(!gate.ready_for_owner_review);
        assert!(!gate.advisory_promotion_ready);
    }

    #[test]
    fn promotion_gate_completes_packet_but_keeps_runtime_influence_false() {
        let shadow_one = ShadowScoreReportEvidence::from_value(
            two_scenario_shadow_score_value(),
            Some("shadow-one.json".to_string()),
        )
        .expect("shadow one");
        let shadow_two = ShadowScoreReportEvidence::from_value(
            two_scenario_shadow_score_value(),
            Some("shadow-two.json".to_string()),
        )
        .expect("shadow two");
        let gate = build_promotion_gate_report(
            vec![shadow_one, shadow_two],
            WorkflowFeedbackPromotionGateOptions {
                owner_approval_refs: vec!["forum:#108-owner-review".to_string()],
                rollback_refs: vec!["git revert 7d3d01d".to_string()],
                behavior_lift_refs: vec![
                    "metric: held-out recovery path 2/2 top-ranked".to_string(),
                ],
                min_shadow_reports: 2,
                min_scenarios: 2,
                min_strong_scenarios: 2,
                min_top_shadow_score: 60,
            },
        )
        .expect("promotion gate");

        assert_eq!(gate.gate_verdict, "owner_review_packet_complete");
        assert!(gate.ready_for_owner_review);
        assert!(gate.advisory_promotion_ready);
        assert!(!gate.boundary.runtime_influence_allowed);
        assert!(gate.checks.iter().all(|check| check.passed));
        assert_eq!(gate.evidence.shadow_report_count, 2);
        assert!(gate.evidence.strong_shadow_match_count >= 2);
    }

    #[test]
    fn promotion_gate_rejects_non_shadow_score_schema() {
        let err = ShadowScoreReportEvidence::from_value(
            json!({"schema": "wrong.schema", "read_only": true}),
            None,
        )
        .expect_err("wrong schema must fail");
        assert!(
            err.to_string()
                .contains("expected agent_bridge.workflow_feedback_shadow_score.v0")
        );
    }

    fn two_case_scenario_fixture() -> ShadowScoreScenarioFixture {
        ShadowScoreScenarioFixture::from_value(
            json!({
                "schema": WORKFLOW_FEEDBACK_SHADOW_SCORE_SCENARIOS_SCHEMA,
                "read_only": true,
                "scenario_cases": [
                    {
                        "scenario_id": "interactive_agent_send_input_stall",
                        "scenario": "interactive Claude Code send_input stalls on chrome prompt after reconnect",
                        "expected_top_experience_id": "exp_agent_input"
                    },
                    {
                        "scenario_id": "workflow_feedback_policy_pressure",
                        "scenario": "workflow feedback lessons should stay report first with shadow scoring and owner gate",
                        "expected_top_experience_id": "exp_workflow_report"
                    }
                ]
            }),
            Some("scenarios.json".to_string()),
        )
        .expect("scenario fixture")
    }

    #[test]
    fn lift_evidence_reports_measured_anchor_when_shadow_beats_baseline() {
        let shadow = ShadowScoreReportEvidence::from_value(
            two_scenario_shadow_score_value(),
            Some("shadow.json".to_string()),
        )
        .expect("shadow evidence");

        let report = build_lift_evidence_report(
            two_case_scenario_fixture(),
            vec![shadow],
            WorkflowFeedbackLiftEvidenceOptions {
                baseline_correct: Some(1),
                baseline_total: Some(2),
                min_accuracy: 0.75,
                min_lift: 0.25,
            },
        )
        .expect("lift evidence");

        assert_eq!(report.schema, WORKFLOW_FEEDBACK_LIFT_EVIDENCE_SCHEMA);
        assert!(report.read_only);
        assert!(!report.boundary.writes_memory);
        assert!(!report.boundary.mutates_runtime_policy);
        assert!(!report.boundary.changes_retrieval_order);
        assert!(!report.boundary.runtime_influence_allowed);
        assert_eq!(report.lift_verdict, "measured_lift_anchor");
        assert!(report.measured_against_baseline);
        assert_eq!(report.evidence.observation_count, 2);
        assert_eq!(report.evidence.expected_top_match_count, 2);
        assert_eq!(report.evidence.missing_observation_count, 0);
        assert_eq!(report.evidence.baseline_correct, Some(1));
        assert_eq!(report.evidence.baseline_total, Some(2));
        assert_eq!(report.evidence.top1_accuracy, 1.0);
        assert_eq!(report.evidence.absolute_lift, Some(0.5));
        assert!(report.metric_anchor_ref.contains("measured_lift_anchor"));
        assert!(report.checks.iter().all(|check| check.passed));
    }

    #[test]
    fn lift_evidence_without_baseline_is_metric_anchor_only() {
        let shadow = ShadowScoreReportEvidence::from_value(
            two_scenario_shadow_score_value(),
            Some("shadow.json".to_string()),
        )
        .expect("shadow evidence");

        let report = build_lift_evidence_report(
            two_case_scenario_fixture(),
            vec![shadow],
            WorkflowFeedbackLiftEvidenceOptions {
                min_accuracy: 0.75,
                ..WorkflowFeedbackLiftEvidenceOptions::default()
            },
        )
        .expect("lift evidence");

        assert_eq!(report.lift_verdict, "metric_anchor_without_baseline");
        assert!(!report.measured_against_baseline);
        assert_eq!(report.evidence.absolute_lift, None);
        let baseline_check = report
            .checks
            .iter()
            .find(|check| check.id == "baseline_supplied")
            .expect("baseline check");
        assert!(!baseline_check.passed);
        assert!(!report.checks.iter().all(|check| check.passed));
    }

    #[test]
    fn lift_evidence_blocks_incomplete_shadow_observations() {
        let shadow = ShadowScoreReportEvidence::from_value(
            two_scenario_shadow_score_value(),
            Some("shadow.json".to_string()),
        )
        .expect("shadow evidence");
        let incomplete_fixture = ShadowScoreScenarioFixture::from_value(
            json!({
                "schema": WORKFLOW_FEEDBACK_SHADOW_SCORE_SCENARIOS_SCHEMA,
                "read_only": true,
                "scenario_cases": [
                    {
                        "scenario_id": "not_scored",
                        "scenario": "a held-out scenario not present in the shadow report",
                        "expected_top_experience_id": "exp_agent_input"
                    }
                ]
            }),
            Some("missing.json".to_string()),
        )
        .expect("scenario fixture");

        let report = build_lift_evidence_report(
            incomplete_fixture,
            vec![shadow],
            WorkflowFeedbackLiftEvidenceOptions {
                baseline_correct: Some(0),
                baseline_total: Some(1),
                min_accuracy: 0.75,
                min_lift: 0.10,
            },
        )
        .expect("lift evidence");

        assert_eq!(report.lift_verdict, "blocked_incomplete_observations");
        assert_eq!(report.evidence.observation_count, 0);
        assert_eq!(report.evidence.missing_observation_count, 1);
        assert!(
            !report
                .checks
                .iter()
                .find(|check| check.id == "scenario_observations_complete")
                .expect("observation check")
                .passed
        );
    }
}
