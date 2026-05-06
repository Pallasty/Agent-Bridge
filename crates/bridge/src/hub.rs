//! Shared backend bundle used by both the JSON-RPC router and the MCP tools.

use ab_agent::{AgentRuntime, GitWorktreeManager};
use ab_browser::BrowserBackend;
use ab_core::NotifyEvent;
use ab_notifier::Notifier;
use ab_store::{MemoryRecord, StateStore};
use ab_terminal::TerminalBackend;
use std::collections::HashMap;
use std::sync::Arc;
use tracing::warn;

use crate::security::SecurityPolicy;

#[derive(Clone)]
pub struct Hub {
    pub notifiers: Vec<Arc<dyn Notifier>>,
    pub store: Option<Arc<dyn StateStore>>,
    pub terminal: Option<Arc<dyn TerminalBackend>>,
    pub browser: Option<Arc<dyn BrowserBackend>>,
    /// Default agent runtime — used when [`agent_spawn`] omits an explicit
    /// `backend` argument. Picked at startup via `AGENT_BRIDGE_AGENT_RUNTIME`.
    pub agent: Option<Arc<dyn AgentRuntime>>,
    /// Registry of all available agent runtimes, keyed by their `id()`
    /// (`"claude-code"`, `"opencode"`, `"kilo"`, `"warp-oz"`, `"auggie"`).
    /// Lets `agent_spawn` fan out to any installed CLI without requiring
    /// per-call env-var rewrites.
    pub agents: HashMap<String, Arc<dyn AgentRuntime>>,
    pub worktree: Option<Arc<GitWorktreeManager>>,
    /// D2.3: per-turn semantic search cache — populated by session_bootstrap,
    /// consumed by memory_search(mode=semantic) to skip the DB round-trip.
    pub memory_embed_cache: Arc<tokio::sync::Mutex<Option<Vec<(MemoryRecord, Vec<f32>)>>>>,
    /// Phase E: runtime security policy (read from env vars at startup).
    pub security: SecurityPolicy,
}

impl Hub {
    pub fn builder() -> HubBuilder {
        HubBuilder::default()
    }

    /// Persist (best-effort) and fan-out one notification.
    pub async fn deliver(&self, evt: &NotifyEvent) -> (u32, bool) {
        let mut persisted = false;
        if let Some(store) = &self.store {
            match store.append_notification(evt).await {
                Ok(()) => persisted = true,
                Err(e) => warn!(error = %e, "store: append_notification failed"),
            }
        }
        let mut delivered = 0u32;
        for n in &self.notifiers {
            match n.send(evt).await {
                Ok(()) => delivered += 1,
                Err(e) => warn!(notifier = n.id(), error = %e, "notifier delivery failed"),
            }
        }
        (delivered, persisted)
    }
}

#[derive(Default)]
pub struct HubBuilder {
    notifiers: Vec<Arc<dyn Notifier>>,
    store: Option<Arc<dyn StateStore>>,
    terminal: Option<Arc<dyn TerminalBackend>>,
    browser: Option<Arc<dyn BrowserBackend>>,
    agent: Option<Arc<dyn AgentRuntime>>,
    agents: HashMap<String, Arc<dyn AgentRuntime>>,
    worktree: Option<Arc<GitWorktreeManager>>,
}

impl HubBuilder {
    pub fn notifier(mut self, n: Arc<dyn Notifier>) -> Self {
        self.notifiers.push(n);
        self
    }
    pub fn store(mut self, s: Arc<dyn StateStore>) -> Self {
        self.store = Some(s);
        self
    }
    pub fn terminal(mut self, t: Arc<dyn TerminalBackend>) -> Self {
        self.terminal = Some(t);
        self
    }
    pub fn browser(mut self, b: Arc<dyn BrowserBackend>) -> Self {
        self.browser = Some(b);
        self
    }
    /// Set the default agent runtime AND register it under its `id()` in
    /// the registry. Backwards-compatible with single-runtime callers.
    pub fn agent(mut self, a: Arc<dyn AgentRuntime>) -> Self {
        self.agents.insert(a.id().to_string(), a.clone());
        self.agent = Some(a);
        self
    }
    /// Register an additional agent runtime under its `id()`. Last write
    /// wins on collisions. Does not change the default runtime.
    pub fn register_agent(mut self, a: Arc<dyn AgentRuntime>) -> Self {
        self.agents.insert(a.id().to_string(), a);
        self
    }
    pub fn worktree(mut self, w: Arc<GitWorktreeManager>) -> Self {
        self.worktree = Some(w);
        self
    }
    pub fn build(self) -> Hub {
        Hub {
            notifiers: self.notifiers,
            store: self.store,
            terminal: self.terminal,
            browser: self.browser,
            agent: self.agent,
            agents: self.agents,
            worktree: self.worktree,
            memory_embed_cache: Arc::new(tokio::sync::Mutex::new(None)),
            security: SecurityPolicy::from_env(),
        }
    }
}
