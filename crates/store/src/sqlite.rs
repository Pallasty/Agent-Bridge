//! SQLite-backed [`StateStore`] using `tokio-rusqlite` (bundled SQLite).

use ab_core::{Error, NotifyEvent, NotifySeverity, NotifySource, Result, SessionId};
use async_trait::async_trait;
use std::path::{Path, PathBuf};
use tokio_rusqlite::{params, Connection};

// Local alias matches the `E` parameter that `tokio_rusqlite::Connection::call`
// expects from the user closure.
type RusqliteResult<T> = std::result::Result<T, tokio_rusqlite::rusqlite::Error>;
use tracing::info;

use crate::{NotificationRecord, StateStore, StoredSession};

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

/// Default database path: `$XDG_DATA_HOME/agent-bridge/state.db`,
/// or `~/.local/share/agent-bridge/state.db` as a fallback.
pub fn default_db_path() -> PathBuf {
    if let Ok(xdg) = std::env::var("XDG_DATA_HOME") {
        return PathBuf::from(xdg).join("agent-bridge").join("state.db");
    }
    if let Ok(home) = std::env::var("HOME") {
        return PathBuf::from(home)
            .join(".local/share/agent-bridge")
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
            Ok(())
        })
        .await
        .map_err(|e| Error::Backend(format!("sqlite migrate: {e}")))?;

        info!(path = %path.display(), "SqliteStore ready");
        Ok(Self { conn })
    }
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
                    "INSERT OR REPLACE INTO sessions(id, runtime_id, cwd, started_at, ended_at)
                     VALUES (?1, ?2, ?3, ?4, ?5)",
                    params![s.id.as_str(), s.runtime_id, s.cwd, s.started_at, s.ended_at],
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
                    "SELECT id, runtime_id, cwd, started_at, ended_at
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
                        })
                    })
                    .ok();
                Ok(r)
            })
            .await
            .map_err(|e| Error::Backend(format!("load_session: {e}")))?;
        Ok(row)
    }

    async fn list_sessions(&self) -> Result<Vec<StoredSession>> {
        let rows = self
            .conn
            .call(|c| -> RusqliteResult<Vec<StoredSession>> {
                let mut stmt = c.prepare(
                    "SELECT id, runtime_id, cwd, started_at, ended_at
                     FROM sessions ORDER BY started_at DESC",
                )?;
                let rows = stmt
                    .query_map([], |row| {
                        Ok(StoredSession {
                            id: SessionId::from_raw(row.get::<_, String>(0)?),
                            runtime_id: row.get(1)?,
                            cwd: row.get(2)?,
                            started_at: row.get(3)?,
                            ended_at: row.get(4)?,
                        })
                    })?
                    .collect::<std::result::Result<Vec<_>, _>>()?;
                Ok(rows)
            })
            .await
            .map_err(|e| Error::Backend(format!("list_sessions: {e}")))?;
        Ok(rows)
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
}
