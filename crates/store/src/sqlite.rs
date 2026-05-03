//! SQLite-backed [`StateStore`] using `tokio-rusqlite` (bundled SQLite).

use ab_core::{Error, NotifyEvent, NotifySeverity, NotifySource, Result, SessionId};
use async_trait::async_trait;
use std::path::{Path, PathBuf};
use tokio_rusqlite::{params, Connection};

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
    AgentMessageRecord, CodebaseIndexStats, CodebaseSymbol, CompactPolicy, ImportConflictPolicy,
    ImportReport, McpToolCallStats, McpToolErrorRecord, MemoryEdge, MemoryEdgeExport,
    MemoryExportFilter, MemoryExportResult, MemoryListSort, MemoryRecord, MemorySearchHit,
    MemoryStats, NotificationRecord, PlanRecord, PlanStep, SessionFilter, StateStore,
    StoredSession, MCP_TOOL_ERROR_RING_CAP, MEMORY_CONTENT_CAP, STDIO_CAP,
};

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

/// Composite score for memory_search results.
/// Each hit starts with a base of 1.0; recency multiplies by exp(-age_days/30),
/// so a memory used today scores ~1.0×, one used 30d ago ~0.37×, 90d ago ~0.05×.
/// Then +log(1+access_count) bumps frequently-touched memories.
fn memory_score(last_accessed_at: i64, access_count: u64, now: i64) -> f64 {
    let age_days = ((now - last_accessed_at).max(0) as f64) / 86_400.0;
    let recency = (-age_days / 30.0).exp();
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

        // Pre-compute embedding (CPU-only, safe outside the async call closure).
        let embedding_bytes = crate::vector::encode_embedding(&crate::vector::embed_text(&content));

        // Pre-compute overlap tokens for contradiction detection (outside closure).
        let new_tokens = overlap_tokens(&content);
        let kind_clone = kind.clone();

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
                            WHEN memories.status = 'superseded' THEN 'active'
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
                            c.execute(
                                "UPDATE memories SET status = 'superseded'
                                 WHERE key = ?1 AND status = 'active'",
                                params![cand_key],
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
                            importance, status, trigger_pattern
                     FROM memories WHERE key = ?1",
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
                            m.importance, m.status, m.trigger_pattern
                     FROM memories_fts
                     JOIN memories m ON m.rowid = memories_fts.rowid
                     WHERE memories_fts MATCH ?1
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
                            match_strength + memory_score(r.last_accessed_at, r.access_count, now);
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
                                importance, status, trigger_pattern
                         FROM memories
                         WHERE key = ?1 COLLATE NOCASE
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
                            1_000_000.0 + memory_score(rec.last_accessed_at, rec.access_count, now);
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
                            importance, status, trigger_pattern
                     FROM memories
                     WHERE (?1 IS NULL OR kind = ?1)
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
        let n = self
            .conn
            .call(move |c| -> RusqliteResult<usize> {
                Ok(c.execute("DELETE FROM memories WHERE key = ?1", params![key])?)
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
                            importance, status, trigger_pattern
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

        let mut report = self
            .conn
            .call(move |c| -> RusqliteResult<ImportReport> {
                let mut report = ImportReport::default();
                let tx = c.unchecked_transaction()?;
                for r in &parsed {
                    let existing: Option<i64> = tx
                        .query_row(
                            "SELECT updated_at FROM memories WHERE key = ?1",
                            params![&r.key],
                            |row| row.get(0),
                        )
                        .ok();
                    let tags_s = serde_json::to_string(&r.tags).unwrap_or_else(|_| "[]".into());
                    let related_s =
                        serde_json::to_string(&r.related_keys).unwrap_or_else(|_| "[]".into());
                    let content = clamp(&r.content, MEMORY_CONTENT_CAP);
                    // Match `memory_save`: feature-hash embedding for semantic search.
                    let embedding_bytes = crate::vector::encode_embedding(
                        &crate::vector::embed_text(&content),
                    );
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
                    match existing {
                        None => {
                            // Brand-new row — insert with the imported timestamps verbatim.
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
                        Some(existing_uat) => {
                            let do_overwrite = match policy {
                                ImportConflictPolicy::Skip => false,
                                ImportConflictPolicy::Overwrite => true,
                                ImportConflictPolicy::NewerWins => r.updated_at > existing_uat,
                            };
                            if do_overwrite {
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
                            } else {
                                report.skipped += 1;
                            }
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
                            importance, status, trigger_pattern, embedding
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
                        };
                        let emb_bytes: Vec<u8> = row.get(13)?;
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
                    + 0.1 * memory_score(rec.last_accessed_at, rec.access_count, now);
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

    async fn memory_load_embeddings(&self) -> Result<Vec<(MemoryRecord, Vec<f32>)>> {
        let rows = self
            .conn
            .call(move |c| -> RusqliteResult<Vec<(MemoryRecord, Vec<u8>)>> {
                let mut stmt = c.prepare(
                    "SELECT key, kind, content, tags, related_keys, scope,
                            created_at, updated_at, last_accessed_at, access_count,
                            importance, status, trigger_pattern, embedding
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
                        };
                        let emb_bytes: Vec<u8> = row.get(13)?;
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
            let mut symbols: Vec<(CodebaseSymbol, Vec<u8>)> = Vec::new();
            let mut count = 0u32;
            for entry in WalkDir::new(&root_for_walk)
                .follow_links(false)
                .into_iter()
                .filter_map(|e| e.ok())
                .filter(|e| e.file_type().is_file())
            {
                let path = entry.path();
                // Skip common non-source directories.
                let skip = path.components().any(|c| {
                    matches!(
                        c.as_os_str().to_str(),
                        Some(".git")
                            | Some("target")
                            | Some("node_modules")
                            | Some(".venv")
                            | Some("__pycache__")
                            | Some(".mypy_cache")
                            | Some("dist")
                            | Some("build")
                    )
                });
                if skip {
                    continue;
                }
                let lang = match detect_language(path) {
                    Some(l) => l,
                    None => continue,
                };
                if !langs.is_empty() && !langs.iter().any(|l| l.as_str() == lang) {
                    continue;
                }
                let file_path_str = path.to_string_lossy().to_string();
                if let Ok(content) = std::fs::read_to_string(path) {
                    for sym in extract_symbols(&content, &file_path_str, lang) {
                        let emb_input = format!("{} {}", sym.name, sym.signature);
                        let emb = crate::vector::encode_embedding(
                            &crate::vector::embed_text(&emb_input),
                        );
                        symbols.push((sym, emb));
                    }
                    count += 1;
                }
            }
            (symbols, count)
        })
        .await
        .map_err(|e| Error::Backend(format!("codebase_index blocking: {e}")))?;

        let symbol_count = all_symbols.len() as u32;
        let root_for_return = root_path.to_string();
        let now = now_secs();

        self.conn
            .call(move |c| -> RusqliteResult<()> {
                // Replace previous index for this root path.
                c.execute(
                    "DELETE FROM codebase_symbols WHERE root_path = ?1",
                    params![root],
                )?;
                let mut stmt = c.prepare(
                    "INSERT INTO codebase_symbols
                     (file_path, line, col, kind, name, signature, language, root_path,
                      indexed_at, embedding)
                     VALUES (?1, ?2, ?3, ?4, ?5, ?6, ?7, ?8, ?9, ?10)",
                )?;
                for (sym, emb) in &all_symbols {
                    stmt.execute(params![
                        sym.file_path,
                        sym.line,
                        sym.col,
                        sym.kind,
                        sym.name,
                        sym.signature,
                        sym.language,
                        root,
                        now,
                        emb
                    ])?;
                }
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
}
