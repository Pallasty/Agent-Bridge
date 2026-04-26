//! Terminal multiplexer abstraction + OSC parsing.
//!
//! - [`TerminalBackend`] trait — generic mux operations.
//! - [`WezTermBackend`] — first concrete impl (wraps `wezterm cli`).
//! - [`osc`] — pure-Rust streaming parser for OSC 9 / 99 / 777 notification
//!   sequences, used by both the bridge daemon and integration glue.

use ab_core::{PaneId, Result};
use async_trait::async_trait;
use futures::stream::BoxStream;
use serde::{Deserialize, Serialize};

pub mod osc;
pub mod wezterm;

pub use osc::{OscEvent, OscParser};
pub use wezterm::WezTermBackend;

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Pane {
    pub id: PaneId,
    pub title: String,
    pub cwd: Option<String>,
    pub command: Option<String>,
}

#[derive(Debug, Clone, Copy, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum SplitDir {
    Horizontal,
    Vertical,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum TermEvent {
    PaneOpened(PaneId),
    PaneClosed(PaneId),
    OscNotification {
        pane: PaneId,
        body: String,
    },
}

#[async_trait]
pub trait TerminalBackend: Send + Sync {
    fn id(&self) -> &str;

    async fn list_panes(&self) -> Result<Vec<Pane>>;

    async fn send_keys(&self, pane: &PaneId, keys: &str) -> Result<()>;

    async fn split(&self, pane: &PaneId, dir: SplitDir) -> Result<PaneId>;

    /// Stream lifecycle + OSC events. Backends without push semantics may
    /// return an empty/never-emitting stream.
    async fn subscribe(&self) -> Result<BoxStream<'static, TermEvent>>;
}
