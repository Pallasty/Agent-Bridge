//! Persistence abstraction.
//!
//! Default impl: [`SqliteStore`] — single-file rusqlite (bundled), zero system deps.
//! Future: in-memory (tests), Postgres (multi-machine), Redis (cache).

use ab_core::{NotifyEvent, Result, SessionId};
use async_trait::async_trait;
use serde::{Deserialize, Serialize};

pub mod codebase;
pub mod embedding;
pub mod sqlite;
pub use sqlite::{default_db_path, temporal_bonus, weight_for_edge_type, SqliteStore};
pub mod vector;
pub use embedding::{
    default_backend, set_default_backend, EmbeddingBackend, HashBackend, OnnxBackend,
};
pub use vector::{cosine_similarity, decode_embedding, embed_text, encode_embedding, VECTOR_DIM};

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct StoredSession {
    pub id: SessionId,
    pub runtime_id: String,
    pub cwd: String,
    pub started_at: i64,
    #[serde(default)]
    pub ended_at: Option<i64>,
    /// Process exit code, populated once the agent finishes.
    #[serde(default)]
    pub exit_code: Option<i32>,
    /// Captured stdout (truncated to STDIO_CAP bytes).
    #[serde(default)]
    pub stdout: Option<String>,
    /// Captured stderr (truncated to STDIO_CAP bytes).
    #[serde(default)]
    pub stderr: Option<String>,
    // ── v8: cloud-run lifecycle fields (warp-oz) ────────────────────
    /// Warp cloud run UUID, parsed from `oz agent run-cloud` JSON output.
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub cloud_run_id: Option<String>,
    /// Last known cloud run state: QUEUED | INPROGRESS | SUCCEEDED | FAILED.
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub cloud_run_state: Option<String>,
    /// URL to the full cloud run transcript on Warp.
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub cloud_session_link: Option<String>,
}

/// One persisted notification, with its server-assigned timestamp.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct NotificationRecord {
    /// Unix epoch seconds.
    pub ts: i64,
    pub event: NotifyEvent,
}

/// One failed MCP `tools/call` kept in the SQLite ring buffer (`mcp_tool_errors`).
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct McpToolErrorRecord {
    pub ts: i64,
    pub tool_name: String,
    pub message: String,
}

/// Aggregate statistics for one MCP tool over a time window — output of
/// [`StateStore::mcp_tool_call_stats`].
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub struct McpToolCallStats {
    pub tool_name: String,
    pub call_count: u64,
    pub error_count: u64,
    pub avg_duration_ms: f64,
    pub p95_duration_ms: u32,
    pub max_duration_ms: u32,
    pub avg_result_size: f64,
}

/// Max rows retained in `mcp_tool_errors` after each insert (oldest pruned).
pub const MCP_TOOL_ERROR_RING_CAP: u32 = 100;

/// Hard cap on stdout/stderr we persist per agent session, to keep the DB
/// file from growing unbounded if a sub-agent goes haywire.
pub const STDIO_CAP: usize = 64 * 1024;

/// Hard cap on a single memory's `content` field (256 KiB).
pub const MEMORY_CONTENT_CAP: usize = 256 * 1024;

/// One row in the `memories` table — Claude's cross-session note.
///
/// Hyperlink-style relationships only: `related_keys` is a list of other
/// memory keys the author thinks are relevant. The store does NOT auto-resolve
/// these — callers can fetch them with separate `get` calls.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct MemoryRecord {
    pub key: String,
    pub kind: String,
    pub content: String,
    #[serde(default)]
    pub tags: Vec<String>,
    #[serde(default)]
    pub related_keys: Vec<String>,
    /// Visibility scope. `None` / `"global"` = visible everywhere.
    /// `"project:/abs/path"` = only when cwd matches.
    /// `"domain:rust"` = technology-domain grouping.
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub scope: Option<String>,
    pub created_at: i64,
    pub updated_at: i64,
    pub last_accessed_at: i64,
    pub access_count: u64,
    /// Cognitive importance score (0.0–1.0). Auto-assigned by kind on first
    /// save (decision:0.8, lesson:0.7, todo:0.6, fact/context:0.5,
    /// observation:0.3). Decays over time via session_finalize.
    #[serde(default = "default_importance")]
    pub importance: f64,
    /// Lifecycle status: "active" | "archived" | "superseded".
    /// Archived = decayed below threshold. Superseded = a newer memory
    /// auto-detected as replacing this one.
    #[serde(default = "default_status")]
    pub status: String,
    /// When `kind == error_pattern`, optional substring to match against
    /// `session_bootstrap`'s `error_hint` (case-insensitive).
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub trigger_pattern: Option<String>,
}

fn default_importance() -> f64 {
    0.5
}
fn default_status() -> String {
    "active".to_string()
}

/// A directed edge between two memory records.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct MemoryEdge {
    pub from_key: String,
    pub to_key: String,
    /// Relationship type: relates | contradicts | supersedes | derived_from | implements
    pub edge_type: String,
    /// Optional strength weight (0.0–1.0). Default 1.0.
    #[serde(default = "default_weight")]
    pub weight: f64,
}

/// One `memory_edges` row for JSONL export / import (portable graph slice).
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub struct MemoryEdgeExport {
    pub from_key: String,
    pub to_key: String,
    pub edge_type: String,
    pub weight: f64,
    pub created_at: i64,
}

fn default_weight() -> f64 {
    1.0
}

/// One hit from `memory_search`. Carries a coarse score so callers can
/// re-rank if needed.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct MemorySearchHit {
    pub record: MemoryRecord,
    /// Composite score: matches × recency × usage. Higher = better.
    pub score: f64,
}

/// One co-activation edge — Hebbian "fire together, wire together" trace
/// between two memories that surfaced in the same `memory_search` result.
///
/// Vision: `docs/DESIGN-v21-synaptic-trace-and-dream.md`. This is the α
/// data layer; β/γ consume it for seed self-mutation and predictive prime.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub struct CoactivationEdge {
    pub key_a: String,
    pub key_b: String,
    pub count: u64,
    pub first_at: i64,
    pub last_at: i64,
}

/// Aggregate health snapshot of the synaptic trace graph (v21 α). Output of
/// [`StateStore::coactivation_stats`] — the data behind the β trigger
/// decision (per design doc §5: "non-trivial cluster structure if top 10
/// pairs' count is ≥ 5× median count").
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub struct CoactivationStats {
    pub total_pairs: u64,
    pub total_unique_keys: u64,
    pub max_count: u64,
    pub median_count: f64,
    pub top10_avg_count: f64,
    /// β trigger metric. Values ≥ 5.0 indicate non-uniform cluster structure
    /// has emerged — at that point β (seed self-mutation) design lock is
    /// justified by data.
    pub top10_to_median_ratio: f64,
    pub pairs_last_24h: u64,
    pub top_5_edges: Vec<CoactivationEdge>,
}

/// Sort order for `list_memories`.
#[derive(Debug, Clone, Copy, Serialize, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "snake_case")]
pub enum MemoryListSort {
    /// `last_accessed_at DESC` — most recently touched first.
    Recent,
    /// `access_count DESC` — most-referenced first.
    Frequent,
    /// `created_at DESC` — newest first.
    Newest,
    /// PUCT-inspired cognitive ranking: `importance / (1 + age_days)` DESC.
    /// High-importance, recently-updated memories surface first.
    ByImportance,
}

impl Default for MemoryListSort {
    fn default() -> Self {
        Self::Recent
    }
}

/// One step in a persisted agent task plan (W5 — DESIGN-warp-first-agent-shell).
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct PlanStep {
    pub id: String,
    pub desc: String,
    /// Typical values: `pending` | `in_progress` | `done` | `cancelled` (free-form allowed).
    #[serde(default = "default_plan_status")]
    pub status: String,
    #[serde(default)]
    pub deps: Vec<String>,
}

fn default_plan_status() -> String {
    "pending".to_string()
}

/// Full plan row loaded from SQLite.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct PlanRecord {
    pub plan_id: String,
    pub title: String,
    pub steps: Vec<PlanStep>,
    pub created_at: i64,
    pub updated_at: i64,
}

/// One persisted agent-to-agent message row (W6 — multi-session inbox).
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct AgentMessageRecord {
    pub id: i64,
    pub from_session: String,
    pub to_session: String,
    pub payload: serde_json::Value,
    pub created_at: i64,
    pub read: bool,
}

// ── v18: forum / shared whiteboard ───────────────────────────────────────────

/// One thread (topic) on a board.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct ForumThreadRecord {
    pub id: i64,
    pub board: String,
    pub title: String,
    pub created_by: String,
    pub created_at: i64,
    pub last_post_at: i64,
    /// `open` | `resolved` | `archived`
    pub status: String,
    pub tags: Vec<String>,
    pub post_count: i64,
    /// Posts after the caller's `last_seen_post_id` (only filled when caller
    /// has a subscription on this thread or its board).
    #[serde(skip_serializing_if = "Option::is_none")]
    pub unread_count: Option<i64>,
}

/// One post inside a thread.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct ForumPostRecord {
    pub id: i64,
    pub thread_id: i64,
    pub author: String,
    /// `msg` | `finding` | `question` | `decision` | `reply`
    pub kind: String,
    pub body: String,
    pub refs: serde_json::Value,
    pub created_at: i64,
}

/// Result of `forum_post`: either a brand-new thread + its first post, or an
/// appended post on an existing thread.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct ForumPostOutcome {
    pub thread_id: i64,
    pub post_id: i64,
    /// True when this call also created the thread row.
    pub created_thread: bool,
}

/// One thread + its posts, in cross-device sync shape. No local id columns —
/// the receiving side either matches an existing row by natural key
/// `(board, created_by, created_at, title)` and reuses its local id, or
/// inserts and gets a fresh local id. Subscriptions are intentionally
/// excluded from sync — each device tracks its own read cursors.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct ForumThreadExport {
    pub board: String,
    pub title: String,
    pub created_by: String,
    pub created_at: i64,
    pub last_post_at: i64,
    pub status: String,
    #[serde(default)]
    pub tags: Vec<String>,
    #[serde(default)]
    pub posts: Vec<ForumPostExport>,
}

/// One post in a `ForumThreadExport`. Natural key for dedup is
/// `(thread, author, created_at, body)` — same author posting the same body
/// at the same epoch second is treated as the same logical post.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct ForumPostExport {
    pub author: String,
    pub kind: String,
    pub body: String,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub refs: Option<serde_json::Value>,
    pub created_at: i64,
}

#[derive(Debug, Clone, Default, Serialize, Deserialize)]
pub struct ForumExportResult {
    pub threads_written: u64,
    pub posts_written: u64,
}

#[derive(Debug, Clone, Default, Serialize, Deserialize)]
pub struct ForumImportReport {
    pub threads_inserted: u64,
    pub threads_matched: u64,
    pub posts_inserted: u64,
    pub posts_skipped: u64,
    pub malformed: u64,
}

// ── v19: agent presence / identity registry ─────────────────────────────────

/// One agent's presence row. Field naming aligns with Google A2A AgentCard so
/// the public-facing block (name/description/version/url/capabilities/skills)
/// can be serialized directly to `/.well-known/agent.json` once we daemon-ize.
/// See `docs/DESIGN-v19-presence-identity.md`.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub struct AgentPresenceRecord {
    pub session_id: String,

    // A2A AgentCard public block
    pub name: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub description: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub version: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub url: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub capabilities: Option<serde_json::Value>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub skills: Option<serde_json::Value>,

    // Identity convention split-out (private to bridge)
    pub node: String,
    pub project: String,
    pub role: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub tag: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub cwd: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub pid: Option<i64>,

    pub started_at: i64,
    pub last_heartbeat_at: i64,
}

/// Optional fields for `agent_presence_announce` upsert. `None` means "leave
/// existing value untouched" (so heartbeat-only refresh calls work without
/// re-supplying everything). Internal builder — not meant to cross the wire.
#[derive(Debug, Clone, Default)]
pub struct AgentPresenceUpsert<'a> {
    pub name: Option<&'a str>,
    pub description: Option<&'a str>,
    pub version: Option<&'a str>,
    pub url: Option<&'a str>,
    pub node: Option<&'a str>,
    pub project: Option<&'a str>,
    pub role: Option<&'a str>,
    pub tag: Option<&'a str>,
    pub cwd: Option<&'a str>,
    pub pid: Option<i64>,
    pub capabilities: Option<&'a serde_json::Value>,
    pub skills: Option<&'a serde_json::Value>,
}

// ── D3.2: codebase symbol index ──────────────────────────────────────────────

/// One symbol extracted from a source file.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct CodebaseSymbol {
    pub file_path: String,
    pub line: u32,
    pub col: u32,
    /// Canonical kind: fn | struct | enum | trait | type | const | static |
    ///   mod | impl | macro | class | def | function | interface | method | var | func
    pub kind: String,
    pub name: String,
    /// First ~200 chars of the declaration line.
    pub signature: String,
    pub language: String,
    /// Cosine similarity score (0–1). Set only when `mode = "semantic"`.
    #[serde(skip_serializing_if = "Option::is_none")]
    pub score: Option<f32>,
}

/// Stats returned by [`StateStore::codebase_index`].
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct CodebaseIndexStats {
    pub indexed_files: u32,
    pub symbols: u32,
    pub duration_ms: u64,
    pub root_path: String,
}

/// Reorder memories so `kind == "session_handoff"` rows appear first.
///
/// Session bootstrap and similar call sites use importance-based SQL ordering;
/// this stable partition ensures cross-session handoff notes surface before
/// lessons/decisions so a new agent sees continuity immediately.
pub fn prioritize_session_handoff(rows: Vec<MemoryRecord>) -> Vec<MemoryRecord> {
    let (mut head, tail): (Vec<_>, Vec<_>) =
        rows.into_iter().partition(|r| r.kind == "session_handoff");
    head.extend(tail);
    head
}

/// Compaction policy for `memory_compact`. After v0.7.1, both thresholds
/// must agree (AND) before a row is considered stale, AND the row must be
/// older than the implementation-defined grace period (1 h on `created_at`).
#[derive(Debug, Clone, Copy, Default)]
pub struct CompactPolicy {
    /// Remove rows with `access_count < min_uses` (None = no threshold).
    pub min_uses: Option<u64>,
    /// Remove rows with `last_accessed_at < (now - older_than_secs)`.
    pub older_than_secs: Option<i64>,
    /// If true, return the matching keys without deleting.
    pub dry_run: bool,
}

impl CompactPolicy {
    /// **v0.8**: a balanced policy callers can use when they have no specific
    /// preference. Removes memories that are BOTH rarely-touched
    /// (`access_count < 2`) AND last accessed > 90 days ago. The 1-hour
    /// grace period on `created_at` (enforced inside `memory_compact`) further
    /// shields anything saved within the last hour.
    ///
    /// Use this when wiring compact into automation (cron, Stop hook,
    /// `agent-cli memory compact`) to avoid the "no thresholds → no-op"
    /// trap of v0.6.x – v0.7.x.
    pub fn healthy_default() -> Self {
        Self {
            min_uses: Some(2),
            older_than_secs: Some(90 * 86_400), // 90 days
            dry_run: false,
        }
    }

    /// True if neither threshold is set — caller almost certainly wants
    /// [`Self::healthy_default`] applied instead of a silent no-op.
    pub fn is_unset(&self) -> bool {
        self.min_uses.is_none() && self.older_than_secs.is_none()
    }
}

/// Filters for `list_sessions` (v0.5). All None = match everything.
/// Multiple filters combine with AND.
#[derive(Debug, Clone, Default)]
pub struct SessionFilter {
    /// Match exact runtime_id (e.g. "claude-code").
    pub runtime_id: Option<String>,
    /// Match sessions whose cwd starts with this prefix.
    pub cwd_prefix: Option<String>,
    /// `Some(true)` → only finished sessions; `Some(false)` → only running;
    /// `None` → both.
    pub exited_only: Option<bool>,
    /// Match exact exit_code (use negative for signal-killed; see v0.3 notes).
    pub exit_code: Option<i32>,
}

/// Aggregate statistics about the memory store (returned by `memory_stats`).
#[derive(Debug, Clone, Default, Serialize, Deserialize)]
pub struct MemoryStats {
    /// Memory count by status: `"active"`, `"archived"`, `"superseded"`.
    pub counts_by_status: std::collections::HashMap<String, u64>,
    /// Active memory count per kind, sorted by count descending (top 20).
    pub counts_by_kind: Vec<(String, u64)>,
    /// Total directed edges in the memory graph.
    pub edge_count: u64,
    /// Oldest memory `created_at` (unix epoch secs). `None` if store is empty.
    pub oldest_created_at: Option<i64>,
    /// Newest memory `created_at` (unix epoch secs). `None` if store is empty.
    pub newest_created_at: Option<i64>,
    /// Mean `importance` of active memories. `0.0` when no active memories exist.
    pub avg_importance_active: f64,
    /// Top tags by frequency across active memories, sorted desc (up to 15).
    pub top_tags: Vec<(String, u64)>,
    /// Approximate SQLite file size in bytes. `None` for in-memory stores.
    pub db_size_bytes: Option<u64>,
}

/// Filters for `memory_export` (v0.6). All None = export everything.
#[derive(Debug, Clone, Default)]
pub struct MemoryExportFilter {
    /// Only export memories of this kind.
    pub kind: Option<String>,
    /// Only export memories that carry at least one of these tags.
    pub tags_any: Option<Vec<String>>,
    /// Only export memories with `updated_at >= since_ts` (unix epoch secs).
    pub since_ts: Option<i64>,
    /// When set, also write [`MemoryEdgeExport`] JSONL for edges whose **both**
    /// endpoints appear among the exported memory keys (same filter as rows).
    pub edges_out_path: Option<std::path::PathBuf>,
}

/// Result of [`StateStore::memory_export`].
#[derive(Debug, Clone, Default, Serialize, Deserialize)]
pub struct MemoryExportResult {
    pub memories_written: u64,
    pub edges_written: u64,
}

/// Conflict resolution policy for `memory_import` (v0.6).
#[derive(Debug, Clone, Copy, Default, Serialize, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "snake_case")]
pub enum ImportConflictPolicy {
    /// If a row with the same `key` already exists, leave it alone.
    #[default]
    Skip,
    /// Always overwrite the existing row with the imported one.
    Overwrite,
    /// Overwrite only when the imported `updated_at` is strictly greater.
    NewerWins,
}

/// Per-row outcome of an import.
#[derive(Debug, Clone, Default, Serialize, Deserialize)]
pub struct ImportReport {
    pub inserted: u64,
    pub updated: u64,
    pub skipped: u64,
    pub malformed: u64,
    #[serde(default)]
    pub edges_upserted: u64,
    #[serde(default)]
    pub edges_malformed: u64,
}

#[async_trait]
pub trait StateStore: Send + Sync {
    async fn save_session(&self, session: &StoredSession) -> Result<()>;

    async fn load_session(&self, id: &SessionId) -> Result<Option<StoredSession>>;

    /// List sessions newest-first, capped to `limit` rows. Optional
    /// [`SessionFilter`] narrows the result set.
    async fn list_sessions(&self, filter: &SessionFilter, limit: u32)
        -> Result<Vec<StoredSession>>;

    /// Update an existing session row with its termination outcome.
    /// Implementations should clamp `stdout`/`stderr` to [`STDIO_CAP`] bytes.
    async fn finalise_session(
        &self,
        id: &SessionId,
        ended_at: i64,
        exit_code: Option<i32>,
        stdout: Option<String>,
        stderr: Option<String>,
    ) -> Result<()>;

    async fn append_notification(&self, evt: &NotifyEvent) -> Result<()>;

    async fn recent_notifications(&self, limit: u32) -> Result<Vec<NotificationRecord>>;

    /// Record a failed MCP tool call for [`Self::recent_mcp_tool_errors`].
    /// Messages are truncated; table size is capped at [`MCP_TOOL_ERROR_RING_CAP`].
    async fn record_mcp_tool_error(&self, tool_name: &str, message: &str) -> Result<()>;

    /// Newest-first recent MCP tool errors (`limit` clamped to 1..=500).
    async fn recent_mcp_tool_errors(&self, limit: u32) -> Result<Vec<McpToolErrorRecord>>;

    /// v17: full telemetry — record every MCP `tools/call` (success + failure)
    /// for the observation period that drives the ab-shell decision (see memory
    /// `plan_warp_observation_metrics_20260503`). Default impl is a no-op so
    /// non-SQLite backends degrade gracefully.
    async fn record_mcp_tool_call(
        &self,
        tool_name: &str,
        duration_ms: u32,
        ok: bool,
        args_size: Option<u32>,
        result_size: Option<u32>,
    ) -> Result<()> {
        let _ = (tool_name, duration_ms, ok, args_size, result_size);
        Ok(())
    }

    /// Aggregate stats over `mcp_tool_calls` within the last `window_secs`
    /// seconds, sorted by call count desc. Default impl returns empty.
    async fn mcp_tool_call_stats(
        &self,
        window_secs: i64,
        top_n: u32,
    ) -> Result<Vec<McpToolCallStats>> {
        let _ = (window_secs, top_n);
        Ok(Vec::new())
    }

    // ─── memory.* — agent self-memory (v0.4) ───────────────────────────

    /// Insert or replace a memory by key. Truncates `content` to
    /// [`MEMORY_CONTENT_CAP`]. Updates `updated_at` to `now`; on first insert
    /// `created_at` is also set, `access_count` starts at 0.
    async fn memory_save(&self, mem: &MemoryRecord) -> Result<()>;

    /// Fetch one memory by exact key. Implementations MUST atomically bump
    /// `access_count` and `last_accessed_at` as a side effect of a successful
    /// read (this is what makes "recency" and "frequency" meaningful for
    /// later sorting/compaction).
    async fn memory_get(&self, key: &str) -> Result<Option<MemoryRecord>>;

    /// Substring search over `key` and `content`. Optional tag filter
    /// (matches if ANY tag in `tags_any` is present). Hits are scored by
    /// `matches × recency_weight × log(1 + access_count)`.
    async fn memory_search(
        &self,
        query: &str,
        tags_any: &[String],
        limit: u32,
    ) -> Result<Vec<MemorySearchHit>>;

    /// List memories. `scope` filters to records visible in the given context:
    /// returns records whose scope is None/global OR matches the provided scope.
    /// Pass `scope = None` to skip filtering (return all).
    async fn list_memories(
        &self,
        kind: Option<&str>,
        sort: MemoryListSort,
        limit: u32,
    ) -> Result<Vec<MemoryRecord>>;

    /// List memories visible in a given context scope (e.g. "project:/path").
    /// Returns records with scope=None, scope="global", or scope matching `ctx`.
    async fn list_memories_in_scope(
        &self,
        ctx: &str,
        kind: Option<&str>,
        sort: MemoryListSort,
        limit: u32,
    ) -> Result<Vec<MemoryRecord>>;

    /// Create or update a directed edge between two memory records.
    async fn memory_link(
        &self,
        from_key: &str,
        to_key: &str,
        edge_type: &str,
        weight: f64,
    ) -> Result<()>;

    /// Return all edges where `key` is `from_key` or `to_key`.
    /// Results are ordered by `weight DESC` (highest-weight / most causal first).
    async fn memory_neighbors(&self, key: &str) -> Result<Vec<MemoryEdge>>;

    /// BFS traversal up to `depth` hops from `start_key`.
    /// Returns `(MemoryEdge, energy)` pairs sorted by descending energy.
    /// Energy starts at 1.0 and decays with each hop:
    ///   `energy_next = energy × weight × temporal_bonus(edge_type) × decay_factor`
    /// where `decay_factor` defaults to 0.7. Edges with energy < `min_energy`
    /// are pruned. Implements the AiOT GraphMemoryBridge "ignite" pattern.
    async fn memory_neighbors_bfs(
        &self,
        start_key: &str,
        depth: u8,
        decay_factor: f64,
        min_energy: f64,
    ) -> Result<Vec<(MemoryEdge, f64)>>;

    async fn memory_delete(&self, key: &str) -> Result<bool>;

    /// Hybrid search: FTS5 + graph-neighbor expansion fused with Reciprocal Rank Fusion (RRF, k=60).
    ///
    /// Algorithm (Hermes issue #346 hybrid search pattern):
    /// 1. Run FTS5 search → list A (ranked by bm25 + recency + importance).
    /// 2. For each top-N hit in A, fetch direct graph neighbors.
    /// 3. Build list B from unique neighbor keys (ranked by edge weight × importance).
    /// 4. RRF merge: `score(d) = Σ 1/(k + rank_in_list)` across both lists.
    /// 5. Return top `limit` hits by RRF score, including the `MemoryRecord`.
    ///
    /// `k` defaults to 60 (standard RRF constant). `expand_top` controls how many
    /// FTS5 hits feed into graph expansion (default 10).
    async fn memory_search_hybrid(
        &self,
        query: &str,
        tags_any: &[String],
        limit: u32,
        k: f64,
        expand_top: u32,
    ) -> Result<Vec<MemorySearchHit>>;

    /// Apply importance time-decay: `new_importance = old × 0.5^(days_since_update / half_life)`.
    /// Memories dropping below `archive_threshold` are marked `status='archived'`
    /// and excluded from session_bootstrap. Returns the count of archived rows.
    /// Typical call: `memory_decay_importance(30.0, 0.05)`.
    async fn memory_decay_importance(
        &self,
        half_life_days: f64,
        archive_threshold: f64,
    ) -> Result<u64>;

    /// Apply [`CompactPolicy`]; returns the keys that were (or would be)
    /// removed. Honours `dry_run`.
    async fn memory_compact(&self, policy: CompactPolicy) -> Result<Vec<String>>;

    /// Export memories matching `filter` to a newline-delimited JSON file
    /// (one [`MemoryRecord`] per line). Optionally writes a sibling edge file
    /// when [`MemoryExportFilter::edges_out_path`] is set.
    async fn memory_export(
        &self,
        filter: &MemoryExportFilter,
        out_path: &std::path::Path,
    ) -> Result<MemoryExportResult>;

    /// Import memories from a JSONL file. Each line is parsed as a
    /// [`MemoryRecord`]; malformed lines are counted but do not abort the
    /// import. Conflict resolution per [`ImportConflictPolicy`].
    ///
    /// When `edges_path` is set, each line must parse as [`MemoryEdgeExport`];
    /// rows are upserted into `memory_edges` (`ON CONFLICT` updates `weight` only).
    async fn memory_import(
        &self,
        in_path: &std::path::Path,
        policy: ImportConflictPolicy,
        edges_path: Option<&std::path::Path>,
    ) -> Result<ImportReport>;

    /// Return aggregate statistics about the memory store.
    /// Intended for `memory_stats` MCP tool and session-curate diagnostics.
    async fn memory_stats(&self) -> Result<MemoryStats>;

    /// Semantic search: embed `query` via feature hashing, load all stored
    /// embeddings, return memories ranked by cosine similarity ≥ `threshold`.
    /// Falls back gracefully when no embeddings are stored yet.
    async fn memory_search_semantic(
        &self,
        query: &str,
        limit: u32,
        threshold: f32,
    ) -> Result<Vec<MemorySearchHit>>;

    /// v21 α — Synaptic Trace: record co-activation between memories that
    /// surfaced together in one `memory_search` result.
    ///
    /// `keys` is the ordered list of result keys (caller decides top-K cut).
    /// All ordered pairs (i, j) with i < j (after lexicographic normalization
    /// of keys) get UPSERTed: first time → insert with count=1; subsequent
    /// → count++ and last_at=now. `ctx_centroid` is an optional rolling-mean
    /// embedding (BLOB f32[N]); pass `None` if no embedding context (e.g.
    /// fts/hybrid mode without semantic). Default impl is a no-op so
    /// stores that don't implement this still compile.
    async fn record_coactivation(
        &self,
        _keys: &[String],
        _ctx_centroid: Option<&[f32]>,
    ) -> Result<()> {
        Ok(())
    }

    /// v21 α — Synaptic Trace: return the top-N co-activation edges for
    /// a given memory key, ordered by count DESC. Default returns empty
    /// so older stores keep compiling.
    async fn top_coactivation(
        &self,
        _key: &str,
        _limit: u32,
    ) -> Result<Vec<CoactivationEdge>> {
        Ok(Vec::new())
    }

    /// v21 α — Aggregate health snapshot for the synaptic trace graph,
    /// powering the `agent-bridge dream stats` subcommand and the β
    /// trigger decision (top10/median ratio ≥ 5 indicates clusters).
    /// Default returns an empty snapshot so older stores keep compiling.
    async fn coactivation_stats(&self) -> Result<CoactivationStats> {
        Ok(CoactivationStats {
            total_pairs: 0,
            total_unique_keys: 0,
            max_count: 0,
            median_count: 0.0,
            top10_avg_count: 0.0,
            top10_to_median_ratio: 0.0,
            pairs_last_24h: 0,
            top_5_edges: Vec::new(),
        })
    }

    // ─── v8: cloud-run lifecycle helpers (warp-oz) ──────────────────

    /// Persist the Warp cloud run id for a session after spawn.
    async fn set_cloud_run_id(&self, session_id: &SessionId, run_id: &str) -> Result<()>;

    /// Update the cloud run state + optional session link.
    async fn set_cloud_run_state(
        &self,
        session_id: &SessionId,
        state: &str,
        session_link: Option<&str>,
    ) -> Result<()>;

    // ─── W5: structured plans (SQLite `plans` table) ─────────────────────

    /// Insert or replace a plan (`plan_id` primary key). Updates `updated_at`;
    /// preserves `created_at` on existing rows.
    async fn plan_save(&self, plan_id: &str, title: &str, steps: &[PlanStep]) -> Result<()>;

    /// Load a plan by id.
    async fn plan_load(&self, plan_id: &str) -> Result<Option<PlanRecord>>;

    /// Set `steps[id].status`. Returns `Ok(false)` if plan or step id is missing.
    async fn plan_update_step(&self, plan_id: &str, step_id: &str, status: &str) -> Result<bool>;

    // ─── W6: agent_messages (multi-session) ────────────────────────────────

    /// Append a JSON payload addressed to `to_session`. Returns new row `id`.
    async fn agent_message_send(
        &self,
        from_session: &str,
        to_session: &str,
        payload: &serde_json::Value,
    ) -> Result<i64>;

    /// Poller-friendly inbox: rows for `to_session`, optionally after `since_id`,
    /// optionally unread-only, ordered by id ascending.
    async fn agent_inbox_fetch(
        &self,
        to_session: &str,
        since_id: Option<i64>,
        unread_only: bool,
        limit: u32,
    ) -> Result<Vec<AgentMessageRecord>>;

    // ─── v18: forum / collaboration whiteboard ─────────────────────────────

    /// Create a new thread (when `thread_id` is None) or append a post to an
    /// existing one. `author` must be non-empty (caller-provided session id).
    /// `refs` is opaque JSON — typically `{memory_keys:[...], files:[...],
    /// parent_post_id:N}`.
    async fn forum_post(
        &self,
        thread_id: Option<i64>,
        board: Option<&str>,
        title: Option<&str>,
        author: &str,
        kind: &str,
        body: &str,
        refs: Option<&serde_json::Value>,
        tags: Option<&[String]>,
    ) -> Result<ForumPostOutcome> {
        let _ = (
            thread_id, board, title, author, kind, body, refs, tags,
        );
        Err(ab_core::Error::Backend("forum_post not implemented".into()))
    }

    /// Read posts from a thread (when `thread_id` is set) or across a board
    /// (when `board` is set). Cursor: `since_post_id` (exclusive). When
    /// `unread_for` is set the cursor is inferred from `forum_subscriptions`
    /// (ignored if no subscription row exists). Limit clamped to 1..=500.
    ///
    /// Auto-advance is **scope-symmetric**: a thread-scoped read only advances
    /// a *thread* subscription cursor (never the board cursor — that would
    /// wrongly mark unread posts in sibling threads as seen). To get unread
    /// tracking on a thread, subscribe with `scope_kind = "thread"`.
    async fn forum_read(
        &self,
        thread_id: Option<i64>,
        board: Option<&str>,
        since_post_id: Option<i64>,
        unread_for: Option<&str>,
        limit: u32,
    ) -> Result<Vec<ForumPostRecord>> {
        let _ = (thread_id, board, since_post_id, unread_for, limit);
        Err(ab_core::Error::Backend("forum_read not implemented".into()))
    }

    /// Subscribe `session_id` to a thread or board. Idempotent: re-subscribing
    /// preserves existing `last_seen_post_id` unless `reset` is true.
    /// `scope_kind` must be `"thread"` or `"board"`.
    async fn forum_subscribe(
        &self,
        session_id: &str,
        scope_kind: &str,
        scope_value: &str,
        reset: bool,
    ) -> Result<()> {
        let _ = (session_id, scope_kind, scope_value, reset);
        Err(ab_core::Error::Backend(
            "forum_subscribe not implemented".into(),
        ))
    }

    /// Mark `session_id` as having seen up to `post_id` (for the matching
    /// thread or board subscription). Used by `forum_read` to advance cursor
    /// and by explicit ack flows.
    async fn forum_mark_seen(
        &self,
        session_id: &str,
        scope_kind: &str,
        scope_value: &str,
        post_id: i64,
    ) -> Result<()> {
        let _ = (session_id, scope_kind, scope_value, post_id);
        Err(ab_core::Error::Backend(
            "forum_mark_seen not implemented".into(),
        ))
    }

    /// List threads on a board, ordered by `last_post_at DESC`. When
    /// `unread_for` is set, each row's `unread_count` is filled relative to
    /// that session's subscription cursors (board-level OR per-thread).
    async fn forum_list_threads(
        &self,
        board: &str,
        unread_for: Option<&str>,
        status: Option<&str>,
        limit: u32,
    ) -> Result<Vec<ForumThreadRecord>> {
        let _ = (board, unread_for, status, limit);
        Err(ab_core::Error::Backend(
            "forum_list_threads not implemented".into(),
        ))
    }

    /// Update thread status (`open` | `resolved` | `archived`).
    /// Export every forum thread (with its posts) to a JSONL file. One thread
    /// per line; posts are nested inside their thread. Subscriptions are not
    /// included (each device has its own read cursors). Used by
    /// `agent-bridge sync` for cross-device collaboration.
    async fn forum_export(
        &self,
        out_path: &std::path::Path,
    ) -> Result<ForumExportResult> {
        let _ = out_path;
        Err(ab_core::Error::Backend(
            "forum_export not implemented".into(),
        ))
    }

    /// Import threads + posts from a JSONL file produced by `forum_export`.
    /// Idempotent: threads are matched by `(board, created_by, created_at,
    /// title)`; posts are matched by `(thread, author, created_at, body)`.
    /// On match, existing local row is reused; on no match, new row is
    /// inserted. `last_post_at` is updated to `max(local, remote)`.
    async fn forum_import(
        &self,
        in_path: &std::path::Path,
    ) -> Result<ForumImportReport> {
        let _ = in_path;
        Err(ab_core::Error::Backend(
            "forum_import not implemented".into(),
        ))
    }

    async fn forum_set_thread_status(&self, thread_id: i64, status: &str) -> Result<()> {
        let _ = (thread_id, status);
        Err(ab_core::Error::Backend(
            "forum_set_thread_status not implemented".into(),
        ))
    }

    // ─── v19: agent presence registry ──────────────────────────────────────

    /// Upsert a presence row keyed by `session_id`. Refreshes
    /// `last_heartbeat_at`. On insert, all required cols (`name`, `node`,
    /// `project`, `role`) must be supplied via `upsert`. On update, fields set
    /// to `None` keep their prior value so heartbeat-only calls are cheap.
    async fn agent_presence_announce(
        &self,
        session_id: &str,
        upsert: AgentPresenceUpsert<'_>,
    ) -> Result<AgentPresenceRecord> {
        let _ = (session_id, upsert);
        Err(ab_core::Error::Backend(
            "agent_presence_announce not implemented".into(),
        ))
    }

    /// List active presence rows (heartbeat ≥ now − `max_idle_secs`).
    /// `max_idle_secs = 0` means no TTL filter. Optional filters on
    /// `project` and `role`. Limit clamped 1..=500.
    async fn agent_presence_list(
        &self,
        project: Option<&str>,
        role: Option<&str>,
        max_idle_secs: i64,
        limit: u32,
    ) -> Result<Vec<AgentPresenceRecord>> {
        let _ = (project, role, max_idle_secs, limit);
        Err(ab_core::Error::Backend(
            "agent_presence_list not implemented".into(),
        ))
    }

    /// Look up a single presence row by `session_id`. Used by
    /// `session_identity` to auto-tag when a fresh sibling already holds
    /// the proposed canonical id. Default impl returns `Ok(None)` so
    /// non-SQLite backends fall back to the pure-helper behavior.
    async fn agent_presence_get(
        &self,
        session_id: &str,
    ) -> Result<Option<AgentPresenceRecord>> {
        let _ = session_id;
        Ok(None)
    }

    /// D2.3: load all active memories with embeddings into an in-process cache.
    /// Returns `(record, embedding)` pairs. Default impl returns an empty vec
    /// so non-SQLite backends degrade gracefully.
    async fn memory_load_embeddings(&self) -> Result<Vec<(MemoryRecord, Vec<f32>)>> {
        Ok(Vec::new())
    }

    /// Re-compute embeddings for all active memories that have `embedding IS NULL`.
    /// Processes up to `batch_size` rows per call; returns the number of rows updated.
    /// Default impl returns 0 (no-op for non-SQLite backends).
    async fn memory_reindex_embeddings(&self, batch_size: usize) -> Result<usize> {
        let _ = batch_size;
        Ok(0)
    }

    // ── D3.2: codebase symbol index ──────────────────────────────────────────

    /// Scan `root_path`, extract symbols from files matching `languages`
    /// (e.g. `["rust", "python"]`; empty = all supported), and persist them
    /// to the `codebase_symbols` table. Previous symbols for the same root
    /// are replaced.
    async fn codebase_index(
        &self,
        root_path: &str,
        languages: &[String],
    ) -> Result<CodebaseIndexStats> {
        let _ = (root_path, languages);
        Err(ab_core::Error::Backend(
            "codebase_index not implemented".into(),
        ))
    }

    /// Search indexed symbols by name/signature substring or semantic similarity.
    ///
    /// - `query` — substring (exact) or natural-language description (semantic).
    /// - `kind` — optional exact filter (`fn`, `struct`, `class`, …).
    /// - `file_filter` — optional substring matched against `file_path`.
    /// - `root_path` — optional exact root to restrict results.
    /// - `limit` — capped to 500.
    /// - `mode` — `"exact"` (substring LIKE, default) or `"semantic"` (cosine similarity).
    async fn codebase_search(
        &self,
        query: &str,
        kind: Option<&str>,
        file_filter: Option<&str>,
        root_path: Option<&str>,
        limit: u32,
        mode: &str,
    ) -> Result<Vec<CodebaseSymbol>> {
        let _ = (query, kind, file_filter, root_path, limit, mode);
        Err(ab_core::Error::Backend(
            "codebase_search not implemented".into(),
        ))
    }
}

#[cfg(test)]
mod session_handoff_order_tests {
    use super::*;

    fn rec(key: &str, kind: &str) -> MemoryRecord {
        MemoryRecord {
            key: key.into(),
            kind: kind.into(),
            content: String::new(),
            tags: vec![],
            related_keys: vec![],
            scope: None,
            created_at: 0,
            updated_at: 0,
            last_accessed_at: 0,
            access_count: 0,
            importance: 0.5,
            status: "active".into(),
            trigger_pattern: None,
        }
    }

    #[test]
    fn prioritize_session_handoff_floats_continuity_first() {
        let rows = vec![
            rec("l1", "lesson"),
            rec("h1", "session_handoff"),
            rec("d1", "decision"),
        ];
        let out = prioritize_session_handoff(rows);
        assert_eq!(
            out.iter().map(|r| r.key.as_str()).collect::<Vec<_>>(),
            vec!["h1", "l1", "d1"]
        );
    }

    #[test]
    fn prioritize_session_handoff_preserves_order_within_tiers() {
        let rows = vec![
            rec("h2", "session_handoff"),
            rec("h1", "session_handoff"),
            rec("a", "lesson"),
        ];
        let out = prioritize_session_handoff(rows);
        assert_eq!(
            out.iter().map(|r| r.key.as_str()).collect::<Vec<_>>(),
            vec!["h2", "h1", "a"]
        );
    }
}
