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

/// Snapshot of one page returned from [`BrowserBackend::list_pages`].
/// Pages discovered for the first time during a list_pages call are
/// auto-registered with a fresh `page_id` so subsequent tool calls can
/// address them.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct PageInfo {
    pub page_id: String,
    pub target_id: String,
    pub url: String,
    pub title: String,
    /// `true` if `list_pages` minted a fresh page_id for this target on this
    /// call (i.e. it was a tab the daemon hadn't seen yet — typically an
    /// OAuth pop-up or a click-opened window).
    pub newly_tracked: bool,
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

    /// List every page the underlying browser has open. Auto-discovers tabs
    /// opened by clicks or window.open / target=_blank links and registers
    /// fresh `page_id`s for them so the agent can address them via the
    /// other browser_* tools. The `newly_tracked` field marks tabs that
    /// were not in the daemon's tracker before this call.
    async fn list_pages(&self) -> Result<Vec<PageInfo>>;

    /// Dispatch a key-down + key-up sequence to whatever element is
    /// currently focused on `page`. `key` is a single character ("a", "0")
    /// or a named key from US keyboard layout ("Enter", "Tab", "Escape",
    /// "ArrowDown", "Backspace", etc.). `modifiers` is a CDP modifier
    /// bitmask: 1=Alt, 2=Ctrl, 4=Meta/Cmd, 8=Shift.
    async fn press_key(&self, page: &PageId, key: &str, modifiers: u32) -> Result<()>;

    /// Set the selected option of a `<select>` element. `value` matches
    /// against `option.value` first, then `option.text` (the visible
    /// label) — handles both `<option value="us">United States</option>`
    /// and country pickers indexed by visible name. Dispatches `input`
    /// + `change` events. Returns `{selectedIndex, selectedValue,
    /// selectedText}` for the agent to verify.
    async fn select_option(
        &self,
        page: &PageId,
        selector: &str,
        value: &str,
    ) -> Result<serde_json::Value>;

    /// Search the DOM for elements whose visible text contains `text`.
    /// Optional `tag_filter` (e.g. "button", "a") narrows the search.
    /// Returns up to 5 deepest-match candidates, each with a generated
    /// CSS `selector` you can hand to browser_click / browser_fill_form.
    /// Empty result = no match found.
    async fn find_by_text(
        &self,
        page: &PageId,
        text: &str,
        tag_filter: Option<&str>,
    ) -> Result<serde_json::Value>;

    async fn close(&self, page: &PageId) -> Result<()>;
}
