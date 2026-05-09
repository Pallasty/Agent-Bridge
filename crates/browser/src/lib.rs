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

/// Result of a [`BrowserBackend::pause_for_human`] call. `outcome` is one
/// of `"resumed"` (caller of `resume` released the wait), `"timeout"` (the
/// timeout elapsed before resume), or `"superseded"` (a second pause on
/// the same page replaced the prior waiter; the older call returns this
/// instead of hanging forever).
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct PauseOutcome {
    pub outcome: String,
    pub elapsed_ms: u64,
}

/// One captured XHR/Fetch response from
/// [`BrowserBackend::capture_response_drain`]. `body` is decoded UTF-8 if
/// the upstream returned `base64Encoded=false`, otherwise it's the
/// original base64 string and `base64_encoded` is set so the caller can
/// decode it for binary payloads (images, fonts).
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct CapturedResponse {
    pub request_id: String,
    pub url: String,
    pub status: i64,
    pub resource_type: String,
    pub mime_type: String,
    pub body: String,
    pub base64_encoded: bool,
    pub headers: serde_json::Value,
    pub ts_ms: u64,
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

    /// Enumerate the frame tree of `page`. Returns a flattened list of
    /// `{frame_id, url, name, parent_id}` covering the main document and
    /// every iframe, regardless of cross-origin status. Use this to
    /// discover the frame_id for `eval_in_frame` (Stripe Elements,
    /// reCAPTCHA, embedded Auth0 widgets all live in their own frame
    /// with a distinguishing URL).
    async fn list_frames(&self, page: &PageId) -> Result<serde_json::Value>;

    /// Evaluate `js` inside a specific frame's isolated world. Pass either
    /// `frame_id` (from list_frames) or `frame_url_substring` (matched
    /// against each frame's URL — first hit wins). Crosses cross-origin
    /// iframe boundaries that the parent's own JS cannot. Surfaces JS
    /// exceptions with `text @ url:line:col` like the main-frame eval.
    async fn eval_in_frame(
        &self,
        page: &PageId,
        frame_id: Option<&str>,
        frame_url_substring: Option<&str>,
        js: &str,
    ) -> Result<serde_json::Value>;

    /// Begin recording XHR / Fetch / document responses on `page` whose
    /// URL contains `url_substring`. Idempotent per page: a second start
    /// replaces the first (existing buffer dropped). The recorder fetches
    /// the response body via `Network.getResponseBody` *after*
    /// `Network.loadingFinished` fires, so bodies are guaranteed-loaded.
    /// `max_buffer` clamped to [1, 200] (default 50); ring-buffer drops
    /// oldest entries when full. Cleared automatically on
    /// [`Self::close`] for the same page.
    async fn capture_response_start(
        &self,
        page: &PageId,
        url_substring: &str,
        max_buffer: usize,
    ) -> Result<()>;

    /// Drain (and clear) all matching responses captured since the last
    /// drain or since [`Self::capture_response_start`] was called. If the
    /// buffer is empty, blocks up to `until_ms` (clamped to [0, 60_000])
    /// for at least one match to arrive. Returns at most `max_results`
    /// (clamped to [1, 200], default 20) entries, oldest-first. Caller
    /// receives an error if no capture is currently active for `page`.
    async fn capture_response_drain(
        &self,
        page: &PageId,
        until_ms: u64,
        max_results: usize,
    ) -> Result<Vec<CapturedResponse>>;

    /// Scroll `page`. If `selector` is `Some`, scroll the matching
    /// element into view (centered). Otherwise dispatch a
    /// `window.scrollBy(dx, dy)` with the supplied pixel deltas
    /// (default 0). Returns the post-scroll
    /// `{scrollX, scrollY, scrollHeight}` for inspection.
    async fn scroll(
        &self,
        page: &PageId,
        selector: Option<&str>,
        dx: f64,
        dy: f64,
    ) -> Result<serde_json::Value>;

    /// Move the mouse cursor over the first element matching `selector`
    /// (auto-scrolls it into view first). Triggers `mouseenter` /
    /// `mouseover` handlers, including CSS `:hover` styles. Useful for
    /// drop-down menus that only render on hover and tooltip
    /// activation. Errors with `not found` if the selector matches
    /// nothing.
    async fn hover(&self, page: &PageId, selector: &str) -> Result<()>;

    /// Reload `page` (CDP `Page.reload`) and wait for the load event.
    /// Equivalent to clicking the browser's reload button.
    async fn reload(&self, page: &PageId) -> Result<()>;

    /// Step `page` one entry back in its session history (equivalent
    /// to `window.history.back()`). Best-effort: returns immediately
    /// after dispatching the navigation; use `wait_for` afterwards if
    /// you need to block until the new URL settles.
    async fn go_back(&self, page: &PageId) -> Result<()>;

    /// Step `page` one entry forward in its session history.
    async fn go_forward(&self, page: &PageId) -> Result<()>;

    /// Block the current request until [`Self::resume`] is called for
    /// `page`, or until `timeout_ms` elapses. Returns a [`PauseOutcome`]
    /// describing which condition fired. Used to hand control to a human
    /// for CAPTCHA solves, OTP entry, manual confirmation, etc. The
    /// MCP wrapper layer is expected to fire a `notify` *before* calling
    /// this so the human gets pinged. `timeout_ms` is clamped to
    /// [1_000, 1_800_000] (1 s … 30 min). If a previous pause is still
    /// pending on the same `page`, the new pause supersedes it: the
    /// older call returns with `outcome="superseded"`.
    async fn pause_for_human(&self, page: &PageId, timeout_ms: u64) -> Result<PauseOutcome>;

    /// Release a [`Self::pause_for_human`] waiter on `page`. Returns
    /// `true` if a waiter existed and was released, `false` if no
    /// pause was pending (caller likely already timed out).
    async fn resume(&self, page: &PageId) -> Result<bool>;

    async fn close(&self, page: &PageId) -> Result<()>;
}
