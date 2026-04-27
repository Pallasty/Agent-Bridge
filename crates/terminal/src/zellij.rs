//! `zellij` CLI-backed [`TerminalBackend`].
//!
//! Zellij's CLI does not expose per-pane enumeration, so [`list_panes`]
//! returns one entry **per session** (the session name is treated as a
//! pane id). [`send_keys`] writes to the currently focused pane in that
//! session; [`split`] creates a new pane in the focused tab.
//!
//! For finer-grained pane control, a future ZellijPluginBackend could
//! talk to a small wasm plugin running inside the session — out of scope
//! for the CLI-only path.
//!
//! Streaming `subscribe()` is empty: zellij has no event firehose over CLI.

use ab_core::{Error, PaneId, Result};
use async_trait::async_trait;
use futures::stream::{self, BoxStream};
use tokio::process::Command;

use crate::{Pane, SplitDir, TermEvent, TerminalBackend};

#[derive(Clone)]
pub struct ZellijBackend {
    binary: String,
}

impl Default for ZellijBackend {
    fn default() -> Self {
        Self {
            binary: "zellij".into(),
        }
    }
}

impl ZellijBackend {
    pub fn new() -> Self {
        Self::default()
    }
    pub fn with_binary(binary: impl Into<String>) -> Self {
        Self { binary: binary.into() }
    }
}

async fn run(binary: &str, args: &[&str]) -> Result<String> {
    let out = Command::new(binary)
        .args(args)
        .output()
        .await
        .map_err(|e| Error::Backend(format!("spawn `{binary} {}`: {e}", args.join(" "))))?;
    if !out.status.success() {
        let stderr = String::from_utf8_lossy(&out.stderr);
        return Err(Error::Backend(format!(
            "{binary} {}: exit={:?} stderr={stderr}",
            args.join(" "),
            out.status.code()
        )));
    }
    Ok(String::from_utf8_lossy(&out.stdout).into_owned())
}

#[async_trait]
impl TerminalBackend for ZellijBackend {
    fn id(&self) -> &str {
        "zellij"
    }

    async fn list_panes(&self) -> Result<Vec<Pane>> {
        // `--short` outputs one session name per line, no ANSI colors.
        let stdout = match run(&self.binary, &["list-sessions", "--short"]).await {
            Ok(s) => s,
            Err(_) => {
                // Older zellij or no sessions: treat as empty rather than error.
                return Ok(Vec::new());
            }
        };
        let panes = stdout
            .lines()
            .map(str::trim)
            .filter(|l| !l.is_empty())
            .map(|name| Pane {
                id: PaneId::from_raw(name.to_string()),
                title: name.to_string(),
                cwd: None,
                command: None,
            })
            .collect();
        Ok(panes)
    }

    async fn send_keys(&self, pane: &PaneId, keys: &str) -> Result<()> {
        // pane id == session name. Targets the focused pane within the session.
        run(
            &self.binary,
            &["--session", pane.as_str(), "action", "write-chars", keys],
        )
        .await
        .map(|_| ())
    }

    async fn split(&self, pane: &PaneId, dir: SplitDir) -> Result<PaneId> {
        let dir_flag = match dir {
            SplitDir::Horizontal => "right",
            SplitDir::Vertical => "down",
        };
        run(
            &self.binary,
            &[
                "--session",
                pane.as_str(),
                "action",
                "new-pane",
                "-d",
                dir_flag,
            ],
        )
        .await?;
        // zellij CLI does not return a new pane id; reuse the session id.
        Ok(pane.clone())
    }

    async fn subscribe(&self) -> Result<BoxStream<'static, TermEvent>> {
        Ok(Box::pin(stream::empty()))
    }
}
