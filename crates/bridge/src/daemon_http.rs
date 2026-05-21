//! v20 — HTTP daemon for cross-machine forum + presence over Tailscale.
//!
//! Serves read-only endpoints in Stage 1:
//!   - `GET /healthz`
//!   - `GET /.well-known/agent.json/<session_id>` — A2A AgentCard
//!   - `GET /forum/threads?board=...&status=...&limit=...`
//!   - `GET /forum/posts?thread_id=...&board=...&since_post_id=...&limit=...&compact=...`
//!   - `GET /presence?project=...&role=...&max_idle_secs=...&limit=...`
//!   - `GET /avatar-surface?project=...&role=...&include_stale=...&limit=...`
//!     — read-only Agent Avatar Protocol JSON projection
//!   - `GET /avatar-surface/report?...` — same projection as text/plain
//!   - `GET /avatar-surface/panel?...` — minimal read-only HTML status panel
//!   - `GET /avatar-surface/heartbeat-health?...` — launchd + presence health
//!   - `GET /avatar-surface/cortex-status?...` — launchd + cortex snapshot status
//!   - `GET /avatar-surface/cortex-language?...` — dynamic language preview
//!   - `GET /avatar-surface/cortex-motion?...` — gesture/mood/attention preview
//!   - `GET /avatar-surface/cortex-renderer?...` — renderer slot mapping dry-run
//!   - `GET /avatar-surface/cortex-renderer-registry?...` — renderer binding registry
//!   - `GET /avatar-surface/cortex-binding-plan?...` — first safe binding plan
//!   - `GET /avatar-surface/cortex-binding-fixture?...` — sidecar preview fixtures
//!   - `GET /avatar-surface/cortex-visual-adapter?...` — sidecar frame preview
//!   - `GET /avatar-surface/cortex-renderer-view?...` — browser sidecar renderer view
//!   - `GET /avatar-surface/cortex-review-gate?...` — read-only renderer review gate
//!   - `GET /avatar-surface/cortex-review-packet?...` — read-only renderer review packets
//!   - `GET /avatar-surface/cortex-preview?...` — voice preview without emission
//!   - `GET /avatar-surface/cortex-voice-gate?...` — dry-run explicit voice gate
//!   - `GET /identity?days=N` — δ-1 cross-node identity fingerprint
//!                              (same shape as `dream identity --json`)
//!   - `POST /embed` — text → 384-d embedding for non-Rust / non-MCP clients
//!                    (game runtimes, web, scripting). Phase 2.1 encoder
//!                    decoupled per thread 6 #226 / #228 / #231 split with
//!                    `embed_text` MCP tool. Returns the raw inner backend's
//!                    output without substrate side-effects.
//!   - `POST /agent/messages` — XM v0.1: write a message addressed to
//!                              a specific session on this node's inbox.
//!                              See `docs/DESIGN-cross-machine-agent-messaging-2026-05-17.md`.
//!   - `GET  /agent/inbox`    — XM v0.1: read this node's inbox for a
//!                              given `to_session`. Both endpoints are
//!                              tailnet-trusted; see R-XM-A/B in §3.
//!
//! Bind to a tailnet-reachable address (`0.0.0.0:7878` by default). The
//! tailscale ACL handles peer auth — this daemon trusts whoever can reach
//! the socket. See `docs/RFC-v20-tailscale-daemon.md` for design rationale.
//!
//! State sharing: takes the same `Arc<dyn StateStore>` the MCP server uses,
//! so daemon-http and stdio MCP can run side-by-side reading/writing the
//! same SQLite WAL.

use ab_store::embedding::{EmbeddingBackend, HashBackend, OnnxBackend};
use ab_store::{AgentPresenceRecord, StateStore};
use anyhow::{Context, Result};
use axum::{
    extract::{Path, Query, State},
    http::{header, StatusCode},
    response::{Html, IntoResponse},
    routing::{get, post},
    Json, Router,
};
use serde::Deserialize;
use serde_json::{json, Value};
use std::sync::Arc;

#[derive(Clone)]
struct AppState {
    store: Arc<dyn StateStore>,
    embed_backend: Arc<dyn EmbeddingBackend>,
}

/// Parse the `listen` argument into one or more addresses. Comma-separated
/// values are split (whitespace around each entry is trimmed). Empty entries
/// are skipped. Used by `run()` to support binding both a tailnet interface
/// and `127.0.0.1` from a single config value without forcing `0.0.0.0` (which
/// would also expose the daemon on any other interface present on the host).
pub fn parse_listen_addrs(listen: &str) -> Vec<String> {
    listen
        .split(',')
        .map(str::trim)
        .filter(|s| !s.is_empty())
        .map(str::to_string)
        .collect()
}

/// Run the HTTP daemon on one or more `listen` addresses. Pass a single
/// address (e.g. `0.0.0.0:7878`) for the legacy single-listener mode, or a
/// comma-separated list (e.g. `127.0.0.1:7878,100.91.146.24:7878`) to bind
/// loopback alongside a specific tailnet interface — strictly narrower than
/// `0.0.0.0` because public interfaces (WiFi, ethernet) are not bound.
/// Blocks until all listeners exit or the runtime is cancelled.
pub async fn run(store: Arc<dyn StateStore>, listen: &str) -> Result<()> {
    let addrs = parse_listen_addrs(listen);
    if addrs.is_empty() {
        anyhow::bail!("daemon-http listen address is empty: {listen:?}");
    }

    let embed_backend = build_raw_embed_backend();
    let state = AppState {
        store,
        embed_backend,
    };
    let app = Router::new()
        .route("/healthz", get(healthz))
        .route("/.well-known/agent.json/:session_id", get(agent_card))
        .route("/forum/threads", get(forum_threads))
        .route("/forum/posts", get(forum_posts))
        .route("/forum/post", post(forum_post))
        .route("/presence", get(presence_list))
        .route("/avatar-surface", get(avatar_surface_snapshot))
        .route("/avatar-surface/report", get(avatar_surface_report))
        .route("/avatar-surface/panel", get(avatar_surface_panel))
        .route(
            "/avatar-surface/heartbeat-health",
            get(avatar_heartbeat_health),
        )
        .route("/avatar-surface/cortex-status", get(avatar_cortex_status))
        .route(
            "/avatar-surface/cortex-language",
            get(avatar_cortex_language),
        )
        .route("/avatar-surface/cortex-motion", get(avatar_cortex_motion))
        .route(
            "/avatar-surface/cortex-renderer",
            get(avatar_cortex_renderer),
        )
        .route(
            "/avatar-surface/cortex-renderer-registry",
            get(avatar_cortex_renderer_registry),
        )
        .route(
            "/avatar-surface/cortex-binding-plan",
            get(avatar_cortex_binding_plan),
        )
        .route(
            "/avatar-surface/cortex-binding-fixture",
            get(avatar_cortex_binding_fixture),
        )
        .route(
            "/avatar-surface/cortex-visual-adapter",
            get(avatar_cortex_visual_adapter),
        )
        .route(
            "/avatar-surface/cortex-renderer-view",
            get(avatar_cortex_renderer_view),
        )
        .route(
            "/avatar-surface/cortex-review-gate",
            get(avatar_cortex_review_gate),
        )
        .route(
            "/avatar-surface/cortex-review-packet",
            get(avatar_cortex_review_packet),
        )
        .route("/avatar-surface/cortex-preview", get(avatar_cortex_preview))
        .route(
            "/avatar-surface/cortex-voice-gate",
            get(avatar_cortex_voice_gate),
        )
        .route("/identity", get(identity_endpoint))
        .route("/embed", post(embed_endpoint))
        .route("/agent/messages", post(agent_message_write))
        .route("/agent/inbox", get(agent_inbox_read))
        .with_state(state);

    // Bind all listeners up-front so any bind failure fails the whole
    // daemon (rather than serving on a subset of addresses silently).
    let mut listeners = Vec::with_capacity(addrs.len());
    for addr in &addrs {
        let listener = tokio::net::TcpListener::bind(addr)
            .await
            .with_context(|| format!("bind {addr}"))?;
        let bound = listener
            .local_addr()
            .map(|a| a.to_string())
            .unwrap_or_else(|_| addr.clone());
        tracing::info!(addr = %bound, "agent-bridge daemon-http listening");
        listeners.push(listener);
    }

    // Spawn one axum::serve task per listener; first one to error wins.
    // The shared Router (`app`) is cheaply cloneable (state is Arc-based).
    let mut joins = Vec::with_capacity(listeners.len());
    for listener in listeners {
        let app = app.clone();
        joins.push(tokio::spawn(async move {
            axum::serve(listener, app).await.context("axum::serve")
        }));
    }
    // Wait for any listener task to finish; surface its error if any.
    // The remaining tasks are aborted when this future resolves and joins drop.
    let (res, _idx, _rest) = futures::future::select_all(joins).await;
    res.context("daemon-http listener task panicked")??;
    Ok(())
}

// ── Endpoints ────────────────────────────────────────────────────────────

async fn healthz() -> impl IntoResponse {
    (StatusCode::OK, "ok")
}

/// Serve the A2A AgentCard for a single session_id.
///
/// Maps the presence row's public block to AgentCard's expected JSON. Local
/// fields (node, project, role, tag, cwd, pid, started_at, last_heartbeat_at)
/// are omitted from the card — see `docs/DESIGN-v19-presence-identity.md` §3.
///
/// Returns 404 if no such session is registered.
async fn agent_card(
    State(s): State<AppState>,
    Path(session_id): Path<String>,
) -> Result<Json<Value>, (StatusCode, String)> {
    let row = lookup_presence(&s, &session_id).await?;
    Ok(Json(presence_to_agent_card(&row)))
}

/// Map a presence row to an AgentCard JSON object.
fn presence_to_agent_card(row: &AgentPresenceRecord) -> Value {
    let mut card = serde_json::Map::new();
    card.insert("name".into(), Value::String(row.name.clone()));
    if let Some(d) = &row.description {
        card.insert("description".into(), Value::String(d.clone()));
    }
    if let Some(v) = &row.version {
        card.insert("version".into(), Value::String(v.clone()));
    }
    if let Some(u) = &row.url {
        card.insert("url".into(), Value::String(u.clone()));
    }
    if let Some(c) = &row.capabilities {
        card.insert("capabilities".into(), c.clone());
    }
    if let Some(s) = &row.skills {
        card.insert("skills".into(), s.clone());
    }
    Value::Object(card)
}

#[derive(Deserialize, Debug)]
struct ForumThreadsQuery {
    board: String,
    status: Option<String>,
    unread_for: Option<String>,
    #[serde(default = "default_limit")]
    limit: u32,
}

async fn forum_threads(
    State(s): State<AppState>,
    Query(q): Query<ForumThreadsQuery>,
) -> Result<Json<Value>, (StatusCode, String)> {
    let limit = q.limit.clamp(1, 500);
    let rows = s
        .store
        .forum_list_threads(
            &q.board,
            q.unread_for.as_deref(),
            q.status.as_deref(),
            limit,
        )
        .await
        .map_err(internal_error)?;
    Ok(Json(
        json!({ "board": q.board, "count": rows.len(), "threads": rows }),
    ))
}

#[derive(Deserialize, Debug)]
struct ForumPostsQuery {
    thread_id: Option<i64>,
    board: Option<String>,
    since_post_id: Option<i64>,
    unread_for: Option<String>,
    #[serde(default = "default_limit")]
    limit: u32,
    compact: Option<bool>,
    body_max_chars: Option<usize>,
    include_refs: Option<bool>,
}

fn forum_projection_options(
    compact: Option<bool>,
    body_max_chars: Option<usize>,
    include_refs: Option<bool>,
) -> (bool, usize, bool) {
    let compact = compact.unwrap_or(false);
    let body_max_chars = body_max_chars
        .map(|v| v.min(100_000))
        .unwrap_or(if compact { 2_000 } else { 0 });
    let include_refs = include_refs.unwrap_or(!compact);
    (compact, body_max_chars, include_refs)
}

fn forum_posts_payload(
    thread_id: Option<i64>,
    board: Option<&str>,
    posts: &[ab_store::ForumPostRecord],
    compact: bool,
    body_max_chars: usize,
    include_refs: bool,
) -> Value {
    let next_cursor = posts.last().map(|p| p.id);
    let (posts, truncated_posts) =
        crate::mcp_tools::project_forum_posts(posts, body_max_chars, include_refs);
    json!({
        "thread_id": thread_id,
        "board": board,
        "count": posts.len(),
        "next_cursor": next_cursor,
        "posts": posts,
        "projection": {
            "compact": compact,
            "body_max_chars": body_max_chars,
            "include_refs": include_refs,
            "truncated_posts": truncated_posts
        }
    })
}

async fn forum_posts(
    State(s): State<AppState>,
    Query(q): Query<ForumPostsQuery>,
) -> Result<Json<Value>, (StatusCode, String)> {
    if q.thread_id.is_none() && q.board.is_none() {
        return Err((
            StatusCode::BAD_REQUEST,
            "must provide thread_id or board".into(),
        ));
    }
    let limit = q.limit.clamp(1, 500);
    let posts = s
        .store
        .forum_read(
            q.thread_id,
            q.board.as_deref(),
            q.since_post_id,
            q.unread_for.as_deref(),
            limit,
        )
        .await
        .map_err(internal_error)?;
    let (compact, body_max_chars, include_refs) =
        forum_projection_options(q.compact, q.body_max_chars, q.include_refs);
    Ok(Json(forum_posts_payload(
        q.thread_id,
        q.board.as_deref(),
        &posts,
        compact,
        body_max_chars,
        include_refs,
    )))
}

/// Request body for `POST /forum/post`. Mirrors the local MCP tool's args
/// 1:1 so peer_client can serialise the same shape it'd send to a stdio
/// MCP server.
#[derive(Deserialize, Debug)]
struct ForumPostRequest {
    author: String,
    body: String,
    thread_id: Option<i64>,
    board: Option<String>,
    title: Option<String>,
    kind: Option<String>,
    tags: Option<Vec<String>>,
    refs: Option<Value>,
}

async fn forum_post(
    State(s): State<AppState>,
    Json(req): Json<ForumPostRequest>,
) -> Result<Json<Value>, (StatusCode, String)> {
    if req.author.trim().is_empty() {
        return Err((StatusCode::BAD_REQUEST, "missing or empty 'author'".into()));
    }
    if req.body.trim().is_empty() {
        return Err((StatusCode::BAD_REQUEST, "missing or empty 'body'".into()));
    }
    let kind = req.kind.as_deref().unwrap_or("msg");
    let outcome = s
        .store
        .forum_post(
            req.thread_id,
            req.board.as_deref(),
            req.title.as_deref(),
            &req.author,
            kind,
            &req.body,
            req.refs.as_ref(),
            req.tags.as_deref(),
        )
        .await
        .map_err(|e| {
            // SQLITE_BUSY / lock contention surfaces as Backend; map to 503
            // so the caller can retry rather than treating it as permanent.
            let msg = e.to_string();
            let code = if msg.contains("locked") || msg.contains("busy") {
                StatusCode::SERVICE_UNAVAILABLE
            } else {
                StatusCode::INTERNAL_SERVER_ERROR
            };
            (code, msg)
        })?;
    Ok(Json(json!({
        "status": "ok",
        "thread_id": outcome.thread_id,
        "post_id": outcome.post_id,
        "created_thread": outcome.created_thread,
    })))
}

// ── XM v0.1: cross-machine agent messaging ────────────────────────────────
//
// `POST /agent/messages` writes to this node's local agent_messages table.
// `GET  /agent/inbox` reads from it. Both are tailnet-only (R-XM-A/B trust
// model: `from_session` is caller-claimed, not verified — same trust level
// as `POST /forum/post`).

#[derive(Deserialize, Debug)]
struct AgentMessageRequest {
    from_session: String,
    to_session: String,
    payload: Value,
}

async fn agent_message_write(
    State(s): State<AppState>,
    Json(req): Json<AgentMessageRequest>,
) -> Result<Json<Value>, (StatusCode, String)> {
    if req.from_session.trim().is_empty() {
        return Err((StatusCode::BAD_REQUEST, "missing 'from_session'".into()));
    }
    if req.to_session.trim().is_empty() {
        return Err((StatusCode::BAD_REQUEST, "missing 'to_session'".into()));
    }
    let id = s
        .store
        .agent_message_send(&req.from_session, &req.to_session, &req.payload)
        .await
        .map_err(|e| {
            let msg = e.to_string();
            let code = if msg.contains("locked") || msg.contains("busy") {
                StatusCode::SERVICE_UNAVAILABLE
            } else {
                StatusCode::INTERNAL_SERVER_ERROR
            };
            (code, msg)
        })?;
    Ok(Json(json!({ "status": "ok", "id": id })))
}

#[derive(Deserialize, Debug)]
struct AgentInboxQuery {
    to_session: String,
    since_id: Option<i64>,
    #[serde(default)]
    unread_only: bool,
    #[serde(default = "default_limit")]
    limit: u32,
}

async fn agent_inbox_read(
    State(s): State<AppState>,
    Query(q): Query<AgentInboxQuery>,
) -> Result<Json<Value>, (StatusCode, String)> {
    if q.to_session.trim().is_empty() {
        return Err((StatusCode::BAD_REQUEST, "missing 'to_session'".into()));
    }
    let limit = q.limit.clamp(1, 500);
    let rows = s
        .store
        .agent_inbox_fetch(&q.to_session, q.since_id, q.unread_only, limit)
        .await
        .map_err(internal_error)?;
    Ok(Json(json!({ "count": rows.len(), "messages": rows })))
}

#[derive(Deserialize, Debug)]
struct PresenceQuery {
    project: Option<String>,
    role: Option<String>,
    #[serde(default = "default_max_idle")]
    max_idle_secs: i64,
    #[serde(default = "default_limit")]
    limit: u32,
}

async fn presence_list(
    State(s): State<AppState>,
    Query(q): Query<PresenceQuery>,
) -> Result<Json<Value>, (StatusCode, String)> {
    let limit = q.limit.clamp(1, 500);
    let rows = s
        .store
        .agent_presence_list(
            q.project.as_deref(),
            q.role.as_deref(),
            q.max_idle_secs,
            limit,
        )
        .await
        .map_err(internal_error)?;
    Ok(Json(json!({ "count": rows.len(), "agents": rows })))
}

#[derive(Deserialize, Debug)]
struct AvatarSurfaceQuery {
    project: Option<String>,
    role: Option<String>,
    #[serde(default = "default_max_idle")]
    max_idle_secs: i64,
    #[serde(default)]
    include_stale: bool,
    #[serde(default = "default_limit")]
    limit: u32,
    #[serde(default = "default_panel_refresh_secs")]
    refresh_secs: u32,
    #[serde(default = "default_avatar_stale_secs")]
    stale_secs: i64,
    #[serde(default)]
    include_raw_presence: bool,
    #[serde(default)]
    include_compat: bool,
}

#[derive(Deserialize, Debug)]
struct AvatarHeartbeatHealthQuery {
    label: Option<String>,
    project: Option<String>,
    #[serde(default = "default_avatar_stale_secs")]
    stale_secs: i64,
}

#[derive(Deserialize, Debug)]
struct AvatarCortexStatusQuery {
    label: Option<String>,
    heartbeat_label: Option<String>,
    project: Option<String>,
    output: Option<std::path::PathBuf>,
    track: Option<String>,
    track_index: Option<usize>,
}

#[derive(Deserialize, Debug)]
struct AvatarCortexVoiceGateQuery {
    label: Option<String>,
    heartbeat_label: Option<String>,
    project: Option<String>,
    output: Option<std::path::PathBuf>,
    #[serde(default)]
    enabled: bool,
    #[serde(default)]
    force: bool,
    #[serde(default = "default_avatar_voice_gate_cooldown_secs")]
    cooldown_secs: i64,
    reason: Option<String>,
}

impl AvatarHeartbeatHealthQuery {
    fn effective_stale_secs(&self) -> i64 {
        self.stale_secs.clamp(30, 86_400)
    }
}

impl AvatarSurfaceQuery {
    fn effective_max_idle_secs(&self) -> i64 {
        if self.include_stale {
            0
        } else {
            self.max_idle_secs
        }
    }

    fn effective_limit(&self) -> u32 {
        self.limit.clamp(1, 500)
    }

    fn effective_refresh_secs(&self) -> u32 {
        self.refresh_secs.clamp(3, 3600)
    }

    fn effective_stale_secs(&self) -> i64 {
        self.stale_secs.clamp(30, 86_400)
    }

    fn report_context(&self) -> crate::avatar_surface::ReportContext<'_> {
        crate::avatar_surface::ReportContext {
            project: self.project.as_deref(),
            role: self.role.as_deref(),
            max_idle_secs: self.effective_max_idle_secs(),
            source: "daemon-http",
        }
    }
}

async fn avatar_surface_entries(
    s: &AppState,
    q: &AvatarSurfaceQuery,
) -> Result<Vec<Value>, (StatusCode, String)> {
    let rows = s
        .store
        .agent_presence_list(
            q.project.as_deref(),
            q.role.as_deref(),
            q.effective_max_idle_secs(),
            q.effective_limit(),
        )
        .await
        .map_err(internal_error)?;
    Ok(rows
        .iter()
        .map(|row| {
            crate::avatar_surface::entry_from_presence(
                row,
                q.include_raw_presence,
                q.include_compat,
            )
        })
        .collect())
}

async fn avatar_surface_snapshot(
    State(s): State<AppState>,
    Query(q): Query<AvatarSurfaceQuery>,
) -> Result<Json<Value>, (StatusCode, String)> {
    let avatars = avatar_surface_entries(&s, &q).await?;
    Ok(Json(avatar_surface_payload(&q, avatars, unix_now())))
}

async fn avatar_surface_report(
    State(s): State<AppState>,
    Query(q): Query<AvatarSurfaceQuery>,
) -> Result<impl IntoResponse, (StatusCode, String)> {
    let avatars = avatar_surface_entries(&s, &q).await?;
    let report = crate::avatar_surface::report_from_entries(&avatars, &q.report_context());
    Ok((
        [(header::CONTENT_TYPE, "text/plain; charset=utf-8")],
        report,
    ))
}

async fn avatar_surface_panel(
    State(s): State<AppState>,
    Query(q): Query<AvatarSurfaceQuery>,
) -> Result<Html<String>, (StatusCode, String)> {
    let avatars = avatar_surface_entries(&s, &q).await?;
    let report = crate::avatar_surface::report_from_entries(&avatars, &q.report_context());
    let health = crate::avatar_health::heartbeat_health(
        s.store.as_ref(),
        None,
        q.project.as_deref(),
        q.effective_stale_secs(),
    )
    .await
    .unwrap_or_else(|e| {
        json!({
            "surface": "avatar_heartbeat_health",
            "read_only": true,
            "status": "error",
            "healthy": false,
            "summary": e.to_string(),
        })
    });
    let cortex = crate::avatar_cortex::avatar_cortex_status(None, None, q.project.as_deref(), None)
        .unwrap_or_else(|e| {
            json!({
                "surface": "avatar_cortex_status",
                "read_only": true,
                "mutates_global_substrate": false,
                "launchd": {
                    "loaded": false,
                    "error": e.to_string(),
                },
                "snapshot": {
                    "exists": false,
                    "error": e.to_string(),
                },
            })
        });
    let cortex_language =
        crate::avatar_cortex::avatar_cortex_language_preview_from_status(cortex.clone());
    let cortex_motion =
        crate::avatar_cortex::avatar_cortex_motion_preview_from_status(cortex.clone());
    let cortex_renderer =
        crate::avatar_cortex::avatar_cortex_renderer_preview_from_status(cortex.clone());
    let cortex_renderer_registry =
        crate::avatar_cortex::avatar_cortex_renderer_registry_from_status(cortex.clone());
    let cortex_binding_plan =
        crate::avatar_cortex::avatar_cortex_binding_plan_from_status(cortex.clone());
    let cortex_binding_fixture =
        crate::avatar_cortex::avatar_cortex_binding_fixture_from_status(cortex.clone());
    let cortex_visual_adapter =
        crate::avatar_cortex::avatar_cortex_visual_adapter_from_status(cortex.clone());
    let cortex_renderer_view =
        crate::avatar_cortex::avatar_cortex_renderer_view_from_status(cortex.clone());
    let cortex_review_gate =
        crate::avatar_cortex::avatar_cortex_renderer_review_gate_from_status(cortex.clone());
    let cortex_review_packet =
        crate::avatar_cortex::avatar_cortex_renderer_review_packet_from_status(cortex.clone());
    Ok(Html(avatar_surface_panel_html(
        &q,
        &avatars,
        &health,
        &cortex,
        &cortex_language,
        &cortex_motion,
        &cortex_renderer,
        &cortex_renderer_registry,
        &cortex_binding_plan,
        &cortex_binding_fixture,
        &cortex_visual_adapter,
        &cortex_renderer_view,
        &cortex_review_gate,
        &cortex_review_packet,
        &report,
        unix_now(),
    )))
}

async fn avatar_heartbeat_health(
    State(s): State<AppState>,
    Query(q): Query<AvatarHeartbeatHealthQuery>,
) -> Result<Json<Value>, (StatusCode, String)> {
    let payload = crate::avatar_health::heartbeat_health(
        s.store.as_ref(),
        q.label.as_deref(),
        q.project.as_deref(),
        q.effective_stale_secs(),
    )
    .await
    .map_err(internal_error)?;
    Ok(Json(payload))
}

async fn avatar_cortex_status(
    Query(q): Query<AvatarCortexStatusQuery>,
) -> Result<Json<Value>, (StatusCode, String)> {
    let payload = crate::avatar_cortex::avatar_cortex_status(
        q.label.as_deref(),
        q.heartbeat_label.as_deref(),
        q.project.as_deref(),
        q.output.as_deref(),
    )
    .map_err(internal_error)?;
    Ok(Json(payload))
}

async fn avatar_cortex_language(
    Query(q): Query<AvatarCortexStatusQuery>,
) -> Result<Json<Value>, (StatusCode, String)> {
    let payload = crate::avatar_cortex::avatar_cortex_language_preview(
        q.label.as_deref(),
        q.heartbeat_label.as_deref(),
        q.project.as_deref(),
        q.output.as_deref(),
    )
    .map_err(internal_error)?;
    Ok(Json(payload))
}

async fn avatar_cortex_motion(
    Query(q): Query<AvatarCortexStatusQuery>,
) -> Result<Json<Value>, (StatusCode, String)> {
    let payload = crate::avatar_cortex::avatar_cortex_motion_preview(
        q.label.as_deref(),
        q.heartbeat_label.as_deref(),
        q.project.as_deref(),
        q.output.as_deref(),
    )
    .map_err(internal_error)?;
    Ok(Json(payload))
}

async fn avatar_cortex_renderer(
    Query(q): Query<AvatarCortexStatusQuery>,
) -> Result<Json<Value>, (StatusCode, String)> {
    let payload = crate::avatar_cortex::avatar_cortex_renderer_preview(
        q.label.as_deref(),
        q.heartbeat_label.as_deref(),
        q.project.as_deref(),
        q.output.as_deref(),
    )
    .map_err(internal_error)?;
    Ok(Json(payload))
}

async fn avatar_cortex_renderer_registry(
    Query(q): Query<AvatarCortexStatusQuery>,
) -> Result<Json<Value>, (StatusCode, String)> {
    let payload = crate::avatar_cortex::avatar_cortex_renderer_registry(
        q.label.as_deref(),
        q.heartbeat_label.as_deref(),
        q.project.as_deref(),
        q.output.as_deref(),
    )
    .map_err(internal_error)?;
    Ok(Json(payload))
}

async fn avatar_cortex_binding_plan(
    Query(q): Query<AvatarCortexStatusQuery>,
) -> Result<Json<Value>, (StatusCode, String)> {
    let payload = crate::avatar_cortex::avatar_cortex_binding_plan(
        q.label.as_deref(),
        q.heartbeat_label.as_deref(),
        q.project.as_deref(),
        q.output.as_deref(),
    )
    .map_err(internal_error)?;
    Ok(Json(payload))
}

async fn avatar_cortex_binding_fixture(
    Query(q): Query<AvatarCortexStatusQuery>,
) -> Result<Json<Value>, (StatusCode, String)> {
    let payload = crate::avatar_cortex::avatar_cortex_binding_fixture(
        q.label.as_deref(),
        q.heartbeat_label.as_deref(),
        q.project.as_deref(),
        q.output.as_deref(),
    )
    .map_err(internal_error)?;
    Ok(Json(payload))
}

async fn avatar_cortex_visual_adapter(
    Query(q): Query<AvatarCortexStatusQuery>,
) -> Result<Json<Value>, (StatusCode, String)> {
    let payload = crate::avatar_cortex::avatar_cortex_visual_adapter(
        q.label.as_deref(),
        q.heartbeat_label.as_deref(),
        q.project.as_deref(),
        q.output.as_deref(),
    )
    .map_err(internal_error)?;
    Ok(Json(payload))
}

async fn avatar_cortex_renderer_view(
    Query(q): Query<AvatarCortexStatusQuery>,
) -> Result<Html<String>, (StatusCode, String)> {
    let payload = crate::avatar_cortex::avatar_cortex_renderer_view(
        q.label.as_deref(),
        q.heartbeat_label.as_deref(),
        q.project.as_deref(),
        q.output.as_deref(),
    )
    .map_err(internal_error)?;
    Ok(Html(avatar_surface_renderer_view_html(
        &payload,
        unix_now(),
        q.track.as_deref(),
        q.track_index,
    )))
}

async fn avatar_cortex_review_gate(
    Query(q): Query<AvatarCortexStatusQuery>,
) -> Result<Json<Value>, (StatusCode, String)> {
    let payload = crate::avatar_cortex::avatar_cortex_renderer_review_gate(
        q.label.as_deref(),
        q.heartbeat_label.as_deref(),
        q.project.as_deref(),
        q.output.as_deref(),
    )
    .map_err(internal_error)?;
    Ok(Json(payload))
}

async fn avatar_cortex_review_packet(
    Query(q): Query<AvatarCortexStatusQuery>,
) -> Result<Json<Value>, (StatusCode, String)> {
    let payload = crate::avatar_cortex::avatar_cortex_renderer_review_packet(
        q.label.as_deref(),
        q.heartbeat_label.as_deref(),
        q.project.as_deref(),
        q.output.as_deref(),
    )
    .map_err(internal_error)?;
    Ok(Json(payload))
}

async fn avatar_cortex_preview(
    Query(q): Query<AvatarCortexStatusQuery>,
) -> Result<Json<Value>, (StatusCode, String)> {
    let payload = crate::avatar_cortex::avatar_cortex_voice_preview(
        q.label.as_deref(),
        q.heartbeat_label.as_deref(),
        q.project.as_deref(),
        q.output.as_deref(),
    )
    .map_err(internal_error)?;
    Ok(Json(payload))
}

async fn avatar_cortex_voice_gate(
    Query(q): Query<AvatarCortexVoiceGateQuery>,
) -> Result<Json<Value>, (StatusCode, String)> {
    let opts = crate::avatar_cortex::AvatarCortexVoiceGateOptions {
        label: q.label.as_deref(),
        heartbeat_label: q.heartbeat_label.as_deref(),
        project: q.project.as_deref(),
        output: q.output.as_deref(),
        enabled: q.enabled,
        force: q.force,
        cooldown_secs: q.cooldown_secs,
        reason: q.reason.as_deref(),
    };
    let payload =
        crate::avatar_cortex::avatar_cortex_voice_gate_dry_run(&opts).map_err(internal_error)?;
    Ok(Json(payload))
}

/// δ-1 (2026-05-11) — Expose this node's behavioural identity fingerprint
/// over HTTP so peers can compare "you on aio2 vs you on Mac". Same JSON
/// shape `dream identity --json` prints, plus a `node` field for
/// disambiguation when several daemons' outputs are stitched together by
/// a hook.
#[derive(Deserialize, Debug)]
struct IdentityQuery {
    #[serde(default = "default_identity_days")]
    days: u32,
}

async fn identity_endpoint(
    State(s): State<AppState>,
    Query(q): Query<IdentityQuery>,
) -> Result<Json<Value>, (StatusCode, String)> {
    use std::time::{SystemTime, UNIX_EPOCH};
    let days = q.days.clamp(1, 90);
    let now = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map(|d| d.as_secs() as i64)
        .unwrap_or(0);
    let window_secs = days as i64 * 86400;
    let cur_start = now - window_secs;
    let prior_start = cur_start - window_secs;
    let cur = s
        .store
        .identity_window(cur_start, now)
        .await
        .map_err(internal_error)?;
    let prior = s
        .store
        .identity_window(prior_start, cur_start)
        .await
        .map_err(internal_error)?;
    Ok(Json(json!({
        "node": node_short(),
        "days": days,
        "current": cur,
        "prior": prior,
    })))
}

fn default_identity_days() -> u32 {
    3
}

/// Request body for `POST /embed`. Single text → single 384-d vector. For
/// throughput callers we may later add a `batch` variant; v0 keeps the shape
/// minimal so non-Rust clients (Unity/C#, Unreal/C++, Godot/GDScript, web/JS)
/// can hit it with one POST per perception event.
#[derive(Deserialize, Debug)]
struct EmbedRequest {
    text: String,
}

async fn embed_endpoint(
    State(s): State<AppState>,
    Json(req): Json<EmbedRequest>,
) -> Result<Json<Value>, (StatusCode, String)> {
    if req.text.is_empty() {
        return Err((StatusCode::BAD_REQUEST, "missing or empty 'text'".into()));
    }
    let backend = s.embed_backend.clone();
    let text = req.text;
    let (name, dim, vec) = tokio::task::spawn_blocking(move || {
        let v = backend.embed(&text);
        (backend.name().to_string(), backend.dim(), v)
    })
    .await
    .map_err(internal_error)?;
    Ok(Json(json!({
        "embedding": vec,
        "backend": name,
        "dim": dim,
    })))
}

/// Select the raw inner embedding backend for `/embed`. Mirrors the env
/// precedence used by `ab_store::embedding::select_default` and
/// `seed_bridge::build_inner_backend`, but always returns the raw inner
/// backend — never a substrate-wrapped one — so external callers can pull
/// embeddings without feeding aio2's perception substrate.
fn build_raw_embed_backend() -> Arc<dyn EmbeddingBackend> {
    let pick = std::env::var("AGENT_BRIDGE_EMBED_BACKEND")
        .ok()
        .map(|s| s.to_lowercase())
        .filter(|s| s == "hash" || s == "onnx")
        .unwrap_or_else(|| "onnx".to_string());
    match pick.as_str() {
        "hash" => Arc::new(HashBackend),
        _ => Arc::new(OnnxBackend),
    }
}

/// Short hostname for cross-node disambiguation. Mirrors the resolution
/// rule used by `agent_presence_announce` (env override → /etc/hostname →
/// `hostname` command → "unknown"), so a single node identifies itself the
/// same way everywhere.
fn node_short() -> String {
    if let Ok(v) = std::env::var("AGENT_BRIDGE_NODE") {
        let v = v.trim().to_string();
        if !v.is_empty() {
            return v;
        }
    }
    if let Ok(s) = std::fs::read_to_string("/etc/hostname") {
        let s = s.trim().to_string();
        if !s.is_empty() {
            return s;
        }
    }
    if let Ok(o) = std::process::Command::new("hostname").output() {
        if let Ok(s) = String::from_utf8(o.stdout) {
            let s = s.trim().to_string();
            if !s.is_empty() {
                return s;
            }
        }
    }
    "unknown".into()
}

// ── Helpers ──────────────────────────────────────────────────────────────

async fn lookup_presence(
    s: &AppState,
    session_id: &str,
) -> Result<AgentPresenceRecord, (StatusCode, String)> {
    // No dedicated `agent_presence_get(session_id)` method on StateStore
    // (Stage 1 keeps the trait surface minimal). Filter from the list with
    // `max_idle_secs=0` (no TTL) so even stale rows are visible — clients
    // can interpret `last_heartbeat_at` themselves.
    let rows = s
        .store
        .agent_presence_list(None, None, 0, 500)
        .await
        .map_err(internal_error)?;
    rows.into_iter()
        .find(|r| r.session_id == session_id)
        .ok_or_else(|| {
            (
                StatusCode::NOT_FOUND,
                format!("session {session_id} not found"),
            )
        })
}

fn internal_error<E: std::fmt::Display>(e: E) -> (StatusCode, String) {
    (StatusCode::INTERNAL_SERVER_ERROR, e.to_string())
}

fn unix_now() -> i64 {
    std::time::SystemTime::now()
        .duration_since(std::time::UNIX_EPOCH)
        .map(|d| d.as_secs() as i64)
        .unwrap_or(0)
}

fn html_escape(input: &str) -> String {
    let mut out = String::with_capacity(input.len());
    for ch in input.chars() {
        match ch {
            '&' => out.push_str("&amp;"),
            '<' => out.push_str("&lt;"),
            '>' => out.push_str("&gt;"),
            '"' => out.push_str("&quot;"),
            '\'' => out.push_str("&#39;"),
            _ => out.push(ch),
        }
    }
    out
}

fn html_json_script(value: &Value) -> String {
    serde_json::to_string(value)
        .unwrap_or_else(|_| "{}".to_string())
        .replace("</", "<\\/")
}

fn url_query_component(input: &str) -> String {
    let mut out = String::with_capacity(input.len());
    for byte in input.bytes() {
        match byte {
            b'A'..=b'Z' | b'a'..=b'z' | b'0'..=b'9' | b'-' | b'_' | b'.' | b'~' => {
                out.push(byte as char)
            }
            _ => out.push_str(&format!("%{byte:02X}")),
        }
    }
    out
}

fn avatar_surface_route_href(
    route_raw: &str,
    project: Option<&str>,
    track: Option<&str>,
) -> String {
    let mut href = route_raw.to_string();
    let mut sep = if route_raw.contains('?') { "&" } else { "?" };
    if let Some(project) = project.filter(|value| !value.is_empty()) {
        href.push_str(sep);
        href.push_str("project=");
        href.push_str(&url_query_component(project));
        sep = "&";
    }
    if let Some(track) = track.filter(|value| !value.is_empty()) {
        href.push_str(sep);
        href.push_str("track=");
        href.push_str(&url_query_component(track));
    }
    href
}

fn avatar_surface_renderer_token_label(token: &str) -> String {
    let parts = token.split("::").collect::<Vec<_>>();
    if parts.len() >= 2 {
        format!("{}::{}", parts[parts.len() - 2], parts[parts.len() - 1])
    } else {
        token.to_string()
    }
}

fn avatar_surface_html_value(entry: &Value, key: &str, fallback: &str) -> String {
    avatar_surface_html_json_value(entry.get(key), fallback)
}

fn avatar_surface_html_json_value(value: Option<&Value>, fallback: &str) -> String {
    match value {
        Some(Value::String(s)) if !s.is_empty() => html_escape(s),
        Some(Value::Number(n)) => html_escape(&n.to_string()),
        Some(Value::Bool(b)) => html_escape(&b.to_string()),
        _ => html_escape(fallback),
    }
}

fn avatar_surface_raw_i64(entry: &Value, key: &str) -> Option<i64> {
    match entry.get(key) {
        Some(Value::Number(n)) => n.as_i64().or_else(|| n.as_u64().map(|v| v as i64)),
        Some(Value::String(s)) => s.parse::<i64>().ok(),
        _ => None,
    }
}

fn avatar_surface_age_label(age_secs: i64) -> String {
    if age_secs < 0 {
        return "future".to_string();
    }
    if age_secs < 60 {
        return format!("{age_secs}s ago");
    }
    if age_secs < 3_600 {
        return format!("{}m {}s ago", age_secs / 60, age_secs % 60);
    }
    if age_secs < 86_400 {
        return format!("{}h {}m ago", age_secs / 3_600, (age_secs % 3_600) / 60);
    }
    format!(
        "{}d {}h ago",
        age_secs / 86_400,
        (age_secs % 86_400) / 3_600
    )
}

fn avatar_surface_status(
    entry: &Value,
    generated_at: i64,
    stale_secs: i64,
) -> (&'static str, &'static str, String) {
    match avatar_surface_raw_i64(entry, "last_heartbeat_at") {
        Some(heartbeat) => {
            let age = generated_at.saturating_sub(heartbeat);
            if age > stale_secs {
                ("status-stale", "stale", avatar_surface_age_label(age))
            } else {
                ("status-fresh", "fresh", avatar_surface_age_label(age))
            }
        }
        None => ("status-unknown", "unknown", "no heartbeat".to_string()),
    }
}

fn avatar_surface_health_class(status: &str) -> &'static str {
    match status {
        "healthy" => "status-fresh",
        "stale" | "failing" | "binary_missing" | "binary_missing_command" | "error" => {
            "status-stale"
        }
        _ => "status-unknown",
    }
}

fn avatar_surface_health_html(health: &Value) -> String {
    let status = health
        .get("status")
        .and_then(Value::as_str)
        .unwrap_or("unknown");
    let status_class = avatar_surface_health_class(status);
    let summary = avatar_surface_html_json_value(health.get("summary"), "-");
    let binary = health.get("binary").unwrap_or(&Value::Null);
    let launchd = health.get("launchd").unwrap_or(&Value::Null);
    let presence = health.get("presence").unwrap_or(&Value::Null);
    let age = match presence.get("age_secs").and_then(Value::as_i64) {
        Some(age) => html_escape(&avatar_surface_age_label(age)),
        None => html_escape("-"),
    };
    let binary_path = avatar_surface_html_json_value(binary.get("path"), "-");
    let sync = avatar_surface_html_json_value(binary.get("supports_sync_presence"), "false");
    let health_cmd =
        avatar_surface_html_json_value(binary.get("supports_heartbeat_health"), "false");
    let exit_code = avatar_surface_html_json_value(launchd.get("last_exit_code"), "-");
    let runs = avatar_surface_html_json_value(launchd.get("runs"), "-");

    format!(
        r#"<section class="health {status_class}">
      <div class="health-title">
        <span class="pill {status_class}">{status}</span>
        <strong>Heartbeat Health</strong>
        <span>{summary}</span>
      </div>
      <dl>
        <div><dt>binary</dt><dd>{binary_path}</dd></div>
        <div><dt>commands</dt><dd>sync={sync} health={health_cmd}</dd></div>
        <div><dt>launchd</dt><dd>exit={exit_code} runs={runs}</dd></div>
        <div><dt>presence</dt><dd>{age}</dd></div>
      </dl>
    </section>"#,
        status = html_escape(status),
        status_class = status_class,
        summary = summary,
        binary_path = binary_path,
        sync = sync,
        health_cmd = health_cmd,
        exit_code = exit_code,
        runs = runs,
        age = age
    )
}

fn avatar_surface_cortex_class(cortex: &Value) -> &'static str {
    let launchd = cortex.get("launchd").unwrap_or(&Value::Null);
    let snapshot = cortex.get("snapshot").unwrap_or(&Value::Null);
    let loaded = launchd
        .get("loaded")
        .and_then(Value::as_bool)
        .unwrap_or(false);
    let exit_ok = launchd
        .get("last_exit_code")
        .and_then(Value::as_i64)
        .map(|code| code == 0)
        .unwrap_or(false);
    let rows_ok = snapshot
        .get("total_rows")
        .and_then(Value::as_u64)
        .map(|rows| rows > 0)
        .unwrap_or(false);
    if loaded && exit_ok && rows_ok {
        "status-fresh"
    } else if loaded || rows_ok {
        "status-stale"
    } else {
        "status-unknown"
    }
}

fn avatar_surface_cortex_html(cortex: &Value) -> String {
    let launchd = cortex.get("launchd").unwrap_or(&Value::Null);
    let snapshot = cortex.get("snapshot").unwrap_or(&Value::Null);
    let events = cortex.get("events").unwrap_or(&Value::Null);
    let trend = cortex.get("trend").unwrap_or(&Value::Null);
    let learning = trend.get("learning_state").unwrap_or(&Value::Null);
    let policy = trend.get("behavior_policy").unwrap_or(&Value::Null);
    let voice = policy.get("voice").unwrap_or(&Value::Null);
    let latest = snapshot.get("latest_long").unwrap_or(&Value::Null);
    let latest_event = events.get("latest").unwrap_or(&Value::Null);
    let status_class = avatar_surface_cortex_class(cortex);
    let status = match status_class {
        "status-fresh" => "active",
        "status-stale" => "attention",
        _ => "unknown",
    };
    let label = avatar_surface_html_json_value(cortex.get("label"), "-");
    let loaded = avatar_surface_html_json_value(launchd.get("loaded"), "false");
    let runs = avatar_surface_html_json_value(launchd.get("runs"), "-");
    let exit_code = avatar_surface_html_json_value(launchd.get("last_exit_code"), "-");
    let interval = avatar_surface_html_json_value(launchd.get("run_interval_secs"), "-");
    let rows = avatar_surface_html_json_value(snapshot.get("total_rows"), "0");
    let step = avatar_surface_html_json_value(latest.get("step"), "-");
    let fingerprint = avatar_surface_html_json_value(latest.get("fingerprint"), "-");
    let event_records = avatar_surface_html_json_value(events.get("records_count"), "0");
    let latest_status = avatar_surface_html_json_value(latest_event.get("status"), "-");
    let latest_reason = avatar_surface_html_json_value(latest_event.get("reason"), "-");
    let unhealthy_count = avatar_surface_html_json_value(events.get("unhealthy_count"), "0");
    let delta = avatar_surface_html_json_value(trend.get("step_records_delta"), "-");
    let lag = avatar_surface_html_json_value(trend.get("snapshot_event_lag_secs"), "-");
    let learning_state = avatar_surface_html_json_value(learning.get("state"), "-");
    let learning_reason = avatar_surface_html_json_value(learning.get("reason"), "-");
    let policy_badge = avatar_surface_html_json_value(policy.get("badge"), "-");
    let policy_action = avatar_surface_html_json_value(policy.get("recommended_action"), "-");
    let voice_allowed = avatar_surface_html_json_value(voice.get("allowed"), "false");
    let path = avatar_surface_html_json_value(snapshot.get("path"), "-");

    format!(
        r#"<section class="health {status_class}">
      <div class="health-title">
        <span class="pill {status_class}">{status}</span>
        <strong>Cortex Status</strong>
        <span>{label}</span>
      </div>
      <dl>
        <div><dt>launchd</dt><dd>loaded={loaded} exit={exit_code} runs={runs}</dd></div>
        <div><dt>interval</dt><dd>{interval}s</dd></div>
        <div><dt>snapshot</dt><dd>rows={rows} step={step}</dd></div>
        <div><dt>events</dt><dd>records={event_records} latest={latest_status} reason={latest_reason}</dd></div>
        <div><dt>learning</dt><dd>state={learning_state} reason={learning_reason}</dd></div>
        <div><dt>policy</dt><dd>badge={policy_badge} action={policy_action} voice={voice_allowed}</dd></div>
        <div><dt>trend</dt><dd>delta={delta} lag={lag}s unhealthy={unhealthy_count}</dd></div>
        <div><dt>fingerprint</dt><dd>{fingerprint}</dd></div>
        <div><dt>path</dt><dd>{path}</dd></div>
      </dl>
    </section>"#,
        status_class = status_class,
        status = html_escape(status),
        label = label,
        loaded = loaded,
        exit_code = exit_code,
        runs = runs,
        interval = interval,
        rows = rows,
        step = step,
        fingerprint = fingerprint,
        event_records = event_records,
        latest_status = latest_status,
        latest_reason = latest_reason,
        unhealthy_count = unhealthy_count,
        delta = delta,
        lag = lag,
        learning_state = learning_state,
        learning_reason = learning_reason,
        policy_badge = policy_badge,
        policy_action = policy_action,
        voice_allowed = voice_allowed,
        path = path,
    )
}

fn avatar_surface_language_html(language_preview: &Value) -> String {
    let language = language_preview.get("language").unwrap_or(&Value::Null);
    let safety = language.get("safety").unwrap_or(&Value::Null);
    let generator = language.get("generator").unwrap_or(&Value::Null);
    let memory = language.get("memory").unwrap_or(&Value::Null);
    let slots = language.get("slots").unwrap_or(&Value::Null);
    let utterance = avatar_surface_html_json_value(language.get("utterance"), "-");
    let intent = avatar_surface_html_json_value(language.get("intent"), "-");
    let style = avatar_surface_html_json_value(language.get("style"), "-");
    let state = avatar_surface_html_json_value(slots.get("state"), "-");
    let latest_status = avatar_surface_html_json_value(slots.get("latest_status"), "-");
    let memory_summary = avatar_surface_html_json_value(memory.get("summary"), "-");
    let memory_window = avatar_surface_html_json_value(memory.get("window_size"), "0");
    let memory_transitions = avatar_surface_html_json_value(memory.get("transition_count"), "0");
    let voice_allowed = avatar_surface_html_json_value(safety.get("voice_allowed"), "false");
    let uses_llm = avatar_surface_html_json_value(generator.get("uses_llm"), "false");
    let uses_voice_model =
        avatar_surface_html_json_value(generator.get("uses_voice_model"), "false");

    format!(
        r#"<section class="health status-fresh">
      <div class="health-title">
        <span class="pill status-fresh">preview</span>
        <strong>Xiao Shu Language</strong>
        <span>{utterance}</span>
      </div>
      <dl>
        <div><dt>intent</dt><dd>{intent}</dd></div>
        <div><dt>style</dt><dd>{style}</dd></div>
        <div><dt>state</dt><dd>{state}</dd></div>
        <div><dt>latest</dt><dd>{latest_status}</dd></div>
        <div><dt>memory</dt><dd>{memory_summary} window={memory_window} transitions={memory_transitions}</dd></div>
        <div><dt>safety</dt><dd>voice={voice_allowed}</dd></div>
        <div><dt>generator</dt><dd>llm={uses_llm} voice_model={uses_voice_model}</dd></div>
      </dl>
    </section>"#,
        utterance = utterance,
        intent = intent,
        style = style,
        state = state,
        latest_status = latest_status,
        memory_summary = memory_summary,
        memory_window = memory_window,
        memory_transitions = memory_transitions,
        voice_allowed = voice_allowed,
        uses_llm = uses_llm,
        uses_voice_model = uses_voice_model,
    )
}

fn avatar_surface_motion_html(motion_preview: &Value) -> String {
    let motion = motion_preview.get("motion").unwrap_or(&Value::Null);
    let hint = motion.get("animation_hint").unwrap_or(&Value::Null);
    let source = motion.get("source").unwrap_or(&Value::Null);
    let safety = motion.get("safety").unwrap_or(&Value::Null);
    let gesture = avatar_surface_html_json_value(motion.get("gesture"), "-");
    let mood = avatar_surface_html_json_value(motion.get("mood"), "-");
    let attention = avatar_surface_html_json_value(motion.get("attention"), "-");
    let reason = avatar_surface_html_json_value(motion.get("reason"), "-");
    let animation = avatar_surface_html_json_value(hint.get("loop"), "-");
    let intensity = avatar_surface_html_json_value(hint.get("intensity"), "-");
    let state = avatar_surface_html_json_value(source.get("state"), "-");
    let memory = avatar_surface_html_json_value(source.get("memory_observation"), "-");
    let sidecar_only = avatar_surface_html_json_value(safety.get("sidecar_only"), "true");
    let renderer_mapping =
        avatar_surface_html_json_value(safety.get("requires_renderer_mapping"), "true");

    format!(
        r#"<section class="health status-fresh">
      <div class="health-title">
        <span class="pill status-fresh">motion</span>
        <strong>Xiao Shu Motion</strong>
        <span>{gesture} / {mood} / {attention}</span>
      </div>
      <dl>
        <div><dt>animation</dt><dd>{animation} intensity={intensity}</dd></div>
        <div><dt>reason</dt><dd>{reason}</dd></div>
        <div><dt>source</dt><dd>state={state} memory={memory}</dd></div>
        <div><dt>safety</dt><dd>sidecar={sidecar_only} renderer_mapping={renderer_mapping}</dd></div>
      </dl>
    </section>"#,
        gesture = gesture,
        mood = mood,
        attention = attention,
        animation = animation,
        intensity = intensity,
        reason = reason,
        state = state,
        memory = memory,
        sidecar_only = sidecar_only,
        renderer_mapping = renderer_mapping,
    )
}

fn avatar_surface_renderer_html(renderer_preview: &Value) -> String {
    let renderer = renderer_preview.get("renderer").unwrap_or(&Value::Null);
    let mapping = renderer.get("mapping").unwrap_or(&Value::Null);
    let evidence = mapping.get("evidence").unwrap_or(&Value::Null);
    let target = mapping.get("target").unwrap_or(&Value::Null);
    let safety = renderer.get("safety").unwrap_or(&Value::Null);
    let token = avatar_surface_html_json_value(mapping.get("input_token"), "-");
    let resolved = avatar_surface_html_json_value(mapping.get("resolved"), "false");
    let pose = avatar_surface_html_json_value(target.get("pose_slot"), "-");
    let expression = avatar_surface_html_json_value(target.get("expression_slot"), "-");
    let motion = avatar_surface_html_json_value(target.get("motion_slot"), "-");
    let accessory = avatar_surface_html_json_value(target.get("accessory_slot"), "-");
    let writes_files = avatar_surface_html_json_value(safety.get("writes_files"), "false");
    let mutates_renderer = avatar_surface_html_json_value(safety.get("mutates_renderer"), "false");
    let pet_mutation =
        avatar_surface_html_json_value(safety.get("codex_pet_package_mutation"), "false");
    let binding_stage = avatar_surface_html_json_value(evidence.get("binding_stage"), "-");
    let risk_level = avatar_surface_html_json_value(evidence.get("risk_level"), "-");
    let visual_intent = avatar_surface_html_json_value(evidence.get("visual_intent"), "-");

    format!(
        r#"<section class="health status-fresh">
      <div class="health-title">
        <span class="pill status-fresh">dry-run</span>
        <strong>Xiao Shu Renderer</strong>
        <span>{token}</span>
      </div>
      <dl>
        <div><dt>resolved</dt><dd>{resolved}</dd></div>
        <div><dt>slots</dt><dd>pose={pose} expression={expression} motion={motion} accessory={accessory}</dd></div>
        <div><dt>evidence</dt><dd>stage={binding_stage} risk={risk_level}</dd></div>
        <div><dt>intent</dt><dd>{visual_intent}</dd></div>
        <div><dt>safety</dt><dd>writes_files={writes_files} mutates_renderer={mutates_renderer} pet_package={pet_mutation}</dd></div>
      </dl>
    </section>"#,
        token = token,
        resolved = resolved,
        pose = pose,
        expression = expression,
        motion = motion,
        accessory = accessory,
        binding_stage = binding_stage,
        risk_level = risk_level,
        visual_intent = visual_intent,
        writes_files = writes_files,
        mutates_renderer = mutates_renderer,
        pet_mutation = pet_mutation,
    )
}

fn avatar_surface_renderer_registry_html(registry_preview: &Value) -> String {
    let registry = registry_preview.get("registry").unwrap_or(&Value::Null);
    let current = registry.get("current").unwrap_or(&Value::Null);
    let stage_counts = registry.get("stage_counts").unwrap_or(&Value::Null);
    let risk_counts = registry.get("risk_counts").unwrap_or(&Value::Null);
    let known = avatar_surface_html_json_value(registry.get("known_token_count"), "0");
    let candidate = avatar_surface_html_json_value(stage_counts.get("candidate"), "0");
    let needs_review = avatar_surface_html_json_value(stage_counts.get("needs_review"), "0");
    let fallback = avatar_surface_html_json_value(stage_counts.get("fallback_only"), "0");
    let risk_low = avatar_surface_html_json_value(risk_counts.get("low"), "0");
    let risk_medium = avatar_surface_html_json_value(risk_counts.get("medium"), "0");
    let risk_high = avatar_surface_html_json_value(risk_counts.get("high"), "0");
    let current_token = avatar_surface_html_json_value(current.get("token"), "-");
    let current_stage = avatar_surface_html_json_value(current.get("binding_stage"), "-");
    let current_risk = avatar_surface_html_json_value(current.get("risk_level"), "-");

    format!(
        r#"<section class="health status-fresh">
      <div class="health-title">
        <span class="pill status-fresh">registry</span>
        <strong>Xiao Shu Renderer Registry</strong>
        <span>known={known} candidate={candidate} review={needs_review} fallback={fallback}</span>
      </div>
      <dl>
        <div><dt>risk</dt><dd>low={risk_low} medium={risk_medium} high={risk_high}</dd></div>
        <div><dt>current</dt><dd>{current_token} stage={current_stage} risk={current_risk}</dd></div>
      </dl>
    </section>"#,
        known = known,
        candidate = candidate,
        needs_review = needs_review,
        fallback = fallback,
        risk_low = risk_low,
        risk_medium = risk_medium,
        risk_high = risk_high,
        current_token = current_token,
        current_stage = current_stage,
        current_risk = current_risk,
    )
}

fn avatar_surface_binding_plan_html(binding_plan_preview: &Value) -> String {
    let plan = binding_plan_preview
        .get("binding_plan")
        .unwrap_or(&Value::Null);
    let first = plan.get("first_candidate").unwrap_or(&Value::Null);
    let current = plan.get("current").unwrap_or(&Value::Null);
    let safety = plan.get("safety").unwrap_or(&Value::Null);
    let selected = avatar_surface_html_json_value(plan.get("selected_count"), "0");
    let deferred = avatar_surface_html_json_value(plan.get("deferred_count"), "0");
    let first_token = avatar_surface_html_json_value(first.get("token"), "-");
    let first_risk = avatar_surface_html_json_value(first.get("risk_level"), "-");
    let current_token = avatar_surface_html_json_value(current.get("token"), "-");
    let current_stage = avatar_surface_html_json_value(current.get("binding_stage"), "-");
    let writes_files = avatar_surface_html_json_value(safety.get("writes_files"), "false");
    let mutates_renderer = avatar_surface_html_json_value(safety.get("mutates_renderer"), "false");
    let pet_mutation =
        avatar_surface_html_json_value(safety.get("codex_pet_package_mutation"), "false");
    let decision = avatar_surface_html_json_value(plan.get("decision"), "-");

    format!(
        r#"<section class="health status-fresh">
      <div class="health-title">
        <span class="pill status-fresh">plan</span>
        <strong>Xiao Shu Binding Plan</strong>
        <span>selected={selected} deferred={deferred}</span>
      </div>
      <dl>
        <div><dt>first</dt><dd>{first_token} risk={first_risk}</dd></div>
        <div><dt>current</dt><dd>{current_token} stage={current_stage}</dd></div>
        <div><dt>safety</dt><dd>writes_files={writes_files} mutates_renderer={mutates_renderer} pet_package={pet_mutation}</dd></div>
        <div><dt>decision</dt><dd>{decision}</dd></div>
      </dl>
    </section>"#,
        selected = selected,
        deferred = deferred,
        first_token = first_token,
        first_risk = first_risk,
        current_token = current_token,
        current_stage = current_stage,
        writes_files = writes_files,
        mutates_renderer = mutates_renderer,
        pet_mutation = pet_mutation,
        decision = decision,
    )
}

fn avatar_surface_binding_fixture_html(binding_fixture_preview: &Value) -> String {
    let fixture = binding_fixture_preview
        .get("fixture")
        .unwrap_or(&Value::Null);
    let first = fixture.get("first_fixture").unwrap_or(&Value::Null);
    let assertions = first.get("golden_assertions").unwrap_or(&Value::Null);
    let acceptance = fixture.get("acceptance").unwrap_or(&Value::Null);
    let count = avatar_surface_html_json_value(fixture.get("fixture_count"), "0");
    let source = avatar_surface_html_json_value(fixture.get("source"), "-");
    let first_token = avatar_surface_html_json_value(first.get("token"), "-");
    let motion = avatar_surface_html_json_value(assertions.get("motion_slot"), "-");
    let duration = avatar_surface_html_json_value(assertions.get("duration_ms"), "0");
    let returns_idle = avatar_surface_html_json_value(assertions.get("returns_to_idle"), "false");
    let all_idle = avatar_surface_html_json_value(acceptance.get("all_return_to_idle"), "false");
    let all_duration =
        avatar_surface_html_json_value(acceptance.get("all_duration_within_2s"), "false");
    let writes_files =
        avatar_surface_html_json_value(acceptance.get("asset_writes_allowed"), "false");
    let mutates_renderer =
        avatar_surface_html_json_value(acceptance.get("renderer_mutation_allowed"), "false");
    let pet_mutation = avatar_surface_html_json_value(
        acceptance.get("codex_pet_package_mutation_allowed"),
        "false",
    );

    format!(
        r#"<section class="health status-fresh">
      <div class="health-title">
        <span class="pill status-fresh">fixture</span>
        <strong>Xiao Shu Binding Fixture</strong>
        <span>fixtures={count} source={source}</span>
      </div>
      <dl>
        <div><dt>first</dt><dd>{first_token} motion={motion}</dd></div>
        <div><dt>timing</dt><dd>duration={duration}ms returns_idle={returns_idle}</dd></div>
        <div><dt>acceptance</dt><dd>all_idle={all_idle} all_under_2s={all_duration}</dd></div>
        <div><dt>safety</dt><dd>writes_files={writes_files} mutates_renderer={mutates_renderer} pet_package={pet_mutation}</dd></div>
      </dl>
    </section>"#,
        count = count,
        source = source,
        first_token = first_token,
        motion = motion,
        duration = duration,
        returns_idle = returns_idle,
        all_idle = all_idle,
        all_duration = all_duration,
        writes_files = writes_files,
        mutates_renderer = mutates_renderer,
        pet_mutation = pet_mutation,
    )
}

fn avatar_surface_visual_adapter_html(visual_adapter_preview: &Value) -> String {
    let adapter = visual_adapter_preview
        .get("visual_adapter")
        .unwrap_or(&Value::Null);
    let first = adapter.get("first_preview").unwrap_or(&Value::Null);
    let final_state = first.get("final_state").unwrap_or(&Value::Null);
    let acceptance = adapter.get("acceptance").unwrap_or(&Value::Null);
    let previews = avatar_surface_html_json_value(adapter.get("preview_count"), "0");
    let input = avatar_surface_html_json_value(adapter.get("input"), "-");
    let first_token = avatar_surface_html_json_value(first.get("token"), "-");
    let frames = avatar_surface_html_json_value(first.get("frame_count"), "0");
    let final_motion = avatar_surface_html_json_value(final_state.get("motion_slot"), "-");
    let final_expression = avatar_surface_html_json_value(final_state.get("expression_slot"), "-");
    let all_idle = avatar_surface_html_json_value(acceptance.get("all_return_to_idle"), "false");
    let all_duration =
        avatar_surface_html_json_value(acceptance.get("all_duration_within_2s"), "false");
    let renders_pixels =
        avatar_surface_html_json_value(visual_adapter_preview.get("renders_pixels"), "false");
    let writes_files =
        avatar_surface_html_json_value(visual_adapter_preview.get("writes_files"), "false");
    let mutates_renderer =
        avatar_surface_html_json_value(visual_adapter_preview.get("mutates_renderer"), "false");
    let pet_mutation = avatar_surface_html_json_value(
        visual_adapter_preview.get("codex_pet_package_mutation"),
        "false",
    );

    format!(
        r#"<section class="health status-fresh">
      <div class="health-title">
        <span class="pill status-fresh">adapter</span>
        <strong>Xiao Shu Visual Adapter</strong>
        <span>previews={previews} input={input}</span>
      </div>
      <dl>
        <div><dt>first</dt><dd>{first_token} frames={frames}</dd></div>
        <div><dt>final</dt><dd>motion={final_motion} expression={final_expression}</dd></div>
        <div><dt>acceptance</dt><dd>all_idle={all_idle} all_under_2s={all_duration}</dd></div>
        <div><dt>safety</dt><dd>pixels={renders_pixels} writes_files={writes_files} mutates_renderer={mutates_renderer} pet_package={pet_mutation}</dd></div>
      </dl>
    </section>"#,
        previews = previews,
        input = input,
        first_token = first_token,
        frames = frames,
        final_motion = final_motion,
        final_expression = final_expression,
        all_idle = all_idle,
        all_duration = all_duration,
        renders_pixels = renders_pixels,
        writes_files = writes_files,
        mutates_renderer = mutates_renderer,
        pet_mutation = pet_mutation,
    )
}

fn avatar_surface_renderer_view_summary_html(
    renderer_view_preview: &Value,
    q: &AvatarSurfaceQuery,
) -> String {
    let view = renderer_view_preview
        .get("renderer_view")
        .unwrap_or(&Value::Null);
    let first = view.get("first_track").unwrap_or(&Value::Null);
    let route_raw = view
        .get("html_route")
        .and_then(Value::as_str)
        .unwrap_or("/avatar-surface/cortex-renderer-view");
    let href_raw = avatar_surface_route_href(route_raw, q.project.as_deref(), None);
    let href = html_escape(&href_raw);
    let tracks = avatar_surface_html_json_value(view.get("track_count"), "0");
    let selected_tracks = avatar_surface_html_json_value(view.get("selected_track_count"), "0");
    let review_tracks = avatar_surface_html_json_value(view.get("review_track_count"), "0");
    let route = html_escape(route_raw);
    let first_token = avatar_surface_html_json_value(first.get("token"), "-");
    let frames = avatar_surface_html_json_value(first.get("frame_count"), "0");
    let browser_pixels = avatar_surface_html_json_value(
        renderer_view_preview.get("browser_renders_pixels"),
        "false",
    );
    let writes_files =
        avatar_surface_html_json_value(renderer_view_preview.get("writes_files"), "false");
    let mutates_renderer =
        avatar_surface_html_json_value(renderer_view_preview.get("mutates_renderer"), "false");
    let pet_mutation = avatar_surface_html_json_value(
        renderer_view_preview.get("codex_pet_package_mutation"),
        "false",
    );

    format!(
        r#"<section class="health status-fresh">
      <div class="health-title">
        <span class="pill status-fresh">view</span>
        <strong>Xiao Shu Renderer View</strong>
        <span>tracks={tracks} selected={selected_tracks} review={review_tracks} route={route}</span>
      </div>
      <dl>
        <div><dt>first</dt><dd>{first_token} frames={frames}</dd></div>
        <div><dt>pixels</dt><dd>browser={browser_pixels}</dd></div>
        <div><dt>safety</dt><dd>writes_files={writes_files} mutates_renderer={mutates_renderer} pet_package={pet_mutation}</dd></div>
        <div><dt>open</dt><dd><a href="{href}">renderer view</a></dd></div>
      </dl>
    </section>"#,
        tracks = tracks,
        selected_tracks = selected_tracks,
        review_tracks = review_tracks,
        route = route,
        first_token = first_token,
        frames = frames,
        browser_pixels = browser_pixels,
        writes_files = writes_files,
        mutates_renderer = mutates_renderer,
        pet_mutation = pet_mutation,
        href = href,
    )
}

fn avatar_surface_quick_actions_html(
    renderer_view_preview: &Value,
    review_gate_preview: &Value,
    q: &AvatarSurfaceQuery,
) -> String {
    let view = renderer_view_preview
        .get("renderer_view")
        .unwrap_or(&Value::Null);
    let gate = review_gate_preview
        .get("review_gate")
        .unwrap_or(&Value::Null);
    let renderer_route = view
        .get("html_route")
        .and_then(Value::as_str)
        .unwrap_or("/avatar-surface/cortex-renderer-view");
    let review_route = gate
        .get("html_route")
        .and_then(Value::as_str)
        .unwrap_or("/avatar-surface/cortex-review-gate");
    let renderer_href_raw = avatar_surface_route_href(renderer_route, q.project.as_deref(), None);
    let review_href_raw = avatar_surface_route_href(review_route, q.project.as_deref(), None);

    let tracks = avatar_surface_html_json_value(view.get("track_count"), "0");
    let selected = avatar_surface_html_json_value(view.get("selected_track_count"), "0");
    let review = avatar_surface_html_json_value(view.get("review_track_count"), "0");
    let browser_pixels = avatar_surface_html_json_value(
        renderer_view_preview.get("browser_renders_pixels"),
        "false",
    );
    let pending = avatar_surface_html_json_value(gate.get("manual_pending_count"), "0");
    let auto_pass = avatar_surface_html_json_value(gate.get("automatic_pass_count"), "0");
    let can_promote = avatar_surface_html_json_value(
        gate.get("acceptance")
            .and_then(|acceptance| acceptance.get("can_promote_review_tracks")),
        "false",
    );

    format!(
        r#"<nav class="quick-actions" aria-label="Avatar quick actions">
      <a href="{renderer_href}" class="quick-action">
        <strong>Renderer View</strong>
        <span>tracks={tracks} selected={selected} review={review} browser={browser_pixels}</span>
      </a>
      <a href="{review_href}" class="quick-action">
        <strong>Review Gate</strong>
        <span>pending={pending} auto_pass={auto_pass} can_promote={can_promote}</span>
      </a>
    </nav>"#,
        renderer_href = html_escape(&renderer_href_raw),
        review_href = html_escape(&review_href_raw),
        tracks = tracks,
        selected = selected,
        review = review,
        browser_pixels = browser_pixels,
        pending = pending,
        auto_pass = auto_pass,
        can_promote = can_promote,
    )
}

fn avatar_surface_review_gate_html(review_gate_preview: &Value, q: &AvatarSurfaceQuery) -> String {
    let gate = review_gate_preview
        .get("review_gate")
        .unwrap_or(&Value::Null);
    let route_raw = gate
        .get("html_route")
        .and_then(Value::as_str)
        .unwrap_or("/avatar-surface/cortex-review-gate");
    let href_raw = avatar_surface_route_href(route_raw, q.project.as_deref(), None);
    let href = html_escape(&href_raw);
    let renderer_route_raw = gate
        .get("renderer_view_route")
        .and_then(Value::as_str)
        .unwrap_or("/avatar-surface/cortex-renderer-view");
    let tracks = avatar_surface_html_json_value(gate.get("track_count"), "0");
    let selected = avatar_surface_html_json_value(gate.get("selected_baseline_count"), "0");
    let pending = avatar_surface_html_json_value(gate.get("manual_pending_count"), "0");
    let auto_pass = avatar_surface_html_json_value(gate.get("automatic_pass_count"), "0");
    let auto_blocked = avatar_surface_html_json_value(gate.get("automatic_blocked_count"), "0");
    let manual_required = avatar_surface_html_json_value(
        gate.get("acceptance")
            .and_then(|acceptance| acceptance.get("manual_review_required")),
        "false",
    );
    let can_promote = avatar_surface_html_json_value(
        gate.get("acceptance")
            .and_then(|acceptance| acceptance.get("can_promote_review_tracks")),
        "false",
    );
    let mut first_pending = "-".to_string();
    let mut pending_links = String::new();
    if let Some(items) = gate.get("items").and_then(Value::as_array) {
        if let Some(item) = items
            .iter()
            .find(|item| item.get("manual_decision").and_then(Value::as_str) == Some("pending"))
        {
            first_pending = format!(
                "{} gate={}",
                avatar_surface_html_json_value(item.get("token"), "-"),
                avatar_surface_html_json_value(item.get("automatic_gate"), "-")
            );
        }
        for item in items
            .iter()
            .filter(|item| item.get("manual_decision").and_then(Value::as_str) == Some("pending"))
        {
            let Some(token) = item.get("token").and_then(Value::as_str) else {
                continue;
            };
            let href_raw =
                avatar_surface_route_href(renderer_route_raw, q.project.as_deref(), Some(token));
            let label = avatar_surface_renderer_token_label(token);
            if !pending_links.is_empty() {
                pending_links.push(' ');
            }
            pending_links.push_str(&format!(
                r#"<a href="{href}">{label}</a>"#,
                href = html_escape(&href_raw),
                label = html_escape(&label),
            ));
        }
    }
    if pending_links.is_empty() {
        pending_links.push('-');
    }

    format!(
        r#"<section class="health status-fresh">
      <div class="health-title">
        <span class="pill status-fresh">review</span>
        <strong>Xiao Shu Review Gate</strong>
        <span>tracks={tracks} selected={selected} pending={pending}</span>
      </div>
      <dl>
        <div><dt>auto</dt><dd>pass={auto_pass} blocked={auto_blocked}</dd></div>
        <div><dt>manual</dt><dd>required={manual_required} can_promote_review={can_promote}</dd></div>
        <div><dt>first pending</dt><dd>{first_pending}</dd></div>
        <div><dt>pending links</dt><dd class="pending-links">{pending_links}</dd></div>
        <div><dt>open</dt><dd><a href="{href}">review gate json</a></dd></div>
      </dl>
    </section>"#,
        tracks = tracks,
        selected = selected,
        pending = pending,
        auto_pass = auto_pass,
        auto_blocked = auto_blocked,
        manual_required = manual_required,
        can_promote = can_promote,
        first_pending = first_pending,
        pending_links = pending_links,
        href = href,
    )
}

fn avatar_surface_review_packet_html(
    review_packet_preview: &Value,
    q: &AvatarSurfaceQuery,
) -> String {
    let packet = review_packet_preview
        .get("review_packet")
        .unwrap_or(&Value::Null);
    let route_raw = packet
        .get("html_route")
        .and_then(Value::as_str)
        .unwrap_or("/avatar-surface/cortex-review-packet");
    let renderer_route_raw = packet
        .get("renderer_view_route")
        .and_then(Value::as_str)
        .unwrap_or("/avatar-surface/cortex-renderer-view");
    let href_raw = avatar_surface_route_href(route_raw, q.project.as_deref(), None);
    let href = html_escape(&href_raw);
    let packets = avatar_surface_html_json_value(packet.get("packet_count"), "0");
    let baseline_refs = avatar_surface_html_json_value(packet.get("baseline_reference_count"), "0");
    let approval_writes = avatar_surface_html_json_value(
        packet
            .get("acceptance")
            .and_then(|acceptance| acceptance.get("approval_writes_allowed")),
        "false",
    );
    let can_promote = avatar_surface_html_json_value(
        packet
            .get("acceptance")
            .and_then(|acceptance| acceptance.get("can_promote_review_tracks")),
        "false",
    );
    let records_persisted = avatar_surface_html_json_value(
        packet
            .get("acceptance")
            .and_then(|acceptance| acceptance.get("records_persisted")),
        "false",
    );
    let mut first_packet = "-".to_string();
    let mut first_preview = "-".to_string();
    if let Some(item) = packet
        .get("packets")
        .and_then(Value::as_array)
        .and_then(|items| items.first())
    {
        let token = item.get("token").and_then(Value::as_str).unwrap_or("-");
        first_packet = format!(
            "{} decision={}",
            html_escape(token),
            avatar_surface_html_json_value(item.get("default_decision"), "-")
        );
        let href_raw =
            avatar_surface_route_href(renderer_route_raw, q.project.as_deref(), Some(token));
        first_preview = format!(
            r#"<a href="{href}">{label}</a>"#,
            href = html_escape(&href_raw),
            label = html_escape(&avatar_surface_renderer_token_label(token)),
        );
    }

    format!(
        r#"<section class="health status-fresh">
      <div class="health-title">
        <span class="pill status-fresh">packet</span>
        <strong>Xiao Shu Review Packet</strong>
        <span>packets={packets} baseline_refs={baseline_refs}</span>
      </div>
      <dl>
        <div><dt>safety</dt><dd>approval_writes={approval_writes} records_persisted={records_persisted} can_promote={can_promote}</dd></div>
        <div><dt>first packet</dt><dd>{first_packet}</dd></div>
        <div><dt>preview</dt><dd>{first_preview}</dd></div>
        <div><dt>open</dt><dd><a href="{href}">review packet json</a></dd></div>
      </dl>
    </section>"#,
        packets = packets,
        baseline_refs = baseline_refs,
        approval_writes = approval_writes,
        records_persisted = records_persisted,
        can_promote = can_promote,
        first_packet = first_packet,
        first_preview = first_preview,
        href = href,
    )
}

fn avatar_surface_renderer_view_html(
    renderer_view_preview: &Value,
    generated_at: i64,
    requested_track: Option<&str>,
    requested_track_index: Option<usize>,
) -> String {
    let view = renderer_view_preview
        .get("renderer_view")
        .unwrap_or(&Value::Null);
    let tracks = view.get("tracks").and_then(Value::as_array);
    let active_track_index = tracks
        .map(|tracks| {
            requested_track
                .and_then(|token| {
                    tracks
                        .iter()
                        .position(|track| track.get("token").and_then(Value::as_str) == Some(token))
                })
                .or_else(|| requested_track_index.filter(|index| *index < tracks.len()))
                .unwrap_or(0)
        })
        .unwrap_or(0);
    let active = tracks
        .and_then(|tracks| tracks.get(active_track_index))
        .or_else(|| view.get("first_track"))
        .unwrap_or(&Value::Null);
    let initial = active.get("initial_frame").unwrap_or(&Value::Null);
    let initial_classes = avatar_surface_html_json_value(
        initial.get("css_classes"),
        "pose-neutral-idle expression-calm-eyes motion-idle-breathe accessory-none",
    );
    let first_token = avatar_surface_html_json_value(active.get("token"), "xiao_shu::unknown");
    let first_state = avatar_surface_html_json_value(initial.get("state_label"), "ready");
    let first_state_html = first_state
        .split_whitespace()
        .map(|part| format!("<span>{part}</span>"))
        .collect::<String>();
    let track_count = avatar_surface_html_json_value(view.get("track_count"), "0");
    let input = avatar_surface_html_json_value(view.get("input"), "-");
    let input_label = {
        input
            .split('+')
            .map(|part| {
                let trimmed = part.trim();
                let parts = trimmed.split('.').collect::<Vec<_>>();
                if parts.len() >= 2 {
                    format!("{}.{}", parts[parts.len() - 2], parts[parts.len() - 1])
                } else {
                    trimmed.to_string()
                }
            })
            .collect::<Vec<_>>()
            .join(" + ")
    };
    let writes_files =
        avatar_surface_html_json_value(renderer_view_preview.get("writes_files"), "false");
    let mutates_renderer =
        avatar_surface_html_json_value(renderer_view_preview.get("mutates_renderer"), "false");
    let pet_mutation = avatar_surface_html_json_value(
        renderer_view_preview.get("codex_pet_package_mutation"),
        "false",
    );
    let browser_pixels = avatar_surface_html_json_value(
        renderer_view_preview.get("browser_renders_pixels"),
        "false",
    );
    let data_json = html_json_script(renderer_view_preview);
    let mut track_buttons = String::new();
    if let Some(tracks) = view.get("tracks").and_then(Value::as_array) {
        for (index, track) in tracks.iter().enumerate() {
            let active = if index == active_track_index {
                " is-active"
            } else {
                ""
            };
            let review = if track
                .get("review_only")
                .and_then(Value::as_bool)
                .unwrap_or(false)
            {
                " is-review"
            } else {
                ""
            };
            let token_raw = track.get("token").and_then(Value::as_str).unwrap_or("-");
            let token = html_escape(token_raw);
            let token_label = html_escape(&avatar_surface_renderer_token_label(token_raw));
            let track_kind = avatar_surface_html_json_value(track.get("track_kind"), "selected");
            let frames = avatar_surface_html_json_value(track.get("frame_count"), "0");
            let duration = avatar_surface_html_json_value(track.get("duration_ms"), "0");
            track_buttons.push_str(&format!(
                r#"<button type="button" class="track-button{active}{review}" data-track-index="{index}" data-track-token="{token}">
          <span title="{token}">{token_label}</span>
          <small>{track_kind} / {frames} frames / {duration}ms</small>
        </button>"#,
                active = active,
                review = review,
                index = index,
                token = token,
                token_label = token_label,
                track_kind = track_kind,
                frames = frames,
                duration = duration,
            ));
        }
    }
    if track_buttons.is_empty() {
        track_buttons.push_str(
            r#"<button type="button" class="track-button is-active" data-track-index="0">
          <span>xiao_shu::unknown</span>
          <small>0 frames / 0ms</small>
        </button>"#,
        );
    }

    format!(
        r#"<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Xiao Shu Sidecar Renderer</title>
  <style>
    :root {{
      color-scheme: light dark;
      --bg: #fbfaf5;
      --fg: #1c1d18;
      --muted: #687066;
      --line: #d9ddd1;
      --teal: #147a74;
      --coral: #d45f4c;
      --gold: #d69b2d;
      --ink: #26312f;
      --stage: #eef5ef;
      --surface: #ffffff;
      --soft: #f7efe6;
    }}
    @media (prefers-color-scheme: dark) {{
      :root {{
        --bg: #151711;
        --fg: #eff2e6;
        --muted: #a7ad9f;
        --line: #32382f;
        --teal: #5bd0c3;
        --coral: #ff907d;
        --gold: #f3c66b;
        --ink: #f4f7ed;
        --stage: #20261f;
        --surface: #1d211b;
        --soft: #29251d;
      }}
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      background: var(--bg);
      color: var(--fg);
      font: 14px/1.45 ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    }}
    main {{
      width: min(1160px, calc(100vw - 32px));
      margin: 22px auto 40px;
    }}
    header {{
      display: flex;
      justify-content: space-between;
      gap: 16px;
      align-items: flex-end;
      border-bottom: 1px solid var(--line);
      padding-bottom: 14px;
    }}
    h1 {{
      margin: 0;
      font-size: 24px;
      line-height: 1.1;
      font-weight: 760;
      letter-spacing: 0;
    }}
    .meta {{
      margin-top: 7px;
      color: var(--muted);
      min-width: 0;
      overflow-wrap: anywhere;
      word-break: break-word;
    }}
    .meta span {{
      display: block;
      min-width: 0;
      overflow-wrap: anywhere;
      word-break: break-all;
    }}
    .badge {{
      color: var(--teal);
      font-weight: 800;
      white-space: nowrap;
    }}
    .stage-grid {{
      display: grid;
      grid-template-columns: minmax(320px, 1.2fr) minmax(280px, 0.8fr);
      gap: 18px;
      margin-top: 22px;
      align-items: stretch;
    }}
    .stage {{
      min-height: 460px;
      display: grid;
      place-items: center;
      border: 1px solid var(--line);
      background:
        radial-gradient(circle at 22% 18%, rgba(212, 95, 76, 0.18), transparent 26%),
        radial-gradient(circle at 80% 12%, rgba(214, 155, 45, 0.18), transparent 28%),
        linear-gradient(180deg, var(--stage), var(--soft));
      overflow: hidden;
      position: relative;
    }}
    .stage::after {{
      content: "";
      position: absolute;
      inset: auto 8% 42px;
      height: 1px;
      background: var(--line);
      opacity: 0.75;
    }}
    .xiao-shu {{
      position: relative;
      width: min(320px, 72vw);
      height: min(320px, 72vw);
      display: grid;
      place-items: center;
      isolation: isolate;
    }}
    .xiao-shu-shadow {{
      position: absolute;
      width: 170px;
      height: 26px;
      bottom: 38px;
      border-radius: 999px;
      background: rgba(38, 49, 47, 0.18);
      filter: blur(1px);
    }}
    .xiao-shu-body {{
      position: relative;
      width: 188px;
      height: 226px;
      transform: translateY(0) rotate(0deg);
      transition: transform 180ms ease, filter 180ms ease;
    }}
    .xiao-shu-inner {{
      position: absolute;
      inset: 0;
      transform-origin: 50% 82%;
    }}
    .xiao-shu-torso {{
      position: absolute;
      width: 132px;
      height: 132px;
      left: 28px;
      bottom: 8px;
      border-radius: 44% 44% 40% 40%;
      background: linear-gradient(180deg, #f6ead7, #dfeadf);
      border: 3px solid var(--ink);
      box-shadow: inset 0 -10px 0 rgba(20, 122, 116, 0.12);
    }}
    .xiao-shu-head {{
      position: absolute;
      width: 152px;
      height: 138px;
      left: 18px;
      top: 18px;
      border-radius: 45% 45% 42% 42%;
      background: linear-gradient(180deg, #fff5e7, #f1ddc3);
      border: 3px solid var(--ink);
      box-shadow: inset 0 -12px 0 rgba(212, 95, 76, 0.1);
    }}
    .xiao-shu-hair {{
      position: absolute;
      width: 44px;
      height: 26px;
      top: 0;
      left: 72px;
      border-radius: 70% 30% 70% 30%;
      background: var(--coral);
      transform: rotate(-10deg);
      border: 3px solid var(--ink);
    }}
    .eye {{
      position: absolute;
      width: 16px;
      height: 23px;
      top: 66px;
      border-radius: 999px;
      background: var(--ink);
      transition: height 160ms ease, transform 160ms ease;
    }}
    .eye.left {{ left: 46px; }}
    .eye.right {{ right: 46px; }}
    .cheek {{
      position: absolute;
      width: 24px;
      height: 12px;
      top: 90px;
      border-radius: 999px;
      background: rgba(212, 95, 76, 0.28);
    }}
    .cheek.left {{ left: 28px; }}
    .cheek.right {{ right: 28px; }}
    .mouth {{
      position: absolute;
      width: 34px;
      height: 16px;
      left: 59px;
      top: 92px;
      border: 3px solid var(--ink);
      border-top: 0;
      border-radius: 0 0 34px 34px;
      transition: width 160ms ease, height 160ms ease, left 160ms ease;
    }}
    .hand {{
      position: absolute;
      width: 34px;
      height: 50px;
      top: 126px;
      border-radius: 999px;
      background: #fff0db;
      border: 3px solid var(--ink);
      transform-origin: 50% 12%;
    }}
    .hand.left {{ left: 8px; transform: rotate(18deg); }}
    .hand.right {{ right: 8px; transform: rotate(-18deg); }}
    .status-dot {{
      position: absolute;
      width: 38px;
      height: 38px;
      right: 16px;
      top: 22px;
      border-radius: 999px;
      background: var(--gold);
      border: 3px solid var(--ink);
      opacity: 0;
      transform: scale(0.84);
      transition: opacity 180ms ease, transform 180ms ease;
    }}
    .pose-upright-ready .xiao-shu-body {{ transform: translateY(-8px) rotate(-1deg); }}
    .pose-neutral-idle .xiao-shu-body {{ transform: translateY(0) rotate(0deg); }}
    .pose-lean-forward .xiao-shu-body {{ transform: translateY(4px) rotate(3deg); }}
    .pose-inspect-tilt .xiao-shu-body {{ transform: translateY(1px) rotate(-5deg); }}
    .pose-peek-forward .xiao-shu-body {{ transform: translateY(6px) scale(1.02); }}
    .expression-bright-smile .mouth {{ width: 44px; height: 22px; left: 54px; }}
    .expression-focused-eyes .eye {{ height: 13px; transform: translateY(5px); }}
    .expression-checking-eyes .eye.left {{ transform: translateX(-4px); }}
    .expression-checking-eyes .eye.right {{ transform: translateX(-4px); }}
    .expression-concerned-eyes .eye {{ height: 18px; transform: rotate(6deg); }}
    .accessory-soft-status-glow .status-dot,
    .accessory-small-attention-mark .status-dot {{
      opacity: 1;
      transform: scale(1);
    }}
    .motion-idle-breathe .xiao-shu-inner {{ animation: breathe 2400ms ease-in-out infinite; }}
    .motion-soft-bounce .xiao-shu-inner {{ animation: soft-bounce 900ms ease-in-out infinite; }}
    .motion-sorting-glow .status-dot {{ animation: glow 1200ms ease-in-out infinite; }}
    .motion-look-sideways .xiao-shu-inner {{ animation: look-sideways 1600ms ease-in-out infinite; }}
    .motion-alert-peek .xiao-shu-inner {{ animation: alert-peek 900ms ease-in-out infinite; }}
    @keyframes breathe {{
      0%, 100% {{ transform: translateY(0) scale(1); }}
      50% {{ transform: translateY(-3px) scale(1.01); }}
    }}
    @keyframes soft-bounce {{
      0%, 100% {{ transform: translateY(0); }}
      45% {{ transform: translateY(-14px); }}
    }}
    @keyframes glow {{
      0%, 100% {{ box-shadow: 0 0 0 rgba(214, 155, 45, 0.15); }}
      50% {{ box-shadow: 0 0 28px rgba(214, 155, 45, 0.55); }}
    }}
    @keyframes look-sideways {{
      0%, 100% {{ transform: translateX(0); }}
      50% {{ transform: translateX(-8px); }}
    }}
    @keyframes alert-peek {{
      0%, 100% {{ transform: translateY(2px) scale(1); }}
      50% {{ transform: translateY(-8px) scale(1.03); }}
    }}
    .inspector {{
      border-top: 4px solid var(--teal);
      border-bottom: 1px solid var(--line);
      padding: 0 0 10px;
      min-width: 0;
    }}
    .inspector h2 {{
      margin: 0 0 10px;
      font-size: 16px;
      letter-spacing: 0;
    }}
    .inspector dl {{
      display: grid;
      grid-template-columns: 110px minmax(0, 1fr);
      gap: 9px 12px;
      margin: 0;
      min-width: 0;
    }}
    .inspector dt {{
      color: var(--muted);
      font-size: 11px;
      font-weight: 800;
      text-transform: uppercase;
    }}
    .inspector dd {{
      margin: 0;
      min-width: 0;
      overflow-wrap: anywhere;
      word-break: break-word;
    }}
    .inspector dd span {{
      display: block;
      min-width: 0;
      overflow-wrap: anywhere;
      word-break: break-word;
    }}
    .inspector dd[data-state] span {{
      word-break: break-all;
    }}
    .tracks {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
      gap: 10px;
      margin-top: 16px;
    }}
    .track-button {{
      min-height: 58px;
      text-align: left;
      border: 1px solid var(--line);
      background: var(--surface);
      color: var(--fg);
      padding: 10px 12px;
      cursor: pointer;
      font: inherit;
    }}
    .track-button.is-active {{
      border-color: var(--teal);
      box-shadow: inset 4px 0 0 var(--teal);
    }}
    .track-button.is-review:not(.is-active) {{
      box-shadow: inset 4px 0 0 var(--gold);
    }}
    .track-button span,
    .track-button small {{
      display: block;
      min-width: 0;
      overflow-wrap: anywhere;
      word-break: break-word;
    }}
    .track-button small {{ color: var(--muted); margin-top: 3px; }}
    @media (max-width: 820px) {{
      main {{ width: min(100vw - 20px, 1160px); margin-top: 14px; }}
      header {{ display: block; }}
      .badge {{ display: block; margin-top: 10px; }}
      .stage-grid {{ grid-template-columns: 1fr; }}
      .stage {{ min-height: 380px; }}
      .inspector dl {{ grid-template-columns: 1fr; }}
    }}
  </style>
</head>
<body>
  <main>
    <header>
      <div>
        <h1>Xiao Shu Sidecar Renderer</h1>
        <div class="meta"><span>tracks={track_count}</span><span>active={first_token}</span><span title="{input_title}">input={input}</span><span>generated_at={generated_at}</span></div>
      </div>
      <div class="badge">browser pixels={browser_pixels}</div>
    </header>
    <section class="stage-grid" data-stage="xiao-shu-renderer-view">
      <div class="stage">
        <div class="xiao-shu {initial_classes}" data-xiao-shu data-current-frame="">
          <div class="xiao-shu-shadow"></div>
          <div class="xiao-shu-body">
            <div class="xiao-shu-inner">
              <div class="xiao-shu-torso"></div>
              <div class="hand left"></div>
              <div class="hand right"></div>
              <div class="xiao-shu-head">
                <div class="xiao-shu-hair"></div>
                <div class="eye left"></div>
                <div class="eye right"></div>
                <div class="cheek left"></div>
                <div class="cheek right"></div>
                <div class="mouth"></div>
              </div>
              <div class="status-dot"></div>
            </div>
          </div>
        </div>
      </div>
      <aside class="inspector">
        <h2>Renderer State</h2>
        <dl>
          <dt>token</dt><dd data-token>{first_token}</dd>
          <dt>state</dt><dd data-state>{first_state}</dd>
          <dt>safety</dt><dd><span>writes_files={writes_files}</span><span>mutates_renderer={mutates_renderer}</span><span>pet_package={pet_mutation}</span></dd>
          <dt>mode</dt><dd>sidecar-only browser view</dd>
        </dl>
      </aside>
    </section>
    <nav class="tracks" aria-label="renderer tracks">
      {track_buttons}
    </nav>
  </main>
  <script type="application/json" id="renderer-data">{data_json}</script>
  <script>
    const payload = JSON.parse(document.getElementById("renderer-data").textContent);
    const view = payload.renderer_view || {{}};
    const tracks = Array.isArray(view.tracks) ? view.tracks : [];
    const figure = document.querySelector("[data-xiao-shu]");
    const tokenEl = document.querySelector("[data-token]");
    const stateEl = document.querySelector("[data-state]");
    const buttons = Array.from(document.querySelectorAll("[data-track-index]"));
    let trackIndex = {active_track_index};
    let frameIndex = 0;
    let timer = null;

    function activeTrack() {{
      return tracks[trackIndex] || tracks[0] || {{ frames: [] }};
    }}

    function setActiveButton() {{
      buttons.forEach((button) => {{
        button.classList.toggle("is-active", Number(button.dataset.trackIndex) === trackIndex);
      }});
    }}

    function setStateLabel(value) {{
      if (!stateEl) {{
        return;
      }}
      stateEl.textContent = "";
      String(value || "").split(/\s+/).filter(Boolean).forEach((part) => {{
        const span = document.createElement("span");
        span.textContent = part;
        stateEl.appendChild(span);
      }});
    }}

    function applyFrame() {{
      const track = activeTrack();
      const frames = Array.isArray(track.frames) ? track.frames : [];
      if (!figure || frames.length === 0) {{
        return;
      }}
      const frame = frames[frameIndex] || frames[0];
      figure.className = "xiao-shu " + (frame.css_classes || "pose-neutral-idle expression-calm-eyes motion-idle-breathe accessory-none");
      figure.dataset.currentFrame = frame.frame_id || "";
      if (tokenEl) tokenEl.textContent = track.token || "xiao_shu::unknown";
      setStateLabel(frame.state_label || "");
      const nextFrame = frames[(frameIndex + 1) % frames.length] || frame;
      const currentAt = Number(frame.at_ms || 0);
      const nextAt = Number(nextFrame.at_ms || 0);
      const duration = Number(track.duration_ms || 1000);
      let delay = frameIndex < frames.length - 1 ? nextAt - currentAt : duration - currentAt;
      delay = Math.max(180, delay);
      frameIndex = (frameIndex + 1) % frames.length;
      timer = window.setTimeout(applyFrame, delay);
    }}

    buttons.forEach((button) => {{
      button.addEventListener("click", () => {{
        trackIndex = Number(button.dataset.trackIndex || 0);
        frameIndex = 0;
        if (timer) window.clearTimeout(timer);
        setActiveButton();
        applyFrame();
        const track = activeTrack();
        if (track.token && window.history && window.URL) {{
          const url = new URL(window.location.href);
          url.searchParams.set("track", track.token);
          window.history.replaceState(null, "", url);
        }}
      }});
    }});
    setActiveButton();
    applyFrame();
  </script>
</body>
</html>"#,
        track_count = track_count,
        input = input_label,
        input_title = input,
        generated_at = generated_at,
        browser_pixels = browser_pixels,
        initial_classes = initial_classes,
        first_token = first_token,
        first_state = first_state_html,
        active_track_index = active_track_index,
        writes_files = writes_files,
        mutates_renderer = mutates_renderer,
        pet_mutation = pet_mutation,
        track_buttons = track_buttons,
        data_json = data_json,
    )
}

fn avatar_surface_payload(q: &AvatarSurfaceQuery, avatars: Vec<Value>, generated_at: i64) -> Value {
    json!({
        "agent_avatar_protocol": crate::avatar_surface::AGENT_AVATAR_PROTOCOL_VERSION,
        "read_only": true,
        "surface": "avatar_surface_http",
        "count": avatars.len(),
        "project": q.project.as_deref(),
        "role": q.role.as_deref(),
        "max_idle_secs": q.effective_max_idle_secs(),
        "limit": q.effective_limit(),
        "generated_at": generated_at,
        "stale_secs": q.effective_stale_secs(),
        "avatars": avatars,
    })
}

fn avatar_surface_panel_html(
    q: &AvatarSurfaceQuery,
    avatars: &[Value],
    heartbeat_health: &Value,
    cortex_status: &Value,
    cortex_language: &Value,
    cortex_motion: &Value,
    cortex_renderer: &Value,
    cortex_renderer_registry: &Value,
    cortex_binding_plan: &Value,
    cortex_binding_fixture: &Value,
    cortex_visual_adapter: &Value,
    cortex_renderer_view: &Value,
    cortex_review_gate: &Value,
    cortex_review_packet: &Value,
    report: &str,
    generated_at: i64,
) -> String {
    let refresh_secs = q.effective_refresh_secs();
    let stale_secs = q.effective_stale_secs();
    let subtitle = format!(
        "project={} role={} max_idle_secs={} source=daemon-http",
        q.project.as_deref().unwrap_or("*"),
        q.role.as_deref().unwrap_or("*"),
        q.effective_max_idle_secs()
    );
    let meta = format!(
        "last update={} refresh={}s stale_after={}s",
        generated_at, refresh_secs, stale_secs
    );
    let mut rows = String::new();
    for avatar in avatars {
        let agent_id = avatar_surface_html_value(avatar, "agent_id", "unknown-agent");
        let runtime = avatar_surface_html_value(avatar, "runtime", "unknown-runtime");
        let avatar_id = avatar_surface_html_value(avatar, "avatar_id", "unknown-avatar");
        let mode = avatar_surface_html_value(avatar, "mode", "unknown");
        let activity = avatar_surface_html_value(avatar, "activity_state", "unknown");
        let focus = avatar_surface_html_value(avatar, "focus", "-");
        let risk = avatar_surface_html_value(avatar, "risk_level", "-");
        let next = avatar_surface_html_value(avatar, "next_action", "-");
        let heartbeat = avatar_surface_html_value(avatar, "last_heartbeat_at", "-");
        let (status_class, status_label, age_label) =
            avatar_surface_status(avatar, generated_at, stale_secs);
        let flags = format!(
            "avatar_state={} compat_pet={}",
            avatar_surface_html_value(avatar, "has_avatar_state", "false"),
            avatar_surface_html_value(avatar, "has_compat_pet_state", "false")
        );
        rows.push_str(&format!(
            r#"<tr class="{status_class}">
  <td><strong>{agent_id}</strong><span>{runtime} / {avatar_id}</span></td>
  <td>{mode}<span>{activity}</span></td>
  <td>{focus}<span>risk {risk}</span></td>
  <td>{next}<span>{flags}</span></td>
  <td><span class="pill {status_class}">{status_label}</span><span>{age_label}</span><span>heartbeat {heartbeat}</span></td>
</tr>"#
        ));
    }
    if rows.is_empty() {
        rows.push_str(
            r#"<tr><td colspan="5" class="empty">No avatar presence rows matched the filters.</td></tr>"#,
        );
    }
    let health_html = avatar_surface_health_html(heartbeat_health);
    let cortex_html = avatar_surface_cortex_html(cortex_status);
    let language_html = avatar_surface_language_html(cortex_language);
    let motion_html = avatar_surface_motion_html(cortex_motion);
    let renderer_html = avatar_surface_renderer_html(cortex_renderer);
    let renderer_registry_html = avatar_surface_renderer_registry_html(cortex_renderer_registry);
    let binding_plan_html = avatar_surface_binding_plan_html(cortex_binding_plan);
    let binding_fixture_html = avatar_surface_binding_fixture_html(cortex_binding_fixture);
    let visual_adapter_html = avatar_surface_visual_adapter_html(cortex_visual_adapter);
    let renderer_view_html = avatar_surface_renderer_view_summary_html(cortex_renderer_view, q);
    let review_gate_html = avatar_surface_review_gate_html(cortex_review_gate, q);
    let review_packet_html = avatar_surface_review_packet_html(cortex_review_packet, q);
    let quick_actions_html =
        avatar_surface_quick_actions_html(cortex_renderer_view, cortex_review_gate, q);

    format!(
        r#"<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta http-equiv="refresh" content="{refresh_secs}">
  <title>Agent Avatar Surface</title>
  <style>
    :root {{
      color-scheme: light dark;
      --bg: #f7f7f3;
      --fg: #181915;
      --muted: #65685f;
      --line: #d8d9cf;
      --accent: #167a72;
      --fresh: #167a72;
      --stale: #b45309;
      --unknown: #65685f;
      --surface: #ffffff;
      --code: #f0f1eb;
    }}
    @media (prefers-color-scheme: dark) {{
      :root {{
        --bg: #161713;
        --fg: #eceee4;
        --muted: #a5a99d;
        --line: #33372e;
        --accent: #5bd0c3;
        --fresh: #5bd0c3;
        --stale: #f0a35e;
        --unknown: #a5a99d;
        --surface: #20221d;
        --code: #282b24;
      }}
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      background: var(--bg);
      color: var(--fg);
      font: 14px/1.45 ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    }}
    main {{
      width: min(1120px, calc(100vw - 32px));
      margin: 24px auto 40px;
    }}
    header {{
      display: flex;
      align-items: flex-end;
      justify-content: space-between;
      gap: 16px;
      border-bottom: 1px solid var(--line);
      padding-bottom: 14px;
    }}
    h1 {{
      margin: 0;
      font-size: 24px;
      line-height: 1.1;
      font-weight: 720;
      letter-spacing: 0;
    }}
    .subtitle {{
      margin-top: 7px;
      color: var(--muted);
      overflow-wrap: anywhere;
    }}
    .meta {{
      margin-top: 6px;
      color: var(--muted);
      font-size: 12px;
      overflow-wrap: anywhere;
    }}
    .count {{
      color: var(--accent);
      font-weight: 700;
      white-space: nowrap;
    }}
    .health {{
      margin-top: 18px;
      padding: 12px;
      background: var(--surface);
      border: 1px solid var(--line);
      border-left: 4px solid var(--unknown);
    }}
    .health.status-fresh {{ border-left-color: var(--fresh); }}
    .health.status-stale {{ border-left-color: var(--stale); }}
    .health.status-unknown {{ border-left-color: var(--unknown); }}
    .health-title {{
      display: flex;
      align-items: baseline;
      gap: 8px;
      flex-wrap: wrap;
    }}
    .health-title strong {{
      font-size: 14px;
    }}
    .health-title span:last-child {{
      color: var(--muted);
      overflow-wrap: anywhere;
    }}
    .health dl {{
      display: grid;
      grid-template-columns: repeat(4, minmax(0, 1fr));
      gap: 10px;
      margin: 12px 0 0;
    }}
    .health dt {{
      color: var(--muted);
      font-size: 11px;
      font-weight: 700;
      text-transform: uppercase;
    }}
    .health dd {{
      margin: 3px 0 0;
      overflow-wrap: anywhere;
    }}
    .quick-actions {{
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 10px;
      margin-top: 18px;
    }}
    .quick-action {{
      display: block;
      padding: 10px 12px;
      color: inherit;
      text-decoration: none;
      background: var(--surface);
      border: 1px solid var(--line);
      border-left: 4px solid var(--accent);
    }}
    .quick-action strong {{
      display: block;
      font-size: 14px;
    }}
    .quick-action span {{
      display: block;
      margin-top: 4px;
      color: var(--muted);
      font-size: 12px;
      overflow-wrap: anywhere;
    }}
    .quick-action:hover {{
      border-color: var(--accent);
    }}
    table {{
      width: 100%;
      margin-top: 18px;
      border-collapse: collapse;
      background: var(--surface);
      border: 1px solid var(--line);
    }}
    th, td {{
      padding: 11px 12px;
      border-bottom: 1px solid var(--line);
      text-align: left;
      vertical-align: top;
      overflow-wrap: anywhere;
    }}
    th {{
      color: var(--muted);
      font-size: 12px;
      font-weight: 700;
      text-transform: uppercase;
    }}
    td span {{
      display: block;
      margin-top: 3px;
      color: var(--muted);
      font-size: 12px;
    }}
    tbody tr.status-fresh td:first-child {{
      border-left: 4px solid var(--fresh);
    }}
    tbody tr.status-stale td:first-child {{
      border-left: 4px solid var(--stale);
    }}
    tbody tr.status-unknown td:first-child {{
      border-left: 4px solid var(--unknown);
    }}
    .pill {{
      display: inline-block;
      margin: 0 0 4px;
      padding: 2px 7px;
      border: 1px solid currentColor;
      border-radius: 999px;
      font-size: 12px;
      font-weight: 700;
      line-height: 1.25;
    }}
    .pill.status-fresh {{ color: var(--fresh); }}
    .pill.status-stale {{ color: var(--stale); }}
    .pill.status-unknown {{ color: var(--unknown); }}
    .empty {{
      color: var(--muted);
      text-align: center;
      padding: 28px 12px;
    }}
    pre {{
      margin: 18px 0 0;
      padding: 14px;
      overflow: auto;
      background: var(--code);
      border: 1px solid var(--line);
      white-space: pre-wrap;
    }}
    @media (max-width: 760px) {{
      main {{ width: min(100vw - 20px, 1120px); margin-top: 14px; }}
      header {{ display: block; }}
      .count {{ display: block; margin-top: 10px; }}
      .quick-actions {{ grid-template-columns: 1fr; }}
      .health dl {{ grid-template-columns: 1fr; }}
      table, thead, tbody, tr, th, td {{ display: block; }}
      thead {{ display: none; }}
      tr {{ border-bottom: 1px solid var(--line); }}
      td {{ border-bottom: 0; padding: 9px 10px; }}
    }}
  </style>
</head>
<body>
  <main>
    <header>
      <div>
        <h1>Agent Avatar Surface</h1>
        <div class="subtitle">{subtitle}</div>
        <div class="meta">{meta}</div>
      </div>
      <div class="count">{count} avatars</div>
    </header>
    {quick_actions_html}
    {health_html}
    {cortex_html}
    {language_html}
    {motion_html}
    {renderer_html}
    {renderer_registry_html}
    {binding_plan_html}
    {binding_fixture_html}
    {visual_adapter_html}
    {renderer_view_html}
    {review_gate_html}
    {review_packet_html}
    <table>
      <thead>
        <tr><th>Agent</th><th>Mode</th><th>Focus</th><th>Next</th><th>Heartbeat</th></tr>
      </thead>
      <tbody>{rows}</tbody>
    </table>
    <pre>{report}</pre>
  </main>
</body>
</html>"#,
        subtitle = html_escape(&subtitle),
        meta = html_escape(&meta),
        count = avatars.len(),
        quick_actions_html = quick_actions_html,
        health_html = health_html,
        cortex_html = cortex_html,
        language_html = language_html,
        motion_html = motion_html,
        renderer_html = renderer_html,
        renderer_registry_html = renderer_registry_html,
        binding_plan_html = binding_plan_html,
        binding_fixture_html = binding_fixture_html,
        visual_adapter_html = visual_adapter_html,
        renderer_view_html = renderer_view_html,
        review_gate_html = review_gate_html,
        review_packet_html = review_packet_html,
        rows = rows,
        report = html_escape(report)
    )
}

fn default_limit() -> u32 {
    50
}

fn default_max_idle() -> i64 {
    300
}

fn default_panel_refresh_secs() -> u32 {
    10
}

fn default_avatar_stale_secs() -> i64 {
    300
}

fn default_avatar_voice_gate_cooldown_secs() -> i64 {
    300
}

#[cfg(test)]
mod tests {
    use super::*;
    use ab_store::{AgentPresenceRecord, ForumPostRecord};

    #[test]
    fn parse_listen_addrs_single() {
        assert_eq!(parse_listen_addrs("0.0.0.0:7878"), vec!["0.0.0.0:7878"]);
        assert_eq!(parse_listen_addrs("127.0.0.1:7878"), vec!["127.0.0.1:7878"]);
    }

    #[test]
    fn parse_listen_addrs_comma_separated_dual_bind() {
        // Realistic config: loopback + tailscale interface only — strictly
        // narrower than 0.0.0.0 since WiFi/ethernet are not bound.
        let addrs = parse_listen_addrs("127.0.0.1:7878,100.91.146.24:7878");
        assert_eq!(addrs, vec!["127.0.0.1:7878", "100.91.146.24:7878"]);
    }

    #[test]
    fn parse_listen_addrs_trims_whitespace_and_skips_empty() {
        // Tolerate "addr1 , addr2 ,, addr3" — common when humans hand-edit.
        let addrs = parse_listen_addrs(" 127.0.0.1:7878 , 100.91.146.24:7878 ,, ");
        assert_eq!(addrs, vec!["127.0.0.1:7878", "100.91.146.24:7878"]);
    }

    #[test]
    fn parse_listen_addrs_empty_input_returns_empty() {
        // `run()` rejects empty-after-parse to fail fast rather than bind to
        // an implicit default surprising the operator.
        assert!(parse_listen_addrs("").is_empty());
        assert!(parse_listen_addrs("  ,  ,  ").is_empty());
    }

    #[test]
    fn forum_projection_options_match_mcp_compact_defaults() {
        assert_eq!(forum_projection_options(None, None, None), (false, 0, true));
        assert_eq!(
            forum_projection_options(Some(true), None, None),
            (true, 2_000, false)
        );
        assert_eq!(
            forum_projection_options(Some(true), Some(80), Some(true)),
            (true, 80, true)
        );
        assert_eq!(
            forum_projection_options(Some(true), Some(200_000), None),
            (true, 100_000, false)
        );
    }

    #[test]
    fn forum_posts_payload_compacts_body_and_omits_refs() {
        let posts = vec![ForumPostRecord {
            id: 9,
            thread_id: 18,
            author: "codex".into(),
            kind: "reply".into(),
            body: "abcdef".into(),
            refs: json!({"files": ["x.rs"]}),
            created_at: 123,
        }];

        let payload = forum_posts_payload(Some(18), None, &posts, true, 3, false);
        assert_eq!(payload["next_cursor"], json!(9));
        assert_eq!(payload["projection"]["compact"], json!(true));
        assert_eq!(payload["projection"]["body_max_chars"], json!(3));
        assert_eq!(payload["projection"]["include_refs"], json!(false));
        assert_eq!(payload["projection"]["truncated_posts"], json!(1));
        assert_eq!(payload["posts"][0]["body"], json!("abc…"));
        assert_eq!(payload["posts"][0]["body_truncated"], json!(true));
        assert_eq!(payload["posts"][0]["body_total_chars"], json!(6));
        assert_eq!(payload["posts"][0]["refs_omitted"], json!(true));
        assert!(payload["posts"][0].get("refs").is_none());
    }

    fn presence_fixture() -> AgentPresenceRecord {
        AgentPresenceRecord {
            session_id: "aio2:agent-bridge:main".into(),
            name: "aio2 main".into(),
            description: Some("test".into()),
            version: Some("0.1.0".into()),
            url: None,
            capabilities: Some(json!({ "forum": true })),
            skills: Some(json!([{ "id": "rust" }])),
            node: "aio2".into(),
            project: "agent-bridge".into(),
            role: "main".into(),
            tag: None,
            cwd: None,
            pid: None,
            started_at: 0,
            last_heartbeat_at: 0,
        }
    }

    fn avatar_presence_fixture() -> AgentPresenceRecord {
        let mut row = presence_fixture();
        row.session_id = "claude-code-xiao-shu-report-dogfood".into();
        row.name = "Claude Code Xiao Shu".into();
        row.capabilities = Some(json!({
            "avatar_state": {
                "agent_avatar_protocol": 1,
                "agent_id": "claude-code-xiao-shu-report-dogfood",
                "runtime": "claude-code",
                "avatar_id": "xiao-shu-dev",
                "mode": "orienting",
                "activity_state": "dogfooding-avatar-report",
                "focus": "avatar-surface-report",
                "risk_level": "low",
                "next_action": "report terminal-facing avatar surface result",
                "evidence": "real CLI Agent dogfood for avatar_surface_report",
                "project": "agent-bridge",
                "cwd": "/Users/pallasting/Projects/agent-bridge"
            },
            "pet_state": {
                "pet_id": "xiao-shu-dev",
                "mode": "orienting"
            }
        }));
        row.last_heartbeat_at = 1779192840;
        row
    }

    #[test]
    fn agent_card_drops_local_only_fields() {
        let row = presence_fixture();
        let card = presence_to_agent_card(&row);
        let obj = card.as_object().unwrap();
        // Public fields kept.
        assert_eq!(obj.get("name").and_then(|v| v.as_str()), Some("aio2 main"));
        assert_eq!(
            obj.get("description").and_then(|v| v.as_str()),
            Some("test")
        );
        assert_eq!(obj.get("version").and_then(|v| v.as_str()), Some("0.1.0"));
        assert!(obj.get("capabilities").is_some());
        assert!(obj.get("skills").is_some());
        // Local-only fields stripped.
        for k in [
            "session_id",
            "node",
            "project",
            "role",
            "tag",
            "cwd",
            "pid",
            "started_at",
            "last_heartbeat_at",
        ] {
            assert!(
                !obj.contains_key(k),
                "AgentCard must not expose local-only field `{k}`"
            );
        }
    }

    #[test]
    fn agent_card_omits_unset_optionals() {
        let mut row = presence_fixture();
        row.description = None;
        row.version = None;
        row.url = None;
        row.capabilities = None;
        row.skills = None;
        let card = presence_to_agent_card(&row);
        let obj = card.as_object().unwrap();
        assert_eq!(obj.len(), 1, "only name should remain when others unset");
        assert!(obj.contains_key("name"));
    }

    #[test]
    fn embed_backend_factory_returns_384_dim() {
        let b = build_raw_embed_backend();
        assert_eq!(b.dim(), 384, "embedding backend must produce 384-d vectors");
        let name = b.name();
        assert!(
            name == "fnv1a-hash-384" || name == "all-MiniLM-L6-v2",
            "unexpected backend name: {name}"
        );
    }

    #[test]
    fn embed_request_deserializes_text_field() {
        let req: EmbedRequest = serde_json::from_str(r#"{"text":"hello world"}"#).unwrap();
        assert_eq!(req.text, "hello world");
    }

    #[test]
    fn avatar_surface_query_include_stale_disables_ttl() {
        let q = AvatarSurfaceQuery {
            project: Some("agent-bridge".into()),
            role: None,
            max_idle_secs: 300,
            include_stale: true,
            limit: 999,
            refresh_secs: 1,
            stale_secs: 1_000_000,
            include_raw_presence: false,
            include_compat: false,
        };

        assert_eq!(q.effective_max_idle_secs(), 0);
        assert_eq!(q.effective_limit(), 500);
        assert_eq!(q.effective_refresh_secs(), 3);
        assert_eq!(q.effective_stale_secs(), 86_400);
        let ctx = q.report_context();
        assert_eq!(ctx.project, Some("agent-bridge"));
        assert_eq!(ctx.role, None);
        assert_eq!(ctx.source, "daemon-http");
    }

    #[test]
    fn avatar_surface_http_payload_matches_protocol_shape() {
        let q = AvatarSurfaceQuery {
            project: Some("agent-bridge".into()),
            role: Some("main".into()),
            max_idle_secs: 300,
            include_stale: false,
            limit: 5,
            refresh_secs: 10,
            stale_secs: 300,
            include_raw_presence: false,
            include_compat: true,
        };
        let avatar =
            crate::avatar_surface::entry_from_presence(&avatar_presence_fixture(), false, true);
        let payload = avatar_surface_payload(&q, vec![avatar], 1_779_193_100);

        assert_eq!(payload["agent_avatar_protocol"], 1);
        assert_eq!(payload["read_only"], true);
        assert_eq!(payload["surface"], "avatar_surface_http");
        assert_eq!(payload["count"], 1);
        assert_eq!(payload["project"], "agent-bridge");
        assert_eq!(payload["role"], "main");
        assert_eq!(payload["max_idle_secs"], 300);
        assert_eq!(payload["limit"], 5);
        assert_eq!(payload["generated_at"], 1_779_193_100i64);
        assert_eq!(payload["stale_secs"], 300);
        assert_eq!(
            payload["avatars"][0]["agent_id"],
            "claude-code-xiao-shu-report-dogfood"
        );
        assert_eq!(payload["avatars"][0]["runtime"], "claude-code");
        assert_eq!(payload["avatars"][0]["has_avatar_state"], true);
        assert_eq!(payload["avatars"][0]["has_compat_pet_state"], true);
    }

    #[test]
    fn avatar_surface_panel_html_escapes_avatar_fields() {
        let q = AvatarSurfaceQuery {
            project: Some("agent-bridge".into()),
            role: None,
            max_idle_secs: 0,
            include_stale: true,
            limit: 5,
            refresh_secs: 10,
            stale_secs: 300,
            include_raw_presence: false,
            include_compat: false,
        };
        let avatar = json!({
            "agent_id": "<script>alert(1)</script>",
            "runtime": "claude-code",
            "avatar_id": "xiao-shu-dev",
            "mode": "orienting",
            "activity_state": "dogfooding-avatar-report",
            "focus": "avatar-surface-report",
            "risk_level": "low",
            "next_action": "read <panel>",
            "last_heartbeat_at": 1779192840,
            "has_avatar_state": true,
            "has_compat_pet_state": true
        });
        let health = json!({
            "status": "healthy",
            "summary": "healthy <binary>",
            "binary": {
                "path": "/Users/me/.local/bin/agent-bridge.real",
                "supports_sync_presence": true,
                "supports_heartbeat_health": true
            },
            "launchd": {
                "last_exit_code": 0,
                "runs": 3
            },
            "presence": {
                "age_secs": 12
            }
        });
        let cortex = json!({
            "label": "com.agentbridge.avatar-cortex.agent-bridge",
            "launchd": {
                "loaded": true,
                "last_exit_code": 0,
                "runs": 2,
                "run_interval_secs": 300
            },
            "snapshot": {
                "path": "/Users/me/.local/share/agent-bridge/avatar_cortex/test.parquet",
                "total_rows": 1,
                "latest_long": {
                    "step": 16,
                    "cycle_ts": 1779193100,
                    "fingerprint": "abc<123>"
                }
            },
            "events": {
                "records_count": 16,
                "unhealthy_count": 0,
                "latest": {
                    "ts": 1779193080,
                    "status": "healthy",
                    "reason": "unchanged"
                }
            },
            "trend": {
                "step_records_delta": 0,
                "snapshot_event_lag_secs": 20,
                "latest_status": "healthy",
                "learning_state": {
                    "state": "caught_up",
                    "reason": "step_matches_records"
                },
                "behavior_policy": {
                    "badge": "caught up",
                    "recommended_action": "none",
                    "voice": {
                        "allowed": false
                    }
                }
            }
        });
        let language =
            crate::avatar_cortex::avatar_cortex_language_preview_from_status(cortex.clone());
        let motion = crate::avatar_cortex::avatar_cortex_motion_preview_from_status(cortex.clone());
        let renderer =
            crate::avatar_cortex::avatar_cortex_renderer_preview_from_status(cortex.clone());
        let renderer_registry =
            crate::avatar_cortex::avatar_cortex_renderer_registry_from_status(cortex.clone());
        let binding_plan =
            crate::avatar_cortex::avatar_cortex_binding_plan_from_status(cortex.clone());
        let binding_fixture =
            crate::avatar_cortex::avatar_cortex_binding_fixture_from_status(cortex.clone());
        let visual_adapter =
            crate::avatar_cortex::avatar_cortex_visual_adapter_from_status(cortex.clone());
        let renderer_view =
            crate::avatar_cortex::avatar_cortex_renderer_view_from_status(cortex.clone());
        let review_gate =
            crate::avatar_cortex::avatar_cortex_renderer_review_gate_from_status(cortex.clone());
        let review_packet =
            crate::avatar_cortex::avatar_cortex_renderer_review_packet_from_status(cortex.clone());
        let html = avatar_surface_panel_html(
            &q,
            &[avatar],
            &health,
            &cortex,
            &language,
            &motion,
            &renderer,
            &renderer_registry,
            &binding_plan,
            &binding_fixture,
            &visual_adapter,
            &renderer_view,
            &review_gate,
            &review_packet,
            "Agent <Avatar> Surface",
            1779193140,
        );

        assert!(html.contains("&lt;script&gt;alert(1)&lt;/script&gt;"));
        assert!(html.contains("read &lt;panel&gt;"));
        assert!(html.contains("Agent &lt;Avatar&gt; Surface"));
        assert!(html.contains("Heartbeat Health"));
        assert!(html.contains("Cortex Status"));
        assert!(html.contains("Xiao Shu Language"));
        assert!(html.contains("Xiao Shu Motion"));
        assert!(html.contains("Xiao Shu Renderer"));
        assert!(html.contains("Xiao Shu Renderer Registry"));
        assert!(html.contains("known=5 candidate=2 review=3 fallback=1"));
        assert!(html.contains("Xiao Shu Binding Plan"));
        assert!(html.contains("selected=2 deferred=4"));
        assert!(html.contains("first"));
        assert!(html.contains("xiao_shu::soft_bounce::low risk=low"));
        assert!(html.contains("writes_files=false mutates_renderer=false pet_package=false"));
        assert!(html.contains("Xiao Shu Binding Fixture"));
        assert!(html.contains("fixtures=2 source=avatar_cortex_binding_plan.selected"));
        assert!(html.contains("xiao_shu::soft_bounce::low motion=soft_bounce"));
        assert!(html.contains("duration=1800ms returns_idle=true"));
        assert!(html.contains("all_idle=true all_under_2s=true"));
        assert!(html.contains("Xiao Shu Visual Adapter"));
        assert!(
            html.contains("previews=2 input=avatar_cortex_binding_fixture.fixture.golden_payloads")
        );
        assert!(html.contains("xiao_shu::soft_bounce::low frames=4"));
        assert!(html.contains("motion=idle_breathe expression=bright_smile"));
        assert!(html
            .contains("pixels=false writes_files=false mutates_renderer=false pet_package=false"));
        assert!(html.contains("Xiao Shu Renderer View"));
        assert!(html
            .contains("tracks=5 selected=2 review=3 route=/avatar-surface/cortex-renderer-view"));
        assert!(html.contains("xiao_shu::soft_bounce::low frames=4"));
        assert!(html.contains("browser=true"));
        assert!(html.contains("renderer view"));
        assert!(html.contains("Avatar quick actions"));
        assert!(html.contains("Renderer View</strong>"));
        assert!(html.contains("Review Gate</strong>"));
        assert!(html.contains("pending=3 auto_pass=5 can_promote=false"));
        assert!(html.contains("Xiao Shu Review Gate"));
        assert!(html.contains("tracks=5 selected=2 pending=3"));
        assert!(html.contains("pass=5 blocked=0"));
        assert!(html.contains("required=true can_promote_review=false"));
        assert!(html.contains("pending links"));
        assert!(html.contains("track=xiao_shu%3A%3Asorting_glow%3A%3Amedium"));
        assert!(html.contains("track=xiao_shu%3A%3Alook_sideways%3A%3Amedium"));
        assert!(html.contains("track=xiao_shu%3A%3Aalert_peek%3A%3Amedium"));
        assert!(html.contains("review gate json"));
        assert!(html.contains("Xiao Shu Review Packet"));
        assert!(html.contains("packets=3 baseline_refs=2"));
        assert!(html.contains("approval_writes=false records_persisted=false can_promote=false"));
        assert!(html.contains("decision=keep_pending"));
        assert!(html.contains("review packet json"));
        assert!(html.contains("stage=candidate risk=low"));
        assert!(html.contains("no recent event window"));
        assert!(html.contains("healthy &lt;binary&gt;"));
        assert!(html.contains("step=16"));
        assert!(html.contains("records=16 latest=healthy reason=unchanged"));
        assert!(html.contains("state=caught_up reason=step_matches_records"));
        assert!(html.contains("badge=caught up action=none voice=false"));
        assert!(html.contains("delta=0 lag=20s unhealthy=0"));
        assert!(html.contains("abc&lt;123&gt;"));
        assert!(html.contains("/Users/me/.local/bin/agent-bridge.real"));
        assert!(html.contains("sync=true health=true"));
        assert!(html.contains(r#"<meta http-equiv="refresh" content="10">"#));
        assert!(html.contains("last update=1779193140 refresh=10s stale_after=300s"));
        assert!(html.contains("status-fresh"));
        assert!(html.contains("5m 0s ago"));
        assert!(!html.contains("<script>alert(1)</script>"));
    }

    #[test]
    fn avatar_surface_renderer_view_html_embeds_sidecar_view() {
        let cortex = json!({
            "surface": "avatar_cortex_status",
            "read_only": true,
            "launchd": { "loaded": true, "last_exit_code": 0, "runs": 1 },
            "snapshot": {
                "path": "/Users/me/.local/share/agent-bridge/avatar_cortex/test.parquet",
                "total_rows": 1,
                "latest_long": {
                    "step": 16,
                    "cycle_ts": 1779193100,
                    "fingerprint": "abc123"
                }
            },
            "events": {
                "records_count": 16,
                "unhealthy_count": 0,
                "latest": {
                    "ts": 1779193080,
                    "status": "healthy",
                    "reason": "unchanged"
                }
            },
            "trend": {
                "step_records_delta": 0,
                "snapshot_event_lag_secs": 20,
                "latest_status": "healthy",
                "learning_state": {
                    "state": "caught_up",
                    "reason": "step_matches_records"
                },
                "behavior_policy": {
                    "badge": "caught up",
                    "recommended_action": "none",
                    "voice": {
                        "allowed": false
                    }
                }
            }
        });
        let renderer_view = crate::avatar_cortex::avatar_cortex_renderer_view_from_status(cortex);
        let html = avatar_surface_renderer_view_html(&renderer_view, 1779193140, None, None);

        assert!(html.contains("Xiao Shu Sidecar Renderer"));
        assert!(html.contains("data-stage=\"xiao-shu-renderer-view\""));
        assert!(html.contains("xiao_shu::soft_bounce::low"));
        assert!(html.contains("xiao_shu::sorting_glow::medium"));
        assert!(html.contains("review_only / 8 frames / 1440ms"));
        assert!(html.contains("motion-soft-bounce"));
        assert!(html.contains("motion-sorting-glow"));
        assert!(html.contains("browser pixels=true"));
        assert!(html.contains("<span>writes_files=false</span>"));
        assert!(html.contains("<span>mutates_renderer=false</span>"));
        assert!(html.contains("<span>pet_package=false</span>"));
        assert!(html.contains("\"surface\":\"avatar_cortex_sidecar_renderer_view\""));

        let focused = avatar_surface_renderer_view_html(
            &renderer_view,
            1779193140,
            Some("xiao_shu::alert_peek::medium"),
            None,
        );
        assert!(focused.contains("<span>active=xiao_shu::alert_peek::medium</span>"));
        assert!(focused.contains(r#"let trackIndex = 4;"#));
        assert!(focused.contains(r#"data-track-token="xiao_shu::alert_peek::medium""#));
    }
}
