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
    CompactPolicy, ImportConflictPolicy, ImportReport, MemoryEdge, MemoryExportFilter,
    MemoryListSort, MemoryRecord, MemorySearchHit, NotificationRecord, SessionFilter, StateStore,
    StoredSession, MEMORY_CONTENT_CAP, STDIO_CAP,
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
                c.execute("UPDATE schema_meta SET value='7' WHERE key='version'", [])?;
            }
            Ok(())
        })
        .await
        .map_err(|e| Error::Backend(format!("sqlite migrate: {e}")))?;

        info!(path = %path.display(), "SqliteStore ready");
        Ok(Self { conn })
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
fn token_overlap_ratio(a: &std::collections::HashSet<String>, b: &std::collections::HashSet<String>) -> f64 {
    if a.is_empty() || b.is_empty() {
        return 0.0;
    }
    let intersection = a.intersection(b).count();
    let union = a.union(b).count();
    if union == 0 { 0.0 } else { intersection as f64 / union as f64 }
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
                       (id, runtime_id, cwd, started_at, ended_at, exit_code, stdout, stderr)
                     VALUES (?1, ?2, ?3, ?4, ?5, ?6, ?7, ?8)",
                    params![
                        s.id.as_str(),
                        s.runtime_id,
                        s.cwd,
                        s.started_at,
                        s.ended_at,
                        s.exit_code,
                        s.stdout,
                        s.stderr
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
                    "SELECT id, runtime_id, cwd, started_at, ended_at, exit_code, stdout, stderr
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
                    "SELECT id, runtime_id, cwd, started_at, ended_at, exit_code, stdout, stderr
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
        let now = now_secs();

        // Pre-compute overlap tokens for contradiction detection (outside closure).
        let new_tokens = overlap_tokens(&content);
        let kind_clone = kind.clone();

        self.conn
            .call(move |c| -> RusqliteResult<()> {
                c.execute(
                    "INSERT INTO memories
                       (key, kind, content, tags, related_keys, scope,
                        created_at, updated_at, last_accessed_at, access_count,
                        importance, status)
                     VALUES (?1, ?2, ?3, ?4, ?5, ?6, ?7, ?7, ?7, 0, ?8, ?9)
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
                        END",
                    params![key, kind_clone, content, tags, related, scope, now, importance, status],
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
                            importance, status
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
                            status: row.get::<_, String>(11).unwrap_or_else(|_| "active".to_string()),
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
                            m.importance, m.status
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
                            status: row.get::<_, String>(12).unwrap_or_else(|_| "active".to_string()),
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
                                importance, status
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
                                status: row.get::<_, String>(11).unwrap_or_else(|_| "active".to_string()),
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
            let edges = self.memory_neighbors(&hit.record.key).await.unwrap_or_default();
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
            all_records.entry(hit.record.key.clone()).or_insert(hit.record);
        }
        for hit in graph_hits {
            all_records.entry(hit.record.key.clone()).or_insert(hit.record);
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
                            importance, status
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
                            status: row.get::<_, String>(11).unwrap_or_else(|_| "active".to_string()),
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
                let mut stmt = c.prepare(
                    "SELECT from_key, to_key, edge_type, weight FROM memory_edges",
                )?;
                let rows = stmt.query_map([], |row| {
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
    ) -> Result<u64> {
        let kind = filter.kind.clone();
        let tags = filter.tags_any.clone();
        let since = filter.since_ts;

        let rows: Vec<MemoryRecord> = self
            .conn
            .call(move |c| -> RusqliteResult<Vec<MemoryRecord>> {
                let mut stmt = c.prepare(
                    "SELECT key, kind, content, tags, related_keys, scope,
                            created_at, updated_at, last_accessed_at, access_count,
                            importance, status
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
                            status: row.get::<_, String>(11).unwrap_or_else(|_| "active".to_string()),
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
        Ok(filtered.len() as u64)
    }

    async fn memory_import(
        &self,
        in_path: &std::path::Path,
        policy: ImportConflictPolicy,
    ) -> Result<ImportReport> {
        let bytes = tokio::fs::read(in_path)
            .await
            .map_err(|e| Error::Backend(format!("read {in_path:?}: {e}")))?;
        let text = String::from_utf8_lossy(&bytes).into_owned();

        let mut report = ImportReport::default();
        // Parse first; we apply the conflict policy in a single transaction
        // for atomicity (a malformed line shouldn't half-import).
        let mut parsed: Vec<MemoryRecord> = Vec::new();
        for line in text.lines() {
            if line.trim().is_empty() {
                continue;
            }
            match serde_json::from_str::<MemoryRecord>(line) {
                Ok(r) => parsed.push(r),
                Err(_) => report.malformed += 1,
            }
        }

        let mut report = self
            .conn
            .call(move |c| -> RusqliteResult<ImportReport> {
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
                    let imp = if (r.importance - 0.5).abs() > 1e-9 {
                        r.importance
                    } else {
                        importance_for_kind(&r.kind)
                    };
                    let stat = if r.status.is_empty() { "active" } else { r.status.as_str() };
                    match existing {
                        None => {
                            // Brand-new row — insert with the imported timestamps verbatim.
                            tx.execute(
                                "INSERT INTO memories
                                   (key, kind, content, tags, related_keys, scope,
                                    created_at, updated_at, last_accessed_at, access_count,
                                    importance, status)
                                 VALUES (?1, ?2, ?3, ?4, ?5, ?6, ?7, ?8, ?9, ?10, ?11, ?12)",
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
                                        access_count = ?9, importance = ?10, status = ?11
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

        // Adjust report.malformed (we updated this field outside the closure).
        report.malformed += 0; // (already counted above; placeholder for clarity)
        Ok(report)
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::{MemoryListSort, StateStore};

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
}
