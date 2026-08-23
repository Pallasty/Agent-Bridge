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
//!   - `GET /avatar-surface/linux-renderer-state?...` — project-aware Linux renderer state
//!   - `GET /avatar-surface/linux-renderer?...` — browser proof for Linux floater renderer
//!   - `GET /avatar-surface/pet-spritesheet?...` — read-only installed pet sprite source
//!   - `GET /avatar-surface/sidecar-spritesheet?...` — read-only prototype sprite source
//!   - `GET /avatar-surface/cortex-review-gate?...` — read-only renderer review gate
//!   - `GET /avatar-surface/cortex-review-packet?...` — read-only renderer review packets
//!   - `GET /avatar-surface/cortex-review-report?...` — read-only review readiness report
//!   - `GET /avatar-surface/cortex-review-decisions?...` — read-only review decision ledger
//!   - `POST /avatar-surface/cortex-review-decision` — append-only review decision record
//!   - `GET /avatar-surface/cortex-preview?...` — voice preview without emission
//!   - `GET /avatar-surface/cortex-voice-policy?...` — read-only sparse voice policy
//!   - `GET /avatar-surface/cortex-voice-request?...` — read-only two-step voice request
//!   - `GET /avatar-surface/cortex-voice-confirm?...` — read-only confirmation action preview
//!   - `GET /avatar-surface/cortex-voice-action-preview?...` — read-only action readiness runbook
//!   - `GET /avatar-surface/xiao-shu-action-request?...` — LLM-safe Xiao Shu action request
//!   - `GET /avatar-surface/xiao-shu-action-requests?...` — read-only Xiao Shu request queue
//!   - `GET /avatar-surface/xiao-shu-action-console?...` — read-only operator console
//!   - `GET /avatar-surface/cortex-voice-gate?...` — dry-run explicit voice gate
//!   - `GET /identity?days=N` — δ-1 cross-node identity fingerprint
//!                              (same shape as `dream identity --json`)
//!   - `POST /embed` — text → 384-d embedding for non-Rust / non-MCP clients
//!                    (game runtimes, web, scripting). Phase 2.1 encoder
//!                    decoupled per thread 6 #226 / #228 / #231 split with
//!                    `embed_text` MCP tool. Returns the raw inner backend's
//!                    output without substrate side-effects.
//!   - `GET /embed/readiness` — honest local-model readiness plus bounded
//!                              stale-vector repair status.
//!   - `POST /agent/messages` — XM v0.1: write a message addressed to
//!                              a specific session on this node's inbox.
//!                              See `docs/DESIGN-cross-machine-agent-messaging-2026-05-17.md`.
//!   - `GET  /agent/inbox`    — XM v0.1: read this node's inbox for a
//!                              given `to_session`. Both endpoints are
//!                              tailnet-trusted; see R-XM-A/B in §3.
//!   - `GET /semantic-bus/runtime-conformance?...` — SSB remote harness export:
//!                                                    read-only conformance
//!                                                    snapshot for this node.
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
    response::{Html, IntoResponse, Response},
    routing::{get, post},
    Json, Router,
};
use serde::Deserialize;
use serde_json::{json, Value};
use std::future::Future;
use std::sync::{Arc, Mutex};

mod avatar_aura_startup;
use avatar_aura_startup::preload_avatar_aura_io;
pub use avatar_aura_startup::{AvatarAuraIoStartupConfig, AvatarAuraIoStartupError};

#[derive(Clone)]
struct AppState {
    store: Arc<dyn StateStore>,
    embed_backend: Arc<dyn EmbeddingBackend>,
    embed_maintenance: Arc<Mutex<EmbedMaintenanceStatus>>,
    avatar_aura_io_default: Option<Arc<crate::avatar_renderer::SanitizedAuraIoReport>>,
}

#[derive(Clone, Debug)]
struct EmbedMaintenanceStatus {
    phase: &'static str,
    batch_limit: usize,
    updated: usize,
    detail: Option<String>,
}

impl EmbedMaintenanceStatus {
    fn from_env() -> Self {
        let enabled = std::env::var("AGENT_BRIDGE_EMBED_AUTO_REPAIR")
            .ok()
            .map(|raw| {
                !matches!(
                    raw.trim().to_ascii_lowercase().as_str(),
                    "0" | "false" | "off" | "no"
                )
            })
            .unwrap_or(true);
        let batch_limit = std::env::var("AGENT_BRIDGE_EMBED_AUTO_REPAIR_BATCH")
            .ok()
            .and_then(|raw| raw.parse::<usize>().ok())
            .unwrap_or(100)
            .clamp(1, 1000);
        Self {
            phase: if enabled { "waiting" } else { "disabled" },
            batch_limit,
            updated: 0,
            detail: None,
        }
    }
}

async fn prepare_app_state(
    store: Arc<dyn StateStore>,
    aura_config: AvatarAuraIoStartupConfig,
) -> Result<AppState> {
    let avatar_aura_io_default = preload_avatar_aura_io(aura_config).await?;
    Ok(AppState {
        store,
        embed_backend: build_raw_embed_backend(),
        embed_maintenance: Arc::new(Mutex::new(EmbedMaintenanceStatus::from_env())),
        avatar_aura_io_default,
    })
}

fn set_embed_maintenance(
    status: &Arc<Mutex<EmbedMaintenanceStatus>>,
    phase: &'static str,
    updated: usize,
    detail: Option<String>,
) {
    let mut current = status
        .lock()
        .unwrap_or_else(|poisoned| poisoned.into_inner());
    current.phase = phase;
    current.updated = updated;
    current.detail = detail;
}

/// Warm the daemon's raw ONNX backend and, once it is genuinely ready, repair
/// at most one stale batch. This is deliberately once-per-process and bounded:
/// readiness recovery must not turn daemon startup into an unbounded migration.
fn spawn_embed_readiness_maintenance(state: &AppState) {
    let initial = state
        .embed_maintenance
        .lock()
        .unwrap_or_else(|poisoned| poisoned.into_inner())
        .clone();
    if initial.phase == "disabled" {
        return;
    }
    if state.embed_backend.name() == "fnv1a-hash-384" {
        set_embed_maintenance(
            &state.embed_maintenance,
            "skipped",
            0,
            Some("explicit hash backend has no semantic model to repair against".into()),
        );
        return;
    }

    let backend = state.embed_backend.clone();
    let store = state.store.clone();
    let status = state.embed_maintenance.clone();
    tokio::spawn(async move {
        let _ = tokio::task::spawn_blocking(move || backend.embed("warmup")).await;
        let deadline = tokio::time::Instant::now() + std::time::Duration::from_secs(120);
        while ab_store::vector::local_model_ready().is_none()
            && tokio::time::Instant::now() < deadline
        {
            tokio::time::sleep(std::time::Duration::from_millis(250)).await;
        }
        match ab_store::vector::local_model_ready() {
            Some(true) => {}
            Some(false) => {
                set_embed_maintenance(
                    &status,
                    "skipped",
                    0,
                    Some(
                        "local semantic model failed to initialize; hash fallback remains active"
                            .into(),
                    ),
                );
                return;
            }
            None => {
                set_embed_maintenance(
                    &status,
                    "timed_out",
                    0,
                    Some("local semantic model did not become ready within 120 seconds".into()),
                );
                return;
            }
        }

        set_embed_maintenance(&status, "running", 0, None);
        match store
            .memory_reindex_embeddings(initial.batch_limit, true)
            .await
        {
            Ok(updated) => set_embed_maintenance(&status, "complete", updated, None),
            Err(error) => set_embed_maintenance(&status, "failed", 0, Some(error.to_string())),
        }
    });
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

async fn prepare_daemon_http_with_binder<B, F>(
    store: Arc<dyn StateStore>,
    listen: &str,
    aura_config: AvatarAuraIoStartupConfig,
    mut bind: B,
) -> Result<(AppState, Vec<tokio::net::TcpListener>)>
where
    B: FnMut(String) -> F,
    F: Future<Output = std::io::Result<tokio::net::TcpListener>>,
{
    let addrs = parse_listen_addrs(listen);
    if addrs.is_empty() {
        anyhow::bail!("daemon-http listen address is empty: {listen:?}");
    }

    let state = prepare_app_state(store, aura_config).await?;
    let mut listeners = Vec::with_capacity(addrs.len());
    for addr in addrs {
        let listener = bind(addr.clone())
            .await
            .with_context(|| format!("bind {addr}"))?;
        let bound = listener
            .local_addr()
            .map(|address| address.to_string())
            .unwrap_or(addr);
        tracing::info!(addr = %bound, "agent-bridge daemon-http listening");
        listeners.push(listener);
    }
    Ok((state, listeners))
}

/// Run the HTTP daemon on one or more `listen` addresses. Pass a single
/// address (e.g. `0.0.0.0:7878`) for the legacy single-listener mode, or a
/// comma-separated list (e.g. `127.0.0.1:7878,100.91.146.24:7878`) to bind
/// loopback alongside a specific tailnet interface — strictly narrower than
/// `0.0.0.0` because public interfaces (WiFi, ethernet) are not bound.
/// Blocks until all listeners exit or the runtime is cancelled.
pub async fn run(store: Arc<dyn StateStore>, listen: &str) -> Result<()> {
    run_with_config(store, listen, AvatarAuraIoStartupConfig::disabled()).await
}

pub async fn run_with_config(
    store: Arc<dyn StateStore>,
    listen: &str,
    aura_config: AvatarAuraIoStartupConfig,
) -> Result<()> {
    let (state, listeners) =
        prepare_daemon_http_with_binder(store, listen, aura_config, |addr| async move {
            tokio::net::TcpListener::bind(addr).await
        })
        .await?;
    spawn_embed_readiness_maintenance(&state);
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
            "/avatar-surface/linux-renderer-state",
            get(avatar_linux_renderer_state),
        )
        .route("/avatar-surface/linux-renderer", get(avatar_linux_renderer))
        .route(
            "/avatar-surface/pet-spritesheet",
            get(avatar_pet_spritesheet),
        )
        .route(
            "/avatar-surface/sidecar-spritesheet",
            get(avatar_sidecar_spritesheet),
        )
        .route(
            "/avatar-surface/cortex-review-gate",
            get(avatar_cortex_review_gate),
        )
        .route(
            "/avatar-surface/cortex-review-packet",
            get(avatar_cortex_review_packet),
        )
        .route(
            "/avatar-surface/cortex-review-report",
            get(avatar_cortex_review_report),
        )
        .route(
            "/avatar-surface/cortex-review-decisions",
            get(avatar_cortex_review_decisions),
        )
        .route(
            "/avatar-surface/cortex-review-decision",
            post(avatar_cortex_review_decision),
        )
        .route("/avatar-surface/cortex-preview", get(avatar_cortex_preview))
        .route(
            "/avatar-surface/cortex-voice-policy",
            get(avatar_cortex_voice_policy),
        )
        .route(
            "/avatar-surface/cortex-voice-request",
            get(avatar_cortex_voice_request),
        )
        .route(
            "/avatar-surface/cortex-voice-confirm",
            get(avatar_cortex_voice_confirm),
        )
        .route(
            "/avatar-surface/cortex-voice-action-preview",
            get(avatar_cortex_voice_action_preview),
        )
        .route(
            "/avatar-surface/xiao-shu-action-request",
            get(xiao_shu_action_request),
        )
        .route(
            "/avatar-surface/xiao-shu-action-requests",
            get(xiao_shu_action_requests),
        )
        .route(
            "/avatar-surface/xiao-shu-action-console",
            get(xiao_shu_action_console),
        )
        .route(
            "/avatar-surface/cortex-voice-gate",
            get(avatar_cortex_voice_gate),
        )
        .route("/identity", get(identity_endpoint))
        .route("/embed", post(embed_endpoint))
        .route("/embed/readiness", get(embed_readiness_endpoint))
        .route("/agent/messages", post(agent_message_write))
        .route("/agent/inbox", get(agent_inbox_read))
        .route(
            "/semantic-bus/runtime-conformance",
            get(semantic_bus_runtime_conformance_endpoint),
        )
        .with_state(state);

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

#[derive(Deserialize, Debug, Default)]
struct SemanticBusRuntimeConformanceQuery {
    cwd: Option<String>,
    include_runtime_health: Option<bool>,
    daemon_http_url: Option<String>,
    palace_url: Option<String>,
    timeout_ms: Option<u64>,
}

async fn semantic_bus_runtime_conformance_endpoint(
    Query(q): Query<SemanticBusRuntimeConformanceQuery>,
) -> Json<Value> {
    let mut args = serde_json::Map::new();
    if let Some(cwd) = q.cwd.filter(|s| !s.trim().is_empty()) {
        args.insert("cwd".into(), json!(cwd));
    }
    if let Some(include_runtime_health) = q.include_runtime_health {
        args.insert(
            "include_runtime_health".into(),
            json!(include_runtime_health),
        );
    }
    if let Some(daemon_http_url) = q.daemon_http_url.filter(|s| !s.trim().is_empty()) {
        args.insert("daemon_http_url".into(), json!(daemon_http_url));
    }
    if let Some(palace_url) = q.palace_url.filter(|s| !s.trim().is_empty()) {
        args.insert("palace_url".into(), json!(palace_url));
    }
    if let Some(timeout_ms) = q.timeout_ms {
        args.insert("timeout_ms".into(), json!(timeout_ms));
    }
    Json(crate::mcp_tools::semantic_bus_runtime_conformance_payload(&Value::Object(args)).await)
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
    aura_io: Option<String>,
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
    #[serde(default)]
    transparent: bool,
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
    variant: Option<String>,
    reason: Option<String>,
    #[serde(default)]
    confirm: bool,
}

#[derive(Deserialize, Debug)]
struct AvatarCortexReviewDecisionsQuery {
    label: Option<String>,
    heartbeat_label: Option<String>,
    project: Option<String>,
    output: Option<std::path::PathBuf>,
    track: Option<String>,
    decision: Option<String>,
    #[serde(default)]
    details: bool,
    limit: Option<usize>,
}

#[derive(Deserialize, Debug)]
struct AvatarCortexReviewDecisionRequest {
    label: Option<String>,
    heartbeat_label: Option<String>,
    project: Option<String>,
    output: Option<std::path::PathBuf>,
    actor: Option<String>,
    track: Option<String>,
    decision: Option<String>,
    note: Option<String>,
    evidence: Option<String>,
    #[serde(default)]
    confirm: bool,
    #[serde(default)]
    details: bool,
}

#[derive(Deserialize, Debug)]
struct AvatarPetSpritesheetQuery {
    pet_id: Option<String>,
}

#[derive(Deserialize, Debug)]
struct AvatarSidecarSpritesheetQuery {
    asset: Option<String>,
}

#[derive(Deserialize, Debug)]
struct AvatarCortexVoiceGateQuery {
    label: Option<String>,
    heartbeat_label: Option<String>,
    project: Option<String>,
    output: Option<std::path::PathBuf>,
    preview_text: Option<String>,
    #[serde(default)]
    enabled: bool,
    #[serde(default)]
    force: bool,
    #[serde(default = "default_avatar_voice_gate_cooldown_secs")]
    cooldown_secs: i64,
    reason: Option<String>,
}

#[derive(Deserialize, Debug)]
struct AvatarCortexVoiceActionPreviewQuery {
    label: Option<String>,
    heartbeat_label: Option<String>,
    project: Option<String>,
    output: Option<std::path::PathBuf>,
    track: Option<String>,
    reason: Option<String>,
    #[serde(default)]
    confirm: bool,
    #[serde(default)]
    force: bool,
    #[serde(default = "default_avatar_voice_gate_cooldown_secs")]
    cooldown_secs: i64,
    tts_voice: Option<String>,
    tts_rate: Option<u64>,
}

#[derive(Deserialize, Debug)]
struct XiaoShuActionRequestQuery {
    label: Option<String>,
    heartbeat_label: Option<String>,
    project: Option<String>,
    output: Option<std::path::PathBuf>,
    actor: Option<String>,
    intent: Option<String>,
    message: Option<String>,
    track: Option<String>,
    reason: Option<String>,
    #[serde(default)]
    confirm: bool,
    #[serde(default)]
    force: bool,
    #[serde(default)]
    details: bool,
    #[serde(default = "default_avatar_voice_gate_cooldown_secs")]
    cooldown_secs: i64,
    tts_voice: Option<String>,
    tts_rate: Option<u64>,
}

#[derive(Deserialize, Debug)]
struct XiaoShuActionRequestsQuery {
    project: Option<String>,
    request_id: Option<String>,
    state: Option<String>,
    #[serde(default)]
    all_states: bool,
    #[serde(default)]
    details: bool,
    limit: Option<usize>,
}

impl XiaoShuActionRequestsQuery {
    fn effective_limit(&self) -> usize {
        self.limit.unwrap_or(20).clamp(1, 500)
    }
}

impl AvatarCortexReviewDecisionsQuery {
    fn effective_limit(&self) -> usize {
        self.limit.unwrap_or(20).clamp(1, 500)
    }
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
    let cortex_review_report =
        crate::avatar_cortex::avatar_cortex_renderer_review_report_from_status_for_project(
            cortex.clone(),
            q.project.as_deref().unwrap_or("agent-bridge"),
        )
        .unwrap_or_else(|e| {
            json!({
                "surface": "avatar_cortex_renderer_review_report",
                "read_only": true,
                "writes_files": false,
                "persists_review_record": false,
                "review_report": {
                    "report_state": "error",
                    "packet_count": 0,
                    "ready_packet_count": 0,
                    "blocked_packet_count": 0,
                    "human_feedback_count": 0,
                    "voice_linkage_requested_count": 0,
                    "human_decision_count": 0,
                    "approved_count": 0,
                    "review_record_count": 0,
                    "html_route": "/avatar-surface/cortex-review-report",
                    "packet_route": "/avatar-surface/cortex-review-packet",
                    "summary": e.to_string(),
                    "acceptance": {
                        "ready_for_human_visual_review": false,
                        "ready_for_approval": false,
                        "can_promote_review_tracks": false,
                        "merge_without_human_review_allowed": false,
                        "records_persisted": false,
                    },
                    "items": []
                }
            })
        });
    let cortex_review_decisions = crate::avatar_cortex::avatar_cortex_renderer_review_decisions(
        &crate::avatar_cortex::AvatarCortexRendererReviewDecisionQueueOptions {
            label: None,
            heartbeat_label: None,
            project: q.project.as_deref(),
            output: None,
            track: None,
            decision: None,
            include_details: false,
            limit: 5,
        },
    )
    .unwrap_or_else(|e| {
        json!({
            "surface": "avatar_cortex_renderer_review_decisions",
            "read_only": true,
            "dry_run": true,
            "emits_audio": false,
            "writes_files": false,
            "writes_approval": false,
            "error": e.to_string(),
        })
    });
    let cortex_voice_policy =
        crate::avatar_cortex::avatar_cortex_voice_policy_from_status(cortex.clone());
    let cortex_voice_request = crate::avatar_cortex::avatar_cortex_voice_request_from_status(
        cortex.clone(),
        Some("xiao_shu::alert_peek::medium"),
        q.project.as_deref(),
        None,
    );
    let cortex_voice_confirm = crate::avatar_cortex::avatar_cortex_voice_confirm_from_status(
        cortex.clone(),
        Some("xiao_shu::alert_peek::medium"),
        q.project.as_deref(),
        Some("panel-dry-run"),
        false,
    );
    let cortex_voice_action_preview = crate::avatar_cortex::avatar_cortex_voice_action_preview(
        &crate::avatar_cortex::AvatarCortexVoiceActionPreviewOptions {
            label: None,
            heartbeat_label: None,
            project: q.project.as_deref(),
            output: None,
            requested_track: Some("xiao_shu::alert_peek::medium"),
            reason: Some("panel-dry-run"),
            confirm: true,
            force: false,
            cooldown_secs: default_avatar_voice_gate_cooldown_secs(),
            tts_voice: None,
            tts_rate: None,
        },
    )
    .unwrap_or_else(|e| {
        json!({
            "surface": "avatar_cortex_voice_action_preview",
            "read_only": true,
            "dry_run": true,
            "emits_audio": false,
            "error": e.to_string(),
        })
    });
    let xiao_shu_action_request = crate::avatar_cortex::xiao_shu_action_request(
        &crate::avatar_cortex::XiaoShuActionRequestOptions {
            label: None,
            heartbeat_label: None,
            project: q.project.as_deref(),
            output: None,
            actor: Some("panel"),
            intent: Some("voice_alert"),
            message: Some("show the operator a safe Xiao Shu action request"),
            requested_track: Some("xiao_shu::alert_peek::medium"),
            reason: Some("panel-dry-run"),
            confirm: false,
            force: false,
            cooldown_secs: default_avatar_voice_gate_cooldown_secs(),
            tts_voice: None,
            tts_rate: None,
            include_details: false,
        },
    )
    .unwrap_or_else(|e| {
        json!({
            "surface": "xiao_shu_action_request",
            "read_only": true,
            "dry_run": true,
            "emits_audio": false,
            "error": e.to_string(),
        })
    });
    let xiao_shu_action_requests = crate::avatar_cortex::xiao_shu_action_request_queue(
        &crate::avatar_cortex::XiaoShuActionRequestQueueOptions {
            project: q.project.as_deref(),
            request_id: None,
            state: None,
            include_all_states: false,
            include_details: false,
            limit: 5,
        },
    )
    .unwrap_or_else(|e| {
        json!({
            "surface": "xiao_shu_action_request_queue",
            "read_only": true,
            "dry_run": true,
            "emits_audio": false,
            "error": e.to_string(),
        })
    });
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
        &cortex_review_report,
        &cortex_review_decisions,
        &cortex_voice_policy,
        &cortex_voice_request,
        &cortex_voice_confirm,
        &cortex_voice_action_preview,
        &xiao_shu_action_request,
        &xiao_shu_action_requests,
        &report,
        unix_now(),
    )))
}

async fn avatar_heartbeat_health(
    State(s): State<AppState>,
    Query(q): Query<AvatarHeartbeatHealthQuery>,
) -> Result<Json<Value>, (StatusCode, String)> {
    crate::avatar_health::resolve_heartbeat_health_identity(
        q.label.as_deref(),
        q.project.as_deref(),
    )
    .map_err(|e| (StatusCode::BAD_REQUEST, e.to_string()))?;
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
        q.variant.as_deref(),
    )))
}

fn str_value(value: &Value, key: &str) -> Option<String> {
    value
        .get(key)
        .and_then(Value::as_str)
        .map(str::trim)
        .filter(|s| !s.is_empty())
        .map(ToString::to_string)
}

fn avatar_renderer_pet_id_from_entry(entry: Option<&Value>) -> String {
    entry
        .and_then(|value| str_value(value, "avatar_id"))
        .or_else(|| {
            entry.and_then(|value| {
                value
                    .get("compat_pet_state")
                    .and_then(|compat| str_value(compat, "pet_id"))
            })
        })
        .unwrap_or_else(crate::pet_state::default_pet_id)
}

async fn avatar_linux_renderer_payload(
    s: &AppState,
    q: &AvatarSurfaceQuery,
) -> Result<Value, (StatusCode, String)> {
    let aura_io_report = if q.aura_io.is_some() {
        let Some(report) = s.avatar_aura_io_default.as_deref() else {
            return Err((
                StatusCode::FORBIDDEN,
                "aura_io_file_access_disabled".to_string(),
            ));
        };
        if q.aura_io.as_deref() != Some("default") {
            return Err((StatusCode::FORBIDDEN, "aura_io_not_authorized".to_string()));
        }
        Some(report)
    } else {
        None
    };

    let avatars = avatar_surface_entries(s, q).await?;
    let projected = avatars.first();
    let pet_id = avatar_renderer_pet_id_from_entry(projected);
    let raw_pet = crate::pet_state::read_pet_state(&pet_id).map_err(internal_error)?;
    let raw_ref = raw_pet.as_ref();
    let project = q
        .project
        .clone()
        .or_else(|| projected.and_then(|value| str_value(value, "project")))
        .or_else(|| raw_ref.and_then(|value| str_value(value, "project")))
        .unwrap_or_else(|| "agent-bridge".to_string());
    let cwd = projected
        .and_then(|value| str_value(value, "cwd"))
        .or_else(|| raw_ref.and_then(|value| str_value(value, "cwd")));
    let scope = crate::avatar_renderer::RendererScope { project, cwd };
    let mut payload =
        crate::avatar_renderer::renderer_payload_from_sources_with_sanitized_aura_io_report(
            &scope,
            projected,
            raw_ref,
            aura_io_report,
        );
    payload["input"] = json!({
        "presence_avatar_count": avatars.len(),
        "pet_id": pet_id,
        "raw_pet_state_available": raw_ref.is_some(),
        "presence_project": q.project,
        "presence_role": q.role,
        "aura_io": q.aura_io,
        "max_idle_secs": q.effective_max_idle_secs(),
    });
    Ok(payload)
}

async fn avatar_linux_renderer_state(
    State(s): State<AppState>,
    Query(q): Query<AvatarSurfaceQuery>,
) -> Result<Json<Value>, (StatusCode, String)> {
    Ok(Json(avatar_linux_renderer_payload(&s, &q).await?))
}

async fn avatar_linux_renderer(
    State(s): State<AppState>,
    Query(q): Query<AvatarSurfaceQuery>,
) -> Result<Html<String>, (StatusCode, String)> {
    let payload = avatar_linux_renderer_payload(&s, &q).await?;
    let state_href = avatar_linux_renderer_state_href(&q);
    Ok(Html(avatar_surface_linux_renderer_html(
        &payload,
        unix_now(),
        &state_href,
        q.transparent,
    )))
}

fn append_query_param(href: &mut String, sep: &mut &str, key: &str, value: &str) {
    if value.trim().is_empty() {
        return;
    }
    href.push_str(sep);
    href.push_str(key);
    href.push('=');
    href.push_str(&url_query_component(value));
    *sep = "&";
}

fn avatar_linux_renderer_state_href(q: &AvatarSurfaceQuery) -> String {
    let mut href = "/avatar-surface/linux-renderer-state".to_string();
    let mut sep = "?";
    if let Some(project) = q.project.as_deref() {
        append_query_param(&mut href, &mut sep, "project", project);
    }
    if let Some(role) = q.role.as_deref() {
        append_query_param(&mut href, &mut sep, "role", role);
    }
    if q.aura_io.as_deref() == Some("default") {
        append_query_param(&mut href, &mut sep, "aura_io", "default");
    }
    if q.include_stale {
        append_query_param(&mut href, &mut sep, "include_stale", "true");
    } else if q.max_idle_secs != default_max_idle() {
        append_query_param(
            &mut href,
            &mut sep,
            "max_idle_secs",
            &q.max_idle_secs.to_string(),
        );
    }
    if q.limit != default_limit() {
        append_query_param(&mut href, &mut sep, "limit", &q.limit.to_string());
    }
    if q.transparent {
        append_query_param(&mut href, &mut sep, "transparent", "true");
    }
    href
}

fn avatar_pet_package_dir(pet_id: &str) -> Result<std::path::PathBuf, (StatusCode, String)> {
    match pet_id {
        "xiao-shu-dev" | "xiao-shu-v2" | "xiao-shu" => {}
        _ => {
            return Err((
                StatusCode::BAD_REQUEST,
                format!("unsupported pet_id: {pet_id}"),
            ));
        }
    }
    let home = std::env::var("HOME").map_err(|e| {
        (
            StatusCode::INTERNAL_SERVER_ERROR,
            format!("HOME is not available: {e}"),
        )
    })?;
    Ok(std::path::PathBuf::from(home)
        .join(".codex")
        .join("pets")
        .join(pet_id))
}

fn avatar_pet_spritesheet_content_type(path: &std::path::Path) -> &'static str {
    match path.extension().and_then(|ext| ext.to_str()) {
        Some("webp") => "image/webp",
        _ => "image/png",
    }
}

async fn avatar_pet_spritesheet(
    Query(q): Query<AvatarPetSpritesheetQuery>,
) -> Result<impl IntoResponse, (StatusCode, String)> {
    let pet_id = q.pet_id.as_deref().unwrap_or("xiao-shu-dev");
    let package_dir = avatar_pet_package_dir(pet_id)?;
    let manifest_path = package_dir.join("pet.json");
    let manifest_bytes = tokio::fs::read(&manifest_path).await.map_err(|e| {
        (
            StatusCode::NOT_FOUND,
            format!("read {}: {e}", manifest_path.display()),
        )
    })?;
    let manifest: Value = serde_json::from_slice(&manifest_bytes).map_err(|e| {
        (
            StatusCode::INTERNAL_SERVER_ERROR,
            format!("parse {}: {e}", manifest_path.display()),
        )
    })?;
    let sprite_name = manifest
        .get("spritesheetPath")
        .and_then(Value::as_str)
        .unwrap_or("spritesheet.png");
    let sprite_rel = std::path::Path::new(sprite_name);
    if sprite_rel.components().count() != 1 {
        return Err((
            StatusCode::BAD_REQUEST,
            format!("unsafe spritesheetPath in {pet_id}: {sprite_name}"),
        ));
    }
    let sprite_path = package_dir.join(sprite_rel);
    let content_type = avatar_pet_spritesheet_content_type(&sprite_path);
    let bytes = tokio::fs::read(&sprite_path).await.map_err(|e| {
        (
            StatusCode::NOT_FOUND,
            format!("read {}: {e}", sprite_path.display()),
        )
    })?;
    Ok(([(header::CONTENT_TYPE, content_type)], bytes))
}

fn avatar_sidecar_spritesheet_svg(asset: &str) -> Option<String> {
    if asset == "xiao-shu-canonical-peek-v3" {
        return avatar_sidecar_canonical_peek_v3_svg();
    }
    if asset == "xiao-shu-motion-canonical-peek-v4" {
        return avatar_sidecar_motion_canonical_peek_v4_svg();
    }
    if asset == "xiao-shu-motion-canonical-soft-bounce-v1"
        || asset == "xiao-shu-motion-canonical-idle-breathe-v1"
        || asset == "xiao-shu-motion-canonical-sorting-glow-v1"
        || asset == "xiao-shu-motion-canonical-sorting-glow-v2"
        || asset == "xiao-shu-motion-canonical-sorting-glow-v3"
        || asset == "xiao-shu-motion-canonical-look-sideways-v1"
        || asset == "xiao-shu-motion-canonical-look-sideways-v2"
    {
        return avatar_sidecar_baseline_motion_svg(asset);
    }
    if asset != "xiao-shu-alert-peek-v2" {
        return None;
    }

    use std::fmt::Write as _;

    struct Frame {
        col: i32,
        rise: i32,
        tilt: i32,
        scale: &'static str,
        eye_shift: i32,
        blink: bool,
        mouth: &'static str,
        left_arm: i32,
        right_arm: i32,
        cheek: &'static str,
    }

    let frames = [
        Frame {
            col: 0,
            rise: 58,
            tilt: -7,
            scale: "0.92",
            eye_shift: -2,
            blink: false,
            mouth: "small",
            left_arm: 18,
            right_arm: -18,
            cheek: "0.12",
        },
        Frame {
            col: 1,
            rise: 42,
            tilt: -10,
            scale: "0.96",
            eye_shift: -6,
            blink: false,
            mouth: "small",
            left_arm: 28,
            right_arm: -24,
            cheek: "0.18",
        },
        Frame {
            col: 2,
            rise: 24,
            tilt: -6,
            scale: "1.00",
            eye_shift: -4,
            blink: false,
            mouth: "open",
            left_arm: 40,
            right_arm: -28,
            cheek: "0.24",
        },
        Frame {
            col: 3,
            rise: 8,
            tilt: 0,
            scale: "1.03",
            eye_shift: 0,
            blink: false,
            mouth: "smile",
            left_arm: 58,
            right_arm: -38,
            cheek: "0.30",
        },
        Frame {
            col: 4,
            rise: -2,
            tilt: 5,
            scale: "1.04",
            eye_shift: 2,
            blink: false,
            mouth: "smile",
            left_arm: 72,
            right_arm: -44,
            cheek: "0.34",
        },
        Frame {
            col: 5,
            rise: 0,
            tilt: 2,
            scale: "1.04",
            eye_shift: 0,
            blink: true,
            mouth: "smile",
            left_arm: 64,
            right_arm: -40,
            cheek: "0.36",
        },
        Frame {
            col: 6,
            rise: 18,
            tilt: -4,
            scale: "1.00",
            eye_shift: -3,
            blink: false,
            mouth: "small",
            left_arm: 40,
            right_arm: -30,
            cheek: "0.24",
        },
        Frame {
            col: 7,
            rise: 46,
            tilt: -8,
            scale: "0.95",
            eye_shift: -1,
            blink: false,
            mouth: "small",
            left_arm: 22,
            right_arm: -22,
            cheek: "0.16",
        },
    ];

    let mut svg = String::new();
    svg.push_str(
        r##"<svg xmlns="http://www.w3.org/2000/svg" width="1536" height="1872" viewBox="0 0 1536 1872">
  <title>Xiao Shu alert peek sidecar v2 sprite atlas</title>
  <defs>
    <linearGradient id="xs-body" x1="0" x2="0" y1="0" y2="1">
      <stop offset="0" stop-color="#f0dfc8"/>
      <stop offset="1" stop-color="#d8e5d6"/>
    </linearGradient>
    <linearGradient id="xs-head" x1="0" x2="0" y1="0" y2="1">
      <stop offset="0" stop-color="#f2dec4"/>
      <stop offset="1" stop-color="#e0c8ac"/>
    </linearGradient>
    <filter id="xs-soft-shadow" x="-20%" y="-20%" width="140%" height="140%">
      <feDropShadow dx="0" dy="5" stdDeviation="4" flood-color="#26312f" flood-opacity="0.18"/>
    </filter>
  </defs>
"##,
    );

    for frame in frames {
        let x = frame.col * 192;
        let left_eye_x = 72 + frame.eye_shift;
        let right_eye_x = 120 + frame.eye_shift;
        let eyes = if frame.blink {
            format!(
                r##"<rect x="{left_eye_x}" y="93" width="18" height="5" rx="3" fill="#26312f"/>
      <rect x="{right_eye_x}" y="93" width="18" height="5" rx="3" fill="#26312f"/>"##
            )
        } else {
            format!(
                r##"<ellipse cx="{left_eye_x}" cy="93" rx="7" ry="13" fill="#26312f"/>
      <ellipse cx="{right_eye_x}" cy="93" rx="7" ry="13" fill="#26312f"/>"##
            )
        };
        let mouth = match frame.mouth {
            "open" => r##"<ellipse cx="96" cy="112" rx="9" ry="7" fill="#26312f"/>"##,
            "smile" => {
                r##"<path d="M79 108 Q96 121 113 108" fill="none" stroke="#26312f" stroke-width="5" stroke-linecap="round"/>"##
            }
            _ => {
                r##"<path d="M87 110 Q96 115 105 110" fill="none" stroke="#26312f" stroke-width="4" stroke-linecap="round"/>"##
            }
        };

        writeln!(
            svg,
            r##"  <g id="frame-{col}" transform="translate({x} 0)">
    <rect width="192" height="208" fill="none"/>
    <ellipse cx="96" cy="188" rx="54" ry="12" fill="#26312f" opacity="0.14"/>
    <g filter="url(#xs-soft-shadow)" transform="translate(96 118) scale({scale}) translate(-96 -118) translate(0 {rise})">
      <g transform="translate(96 94) rotate({tilt}) translate(-96 -94)">
        <ellipse cx="96" cy="154" rx="50" ry="43" fill="url(#xs-body)" stroke="#26312f" stroke-width="5"/>
        <path d="M58 133 C76 121 116 121 134 133" fill="none" stroke="#147a74" stroke-width="6" stroke-linecap="round"/>
        <g transform="translate(53 147) rotate({left_arm})">
          <ellipse cx="0" cy="0" rx="14" ry="29" fill="#ead7bd" stroke="#26312f" stroke-width="5"/>
        </g>
        <g transform="translate(139 147) rotate({right_arm})">
          <ellipse cx="0" cy="0" rx="14" ry="29" fill="#ead7bd" stroke="#26312f" stroke-width="5"/>
        </g>
        <path d="M42 82 C42 47 63 25 96 25 C129 25 150 47 150 82 C150 123 128 145 96 145 C64 145 42 123 42 82 Z" fill="url(#xs-head)" stroke="#26312f" stroke-width="5"/>
        <path d="M89 26 C100 6 126 10 124 34 C111 29 99 33 89 26 Z" fill="#d45f4c" stroke="#26312f" stroke-width="5" stroke-linejoin="round"/>
        {eyes}
        <ellipse cx="58" cy="112" rx="13" ry="7" fill="#d45f4c" opacity="{cheek}"/>
        <ellipse cx="134" cy="112" rx="13" ry="7" fill="#d45f4c" opacity="{cheek}"/>
        {mouth}
      </g>
    </g>
  </g>
"##,
            col = frame.col,
            x = x,
            scale = frame.scale,
            rise = frame.rise,
            tilt = frame.tilt,
            left_arm = frame.left_arm,
            right_arm = frame.right_arm,
            eyes = eyes,
            cheek = frame.cheek,
            mouth = mouth
        )
        .ok()?;
    }

    svg.push_str("</svg>\n");
    Some(svg)
}

fn avatar_sidecar_baseline_motion_svg(asset: &str) -> Option<String> {
    use std::fmt::Write as _;

    struct Frame {
        col: i32,
        rise: i32,
        tilt: i32,
        scale: &'static str,
        eye_shift: i32,
        blink: bool,
        mouth: &'static str,
        left_arm: i32,
        right_arm: i32,
        ribbon: i32,
        cheek: &'static str,
        aura: &'static str,
    }

    let (title, frames): (&str, Vec<Frame>) = match asset {
        "xiao-shu-motion-canonical-soft-bounce-v1" => (
            "Xiao Shu motion-canonical soft bounce sidecar v1 sprite atlas",
            vec![
                Frame {
                    col: 0,
                    rise: 8,
                    tilt: -1,
                    scale: "0.96",
                    eye_shift: 0,
                    blink: false,
                    mouth: "smile",
                    left_arm: 7,
                    right_arm: -7,
                    ribbon: -8,
                    cheek: "0.26",
                    aura: "0.00",
                },
                Frame {
                    col: 1,
                    rise: 6,
                    tilt: -2,
                    scale: "0.98",
                    eye_shift: 0,
                    blink: false,
                    mouth: "smile",
                    left_arm: 10,
                    right_arm: -10,
                    ribbon: -12,
                    cheek: "0.28",
                    aura: "0.00",
                },
                Frame {
                    col: 2,
                    rise: -8,
                    tilt: -3,
                    scale: "1.02",
                    eye_shift: 1,
                    blink: false,
                    mouth: "smile",
                    left_arm: 15,
                    right_arm: -14,
                    ribbon: -18,
                    cheek: "0.32",
                    aura: "0.00",
                },
                Frame {
                    col: 3,
                    rise: -24,
                    tilt: 2,
                    scale: "1.05",
                    eye_shift: 1,
                    blink: false,
                    mouth: "wide",
                    left_arm: 21,
                    right_arm: -20,
                    ribbon: 8,
                    cheek: "0.36",
                    aura: "0.00",
                },
                Frame {
                    col: 4,
                    rise: -18,
                    tilt: 3,
                    scale: "1.04",
                    eye_shift: 0,
                    blink: false,
                    mouth: "wide",
                    left_arm: 18,
                    right_arm: -18,
                    ribbon: 14,
                    cheek: "0.34",
                    aura: "0.00",
                },
                Frame {
                    col: 5,
                    rise: -4,
                    tilt: 1,
                    scale: "1.00",
                    eye_shift: 0,
                    blink: true,
                    mouth: "smile",
                    left_arm: 12,
                    right_arm: -12,
                    ribbon: 4,
                    cheek: "0.32",
                    aura: "0.00",
                },
                Frame {
                    col: 6,
                    rise: 5,
                    tilt: -2,
                    scale: "0.98",
                    eye_shift: 0,
                    blink: false,
                    mouth: "smile",
                    left_arm: 8,
                    right_arm: -8,
                    ribbon: -6,
                    cheek: "0.28",
                    aura: "0.00",
                },
                Frame {
                    col: 7,
                    rise: 8,
                    tilt: -1,
                    scale: "0.96",
                    eye_shift: 0,
                    blink: false,
                    mouth: "small",
                    left_arm: 6,
                    right_arm: -6,
                    ribbon: -8,
                    cheek: "0.24",
                    aura: "0.00",
                },
            ],
        ),
        "xiao-shu-motion-canonical-idle-breathe-v1" => (
            "Xiao Shu motion-canonical idle breathe sidecar v1 sprite atlas",
            vec![
                Frame {
                    col: 0,
                    rise: 8,
                    tilt: 0,
                    scale: "0.98",
                    eye_shift: 0,
                    blink: false,
                    mouth: "small",
                    left_arm: 4,
                    right_arm: -4,
                    ribbon: -4,
                    cheek: "0.20",
                    aura: "0.00",
                },
                Frame {
                    col: 1,
                    rise: 5,
                    tilt: -1,
                    scale: "0.99",
                    eye_shift: 0,
                    blink: false,
                    mouth: "small",
                    left_arm: 5,
                    right_arm: -5,
                    ribbon: -6,
                    cheek: "0.22",
                    aura: "0.00",
                },
                Frame {
                    col: 2,
                    rise: 2,
                    tilt: 0,
                    scale: "1.00",
                    eye_shift: 0,
                    blink: false,
                    mouth: "soft",
                    left_arm: 6,
                    right_arm: -6,
                    ribbon: 0,
                    cheek: "0.24",
                    aura: "0.00",
                },
                Frame {
                    col: 3,
                    rise: 0,
                    tilt: 1,
                    scale: "1.01",
                    eye_shift: 0,
                    blink: false,
                    mouth: "soft",
                    left_arm: 7,
                    right_arm: -7,
                    ribbon: 4,
                    cheek: "0.26",
                    aura: "0.00",
                },
                Frame {
                    col: 4,
                    rise: 3,
                    tilt: 0,
                    scale: "1.00",
                    eye_shift: 0,
                    blink: true,
                    mouth: "soft",
                    left_arm: 5,
                    right_arm: -5,
                    ribbon: 0,
                    cheek: "0.24",
                    aura: "0.00",
                },
                Frame {
                    col: 5,
                    rise: 6,
                    tilt: -1,
                    scale: "0.99",
                    eye_shift: 0,
                    blink: false,
                    mouth: "small",
                    left_arm: 4,
                    right_arm: -4,
                    ribbon: -4,
                    cheek: "0.22",
                    aura: "0.00",
                },
            ],
        ),
        "xiao-shu-motion-canonical-sorting-glow-v1" => (
            "Xiao Shu motion-canonical sorting glow sidecar v1 sprite atlas",
            vec![
                Frame {
                    col: 0,
                    rise: 5,
                    tilt: 0,
                    scale: "0.99",
                    eye_shift: 0,
                    blink: false,
                    mouth: "small",
                    left_arm: 4,
                    right_arm: -4,
                    ribbon: -4,
                    cheek: "0.22",
                    aura: "0.08",
                },
                Frame {
                    col: 1,
                    rise: 3,
                    tilt: -2,
                    scale: "1.00",
                    eye_shift: -2,
                    blink: false,
                    mouth: "soft",
                    left_arm: 9,
                    right_arm: -8,
                    ribbon: -10,
                    cheek: "0.24",
                    aura: "0.18",
                },
                Frame {
                    col: 2,
                    rise: 0,
                    tilt: -4,
                    scale: "1.02",
                    eye_shift: -4,
                    blink: false,
                    mouth: "small",
                    left_arm: 14,
                    right_arm: -12,
                    ribbon: -18,
                    cheek: "0.26",
                    aura: "0.32",
                },
                Frame {
                    col: 3,
                    rise: -2,
                    tilt: 3,
                    scale: "1.03",
                    eye_shift: 3,
                    blink: false,
                    mouth: "soft",
                    left_arm: -10,
                    right_arm: 16,
                    ribbon: 10,
                    cheek: "0.28",
                    aura: "0.45",
                },
                Frame {
                    col: 4,
                    rise: -4,
                    tilt: 1,
                    scale: "1.04",
                    eye_shift: 0,
                    blink: false,
                    mouth: "wide",
                    left_arm: 12,
                    right_arm: -12,
                    ribbon: 16,
                    cheek: "0.34",
                    aura: "0.62",
                },
                Frame {
                    col: 5,
                    rise: 0,
                    tilt: -1,
                    scale: "1.02",
                    eye_shift: 2,
                    blink: true,
                    mouth: "soft",
                    left_arm: 8,
                    right_arm: -8,
                    ribbon: 4,
                    cheek: "0.30",
                    aura: "0.40",
                },
                Frame {
                    col: 6,
                    rise: 3,
                    tilt: 2,
                    scale: "1.00",
                    eye_shift: -1,
                    blink: false,
                    mouth: "small",
                    left_arm: 5,
                    right_arm: -5,
                    ribbon: -3,
                    cheek: "0.24",
                    aura: "0.22",
                },
                Frame {
                    col: 7,
                    rise: 5,
                    tilt: 0,
                    scale: "0.99",
                    eye_shift: 0,
                    blink: false,
                    mouth: "small",
                    left_arm: 4,
                    right_arm: -4,
                    ribbon: -4,
                    cheek: "0.22",
                    aura: "0.10",
                },
            ],
        ),
        "xiao-shu-motion-canonical-sorting-glow-v2" => (
            "Xiao Shu motion-canonical sorting glow sidecar v2 sprite atlas",
            vec![
                Frame {
                    col: 0,
                    rise: 7,
                    tilt: 0,
                    scale: "0.98",
                    eye_shift: 0,
                    blink: false,
                    mouth: "small",
                    left_arm: 2,
                    right_arm: -2,
                    ribbon: -4,
                    cheek: "0.22",
                    aura: "0.12",
                },
                Frame {
                    col: 1,
                    rise: 4,
                    tilt: -5,
                    scale: "1.00",
                    eye_shift: -5,
                    blink: false,
                    mouth: "soft",
                    left_arm: 18,
                    right_arm: -12,
                    ribbon: -18,
                    cheek: "0.25",
                    aura: "0.28",
                },
                Frame {
                    col: 2,
                    rise: 1,
                    tilt: -9,
                    scale: "1.03",
                    eye_shift: -10,
                    blink: false,
                    mouth: "small",
                    left_arm: 28,
                    right_arm: -20,
                    ribbon: -32,
                    cheek: "0.28",
                    aura: "0.46",
                },
                Frame {
                    col: 3,
                    rise: -3,
                    tilt: 7,
                    scale: "1.04",
                    eye_shift: 8,
                    blink: false,
                    mouth: "soft",
                    left_arm: -20,
                    right_arm: 30,
                    ribbon: 26,
                    cheek: "0.30",
                    aura: "0.62",
                },
                Frame {
                    col: 4,
                    rise: -5,
                    tilt: 2,
                    scale: "1.06",
                    eye_shift: 0,
                    blink: false,
                    mouth: "wide",
                    left_arm: 30,
                    right_arm: -26,
                    ribbon: 36,
                    cheek: "0.36",
                    aura: "0.82",
                },
                Frame {
                    col: 5,
                    rise: -1,
                    tilt: -4,
                    scale: "1.03",
                    eye_shift: 6,
                    blink: true,
                    mouth: "soft",
                    left_arm: 18,
                    right_arm: -16,
                    ribbon: 14,
                    cheek: "0.32",
                    aura: "0.58",
                },
                Frame {
                    col: 6,
                    rise: 3,
                    tilt: 3,
                    scale: "1.00",
                    eye_shift: -2,
                    blink: false,
                    mouth: "small",
                    left_arm: 8,
                    right_arm: -8,
                    ribbon: -8,
                    cheek: "0.25",
                    aura: "0.30",
                },
                Frame {
                    col: 7,
                    rise: 7,
                    tilt: 0,
                    scale: "0.98",
                    eye_shift: 0,
                    blink: false,
                    mouth: "small",
                    left_arm: 2,
                    right_arm: -2,
                    ribbon: -4,
                    cheek: "0.22",
                    aura: "0.14",
                },
            ],
        ),
        "xiao-shu-motion-canonical-sorting-glow-v3" => (
            "Xiao Shu motion-canonical sorting glow sidecar v3 sprite atlas",
            vec![
                Frame {
                    col: 0,
                    rise: 7,
                    tilt: 0,
                    scale: "0.98",
                    eye_shift: 0,
                    blink: false,
                    mouth: "small",
                    left_arm: 2,
                    right_arm: -2,
                    ribbon: -4,
                    cheek: "0.22",
                    aura: "0.10",
                },
                Frame {
                    col: 1,
                    rise: 5,
                    tilt: -4,
                    scale: "1.00",
                    eye_shift: -5,
                    blink: false,
                    mouth: "soft",
                    left_arm: 14,
                    right_arm: -8,
                    ribbon: -18,
                    cheek: "0.25",
                    aura: "0.36",
                },
                Frame {
                    col: 2,
                    rise: 1,
                    tilt: -8,
                    scale: "1.03",
                    eye_shift: -10,
                    blink: false,
                    mouth: "small",
                    left_arm: 30,
                    right_arm: -16,
                    ribbon: -34,
                    cheek: "0.28",
                    aura: "0.58",
                },
                Frame {
                    col: 3,
                    rise: -2,
                    tilt: 8,
                    scale: "1.04",
                    eye_shift: 9,
                    blink: false,
                    mouth: "soft",
                    left_arm: -18,
                    right_arm: 32,
                    ribbon: 28,
                    cheek: "0.30",
                    aura: "0.70",
                },
                Frame {
                    col: 4,
                    rise: -6,
                    tilt: 1,
                    scale: "1.06",
                    eye_shift: 0,
                    blink: false,
                    mouth: "wide",
                    left_arm: 32,
                    right_arm: -28,
                    ribbon: 38,
                    cheek: "0.36",
                    aura: "0.94",
                },
                Frame {
                    col: 5,
                    rise: -1,
                    tilt: -5,
                    scale: "1.04",
                    eye_shift: 6,
                    blink: true,
                    mouth: "soft",
                    left_arm: 18,
                    right_arm: -18,
                    ribbon: 16,
                    cheek: "0.32",
                    aura: "0.64",
                },
                Frame {
                    col: 6,
                    rise: 3,
                    tilt: 3,
                    scale: "1.00",
                    eye_shift: -2,
                    blink: false,
                    mouth: "small",
                    left_arm: 8,
                    right_arm: -8,
                    ribbon: -8,
                    cheek: "0.25",
                    aura: "0.34",
                },
                Frame {
                    col: 7,
                    rise: 7,
                    tilt: 0,
                    scale: "0.98",
                    eye_shift: 0,
                    blink: false,
                    mouth: "small",
                    left_arm: 2,
                    right_arm: -2,
                    ribbon: -4,
                    cheek: "0.22",
                    aura: "0.12",
                },
            ],
        ),
        "xiao-shu-motion-canonical-look-sideways-v1" => (
            "Xiao Shu motion-canonical look sideways sidecar v1 sprite atlas",
            vec![
                Frame {
                    col: 0,
                    rise: 6,
                    tilt: 0,
                    scale: "0.99",
                    eye_shift: 0,
                    blink: false,
                    mouth: "small",
                    left_arm: 4,
                    right_arm: -4,
                    ribbon: -4,
                    cheek: "0.20",
                    aura: "0.00",
                },
                Frame {
                    col: 1,
                    rise: 5,
                    tilt: -2,
                    scale: "1.00",
                    eye_shift: -3,
                    blink: false,
                    mouth: "small",
                    left_arm: 5,
                    right_arm: -8,
                    ribbon: -10,
                    cheek: "0.22",
                    aura: "0.00",
                },
                Frame {
                    col: 2,
                    rise: 4,
                    tilt: -5,
                    scale: "1.01",
                    eye_shift: -6,
                    blink: false,
                    mouth: "soft",
                    left_arm: 6,
                    right_arm: -14,
                    ribbon: -18,
                    cheek: "0.24",
                    aura: "0.00",
                },
                Frame {
                    col: 3,
                    rise: 3,
                    tilt: -7,
                    scale: "1.02",
                    eye_shift: -8,
                    blink: false,
                    mouth: "soft",
                    left_arm: 9,
                    right_arm: -17,
                    ribbon: -24,
                    cheek: "0.26",
                    aura: "0.00",
                },
                Frame {
                    col: 4,
                    rise: 4,
                    tilt: -5,
                    scale: "1.01",
                    eye_shift: -7,
                    blink: true,
                    mouth: "soft",
                    left_arm: 7,
                    right_arm: -14,
                    ribbon: -20,
                    cheek: "0.24",
                    aura: "0.00",
                },
                Frame {
                    col: 5,
                    rise: 5,
                    tilt: -2,
                    scale: "1.00",
                    eye_shift: -4,
                    blink: false,
                    mouth: "small",
                    left_arm: 5,
                    right_arm: -8,
                    ribbon: -10,
                    cheek: "0.22",
                    aura: "0.00",
                },
                Frame {
                    col: 6,
                    rise: 6,
                    tilt: 0,
                    scale: "0.99",
                    eye_shift: 0,
                    blink: false,
                    mouth: "small",
                    left_arm: 4,
                    right_arm: -4,
                    ribbon: -4,
                    cheek: "0.20",
                    aura: "0.00",
                },
            ],
        ),
        "xiao-shu-motion-canonical-look-sideways-v2" => (
            "Xiao Shu motion-canonical look sideways sidecar v2 sprite atlas",
            vec![
                Frame {
                    col: 0,
                    rise: 6,
                    tilt: 0,
                    scale: "0.98",
                    eye_shift: 0,
                    blink: false,
                    mouth: "small",
                    left_arm: 4,
                    right_arm: -4,
                    ribbon: -4,
                    cheek: "0.20",
                    aura: "0.00",
                },
                Frame {
                    col: 1,
                    rise: 5,
                    tilt: -5,
                    scale: "1.00",
                    eye_shift: -7,
                    blink: false,
                    mouth: "small",
                    left_arm: 3,
                    right_arm: -12,
                    ribbon: -20,
                    cheek: "0.22",
                    aura: "0.00",
                },
                Frame {
                    col: 2,
                    rise: 4,
                    tilt: -10,
                    scale: "1.02",
                    eye_shift: -14,
                    blink: false,
                    mouth: "soft",
                    left_arm: 2,
                    right_arm: -24,
                    ribbon: -38,
                    cheek: "0.24",
                    aura: "0.00",
                },
                Frame {
                    col: 3,
                    rise: 3,
                    tilt: -13,
                    scale: "1.03",
                    eye_shift: -18,
                    blink: false,
                    mouth: "soft",
                    left_arm: 0,
                    right_arm: -30,
                    ribbon: -44,
                    cheek: "0.27",
                    aura: "0.00",
                },
                Frame {
                    col: 4,
                    rise: 4,
                    tilt: -11,
                    scale: "1.02",
                    eye_shift: -16,
                    blink: true,
                    mouth: "soft",
                    left_arm: 1,
                    right_arm: -26,
                    ribbon: -40,
                    cheek: "0.24",
                    aura: "0.00",
                },
                Frame {
                    col: 5,
                    rise: 5,
                    tilt: -5,
                    scale: "1.00",
                    eye_shift: -8,
                    blink: false,
                    mouth: "small",
                    left_arm: 3,
                    right_arm: -14,
                    ribbon: -22,
                    cheek: "0.22",
                    aura: "0.00",
                },
                Frame {
                    col: 6,
                    rise: 6,
                    tilt: 0,
                    scale: "0.98",
                    eye_shift: 0,
                    blink: false,
                    mouth: "small",
                    left_arm: 4,
                    right_arm: -4,
                    ribbon: -4,
                    cheek: "0.20",
                    aura: "0.00",
                },
            ],
        ),
        _ => return None,
    };

    let mut svg = String::new();
    svg.push_str(&format!(
        r##"<svg xmlns="http://www.w3.org/2000/svg" width="1536" height="1872" viewBox="0 0 1536 1872">
  <title>{title}</title>
  <defs>
    <linearGradient id="xsb-head" x1="0" x2="0" y1="0" y2="1">
      <stop offset="0" stop-color="#f1d89f"/>
      <stop offset="0.62" stop-color="#e4bd76"/>
      <stop offset="1" stop-color="#b9803e"/>
    </linearGradient>
    <linearGradient id="xsb-robe" x1="0" x2="0" y1="0" y2="1">
      <stop offset="0" stop-color="#f0dfb8"/>
      <stop offset="1" stop-color="#cba35e"/>
    </linearGradient>
    <radialGradient id="xsb-process-glow" cx="50%" cy="50%" r="50%">
      <stop offset="0" stop-color="#56c6cc" stop-opacity="0.70"/>
      <stop offset="0.52" stop-color="#56c6cc" stop-opacity="0.28"/>
      <stop offset="1" stop-color="#56c6cc" stop-opacity="0"/>
    </radialGradient>
    <filter id="xsb-shadow" x="-24%" y="-24%" width="148%" height="148%">
      <feDropShadow dx="0" dy="5" stdDeviation="4" flood-color="#2d2018" flood-opacity="0.18"/>
    </filter>
  </defs>
"##,
        title = title
    ));

    for frame in frames {
        let x = frame.col * 192;
        let left_eye_x = 73 + frame.eye_shift;
        let right_eye_x = 119 + frame.eye_shift;
        let eyes = if frame.blink {
            format!(
                r##"<path d="M{left_eye_x} 92 h15" fill="none" stroke="#35251a" stroke-width="5" stroke-linecap="round"/>
      <path d="M{right_eye_x} 92 h15" fill="none" stroke="#35251a" stroke-width="5" stroke-linecap="round"/>"##
            )
        } else {
            format!(
                r##"<ellipse cx="{left_eye_x}" cy="92" rx="7" ry="12" fill="#35251a"/>
      <ellipse cx="{right_eye_x}" cy="92" rx="7" ry="12" fill="#35251a"/>
      <circle cx="{left_eye_x}" cy="87" r="2" fill="#f8efd6"/>
      <circle cx="{right_eye_x}" cy="87" r="2" fill="#f8efd6"/>"##
            )
        };
        let mouth = match frame.mouth {
            "wide" => {
                r##"<path d="M78 107 Q96 123 114 107" fill="none" stroke="#35251a" stroke-width="5" stroke-linecap="round"/>"##
            }
            "soft" => {
                r##"<path d="M85 109 Q96 117 107 109" fill="none" stroke="#35251a" stroke-width="4.5" stroke-linecap="round"/>"##
            }
            "smile" => {
                r##"<path d="M81 108 Q96 120 111 108" fill="none" stroke="#35251a" stroke-width="4.5" stroke-linecap="round"/>"##
            }
            _ => {
                r##"<path d="M88 110 Q96 114 104 110" fill="none" stroke="#35251a" stroke-width="4" stroke-linecap="round"/>"##
            }
        };
        let sorting_signal_overlay = if asset == "xiao-shu-motion-canonical-sorting-glow-v3" {
            let signal_opacity = match frame.col {
                0 => "0.18",
                1 => "0.46",
                2 => "0.72",
                3 => "0.78",
                4 => "0.96",
                5 => "0.74",
                6 => "0.42",
                _ => "0.18",
            };
            let signal_rotation = match frame.col {
                1 => "-10",
                2 => "-22",
                3 => "18",
                4 => "0",
                5 => "13",
                6 => "-7",
                _ => "0",
            };
            let signal_y = match frame.col {
                2 => 126,
                3 => 130,
                4 => 120,
                5 => 126,
                _ => 132,
            };
            format!(
                r##"<g class="xsb-sorting-signals" opacity="{signal_opacity}" transform="rotate({signal_rotation} 96 122)">
          <path d="M58 {line_y} C74 {curve_y} 118 {curve_y} 134 {line_y}" fill="none" stroke="#2f9da4" stroke-width="3.5" stroke-linecap="round" stroke-dasharray="7 7"/>
          <rect x="58" y="{signal_y}" width="17" height="12" rx="4" fill="#f6d68f" stroke="#2f9da4" stroke-width="3" transform="rotate(-11 66 {signal_y})"/>
          <rect x="87" y="{middle_y}" width="18" height="13" rx="4" fill="#eaf5e8" stroke="#2f9da4" stroke-width="3"/>
          <rect x="118" y="{signal_y}" width="17" height="12" rx="4" fill="#f6d68f" stroke="#2f9da4" stroke-width="3" transform="rotate(11 126 {signal_y})"/>
          <circle cx="72" cy="{dot_y}" r="4" fill="#56c6cc" stroke="#3a291c" stroke-width="2"/>
          <circle cx="120" cy="{dot_y}" r="4" fill="#56c6cc" stroke="#3a291c" stroke-width="2"/>
        </g>"##,
                line_y = signal_y + 8,
                curve_y = signal_y - 7,
                middle_y = signal_y - 8,
                dot_y = signal_y + 24
            )
        } else {
            String::new()
        };

        writeln!(
            svg,
            r##"  <g id="frame-{col}" transform="translate({x} 0)">
    <rect width="192" height="208" fill="none"/>
    <ellipse cx="96" cy="190" rx="54" ry="12" fill="#2d2018" opacity="0.14"/>
    <g filter="url(#xsb-shadow)" transform="translate(96 118) scale({scale}) translate(-96 -118) translate(0 {rise})">
      <g transform="translate(96 96) rotate({tilt}) translate(-96 -96)">
        <g class="xsb-process-glow" opacity="{aura}">
          <circle cx="96" cy="129" r="60" fill="url(#xsb-process-glow)"/>
          <path d="M58 132 C76 117 115 117 134 132" fill="none" stroke="#56c6cc" stroke-width="5" stroke-linecap="round" stroke-dasharray="9 8"/>
          <circle cx="62" cy="128" r="4" fill="#56c6cc"/>
          <circle cx="132" cy="128" r="4" fill="#56c6cc"/>
        </g>
        <ellipse cx="96" cy="154" rx="51" ry="44" fill="url(#xsb-robe)" stroke="#3a291c" stroke-width="5"/>
        <path d="M58 133 C76 121 116 121 134 133" fill="none" stroke="#b94735" stroke-width="6" stroke-linecap="round"/>
        <path d="M72 132 L96 187 L120 132" fill="#ead9ad" stroke="#8f4a32" stroke-width="4" stroke-linejoin="round"/>
        <path d="M83 137 L108 163 L93 188" fill="none" stroke="#b94735" stroke-width="5" stroke-linecap="round" stroke-linejoin="round"/>
        <g transform="translate(53 148) rotate({left_arm})">
          <ellipse cx="0" cy="0" rx="14" ry="27" fill="#d4ad64" stroke="#3a291c" stroke-width="5"/>
          <ellipse cx="0" cy="-18" rx="8" ry="5" fill="#f0d59f" stroke="#3a291c" stroke-width="3"/>
        </g>
        <g transform="translate(139 148) rotate({right_arm})">
          <ellipse cx="0" cy="0" rx="14" ry="27" fill="#d4ad64" stroke="#3a291c" stroke-width="5"/>
          <ellipse cx="0" cy="-18" rx="8" ry="5" fill="#f0d59f" stroke="#3a291c" stroke-width="3"/>
        </g>
        <path d="M48 70 C48 43 67 27 96 27 C125 27 144 43 144 70 L144 90 C144 124 123 144 96 144 C69 144 48 124 48 90 Z" fill="url(#xsb-head)" stroke="#3a291c" stroke-width="5" stroke-linejoin="round"/>
        <path d="M73 31 C63 19 73 8 82 17 C90 26 79 38 65 33" fill="none" stroke="#9b6b32" stroke-width="5" stroke-linecap="round"/>
        <path d="M114 37 C130 21 154 29 152 52 C138 47 126 53 114 37 Z" fill="#b94735" stroke="#3a291c" stroke-width="4" stroke-linejoin="round" transform="rotate({ribbon} 134 42)"/>
        <circle cx="140" cy="61" r="6" fill="#56c6cc" stroke="#3a291c" stroke-width="3"/>
        {eyes}
        <ellipse cx="60" cy="112" rx="12" ry="7" fill="#c95f4a" opacity="{cheek}"/>
        <ellipse cx="132" cy="112" rx="12" ry="7" fill="#c95f4a" opacity="{cheek}"/>
        {mouth}
        {sorting_signal_overlay}
      </g>
    </g>
  </g>
"##,
            col = frame.col,
            x = x,
            scale = frame.scale,
            rise = frame.rise,
            tilt = frame.tilt,
            left_arm = frame.left_arm,
            right_arm = frame.right_arm,
            sorting_signal_overlay = sorting_signal_overlay,
            ribbon = frame.ribbon,
            eyes = eyes,
            cheek = frame.cheek,
            aura = frame.aura,
            mouth = mouth
        )
        .ok()?;
    }

    svg.push_str("</svg>\n");
    Some(svg)
}

fn avatar_sidecar_motion_canonical_peek_v4_svg() -> Option<String> {
    use std::fmt::Write as _;

    struct Frame {
        col: i32,
        rise: i32,
        tilt: i32,
        scale: &'static str,
        eye_shift: i32,
        blink: bool,
        mouth: &'static str,
        left_arm: i32,
        right_arm: i32,
        ribbon: i32,
        cheek: &'static str,
    }

    let frames = [
        Frame {
            col: 0,
            rise: 58,
            tilt: -7,
            scale: "0.92",
            eye_shift: -2,
            blink: false,
            mouth: "small",
            left_arm: 18,
            right_arm: -18,
            ribbon: -8,
            cheek: "0.12",
        },
        Frame {
            col: 1,
            rise: 42,
            tilt: -10,
            scale: "0.96",
            eye_shift: -6,
            blink: false,
            mouth: "small",
            left_arm: 28,
            right_arm: -24,
            ribbon: -18,
            cheek: "0.18",
        },
        Frame {
            col: 2,
            rise: 24,
            tilt: -6,
            scale: "1.00",
            eye_shift: -4,
            blink: false,
            mouth: "open",
            left_arm: 40,
            right_arm: -28,
            ribbon: -24,
            cheek: "0.24",
        },
        Frame {
            col: 3,
            rise: 8,
            tilt: 0,
            scale: "1.03",
            eye_shift: 0,
            blink: false,
            mouth: "smile",
            left_arm: 58,
            right_arm: -38,
            ribbon: -10,
            cheek: "0.30",
        },
        Frame {
            col: 4,
            rise: -2,
            tilt: 5,
            scale: "1.04",
            eye_shift: 2,
            blink: false,
            mouth: "smile",
            left_arm: 72,
            right_arm: -44,
            ribbon: 8,
            cheek: "0.34",
        },
        Frame {
            col: 5,
            rise: 0,
            tilt: 2,
            scale: "1.04",
            eye_shift: 0,
            blink: true,
            mouth: "smile",
            left_arm: 64,
            right_arm: -40,
            ribbon: 16,
            cheek: "0.36",
        },
        Frame {
            col: 6,
            rise: 18,
            tilt: -4,
            scale: "1.00",
            eye_shift: -3,
            blink: false,
            mouth: "small",
            left_arm: 40,
            right_arm: -30,
            ribbon: -5,
            cheek: "0.24",
        },
        Frame {
            col: 7,
            rise: 46,
            tilt: -8,
            scale: "0.95",
            eye_shift: -1,
            blink: false,
            mouth: "small",
            left_arm: 22,
            right_arm: -22,
            ribbon: -12,
            cheek: "0.16",
        },
    ];

    let mut svg = String::new();
    svg.push_str(
        r##"<svg xmlns="http://www.w3.org/2000/svg" width="1536" height="1872" viewBox="0 0 1536 1872">
  <title>Xiao Shu motion-canonical alert peek sidecar v4 sprite atlas</title>
  <defs>
    <linearGradient id="xs4-head" x1="0" x2="0" y1="0" y2="1">
      <stop offset="0" stop-color="#f1d89f"/>
      <stop offset="0.6" stop-color="#e4bd76"/>
      <stop offset="1" stop-color="#b9803e"/>
    </linearGradient>
    <linearGradient id="xs4-robe" x1="0" x2="0" y1="0" y2="1">
      <stop offset="0" stop-color="#f0dfb8"/>
      <stop offset="1" stop-color="#cba35e"/>
    </linearGradient>
    <filter id="xs4-shadow" x="-24%" y="-24%" width="148%" height="148%">
      <feDropShadow dx="0" dy="5" stdDeviation="4" flood-color="#2d2018" flood-opacity="0.20"/>
    </filter>
  </defs>
"##,
    );

    for frame in frames {
        let x = frame.col * 192;
        let left_eye_x = 72 + frame.eye_shift;
        let right_eye_x = 120 + frame.eye_shift;
        let eyes = if frame.blink {
            format!(
                r##"<path d="M{left_eye_x} 93 h16" fill="none" stroke="#35251a" stroke-width="5" stroke-linecap="round"/>
      <path d="M{right_eye_x} 93 h16" fill="none" stroke="#35251a" stroke-width="5" stroke-linecap="round"/>"##
            )
        } else {
            format!(
                r##"<ellipse cx="{left_eye_x}" cy="93" rx="7" ry="13" fill="#35251a"/>
      <ellipse cx="{right_eye_x}" cy="93" rx="7" ry="13" fill="#35251a"/>
      <circle cx="{left_eye_x}" cy="88" r="2" fill="#f8efd6"/>
      <circle cx="{right_eye_x}" cy="88" r="2" fill="#f8efd6"/>"##
            )
        };
        let mouth = match frame.mouth {
            "open" => r##"<ellipse cx="96" cy="112" rx="9" ry="7" fill="#35251a"/>"##,
            "smile" => {
                r##"<path d="M79 108 Q96 121 113 108" fill="none" stroke="#35251a" stroke-width="5" stroke-linecap="round"/>"##
            }
            _ => {
                r##"<path d="M87 110 Q96 115 105 110" fill="none" stroke="#35251a" stroke-width="4" stroke-linecap="round"/>"##
            }
        };

        writeln!(
            svg,
            r##"  <g id="frame-{col}" transform="translate({x} 0)">
    <rect width="192" height="208" fill="none"/>
    <ellipse cx="96" cy="188" rx="54" ry="12" fill="#2d2018" opacity="0.15"/>
    <g filter="url(#xs4-shadow)" transform="translate(96 118) scale({scale}) translate(-96 -118) translate(0 {rise})">
      <g transform="translate(96 94) rotate({tilt}) translate(-96 -94)">
        <ellipse cx="96" cy="154" rx="51" ry="44" fill="url(#xs4-robe)" stroke="#3a291c" stroke-width="5"/>
        <path d="M58 133 C76 121 116 121 134 133" fill="none" stroke="#b94735" stroke-width="6" stroke-linecap="round"/>
        <path d="M72 132 L96 187 L120 132" fill="#ead9ad" stroke="#8f4a32" stroke-width="4" stroke-linejoin="round"/>
        <path d="M83 137 L108 163 L93 188" fill="none" stroke="#b94735" stroke-width="5" stroke-linecap="round" stroke-linejoin="round"/>
        <circle cx="72" cy="160" r="3" fill="#8f6d38" opacity="0.8"/>
        <circle cx="122" cy="159" r="3" fill="#8f6d38" opacity="0.8"/>
        <g transform="translate(53 147) rotate({left_arm})">
          <ellipse cx="0" cy="0" rx="14" ry="29" fill="#d4ad64" stroke="#3a291c" stroke-width="5"/>
          <ellipse cx="0" cy="-19" rx="8" ry="6" fill="#f0d59f" stroke="#3a291c" stroke-width="3"/>
          <path d="M-7 0 L7 0" stroke="#8f4a32" stroke-width="3" stroke-linecap="round" opacity="0.72"/>
        </g>
        <g transform="translate(139 147) rotate({right_arm})">
          <ellipse cx="0" cy="0" rx="14" ry="29" fill="#d4ad64" stroke="#3a291c" stroke-width="5"/>
          <ellipse cx="0" cy="-19" rx="8" ry="6" fill="#f0d59f" stroke="#3a291c" stroke-width="3"/>
          <path d="M-7 0 L7 0" stroke="#8f4a32" stroke-width="3" stroke-linecap="round" opacity="0.72"/>
        </g>
        <path d="M42 82 C42 47 63 25 96 25 C129 25 150 47 150 82 C150 123 128 145 96 145 C64 145 42 123 42 82 Z" fill="url(#xs4-head)" stroke="#3a291c" stroke-width="5"/>
        <path d="M73 31 C63 19 73 8 82 17 C90 26 79 38 65 33" fill="none" stroke="#9b6b32" stroke-width="5" stroke-linecap="round"/>
        <path d="M112 35 C128 20 153 29 151 52 C137 47 125 52 112 35 Z" fill="#b94735" stroke="#3a291c" stroke-width="4" stroke-linejoin="round" transform="rotate({ribbon} 134 42)"/>
        <circle cx="140" cy="61" r="6" fill="#56c6cc" stroke="#3a291c" stroke-width="3"/>
        {eyes}
        <ellipse cx="58" cy="112" rx="13" ry="7" fill="#c95f4a" opacity="{cheek}"/>
        <ellipse cx="134" cy="112" rx="13" ry="7" fill="#c95f4a" opacity="{cheek}"/>
        {mouth}
      </g>
    </g>
  </g>
"##,
            col = frame.col,
            x = x,
            scale = frame.scale,
            rise = frame.rise,
            tilt = frame.tilt,
            left_arm = frame.left_arm,
            right_arm = frame.right_arm,
            ribbon = frame.ribbon,
            eyes = eyes,
            cheek = frame.cheek,
            mouth = mouth
        )
        .ok()?;
    }

    svg.push_str("</svg>\n");
    Some(svg)
}

fn avatar_sidecar_canonical_peek_v3_svg() -> Option<String> {
    use std::fmt::Write as _;

    struct Frame {
        col: i32,
        rise: i32,
        tilt: i32,
        scale: &'static str,
        eye_shift: i32,
        blink: bool,
        mouth: &'static str,
        left_sleeve: i32,
        right_sleeve: i32,
        sleeve_y: i32,
        hand_lift: i32,
        ribbon: i32,
        cheek: &'static str,
    }

    let frames = [
        Frame {
            col: 0,
            rise: 58,
            tilt: -7,
            scale: "0.92",
            eye_shift: -2,
            blink: false,
            mouth: "small",
            left_sleeve: -8,
            right_sleeve: 8,
            sleeve_y: 143,
            hand_lift: 0,
            ribbon: -8,
            cheek: "0.10",
        },
        Frame {
            col: 1,
            rise: 42,
            tilt: -10,
            scale: "0.96",
            eye_shift: -6,
            blink: false,
            mouth: "small",
            left_sleeve: -18,
            right_sleeve: 14,
            sleeve_y: 139,
            hand_lift: 0,
            ribbon: -18,
            cheek: "0.16",
        },
        Frame {
            col: 2,
            rise: 24,
            tilt: -6,
            scale: "1.00",
            eye_shift: -4,
            blink: false,
            mouth: "open",
            left_sleeve: -38,
            right_sleeve: 28,
            sleeve_y: 133,
            hand_lift: 1,
            ribbon: -24,
            cheek: "0.22",
        },
        Frame {
            col: 3,
            rise: 8,
            tilt: 0,
            scale: "1.03",
            eye_shift: 0,
            blink: false,
            mouth: "smile",
            left_sleeve: -62,
            right_sleeve: 46,
            sleeve_y: 126,
            hand_lift: 2,
            ribbon: -10,
            cheek: "0.30",
        },
        Frame {
            col: 4,
            rise: -2,
            tilt: 5,
            scale: "1.04",
            eye_shift: 2,
            blink: false,
            mouth: "smile",
            left_sleeve: -76,
            right_sleeve: 56,
            sleeve_y: 122,
            hand_lift: 2,
            ribbon: 8,
            cheek: "0.34",
        },
        Frame {
            col: 5,
            rise: 0,
            tilt: 2,
            scale: "1.04",
            eye_shift: 0,
            blink: true,
            mouth: "smile",
            left_sleeve: -70,
            right_sleeve: 50,
            sleeve_y: 124,
            hand_lift: 2,
            ribbon: 16,
            cheek: "0.36",
        },
        Frame {
            col: 6,
            rise: 18,
            tilt: -4,
            scale: "1.00",
            eye_shift: -3,
            blink: false,
            mouth: "small",
            left_sleeve: -44,
            right_sleeve: 30,
            sleeve_y: 133,
            hand_lift: 1,
            ribbon: -5,
            cheek: "0.24",
        },
        Frame {
            col: 7,
            rise: 46,
            tilt: -8,
            scale: "0.95",
            eye_shift: -1,
            blink: false,
            mouth: "small",
            left_sleeve: -12,
            right_sleeve: 10,
            sleeve_y: 141,
            hand_lift: 0,
            ribbon: -12,
            cheek: "0.16",
        },
    ];

    let mut svg = String::new();
    svg.push_str(
        r##"<svg xmlns="http://www.w3.org/2000/svg" width="1536" height="1872" viewBox="0 0 1536 1872">
  <title>Xiao Shu canonical alert peek sidecar v3 sprite atlas</title>
  <defs>
    <linearGradient id="xs3-head" x1="0" x2="0" y1="0" y2="1">
      <stop offset="0" stop-color="#f1d89f"/>
      <stop offset="0.58" stop-color="#e4bd76"/>
      <stop offset="1" stop-color="#b9803e"/>
    </linearGradient>
    <linearGradient id="xs3-robe" x1="0" x2="0" y1="0" y2="1">
      <stop offset="0" stop-color="#f0dfb8"/>
      <stop offset="1" stop-color="#cba35e"/>
    </linearGradient>
    <filter id="xs3-shadow" x="-25%" y="-25%" width="150%" height="150%">
      <feDropShadow dx="0" dy="5" stdDeviation="4" flood-color="#2d2018" flood-opacity="0.22"/>
    </filter>
  </defs>
"##,
    );

    for frame in frames {
        let x = frame.col * 192;
        let left_eye_x = 74 + frame.eye_shift;
        let right_eye_x = 119 + frame.eye_shift;
        let eyes = if frame.blink {
            format!(
                r##"<path d="M{left_eye_x} 92 h15" fill="none" stroke="#35251a" stroke-width="5" stroke-linecap="round"/>
      <path d="M{right_eye_x} 92 h15" fill="none" stroke="#35251a" stroke-width="5" stroke-linecap="round"/>"##
            )
        } else {
            format!(
                r##"<ellipse cx="{left_eye_x}" cy="91" rx="7" ry="12" fill="#35251a"/>
      <ellipse cx="{right_eye_x}" cy="91" rx="7" ry="12" fill="#35251a"/>
      <circle cx="{left_eye_x}" cy="86" r="2.2" fill="#f8efd6"/>
      <circle cx="{right_eye_x}" cy="86" r="2.2" fill="#f8efd6"/>"##
            )
        };
        let mouth = match frame.mouth {
            "open" => r##"<ellipse cx="96" cy="111" rx="8" ry="6" fill="#35251a"/>"##,
            "smile" => {
                r##"<path d="M82 108 Q96 119 110 108" fill="none" stroke="#35251a" stroke-width="4.5" stroke-linecap="round"/>"##
            }
            _ => {
                r##"<path d="M88 110 Q96 114 104 110" fill="none" stroke="#35251a" stroke-width="4" stroke-linecap="round"/>"##
            }
        };
        let sleeves = match frame.hand_lift {
            2 => r##"<path d="M60 146 C44 130 47 109 62 99 C72 111 76 132 68 151 Z" fill="#d4ad64" stroke="#3a291c" stroke-width="5" stroke-linejoin="round"/>
        <path d="M57 124 L69 119" stroke="#8f4a32" stroke-width="3" stroke-linecap="round" opacity="0.75"/>
        <ellipse cx="61" cy="100" rx="7" ry="5" fill="#f0d59f" stroke="#3a291c" stroke-width="3"/>
        <path d="M132 146 C150 130 147 109 132 99 C122 111 118 132 126 151 Z" fill="#d4ad64" stroke="#3a291c" stroke-width="5" stroke-linejoin="round"/>
        <path d="M135 124 L123 119" stroke="#8f4a32" stroke-width="3" stroke-linecap="round" opacity="0.75"/>
        <ellipse cx="131" cy="100" rx="7" ry="5" fill="#f0d59f" stroke="#3a291c" stroke-width="3"/>"##
                .to_string(),
            1 => r##"<path d="M58 150 C43 137 46 117 60 109 C70 119 74 137 68 154 Z" fill="#d4ad64" stroke="#3a291c" stroke-width="5" stroke-linejoin="round"/>
        <path d="M56 132 L68 128" stroke="#8f4a32" stroke-width="3" stroke-linecap="round" opacity="0.75"/>
        <ellipse cx="60" cy="111" rx="7" ry="5" fill="#f0d59f" stroke="#3a291c" stroke-width="3"/>
        <path d="M134 150 C149 137 146 117 132 109 C122 119 118 137 124 154 Z" fill="#d4ad64" stroke="#3a291c" stroke-width="5" stroke-linejoin="round"/>
        <path d="M136 132 L124 128" stroke="#8f4a32" stroke-width="3" stroke-linecap="round" opacity="0.75"/>
        <ellipse cx="132" cy="111" rx="7" ry="5" fill="#f0d59f" stroke="#3a291c" stroke-width="3"/>"##
                .to_string(),
            _ => format!(
                r##"<g transform="translate(54 {sleeve_y}) rotate({left_sleeve})">
          <path d="M0 -8 C-23 4 -31 34 -12 45 C8 53 23 20 18 -1 Z" fill="#d4ad64" stroke="#3a291c" stroke-width="5" stroke-linejoin="round"/>
          <path d="M-8 14 L13 23" stroke="#8f4a32" stroke-width="3" stroke-linecap="round" opacity="0.75"/>
          <ellipse cx="-12" cy="33" rx="7" ry="5" fill="#f0d59f" stroke="#3a291c" stroke-width="3"/>
        </g>
        <g transform="translate(138 {sleeve_y}) rotate({right_sleeve})">
          <path d="M0 -8 C23 4 31 34 12 45 C-8 53 -23 20 -18 -1 Z" fill="#d4ad64" stroke="#3a291c" stroke-width="5" stroke-linejoin="round"/>
          <path d="M8 14 L-13 23" stroke="#8f4a32" stroke-width="3" stroke-linecap="round" opacity="0.75"/>
          <ellipse cx="12" cy="33" rx="7" ry="5" fill="#f0d59f" stroke="#3a291c" stroke-width="3"/>
        </g>"##,
                sleeve_y = frame.sleeve_y,
                left_sleeve = frame.left_sleeve,
                right_sleeve = frame.right_sleeve
            ),
        };

        writeln!(
            svg,
            r##"  <g id="frame-{col}" transform="translate({x} 0)">
    <rect width="192" height="208" fill="none"/>
    <ellipse cx="96" cy="190" rx="54" ry="12" fill="#2d2018" opacity="0.16"/>
    <g filter="url(#xs3-shadow)" transform="translate(96 118) scale({scale}) translate(-96 -118) translate(0 {rise})">
      <g transform="translate(96 96) rotate({tilt}) translate(-96 -96)">
        <path d="M56 123 C66 110 126 110 136 123 L150 189 C132 198 60 198 42 189 Z" fill="url(#xs3-robe)" stroke="#3a291c" stroke-width="5" stroke-linejoin="round"/>
        <path d="M71 122 L96 188 L121 122" fill="#ead9ad" stroke="#8f4a32" stroke-width="4" stroke-linejoin="round"/>
        <path d="M62 134 C82 145 111 145 130 134" fill="none" stroke="#b94735" stroke-width="7" stroke-linecap="round"/>
        <path d="M83 136 L108 163 L93 188" fill="none" stroke="#b94735" stroke-width="5" stroke-linecap="round" stroke-linejoin="round"/>
        <circle cx="72" cy="160" r="3" fill="#8f6d38" opacity="0.8"/>
        <circle cx="122" cy="159" r="3" fill="#8f6d38" opacity="0.8"/>
        {sleeves}
        <path d="M51 66 C51 41 69 27 96 27 C123 27 141 41 141 66 L141 91 C141 124 122 144 96 144 C70 144 51 124 51 91 Z" fill="url(#xs3-head)" stroke="#3a291c" stroke-width="5" stroke-linejoin="round"/>
        <path d="M73 31 C63 19 73 8 82 17 C90 26 79 38 65 33" fill="none" stroke="#9b6b32" stroke-width="5" stroke-linecap="round"/>
        <path d="M115 38 C130 22 155 29 153 52 C139 47 127 53 115 38 Z" fill="#b94735" stroke="#3a291c" stroke-width="4" stroke-linejoin="round" transform="rotate({ribbon} 134 42)"/>
        <circle cx="140" cy="61" r="6" fill="#56c6cc" stroke="#3a291c" stroke-width="3"/>
        {eyes}
        <ellipse cx="60" cy="111" rx="12" ry="7" fill="#c95f4a" opacity="{cheek}"/>
        <ellipse cx="132" cy="111" rx="12" ry="7" fill="#c95f4a" opacity="{cheek}"/>
        {mouth}
      </g>
    </g>
  </g>
"##,
            col = frame.col,
            x = x,
            scale = frame.scale,
            rise = frame.rise,
            tilt = frame.tilt,
            sleeves = sleeves,
            ribbon = frame.ribbon,
            eyes = eyes,
            cheek = frame.cheek,
            mouth = mouth
        )
        .ok()?;
    }

    svg.push_str("</svg>\n");
    Some(svg)
}

fn avatar_sidecar_spritesheet_png(asset: &str) -> Option<&'static [u8]> {
    if asset == "xiao-shu-ai-alert-peek-v1" {
        return Some(include_bytes!(
            "../assets/xiao-shu-prototypes/xiao-shu-ai-alert-peek-v1-atlas.png"
        ));
    }
    if asset == "xiao-shu-ai-alert-peek-v2" {
        return Some(include_bytes!(
            "../assets/xiao-shu-prototypes/xiao-shu-ai-alert-peek-v2-atlas.png"
        ));
    }
    if asset == "xiao-shu-v3-alert-peek-sheet-v1" {
        return Some(include_bytes!(
            "../assets/xiao-shu-prototypes/xiao-shu-v3-alert-peek-sheet-v1-atlas.png"
        ));
    }
    if asset == "xiao-shu-v3-ai-alert-peek-v1" {
        return Some(include_bytes!(
            "../assets/xiao-shu-prototypes/xiao-shu-v3-ai-alert-peek-v1-atlas.png"
        ));
    }
    if asset == "xiao-shu-v3-ai-alert-peek-v2" {
        return Some(include_bytes!(
            "../assets/xiao-shu-prototypes/xiao-shu-v3-ai-alert-peek-v2-atlas.png"
        ));
    }
    if asset == "xiao-shu-v3-ai-alert-peek-v3" {
        return Some(include_bytes!(
            "../assets/xiao-shu-prototypes/xiao-shu-v3-ai-alert-peek-v3-atlas.png"
        ));
    }
    if asset == "xiao-shu-v3-ai-idle-breathe-v1" {
        return Some(include_bytes!(
            "../assets/xiao-shu-prototypes/xiao-shu-v3-ai-idle-breathe-v1-atlas.png"
        ));
    }
    if asset == "xiao-shu-v3-ai-soft-bounce-v1" {
        return Some(include_bytes!(
            "../assets/xiao-shu-prototypes/xiao-shu-v3-ai-soft-bounce-v1-atlas.png"
        ));
    }
    if asset == "xiao-shu-v3-ai-completion-nod-v1" {
        return Some(include_bytes!(
            "../assets/xiao-shu-prototypes/xiao-shu-v3-ai-completion-nod-v1-atlas.png"
        ));
    }
    if asset == "xiao-shu-v3-focus-wave-v1" {
        return Some(include_bytes!(
            "../assets/xiao-shu-prototypes/xiao-shu-v3-focus-wave-v1-atlas.png"
        ));
    }
    if asset == "xiao-shu-v3-focus-turn-left-v1" {
        return Some(include_bytes!(
            "../assets/xiao-shu-prototypes/xiao-shu-v3-focus-turn-left-v1-atlas.png"
        ));
    }
    if asset == "xiao-shu-v3-focus-turn-right-v1" {
        return Some(include_bytes!(
            "../assets/xiao-shu-prototypes/xiao-shu-v3-focus-turn-right-v1-atlas.png"
        ));
    }
    if asset == "xiao-shu-v3-focus-walk-left-v1" {
        return Some(include_bytes!(
            "../assets/xiao-shu-prototypes/xiao-shu-v3-focus-walk-left-v1-atlas.png"
        ));
    }
    if asset == "xiao-shu-v3-focus-walk-right-v1" {
        return Some(include_bytes!(
            "../assets/xiao-shu-prototypes/xiao-shu-v3-focus-walk-right-v1-atlas.png"
        ));
    }
    None
}

async fn avatar_sidecar_spritesheet(
    Query(q): Query<AvatarSidecarSpritesheetQuery>,
) -> Result<Response, (StatusCode, String)> {
    let asset = q.asset.as_deref().unwrap_or("xiao-shu-alert-peek-v2");
    if let Some(png) = avatar_sidecar_spritesheet_png(asset) {
        return Ok((
            [
                (header::CONTENT_TYPE, "image/png"),
                (header::CACHE_CONTROL, "no-store"),
            ],
            png.to_vec(),
        )
            .into_response());
    }
    let svg = avatar_sidecar_spritesheet_svg(asset).ok_or_else(|| {
        (
            StatusCode::NOT_FOUND,
            format!("unsupported sidecar spritesheet asset: {asset}"),
        )
    })?;
    Ok((
        [
            (header::CONTENT_TYPE, "image/svg+xml; charset=utf-8"),
            (header::CACHE_CONTROL, "no-store"),
        ],
        svg,
    )
        .into_response())
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

async fn avatar_cortex_review_report(
    Query(q): Query<AvatarCortexStatusQuery>,
) -> Result<Json<Value>, (StatusCode, String)> {
    let payload = crate::avatar_cortex::avatar_cortex_renderer_review_report(
        q.label.as_deref(),
        q.heartbeat_label.as_deref(),
        q.project.as_deref(),
        q.output.as_deref(),
    )
    .map_err(internal_error)?;
    Ok(Json(payload))
}

async fn avatar_cortex_review_decisions(
    Query(q): Query<AvatarCortexReviewDecisionsQuery>,
) -> Result<Json<Value>, (StatusCode, String)> {
    let opts = crate::avatar_cortex::AvatarCortexRendererReviewDecisionQueueOptions {
        label: q.label.as_deref(),
        heartbeat_label: q.heartbeat_label.as_deref(),
        project: q.project.as_deref(),
        output: q.output.as_deref(),
        track: q.track.as_deref(),
        decision: q.decision.as_deref(),
        include_details: q.details,
        limit: q.effective_limit(),
    };
    let payload = crate::avatar_cortex::avatar_cortex_renderer_review_decisions(&opts)
        .map_err(internal_error)?;
    Ok(Json(payload))
}

async fn avatar_cortex_review_decision(
    Json(q): Json<AvatarCortexReviewDecisionRequest>,
) -> Result<Json<Value>, (StatusCode, String)> {
    let opts = crate::avatar_cortex::AvatarCortexRendererReviewDecisionOptions {
        label: q.label.as_deref(),
        heartbeat_label: q.heartbeat_label.as_deref(),
        project: q.project.as_deref(),
        output: q.output.as_deref(),
        actor: q.actor.as_deref(),
        track: q.track.as_deref(),
        decision: q.decision.as_deref(),
        note: q.note.as_deref(),
        evidence: q.evidence.as_deref(),
        confirm: q.confirm,
        include_details: q.details,
    };
    let payload = crate::avatar_cortex::avatar_cortex_renderer_review_decision(&opts)
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

async fn avatar_cortex_voice_policy(
    Query(q): Query<AvatarCortexStatusQuery>,
) -> Result<Json<Value>, (StatusCode, String)> {
    let payload = crate::avatar_cortex::avatar_cortex_voice_policy(
        q.label.as_deref(),
        q.heartbeat_label.as_deref(),
        q.project.as_deref(),
        q.output.as_deref(),
    )
    .map_err(internal_error)?;
    Ok(Json(payload))
}

async fn avatar_cortex_voice_request(
    Query(q): Query<AvatarCortexStatusQuery>,
) -> Result<Json<Value>, (StatusCode, String)> {
    let payload = crate::avatar_cortex::avatar_cortex_voice_request(
        q.label.as_deref(),
        q.heartbeat_label.as_deref(),
        q.project.as_deref(),
        q.output.as_deref(),
        q.track.as_deref(),
        q.reason.as_deref(),
    )
    .map_err(internal_error)?;
    Ok(Json(payload))
}

async fn avatar_cortex_voice_confirm(
    Query(q): Query<AvatarCortexStatusQuery>,
) -> Result<Json<Value>, (StatusCode, String)> {
    let payload = crate::avatar_cortex::avatar_cortex_voice_confirm(
        q.label.as_deref(),
        q.heartbeat_label.as_deref(),
        q.project.as_deref(),
        q.output.as_deref(),
        q.track.as_deref(),
        q.reason.as_deref(),
        q.confirm,
    )
    .map_err(internal_error)?;
    Ok(Json(payload))
}

async fn avatar_cortex_voice_action_preview(
    Query(q): Query<AvatarCortexVoiceActionPreviewQuery>,
) -> Result<Json<Value>, (StatusCode, String)> {
    let opts = crate::avatar_cortex::AvatarCortexVoiceActionPreviewOptions {
        label: q.label.as_deref(),
        heartbeat_label: q.heartbeat_label.as_deref(),
        project: q.project.as_deref(),
        output: q.output.as_deref(),
        requested_track: q.track.as_deref(),
        reason: q.reason.as_deref(),
        confirm: q.confirm,
        force: q.force,
        cooldown_secs: q.cooldown_secs,
        tts_voice: q.tts_voice.as_deref(),
        tts_rate: q.tts_rate,
    };
    let payload =
        crate::avatar_cortex::avatar_cortex_voice_action_preview(&opts).map_err(internal_error)?;
    Ok(Json(payload))
}

async fn xiao_shu_action_request(
    Query(q): Query<XiaoShuActionRequestQuery>,
) -> Result<Json<Value>, (StatusCode, String)> {
    let opts = crate::avatar_cortex::XiaoShuActionRequestOptions {
        label: q.label.as_deref(),
        heartbeat_label: q.heartbeat_label.as_deref(),
        project: q.project.as_deref(),
        output: q.output.as_deref(),
        actor: q.actor.as_deref(),
        intent: q.intent.as_deref(),
        message: q.message.as_deref(),
        requested_track: q.track.as_deref(),
        reason: q.reason.as_deref(),
        confirm: q.confirm,
        force: q.force,
        cooldown_secs: q.cooldown_secs,
        tts_voice: q.tts_voice.as_deref(),
        tts_rate: q.tts_rate,
        include_details: q.details,
    };
    let payload = crate::avatar_cortex::xiao_shu_action_request(&opts).map_err(internal_error)?;
    Ok(Json(payload))
}

async fn xiao_shu_action_requests(
    Query(q): Query<XiaoShuActionRequestsQuery>,
) -> Result<Json<Value>, (StatusCode, String)> {
    let opts = crate::avatar_cortex::XiaoShuActionRequestQueueOptions {
        project: q.project.as_deref(),
        request_id: q.request_id.as_deref(),
        state: q.state.as_deref(),
        include_all_states: q.all_states,
        include_details: q.details,
        limit: q.effective_limit(),
    };
    let payload =
        crate::avatar_cortex::xiao_shu_action_request_queue(&opts).map_err(internal_error)?;
    Ok(Json(payload))
}

async fn xiao_shu_action_console(
    Query(q): Query<XiaoShuActionRequestsQuery>,
) -> Result<Html<String>, (StatusCode, String)> {
    let opts = crate::avatar_cortex::XiaoShuActionRequestQueueOptions {
        project: q.project.as_deref(),
        request_id: q.request_id.as_deref(),
        state: q.state.as_deref(),
        include_all_states: q.all_states,
        include_details: true,
        limit: q.effective_limit(),
    };
    let payload =
        crate::avatar_cortex::xiao_shu_action_request_queue(&opts).map_err(internal_error)?;
    Ok(Html(avatar_surface_xiao_shu_action_console_html(
        &payload, &q,
    )))
}

async fn avatar_cortex_voice_gate(
    Query(q): Query<AvatarCortexVoiceGateQuery>,
) -> Result<Json<Value>, (StatusCode, String)> {
    let opts = crate::avatar_cortex::AvatarCortexVoiceGateOptions {
        label: q.label.as_deref(),
        heartbeat_label: q.heartbeat_label.as_deref(),
        project: q.project.as_deref(),
        output: q.output.as_deref(),
        preview_text: q.preview_text.as_deref(),
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

/// Request body for `POST /embed`. Single text → one model-dependent vector. For
/// throughput callers we may later add a `batch` variant; v0 keeps the shape
/// minimal so non-Rust clients (Unity/C#, Unreal/C++, Godot/GDScript, web/JS)
/// can hit it with one POST per perception event.
#[derive(Deserialize, Debug)]
struct EmbedRequest {
    text: String,
}

async fn embed_readiness_endpoint(State(s): State<AppState>) -> Json<Value> {
    let configured_backend = s.embed_backend.name();
    let (model_state, semantic_ready) = if configured_backend == "fnv1a-hash-384" {
        ("hash_only", false)
    } else {
        match ab_store::vector::local_model_ready() {
            None => ("loading", false),
            Some(true) => ("ready", true),
            Some(false) => ("fallback", false),
        }
    };
    let maintenance = s
        .embed_maintenance
        .lock()
        .unwrap_or_else(|poisoned| poisoned.into_inner())
        .clone();
    Json(json!({
        "configured_backend": configured_backend,
        "configured_dim": s.embed_backend.dim(),
        "model_state": model_state,
        "semantic_ready": semantic_ready,
        "automatic_repair": {
            "phase": maintenance.phase,
            "batch_limit": maintenance.batch_limit,
            "updated": maintenance.updated,
            "detail": maintenance.detail,
        }
    }))
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
        let (name, dim) = embed_response_metadata(backend.name(), backend.dim(), &text, &v);
        (name, dim, v)
    })
    .await
    .map_err(internal_error)?;
    Ok(Json(json!({
        "embedding": vec,
        "backend": name,
        "dim": dim,
    })))
}

/// Report what actually produced the wire vector, not merely what the optional
/// ONNX backend was configured to produce. During cold start or model failure,
/// `OnnxBackend` deliberately returns the deterministic hash fallback; labelling
/// that 384d vector as gte/768 makes remote clients reject it and previously let
/// write paths persist dimension-mismatched rows under a false backend tag.
fn embed_response_metadata(
    configured_name: &str,
    _configured_dim: usize,
    text: &str,
    vector: &[f32],
) -> (String, usize) {
    let actual_dim = vector.len();
    if configured_name != "fnv1a-hash-384" && vector == HashBackend.embed(text).as_slice() {
        ("fnv1a-hash-384".to_string(), actual_dim)
    } else {
        (configured_name.to_string(), actual_dim)
    }
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

fn avatar_surface_renderer_default_variant(track: &Value) -> Option<&Value> {
    let variants = track.get("semantic_variants").and_then(Value::as_array)?;
    variants
        .iter()
        .find(|variant| {
            variant
                .get("default")
                .and_then(Value::as_bool)
                .unwrap_or(false)
        })
        .or_else(|| variants.first())
}

fn avatar_surface_renderer_variant_choreography(variant: &Value) -> Option<&Value> {
    variant
        .get("frame_choreography")
        .filter(|choreography| choreography.is_object())
}

fn avatar_surface_renderer_i64(value: Option<&Value>) -> Option<i64> {
    match value {
        Some(Value::Number(n)) => n.as_i64().or_else(|| n.as_u64().map(|v| v as i64)),
        Some(Value::String(s)) => s.parse::<i64>().ok(),
        _ => None,
    }
}

fn avatar_surface_renderer_track_display_metrics(track: &Value) -> (String, String) {
    if let Some(choreography) = avatar_surface_renderer_default_variant(track)
        .and_then(avatar_surface_renderer_variant_choreography)
    {
        if let Some(frames) = choreography
            .get("frames")
            .and_then(Value::as_array)
            .map(|frames| frames.len())
            .filter(|frames| *frames > 0)
        {
            let duration = avatar_surface_renderer_i64(choreography.get("duration_ms"))
                .or_else(|| avatar_surface_renderer_i64(track.get("duration_ms")))
                .unwrap_or(0);
            return (frames.to_string(), duration.to_string());
        }
    }

    (
        avatar_surface_html_json_value(track.get("frame_count"), "0"),
        avatar_surface_html_json_value(track.get("duration_ms"), "0"),
    )
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
    let configured_sync =
        avatar_surface_html_json_value(binary.get("configured_sync_presence"), "false");
    let sync = avatar_surface_html_json_value(binary.get("supports_sync_presence"), "unknown");
    let health_cmd =
        avatar_surface_html_json_value(binary.get("supports_heartbeat_health"), "unknown");
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
        <div><dt>commands</dt><dd>configured_sync={configured_sync} support_sync={sync} health={health_cmd}</dd></div>
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

fn avatar_surface_review_report_html(
    review_report_preview: &Value,
    q: &AvatarSurfaceQuery,
) -> String {
    let report = review_report_preview
        .get("review_report")
        .unwrap_or(&Value::Null);
    let route_raw = report
        .get("html_route")
        .and_then(Value::as_str)
        .unwrap_or("/avatar-surface/cortex-review-report");
    let packet_route_raw = report
        .get("packet_route")
        .and_then(Value::as_str)
        .unwrap_or("/avatar-surface/cortex-review-packet");
    let href_raw = avatar_surface_route_href(route_raw, q.project.as_deref(), None);
    let packet_href_raw = avatar_surface_route_href(packet_route_raw, q.project.as_deref(), None);
    let href = html_escape(&href_raw);
    let packet_href = html_escape(&packet_href_raw);
    let state = avatar_surface_html_json_value(report.get("report_state"), "-");
    let packets = avatar_surface_html_json_value(report.get("packet_count"), "0");
    let ready = avatar_surface_html_json_value(report.get("ready_packet_count"), "0");
    let blocked = avatar_surface_html_json_value(report.get("blocked_packet_count"), "0");
    let feedback = avatar_surface_html_json_value(report.get("human_feedback_count"), "0");
    let voice_requests =
        avatar_surface_html_json_value(report.get("voice_linkage_requested_count"), "0");
    let human_decisions = avatar_surface_html_json_value(report.get("human_decision_count"), "0");
    let approved_count = avatar_surface_html_json_value(report.get("approved_count"), "0");
    let review_records = avatar_surface_html_json_value(report.get("review_record_count"), "0");
    let records_persisted = avatar_surface_html_json_value(
        report
            .get("acceptance")
            .and_then(|acceptance| acceptance.get("records_persisted")),
        "false",
    );
    let items = report.get("items").and_then(Value::as_array);
    let latest_record = items
        .and_then(|items| {
            items.iter().find_map(|item| {
                let record = item.get("latest_review_record")?;
                if !record.is_object() {
                    return None;
                }
                let token = item.get("token").and_then(Value::as_str).unwrap_or("-");
                let variant = record.get("variant").and_then(Value::as_str).unwrap_or("-");
                let outcome = record.get("outcome").and_then(Value::as_str).unwrap_or("-");
                Some(format!("{token} variant={variant} outcome={outcome}"))
            })
        })
        .unwrap_or_else(|| "-".to_string());
    let latest_record = html_escape(&latest_record);
    let record_command = items
        .and_then(|items| {
            items.iter().find_map(|item| {
                if item
                    .get("human_decision_present")
                    .and_then(Value::as_bool)
                    .unwrap_or(false)
                {
                    None
                } else {
                    item.get("review_record_command").and_then(Value::as_str)
                }
            })
        })
        .or_else(|| {
            items.and_then(|items| {
                items
                    .iter()
                    .find_map(|item| item.get("review_record_command").and_then(Value::as_str))
            })
        })
        .unwrap_or("-");
    let record_command = html_escape(record_command);
    let ready_for_human = avatar_surface_html_json_value(
        report
            .get("acceptance")
            .and_then(|acceptance| acceptance.get("ready_for_human_visual_review")),
        "false",
    );
    let ready_for_approval = avatar_surface_html_json_value(
        report
            .get("acceptance")
            .and_then(|acceptance| acceptance.get("ready_for_approval")),
        "false",
    );
    let can_promote = avatar_surface_html_json_value(
        report
            .get("acceptance")
            .and_then(|acceptance| acceptance.get("can_promote_review_tracks")),
        "false",
    );
    let merge_without_review = avatar_surface_html_json_value(
        report
            .get("acceptance")
            .and_then(|acceptance| acceptance.get("merge_without_human_review_allowed")),
        "false",
    );

    format!(
        r#"<section class="health status-fresh">
      <div class="health-title">
        <span class="pill status-fresh">report</span>
        <strong>Xiao Shu Review Report</strong>
        <span>state={state} packets={packets} ready={ready} blocked={blocked}</span>
      </div>
      <dl>
        <div><dt>readiness</dt><dd>human={ready_for_human} approval={ready_for_approval} decisions={human_decisions}</dd></div>
        <div><dt>records</dt><dd>approved={approved_count} records={review_records} persisted={records_persisted}</dd></div>
        <div><dt>latest</dt><dd>{latest_record}</dd></div>
        <div><dt>feedback</dt><dd>items={feedback} voice_requests={voice_requests}</dd></div>
        <div><dt>safety</dt><dd>can_promote={can_promote} merge_without_review={merge_without_review}</dd></div>
        <div><dt>next record</dt><dd><code>{record_command}</code></dd></div>
        <div><dt>packet</dt><dd><a href="{packet_href}">review packet json</a></dd></div>
        <div><dt>open</dt><dd><a href="{href}">review report json</a></dd></div>
      </dl>
    </section>"#,
        state = state,
        packets = packets,
        ready = ready,
        blocked = blocked,
        feedback = feedback,
        voice_requests = voice_requests,
        ready_for_human = ready_for_human,
        ready_for_approval = ready_for_approval,
        human_decisions = human_decisions,
        approved_count = approved_count,
        review_records = review_records,
        records_persisted = records_persisted,
        latest_record = latest_record,
        can_promote = can_promote,
        merge_without_review = merge_without_review,
        record_command = record_command,
        packet_href = packet_href,
        href = href,
    )
}

fn avatar_surface_review_decisions_html(
    review_decisions_preview: &Value,
    q: &AvatarSurfaceQuery,
) -> String {
    let ledger = review_decisions_preview
        .get("ledger")
        .unwrap_or(&Value::Null);
    let href_raw = avatar_surface_route_href(
        "/avatar-surface/cortex-review-decisions",
        q.project.as_deref(),
        None,
    );
    let exists = avatar_surface_html_json_value(ledger.get("exists"), "false");
    let matching = avatar_surface_html_json_value(ledger.get("matching_records"), "0");
    let returned = avatar_surface_html_json_value(ledger.get("returned_count"), "0");
    let latest = avatar_surface_html_json_value(ledger.get("latest_track_count"), "0");
    let parsed = avatar_surface_html_json_value(ledger.get("parsed_records"), "0");
    let path = avatar_surface_html_json_value(ledger.get("path"), "-");
    let writes_approval =
        avatar_surface_html_json_value(review_decisions_preview.get("writes_approval"), "false");
    let can_promote = avatar_surface_html_json_value(
        review_decisions_preview
            .get("acceptance")
            .and_then(|acceptance| acceptance.get("can_promote_review_tracks")),
        "false",
    );
    let mut rows = String::new();
    if let Some(records) = review_decisions_preview
        .get("records")
        .and_then(Value::as_array)
    {
        for record in records.iter().take(3) {
            rows.push_str(&format!(
                "<li><strong>{}</strong><span>track={} decision={} actor={}</span><span>approval={}</span></li>",
                avatar_surface_html_json_value(record.get("decision_id"), "-"),
                avatar_surface_html_json_value(record.get("track"), "-"),
                avatar_surface_html_json_value(record.get("decision"), "-"),
                avatar_surface_html_json_value(record.get("actor"), "-"),
                avatar_surface_html_json_value(record.get("approval_state"), "not_approved"),
            ));
        }
    }
    if rows.is_empty() {
        rows.push_str(
            "<li><strong>none</strong><span>no review decisions recorded yet</span></li>",
        );
    }

    format!(
        r#"<section class="health status-fresh">
      <div class="health-title">
        <span class="pill status-fresh">ledger</span>
        <strong>Xiao Shu Review Decisions</strong>
        <span>exists={exists} parsed={parsed} latest={latest}</span>
      </div>
      <dl>
        <div><dt>records</dt><dd>matching={matching} returned={returned}</dd></div>
        <div><dt>safety</dt><dd>writes_approval={writes_approval} can_promote={can_promote}</dd></div>
        <div><dt>path</dt><dd>{path}</dd></div>
        <div><dt>open</dt><dd><a href="{href}">review decisions json</a></dd></div>
      </dl>
      <ul class="event-list">{rows}</ul>
    </section>"#,
        exists = exists,
        parsed = parsed,
        latest = latest,
        matching = matching,
        returned = returned,
        writes_approval = writes_approval,
        can_promote = can_promote,
        path = path,
        href = html_escape(&href_raw),
        rows = rows,
    )
}

fn avatar_surface_voice_policy_html(
    voice_policy_preview: &Value,
    q: &AvatarSurfaceQuery,
) -> String {
    let policy = voice_policy_preview
        .get("voice_policy")
        .unwrap_or(&Value::Null);
    let route_raw = policy
        .get("html_route")
        .and_then(Value::as_str)
        .unwrap_or("/avatar-surface/cortex-voice-policy");
    let renderer_route_raw = policy
        .get("renderer_view_route")
        .and_then(Value::as_str)
        .unwrap_or("/avatar-surface/cortex-renderer-view");
    let href_raw = avatar_surface_route_href(route_raw, q.project.as_deref(), None);
    let renderer_href_raw =
        avatar_surface_route_href(renderer_route_raw, q.project.as_deref(), None);
    let tracks = avatar_surface_html_json_value(policy.get("track_count"), "0");
    let manual = avatar_surface_html_json_value(policy.get("manual_cli_emit_count"), "0");
    let display = avatar_surface_html_json_value(policy.get("display_only_count"), "0");
    let auto = avatar_surface_html_json_value(policy.get("auto_emit_count"), "0");
    let voice = avatar_surface_html_json_value(policy.get("default_voice"), "-");
    let rate = avatar_surface_html_json_value(policy.get("default_rate"), "-");
    let cooldown = avatar_surface_html_json_value(policy.get("default_cooldown_secs"), "300");
    let http_emit = avatar_surface_html_json_value(
        policy
            .get("acceptance")
            .and_then(|acceptance| acceptance.get("http_emit_route_added")),
        "false",
    );
    let mut first_manual = "-".to_string();
    if let Some(rule) = policy
        .get("rules")
        .and_then(Value::as_array)
        .and_then(|rules| {
            rules.iter().find(|rule| {
                rule.get("manual_cli_emit_allowed")
                    .and_then(Value::as_bool)
                    .unwrap_or(false)
            })
        })
    {
        first_manual = format!(
            "{} cue={} line={}",
            avatar_surface_html_json_value(rule.get("token"), "-"),
            avatar_surface_html_json_value(rule.get("cue_id"), "-"),
            avatar_surface_html_json_value(rule.get("utterance"), "-")
        );
    }

    format!(
        r#"<section class="health status-fresh">
      <div class="health-title">
        <span class="pill status-fresh">voice</span>
        <strong>Xiao Shu Voice Policy</strong>
        <span>tracks={tracks} manual_cli={manual} display_only={display} auto={auto}</span>
      </div>
      <dl>
        <div><dt>default</dt><dd>{voice} rate={rate} cooldown={cooldown}s</dd></div>
        <div><dt>first manual</dt><dd>{first_manual}</dd></div>
        <div><dt>safety</dt><dd>http_emit_route_added={http_emit} auto_emit={auto}</dd></div>
        <div><dt>renderer</dt><dd><a href="{renderer_href}">renderer view</a></dd></div>
        <div><dt>open</dt><dd><a href="{href}">voice policy json</a></dd></div>
      </dl>
    </section>"#,
        tracks = tracks,
        manual = manual,
        display = display,
        auto = auto,
        voice = voice,
        rate = rate,
        cooldown = cooldown,
        first_manual = first_manual,
        http_emit = http_emit,
        renderer_href = html_escape(&renderer_href_raw),
        href = html_escape(&href_raw),
    )
}

fn avatar_surface_voice_request_html(
    voice_request_preview: &Value,
    q: &AvatarSurfaceQuery,
) -> String {
    let request = voice_request_preview
        .get("voice_request")
        .unwrap_or(&Value::Null);
    let route_raw = request
        .get("html_route")
        .and_then(Value::as_str)
        .unwrap_or("/avatar-surface/cortex-voice-request");
    let policy_route_raw = request
        .get("policy_route")
        .and_then(Value::as_str)
        .unwrap_or("/avatar-surface/cortex-voice-policy");
    let selected_token = request
        .get("selected_token")
        .and_then(Value::as_str)
        .unwrap_or("xiao_shu::alert_peek::medium");
    let href_raw = avatar_surface_route_href(route_raw, q.project.as_deref(), Some(selected_token));
    let policy_href_raw = avatar_surface_route_href(policy_route_raw, q.project.as_deref(), None);
    let state = avatar_surface_html_json_value(request.get("request_state"), "-");
    let token = avatar_surface_html_json_value(request.get("selected_token"), "-");
    let manual = avatar_surface_html_json_value(request.get("manual_cli_emit_allowed"), "false");
    let auto = avatar_surface_html_json_value(request.get("auto_emit_allowed"), "false");
    let line = avatar_surface_html_json_value(request.get("line"), "-");
    let script = avatar_surface_html_json_value(
        request
            .get("voice_script")
            .and_then(|script| script.get("script_id")),
        "-",
    );
    let cue = avatar_surface_html_json_value(request.get("cue_id"), "-");
    let message_policy = avatar_surface_html_json_value(
        request
            .get("caller_message_policy")
            .and_then(|policy| policy.get("message_can_replace_utterance")),
        "false",
    );
    let voice = avatar_surface_html_json_value(request.get("suggested_voice"), "-");
    let rate = avatar_surface_html_json_value(request.get("suggested_rate"), "-");
    let reason = avatar_surface_html_json_value(request.get("operator_reason_present"), "false");
    let second_step = avatar_surface_html_json_value(request.get("requires_second_step"), "true");
    let http_emit = avatar_surface_html_json_value(request.get("http_emit_route"), "null");

    format!(
        r#"<section class="health status-fresh">
      <div class="health-title">
        <span class="pill status-fresh">request</span>
        <strong>Xiao Shu Voice Request</strong>
        <span>state={state} token={token}</span>
      </div>
      <dl>
        <div><dt>line</dt><dd>{line}</dd></div>
        <div><dt>script</dt><dd>{script} cue={cue} llm_replace_line={message_policy}</dd></div>
        <div><dt>voice</dt><dd>{voice} rate={rate}</dd></div>
        <div><dt>confirm</dt><dd>manual_cli={manual} second_step={second_step} reason_present={reason}</dd></div>
        <div><dt>safety</dt><dd>auto_emit={auto} http_emit_route={http_emit}</dd></div>
        <div><dt>policy</dt><dd><a href="{policy_href}">voice policy json</a></dd></div>
        <div><dt>open</dt><dd><a href="{href}">voice request json</a></dd></div>
      </dl>
    </section>"#,
        state = state,
        token = token,
        line = line,
        script = script,
        cue = cue,
        message_policy = message_policy,
        voice = voice,
        rate = rate,
        manual = manual,
        second_step = second_step,
        reason = reason,
        auto = auto,
        http_emit = http_emit,
        policy_href = html_escape(&policy_href_raw),
        href = html_escape(&href_raw),
    )
}

fn avatar_surface_voice_confirm_html(
    voice_confirm_preview: &Value,
    q: &AvatarSurfaceQuery,
) -> String {
    let confirm = voice_confirm_preview
        .get("voice_confirm")
        .unwrap_or(&Value::Null);
    let route_raw = confirm
        .get("html_route")
        .and_then(Value::as_str)
        .unwrap_or("/avatar-surface/cortex-voice-confirm");
    let request_route_raw = confirm
        .get("request_route")
        .and_then(Value::as_str)
        .unwrap_or("/avatar-surface/cortex-voice-request");
    let selected_token = confirm
        .get("selected_token")
        .and_then(Value::as_str)
        .unwrap_or("xiao_shu::alert_peek::medium");
    let mut href_raw =
        avatar_surface_route_href(route_raw, q.project.as_deref(), Some(selected_token));
    let sep = if href_raw.contains('?') { "&" } else { "?" };
    href_raw.push_str(sep);
    href_raw.push_str("confirm=true&reason=panel-dry-run");
    let request_href_raw = avatar_surface_route_href(
        request_route_raw,
        q.project.as_deref(),
        Some(selected_token),
    );
    let state = avatar_surface_html_json_value(confirm.get("confirmation_state"), "-");
    let token = avatar_surface_html_json_value(confirm.get("selected_token"), "-");
    let confirm_requested =
        avatar_surface_html_json_value(confirm.get("confirm_requested"), "false");
    let would_execute = avatar_surface_html_json_value(confirm.get("would_execute_cli"), "false");
    let reason = avatar_surface_html_json_value(confirm.get("operator_reason_present"), "false");
    let auto = avatar_surface_html_json_value(confirm.get("auto_emit_allowed"), "false");
    let http_emit = avatar_surface_html_json_value(confirm.get("http_emit_route"), "null");
    let line = avatar_surface_html_json_value(confirm.get("line"), "-");
    let voice = avatar_surface_html_json_value(confirm.get("suggested_voice"), "-");
    let rate = avatar_surface_html_json_value(confirm.get("suggested_rate"), "-");
    let actual_execution =
        avatar_surface_html_json_value(confirm.get("actual_execution_available_here"), "false");
    let command = avatar_surface_html_json_value(confirm.get("pending_command_preview"), "-");
    let action = avatar_surface_html_json_value(confirm.get("pending_action_command_preview"), "-");

    format!(
        r#"<section class="health status-fresh">
      <div class="health-title">
        <span class="pill status-fresh">confirm</span>
        <strong>Xiao Shu Voice Confirm</strong>
        <span>state={state} token={token}</span>
      </div>
      <dl>
        <div><dt>line</dt><dd>{line}</dd></div>
        <div><dt>voice</dt><dd>{voice} rate={rate}</dd></div>
        <div><dt>confirm</dt><dd>confirm={confirm_requested} would_execute_cli={would_execute} reason_present={reason}</dd></div>
        <div><dt>safety</dt><dd>auto_emit={auto} http_emit_route={http_emit} actual_execution_here={actual_execution}</dd></div>
        <div><dt>command</dt><dd>{command}</dd></div>
        <div><dt>action</dt><dd>{action}</dd></div>
        <div><dt>request</dt><dd><a href="{request_href}">voice request json</a></dd></div>
        <div><dt>open</dt><dd><a href="{href}">voice confirm json</a></dd></div>
      </dl>
    </section>"#,
        state = state,
        token = token,
        line = line,
        voice = voice,
        rate = rate,
        confirm_requested = confirm_requested,
        would_execute = would_execute,
        reason = reason,
        auto = auto,
        http_emit = http_emit,
        actual_execution = actual_execution,
        command = command,
        action = action,
        request_href = html_escape(&request_href_raw),
        href = html_escape(&href_raw),
    )
}

fn avatar_surface_voice_action_preview_html(
    voice_action_preview: &Value,
    q: &AvatarSurfaceQuery,
) -> String {
    let action = voice_action_preview
        .get("action_preview")
        .unwrap_or(&Value::Null);
    let selected_token = action
        .get("selected_token")
        .and_then(Value::as_str)
        .unwrap_or("xiao_shu::alert_peek::medium");
    let route_raw = "/avatar-surface/cortex-voice-action-preview";
    let mut href_raw =
        avatar_surface_route_href(route_raw, q.project.as_deref(), Some(selected_token));
    let sep = if href_raw.contains('?') { "&" } else { "?" };
    href_raw.push_str(sep);
    href_raw.push_str("confirm=true&reason=panel-dry-run");
    let state = avatar_surface_html_json_value(action.get("confirmation_state"), "-");
    let ready = avatar_surface_html_json_value(action.get("ready_to_emit_now"), "false");
    let would =
        avatar_surface_html_json_value(action.get("would_emit_if_operator_runs_command"), "false");
    let blocked = avatar_surface_html_json_value(action.get("blocked"), "true");
    let reasons = html_escape(
        &action
            .get("blocked_reasons")
            .map(Value::to_string)
            .unwrap_or_else(|| "[]".to_string()),
    );
    let token = avatar_surface_html_json_value(action.get("selected_token"), "-");
    let line = avatar_surface_html_json_value(action.get("line"), "-");
    let voice = avatar_surface_html_json_value(action.get("tts_voice"), "-");
    let rate = avatar_surface_html_json_value(action.get("tts_rate"), "-");
    let cooldown = avatar_surface_html_json_value(action.get("cooldown_secs"), "300");
    let state_path = avatar_surface_html_json_value(action.get("state_path"), "-");
    let command = avatar_surface_html_json_value(action.get("command_preview"), "-");
    let gate = voice_action_preview
        .get("gate_dry_run")
        .unwrap_or(&Value::Null);
    let cooldown_block = gate.get("cooldown").unwrap_or(&Value::Null);
    let cooldown_active = avatar_surface_html_json_value(cooldown_block.get("active"), "false");
    let next_allowed = avatar_surface_html_json_value(cooldown_block.get("next_allowed_at"), "-");

    format!(
        r#"<section class="health status-fresh">
      <div class="health-title">
        <span class="pill status-fresh">action</span>
        <strong>Xiao Shu Voice Action Preview</strong>
        <span>state={state} ready={ready} token={token}</span>
      </div>
      <dl>
        <div><dt>line</dt><dd>{line}</dd></div>
        <div><dt>voice</dt><dd>{voice} rate={rate}</dd></div>
        <div><dt>readiness</dt><dd>would_emit={would} blocked={blocked} reasons={reasons}</dd></div>
        <div><dt>cooldown</dt><dd>active={cooldown_active} secs={cooldown} next={next_allowed}</dd></div>
        <div><dt>state</dt><dd>{state_path}</dd></div>
        <div><dt>command</dt><dd>{command}</dd></div>
        <div><dt>open</dt><dd><a href="{href}">voice action preview json</a></dd></div>
      </dl>
    </section>"#,
        state = state,
        ready = ready,
        token = token,
        line = line,
        voice = voice,
        rate = rate,
        would = would,
        blocked = blocked,
        reasons = reasons,
        cooldown_active = cooldown_active,
        cooldown = cooldown,
        next_allowed = next_allowed,
        state_path = state_path,
        command = command,
        href = html_escape(&href_raw),
    )
}

fn avatar_surface_xiao_shu_action_request_html(
    action_request_preview: &Value,
    q: &AvatarSurfaceQuery,
) -> String {
    let request = action_request_preview
        .get("action_request")
        .unwrap_or(&Value::Null);
    let route_raw = "/avatar-surface/xiao-shu-action-request";
    let mut href_raw = avatar_surface_route_href(
        route_raw,
        q.project.as_deref(),
        request
            .get("mapped_track")
            .and_then(Value::as_str)
            .or(Some("xiao_shu::alert_peek::medium")),
    );
    let sep = if href_raw.contains('?') { "&" } else { "?" };
    href_raw.push_str(sep);
    href_raw.push_str("actor=panel&intent=voice_alert&reason=panel-dry-run");
    let state = avatar_surface_html_json_value(request.get("request_state"), "-");
    let actor = avatar_surface_html_json_value(request.get("actor"), "-");
    let intent = avatar_surface_html_json_value(request.get("intent"), "-");
    let supported = avatar_surface_html_json_value(request.get("supported_intent"), "false");
    let direct_control = avatar_surface_html_json_value(
        action_request_preview.get("direct_pet_control_allowed"),
        "false",
    );
    let emit_audio =
        avatar_surface_html_json_value(action_request_preview.get("emits_audio"), "false");
    let human_required =
        avatar_surface_html_json_value(request.get("requires_human_confirmation"), "true");
    let confirmed =
        avatar_surface_html_json_value(request.get("human_confirmation_present"), "false");
    let ready = avatar_surface_html_json_value(request.get("ready_for_local_cli_emit"), "false");
    let blocked = avatar_surface_html_json_value(request.get("blocked"), "true");
    let reasons = html_escape(
        &request
            .get("blocked_reasons")
            .map(Value::to_string)
            .unwrap_or_else(|| "[]".to_string()),
    );
    let track = avatar_surface_html_json_value(request.get("mapped_track"), "-");
    let line = avatar_surface_html_json_value(request.get("line"), "-");
    let cue = avatar_surface_html_json_value(request.get("cue_id"), "-");
    let message_handling = request.get("message_handling").unwrap_or(&Value::Null);
    let message_context = avatar_surface_html_json_value(
        message_handling.get("message_is_context_note_only"),
        "false",
    );
    let message_replace = avatar_surface_html_json_value(
        message_handling.get("message_can_replace_utterance"),
        "false",
    );
    let preview_command = avatar_surface_html_json_value(request.get("preview_command"), "-");
    let enqueue_command = avatar_surface_html_json_value(request.get("enqueue_command"), "-");
    let confirm_command =
        avatar_surface_html_json_value(request.get("confirm_request_command"), "-");
    let queue_command = avatar_surface_html_json_value(request.get("queue_command"), "-");
    let queue_panel_raw = request
        .get("queue_panel_path")
        .and_then(Value::as_str)
        .unwrap_or("/avatar-surface/xiao-shu-action-requests");
    let queue_summary = action_request_preview
        .get("queue_summary")
        .unwrap_or(&Value::Null);
    let pending_count = avatar_surface_html_json_value(queue_summary.get("pending_count"), "0");
    let emit_command = avatar_surface_html_json_value(request.get("emit_command"), "-");

    format!(
        r#"<section class="health status-fresh">
      <div class="health-title">
        <span class="pill status-fresh">request</span>
        <strong>Xiao Shu Action Request</strong>
        <span>state={state} actor={actor} intent={intent}</span>
      </div>
      <dl>
        <div><dt>target</dt><dd>track={track} supported={supported}</dd></div>
        <div><dt>line</dt><dd>{line} cue={cue}</dd></div>
        <div><dt>message</dt><dd>context_only={message_context} can_replace_line={message_replace}</dd></div>
        <div><dt>policy</dt><dd>direct_control={direct_control} emits_audio={emit_audio} human_required={human_required} confirmed={confirmed}</dd></div>
        <div><dt>readiness</dt><dd>ready={ready} blocked={blocked} reasons={reasons}</dd></div>
        <div><dt>preview</dt><dd>{preview_command}</dd></div>
        <div><dt>enqueue</dt><dd>{enqueue_command}</dd></div>
        <div><dt>confirm</dt><dd>{confirm_command}</dd></div>
        <div><dt>emit</dt><dd>{emit_command}</dd></div>
        <div><dt>queue</dt><dd>pending={pending_count} command={queue_command} <a href="{queue_panel}">open queue</a></dd></div>
        <div><dt>open</dt><dd><a href="{href}">xiao shu action request json</a></dd></div>
      </dl>
    </section>"#,
        state = state,
        actor = actor,
        intent = intent,
        track = track,
        supported = supported,
        line = line,
        cue = cue,
        message_context = message_context,
        message_replace = message_replace,
        direct_control = direct_control,
        emit_audio = emit_audio,
        human_required = human_required,
        confirmed = confirmed,
        ready = ready,
        blocked = blocked,
        reasons = reasons,
        preview_command = preview_command,
        enqueue_command = enqueue_command,
        confirm_command = confirm_command,
        emit_command = emit_command,
        pending_count = pending_count,
        queue_command = queue_command,
        queue_panel = html_escape(queue_panel_raw),
        href = html_escape(&href_raw),
    )
}

fn avatar_surface_xiao_shu_action_requests_html(
    action_request_queue: &Value,
    q: &AvatarSurfaceQuery,
) -> String {
    let queue = action_request_queue.get("queue").unwrap_or(&Value::Null);
    let records = action_request_queue
        .get("records")
        .and_then(Value::as_array)
        .cloned()
        .unwrap_or_default();
    let href_raw = avatar_surface_route_href(
        "/avatar-surface/xiao-shu-action-requests",
        q.project.as_deref(),
        None,
    );
    let exists = avatar_surface_html_json_value(queue.get("exists"), "false");
    let state_filter =
        avatar_surface_html_json_value(queue.get("state_filter"), "pending_human_confirmation");
    let matching = avatar_surface_html_json_value(queue.get("matching_records"), "0");
    let returned = avatar_surface_html_json_value(queue.get("returned_count"), "0");
    let include_details = avatar_surface_html_json_value(queue.get("include_details"), "false");
    let path = avatar_surface_html_json_value(queue.get("path"), "-");
    let current_records = avatar_surface_html_json_value(queue.get("current_records"), "0");
    let state_counts = queue
        .get("state_counts")
        .and_then(Value::as_object)
        .map(|counts| {
            let mut parts = counts
                .iter()
                .map(|(state, count)| format!("{state}={count}"))
                .collect::<Vec<_>>();
            parts.sort();
            parts.join(" ")
        })
        .filter(|summary| !summary.is_empty())
        .unwrap_or_else(|| "none".to_string());
    let state_counts = html_escape(&state_counts);
    let mut rows = String::new();
    for record in records {
        let request_id_raw = record
            .get("request_id")
            .and_then(Value::as_str)
            .unwrap_or("-");
        let project_raw = record
            .get("project")
            .and_then(Value::as_str)
            .or(q.project.as_deref())
            .unwrap_or("agent-bridge");
        let reason_raw = record
            .get("reason")
            .and_then(Value::as_str)
            .unwrap_or("operator-confirmed-request");
        let local_confirm_raw = crate::avatar_cortex::xiao_shu_action_request_action_command(
            project_raw,
            request_id_raw,
            reason_raw,
            None,
        );
        let local_command_raw = crate::avatar_cortex::xiao_shu_action_request_action_command(
            project_raw,
            request_id_raw,
            reason_raw,
            Some("--emit"),
        );
        let local_dismiss_raw = crate::avatar_cortex::xiao_shu_action_request_action_command(
            project_raw,
            request_id_raw,
            reason_raw,
            Some("--dismiss"),
        );
        let detail_href_raw = format!(
            "/avatar-surface/xiao-shu-action-requests?project={project}&request_id={request_id}&details=true",
            project = url_query_component(project_raw),
            request_id = url_query_component(request_id_raw)
        );
        let console_href_raw = format!(
            "/avatar-surface/xiao-shu-action-console?project={project}&request_id={request_id}",
            project = url_query_component(project_raw),
            request_id = url_query_component(request_id_raw)
        );
        let request_id = avatar_surface_html_json_value(record.get("request_id"), "-");
        let state = avatar_surface_html_json_value(record.get("state"), "-");
        let actor = avatar_surface_html_json_value(record.get("actor"), "-");
        let intent = avatar_surface_html_json_value(record.get("intent"), "-");
        let track = avatar_surface_html_json_value(record.get("mapped_track"), "-");
        let line = avatar_surface_html_json_value(
            record
                .get("action_request")
                .and_then(|request| request.get("line"))
                .or_else(|| record.get("line")),
            "-",
        );
        let cue = avatar_surface_html_json_value(
            record
                .get("action_request")
                .and_then(|request| request.get("cue_id"))
                .or_else(|| record.get("cue_id")),
            "-",
        );
        let reason = avatar_surface_html_json_value(record.get("reason"), "-");
        let local_confirm = html_escape(&local_confirm_raw);
        let local_command = html_escape(&local_command_raw);
        let local_dismiss = html_escape(&local_dismiss_raw);
        let detail_href = html_escape(&detail_href_raw);
        let console_href = html_escape(&console_href_raw);
        rows.push_str(&format!(
            r#"<li><strong>{request_id}</strong><span>state={state} actor={actor} intent={intent}</span><span>track={track}</span><span>cue={cue} line={line}</span><span>reason={reason}</span><span><a href="{console_href}">console</a> <a href="{detail_href}">detail json</a></span><span>dry_run={local_confirm}</span><span>emit={local_command}</span><span>dismiss={local_dismiss}</span></li>"#
        ));
    }
    if rows.is_empty() {
        rows.push_str(
            r#"<li><strong>none</strong><span>no pending Xiao Shu action requests</span></li>"#,
        );
    }

    format!(
        r#"<section class="health status-fresh">
      <div class="health-title">
        <span class="pill status-fresh">queue</span>
        <strong>Xiao Shu Action Requests</strong>
        <span>pending={matching} returned={returned} current={current_records} exists={exists}</span>
      </div>
      <dl>
        <div><dt>states</dt><dd>{state_counts}</dd></div>
        <div><dt>filter</dt><dd>state={state_filter} details={include_details}</dd></div>
        <div><dt>path</dt><dd>{path}</dd></div>
        <div><dt>open</dt><dd><a href="{href}">pending action request json</a> <a href="{console_href}">operator console</a></dd></div>
      </dl>
      <ul class="compact-list">{rows}</ul>
    </section>"#,
        matching = matching,
        returned = returned,
        current_records = current_records,
        exists = exists,
        state_counts = state_counts,
        state_filter = state_filter,
        include_details = include_details,
        path = path,
        href = html_escape(&href_raw),
        console_href = html_escape(&avatar_surface_route_href(
            "/avatar-surface/xiao-shu-action-console",
            q.project.as_deref(),
            None,
        )),
        rows = rows,
    )
}

fn avatar_surface_xiao_shu_action_console_html(
    action_request_queue: &Value,
    q: &XiaoShuActionRequestsQuery,
) -> String {
    let queue = action_request_queue.get("queue").unwrap_or(&Value::Null);
    let records = action_request_queue
        .get("records")
        .and_then(Value::as_array)
        .cloned()
        .unwrap_or_default();
    let project_raw = queue
        .get("project")
        .and_then(Value::as_str)
        .or(q.project.as_deref())
        .unwrap_or("agent-bridge");
    let path = avatar_surface_html_json_value(queue.get("path"), "-");
    let returned = avatar_surface_html_json_value(queue.get("returned_count"), "0");
    let matching = avatar_surface_html_json_value(queue.get("matching_records"), "0");
    let current = avatar_surface_html_json_value(queue.get("current_records"), "0");
    let state_filter =
        avatar_surface_html_json_value(queue.get("state_filter"), "pending_human_confirmation");
    let queue_href = html_escape(&format!(
        "/avatar-surface/xiao-shu-action-requests?project={project}",
        project = url_query_component(project_raw)
    ));
    let panel_href = html_escape(&format!(
        "/avatar-surface/panel?project={project}&include_stale=true&limit=10",
        project = url_query_component(project_raw)
    ));
    let pending_href = html_escape(&format!(
        "/avatar-surface/xiao-shu-action-console?project={project}",
        project = url_query_component(project_raw)
    ));
    let all_href = html_escape(&format!(
        "/avatar-surface/xiao-shu-action-console?project={project}&all_states=true&limit=10",
        project = url_query_component(project_raw)
    ));
    let emitted_href = html_escape(&format!(
        "/avatar-surface/xiao-shu-action-console?project={project}&state=emitted&limit=10",
        project = url_query_component(project_raw)
    ));
    let dismissed_href = html_escape(&format!(
        "/avatar-surface/xiao-shu-action-console?project={project}&state=dismissed&limit=10",
        project = url_query_component(project_raw)
    ));

    let mut cards = String::new();
    for record in records {
        let request = record.get("action_request").unwrap_or(&Value::Null);
        let request_id_raw = record
            .get("request_id")
            .and_then(Value::as_str)
            .unwrap_or("-");
        let reason_raw = record
            .get("reason")
            .and_then(Value::as_str)
            .or_else(|| request.get("reason").and_then(Value::as_str))
            .unwrap_or("operator-confirmed-request");
        let project_for_command = record
            .get("project")
            .and_then(Value::as_str)
            .unwrap_or(project_raw);
        let confirm_raw = crate::avatar_cortex::xiao_shu_action_request_action_command(
            project_for_command,
            request_id_raw,
            reason_raw,
            None,
        );
        let emit_raw = crate::avatar_cortex::xiao_shu_action_request_action_command(
            project_for_command,
            request_id_raw,
            reason_raw,
            Some("--emit"),
        );
        let dismiss_raw = crate::avatar_cortex::xiao_shu_action_request_action_command(
            project_for_command,
            request_id_raw,
            reason_raw,
            Some("--dismiss"),
        );
        let json_href = html_escape(&format!(
            "/avatar-surface/xiao-shu-action-requests?project={project}&request_id={request_id}&details=true",
            project = url_query_component(project_for_command),
            request_id = url_query_component(request_id_raw)
        ));
        let state = avatar_surface_html_json_value(record.get("state"), "-");
        let actor = avatar_surface_html_json_value(record.get("actor"), "-");
        let intent = avatar_surface_html_json_value(record.get("intent"), "-");
        let track = avatar_surface_html_json_value(record.get("mapped_track"), "-");
        let cue = avatar_surface_html_json_value(
            request.get("cue_id").or_else(|| record.get("cue_id")),
            "-",
        );
        let line =
            avatar_surface_html_json_value(request.get("line").or_else(|| record.get("line")), "-");
        let message = avatar_surface_html_json_value(
            request.get("message").or_else(|| record.get("message")),
            "-",
        );
        let context_only = avatar_surface_html_json_value(
            request
                .get("message_handling")
                .and_then(|handling| handling.get("message_is_context_note_only"))
                .or_else(|| {
                    record
                        .get("message_handling")
                        .and_then(|handling| handling.get("message_is_context_note_only"))
                }),
            "true",
        );
        let can_replace = avatar_surface_html_json_value(
            request
                .get("message_handling")
                .and_then(|handling| handling.get("message_can_replace_utterance"))
                .or_else(|| {
                    record
                        .get("message_handling")
                        .and_then(|handling| handling.get("message_can_replace_utterance"))
                }),
            "false",
        );
        let confirm = avatar_surface_xiao_shu_action_console_command_html("dry run", &confirm_raw);
        let emit = avatar_surface_xiao_shu_action_console_command_html("emit", &emit_raw);
        let dismiss = avatar_surface_xiao_shu_action_console_command_html("dismiss", &dismiss_raw);
        cards.push_str(&format!(
            r#"<section class="card">
        <div class="card-title"><span class="pill">request</span><strong>{request_id}</strong><span>state={state}</span></div>
        <dl>
          <div><dt>target</dt><dd>actor={actor} intent={intent} track={track}</dd></div>
          <div><dt>cue</dt><dd>{cue}</dd></div>
          <div><dt>line</dt><dd>{line}</dd></div>
          <div><dt>message</dt><dd>{message} context_only={context_only} can_replace_line={can_replace}</dd></div>
        </dl>
        <div class="commands">
          {confirm}
          {emit}
          {dismiss}
        </div>
        <div class="links"><a href="{json_href}">json</a><a href="{queue_href}">queue</a><a href="{panel_href}">panel</a></div>
      </section>"#,
            request_id = avatar_surface_html_json_value(record.get("request_id"), "-"),
            state = state,
            actor = actor,
            intent = intent,
            track = track,
            cue = cue,
            line = line,
            message = message,
            context_only = context_only,
            can_replace = can_replace,
            confirm = confirm,
            emit = emit,
            dismiss = dismiss,
            json_href = json_href,
            queue_href = queue_href,
            panel_href = panel_href,
        ));
    }
    if cards.is_empty() {
        cards.push_str(r#"<section class="card"><strong>No matching Xiao Shu action requests</strong><p>Queue has no pending record for this filter.</p></section>"#);
    }

    format!(
        r#"<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>Xiao Shu Action Console</title>
  <style>
    :root {{ --bg:#f8f8f2; --fg:#20221d; --muted:#65685f; --line:#d8d9cf; --accent:#167a72; --surface:#fff; --code:#f0f1eb; }}
    @media (prefers-color-scheme: dark) {{ :root {{ --bg:#161713; --fg:#eceee4; --muted:#a5a99d; --line:#33372e; --accent:#5bd0c3; --surface:#20221d; --code:#282b24; }} }}
    * {{ box-sizing:border-box; }}
    body {{ margin:0; background:var(--bg); color:var(--fg); font:14px/1.45 ui-sans-serif,system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif; }}
    main {{ width:min(960px,calc(100vw - 32px)); margin:24px auto 40px; }}
    header {{ display:flex; justify-content:space-between; gap:16px; align-items:flex-end; border-bottom:1px solid var(--line); padding-bottom:14px; }}
    h1 {{ margin:0; font-size:24px; line-height:1.1; letter-spacing:0; }}
    .meta,.card-title span,p {{ color:var(--muted); overflow-wrap:anywhere; }}
    .card {{ margin-top:18px; padding:14px; background:var(--surface); border:1px solid var(--line); border-left:4px solid var(--accent); }}
    .card-title {{ display:flex; gap:8px; flex-wrap:wrap; align-items:baseline; }}
    .pill {{ display:inline-block; padding:2px 7px; border:1px solid var(--accent); color:var(--accent); border-radius:999px; font-size:12px; font-weight:700; }}
    .filters {{ display:flex; flex-wrap:wrap; gap:8px; margin-top:10px; }}
    .filters a,.copy-command {{ border:1px solid var(--line); background:var(--surface); color:var(--accent); border-radius:6px; padding:5px 8px; font:inherit; font-weight:700; text-decoration:none; cursor:pointer; }}
    .policy {{ margin-top:10px; color:var(--muted); }}
    dl,.commands {{ display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); gap:10px; margin:12px 0 0; }}
    .commands {{ grid-template-columns:1fr; }}
    .command-head {{ display:flex; align-items:center; justify-content:space-between; gap:8px; }}
    dt {{ color:var(--muted); font-size:11px; font-weight:700; text-transform:uppercase; }}
    dd {{ margin:3px 0 0; overflow-wrap:anywhere; }}
    code {{ display:block; padding:10px; background:var(--code); border:1px solid var(--line); white-space:pre-wrap; overflow-wrap:anywhere; }}
    .links {{ display:flex; flex-wrap:wrap; gap:12px; margin-top:12px; }}
    a {{ color:var(--accent); }}
    @media (max-width:760px) {{ main {{ width:min(100vw - 20px,960px); margin-top:14px; }} header {{ display:block; }} dl,.commands {{ grid-template-columns:1fr; }} }}
  </style>
</head>
<body>
  <main>
    <header>
      <div>
        <h1>Xiao Shu Action Console</h1>
        <div class="meta">project={project} returned={returned} matching={matching} current={current} state={state_filter}</div>
        <div class="meta">queue={path}</div>
        <nav class="filters" aria-label="queue filters"><a href="{pending_href}">pending</a><a href="{all_href}">all</a><a href="{emitted_href}">emitted</a><a href="{dismissed_href}">dismissed</a></nav>
        <div class="policy">read-only console; server actions disabled; real output stays behind local CLI confirmation</div>
      </div>
      <div class="meta"><a href="{panel_href}">panel</a> <a href="{queue_href}">queue json</a></div>
    </header>
    {cards}
  </main>
  <script>
    (() => {{
      const copyText = async (button) => {{
        const text = button.getAttribute("data-copy") || "";
        if (!text) return;
        try {{
          await navigator.clipboard.writeText(text);
          const previous = button.textContent;
          button.textContent = "copied";
          window.setTimeout(() => {{ button.textContent = previous; }}, 1200);
        }} catch (_err) {{
          button.textContent = "select";
        }}
      }};
      document.addEventListener("click", (event) => {{
        const button = event.target.closest("[data-copy]");
        if (button) copyText(button);
      }});
    }})();
  </script>
</body>
</html>"#,
        project = html_escape(project_raw),
        returned = returned,
        matching = matching,
        current = current,
        state_filter = state_filter,
        path = path,
        panel_href = panel_href,
        queue_href = queue_href,
        pending_href = pending_href,
        all_href = all_href,
        emitted_href = emitted_href,
        dismissed_href = dismissed_href,
        cards = cards,
    )
}

fn avatar_surface_xiao_shu_action_console_command_html(label: &str, command: &str) -> String {
    let command = html_escape(command);
    format!(
        r#"<div class="command-row"><div class="command-head"><dt>{label}</dt><button class="copy-command" type="button" data-copy="{command}">copy</button></div><dd><code>{command}</code></dd></div>"#,
        label = html_escape(label),
        command = command
    )
}

fn avatar_surface_linux_renderer_html(
    payload: &Value,
    generated_at: i64,
    state_url: &str,
    transparent: bool,
) -> String {
    let project = avatar_surface_html_json_value(payload.get("project"), "unknown");
    let state = payload.get("state").unwrap_or(&Value::Null);
    let plan = payload.get("plan").unwrap_or(&Value::Null);
    let selection = payload.get("selection").unwrap_or(&Value::Null);
    let safety = payload.get("safety").unwrap_or(&Value::Null);

    let mode = avatar_surface_html_json_value(state.get("mode"), "idle");
    let activity = avatar_surface_html_json_value(state.get("activity_state"), &mode);
    let source = avatar_surface_html_json_value(selection.get("source"), "idle_fallback");
    let selection_fallback =
        avatar_surface_html_json_value(selection.get("fallback_reason"), "none");
    let track = avatar_surface_html_json_value(plan.get("track"), "idle_breathe");
    let token =
        avatar_surface_html_json_value(plan.get("renderer_token"), "xiao_shu::idle_breathe::low");
    let asset_route = avatar_surface_html_json_value(
        plan.get("asset_route"),
        "/avatar-surface/sidecar-spritesheet?asset=xiao-shu-v3-ai-idle-breathe-v1",
    );
    let plan_fallback = avatar_surface_html_json_value(plan.get("fallback_reason"), "none");
    let codex_pet_mutation =
        avatar_surface_html_json_value(safety.get("codex_pet_package_mutation"), "false");
    let emits_audio = avatar_surface_html_json_value(safety.get("emits_audio"), "false");
    let controls_desktop = avatar_surface_html_json_value(safety.get("controls_desktop"), "false");
    let writes_files = avatar_surface_html_json_value(safety.get("writes_files"), "false");
    let mutates_renderer = avatar_surface_html_json_value(safety.get("mutates_renderer"), "false");
    let payload_json = html_json_script(payload);
    let route_json = html_json_script(&json!(asset_route.clone()));
    let state_url_json = html_json_script(&json!(state_url));
    let transparent_attr = if transparent { "true" } else { "false" };
    let transparent_css = if transparent {
        r#"
    html, body { background:transparent !important; }
    body { overflow:hidden; }
    main { width:100vw; height:100vh; margin:0; display:grid; place-items:center; background:transparent; }
    header, .debug-panel { display:none; }
    .stage { margin:0; width:100vw; height:100vh; min-height:0; border:0; background:transparent; }
    .sprite { transform:scale(1.55); }
"#
    } else {
        ""
    };

    format!(
        r#"<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>Linux Codex Avatar Renderer</title>
  <style>
    :root {{ color-scheme: light dark; --bg:#f7f9f7; --fg:#1b1e1b; --muted:#68706a; --line:#d5ddd6; --surface:#fff; --accent:#147a74; --stage:#edf6f2; }}
    @media (prefers-color-scheme: dark) {{ :root {{ --bg:#121512; --fg:#eef4ef; --muted:#a6b0a9; --line:#303831; --surface:#1c211d; --accent:#5bd0c3; --stage:#202820; }} }}
    * {{ box-sizing:border-box; }}
    body {{ margin:0; background:var(--bg); color:var(--fg); font:14px/1.45 ui-sans-serif,system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif; }}
    main {{ width:min(860px,calc(100vw - 28px)); margin:22px auto 34px; }}
    header {{ display:flex; justify-content:space-between; gap:16px; align-items:flex-end; border-bottom:1px solid var(--line); padding-bottom:14px; }}
    h1 {{ margin:0; font-size:24px; line-height:1.1; letter-spacing:0; }}
    .meta,.safety {{ color:var(--muted); overflow-wrap:anywhere; }}
    .stage {{ margin-top:18px; min-height:360px; border:1px solid var(--line); background:var(--stage); display:grid; place-items:center; overflow:hidden; position:relative; isolation:isolate; }}
    .aura {{ --aura-hue:174; --aura-hue-2:218; position:absolute; width:min(330px,72%); aspect-ratio:1; border-radius:999px; opacity:.78; transform:translateY(18px); filter:blur(1px) saturate(1.2); background:radial-gradient(circle at 50% 45%, hsla(var(--aura-hue),78%,66%,.62) 0 18%, hsla(var(--aura-hue-2),68%,48%,.38) 34%, rgba(20,122,116,.08) 58%, transparent 72%), conic-gradient(from 18deg, hsla(var(--aura-hue),70%,55%,.16), hsla(var(--aura-hue-2),72%,52%,.28), hsla(var(--aura-hue),70%,55%,.16)); box-shadow:0 0 34px hsla(var(--aura-hue),70%,55%,.32); z-index:0; }}
    .stage:not(.has-aura) .aura {{ display:none; }}
    .sprite {{ width:192px; height:208px; background-image:url("{asset_route}"); background-size:1536px 1872px; background-repeat:no-repeat; image-rendering:auto; transform:scale(1.35); transform-origin:center bottom; position:relative; z-index:1; }}
    .panel {{ margin-top:14px; padding:12px; border:1px solid var(--line); background:var(--surface); }}
    dl {{ display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); gap:10px; margin:0; }}
    dt {{ color:var(--muted); font-size:11px; text-transform:uppercase; font-weight:700; }}
    dd {{ margin:3px 0 0; overflow-wrap:anywhere; }}
    code {{ display:block; margin-top:12px; padding:10px; background:rgba(127,127,127,.12); overflow:auto; white-space:pre-wrap; }}
    @media (max-width:720px) {{ header {{ display:block; }} dl {{ grid-template-columns:1fr; }} .stage {{ min-height:300px; }} }}
    {transparent_css}
  </style>
</head>
<body>
  <main data-state-url="{state_url}" data-transparent="{transparent_attr}">
    <header>
      <div>
        <h1>Linux Codex Avatar Renderer</h1>
        <div class="meta">project={project} generated_at={generated_at}</div>
      </div>
      <div class="meta">read_only=true source={source}</div>
    </header>
    <section class="stage" data-track="{track}" data-token="{token}">
      <div class="aura" aria-hidden="true"></div>
      <div class="sprite" role="img" aria-label="Xiao Shu {track}"></div>
    </section>
    <section class="panel debug-panel">
      <dl>
        <div><dt>state</dt><dd data-field="state">mode={mode} activity={activity}</dd></div>
        <div><dt>plan</dt><dd data-field="plan">track={track} token={token}</dd></div>
        <div><dt>asset</dt><dd data-field="asset">{asset_route}</dd></div>
        <div><dt>aura</dt><dd data-field="aura">none</dd></div>
        <div><dt>fallback</dt><dd data-field="fallback">selection={selection_fallback} plan={plan_fallback}</dd></div>
        <div><dt>safety</dt><dd data-field="safety">codex_pet_package_mutation={codex_pet_mutation} emits_audio={emits_audio} controls_desktop={controls_desktop}</dd></div>
        <div><dt>mutation</dt><dd data-field="mutation">writes_files={writes_files} mutates_renderer={mutates_renderer}</dd></div>
      </dl>
      <code id="payload-json"></code>
    </section>
  </main>
  <script>
    const initialPayload = {payload_json};
    const fallbackAssetRoute = {route_json};
    const stateUrl = {state_url_json};
    const stage = document.querySelector(".stage");
    const aura = document.querySelector(".aura");
    const sprite = document.querySelector(".sprite");
    const payloadJson = document.getElementById("payload-json");
    const field = (name) => document.querySelector(`[data-field="${{name}}"]`);
    const value = (source, key, fallback) => {{
      const next = source && source[key];
      return next === null || next === undefined || next === "" ? fallback : String(next);
    }};
    const setField = (name, text) => {{
      const node = field(name);
      if (node) node.textContent = text;
    }};
    function hashHue(seed) {{
      let acc = 0;
      for (const ch of String(seed || "lcc-aura")) acc = (acc * 33 + ch.charCodeAt(0)) % 360;
      return acc;
    }}
    function applyAuraLayer(auraIo) {{
      const active = Boolean(auraIo && auraIo.surface === "lcc_aura_io_intake");
      stage.classList.toggle("has-aura", active);
      if (!aura) return;
      if (!active) {{
        aura.hidden = true;
        setField("aura", "none");
        return;
      }}
      const seed = value(auraIo, "uniform_sha256", value(auraIo, "uniform_path", "lcc-aura"));
      const hue = hashHue(seed);
      aura.hidden = false;
      aura.dataset.schema = value(auraIo, "schema_version", "unknown");
      aura.dataset.uniform = seed.slice(0, 16);
      aura.style.setProperty("--aura-hue", String(hue));
      aura.style.setProperty("--aura-hue-2", String((hue + 58) % 360));
      setField("aura", `surface=${{value(auraIo, "surface", "unknown")}} kind=${{value(auraIo, "renderer_input_kind", "unknown")}} uniform=${{seed.slice(0, 12)}} source=${{value(auraIo, "visible_signal_source", "unknown")}}`);
    }}
    function applyRendererPayload(nextPayload) {{
      const state = nextPayload.state || {{}};
      const plan = nextPayload.plan || {{}};
      const selection = nextPayload.selection || {{}};
      const safety = nextPayload.safety || {{}};
      const track = value(plan, "track", "idle_breathe");
      const token = value(plan, "renderer_token", "xiao_shu::idle_breathe::low");
      const assetRoute = value(plan, "asset_route", fallbackAssetRoute);
      stage.dataset.track = track;
      stage.dataset.token = token;
      sprite.setAttribute("aria-label", `Xiao Shu ${{track}}`);
      sprite.style.backgroundImage = `url("${{assetRoute}}")`;
      applyAuraLayer(nextPayload.aura_io);
      setField("state", `mode=${{value(state, "mode", "idle")}} activity=${{value(state, "activity_state", value(state, "mode", "idle"))}}`);
      setField("plan", `track=${{track}} token=${{token}}`);
      setField("asset", assetRoute);
      setField("fallback", `selection=${{value(selection, "fallback_reason", "none")}} plan=${{value(plan, "fallback_reason", "none")}}`);
      setField("safety", `codex_pet_package_mutation=${{value(safety, "codex_pet_package_mutation", "false")}} emits_audio=${{value(safety, "emits_audio", "false")}} controls_desktop=${{value(safety, "controls_desktop", "false")}}`);
      setField("mutation", `writes_files=${{value(safety, "writes_files", "false")}} mutates_renderer=${{value(safety, "mutates_renderer", "false")}}`);
      payloadJson.textContent = JSON.stringify(nextPayload, null, 2);
    }}
    async function refreshRendererState() {{
      try {{
        const response = await fetch(stateUrl, {{ cache: "no-store" }});
        if (!response.ok) return;
        applyRendererPayload(await response.json());
      }} catch (_err) {{}}
    }}
    applyRendererPayload(initialPayload);
    setInterval(refreshRendererState, 1000);
  </script>
</body>
</html>"#,
        state_url = html_escape(state_url),
        transparent_attr = transparent_attr,
        transparent_css = transparent_css,
        project = html_escape(&project),
        generated_at = generated_at,
        source = html_escape(&source),
        track = html_escape(&track),
        token = html_escape(&token),
        mode = html_escape(&mode),
        activity = html_escape(&activity),
        asset_route = html_escape(&asset_route),
        selection_fallback = html_escape(&selection_fallback),
        plan_fallback = html_escape(&plan_fallback),
        codex_pet_mutation = html_escape(&codex_pet_mutation),
        emits_audio = html_escape(&emits_audio),
        controls_desktop = html_escape(&controls_desktop),
        writes_files = html_escape(&writes_files),
        mutates_renderer = html_escape(&mutates_renderer),
        payload_json = payload_json,
        route_json = route_json,
        state_url_json = state_url_json,
    )
}

fn avatar_surface_renderer_view_html(
    renderer_view_preview: &Value,
    generated_at: i64,
    requested_track: Option<&str>,
    requested_track_index: Option<usize>,
    requested_variant: Option<&str>,
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
    let active_variant = active
        .get("semantic_variants")
        .and_then(Value::as_array)
        .and_then(|variants| {
            requested_variant
                .and_then(|variant_id| {
                    variants.iter().find(|variant| {
                        variant.get("variant_id").and_then(Value::as_str) == Some(variant_id)
                    })
                })
                .or_else(|| {
                    variants.iter().find(|variant| {
                        variant
                            .get("default")
                            .and_then(Value::as_bool)
                            .unwrap_or(false)
                    })
                })
                .or_else(|| variants.first())
        });
    let active_variant_id_raw = active_variant
        .and_then(|variant| variant.get("variant_id"))
        .and_then(Value::as_str)
        .unwrap_or("");
    let active_variant_label_raw = active_variant
        .and_then(|variant| variant.get("label"))
        .and_then(Value::as_str)
        .unwrap_or("default");
    let active_variant_meta = if active_variant_id_raw.is_empty() {
        "default".to_string()
    } else {
        format!("{active_variant_id_raw} / {active_variant_label_raw}")
    };
    let active_variant_label = html_escape(&active_variant_meta);
    let active_variant_json = html_json_script(&json!(active_variant_id_raw));
    let active_voice_linkage = active
        .get("semantic_variant_review")
        .and_then(|review| review.get("voice_linkage_preview"))
        .unwrap_or(&Value::Null);
    let active_voice_text = avatar_surface_html_json_value(
        active_voice_linkage.get("utterance"),
        "visual-only preview",
    );
    let active_voice_gate = avatar_surface_html_json_value(
        active_voice_linkage
            .get("gate")
            .and_then(|gate| gate.get("dry_run_route")),
        "-",
    );
    let active_voice_audio =
        avatar_surface_html_json_value(active_voice_linkage.get("emits_audio"), "false");
    let active_voice_required = avatar_surface_html_json_value(
        active_voice_linkage
            .get("voice")
            .and_then(|voice| voice.get("requires_explicit_emit_gate")),
        "true",
    );
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
    let asset_source = view.get("asset_source").unwrap_or(&Value::Null);
    let asset_pet_id = avatar_surface_html_json_value(asset_source.get("pet_id"), "xiao-shu-dev");
    let sprite_route = avatar_surface_html_json_value(
        asset_source.get("route"),
        "/avatar-surface/pet-spritesheet?pet_id=xiao-shu-dev",
    );
    let data_json = html_json_script(renderer_view_preview);
    let sprite_route_json = html_json_script(&json!(sprite_route.clone()));
    let asset_pet_id_json = html_json_script(&json!(asset_pet_id.clone()));
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
            let (frames, duration) = avatar_surface_renderer_track_display_metrics(track);
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
      --alert-soft: #c97968;
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
        --alert-soft: #d58c7f;
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
    .xiao-shu-sprite {{
      width: 192px;
      height: 208px;
      background-image: url("{sprite_route}");
      background-repeat: no-repeat;
      background-size: 1536px 1872px;
      background-position: 0 0;
      transform: translateY(8px) scale(1.42);
      transform-origin: 50% 88%;
      filter: none;
      transition: filter 180ms ease, transform 180ms ease;
      z-index: 2;
    }}
    .xiao-shu.sprite-choreographed .xiao-shu-sprite {{
      transition: none;
    }}
    .xiao-shu.sprite-backed .xiao-shu-body {{
      display: none;
    }}
    .sprite-alert-mark {{
      position: absolute;
      width: 22px;
      height: 22px;
      right: 82px;
      top: 54px;
      border-radius: 999px;
      background: var(--alert-soft);
      border: 3px solid rgba(244, 247, 237, 0.82);
      opacity: 0;
      transform: scale(0.9);
      transition: opacity 180ms ease, transform 180ms ease;
      z-index: 3;
    }}
    .sprite-alert.sprite-attention-visible .sprite-alert-mark {{
      opacity: 0.78;
      transform: scale(1);
    }}
    .sprite-alert .xiao-shu-sprite {{
      filter: none;
      transform: translateY(8px) scale(1.42);
    }}
    .xiao-shu[data-sprite-variant="current_alert_row"].sprite-alert .xiao-shu-sprite {{
      transform: translateY(8px) scale(1.46);
    }}
    .xiao-shu[data-sprite-variant="waiting_peek_row"].sprite-alert .sprite-alert-mark {{
      opacity: 0.58;
      transform: scale(0.86);
    }}
    .xiao-shu[data-sprite-variant="sidecar_peek_v2"].sprite-alert .sprite-alert-mark,
    .xiao-shu[data-sprite-variant="sidecar_peek_v4"].sprite-alert .sprite-alert-mark {{
      width: 18px;
      height: 18px;
      right: 78px;
      top: 56px;
      opacity: 0.62;
      transform: scale(0.9);
    }}
    .xiao-shu[data-sprite-variant="focused_review_row"].sprite-alert .sprite-alert-mark {{
      width: 18px;
      height: 18px;
      right: 88px;
      top: 58px;
      opacity: 0.66;
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
    .accessory-small-attention-mark .status-dot {{
      width: 34px;
      height: 34px;
      background: var(--alert-soft);
      opacity: 0.68;
      transform: scale(0.9);
    }}
    .motion-alert-peek .xiao-shu-head,
    .motion-alert-peek .xiao-shu-torso,
    .motion-alert-peek .hand,
    .motion-alert-peek .status-dot {{
      border-width: 4px;
    }}
    .motion-alert-peek .xiao-shu-body {{
      filter: saturate(0.88) brightness(0.94) contrast(0.96);
    }}
    .motion-idle-breathe .xiao-shu-inner {{ animation: breathe 2400ms ease-in-out infinite; }}
    .motion-soft-bounce .xiao-shu-inner {{ animation: soft-bounce 900ms ease-in-out infinite; }}
    .motion-sorting-glow .status-dot {{ animation: glow 1200ms ease-in-out infinite; }}
    .motion-look-sideways .xiao-shu-inner {{ animation: look-sideways 1600ms ease-in-out infinite; }}
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
    .variant-panel {{
      margin-top: 18px;
      border-top: 1px solid var(--line);
      padding-top: 14px;
    }}
    .variant-panel[hidden] {{
      display: none;
    }}
    .variant-panel h2 {{
      margin: 0 0 10px;
      font-size: 15px;
      letter-spacing: 0;
    }}
    .variant-options {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
      gap: 10px;
    }}
    .variant-button {{
      min-height: 70px;
      text-align: left;
      border: 1px solid var(--line);
      background: var(--surface);
      color: var(--fg);
      padding: 10px 12px;
      cursor: pointer;
      font: inherit;
    }}
    .variant-button.is-active {{
      border-color: var(--coral);
      box-shadow: inset 4px 0 0 var(--coral);
    }}
    .variant-button span,
    .variant-button small {{
      display: block;
      min-width: 0;
      overflow-wrap: anywhere;
      word-break: break-word;
    }}
    .variant-button small {{ color: var(--muted); margin-top: 4px; }}
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
        <div class="xiao-shu sprite-backed {initial_classes}" data-xiao-shu data-current-frame="">
          <div class="xiao-shu-shadow"></div>
          <div class="xiao-shu-sprite" data-sprite-frame aria-hidden="true"></div>
          <div class="sprite-alert-mark" aria-hidden="true"></div>
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
          <dt>variant</dt><dd data-variant>{active_variant_label}</dd>
          <dt>asset</dt><dd data-asset><span>pet={asset_pet_id}</span><span>route={sprite_route}</span><span>mode=read-only spritesheet</span></dd>
          <dt>voice</dt><dd data-voice-linkage><span>preview={active_voice_text}</span><span>gate={active_voice_gate}</span><span>requires_gate={active_voice_required}</span><span>emits_audio={active_voice_audio}</span></dd>
          <dt>safety</dt><dd><span>writes_files={writes_files}</span><span>mutates_renderer={mutates_renderer}</span><span>pet_package={pet_mutation}</span></dd>
          <dt>mode</dt><dd>sidecar-only browser view</dd>
        </dl>
      </aside>
    </section>
    <nav class="tracks" aria-label="renderer tracks">
      {track_buttons}
    </nav>
    <section class="variant-panel" data-variant-panel hidden>
      <h2 data-variant-title>Renderer Variants</h2>
      <div class="variant-options" data-variant-options></div>
    </section>
  </main>
  <script type="application/json" id="renderer-data">{data_json}</script>
  <script>
    const payload = JSON.parse(document.getElementById("renderer-data").textContent);
    const view = payload.renderer_view || {{}};
    const tracks = Array.isArray(view.tracks) ? view.tracks : [];
    const figure = document.querySelector("[data-xiao-shu]");
    const spriteFrame = document.querySelector("[data-sprite-frame]");
    const tokenEl = document.querySelector("[data-token]");
    const stateEl = document.querySelector("[data-state]");
    const variantEl = document.querySelector("[data-variant]");
    const assetEl = document.querySelector("[data-asset]");
    const voiceEl = document.querySelector("[data-voice-linkage]");
    const variantPanel = document.querySelector("[data-variant-panel]");
    const variantTitle = document.querySelector("[data-variant-title]");
    const variantOptions = document.querySelector("[data-variant-options]");
    const buttons = Array.from(document.querySelectorAll("[data-track-index]"));
    let trackIndex = {active_track_index};
    let variantId = {active_variant_json};
    let frameIndex = 0;
    let timer = null;
    const defaultSpriteRoute = {sprite_route_json};
    const defaultAssetPetId = {asset_pet_id_json};
    let defaultSpriteAvailable = true;
    const spriteRows = {{
      "xiao_shu::soft_bounce::low": {{ row: 0, frames: 6, alert: false }},
      "xiao_shu::idle_breathe::low": {{ row: 0, frames: 6, alert: false }},
      "xiao_shu::sorting_glow::medium": {{ row: 8, frames: 6, alert: false }},
      "xiao_shu::look_sideways::medium": {{ row: 6, frames: 6, alert: false }},
      "xiao_shu::alert_peek::medium": {{ row: 5, frames: 8, alert: true }}
    }};

    function activeTrack() {{
      return tracks[trackIndex] || tracks[0] || {{ frames: [] }};
    }}

    function trackVariants(track) {{
      return Array.isArray(track.semantic_variants) ? track.semantic_variants : [];
    }}

    function defaultVariant(variants) {{
      return variants.find((variant) => Boolean(variant.default)) || variants[0] || null;
    }}

    function activeVariant(track) {{
      const variants = trackVariants(track);
      if (!variants.length) {{
        return null;
      }}
      return variants.find((variant) => variant.variant_id === variantId) || defaultVariant(variants);
    }}

    function variantChoreography(track) {{
      const variant = activeVariant(track);
      const choreography = variant && variant.frame_choreography;
      if (!choreography || !Array.isArray(choreography.frames) || choreography.frames.length === 0) {{
        return null;
      }}
      return choreography;
    }}

    function choreographyFrames(track) {{
      const choreography = variantChoreography(track);
      return choreography ? choreography.frames : null;
    }}

    function playbackFrameCount(track, stateFrames) {{
      const spriteFrames = choreographyFrames(track);
      if (spriteFrames) {{
        return spriteFrames.length;
      }}
      return Math.max(1, stateFrames.length);
    }}

    function stateFrameForOrdinal(stateFrames, ordinal, playbackCount) {{
      if (!stateFrames.length) {{
        return null;
      }}
      if (playbackCount <= 1) {{
        return stateFrames[0];
      }}
      const stateIndex = Math.min(
        stateFrames.length - 1,
        Math.round((Number(ordinal || 0) / (playbackCount - 1)) * (stateFrames.length - 1))
      );
      return stateFrames[stateIndex] || stateFrames[0];
    }}

    function setActiveButton() {{
      buttons.forEach((button) => {{
        button.classList.toggle("is-active", Number(button.dataset.trackIndex) === trackIndex);
      }});
    }}

    function updateVariantLabel() {{
      if (!variantEl) {{
        return;
      }}
      const variant = activeVariant(activeTrack());
      if (!variant) {{
        variantEl.textContent = "default";
        return;
      }}
      variantEl.textContent = `${{variant.variant_id || "variant"}} / ${{variant.label || "semantic option"}}`;
    }}

    function setActiveVariantButton() {{
      if (!variantOptions) {{
        return;
      }}
      Array.from(variantOptions.querySelectorAll("[data-variant-id]")).forEach((button) => {{
        button.classList.toggle("is-active", button.dataset.variantId === variantId);
      }});
      updateVariantLabel();
    }}

    function updateUrl(track) {{
      if (!track.token || !window.history || !window.URL) {{
        return;
      }}
      const url = new URL(window.location.href);
      url.searchParams.set("track", track.token);
      const variant = activeVariant(track);
      if (variant && variant.variant_id) {{
        url.searchParams.set("variant", variant.variant_id);
      }} else {{
        url.searchParams.delete("variant");
      }}
      window.history.replaceState(null, "", url);
    }}

    function renderVariantButtons() {{
      if (!variantPanel || !variantOptions) {{
        updateVariantLabel();
        return;
      }}
      const track = activeTrack();
      const variants = trackVariants(track);
      variantOptions.textContent = "";
      if (variantTitle) {{
        variantTitle.textContent = track.semantic_variant_review
          ? "Alert Peek Semantic Variants"
          : "Sidecar Track Variants";
      }}
      if (!variants.length) {{
        variantId = "";
        variantPanel.hidden = true;
        updateVariantLabel();
        return;
      }}
      const selected = activeVariant(track) || defaultVariant(variants);
      variantId = selected && selected.variant_id ? selected.variant_id : "";
      variantPanel.hidden = false;
      variants.forEach((variant) => {{
        const button = document.createElement("button");
        button.type = "button";
        button.className = "variant-button";
        button.dataset.variantId = variant.variant_id || "";
        const label = document.createElement("span");
        label.textContent = variant.label || variant.variant_id || "variant";
        const detail = document.createElement("small");
        const choreography = variant.frame_choreography || {{}};
        const choreoFrames = Array.isArray(choreography.frames) ? choreography.frames.length : 0;
        const asset = variant.sidecar_asset && variant.sidecar_asset.asset_id ? ` asset=${{variant.sidecar_asset.asset_id}}` : "";
        detail.textContent = `row=${{variant.sprite_row}} frames=${{variant.sprite_frames}} choreo=${{choreoFrames}} css_motion=${{Boolean(choreography.uses_css_motion)}}${{asset}}`;
        const intent = document.createElement("small");
        intent.textContent = variant.intent || "";
        button.append(label, detail, intent);
        button.addEventListener("click", () => {{
          variantId = button.dataset.variantId || "";
          frameIndex = 0;
          if (timer) window.clearTimeout(timer);
          setActiveVariantButton();
          applyFrame();
          updateUrl(activeTrack());
        }});
        variantOptions.appendChild(button);
      }});
      setActiveVariantButton();
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

    function setAssetLabel(spriteRoute, sidecarAsset, fallbackReason) {{
      if (!assetEl) {{
        return;
      }}
      assetEl.textContent = "";
      const parts = fallbackReason
        ? [
            "fallback=css silhouette",
            `missing=${{defaultSpriteRoute || ""}}`,
            `reason=${{fallbackReason}}`,
            "mode=read-only visual fallback"
          ]
        : sidecarAsset
        ? [
            `sidecar=${{sidecarAsset.asset_id || "prototype"}}`,
            `route=${{spriteRoute || ""}}`,
            `format=${{sidecarAsset.format || "image/svg+xml"}}`,
            "mode=read-only sidecar spritesheet"
          ]
        : [
            `pet=${{defaultAssetPetId || "xiao-shu-dev"}}`,
            `route=${{spriteRoute || defaultSpriteRoute}}`,
            "mode=read-only spritesheet"
          ];
      parts.forEach((part) => {{
        const span = document.createElement("span");
        span.textContent = part;
        assetEl.appendChild(span);
      }});
    }}

    function setVoiceLinkageLabel(track) {{
      if (!voiceEl) {{
        return;
      }}
      const review = track && track.semantic_variant_review ? track.semantic_variant_review : null;
      const preview = review && review.voice_linkage_preview ? review.voice_linkage_preview : null;
      const gate = preview && preview.gate ? preview.gate : {{}};
      const voice = preview && preview.voice ? preview.voice : {{}};
      const parts = preview
        ? [
            `preview=${{preview.utterance || "visual-only preview"}}`,
            `gate=${{gate.dry_run_route || "-"}}`,
            `requires_gate=${{Boolean(voice.requires_explicit_emit_gate)}}`,
            `emits_audio=${{Boolean(preview.emits_audio)}}`
          ]
        : [
            "preview=none",
            "gate=-",
            "requires_gate=true",
            "emits_audio=false"
          ];
      voiceEl.textContent = "";
      parts.forEach((part) => {{
        const span = document.createElement("span");
        span.textContent = part;
        voiceEl.appendChild(span);
      }});
    }}

    function applySpriteFrame(track, ordinal, choreoFrame) {{
      if (!spriteFrame || !figure) {{
        return;
      }}
      const config = {{ ...(spriteRows[track.token] || {{ row: 0, frames: 6, alert: false }}) }};
      const variant = activeVariant(track);
      const sidecarAsset = variant && variant.sidecar_asset ? variant.sidecar_asset : null;
      const hasVariantSprite = Boolean(variant && (variant.asset_route || sidecarAsset));
      if (!hasVariantSprite && !defaultSpriteAvailable) {{
        spriteFrame.style.backgroundImage = "";
        setAssetLabel("", null, "pet_spritesheet_unavailable");
        figure.dataset.spriteVariant = "css_fallback";
        figure.dataset.spriteAsset = "css_silhouette";
        figure.dataset.spritePhase = "";
        figure.classList.toggle("sprite-backed", false);
        figure.classList.toggle("sprite-choreographed", false);
        figure.classList.toggle("sprite-sidecar-asset", false);
        figure.classList.toggle("sprite-alert", false);
        figure.classList.toggle("sprite-attention-visible", false);
        return;
      }}
      const spriteRoute = variant && (variant.asset_route || (sidecarAsset && sidecarAsset.route))
        ? variant.asset_route || sidecarAsset.route
        : defaultSpriteRoute;
      if (variant) {{
        config.row = Number(variant.sprite_row || config.row || 0);
        config.frames = Number(variant.sprite_frames || config.frames || 1);
        config.alert = Boolean(variant.alert_mark);
      }}
      if (choreoFrame) {{
        config.row = Number(choreoFrame.row ?? config.row ?? 0);
        config.frames = Number(config.frames || 1);
        config.alert = Boolean(config.alert);
      }}
      const column = choreoFrame
        ? Number(choreoFrame.col ?? 0)
        : Number(ordinal || 0) % Number(config.frames || 1);
      const x = -column * 192;
      const y = -Number(config.row || 0) * 208;
      spriteFrame.style.backgroundImage = "url(" + JSON.stringify(String(spriteRoute || defaultSpriteRoute)) + ")";
      spriteFrame.style.backgroundPosition = `${{x}}px ${{y}}px`;
      setAssetLabel(spriteRoute, sidecarAsset, "");
      figure.dataset.spriteVariant = variant && variant.variant_id ? variant.variant_id : "default";
      figure.dataset.spriteAsset = sidecarAsset && sidecarAsset.asset_id ? sidecarAsset.asset_id : "official_pet";
      figure.dataset.spritePhase = choreoFrame && choreoFrame.phase ? choreoFrame.phase : "";
      figure.classList.toggle("sprite-backed", true);
      figure.classList.toggle("sprite-choreographed", Boolean(choreoFrame));
      figure.classList.toggle("sprite-sidecar-asset", Boolean(sidecarAsset));
      figure.classList.toggle("sprite-alert", Boolean(config.alert));
      const markVisible = Boolean(config.alert) && (!choreoFrame || choreoFrame.mark !== false);
      figure.classList.toggle("sprite-attention-visible", markVisible);
    }}

    function applyFrame() {{
      const track = activeTrack();
      const frames = Array.isArray(track.frames) ? track.frames : [];
      if (!figure || frames.length === 0) {{
        return;
      }}
      const spriteFrames = choreographyFrames(track);
      const playbackCount = playbackFrameCount(track, frames);
      const playbackOrdinal = frameIndex % playbackCount;
      const frame = stateFrameForOrdinal(frames, playbackOrdinal, playbackCount) || frames[0];
      const choreoFrame = spriteFrames ? spriteFrames[playbackOrdinal] : null;
      figure.className = "xiao-shu sprite-backed " + (frame.css_classes || "pose-neutral-idle expression-calm-eyes motion-idle-breathe accessory-none");
      applySpriteFrame(track, playbackOrdinal, choreoFrame);
      figure.dataset.currentFrame = frame.frame_id || "";
      if (tokenEl) tokenEl.textContent = track.token || "xiao_shu::unknown";
      setStateLabel(frame.state_label || "");
      updateVariantLabel();
      setVoiceLinkageLabel(track);
      const nextFrame = frames[Math.min(frames.length - 1, playbackOrdinal + 1)] || frame;
      const currentAt = Number(frame.at_ms || 0);
      const nextAt = Number(nextFrame.at_ms || 0);
      const duration = Number(track.duration_ms || 1000);
      let delay = choreoFrame && choreoFrame.hold_ms
        ? Number(choreoFrame.hold_ms)
        : playbackOrdinal < frames.length - 1 ? nextAt - currentAt : duration - currentAt;
      delay = Math.max(choreoFrame ? 80 : 180, delay);
      frameIndex = (frameIndex + 1) % playbackCount;
      timer = window.setTimeout(applyFrame, delay);
    }}

    buttons.forEach((button) => {{
      button.addEventListener("click", () => {{
        trackIndex = Number(button.dataset.trackIndex || 0);
        frameIndex = 0;
        if (timer) window.clearTimeout(timer);
        setActiveButton();
        renderVariantButtons();
        applyFrame();
        updateUrl(activeTrack());
      }});
    }});
    setActiveButton();
    renderVariantButtons();
    applyFrame();
    fetch(defaultSpriteRoute, {{ method: "HEAD", cache: "no-store" }})
      .then((response) => {{
        defaultSpriteAvailable = Boolean(response && response.ok);
      }})
      .catch(() => {{
        defaultSpriteAvailable = false;
      }})
      .finally(() => {{
        if (!defaultSpriteAvailable) {{
          if (timer) window.clearTimeout(timer);
          frameIndex = 0;
          applyFrame();
        }}
      }});
  </script>
</body>
</html>"#,
        track_count = track_count,
        input = input_label,
        input_title = input,
        generated_at = generated_at,
        browser_pixels = browser_pixels,
        sprite_route = sprite_route,
        initial_classes = initial_classes,
        first_token = first_token,
        first_state = first_state_html,
        active_variant_label = active_variant_label,
        active_variant_json = active_variant_json,
        asset_pet_id = asset_pet_id,
        asset_pet_id_json = asset_pet_id_json,
        active_track_index = active_track_index,
        active_voice_text = active_voice_text,
        active_voice_gate = active_voice_gate,
        active_voice_audio = active_voice_audio,
        active_voice_required = active_voice_required,
        writes_files = writes_files,
        mutates_renderer = mutates_renderer,
        pet_mutation = pet_mutation,
        track_buttons = track_buttons,
        data_json = data_json,
        sprite_route_json = sprite_route_json,
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
    cortex_review_report: &Value,
    cortex_review_decisions: &Value,
    cortex_voice_policy: &Value,
    cortex_voice_request: &Value,
    cortex_voice_confirm: &Value,
    cortex_voice_action_preview: &Value,
    xiao_shu_action_request: &Value,
    xiao_shu_action_requests: &Value,
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
    let review_report_html = avatar_surface_review_report_html(cortex_review_report, q);
    let review_decisions_html = avatar_surface_review_decisions_html(cortex_review_decisions, q);
    let voice_policy_html = avatar_surface_voice_policy_html(cortex_voice_policy, q);
    let voice_request_html = avatar_surface_voice_request_html(cortex_voice_request, q);
    let voice_confirm_html = avatar_surface_voice_confirm_html(cortex_voice_confirm, q);
    let voice_action_preview_html =
        avatar_surface_voice_action_preview_html(cortex_voice_action_preview, q);
    let xiao_shu_action_request_html =
        avatar_surface_xiao_shu_action_request_html(xiao_shu_action_request, q);
    let xiao_shu_action_requests_html =
        avatar_surface_xiao_shu_action_requests_html(xiao_shu_action_requests, q);
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
    .compact-list {{
      display: grid;
      gap: 8px;
      margin: 12px 0 0;
      padding: 0;
      list-style: none;
    }}
    .compact-list li {{
      display: grid;
      gap: 2px;
      padding-top: 8px;
      border-top: 1px solid var(--line);
    }}
    .compact-list li span {{
      color: var(--muted);
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
    {review_report_html}
    {review_decisions_html}
    {voice_policy_html}
    {voice_request_html}
    {voice_confirm_html}
    {voice_action_preview_html}
    {xiao_shu_action_request_html}
    {xiao_shu_action_requests_html}
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
        review_report_html = review_report_html,
        review_decisions_html = review_decisions_html,
        voice_policy_html = voice_policy_html,
        voice_request_html = voice_request_html,
        voice_confirm_html = voice_confirm_html,
        voice_action_preview_html = voice_action_preview_html,
        xiao_shu_action_request_html = xiao_shu_action_request_html,
        xiao_shu_action_requests_html = xiao_shu_action_requests_html,
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

    #[cfg(target_os = "linux")]
    fn write_avatar_aura_p3_fixture(root: &std::path::Path) {
        use sha2::{Digest, Sha256};
        use std::os::unix::fs::PermissionsExt;

        let sidecar_dir = root.join("nested");
        let assets_dir = sidecar_dir.join("assets");
        for directory in [root, sidecar_dir.as_path(), assets_dir.as_path()] {
            std::fs::create_dir_all(directory).expect("create trusted Aura directory");
            std::fs::set_permissions(directory, std::fs::Permissions::from_mode(0o700))
                .expect("set trusted Aura directory permissions");
        }

        let uniform_bytes = vec![7_u8; 1_024];
        let digest_bytes = br#"{"items":[{"title":"working"}]}"#;
        let uniform_sha256 = format!("{:x}", Sha256::digest(&uniform_bytes));
        let digest_sha256 = format!("{:x}", Sha256::digest(digest_bytes));
        let uniform_path = assets_dir.join("uniform.bin");
        let digest_path = sidecar_dir.join("digest.json");
        let sidecar_path = sidecar_dir.join("aura.json");
        std::fs::write(&uniform_path, &uniform_bytes).expect("write uniform fixture");
        std::fs::write(&digest_path, digest_bytes).expect("write digest fixture");
        let sidecar = json!({
            "schema_version": "lcc.aura_io.v1",
            "renderer_input": {
                "kind": "tfe_uniform_f32x256",
                "contract_version": 1,
                "path": "assets/uniform.bin",
                "sha256": format!("sha256:{uniform_sha256}"),
                "uniform_len": 256,
                "bin_bytes": 1_024,
                "encoding": "little_endian_f32"
            },
            "source_digest": {
                "schema_version": "1.0",
                "item_count": 1,
                "json_path": "digest.json",
                "json_sha256": format!("sha256:{digest_sha256}")
            },
            "visible_signal_source": "curated_digest_only",
            "shadow_signal_policy": "shadow_only_until_falsified",
            "source_state": {
                "mode": "working",
                "activity_state": "aura-p3-preload",
                "focus": "face-aura",
                "risk_level": "low"
            }
        });
        std::fs::write(
            &sidecar_path,
            serde_json::to_vec_pretty(&sidecar).expect("serialize sidecar fixture"),
        )
        .expect("write sidecar fixture");
        for file in [&uniform_path, &digest_path, &sidecar_path] {
            std::fs::set_permissions(file, std::fs::Permissions::from_mode(0o600))
                .expect("set trusted Aura file permissions");
        }
    }

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

    #[cfg(target_os = "linux")]
    #[tokio::test]
    async fn avatar_aura_enabled_config_preloads_default_snapshot_before_router() {
        use std::collections::BTreeMap;

        let temp = tempfile::tempdir().expect("create Aura P3 fixture parent");
        let root = temp.path().join("trusted-aura-root");
        write_avatar_aura_p3_fixture(&root);

        let values = BTreeMap::from([
            (
                "AGENT_BRIDGE_AVATAR_AURA_IO_ENABLE".to_string(),
                "1".to_string(),
            ),
            (
                "AGENT_BRIDGE_AVATAR_AURA_IO_ROOT".to_string(),
                root.display().to_string(),
            ),
            (
                "AGENT_BRIDGE_AVATAR_AURA_IO_ENTRY".to_string(),
                "nested/aura.json".to_string(),
            ),
        ]);
        let config =
            AvatarAuraIoStartupConfig::from_values(&values).expect("valid enabled startup config");
        let store: Arc<dyn StateStore> = Arc::new(
            ab_store::SqliteStore::open(&temp.path().join("state.db"))
                .await
                .expect("open isolated test store"),
        );

        let state = prepare_app_state(store, config)
            .await
            .expect("preload Aura snapshot before router construction");
        let report = state
            .avatar_aura_io_default
            .as_ref()
            .expect("default Aura snapshot installed")
            .to_json_value();

        assert_eq!(report["ok"], true);
        assert_eq!(report["schema_version"], "lcc.aura_io.v1");
        assert!(report.get("sidecar_path").is_none());
        assert!(report.get("uniform_path").is_none());
        assert!(report.get("digest_path").is_none());
        assert!(!report.to_string().contains(&root.display().to_string()));
    }

    #[test]
    fn avatar_aura_startup_config_enforces_activation_matrix() {
        use std::collections::BTreeMap;

        let disabled_cases = [
            BTreeMap::new(),
            BTreeMap::from([(
                "AGENT_BRIDGE_AVATAR_AURA_IO_ENABLE".to_string(),
                "".to_string(),
            )]),
            BTreeMap::from([(
                "AGENT_BRIDGE_AVATAR_AURA_IO_ENABLE".to_string(),
                "0".to_string(),
            )]),
        ];
        for values in disabled_cases {
            assert_eq!(
                AvatarAuraIoStartupConfig::from_values(&values).expect("canonical disabled form"),
                AvatarAuraIoStartupConfig::Disabled
            );
        }

        let invalid_cases = [
            (
                BTreeMap::from([(
                    "AGENT_BRIDGE_AVATAR_AURA_IO_ENABLE".to_string(),
                    "yes".to_string(),
                )]),
                "avatar_aura_io_config_activation_invalid",
            ),
            (
                BTreeMap::from([(
                    "AGENT_BRIDGE_AVATAR_AURA_IO_ROOT".to_string(),
                    "/tmp/aura".to_string(),
                )]),
                "avatar_aura_io_config_without_activation",
            ),
            (
                BTreeMap::from([
                    (
                        "AGENT_BRIDGE_AVATAR_AURA_IO_ENABLE".to_string(),
                        "0".to_string(),
                    ),
                    (
                        "AGENT_BRIDGE_AVATAR_AURA_IO_ENTRY".to_string(),
                        "nested/aura.json".to_string(),
                    ),
                ]),
                "avatar_aura_io_config_without_activation",
            ),
            (
                BTreeMap::from([(
                    "AGENT_BRIDGE_AVATAR_AURA_IO_ENABLE".to_string(),
                    "1".to_string(),
                )]),
                "avatar_aura_io_config_root_missing",
            ),
            (
                BTreeMap::from([
                    (
                        "AGENT_BRIDGE_AVATAR_AURA_IO_ENABLE".to_string(),
                        "1".to_string(),
                    ),
                    (
                        "AGENT_BRIDGE_AVATAR_AURA_IO_ROOT".to_string(),
                        "/tmp/aura".to_string(),
                    ),
                ]),
                "avatar_aura_io_config_entry_missing",
            ),
        ];
        for (values, expected_code) in invalid_cases {
            let error = AvatarAuraIoStartupConfig::from_values(&values)
                .expect_err("invalid startup config must fail closed");
            assert_eq!(error.code(), expected_code);
            assert!(!error.to_string().contains("/tmp/aura"));
            assert!(!error.to_string().contains("nested/aura.json"));
        }
    }

    #[test]
    fn avatar_aura_startup_config_rejects_ambient_root_and_entry_authority() {
        use std::collections::BTreeMap;

        fn enabled_values(root: &str, entry: &str) -> BTreeMap<String, String> {
            BTreeMap::from([
                (
                    "AGENT_BRIDGE_AVATAR_AURA_IO_ENABLE".to_string(),
                    "1".to_string(),
                ),
                (
                    "AGENT_BRIDGE_AVATAR_AURA_IO_ROOT".to_string(),
                    root.to_string(),
                ),
                (
                    "AGENT_BRIDGE_AVATAR_AURA_IO_ENTRY".to_string(),
                    entry.to_string(),
                ),
                ("HOME".to_string(), "/home/operator".to_string()),
            ])
        }

        let cases = [
            (
                enabled_values("relative/root", "nested/aura.json"),
                "avatar_aura_io_config_root_not_absolute",
            ),
            (
                enabled_values("/", "nested/aura.json"),
                "avatar_aura_io_config_root_is_filesystem_root",
            ),
            (
                enabled_values("/home/operator", "nested/aura.json"),
                "avatar_aura_io_config_root_is_home",
            ),
            (
                enabled_values("/home/operator/.", "nested/aura.json"),
                "avatar_aura_io_config_root_is_home",
            ),
            (
                enabled_values("/srv/avatar-aura/../avatar-aura", "nested/aura.json"),
                "avatar_aura_io_config_root_not_normalized",
            ),
            (
                enabled_values("/srv/avatar-aura", "/tmp/aura.json"),
                "avatar_aura_io_config_entry_not_relative",
            ),
            (
                enabled_values("/srv/avatar-aura", "../aura.json"),
                "avatar_aura_io_config_entry_parent_component",
            ),
        ];

        for (values, expected_code) in cases {
            let error = AvatarAuraIoStartupConfig::from_values(&values)
                .expect_err("ambient root or entry authority must reject");
            assert_eq!(error.code(), expected_code);
            assert!(!error.to_string().contains("relative/root"));
            assert!(!error.to_string().contains("/home/operator"));
            assert!(!error.to_string().contains("/tmp/aura.json"));
        }
    }

    #[tokio::test]
    async fn avatar_aura_enabled_preload_failure_prevents_listener_bind() {
        use std::collections::BTreeMap;
        use std::sync::atomic::{AtomicUsize, Ordering};

        let temp = tempfile::tempdir().expect("create startup-order fixture parent");
        let missing_root = temp.path().join("missing-aura-root");
        let values = BTreeMap::from([
            (
                "AGENT_BRIDGE_AVATAR_AURA_IO_ENABLE".to_string(),
                "1".to_string(),
            ),
            (
                "AGENT_BRIDGE_AVATAR_AURA_IO_ROOT".to_string(),
                missing_root.display().to_string(),
            ),
            (
                "AGENT_BRIDGE_AVATAR_AURA_IO_ENTRY".to_string(),
                "nested/aura.json".to_string(),
            ),
            (
                "HOME".to_string(),
                temp.path().join("home").display().to_string(),
            ),
        ]);
        let config = AvatarAuraIoStartupConfig::from_values(&values)
            .expect("syntactically valid enabled startup config");
        let store: Arc<dyn StateStore> = Arc::new(
            ab_store::SqliteStore::open(&temp.path().join("state.db"))
                .await
                .expect("open isolated test store"),
        );
        let bind_count = Arc::new(AtomicUsize::new(0));
        let observed_bind_count = bind_count.clone();
        let binder = move |_addr: String| {
            let bind_count = bind_count.clone();
            async move {
                bind_count.fetch_add(1, Ordering::SeqCst);
                tokio::net::TcpListener::bind("127.0.0.1:0").await
            }
        };

        let result = prepare_daemon_http_with_binder(store, "127.0.0.1:0", config, binder).await;
        let error = match result {
            Ok(_) => panic!("unsafe enabled preload must fail before binding"),
            Err(error) => error,
        };

        assert_eq!(observed_bind_count.load(Ordering::SeqCst), 0);
        assert!(error
            .to_string()
            .contains("avatar_aura_io_startup_preload_"));
        assert!(!error
            .to_string()
            .contains(&missing_root.display().to_string()));
    }

    #[cfg(target_os = "linux")]
    #[tokio::test]
    async fn avatar_aura_symlink_root_prevents_listener_bind() {
        use std::collections::BTreeMap;
        use std::os::unix::fs::{symlink, PermissionsExt};
        use std::sync::atomic::{AtomicUsize, Ordering};

        let temp = tempfile::tempdir().expect("create symlink-root fixture parent");
        let actual_root = temp.path().join("actual-aura-root");
        let symlink_root = temp.path().join("symlink-aura-root");
        std::fs::create_dir(&actual_root).expect("create actual Aura root");
        std::fs::set_permissions(&actual_root, std::fs::Permissions::from_mode(0o700))
            .expect("set trusted Aura root permissions");
        symlink(&actual_root, &symlink_root).expect("create Aura root symlink");
        let values = BTreeMap::from([
            (
                "AGENT_BRIDGE_AVATAR_AURA_IO_ENABLE".to_string(),
                "1".to_string(),
            ),
            (
                "AGENT_BRIDGE_AVATAR_AURA_IO_ROOT".to_string(),
                symlink_root.display().to_string(),
            ),
            (
                "AGENT_BRIDGE_AVATAR_AURA_IO_ENTRY".to_string(),
                "aura.json".to_string(),
            ),
            (
                "HOME".to_string(),
                temp.path().join("home").display().to_string(),
            ),
        ]);
        let config = AvatarAuraIoStartupConfig::from_values(&values)
            .expect("symlink root is rejected by capability admission, not pure parsing");
        let store: Arc<dyn StateStore> = Arc::new(
            ab_store::SqliteStore::open(&temp.path().join("state.db"))
                .await
                .expect("open isolated test store"),
        );
        let bind_count = Arc::new(AtomicUsize::new(0));
        let observed_bind_count = bind_count.clone();
        let binder = move |_addr: String| {
            let bind_count = bind_count.clone();
            async move {
                bind_count.fetch_add(1, Ordering::SeqCst);
                tokio::net::TcpListener::bind("127.0.0.1:0").await
            }
        };

        let result = prepare_daemon_http_with_binder(store, "127.0.0.1:0", config, binder).await;
        let error = match result {
            Ok(_) => panic!("symlink root must fail before binding"),
            Err(error) => error,
        };

        assert_eq!(observed_bind_count.load(Ordering::SeqCst), 0);
        assert!(error
            .to_string()
            .contains("avatar_aura_io_startup_preload_"));
        assert!(!error
            .to_string()
            .contains(&symlink_root.display().to_string()));
        assert!(!error
            .to_string()
            .contains(&actual_root.display().to_string()));
    }

    #[cfg(target_os = "linux")]
    #[tokio::test]
    async fn avatar_aura_default_selector_uses_cached_report_after_root_removed() {
        use std::collections::BTreeMap;

        let temp = tempfile::tempdir().expect("create Aura selector fixture parent");
        let root = temp.path().join("trusted-aura-root");
        write_avatar_aura_p3_fixture(&root);
        let values = BTreeMap::from([
            (
                "AGENT_BRIDGE_AVATAR_AURA_IO_ENABLE".to_string(),
                "1".to_string(),
            ),
            (
                "AGENT_BRIDGE_AVATAR_AURA_IO_ROOT".to_string(),
                root.display().to_string(),
            ),
            (
                "AGENT_BRIDGE_AVATAR_AURA_IO_ENTRY".to_string(),
                "nested/aura.json".to_string(),
            ),
            (
                "HOME".to_string(),
                temp.path().join("home").display().to_string(),
            ),
        ]);
        let config =
            AvatarAuraIoStartupConfig::from_values(&values).expect("valid enabled startup config");
        let disabled_state = isolated_avatar_renderer_state(&temp).await;
        let enabled_state = prepare_app_state(disabled_state.store.clone(), config)
            .await
            .expect("preload default Aura report");

        std::fs::remove_dir_all(&root).expect("remove Aura root after preload");
        assert!(!root.exists());

        for _ in 0..2 {
            let query = isolated_avatar_renderer_query(Some("default".to_string()));
            let payload = avatar_linux_renderer_payload(&enabled_state, &query)
                .await
                .expect("default selector must use cached report only");
            assert_eq!(payload["aura_io"]["ok"], true);
            assert_eq!(payload["input"]["aura_io"], "default");
            assert!(!payload.to_string().contains(&root.display().to_string()));

            let href = avatar_linux_renderer_state_href(&query);
            let html = avatar_surface_linux_renderer_html(&payload, 1, &href, false);
            assert!(html.contains("aura_io=default"));
            assert!(!html.contains(&root.display().to_string()));
        }

        for selector in ["", "other", "/tmp/aura.json"] {
            let result = avatar_linux_renderer_payload(
                &enabled_state,
                &isolated_avatar_renderer_query(Some(selector.to_string())),
            )
            .await;
            assert_eq!(
                result,
                Err((StatusCode::FORBIDDEN, "aura_io_not_authorized".to_string()))
            );
        }

        let disabled_result = avatar_linux_renderer_payload(
            &disabled_state,
            &isolated_avatar_renderer_query(Some("default".to_string())),
        )
        .await;
        assert_eq!(
            disabled_result,
            Err((
                StatusCode::FORBIDDEN,
                "aura_io_file_access_disabled".to_string()
            ))
        );
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

    #[tokio::test]
    async fn semantic_bus_runtime_conformance_endpoint_is_read_only_json() {
        let Json(payload) =
            semantic_bus_runtime_conformance_endpoint(Query(SemanticBusRuntimeConformanceQuery {
                include_runtime_health: Some(false),
                ..Default::default()
            }))
            .await;

        assert_eq!(
            payload["schema"].as_str(),
            Some("agent_bridge.semantic_bus.runtime_conformance.v0")
        );
        assert_eq!(payload["read_only"].as_bool(), Some(true));
        assert_eq!(payload["live_checks_executed"].as_bool(), Some(false));
        assert_eq!(
            payload["verification"]["verdict"].as_str(),
            Some("not_checked")
        );
        assert_eq!(
            payload["windows_uia_runtime_slot"]["adapter_id"].as_str(),
            Some("windows_uia_runtime_adapter")
        );
    }

    #[test]
    fn linux_renderer_html_embeds_plan_and_sidecar_asset_route() {
        let payload = json!({
            "surface": "linux_codex_avatar_renderer_state",
            "read_only": true,
            "project": "agent-bridge",
            "selection": {"source": "projected_avatar", "fallback_reason": null},
            "state": {"mode": "working", "activity_state": "implementing"},
            "plan": {
                "track": "sorting_glow",
                "renderer_token": "xiao_shu::sorting_glow::medium",
                "asset_route": "/avatar-surface/sidecar-spritesheet?asset=xiao-shu-motion-canonical-sorting-glow-v3",
                "fallback_reason": null
            },
            "safety": {
                "codex_pet_package_mutation": false,
                "emits_audio": false,
                "controls_desktop": false
            },
            "aura_io": {
                "surface": "lcc_aura_io_intake",
                "schema_version": "lcc.aura_io.v1",
                "renderer_input_kind": "tfe_uniform_f32x256",
                "uniform_path": "/tmp/a2_working_uniform.bin",
                "digest_path": "/tmp/a2_working_digest.json",
                "visible_signal_source": "curated_digest_only",
                "shadow_signal_policy": "shadow_only_until_falsified",
                "uniform_file_sha256_matches": true,
                "digest_file_sha256_matches": true
            }
        });

        let html = avatar_surface_linux_renderer_html(
            &payload,
            1780294000,
            "/avatar-surface/linux-renderer-state?project=agent-bridge&include_stale=true",
            false,
        );

        assert!(html.contains("Linux Codex Avatar Renderer"));
        assert!(html.contains("data-track=\"sorting_glow\""));
        assert!(html.contains("xiao_shu::sorting_glow::medium"));
        assert!(html.contains(
            "/avatar-surface/sidecar-spritesheet?asset=xiao-shu-motion-canonical-sorting-glow-v3"
        ));
        assert!(html.contains("data-state-url=\"/avatar-surface/linux-renderer-state"));
        assert!(html.contains("setInterval(refreshRendererState, 1000)"));
        assert!(html.contains("fetch(stateUrl"));
        assert!(html.contains("function applyRendererPayload(nextPayload)"));
        assert!(html.contains("class=\"aura\""));
        assert!(html.contains("data-field=\"aura\""));
        assert!(html.contains("function applyAuraLayer(auraIo)"));
        assert!(html.contains("lcc_aura_io_intake"));
        assert!(html.contains("curated_digest_only"));
        assert!(html.contains("codex_pet_package_mutation=false"));
        assert!(html.contains("emits_audio=false"));
    }

    #[test]
    fn linux_renderer_html_transparent_mode_renders_pet_only_surface() {
        let payload = json!({
            "surface": "linux_codex_avatar_renderer_state",
            "read_only": true,
            "project": "agent-bridge",
            "selection": {"source": "projected_avatar", "fallback_reason": null},
            "state": {"mode": "verified", "activity_state": "dogfood"},
            "plan": {
                "track": "completion_nod",
                "renderer_token": "xiao_shu::completion_nod::low",
                "asset_route": "/avatar-surface/sidecar-spritesheet?asset=xiao-shu-v3-ai-completion-nod-v1",
                "fallback_reason": null
            },
            "safety": {
                "codex_pet_package_mutation": false,
                "emits_audio": false,
                "controls_desktop": false
            }
        });

        let html = avatar_surface_linux_renderer_html(
            &payload,
            1780294000,
            "/avatar-surface/linux-renderer-state?project=agent-bridge&include_stale=true&transparent=true",
            true,
        );

        assert!(html.contains("data-transparent=\"true\""));
        assert!(html.contains("background:transparent"));
        assert!(html.contains(".debug-panel { display:none; }"));
        assert!(html.contains("data-track=\"completion_nod\""));
        assert!(html.contains("xiao-shu-v3-ai-completion-nod-v1"));
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
    fn embed_backend_factory_dim_matches_vector_dim() {
        let b = build_raw_embed_backend();
        assert_eq!(
            b.dim(),
            ab_store::vector_dim(),
            "embedding backend dim must track the active model (768 since the gte default flip)"
        );
        let name = b.name();
        assert!(
            name == "fnv1a-hash-384"
                || name == "all-MiniLM-L6-v2"
                || name == "gte-multilingual-base",
            "unexpected backend name: {name}"
        );
    }

    #[test]
    fn embed_request_deserializes_text_field() {
        let req: EmbedRequest = serde_json::from_str(r#"{"text":"hello world"}"#).unwrap();
        assert_eq!(req.text, "hello world");
    }

    #[test]
    fn embed_response_metadata_exposes_hash_fallback_honestly() {
        let text = "cold model";
        let vector = HashBackend.embed(text);
        let (name, dim) = embed_response_metadata("gte-multilingual-base", 768, text, &vector);
        assert_eq!(name, "fnv1a-hash-384");
        assert_eq!(dim, vector.len());
    }

    #[test]
    fn embed_response_metadata_uses_actual_vector_length() {
        let vector = vec![0.1, 0.2, 0.3];
        let (name, dim) = embed_response_metadata("test-model", 768, "text", &vector);
        assert_eq!(name, "test-model");
        assert_eq!(dim, 3);
    }

    #[tokio::test]
    async fn embed_readiness_reports_hash_only_and_bounded_repair_status() {
        let temp = tempfile::tempdir().expect("create tempdir");
        let store: Arc<dyn StateStore> = Arc::new(
            ab_store::SqliteStore::open(&temp.path().join("state.db"))
                .await
                .expect("open temporary store"),
        );
        let status = EmbedMaintenanceStatus {
            phase: "skipped",
            batch_limit: 100,
            updated: 0,
            detail: Some("explicit hash backend".into()),
        };
        let Json(body) = embed_readiness_endpoint(State(AppState {
            store,
            embed_backend: Arc::new(HashBackend),
            embed_maintenance: Arc::new(Mutex::new(status)),
            avatar_aura_io_default: None,
        }))
        .await;

        assert_eq!(body["model_state"], "hash_only");
        assert_eq!(body["semantic_ready"], false);
        assert_eq!(body["automatic_repair"]["phase"], "skipped");
        assert_eq!(body["automatic_repair"]["batch_limit"], 100);
    }

    #[tokio::test]
    async fn avatar_heartbeat_health_rejects_unsafe_label_as_bad_request() {
        let temp = tempfile::tempdir().expect("create tempdir");
        let store: std::sync::Arc<dyn StateStore> = std::sync::Arc::new(
            ab_store::SqliteStore::open(&temp.path().join("state.db"))
                .await
                .expect("open temporary store"),
        );
        let result = avatar_heartbeat_health(
            State(AppState {
                store,
                embed_backend: build_raw_embed_backend(),
                embed_maintenance: Arc::new(Mutex::new(EmbedMaintenanceStatus::from_env())),
                avatar_aura_io_default: None,
            }),
            Query(AvatarHeartbeatHealthQuery {
                label: Some("/tmp/escape".to_string()),
                project: None,
                stale_secs: 300,
            }),
        )
        .await;

        let (status, message) = result.expect_err("unsafe label must be rejected");
        assert_eq!(status, StatusCode::BAD_REQUEST);
        assert!(
            message.contains("invalid heartbeat label"),
            "message={message}"
        );
    }

    #[test]
    fn avatar_surface_query_include_stale_disables_ttl() {
        let q = AvatarSurfaceQuery {
            project: Some("agent-bridge".into()),
            role: None,
            aura_io: None,
            max_idle_secs: 300,
            include_stale: true,
            limit: 999,
            refresh_secs: 1,
            stale_secs: 1_000_000,
            include_raw_presence: false,
            include_compat: false,
            transparent: false,
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
    fn avatar_linux_renderer_state_href_preserves_only_default_aura_selector() {
        let default_query = AvatarSurfaceQuery {
            project: Some("agent-bridge".into()),
            role: Some("main".into()),
            aura_io: Some("default".into()),
            max_idle_secs: 300,
            include_stale: true,
            limit: 5,
            refresh_secs: 10,
            stale_secs: 300,
            include_raw_presence: false,
            include_compat: false,
            transparent: true,
        };

        let href = avatar_linux_renderer_state_href(&default_query);

        assert!(href.starts_with("/avatar-surface/linux-renderer-state?"));
        assert!(href.contains("project=agent-bridge"));
        assert!(href.contains("role=main"));
        assert!(href.contains("aura_io=default"));
        assert!(href.contains("include_stale=true"));
        assert!(href.contains("transparent=true"));

        for selector in ["", "other", "/tmp/a2_working_aura_io.json"] {
            let query = AvatarSurfaceQuery {
                aura_io: Some(selector.to_string()),
                ..AvatarSurfaceQuery {
                    project: None,
                    role: None,
                    aura_io: None,
                    max_idle_secs: 300,
                    include_stale: false,
                    limit: 5,
                    refresh_secs: 10,
                    stale_secs: 300,
                    include_raw_presence: false,
                    include_compat: false,
                    transparent: false,
                }
            };
            let href = avatar_linux_renderer_state_href(&query);
            assert!(!href.contains("aura_io="), "href={href}");
            if !selector.is_empty() {
                assert!(!href.contains(selector), "href={href}");
            }
        }
    }

    #[test]
    fn avatar_aura_query_rejects_duplicate_and_cannot_promote_invalid_encoding() {
        let duplicate: axum::http::Uri =
            "/avatar-surface/linux-renderer-state?aura_io=default&aura_io=default"
                .parse()
                .expect("valid duplicate-query URI envelope");
        let duplicate_result: Result<Query<AvatarSurfaceQuery>, _> =
            Query::try_from_uri(&duplicate);
        assert!(duplicate_result.is_err());

        let invalid_encoding: axum::http::Uri = "/avatar-surface/linux-renderer-state?aura_io=%FF"
            .parse()
            .expect("valid URI envelope");
        let Query(query): Query<AvatarSurfaceQuery> = Query::try_from_uri(&invalid_encoding)
            .expect("Axum replaces invalid UTF-8 instead of rejecting it");
        assert!(query.aura_io.is_some());
        assert_ne!(query.aura_io.as_deref(), Some("default"));
    }

    async fn isolated_avatar_renderer_state(temp: &tempfile::TempDir) -> AppState {
        let store: std::sync::Arc<dyn StateStore> = std::sync::Arc::new(
            ab_store::SqliteStore::open(&temp.path().join("state.db"))
                .await
                .expect("open temporary store"),
        );
        let capabilities = json!({
            "avatar_state": {
                "agent_avatar_protocol": 1,
                "agent_id": "aura-p1-default-disabled-test",
                "runtime": "codex",
                "avatar_id": "aura-p1-no-ambient-pet-state",
                "project": "aura-p1-default-disabled-test"
            }
        });
        store
            .agent_presence_announce(
                "aura-p1-default-disabled-test",
                ab_store::AgentPresenceUpsert {
                    name: Some("Aura P1 default-disabled test"),
                    node: Some("test"),
                    project: Some("aura-p1-default-disabled-test"),
                    role: Some("gate"),
                    capabilities: Some(&capabilities),
                    ..Default::default()
                },
            )
            .await
            .expect("seed isolated avatar presence");

        AppState {
            store,
            embed_backend: build_raw_embed_backend(),
            embed_maintenance: Arc::new(Mutex::new(EmbedMaintenanceStatus::from_env())),
            avatar_aura_io_default: None,
        }
    }

    fn isolated_avatar_renderer_query(aura_io: Option<String>) -> AvatarSurfaceQuery {
        AvatarSurfaceQuery {
            project: Some("aura-p1-default-disabled-test".into()),
            role: Some("gate".into()),
            aura_io,
            max_idle_secs: 300,
            include_stale: true,
            limit: 1,
            refresh_secs: 10,
            stale_secs: 300,
            include_raw_presence: false,
            include_compat: false,
            transparent: false,
        }
    }

    #[tokio::test]
    async fn avatar_linux_renderer_rejects_successfully_parsed_aura_io_before_payload_acquisition()
    {
        let temp = tempfile::tempdir().expect("create tempdir");
        let invalid_aura_io = temp.path().join("invalid-aura-io.json");
        std::fs::write(&invalid_aura_io, b"not valid json").expect("write invalid aura fixture");
        let state = isolated_avatar_renderer_state(&temp).await;

        let result = avatar_linux_renderer_payload(
            &state,
            &isolated_avatar_renderer_query(Some(invalid_aura_io.display().to_string())),
        )
        .await;

        assert_eq!(
            result,
            Err((
                StatusCode::FORBIDDEN,
                "aura_io_file_access_disabled".to_string()
            ))
        );
    }

    #[tokio::test]
    async fn avatar_linux_renderer_without_aura_io_preserves_existing_payload() {
        let temp = tempfile::tempdir().expect("create tempdir");
        let state = isolated_avatar_renderer_state(&temp).await;

        let payload = avatar_linux_renderer_payload(&state, &isolated_avatar_renderer_query(None))
            .await
            .expect("a request without aura_io must preserve the renderer payload");

        assert_eq!(payload["surface"], "linux_codex_avatar_renderer_state");
        assert_eq!(payload["read_only"], true);
        assert_eq!(payload["project"], "aura-p1-default-disabled-test");
        assert_eq!(payload["input"]["presence_avatar_count"], 1);
        assert_eq!(payload["input"]["pet_id"], "aura-p1-no-ambient-pet-state");
        assert_eq!(payload["input"]["raw_pet_state_available"], false);
        assert_eq!(
            payload["input"]["presence_project"],
            "aura-p1-default-disabled-test"
        );
        assert_eq!(payload["input"]["presence_role"], "gate");
        assert!(payload["input"]["aura_io"].is_null());
    }

    #[test]
    fn avatar_linux_renderer_aura_guard_precedes_payload_acquisition() {
        let source = include_str!("daemon_http.rs");
        let handler_start = source
            .find("async fn avatar_linux_renderer_payload(")
            .expect("renderer payload handler");
        let handler_end = source[handler_start..]
            .find("\nasync fn avatar_linux_renderer_state(")
            .map(|offset| handler_start + offset)
            .expect("renderer state handler boundary");
        let handler = &source[handler_start..handler_end];
        let aura_guard = handler
            .find("if q.aura_io.is_some()")
            .expect("unconditional aura_io guard");
        let presence_read = handler
            .find("avatar_surface_entries(s, q).await?")
            .expect("presence payload acquisition");
        let pet_state_read = handler
            .find("read_pet_state(&pet_id)")
            .expect("pet-state payload acquisition");

        assert!(aura_guard < presence_read);
        assert!(aura_guard < pet_state_read);
    }

    #[test]
    fn avatar_aura_app_state_retains_only_sanitized_default_report() {
        let source = include_str!("daemon_http.rs");
        let state_start = source.find("struct AppState {").expect("AppState start");
        let state_end = source[state_start..]
            .find("\n}\n\nasync fn prepare_app_state(")
            .map(|offset| state_start + offset)
            .expect("AppState boundary");
        let state = &source[state_start..state_end];

        assert!(state.contains("SanitizedAuraIoReport"));
        assert!(!state.contains("AuraIoReadCapability"));
        assert!(!state.contains("PathBuf"));

        let handler_start = source
            .find("async fn avatar_linux_renderer_payload(")
            .expect("renderer payload handler");
        let handler_end = source[handler_start..]
            .find("\nasync fn avatar_linux_renderer_state(")
            .map(|offset| handler_start + offset)
            .expect("renderer state handler boundary");
        let handler = &source[handler_start..handler_end];

        assert!(handler.contains("renderer_payload_from_sources_with_sanitized_aura_io_report"));
        assert!(!handler.contains("renderer_payload_from_sources_with_aura_io_path"));
        assert!(!handler.contains("AuraIoReadCapability"));
        assert!(!handler.contains("preload_avatar_aura_io"));
    }

    #[test]
    fn avatar_surface_http_payload_matches_protocol_shape() {
        let q = AvatarSurfaceQuery {
            project: Some("agent-bridge".into()),
            role: Some("main".into()),
            aura_io: None,
            max_idle_secs: 300,
            include_stale: false,
            limit: 5,
            refresh_secs: 10,
            stale_secs: 300,
            include_raw_presence: false,
            include_compat: true,
            transparent: false,
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
            aura_io: None,
            max_idle_secs: 0,
            include_stale: true,
            limit: 5,
            refresh_secs: 10,
            stale_secs: 300,
            include_raw_presence: false,
            include_compat: false,
            transparent: false,
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
                "configured_sync_presence": true,
                "supports_sync_presence": null,
                "supports_heartbeat_health": null
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
        let review_report =
            crate::avatar_cortex::avatar_cortex_renderer_review_report_from_status(cortex.clone());
        let voice_policy =
            crate::avatar_cortex::avatar_cortex_voice_policy_from_status(cortex.clone());
        let voice_request = crate::avatar_cortex::avatar_cortex_voice_request_from_status(
            cortex.clone(),
            Some("xiao_shu::alert_peek::medium"),
            Some("agent-bridge"),
            None,
        );
        let voice_confirm = crate::avatar_cortex::avatar_cortex_voice_confirm_from_status(
            cortex.clone(),
            Some("xiao_shu::alert_peek::medium"),
            Some("agent-bridge"),
            Some("panel-dry-run"),
            false,
        );
        let voice_action_preview =
            crate::avatar_cortex::avatar_cortex_voice_action_preview_from_status(
                cortex.clone(),
                Some("xiao_shu::alert_peek::medium"),
                Some("agent-bridge"),
                Some("panel-dry-run"),
                true,
                false,
                300,
                None,
            );
        let xiao_shu_action_request = crate::avatar_cortex::xiao_shu_action_request(
            &crate::avatar_cortex::XiaoShuActionRequestOptions {
                label: None,
                heartbeat_label: None,
                project: Some("agent-bridge"),
                output: None,
                actor: Some("panel"),
                intent: Some("voice_alert"),
                message: Some("show the operator a safe Xiao Shu action request"),
                requested_track: Some("xiao_shu::alert_peek::medium"),
                reason: Some("panel-dry-run"),
                confirm: false,
                force: false,
                cooldown_secs: 300,
                tts_voice: None,
                tts_rate: None,
                include_details: false,
            },
        )
        .unwrap();
        let review_decisions = json!({
            "surface": "avatar_cortex_renderer_review_decisions",
            "read_only": true,
            "dry_run": true,
            "emits_audio": false,
            "writes_files": false,
            "writes_approval": false,
            "mutates_renderer": false,
            "codex_pet_package_mutation": false,
            "ledger": {
                "project": "agent-bridge",
                "exists": true,
                "path": "/tmp/decisions.jsonl",
                "matching_records": 1,
                "returned_count": 1,
                "latest_track_count": 1,
                "parsed_records": 1
            },
            "acceptance": {
                "can_promote_review_tracks": false
            },
            "records": [{
                "decision_id": "xrd-test",
                "track": "xiao_shu::look_sideways::medium",
                "decision": "accept_visual_motion_candidate",
                "actor": "operator",
                "approval_state": "not_approved"
            }]
        });
        let xiao_shu_action_requests = json!({
            "surface": "xiao_shu_action_request_queue",
            "read_only": true,
            "dry_run": true,
            "emits_audio": false,
            "queue": {
                "project": "agent-bridge",
                "exists": true,
                "path": "/tmp/requests.jsonl",
                "state_filter": "pending_human_confirmation",
                "include_details": false,
                "matching_records": 1,
                "returned_count": 1
            },
            "records": [{
                "request_id": "xsr-test",
                "state": "pending_human_confirmation",
                "actor": "codex",
                "intent": "voice_alert",
                "mapped_track": "xiao_shu::alert_peek::medium",
                "reason": "unit-test",
                "local_confirm_command": "agent-bridge avatar xiao-shu-action-request-action --project agent-bridge --request-id \"xsr-test\" --reason \"unit-test\" --confirm",
                "local_emit_command": "agent-bridge avatar xiao-shu-action-request-action --project agent-bridge --request-id \"xsr-test\" --reason \"unit-test\" --confirm --emit",
                "action_request": {
                    "line": "please look",
                    "cue_id": "soft_attention_needed"
                }
            }]
        });
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
            &review_report,
            &review_decisions,
            &voice_policy,
            &voice_request,
            &voice_confirm,
            &voice_action_preview,
            &xiao_shu_action_request,
            &xiao_shu_action_requests,
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
        assert!(html.contains("Xiao Shu Action Requests"));
        assert!(html.contains("xsr-test"));
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
        assert!(html.contains("Xiao Shu Review Report"));
        assert!(html.contains("state=ready_for_human_visual_review packets=3 ready=3 blocked=0"));
        assert!(html.contains("human=true approval=false decisions=0"));
        assert!(html.contains("approved=0 records=0 persisted=false"));
        assert!(html.contains("<dt>latest</dt><dd>-</dd>"));
        assert!(html.contains("items=1 voice_requests=1"));
        assert!(html.contains("can_promote=false merge_without_review=false"));
        assert!(html.contains("next record"));
        assert!(html.contains("cortex-review-record"));
        assert!(html.contains("review report json"));
        assert!(html.contains("Xiao Shu Review Decisions"));
        assert!(html.contains("exists=true parsed=1 latest=1"));
        assert!(html.contains("xrd-test"));
        assert!(html.contains("approval=not_approved"));
        assert!(html.contains("review decisions json"));
        assert!(html.contains("Xiao Shu Voice Policy"));
        assert!(html.contains("tracks=5 manual_cli=1 display_only=4 auto=0"));
        assert!(html.contains("Flo (中文（中国大陆）) rate=190 cooldown=300s"));
        assert!(html.contains(
            "xiao_shu::alert_peek::medium cue=soft_attention_needed line=小舒发现一点需要你看一下。"
        ));
        assert!(html.contains("http_emit_route_added=false auto_emit=0"));
        assert!(html.contains("voice policy json"));
        assert!(html.contains("Xiao Shu Voice Request"));
        assert!(html
            .contains("state=ready_for_operator_confirmation token=xiao_shu::alert_peek::medium"));
        assert!(html.contains(
            "xiao_shu_alert_peek_sparse_voice_v1 cue=soft_attention_needed llm_replace_line=false"
        ));
        assert!(html.contains("manual_cli=true second_step=true reason_present=false"));
        assert!(html.contains("auto_emit=false http_emit_route=null"));
        assert!(html.contains("voice request json"));
        assert!(html.contains("Xiao Shu Voice Confirm"));
        assert!(html.contains(
            "state=waiting_for_operator_confirmation token=xiao_shu::alert_peek::medium"
        ));
        assert!(html.contains("confirm=false would_execute_cli=false reason_present=true"));
        assert!(html.contains("auto_emit=false http_emit_route=null actual_execution_here=false"));
        assert!(html.contains("agent-bridge avatar cortex-voice-action"));
        assert!(html.contains("voice confirm json"));
        assert!(html.contains("Xiao Shu Voice Action Preview"));
        assert!(html.contains("ready=true token=xiao_shu::alert_peek::medium"));
        assert!(html.contains("would_emit=true blocked=false"));
        assert!(html.contains("voice action preview json"));
        assert!(html.contains("Xiao Shu Action Request"));
        assert!(html.contains("state=requires_human_confirmation actor=panel intent=voice_alert"));
        assert!(html.contains("cue=soft_attention_needed"));
        assert!(html.contains("context_only=true can_replace_line=false"));
        assert!(html.contains(
            "direct_control=false emits_audio=false human_required=true confirmed=false"
        ));
        assert!(html.contains("ready=false blocked=true reasons="));
        assert!(html.contains("human_confirmation_required"));
        assert!(html.contains("agent-bridge avatar xiao-shu-action-request"));
        assert!(html.contains("--enqueue"));
        assert!(html.contains("command=agent-bridge avatar xiao-shu-action-requests"));
        assert!(html.contains("open queue"));
        assert!(html.contains("xiao shu action request json"));
        assert!(html.contains("Xiao Shu Action Requests"));
        assert!(html.contains("state=pending_human_confirmation details=false"));
        assert!(html.contains("/avatar-surface/xiao-shu-action-console?project=agent-bridge"));
        assert!(html.contains(
            "/avatar-surface/xiao-shu-action-console?project=agent-bridge&amp;request_id=xsr-test"
        ));
        assert!(html.contains("/avatar-surface/xiao-shu-action-requests?project=agent-bridge&amp;request_id=xsr-test&amp;details=true"));
        assert!(html.contains("console"));
        assert!(html.contains("detail json"));
        assert!(html.contains("cue=soft_attention_needed line=please look"));
        assert!(html.contains("dry_run=agent-bridge avatar xiao-shu-action-request-action"));
        assert!(html.contains("emit=agent-bridge avatar xiao-shu-action-request-action"));
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
        assert!(html.contains("configured_sync=true support_sync=unknown health=unknown"));
        assert!(html.contains(r#"<meta http-equiv="refresh" content="10">"#));
        assert!(html.contains("last update=1779193140 refresh=10s stale_after=300s"));
        assert!(html.contains("status-fresh"));
        assert!(html.contains("5m 0s ago"));
        assert!(!html.contains("<script>alert(1)</script>"));
    }

    #[test]
    fn xiao_shu_action_console_html_is_read_only_operator_surface() {
        let q = XiaoShuActionRequestsQuery {
            project: Some("agent-bridge".into()),
            request_id: Some("xsr-test".into()),
            state: None,
            all_states: true,
            details: true,
            limit: Some(1),
        };
        let queue = json!({
            "surface": "xiao_shu_action_request_queue",
            "read_only": true,
            "dry_run": true,
            "emits_audio": false,
            "queue": {
                "project": "agent-bridge",
                "exists": true,
                "path": "/tmp/requests.jsonl",
                "state_filter": null,
                "matching_records": 1,
                "returned_count": 1,
                "current_records": 1
            },
            "records": [{
                "request_id": "xsr-test",
                "state": "pending_human_confirmation",
                "actor": "codex",
                "intent": "voice_alert",
                "mapped_track": "xiao_shu::alert_peek::medium",
                "reason": "unit-test",
                "local_confirm_command": "agent-bridge avatar xiao-shu-action-request-action --project agent-bridge --request-id \"xsr-test\" --reason \"unit-test\" --confirm",
                "local_emit_command": "agent-bridge avatar xiao-shu-action-request-action --project agent-bridge --request-id \"xsr-test\" --reason \"unit-test\" --confirm --emit",
                "action_request": {
                    "message": "please look",
                    "line": "小舒发现一点需要你看一下。",
                    "cue_id": "soft_attention_needed",
                    "message_handling": {
                        "message_is_context_note_only": true,
                        "message_can_replace_utterance": false
                    }
                }
            }]
        });
        let html = avatar_surface_xiao_shu_action_console_html(&queue, &q);

        assert!(html.contains("Xiao Shu Action Console"));
        assert!(html.contains("project=agent-bridge returned=1 matching=1 current=1"));
        assert!(html.contains("xsr-test"));
        assert!(html.contains("cue</dt><dd>soft_attention_needed"));
        assert!(html.contains("小舒发现一点需要你看一下。"));
        assert!(html.contains("context_only=true can_replace_line=false"));
        assert!(html.contains("read-only console; server actions disabled"));
        assert!(html.contains("/avatar-surface/xiao-shu-action-console?project=agent-bridge&amp;all_states=true&amp;limit=10"));
        assert!(html.contains("/avatar-surface/xiao-shu-action-console?project=agent-bridge&amp;state=emitted&amp;limit=10"));
        assert!(html.contains("data-copy=\"agent-bridge avatar xiao-shu-action-request-action --project agent-bridge --request-id xsr-test --reason unit-test --confirm\""));
        assert!(html.contains("navigator.clipboard.writeText"));
        assert!(html.contains("dry run"));
        assert!(html.contains("--confirm"));
        assert!(html.contains("--confirm --emit"));
        assert!(html.contains("--confirm --dismiss"));
        assert!(html.contains("/avatar-surface/xiao-shu-action-requests?project=agent-bridge&amp;request_id=xsr-test&amp;details=true"));
        assert!(!html.contains("http_emit_route"));
    }

    #[test]
    fn xiao_shu_action_console_copy_commands_quote_unsafe_cli_args() {
        let q = XiaoShuActionRequestsQuery {
            project: Some("agent bridge; rm -rf /".into()),
            request_id: Some("xsr-test".into()),
            state: None,
            all_states: true,
            details: true,
            limit: Some(1),
        };
        let queue = json!({
            "surface": "xiao_shu_action_request_queue",
            "read_only": true,
            "dry_run": true,
            "emits_audio": false,
            "queue": {
                "project": "agent bridge; rm -rf /",
                "exists": true,
                "path": "/tmp/requests.jsonl",
                "state_filter": null,
                "matching_records": 1,
                "returned_count": 1,
                "current_records": 1
            },
            "records": [{
                "request_id": "xsr-test",
                "state": "pending_human_confirmation",
                "actor": "codex",
                "intent": "voice_alert",
                "mapped_track": "xiao_shu::alert_peek::medium",
                "reason": "operator's reason",
                "action_request": {
                    "message": "please look",
                    "line": "小舒发现一点需要你看一下。",
                    "cue_id": "soft_attention_needed"
                }
            }]
        });
        let html = avatar_surface_xiao_shu_action_console_html(&queue, &q);

        assert!(html.contains("--project &#39;agent bridge; rm -rf /&#39;"));
        assert!(html.contains("--reason &#39;operator&#39;\\&#39;&#39;s reason&#39;"));
        assert!(!html.contains("--project agent bridge; rm -rf / --request-id"));
        assert!(html.contains("navigator.clipboard.writeText"));
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
        let html = avatar_surface_renderer_view_html(&renderer_view, 1779193140, None, None, None);

        assert!(html.contains("Xiao Shu Sidecar Renderer"));
        assert!(html.contains("data-stage=\"xiao-shu-renderer-view\""));
        assert!(html.contains("xiao_shu::soft_bounce::low"));
        assert!(html.contains("xiao_shu::sorting_glow::medium"));
        assert!(html.contains("selected / 8 frames / 1800ms"));
        assert!(html.contains("selected / 6 frames / 1800ms"));
        assert!(html.contains("review_only / 8 frames / 1520ms"));
        assert!(html.contains("motion-soft-bounce"));
        assert!(html.contains("motion-sorting-glow"));
        assert!(html.contains("xiao-shu sprite-backed"));
        assert!(html.contains("xiao-shu-sprite"));
        assert!(html.contains("pet=xiao-shu-dev"));
        assert!(html.contains("<dd data-asset>"));
        assert!(html.contains("/avatar-surface/pet-spritesheet?pet_id=xiao-shu-dev"));
        assert!(html.contains(
            "/avatar-surface/sidecar-spritesheet?asset=xiao-shu-motion-canonical-soft-bounce-v1"
        ));
        assert!(html
            .contains("/avatar-surface/sidecar-spritesheet?asset=xiao-shu-v3-ai-soft-bounce-v1"));
        assert!(html.contains(
            "/avatar-surface/sidecar-spritesheet?asset=xiao-shu-v3-ai-completion-nod-v1"
        ));
        assert!(html.contains(
            "/avatar-surface/sidecar-spritesheet?asset=xiao-shu-motion-canonical-idle-breathe-v1"
        ));
        assert!(html
            .contains("/avatar-surface/sidecar-spritesheet?asset=xiao-shu-v3-ai-idle-breathe-v1"));
        assert!(html.contains(
            "/avatar-surface/sidecar-spritesheet?asset=xiao-shu-motion-canonical-sorting-glow-v1"
        ));
        assert!(html.contains(
            "/avatar-surface/sidecar-spritesheet?asset=xiao-shu-motion-canonical-sorting-glow-v2"
        ));
        assert!(html.contains(
            "/avatar-surface/sidecar-spritesheet?asset=xiao-shu-motion-canonical-sorting-glow-v3"
        ));
        assert!(html.contains(
            "/avatar-surface/sidecar-spritesheet?asset=xiao-shu-motion-canonical-look-sideways-v1"
        ));
        assert!(html.contains(
            "/avatar-surface/sidecar-spritesheet?asset=xiao-shu-motion-canonical-look-sideways-v2"
        ));
        assert!(html.contains("\"asset_id\":\"xiao-shu-motion-canonical-soft-bounce-v1\""));
        assert!(html.contains("\"asset_id\":\"xiao-shu-motion-canonical-idle-breathe-v1\""));
        assert!(html.contains("\"asset_id\":\"xiao-shu-motion-canonical-sorting-glow-v1\""));
        assert!(html.contains("\"asset_id\":\"xiao-shu-motion-canonical-sorting-glow-v2\""));
        assert!(html.contains("\"asset_id\":\"xiao-shu-motion-canonical-sorting-glow-v3\""));
        assert!(html.contains("\"asset_id\":\"xiao-shu-motion-canonical-look-sideways-v1\""));
        assert!(html.contains("\"asset_id\":\"xiao-shu-motion-canonical-look-sideways-v2\""));
        assert!(html.contains("<h2 data-variant-title>Renderer Variants</h2>"));
        assert!(html.contains("Sidecar Track Variants"));
        assert!(html.contains("Alert Peek Semantic Variants"));
        assert!(html.contains("data-variant-panel hidden"));
        assert!(html.contains("\"variant_id\":\"current_alert_row\""));
        assert!(html.contains("\"variant_id\":\"waiting_peek_row\""));
        assert!(html.contains("\"variant_id\":\"sidecar_v3_soft_bounce_v1\""));
        assert!(html.contains("\"variant_id\":\"sidecar_v3_completion_nod_v1\""));
        assert!(html.contains("\"variant_id\":\"sidecar_v3_idle_breathe_v1\""));
        assert!(html.contains("\"variant_id\":\"sidecar_sorting_glow_v3\""));
        assert!(html.contains("\"variant_id\":\"sidecar_sorting_glow_v2\""));
        assert!(html.contains("\"variant_id\":\"sidecar_look_sideways_v2\""));
        assert!(html.contains("\"variant_id\":\"sidecar_peek_v2\""));
        assert!(html.contains("\"variant_id\":\"sidecar_peek_v4\""));
        assert!(html.contains("\"variant_id\":\"sidecar_ai_peek_v1\""));
        assert!(html.contains("\"variant_id\":\"sidecar_ai_peek_v2\""));
        assert!(html.contains("\"variant_id\":\"sidecar_v3_peek_sheet_v1\""));
        assert!(html.contains("\"variant_id\":\"sidecar_v3_ai_peek_v1\""));
        assert!(html.contains("\"variant_id\":\"sidecar_v3_ai_peek_v2\""));
        assert!(html.contains("\"variant_id\":\"sidecar_v3_ai_peek_v3\""));
        assert!(html.contains("\"variant_id\":\"sidecar_peek_v3\""));
        assert!(html.contains("\"variant_id\":\"focused_review_row\""));
        assert!(html.contains("/avatar-surface/sidecar-spritesheet?asset=xiao-shu-alert-peek-v2"));
        assert!(html.contains(
            "/avatar-surface/sidecar-spritesheet?asset=xiao-shu-motion-canonical-peek-v4"
        ));
        assert!(
            html.contains("/avatar-surface/sidecar-spritesheet?asset=xiao-shu-ai-alert-peek-v1")
        );
        assert!(
            html.contains("/avatar-surface/sidecar-spritesheet?asset=xiao-shu-ai-alert-peek-v2")
        );
        assert!(html
            .contains("/avatar-surface/sidecar-spritesheet?asset=xiao-shu-v3-alert-peek-sheet-v1"));
        assert!(
            html.contains("/avatar-surface/sidecar-spritesheet?asset=xiao-shu-v3-ai-alert-peek-v1")
        );
        assert!(
            html.contains("/avatar-surface/sidecar-spritesheet?asset=xiao-shu-v3-ai-alert-peek-v2")
        );
        assert!(
            html.contains("/avatar-surface/sidecar-spritesheet?asset=xiao-shu-v3-ai-alert-peek-v3")
        );
        assert!(
            html.contains("/avatar-surface/sidecar-spritesheet?asset=xiao-shu-canonical-peek-v3")
        );
        assert!(html.contains("\"asset_id\":\"xiao-shu-alert-peek-v2\""));
        assert!(html.contains("\"asset_id\":\"xiao-shu-v3-ai-soft-bounce-v1\""));
        assert!(html.contains("\"asset_id\":\"xiao-shu-v3-ai-completion-nod-v1\""));
        assert!(html.contains("\"asset_id\":\"xiao-shu-v3-ai-idle-breathe-v1\""));
        assert!(html.contains("\"asset_id\":\"xiao-shu-motion-canonical-peek-v4\""));
        assert!(html.contains("\"asset_id\":\"xiao-shu-ai-alert-peek-v1\""));
        assert!(html.contains("\"asset_id\":\"xiao-shu-ai-alert-peek-v2\""));
        assert!(html.contains("\"asset_id\":\"xiao-shu-v3-alert-peek-sheet-v1\""));
        assert!(html.contains("\"asset_id\":\"xiao-shu-v3-ai-alert-peek-v1\""));
        assert!(html.contains("\"asset_id\":\"xiao-shu-v3-ai-alert-peek-v2\""));
        assert!(html.contains("\"asset_id\":\"xiao-shu-v3-ai-alert-peek-v3\""));
        assert!(html.contains("\"asset_id\":\"xiao-shu-canonical-peek-v3\""));
        assert!(html.contains("\"choreography_id\":\"alert_peek_frame_choreo_v1\""));
        assert!(html.contains("\"choreography_id\":\"soft_bounce_v3_ai_frame_v1_choreo\""));
        assert!(html.contains("\"choreography_id\":\"completion_nod_v3_ai_frame_v1_choreo\""));
        assert!(html.contains("\"choreography_id\":\"idle_breathe_v3_ai_frame_v1_choreo\""));
        assert!(html.contains("\"choreography_id\":\"sorting_glow_sidecar_v3_frame_choreo\""));
        assert!(html.contains("\"choreography_id\":\"sorting_glow_sidecar_v2_frame_choreo\""));
        assert!(html.contains("\"choreography_id\":\"look_sideways_sidecar_v2_frame_choreo\""));
        assert!(html.contains("\"choreography_id\":\"alert_peek_sidecar_v2_frame_choreo\""));
        assert!(html.contains("\"choreography_id\":\"alert_peek_sidecar_v4_frame_choreo\""));
        assert!(html.contains("\"choreography_id\":\"alert_peek_ai_frame_v1_choreo\""));
        assert!(html.contains("\"choreography_id\":\"alert_peek_ai_frame_v2_grounded_choreo\""));
        assert!(html.contains("\"choreography_id\":\"alert_peek_v3_sheet_v1_choreo\""));
        assert!(html.contains("\"choreography_id\":\"alert_peek_v3_ai_frame_v1_choreo\""));
        assert!(html.contains("\"choreography_id\":\"alert_peek_v3_ai_frame_v2_cleanup_choreo\""));
        assert!(html
            .contains("\"choreography_id\":\"alert_peek_v3_ai_frame_v3_chroma_cleanup_choreo\""));
        assert!(html.contains("\"choreography_id\":\"alert_peek_sidecar_v3_frame_choreo\""));
        assert!(html.contains("\"surface\":\"alert_peek_voice_linkage_preview\""));
        assert!(html.contains("\"utterance\":\"小舒发现一点需要你看一下。\""));
        assert!(html.contains("/avatar-surface/cortex-voice-gate?enabled=true&reason=alert-peek-visual-review&preview_text=%E5%B0%8F%E8%88%92%E5%8F%91%E7%8E%B0%E4%B8%80%E7%82%B9%E9%9C%80%E8%A6%81%E4%BD%A0%E7%9C%8B%E4%B8%80%E4%B8%8B%E3%80%82"));
        assert!(html.contains("\"real_emit_surface\":\"agent-bridge avatar cortex-voice-emit\""));
        assert!(html.contains("\"http_emit_route\":null"));
        assert!(html.contains("function setVoiceLinkageLabel(track)"));
        assert!(html.contains("\"uses_css_motion\":false"));
        assert!(html.contains("\"phase\":\"attention_hold\""));
        assert!(
            html.contains("\"xiao_shu::alert_peek::medium\": { row: 5, frames: 8, alert: true }")
        );
        assert!(html.contains("filter: none;"));
        assert!(html.contains("--alert-soft: #c97968;"));
        assert!(html.contains("border-width: 4px;"));
        assert!(html.contains("brightness(0.94)"));
        assert!(html.contains("sprite-choreographed"));
        assert!(html.contains("sprite-attention-visible"));
        assert!(html.contains("function choreographyFrames(track)"));
        assert!(!html.contains("animation: alert-peek 1400ms ease-in-out infinite;"));
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
            Some("waiting_peek_row"),
        );
        assert!(focused.contains("<span>active=xiao_shu::alert_peek::medium</span>"));
        assert!(focused.contains("waiting_peek_row / waiting peek row"));
        assert!(focused.contains("data-voice-linkage"));
        assert!(focused.contains("preview=小舒发现一点需要你看一下。"));
        assert!(focused.contains("gate=/avatar-surface/cortex-voice-gate?enabled=true&amp;reason=alert-peek-visual-review&amp;preview_text=%E5%B0%8F%E8%88%92%E5%8F%91%E7%8E%B0%E4%B8%80%E7%82%B9%E9%9C%80%E8%A6%81%E4%BD%A0%E7%9C%8B%E4%B8%80%E4%B8%8B%E3%80%82"));
        assert!(focused.contains(
            "choreo=${choreoFrames} css_motion=${Boolean(choreography.uses_css_motion)}${asset}"
        ));
        assert!(focused.contains(r#"let variantId = "waiting_peek_row";"#));
        assert!(focused.contains("data-sprite-variant=\"waiting_peek_row\""));
        assert!(focused.contains(
            "const defaultSpriteRoute = \"/avatar-surface/pet-spritesheet?pet_id=xiao-shu-dev\";"
        ));
        assert!(focused.contains("const defaultAssetPetId = \"xiao-shu-dev\";"));
        assert!(focused.contains("let defaultSpriteAvailable = true;"));
        assert!(
            focused.contains("function setAssetLabel(spriteRoute, sidecarAsset, fallbackReason)")
        );
        assert!(focused.contains("fallback=css silhouette"));
        assert!(focused.contains("reason=${fallbackReason}"));
        assert!(focused.contains("pet_spritesheet_unavailable"));
        assert!(focused.contains("figure.dataset.spriteAsset = \"css_silhouette\";"));
        assert!(focused
            .contains("fetch(defaultSpriteRoute, { method: \"HEAD\", cache: \"no-store\" })"));
        assert!(focused.contains("figure.dataset.spriteAsset"));
        assert!(focused.contains("sprite-sidecar-asset"));
        assert!(focused.contains("figure.dataset.spritePhase"));
        assert!(focused.contains("choreoFrame.hold_ms"));
        assert!(focused.contains("url.searchParams.set(\"variant\", variant.variant_id);"));
        assert!(focused.contains(r#"let trackIndex = 4;"#));
        assert!(focused.contains(r#"data-track-token="xiao_shu::alert_peek::medium""#));
    }

    #[test]
    fn avatar_sidecar_spritesheet_serves_prototype_atlas_contract() {
        let svg = avatar_sidecar_spritesheet_svg("xiao-shu-alert-peek-v2").unwrap();
        let motion_svg =
            avatar_sidecar_spritesheet_svg("xiao-shu-motion-canonical-peek-v4").unwrap();
        let ai_peek_png = avatar_sidecar_spritesheet_png("xiao-shu-ai-alert-peek-v1").unwrap();
        let ai_peek_v2_png = avatar_sidecar_spritesheet_png("xiao-shu-ai-alert-peek-v2").unwrap();
        let v3_sheet_png =
            avatar_sidecar_spritesheet_png("xiao-shu-v3-alert-peek-sheet-v1").unwrap();
        let v3_ai_peek_png =
            avatar_sidecar_spritesheet_png("xiao-shu-v3-ai-alert-peek-v1").unwrap();
        let v3_ai_peek_v2_png =
            avatar_sidecar_spritesheet_png("xiao-shu-v3-ai-alert-peek-v2").unwrap();
        let v3_ai_peek_v3_png =
            avatar_sidecar_spritesheet_png("xiao-shu-v3-ai-alert-peek-v3").unwrap();
        let v3_idle_breathe_png =
            avatar_sidecar_spritesheet_png("xiao-shu-v3-ai-idle-breathe-v1").unwrap();
        let v3_soft_bounce_png =
            avatar_sidecar_spritesheet_png("xiao-shu-v3-ai-soft-bounce-v1").unwrap();
        let v3_completion_nod_png =
            avatar_sidecar_spritesheet_png("xiao-shu-v3-ai-completion-nod-v1").unwrap();
        let v3_focus_wave_png =
            avatar_sidecar_spritesheet_png("xiao-shu-v3-focus-wave-v1").unwrap();
        let v3_focus_turn_left_png =
            avatar_sidecar_spritesheet_png("xiao-shu-v3-focus-turn-left-v1").unwrap();
        let v3_focus_turn_right_png =
            avatar_sidecar_spritesheet_png("xiao-shu-v3-focus-turn-right-v1").unwrap();
        let v3_focus_walk_left_png =
            avatar_sidecar_spritesheet_png("xiao-shu-v3-focus-walk-left-v1").unwrap();
        let v3_focus_walk_right_png =
            avatar_sidecar_spritesheet_png("xiao-shu-v3-focus-walk-right-v1").unwrap();
        let canonical_svg = avatar_sidecar_spritesheet_svg("xiao-shu-canonical-peek-v3").unwrap();
        let soft_bounce_svg =
            avatar_sidecar_spritesheet_svg("xiao-shu-motion-canonical-soft-bounce-v1").unwrap();
        let idle_breathe_svg =
            avatar_sidecar_spritesheet_svg("xiao-shu-motion-canonical-idle-breathe-v1").unwrap();
        let sorting_glow_svg =
            avatar_sidecar_spritesheet_svg("xiao-shu-motion-canonical-sorting-glow-v1").unwrap();
        let sorting_glow_v2_svg =
            avatar_sidecar_spritesheet_svg("xiao-shu-motion-canonical-sorting-glow-v2").unwrap();
        let sorting_glow_v3_svg =
            avatar_sidecar_spritesheet_svg("xiao-shu-motion-canonical-sorting-glow-v3").unwrap();
        let look_sideways_svg =
            avatar_sidecar_spritesheet_svg("xiao-shu-motion-canonical-look-sideways-v1").unwrap();
        let look_sideways_v2_svg =
            avatar_sidecar_spritesheet_svg("xiao-shu-motion-canonical-look-sideways-v2").unwrap();

        assert!(
            svg.contains(r#"<svg xmlns="http://www.w3.org/2000/svg" width="1536" height="1872""#)
        );
        assert!(svg.contains("Xiao Shu alert peek sidecar v2 sprite atlas"));
        assert!(svg.contains(r#"id="frame-0""#));
        assert!(svg.contains(r#"id="frame-7""#));
        assert!(svg.contains("rotate(72)"));
        assert!(svg.contains(r##"fill="#d45f4c""##));
        assert!(motion_svg.contains("Xiao Shu motion-canonical alert peek sidecar v4 sprite atlas"));
        assert!(motion_svg.contains(r#"id="frame-7""#));
        assert!(motion_svg.contains("xs4-robe"));
        assert!(motion_svg.contains("rotate(72)"));
        assert!(motion_svg.contains(r##"fill="#56c6cc""##));
        assert!(ai_peek_png.starts_with(b"\x89PNG\r\n\x1a\n"));
        assert!(ai_peek_png.len() > 4096);
        assert!(ai_peek_v2_png.starts_with(b"\x89PNG\r\n\x1a\n"));
        assert!(ai_peek_v2_png.len() > 4096);
        assert!(v3_sheet_png.starts_with(b"\x89PNG\r\n\x1a\n"));
        assert!(v3_sheet_png.len() > 4096);
        assert!(v3_ai_peek_png.starts_with(b"\x89PNG\r\n\x1a\n"));
        assert!(v3_ai_peek_png.len() > 4096);
        assert!(v3_ai_peek_v2_png.starts_with(b"\x89PNG\r\n\x1a\n"));
        assert!(v3_ai_peek_v2_png.len() > 4096);
        assert!(v3_ai_peek_v3_png.starts_with(b"\x89PNG\r\n\x1a\n"));
        assert!(v3_ai_peek_v3_png.len() > 4096);
        assert!(v3_idle_breathe_png.starts_with(b"\x89PNG\r\n\x1a\n"));
        assert!(v3_idle_breathe_png.len() > 4096);
        assert!(v3_soft_bounce_png.starts_with(b"\x89PNG\r\n\x1a\n"));
        assert!(v3_soft_bounce_png.len() > 4096);
        assert!(v3_completion_nod_png.starts_with(b"\x89PNG\r\n\x1a\n"));
        assert!(v3_completion_nod_png.len() > 4096);
        assert!(v3_focus_wave_png.starts_with(b"\x89PNG\r\n\x1a\n"));
        assert!(v3_focus_wave_png.len() > 4096);
        assert!(v3_focus_turn_left_png.starts_with(b"\x89PNG\r\n\x1a\n"));
        assert!(v3_focus_turn_left_png.len() > 4096);
        assert!(v3_focus_turn_right_png.starts_with(b"\x89PNG\r\n\x1a\n"));
        assert!(v3_focus_turn_right_png.len() > 4096);
        assert!(v3_focus_walk_left_png.starts_with(b"\x89PNG\r\n\x1a\n"));
        assert!(v3_focus_walk_left_png.len() > 4096);
        assert!(v3_focus_walk_right_png.starts_with(b"\x89PNG\r\n\x1a\n"));
        assert!(v3_focus_walk_right_png.len() > 4096);
        assert!(canonical_svg.contains("Xiao Shu canonical alert peek sidecar v3 sprite atlas"));
        assert!(canonical_svg.contains(r#"id="frame-7""#));
        assert!(canonical_svg.contains("xs3-robe"));
        assert!(!canonical_svg.contains("xiao-shu-canonical-peek-v3"));
        assert!(soft_bounce_svg
            .contains("Xiao Shu motion-canonical soft bounce sidecar v1 sprite atlas"));
        assert!(soft_bounce_svg.contains(r#"id="frame-7""#));
        assert!(soft_bounce_svg.contains("xsb-robe"));
        assert!(soft_bounce_svg.contains("rotate(21)"));
        assert!(idle_breathe_svg
            .contains("Xiao Shu motion-canonical idle breathe sidecar v1 sprite atlas"));
        assert!(idle_breathe_svg.contains(r#"id="frame-5""#));
        assert!(idle_breathe_svg.contains("xsb-robe"));
        assert!(!idle_breathe_svg.contains(r#"id="frame-7""#));
        assert!(sorting_glow_svg
            .contains("Xiao Shu motion-canonical sorting glow sidecar v1 sprite atlas"));
        assert!(sorting_glow_svg.contains(r#"id="frame-7""#));
        assert!(sorting_glow_svg.contains("xsb-process-glow"));
        assert!(sorting_glow_svg.contains(r#"opacity="0.62""#));
        assert!(sorting_glow_v2_svg
            .contains("Xiao Shu motion-canonical sorting glow sidecar v2 sprite atlas"));
        assert!(sorting_glow_v2_svg.contains(r#"id="frame-7""#));
        assert!(sorting_glow_v2_svg.contains(r#"opacity="0.82""#));
        assert!(sorting_glow_v2_svg.contains("rotate(36 134 42)"));
        assert!(sorting_glow_v3_svg
            .contains("Xiao Shu motion-canonical sorting glow sidecar v3 sprite atlas"));
        assert!(sorting_glow_v3_svg.contains(r#"id="frame-7""#));
        assert!(sorting_glow_v3_svg.contains(r#"opacity="0.94""#));
        assert!(sorting_glow_v3_svg.contains("xsb-sorting-signals"));
        assert!(sorting_glow_v3_svg.contains("rotate(38 134 42)"));
        assert!(look_sideways_svg
            .contains("Xiao Shu motion-canonical look sideways sidecar v1 sprite atlas"));
        assert!(look_sideways_svg.contains(r#"id="frame-6""#));
        assert!(look_sideways_svg.contains("rotate(-24 134 42)"));
        assert!(!look_sideways_svg.contains(r#"id="frame-7""#));
        assert!(look_sideways_v2_svg
            .contains("Xiao Shu motion-canonical look sideways sidecar v2 sprite atlas"));
        assert!(look_sideways_v2_svg.contains(r#"id="frame-6""#));
        assert!(look_sideways_v2_svg.contains("rotate(-44 134 42)"));
        assert!(!look_sideways_v2_svg.contains(r#"id="frame-7""#));
        assert!(avatar_sidecar_spritesheet_svg("unknown").is_none());
    }
}
