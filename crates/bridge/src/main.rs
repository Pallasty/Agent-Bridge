use ab_agent::{AgentRuntime, ClaudeCodeRuntime, GitWorktreeManager};
use ab_bridge::{build_registry, default_socket_path, serve, Hub, Router};
use ab_browser::{BrowserBackend, ChromiumCdpBackend};
use ab_mcp::server::serve_stdio;
use ab_notifier::DbusNotifier;
use ab_store::{default_db_path, SqliteStore, StateStore};
use ab_terminal::{TerminalBackend, WezTermBackend};
use anyhow::Result;
use clap::{Parser, Subcommand};
use std::sync::Arc;
use tracing_subscriber::{prelude::*, EnvFilter};

#[derive(Parser, Debug)]
#[command(version, about = "agent-bridge — Linux-native AI agent control plane")]
struct Cli {
    #[command(subcommand)]
    cmd: Option<Cmd>,
}

#[derive(Subcommand, Debug)]
enum Cmd {
    /// Run the long-lived JSON-RPC daemon on a Unix socket (default).
    Daemon,
    /// Run as an MCP stdio server (for `claude mcp add agent-bridge ...`).
    Mcp,
}

#[tokio::main]
async fn main() -> Result<()> {
    let cli = Cli::parse();
    let cmd = cli.cmd.unwrap_or(Cmd::Daemon);

    let log_layer = match cmd {
        Cmd::Mcp => tracing_subscriber::fmt::layer().with_writer(std::io::stderr).boxed(),
        Cmd::Daemon => tracing_subscriber::fmt::layer().boxed(),
    };
    tracing_subscriber::registry()
        .with(EnvFilter::try_from_default_env().unwrap_or_else(|_| "info".into()))
        .with(log_layer)
        .init();

    let hub = build_hub().await?;

    match cmd {
        Cmd::Daemon => {
            let socket = default_socket_path();
            tracing::info!(socket = %socket.display(), "starting agent-bridge daemon");
            serve(&socket, Router::new(hub)).await
        }
        Cmd::Mcp => {
            let registry = build_registry(hub);
            tracing::info!(tools = registry.list().len(), "starting MCP stdio server");
            serve_stdio(registry, "agent-bridge", env!("CARGO_PKG_VERSION")).await;
            Ok(())
        }
    }
}

/// Construct the shared backend bundle used by both modes.
///
/// `AGENT_BRIDGE_REPO` selects the git repository the worktree manager binds
/// to (defaults to `$PWD`). `AGENT_BRIDGE_CLAUDE_BIN` overrides the claude
/// binary path. `AGENT_BRIDGE_HEADLESS=1` for headless Chromium.
async fn build_hub() -> Result<Hub> {
    let dbus = DbusNotifier::connect().await?;
    let store: Arc<dyn StateStore> = Arc::new(SqliteStore::open(&default_db_path()).await?);
    let terminal: Arc<dyn TerminalBackend> = Arc::new(WezTermBackend::new());
    let browser: Arc<dyn BrowserBackend> = Arc::new(ChromiumCdpBackend::new());

    let claude_bin =
        std::env::var("AGENT_BRIDGE_CLAUDE_BIN").unwrap_or_else(|_| "claude".into());
    let agent: Arc<dyn AgentRuntime> = Arc::new(ClaudeCodeRuntime::with_binary(claude_bin));

    let repo = std::env::var("AGENT_BRIDGE_REPO")
        .ok()
        .map(std::path::PathBuf::from)
        .unwrap_or_else(|| std::env::current_dir().unwrap_or_else(|_| ".".into()));
    let worktree = Arc::new(GitWorktreeManager::new(repo));

    Ok(Hub::builder()
        .notifier(Arc::new(dbus))
        .store(store)
        .terminal(terminal)
        .browser(browser)
        .agent(agent)
        .worktree(worktree)
        .build())
}
