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
use chromiumoxide::cdp::browser_protocol::page::CaptureScreenshotFormat;
use chromiumoxide::page::ScreenshotParams;
use chromiumoxide::{Browser, BrowserConfig, Page};
use dashmap::DashMap;
use futures::StreamExt;
use std::sync::Arc;
use std::time::Duration;
use tokio::sync::RwLock;
use tracing::{debug, info, warn};

use crate::{A11yNode, BrowserBackend};

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

        let browser = Arc::new(Self::launch_chrome().await?);
        *guard = Some(browser.clone());
        Ok(browser)
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
    /// `AGENT_BRIDGE_HEADLESS` and `AGENT_BRIDGE_CHROME`. Each launch picks a
    /// per-PID user-data-dir to avoid Chrome's `SingletonLock` collisions
    /// when multiple agent-bridge daemons coexist.
    async fn launch_chrome() -> Result<Browser> {
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
        let user_data =
            std::env::temp_dir().join(format!("agent-bridge-chrome-{}", std::process::id()));
        cfg = cfg.user_data_dir(user_data);

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
        let val = p
            .evaluate(js)
            .await
            .map_err(|e| Error::Backend(format!("evaluate: {e}")))?;
        // `into_value` deserialises to anything; ask for raw JSON.
        let v: serde_json::Value = val
            .into_value()
            .map_err(|e| Error::Backend(format!("into_value: {e}")))?;
        Ok(v)
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
        let val = p
            .evaluate(JS)
            .await
            .map_err(|e| Error::Backend(format!("extract_text evaluate: {e}")))?;
        let v: serde_json::Value = val
            .into_value()
            .map_err(|e| Error::Backend(format!("extract_text into_value: {e}")))?;
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
        let val = p
            .evaluate(js.as_str())
            .await
            .map_err(|e| Error::Backend(format!("fill_form evaluate: {e}")))?;
        let _: serde_json::Value = val
            .into_value()
            .map_err(|e| Error::Backend(format!("fill_form into_value: {e}")))?;
        Ok(())
    }

    async fn close(&self, page: &PageId) -> Result<()> {
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
