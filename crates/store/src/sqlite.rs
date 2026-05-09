//! SQLite-backed [`StateStore`] using `tokio-rusqlite` (bundled SQLite).

use ab_core::{Error, NotifyEvent, NotifySeverity, NotifySource, Result, SessionId};
use async_trait::async_trait;
use std::path::{Path, PathBuf};
use tokio_rusqlite::{params, rusqlite, Connection};

// Local alias matches the `E` parameter that `tokio_rusqlite::Connection::call`
// expects from the user closure.
type RusqliteResult<T> = std::result::Result<T, tokio_rusqlite::rusqlite::Error>;
use tracing::info;

// ── Edge type canonical weights (P1: typed-edges) ──────────────────────────
// Inspired by AiOT GraphMemoryBridge edge semantics + temporal bonus idea.
//
// Causal edges (updates, caused_by, supersedes) get a temporal bonus ×1.2
// in energy propagation (applied in memory_neighbors BFS traversal).
// Recall edges (invalidates, contradicts) get a penalty ×0.85.
//
// Base weights — used when caller passes edge_type but no explicit weight:
const EDGE_WEIGHT_UPDATES: f64 = 1.5; // newest info replaces old
const EDGE_WEIGHT_CAUSED_BY: f64 = 1.3; // causal chain
const EDGE_WEIGHT_SUPERSEDES: f64 = 1.3; // explicit supersession
const EDGE_WEIGHT_IMPLEMENTS: f64 = 1.1; // concrete realisation of design
const EDGE_WEIGHT_RELATED: f64 = 1.0; // generic relation
const EDGE_WEIGHT_PART_OF: f64 = 0.8; // structural containment
const EDGE_WEIGHT_DERIVED_FROM: f64 = 0.8; // loose derivation
const EDGE_WEIGHT_CONTRADICTS: f64 = 0.5; // known conflict
const EDGE_WEIGHT_INVALIDATES: f64 = 0.5; // explicit invalidation

/// Return the canonical base weight for a known edge type.
/// Unknown types default to 1.0 (generic relation).
pub fn weight_for_edge_type(edge_type: &str) -> f64 {
    match edge_type {
        "updates" => EDGE_WEIGHT_UPDATES,
        "caused_by" => EDGE_WEIGHT_CAUSED_BY,
        "supersedes" => EDGE_WEIGHT_SUPERSEDES,
        "implements" => EDGE_WEIGHT_IMPLEMENTS,
        "relates" | "related" => EDGE_WEIGHT_RELATED,
        "part_of" => EDGE_WEIGHT_PART_OF,
        "derived_from" => EDGE_WEIGHT_DERIVED_FROM,
        "contradicts" => EDGE_WEIGHT_CONTRADICTS,
        "invalidates" => EDGE_WEIGHT_INVALIDATES,
        _ => 1.0,
    }
}

/// AiOT temporal bonus multiplier for an edge type:
/// causal edges get ×1.2, recall-penalty edges get ×0.85, others ×1.0.
pub fn temporal_bonus(edge_type: &str) -> f64 {
    match edge_type {
        "updates" | "caused_by" | "supersedes" | "implements" => 1.2,
        "contradicts" | "invalidates" => 0.85,
        _ => 1.0,
    }
}

use crate::{
    AgentMessageRecord, AgentPresenceRecord, AgentPresenceUpsert, CoactivationEdge,
    CoactivationStats, CodebaseIndexStats, CodebaseSymbol, CompactPolicy, ForumExportResult, ForumImportReport,
    ForumPostExport, ForumPostOutcome, ForumPostRecord, ForumThreadExport, ForumThreadRecord,
    IdentityWindow, ImportConflictPolicy, ImportReport, McpToolCallStats, McpToolErrorRecord,
    MemoryEdge, MemoryEdgeExport, MemoryExportFilter, MemoryExportResult, MemoryListSort,
    MemoryQueryRecord, MemoryQueryStats, MemoryRecord, MemorySearchHit, MemoryStats,
    NotificationRecord, PlanRecord, PlanStep, SessionFilter, StateStore, StoredSession,
    MCP_TOOL_ERROR_RING_CAP, MEMORY_CONTENT_CAP, MEMORY_QUERY_LOG_RING_CAP,
    STDIO_CAP,
};
use tokio_rusqlite::rusqlite::OptionalExtension;

const SCHEMA_V1: &str = r#"
CREATE TABLE IF NOT EXISTS schema_meta (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS sessions (
    id          TEXT    PRIMARY KEY,
    runtime_id  TEXT    NOT NULL,
    cwd         TEXT    NOT NULL,
    started_at  INTEGER NOT NULL,
    ended_at    INTEGER
);
CREATE INDEX IF NOT EXISTS idx_sessions_started_at ON sessions(started_at DESC);

CREATE TABLE IF NOT EXISTS notifications (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    ts          INTEGER NOT NULL,
    source      TEXT    NOT NULL,
    severity    TEXT    NOT NULL,
    title       TEXT    NOT NULL,
    body        TEXT    NOT NULL,
    session_id  TEXT,
    context     TEXT    NOT NULL DEFAULT '{}'
);
CREATE INDEX IF NOT EXISTS idx_notifications_ts ON notifications(ts DESC);

CREATE TABLE IF NOT EXISTS tool_invocations (
    id           TEXT    PRIMARY KEY,
    ts           INTEGER NOT NULL,
    tool_name    TEXT    NOT NULL,
    args         TEXT    NOT NULL,
    result       TEXT,
    error        TEXT,
    duration_ms  INTEGER,
    session_id   TEXT
);
CREATE INDEX IF NOT EXISTS idx_tool_invocations_ts ON tool_invocations(ts DESC);
"#;

const SCHEMA_V3: &str = r#"
CREATE TABLE IF NOT EXISTS memories (
    key              TEXT    PRIMARY KEY,
    kind             TEXT    NOT NULL,
    content          TEXT    NOT NULL,
    tags             TEXT    NOT NULL DEFAULT '[]',
    related_keys     TEXT    NOT NULL DEFAULT '[]',
    created_at       INTEGER NOT NULL,
    updated_at       INTEGER NOT NULL,
    last_accessed_at INTEGER NOT NULL,
    access_count     INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_memories_kind          ON memories(kind);
CREATE INDEX IF NOT EXISTS idx_memories_last_accessed ON memories(last_accessed_at DESC);
CREATE INDEX IF NOT EXISTS idx_memories_updated_at    ON memories(updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_memories_access_count  ON memories(access_count DESC);
"#;

// ── FTS5 virtual table for memory.content + key, with auto-sync triggers ──
//
// FTS5 ships in rusqlite/bundled by default. We use the unicode61 tokenizer
// (case-insensitive, accent-folding) and remove_diacritics=2 for best CJK
// fallback (mostly tokenizes by char). Trigram tokenizer would be better
// for substring search but unicode61 covers 99% of agent-memory needs.
//
// Sync triggers: this is a **content-stored** FTS5 table (no `content=` arg
// in the CREATE), so deletes use the standard `DELETE FROM fts WHERE rowid`
// pattern, NOT the contentless `INSERT … VALUES ('delete', …)` command.
// (v0.5.0 shipped with the wrong pattern — see v0.5.1 fix below.)
const SCHEMA_V4: &str = r#"
CREATE VIRTUAL TABLE IF NOT EXISTS memories_fts USING fts5(
    key UNINDEXED,
    content,
    tokenize = "unicode61 remove_diacritics 2"
);

CREATE TRIGGER IF NOT EXISTS memories_ai AFTER INSERT ON memories BEGIN
    INSERT INTO memories_fts(rowid, key, content)
    VALUES (new.rowid, new.key, new.content);
END;
CREATE TRIGGER IF NOT EXISTS memories_ad AFTER DELETE ON memories BEGIN
    DELETE FROM memories_fts WHERE rowid = old.rowid;
END;
CREATE TRIGGER IF NOT EXISTS memories_au AFTER UPDATE ON memories BEGIN
    DELETE FROM memories_fts WHERE rowid = old.rowid;
    INSERT INTO memories_fts(rowid, key, content)
    VALUES (new.rowid, new.key, new.content);
END;
"#;

// v0.7: scope column on memories + memory_edges graph table
const SCHEMA_V6: &str = r#"
ALTER TABLE memories ADD COLUMN scope TEXT;

CREATE TABLE IF NOT EXISTS memory_edges (
    from_key  TEXT    NOT NULL,
    to_key    TEXT    NOT NULL,
    edge_type TEXT    NOT NULL DEFAULT 'relates',
    weight    REAL    NOT NULL DEFAULT 1.0,
    created_at INTEGER NOT NULL,
    PRIMARY KEY (from_key, to_key, edge_type)
);
CREATE INDEX IF NOT EXISTS idx_memory_edges_from ON memory_edges(from_key);
CREATE INDEX IF NOT EXISTS idx_memory_edges_to   ON memory_edges(to_key);
"#;

// v8: cloud-run lifecycle columns on sessions (warp-oz)
const SCHEMA_V8: &str = r#"
ALTER TABLE sessions ADD COLUMN cloud_run_id TEXT;
ALTER TABLE sessions ADD COLUMN cloud_run_state TEXT;
ALTER TABLE sessions ADD COLUMN cloud_session_link TEXT;
"#;

// W5: structured task plans (DESIGN-warp-first-agent-shell)
const SCHEMA_V9: &str = r#"
CREATE TABLE IF NOT EXISTS plans (
    plan_id     TEXT PRIMARY KEY,
    title       TEXT NOT NULL,
    steps_json  TEXT NOT NULL,
    created_at  INTEGER NOT NULL,
    updated_at  INTEGER NOT NULL
);
"#;

// W6: lightweight inbox between sessions / agents
const SCHEMA_V10: &str = r#"
CREATE TABLE IF NOT EXISTS agent_messages (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    from_session   TEXT    NOT NULL,
    to_session     TEXT    NOT NULL,
    payload_json   TEXT    NOT NULL,
    created_at     INTEGER NOT NULL,
    read           INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_agent_messages_to ON agent_messages(to_session, created_at DESC);
"#;

// W7: optional substring for kind=error_pattern (session_bootstrap `error_hint` matching)
const SCHEMA_V11: &str = r#"
ALTER TABLE memories ADD COLUMN trigger_pattern TEXT;
"#;

// Phase C: ring buffer of recent MCP `tools/call` failures (observability).
const SCHEMA_V13: &str = r#"
CREATE TABLE IF NOT EXISTS mcp_tool_errors (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts INTEGER NOT NULL,
    tool_name TEXT NOT NULL,
    message TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_mcp_tool_errors_ts ON mcp_tool_errors(ts DESC, id DESC);
"#;

// v17: full call telemetry (every tools/call success+failure logged for the
// observation period that drives the ab-shell decision — see memory
// plan_warp_observation_metrics_20260503).
const SCHEMA_V17: &str = r#"
CREATE TABLE IF NOT EXISTS mcp_tool_calls (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    ts          INTEGER NOT NULL,
    tool_name   TEXT    NOT NULL,
    duration_ms INTEGER NOT NULL,
    ok          INTEGER NOT NULL,
    args_size   INTEGER,
    result_size INTEGER
);
CREATE INDEX IF NOT EXISTS idx_mcp_tool_calls_ts   ON mcp_tool_calls(ts DESC, id DESC);
CREATE INDEX IF NOT EXISTS idx_mcp_tool_calls_tool ON mcp_tool_calls(tool_name, ts DESC);
"#;

// v1.0: importance score + status column for cognitive memory
const SCHEMA_V7: &str = r#"
ALTER TABLE memories ADD COLUMN importance REAL NOT NULL DEFAULT 0.5;
ALTER TABLE memories ADD COLUMN status TEXT NOT NULL DEFAULT 'active';

-- Back-fill kind-based importance for existing rows
UPDATE memories SET importance = CASE kind
    WHEN 'decision'    THEN 0.8
    WHEN 'architecture' THEN 0.8
    WHEN 'design'      THEN 0.8
    WHEN 'lesson'      THEN 0.7
    WHEN 'bug'         THEN 0.7
    WHEN 'fix'         THEN 0.7
    WHEN 'pitfall'     THEN 0.7
    WHEN 'todo'        THEN 0.6
    WHEN 'action'      THEN 0.6
    WHEN 'fact'        THEN 0.5
    WHEN 'context'     THEN 0.5
    WHEN 'preference'  THEN 0.5
    WHEN 'observation' THEN 0.3
    WHEN 'note'        THEN 0.3
    ELSE 0.5
END;

CREATE INDEX IF NOT EXISTS idx_memories_importance ON memories(importance DESC);
CREATE INDEX IF NOT EXISTS idx_memories_status     ON memories(status);
"#;

// v0.5.1 hotfix: replace the broken triggers v0.5.0 may have installed.
const SCHEMA_V5: &str = r#"
DROP TRIGGER IF EXISTS memories_ai;
DROP TRIGGER IF EXISTS memories_ad;
DROP TRIGGER IF EXISTS memories_au;

CREATE TRIGGER memories_ai AFTER INSERT ON memories BEGIN
    INSERT INTO memories_fts(rowid, key, content)
    VALUES (new.rowid, new.key, new.content);
END;
CREATE TRIGGER memories_ad AFTER DELETE ON memories BEGIN
    DELETE FROM memories_fts WHERE rowid = old.rowid;
END;
CREATE TRIGGER memories_au AFTER UPDATE ON memories BEGIN
    DELETE FROM memories_fts WHERE rowid = old.rowid;
    INSERT INTO memories_fts(rowid, key, content)
    VALUES (new.rowid, new.key, new.content);
END;
"#;

// D3.2: codebase symbol index
const SCHEMA_V14: &str = r#"
CREATE TABLE IF NOT EXISTS codebase_symbols (
    id         INTEGER PRIMARY KEY,
    file_path  TEXT    NOT NULL,
    line       INTEGER NOT NULL,
    col        INTEGER NOT NULL DEFAULT 0,
    kind       TEXT    NOT NULL,
    name       TEXT    NOT NULL,
    signature  TEXT    NOT NULL DEFAULT '',
    language   TEXT    NOT NULL,
    root_path  TEXT    NOT NULL,
    indexed_at INTEGER NOT NULL,
    embedding  BLOB
);
CREATE INDEX IF NOT EXISTS idx_csym_root ON codebase_symbols(root_path);
CREATE INDEX IF NOT EXISTS idx_csym_name ON codebase_symbols(name COLLATE NOCASE);
CREATE INDEX IF NOT EXISTS idx_csym_kind ON codebase_symbols(kind);
"#;

// v18: forum / shared whiteboard for cross-process Claude Code collaboration.
// Keeps "ephemeral discussion" separate from the long-term `memories` graph so
// embedding-dedup and compaction do not collapse conversation turns.
const SCHEMA_V18: &str = r#"
CREATE TABLE IF NOT EXISTS forum_threads (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    board         TEXT    NOT NULL,
    title         TEXT    NOT NULL,
    created_by    TEXT    NOT NULL,
    created_at    INTEGER NOT NULL,
    last_post_at  INTEGER NOT NULL,
    status        TEXT    NOT NULL DEFAULT 'open',
    tags_json     TEXT
);
CREATE INDEX IF NOT EXISTS idx_forum_threads_board ON forum_threads(board, last_post_at DESC);
CREATE INDEX IF NOT EXISTS idx_forum_threads_status ON forum_threads(status);

CREATE TABLE IF NOT EXISTS forum_posts (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    thread_id     INTEGER NOT NULL REFERENCES forum_threads(id) ON DELETE CASCADE,
    author        TEXT    NOT NULL,
    kind          TEXT    NOT NULL DEFAULT 'msg',
    body          TEXT    NOT NULL,
    refs_json     TEXT,
    created_at    INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_forum_posts_thread ON forum_posts(thread_id, id);
CREATE INDEX IF NOT EXISTS idx_forum_posts_author ON forum_posts(author, id DESC);

CREATE TABLE IF NOT EXISTS forum_subscriptions (
    session_id        TEXT    NOT NULL,
    scope_kind        TEXT    NOT NULL,
    scope_value       TEXT    NOT NULL,
    last_seen_post_id INTEGER NOT NULL DEFAULT 0,
    created_at        INTEGER NOT NULL,
    PRIMARY KEY (session_id, scope_kind, scope_value)
);
CREATE INDEX IF NOT EXISTS idx_forum_subs_scope ON forum_subscriptions(scope_kind, scope_value);
"#;

// v19: cross-process identity & presence registry. Field naming intentionally
// aligned with Google A2A AgentCard so a future Tailscale daemon can serve
// `/.well-known/agent.json` directly off these rows. See
// docs/DESIGN-v19-presence-identity.md.
const SCHEMA_V19: &str = r#"
CREATE TABLE IF NOT EXISTS agent_presence (
    session_id        TEXT    PRIMARY KEY,
    name              TEXT    NOT NULL,
    description       TEXT,
    version           TEXT,
    url               TEXT,
    node              TEXT    NOT NULL,
    project           TEXT    NOT NULL,
    role              TEXT    NOT NULL,
    tag               TEXT,
    cwd               TEXT,
    pid               INTEGER,
    capabilities_json TEXT,
    skills_json       TEXT,
    started_at        INTEGER NOT NULL,
    last_heartbeat_at INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_agent_presence_active  ON agent_presence(last_heartbeat_at DESC);
CREATE INDEX IF NOT EXISTS idx_agent_presence_project ON agent_presence(project, role);
"#;

// v23 — Phase 1 P2 reconsolidation: `superseded_by` foreign key on memories.
// Lets memory_save auto-detect when a new save semantically supersedes an
// existing record (cosine ≥ threshold) and mark the old row → status='superseded'
// with a pointer to the replacement key. memory_search already filters
// `status='active'` so superseded rows auto-drop from search.
//
// FK is intentionally NOT enforced: ON DELETE constraint would cascade if a
// new memory got deleted, orphaning the supersede pointer. Soft pointer is
// the museum-pattern equivalent for memory rows.
const SCHEMA_V22: &str = r#"
ALTER TABLE memories ADD COLUMN superseded_by TEXT;
CREATE INDEX IF NOT EXISTS idx_memories_superseded_by ON memories(superseded_by);
"#;

// v22 — Phase 0 memory telemetry (`memory_query_log`). One row per user-facing
// memory_search / memory_get call; aggregated by `memory_query_stats`.
// Capped to MEMORY_QUERY_LOG_RING_CAP rows; oldest pruned by `record_memory_query`.
const SCHEMA_V21: &str = r#"
CREATE TABLE IF NOT EXISTS memory_query_log (
    id                 INTEGER PRIMARY KEY AUTOINCREMENT,
    kind               TEXT    NOT NULL,
    query              TEXT    NOT NULL,
    tags_json          TEXT    NOT NULL DEFAULT '[]',
    hit_count          INTEGER NOT NULL,
    top_hit_age_secs   INTEGER,
    top_hit_created_at INTEGER,
    duration_us        INTEGER NOT NULL,
    source             TEXT    NOT NULL DEFAULT '',
    at                 INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_memory_query_log_at   ON memory_query_log(at DESC);
CREATE INDEX IF NOT EXISTS idx_memory_query_log_kind ON memory_query_log(kind, at DESC);
CREATE INDEX IF NOT EXISTS idx_memory_query_log_miss ON memory_query_log(hit_count, at DESC);
"#;

// v21 — Synaptic Trace (Hebbian co-activation graph for memory_search hits)
// Vision: docs/DESIGN-v21-synaptic-trace-and-dream.md
const SCHEMA_V20: &str = r#"
CREATE TABLE IF NOT EXISTS memory_coactivation (
    key_a         TEXT    NOT NULL,
    key_b         TEXT    NOT NULL,
    count         INTEGER NOT NULL DEFAULT 1,
    first_at      INTEGER NOT NULL,
    last_at       INTEGER NOT NULL,
    ctx_centroid  BLOB,
    PRIMARY KEY (key_a, key_b),
    CHECK (key_a < key_b),
    FOREIGN KEY (key_a) REFERENCES memories(key) ON DELETE CASCADE,
    FOREIGN KEY (key_b) REFERENCES memories(key) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_memory_coactivation_a       ON memory_coactivation(key_a);
CREATE INDEX IF NOT EXISTS idx_memory_coactivation_b       ON memory_coactivation(key_b);
CREATE INDEX IF NOT EXISTS idx_memory_coactivation_count   ON memory_coactivation(count DESC);
"#;

/// Default database path.
///
/// Linux: `$XDG_DATA_HOME/agent-bridge/state.db` → `~/.local/share/agent-bridge/state.db`.
/// macOS: `~/Library/Application Support/agent-bridge/state.db`.
pub fn default_db_path() -> PathBuf {
    #[cfg(target_os = "linux")]
    {
        if let Ok(xdg) = std::env::var("XDG_DATA_HOME") {
            return PathBuf::from(xdg).join("agent-bridge").join("state.db");
        }
        if let Ok(home) = std::env::var("HOME") {
            return PathBuf::from(home)
                .join(".local/share/agent-bridge")
                .join("state.db");
        }
    }

    #[cfg(target_os = "macos")]
    if let Ok(home) = std::env::var("HOME") {
        return PathBuf::from(home)
            .join("Library/Application Support/agent-bridge")
            .join("state.db");
    }

    PathBuf::from("./agent-bridge-state.db")
}

#[derive(Clone)]
pub struct SqliteStore {
    conn: Connection,
}

impl SqliteStore {
    pub async fn open(path: &Path) -> Result<Self> {
        if let Some(parent) = path.parent() {
            tokio::fs::create_dir_all(parent)
                .await
                .map_err(|e| Error::Backend(format!("create db dir: {e}")))?;
        }
        let conn = Connection::open(path)
            .await
            .map_err(|e| Error::Backend(format!("sqlite open {path:?}: {e}")))?;

        conn.call(|c| -> RusqliteResult<()> {
            // Allow up to 5 s of retries when another writer holds the DB.
            c.busy_timeout(std::time::Duration::from_secs(5))?;
            c.execute_batch("PRAGMA journal_mode=WAL; PRAGMA foreign_keys=ON;")?;
            c.execute_batch(SCHEMA_V1)?;
            c.execute(
                "INSERT OR IGNORE INTO schema_meta(key, value) VALUES('version', '1')",
                [],
            )?;

            // ── v2 migration: add exit_code / stdout / stderr to sessions ──
            let cur: String = c
                .query_row(
                    "SELECT value FROM schema_meta WHERE key='version'",
                    [],
                    |r| r.get(0),
                )
                .unwrap_or_else(|_| "1".to_string());
            if cur.as_str() == "1" {
                let _ = c.execute("ALTER TABLE sessions ADD COLUMN exit_code INTEGER", []);
                let _ = c.execute("ALTER TABLE sessions ADD COLUMN stdout    TEXT", []);
                let _ = c.execute("ALTER TABLE sessions ADD COLUMN stderr    TEXT", []);
                c.execute("UPDATE schema_meta SET value='2' WHERE key='version'", [])?;
            }

            // ── v3 migration: memories table for agent self-memory ──
            let cur: String = c
                .query_row(
                    "SELECT value FROM schema_meta WHERE key='version'",
                    [],
                    |r| r.get(0),
                )
                .unwrap_or_else(|_| "2".to_string());
            if cur.as_str() == "2" {
                c.execute_batch(SCHEMA_V3)?;
                c.execute("UPDATE schema_meta SET value='3' WHERE key='version'", [])?;
            }

            // ── v4 migration: FTS5 index on memories ──
            let cur: String = c
                .query_row(
                    "SELECT value FROM schema_meta WHERE key='version'",
                    [],
                    |r| r.get(0),
                )
                .unwrap_or_else(|_| "3".to_string());
            if cur.as_str() == "3" {
                c.execute_batch(SCHEMA_V4)?;
                // Backfill: copy every existing memory row into the FTS index.
                c.execute(
                    "INSERT INTO memories_fts(rowid, key, content)
                     SELECT rowid, key, content FROM memories",
                    [],
                )?;
                c.execute("UPDATE schema_meta SET value='4' WHERE key='version'", [])?;
            }

            // ── v5 hotfix: replace v0.5.0's broken FTS5 sync triggers ──
            let cur: String = c
                .query_row(
                    "SELECT value FROM schema_meta WHERE key='version'",
                    [],
                    |r| r.get(0),
                )
                .unwrap_or_else(|_| "4".to_string());
            if cur.as_str() == "4" {
                c.execute_batch(SCHEMA_V5)?;
                c.execute("UPDATE schema_meta SET value='5' WHERE key='version'", [])?;
            }

            // ── v6: scope column + memory_edges graph table ──
            let cur: String = c
                .query_row(
                    "SELECT value FROM schema_meta WHERE key='version'",
                    [],
                    |r| r.get(0),
                )
                .unwrap_or_else(|_| "5".to_string());
            if cur.as_str() == "5" {
                c.execute_batch(SCHEMA_V6)?;
                c.execute("UPDATE schema_meta SET value='6' WHERE key='version'", [])?;
            }

            // ── v7: importance score + status for cognitive memory ──
            let cur: String = c
                .query_row(
                    "SELECT value FROM schema_meta WHERE key='version'",
                    [],
                    |r| r.get(0),
                )
                .unwrap_or_else(|_| "6".to_string());
            if cur.as_str() == "6" {
                // Guard: skip ALTER TABLE if columns already exist (idempotent).
                let has_importance: bool = c
                    .query_row(
                        "SELECT COUNT(*) FROM pragma_table_info('memories') WHERE name='importance'",
                        [],
                        |r| r.get::<_, i64>(0),
                    )
                    .unwrap_or(0)
                    > 0;
                if !has_importance {
                    c.execute_batch(SCHEMA_V7)?;
                } else {
                    // Columns exist but version stamp was lost — recreate indices only.
                    c.execute_batch(
                        "CREATE INDEX IF NOT EXISTS idx_memories_importance ON memories(importance DESC);\
                         CREATE INDEX IF NOT EXISTS idx_memories_status ON memories(status);",
                    )?;
                }
                let _ = c.execute("UPDATE schema_meta SET value='7' WHERE key='version'", []);
            }

            // ── v8 migration: cloud-run lifecycle columns on sessions ──
            let cur: String = c
                .query_row(
                    "SELECT value FROM schema_meta WHERE key='version'",
                    [],
                    |r| r.get(0),
                )
                .unwrap_or_else(|_| "7".to_string());
            if cur.as_str() == "7" {
                let has_col: bool = c
                    .query_row(
                        "SELECT COUNT(*) FROM pragma_table_info('sessions') WHERE name='cloud_run_id'",
                        [],
                        |r| r.get::<_, i64>(0),
                    )
                    .unwrap_or(0)
                    > 0;
                if !has_col {
                    c.execute_batch(SCHEMA_V8)?;
                }
                let _ = c.execute("UPDATE schema_meta SET value='8' WHERE key='version'", []);
            }

            // ── v9: plans table (W5) ──
            let cur: String = c
                .query_row(
                    "SELECT value FROM schema_meta WHERE key='version'",
                    [],
                    |r| r.get(0),
                )
                .unwrap_or_else(|_| "8".to_string());
            if cur.as_str() == "8" {
                c.execute_batch(SCHEMA_V9)?;
                let _ = c.execute("UPDATE schema_meta SET value='9' WHERE key='version'", []);
            }

            // ── v10: agent_messages inbox (W6) ──
            let cur: String = c
                .query_row(
                    "SELECT value FROM schema_meta WHERE key='version'",
                    [],
                    |r| r.get(0),
                )
                .unwrap_or_else(|_| "9".to_string());
            if cur.as_str() == "9" {
                c.execute_batch(SCHEMA_V10)?;
                let _ = c.execute("UPDATE schema_meta SET value='10' WHERE key='version'", []);
            }

            // ── v11: memories.trigger_pattern (W7) ──
            let cur: String = c
                .query_row(
                    "SELECT value FROM schema_meta WHERE key='version'",
                    [],
                    |r| r.get(0),
                )
                .unwrap_or_else(|_| "10".to_string());
            if cur.as_str() == "10" {
                let has_col: bool = c
                    .query_row(
                        "SELECT COUNT(*) FROM pragma_table_info('memories') WHERE name='trigger_pattern'",
                        [],
                        |r| r.get::<_, i64>(0),
                    )
                    .unwrap_or(0)
                    > 0;
                if !has_col {
                    c.execute_batch(SCHEMA_V11)?;
                }
                let _ = c.execute("UPDATE schema_meta SET value='11' WHERE key='version'", []);
            }

            // ── v12: memories.embedding BLOB for local vector search ──
            let cur: String = c
                .query_row(
                    "SELECT value FROM schema_meta WHERE key='version'",
                    [],
                    |r| r.get(0),
                )
                .unwrap_or_else(|_| "11".to_string());
            if cur.as_str() == "11" {
                let has_col: bool = c
                    .query_row(
                        "SELECT COUNT(*) FROM pragma_table_info('memories') WHERE name='embedding'",
                        [],
                        |r| r.get::<_, i64>(0),
                    )
                    .unwrap_or(0)
                    > 0;
                if !has_col {
                    c.execute_batch(
                        "ALTER TABLE memories ADD COLUMN embedding BLOB;",
                    )?;
                }
                let _ = c.execute("UPDATE schema_meta SET value='12' WHERE key='version'", []);
            }

            // ── v13: mcp_tool_errors (Phase C) ──
            let cur: String = c
                .query_row(
                    "SELECT value FROM schema_meta WHERE key='version'",
                    [],
                    |r| r.get(0),
                )
                .unwrap_or_else(|_| "12".to_string());
            if cur.as_str() == "12" {
                c.execute_batch(SCHEMA_V13)?;
                let _ = c.execute("UPDATE schema_meta SET value='13' WHERE key='version'", []);
            }

            // ── v14: codebase_symbols table (D3.2) ──
            let cur: String = c
                .query_row(
                    "SELECT value FROM schema_meta WHERE key='version'",
                    [],
                    |r| r.get(0),
                )
                .unwrap_or_else(|_| "13".to_string());
            if cur.as_str() == "13" {
                c.execute_batch(SCHEMA_V14)?;
                let _ = c.execute("UPDATE schema_meta SET value='14' WHERE key='version'", []);
            }

            // ── v15: codebase_symbols.embedding BLOB (D3.2b semantic search) ──
            let cur: String = c
                .query_row(
                    "SELECT value FROM schema_meta WHERE key='version'",
                    [],
                    |r| r.get(0),
                )
                .unwrap_or_else(|_| "14".to_string());
            if cur.as_str() == "14" {
                let col_exists: i64 = c
                    .query_row(
                        "SELECT COUNT(*) FROM pragma_table_info('codebase_symbols') \
                         WHERE name='embedding'",
                        [],
                        |r| r.get(0),
                    )
                    .unwrap_or(0);
                if col_exists == 0 {
                    c.execute_batch(
                        "ALTER TABLE codebase_symbols ADD COLUMN embedding BLOB;",
                    )?;
                }
                let _ = c.execute("UPDATE schema_meta SET value='15' WHERE key='version'", []);
            }

            // ── v16: clear stale 512-dim hash embeddings → force re-embed at 384-dim ──
            // VECTOR_DIM changed from 512 to 384 (all-MiniLM-L6-v2).  Old stored
            // blobs are 2048 bytes (512×f32); new ones will be 1536 bytes (384×f32).
            // cosine_similarity returns 0.0 on dimension mismatch, so we must clear
            // before the new embedder runs the backfill.
            let cur: String = c
                .query_row(
                    "SELECT value FROM schema_meta WHERE key='version'",
                    [],
                    |r| r.get(0),
                )
                .unwrap_or_else(|_| "15".to_string());
            if cur.as_str() == "15" {
                c.execute_batch(
                    "UPDATE memories          SET embedding = NULL;
                     UPDATE codebase_symbols  SET embedding = NULL;",
                )?;
                let _ = c.execute("UPDATE schema_meta SET value='16' WHERE key='version'", []);
            }

            // ── v17: mcp_tool_calls full telemetry table ──
            let cur: String = c
                .query_row(
                    "SELECT value FROM schema_meta WHERE key='version'",
                    [],
                    |r| r.get(0),
                )
                .unwrap_or_else(|_| "16".to_string());
            if cur.as_str() == "16" {
                c.execute_batch(SCHEMA_V17)?;
                let _ = c.execute("UPDATE schema_meta SET value='17' WHERE key='version'", []);
            }

            // ── v18: forum tables (cross-process collaboration whiteboard) ──
            let cur: String = c
                .query_row(
                    "SELECT value FROM schema_meta WHERE key='version'",
                    [],
                    |r| r.get(0),
                )
                .unwrap_or_else(|_| "17".to_string());
            if cur.as_str() == "17" {
                c.execute_batch(SCHEMA_V18)?;
                let _ = c.execute("UPDATE schema_meta SET value='18' WHERE key='version'", []);
            }

            // ── v19: agent_presence registry (identity + heartbeat) ──
            let cur: String = c
                .query_row(
                    "SELECT value FROM schema_meta WHERE key='version'",
                    [],
                    |r| r.get(0),
                )
                .unwrap_or_else(|_| "18".to_string());
            if cur.as_str() == "18" {
                c.execute_batch(SCHEMA_V19)?;
                let _ = c.execute("UPDATE schema_meta SET value='19' WHERE key='version'", []);
            }

            // ── v20: synaptic trace (memory_coactivation, project codename "v21") ──
            let cur: String = c
                .query_row(
                    "SELECT value FROM schema_meta WHERE key='version'",
                    [],
                    |r| r.get(0),
                )
                .unwrap_or_else(|_| "19".to_string());
            if cur.as_str() == "19" {
                c.execute_batch(SCHEMA_V20)?;
                let _ = c.execute("UPDATE schema_meta SET value='20' WHERE key='version'", []);
            }

            // ── v21: memory_query_log (Phase 0 memory telemetry) ──
            let cur: String = c
                .query_row(
                    "SELECT value FROM schema_meta WHERE key='version'",
                    [],
                    |r| r.get(0),
                )
                .unwrap_or_else(|_| "20".to_string());
            if cur.as_str() == "20" {
                c.execute_batch(SCHEMA_V21)?;
                let _ = c.execute("UPDATE schema_meta SET value='21' WHERE key='version'", []);
            }

            // ── v22: superseded_by FK (Phase 1 P2 reconsolidation) ──
            let cur: String = c
                .query_row(
                    "SELECT value FROM schema_meta WHERE key='version'",
                    [],
                    |r| r.get(0),
                )
                .unwrap_or_else(|_| "21".to_string());
            if cur.as_str() == "21" {
                c.execute_batch(SCHEMA_V22)?;
                let _ = c.execute("UPDATE schema_meta SET value='22' WHERE key='version'", []);
            }
            Ok(())
        })
        .await
        .map_err(|e| Error::Backend(format!("sqlite migrate: {e}")))?;

        info!(path = %path.display(), "SqliteStore ready");
        Ok(Self { conn })
    }

    /// Write [`MemoryEdgeExport`] JSONL for edges whose endpoints are both in `keys`.
    async fn export_edges_for_key_set(
        &self,
        keys: &std::collections::HashSet<String>,
        out_path: &Path,
    ) -> Result<u64> {
        let keys_clone = keys.clone();
        let rows: Vec<MemoryEdgeExport> = self
            .conn
            .call(move |c| -> RusqliteResult<Vec<MemoryEdgeExport>> {
                let mut stmt = c.prepare(
                    "SELECT from_key, to_key, edge_type, weight, created_at FROM memory_edges",
                )?;
                let rows = stmt
                    .query_map([], |row| {
                        Ok(MemoryEdgeExport {
                            from_key: row.get(0)?,
                            to_key: row.get(1)?,
                            edge_type: row.get(2)?,
                            weight: row.get(3)?,
                            created_at: row.get(4)?,
                        })
                    })?
                    .collect::<std::result::Result<Vec<_>, _>>()?;
                Ok(rows)
            })
            .await
            .map_err(|e| Error::Backend(format!("export_edges query: {e}")))?;

        let selected: Vec<MemoryEdgeExport> = rows
            .into_iter()
            .filter(|e| keys_clone.contains(&e.from_key) && keys_clone.contains(&e.to_key))
            .collect();

        if let Some(parent) = out_path.parent() {
            tokio::fs::create_dir_all(parent)
                .await
                .map_err(|e| Error::Backend(format!("mkdir {parent:?}: {e}")))?;
        }
        let mut buf = String::new();
        for e in &selected {
            buf.push_str(&serde_json::to_string(e)?);
            buf.push('\n');
        }
        tokio::fs::write(out_path, buf)
            .await
            .map_err(|e| Error::Backend(format!("write edges {out_path:?}: {e}")))?;
        Ok(selected.len() as u64)
    }

    /// Upsert edges from JSONL (`MemoryEdgeExport` per line).
    async fn import_edges_jsonl(&self, edges_path: &Path) -> Result<(u64, u64)> {
        let bytes = tokio::fs::read(edges_path)
            .await
            .map_err(|e| Error::Backend(format!("read edges {edges_path:?}: {e}")))?;
        let text = String::from_utf8_lossy(&bytes).into_owned();

        let mut parsed: Vec<MemoryEdgeExport> = Vec::new();
        let mut malformed = 0u64;
        for line in text.lines() {
            if line.trim().is_empty() {
                continue;
            }
            match serde_json::from_str::<MemoryEdgeExport>(line) {
                Ok(e) => parsed.push(e),
                Err(_) => malformed += 1,
            }
        }

        let now = now_secs();
        let upserted = self
            .conn
            .call(move |c| -> RusqliteResult<u64> {
                let tx = c.unchecked_transaction()?;
                let mut n = 0u64;
                for e in parsed {
                    let from = e.from_key.trim();
                    let to = e.to_key.trim();
                    let et = e.edge_type.trim();
                    if from.is_empty() || to.is_empty() || et.is_empty() {
                        continue;
                    }
                    let w = e.weight.clamp(0.0, 2.0);
                    let ca = if e.created_at > 0 { e.created_at } else { now };
                    tx.execute(
                        "INSERT INTO memory_edges (from_key, to_key, edge_type, weight, created_at)
                         VALUES (?1, ?2, ?3, ?4, ?5)
                         ON CONFLICT(from_key, to_key, edge_type) DO UPDATE SET
                            weight = excluded.weight",
                        params![from, to, et, w, ca],
                    )?;
                    n += 1;
                }
                tx.commit()?;
                Ok(n)
            })
            .await
            .map_err(|e| Error::Backend(format!("import_edges tx: {e}")))?;

        Ok((upserted, malformed))
    }
}

// ─── memory.* implementations ──────────────────────────────────────────

/// Make a user query safe + useful for FTS5 MATCH.
///
/// FTS5 has its own tiny query language (operators AND/OR/NOT/NEAR, "phrase",
/// `prefix*`, column filters). We let users pass either:
/// - **Plain text** (whitespace-separated terms) — we split into tokens,
///   match the indexer's tokenisation rules, and add `*` for prefix matching.
/// - **Quoted phrases or anything containing FTS5 operators** — passed through
///   unchanged so power users can write `"signal exit" OR sigterm`.
///
/// **Token-boundary alignment** (v0.7.2): SQLite FTS5's default `unicode61`
/// tokeniser treats `_` as a token char and everything else non-alphanumeric
/// as a separator. We mirror that exactly: split on `!c.is_alphanumeric() && c != '_'`,
/// then prefix-suffix each non-empty token. Earlier versions stripped `.` from
/// the input rather than splitting on it, so a query like `v0.7.1` collapsed
/// to `v071*` and matched nothing (`lesson_fts5_search_dot_strip_bug`).
fn sanitise_fts_query(q: &str) -> String {
    let trimmed = q.trim();
    let has_operator = trimmed.contains('"')
        || trimmed.contains('*')
        || trimmed.contains(':')
        || trimmed.contains('(')
        || trimmed.contains(')')
        || trimmed.contains(" AND ")
        || trimmed.contains(" OR ")
        || trimmed.contains(" NOT ")
        || trimmed.contains(" NEAR ");
    if has_operator {
        return trimmed.to_string();
    }
    // Plain-text path: split on the same separators FTS5's unicode61 uses,
    // so a single tokenised user query maps 1:1 to indexed tokens.
    trimmed
        .split(|c: char| !c.is_alphanumeric() && c != '_')
        .filter(|s| !s.is_empty())
        .map(|s| format!("{s}*"))
        .collect::<Vec<_>>()
        .join(" ")
}

fn now_secs() -> i64 {
    std::time::SystemTime::now()
        .duration_since(std::time::UNIX_EPOCH)
        .map(|d| d.as_secs() as i64)
        .unwrap_or(0)
}

/// **Phase 1 P3** — kind-aware decay constant. Faster decay for ephemeral
/// kinds (observation, todo) because they age out fast in real workflows;
/// slower for long-lived knowledge (decision, architecture). The current
/// 30-day-everywhere default was a placeholder until usage data confirmed
/// that observations rot in days while decisions stay relevant for months.
fn decay_tau_days(kind: &str) -> f64 {
    match kind {
        "observation" | "note" => 7.0,
        "todo" | "action" => 14.0,
        "lesson" | "bug" | "fix" | "pitfall" | "error_pattern" => 60.0,
        "decision" | "architecture" | "design" => 90.0,
        // fact / context / session_handoff / preference / unknown
        _ => 30.0,
    }
}

/// Composite score for memory_search results.
/// Each hit starts with a base of 1.0; recency multiplies by `exp(-age_days/τ)`
/// where τ is kind-aware (see [`decay_tau_days`]). For τ=30 (default), a
/// memory used today scores ~1.0×, one used 30d ago ~0.37×, 90d ago ~0.05×.
/// Then `+0.3*ln(1+access_count)` bumps frequently-touched memories.
fn memory_score(last_accessed_at: i64, access_count: u64, now: i64, kind: &str) -> f64 {
    let age_days = ((now - last_accessed_at).max(0) as f64) / 86_400.0;
    let recency = (-age_days / decay_tau_days(kind)).exp();
    let frequency = (1.0 + access_count as f64).ln();
    recency + 0.3 * frequency
}

/// Map a memory kind string to its default importance score.
fn importance_for_kind(kind: &str) -> f64 {
    match kind {
        "decision" | "architecture" | "design" => 0.8,
        "lesson" | "bug" | "fix" | "pitfall" => 0.7,
        "error_pattern" => 0.72,
        "todo" | "action" => 0.6,
        "fact" | "context" | "preference" | "session_handoff" => 0.5,
        "observation" | "note" => 0.3,
        _ => 0.5,
    }
}

/// Tokenise content for contradiction-overlap detection.
/// Returns lowercase alpha-numeric tokens of length >= 4.
fn overlap_tokens(text: &str) -> std::collections::HashSet<String> {
    text.split(|c: char| !c.is_alphanumeric())
        .filter(|t| t.len() >= 4)
        .map(|t| t.to_lowercase())
        .collect()
}

/// Jaccard-style overlap ratio between two token sets.
fn token_overlap_ratio(
    a: &std::collections::HashSet<String>,
    b: &std::collections::HashSet<String>,
) -> f64 {
    if a.is_empty() || b.is_empty() {
        return 0.0;
    }
    let intersection = a.intersection(b).count();
    let union = a.union(b).count();
    if union == 0 {
        0.0
    } else {
        intersection as f64 / union as f64
    }
}

fn parse_str_array(s: &str) -> Vec<String> {
    serde_json::from_str(s).unwrap_or_default()
}

/// Clamp `s` to at most `max` bytes, preserving UTF-8 boundaries.
/// Action selected for one row during a [`SqliteStore::memory_import`] preflight.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
enum ImportAction {
    Insert,
    Update,
    Skip,
}

/// Decide what `memory_import` will do per row, *without* touching SQLite or the
/// embedding backend. Pulled out so the "skip everything" fast path is unit-testable
/// and so we can guarantee `embed_batch` is only called for rows we actually persist.
fn plan_import_actions(
    parsed: &[MemoryRecord],
    existing_uat: &std::collections::HashMap<String, i64>,
    policy: ImportConflictPolicy,
) -> Vec<ImportAction> {
    parsed
        .iter()
        .map(|r| match existing_uat.get(&r.key) {
            None => ImportAction::Insert,
            Some(&existing) => match policy {
                ImportConflictPolicy::Skip => ImportAction::Skip,
                ImportConflictPolicy::Overwrite => ImportAction::Update,
                ImportConflictPolicy::NewerWins => {
                    if r.updated_at > existing {
                        ImportAction::Update
                    } else {
                        ImportAction::Skip
                    }
                }
            },
        })
        .collect()
}

/// Picks the percentile element from a **sorted-ascending** slice. Returns
/// 0 for empty input. `q` clamped to [0.0, 1.0]. Used by `memory_query_stats`
/// for p50/p95 latency.
fn pct_idx(sorted: &[i64], q: f64) -> i64 {
    if sorted.is_empty() {
        return 0;
    }
    let q = q.clamp(0.0, 1.0);
    let idx = ((sorted.len() as f64 - 1.0) * q).round() as usize;
    sorted[idx.min(sorted.len() - 1)]
}

fn clamp(s: &str, max: usize) -> String {
    if s.len() <= max {
        return s.to_string();
    }
    let mut end = max;
    while end > 0 && !s.is_char_boundary(end) {
        end -= 1;
    }
    let mut out = s[..end].to_string();
    out.push_str("\n…[truncated]…");
    out
}

fn severity_to_str(s: NotifySeverity) -> &'static str {
    match s {
        NotifySeverity::Info => "info",
        NotifySeverity::Success => "success",
        NotifySeverity::Warning => "warning",
        NotifySeverity::Error => "error",
        NotifySeverity::Attention => "attention",
    }
}
fn severity_from_str(s: &str) -> NotifySeverity {
    match s {
        "success" => NotifySeverity::Success,
        "warning" => NotifySeverity::Warning,
        "error" => NotifySeverity::Error,
        "attention" => NotifySeverity::Attention,
        _ => NotifySeverity::Info,
    }
}
fn source_to_str(s: NotifySource) -> &'static str {
    match s {
        NotifySource::Manual => "manual",
        NotifySource::Osc9 => "osc9",
        NotifySource::Osc99 => "osc99",
        NotifySource::Osc777 => "osc777",
        NotifySource::Mcp => "mcp",
        NotifySource::System => "system",
    }
}
fn source_from_str(s: &str) -> NotifySource {
    match s {
        "osc9" => NotifySource::Osc9,
        "osc99" => NotifySource::Osc99,
        "osc777" => NotifySource::Osc777,
        "mcp" => NotifySource::Mcp,
        "system" => NotifySource::System,
        _ => NotifySource::Manual,
    }
}

#[async_trait]
impl StateStore for SqliteStore {
    async fn save_session(&self, session: &StoredSession) -> Result<()> {
        let s = session.clone();
        self.conn
            .call(move |c| -> RusqliteResult<()> {
                c.execute(
                    "INSERT OR REPLACE INTO sessions
                       (id, runtime_id, cwd, started_at, ended_at, exit_code, stdout, stderr,
                        cloud_run_id, cloud_run_state, cloud_session_link)
                     VALUES (?1, ?2, ?3, ?4, ?5, ?6, ?7, ?8, ?9, ?10, ?11)",
                    params![
                        s.id.as_str(),
                        s.runtime_id,
                        s.cwd,
                        s.started_at,
                        s.ended_at,
                        s.exit_code,
                        s.stdout,
                        s.stderr,
                        s.cloud_run_id,
                        s.cloud_run_state,
                        s.cloud_session_link
                    ],
                )?;
                Ok(())
            })
            .await
            .map_err(|e| Error::Backend(format!("save_session: {e}")))?;
        Ok(())
    }

    async fn load_session(&self, id: &SessionId) -> Result<Option<StoredSession>> {
        let key = id.as_str().to_string();
        let row = self
            .conn
            .call(move |c| -> RusqliteResult<Option<StoredSession>> {
                let mut stmt = c.prepare(
                    "SELECT id, runtime_id, cwd, started_at, ended_at, exit_code, stdout, stderr,
                            cloud_run_id, cloud_run_state, cloud_session_link
                     FROM sessions WHERE id=?1",
                )?;
                let r = stmt
                    .query_row(params![key], |row| {
                        Ok(StoredSession {
                            id: SessionId::from_raw(row.get::<_, String>(0)?),
                            runtime_id: row.get(1)?,
                            cwd: row.get(2)?,
                            started_at: row.get(3)?,
                            ended_at: row.get(4)?,
                            exit_code: row.get(5)?,
                            stdout: row.get(6)?,
                            stderr: row.get(7)?,
                            cloud_run_id: row.get(8)?,
                            cloud_run_state: row.get(9)?,
                            cloud_session_link: row.get(10)?,
                        })
                    })
                    .ok();
                Ok(r)
            })
            .await
            .map_err(|e| Error::Backend(format!("load_session: {e}")))?;
        Ok(row)
    }

    async fn list_sessions(
        &self,
        filter: &SessionFilter,
        limit: u32,
    ) -> Result<Vec<StoredSession>> {
        let limit_i = limit as i64;
        let f_runtime = filter.runtime_id.clone();
        let f_cwd_prefix = filter.cwd_prefix.clone();
        let f_exited = filter.exited_only;
        let f_exit_code = filter.exit_code;

        let rows = self
            .conn
            .call(move |c| -> RusqliteResult<Vec<StoredSession>> {
                // Build WHERE incrementally; bind params positionally.
                // SQLite tolerates parameters bound but unused, so this stays
                // simple: each filter contributes either an active condition
                // or a no-op `?N IS NULL OR …` guard.
                //
                // For cwd_prefix we use `LIKE ?N || '%'` since an explicit `%`
                // suffix lets us reuse the same string param.
                let cwd_like = f_cwd_prefix.as_ref().map(|p| {
                    let mut s = p.replace('%', r"\%").replace('_', r"\_");
                    s.push('%');
                    s
                });

                let mut stmt = c.prepare(
                    "SELECT id, runtime_id, cwd, started_at, ended_at, exit_code, stdout, stderr,
                            cloud_run_id, cloud_run_state, cloud_session_link
                     FROM sessions
                     WHERE (?1 IS NULL OR runtime_id = ?1)
                       AND (?2 IS NULL OR cwd LIKE ?2 ESCAPE '\\')
                       AND (?3 IS NULL
                            OR (?3 = 1 AND ended_at IS NOT NULL)
                            OR (?3 = 0 AND ended_at IS NULL))
                       AND (?4 IS NULL OR exit_code = ?4)
                     ORDER BY started_at DESC
                     LIMIT ?5",
                )?;
                let exited_param: Option<i64> = f_exited.map(|b| if b { 1 } else { 0 });
                let rows = stmt
                    .query_map(
                        params![f_runtime, cwd_like, exited_param, f_exit_code, limit_i],
                        |row| {
                            Ok(StoredSession {
                                id: SessionId::from_raw(row.get::<_, String>(0)?),
                                runtime_id: row.get(1)?,
                                cwd: row.get(2)?,
                                started_at: row.get(3)?,
                                ended_at: row.get(4)?,
                                exit_code: row.get(5)?,
                                stdout: row.get(6)?,
                                stderr: row.get(7)?,
                                cloud_run_id: row.get(8)?,
                                cloud_run_state: row.get(9)?,
                                cloud_session_link: row.get(10)?,
                            })
                        },
                    )?
                    .collect::<std::result::Result<Vec<_>, _>>()?;
                Ok(rows)
            })
            .await
            .map_err(|e| Error::Backend(format!("list_sessions: {e}")))?;
        Ok(rows)
    }

    async fn finalise_session(
        &self,
        id: &SessionId,
        ended_at: i64,
        exit_code: Option<i32>,
        stdout: Option<String>,
        stderr: Option<String>,
    ) -> Result<()> {
        let key = id.as_str().to_string();
        let stdout = stdout.map(|s| clamp(&s, STDIO_CAP));
        let stderr = stderr.map(|s| clamp(&s, STDIO_CAP));
        self.conn
            .call(move |c| -> RusqliteResult<()> {
                c.execute(
                    "UPDATE sessions
                        SET ended_at = ?2, exit_code = ?3, stdout = ?4, stderr = ?5
                      WHERE id = ?1",
                    params![key, ended_at, exit_code, stdout, stderr],
                )?;
                Ok(())
            })
            .await
            .map_err(|e| Error::Backend(format!("finalise_session: {e}")))?;
        Ok(())
    }

    async fn append_notification(&self, evt: &NotifyEvent) -> Result<()> {
        let source = source_to_str(evt.source).to_string();
        let severity = severity_to_str(evt.severity).to_string();
        let title = evt.title.clone();
        let body = evt.body.clone();
        let session_id = evt.session_id.as_ref().map(|s| s.as_str().to_string());
        let context = serde_json::to_string(&evt.context)?;

        self.conn
            .call(move |c| -> RusqliteResult<()> {
                c.execute(
                    "INSERT INTO notifications(ts, source, severity, title, body, session_id, context)
                     VALUES (CAST(strftime('%s','now') AS INTEGER), ?1, ?2, ?3, ?4, ?5, ?6)",
                    params![source, severity, title, body, session_id, context],
                )?;
                Ok(())
            })
            .await
            .map_err(|e| Error::Backend(format!("append_notification: {e}")))?;
        Ok(())
    }

    async fn recent_notifications(&self, limit: u32) -> Result<Vec<NotificationRecord>> {
        let limit = limit as i64;
        let rows = self
            .conn
            .call(move |c| -> RusqliteResult<Vec<NotificationRecord>> {
                let mut stmt = c.prepare(
                    "SELECT ts, source, severity, title, body, session_id, context
                     FROM notifications ORDER BY ts DESC, id DESC LIMIT ?1",
                )?;
                let rows = stmt
                    .query_map(params![limit], |row| {
                        let context_str: String = row.get(6)?;
                        let context =
                            serde_json::from_str(&context_str).unwrap_or(serde_json::Value::Null);
                        let session_id: Option<String> = row.get(5)?;
                        Ok(NotificationRecord {
                            ts: row.get(0)?,
                            event: NotifyEvent {
                                source: source_from_str(&row.get::<_, String>(1)?),
                                severity: severity_from_str(&row.get::<_, String>(2)?),
                                title: row.get(3)?,
                                body: row.get(4)?,
                                session_id: session_id.map(SessionId::from_raw),
                                context,
                            },
                        })
                    })?
                    .collect::<std::result::Result<Vec<_>, _>>()?;
                Ok(rows)
            })
            .await
            .map_err(|e| Error::Backend(format!("recent_notifications: {e}")))?;
        Ok(rows)
    }

    async fn record_mcp_tool_error(&self, tool_name: &str, message: &str) -> Result<()> {
        const MSG_CAP: usize = 2048;
        let msg = clamp(message, MSG_CAP);
        let tn = {
            let t = tool_name.trim();
            if t.is_empty() {
                "(unknown)".to_string()
            } else {
                clamp(t, 512)
            }
        };
        let cap = i64::from(MCP_TOOL_ERROR_RING_CAP);
        self.conn
            .call(move |c| -> RusqliteResult<()> {
                let ts = now_secs();
                c.execute(
                    "INSERT INTO mcp_tool_errors (ts, tool_name, message) VALUES (?1, ?2, ?3)",
                    params![ts, tn, msg],
                )?;
                c.execute(
                    "DELETE FROM mcp_tool_errors WHERE id NOT IN (
                        SELECT id FROM mcp_tool_errors ORDER BY ts DESC, id DESC LIMIT ?1
                    )",
                    params![cap],
                )?;
                Ok(())
            })
            .await
            .map_err(|e| Error::Backend(format!("record_mcp_tool_error: {e}")))?;
        Ok(())
    }

    async fn recent_mcp_tool_errors(&self, limit: u32) -> Result<Vec<McpToolErrorRecord>> {
        let limit = limit.min(500).max(1) as i64;
        let rows = self
            .conn
            .call(move |c| -> RusqliteResult<Vec<McpToolErrorRecord>> {
                let mut stmt = c.prepare(
                    "SELECT ts, tool_name, message FROM mcp_tool_errors
                     ORDER BY ts DESC, id DESC LIMIT ?1",
                )?;
                let rows = stmt
                    .query_map(params![limit], |row| {
                        Ok(McpToolErrorRecord {
                            ts: row.get(0)?,
                            tool_name: row.get(1)?,
                            message: row.get(2)?,
                        })
                    })?
                    .collect::<std::result::Result<Vec<_>, _>>()?;
                Ok(rows)
            })
            .await
            .map_err(|e| Error::Backend(format!("recent_mcp_tool_errors: {e}")))?;
        Ok(rows)
    }

    async fn record_mcp_tool_call(
        &self,
        tool_name: &str,
        duration_ms: u32,
        ok: bool,
        args_size: Option<u32>,
        result_size: Option<u32>,
    ) -> Result<()> {
        let ts = now_secs();
        let tn = tool_name.to_string();
        let ok_int = if ok { 1 } else { 0 };
        let args_size_i = args_size.map(|v| v as i64);
        let result_size_i = result_size.map(|v| v as i64);
        self.conn
            .call(move |c| -> RusqliteResult<()> {
                c.execute(
                    "INSERT INTO mcp_tool_calls
                       (ts, tool_name, duration_ms, ok, args_size, result_size)
                     VALUES (?1, ?2, ?3, ?4, ?5, ?6)",
                    params![ts, tn, duration_ms as i64, ok_int, args_size_i, result_size_i],
                )?;
                Ok(())
            })
            .await
            .map_err(|e| Error::Backend(format!("record_mcp_tool_call: {e}")))?;
        Ok(())
    }

    async fn mcp_tool_call_stats(
        &self,
        window_secs: i64,
        top_n: u32,
    ) -> Result<Vec<McpToolCallStats>> {
        let cutoff = now_secs() - window_secs.max(0);
        let limit = top_n.min(200).max(1) as i64;
        let rows = self
            .conn
            .call(move |c| -> RusqliteResult<Vec<McpToolCallStats>> {
                // SQLite has no built-in percentile; we compute p95 via window function.
                // For correctness we read raw durations per tool and aggregate in Rust.
                let mut stmt = c.prepare(
                    "SELECT tool_name, duration_ms, ok, COALESCE(result_size, 0)
                     FROM mcp_tool_calls
                     WHERE ts >= ?1
                     ORDER BY tool_name",
                )?;
                let mut buckets: std::collections::HashMap<
                    String,
                    Vec<(u32, bool, u32)>,
                > = std::collections::HashMap::new();
                let iter = stmt.query_map(params![cutoff], |row| {
                    Ok((
                        row.get::<_, String>(0)?,
                        row.get::<_, i64>(1)? as u32,
                        row.get::<_, i64>(2)? != 0,
                        row.get::<_, i64>(3)? as u32,
                    ))
                })?;
                for r in iter {
                    let (name, dur, ok, sz) = r?;
                    buckets.entry(name).or_default().push((dur, ok, sz));
                }

                let mut out: Vec<McpToolCallStats> = buckets
                    .into_iter()
                    .map(|(name, mut rows)| {
                        rows.sort_by_key(|(d, _, _)| *d);
                        let count = rows.len() as u64;
                        let errors = rows.iter().filter(|(_, ok, _)| !ok).count() as u64;
                        let sum_dur: u64 = rows.iter().map(|(d, _, _)| *d as u64).sum();
                        let avg_dur = if count > 0 {
                            sum_dur as f64 / count as f64
                        } else {
                            0.0
                        };
                        let max_dur = rows.last().map(|(d, _, _)| *d).unwrap_or(0);
                        // p95: index = ceil(0.95 * n) - 1
                        let p95_idx = ((count as f64 * 0.95).ceil() as usize)
                            .saturating_sub(1)
                            .min(rows.len().saturating_sub(1));
                        let p95_dur = rows.get(p95_idx).map(|(d, _, _)| *d).unwrap_or(0);
                        let sum_sz: u64 = rows.iter().map(|(_, _, s)| *s as u64).sum();
                        let avg_sz = if count > 0 {
                            sum_sz as f64 / count as f64
                        } else {
                            0.0
                        };
                        McpToolCallStats {
                            tool_name: name,
                            call_count: count,
                            error_count: errors,
                            avg_duration_ms: avg_dur,
                            p95_duration_ms: p95_dur,
                            max_duration_ms: max_dur,
                            avg_result_size: avg_sz,
                        }
                    })
                    .collect();
                out.sort_by(|a, b| b.call_count.cmp(&a.call_count));
                out.truncate(limit as usize);
                Ok(out)
            })
            .await
            .map_err(|e| Error::Backend(format!("mcp_tool_call_stats: {e}")))?;
        Ok(rows)
    }

    // ─── memory.* (v0.4) ──────────────────────────────────────────────

    async fn memory_save(&self, mem: &MemoryRecord) -> Result<()> {
        let key = mem.key.clone();
        let kind = mem.kind.clone();
        let content = clamp(&mem.content, MEMORY_CONTENT_CAP);
        let tags = serde_json::to_string(&mem.tags)?;
        let related = serde_json::to_string(&mem.related_keys)?;
        let scope = mem.scope.clone();
        // Use caller-supplied importance if non-default, otherwise auto-assign from kind.
        let importance = if (mem.importance - 0.5).abs() > 1e-9 {
            mem.importance.clamp(0.0, 1.0)
        } else {
            importance_for_kind(&kind)
        };
        let status = if mem.status.is_empty() {
            "active".to_string()
        } else {
            mem.status.clone()
        };
        let trigger_pattern = mem
            .trigger_pattern
            .clone()
            .map(|s| s.trim().to_string())
            .filter(|s| !s.is_empty());
        let now = now_secs();

        // Preflight: if a row with this key already exists with the same content
        // and a well-formed embedding, reuse it instead of paying the embed cost
        // (mirrors the memory_import preflight in this same file). Same-content
        // re-saves are common — session_curate re-extracts identical lessons,
        // and users may update tags/importance without touching content.
        const EXPECTED_EMBED_BYTES: usize = crate::vector::VECTOR_DIM * 4;
        let key_for_preflight = key.clone();
        let existing: Option<(String, Vec<u8>)> = self
            .conn
            .call(move |c| -> RusqliteResult<Option<(String, Vec<u8>)>> {
                let mut stmt =
                    c.prepare("SELECT content, embedding FROM memories WHERE key = ?1")?;
                let mut rows = stmt.query(params![key_for_preflight])?;
                if let Some(row) = rows.next()? {
                    let existing_content: String = row.get(0)?;
                    let existing_emb: Option<Vec<u8>> = row.get(1)?;
                    Ok(Some((existing_content, existing_emb.unwrap_or_default())))
                } else {
                    Ok(None)
                }
            })
            .await
            .map_err(|e| Error::Backend(format!("memory_save preflight: {e}")))?;

        let embedding_bytes = match existing {
            Some((existing_content, existing_emb))
                if existing_content == content && existing_emb.len() == EXPECTED_EMBED_BYTES =>
            {
                existing_emb
            }
            _ => crate::vector::encode_embedding(&crate::vector::embed_text(&content)),
        };

        // Pre-compute overlap tokens for contradiction detection (outside closure).
        let new_tokens = overlap_tokens(&content);
        let kind_clone = kind.clone();
        // Caller-supplied `dedupe:<id>` tags collapse near-duplicate writes
        // to a single active row (Phase 2 #2). E.g. P5 dream replay sets
        // `dedupe:cluster:<hash>` so different LLMs summarizing the same
        // source cluster supersede each other instead of accumulating.
        let dedupe_tags: Vec<String> = mem
            .tags
            .iter()
            .filter(|t| t.starts_with("dedupe:"))
            .cloned()
            .collect();

        self.conn
            .call(move |c| -> RusqliteResult<()> {
                c.execute(
                    "INSERT INTO memories
                       (key, kind, content, tags, related_keys, scope,
                        created_at, updated_at, last_accessed_at, access_count,
                        importance, status, trigger_pattern, embedding)
                     VALUES (?1, ?2, ?3, ?4, ?5, ?6, ?7, ?7, ?7, 0, ?8, ?9, ?10, ?11)
                     ON CONFLICT(key) DO UPDATE SET
                        kind          = excluded.kind,
                        content       = excluded.content,
                        tags          = excluded.tags,
                        related_keys  = excluded.related_keys,
                        scope         = excluded.scope,
                        updated_at    = excluded.updated_at,
                        importance    = excluded.importance,
                        status        = CASE
                            WHEN memories.status IN ('superseded', 'tombstoned')
                                THEN 'active'
                            ELSE excluded.status
                        END,
                        trigger_pattern = excluded.trigger_pattern,
                        embedding     = excluded.embedding",
                    params![
                        key,
                        kind_clone,
                        content,
                        tags,
                        related,
                        scope,
                        now,
                        importance,
                        status,
                        trigger_pattern,
                        embedding_bytes
                    ],
                )?;

                // ── dedupe-tag pass (Phase 2 #2) ─────────────────────────────
                // Caller-supplied `dedupe:<id>` tags explicitly group records
                // that should collapse to the most recent write. Newer save
                // (this one) wins; matching active records get superseded.
                // Tag-based (not column-based) so cross-machine sync works
                // without a schema migration — tags already serialize through
                // memory_export / memory_import.
                for dedupe_tag in &dedupe_tags {
                    let mut cand_stmt = c.prepare(
                        "SELECT key FROM memories
                         WHERE key != ?1
                           AND status = 'active'
                           AND tags LIKE ?2",
                    )?;
                    // The `\"<tag>\"` quoting matches a JSON-array string
                    // element exactly, not a substring of another tag.
                    let json_needle = format!("%\"{}\"%", dedupe_tag);
                    let dups: Vec<String> = cand_stmt
                        .query_map(params![key, json_needle], |row| row.get::<_, String>(0))?
                        .filter_map(|r| r.ok())
                        .collect();
                    for cand_key in dups {
                        c.execute(
                            "INSERT INTO memory_edges
                               (from_key, to_key, edge_type, weight, created_at)
                             VALUES (?1, ?2, 'supersedes', 1.5, ?3)
                             ON CONFLICT(from_key, to_key, edge_type)
                             DO UPDATE SET weight = excluded.weight",
                            params![key, cand_key, now],
                        )?;
                        c.execute(
                            "UPDATE memories
                                SET status = 'superseded', superseded_by = ?2
                              WHERE key = ?1 AND status = 'active'",
                            params![cand_key, key],
                        )?;
                    }
                }

                // ── Contradiction detection ──────────────────────────────────
                // Only run if we have enough tokens to compare meaningfully.
                if new_tokens.len() >= 3 {
                    let mut cand_stmt = c.prepare(
                        "SELECT key, content FROM memories
                         WHERE kind = ?1
                           AND (scope IS ?2)
                           AND key != ?3
                           AND status = 'active'
                         LIMIT 30",
                    )?;
                    let candidates: Vec<(String, String)> = cand_stmt
                        .query_map(params![kind_clone, scope, key], |row| {
                            Ok((row.get::<_, String>(0)?, row.get::<_, String>(1)?))
                        })?
                        .filter_map(|r| r.ok())
                        .collect();

                    for (cand_key, cand_content) in candidates {
                        let cand_tokens = overlap_tokens(&cand_content);
                        if token_overlap_ratio(&new_tokens, &cand_tokens) > 0.5 {
                            // New memory supersedes the old one.
                            c.execute(
                                "INSERT INTO memory_edges
                                   (from_key, to_key, edge_type, weight, created_at)
                                 VALUES (?1, ?2, 'supersedes', 1.3, ?3)
                                 ON CONFLICT(from_key, to_key, edge_type)
                                 DO UPDATE SET weight = excluded.weight",
                                params![key, cand_key, now],
                            )?;
                            // **Phase 1 P2** — record the supersede pointer
                            // alongside flipping status. Lets memory_get
                            // expose `superseded_by` so callers can see
                            // *what* replaced this row, not just that it
                            // was retired. Older rows superseded before v22
                            // stay with NULL pointer; new ones get linked.
                            c.execute(
                                "UPDATE memories
                                 SET status = 'superseded', superseded_by = ?2
                                 WHERE key = ?1 AND status = 'active'",
                                params![cand_key, key],
                            )?;
                        }
                    }
                }

                Ok(())
            })
            .await
            .map_err(|e| Error::Backend(format!("memory_save: {e}")))?;
        Ok(())
    }

    async fn memory_get(&self, key: &str) -> Result<Option<MemoryRecord>> {
        let key = key.to_string();
        let now = now_secs();

        let row = self
            .conn
            .call(move |c| -> RusqliteResult<Option<MemoryRecord>> {
                let mut stmt = c.prepare(
                    "SELECT key, kind, content, tags, related_keys, scope,
                            created_at, updated_at, last_accessed_at, access_count,
                            importance, status, trigger_pattern, superseded_by
                     FROM memories WHERE key = ?1 AND status != 'tombstoned'",
                )?;
                let r = stmt
                    .query_row(params![key], |row| {
                        let tags_s: String = row.get(3)?;
                        let related_s: String = row.get(4)?;
                        Ok(MemoryRecord {
                            key: row.get(0)?,
                            kind: row.get(1)?,
                            content: row.get(2)?,
                            tags: parse_str_array(&tags_s),
                            related_keys: parse_str_array(&related_s),
                            scope: row.get(5)?,
                            created_at: row.get(6)?,
                            updated_at: row.get(7)?,
                            last_accessed_at: row.get(8)?,
                            access_count: row.get::<_, i64>(9)? as u64,
                            importance: row.get::<_, f64>(10).unwrap_or(0.5),
                            status: row
                                .get::<_, String>(11)
                                .unwrap_or_else(|_| "active".to_string()),
                            trigger_pattern: row.get::<_, Option<String>>(12)?,
                            superseded_by: row.get::<_, Option<String>>(13)?,
                        })
                    })
                    .ok();
                // Bump access stats — even if the SELECT didn't find anything,
                // UPDATE is a no-op so this is cheap and idempotent.
                if r.is_some() {
                    c.execute(
                        "UPDATE memories
                            SET access_count = access_count + 1,
                                last_accessed_at = ?2
                          WHERE key = ?1",
                        params![key, now],
                    )?;
                }
                Ok(r)
            })
            .await
            .map_err(|e| Error::Backend(format!("memory_get: {e}")))?;

        // Reflect the bump in the returned record so callers see fresh values.
        Ok(row.map(|mut r| {
            r.access_count = r.access_count.saturating_add(1);
            r.last_accessed_at = now;
            r
        }))
    }

    async fn memory_search(
        &self,
        query: &str,
        tags_any: &[String],
        limit: u32,
    ) -> Result<Vec<MemorySearchHit>> {
        let q = query.trim().to_string();
        if q.is_empty() {
            return Ok(Vec::new());
        }
        let fts_query = sanitise_fts_query(&q);
        let tags = tags_any.to_vec();
        let limit_i = limit as i64;
        let now = now_secs();

        let hits = self
            .conn
            .call(move |c| -> RusqliteResult<Vec<MemorySearchHit>> {
                // FTS5 first: get candidate rowids ranked by bm25.
                // Then JOIN back to memories for the full record.
                // Final ranking blends bm25 (lower=better → invert) with
                // recency + frequency, applied in Rust.
                let mut stmt = c.prepare(
                    "SELECT m.key, m.kind, m.content, m.tags, m.related_keys, m.scope,
                            m.created_at, m.updated_at, m.last_accessed_at, m.access_count,
                            bm25(memories_fts) AS bm25_score,
                            m.importance, m.status, m.trigger_pattern, m.superseded_by
                     FROM memories_fts
                     JOIN memories m ON m.rowid = memories_fts.rowid
                     WHERE memories_fts MATCH ?1
                       AND m.status = 'active'
                     ORDER BY bm25_score
                     LIMIT ?2",
                )?;
                let rows = stmt
                    .query_map(params![fts_query, limit_i * 4], |row| {
                        let tags_s: String = row.get(3)?;
                        let related_s: String = row.get(4)?;
                        let rec = MemoryRecord {
                            key: row.get(0)?,
                            kind: row.get(1)?,
                            content: row.get(2)?,
                            tags: parse_str_array(&tags_s),
                            related_keys: parse_str_array(&related_s),
                            scope: row.get(5)?,
                            created_at: row.get(6)?,
                            updated_at: row.get(7)?,
                            last_accessed_at: row.get(8)?,
                            access_count: row.get::<_, i64>(9)? as u64,
                            importance: row.get::<_, f64>(11).unwrap_or(0.5),
                            status: row
                                .get::<_, String>(12)
                                .unwrap_or_else(|_| "active".to_string()),
                            trigger_pattern: row.get::<_, Option<String>>(13)?,
                            superseded_by: row.get::<_, Option<String>>(14)?,
                        };
                        let bm25: f64 = row.get(10)?;
                        Ok((rec, bm25))
                    })?
                    .collect::<std::result::Result<Vec<_>, _>>()?;

                let mut hits: Vec<MemorySearchHit> = rows
                    .into_iter()
                    .filter(|(r, _)| tags.is_empty() || tags.iter().any(|t| r.tags.contains(t)))
                    .map(|(r, bm25)| {
                        // bm25 is negative (more negative = better match in SQLite).
                        // Convert to positive "match strength", then mix with our
                        // existing recency+frequency score.
                        let match_strength = (-bm25).max(0.0);
                        let score =
                            match_strength + memory_score(r.last_accessed_at, r.access_count, now, &r.kind);
                        MemorySearchHit { record: r, score }
                    })
                    .collect();

                // Intuition guardrail: FTS5 tokenisation can miss obvious "exact key"
                // queries (e.g. keys with separators like `_` / `.`). Always add an
                // exact-key fallback candidate so searching by key behaves predictably.
                let exact_key_row = {
                    let mut exact_stmt = c.prepare(
                        "SELECT key, kind, content, tags, related_keys, scope,
                                created_at, updated_at, last_accessed_at, access_count,
                                importance, status, trigger_pattern, superseded_by
                         FROM memories
                         WHERE key = ?1 COLLATE NOCASE
                           AND status = 'active'
                         LIMIT 1",
                    )?;
                    exact_stmt
                        .query_row(params![q], |row| {
                            let tags_s: String = row.get(3)?;
                            let related_s: String = row.get(4)?;
                            Ok(MemoryRecord {
                                key: row.get(0)?,
                                kind: row.get(1)?,
                                content: row.get(2)?,
                                tags: parse_str_array(&tags_s),
                                related_keys: parse_str_array(&related_s),
                                scope: row.get(5)?,
                                created_at: row.get(6)?,
                                updated_at: row.get(7)?,
                                last_accessed_at: row.get(8)?,
                                access_count: row.get::<_, i64>(9)? as u64,
                                importance: row.get::<_, f64>(10).unwrap_or(0.5),
                                status: row
                                    .get::<_, String>(11)
                                    .unwrap_or_else(|_| "active".to_string()),
                                trigger_pattern: row.get::<_, Option<String>>(12)?,
                                superseded_by: row.get::<_, Option<String>>(13)?,
                            })
                        })
                        .ok()
                };
                if let Some(rec) = exact_key_row {
                    let tags_match = tags.is_empty() || tags.iter().any(|t| rec.tags.contains(t));
                    let exists = hits.iter().any(|h| h.record.key == rec.key);
                    if tags_match && !exists {
                        // Keep exact-key hits above fuzzy matches.
                        let score =
                            1_000_000.0 + memory_score(rec.last_accessed_at, rec.access_count, now, &rec.kind);
                        hits.push(MemorySearchHit { record: rec, score });
                    }
                }

                hits.sort_by(|a, b| {
                    b.score
                        .partial_cmp(&a.score)
                        .unwrap_or(std::cmp::Ordering::Equal)
                });
                hits.truncate(limit_i as usize);
                Ok(hits)
            })
            .await
            .map_err(|e| Error::Backend(format!("memory_search: {e}")))?;
        Ok(hits)
    }

    async fn memory_search_hybrid(
        &self,
        query: &str,
        tags_any: &[String],
        limit: u32,
        k: f64,
        expand_top: u32,
    ) -> Result<Vec<MemorySearchHit>> {
        use std::collections::HashMap;

        // ── Step 1: FTS5 search (list A) ──────────────────────────────────────
        // Fetch 4× limit so graph expansion has candidates to work with.
        let fts_hits = self
            .memory_search(query, tags_any, limit.saturating_mul(4).max(40))
            .await?;

        if fts_hits.is_empty() {
            return Ok(Vec::new());
        }

        // ── Step 2: Graph expansion (list B) ──────────────────────────────────
        // For each of the top `expand_top` FTS5 hits, fetch direct neighbors.
        // Weight each neighbor by edge.weight × neighbour.importance.
        let expand_n = expand_top.min(fts_hits.len() as u32) as usize;
        let mut graph_scores: HashMap<String, f64> = HashMap::new();

        for hit in fts_hits.iter().take(expand_n) {
            let edges = self
                .memory_neighbors(&hit.record.key)
                .await
                .unwrap_or_default();
            for edge in edges {
                // Neighbour key is the other end of the edge
                let neighbour_key = if edge.from_key == hit.record.key {
                    edge.to_key.clone()
                } else {
                    edge.from_key.clone()
                };
                // Skip if this key is already in FTS5 results (we'll pick it up via RRF)
                let already_in_fts = fts_hits.iter().any(|h| h.record.key == neighbour_key);
                // Score = edge weight × fts hit importance (the seed's importance)
                let edge_score = edge.weight * hit.record.importance;
                let e = graph_scores.entry(neighbour_key).or_insert(0.0);
                *e += edge_score; // accumulate across multiple seed paths
                let _ = already_in_fts; // keep both — RRF handles dedup via rank
            }
        }

        // Fetch full records for graph candidates not already in FTS list
        let mut graph_records: Vec<(String, f64)> = graph_scores.into_iter().collect();
        // Sort graph candidates by accumulated score (higher = more relevant neighbor)
        graph_records.sort_by(|a, b| b.1.partial_cmp(&a.1).unwrap_or(std::cmp::Ordering::Equal));

        // Collect full MemoryRecords for graph list
        let mut graph_hits: Vec<MemorySearchHit> = Vec::new();
        for (key, gscore) in &graph_records {
            if let Ok(Some(rec)) = self.memory_get(key).await {
                // Only include active memories
                if rec.status == "active" {
                    graph_hits.push(MemorySearchHit {
                        record: rec,
                        score: *gscore,
                    });
                }
            }
        }

        // ── Step 3: RRF fusion ─────────────────────────────────────────────────
        // RRF score(d) = Σ_list 1/(k + rank_in_list)
        // k=60 is the standard constant (Robertson et al.)
        let rrf_k = k.max(1.0);
        let mut rrf_scores: HashMap<String, f64> = HashMap::new();

        // List A: FTS5 results
        for (rank, hit) in fts_hits.iter().enumerate() {
            let key = hit.record.key.clone();
            *rrf_scores.entry(key).or_insert(0.0) += 1.0 / (rrf_k + rank as f64 + 1.0);
        }
        // List B: Graph neighbor results
        for (rank, hit) in graph_hits.iter().enumerate() {
            let key = hit.record.key.clone();
            *rrf_scores.entry(key).or_insert(0.0) += 1.0 / (rrf_k + rank as f64 + 1.0);
        }

        // ── Step 4: Build final result set ────────────────────────────────────
        // Collect all unique MemoryRecords (prefer FTS5 record since it was freshly bumped)
        let mut all_records: HashMap<String, MemoryRecord> = HashMap::new();
        for hit in fts_hits {
            all_records
                .entry(hit.record.key.clone())
                .or_insert(hit.record);
        }
        for hit in graph_hits {
            all_records
                .entry(hit.record.key.clone())
                .or_insert(hit.record);
        }

        let mut merged: Vec<MemorySearchHit> = rrf_scores
            .into_iter()
            .filter_map(|(key, rrf_score)| {
                all_records.remove(&key).map(|record| MemorySearchHit {
                    score: rrf_score,
                    record,
                })
            })
            .collect();

        merged.sort_by(|a, b| {
            b.score
                .partial_cmp(&a.score)
                .unwrap_or(std::cmp::Ordering::Equal)
        });
        merged.truncate(limit as usize);
        Ok(merged)
    }

    async fn list_memories(
        &self,
        kind: Option<&str>,
        sort: MemoryListSort,
        limit: u32,
    ) -> Result<Vec<MemoryRecord>> {
        self.list_memories_in_scope("", kind, sort, limit).await
    }

    async fn list_memories_in_scope(
        &self,
        ctx: &str,
        kind: Option<&str>,
        sort: MemoryListSort,
        limit: u32,
    ) -> Result<Vec<MemoryRecord>> {
        let kind = kind.map(|s| s.to_string());
        let ctx = ctx.to_string();
        let limit_i = limit as i64;
        let order = match sort {
            MemoryListSort::Recent => "last_accessed_at DESC".to_string(),
            MemoryListSort::Frequent => "access_count DESC, last_accessed_at DESC".to_string(),
            MemoryListSort::Newest => "created_at DESC".to_string(),
            // PUCT-inspired: importance / (1 + age_days_since_update) DESC
            // This surfaces high-importance, recently-updated memories first.
            MemoryListSort::ByImportance => {
                "(importance / (1.0 + (CAST(strftime('%s','now') AS REAL) - updated_at) / 86400.0)) DESC, importance DESC".to_string()
            }
        };

        let rows = self
            .conn
            .call(move |c| -> RusqliteResult<Vec<MemoryRecord>> {
                // Bind exactly 3 params unconditionally — `?3` (the scope ctx)
                // is NULL when the caller didn't supply one, and the WHERE
                // clause is written so a NULL `?3` short-circuits to "all
                // records pass the scope filter". v0.7.0 had two SQL variants
                // (one with `?3`, one without) but always bound 3 params,
                // which raised "Got 3, needed 2" on the empty-ctx path
                // (lesson_memory_list_scope_query_bug).
                //
                // When `?3` is provided, a record matches if:
                //   - it's global/unscoped (scope IS NULL or 'global'), OR
                //   - its scope equals `?3` exactly, OR
                //   - it's project-scoped (`scope` begins with `project:`) and
                //     `?3` is a path under that project.
                let sql = format!(
                    "SELECT key, kind, content, tags, related_keys, scope,
                            created_at, updated_at, last_accessed_at, access_count,
                            importance, status, trigger_pattern, superseded_by
                     FROM memories
                     WHERE (?1 IS NULL OR kind = ?1)
                       AND status = 'active'
                       AND (?3 IS NULL
                            OR scope IS NULL
                            OR scope = 'global'
                            OR scope = ?3
                            OR (scope LIKE 'project:%' AND ?3 LIKE (SUBSTR(scope, 9) || '%')))
                     ORDER BY {order}
                     LIMIT ?2"
                );
                let mut stmt = c.prepare(&sql)?;
                let ctx_param: Option<&str> = if ctx.is_empty() { None } else { Some(&ctx) };
                let rows = stmt
                    .query_map(params![kind, limit_i, ctx_param], |row| {
                        let tags_s: String = row.get(3)?;
                        let related_s: String = row.get(4)?;
                        Ok(MemoryRecord {
                            key: row.get(0)?,
                            kind: row.get(1)?,
                            content: row.get(2)?,
                            tags: parse_str_array(&tags_s),
                            related_keys: parse_str_array(&related_s),
                            scope: row.get(5)?,
                            created_at: row.get(6)?,
                            updated_at: row.get(7)?,
                            last_accessed_at: row.get(8)?,
                            access_count: row.get::<_, i64>(9)? as u64,
                            importance: row.get::<_, f64>(10).unwrap_or(0.5),
                            status: row
                                .get::<_, String>(11)
                                .unwrap_or_else(|_| "active".to_string()),
                            trigger_pattern: row.get::<_, Option<String>>(12)?,
                            superseded_by: row.get::<_, Option<String>>(13)?,
                        })
                    })?
                    .collect::<std::result::Result<Vec<_>, _>>()?;
                Ok(rows)
            })
            .await
            .map_err(|e| Error::Backend(format!("list_memories_in_scope: {e}")))?;
        Ok(rows)
    }

    async fn memory_link(
        &self,
        from_key: &str,
        to_key: &str,
        edge_type: &str,
        weight: f64,
    ) -> Result<()> {
        let from = from_key.to_string();
        let to = to_key.to_string();
        let etype = edge_type.to_string();
        // If the caller passed the sentinel default (1.0), auto-upgrade to
        // the canonical weight for this edge type so callers don't have to
        // remember the weight table.
        let effective_weight = if (weight - 1.0).abs() < f64::EPSILON {
            weight_for_edge_type(&etype)
        } else {
            weight.clamp(0.0, 2.0) // allow >1.0 for temporal-bonus pre-applied weights
        };
        let now = now_secs();
        self.conn
            .call(move |c| -> RusqliteResult<()> {
                c.execute(
                    "INSERT INTO memory_edges (from_key, to_key, edge_type, weight, created_at)
                     VALUES (?1, ?2, ?3, ?4, ?5)
                     ON CONFLICT(from_key, to_key, edge_type) DO UPDATE SET
                        weight = excluded.weight",
                    params![from, to, etype, effective_weight, now],
                )?;
                Ok(())
            })
            .await
            .map_err(|e| Error::Backend(format!("memory_link: {e}")))?;
        Ok(())
    }

    async fn memory_neighbors(&self, key: &str) -> Result<Vec<MemoryEdge>> {
        let key = key.to_string();
        let edges = self
            .conn
            .call(move |c| -> RusqliteResult<Vec<MemoryEdge>> {
                let mut stmt = c.prepare(
                    "SELECT from_key, to_key, edge_type, weight FROM memory_edges
                     WHERE from_key = ?1 OR to_key = ?1
                     ORDER BY weight DESC",
                )?;
                let rows = stmt
                    .query_map(params![key], |row| {
                        Ok(MemoryEdge {
                            from_key: row.get(0)?,
                            to_key: row.get(1)?,
                            edge_type: row.get(2)?,
                            weight: row.get(3)?,
                        })
                    })?
                    .collect::<std::result::Result<Vec<_>, _>>()?;
                Ok(rows)
            })
            .await
            .map_err(|e| Error::Backend(format!("memory_neighbors: {e}")))?;
        Ok(edges)
    }

    async fn memory_neighbors_bfs(
        &self,
        start_key: &str,
        depth: u8,
        decay_factor: f64,
        min_energy: f64,
    ) -> Result<Vec<(MemoryEdge, f64)>> {
        use std::collections::{HashMap, VecDeque};

        let start = start_key.to_string();
        let max_depth = depth.min(6); // hard cap to avoid O(n^d) blowup
        let decay = decay_factor.clamp(0.1, 1.0);
        let threshold = min_energy.max(0.001);

        // Fetch all edges once and work in-memory — DB is local SQLite, fits RAM.
        let all_edges = self
            .conn
            .call(move |c| -> RusqliteResult<Vec<MemoryEdge>> {
                let mut stmt =
                    c.prepare("SELECT from_key, to_key, edge_type, weight FROM memory_edges")?;
                let rows = stmt
                    .query_map([], |row| {
                        Ok(MemoryEdge {
                            from_key: row.get(0)?,
                            to_key: row.get(1)?,
                            edge_type: row.get(2)?,
                            weight: row.get(3)?,
                        })
                    })?
                    .collect::<std::result::Result<Vec<_>, _>>()?;
                Ok(rows)
            })
            .await
            .map_err(|e| Error::Backend(format!("memory_neighbors_bfs fetch: {e}")))?;

        // BFS with energy tracking (AiOT GraphMemoryBridge "ignite" pattern).
        // visited: key → best energy seen so far (we propagate max).
        let mut visited: HashMap<String, f64> = HashMap::new();
        visited.insert(start.clone(), 1.0);

        // queue: (current_key, remaining_depth, energy_at_this_node)
        let mut queue: VecDeque<(String, u8, f64)> = VecDeque::new();
        queue.push_back((start.clone(), max_depth, 1.0));

        // result: (edge, propagated_energy) — collect edges we traverse
        let mut result: Vec<(MemoryEdge, f64)> = Vec::new();

        while let Some((current, hops_left, energy)) = queue.pop_front() {
            if hops_left == 0 {
                continue;
            }
            // Find edges incident to `current`
            for edge in &all_edges {
                let (neighbour, is_outbound) = if edge.from_key == current {
                    (edge.to_key.clone(), true)
                } else if edge.to_key == current {
                    (edge.from_key.clone(), false)
                } else {
                    continue;
                };
                // Strict cycle guard: never revisit a node already in the queue.
                // This prevents loops (e.g. A→B→A) from appearing in results.
                if visited.contains_key(&neighbour) {
                    continue;
                }
                // Energy propagation:
                //   causal outbound edges get temporal bonus ×1.2
                //   inbound causal edges don't get the bonus (information flows forward)
                let bonus = if is_outbound {
                    temporal_bonus(&edge.edge_type)
                } else {
                    1.0
                };
                let next_energy = energy * edge.weight * bonus * decay;
                if next_energy < threshold {
                    continue;
                }
                visited.insert(neighbour.clone(), next_energy);
                result.push((edge.clone(), next_energy));
                queue.push_back((neighbour, hops_left - 1, next_energy));
            }
        }

        // Sort by descending energy (highest-energy = most relevant first)
        result.sort_by(|a, b| b.1.partial_cmp(&a.1).unwrap_or(std::cmp::Ordering::Equal));
        // Deduplicate: keep highest-energy occurrence of each (from, to, type) triple
        let mut seen = std::collections::HashSet::new();
        result.retain(|(e, _)| {
            seen.insert((e.from_key.clone(), e.to_key.clone(), e.edge_type.clone()))
        });
        Ok(result)
    }

    async fn memory_delete(&self, key: &str) -> Result<bool> {
        let key = key.to_string();
        let now = now_secs();
        let n = self
            .conn
            .call(move |c| -> RusqliteResult<usize> {
                let tx = c.unchecked_transaction()?;
                // Soft delete (tombstone): keep the row with status='tombstoned'
                // and bump updated_at so the deletion propagates across
                // `agent-bridge sync`. NewerWins import on the remote side sees
                // the bumped timestamp and refuses to revive from stale jsonl,
                // which used to be the bug — hard DELETE here meant the row
                // re-imported on the next sync round and "undeleted" itself.
                // Read-side filters in memory_get/search/list already exclude
                // status != 'active', so tombstoned rows are invisible to users.
                // Tombstone GC (true row removal after a quiet period) is a
                // future Phase 2 task — for now tombstones accumulate. Manual
                // purge: `DELETE FROM memories WHERE status='tombstoned' AND
                // updated_at < ?` via sqlite3 CLI.
                let n = tx.execute(
                    "UPDATE memories
                        SET status = 'tombstoned',
                            updated_at = ?2
                      WHERE key = ?1
                        AND status != 'tombstoned'",
                    params![key, now],
                )?;
                // Mirror the previous ON DELETE CASCADE on memory_coactivation:
                // a tombstoned node shouldn't keep pulling in synaptic neighbors.
                tx.execute(
                    "DELETE FROM memory_coactivation
                       WHERE key_a = ?1 OR key_b = ?1",
                    params![key],
                )?;
                tx.commit()?;
                Ok(n)
            })
            .await
            .map_err(|e| Error::Backend(format!("memory_delete: {e}")))?;
        Ok(n > 0)
    }

    async fn memory_decay_importance(
        &self,
        half_life_days: f64,
        archive_threshold: f64,
    ) -> Result<u64> {
        let now = now_secs();
        let archived = self
            .conn
            .call(move |c| -> RusqliteResult<u64> {
                // Fetch all active memories with their updated_at + current importance.
                let mut stmt = c.prepare(
                    "SELECT key, importance, updated_at FROM memories
                     WHERE status = 'active'",
                )?;
                let candidates: Vec<(String, f64, i64)> = stmt
                    .query_map([], |row| {
                        Ok((
                            row.get::<_, String>(0)?,
                            row.get::<_, f64>(1)?,
                            row.get::<_, i64>(2)?,
                        ))
                    })?
                    .filter_map(|r| r.ok())
                    .collect();

                let tx = c.unchecked_transaction()?;
                let mut archived_count = 0u64;
                for (key, importance, updated_at) in candidates {
                    let age_days = ((now - updated_at).max(0) as f64) / 86_400.0;
                    // importance × 0.5^(age_days / half_life_days)
                    let new_importance = importance * (0.5f64).powf(age_days / half_life_days);
                    if new_importance < archive_threshold {
                        tx.execute(
                            "UPDATE memories SET importance = ?2, status = 'archived'
                             WHERE key = ?1",
                            params![key, new_importance],
                        )?;
                        archived_count += 1;
                    } else {
                        tx.execute(
                            "UPDATE memories SET importance = ?2 WHERE key = ?1",
                            params![key, new_importance],
                        )?;
                    }
                }
                tx.commit()?;
                Ok(archived_count)
            })
            .await
            .map_err(|e| Error::Backend(format!("memory_decay_importance: {e}")))?;
        Ok(archived)
    }

    async fn memory_compact(&self, policy: CompactPolicy) -> Result<Vec<String>> {
        let CompactPolicy {
            min_uses,
            older_than_secs,
            dry_run,
        } = policy;
        let cutoff_lat = older_than_secs.map(|s| now_secs() - s);
        let min_uses_i = min_uses.map(|n| n as i64);
        // v0.7.1 fix (lesson_compact_or_logic_kills_new_memories): newly saved
        // memories have access_count=0 and would match `access_count < 2` on
        // the very next compact pass — so the v0.7 PreCompact curator+Stop-hook
        // pipeline was deleting memories within seconds of saving them.
        //
        // Two-part fix:
        //   1. OR → AND between the access-count and recency thresholds:
        //      a row is only stale when *both* signals say so (low usage AND
        //      not touched recently). Either condition alone is no longer
        //      enough.
        //   2. Hard-coded GRACE_SECS protects records created in the last
        //      hour regardless of policy — defence-in-depth against hooks
        //      that fire faster than memory has time to accumulate hits.
        const GRACE_SECS: i64 = 3600;
        let grace_cutoff = now_secs() - GRACE_SECS;

        let keys = self
            .conn
            .call(move |c| -> RusqliteResult<Vec<String>> {
                let mut stmt = c.prepare(
                    "SELECT key FROM memories
                     WHERE created_at < ?3
                       AND (?1 IS NOT NULL OR ?2 IS NOT NULL)
                       AND (?1 IS NULL OR access_count < ?1)
                       AND (?2 IS NULL OR last_accessed_at < ?2)",
                )?;
                let keys: Vec<String> = stmt
                    .query_map(params![min_uses_i, cutoff_lat, grace_cutoff], |r| {
                        r.get::<_, String>(0)
                    })?
                    .collect::<std::result::Result<Vec<_>, _>>()?;

                if !dry_run && !keys.is_empty() {
                    let tx = c.unchecked_transaction()?;
                    for k in &keys {
                        tx.execute("DELETE FROM memories WHERE key = ?1", params![k])?;
                    }
                    tx.commit()?;
                }
                Ok(keys)
            })
            .await
            .map_err(|e| Error::Backend(format!("memory_compact: {e}")))?;
        Ok(keys)
    }

    async fn memory_export(
        &self,
        filter: &MemoryExportFilter,
        out_path: &std::path::Path,
    ) -> Result<MemoryExportResult> {
        let kind = filter.kind.clone();
        let tags = filter.tags_any.clone();
        let since = filter.since_ts;

        let rows: Vec<MemoryRecord> = self
            .conn
            .call(move |c| -> RusqliteResult<Vec<MemoryRecord>> {
                let mut stmt = c.prepare(
                    "SELECT key, kind, content, tags, related_keys, scope,
                            created_at, updated_at, last_accessed_at, access_count,
                            importance, status, trigger_pattern, superseded_by
                     FROM memories
                     WHERE (?1 IS NULL OR kind = ?1)
                       AND (?2 IS NULL OR updated_at >= ?2)
                     ORDER BY created_at ASC",
                )?;
                let rows = stmt
                    .query_map(params![kind, since], |row| {
                        let tags_s: String = row.get(3)?;
                        let related_s: String = row.get(4)?;
                        Ok(MemoryRecord {
                            key: row.get(0)?,
                            kind: row.get(1)?,
                            content: row.get(2)?,
                            tags: parse_str_array(&tags_s),
                            related_keys: parse_str_array(&related_s),
                            scope: row.get(5)?,
                            created_at: row.get(6)?,
                            updated_at: row.get(7)?,
                            last_accessed_at: row.get(8)?,
                            access_count: row.get::<_, i64>(9)? as u64,
                            importance: row.get::<_, f64>(10).unwrap_or(0.5),
                            status: row
                                .get::<_, String>(11)
                                .unwrap_or_else(|_| "active".to_string()),
                            trigger_pattern: row.get::<_, Option<String>>(12)?,
                            superseded_by: row.get::<_, Option<String>>(13)?,
                        })
                    })?
                    .collect::<std::result::Result<Vec<_>, _>>()?;
                Ok(rows)
            })
            .await
            .map_err(|e| Error::Backend(format!("memory_export query: {e}")))?;

        // Tag intersection done in Rust (JSON column).
        let filtered: Vec<MemoryRecord> = rows
            .into_iter()
            .filter(|r| match &tags {
                Some(want) if !want.is_empty() => want.iter().any(|t| r.tags.contains(t)),
                _ => true,
            })
            .collect();

        if let Some(parent) = out_path.parent() {
            tokio::fs::create_dir_all(parent)
                .await
                .map_err(|e| Error::Backend(format!("mkdir {parent:?}: {e}")))?;
        }
        let mut buf = String::new();
        for r in &filtered {
            buf.push_str(&serde_json::to_string(r)?);
            buf.push('\n');
        }
        tokio::fs::write(out_path, buf)
            .await
            .map_err(|e| Error::Backend(format!("write {out_path:?}: {e}")))?;

        let edges_written = if let Some(ref ep) = filter.edges_out_path {
            let keys: std::collections::HashSet<String> =
                filtered.iter().map(|r| r.key.clone()).collect();
            self.export_edges_for_key_set(&keys, ep.as_path()).await?
        } else {
            0
        };

        Ok(MemoryExportResult {
            memories_written: filtered.len() as u64,
            edges_written,
        })
    }

    async fn memory_import(
        &self,
        in_path: &std::path::Path,
        policy: ImportConflictPolicy,
        edges_path: Option<&std::path::Path>,
    ) -> Result<ImportReport> {
        let bytes = tokio::fs::read(in_path)
            .await
            .map_err(|e| Error::Backend(format!("read {in_path:?}: {e}")))?;
        let text = String::from_utf8_lossy(&bytes).into_owned();

        // Parse first; we apply the conflict policy in a single transaction
        // for atomicity (a malformed line shouldn't half-import).
        let mut malformed_mem = 0u64;
        let mut parsed: Vec<MemoryRecord> = Vec::new();
        for line in text.lines() {
            if line.trim().is_empty() {
                continue;
            }
            match serde_json::from_str::<MemoryRecord>(line) {
                Ok(r) => parsed.push(r),
                Err(_) => malformed_mem += 1,
            }
        }

        let clamped_contents: Vec<String> = parsed
            .iter()
            .map(|r| clamp(&r.content, MEMORY_CONTENT_CAP))
            .collect();

        // Pre-flight (read-only): figure out which keys already exist so we
        // can decide each row's action *before* paying for embeddings. The
        // typical sync.sh flow re-imports an unchanged JSONL with Skip
        // policy — without this gate, every Stop hook spawned a fresh
        // process that batch-embedded 100s of rows and then threw the
        // results away, cold-starting fastembed each time.
        let existing_uat: std::collections::HashMap<String, i64> = if parsed.is_empty() {
            std::collections::HashMap::new()
        } else {
            let keys: Vec<String> = parsed.iter().map(|r| r.key.clone()).collect();
            self.conn
                .call(move |c| -> RusqliteResult<std::collections::HashMap<String, i64>> {
                    let mut map = std::collections::HashMap::with_capacity(keys.len());
                    // Chunk to stay under SQLite's default max parameter limit (999).
                    for chunk in keys.chunks(500) {
                        let placeholders = std::iter::repeat("?")
                            .take(chunk.len())
                            .collect::<Vec<_>>()
                            .join(",");
                        let sql = format!(
                            "SELECT key, updated_at FROM memories WHERE key IN ({placeholders})"
                        );
                        let mut stmt = c.prepare(&sql)?;
                        let mut rows = stmt.query(rusqlite::params_from_iter(chunk.iter()))?;
                        while let Some(row) = rows.next()? {
                            let k: String = row.get(0)?;
                            let u: i64 = row.get(1)?;
                            map.insert(k, u);
                        }
                    }
                    Ok(map)
                })
                .await
                .map_err(|e| Error::Backend(format!("memory_import preflight: {e}")))?
        };

        let actions = plan_import_actions(&parsed, &existing_uat, policy);

        // Embed only rows we're actually going to persist. When everything
        // is Skip (the common sync-no-op case), we never touch the embedding
        // backend → fastembed never cold-starts.
        let to_embed_idx: Vec<usize> = actions
            .iter()
            .enumerate()
            .filter(|(_, a)| !matches!(a, ImportAction::Skip))
            .map(|(i, _)| i)
            .collect();
        let mut embeddings: Vec<Option<Vec<u8>>> = vec![None; parsed.len()];
        if !to_embed_idx.is_empty() {
            let to_embed_refs: Vec<&str> = to_embed_idx
                .iter()
                .map(|&i| clamped_contents[i].as_str())
                .collect();
            let backend = crate::embedding::default_backend();
            let vecs = backend.embed_batch(&to_embed_refs);
            for (k, &i) in to_embed_idx.iter().enumerate() {
                embeddings[i] = Some(crate::vector::encode_embedding(&vecs[k]));
            }
        }

        let parsed_for_tx = parsed;
        let clamped_for_tx = clamped_contents;
        let actions_for_tx = actions;
        let embeddings_for_tx = embeddings;
        let mut report = self
            .conn
            .call(move |c| -> RusqliteResult<ImportReport> {
                let mut report = ImportReport::default();
                let tx = c.unchecked_transaction()?;
                for (idx, r) in parsed_for_tx.iter().enumerate() {
                    let action = actions_for_tx[idx];
                    let tags_s = serde_json::to_string(&r.tags).unwrap_or_else(|_| "[]".into());
                    let related_s =
                        serde_json::to_string(&r.related_keys).unwrap_or_else(|_| "[]".into());
                    let content = &clamped_for_tx[idx];
                    let imp = if (r.importance - 0.5).abs() > 1e-9 {
                        r.importance
                    } else {
                        importance_for_kind(&r.kind)
                    };
                    let stat = if r.status.is_empty() {
                        "active"
                    } else {
                        r.status.as_str()
                    };
                    let trig = r
                        .trigger_pattern
                        .clone()
                        .map(|s| s.trim().to_string())
                        .filter(|s| !s.is_empty());
                    match action {
                        ImportAction::Insert => {
                            let embedding_bytes = embeddings_for_tx[idx]
                                .as_deref()
                                .unwrap_or(&[]);
                            tx.execute(
                                "INSERT INTO memories
                                   (key, kind, content, tags, related_keys, scope,
                                    created_at, updated_at, last_accessed_at, access_count,
                                    importance, status, trigger_pattern, embedding)
                                 VALUES (?1, ?2, ?3, ?4, ?5, ?6, ?7, ?8, ?9, ?10, ?11, ?12, ?13, ?14)",
                                params![
                                    r.key,
                                    r.kind,
                                    content,
                                    tags_s,
                                    related_s,
                                    r.scope,
                                    r.created_at,
                                    r.updated_at,
                                    r.last_accessed_at,
                                    r.access_count as i64,
                                    imp,
                                    stat,
                                    trig,
                                    embedding_bytes,
                                ],
                            )?;
                            report.inserted += 1;
                        }
                        ImportAction::Update => {
                            let embedding_bytes = embeddings_for_tx[idx]
                                .as_deref()
                                .unwrap_or(&[]);
                            tx.execute(
                                "UPDATE memories SET
                                    kind = ?2, content = ?3, tags = ?4, related_keys = ?5,
                                    scope = ?6, updated_at = ?7, last_accessed_at = ?8,
                                    access_count = ?9, importance = ?10, status = ?11,
                                    trigger_pattern = ?12, embedding = ?13
                                 WHERE key = ?1",
                                params![
                                    r.key,
                                    r.kind,
                                    content,
                                    tags_s,
                                    related_s,
                                    r.scope,
                                    r.updated_at,
                                    r.last_accessed_at,
                                    r.access_count as i64,
                                    imp,
                                    stat,
                                    trig,
                                    embedding_bytes,
                                ],
                            )?;
                            report.updated += 1;
                        }
                        ImportAction::Skip => {
                            report.skipped += 1;
                        }
                    }
                }
                tx.commit()?;
                Ok(report)
            })
            .await
            .map_err(|e| Error::Backend(format!("memory_import tx: {e}")))?;

        report.malformed += malformed_mem;
        if let Some(ep) = edges_path {
            let (u, m) = self.import_edges_jsonl(ep).await?;
            report.edges_upserted = u;
            report.edges_malformed = m;
        }
        Ok(report)
    }

    async fn memory_stats(&self) -> Result<MemoryStats> {
        let stats = self
            .conn
            .call(move |c| -> RusqliteResult<MemoryStats> {
                // 0. Approximate DB size via SQLite page pragmas.
                let page_count: i64 = c
                    .query_row("PRAGMA page_count", [], |r| r.get(0))
                    .unwrap_or(0);
                let page_size: i64 = c
                    .query_row("PRAGMA page_size", [], |r| r.get(0))
                    .unwrap_or(4096);
                let db_size_bytes: Option<u64> = if page_count > 0 {
                    Some((page_count * page_size) as u64)
                } else {
                    None
                };

                // 1. Counts by status.
                let mut counts_by_status: std::collections::HashMap<String, u64> =
                    std::collections::HashMap::new();
                {
                    let mut stmt =
                        c.prepare("SELECT status, COUNT(*) FROM memories GROUP BY status")?;
                    let rows = stmt.query_map([], |row| {
                        Ok((row.get::<_, String>(0)?, row.get::<_, i64>(1)? as u64))
                    })?;
                    for r in rows.flatten() {
                        counts_by_status.insert(r.0, r.1);
                    }
                }

                // 2. Counts by kind (active only), top 20.
                let mut counts_by_kind: Vec<(String, u64)> = Vec::new();
                {
                    let mut stmt = c.prepare(
                        "SELECT kind, COUNT(*) AS n FROM memories
                         WHERE status = 'active'
                         GROUP BY kind
                         ORDER BY n DESC
                         LIMIT 20",
                    )?;
                    let rows = stmt.query_map([], |row| {
                        Ok((row.get::<_, String>(0)?, row.get::<_, i64>(1)? as u64))
                    })?;
                    for r in rows.flatten() {
                        counts_by_kind.push(r);
                    }
                }

                // 3. Edge count.
                let edge_count: u64 = c
                    .query_row("SELECT COUNT(*) FROM memory_edges", [], |r| {
                        r.get::<_, i64>(0)
                    })
                    .unwrap_or(0) as u64;

                // 4. Oldest / newest created_at.
                let (oldest_created_at, newest_created_at): (Option<i64>, Option<i64>) = c
                    .query_row(
                        "SELECT MIN(created_at), MAX(created_at) FROM memories",
                        [],
                        |r| Ok((r.get::<_, Option<i64>>(0)?, r.get::<_, Option<i64>>(1)?)),
                    )
                    .unwrap_or((None, None));

                // 5. Average importance (active).
                let avg_importance_active: f64 = c
                    .query_row(
                        "SELECT AVG(importance) FROM memories WHERE status = 'active'",
                        [],
                        |r| r.get::<_, Option<f64>>(0),
                    )
                    .unwrap_or(None)
                    .unwrap_or(0.0);

                // 6. Top tags (active memories; tags stored as JSON arrays).
                let mut tag_counts: std::collections::HashMap<String, u64> =
                    std::collections::HashMap::new();
                {
                    let mut stmt =
                        c.prepare("SELECT tags FROM memories WHERE status = 'active'")?;
                    let rows = stmt.query_map([], |row| row.get::<_, String>(0))?;
                    for tags_s in rows.flatten() {
                        for tag in parse_str_array(&tags_s) {
                            *tag_counts.entry(tag).or_default() += 1;
                        }
                    }
                }
                let mut top_tags: Vec<(String, u64)> = tag_counts.into_iter().collect();
                top_tags.sort_by(|a, b| b.1.cmp(&a.1));
                top_tags.truncate(15);

                Ok(MemoryStats {
                    counts_by_status,
                    counts_by_kind,
                    edge_count,
                    oldest_created_at,
                    newest_created_at,
                    avg_importance_active,
                    top_tags,
                    db_size_bytes,
                })
            })
            .await
            .map_err(|e| Error::Backend(format!("memory_stats: {e}")))?;

        Ok(stats)
    }

    // ─── v12: semantic vector search ────────────────────────────────────

    async fn memory_search_semantic(
        &self,
        query: &str,
        limit: u32,
        threshold: f32,
    ) -> Result<Vec<MemorySearchHit>> {
        if query.trim().is_empty() {
            return Ok(Vec::new());
        }
        let query_vec = crate::vector::embed_text(query);
        let limit_usize = limit as usize;
        let now = now_secs();

        let rows = self
            .conn
            .call(move |c| -> RusqliteResult<Vec<(MemoryRecord, Vec<u8>)>> {
                let mut stmt = c.prepare(
                    "SELECT key, kind, content, tags, related_keys, scope,
                            created_at, updated_at, last_accessed_at, access_count,
                            importance, status, trigger_pattern, superseded_by, embedding
                     FROM memories
                     WHERE status = 'active' AND embedding IS NOT NULL",
                )?;
                let rows = stmt
                    .query_map([], |row| {
                        let tags_s: String = row.get(3)?;
                        let related_s: String = row.get(4)?;
                        let rec = MemoryRecord {
                            key: row.get(0)?,
                            kind: row.get(1)?,
                            content: row.get(2)?,
                            tags: parse_str_array(&tags_s),
                            related_keys: parse_str_array(&related_s),
                            scope: row.get(5)?,
                            created_at: row.get(6)?,
                            updated_at: row.get(7)?,
                            last_accessed_at: row.get(8)?,
                            access_count: row.get::<_, i64>(9)? as u64,
                            importance: row.get::<_, f64>(10).unwrap_or(0.5),
                            status: row
                                .get::<_, String>(11)
                                .unwrap_or_else(|_| "active".to_string()),
                            trigger_pattern: row.get::<_, Option<String>>(12)?,
                            superseded_by: row.get::<_, Option<String>>(13)?,
                        };
                        let emb_bytes: Vec<u8> = row.get(14)?;
                        Ok((rec, emb_bytes))
                    })?
                    .collect::<std::result::Result<Vec<_>, _>>()?;
                Ok(rows)
            })
            .await
            .map_err(|e| Error::Backend(format!("memory_search_semantic: {e}")))?;

        let mut hits: Vec<MemorySearchHit> = rows
            .into_iter()
            .filter_map(|(rec, emb_bytes)| {
                let stored_vec = crate::vector::decode_embedding(&emb_bytes);
                if stored_vec.is_empty() {
                    return None;
                }
                let cosine = crate::vector::cosine_similarity(&query_vec, &stored_vec);
                if cosine < threshold {
                    return None;
                }
                // Blend cosine similarity with recency / importance bonus.
                let score = cosine as f64
                    + 0.2 * rec.importance
                    + 0.1 * memory_score(rec.last_accessed_at, rec.access_count, now, &rec.kind);
                Some(MemorySearchHit { record: rec, score })
            })
            .collect();

        hits.sort_by(|a, b| {
            b.score
                .partial_cmp(&a.score)
                .unwrap_or(std::cmp::Ordering::Equal)
        });
        hits.truncate(limit_usize);
        Ok(hits)
    }

    /// v21 α — record co-activation pairs from a single search result.
    ///
    /// All ordered pairs (i, j) with key_i < key_j (lex normalized) get
    /// UPSERTed. ctx_centroid (when provided) blends into the stored BLOB
    /// via online rolling-mean: `new = (count * old + new_contrib) / (count+1)`.
    /// Fail-soft: errors logged but never propagated as the caller is
    /// `memory_search` and we don't want trace writes breaking search.
    async fn record_coactivation(
        &self,
        keys: &[String],
        ctx_centroid: Option<&[f32]>,
    ) -> Result<()> {
        if keys.len() < 2 {
            return Ok(());
        }
        // Build deduped + sorted pairs (a < b).
        let mut keys_owned: Vec<String> = keys.iter().cloned().collect();
        keys_owned.sort();
        keys_owned.dedup();
        if keys_owned.len() < 2 {
            return Ok(());
        }
        let now = now_secs();
        // Prepare ctx contribution as encoded blob (or None).
        let ctx_blob: Option<Vec<u8>> = ctx_centroid
            .filter(|v| !v.is_empty())
            .map(crate::vector::encode_embedding);

        // Generate all (a, b) pairs with a < b.
        let mut pairs: Vec<(String, String)> = Vec::with_capacity(
            keys_owned.len() * (keys_owned.len() - 1) / 2,
        );
        for i in 0..keys_owned.len() {
            for j in (i + 1)..keys_owned.len() {
                pairs.push((keys_owned[i].clone(), keys_owned[j].clone()));
            }
        }

        let res = self
            .conn
            .call(move |c| -> RusqliteResult<()> {
                let tx = c.transaction()?;
                for (a, b) in &pairs {
                    // Read existing row (if any) to compute rolling-mean.
                    let existing: Option<(i64, Option<Vec<u8>>)> = tx
                        .query_row(
                            "SELECT count, ctx_centroid FROM memory_coactivation
                             WHERE key_a = ?1 AND key_b = ?2",
                            rusqlite::params![a, b],
                            |row| Ok((row.get(0)?, row.get(1)?)),
                        )
                        .optional()?;

                    let new_blob: Option<Vec<u8>> = match (&ctx_blob, &existing) {
                        (None, _) => existing.as_ref().and_then(|(_, blob)| blob.clone()),
                        (Some(new_b), None) => Some(new_b.clone()),
                        (Some(new_b), Some((cnt, Some(old_b)))) => {
                            // Rolling mean: new_centroid = (count*old + new_contrib) / (count+1)
                            let old_v = crate::vector::decode_embedding(old_b);
                            let new_v = crate::vector::decode_embedding(new_b);
                            if old_v.len() == new_v.len() && !old_v.is_empty() {
                                let cnt_f = *cnt as f32;
                                let denom = cnt_f + 1.0;
                                let blended: Vec<f32> = old_v
                                    .iter()
                                    .zip(new_v.iter())
                                    .map(|(o, n)| (cnt_f * o + n) / denom)
                                    .collect();
                                Some(crate::vector::encode_embedding(&blended))
                            } else {
                                Some(new_b.clone())
                            }
                        }
                        (Some(new_b), Some((_, None))) => Some(new_b.clone()),
                    };

                    tx.execute(
                        "INSERT INTO memory_coactivation
                            (key_a, key_b, count, first_at, last_at, ctx_centroid)
                         VALUES (?1, ?2, 1, ?3, ?3, ?4)
                         ON CONFLICT(key_a, key_b) DO UPDATE SET
                            count    = count + 1,
                            last_at  = ?3,
                            ctx_centroid = ?4",
                        rusqlite::params![a, b, now, new_blob],
                    )?;
                }
                tx.commit()?;
                Ok(())
            })
            .await;

        match res {
            Ok(()) => Ok(()),
            Err(e) => {
                // Fail-soft: trace must never break search.
                tracing::warn!(error = %e, "record_coactivation failed (non-fatal)");
                Ok(())
            }
        }
    }

    /// v21 α — return top-N co-activation edges for a memory key,
    /// ordered by count DESC. Returns the *other* key in each pair
    /// (so caller doesn't have to filter).
    async fn top_coactivation(
        &self,
        key: &str,
        limit: u32,
    ) -> Result<Vec<CoactivationEdge>> {
        let key_owned = key.to_string();
        let lim = limit as i64;
        self.conn
            .call(move |c| -> RusqliteResult<Vec<CoactivationEdge>> {
                let mut stmt = c.prepare(
                    "SELECT key_a, key_b, count, first_at, last_at
                       FROM memory_coactivation
                      WHERE key_a = ?1 OR key_b = ?1
                   ORDER BY count DESC, last_at DESC
                      LIMIT ?2",
                )?;
                let rows = stmt
                    .query_map(rusqlite::params![key_owned, lim], |row| {
                        Ok(CoactivationEdge {
                            key_a: row.get(0)?,
                            key_b: row.get(1)?,
                            count: row.get::<_, i64>(2)? as u64,
                            first_at: row.get(3)?,
                            last_at: row.get(4)?,
                        })
                    })?
                    .collect::<std::result::Result<Vec<_>, _>>()?;
                Ok(rows)
            })
            .await
            .map_err(|e| Error::Backend(format!("top_coactivation: {e}")))
    }

    /// **Phase 1 P1** — coactivation edges where both endpoints are in `keys`.
    /// Single SQL round-trip with an `IN (?,?,...)` clause built from `keys`.
    /// Empty / single-key inputs short-circuit. Cap on `keys.len()` is the
    /// SQLite parameter limit (~999); the MCP layer caps result pages well
    /// below that, so no extra guard is needed here.
    async fn coactivation_among(&self, keys: &[String]) -> Result<Vec<CoactivationEdge>> {
        if keys.len() < 2 {
            return Ok(Vec::new());
        }
        let owned: Vec<String> = keys.to_vec();
        self.conn
            .call(move |c| -> RusqliteResult<Vec<CoactivationEdge>> {
                let placeholders = (1..=owned.len())
                    .map(|i| format!("?{i}"))
                    .collect::<Vec<_>>()
                    .join(",");
                let sql = format!(
                    "SELECT key_a, key_b, count, first_at, last_at
                       FROM memory_coactivation
                      WHERE key_a IN ({phs}) AND key_b IN ({phs})",
                    phs = placeholders,
                );
                let mut stmt = c.prepare(&sql)?;
                let params_vec: Vec<&dyn rusqlite::ToSql> =
                    owned.iter().map(|s| s as &dyn rusqlite::ToSql).collect();
                let rows = stmt
                    .query_map(params_vec.as_slice(), |row| {
                        Ok(CoactivationEdge {
                            key_a: row.get(0)?,
                            key_b: row.get(1)?,
                            count: row.get::<_, i64>(2)? as u64,
                            first_at: row.get(3)?,
                            last_at: row.get(4)?,
                        })
                    })?
                    .collect::<std::result::Result<Vec<_>, _>>()?;
                Ok(rows)
            })
            .await
            .map_err(|e| Error::Backend(format!("coactivation_among: {e}")))
    }

    /// **Phase 1 P5** — bulk version of [`top_coactivation`] over the whole
    /// graph: edges with `count >= min_count`, ordered by count DESC. Used
    /// by `agent-bridge dream replay` to seed cluster discovery (weight-first
    /// union-find).
    async fn top_coactivation_edges(
        &self,
        min_count: u64,
        limit: u32,
    ) -> Result<Vec<CoactivationEdge>> {
        let min_c = min_count as i64;
        let lim = limit as i64;
        self.conn
            .call(move |c| -> RusqliteResult<Vec<CoactivationEdge>> {
                let mut stmt = c.prepare(
                    "SELECT key_a, key_b, count, first_at, last_at
                       FROM memory_coactivation
                      WHERE count >= ?1
                   ORDER BY count DESC, last_at DESC
                      LIMIT ?2",
                )?;
                let rows = stmt
                    .query_map(rusqlite::params![min_c, lim], |row| {
                        Ok(CoactivationEdge {
                            key_a: row.get(0)?,
                            key_b: row.get(1)?,
                            count: row.get::<_, i64>(2)? as u64,
                            first_at: row.get(3)?,
                            last_at: row.get(4)?,
                        })
                    })?
                    .collect::<std::result::Result<Vec<_>, _>>()?;
                Ok(rows)
            })
            .await
            .map_err(|e| Error::Backend(format!("top_coactivation_edges: {e}")))
    }

    /// **Phase 0 telemetry** — append one `memory_query_log` row and prune
    /// the oldest if the table is over [`MEMORY_QUERY_LOG_RING_CAP`]. Both
    /// in one transaction so concurrent writers can't slip past the cap.
    async fn record_memory_query(&self, record: &MemoryQueryRecord) -> Result<()> {
        let kind = clamp(&record.kind, 32);
        let query = clamp(&record.query, 256);
        let tags_json = clamp(&record.tags_json, 256);
        let source = clamp(&record.source, 64);
        let hit_count = i64::from(record.hit_count);
        let duration_us = i64::from(record.duration_us);
        let top_hit_age_secs = record.top_hit_age_secs;
        let top_hit_created_at = record.top_hit_created_at;
        let at = record.at;

        self.conn
            .call(move |c| -> RusqliteResult<()> {
                let tx = c.unchecked_transaction()?;
                tx.execute(
                    "INSERT INTO memory_query_log
                        (kind, query, tags_json, hit_count, top_hit_age_secs,
                         top_hit_created_at, duration_us, source, at)
                     VALUES (?1, ?2, ?3, ?4, ?5, ?6, ?7, ?8, ?9)",
                    rusqlite::params![
                        kind, query, tags_json, hit_count, top_hit_age_secs,
                        top_hit_created_at, duration_us, source, at
                    ],
                )?;
                // Ring-buffer prune: keep at most MEMORY_QUERY_LOG_RING_CAP rows.
                tx.execute(
                    "DELETE FROM memory_query_log
                       WHERE id IN (
                           SELECT id FROM memory_query_log
                           ORDER BY id ASC
                           LIMIT MAX(0, (SELECT COUNT(*) FROM memory_query_log) - ?1)
                       )",
                    rusqlite::params![MEMORY_QUERY_LOG_RING_CAP],
                )?;
                tx.commit()
            })
            .await
            .map_err(|e| Error::Backend(format!("record_memory_query: {e}")))
    }

    /// **Phase 0 telemetry** — aggregate `memory_query_log` over the last
    /// `window_secs` seconds. Returns hit-rate, p50/p95 latency, avg top-hit
    /// age, per-kind counts, and top miss queries.
    async fn memory_query_stats(&self, window_secs: i64) -> Result<MemoryQueryStats> {
        let now = now_secs();
        let window_start = now - window_secs.max(0);

        self.conn
            .call(move |c| -> RusqliteResult<MemoryQueryStats> {
                // Pull all (hit_count, duration_us, top_hit_age_secs) rows in window.
                // Window is small (≤ ring cap), so vector is bounded.
                let mut stmt = c.prepare(
                    "SELECT hit_count, duration_us, top_hit_age_secs, kind
                       FROM memory_query_log
                      WHERE at >= ?1",
                )?;
                let rows: Vec<(i64, i64, Option<i64>, String)> = stmt
                    .query_map(rusqlite::params![window_start], |r| {
                        Ok((r.get(0)?, r.get(1)?, r.get(2)?, r.get(3)?))
                    })?
                    .collect::<std::result::Result<Vec<_>, _>>()?;

                if rows.is_empty() {
                    return Ok(MemoryQueryStats {
                        window_start,
                        window_end: now,
                        ..Default::default()
                    });
                }

                let total = rows.len() as u64;
                let hits = rows.iter().filter(|(h, _, _, _)| *h > 0).count() as u64;
                let misses = total - hits;
                let hit_rate = if total > 0 {
                    hits as f64 / total as f64
                } else {
                    0.0
                };

                let age_sum: i64 = rows.iter().filter_map(|(_, _, a, _)| *a).sum();
                let age_n = rows.iter().filter(|(_, _, a, _)| a.is_some()).count() as f64;
                let avg_top_hit_age_secs = if age_n > 0.0 { age_sum as f64 / age_n } else { 0.0 };

                let mut durations: Vec<i64> =
                    rows.iter().map(|(_, d, _, _)| *d).collect();
                durations.sort_unstable();
                let p50 = pct_idx(&durations, 0.50);
                let p95 = pct_idx(&durations, 0.95);

                // Per-kind counts via SQL (cheap, lets SQLite handle group by).
                let mut by_kind_stmt = c.prepare(
                    "SELECT kind, COUNT(*) FROM memory_query_log
                      WHERE at >= ?1
                   GROUP BY kind ORDER BY COUNT(*) DESC",
                )?;
                let by_kind: Vec<(String, u64)> = by_kind_stmt
                    .query_map(rusqlite::params![window_start], |r| {
                        Ok((r.get::<_, String>(0)?, r.get::<_, i64>(1)? as u64))
                    })?
                    .collect::<std::result::Result<Vec<_>, _>>()?;

                let mut miss_stmt = c.prepare(
                    "SELECT query, COUNT(*) FROM memory_query_log
                      WHERE at >= ?1 AND hit_count = 0 AND query <> ''
                   GROUP BY query ORDER BY COUNT(*) DESC LIMIT 10",
                )?;
                let top_miss_queries: Vec<(String, u64)> = miss_stmt
                    .query_map(rusqlite::params![window_start], |r| {
                        Ok((r.get::<_, String>(0)?, r.get::<_, i64>(1)? as u64))
                    })?
                    .collect::<std::result::Result<Vec<_>, _>>()?;

                Ok(MemoryQueryStats {
                    window_start,
                    window_end: now,
                    total_queries: total,
                    hits,
                    misses,
                    hit_rate,
                    avg_top_hit_age_secs,
                    p50_duration_us: p50.try_into().unwrap_or(u32::MAX),
                    p95_duration_us: p95.try_into().unwrap_or(u32::MAX),
                    by_kind,
                    top_miss_queries,
                })
            })
            .await
            .map_err(|e| Error::Backend(format!("memory_query_stats: {e}")))
    }

    /// v21 α — Aggregate stats for the synaptic trace graph. Powers the
    /// `agent-bridge dream stats` subcommand. The β trigger metric
    /// (top10/median ratio) reads here (≥ 5.0 means clusters emerged).
    async fn coactivation_stats(&self) -> Result<CoactivationStats> {
        let now = now_secs();
        self.conn
            .call(move |c| -> RusqliteResult<CoactivationStats> {
                let (total_pairs, max_count, pairs_last_24h): (i64, Option<i64>, i64) = c
                    .query_row(
                        "SELECT COUNT(*), MAX(count),
                                COALESCE(SUM(CASE WHEN last_at >= ?1 THEN 1 ELSE 0 END), 0)
                           FROM memory_coactivation",
                        rusqlite::params![now - 86400],
                        |row| Ok((row.get(0)?, row.get(1)?, row.get(2)?)),
                    )?;

                if total_pairs == 0 {
                    return Ok(CoactivationStats {
                        total_pairs: 0,
                        total_unique_keys: 0,
                        max_count: 0,
                        median_count: 0.0,
                        top10_avg_count: 0.0,
                        top10_to_median_ratio: 0.0,
                        pairs_last_24h: 0,
                        top_5_edges: Vec::new(),
                    });
                }

                let total_unique_keys: i64 = c.query_row(
                    "SELECT COUNT(DISTINCT k) FROM (
                       SELECT key_a AS k FROM memory_coactivation
                       UNION ALL
                       SELECT key_b AS k FROM memory_coactivation
                     )",
                    [],
                    |row| row.get(0),
                )?;

                let mut stmt_counts = c.prepare(
                    "SELECT count FROM memory_coactivation ORDER BY count DESC",
                )?;
                let all_counts: Vec<i64> = stmt_counts
                    .query_map([], |row| row.get::<_, i64>(0))?
                    .collect::<std::result::Result<Vec<_>, _>>()?;
                drop(stmt_counts);

                let n = all_counts.len();
                let median = if n % 2 == 1 {
                    all_counts[n / 2] as f64
                } else {
                    (all_counts[n / 2 - 1] as f64 + all_counts[n / 2] as f64) / 2.0
                };
                let top10_n = n.min(10);
                let top10_sum: i64 = all_counts.iter().take(top10_n).sum();
                let top10_avg = if top10_n > 0 {
                    top10_sum as f64 / top10_n as f64
                } else {
                    0.0
                };
                let ratio = if median > 0.0 { top10_avg / median } else { 0.0 };

                let mut stmt_top = c.prepare(
                    "SELECT key_a, key_b, count, first_at, last_at
                       FROM memory_coactivation
                   ORDER BY count DESC, last_at DESC
                      LIMIT 5",
                )?;
                let top_5_edges: Vec<CoactivationEdge> = stmt_top
                    .query_map([], |row| {
                        Ok(CoactivationEdge {
                            key_a: row.get(0)?,
                            key_b: row.get(1)?,
                            count: row.get::<_, i64>(2)? as u64,
                            first_at: row.get(3)?,
                            last_at: row.get(4)?,
                        })
                    })?
                    .collect::<std::result::Result<Vec<_>, _>>()?;
                drop(stmt_top);

                Ok(CoactivationStats {
                    total_pairs: total_pairs as u64,
                    total_unique_keys: total_unique_keys as u64,
                    max_count: max_count.unwrap_or(0) as u64,
                    median_count: median,
                    top10_avg_count: top10_avg,
                    top10_to_median_ratio: ratio,
                    pairs_last_24h: pairs_last_24h as u64,
                    top_5_edges,
                })
            })
            .await
            .map_err(|e| Error::Backend(format!("coactivation_stats: {e}")))
    }

    /// v21 — Identity behavioral fingerprint over [window_start, window_end).
    /// Aggregates from mcp_tool_calls (tool histogram + ok rate) +
    /// forum_posts (post count, kind distribution, avg body length) +
    /// memories (saves in window). Powers `agent-bridge dream identity`
    /// delta reports.
    async fn identity_window(
        &self,
        window_start: i64,
        window_end: i64,
    ) -> Result<IdentityWindow> {
        self.conn
            .call(move |c| -> RusqliteResult<IdentityWindow> {
                // Tool call totals + ok rate.
                let (tool_total, tool_ok): (i64, i64) = c.query_row(
                    "SELECT COUNT(*), COALESCE(SUM(ok), 0)
                       FROM mcp_tool_calls
                      WHERE ts >= ?1 AND ts < ?2",
                    rusqlite::params![window_start, window_end],
                    |row| Ok((row.get(0)?, row.get(1)?)),
                )?;

                // Top 10 tools by count.
                let mut stmt_top = c.prepare(
                    "SELECT tool_name, COUNT(*) AS cnt
                       FROM mcp_tool_calls
                      WHERE ts >= ?1 AND ts < ?2
                   GROUP BY tool_name
                   ORDER BY cnt DESC
                      LIMIT 10",
                )?;
                let top_tools: Vec<(String, u64)> = stmt_top
                    .query_map(
                        rusqlite::params![window_start, window_end],
                        |row| Ok((row.get::<_, String>(0)?, row.get::<_, i64>(1)? as u64)),
                    )?
                    .collect::<std::result::Result<Vec<_>, _>>()?;
                drop(stmt_top);

                // Forum: count + avg body length.
                let (forum_count, forum_avg_len): (i64, Option<f64>) = c.query_row(
                    "SELECT COUNT(*), AVG(LENGTH(body))
                       FROM forum_posts
                      WHERE created_at >= ?1 AND created_at < ?2",
                    rusqlite::params![window_start, window_end],
                    |row| Ok((row.get(0)?, row.get(1)?)),
                )?;

                // Forum kind distribution.
                let mut stmt_kinds = c.prepare(
                    "SELECT kind, COUNT(*) AS cnt
                       FROM forum_posts
                      WHERE created_at >= ?1 AND created_at < ?2
                   GROUP BY kind
                   ORDER BY kind ASC",
                )?;
                let forum_kinds: Vec<(String, u64)> = stmt_kinds
                    .query_map(
                        rusqlite::params![window_start, window_end],
                        |row| Ok((row.get::<_, String>(0)?, row.get::<_, i64>(1)? as u64)),
                    )?
                    .collect::<std::result::Result<Vec<_>, _>>()?;
                drop(stmt_kinds);

                // Memory saves (created_at in window — distinct from access).
                let memory_saves: i64 = c.query_row(
                    "SELECT COUNT(*) FROM memories
                      WHERE created_at >= ?1 AND created_at < ?2",
                    rusqlite::params![window_start, window_end],
                    |row| row.get(0),
                )?;

                Ok(IdentityWindow {
                    window_start,
                    window_end,
                    tool_calls_total: tool_total as u64,
                    tool_calls_ok: tool_ok as u64,
                    top_tools,
                    forum_posts: forum_count as u64,
                    forum_kinds,
                    forum_avg_body_len: forum_avg_len.unwrap_or(0.0),
                    memory_saves: memory_saves as u64,
                })
            })
            .await
            .map_err(|e| Error::Backend(format!("identity_window: {e}")))
    }

    async fn memory_load_embeddings(&self) -> Result<Vec<(MemoryRecord, Vec<f32>)>> {
        let rows = self
            .conn
            .call(move |c| -> RusqliteResult<Vec<(MemoryRecord, Vec<u8>)>> {
                let mut stmt = c.prepare(
                    "SELECT key, kind, content, tags, related_keys, scope,
                            created_at, updated_at, last_accessed_at, access_count,
                            importance, status, trigger_pattern, superseded_by, embedding
                     FROM memories
                     WHERE status = 'active' AND embedding IS NOT NULL",
                )?;
                let rows = stmt
                    .query_map([], |row| {
                        let tags_s: String = row.get(3)?;
                        let related_s: String = row.get(4)?;
                        let rec = MemoryRecord {
                            key: row.get(0)?,
                            kind: row.get(1)?,
                            content: row.get(2)?,
                            tags: parse_str_array(&tags_s),
                            related_keys: parse_str_array(&related_s),
                            scope: row.get(5)?,
                            created_at: row.get(6)?,
                            updated_at: row.get(7)?,
                            last_accessed_at: row.get(8)?,
                            access_count: row.get::<_, i64>(9)? as u64,
                            importance: row.get::<_, f64>(10).unwrap_or(0.5),
                            status: row
                                .get::<_, String>(11)
                                .unwrap_or_else(|_| "active".to_string()),
                            trigger_pattern: row.get::<_, Option<String>>(12)?,
                            superseded_by: row.get::<_, Option<String>>(13)?,
                        };
                        let emb_bytes: Vec<u8> = row.get(14)?;
                        Ok((rec, emb_bytes))
                    })?
                    .collect::<std::result::Result<Vec<_>, _>>()?;
                Ok(rows)
            })
            .await
            .map_err(|e| Error::Backend(format!("memory_load_embeddings: {e}")))?;

        Ok(rows
            .into_iter()
            .filter_map(|(rec, emb_bytes)| {
                let emb = crate::vector::decode_embedding(&emb_bytes);
                if emb.is_empty() {
                    return None;
                }
                Some((rec, emb))
            })
            .collect())
    }

    async fn memory_reindex_embeddings(&self, batch_size: usize) -> Result<usize> {
        let cap = batch_size.max(1).min(1000);
        // Load rows needing re-embedding (embedding IS NULL or wrong-dim).
        let to_update: Vec<(String, String)> = self
            .conn
            .call(move |c| -> RusqliteResult<Vec<(String, String)>> {
                let mut stmt = c.prepare(
                    "SELECT key, content FROM memories
                     WHERE status = 'active' AND embedding IS NULL
                     LIMIT ?1",
                )?;
                let rows = stmt
                    .query_map([cap as i64], |row| {
                        Ok((row.get::<_, String>(0)?, row.get::<_, String>(1)?))
                    })?
                    .collect::<std::result::Result<Vec<_>, _>>()?;
                Ok(rows)
            })
            .await
            .map_err(|e| Error::Backend(format!("memory_reindex list: {e}")))?;

        if to_update.is_empty() {
            return Ok(0);
        }

        // Compute embeddings on the calling thread (CPU work outside DB conn).
        let pairs: Vec<(String, Vec<u8>)> = to_update
            .into_iter()
            .map(|(key, content)| {
                let emb = crate::vector::embed_text(&content);
                let bytes = crate::vector::encode_embedding(&emb);
                (key, bytes)
            })
            .collect();

        let updated = pairs.len();
        self.conn
            .call(move |c| -> RusqliteResult<()> {
                let tx = c.unchecked_transaction()?;
                let mut stmt =
                    tx.prepare("UPDATE memories SET embedding = ?2 WHERE key = ?1")?;
                for (key, emb_bytes) in &pairs {
                    stmt.execute(params![key, emb_bytes])?;
                }
                drop(stmt);
                tx.commit()?;
                Ok(())
            })
            .await
            .map_err(|e| Error::Backend(format!("memory_reindex update: {e}")))?;

        Ok(updated)
    }

    async fn codebase_reindex_embeddings(&self, batch_size: usize) -> Result<usize> {
        let cap = batch_size.max(1).min(1000);
        // Load rows needing fill (embedding IS NULL). codebase_index always
        // writes NULL on insert and there is no other path that fills these,
        // so this method is the only thing that makes semantic search usable.
        let to_update: Vec<(i64, String, String)> = self
            .conn
            .call(move |c| -> RusqliteResult<Vec<(i64, String, String)>> {
                let mut stmt = c.prepare(
                    "SELECT id, name, signature FROM codebase_symbols
                     WHERE embedding IS NULL
                     LIMIT ?1",
                )?;
                let rows = stmt
                    .query_map([cap as i64], |row| {
                        Ok((
                            row.get::<_, i64>(0)?,
                            row.get::<_, String>(1)?,
                            row.get::<_, String>(2)?,
                        ))
                    })?
                    .collect::<std::result::Result<Vec<_>, _>>()?;
                Ok(rows)
            })
            .await
            .map_err(|e| Error::Backend(format!("codebase_reindex list: {e}")))?;

        if to_update.is_empty() {
            return Ok(0);
        }

        // Embed `name + signature` so user queries like "function that opens a
        // browser tab" pick up both the identifier and the parameter list.
        // signature is already capped at 200 chars in extract_symbols::make.
        let pairs: Vec<(i64, Vec<u8>)> = to_update
            .into_iter()
            .map(|(id, name, signature)| {
                let text = if signature.is_empty() {
                    name
                } else {
                    format!("{name} {signature}")
                };
                let emb = crate::vector::embed_text(&text);
                let bytes = crate::vector::encode_embedding(&emb);
                (id, bytes)
            })
            .collect();

        let updated = pairs.len();
        self.conn
            .call(move |c| -> RusqliteResult<()> {
                let tx = c.unchecked_transaction()?;
                let mut stmt =
                    tx.prepare("UPDATE codebase_symbols SET embedding = ?2 WHERE id = ?1")?;
                for (id, emb_bytes) in &pairs {
                    stmt.execute(params![id, emb_bytes])?;
                }
                drop(stmt);
                tx.commit()?;
                Ok(())
            })
            .await
            .map_err(|e| Error::Backend(format!("codebase_reindex update: {e}")))?;

        Ok(updated)
    }

    // ─── D3.2: codebase symbol index ────────────────────────────────────

    async fn codebase_index(
        &self,
        root_path: &str,
        languages: &[String],
    ) -> Result<CodebaseIndexStats> {
        use crate::codebase::{detect_language, extract_symbols};
        use walkdir::WalkDir;

        let start = std::time::Instant::now();
        let root = root_path.to_string();
        let langs: Vec<String> = languages.to_vec();

        // File walking, symbol extraction, and embedding computation run in a blocking thread.
        let root_for_walk = root.clone();
        let (all_symbols, indexed_files) = tokio::task::spawn_blocking(move || {
            // Walk source files; prune non-source trees at directory level.
            let mut symbols: Vec<CodebaseSymbol> = Vec::new();
            let mut count = 0u32;
            for entry in WalkDir::new(&root_for_walk)
                .follow_links(false)
                .into_iter()
                .filter_entry(|e| {
                    let name = e.file_name().to_str().unwrap_or("");
                    !matches!(
                        name,
                        ".git"
                            | "target"
                            | "node_modules"
                            | ".venv"
                            | "__pycache__"
                            | ".mypy_cache"
                            | "dist"
                            | "build"
                    )
                })
                .filter_map(|e| e.ok())
                .filter(|e| e.file_type().is_file())
            {
                let path = entry.path();
                let lang = match detect_language(path) {
                    Some(l) => l,
                    None => continue,
                };
                if !langs.is_empty() && !langs.iter().any(|l| l.as_str() == lang) {
                    continue;
                }
                let file_path_str = path.to_string_lossy().to_string();
                if let Ok(content) = std::fs::read_to_string(path) {
                    symbols.extend(extract_symbols(&content, &file_path_str, lang));
                    count += 1;
                }
            }
            // Embeddings are filled by `codebase_reindex_embeddings` (call
            // it after this returns); rows ship with embedding=NULL so the
            // walk stays fast and embed cost is opt-in.
            (symbols, count)
        })
        .await
        .map_err(|e| Error::Backend(format!("codebase_index blocking: {e}")))?;

        let symbol_count = all_symbols.len() as u32;
        let root_for_return = root_path.to_string();
        let now = now_secs();

        self.conn
            .call(move |c| -> RusqliteResult<()> {
                // Wrap in explicit transaction: all INSERTs commit in one fsync.
                let tx = c.savepoint()?;
                tx.execute(
                    "DELETE FROM codebase_symbols WHERE root_path = ?1",
                    params![root],
                )?;
                let mut stmt = tx.prepare(
                    "INSERT INTO codebase_symbols
                     (file_path, line, col, kind, name, signature, language, root_path,
                      indexed_at, embedding)
                     VALUES (?1, ?2, ?3, ?4, ?5, ?6, ?7, ?8, ?9, NULL)",
                )?;
                for sym in &all_symbols {
                    stmt.execute(params![
                        sym.file_path,
                        sym.line,
                        sym.col,
                        sym.kind,
                        sym.name,
                        sym.signature,
                        sym.language,
                        root,
                        now
                    ])?;
                }
                drop(stmt);
                tx.commit()?;
                Ok(())
            })
            .await
            .map_err(|e| Error::Backend(format!("codebase_index write: {e}")))?;

        Ok(CodebaseIndexStats {
            indexed_files,
            symbols: symbol_count,
            duration_ms: start.elapsed().as_millis() as u64,
            root_path: root_for_return,
        })
    }

    async fn codebase_search(
        &self,
        query: &str,
        kind: Option<&str>,
        file_filter: Option<&str>,
        root_path: Option<&str>,
        limit: u32,
        mode: &str,
    ) -> Result<Vec<CodebaseSymbol>> {
        if mode == "semantic" {
            return self
                .codebase_search_semantic(query, kind, file_filter, root_path, limit)
                .await;
        }

        let pattern = format!("%{}%", query);
        let kind_f = kind.map(|s| s.to_string());
        let file_f = file_filter.map(|s| format!("%{}%", s));
        let root_f = root_path.map(|s| s.to_string());
        let lim = limit.min(500) as i64;

        self.conn
            .call(move |c| -> RusqliteResult<Vec<CodebaseSymbol>> {
                let mut stmt = c.prepare(
                    "SELECT file_path, line, col, kind, name, signature, language
                     FROM codebase_symbols
                     WHERE (name LIKE ?1 OR signature LIKE ?1)
                       AND (?2 IS NULL OR kind = ?2)
                       AND (?3 IS NULL OR root_path = ?3)
                       AND (?4 IS NULL OR file_path LIKE ?4)
                     GROUP BY file_path, line, kind, name
                     ORDER BY length(name), name
                     LIMIT ?5",
                )?;
                let rows = stmt
                    .query_map(params![pattern, kind_f, root_f, file_f, lim], |row| {
                        Ok(CodebaseSymbol {
                            file_path: row.get(0)?,
                            line: row.get::<_, i64>(1)? as u32,
                            col: row.get::<_, i64>(2)? as u32,
                            kind: row.get(3)?,
                            name: row.get(4)?,
                            signature: row.get(5)?,
                            language: row.get(6)?,
                            score: None,
                        })
                    })?
                    .collect::<std::result::Result<Vec<_>, _>>()?;
                Ok(rows)
            })
            .await
            .map_err(|e| Error::Backend(format!("codebase_search: {e}")))
    }


    // ─── v8: cloud-run lifecycle (warp-oz) ──────────────────────────────

    async fn set_cloud_run_id(&self, session_id: &SessionId, run_id: &str) -> Result<()> {
        let key = session_id.as_str().to_string();
        let rid = run_id.to_string();
        self.conn
            .call(move |c| -> RusqliteResult<()> {
                c.execute(
                    "UPDATE sessions SET cloud_run_id = ?2 WHERE id = ?1",
                    params![key, rid],
                )?;
                Ok(())
            })
            .await
            .map_err(|e| Error::Backend(format!("set_cloud_run_id: {e}")))?;
        Ok(())
    }

    async fn set_cloud_run_state(
        &self,
        session_id: &SessionId,
        state: &str,
        session_link: Option<&str>,
    ) -> Result<()> {
        let key = session_id.as_str().to_string();
        let st = state.to_string();
        let link = session_link.map(|s| s.to_string());
        self.conn
            .call(move |c| -> RusqliteResult<()> {
                c.execute(
                    "UPDATE sessions SET cloud_run_state = ?2, cloud_session_link = COALESCE(?3, cloud_session_link) WHERE id = ?1",
                    params![key, st, link],
                )?;
                Ok(())
            })
            .await
            .map_err(|e| Error::Backend(format!("set_cloud_run_state: {e}")))?;
        Ok(())
    }

    // ─── W5: plans ───────────────────────────────────────────────────────

    async fn plan_save(&self, plan_id: &str, title: &str, steps: &[PlanStep]) -> Result<()> {
        let pid = plan_id.to_string();
        let ttl = title.to_string();
        let steps_json = serde_json::to_string(steps).map_err(Error::Serde)?;
        self.conn
            .call(move |c| -> RusqliteResult<()> {
                let now = now_secs();
                let cnt: i64 = c.query_row(
                    "SELECT COUNT(*) FROM plans WHERE plan_id = ?1",
                    params![&pid],
                    |r| r.get(0),
                )?;
                if cnt > 0 {
                    c.execute(
                        "UPDATE plans SET title = ?2, steps_json = ?3, updated_at = ?4 WHERE plan_id = ?1",
                        params![&pid, &ttl, &steps_json, now],
                    )?;
                } else {
                    c.execute(
                        "INSERT INTO plans (plan_id, title, steps_json, created_at, updated_at) VALUES (?1, ?2, ?3, ?4, ?5)",
                        params![&pid, &ttl, &steps_json, now, now],
                    )?;
                }
                Ok(())
            })
            .await
            .map_err(|e| Error::Backend(format!("plan_save: {e}")))?;
        Ok(())
    }

    async fn plan_load(&self, plan_id: &str) -> Result<Option<PlanRecord>> {
        let pid = plan_id.to_string();
        let row = self
            .conn
            .call(move |c| -> RusqliteResult<Option<(String, String, String, i64, i64)>> {
                let mut stmt = c.prepare(
                    "SELECT plan_id, title, steps_json, created_at, updated_at FROM plans WHERE plan_id = ?",
                )?;
                let mut rows = stmt.query(params![pid])?;
                if let Some(r) = rows.next()? {
                    Ok(Some((r.get(0)?, r.get(1)?, r.get(2)?, r.get(3)?, r.get(4)?)))
                } else {
                    Ok(None)
                }
            })
            .await
            .map_err(|e| Error::Backend(format!("plan_load: {e}")))?;

        Ok(match row {
            Some((plan_id, title, steps_json, created_at, updated_at)) => {
                let steps: Vec<PlanStep> = serde_json::from_str(&steps_json)
                    .map_err(|e| Error::Backend(format!("plan_load: corrupt steps_json: {e}")))?;
                Some(PlanRecord {
                    plan_id,
                    title,
                    steps,
                    created_at,
                    updated_at,
                })
            }
            None => None,
        })
    }

    async fn plan_update_step(&self, plan_id: &str, step_id: &str, status: &str) -> Result<bool> {
        let pid = plan_id.to_string();
        let sid = step_id.to_string();
        let st = status.to_string();

        let maybe_json = self
            .conn
            .call({
                let pid = pid.clone();
                move |c| -> RusqliteResult<Option<String>> {
                    let mut stmt = c.prepare("SELECT steps_json FROM plans WHERE plan_id = ?")?;
                    let mut rows = stmt.query(params![pid])?;
                    if let Some(r) = rows.next()? {
                        Ok(Some(r.get::<_, String>(0)?))
                    } else {
                        Ok(None)
                    }
                }
            })
            .await
            .map_err(|e| Error::Backend(format!("plan_update_step(select): {e}")))?;

        let Some(steps_json) = maybe_json else {
            return Ok(false);
        };

        let mut steps: Vec<PlanStep> = serde_json::from_str(&steps_json)
            .map_err(|e| Error::Backend(format!("plan_update_step: corrupt steps_json: {e}")))?;

        let mut found = false;
        for step in &mut steps {
            if step.id == sid {
                step.status = st.clone();
                found = true;
                break;
            }
        }
        if !found {
            return Ok(false);
        }

        let new_json = serde_json::to_string(&steps).map_err(Error::Serde)?;
        let now = now_secs();
        self.conn
            .call(move |c| -> RusqliteResult<()> {
                c.execute(
                    "UPDATE plans SET steps_json = ?2, updated_at = ?3 WHERE plan_id = ?1",
                    params![pid, new_json, now],
                )?;
                Ok(())
            })
            .await
            .map_err(|e| Error::Backend(format!("plan_update_step(update): {e}")))?;

        Ok(true)
    }

    // ─── W6: agent_messages ────────────────────────────────────────────────

    async fn agent_message_send(
        &self,
        from_session: &str,
        to_session: &str,
        payload: &serde_json::Value,
    ) -> Result<i64> {
        let from_s = from_session.to_string();
        let to_s = to_session.to_string();
        let payload_json = serde_json::to_string(payload).map_err(Error::Serde)?;
        let ts = now_secs();
        let id = self
            .conn
            .call(move |c| -> RusqliteResult<i64> {
                c.execute(
                    "INSERT INTO agent_messages (from_session, to_session, payload_json, created_at, read)
                     VALUES (?1, ?2, ?3, ?4, 0)",
                    params![from_s, to_s, payload_json, ts],
                )?;
                Ok(c.last_insert_rowid())
            })
            .await
            .map_err(|e| Error::Backend(format!("agent_message_send: {e}")))?;
        Ok(id)
    }

    async fn agent_inbox_fetch(
        &self,
        to_session: &str,
        since_id: Option<i64>,
        unread_only: bool,
        limit: u32,
    ) -> Result<Vec<AgentMessageRecord>> {
        let to_s = to_session.to_string();
        let lim = i64::from(limit.max(1).min(500));
        let unread_flag: i64 = if unread_only { 1 } else { 0 };

        let rows = self
            .conn
            .call(
                move |c| -> RusqliteResult<Vec<(i64, String, String, String, i64, i64)>> {
                    let mut stmt = c.prepare(
                        "SELECT id, from_session, to_session, payload_json, created_at, read
                     FROM agent_messages
                     WHERE to_session = ?1
                       AND (?2 IS NULL OR id > ?2)
                       AND (?3 = 0 OR read = 0)
                     ORDER BY id ASC
                     LIMIT ?4",
                    )?;
                    let mut out = Vec::new();
                    let mut q = stmt.query(params![to_s, since_id, unread_flag, lim])?;
                    while let Some(r) = q.next()? {
                        out.push((
                            r.get(0)?,
                            r.get(1)?,
                            r.get(2)?,
                            r.get(3)?,
                            r.get(4)?,
                            r.get(5)?,
                        ));
                    }
                    Ok(out)
                },
            )
            .await
            .map_err(|e| Error::Backend(format!("agent_inbox_fetch: {e}")))?;

        let mut recs = Vec::with_capacity(rows.len());
        for (id, from_session, to_session, payload_json, created_at, read_i) in rows {
            let payload: serde_json::Value = serde_json::from_str(&payload_json).map_err(|e| {
                Error::Backend(format!(
                    "agent_inbox_fetch: corrupt payload_json id={id}: {e}"
                ))
            })?;
            recs.push(AgentMessageRecord {
                id,
                from_session,
                to_session,
                payload,
                created_at,
                read: read_i != 0,
            });
        }
        Ok(recs)
    }

    // ── v18: forum / collaboration whiteboard ──────────────────────────────

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
        if author.trim().is_empty() {
            return Err(Error::Backend(
                "forum_post: 'author' must be a non-empty session id".into(),
            ));
        }
        if body.trim().is_empty() {
            return Err(Error::Backend("forum_post: 'body' must be non-empty".into()));
        }
        let kind_norm = match kind {
            "" | "msg" => "msg",
            "finding" | "question" | "decision" | "reply" => kind,
            other => {
                return Err(Error::Backend(format!(
                    "forum_post: unknown kind '{other}'"
                )))
            }
        }
        .to_string();

        let author = author.to_string();
        let body = body.to_string();
        let refs_json = match refs {
            Some(v) => Some(serde_json::to_string(v).map_err(Error::Serde)?),
            None => None,
        };
        let now = now_secs();

        let outcome = match thread_id {
            Some(tid) => {
                self.conn
                    .call(move |c| -> RusqliteResult<ForumPostOutcome> {
                        let exists: i64 = c.query_row(
                            "SELECT COUNT(*) FROM forum_threads WHERE id=?1",
                            params![tid],
                            |r| r.get(0),
                        )?;
                        if exists == 0 {
                            return Err(tokio_rusqlite::rusqlite::Error::QueryReturnedNoRows);
                        }
                        c.execute(
                            "INSERT INTO forum_posts \
                             (thread_id, author, kind, body, refs_json, created_at) \
                             VALUES (?1, ?2, ?3, ?4, ?5, ?6)",
                            params![tid, author, kind_norm, body, refs_json, now],
                        )?;
                        let pid = c.last_insert_rowid();
                        c.execute(
                            "UPDATE forum_threads SET last_post_at=?1 WHERE id=?2",
                            params![now, tid],
                        )?;
                        Ok(ForumPostOutcome {
                            thread_id: tid,
                            post_id: pid,
                            created_thread: false,
                        })
                    })
                    .await
                    .map_err(|e| match e {
                        tokio_rusqlite::Error::Error(
                            tokio_rusqlite::rusqlite::Error::QueryReturnedNoRows,
                        ) => Error::Backend(format!("forum_post: thread_id={tid} not found")),
                        other => Error::Backend(format!("forum_post append: {other}")),
                    })?
            }
            None => {
                let board_s = board
                    .filter(|s| !s.is_empty())
                    .ok_or_else(|| {
                        Error::Backend(
                            "forum_post: 'board' required when creating a new thread".into(),
                        )
                    })?
                    .to_string();
                let title_s = title
                    .filter(|s| !s.is_empty())
                    .ok_or_else(|| {
                        Error::Backend(
                            "forum_post: 'title' required when creating a new thread".into(),
                        )
                    })?
                    .to_string();
                let tags_json = tags
                    .filter(|t| !t.is_empty())
                    .map(|t| serde_json::to_string(t))
                    .transpose()
                    .map_err(Error::Serde)?;
                let author2 = author.clone();
                self.conn
                    .call(move |c| -> RusqliteResult<ForumPostOutcome> {
                        c.execute(
                            "INSERT INTO forum_threads \
                             (board, title, created_by, created_at, last_post_at, status, tags_json) \
                             VALUES (?1, ?2, ?3, ?4, ?4, 'open', ?5)",
                            params![board_s, title_s, author2, now, tags_json],
                        )?;
                        let tid = c.last_insert_rowid();
                        c.execute(
                            "INSERT INTO forum_posts \
                             (thread_id, author, kind, body, refs_json, created_at) \
                             VALUES (?1, ?2, ?3, ?4, ?5, ?6)",
                            params![tid, author, kind_norm, body, refs_json, now],
                        )?;
                        let pid = c.last_insert_rowid();
                        Ok(ForumPostOutcome {
                            thread_id: tid,
                            post_id: pid,
                            created_thread: true,
                        })
                    })
                    .await
                    .map_err(|e| Error::Backend(format!("forum_post create: {e}")))?
            }
        };

        Ok(outcome)
    }

    async fn forum_read(
        &self,
        thread_id: Option<i64>,
        board: Option<&str>,
        since_post_id: Option<i64>,
        unread_for: Option<&str>,
        limit: u32,
    ) -> Result<Vec<ForumPostRecord>> {
        if thread_id.is_none() && board.is_none() {
            return Err(Error::Backend(
                "forum_read: provide at least one of 'thread_id' or 'board'".into(),
            ));
        }
        let lim = i64::from(limit.clamp(1, 500));

        // If caller asked for unread_for, override since_post_id with the
        // saved subscription cursor (most specific wins: thread > board).
        let mut effective_since = since_post_id;
        if let Some(sess) = unread_for.filter(|s| !s.is_empty()) {
            let sess_s = sess.to_string();
            let board_s = board.map(|s| s.to_string());
            let cursor = self
                .conn
                .call(move |c| -> RusqliteResult<Option<i64>> {
                    if let Some(tid) = thread_id {
                        if let Ok(v) = c.query_row(
                            "SELECT last_seen_post_id FROM forum_subscriptions \
                             WHERE session_id=?1 AND scope_kind='thread' AND scope_value=?2",
                            params![sess_s, tid.to_string()],
                            |r| r.get::<_, i64>(0),
                        ) {
                            return Ok(Some(v));
                        }
                    }
                    if let Some(b) = board_s {
                        if let Ok(v) = c.query_row(
                            "SELECT last_seen_post_id FROM forum_subscriptions \
                             WHERE session_id=?1 AND scope_kind='board' AND scope_value=?2",
                            params![sess_s, b],
                            |r| r.get::<_, i64>(0),
                        ) {
                            return Ok(Some(v));
                        }
                    }
                    Ok(None)
                })
                .await
                .map_err(|e| Error::Backend(format!("forum_read cursor: {e}")))?;
            if let Some(v) = cursor {
                effective_since = Some(effective_since.map_or(v, |s| s.max(v)));
            }
        }

        let board_s = board.map(|s| s.to_string());
        let rows = self
            .conn
            .call(
                move |c| -> RusqliteResult<Vec<(i64, i64, String, String, String, Option<String>, i64)>> {
                    let (sql, has_thread, has_board) = match (thread_id.is_some(), board_s.is_some()) {
                        (true, _) => (
                            "SELECT p.id, p.thread_id, p.author, p.kind, p.body, p.refs_json, p.created_at \
                             FROM forum_posts p \
                             WHERE p.thread_id = ?1 AND (?2 IS NULL OR p.id > ?2) \
                             ORDER BY p.id ASC LIMIT ?3",
                            true,
                            false,
                        ),
                        (false, true) => (
                            "SELECT p.id, p.thread_id, p.author, p.kind, p.body, p.refs_json, p.created_at \
                             FROM forum_posts p \
                             JOIN forum_threads t ON t.id = p.thread_id \
                             WHERE t.board = ?1 AND (?2 IS NULL OR p.id > ?2) \
                             ORDER BY p.id ASC LIMIT ?3",
                            false,
                            true,
                        ),
                        _ => unreachable!(),
                    };
                    let mut stmt = c.prepare(sql)?;
                    let mut q = if has_thread {
                        stmt.query(params![thread_id.unwrap(), effective_since, lim])?
                    } else if has_board {
                        stmt.query(params![board_s.as_ref().unwrap(), effective_since, lim])?
                    } else {
                        unreachable!()
                    };
                    let mut out = Vec::new();
                    while let Some(r) = q.next()? {
                        out.push((
                            r.get(0)?,
                            r.get(1)?,
                            r.get(2)?,
                            r.get(3)?,
                            r.get(4)?,
                            r.get(5)?,
                            r.get(6)?,
                        ));
                    }
                    Ok(out)
                },
            )
            .await
            .map_err(|e| Error::Backend(format!("forum_read: {e}")))?;

        let mut posts = Vec::with_capacity(rows.len());
        for (id, thread_id, author, kind, body, refs_json, created_at) in rows {
            let refs = match refs_json {
                Some(s) => serde_json::from_str(&s).unwrap_or(serde_json::Value::Null),
                None => serde_json::Value::Null,
            };
            posts.push(ForumPostRecord {
                id,
                thread_id,
                author,
                kind,
                body,
                refs,
                created_at,
            });
        }

        // Auto-advance subscription cursor for unread_for caller.
        if let (Some(sess), Some(last)) = (unread_for, posts.last().map(|p| p.id)) {
            let sess_s = sess.to_string();
            let board_s = board.map(|s| s.to_string());
            let _ = self
                .conn
                .call(move |c| -> RusqliteResult<()> {
                    if let Some(tid) = thread_id {
                        let n = c.execute(
                            "UPDATE forum_subscriptions SET last_seen_post_id=?1 \
                             WHERE session_id=?2 AND scope_kind='thread' AND scope_value=?3 \
                               AND last_seen_post_id < ?1",
                            params![last, sess_s, tid.to_string()],
                        )?;
                        if n > 0 {
                            return Ok(());
                        }
                    }
                    if let Some(b) = board_s {
                        let _ = c.execute(
                            "UPDATE forum_subscriptions SET last_seen_post_id=?1 \
                             WHERE session_id=?2 AND scope_kind='board' AND scope_value=?3 \
                               AND last_seen_post_id < ?1",
                            params![last, sess_s, b],
                        )?;
                    }
                    Ok(())
                })
                .await;
        }

        Ok(posts)
    }

    async fn forum_subscribe(
        &self,
        session_id: &str,
        scope_kind: &str,
        scope_value: &str,
        reset: bool,
    ) -> Result<()> {
        if session_id.trim().is_empty() {
            return Err(Error::Backend(
                "forum_subscribe: 'session_id' must be non-empty".into(),
            ));
        }
        if !matches!(scope_kind, "thread" | "board") {
            return Err(Error::Backend(format!(
                "forum_subscribe: scope_kind must be 'thread' or 'board' (got '{scope_kind}')"
            )));
        }
        let sess = session_id.to_string();
        let kind = scope_kind.to_string();
        let val = scope_value.to_string();
        let now = now_secs();
        self.conn
            .call(move |c| -> RusqliteResult<()> {
                if reset {
                    c.execute(
                        "INSERT INTO forum_subscriptions \
                         (session_id, scope_kind, scope_value, last_seen_post_id, created_at) \
                         VALUES (?1, ?2, ?3, 0, ?4) \
                         ON CONFLICT(session_id, scope_kind, scope_value) \
                         DO UPDATE SET last_seen_post_id=0",
                        params![sess, kind, val, now],
                    )?;
                } else {
                    c.execute(
                        "INSERT OR IGNORE INTO forum_subscriptions \
                         (session_id, scope_kind, scope_value, last_seen_post_id, created_at) \
                         VALUES (?1, ?2, ?3, 0, ?4)",
                        params![sess, kind, val, now],
                    )?;
                }
                Ok(())
            })
            .await
            .map_err(|e| Error::Backend(format!("forum_subscribe: {e}")))?;
        Ok(())
    }

    async fn forum_mark_seen(
        &self,
        session_id: &str,
        scope_kind: &str,
        scope_value: &str,
        post_id: i64,
    ) -> Result<()> {
        if !matches!(scope_kind, "thread" | "board") {
            return Err(Error::Backend(format!(
                "forum_mark_seen: scope_kind must be 'thread' or 'board' (got '{scope_kind}')"
            )));
        }
        let sess = session_id.to_string();
        let kind = scope_kind.to_string();
        let val = scope_value.to_string();
        self.conn
            .call(move |c| -> RusqliteResult<()> {
                c.execute(
                    "UPDATE forum_subscriptions SET last_seen_post_id=?1 \
                     WHERE session_id=?2 AND scope_kind=?3 AND scope_value=?4 \
                       AND last_seen_post_id < ?1",
                    params![post_id, sess, kind, val],
                )?;
                Ok(())
            })
            .await
            .map_err(|e| Error::Backend(format!("forum_mark_seen: {e}")))?;
        Ok(())
    }

    async fn forum_list_threads(
        &self,
        board: &str,
        unread_for: Option<&str>,
        status: Option<&str>,
        limit: u32,
    ) -> Result<Vec<ForumThreadRecord>> {
        if board.trim().is_empty() {
            return Err(Error::Backend("forum_list_threads: 'board' required".into()));
        }
        let board_s = board.to_string();
        let status_f = status.map(|s| s.to_string());
        let lim = i64::from(limit.clamp(1, 500));
        let unread_for_s = unread_for.map(|s| s.to_string());

        let rows = self
            .conn
            .call(
                move |c| -> RusqliteResult<Vec<(i64, String, String, String, i64, i64, String, Option<String>, i64, Option<i64>)>> {
                    // Per-thread board cursor (one value), if caller passed unread_for.
                    let board_cursor: Option<i64> = match unread_for_s.as_deref() {
                        Some(sess) => c
                            .query_row(
                                "SELECT last_seen_post_id FROM forum_subscriptions \
                                 WHERE session_id=?1 AND scope_kind='board' AND scope_value=?2",
                                params![sess, board_s],
                                |r| r.get(0),
                            )
                            .ok(),
                        None => None,
                    };

                    let mut stmt = c.prepare(
                        "SELECT id, board, title, created_by, created_at, last_post_at, \
                                status, tags_json, \
                                (SELECT COUNT(*) FROM forum_posts WHERE thread_id = forum_threads.id) AS post_count \
                         FROM forum_threads \
                         WHERE board = ?1 AND (?2 IS NULL OR status = ?2) \
                         ORDER BY last_post_at DESC LIMIT ?3",
                    )?;
                    let mut q = stmt.query(params![board_s, status_f, lim])?;

                    let mut out = Vec::new();
                    while let Some(r) = q.next()? {
                        let tid: i64 = r.get(0)?;
                        let unread: Option<i64> = match unread_for_s.as_deref() {
                            Some(sess) => {
                                // thread cursor wins over board cursor
                                let thread_cursor: Option<i64> = c
                                    .query_row(
                                        "SELECT last_seen_post_id FROM forum_subscriptions \
                                         WHERE session_id=?1 AND scope_kind='thread' AND scope_value=?2",
                                        params![sess, tid.to_string()],
                                        |r| r.get(0),
                                    )
                                    .ok();
                                let cursor = thread_cursor.or(board_cursor).unwrap_or(0);
                                let cnt: i64 = c.query_row(
                                    "SELECT COUNT(*) FROM forum_posts \
                                     WHERE thread_id=?1 AND id > ?2",
                                    params![tid, cursor],
                                    |r| r.get(0),
                                )?;
                                Some(cnt)
                            }
                            None => None,
                        };
                        out.push((
                            tid,
                            r.get::<_, String>(1)?,
                            r.get::<_, String>(2)?,
                            r.get::<_, String>(3)?,
                            r.get::<_, i64>(4)?,
                            r.get::<_, i64>(5)?,
                            r.get::<_, String>(6)?,
                            r.get::<_, Option<String>>(7)?,
                            r.get::<_, i64>(8)?,
                            unread,
                        ));
                    }
                    Ok(out)
                },
            )
            .await
            .map_err(|e| Error::Backend(format!("forum_list_threads: {e}")))?;

        let mut out = Vec::with_capacity(rows.len());
        for (
            id,
            board,
            title,
            created_by,
            created_at,
            last_post_at,
            status,
            tags_json,
            post_count,
            unread_count,
        ) in rows
        {
            let tags: Vec<String> = match tags_json {
                Some(s) => serde_json::from_str(&s).unwrap_or_default(),
                None => Vec::new(),
            };
            out.push(ForumThreadRecord {
                id,
                board,
                title,
                created_by,
                created_at,
                last_post_at,
                status,
                tags,
                post_count,
                unread_count,
            });
        }
        Ok(out)
    }

    async fn forum_export(
        &self,
        out_path: &std::path::Path,
    ) -> Result<ForumExportResult> {
        let threads: Vec<ForumThreadExport> = self
            .conn
            .call(move |c| -> RusqliteResult<Vec<ForumThreadExport>> {
                let mut tstmt = c.prepare(
                    "SELECT id, board, title, created_by, created_at, last_post_at,
                            status, tags_json
                     FROM forum_threads
                     ORDER BY created_at ASC, id ASC",
                )?;
                let mut out = Vec::new();
                let rows = tstmt
                    .query_map([], |row| {
                        let id: i64 = row.get(0)?;
                        let tags_json: Option<String> = row.get(7)?;
                        let tags: Vec<String> = tags_json
                            .as_deref()
                            .and_then(|s| serde_json::from_str::<Vec<String>>(s).ok())
                            .unwrap_or_default();
                        Ok((
                            id,
                            ForumThreadExport {
                                board: row.get(1)?,
                                title: row.get(2)?,
                                created_by: row.get(3)?,
                                created_at: row.get(4)?,
                                last_post_at: row.get(5)?,
                                status: row.get(6)?,
                                tags,
                                posts: Vec::new(),
                            },
                        ))
                    })?
                    .collect::<std::result::Result<Vec<_>, _>>()?;
                let mut pstmt = c.prepare(
                    "SELECT author, kind, body, refs_json, created_at
                     FROM forum_posts
                     WHERE thread_id = ?1
                     ORDER BY created_at ASC, id ASC",
                )?;
                for (id, mut t) in rows {
                    let posts = pstmt
                        .query_map(params![id], |row| {
                            let refs_json: Option<String> = row.get(3)?;
                            let refs = refs_json
                                .as_deref()
                                .and_then(|s| serde_json::from_str::<serde_json::Value>(s).ok());
                            Ok(ForumPostExport {
                                author: row.get(0)?,
                                kind: row.get(1)?,
                                body: row.get(2)?,
                                refs,
                                created_at: row.get(4)?,
                            })
                        })?
                        .collect::<std::result::Result<Vec<_>, _>>()?;
                    t.posts = posts;
                    out.push(t);
                }
                Ok(out)
            })
            .await
            .map_err(|e| Error::Backend(format!("forum_export query: {e}")))?;

        if let Some(parent) = out_path.parent() {
            tokio::fs::create_dir_all(parent)
                .await
                .map_err(|e| Error::Backend(format!("mkdir {parent:?}: {e}")))?;
        }
        let mut posts_written = 0u64;
        let mut buf = String::new();
        for t in &threads {
            posts_written += t.posts.len() as u64;
            buf.push_str(&serde_json::to_string(t)?);
            buf.push('\n');
        }
        tokio::fs::write(out_path, buf)
            .await
            .map_err(|e| Error::Backend(format!("write {out_path:?}: {e}")))?;
        Ok(ForumExportResult {
            threads_written: threads.len() as u64,
            posts_written,
        })
    }

    async fn forum_import(
        &self,
        in_path: &std::path::Path,
    ) -> Result<ForumImportReport> {
        let raw = match tokio::fs::read_to_string(in_path).await {
            Ok(s) => s,
            Err(e) if e.kind() == std::io::ErrorKind::NotFound => {
                return Ok(ForumImportReport::default());
            }
            Err(e) => {
                return Err(Error::Backend(format!("read {in_path:?}: {e}")));
            }
        };

        // Parse lines first so we can move owned data into the call closure.
        let mut threads: Vec<ForumThreadExport> = Vec::new();
        let mut malformed = 0u64;
        for line in raw.lines() {
            let line = line.trim();
            if line.is_empty() {
                continue;
            }
            match serde_json::from_str::<ForumThreadExport>(line) {
                Ok(t) => threads.push(t),
                Err(_) => malformed += 1,
            }
        }

        let report = self
            .conn
            .call(move |c| -> RusqliteResult<ForumImportReport> {
                let mut rep = ForumImportReport {
                    malformed,
                    ..Default::default()
                };
                let tx = c.transaction()?;
                {
                    let mut find_thread = tx.prepare(
                        "SELECT id, last_post_at FROM forum_threads
                         WHERE board=?1 AND created_by=?2 AND created_at=?3 AND title=?4
                         LIMIT 1",
                    )?;
                    let mut insert_thread = tx.prepare(
                        "INSERT INTO forum_threads
                            (board, title, created_by, created_at, last_post_at, status, tags_json)
                         VALUES (?1, ?2, ?3, ?4, ?5, ?6, ?7)",
                    )?;
                    let mut bump_last_post = tx.prepare(
                        "UPDATE forum_threads SET last_post_at=?1 WHERE id=?2",
                    )?;
                    let mut find_post = tx.prepare(
                        "SELECT 1 FROM forum_posts
                         WHERE thread_id=?1 AND author=?2 AND created_at=?3 AND body=?4
                         LIMIT 1",
                    )?;
                    let mut insert_post = tx.prepare(
                        "INSERT INTO forum_posts
                            (thread_id, author, kind, body, refs_json, created_at)
                         VALUES (?1, ?2, ?3, ?4, ?5, ?6)",
                    )?;

                    for t in &threads {
                        let tags_json = if t.tags.is_empty() {
                            None
                        } else {
                            Some(serde_json::to_string(&t.tags).unwrap_or_else(|_| "[]".into()))
                        };
                        let existing: Option<(i64, i64)> = find_thread
                            .query_row(
                                params![&t.board, &t.created_by, t.created_at, &t.title],
                                |row| Ok((row.get(0)?, row.get(1)?)),
                            )
                            .ok();
                        let (thread_id, prior_last_post) = match existing {
                            Some((id, lp)) => {
                                rep.threads_matched += 1;
                                (id, lp)
                            }
                            None => {
                                insert_thread.execute(params![
                                    &t.board,
                                    &t.title,
                                    &t.created_by,
                                    t.created_at,
                                    t.last_post_at,
                                    &t.status,
                                    tags_json,
                                ])?;
                                rep.threads_inserted += 1;
                                (tx.last_insert_rowid(), t.last_post_at)
                            }
                        };

                        let mut max_post_at = prior_last_post;
                        for p in &t.posts {
                            let exists: Option<i64> = find_post
                                .query_row(
                                    params![thread_id, &p.author, p.created_at, &p.body],
                                    |row| row.get(0),
                                )
                                .ok();
                            if exists.is_some() {
                                rep.posts_skipped += 1;
                                continue;
                            }
                            let refs_json = p
                                .refs
                                .as_ref()
                                .map(|v| v.to_string());
                            insert_post.execute(params![
                                thread_id,
                                &p.author,
                                &p.kind,
                                &p.body,
                                refs_json,
                                p.created_at,
                            ])?;
                            rep.posts_inserted += 1;
                            if p.created_at > max_post_at {
                                max_post_at = p.created_at;
                            }
                        }
                        if max_post_at > prior_last_post {
                            bump_last_post.execute(params![max_post_at, thread_id])?;
                        }
                    }
                }
                tx.commit()?;
                Ok(rep)
            })
            .await
            .map_err(|e| Error::Backend(format!("forum_import: {e}")))?;
        Ok(report)
    }

    async fn forum_set_thread_status(&self, thread_id: i64, status: &str) -> Result<()> {
        if !matches!(status, "open" | "resolved" | "archived") {
            return Err(Error::Backend(format!(
                "forum_set_thread_status: status must be open|resolved|archived (got '{status}')"
            )));
        }
        let st = status.to_string();
        self.conn
            .call(move |c| -> RusqliteResult<()> {
                let n = c.execute(
                    "UPDATE forum_threads SET status=?1 WHERE id=?2",
                    params![st, thread_id],
                )?;
                if n == 0 {
                    return Err(tokio_rusqlite::rusqlite::Error::QueryReturnedNoRows);
                }
                Ok(())
            })
            .await
            .map_err(|e| match e {
                tokio_rusqlite::Error::Error(
                    tokio_rusqlite::rusqlite::Error::QueryReturnedNoRows,
                ) => Error::Backend(format!(
                    "forum_set_thread_status: thread_id={thread_id} not found"
                )),
                other => Error::Backend(format!("forum_set_thread_status: {other}")),
            })?;
        Ok(())
    }

    // ── v19: agent presence registry ───────────────────────────────────────

    async fn agent_presence_announce(
        &self,
        session_id: &str,
        upsert: AgentPresenceUpsert<'_>,
    ) -> Result<AgentPresenceRecord> {
        if session_id.trim().is_empty() {
            return Err(Error::Backend(
                "agent_presence_announce: 'session_id' must be non-empty".into(),
            ));
        }
        let session_id = session_id.to_string();
        let now = now_secs();

        // Owned clones for the move closure.
        let name = upsert.name.map(|s| s.to_string());
        let description = upsert.description.map(|s| s.to_string());
        let version = upsert.version.map(|s| s.to_string());
        let url = upsert.url.map(|s| s.to_string());
        let node = upsert.node.map(|s| s.to_string());
        let project = upsert.project.map(|s| s.to_string());
        let role = upsert.role.map(|s| s.to_string());
        let tag = upsert.tag.map(|s| s.to_string());
        let cwd = upsert.cwd.map(|s| s.to_string());
        let pid = upsert.pid;
        let capabilities_json = match upsert.capabilities {
            Some(v) => Some(serde_json::to_string(v).map_err(Error::Serde)?),
            None => None,
        };
        let skills_json = match upsert.skills {
            Some(v) => Some(serde_json::to_string(v).map_err(Error::Serde)?),
            None => None,
        };

        let row = self
            .conn
            .call(move |c| -> RusqliteResult<AgentPresenceRecord> {
                let exists: i64 = c.query_row(
                    "SELECT COUNT(*) FROM agent_presence WHERE session_id=?1",
                    params![session_id],
                    |r| r.get(0),
                )?;

                if exists == 0 {
                    // INSERT path — required fields must be present.
                    let name = name.ok_or_else(|| {
                        tokio_rusqlite::rusqlite::Error::InvalidParameterName(
                            "name (required on first announce)".into(),
                        )
                    })?;
                    let node = node.ok_or_else(|| {
                        tokio_rusqlite::rusqlite::Error::InvalidParameterName(
                            "node (required on first announce)".into(),
                        )
                    })?;
                    let project = project.ok_or_else(|| {
                        tokio_rusqlite::rusqlite::Error::InvalidParameterName(
                            "project (required on first announce)".into(),
                        )
                    })?;
                    let role = role.ok_or_else(|| {
                        tokio_rusqlite::rusqlite::Error::InvalidParameterName(
                            "role (required on first announce)".into(),
                        )
                    })?;
                    c.execute(
                        "INSERT INTO agent_presence (
                            session_id, name, description, version, url,
                            node, project, role, tag, cwd, pid,
                            capabilities_json, skills_json,
                            started_at, last_heartbeat_at
                         ) VALUES (?1,?2,?3,?4,?5,?6,?7,?8,?9,?10,?11,?12,?13,?14,?14)",
                        params![
                            session_id,
                            name,
                            description,
                            version,
                            url,
                            node,
                            project,
                            role,
                            tag,
                            cwd,
                            pid,
                            capabilities_json,
                            skills_json,
                            now,
                        ],
                    )?;
                } else {
                    // UPDATE path — COALESCE so None keeps prior value.
                    c.execute(
                        "UPDATE agent_presence SET
                            name              = COALESCE(?2, name),
                            description       = COALESCE(?3, description),
                            version           = COALESCE(?4, version),
                            url               = COALESCE(?5, url),
                            node              = COALESCE(?6, node),
                            project           = COALESCE(?7, project),
                            role              = COALESCE(?8, role),
                            tag               = COALESCE(?9, tag),
                            cwd               = COALESCE(?10, cwd),
                            pid               = COALESCE(?11, pid),
                            capabilities_json = COALESCE(?12, capabilities_json),
                            skills_json       = COALESCE(?13, skills_json),
                            last_heartbeat_at = ?14
                         WHERE session_id = ?1",
                        params![
                            session_id,
                            name,
                            description,
                            version,
                            url,
                            node,
                            project,
                            role,
                            tag,
                            cwd,
                            pid,
                            capabilities_json,
                            skills_json,
                            now,
                        ],
                    )?;
                }

                let row = c.query_row(
                    "SELECT session_id, name, description, version, url,
                            node, project, role, tag, cwd, pid,
                            capabilities_json, skills_json,
                            started_at, last_heartbeat_at
                     FROM agent_presence WHERE session_id = ?1",
                    params![session_id],
                    |r| {
                        let cap_s: Option<String> = r.get(11)?;
                        let sk_s: Option<String> = r.get(12)?;
                        Ok((
                            r.get::<_, String>(0)?,
                            r.get::<_, String>(1)?,
                            r.get::<_, Option<String>>(2)?,
                            r.get::<_, Option<String>>(3)?,
                            r.get::<_, Option<String>>(4)?,
                            r.get::<_, String>(5)?,
                            r.get::<_, String>(6)?,
                            r.get::<_, String>(7)?,
                            r.get::<_, Option<String>>(8)?,
                            r.get::<_, Option<String>>(9)?,
                            r.get::<_, Option<i64>>(10)?,
                            cap_s,
                            sk_s,
                            r.get::<_, i64>(13)?,
                            r.get::<_, i64>(14)?,
                        ))
                    },
                )?;
                let (sid, nm, desc, ver, url, nd, proj, rl, tg, cd, p, cap_s, sk_s, st, hb) = row;
                let capabilities = cap_s
                    .as_deref()
                    .and_then(|s| serde_json::from_str(s).ok());
                let skills = sk_s.as_deref().and_then(|s| serde_json::from_str(s).ok());
                Ok(AgentPresenceRecord {
                    session_id: sid,
                    name: nm,
                    description: desc,
                    version: ver,
                    url,
                    capabilities,
                    skills,
                    node: nd,
                    project: proj,
                    role: rl,
                    tag: tg,
                    cwd: cd,
                    pid: p,
                    started_at: st,
                    last_heartbeat_at: hb,
                })
            })
            .await
            .map_err(|e| match e {
                tokio_rusqlite::Error::Error(
                    tokio_rusqlite::rusqlite::Error::InvalidParameterName(field),
                ) => Error::Backend(format!(
                    "agent_presence_announce: missing required field on first announce — {field}"
                )),
                other => Error::Backend(format!("agent_presence_announce: {other}")),
            })?;
        Ok(row)
    }

    async fn agent_presence_list(
        &self,
        project: Option<&str>,
        role: Option<&str>,
        max_idle_secs: i64,
        limit: u32,
    ) -> Result<Vec<AgentPresenceRecord>> {
        let lim = i64::from(limit.clamp(1, 500));
        let cutoff = if max_idle_secs <= 0 {
            0
        } else {
            now_secs() - max_idle_secs
        };
        let project_f = project.map(|s| s.to_string());
        let role_f = role.map(|s| s.to_string());

        let rows = self
            .conn
            .call(move |c| -> RusqliteResult<Vec<_>> {
                let mut stmt = c.prepare(
                    "SELECT session_id, name, description, version, url,
                            node, project, role, tag, cwd, pid,
                            capabilities_json, skills_json,
                            started_at, last_heartbeat_at
                     FROM agent_presence
                     WHERE last_heartbeat_at >= ?1
                       AND (?2 IS NULL OR project = ?2)
                       AND (?3 IS NULL OR role    = ?3)
                     ORDER BY last_heartbeat_at DESC
                     LIMIT ?4",
                )?;
                let mut q = stmt.query(params![cutoff, project_f, role_f, lim])?;
                let mut out = Vec::new();
                while let Some(r) = q.next()? {
                    out.push((
                        r.get::<_, String>(0)?,
                        r.get::<_, String>(1)?,
                        r.get::<_, Option<String>>(2)?,
                        r.get::<_, Option<String>>(3)?,
                        r.get::<_, Option<String>>(4)?,
                        r.get::<_, String>(5)?,
                        r.get::<_, String>(6)?,
                        r.get::<_, String>(7)?,
                        r.get::<_, Option<String>>(8)?,
                        r.get::<_, Option<String>>(9)?,
                        r.get::<_, Option<i64>>(10)?,
                        r.get::<_, Option<String>>(11)?,
                        r.get::<_, Option<String>>(12)?,
                        r.get::<_, i64>(13)?,
                        r.get::<_, i64>(14)?,
                    ));
                }
                Ok(out)
            })
            .await
            .map_err(|e| Error::Backend(format!("agent_presence_list: {e}")))?;

        let mut out = Vec::with_capacity(rows.len());
        for (sid, nm, desc, ver, url, nd, proj, rl, tg, cd, p, cap_s, sk_s, st, hb) in rows {
            let capabilities = cap_s
                .as_deref()
                .and_then(|s| serde_json::from_str(s).ok());
            let skills = sk_s.as_deref().and_then(|s| serde_json::from_str(s).ok());
            out.push(AgentPresenceRecord {
                session_id: sid,
                name: nm,
                description: desc,
                version: ver,
                url,
                capabilities,
                skills,
                node: nd,
                project: proj,
                role: rl,
                tag: tg,
                cwd: cd,
                pid: p,
                started_at: st,
                last_heartbeat_at: hb,
            });
        }
        Ok(out)
    }

    async fn agent_presence_get(
        &self,
        session_id: &str,
    ) -> Result<Option<AgentPresenceRecord>> {
        let session_id = session_id.to_string();
        let row = self
            .conn
            .call(move |c| -> RusqliteResult<Option<_>> {
                c.query_row(
                    "SELECT session_id, name, description, version, url,
                            node, project, role, tag, cwd, pid,
                            capabilities_json, skills_json,
                            started_at, last_heartbeat_at
                     FROM agent_presence
                     WHERE session_id = ?1",
                    params![session_id],
                    |r| {
                        Ok((
                            r.get::<_, String>(0)?,
                            r.get::<_, String>(1)?,
                            r.get::<_, Option<String>>(2)?,
                            r.get::<_, Option<String>>(3)?,
                            r.get::<_, Option<String>>(4)?,
                            r.get::<_, String>(5)?,
                            r.get::<_, String>(6)?,
                            r.get::<_, String>(7)?,
                            r.get::<_, Option<String>>(8)?,
                            r.get::<_, Option<String>>(9)?,
                            r.get::<_, Option<i64>>(10)?,
                            r.get::<_, Option<String>>(11)?,
                            r.get::<_, Option<String>>(12)?,
                            r.get::<_, i64>(13)?,
                            r.get::<_, i64>(14)?,
                        ))
                    },
                )
                .optional()
            })
            .await
            .map_err(|e| Error::Backend(format!("agent_presence_get: {e}")))?;

        Ok(row.map(
            |(sid, nm, desc, ver, url, nd, proj, rl, tg, cd, p, cap_s, sk_s, st, hb)| {
                let capabilities = cap_s
                    .as_deref()
                    .and_then(|s| serde_json::from_str(s).ok());
                let skills = sk_s.as_deref().and_then(|s| serde_json::from_str(s).ok());
                AgentPresenceRecord {
                    session_id: sid,
                    name: nm,
                    description: desc,
                    version: ver,
                    url,
                    capabilities,
                    skills,
                    node: nd,
                    project: proj,
                    role: rl,
                    tag: tg,
                    cwd: cd,
                    pid: p,
                    started_at: st,
                    last_heartbeat_at: hb,
                }
            },
        ))
    }
}

impl SqliteStore {
    async fn codebase_search_semantic(
        &self,
        query: &str,
        kind: Option<&str>,
        file_filter: Option<&str>,
        root_path: Option<&str>,
        limit: u32,
    ) -> Result<Vec<CodebaseSymbol>> {
        let query_vec = crate::vector::embed_text(query);
        let kind_f = kind.map(|s| s.to_string());
        let file_f = file_filter.map(|s| format!("%{}%", s));
        let root_f = root_path.map(|s| s.to_string());
        let lim = limit.min(500) as usize;

        // Load all matching symbols with embeddings (no name filter — semantic scoring does that).
        let rows = self
            .conn
            .call(move |c| -> RusqliteResult<Vec<(CodebaseSymbol, Option<Vec<u8>>)>> {
                let mut stmt = c.prepare(
                    "SELECT file_path, line, col, kind, name, signature, language, embedding
                     FROM codebase_symbols
                     WHERE (?1 IS NULL OR kind = ?1)
                       AND (?2 IS NULL OR root_path = ?2)
                       AND (?3 IS NULL OR file_path LIKE ?3)",
                )?;
                let rows = stmt
                    .query_map(params![kind_f, root_f, file_f], |row| {
                        Ok((
                            CodebaseSymbol {
                                file_path: row.get(0)?,
                                line: row.get::<_, i64>(1)? as u32,
                                col: row.get::<_, i64>(2)? as u32,
                                kind: row.get(3)?,
                                name: row.get(4)?,
                                signature: row.get(5)?,
                                language: row.get(6)?,
                                score: None,
                            },
                            row.get::<_, Option<Vec<u8>>>(7)?,
                        ))
                    })?
                    .collect::<std::result::Result<Vec<_>, _>>()?;
                Ok(rows)
            })
            .await
            .map_err(|e| Error::Backend(format!("codebase_search_semantic load: {e}")))?;

        // Score and rank by cosine similarity.
        let mut scored: Vec<(f32, CodebaseSymbol)> = rows
            .into_iter()
            .filter_map(|(mut sym, emb_bytes)| {
                let bytes = emb_bytes?;
                let emb = crate::vector::decode_embedding(&bytes);
                let score = crate::vector::cosine_similarity(&query_vec, &emb);
                sym.score = Some(score);
                Some((score, sym))
            })
            .collect();

        // Deduplicate across overlapping root-path indexes: keep highest-scored
        // entry per (file_path, line, kind, name).
        scored.sort_by(|a, b| b.0.partial_cmp(&a.0).unwrap_or(std::cmp::Ordering::Equal));
        let mut seen = std::collections::HashSet::new();
        scored.retain(|(_, sym)| {
            seen.insert((sym.file_path.clone(), sym.line, sym.kind.clone(), sym.name.clone()))
        });
        scored.truncate(lim);

        Ok(scored.into_iter().map(|(_, sym)| sym).collect())
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::{MemoryListSort, PlanStep, StateStore};

    fn mk_record(key: &str, updated_at: i64) -> MemoryRecord {
        MemoryRecord {
            key: key.into(),
            kind: "fact".into(),
            content: format!("content-{key}"),
            tags: vec![],
            related_keys: vec![],
            scope: None,
            created_at: 1_700_000_000,
            updated_at,
            last_accessed_at: 0,
            access_count: 0,
            importance: 0.5,
            status: "active".into(),
            trigger_pattern: None,
            superseded_by: None,
        }
    }

    #[test]
    fn plan_import_actions_skip_existing_under_skip_policy() {
        // Regression: sync.sh re-imports the same JSONL every Stop hook.
        // Under Skip policy and pre-existing keys, every action must be Skip
        // so the caller never invokes the embedding backend.
        let parsed = vec![mk_record("k1", 100), mk_record("k2", 200)];
        let mut existing = std::collections::HashMap::new();
        existing.insert("k1".to_string(), 100);
        existing.insert("k2".to_string(), 200);
        let actions = plan_import_actions(&parsed, &existing, ImportConflictPolicy::Skip);
        assert_eq!(actions, vec![ImportAction::Skip, ImportAction::Skip]);
    }

    #[test]
    fn plan_import_actions_inserts_unknown_keys() {
        let parsed = vec![mk_record("new", 500), mk_record("known", 200)];
        let mut existing = std::collections::HashMap::new();
        existing.insert("known".to_string(), 200);
        let actions = plan_import_actions(&parsed, &existing, ImportConflictPolicy::Skip);
        assert_eq!(actions, vec![ImportAction::Insert, ImportAction::Skip]);
    }

    #[test]
    fn plan_import_actions_newer_wins_compares_updated_at() {
        let parsed = vec![
            mk_record("stale", 100),  // local 200 → keep local
            mk_record("fresh", 300),  // local 200 → take import
            mk_record("equal", 200),  // local 200 → keep local (strictly greater)
        ];
        let mut existing = std::collections::HashMap::new();
        existing.insert("stale".to_string(), 200);
        existing.insert("fresh".to_string(), 200);
        existing.insert("equal".to_string(), 200);
        let actions = plan_import_actions(&parsed, &existing, ImportConflictPolicy::NewerWins);
        assert_eq!(
            actions,
            vec![ImportAction::Skip, ImportAction::Update, ImportAction::Skip]
        );
    }

    #[test]
    fn plan_import_actions_overwrite_always_updates_existing() {
        let parsed = vec![mk_record("k1", 100)];
        let mut existing = std::collections::HashMap::new();
        existing.insert("k1".to_string(), 999);
        let actions = plan_import_actions(&parsed, &existing, ImportConflictPolicy::Overwrite);
        assert_eq!(actions, vec![ImportAction::Update]);
    }

    #[tokio::test]
    async fn memory_import_skip_all_does_not_disturb_existing_embeddings() {
        // End-to-end check that the pre-flight gate works: import the same
        // JSONL twice with Skip policy and verify the second pass touches
        // nothing (no embedding rewrite, accurate skipped count).
        let temp_dir = std::env::temp_dir().join(format!(
            "ab-import-skip-noop-{}",
            std::time::SystemTime::now()
                .duration_since(std::time::UNIX_EPOCH)
                .unwrap_or_default()
                .as_nanos()
        ));
        tokio::fs::create_dir_all(&temp_dir).await.expect("mkdir");
        let db_path = temp_dir.join("state.db");
        let store = SqliteStore::open(&db_path).await.expect("open store");

        let jsonl = temp_dir.join("rows.jsonl");
        let line = serde_json::to_string(&serde_json::json!({
            "key": "skip_noop_row",
            "kind": "fact",
            "content": "stable content for skip-path regression test",
            "tags": [],
            "related_keys": [],
            "scope": null,
            "created_at": 1_700_000_000_i64,
            "updated_at": 1_700_000_000_i64,
            "last_accessed_at": 0_i64,
            "access_count": 0_u64,
            "importance": 0.5,
            "status": "active",
            "trigger_pattern": null,
        }))
        .unwrap();
        tokio::fs::write(&jsonl, format!("{line}\n"))
            .await
            .expect("write jsonl");

        let r1 = store
            .memory_import(&jsonl, ImportConflictPolicy::Skip, None)
            .await
            .expect("first import");
        assert_eq!(r1.inserted, 1);
        assert_eq!(r1.skipped, 0);

        let r2 = store
            .memory_import(&jsonl, ImportConflictPolicy::Skip, None)
            .await
            .expect("second import");
        assert_eq!(r2.inserted, 0);
        assert_eq!(r2.updated, 0);
        assert_eq!(r2.skipped, 1);

        let _ = tokio::fs::remove_dir_all(&temp_dir).await;
    }

    #[tokio::test]
    async fn memory_save_reuses_embedding_when_content_unchanged() {
        // Preflight gate for memory_save: when an upsert hits an existing key
        // whose stored content is byte-identical to the new content, reuse the
        // existing embedding instead of paying embed_text again. We verify the
        // gate by writing a sentinel embedding in place, re-saving with the
        // same content, and asserting the sentinel survives. A subsequent save
        // with different content must recompute.
        let temp_dir = std::env::temp_dir().join(format!(
            "ab-msave-preflight-{}",
            std::time::SystemTime::now()
                .duration_since(std::time::UNIX_EPOCH)
                .unwrap_or_default()
                .as_nanos()
        ));
        let db_path = temp_dir.join("state.db");
        let store = SqliteStore::open(&db_path).await.expect("open store");

        let mut rec = mk_record("preflight_save_key", 1_700_000_000);
        rec.content = "stable content".into();
        store.memory_save(&rec).await.expect("first save");

        let sentinel = vec![0x42u8; crate::vector::VECTOR_DIM * 4];
        let sentinel_for_write = sentinel.clone();
        store
            .conn
            .call(move |c| -> RusqliteResult<()> {
                c.execute(
                    "UPDATE memories SET embedding = ?1 WHERE key = 'preflight_save_key'",
                    params![sentinel_for_write],
                )?;
                Ok(())
            })
            .await
            .expect("install sentinel");

        // Same content → preflight should reuse, sentinel survives.
        rec.tags = vec!["new-tag".into()];
        store.memory_save(&rec).await.expect("re-save same content");
        let reused: Vec<u8> = store
            .conn
            .call(|c| {
                c.query_row(
                    "SELECT embedding FROM memories WHERE key = 'preflight_save_key'",
                    [],
                    |row| row.get::<_, Option<Vec<u8>>>(0),
                )
                .map(|o| o.unwrap_or_default())
            })
            .await
            .expect("read reused");
        assert_eq!(reused, sentinel, "sentinel must survive same-content re-save");

        // Different content → must recompute (sentinel overwritten).
        rec.content = "different content now".into();
        store.memory_save(&rec).await.expect("re-save new content");
        let recomputed: Vec<u8> = store
            .conn
            .call(|c| {
                c.query_row(
                    "SELECT embedding FROM memories WHERE key = 'preflight_save_key'",
                    [],
                    |row| row.get::<_, Option<Vec<u8>>>(0),
                )
                .map(|o| o.unwrap_or_default())
            })
            .await
            .expect("read recomputed");
        assert_ne!(recomputed, sentinel, "sentinel must be replaced on content change");
        assert_eq!(recomputed.len(), crate::vector::VECTOR_DIM * 4);

        let _ = tokio::fs::remove_dir_all(&temp_dir).await;
    }

    #[tokio::test]
    async fn plan_save_load_update_roundtrip() {
        let temp_dir = std::env::temp_dir().join(format!(
            "ab-plan-test-{}",
            std::time::SystemTime::now()
                .duration_since(std::time::UNIX_EPOCH)
                .unwrap_or_default()
                .as_nanos()
        ));
        let db_path = temp_dir.join("state.db");
        let store = SqliteStore::open(&db_path)
            .await
            .expect("open sqlite store");

        let steps = vec![
            PlanStep {
                id: "a".into(),
                desc: "first".into(),
                status: "pending".into(),
                deps: vec![],
            },
            PlanStep {
                id: "b".into(),
                desc: "second".into(),
                status: "done".into(),
                deps: vec!["a".into()],
            },
        ];
        store
            .plan_save("p1", "title", &steps)
            .await
            .expect("plan_save");

        let loaded = store
            .plan_load("p1")
            .await
            .expect("plan_load")
            .expect("row");
        assert_eq!(loaded.title, "title");
        assert_eq!(loaded.steps.len(), 2);
        assert_eq!(loaded.created_at, loaded.updated_at);

        let ok = store
            .plan_update_step("p1", "a", "done")
            .await
            .expect("plan_update_step");
        assert!(ok);

        let loaded2 = store
            .plan_load("p1")
            .await
            .expect("plan_load2")
            .expect("row");
        assert_eq!(loaded2.steps[0].status, "done");
        assert!(loaded2.updated_at >= loaded2.created_at);

        let missing = store
            .plan_update_step("p1", "nope", "done")
            .await
            .expect("plan_update_step missing");
        assert!(!missing);

        let _ = tokio::fs::remove_dir_all(&temp_dir).await;
    }

    #[tokio::test]
    async fn agent_messages_send_inbox_roundtrip() {
        let temp_dir = std::env::temp_dir().join(format!(
            "ab-agent-msg-test-{}",
            std::time::SystemTime::now()
                .duration_since(std::time::UNIX_EPOCH)
                .unwrap_or_default()
                .as_nanos()
        ));
        let db_path = temp_dir.join("state.db");
        let store = SqliteStore::open(&db_path)
            .await
            .expect("open sqlite store");

        let payload = serde_json::json!({ "hello": "world", "n": 1 });
        let id = store
            .agent_message_send("sess-a", "sess-b", &payload)
            .await
            .expect("send");
        assert!(id > 0);

        let rows = store
            .agent_inbox_fetch("sess-b", None, false, 10)
            .await
            .expect("inbox");
        assert_eq!(rows.len(), 1);
        assert_eq!(rows[0].from_session, "sess-a");
        assert_eq!(rows[0].to_session, "sess-b");
        assert_eq!(rows[0].payload, payload);
        assert!(!rows[0].read);

        let empty = store
            .agent_inbox_fetch("sess-b", Some(id), false, 10)
            .await
            .expect("after_cursor");
        assert!(empty.is_empty());

        let _ = tokio::fs::remove_dir_all(&temp_dir).await;
    }

    #[tokio::test]
    async fn memory_search_falls_back_to_exact_key_match() {
        let temp_dir = std::env::temp_dir().join(format!(
            "ab-store-test-{}",
            std::time::SystemTime::now()
                .duration_since(std::time::UNIX_EPOCH)
                .unwrap_or_default()
                .as_nanos()
        ));
        let db_path = temp_dir.join("state.db");
        let store = SqliteStore::open(&db_path)
            .await
            .expect("open sqlite store");

        let rec = MemoryRecord {
            key: "probe_exact_key_fix_20260429".to_string(),
            kind: "context".to_string(),
            content: "regression test for exact key fallback".to_string(),
            tags: vec!["probe".to_string()],
            related_keys: vec![],
            scope: None,
            created_at: 0,
            updated_at: 0,
            last_accessed_at: 0,
            access_count: 0,
            importance: 0.5,
            status: "active".to_string(),
            trigger_pattern: None,
            superseded_by: None,
        };
        store.memory_save(&rec).await.expect("memory_save");

        let hits = store
            .memory_search("probe_exact_key_fix_20260429", &[], 5)
            .await
            .expect("memory_search");
        assert!(
            hits.iter()
                .any(|h| h.record.key == "probe_exact_key_fix_20260429"),
            "exact key should be found even when FTS tokenization misses it"
        );

        let list = store
            .list_memories(Some("context"), MemoryListSort::Recent, 10)
            .await
            .expect("list_memories");
        assert!(!list.is_empty());
    }

    #[tokio::test]
    async fn memory_trigger_pattern_roundtrip() {
        let temp_dir = std::env::temp_dir().join(format!(
            "ab-trigger-pat-test-{}",
            std::time::SystemTime::now()
                .duration_since(std::time::UNIX_EPOCH)
                .unwrap_or_default()
                .as_nanos()
        ));
        let db_path = temp_dir.join("state.db");
        let store = SqliteStore::open(&db_path)
            .await
            .expect("open sqlite store");

        let rec = MemoryRecord {
            key: "errpat_demo_signal_exit".to_string(),
            kind: "error_pattern".to_string(),
            content: "avoid SIGKILL during cargo test; use timeout".to_string(),
            tags: vec![],
            related_keys: vec![],
            scope: None,
            created_at: 0,
            updated_at: 0,
            last_accessed_at: 0,
            access_count: 0,
            importance: 0.5,
            status: "active".to_string(),
            trigger_pattern: Some("SIGKILL".to_string()),
            superseded_by: None,
        };
        store.memory_save(&rec).await.expect("memory_save");
        let loaded = store
            .memory_get("errpat_demo_signal_exit")
            .await
            .expect("memory_get")
            .expect("row");
        assert_eq!(loaded.trigger_pattern.as_deref(), Some("SIGKILL"));

        let _ = tokio::fs::remove_dir_all(&temp_dir).await;
    }

    #[tokio::test]
    async fn memory_import_populates_embedding_for_semantic_search() {
        use crate::ImportConflictPolicy;

        let temp_dir = std::env::temp_dir().join(format!(
            "ab-import-emb-{}",
            std::time::SystemTime::now()
                .duration_since(std::time::UNIX_EPOCH)
                .unwrap_or_default()
                .as_nanos()
        ));
        tokio::fs::create_dir_all(&temp_dir).await.expect("mkdir");
        let db_path = temp_dir.join("state.db");
        let store = SqliteStore::open(&db_path)
            .await
            .expect("open sqlite store");

        let jsonl_path = temp_dir.join("probe.jsonl");
        let line = serde_json::json!({
            "key": "import_sem_embed_ipc_warp_socket",
            "kind": "context",
            "content": "Warp terminal uses Unix IPC socket bridge agent-bridge for semantic vector recall testing",
            "tags": ["import-test"],
            "related_keys": [],
            "scope": null,
            "created_at": 1700000000_i64,
            "updated_at": 1700000000_i64,
            "last_accessed_at": 0_i64,
            "access_count": 0_u64,
            "importance": 0.5,
            "status": "active",
            "trigger_pattern": null,
        });
        tokio::fs::write(&jsonl_path, format!("{}\n", line))
            .await
            .expect("write jsonl");

        let report = store
            .memory_import(&jsonl_path, ImportConflictPolicy::Skip, None)
            .await
            .expect("import");
        assert!(report.inserted >= 1);

        let hits = store
            .memory_search_semantic("IPC socket warp bridge", 10, 0.25_f32)
            .await
            .expect("semantic search");
        assert!(
            hits.iter()
                .any(|h| h.record.key == "import_sem_embed_ipc_warp_socket"),
            "semantic search should find imported row; keys={:?}",
            hits.iter().map(|h| &h.record.key).collect::<Vec<_>>()
        );

        let _ = tokio::fs::remove_dir_all(&temp_dir).await;
    }

    #[tokio::test]
    async fn memory_export_import_roundtrip_edges_jsonl() {
        use crate::{ImportConflictPolicy, MemoryExportFilter, MemoryRecord};

        let temp_dir = std::env::temp_dir().join(format!(
            "ab-edge-rt-{}",
            std::time::SystemTime::now()
                .duration_since(std::time::UNIX_EPOCH)
                .unwrap_or_default()
                .as_nanos()
        ));
        tokio::fs::create_dir_all(&temp_dir).await.expect("mkdir");
        let db_path = temp_dir.join("state.db");
        let store = SqliteStore::open(&db_path)
            .await
            .expect("open sqlite store");

        let mk = |k: &str| MemoryRecord {
            key: k.to_string(),
            kind: "fact".to_string(),
            content: format!("content {k}"),
            tags: vec![],
            related_keys: vec![],
            scope: None,
            created_at: 1700000002,
            updated_at: 1700000002,
            last_accessed_at: 0,
            access_count: 0,
            importance: 0.5,
            status: "active".to_string(),
            trigger_pattern: None,
            superseded_by: None,
        };
        store.memory_save(&mk("edge_rt_a")).await.expect("save a");
        store.memory_save(&mk("edge_rt_b")).await.expect("save b");
        store
            .memory_link("edge_rt_a", "edge_rt_b", "relates", 1.0)
            .await
            .expect("link");

        let mem_out = temp_dir.join("mem.jsonl");
        let edges_out = temp_dir.join("edges.jsonl");
        let filter = MemoryExportFilter {
            edges_out_path: Some(edges_out.clone()),
            ..Default::default()
        };
        let res = store
            .memory_export(&filter, &mem_out)
            .await
            .expect("export");
        assert_eq!(res.memories_written, 2);
        assert_eq!(res.edges_written, 1);

        let db2 = temp_dir.join("state2.db");
        let store2 = SqliteStore::open(&db2).await.expect("open second store");
        let report = store2
            .memory_import(&mem_out, ImportConflictPolicy::Skip, Some(&edges_out))
            .await
            .expect("import");
        assert_eq!(report.inserted, 2);
        assert_eq!(report.edges_upserted, 1);

        let n = store2
            .memory_neighbors("edge_rt_a")
            .await
            .expect("neighbors");
        assert!(
            n.iter()
                .any(|e| e.to_key == "edge_rt_b" && e.edge_type == "relates"),
            "expected relates edge; got {n:?}"
        );

        let _ = tokio::fs::remove_dir_all(&temp_dir).await;
    }

    #[tokio::test]
    async fn dedupe_tag_collapses_duplicate_summaries_via_supersede() {
        // Phase 2 #2: when two records carry the same `dedupe:<id>` tag,
        // the newer save supersedes the older one (and back-links via
        // memory_edges 'supersedes' for traceability). Use case: P5 dream
        // replay where different LLMs summarize the same source cluster
        // on different runs and we want them to collapse to the latest.
        use crate::MemoryRecord;

        let temp_dir = std::env::temp_dir().join(format!(
            "ab-dedupe-tag-{}",
            std::time::SystemTime::now()
                .duration_since(std::time::UNIX_EPOCH)
                .unwrap_or_default()
                .as_nanos()
        ));
        tokio::fs::create_dir_all(&temp_dir).await.expect("mkdir");
        let db_path = temp_dir.join("state.db");
        let store = SqliteStore::open(&db_path).await.expect("open store");

        let mk = |key: &str, content: &str| MemoryRecord {
            key: key.to_string(),
            kind: "lesson".to_string(),
            content: content.to_string(),
            tags: vec!["dedupe:cluster:abc123".to_string(), "p5_replay".to_string()],
            related_keys: vec![],
            scope: None,
            created_at: 0,
            updated_at: 0,
            last_accessed_at: 0,
            access_count: 0,
            importance: 0.7,
            status: String::new(),
            trigger_pattern: None,
            superseded_by: None,
        };

        // Three different LLM-suggested keys for the same source cluster.
        store
            .memory_save(&mk("summary_v1_minimax", "minimax phrasing of the lesson"))
            .await
            .expect("save v1");
        store
            .memory_save(&mk("summary_v2_haiku", "haiku phrasing of the same lesson"))
            .await
            .expect("save v2");
        store
            .memory_save(&mk("summary_v3_qwen", "qwen phrasing of the same lesson"))
            .await
            .expect("save v3");

        // The latest save wins; the prior two are superseded with a
        // back-pointer to the winner.
        let v1 = store
            .memory_get("summary_v1_minimax")
            .await
            .expect("get v1")
            .expect("v1 exists");
        let v2 = store
            .memory_get("summary_v2_haiku")
            .await
            .expect("get v2")
            .expect("v2 exists");
        let v3 = store
            .memory_get("summary_v3_qwen")
            .await
            .expect("get v3")
            .expect("v3 exists");

        // Chain semantics: each save supersedes only currently-active
        // duplicates, so the supersede pointer forms a chain v1→v2→v3
        // rather than all losers pointing at the final winner. Following
        // the chain (v1.superseded_by → v2; v2.superseded_by → v3) leads
        // to the active record. memory_search filters status='active' so
        // the user only sees v3 either way — the chain is observable
        // only via memory_neighbors / direct memory_get.
        assert_eq!(v3.status, "active", "latest save stays active");
        assert_eq!(v1.status, "superseded", "v1 superseded in the chain");
        assert_eq!(v2.status, "superseded", "v2 superseded in the chain");
        assert_eq!(v1.superseded_by.as_deref(), Some("summary_v2_haiku"));
        assert_eq!(v2.superseded_by.as_deref(), Some("summary_v3_qwen"));

        // Edges record the chain (v1↔v2 and v2↔v3, not v1↔v3 directly).
        let v3_neighbors = store
            .memory_neighbors("summary_v3_qwen")
            .await
            .expect("neighbors v3");
        assert!(
            v3_neighbors
                .iter()
                .any(|e| e.edge_type == "supersedes" && e.to_key == "summary_v2_haiku"),
            "v3 must record supersedes->v2; got {:?}",
            v3_neighbors
        );
        let v2_neighbors = store
            .memory_neighbors("summary_v2_haiku")
            .await
            .expect("neighbors v2");
        assert!(
            v2_neighbors
                .iter()
                .any(|e| e.edge_type == "supersedes" && e.to_key == "summary_v1_minimax"),
            "v2 must record supersedes->v1; got {:?}",
            v2_neighbors
        );

        // A different dedupe tag is unaffected by the same-tag group.
        let other = MemoryRecord {
            key: "summary_other_cluster".to_string(),
            kind: "lesson".to_string(),
            content: "unrelated cluster summary".to_string(),
            tags: vec!["dedupe:cluster:xyz999".to_string()],
            related_keys: vec![],
            scope: None,
            created_at: 0,
            updated_at: 0,
            last_accessed_at: 0,
            access_count: 0,
            importance: 0.7,
            status: String::new(),
            trigger_pattern: None,
            superseded_by: None,
        };
        store.memory_save(&other).await.expect("save other");
        let other_after = store
            .memory_get("summary_other_cluster")
            .await
            .expect("get other")
            .expect("other exists");
        assert_eq!(
            other_after.status, "active",
            "different dedupe tag must not be pulled into the group"
        );
        let v3_after = store
            .memory_get("summary_v3_qwen")
            .await
            .expect("get v3 again")
            .expect("v3 still there");
        assert_eq!(
            v3_after.status, "active",
            "winner of a different dedupe group stays active"
        );

        // Substring safety: a tag like `dedupe:cluster:abc12345` (proper
        // superset of our `dedupe:cluster:abc123`) must NOT match the
        // group via the LIKE %"<tag>"% needle.
        let confusable = MemoryRecord {
            key: "summary_confusable_superstring".to_string(),
            kind: "lesson".to_string(),
            content: "should not collapse with the abc123 group".to_string(),
            tags: vec!["dedupe:cluster:abc12345".to_string()],
            related_keys: vec![],
            scope: None,
            created_at: 0,
            updated_at: 0,
            last_accessed_at: 0,
            access_count: 0,
            importance: 0.7,
            status: String::new(),
            trigger_pattern: None,
            superseded_by: None,
        };
        store.memory_save(&confusable).await.expect("save confusable");
        let v3_still = store
            .memory_get("summary_v3_qwen")
            .await
            .expect("get v3 third time")
            .expect("v3 still there");
        assert_eq!(
            v3_still.status, "active",
            "tag substring of another tag must not falsely supersede"
        );

        let _ = tokio::fs::remove_dir_all(&temp_dir).await;
    }

    #[tokio::test]
    async fn tombstone_propagates_through_export_import_and_resists_revival() {
        // Regression: before this change, memory_delete hard-DELETE'd the row,
        // so on the next sync round the remote node's jsonl re-imported the
        // record and "undeleted" it. Tombstone semantics: delete flips status
        // to 'tombstoned' + bumps updated_at; export carries the tombstone;
        // remote import respects NewerWins and refuses to revive.
        use crate::{ImportConflictPolicy, MemoryExportFilter, MemoryRecord};

        let temp_dir = std::env::temp_dir().join(format!(
            "ab-tomb-rt-{}",
            std::time::SystemTime::now()
                .duration_since(std::time::UNIX_EPOCH)
                .unwrap_or_default()
                .as_nanos()
        ));
        tokio::fs::create_dir_all(&temp_dir).await.expect("mkdir");

        // Node A: save a memory then delete it.
        let db_a = temp_dir.join("a.db");
        let store_a = SqliteStore::open(&db_a).await.expect("open a");
        store_a
            .memory_save(&MemoryRecord {
                key: "tomb_x".to_string(),
                kind: "fact".to_string(),
                content: "to be deleted".to_string(),
                tags: vec!["t".to_string()],
                related_keys: vec![],
                scope: None,
                created_at: 1700000010,
                updated_at: 1700000010,
                last_accessed_at: 0,
                access_count: 0,
                importance: 0.5,
                status: String::new(),
                trigger_pattern: None,
                superseded_by: None,
            })
            .await
            .expect("save");
        // Verify get returns it pre-delete.
        assert!(store_a.memory_get("tomb_x").await.expect("get").is_some());

        let deleted = store_a.memory_delete("tomb_x").await.expect("delete");
        assert!(deleted, "delete should report row was tombstoned");

        // get after delete: invisible to user.
        assert!(
            store_a.memory_get("tomb_x").await.expect("get").is_none(),
            "tombstoned key must not appear in memory_get"
        );
        // Idempotent: second delete is a no-op (status already tombstoned).
        let again = store_a.memory_delete("tomb_x").await.expect("delete2");
        assert!(!again, "second delete should report no change");

        // Export carries the tombstone.
        let mem_out = temp_dir.join("a.jsonl");
        let filter = MemoryExportFilter::default();
        let res = store_a
            .memory_export(&filter, &mem_out)
            .await
            .expect("export");
        assert_eq!(
            res.memories_written, 1,
            "tombstoned row must export so the deletion propagates"
        );
        let exported = tokio::fs::read_to_string(&mem_out).await.expect("read");
        assert!(
            exported.contains("\"status\":\"tombstoned\""),
            "exported jsonl should carry status=tombstoned, got: {exported}"
        );

        // Node B: import the jsonl, then verify the key is invisible.
        let db_b = temp_dir.join("b.db");
        let store_b = SqliteStore::open(&db_b).await.expect("open b");
        let report = store_b
            .memory_import(&mem_out, ImportConflictPolicy::NewerWins, None)
            .await
            .expect("import");
        assert_eq!(report.inserted, 1);
        assert!(
            store_b.memory_get("tomb_x").await.expect("get b").is_none(),
            "imported tombstone must not surface via memory_get"
        );

        // Now simulate a stale jsonl from before the delete (older
        // updated_at). Re-importing it under NewerWins must NOT revive
        // the tombstone — that was the original bug.
        let stale = temp_dir.join("stale.jsonl");
        let stale_record = MemoryRecord {
            key: "tomb_x".to_string(),
            kind: "fact".to_string(),
            content: "to be deleted".to_string(),
            tags: vec!["t".to_string()],
            related_keys: vec![],
            scope: None,
            created_at: 1700000010,
            updated_at: 1700000010, // older than the tombstone bump
            last_accessed_at: 0,
            access_count: 0,
            importance: 0.5,
            status: "active".to_string(),
            trigger_pattern: None,
            superseded_by: None,
        };
        tokio::fs::write(
            &stale,
            format!("{}\n", serde_json::to_string(&stale_record).unwrap()),
        )
        .await
        .expect("write stale");
        let report2 = store_b
            .memory_import(&stale, ImportConflictPolicy::NewerWins, None)
            .await
            .expect("reimport stale");
        assert_eq!(
            report2.skipped, 1,
            "stale active record must be skipped — not revive the tombstone"
        );
        assert!(
            store_b.memory_get("tomb_x").await.expect("get b2").is_none(),
            "tombstone must survive a stale-jsonl reimport (regression guard)"
        );

        // Resurrect path: memory_save with the same key flips status back to
        // 'active' (parallel to the existing 'superseded' resurrect logic).
        store_b
            .memory_save(&MemoryRecord {
                key: "tomb_x".to_string(),
                kind: "fact".to_string(),
                content: "back from the dead".to_string(),
                tags: vec![],
                related_keys: vec![],
                scope: None,
                created_at: 1700000010,
                updated_at: 1700001000, // newer than tombstone bump
                last_accessed_at: 0,
                access_count: 0,
                importance: 0.5,
                status: "active".to_string(),
                trigger_pattern: None,
                superseded_by: None,
            })
            .await
            .expect("resurrect save");
        let resurrected = store_b
            .memory_get("tomb_x")
            .await
            .expect("get post-resurrect");
        assert!(resurrected.is_some(), "save with same key resurrects");
        assert_eq!(resurrected.unwrap().status, "active");

        let _ = tokio::fs::remove_dir_all(&temp_dir).await;
    }

    #[tokio::test]
    async fn mcp_tool_errors_ring_prunes_and_recent_is_newest_first() {
        let temp_dir = std::env::temp_dir().join(format!(
            "ab-mcp-err-{}",
            std::time::SystemTime::now()
                .duration_since(std::time::UNIX_EPOCH)
                .unwrap_or_default()
                .as_nanos()
        ));
        tokio::fs::create_dir_all(&temp_dir).await.expect("mkdir");
        let db_path = temp_dir.join("state.db");
        let store = SqliteStore::open(&db_path)
            .await
            .expect("open sqlite store");

        for i in 0..102_u32 {
            store
                .record_mcp_tool_error("probe_tool", &format!("msg-{i}"))
                .await
                .expect("record");
        }

        let recent100 = store
            .recent_mcp_tool_errors(MCP_TOOL_ERROR_RING_CAP)
            .await
            .expect("recent 100");
        assert_eq!(
            recent100.len(),
            usize::try_from(MCP_TOOL_ERROR_RING_CAP).unwrap()
        );
        assert_eq!(recent100[0].message, "msg-101");
        assert_eq!(
            recent100[recent100.len() - 1].message,
            "msg-2",
            "oldest retained after 102 inserts"
        );

        let recent = store.recent_mcp_tool_errors(3).await.expect("recent");
        assert_eq!(recent.len(), 3);
        assert_eq!(recent[0].message, "msg-101");
        assert_eq!(recent[1].message, "msg-100");
        assert_eq!(recent[2].message, "msg-99");

        let _ = tokio::fs::remove_dir_all(&temp_dir).await;
    }

    // ── v18 forum tests ────────────────────────────────────────────────────

    async fn fresh_store(tag: &str) -> (std::path::PathBuf, SqliteStore) {
        let temp_dir = std::env::temp_dir().join(format!(
            "ab-forum-{tag}-{}",
            std::time::SystemTime::now()
                .duration_since(std::time::UNIX_EPOCH)
                .unwrap_or_default()
                .as_nanos()
        ));
        let db_path = temp_dir.join("state.db");
        let store = SqliteStore::open(&db_path)
            .await
            .expect("open sqlite store");
        (temp_dir, store)
    }

    #[tokio::test]
    async fn forum_post_creates_thread_then_appends() {
        let (dir, store) = fresh_store("create").await;

        // First call without thread_id → must create thread.
        let refs = serde_json::json!({"memory_keys": ["k1"], "files": ["x.rs"]});
        let out1 = store
            .forum_post(
                None,
                Some("design"),
                Some("Bridge protocol revision"),
                "cc-A",
                "finding",
                "initial proposal: switch stdio→sse",
                Some(&refs),
                Some(&["bridge".into(), "rfc".into()]),
            )
            .await
            .expect("create thread");
        assert!(out1.created_thread);
        assert!(out1.post_id > 0);

        // Append a reply from a second session.
        let out2 = store
            .forum_post(
                Some(out1.thread_id),
                None,
                None,
                "cc-B",
                "reply",
                "+1, but watch backpressure on the SSE side",
                None,
                None,
            )
            .await
            .expect("append");
        assert!(!out2.created_thread);
        assert_eq!(out2.thread_id, out1.thread_id);
        assert!(out2.post_id > out1.post_id);

        // Empty author / body must be rejected.
        assert!(store
            .forum_post(Some(out1.thread_id), None, None, "", "msg", "x", None, None)
            .await
            .is_err());
        assert!(store
            .forum_post(Some(out1.thread_id), None, None, "cc-A", "msg", "  ", None, None)
            .await
            .is_err());

        // Posting to nonexistent thread fails clearly.
        let err = store
            .forum_post(Some(9_999_999), None, None, "cc-A", "msg", "x", None, None)
            .await
            .expect_err("missing thread");
        assert!(format!("{err}").contains("not found"));

        let _ = tokio::fs::remove_dir_all(&dir).await;
    }

    #[tokio::test]
    async fn forum_read_cursor_and_subscription_advance() {
        let (dir, store) = fresh_store("cursor").await;
        let t = store
            .forum_post(
                None,
                Some("general"),
                Some("Daily standup"),
                "cc-A",
                "msg",
                "post-1",
                None,
                None,
            )
            .await
            .expect("create");
        let p1 = t.post_id;
        let p2 = store
            .forum_post(Some(t.thread_id), None, None, "cc-A", "msg", "post-2", None, None)
            .await
            .expect("p2")
            .post_id;
        let p3 = store
            .forum_post(Some(t.thread_id), None, None, "cc-B", "msg", "post-3", None, None)
            .await
            .expect("p3")
            .post_id;

        // Plain read returns all 3.
        let all = store
            .forum_read(Some(t.thread_id), None, None, None, 50)
            .await
            .expect("read all");
        assert_eq!(all.len(), 3);
        assert_eq!(all[0].id, p1);
        assert_eq!(all[2].id, p3);

        // since_post_id excludes equal id.
        let after_p1 = store
            .forum_read(Some(t.thread_id), None, Some(p1), None, 50)
            .await
            .expect("after p1");
        assert_eq!(after_p1.len(), 2);
        assert_eq!(after_p1[0].id, p2);

        // unread_for without subscription = same as no cursor.
        let unsub = store
            .forum_read(Some(t.thread_id), None, None, Some("cc-C"), 50)
            .await
            .expect("unsub");
        assert_eq!(unsub.len(), 3);

        // Subscribe cc-C, mark seen at p1, then unread_for advances after read.
        store
            .forum_subscribe("cc-C", "thread", &t.thread_id.to_string(), false)
            .await
            .expect("sub");
        store
            .forum_mark_seen("cc-C", "thread", &t.thread_id.to_string(), p1)
            .await
            .expect("mark seen");

        let unread1 = store
            .forum_read(Some(t.thread_id), None, None, Some("cc-C"), 50)
            .await
            .expect("unread1");
        assert_eq!(unread1.len(), 2, "should skip post-1");
        assert_eq!(unread1[0].id, p2);

        // After read, cursor auto-advanced to p3 → next read empty.
        let unread2 = store
            .forum_read(Some(t.thread_id), None, None, Some("cc-C"), 50)
            .await
            .expect("unread2");
        assert!(unread2.is_empty(), "cursor should have advanced");

        let _ = tokio::fs::remove_dir_all(&dir).await;
    }

    #[tokio::test]
    async fn forum_list_threads_unread_counts() {
        let (dir, store) = fresh_store("list").await;
        let t1 = store
            .forum_post(None, Some("general"), Some("T1"), "cc-A", "msg", "a", None, None)
            .await
            .expect("t1")
            .thread_id;
        let _ = store
            .forum_post(Some(t1), None, None, "cc-B", "msg", "b", None, None)
            .await
            .expect("t1.2");
        let t2 = store
            .forum_post(None, Some("general"), Some("T2"), "cc-A", "msg", "a", None, None)
            .await
            .expect("t2")
            .thread_id;

        // Without unread_for → no counts.
        let plain = store
            .forum_list_threads("general", None, None, 50)
            .await
            .expect("list");
        assert_eq!(plain.len(), 2);
        assert!(plain.iter().all(|t| t.unread_count.is_none()));

        // Subscribe cc-X to the board → all posts unread.
        store
            .forum_subscribe("cc-X", "board", "general", false)
            .await
            .expect("sub board");
        let withc = store
            .forum_list_threads("general", Some("cc-X"), None, 50)
            .await
            .expect("list with counts");
        let totals: i64 = withc.iter().filter_map(|t| t.unread_count).sum();
        assert_eq!(totals, 3, "all 3 posts unread");

        // Per-thread cursor on t1 wins over board cursor.
        store
            .forum_subscribe("cc-X", "thread", &t1.to_string(), false)
            .await
            .expect("sub thread");
        let last_t1 = store
            .forum_read(Some(t1), None, None, Some("cc-X"), 50)
            .await
            .expect("read t1")
            .last()
            .map(|p| p.id)
            .unwrap();
        // After reading t1 fully, t1's unread should be 0 even though board cursor untouched.
        let withc2 = store
            .forum_list_threads("general", Some("cc-X"), None, 50)
            .await
            .expect("list 2");
        let row_t1 = withc2.iter().find(|t| t.id == t1).unwrap();
        assert_eq!(row_t1.unread_count, Some(0));
        assert!(last_t1 > 0);

        // Status filter.
        store
            .forum_set_thread_status(t2, "resolved")
            .await
            .expect("status");
        let only_open = store
            .forum_list_threads("general", None, Some("open"), 50)
            .await
            .expect("filter");
        assert_eq!(only_open.len(), 1);
        assert_eq!(only_open[0].id, t1);

        let _ = tokio::fs::remove_dir_all(&dir).await;
    }

    // ── v19 presence tests ─────────────────────────────────────────────────

    #[tokio::test]
    async fn presence_announce_insert_then_heartbeat_only() {
        let (dir, store) = fresh_store("presence-hb").await;

        // First call must include all required fields.
        let first = store
            .agent_presence_announce(
                "host-a:agent-bridge:main",
                AgentPresenceUpsert {
                    name: Some("agent-bridge main"),
                    description: Some("v19 smoke"),
                    version: Some("0.1.0"),
                    node: Some("host-a"),
                    project: Some("agent-bridge"),
                    role: Some("main"),
                    pid: Some(1234),
                    capabilities: Some(&serde_json::json!({"forum": true})),
                    skills: Some(&serde_json::json!([{"id":"design","name":"design"}])),
                    ..Default::default()
                },
            )
            .await
            .expect("first announce");
        assert_eq!(first.session_id, "host-a:agent-bridge:main");
        assert_eq!(first.started_at, first.last_heartbeat_at);
        assert_eq!(first.pid, Some(1234));
        assert_eq!(
            first.capabilities,
            Some(serde_json::json!({"forum": true}))
        );

        // Sleep a moment to ensure heartbeat changes.
        tokio::time::sleep(std::time::Duration::from_millis(1100)).await;

        // Heartbeat-only refresh: omit everything except session_id.
        let second = store
            .agent_presence_announce(
                "host-a:agent-bridge:main",
                AgentPresenceUpsert::default(),
            )
            .await
            .expect("heartbeat");
        assert_eq!(second.name, "agent-bridge main", "kept prior name");
        assert_eq!(second.pid, Some(1234), "kept prior pid");
        assert!(
            second.last_heartbeat_at > first.last_heartbeat_at,
            "heartbeat advanced"
        );
        assert_eq!(
            second.started_at, first.started_at,
            "started_at preserved across heartbeats"
        );

        // Heartbeat-only on a session that doesn't exist must error clearly.
        let err = store
            .agent_presence_announce("ghost:proj:role", AgentPresenceUpsert::default())
            .await
            .expect_err("missing required");
        assert!(format!("{err}").to_lowercase().contains("required"));

        let _ = tokio::fs::remove_dir_all(&dir).await;
    }

    #[tokio::test]
    async fn presence_list_filter_and_ttl() {
        let (dir, store) = fresh_store("presence-list").await;
        for (sid, proj, role) in [
            ("host-a:agent-bridge:main", "agent-bridge", "main"),
            ("host-a:agent-bridge:reviewer", "agent-bridge", "reviewer"),
            ("host-b:AiOT:main", "AiOT", "main"),
        ] {
            store
                .agent_presence_announce(
                    sid,
                    AgentPresenceUpsert {
                        name: Some(sid),
                        node: Some(sid.split(':').next().unwrap()),
                        project: Some(proj),
                        role: Some(role),
                        ..Default::default()
                    },
                )
                .await
                .expect("ann");
        }

        let all = store
            .agent_presence_list(None, None, 300, 50)
            .await
            .expect("list all");
        assert_eq!(all.len(), 3);

        let only_ab = store
            .agent_presence_list(Some("agent-bridge"), None, 300, 50)
            .await
            .expect("by project");
        assert_eq!(only_ab.len(), 2);

        let only_main = store
            .agent_presence_list(None, Some("main"), 300, 50)
            .await
            .expect("by role");
        assert_eq!(only_main.len(), 2);

        let only_ab_main = store
            .agent_presence_list(Some("agent-bridge"), Some("main"), 300, 50)
            .await
            .expect("by both");
        assert_eq!(only_ab_main.len(), 1);
        assert_eq!(only_ab_main[0].session_id, "host-a:agent-bridge:main");

        // TTL=1 should drop everything we just inserted (they have heartbeat=now,
        // but cutoff = now-1; rows with heartbeat>=cutoff stay → all stay).
        // Use a far-past-cutoff trick: directly poke last_heartbeat_at via a manual
        // update is overkill — instead verify that max_idle_secs=0 returns all.
        let no_ttl = store
            .agent_presence_list(None, None, 0, 50)
            .await
            .expect("ttl 0");
        assert_eq!(no_ttl.len(), 3);

        let _ = tokio::fs::remove_dir_all(&dir).await;
    }

    #[tokio::test]
    async fn forum_refs_json_roundtrip() {
        let (dir, store) = fresh_store("refs").await;
        let refs = serde_json::json!({
            "memory_keys": ["k1", "k2"],
            "files": ["a.rs", "b.rs"],
            "parent_post_id": 42
        });
        let out = store
            .forum_post(
                None,
                Some("incidents"),
                Some("Hot path regression"),
                "cc-A",
                "finding",
                "see refs",
                Some(&refs),
                None,
            )
            .await
            .expect("create");
        let posts = store
            .forum_read(Some(out.thread_id), None, None, None, 50)
            .await
            .expect("read");
        assert_eq!(posts.len(), 1);
        assert_eq!(posts[0].refs, refs);

        let _ = tokio::fs::remove_dir_all(&dir).await;
    }

    #[tokio::test]
    async fn forum_export_import_roundtrip_dedupes() {
        // Simulate two devices: store-A creates a thread + post; we export,
        // then import the file into a fresh store-B (acting as the other
        // device) and verify the rows show up. Re-importing on the same
        // store must be idempotent (matched threads, skipped posts).
        let (dir_a, store_a) = fresh_store("forum-exp-a").await;
        let (dir_b, store_b) = fresh_store("forum-exp-b").await;

        let refs = serde_json::json!({"memory_keys": ["plan_v18"]});
        let t = store_a
            .forum_post(
                None,
                Some("design"),
                Some("Forum sync RFC"),
                "node-A:proj:main",
                "finding",
                "v1: append-only natural-key dedup",
                Some(&refs),
                Some(&["v18".into(), "sync".into()]),
            )
            .await
            .expect("create");
        store_a
            .forum_post(
                Some(t.thread_id),
                None,
                None,
                "node-A:proj:reviewer",
                "reply",
                "+1, looks idempotent",
                None,
                None,
            )
            .await
            .expect("reply");

        let out_file = dir_a.join("forum.jsonl");
        let exp = store_a
            .forum_export(&out_file)
            .await
            .expect("export");
        assert_eq!(exp.threads_written, 1);
        assert_eq!(exp.posts_written, 2);

        // Import into store-B (cold, no overlap) → both rows materialise.
        let rep1 = store_b
            .forum_import(&out_file)
            .await
            .expect("import cold");
        assert_eq!(rep1.threads_inserted, 1);
        assert_eq!(rep1.threads_matched, 0);
        assert_eq!(rep1.posts_inserted, 2);
        assert_eq!(rep1.posts_skipped, 0);

        let threads_b = store_b
            .forum_list_threads("design", None, None, 10)
            .await
            .expect("list");
        assert_eq!(threads_b.len(), 1);
        assert_eq!(threads_b[0].title, "Forum sync RFC");
        assert_eq!(threads_b[0].post_count, 2);
        let posts_b = store_b
            .forum_read(Some(threads_b[0].id), None, None, None, 50)
            .await
            .expect("read");
        assert_eq!(posts_b[0].refs, refs);

        // Re-importing the same file on store-B must be a no-op (matched
        // thread + skipped posts). This is the property that makes the
        // Stop hook safe to fire repeatedly.
        let rep2 = store_b
            .forum_import(&out_file)
            .await
            .expect("import warm");
        assert_eq!(rep2.threads_inserted, 0);
        assert_eq!(rep2.threads_matched, 1);
        assert_eq!(rep2.posts_inserted, 0);
        assert_eq!(rep2.posts_skipped, 2);

        // Importing on store-A (the origin) must also be a no-op — same logic.
        let rep3 = store_a
            .forum_import(&out_file)
            .await
            .expect("import origin");
        assert_eq!(rep3.threads_inserted, 0);
        assert_eq!(rep3.threads_matched, 1);
        assert_eq!(rep3.posts_inserted, 0);
        assert_eq!(rep3.posts_skipped, 2);

        let _ = tokio::fs::remove_dir_all(&dir_a).await;
        let _ = tokio::fs::remove_dir_all(&dir_b).await;
    }

    #[tokio::test]
    async fn forum_export_missing_file_import_returns_zero() {
        // Cold-start sync: forum.jsonl doesn't exist yet → import is a no-op.
        let (dir, store) = fresh_store("forum-cold").await;
        let missing = dir.join("does-not-exist.jsonl");
        let rep = store.forum_import(&missing).await.expect("import missing");
        assert_eq!(rep.threads_inserted, 0);
        assert_eq!(rep.posts_inserted, 0);
        assert_eq!(rep.malformed, 0);
        let _ = tokio::fs::remove_dir_all(&dir).await;
    }

    // ── v21 α — Synaptic Trace tests ───────────────────────────────

    fn make_memrec(key: &str, content: &str) -> MemoryRecord {
        MemoryRecord {
            key: key.to_string(),
            kind: "fact".to_string(),
            content: content.to_string(),
            tags: vec![],
            related_keys: vec![],
            scope: None,
            created_at: 1_700_000_000,
            updated_at: 1_700_000_000,
            last_accessed_at: 0,
            access_count: 0,
            importance: 0.5,
            status: "active".to_string(),
            trigger_pattern: None,
            superseded_by: None,
        }
    }

    #[tokio::test]
    async fn coactivation_record_and_top_basic() {
        // Save 3 memories, record co-activation across all 3 → 3 pairs
        // ((a,b), (a,c), (b,c)) each with count=1. top_coactivation('a')
        // returns 2 edges.
        let (dir, store) = fresh_store("coact-basic").await;
        for k in ["alpha", "bravo", "charlie"] {
            store
                .memory_save(&make_memrec(k, &format!("content for {k}")))
                .await
                .expect("save");
        }

        store
            .record_coactivation(
                &[
                    "alpha".to_string(),
                    "bravo".to_string(),
                    "charlie".to_string(),
                ],
                None,
            )
            .await
            .expect("record");

        let edges = store.top_coactivation("alpha", 10).await.expect("top");
        assert_eq!(edges.len(), 2, "alpha co-activated with bravo + charlie");
        for e in &edges {
            assert_eq!(e.count, 1);
            assert!(e.key_a < e.key_b, "pair must be normalized lex order");
        }

        let edges_b = store.top_coactivation("bravo", 10).await.expect("top");
        assert_eq!(edges_b.len(), 2);

        let _ = tokio::fs::remove_dir_all(&dir).await;
    }

    #[test]
    fn p3_kind_aware_decay_observation_falls_faster_than_decision() {
        // Same age (30 days) — observation (τ=7) should be heavily decayed,
        // decision (τ=90) barely. Demonstrates the kind-aware τ behavior.
        let now = 1_000_000_000_i64;
        let thirty_days_ago = now - 30 * 86_400;
        let obs = memory_score(thirty_days_ago, 0, now, "observation");
        let dec = memory_score(thirty_days_ago, 0, now, "decision");
        let fact = memory_score(thirty_days_ago, 0, now, "fact");

        // observation: exp(-30/7) ≈ 0.0136
        // fact:        exp(-30/30) = 0.3679
        // decision:    exp(-30/90) ≈ 0.7165
        assert!(obs < 0.05, "observation 30d old should be heavily decayed: {obs}");
        assert!(dec > 0.7, "decision 30d old should still rank high: {dec}");
        assert!(obs < fact && fact < dec, "ordering observation < fact < decision");

        // Sanity: same kind, recent vs old. Today's observation > 30d-old observation.
        let obs_now = memory_score(now, 0, now, "observation");
        assert!(obs_now > obs);
    }

    #[test]
    fn p3_decay_tau_days_known_kinds_have_expected_constants() {
        // Lock the table so future-me doesn't accidentally rebalance it
        // without thinking about which kinds get faster/slower decay.
        assert_eq!(decay_tau_days("observation"), 7.0);
        assert_eq!(decay_tau_days("note"), 7.0);
        assert_eq!(decay_tau_days("todo"), 14.0);
        assert_eq!(decay_tau_days("action"), 14.0);
        assert_eq!(decay_tau_days("fact"), 30.0);
        assert_eq!(decay_tau_days("context"), 30.0);
        assert_eq!(decay_tau_days("session_handoff"), 30.0);
        assert_eq!(decay_tau_days("lesson"), 60.0);
        assert_eq!(decay_tau_days("error_pattern"), 60.0);
        assert_eq!(decay_tau_days("decision"), 90.0);
        assert_eq!(decay_tau_days("architecture"), 90.0);
        // Unknown kind falls back to 30d (same as fact/context).
        assert_eq!(decay_tau_days("xyz_unknown"), 30.0);
    }

    #[tokio::test]
    async fn memory_save_supersede_sets_pointer_back_to_new_key() {
        // **Phase 1 P2** — when memory_save's auto-supersede path fires
        // (token overlap > 0.5), the OLD row should get
        // `superseded_by = <new_key>` in addition to status='superseded'.
        // Without the pointer, callers had to traverse memory_edges to
        // discover what replaced a retired record.
        let (dir, store) = fresh_store("supersede-pointer").await;

        // Save the original. Distinct kind to make supersede candidate
        // discovery deterministic (kind filter in supersede SQL).
        let mut old = make_memrec(
            "lesson_path_c_v01",
            "Path C actuator v01 design rationale build at /tmp/agent-bridge-pathc \
             with SEED_BOOST_FACTOR 1.20 and Mac-targeted deploy recipe",
        );
        old.kind = "lesson".into();
        store.memory_save(&old).await.expect("save old");

        // Save a near-superset memory with same kind + same scope. Token
        // overlap is high (sharing all the path-c-actuator vocabulary)
        // so token_overlap_ratio > 0.5 should fire the supersede path.
        let mut new = make_memrec(
            "lesson_path_c_v02",
            "Path C actuator v02 design rationale build at /tmp/agent-bridge-pathc-v02 \
             with SEED_BOOST_FACTOR 1.20 and Mac-targeted deploy recipe \
             plus revised hub_clusters consumer wiring",
        );
        new.kind = "lesson".into();
        store.memory_save(&new).await.expect("save new");

        // The OLD record must now be superseded with pointer to NEW.
        let retired = store
            .memory_get("lesson_path_c_v01")
            .await
            .expect("get old");
        // Even superseded records are returned by memory_get — only
        // memory_search filters them out via status='active'.
        let retired = retired.expect("old still readable");
        assert_eq!(retired.status, "superseded");
        assert_eq!(
            retired.superseded_by.as_deref(),
            Some("lesson_path_c_v02"),
            "supersede pointer must name the replacement key"
        );

        // The NEW record must remain active and have NULL pointer.
        let live = store
            .memory_get("lesson_path_c_v02")
            .await
            .expect("get new")
            .expect("new exists");
        assert_eq!(live.status, "active");
        assert!(live.superseded_by.is_none());

        let _ = tokio::fs::remove_dir_all(&dir).await;
    }

    #[tokio::test]
    async fn coactivation_among_returns_pairs_with_both_endpoints_in_set() {
        // Setup: 4 memories alpha/bravo/charlie/delta. Record activations
        // [alpha, bravo, charlie] (3 pairs) and separately [bravo, delta]
        // (1 pair). Query coactivation_among({alpha, bravo, charlie}) →
        // must return only the 3 pairs whose BOTH endpoints are in the
        // input set. The bravo↔delta pair is filtered out because delta
        // is not in the query set.
        let (dir, store) = fresh_store("coact-among").await;
        for k in ["alpha", "bravo", "charlie", "delta"] {
            store.memory_save(&make_memrec(k, k)).await.expect("save");
        }

        store
            .record_coactivation(
                &["alpha".to_string(), "bravo".to_string(), "charlie".to_string()],
                None,
            )
            .await
            .expect("rec 1");
        store
            .record_coactivation(
                &["bravo".to_string(), "delta".to_string()],
                None,
            )
            .await
            .expect("rec 2");

        let edges = store
            .coactivation_among(&[
                "alpha".to_string(),
                "bravo".to_string(),
                "charlie".to_string(),
            ])
            .await
            .expect("among");
        assert_eq!(edges.len(), 3, "alpha-bravo, alpha-charlie, bravo-charlie");
        for e in &edges {
            assert!(
                e.key_a == "alpha" || e.key_a == "bravo" || e.key_a == "charlie",
                "key_a {} not in input set", e.key_a
            );
            assert!(
                e.key_b == "alpha" || e.key_b == "bravo" || e.key_b == "charlie",
                "key_b {} not in input set", e.key_b
            );
            assert_ne!(e.key_a, "delta");
            assert_ne!(e.key_b, "delta");
            assert_eq!(e.count, 1);
        }

        // Single-key set short-circuits to empty (need at least 2 keys
        // for any edge to qualify).
        let none = store
            .coactivation_among(&["alpha".to_string()])
            .await
            .expect("among 1");
        assert!(none.is_empty());

        // Empty input must not crash and returns empty.
        let none = store.coactivation_among(&[]).await.expect("among 0");
        assert!(none.is_empty());

        let _ = tokio::fs::remove_dir_all(&dir).await;
    }

    #[tokio::test]
    async fn coactivation_pair_normalized_and_count_increments() {
        // Calling with [b, a] then [a, b] must hit the same row (a < b
        // normalized), final count = 2.
        let (dir, store) = fresh_store("coact-norm").await;
        for k in ["delta", "echo"] {
            store
                .memory_save(&make_memrec(k, &format!("content for {k}")))
                .await
                .expect("save");
        }

        store
            .record_coactivation(&["echo".to_string(), "delta".to_string()], None)
            .await
            .expect("record 1");
        store
            .record_coactivation(&["delta".to_string(), "echo".to_string()], None)
            .await
            .expect("record 2");

        let edges = store.top_coactivation("delta", 10).await.expect("top");
        assert_eq!(edges.len(), 1);
        assert_eq!(edges[0].count, 2, "two recordings of same pair → count=2");
        assert_eq!(edges[0].key_a, "delta");
        assert_eq!(edges[0].key_b, "echo");

        let _ = tokio::fs::remove_dir_all(&dir).await;
    }

    #[tokio::test]
    async fn coactivation_dedupes_within_single_call() {
        // A single call with duplicates — must collapse to unique pairs only.
        let (dir, store) = fresh_store("coact-dedup").await;
        for k in ["foxtrot", "golf"] {
            store
                .memory_save(&make_memrec(k, &format!("content for {k}")))
                .await
                .expect("save");
        }

        store
            .record_coactivation(
                &[
                    "foxtrot".to_string(),
                    "foxtrot".to_string(),
                    "golf".to_string(),
                    "golf".to_string(),
                ],
                None,
            )
            .await
            .expect("record");

        let edges = store.top_coactivation("foxtrot", 10).await.expect("top");
        assert_eq!(edges.len(), 1);
        assert_eq!(edges[0].count, 1, "dedupe → single (foxtrot, golf) pair");

        let _ = tokio::fs::remove_dir_all(&dir).await;
    }

    #[tokio::test]
    async fn coactivation_below_two_keys_is_noop() {
        // Calling with 0 or 1 keys must be a no-op (no rows, no error).
        let (dir, store) = fresh_store("coact-noop").await;
        store.record_coactivation(&[], None).await.expect("zero ok");
        store
            .record_coactivation(&["only_one".to_string()], None)
            .await
            .expect("one ok");
        let edges = store.top_coactivation("only_one", 10).await.expect("top");
        assert!(edges.is_empty(), "no pairs from <2 keys");
        let _ = tokio::fs::remove_dir_all(&dir).await;
    }

    #[tokio::test]
    async fn coactivation_fk_cascade_on_memory_delete() {
        // Deleting one memory drops its co-activation rows (FK ON DELETE CASCADE).
        let (dir, store) = fresh_store("coact-fk").await;
        for k in ["hotel", "india", "juliet"] {
            store
                .memory_save(&make_memrec(k, &format!("content for {k}")))
                .await
                .expect("save");
        }
        store
            .record_coactivation(
                &[
                    "hotel".to_string(),
                    "india".to_string(),
                    "juliet".to_string(),
                ],
                None,
            )
            .await
            .expect("record");
        let before = store.top_coactivation("india", 10).await.expect("before");
        assert_eq!(before.len(), 2);

        store.memory_delete("india").await.expect("delete india");
        let after = store.top_coactivation("hotel", 10).await.expect("after");
        // hotel's only remaining edge should be (hotel, juliet); india edges gone.
        assert_eq!(after.len(), 1);
        assert!(
            (after[0].key_a == "hotel" && after[0].key_b == "juliet")
                || (after[0].key_a == "juliet" && after[0].key_b == "hotel")
        );

        let _ = tokio::fs::remove_dir_all(&dir).await;
    }

    #[tokio::test]
    async fn coactivation_ctx_centroid_rolling_mean() {
        // First call with ctx [1, 0, 0]; second call with ctx [3, 0, 0].
        // count=2 → stored centroid should be (1*1 + 3) / 2 = 2 in dim 0.
        // Pad to VECTOR_DIM with zeros to satisfy encode/decode roundtrip.
        let (dir, store) = fresh_store("coact-ctx").await;
        for k in ["kilo", "lima"] {
            store
                .memory_save(&make_memrec(k, &format!("content for {k}")))
                .await
                .expect("save");
        }

        let mut v1 = vec![0.0_f32; crate::vector::VECTOR_DIM];
        v1[0] = 1.0;
        let mut v2 = vec![0.0_f32; crate::vector::VECTOR_DIM];
        v2[0] = 3.0;

        store
            .record_coactivation(&["kilo".to_string(), "lima".to_string()], Some(&v1))
            .await
            .expect("first");
        store
            .record_coactivation(&["kilo".to_string(), "lima".to_string()], Some(&v2))
            .await
            .expect("second");

        // Verify the count incremented to 2 — centroid blob is internal,
        // verified via shape only (BLOB present + decodable).
        let edges = store.top_coactivation("kilo", 10).await.expect("top");
        assert_eq!(edges.len(), 1);
        assert_eq!(edges[0].count, 2);
        let _ = tokio::fs::remove_dir_all(&dir).await;
    }

    #[tokio::test]
    async fn coactivation_stats_empty_db() {
        // Fresh store → all-zeros stats, no panic on empty.
        let (dir, store) = fresh_store("coact-stats-empty").await;
        let stats = store.coactivation_stats().await.expect("stats");
        assert_eq!(stats.total_pairs, 0);
        assert_eq!(stats.total_unique_keys, 0);
        assert_eq!(stats.max_count, 0);
        assert_eq!(stats.median_count, 0.0);
        assert_eq!(stats.top10_to_median_ratio, 0.0);
        assert!(stats.top_5_edges.is_empty());
        let _ = tokio::fs::remove_dir_all(&dir).await;
    }

    #[tokio::test]
    async fn coactivation_stats_basic_aggregates() {
        // Build a graph with known shape:
        //   pair (a, b) co-activated 3 times → count=3
        //   pair (a, c) co-activated 1 time  → count=1
        //   pair (b, c) co-activated 1 time  → count=1
        // total_pairs=3, max=3, median=1, top10_avg = (3+1+1)/3 = 1.667,
        // ratio = 1.667 / 1 = 1.667 (well below β trigger 5.0).
        let (dir, store) = fresh_store("coact-stats-basic").await;
        for k in ["papa", "quebec", "romeo"] {
            store
                .memory_save(&make_memrec(k, &format!("content for {k}")))
                .await
                .expect("save");
        }
        for _ in 0..3 {
            store
                .record_coactivation(
                    &["papa".to_string(), "quebec".to_string()],
                    None,
                )
                .await
                .expect("record p+q");
        }
        store
            .record_coactivation(&["papa".to_string(), "romeo".to_string()], None)
            .await
            .expect("record p+r");
        store
            .record_coactivation(&["quebec".to_string(), "romeo".to_string()], None)
            .await
            .expect("record q+r");

        let stats = store.coactivation_stats().await.expect("stats");
        assert_eq!(stats.total_pairs, 3);
        assert_eq!(stats.total_unique_keys, 3);
        assert_eq!(stats.max_count, 3);
        assert_eq!(stats.median_count, 1.0, "median of (3,1,1) sorted is 1");
        let top10_avg = (3.0 + 1.0 + 1.0) / 3.0;
        assert!(
            (stats.top10_avg_count - top10_avg).abs() < 1e-6,
            "top10_avg expected {top10_avg}, got {}",
            stats.top10_avg_count
        );
        assert!(
            (stats.top10_to_median_ratio - top10_avg).abs() < 1e-6,
            "ratio = top10_avg / median(=1) = {top10_avg}, got {}",
            stats.top10_to_median_ratio
        );
        assert!(
            stats.top10_to_median_ratio < 5.0,
            "uniform graph should NOT trigger β"
        );
        assert_eq!(stats.top_5_edges.len(), 3);
        assert_eq!(stats.top_5_edges[0].count, 3, "highest count first");

        let _ = tokio::fs::remove_dir_all(&dir).await;
    }

    #[tokio::test]
    async fn coactivation_stats_β_trigger_threshold() {
        // 1 pair with count=10, 9 pairs with count=1 each.
        // median=1, top10_avg=(10+9*1)/10=1.9 → ratio=1.9 (still below 5)
        // Then push 5 more activations on the hot pair to count=15.
        // top10_avg=(15+9*1)/10=2.4 → still below 5.
        // To clear β=5: need top10 avg ≥ 5×median. With median=1 and 1
        // dominant pair carrying 50+ count, top10_avg would be ≥5.
        // We construct exactly that.
        let (dir, store) = fresh_store("coact-stats-trigger").await;
        // 11 keys → enough to make 10 minor pairs + 1 hot pair.
        let keys: Vec<String> = (0..11).map(|i| format!("node{i}")).collect();
        for k in &keys {
            store
                .memory_save(&make_memrec(k, &format!("content for {k}")))
                .await
                .expect("save");
        }
        // Hot pair (node0, node1) → count=50.
        for _ in 0..50 {
            store
                .record_coactivation(&[keys[0].clone(), keys[1].clone()], None)
                .await
                .expect("hot");
        }
        // 9 minor pairs each count=1.
        for i in 2..11 {
            store
                .record_coactivation(&[keys[0].clone(), keys[i].clone()], None)
                .await
                .expect("minor");
        }

        let stats = store.coactivation_stats().await.expect("stats");
        assert_eq!(stats.total_pairs, 10);
        assert_eq!(stats.max_count, 50);
        assert_eq!(stats.median_count, 1.0);
        // top10_avg = (50 + 9*1) / 10 = 5.9
        assert!(
            (stats.top10_avg_count - 5.9).abs() < 1e-6,
            "expected top10_avg=5.9, got {}",
            stats.top10_avg_count
        );
        assert!(
            stats.top10_to_median_ratio >= 5.0,
            "this graph SHOULD clear β trigger 5.0×, got {}",
            stats.top10_to_median_ratio
        );

        let _ = tokio::fs::remove_dir_all(&dir).await;
    }

    #[tokio::test]
    async fn coactivation_ordered_by_count_desc() {
        // Pair (a, b) co-activated 3 times; pair (a, c) co-activated 1 time.
        // top_coactivation('a') should return (a, b) before (a, c).
        let (dir, store) = fresh_store("coact-order").await;
        for k in ["mike", "november", "oscar"] {
            store
                .memory_save(&make_memrec(k, &format!("content for {k}")))
                .await
                .expect("save");
        }
        for _ in 0..3 {
            store
                .record_coactivation(
                    &["mike".to_string(), "november".to_string()],
                    None,
                )
                .await
                .expect("record m+n");
        }
        store
            .record_coactivation(&["mike".to_string(), "oscar".to_string()], None)
            .await
            .expect("record m+o");

        let edges = store.top_coactivation("mike", 10).await.expect("top");
        assert_eq!(edges.len(), 2);
        assert_eq!(edges[0].count, 3, "highest count first");
        assert!(
            edges[0].key_a == "mike" && edges[0].key_b == "november"
                || edges[0].key_a == "november" && edges[0].key_b == "mike"
        );
        assert_eq!(edges[1].count, 1);

        let _ = tokio::fs::remove_dir_all(&dir).await;
    }

    #[tokio::test]
    async fn codebase_reindex_fills_null_embeddings_and_unblocks_semantic_search() {
        // codebase_index writes rows with embedding=NULL by design; without a
        // fill path semantic search returns 0 results. This regression-locks
        // codebase_reindex_embeddings as the only thing that turns those rows
        // into searchable vectors, plus its idempotence (no-NULL → returns 0).
        let temp_dir = std::env::temp_dir().join(format!(
            "ab-codebase-reindex-{}-{}",
            std::process::id(),
            std::time::SystemTime::now()
                .duration_since(std::time::UNIX_EPOCH)
                .unwrap_or_default()
                .as_nanos()
        ));
        let db_path = temp_dir.join("state.db");
        let store = SqliteStore::open(&db_path).await.expect("open store");

        // Seed 3 symbol rows directly (codebase_index requires real files on
        // disk; we only need rows in the table for this test).
        store
            .conn
            .call(|c| -> RusqliteResult<()> {
                let mut stmt = c.prepare(
                    "INSERT INTO codebase_symbols
                       (file_path, line, col, kind, name, signature, language, root_path,
                        indexed_at, embedding)
                     VALUES (?1, ?2, 0, ?3, ?4, ?5, 'rust', '/tmp/x', 1, NULL)",
                )?;
                stmt.execute(params![
                    "src/lib.rs",
                    1_i64,
                    "fn",
                    "open_browser_tab",
                    "fn open_browser_tab(url: &str) -> Result<()>"
                ])?;
                stmt.execute(params![
                    "src/lib.rs",
                    20_i64,
                    "fn",
                    "embed_text",
                    "fn embed_text(text: &str) -> Vec<f32>"
                ])?;
                stmt.execute(params![
                    "src/lib.rs",
                    50_i64,
                    "struct",
                    "ParseResult",
                    "struct ParseResult { tokens: Vec<Token> }"
                ])?;
                Ok(())
            })
            .await
            .expect("seed rows");

        // Reindex — must fill all 3 NULL embeddings on the first call.
        let updated = store
            .codebase_reindex_embeddings(100)
            .await
            .expect("reindex");
        assert_eq!(updated, 3);

        // Each row now carries 1536 bytes (384-dim f32 LE).
        let lengths: Vec<i64> = store
            .conn
            .call(|c| -> RusqliteResult<Vec<i64>> {
                let mut stmt =
                    c.prepare("SELECT length(embedding) FROM codebase_symbols ORDER BY id")?;
                let rows = stmt
                    .query_map([], |r| r.get::<_, i64>(0))?
                    .collect::<std::result::Result<Vec<_>, _>>()?;
                Ok(rows)
            })
            .await
            .expect("read lengths");
        let expected = (crate::vector::VECTOR_DIM * 4) as i64;
        for len in &lengths {
            assert_eq!(*len, expected);
        }

        // Idempotent: with no NULL rows left, second call updates 0.
        let updated2 = store
            .codebase_reindex_embeddings(100)
            .await
            .expect("reindex 2");
        assert_eq!(updated2, 0);

        // Sanity: codebase_search(mode=semantic) now returns rows (was 0
        // before because all embeddings were NULL).
        let hits = store
            .codebase_search("function that opens a browser", None, None, None, 10, "semantic")
            .await
            .expect("search");
        assert!(
            !hits.is_empty(),
            "semantic search should return rows once embeddings are filled"
        );

        let _ = tokio::fs::remove_dir_all(&temp_dir).await;
    }

    // ── Phase 0 memory telemetry: record_memory_query / memory_query_stats ──

    fn mk_query_record(kind: &str, q: &str, hits: u32, age: Option<i64>, dur_us: u32, at: i64)
        -> MemoryQueryRecord
    {
        MemoryQueryRecord {
            kind: kind.to_string(),
            query: q.to_string(),
            tags_json: "[]".to_string(),
            hit_count: hits,
            top_hit_age_secs: age,
            top_hit_created_at: age.map(|a| at - a),
            duration_us: dur_us,
            source: "test".to_string(),
            at,
        }
    }

    #[tokio::test]
    async fn record_memory_query_persists_and_aggregates() {
        let temp_dir = std::env::temp_dir().join(format!(
            "ab-mem-query-log-{}-{}",
            std::process::id(),
            std::time::SystemTime::now()
                .duration_since(std::time::UNIX_EPOCH)
                .unwrap_or_default()
                .as_nanos()
        ));
        let db_path = temp_dir.join("state.db");
        let store = SqliteStore::open(&db_path).await.expect("open");

        let now = now_secs();
        // 4 hits + 2 misses, mixed kinds, varying durations
        store.record_memory_query(&mk_query_record("search_fts", "rust", 3, Some(86_400), 1500, now - 60))
            .await.expect("rec 1");
        store.record_memory_query(&mk_query_record("search_fts", "rust", 1, Some(7200), 800, now - 50))
            .await.expect("rec 2");
        store.record_memory_query(&mk_query_record("search_hybrid", "warp ipc", 2, Some(3600), 2200, now - 40))
            .await.expect("rec 3");
        store.record_memory_query(&mk_query_record("search_semantic", "neural net", 1, Some(43_200), 4500, now - 30))
            .await.expect("rec 4");
        store.record_memory_query(&mk_query_record("search_fts", "nonsense_xyz", 0, None, 600, now - 20))
            .await.expect("rec 5 (miss)");
        store.record_memory_query(&mk_query_record("get", "unknown_key", 0, None, 200, now - 10))
            .await.expect("rec 6 (miss)");

        let stats = store.memory_query_stats(3600).await.expect("stats");
        assert_eq!(stats.total_queries, 6);
        assert_eq!(stats.hits, 4);
        assert_eq!(stats.misses, 2);
        assert!((stats.hit_rate - (4.0 / 6.0)).abs() < 1e-9);
        // avg age over hit rows: (86400 + 7200 + 3600 + 43200) / 4 = 35100
        assert!((stats.avg_top_hit_age_secs - 35_100.0).abs() < 1.0);
        // p50/p95 sorted: 200, 600, 800, 1500, 2200, 4500 (6 values, last idx=5)
        // p50 idx = round(5 * 0.50) = round(2.5) = 3 → 1500
        // p95 idx = round(5 * 0.95) = round(4.75) = 5 → 4500
        assert_eq!(stats.p50_duration_us, 1500);
        assert_eq!(stats.p95_duration_us, 4500);

        // by_kind: search_fts=3, search_hybrid=1, search_semantic=1, get=1
        let m: std::collections::HashMap<_, _> = stats.by_kind.iter().cloned().collect();
        assert_eq!(m.get("search_fts").copied(), Some(3));
        assert_eq!(m.get("search_hybrid").copied(), Some(1));
        assert_eq!(m.get("search_semantic").copied(), Some(1));
        assert_eq!(m.get("get").copied(), Some(1));

        // top miss queries: nonsense_xyz once, unknown_key once
        assert_eq!(stats.top_miss_queries.len(), 2);
        let miss_keys: std::collections::HashSet<_> =
            stats.top_miss_queries.iter().map(|(k, _)| k.clone()).collect();
        assert!(miss_keys.contains("nonsense_xyz"));
        assert!(miss_keys.contains("unknown_key"));

        let _ = tokio::fs::remove_dir_all(&temp_dir).await;
    }

    #[tokio::test]
    async fn memory_query_stats_window_excludes_old_rows() {
        let temp_dir = std::env::temp_dir().join(format!(
            "ab-mem-query-window-{}-{}",
            std::process::id(),
            std::time::SystemTime::now()
                .duration_since(std::time::UNIX_EPOCH)
                .unwrap_or_default()
                .as_nanos()
        ));
        let db_path = temp_dir.join("state.db");
        let store = SqliteStore::open(&db_path).await.expect("open");

        let now = now_secs();
        store.record_memory_query(&mk_query_record("search_fts", "old", 1, Some(60), 500, now - 7200))
            .await.expect("old"); // 2h ago
        store.record_memory_query(&mk_query_record("search_fts", "new", 1, Some(60), 500, now - 60))
            .await.expect("new"); // 60s ago

        // 1-hour window: only "new" should count
        let stats = store.memory_query_stats(3600).await.expect("stats");
        assert_eq!(stats.total_queries, 1);

        // 3-hour window: both
        let stats = store.memory_query_stats(10_800).await.expect("stats");
        assert_eq!(stats.total_queries, 2);

        let _ = tokio::fs::remove_dir_all(&temp_dir).await;
    }

    #[tokio::test]
    async fn memory_query_log_ring_caps_at_max() {
        // Insert MEMORY_QUERY_LOG_RING_CAP + 5 rows; expect exactly cap rows present.
        let temp_dir = std::env::temp_dir().join(format!(
            "ab-mem-query-ring-{}-{}",
            std::process::id(),
            std::time::SystemTime::now()
                .duration_since(std::time::UNIX_EPOCH)
                .unwrap_or_default()
                .as_nanos()
        ));
        let db_path = temp_dir.join("state.db");
        let store = SqliteStore::open(&db_path).await.expect("open");

        let cap = MEMORY_QUERY_LOG_RING_CAP;
        let overshoot = cap + 5;
        let now = now_secs();
        for i in 0..overshoot {
            store.record_memory_query(
                &mk_query_record("search_fts", &format!("q{i}"), 1, Some(60), 500, now)
            ).await.expect("rec");
        }

        let count: i64 = store
            .conn
            .call(|c| -> RusqliteResult<i64> {
                c.query_row("SELECT COUNT(*) FROM memory_query_log", [], |r| r.get(0))
            })
            .await
            .expect("count");
        assert_eq!(count, cap);

        let _ = tokio::fs::remove_dir_all(&temp_dir).await;
    }
}
