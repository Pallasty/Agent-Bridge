//! Chromium / Chrome backend via Chrome DevTools Protocol (`chromiumoxide`).
//!
//! - Lazy launch: the browser process starts on the first call that needs it.
//! - Headed by default (so you can watch the agent work); set
//!   `AGENT_BRIDGE_HEADLESS=1` to switch to headless.
//! - Pages are tracked in a [`DashMap`] keyed by [`PageId`]; the backend hands
//!   the same id back to the caller for subsequent eval/click/screenshot.

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
use tokio::sync::OnceCell;
use tracing::{debug, info, warn};

use crate::{A11yNode, BrowserBackend};

#[derive(Clone)]
pub struct ChromiumCdpBackend {
    /// Lazily-initialised Chrome connection.
    inner: Arc<OnceCell<Inner>>,
    /// PageId → live Page handle.
    pages: Arc<DashMap<String, Arc<Page>>>,
}

struct Inner {
    _browser: Browser,
}

impl Default for ChromiumCdpBackend {
    fn default() -> Self {
        Self::new()
    }
}

impl ChromiumCdpBackend {
    pub fn new() -> Self {
        Self {
            inner: Arc::new(OnceCell::new()),
            pages: Arc::new(DashMap::new()),
        }
    }

    async fn ensure_browser(&self) -> Result<&Inner> {
        self.inner
            .get_or_try_init(|| async {
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
                // Per-process user-data-dir avoids SingletonLock collisions when
                // multiple agent-bridge daemons (or stale lock files) coexist.
                let user_data = std::env::temp_dir()
                    .join(format!("agent-bridge-chrome-{}", std::process::id()));
                cfg = cfg.user_data_dir(user_data);

                let cfg = cfg
                    .build()
                    .map_err(|e| Error::Backend(format!("BrowserConfig build: {e}")))?;

                let (browser, mut handler) = Browser::launch(cfg)
                    .await
                    .map_err(|e| Error::Backend(format!("chrome launch: {e}")))?;

                // Drive the handler stream to keep the websocket alive.
                tokio::spawn(async move {
                    while let Some(item) = handler.next().await {
                        if let Err(e) = item {
                            warn!(error = %e, "chromiumoxide handler error");
                        }
                    }
                });

                info!(headless, "Chromium CDP backend ready");
                Ok::<_, Error>(Inner { _browser: browser })
            })
            .await
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
        let inner = self.ensure_browser().await?;
        let page = inner
            ._browser
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
    let name = node.name.as_ref().and_then(|v| ax_value_to_string(&v.value));
    let value = node.value.as_ref().and_then(|v| ax_value_to_string(&v.value));
    let children = node
        .child_ids
        .as_ref()
        .map(|ids| {
            ids.iter()
                .filter_map(|id| by_id.get(id.inner()).map(|c| convert(c, by_id)))
                .collect()
        })
        .unwrap_or_default();

    A11yNode { role, name, value, children }
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
