use ab_core::{NotifyEvent, NotifySeverity, NotifySource, PageId, PaneId, RpcRequest, RpcResponse};
use ab_terminal::{OscEvent, OscParser, SplitDir};
use serde_json::{json, Value};
use tracing::debug;

use crate::hub::Hub;
use crate::invocation_lease::rpc_capability;

#[derive(Clone)]
pub struct Router {
    hub: Hub,
}

impl Router {
    pub fn new(hub: Hub) -> Self {
        Self { hub }
    }

    pub async fn dispatch(&self, req: RpcRequest) -> RpcResponse {
        self.dispatch_from_peer(req, None).await
    }

    /// Dispatch a request received from a Unix peer.
    ///
    /// Authorization metadata belongs only at the top level of JSON-RPC
    /// `params`. It is removed before the request reaches an effect handler so
    /// no backend can accidentally interpret transport authority as an effect
    /// argument.
    pub async fn dispatch_from_peer(
        &self,
        mut req: RpcRequest,
        peer_uid: Option<u32>,
    ) -> RpcResponse {
        let authorization_metadata = take_authorization_metadata(&mut req.params);

        if let Err(response) = self
            .pre_dispatch(&req, peer_uid, authorization_metadata.as_ref())
            .await
        {
            return response;
        }

        self.dispatch_effect(req).await
    }

    async fn pre_dispatch(
        &self,
        req: &RpcRequest,
        peer_uid: Option<u32>,
        authorization_metadata: Option<&Value>,
    ) -> Result<(), RpcResponse> {
        if let Some(capability) = rpc_capability(&req.method) {
            if let Err(error) = self.hub.security.check(capability) {
                return Err(RpcResponse::fail(req.id, -32003, error));
            }
        }

        let arguments = req.params.clone().unwrap_or(Value::Null);
        if let Err(error) = self
            .hub
            .invocation_leases
            .authorize_unix(&req.method, &arguments, peer_uid, authorization_metadata)
            .await
        {
            return Err(RpcResponse::fail(req.id, -32003, error.to_string()));
        }
        Ok(())
    }

    async fn dispatch_effect(&self, req: RpcRequest) -> RpcResponse {
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
                "invocation_lease": self.hub.invocation_leases.snapshot(),
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

fn take_authorization_metadata(params: &mut Option<Value>) -> Option<Value> {
    params
        .as_mut()
        .and_then(Value::as_object_mut)
        .and_then(|params| params.remove("_meta"))
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

#[cfg(test)]
mod tests {
    use super::*;
    use crate::agent_spawn_governor::AgentSpawnGovernor;
    use crate::invocation_lease::{
        InvocationLeaseMode, LeasePrincipal, ProvisionedInvocationLeaseAuthority,
    };

    fn backend_free_router() -> Router {
        Router::new(
            Hub::builder()
                .agent_spawn_governor(AgentSpawnGovernor::disabled())
                .build(),
        )
    }

    #[test]
    fn authorization_metadata_is_only_taken_from_top_level_params() {
        let mut params = Some(json!({
            "_meta": { "lease": "opaque" },
            "limit": 7,
            "arguments": { "_meta": { "not_transport_metadata": true } }
        }));

        let metadata = take_authorization_metadata(&mut params);

        assert_eq!(metadata, Some(json!({ "lease": "opaque" })));
        let effect_args = params.expect("effect args remain");
        assert!(effect_args.get("_meta").is_none());
        assert_eq!(effect_args["limit"], 7);
        assert_eq!(
            effect_args["arguments"]["_meta"]["not_transport_metadata"],
            true
        );
    }

    #[tokio::test]
    async fn peer_dispatch_with_metadata_preserves_ping() {
        let response = backend_free_router()
            .dispatch_from_peer(
                RpcRequest::new(
                    41,
                    "system.ping",
                    Some(json!({ "_meta": { "lease": "opaque" } })),
                ),
                Some(1000),
            )
            .await;

        assert!(response.ok);
        assert_eq!(response.result, Some(json!({ "pong": true })));
    }

    #[tokio::test]
    async fn peer_dispatch_with_metadata_preserves_read_path() {
        let response = backend_free_router()
            .dispatch_from_peer(
                RpcRequest::new(
                    42,
                    "system.capabilities",
                    Some(json!({ "_meta": { "lease": "opaque" } })),
                ),
                Some(1000),
            )
            .await;

        assert!(response.ok);
        let capabilities = response.result.expect("capabilities result");
        assert_eq!(capabilities["store"], false);
        assert_eq!(capabilities["terminal"], Value::Null);
        assert_eq!(capabilities["browser"], Value::Null);
    }

    #[tokio::test]
    async fn compatibility_dispatch_still_routes_requests() {
        let response = backend_free_router()
            .dispatch(RpcRequest::new(43, "system.ping", None))
            .await;

        assert!(response.ok);
        assert_eq!(response.result, Some(json!({ "pong": true })));
    }

    #[tokio::test]
    async fn unix_effect_requires_exact_uid_lease_and_consumes_before_handler() {
        let directory = tempfile::tempdir().expect("lease directory");
        let authority = ProvisionedInvocationLeaseAuthority::provision(
            &directory.path().join("leases.sqlite3"),
            InvocationLeaseMode::Enforce,
            &[],
        )
        .expect("provision lease authority");
        let uid = unsafe { libc::geteuid() };
        let exact_arguments = json!({ "pane": "pane-1", "keys": "echo exact" });
        let issued = authority
            .issuer
            .issue_exact(
                LeasePrincipal::UnixUid { uid },
                "terminal.send_keys",
                &exact_arguments,
                60,
                1,
            )
            .await
            .expect("issue exact Unix lease");

        let mut hub = Hub::builder()
            .agent_spawn_governor(AgentSpawnGovernor::disabled())
            .invocation_lease_authorizer(authority.authorizer.clone())
            .build();
        hub.security = Default::default();
        let router = Router::new(hub);

        let mut wrong_arguments = json!({ "pane": "pane-1", "keys": "echo changed" });
        wrong_arguments
            .as_object_mut()
            .expect("object")
            .insert("_meta".into(), issued.authorization_meta());
        let wrong = router
            .dispatch_from_peer(
                RpcRequest::new(44, "terminal.send_keys", Some(wrong_arguments)),
                Some(uid),
            )
            .await;
        assert_eq!(wrong.error.expect("wrong scope denied").code, -32003);

        let mut exact_with_meta = exact_arguments.clone();
        exact_with_meta
            .as_object_mut()
            .expect("object")
            .insert("_meta".into(), issued.authorization_meta());
        let authorized = router
            .dispatch_from_peer(
                RpcRequest::new(45, "terminal.send_keys", Some(exact_with_meta.clone())),
                Some(uid),
            )
            .await;
        assert_eq!(
            authorized
                .error
                .expect("handler reached without backend")
                .code,
            -32005,
            "authorization must consume before the effect handler runs"
        );

        let replay = router
            .dispatch_from_peer(
                RpcRequest::new(46, "terminal.send_keys", Some(exact_with_meta)),
                Some(uid),
            )
            .await;
        assert_eq!(replay.error.expect("replay denied").code, -32003);
    }

    #[tokio::test]
    async fn static_security_policy_is_a_hard_ceiling_before_unix_dispatch() {
        let directory = tempfile::tempdir().expect("lease directory");
        let authority = ProvisionedInvocationLeaseAuthority::provision(
            &directory.path().join("leases.sqlite3"),
            InvocationLeaseMode::Enforce,
            &[],
        )
        .expect("provision lease authority");
        let uid = unsafe { libc::geteuid() };
        let arguments = json!({ "page": "p", "url": "https://example.invalid" });
        let issued = authority
            .issuer
            .issue_exact(
                LeasePrincipal::UnixUid { uid },
                "browser.navigate",
                &arguments,
                60,
                1,
            )
            .await
            .expect("issue browser lease");
        let mut arguments_with_meta = arguments;
        arguments_with_meta
            .as_object_mut()
            .expect("object")
            .insert("_meta".into(), issued.authorization_meta());

        let mut hub = Hub::builder()
            .agent_spawn_governor(AgentSpawnGovernor::disabled())
            .invocation_lease_authorizer(authority.authorizer.clone())
            .build();
        hub.security = Default::default();
        hub.security.allow_browser = false;

        let response = Router::new(hub)
            .dispatch_from_peer(
                RpcRequest::new(47, "browser.navigate", Some(arguments_with_meta.clone())),
                Some(uid),
            )
            .await;

        let error = response.error.expect("policy denial");
        assert_eq!(error.code, -32003);
        assert!(error.message.contains("AB_ALLOW_BROWSER"));

        let mut allowed_hub = Hub::builder()
            .agent_spawn_governor(AgentSpawnGovernor::disabled())
            .invocation_lease_authorizer(authority.authorizer)
            .build();
        allowed_hub.security = Default::default();
        let after_policy_denial = Router::new(allowed_hub)
            .dispatch_from_peer(
                RpcRequest::new(48, "browser.navigate", Some(arguments_with_meta)),
                Some(uid),
            )
            .await;
        assert_eq!(
            after_policy_denial
                .error
                .expect("authorized handler has no browser backend")
                .code,
            -32006,
            "a static-policy denial must happen before and must not consume the lease"
        );
    }
}
