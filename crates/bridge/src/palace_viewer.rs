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
//!   - `GET /api/graph`         → merged `{ nodes, edges }` from both sources
//!   - `GET /api/memory/:key`   → single record (sqlite first, markdown fallback)
//!   - `POST /api/annotate`     → C1: write a new sqlite memory linked to a node
//!     (closes the 呼吸 loop — Palace exploration → annotation → memory)
//!
//! Bind defaults to `127.0.0.1` (single-user local view).
//!
//! See `vision_breathing_canvas.md` for the broader 呼吸式画布 design.

use ab_store::{MemoryListSort, MemoryRecord, StateStore};
use anyhow::{Context, Result};
use axum::{
    extract::{Path, Query, State},
    http::StatusCode,
    response::{Html, IntoResponse},
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
) -> Result<()> {
    if let Some(p) = &markdown_root {
        tracing::info!(path = %p.display(), "Palace markdown layer enabled");
    } else {
        tracing::info!("Palace markdown layer disabled (sqlite-only)");
    }

    let state = AppState {
        store,
        markdown_root,
        recent_clicks: Arc::new(Mutex::new(VecDeque::with_capacity(CLICK_WINDOW))),
    };
    let app = Router::new()
        .route("/", get(index))
        .route("/healthz", get(healthz))
        .route("/api/graph", get(api_graph))
        .route("/api/memory/:key", get(api_memory))
        .route("/api/annotate", post(api_annotate))
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

    // ── serialize ───────────────────────────────────────────────────────
    let mut nodes_json: Vec<Value> = active
        .iter()
        .map(|m| {
            json!({
                "id":         m.key,
                "kind":       m.kind,
                "importance": (m.importance * 1000.0).round() / 1000.0,
                "tags":       m.tags,
                "label":      m.key,
                "access":     m.access_count,
                "source":     "sqlite",
            })
        })
        .collect();

    for m in &md_only {
        nodes_json.push(json!({
            "id":         m.key,
            "kind":       m.kind,
            "importance": 0.7,    // markdown memories are user-curated → treat as high signal
            "tags":       Vec::<String>::new(),
            "label":      m.key,
            "access":     0,
            "source":     "markdown",
            "description": m.description,
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

    Ok(Json(json!({
        "nodes": nodes_json,
        "edges": edges_json,
        "stats": {
            "sqlite_nodes":   active.len(),
            "markdown_nodes": md_only.len(),
            "sqlite_edges":   sqlite_edges.len(),
            "markdown_edges": md_edges.len(),
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
    if let Some(m) = s
        .store
        .memory_get(&key)
        .await
        .map_err(|e| (StatusCode::INTERNAL_SERVER_ERROR, format!("memory_get: {e}")))?
    {
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

// ── Annotate endpoint (C1: closes the 呼吸 loop) ─────────────────────────

#[derive(Deserialize)]
struct AnnotatePayload {
    /// The node the user is annotating from. Becomes the `to_key` of an
    /// `annotates` edge.
    target_key: String,
    /// User-authored body. Becomes the `content` of the new sqlite memory.
    content: String,
}

/// Create a new sqlite memory authored from the Palace, linked back to
/// `target_key` via an `annotates` edge.
///
/// The new memory is `kind=annotation`, importance 0.6, scope-less (global
/// — visible from any project's Palace). The key is timestamp-prefixed so
/// multiple annotations stay sortable and unique.
///
/// Returns `{ ok: true, key: <new key> }` on success. The frontend should
/// re-fetch `/api/graph` to see the new node + edge.
async fn api_annotate(
    State(s): State<AppState>,
    Json(p): Json<AnnotatePayload>,
) -> Result<Json<Value>, (StatusCode, String)> {
    let target = p.target_key.trim();
    let body = p.content.trim();
    if target.is_empty() {
        return Err((StatusCode::BAD_REQUEST, "target_key required".into()));
    }
    if body.is_empty() {
        return Err((StatusCode::BAD_REQUEST, "content required".into()));
    }

    let now_millis = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map(|d| d.as_millis())
        .unwrap_or(0);
    let key = format!("palace_annotation_{now_millis:013}");

    let mem = MemoryRecord {
        key: key.clone(),
        kind: "annotation".to_string(),
        content: body.to_string(),
        tags: vec!["palace".to_string(), "annotation".to_string()],
        related_keys: vec![target.to_string()],
        scope: None,
        created_at: 0,
        updated_at: 0,
        last_accessed_at: 0,
        access_count: 0,
        importance: 0.6,
        status: "active".to_string(),
        trigger_pattern: None,
        superseded_by: None,
    };

    s.store
        .memory_save(&mem)
        .await
        .map_err(|e| (StatusCode::INTERNAL_SERVER_ERROR, format!("memory_save: {e}")))?;

    s.store
        .memory_link(&key, target, "annotates", 1.0)
        .await
        .map_err(|e| (StatusCode::INTERNAL_SERVER_ERROR, format!("memory_link: {e}")))?;

    Ok(Json(json!({
        "ok":  true,
        "key": key,
    })))
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
