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
use std::collections::BTreeSet;
use std::path::PathBuf;

pub const WORKFLOW_FEEDBACK_REPORT_SCHEMA: &str = "agent_bridge.workflow_feedback_report.v0";
pub const EXPERIENCE_OBJECT_SCHEMA: &str = "agent_bridge.experience.v0";
pub const WORKFLOW_FEEDBACK_SHADOW_SCORE_SCHEMA: &str =
    "agent_bridge.workflow_feedback_shadow_score.v0";

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
}
