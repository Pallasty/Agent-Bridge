use ab_core::{NotifyEvent, NotifySeverity, NotifySource, PageId, PaneId, RpcRequest, RpcResponse};
use ab_terminal::{OscEvent, OscParser, SplitDir};
use serde_json::{json, Value};
use tracing::debug;

use crate::hub::Hub;

#[derive(Clone)]
pub struct Router {
    hub: Hub,
}

impl Router {
    pub fn new(hub: Hub) -> Self {
        Self { hub }
    }

    pub async fn dispatch(&self, req: RpcRequest) -> RpcResponse {
        debug!(method = %req.method, id = req.id, "dispatch");

        match req.method.as_str() {
            "system.ping" => RpcResponse::success(req.id, json!({ "pong": true })),
            "system.capabilities" => self.handle_capabilities(req),

            "notify.send" => {
                let evt = build_notify(req.params.unwrap_or(Value::Null));
                let (delivered, persisted) = self.hub.deliver(&evt).await;
                RpcResponse::success(
                    req.id,
                    json!({ "delivered": delivered, "persisted": persisted }),
                )
            }
            "notifications.recent" => self.handle_recent(req).await,
            "osc.parse" => self.handle_osc_parse(req).await,

            "terminal.list" => self.handle_term_list(req).await,
            "terminal.send_keys" => self.handle_term_send_keys(req).await,
            "terminal.split" => self.handle_term_split(req).await,

            "browser.navigate" => self.handle_browser_navigate(req).await,
            "browser.eval" => self.handle_browser_eval(req).await,
            "browser.snapshot" => self.handle_browser_snapshot(req).await,
            "browser.click" => self.handle_browser_click(req).await,
            "browser.screenshot" => self.handle_browser_screenshot(req).await,

            other => RpcResponse::fail(req.id, -32601, format!("unknown method: {other}")),
        }
    }

    fn handle_capabilities(&self, req: RpcRequest) -> RpcResponse {
        RpcResponse::success(
            req.id,
            json!({
                "methods": [
                    "system.ping", "system.capabilities",
                    "notify.send", "notifications.recent", "osc.parse",
                    "terminal.list", "terminal.send_keys", "terminal.split",
                    "browser.navigate", "browser.eval", "browser.snapshot",
                    "browser.click", "browser.screenshot",
                ],
                "notifiers": self.hub.notifiers.iter().map(|n| n.id()).collect::<Vec<_>>(),
                "store": self.hub.store.is_some(),
                "terminal": self.hub.terminal.as_ref().map(|t| t.id()),
                "browser": self.hub.browser.as_ref().map(|b| b.id()),
            }),
        )
    }

    async fn handle_recent(&self, req: RpcRequest) -> RpcResponse {
        let store = match &self.hub.store {
            Some(s) => s.clone(),
            None => return RpcResponse::fail(req.id, -32004, "no store configured"),
        };
        let limit = req
            .params
            .as_ref()
            .and_then(|p| p.get("limit"))
            .and_then(|v| v.as_u64())
            .unwrap_or(20)
            .min(1000) as u32;
        match store.recent_notifications(limit).await {
            Ok(rows) => match serde_json::to_value(&rows) {
                Ok(v) => RpcResponse::success(req.id, json!({ "notifications": v })),
                Err(e) => RpcResponse::fail(req.id, -32603, format!("serialize: {e}")),
            },
            Err(e) => RpcResponse::fail(req.id, -32000, format!("store error: {e}")),
        }
    }

    async fn handle_osc_parse(&self, req: RpcRequest) -> RpcResponse {
        let params = req.params.unwrap_or(Value::Null);
        let raw = params
            .get("raw")
            .and_then(|v| v.as_str())
            .unwrap_or("")
            .as_bytes()
            .to_vec();
        let mut parser = OscParser::new();
        let events = parser.feed(&raw);
        let mut delivered = 0u32;
        let mut malformed = Vec::new();
        for e in &events {
            match e {
                OscEvent::Notify(evt) => {
                    let (d, _p) = self.hub.deliver(evt).await;
                    if d > 0 {
                        delivered += 1;
                    }
                }
                OscEvent::Malformed { code, reason, .. } => {
                    malformed.push(json!({ "code": code, "reason": reason }));
                }
                // OSC 133 prompt markers flow through the read_blocks
                // state machine, not the notification fan-out.
                OscEvent::Prompt(_) => {}
            }
        }
        RpcResponse::success(
            req.id,
            json!({
                "events": events.len(),
                "delivered": delivered,
                "malformed": malformed,
            }),
        )
    }

    // -------- terminal --------

    async fn handle_term_list(&self, req: RpcRequest) -> RpcResponse {
        let term = match &self.hub.terminal {
            Some(t) => t.clone(),
            None => return RpcResponse::fail(req.id, -32005, "no terminal backend configured"),
        };
        match term.list_panes().await {
            Ok(panes) => match serde_json::to_value(&panes) {
                Ok(v) => RpcResponse::success(req.id, json!({ "panes": v })),
                Err(e) => RpcResponse::fail(req.id, -32603, format!("serialize: {e}")),
            },
            Err(e) => RpcResponse::fail(req.id, -32000, format!("terminal: {e}")),
        }
    }

    async fn handle_term_send_keys(&self, req: RpcRequest) -> RpcResponse {
        let term = match &self.hub.terminal {
            Some(t) => t.clone(),
            None => return RpcResponse::fail(req.id, -32005, "no terminal backend configured"),
        };
        let params = req.params.unwrap_or(Value::Null);
        let pane = match params.get("pane").and_then(|v| v.as_str()) {
            Some(s) => PaneId::from_raw(s.to_string()),
            None => return RpcResponse::fail(req.id, -32602, "missing 'pane'"),
        };
        let keys = params.get("keys").and_then(|v| v.as_str()).unwrap_or("");
        match term.send_keys(&pane, keys).await {
            Ok(()) => RpcResponse::success(req.id, json!({ "ok": true })),
            Err(e) => RpcResponse::fail(req.id, -32000, format!("terminal: {e}")),
        }
    }

    async fn handle_term_split(&self, req: RpcRequest) -> RpcResponse {
        let term = match &self.hub.terminal {
            Some(t) => t.clone(),
            None => return RpcResponse::fail(req.id, -32005, "no terminal backend configured"),
        };
        let params = req.params.unwrap_or(Value::Null);
        let pane = match params.get("pane").and_then(|v| v.as_str()) {
            Some(s) => PaneId::from_raw(s.to_string()),
            None => return RpcResponse::fail(req.id, -32602, "missing 'pane'"),
        };
        let dir = match params
            .get("dir")
            .and_then(|v| v.as_str())
            .unwrap_or("vertical")
        {
            "horizontal" => SplitDir::Horizontal,
            _ => SplitDir::Vertical,
        };
        match term.split(&pane, dir).await {
            Ok(new_pane) => RpcResponse::success(req.id, json!({ "pane": new_pane.as_str() })),
            Err(e) => RpcResponse::fail(req.id, -32000, format!("terminal: {e}")),
        }
    }

    // -------- browser --------

    async fn handle_browser_navigate(&self, req: RpcRequest) -> RpcResponse {
        let b = match &self.hub.browser {
            Some(b) => b.clone(),
            None => return RpcResponse::fail(req.id, -32006, "no browser backend configured"),
        };
        let url = req
            .params
            .as_ref()
            .and_then(|p| p.get("url"))
            .and_then(|v| v.as_str())
            .unwrap_or("");
        if url.is_empty() {
            return RpcResponse::fail(req.id, -32602, "missing 'url'");
        }
        match b.navigate(url).await {
            Ok(pid) => RpcResponse::success(req.id, json!({ "page": pid.as_str() })),
            Err(e) => RpcResponse::fail(req.id, -32000, format!("browser: {e}")),
        }
    }

    async fn handle_browser_eval(&self, req: RpcRequest) -> RpcResponse {
        let b = match &self.hub.browser {
            Some(b) => b.clone(),
            None => return RpcResponse::fail(req.id, -32006, "no browser backend configured"),
        };
        let p = req.params.unwrap_or(Value::Null);
        let page = match p.get("page").and_then(|v| v.as_str()) {
            Some(s) => PageId::from_raw(s.to_string()),
            None => return RpcResponse::fail(req.id, -32602, "missing 'page'"),
        };
        let js = p.get("js").and_then(|v| v.as_str()).unwrap_or("");
        match b.eval(&page, js).await {
            Ok(v) => RpcResponse::success(req.id, json!({ "value": v })),
            Err(e) => RpcResponse::fail(req.id, -32000, format!("browser: {e}")),
        }
    }

    async fn handle_browser_snapshot(&self, req: RpcRequest) -> RpcResponse {
        let b = match &self.hub.browser {
            Some(b) => b.clone(),
            None => return RpcResponse::fail(req.id, -32006, "no browser backend configured"),
        };
        let page = match req
            .params
            .as_ref()
            .and_then(|p| p.get("page"))
            .and_then(|v| v.as_str())
        {
            Some(s) => PageId::from_raw(s.to_string()),
            None => return RpcResponse::fail(req.id, -32602, "missing 'page'"),
        };
        match b.snapshot_a11y(&page).await {
            Ok(tree) => RpcResponse::success(req.id, json!({ "tree": tree })),
            Err(e) => RpcResponse::fail(req.id, -32000, format!("browser: {e}")),
        }
    }

    async fn handle_browser_click(&self, req: RpcRequest) -> RpcResponse {
        let b = match &self.hub.browser {
            Some(b) => b.clone(),
            None => return RpcResponse::fail(req.id, -32006, "no browser backend configured"),
        };
        let p = req.params.unwrap_or(Value::Null);
        let page = match p.get("page").and_then(|v| v.as_str()) {
            Some(s) => PageId::from_raw(s.to_string()),
            None => return RpcResponse::fail(req.id, -32602, "missing 'page'"),
        };
        let sel = p.get("selector").and_then(|v| v.as_str()).unwrap_or("");
        if sel.is_empty() {
            return RpcResponse::fail(req.id, -32602, "missing 'selector'");
        }
        match b.click(&page, sel).await {
            Ok(()) => RpcResponse::success(req.id, json!({ "ok": true })),
            Err(e) => RpcResponse::fail(req.id, -32000, format!("browser: {e}")),
        }
    }

    async fn handle_browser_screenshot(&self, req: RpcRequest) -> RpcResponse {
        let b = match &self.hub.browser {
            Some(b) => b.clone(),
            None => return RpcResponse::fail(req.id, -32006, "no browser backend configured"),
        };
        let p = req.params.unwrap_or(Value::Null);
        let page = match p.get("page").and_then(|v| v.as_str()) {
            Some(s) => PageId::from_raw(s.to_string()),
            None => return RpcResponse::fail(req.id, -32602, "missing 'page'"),
        };
        let bytes = match b.screenshot(&page).await {
            Ok(b) => b,
            Err(e) => return RpcResponse::fail(req.id, -32000, format!("browser: {e}")),
        };
        let path = p
            .get("path")
            .and_then(|v| v.as_str())
            .map(|s| s.to_string())
            .unwrap_or_else(|| {
                std::env::temp_dir()
                    .join(format!("agent-bridge-{page}.png"))
                    .to_string_lossy()
                    .into_owned()
            });
        if let Err(e) = tokio::fs::write(&path, &bytes).await {
            return RpcResponse::fail(req.id, -32000, format!("write {path}: {e}"));
        }
        RpcResponse::success(req.id, json!({ "path": path, "bytes": bytes.len() }))
    }
}

fn build_notify(params: Value) -> NotifyEvent {
    let title = params
        .get("title")
        .and_then(|v| v.as_str())
        .unwrap_or("agent-bridge")
        .to_string();
    let body = params
        .get("body")
        .and_then(|v| v.as_str())
        .unwrap_or("")
        .to_string();
    let severity = params
        .get("severity")
        .and_then(|v| v.as_str())
        .and_then(parse_severity)
        .unwrap_or(NotifySeverity::Info);
    NotifyEvent {
        source: NotifySource::Manual,
        severity,
        title,
        body,
        session_id: None,
        context: Value::Null,
    }
}

fn parse_severity(s: &str) -> Option<NotifySeverity> {
    Some(match s {
        "info" => NotifySeverity::Info,
        "success" => NotifySeverity::Success,
        "warning" => NotifySeverity::Warning,
        "error" => NotifySeverity::Error,
        "attention" => NotifySeverity::Attention,
        _ => return None,
    })
}
