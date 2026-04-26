//! Persistence abstraction.
//!
//! Default impl: [`SqliteStore`] — single-file rusqlite (bundled), zero system deps.
//! Future: in-memory (tests), Postgres (multi-machine), Redis (cache).

use ab_core::{NotifyEvent, Result, SessionId};
use async_trait::async_trait;
use serde::{Deserialize, Serialize};

pub mod sqlite;
pub use sqlite::{default_db_path, SqliteStore};

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
}

/// One persisted notification, with its server-assigned timestamp.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct NotificationRecord {
    /// Unix epoch seconds.
    pub ts: i64,
    pub event: NotifyEvent,
}

/// Hard cap on stdout/stderr we persist per agent session, to keep the DB
/// file from growing unbounded if a sub-agent goes haywire.
pub const STDIO_CAP: usize = 64 * 1024;

#[async_trait]
pub trait StateStore: Send + Sync {
    async fn save_session(&self, session: &StoredSession) -> Result<()>;

    async fn load_session(&self, id: &SessionId) -> Result<Option<StoredSession>>;

    /// List sessions newest-first, capped to `limit` rows.
    async fn list_sessions(&self, limit: u32) -> Result<Vec<StoredSession>>;

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
}
