//! SQLite-backed [`StateStore`] using `tokio-rusqlite` (bundled SQLite).

use ab_core::{Error, NotifyEvent, NotifySeverity, NotifySource, Result, SessionId};
use async_trait::async_trait;
use std::path::{Path, PathBuf};
use tokio_rusqlite::{params, Connection};

// Local alias matches the `E` parameter that `tokio_rusqlite::Connection::call`
// expects from the user closure.
type RusqliteResult<T> = std::result::Result<T, tokio_rusqlite::rusqlite::Error>;
use tracing::info;

use crate::{
    CompactPolicy, ImportConflictPolicy, ImportReport, MemoryExportFilter, MemoryListSort,
    MemoryRecord, MemorySearchHit, NotificationRecord, SessionFilter, StateStore, StoredSession,
    MEMORY_CONTENT_CAP, STDIO_CAP,
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
                let _ = c.execute("ALTER TABLE sessions ADD COLUMN stdout    TEXT",   []);
                let _ = c.execute("ALTER TABLE sessions ADD COLUMN stderr    TEXT",   []);
                c.execute(
                    "UPDATE schema_meta SET value='2' WHERE key='version'",
                    [],
                )?;
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
                c.execute(
                    "UPDATE schema_meta SET value='3' WHERE key='version'",
                    [],
                )?;
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
                c.execute(
                    "UPDATE schema_meta SET value='4' WHERE key='version'",
                    [],
                )?;
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
                c.execute(
                    "UPDATE schema_meta SET value='5' WHERE key='version'",
                    [],
                )?;
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
/// - **Plain text** (whitespace-separated terms) — we add `*` for prefix
///   matching on each term so partial words work as expected.
/// - **Quoted phrases or anything containing FTS5 operators** — passed through
///   unchanged so power users can write `"signal exit" OR sigterm`.
///
/// Heuristic: if the input contains FTS5 operator characters
/// (`"`, `*`, `:`, `(`, `)`, ` AND `, ` OR `, ` NOT `, ` NEAR `) we trust it;
/// otherwise we tokenise on whitespace and add `*` suffix to each term.
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
    // Plain-text path: tokenize, strip non-alphanumeric (FTS5 needs bare
    // tokens; "term"* is not the same as term*), prefix-match each.
    trimmed
        .split_whitespace()
        .filter_map(|t| {
            let cleaned: String = t
                .chars()
                .filter(|c| c.is_alphanumeric() || *c == '_' || *c == '-')
                .collect();
            if cleaned.is_empty() {
                None
            } else {
                Some(format!("{cleaned}*"))
            }
        })
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

fn parse_str_array(s: &str) -> Vec<String> {
    serde_json::from_str(s).unwrap_or_default()
}

/// Clamp `s` to at most `max` bytes, preserving UTF-8 boundaries.
fn clamp(s: &str, max: usize) -> String {
    if s.len() <= max { return s.to_string(); }
    let mut end = max;
    while end > 0 && !s.is_char_boundary(end) { end -= 1; }
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
                        s.id.as_str(), s.runtime_id, s.cwd, s.started_at, s.ended_at,
                        s.exit_code, s.stdout, s.stderr
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
        let f_runtime    = filter.runtime_id.clone();
        let f_cwd_prefix = filter.cwd_prefix.clone();
        let f_exited     = filter.exited_only;
        let f_exit_code  = filter.exit_code;

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
                        let context = serde_json::from_str(&context_str)
                            .unwrap_or(serde_json::Value::Null);
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
        let now = now_secs();

        self.conn
            .call(move |c| -> RusqliteResult<()> {
                // Preserve the original created_at if the row already exists.
                c.execute(
                    "INSERT INTO memories
                       (key, kind, content, tags, related_keys,
                        created_at, updated_at, last_accessed_at, access_count)
                     VALUES (?1, ?2, ?3, ?4, ?5, ?6, ?6, ?6, 0)
                     ON CONFLICT(key) DO UPDATE SET
                        kind          = excluded.kind,
                        content       = excluded.content,
                        tags          = excluded.tags,
                        related_keys  = excluded.related_keys,
                        updated_at    = excluded.updated_at",
                    params![key, kind, content, tags, related, now],
                )?;
                Ok(())
            })
            .await
            .map_err(|e| Error::Backend(format!("memory_save: {e}")))?;
        Ok(())
    }

    async fn memory_get(&self, key: &str) -> Result<Option<MemoryRecord>> {
        let key = key.to_string();
        let now = now_secs();

        let row = self.conn
            .call(move |c| -> RusqliteResult<Option<MemoryRecord>> {
                let mut stmt = c.prepare(
                    "SELECT key, kind, content, tags, related_keys,
                            created_at, updated_at, last_accessed_at, access_count
                     FROM memories WHERE key = ?1",
                )?;
                let r = stmt
                    .query_row(params![key], |row| {
                        let tags_s: String = row.get(3)?;
                        let related_s: String = row.get(4)?;
                        Ok(MemoryRecord {
                            key:              row.get(0)?,
                            kind:             row.get(1)?,
                            content:          row.get(2)?,
                            tags:             parse_str_array(&tags_s),
                            related_keys:     parse_str_array(&related_s),
                            created_at:       row.get(5)?,
                            updated_at:       row.get(6)?,
                            last_accessed_at: row.get(7)?,
                            access_count:     row.get::<_, i64>(8)? as u64,
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

        let hits = self.conn
            .call(move |c| -> RusqliteResult<Vec<MemorySearchHit>> {
                // FTS5 first: get candidate rowids ranked by bm25.
                // Then JOIN back to memories for the full record.
                // Final ranking blends bm25 (lower=better → invert) with
                // recency + frequency, applied in Rust.
                let mut stmt = c.prepare(
                    "SELECT m.key, m.kind, m.content, m.tags, m.related_keys,
                            m.created_at, m.updated_at, m.last_accessed_at, m.access_count,
                            bm25(memories_fts) AS bm25_score
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
                            key:              row.get(0)?,
                            kind:             row.get(1)?,
                            content:          row.get(2)?,
                            tags:             parse_str_array(&tags_s),
                            related_keys:     parse_str_array(&related_s),
                            created_at:       row.get(5)?,
                            updated_at:       row.get(6)?,
                            last_accessed_at: row.get(7)?,
                            access_count:     row.get::<_, i64>(8)? as u64,
                        };
                        let bm25: f64 = row.get(9)?;
                        Ok((rec, bm25))
                    })?
                    .collect::<std::result::Result<Vec<_>, _>>()?;

                let mut hits: Vec<MemorySearchHit> = rows
                    .into_iter()
                    .filter(|(r, _)| {
                        tags.is_empty() || tags.iter().any(|t| r.tags.contains(t))
                    })
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
                hits.sort_by(|a, b| b.score.partial_cmp(&a.score).unwrap_or(std::cmp::Ordering::Equal));
                hits.truncate(limit_i as usize);
                Ok(hits)
            })
            .await
            .map_err(|e| Error::Backend(format!("memory_search: {e}")))?;
        Ok(hits)
    }

    async fn list_memories(
        &self,
        kind: Option<&str>,
        sort: MemoryListSort,
        limit: u32,
    ) -> Result<Vec<MemoryRecord>> {
        let kind = kind.map(|s| s.to_string());
        let limit_i = limit as i64;
        let order = match sort {
            MemoryListSort::Recent   => "last_accessed_at DESC",
            MemoryListSort::Frequent => "access_count DESC, last_accessed_at DESC",
            MemoryListSort::Newest   => "created_at DESC",
        };

        let rows = self.conn
            .call(move |c| -> RusqliteResult<Vec<MemoryRecord>> {
                let sql = format!(
                    "SELECT key, kind, content, tags, related_keys,
                            created_at, updated_at, last_accessed_at, access_count
                     FROM memories
                     WHERE (?1 IS NULL OR kind = ?1)
                     ORDER BY {order}
                     LIMIT ?2"
                );
                let mut stmt = c.prepare(&sql)?;
                let rows = stmt
                    .query_map(params![kind, limit_i], |row| {
                        let tags_s: String = row.get(3)?;
                        let related_s: String = row.get(4)?;
                        Ok(MemoryRecord {
                            key:              row.get(0)?,
                            kind:             row.get(1)?,
                            content:          row.get(2)?,
                            tags:             parse_str_array(&tags_s),
                            related_keys:     parse_str_array(&related_s),
                            created_at:       row.get(5)?,
                            updated_at:       row.get(6)?,
                            last_accessed_at: row.get(7)?,
                            access_count:     row.get::<_, i64>(8)? as u64,
                        })
                    })?
                    .collect::<std::result::Result<Vec<_>, _>>()?;
                Ok(rows)
            })
            .await
            .map_err(|e| Error::Backend(format!("list_memories: {e}")))?;
        Ok(rows)
    }

    async fn memory_delete(&self, key: &str) -> Result<bool> {
        let key = key.to_string();
        let n = self.conn
            .call(move |c| -> RusqliteResult<usize> {
                Ok(c.execute("DELETE FROM memories WHERE key = ?1", params![key])?)
            })
            .await
            .map_err(|e| Error::Backend(format!("memory_delete: {e}")))?;
        Ok(n > 0)
    }

    async fn memory_compact(&self, policy: CompactPolicy) -> Result<Vec<String>> {
        let CompactPolicy { min_uses, older_than_secs, dry_run } = policy;
        let cutoff_lat = older_than_secs.map(|s| now_secs() - s);
        let min_uses_i = min_uses.map(|n| n as i64);

        let keys = self.conn
            .call(move |c| -> RusqliteResult<Vec<String>> {
                // Pick keys matching either condition.
                let mut stmt = c.prepare(
                    "SELECT key FROM memories
                     WHERE (?1 IS NOT NULL AND access_count < ?1)
                        OR (?2 IS NOT NULL AND last_accessed_at < ?2)",
                )?;
                let keys: Vec<String> = stmt
                    .query_map(params![min_uses_i, cutoff_lat], |r| r.get::<_, String>(0))?
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

        let rows: Vec<MemoryRecord> = self.conn
            .call(move |c| -> RusqliteResult<Vec<MemoryRecord>> {
                let mut stmt = c.prepare(
                    "SELECT key, kind, content, tags, related_keys,
                            created_at, updated_at, last_accessed_at, access_count
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
                            key:              row.get(0)?,
                            kind:             row.get(1)?,
                            content:          row.get(2)?,
                            tags:             parse_str_array(&tags_s),
                            related_keys:     parse_str_array(&related_s),
                            created_at:       row.get(5)?,
                            updated_at:       row.get(6)?,
                            last_accessed_at: row.get(7)?,
                            access_count:     row.get::<_, i64>(8)? as u64,
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
            if line.trim().is_empty() { continue; }
            match serde_json::from_str::<MemoryRecord>(line) {
                Ok(r) => parsed.push(r),
                Err(_) => report.malformed += 1,
            }
        }

        let mut report = self.conn
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
                    let related_s = serde_json::to_string(&r.related_keys).unwrap_or_else(|_| "[]".into());
                    let content = clamp(&r.content, MEMORY_CONTENT_CAP);
                    match existing {
                        None => {
                            // Brand-new row — insert with the imported timestamps verbatim.
                            tx.execute(
                                "INSERT INTO memories
                                   (key, kind, content, tags, related_keys,
                                    created_at, updated_at, last_accessed_at, access_count)
                                 VALUES (?1, ?2, ?3, ?4, ?5, ?6, ?7, ?8, ?9)",
                                params![
                                    r.key, r.kind, content, tags_s, related_s,
                                    r.created_at, r.updated_at, r.last_accessed_at,
                                    r.access_count as i64,
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
                                        updated_at = ?6, last_accessed_at = ?7, access_count = ?8
                                     WHERE key = ?1",
                                    params![
                                        r.key, r.kind, content, tags_s, related_s,
                                        r.updated_at, r.last_accessed_at, r.access_count as i64,
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
