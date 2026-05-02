use std::collections::HashMap;
use std::sync::{
    atomic::{AtomicBool, Ordering},
    Arc,
};

use parking_lot::FairMutex;
use warp_agent_bridge::protocol::TerminalSession;
use warpui::{Entity, ModelContext, SingletonEntity};

use crate::terminal::model::terminal_model::TerminalModel;

/// Opaque PTY writer — created by `TerminalManager` over its private
/// `event_loop_tx`, type-erased so we don't expose mio_channel outside local_tty.
type PtyWriter = Arc<dyn Fn(&[u8]) -> anyhow::Result<()> + Send + Sync>;

/// Per-session entry stored in the registry.
pub struct SessionEntry {
    pub info: TerminalSession,
    /// Writes bytes directly into the shell's PTY without needing AppContext.
    pub pty_writer: PtyWriter,
    /// Direct handle to the terminal model for scrollback reads.
    pub model: Arc<FairMutex<TerminalModel>>,
    /// Set to `false` when the owning `TerminalManager` is dropped.
    pub alive: Arc<AtomicBool>,
}

/// Singleton GPUI model that bridges Warp terminal sessions to the IPC server.
///
/// `TerminalManager::create_model()` calls `register()` and its `Drop` impl
/// atomically marks the entry as dead via the `alive` flag.
pub struct AgentBridgeRegistry {
    sessions: HashMap<String, SessionEntry>,
}

impl AgentBridgeRegistry {
    pub fn new(_ctx: &mut ModelContext<Self>) -> Self {
        Self {
            sessions: HashMap::new(),
        }
    }

    /// Register a new terminal session.
    ///
    /// Returns a liveness flag that the caller should store; when it is dropped
    /// (or set to `false`), `list_sessions` will stop reporting this session.
    pub fn register(
        &mut self,
        info: TerminalSession,
        pty_writer: PtyWriter,
        model: Arc<FairMutex<TerminalModel>>,
    ) -> Arc<AtomicBool> {
        let alive = Arc::new(AtomicBool::new(true));
        log::debug!("agent-bridge: register session {}", info.session_id);
        self.sessions.insert(
            info.session_id.clone(),
            SessionEntry {
                info,
                pty_writer,
                model,
                alive: alive.clone(),
            },
        );
        // Opportunistically prune dead entries on each register.
        self.sessions.retain(|_, e| e.alive.load(Ordering::Relaxed));
        alive
    }

    pub fn list_sessions(&self) -> Vec<TerminalSession> {
        self.sessions
            .values()
            .filter(|e| e.alive.load(Ordering::Relaxed))
            .map(|e| e.info.clone())
            .collect()
    }

    /// Inject `text` bytes into the PTY for the named session.
    pub fn send_text(&self, session_id: &str, text: &str) -> anyhow::Result<()> {
        let entry = self
            .sessions
            .get(session_id)
            .filter(|e| e.alive.load(Ordering::Relaxed))
            .ok_or_else(|| anyhow::anyhow!("unknown or closed session: {session_id}"))?;
        (entry.pty_writer)(text.as_bytes())
    }

    /// Extract the last `last_n_lines` lines from the session's terminal model.
    ///
    /// Locks the model's `FairMutex` directly — safe from any thread.
    pub fn read_scrollback(
        &self,
        session_id: &str,
        last_n_lines: usize,
    ) -> anyhow::Result<Vec<String>> {
        let entry = self
            .sessions
            .get(session_id)
            .filter(|e| e.alive.load(Ordering::Relaxed))
            .ok_or_else(|| anyhow::anyhow!("unknown or closed session: {session_id}"))?;

        let model = entry.model.lock();

        let mut all_lines: Vec<String> = if model.is_alt_screen_active() {
            model
                .alt_screen()
                .output_to_string()
                .lines()
                .map(str::to_owned)
                .collect()
        } else {
            model
                .block_list()
                .blocks()
                .iter()
                .flat_map(|block| {
                    block
                        .output_to_string()
                        .lines()
                        .map(str::to_owned)
                        .collect::<Vec<_>>()
                })
                .collect()
        };

        let start = all_lines.len().saturating_sub(last_n_lines);
        all_lines.drain(..start);
        Ok(all_lines)
    }
}

impl Entity for AgentBridgeRegistry {
    type Event = ();
}

impl SingletonEntity for AgentBridgeRegistry {}
