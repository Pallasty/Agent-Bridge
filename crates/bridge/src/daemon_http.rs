//! v20 — HTTP daemon for cross-machine forum + presence over Tailscale.
//!
//! Serves read-only endpoints in Stage 1:
//!   - `GET /healthz`
//!   - `GET /.well-known/agent.json/<session_id>` — A2A AgentCard
//!   - `GET /forum/threads?board=...&status=...&limit=...`
//!   - `GET /forum/posts?thread_id=...&board=...&since_post_id=...&limit=...`
//!   - `GET /presence?project=...&role=...&max_idle_secs=...&limit=...`
//!   - `GET /avatar-surface?project=...&role=...&include_stale=...&limit=...`
//!     — read-only Agent Avatar Protocol JSON projection
//!   - `GET /avatar-surface/report?...` — same projection as text/plain
//!   - `GET /avatar-surface/panel?...` — minimal read-only HTML status panel
//!   - `GET /identity?days=N` — δ-1 cross-node identity fingerprint
//!                              (same shape as `dream identity --json`)
//!   - `POST /embed` — text → 384-d embedding for non-Rust / non-MCP clients
//!                    (game runtimes, web, scripting). Phase 2.1 encoder
//!                    decoupled per thread 6 #226 / #228 / #231 split with
//!                    `embed_text` MCP tool. Returns the raw inner backend's
//!                    output without substrate side-effects.
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

/// Run the HTTP daemon on `listen` (e.g. `0.0.0.0:7878`). Blocks until the
/// listener is dropped or the runtime is cancelled.
pub async fn run(store: Arc<dyn StateStore>, listen: &str) -> Result<()> {
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
        .route("/identity", get(identity_endpoint))
        .route("/embed", post(embed_endpoint))
        .with_state(state);

    let listener = tokio::net::TcpListener::bind(listen)
        .await
        .with_context(|| format!("bind {listen}"))?;
    let addr = listener
        .local_addr()
        .map(|a| a.to_string())
        .unwrap_or_else(|_| listen.to_string());
    tracing::info!(addr = %addr, "agent-bridge daemon-http listening");
    axum::serve(listener, app).await.context("axum::serve")?;
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
    Ok(Json(json!({
        "thread_id": q.thread_id,
        "board": q.board,
        "count": posts.len(),
        "posts": posts,
    })))
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
    #[serde(default)]
    include_raw_presence: bool,
    #[serde(default)]
    include_compat: bool,
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

fn avatar_surface_payload(q: &AvatarSurfaceQuery, avatars: Vec<Value>) -> Value {
    json!({
        "agent_avatar_protocol": crate::avatar_surface::AGENT_AVATAR_PROTOCOL_VERSION,
        "read_only": true,
        "surface": "avatar_surface_http",
        "count": avatars.len(),
        "project": q.project.as_deref(),
        "role": q.role.as_deref(),
        "max_idle_secs": q.effective_max_idle_secs(),
        "limit": q.effective_limit(),
        "avatars": avatars,
    })
}

async fn avatar_surface_snapshot(
    State(s): State<AppState>,
    Query(q): Query<AvatarSurfaceQuery>,
) -> Result<Json<Value>, (StatusCode, String)> {
    let avatars = avatar_surface_entries(&s, &q).await?;
    Ok(Json(avatar_surface_payload(&q, avatars)))
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
    Ok(Html(avatar_surface_panel_html(&q, &avatars, &report)))
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

fn avatar_surface_html_value(entry: &Value, key: &str, fallback: &str) -> String {
    match entry.get(key) {
        Some(Value::String(s)) if !s.is_empty() => html_escape(s),
        Some(Value::Number(n)) => html_escape(&n.to_string()),
        Some(Value::Bool(b)) => html_escape(&b.to_string()),
        _ => html_escape(fallback),
    }
}

fn avatar_surface_panel_html(q: &AvatarSurfaceQuery, avatars: &[Value], report: &str) -> String {
    let subtitle = format!(
        "project={} role={} max_idle_secs={} source=daemon-http",
        q.project.as_deref().unwrap_or("*"),
        q.role.as_deref().unwrap_or("*"),
        q.effective_max_idle_secs()
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
        let flags = format!(
            "avatar_state={} compat_pet={}",
            avatar_surface_html_value(avatar, "has_avatar_state", "false"),
            avatar_surface_html_value(avatar, "has_compat_pet_state", "false")
        );
        rows.push_str(&format!(
            r#"<tr>
  <td><strong>{agent_id}</strong><span>{runtime} / {avatar_id}</span></td>
  <td>{mode}<span>{activity}</span></td>
  <td>{focus}<span>risk {risk}</span></td>
  <td>{next}<span>{flags}</span></td>
  <td>{heartbeat}</td>
</tr>"#
        ));
    }
    if rows.is_empty() {
        rows.push_str(
            r#"<tr><td colspan="5" class="empty">No avatar presence rows matched the filters.</td></tr>"#,
        );
    }

    format!(
        r#"<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Agent Avatar Surface</title>
  <style>
    :root {{
      color-scheme: light dark;
      --bg: #f7f7f3;
      --fg: #181915;
      --muted: #65685f;
      --line: #d8d9cf;
      --accent: #167a72;
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
    .count {{
      color: var(--accent);
      font-weight: 700;
      white-space: nowrap;
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
      </div>
      <div class="count">{count} avatars</div>
    </header>
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
        count = avatars.len(),
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

#[cfg(test)]
mod tests {
    use super::*;
    use ab_store::AgentPresenceRecord;

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
            include_raw_presence: false,
            include_compat: false,
        };

        assert_eq!(q.effective_max_idle_secs(), 0);
        assert_eq!(q.effective_limit(), 500);
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
            include_raw_presence: false,
            include_compat: true,
        };
        let avatar =
            crate::avatar_surface::entry_from_presence(&avatar_presence_fixture(), false, true);
        let payload = avatar_surface_payload(&q, vec![avatar]);

        assert_eq!(payload["agent_avatar_protocol"], 1);
        assert_eq!(payload["read_only"], true);
        assert_eq!(payload["surface"], "avatar_surface_http");
        assert_eq!(payload["count"], 1);
        assert_eq!(payload["project"], "agent-bridge");
        assert_eq!(payload["role"], "main");
        assert_eq!(payload["max_idle_secs"], 300);
        assert_eq!(payload["limit"], 5);
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
        let html = avatar_surface_panel_html(&q, &[avatar], "Agent <Avatar> Surface");

        assert!(html.contains("&lt;script&gt;alert(1)&lt;/script&gt;"));
        assert!(html.contains("read &lt;panel&gt;"));
        assert!(html.contains("Agent &lt;Avatar&gt; Surface"));
        assert!(!html.contains("<script>alert(1)</script>"));
    }
}
