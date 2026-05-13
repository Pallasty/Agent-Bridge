//! P1 — Static Palace viewer (呼吸式画布).
//!
//! Read-only HTTP server that renders the active memory graph as a
//! force-directed network in the browser using cytoscape.js.
//!
//! ## Two memory sources, one graph
//!
//! Two parallel memory systems live side-by-side and the viewer merges them:
//!
//! - **sqlite** (agent-bridge `state.db`): lesson / decision / observation /
//!   todo / session_handoff / etc. — produced by agent work via `memory_save`.
//!   Edges are real `memory_edges` rows (Hebbian-evolved, supersedes,
//!   summarizes, references).
//! - **markdown** (`~/.claude/projects/<cwd-encoded>/memory/*.md`): Claude
//!   Code's auto-memory layer — vision / user / project / feedback / decision
//!   files written by the user and the assistant during conversation.
//!   Edges come from `(other.md)` references inside the body.
//!
//! Cross-source edges are NOT inferred from semantic similarity (would
//! generate false positives — that's a P3 job). But **explicit** cross-
//! source edges written via `memory_link` (e.g. C1 `annotates` edges from
//! a sqlite annotation back to a markdown vision file) DO render — those
//! are user-authored intent, not noise.
//!
//! ## Endpoints
//!   - `GET /`                  → embedded HTML viewer
//!   - `GET /healthz`           → liveness probe
//!   - `GET /api/graph`         → merged `{ nodes, edges }` from both sources;
//!     edges include explicit (memory_edges) AND co-activation (Hebbian) —
//!     the latter dedup'd against explicit so a structural edge always wins
//!   - `GET /api/memory/:key`   → single record (sqlite first, markdown fallback)
//!   - `POST /api/annotate`     → C1: write a new sqlite memory linked to a node
//!     (closes the 呼吸 loop — Palace exploration → annotation → memory)
//!
//! Bind defaults to `127.0.0.1` (single-user local view).
//!
//! See `vision_breathing_canvas.md` for the broader 呼吸式画布 design.

use ab_store::{MemoryListSort, MemoryQueryRecord, MemoryRecord, StateStore};
use anyhow::{Context, Result};
use base64::{engine::general_purpose, Engine as _};
use axum::{
    extract::{Path, Query, State},
    http::StatusCode,
    response::{
        sse::{Event as SseEvent, KeepAlive, Sse},
        Html, IntoResponse,
    },
    routing::{get, post},
    Json, Router,
};
use serde::Deserialize;
use serde_json::{json, Value};
use std::collections::{HashSet, VecDeque};
use std::fs;
use std::path::PathBuf;
use std::sync::{Arc, Mutex};
use std::time::{SystemTime, UNIX_EPOCH};

/// Size of the rolling click window used to feed the co-activation table.
/// 5 = "last 5 nodes you looked at" → the system records that these were
/// in your attention together. Small enough that a fresh palace visit
/// quickly self-prunes; large enough to capture multi-step exploration.
const CLICK_WINDOW: usize = 5;

const VIEWER_NODE_CAP: usize = 500;
const STORE_FETCH_LIMIT: u32 = 2000;

const PALACE_HTML: &str = include_str!("../assets/palace.html");

#[derive(Clone)]
struct AppState {
    store: Arc<dyn StateStore>,
    markdown_root: Option<PathBuf>,
    /// Directory holding `dream promote --html` reports (and any other
    /// future agent-generated HTML artifacts). When set, Palace serves
    /// `/reports/:filename` for direct viewing and exposes
    /// `/api/reports?key=KEY` so the side panel can surface related
    /// reports — closing the loop from "report → Palace ?focus=KEY"
    /// back to "Palace node → reports that mention it".
    reports_dir: Option<PathBuf>,
    /// Rolling window of recently-clicked node keys. When full, each new
    /// click triggers a `record_coactivation` call so the Hebbian system
    /// learns that "these nodes were in the user's attention together".
    /// `Mutex<VecDeque<…>>` (not async) — held only across cheap ops.
    recent_clicks: Arc<Mutex<VecDeque<String>>>,
}

/// Run the Palace viewer HTTP server. Blocks until the listener is dropped.
///
/// `markdown_root` is the directory containing `*.md` auto-memory files.
/// Pass `None` to disable the markdown layer (sqlite-only).
pub async fn run(
    store: Arc<dyn StateStore>,
    listen: &str,
    markdown_root: Option<PathBuf>,
    reports_dir: Option<PathBuf>,
) -> Result<()> {
    if let Some(p) = &markdown_root {
        tracing::info!(path = %p.display(), "Palace markdown layer enabled");
    } else {
        tracing::info!("Palace markdown layer disabled (sqlite-only)");
    }
    if let Some(p) = &reports_dir {
        tracing::info!(path = %p.display(), "Palace reports layer enabled");
    }

    let state = AppState {
        store,
        markdown_root,
        reports_dir,
        recent_clicks: Arc::new(Mutex::new(VecDeque::with_capacity(CLICK_WINDOW))),
    };
    let app = Router::new()
        .route("/", get(index))
        .route("/healthz", get(healthz))
        .route("/api/graph", get(api_graph))
        .route("/api/memory/:key", get(api_memory))
        .route("/api/annotate", post(api_annotate))
        .route("/api/reports", get(api_reports))
        .route("/reports/:filename", get(serve_report))
        .route("/api/canvas-chat", post(api_canvas_chat))
        .route("/api/canvas-chat-stream", post(api_canvas_chat_stream))
        .route("/api/memory/:key/tombstone", post(api_memory_tombstone))
        .route("/api/lineage/:key", get(api_lineage))
        .route("/api/coactivation-peers/:key", get(api_coactivation_peers))
        .route("/api/embedding-stats", get(api_embedding_stats))
        .route("/api/canvas-chat-attachment", post(api_canvas_chat_attachment))
        .with_state(state);

    let listener = tokio::net::TcpListener::bind(listen)
        .await
        .with_context(|| format!("bind {listen}"))?;
    let addr = listener
        .local_addr()
        .map(|a| a.to_string())
        .unwrap_or_else(|_| listen.to_string());
    tracing::info!(addr = %addr, "Palace viewer (P1) listening");
    eprintln!("Palace viewer ready: http://{addr}");
    axum::serve(listener, app).await.context("axum::serve")?;
    Ok(())
}

/// Best-effort default: `~/.claude/projects/<cwd-encoded>/memory/`.
/// Returns `None` if the directory doesn't exist (e.g. user runs the
/// viewer outside a project that has been opened in Claude Code).
pub fn default_markdown_dir() -> Option<PathBuf> {
    let home = std::env::var_os("HOME")?;
    let cwd = std::env::current_dir().ok()?;
    let cwd_str = cwd.to_str()?;
    let encoded = cwd_str.replace('/', "-");
    let path = PathBuf::from(home)
        .join(".claude")
        .join("projects")
        .join(encoded)
        .join("memory");
    if path.is_dir() {
        Some(path)
    } else {
        None
    }
}

async fn index() -> impl IntoResponse {
    Html(PALACE_HTML)
}

async fn healthz() -> impl IntoResponse {
    (StatusCode::OK, "ok")
}

#[derive(Deserialize, Default)]
struct GraphQuery {
    /// `?all=1` includes `kind=skill` records (indexed third-party skills).
    #[serde(default)]
    all: bool,
}

// ── Markdown source ──────────────────────────────────────────────────────

#[derive(Debug, Clone)]
struct MarkdownMemory {
    /// Filename without `.md` — used as graph node id.
    key: String,
    /// `type` field from frontmatter (project / feedback / vision / etc.).
    /// Falls back to `"markdown"` if no frontmatter or no `type`.
    kind: String,
    /// `description` field from frontmatter (one-line summary).
    description: String,
    /// Full body content after the frontmatter block.
    content: String,
    /// `(other.md)` references found in the body (sans `.md`).
    links_to: Vec<String>,
}

/// Walk a directory of `*.md` files, parse each as a markdown memory.
/// Skips `MEMORY.md` (the index) and any non-`.md` files.
fn read_markdown_dir(dir: &PathBuf) -> Vec<MarkdownMemory> {
    let entries = match fs::read_dir(dir) {
        Ok(e) => e,
        Err(e) => {
            tracing::warn!(?dir, error = %e, "markdown memory dir unreadable");
            return Vec::new();
        }
    };

    let mut out = Vec::new();
    for entry in entries.flatten() {
        let path = entry.path();
        if path.extension().and_then(|s| s.to_str()) != Some("md") {
            continue;
        }
        let Some(stem) = path.file_stem().and_then(|s| s.to_str()) else {
            continue;
        };
        if stem == "MEMORY" {
            continue;
        }
        let body = match fs::read_to_string(&path) {
            Ok(s) => s,
            Err(_) => continue,
        };
        out.push(parse_markdown_memory(stem.to_string(), &body));
    }
    out
}

fn parse_markdown_memory(key: String, body: &str) -> MarkdownMemory {
    let (fm_text, content) = split_frontmatter(body);

    let mut description = String::new();
    let mut kind = String::from("markdown");

    if let Some(fm) = fm_text {
        for line in fm.lines() {
            if let Some((k, v)) = line.split_once(':') {
                let k = k.trim();
                let v = v.trim().trim_matches(|c| c == '"' || c == '\'');
                match k {
                    "description" => description = v.to_string(),
                    "type" => kind = v.to_string(),
                    _ => {}
                }
            }
        }
    }

    let links_to = extract_links(content);

    MarkdownMemory {
        key,
        kind,
        description,
        content: content.to_string(),
        links_to,
    }
}

/// Split body into `(frontmatter, content)`. Frontmatter is the YAML-ish
/// block delimited by leading `---\n` and the next `---\n`. Returns
/// `(None, body)` if no frontmatter is present.
fn split_frontmatter(body: &str) -> (Option<&str>, &str) {
    let Some(rest) = body.strip_prefix("---\n") else {
        return (None, body);
    };
    let Some(idx) = rest.find("\n---\n") else {
        return (None, body);
    };
    let fm = &rest[..idx];
    let content = &rest[idx + 5..];
    (Some(fm), content)
}

/// Extract `*.md` references — both strict `(filename.md)` markdown-link
/// form and bare `filename.md` prose mentions. Filenames must be all
/// lowercase ASCII alphanumeric plus `_` `-`. Dangling refs (target file
/// doesn't exist in our memory set) are filtered out by the caller.
fn extract_links(content: &str) -> Vec<String> {
    let mut out = Vec::new();

    // Tokenize on any char that isn't a valid filename char. This catches
    // both `(name.md)` (parens are separators) and bare `name.md` in prose.
    for token in content.split(|c: char| {
        !c.is_ascii_alphanumeric() && c != '_' && c != '-' && c != '.'
    }) {
        let Some(stem) = token.strip_suffix(".md") else {
            continue;
        };
        if is_valid_memory_filename(stem) {
            out.push(stem.to_string());
        }
    }

    out.sort();
    out.dedup();
    out
}

fn is_valid_memory_filename(s: &str) -> bool {
    if s.is_empty() {
        return false;
    }
    // Must start with a letter (avoids `42.md` numeric noise).
    if !s.chars().next().is_some_and(|c| c.is_ascii_lowercase()) {
        return false;
    }
    s.chars()
        .all(|c| c.is_ascii_alphanumeric() || c == '_' || c == '-')
}

// ── Graph endpoint ───────────────────────────────────────────────────────

/// Build the graph: active sqlite memories + markdown memories +
/// edges from both sources. Cross-source edges are not inferred.
async fn api_graph(
    State(s): State<AppState>,
    Query(q): Query<GraphQuery>,
) -> Result<Json<Value>, (StatusCode, String)> {
    // ── sqlite layer ────────────────────────────────────────────────────
    let nodes = s
        .store
        .list_memories(None, MemoryListSort::ByImportance, STORE_FETCH_LIMIT)
        .await
        .map_err(|e| {
            (
                StatusCode::INTERNAL_SERVER_ERROR,
                format!("list_memories: {e}"),
            )
        })?;

    let active: Vec<_> = nodes
        .into_iter()
        .filter(|m| m.status == "active")
        .filter(|m| q.all || m.kind != "skill")
        .take(VIEWER_NODE_CAP)
        .collect();
    let sqlite_keys: HashSet<String> = active.iter().map(|m| m.key.clone()).collect();

    // ── markdown layer ──────────────────────────────────────────────────
    // Read markdown first so that the sqlite edge loop knows which keys
    // resolve as markdown nodes (used to render explicit cross-source
    // edges like `annotates` written via POST /api/annotate).
    let mds = if let Some(root) = &s.markdown_root {
        read_markdown_dir(root)
    } else {
        Vec::new()
    };
    // Markdown keys that are NOT already in sqlite (avoid double-rendering
    // if a key happens to exist in both — unlikely, but cheap to handle).
    let md_only: Vec<&MarkdownMemory> = mds
        .iter()
        .filter(|m| !sqlite_keys.contains(&m.key))
        .collect();
    let md_keys: HashSet<String> = md_only.iter().map(|m| m.key.clone()).collect();

    // Helper: is this key renderable as a node in the merged graph?
    let is_node = |k: &str| sqlite_keys.contains(k) || md_keys.contains(k);

    // ── sqlite edges ────────────────────────────────────────────────────
    // Includes intra-sqlite edges and explicit cross-source edges (e.g.
    // `annotates` from a sqlite annotation to a markdown vision node).
    // Cross-source edges are only rendered when **both endpoints exist as
    // nodes** — we don't render dangling refs.
    let mut seen: HashSet<(String, String, String)> = HashSet::new();
    let mut sqlite_edges = Vec::new();
    for m in &active {
        let nbrs = s.store.memory_neighbors(&m.key).await.unwrap_or_default();
        for e in nbrs {
            let key = if e.from_key < e.to_key {
                (e.from_key.clone(), e.to_key.clone(), e.edge_type.clone())
            } else {
                (e.to_key.clone(), e.from_key.clone(), e.edge_type.clone())
            };
            if seen.insert(key) && is_node(&e.from_key) && is_node(&e.to_key) {
                sqlite_edges.push(e);
            }
        }
    }

    // ── markdown edges ─ within markdown only (no cross-source). ────────
    let mut md_edges = Vec::new();
    let mut md_seen: HashSet<(String, String)> = HashSet::new();
    for m in &md_only {
        for target in &m.links_to {
            if !md_keys.contains(target) {
                continue;
            }
            let key = if m.key < *target {
                (m.key.clone(), target.clone())
            } else {
                (target.clone(), m.key.clone())
            };
            if md_seen.insert(key) {
                md_edges.push((m.key.clone(), target.clone()));
            }
        }
    }

    // ── co-activation edges ─ Hebbian "fire together, wire together" ────
    // Pairs are seen via record_coactivation as side-effect of memory_search
    // and (since C2) Palace clicks. We render them as a soft underlay so
    // attention-clusters become visible *beneath* the structural skeleton.
    //
    // Dedup: an explicit (sqlite or markdown) edge between a pair always wins
    // — coact between the same nodes would be redundant signal. min_count=2
    // filters out single-encounter noise; limit=300 caps render cost.
    let coact_top = s
        .store
        .top_coactivation_edges(2, 300)
        .await
        .unwrap_or_default();
    let mut explicit_pairs: HashSet<(String, String)> = HashSet::new();
    for e in &sqlite_edges {
        let p = if e.from_key < e.to_key {
            (e.from_key.clone(), e.to_key.clone())
        } else {
            (e.to_key.clone(), e.from_key.clone())
        };
        explicit_pairs.insert(p);
    }
    for (a, b) in &md_edges {
        let p = if a < b {
            (a.clone(), b.clone())
        } else {
            (b.clone(), a.clone())
        };
        explicit_pairs.insert(p);
    }
    let mut coact_edges = Vec::new();
    let mut coact_seen: HashSet<(String, String)> = HashSet::new();
    for c in coact_top {
        if !is_node(&c.key_a) || !is_node(&c.key_b) {
            continue;
        }
        let p = if c.key_a < c.key_b {
            (c.key_a.clone(), c.key_b.clone())
        } else {
            (c.key_b.clone(), c.key_a.clone())
        };
        if explicit_pairs.contains(&p) {
            continue;
        }
        if coact_seen.insert(p) {
            coact_edges.push(c);
        }
    }

    // ── serialize ───────────────────────────────────────────────────────
    let mut nodes_json: Vec<Value> = active
        .iter()
        .map(|m| {
            json!({
                "id":            m.key,
                "kind":          m.kind,
                "importance":    (m.importance * 1000.0).round() / 1000.0,
                "tags":          m.tags,
                "label":         m.key,
                "access":        m.access_count,
                "last_accessed": m.last_accessed_at,
                "source":        "sqlite",
            })
        })
        .collect();

    for m in &md_only {
        nodes_json.push(json!({
            "id":            m.key,
            "kind":          m.kind,
            "importance":    0.7,    // markdown memories are user-curated → treat as high signal
            "tags":          Vec::<String>::new(),
            "label":         m.key,
            "access":        0,
            "last_accessed": 0,
            "source":        "markdown",
            "description":   m.description,
        }));
    }

    let mut edges_json: Vec<Value> = sqlite_edges
        .iter()
        .map(|e| {
            json!({
                "source": e.from_key,
                "target": e.to_key,
                "type":   e.edge_type,
                "weight": (e.weight * 1000.0).round() / 1000.0,
            })
        })
        .collect();

    for (a, b) in &md_edges {
        edges_json.push(json!({
            "source": a,
            "target": b,
            "type":   "references",
            "weight": 0.5,
        }));
    }

    for c in &coact_edges {
        // Normalize raw count → 0..1 for cytoscape mapData; keep raw count
        // alongside so the side panel / hover tip can show "fired N times".
        let weight = (c.count as f64 / 10.0).min(1.0);
        edges_json.push(json!({
            "source": c.key_a,
            "target": c.key_b,
            "type":   "coactivation",
            "weight": (weight * 1000.0).round() / 1000.0,
            "count":  c.count,
        }));
    }

    let now_secs = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map(|d| d.as_secs() as i64)
        .unwrap_or(0);

    Ok(Json(json!({
        "nodes": nodes_json,
        "edges": edges_json,
        "now":   now_secs,
        "stats": {
            "sqlite_nodes":   active.len(),
            "markdown_nodes": md_only.len(),
            "sqlite_edges":   sqlite_edges.len(),
            "markdown_edges": md_edges.len(),
            "coact_edges":    coact_edges.len(),
        }
    })))
}

// ── Single-memory endpoint ───────────────────────────────────────────────

/// Fetch a single memory record by key.
///
/// Tries sqlite first via `memory_get` (which atomically bumps
/// `access_count` and `last_accessed_at` — this is **C2 click-as-trace**:
/// every Palace click leaves a real cognitive imprint). Falls back to
/// markdown if the key matches a `.md` file. After a successful sqlite
/// hit, the key joins a rolling click window; once the window has 2+
/// entries we call `record_coactivation` so the Hebbian system learns
/// "these nodes were in the user's attention together".
async fn api_memory(
    State(s): State<AppState>,
    Path(key): Path<String>,
) -> Result<Json<Value>, (StatusCode, String)> {
    // sqlite lookup — auto-bumps access_count + last_accessed_at.
    let started = std::time::Instant::now();
    if let Some(m) = s
        .store
        .memory_get(&key)
        .await
        .map_err(|e| (StatusCode::INTERNAL_SERVER_ERROR, format!("memory_get: {e}")))?
    {
        // Phase 0 telemetry: log the click into `memory_query_log` so
        // `dream replay-audit` (and downstream attention analyses) can
        // see Palace navigation, not just MCP tool calls. Without this
        // the trace is biased toward Claude's programmatic retrievals —
        // an audit on a Palace-heavy workflow ends up with 0–2 events
        // per summary even when humans are actively clicking around.
        // Source label distinguishes from MCP `memory_get` (`mcp:memory_get`).
        let now_secs = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .map(|d| d.as_secs() as i64)
            .unwrap_or(0);
        let elapsed_us = started.elapsed().as_micros().min(u32::MAX as u128) as u32;
        let rec = MemoryQueryRecord {
            kind: "get".into(),
            query: key.clone(),
            tags_json: "[]".into(),
            hit_count: 1,
            top_hit_age_secs: Some(now_secs - m.created_at),
            top_hit_created_at: Some(m.created_at),
            duration_us: elapsed_us,
            source: "palace_viewer:click".into(),
            at: now_secs,
        };
        let store_for_log = s.store.clone();
        tokio::spawn(async move {
            let _ = store_for_log.record_memory_query(&rec).await;
        });


        // Feed the rolling click window → co-activation. Best-effort: any
        // failure here just skips the recording, never blocks the read.
        let coact_keys = {
            let mut buf = s.recent_clicks.lock().expect("click window poisoned");
            // Don't double-record consecutive clicks on the same node
            // (user re-opening a panel shouldn't inflate the bond).
            if buf.back().map(String::as_str) != Some(key.as_str()) {
                if buf.len() >= CLICK_WINDOW {
                    buf.pop_front();
                }
                buf.push_back(key.clone());
            }
            // Snapshot for the await call below — drop the lock first.
            buf.iter().cloned().collect::<Vec<_>>()
        };
        if coact_keys.len() >= 2 {
            let _ = s.store.record_coactivation(&coact_keys, None).await;
        }

        return Ok(Json(json!({
            "key":          m.key,
            "kind":         m.kind,
            "content":      m.content,
            "tags":         m.tags,
            "importance":   m.importance,
            "status":       m.status,
            "access_count": m.access_count,
            "created_at":   m.created_at,
            "updated_at":   m.updated_at,
            "scope":        m.scope,
            "source":       "sqlite",
        })));
    }

    // Markdown fallback. No access tracking yet — would need a separate
    // file-watcher schema to attribute clicks to markdown nodes.
    if let Some(root) = &s.markdown_root {
        let path = root.join(format!("{key}.md"));
        if let Ok(body) = fs::read_to_string(&path) {
            let m = parse_markdown_memory(key.clone(), &body);
            return Ok(Json(json!({
                "key":          m.key,
                "kind":         m.kind,
                "content":      m.content,
                "tags":         Vec::<String>::new(),
                "importance":   0.7,
                "status":       "active",
                "access_count": 0,
                "description":  m.description,
                "links_to":     m.links_to,
                "source":       "markdown",
                "file_path":    path.display().to_string(),
            })));
        }
    }

    Err((StatusCode::NOT_FOUND, format!("memory not found: {key}")))
}

// ── Tombstone endpoint (C8: act on stale memories) ──────────────────────

/// Soft-delete (tombstone) a memory by key. Idempotent: tombstoning an
/// already-tombstoned key returns `deleted: false` without error. Used
/// by the C8 stale-review panel so the user can sweep cold memories
/// without leaving Palace.
async fn api_memory_tombstone(
    State(s): State<AppState>,
    Path(key): Path<String>,
) -> Result<Json<Value>, (StatusCode, String)> {
    let deleted = s
        .store
        .memory_delete(&key)
        .await
        .map_err(|e| (StatusCode::INTERNAL_SERVER_ERROR, format!("memory_delete: {e}")))?;
    Ok(Json(json!({ "ok": true, "key": key, "deleted": deleted })))
}

// ── Lineage endpoint (P7: closes VIEWER_NODE_CAP visibility gap) ────────
//
// `/api/graph` truncates by importance, so chains of low-importance
// chat_sessions (the typical fork-chain shape) become invisible in the
// rendered subgraph. memory_edges still has them; this endpoint walks
// them directly so the canvas rail can surface the chain.
//
// BFS from `key` along edges matching `type` (default `evolved_from`),
// up to `depth` hops (default 10, capped at 50). Visited set guards
// against cycles. Returns the chain in walk order with the edge type
// that connected each hop.

#[derive(Deserialize)]
struct LineageQuery {
    /// Edge type to follow. Default `evolved_from`. Use `discussed_at`
    /// to walk chat_session → topic; `supersedes` for replacement chains;
    /// `all` (literal string) walks any edge type — useful for general
    /// "show me everything connected".
    #[serde(default)]
    r#type: Option<String>,
    /// Max hops. Capped at 50 server-side to bound work.
    #[serde(default)]
    depth: Option<u32>,
    /// Walk direction. `out` (default) follows from→to; `in` follows
    /// to→from (i.e. "who evolved from me"); `both` is bidirectional.
    #[serde(default)]
    direction: Option<String>,
}

async fn api_lineage(
    State(s): State<AppState>,
    Path(key): Path<String>,
    Query(q): Query<LineageQuery>,
) -> Result<Json<Value>, (StatusCode, String)> {
    let edge_filter = q.r#type.as_deref().unwrap_or("evolved_from").to_string();
    let depth = q.depth.unwrap_or(10).min(50) as usize;
    let direction = q.direction.as_deref().unwrap_or("out").to_string();
    let walk_out = matches!(direction.as_str(), "out" | "both");
    let walk_in = matches!(direction.as_str(), "in" | "both");
    if !walk_out && !walk_in {
        return Err((
            StatusCode::BAD_REQUEST,
            format!("direction must be one of out|in|both, got {direction}"),
        ));
    }

    // BFS queue of (key, hop_count). Two distinct visited sets:
    //   `enqueued`  — guards cycle re-traversal (per-node, like classic BFS)
    //   `emitted`   — guards duplicate chain entries (per (next, edge_type))
    // Without the (next, edge_type) tier, two edges between the same
    // pair (e.g. fork-chain creates BOTH evolved_from B→A AND an
    // auto-supersedes B→A from threshold dedupe) would have only one
    // emitted: whichever came first via memory_neighbors. Bug surfaced
    // in P10-B e2e where evolved_from quietly disappeared from the
    // lineage rail because supersedes happened to win the iteration race.
    use std::collections::{HashSet, VecDeque};
    let mut enqueued: HashSet<String> = HashSet::new();
    enqueued.insert(key.clone());
    let mut emitted: HashSet<(String, String)> = HashSet::new();
    let mut queue: VecDeque<(String, u32)> = VecDeque::new();
    queue.push_back((key.clone(), 0));

    // Each chain entry records the step: who was added + how we got here.
    let mut chain: Vec<Value> = Vec::new();
    let mut truncated = false;

    while let Some((cur, hop)) = queue.pop_front() {
        if hop >= depth as u32 {
            // Reached depth limit; any further would be cut off.
            truncated = true;
            continue;
        }
        let nbrs = s.store.memory_neighbors(&cur).await.unwrap_or_default();
        for e in nbrs {
            // Edge filter — "all" passes everything.
            if edge_filter != "all" && e.edge_type != edge_filter {
                continue;
            }
            // Direction filter — only follow edges in the requested direction.
            // memory_neighbors returns both incoming and outgoing edges for
            // `cur` (it's the union); we distinguish via from_key/to_key.
            let next = if e.from_key == cur && walk_out {
                e.to_key.clone()
            } else if e.to_key == cur && walk_in {
                e.from_key.clone()
            } else {
                continue;
            };
            // Dedup per (target_key, edge_type): multiple edge types
            // between the same pair each emit their own chain entry.
            let emit_key = (next.clone(), e.edge_type.clone());
            if emitted.contains(&emit_key) {
                continue;
            }
            emitted.insert(emit_key);
            chain.push(json!({
                "from": cur,
                "to": next,
                "edge_type": e.edge_type,
                "weight": e.weight,
                "hop": hop + 1,
            }));
            // Enqueue once per target (cycle guard): if we already walked
            // from this node before, don't re-traverse its outgoing edges
            // — but we still emitted the new edge type above so the
            // chain surface stays complete.
            if !enqueued.contains(&next) {
                enqueued.insert(next.clone());
                queue.push_back((next, hop + 1));
            }
        }
    }

    Ok(Json(json!({
        "ok": true,
        "key": key,
        "edge_filter": edge_filter,
        "direction": direction,
        "depth_limit": depth,
        "chain": chain,
        "chain_length": chain.len(),
        "truncated": truncated,
    })))
}

// ── Coactivation peers (P18) ─────────────────────────────────────────────
//
// One-hop neighbors over the **explicit** attention edges (`cofires` from
// dream-promote tier 1, `co_referenced` from tier 2 — see P16-M). Direct
// memory_edges scan; bypasses the /api/graph VIEWER_NODE_CAP=500 filter
// that drops these edges when their endpoints sit below the top-500
// importance line (very common for chat_session + lesson clusters).
//
// Same pattern as P7 /api/lineage: focused endpoint per key, no graph
// truncation, used by the canvas rail to surface tier-1 + tier-2
// Hebbian peers for whichever node the user is working on.

async fn api_coactivation_peers(
    State(s): State<AppState>,
    Path(key): Path<String>,
) -> Result<Json<Value>, (StatusCode, String)> {
    let nbrs = s.store.memory_neighbors(&key).await.map_err(|e| {
        (
            StatusCode::INTERNAL_SERVER_ERROR,
            format!("memory_neighbors: {e}"),
        )
    })?;

    // Project to peer view. Dedupe by (peer, edge_type) so two parallel
    // edges of the same type collapse, but the same peer can appear under
    // both 'cofires' AND 'co_referenced' if the dream-promote pass added
    // both (rare; tier-2 normally skips when tier-1 cofires exists).
    let mut peers: Vec<Value> = Vec::new();
    let mut seen: HashSet<(String, String)> = HashSet::new();
    for e in nbrs {
        let et = e.edge_type.as_str();
        if et != "cofires" && et != "co_referenced" {
            continue;
        }
        let other = if e.from_key == key {
            e.to_key.clone()
        } else {
            e.from_key.clone()
        };
        if other == key {
            continue;
        }
        if !seen.insert((other.clone(), et.to_string())) {
            continue;
        }
        peers.push(json!({
            "key": other,
            "edge_type": et,
            "weight": (e.weight * 1000.0).round() / 1000.0,
        }));
    }

    // Sort: cofires (tier 1, weight 0.5-0.95) first, co_referenced
    // (tier 2, weight 0.3-0.5) after; within each tier, weight desc.
    peers.sort_by(|a, b| {
        let ta = a["edge_type"].as_str() == Some("cofires");
        let tb = b["edge_type"].as_str() == Some("cofires");
        tb.cmp(&ta).then_with(|| {
            let wa = a["weight"].as_f64().unwrap_or(0.0);
            let wb = b["weight"].as_f64().unwrap_or(0.0);
            wb.partial_cmp(&wa).unwrap_or(std::cmp::Ordering::Equal)
        })
    });

    let cofires_count = peers
        .iter()
        .filter(|p| p["edge_type"].as_str() == Some("cofires"))
        .count();
    let co_referenced_count = peers.len() - cofires_count;

    Ok(Json(json!({
        "ok": true,
        "key": key,
        "peers": peers,
        "edge_types": ["cofires", "co_referenced"],
        "cofires_count": cofires_count,
        "co_referenced_count": co_referenced_count,
    })))
}

// ── Embedding backend stats (P12) ────────────────────────────────────────
//
// Surfaces the v26 `embedding_backend` distribution so Palace can show
// "you have N hash-quality memories, run memory_reindex --only-stale
// when ONNX is ready." NULL is reported as `"unknown"` (pre-v26 rows).

async fn api_embedding_stats(
    State(s): State<AppState>,
) -> Result<Json<Value>, (StatusCode, String)> {
    let rows = s
        .store
        .memory_embedding_backend_counts()
        .await
        .map_err(|e| {
            (
                StatusCode::INTERNAL_SERVER_ERROR,
                format!("embedding_backend_counts: {e}"),
            )
        })?;
    let total: u64 = rows.iter().map(|(_, n)| n).sum();
    let breakdown: Vec<Value> = rows
        .into_iter()
        .map(|(b, n)| json!({ "backend": b, "count": n }))
        .collect();
    // P17: also surface kind breakdown so the footer can separate
    // working memory from catalog-style bulk imports (e.g. kind='skill').
    // Raw counts only; UI decides which kinds are catalog.
    let kind_rows = s.store.memory_kind_counts().await.map_err(|e| {
        (
            StatusCode::INTERNAL_SERVER_ERROR,
            format!("memory_kind_counts: {e}"),
        )
    })?;
    let kind_breakdown: Vec<Value> = kind_rows
        .into_iter()
        .map(|(k, n)| json!({ "kind": k, "count": n }))
        .collect();
    Ok(Json(json!({
        "ok": true,
        "total_active": total,
        "breakdown": breakdown,
        "kind_breakdown": kind_breakdown,
        "catalog_kinds": ["skill"],
    })))
}

// ── Canvas chat attachment upload (P14: multi-modal paste v0.5) ─────────
//
// Accepts base64-encoded images (or any binary) from the chat panel's
// paste handler. Writes to `/tmp/canvas-chat-attachments/<ts>-<hex>.<ext>`
// and returns the path. The spawned-claude in canvas chat has Read tool
// access by default and can interpret images natively, so the chat
// flow only has to surface "[image: <path>]" markers in the prompt and
// claude will reach for Read on its own (the chat prompt template also
// hints this).
//
// No auth/quota in v0.5; Palace is local-only; abuse risk is low.

#[derive(Deserialize)]
struct AttachmentPayload {
    /// MIME type, e.g. `image/png`, `image/jpeg`. Used to derive file
    /// extension; defaults to `bin` for unknown types.
    media_type: String,
    /// Base64-encoded payload (no `data:` URL prefix).
    data_base64: String,
}

async fn api_canvas_chat_attachment(
    State(_s): State<AppState>,
    Json(p): Json<AttachmentPayload>,
) -> Result<Json<Value>, (StatusCode, String)> {
    let ext = match p.media_type.as_str() {
        "image/png" => "png",
        "image/jpeg" => "jpg",
        "image/gif" => "gif",
        "image/webp" => "webp",
        "image/svg+xml" => "svg",
        _ => "bin",
    };
    let bytes = general_purpose::STANDARD
        .decode(p.data_base64.trim())
        .map_err(|e| (StatusCode::BAD_REQUEST, format!("invalid base64: {e}")))?;
    // 8 MiB cap — Palace chat is for snippets / screenshots, not
    // large media. Past that, user should put the file on disk
    // and paste the path directly.
    if bytes.len() > 8 * 1024 * 1024 {
        return Err((
            StatusCode::PAYLOAD_TOO_LARGE,
            format!("attachment {} bytes exceeds 8 MiB cap", bytes.len()),
        ));
    }
    let dir = std::path::PathBuf::from("/tmp/canvas-chat-attachments");
    tokio::fs::create_dir_all(&dir)
        .await
        .map_err(|e| (StatusCode::INTERNAL_SERVER_ERROR, format!("mkdir: {e}")))?;
    // Filename: <unix-ms>-<8-hex>.ext — sortable + collision-resistant
    // without a uuid crate. A second process landing in the same ms
    // collides only on full 8-hex match (1 in 4 billion).
    let now_ms = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map(|d| d.as_millis())
        .unwrap_or(0);
    let mut rand_hex = String::with_capacity(8);
    for _ in 0..8 {
        let r: u8 = (now_ms as u8).wrapping_mul(31).wrapping_add(rand_hex.len() as u8 * 7);
        rand_hex.push_str(&format!("{:x}", r % 16));
    }
    // Mix in a tiny entropy from the byte content itself so two pastes
    // of different content in the same millisecond don't collide.
    let content_hash: u32 = bytes
        .iter()
        .take(64)
        .fold(0u32, |a, b| a.wrapping_mul(131).wrapping_add(*b as u32));
    let filename = format!("{:013}-{:08x}.{}", now_ms, content_hash, ext);
    let path = dir.join(&filename);
    tokio::fs::write(&path, &bytes)
        .await
        .map_err(|e| (StatusCode::INTERNAL_SERVER_ERROR, format!("write {path:?}: {e}")))?;

    Ok(Json(json!({
        "ok": true,
        "path": path.display().to_string(),
        "filename": filename,
        "media_type": p.media_type,
        "size_bytes": bytes.len(),
    })))
}

// ── Annotate endpoint (C1: closes the 呼吸 loop) ─────────────────────────

#[derive(Deserialize)]
struct AnnotatePayload {
    /// The node the user is annotating from. Becomes the `to_key` of the
    /// outgoing edge (default `annotates`).
    target_key: String,
    /// User-authored body. Becomes the `content` of the new sqlite memory.
    content: String,
    /// New-memory kind. Defaults to `annotation` for backwards-compat with
    /// the C1 annotate flow. B-mode canvas-save passes `working_doc`.
    #[serde(default)]
    kind: Option<String>,
    /// Edge type from the new memory back to `target_key`. Defaults to
    /// `annotates`. Canvas-save uses `expanded_from` so the structural
    /// distinction (一笔注解 vs 完整工坊产物) survives in the graph.
    #[serde(default)]
    edge_type: Option<String>,
    /// Edge weight. Defaults to 1.0 (the historic annotate behavior).
    /// Canvas-save passes 0.7: 用户主动行为，强但弱于 hand-authored 主结构。
    #[serde(default)]
    weight: Option<f64>,
    /// Importance for the new memory record. Defaults to 0.6.
    #[serde(default)]
    importance: Option<f64>,
    /// Optional lineage parent — when set, the server adds a second
    /// `evolved_from` edge from the new memory → `parent_key`. Used by
    /// the canvas chat fork-chain flow: continue-this-discussion preloads
    /// the prior chat_session onto an origin focus, the user keeps
    /// chatting, then save records the new chat_session as evolved from
    /// the old one — preserving lineage so the graph can surface
    /// "this chat is descendant of <older chat>".
    #[serde(default)]
    parent_key: Option<String>,
}

/// Sanitize a kind string into a key-friendly snake_case slug. Only
/// `[a-z0-9_]` allowed; everything else becomes `_`. Empty → "memory".
/// Caps at 24 chars so keys don't blow up.
fn sanitize_kind_slug(raw: &str) -> String {
    let lower: String = raw
        .chars()
        .map(|c| {
            let c = c.to_ascii_lowercase();
            if c.is_ascii_alphanumeric() || c == '_' { c } else { '_' }
        })
        .take(24)
        .collect();
    if lower.is_empty() { "memory".into() } else { lower }
}

/// Create a new sqlite memory authored from the Palace, linked back to
/// `target_key`. The default flow (no extra payload fields) writes a
/// `kind=annotation` record with an `annotates` edge — the C1 path
/// untouched. B-mode "expand canvas" passes `kind=working_doc` +
/// `edge_type=expanded_from` + `weight=0.7` to make the structural
/// distinction visible in the graph.
///
/// Returns `{ ok: true, key, kind, edge }` on success. The frontend
/// should re-fetch `/api/graph` to see the new node + edge.
async fn api_annotate(
    State(s): State<AppState>,
    Json(p): Json<AnnotatePayload>,
) -> Result<Json<Value>, (StatusCode, String)> {
    let target = p.target_key.trim().to_string();
    let body = p.content.trim().to_string();
    if target.is_empty() {
        return Err((StatusCode::BAD_REQUEST, "target_key required".into()));
    }
    if body.is_empty() {
        return Err((StatusCode::BAD_REQUEST, "content required".into()));
    }

    let kind = p
        .kind
        .as_deref()
        .map(str::trim)
        .filter(|s| !s.is_empty())
        .unwrap_or("annotation")
        .to_string();
    let edge_type = p
        .edge_type
        .as_deref()
        .map(str::trim)
        .filter(|s| !s.is_empty())
        .unwrap_or("annotates")
        .to_string();
    let weight = p.weight.unwrap_or(1.0);
    let importance = p.importance.unwrap_or(0.6);

    let now_millis = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map(|d| d.as_millis())
        .unwrap_or(0);
    let kind_slug = sanitize_kind_slug(&kind);
    let key = format!("palace_{kind_slug}_{now_millis:013}");

    let mut tags = vec!["palace".to_string(), kind.clone()];
    if kind == "working_doc" {
        tags.push("canvas".to_string());
    }
    if kind == "chat_session" {
        // `chat` for filter UX; `canvas` because chat lives inside the
        // canvas overlay and is part of B-mode by definition.
        tags.push("chat".to_string());
        tags.push("canvas".to_string());
    }

    let mem = MemoryRecord {
        key: key.clone(),
        kind: kind.clone(),
        content: body,
        tags,
        related_keys: vec![target.clone()],
        scope: None,
        created_at: 0,
        updated_at: 0,
        last_accessed_at: 0,
        access_count: 0,
        importance,
        status: "active".to_string(),
        trigger_pattern: None,
        superseded_by: None,
    };

    s.store
        .memory_save(&mem)
        .await
        .map_err(|e| (StatusCode::INTERNAL_SERVER_ERROR, format!("memory_save: {e}")))?;

    s.store
        .memory_link(&key, &target, &edge_type, weight)
        .await
        .map_err(|e| (StatusCode::INTERNAL_SERVER_ERROR, format!("memory_link: {e}")))?;

    // Optional lineage edge (fork chain). Skip silently if parent_key is
    // missing or empty, or points at this same memory (self-edge guard).
    // Failure to add the lineage edge surfaces as `lineage_ok: false` in
    // the response — non-fatal: the primary chat_session is already saved.
    let mut lineage_ok = true;
    let mut lineage_edge: Option<String> = None;
    let parent = p
        .parent_key
        .as_deref()
        .map(str::trim)
        .filter(|s| !s.is_empty() && *s != key);
    if let Some(parent_key) = parent {
        let et = "evolved_from";
        match s.store.memory_link(&key, parent_key, et, 0.9).await {
            Ok(_) => {
                lineage_edge = Some(et.to_string());
            }
            Err(_) => {
                lineage_ok = false;
            }
        }
    }

    Ok(Json(json!({
        "ok":   true,
        "key":  key,
        "kind": kind,
        "edge": edge_type,
        "lineage_ok": lineage_ok,
        "lineage_edge": lineage_edge,
    })))
}

// ── Reports layer (C/A6 ↔ HTML reports back-link) ────────────────────────
//
// `dream promote --html` writes audit reports keyed to memory keys; the
// reports link forward to Palace via `?focus=KEY`. These endpoints close
// the loop the other way: Palace's side panel can list reports that
// mention the focused key, and a path-traversal-safe handler serves the
// HTML files directly so the back-link doesn't rely on file:// URLs.

#[derive(Deserialize)]
struct ReportsQuery {
    key: String,
}

/// Maximum number of bytes scanned per report when checking for key
/// occurrences. Reports stay well under this in practice (~40KB), but
/// the cap protects against accidentally pointing `--reports-dir` at a
/// folder of arbitrary HTML.
const REPORT_SCAN_BYTES: u64 = 1_048_576; // 1 MiB

/// Maximum number of recent reports to enumerate per request. Keeps the
/// side-panel list short and bounds the I/O cost of each call.
const REPORTS_PER_KEY_LIMIT: usize = 8;

/// `GET /api/reports?key=KEY` — list reports in `reports_dir` that
/// mention the given memory key, sorted newest first. Returns
/// `{ items: [{ filename, mtime, mentions, label }] }`.
async fn api_reports(
    State(s): State<AppState>,
    Query(q): Query<ReportsQuery>,
) -> Result<Json<Value>, (StatusCode, String)> {
    let dir = match &s.reports_dir {
        Some(p) => p,
        None => return Ok(Json(json!({"items": []}))),
    };
    let entries = match fs::read_dir(dir) {
        Ok(e) => e,
        Err(_) => return Ok(Json(json!({"items": []}))),
    };

    let mut hits: Vec<(String, u64, usize)> = Vec::new();
    for entry in entries.flatten() {
        let name = match entry.file_name().into_string() {
            Ok(n) => n,
            Err(_) => continue,
        };
        if !name.ends_with(".html") {
            continue;
        }
        let path = entry.path();
        let meta = match entry.metadata() {
            Ok(m) => m,
            Err(_) => continue,
        };
        if !meta.is_file() || meta.len() > REPORT_SCAN_BYTES {
            continue;
        }
        let content = match fs::read_to_string(&path) {
            Ok(c) => c,
            Err(_) => continue,
        };
        let mentions = content.matches(q.key.as_str()).count();
        if mentions == 0 {
            continue;
        }
        let mtime = meta
            .modified()
            .ok()
            .and_then(|t| t.duration_since(UNIX_EPOCH).ok())
            .map(|d| d.as_secs())
            .unwrap_or(0);
        hits.push((name, mtime, mentions));
    }
    // Newest first; truncate to the per-key limit.
    hits.sort_by(|a, b| b.1.cmp(&a.1));
    hits.truncate(REPORTS_PER_KEY_LIMIT);

    let items: Vec<Value> = hits
        .into_iter()
        .map(|(filename, mtime, mentions)| {
            // Strip extension and the standard `promote-` prefix to make
            // a compact label like "2026-05-10". Other filenames pass
            // through with just the extension dropped.
            let stem = filename.strip_suffix(".html").unwrap_or(&filename);
            let label = stem.strip_prefix("promote-").unwrap_or(stem).to_string();
            json!({
                "filename": filename,
                "mtime":    mtime,
                "mentions": mentions,
                "label":    label,
            })
        })
        .collect();

    Ok(Json(json!({"items": items})))
}

/// `GET /reports/:filename` — serve a single HTML report by filename.
/// Path-traversal safe: rejects any name containing `/`, `\`, `..`, or
/// not ending in `.html`.
async fn serve_report(
    State(s): State<AppState>,
    Path(filename): Path<String>,
) -> Result<impl IntoResponse, (StatusCode, String)> {
    let dir = s
        .reports_dir
        .as_ref()
        .ok_or((StatusCode::NOT_FOUND, "reports layer disabled".to_string()))?;
    if !is_safe_report_filename(&filename) {
        return Err((StatusCode::BAD_REQUEST, "invalid filename".to_string()));
    }
    let path = dir.join(&filename);
    let body = fs::read(&path)
        .map_err(|_| (StatusCode::NOT_FOUND, format!("report not found: {filename}")))?;
    Ok((
        [(axum::http::header::CONTENT_TYPE, "text/html; charset=utf-8")],
        body,
    ))
}

fn is_safe_report_filename(name: &str) -> bool {
    if !name.ends_with(".html") {
        return false;
    }
    if name.contains('/') || name.contains('\\') || name.contains("..") {
        return false;
    }
    // Restrict the rest of the alphabet to a sane subset — file names we
    // generate are date-keyed (`promote-YYYY-MM-DD.html`) but allow tags
    // and underscores for future report kinds.
    name.chars().all(|c| {
        c.is_ascii_alphanumeric()
            || c == '-'
            || c == '_'
            || c == '.'
    })
}

// ── Canvas chat endpoint (B-mode discussion with spawned Claude Code) ────
//
// Each chat round trip spawns a fresh `claude -p "<full prompt>"` process,
// captures stdout, returns it. Stateless on the server: full conversation
// history is rebuilt into the prompt every call (Anthropic chat history
// is the cheapest way to carry continuity without managing a persistent
// PTY session — that's P2/B M2 territory).
//
// Context auto-attached:
//   - Focused node's full content
//   - Top-N neighbors with snippets (cofires + annotates + supersedes +
//     summarizes + references — structural and attention edges, not
//     ephemeral coactivation)
//
// The spawned claude has full access to whatever MCP servers are configured
// in the user's `~/.claude/mcp.json` — meaning it can call memory_save /
// memory_link / dream_* directly when the user explicitly asks. We don't
// inject those tools here; the spawned session has them via Claude Code's
// own config.

#[derive(Deserialize)]
struct ChatMessage {
    role: String,    // "user" | "assistant"
    content: String,
}

#[derive(Deserialize)]
struct CanvasChatPayload {
    focus_key: String,
    /// Conversation so far (excluding the new message). Frontend keeps
    /// this in canvasState and resends each round so we can be stateless.
    #[serde(default)]
    history: Vec<ChatMessage>,
    /// New user message.
    message: String,
    /// Per-spawn timeout in seconds. Default 90s — long enough for
    /// thinking + tool use, short enough that a stuck spawn doesn't
    /// block the canvas indefinitely.
    #[serde(default)]
    timeout_secs: Option<u64>,
}

const CANVAS_CHAT_NEIGHBOR_LIMIT: usize = 6;
const CANVAS_CHAT_SNIPPET_CHARS: usize = 280;
const CANVAS_CHAT_DEFAULT_TIMEOUT_SECS: u64 = 90;
const CANVAS_CHAT_MAX_TIMEOUT_SECS: u64 = 600;

async fn api_canvas_chat(
    State(s): State<AppState>,
    Json(p): Json<CanvasChatPayload>,
) -> Result<Json<Value>, (StatusCode, String)> {
    let focus = p.focus_key.trim();
    let user_msg = p.message.trim();
    if focus.is_empty() {
        return Err((StatusCode::BAD_REQUEST, "focus_key required".into()));
    }
    if user_msg.is_empty() {
        return Err((StatusCode::BAD_REQUEST, "message required".into()));
    }

    // Build the context block (focus node + neighbors). Best-effort: a
    // missing focus node still produces a usable prompt — the agent can
    // ask the user for context.
    let focus_block = build_focus_block(&s, focus).await;
    let neighbor_block = build_neighbor_block(&s, focus).await;
    let history_block = format_history(&p.history);

    let prompt = format!(
        "你正在 Palace 画布的 chat panel 里和用户讨论 memory 节点 `{focus}`。\n\
         你的目标是帮用户思考、提出连接、起草 working_doc 内容。\n\
         回复用中文，简洁直接，避免空泛。\n\
         如果用户想沉淀某段为 working_doc，提示他可以点 [→ copy to editor]。\n\
         如果用户消息里出现 `[image: /tmp/canvas-chat-attachments/...]` 标记（粘贴的图），\
         请用 Read 工具读取那个路径来看图，然后基于图的内容回答。\n\n\
         ## 当前焦点节点\n{focus_block}\n\n\
         ## 邻居节点（top {n} by edge weight）\n{neighbor_block}\n\n\
         ## 对话历史\n{history_block}\n\n\
         ## 用户最新消息\n{user_msg}\n",
        focus = focus,
        n = CANVAS_CHAT_NEIGHBOR_LIMIT,
        focus_block = focus_block,
        neighbor_block = neighbor_block,
        history_block = history_block,
        user_msg = user_msg,
    );

    let timeout = p
        .timeout_secs
        .unwrap_or(CANVAS_CHAT_DEFAULT_TIMEOUT_SECS)
        .min(CANVAS_CHAT_MAX_TIMEOUT_SECS);

    // Spawn `claude -p` with the prompt. Inherits palace's env so the
    // wrapper-injected ANTHROPIC_API_KEY (or whichever provider) carries
    // through. cwd = palace's cwd — Claude Code reads MCP config relative
    // to that, so it gets the same agent-bridge tools the user sees.
    let mut cmd = tokio::process::Command::new("claude");
    cmd.arg("-p").arg(&prompt);
    cmd.stdin(std::process::Stdio::null());
    cmd.stdout(std::process::Stdio::piped());
    cmd.stderr(std::process::Stdio::piped());

    let started = SystemTime::now();
    let child = cmd
        .spawn()
        .map_err(|e| (StatusCode::INTERNAL_SERVER_ERROR, format!("spawn claude: {e}")))?;

    let output = match tokio::time::timeout(
        std::time::Duration::from_secs(timeout),
        child.wait_with_output(),
    )
    .await
    {
        Ok(Ok(out)) => out,
        Ok(Err(e)) => {
            return Err((
                StatusCode::INTERNAL_SERVER_ERROR,
                format!("wait claude: {e}"),
            ));
        }
        Err(_elapsed) => {
            return Err((
                StatusCode::GATEWAY_TIMEOUT,
                format!("claude exceeded {timeout}s timeout"),
            ));
        }
    };

    let stdout = String::from_utf8_lossy(&output.stdout).into_owned();
    let stderr = String::from_utf8_lossy(&output.stderr).into_owned();
    let elapsed_ms = started
        .elapsed()
        .map(|d| d.as_millis() as u64)
        .unwrap_or(0);

    if !output.status.success() {
        // Surface stderr but truncated — don't leak huge logs to the
        // browser. Caller can repro via terminal if they want full output.
        let trimmed: String = stderr.chars().take(800).collect();
        return Err((
            StatusCode::BAD_GATEWAY,
            format!(
                "claude exited {:?} after {elapsed_ms}ms: {}",
                output.status.code(),
                trimmed
            ),
        ));
    }

    Ok(Json(json!({
        "ok":         true,
        "assistant":  stdout.trim_end(),
        "elapsed_ms": elapsed_ms,
        "stderr":     if stderr.is_empty() { Value::Null } else { Value::String(stderr) },
    })))
}

// ── Streaming canvas chat (P8) ──────────────────────────────────────────
//
// SSE counterpart of `api_canvas_chat`. Spawns `claude -p
// --output-format=stream-json --verbose --include-partial-messages` and
// forwards `content_block_delta.text_delta.text` chunks as SSE events,
// so the canvas chat panel can render tokens as they arrive instead of
// waiting for the full response.
//
// SSE events emitted:
//   data: {"type":"delta","text":"..."}       — one token chunk
//   data: {"type":"done","elapsed_ms":N}      — process exited cleanly
//   data: {"type":"error","message":"..."}    — spawn / nonzero exit /
//                                                timeout / parse fail
//
// stream-json shape (relevant subset):
//   {"type":"stream_event","event":{"type":"content_block_delta",
//    "delta":{"type":"text_delta","text":"…"}}, …}
//   {"type":"result","subtype":"success", …}    final summary
//
// Failure handling: any spawn / process error becomes an SSE error event
// rather than an HTTP error response — the connection is already open,
// the client needs structured info to surface to the user.

async fn api_canvas_chat_stream(
    State(s): State<AppState>,
    Json(p): Json<CanvasChatPayload>,
) -> Sse<impl futures::Stream<Item = std::result::Result<SseEvent, std::convert::Infallible>>> {
    use futures::stream;
    use std::convert::Infallible;
    use tokio::io::{AsyncBufReadExt, BufReader};
    use tokio::sync::mpsc;

    let focus = p.focus_key.trim().to_string();
    let user_msg = p.message.trim().to_string();

    let (tx, rx) = mpsc::unbounded_channel::<SseEvent>();
    let send_err = |tx: &mpsc::UnboundedSender<SseEvent>, msg: String| {
        let _ = tx.send(
            SseEvent::default().data(json!({"type":"error","message":msg}).to_string()),
        );
    };

    // Build the prompt now (uses State; can't move S into the spawn).
    // Empty inputs are flagged early but the actual error is sent from
    // inside the spawn so the SSE stream has a single return shape.
    let validation_err = if focus.is_empty() || user_msg.is_empty() {
        Some("focus_key + message required".to_string())
    } else {
        None
    };
    let focus_block = if validation_err.is_none() {
        build_focus_block(&s, &focus).await
    } else {
        String::new()
    };
    let neighbor_block = if validation_err.is_none() {
        build_neighbor_block(&s, &focus).await
    } else {
        String::new()
    };
    let history_block = format_history(&p.history);

    let prompt = format!(
        "你正在 Palace 画布的 chat panel 里和用户讨论 memory 节点 `{focus}`。\n\
         你的目标是帮用户思考、提出连接、起草 working_doc 内容。\n\
         回复用中文，简洁直接，避免空泛。\n\
         如果用户想沉淀某段为 working_doc，提示他可以点 [→ copy to editor]。\n\
         如果用户消息里出现 `[image: /tmp/canvas-chat-attachments/...]` 标记（粘贴的图），\
         请用 Read 工具读取那个路径来看图，然后基于图的内容回答。\n\n\
         ## 当前焦点节点\n{focus_block}\n\n\
         ## 邻居节点（top {n} by edge weight）\n{neighbor_block}\n\n\
         ## 对话历史\n{history_block}\n\n\
         ## 用户最新消息\n{user_msg}\n",
        focus = focus,
        n = CANVAS_CHAT_NEIGHBOR_LIMIT,
        focus_block = focus_block,
        neighbor_block = neighbor_block,
        history_block = history_block,
        user_msg = user_msg,
    );

    let timeout = p
        .timeout_secs
        .unwrap_or(CANVAS_CHAT_DEFAULT_TIMEOUT_SECS)
        .min(CANVAS_CHAT_MAX_TIMEOUT_SECS);

    // Spawn streaming claude in a background task; bg pipes parsed
    // deltas into `tx`. SSE response polls `rx` until the bg task
    // emits "done" or "error" and closes the channel.
    tokio::spawn(async move {
        let started = SystemTime::now();
        if let Some(msg) = validation_err {
            send_err(&tx, msg);
            let _ = tx.send(
                SseEvent::default().data(json!({"type":"done","elapsed_ms":0}).to_string()),
            );
            return;
        }
        let mut cmd = tokio::process::Command::new("claude");
        cmd.arg("-p")
            .arg("--output-format=stream-json")
            .arg("--verbose")
            .arg("--include-partial-messages")
            .arg(&prompt);
        cmd.stdin(std::process::Stdio::null());
        cmd.stdout(std::process::Stdio::piped());
        cmd.stderr(std::process::Stdio::piped());
        let mut child = match cmd.spawn() {
            Ok(c) => c,
            Err(e) => {
                send_err(&tx, format!("spawn claude: {e}"));
                let _ = tx.send(
                    SseEvent::default()
                        .data(json!({"type":"done","elapsed_ms":0}).to_string()),
                );
                return;
            }
        };
        let stdout = match child.stdout.take() {
            Some(s) => s,
            None => {
                send_err(&tx, "no stdout pipe".to_string());
                let _ = tx.send(
                    SseEvent::default()
                        .data(json!({"type":"done","elapsed_ms":0}).to_string()),
                );
                return;
            }
        };

        let reader = BufReader::new(stdout);
        let mut lines = reader.lines();
        // Track each content_block index → kind (text / tool_use / thinking)
        // because content_block_stop arrives with only the index, not the
        // kind. We need the kind to decide whether to emit a tool_stop.
        let mut block_kind_by_index: std::collections::HashMap<i64, String> =
            std::collections::HashMap::new();
        let read_fut = async {
            while let Ok(Some(line)) = lines.next_line().await {
                if line.trim().is_empty() {
                    continue;
                }
                // Lossy parse — a malformed line is skipped rather than
                // killing the stream.
                let val: Value = match serde_json::from_str(&line) {
                    Ok(v) => v,
                    Err(_) => continue,
                };
                if val.get("type").and_then(|v| v.as_str()) != Some("stream_event") {
                    continue;
                }
                let event = match val.get("event") {
                    Some(e) => e,
                    None => continue,
                };
                let event_type = event.get("type").and_then(|v| v.as_str()).unwrap_or("");

                match event_type {
                    // Text token chunk — the bread-and-butter streaming event.
                    "content_block_delta" => {
                        let delta = match event.get("delta") {
                            Some(d) => d,
                            None => continue,
                        };
                        if delta.get("type").and_then(|v| v.as_str()) == Some("text_delta") {
                            if let Some(text) = delta.get("text").and_then(|v| v.as_str()) {
                                let _ = tx.send(
                                    SseEvent::default()
                                        .data(json!({"type":"delta","text":text}).to_string()),
                                );
                            }
                        } else if delta.get("type").and_then(|v| v.as_str())
                            == Some("input_json_delta")
                        {
                            // Tool args chunk — forward to client so the
                            // chip tooltip can accumulate the JSON args
                            // claude is sending to the tool.
                            if let (Some(idx), Some(chunk)) = (
                                event.get("index").and_then(|v| v.as_i64()),
                                delta.get("partial_json").and_then(|v| v.as_str()),
                            ) {
                                let _ = tx.send(SseEvent::default().data(
                                    json!({
                                        "type": "tool_args_delta",
                                        "index": idx,
                                        "chunk": chunk,
                                    })
                                    .to_string(),
                                ));
                            }
                        }
                        // signature_delta etc. — silently skipped for v1;
                        // reasoning signature not surfaced to the chat panel.
                    }
                    // Block start — record kind by index; if it's a tool_use
                    // emit tool_start with the tool name + id so the client
                    // can render a chip.
                    "content_block_start" => {
                        let idx = match event.get("index").and_then(|v| v.as_i64()) {
                            Some(i) => i,
                            None => continue,
                        };
                        let cb = match event.get("content_block") {
                            Some(c) => c,
                            None => continue,
                        };
                        let kind = cb
                            .get("type")
                            .and_then(|v| v.as_str())
                            .unwrap_or("")
                            .to_string();
                        block_kind_by_index.insert(idx, kind.clone());
                        if kind == "tool_use" {
                            let name = cb
                                .get("name")
                                .and_then(|v| v.as_str())
                                .unwrap_or("")
                                .to_string();
                            let id = cb
                                .get("id")
                                .and_then(|v| v.as_str())
                                .unwrap_or("")
                                .to_string();
                            let _ = tx.send(SseEvent::default().data(
                                json!({
                                    "type": "tool_start",
                                    "index": idx,
                                    "name": name,
                                    "id": id,
                                })
                                .to_string(),
                            ));
                        }
                    }
                    // Block end — if it was a tool_use, emit tool_stop so
                    // the client flips the chip from "running" to "done".
                    "content_block_stop" => {
                        let idx = match event.get("index").and_then(|v| v.as_i64()) {
                            Some(i) => i,
                            None => continue,
                        };
                        if let Some(kind) = block_kind_by_index.get(&idx) {
                            if kind == "tool_use" {
                                let _ = tx.send(SseEvent::default().data(
                                    json!({"type":"tool_stop","index":idx}).to_string(),
                                ));
                            }
                        }
                    }
                    // message_start / message_delta / message_stop are
                    // currently ignored — the SSE done event fires on
                    // process exit (sub-thread) which is the simpler
                    // truth-of-completion signal.
                    _ => {}
                }
            }
        };

        let result = tokio::time::timeout(
            std::time::Duration::from_secs(timeout),
            async {
                read_fut.await;
                child.wait().await
            },
        )
        .await;

        let elapsed_ms = started.elapsed().map(|d| d.as_millis() as u64).unwrap_or(0);
        match result {
            Ok(Ok(status)) if status.success() => {
                let _ = tx.send(
                    SseEvent::default()
                        .data(json!({"type":"done","elapsed_ms":elapsed_ms}).to_string()),
                );
            }
            Ok(Ok(status)) => {
                send_err(
                    &tx,
                    format!("claude exited code={:?} after {elapsed_ms}ms", status.code()),
                );
                let _ = tx.send(
                    SseEvent::default()
                        .data(json!({"type":"done","elapsed_ms":elapsed_ms}).to_string()),
                );
            }
            Ok(Err(e)) => {
                send_err(&tx, format!("wait claude: {e}"));
                let _ = tx.send(
                    SseEvent::default()
                        .data(json!({"type":"done","elapsed_ms":elapsed_ms}).to_string()),
                );
            }
            Err(_elapsed) => {
                let _ = child.start_kill();
                send_err(&tx, format!("claude exceeded {timeout}s timeout"));
                let _ = tx.send(
                    SseEvent::default()
                        .data(json!({"type":"done","elapsed_ms":elapsed_ms}).to_string()),
                );
            }
        }
    });

    let stream = stream::unfold(rx, |mut rx| async move {
        rx.recv().await.map(|e| (Ok::<_, Infallible>(e), rx))
    });
    Sse::new(stream).keep_alive(KeepAlive::default())
}

async fn build_focus_block(s: &AppState, key: &str) -> String {
    // Try sqlite first.
    if let Ok(Some(m)) = s.store.memory_get(key).await {
        let tags = if m.tags.is_empty() {
            String::new()
        } else {
            format!("\ntags: {}", m.tags.join(", "))
        };
        return format!(
            "**{}** ({})  importance {:.2}{}\n\n{}",
            m.key,
            m.kind,
            m.importance,
            tags,
            m.content,
        );
    }
    // Markdown fallback — same lookup the side panel uses.
    if let Some(root) = &s.markdown_root {
        let path = root.join(format!("{key}.md"));
        if let Ok(body) = fs::read_to_string(&path) {
            let mm = parse_markdown_memory(key.to_string(), &body);
            return format!(
                "**{}** ({}, markdown)\n\n{}\n\n{}",
                mm.key, mm.kind, mm.description, mm.content,
            );
        }
    }
    format!("**{key}** — not found in store")
}

async fn build_neighbor_block(s: &AppState, key: &str) -> String {
    let nbrs = match s.store.memory_neighbors(key).await {
        Ok(v) => v,
        Err(_) => return "(no neighbors)".to_string(),
    };
    if nbrs.is_empty() {
        return "(no neighbors)".to_string();
    }
    // Filter to structural edges (skip ephemeral coactivation), sort by
    // weight desc, take top N.
    let mut filtered: Vec<_> = nbrs
        .into_iter()
        .filter(|e| {
            !matches!(
                e.edge_type.as_str(),
                "coactivation"
            )
        })
        .collect();
    filtered.sort_by(|a, b| {
        b.weight
            .partial_cmp(&a.weight)
            .unwrap_or(std::cmp::Ordering::Equal)
    });
    filtered.truncate(CANVAS_CHAT_NEIGHBOR_LIMIT);
    if filtered.is_empty() {
        return "(no structural neighbors)".to_string();
    }

    let mut out = String::new();
    for e in filtered {
        let other_key = if e.from_key == key {
            &e.to_key
        } else {
            &e.from_key
        };
        let snippet = neighbor_snippet(s, other_key).await;
        out.push_str(&format!(
            "- **{}** [{}, w={:.2}]: {}\n",
            other_key, e.edge_type, e.weight, snippet,
        ));
    }
    out
}

async fn neighbor_snippet(s: &AppState, key: &str) -> String {
    if let Ok(Some(m)) = s.store.memory_get(key).await {
        let preview: String = m
            .content
            .chars()
            .take(CANVAS_CHAT_SNIPPET_CHARS)
            .collect::<String>()
            .replace('\n', " ");
        if m.content.chars().count() > CANVAS_CHAT_SNIPPET_CHARS {
            return format!("{preview}…");
        }
        return preview;
    }
    if let Some(root) = &s.markdown_root {
        let path = root.join(format!("{key}.md"));
        if let Ok(body) = fs::read_to_string(&path) {
            let mm = parse_markdown_memory(key.to_string(), &body);
            let combined = if mm.description.is_empty() {
                mm.content
            } else {
                format!("{} — {}", mm.description, mm.content)
            };
            let preview: String = combined
                .chars()
                .take(CANVAS_CHAT_SNIPPET_CHARS)
                .collect::<String>()
                .replace('\n', " ");
            if combined.chars().count() > CANVAS_CHAT_SNIPPET_CHARS {
                return format!("{preview}…");
            }
            return preview;
        }
    }
    "(content unavailable)".to_string()
}

fn format_history(history: &[ChatMessage]) -> String {
    if history.is_empty() {
        return "(none — this is the first message)".to_string();
    }
    let mut out = String::new();
    for m in history {
        let label = if m.role == "user" { "USER" } else { "ASSISTANT" };
        out.push_str(&format!("**{}**: {}\n\n", label, m.content));
    }
    out
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn split_frontmatter_basic() {
        let body = "---\nname: foo\ntype: project\n---\n# Hello\n\nbody.";
        let (fm, content) = split_frontmatter(body);
        assert!(fm.is_some());
        assert!(fm.unwrap().contains("type: project"));
        assert_eq!(content, "# Hello\n\nbody.");
    }

    #[test]
    fn split_frontmatter_absent() {
        let body = "# No frontmatter\n\nbody";
        let (fm, content) = split_frontmatter(body);
        assert!(fm.is_none());
        assert_eq!(content, body);
    }

    #[test]
    fn extract_links_finds_md_refs() {
        let content = "see [foo](foo.md) and [bar](bar.md). also (baz.md).";
        let links = extract_links(content);
        assert_eq!(links, vec!["bar", "baz", "foo"]);
    }

    #[test]
    fn extract_links_finds_bare_mentions() {
        // Memory bodies often reference siblings by bare filename
        // ("see project_warp_drop_to_museum.md for retirement context").
        let content = "see project_warp_drop_to_museum.md for retirement context";
        let links = extract_links(content);
        assert_eq!(links, vec!["project_warp_drop_to_museum"]);
    }

    #[test]
    fn extract_links_ignores_non_md() {
        let content = "see (https://example.com) and (some text)";
        let links = extract_links(content);
        assert!(links.is_empty());
    }

    #[test]
    fn extract_links_rejects_numeric_start() {
        // Avoid accidentally matching "42.md" or "123.md" — not real keys.
        let content = "see 42.md or 999.md";
        let links = extract_links(content);
        assert!(links.is_empty());
    }

    #[test]
    fn parse_full_memory() {
        let body = "---\nname: My Vision\ndescription: A short one\ntype: project\n---\nbody with (related.md) ref.";
        let m = parse_markdown_memory("test".to_string(), body);
        assert_eq!(m.key, "test");
        assert_eq!(m.kind, "project");
        assert_eq!(m.description, "A short one");
        assert_eq!(m.links_to, vec!["related"]);
    }
}
