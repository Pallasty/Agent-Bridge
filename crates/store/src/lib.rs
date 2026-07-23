//! Persistence abstraction.
//!
//! Default impl: [`SqliteStore`] — single-file rusqlite (bundled), zero system deps.
//! Future: in-memory (tests), Postgres (multi-machine), Redis (cache).

use ab_core::{NotifyEvent, Result, SessionId};
use async_trait::async_trait;
use serde::{Deserialize, Serialize};

pub mod coactivation_latch;
pub mod codebase;
pub mod connectivity_repair;
pub mod embedding;
#[cfg(feature = "engram-g1-authenticated-envelope-shadow-synthetic")]
mod engram_g1_authenticated_envelope_shadow;
#[cfg(all(
    feature = "engram-g1-secure-custody-shadow-synthetic",
    target_os = "macos"
))]
mod engram_g1_secure_custody_shadow;
#[cfg(feature = "episode-observation-slice-a")]
mod episode_observation_slice_a;
#[cfg(feature = "episode-observation-slice-c2-synthetic")]
pub mod episode_observation_c2_synthetic;
pub mod lineage_audit;
pub mod mmr;
pub use mmr::mmr_rerank_by_text;
pub mod quant;
pub mod sqlite;
#[cfg(feature = "temporal-evidence-s5-candidate-synthetic")]
mod temporal_candidate_evidence;
#[cfg(feature = "temporal-evidence-s6-detached-verifier-synthetic")]
mod temporal_replay_transport;
pub use sqlite::{
    default_db_path, now_secs, rrf_fuse, semantic_blend_score, semantic_rank_weights,
    temporal_bonus, weight_for_edge_type, SqliteStore,
};
#[cfg(feature = "temporal-evidence-s4-synthetic")]
pub use sqlite::{
    temporal_truth_project_read_only_synthetic_v1, BoundTemporalTruthProjectionV1,
    SyntheticTemporalTruthProjectionPermitV1, TemporalTruthAuthorityBasisViewV1,
    TemporalTruthDispositionReasonKindV1, TemporalTruthDispositionReasonViewV1,
    TemporalTruthEvidenceDispositionViewV1, TemporalTruthEvidenceProvenanceViewV1,
    TemporalTruthProjectedClaimViewV1, TemporalTruthProjectionLimitsV1,
    TemporalTruthProjectionRequestV1, TemporalTruthProjectionV1Error, TemporalTruthRequiredClaimV1,
    TemporalTruthSnapshotCountsV1, TemporalTruthSourceBindingViewV1, TemporalTruthStateV1,
    TemporalTruthSuppressionKindV1, TemporalTruthTemporalStateV1, TemporalTruthTierV1,
    TEMPORAL_TRUTH_PROJECTION_V1_MAPPING, TEMPORAL_TRUTH_PROJECTION_V1_MODE,
    TEMPORAL_TRUTH_PROJECTION_V1_PROFILE, TEMPORAL_TRUTH_PROJECTION_V1_SCHEMA,
};
#[cfg(all(test, feature = "temporal-evidence-s5-candidate-synthetic"))]
pub(crate) use temporal_candidate_evidence::synthetic_track_b_candidate_evidence_permit_v1;
#[cfg(feature = "temporal-evidence-s5-candidate-synthetic")]
pub use temporal_candidate_evidence::{
    bind_synthetic_track_b_candidate_evidence_v1, project_synthetic_track_b_candidate_source_v1,
    BoundTrackBCandidateEvidenceV1, SyntheticTrackBCandidateEvidencePermitV1,
    SyntheticTrackBCandidateProjectionPairV1, TrackBCandidateEvidenceClaimViewV1,
    TrackBCandidateEvidenceV1Error, TRACK_B_CANDIDATE_EVIDENCE_SCHEMA_SHA256,
    TRACK_B_CANDIDATE_EVIDENCE_V1_MODE, TRACK_B_CANDIDATE_EVIDENCE_V1_SCHEMA,
    TRACK_B_CANDIDATE_HANDLE_PROFILE_V1, TRACK_B_FOUNDATIONAL_ARTIFACT_CATALOG_SHA256,
    TRACK_B_FOUNDATIONAL_PACK_MANIFEST_SHA256, TRACK_B_TRUTH_REFERENT_SCHEMA_ID,
    TRACK_B_TRUTH_REFERENT_SCHEMA_SHA256,
};
pub mod vector;
pub use embedding::{
    default_backend, set_default_backend, EmbeddingBackend, HashBackend, OnnxBackend,
};
pub use vector::{
    active_model_name, cosine_similarity, decode_embedding, embed_text, encode_embedding,
    vector_dim,
};
pub mod version_vector;
pub use version_vector::{
    node_id_from_env, node_id_from_name, Counter, NodeId, Ordering, VersionVector,
};

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
    // ── v41: local child process identity (orphan reaper) ────────────
    /// OS pid of the spawned local child (PTY leader), when known.
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub proc_pid: Option<i64>,
    /// Child's process group id (== pid: portable_pty setsids the child).
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub proc_pgid: Option<i64>,
    /// `/proc/<pid>/stat` starttime at spawn — the anti-pid-reuse token: a
    /// recycled pid has a different starttime, so a reaper that checks this
    /// can never signal an unrelated process.
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub proc_start_ticks: Option<i64>,
    /// Pid of the OS process that owns the in-memory PTY handle (the MCP
    /// server / daemon that spawned the child). A session whose owner is
    /// gone is an orphan: nothing holds its PTY and no Drop will ever fire.
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub owner_pid: Option<i64>,
    /// starttime of the owner process — same anti-reuse token for the owner.
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub owner_start_ticks: Option<i64>,
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
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub client_name: Option<String>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub profile: Option<String>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub source: Option<String>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub model: Option<String>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub model_reasoning_effort: Option<String>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub codex_host: Option<String>,
}

/// Optional attribution filter for MCP tool-call telemetry.
#[derive(Debug, Clone, Default, PartialEq, Eq)]
pub struct McpToolCallFilter {
    pub client_name: Option<String>,
    pub profile: Option<String>,
    pub source: Option<String>,
    pub model: Option<String>,
    pub model_reasoning_effort: Option<String>,
    pub codex_host: Option<String>,
}

/// Grouped MCP tool-call telemetry by attributed caller/source.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct McpToolSourceStats {
    pub source: String,
    pub client_name: String,
    pub profile: String,
    pub model: String,
    pub model_reasoning_effort: String,
    pub codex_host: String,
    pub call_count: u64,
    pub error_count: u64,
}

/// Row-level MCP tool-call telemetry for `tool_call_attention_report`
/// (L6 P2). Carries enough fields for in-process time-window analysis
/// (which calls were high-yield, which had follow-up activity within
/// K minutes, which were never referenced).
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub struct McpToolCallRow {
    pub ts: i64,
    pub tool_name: String,
    pub duration_ms: u32,
    pub ok: bool,
    /// Argument JSON payload size at MCP entry (`None` when not
    /// recorded by the caller).
    pub args_size: Option<u32>,
    /// Result payload size at MCP exit (`None` when not recorded).
    pub result_size: Option<u32>,
}

/// A produced (not derived) semantic event — SSB Phase-1 typed event spine.
///
/// Unlike [`event_spine`] derivations over telemetry rows, these are emitted by
/// a real producer AT ACTION TIME and carry a verify-first verdict, so the
/// "no green laundering" invariant is recorded as a mechanism: an action that
/// would be inert is stored with `verdict_status='not_verified'`, never as a
/// silent success. Append-only + node-local (not exported in memory sync).
#[derive(Debug, Clone, serde::Serialize, PartialEq, Eq)]
pub struct SemanticEventRecord {
    pub ts: i64,
    /// Who produced it (mcp caller / node / session).
    pub actor: String,
    /// Adapter / subsystem, e.g. "browser".
    pub source: String,
    /// Action verb, e.g. "click".
    pub action: String,
    /// Semantic object reference acted on, e.g. "@e5" (None when not applicable).
    pub target: Option<String>,
    /// "verified" | "not_verified" | "unknown".
    pub verdict_status: String,
    /// How the verdict was reached, e.g. "cdp_actionability_probe".
    pub verdict_method: String,
    /// JSON evidence string (None when none).
    pub evidence: Option<String>,
    /// JSON facts string.
    pub facts: String,
    /// SSB unified contract: normalized `{"object":…,"affordance":…}` descriptor
    /// (roadmap §3.1/§3.2), emitted with the same vocabulary by every producer.
    /// Distinct from `facts` (adapter-specific extras). None for legacy rows /
    /// producers that have not adopted the contract yet.
    pub descriptor: Option<String>,
}

/// Max rows retained in `mcp_tool_errors` after each insert (oldest pruned).
pub const MCP_TOOL_ERROR_RING_CAP: u32 = 100;

/// Cap on `semantic_events` rows after each insert (oldest pruned), keeping the
/// append-only producer log bounded like the MCP telemetry ring.
pub const SEMANTIC_EVENT_RING_CAP: i64 = 5_000;

/// Cap on `memory_query_log` rows (Phase 0 memory telemetry). Older rows are
/// pruned each `record_memory_query` call, FIFO. ~7 days of moderate use at
/// 5k rows; tune via design review when telemetry exposes traffic shape.
pub const MEMORY_QUERY_LOG_RING_CAP: i64 = 5_000;

/// Cap on `retrieval_surfacing` rows (Outcome-collector feedback telemetry).
/// Older rows are pruned FIFO on each `record_retrieval_surfacing` call so the
/// table stays bounded once the collector is enabled. One search writes up to
/// ~10 rows (top-k surfaced keys) vs one row for `memory_query_log`, so this is
/// scaled ~10× for a comparable ~7-day window of moderate use. Under any
/// non-pathological traffic the FIFO-by-id prune removes only rows far older
/// than the 1800s attribution window, so it doesn't race with
/// `attribute_retrieval_get` stamping used_at; the crossover is >~2.8
/// searches/sec sustained for 30 min (50k rows ÷ 10 rows/search ÷ 1800s), where
/// the worst case is losing used_at stamps on the oldest telemetry rows —
/// bounded, telemetry-only. The ambient session_bootstrap writer (2026-07-05)
/// adds up to ~60 [`AMBIENT_SURFACING_MODE`] rows per injection, shrinking the
/// retained span (~1.2k rows/day at hook cadence ≈ ring full in ~6 weeks if
/// nothing consumes); the prune evicts pending ambient rows before pending
/// search evidence, so that arithmetic degrades ambient history first. Tune
/// via design review once the retrieval_outcome_report exposes real traffic
/// shape.
pub const RETRIEVAL_SURFACING_RING_CAP: i64 = 50_000;

/// Cap on `fusion_shadow` rows (R2 passive RRF-fusion shadow, forum #147).
/// One row per shadowed default-mode search (skips included), pruned FIFO on
/// each write — same bound rationale as `memory_query_log` (one row/query).
pub const FUSION_SHADOW_RING_CAP: i64 = 5_000;

/// `retrieval_surfacing.mode` value for AMBIENT bootstrap injections — the
/// session_bootstrap semantic page (hook-driven or agent-called), logged so
/// injected memories participate in used_at attribution at all.
///
/// Stage 1 is telemetry-only (2026-07-05): rows with this mode are excluded
/// from every reinforce/decay aggregate (`retrieval_outcome_summary`
/// candidates, `retrieval_outcome_shadow_rows`, `retrieval_outcome_apply_rows`)
/// because "injected and not used" is a far weaker negative signal than
/// "searched for and not used" — one injection surfaces up to ~60 rows vs ~10
/// per search, so an uncalibrated shared rule would let ambient volume decay
/// memories that were never actually noise. The rows still receive used_at
/// stamps (memory_get / feedback attribution is mode-agnostic) and are retired
/// each confirmed apply pass via [`StateStore::consume_ambient_surfacings`].
/// Acting on this slice (a calibrated bootstrap-specific rule) is the stage-2
/// follow-up, gated on the data this stage accumulates.
pub const AMBIENT_SURFACING_MODE: &str = "bootstrap";

/// v42 retrieval provenance. Traffic origin is orthogonal to retrieval mode:
/// an eval process may call either `memory_search` or `session_bootstrap`.
/// Missing/invalid values fail closed to `unknown`; they are never inferred
/// from query text, keys, mode, timestamps, or process names.
pub const RETRIEVAL_TRAFFIC_CLASS_UNKNOWN: &str = "unknown";
pub const RETRIEVAL_TRAFFIC_CLASS_ORGANIC: &str = "organic";
pub const RETRIEVAL_TRAFFIC_CLASS_EVAL: &str = "eval";

pub fn normalize_retrieval_traffic_class(value: Option<&str>) -> &'static str {
    match value.map(str::trim) {
        Some(value) if value.eq_ignore_ascii_case(RETRIEVAL_TRAFFIC_CLASS_ORGANIC) => {
            RETRIEVAL_TRAFFIC_CLASS_ORGANIC
        }
        Some(value) if value.eq_ignore_ascii_case(RETRIEVAL_TRAFFIC_CLASS_EVAL) => {
            RETRIEVAL_TRAFFIC_CLASS_EVAL
        }
        _ => RETRIEVAL_TRAFFIC_CLASS_UNKNOWN,
    }
}

/// Hard cap on stdout/stderr we persist per agent session, to keep the DB
/// file from growing unbounded if a sub-agent goes haywire.
pub const STDIO_CAP: usize = 64 * 1024;

/// Hard cap on a single memory's `content` field (256 KiB).
pub const MEMORY_CONTENT_CAP: usize = 256 * 1024;

/// Hard ceilings for one internal truth-adapter diagnostic snapshot. These
/// bounds are deliberately below the general export surface: a preflight is a
/// bounded proof attempt, not another bulk raw-memory API.
pub const MEMORY_EVIDENCE_SNAPSHOT_MAX_RECORDS: usize = 10_000;
pub const MEMORY_EVIDENCE_SNAPSHOT_MAX_TOMBSTONES: usize = 10_000;
pub const MEMORY_EVIDENCE_SNAPSHOT_MAX_EDGES: usize = 50_000;
pub const MEMORY_EVIDENCE_SNAPSHOT_MAX_PAYLOAD_BYTES: usize = 16 * 1024 * 1024;

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
    /// Lifecycle status: "active" | "archived" | "superseded" | "conflict" |
    /// "tombstoned". Archived = decayed below threshold. Superseded = a newer
    /// memory auto-detected as replacing this one. Conflict rows preserve a
    /// concurrent imported version. Tombstoned rows are retained deletion
    /// markers and are hidden from ordinary retrieval.
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

/// Return whether a memory scope is visible from `ctx`.
///
/// This is the store-level counterpart of [`StateStore::list_memories_in_scope`]:
/// an empty context is the backwards-compatible unscoped/admin view; otherwise
/// global/unscoped rows, an exact scope match, and a `project:/root` row viewed
/// from `/root` (or one of its descendants) are visible. Other project and
/// domain scopes are not. Project matching is path-segment aware, so
/// `project:/repo/a` never matches `/repo/another`.
///
/// `ctx` accepts either a cwd-style path (`/repo/a/sub`) or a stored scope
/// string (`project:/repo/a/sub`, `domain:rust`). This is recall scoping for the
/// local single-user store, not a principal/ACL authorization check.
pub fn memory_scope_visible_in_context(record_scope: Option<&str>, ctx: &str) -> bool {
    let ctx = ctx.trim();
    if ctx.is_empty() {
        return true;
    }

    let Some(scope) = record_scope
        .map(str::trim)
        .filter(|scope| !scope.is_empty())
    else {
        return true;
    };
    if scope == "global" || scope == ctx {
        return true;
    }

    let Some(project_root) = scope.strip_prefix("project:") else {
        // Non-project scopes (including `domain:*`) are exact-match only.
        return false;
    };
    let ctx_path = ctx.strip_prefix("project:").unwrap_or(ctx);
    let project_root = project_root.trim_end_matches('/');
    let ctx_path = ctx_path.trim_end_matches('/');
    if project_root.is_empty() || ctx_path.is_empty() {
        return false;
    }

    ctx_path == project_root
        || ctx_path
            .strip_prefix(project_root)
            .is_some_and(|rest| rest.starts_with('/'))
}

/// Content-free privacy marker returned by [`StateStore::memory_peek`] and
/// [`StateStore::memory_evidence_snapshot`]. Tombstoned content, tags, scope,
/// and relationship fields must never be rehydrated through these surfaces.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct MemoryTombstoneMarker {
    pub key: String,
    pub updated_at: i64,
}

/// Exact, side-effect-free result for one memory key.
#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(tag = "state", rename_all = "snake_case", deny_unknown_fields)]
pub enum MemoryPeekResult {
    Missing,
    Present { record: Box<MemoryRecord> },
    Tombstoned { marker: MemoryTombstoneMarker },
}

/// Caller bounds for one internal evidence snapshot.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct MemoryEvidenceSnapshotLimits {
    pub max_records: usize,
    pub max_tombstones: usize,
    pub max_edges: usize,
    /// Maximum aggregate UTF-8 payload bytes retained across row markers,
    /// tombstone markers, and visible edges. Rust container overhead is
    /// separately bounded by the three row caps.
    pub max_payload_bytes: usize,
}

impl Default for MemoryEvidenceSnapshotLimits {
    fn default() -> Self {
        Self {
            max_records: 1_000,
            max_tombstones: 1_000,
            max_edges: 5_000,
            max_payload_bytes: 4 * 1024 * 1024,
        }
    }
}

impl MemoryEvidenceSnapshotLimits {
    pub fn validate(self) -> Result<Self> {
        let checks = [
            (
                "max_records",
                self.max_records,
                MEMORY_EVIDENCE_SNAPSHOT_MAX_RECORDS,
            ),
            (
                "max_tombstones",
                self.max_tombstones,
                MEMORY_EVIDENCE_SNAPSHOT_MAX_TOMBSTONES,
            ),
            (
                "max_edges",
                self.max_edges,
                MEMORY_EVIDENCE_SNAPSHOT_MAX_EDGES,
            ),
            (
                "max_payload_bytes",
                self.max_payload_bytes,
                MEMORY_EVIDENCE_SNAPSHOT_MAX_PAYLOAD_BYTES,
            ),
        ];
        if let Some((field, value, hard_max)) = checks
            .into_iter()
            .find(|(_, value, hard_max)| *value == 0 || *value > *hard_max)
        {
            return Err(ab_core::Error::Backend(format!(
                "memory evidence snapshot {field} must be in 1..={hard_max}, got {value}"
            )));
        }
        Ok(self)
    }
}

/// Producer/schema profile bound into an opaque evidence snapshot by the
/// store implementation. Callers cannot supply an arbitrary capability bag.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
#[non_exhaustive]
pub enum MemoryEvidenceProfile {
    /// Current SQLite: one mutable row per key, purgeable tombstones, and no
    /// append-only truth/governance ledger.
    MutableSqliteV41,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub(crate) struct MemoryEvidenceRecordMarker {
    pub key: String,
    pub status: String,
    pub created_at: i64,
    pub updated_at: i64,
}

/// One bounded, deterministic, read-only inventory used only for adapter
/// completeness preflight. Retained content/tags/related_keys remain behind
/// single-key [`StateStore::memory_peek`]; tombstoned relationship endpoints
/// never enter this value. The type is intentionally not serializable and its
/// payload fields are private outside `ab-store`.
#[derive(Clone)]
pub struct MemoryEvidenceSnapshot {
    records: Vec<MemoryEvidenceRecordMarker>,
    tombstones: Vec<MemoryTombstoneMarker>,
    edges: Vec<MemoryEdgeExport>,
    payload_bytes: usize,
    truncated: bool,
    /// Direct endpoint check over the retained rows in this exact snapshot.
    /// Adapter admission still requires stronger profile guarantees.
    retained_edge_endpoints_closed: bool,
    tombstone_relationships_redacted: bool,
    profile: MemoryEvidenceProfile,
}

impl MemoryEvidenceSnapshot {
    pub fn profile(&self) -> MemoryEvidenceProfile {
        self.profile
    }

    pub fn truncated(&self) -> bool {
        self.truncated
    }

    pub fn record_count(&self) -> usize {
        self.records.len()
    }

    pub fn tombstone_count(&self) -> usize {
        self.tombstones.len()
    }

    pub fn visible_edge_count(&self) -> usize {
        self.edges.len()
    }

    pub fn payload_bytes(&self) -> usize {
        self.payload_bytes
    }

    pub fn retained_edge_endpoints_closed(&self) -> bool {
        self.retained_edge_endpoints_closed
    }

    pub fn tombstone_relationships_redacted(&self) -> bool {
        self.tombstone_relationships_redacted
    }
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
    /// **Not** a pure cosine — semantic paths blend in importance / recency
    /// bonuses so `score` can exceed 1.0. For threshold checks against a
    /// raw geometric distance use [`Self::cosine`] (semantic mode only).
    pub score: f64,
    /// Raw cosine ∈ [-1, 1] for `semantic` and `hybrid` semantic-leg hits.
    /// `None` for FTS5-only paths (no embedding compared). Callers doing
    /// near-duplicate detection (e.g. B3 `prior_decision_warning`) MUST
    /// read this field — `score` is post-blend and not bounded by 1.0.
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub cosine: Option<f32>,
}

/// Conservative fan-out for the frozen reference surface. A content-free
/// structural audit of the current owner store observed p99 degree 36 and max
/// degree 123 on 2026-07-14, so 64 bounds work while retaining more than 99%
/// of observed neighbourhoods. This remains an engineering cap, not a quality
/// target. The legacy hybrid API is unchanged.
pub const MEMORY_REFERENCE_GRAPH_FANOUT: usize = 64;

/// Hard exact UTF-8 budget for the final context sent to a generator. The
/// separately frozen model-tokenizer binding required by Track B remains a
/// later admission gate; this surface does not pretend whitespace counts are
/// model tokens.
pub const MEMORY_REFERENCE_MAX_CONTEXT_BYTES: usize = 128 * 1024;

const MEMORY_TTL_SECONDS_PER_DAY: i64 = 86_400;

/// Expiry instant for the retrieval-wide `ttl:<N>d` convention. The anchor
/// and saturating arithmetic intentionally match the MCP retrieval path so a
/// frozen reference clock cannot observe a different TTL policy.
pub fn memory_record_ttl_expires_at(record: &MemoryRecord) -> Option<i64> {
    let ttl_days = record.tags.iter().find_map(|tag| {
        tag.strip_prefix("ttl:")
            .and_then(|value| value.strip_suffix('d'))
            .and_then(|value| value.parse::<i64>().ok())
            .filter(|days| *days > 0)
    })?;
    let anchor = record.updated_at.max(record.created_at);
    (anchor > 0).then(|| anchor.saturating_add(ttl_days.saturating_mul(MEMORY_TTL_SECONDS_PER_DAY)))
}

/// Whether a TTL-tagged record is live at the caller-bound Unix second.
/// Expiry is exclusive: a record is suppressed exactly at `expires_at`.
pub fn memory_record_ttl_is_live_at(record: &MemoryRecord, as_of_secs: i64) -> bool {
    memory_record_ttl_expires_at(record)
        .map(|expires_at| expires_at > as_of_secs)
        .unwrap_or(true)
}

/// Runtime controls for the deterministic, read-only reference search
/// surface. `as_of_secs` is mandatory so a future runner can bind one clock
/// value for every paired condition. The regular search APIs do not consume
/// this type and retain their existing wall-clock/telemetry behavior.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct MemorySearchReferenceOptions {
    pub as_of_secs: i64,
    pub graph_fanout: usize,
    pub max_context_bytes: usize,
    pub exclude_kinds: Vec<String>,
    pub coactivation_rerank: bool,
}

impl MemorySearchReferenceOptions {
    pub fn at(as_of_secs: i64) -> Self {
        Self {
            as_of_secs,
            graph_fanout: MEMORY_REFERENCE_GRAPH_FANOUT,
            max_context_bytes: MEMORY_REFERENCE_MAX_CONTEXT_BYTES,
            exclude_kinds: vec!["skill".to_string()],
            coactivation_rerank: true,
        }
    }
}

/// Stable context projection for the deterministic reference surface.
/// Access telemetry is intentionally absent: `last_accessed_at` and
/// `access_count` are mutable read-side signals and must not enter a frozen
/// paired context payload.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub struct MemorySearchReferenceHit {
    pub rank: usize,
    pub key: String,
    pub kind: String,
    pub content: String,
    pub tags: Vec<String>,
    pub related_keys: Vec<String>,
    pub scope: Option<String>,
    pub created_at: i64,
    pub updated_at: i64,
    pub status: String,
    pub trigger_pattern: Option<String>,
    pub superseded_by: Option<String>,
}

/// Exact context and its normalized rows. `context_json` is the byte string a
/// future generator receives; callers must not reserialize `hits` under a
/// different policy and still claim this receipt.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub struct MemorySearchReferenceContext {
    pub context_json: String,
    pub context_bytes: usize,
    pub hits: Vec<MemorySearchReferenceHit>,
}

/// Project the complete selected page into a telemetry-free context. Budget
/// overflow is terminal: silently truncating the tail could hide a recalled
/// gold item and turn a retrieval success into an unreported synthesis input
/// change.
pub fn project_memory_search_reference_hits(
    hits: &[MemorySearchHit],
    max_context_bytes: usize,
) -> Result<MemorySearchReferenceContext> {
    if max_context_bytes < 2 {
        return Err(ab_core::Error::Backend(
            "reference context byte budget must be at least two".into(),
        ));
    }

    let projected: Vec<MemorySearchReferenceHit> = hits
        .iter()
        .enumerate()
        .map(|(index, hit)| {
            let mut tags = hit.record.tags.clone();
            tags.sort();
            tags.dedup();
            let mut related_keys = hit.record.related_keys.clone();
            related_keys.sort();
            related_keys.dedup();
            MemorySearchReferenceHit {
                rank: index + 1,
                key: hit.record.key.clone(),
                kind: hit.record.kind.clone(),
                content: hit.record.content.clone(),
                tags,
                related_keys,
                scope: hit.record.scope.clone(),
                created_at: hit.record.created_at,
                updated_at: hit.record.updated_at,
                status: hit.record.status.clone(),
                trigger_pattern: hit.record.trigger_pattern.clone(),
                superseded_by: hit.record.superseded_by.clone(),
            }
        })
        .collect();
    let context_json = serde_json::to_string(&projected).map_err(|error| {
        ab_core::Error::Backend(format!("reference context serialize: {error}"))
    })?;
    let context_bytes = context_json.len();
    if context_bytes > max_context_bytes {
        return Err(ab_core::Error::Backend(format!(
            "reference context byte budget exceeded: {context_bytes} > {max_context_bytes}"
        )));
    }

    Ok(MemorySearchReferenceContext {
        context_json,
        context_bytes,
        hits: projected,
    })
}

pub const BIOCORTEX_RETRIEVAL_OPT_IN_STORE_CONTRACT_SCHEMA: &str =
    "agent_bridge.store.memory_search.biocortex_opt_in_contract.v0";
pub const BIOCORTEX_RETRIEVAL_OPT_IN_SEARCH_AUDIT_SCHEMA: &str =
    "agent_bridge.store.memory_search.biocortex_opt_in_search_audit.v0";
pub const BIOCORTEX_RETRIEVAL_OPT_IN_AUTHORIZATION_SCOPE: &str = "opt_in_experiment";

/// Store-level contract for a future BioCortex-assisted `memory_search` call.
///
/// This is deliberately just a contract shape: it does not run BioCortex and
/// does not alter `memory_search`. Callers must already have the baseline FTS
/// result before an opt-in experiment can be evaluated, so every failure path
/// can return the baseline list.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct BioCortexRetrievalOptInRequest {
    /// Retrieval mode under review. Only `fts` is authorized by the current
    /// opt-in experiment scope.
    #[serde(default = "default_biocortex_retrieval_mode")]
    pub mode: String,
    /// Explicit per-call opt-in. Feature/runtime flags alone are insufficient.
    #[serde(default)]
    pub per_call_opt_in: bool,
    /// Whether the optional Cargo feature was compiled in.
    #[serde(default)]
    pub compile_feature_enabled: bool,
    /// Whether the runtime enable env was set for this process.
    #[serde(default)]
    pub runtime_enabled: bool,
    /// Operator kill-switch; wins over runtime enable and per-call opt-in.
    #[serde(default)]
    pub operator_disabled: bool,
    /// True when the baseline search has already completed. A baseline may have
    /// zero hits; that is still a completed baseline and is safe to return.
    #[serde(default = "default_true")]
    pub baseline_completed: bool,
    /// Count only. The store-level contract must not require raw memory keys.
    #[serde(default)]
    pub baseline_key_count: usize,
    /// Review gate for future runtime influence. False in the current plan.
    #[serde(default)]
    pub runtime_adapter_approved: bool,
    /// True only after code is intentionally connected to an ordering path.
    #[serde(default)]
    pub ordering_behavior_connected: bool,
}

impl Default for BioCortexRetrievalOptInRequest {
    fn default() -> Self {
        Self {
            mode: default_biocortex_retrieval_mode(),
            per_call_opt_in: false,
            compile_feature_enabled: false,
            runtime_enabled: false,
            operator_disabled: false,
            baseline_completed: true,
            baseline_key_count: 0,
            runtime_adapter_approved: false,
            ordering_behavior_connected: false,
        }
    }
}

impl BioCortexRetrievalOptInRequest {
    pub fn normalized_mode(&self) -> String {
        normalize_retrieval_mode(&self.mode)
    }

    pub fn evaluate(&self) -> BioCortexRetrievalOptInDecision {
        let mode = self.normalized_mode();
        let mode_authorized = mode == "fts";
        let mut blocking_reasons = Vec::new();

        if !mode_authorized {
            blocking_reasons.push(BioCortexRetrievalOptInBlocker::ModeNotAuthorized);
        }
        if !self.baseline_completed {
            blocking_reasons.push(BioCortexRetrievalOptInBlocker::BaselineNotEstablished);
        }
        if !self.compile_feature_enabled {
            blocking_reasons.push(BioCortexRetrievalOptInBlocker::CompileFeatureDisabled);
        } else if self.operator_disabled {
            blocking_reasons.push(BioCortexRetrievalOptInBlocker::OperatorDisabled);
        } else if !self.runtime_enabled {
            blocking_reasons.push(BioCortexRetrievalOptInBlocker::RuntimeDisabled);
        } else if !self.per_call_opt_in {
            blocking_reasons.push(BioCortexRetrievalOptInBlocker::PerCallOptInMissing);
        }

        let gate_ready = mode_authorized
            && self.baseline_completed
            && self.compile_feature_enabled
            && self.runtime_enabled
            && self.per_call_opt_in
            && !self.operator_disabled;
        if gate_ready {
            if !self.ordering_behavior_connected {
                blocking_reasons.push(BioCortexRetrievalOptInBlocker::OrderingBehaviorNotConnected);
            }
            if !self.runtime_adapter_approved {
                blocking_reasons.push(BioCortexRetrievalOptInBlocker::RuntimeAdapterNotApproved);
            }
        }

        let may_change_search_order = blocking_reasons.is_empty();
        BioCortexRetrievalOptInDecision {
            schema: BIOCORTEX_RETRIEVAL_OPT_IN_STORE_CONTRACT_SCHEMA.to_string(),
            authorization_scope: BIOCORTEX_RETRIEVAL_OPT_IN_AUTHORIZATION_SCOPE.to_string(),
            mode,
            mode_authorized,
            eligible_for_side_signal: may_change_search_order,
            may_change_search_order,
            default_search_order_change_allowed: false,
            default_calls_unchanged: true,
            must_return_baseline: !may_change_search_order,
            baseline_completed: self.baseline_completed,
            baseline_key_count: self.baseline_key_count,
            fallback_reason: blocking_reasons.first().copied(),
            blocking_reasons,
            audit_requirements: BioCortexRetrievalAuditRequirements::default(),
        }
    }
}

fn default_biocortex_retrieval_mode() -> String {
    "fts".to_string()
}

fn default_true() -> bool {
    true
}

fn normalize_retrieval_mode(value: &str) -> String {
    let mut out = String::new();
    for ch in value.trim().chars() {
        if ch.is_ascii_alphanumeric() || ch == '_' || ch == '-' {
            out.push(ch.to_ascii_lowercase());
        }
    }
    if out.is_empty() {
        "fts".to_string()
    } else {
        out
    }
}

#[derive(Debug, Clone, Copy, Serialize, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "snake_case")]
pub enum BioCortexRetrievalOptInBlocker {
    ModeNotAuthorized,
    BaselineNotEstablished,
    CompileFeatureDisabled,
    OperatorDisabled,
    RuntimeDisabled,
    PerCallOptInMissing,
    OrderingBehaviorNotConnected,
    RuntimeAdapterNotApproved,
    SideSignalUnavailable,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct BioCortexRetrievalAuditRequirements {
    pub query_hash_required: bool,
    pub baseline_order_hash_required: bool,
    pub raw_query_included: bool,
    pub raw_keys_included: bool,
    pub content_included: bool,
    pub side_signal_raw_included: bool,
}

impl Default for BioCortexRetrievalAuditRequirements {
    fn default() -> Self {
        Self {
            query_hash_required: true,
            baseline_order_hash_required: true,
            raw_query_included: false,
            raw_keys_included: false,
            content_included: false,
            side_signal_raw_included: false,
        }
    }
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct BioCortexRetrievalOptInDecision {
    pub schema: String,
    pub authorization_scope: String,
    pub mode: String,
    pub mode_authorized: bool,
    pub eligible_for_side_signal: bool,
    pub may_change_search_order: bool,
    pub default_search_order_change_allowed: bool,
    pub default_calls_unchanged: bool,
    pub must_return_baseline: bool,
    pub baseline_completed: bool,
    pub baseline_key_count: usize,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub fallback_reason: Option<BioCortexRetrievalOptInBlocker>,
    pub blocking_reasons: Vec<BioCortexRetrievalOptInBlocker>,
    pub audit_requirements: BioCortexRetrievalAuditRequirements,
}

impl BioCortexRetrievalOptInDecision {
    pub fn response_contract(
        &self,
        experimental_order_available: bool,
    ) -> BioCortexRetrievalOptInResponseContract {
        let use_experimental = self.may_change_search_order && experimental_order_available;
        let fallback_reason = if use_experimental {
            None
        } else {
            self.fallback_reason
                .or(Some(BioCortexRetrievalOptInBlocker::SideSignalUnavailable))
        };
        BioCortexRetrievalOptInResponseContract {
            schema: BIOCORTEX_RETRIEVAL_OPT_IN_STORE_CONTRACT_SCHEMA.to_string(),
            returned_order_source: if use_experimental {
                BioCortexReturnedOrderSource::Experimental
            } else {
                BioCortexReturnedOrderSource::Baseline
            },
            baseline_returned: !use_experimental,
            changes_memory_search_order: use_experimental,
            fallback_reason,
            decision: self.clone(),
        }
    }
}

#[derive(Debug, Clone, Copy, Serialize, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "snake_case")]
pub enum BioCortexReturnedOrderSource {
    Baseline,
    Experimental,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct BioCortexRetrievalOptInResponseContract {
    pub schema: String,
    pub returned_order_source: BioCortexReturnedOrderSource,
    pub baseline_returned: bool,
    pub changes_memory_search_order: bool,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub fallback_reason: Option<BioCortexRetrievalOptInBlocker>,
    pub decision: BioCortexRetrievalOptInDecision,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub struct BioCortexRetrievalOptInSideSignal {
    pub candidate_key: String,
    pub score: f32,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub struct BioCortexRetrievalOptInSideSignalSummary {
    pub row_count: usize,
    pub matched_candidate_count: usize,
    pub candidate_count: usize,
    pub coverage: f64,
    pub coverage_threshold: f64,
    pub blend_alpha: f32,
    pub invalid_score_count: usize,
    pub duplicate_candidate_count: usize,
    pub available: bool,
    pub raw_scores_included: bool,
    pub raw_keys_included: bool,
    pub content_included: bool,
}

impl BioCortexRetrievalOptInSideSignalSummary {
    fn unavailable(candidate_count: usize, coverage_threshold: f64, blend_alpha: f32) -> Self {
        Self {
            row_count: 0,
            matched_candidate_count: 0,
            candidate_count,
            coverage: if candidate_count == 0 { 1.0 } else { 0.0 },
            coverage_threshold,
            blend_alpha,
            invalid_score_count: 0,
            duplicate_candidate_count: 0,
            available: false,
            raw_scores_included: false,
            raw_keys_included: false,
            content_included: false,
        }
    }
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub struct BioCortexRetrievalOptInSearchOptions {
    #[serde(default = "default_biocortex_retrieval_mode")]
    pub mode: String,
    #[serde(default)]
    pub per_call_opt_in: bool,
    #[serde(default)]
    pub compile_feature_enabled: bool,
    #[serde(default)]
    pub runtime_enabled: bool,
    #[serde(default)]
    pub operator_disabled: bool,
    #[serde(default)]
    pub runtime_adapter_approved: bool,
    #[serde(default)]
    pub ordering_behavior_connected: bool,
    #[serde(default)]
    pub side_signal_scores: Vec<BioCortexRetrievalOptInSideSignal>,
    #[serde(default = "default_biocortex_side_signal_alpha")]
    pub side_signal_alpha: f32,
    #[serde(default = "default_biocortex_side_signal_coverage_threshold")]
    pub side_signal_coverage_threshold: f64,
}

impl Default for BioCortexRetrievalOptInSearchOptions {
    fn default() -> Self {
        Self {
            mode: default_biocortex_retrieval_mode(),
            per_call_opt_in: false,
            compile_feature_enabled: false,
            runtime_enabled: false,
            operator_disabled: false,
            runtime_adapter_approved: false,
            ordering_behavior_connected: false,
            side_signal_scores: Vec::new(),
            side_signal_alpha: default_biocortex_side_signal_alpha(),
            side_signal_coverage_threshold: default_biocortex_side_signal_coverage_threshold(),
        }
    }
}

fn default_biocortex_side_signal_alpha() -> f32 {
    0.8
}

fn default_biocortex_side_signal_coverage_threshold() -> f64 {
    0.8
}

pub fn biocortex_opt_in_apply_side_signal(
    baseline_hits: &[MemorySearchHit],
    side_signal_scores: &[BioCortexRetrievalOptInSideSignal],
    side_signal_alpha: f32,
    side_signal_coverage_threshold: f64,
    gate_allows_ordering: bool,
) -> (
    Vec<MemorySearchHit>,
    BioCortexRetrievalOptInSideSignalSummary,
    bool,
) {
    let candidate_count = baseline_hits.len();
    let alpha = if side_signal_alpha.is_finite() && side_signal_alpha >= 0.0 {
        side_signal_alpha
    } else {
        default_biocortex_side_signal_alpha()
    };
    let coverage_threshold = if side_signal_coverage_threshold.is_finite()
        && (0.0..=1.0).contains(&side_signal_coverage_threshold)
    {
        side_signal_coverage_threshold
    } else {
        default_biocortex_side_signal_coverage_threshold()
    };

    if side_signal_scores.is_empty() || candidate_count == 0 {
        return (
            baseline_hits.to_vec(),
            BioCortexRetrievalOptInSideSignalSummary::unavailable(
                candidate_count,
                coverage_threshold,
                alpha,
            ),
            false,
        );
    }

    let mut matched_scores: Vec<(String, f32)> = Vec::new();
    let mut invalid_score_count = 0usize;
    let mut duplicate_candidate_count = 0usize;

    for row in side_signal_scores {
        if !row.score.is_finite() || !(-1.0..=1.0).contains(&row.score) {
            invalid_score_count += 1;
            continue;
        }
        if !baseline_hits
            .iter()
            .any(|hit| hit.record.key == row.candidate_key)
        {
            continue;
        }
        if matched_scores
            .iter()
            .any(|(key, _)| key == &row.candidate_key)
        {
            duplicate_candidate_count += 1;
            continue;
        }
        matched_scores.push((row.candidate_key.clone(), row.score));
    }

    let coverage = matched_scores.len() as f64 / candidate_count.max(1) as f64;
    let available =
        invalid_score_count == 0 && coverage >= coverage_threshold && !matched_scores.is_empty();
    let summary = BioCortexRetrievalOptInSideSignalSummary {
        row_count: side_signal_scores.len(),
        matched_candidate_count: matched_scores.len(),
        candidate_count,
        coverage,
        coverage_threshold,
        blend_alpha: alpha,
        invalid_score_count,
        duplicate_candidate_count,
        available,
        raw_scores_included: false,
        raw_keys_included: false,
        content_included: false,
    };

    if !(gate_allows_ordering && available) {
        return (baseline_hits.to_vec(), summary, false);
    }

    let mut scored_hits = baseline_hits
        .iter()
        .cloned()
        .enumerate()
        .map(|(idx, hit)| {
            let side_score = matched_scores
                .iter()
                .find(|(key, _)| key == &hit.record.key)
                .map(|(_, score)| *score)
                .unwrap_or(0.0);
            let blended = hit.score + f64::from(alpha * side_score);
            (idx, blended, hit)
        })
        .collect::<Vec<_>>();

    scored_hits.sort_by(|a, b| {
        b.1.partial_cmp(&a.1)
            .unwrap_or(std::cmp::Ordering::Equal)
            .then_with(|| a.0.cmp(&b.0))
    });

    (
        scored_hits
            .into_iter()
            .map(|(_, _, hit)| hit)
            .collect::<Vec<_>>(),
        summary,
        true,
    )
}

#[derive(Debug, Clone)]
pub struct BioCortexRetrievalOptInSearchOutcome {
    pub baseline_hits: Vec<MemorySearchHit>,
    pub returned_hits: Vec<MemorySearchHit>,
    pub response_contract: BioCortexRetrievalOptInResponseContract,
    pub side_signal_summary: BioCortexRetrievalOptInSideSignalSummary,
}

impl BioCortexRetrievalOptInSearchOutcome {
    pub fn redacted_audit(&self) -> BioCortexRetrievalOptInSearchAudit {
        BioCortexRetrievalOptInSearchAudit {
            schema: BIOCORTEX_RETRIEVAL_OPT_IN_SEARCH_AUDIT_SCHEMA.to_string(),
            authorization_scope: BIOCORTEX_RETRIEVAL_OPT_IN_AUTHORIZATION_SCOPE.to_string(),
            baseline_key_count: self.baseline_hits.len(),
            returned_hit_count: self.returned_hits.len(),
            returned_order_source: self.response_contract.returned_order_source,
            baseline_returned: self.response_contract.baseline_returned,
            changes_memory_search_order: self.response_contract.changes_memory_search_order,
            raw_query_included: false,
            raw_keys_included: false,
            content_included: false,
            side_signal_summary: self.side_signal_summary.clone(),
            response_contract: self.response_contract.clone(),
        }
    }
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub struct BioCortexRetrievalOptInSearchAudit {
    pub schema: String,
    pub authorization_scope: String,
    pub baseline_key_count: usize,
    pub returned_hit_count: usize,
    pub returned_order_source: BioCortexReturnedOrderSource,
    pub baseline_returned: bool,
    pub changes_memory_search_order: bool,
    pub raw_query_included: bool,
    pub raw_keys_included: bool,
    pub content_included: bool,
    pub side_signal_summary: BioCortexRetrievalOptInSideSignalSummary,
    pub response_contract: BioCortexRetrievalOptInResponseContract,
}

/// One memory ranked purely by cosine similarity to a query, **without**
/// the importance / recency / access-count blending that `MemorySearchHit`
/// applies. Used by L6 introspection probes (e.g. `introspect_recall`'s
/// novelty score = `1 - max(cosine)`) where the raw geometric distance
/// is the signal of interest, not "best result for the user".
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct MemoryCosineHit {
    pub record: MemoryRecord,
    /// Raw cosine ∈ [-1, 1] (typically [0, 1] for non-negative text
    /// embeddings). 1.0 = identical direction. 0.0 = orthogonal. Negative
    /// happens with signed embeddings (rare for hash / ONNX MiniLM).
    pub cosine: f32,
}

/// Cheap, always-fresh ranking metadata for one active memory — everything
/// the semantic blend needs EXCEPT the embedding. The bridge's warm embed
/// cache is a frozen snapshot: it holds the expensive embeddings but its
/// per-row `importance` / `last_accessed_at` / `access_count` / `status`
/// go stale the moment another writer (valence apply, decay, reinforce,
/// correction, archive) mutates the DB without touching the cache. A
/// metadata-only overlay (no embedding blobs, so no overflow-page I/O)
/// lets the warm path re-hydrate these fields per query and match the SQL
/// path exactly, so `mode=semantic` ranking no longer depends on how long
/// a daemon has been running.
#[derive(Debug, Clone, Copy, PartialEq)]
pub struct MemoryLiveMeta {
    pub importance: f64,
    pub last_accessed_at: i64,
    pub access_count: u64,
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
    /// Per-mode breakdown (hit_rate + latency + age within each `kind`),
    /// ordered by `total` DESC. The aggregate `hit_rate` / `p50` / `p95` above
    /// blend all modes together; this separates them so a T0 recall baseline
    /// can attribute a miss or a slow tail to a specific retrieval mode
    /// (`search_fts` vs `search_semantic` behave very differently — confirmed
    /// by the recall LEVER work). Empty when there are no rows in the window.
    pub by_mode: Vec<ModeStats>,
    /// Top miss queries (hit_count = 0), most-recurring first, capped to 10.
    pub top_miss_queries: Vec<(String, u64)>,
}

/// Per-mode (per-`kind`) slice of [`MemoryQueryStats`]. Surfaces where recall
/// is slow or missing for one retrieval mode — detail the blended aggregate
/// hides. Read-only baseline telemetry; carries no authority over ranking.
#[derive(Debug, Clone, Default, Serialize, Deserialize, PartialEq)]
pub struct ModeStats {
    /// Query kind: `search_fts`, `search_hybrid`, `search_semantic`, `get`.
    pub kind: String,
    /// Rows of this kind in the window.
    pub total: u64,
    /// Rows of this kind that returned at least one hit.
    pub hits: u64,
    /// `hits / total` (0.0 if total=0).
    pub hit_rate: f64,
    /// p50 / p95 latency within this mode (microseconds).
    pub p50_duration_us: u32,
    pub p95_duration_us: u32,
    /// Mean top-hit age (secs) across the hit rows of this mode.
    pub avg_top_hit_age_secs: f64,
}

/// One memory's retrieval-outcome tally within a window, aggregated from the
/// `retrieval_surfacing` telemetry table (rows written only when the outcome
/// collector gate `AGENT_BRIDGE_OUTCOME_COLLECTOR` is enabled). Read-only
/// diagnostic — carries no authority over ranking; it makes the surfaced→used
/// signal visible so a later, calibrated reinforce/decay rule can be designed
/// against the real distribution instead of guessed against zero data.
#[derive(Debug, Clone, Default, Serialize, Deserialize, PartialEq)]
pub struct RetrievalOutcomeMemory {
    pub key: String,
    /// Times this memory was surfaced (logged as a top-10 search hit) in-window.
    pub surfaced_count: u64,
    /// Of those surfacings, how many were attributed a `used_at` (an explicit
    /// `memory_get` within the attribution window) — the de-contaminated "used".
    pub used_count: u64,
    /// Mean surfaced rank (0 = top of results). A memory used from a deeper
    /// rank is a stronger relevance signal than one used from rank 0.
    pub avg_rank: f64,
    /// Most recent `surfaced_at` (unix secs) for this memory in-window.
    pub last_surfaced_at: i64,
}

/// Aggregate readout over `retrieval_surfacing` — the retrieval-feedback half of
/// the learning loop (surfaced→used). Read-only baseline telemetry; empty when
/// the collector has logged nothing in the window (default-OFF gate ⇒ an honest
/// "no data yet"). Reinforce/decay candidates are surfaced for a downstream,
/// separately-gated calibrated rule — this readout itself mutates nothing.
#[derive(Debug, Clone, Default, Serialize, Deserialize, PartialEq)]
pub struct RetrievalOutcomeSummary {
    /// Earliest `surfaced_at` counted (unix secs) = now − window_secs.
    pub window_start: i64,
    /// Window end (unix secs).
    pub window_end: i64,
    /// Total surfacing rows in-window.
    pub total_surfacings: u64,
    /// Surfacings with a non-NULL `used_at`.
    pub used_surfacings: u64,
    /// Distinct memories surfaced in-window.
    pub distinct_memories: u64,
    /// Distinct memories with at least one used surfacing in-window.
    pub distinct_used_memories: u64,
    /// Mean rank across all surfacings (0 = top).
    pub avg_rank_overall: f64,
    /// Mean rank across USED surfacings only (0.0 if none used).
    pub avg_rank_when_used: f64,
    /// Per-mode surfacing counts, most-first.
    pub by_mode: Vec<(String, u64)>,
    /// Reinforce candidates: memories with ≥1 used surfacing, ranked by
    /// `used_count` DESC then used/surfaced ratio DESC. Capped to `top_n`.
    pub top_used: Vec<RetrievalOutcomeMemory>,
    /// Decay candidates: memories surfaced ≥2× with ZERO used, ranked by
    /// `surfaced_count` DESC (surfaced-but-never-used = noise in results).
    /// Capped to `top_n`.
    pub top_never_used: Vec<RetrievalOutcomeMemory>,
}

/// One memory's in-window surfacing tally JOINed with its CURRENT active
/// importance — the raw material for the `retrieval_outcome_shadow` what-if
/// harness. Same aggregates as [`RetrievalOutcomeMemory`] plus `importance`,
/// so a parameterized reinforce/decay rule can be simulated (bridge-side)
/// without writing anything. Rows exist only for memories still active.
#[derive(Debug, Clone, Default, Serialize, Deserialize, PartialEq)]
pub struct RetrievalOutcomeShadowRow {
    pub key: String,
    /// Times this memory was surfaced (top-10 search hit) in-window.
    pub surfaced_count: u64,
    /// Surfacings attributed a `used_at` (explicit get within the window).
    pub used_count: u64,
    /// Mean surfaced rank (0 = top of results).
    pub avg_rank: f64,
    /// Most recent `surfaced_at` (unix secs) in-window.
    pub last_surfaced_at: i64,
    /// The memory's CURRENT importance (live read at query time).
    pub importance: f64,
    /// Constraint-class flag: kind=feedback (owner corrections/behavioral
    /// feedback) or a continuity tag marking must_block actionability /
    /// constraint / warning role. These rows are consumed ambiently (the
    /// bootstrap continuity kernel and feedback preamble) where nothing
    /// stamps `used_at`, so surfaced-never-used telemetry on them is
    /// class-level attribution bias, not deadness — the decay half of the
    /// reinforce/decay rule skips them unless protection is explicitly
    /// disabled (AB_RETRIEVAL_OUTCOME_APPLY_PROTECT_DISABLE=1).
    #[serde(default)]
    pub protected: bool,
}

/// One passive R2 fusion-shadow measurement (forum #147): what the page a
/// default (mode=fts) `memory_search` actually returned WOULD look like had a
/// semantic leg been RRF-fused in. Purely observational — the main query's
/// results are final before this is ever computed. `at` is stamped by the
/// store at insert (caller value ignored). `overlap` = |fused top-k ∩ actual|
/// / max(|actual|, |fused top-k|), 1.0 when both are empty; `gained`/`lost`
/// count keys fusion would add/drop (with a few example keys each); shifts are
/// |rank_fused − rank_actual| over keys present in BOTH pages. Skip rows
/// (`skipped=true`, metrics zeroed) count shadow opportunities where measuring
/// would be meaningless (hash-fallback embedder, page already served by the
/// semantic fallback), so coverage stays honest.
#[derive(Debug, Clone, Default, Serialize, Deserialize, PartialEq)]
pub struct FusionShadowSample {
    #[serde(default)]
    pub at: i64,
    pub query: String,
    /// Requested page size — the top-k under comparison.
    pub k: u32,
    pub actual_n: u32,
    pub semantic_n: u32,
    pub overlap: f64,
    pub gained: u32,
    pub lost: u32,
    pub gained_keys: Vec<String>,
    pub lost_keys: Vec<String>,
    pub mean_abs_shift: f64,
    pub max_abs_shift: u32,
    pub skipped: bool,
    pub skip_reason: Option<String>,
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
///
/// `read_at` (v30 / XM v0.1) is the unix-seconds timestamp the message was
/// marked read, or `None` if still unread. The P-XM-7 GC pass uses
/// `COALESCE(read_at, created_at)` as the effective last-touch timestamp.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct AgentMessageRecord {
    pub id: i64,
    pub from_session: String,
    pub to_session: String,
    pub payload: serde_json::Value,
    pub created_at: i64,
    pub read: bool,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub read_at: Option<i64>,
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

/// One read-only forum-search hit. Results are grouped by thread and carry at
/// most one matching post preview so callers can decide whether to fetch the
/// bounded recent thread history.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct ForumSearchPostRecord {
    pub id: i64,
    pub author: String,
    pub kind: String,
    pub body: String,
    pub created_at: i64,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct ForumSearchRecord {
    pub thread: ForumThreadRecord,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub matched_post: Option<ForumSearchPostRecord>,
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

/// One node in the transitive caller closure of a symbol. Output of
/// [`StateStore::codebase_impact`]. Each entry is a function reachable
/// from the original target by following `caller → target` edges
/// backwards up to `max_depth` hops.
///
/// `hop_distance` = 1 for direct callers of the original target, 2 for
/// callers-of-callers, and so on up to the requested `max_depth`.
///
/// Closure semantics:
///   • Visited set keys on the `caller` text returned by
///     [`StateStore::codebase_callers`] (qualified name of the enclosing
///     function as recorded in the calls table). A caller is emitted at
///     most once — at its **shortest** hop distance from the target.
///   • Cycles are handled by the visited set; the BFS terminates on the
///     first re-visit attempt.
///   • Per-hop fan-out is capped by the underlying `codebase_callers`
///     limit so a hub function with thousands of callers doesn't
///     explode the closure size.
///
/// Caveat: BFS uses the caller's `caller` field verbatim as the next
/// `target` for the recursive lookup. When that field is not a
/// fully-qualified path (e.g. an intra-module function recorded as the
/// bare name `bar` rather than `crate::foo::bar`), the recursive lookup
/// may miss cross-module continuations. v0 accepts this as a known
/// underreport-rather-than-overreport bound. A future v1 could join
/// against `codebase_symbols` to resolve to qualified names.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ImpactNode {
    /// Fully-qualified name of the caller as recorded in the calls
    /// table. Used as the visited-set key.
    pub qualified_name: String,
    /// File containing the call site that brought this caller into
    /// the closure (the earliest such file when multiple call sites
    /// exist at the same hop).
    pub file_path: String,
    /// 1 for direct callers of the original target, N for callers
    /// reached after N-1 intermediate hops.
    pub hop_distance: u32,
    /// The fully-qualified callee that this node calls — for hop=1
    /// this is the original `target`; for hop=N>1 it is whichever
    /// intermediate node introduced this caller into the BFS frontier.
    pub via_callee: String,
}

/// β v0 — A connected component on the subgraph defined by `cofires` +
/// `co_referenced` edges. Output of [`StateStore::hebbian_clusters`];
/// the foundational data structure for vision §5 β "seed self-evolution":
/// each cluster is a candidate for LLM abstraction into a new `seed`
/// memory. v0 ships read-only surfacing; v1 will layer LLM summary.
///
/// `hub` is the member with the highest within-cluster degree (ties
/// broken by lexicographic key ASC for determinism). `members` includes
/// the hub and is sorted ASC. `size` == `members.len()`.
///
/// `coactivation` edges (the soft Hebbian trace) are intentionally
/// excluded — they are noisy by design (every co-fire pair gets one).
/// Only explicit promotions (`cofires` tier-1, `co_referenced` tier-2)
/// constitute crystallised structure worth seeding from.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct HebbianCluster {
    pub hub: String,
    pub members: Vec<String>,
    pub size: u64,
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
    /// True when the row is *probably* a false positive — e.g. test
    /// functions whose callers are `#[tokio::test]` macro-generated and
    /// invisible to the extractor, or bare `main` which is called by the
    /// runtime rather than user code. Used by `dream codebase-report` to
    /// split the orphan list into a high-confidence section and a
    /// likely-FP tail (visual demotion, not removal). Tagging rules live
    /// in the SQLite impl (`codebase_call_stats`); see
    /// `orphan_likely_fp_rules` doc there.
    #[serde(default)]
    pub likely_fp: bool,
    /// Why the orphan was flagged as likely-FP. Short reason string so
    /// the HTML/CLI can show "test file" / "main entry" without
    /// re-running heuristics. Empty when `likely_fp = false`.
    #[serde(default, skip_serializing_if = "String::is_empty")]
    pub likely_fp_reason: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct FileFanOut {
    pub file_path: String,
    pub language: String,
    pub total_calls: u64,
    pub distinct_callees: u64,
}

/// P-ε — Aggregate substrate-readiness audit (`memory_substrate_audit`).
/// Pure read-only composition of existing trait methods + a few raw SQL
/// queries. Surfaces 7 metric families relevant to Layer-2 substrate
/// (current state, edge crystallization, retire balance, signal fidelity)
/// so the verify-design-act workflow has continuous evidence for the
/// other 4 proposals (P-α/β/γ/δ) in `verify_memory_layers_vs_seed_l1l2l3`.
///
/// **Caveat**: this report does NOT touch the substrate itself — it
/// reports the L1+L2 observable surface. No schema changes, no writes.
#[derive(Debug, Clone, Default, Serialize, Deserialize)]
pub struct SubstrateAuditReport {
    pub version: u8,
    pub generated_at_secs: i64,
    pub window_secs: u64,
    pub m1_components: SubstrateComponents,
    pub m2_edges: EdgeBreakdown,
    pub m3_coactivation: CoactivationGrowth,
    pub m4_retire: RetireBalance,
    pub m5_edge_coverage: EdgeCoverage,
    pub m6_embedding: EmbeddingBackendDist,
    pub m7_signal_fidelity: SignalFidelityCompact,
    pub m8_query: MemoryQueryStats,
    /// **Method A (#204 / #203)** — kinds excluded from M7 `signal_fidelity`
    /// computation when the audit is run with the `--exclude-kinds` flag.
    /// Empty for default audits. Populated by CLI handler before output
    /// so downstream readers (Day-7/14/28 trend diff JSONs) can tell
    /// apart full-set vs filtered runs without parsing file names.
    #[serde(default)]
    pub excluded_kinds: Vec<String>,
}

/// M1 — connected-component breakdown of crystallized substrate edges.
/// Hairball detection: `components=1` and `largest_size ≈ total_clustered_nodes`.
#[derive(Debug, Clone, Default, Serialize, Deserialize)]
pub struct SubstrateComponents {
    pub min_size: i64,
    pub components: u64,
    pub total_clustered_nodes: u64,
    pub largest_size: u64,
    /// Per-component sizes, sorted descending.
    pub distribution: Vec<u64>,
}

/// M2 — Edge density per edge_type. Splits L1-authored (`relates`,
/// `derived_from`, etc.) from L2-crystallized (`cofires`, `co_referenced`).
#[derive(Debug, Clone, Default, Serialize, Deserialize)]
pub struct EdgeBreakdown {
    pub total: u64,
    pub per_type: std::collections::HashMap<String, u64>,
    /// `total / active_memories` (0.0 if no active memories).
    pub density_per_active: f64,
}

/// M3 — coactivation table growth. Tracks trace expansion vs saturation.
/// Distinct from [`CoactivationStats`] (the β-trigger summary) — this is
/// the temporal-growth-flavoured view scoped to a window.
#[derive(Debug, Clone, Default, Serialize, Deserialize)]
pub struct CoactivationGrowth {
    pub total_pairs: u64,
    /// Pairs whose `last_at >= now - window_secs`.
    pub recent_active: u64,
    pub avg_count: f64,
    pub max_count: u64,
    /// Estimated new pairs per day = `recent_active / (window_secs / 86400)`.
    pub est_daily_new_pairs: f64,
}

/// M4 — retire state machine balance + 7d delta.
#[derive(Debug, Clone, Default, Serialize, Deserialize)]
pub struct RetireBalance {
    pub active: u64,
    pub archived: u64,
    pub superseded: u64,
    pub tombstoned: u64,
    /// `archived / (active + archived + superseded + tombstoned)`.
    pub archived_fraction: f64,
    /// Net change over the window. Path-a: snapshot diff; path-b:
    /// row-timestamp fallback. Approximate when `is_approximate=true`.
    pub delta: RetireDelta,
}

#[derive(Debug, Clone, Default, Serialize, Deserialize)]
pub struct RetireDelta {
    pub active: i64,
    pub archived: i64,
    pub superseded: i64,
    pub tombstoned: i64,
    /// True when computed from row timestamps (no prior snapshot found);
    /// false when computed by snapshot diff.
    pub is_approximate: bool,
}

/// M5 — fraction of active **non-skill** memories with ≥1 *live*
/// cofires/co_referenced edge (both endpoints active non-skill).
///
/// `active_total` excludes `kind='skill'`: the skill catalog floods the
/// active pool with edge-less rows and would deflate the fraction to a
/// measurement artifact (1272 skill rows seen 2026-05-29). The numerator
/// likewise requires both edge endpoints to be active non-skill, so edges
/// dangling to hard-deleted / tombstoned / skill nodes do not count as
/// coverage — robust without an ON DELETE CASCADE (`memory_edges` is
/// deliberately FK-free; soft pointers are the museum pattern).
#[derive(Debug, Clone, Default, Serialize, Deserialize)]
pub struct EdgeCoverage {
    /// Distinct active non-skill memories with ≥1 live cofires/co_referenced edge.
    pub active_with_l2_edge: u64,
    /// Active memories excluding `kind='skill'` (the M5 denominator).
    pub active_total: u64,
    pub fraction: f64,
}

/// M6 — embedding backend distribution (P9/P12 column).
#[derive(Debug, Clone, Default, Serialize, Deserialize)]
pub struct EmbeddingBackendDist {
    pub onnx: u64,
    pub hash: u64,
    pub unknown: u64,
    pub total: u64,
    /// `(hash + unknown) / total` (0.0 if total=0).
    pub stale_fraction: f64,
}

/// M7 — compact view of `signal_fidelity_stats` (no misrank lists).
#[derive(Debug, Clone, Default, Serialize, Deserialize)]
pub struct SignalFidelityCompact {
    pub r_all: f64,
    pub r_touched: f64,
    pub n_touched: u64,
    /// "noise" / "weak" / "moderate" / "strong" per
    /// `signal_fidelity_stats` verdict thresholds (|r| < 0.2 = noise,
    /// < 0.4 = weak, < 0.6 = moderate, ≥ 0.6 = strong).
    pub verdict: String,
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
/// P-α — Stats returned by a single `decay_coactivation_once` sweep.
///
/// The decay rule (integer half-life) halves `count` and advances
/// `last_at` by `tau_secs` for every row where `last_at + tau ≤ now`.
/// Rows that drop to `count < 1` are DELETEd. One sweep applies one
/// half-life advance per eligible row; very stale tables (last_at far
/// in the past) need multiple iterations within the same tick to catch
/// up. The impl caps iterations at `max_iterations` (default 10).
///
/// Caller (bg task or CLI) injects `now` for deterministic testability.
/// See `docs/DESIGN-P-alpha-always-warm-coactivation-tick.md`.
#[derive(Debug, Clone, Copy, Default, Serialize, Deserialize)]
pub struct DecayCoactivationStats {
    /// Total UPDATE-eligible rows touched across all iterations of this
    /// sweep. Counts each iteration's affected rows (so if 5 rows decayed
    /// twice in one sweep, `swept = 10`).
    pub swept: u64,
    /// Rows DELETEd because their `count` dropped to `< 1` this sweep.
    pub pruned: u64,
    /// How many UPDATE/DELETE rounds ran in this sweep (1..=max).
    /// Returns `0` only when the table is empty or no row is eligible.
    pub iterations: u32,
}

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
    /// Memories at or above the reinforce ceiling (`importance >= 0.95`).
    /// The saturation mirror of `n_floor_importance`: a high count is the
    /// "reinforce ratchet pinned everyone to the top" tell. Watch this fall
    /// after the multiplicative-reinforce fix (2026-06-30) lands.
    pub n_ceiling_importance: u64,
    /// Distinct `importance` values among the top-50 rows by importance.
    /// The top-tier discrimination metric: `1`–`2` means importance has
    /// collapsed onto a single ceiling value and contributes no ordering to
    /// the search-rank `+w·importance` bonus where it matters most; a healthy
    /// value approaches the observed top-tier row count, capped at 50.
    pub top_distinct_importance: u64,
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

/// The dominant `(backend, dim)` pair among active stored memory embeddings —
/// the embedding space the store was *actually* written in. Used by the startup
/// embedding dim-guard to detect a process whose active embedder produces a
/// different dimension than the store holds (silent model drift: a stale
/// launchd env, a wrong `AGENT_BRIDGE_ONNX_MODEL`, or an ONNX load that fell
/// back to a different model). `dim`/`backend` are `None` for an empty store.
#[derive(Debug, Clone, Default, PartialEq, Eq, Serialize, Deserialize)]
pub struct EmbeddingProfile {
    /// `embedding_backend` tag shared by the most active rows (e.g.
    /// `"gte-multilingual-base"`). `None` when the store has no embeddings.
    pub backend: Option<String>,
    /// Vector dimension (floats) of those rows. `None` when unknown/empty.
    pub dim: Option<usize>,
    /// How many active rows share this dominant `(backend, dim)`.
    pub rows: u64,
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

/// One active memory row's embedding columns, for the read-only INT8
/// quantization shadow diagnostic (`embedding_quant_shadow` MCP tool).
///
/// Pure data accessor: the f32 `embedding` BLOB (the source of truth) plus the
/// optional v37 INT8 shadow pair. `embedding_i8`/`embedding_i8_scale` are
/// `None` for rows whose shadow has not been populated (pre-v37 rows, or rows
/// whose f32 embedding was reused rather than recomputed). No decode or
/// quantize happens here — the caller (the bridge diagnostic) owns the math.
#[derive(Debug, Clone)]
pub struct EmbeddingQuantRow {
    /// Raw little-endian f32 bytes (decode via [`decode_embedding`]).
    pub embedding: Vec<u8>,
    /// Per-row INT8 codes BLOB (1 byte/code, no framing), or `None` if unshadowed.
    pub embedding_i8: Option<Vec<u8>>,
    /// Per-row absmax dequant scale, or `None` if unshadowed.
    pub embedding_i8_scale: Option<f32>,
}

/// One active `present_outcome` row's already-normalized metadata facets,
/// read-only for the `outcome_valence_shadow` valence-derivation diagnostic
/// (arc5 stage V0). The valence rule reads only the `verify:`/`method:`/
/// `decision:`/`embody:` tags that `build_outcome_memory` writes
/// (`crates/bridge/src/present_ingest.rs`); NO free-text content is read.
/// `tags_json` holds the raw JSON-array TEXT from the `tags` column; the caller
/// decodes it with serde_json. See
/// `docs/design/OUTCOMES_VALENCE_TRANSPORT_CONTRACT_DESIGN_2026_06_30.md`.
#[derive(Debug, Clone)]
pub struct OutcomeMetaRow {
    pub key: String,
    pub scope: Option<String>,
    pub tags_json: String,
    /// Current stored importance (0.0–1.0) — read so the gated
    /// `outcome_valence_importance_apply` tool can report old→new diffs
    /// without a second query. 0.5 is the historical hardcoded default.
    pub importance: f64,
}

/// Memory kinds treated as bulk-imported reference catalog rather than
/// working memory. Excluded from `S234Counts::memories_active` so
/// routine catalog churn (decay-archive, restore, bulk-import) doesn't
/// trigger C3 s2 "memories drop" false-positive alerts. Matches the
/// `catalog_kinds` field in `memory_stats` (P17b working/catalog split,
/// see `project_palace_working_catalog_split_p17_shipped`).
///
/// Single source of truth for both `s234_counts` and the
/// `memory_stats` MCP tool — if a new bulk-import kind is added,
/// update here and both surfaces pick it up automatically.
pub const CATALOG_KINDS_C3: &[&str] = &["skill"];

/// Lookback window (seconds) for the S2 *recently-tombstoned* conservation
/// credit (#122, 2026-06-24). Must comfortably exceed the C3 §3.4 5-minute
/// anchor interval so consolidation tombstones inside the compared window are
/// credited; over-coverage is safe because this credit only ever REDUCES S2
/// false-fires and a hard DELETE leaves no tombstoned row to credit. 10 min.
pub const S2_TOMBSTONE_RECENT_WINDOW_SECS: i64 = 600;

/// Memory kinds excluded from graph-*coverage* denominators (orphan_fraction,
/// M5 edge-coverage, degree/hub topology, P4 evolved coverage). These are
/// edge-less *by design*, so counting them in the denominator deflates the
/// fraction into a pure measurement artifact — the same rationale the M5
/// query comment gives for `skill`:
///   - `skill`           — bulk-imported reference catalog (never graph citizens).
///   - `present_outcome` — the output→memory audit cohort; `related_keys` is
///     empty by anti-fabrication design, so it can only earn edges organically
///     via dream-promote, never at write time (thread 6 #1983 ruling,
///     2026-06-04: no live #6 owner → operator ruled "exclude denominator,
///     defer recall-scope").
///
/// Deliberately DISTINCT from [`CATALOG_KINDS_C3`], which governs C3 drop-alert
/// / `memory_stats` catalog accounting and stays `skill`-only. Coverage
/// exclusion and catalog accounting are different concerns — do not merge them.
pub const COVERAGE_EXCLUDED_KINDS: &[&str] = &["skill", "present_outcome"];

/// SQL predicate fragment excluding [`COVERAGE_EXCLUDED_KINDS`] from a coverage
/// denominator. `alias` is the table alias (`"m"` → `m.kind ...`) or `""` for an
/// unqualified column. The kind list is a compile-time constant of SQL-safe
/// identifiers, so the emitted fragment carries no caller-influenced text.
///
/// Single source of truth: every coverage denominator in `sqlite.rs`
/// (`graph_topology`, substrate-audit M5) routes through this, and the in-memory
/// mirror (`memory_graph_topology_record_visible` in the bridge crate) keys off
/// the same [`COVERAGE_EXCLUDED_KINDS`] slice, so the SQL path and the MCP path
/// stay symmetric.
pub fn coverage_kind_exclusion_sql(alias: &str) -> String {
    let col = if alias.is_empty() {
        "kind".to_string()
    } else {
        format!("{alias}.kind")
    };
    let list = COVERAGE_EXCLUDED_KINDS
        .iter()
        .map(|k| format!("'{k}'"))
        .collect::<Vec<_>>()
        .join(", ");
    format!("{col} NOT IN ({list})")
}

/// Snapshot of the three counts feeding C3 §3.4 S2-S4 drop detection
/// (`memories.count` active / `forum_threads.count` / `memory_edges.count`).
/// Light-weight — three `SELECT COUNT(*)` calls, designed to be safe
/// to read on a 30s tick.
#[derive(Debug, Clone, Copy, Default, Serialize, Deserialize, PartialEq, Eq)]
pub struct S234Counts {
    /// Memories with `status='active'` AND `kind NOT IN CATALOG_KINDS_C3`
    /// (i.e. *working* active memories, excluding bulk-imported catalog
    /// kinds like `skill`). Excludes archived + tombstoned so dream-tier
    /// GC bulk-status-change doesn't trigger S2 false positives, and
    /// excludes catalog kinds so importance-decay archives on the
    /// reference catalog don't false-alarm either.
    pub memories_active: u64,
    /// Total `forum_threads` rows (status-agnostic — archive/resolve
    /// don't delete rows so this is stable).
    pub forum_threads: u64,
    /// Total `memory_edges` rows.
    pub memory_edges: u64,
    /// Count of *retired* working memories: `status != 'active'`
    /// (archived / superseded / tombstoned) AND `kind NOT IN
    /// CATALOG_KINDS_C3` — same universe as `memories_active` but on the
    /// retired side. Lets S2 distinguish a benign active→retired
    /// lifecycle transition (active↓ matched by an equal retired↑, total
    /// conserved) from genuine row disappearance (active↓ with no
    /// retired↑ — the inode-swap / accidental-DELETE failure class).
    pub memories_retired: u64,
    /// Count of memories in the two *benign-transition* retired tiers:
    /// `status IN ('archived','superseded')` AND `kind NOT IN
    /// CATALOG_KINDS_C3`. This is the conservation credit S2 actually
    /// tests against (NOT `memories_retired`): bulk hygiene moves active
    /// rows here (active→archived / →superseded), whereas
    /// `purge-tombstones` hard-removes rows from the *tombstoned* tier in
    /// the same daily window — so `memories_retired` (which counts
    /// tombstoned too) can FALL even as a benign active→archived
    /// transition happens, zeroing a `retired`-delta credit and firing S2
    /// falsely (#110, 2026-06-11). archived+superseded is immune to
    /// same-window purge.
    pub memories_archived_superseded: u64,
    /// Count of *recently* tombstoned working memories: `status='tombstoned'`
    /// AND `kind NOT IN CATALOG_KINDS_C3` AND `updated_at` within the last
    /// `S2_TOMBSTONE_RECENT_WINDOW_SECS`. This is an ADDITIVE conservation
    /// credit on top of `memories_archived_superseded` (#122, 2026-06-24):
    /// dream/curate consolidation tombstones its `curated_implicit_*`
    /// by-products active→tombstoned, which `archived+superseded` does not
    /// credit, so a consolidation-heavy window shows `unexplained_drop≈the
    /// consolidation count` and S2 false-fires. Crediting *recently*
    /// tombstoned rows (by `updated_at`, NOT the tombstoned tier *count*)
    /// is immune to the #110 purge trap — `purge-tombstones` removes rows
    /// with OLD `updated_at`, never the freshly-tombstoned ones — and is
    /// safe against the inode-swap/accidental-DELETE class: a hard DELETE
    /// leaves NO tombstoned row, so it is never credited and S2 still fires.
    pub memories_tombstoned_recent: u64,
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
    /// Normalize per-node retrieval/maintenance metadata when writing a
    /// shared sync transport file. Access counters and decay-derived ranking
    /// are local signals; serializing them verbatim makes otherwise unchanged
    /// peers rewrite `memory.jsonl` every sync cycle.
    pub stable_sync_metadata: bool,
    /// When `Some(secs)`, exclude tombstoned rows whose `updated_at` is older
    /// than `secs` ago (a sync-window cutoff). The sync transport sets this to
    /// the purge window so the exported `memory.jsonl` stops carrying zombie
    /// tombstones: `memory_import` Inserts any absent-key row (incl. a
    /// tombstone), so without this an aged tombstone is resurrected from the
    /// export on the next sync — right after `purge-tombstones` deleted it —
    /// and the deletion never converges (the export grows unbounded with dead
    /// rows). `None` = export everything (full backups).
    pub exclude_tombstoned_older_than_secs: Option<i64>,
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
    /// Track MS-3 — conflict-aware merge by per-record version vector. When an
    /// existing row is present and both sides carry a vector: the dominating
    /// version wins (`Update`/`Skip`); a *concurrent* pair (neither dominates)
    /// is preserved non-destructively as a conflict copy instead of silently
    /// dropping the loser. Falls back to `NewerWins` when either side has no
    /// vector yet (rollout / legacy rows).
    VersionVectorMerge,
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
    /// Track MS-3 — rows preserved as non-destructive conflict copies because
    /// the incoming version was *concurrent* with the existing one (neither
    /// version vector dominated). Both versions survive; zero rows are lost.
    #[serde(default)]
    pub conflict_copies: u64,
}

#[async_trait]
pub trait StateStore: Send + Sync {
    async fn save_session(&self, session: &StoredSession) -> Result<()>;

    /// v41 — stamp the spawned child's process identity (pid/pgid/starttime
    /// plus owning-process identity) onto its session row so an orphan reaper
    /// can later kill proven-abandoned process groups. Default is an ERROR:
    /// a backend that silently drops the stamp would leave the reaper blind
    /// while looking wired-up.
    async fn update_session_process(
        &self,
        id: &SessionId,
        proc_pid: i64,
        proc_pgid: i64,
        proc_start_ticks: Option<i64>,
        owner_pid: i64,
        owner_start_ticks: Option<i64>,
    ) -> Result<bool> {
        let _ = (
            id,
            proc_pid,
            proc_pgid,
            proc_start_ticks,
            owner_pid,
            owner_start_ticks,
        );
        Err(ab_core::Error::Backend(
            "update_session_process unsupported by this store backend".into(),
        ))
    }

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
        client_name: Option<String>,
        profile: Option<String>,
        source: Option<String>,
        model: Option<String>,
        model_reasoning_effort: Option<String>,
        codex_host: Option<String>,
    ) -> Result<()> {
        let _ = (
            tool_name,
            duration_ms,
            ok,
            args_size,
            result_size,
            client_name,
            profile,
            source,
            model,
            model_reasoning_effort,
            codex_host,
        );
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

    /// L6 P2 — Row-level MCP tool-call telemetry within the last
    /// `window_secs` seconds, sorted by `ts ASC` so callers can do
    /// in-order time-window analysis (e.g. detect follow-up activity
    /// after a high-yield call). Capped at `limit` rows. Default impl
    /// returns empty so non-SQLite backends silently no-op the L6 P2
    /// `tool_call_attention_report` MCP tool.
    async fn recent_mcp_tool_calls(
        &self,
        window_secs: i64,
        limit: u32,
    ) -> Result<Vec<McpToolCallRow>> {
        let _ = (window_secs, limit);
        Ok(Vec::new())
    }

    /// Append a produced semantic event (SSB typed event spine, Phase 1).
    /// Default impl is a no-op so non-sqlite stores stay compilable.
    async fn record_semantic_event(&self, event: SemanticEventRecord) -> Result<()> {
        let _ = event;
        Ok(())
    }

    /// Most-recent produced semantic events within `window_secs`, newest first.
    async fn recent_semantic_events(
        &self,
        window_secs: i64,
        limit: u32,
    ) -> Result<Vec<SemanticEventRecord>> {
        let _ = (window_secs, limit);
        Ok(Vec::new())
    }

    /// Aggregate stats over `mcp_tool_calls`, optionally narrowed by caller
    /// attribution. Default impl falls back to the unfiltered aggregate.
    async fn mcp_tool_call_stats_filtered(
        &self,
        window_secs: i64,
        top_n: u32,
        filter: McpToolCallFilter,
    ) -> Result<Vec<McpToolCallStats>> {
        let _ = filter;
        self.mcp_tool_call_stats(window_secs, top_n).await
    }

    /// Group recent MCP traffic by source/client/profile attribution.
    async fn mcp_tool_source_stats(
        &self,
        window_secs: i64,
        top_n: u32,
    ) -> Result<Vec<McpToolSourceStats>> {
        self.mcp_tool_source_stats_filtered(window_secs, top_n, McpToolCallFilter::default())
            .await
    }

    /// Group recent MCP traffic by source/client/profile/model attribution,
    /// optionally narrowed by the same attribution filters used for hot-tool
    /// stats.
    async fn mcp_tool_source_stats_filtered(
        &self,
        window_secs: i64,
        top_n: u32,
        filter: McpToolCallFilter,
    ) -> Result<Vec<McpToolSourceStats>> {
        let _ = (window_secs, top_n, filter);
        Ok(Vec::new())
    }

    // ─── memory.* — agent self-memory (v0.4) ───────────────────────────

    /// Insert or replace a memory by key. Truncates `content` to
    /// [`MEMORY_CONTENT_CAP`]. Updates `updated_at` to `now`; on first insert
    /// `created_at` is also set, `access_count` starts at 0.
    async fn memory_save(&self, mem: &MemoryRecord) -> Result<()>;

    /// Fetch one exact key without changing access counters or any query,
    /// surfacing, retrieval-use, or coactivation telemetry. Active, archived,
    /// superseded, and conflict rows return their exact current envelope;
    /// tombstones return only a content-free marker. This is an internal
    /// diagnostic read, not a retrieval or truth-adapter admission surface.
    async fn memory_peek(&self, key: &str) -> Result<MemoryPeekResult> {
        let _ = key;
        Err(ab_core::Error::Backend(
            "memory_peek unsupported by this store backend".into(),
        ))
    }

    /// Read retained-row markers, content-free tombstones, and timestamped
    /// visible edges in one bounded store snapshot. Implementations must not
    /// mutate access or retrieval telemetry, bulk-load retained content, or
    /// expose tombstone-incident relationships. Unsupported backends fail
    /// closed rather than returning an empty snapshot that could be mistaken
    /// for completeness.
    async fn memory_evidence_snapshot(
        &self,
        limits: MemoryEvidenceSnapshotLimits,
    ) -> Result<MemoryEvidenceSnapshot> {
        let _ = limits;
        Err(ab_core::Error::Backend(
            "memory_evidence_snapshot unsupported by this store backend".into(),
        ))
    }

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

    /// Frozen-clock search used by the reference admission surface. Backends
    /// that cannot bind an as-of value fail closed instead of silently falling
    /// back to a wall-clock ranking.
    async fn memory_search_as_of(
        &self,
        query: &str,
        tags_any: &[String],
        limit: u32,
        as_of_secs: i64,
    ) -> Result<Vec<MemorySearchHit>> {
        let _ = (query, tags_any, limit, as_of_secs);
        Err(ab_core::Error::Backend(
            "memory_search_as_of unsupported by this store backend".into(),
        ))
    }

    /// Protected BioCortex opt-in search surface.
    ///
    /// Default calls still use baseline `memory_search`. This protected wrapper
    /// can return an experimental order only when the caller supplies explicit
    /// opt-in, runtime approval, an ordering connection flag, and sufficient
    /// side-signal coverage. Every blocked or malformed side-signal path returns
    /// the baseline list.
    async fn memory_search_biocortex_opt_in(
        &self,
        query: &str,
        tags_any: &[String],
        limit: u32,
        options: BioCortexRetrievalOptInSearchOptions,
    ) -> Result<BioCortexRetrievalOptInSearchOutcome> {
        let baseline_hits = self.memory_search(query, tags_any, limit).await?;
        let side_signal_scores = options.side_signal_scores;
        let side_signal_alpha = options.side_signal_alpha;
        let side_signal_coverage_threshold = options.side_signal_coverage_threshold;
        let decision = BioCortexRetrievalOptInRequest {
            mode: options.mode,
            per_call_opt_in: options.per_call_opt_in,
            compile_feature_enabled: options.compile_feature_enabled,
            runtime_enabled: options.runtime_enabled,
            operator_disabled: options.operator_disabled,
            baseline_completed: true,
            baseline_key_count: baseline_hits.len(),
            runtime_adapter_approved: options.runtime_adapter_approved,
            ordering_behavior_connected: options.ordering_behavior_connected,
        }
        .evaluate();
        let (returned_hits, side_signal_summary, experimental_order_available) =
            biocortex_opt_in_apply_side_signal(
                &baseline_hits,
                &side_signal_scores,
                side_signal_alpha,
                side_signal_coverage_threshold,
                decision.may_change_search_order,
            );
        let response_contract = decision.response_contract(experimental_order_available);

        Ok(BioCortexRetrievalOptInSearchOutcome {
            returned_hits,
            baseline_hits,
            response_contract,
            side_signal_summary,
        })
    }

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
    /// Results are ordered by weight descending and then canonical edge
    /// identity, so equal-weight neighbours do not inherit SQLite row order.
    async fn memory_neighbors(&self, key: &str) -> Result<Vec<MemoryEdge>>;

    /// Deterministic bounded neighbour read used by frozen reference search.
    /// Backends may override this to enforce the cap in their query. The
    /// default is functionally bounded after retrieval and preserves the
    /// canonical ordering contract.
    async fn memory_neighbors_bounded(&self, key: &str, limit: usize) -> Result<Vec<MemoryEdge>> {
        let mut edges = self.memory_neighbors(key).await?;
        edges.sort_by(|a, b| {
            b.weight
                .partial_cmp(&a.weight)
                .unwrap_or(std::cmp::Ordering::Equal)
                .then_with(|| a.from_key.cmp(&b.from_key))
                .then_with(|| a.to_key.cmp(&b.to_key))
                .then_with(|| a.edge_type.cmp(&b.edge_type))
        });
        edges.truncate(limit);
        Ok(edges)
    }

    /// Active memory keys that start with `prefix` (literal byte-prefix match
    /// on the primary key — `substr()` comparison, so `_`/`%` in the prefix
    /// stay literal), `status='active'` only, oldest-first, capped at `limit`.
    /// Added for session_curate's prior-handoff retirement (staleness-gate
    /// slice ③, 2026-07-10): a curate run looks up its own session's earlier
    /// in-flight snapshots to supersede them.
    async fn memory_active_keys_with_prefix(
        &self,
        prefix: &str,
        limit: usize,
    ) -> Result<Vec<String>>;

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

    /// Deterministic hybrid leg for a frozen reference request. The graph
    /// read is explicitly non-telemetry-mutating and bounded by
    /// `graph_fanout`; unsupported backends fail closed.
    async fn memory_search_hybrid_as_of(
        &self,
        query: &str,
        tags_any: &[String],
        limit: u32,
        k: f64,
        expand_top: u32,
        as_of_secs: i64,
        graph_fanout: usize,
        mutate_graph_reads: bool,
    ) -> Result<Vec<MemorySearchHit>> {
        let _ = (
            query,
            tags_any,
            limit,
            k,
            expand_top,
            as_of_secs,
            graph_fanout,
            mutate_graph_reads,
        );
        Err(ab_core::Error::Backend(
            "memory_search_hybrid_as_of unsupported by this store backend".into(),
        ))
    }

    /// Side-effect-free coactivation read for the frozen reference policy.
    /// The ordinary coactivation API defaults to an empty result for legacy
    /// backends; a reference run must instead fail when support is absent.
    async fn memory_coactivation_among_reference(
        &self,
        keys: &[String],
    ) -> Result<Vec<CoactivationEdge>> {
        let _ = keys;
        Err(ab_core::Error::Backend(
            "memory_coactivation_among_reference unsupported by this store backend".into(),
        ))
    }

    /// Fully bounded reference search: frozen as-of, bounded graph fan-out,
    /// deterministic ordering, and a telemetry-free context projection.
    async fn memory_search_reference(
        &self,
        query: &str,
        tags_any: &[String],
        limit: u32,
        k: f64,
        expand_top: u32,
        options: MemorySearchReferenceOptions,
    ) -> Result<MemorySearchReferenceContext> {
        if options.as_of_secs < 0 {
            return Err(ab_core::Error::Backend(
                "reference as_of_secs must be non-negative".into(),
            ));
        }
        if limit == 0 || limit > 40 {
            return Err(ab_core::Error::Backend(
                "reference final limit must be in 1..=40".into(),
            ));
        }
        if options.graph_fanout == 0 || options.graph_fanout > 256 {
            return Err(ab_core::Error::Backend(
                "reference graph fanout must be in 1..=256".into(),
            ));
        }
        if !k.is_finite() || !(1.0..=200.0).contains(&k) {
            return Err(ab_core::Error::Backend(
                "reference RRF k must be finite and in 1..=200".into(),
            ));
        }
        if expand_top == 0 || expand_top > 20 {
            return Err(ab_core::Error::Backend(
                "reference expand_top must be in 1..=20".into(),
            ));
        }
        if options
            .exclude_kinds
            .iter()
            .any(|kind| kind.trim().is_empty())
        {
            return Err(ab_core::Error::Backend(
                "reference excluded kinds must be non-empty".into(),
            ));
        }

        // Mirror the declared full-hybrid reference pipeline: an output
        // exclusion overfetches fivefold before filtering. With the frozen
        // limit=10 this yields fused pool 50, FTS-ranked pool 200 and raw FTS
        // scan cap 800.
        let fused_pool_limit = limit.saturating_mul(5).min(200);
        let mut hits = self
            .memory_search_hybrid_as_of(
                query,
                tags_any,
                fused_pool_limit,
                k,
                expand_top,
                options.as_of_secs,
                options.graph_fanout,
                false,
            )
            .await?;
        if options.coactivation_rerank && hits.len() >= 2 {
            let keys: Vec<String> = hits.iter().map(|hit| hit.record.key.clone()).collect();
            let edges = self.memory_coactivation_among_reference(&keys).await?;
            if !edges.is_empty() {
                let mut per_key = std::collections::BTreeMap::<String, u64>::new();
                for edge in edges {
                    let count_a = per_key.entry(edge.key_a).or_insert(0);
                    *count_a = count_a.saturating_add(edge.count);
                    let count_b = per_key.entry(edge.key_b).or_insert(0);
                    *count_b = count_b.saturating_add(edge.count);
                }
                for hit in &mut hits {
                    let count = per_key.get(&hit.record.key).copied().unwrap_or(0);
                    hit.score *= 1.0 + 0.2 * (1.0 + count as f64).ln();
                }
                hits.sort_by(|a, b| {
                    b.score
                        .partial_cmp(&a.score)
                        .unwrap_or(std::cmp::Ordering::Equal)
                        .then_with(|| a.record.key.cmp(&b.record.key))
                });
            }
        }
        hits.retain(|hit| {
            !options
                .exclude_kinds
                .iter()
                .any(|kind| kind == &hit.record.kind)
                && memory_record_ttl_is_live_at(&hit.record, options.as_of_secs)
        });
        hits.truncate(limit as usize);
        project_memory_search_reference_hits(&hits, options.max_context_bytes)
    }

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
    /// Moves `importance` a `step` FRACTION of its remaining headroom toward
    /// `ceiling` (`importance += step·(ceiling − importance)`) for every active
    /// row that has `access_count >= min_access` AND was read within the
    /// window (`last_accessed_at > now - window_secs`). This multiplicative
    /// (not flat-additive) step asymptotes toward the ceiling without ever
    /// reaching it, so repeatedly-reinforced rows stay ordered by reinforcement
    /// frequency instead of collapsing onto a single ceiling value — see the
    /// 2026-06-30 saturation finding. Rows already `== ceiling` are left as-is.
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

    /// **Method A (#204 / #203)** — variant of [`signal_fidelity_stats`]
    /// that excludes rows whose `kind` is in `exclude_kinds`.
    ///
    /// Designed for Day-7 (5/20) P-α audit where L5 P3 session-bootstrap
    /// preamble (`a3af97a`) systematically pumps `kind=feedback` access,
    /// confounding the M7 `r_touched` reading. Filtering `["feedback"]`
    /// yields a pure-P-α subset reading; combined with the unfiltered
    /// run in dual-report mode, the audit can distinguish P-α signal
    /// from L5 P3 artifact. (Since 2026-07-07 the machine-written retrieval
    /// telemetry rows use kind=retrieval_feedback; kind=feedback is
    /// corrections / owner feedback only, so an equivalent audit today
    /// would filter both kinds.)
    ///
    /// Default no-op: returns empty `SignalFidelityStats`. SQLite impl
    /// extends the base query with `AND kind NOT IN (...)`. When
    /// `exclude_kinds` is empty the result MUST match
    /// [`signal_fidelity_stats`] bit-exact (validated by test).
    async fn signal_fidelity_stats_excluding(
        &self,
        _top_n: u32,
        _exclude_kinds: &[String],
    ) -> Result<SignalFidelityStats> {
        Ok(SignalFidelityStats::default())
    }

    /// Apply [`CompactPolicy`]; returns the keys that were (or would be)
    /// retired. Honours `dry_run`. Retirement is a **tombstone** (not a hard
    /// DELETE) so the count stays conservation-consistent for the C3 s2 check
    /// and the deletion propagates across peers via NewerWins sync; final row
    /// removal is `memory_purge_tombstones`. Acts only on `status='active'`
    /// rows and skips durable ones (importance ≥ 0.6, author-linked via
    /// `related_keys`, or graph-connected).
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

    /// β v0 (2026-05-13) — Surface connected components on the
    /// `cofires` + `co_referenced` subgraph. Each component is a
    /// candidate cluster for vision §5 β seed-self-evolution; v0
    /// returns the raw groups so the operator (or v1 LLM pass) can
    /// inspect thematic coherence before paying summary cost.
    ///
    /// `min_size` filters out trivial (e.g. size-1 singletons in the
    /// rare case of self-edges; size-2 isolated pairs if uninteresting).
    /// Default callers pass 2. Components sorted by size DESC, ties
    /// broken by hub key ASC.
    ///
    /// `coactivation` edges are excluded: they fire on every pair and
    /// would collapse the graph into one giant component without
    /// signal. Only crystallised Hebbian edges count toward structure.
    async fn hebbian_clusters(&self, min_size: i64) -> Result<Vec<HebbianCluster>> {
        let _ = min_size;
        Ok(Vec::new())
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

    /// Read-only snapshot of every active row's embedding columns for the INT8
    /// quantization shadow diagnostic (`embedding_quant_shadow`): the f32
    /// `embedding` (source of truth) plus the optional v37 INT8 shadow pair.
    /// Reads only `status='active' AND embedding IS NOT NULL`; mutates nothing,
    /// never touches the retrieval path, never drops f32. Default impl returns
    /// empty so non-SQLite stores stay trait-compatible.
    async fn active_embedding_quant_rows(&self) -> Result<Vec<EmbeddingQuantRow>> {
        Ok(Vec::new())
    }

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

    /// Counts of active memories grouped by `scope`. Backs the read-only
    /// `memory_scope_survey` diagnostic, which detects project-scope
    /// fragmentation (several legacy scope strings that canonicalize to one
    /// project identity). NULL/empty scope is reported as the literal string
    /// `"global"`. Read-only; default impl returns empty vec.
    async fn memory_scope_counts(&self) -> Result<Vec<(String, u64)>> {
        Ok(Vec::new())
    }

    /// Read-only snapshot of active `kind='present_outcome'` rows' metadata
    /// (key, scope, tags) for the `outcome_valence_shadow` valence-derivation
    /// diagnostic. Reads only the normalized tag facets — never the content
    /// body. Mutates nothing, never touches the retrieval path. Default impl
    /// returns empty so non-SQLite stores stay trait-compatible.
    async fn active_outcome_meta_rows(&self) -> Result<Vec<OutcomeMetaRow>> {
        Ok(Vec::new())
    }

    /// Set one active memory's `importance` column directly (no supersede, no
    /// timestamp churn — mirrors the decay/strengthen UPDATE semantics, which
    /// also touch only `importance`). Returns `true` iff a row was updated.
    /// Used by the gated `outcome_valence_importance_apply` writer; the audit
    /// trail (old values) is the caller's responsibility. Default impl is a
    /// no-op `false` so non-SQLite stores stay trait-compatible.
    async fn memory_set_importance(&self, _key: &str, _importance: f64) -> Result<bool> {
        Ok(false)
    }

    /// Merge `tags` into one active memory's tag list (append-unique; existing
    /// tags and their order preserved; no supersede, no timestamp churn — the
    /// tags-column mirror of [`Self::memory_set_importance`]). Returns `true`
    /// iff the row exists and is active (even when every tag was already
    /// present). Used by `outcome_valence_importance_apply` to stamp applied
    /// rows. Default impl is a no-op `false` so non-SQLite stores stay
    /// trait-compatible.
    async fn memory_add_tags(&self, _key: &str, _tags: &[String]) -> Result<bool> {
        Ok(false)
    }

    /// Replace one active memory's tags under the given prefixes: every
    /// existing tag starting with ANY of `prefixes` is removed, then `tags`
    /// are appended (unique). Single transaction, tags-column-only UPDATE.
    /// Used by `outcome_valence_importance_apply` so a re-derivation (facet
    /// change, rule revision) leaves exactly ONE current valence label/stamp
    /// per row instead of accumulating stale contradictory ones. Returns
    /// `true` iff the row exists and is active. Default impl is a no-op
    /// `false` so non-SQLite stores stay trait-compatible.
    async fn memory_replace_tag_prefixes(
        &self,
        _key: &str,
        _prefixes: &[String],
        _tags: &[String],
    ) -> Result<bool> {
        Ok(false)
    }

    /// Merge `related_keys` into one active memory's lineage list
    /// (append-unique; existing order preserved) without re-running the full
    /// save/supersession pipeline or changing timestamps. Returns `true` iff
    /// the row exists and is active. Default is a no-op `false` for
    /// non-SQLite stores.
    async fn memory_add_related_keys(&self, _key: &str, _related_keys: &[String]) -> Result<bool> {
        Ok(false)
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

    /// Frozen-clock semantic search for deterministic evaluation. Production
    /// callers continue to use [`Self::memory_search_semantic`]; unsupported
    /// backends fail closed instead of silently consulting wall time.
    async fn memory_search_semantic_as_of(
        &self,
        query: &str,
        limit: u32,
        threshold: f32,
        as_of_secs: i64,
    ) -> Result<Vec<MemorySearchHit>> {
        let _ = (query, limit, threshold, as_of_secs);
        Err(ab_core::Error::Backend(
            "memory_search_semantic_as_of unsupported by this store backend".into(),
        ))
    }

    /// Scope-safe semantic search for bootstrap and other contextual recall.
    ///
    /// Returns only rows visible under [`memory_scope_visible_in_context`]:
    /// global/unscoped plus the requested project/domain scope, never another
    /// project/domain. SQLite overrides this method so scope filtering happens
    /// before ranking/truncation. The default is deliberately fail-safe for
    /// third-party/back-compat implementations: it filters their existing
    /// result page and may therefore return fewer than `limit`, but cannot leak
    /// a cross-scope row.
    async fn memory_search_semantic_in_scope(
        &self,
        query: &str,
        ctx: &str,
        limit: u32,
        threshold: f32,
    ) -> Result<Vec<MemorySearchHit>> {
        let hits = self.memory_search_semantic(query, limit, threshold).await?;
        Ok(hits
            .into_iter()
            .filter(|hit| memory_scope_visible_in_context(hit.record.scope.as_deref(), ctx))
            .collect())
    }

    /// Pure-cosine top-K — embed `query` and return the K active memories
    /// whose stored embeddings have the highest cosine similarity to it,
    /// **without** the importance/recency/access blending that
    /// `memory_search_semantic` applies. Used by L6 introspection (e.g.
    /// `introspect_recall` novelty = `1 - max(cosine)`) where the raw
    /// geometric signal is the point. Default impl returns empty (back-
    /// compat — non-SQLite stores quietly produce no novelty signal).
    async fn memory_top_k_cosine(&self, query: &str, k: u32) -> Result<Vec<MemoryCosineHit>> {
        let _ = (query, k);
        Ok(Vec::new())
    }

    /// Scope-safe pure-cosine top-K. Visibility matches
    /// [`Self::memory_search_semantic_in_scope`]; ranking remains pure cosine.
    /// The default filters the backend's existing top-K page (safe but possibly
    /// under-filled), while SQLite ranks the complete visible candidate set.
    async fn memory_top_k_cosine_in_scope(
        &self,
        query: &str,
        ctx: &str,
        k: u32,
    ) -> Result<Vec<MemoryCosineHit>> {
        let hits = self.memory_top_k_cosine(query, k).await?;
        Ok(hits
            .into_iter()
            .filter(|hit| memory_scope_visible_in_context(hit.record.scope.as_deref(), ctx))
            .collect())
    }

    /// Fresh ranking metadata for every `status='active'` memory, keyed by
    /// `key`. A metadata-only scan (no embedding blobs) used by the bridge's
    /// warm semantic path to re-hydrate the frozen embed cache: a key ABSENT
    /// from the returned map is no longer active (superseded / archived /
    /// deleted after the cache was primed) and must be dropped; a present key
    /// carries the current importance/recency/access so the blend matches the
    /// SQL path. Note the overlay is metadata-FOR-RANKING only — `kind` /
    /// content / tags stay frozen with the cached embedding (changing any of
    /// those requires a re-save, which re-embeds and re-primes anyway).
    ///
    /// Default impl returns `Err` (not `Ok(empty)`) on purpose: an empty map
    /// means "every candidate is inactive" to the warm path, so a store that
    /// primed the cache but forgot to implement this would silently return no
    /// results. Erroring instead makes the warm path degrade to its cached
    /// (possibly stale) metadata — the strictly safer failure. Only stores
    /// that actually back the warm cache (SQLite) need to override.
    async fn memory_active_meta(
        &self,
    ) -> Result<std::collections::HashMap<String, MemoryLiveMeta>> {
        Err(ab_core::Error::Backend(
            "memory_active_meta not implemented".into(),
        ))
    }

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
    async fn top_coactivation(&self, _key: &str, _limit: u32) -> Result<Vec<CoactivationEdge>> {
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

    /// **Outcome-collector prototype (flag-gated, default-OFF).** Append one row
    /// per surfaced key to the v39 `retrieval_surfacing` telemetry log, so a
    /// later EXPLICIT `memory_get` of the same key can be attributed as a "used"
    /// retrieval outcome. This is the de-contaminated signal from the Phase-0
    /// study: search surfacings only, never the background re-access that inflates
    /// `access_count`. `surfaced` is `(key, rank)` pairs (rank 0-based). Default
    /// no-op so the feature writes rows only when SqliteStore + the
    /// `AGENT_BRIDGE_OUTCOME_COLLECTOR` flag are both present.
    async fn record_retrieval_surfacing(
        &self,
        surfaced: &[(String, i64)],
        query: &str,
        mode: &str,
    ) -> Result<()> {
        self.record_retrieval_surfacing_classified(
            surfaced,
            query,
            mode,
            RETRIEVAL_TRAFFIC_CLASS_UNKNOWN,
        )
        .await
    }

    /// v42 classified writer. The bridge supplies a process-boundary class;
    /// direct/legacy callers that use `record_retrieval_surfacing` above are
    /// deliberately persisted as `unknown`.
    async fn record_retrieval_surfacing_classified(
        &self,
        _surfaced: &[(String, i64)],
        _query: &str,
        _mode: &str,
        _traffic_class: &str,
    ) -> Result<()> {
        Ok(())
    }

    /// **Outcome-collector prototype (flag-gated, default-OFF).** Mark recent
    /// un-attributed surfacings of `key` (surfaced within `window_secs`) as
    /// "used" by stamping `used_at`, and return how many rows were newly
    /// attributed. Default no-op returning 0.
    async fn attribute_retrieval_get(&self, _key: &str, _window_secs: i64) -> Result<u64> {
        Ok(0)
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

    /// Retrieval-feedback readout — aggregate the `retrieval_surfacing`
    /// telemetry (surfaced→used) over the last `window_secs`, returning up to
    /// `top_n` reinforce candidates (used) and decay candidates (surfaced-never-
    /// used). Read-only; default returns an empty [`RetrievalOutcomeSummary`] so
    /// non-SQLite backends and unit tests degrade to "no data" (safe for a
    /// diagnostic — unlike a ranking filter, an empty readout misleads nobody).
    async fn retrieval_outcome_summary(
        &self,
        window_secs: i64,
        top_n: usize,
    ) -> Result<RetrievalOutcomeSummary> {
        let _ = (window_secs, top_n);
        Ok(RetrievalOutcomeSummary::default())
    }

    /// What-if raw material for the `retrieval_outcome_shadow` harness:
    /// per-memory surfacing aggregates over the last `window_secs` JOINed with
    /// each memory's CURRENT active importance. Strictly read-only — the
    /// parameterized reinforce/decay rule is simulated by the caller; nothing
    /// here (or there) writes. Bounded by the `retrieval_surfacing` ring cap.
    /// Default returns empty for the same reason as
    /// [`StateStore::retrieval_outcome_summary`]: an empty what-if is an honest
    /// "no data yet", never a wrong answer.
    async fn retrieval_outcome_shadow_rows(
        &self,
        window_secs: i64,
    ) -> Result<Vec<RetrievalOutcomeShadowRow>> {
        let _ = window_secs;
        Ok(Vec::new())
    }

    /// **R2 fusion shadow (flag-gated, default-OFF).** Append one passive
    /// [`FusionShadowSample`] measurement row. Writes happen only when the
    /// bridge's `AGENT_BRIDGE_FUSION_SHADOW` gate is on; default no-op so
    /// non-SQLite backends degrade silently (telemetry-only, like
    /// [`StateStore::record_retrieval_surfacing`]).
    async fn record_fusion_shadow(&self, _sample: &FusionShadowSample) -> Result<()> {
        Ok(())
    }

    /// R2 fusion-shadow readback — rows from the last `window_secs`, newest
    /// first, bounded by [`FUSION_SHADOW_RING_CAP`]. Default returns empty
    /// (an honest "no data yet" for a read-only report, never a wrong answer).
    async fn fusion_shadow_rows(&self, _window_secs: i64) -> Result<Vec<FusionShadowSample>> {
        Ok(Vec::new())
    }

    /// Raw material for the behavior-changing `retrieval_outcome_apply` pass —
    /// the same per-memory aggregate shape as
    /// [`StateStore::retrieval_outcome_shadow_rows`], but over the UNCONSUMED,
    /// MATURE slice of the telemetry: rows not yet counted toward a prior
    /// action (`consumed_at IS NULL`) and old enough that the used_at
    /// attribution windows have closed (`surfaced_at <= cutoff`). The caller
    /// computes `cutoff` ONCE per pass and hands the same value to
    /// [`StateStore::consume_retrieval_surfacings`] so the consumed set is
    /// exactly the aggregated set. Default is an ERROR, not an empty vec — a
    /// backend that silently reports "nothing pending" to an apply pass would
    /// disguise a dead learning loop as a quiet one (the memory_active_meta
    /// lesson, 2026-07-02).
    async fn retrieval_outcome_apply_rows(
        &self,
        cutoff: i64,
    ) -> Result<Vec<RetrievalOutcomeShadowRow>> {
        let _ = cutoff;
        Err(ab_core::Error::Backend(
            "retrieval_outcome_apply_rows unsupported by this store backend".into(),
        ))
    }

    /// Mark every still-unconsumed surfacing of `key` with `surfaced_at <=
    /// cutoff` as consumed (counted toward exactly one reinforce/decay
    /// action). Same predicate as [`StateStore::retrieval_outcome_apply_rows`]
    /// by construction, so a pass consumes exactly what it aggregated even if
    /// new surfacings of the same key land mid-pass. Returns rows marked.
    /// Default is an ERROR for the same reason as `retrieval_outcome_apply_rows`.
    async fn consume_retrieval_surfacings(&self, key: &str, cutoff: i64) -> Result<u64> {
        let _ = (key, cutoff);
        Err(ab_core::Error::Backend(
            "consume_retrieval_surfacings unsupported by this store backend".into(),
        ))
    }

    /// ONE transaction: consume `key`'s pending mature surfacings and, iff
    /// any were consumed, write `importance`. Returns (rows_consumed,
    /// importance_written). Consume-first makes concurrent apply passes safe:
    /// the race loser consumes 0 rows and must not write. Default is an ERROR
    /// for the same reason as `retrieval_outcome_apply_rows`.
    async fn consume_and_apply_importance(
        &self,
        key: &str,
        importance: f64,
        cutoff: i64,
    ) -> Result<(u64, bool)> {
        let _ = (key, importance, cutoff);
        Err(ab_core::Error::Backend(
            "consume_and_apply_importance unsupported by this store backend".into(),
        ))
    }

    /// Consume pending mature surfacings whose memory is no longer active —
    /// the apply aggregate INNER JOINs on status='active', so these rows
    /// would otherwise sit pending forever. Returns rows marked. Default is
    /// an ERROR for the same reason as `retrieval_outcome_apply_rows`.
    async fn consume_orphaned_surfacings(&self, cutoff: i64) -> Result<u64> {
        let _ = cutoff;
        Err(ab_core::Error::Backend(
            "consume_orphaned_surfacings unsupported by this store backend".into(),
        ))
    }

    /// Retire pending mature AMBIENT surfacings (mode =
    /// [`AMBIENT_SURFACING_MODE`]). The apply aggregate excludes that mode, so
    /// no per-key consume path ever reaches these rows; without this sweep
    /// they would sit pending forever — and because the ring prune eats
    /// consumed rows first, ambient history would paradoxically outlive real
    /// search evidence under cap pressure. Same `cutoff` discipline as the
    /// other consume paths: rows younger than the maturation window keep
    /// their used_at stamp eligibility. Returns rows marked. Default is an
    /// ERROR for the same reason as `retrieval_outcome_apply_rows`.
    async fn consume_ambient_surfacings(&self, cutoff: i64) -> Result<u64> {
        let _ = cutoff;
        Err(ab_core::Error::Backend(
            "consume_ambient_surfacings unsupported by this store backend".into(),
        ))
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
    async fn identity_window(&self, window_start: i64, window_end: i64) -> Result<IdentityWindow> {
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

    /// XM v0.1 — mark message `id` as read. Idempotent: if already read,
    /// `read_at` is preserved (not overwritten). Returns `Ok(true)` if the
    /// row was found AND addressed to `to_session`; `Ok(false)` otherwise.
    /// The `to_session` guard prevents cross-session reads from accidentally
    /// touching another recipient's inbox state.
    async fn agent_message_mark_read(&self, id: i64, to_session: &str) -> Result<bool>;

    /// XM v0.1 P-XM-7 GC pass. Deletes rows whose effective last-touch
    /// timestamp (`COALESCE(read_at, created_at)`) is older than
    /// `now_secs - max_age_secs`. Returns `(cleared, retained)` counts.
    ///
    /// When `dry_run` is true, no rows are deleted: `cleared` is the count
    /// that *would* be removed and `retained` the count that *would* remain.
    /// The match predicate is shared between the count and delete paths so a
    /// dry-run preview can never diverge from the real GC (the exact drift
    /// class P-XM-7 guards against).
    ///
    /// Guarantees (locked per design §4 / §6.5 rule 2):
    /// - any message with `last_touch < cutoff` → DELETED (100%)
    /// - any message with `last_touch >= cutoff` → KEPT (0% false-delete)
    async fn agent_messages_gc(
        &self,
        now_secs: i64,
        max_age_secs: i64,
        dry_run: bool,
    ) -> Result<(usize, usize)>;

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
        let _ = (thread_id, board, title, author, kind, body, refs, tags);
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

    /// Fetch a single forum post by id (C3 S6 post-write race-detection helper).
    /// Returns `Ok(None)` if no row matches — caller decides whether to retry
    /// (read-replica lag) or escalate to an OOB alert. Default impl returns
    /// `Ok(None)` so non-SQLite backends never trip S6 alerts incorrectly.
    async fn forum_post_get(&self, post_id: i64) -> Result<Option<ForumPostRecord>> {
        let _ = post_id;
        Ok(None)
    }

    /// Fetch one forum thread without touching subscription cursors.
    async fn forum_thread_get(&self, thread_id: i64) -> Result<Option<ForumThreadRecord>> {
        let _ = thread_id;
        Ok(None)
    }

    /// Search forum thread titles and post bodies without touching
    /// subscription cursors. `allowed_tags` is a mandatory visibility
    /// boundary: only threads carrying at least one exact tag are eligible.
    /// Results are grouped by thread and ordered by title match then recency.
    async fn forum_search(
        &self,
        query: &str,
        allowed_tags: &[String],
        limit: u32,
    ) -> Result<Vec<ForumSearchRecord>> {
        let _ = (query, allowed_tags, limit);
        Err(ab_core::Error::Backend(
            "forum_search not implemented".into(),
        ))
    }

    /// List threads across boards (or one `board` when set), status-filtered,
    /// ordered by `last_post_at DESC`. Powers `forum_digest` — unlike
    /// `forum_list_threads` it has no per-session unread bookkeeping (the
    /// digest is a stateless snapshot). Default impl returns an error.
    async fn forum_digest_threads(
        &self,
        status: Option<&str>,
        board: Option<&str>,
        limit: u32,
    ) -> Result<Vec<ForumThreadRecord>> {
        let _ = (status, board, limit);
        Err(ab_core::Error::Backend(
            "forum_digest_threads not implemented".into(),
        ))
    }

    /// The most RECENT `limit` posts in a thread (id DESC, capped). Unlike
    /// `forum_read` (which returns the OLDEST window from a cursor), this powers
    /// `forum_digest`'s per-thread extraction so high-volume threads reflect
    /// current state, not their opening posts. Returned newest-first; callers
    /// that need chronological order should sort by id. Default impl errors.
    async fn forum_recent_posts(&self, thread_id: i64, limit: u32) -> Result<Vec<ForumPostRecord>> {
        let _ = (thread_id, limit);
        Err(ab_core::Error::Backend(
            "forum_recent_posts not implemented".into(),
        ))
    }

    /// Update thread status (`open` | `resolved` | `archived`).
    /// Export every forum thread (with its posts) to a JSONL file. One thread
    /// per line; posts are nested inside their thread. Subscriptions are not
    /// included (each device has its own read cursors). Used by
    /// `agent-bridge sync` for cross-device collaboration.
    async fn forum_export(&self, out_path: &std::path::Path) -> Result<ForumExportResult> {
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
    async fn forum_import(&self, in_path: &std::path::Path) -> Result<ForumImportReport> {
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
    async fn agent_presence_get(&self, session_id: &str) -> Result<Option<AgentPresenceRecord>> {
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

    /// Full active-embedding distribution as `(backend, dim, rows)` buckets,
    /// largest first. Default empty; SQLite overrides with a real query. The
    /// startup dim-guard uses this to see BOTH the dominant space and the
    /// minority of wrong-dim rows (mislabeled/stale, e.g. peer-synced rows
    /// tagged `gte` but holding 384d vectors) that the dominant bucket hides.
    async fn embedding_profile_buckets(&self) -> Result<Vec<EmbeddingProfile>> {
        Ok(Vec::new())
    }

    /// Dominant `(backend, dim)` among active stored embeddings — the largest
    /// bucket from [`Self::embedding_profile_buckets`], i.e. the space the store
    /// was actually written in. Feeds the startup embedding dim-guard so a
    /// process embedding at a different dimension than the store is flagged
    /// instead of silently returning all-zero (dim-mismatched) semantic cosines.
    /// Empty profile for an empty store.
    async fn dominant_embedding_profile(&self) -> Result<EmbeddingProfile> {
        Ok(self
            .embedding_profile_buckets()
            .await?
            .into_iter()
            .next()
            .unwrap_or_default())
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
        let _ = (callee_substr, caller_substr, file_filter, root_path, limit);
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

    /// Multi-hop transitive caller closure — answers "what's the
    /// blast-radius if I change symbol X?". BFS over the alias-resolved
    /// callers graph up to `max_depth` hops. Composes
    /// [`StateStore::codebase_callers`] iteratively; any backend that
    /// implements `codebase_callers` gets this for free via the default
    /// impl below.
    ///
    /// Arguments:
    ///   • `target` — same format as `codebase_callers`, e.g.
    ///     `crate::store::SqliteStore::new`.
    ///   • `max_depth` — BFS depth cap (1 = direct callers only).
    ///     Default-safe at 3 for human-readable closures. Higher values
    ///     blow up quickly on hub functions.
    ///   • `per_hop_limit` — passed to each nested `codebase_callers`
    ///     call. Caps fan-out per frontier node.
    ///   • `root_path` / `file_filter` — passed through to each lookup.
    ///
    /// Returns nodes sorted by `(hop_distance ASC, qualified_name ASC)`.
    /// The original `target` itself is **not** included in the output
    /// (only its transitive callers).
    ///
    /// Default impl works on any backend that supports `codebase_callers`.
    /// Backends that want to optimize (e.g. closed-form recursive CTE)
    /// can override.
    async fn codebase_impact(
        &self,
        target: &str,
        max_depth: u32,
        per_hop_limit: u32,
        file_filter: Option<&str>,
        root_path: Option<&str>,
    ) -> Result<Vec<ImpactNode>> {
        let max_depth = max_depth.max(1);
        let per_hop_limit = per_hop_limit.clamp(1, 500);

        let mut closure: Vec<ImpactNode> = Vec::new();
        let mut visited: std::collections::HashSet<String> = std::collections::HashSet::new();
        // Frontier of (callee_to_lookup, hop_to_record) — hop=1 for
        // direct callers of `target`, hop=N+1 after one BFS expansion.
        let mut frontier: Vec<(String, u32)> = vec![(target.to_string(), 1)];

        while !frontier.is_empty() {
            let mut next_frontier: Vec<(String, u32)> = Vec::new();
            for (callee, hop) in std::mem::take(&mut frontier) {
                if hop > max_depth {
                    continue;
                }
                let hits = self
                    .codebase_callers(&callee, file_filter, root_path, per_hop_limit)
                    .await?;
                for hit in hits {
                    // visited-set keys on caller text (not file:line) so
                    // multiple call sites from the same caller dedupe.
                    if hit.caller.is_empty() {
                        // File-scope call without an enclosing fn — skip;
                        // can't continue BFS without a function key, and
                        // it would pollute the closure with non-callable
                        // synthetic nodes.
                        continue;
                    }
                    if visited.insert(hit.caller.clone()) {
                        closure.push(ImpactNode {
                            qualified_name: hit.caller.clone(),
                            file_path: hit.file_path.clone(),
                            hop_distance: hop,
                            via_callee: callee.clone(),
                        });
                        if hop < max_depth {
                            next_frontier.push((hit.caller, hop + 1));
                        }
                    }
                }
            }
            frontier = next_frontier;
        }

        // Stable sort by (hop ASC, qualified_name ASC).
        closure.sort_by(|a, b| {
            a.hop_distance
                .cmp(&b.hop_distance)
                .then_with(|| a.qualified_name.cmp(&b.qualified_name))
        });
        Ok(closure)
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
    async fn codebase_call_stats(&self, root_path: &str, top_n: u32) -> Result<CodebaseCallStats> {
        let _ = (root_path, top_n);
        Err(ab_core::Error::Backend(
            "codebase_call_stats not implemented".into(),
        ))
    }

    /// P-ε — Substrate-Readiness Audit. Composes M1-M8 metric families
    /// from existing trait methods + raw SQL on coactivation /
    /// embedding_backend / edge_coverage. Pure read; no writes.
    ///
    /// `window_secs` controls lookback for M3 / M8 / RetireDelta.
    /// Default-safe to pass `7 * 86400` (7 days).
    ///
    /// Default impl errors so non-sqlite backends opt in explicitly.
    async fn memory_substrate_audit(&self, window_secs: u64) -> Result<SubstrateAuditReport> {
        let _ = window_secs;
        Err(ab_core::Error::Backend(
            "memory_substrate_audit not implemented".into(),
        ))
    }

    /// P-α — Always-Warm Coactivation Tick: one sweep over
    /// `memory_coactivation` applying integer half-life decay. For every
    /// row where `last_at + tau_secs ≤ now`, halves `count` and advances
    /// `last_at` by `tau_secs`. Iterates within a single call up to
    /// `max_iterations` so multiple half-lives can be caught up on
    /// stale tables. Rows with `count < 1` after decay are DELETEd.
    ///
    /// Caller injects `now` for deterministic testing. Default
    /// `max_iterations` should be 10 (bounds the per-tick wall time).
    ///
    /// See `docs/DESIGN-P-alpha-always-warm-coactivation-tick.md`.
    async fn decay_coactivation_once(
        &self,
        tau_secs: i64,
        now: i64,
        max_iterations: u32,
    ) -> Result<DecayCoactivationStats> {
        let _ = (tau_secs, now, max_iterations);
        Err(ab_core::Error::Backend(
            "decay_coactivation_once not implemented".into(),
        ))
    }

    /// C3 §3.4 S5 — current value of `schema_meta.version` (or
    /// equivalent migration cursor). Returns `Ok(None)` when no version
    /// row is present. Default impl returns `Ok(None)` so non-SQLite
    /// backends silently no-op the daemon's S5 schema-change watch.
    async fn schema_meta_version(&self) -> Result<Option<String>> {
        Ok(None)
    }

    /// C3 §3.4 S2-S4 — read the three drop-detection counts in one
    /// call. Default returns zeroed [`S234Counts`] so non-SQLite
    /// backends silently no-op the daemon's S2-S4 forum-channel alerts.
    async fn s234_counts(&self) -> Result<S234Counts> {
        Ok(S234Counts::default())
    }
}

#[cfg(test)]
mod reference_search_projection_tests {
    use super::*;

    fn hit(key: &str, content: &str) -> MemorySearchHit {
        MemorySearchHit {
            record: MemoryRecord {
                key: key.to_string(),
                kind: "decision".to_string(),
                content: content.to_string(),
                tags: vec!["s0".to_string()],
                related_keys: vec![
                    "z-edge".to_string(),
                    "a-edge".to_string(),
                    "a-edge".to_string(),
                ],
                scope: Some("project:/frozen".to_string()),
                created_at: 10,
                updated_at: 11,
                last_accessed_at: 999,
                access_count: 77,
                importance: 0.8,
                status: "active".to_string(),
                trigger_pattern: None,
                superseded_by: None,
            },
            score: 1.0,
            cosine: None,
        }
    }

    #[test]
    fn reference_projection_excludes_access_telemetry_and_is_bounded() {
        let context = project_memory_search_reference_hits(
            &[hit("a", "alpha beta"), hit("b", "gamma delta")],
            1_024,
        )
        .expect("bounded projection");
        assert_eq!(context.hits.len(), 2);
        assert_eq!(context.context_bytes, context.context_json.len());
        assert_eq!(
            context.context_json,
            serde_json::to_string(&context.hits).expect("serialize projection")
        );
        let serialized = context.context_json;
        assert!(!serialized.contains("last_accessed_at"));
        assert!(!serialized.contains("access_count"));
        assert!(!serialized.contains("importance"));
        assert!(!serialized.contains("score"));
        assert_eq!(context.hits[0].related_keys, vec!["a-edge", "z-edge"]);
    }

    #[test]
    fn reference_projection_fails_closed_instead_of_truncating() {
        let result = project_memory_search_reference_hits(
            &[hit("a", "one two"), hit("b", &"x ".repeat(100))],
            128,
        );
        assert!(result.is_err());
    }

    #[test]
    fn reference_options_bind_defaults_to_explicit_as_of() {
        let options = MemorySearchReferenceOptions::at(1234);
        assert_eq!(options.as_of_secs, 1234);
        assert_eq!(options.graph_fanout, MEMORY_REFERENCE_GRAPH_FANOUT);
        assert_eq!(
            options.max_context_bytes,
            MEMORY_REFERENCE_MAX_CONTEXT_BYTES
        );
        assert_eq!(options.exclude_kinds, vec!["skill"]);
        assert!(options.coactivation_rerank);
    }

    #[test]
    fn reference_ttl_uses_the_frozen_expiry_boundary() {
        let mut record = hit("ttl", "bounded").record;
        record.created_at = 10;
        record.updated_at = 20;
        record.tags = vec!["ttl:1d".to_string()];
        let expires_at = 20 + MEMORY_TTL_SECONDS_PER_DAY;

        assert_eq!(memory_record_ttl_expires_at(&record), Some(expires_at));
        assert!(memory_record_ttl_is_live_at(&record, expires_at - 1));
        assert!(!memory_record_ttl_is_live_at(&record, expires_at));

        record.tags = vec!["ttl:not-days".to_string()];
        assert!(memory_record_ttl_is_live_at(&record, i64::MAX));
    }
}

#[cfg(test)]
mod biocortex_opt_in_contract_tests {
    use super::*;

    #[test]
    fn biocortex_contract_defaults_to_baseline_fallback() {
        let decision = BioCortexRetrievalOptInRequest::default().evaluate();

        assert_eq!(
            decision.schema,
            BIOCORTEX_RETRIEVAL_OPT_IN_STORE_CONTRACT_SCHEMA
        );
        assert_eq!(
            decision.authorization_scope,
            BIOCORTEX_RETRIEVAL_OPT_IN_AUTHORIZATION_SCOPE
        );
        assert_eq!(decision.mode, "fts");
        assert!(decision.mode_authorized);
        assert!(!decision.eligible_for_side_signal);
        assert!(!decision.may_change_search_order);
        assert!(!decision.default_search_order_change_allowed);
        assert!(decision.default_calls_unchanged);
        assert!(decision.must_return_baseline);
        assert_eq!(
            decision.fallback_reason,
            Some(BioCortexRetrievalOptInBlocker::CompileFeatureDisabled)
        );
        assert_eq!(decision.audit_requirements.raw_query_included, false);
        assert_eq!(decision.audit_requirements.raw_keys_included, false);
        assert_eq!(decision.audit_requirements.content_included, false);

        let response = decision.response_contract(false);
        assert_eq!(
            response.returned_order_source,
            BioCortexReturnedOrderSource::Baseline
        );
        assert!(response.baseline_returned);
        assert!(!response.changes_memory_search_order);
    }

    #[test]
    fn biocortex_contract_rejects_non_fts_before_runtime_gate() {
        let decision = BioCortexRetrievalOptInRequest {
            mode: "hybrid".to_string(),
            per_call_opt_in: true,
            compile_feature_enabled: true,
            runtime_enabled: true,
            baseline_key_count: 2,
            ..Default::default()
        }
        .evaluate();

        assert_eq!(decision.mode, "hybrid");
        assert!(!decision.mode_authorized);
        assert_eq!(
            decision.fallback_reason,
            Some(BioCortexRetrievalOptInBlocker::ModeNotAuthorized)
        );
        assert!(decision
            .blocking_reasons
            .contains(&BioCortexRetrievalOptInBlocker::ModeNotAuthorized));
        assert!(!decision.may_change_search_order);
        assert!(decision.must_return_baseline);
    }

    #[test]
    fn biocortex_contract_ready_gate_still_blocks_without_ordering_path() {
        let decision = BioCortexRetrievalOptInRequest {
            mode: "fts".to_string(),
            per_call_opt_in: true,
            compile_feature_enabled: true,
            runtime_enabled: true,
            baseline_key_count: 2,
            runtime_adapter_approved: false,
            ordering_behavior_connected: false,
            ..Default::default()
        }
        .evaluate();

        assert_eq!(
            decision.fallback_reason,
            Some(BioCortexRetrievalOptInBlocker::OrderingBehaviorNotConnected)
        );
        assert!(decision
            .blocking_reasons
            .contains(&BioCortexRetrievalOptInBlocker::RuntimeAdapterNotApproved));
        assert!(!decision.eligible_for_side_signal);
        assert!(!decision.may_change_search_order);
        assert!(decision.must_return_baseline);

        let response = decision.response_contract(false);
        assert_eq!(
            response.returned_order_source,
            BioCortexReturnedOrderSource::Baseline
        );
        assert!(response.baseline_returned);
        assert!(!response.changes_memory_search_order);
    }

    #[test]
    fn biocortex_contract_allows_experimental_order_only_after_all_gates() {
        let decision = BioCortexRetrievalOptInRequest {
            mode: "fts".to_string(),
            per_call_opt_in: true,
            compile_feature_enabled: true,
            runtime_enabled: true,
            baseline_completed: true,
            baseline_key_count: 3,
            runtime_adapter_approved: true,
            ordering_behavior_connected: true,
            operator_disabled: false,
        }
        .evaluate();

        assert!(decision.eligible_for_side_signal);
        assert!(decision.may_change_search_order);
        assert!(!decision.must_return_baseline);
        assert_eq!(decision.fallback_reason, None);

        let missing_signal = decision.response_contract(false);
        assert_eq!(
            missing_signal.returned_order_source,
            BioCortexReturnedOrderSource::Baseline
        );
        assert_eq!(
            missing_signal.fallback_reason,
            Some(BioCortexRetrievalOptInBlocker::SideSignalUnavailable)
        );

        let experimental = decision.response_contract(true);
        assert_eq!(
            experimental.returned_order_source,
            BioCortexReturnedOrderSource::Experimental
        );
        assert!(!experimental.baseline_returned);
        assert!(experimental.changes_memory_search_order);
        assert_eq!(experimental.fallback_reason, None);
    }

    #[test]
    fn biocortex_contract_serializes_audit_requirements_without_raw_data() {
        let decision = BioCortexRetrievalOptInRequest {
            mode: "fts".to_string(),
            per_call_opt_in: true,
            compile_feature_enabled: true,
            runtime_enabled: true,
            baseline_key_count: 2,
            ..Default::default()
        }
        .evaluate();

        let serialized = serde_json::to_string(&decision).expect("serialize decision");
        assert!(serialized.contains(BIOCORTEX_RETRIEVAL_OPT_IN_STORE_CONTRACT_SCHEMA));
        assert!(serialized.contains("\"baseline_key_count\":2"));
        assert!(serialized.contains("\"raw_keys_included\":false"));
        assert!(serialized.contains("\"content_included\":false"));
        assert!(!serialized.contains("secret_key"));
        assert!(!serialized.contains("secret query"));
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
