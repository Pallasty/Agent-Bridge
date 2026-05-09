//! Headless / embedded browser automation abstraction.
//!
//! Default impl ([`ChromiumCdpBackend`]) drives a Chrome/Chromium process via
//! the Chrome DevTools Protocol using `chromiumoxide`. The browser is launched
//! lazily on first use, in headed mode (so the human can see what the agent is
//! doing) — set `AGENT_BRIDGE_HEADLESS=1` to switch to headless.

use ab_core::{PageId, Result};
use async_trait::async_trait;
use bytes::Bytes;
use serde::{Deserialize, Serialize};

pub mod chromium_cdp;
pub use chromium_cdp::ChromiumCdpBackend;

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct A11yNode {
    pub role: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub name: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub value: Option<String>,
    #[serde(default, skip_serializing_if = "Vec::is_empty")]
    pub children: Vec<A11yNode>,
}

/// Result of a [`BrowserBackend::wait_for`] call. `matched` is one of
/// `"selector"`, `"url"`, or `"timeout"` depending on which condition
/// resolved (or whether the deadline expired).
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct WaitOutcome {
    pub matched: String,
    pub elapsed_ms: u64,
    pub current_url: String,
}

#[async_trait]
pub trait BrowserBackend: Send + Sync {
    fn id(&self) -> &str;

    async fn navigate(&self, url: &str) -> Result<PageId>;

    async fn eval(&self, page: &PageId, js: &str) -> Result<serde_json::Value>;

    async fn snapshot_a11y(&self, page: &PageId) -> Result<A11yNode>;

    async fn click(&self, page: &PageId, selector: &str) -> Result<()>;

    async fn screenshot(&self, page: &PageId) -> Result<Bytes>;

    /// Visible text of the page (`document.documentElement.innerText`), best-effort.
    async fn extract_text(&self, page: &PageId) -> Result<String>;

    /// Set the value of the first element matching `selector` (input/textarea or
    /// `textContent` fallback) and dispatch `input` + `change` events.
    async fn fill_form(&self, page: &PageId, selector: &str, value: &str) -> Result<()>;

    /// Block until either:
    ///   * `selector` matches a DOM element (polled @ 100 ms), or
    ///   * `location.href` contains `url_substring` (polled @ 100 ms), or
    ///   * `timeout_ms` elapses (always returns Ok with `matched="timeout"`).
    /// Either or both predicates may be passed; if neither, this becomes a
    /// pure sleep. `timeout_ms` is clamped to [50, 60_000].
    async fn wait_for(
        &self,
        page: &PageId,
        selector: Option<&str>,
        url_substring: Option<&str>,
        timeout_ms: u64,
    ) -> Result<WaitOutcome>;

    async fn close(&self, page: &PageId) -> Result<()>;
}
