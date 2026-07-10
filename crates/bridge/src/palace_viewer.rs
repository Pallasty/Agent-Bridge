//! P1 — Static Palace viewer (呼吸式画布).
//!
//! Read-only HTTP server that renders the active memory graph as a
//! force-directed network in the browser using cytoscape.js.
//!
//! ## Two memory sources, one graph
//!
//! Two parallel memory systems live side-by-side and the viewer merges them:
//!
//! - **sqlite** (agent-bridge `state.db`): lesson / decision / observation /
//!   todo / session_handoff / etc. — produced by agent work via `memory_save`.
//!   Edges are real `memory_edges` rows (Hebbian-evolved, supersedes,
//!   summarizes, references).
//! - **markdown** (`~/.claude/projects/<cwd-encoded>/memory/*.md`): Claude
//!   Code's auto-memory layer — vision / user / project / feedback / decision
//!   files written by the user and the assistant during conversation.
//!   Edges come from `(other.md)` references inside the body.
//!
//! Cross-source edges are NOT inferred from semantic similarity (would
//! generate false positives — that's a P3 job). But **explicit** cross-
//! source edges written via `memory_link` (e.g. C1 `annotates` edges from
//! a sqlite annotation back to a markdown vision file) DO render — those
//! are user-authored intent, not noise.
//!
//! ## Endpoints
//!   - `GET /`                  → embedded HTML viewer
//!   - `GET /healthz`           → liveness probe
//!   - `GET /api/graph`         → merged `{ nodes, edges }` from both sources;
//!     edges include explicit (memory_edges) AND co-activation (Hebbian) —
//!     the latter dedup'd against explicit so a structural edge always wins
//!   - `GET /api/memory/:key`   → single record (sqlite first, markdown fallback)
//!   - `POST /api/annotate`     → C1: write a new sqlite memory linked to a node
//!     (closes the 呼吸 loop — Palace exploration → annotation → memory)
//!
//! Bind defaults to `127.0.0.1` (single-user local view).
//!
//! See `vision_breathing_canvas.md` for the broader 呼吸式画布 design.

use ab_store::{MemoryListSort, MemoryQueryRecord, MemoryRecord, StateStore};
use anyhow::{Context, Result};
use axum::{
    extract::{Path, Query, State},
    http::StatusCode,
    response::{
        sse::{Event as SseEvent, KeepAlive, Sse},
        Html, IntoResponse,
    },
    routing::{get, post},
    Json, Router,
};
use base64::{engine::general_purpose, Engine as _};
use serde::{de, Deserialize};
use serde_json::{json, Value};
use std::collections::{hash_map::DefaultHasher, BTreeMap, HashSet, VecDeque};
use std::fs;
use std::hash::{Hash, Hasher};
use std::io::Write;
use std::path::{Path as FsPath, PathBuf};
use std::sync::{Arc, Mutex};
use std::time::{SystemTime, UNIX_EPOCH};

/// Size of the rolling click window used to feed the co-activation table.
/// 5 = "last 5 nodes you looked at" → the system records that these were
/// in your attention together. Small enough that a fresh palace visit
/// quickly self-prunes; large enough to capture multi-step exploration.
const CLICK_WINDOW: usize = 5;

const VIEWER_NODE_CAP: usize = 500;
const STORE_FETCH_LIMIT: u32 = 2000;
const DEFAULT_PALACE_MATERIALIZATION_REVIEW_PACKET_JSON: &str =
    "docs/design/fixtures/memory-biocortex-materialization-review-packet-2026-06-20.json";
const DEFAULT_PALACE_MATERIALIZATION_REVIEW_PACKET_BODY: &str = include_str!(
    "../../../docs/design/fixtures/memory-biocortex-materialization-review-packet-2026-06-20.json"
);

const PALACE_HTML: &str = include_str!("../assets/palace.html");

#[derive(Clone)]
struct AppState {
    store: Arc<dyn StateStore>,
    markdown_root: Option<PathBuf>,
    /// Directory holding `dream promote --html` reports (and any other
    /// future agent-generated HTML artifacts). When set, Palace serves
    /// `/reports/:filename` for direct viewing and exposes
    /// `/api/reports?key=KEY` so the side panel can surface related
    /// reports — closing the loop from "report → Palace ?focus=KEY"
    /// back to "Palace node → reports that mention it".
    reports_dir: Option<PathBuf>,
    /// Rolling window of recently-clicked node keys. When full, each new
    /// click triggers a `record_coactivation` call so the Hebbian system
    /// learns that "these nodes were in the user's attention together".
    /// `Mutex<VecDeque<…>>` (not async) — held only across cheap ops.
    recent_clicks: Arc<Mutex<VecDeque<String>>>,
}

/// Run the Palace viewer HTTP server. Blocks until the listener is dropped.
///
/// `markdown_root` is the directory containing `*.md` auto-memory files.
/// Pass `None` to disable the markdown layer (sqlite-only).
pub async fn run(
    store: Arc<dyn StateStore>,
    listen: &str,
    markdown_root: Option<PathBuf>,
    reports_dir: Option<PathBuf>,
) -> Result<()> {
    if let Some(p) = &markdown_root {
        tracing::info!(path = %p.display(), "Palace markdown layer enabled");
    } else {
        tracing::info!("Palace markdown layer disabled (sqlite-only)");
    }
    if let Some(p) = &reports_dir {
        tracing::info!(path = %p.display(), "Palace reports layer enabled");
    }

    let state = AppState {
        store,
        markdown_root,
        reports_dir,
        recent_clicks: Arc::new(Mutex::new(VecDeque::with_capacity(CLICK_WINDOW))),
    };
    let app = Router::new()
        .route("/", get(index))
        .route("/healthz", get(healthz))
        .route("/api/graph", get(api_graph))
        .route("/api/self-review-packet", get(api_self_review_packet))
        .route(
            "/api/materialization-review-artifact",
            get(api_materialization_review_artifact),
        )
        .route(
            "/api/materialization-review-approved-plan",
            get(api_materialization_review_approved_plan),
        )
        .route(
            "/api/materialization-review-apply",
            post(api_materialization_review_apply),
        )
        .route(
            "/api/materialization-review-decision",
            post(api_materialization_review_decision),
        )
        .route(
            "/api/palace-review-artifact",
            get(api_palace_review_artifact),
        )
        .route("/api/orphan-candidates", get(api_orphan_candidates))
        .route(
            "/api/orphan-approved-link-plan",
            get(api_orphan_approved_link_plan),
        )
        .route(
            "/api/orphan-approved-link-apply",
            post(api_orphan_approved_link_apply),
        )
        .route(
            "/api/orphan-candidate-decision",
            post(api_orphan_candidate_decision),
        )
        .route("/api/semantic-events", get(api_semantic_events))
        .route("/api/memory/:key", get(api_memory))
        .route("/api/annotate", post(api_annotate))
        .route("/api/reports", get(api_reports))
        .route("/reports/:filename", get(serve_report))
        .route("/api/canvas-chat", post(api_canvas_chat))
        .route("/api/canvas-chat-stream", post(api_canvas_chat_stream))
        .route("/api/memory/:key/tombstone", post(api_memory_tombstone))
        .route("/api/lineage/:key", get(api_lineage))
        .route("/api/coactivation-peers/:key", get(api_coactivation_peers))
        .route("/api/embedding-stats", get(api_embedding_stats))
        .route(
            "/api/canvas-chat-attachment",
            post(api_canvas_chat_attachment),
        )
        .with_state(state);

    let listener = tokio::net::TcpListener::bind(listen)
        .await
        .with_context(|| format!("bind {listen}"))?;
    let addr = listener
        .local_addr()
        .map(|a| a.to_string())
        .unwrap_or_else(|_| listen.to_string());
    tracing::info!(addr = %addr, "Palace viewer (P1) listening");
    eprintln!("Palace viewer ready: http://{addr}");
    axum::serve(listener, app).await.context("axum::serve")?;
    Ok(())
}

/// Best-effort default: `~/.claude/projects/<cwd-encoded>/memory/`.
/// Returns `None` if the directory doesn't exist (e.g. user runs the
/// viewer outside a project that has been opened in Claude Code).
pub fn default_markdown_dir() -> Option<PathBuf> {
    let home = std::env::var_os("HOME")?;
    let cwd = std::env::current_dir().ok()?;
    let cwd_str = cwd.to_str()?;
    let encoded = cwd_str.replace('/', "-");
    let path = PathBuf::from(home)
        .join(".claude")
        .join("projects")
        .join(encoded)
        .join("memory");
    if path.is_dir() {
        Some(path)
    } else {
        None
    }
}

async fn index() -> impl IntoResponse {
    Html(PALACE_HTML)
}

async fn healthz() -> impl IntoResponse {
    (StatusCode::OK, "ok")
}

#[derive(Deserialize, Default)]
struct GraphQuery {
    /// `?all=1` includes `kind=skill` records (indexed third-party skills).
    #[serde(default)]
    #[serde(deserialize_with = "deserialize_boolish")]
    all: bool,
}

#[derive(Deserialize, Default)]
struct SelfReviewPacketQuery {
    /// `?all=1` mirrors `/api/graph?all=1`.
    #[serde(default)]
    #[serde(deserialize_with = "deserialize_boolish")]
    all: bool,
}

#[derive(Deserialize, Default)]
struct OrphanCandidatesQuery {
    /// Optional Palace atlas region id, e.g. `memory` or `auto-curated`.
    #[serde(default)]
    region: Option<String>,
    /// Top candidate score needed for `status=would_link`.
    #[serde(default)]
    threshold: Option<f64>,
    /// Skip orphan sources whose content is shorter than this many bytes.
    #[serde(default)]
    min_content_len: Option<u64>,
    /// Maximum orphan source rows to inspect.
    #[serde(default)]
    max_orphans: Option<u64>,
    /// Maximum candidate targets returned per orphan.
    #[serde(default)]
    candidate_limit: Option<u64>,
}

#[derive(Deserialize)]
struct OrphanCandidateDecisionRequest {
    orphan_key: String,
    candidate_key: String,
    decision: String,
    #[serde(default)]
    reviewer: Option<String>,
    #[serde(default)]
    note: Option<String>,
}

#[derive(Deserialize)]
struct MaterializationReviewDecisionRequest {
    from_key: String,
    to_key: String,
    #[serde(default)]
    edge_type: Option<String>,
    decision: String,
    #[serde(default)]
    reviewer: Option<String>,
    #[serde(default)]
    note: Option<String>,
}

#[derive(Deserialize, Default)]
struct MaterializationApprovedEdgeApplyRequest {
    #[serde(default)]
    dry_run: Option<bool>,
    #[serde(default)]
    confirm: Option<String>,
    #[serde(default)]
    actor: Option<String>,
}

#[derive(Deserialize, Default)]
struct OrphanApprovedLinkApplyRequest {
    #[serde(default)]
    region: Option<String>,
    #[serde(default)]
    threshold: Option<f64>,
    #[serde(default)]
    min_content_len: Option<u64>,
    #[serde(default)]
    max_orphans: Option<u64>,
    #[serde(default)]
    candidate_limit: Option<u64>,
    #[serde(default)]
    dry_run: Option<bool>,
    #[serde(default)]
    confirm: Option<String>,
    #[serde(default)]
    actor: Option<String>,
}

fn deserialize_boolish<'de, D>(deserializer: D) -> std::result::Result<bool, D::Error>
where
    D: de::Deserializer<'de>,
{
    let raw = Option::<String>::deserialize(deserializer)?;
    let Some(raw) = raw else {
        return Ok(false);
    };
    match raw.trim().to_ascii_lowercase().as_str() {
        "" | "1" | "true" | "yes" | "y" | "on" => Ok(true),
        "0" | "false" | "no" | "n" | "off" => Ok(false),
        other => Err(de::Error::custom(format!(
            "invalid boolish value `{other}`"
        ))),
    }
}

const PALACE_ORPHAN_SKIP_TAGS: &[&str] = &["auto_curated", "alert", "ttl:7d"];
const PALACE_ORPHAN_SKIP_KINDS: &[&str] = &["alert", "work_memory", "session_handoff", "snapshot"];
const PALACE_ORPHAN_APPROVED_LINK_APPLY_CONFIRM: &str = "APPLY APPROVED LINKS";
const PALACE_MATERIALIZATION_APPROVED_EDGE_APPLY_CONFIRM: &str = "APPLY MATERIALIZATION EDGES";
const PALACE_ORPHAN_SAFE_BATCH_LIMIT: usize = 3;
const PALACE_ORPHAN_SAFE_BATCH_MIN_CONFIDENCE: f64 = 0.85;
const PALACE_ORPHAN_SAFE_BATCH_SCOPE_RELATION: &str = "same_scope";

#[derive(Debug, Clone)]
struct PalaceLinkSuggestion {
    key: String,
    kind: String,
    confidence: f64,
    reason: String,
    scope: Option<String>,
    scope_relation: &'static str,
    preview: String,
}

#[derive(Debug, Clone)]
struct PalaceOrphanCandidatePreviewRow {
    orphan: MemoryRecord,
    suggestions: Vec<PalaceLinkSuggestion>,
}

#[derive(Debug, Default)]
struct PalaceOrphanCandidatePreview {
    examined: u64,
    eligible_orphans: u64,
    would_link: u64,
    skipped_low_score: u64,
    skipped_no_candidates: u64,
    skipped_existing_edges: u64,
    skipped_blacklisted_orphan: u64,
    skipped_blacklisted_kind: u64,
    rows: Vec<PalaceOrphanCandidatePreviewRow>,
}

#[derive(Debug, Clone, Eq, PartialEq, Hash)]
struct PalaceOrphanCandidatePair {
    orphan_key: String,
    candidate_key: String,
}

#[derive(Debug, Clone)]
struct PalaceOrphanApprovedLink {
    pair_id: String,
    orphan_key: String,
    candidate_key: String,
    edge_type: String,
}

#[derive(Debug, Clone)]
struct PalaceMaterializationApprovedEdge {
    pair_id: String,
    from_key: String,
    to_key: String,
    edge_type: String,
}

#[derive(Debug, Clone, Eq, PartialEq, Hash)]
struct PalaceMaterializationReviewPair {
    from_key: String,
    to_key: String,
    edge_type: String,
}

#[derive(Debug, Default)]
struct PalaceOrphanApprovedLinkApplyOutcome {
    results: Vec<Value>,
    applied_count: u64,
    failed_count: u64,
    skipped_count: u64,
}

fn normalize_palace_orphan_decision(decision: &str) -> std::io::Result<&'static str> {
    match decision {
        "approve" => Ok("approve"),
        "reject" => Ok("reject"),
        "defer" => Ok("defer"),
        other => Err(std::io::Error::new(
            std::io::ErrorKind::InvalidInput,
            format!("unsupported palace orphan candidate decision: {other}"),
        )),
    }
}

fn palace_orphan_pair_id(pair: &PalaceOrphanCandidatePair) -> String {
    format!("{} -> {}", pair.orphan_key, pair.candidate_key)
}

fn palace_materialization_pair_id(pair: &PalaceMaterializationReviewPair) -> String {
    format!("{} -[{}]-> {}", pair.from_key, pair.edge_type, pair.to_key)
}

fn normalize_palace_materialization_edge_type(edge_type: Option<&str>) -> String {
    let value = edge_type
        .map(str::trim)
        .filter(|value| !value.is_empty())
        .unwrap_or("relates");
    value
        .chars()
        .filter(|ch| ch.is_ascii_alphanumeric() || *ch == '_' || *ch == '-')
        .take(64)
        .collect::<String>()
        .trim()
        .to_string()
}

fn default_palace_review_dir_path() -> PathBuf {
    if let Some(path) = std::env::var_os("AB_PALACE_REVIEW_DIR") {
        return PathBuf::from(path);
    }
    palace_private_home_dir_path().join("palace-review")
}

fn default_palace_orphan_candidate_decisions_path() -> PathBuf {
    if let Some(path) = std::env::var_os("AB_PALACE_ORPHAN_CANDIDATE_DECISIONS") {
        return PathBuf::from(path);
    }
    default_palace_review_dir_path().join("orphan-candidate-decisions.jsonl")
}

fn default_palace_orphan_approved_link_apply_path() -> PathBuf {
    if let Some(path) = std::env::var_os("AB_PALACE_ORPHAN_APPROVED_LINK_APPLY_AUDIT") {
        return PathBuf::from(path);
    }
    default_palace_review_dir_path().join("orphan-approved-link-apply.jsonl")
}

fn default_palace_materialization_review_packet_path() -> PathBuf {
    if let Some(path) = std::env::var_os("AB_PALACE_MATERIALIZATION_REVIEW_PACKET_JSON") {
        return PathBuf::from(path);
    }
    PathBuf::from(DEFAULT_PALACE_MATERIALIZATION_REVIEW_PACKET_JSON)
}

fn default_palace_materialization_review_decisions_path() -> PathBuf {
    if let Some(path) = std::env::var_os("AB_PALACE_MATERIALIZATION_REVIEW_DECISIONS") {
        return PathBuf::from(path);
    }
    default_palace_review_dir_path().join("materialization-review-decisions.jsonl")
}

fn default_palace_materialization_approved_edge_apply_path() -> PathBuf {
    if let Some(path) = std::env::var_os("AB_PALACE_MATERIALIZATION_APPROVED_EDGE_APPLY_AUDIT") {
        return PathBuf::from(path);
    }
    default_palace_review_dir_path().join("materialization-approved-edge-apply.jsonl")
}

fn palace_private_home_dir_path() -> PathBuf {
    palace_home_dir().join(".agent-bridge-private")
}

fn palace_home_dir() -> PathBuf {
    std::env::var("HOME")
        .map(PathBuf::from)
        .unwrap_or_else(|_| PathBuf::from("/tmp"))
}

fn palace_orphan_candidate_decision_record_for_time(
    pair: &PalaceOrphanCandidatePair,
    decision: &str,
    reviewer: Option<&str>,
    note: Option<&str>,
    generated_at_unix: u64,
) -> std::io::Result<Value> {
    let decision = normalize_palace_orphan_decision(decision)?;
    Ok(json!({
        "schema": "agent_bridge.palace.orphan_candidate_decision.v0",
        "generated_at_unix": generated_at_unix,
        "pair_id": palace_orphan_pair_id(pair),
        "orphan_key": pair.orphan_key,
        "candidate_key": pair.candidate_key,
        "decision": decision,
        "reviewer": reviewer,
        "note": note,
        "writes_memory": false,
        "writes_edges": false,
        "auto_apply_allowed": false,
    }))
}

fn load_palace_orphan_candidate_decisions(path: &FsPath) -> std::io::Result<Vec<Value>> {
    let text = match std::fs::read_to_string(path) {
        Ok(text) => text,
        Err(e) if e.kind() == std::io::ErrorKind::NotFound => return Ok(Vec::new()),
        Err(e) => return Err(e),
    };
    let mut decisions = Vec::new();
    for line in text.lines().filter(|line| !line.trim().is_empty()) {
        let value: Value = serde_json::from_str(line)
            .map_err(|e| std::io::Error::new(std::io::ErrorKind::InvalidData, e))?;
        if value.get("schema").and_then(|v| v.as_str())
            == Some("agent_bridge.palace.orphan_candidate_decision.v0")
        {
            decisions.push(value);
        }
    }
    decisions.sort_by_key(|value| {
        value
            .get("generated_at_unix")
            .and_then(|v| v.as_u64())
            .unwrap_or(0)
    });
    Ok(decisions)
}

fn append_palace_orphan_candidate_decision(path: &FsPath, value: &Value) -> std::io::Result<()> {
    if let Some(parent) = path.parent() {
        std::fs::create_dir_all(parent)?;
        set_palace_private_home_root_permissions_if_needed(parent)?;
        set_palace_private_dir_permissions(parent)?;
    }
    let mut file = std::fs::OpenOptions::new()
        .create(true)
        .append(true)
        .open(path)?;
    let line = serde_json::to_string(value)
        .map_err(|e| std::io::Error::new(std::io::ErrorKind::InvalidData, e))?;
    writeln!(file, "{line}")?;
    set_palace_private_file_permissions(path)?;
    Ok(())
}

fn palace_materialization_review_pair_from_candidate(
    candidate: &Value,
) -> Option<PalaceMaterializationReviewPair> {
    let from_key = candidate.get("from_key").and_then(Value::as_str)?.trim();
    let to_key = candidate.get("to_key").and_then(Value::as_str)?.trim();
    if from_key.is_empty() || to_key.is_empty() {
        return None;
    }
    let edge_type = normalize_palace_materialization_edge_type(
        candidate.get("edge_type").and_then(Value::as_str),
    );
    if edge_type.is_empty() {
        return None;
    }
    Some(PalaceMaterializationReviewPair {
        from_key: from_key.to_string(),
        to_key: to_key.to_string(),
        edge_type,
    })
}

fn palace_materialization_review_decision_record_for_time(
    pair: &PalaceMaterializationReviewPair,
    decision: &str,
    reviewer: Option<&str>,
    note: Option<&str>,
    generated_at_unix: u64,
) -> std::io::Result<Value> {
    let decision = normalize_palace_orphan_decision(decision)?;
    Ok(json!({
        "schema": "agent_bridge.palace.materialization_review_decision.v0",
        "generated_at_unix": generated_at_unix,
        "pair_id": palace_materialization_pair_id(pair),
        "from_key": pair.from_key,
        "to_key": pair.to_key,
        "edge_type": pair.edge_type,
        "decision": decision,
        "reviewer": reviewer,
        "note": note,
        "writes_memory": false,
        "writes_edges": false,
        "changes_search_order": false,
        "can_change_retrieval_order": false,
        "approval_writes_allowed": false,
        "can_materialize_edges": false,
        "auto_apply_allowed": false,
    }))
}

fn load_palace_materialization_review_decisions(path: &FsPath) -> std::io::Result<Vec<Value>> {
    let text = match std::fs::read_to_string(path) {
        Ok(text) => text,
        Err(e) if e.kind() == std::io::ErrorKind::NotFound => return Ok(Vec::new()),
        Err(e) => return Err(e),
    };
    let mut decisions = Vec::new();
    for line in text.lines().filter(|line| !line.trim().is_empty()) {
        let value: Value = serde_json::from_str(line)
            .map_err(|e| std::io::Error::new(std::io::ErrorKind::InvalidData, e))?;
        if value.get("schema").and_then(|v| v.as_str())
            == Some("agent_bridge.palace.materialization_review_decision.v0")
        {
            decisions.push(value);
        }
    }
    decisions.sort_by_key(|value| {
        value
            .get("generated_at_unix")
            .and_then(|v| v.as_u64())
            .unwrap_or(0)
    });
    Ok(decisions)
}

fn append_palace_materialization_review_decision(
    path: &FsPath,
    value: &Value,
) -> std::io::Result<()> {
    if let Some(parent) = path.parent() {
        std::fs::create_dir_all(parent)?;
        set_palace_private_home_root_permissions_if_needed(parent)?;
        set_palace_private_dir_permissions(parent)?;
    }
    let mut file = std::fs::OpenOptions::new()
        .create(true)
        .append(true)
        .open(path)?;
    let line = serde_json::to_string(value)
        .map_err(|e| std::io::Error::new(std::io::ErrorKind::InvalidData, e))?;
    writeln!(file, "{line}")?;
    set_palace_private_file_permissions(path)?;
    Ok(())
}

fn palace_materialization_approved_edge_apply_record_for_time(
    response: &Value,
    actor: Option<&str>,
    generated_at_unix: u64,
) -> Value {
    json!({
        "schema": "agent_bridge.palace.materialization_approved_edge_apply_audit.v0",
        "generated_at_unix": generated_at_unix,
        "actor": actor.map(str::trim).filter(|value| !value.is_empty()),
        "response_schema": response.get("schema").cloned().unwrap_or(Value::Null),
        "status": response.get("status").cloned().unwrap_or(Value::Null),
        "blocked": response.get("blocked").cloned().unwrap_or(json!(true)),
        "dry_run": response.get("dry_run").cloned().unwrap_or(json!(true)),
        "approved_pair_count": response.get("approved_pair_count").cloned().unwrap_or(json!(0)),
        "would_write_edges": response.get("would_write_edges").cloned().unwrap_or(json!(0)),
        "applied_count": response.get("applied_count").cloned().unwrap_or(json!(0)),
        "failed_count": response.get("failed_count").cloned().unwrap_or(json!(0)),
        "skipped_count": response.get("skipped_count").cloned().unwrap_or(json!(0)),
        "writes_memory": response.get("writes_memory").cloned().unwrap_or(json!(false)),
        "writes_edges": response.get("writes_edges").cloned().unwrap_or(json!(false)),
        "changes_search_order": response.get("changes_search_order").cloned().unwrap_or(json!(false)),
        "can_change_retrieval_order": response
            .get("can_change_retrieval_order")
            .cloned()
            .unwrap_or(json!(false)),
        "approval_writes_allowed": response
            .get("approval_writes_allowed")
            .cloned()
            .unwrap_or(json!(false)),
        "can_materialize_edges": response
            .get("can_materialize_edges")
            .cloned()
            .unwrap_or(json!(false)),
        "blocking_reasons": response.get("blocking_reasons").cloned().unwrap_or_else(|| json!([])),
        "results": response.get("results").cloned().unwrap_or_else(|| json!([])),
    })
}

fn load_palace_materialization_approved_edge_apply_records(
    path: &FsPath,
) -> std::io::Result<Vec<Value>> {
    let text = match std::fs::read_to_string(path) {
        Ok(text) => text,
        Err(e) if e.kind() == std::io::ErrorKind::NotFound => return Ok(Vec::new()),
        Err(e) => return Err(e),
    };
    let mut records = Vec::new();
    for line in text.lines().filter(|line| !line.trim().is_empty()) {
        let stream = serde_json::Deserializer::from_str(line).into_iter::<Value>();
        for parsed in stream {
            let Ok(value) = parsed else {
                continue;
            };
            if value.get("schema").and_then(|v| v.as_str())
                == Some("agent_bridge.palace.materialization_approved_edge_apply_audit.v0")
            {
                records.push(value);
            }
        }
    }
    records.sort_by_key(|value| {
        value
            .get("generated_at_unix")
            .and_then(|v| v.as_u64())
            .unwrap_or(0)
    });
    Ok(records)
}

fn append_palace_materialization_approved_edge_apply_record(
    path: &FsPath,
    value: &Value,
) -> std::io::Result<()> {
    if let Some(parent) = path.parent() {
        std::fs::create_dir_all(parent)?;
        set_palace_private_home_root_permissions_if_needed(parent)?;
        set_palace_private_dir_permissions(parent)?;
    }
    let mut file = std::fs::OpenOptions::new()
        .create(true)
        .append(true)
        .open(path)?;
    let line = serde_json::to_string(value)
        .map_err(|e| std::io::Error::new(std::io::ErrorKind::InvalidData, e))?;
    writeln!(file, "{line}")?;
    set_palace_private_file_permissions(path)?;
    Ok(())
}

fn palace_orphan_approved_link_apply_record_for_time(
    response: &Value,
    actor: Option<&str>,
    generated_at_unix: u64,
) -> Value {
    json!({
        "schema": "agent_bridge.palace.orphan_approved_link_apply_audit.v0",
        "generated_at_unix": generated_at_unix,
        "actor": actor.map(str::trim).filter(|value| !value.is_empty()),
        "response_schema": response.get("schema").cloned().unwrap_or(Value::Null),
        "status": response.get("status").cloned().unwrap_or(Value::Null),
        "blocked": response.get("blocked").cloned().unwrap_or(json!(true)),
        "dry_run": response.get("dry_run").cloned().unwrap_or(json!(true)),
        "approved_pair_count": response.get("approved_pair_count").cloned().unwrap_or(json!(0)),
        "would_write_edges": response.get("would_write_edges").cloned().unwrap_or(json!(0)),
        "applied_count": response.get("applied_count").cloned().unwrap_or(json!(0)),
        "failed_count": response.get("failed_count").cloned().unwrap_or(json!(0)),
        "skipped_count": response.get("skipped_count").cloned().unwrap_or(json!(0)),
        "writes_memory": response.get("writes_memory").cloned().unwrap_or(json!(false)),
        "writes_edges": response.get("writes_edges").cloned().unwrap_or(json!(false)),
        "blocking_reasons": response.get("blocking_reasons").cloned().unwrap_or_else(|| json!([])),
        "results": response.get("results").cloned().unwrap_or_else(|| json!([])),
        "region": response.get("region").cloned().unwrap_or(Value::Null),
        "threshold": response.get("threshold").cloned().unwrap_or(Value::Null),
        "max_orphans": response.get("max_orphans").cloned().unwrap_or(Value::Null),
        "candidate_limit": response.get("candidate_limit").cloned().unwrap_or(Value::Null),
    })
}

fn load_palace_orphan_approved_link_apply_records(path: &FsPath) -> std::io::Result<Vec<Value>> {
    let text = match std::fs::read_to_string(path) {
        Ok(text) => text,
        Err(e) if e.kind() == std::io::ErrorKind::NotFound => return Ok(Vec::new()),
        Err(e) => return Err(e),
    };
    let mut records = Vec::new();
    for line in text.lines().filter(|line| !line.trim().is_empty()) {
        let stream = serde_json::Deserializer::from_str(line).into_iter::<Value>();
        for parsed in stream {
            let Ok(value) = parsed else {
                continue;
            };
            if value.get("schema").and_then(|v| v.as_str())
                == Some("agent_bridge.palace.orphan_approved_link_apply_audit.v0")
            {
                records.push(value);
            }
        }
    }
    records.sort_by_key(|value| {
        value
            .get("generated_at_unix")
            .and_then(|v| v.as_u64())
            .unwrap_or(0)
    });
    Ok(records)
}

fn append_palace_orphan_approved_link_apply_record(
    path: &FsPath,
    value: &Value,
) -> std::io::Result<()> {
    if let Some(parent) = path.parent() {
        std::fs::create_dir_all(parent)?;
        set_palace_private_home_root_permissions_if_needed(parent)?;
        set_palace_private_dir_permissions(parent)?;
    }
    let mut file = std::fs::OpenOptions::new()
        .create(true)
        .append(true)
        .open(path)?;
    let line = serde_json::to_string(value)
        .map_err(|e| std::io::Error::new(std::io::ErrorKind::InvalidData, e))?;
    writeln!(file, "{line}")?;
    set_palace_private_file_permissions(path)?;
    Ok(())
}

fn set_palace_private_home_root_permissions_if_needed(path: &FsPath) -> std::io::Result<()> {
    let private_root = palace_private_home_dir_path();
    if path.starts_with(&private_root) && private_root.is_dir() {
        set_palace_private_dir_permissions(&private_root)?;
    }
    Ok(())
}

#[cfg(unix)]
fn set_palace_private_dir_permissions(path: &FsPath) -> std::io::Result<()> {
    use std::os::unix::fs::PermissionsExt;
    std::fs::set_permissions(path, std::fs::Permissions::from_mode(0o700))
}

#[cfg(not(unix))]
fn set_palace_private_dir_permissions(_path: &FsPath) -> std::io::Result<()> {
    Ok(())
}

#[cfg(unix)]
fn set_palace_private_file_permissions(path: &FsPath) -> std::io::Result<()> {
    use std::os::unix::fs::PermissionsExt;
    std::fs::set_permissions(path, std::fs::Permissions::from_mode(0o600))
}

#[cfg(not(unix))]
fn set_palace_private_file_permissions(_path: &FsPath) -> std::io::Result<()> {
    Ok(())
}

fn palace_orphan_candidate_decision_inbox_for_pairs(
    pairs: &[PalaceOrphanCandidatePair],
    decisions: &[Value],
) -> Value {
    let mut latest_by_pair: BTreeMap<(String, String), &Value> = BTreeMap::new();
    for decision in decisions.iter().filter(|value| {
        value.get("schema").and_then(|v| v.as_str())
            == Some("agent_bridge.palace.orphan_candidate_decision.v0")
    }) {
        let Some(orphan_key) = decision.get("orphan_key").and_then(|v| v.as_str()) else {
            continue;
        };
        let Some(candidate_key) = decision.get("candidate_key").and_then(|v| v.as_str()) else {
            continue;
        };
        let key = (orphan_key.to_string(), candidate_key.to_string());
        let current_ts = decision
            .get("generated_at_unix")
            .and_then(|v| v.as_u64())
            .unwrap_or(0);
        let existing_ts = latest_by_pair
            .get(&key)
            .and_then(|v| v.get("generated_at_unix"))
            .and_then(|v| v.as_u64())
            .unwrap_or(0);
        if !latest_by_pair.contains_key(&key) || current_ts >= existing_ts {
            latest_by_pair.insert(key, decision);
        }
    }

    let mut pending_count = 0_u64;
    let mut approved_count = 0_u64;
    let mut rejected_count = 0_u64;
    let mut deferred_count = 0_u64;
    let candidates: Vec<Value> = pairs
        .iter()
        .map(|pair| {
            let key = (pair.orphan_key.clone(), pair.candidate_key.clone());
            let latest = latest_by_pair.get(&key).copied();
            let decision = latest
                .and_then(|value| value.get("decision"))
                .and_then(|value| value.as_str())
                .unwrap_or("pending");
            match decision {
                "approve" => approved_count += 1,
                "reject" => rejected_count += 1,
                "defer" => deferred_count += 1,
                _ => pending_count += 1,
            }
            json!({
                "pair_id": palace_orphan_pair_id(pair),
                "orphan_key": pair.orphan_key,
                "candidate_key": pair.candidate_key,
                "decision": decision,
                "latest_decision_at_unix": latest
                    .and_then(|value| value.get("generated_at_unix"))
                    .cloned()
                    .unwrap_or(Value::Null),
                "reviewer": latest
                    .and_then(|value| value.get("reviewer"))
                    .cloned()
                    .unwrap_or(Value::Null),
                "note": latest
                    .and_then(|value| value.get("note"))
                    .cloned()
                    .unwrap_or(Value::Null),
            })
        })
        .collect();

    json!({
        "schema": "agent_bridge.palace.orphan_candidate_decision_inbox.v0",
        "read_only": true,
        "candidate_count": candidates.len(),
        "pending_count": pending_count,
        "approved_count": approved_count,
        "rejected_count": rejected_count,
        "deferred_count": deferred_count,
        "writes_memory": false,
        "writes_edges": false,
        "auto_apply_allowed": false,
        "candidates": candidates,
    })
}

fn palace_orphan_candidate_pairs_for_preview(
    preview: &PalaceOrphanCandidatePreview,
) -> Vec<PalaceOrphanCandidatePair> {
    preview
        .rows
        .iter()
        .flat_map(|row| {
            row.suggestions
                .iter()
                .map(|candidate| PalaceOrphanCandidatePair {
                    orphan_key: row.orphan.key.clone(),
                    candidate_key: candidate.key.clone(),
                })
                .collect::<Vec<_>>()
        })
        .collect()
}

fn palace_orphan_review_by_pair(inbox: &Value) -> BTreeMap<(String, String), Value> {
    let mut out = BTreeMap::new();
    if let Some(candidates) = inbox.get("candidates").and_then(|v| v.as_array()) {
        for candidate in candidates {
            let Some(orphan_key) = candidate.get("orphan_key").and_then(|v| v.as_str()) else {
                continue;
            };
            let Some(candidate_key) = candidate.get("candidate_key").and_then(|v| v.as_str())
            else {
                continue;
            };
            out.insert(
                (orphan_key.to_string(), candidate_key.to_string()),
                candidate.clone(),
            );
        }
    }
    out
}

fn palace_orphan_approved_link_plan_for_inbox(inbox: &Value) -> Value {
    let links: Vec<Value> = inbox
        .get("candidates")
        .and_then(|v| v.as_array())
        .into_iter()
        .flatten()
        .filter(|candidate| candidate.get("decision").and_then(|v| v.as_str()) == Some("approve"))
        .filter_map(|candidate| {
            let orphan_key = candidate.get("orphan_key").and_then(|v| v.as_str())?;
            let candidate_key = candidate.get("candidate_key").and_then(|v| v.as_str())?;
            Some(json!({
                "pair_id": candidate
                    .get("pair_id")
                    .cloned()
                    .unwrap_or_else(|| json!(format!("{orphan_key} -> {candidate_key}"))),
                "orphan_key": orphan_key,
                "candidate_key": candidate_key,
                "edge_type": "relates",
                "decision": "approve",
                "latest_decision_at_unix": candidate
                    .get("latest_decision_at_unix")
                    .cloned()
                    .unwrap_or(Value::Null),
                "reviewer": candidate.get("reviewer").cloned().unwrap_or(Value::Null),
                "note": candidate.get("note").cloned().unwrap_or(Value::Null),
            }))
        })
        .collect();

    json!({
        "schema": "agent_bridge.palace.orphan_approved_link_plan.v0",
        "read_only": true,
        "approved_pair_count": links.len(),
        "edge_type": "relates",
        "writes_memory": false,
        "writes_edges": false,
        "auto_apply_allowed": false,
        "links": links,
        "next_step": "Review this approved plan before invoking any write-capable memory edge tool.",
    })
}

fn palace_orphan_approved_links_from_plan(plan: &Value) -> Vec<PalaceOrphanApprovedLink> {
    plan.get("links")
        .and_then(|v| v.as_array())
        .into_iter()
        .flatten()
        .filter_map(|link| {
            let orphan_key = link.get("orphan_key").and_then(|v| v.as_str())?.trim();
            let candidate_key = link.get("candidate_key").and_then(|v| v.as_str())?.trim();
            if orphan_key.is_empty() || candidate_key.is_empty() {
                return None;
            }
            let edge_type = link
                .get("edge_type")
                .and_then(|v| v.as_str())
                .unwrap_or("relates")
                .trim();
            Some(PalaceOrphanApprovedLink {
                pair_id: link
                    .get("pair_id")
                    .and_then(|v| v.as_str())
                    .map(str::to_string)
                    .unwrap_or_else(|| format!("{orphan_key} -> {candidate_key}")),
                orphan_key: orphan_key.to_string(),
                candidate_key: candidate_key.to_string(),
                edge_type: if edge_type.is_empty() {
                    "relates".to_string()
                } else {
                    edge_type.to_string()
                },
            })
        })
        .collect()
}

fn palace_orphan_approved_link_apply_gate_for_plan(
    plan: &Value,
    dry_run: bool,
    confirm: Option<&str>,
) -> Value {
    let links = palace_orphan_approved_links_from_plan(plan);
    let confirmation_required = !dry_run && !links.is_empty();
    let confirmation_matches = confirm
        .map(str::trim)
        .is_some_and(|value| value == PALACE_ORPHAN_APPROVED_LINK_APPLY_CONFIRM);
    let mut blocking_reasons = Vec::new();
    if confirmation_required && !confirmation_matches {
        blocking_reasons.push("confirmation_required");
    }
    json!({
        "schema": "agent_bridge.palace.orphan_approved_link_apply.v0",
        "dry_run": dry_run,
        "blocked": !blocking_reasons.is_empty(),
        "status": if blocking_reasons.is_empty() { "ready" } else { "blocked" },
        "confirm_phrase": PALACE_ORPHAN_APPROVED_LINK_APPLY_CONFIRM,
        "confirmation_required": confirmation_required,
        "confirmation_matches": confirmation_matches,
        "approved_pair_count": links.len(),
        "would_write_edges": links.len(),
        "writes_memory": false,
        "writes_edges": false,
        "auto_apply_allowed": false,
        "blocking_reasons": blocking_reasons,
    })
}

async fn palace_orphan_approved_link_apply_links(
    store: &dyn StateStore,
    links: Vec<PalaceOrphanApprovedLink>,
    dry_run: bool,
) -> PalaceOrphanApprovedLinkApplyOutcome {
    let mut outcome = PalaceOrphanApprovedLinkApplyOutcome::default();
    for link in links {
        if link.edge_type != "relates" {
            outcome.skipped_count += 1;
            outcome.results.push(json!({
                "pair_id": link.pair_id,
                "orphan_key": link.orphan_key,
                "candidate_key": link.candidate_key,
                "edge_type": link.edge_type,
                "status": "skipped_unsupported_edge_type",
            }));
            continue;
        }
        if link.orphan_key == link.candidate_key {
            outcome.skipped_count += 1;
            outcome.results.push(json!({
                "pair_id": link.pair_id,
                "orphan_key": link.orphan_key,
                "candidate_key": link.candidate_key,
                "edge_type": link.edge_type,
                "status": "skipped_self_edge",
            }));
            continue;
        }
        if dry_run {
            outcome.results.push(json!({
                "pair_id": link.pair_id,
                "orphan_key": link.orphan_key,
                "candidate_key": link.candidate_key,
                "edge_type": link.edge_type,
                "status": "would_write",
            }));
            continue;
        }
        match store
            .memory_link(&link.orphan_key, &link.candidate_key, &link.edge_type, 1.0)
            .await
        {
            Ok(()) => {
                outcome.applied_count += 1;
                outcome.results.push(json!({
                    "pair_id": link.pair_id,
                    "orphan_key": link.orphan_key,
                    "candidate_key": link.candidate_key,
                    "edge_type": link.edge_type,
                    "status": "applied",
                }));
            }
            Err(e) => {
                outcome.failed_count += 1;
                outcome.results.push(json!({
                    "pair_id": link.pair_id,
                    "orphan_key": link.orphan_key,
                    "candidate_key": link.candidate_key,
                    "edge_type": link.edge_type,
                    "status": "failed",
                    "error": e.to_string(),
                }));
            }
        }
    }
    outcome
}

fn palace_orphan_approved_link_plan_for_preview(
    preview: &PalaceOrphanCandidatePreview,
    decisions: &[Value],
) -> Value {
    let pairs = palace_orphan_candidate_pairs_for_preview(preview);
    let inbox = palace_orphan_candidate_decision_inbox_for_pairs(&pairs, decisions);
    let mut plan = palace_orphan_approved_link_plan_for_inbox(&inbox);
    let mut evidence_by_pair: BTreeMap<(String, String), &PalaceLinkSuggestion> = BTreeMap::new();
    for row in &preview.rows {
        for suggestion in &row.suggestions {
            evidence_by_pair.insert((row.orphan.key.clone(), suggestion.key.clone()), suggestion);
        }
    }

    let mut safe_links = Vec::new();
    let mut blocked = Vec::new();
    if let Some(links) = plan.get_mut("links").and_then(Value::as_array_mut) {
        for link in links.iter_mut() {
            let orphan_key = link
                .get("orphan_key")
                .and_then(Value::as_str)
                .unwrap_or("")
                .to_string();
            let candidate_key = link
                .get("candidate_key")
                .and_then(Value::as_str)
                .unwrap_or("")
                .to_string();
            let evidence = evidence_by_pair.get(&(orphan_key.clone(), candidate_key.clone()));
            if let Some(evidence) = evidence {
                if let Some(obj) = link.as_object_mut() {
                    obj.insert("confidence".to_string(), json!(evidence.confidence));
                    obj.insert("reason".to_string(), json!(evidence.reason));
                    obj.insert("scope".to_string(), json!(evidence.scope));
                    obj.insert("scope_relation".to_string(), json!(evidence.scope_relation));
                    obj.insert("preview".to_string(), json!(evidence.preview));
                }
            }

            let confidence = evidence.map(|e| e.confidence).unwrap_or(0.0);
            let scope_relation = evidence
                .map(|e| e.scope_relation)
                .unwrap_or("unknown_scope_relation");
            let blocked_reason = if scope_relation != PALACE_ORPHAN_SAFE_BATCH_SCOPE_RELATION {
                Some("scope_relation_not_safe")
            } else if confidence < PALACE_ORPHAN_SAFE_BATCH_MIN_CONFIDENCE {
                Some("confidence_below_safe_threshold")
            } else {
                None
            };

            if let Some(reason) = blocked_reason {
                blocked.push(json!({
                    "pair_id": link.get("pair_id").cloned().unwrap_or(Value::Null),
                    "orphan_key": orphan_key,
                    "candidate_key": candidate_key,
                    "confidence": confidence,
                    "scope_relation": scope_relation,
                    "reason": reason,
                }));
            } else if safe_links.len() < PALACE_ORPHAN_SAFE_BATCH_LIMIT {
                safe_links.push(link.clone());
            } else {
                blocked.push(json!({
                    "pair_id": link.get("pair_id").cloned().unwrap_or(Value::Null),
                    "orphan_key": orphan_key,
                    "candidate_key": candidate_key,
                    "confidence": confidence,
                    "scope_relation": scope_relation,
                    "reason": "safe_batch_limit_reached",
                }));
            }
        }
    }

    if let Some(obj) = plan.as_object_mut() {
        obj.insert(
            "safe_batch".to_string(),
            json!({
                "schema": "agent_bridge.palace.orphan_safe_batch.v0",
                "read_only": true,
                "writes_memory": false,
                "writes_edges": false,
                "auto_apply_allowed": false,
                "limit": PALACE_ORPHAN_SAFE_BATCH_LIMIT,
                "min_confidence": PALACE_ORPHAN_SAFE_BATCH_MIN_CONFIDENCE,
                "required_scope_relation": PALACE_ORPHAN_SAFE_BATCH_SCOPE_RELATION,
                "eligible_count": safe_links.len(),
                "blocked_count": blocked.len(),
                "links": safe_links,
                "blocked": blocked,
                "next_step": "Dry-run the safe batch first, then apply only after human confirmation.",
            }),
        );
    }
    plan
}

fn palace_json_u64_at(value: &Value, path: &[&str]) -> u64 {
    let mut current = value;
    for key in path {
        let Some(next) = current.get(*key) else {
            return 0;
        };
        current = next;
    }
    if let Some(value) = current.as_u64() {
        return value;
    }
    current.as_i64().filter(|value| *value > 0).unwrap_or(0) as u64
}

fn palace_json_bool_at(value: &Value, path: &[&str]) -> bool {
    let mut current = value;
    for key in path {
        let Some(next) = current.get(*key) else {
            return false;
        };
        current = next;
    }
    current.as_bool().unwrap_or(false)
}

fn palace_materialization_review_candidate_has_write_signal(candidate: &Value) -> bool {
    palace_json_bool_at(candidate, &["writes_memory"])
        || palace_json_bool_at(candidate, &["writes_edges"])
        || palace_json_bool_at(candidate, &["changes_search_order"])
        || palace_json_bool_at(candidate, &["can_change_retrieval_order"])
        || palace_json_bool_at(candidate, &["approval_writes_allowed"])
        || palace_json_bool_at(candidate, &["can_materialize_edges"])
}

fn parse_palace_materialization_review_packet(raw: &str, source: &str) -> Result<Value, String> {
    let packet: Value = serde_json::from_str(&raw)
        .map_err(|e| format!("parse materialization review packet {source}: {e}"))?;
    if packet.get("schema").and_then(Value::as_str)
        != Some("agent_bridge.biocortex_retrieval.materialization_review_packet.v0")
    {
        return Err(format!(
            "unexpected materialization review packet schema at {source}"
        ));
    }
    if !palace_json_bool_at(&packet, &["read_only"])
        || palace_json_bool_at(&packet, &["writes_memory"])
        || palace_json_bool_at(&packet, &["writes_edges"])
        || palace_json_bool_at(&packet, &["changes_search_order"])
        || palace_json_bool_at(&packet, &["can_change_retrieval_order"])
        || palace_json_bool_at(&packet, &["approval_writes_allowed"])
        || palace_json_bool_at(&packet, &["can_materialize_edges"])
    {
        return Err(format!(
            "materialization review packet at {source} is not read-only"
        ));
    }
    if packet
        .get("candidates")
        .and_then(Value::as_array)
        .is_some_and(|candidates| {
            candidates
                .iter()
                .any(palace_materialization_review_candidate_has_write_signal)
        })
    {
        return Err(format!(
            "materialization review packet at {source} is not read-only"
        ));
    }
    Ok(packet)
}

fn load_palace_materialization_review_packet(path: &FsPath) -> Result<Value, String> {
    let raw = fs::read_to_string(path)
        .map_err(|e| format!("read materialization review packet {}: {e}", path.display()))?;
    parse_palace_materialization_review_packet(&raw, &path.display().to_string())
}

fn load_default_palace_materialization_review_packet(path: &FsPath) -> Result<Value, String> {
    if std::env::var_os("AB_PALACE_MATERIALIZATION_REVIEW_PACKET_JSON").is_some() {
        return load_palace_materialization_review_packet(path);
    }

    load_palace_materialization_review_packet(path).or_else(|err| {
        if path == FsPath::new(DEFAULT_PALACE_MATERIALIZATION_REVIEW_PACKET_JSON)
            && err.starts_with("read materialization review packet ")
        {
            parse_palace_materialization_review_packet(
                DEFAULT_PALACE_MATERIALIZATION_REVIEW_PACKET_BODY,
                DEFAULT_PALACE_MATERIALIZATION_REVIEW_PACKET_JSON,
            )
        } else {
            Err(err)
        }
    })
}

fn palace_materialization_review_decision_inbox_for_packet(
    packet: &Value,
    decisions: &[Value],
) -> Value {
    let mut latest_by_pair: BTreeMap<(String, String, String), &Value> = BTreeMap::new();
    for decision in decisions.iter().filter(|value| {
        value.get("schema").and_then(|v| v.as_str())
            == Some("agent_bridge.palace.materialization_review_decision.v0")
    }) {
        let Some(from_key) = decision.get("from_key").and_then(Value::as_str) else {
            continue;
        };
        let Some(to_key) = decision.get("to_key").and_then(Value::as_str) else {
            continue;
        };
        let edge_type = normalize_palace_materialization_edge_type(
            decision.get("edge_type").and_then(Value::as_str),
        );
        if from_key.trim().is_empty() || to_key.trim().is_empty() || edge_type.is_empty() {
            continue;
        }
        let key = (from_key.to_string(), to_key.to_string(), edge_type);
        let current_ts = decision
            .get("generated_at_unix")
            .and_then(Value::as_u64)
            .unwrap_or(0);
        let existing_ts = latest_by_pair
            .get(&key)
            .and_then(|v| v.get("generated_at_unix"))
            .and_then(Value::as_u64)
            .unwrap_or(0);
        if !latest_by_pair.contains_key(&key) || current_ts >= existing_ts {
            latest_by_pair.insert(key, decision);
        }
    }

    let mut pending_count = 0_u64;
    let mut approved_count = 0_u64;
    let mut rejected_count = 0_u64;
    let mut deferred_count = 0_u64;
    let candidates: Vec<Value> = packet
        .get("candidates")
        .and_then(Value::as_array)
        .into_iter()
        .flatten()
        .filter_map(|candidate| {
            let pair = palace_materialization_review_pair_from_candidate(candidate)?;
            let key = (
                pair.from_key.clone(),
                pair.to_key.clone(),
                pair.edge_type.clone(),
            );
            let latest = latest_by_pair.get(&key).copied();
            let decision = latest
                .and_then(|value| value.get("decision"))
                .and_then(Value::as_str)
                .unwrap_or("pending");
            match decision {
                "approve" => approved_count += 1,
                "reject" => rejected_count += 1,
                "defer" => deferred_count += 1,
                _ => pending_count += 1,
            }
            let review = json!({
                "pair_id": palace_materialization_pair_id(&pair),
                "from_key": pair.from_key,
                "to_key": pair.to_key,
                "edge_type": pair.edge_type,
                "decision": decision,
                "latest_decision_at_unix": latest
                    .and_then(|value| value.get("generated_at_unix"))
                    .cloned()
                    .unwrap_or(Value::Null),
                "reviewer": latest
                    .and_then(|value| value.get("reviewer"))
                    .cloned()
                    .unwrap_or(Value::Null),
                "note": latest
                    .and_then(|value| value.get("note"))
                    .cloned()
                    .unwrap_or(Value::Null),
            });
            let mut candidate_with_review = candidate.clone();
            if let Some(obj) = candidate_with_review.as_object_mut() {
                obj.insert("review".to_string(), review.clone());
            }
            Some(json!({
                "pair_id": review.get("pair_id").cloned().unwrap_or(Value::Null),
                "from_key": review.get("from_key").cloned().unwrap_or(Value::Null),
                "to_key": review.get("to_key").cloned().unwrap_or(Value::Null),
                "edge_type": review.get("edge_type").cloned().unwrap_or(Value::Null),
                "decision": decision,
                "latest_decision_at_unix": review
                    .get("latest_decision_at_unix")
                    .cloned()
                    .unwrap_or(Value::Null),
                "reviewer": review.get("reviewer").cloned().unwrap_or(Value::Null),
                "note": review.get("note").cloned().unwrap_or(Value::Null),
                "candidate": candidate_with_review,
            }))
        })
        .collect();

    json!({
        "schema": "agent_bridge.palace.materialization_review_decision_inbox.v0",
        "read_only": true,
        "candidate_count": candidates.len(),
        "pending_count": pending_count,
        "approved_count": approved_count,
        "rejected_count": rejected_count,
        "deferred_count": deferred_count,
        "writes_memory": false,
        "writes_edges": false,
        "changes_search_order": false,
        "can_change_retrieval_order": false,
        "approval_writes_allowed": false,
        "can_materialize_edges": false,
        "auto_apply_allowed": false,
        "candidates": candidates,
    })
}

fn palace_materialization_approved_edge_plan_for_inbox(inbox: &Value) -> Value {
    let links: Vec<Value> = inbox
        .get("candidates")
        .and_then(Value::as_array)
        .into_iter()
        .flatten()
        .filter(|candidate| candidate.get("decision").and_then(Value::as_str) == Some("approve"))
        .filter_map(|candidate| {
            let full = candidate.get("candidate").and_then(Value::as_object)?;
            let from_key = candidate.get("from_key").and_then(Value::as_str)?;
            let to_key = candidate.get("to_key").and_then(Value::as_str)?;
            let edge_type = candidate
                .get("edge_type")
                .and_then(Value::as_str)
                .unwrap_or("relates");
            Some(json!({
                "pair_id": candidate.get("pair_id").cloned().unwrap_or_else(|| {
                    json!(format!("{from_key} -[{edge_type}]-> {to_key}"))
                }),
                "from_key": from_key,
                "to_key": to_key,
                "edge_type": edge_type,
                "decision": "approve",
                "latest_decision_at_unix": candidate
                    .get("latest_decision_at_unix")
                    .cloned()
                    .unwrap_or(Value::Null),
                "reviewer": candidate.get("reviewer").cloned().unwrap_or(Value::Null),
                "note": candidate.get("note").cloned().unwrap_or(Value::Null),
                "candidate_source": full.get("candidate_source").cloned().unwrap_or(Value::Null),
                "gate": full.get("gate").cloned().unwrap_or(Value::Null),
                "reason_kind": full.get("reason_kind").cloned().unwrap_or(Value::Null),
                "rationale": full.get("rationale").cloned().unwrap_or(Value::Null),
                "shadow_aligned": full.get("shadow_aligned").cloned().unwrap_or(Value::Null),
                "baseline_top3": full.get("baseline_top3").cloned().unwrap_or_else(|| json!([])),
                "preview_top3": full.get("preview_top3").cloned().unwrap_or_else(|| json!([])),
                "baseline_from_rank": full.get("baseline_from_rank").cloned().unwrap_or(Value::Null),
                "preview_from_rank": full.get("preview_from_rank").cloned().unwrap_or(Value::Null),
                "baseline_to_rank": full.get("baseline_to_rank").cloned().unwrap_or(Value::Null),
                "preview_to_rank": full.get("preview_to_rank").cloned().unwrap_or(Value::Null),
                "blend_coverage": full.get("blend_coverage").cloned().unwrap_or(Value::Null),
                "writes_memory": false,
                "writes_edges": false,
                "changes_search_order": false,
                "can_change_retrieval_order": false,
                "approval_writes_allowed": false,
                "can_materialize_edges": false,
            }))
        })
        .collect();

    json!({
        "schema": "agent_bridge.palace.materialization_approved_edge_plan.v0",
        "read_only": true,
        "dry_run": true,
        "approved_pair_count": links.len(),
        "would_write_edges": links.len(),
        "writes_memory": false,
        "writes_edges": false,
        "changes_search_order": false,
        "can_change_retrieval_order": false,
        "approval_writes_allowed": false,
        "can_materialize_edges": false,
        "auto_apply_allowed": false,
        "links": links,
        "next_step": "Dry-run only: review the approved edge plan before designing any separate write-capable materializer.",
    })
}

async fn palace_materialization_approved_edge_plan_mark_existing_edges(
    store: &dyn StateStore,
    mut plan: Value,
) -> std::result::Result<Value, String> {
    let mut approved_pair_count = 0usize;
    let mut already_materialized_edge_count = 0usize;
    let mut would_write_edges = 0usize;
    let mut neighbor_cache = BTreeMap::new();

    if let Some(links) = plan.get_mut("links").and_then(Value::as_array_mut) {
        approved_pair_count = links.len();
        for link in links {
            let from_key = link
                .get("from_key")
                .and_then(Value::as_str)
                .map(str::trim)
                .unwrap_or("")
                .to_string();
            let to_key = link
                .get("to_key")
                .and_then(Value::as_str)
                .map(str::trim)
                .unwrap_or("")
                .to_string();
            let edge_type = normalize_palace_materialization_edge_type(
                link.get("edge_type").and_then(Value::as_str),
            );

            let already_materialized =
                if from_key.is_empty() || to_key.is_empty() || edge_type.is_empty() {
                    false
                } else {
                    if !neighbor_cache.contains_key(&from_key) {
                        let edges = store.memory_neighbors(&from_key).await.map_err(|e| {
                            format!("load existing materialization edges for {from_key}: {e}")
                        })?;
                        neighbor_cache.insert(from_key.clone(), edges);
                    }
                    neighbor_cache
                        .get(&from_key)
                        .into_iter()
                        .flatten()
                        .any(|edge| {
                            edge.from_key == from_key
                                && edge.to_key == to_key
                                && edge.edge_type == edge_type
                        })
                };

            if let Some(obj) = link.as_object_mut() {
                obj.insert(
                    "already_materialized".to_string(),
                    json!(already_materialized),
                );
                obj.insert(
                    "materialization_status".to_string(),
                    json!(if already_materialized {
                        "already_materialized"
                    } else {
                        "pending"
                    }),
                );
                obj.insert("would_write_edge".to_string(), json!(!already_materialized));
            }

            if already_materialized {
                already_materialized_edge_count += 1;
            } else {
                would_write_edges += 1;
            }
        }
    }

    if let Some(obj) = plan.as_object_mut() {
        obj.insert(
            "approved_pair_count".to_string(),
            json!(approved_pair_count),
        );
        obj.insert("would_write_edges".to_string(), json!(would_write_edges));
        obj.insert(
            "already_materialized_edge_count".to_string(),
            json!(already_materialized_edge_count),
        );
        obj.insert(
            "pending_materialization_edge_count".to_string(),
            json!(would_write_edges),
        );
    }

    Ok(plan)
}

fn palace_materialization_approved_edges_from_plan(
    plan: &Value,
) -> Vec<PalaceMaterializationApprovedEdge> {
    plan.get("links")
        .and_then(Value::as_array)
        .into_iter()
        .flatten()
        .filter(|link| link.get("already_materialized").and_then(Value::as_bool) != Some(true))
        .filter(|link| link.get("would_write_edge").and_then(Value::as_bool) != Some(false))
        .filter_map(|link| {
            let from_key = link.get("from_key").and_then(Value::as_str)?.trim();
            let to_key = link.get("to_key").and_then(Value::as_str)?.trim();
            if from_key.is_empty() || to_key.is_empty() {
                return None;
            }
            let edge_type = normalize_palace_materialization_edge_type(
                link.get("edge_type").and_then(Value::as_str),
            );
            if edge_type.is_empty() {
                return None;
            }
            Some(PalaceMaterializationApprovedEdge {
                pair_id: link
                    .get("pair_id")
                    .and_then(Value::as_str)
                    .map(str::to_string)
                    .unwrap_or_else(|| format!("{from_key} -[{edge_type}]-> {to_key}")),
                from_key: from_key.to_string(),
                to_key: to_key.to_string(),
                edge_type,
            })
        })
        .collect()
}

fn palace_materialization_approved_edge_apply_gate_for_plan(
    plan: &Value,
    dry_run: bool,
    confirm: Option<&str>,
) -> Value {
    let links = palace_materialization_approved_edges_from_plan(plan);
    let approved_pair_count = plan
        .get("approved_pair_count")
        .and_then(Value::as_u64)
        .unwrap_or(links.len() as u64);
    let already_materialized_edge_count = plan
        .get("already_materialized_edge_count")
        .and_then(Value::as_u64)
        .unwrap_or(0);
    let confirmation_required = !dry_run && !links.is_empty();
    let confirmation_matches = confirm
        .map(str::trim)
        .is_some_and(|value| value == PALACE_MATERIALIZATION_APPROVED_EDGE_APPLY_CONFIRM);
    let mut blocking_reasons = Vec::new();
    if confirmation_required && !confirmation_matches {
        blocking_reasons.push("confirmation_required");
    }
    json!({
        "schema": "agent_bridge.palace.materialization_approved_edge_apply.v0",
        "dry_run": dry_run,
        "blocked": !blocking_reasons.is_empty(),
        "status": if blocking_reasons.is_empty() { "ready" } else { "blocked" },
        "confirm_phrase": PALACE_MATERIALIZATION_APPROVED_EDGE_APPLY_CONFIRM,
        "confirmation_required": confirmation_required,
        "confirmation_matches": confirmation_matches,
        "approved_pair_count": approved_pair_count,
        "would_write_edges": links.len(),
        "already_materialized_edge_count": already_materialized_edge_count,
        "pending_materialization_edge_count": links.len(),
        "writes_memory": false,
        "writes_edges": false,
        "changes_search_order": false,
        "can_change_retrieval_order": false,
        "approval_writes_allowed": false,
        "can_materialize_edges": false,
        "auto_apply_allowed": false,
        "blocking_reasons": blocking_reasons,
    })
}

async fn palace_materialization_approved_edge_apply_edges(
    store: &dyn StateStore,
    links: Vec<PalaceMaterializationApprovedEdge>,
    dry_run: bool,
) -> PalaceOrphanApprovedLinkApplyOutcome {
    let mut outcome = PalaceOrphanApprovedLinkApplyOutcome::default();
    for link in links {
        if link.edge_type != "relates" {
            outcome.skipped_count += 1;
            outcome.results.push(json!({
                "pair_id": link.pair_id,
                "from_key": link.from_key,
                "to_key": link.to_key,
                "edge_type": link.edge_type,
                "status": "skipped_unsupported_edge_type",
            }));
            continue;
        }
        if link.from_key == link.to_key {
            outcome.skipped_count += 1;
            outcome.results.push(json!({
                "pair_id": link.pair_id,
                "from_key": link.from_key,
                "to_key": link.to_key,
                "edge_type": link.edge_type,
                "status": "skipped_self_edge",
            }));
            continue;
        }
        if dry_run {
            outcome.results.push(json!({
                "pair_id": link.pair_id,
                "from_key": link.from_key,
                "to_key": link.to_key,
                "edge_type": link.edge_type,
                "status": "would_write",
            }));
            continue;
        }
        match store
            .memory_link(&link.from_key, &link.to_key, &link.edge_type, 1.0)
            .await
        {
            Ok(()) => {
                outcome.applied_count += 1;
                outcome.results.push(json!({
                    "pair_id": link.pair_id,
                    "from_key": link.from_key,
                    "to_key": link.to_key,
                    "edge_type": link.edge_type,
                    "status": "applied",
                }));
            }
            Err(e) => {
                outcome.failed_count += 1;
                outcome.results.push(json!({
                    "pair_id": link.pair_id,
                    "from_key": link.from_key,
                    "to_key": link.to_key,
                    "edge_type": link.edge_type,
                    "status": "failed",
                    "error": e.to_string(),
                }));
            }
        }
    }
    outcome
}

fn palace_review_artifact_for_sources(
    region: Option<&str>,
    threshold: f64,
    min_content_len: usize,
    max_orphans: usize,
    candidate_limit: usize,
    candidate_review: &Value,
    approved_plan: &Value,
    apply_records: &[Value],
    verification_rows: &[Value],
) -> Value {
    let safe_batch = approved_plan.get("safe_batch").cloned().unwrap_or_else(|| {
        json!({
            "schema": "agent_bridge.palace.orphan_safe_batch.v0",
            "read_only": true,
            "writes_memory": false,
            "writes_edges": false,
            "auto_apply_allowed": false,
            "eligible_count": 0,
            "blocked_count": 0,
            "links": [],
            "blocked": [],
        })
    });
    let mut recent_apply_records = apply_records.to_vec();
    recent_apply_records.sort_by(|a, b| {
        palace_json_u64_at(b, &["generated_at_unix"])
            .cmp(&palace_json_u64_at(a, &["generated_at_unix"]))
    });

    let verification_rows = verification_rows.to_vec();
    json!({
        "schema": "agent_bridge.palace.review_artifact.v0",
        "artifact_kind": "palace_review_packet",
        "read_only": true,
        "writes_memory": false,
        "writes_edges": false,
        "auto_apply_allowed": false,
        "region": region,
        "threshold": threshold,
        "min_content_len": min_content_len,
        "max_orphans": max_orphans,
        "candidate_limit": candidate_limit,
        "summary": {
            "candidate_count": palace_json_u64_at(candidate_review, &["review", "candidate_count"]),
            "pending_candidate_count": palace_json_u64_at(candidate_review, &["review", "pending_count"]),
            "approved_candidate_count": palace_json_u64_at(candidate_review, &["review", "approved_count"]),
            "rejected_candidate_count": palace_json_u64_at(candidate_review, &["review", "rejected_count"]),
            "deferred_candidate_count": palace_json_u64_at(candidate_review, &["review", "deferred_count"]),
            "approved_pair_count": palace_json_u64_at(approved_plan, &["approved_pair_count"]),
            "safe_batch_eligible_count": palace_json_u64_at(&safe_batch, &["eligible_count"]),
            "safe_batch_blocked_count": palace_json_u64_at(&safe_batch, &["blocked_count"]),
            "recent_apply_audit_count": recent_apply_records.len(),
            "verified_edge_count": verification_rows.len(),
        },
        "sections": {
            "candidate_review": candidate_review,
            "approved_plan": approved_plan,
            "safe_batch": safe_batch,
            "apply_audit": {
                "schema": "agent_bridge.palace.apply_audit_summary.v0",
                "read_only": true,
                "writes_memory": false,
                "writes_edges": false,
                "auto_apply_allowed": false,
                "recent_count": recent_apply_records.len(),
                "records": recent_apply_records,
            },
            "verification_evidence": {
                "schema": "agent_bridge.palace.verification_evidence.v0",
                "read_only": true,
                "writes_memory": false,
                "writes_edges": false,
                "auto_apply_allowed": false,
                "edge_count": verification_rows.len(),
                "rows": verification_rows,
            },
        },
        "next_step": "Review the artifact evidence before publishing or invoking write-capable memory edge behavior.",
    })
}

fn palace_materialization_review_artifact_from_packet(
    packet: &Value,
    path: &FsPath,
    decisions_path: &FsPath,
    decisions: &[Value],
) -> Value {
    let decision_inbox = palace_materialization_review_decision_inbox_for_packet(packet, decisions);
    let approved_plan = palace_materialization_approved_edge_plan_for_inbox(&decision_inbox);
    let mut summary = packet.get("summary").cloned().unwrap_or_else(|| json!({}));
    if !summary.is_object() {
        summary = json!({});
    }
    if let Some(summary_obj) = summary.as_object_mut() {
        summary_obj.insert(
            "materialization_candidate_count".to_string(),
            decision_inbox
                .get("candidate_count")
                .cloned()
                .unwrap_or(Value::Null),
        );
        summary_obj.insert(
            "materialization_pending_count".to_string(),
            decision_inbox
                .get("pending_count")
                .cloned()
                .unwrap_or(Value::Null),
        );
        summary_obj.insert(
            "materialization_approved_count".to_string(),
            decision_inbox
                .get("approved_count")
                .cloned()
                .unwrap_or(Value::Null),
        );
        summary_obj.insert(
            "materialization_rejected_count".to_string(),
            decision_inbox
                .get("rejected_count")
                .cloned()
                .unwrap_or(Value::Null),
        );
        summary_obj.insert(
            "materialization_deferred_count".to_string(),
            decision_inbox
                .get("deferred_count")
                .cloned()
                .unwrap_or(Value::Null),
        );
        summary_obj.insert(
            "materialization_approved_pair_count".to_string(),
            approved_plan
                .get("approved_pair_count")
                .cloned()
                .unwrap_or(Value::Null),
        );
    }
    let candidates: Vec<Value> = decision_inbox
        .get("candidates")
        .and_then(Value::as_array)
        .into_iter()
        .flatten()
        .filter_map(|candidate| candidate.get("candidate").cloned())
        .collect();
    json!({
        "schema": "agent_bridge.palace.materialization_review_artifact.v0",
        "artifact_kind": "materialization_review_packet",
        "read_only": true,
        "writes_memory": false,
        "writes_edges": false,
        "changes_search_order": false,
        "can_change_retrieval_order": false,
        "approval_writes_allowed": false,
        "can_materialize_edges": false,
        "review_state": packet.get("review_state").cloned().unwrap_or(Value::Null),
        "approval_state": packet.get("approval_state").cloned().unwrap_or(Value::Null),
        "default_decision": packet.get("default_decision").cloned().unwrap_or(Value::Null),
        "source": {
            "packet_path": path.display().to_string(),
            "decisions_path": decisions_path.display().to_string(),
            "packet_schema": packet.get("schema").cloned().unwrap_or(Value::Null),
            "generator": packet.pointer("/packet_source/generator").cloned().unwrap_or(Value::Null),
            "fixture_path": packet.pointer("/packet_source/fixture_path").cloned().unwrap_or(Value::Null),
            "fixture_schema": packet.pointer("/packet_source/fixture_schema").cloned().unwrap_or(Value::Null),
        },
        "summary": summary,
        "questions": packet.get("review_questions").cloned().unwrap_or_else(|| json!([])),
        "candidates": candidates,
        "sections": {
            "input_contract": packet.get("input_contract").cloned().unwrap_or_else(|| json!({})),
            "packet_source": packet.get("packet_source").cloned().unwrap_or_else(|| json!({})),
            "decision_inbox": decision_inbox,
            "approved_plan": approved_plan,
        },
        "next_step": "Record human decisions here, then inspect the dry-run approved plan before designing any separate write-capable materializer."
    })
}

fn palace_slug(raw: &str) -> String {
    let mut out = String::new();
    let mut pending_dash = false;
    for c in raw.trim().chars().flat_map(char::to_lowercase) {
        if c.is_ascii_alphanumeric() {
            if pending_dash && !out.is_empty() && out.len() < 48 {
                out.push('-');
            }
            pending_dash = false;
            if out.len() < 48 {
                out.push(c);
            }
        } else if !out.is_empty() {
            pending_dash = true;
        }
        if out.len() >= 48 {
            break;
        }
    }
    while out.ends_with('-') {
        out.pop();
    }
    out
}

fn palace_tag_is_useful_for_atlas(tag: &str) -> bool {
    const STOPWORDS: &[&str] = &[
        "palace",
        "auto_curated",
        "implicit",
        "session-handoff",
        "session_handoff",
        "handoff",
        "superseded",
        "verified",
        "deployed",
        "shipped",
    ];
    let slug = palace_slug(tag);
    if slug.len() < 3 {
        return false;
    }
    if STOPWORDS.iter().any(|word| *word == slug) {
        return false;
    }
    if slug.starts_with("summarized-at") || slug.starts_with("ttl-") {
        return false;
    }
    if slug.len() >= 4 && slug.as_bytes()[0..2] == *b"20" {
        return false;
    }
    true
}

fn palace_region_for_memory(mem: &MemoryRecord) -> String {
    if let Some(tag) = mem
        .tags
        .iter()
        .find(|tag| palace_tag_is_useful_for_atlas(tag))
    {
        return palace_slug(tag);
    }

    let key = mem.key.to_ascii_lowercase();
    let kind = mem.kind.to_ascii_lowercase();
    if kind == "session_handoff" || key.contains("handoff") {
        return "session-handoffs".to_string();
    }

    const PATTERNS: &[(&str, &str)] = &[
        ("biocortex", "biocortex"),
        ("onsen", "onsen-hd"),
        ("agent-bridge", "agent-bridge"),
        ("output-lane", "output-lane"),
        ("present", "present"),
        ("voice", "voice"),
        ("memory", "memory"),
        ("palace", "palace"),
        ("xiao", "xiao-shu"),
        ("warp", "warp"),
        ("desktop", "desktop"),
        ("nexus", "nexus"),
        ("skill", "skills"),
    ];
    if let Some((_, region)) = PATTERNS
        .iter()
        .find(|(needle, _)| key.contains(*needle) || kind.contains(*needle))
    {
        return (*region).to_string();
    }
    let fallback = palace_slug(if kind.is_empty() {
        "uncategorized"
    } else {
        &kind
    });
    if fallback.is_empty() {
        "uncategorized".to_string()
    } else {
        fallback
    }
}

fn palace_memory_active(mem: &MemoryRecord) -> bool {
    mem.status == "active" || mem.status.is_empty()
}

fn palace_memory_has_any_tag(mem: &MemoryRecord, tags: &[&str]) -> bool {
    mem.tags.iter().any(|tag| {
        tags.iter()
            .any(|skip| tag.eq_ignore_ascii_case(skip) || palace_slug(tag) == palace_slug(skip))
    })
}

fn palace_memory_kind_is_any(mem: &MemoryRecord, kinds: &[&str]) -> bool {
    kinds.iter().any(|kind| mem.kind.eq_ignore_ascii_case(kind))
}

fn palace_memory_excluded_kind(mem: &MemoryRecord) -> bool {
    ab_store::COVERAGE_EXCLUDED_KINDS
        .iter()
        .any(|kind| mem.kind.eq_ignore_ascii_case(kind))
        || palace_memory_kind_is_any(mem, PALACE_ORPHAN_SKIP_KINDS)
}

fn palace_memory_scope_value(mem: &MemoryRecord) -> Option<&str> {
    mem.scope
        .as_deref()
        .map(str::trim)
        .filter(|scope| !scope.is_empty())
}

fn palace_memory_scopes_compatible(source: &MemoryRecord, target: &MemoryRecord) -> bool {
    match (
        palace_memory_scope_value(source),
        palace_memory_scope_value(target),
    ) {
        (Some(a), Some(b)) => a == b || a == "global" || b == "global",
        _ => true,
    }
}

fn palace_pair_scope_relation(source: &MemoryRecord, target: &MemoryRecord) -> &'static str {
    match (
        palace_memory_scope_value(source),
        palace_memory_scope_value(target),
    ) {
        (Some(a), Some(b)) if a == b => "same_scope",
        (Some("global"), _) | (_, Some("global")) | (None, _) | (_, None) => "global_or_unscoped",
        _ => "cross_scope",
    }
}

fn palace_key_prefix(key: &str) -> &str {
    key.split(&['_', '-', '/', '.'][..]).next().unwrap_or("")
}

fn palace_content_tokens(content: &str) -> HashSet<String> {
    content
        .split_whitespace()
        .filter(|token| token.len() >= 4)
        .map(|token| token.to_ascii_lowercase())
        .collect()
}

fn palace_content_preview(content: &str, max_chars: usize) -> String {
    let total = content.chars().count();
    let mut preview: String = content.chars().take(max_chars).collect();
    preview = preview.replace(['\n', '\r'], " ");
    if total > max_chars {
        preview.push_str("...");
    }
    preview
}

fn palace_store_neighbor_summary_value(key: &str, edges: &[ab_store::MemoryEdge]) -> Value {
    let structural = edges
        .iter()
        .filter(|edge| edge.edge_type != "coactivation")
        .count();
    let coactivation = edges
        .iter()
        .filter(|edge| edge.edge_type == "coactivation")
        .count();
    let rows: Vec<Value> = edges
        .iter()
        .take(12)
        .map(|edge| {
            let (peer_key, direction) = if edge.from_key == key {
                (edge.to_key.as_str(), "out")
            } else if edge.to_key == key {
                (edge.from_key.as_str(), "in")
            } else {
                (edge.to_key.as_str(), "external")
            };
            json!({
                "peer_key": peer_key,
                "edge_type": edge.edge_type,
                "weight": (edge.weight * 1000.0).round() / 1000.0,
                "direction": direction,
            })
        })
        .collect();
    json!({
        "read_only": true,
        "total": edges.len(),
        "structural": structural,
        "coactivation": coactivation,
        "rows": rows,
        "truncated": edges.len() > 12,
    })
}

fn palace_candidate_allowed(source: &MemoryRecord, target: &MemoryRecord) -> bool {
    source.key != target.key
        && palace_memory_active(target)
        && !palace_memory_excluded_kind(target)
        && !palace_memory_has_any_tag(target, PALACE_ORPHAN_SKIP_TAGS)
        && palace_memory_scopes_compatible(source, target)
}

fn compute_palace_link_suggestions(
    source: &MemoryRecord,
    candidates: &[MemoryRecord],
    already_linked: &HashSet<String>,
    limit: usize,
) -> Vec<PalaceLinkSuggestion> {
    let source_prefix = palace_key_prefix(&source.key);
    let source_tokens = palace_content_tokens(&source.content);
    let mut scored: Vec<PalaceLinkSuggestion> = candidates
        .iter()
        .filter(|mem| mem.key != source.key && !already_linked.contains(&mem.key))
        .filter_map(|mem| {
            let mut score = 0.0f64;
            let mut reasons: Vec<&str> = Vec::new();
            let tag_overlap = source
                .tags
                .iter()
                .filter(|tag| mem.tags.contains(*tag))
                .count();
            if tag_overlap > 0 {
                score += 0.4 * tag_overlap as f64;
                reasons.push("tag_overlap");
            }
            let target_prefix = palace_key_prefix(&mem.key);
            if !source_prefix.is_empty() && source_prefix == target_prefix {
                score += 0.3;
                reasons.push("same_prefix");
            }
            let target_tokens = palace_content_tokens(&mem.content);
            let intersection = source_tokens
                .iter()
                .filter(|token| target_tokens.contains(*token))
                .count();
            let union = source_tokens.len() + target_tokens.len() - intersection;
            if union > 0 && intersection > 2 {
                let jaccard = intersection as f64 / union as f64;
                score += jaccard;
                reasons.push("content_overlap");
            }
            if score < 0.1 {
                return None;
            }
            let confidence = (score * 100.0).min(100.0).round() / 100.0;
            Some(PalaceLinkSuggestion {
                key: mem.key.clone(),
                kind: mem.kind.clone(),
                confidence,
                reason: reasons.join("+"),
                scope: mem.scope.clone(),
                scope_relation: palace_pair_scope_relation(source, mem),
                preview: palace_content_preview(&mem.content, 120),
            })
        })
        .collect();
    scored.sort_by(|a, b| {
        b.confidence
            .partial_cmp(&a.confidence)
            .unwrap_or(std::cmp::Ordering::Equal)
            .then_with(|| a.key.cmp(&b.key))
    });
    scored.truncate(limit);
    scored
}

#[allow(clippy::too_many_arguments)]
fn preview_palace_orphan_candidates(
    all: &[MemoryRecord],
    keys_with_edges: &HashSet<String>,
    region: Option<&str>,
    threshold: f64,
    min_content_len: usize,
    max_orphans: usize,
    candidate_limit: usize,
) -> PalaceOrphanCandidatePreview {
    let region = region.map(palace_slug).filter(|slug| !slug.is_empty());
    let mut preview = PalaceOrphanCandidatePreview::default();
    let mut orphans: Vec<MemoryRecord> = Vec::new();

    for mem in all {
        if !palace_memory_active(mem) || palace_memory_excluded_kind(mem) {
            continue;
        }
        if mem.content.len() < min_content_len {
            continue;
        }
        if let Some(region) = region.as_deref() {
            if palace_region_for_memory(mem) != region {
                continue;
            }
        }
        preview.examined += 1;
        if keys_with_edges.contains(&mem.key) {
            preview.skipped_existing_edges += 1;
            continue;
        }
        if palace_memory_has_any_tag(mem, PALACE_ORPHAN_SKIP_TAGS) {
            preview.skipped_blacklisted_orphan += 1;
            continue;
        }
        if palace_memory_kind_is_any(mem, PALACE_ORPHAN_SKIP_KINDS) {
            preview.skipped_blacklisted_kind += 1;
            continue;
        }
        orphans.push(mem.clone());
        if orphans.len() >= max_orphans {
            break;
        }
    }

    preview.eligible_orphans = orphans.len() as u64;
    for orphan in &orphans {
        let already_linked = HashSet::new();
        let candidate_pool: Vec<MemoryRecord> = all
            .iter()
            .filter(|candidate| palace_candidate_allowed(orphan, candidate))
            .cloned()
            .collect();
        let suggestions = compute_palace_link_suggestions(
            orphan,
            &candidate_pool,
            &already_linked,
            candidate_limit,
        );
        match suggestions.first() {
            Some(top) if top.confidence >= threshold => preview.would_link += 1,
            Some(_) => preview.skipped_low_score += 1,
            None => preview.skipped_no_candidates += 1,
        }
        preview.rows.push(PalaceOrphanCandidatePreviewRow {
            orphan: orphan.clone(),
            suggestions,
        });
    }

    preview
}

fn palace_orphan_row_status(row: &PalaceOrphanCandidatePreviewRow, threshold: f64) -> &'static str {
    match row.suggestions.first() {
        Some(top) if top.confidence >= threshold => "would_link",
        Some(_) => "low_score",
        None => "no_candidates",
    }
}

// ── Markdown source ──────────────────────────────────────────────────────

#[derive(Debug, Clone)]
struct MarkdownMemory {
    /// Filename without `.md` — used as graph node id.
    key: String,
    /// `type` field from frontmatter (project / feedback / vision / etc.).
    /// Falls back to `"markdown"` if no frontmatter or no `type`.
    kind: String,
    /// `description` field from frontmatter (one-line summary).
    description: String,
    /// Full body content after the frontmatter block.
    content: String,
    /// `(other.md)` references found in the body (sans `.md`).
    links_to: Vec<String>,
}

/// Walk a directory of `*.md` files, parse each as a markdown memory.
/// Skips `MEMORY.md` (the index) and any non-`.md` files.
fn read_markdown_dir(dir: &PathBuf) -> Vec<MarkdownMemory> {
    let entries = match fs::read_dir(dir) {
        Ok(e) => e,
        Err(e) => {
            tracing::warn!(?dir, error = %e, "markdown memory dir unreadable");
            return Vec::new();
        }
    };

    let mut out = Vec::new();
    for entry in entries.flatten() {
        let path = entry.path();
        if path.extension().and_then(|s| s.to_str()) != Some("md") {
            continue;
        }
        let Some(stem) = path.file_stem().and_then(|s| s.to_str()) else {
            continue;
        };
        if stem == "MEMORY" {
            continue;
        }
        let body = match fs::read_to_string(&path) {
            Ok(s) => s,
            Err(_) => continue,
        };
        out.push(parse_markdown_memory(stem.to_string(), &body));
    }
    out
}

fn parse_markdown_memory(key: String, body: &str) -> MarkdownMemory {
    let (fm_text, content) = split_frontmatter(body);

    let mut description = String::new();
    let mut kind = String::from("markdown");

    if let Some(fm) = fm_text {
        for line in fm.lines() {
            if let Some((k, v)) = line.split_once(':') {
                let k = k.trim();
                let v = v.trim().trim_matches(|c| c == '"' || c == '\'');
                match k {
                    "description" => description = v.to_string(),
                    "type" => kind = v.to_string(),
                    _ => {}
                }
            }
        }
    }

    let links_to = extract_links(content);

    MarkdownMemory {
        key,
        kind,
        description,
        content: content.to_string(),
        links_to,
    }
}

/// Split body into `(frontmatter, content)`. Frontmatter is the YAML-ish
/// block delimited by leading `---\n` and the next `---\n`. Returns
/// `(None, body)` if no frontmatter is present.
fn split_frontmatter(body: &str) -> (Option<&str>, &str) {
    let Some(rest) = body.strip_prefix("---\n") else {
        return (None, body);
    };
    let Some(idx) = rest.find("\n---\n") else {
        return (None, body);
    };
    let fm = &rest[..idx];
    let content = &rest[idx + 5..];
    (Some(fm), content)
}

/// Extract `*.md` references — both strict `(filename.md)` markdown-link
/// form and bare `filename.md` prose mentions. Filenames must be all
/// lowercase ASCII alphanumeric plus `_` `-`. Dangling refs (target file
/// doesn't exist in our memory set) are filtered out by the caller.
fn extract_links(content: &str) -> Vec<String> {
    let mut out = Vec::new();

    // Tokenize on any char that isn't a valid filename char. This catches
    // both `(name.md)` (parens are separators) and bare `name.md` in prose.
    for token in
        content.split(|c: char| !c.is_ascii_alphanumeric() && c != '_' && c != '-' && c != '.')
    {
        let Some(stem) = token.strip_suffix(".md") else {
            continue;
        };
        if is_valid_memory_filename(stem) {
            out.push(stem.to_string());
        }
    }

    out.sort();
    out.dedup();
    out
}

fn is_valid_memory_filename(s: &str) -> bool {
    if s.is_empty() {
        return false;
    }
    // Must start with a letter (avoids `42.md` numeric noise).
    if !s.chars().next().is_some_and(|c| c.is_ascii_lowercase()) {
        return false;
    }
    s.chars()
        .all(|c| c.is_ascii_alphanumeric() || c == '_' || c == '-')
}

// ── Graph endpoint ───────────────────────────────────────────────────────

/// Build the graph: active sqlite memories + markdown memories +
/// edges from both sources. Cross-source edges are not inferred.
async fn api_graph(
    State(s): State<AppState>,
    Query(q): Query<GraphQuery>,
) -> Result<Json<Value>, (StatusCode, String)> {
    build_graph_snapshot(&s, q.all).await.map(Json)
}

struct PalaceOrphanCandidateResult {
    region: Option<String>,
    threshold: f64,
    min_content_len: usize,
    max_orphans: usize,
    candidate_limit: usize,
    preview: PalaceOrphanCandidatePreview,
    decisions: Vec<Value>,
    result: Value,
}

async fn palace_orphan_candidate_result_for_query(
    s: &AppState,
    q: &OrphanCandidatesQuery,
) -> Result<PalaceOrphanCandidateResult, (StatusCode, String)> {
    let threshold = q.threshold.unwrap_or(0.85).clamp(0.0, 2.0);
    let min_content_len = q.min_content_len.unwrap_or(50).min(1000) as usize;
    let max_orphans = q.max_orphans.unwrap_or(12).clamp(1, 100) as usize;
    let candidate_limit = q.candidate_limit.unwrap_or(3).clamp(1, 10) as usize;
    let region = q
        .region
        .as_deref()
        .map(str::trim)
        .filter(|region| !region.is_empty())
        .map(str::to_string);
    let region_ref = region.as_deref();

    let all = s
        .store
        .list_memories(None, MemoryListSort::Recent, STORE_FETCH_LIMIT)
        .await
        .map_err(|e| {
            (
                StatusCode::INTERNAL_SERVER_ERROR,
                format!("list_memories: {e}"),
            )
        })?;

    let mut keys_with_edges: HashSet<String> = HashSet::new();
    for mem in &all {
        if !palace_memory_active(mem) || palace_memory_excluded_kind(mem) {
            continue;
        }
        if let Ok(edges) = s.store.memory_neighbors(&mem.key).await {
            if !edges.is_empty() {
                keys_with_edges.insert(mem.key.clone());
            }
        }
    }

    let preview = preview_palace_orphan_candidates(
        &all,
        &keys_with_edges,
        region_ref,
        threshold,
        min_content_len,
        max_orphans,
        candidate_limit,
    );
    let decisions_path = default_palace_orphan_candidate_decisions_path();
    let decisions = load_palace_orphan_candidate_decisions(&decisions_path).map_err(|e| {
        (
            StatusCode::INTERNAL_SERVER_ERROR,
            format!("load orphan candidate review decisions: {e}"),
        )
    })?;
    let review_inbox = palace_orphan_candidate_decision_inbox_for_pairs(
        &palace_orphan_candidate_pairs_for_preview(&preview),
        &decisions,
    );
    let review_by_pair = palace_orphan_review_by_pair(&review_inbox);

    let rows: Vec<Value> = preview
        .rows
        .iter()
        .map(|row| {
            let candidates: Vec<Value> = row
                .suggestions
                .iter()
                .map(|candidate| {
                    let pair = PalaceOrphanCandidatePair {
                        orphan_key: row.orphan.key.clone(),
                        candidate_key: candidate.key.clone(),
                    };
                    let review = review_by_pair
                        .get(&(pair.orphan_key.clone(), pair.candidate_key.clone()))
                        .cloned()
                        .unwrap_or_else(|| {
                            json!({
                                "pair_id": palace_orphan_pair_id(&pair),
                                "orphan_key": &pair.orphan_key,
                                "candidate_key": &pair.candidate_key,
                                "decision": "pending",
                                "latest_decision_at_unix": Value::Null,
                                "reviewer": Value::Null,
                                "note": Value::Null,
                            })
                        });
                    json!({
                        "key": &candidate.key,
                        "kind": &candidate.kind,
                        "confidence": candidate.confidence,
                        "reason": &candidate.reason,
                        "scope": candidate.scope.as_deref(),
                        "scope_relation": candidate.scope_relation,
                        "preview": &candidate.preview,
                        "review": review,
                    })
                })
                .collect();
            json!({
                "orphan": &row.orphan.key,
                "kind": &row.orphan.kind,
                "region": palace_region_for_memory(&row.orphan),
                "scope": row.orphan.scope.as_deref(),
                "top_confidence": row.suggestions.first().map(|candidate| candidate.confidence),
                "status": palace_orphan_row_status(row, threshold),
                "preview": palace_content_preview(&row.orphan.content, 120),
                "candidates": candidates,
            })
        })
        .collect();

    let result = json!({
        "schema": "agent_bridge.palace.orphan_candidates.v0",
        "read_only": true,
        "region": region_ref,
        "threshold": threshold,
        "min_content_len": min_content_len,
        "max_orphans": max_orphans,
        "candidate_limit": candidate_limit,
        "skip_tags": PALACE_ORPHAN_SKIP_TAGS,
        "skip_kinds": PALACE_ORPHAN_SKIP_KINDS,
        "loaded_records": all.len(),
        "examined": preview.examined,
        "eligible_orphans": preview.eligible_orphans,
        "would_link": preview.would_link,
        "skipped_low_score": preview.skipped_low_score,
        "skipped_no_candidates": preview.skipped_no_candidates,
        "skipped_existing_edges": preview.skipped_existing_edges,
        "skipped_blacklisted_orphan": preview.skipped_blacklisted_orphan,
        "skipped_blacklisted_kind": preview.skipped_blacklisted_kind,
        "review": {
            "read_only": true,
            "decisions_path": decisions_path.display().to_string(),
            "candidate_count": review_inbox.get("candidate_count").cloned().unwrap_or(Value::Null),
            "pending_count": review_inbox.get("pending_count").cloned().unwrap_or(Value::Null),
            "approved_count": review_inbox.get("approved_count").cloned().unwrap_or(Value::Null),
            "rejected_count": review_inbox.get("rejected_count").cloned().unwrap_or(Value::Null),
            "deferred_count": review_inbox.get("deferred_count").cloned().unwrap_or(Value::Null),
            "writes_memory": false,
            "writes_edges": false,
            "auto_apply_allowed": false,
        },
        "rows": rows,
        "next_step": "Inspect candidate quality before any write-capable hygiene run.",
    });

    Ok(PalaceOrphanCandidateResult {
        region,
        threshold,
        min_content_len,
        max_orphans,
        candidate_limit,
        preview,
        decisions,
        result,
    })
}

fn palace_orphan_approved_links_from_apply_records(
    records: &[Value],
) -> Vec<PalaceOrphanApprovedLink> {
    records
        .iter()
        .filter(|record| record.get("dry_run").and_then(Value::as_bool) == Some(false))
        .flat_map(|record| {
            record
                .get("results")
                .and_then(Value::as_array)
                .into_iter()
                .flatten()
                .filter(|result| result.get("status").and_then(Value::as_str) == Some("applied"))
                .filter_map(|result| {
                    let orphan_key = result.get("orphan_key").and_then(Value::as_str)?.trim();
                    let candidate_key = result.get("candidate_key").and_then(Value::as_str)?.trim();
                    if orphan_key.is_empty() || candidate_key.is_empty() {
                        return None;
                    }
                    let edge_type = result
                        .get("edge_type")
                        .and_then(Value::as_str)
                        .unwrap_or("relates")
                        .trim();
                    Some(PalaceOrphanApprovedLink {
                        pair_id: result
                            .get("pair_id")
                            .and_then(Value::as_str)
                            .map(str::to_string)
                            .unwrap_or_else(|| format!("{orphan_key} -> {candidate_key}")),
                        orphan_key: orphan_key.to_string(),
                        candidate_key: candidate_key.to_string(),
                        edge_type: if edge_type.is_empty() {
                            "relates".to_string()
                        } else {
                            edge_type.to_string()
                        },
                    })
                })
                .collect::<Vec<_>>()
        })
        .collect()
}

async fn palace_verified_edge_rows_for_links(
    store: &dyn StateStore,
    links: &[PalaceOrphanApprovedLink],
) -> Vec<Value> {
    let mut rows = Vec::new();
    let mut seen: HashSet<(String, String, String)> = HashSet::new();
    for link in links {
        if !seen.insert((
            link.orphan_key.clone(),
            link.candidate_key.clone(),
            link.edge_type.clone(),
        )) {
            continue;
        }
        let Ok(edges) = store.memory_neighbors(&link.orphan_key).await else {
            continue;
        };
        if let Some(edge) = edges.into_iter().find(|edge| {
            edge.from_key == link.orphan_key
                && edge.to_key == link.candidate_key
                && edge.edge_type == link.edge_type
        }) {
            rows.push(json!({
                "pair_id": link.pair_id,
                "from_key": edge.from_key,
                "to_key": edge.to_key,
                "edge_type": edge.edge_type,
                "weight": edge.weight,
                "verified": true,
            }));
        }
    }
    rows
}

async fn api_palace_review_artifact(
    State(s): State<AppState>,
    Query(q): Query<OrphanCandidatesQuery>,
) -> Result<Json<Value>, (StatusCode, String)> {
    let source = palace_orphan_candidate_result_for_query(&s, &q).await?;
    let mut approved_plan =
        palace_orphan_approved_link_plan_for_preview(&source.preview, &source.decisions);
    if let Some(obj) = approved_plan.as_object_mut() {
        obj.insert("region".to_string(), json!(source.region.as_deref()));
        obj.insert("threshold".to_string(), json!(source.threshold));
        obj.insert("min_content_len".to_string(), json!(source.min_content_len));
        obj.insert("max_orphans".to_string(), json!(source.max_orphans));
        obj.insert("candidate_limit".to_string(), json!(source.candidate_limit));
        obj.insert(
            "reviewed_candidate_count".to_string(),
            json!(palace_orphan_candidate_pairs_for_preview(&source.preview).len()),
        );
    }

    let apply_audit_path = default_palace_orphan_approved_link_apply_path();
    let apply_records =
        load_palace_orphan_approved_link_apply_records(&apply_audit_path).map_err(|e| {
            (
                StatusCode::INTERNAL_SERVER_ERROR,
                format!("load orphan approved link apply audit: {e}"),
            )
        })?;
    let mut verification_links = palace_orphan_approved_links_from_plan(&approved_plan);
    verification_links.extend(palace_orphan_approved_links_from_apply_records(
        &apply_records,
    ));
    let verification_rows =
        palace_verified_edge_rows_for_links(s.store.as_ref(), &verification_links).await;
    let mut artifact = palace_review_artifact_for_sources(
        source.region.as_deref(),
        source.threshold,
        source.min_content_len,
        source.max_orphans,
        source.candidate_limit,
        &source.result,
        &approved_plan,
        &apply_records,
        &verification_rows,
    );
    if let Some(apply_obj) = artifact
        .pointer_mut("/sections/apply_audit")
        .and_then(Value::as_object_mut)
    {
        apply_obj.insert(
            "path".to_string(),
            json!(apply_audit_path.display().to_string()),
        );
    }
    Ok(Json(artifact))
}

async fn api_materialization_review_artifact(
    State(_s): State<AppState>,
) -> Result<Json<Value>, (StatusCode, String)> {
    let packet_path = default_palace_materialization_review_packet_path();
    let packet = load_default_palace_materialization_review_packet(&packet_path)
        .map_err(|e| (StatusCode::INTERNAL_SERVER_ERROR, e))?;
    let decisions_path = default_palace_materialization_review_decisions_path();
    let decisions = load_palace_materialization_review_decisions(&decisions_path).map_err(|e| {
        (
            StatusCode::INTERNAL_SERVER_ERROR,
            format!("load materialization review decisions: {e}"),
        )
    })?;
    Ok(Json(palace_materialization_review_artifact_from_packet(
        &packet,
        &packet_path,
        &decisions_path,
        &decisions,
    )))
}

async fn api_materialization_review_approved_plan(
    State(s): State<AppState>,
) -> Result<Json<Value>, (StatusCode, String)> {
    let packet_path = default_palace_materialization_review_packet_path();
    let packet = load_default_palace_materialization_review_packet(&packet_path)
        .map_err(|e| (StatusCode::INTERNAL_SERVER_ERROR, e))?;
    let decisions_path = default_palace_materialization_review_decisions_path();
    let decisions = load_palace_materialization_review_decisions(&decisions_path).map_err(|e| {
        (
            StatusCode::INTERNAL_SERVER_ERROR,
            format!("load materialization review decisions: {e}"),
        )
    })?;
    let inbox = palace_materialization_review_decision_inbox_for_packet(&packet, &decisions);
    let mut plan = palace_materialization_approved_edge_plan_mark_existing_edges(
        s.store.as_ref(),
        palace_materialization_approved_edge_plan_for_inbox(&inbox),
    )
    .await
    .map_err(|e| {
        (
            StatusCode::INTERNAL_SERVER_ERROR,
            format!("mark existing materialization edges: {e}"),
        )
    })?;
    let apply_audit_path = default_palace_materialization_approved_edge_apply_path();
    let apply_records = load_palace_materialization_approved_edge_apply_records(&apply_audit_path)
        .map_err(|e| {
            (
                StatusCode::INTERNAL_SERVER_ERROR,
                format!("load materialization approved edge apply audit: {e}"),
            )
        })?;
    if let Some(obj) = plan.as_object_mut() {
        obj.insert(
            "packet_path".to_string(),
            json!(packet_path.display().to_string()),
        );
        obj.insert(
            "decisions_path".to_string(),
            json!(decisions_path.display().to_string()),
        );
        obj.insert(
            "reviewed_candidate_count".to_string(),
            inbox.get("candidate_count").cloned().unwrap_or(Value::Null),
        );
        obj.insert(
            "apply_audit_path".to_string(),
            json!(apply_audit_path.display().to_string()),
        );
        obj.insert("apply_audit_count".to_string(), json!(apply_records.len()));
        obj.insert(
            "recent_apply_audit".to_string(),
            json!(apply_records
                .iter()
                .rev()
                .take(5)
                .cloned()
                .collect::<Vec<_>>()),
        );
    }
    Ok(Json(plan))
}

async fn api_materialization_review_apply(
    State(s): State<AppState>,
    Json(req): Json<MaterializationApprovedEdgeApplyRequest>,
) -> Result<Json<Value>, (StatusCode, String)> {
    let dry_run = req.dry_run.unwrap_or(true);
    let packet_path = default_palace_materialization_review_packet_path();
    let packet = load_default_palace_materialization_review_packet(&packet_path)
        .map_err(|e| (StatusCode::INTERNAL_SERVER_ERROR, e))?;
    let decisions_path = default_palace_materialization_review_decisions_path();
    let decisions = load_palace_materialization_review_decisions(&decisions_path).map_err(|e| {
        (
            StatusCode::INTERNAL_SERVER_ERROR,
            format!("load materialization review decisions: {e}"),
        )
    })?;
    let inbox = palace_materialization_review_decision_inbox_for_packet(&packet, &decisions);
    let mut plan = palace_materialization_approved_edge_plan_mark_existing_edges(
        s.store.as_ref(),
        palace_materialization_approved_edge_plan_for_inbox(&inbox),
    )
    .await
    .map_err(|e| {
        (
            StatusCode::INTERNAL_SERVER_ERROR,
            format!("mark existing materialization edges: {e}"),
        )
    })?;
    if let Some(obj) = plan.as_object_mut() {
        obj.insert(
            "packet_path".to_string(),
            json!(packet_path.display().to_string()),
        );
        obj.insert(
            "decisions_path".to_string(),
            json!(decisions_path.display().to_string()),
        );
        obj.insert(
            "reviewed_candidate_count".to_string(),
            inbox.get("candidate_count").cloned().unwrap_or(Value::Null),
        );
    }

    let links = palace_materialization_approved_edges_from_plan(&plan);
    let mut response = palace_materialization_approved_edge_apply_gate_for_plan(
        &plan,
        dry_run,
        req.confirm.as_deref(),
    );
    let apply_audit_path = default_palace_materialization_approved_edge_apply_path();
    if let Some(obj) = response.as_object_mut() {
        obj.insert(
            "packet_path".to_string(),
            json!(packet_path.display().to_string()),
        );
        obj.insert(
            "decisions_path".to_string(),
            json!(decisions_path.display().to_string()),
        );
        obj.insert(
            "apply_audit_path".to_string(),
            json!(apply_audit_path.display().to_string()),
        );
        obj.insert(
            "actor".to_string(),
            req.actor
                .as_deref()
                .map(str::trim)
                .filter(|actor| !actor.is_empty())
                .map(|actor| json!(actor))
                .unwrap_or(Value::Null),
        );
    }

    let blocked = response
        .get("blocked")
        .and_then(Value::as_bool)
        .unwrap_or(true);
    if blocked {
        let generated_at_unix = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .map(|d| d.as_secs())
            .unwrap_or(0);
        let record = palace_materialization_approved_edge_apply_record_for_time(
            &response,
            req.actor.as_deref(),
            generated_at_unix,
        );
        append_palace_materialization_approved_edge_apply_record(&apply_audit_path, &record)
            .map_err(|e| {
                (
                    StatusCode::INTERNAL_SERVER_ERROR,
                    format!("append materialization approved edge apply audit: {e}"),
                )
            })?;
        return Ok(Json(response));
    }

    let outcome =
        palace_materialization_approved_edge_apply_edges(s.store.as_ref(), links, dry_run).await;

    if let Some(obj) = response.as_object_mut() {
        obj.insert(
            "status".to_string(),
            json!(if dry_run {
                "dry_run"
            } else if outcome.failed_count > 0 {
                "partial"
            } else if outcome.applied_count > 0 {
                "applied"
            } else {
                "noop"
            }),
        );
        obj.insert("applied_count".to_string(), json!(outcome.applied_count));
        obj.insert("failed_count".to_string(), json!(outcome.failed_count));
        obj.insert("skipped_count".to_string(), json!(outcome.skipped_count));
        obj.insert("results".to_string(), json!(outcome.results));
        obj.insert(
            "writes_edges".to_string(),
            json!(!dry_run && outcome.applied_count > 0),
        );
        obj.insert(
            "can_materialize_edges".to_string(),
            json!(!dry_run && outcome.applied_count > 0),
        );
        obj.insert("plan".to_string(), plan);
    }

    let generated_at_unix = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map(|d| d.as_secs())
        .unwrap_or(0);
    let record = palace_materialization_approved_edge_apply_record_for_time(
        &response,
        req.actor.as_deref(),
        generated_at_unix,
    );
    append_palace_materialization_approved_edge_apply_record(&apply_audit_path, &record).map_err(
        |e| {
            (
                StatusCode::INTERNAL_SERVER_ERROR,
                format!("append materialization approved edge apply audit: {e}"),
            )
        },
    )?;

    Ok(Json(response))
}

async fn api_materialization_review_decision(
    Json(req): Json<MaterializationReviewDecisionRequest>,
) -> Result<Json<Value>, (StatusCode, String)> {
    let pair = PalaceMaterializationReviewPair {
        from_key: req.from_key.trim().to_string(),
        to_key: req.to_key.trim().to_string(),
        edge_type: normalize_palace_materialization_edge_type(req.edge_type.as_deref()),
    };
    if pair.from_key.is_empty() || pair.to_key.is_empty() || pair.edge_type.is_empty() {
        return Err((
            StatusCode::BAD_REQUEST,
            "from_key, to_key, and edge_type are required".to_string(),
        ));
    }
    let generated_at_unix = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map(|d| d.as_secs())
        .unwrap_or(0);
    let record = palace_materialization_review_decision_record_for_time(
        &pair,
        req.decision.trim(),
        req.reviewer.as_deref(),
        req.note.as_deref(),
        generated_at_unix,
    )
    .map_err(|e| (StatusCode::BAD_REQUEST, e.to_string()))?;
    let decisions_path = default_palace_materialization_review_decisions_path();
    append_palace_materialization_review_decision(&decisions_path, &record).map_err(|e| {
        (
            StatusCode::INTERNAL_SERVER_ERROR,
            format!("append materialization review decision: {e}"),
        )
    })?;
    Ok(Json(json!({
        "schema": "agent_bridge.palace.materialization_review_decision_response.v0",
        "written": true,
        "decisions_path": decisions_path.display().to_string(),
        "writes_memory": false,
        "writes_edges": false,
        "changes_search_order": false,
        "can_change_retrieval_order": false,
        "approval_writes_allowed": false,
        "can_materialize_edges": false,
        "auto_apply_allowed": false,
        "record": record,
    })))
}

async fn api_orphan_candidates(
    State(s): State<AppState>,
    Query(q): Query<OrphanCandidatesQuery>,
) -> Result<Json<Value>, (StatusCode, String)> {
    let threshold = q.threshold.unwrap_or(0.85).clamp(0.0, 2.0);
    let min_content_len = q.min_content_len.unwrap_or(50).min(1000) as usize;
    let max_orphans = q.max_orphans.unwrap_or(12).clamp(1, 100) as usize;
    let candidate_limit = q.candidate_limit.unwrap_or(3).clamp(1, 10) as usize;
    let region = q
        .region
        .as_deref()
        .map(str::trim)
        .filter(|region| !region.is_empty());

    let all = s
        .store
        .list_memories(None, MemoryListSort::Recent, STORE_FETCH_LIMIT)
        .await
        .map_err(|e| {
            (
                StatusCode::INTERNAL_SERVER_ERROR,
                format!("list_memories: {e}"),
            )
        })?;

    let mut keys_with_edges: HashSet<String> = HashSet::new();
    for mem in &all {
        if !palace_memory_active(mem) || palace_memory_excluded_kind(mem) {
            continue;
        }
        if let Ok(edges) = s.store.memory_neighbors(&mem.key).await {
            if !edges.is_empty() {
                keys_with_edges.insert(mem.key.clone());
            }
        }
    }

    let preview = preview_palace_orphan_candidates(
        &all,
        &keys_with_edges,
        region,
        threshold,
        min_content_len,
        max_orphans,
        candidate_limit,
    );
    let decisions_path = default_palace_orphan_candidate_decisions_path();
    let decisions = load_palace_orphan_candidate_decisions(&decisions_path).map_err(|e| {
        (
            StatusCode::INTERNAL_SERVER_ERROR,
            format!("load orphan candidate review decisions: {e}"),
        )
    })?;
    let review_inbox = palace_orphan_candidate_decision_inbox_for_pairs(
        &palace_orphan_candidate_pairs_for_preview(&preview),
        &decisions,
    );
    let review_by_pair = palace_orphan_review_by_pair(&review_inbox);

    let rows: Vec<Value> = preview
        .rows
        .iter()
        .map(|row| {
            let candidates: Vec<Value> = row
                .suggestions
                .iter()
                .map(|candidate| {
                    let pair = PalaceOrphanCandidatePair {
                        orphan_key: row.orphan.key.clone(),
                        candidate_key: candidate.key.clone(),
                    };
                    let review = review_by_pair
                        .get(&(pair.orphan_key.clone(), pair.candidate_key.clone()))
                        .cloned()
                        .unwrap_or_else(|| {
                            json!({
                                "pair_id": palace_orphan_pair_id(&pair),
                                "orphan_key": &pair.orphan_key,
                                "candidate_key": &pair.candidate_key,
                                "decision": "pending",
                                "latest_decision_at_unix": Value::Null,
                                "reviewer": Value::Null,
                                "note": Value::Null,
                            })
                        });
                    json!({
                        "key": &candidate.key,
                        "kind": &candidate.kind,
                        "confidence": candidate.confidence,
                        "reason": &candidate.reason,
                        "scope": candidate.scope.as_deref(),
                        "scope_relation": candidate.scope_relation,
                        "preview": &candidate.preview,
                        "review": review,
                    })
                })
                .collect();
            json!({
                "orphan": &row.orphan.key,
                "kind": &row.orphan.kind,
                "region": palace_region_for_memory(&row.orphan),
                "scope": row.orphan.scope.as_deref(),
                "top_confidence": row.suggestions.first().map(|candidate| candidate.confidence),
                "status": palace_orphan_row_status(row, threshold),
                "preview": palace_content_preview(&row.orphan.content, 120),
                "candidates": candidates,
            })
        })
        .collect();

    Ok(Json(json!({
        "read_only": true,
        "region": region,
        "threshold": threshold,
        "min_content_len": min_content_len,
        "max_orphans": max_orphans,
        "candidate_limit": candidate_limit,
        "skip_tags": PALACE_ORPHAN_SKIP_TAGS,
        "skip_kinds": PALACE_ORPHAN_SKIP_KINDS,
        "loaded_records": all.len(),
        "examined": preview.examined,
        "eligible_orphans": preview.eligible_orphans,
        "would_link": preview.would_link,
        "skipped_low_score": preview.skipped_low_score,
        "skipped_no_candidates": preview.skipped_no_candidates,
        "skipped_existing_edges": preview.skipped_existing_edges,
        "skipped_blacklisted_orphan": preview.skipped_blacklisted_orphan,
        "skipped_blacklisted_kind": preview.skipped_blacklisted_kind,
        "review": {
            "read_only": true,
            "decisions_path": decisions_path.display().to_string(),
            "candidate_count": review_inbox.get("candidate_count").cloned().unwrap_or(Value::Null),
            "pending_count": review_inbox.get("pending_count").cloned().unwrap_or(Value::Null),
            "approved_count": review_inbox.get("approved_count").cloned().unwrap_or(Value::Null),
            "rejected_count": review_inbox.get("rejected_count").cloned().unwrap_or(Value::Null),
            "deferred_count": review_inbox.get("deferred_count").cloned().unwrap_or(Value::Null),
            "writes_memory": false,
            "writes_edges": false,
            "auto_apply_allowed": false,
        },
        "rows": rows,
        "next_step": "Inspect candidate quality before any write-capable hygiene run.",
    })))
}

async fn api_orphan_candidate_decision(
    Json(req): Json<OrphanCandidateDecisionRequest>,
) -> Result<Json<Value>, (StatusCode, String)> {
    let pair = PalaceOrphanCandidatePair {
        orphan_key: req.orphan_key.trim().to_string(),
        candidate_key: req.candidate_key.trim().to_string(),
    };
    if pair.orphan_key.is_empty() || pair.candidate_key.is_empty() {
        return Err((
            StatusCode::BAD_REQUEST,
            "orphan_key and candidate_key are required".to_string(),
        ));
    }
    let generated_at_unix = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map(|d| d.as_secs())
        .unwrap_or(0);
    let record = palace_orphan_candidate_decision_record_for_time(
        &pair,
        req.decision.trim(),
        req.reviewer.as_deref(),
        req.note.as_deref(),
        generated_at_unix,
    )
    .map_err(|e| (StatusCode::BAD_REQUEST, e.to_string()))?;
    let decisions_path = default_palace_orphan_candidate_decisions_path();
    append_palace_orphan_candidate_decision(&decisions_path, &record).map_err(|e| {
        (
            StatusCode::INTERNAL_SERVER_ERROR,
            format!("append orphan candidate review decision: {e}"),
        )
    })?;
    Ok(Json(json!({
        "schema": "agent_bridge.palace.orphan_candidate_decision_response.v0",
        "written": true,
        "decisions_path": decisions_path.display().to_string(),
        "writes_memory": false,
        "writes_edges": false,
        "auto_apply_allowed": false,
        "record": record,
    })))
}

async fn api_orphan_approved_link_plan(
    State(s): State<AppState>,
    Query(q): Query<OrphanCandidatesQuery>,
) -> Result<Json<Value>, (StatusCode, String)> {
    let threshold = q.threshold.unwrap_or(0.85).clamp(0.0, 2.0);
    let min_content_len = q.min_content_len.unwrap_or(50).min(1000) as usize;
    let max_orphans = q.max_orphans.unwrap_or(12).clamp(1, 100) as usize;
    let candidate_limit = q.candidate_limit.unwrap_or(3).clamp(1, 10) as usize;
    let region = q
        .region
        .as_deref()
        .map(str::trim)
        .filter(|region| !region.is_empty());

    let all = s
        .store
        .list_memories(None, MemoryListSort::Recent, STORE_FETCH_LIMIT)
        .await
        .map_err(|e| {
            (
                StatusCode::INTERNAL_SERVER_ERROR,
                format!("list_memories: {e}"),
            )
        })?;

    let mut keys_with_edges: HashSet<String> = HashSet::new();
    for mem in &all {
        if !palace_memory_active(mem) || palace_memory_excluded_kind(mem) {
            continue;
        }
        if let Ok(edges) = s.store.memory_neighbors(&mem.key).await {
            if !edges.is_empty() {
                keys_with_edges.insert(mem.key.clone());
            }
        }
    }

    let preview = preview_palace_orphan_candidates(
        &all,
        &keys_with_edges,
        region,
        threshold,
        min_content_len,
        max_orphans,
        candidate_limit,
    );
    let decisions_path = default_palace_orphan_candidate_decisions_path();
    let decisions = load_palace_orphan_candidate_decisions(&decisions_path).map_err(|e| {
        (
            StatusCode::INTERNAL_SERVER_ERROR,
            format!("load orphan candidate review decisions: {e}"),
        )
    })?;
    let mut plan = palace_orphan_approved_link_plan_for_preview(&preview, &decisions);
    if let Some(obj) = plan.as_object_mut() {
        obj.insert("region".to_string(), json!(region));
        obj.insert("threshold".to_string(), json!(threshold));
        obj.insert("min_content_len".to_string(), json!(min_content_len));
        obj.insert("max_orphans".to_string(), json!(max_orphans));
        obj.insert("candidate_limit".to_string(), json!(candidate_limit));
        obj.insert("loaded_records".to_string(), json!(all.len()));
        obj.insert(
            "reviewed_candidate_count".to_string(),
            json!(palace_orphan_candidate_pairs_for_preview(&preview).len()),
        );
        obj.insert(
            "decisions_path".to_string(),
            json!(decisions_path.display().to_string()),
        );
    }
    Ok(Json(plan))
}

async fn api_orphan_approved_link_apply(
    State(s): State<AppState>,
    Json(req): Json<OrphanApprovedLinkApplyRequest>,
) -> Result<Json<Value>, (StatusCode, String)> {
    let threshold = req.threshold.unwrap_or(0.85).clamp(0.0, 2.0);
    let min_content_len = req.min_content_len.unwrap_or(50).min(1000) as usize;
    let max_orphans = req.max_orphans.unwrap_or(12).clamp(1, 100) as usize;
    let candidate_limit = req.candidate_limit.unwrap_or(3).clamp(1, 10) as usize;
    let region = req
        .region
        .as_deref()
        .map(str::trim)
        .filter(|region| !region.is_empty());
    let dry_run = req.dry_run.unwrap_or(true);

    let all = s
        .store
        .list_memories(None, MemoryListSort::Recent, STORE_FETCH_LIMIT)
        .await
        .map_err(|e| {
            (
                StatusCode::INTERNAL_SERVER_ERROR,
                format!("list_memories: {e}"),
            )
        })?;

    let mut keys_with_edges: HashSet<String> = HashSet::new();
    for mem in &all {
        if !palace_memory_active(mem) || palace_memory_excluded_kind(mem) {
            continue;
        }
        if let Ok(edges) = s.store.memory_neighbors(&mem.key).await {
            if !edges.is_empty() {
                keys_with_edges.insert(mem.key.clone());
            }
        }
    }

    let preview = preview_palace_orphan_candidates(
        &all,
        &keys_with_edges,
        region,
        threshold,
        min_content_len,
        max_orphans,
        candidate_limit,
    );
    let decisions_path = default_palace_orphan_candidate_decisions_path();
    let decisions = load_palace_orphan_candidate_decisions(&decisions_path).map_err(|e| {
        (
            StatusCode::INTERNAL_SERVER_ERROR,
            format!("load orphan candidate review decisions: {e}"),
        )
    })?;
    let mut plan = palace_orphan_approved_link_plan_for_preview(&preview, &decisions);
    if let Some(obj) = plan.as_object_mut() {
        obj.insert("region".to_string(), json!(region));
        obj.insert("threshold".to_string(), json!(threshold));
        obj.insert("min_content_len".to_string(), json!(min_content_len));
        obj.insert("max_orphans".to_string(), json!(max_orphans));
        obj.insert("candidate_limit".to_string(), json!(candidate_limit));
        obj.insert("loaded_records".to_string(), json!(all.len()));
        obj.insert(
            "reviewed_candidate_count".to_string(),
            json!(palace_orphan_candidate_pairs_for_preview(&preview).len()),
        );
        obj.insert(
            "decisions_path".to_string(),
            json!(decisions_path.display().to_string()),
        );
    }

    let links = palace_orphan_approved_links_from_plan(&plan);
    let mut response =
        palace_orphan_approved_link_apply_gate_for_plan(&plan, dry_run, req.confirm.as_deref());
    let apply_audit_path = default_palace_orphan_approved_link_apply_path();
    if let Some(obj) = response.as_object_mut() {
        obj.insert("region".to_string(), json!(region));
        obj.insert("threshold".to_string(), json!(threshold));
        obj.insert("min_content_len".to_string(), json!(min_content_len));
        obj.insert("max_orphans".to_string(), json!(max_orphans));
        obj.insert("candidate_limit".to_string(), json!(candidate_limit));
        obj.insert(
            "decisions_path".to_string(),
            json!(decisions_path.display().to_string()),
        );
        obj.insert(
            "apply_audit_path".to_string(),
            json!(apply_audit_path.display().to_string()),
        );
        obj.insert(
            "actor".to_string(),
            req.actor
                .as_deref()
                .map(str::trim)
                .filter(|actor| !actor.is_empty())
                .map(|actor| json!(actor))
                .unwrap_or(Value::Null),
        );
    }

    let blocked = response
        .get("blocked")
        .and_then(|v| v.as_bool())
        .unwrap_or(true);
    if blocked {
        let generated_at_unix = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .map(|d| d.as_secs())
            .unwrap_or(0);
        let record = palace_orphan_approved_link_apply_record_for_time(
            &response,
            req.actor.as_deref(),
            generated_at_unix,
        );
        append_palace_orphan_approved_link_apply_record(&apply_audit_path, &record).map_err(
            |e| {
                (
                    StatusCode::INTERNAL_SERVER_ERROR,
                    format!("append orphan approved link apply audit: {e}"),
                )
            },
        )?;
        return Ok(Json(response));
    }

    let outcome = palace_orphan_approved_link_apply_links(s.store.as_ref(), links, dry_run).await;

    if let Some(obj) = response.as_object_mut() {
        obj.insert(
            "status".to_string(),
            json!(if dry_run {
                "dry_run"
            } else if outcome.failed_count > 0 {
                "partial"
            } else if outcome.applied_count > 0 {
                "applied"
            } else {
                "noop"
            }),
        );
        obj.insert("applied_count".to_string(), json!(outcome.applied_count));
        obj.insert("failed_count".to_string(), json!(outcome.failed_count));
        obj.insert("skipped_count".to_string(), json!(outcome.skipped_count));
        obj.insert("results".to_string(), json!(outcome.results));
        obj.insert(
            "writes_edges".to_string(),
            json!(!dry_run && outcome.applied_count > 0),
        );
        obj.insert("plan".to_string(), plan);
    }

    let generated_at_unix = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map(|d| d.as_secs())
        .unwrap_or(0);
    let record = palace_orphan_approved_link_apply_record_for_time(
        &response,
        req.actor.as_deref(),
        generated_at_unix,
    );
    append_palace_orphan_approved_link_apply_record(&apply_audit_path, &record).map_err(|e| {
        (
            StatusCode::INTERNAL_SERVER_ERROR,
            format!("append orphan approved link apply audit: {e}"),
        )
    })?;

    Ok(Json(response))
}

async fn build_graph_snapshot(
    s: &AppState,
    include_catalog: bool,
) -> Result<Value, (StatusCode, String)> {
    // ── sqlite layer ────────────────────────────────────────────────────
    let nodes = s
        .store
        .list_memories(None, MemoryListSort::ByImportance, STORE_FETCH_LIMIT)
        .await
        .map_err(|e| {
            (
                StatusCode::INTERNAL_SERVER_ERROR,
                format!("list_memories: {e}"),
            )
        })?;

    // P19 — fill VIEWER_NODE_CAP working-memory-first, then catalog.
    //
    // Pre-P19 the cap was a flat `take(500)` after sort-by-importance. When
    // `q.all=true` (the default for the canvas viewer) catalog rows (484
    // kind='skill' bulk imports) dominate the top-500, pushing chat_session
    // / lesson / decision off the cap. Result: cofires + co_referenced
    // edges silently dropped because one endpoint sits outside `is_node`.
    // P17 diagnosed the catalog skew; P18 worked around it via a focused
    // endpoint; P19 fixes the graph itself: working memory always fits
    // first (today: 186 < 500), catalog only takes the leftover slots.
    let active_all: Vec<_> = nodes
        .into_iter()
        .filter(|m| m.status == "active")
        .filter(|m| include_catalog || m.kind != "skill")
        .collect();
    const CATALOG_KINDS: &[&str] = &["skill"];
    let (catalog_nodes, working_nodes): (Vec<_>, Vec<_>) = active_all
        .into_iter()
        .partition(|m| CATALOG_KINDS.iter().any(|c| *c == m.kind.as_str()));
    let mut active: Vec<_> = working_nodes.into_iter().take(VIEWER_NODE_CAP).collect();
    let remaining = VIEWER_NODE_CAP.saturating_sub(active.len());
    active.extend(catalog_nodes.into_iter().take(remaining));
    let sqlite_keys: HashSet<String> = active.iter().map(|m| m.key.clone()).collect();

    // ── markdown layer ──────────────────────────────────────────────────
    // Read markdown first so that the sqlite edge loop knows which keys
    // resolve as markdown nodes (used to render explicit cross-source
    // edges like `annotates` written via POST /api/annotate).
    let mds = if let Some(root) = &s.markdown_root {
        read_markdown_dir(root)
    } else {
        Vec::new()
    };
    // Markdown keys that are NOT already in sqlite (avoid double-rendering
    // if a key happens to exist in both — unlikely, but cheap to handle).
    let md_only: Vec<&MarkdownMemory> = mds
        .iter()
        .filter(|m| !sqlite_keys.contains(&m.key))
        .collect();
    let md_keys: HashSet<String> = md_only.iter().map(|m| m.key.clone()).collect();

    // Helper: is this key renderable as a node in the merged graph?
    let is_node = |k: &str| sqlite_keys.contains(k) || md_keys.contains(k);

    // ── sqlite edges ────────────────────────────────────────────────────
    // Includes intra-sqlite edges and explicit cross-source edges (e.g.
    // `annotates` from a sqlite annotation to a markdown vision node).
    // Cross-source edges are only rendered when **both endpoints exist as
    // nodes** — we don't render dangling refs.
    let mut seen: HashSet<(String, String, String)> = HashSet::new();
    let mut sqlite_edges = Vec::new();
    for m in &active {
        let nbrs = s.store.memory_neighbors(&m.key).await.unwrap_or_default();
        for e in nbrs {
            let key = if e.from_key < e.to_key {
                (e.from_key.clone(), e.to_key.clone(), e.edge_type.clone())
            } else {
                (e.to_key.clone(), e.from_key.clone(), e.edge_type.clone())
            };
            if seen.insert(key) && is_node(&e.from_key) && is_node(&e.to_key) {
                sqlite_edges.push(e);
            }
        }
    }

    // ── markdown edges ─ within markdown only (no cross-source). ────────
    let mut md_edges = Vec::new();
    let mut md_seen: HashSet<(String, String)> = HashSet::new();
    for m in &md_only {
        for target in &m.links_to {
            if !md_keys.contains(target) {
                continue;
            }
            let key = if m.key < *target {
                (m.key.clone(), target.clone())
            } else {
                (target.clone(), m.key.clone())
            };
            if md_seen.insert(key) {
                md_edges.push((m.key.clone(), target.clone()));
            }
        }
    }

    // ── co-activation edges ─ Hebbian "fire together, wire together" ────
    // Pairs are seen via record_coactivation as side-effect of memory_search
    // and (since C2) Palace clicks. We render them as a soft underlay so
    // attention-clusters become visible *beneath* the structural skeleton.
    //
    // Dedup: an explicit (sqlite or markdown) edge between a pair always wins
    // — coact between the same nodes would be redundant signal. min_count=2
    // filters out single-encounter noise; limit=300 caps render cost.
    let coact_top = s
        .store
        .top_coactivation_edges(2, 300)
        .await
        .unwrap_or_default();
    let mut explicit_pairs: HashSet<(String, String)> = HashSet::new();
    for e in &sqlite_edges {
        let p = if e.from_key < e.to_key {
            (e.from_key.clone(), e.to_key.clone())
        } else {
            (e.to_key.clone(), e.from_key.clone())
        };
        explicit_pairs.insert(p);
    }
    for (a, b) in &md_edges {
        let p = if a < b {
            (a.clone(), b.clone())
        } else {
            (b.clone(), a.clone())
        };
        explicit_pairs.insert(p);
    }
    let mut coact_edges = Vec::new();
    let mut coact_seen: HashSet<(String, String)> = HashSet::new();
    for c in coact_top {
        if !is_node(&c.key_a) || !is_node(&c.key_b) {
            continue;
        }
        let p = if c.key_a < c.key_b {
            (c.key_a.clone(), c.key_b.clone())
        } else {
            (c.key_b.clone(), c.key_a.clone())
        };
        if explicit_pairs.contains(&p) {
            continue;
        }
        if coact_seen.insert(p) {
            coact_edges.push(c);
        }
    }

    // ── serialize ───────────────────────────────────────────────────────
    let mut nodes_json: Vec<Value> = active
        .iter()
        .map(|m| {
            json!({
                "id":            m.key,
                "kind":          m.kind,
                "importance":    (m.importance * 1000.0).round() / 1000.0,
                "tags":          m.tags,
                "label":         m.key,
                "access":        m.access_count,
                "last_accessed": m.last_accessed_at,
                "source":        "sqlite",
            })
        })
        .collect();

    for m in &md_only {
        nodes_json.push(json!({
            "id":            m.key,
            "kind":          m.kind,
            "importance":    0.7,    // markdown memories are user-curated → treat as high signal
            "tags":          Vec::<String>::new(),
            "label":         m.key,
            "access":        0,
            "last_accessed": 0,
            "source":        "markdown",
            "description":   m.description,
        }));
    }

    let mut edges_json: Vec<Value> = sqlite_edges
        .iter()
        .map(|e| {
            json!({
                "source": e.from_key,
                "target": e.to_key,
                "type":   e.edge_type,
                "weight": (e.weight * 1000.0).round() / 1000.0,
            })
        })
        .collect();

    for (a, b) in &md_edges {
        edges_json.push(json!({
            "source": a,
            "target": b,
            "type":   "references",
            "weight": 0.5,
        }));
    }

    for c in &coact_edges {
        // Normalize raw count → 0..1 for cytoscape mapData; keep raw count
        // alongside so the side panel / hover tip can show "fired N times".
        let weight = (c.count as f64 / 10.0).min(1.0);
        edges_json.push(json!({
            "source": c.key_a,
            "target": c.key_b,
            "type":   "coactivation",
            "weight": (weight * 1000.0).round() / 1000.0,
            "count":  c.count,
        }));
    }

    let now_secs = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map(|d| d.as_secs() as i64)
        .unwrap_or(0);

    Ok(json!({
        "nodes": nodes_json,
        "edges": edges_json,
        "now":   now_secs,
        "stats": {
            "sqlite_nodes":   active.len(),
            "markdown_nodes": md_only.len(),
            "sqlite_edges":   sqlite_edges.len(),
            "markdown_edges": md_edges.len(),
            "coact_edges":    coact_edges.len(),
        }
    }))
}

#[derive(Deserialize, Default)]
struct SemanticEventsQuery {
    /// `?all=1` mirrors `/api/graph?all=1`.
    #[serde(default)]
    #[serde(deserialize_with = "deserialize_boolish")]
    all: bool,
    /// Optional client-provided previous counts. The endpoint stays read-only:
    /// callers that want a diff carry their own baseline, typically via
    /// localStorage or an external monitor.
    #[serde(default)]
    baseline_nodes: Option<i64>,
    #[serde(default)]
    baseline_edges: Option<i64>,
    #[serde(default)]
    baseline_orphans: Option<i64>,
    #[serde(default)]
    baseline_hubs: Option<i64>,
}

async fn api_semantic_events(
    State(s): State<AppState>,
    Query(q): Query<SemanticEventsQuery>,
) -> Result<Json<Value>, (StatusCode, String)> {
    let graph = build_graph_snapshot(&s, q.all).await?;
    Ok(Json(build_palace_semantic_events(&graph, &q)))
}

async fn api_self_review_packet(
    State(s): State<AppState>,
    Query(q): Query<SelfReviewPacketQuery>,
) -> Result<Json<Value>, (StatusCode, String)> {
    let graph = build_graph_snapshot(&s, q.all).await?;
    let decisions_path = default_palace_orphan_candidate_decisions_path();
    let decisions = load_palace_orphan_candidate_decisions(&decisions_path).map_err(|e| {
        (
            StatusCode::INTERNAL_SERVER_ERROR,
            format!("load orphan candidate review decisions: {e}"),
        )
    })?;
    let apply_audit_path = default_palace_orphan_approved_link_apply_path();
    let apply_records =
        load_palace_orphan_approved_link_apply_records(&apply_audit_path).map_err(|e| {
            (
                StatusCode::INTERNAL_SERVER_ERROR,
                format!("load orphan approved link apply audit: {e}"),
            )
        })?;
    Ok(Json(build_palace_self_review_packet_with_history(
        &graph,
        &decisions,
        &apply_records,
    )))
}

fn vi64(v: &Value) -> Option<i64> {
    v.as_i64()
        .or_else(|| v.as_u64().and_then(|n| i64::try_from(n).ok()))
}

fn palace_graph_stats(graph: &Value) -> Value {
    let nodes = graph
        .get("nodes")
        .and_then(Value::as_array)
        .cloned()
        .unwrap_or_default();
    let edges = graph
        .get("edges")
        .and_then(Value::as_array)
        .cloned()
        .unwrap_or_default();
    let now_secs = vi64(graph.get("now").unwrap_or(&Value::Null)).unwrap_or(0);
    let mut degree_keys: HashSet<String> = nodes
        .iter()
        .filter_map(|n| n.get("id").and_then(Value::as_str).map(str::to_string))
        .collect();
    let mut degree_map = std::collections::HashMap::<String, i64>::new();
    for key in &degree_keys {
        degree_map.insert(key.clone(), 0);
    }

    let mut coactivation_edges = 0i64;
    let mut explicit_edges = 0i64;
    for e in &edges {
        let edge_type = e.get("type").and_then(Value::as_str).unwrap_or("untyped");
        if edge_type == "coactivation" {
            coactivation_edges += 1;
            continue;
        }
        explicit_edges += 1;
        let Some(source) = e.get("source").and_then(Value::as_str) else {
            continue;
        };
        let Some(target) = e.get("target").and_then(Value::as_str) else {
            continue;
        };
        if degree_keys.contains(source) {
            *degree_map.entry(source.to_string()).or_insert(0) += 1;
        }
        if degree_keys.contains(target) {
            *degree_map.entry(target.to_string()).or_insert(0) += 1;
        }
    }
    degree_keys.clear();

    let mut sqlite_nodes = 0i64;
    let mut markdown_nodes = 0i64;
    let mut fresh_nodes = 0i64;
    let mut stale_nodes = 0i64;
    const FRESH_WINDOW_SECS: i64 = 3600;
    const STALE_WINDOW_SECS: i64 = 7 * 24 * 3600;
    for n in &nodes {
        match n.get("source").and_then(Value::as_str).unwrap_or("") {
            "sqlite" => sqlite_nodes += 1,
            "markdown" => markdown_nodes += 1,
            _ => {}
        }
        let last_accessed = vi64(n.get("last_accessed").unwrap_or(&Value::Null)).unwrap_or(0);
        if last_accessed > 0 {
            let age = now_secs.saturating_sub(last_accessed);
            if age < FRESH_WINDOW_SECS {
                fresh_nodes += 1;
            }
            if age > STALE_WINDOW_SECS {
                stale_nodes += 1;
            }
        }
    }

    let connected: Vec<i64> = degree_map.values().copied().filter(|d| *d > 0).collect();
    let orphan_nodes = degree_map.values().filter(|d| **d == 0).count() as i64;
    let mut sorted = connected.clone();
    sorted.sort_unstable();
    let p95_idx = sorted.len().saturating_sub(1).min(sorted.len() * 95 / 100);
    let p95 = sorted.get(p95_idx).copied().unwrap_or(0);
    let hub_threshold = 5.max(p95);
    let enable_hubs = connected.len() >= 20;
    let hub_nodes = if enable_hubs {
        degree_map.values().filter(|d| **d >= hub_threshold).count() as i64
    } else {
        0
    };
    let node_count = nodes.len() as i64;
    let edge_count = edges.len() as i64;
    let connected_ratio = if node_count > 0 {
        (node_count - orphan_nodes) as f64 / node_count as f64
    } else {
        0.0
    };
    let explicit_density = explicit_edges as f64 / node_count.max(1) as f64;

    json!({
        "nodes": node_count,
        "edges": edge_count,
        "sqlite_nodes": sqlite_nodes,
        "markdown_nodes": markdown_nodes,
        "explicit_edges": explicit_edges,
        "coactivation_edges": coactivation_edges,
        "orphan_nodes": orphan_nodes,
        "hub_nodes": hub_nodes,
        "fresh_nodes": fresh_nodes,
        "stale_nodes": stale_nodes,
        "hub_threshold": hub_threshold,
        "connected_ratio": (connected_ratio * 1000.0).round() / 1000.0,
        "explicit_density": (explicit_density * 1000.0).round() / 1000.0,
    })
}

fn palace_self_review_lane(
    id: &str,
    action: &str,
    count: i64,
    priority: i64,
    risk: &str,
    tone: &str,
    detail: &str,
    next_step: &str,
    href: &str,
) -> Value {
    json!({
        "id": id,
        "action": action,
        "count": count.max(0),
        "priority": priority,
        "risk": risk,
        "tone": tone,
        "detail": detail,
        "next_step": next_step,
        "href": href,
    })
}

#[cfg(test)]
fn build_palace_self_review_packet(graph: &Value) -> Value {
    build_palace_self_review_packet_with_history(graph, &[], &[])
}

fn build_palace_self_review_history(decisions: &[Value], apply_records: &[Value]) -> Value {
    let mut approved_count = 0_i64;
    let mut deferred_count = 0_i64;
    let mut rejected_count = 0_i64;
    let mut last_decision_at_unix = 0_i64;
    let mut recent = Vec::new();

    for decision in decisions {
        let generated_at = vi64(decision.get("generated_at_unix").unwrap_or(&Value::Null))
            .unwrap_or(0)
            .max(0);
        last_decision_at_unix = last_decision_at_unix.max(generated_at);
        match decision
            .get("decision")
            .and_then(Value::as_str)
            .unwrap_or("")
        {
            "approve" => approved_count += 1,
            "defer" => deferred_count += 1,
            "reject" => rejected_count += 1,
            _ => {}
        }
        recent.push(json!({
            "kind": "decision",
            "generated_at_unix": generated_at,
            "decision": decision.get("decision").cloned().unwrap_or(Value::Null),
            "pair_id": decision.get("pair_id").cloned().unwrap_or(Value::Null),
            "reviewer": decision.get("reviewer").cloned().unwrap_or(Value::Null),
        }));
    }

    let mut applied_count = 0_i64;
    let mut failed_count = 0_i64;
    let mut last_apply_at_unix = 0_i64;
    for record in apply_records {
        let generated_at = vi64(record.get("generated_at_unix").unwrap_or(&Value::Null))
            .unwrap_or(0)
            .max(0);
        last_apply_at_unix = last_apply_at_unix.max(generated_at);
        applied_count += vi64(record.get("applied_count").unwrap_or(&Value::Null))
            .unwrap_or(0)
            .max(0);
        failed_count += vi64(record.get("failed_count").unwrap_or(&Value::Null))
            .unwrap_or(0)
            .max(0);
        recent.push(json!({
            "kind": "apply",
            "generated_at_unix": generated_at,
            "status": record.get("status").cloned().unwrap_or(Value::Null),
            "applied_count": record.get("applied_count").cloned().unwrap_or(json!(0)),
            "failed_count": record.get("failed_count").cloned().unwrap_or(json!(0)),
            "dry_run": record.get("dry_run").cloned().unwrap_or(json!(true)),
            "blocked": record.get("blocked").cloned().unwrap_or(json!(true)),
            "actor": record.get("actor").cloned().unwrap_or(Value::Null),
        }));
    }

    recent.sort_by(|a, b| {
        let at = vi64(a.get("generated_at_unix").unwrap_or(&Value::Null)).unwrap_or(0);
        let bt = vi64(b.get("generated_at_unix").unwrap_or(&Value::Null)).unwrap_or(0);
        bt.cmp(&at).then_with(|| {
            let ak = a.get("kind").and_then(Value::as_str).unwrap_or("");
            let bk = b.get("kind").and_then(Value::as_str).unwrap_or("");
            ak.cmp(bk)
        })
    });
    recent.truncate(6);

    json!({
        "schema": "agent_bridge.palace.self_review_history.v0",
        "read_only": true,
        "writes_memory": false,
        "writes_edges": false,
        "auto_apply_allowed": false,
        "decision_count": decisions.len(),
        "approved_count": approved_count,
        "deferred_count": deferred_count,
        "rejected_count": rejected_count,
        "apply_audit_count": apply_records.len(),
        "applied_count": applied_count,
        "failed_count": failed_count,
        "last_decision_at_unix": last_decision_at_unix,
        "last_apply_at_unix": last_apply_at_unix,
        "recent_limit": 6,
        "recent": recent,
    })
}

fn build_palace_self_review_packet_with_history(
    graph: &Value,
    decisions: &[Value],
    apply_records: &[Value],
) -> Value {
    let history = build_palace_self_review_history(decisions, apply_records);
    let now_secs = vi64(graph.get("now").unwrap_or(&Value::Null)).unwrap_or(0);
    let stats = palace_graph_stats(graph);
    let orphan_nodes = vi64(stats.get("orphan_nodes").unwrap_or(&Value::Null)).unwrap_or(0);
    let stale_nodes = vi64(stats.get("stale_nodes").unwrap_or(&Value::Null)).unwrap_or(0);
    let hub_nodes = vi64(stats.get("hub_nodes").unwrap_or(&Value::Null)).unwrap_or(0);
    let fresh_nodes = vi64(stats.get("fresh_nodes").unwrap_or(&Value::Null)).unwrap_or(0);
    let connected_ratio = stats
        .get("connected_ratio")
        .and_then(Value::as_f64)
        .unwrap_or(0.0);
    let health_score = ((connected_ratio * 100.0).round() as i64).clamp(0, 100);
    let readiness = if orphan_nodes > 0 || stale_nodes > 0 {
        "needs-review"
    } else if hub_nodes > 0 {
        "watch"
    } else {
        "steady"
    };

    let mut lanes = vec![
        palace_self_review_lane(
            "formation",
            "fresh",
            fresh_nodes,
            if fresh_nodes > 0 { 30 } else { 0 },
            if fresh_nodes > 0 { "low" } else { "none" },
            if fresh_nodes > 0 { "good" } else { "quiet" },
            "recent memories to classify",
            "Scan fresh entries for missing kind, scope, and tags.",
            "/?preset=fresh",
        ),
        palace_self_review_lane(
            "connect",
            "orphans",
            orphan_nodes,
            if orphan_nodes > 0 { 100 } else { 0 },
            if orphan_nodes > 0 { "high" } else { "none" },
            if orphan_nodes > 0 { "fragile" } else { "good" },
            "unlinked memories need edges",
            "Open orphan candidates and approve only evidence-backed links.",
            "/?preset=orphans",
        ),
        palace_self_review_lane(
            "retrieval",
            "stale",
            stale_nodes,
            if stale_nodes > 0 { 80 } else { 0 },
            if stale_nodes > 0 { "medium" } else { "none" },
            if stale_nodes > 0 { "watch" } else { "good" },
            "cold memories need judgment",
            "Review stale memories for keep, tombstone, or consolidation.",
            "/?preset=stale",
        ),
        palace_self_review_lane(
            "consolidate",
            "hubs",
            hub_nodes,
            if hub_nodes > 0 { 60 } else { 0 },
            if hub_nodes > 0 { "medium" } else { "none" },
            if hub_nodes > 0 { "watch" } else { "quiet" },
            "anchors need duplicate scan",
            "Inspect high-degree anchors for duplicates, summaries, and conflicts.",
            "/?preset=hubs",
        ),
    ];
    lanes.sort_by(|a, b| {
        let ap = vi64(a.get("priority").unwrap_or(&Value::Null)).unwrap_or(0);
        let bp = vi64(b.get("priority").unwrap_or(&Value::Null)).unwrap_or(0);
        bp.cmp(&ap).then_with(|| {
            let aid = a.get("id").and_then(Value::as_str).unwrap_or("");
            let bid = b.get("id").and_then(Value::as_str).unwrap_or("");
            aid.cmp(bid)
        })
    });

    let primary_lane = lanes
        .iter()
        .find(|lane| vi64(lane.get("count").unwrap_or(&Value::Null)).unwrap_or(0) > 0)
        .and_then(|lane| lane.get("id"))
        .and_then(Value::as_str)
        .unwrap_or("formation")
        .to_string();
    let summary = if readiness == "steady" {
        "Memory graph is steady; no urgent self-review lane is active.".to_string()
    } else {
        format!("Memory graph needs self-review: {primary_lane} is the highest-priority lane.")
    };
    let recommendations: Vec<Value> = lanes
        .iter()
        .filter(|lane| vi64(lane.get("count").unwrap_or(&Value::Null)).unwrap_or(0) > 0)
        .map(|lane| {
            json!({
                "lane": lane.get("id").cloned().unwrap_or(Value::Null),
                "action": lane.get("action").cloned().unwrap_or(Value::Null),
                "next_step": lane.get("next_step").cloned().unwrap_or(Value::Null),
            })
        })
        .collect();

    json!({
        "schema": "agent_bridge.palace.self_review_packet.v0",
        "source_adapter": "palace.self_review",
        "observed_at": now_secs,
        "read_only": true,
        "writes_memory": false,
        "writes_edges": false,
        "auto_apply_allowed": false,
        "readiness": readiness,
        "primary_lane": primary_lane.clone(),
        "health_score": health_score,
        "graph": stats.clone(),
        "history": history.clone(),
        "lanes": lanes,
        "recommendations": recommendations,
        "guardrails": {
            "write_policy": "read_only_no_auto_memory_write",
            "human_gate_required_for_writes": true,
            "source_of_truth": "server_side_graph_snapshot"
        },
        "provenance": {
            "endpoint": "/api/self-review-packet",
            "graph_endpoint": "/api/graph",
            "history_sources": [
                "palace_orphan_candidate_decisions",
                "palace_orphan_approved_link_apply_audit"
            ],
            "hash": semantic_hash(&json!({
                "stats": stats.clone(),
                "readiness": readiness,
                "primary_lane": primary_lane.clone(),
                "history": history.clone(),
            }))
        },
        "presentation": {
            "human_summary": summary,
            "machine_payload": {
                "readiness": readiness,
                "primary_lane": primary_lane.clone(),
                "health_score": health_score,
                "history": history.clone()
            },
            "ingestion": {
                "suggested_kind": "observation",
                "write_policy": "read_only_no_auto_memory_write"
            },
            "artifact": {
                "type": "http_json",
                "href": "/api/self-review-packet"
            },
            "created_at": now_secs
        }
    })
}

fn semantic_hash(value: &Value) -> String {
    let mut hasher = DefaultHasher::new();
    serde_json::to_string(value)
        .unwrap_or_else(|_| value.to_string())
        .hash(&mut hasher);
    format!("read_only_default_hasher:{:016x}", hasher.finish())
}

fn delta_json(current: &Value, baseline: &Value, key: &str) -> Value {
    let cur = vi64(current.get(key).unwrap_or(&Value::Null)).unwrap_or(0);
    let base = vi64(baseline.get(key).unwrap_or(&Value::Null)).unwrap_or(cur);
    json!(cur - base)
}

fn build_palace_semantic_events(graph: &Value, q: &SemanticEventsQuery) -> Value {
    let now_secs = vi64(graph.get("now").unwrap_or(&Value::Null)).unwrap_or(0);
    let current = palace_graph_stats(graph);
    let baseline = json!({
        "nodes": q.baseline_nodes.unwrap_or_else(|| vi64(current.get("nodes").unwrap_or(&Value::Null)).unwrap_or(0)),
        "edges": q.baseline_edges.unwrap_or_else(|| vi64(current.get("edges").unwrap_or(&Value::Null)).unwrap_or(0)),
        "orphan_nodes": q.baseline_orphans.unwrap_or_else(|| vi64(current.get("orphan_nodes").unwrap_or(&Value::Null)).unwrap_or(0)),
        "hub_nodes": q.baseline_hubs.unwrap_or_else(|| vi64(current.get("hub_nodes").unwrap_or(&Value::Null)).unwrap_or(0)),
    });
    let delta = json!({
        "nodes": delta_json(&current, &baseline, "nodes"),
        "edges": delta_json(&current, &baseline, "edges"),
        "orphan_nodes": delta_json(&current, &baseline, "orphan_nodes"),
        "hub_nodes": delta_json(&current, &baseline, "hub_nodes"),
    });
    let changed = delta
        .as_object()
        .map(|m| m.values().any(|v| vi64(v).unwrap_or(0) != 0))
        .unwrap_or(false);
    let event_id = format!("evt-palace-graph-observed-{now_secs}");
    let diff_event_id = format!("evt-palace-graph-diff-{now_secs}");
    let object_id = "palace:memory-graph";
    let current_hash = semantic_hash(&current);

    json!({
        "schema": "agent_bridge.semantic_bus.palace_diff.v0",
        "source_adapter": "palace.memory_graph",
        "observed_at": now_secs,
        "semantic_objects": [
            {
                "schema": "agent_bridge.semantic_bus.object.v0",
                "object_id": object_id,
                "object_type": "palace.memory_graph",
                "source_adapter": "palace.memory_graph",
                "label": "Palace memory graph",
                "state": current,
                "relations": [
                    { "type": "source_layer", "target": "palace:memory-source:sqlite" },
                    { "type": "source_layer", "target": "palace:memory-source:markdown" },
                    { "type": "edge_layer", "target": "palace:edge-layer:coactivation" }
                ],
                "confidence": 1.0,
                "observed_at": now_secs,
                "provenance": {
                    "endpoint": "/api/semantic-events",
                    "graph_endpoint": "/api/graph",
                    "hash": current_hash
                }
            }
        ],
        "events": [
            {
                "event_id": event_id,
                "ts": now_secs,
                "source": "palace",
                "actor": "palace_viewer",
                "project": null,
                "event_type": "palace.graph.observed",
                "subject_id": object_id,
                "payload_json": current,
                "source_event_ids": [],
                "prev_hash": null,
                "hash": current_hash
            },
            {
                "event_id": diff_event_id,
                "ts": now_secs,
                "source": "palace",
                "actor": "palace_viewer",
                "project": null,
                "event_type": if changed { "palace.graph.diff.changed" } else { "palace.graph.diff.unchanged" },
                "subject_id": object_id,
                "payload_json": {
                    "baseline": baseline,
                    "current": current,
                    "delta": delta,
                    "changed": changed
                },
                "source_event_ids": [event_id],
                "prev_hash": null,
                "hash": semantic_hash(&json!({ "current": current, "delta": delta, "changed": changed }))
            }
        ],
        "diff": {
            "baseline": baseline,
            "current": current,
            "delta": delta,
            "changed": changed
        },
        "verification": {
            "verdict": "verified",
            "reason": "palace_graph_snapshot_normalized",
            "method": "server_side_graph_builder",
            "evidence": {
                "raw_nodes": graph.get("nodes").and_then(Value::as_array).map(Vec::len).unwrap_or(0),
                "raw_edges": graph.get("edges").and_then(Value::as_array).map(Vec::len).unwrap_or(0),
                "stats": graph.get("stats").cloned().unwrap_or(Value::Null)
            },
            "verified_to": "semantic_objects/events/diff",
            "recover": "proceed",
            "raw_available": true
        },
        "presentation": {
            "presentation_id": format!("present-palace-graph-{now_secs}"),
            "source_event_ids": [event_id, diff_event_id],
            "human_summary": if changed { "Palace graph changed relative to caller baseline." } else { "Palace graph matches caller baseline." },
            "machine_payload": {
                "object_id": object_id,
                "diff": {
                    "nodes": delta_json(&current, &baseline, "nodes"),
                    "edges": delta_json(&current, &baseline, "edges"),
                    "orphan_nodes": delta_json(&current, &baseline, "orphan_nodes"),
                    "hub_nodes": delta_json(&current, &baseline, "hub_nodes")
                }
            },
            "ingestion": {
                "suggested_kind": "observation",
                "write_policy": "read_only_no_auto_memory_write"
            },
            "artifact": {
                "type": "http_json",
                "href": "/api/semantic-events"
            },
            "created_at": now_secs
        }
    })
}

// ── Single-memory endpoint ───────────────────────────────────────────────

/// Fetch a single memory record by key.
///
/// Tries sqlite first via `memory_get` (which atomically bumps
/// `access_count` and `last_accessed_at` — this is **C2 click-as-trace**:
/// every Palace click leaves a real cognitive imprint). Falls back to
/// markdown if the key matches a `.md` file. After a successful sqlite
/// hit, the key joins a rolling click window; once the window has 2+
/// entries we call `record_coactivation` so the Hebbian system learns
/// "these nodes were in the user's attention together".
async fn api_memory(
    State(s): State<AppState>,
    Path(key): Path<String>,
) -> Result<Json<Value>, (StatusCode, String)> {
    // sqlite lookup — auto-bumps access_count + last_accessed_at.
    let started = std::time::Instant::now();
    if let Some(m) = s.store.memory_get(&key).await.map_err(|e| {
        (
            StatusCode::INTERNAL_SERVER_ERROR,
            format!("memory_get: {e}"),
        )
    })? {
        // Phase 0 telemetry: log the click into `memory_query_log` so
        // `dream replay-audit` (and downstream attention analyses) can
        // see Palace navigation, not just MCP tool calls. Without this
        // the trace is biased toward Claude's programmatic retrievals —
        // an audit on a Palace-heavy workflow ends up with 0–2 events
        // per summary even when humans are actively clicking around.
        // Source label distinguishes from MCP `memory_get` (`mcp:memory_get`).
        let now_secs = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .map(|d| d.as_secs() as i64)
            .unwrap_or(0);
        let elapsed_us = started.elapsed().as_micros().min(u32::MAX as u128) as u32;
        let rec = MemoryQueryRecord {
            kind: "get".into(),
            query: key.clone(),
            tags_json: "[]".into(),
            hit_count: 1,
            top_hit_age_secs: Some(now_secs - m.created_at),
            top_hit_created_at: Some(m.created_at),
            duration_us: elapsed_us,
            source: "palace_viewer:click".into(),
            at: now_secs,
        };
        let store_for_log = s.store.clone();
        tokio::spawn(async move {
            let _ = store_for_log.record_memory_query(&rec).await;
        });

        // Feed the rolling click window → co-activation. Best-effort: any
        // failure here just skips the recording, never blocks the read.
        let coact_keys = {
            let mut buf = s.recent_clicks.lock().expect("click window poisoned");
            // Don't double-record consecutive clicks on the same node
            // (user re-opening a panel shouldn't inflate the bond).
            if buf.back().map(String::as_str) != Some(key.as_str()) {
                if buf.len() >= CLICK_WINDOW {
                    buf.pop_front();
                }
                buf.push_back(key.clone());
            }
            // Snapshot for the await call below — drop the lock first.
            buf.iter().cloned().collect::<Vec<_>>()
        };
        if coact_keys.len() >= 2 {
            let _ = s.store.record_coactivation(&coact_keys, None).await;
        }

        let store_neighbors = s.store.memory_neighbors(&key).await.unwrap_or_default();

        return Ok(Json(json!({
            "key":          m.key,
            "kind":         m.kind,
            "content":      m.content,
            "tags":         m.tags,
            "importance":   m.importance,
            "status":       m.status,
            "access_count": m.access_count,
            "created_at":   m.created_at,
            "updated_at":   m.updated_at,
            "scope":        m.scope,
            "source":       "sqlite",
            "store_neighbors": palace_store_neighbor_summary_value(&key, &store_neighbors),
        })));
    }

    // Markdown fallback. No access tracking yet — would need a separate
    // file-watcher schema to attribute clicks to markdown nodes.
    if let Some(root) = &s.markdown_root {
        let path = root.join(format!("{key}.md"));
        if let Ok(body) = fs::read_to_string(&path) {
            let m = parse_markdown_memory(key.clone(), &body);
            return Ok(Json(json!({
                "key":          m.key,
                "kind":         m.kind,
                "content":      m.content,
                "tags":         Vec::<String>::new(),
                "importance":   0.7,
                "status":       "active",
                "access_count": 0,
                "description":  m.description,
                "links_to":     m.links_to,
                "source":       "markdown",
                "file_path":    path.display().to_string(),
            })));
        }
    }

    Err((StatusCode::NOT_FOUND, format!("memory not found: {key}")))
}

// ── Tombstone endpoint (C8: act on stale memories) ──────────────────────

/// Soft-delete (tombstone) a memory by key. Idempotent: tombstoning an
/// already-tombstoned key returns `deleted: false` without error. Used
/// by the C8 stale-review panel so the user can sweep cold memories
/// without leaving Palace.
async fn api_memory_tombstone(
    State(s): State<AppState>,
    Path(key): Path<String>,
) -> Result<Json<Value>, (StatusCode, String)> {
    let deleted = s.store.memory_delete(&key).await.map_err(|e| {
        (
            StatusCode::INTERNAL_SERVER_ERROR,
            format!("memory_delete: {e}"),
        )
    })?;
    Ok(Json(json!({ "ok": true, "key": key, "deleted": deleted })))
}

// ── Lineage endpoint (P7: closes VIEWER_NODE_CAP visibility gap) ────────
//
// `/api/graph` truncates by importance, so chains of low-importance
// chat_sessions (the typical fork-chain shape) become invisible in the
// rendered subgraph. memory_edges still has them; this endpoint walks
// them directly so the canvas rail can surface the chain.
//
// BFS from `key` along edges matching `type` (default `evolved_from`),
// up to `depth` hops (default 10, capped at 50). Visited set guards
// against cycles. Returns the chain in walk order with the edge type
// that connected each hop.

#[derive(Deserialize)]
struct LineageQuery {
    /// Edge type to follow. Default `evolved_from`. Use `discussed_at`
    /// to walk chat_session → topic; `supersedes` for replacement chains;
    /// `all` (literal string) walks any edge type — useful for general
    /// "show me everything connected".
    #[serde(default)]
    r#type: Option<String>,
    /// Max hops. Capped at 50 server-side to bound work.
    #[serde(default)]
    depth: Option<u32>,
    /// Walk direction. `out` (default) follows from→to; `in` follows
    /// to→from (i.e. "who evolved from me"); `both` is bidirectional.
    #[serde(default)]
    direction: Option<String>,
}

async fn api_lineage(
    State(s): State<AppState>,
    Path(key): Path<String>,
    Query(q): Query<LineageQuery>,
) -> Result<Json<Value>, (StatusCode, String)> {
    let edge_filter = q.r#type.as_deref().unwrap_or("evolved_from").to_string();
    let depth = q.depth.unwrap_or(10).min(50) as usize;
    let direction = q.direction.as_deref().unwrap_or("out").to_string();
    let walk_out = matches!(direction.as_str(), "out" | "both");
    let walk_in = matches!(direction.as_str(), "in" | "both");
    if !walk_out && !walk_in {
        return Err((
            StatusCode::BAD_REQUEST,
            format!("direction must be one of out|in|both, got {direction}"),
        ));
    }

    // BFS queue of (key, hop_count). Two distinct visited sets:
    //   `enqueued`  — guards cycle re-traversal (per-node, like classic BFS)
    //   `emitted`   — guards duplicate chain entries (per (next, edge_type))
    // Without the (next, edge_type) tier, two edges between the same
    // pair (e.g. fork-chain creates BOTH evolved_from B→A AND an
    // auto-supersedes B→A from threshold dedupe) would have only one
    // emitted: whichever came first via memory_neighbors. Bug surfaced
    // in P10-B e2e where evolved_from quietly disappeared from the
    // lineage rail because supersedes happened to win the iteration race.
    use std::collections::{HashSet, VecDeque};
    let mut enqueued: HashSet<String> = HashSet::new();
    enqueued.insert(key.clone());
    let mut emitted: HashSet<(String, String)> = HashSet::new();
    let mut queue: VecDeque<(String, u32)> = VecDeque::new();
    queue.push_back((key.clone(), 0));

    // Each chain entry records the step: who was added + how we got here.
    let mut chain: Vec<Value> = Vec::new();
    let mut truncated = false;

    while let Some((cur, hop)) = queue.pop_front() {
        if hop >= depth as u32 {
            // Reached depth limit; any further would be cut off.
            truncated = true;
            continue;
        }
        let nbrs = s.store.memory_neighbors(&cur).await.unwrap_or_default();
        for e in nbrs {
            // Edge filter — "all" passes everything.
            if edge_filter != "all" && e.edge_type != edge_filter {
                continue;
            }
            // Direction filter — only follow edges in the requested direction.
            // memory_neighbors returns both incoming and outgoing edges for
            // `cur` (it's the union); we distinguish via from_key/to_key.
            let next = if e.from_key == cur && walk_out {
                e.to_key.clone()
            } else if e.to_key == cur && walk_in {
                e.from_key.clone()
            } else {
                continue;
            };
            // Dedup per (target_key, edge_type): multiple edge types
            // between the same pair each emit their own chain entry.
            let emit_key = (next.clone(), e.edge_type.clone());
            if emitted.contains(&emit_key) {
                continue;
            }
            emitted.insert(emit_key);
            chain.push(json!({
                "from": cur,
                "to": next,
                "edge_type": e.edge_type,
                "weight": e.weight,
                "hop": hop + 1,
            }));
            // Enqueue once per target (cycle guard): if we already walked
            // from this node before, don't re-traverse its outgoing edges
            // — but we still emitted the new edge type above so the
            // chain surface stays complete.
            if !enqueued.contains(&next) {
                enqueued.insert(next.clone());
                queue.push_back((next, hop + 1));
            }
        }
    }

    Ok(Json(json!({
        "ok": true,
        "key": key,
        "edge_filter": edge_filter,
        "direction": direction,
        "depth_limit": depth,
        "chain": chain,
        "chain_length": chain.len(),
        "truncated": truncated,
    })))
}

// ── Coactivation peers (P18) ─────────────────────────────────────────────
//
// One-hop neighbors over the **explicit** attention edges (`cofires` from
// dream-promote tier 1, `co_referenced` from tier 2 — see P16-M). Direct
// memory_edges scan; bypasses the /api/graph VIEWER_NODE_CAP=500 filter
// that drops these edges when their endpoints sit below the top-500
// importance line (very common for chat_session + lesson clusters).
//
// Same pattern as P7 /api/lineage: focused endpoint per key, no graph
// truncation, used by the canvas rail to surface tier-1 + tier-2
// Hebbian peers for whichever node the user is working on.

async fn api_coactivation_peers(
    State(s): State<AppState>,
    Path(key): Path<String>,
) -> Result<Json<Value>, (StatusCode, String)> {
    let nbrs = s.store.memory_neighbors(&key).await.map_err(|e| {
        (
            StatusCode::INTERNAL_SERVER_ERROR,
            format!("memory_neighbors: {e}"),
        )
    })?;

    // Project to peer view. Dedupe by (peer, edge_type) so two parallel
    // edges of the same type collapse, but the same peer can appear under
    // both 'cofires' AND 'co_referenced' if the dream-promote pass added
    // both (rare; tier-2 normally skips when tier-1 cofires exists).
    let mut peers: Vec<Value> = Vec::new();
    let mut seen: HashSet<(String, String)> = HashSet::new();
    for e in nbrs {
        let et = e.edge_type.as_str();
        if et != "cofires" && et != "co_referenced" {
            continue;
        }
        let other = if e.from_key == key {
            e.to_key.clone()
        } else {
            e.from_key.clone()
        };
        if other == key {
            continue;
        }
        if !seen.insert((other.clone(), et.to_string())) {
            continue;
        }
        peers.push(json!({
            "key": other,
            "edge_type": et,
            "weight": (e.weight * 1000.0).round() / 1000.0,
        }));
    }

    // Sort: cofires (tier 1, weight 0.5-0.95) first, co_referenced
    // (tier 2, weight 0.3-0.5) after; within each tier, weight desc.
    peers.sort_by(|a, b| {
        let ta = a["edge_type"].as_str() == Some("cofires");
        let tb = b["edge_type"].as_str() == Some("cofires");
        tb.cmp(&ta).then_with(|| {
            let wa = a["weight"].as_f64().unwrap_or(0.0);
            let wb = b["weight"].as_f64().unwrap_or(0.0);
            wb.partial_cmp(&wa).unwrap_or(std::cmp::Ordering::Equal)
        })
    });

    let cofires_count = peers
        .iter()
        .filter(|p| p["edge_type"].as_str() == Some("cofires"))
        .count();
    let co_referenced_count = peers.len() - cofires_count;

    Ok(Json(json!({
        "ok": true,
        "key": key,
        "peers": peers,
        "edge_types": ["cofires", "co_referenced"],
        "cofires_count": cofires_count,
        "co_referenced_count": co_referenced_count,
    })))
}

// ── Embedding backend stats (P12) ────────────────────────────────────────
//
// Surfaces the v26 `embedding_backend` distribution so Palace can show
// "you have N hash-quality memories, run memory_reindex --only-stale
// when ONNX is ready." NULL is reported as `"unknown"` (pre-v26 rows).

async fn api_embedding_stats(
    State(s): State<AppState>,
) -> Result<Json<Value>, (StatusCode, String)> {
    let rows = s
        .store
        .memory_embedding_backend_counts()
        .await
        .map_err(|e| {
            (
                StatusCode::INTERNAL_SERVER_ERROR,
                format!("embedding_backend_counts: {e}"),
            )
        })?;
    let total: u64 = rows.iter().map(|(_, n)| n).sum();
    let breakdown: Vec<Value> = rows
        .into_iter()
        .map(|(b, n)| json!({ "backend": b, "count": n }))
        .collect();
    // P17: also surface kind breakdown so the footer can separate
    // working memory from catalog-style bulk imports (e.g. kind='skill').
    // Raw counts only; UI decides which kinds are catalog.
    let kind_rows = s.store.memory_kind_counts().await.map_err(|e| {
        (
            StatusCode::INTERNAL_SERVER_ERROR,
            format!("memory_kind_counts: {e}"),
        )
    })?;
    let kind_breakdown: Vec<Value> = kind_rows
        .into_iter()
        .map(|(k, n)| json!({ "kind": k, "count": n }))
        .collect();
    Ok(Json(json!({
        "ok": true,
        "total_active": total,
        "breakdown": breakdown,
        "kind_breakdown": kind_breakdown,
        "catalog_kinds": ["skill"],
    })))
}

// ── Canvas chat attachment upload (P14: multi-modal paste v0.5) ─────────
//
// Accepts base64-encoded images (or any binary) from the chat panel's
// paste handler. Writes to `/tmp/canvas-chat-attachments/<ts>-<hex>.<ext>`
// and returns the path. The spawned-claude in canvas chat has Read tool
// access by default and can interpret images natively, so the chat
// flow only has to surface "[image: <path>]" markers in the prompt and
// claude will reach for Read on its own (the chat prompt template also
// hints this).
//
// No auth/quota in v0.5; Palace is local-only; abuse risk is low.

#[derive(Deserialize)]
struct AttachmentPayload {
    /// MIME type, e.g. `image/png`, `image/jpeg`. Used to derive file
    /// extension; defaults to `bin` for unknown types.
    media_type: String,
    /// Base64-encoded payload (no `data:` URL prefix).
    data_base64: String,
}

async fn api_canvas_chat_attachment(
    State(_s): State<AppState>,
    Json(p): Json<AttachmentPayload>,
) -> Result<Json<Value>, (StatusCode, String)> {
    let ext = match p.media_type.as_str() {
        "image/png" => "png",
        "image/jpeg" => "jpg",
        "image/gif" => "gif",
        "image/webp" => "webp",
        "image/svg+xml" => "svg",
        _ => "bin",
    };
    let bytes = general_purpose::STANDARD
        .decode(p.data_base64.trim())
        .map_err(|e| (StatusCode::BAD_REQUEST, format!("invalid base64: {e}")))?;
    // 8 MiB cap — Palace chat is for snippets / screenshots, not
    // large media. Past that, user should put the file on disk
    // and paste the path directly.
    if bytes.len() > 8 * 1024 * 1024 {
        return Err((
            StatusCode::PAYLOAD_TOO_LARGE,
            format!("attachment {} bytes exceeds 8 MiB cap", bytes.len()),
        ));
    }
    let dir = std::path::PathBuf::from("/tmp/canvas-chat-attachments");
    tokio::fs::create_dir_all(&dir)
        .await
        .map_err(|e| (StatusCode::INTERNAL_SERVER_ERROR, format!("mkdir: {e}")))?;
    // Filename: <unix-ms>-<8-hex>.ext — sortable + collision-resistant
    // without a uuid crate. A second process landing in the same ms
    // collides only on full 8-hex match (1 in 4 billion).
    let now_ms = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map(|d| d.as_millis())
        .unwrap_or(0);
    let mut rand_hex = String::with_capacity(8);
    for _ in 0..8 {
        let r: u8 = (now_ms as u8)
            .wrapping_mul(31)
            .wrapping_add(rand_hex.len() as u8 * 7);
        rand_hex.push_str(&format!("{:x}", r % 16));
    }
    // Mix in a tiny entropy from the byte content itself so two pastes
    // of different content in the same millisecond don't collide.
    let content_hash: u32 = bytes
        .iter()
        .take(64)
        .fold(0u32, |a, b| a.wrapping_mul(131).wrapping_add(*b as u32));
    let filename = format!("{:013}-{:08x}.{}", now_ms, content_hash, ext);
    let path = dir.join(&filename);
    tokio::fs::write(&path, &bytes).await.map_err(|e| {
        (
            StatusCode::INTERNAL_SERVER_ERROR,
            format!("write {path:?}: {e}"),
        )
    })?;

    Ok(Json(json!({
        "ok": true,
        "path": path.display().to_string(),
        "filename": filename,
        "media_type": p.media_type,
        "size_bytes": bytes.len(),
    })))
}

// ── Annotate endpoint (C1: closes the 呼吸 loop) ─────────────────────────

#[derive(Deserialize)]
struct AnnotatePayload {
    /// The node the user is annotating from. Becomes the `to_key` of the
    /// outgoing edge (default `annotates`).
    target_key: String,
    /// User-authored body. Becomes the `content` of the new sqlite memory.
    content: String,
    /// New-memory kind. Defaults to `annotation` for backwards-compat with
    /// the C1 annotate flow. B-mode canvas-save passes `working_doc`.
    #[serde(default)]
    kind: Option<String>,
    /// Edge type from the new memory back to `target_key`. Defaults to
    /// `annotates`. Canvas-save uses `expanded_from` so the structural
    /// distinction (一笔注解 vs 完整工坊产物) survives in the graph.
    #[serde(default)]
    edge_type: Option<String>,
    /// Edge weight. Defaults to 1.0 (the historic annotate behavior).
    /// Canvas-save passes 0.7: 用户主动行为，强但弱于 hand-authored 主结构。
    #[serde(default)]
    weight: Option<f64>,
    /// Importance for the new memory record. Defaults to 0.6.
    #[serde(default)]
    importance: Option<f64>,
    /// Optional lineage parent — when set, the server adds a second
    /// `evolved_from` edge from the new memory → `parent_key`. Used by
    /// the canvas chat fork-chain flow: continue-this-discussion preloads
    /// the prior chat_session onto an origin focus, the user keeps
    /// chatting, then save records the new chat_session as evolved from
    /// the old one — preserving lineage so the graph can surface
    /// "this chat is descendant of <older chat>".
    #[serde(default)]
    parent_key: Option<String>,
}

/// Sanitize a kind string into a key-friendly snake_case slug. Only
/// `[a-z0-9_]` allowed; everything else becomes `_`. Empty → "memory".
/// Caps at 24 chars so keys don't blow up.
fn sanitize_kind_slug(raw: &str) -> String {
    let lower: String = raw
        .chars()
        .map(|c| {
            let c = c.to_ascii_lowercase();
            if c.is_ascii_alphanumeric() || c == '_' {
                c
            } else {
                '_'
            }
        })
        .take(24)
        .collect();
    if lower.is_empty() {
        "memory".into()
    } else {
        lower
    }
}

/// Create a new sqlite memory authored from the Palace, linked back to
/// `target_key`. The default flow (no extra payload fields) writes a
/// `kind=annotation` record with an `annotates` edge — the C1 path
/// untouched. B-mode "expand canvas" passes `kind=working_doc` +
/// `edge_type=expanded_from` + `weight=0.7` to make the structural
/// distinction visible in the graph.
///
/// Returns `{ ok: true, key, kind, edge }` on success. The frontend
/// should re-fetch `/api/graph` to see the new node + edge.
async fn api_annotate(
    State(s): State<AppState>,
    Json(p): Json<AnnotatePayload>,
) -> Result<Json<Value>, (StatusCode, String)> {
    let target = p.target_key.trim().to_string();
    let body = p.content.trim().to_string();
    if target.is_empty() {
        return Err((StatusCode::BAD_REQUEST, "target_key required".into()));
    }
    if body.is_empty() {
        return Err((StatusCode::BAD_REQUEST, "content required".into()));
    }

    let kind = p
        .kind
        .as_deref()
        .map(str::trim)
        .filter(|s| !s.is_empty())
        .unwrap_or("annotation")
        .to_string();
    let edge_type = p
        .edge_type
        .as_deref()
        .map(str::trim)
        .filter(|s| !s.is_empty())
        .unwrap_or("annotates")
        .to_string();
    let weight = p.weight.unwrap_or(1.0);
    let importance = p.importance.unwrap_or(0.6);

    let now_millis = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map(|d| d.as_millis())
        .unwrap_or(0);
    let kind_slug = sanitize_kind_slug(&kind);
    let key = format!("palace_{kind_slug}_{now_millis:013}");

    let mut tags = vec!["palace".to_string(), kind.clone()];
    if kind == "working_doc" {
        tags.push("canvas".to_string());
    }
    if kind == "chat_session" {
        // `chat` for filter UX; `canvas` because chat lives inside the
        // canvas overlay and is part of B-mode by definition.
        tags.push("chat".to_string());
        tags.push("canvas".to_string());
    }

    let mem = MemoryRecord {
        key: key.clone(),
        kind: kind.clone(),
        content: body,
        tags,
        related_keys: vec![target.clone()],
        scope: None,
        created_at: 0,
        updated_at: 0,
        last_accessed_at: 0,
        access_count: 0,
        importance,
        status: "active".to_string(),
        trigger_pattern: None,
        superseded_by: None,
    };

    s.store.memory_save(&mem).await.map_err(|e| {
        (
            StatusCode::INTERNAL_SERVER_ERROR,
            format!("memory_save: {e}"),
        )
    })?;

    s.store
        .memory_link(&key, &target, &edge_type, weight)
        .await
        .map_err(|e| {
            (
                StatusCode::INTERNAL_SERVER_ERROR,
                format!("memory_link: {e}"),
            )
        })?;

    // Optional lineage edge (fork chain). Skip silently if parent_key is
    // missing or empty, or points at this same memory (self-edge guard).
    // Failure to add the lineage edge surfaces as `lineage_ok: false` in
    // the response — non-fatal: the primary chat_session is already saved.
    let mut lineage_ok = true;
    let mut lineage_edge: Option<String> = None;
    let parent = p
        .parent_key
        .as_deref()
        .map(str::trim)
        .filter(|s| !s.is_empty() && *s != key);
    if let Some(parent_key) = parent {
        let et = "evolved_from";
        match s.store.memory_link(&key, parent_key, et, 0.9).await {
            Ok(_) => {
                lineage_edge = Some(et.to_string());
            }
            Err(_) => {
                lineage_ok = false;
            }
        }
    }

    Ok(Json(json!({
        "ok":   true,
        "key":  key,
        "kind": kind,
        "edge": edge_type,
        "lineage_ok": lineage_ok,
        "lineage_edge": lineage_edge,
    })))
}

// ── Reports layer (C/A6 ↔ HTML reports back-link) ────────────────────────
//
// `dream promote --html` writes audit reports keyed to memory keys; the
// reports link forward to Palace via `?focus=KEY`. These endpoints close
// the loop the other way: Palace's side panel can list reports that
// mention the focused key, and a path-traversal-safe handler serves the
// HTML files directly so the back-link doesn't rely on file:// URLs.

#[derive(Deserialize)]
struct ReportsQuery {
    key: String,
}

/// Maximum number of bytes scanned per report when checking for key
/// occurrences. Reports stay well under this in practice (~40KB), but
/// the cap protects against accidentally pointing `--reports-dir` at a
/// folder of arbitrary HTML.
const REPORT_SCAN_BYTES: u64 = 1_048_576; // 1 MiB

/// Maximum number of recent reports to enumerate per request. Keeps the
/// side-panel list short and bounds the I/O cost of each call.
const REPORTS_PER_KEY_LIMIT: usize = 8;

/// `GET /api/reports?key=KEY` — list reports in `reports_dir` that
/// mention the given memory key, sorted newest first. Returns
/// `{ items: [{ filename, mtime, mentions, label }] }`.
async fn api_reports(
    State(s): State<AppState>,
    Query(q): Query<ReportsQuery>,
) -> Result<Json<Value>, (StatusCode, String)> {
    let dir = match &s.reports_dir {
        Some(p) => p,
        None => return Ok(Json(json!({"items": []}))),
    };
    let entries = match fs::read_dir(dir) {
        Ok(e) => e,
        Err(_) => return Ok(Json(json!({"items": []}))),
    };

    let mut hits: Vec<(String, u64, usize)> = Vec::new();
    for entry in entries.flatten() {
        let name = match entry.file_name().into_string() {
            Ok(n) => n,
            Err(_) => continue,
        };
        if !name.ends_with(".html") {
            continue;
        }
        let path = entry.path();
        let meta = match entry.metadata() {
            Ok(m) => m,
            Err(_) => continue,
        };
        if !meta.is_file() || meta.len() > REPORT_SCAN_BYTES {
            continue;
        }
        let content = match fs::read_to_string(&path) {
            Ok(c) => c,
            Err(_) => continue,
        };
        let mentions = content.matches(q.key.as_str()).count();
        if mentions == 0 {
            continue;
        }
        let mtime = meta
            .modified()
            .ok()
            .and_then(|t| t.duration_since(UNIX_EPOCH).ok())
            .map(|d| d.as_secs())
            .unwrap_or(0);
        hits.push((name, mtime, mentions));
    }
    // Newest first; truncate to the per-key limit.
    hits.sort_by(|a, b| b.1.cmp(&a.1));
    hits.truncate(REPORTS_PER_KEY_LIMIT);

    let items: Vec<Value> = hits
        .into_iter()
        .map(|(filename, mtime, mentions)| {
            // Strip extension and the standard `promote-` prefix to make
            // a compact label like "2026-05-10". Other filenames pass
            // through with just the extension dropped.
            let stem = filename.strip_suffix(".html").unwrap_or(&filename);
            let label = stem.strip_prefix("promote-").unwrap_or(stem).to_string();
            json!({
                "filename": filename,
                "mtime":    mtime,
                "mentions": mentions,
                "label":    label,
            })
        })
        .collect();

    Ok(Json(json!({"items": items})))
}

/// `GET /reports/:filename` — serve a single HTML report by filename.
/// Path-traversal safe: rejects any name containing `/`, `\`, `..`, or
/// not ending in `.html`.
async fn serve_report(
    State(s): State<AppState>,
    Path(filename): Path<String>,
) -> Result<impl IntoResponse, (StatusCode, String)> {
    let dir = s
        .reports_dir
        .as_ref()
        .ok_or((StatusCode::NOT_FOUND, "reports layer disabled".to_string()))?;
    if !is_safe_report_filename(&filename) {
        return Err((StatusCode::BAD_REQUEST, "invalid filename".to_string()));
    }
    let path = dir.join(&filename);
    let body = fs::read(&path).map_err(|_| {
        (
            StatusCode::NOT_FOUND,
            format!("report not found: {filename}"),
        )
    })?;
    Ok((
        [(axum::http::header::CONTENT_TYPE, "text/html; charset=utf-8")],
        body,
    ))
}

fn is_safe_report_filename(name: &str) -> bool {
    if !name.ends_with(".html") {
        return false;
    }
    if name.contains('/') || name.contains('\\') || name.contains("..") {
        return false;
    }
    // Restrict the rest of the alphabet to a sane subset — file names we
    // generate are date-keyed (`promote-YYYY-MM-DD.html`) but allow tags
    // and underscores for future report kinds.
    name.chars()
        .all(|c| c.is_ascii_alphanumeric() || c == '-' || c == '_' || c == '.')
}

// ── Canvas chat endpoint (B-mode discussion with spawned Claude Code) ────
//
// Each chat round trip spawns a fresh `claude -p "<full prompt>"` process,
// captures stdout, returns it. Stateless on the server: full conversation
// history is rebuilt into the prompt every call (Anthropic chat history
// is the cheapest way to carry continuity without managing a persistent
// PTY session — that's P2/B M2 territory).
//
// Context auto-attached:
//   - Focused node's full content
//   - Top-N neighbors with snippets (cofires + annotates + supersedes +
//     summarizes + references — structural and attention edges, not
//     ephemeral coactivation)
//
// The spawned claude has full access to whatever MCP servers are configured
// in the user's `~/.claude/mcp.json` — meaning it can call memory_save /
// memory_link / dream_* directly when the user explicitly asks. We don't
// inject those tools here; the spawned session has them via Claude Code's
// own config.

#[derive(Deserialize)]
struct ChatMessage {
    role: String, // "user" | "assistant"
    content: String,
}

#[derive(Deserialize)]
struct CanvasChatPayload {
    focus_key: String,
    /// Conversation so far (excluding the new message). Frontend keeps
    /// this in canvasState and resends each round so we can be stateless.
    #[serde(default)]
    history: Vec<ChatMessage>,
    /// New user message.
    message: String,
    /// Per-spawn timeout in seconds. Default 90s — long enough for
    /// thinking + tool use, short enough that a stuck spawn doesn't
    /// block the canvas indefinitely.
    #[serde(default)]
    timeout_secs: Option<u64>,
}

const CANVAS_CHAT_NEIGHBOR_LIMIT: usize = 6;
const CANVAS_CHAT_SNIPPET_CHARS: usize = 280;
const CANVAS_CHAT_DEFAULT_TIMEOUT_SECS: u64 = 90;
const CANVAS_CHAT_MAX_TIMEOUT_SECS: u64 = 600;

async fn api_canvas_chat(
    State(s): State<AppState>,
    Json(p): Json<CanvasChatPayload>,
) -> Result<Json<Value>, (StatusCode, String)> {
    let focus = p.focus_key.trim();
    let user_msg = p.message.trim();
    if focus.is_empty() {
        return Err((StatusCode::BAD_REQUEST, "focus_key required".into()));
    }
    if user_msg.is_empty() {
        return Err((StatusCode::BAD_REQUEST, "message required".into()));
    }

    // Build the context block (focus node + neighbors). Best-effort: a
    // missing focus node still produces a usable prompt — the agent can
    // ask the user for context.
    let focus_block = build_focus_block(&s, focus).await;
    let neighbor_block = build_neighbor_block(&s, focus).await;
    let history_block = format_history(&p.history);

    let prompt = format!(
        "你正在 Palace 画布的 chat panel 里和用户讨论 memory 节点 `{focus}`。\n\
         你的目标是帮用户思考、提出连接、起草 working_doc 内容。\n\
         回复用中文，简洁直接，避免空泛。\n\
         如果用户想沉淀某段为 working_doc，提示他可以点 [→ copy to editor]。\n\
         如果用户消息里出现 `[image: /tmp/canvas-chat-attachments/...]` 标记（粘贴的图），\
         请用 Read 工具读取那个路径来看图，然后基于图的内容回答。\n\n\
         ## 当前焦点节点\n{focus_block}\n\n\
         ## 邻居节点（top {n} by edge weight）\n{neighbor_block}\n\n\
         ## 对话历史\n{history_block}\n\n\
         ## 用户最新消息\n{user_msg}\n",
        focus = focus,
        n = CANVAS_CHAT_NEIGHBOR_LIMIT,
        focus_block = focus_block,
        neighbor_block = neighbor_block,
        history_block = history_block,
        user_msg = user_msg,
    );

    let timeout = p
        .timeout_secs
        .unwrap_or(CANVAS_CHAT_DEFAULT_TIMEOUT_SECS)
        .min(CANVAS_CHAT_MAX_TIMEOUT_SECS);

    // Spawn `claude -p` with the prompt. Inherits palace's env so the
    // wrapper-injected ANTHROPIC_API_KEY (or whichever provider) carries
    // through. cwd = palace's cwd — Claude Code reads MCP config relative
    // to that, so it gets the same agent-bridge tools the user sees.
    let mut cmd = tokio::process::Command::new("claude");
    cmd.arg("-p").arg(&prompt);
    cmd.stdin(std::process::Stdio::null());
    cmd.stdout(std::process::Stdio::piped());
    cmd.stderr(std::process::Stdio::piped());

    let started = SystemTime::now();
    let child = cmd.spawn().map_err(|e| {
        (
            StatusCode::INTERNAL_SERVER_ERROR,
            format!("spawn claude: {e}"),
        )
    })?;

    let output = match tokio::time::timeout(
        std::time::Duration::from_secs(timeout),
        child.wait_with_output(),
    )
    .await
    {
        Ok(Ok(out)) => out,
        Ok(Err(e)) => {
            return Err((
                StatusCode::INTERNAL_SERVER_ERROR,
                format!("wait claude: {e}"),
            ));
        }
        Err(_elapsed) => {
            return Err((
                StatusCode::GATEWAY_TIMEOUT,
                format!("claude exceeded {timeout}s timeout"),
            ));
        }
    };

    let stdout = String::from_utf8_lossy(&output.stdout).into_owned();
    let stderr = String::from_utf8_lossy(&output.stderr).into_owned();
    let elapsed_ms = started.elapsed().map(|d| d.as_millis() as u64).unwrap_or(0);

    if !output.status.success() {
        // Surface stderr but truncated — don't leak huge logs to the
        // browser. Caller can repro via terminal if they want full output.
        let trimmed: String = stderr.chars().take(800).collect();
        return Err((
            StatusCode::BAD_GATEWAY,
            format!(
                "claude exited {:?} after {elapsed_ms}ms: {}",
                output.status.code(),
                trimmed
            ),
        ));
    }

    Ok(Json(json!({
        "ok":         true,
        "assistant":  stdout.trim_end(),
        "elapsed_ms": elapsed_ms,
        "stderr":     if stderr.is_empty() { Value::Null } else { Value::String(stderr) },
    })))
}

// ── Streaming canvas chat (P8) ──────────────────────────────────────────
//
// SSE counterpart of `api_canvas_chat`. Spawns `claude -p
// --output-format=stream-json --verbose --include-partial-messages` and
// forwards `content_block_delta.text_delta.text` chunks as SSE events,
// so the canvas chat panel can render tokens as they arrive instead of
// waiting for the full response.
//
// SSE events emitted:
//   data: {"type":"delta","text":"..."}       — one token chunk
//   data: {"type":"done","elapsed_ms":N}      — process exited cleanly
//   data: {"type":"error","message":"..."}    — spawn / nonzero exit /
//                                                timeout / parse fail
//
// stream-json shape (relevant subset):
//   {"type":"stream_event","event":{"type":"content_block_delta",
//    "delta":{"type":"text_delta","text":"…"}}, …}
//   {"type":"result","subtype":"success", …}    final summary
//
// Failure handling: any spawn / process error becomes an SSE error event
// rather than an HTTP error response — the connection is already open,
// the client needs structured info to surface to the user.

async fn api_canvas_chat_stream(
    State(s): State<AppState>,
    Json(p): Json<CanvasChatPayload>,
) -> Sse<impl futures::Stream<Item = std::result::Result<SseEvent, std::convert::Infallible>>> {
    use futures::stream;
    use std::convert::Infallible;
    use tokio::io::{AsyncBufReadExt, BufReader};
    use tokio::sync::mpsc;

    let focus = p.focus_key.trim().to_string();
    let user_msg = p.message.trim().to_string();

    let (tx, rx) = mpsc::unbounded_channel::<SseEvent>();
    let send_err = |tx: &mpsc::UnboundedSender<SseEvent>, msg: String| {
        let _ =
            tx.send(SseEvent::default().data(json!({"type":"error","message":msg}).to_string()));
    };

    // Build the prompt now (uses State; can't move S into the spawn).
    // Empty inputs are flagged early but the actual error is sent from
    // inside the spawn so the SSE stream has a single return shape.
    let validation_err = if focus.is_empty() || user_msg.is_empty() {
        Some("focus_key + message required".to_string())
    } else {
        None
    };
    let focus_block = if validation_err.is_none() {
        build_focus_block(&s, &focus).await
    } else {
        String::new()
    };
    let neighbor_block = if validation_err.is_none() {
        build_neighbor_block(&s, &focus).await
    } else {
        String::new()
    };
    let history_block = format_history(&p.history);

    let prompt = format!(
        "你正在 Palace 画布的 chat panel 里和用户讨论 memory 节点 `{focus}`。\n\
         你的目标是帮用户思考、提出连接、起草 working_doc 内容。\n\
         回复用中文，简洁直接，避免空泛。\n\
         如果用户想沉淀某段为 working_doc，提示他可以点 [→ copy to editor]。\n\
         如果用户消息里出现 `[image: /tmp/canvas-chat-attachments/...]` 标记（粘贴的图），\
         请用 Read 工具读取那个路径来看图，然后基于图的内容回答。\n\n\
         ## 当前焦点节点\n{focus_block}\n\n\
         ## 邻居节点（top {n} by edge weight）\n{neighbor_block}\n\n\
         ## 对话历史\n{history_block}\n\n\
         ## 用户最新消息\n{user_msg}\n",
        focus = focus,
        n = CANVAS_CHAT_NEIGHBOR_LIMIT,
        focus_block = focus_block,
        neighbor_block = neighbor_block,
        history_block = history_block,
        user_msg = user_msg,
    );

    let timeout = p
        .timeout_secs
        .unwrap_or(CANVAS_CHAT_DEFAULT_TIMEOUT_SECS)
        .min(CANVAS_CHAT_MAX_TIMEOUT_SECS);

    // Spawn streaming claude in a background task; bg pipes parsed
    // deltas into `tx`. SSE response polls `rx` until the bg task
    // emits "done" or "error" and closes the channel.
    tokio::spawn(async move {
        let started = SystemTime::now();
        if let Some(msg) = validation_err {
            send_err(&tx, msg);
            let _ = tx
                .send(SseEvent::default().data(json!({"type":"done","elapsed_ms":0}).to_string()));
            return;
        }
        let mut cmd = tokio::process::Command::new("claude");
        cmd.arg("-p")
            .arg("--output-format=stream-json")
            .arg("--verbose")
            .arg("--include-partial-messages")
            .arg(&prompt);
        cmd.stdin(std::process::Stdio::null());
        cmd.stdout(std::process::Stdio::piped());
        cmd.stderr(std::process::Stdio::piped());
        let mut child = match cmd.spawn() {
            Ok(c) => c,
            Err(e) => {
                send_err(&tx, format!("spawn claude: {e}"));
                let _ = tx.send(
                    SseEvent::default().data(json!({"type":"done","elapsed_ms":0}).to_string()),
                );
                return;
            }
        };
        let stdout = match child.stdout.take() {
            Some(s) => s,
            None => {
                send_err(&tx, "no stdout pipe".to_string());
                let _ = tx.send(
                    SseEvent::default().data(json!({"type":"done","elapsed_ms":0}).to_string()),
                );
                return;
            }
        };

        let reader = BufReader::new(stdout);
        let mut lines = reader.lines();
        // Track each content_block index → kind (text / tool_use / thinking)
        // because content_block_stop arrives with only the index, not the
        // kind. We need the kind to decide whether to emit a tool_stop.
        let mut block_kind_by_index: std::collections::HashMap<i64, String> =
            std::collections::HashMap::new();
        let read_fut = async {
            while let Ok(Some(line)) = lines.next_line().await {
                if line.trim().is_empty() {
                    continue;
                }
                // Lossy parse — a malformed line is skipped rather than
                // killing the stream.
                let val: Value = match serde_json::from_str(&line) {
                    Ok(v) => v,
                    Err(_) => continue,
                };
                if val.get("type").and_then(|v| v.as_str()) != Some("stream_event") {
                    continue;
                }
                let event = match val.get("event") {
                    Some(e) => e,
                    None => continue,
                };
                let event_type = event.get("type").and_then(|v| v.as_str()).unwrap_or("");

                match event_type {
                    // Text token chunk — the bread-and-butter streaming event.
                    "content_block_delta" => {
                        let delta = match event.get("delta") {
                            Some(d) => d,
                            None => continue,
                        };
                        if delta.get("type").and_then(|v| v.as_str()) == Some("text_delta") {
                            if let Some(text) = delta.get("text").and_then(|v| v.as_str()) {
                                let _ = tx.send(
                                    SseEvent::default()
                                        .data(json!({"type":"delta","text":text}).to_string()),
                                );
                            }
                        } else if delta.get("type").and_then(|v| v.as_str())
                            == Some("input_json_delta")
                        {
                            // Tool args chunk — forward to client so the
                            // chip tooltip can accumulate the JSON args
                            // claude is sending to the tool.
                            if let (Some(idx), Some(chunk)) = (
                                event.get("index").and_then(|v| v.as_i64()),
                                delta.get("partial_json").and_then(|v| v.as_str()),
                            ) {
                                let _ = tx.send(
                                    SseEvent::default().data(
                                        json!({
                                            "type": "tool_args_delta",
                                            "index": idx,
                                            "chunk": chunk,
                                        })
                                        .to_string(),
                                    ),
                                );
                            }
                        }
                        // signature_delta etc. — silently skipped for v1;
                        // reasoning signature not surfaced to the chat panel.
                    }
                    // Block start — record kind by index; if it's a tool_use
                    // emit tool_start with the tool name + id so the client
                    // can render a chip.
                    "content_block_start" => {
                        let idx = match event.get("index").and_then(|v| v.as_i64()) {
                            Some(i) => i,
                            None => continue,
                        };
                        let cb = match event.get("content_block") {
                            Some(c) => c,
                            None => continue,
                        };
                        let kind = cb
                            .get("type")
                            .and_then(|v| v.as_str())
                            .unwrap_or("")
                            .to_string();
                        block_kind_by_index.insert(idx, kind.clone());
                        if kind == "tool_use" {
                            let name = cb
                                .get("name")
                                .and_then(|v| v.as_str())
                                .unwrap_or("")
                                .to_string();
                            let id = cb
                                .get("id")
                                .and_then(|v| v.as_str())
                                .unwrap_or("")
                                .to_string();
                            let _ = tx.send(
                                SseEvent::default().data(
                                    json!({
                                        "type": "tool_start",
                                        "index": idx,
                                        "name": name,
                                        "id": id,
                                    })
                                    .to_string(),
                                ),
                            );
                        }
                    }
                    // Block end — if it was a tool_use, emit tool_stop so
                    // the client flips the chip from "running" to "done".
                    "content_block_stop" => {
                        let idx = match event.get("index").and_then(|v| v.as_i64()) {
                            Some(i) => i,
                            None => continue,
                        };
                        if let Some(kind) = block_kind_by_index.get(&idx) {
                            if kind == "tool_use" {
                                let _ = tx.send(
                                    SseEvent::default()
                                        .data(json!({"type":"tool_stop","index":idx}).to_string()),
                                );
                            }
                        }
                    }
                    // message_start / message_delta / message_stop are
                    // currently ignored — the SSE done event fires on
                    // process exit (sub-thread) which is the simpler
                    // truth-of-completion signal.
                    _ => {}
                }
            }
        };

        let result = tokio::time::timeout(std::time::Duration::from_secs(timeout), async {
            read_fut.await;
            child.wait().await
        })
        .await;

        let elapsed_ms = started.elapsed().map(|d| d.as_millis() as u64).unwrap_or(0);
        match result {
            Ok(Ok(status)) if status.success() => {
                let _ = tx.send(
                    SseEvent::default()
                        .data(json!({"type":"done","elapsed_ms":elapsed_ms}).to_string()),
                );
            }
            Ok(Ok(status)) => {
                send_err(
                    &tx,
                    format!(
                        "claude exited code={:?} after {elapsed_ms}ms",
                        status.code()
                    ),
                );
                let _ = tx.send(
                    SseEvent::default()
                        .data(json!({"type":"done","elapsed_ms":elapsed_ms}).to_string()),
                );
            }
            Ok(Err(e)) => {
                send_err(&tx, format!("wait claude: {e}"));
                let _ = tx.send(
                    SseEvent::default()
                        .data(json!({"type":"done","elapsed_ms":elapsed_ms}).to_string()),
                );
            }
            Err(_elapsed) => {
                let _ = child.start_kill();
                send_err(&tx, format!("claude exceeded {timeout}s timeout"));
                let _ = tx.send(
                    SseEvent::default()
                        .data(json!({"type":"done","elapsed_ms":elapsed_ms}).to_string()),
                );
            }
        }
    });

    let stream = stream::unfold(rx, |mut rx| async move {
        rx.recv().await.map(|e| (Ok::<_, Infallible>(e), rx))
    });
    Sse::new(stream).keep_alive(KeepAlive::default())
}

async fn build_focus_block(s: &AppState, key: &str) -> String {
    // Try sqlite first.
    if let Ok(Some(m)) = s.store.memory_get(key).await {
        let tags = if m.tags.is_empty() {
            String::new()
        } else {
            format!("\ntags: {}", m.tags.join(", "))
        };
        return format!(
            "**{}** ({})  importance {:.2}{}\n\n{}",
            m.key, m.kind, m.importance, tags, m.content,
        );
    }
    // Markdown fallback — same lookup the side panel uses.
    if let Some(root) = &s.markdown_root {
        let path = root.join(format!("{key}.md"));
        if let Ok(body) = fs::read_to_string(&path) {
            let mm = parse_markdown_memory(key.to_string(), &body);
            return format!(
                "**{}** ({}, markdown)\n\n{}\n\n{}",
                mm.key, mm.kind, mm.description, mm.content,
            );
        }
    }
    format!("**{key}** — not found in store")
}

async fn build_neighbor_block(s: &AppState, key: &str) -> String {
    let nbrs = match s.store.memory_neighbors(key).await {
        Ok(v) => v,
        Err(_) => return "(no neighbors)".to_string(),
    };
    if nbrs.is_empty() {
        return "(no neighbors)".to_string();
    }
    // Filter to structural edges (skip ephemeral coactivation), sort by
    // weight desc, take top N.
    let mut filtered: Vec<_> = nbrs
        .into_iter()
        .filter(|e| !matches!(e.edge_type.as_str(), "coactivation"))
        .collect();
    filtered.sort_by(|a, b| {
        b.weight
            .partial_cmp(&a.weight)
            .unwrap_or(std::cmp::Ordering::Equal)
    });
    filtered.truncate(CANVAS_CHAT_NEIGHBOR_LIMIT);
    if filtered.is_empty() {
        return "(no structural neighbors)".to_string();
    }

    let mut out = String::new();
    for e in filtered {
        let other_key = if e.from_key == key {
            &e.to_key
        } else {
            &e.from_key
        };
        let snippet = neighbor_snippet(s, other_key).await;
        out.push_str(&format!(
            "- **{}** [{}, w={:.2}]: {}\n",
            other_key, e.edge_type, e.weight, snippet,
        ));
    }
    out
}

async fn neighbor_snippet(s: &AppState, key: &str) -> String {
    if let Ok(Some(m)) = s.store.memory_get(key).await {
        let preview: String = m
            .content
            .chars()
            .take(CANVAS_CHAT_SNIPPET_CHARS)
            .collect::<String>()
            .replace('\n', " ");
        if m.content.chars().count() > CANVAS_CHAT_SNIPPET_CHARS {
            return format!("{preview}…");
        }
        return preview;
    }
    if let Some(root) = &s.markdown_root {
        let path = root.join(format!("{key}.md"));
        if let Ok(body) = fs::read_to_string(&path) {
            let mm = parse_markdown_memory(key.to_string(), &body);
            let combined = if mm.description.is_empty() {
                mm.content
            } else {
                format!("{} — {}", mm.description, mm.content)
            };
            let preview: String = combined
                .chars()
                .take(CANVAS_CHAT_SNIPPET_CHARS)
                .collect::<String>()
                .replace('\n', " ");
            if combined.chars().count() > CANVAS_CHAT_SNIPPET_CHARS {
                return format!("{preview}…");
            }
            return preview;
        }
    }
    "(content unavailable)".to_string()
}

fn format_history(history: &[ChatMessage]) -> String {
    if history.is_empty() {
        return "(none — this is the first message)".to_string();
    }
    let mut out = String::new();
    for m in history {
        let label = if m.role == "user" {
            "USER"
        } else {
            "ASSISTANT"
        };
        out.push_str(&format!("**{}**: {}\n\n", label, m.content));
    }
    out
}

#[cfg(test)]
mod tests {
    use super::*;

    static ENV_LOCK: std::sync::Mutex<()> = std::sync::Mutex::new(());

    fn test_mem(key: &str, kind: &str, content: &str, tags: &[&str]) -> MemoryRecord {
        MemoryRecord {
            key: key.to_string(),
            kind: kind.to_string(),
            content: content.to_string(),
            tags: tags.iter().map(|tag| (*tag).to_string()).collect(),
            related_keys: Vec::new(),
            scope: None,
            created_at: 0,
            updated_at: 0,
            last_accessed_at: 0,
            access_count: 0,
            importance: 0.5,
            status: "active".to_string(),
            trigger_pattern: None,
            superseded_by: None,
        }
    }

    #[test]
    fn palace_region_for_memory_mirrors_atlas_tags_and_patterns() {
        let tagged = test_mem("curated_implicit_001", "context", "body", &["auto_curated"]);
        assert_eq!(palace_region_for_memory(&tagged), "auto-curated");

        let handoff = test_mem("daily_handoff", "session_handoff", "body", &[]);
        assert_eq!(palace_region_for_memory(&handoff), "session-handoffs");

        let keyed = test_mem("agent-bridge-palace-graph", "lesson", "body", &[]);
        assert_eq!(palace_region_for_memory(&keyed), "agent-bridge");
    }

    #[test]
    fn palace_orphan_preview_skips_blacklisted_orphans_and_targets() {
        let shared = "memory graph candidate preview health topology orphan repair signal explicit edge classification stable operator review alpha beta gamma";
        let source = test_mem("memory_orphan", "lesson", shared, &["memory"]);
        let anchor = test_mem(
            "memory_anchor",
            "lesson",
            "memory graph candidate preview health topology orphan repair signal explicit edge classification stable target beta gamma",
            &["memory"],
        );
        let blacklisted_target = test_mem(
            "memory_auto_target",
            "lesson",
            "memory graph candidate preview health topology orphan repair signal explicit edge classification stable target beta gamma",
            &["memory", "auto_curated"],
        );
        let blacklisted_source = test_mem(
            "curated_implicit_skip",
            "context",
            "memory graph candidate preview health topology orphan repair signal explicit edge classification stable target beta gamma",
            &["auto_curated"],
        );
        let all = vec![source, anchor, blacklisted_target, blacklisted_source];
        let keys_with_edges = HashSet::from(["memory_anchor".to_string()]);

        let preview =
            preview_palace_orphan_candidates(&all, &keys_with_edges, None, 0.85, 20, 10, 3);

        assert_eq!(preview.skipped_blacklisted_orphan, 2);
        assert_eq!(preview.would_link, 1);
        let row = preview
            .rows
            .iter()
            .find(|row| row.orphan.key == "memory_orphan")
            .expect("memory_orphan row");
        assert!(row.suggestions.iter().any(|s| s.key == "memory_anchor"));
        assert!(!row
            .suggestions
            .iter()
            .any(|s| s.key == "memory_auto_target"));
    }

    #[test]
    fn palace_orphan_preview_counts_existing_edge_source_skips() {
        let shared = "memory graph candidate preview health topology orphan repair signal explicit edge classification stable operator review alpha beta gamma";
        let linked_source = test_mem("memory_linked_source", "lesson", shared, &["memory"]);
        let orphan = test_mem("memory_orphan", "lesson", shared, &["memory"]);
        let linked_target = test_mem(
            "memory_linked_target",
            "lesson",
            "memory graph candidate preview health topology orphan repair signal explicit edge classification stable target beta gamma",
            &["memory"],
        );
        let all = vec![linked_source, orphan, linked_target];
        let keys_with_edges = HashSet::from([
            "memory_linked_source".to_string(),
            "memory_linked_target".to_string(),
        ]);

        let preview =
            preview_palace_orphan_candidates(&all, &keys_with_edges, None, 0.85, 20, 10, 3);

        assert_eq!(preview.examined, 3);
        assert_eq!(preview.skipped_existing_edges, 2);
        assert_eq!(preview.eligible_orphans, 1);
        assert_eq!(preview.would_link, 1);
    }

    #[test]
    fn palace_store_neighbor_summary_counts_edges_outside_visible_graph() {
        let edges = vec![
            ab_store::MemoryEdge {
                from_key: "memory_orphan".to_string(),
                to_key: "memory_anchor".to_string(),
                edge_type: "relates".to_string(),
                weight: 1.0,
            },
            ab_store::MemoryEdge {
                from_key: "memory_citation".to_string(),
                to_key: "memory_orphan".to_string(),
                edge_type: "coactivation".to_string(),
                weight: 0.42,
            },
        ];

        let summary = palace_store_neighbor_summary_value("memory_orphan", &edges);

        assert_eq!(summary["read_only"], json!(true));
        assert_eq!(summary["total"], json!(2));
        assert_eq!(summary["structural"], json!(1));
        assert_eq!(summary["coactivation"], json!(1));
        assert_eq!(summary["rows"][0]["peer_key"], json!("memory_anchor"));
        assert_eq!(summary["rows"][0]["edge_type"], json!("relates"));
        assert_eq!(summary["rows"][1]["peer_key"], json!("memory_citation"));
    }

    #[test]
    fn palace_orphan_decision_inbox_merges_latest_pair_decision_without_memory_write() {
        let pair = PalaceOrphanCandidatePair {
            orphan_key: "memory_orphan".to_string(),
            candidate_key: "memory_anchor".to_string(),
        };
        let decisions = vec![
            palace_orphan_candidate_decision_record_for_time(
                &pair,
                "approve",
                Some("alice"),
                Some("looks related"),
                10,
            )
            .expect("approve record"),
            palace_orphan_candidate_decision_record_for_time(
                &pair,
                "defer",
                Some("bob"),
                Some("needs another look"),
                20,
            )
            .expect("defer record"),
        ];

        let inbox = palace_orphan_candidate_decision_inbox_for_pairs(&[pair], &decisions);

        assert_eq!(
            inbox["schema"],
            "agent_bridge.palace.orphan_candidate_decision_inbox.v0"
        );
        assert_eq!(inbox["writes_memory"], json!(false));
        assert_eq!(inbox["auto_apply_allowed"], json!(false));
        assert_eq!(inbox["candidate_count"], json!(1));
        assert_eq!(inbox["deferred_count"], json!(1));
        assert_eq!(inbox["approved_count"], json!(0));
        assert_eq!(inbox["candidates"][0]["decision"], json!("defer"));
        assert_eq!(inbox["candidates"][0]["reviewer"], json!("bob"));
    }

    #[test]
    fn palace_orphan_decision_jsonl_is_private_append_only_and_schema_filtered() {
        let dir = tempfile::tempdir().expect("tempdir");
        let path = dir.path().join("review").join("decisions.jsonl");
        let pair = PalaceOrphanCandidatePair {
            orphan_key: "memory_orphan".to_string(),
            candidate_key: "memory_anchor".to_string(),
        };
        let approve = palace_orphan_candidate_decision_record_for_time(
            &pair,
            "approve",
            Some("alice"),
            None,
            10,
        )
        .expect("approve");
        let reject = palace_orphan_candidate_decision_record_for_time(
            &pair,
            "reject",
            Some("bob"),
            Some("not the same thing"),
            20,
        )
        .expect("reject");

        append_palace_orphan_candidate_decision(&path, &approve).expect("append approve");
        append_palace_orphan_candidate_decision(
            &path,
            &json!({
                "schema": "other.schema",
                "decision": "approve"
            }),
        )
        .expect("append ignored schema");
        append_palace_orphan_candidate_decision(&path, &reject).expect("append reject");

        let loaded = load_palace_orphan_candidate_decisions(&path).expect("load decisions");

        assert_eq!(loaded.len(), 2);
        assert_eq!(loaded[0]["decision"], json!("approve"));
        assert_eq!(loaded[1]["decision"], json!("reject"));
        assert_eq!(loaded[1]["writes_edges"], json!(false));
        #[cfg(unix)]
        {
            use std::os::unix::fs::PermissionsExt;
            let file_mode = std::fs::metadata(&path).unwrap().permissions().mode() & 0o777;
            let dir_mode = std::fs::metadata(path.parent().unwrap())
                .unwrap()
                .permissions()
                .mode()
                & 0o777;
            assert_eq!(file_mode, 0o600);
            assert_eq!(dir_mode, 0o700);
        }
    }

    #[test]
    fn palace_orphan_candidate_decisions_default_to_private_home_dir() {
        let _guard = ENV_LOCK.lock().expect("env lock");
        let home_dir = tempfile::tempdir().expect("home tempdir");
        let old_home = std::env::var_os("HOME");
        let old_review_dir = std::env::var_os("AB_PALACE_REVIEW_DIR");
        let old_decisions = std::env::var_os("AB_PALACE_ORPHAN_CANDIDATE_DECISIONS");

        std::env::set_var("HOME", home_dir.path());
        std::env::remove_var("AB_PALACE_REVIEW_DIR");
        std::env::remove_var("AB_PALACE_ORPHAN_CANDIDATE_DECISIONS");

        let path = default_palace_orphan_candidate_decisions_path();
        let expected = home_dir
            .path()
            .join(".agent-bridge-private")
            .join("palace-review")
            .join("orphan-candidate-decisions.jsonl");

        match old_home {
            Some(value) => std::env::set_var("HOME", value),
            None => std::env::remove_var("HOME"),
        }
        match old_review_dir {
            Some(value) => std::env::set_var("AB_PALACE_REVIEW_DIR", value),
            None => std::env::remove_var("AB_PALACE_REVIEW_DIR"),
        }
        match old_decisions {
            Some(value) => std::env::set_var("AB_PALACE_ORPHAN_CANDIDATE_DECISIONS", value),
            None => std::env::remove_var("AB_PALACE_ORPHAN_CANDIDATE_DECISIONS"),
        }

        assert_eq!(path, expected);
    }

    #[test]
    fn palace_orphan_candidate_decisions_set_private_home_root_permissions() {
        let _guard = ENV_LOCK.lock().expect("env lock");
        let home_dir = tempfile::tempdir().expect("home tempdir");
        let old_home = std::env::var_os("HOME");
        let old_decisions = std::env::var_os("AB_PALACE_ORPHAN_CANDIDATE_DECISIONS");

        std::env::set_var("HOME", home_dir.path());
        std::env::remove_var("AB_PALACE_ORPHAN_CANDIDATE_DECISIONS");

        let path = default_palace_orphan_candidate_decisions_path();
        let pair = PalaceOrphanCandidatePair {
            orphan_key: "memory_orphan".to_string(),
            candidate_key: "memory_anchor".to_string(),
        };
        let approve = palace_orphan_candidate_decision_record_for_time(
            &pair,
            "approve",
            Some("alice"),
            None,
            30,
        )
        .expect("approve");
        append_palace_orphan_candidate_decision(&path, &approve).expect("append decision");

        match old_home {
            Some(value) => std::env::set_var("HOME", value),
            None => std::env::remove_var("HOME"),
        }
        match old_decisions {
            Some(value) => std::env::set_var("AB_PALACE_ORPHAN_CANDIDATE_DECISIONS", value),
            None => std::env::remove_var("AB_PALACE_ORPHAN_CANDIDATE_DECISIONS"),
        }

        #[cfg(unix)]
        {
            use std::os::unix::fs::PermissionsExt;
            let private_root = home_dir.path().join(".agent-bridge-private");
            let root_mode = std::fs::metadata(private_root)
                .unwrap()
                .permissions()
                .mode()
                & 0o777;
            let review_mode = std::fs::metadata(path.parent().unwrap())
                .unwrap()
                .permissions()
                .mode()
                & 0o777;
            let file_mode = std::fs::metadata(&path).unwrap().permissions().mode() & 0o777;
            assert_eq!(root_mode, 0o700);
            assert_eq!(review_mode, 0o700);
            assert_eq!(file_mode, 0o600);
        }
    }

    #[test]
    fn palace_orphan_approved_plan_only_includes_latest_approved_pairs() {
        let approved = PalaceOrphanCandidatePair {
            orphan_key: "memory_orphan".to_string(),
            candidate_key: "memory_anchor".to_string(),
        };
        let rejected = PalaceOrphanCandidatePair {
            orphan_key: "memory_rejected".to_string(),
            candidate_key: "memory_other_anchor".to_string(),
        };
        let pairs = vec![approved.clone(), rejected.clone()];
        let decisions = vec![
            palace_orphan_candidate_decision_record_for_time(
                &approved,
                "defer",
                Some("alice"),
                None,
                10,
            )
            .expect("initial defer"),
            palace_orphan_candidate_decision_record_for_time(
                &approved,
                "approve",
                Some("bob"),
                Some("human checked"),
                20,
            )
            .expect("latest approve"),
            palace_orphan_candidate_decision_record_for_time(
                &rejected,
                "reject",
                Some("carol"),
                None,
                30,
            )
            .expect("reject"),
        ];
        let inbox = palace_orphan_candidate_decision_inbox_for_pairs(&pairs, &decisions);

        let plan = palace_orphan_approved_link_plan_for_inbox(&inbox);

        assert_eq!(
            plan["schema"],
            "agent_bridge.palace.orphan_approved_link_plan.v0"
        );
        assert_eq!(plan["read_only"], json!(true));
        assert_eq!(plan["writes_memory"], json!(false));
        assert_eq!(plan["writes_edges"], json!(false));
        assert_eq!(plan["auto_apply_allowed"], json!(false));
        assert_eq!(plan["approved_pair_count"], json!(1));
        assert_eq!(plan["links"][0]["orphan_key"], json!("memory_orphan"));
        assert_eq!(plan["links"][0]["candidate_key"], json!("memory_anchor"));
        assert_eq!(plan["links"][0]["reviewer"], json!("bob"));
        assert_eq!(plan["links"][0]["note"], json!("human checked"));
    }

    #[test]
    fn palace_orphan_approved_plan_is_scoped_to_current_preview_pairs() {
        let preview = PalaceOrphanCandidatePreview {
            rows: vec![PalaceOrphanCandidatePreviewRow {
                orphan: test_mem("memory_orphan", "lesson", "body", &[]),
                suggestions: vec![PalaceLinkSuggestion {
                    key: "memory_anchor".to_string(),
                    kind: "lesson".to_string(),
                    confidence: 1.0,
                    reason: "tag_overlap".to_string(),
                    scope: None,
                    scope_relation: "same_scope",
                    preview: "anchor".to_string(),
                }],
            }],
            ..PalaceOrphanCandidatePreview::default()
        };
        let visible_pair = PalaceOrphanCandidatePair {
            orphan_key: "memory_orphan".to_string(),
            candidate_key: "memory_anchor".to_string(),
        };
        let stale_pair = PalaceOrphanCandidatePair {
            orphan_key: "old_orphan".to_string(),
            candidate_key: "old_anchor".to_string(),
        };
        let decisions = vec![
            palace_orphan_candidate_decision_record_for_time(
                &visible_pair,
                "approve",
                Some("alice"),
                None,
                10,
            )
            .expect("visible approve"),
            palace_orphan_candidate_decision_record_for_time(
                &stale_pair,
                "approve",
                Some("bob"),
                None,
                20,
            )
            .expect("stale approve"),
        ];

        let plan = palace_orphan_approved_link_plan_for_preview(&preview, &decisions);

        assert_eq!(plan["approved_pair_count"], json!(1));
        assert_eq!(plan["links"][0]["orphan_key"], json!("memory_orphan"));
        assert_eq!(plan["links"][0]["candidate_key"], json!("memory_anchor"));
        assert_eq!(plan["links"][0]["reviewer"], json!("alice"));
    }

    #[test]
    fn palace_orphan_approved_plan_marks_small_same_scope_safe_batch() {
        let preview = PalaceOrphanCandidatePreview {
            rows: vec![
                PalaceOrphanCandidatePreviewRow {
                    orphan: test_mem("safe_orphan", "lesson", "body", &[]),
                    suggestions: vec![PalaceLinkSuggestion {
                        key: "safe_anchor".to_string(),
                        kind: "lesson".to_string(),
                        confidence: 0.95,
                        reason: "tag_overlap+content_overlap".to_string(),
                        scope: Some("project:/Data/CascadeProjects/agent-bridge".to_string()),
                        scope_relation: "same_scope",
                        preview: "safe anchor".to_string(),
                    }],
                },
                PalaceOrphanCandidatePreviewRow {
                    orphan: test_mem("cross_orphan", "lesson", "body", &[]),
                    suggestions: vec![PalaceLinkSuggestion {
                        key: "cross_anchor".to_string(),
                        kind: "lesson".to_string(),
                        confidence: 0.99,
                        reason: "content_overlap".to_string(),
                        scope: Some("project:/tmp/other".to_string()),
                        scope_relation: "cross_scope",
                        preview: "cross anchor".to_string(),
                    }],
                },
                PalaceOrphanCandidatePreviewRow {
                    orphan: test_mem("low_orphan", "lesson", "body", &[]),
                    suggestions: vec![PalaceLinkSuggestion {
                        key: "low_anchor".to_string(),
                        kind: "lesson".to_string(),
                        confidence: 0.70,
                        reason: "tag_overlap".to_string(),
                        scope: Some("project:/Data/CascadeProjects/agent-bridge".to_string()),
                        scope_relation: "same_scope",
                        preview: "low anchor".to_string(),
                    }],
                },
            ],
            ..PalaceOrphanCandidatePreview::default()
        };
        let pairs = [
            PalaceOrphanCandidatePair {
                orphan_key: "safe_orphan".to_string(),
                candidate_key: "safe_anchor".to_string(),
            },
            PalaceOrphanCandidatePair {
                orphan_key: "cross_orphan".to_string(),
                candidate_key: "cross_anchor".to_string(),
            },
            PalaceOrphanCandidatePair {
                orphan_key: "low_orphan".to_string(),
                candidate_key: "low_anchor".to_string(),
            },
        ];
        let decisions = pairs
            .iter()
            .enumerate()
            .map(|(idx, pair)| {
                palace_orphan_candidate_decision_record_for_time(
                    pair,
                    "approve",
                    Some("codex-test"),
                    Some("reviewed"),
                    100 + idx as u64,
                )
                .expect("approve")
            })
            .collect::<Vec<_>>();

        let plan = palace_orphan_approved_link_plan_for_preview(&preview, &decisions);

        assert_eq!(plan["approved_pair_count"], json!(3));
        assert_eq!(
            plan["safe_batch"]["schema"],
            json!("agent_bridge.palace.orphan_safe_batch.v0")
        );
        assert_eq!(plan["safe_batch"]["read_only"], json!(true));
        assert_eq!(plan["safe_batch"]["writes_edges"], json!(false));
        assert_eq!(plan["safe_batch"]["auto_apply_allowed"], json!(false));
        assert_eq!(plan["safe_batch"]["limit"], json!(3));
        assert_eq!(plan["safe_batch"]["eligible_count"], json!(1));
        assert_eq!(plan["safe_batch"]["blocked_count"], json!(2));
        assert_eq!(plan["safe_batch"]["min_confidence"], json!(0.85));
        assert_eq!(
            plan["safe_batch"]["required_scope_relation"],
            json!("same_scope")
        );
        assert_eq!(
            plan["safe_batch"]["links"][0]["orphan_key"],
            json!("safe_orphan")
        );
        assert_eq!(plan["safe_batch"]["links"][0]["confidence"], json!(0.95));
        assert_eq!(
            plan["safe_batch"]["blocked"][0]["reason"],
            json!("scope_relation_not_safe")
        );
        assert_eq!(
            plan["safe_batch"]["blocked"][1]["reason"],
            json!("confidence_below_safe_threshold")
        );
    }

    #[test]
    fn palace_review_artifact_contract_is_read_only_and_evidence_backed() {
        let candidate_review = json!({
            "read_only": true,
            "review": {
                "candidate_count": 3,
                "pending_count": 1,
                "approved_count": 2,
                "rejected_count": 0,
                "deferred_count": 0,
                "writes_memory": false,
                "writes_edges": false,
                "auto_apply_allowed": false
            },
            "rows": [{
                "orphan": "memory_orphan",
                "candidates": [{
                    "key": "memory_anchor",
                    "confidence": 0.93,
                    "review": {
                        "decision": "approve"
                    }
                }]
            }]
        });
        let approved_plan = json!({
            "schema": "agent_bridge.palace.orphan_approved_link_plan.v0",
            "read_only": true,
            "approved_pair_count": 2,
            "writes_memory": false,
            "writes_edges": false,
            "auto_apply_allowed": false,
            "safe_batch": {
                "schema": "agent_bridge.palace.orphan_safe_batch.v0",
                "read_only": true,
                "eligible_count": 2,
                "blocked_count": 0,
                "writes_memory": false,
                "writes_edges": false,
                "auto_apply_allowed": false,
                "links": [{
                    "pair_id": "memory_orphan -> memory_anchor",
                    "orphan_key": "memory_orphan",
                    "candidate_key": "memory_anchor"
                }],
                "blocked": []
            }
        });
        let apply_records = vec![
            json!({
                "schema": "agent_bridge.palace.orphan_approved_link_apply_audit.v0",
                "generated_at_unix": 20,
                "status": "applied",
                "dry_run": false,
                "applied_count": 2,
                "failed_count": 0,
                "skipped_count": 0
            }),
            json!({
                "schema": "agent_bridge.palace.orphan_approved_link_apply_audit.v0",
                "generated_at_unix": 10,
                "status": "dry_run",
                "dry_run": true,
                "applied_count": 0,
                "failed_count": 0,
                "skipped_count": 0
            }),
        ];
        let verification_rows = vec![json!({
            "from_key": "memory_orphan",
            "to_key": "memory_anchor",
            "edge_type": "relates",
            "weight": 1.0
        })];

        let artifact = palace_review_artifact_for_sources(
            Some("memory-graph"),
            0.85,
            50,
            12,
            3,
            &candidate_review,
            &approved_plan,
            &apply_records,
            &verification_rows,
        );

        assert_eq!(
            artifact["schema"],
            json!("agent_bridge.palace.review_artifact.v0")
        );
        assert_eq!(artifact["artifact_kind"], json!("palace_review_packet"));
        assert_eq!(artifact["read_only"], json!(true));
        assert_eq!(artifact["writes_memory"], json!(false));
        assert_eq!(artifact["writes_edges"], json!(false));
        assert_eq!(artifact["auto_apply_allowed"], json!(false));
        assert_eq!(artifact["region"], json!("memory-graph"));
        assert_eq!(artifact["summary"]["candidate_count"], json!(3));
        assert_eq!(artifact["summary"]["pending_candidate_count"], json!(1));
        assert_eq!(artifact["summary"]["approved_pair_count"], json!(2));
        assert_eq!(artifact["summary"]["safe_batch_eligible_count"], json!(2));
        assert_eq!(artifact["summary"]["safe_batch_blocked_count"], json!(0));
        assert_eq!(artifact["summary"]["recent_apply_audit_count"], json!(2));
        assert_eq!(artifact["summary"]["verified_edge_count"], json!(1));
        assert_eq!(
            artifact["sections"]["candidate_review"]["review"]["approved_count"],
            json!(2)
        );
        assert_eq!(
            artifact["sections"]["safe_batch"]["links"][0]["pair_id"],
            json!("memory_orphan -> memory_anchor")
        );
        assert_eq!(
            artifact["sections"]["apply_audit"]["records"][0]["generated_at_unix"],
            json!(20)
        );
        assert_eq!(
            artifact["sections"]["verification_evidence"]["rows"][0]["from_key"],
            json!("memory_orphan")
        );
    }

    #[test]
    fn palace_materialization_review_artifact_route_loads_read_only_packet_fixture() {
        let _guard = ENV_LOCK.lock().expect("env lock");
        let dir = tempfile::tempdir().expect("tempdir");
        let old_packet = std::env::var_os("AB_PALACE_MATERIALIZATION_REVIEW_PACKET_JSON");
        let packet_path = dir.path().join("materialization-review-packet.json");
        std::env::set_var("AB_PALACE_MATERIALIZATION_REVIEW_PACKET_JSON", &packet_path);
        std::fs::write(
            &packet_path,
            serde_json::to_vec_pretty(&json!({
                "schema": "agent_bridge.biocortex_retrieval.materialization_review_packet.v0",
                "generated_at": "2026-06-20T00:00:00Z",
                "purpose": "Read-only materialization review packet for human review; this is not approval state.",
                "review_state": "needs_human_review",
                "approval_state": "not_approved",
                "default_decision": "keep_preview_only",
                "read_only": true,
                "writes_memory": false,
                "writes_edges": false,
                "changes_search_order": false,
                "can_change_retrieval_order": false,
                "approval_writes_allowed": false,
                "can_materialize_edges": false,
                "input_contract": {
                    "raw_queries_included": false,
                    "raw_relevant_keys_included": false,
                    "content_included": false,
                    "query_cases_included": false
                },
                "packet_source": {
                    "generator": "biocortex_relevance_lift_fixture_eval",
                    "fixture_path": "docs/design/fixtures/memory-biocortex-relevance-lift-missing-graph-cases-2026-06-20.json",
                    "fixture_schema": "agent_bridge.biocortex_retrieval.fixture.v0",
                    "query_case_count": 1
                },
                "summary": {
                    "preview_case_count": 1,
                    "preview_candidate_count": 1,
                    "reason_packet_selected_edge_count": 1,
                    "reason_packet_relevant_edge_count": 1,
                    "reason_packet_blocked_packet_count": 0,
                    "reason_packet_blocked_shadow_count": 0
                },
                "review_questions": [
                    "Does the reason packet justify the proposed edge?",
                    "Do the rank movements support keeping this candidate in preview-only review?",
                    "Should this candidate remain non-materialized until a separate write path is explicitly approved?"
                ],
                "candidates": [{
                    "case_index": 15,
                    "class_label": "missing_graph_moderate_case_15",
                    "baseline_fts_rank_observed": 4,
                    "review_intent": "candidate-present but no direct explicit candidate graph edge",
                    "candidate_source": "reason_packet",
                    "gate": "explicit_related_keys",
                    "from_key": "from_a",
                    "to_key": "to_b",
                    "edge_type": "relates",
                    "reason_kind": "explicit_related_keys",
                    "rationale": "shared review artifact context",
                    "shadow_aligned": true,
                    "baseline_top3": ["one", "two", "three"],
                    "preview_top3": ["one", "from_a", "to_b"],
                    "baseline_from_rank": 3,
                    "preview_from_rank": 1,
                    "baseline_to_rank": 4,
                    "preview_to_rank": 3,
                    "preview_order_changed": true,
                    "blend_coverage": 0.2,
                    "writes_memory": false,
                    "changes_search_order": false
                }]
            }))
            .expect("serialize packet fixture"),
        )
        .expect("write packet fixture");

        let rt = tokio::runtime::Builder::new_current_thread()
            .enable_all()
            .build()
            .expect("runtime");
        rt.block_on(async {
            let db_path = dir.path().join("state.db");
            let store = Arc::new(
                ab_store::SqliteStore::open(&db_path)
                    .await
                    .expect("open sqlite store"),
            );
            let state = AppState {
                store,
                markdown_root: None,
                reports_dir: None,
                recent_clicks: Arc::new(Mutex::new(VecDeque::with_capacity(CLICK_WINDOW))),
            };

            let Json(artifact) = api_materialization_review_artifact(State(state))
                .await
                .expect("materialization review artifact");

            assert_eq!(
                artifact["schema"],
                json!("agent_bridge.palace.materialization_review_artifact.v0")
            );
            assert_eq!(
                artifact["artifact_kind"],
                json!("materialization_review_packet")
            );
            assert_eq!(artifact["read_only"], json!(true));
            assert_eq!(artifact["writes_memory"], json!(false));
            assert_eq!(artifact["writes_edges"], json!(false));
            assert_eq!(artifact["changes_search_order"], json!(false));
            assert_eq!(artifact["can_change_retrieval_order"], json!(false));
            assert_eq!(artifact["approval_writes_allowed"], json!(false));
            assert_eq!(artifact["can_materialize_edges"], json!(false));
            assert_eq!(
                artifact["source"]["packet_path"],
                json!(packet_path.display().to_string())
            );
            assert_eq!(artifact["summary"]["preview_case_count"], json!(1));
            assert_eq!(artifact["summary"]["preview_candidate_count"], json!(1));
            assert_eq!(
                artifact["questions"][0],
                json!("Does the reason packet justify the proposed edge?")
            );
            assert_eq!(artifact["candidates"][0]["from_key"], json!("from_a"));
            assert_eq!(artifact["candidates"][0]["to_key"], json!("to_b"));
            assert_eq!(artifact["candidates"][0]["writes_memory"], json!(false));
        });

        match old_packet {
            Some(value) => std::env::set_var("AB_PALACE_MATERIALIZATION_REVIEW_PACKET_JSON", value),
            None => std::env::remove_var("AB_PALACE_MATERIALIZATION_REVIEW_PACKET_JSON"),
        }
    }

    #[test]
    fn palace_materialization_review_artifact_route_uses_embedded_default_without_repo_cwd() {
        let _guard = ENV_LOCK.lock().expect("env lock");
        let dir = tempfile::tempdir().expect("tempdir");
        let old_packet = std::env::var_os("AB_PALACE_MATERIALIZATION_REVIEW_PACKET_JSON");
        let old_cwd = std::env::current_dir().expect("current dir");

        std::env::remove_var("AB_PALACE_MATERIALIZATION_REVIEW_PACKET_JSON");
        std::env::set_current_dir(dir.path()).expect("set temp cwd");

        let rt = tokio::runtime::Builder::new_current_thread()
            .enable_all()
            .build()
            .expect("runtime");
        let artifact_result = rt.block_on(async {
            let db_path = dir.path().join("state.db");
            let store = Arc::new(
                ab_store::SqliteStore::open(&db_path)
                    .await
                    .expect("open sqlite store"),
            );
            let state = AppState {
                store,
                markdown_root: None,
                reports_dir: None,
                recent_clicks: Arc::new(Mutex::new(VecDeque::with_capacity(CLICK_WINDOW))),
            };

            api_materialization_review_artifact(State(state))
                .await
                .map(|Json(artifact)| artifact)
        });

        std::env::set_current_dir(&old_cwd).expect("restore cwd");
        match old_packet {
            Some(value) => std::env::set_var("AB_PALACE_MATERIALIZATION_REVIEW_PACKET_JSON", value),
            None => std::env::remove_var("AB_PALACE_MATERIALIZATION_REVIEW_PACKET_JSON"),
        }

        let artifact = artifact_result.expect("materialization review artifact");
        assert_eq!(
            artifact["schema"],
            json!("agent_bridge.palace.materialization_review_artifact.v0")
        );
        assert_eq!(artifact["read_only"], json!(true));
        assert_eq!(artifact["writes_memory"], json!(false));
        assert_eq!(
            artifact["source"]["packet_path"],
            json!(DEFAULT_PALACE_MATERIALIZATION_REVIEW_PACKET_JSON)
        );
        assert_eq!(
            artifact["source"]["packet_schema"],
            json!("agent_bridge.biocortex_retrieval.materialization_review_packet.v0")
        );
    }

    #[test]
    fn palace_materialization_review_artifact_surfaces_decision_inbox_and_dry_run_plan() {
        let _guard = ENV_LOCK.lock().expect("env lock");
        let dir = tempfile::tempdir().expect("tempdir");
        let old_packet = std::env::var_os("AB_PALACE_MATERIALIZATION_REVIEW_PACKET_JSON");
        let old_decisions = std::env::var_os("AB_PALACE_MATERIALIZATION_REVIEW_DECISIONS");
        let packet_path = dir.path().join("materialization-review-packet.json");
        let decisions_path = dir.path().join("materialization-review-decisions.jsonl");
        std::env::set_var("AB_PALACE_MATERIALIZATION_REVIEW_PACKET_JSON", &packet_path);
        std::env::set_var(
            "AB_PALACE_MATERIALIZATION_REVIEW_DECISIONS",
            &decisions_path,
        );
        std::fs::write(
            &packet_path,
            serde_json::to_vec_pretty(&json!({
                "schema": "agent_bridge.biocortex_retrieval.materialization_review_packet.v0",
                "review_state": "needs_human_review",
                "approval_state": "not_approved",
                "default_decision": "keep_preview_only",
                "read_only": true,
                "writes_memory": false,
                "writes_edges": false,
                "changes_search_order": false,
                "can_change_retrieval_order": false,
                "approval_writes_allowed": false,
                "can_materialize_edges": false,
                "summary": {
                    "preview_case_count": 1,
                    "preview_candidate_count": 1
                },
                "candidates": [{
                    "case_index": 15,
                    "class_label": "missing_graph_moderate_case_15",
                    "candidate_source": "reason_packet",
                    "gate": "explicit_related_keys",
                    "from_key": "from_a",
                    "to_key": "to_b",
                    "edge_type": "relates",
                    "reason_kind": "explicit_related_keys",
                    "rationale": "shared review artifact context",
                    "shadow_aligned": true,
                    "baseline_top3": ["one", "two", "three"],
                    "preview_top3": ["one", "from_a", "to_b"],
                    "baseline_from_rank": 3,
                    "preview_from_rank": 1,
                    "baseline_to_rank": 4,
                    "preview_to_rank": 3,
                    "blend_coverage": 0.2,
                    "writes_memory": false,
                    "writes_edges": false,
                    "changes_search_order": false,
                    "can_change_retrieval_order": false,
                    "approval_writes_allowed": false,
                    "can_materialize_edges": false
                }]
            }))
            .expect("serialize packet fixture"),
        )
        .expect("write packet fixture");

        let rt = tokio::runtime::Builder::new_current_thread()
            .enable_all()
            .build()
            .expect("runtime");
        rt.block_on(async {
            let db_path = dir.path().join("state.db");
            let store = Arc::new(
                ab_store::SqliteStore::open(&db_path)
                    .await
                    .expect("open sqlite store"),
            );
            let state = AppState {
                store,
                markdown_root: None,
                reports_dir: None,
                recent_clicks: Arc::new(Mutex::new(VecDeque::with_capacity(CLICK_WINDOW))),
            };

            let Json(artifact) = api_materialization_review_artifact(State(state))
                .await
                .expect("materialization review artifact");

            assert_eq!(
                artifact["sections"]["decision_inbox"]["schema"],
                json!("agent_bridge.palace.materialization_review_decision_inbox.v0")
            );
            assert_eq!(
                artifact["sections"]["approved_plan"]["schema"],
                json!("agent_bridge.palace.materialization_approved_edge_plan.v0")
            );
            assert_eq!(
                artifact["summary"]["materialization_pending_count"],
                json!(1)
            );
            assert_eq!(
                artifact["summary"]["materialization_approved_count"],
                json!(0)
            );
            assert_eq!(
                artifact["candidates"][0]["review"]["decision"],
                json!("pending")
            );
            assert_eq!(
                artifact["sections"]["approved_plan"]["dry_run"],
                json!(true)
            );
            assert_eq!(
                artifact["sections"]["approved_plan"]["writes_edges"],
                json!(false)
            );
            assert_eq!(
                artifact["sections"]["approved_plan"]["changes_search_order"],
                json!(false)
            );
        });

        match old_packet {
            Some(value) => std::env::set_var("AB_PALACE_MATERIALIZATION_REVIEW_PACKET_JSON", value),
            None => std::env::remove_var("AB_PALACE_MATERIALIZATION_REVIEW_PACKET_JSON"),
        }
        match old_decisions {
            Some(value) => std::env::set_var("AB_PALACE_MATERIALIZATION_REVIEW_DECISIONS", value),
            None => std::env::remove_var("AB_PALACE_MATERIALIZATION_REVIEW_DECISIONS"),
        }
    }

    #[test]
    fn palace_materialization_review_decision_route_records_dry_run_approval_plan() {
        let _guard = ENV_LOCK.lock().expect("env lock");
        let dir = tempfile::tempdir().expect("tempdir");
        let old_packet = std::env::var_os("AB_PALACE_MATERIALIZATION_REVIEW_PACKET_JSON");
        let old_decisions = std::env::var_os("AB_PALACE_MATERIALIZATION_REVIEW_DECISIONS");
        let packet_path = dir.path().join("materialization-review-packet.json");
        let decisions_path = dir.path().join("materialization-review-decisions.jsonl");
        std::env::set_var("AB_PALACE_MATERIALIZATION_REVIEW_PACKET_JSON", &packet_path);
        std::env::set_var(
            "AB_PALACE_MATERIALIZATION_REVIEW_DECISIONS",
            &decisions_path,
        );
        std::fs::write(
            &packet_path,
            serde_json::to_vec_pretty(&json!({
                "schema": "agent_bridge.biocortex_retrieval.materialization_review_packet.v0",
                "read_only": true,
                "writes_memory": false,
                "writes_edges": false,
                "changes_search_order": false,
                "can_change_retrieval_order": false,
                "approval_writes_allowed": false,
                "can_materialize_edges": false,
                "candidates": [{
                    "candidate_source": "reason_packet",
                    "gate": "explicit_related_keys",
                    "from_key": "from_a",
                    "to_key": "to_b",
                    "edge_type": "relates",
                    "reason_kind": "explicit_related_keys",
                    "rationale": "shared review artifact context",
                    "shadow_aligned": true,
                    "baseline_top3": ["one", "two", "three"],
                    "preview_top3": ["one", "from_a", "to_b"],
                    "baseline_from_rank": 3,
                    "preview_from_rank": 1,
                    "baseline_to_rank": 4,
                    "preview_to_rank": 3,
                    "blend_coverage": 0.2,
                    "writes_memory": false,
                    "writes_edges": false,
                    "changes_search_order": false,
                    "can_change_retrieval_order": false,
                    "approval_writes_allowed": false,
                    "can_materialize_edges": false
                }]
            }))
            .expect("serialize packet fixture"),
        )
        .expect("write packet fixture");

        let rt = tokio::runtime::Builder::new_current_thread()
            .enable_all()
            .build()
            .expect("runtime");
        rt.block_on(async {
            let db_path = dir.path().join("state.db");
            let store = Arc::new(
                ab_store::SqliteStore::open(&db_path)
                    .await
                    .expect("open sqlite store"),
            );
            let state = AppState {
                store,
                markdown_root: None,
                reports_dir: None,
                recent_clicks: Arc::new(Mutex::new(VecDeque::with_capacity(CLICK_WINDOW))),
            };

            let Json(response) =
                api_materialization_review_decision(Json(MaterializationReviewDecisionRequest {
                    from_key: "from_a".to_string(),
                    to_key: "to_b".to_string(),
                    edge_type: Some("relates".to_string()),
                    decision: "approve".to_string(),
                    reviewer: Some("test".to_string()),
                    note: Some("looks evidence-backed".to_string()),
                }))
                .await
                .expect("record decision");

            assert_eq!(
                response["schema"],
                json!("agent_bridge.palace.materialization_review_decision_response.v0")
            );
            assert_eq!(response["writes_memory"], json!(false));
            assert_eq!(response["writes_edges"], json!(false));
            assert_eq!(response["changes_search_order"], json!(false));

            let loaded = load_palace_materialization_review_decisions(&decisions_path)
                .expect("load decisions");
            assert_eq!(loaded.len(), 1);
            assert_eq!(loaded[0]["decision"], json!("approve"));
            assert_eq!(loaded[0]["writes_edges"], json!(false));

            let Json(plan) = api_materialization_review_approved_plan(State(state))
                .await
                .expect("approved plan");
            assert_eq!(
                plan["schema"],
                json!("agent_bridge.palace.materialization_approved_edge_plan.v0")
            );
            assert_eq!(plan["dry_run"], json!(true));
            assert_eq!(plan["approved_pair_count"], json!(1));
            assert_eq!(plan["would_write_edges"], json!(1));
            assert_eq!(plan["writes_memory"], json!(false));
            assert_eq!(plan["writes_edges"], json!(false));
            assert_eq!(plan["changes_search_order"], json!(false));
            assert_eq!(plan["can_materialize_edges"], json!(false));
            assert_eq!(plan["links"][0]["from_key"], json!("from_a"));
            assert_eq!(plan["links"][0]["to_key"], json!("to_b"));
        });

        match old_packet {
            Some(value) => std::env::set_var("AB_PALACE_MATERIALIZATION_REVIEW_PACKET_JSON", value),
            None => std::env::remove_var("AB_PALACE_MATERIALIZATION_REVIEW_PACKET_JSON"),
        }
        match old_decisions {
            Some(value) => std::env::set_var("AB_PALACE_MATERIALIZATION_REVIEW_DECISIONS", value),
            None => std::env::remove_var("AB_PALACE_MATERIALIZATION_REVIEW_DECISIONS"),
        }
    }

    #[test]
    fn palace_materialization_approved_edge_apply_gate_requires_confirmation_before_writes() {
        let plan = json!({
            "schema": "agent_bridge.palace.materialization_approved_edge_plan.v0",
            "links": [{
                "pair_id": "from_a -[relates]-> to_b",
                "from_key": "from_a",
                "to_key": "to_b",
                "edge_type": "relates",
            }],
        });

        let gate = palace_materialization_approved_edge_apply_gate_for_plan(
            &plan,
            false,
            Some("wrong phrase"),
        );

        assert_eq!(
            gate["schema"],
            "agent_bridge.palace.materialization_approved_edge_apply.v0"
        );
        assert_eq!(
            gate["confirm_phrase"],
            json!(PALACE_MATERIALIZATION_APPROVED_EDGE_APPLY_CONFIRM)
        );
        assert_eq!(gate["dry_run"], json!(false));
        assert_eq!(gate["blocked"], json!(true));
        assert_eq!(gate["writes_edges"], json!(false));
        assert_eq!(gate["blocking_reasons"][0], json!("confirmation_required"));
    }

    #[test]
    fn palace_materialization_review_apply_route_uses_recorded_approvals_and_writes_edges() {
        let _guard = ENV_LOCK.lock().expect("env lock");
        let dir = tempfile::tempdir().expect("tempdir");
        let old_packet = std::env::var_os("AB_PALACE_MATERIALIZATION_REVIEW_PACKET_JSON");
        let old_decisions = std::env::var_os("AB_PALACE_MATERIALIZATION_REVIEW_DECISIONS");
        let old_apply_audit =
            std::env::var_os("AB_PALACE_MATERIALIZATION_APPROVED_EDGE_APPLY_AUDIT");
        let packet_path = dir.path().join("materialization-review-packet.json");
        let decisions_path = dir.path().join("materialization-review-decisions.jsonl");
        let apply_audit_path = dir.path().join("materialization-approved-edge-apply.jsonl");
        std::env::set_var("AB_PALACE_MATERIALIZATION_REVIEW_PACKET_JSON", &packet_path);
        std::env::set_var(
            "AB_PALACE_MATERIALIZATION_REVIEW_DECISIONS",
            &decisions_path,
        );
        std::env::set_var(
            "AB_PALACE_MATERIALIZATION_APPROVED_EDGE_APPLY_AUDIT",
            &apply_audit_path,
        );
        std::fs::write(
            &packet_path,
            serde_json::to_vec_pretty(&json!({
                "schema": "agent_bridge.biocortex_retrieval.materialization_review_packet.v0",
                "read_only": true,
                "writes_memory": false,
                "writes_edges": false,
                "changes_search_order": false,
                "can_change_retrieval_order": false,
                "approval_writes_allowed": false,
                "can_materialize_edges": false,
                "candidates": [{
                    "candidate_source": "reason_packet",
                    "gate": "explicit_related_keys",
                    "from_key": "from_a",
                    "to_key": "to_b",
                    "edge_type": "relates",
                    "reason_kind": "explicit_related_keys",
                    "rationale": "shared review artifact context",
                    "shadow_aligned": true,
                    "baseline_top3": ["one", "two", "three"],
                    "preview_top3": ["one", "from_a", "to_b"],
                    "baseline_from_rank": 3,
                    "preview_from_rank": 1,
                    "baseline_to_rank": 4,
                    "preview_to_rank": 3,
                    "blend_coverage": 0.2,
                    "writes_memory": false,
                    "writes_edges": false,
                    "changes_search_order": false,
                    "can_change_retrieval_order": false,
                    "approval_writes_allowed": false,
                    "can_materialize_edges": false
                }]
            }))
            .expect("serialize packet fixture"),
        )
        .expect("write packet fixture");

        let rt = tokio::runtime::Builder::new_current_thread()
            .enable_all()
            .build()
            .expect("runtime");
        rt.block_on(async {
            let db_path = dir.path().join("state.db");
            let store = Arc::new(
                ab_store::SqliteStore::open(&db_path)
                    .await
                    .expect("open sqlite store"),
            );
            store
                .memory_save(&test_mem(
                    "from_a",
                    "lesson",
                    "shared materialization review content alpha beta gamma",
                    &["memory"],
                ))
                .await
                .expect("save source");
            store
                .memory_save(&test_mem(
                    "to_b",
                    "lesson",
                    "shared materialization review content alpha beta delta",
                    &["memory"],
                ))
                .await
                .expect("save target");

            let state = AppState {
                store: store.clone(),
                markdown_root: None,
                reports_dir: None,
                recent_clicks: Arc::new(Mutex::new(VecDeque::with_capacity(CLICK_WINDOW))),
            };

            let Json(decision) =
                api_materialization_review_decision(Json(MaterializationReviewDecisionRequest {
                    from_key: "from_a".to_string(),
                    to_key: "to_b".to_string(),
                    edge_type: Some("relates".to_string()),
                    decision: "approve".to_string(),
                    reviewer: Some("test".to_string()),
                    note: Some("looks evidence-backed".to_string()),
                }))
                .await
                .expect("record materialization approval");
            assert_eq!(decision["writes_edges"], json!(false));

            let Json(blocked) = api_materialization_review_apply(
                State(state.clone()),
                Json(MaterializationApprovedEdgeApplyRequest {
                    dry_run: Some(false),
                    confirm: Some("wrong phrase".to_string()),
                    actor: Some("codex-test".to_string()),
                }),
            )
            .await
            .expect("blocked live apply");
            assert_eq!(blocked["status"], json!("blocked"));
            assert_eq!(blocked["writes_edges"], json!(false));
            assert_eq!(
                blocked["blocking_reasons"][0],
                json!("confirmation_required")
            );

            let Json(dry_run) = api_materialization_review_apply(
                State(state.clone()),
                Json(MaterializationApprovedEdgeApplyRequest {
                    dry_run: Some(true),
                    confirm: None,
                    actor: Some("codex-test".to_string()),
                }),
            )
            .await
            .expect("dry-run apply");
            assert_eq!(dry_run["status"], json!("dry_run"));
            assert_eq!(dry_run["would_write_edges"], json!(1));
            assert_eq!(dry_run["writes_edges"], json!(false));
            assert_eq!(dry_run["results"][0]["status"], json!("would_write"));
            let dry_run_neighbors = store
                .memory_neighbors("from_a")
                .await
                .expect("dry-run neighbors");
            assert!(
                !dry_run_neighbors.iter().any(|edge| {
                    edge.from_key == "from_a"
                        && edge.to_key == "to_b"
                        && edge.edge_type == "relates"
                }),
                "dry-run must not write the materialized relates edge; got {dry_run_neighbors:?}"
            );

            let Json(live) = api_materialization_review_apply(
                State(state.clone()),
                Json(MaterializationApprovedEdgeApplyRequest {
                    dry_run: Some(false),
                    confirm: Some(PALACE_MATERIALIZATION_APPROVED_EDGE_APPLY_CONFIRM.to_string()),
                    actor: Some("codex-test".to_string()),
                }),
            )
            .await
            .expect("live apply");
            assert_eq!(
                live["schema"],
                json!("agent_bridge.palace.materialization_approved_edge_apply.v0")
            );
            assert_eq!(live["status"], json!("applied"));
            assert_eq!(live["applied_count"], json!(1));
            assert_eq!(live["writes_edges"], json!(true));
            assert_eq!(live["changes_search_order"], json!(false));
            assert_eq!(live["can_change_retrieval_order"], json!(false));

            let neighbors = store.memory_neighbors("from_a").await.expect("neighbors");
            assert!(
                neighbors.iter().any(|edge| {
                    edge.from_key == "from_a"
                        && edge.to_key == "to_b"
                        && edge.edge_type == "relates"
                }),
                "expected live materialization apply to write the relates edge; got {neighbors:?}"
            );

            let Json(post_apply_plan) = api_materialization_review_approved_plan(State(state))
                .await
                .expect("post-apply approved plan");
            assert_eq!(post_apply_plan["approved_pair_count"], json!(1));
            assert_eq!(post_apply_plan["would_write_edges"], json!(0));
            assert_eq!(post_apply_plan["already_materialized_edge_count"], json!(1));
            assert_eq!(
                post_apply_plan["links"][0]["materialization_status"],
                json!("already_materialized")
            );
        });

        let records = load_palace_materialization_approved_edge_apply_records(&apply_audit_path)
            .expect("load apply audit");
        assert_eq!(records.len(), 3);
        assert_eq!(
            records[2]["schema"],
            json!("agent_bridge.palace.materialization_approved_edge_apply_audit.v0")
        );
        assert_eq!(records[2]["status"], json!("applied"));
        assert_eq!(records[2]["writes_edges"], json!(true));

        match old_packet {
            Some(value) => std::env::set_var("AB_PALACE_MATERIALIZATION_REVIEW_PACKET_JSON", value),
            None => std::env::remove_var("AB_PALACE_MATERIALIZATION_REVIEW_PACKET_JSON"),
        }
        match old_decisions {
            Some(value) => std::env::set_var("AB_PALACE_MATERIALIZATION_REVIEW_DECISIONS", value),
            None => std::env::remove_var("AB_PALACE_MATERIALIZATION_REVIEW_DECISIONS"),
        }
        match old_apply_audit {
            Some(value) => {
                std::env::set_var("AB_PALACE_MATERIALIZATION_APPROVED_EDGE_APPLY_AUDIT", value)
            }
            None => std::env::remove_var("AB_PALACE_MATERIALIZATION_APPROVED_EDGE_APPLY_AUDIT"),
        }
    }

    #[test]
    fn palace_materialization_review_packet_rejects_write_capable_candidate() {
        let dir = tempfile::tempdir().expect("tempdir");
        let packet_path = dir.path().join("materialization-review-packet.json");
        std::fs::write(
            &packet_path,
            serde_json::to_vec_pretty(&json!({
                "schema": "agent_bridge.biocortex_retrieval.materialization_review_packet.v0",
                "read_only": true,
                "writes_memory": false,
                "writes_edges": false,
                "changes_search_order": false,
                "can_change_retrieval_order": false,
                "approval_writes_allowed": false,
                "can_materialize_edges": false,
                "candidates": [{
                    "from_key": "from_a",
                    "to_key": "to_b",
                    "edge_type": "relates",
                    "writes_memory": true,
                    "changes_search_order": false
                }]
            }))
            .expect("serialize packet fixture"),
        )
        .expect("write packet fixture");

        let err = load_palace_materialization_review_packet(&packet_path)
            .expect_err("write-capable candidate must be rejected");
        assert!(
            err.contains("not read-only"),
            "unexpected error message: {err}"
        );
    }

    #[test]
    fn palace_review_artifact_html_exposes_section_anchors_and_copy_links() {
        assert!(
            PALACE_HTML.contains("data-review-artifact-anchor"),
            "review artifact sections should expose stable anchor markers"
        );
        assert!(
            PALACE_HTML.contains("copyPalaceReviewArtifactLink"),
            "review artifact section links should be copyable"
        );
        assert!(
            PALACE_HTML.contains("palace-review-artifact-anchor"),
            "review artifact section anchors should have a dedicated affordance style"
        );
    }

    #[test]
    fn palace_orphan_approved_link_apply_gate_requires_confirmation_before_writes() {
        let plan = json!({
            "schema": "agent_bridge.palace.orphan_approved_link_plan.v0",
            "links": [{
                "orphan_key": "memory_orphan",
                "candidate_key": "memory_anchor",
                "edge_type": "relates",
            }],
        });

        let gate =
            palace_orphan_approved_link_apply_gate_for_plan(&plan, false, Some("wrong phrase"));

        assert_eq!(
            gate["schema"],
            "agent_bridge.palace.orphan_approved_link_apply.v0"
        );
        assert_eq!(
            gate["confirm_phrase"],
            json!(PALACE_ORPHAN_APPROVED_LINK_APPLY_CONFIRM)
        );
        assert_eq!(gate["dry_run"], json!(false));
        assert_eq!(gate["blocked"], json!(true));
        assert_eq!(gate["writes_edges"], json!(false));
        assert_eq!(gate["blocking_reasons"][0], json!("confirmation_required"));
    }

    #[tokio::test]
    async fn palace_orphan_approved_link_apply_links_dry_run_then_live_writes_store_edges() {
        let dir = tempfile::tempdir().expect("tempdir");
        let db_path = dir.path().join("state.db");
        let store = ab_store::SqliteStore::open(&db_path)
            .await
            .expect("open sqlite store");
        store
            .memory_save(&test_mem(
                "memory_orphan",
                "lesson",
                "shared memory graph review content alpha beta gamma",
                &["memory"],
            ))
            .await
            .expect("save orphan");
        store
            .memory_save(&test_mem(
                "memory_anchor",
                "lesson",
                "shared memory graph review content alpha beta delta",
                &["memory"],
            ))
            .await
            .expect("save anchor");

        let plan = json!({
            "schema": "agent_bridge.palace.orphan_approved_link_plan.v0",
            "links": [{
                "pair_id": "memory_orphan -> memory_anchor",
                "orphan_key": "memory_orphan",
                "candidate_key": "memory_anchor",
                "edge_type": "relates",
            }],
        });
        let links = palace_orphan_approved_links_from_plan(&plan);

        let dry_run = palace_orphan_approved_link_apply_links(&store, links.clone(), true).await;

        assert_eq!(dry_run.applied_count, 0);
        assert_eq!(dry_run.failed_count, 0);
        assert_eq!(dry_run.skipped_count, 0);
        assert_eq!(dry_run.results[0]["status"], json!("would_write"));
        let dry_run_neighbors = store
            .memory_neighbors("memory_orphan")
            .await
            .expect("dry-run neighbors");
        assert!(
            !dry_run_neighbors.iter().any(|edge| {
                edge.from_key == "memory_orphan"
                    && edge.to_key == "memory_anchor"
                    && edge.edge_type == "relates"
            }),
            "dry-run must not write the approved relates edge; got {dry_run_neighbors:?}"
        );

        let live = palace_orphan_approved_link_apply_links(&store, links, false).await;

        assert_eq!(live.applied_count, 1);
        assert_eq!(live.failed_count, 0);
        assert_eq!(live.skipped_count, 0);
        assert_eq!(live.results[0]["status"], json!("applied"));
        let neighbors = store
            .memory_neighbors("memory_orphan")
            .await
            .expect("live neighbors");
        assert!(
            neighbors.iter().any(|edge| {
                edge.from_key == "memory_orphan"
                    && edge.to_key == "memory_anchor"
                    && edge.edge_type == "relates"
            }),
            "expected live apply to write a relates edge; got {neighbors:?}"
        );
    }

    #[test]
    fn palace_orphan_approved_link_apply_routes_use_recorded_approvals_and_write_edges() {
        let _guard = ENV_LOCK.lock().expect("env lock");
        let dir = tempfile::tempdir().expect("tempdir");
        let old_decisions = std::env::var_os("AB_PALACE_ORPHAN_CANDIDATE_DECISIONS");
        let old_apply_audit = std::env::var_os("AB_PALACE_ORPHAN_APPROVED_LINK_APPLY_AUDIT");

        std::env::set_var(
            "AB_PALACE_ORPHAN_CANDIDATE_DECISIONS",
            dir.path().join("decisions.jsonl"),
        );
        std::env::set_var(
            "AB_PALACE_ORPHAN_APPROVED_LINK_APPLY_AUDIT",
            dir.path().join("apply.jsonl"),
        );

        let rt = tokio::runtime::Builder::new_current_thread()
            .enable_all()
            .build()
            .expect("runtime");
        rt.block_on(async {
            let db_path = dir.path().join("state.db");
            let store = Arc::new(
                ab_store::SqliteStore::open(&db_path)
                    .await
                    .expect("open sqlite store"),
            );
            store
                .memory_save(&test_mem(
                    "route_orphan",
                    "lesson",
                    "orchid basalt comet lantern",
                    &["memory"],
                ))
                .await
                .expect("save orphan");
            store
                .memory_save(&test_mem(
                    "route_anchor",
                    "lesson",
                    "river marble copper horizon",
                    &["memory"],
                ))
                .await
                .expect("save anchor");

            let state = AppState {
                store: store.clone(),
                markdown_root: None,
                reports_dir: None,
                recent_clicks: Arc::new(Mutex::new(VecDeque::with_capacity(CLICK_WINDOW))),
            };
            let query = || OrphanCandidatesQuery {
                region: None,
                threshold: Some(0.1),
                min_content_len: Some(0),
                max_orphans: Some(4),
                candidate_limit: Some(2),
            };

            let Json(decision) =
                api_orphan_candidate_decision(Json(OrphanCandidateDecisionRequest {
                    orphan_key: "route_orphan".to_string(),
                    candidate_key: "route_anchor".to_string(),
                    decision: "approve".to_string(),
                    reviewer: Some("codex-test".to_string()),
                    note: Some("route-level approval".to_string()),
                }))
                .await
                .expect("record approval");
            assert_eq!(
                decision["schema"],
                json!("agent_bridge.palace.orphan_candidate_decision_response.v0")
            );
            assert_eq!(decision["written"], json!(true));
            assert_eq!(decision["writes_edges"], json!(false));
            assert_eq!(decision["record"]["decision"], json!("approve"));

            let Json(plan) = api_orphan_approved_link_plan(State(state.clone()), Query(query()))
                .await
                .expect("approved plan");
            assert_eq!(plan["approved_pair_count"], json!(1));
            assert_eq!(plan["links"][0]["orphan_key"], json!("route_orphan"));
            assert_eq!(plan["links"][0]["candidate_key"], json!("route_anchor"));
            assert_eq!(plan["links"][0]["reviewer"], json!("codex-test"));

            let Json(dry_run) = api_orphan_approved_link_apply(
                State(state.clone()),
                Json(OrphanApprovedLinkApplyRequest {
                    region: None,
                    threshold: Some(0.1),
                    min_content_len: Some(0),
                    max_orphans: Some(4),
                    candidate_limit: Some(2),
                    dry_run: Some(true),
                    confirm: None,
                    actor: Some("codex-test".to_string()),
                }),
            )
            .await
            .expect("dry-run apply");
            assert_eq!(dry_run["status"], json!("dry_run"));
            assert_eq!(dry_run["would_write_edges"], json!(1));
            assert_eq!(dry_run["writes_edges"], json!(false));
            assert_eq!(dry_run["results"][0]["status"], json!("would_write"));
            let dry_run_neighbors = store
                .memory_neighbors("route_orphan")
                .await
                .expect("dry-run neighbors");
            assert!(
                !dry_run_neighbors.iter().any(|edge| {
                    edge.from_key == "route_orphan"
                        && edge.to_key == "route_anchor"
                        && edge.edge_type == "relates"
                }),
                "dry-run must not write the approved relates edge; got {dry_run_neighbors:?}"
            );

            let Json(live) = api_orphan_approved_link_apply(
                State(state),
                Json(OrphanApprovedLinkApplyRequest {
                    region: None,
                    threshold: Some(0.1),
                    min_content_len: Some(0),
                    max_orphans: Some(4),
                    candidate_limit: Some(2),
                    dry_run: Some(false),
                    confirm: Some(PALACE_ORPHAN_APPROVED_LINK_APPLY_CONFIRM.to_string()),
                    actor: Some("codex-test".to_string()),
                }),
            )
            .await
            .expect("live apply");
            assert_eq!(live["status"], json!("applied"));
            assert_eq!(live["applied_count"], json!(1));
            assert_eq!(live["writes_edges"], json!(true));
            assert_eq!(live["results"][0]["status"], json!("applied"));

            let neighbors = store
                .memory_neighbors("route_orphan")
                .await
                .expect("live neighbors");
            assert!(
                neighbors.iter().any(|edge| {
                    edge.from_key == "route_orphan"
                        && edge.to_key == "route_anchor"
                        && edge.edge_type == "relates"
                }),
                "expected confirmed route apply to write a relates edge; got {neighbors:?}"
            );
        });

        match old_decisions {
            Some(value) => std::env::set_var("AB_PALACE_ORPHAN_CANDIDATE_DECISIONS", value),
            None => std::env::remove_var("AB_PALACE_ORPHAN_CANDIDATE_DECISIONS"),
        }
        match old_apply_audit {
            Some(value) => std::env::set_var("AB_PALACE_ORPHAN_APPROVED_LINK_APPLY_AUDIT", value),
            None => std::env::remove_var("AB_PALACE_ORPHAN_APPROVED_LINK_APPLY_AUDIT"),
        }
    }

    #[test]
    fn palace_review_artifact_route_assembles_current_review_state_without_writes() {
        let _guard = ENV_LOCK.lock().expect("env lock");
        let dir = tempfile::tempdir().expect("tempdir");
        let old_decisions = std::env::var_os("AB_PALACE_ORPHAN_CANDIDATE_DECISIONS");
        let old_apply_audit = std::env::var_os("AB_PALACE_ORPHAN_APPROVED_LINK_APPLY_AUDIT");

        std::env::set_var(
            "AB_PALACE_ORPHAN_CANDIDATE_DECISIONS",
            dir.path().join("decisions.jsonl"),
        );
        std::env::set_var(
            "AB_PALACE_ORPHAN_APPROVED_LINK_APPLY_AUDIT",
            dir.path().join("apply.jsonl"),
        );

        let rt = tokio::runtime::Builder::new_current_thread()
            .enable_all()
            .build()
            .expect("runtime");
        rt.block_on(async {
            let db_path = dir.path().join("state.db");
            let store = Arc::new(
                ab_store::SqliteStore::open(&db_path)
                    .await
                    .expect("open sqlite store"),
            );
            store
                .memory_save(&test_mem(
                    "artifact_route_orphan",
                    "lesson",
                    "palace review artifact route alpha beta gamma",
                    &["memory"],
                ))
                .await
                .expect("save orphan");
            store
                .memory_save(&test_mem(
                    "artifact_route_anchor",
                    "lesson",
                    "palace review artifact route alpha beta delta",
                    &["memory"],
                ))
                .await
                .expect("save anchor");

            let state = AppState {
                store: store.clone(),
                markdown_root: None,
                reports_dir: None,
                recent_clicks: Arc::new(Mutex::new(VecDeque::with_capacity(CLICK_WINDOW))),
            };
            let query = OrphanCandidatesQuery {
                region: None,
                threshold: Some(0.1),
                min_content_len: Some(0),
                max_orphans: Some(4),
                candidate_limit: Some(2),
            };

            let _ = api_orphan_candidate_decision(Json(OrphanCandidateDecisionRequest {
                orphan_key: "artifact_route_orphan".to_string(),
                candidate_key: "artifact_route_anchor".to_string(),
                decision: "approve".to_string(),
                reviewer: Some("codex-test".to_string()),
                note: Some("artifact route approval".to_string()),
            }))
            .await
            .expect("record approval");
            store
                .memory_link(
                    "artifact_route_orphan",
                    "artifact_route_anchor",
                    "relates",
                    1.0,
                )
                .await
                .expect("pre-existing verified edge");
            let apply_record = palace_orphan_approved_link_apply_record_for_time(
                &json!({
                    "schema": "agent_bridge.palace.orphan_approved_link_apply.v0",
                    "status": "applied",
                    "blocked": false,
                    "dry_run": false,
                    "approved_pair_count": 1,
                    "would_write_edges": 1,
                    "writes_memory": false,
                    "writes_edges": true,
                    "applied_count": 1,
                    "failed_count": 0,
                    "skipped_count": 0,
                    "results": [{
                        "pair_id": "artifact_route_orphan -> artifact_route_anchor",
                        "orphan_key": "artifact_route_orphan",
                        "candidate_key": "artifact_route_anchor",
                        "edge_type": "relates",
                        "status": "applied"
                    }]
                }),
                Some("codex-test"),
                30,
            );
            append_palace_orphan_approved_link_apply_record(
                &default_palace_orphan_approved_link_apply_path(),
                &apply_record,
            )
            .expect("append apply audit");

            let Json(artifact) = api_palace_review_artifact(State(state), Query(query))
                .await
                .expect("review artifact");

            assert_eq!(
                artifact["schema"],
                json!("agent_bridge.palace.review_artifact.v0")
            );
            assert_eq!(artifact["read_only"], json!(true));
            assert_eq!(artifact["writes_memory"], json!(false));
            assert_eq!(artifact["writes_edges"], json!(false));
            assert_eq!(artifact["auto_apply_allowed"], json!(false));
            assert_eq!(artifact["summary"]["approved_pair_count"], json!(0));
            assert_eq!(artifact["summary"]["recent_apply_audit_count"], json!(1));
            assert_eq!(artifact["summary"]["verified_edge_count"], json!(1));
            assert_eq!(
                artifact["sections"]["candidate_review"]["review"]["approved_count"],
                json!(0)
            );
            assert_eq!(
                artifact["sections"]["apply_audit"]["records"][0]["actor"],
                json!("codex-test")
            );
            assert_eq!(
                artifact["sections"]["verification_evidence"]["rows"][0]["from_key"],
                json!("artifact_route_orphan")
            );
        });

        match old_decisions {
            Some(value) => std::env::set_var("AB_PALACE_ORPHAN_CANDIDATE_DECISIONS", value),
            None => std::env::remove_var("AB_PALACE_ORPHAN_CANDIDATE_DECISIONS"),
        }
        match old_apply_audit {
            Some(value) => std::env::set_var("AB_PALACE_ORPHAN_APPROVED_LINK_APPLY_AUDIT", value),
            None => std::env::remove_var("AB_PALACE_ORPHAN_APPROVED_LINK_APPLY_AUDIT"),
        }
    }

    #[test]
    fn palace_orphan_approved_link_apply_audit_is_private_append_only_and_schema_filtered() {
        let dir = tempfile::tempdir().expect("tempdir");
        let path = dir.path().join("review").join("apply.jsonl");
        let blocked = palace_orphan_approved_link_apply_record_for_time(
            &json!({
                "schema": "agent_bridge.palace.orphan_approved_link_apply.v0",
                "status": "blocked",
                "blocked": true,
                "dry_run": false,
                "approved_pair_count": 1,
                "would_write_edges": 1,
                "writes_edges": false,
                "writes_memory": false,
                "blocking_reasons": ["confirmation_required"],
            }),
            Some("palace"),
            10,
        );
        let dry_run = palace_orphan_approved_link_apply_record_for_time(
            &json!({
                "schema": "agent_bridge.palace.orphan_approved_link_apply.v0",
                "status": "dry_run",
                "blocked": false,
                "dry_run": true,
                "approved_pair_count": 2,
                "would_write_edges": 2,
                "writes_edges": false,
                "writes_memory": false,
                "blocking_reasons": [],
            }),
            Some("palace"),
            20,
        );

        append_palace_orphan_approved_link_apply_record(&path, &blocked).expect("append blocked");
        append_palace_orphan_approved_link_apply_record(
            &path,
            &json!({
                "schema": "other.schema",
                "status": "ignored"
            }),
        )
        .expect("append ignored schema");
        append_palace_orphan_approved_link_apply_record(&path, &dry_run).expect("append dry_run");

        let loaded = load_palace_orphan_approved_link_apply_records(&path).expect("load apply");

        assert_eq!(loaded.len(), 2);
        assert_eq!(loaded[0]["status"], json!("blocked"));
        assert_eq!(loaded[0]["writes_edges"], json!(false));
        assert_eq!(
            loaded[0]["blocking_reasons"][0],
            json!("confirmation_required")
        );
        assert_eq!(loaded[1]["status"], json!("dry_run"));
        assert_eq!(loaded[1]["would_write_edges"], json!(2));
        #[cfg(unix)]
        {
            use std::os::unix::fs::PermissionsExt;
            let file_mode = std::fs::metadata(&path).unwrap().permissions().mode() & 0o777;
            let dir_mode = std::fs::metadata(path.parent().unwrap())
                .unwrap()
                .permissions()
                .mode()
                & 0o777;
            assert_eq!(file_mode, 0o600);
            assert_eq!(dir_mode, 0o700);
        }
    }

    #[test]
    fn palace_orphan_approved_link_apply_audit_tolerates_concatenated_legacy_lines() {
        let dir = tempfile::tempdir().expect("tempdir");
        let path = dir.path().join("apply.jsonl");
        let first = palace_orphan_approved_link_apply_record_for_time(
            &json!({
                "schema": "agent_bridge.palace.orphan_approved_link_apply.v0",
                "status": "dry_run",
                "blocked": false,
                "dry_run": true,
                "approved_pair_count": 1,
                "would_write_edges": 1,
                "writes_edges": false,
                "writes_memory": false,
                "blocking_reasons": [],
            }),
            Some("palace"),
            10,
        );
        let second = palace_orphan_approved_link_apply_record_for_time(
            &json!({
                "schema": "agent_bridge.palace.orphan_approved_link_apply.v0",
                "status": "applied",
                "blocked": false,
                "dry_run": false,
                "approved_pair_count": 1,
                "would_write_edges": 1,
                "applied_count": 1,
                "writes_edges": true,
                "writes_memory": false,
                "blocking_reasons": [],
            }),
            Some("palace"),
            20,
        );
        std::fs::write(
            &path,
            format!(
                "{}{}\nnot-json\n",
                serde_json::to_string(&first).expect("first json"),
                serde_json::to_string(&second).expect("second json")
            ),
        )
        .expect("write legacy audit");

        let loaded = load_palace_orphan_approved_link_apply_records(&path).expect("load apply");

        assert_eq!(loaded.len(), 2);
        assert_eq!(loaded[0]["status"], json!("dry_run"));
        assert_eq!(loaded[1]["status"], json!("applied"));
    }

    #[test]
    fn palace_orphan_approved_link_apply_audit_defaults_to_private_home_dir() {
        let _guard = ENV_LOCK.lock().expect("env lock");
        let home_dir = tempfile::tempdir().expect("home tempdir");
        let xdg_dir = tempfile::tempdir().expect("xdg tempdir");
        let old_home = std::env::var_os("HOME");
        let old_data_home = std::env::var_os("XDG_DATA_HOME");
        let old_review_dir = std::env::var_os("AB_PALACE_REVIEW_DIR");
        let old_apply_audit = std::env::var_os("AB_PALACE_ORPHAN_APPROVED_LINK_APPLY_AUDIT");

        std::env::set_var("HOME", home_dir.path());
        std::env::set_var("XDG_DATA_HOME", xdg_dir.path());
        std::env::remove_var("AB_PALACE_REVIEW_DIR");
        std::env::remove_var("AB_PALACE_ORPHAN_APPROVED_LINK_APPLY_AUDIT");

        let path = default_palace_orphan_approved_link_apply_path();
        let expected = home_dir
            .path()
            .join(".agent-bridge-private")
            .join("palace-review")
            .join("orphan-approved-link-apply.jsonl");

        match old_home {
            Some(value) => std::env::set_var("HOME", value),
            None => std::env::remove_var("HOME"),
        }
        match old_data_home {
            Some(value) => std::env::set_var("XDG_DATA_HOME", value),
            None => std::env::remove_var("XDG_DATA_HOME"),
        }
        match old_review_dir {
            Some(value) => std::env::set_var("AB_PALACE_REVIEW_DIR", value),
            None => std::env::remove_var("AB_PALACE_REVIEW_DIR"),
        }
        match old_apply_audit {
            Some(value) => std::env::set_var("AB_PALACE_ORPHAN_APPROVED_LINK_APPLY_AUDIT", value),
            None => std::env::remove_var("AB_PALACE_ORPHAN_APPROVED_LINK_APPLY_AUDIT"),
        }

        assert_eq!(path, expected);
    }

    #[test]
    fn palace_orphan_approved_link_apply_audit_sets_private_home_root_permissions() {
        let _guard = ENV_LOCK.lock().expect("env lock");
        let home_dir = tempfile::tempdir().expect("home tempdir");
        let old_home = std::env::var_os("HOME");
        let old_apply_audit = std::env::var_os("AB_PALACE_ORPHAN_APPROVED_LINK_APPLY_AUDIT");

        std::env::set_var("HOME", home_dir.path());
        std::env::remove_var("AB_PALACE_ORPHAN_APPROVED_LINK_APPLY_AUDIT");

        let path = default_palace_orphan_approved_link_apply_path();
        let record = palace_orphan_approved_link_apply_record_for_time(
            &json!({
                "schema": "agent_bridge.palace.orphan_approved_link_apply.v0",
                "status": "dry_run",
                "blocked": false,
                "dry_run": true,
            }),
            Some("palace"),
            30,
        );
        append_palace_orphan_approved_link_apply_record(&path, &record).expect("append audit");

        match old_home {
            Some(value) => std::env::set_var("HOME", value),
            None => std::env::remove_var("HOME"),
        }
        match old_apply_audit {
            Some(value) => std::env::set_var("AB_PALACE_ORPHAN_APPROVED_LINK_APPLY_AUDIT", value),
            None => std::env::remove_var("AB_PALACE_ORPHAN_APPROVED_LINK_APPLY_AUDIT"),
        }

        #[cfg(unix)]
        {
            use std::os::unix::fs::PermissionsExt;
            let private_root = home_dir.path().join(".agent-bridge-private");
            let root_mode = std::fs::metadata(private_root)
                .unwrap()
                .permissions()
                .mode()
                & 0o777;
            let review_mode = std::fs::metadata(path.parent().unwrap())
                .unwrap()
                .permissions()
                .mode()
                & 0o777;
            let file_mode = std::fs::metadata(&path).unwrap().permissions().mode() & 0o777;
            assert_eq!(root_mode, 0o700);
            assert_eq!(review_mode, 0o700);
            assert_eq!(file_mode, 0o600);
        }
    }

    #[test]
    fn split_frontmatter_basic() {
        let body = "---\nname: foo\ntype: project\n---\n# Hello\n\nbody.";
        let (fm, content) = split_frontmatter(body);
        assert!(fm.is_some());
        assert!(fm.unwrap().contains("type: project"));
        assert_eq!(content, "# Hello\n\nbody.");
    }

    #[test]
    fn split_frontmatter_absent() {
        let body = "# No frontmatter\n\nbody";
        let (fm, content) = split_frontmatter(body);
        assert!(fm.is_none());
        assert_eq!(content, body);
    }

    #[test]
    fn extract_links_finds_md_refs() {
        let content = "see [foo](foo.md) and [bar](bar.md). also (baz.md).";
        let links = extract_links(content);
        assert_eq!(links, vec!["bar", "baz", "foo"]);
    }

    #[test]
    fn extract_links_finds_bare_mentions() {
        // Memory bodies often reference siblings by bare filename
        // ("see project_warp_drop_to_museum.md for retirement context").
        let content = "see project_warp_drop_to_museum.md for retirement context";
        let links = extract_links(content);
        assert_eq!(links, vec!["project_warp_drop_to_museum"]);
    }

    #[test]
    fn extract_links_ignores_non_md() {
        let content = "see (https://example.com) and (some text)";
        let links = extract_links(content);
        assert!(links.is_empty());
    }

    #[test]
    fn extract_links_rejects_numeric_start() {
        // Avoid accidentally matching "42.md" or "123.md" — not real keys.
        let content = "see 42.md or 999.md";
        let links = extract_links(content);
        assert!(links.is_empty());
    }

    #[test]
    fn graph_query_accepts_boolish_all_values() {
        let q: GraphQuery = serde_json::from_value(json!({"all": "1"})).unwrap();
        assert!(q.all);
        let q: GraphQuery = serde_json::from_value(json!({"all": "true"})).unwrap();
        assert!(q.all);
        let q: GraphQuery = serde_json::from_value(json!({"all": "0"})).unwrap();
        assert!(!q.all);
        let q: GraphQuery = serde_json::from_value(json!({})).unwrap();
        assert!(!q.all);
    }

    #[test]
    fn semantic_events_report_palace_graph_diff() {
        let graph = json!({
            "now": 700000,
            "nodes": [
                {
                    "id": "a",
                    "kind": "lesson",
                    "label": "a",
                    "source": "sqlite",
                    "last_accessed": 699990,
                    "tags": []
                },
                {
                    "id": "b",
                    "kind": "decision",
                    "label": "b",
                    "source": "sqlite",
                    "last_accessed": 1,
                    "tags": []
                },
                {
                    "id": "c",
                    "kind": "project",
                    "label": "c",
                    "source": "markdown",
                    "last_accessed": 0,
                    "tags": []
                }
            ],
            "edges": [
                { "source": "a", "target": "b", "type": "references", "weight": 0.7 },
                { "source": "b", "target": "c", "type": "coactivation", "weight": 0.2 }
            ],
            "stats": {
                "sqlite_nodes": 2,
                "markdown_nodes": 1,
                "sqlite_edges": 1,
                "markdown_edges": 0,
                "coact_edges": 1
            }
        });
        let q: SemanticEventsQuery = serde_json::from_value(json!({
            "baseline_nodes": 2,
            "baseline_edges": 1,
            "baseline_orphans": 0,
            "baseline_hubs": 0
        }))
        .unwrap();

        let report = build_palace_semantic_events(&graph, &q);
        assert_eq!(report["schema"], "agent_bridge.semantic_bus.palace_diff.v0");
        assert_eq!(report["verification"]["verdict"], "verified");
        assert_eq!(
            report["verification"]["verified_to"],
            "semantic_objects/events/diff"
        );
        assert_eq!(
            report["semantic_objects"][0]["schema"],
            "agent_bridge.semantic_bus.object.v0"
        );
        assert_eq!(
            report["semantic_objects"][0]["object_id"],
            "palace:memory-graph"
        );
        assert_eq!(report["diff"]["changed"], true);
        assert_eq!(report["diff"]["delta"]["nodes"], 1);
        assert_eq!(report["diff"]["delta"]["edges"], 1);
        assert_eq!(report["diff"]["current"]["sqlite_nodes"], 2);
        assert_eq!(report["diff"]["current"]["markdown_nodes"], 1);
        assert_eq!(report["diff"]["current"]["explicit_edges"], 1);
        assert_eq!(report["diff"]["current"]["coactivation_edges"], 1);
        assert_eq!(report["diff"]["current"]["orphan_nodes"], 1);
        assert_eq!(report["diff"]["current"]["fresh_nodes"], 1);
        assert_eq!(report["diff"]["current"]["stale_nodes"], 1);
        assert_eq!(report["events"][0]["event_type"], "palace.graph.observed");
        assert_eq!(
            report["events"][1]["event_type"],
            "palace.graph.diff.changed"
        );
        assert_eq!(
            report["events"][1]["source_event_ids"][0],
            report["events"][0]["event_id"]
        );
        assert_eq!(
            report["presentation"]["ingestion"]["write_policy"],
            "read_only_no_auto_memory_write"
        );
    }

    #[test]
    fn self_review_packet_prioritizes_memory_governance_lanes_without_writes() {
        let graph = json!({
            "now": 700000,
            "nodes": [
                { "id": "fresh_note", "kind": "lesson", "source": "sqlite", "last_accessed": 699990, "tags": [] },
                { "id": "stale_note", "kind": "decision", "source": "sqlite", "last_accessed": 1, "tags": [] },
                { "id": "orphan_note", "kind": "todo", "source": "sqlite", "last_accessed": 600000, "tags": [] },
                { "id": "hub_a", "kind": "lesson", "source": "sqlite", "last_accessed": 600000, "tags": [] },
                { "id": "hub_b", "kind": "lesson", "source": "sqlite", "last_accessed": 600000, "tags": [] },
                { "id": "hub_c", "kind": "lesson", "source": "sqlite", "last_accessed": 600000, "tags": [] },
                { "id": "hub_d", "kind": "lesson", "source": "sqlite", "last_accessed": 600000, "tags": [] },
                { "id": "hub_e", "kind": "lesson", "source": "sqlite", "last_accessed": 600000, "tags": [] },
                { "id": "hub_f", "kind": "lesson", "source": "sqlite", "last_accessed": 600000, "tags": [] },
                { "id": "hub_g", "kind": "lesson", "source": "sqlite", "last_accessed": 600000, "tags": [] },
                { "id": "hub_h", "kind": "lesson", "source": "sqlite", "last_accessed": 600000, "tags": [] },
                { "id": "hub_i", "kind": "lesson", "source": "sqlite", "last_accessed": 600000, "tags": [] },
                { "id": "hub_j", "kind": "lesson", "source": "sqlite", "last_accessed": 600000, "tags": [] },
                { "id": "hub_k", "kind": "lesson", "source": "sqlite", "last_accessed": 600000, "tags": [] },
                { "id": "hub_l", "kind": "lesson", "source": "sqlite", "last_accessed": 600000, "tags": [] },
                { "id": "hub_m", "kind": "lesson", "source": "sqlite", "last_accessed": 600000, "tags": [] },
                { "id": "hub_n", "kind": "lesson", "source": "sqlite", "last_accessed": 600000, "tags": [] },
                { "id": "hub_o", "kind": "lesson", "source": "sqlite", "last_accessed": 600000, "tags": [] },
                { "id": "hub_p", "kind": "lesson", "source": "sqlite", "last_accessed": 600000, "tags": [] },
                { "id": "hub_q", "kind": "lesson", "source": "sqlite", "last_accessed": 600000, "tags": [] },
                { "id": "hub_r", "kind": "lesson", "source": "sqlite", "last_accessed": 600000, "tags": [] },
                { "id": "hub_s", "kind": "lesson", "source": "sqlite", "last_accessed": 600000, "tags": [] },
                { "id": "hub_t", "kind": "lesson", "source": "sqlite", "last_accessed": 600000, "tags": [] }
            ],
            "edges": [
                { "source": "fresh_note", "target": "stale_note", "type": "relates", "weight": 1.0 },
                { "source": "hub_a", "target": "hub_b", "type": "relates", "weight": 1.0 },
                { "source": "hub_a", "target": "hub_c", "type": "relates", "weight": 1.0 },
                { "source": "hub_a", "target": "hub_d", "type": "relates", "weight": 1.0 },
                { "source": "hub_a", "target": "hub_e", "type": "relates", "weight": 1.0 },
                { "source": "hub_a", "target": "hub_f", "type": "relates", "weight": 1.0 },
                { "source": "hub_g", "target": "hub_h", "type": "relates", "weight": 1.0 },
                { "source": "hub_i", "target": "hub_j", "type": "relates", "weight": 1.0 },
                { "source": "hub_k", "target": "hub_l", "type": "relates", "weight": 1.0 },
                { "source": "hub_m", "target": "hub_n", "type": "relates", "weight": 1.0 },
                { "source": "hub_o", "target": "hub_p", "type": "relates", "weight": 1.0 },
                { "source": "hub_q", "target": "hub_r", "type": "relates", "weight": 1.0 },
                { "source": "hub_s", "target": "hub_t", "type": "relates", "weight": 1.0 }
            ],
            "stats": {}
        });

        let packet = build_palace_self_review_packet(&graph);

        assert_eq!(
            packet["schema"],
            "agent_bridge.palace.self_review_packet.v0"
        );
        assert_eq!(packet["read_only"], json!(true));
        assert_eq!(packet["writes_memory"], json!(false));
        assert_eq!(packet["writes_edges"], json!(false));
        assert_eq!(packet["auto_apply_allowed"], json!(false));
        assert_eq!(packet["readiness"], json!("needs-review"));
        assert_eq!(packet["primary_lane"], json!("connect"));
        assert_eq!(
            packet["presentation"]["human_summary"],
            json!("Memory graph needs self-review: connect is the highest-priority lane.")
        );
        assert_eq!(packet["lanes"][0]["id"], json!("connect"));
        assert_eq!(packet["lanes"][0]["count"], json!(1));
        assert_eq!(packet["lanes"][0]["risk"], json!("high"));
        assert_eq!(packet["lanes"][1]["id"], json!("retrieval"));
        assert_eq!(packet["lanes"][1]["count"], json!(1));
        assert_eq!(packet["lanes"][2]["id"], json!("consolidate"));
        assert_eq!(packet["lanes"][2]["count"], json!(1));
        assert_eq!(packet["lanes"][3]["id"], json!("formation"));
        assert_eq!(packet["lanes"][3]["count"], json!(1));
        assert_eq!(packet["graph"]["orphan_nodes"], json!(1));
        assert_eq!(packet["provenance"]["graph_endpoint"], json!("/api/graph"));
    }

    #[test]
    fn self_review_packet_includes_read_only_history_from_review_audits() {
        let graph = json!({
            "now": 700000,
            "nodes": [
                { "id": "memory_orphan", "kind": "lesson", "source": "sqlite", "last_accessed": 600000, "tags": [] },
                { "id": "memory_anchor", "kind": "lesson", "source": "sqlite", "last_accessed": 600000, "tags": [] }
            ],
            "edges": [],
            "stats": {}
        });
        let pairs = [
            PalaceOrphanCandidatePair {
                orphan_key: "memory_orphan_a".to_string(),
                candidate_key: "memory_anchor_a".to_string(),
            },
            PalaceOrphanCandidatePair {
                orphan_key: "memory_orphan_b".to_string(),
                candidate_key: "memory_anchor_b".to_string(),
            },
            PalaceOrphanCandidatePair {
                orphan_key: "memory_orphan_c".to_string(),
                candidate_key: "memory_anchor_c".to_string(),
            },
        ];
        let decisions = vec![
            palace_orphan_candidate_decision_record_for_time(
                &pairs[0],
                "approve",
                Some("codex"),
                Some("explicit evidence"),
                10,
            )
            .expect("approve record"),
            palace_orphan_candidate_decision_record_for_time(
                &pairs[1],
                "defer",
                Some("codex"),
                Some("needs review"),
                20,
            )
            .expect("defer record"),
            palace_orphan_candidate_decision_record_for_time(
                &pairs[2],
                "reject",
                Some("codex"),
                Some("wrong relation"),
                30,
            )
            .expect("reject record"),
        ];
        let apply_records = vec![
            palace_orphan_approved_link_apply_record_for_time(
                &json!({
                    "schema": "agent_bridge.palace.orphan_approved_link_apply.v0",
                    "status": "applied",
                    "blocked": false,
                    "dry_run": false,
                    "applied_count": 2,
                    "failed_count": 0,
                    "writes_memory": false,
                    "writes_edges": true
                }),
                Some("codex"),
                40,
            ),
            palace_orphan_approved_link_apply_record_for_time(
                &json!({
                    "schema": "agent_bridge.palace.orphan_approved_link_apply.v0",
                    "status": "blocked",
                    "blocked": true,
                    "dry_run": true,
                    "applied_count": 0,
                    "failed_count": 1,
                    "writes_memory": false,
                    "writes_edges": false
                }),
                Some("codex"),
                50,
            ),
        ];

        let packet =
            build_palace_self_review_packet_with_history(&graph, &decisions, &apply_records);

        assert_eq!(
            packet["history"]["schema"],
            json!("agent_bridge.palace.self_review_history.v0")
        );
        assert_eq!(packet["history"]["read_only"], json!(true));
        assert_eq!(packet["history"]["writes_memory"], json!(false));
        assert_eq!(packet["history"]["writes_edges"], json!(false));
        assert_eq!(packet["history"]["decision_count"], json!(3));
        assert_eq!(packet["history"]["approved_count"], json!(1));
        assert_eq!(packet["history"]["deferred_count"], json!(1));
        assert_eq!(packet["history"]["rejected_count"], json!(1));
        assert_eq!(packet["history"]["apply_audit_count"], json!(2));
        assert_eq!(packet["history"]["applied_count"], json!(2));
        assert_eq!(packet["history"]["failed_count"], json!(1));
        assert_eq!(packet["history"]["last_decision_at_unix"], json!(30));
        assert_eq!(packet["history"]["last_apply_at_unix"], json!(50));
        assert_eq!(packet["history"]["recent"][0]["kind"], json!("apply"));
        assert_eq!(
            packet["presentation"]["machine_payload"]["history"]["decision_count"],
            json!(3)
        );
        assert_eq!(
            packet["provenance"]["history_sources"],
            json!([
                "palace_orphan_candidate_decisions",
                "palace_orphan_approved_link_apply_audit"
            ])
        );
    }

    #[test]
    fn parse_full_memory() {
        let body = "---\nname: My Vision\ndescription: A short one\ntype: project\n---\nbody with (related.md) ref.";
        let m = parse_markdown_memory("test".to_string(), body);
        assert_eq!(m.key, "test");
        assert_eq!(m.kind, "project");
        assert_eq!(m.description, "A short one");
        assert_eq!(m.links_to, vec!["related"]);
    }
}
