//! `kitten @` (kitty remote control) backed [`TerminalBackend`].
//!
//! Requires `allow_remote_control yes` in `kitty.conf`. Pane IDs are kitty
//! window IDs (stable u64 integers per running kitty instance).
//!
//! Socket discovery order:
//! 1. `AGENT_BRIDGE_KITTY_SOCKET` env var — explicit override (e.g. when
//!    running the daemon outside any kitty session).
//! 2. `KITTY_LISTEN_ON` env var — kitty exports this into shells it spawns
//!    when `listen_on` is set in `kitty.conf`.
//! 3. Neither set: kitten auto-probes via /dev/tty (works only when invoked
//!    from a real terminal).
//!
//! Streaming `subscribe()` is intentionally a no-op: kitty has no event
//! firehose. OSC notifications are expected to arrive via the daemon's
//! `osc.parse` RPC, fed by a shell-side hook if desired.

use ab_core::{Error, PaneId, Result};
use async_trait::async_trait;
use futures::stream::{self, BoxStream};
use serde::Deserialize;
use tokio::process::Command;

use crate::{Pane, SplitDir, TermEvent, TerminalBackend, TerminalCapabilities};

#[derive(Clone)]
pub struct KittyBackend {
    binary: String,
    socket: Option<String>,
}

impl Default for KittyBackend {
    fn default() -> Self {
        let socket = std::env::var("AGENT_BRIDGE_KITTY_SOCKET")
            .ok()
            .or_else(|| std::env::var("KITTY_LISTEN_ON").ok())
            .filter(|s| !s.is_empty());
        Self {
            binary: "kitten".into(),
            socket,
        }
    }
}

impl KittyBackend {
    pub fn new() -> Self {
        Self::default()
    }
    pub fn with_binary(binary: impl Into<String>) -> Self {
        Self {
            binary: binary.into(),
            socket: Self::default().socket,
        }
    }
    pub fn with_socket(mut self, socket: impl Into<String>) -> Self {
        self.socket = Some(socket.into());
        self
    }

    /// Build args starting with `@` plus optional `--to <socket>`.
    fn at_prefix(&self) -> Vec<String> {
        let mut args = vec!["@".to_string()];
        if let Some(s) = &self.socket {
            args.push("--to".into());
            args.push(s.clone());
        }
        args
    }
}

async fn run(binary: &str, args: &[String]) -> Result<String> {
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
struct KittyOsWindow {
    #[serde(default)]
    tabs: Vec<KittyTab>,
}

#[derive(Debug, Deserialize)]
struct KittyTab {
    #[serde(default)]
    windows: Vec<KittyWindow>,
}

#[derive(Debug, Deserialize)]
struct KittyWindow {
    id: u64,
    #[serde(default)]
    title: String,
    #[serde(default)]
    cwd: Option<String>,
    #[serde(default)]
    foreground_processes: Vec<KittyForegroundProc>,
}

#[derive(Debug, Deserialize)]
struct KittyForegroundProc {
    #[serde(default)]
    cmdline: Vec<String>,
}

#[async_trait]
impl TerminalBackend for KittyBackend {
    fn id(&self) -> &str {
        "kitty"
    }

    fn capabilities(&self) -> TerminalCapabilities {
        TerminalCapabilities {
            backend_id: self.id().to_string(),
            can_read_output: true,
            can_send_keys: true,
            can_split: true,
        }
    }

    async fn list_panes(&self) -> Result<Vec<Pane>> {
        let mut args = self.at_prefix();
        args.push("ls".into());
        let stdout = run(&self.binary, &args).await?;
        let os_windows: Vec<KittyOsWindow> = serde_json::from_str(&stdout)
            .map_err(|e| Error::Backend(format!("parse kitten @ ls json: {e}; raw={stdout}")))?;
        let mut panes = Vec::new();
        for ow in os_windows {
            for tab in ow.tabs {
                for w in tab.windows {
                    let command = w
                        .foreground_processes
                        .first()
                        .and_then(|p| p.cmdline.first().cloned());
                    panes.push(Pane {
                        id: PaneId::from_raw(w.id.to_string()),
                        title: w.title,
                        cwd: w.cwd,
                        command,
                    });
                }
            }
        }
        Ok(panes)
    }

    async fn send_keys(&self, pane: &PaneId, keys: &str) -> Result<()> {
        let mut args = self.at_prefix();
        args.push("send-text".into());
        args.push("--match".into());
        args.push(format!("id:{}", pane.as_str()));
        args.push("--stdin".into());
        let mut child = Command::new(&self.binary)
            .args(&args)
            .stdin(std::process::Stdio::piped())
            .stdout(std::process::Stdio::null())
            .stderr(std::process::Stdio::piped())
            .spawn()
            .map_err(|e| Error::Backend(format!("spawn kitten @ send-text: {e}")))?;
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
            .map_err(|e| Error::Backend(format!("wait kitten @ send-text: {e}")))?;
        if !status.success() {
            return Err(Error::Backend(format!(
                "kitten @ send-text failed: {status:?}"
            )));
        }
        Ok(())
    }

    async fn read_output(&self, pane: &PaneId, lines: usize) -> Result<Vec<String>> {
        let mut args = self.at_prefix();
        args.push("get-text".into());
        args.push("--match".into());
        args.push(format!("id:{}", pane.as_str()));
        let stdout = run(&self.binary, &args).await?;
        let all: Vec<String> = stdout.lines().map(ToString::to_string).collect();
        let total = all.len();
        let keep = lines.max(1).min(total);
        Ok(all.into_iter().skip(total.saturating_sub(keep)).collect())
    }

    async fn split(&self, pane: &PaneId, dir: SplitDir) -> Result<PaneId> {
        // kitty terminology: vsplit = side-by-side, hsplit = stacked top/bottom.
        // Match wezterm's SplitDir semantics: Horizontal = side-by-side, Vertical = stacked.
        let location = match dir {
            SplitDir::Horizontal => "vsplit",
            SplitDir::Vertical => "hsplit",
        };
        let mut args = self.at_prefix();
        args.push("launch".into());
        args.push("--type=window".into());
        args.push(format!("--location={location}"));
        args.push("--match".into());
        args.push(format!("id:{}", pane.as_str()));
        let stdout = run(&self.binary, &args).await?;
        let new_id = stdout.trim();
        if new_id.is_empty() {
            return Err(Error::Backend("kitten @ launch returned empty id".into()));
        }
        Ok(PaneId::from_raw(new_id.to_string()))
    }

    async fn subscribe(&self) -> Result<BoxStream<'static, TermEvent>> {
        Ok(Box::pin(stream::empty()))
    }
}
