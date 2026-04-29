//! `wezterm cli` subprocess-backed [`TerminalBackend`].
//!
//! WezTerm exposes a stable mux protocol via `wezterm cli`. We wrap the
//! relevant subcommands and shape their stdout into our trait types.
//!
//! Streaming `subscribe()` is intentionally a no-op: WezTerm has no event
//! firehose. OSC notifications are expected to arrive via the daemon's
//! `osc.parse` RPC, fed by a small Lua hook (see `examples/wezterm/`).

use ab_core::{Error, PaneId, Result};
use async_trait::async_trait;
use futures::stream::{self, BoxStream};
use serde::Deserialize;
use tokio::process::Command;

use crate::{Pane, SplitDir, TermEvent, TerminalBackend};

#[derive(Clone)]
pub struct WezTermBackend {
    binary: String,
}

impl Default for WezTermBackend {
    fn default() -> Self {
        Self {
            binary: "wezterm".into(),
        }
    }
}

impl WezTermBackend {
    pub fn new() -> Self {
        Self::default()
    }
    pub fn with_binary(binary: impl Into<String>) -> Self {
        Self {
            binary: binary.into(),
        }
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

#[derive(Debug, Deserialize)]
struct WezPaneRow {
    pane_id: u64,
    title: String,
    cwd: Option<String>,
    #[serde(default)]
    command: Option<String>,
}

#[async_trait]
impl TerminalBackend for WezTermBackend {
    fn id(&self) -> &str {
        "wezterm"
    }

    async fn list_panes(&self) -> Result<Vec<Pane>> {
        let stdout = run(&self.binary, &["cli", "list", "--format", "json"]).await?;
        let rows: Vec<WezPaneRow> = serde_json::from_str(&stdout).map_err(|e| {
            Error::Backend(format!("parse wezterm cli list json: {e}; raw={stdout}"))
        })?;
        Ok(rows
            .into_iter()
            .map(|r| Pane {
                id: PaneId::from_raw(r.pane_id.to_string()),
                title: r.title,
                cwd: r.cwd,
                command: r.command,
            })
            .collect())
    }

    async fn send_keys(&self, pane: &PaneId, keys: &str) -> Result<()> {
        let pane = pane.as_str().to_string();
        let mut child = Command::new(&self.binary)
            .args(["cli", "send-text", "--pane-id", &pane, "--no-paste"])
            .stdin(std::process::Stdio::piped())
            .stdout(std::process::Stdio::null())
            .stderr(std::process::Stdio::piped())
            .spawn()
            .map_err(|e| Error::Backend(format!("spawn wezterm cli send-text: {e}")))?;
        if let Some(mut stdin) = child.stdin.take() {
            use tokio::io::AsyncWriteExt;
            stdin
                .write_all(keys.as_bytes())
                .await
                .map_err(|e| Error::Backend(format!("write send-text stdin: {e}")))?;
            stdin.shutdown().await.ok();
        }
        let status = child
            .wait()
            .await
            .map_err(|e| Error::Backend(format!("wait wezterm cli send-text: {e}")))?;
        if !status.success() {
            return Err(Error::Backend(format!(
                "wezterm cli send-text failed: {status:?}"
            )));
        }
        Ok(())
    }

    async fn split(&self, pane: &PaneId, dir: SplitDir) -> Result<PaneId> {
        let dir_flag = match dir {
            SplitDir::Horizontal => "--horizontal",
            SplitDir::Vertical => "--bottom",
        };
        let stdout = run(
            &self.binary,
            &["cli", "split-pane", "--pane-id", pane.as_str(), dir_flag],
        )
        .await?;
        let new_id = stdout.trim();
        if new_id.is_empty() {
            return Err(Error::Backend(
                "wezterm cli split-pane returned empty id".into(),
            ));
        }
        Ok(PaneId::from_raw(new_id.to_string()))
    }

    async fn subscribe(&self) -> Result<BoxStream<'static, TermEvent>> {
        // No native event stream from `wezterm cli`; the bridge fronts events
        // via osc.parse RPC instead.
        Ok(Box::pin(stream::empty()))
    }
}
