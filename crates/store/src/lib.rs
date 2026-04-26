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
    pub ended_at: Option<i64>,
}

/// One persisted notification, with its server-assigned timestamp.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct NotificationRecord {
    /// Unix epoch seconds.
    pub ts: i64,
    pub event: NotifyEvent,
}

#[async_trait]
pub trait StateStore: Send + Sync {
    async fn save_session(&self, session: &StoredSession) -> Result<()>;

    async fn load_session(&self, id: &SessionId) -> Result<Option<StoredSession>>;

    async fn list_sessions(&self) -> Result<Vec<StoredSession>>;

    async fn append_notification(&self, evt: &NotifyEvent) -> Result<()>;

    async fn recent_notifications(&self, limit: u32) -> Result<Vec<NotificationRecord>>;
}
