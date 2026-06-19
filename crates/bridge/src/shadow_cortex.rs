use crate::seed_substrate as ab_seed_bridge;
use crate::seed_substrate::{SeedBackend, SubstrateConfig};
use ab_store::embedding::{EmbeddingBackend, HashBackend};
use ab_store::{IdentityWindow, McpToolCallFilter, McpToolCallStats, MemoryQueryStats, StateStore};
use anyhow::{anyhow, Result};
use serde::{Deserialize, Serialize};
use serde_json::json;
use std::collections::{BTreeMap, BTreeSet};
use std::fs::OpenOptions;
use std::io::Write;
use std::path::Path;
use std::sync::Arc;
use std::time::{SystemTime, UNIX_EPOCH};

const SIGNAL_SCHEMA_VERSION: u8 = 1;
const SHORT_TTL_SECS: u64 = 3_600;
const LONG_TTL_SECS: u64 = 86_400;
const SALIENCE_SATURATION_TOP_K: usize = 4;
// Saturation thresholds are lane-local proxies for each lane's salience cap.
// Keep them below the corresponding clamp ceiling so guarded verdicts remain reachable.
const HEURISTIC_SALIENCE_SATURATION_THRESHOLD: f64 = 0.75;
const SEED_SHADOW_SALIENCE_SATURATION_THRESHOLD: f64 = 0.945;
const SEED_RUNTIME_SALIENCE_MAX: f64 = 0.98;
const SEED_RUNTIME_SALIENCE_SATURATION_THRESHOLD: f64 = 0.975;
const SEED_RUNTIME_REPLAY_N: usize = 32;
const SEED_RUNTIME_REPLAY_D: usize = 64;

#[derive(Debug, Clone)]
pub struct ShadowCortexOptions {
    pub window_days: u32,
    pub source: String,
}

#[derive(Debug, Clone, Copy, Serialize, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "kebab-case")]
pub enum ShadowCortexMode {
    Off,
    Heuristic,
    SeedShadow,
    SeedRuntime,
}

impl ShadowCortexMode {
    fn from_env() -> Self {
        Self::from_value(std::env::var("AGENT_BRIDGE_SHADOW_CORTEX").ok().as_deref())
    }

    fn from_value(raw: Option<&str>) -> Self {
        match raw
            .map(str::trim)
            .filter(|s| !s.is_empty())
            .unwrap_or("heuristic")
        {
            "off" | "disabled" | "0" | "false" => Self::Off,
            "seed-shadow" | "seed_shadow" => Self::SeedShadow,
            "seed-runtime" | "seed_runtime" => Self::SeedRuntime,
            _ => Self::Heuristic,
        }
    }
}

#[derive(Debug, Clone, Copy, Serialize, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "snake_case")]
pub enum SignalScope {
    Memory,
    Tool,
    Forum,
    System,
}

#[derive(Debug, Clone, Copy, Serialize, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "snake_case")]
pub enum SignalType {
    Risk,
    Opportunity,
    Continuity,
    Anomaly,
    Handoff,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub struct AgentAttentionSignal {
    pub agent_shadow_cortex: u8,
    pub at: i64,
    pub scope: SignalScope,
    pub subject_id: String,
    pub signal_type: SignalType,
    pub salience: f64,
    pub reason_codes: Vec<String>,
    pub source_event_ids: Vec<String>,
    pub ttl_secs: u64,
    pub evidence: serde_json::Value,
    pub consumer_hints: Vec<String>,
    pub confidence: f64,
    pub summary: String,
    pub recommendation: String,
}

#[derive(Debug, Clone, Default, Serialize, Deserialize, PartialEq)]
pub struct ShadowCortexTotals {
    pub mcp_tool_calls: u64,
    pub mcp_tool_errors: u64,
    pub memory_queries: u64,
    pub memory_misses: u64,
    pub forum_posts: u64,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub struct ShadowCortexReport {
    pub agent_shadow_cortex: u8,
    pub mode: ShadowCortexMode,
    pub generated_at: i64,
    pub window_days: u32,
    pub window_secs: i64,
    pub requested_source: String,
    pub sources: Vec<String>,
    pub max_signals: usize,
    pub totals: ShadowCortexTotals,
    pub comparison: ShadowCortexComparison,
    pub signals: Vec<AgentAttentionSignal>,
    pub seed_shadow_signals: Vec<AgentAttentionSignal>,
    pub seed_runtime_signals: Vec<AgentAttentionSignal>,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub struct ShadowCortexWeeklySummary {
    pub agent_shadow_cortex: u8,
    pub mode: ShadowCortexMode,
    pub generated_at: i64,
    pub window_days: u32,
    pub requested_source: String,
    pub verdict: String,
    pub total_events: usize,
    pub totals: ShadowCortexTotals,
    pub lane_coverage: Vec<ShadowCortexLaneCoverage>,
    pub top_signal: Option<ShadowCortexWeeklySignal>,
    pub seed_shadow_top_signal: Option<ShadowCortexWeeklySignal>,
    pub seed_runtime_top_signal: Option<ShadowCortexWeeklySignal>,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub struct ShadowCortexWeeklySignal {
    pub scope: SignalScope,
    pub signal_type: SignalType,
    pub subject_id: String,
    pub salience: f64,
    pub reason_codes: Vec<String>,
    pub summary: String,
    pub recommendation: String,
}

#[derive(Debug, Clone, Default, Serialize, Deserialize, PartialEq)]
pub struct ShadowCortexComparison {
    pub verdict: String,
    pub notes: Vec<String>,
    pub lane_coverage: Vec<ShadowCortexLaneCoverage>,
    pub rank_deltas: Vec<ShadowCortexRankDelta>,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub struct ShadowCortexLaneCoverage {
    pub lane: String,
    pub state: String,
    pub produced_signals: usize,
    pub covered_events: usize,
    pub total_events: usize,
    pub coverage: f64,
    pub unique_salience_values: usize,
    pub rank_tie_state: String,
    pub salience_saturation_state: String,
    pub top_k_cap_hits: usize,
    pub top_k_size: usize,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub struct ShadowCortexRankDelta {
    pub source_event_id: String,
    pub subject_id: String,
    pub heuristic_rank: Option<usize>,
    pub heuristic_salience: Option<f64>,
    pub seed_shadow_rank: Option<usize>,
    pub seed_shadow_salience: Option<f64>,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub struct ShadowCortexEvent {
    pub agent_shadow_cortex: u8,
    pub event_id: String,
    pub at: i64,
    pub source: String,
    pub scope: SignalScope,
    pub subject_id: String,
    pub features: serde_json::Value,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub struct ShadowCortexReplayFixture {
    pub agent_shadow_cortex: u8,
    pub mode: ShadowCortexMode,
    pub captured_at: i64,
    pub window_days: u32,
    pub window_secs: i64,
    pub requested_source: String,
    pub sources: Vec<String>,
    pub mcp_dispatch: Option<Vec<McpToolCallStats>>,
    pub memory_query_log: Option<MemoryQueryStats>,
    pub forum_window: Option<IdentityWindow>,
    pub events: Vec<ShadowCortexEvent>,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub struct ShadowCortexFeedbackRecord {
    pub agent_shadow_cortex: u8,
    pub recorded_at: i64,
    pub decision: String,
    pub signal_id: String,
    pub source_event_ids: Vec<String>,
    pub actor: String,
    pub note: Option<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub struct ShadowCortexFeedbackSummary {
    pub path: String,
    pub window_secs: i64,
    pub total_records: usize,
    pub window_records: usize,
    pub accepted: usize,
    pub ignored: usize,
    pub latest: Option<ShadowCortexFeedbackRecord>,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
enum ShadowSource {
    McpDispatch,
    MemoryQueryLog,
    ForumPosts,
}

impl ShadowSource {
    fn as_str(self) -> &'static str {
        match self {
            Self::McpDispatch => "mcp_dispatch",
            Self::MemoryQueryLog => "memory_query_log",
            Self::ForumPosts => "forum_posts",
        }
    }
}

pub fn default_feedback_path() -> std::path::PathBuf {
    std::env::var_os("AGENT_BRIDGE_SHADOW_CORTEX_FEEDBACK_PATH")
        .map(std::path::PathBuf::from)
        .unwrap_or_else(|| shadow_cortex_cache_dir().join("feedback.jsonl"))
}

pub fn append_feedback_record(
    path: Option<&Path>,
    decision: &str,
    signal_id: &str,
    source_event_ids: Vec<String>,
    actor: &str,
    note: Option<&str>,
) -> Result<ShadowCortexFeedbackRecord> {
    let decision = normalize_feedback_decision(decision)?;
    let signal_id = signal_id.trim();
    if signal_id.is_empty() {
        return Err(anyhow!("signal_id is required"));
    }
    let actor = actor.trim();
    if actor.is_empty() {
        return Err(anyhow!("actor is required"));
    }
    let record = ShadowCortexFeedbackRecord {
        agent_shadow_cortex: SIGNAL_SCHEMA_VERSION,
        recorded_at: now_secs(),
        decision,
        signal_id: signal_id.to_string(),
        source_event_ids: source_event_ids
            .into_iter()
            .map(|s| s.trim().to_string())
            .filter(|s| !s.is_empty())
            .collect(),
        actor: actor.to_string(),
        note: note
            .map(str::trim)
            .filter(|s| !s.is_empty())
            .map(str::to_string),
    };

    let path = path
        .map(Path::to_path_buf)
        .unwrap_or_else(default_feedback_path);
    if let Some(parent) = path.parent() {
        std::fs::create_dir_all(parent)
            .map_err(|e| anyhow!("create shadow-cortex feedback dir at {parent:?}: {e}"))?;
    }
    let mut file = OpenOptions::new()
        .create(true)
        .append(true)
        .open(&path)
        .map_err(|e| anyhow!("open shadow-cortex feedback log at {path:?}: {e}"))?;
    serde_json::to_writer(&mut file, &record)?;
    file.write_all(b"\n")?;
    Ok(record)
}

pub fn read_feedback_records(
    path: Option<&Path>,
    limit: usize,
) -> Result<Vec<ShadowCortexFeedbackRecord>> {
    let path = path
        .map(Path::to_path_buf)
        .unwrap_or_else(default_feedback_path);
    if !path.exists() {
        return Ok(Vec::new());
    }
    let body = std::fs::read_to_string(&path)
        .map_err(|e| anyhow!("read shadow-cortex feedback log at {path:?}: {e}"))?;
    let mut records = Vec::new();
    for (idx, line) in body.lines().enumerate() {
        let line = line.trim();
        if line.is_empty() {
            continue;
        }
        let record = serde_json::from_str::<ShadowCortexFeedbackRecord>(line)
            .map_err(|e| anyhow!("parse shadow-cortex feedback line {}: {e}", idx + 1))?;
        records.push(record);
    }
    let limit = limit.max(1);
    if records.len() > limit {
        records = records.split_off(records.len() - limit);
    }
    Ok(records)
}

pub fn feedback_summary(
    path: Option<&Path>,
    window_secs: i64,
    now: i64,
) -> Result<ShadowCortexFeedbackSummary> {
    let path = path
        .map(Path::to_path_buf)
        .unwrap_or_else(default_feedback_path);
    let records = read_feedback_records(Some(&path), usize::MAX)?;
    let window_start = now - window_secs.max(1);
    let window_records: Vec<ShadowCortexFeedbackRecord> = records
        .iter()
        .filter(|record| record.recorded_at >= window_start && record.recorded_at <= now)
        .cloned()
        .collect();
    let accepted = window_records
        .iter()
        .filter(|record| record.decision == "accepted")
        .count();
    let ignored = window_records
        .iter()
        .filter(|record| record.decision == "ignored")
        .count();
    Ok(ShadowCortexFeedbackSummary {
        path: path.display().to_string(),
        window_secs: window_secs.max(1),
        total_records: records.len(),
        window_records: window_records.len(),
        accepted,
        ignored,
        latest: window_records.last().cloned(),
    })
}

pub async fn collect_shadow_cortex_fixture(
    store: &dyn StateStore,
    opts: ShadowCortexOptions,
) -> Result<ShadowCortexReplayFixture> {
    let window_days = opts.window_days.clamp(1, 365);
    let window_secs = window_days as i64 * 86_400;
    let captured_at = now_secs();
    let mode = ShadowCortexMode::from_env();
    let sources = parse_sources(&opts.source)?;
    let source_names: Vec<String> = sources.iter().map(|s| s.as_str().to_string()).collect();
    let mut fixture = ShadowCortexReplayFixture {
        agent_shadow_cortex: SIGNAL_SCHEMA_VERSION,
        mode,
        captured_at,
        window_days,
        window_secs,
        requested_source: opts.source,
        sources: source_names,
        mcp_dispatch: None,
        memory_query_log: None,
        forum_window: None,
        events: Vec::new(),
    };

    if mode == ShadowCortexMode::Off {
        return Ok(fixture);
    }

    if sources.contains(&ShadowSource::McpDispatch) {
        let source_filter = if requested_source_is_codex(&fixture.requested_source) {
            Some("codex".to_string())
        } else {
            None
        };
        fixture.mcp_dispatch = Some(
            store
                .mcp_tool_call_stats_filtered(
                    fixture.window_secs,
                    50,
                    McpToolCallFilter {
                        source: source_filter.clone(),
                        ..McpToolCallFilter::default()
                    },
                )
                .await?,
        );
    }
    if sources.contains(&ShadowSource::MemoryQueryLog) {
        fixture.memory_query_log = Some(store.memory_query_stats(fixture.window_secs).await?);
    }
    if sources.contains(&ShadowSource::ForumPosts) {
        fixture.forum_window = Some(
            store
                .identity_window(captured_at - fixture.window_secs, captured_at)
                .await?,
        );
    }

    fixture.events = encode_shadow_events(&fixture);
    Ok(fixture)
}

pub fn build_shadow_cortex_report_from_fixture(
    fixture: &ShadowCortexReplayFixture,
    max_signals: usize,
) -> Result<ShadowCortexReport> {
    let max_signals = max_signals.clamp(1, 200);
    let mut report = ShadowCortexReport {
        agent_shadow_cortex: SIGNAL_SCHEMA_VERSION,
        mode: fixture.mode,
        generated_at: fixture.captured_at,
        window_days: fixture.window_days,
        window_secs: fixture.window_secs,
        requested_source: fixture.requested_source.clone(),
        sources: fixture.sources.clone(),
        max_signals,
        totals: totals_from_fixture(fixture),
        comparison: ShadowCortexComparison::default(),
        signals: Vec::new(),
        seed_shadow_signals: Vec::new(),
        seed_runtime_signals: Vec::new(),
    };

    if fixture.mode == ShadowCortexMode::Off {
        report.comparison = build_shadow_comparison(fixture, &report.signals, &[], &[]);
        return Ok(report);
    }

    let mut heuristic_signals = Vec::new();

    if let Some(stats) = &fixture.mcp_dispatch {
        if stats.is_empty() {
            push_mcp_quiet_signal(
                report.generated_at,
                report.window_secs,
                requested_source_is_codex(&report.requested_source),
                &mut heuristic_signals,
            );
        } else {
            collect_mcp_stat_signals(
                stats,
                requested_source_is_codex(&report.requested_source).then_some("codex"),
                report.generated_at,
                &mut heuristic_signals,
            );
        }
    }
    if let Some(stats) = &fixture.memory_query_log {
        collect_memory_stat_signals(stats, report.generated_at, &mut heuristic_signals);
    }
    if let Some(window) = &fixture.forum_window {
        collect_forum_window_signals(window, report.generated_at, &mut heuristic_signals);
    }

    let mut seed_shadow_signals = seed_shadow_signals_from_fixture(fixture);
    let mut seed_runtime_signals = seed_runtime_signals_from_fixture(fixture);
    report.comparison = build_shadow_comparison(
        fixture,
        &heuristic_signals,
        &seed_shadow_signals,
        &seed_runtime_signals,
    );

    report.signals = heuristic_signals;
    finalize_signals(&mut report.signals, max_signals);
    finalize_signals(&mut seed_shadow_signals, max_signals);
    report.seed_shadow_signals = seed_shadow_signals;
    finalize_signals(&mut seed_runtime_signals, max_signals);
    report.seed_runtime_signals = seed_runtime_signals;
    Ok(report)
}

pub fn weekly_summary(report: &ShadowCortexReport) -> ShadowCortexWeeklySummary {
    ShadowCortexWeeklySummary {
        agent_shadow_cortex: report.agent_shadow_cortex,
        mode: report.mode,
        generated_at: report.generated_at,
        window_days: report.window_days,
        requested_source: report.requested_source.clone(),
        verdict: report.comparison.verdict.clone(),
        total_events: report
            .comparison
            .lane_coverage
            .iter()
            .map(|lane| lane.total_events)
            .max()
            .unwrap_or(0),
        totals: report.totals.clone(),
        lane_coverage: report.comparison.lane_coverage.clone(),
        top_signal: weekly_signal(&report.signals),
        seed_shadow_top_signal: weekly_signal(&report.seed_shadow_signals),
        seed_runtime_top_signal: weekly_signal(&report.seed_runtime_signals),
    }
}

pub fn print_shadow_cortex_report(report: &ShadowCortexReport, input_path: &Path) {
    println!("# Agent Shadow Cortex — heuristic attention report");
    println!("Input: {}", input_path.display());
    println!(
        "Window: {}d | Sources: {} | Signals: {}",
        report.window_days,
        report.sources.join(", "),
        report.signals.len()
    );
    println!(
        "Totals: tool_calls={} tool_errors={} memory_queries={} memory_misses={} forum_posts={}",
        report.totals.mcp_tool_calls,
        report.totals.mcp_tool_errors,
        report.totals.memory_queries,
        report.totals.memory_misses,
        report.totals.forum_posts
    );
    if !report.comparison.verdict.is_empty() {
        println!("Verdict: {}", report.comparison.verdict);
        if !report.comparison.lane_coverage.is_empty() {
            println!("Coverage:");
            for lane in &report.comparison.lane_coverage {
                println!(
                    "- {}: {} ({}/{}, {:.0}%) rank_tie={} saturation={} top_k_cap_hits={}/{}",
                    lane.lane,
                    lane.state,
                    lane.covered_events,
                    lane.total_events,
                    lane.coverage * 100.0,
                    lane.rank_tie_state,
                    lane.salience_saturation_state,
                    lane.top_k_cap_hits,
                    lane.top_k_size
                );
            }
        }
    }
    println!();

    if report.mode == ShadowCortexMode::Off {
        println!("Shadow cortex is off via AGENT_BRIDGE_SHADOW_CORTEX=off.");
        return;
    }

    if report.signals.is_empty() {
        println!("No attention signals in this window.");
        return;
    }

    for (idx, signal) in report.signals.iter().enumerate() {
        println!(
            "{}. [{:?}/{:?}] {} ({:.2})",
            idx + 1,
            signal.scope,
            signal.signal_type,
            signal.subject_id,
            signal.salience
        );
        println!("   {}", signal.summary);
        println!("   evidence: {}", compact_json(&signal.evidence));
        println!("   next: {}", signal.recommendation);
    }

    if !report.seed_shadow_signals.is_empty() {
        println!();
        println!("# seed-shadow top signals (deterministic, no runtime)");
        for (idx, signal) in report.seed_shadow_signals.iter().take(3).enumerate() {
            println!(
                "{}. [{:?}/{:?}] {} ({:.2})",
                idx + 1,
                signal.scope,
                signal.signal_type,
                signal.subject_id,
                signal.salience
            );
            println!("   {}", signal.summary);
        }
    }
    if !report.seed_runtime_signals.is_empty() {
        println!();
        println!("# seed-runtime top signals (ephemeral in-process replay)");
        for (idx, signal) in report.seed_runtime_signals.iter().take(3).enumerate() {
            println!(
                "{}. [{:?}/{:?}] {} ({:.2})",
                idx + 1,
                signal.scope,
                signal.signal_type,
                signal.subject_id,
                signal.salience
            );
            println!("   {}", signal.summary);
        }
    }
}

fn weekly_signal(signals: &[AgentAttentionSignal]) -> Option<ShadowCortexWeeklySignal> {
    signals
        .iter()
        .find(|signal| {
            signal
                .consumer_hints
                .iter()
                .any(|hint| hint == "show_in_dream_weekly")
        })
        .or_else(|| signals.first())
        .map(|signal| ShadowCortexWeeklySignal {
            scope: signal.scope,
            signal_type: signal.signal_type,
            subject_id: signal.subject_id.clone(),
            salience: signal.salience,
            reason_codes: signal.reason_codes.clone(),
            summary: signal.summary.clone(),
            recommendation: signal.recommendation.clone(),
        })
}

fn totals_from_fixture(fixture: &ShadowCortexReplayFixture) -> ShadowCortexTotals {
    let (mcp_tool_calls, mcp_tool_errors) = fixture
        .mcp_dispatch
        .as_ref()
        .map(|stats| {
            (
                stats.iter().map(|s| s.call_count).sum(),
                stats.iter().map(|s| s.error_count).sum(),
            )
        })
        .unwrap_or((0, 0));
    let (memory_queries, memory_misses) = fixture
        .memory_query_log
        .as_ref()
        .map(|stats| (stats.total_queries, stats.misses))
        .unwrap_or((0, 0));
    let forum_posts = fixture
        .forum_window
        .as_ref()
        .map(|window| window.forum_posts)
        .unwrap_or(0);
    ShadowCortexTotals {
        mcp_tool_calls,
        mcp_tool_errors,
        memory_queries,
        memory_misses,
        forum_posts,
    }
}

fn encode_shadow_events(fixture: &ShadowCortexReplayFixture) -> Vec<ShadowCortexEvent> {
    let mut events = Vec::new();
    let codex_source = requested_source_is_codex(&fixture.requested_source);

    if let Some(stats) = &fixture.mcp_dispatch {
        if stats.is_empty() {
            events.push(shadow_event(
                "mcp_dispatch:window:empty".to_string(),
                fixture.captured_at,
                "mcp_dispatch",
                SignalScope::Tool,
                "mcp_dispatch",
                json!({
                    "window_secs": fixture.window_secs,
                    "filter_source": codex_source.then_some("codex"),
                    "call_count": 0
                }),
            ));
        }
        for s in stats {
            let error_rate = rate(s.error_count, s.call_count);
            if s.error_count > 0 {
                events.push(shadow_event(
                    format!("mcp_dispatch:{}:errors", s.tool_name),
                    fixture.captured_at,
                    "mcp_dispatch",
                    SignalScope::Tool,
                    &s.tool_name,
                    json!({
                        "call_count": s.call_count,
                        "error_count": s.error_count,
                        "error_rate": error_rate,
                        "p95_duration_ms": s.p95_duration_ms
                    }),
                ));
            }
            if s.call_count >= 3 && s.p95_duration_ms >= 1_000 {
                events.push(shadow_event(
                    format!("mcp_dispatch:{}:latency", s.tool_name),
                    fixture.captured_at,
                    "mcp_dispatch",
                    SignalScope::Tool,
                    &s.tool_name,
                    json!({
                        "call_count": s.call_count,
                        "avg_duration_ms": s.avg_duration_ms,
                        "p95_duration_ms": s.p95_duration_ms
                    }),
                ));
            }
            if s.call_count >= 3 && s.avg_result_size >= 24_000.0 {
                events.push(shadow_event(
                    format!("mcp_dispatch:{}:result_size", s.tool_name),
                    fixture.captured_at,
                    "mcp_dispatch",
                    SignalScope::Tool,
                    &s.tool_name,
                    json!({
                        "call_count": s.call_count,
                        "avg_result_size": s.avg_result_size
                    }),
                ));
            }
            if codex_source && s.call_count >= 3 && is_codex_native_overlap(&s.tool_name) {
                events.push(shadow_event(
                    format!("mcp_dispatch:{}:native_overlap", s.tool_name),
                    fixture.captured_at,
                    "mcp_dispatch",
                    SignalScope::Tool,
                    &s.tool_name,
                    json!({
                        "call_count": s.call_count,
                        "filter_source": "codex"
                    }),
                ));
            }
        }
    }

    if let Some(stats) = &fixture.memory_query_log {
        if stats.total_queries == 0 {
            events.push(shadow_event(
                "memory_query_log:window:empty".to_string(),
                fixture.captured_at,
                "memory_query_log",
                SignalScope::Memory,
                "memory_query_log",
                json!({
                    "window_start": stats.window_start,
                    "window_end": stats.window_end,
                    "total_queries": 0
                }),
            ));
        } else {
            events.push(shadow_event(
                "memory_query_log:window:hit_rate".to_string(),
                fixture.captured_at,
                "memory_query_log",
                SignalScope::Memory,
                "memory_query_log",
                json!({
                    "total_queries": stats.total_queries,
                    "hits": stats.hits,
                    "misses": stats.misses,
                    "hit_rate": stats.hit_rate,
                    "by_kind": stats.by_kind
                }),
            ));
            events.push(shadow_event(
                "memory_query_log:window:latency".to_string(),
                fixture.captured_at,
                "memory_query_log",
                SignalScope::Memory,
                "memory_query_latency",
                json!({
                    "total_queries": stats.total_queries,
                    "p50_duration_us": stats.p50_duration_us,
                    "p95_duration_us": stats.p95_duration_us
                }),
            ));
            for (query, count) in stats.top_miss_queries.iter().take(5) {
                events.push(shadow_event(
                    format!("memory_query_log:miss:{query}"),
                    fixture.captured_at,
                    "memory_query_log",
                    SignalScope::Memory,
                    &format!("memory_miss:{query}"),
                    json!({
                        "query": query,
                        "miss_count": count
                    }),
                ));
            }
        }
    }

    if let Some(window) = &fixture.forum_window {
        if window.forum_posts == 0 {
            events.push(shadow_event(
                "forum_posts:window:empty".to_string(),
                fixture.captured_at,
                "forum_posts",
                SignalScope::Forum,
                "forum_posts",
                json!({
                    "window_start": window.window_start,
                    "window_end": window.window_end,
                    "forum_posts": 0
                }),
            ));
        } else {
            events.push(shadow_event(
                "forum_posts:window:activity".to_string(),
                fixture.captured_at,
                "forum_posts",
                SignalScope::Forum,
                "forum_posts",
                json!({
                    "forum_posts": window.forum_posts,
                    "forum_kinds": window.forum_kinds,
                    "forum_avg_body_len": window.forum_avg_body_len
                }),
            ));
            if window.forum_posts >= 5 && window.forum_avg_body_len < 40.0 {
                events.push(shadow_event(
                    "forum_posts:window:avg_body_len".to_string(),
                    fixture.captured_at,
                    "forum_posts",
                    SignalScope::Forum,
                    "forum_posts",
                    json!({
                        "forum_posts": window.forum_posts,
                        "forum_avg_body_len": window.forum_avg_body_len
                    }),
                ));
            }
        }
    }

    events.sort_by(|a, b| a.event_id.cmp(&b.event_id));
    events
}

fn shadow_event(
    event_id: String,
    at: i64,
    source: &str,
    scope: SignalScope,
    subject_id: &str,
    features: serde_json::Value,
) -> ShadowCortexEvent {
    ShadowCortexEvent {
        agent_shadow_cortex: SIGNAL_SCHEMA_VERSION,
        event_id,
        at,
        source: source.to_string(),
        scope,
        subject_id: subject_id.to_string(),
        features,
    }
}

fn push_mcp_quiet_signal(
    generated_at: i64,
    window_secs: i64,
    codex_source: bool,
    out: &mut Vec<AgentAttentionSignal>,
) {
    out.push(signal(
        generated_at,
        SignalScope::Tool,
        "mcp_dispatch".to_string(),
        SignalType::Continuity,
        0.25,
        &["mcp_dispatch_quiet"],
        vec!["mcp_dispatch:window:empty".to_string()],
        LONG_TTL_SECS,
        json!({
            "source": "mcp_dispatch",
            "window_secs": window_secs,
            "filter_source": codex_source.then_some("codex"),
            "call_count": 0
        }),
        &["show_in_dream_weekly"],
        0.55,
        "No MCP tool calls were observed in the selected window.",
        "Keep observing before changing the tool surface.",
    ));
}

fn seed_shadow_signals_from_fixture(
    fixture: &ShadowCortexReplayFixture,
) -> Vec<AgentAttentionSignal> {
    if fixture.mode == ShadowCortexMode::Off {
        return Vec::new();
    }

    let mut out = Vec::new();
    for event in &fixture.events {
        if let Some(signal) = seed_shadow_signal_for_event(fixture.captured_at, event) {
            out.push(signal);
        }
    }
    finalize_signals(&mut out, 200);
    out
}

fn seed_shadow_signal_for_event(
    at: i64,
    event: &ShadowCortexEvent,
) -> Option<AgentAttentionSignal> {
    let event_id = event.event_id.as_str();
    let (signal_type, base, reason_codes, summary, recommendation) = if event_id.ends_with(":empty")
    {
        (
            SignalType::Continuity,
            0.24,
            vec!["seed_shadow", "quiet_window"],
            "The deterministic shadow scorer saw no events for this source window.",
            "Treat this lane as low evidence and avoid drawing comparative conclusions.",
        )
    } else if event_id.contains(":errors") {
        (
            SignalType::Risk,
            0.56,
            vec!["seed_shadow", "error_attention"],
            "The deterministic shadow scorer prioritised an error-bearing event.",
            "Inspect error coverage before using this lane as a product hint.",
        )
    } else if event_id.contains(":latency") {
        (
            SignalType::Opportunity,
            0.50,
            vec!["seed_shadow", "latency_attention"],
            "The deterministic shadow scorer prioritised a latency-heavy event.",
            "Consider whether latency is real user pain or expected long-running work.",
        )
    } else if event_id.contains(":result_size") {
        (
            SignalType::Opportunity,
            0.48,
            vec!["seed_shadow", "context_pressure_attention"],
            "The deterministic shadow scorer prioritised a context-pressure event.",
            "Check whether a summary-first output would preserve utility.",
        )
    } else if event_id.contains(":native_overlap") {
        (
            SignalType::Opportunity,
            0.46,
            vec!["seed_shadow", "routing_attention"],
            "The deterministic shadow scorer noticed a native-overlap routing event.",
            "Verify whether Agent-Bridge adds local context beyond Codex native tools.",
        )
    } else if event_id == "memory_query_log:window:hit_rate" {
        (
            SignalType::Risk,
            0.54,
            vec!["seed_shadow", "recall_attention"],
            "The deterministic shadow scorer prioritised recall pressure.",
            "Fix capture/query fit before changing rankers.",
        )
    } else if event_id.starts_with("memory_query_log:miss:") {
        (
            SignalType::Risk,
            0.50,
            vec!["seed_shadow", "repeated_miss_attention"],
            "The deterministic shadow scorer noticed a repeated memory miss.",
            "Add aliases, tags, or a compact memory only if the miss reflects useful intent.",
        )
    } else if event_id == "memory_query_log:window:latency" {
        (
            SignalType::Opportunity,
            0.44,
            vec!["seed_shadow", "recall_latency_attention"],
            "The deterministic shadow scorer noticed recall latency.",
            "Use this as a performance hint only with enough recall traffic.",
        )
    } else if event_id == "forum_posts:window:activity" {
        (
            SignalType::Handoff,
            0.46,
            vec!["seed_shadow", "coordination_attention"],
            "The deterministic shadow scorer noticed cross-agent forum activity.",
            "Check coordination state before assuming single-agent ownership.",
        )
    } else if event_id == "forum_posts:window:avg_body_len" {
        (
            SignalType::Risk,
            0.42,
            vec!["seed_shadow", "coordination_context_attention"],
            "The deterministic shadow scorer noticed low-context collaboration posts.",
            "Prefer explicit handoff summaries while parallel work is active.",
        )
    } else {
        return None;
    };

    let salience = seed_shadow_salience(base, event);
    Some(signal(
        at,
        event.scope,
        event.subject_id.clone(),
        signal_type,
        salience,
        &reason_codes,
        vec![event.event_id.clone()],
        SHORT_TTL_SECS,
        json!({
            "source": event.source,
            "source_event_id": event.event_id,
            "scorer": "seed_shadow",
            "features": event.features
        }),
        &["show_in_dream_weekly"],
        0.52,
        summary,
        recommendation,
    ))
}

fn seed_shadow_salience(base: f64, event: &ShadowCortexEvent) -> f64 {
    let mut score = base;
    match event.source.as_str() {
        "memory_query_log" => score += 0.08,
        "mcp_dispatch" => score += 0.05,
        "forum_posts" => score += 0.04,
        _ => {}
    }

    score += number_feature(&event.features, "error_rate").unwrap_or(0.0) * 0.24;
    if let Some(hit_rate) = number_feature(&event.features, "hit_rate") {
        score += (0.55 - hit_rate).max(0.0) * 0.32;
    }
    if let Some(p95_ms) = number_feature(&event.features, "p95_duration_ms") {
        score += (p95_ms / 10_000.0).min(0.18);
    }
    if let Some(p95_us) = number_feature(&event.features, "p95_duration_us") {
        score += (p95_us / 1_000_000.0).min(0.16);
    }
    if let Some(miss_count) = number_feature(&event.features, "miss_count") {
        score += (miss_count / 10.0).min(0.16);
    }
    if let Some(call_count) = number_feature(&event.features, "call_count").filter(|v| *v > 0.0) {
        score += (call_count.log10() / 20.0).min(0.10);
    }
    if let Some(forum_posts) = number_feature(&event.features, "forum_posts").filter(|v| *v > 0.0) {
        score += (forum_posts.log10() / 18.0).min(0.12);
    }
    score.clamp(0.0, 0.95)
}

fn seed_runtime_signals_from_fixture(
    fixture: &ShadowCortexReplayFixture,
) -> Vec<AgentAttentionSignal> {
    if fixture.mode != ShadowCortexMode::SeedRuntime || fixture.events.is_empty() {
        return Vec::new();
    }

    // Feasibility probe only: local, ephemeral Seed runtime. This does
    // not install the global substrate, does not write snapshots, and
    // never calls the AiOT production daemon.
    let backend = SeedBackend::wrap_with(
        Arc::new(HashBackend),
        SubstrateConfig {
            n: SEED_RUNTIME_REPLAY_N,
            d: SEED_RUNTIME_REPLAY_D,
            state_noise: 0.0,
            lr: 0.01,
        },
    );
    let total_events = fixture.events.len().max(1);
    let mut out = Vec::with_capacity(fixture.events.len());

    for (idx, event) in fixture.events.iter().enumerate() {
        let text = seed_runtime_event_text(event);
        let _ = EmbeddingBackend::perceive(&backend, &text, &event.event_id);
        let stats = backend.stats();
        let neighbors = backend.neighbors_of(&event.event_id, 3);
        let salience = seed_runtime_salience(
            &stats,
            event,
            idx,
            total_events,
            neighbors.iter().map(|(_, weight)| *weight as f64).sum(),
        );
        let (signal_type, summary, recommendation) = seed_runtime_signal_copy(event);
        out.push(signal(
            fixture.captured_at,
            event.scope,
            event.subject_id.clone(),
            signal_type,
            salience,
            &[
                "seed_runtime",
                "ephemeral_replay",
                "runtime_surprise_attention",
            ],
            vec![event.event_id.clone()],
            SHORT_TTL_SECS,
            json!({
                "source": event.source,
                "source_event_id": event.event_id,
                "scorer": "seed_runtime_ephemeral",
                "features": event.features,
                "substrate": {
                    "backend": stats.backend_name,
                    "n": stats.n,
                    "d": stats.d,
                    "step_count": stats.step_count,
                    "last_surprise_mean": stats.last_surprise_mean,
                    "last_surprise_max": stats.last_surprise_max,
                    "connection_mean_abs": stats.connection_mean_abs,
                    "neighbors": neighbors,
                    "mutates_global_substrate": false,
                    "writes_snapshot": false,
                    "calls_daemon": false
                }
            }),
            &["show_in_dream_weekly"],
            0.46,
            summary,
            recommendation,
        ));
    }
    finalize_signals(&mut out, 200);
    out
}

fn seed_runtime_event_text(event: &ShadowCortexEvent) -> String {
    format!(
        "shadow-cortex event\nsource: {}\nscope: {:?}\nsubject: {}\nevent: {}\nfeatures: {}",
        event.source,
        event.scope,
        event.subject_id,
        event.event_id,
        compact_json(&event.features)
    )
}

fn seed_runtime_signal_copy(event: &ShadowCortexEvent) -> (SignalType, &'static str, &'static str) {
    let event_id = event.event_id.as_str();
    if event_id.ends_with(":empty") {
        (
            SignalType::Continuity,
            "The in-process Seed replay saw an empty observation window.",
            "Treat this as a low-evidence continuity signal, not a product hint.",
        )
    } else if event_id.contains(":errors") {
        (
            SignalType::Risk,
            "The in-process Seed replay assigned attention to an error-bearing event.",
            "Inspect whether the error is fresh, repeated, and actionable before changing routing.",
        )
    } else if event_id.contains(":latency") {
        (
            SignalType::Opportunity,
            "The in-process Seed replay assigned attention to a latency-heavy event.",
            "Compare against expected long-running work before optimizing the surface.",
        )
    } else if event_id.contains(":result_size") {
        (
            SignalType::Opportunity,
            "The in-process Seed replay assigned attention to a context-pressure event.",
            "Prefer compact result shaping only if the large payload is not carrying useful evidence.",
        )
    } else if event_id.contains(":native_overlap") {
        (
            SignalType::Opportunity,
            "The in-process Seed replay assigned attention to native-tool overlap.",
            "Keep Agent-Bridge exposure focused on capabilities Codex cannot already perform natively.",
        )
    } else if event_id.starts_with("memory_query_log:miss:") {
        (
            SignalType::Risk,
            "The in-process Seed replay assigned attention to a repeated memory miss.",
            "Only add aliases or compact memories when the miss reflects durable future intent.",
        )
    } else if event_id.starts_with("memory_query_log:") {
        (
            SignalType::Risk,
            "The in-process Seed replay assigned attention to recall behavior.",
            "Use this as a recall-fit probe before changing retrieval rankers.",
        )
    } else if event_id.starts_with("forum_posts:") {
        (
            SignalType::Handoff,
            "The in-process Seed replay assigned attention to collaboration activity.",
            "Check the board before taking ownership of nearby work.",
        )
    } else {
        (
            SignalType::Anomaly,
            "The in-process Seed replay assigned attention to an uncategorized event.",
            "Inspect the raw event before deriving a workflow decision.",
        )
    }
}

fn seed_runtime_salience(
    stats: &ab_seed_bridge::SubstrateStats,
    event: &ShadowCortexEvent,
    idx: usize,
    total_events: usize,
    neighbor_weight_sum: f64,
) -> f64 {
    let surprise = stats.last_surprise_mean.max(0.0) as f64;
    let surprise_spread = (stats.last_surprise_max - stats.last_surprise_mean).max(0.0) as f64;
    let event_pressure = seed_runtime_event_pressure(event);
    let neighbor_pressure = neighbor_weight_sum.min(1.0) * 0.08;
    let order_tiebreak = if total_events > 1 {
        (idx as f64 / (total_events - 1) as f64) * 0.03
    } else {
        0.0
    };

    (0.24
        + surprise.min(1.0) * 0.24
        + surprise_spread.min(1.0) * 0.10
        + event_pressure
        + neighbor_pressure
        + order_tiebreak)
        .clamp(0.0, SEED_RUNTIME_SALIENCE_MAX)
}

fn seed_runtime_event_pressure(event: &ShadowCortexEvent) -> f64 {
    let mut score = 0.0;
    score += number_feature(&event.features, "error_rate").unwrap_or(0.0) * 0.22;
    if let Some(hit_rate) = number_feature(&event.features, "hit_rate") {
        score += (0.55 - hit_rate).max(0.0) * 0.24;
    }
    if let Some(p95_ms) = number_feature(&event.features, "p95_duration_ms") {
        score += (p95_ms / 12_000.0).min(0.12);
    }
    if let Some(p95_us) = number_feature(&event.features, "p95_duration_us") {
        score += (p95_us / 1_250_000.0).min(0.12);
    }
    if let Some(miss_count) = number_feature(&event.features, "miss_count") {
        score += (miss_count / 12.0).min(0.12);
    }
    if let Some(call_count) = number_feature(&event.features, "call_count").filter(|v| *v > 0.0) {
        score += (call_count.log10() / 25.0).min(0.08);
    }
    if let Some(forum_posts) = number_feature(&event.features, "forum_posts").filter(|v| *v > 0.0) {
        score += (forum_posts.log10() / 20.0).min(0.08);
    }
    score.min(0.28)
}

fn build_shadow_comparison(
    fixture: &ShadowCortexReplayFixture,
    heuristic_signals: &[AgentAttentionSignal],
    seed_shadow_signals: &[AgentAttentionSignal],
    seed_runtime_signals: &[AgentAttentionSignal],
) -> ShadowCortexComparison {
    let heuristic = lane_coverage("heuristic", &fixture.events, heuristic_signals, true);
    let seed_shadow = lane_coverage("seed_shadow", &fixture.events, seed_shadow_signals, true);
    let seed_runtime_enabled = fixture.mode == ShadowCortexMode::SeedRuntime;
    let seed_runtime = lane_coverage(
        "seed_runtime",
        &fixture.events,
        seed_runtime_signals,
        seed_runtime_enabled,
    );
    let lane_coverage = vec![heuristic.clone(), seed_shadow.clone(), seed_runtime.clone()];
    let mut notes = Vec::new();

    if seed_runtime.state == "not_enabled" {
        notes.push(
            "seed_runtime is not evaluated unless AGENT_BRIDGE_SHADOW_CORTEX=seed-runtime"
                .to_string(),
        );
    } else {
        notes.push(
            "seed_runtime used an ephemeral in-process SeedBackend replay; no global substrate, snapshot, or daemon was touched"
                .to_string(),
        );
    }
    if seed_shadow.state == "ablation_state" || seed_shadow.state == "insufficient_coverage" {
        notes.push(
            "seed_shadow coverage is below threshold; skip correlation-style conclusions"
                .to_string(),
        );
    }
    if seed_shadow.rank_tie_state != "ok" || heuristic.rank_tie_state != "ok" {
        notes.push(
            "rank-tie guardrail is active; do not treat raw rank correlation as evidence"
                .to_string(),
        );
    }
    if salience_saturation_is_guarded(&seed_shadow) || salience_saturation_is_guarded(&heuristic) {
        notes.push(
            "top-K salience saturation guardrail is active; inspect capped signals before treating rank order as evidence"
                .to_string(),
        );
    }
    notes.push("seed_shadow remains deterministic and shadow-only".to_string());

    ShadowCortexComparison {
        verdict: comparison_verdict(
            &fixture.events,
            &heuristic,
            &seed_shadow,
            &seed_runtime,
            seed_runtime_enabled,
        ),
        notes,
        lane_coverage,
        rank_deltas: rank_deltas(heuristic_signals, seed_shadow_signals, 12),
    }
}

fn lane_coverage(
    lane: &str,
    events: &[ShadowCortexEvent],
    signals: &[AgentAttentionSignal],
    enabled: bool,
) -> ShadowCortexLaneCoverage {
    let event_ids: BTreeSet<&str> = events.iter().map(|e| e.event_id.as_str()).collect();
    let covered: BTreeSet<&str> = signals
        .iter()
        .flat_map(|s| s.source_event_ids.iter().map(String::as_str))
        .filter(|id| event_ids.contains(id))
        .collect();
    let total_events = event_ids.len();
    let covered_events = covered.len();
    let produced_signals = signals.len();
    let coverage = if total_events == 0 {
        0.0
    } else {
        covered_events as f64 / total_events as f64
    };
    let unique_salience_values: BTreeSet<String> = signals
        .iter()
        .map(|s| format!("{:.4}", s.salience))
        .collect();
    let unique_salience_values = unique_salience_values.len();
    let rank_tie_state = if produced_signals >= 2 && unique_salience_values <= 1 {
        "degenerate_rank_tie"
    } else if produced_signals >= 4 && unique_salience_values <= 2 {
        "low_resolution_rank_tie"
    } else {
        "ok"
    };
    let (salience_saturation_state, top_k_cap_hits, top_k_size) =
        classify_salience_saturation(lane, signals);
    let state = if !enabled {
        "not_enabled"
    } else if total_events == 0 {
        "no_events"
    } else if covered_events == 0 {
        "ablation_state"
    } else if coverage < 0.50 {
        "insufficient_coverage"
    } else {
        "covered"
    };

    ShadowCortexLaneCoverage {
        lane: lane.to_string(),
        state: state.to_string(),
        produced_signals,
        covered_events,
        total_events,
        coverage,
        unique_salience_values,
        rank_tie_state: rank_tie_state.to_string(),
        salience_saturation_state: salience_saturation_state.to_string(),
        top_k_cap_hits,
        top_k_size,
    }
}

fn classify_salience_saturation(
    lane: &str,
    signals: &[AgentAttentionSignal],
) -> (&'static str, usize, usize) {
    let mut saliences: Vec<f64> = signals.iter().map(|signal| signal.salience).collect();
    saliences.sort_by(|a, b| b.partial_cmp(a).unwrap_or(std::cmp::Ordering::Equal));
    let top_k_size = saliences.len().min(SALIENCE_SATURATION_TOP_K);
    if top_k_size == 0 {
        return ("ok", 0, 0);
    }

    let saturation_threshold = match lane {
        "seed_shadow" => SEED_SHADOW_SALIENCE_SATURATION_THRESHOLD,
        "seed_runtime" => SEED_RUNTIME_SALIENCE_SATURATION_THRESHOLD,
        _ => HEURISTIC_SALIENCE_SATURATION_THRESHOLD,
    };
    let cap_hits = saliences
        .iter()
        .take(top_k_size)
        .filter(|salience| **salience >= saturation_threshold)
        .count();
    let cap_hit_fraction = cap_hits as f64 / top_k_size as f64;
    let state = if top_k_size >= 3 && cap_hits == top_k_size {
        "fully_saturated_top_k"
    } else if top_k_size >= 4 && cap_hit_fraction >= 0.5 {
        "majority_saturated_top_k"
    } else if cap_hits >= 2 {
        "partial_saturated_top_k"
    } else {
        "ok"
    };
    (state, cap_hits, top_k_size)
}

fn salience_saturation_is_guarded(lane: &ShadowCortexLaneCoverage) -> bool {
    matches!(
        lane.salience_saturation_state.as_str(),
        "fully_saturated_top_k" | "majority_saturated_top_k"
    )
}

fn comparison_verdict(
    events: &[ShadowCortexEvent],
    heuristic: &ShadowCortexLaneCoverage,
    seed_shadow: &ShadowCortexLaneCoverage,
    seed_runtime: &ShadowCortexLaneCoverage,
    seed_runtime_enabled: bool,
) -> String {
    if events.is_empty() {
        "no_events".to_string()
    } else if seed_runtime_enabled {
        seed_runtime_comparison_verdict(seed_runtime)
    } else if seed_shadow.state == "ablation_state" {
        "ablation_state".to_string()
    } else if seed_shadow.state == "insufficient_coverage" {
        "insufficient_coverage".to_string()
    } else if seed_shadow.rank_tie_state != "ok" {
        "rank_tie_guarded".to_string()
    } else if salience_saturation_is_guarded(seed_shadow)
        || salience_saturation_is_guarded(heuristic)
    {
        "salience_saturation_guarded".to_string()
    } else {
        "seed_shadow_ready_for_review".to_string()
    }
}

fn seed_runtime_comparison_verdict(seed_runtime: &ShadowCortexLaneCoverage) -> String {
    if seed_runtime.state == "ablation_state" {
        "seed_runtime_ablation_state".to_string()
    } else if seed_runtime.state == "insufficient_coverage" {
        "seed_runtime_insufficient_coverage".to_string()
    } else if seed_runtime.rank_tie_state != "ok" {
        "seed_runtime_rank_tie_guarded".to_string()
    } else if salience_saturation_is_guarded(seed_runtime) {
        "seed_runtime_salience_saturation_guarded".to_string()
    } else {
        "seed_runtime_ready_for_review".to_string()
    }
}

fn rank_deltas(
    heuristic_signals: &[AgentAttentionSignal],
    seed_shadow_signals: &[AgentAttentionSignal],
    limit: usize,
) -> Vec<ShadowCortexRankDelta> {
    let heuristic = signal_rank_map(heuristic_signals);
    let seed_shadow = signal_rank_map(seed_shadow_signals);
    let keys: BTreeSet<String> = heuristic
        .keys()
        .chain(seed_shadow.keys())
        .cloned()
        .collect();

    let mut rows: Vec<ShadowCortexRankDelta> = keys
        .into_iter()
        .map(|source_event_id| {
            let h = heuristic.get(&source_event_id);
            let s = seed_shadow.get(&source_event_id);
            ShadowCortexRankDelta {
                subject_id: h
                    .map(|(_, _, subject)| subject.clone())
                    .or_else(|| s.map(|(_, _, subject)| subject.clone()))
                    .unwrap_or_default(),
                source_event_id,
                heuristic_rank: h.map(|(rank, _, _)| *rank),
                heuristic_salience: h.map(|(_, salience, _)| *salience),
                seed_shadow_rank: s.map(|(rank, _, _)| *rank),
                seed_shadow_salience: s.map(|(_, salience, _)| *salience),
            }
        })
        .collect();
    rows.sort_by(|a, b| {
        a.heuristic_rank
            .unwrap_or(usize::MAX)
            .min(a.seed_shadow_rank.unwrap_or(usize::MAX))
            .cmp(
                &b.heuristic_rank
                    .unwrap_or(usize::MAX)
                    .min(b.seed_shadow_rank.unwrap_or(usize::MAX)),
            )
            .then_with(|| a.source_event_id.cmp(&b.source_event_id))
    });
    rows.truncate(limit);
    rows
}

fn signal_rank_map(signals: &[AgentAttentionSignal]) -> BTreeMap<String, (usize, f64, String)> {
    let mut out = BTreeMap::new();
    for (idx, signal) in signals.iter().enumerate() {
        for event_id in &signal.source_event_ids {
            out.entry(event_id.clone()).or_insert((
                idx + 1,
                signal.salience,
                signal.subject_id.clone(),
            ));
        }
    }
    out
}

fn number_feature(value: &serde_json::Value, key: &str) -> Option<f64> {
    value.get(key).and_then(|v| v.as_f64())
}

fn collect_mcp_stat_signals(
    stats: &[McpToolCallStats],
    source_filter: Option<&str>,
    generated_at: i64,
    out: &mut Vec<AgentAttentionSignal>,
) {
    for s in stats.iter().take(20) {
        let error_rate = rate(s.error_count, s.call_count);
        if s.call_count >= 10 && error_rate >= 0.20 {
            out.push(signal(
                generated_at,
                SignalScope::Tool,
                s.tool_name.clone(),
                SignalType::Risk,
                (0.72 + error_rate * 0.2).min(0.95),
                &["tool_failure_spike", "high_error_rate"],
                vec![format!("mcp_dispatch:{}:errors", s.tool_name)],
                SHORT_TTL_SECS,
                json!({
                    "source": "mcp_dispatch",
                    "tool_name": s.tool_name,
                    "call_count": s.call_count,
                    "error_count": s.error_count,
                    "error_rate": error_rate,
                    "p95_duration_ms": s.p95_duration_ms
                }),
                &["show_in_dream_weekly"],
                0.78,
                "A frequently used MCP tool is failing at a high rate.",
                "Inspect recent errors before promoting or relying on this tool.",
            ));
        } else if s.error_count > 0 {
            out.push(signal(
                generated_at,
                SignalScope::Tool,
                s.tool_name.clone(),
                SignalType::Risk,
                0.58,
                &["tool_has_errors"],
                vec![format!("mcp_dispatch:{}:errors", s.tool_name)],
                SHORT_TTL_SECS,
                json!({
                    "source": "mcp_dispatch",
                    "tool_name": s.tool_name,
                    "call_count": s.call_count,
                    "error_count": s.error_count,
                    "error_rate": error_rate
                }),
                &["show_in_dream_weekly"],
                0.62,
                "An MCP tool has recent failures.",
                "Check whether the failure is transient, schema-related, or profile-related.",
            ));
        }

        if s.call_count >= 3 && s.p95_duration_ms >= 1_000 {
            out.push(signal(
                generated_at,
                SignalScope::Tool,
                s.tool_name.clone(),
                SignalType::Opportunity,
                (0.52 + (s.p95_duration_ms as f64 / 10_000.0).min(0.25)).min(0.85),
                &["slow_p95", "tool_latency"],
                vec![format!("mcp_dispatch:{}:latency", s.tool_name)],
                SHORT_TTL_SECS,
                json!({
                    "source": "mcp_dispatch",
                    "tool_name": s.tool_name,
                    "call_count": s.call_count,
                    "avg_duration_ms": s.avg_duration_ms,
                    "p95_duration_ms": s.p95_duration_ms
                }),
                &["show_in_dream_weekly"],
                0.66,
                "An MCP tool has a slow p95 latency in recent use.",
                "Consider result shaping, narrower defaults, or moving expensive work behind an explicit command.",
            ));
        }

        if s.call_count >= 3 && s.avg_result_size >= 24_000.0 {
            out.push(signal(
                generated_at,
                SignalScope::Tool,
                s.tool_name.clone(),
                SignalType::Opportunity,
                0.56,
                &["large_average_result", "context_pressure"],
                vec![format!("mcp_dispatch:{}:result_size", s.tool_name)],
                SHORT_TTL_SECS,
                json!({
                    "source": "mcp_dispatch",
                    "tool_name": s.tool_name,
                    "call_count": s.call_count,
                    "avg_result_size": s.avg_result_size
                }),
                &["show_in_dream_weekly"],
                0.66,
                "An MCP tool is returning large payloads on average.",
                "Tighten default limits or add summary-first output before increasing exposure.",
            ));
        }

        if source_filter == Some("codex")
            && s.call_count >= 3
            && is_codex_native_overlap(&s.tool_name)
        {
            out.push(signal(
                generated_at,
                SignalScope::Tool,
                s.tool_name.clone(),
                SignalType::Opportunity,
                0.50,
                &["native_overlap", "codex_profile_relevant"],
                vec![format!("mcp_dispatch:{}:native_overlap", s.tool_name)],
                SHORT_TTL_SECS,
                json!({
                    "source": "mcp_dispatch",
                    "tool_name": s.tool_name,
                    "call_count": s.call_count,
                    "filter_source": source_filter
                }),
                &["show_in_dream_weekly"],
                0.60,
                "Codex is repeatedly using an Agent-Bridge tool that overlaps native Codex capabilities.",
                "Verify whether Agent-Bridge is adding local context; otherwise keep it out of Essential.",
            ));
        }
    }
}

fn collect_memory_stat_signals(
    stats: &MemoryQueryStats,
    generated_at: i64,
    out: &mut Vec<AgentAttentionSignal>,
) {
    if stats.total_queries == 0 {
        out.push(signal(
            generated_at,
            SignalScope::Memory,
            "memory_query_log".to_string(),
            SignalType::Continuity,
            0.25,
            &["memory_query_quiet"],
            vec!["memory_query_log:window:empty".to_string()],
            LONG_TTL_SECS,
            json!({
                "source": "memory_query_log",
                "window_start": stats.window_start,
                "window_end": stats.window_end,
                "total_queries": 0
            }),
            &["show_in_dream_weekly"],
            0.55,
            "No memory query telemetry was observed in the selected window.",
            "Keep the current memory surface until there is enough recall traffic to judge.",
        ));
        return;
    }

    if stats.total_queries >= 5 && stats.hit_rate < 0.55 {
        out.push(signal(
            generated_at,
            SignalScope::Memory,
            "memory_query_log".to_string(),
            SignalType::Risk,
            (0.62 + (0.55 - stats.hit_rate).max(0.0) * 0.4).min(0.90),
            &["low_memory_hit_rate", "recall_pressure"],
            vec!["memory_query_log:window:hit_rate".to_string()],
            SHORT_TTL_SECS,
            json!({
                "source": "memory_query_log",
                "total_queries": stats.total_queries,
                "hits": stats.hits,
                "misses": stats.misses,
                "hit_rate": stats.hit_rate,
                "by_kind": stats.by_kind
            }),
            &["show_in_dream_weekly", "include_in_session_bootstrap"],
            0.74,
            "Recent memory lookups are missing too often.",
            "Inspect top misses and adjust memory capture, tags, or query phrasing before changing rankers.",
        ));
    }

    for (query, count) in stats.top_miss_queries.iter().take(5) {
        if *count < 2 {
            continue;
        }
        out.push(signal(
            generated_at,
            SignalScope::Memory,
            format!("memory_miss:{query}"),
            SignalType::Risk,
            (0.54 + (*count as f64 / 10.0).min(0.25)).min(0.82),
            &["repeated_miss"],
            vec![format!("memory_query_log:miss:{query}")],
            SHORT_TTL_SECS,
            json!({
                "source": "memory_query_log",
                "query": query,
                "miss_count": count
            }),
            &["include_in_session_bootstrap"],
            0.68,
            "The same memory query missed repeatedly.",
            "Consider saving a compact memory note or adding aliases/tags for this concept.",
        ));
    }

    if stats.total_queries >= 3 && stats.p95_duration_us >= 100_000 {
        out.push(signal(
            generated_at,
            SignalScope::Memory,
            "memory_query_latency".to_string(),
            SignalType::Opportunity,
            (0.50 + (stats.p95_duration_us as f64 / 1_000_000.0).min(0.30)).min(0.82),
            &["memory_query_latency_high"],
            vec!["memory_query_log:window:latency".to_string()],
            SHORT_TTL_SECS,
            json!({
                "source": "memory_query_log",
                "total_queries": stats.total_queries,
                "p50_duration_us": stats.p50_duration_us,
                "p95_duration_us": stats.p95_duration_us
            }),
            &["show_in_dream_weekly"],
            0.64,
            "Memory query latency is high enough to affect interactive chains.",
            "Check embedding backend, FTS selectivity, and result limits before expanding recall surfaces.",
        ));
    }
}

fn collect_forum_window_signals(
    current: &IdentityWindow,
    generated_at: i64,
    out: &mut Vec<AgentAttentionSignal>,
) {
    if current.forum_posts == 0 {
        out.push(signal(
            generated_at,
            SignalScope::Forum,
            "forum_posts".to_string(),
            SignalType::Continuity,
            0.25,
            &["forum_quiet_window"],
            vec!["forum_posts:window:empty".to_string()],
            LONG_TTL_SECS,
            json!({
                "source": "forum_posts",
                "window_start": current.window_start,
                "window_end": current.window_end,
                "forum_posts": 0
            }),
            &["show_in_dream_weekly"],
            0.55,
            "No cross-agent forum posts were observed in the selected window.",
            "Treat collaboration state as unknown rather than assuming there is no parallel work.",
        ));
        return;
    }

    out.push(signal(
        generated_at,
        SignalScope::Forum,
        "forum_posts".to_string(),
        SignalType::Handoff,
        (0.38 + (current.forum_posts as f64 / 20.0).min(0.25)).min(0.70),
        &["forum_activity_recent"],
        vec!["forum_posts:window:activity".to_string()],
        LONG_TTL_SECS,
        json!({
            "source": "forum_posts",
            "forum_posts": current.forum_posts,
            "forum_kinds": current.forum_kinds,
            "forum_avg_body_len": current.forum_avg_body_len
        }),
        &["show_in_dream_weekly", "include_in_session_bootstrap"],
        0.62,
        "Cross-agent forum activity exists in the selected window.",
        "Check recent board/forum state before assuming this worktree is the only active lane.",
    ));

    if current.forum_posts >= 5 && current.forum_avg_body_len < 40.0 {
        out.push(signal(
            generated_at,
            SignalScope::Forum,
            "forum_posts".to_string(),
            SignalType::Risk,
            0.46,
            &["low_context_forum_posts"],
            vec!["forum_posts:window:avg_body_len".to_string()],
            LONG_TTL_SECS,
            json!({
                "source": "forum_posts",
                "forum_posts": current.forum_posts,
                "forum_avg_body_len": current.forum_avg_body_len
            }),
            &["show_in_dream_weekly"],
            0.58,
            "Recent forum posts are short on average.",
            "Prefer explicit handoff summaries when parallel work is active.",
        ));
    }
}

fn shadow_cortex_cache_dir() -> std::path::PathBuf {
    std::env::var_os("XDG_CACHE_HOME")
        .map(std::path::PathBuf::from)
        .or_else(|| {
            std::env::var_os("HOME").map(|home| std::path::PathBuf::from(home).join(".cache"))
        })
        .unwrap_or_else(|| std::path::PathBuf::from("."))
        .join("agent-bridge/shadow-cortex")
}

fn normalize_feedback_decision(decision: &str) -> Result<String> {
    match decision
        .trim()
        .to_ascii_lowercase()
        .replace('-', "_")
        .as_str()
    {
        "accepted" | "accept" => Ok("accepted".to_string()),
        "ignored" | "ignore" => Ok("ignored".to_string()),
        other => Err(anyhow!(
            "unknown shadow-cortex feedback decision '{other}', expected accepted|ignored"
        )),
    }
}

fn parse_sources(raw: &str) -> Result<Vec<ShadowSource>> {
    let normalized = raw.trim().to_ascii_lowercase().replace('-', "_");
    match normalized.as_str() {
        "" | "all" => Ok(vec![
            ShadowSource::McpDispatch,
            ShadowSource::MemoryQueryLog,
            ShadowSource::ForumPosts,
        ]),
        "mcp" | "mcp_dispatch" => Ok(vec![ShadowSource::McpDispatch]),
        "memory" | "memory_query" | "memory_query_log" => Ok(vec![ShadowSource::MemoryQueryLog]),
        "forum" | "forum_posts" => Ok(vec![ShadowSource::ForumPosts]),
        "codex" => Ok(vec![ShadowSource::McpDispatch]),
        other => Err(anyhow!(
            "unknown shadow-cortex source '{other}', expected all|mcp_dispatch|memory|forum|codex"
        )),
    }
}

fn signal(
    at: i64,
    scope: SignalScope,
    subject_id: String,
    signal_type: SignalType,
    salience: f64,
    reason_codes: &[&str],
    source_event_ids: Vec<String>,
    ttl_secs: u64,
    evidence: serde_json::Value,
    consumer_hints: &[&str],
    confidence: f64,
    summary: &str,
    recommendation: &str,
) -> AgentAttentionSignal {
    AgentAttentionSignal {
        agent_shadow_cortex: SIGNAL_SCHEMA_VERSION,
        at,
        scope,
        subject_id,
        signal_type,
        salience: salience.clamp(0.0, 1.0),
        reason_codes: reason_codes.iter().map(|s| (*s).to_string()).collect(),
        source_event_ids,
        ttl_secs,
        evidence,
        consumer_hints: consumer_hints.iter().map(|s| (*s).to_string()).collect(),
        confidence: confidence.clamp(0.0, 1.0),
        summary: summary.to_string(),
        recommendation: recommendation.to_string(),
    }
}

fn finalize_signals(signals: &mut Vec<AgentAttentionSignal>, max_signals: usize) {
    signals.sort_by(|a, b| {
        b.salience
            .total_cmp(&a.salience)
            .then_with(|| b.confidence.total_cmp(&a.confidence))
            .then_with(|| a.subject_id.cmp(&b.subject_id))
    });
    signals.truncate(max_signals);
}

fn is_codex_native_overlap(tool_name: &str) -> bool {
    tool_name == "shell_exec"
        || tool_name.starts_with("terminal_")
        || tool_name.starts_with("browser_")
        || tool_name.starts_with("github_")
        || tool_name.starts_with("gitlab_")
        || tool_name.starts_with("notion_")
        || tool_name.starts_with("cloudflare_")
        || tool_name.starts_with("brave_")
        || tool_name.starts_with("worktree_")
        || tool_name.starts_with("codebase_")
}

fn requested_source_is_codex(raw: &str) -> bool {
    raw.trim().eq_ignore_ascii_case("codex")
}

fn rate(part: u64, total: u64) -> f64 {
    if total == 0 {
        0.0
    } else {
        part as f64 / total as f64
    }
}

fn now_secs() -> i64 {
    SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map(|d| d.as_secs() as i64)
        .unwrap_or(0)
}

fn compact_json(value: &serde_json::Value) -> String {
    serde_json::to_string(value).unwrap_or_else(|_| "{}".to_string())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn parse_sources_accepts_expected_aliases() {
        assert_eq!(
            parse_sources("all").unwrap(),
            vec![
                ShadowSource::McpDispatch,
                ShadowSource::MemoryQueryLog,
                ShadowSource::ForumPosts
            ]
        );
        assert_eq!(
            parse_sources("mcp-dispatch").unwrap(),
            vec![ShadowSource::McpDispatch]
        );
        assert_eq!(
            parse_sources("memory").unwrap(),
            vec![ShadowSource::MemoryQueryLog]
        );
        assert_eq!(
            parse_sources("forum").unwrap(),
            vec![ShadowSource::ForumPosts]
        );
    }

    #[test]
    fn off_mode_is_explicit() {
        assert_eq!(
            ShadowCortexMode::from_value(Some("off")),
            ShadowCortexMode::Off
        );
        assert_eq!(
            ShadowCortexMode::from_value(Some("seed-shadow")),
            ShadowCortexMode::SeedShadow
        );
        assert_eq!(
            ShadowCortexMode::from_value(None),
            ShadowCortexMode::Heuristic
        );
    }

    #[test]
    fn finalize_sorts_by_salience_and_truncates() {
        let mut signals = vec![
            signal(
                1,
                SignalScope::Tool,
                "b".to_string(),
                SignalType::Risk,
                0.3,
                &["b"],
                vec![],
                SHORT_TTL_SECS,
                json!({}),
                &[],
                0.9,
                "b",
                "b",
            ),
            signal(
                1,
                SignalScope::Tool,
                "a".to_string(),
                SignalType::Risk,
                0.8,
                &["a"],
                vec![],
                SHORT_TTL_SECS,
                json!({}),
                &[],
                0.7,
                "a",
                "a",
            ),
        ];
        finalize_signals(&mut signals, 1);
        assert_eq!(signals.len(), 1);
        assert_eq!(signals[0].subject_id, "a");
    }

    #[test]
    fn memory_repeated_misses_generate_risk_signal() {
        let stats = MemoryQueryStats {
            window_start: 1,
            window_end: 2,
            total_queries: 10,
            hits: 2,
            misses: 8,
            hit_rate: 0.2,
            avg_top_hit_age_secs: 0.0,
            p50_duration_us: 1_000,
            p95_duration_us: 2_000,
            by_kind: vec![("search_fts".to_string(), 10)],
            by_mode: Vec::new(),
            top_miss_queries: vec![("shadow cortex".to_string(), 3)],
        };
        let mut signals = Vec::new();
        collect_memory_stat_signals(&stats, 42, &mut signals);
        assert!(signals
            .iter()
            .any(|s| s.reason_codes.contains(&"low_memory_hit_rate".to_string())));
        assert!(signals
            .iter()
            .any(|s| s.reason_codes.contains(&"repeated_miss".to_string())));
    }

    #[test]
    fn mcp_high_error_rate_generates_tool_risk() {
        let stats = vec![McpToolCallStats {
            tool_name: "memory_search".to_string(),
            call_count: 10,
            error_count: 3,
            avg_duration_ms: 20.0,
            p95_duration_ms: 30,
            max_duration_ms: 40,
            avg_result_size: 100.0,
            client_name: None,
            profile: None,
            source: Some("codex".to_string()),
            model: None,
            model_reasoning_effort: None,
            codex_host: None,
        }];
        let mut signals = Vec::new();
        collect_mcp_stat_signals(&stats, Some("codex"), 42, &mut signals);
        assert!(signals
            .iter()
            .any(|s| s.reason_codes.contains(&"high_error_rate".to_string())));
        assert_eq!(signals[0].ttl_secs, SHORT_TTL_SECS);
    }

    #[test]
    fn forum_quiet_window_has_long_expiry() {
        let current = IdentityWindow {
            window_start: 1,
            window_end: 2,
            tool_calls_total: 0,
            tool_calls_ok: 0,
            top_tools: Vec::new(),
            forum_posts: 0,
            forum_kinds: Vec::new(),
            forum_avg_body_len: 0.0,
            memory_saves: 0,
        };
        let mut signals = Vec::new();
        collect_forum_window_signals(&current, 42, &mut signals);
        assert_eq!(signals.len(), 1);
        assert_eq!(signals[0].ttl_secs, LONG_TTL_SECS);
        assert!(signals[0]
            .reason_codes
            .contains(&"forum_quiet_window".to_string()));
    }

    #[test]
    fn fixture_event_encoder_uses_stable_ids_and_order() {
        let mut fixture = sample_fixture();
        fixture.events = encode_shadow_events(&fixture);
        let ids: Vec<String> = fixture.events.iter().map(|e| e.event_id.clone()).collect();
        let mut sorted = ids.clone();
        sorted.sort();
        assert_eq!(ids, sorted);
        assert!(ids.contains(&"mcp_dispatch:memory_search:errors".to_string()));
        assert!(ids.contains(&"mcp_dispatch:shell_exec:latency".to_string()));
        assert!(ids.contains(&"memory_query_log:window:hit_rate".to_string()));
        assert!(ids.contains(&"forum_posts:window:activity".to_string()));
    }

    #[test]
    fn fixture_replay_is_deterministic() {
        let mut fixture = sample_fixture();
        fixture.events = encode_shadow_events(&fixture);
        let a = build_shadow_cortex_report_from_fixture(&fixture, 5).expect("report a");
        let b = build_shadow_cortex_report_from_fixture(&fixture, 5).expect("report b");
        assert_eq!(a, b);
        assert_eq!(a.generated_at, 42);
        assert_eq!(a.totals.mcp_tool_calls, 16);
        assert!(a.signals.iter().any(|s| s
            .source_event_ids
            .contains(&"mcp_dispatch:shell_exec:latency".to_string())));
    }

    #[test]
    fn seed_shadow_replay_reports_lane_coverage() {
        let mut fixture = sample_fixture();
        fixture.events = encode_shadow_events(&fixture);
        let report = build_shadow_cortex_report_from_fixture(&fixture, 10).expect("report");
        assert!(!report.seed_shadow_signals.is_empty());
        assert_eq!(report.comparison.verdict, "salience_saturation_guarded");
        let heuristic = report
            .comparison
            .lane_coverage
            .iter()
            .find(|lane| lane.lane == "heuristic")
            .expect("heuristic lane");
        assert!(salience_saturation_is_guarded(heuristic));
        let seed = report
            .comparison
            .lane_coverage
            .iter()
            .find(|lane| lane.lane == "seed_shadow")
            .expect("seed shadow lane");
        assert_eq!(seed.state, "covered");
        assert_eq!(seed.covered_events, seed.total_events);
        assert_eq!(seed.salience_saturation_state, "ok");
    }

    #[test]
    fn weekly_summary_keeps_top_signals_and_guardrails() {
        let mut fixture = sample_fixture();
        fixture.events = encode_shadow_events(&fixture);
        let report = build_shadow_cortex_report_from_fixture(&fixture, 10).expect("report");
        let summary = weekly_summary(&report);

        assert_eq!(summary.verdict, "salience_saturation_guarded");
        assert_eq!(summary.total_events, fixture.events.len());
        assert!(summary.top_signal.is_some());
        assert!(summary.seed_shadow_top_signal.is_some());
        assert!(summary
            .lane_coverage
            .iter()
            .any(|lane| lane.lane == "seed_runtime" && lane.state == "not_enabled"));
    }

    #[test]
    fn coverage_guardrail_detects_ablation_state() {
        let mut fixture = sample_fixture();
        fixture.events = encode_shadow_events(&fixture);
        let coverage = lane_coverage("seed_shadow", &fixture.events, &[], true);
        assert_eq!(coverage.state, "ablation_state");
        assert_eq!(
            comparison_verdict(&fixture.events, &coverage, &coverage, &coverage, false),
            "ablation_state"
        );
    }

    #[test]
    fn coverage_guardrail_detects_degenerate_rank_tie() {
        let events = vec![
            shadow_event(
                "mcp_dispatch:a:errors".to_string(),
                1,
                "mcp_dispatch",
                SignalScope::Tool,
                "a",
                json!({"error_rate": 0.2}),
            ),
            shadow_event(
                "mcp_dispatch:b:errors".to_string(),
                1,
                "mcp_dispatch",
                SignalScope::Tool,
                "b",
                json!({"error_rate": 0.2}),
            ),
        ];
        let signals = vec![
            signal(
                1,
                SignalScope::Tool,
                "a".to_string(),
                SignalType::Risk,
                0.5,
                &["probe"],
                vec!["mcp_dispatch:a:errors".to_string()],
                SHORT_TTL_SECS,
                json!({}),
                &[],
                0.5,
                "a",
                "a",
            ),
            signal(
                1,
                SignalScope::Tool,
                "b".to_string(),
                SignalType::Risk,
                0.5,
                &["probe"],
                vec!["mcp_dispatch:b:errors".to_string()],
                SHORT_TTL_SECS,
                json!({}),
                &[],
                0.5,
                "b",
                "b",
            ),
        ];
        let coverage = lane_coverage("seed_shadow", &events, &signals, true);
        assert_eq!(coverage.state, "covered");
        assert_eq!(coverage.rank_tie_state, "degenerate_rank_tie");
        assert_eq!(
            comparison_verdict(&events, &coverage, &coverage, &coverage, false),
            "rank_tie_guarded"
        );
    }

    #[test]
    fn coverage_guardrail_detects_low_resolution_rank_tie() {
        let mut events = Vec::new();
        let mut signals = Vec::new();
        for idx in 0..4 {
            let subject = format!("tool_{idx}");
            let event_id = format!("mcp_dispatch:{subject}:latency");
            events.push(shadow_event(
                event_id.clone(),
                1,
                "mcp_dispatch",
                SignalScope::Tool,
                &subject,
                json!({"p95_ms": 1_000 + idx}),
            ));
            signals.push(signal(
                1,
                SignalScope::Tool,
                subject.clone(),
                SignalType::Opportunity,
                if idx < 2 { 0.50 } else { 0.51 },
                &["probe"],
                vec![event_id],
                SHORT_TTL_SECS,
                json!({}),
                &[],
                0.5,
                "probe",
                "probe",
            ));
        }
        let coverage = lane_coverage("seed_shadow", &events, &signals, true);
        assert_eq!(coverage.state, "covered");
        assert_eq!(coverage.rank_tie_state, "low_resolution_rank_tie");
        assert_eq!(
            comparison_verdict(&events, &coverage, &coverage, &coverage, false),
            "rank_tie_guarded"
        );
    }

    #[test]
    fn coverage_guardrail_detects_top_k_salience_saturation() {
        let mut events = Vec::new();
        let mut signals = Vec::new();
        let saliences = [0.77, 0.77, 0.77, 0.77, 0.70, 0.69, 0.68, 0.67];
        for (idx, salience) in saliences.iter().enumerate() {
            let subject = format!("tool_{idx}");
            let event_id = format!("mcp_dispatch:{subject}:latency");
            events.push(shadow_event(
                event_id.clone(),
                1,
                "mcp_dispatch",
                SignalScope::Tool,
                &subject,
                json!({"p95_ms": 3_500 + idx}),
            ));
            signals.push(signal(
                1,
                SignalScope::Tool,
                subject,
                SignalType::Opportunity,
                *salience,
                &["probe"],
                vec![event_id],
                SHORT_TTL_SECS,
                json!({}),
                &[],
                0.5,
                "probe",
                "probe",
            ));
        }
        let coverage = lane_coverage("heuristic", &events, &signals, true);
        assert_eq!(coverage.state, "covered");
        assert_eq!(coverage.rank_tie_state, "ok");
        assert_eq!(coverage.salience_saturation_state, "fully_saturated_top_k");
        assert_eq!(coverage.top_k_cap_hits, 4);
        assert_eq!(coverage.top_k_size, 4);
        assert_eq!(
            comparison_verdict(&events, &coverage, &coverage, &coverage, false),
            "salience_saturation_guarded"
        );
    }

    #[test]
    fn seed_shadow_saturation_uses_seed_shadow_cap() {
        let mut events = Vec::new();
        let mut signals = Vec::new();
        let saliences = [0.94, 0.93, 0.86, 0.80];
        for (idx, salience) in saliences.iter().enumerate() {
            let subject = format!("tool_{idx}");
            let event_id = format!("mcp_dispatch:{subject}:errors");
            events.push(shadow_event(
                event_id.clone(),
                1,
                "mcp_dispatch",
                SignalScope::Tool,
                &subject,
                json!({"error_rate": 0.3}),
            ));
            signals.push(signal(
                1,
                SignalScope::Tool,
                subject,
                SignalType::Risk,
                *salience,
                &["probe"],
                vec![event_id],
                SHORT_TTL_SECS,
                json!({}),
                &[],
                0.5,
                "probe",
                "probe",
            ));
        }
        let coverage = lane_coverage("seed_shadow", &events, &signals, true);
        assert_eq!(coverage.state, "covered");
        assert_eq!(coverage.rank_tie_state, "ok");
        assert_eq!(coverage.salience_saturation_state, "ok");
        assert_eq!(coverage.top_k_cap_hits, 0);
    }

    #[test]
    fn seed_runtime_saturation_guard_is_reachable_below_runtime_cap() {
        let mut events = Vec::new();
        let mut signals = Vec::new();
        let saliences = [0.980, 0.979, 0.978, 0.977, 0.940, 0.920];
        for (idx, salience) in saliences.iter().enumerate() {
            let subject = format!("tool_{idx}");
            let event_id = format!("mcp_dispatch:{subject}:runtime");
            events.push(shadow_event(
                event_id.clone(),
                1,
                "mcp_dispatch",
                SignalScope::Tool,
                &subject,
                json!({"p95_ms": 4_000 + idx}),
            ));
            signals.push(signal(
                1,
                SignalScope::Tool,
                subject,
                SignalType::Opportunity,
                *salience,
                &["seed_runtime"],
                vec![event_id],
                SHORT_TTL_SECS,
                json!({}),
                &[],
                0.5,
                "probe",
                "probe",
            ));
        }
        let coverage = lane_coverage("seed_runtime", &events, &signals, true);
        assert_eq!(coverage.state, "covered");
        assert_eq!(coverage.rank_tie_state, "ok");
        assert_eq!(coverage.salience_saturation_state, "fully_saturated_top_k");
        assert_eq!(coverage.top_k_cap_hits, 4);
        assert_eq!(coverage.top_k_size, 4);
        assert_eq!(
            comparison_verdict(&events, &coverage, &coverage, &coverage, true),
            "seed_runtime_salience_saturation_guarded"
        );
    }

    #[test]
    fn seed_runtime_mode_evaluates_ephemeral_seed_lane() {
        let mut fixture = sample_fixture();
        fixture.mode = ShadowCortexMode::SeedRuntime;
        fixture.events = encode_shadow_events(&fixture);

        let report = build_shadow_cortex_report_from_fixture(&fixture, 10).expect("report");

        assert!(!report.seed_runtime_signals.is_empty());
        assert_eq!(report.seed_runtime_signals.len(), fixture.events.len());
        assert!(report
            .seed_runtime_signals
            .iter()
            .all(|signal| signal.reason_codes.contains(&"seed_runtime".to_string())));
        assert!(report
            .seed_runtime_signals
            .iter()
            .all(|signal| signal.evidence["substrate"]["mutates_global_substrate"] == false));
        assert!(ab_seed_bridge::current().is_none());

        let runtime = report
            .comparison
            .lane_coverage
            .iter()
            .find(|lane| lane.lane == "seed_runtime")
            .expect("seed runtime lane");
        assert_eq!(runtime.state, "covered");
        assert_eq!(runtime.covered_events, runtime.total_events);
        assert_eq!(runtime.salience_saturation_state, "ok");
        assert_eq!(report.comparison.verdict, "seed_runtime_ready_for_review");
        assert!(report
            .comparison
            .notes
            .iter()
            .any(|note| { note.contains("ephemeral in-process SeedBackend replay") }));

        let summary = weekly_summary(&report);
        assert!(summary.seed_runtime_top_signal.is_some());
    }

    #[test]
    fn feedback_records_append_and_read_jsonl() {
        let dir = tempfile::tempdir().expect("tempdir");
        let path = dir.path().join("feedback.jsonl");
        let record = append_feedback_record(
            Some(&path),
            "accept",
            "mcp_dispatch:shell_exec:latency",
            vec!["mcp_dispatch:shell_exec:latency".to_string()],
            "test-agent",
            Some("useful weekly signal"),
        )
        .expect("append feedback");
        assert_eq!(record.decision, "accepted");

        let records = read_feedback_records(Some(&path), 10).expect("read feedback");
        assert_eq!(records.len(), 1);
        assert_eq!(records[0].signal_id, "mcp_dispatch:shell_exec:latency");
        assert_eq!(records[0].note.as_deref(), Some("useful weekly signal"));
    }

    #[test]
    fn feedback_summary_counts_window_decisions() {
        let dir = tempfile::tempdir().expect("tempdir");
        let path = dir.path().join("feedback.jsonl");
        let records = vec![
            ShadowCortexFeedbackRecord {
                agent_shadow_cortex: SIGNAL_SCHEMA_VERSION,
                recorded_at: 1,
                decision: "accepted".to_string(),
                signal_id: "old".to_string(),
                source_event_ids: Vec::new(),
                actor: "test".to_string(),
                note: None,
            },
            ShadowCortexFeedbackRecord {
                agent_shadow_cortex: SIGNAL_SCHEMA_VERSION,
                recorded_at: 8,
                decision: "accepted".to_string(),
                signal_id: "new-accepted".to_string(),
                source_event_ids: Vec::new(),
                actor: "test".to_string(),
                note: None,
            },
            ShadowCortexFeedbackRecord {
                agent_shadow_cortex: SIGNAL_SCHEMA_VERSION,
                recorded_at: 10,
                decision: "ignored".to_string(),
                signal_id: "new-ignored".to_string(),
                source_event_ids: Vec::new(),
                actor: "test".to_string(),
                note: None,
            },
        ];
        let body = records
            .iter()
            .map(serde_json::to_string)
            .collect::<std::result::Result<Vec<_>, _>>()
            .expect("serialize records")
            .join("\n");
        std::fs::write(&path, format!("{body}\n")).expect("write feedback");

        let summary = feedback_summary(Some(&path), 7, 10).expect("feedback summary");
        assert_eq!(summary.total_records, 3);
        assert_eq!(summary.window_records, 2);
        assert_eq!(summary.accepted, 1);
        assert_eq!(summary.ignored, 1);
        assert_eq!(summary.latest.unwrap().signal_id, "new-ignored");
    }

    fn sample_fixture() -> ShadowCortexReplayFixture {
        ShadowCortexReplayFixture {
            agent_shadow_cortex: SIGNAL_SCHEMA_VERSION,
            mode: ShadowCortexMode::Heuristic,
            captured_at: 42,
            window_days: 7,
            window_secs: 604_800,
            requested_source: "codex".to_string(),
            sources: vec![
                "mcp_dispatch".to_string(),
                "memory_query_log".to_string(),
                "forum_posts".to_string(),
            ],
            mcp_dispatch: Some(vec![
                McpToolCallStats {
                    tool_name: "shell_exec".to_string(),
                    call_count: 6,
                    error_count: 0,
                    avg_duration_ms: 1_200.0,
                    p95_duration_ms: 2_400,
                    max_duration_ms: 2_600,
                    avg_result_size: 100.0,
                    client_name: None,
                    profile: Some("essential".to_string()),
                    source: Some("codex".to_string()),
                    model: Some("gpt-5.5".to_string()),
                    model_reasoning_effort: Some("xhigh".to_string()),
                    codex_host: Some("desktop".to_string()),
                },
                McpToolCallStats {
                    tool_name: "memory_search".to_string(),
                    call_count: 10,
                    error_count: 3,
                    avg_duration_ms: 10.0,
                    p95_duration_ms: 12,
                    max_duration_ms: 13,
                    avg_result_size: 100.0,
                    client_name: None,
                    profile: Some("essential".to_string()),
                    source: Some("codex".to_string()),
                    model: Some("gpt-5.5".to_string()),
                    model_reasoning_effort: Some("xhigh".to_string()),
                    codex_host: Some("desktop".to_string()),
                },
            ]),
            memory_query_log: Some(MemoryQueryStats {
                window_start: 1,
                window_end: 42,
                total_queries: 10,
                hits: 2,
                misses: 8,
                hit_rate: 0.2,
                avg_top_hit_age_secs: 0.0,
                p50_duration_us: 1_000,
                p95_duration_us: 2_000,
                by_kind: vec![("search_fts".to_string(), 10)],
                by_mode: Vec::new(),
                top_miss_queries: vec![("shadow cortex".to_string(), 3)],
            }),
            forum_window: Some(IdentityWindow {
                window_start: 1,
                window_end: 42,
                tool_calls_total: 0,
                tool_calls_ok: 0,
                top_tools: Vec::new(),
                forum_posts: 3,
                forum_kinds: vec![("decision".to_string(), 3)],
                forum_avg_body_len: 128.0,
                memory_saves: 0,
            }),
            events: Vec::new(),
        }
    }
}
