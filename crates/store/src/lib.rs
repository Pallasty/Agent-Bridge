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

/// Cap on `memory_query_log` rows (Phase 0 memory telemetry). Older rows are
/// pruned each `record_memory_query` call, FIFO. ~7 days of moderate use at
/// 5k rows; tune via design review when telemetry exposes traffic shape.
pub const MEMORY_QUERY_LOG_RING_CAP: i64 = 5_000;

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
    /// **Phase 1 P2** — When this row was auto-marked `status='superseded'`
    /// by `memory_save` (see `auto_supersede_threshold`), this points at the
    /// replacement row's key. `None` for active records and for records that
    /// were superseded manually without going through the auto-detect path.
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub superseded_by: Option<String>,
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
    /// **ε-2 (2026-05-11)** — pairs whose `last_at - first_at` is < 1 hour.
    /// Self-archaeology found that 95% of pairs are "investigation bursts"
    /// (co-occurred in a single tight session) rather than cross-session
    /// repeated firings. Surfacing this distinguishes "wired through repeat
    /// firing over days" from "co-appeared in one search burst".
    #[serde(default)]
    pub pairs_burst_lt_1h: u64,
    /// **ε-2** — pairs whose `last_at - first_at` is ≥ 6 hours. These are
    /// the persistent associations β-Hebbian was *originally meant* to
    /// crystallise: edges that fire across investigation sessions.
    #[serde(default)]
    pub pairs_persistent_ge_6h: u64,
    /// **ε-2** — top-5 pairs filtered to `last_at - first_at >= 6h`. Catches
    /// cross-session attractors that the raw `top_5_edges` (sorted by
    /// count) misses when burst-pairs dominate. Same shape as `top_5_edges`.
    #[serde(default)]
    pub top_5_persistent_edges: Vec<CoactivationEdge>,
}

/// **ζ-9 (2026-05-12)** — Graph topology snapshot. Single output of
/// [`StateStore::graph_topology`]. Designed for `dream snapshot` schema
/// v2's `topology` section: orphan rate, degree distribution, top hubs,
/// P4 evolved coverage. Cheap (4 small SQL passes), suitable for daily
/// capture.
///
/// Catches the blind spot `finding_graph_orphan_topology_20260511`
/// surfaced manually: 60% orphan rate was invisible to existing
/// snapshot/dream-stats output.
#[derive(Debug, Clone, Default, Serialize, Deserialize, PartialEq)]
pub struct GraphTopology {
    /// Active non-skill memories (denominator for orphan_pct).
    pub non_skill_active_total: u64,
    /// Active non-skill memories with **zero** edges in `memory_edges`.
    pub orphan_count: u64,
    /// Histogram of node degrees (in+out edges). Buckets:
    /// `"0"`, `"1"`, `"2-3"`, `"4-5"`, `"6-10"`, `"11-20"`, `"21+"`.
    /// Ordered as listed; zero-count buckets are still included for
    /// stable diff alignment.
    pub degree_histogram: Vec<(String, u64)>,
    /// Top-5 nodes by total degree, non-skill active only. (key, degree).
    pub top_5_hubs: Vec<(String, u64)>,
    /// Number of active non-skill memories with at least one `evolved`
    /// edge. P4 coverage indicator — divides over `non_skill_active_total`
    /// to read as percentage at the caller.
    pub p4_evolved_coverage: u64,
}

/// One window of "what did self look like during these N days" — the
/// behavioral fingerprint output of [`StateStore::identity_window`].
/// Two of these (current vs prior) compose an identity-continuity delta
/// per design doc §5: "today-self vs last-week-self".
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub struct IdentityWindow {
    pub window_start: i64,
    pub window_end: i64,
    pub tool_calls_total: u64,
    pub tool_calls_ok: u64,
    /// (tool_name, call_count) for top tools, count DESC, capped to 10.
    pub top_tools: Vec<(String, u64)>,
    pub forum_posts: u64,
    /// (kind, count) sorted by kind for stable diff.
    pub forum_kinds: Vec<(String, u64)>,
    pub forum_avg_body_len: f64,
    pub memory_saves: u64,
}

/// One persisted query against the memory subsystem — a single row written
/// by `memory_search` / `memory_get` for **Phase 0 telemetry**. The point is
/// not "audit log" but "what fraction of recalls actually find anything",
/// "how stale are the hits we return", "where are we slow".
///
/// One row per user-facing query at the MCP layer; internal calls (e.g.
/// `session_curate` walking the store) MUST NOT log here, otherwise
/// hit-rate is inflated by self-traffic.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub struct MemoryQueryRecord {
    /// Operation: `"search_fts"` | `"search_hybrid"` | `"search_semantic"` | `"get"`.
    pub kind: String,
    /// The query string (search) or the looked-up key (`get`). Trimmed to
    /// 256 bytes by the impl — we don't need full-text logs.
    pub query: String,
    /// Optional tag filter as JSON array text (`"[]"` if none). Same 256 cap.
    pub tags_json: String,
    /// How many results came back. `0` for misses (the most useful row).
    pub hit_count: u32,
    /// `last_accessed_at` of the top hit at the time the row is logged —
    /// `None` for misses or `get(missing_key)`. Useful for "are we mostly
    /// surfacing stale memories" diagnostics.
    pub top_hit_age_secs: Option<i64>,
    /// `created_at` of the top hit at the time the row is logged — `None`
    /// for misses. Pairs with `top_hit_age_secs` to spot "we keep returning
    /// 30-day-old hits even for new queries" patterns.
    pub top_hit_created_at: Option<i64>,
    /// Wall-clock latency in microseconds (Instant::now() pre/post).
    pub duration_us: u32,
    /// Caller hint, e.g. `"mcp:memory_search"` / `"mcp:memory_get"`. Free-form.
    pub source: String,
    /// When the row was written (unix epoch secs).
    pub at: i64,
}

/// Aggregate statistics over a window of `memory_query_log` rows. Output of
/// [`StateStore::memory_query_stats`]. The numbers we actually need to drive
/// Phase 1 design decisions:
///
/// * `hit_rate` → are most queries finding nothing? then ranking is broken
/// * `avg_top_hit_age_days` → are we surfacing stale memories?
/// * `p95_duration_us` → is recall fast enough for chains?
/// * `top_miss_queries` → what to fix in next ranker iteration
#[derive(Debug, Clone, Default, Serialize, Deserialize, PartialEq)]
pub struct MemoryQueryStats {
    /// Window start (unix epoch secs) — the earliest row counted.
    pub window_start: i64,
    /// Window end (unix epoch secs) — the latest row counted.
    pub window_end: i64,
    pub total_queries: u64,
    pub hits: u64,
    pub misses: u64,
    /// `hits / total_queries` (0.0 if total=0).
    pub hit_rate: f64,
    /// Mean age in seconds of top hit at recall time, across hit rows only.
    pub avg_top_hit_age_secs: f64,
    /// p50 / p95 latency across all rows (microseconds).
    pub p50_duration_us: u32,
    pub p95_duration_us: u32,
    /// Per-kind counts (`search_fts`, `search_hybrid`, `search_semantic`, `get`).
    pub by_kind: Vec<(String, u64)>,
    /// Top miss queries (hit_count = 0), most-recurring first, capped to 10.
    pub top_miss_queries: Vec<(String, u64)>,
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
    /// Phase 2 #3 second slice — imports/uses extracted alongside symbols.
    /// Counted across all languages that have an importer (Rust as of v24).
    #[serde(default)]
    pub imports: u32,
    /// Phase 2 #3 third slice — call sites extracted alongside symbols.
    /// Counted across all languages that have a call extractor (Rust as
    /// of v25).
    #[serde(default)]
    pub calls: u32,
    pub duration_ms: u64,
    pub root_path: String,
}

/// One `use` / `import` statement extracted from a source file. First slice
/// of the cross-language reference graph (Phase 2 #3 second part) — the
/// goal is to let `codebase_search` resolve "who imports X" and eventually
/// "who calls X" without re-walking source.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct CodebaseImport {
    pub file_path: String,
    pub line: u32,
    pub language: String,
    /// Raw source text of the statement (first ~200 chars), e.g.
    /// `use crate::store::SqliteStore;`.
    pub raw: String,
    /// Normalized import path, e.g. `crate::store::SqliteStore` for Rust
    /// or `os.path` for Python. One row per imported item — group imports
    /// like `use a::{b, c}` expand to two rows (`a::b`, `a::c`).
    pub target: String,
    /// `use foo as bar` → `Some("bar")`. None when no alias.
    #[serde(skip_serializing_if = "Option::is_none")]
    pub alias: Option<String>,
}

/// One call site extracted from a function body. Third slice of Phase 2 #3
/// — joins symbols (callers) and imports (callees) so the codebase graph
/// can answer "what calls X" / "what does Y call" without re-walking
/// source. Callee resolution is callee-textual: a call site to `foo` is
/// emitted with callee=`foo`, and the actual cross-file resolution
/// happens at query time by joining against `codebase_symbols` (defs)
/// and `codebase_imports` (in-scope aliases).
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct CodebaseCall {
    pub file_path: String,
    pub line: u32,
    pub language: String,
    /// Qualified name of the enclosing function, mirroring
    /// [`CodebaseSymbol::name`] convention for trait/impl methods
    /// (e.g. `Foo::bar`, `<Foo as Bar>::baz`). Empty when the call
    /// occurs at file scope (rare in Rust; common in scripts).
    pub caller: String,
    /// Raw callee identifier as written at the call site. May be a bare
    /// name (`foo`), a qualified path (`Foo::bar`), or a method call
    /// prefixed with `.` (`.method` for `obj.method(...)`).
    pub callee: String,
}

/// One alias-resolved call site — output of [`StateStore::codebase_callers`].
/// Same fields as [`CodebaseCall`] plus the resolved fully-qualified
/// callee (rewritten through the in-scope `use` alias) and the alias
/// that brought the import into scope (when applicable).
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ResolvedCall {
    pub file_path: String,
    pub line: u32,
    pub language: String,
    pub caller: String,
    /// As-written callee at the call site (e.g. `Baz::new` from a
    /// `use foo::Bar as Baz`).
    pub callee: String,
    /// Fully-qualified callee after alias rewrite (e.g. `foo::Bar::new`).
    /// When emitted from [`StateStore::codebase_callers`] this is the
    /// path that the call resolved TO — equal to the user's `target`
    /// argument or a longer suffix of it.
    pub resolved_callee: String,
    /// Local alias that brought the import into scope. `None` when the
    /// import was a plain `use` (last segment used as the local name).
    #[serde(skip_serializing_if = "Option::is_none")]
    pub via_alias: Option<String>,
    /// The `use`/`import` target that resolved this call. Useful for
    /// debugging why a particular call was matched.
    pub via_import: String,
}

/// Aggregate view of the `codebase_calls` table for a single index root.
/// Output of [`StateStore::codebase_call_stats`]; consumed by
/// `dream codebase-report --html` to render the audit page. Computed
/// against a single `root_path` so cross-project pollution is impossible.
///
/// Caveat: `hot_callees` / `orphan_functions` rely on raw textual `callee`
/// matching — they are alias-blind (a call to `Baz::new` after
/// `use Foo::Bar as Baz` shows up under `Baz`, not `Foo::Bar`). Use
/// [`StateStore::codebase_callers`] when you need alias-resolved lookups.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct CodebaseCallStats {
    pub root_path: String,
    pub total_calls: u64,
    pub distinct_caller_files: u64,
    pub per_language: Vec<LanguageCallCount>,
    pub hot_callees: Vec<HotCallee>,
    pub hot_callers: Vec<HotCaller>,
    /// Function/method symbols whose last-segment name never appears as a
    /// callee in `codebase_calls` for the same root. Best-effort "dead
    /// code" candidates — false positives include trait-object dispatch,
    /// reflection/string-key dispatch, FFI exports, and tests-only entry
    /// points. Capped to `top_n`.
    pub orphan_functions: Vec<OrphanFunction>,
    /// Per-file fan-out — files that issue the most distinct callees.
    /// Proxy for module coupling.
    pub fan_out_files: Vec<FileFanOut>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct LanguageCallCount {
    pub language: String,
    pub call_count: u64,
    pub distinct_files: u64,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct HotCallee {
    pub callee: String,
    pub call_count: u64,
    pub distinct_callers: u64,
    /// Sorted distinct language tags that issue calls to this name.
    pub languages: Vec<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct HotCaller {
    pub caller: String,
    pub file_path: String,
    pub language: String,
    pub total_calls: u64,
    pub distinct_callees: u64,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct OrphanFunction {
    pub name: String,
    pub kind: String,
    pub file_path: String,
    pub language: String,
    pub line: u32,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct FileFanOut {
    pub file_path: String,
    pub language: String,
    pub total_calls: u64,
    pub distinct_callees: u64,
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

/// Result of `memory_decay_unused_importance` — read-recency-based decay.
/// Distinct from `memory_decay_importance` (which decays by `updated_at`,
/// i.e. "hasn't evolved"); this one captures "hasn't been useful" via
/// `last_accessed_at`. Together they cover both edges of memory hygiene:
/// stale-write (compact target) and stale-read (Palace C7/C8 target).
#[derive(Debug, Clone, Copy, Default, Serialize, Deserialize)]
pub struct DecayUnusedStats {
    /// Active rows whose `last_accessed_at > 0` and is older than the
    /// window cutoff (i.e. "matched the unused predicate").
    pub candidates: u64,
    /// Rows whose `importance` was actually reduced this pass (above floor
    /// and the SQL UPDATE touched them).
    pub decayed: u64,
    /// Candidates already at or below the floor — counted but not decayed.
    pub skipped_at_floor: u64,
}

/// Counts emitted by `memory_reinforce_active` — the positive-reinforcement
/// mirror of `memory_decay_unused_importance`. Active rows with
/// `access_count >= min_access` and `last_accessed_at` within the window
/// get their `importance` bumped by `step`, capped at `ceiling`.
///
/// Why it exists: prior to this op the system was entropy-monotonic. Three
/// passes (`memory_compact`, `memory_decay_importance`, `memory_decay_unused_importance`)
/// could only LOWER `importance`. Repeatedly-accessed memories were
/// indistinguishable from inert ones once decay had cratered everything.
/// Hebbian "cells that fire together wire together" needs a wire-strengthen
/// step — this is it for single-node importance (the wire-strengthen for
/// pairs is `dream promote`).
#[derive(Debug, Clone, Copy, Default, Serialize, Deserialize)]
pub struct ReinforceActiveStats {
    /// Active rows whose `access_count >= min_access` AND
    /// `last_accessed_at > cutoff` (i.e. "matched the active predicate").
    pub candidates: u64,
    /// Rows whose `importance` was actually raised this pass (below ceiling
    /// and the SQL UPDATE touched them).
    pub reinforced: u64,
    /// Candidates already at or above the ceiling — counted but not bumped.
    pub skipped_at_ceiling: u64,
}

/// One row in [`SignalFidelityStats::under_reinforced`] /
/// [`SignalFidelityStats::over_promoted`]. Surfaces a single memory whose
/// `importance` rank disagrees most strongly with its `access_count` rank.
/// Under-reinforced rows are candidates for a manual `reinforce-active`
/// bump; over-promoted rows are candidates for `decay-unused`-or-tombstone
/// review.
#[derive(Debug, Clone, Default, Serialize, Deserialize)]
pub struct MisrankRow {
    pub key: String,
    pub importance: f64,
    pub access_count: u64,
    /// 1-based fractional rank (ties averaged) over all active rows.
    pub rank_importance: f64,
    pub rank_access: f64,
    /// `rank_importance - rank_access`. Positive = over-promoted (high
    /// importance, low access); negative = under-reinforced.
    pub rank_diff: f64,
}

/// Aggregate of the `dream signal-fidelity` probe: how well does
/// `importance` actually predict observed access? Computed by Spearman
/// rank correlation (Pearson on rank-transformed vectors with ties
/// averaged) over all active memories — robust to the heavy left-cluster
/// at the importance floor and the right-skew of access counts.
///
/// Interpretation:
/// - `spearman_r ≈ 0.0` — importance is noise: ranking doesn't predict
///   access. Expected baseline pre-`reinforce-active` because decay had
///   flattened importance to the floor.
/// - `spearman_r ≈ 0.4-0.6` — meaningful signal: the Hebbian closure
///   produced informative ranks.
/// - `spearman_r > 0.7` — strong signal: importance is a reliable
///   retrieval prior.
///
/// Pairs longitudinally: baseline before `reinforce-active` has had time
/// to work, re-run after N cron cycles, observe drift.
#[derive(Debug, Clone, Default, Serialize, Deserialize)]
pub struct SignalFidelityStats {
    /// Total active memories considered.
    pub total_active: u64,
    /// Spearman rank correlation between `importance` and `access_count`.
    /// Range `[-1.0, 1.0]`. `NaN` if `total_active < 2` or either vector
    /// has zero variance.
    pub spearman_r: f64,
    /// Same correlation but restricted to memories with
    /// `access_count > 0` — strips bootstrap-imported never-read rows
    /// that would otherwise dominate the rank distribution at 0.
    pub spearman_r_touched: f64,
    /// Number of rows considered after the `access_count > 0` filter.
    /// `spearman_r_touched`'s denominator.
    pub n_touched: u64,
    /// Memories with `access_count = 0`. Dominated by markdown imports
    /// and bootstrap inserts that were never retrieved.
    pub n_zero_access: u64,
    /// Memories at or below `importance = 0.11` (decay-unused floor + ε).
    /// High count here is the "everyone got crushed by decay" tell.
    pub n_floor_importance: u64,
    /// Mean importance across all active rows.
    pub mean_importance: f64,
    /// Mean access_count across all active rows.
    pub mean_access: f64,
    /// Top-N memories with `access_count` rank much higher than
    /// `importance` rank. Reinforce-active should be pulling these up.
    pub under_reinforced: Vec<MisrankRow>,
    /// Top-N memories with `importance` rank much higher than
    /// `access_count` rank. Candidates for review (stale-but-pinned).
    pub over_promoted: Vec<MisrankRow>,
}

/// One per-summary row in [`ReplayAuditStats::top_summaries`] /
/// [`ReplayAuditStats::dead_weight_summaries`]. Captures the post-creation
/// fate of a single replay-generated summary.
#[derive(Debug, Clone, Default, Serialize, Deserialize)]
pub struct ReplayAuditRow {
    pub key: String,
    pub created_at: i64,
    pub last_accessed_at: i64,
    pub access_count: u64,
    /// `now - created_at` in seconds at audit time. Snapshotted into the
    /// row so a JSON dump is self-contained.
    pub age_secs: i64,
}

/// Temporal-relation classification for one replay summary. Built by
/// scanning `memory_query_log` (kind='get' events) and pairing each
/// `get(summary)` event with `get(summary_source)` events within
/// [`WaypointStats::window_secs`].
///
/// Interpretation:
/// - `gateway`  — `leading_pairs > trailing_pairs`. User touched the
///                summary first, then the source(s). Summary is acting
///                as an attention entrypoint.
/// - `trailing` — `trailing_pairs > leading_pairs`. User touched the
///                source(s) first, summary touched after. Summary is
///                decoration / acknowledgement, not entrypoint.
/// - `ambiguous`— equal counts, both > 0. Bidirectional or insufficient
///                signal to call it.
/// - `isolated` — summary itself had `get` events but no source-get
///                fell within the window. Recall happened independently
///                of source recall in this window. Counted separately
///                in [`WaypointStats::isolated_summaries`] (not in `rows`).
#[derive(Debug, Clone, Default, Serialize, Deserialize)]
pub struct WaypointRow {
    pub key: String,
    pub leading_pairs: u64,
    pub trailing_pairs: u64,
    pub pairs_total: u64,
    pub classification: String,
}

/// One pair of replay summaries whose `summarizes`-edge source sets
/// overlap above the caller-supplied Jaccard threshold. Surfaces orphan
/// duplicates from pre-Phase-2-#2 keys that skipped canonical-key
/// dedupe — e.g. two summaries on the same cluster with different
/// human-readable keys.
///
/// `classification_a` / `classification_b` are populated from the
/// waypoint pass if both passes ran (window > 0). When two duplicate
/// summaries land on different waypoint sides (e.g. one gateway, one
/// trailing) it's strong evidence the role is access-order-driven
/// rather than cluster-shape-driven.
#[derive(Debug, Clone, Default, Serialize, Deserialize)]
pub struct OverlapPair {
    pub key_a: String,
    pub key_b: String,
    /// Count of distinct sources that both summaries point to.
    pub shared_sources: u64,
    /// `|sources(a)|` — total distinct sources for `key_a`.
    pub size_a: u64,
    /// `|sources(b)|` — total distinct sources for `key_b`.
    pub size_b: u64,
    /// `shared / (size_a + size_b - shared)`. Range `(0, 1]`.
    pub jaccard: f64,
    /// Waypoint classification of `key_a` if available.
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub classification_a: Option<String>,
    /// Waypoint classification of `key_b` if available.
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub classification_b: Option<String>,
}

/// Aggregate of [`WaypointRow`] across all replay summaries that had at
/// least one `get` event in the trace. Surfaces the gateway-vs-decoration
/// breakdown — answers "do summaries cause source access, or just
/// trail it?"
#[derive(Debug, Clone, Default, Serialize, Deserialize)]
pub struct WaypointStats {
    /// Pairing window in seconds. Caller-controlled; 1800 (30 min) is
    /// the typical session-locality default.
    pub window_secs: i64,
    /// Summaries that had at least one paired source-get in the window
    /// (i.e. `rows.len()`). Denominator for the classification ratios.
    pub summaries_with_pairs: u64,
    /// Summaries that had `get` events but no source-get within the
    /// window. Independent recall — not part of a topical session.
    pub isolated_summaries: u64,
    /// `leading_pairs > trailing_pairs` — gateway pattern.
    pub gateway_summaries: u64,
    /// `trailing_pairs > leading_pairs` — decoration pattern.
    pub trailing_summaries: u64,
    /// `leading_pairs == trailing_pairs` with both > 0 — bidirectional.
    pub ambiguous_summaries: u64,
    /// Per-summary detail rows (gateway/trailing/ambiguous only, sorted
    /// by `pairs_total` desc). Isolated summaries omitted to keep the
    /// detail list focused on summaries actually carrying signal.
    pub rows: Vec<WaypointRow>,
}

/// Aggregate health of `dream replay` output. Are LLM-consolidated summary
/// memories actually being used after creation? This is the audit surface
/// for that question — pairs with `dream replay-audit` CLI.
///
/// Identifies summaries by tag `p5_replay` (set unconditionally by
/// `dream_replay::apply_summary`). Source comparison walks the
/// `summarizes` edge type.
#[derive(Debug, Clone, Default, Serialize, Deserialize)]
pub struct ReplayAuditStats {
    /// Total active summaries (tag `p5_replay`, status='active').
    pub total_summaries: u64,
    /// `access_count = 0` — never touched after creation.
    pub never_accessed: u64,
    /// `access_count = 1` — likely just the post-creation auto-bump
    /// (or one curious follow-up read).
    pub accessed_once: u64,
    /// `access_count >= 2` — repeated use, evidence of real value.
    pub accessed_multi: u64,
    /// `access_count = 0` AND `created_at` older than the audit's
    /// `stale_days` threshold. The "dead weight" tally — LLM cost
    /// paid, no recall ever happened.
    pub stale_dead: u64,
    /// Mean `access_count` across all summaries.
    pub avg_access_count: f64,
    /// Mean age (seconds) across all summaries.
    pub avg_age_secs: f64,
    /// Distinct source memories (`summarizes` edge endpoints, active).
    pub source_count: u64,
    /// Mean `access_count` across distinct source memories. Compare
    /// against `avg_access_count` — if summaries clearly out-access
    /// sources, replay is creating real abstractions; if not, users
    /// are still going to the raw rows.
    pub avg_source_access_count: f64,
    /// Up to 5 summaries by descending `access_count` — the wins.
    pub top_summaries: Vec<ReplayAuditRow>,
    /// Up to 5 `access_count=0` summaries by ascending `created_at` —
    /// the oldest unused (most likely dead weight).
    pub dead_weight_summaries: Vec<ReplayAuditRow>,
    /// Optional temporal-classification block. `None` when the caller
    /// passes `waypoint_window_secs <= 0` to
    /// [`StateStore::replay_audit_stats`]. See [`WaypointStats`].
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub waypoint: Option<WaypointStats>,
    /// Pairs of active replay summaries sharing source-sets above the
    /// caller-supplied Jaccard threshold. Empty when the caller passed
    /// `overlap_min_jaccard <= 0.0`. See [`OverlapPair`].
    #[serde(default, skip_serializing_if = "Vec::is_empty")]
    pub overlap_pairs: Vec<OverlapPair>,
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
    /// When set, also write [`MemoryEdgeExport`] JSONL for edges whose
    /// endpoints satisfy the membership rule below.
    pub edges_out_path: Option<std::path::PathBuf>,
    /// Edge filter mode. `false` (default, strict) = both endpoints must be
    /// in the exported set; an edge to a non-exported node is dropped (this
    /// is the original v0.6 contract). `true` (loose) = keep edges where
    /// *either* endpoint is in the set; the cross-set endpoint may not exist
    /// on the import side and will be dropped + counted by `memory_import`.
    /// Loose mode unblocks narrow-filter exports (e.g. `kind=chat_session`)
    /// that have edges to nodes living under other filters.
    pub loose_edges: bool,
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
    /// Edges where one or both endpoints did not exist in the destination
    /// `memories` table at import time. These are skipped rather than upserted
    /// — keeping the rule "no dangling refs in the graph". Counted here so
    /// callers can decide whether to re-export the missing endpoints.
    #[serde(default)]
    pub edges_skipped_dangling: u64,
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

    /// Read-recency decay: shave `step` off `importance` for every active
    /// row whose `last_accessed_at > 0` and is older than the window cutoff,
    /// floored at `floor`. Mirrors the C7 / C8 staleness model — what
    /// hasn't been *read* loses its rank in retrieval, even if it was
    /// recently written. Skips rows with `last_accessed_at = 0` (markdown
    /// imports / never-accessed rows) so first-time saves don't take a hit
    /// before they've had a chance to surface.
    ///
    /// Typical call: `memory_decay_unused_importance(30 * 86400, 0.05, 0.1)`
    /// (30-day window, 5% step, 0.1 floor).
    async fn memory_decay_unused_importance(
        &self,
        window_secs: i64,
        step: f64,
        floor: f64,
    ) -> Result<DecayUnusedStats>;

    /// Positive-reinforcement mirror of [`Self::memory_decay_unused_importance`].
    /// Bumps `importance` by `step` (capped at `ceiling`) for every active
    /// row that has `access_count >= min_access` AND was read within the
    /// window (`last_accessed_at > now - window_secs`).
    ///
    /// Designed to compose with the daily hygiene service alongside
    /// `decay-unused` and `prune-coactivation-noise`: those two only
    /// remove signal, this one rewards repeat use so frequently-touched
    /// memories don't get crushed to the floor by background decay.
    ///
    /// Rows with `last_accessed_at = 0` are skipped (markdown imports
    /// and never-accessed rows can't be reinforced even if their
    /// `access_count > 0` due to bootstrap inserts).
    ///
    /// Typical call: `memory_reinforce_active(7 * 86400, 5, 0.05, 0.95)`
    /// (7-day window, ≥5 accesses, 5% step, 0.95 ceiling).
    async fn memory_reinforce_active(
        &self,
        window_secs: i64,
        min_access: u64,
        step: f64,
        ceiling: f64,
    ) -> Result<ReinforceActiveStats>;

    /// Compute Spearman rank correlation between `importance` and
    /// `access_count` over active memories. Pure read pass — no writes.
    /// Surfaces the worst `top_n` misranks on each side
    /// (under-reinforced + over-promoted) to make the scalar
    /// interpretable. See [`SignalFidelityStats`] for fields.
    ///
    /// `top_n` is capped at 50 to keep the result bounded.
    async fn signal_fidelity_stats(&self, top_n: u32) -> Result<SignalFidelityStats>;

    /// Apply [`CompactPolicy`]; returns the keys that were (or would be)
    /// removed. Honours `dry_run`.
    async fn memory_compact(&self, policy: CompactPolicy) -> Result<Vec<String>>;

    /// Hard-DELETE rows that have been tombstoned for at least `older_than_days`.
    /// Tombstone soft-delete (Phase 2 #1) keeps deleted rows so the deletion
    /// propagates across `agent-bridge sync`; this GC pass cleans them up
    /// once the sync window is safely past. Returns the keys removed (or that
    /// would be removed if `dry_run`).
    async fn memory_purge_tombstones(
        &self,
        older_than_days: i64,
        dry_run: bool,
    ) -> Result<Vec<String>>;

    /// δ-3 (Butlin HOT-4 hygiene) — drop low-weight coactivation rows that
    /// never crystallised. A pair with `count <= max_count` AND
    /// `last_at <= now - older_than_days*86400` is noise: it co-fired briefly
    /// once, never re-fired, and is now ageing the table. Returns the number
    /// of rows that would be (or were) removed.
    ///
    /// Conservative defaults at the caller level: `max_count=1`,
    /// `older_than_days=30`. dream promote only crystallises pairs at
    /// `count >= min_count` (usually 3–5), so leaving count=2 rows live
    /// gives them a chance to grow before this GC removes them.
    async fn memory_prune_coactivation_noise(
        &self,
        max_count: i64,
        older_than_days: i64,
        dry_run: bool,
    ) -> Result<u64>;

    /// ζ-12 (2026-05-12) — drop `relates` edges where BOTH endpoints carry
    /// any tag in `blacklist_tags`. Cleans the legacy noise hubs produced by
    /// pre-ζ-11 `memory_link_orphans` runs that collapsed auto_curated stubs
    /// onto a single sibling. Defensive: only `relates` (the softest edge
    /// type) is in scope — causal/structural edges are preserved. Returns
    /// the number of edges removed (or that would be removed if `dry_run`).
    async fn memory_prune_degenerate_relates(
        &self,
        blacklist_tags: &[String],
        dry_run: bool,
    ) -> Result<u64> {
        let _ = (blacklist_tags, dry_run);
        Ok(0)
    }

    /// ζ-14 (2026-05-12) — flip orphan stubs carrying a blacklist tag from
    /// `status='active'` to `status='archived'`. Closes the ζ-9 → ζ-12
    /// loop: ζ-11 stopped new degenerate links, ζ-12 removed the legacy
    /// ones, leaving ~90 auto_curated stubs in orphan-set. ζ-11's blacklist
    /// blocks them from re-linking, so they are by construction signal-poor
    /// dead weight. ζ-14 actively retires them rather than waiting for
    /// passive decay.
    ///
    /// Criterion (all three required):
    /// - `status = 'active'`
    /// - `tags` overlaps `blacklist_tags`
    /// - no edges (orphan)
    /// - `created_at <= now - older_than_days*86400`
    ///
    /// `max_archive` caps a single run (default caller: 200) so accidents
    /// are bounded. Returns the count archived (or that would be archived
    /// if `dry_run`). `archived` is a soft transition — rows are excluded
    /// from snapshot/Palace/search but remain in the DB for forensics.
    async fn memory_archive_orphan_stubs(
        &self,
        blacklist_tags: &[String],
        older_than_days: i64,
        max_archive: i64,
        dry_run: bool,
    ) -> Result<u64> {
        let _ = (blacklist_tags, older_than_days, max_archive, dry_run);
        Ok(0)
    }

    /// ζ-18 (2026-05-13) — reverse of ζ-14. Restore a single archived row
    /// back to `status='active'`. Designed as the operator escape hatch
    /// when ζ-14 auto-archive misclassifies a row, or when a sweep
    /// captured a cohort that turns out to still carry signal after all.
    ///
    /// Single-row by key (not criterion-based): ζ-14 retires by sweep,
    /// ζ-18 restores by inspection. The asymmetry is intentional — a
    /// bulk restore op would re-introduce the noise ζ-14 just retired.
    ///
    /// Behavior:
    /// - Match only `status = 'archived'`. `active` / `superseded` /
    ///   `tombstoned` are no-ops (returns `Ok(false)`); the tombstone →
    ///   active path goes through `memory_save` + supersede chain, not
    ///   here. Resurrecting a tombstoned row through restore would
    ///   bypass the dedupe key reservation Phase-2-#2 relies on.
    /// - On match: flip status to `active`, bump `updated_at`.
    /// - Missing key returns `Ok(false)` (no error — same shape as a
    ///   status-mismatch no-op so callers can ignore both uniformly).
    ///
    /// Returns `true` iff a row was actually flipped.
    async fn memory_restore_archived(&self, key: &str) -> Result<bool> {
        let _ = key;
        Ok(false)
    }

    /// ζ-19 (2026-05-13) — retire-end GC. Time-based downgrade of stale
    /// `archived` rows to `tombstoned`. Closes the hygiene state machine:
    ///
    ///   active → ζ-14 → archived → ζ-19 → tombstoned → purge (7d) → DELETE
    ///
    /// Why archived → tombstoned (not direct DELETE)?
    /// - `tombstoned` rows still occupy their `dedupe_key` slot (Phase 2 #2),
    ///   so a NewerWins import or a same-content re-save will not silently
    ///   resurrect a row the operator already retired twice over. Going
    ///   straight to DELETE would forget the dedupe contract.
    /// - The 7-day purge_tombstones window provides a final undo before
    ///   physical loss.
    ///
    /// Criterion (both required):
    /// - `status = 'archived'`
    /// - `updated_at <= now - older_than_days*86400` (so ζ-14's flip
    ///    timestamp anchors the GC clock — 14-day default leaves a
    ///    generous ζ-18 restore window)
    ///
    /// `max_count` caps a single run; `dry_run` previews without writing.
    /// Returns the count tombstoned (or that would be tombstoned).
    async fn memory_tombstone_aged_archived(
        &self,
        older_than_days: i64,
        max_count: i64,
        dry_run: bool,
    ) -> Result<u64> {
        let _ = (older_than_days, max_count, dry_run);
        Ok(0)
    }

    /// ζ-16 — return the two most-recent `snapshot_daily_*` memory keys
    /// as `(older, newer)`. Designed to feed `dream diff --auto` so the
    /// operator doesn't have to look up yesterday's vs today's slug
    /// after the ζ-10 daily cron fires.
    ///
    /// Implementations should:
    /// - filter `kind = 'snapshot'`, `key LIKE 'snapshot_daily_%'`
    /// - accept both `active` and `superseded` (dream snapshot writes
    ///   through memory_save → Phase-1-P2 auto-supersedes the older
    ///   same-kind row, but for diff purposes that older row *is* the
    ///   target). Exclude `tombstoned` + `archived` — those reflect
    ///   explicit retirement.
    /// - order by `created_at DESC` and LIMIT 2
    /// - return `Ok(None)` when fewer than 2 daily snapshots exist
    ///
    /// Default returns `Ok(None)` so non-sqlite stores can opt out
    /// without a build break.
    async fn latest_daily_snapshot_pair(&self) -> Result<Option<(String, String)>> {
        Ok(None)
    }

    /// Audit `dream replay` output: are the LLM-consolidated summary
    /// memories actually used after creation? `stale_days` controls the
    /// "dead weight" cutoff — a `p5_replay`-tagged memory with
    /// `access_count = 0` AND older than this many days is counted in
    /// [`ReplayAuditStats::stale_dead`].
    ///
    /// Pure read pass — no writes. See [`ReplayAuditStats`] for fields
    /// and [`ReplayAuditRow`] for the per-summary detail rows.
    ///
    /// `waypoint_window_secs > 0` enables the temporal classification
    /// pass — for each summary with `get` events in `memory_query_log`,
    /// pair them against `get` events for `summarizes`-edge sources
    /// within ± this window. Drives gateway / trailing / ambiguous /
    /// isolated classification (see [`WaypointStats`]). Pass 0 to skip.
    ///
    /// `overlap_min_jaccard > 0.0` enables the source-set overlap pass
    /// (see [`OverlapPair`]). For each pair of active replay summaries
    /// whose `summarizes`-edge source-sets intersect, compute Jaccard
    /// similarity and emit those `>= overlap_min_jaccard`. Surfaces
    /// pre-Phase-2-#2 duplicates that escaped canonical-key dedupe.
    /// Pass 0.0 to skip.
    async fn replay_audit_stats(
        &self,
        stale_days: u32,
        waypoint_window_secs: i64,
        overlap_min_jaccard: f64,
    ) -> Result<ReplayAuditStats>;

    /// δ-4 (Butlin PP-1 lift) — return recent `memory_get` events as
    /// `(key, at)` pairs ordered by `at` DESC, capped at `limit`. Drives the
    /// bootstrap predicted-next-step section: by scanning recent get
    /// transitions you can answer "after focus X, what gets touched next?".
    /// Cheaper than a full coactivation walk because we only care about the
    /// raw temporal trace, not the pair graph.
    async fn recent_memory_get_keys(&self, limit: u32) -> Result<Vec<(String, i64)>>;

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

    /// P12: counts of active memories grouped by `embedding_backend`
    /// (added v26). NULL is reported as the literal string `"unknown"`
    /// so the caller doesn't have to special-case it. Used by Palace
    /// footer to surface "you have N hash-quality rows; reindex when
    /// ONNX is ready" awareness. Default impl returns empty vec.
    async fn memory_embedding_backend_counts(&self) -> Result<Vec<(String, u64)>> {
        Ok(Vec::new())
    }

    /// P17: counts of active memories grouped by `kind`. Used by Palace
    /// footer to separate working memory (kind='lesson' / 'project' / ...)
    /// from catalog imports (kind='skill', etc.) — without this split a
    /// 484-row skill bulk-import distorts every "active count" reading.
    /// Default impl returns empty vec.
    async fn memory_kind_counts(&self) -> Result<Vec<(String, u64)>> {
        Ok(Vec::new())
    }

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

    /// **Phase 1 P1** — return all coactivation edges where BOTH endpoints
    /// fall in `keys`. Lets `memory_search` rerank a result page by
    /// "this hit is in the same cluster as many other hits in the same
    /// page". Empty input → empty output. Default impl is a no-op so
    /// non-SQLite backends and unit tests degrade silently.
    async fn coactivation_among(&self, keys: &[String]) -> Result<Vec<CoactivationEdge>> {
        let _ = keys;
        Ok(Vec::new())
    }

    /// **Phase 1 P5** — return up to `limit` coactivation edges with
    /// `count >= min_count`, ordered by count DESC. Powers the dream-replay
    /// cluster picker (cluster building scans the heaviest edges first and
    /// joins endpoints with union-find). Default no-op for non-SQLite stores.
    async fn top_coactivation_edges(
        &self,
        min_count: u64,
        limit: u32,
    ) -> Result<Vec<CoactivationEdge>> {
        let _ = (min_count, limit);
        Ok(Vec::new())
    }

    /// **Phase 0 telemetry** — append one row to `memory_query_log`. Called
    /// by the MCP layer immediately after `memory_search` / `memory_get` so
    /// hit-rate / latency / top-hit-age can be aggregated. Default impl is
    /// a no-op so non-SQLite backends and unit tests degrade silently.
    ///
    /// The store is responsible for retention pruning (cap rows, drop oldest)
    /// — the caller does NOT need to think about table size.
    async fn record_memory_query(&self, _record: &MemoryQueryRecord) -> Result<()> {
        Ok(())
    }

    /// **Phase 0 telemetry** — aggregate the `memory_query_log` over the
    /// last `window_secs` seconds. Default returns an empty
    /// [`MemoryQueryStats`].
    async fn memory_query_stats(&self, window_secs: i64) -> Result<MemoryQueryStats> {
        let _ = window_secs;
        Ok(MemoryQueryStats::default())
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
            pairs_burst_lt_1h: 0,
            pairs_persistent_ge_6h: 0,
            top_5_persistent_edges: Vec::new(),
        })
    }

    /// ζ-9 — Graph topology snapshot. Default returns empty so older
    /// backends keep compiling.
    async fn graph_topology(&self) -> Result<GraphTopology> {
        Ok(GraphTopology::default())
    }

    /// v21 — Identity meta-monitor: behavioral fingerprint over a time
    /// window. Powers `agent-bridge dream identity` (vision principle 5:
    /// "literal answer to non-continuous medium continuity"). Default
    /// returns an empty window so older stores keep compiling.
    async fn identity_window(
        &self,
        window_start: i64,
        window_end: i64,
    ) -> Result<IdentityWindow> {
        Ok(IdentityWindow {
            window_start,
            window_end,
            tool_calls_total: 0,
            tool_calls_ok: 0,
            top_tools: Vec::new(),
            forum_posts: 0,
            forum_kinds: Vec::new(),
            forum_avg_body_len: 0.0,
            memory_saves: 0,
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

    /// Re-compute embeddings for active memories.
    /// - `only_stale=false`: rows with `embedding IS NULL` only.
    /// - `only_stale=true` (P9): also rows tagged with a different
    ///   `embedding_backend` than current default. NULL-backend rows
    ///   (pre-v26) are NOT touched in stale mode.
    async fn memory_reindex_embeddings(
        &self,
        batch_size: usize,
        only_stale: bool,
    ) -> Result<usize> {
        let _ = (batch_size, only_stale);
        Ok(0)
    }

    /// Compute and persist embeddings for `codebase_symbols` rows whose
    /// `embedding IS NULL`. Without this, `codebase_search(mode="semantic")`
    /// has nothing to score against — `codebase_index` writes rows with a
    /// NULL embedding column intentionally so this fill can be deferred to
    /// an explicit reindex call. Returns the number of rows updated.
    /// Default impl returns 0 (no-op for non-SQLite backends).
    async fn codebase_reindex_embeddings(&self, batch_size: usize) -> Result<usize> {
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

    /// Phase 2 #3 second slice — query the imports table by `target` substring
    /// (LIKE), optionally narrowed to a file or root. Returns rows ordered by
    /// `(file_path, line)` ascending. Use to answer "who imports X" without
    /// re-walking source.
    async fn codebase_imports_for(
        &self,
        target_substr: &str,
        file_filter: Option<&str>,
        root_path: Option<&str>,
        limit: u32,
    ) -> Result<Vec<CodebaseImport>> {
        let _ = (target_substr, file_filter, root_path, limit);
        Err(ab_core::Error::Backend(
            "codebase_imports_for not implemented".into(),
        ))
    }

    /// Phase 2 #3 third slice — query the calls table by `callee` and/or
    /// `caller` substring (LIKE), optionally narrowed to a file or root.
    /// Returns rows ordered by `(file_path, line)` ascending. Use to
    /// answer "who calls X" or "what does Y call" without re-walking
    /// source. At least one of `callee_substr` / `caller_substr` must
    /// be `Some` to narrow the result set.
    async fn codebase_calls_for(
        &self,
        callee_substr: Option<&str>,
        caller_substr: Option<&str>,
        file_filter: Option<&str>,
        root_path: Option<&str>,
        limit: u32,
    ) -> Result<Vec<CodebaseCall>> {
        let _ = (
            callee_substr,
            caller_substr,
            file_filter,
            root_path,
            limit,
        );
        Err(ab_core::Error::Backend(
            "codebase_calls_for not implemented".into(),
        ))
    }

    /// Phase 2 #3 third-slice — alias-resolved call lookup. Joins
    /// `codebase_imports` (in-scope aliases) with `codebase_calls`
    /// (textual call sites) so a query for `crate::store::SqliteStore::new`
    /// also surfaces sites that wrote `Baz::new()` after a
    /// `use crate::store::SqliteStore as Baz`. Algorithm:
    ///
    /// 1. Split `target` at every `::` boundary into (prefix, suffix) pairs.
    /// 2. For each prefix, find imports whose target equals that prefix.
    ///    The import's local name is `alias.unwrap_or(last_segment(target))`.
    /// 3. For each such import, look up calls in the same file whose
    ///    callee equals `local_name + suffix` (or just `local_name` when
    ///    suffix is empty).
    /// 4. Emit one `ResolvedCall` per match, deduping by `(file, line)`.
    ///
    /// Returns rows ordered by `(file_path, line)` ascending. Default
    /// implementation errors so non-sqlite backends opt-in explicitly.
    async fn codebase_callers(
        &self,
        target: &str,
        file_filter: Option<&str>,
        root_path: Option<&str>,
        limit: u32,
    ) -> Result<Vec<ResolvedCall>> {
        let _ = (target, file_filter, root_path, limit);
        Err(ab_core::Error::Backend(
            "codebase_callers not implemented".into(),
        ))
    }

    /// Phase 2 #3 third slice — aggregate stats for a single `root_path`,
    /// used by `dream codebase-report --html`. Combines per-language
    /// counts, hot callees/callers, fan-out by file, and a best-effort
    /// orphan-function list (function/method symbols whose last-segment
    /// name never appears as a callee).
    ///
    /// `top_n` caps the size of `hot_callees`, `hot_callers`,
    /// `orphan_functions`, and `fan_out_files`. The per-language and
    /// total counts are always full.
    async fn codebase_call_stats(
        &self,
        root_path: &str,
        top_n: u32,
    ) -> Result<CodebaseCallStats> {
        let _ = (root_path, top_n);
        Err(ab_core::Error::Backend(
            "codebase_call_stats not implemented".into(),
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
            superseded_by: None,
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
