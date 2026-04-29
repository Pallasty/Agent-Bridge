use ab_agent::{AgentRuntime, ClaudeCodeRuntime, GitWorktreeManager};
use ab_bridge::{build_registry, default_socket_path, serve, Hub, Router};
use ab_browser::{BrowserBackend, ChromiumCdpBackend};
use ab_mcp::server::serve_stdio;
use ab_store::{default_db_path, SqliteStore, StateStore};
use ab_terminal::{auto_backend, TerminalBackend, WarpBackend};
use anyhow::Result;
use clap::{Parser, Subcommand, ValueEnum};
use std::sync::Arc;
use tracing_subscriber::{prelude::*, EnvFilter};

mod setup;

#[derive(Parser, Debug)]
#[command(version, about = "agent-bridge — Unix-native AI agent control plane")]
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
    /// Install agent-bridge for the chosen frontend.
    ///
    /// `--frontend claude-code` (default): copies the binary to
    /// `~/.local/bin/agent-bridge`, writes the three Claude Code hook
    /// scripts, and merges hook entries into `~/.claude/settings.json`.
    ///
    /// `--frontend warp`: copies the binary only and prints guidance for
    /// registering the MCP server in Warp's settings UI. Skips all
    /// Claude-specific hook installation since Warp does not have
    /// equivalent hook-event slots.
    ///
    /// `--frontend auto`: detect from `WarpBackend::detect()` /
    /// CLAUDE_* env vars. Defaults to claude-code if neither is found.
    Setup {
        #[arg(long, value_enum, default_value_t = SetupFrontend::Auto)]
        frontend: SetupFrontend,
    },
}

#[derive(Copy, Clone, Debug, ValueEnum)]
pub enum SetupFrontend {
    /// Install hooks for Claude Code (legacy behaviour).
    ClaudeCode,
    /// Install for Warp (binary only; no hook scripts).
    Warp,
    /// Auto-detect from the running shell's environment.
    Auto,
}

impl SetupFrontend {
    /// Resolve `Auto` to a concrete frontend by inspecting the env.
    fn resolve(self) -> setup::Frontend {
        match self {
            Self::ClaudeCode => setup::Frontend::ClaudeCode,
            Self::Warp => setup::Frontend::Warp,
            Self::Auto => {
                if WarpBackend::detect() {
                    setup::Frontend::Warp
                } else {
                    setup::Frontend::ClaudeCode
                }
            }
        }
    }
}

#[tokio::main]
async fn main() -> Result<()> {
    let cli = Cli::parse();
    let cmd = cli.cmd.unwrap_or(Cmd::Daemon);

    // Setup runs synchronously, no async runtime needed beyond tokio's shell.
    if let Cmd::Setup { frontend } = &cmd {
        return setup::run(frontend.resolve());
    }

    let log_layer = match cmd {
        Cmd::Mcp => tracing_subscriber::fmt::layer()
            .with_writer(std::io::stderr)
            .boxed(),
        _ => tracing_subscriber::fmt::layer().boxed(),
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
            let store = hub.store.clone();
            let registry = build_registry(hub);
            tracing::info!(tools = registry.list().len(), "starting MCP stdio server");
            serve_stdio(registry, store, "agent-bridge", env!("CARGO_PKG_VERSION")).await;
            Ok(())
        }
        Cmd::Setup { .. } => unreachable!(),
    }
}

/// Construct the shared backend bundle used by both modes.
///
/// `AGENT_BRIDGE_REPO` selects the git repository the worktree manager binds
/// to (defaults to `$PWD`). `AGENT_BRIDGE_CLAUDE_BIN` overrides the claude
/// binary path. `AGENT_BRIDGE_HEADLESS=1` for headless Chromium.
async fn build_hub() -> Result<Hub> {
    #[cfg(target_os = "linux")]
    let notifier: Arc<dyn ab_notifier::Notifier> = {
        use ab_notifier::DbusNotifier;
        Arc::new(DbusNotifier::connect().await?)
    };
    #[cfg(target_os = "macos")]
    let notifier: Arc<dyn ab_notifier::Notifier> = {
        use ab_notifier::MacOsNotifier;
        Arc::new(MacOsNotifier)
    };
    #[cfg(not(any(target_os = "linux", target_os = "macos")))]
    compile_error!("agent-bridge requires Linux or macOS");

    let store: Arc<dyn StateStore> = Arc::new(SqliteStore::open(&default_db_path()).await?);
    let terminal: Arc<dyn TerminalBackend> = auto_backend();
    tracing::info!(terminal_backend = %terminal.id(), "terminal backend selected");
    let browser: Arc<dyn BrowserBackend> = Arc::new(ChromiumCdpBackend::new());

    let claude_bin = std::env::var("AGENT_BRIDGE_CLAUDE_BIN").unwrap_or_else(|_| "claude".into());
    let agent: Arc<dyn AgentRuntime> =
        Arc::new(ClaudeCodeRuntime::with_binary(claude_bin).with_store(store.clone()));

    let repo = std::env::var("AGENT_BRIDGE_REPO")
        .ok()
        .map(std::path::PathBuf::from)
        .unwrap_or_else(|| std::env::current_dir().unwrap_or_else(|_| ".".into()));
    let worktree = Arc::new(GitWorktreeManager::new(repo));

    Ok(Hub::builder()
        .notifier(notifier)
        .store(store)
        .terminal(terminal)
        .browser(browser)
        .agent(agent)
        .worktree(worktree)
        .build())
}
