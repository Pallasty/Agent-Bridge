//! Chromium / Chrome backend via Chrome DevTools Protocol (`chromiumoxide`).
//!
//! - Lazy launch: the browser process starts on the first call that needs it.
//! - Headed by default (so you can watch the agent work); set
//!   `AGENT_BRIDGE_HEADLESS=1` to switch to headless.
//! - Pages are tracked in a [`DashMap`] keyed by [`PageId`]; the backend hands
//!   the same id back to the caller for subsequent eval/click/screenshot.
//!
//! ## Self-healing (v0.6.1)
//!
//! v0.6.0 used [`OnceCell`] to lazily launch chrome exactly once per backend
//! instance. That assumed chrome would never die, which is wrong: external
//! `kill -9`, OOM, or a session ending would leave the OnceCell holding a
//! dead websocket handle, and the next `browser_*` call would block forever
//! because the CDP protocol has no inherent RPC timeout.
//!
//! v0.6.1 swaps `OnceCell<Browser>` for `RwLock<Option<Browser>>` and adds
//! a 500 ms timeout-wrapped health probe (`browser.version()`) before reusing
//! a cached handle. If the probe fails, we relaunch chrome and clear the
//! stale `PageId → Page` map (the old page refs pointed at the dead
//! browser's targets and would all error anyway).

use ab_core::{Error, PageId, Result};
use async_trait::async_trait;
use bytes::Bytes;
use chromiumoxide::cdp::browser_protocol::accessibility::GetFullAxTreeParams;
use chromiumoxide::cdp::browser_protocol::dom::SetFileInputFilesParams;
use chromiumoxide::cdp::browser_protocol::emulation::{
    SetDeviceMetricsOverrideParams, SetUserAgentOverrideParams,
};
use chromiumoxide::cdp::browser_protocol::input::{DispatchKeyEventParams, DispatchKeyEventType};
use chromiumoxide::cdp::browser_protocol::network::{
    EnableParams as NetworkEnableParams, EventLoadingFinished, EventResponseReceived,
    GetResponseBodyParams,
};
use chromiumoxide::cdp::browser_protocol::page::{
    CaptureScreenshotFormat, CreateIsolatedWorldParams, FrameId, FrameTree, GetFrameTreeParams,
    Viewport,
};
use chromiumoxide::cdp::browser_protocol::target::{
    AttachToTargetParams, GetTargetsParams, TargetInfo,
};
use chromiumoxide::cdp::js_protocol::runtime::EvaluateParams;
use chromiumoxide::keys::{KeyDefinition, USKEYBOARD_LAYOUT};
use chromiumoxide::page::ScreenshotParams;
use chromiumoxide::{Browser, BrowserConfig, Page};
use dashmap::DashMap;
use futures::StreamExt;
use std::collections::{HashMap, VecDeque};
use std::path::PathBuf;
use std::sync::Arc;
use std::time::{Duration, Instant};
use tokio::sync::{oneshot, Mutex, Notify, RwLock};
use tracing::{debug, info, warn};

use crate::{A11yNode, BrowserBackend, CapturedResponse, PageInfo, PauseOutcome, WaitOutcome};

const HEALTH_TIMEOUT: Duration = Duration::from_millis(500);

#[derive(Clone)]
pub struct ChromiumCdpBackend {
    /// Cached Chrome handle. `None` = not yet launched (or was relaunched
    /// after death and is currently being rebuilt under the write lock).
    /// Wrapped in [`Arc`] because `chromiumoxide::Browser` is not [`Clone`];
    /// the Arc lets multiple async tasks share one handle cheaply.
    inner: Arc<RwLock<Option<Arc<Browser>>>>,
    /// PageId → live Page handle. Cleared on relaunch since old pages are
    /// associated with the dead chrome's targets.
    pages: Arc<DashMap<String, Arc<Page>>>,
    /// PageId → oneshot sender for an in-flight `pause_for_human` waiter.
    /// `Mutex<HashMap>` instead of `DashMap` so we can take-and-replace
    /// atomically when a second pause supersedes the first.
    pause_waiters: Arc<Mutex<HashMap<String, oneshot::Sender<PauseSignal>>>>,
    /// PageId → (in-flight capture state, pump abort handle). One capture
    /// per page max; a second `capture_response_start` aborts the prior
    /// pump and replaces the entry.
    captures: Arc<Mutex<HashMap<String, (Arc<CaptureState>, tokio::task::AbortHandle)>>>,
}

/// Per-page capture state for `capture_response_start` /
/// `capture_response_drain`. The pump task runs until aborted via
/// the [`tokio::task::AbortHandle`] held in
/// [`ChromiumCdpBackend::captures`] alongside this state; the page-side
/// `Network.disable` is sent best-effort on stop.
struct CaptureState {
    url_substring: String,
    buffer: Mutex<VecDeque<CapturedResponse>>,
    max_buffer: usize,
    /// Notified by the pump every time a new entry lands so blocking
    /// drain calls can wake without polling.
    arrival: Notify,
}

impl CaptureState {
    /// Push a new entry, dropping the oldest if the ring is full.
    /// Notifies any drainers blocked in `arrival.notified()`.
    async fn push(&self, entry: CapturedResponse) {
        let mut buf = self.buffer.lock().await;
        if buf.len() >= self.max_buffer {
            buf.pop_front();
        }
        buf.push_back(entry);
        drop(buf);
        self.arrival.notify_waiters();
    }
}

/// Signal sent through the oneshot channel that a pause waiter is awaiting on.
/// `Resumed` = `resume()` released the wait. `Superseded` = a newer pause
/// replaced the wait (the new caller takes ownership of waiting for resume).
#[derive(Debug, Clone, Copy)]
enum PauseSignal {
    Resumed,
    Superseded,
}

impl Default for ChromiumCdpBackend {
    fn default() -> Self {
        Self::new()
    }
}

impl ChromiumCdpBackend {
    pub fn new() -> Self {
        Self {
            inner: Arc::new(RwLock::new(None)),
            pages: Arc::new(DashMap::new()),
            pause_waiters: Arc::new(Mutex::new(HashMap::new())),
            captures: Arc::new(Mutex::new(HashMap::new())),
        }
    }

    /// Returns a live [`Arc<Browser>`], launching (or relaunching) chrome if
    /// needed. Cheap fast-path: a read lock + 500 ms health probe; only takes
    /// the write lock when the cached handle is missing or dead.
    async fn ensure_browser(&self) -> Result<Arc<Browser>> {
        // Fast path: read lock, health-check the cached handle.
        {
            let guard = self.inner.read().await;
            if let Some(b) = guard.as_ref() {
                if Self::is_alive(b).await {
                    return Ok(b.clone());
                }
            }
        }

        // Slow path: take the write lock and (re)launch.
        let mut guard = self.inner.write().await;
        // Double-check after acquiring the write lock — another task may have
        // beaten us here.
        if let Some(b) = guard.as_ref() {
            if Self::is_alive(b).await {
                return Ok(b.clone());
            }
            warn!("cached chrome handle failed health check; relaunching");
            // Stale pages reference the dead browser's targets — drop them so
            // callers get a clean NotFound rather than a confusing CDP error.
            self.pages.clear();
        }

        // R2.5 #5b — try to adopt an existing chrome holding the persistent
        // profile before launching a new one. This handles the common case
        // where a previous agent-bridge daemon's chrome outlived the daemon
        // itself (chrome doesn't auto-quit when its parent disconnects), and
        // the new daemon would otherwise crash with "Failed to create
        // SingletonLock" on launch.
        let user_data = resolve_user_data_dir();
        if let Some(adopted) = Self::try_adopt_existing(&user_data).await {
            *guard = Some(adopted.clone());
            return Ok(adopted);
        }

        let browser = Arc::new(Self::launch_chrome_with_profile(&user_data).await?);
        *guard = Some(browser.clone());
        Ok(browser)
    }

    /// If a previous chrome is still running on the configured profile and
    /// has a live DevTools endpoint, attach to it via `Browser::connect`
    /// instead of launching a new chrome. Returns `None` for any failure
    /// path — the caller falls through to launch.
    async fn try_adopt_existing(profile: &PathBuf) -> Option<Arc<Browser>> {
        let port_file = profile.join("DevToolsActivePort");
        let raw = std::fs::read_to_string(&port_file).ok()?;
        let port: u16 = raw.lines().next()?.trim().parse().ok()?;
        let http_url = format!("http://127.0.0.1:{port}");
        match Browser::connect(http_url.clone()).await {
            Ok((browser, mut handler)) => {
                tokio::spawn(async move {
                    while let Some(item) = handler.next().await {
                        if let Err(e) = item {
                            warn!(error = %e, "chromiumoxide handler error (adopted)");
                        }
                    }
                });
                if !Self::is_alive(&browser).await {
                    debug!(http_url, "adopted browser failed health probe");
                    return None;
                }
                info!(http_url, "adopted existing chrome on persistent profile");
                Some(Arc::new(browser))
            }
            Err(e) => {
                debug!(http_url, error = %e, "could not adopt existing chrome");
                None
            }
        }
    }

    /// 500 ms timeout-wrapped probe via the CDP `Browser.getVersion` command.
    /// Returns `false` for both timeout and protocol error — both mean the
    /// handle is unusable.
    async fn is_alive(browser: &Browser) -> bool {
        match tokio::time::timeout(HEALTH_TIMEOUT, browser.version()).await {
            Ok(Ok(_)) => true,
            Ok(Err(e)) => {
                debug!(error = %e, "browser.version() returned error → treating as dead");
                false
            }
            Err(_) => {
                debug!(
                    timeout_ms = HEALTH_TIMEOUT.as_millis(),
                    "browser.version() timed out"
                );
                false
            }
        }
    }

    /// Spawn chrome + the chromiumoxide event handler. Honours
    /// `AGENT_BRIDGE_HEADLESS` and `AGENT_BRIDGE_CHROME`. The caller passes
    /// the resolved user-data-dir.
    ///
    /// Before launching, stale `Singleton{Lock,Cookie,Socket}` artifacts in
    /// the profile dir are removed — by the time we reach this code the
    /// adopt path has failed (no live DevTools endpoint), so any leftover
    /// lock is from a dead chrome and would only block the new launch.
    async fn launch_chrome_with_profile(user_data: &PathBuf) -> Result<Browser> {
        let headless = std::env::var("AGENT_BRIDGE_HEADLESS")
            .map(|v| v == "1" || v.eq_ignore_ascii_case("true"))
            .unwrap_or(false);

        let mut cfg = BrowserConfig::builder();
        if headless {
            // chromiumoxide's default is "headless" mode.
        } else {
            cfg = cfg.with_head();
        }
        if let Ok(path) = std::env::var("AGENT_BRIDGE_CHROME") {
            cfg = cfg.chrome_executable(path);
        }
        if let Err(e) = std::fs::create_dir_all(user_data) {
            warn!(path = %user_data.display(), error = %e, "create_dir_all on chrome profile failed; chrome may fall back to default");
        }
        for stale in ["SingletonLock", "SingletonCookie", "SingletonSocket"] {
            let p = user_data.join(stale);
            if p.exists() {
                if let Err(e) = std::fs::remove_file(&p) {
                    warn!(path = %p.display(), error = %e, "could not remove stale Singleton artifact");
                } else {
                    debug!(path = %p.display(), "removed stale Singleton artifact");
                }
            }
        }
        info!(profile = %user_data.display(), "chrome user-data-dir");
        cfg = cfg.user_data_dir(user_data.clone());

        let cfg = cfg
            .build()
            .map_err(|e| Error::Backend(format!("BrowserConfig build: {e}")))?;

        let (browser, mut handler) = Browser::launch(cfg)
            .await
            .map_err(|e| Error::Backend(format!("chrome launch: {e}")))?;

        tokio::spawn(async move {
            while let Some(item) = handler.next().await {
                if let Err(e) = item {
                    warn!(error = %e, "chromiumoxide handler error");
                }
            }
        });

        info!(headless, "Chromium CDP backend ready");
        Ok(browser)
    }

    fn page_handle(&self, page: &PageId) -> Result<Arc<Page>> {
        self.pages
            .get(page.as_str())
            .map(|p| p.clone())
            .ok_or_else(|| Error::NotFound(format!("page id {page} not tracked")))
    }
}

#[async_trait]
impl BrowserBackend for ChromiumCdpBackend {
    fn id(&self) -> &str {
        "chromium-cdp"
    }

    async fn navigate(&self, url: &str) -> Result<PageId> {
        let browser = self.ensure_browser().await?;
        let page = browser
            .new_page(url)
            .await
            .map_err(|e| Error::Backend(format!("new_page {url}: {e}")))?;
        page.wait_for_navigation()
            .await
            .map_err(|e| Error::Backend(format!("wait_for_navigation: {e}")))?;
        let pid = PageId::new();
        debug!(page = %pid, url, "page tracked");
        self.pages.insert(pid.as_str().to_string(), Arc::new(page));
        Ok(pid)
    }

    async fn eval(&self, page: &PageId, js: &str) -> Result<serde_json::Value> {
        let p = self.page_handle(page)?;
        eval_with_exception_details(&p, js).await
    }

    async fn snapshot_a11y(&self, page: &PageId) -> Result<A11yNode> {
        let p = self.page_handle(page)?;
        let resp = p
            .execute(GetFullAxTreeParams::default())
            .await
            .map_err(|e| Error::Backend(format!("getFullAXTree: {e}")))?;
        // `resp.result.nodes` is a flat list of Accessibility.AXNode.
        let nodes = &resp.result.nodes;
        let tree = build_a11y_tree(nodes);
        Ok(tree)
    }

    async fn click(&self, page: &PageId, selector: &str) -> Result<()> {
        let p = self.page_handle(page)?;
        let el = p
            .find_element(selector)
            .await
            .map_err(|e| Error::Backend(format!("find_element {selector}: {e}")))?;
        el.click()
            .await
            .map_err(|e| Error::Backend(format!("click {selector}: {e}")))?;
        Ok(())
    }

    async fn screenshot(&self, page: &PageId) -> Result<Bytes> {
        let p = self.page_handle(page)?;
        let params = ScreenshotParams::builder()
            .format(CaptureScreenshotFormat::Png)
            .full_page(true)
            .build();
        let png = p
            .screenshot(params)
            .await
            .map_err(|e| Error::Backend(format!("screenshot: {e}")))?;
        Ok(Bytes::from(png))
    }

    async fn upload_file(
        &self,
        page: &PageId,
        selector: &str,
        files: Vec<String>,
    ) -> Result<()> {
        if files.is_empty() {
            return Err(Error::InvalidArgument("files is empty".into()));
        }
        let p = self.page_handle(page)?;
        let el = p
            .find_element(selector.to_string())
            .await
            .map_err(|e| Error::Backend(format!("find_element {selector}: {e}")))?;
        let params = SetFileInputFilesParams::builder()
            .files(files)
            .backend_node_id(el.backend_node_id.clone())
            .build()
            .map_err(|e| Error::Backend(format!("setFileInputFiles builder: {e}")))?;
        p.execute(params)
            .await
            .map_err(|e| Error::Backend(format!("setFileInputFiles: {e}")))?;
        Ok(())
    }

    async fn set_user_agent(
        &self,
        page: &PageId,
        user_agent: &str,
        accept_language: Option<&str>,
        platform: Option<&str>,
    ) -> Result<()> {
        let p = self.page_handle(page)?;
        let params = SetUserAgentOverrideParams {
            user_agent: user_agent.to_string(),
            accept_language: accept_language.map(|s| s.to_string()),
            platform: platform.map(|s| s.to_string()),
            user_agent_metadata: None,
        };
        p.execute(params)
            .await
            .map_err(|e| Error::Backend(format!("setUserAgentOverride: {e}")))?;
        Ok(())
    }

    async fn set_viewport(
        &self,
        page: &PageId,
        width: i64,
        height: i64,
        device_scale_factor: f64,
        mobile: bool,
    ) -> Result<()> {
        let p = self.page_handle(page)?;
        let params = SetDeviceMetricsOverrideParams::builder()
            .width(width)
            .height(height)
            .device_scale_factor(device_scale_factor)
            .mobile(mobile)
            .build()
            .map_err(|e| Error::Backend(format!("setDeviceMetricsOverride builder: {e}")))?;
        p.execute(params)
            .await
            .map_err(|e| Error::Backend(format!("setDeviceMetricsOverride: {e}")))?;
        Ok(())
    }

    async fn screenshot_element(&self, page: &PageId, selector: &str) -> Result<Bytes> {
        let p = self.page_handle(page)?;
        let el = p
            .find_element(selector.to_string())
            .await
            .map_err(|e| Error::Backend(format!("find_element {selector}: {e}")))?;
        // Auto-scroll so the element is in-frame for capture; otherwise
        // CDP captures whatever scroll offset happens to be active.
        el.scroll_into_view()
            .await
            .map_err(|e| Error::Backend(format!("scroll_into_view: {e}")))?;
        let bb = el
            .bounding_box()
            .await
            .map_err(|e| Error::Backend(format!("bounding_box: {e}")))?;
        if bb.width <= 0.0 || bb.height <= 0.0 {
            return Err(Error::Backend(format!(
                "element has zero area: {}x{}",
                bb.width, bb.height
            )));
        }
        let clip = Viewport {
            x: bb.x,
            y: bb.y,
            width: bb.width,
            height: bb.height,
            scale: 1.0,
        };
        let params = ScreenshotParams::builder()
            .format(CaptureScreenshotFormat::Png)
            .clip(clip)
            .build();
        let png = p
            .screenshot(params)
            .await
            .map_err(|e| Error::Backend(format!("screenshot_element: {e}")))?;
        Ok(Bytes::from(png))
    }

    async fn extract_text(&self, page: &PageId) -> Result<String> {
        let p = self.page_handle(page)?;
        const JS: &str = r#"(() => {
            try {
                const r = document.documentElement;
                return r && r.innerText != null ? String(r.innerText) : '';
            } catch (_) {
                return '';
            }
        })()"#;
        let v = eval_with_exception_details(&p, JS).await?;
        Ok(json_eval_result_as_plain_text(&v))
    }

    async fn fill_form(&self, page: &PageId, selector: &str, value: &str) -> Result<()> {
        let p = self.page_handle(page)?;
        let sel_lit = serde_json::to_string(selector).map_err(|e| Error::Serde(e))?;
        let val_lit = serde_json::to_string(value).map_err(|e| Error::Serde(e))?;
        let js = format!(
            "(() => {{ const sel = {sel_lit}; const val = {val_lit}; \
             const el = document.querySelector(sel); \
             if (!el) {{ throw new Error('fill_form: no element for selector'); }} \
             el.focus(); \
             if ('value' in el && el.value !== undefined) {{ el.value = val; }} \
             else {{ el.textContent = val; }} \
             el.dispatchEvent(new Event('input', {{ bubbles: true }})); \
             el.dispatchEvent(new Event('change', {{ bubbles: true }})); \
             return true; }})()"
        );
        eval_with_exception_details(&p, &js).await.map(|_| ())
    }

    async fn wait_for(
        &self,
        page: &PageId,
        selector: Option<&str>,
        url_substring: Option<&str>,
        timeout_ms: u64,
    ) -> Result<WaitOutcome> {
        let p = self.page_handle(page)?;
        let timeout = Duration::from_millis(timeout_ms.clamp(50, 60_000));
        let poll = Duration::from_millis(100);
        let start = std::time::Instant::now();

        // Pre-build polling expressions once.
        let selector_expr = selector.map(|s| {
            let lit = serde_json::to_string(s).unwrap_or_else(|_| "\"\"".into());
            format!("(() => document.querySelector({lit}) != null)()")
        });
        let url_expr = url_substring.map(|s| {
            let lit = serde_json::to_string(s).unwrap_or_else(|_| "\"\"".into());
            format!("(() => location.href.includes({lit}))()")
        });
        const URL_EXPR: &str = "(() => location.href)()";

        loop {
            if let Some(ref js) = selector_expr {
                let v = eval_with_exception_details(&p, js).await?;
                if v.as_bool().unwrap_or(false) {
                    let cur = eval_with_exception_details(&p, URL_EXPR)
                        .await
                        .ok()
                        .and_then(|x| x.as_str().map(String::from))
                        .unwrap_or_default();
                    return Ok(WaitOutcome {
                        matched: "selector".into(),
                        elapsed_ms: start.elapsed().as_millis() as u64,
                        current_url: cur,
                    });
                }
            }
            if let Some(ref js) = url_expr {
                let v = eval_with_exception_details(&p, js).await?;
                if v.as_bool().unwrap_or(false) {
                    let cur = eval_with_exception_details(&p, URL_EXPR)
                        .await
                        .ok()
                        .and_then(|x| x.as_str().map(String::from))
                        .unwrap_or_default();
                    return Ok(WaitOutcome {
                        matched: "url".into(),
                        elapsed_ms: start.elapsed().as_millis() as u64,
                        current_url: cur,
                    });
                }
            }
            if start.elapsed() >= timeout {
                let cur = eval_with_exception_details(&p, URL_EXPR)
                    .await
                    .ok()
                    .and_then(|x| x.as_str().map(String::from))
                    .unwrap_or_default();
                return Ok(WaitOutcome {
                    matched: "timeout".into(),
                    elapsed_ms: start.elapsed().as_millis() as u64,
                    current_url: cur,
                });
            }
            tokio::time::sleep(poll).await;
        }
    }

    async fn list_pages(&self) -> Result<Vec<PageInfo>> {
        let browser = self.ensure_browser().await?;
        let live = browser
            .pages()
            .await
            .map_err(|e| Error::Backend(format!("browser.pages: {e}")))?;

        // Build target_id → existing PageId.as_str() reverse lookup from the
        // currently tracked map (typically <10 entries, so O(n) is fine).
        let mut existing: std::collections::HashMap<String, String> =
            std::collections::HashMap::new();
        for entry in self.pages.iter() {
            existing.insert(entry.value().target_id().as_ref().to_string(), entry.key().clone());
        }

        let mut out = Vec::with_capacity(live.len());
        for page in live {
            let tid = page.target_id().as_ref().to_string();
            let (page_id, newly) = if let Some(pid) = existing.get(&tid) {
                (pid.clone(), false)
            } else {
                let pid = PageId::new();
                let key = pid.as_str().to_string();
                self.pages.insert(key.clone(), Arc::new(page.clone()));
                (key, true)
            };
            let url = page.url().await.ok().flatten().unwrap_or_default();
            let title = page.get_title().await.ok().flatten().unwrap_or_default();
            out.push(PageInfo {
                page_id,
                target_id: tid,
                url,
                title,
                newly_tracked: newly,
            });
        }
        Ok(out)
    }

    async fn press_key(&self, page: &PageId, key: &str, modifiers: u32) -> Result<()> {
        let p = self.page_handle(page)?;
        let kd = lookup_key(key).ok_or_else(|| {
            Error::Backend(format!(
                "press_key: unknown key '{key}' (try 'Enter', 'Tab', 'Escape', 'ArrowDown', \
                 'Backspace', 'a', '0', etc. — see chromiumoxide::keys::USKEYBOARD_LAYOUT)"
            ))
        })?;
        // Mirror chromiumoxide's PageInner::press_key text-decoration logic so
        // single-char keys actually insert characters into focused inputs.
        let key_text: Option<&'static str> = if let Some(t) = kd.text {
            Some(t)
        } else if kd.key.len() == 1 {
            Some(kd.key)
        } else {
            None
        };
        let down_type = if key_text.is_some() {
            DispatchKeyEventType::KeyDown
        } else {
            DispatchKeyEventType::RawKeyDown
        };
        let modifiers_i = modifiers as i64;

        let mut down = DispatchKeyEventParams::builder()
            .r#type(down_type)
            .key(kd.key)
            .code(kd.code)
            .windows_virtual_key_code(kd.key_code)
            .native_virtual_key_code(kd.key_code)
            .modifiers(modifiers_i);
        if let Some(t) = key_text {
            down = down.text(t);
        }
        let down_cmd = down
            .build()
            .map_err(|e| Error::Backend(format!("press_key down build: {e}")))?;
        p.execute(down_cmd)
            .await
            .map_err(|e| Error::Backend(format!("press_key down send: {e}")))?;

        let up_cmd = DispatchKeyEventParams::builder()
            .r#type(DispatchKeyEventType::KeyUp)
            .key(kd.key)
            .code(kd.code)
            .windows_virtual_key_code(kd.key_code)
            .native_virtual_key_code(kd.key_code)
            .modifiers(modifiers_i)
            .build()
            .map_err(|e| Error::Backend(format!("press_key up build: {e}")))?;
        p.execute(up_cmd)
            .await
            .map_err(|e| Error::Backend(format!("press_key up send: {e}")))?;
        Ok(())
    }

    async fn select_option(
        &self,
        page: &PageId,
        selector: &str,
        value: &str,
    ) -> Result<serde_json::Value> {
        let p = self.page_handle(page)?;
        let sel_lit = serde_json::to_string(selector).map_err(Error::Serde)?;
        let val_lit = serde_json::to_string(value).map_err(Error::Serde)?;
        let js = format!(
            "(() => {{
                const sel = {sel_lit}; const val = {val_lit};
                const el = document.querySelector(sel);
                if (!el) throw new Error('select_option: no element for selector');
                if (el.tagName !== 'SELECT') {{
                    throw new Error('select_option: element is <' + el.tagName + '>, not <SELECT>');
                }}
                let matched = -1;
                for (let i = 0; i < el.options.length; i++) {{
                    const opt = el.options[i];
                    if (opt.value === val || opt.text === val) {{
                        opt.selected = true; el.selectedIndex = i; matched = i; break;
                    }}
                }}
                if (matched < 0) {{
                    const labels = Array.from(el.options).map(o => o.value + '|' + o.text).join(', ');
                    throw new Error('select_option: no option matches; available = ' + labels);
                }}
                el.dispatchEvent(new Event('input', {{ bubbles: true }}));
                el.dispatchEvent(new Event('change', {{ bubbles: true }}));
                return {{
                    selectedIndex: el.selectedIndex,
                    selectedValue: el.options[matched].value,
                    selectedText: el.options[matched].text
                }};
            }})()"
        );
        eval_with_exception_details(&p, &js).await
    }

    async fn find_by_text(
        &self,
        page: &PageId,
        text: &str,
        tag_filter: Option<&str>,
    ) -> Result<serde_json::Value> {
        let p = self.page_handle(page)?;
        let text_lit = serde_json::to_string(text).map_err(Error::Serde)?;
        let tag_lit = serde_json::to_string(tag_filter.unwrap_or("*")).map_err(Error::Serde)?;
        // Deepest-match strategy: collect all elements containing `text`,
        // then keep only those with no descendant also containing the text.
        // Build a CSS selector path for each (id-anchored when possible,
        // nth-of-type otherwise). Cap output at 5 hits.
        let js = format!(
            "(() => {{
                const text = {text_lit};
                const tag = {tag_lit};
                const all = Array.from(document.querySelectorAll(tag));
                const hits = all.filter(el => {{
                    const t = (el.innerText || el.textContent || '').toString();
                    return t.includes(text);
                }});
                const deepest = hits.filter(el =>
                    !hits.some(other => other !== el && el.contains(other))
                );
                const buildSelector = (el) => {{
                    const path = [];
                    let cur = el;
                    while (cur && cur.tagName && cur !== document) {{
                        let s = cur.tagName.toLowerCase();
                        if (cur.id && /^[a-zA-Z][\\w-]*$/.test(cur.id)) {{
                            s += '#' + cur.id;
                            path.unshift(s); break;
                        }}
                        if (cur.parentNode) {{
                            const sib = Array.from(cur.parentNode.children).filter(c => c.tagName === cur.tagName);
                            if (sib.length > 1) {{
                                s += ':nth-of-type(' + (sib.indexOf(cur) + 1) + ')';
                            }}
                        }}
                        path.unshift(s);
                        cur = cur.parentNode;
                    }}
                    return path.join(' > ');
                }};
                const out = deepest.slice(0, 5).map(el => ({{
                    tag: el.tagName.toLowerCase(),
                    text: ((el.innerText || el.textContent || '') + '').trim().slice(0, 200),
                    selector: buildSelector(el),
                    role: el.getAttribute('role'),
                    aria_label: el.getAttribute('aria-label')
                }}));
                return {{ count: out.length, matches: out }};
            }})()"
        );
        eval_with_exception_details(&p, &js).await
    }

    async fn list_frames(&self, page: &PageId) -> Result<serde_json::Value> {
        let p = self.page_handle(page)?;
        // Same-process frames via Page.getFrameTree (visible to this page's
        // own session). Each entry is tagged kind="main" (root) or "frame".
        let resp = p
            .execute(GetFrameTreeParams::default())
            .await
            .map_err(|e| Error::Backend(format!("getFrameTree: {e}")))?;
        let mut flat = Vec::new();
        flatten_frame_tree(&resp.result.frame_tree, None, &mut flat);
        for (idx, entry) in flat.iter_mut().enumerate() {
            if let Some(obj) = entry.as_object_mut() {
                obj.insert(
                    "kind".into(),
                    serde_json::Value::String(
                        if idx == 0 { "main" } else { "frame" }.into(),
                    ),
                );
            }
        }
        // Cross-origin iframes (OOPIFs) live in their own targets — invisible
        // to per-page getFrameTree. Pull them via Target.getTargets at the
        // browser level and append with kind="oopif". Stripe Elements,
        // reCAPTCHA, Auth0, and most modern OAuth widgets land here.
        let browser = self.ensure_browser().await?;
        if let Ok(resp) = browser.execute(GetTargetsParams::default()).await {
            for ti in &resp.result.target_infos {
                if ti.r#type == "iframe" {
                    flat.push(serde_json::json!({
                        "frame_id": ti.target_id.inner(),
                        "url": ti.url,
                        "name": serde_json::Value::Null,
                        "parent_id": ti.parent_frame_id.as_ref().map(|f| f.inner().clone()),
                        "kind": "oopif",
                    }));
                }
            }
        }
        Ok(serde_json::json!({ "count": flat.len(), "frames": flat }))
    }

    async fn eval_in_frame(
        &self,
        page: &PageId,
        frame_id: Option<&str>,
        frame_url_substring: Option<&str>,
        js: &str,
    ) -> Result<serde_json::Value> {
        let p = self.page_handle(page)?;
        let browser = self.ensure_browser().await?;

        // OOPIF dispatch first: cross-origin iframes have their own target
        // and don't appear in Page.getFrameTree. Match by exact target_id
        // OR by URL substring.
        if let Ok(targets_resp) = browser.execute(GetTargetsParams::default()).await {
            let oopif: Option<&TargetInfo> = targets_resp
                .result
                .target_infos
                .iter()
                .find(|ti| ti.r#type == "iframe" && oopif_matches(ti, frame_id, frame_url_substring));
            if let Some(ti) = oopif {
                // chromiumoxide's per-page setAutoAttach doesn't auto-attach
                // foreign-page OOPIFs, so the target is in pin.targets but
                // has no session_id and get_page returns NotFound. Force the
                // attach (flatten=true so chromiumoxide's existing
                // on_attached_to_target stores the session) before fetching.
                let attach = AttachToTargetParams::builder()
                    .target_id(ti.target_id.clone())
                    .flatten(true)
                    .build()
                    .map_err(|e| Error::Backend(format!("attachToTarget build: {e}")))?;
                let _ = browser.execute(attach).await.map_err(|e| {
                    Error::Backend(format!("attachToTarget (oopif {}): {e}", ti.url))
                })?;
                let oopif_page = browser
                    .get_page(ti.target_id.clone())
                    .await
                    .map_err(|e| Error::Backend(format!("get_page (oopif): {e}")))?;
                return eval_with_exception_details(&oopif_page, js).await;
            }
        }

        // Same-process path: resolve FrameId from same-process tree, then
        // Page.createIsolatedWorld + Runtime.evaluate(contextId).
        let target_fid = if let Some(fid) = frame_id.filter(|s| !s.is_empty()) {
            FrameId::new(fid.to_string())
        } else if let Some(sub) = frame_url_substring.filter(|s| !s.is_empty()) {
            let resp = p
                .execute(GetFrameTreeParams::default())
                .await
                .map_err(|e| Error::Backend(format!("getFrameTree: {e}")))?;
            let mut found = None;
            find_frame_by_url(&resp.result.frame_tree, sub, &mut found);
            match found {
                Some(fid) => fid,
                None => {
                    return Err(Error::Backend(format!(
                        "eval_in_frame: no frame URL contains '{sub}' — list_frames to inspect"
                    )));
                }
            }
        } else {
            return Err(Error::Backend(
                "eval_in_frame: pass either frame_id or frame_url_substring".into(),
            ));
        };

        // Mint an isolated world in the target frame and grab its execution
        // context id; this works across origin boundaries that parent JS cannot.
        let iw = p
            .execute(
                CreateIsolatedWorldParams::builder()
                    .frame_id(target_fid)
                    .world_name("agent-bridge-iso")
                    .build()
                    .map_err(|e| {
                        Error::Backend(format!("createIsolatedWorld build: {e}"))
                    })?,
            )
            .await
            .map_err(|e| Error::Backend(format!("createIsolatedWorld: {e}")))?;
        let ctx_id = iw.result.execution_context_id.clone();

        // Evaluate with the isolated-world contextId.
        let params = EvaluateParams::builder()
            .expression(js.to_string())
            .return_by_value(true)
            .await_promise(true)
            .context_id(ctx_id)
            .build()
            .map_err(|e| Error::Backend(format!("evaluate (frame) build: {e}")))?;
        let resp = p
            .execute(params)
            .await
            .map_err(|e| Error::Backend(format!("evaluate (frame) execute: {e}")))?;
        let result = &resp.result;
        if let Some(ex) = &result.exception_details {
            let url = ex.url.as_deref().unwrap_or("(inline)");
            let line = ex.line_number;
            let col = ex.column_number;
            let head = &ex.text;
            let detail = ex
                .exception
                .as_ref()
                .and_then(|e| e.description.as_deref())
                .unwrap_or("");
            let where_part = if !detail.is_empty() {
                format!("{head}: {detail}")
            } else {
                head.clone()
            };
            return Err(Error::Backend(format!(
                "evaluate (frame) exception @ {url}:{line}:{col}: {where_part}"
            )));
        }
        Ok(result
            .result
            .value
            .clone()
            .unwrap_or(serde_json::Value::Null))
    }

    async fn scroll(
        &self,
        page: &PageId,
        selector: Option<&str>,
        dx: f64,
        dy: f64,
    ) -> Result<serde_json::Value> {
        let p = match self.pages.get(page.as_str()) {
            Some(p) => p.clone(),
            None => return Err(Error::NotFound(format!("page not tracked: {}", page.as_str()))),
        };
        if let Some(sel) = selector {
            let el = p
                .find_element(sel.to_string())
                .await
                .map_err(|e| Error::Backend(format!("find_element {sel}: {e}")))?;
            el.scroll_into_view()
                .await
                .map_err(|e| Error::Backend(format!("scroll_into_view: {e}")))?;
        } else if dx != 0.0 || dy != 0.0 {
            let js = format!("window.scrollBy({dx}, {dy})");
            self.eval(page, &js).await?;
        }
        // Always report current scroll offset so the agent can verify.
        self.eval(
            page,
            "({scrollX: window.scrollX, scrollY: window.scrollY, scrollHeight: document.documentElement.scrollHeight})",
        )
        .await
    }

    async fn hover(&self, page: &PageId, selector: &str) -> Result<()> {
        let p = match self.pages.get(page.as_str()) {
            Some(p) => p.clone(),
            None => return Err(Error::NotFound(format!("page not tracked: {}", page.as_str()))),
        };
        let el = p
            .find_element(selector.to_string())
            .await
            .map_err(|e| Error::Backend(format!("find_element {selector}: {e}")))?;
        el.hover()
            .await
            .map_err(|e| Error::Backend(format!("hover: {e}")))?;
        Ok(())
    }

    async fn pause_for_human(&self, page: &PageId, timeout_ms: u64) -> Result<PauseOutcome> {
        let timeout_ms = timeout_ms.clamp(1_000, 1_800_000);
        let key = page.as_str().to_string();
        let (tx, rx) = oneshot::channel::<PauseSignal>();
        // Insert atomically. If a previous waiter exists, it's superseded —
        // notify it so it doesn't hang forever.
        {
            let mut waiters = self.pause_waiters.lock().await;
            if let Some(prev) = waiters.insert(key.clone(), tx) {
                let _ = prev.send(PauseSignal::Superseded);
            }
        }
        let started = Instant::now();
        let outcome = match tokio::time::timeout(Duration::from_millis(timeout_ms), rx).await {
            Ok(Ok(PauseSignal::Resumed)) => "resumed",
            Ok(Ok(PauseSignal::Superseded)) => "superseded",
            Ok(Err(_)) => "resumed", // sender dropped — treat as resume
            Err(_) => {
                // Timed out — clean ourselves out of the map. Only remove if
                // we're still the registered waiter (a superseder may have
                // already replaced us, in which case leave their entry alone).
                let mut waiters = self.pause_waiters.lock().await;
                if let Some(entry) = waiters.get(&key) {
                    if entry.is_closed() {
                        waiters.remove(&key);
                    }
                }
                "timeout"
            }
        };
        Ok(PauseOutcome {
            outcome: outcome.into(),
            elapsed_ms: started.elapsed().as_millis() as u64,
        })
    }

    async fn capture_response_start(
        &self,
        page: &PageId,
        url_substring: &str,
        max_buffer: usize,
    ) -> Result<()> {
        if url_substring.is_empty() {
            return Err(Error::InvalidArgument("url_substring is empty".into()));
        }
        let max_buffer = max_buffer.clamp(1, 200);
        let key = page.as_str().to_string();
        let p = match self.pages.get(&key) {
            Some(p) => p.clone(),
            None => return Err(Error::NotFound(format!("page not tracked: {key}"))),
        };
        // Enable Network domain (idempotent server-side).
        p.execute(NetworkEnableParams::default())
            .await
            .map_err(|e| Error::Backend(format!("Network.enable: {e}")))?;
        // Subscribe to both events before spawning the pump so no
        // in-flight responses are dropped between subscribe and pump-start.
        let resp_listener = p
            .event_listener::<EventResponseReceived>()
            .await
            .map_err(|e| Error::Backend(format!("event_listener(ResponseReceived): {e}")))?;
        let done_listener = p
            .event_listener::<EventLoadingFinished>()
            .await
            .map_err(|e| Error::Backend(format!("event_listener(LoadingFinished): {e}")))?;

        let state = Arc::new(CaptureState {
            url_substring: url_substring.to_string(),
            buffer: Mutex::new(VecDeque::with_capacity(max_buffer)),
            max_buffer,
            arrival: Notify::new(),
        });
        let pump = tokio::spawn(run_capture_pump(
            p.clone(),
            state.clone(),
            resp_listener,
            done_listener,
        ));
        let abort = pump.abort_handle();
        // Detach JoinHandle: we never join, only abort.
        drop(pump);

        let mut captures = self.captures.lock().await;
        if let Some((_prior_state, prior_abort)) = captures.remove(&key) {
            prior_abort.abort();
        }
        captures.insert(key, (state, abort));
        Ok(())
    }

    async fn capture_response_drain(
        &self,
        page: &PageId,
        until_ms: u64,
        max_results: usize,
    ) -> Result<Vec<CapturedResponse>> {
        let key = page.as_str().to_string();
        let max_results = max_results.clamp(1, 200);
        let until_ms = until_ms.min(60_000);
        let state = {
            let captures = self.captures.lock().await;
            match captures.get(&key) {
                Some((s, _abort)) => s.clone(),
                None => {
                    return Err(Error::NotFound(format!(
                        "no active capture on page: {key}"
                    )));
                }
            }
        };
        // Fast path: already have something buffered.
        {
            let buf = state.buffer.lock().await;
            if !buf.is_empty() {
                drop(buf);
                return Ok(drain_buffer(&state, max_results).await);
            }
        }
        // Slow path: wait up to until_ms for first arrival.
        if until_ms > 0 {
            let _ = tokio::time::timeout(
                Duration::from_millis(until_ms),
                state.arrival.notified(),
            )
            .await;
        }
        Ok(drain_buffer(&state, max_results).await)
    }

    async fn resume(&self, page: &PageId) -> Result<bool> {
        let key = page.as_str().to_string();
        let tx = {
            let mut waiters = self.pause_waiters.lock().await;
            waiters.remove(&key)
        };
        match tx {
            Some(tx) => {
                let _ = tx.send(PauseSignal::Resumed);
                Ok(true)
            }
            None => Ok(false),
        }
    }

    async fn reload(&self, page: &PageId) -> Result<()> {
        let p = match self.pages.get(page.as_str()) {
            Some(p) => p.clone(),
            None => return Err(Error::NotFound(format!("page not tracked: {}", page.as_str()))),
        };
        p.reload()
            .await
            .map_err(|e| Error::Backend(format!("reload: {e}")))?;
        Ok(())
    }

    async fn go_back(&self, page: &PageId) -> Result<()> {
        // history.back() is async; eval returns before navigation
        // commits. Caller is expected to chase with wait_for if needed.
        self.eval(page, "window.history.back();").await?;
        Ok(())
    }

    async fn go_forward(&self, page: &PageId) -> Result<()> {
        self.eval(page, "window.history.forward();").await?;
        Ok(())
    }

    async fn close(&self, page: &PageId) -> Result<()> {
        // Release any pending pause waiter on this page so resume-less
        // close() doesn't strand a request.
        {
            let mut waiters = self.pause_waiters.lock().await;
            if let Some(tx) = waiters.remove(page.as_str()) {
                let _ = tx.send(PauseSignal::Resumed);
            }
        }
        // Abort any active capture pump so it doesn't outlive the page.
        {
            let mut captures = self.captures.lock().await;
            if let Some((_state, abort)) = captures.remove(page.as_str()) {
                abort.abort();
            }
        }
        if let Some((_, p)) = self.pages.remove(page.as_str()) {
            // `Arc<Page>` may have outstanding references; if we're the last
            // we close cleanly. Either way, ignore close errors on shutdown.
            if let Ok(p) = Arc::try_unwrap(p) {
                let _ = p.close().await;
            }
        }
        Ok(())
    }
}

/// Pull up to `max_results` entries off the front of `state.buffer`,
/// preserving FIFO order. Used by `capture_response_drain`.
async fn drain_buffer(state: &CaptureState, max_results: usize) -> Vec<CapturedResponse> {
    let mut buf = state.buffer.lock().await;
    let n = buf.len().min(max_results);
    buf.drain(..n).collect()
}

/// Two-stream pump for `capture_response_start`. Subscribes to
/// `Network.responseReceived` (header arrival, with URL + status +
/// headers) and `Network.loadingFinished` (body fully loaded). On
/// matching ResponseReceived, stash metadata in `pending`. On
/// LoadingFinished, look up by request_id; if matched, fetch body via
/// `Network.getResponseBody` and push to the ring buffer.
///
/// Aborts cleanly when the parent's `AbortHandle::abort()` is called —
/// `select!` polls the futures directly, so an `abort()` immediately
/// drops the in-flight `getResponseBody` call.
async fn run_capture_pump(
    page: Arc<Page>,
    state: Arc<CaptureState>,
    mut resp_listener: chromiumoxide::listeners::EventStream<EventResponseReceived>,
    mut done_listener: chromiumoxide::listeners::EventStream<EventLoadingFinished>,
) {
    use std::collections::HashMap as StdHashMap;
    struct Pending {
        url: String,
        status: i64,
        resource_type: String,
        mime_type: String,
        headers: serde_json::Value,
    }
    let mut pending: StdHashMap<String, Pending> = StdHashMap::new();
    loop {
        tokio::select! {
            ev = resp_listener.next() => {
                let Some(ev) = ev else { return; };
                let url = ev.response.url.clone();
                if !url.contains(&state.url_substring) { continue; }
                let req_id = ev.request_id.inner().clone();
                let headers = ev.response.headers.inner().clone();
                pending.insert(req_id, Pending {
                    url,
                    status: ev.response.status,
                    resource_type: format!("{:?}", ev.r#type),
                    mime_type: ev.response.mime_type.clone(),
                    headers,
                });
            }
            ev = done_listener.next() => {
                let Some(ev) = ev else { return; };
                let req_id = ev.request_id.inner().clone();
                let Some(meta) = pending.remove(&req_id) else { continue; };
                let body_res = page
                    .execute(GetResponseBodyParams {
                        request_id: ev.request_id.clone(),
                    })
                    .await;
                let (body, base64_encoded) = match body_res {
                    Ok(r) => (r.result.body.clone(), r.result.base64_encoded),
                    Err(e) => {
                        debug!(req_id, error = %e, "getResponseBody failed; skipping");
                        continue;
                    }
                };
                let ts_ms = std::time::SystemTime::now()
                    .duration_since(std::time::UNIX_EPOCH)
                    .map(|d| d.as_millis() as u64)
                    .unwrap_or(0);
                state.push(CapturedResponse {
                    request_id: req_id,
                    url: meta.url,
                    status: meta.status,
                    resource_type: meta.resource_type,
                    mime_type: meta.mime_type,
                    body,
                    base64_encoded,
                    headers: meta.headers,
                    ts_ms,
                }).await;
            }
        }
    }
}

/// Walk a [`FrameTree`] (root + child_frames) into a flat `Vec` of
/// JSON `{frame_id, url, name, parent_id}` rows. Invoked by `list_frames`.
fn flatten_frame_tree(
    tree: &FrameTree,
    parent_id: Option<&str>,
    out: &mut Vec<serde_json::Value>,
) {
    let frame = &tree.frame;
    out.push(serde_json::json!({
        "frame_id": frame.id.inner(),
        "url": frame.url,
        "name": frame.name,
        "parent_id": parent_id,
    }));
    if let Some(children) = &tree.child_frames {
        let me = frame.id.inner().clone();
        for child in children {
            flatten_frame_tree(child, Some(me.as_str()), out);
        }
    }
}

/// Predicate for matching an OOPIF [`TargetInfo`] against caller's
/// `frame_id` (exact target_id match) or `frame_url_substring`.
fn oopif_matches(
    ti: &TargetInfo,
    frame_id: Option<&str>,
    frame_url_substring: Option<&str>,
) -> bool {
    if let Some(fid) = frame_id.filter(|s| !s.is_empty()) {
        return ti.target_id.inner() == fid;
    }
    if let Some(sub) = frame_url_substring.filter(|s| !s.is_empty()) {
        return ti.url.contains(sub);
    }
    false
}

/// Walk a [`FrameTree`] looking for the first frame whose URL contains
/// `substring`. On hit, sets `out` and short-circuits further traversal.
fn find_frame_by_url(tree: &FrameTree, substring: &str, out: &mut Option<FrameId>) {
    if out.is_some() {
        return;
    }
    if tree.frame.url.contains(substring) {
        *out = Some(tree.frame.id.clone());
        return;
    }
    if let Some(children) = &tree.child_frames {
        for child in children {
            find_frame_by_url(child, substring, out);
            if out.is_some() {
                return;
            }
        }
    }
}

/// Look up a [`KeyDefinition`] from US keyboard layout, matching either the
/// human-readable key (`"Enter"`, `"a"`) or the DOM `code` (`"KeyA"`,
/// `"Enter"`).
fn lookup_key(key: &str) -> Option<&'static KeyDefinition> {
    USKEYBOARD_LAYOUT
        .iter()
        .find(|k| k.key == key || k.code == key)
}

/// Resolve the chrome user-data-dir (login/cookies persist here across daemon
/// restarts). Honours `AGENT_BRIDGE_BROWSER_PROFILE`; defaults to
/// `$HOME/.cache/agent-bridge/chrome-profile`.
fn resolve_user_data_dir() -> PathBuf {
    if let Ok(custom) = std::env::var("AGENT_BRIDGE_BROWSER_PROFILE") {
        if !custom.trim().is_empty() {
            return PathBuf::from(custom);
        }
    }
    if let Ok(home) = std::env::var("HOME") {
        if !home.is_empty() {
            return PathBuf::from(home).join(".cache/agent-bridge/chrome-profile");
        }
    }
    std::env::temp_dir().join(format!("agent-bridge-chrome-{}", std::process::id()))
}

/// Run `js` via raw CDP `Runtime.evaluate` and surface JS exceptions with
/// `text @ url:line:col` instead of the previous opaque chromiumoxide
/// `Backend("evaluate: ...")` string. Used by all eval-driven backend methods.
async fn eval_with_exception_details(p: &Page, js: &str) -> Result<serde_json::Value> {
    let params = EvaluateParams::builder()
        .expression(js.to_string())
        .return_by_value(true)
        .await_promise(true)
        .build()
        .map_err(|e| Error::Backend(format!("evaluate params build: {e}")))?;
    let resp = p
        .execute(params)
        .await
        .map_err(|e| Error::Backend(format!("evaluate execute: {e}")))?;
    let result = &resp.result;
    if let Some(ex) = &result.exception_details {
        let url = ex.url.as_deref().unwrap_or("(inline)");
        let line = ex.line_number;
        let col = ex.column_number;
        let head = &ex.text;
        let detail = ex
            .exception
            .as_ref()
            .and_then(|e| e.description.as_deref())
            .unwrap_or("");
        let where_part = if !detail.is_empty() {
            format!("{head}: {detail}")
        } else {
            head.clone()
        };
        return Err(Error::Backend(format!(
            "evaluate exception @ {url}:{line}:{col}: {where_part}"
        )));
    }
    Ok(result
        .result
        .value
        .clone()
        .unwrap_or(serde_json::Value::Null))
}

fn json_eval_result_as_plain_text(v: &serde_json::Value) -> String {
    match v {
        serde_json::Value::String(s) => s.clone(),
        serde_json::Value::Null => String::new(),
        serde_json::Value::Bool(b) => b.to_string(),
        serde_json::Value::Number(n) => n.to_string(),
        _ => v.to_string(),
    }
}

/// Convert chromiumoxide's flat AXNode list into our nested [`A11yNode`].
fn build_a11y_tree(
    nodes: &[chromiumoxide::cdp::browser_protocol::accessibility::AxNode],
) -> A11yNode {
    use std::collections::HashMap;
    let mut by_id: HashMap<String, &chromiumoxide::cdp::browser_protocol::accessibility::AxNode> =
        HashMap::with_capacity(nodes.len());
    for n in nodes {
        by_id.insert(n.node_id.inner().clone(), n);
    }
    let root = nodes.first().cloned().map(|n| convert(&n, &by_id));
    root.unwrap_or_else(|| A11yNode {
        role: "root".into(),
        name: None,
        value: None,
        children: vec![],
    })
}

fn convert(
    node: &chromiumoxide::cdp::browser_protocol::accessibility::AxNode,
    by_id: &std::collections::HashMap<
        String,
        &chromiumoxide::cdp::browser_protocol::accessibility::AxNode,
    >,
) -> A11yNode {
    let role = node
        .role
        .as_ref()
        .and_then(|v| ax_value_to_string(&v.value))
        .unwrap_or_else(|| "unknown".into());
    let name = node
        .name
        .as_ref()
        .and_then(|v| ax_value_to_string(&v.value));
    let value = node
        .value
        .as_ref()
        .and_then(|v| ax_value_to_string(&v.value));
    let children = node
        .child_ids
        .as_ref()
        .map(|ids| {
            ids.iter()
                .filter_map(|id| by_id.get(id.inner()).map(|c| convert(c, by_id)))
                .collect()
        })
        .unwrap_or_default();

    A11yNode {
        role,
        name,
        value,
        children,
    }
}

/// `AxValue.value` is `Option<serde_json::Value>` — flatten it down to a
/// human-readable string when present.
fn ax_value_to_string(v: &Option<serde_json::Value>) -> Option<String> {
    let val = v.as_ref()?;
    if let Some(s) = val.as_str() {
        Some(s.to_string())
    } else {
        Some(val.to_string())
    }
}
