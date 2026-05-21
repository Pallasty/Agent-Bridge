//! v20 Stage 2 — HTTP client for cross-machine MCP tool routing.
//!
//! When an MCP tool gets `peer: "host:port"` in its args, it delegates to
//! the peer's `daemon-http` server instead of reading/writing local state.
//! This module is the thin client that wraps those calls.
//!
//! Transport: plain HTTP (the tailscale layer handles encryption between
//! tailnet peers — see RFC §2). Not for use outside a trusted tailnet.
//!
//! Errors are wrapped in `ab_core::Error::Backend(String)` so MCP tools
//! can `?`-propagate them and the caller sees a clean error message.

use ab_core::{Error, Result};
use ab_store::{AgentMessageRecord, AgentPresenceRecord, ForumPostRecord, ForumThreadRecord};
use serde::{de::DeserializeOwned, Deserialize, Serialize};
use serde_json::Value;
use std::time::Duration;

/// Build a `http://<peer>` base URL, accepting either `host:port` or a full
/// URL. Trims trailing `/` so concatenation with `/path` is unambiguous.
fn base_url(peer: &str) -> String {
    let trimmed = peer.trim_end_matches('/');
    if trimmed.starts_with("http://") || trimmed.starts_with("https://") {
        trimmed.to_string()
    } else {
        format!("http://{trimmed}")
    }
}

/// Shared client with a 10s default timeout. axum daemon endpoints are
/// fast (single SQLite query) but we don't want a wedged peer to block
/// MCP tool calls indefinitely.
fn client() -> Result<reqwest::Client> {
    reqwest::Client::builder()
        .timeout(Duration::from_secs(10))
        .build()
        .map_err(|e| Error::Backend(format!("peer http client init: {e}")))
}

fn map_err<T, E: std::fmt::Display>(prefix: &str, r: std::result::Result<T, E>) -> Result<T> {
    r.map_err(|e| Error::Backend(format!("peer.{prefix}: {e}")))
}

fn body_snippet(body: &str) -> String {
    const MAX: usize = 512;
    let mut out = String::new();
    for ch in body.chars().take(MAX) {
        if ch.is_control() && ch != '\n' && ch != '\t' {
            out.push(' ');
        } else {
            out.push(ch);
        }
    }
    if body.chars().count() > MAX {
        out.push_str("...");
    }
    out
}

async fn json_body<T: DeserializeOwned>(
    prefix: &str,
    url: &str,
    response: reqwest::Response,
) -> Result<T> {
    let status = response.status();
    let content_type = response
        .headers()
        .get(reqwest::header::CONTENT_TYPE)
        .and_then(|v| v.to_str().ok())
        .unwrap_or("<missing>")
        .to_string();
    let text = map_err(&format!("{prefix}.body"), response.text().await)?;
    decode_json_body(prefix, url, status, &content_type, &text)
}

fn decode_json_body<T: DeserializeOwned>(
    prefix: &str,
    url: &str,
    status: reqwest::StatusCode,
    content_type: &str,
    text: &str,
) -> Result<T> {
    if !status.is_success() {
        return Err(Error::Backend(format!(
            "peer.{prefix}.status: HTTP {status}; url={url}; content_type={content_type}; body={}",
            body_snippet(text)
        )));
    }
    serde_json::from_str(text).map_err(|e| {
        Error::Backend(format!(
            "peer.{prefix}.json: {e}; url={url}; status={status}; content_type={content_type}; body={}",
            body_snippet(text)
        ))
    })
}

#[derive(Deserialize)]
struct ThreadsResponse {
    threads: Vec<ForumThreadRecord>,
}

pub async fn forum_list_threads(
    peer: &str,
    board: &str,
    unread_for: Option<&str>,
    status: Option<&str>,
    limit: u32,
) -> Result<Vec<ForumThreadRecord>> {
    let url = format!("{}/forum/threads", base_url(peer));
    let mut q: Vec<(&str, String)> = vec![("board", board.into()), ("limit", limit.to_string())];
    if let Some(u) = unread_for {
        q.push(("unread_for", u.into()));
    }
    if let Some(s) = status {
        q.push(("status", s.into()));
    }
    let r = map_err(
        "forum_list_threads.send",
        client()?.get(&url).query(&q).send().await,
    )?;
    let body: ThreadsResponse = json_body("forum_list_threads", &url, r).await?;
    Ok(body.threads)
}

#[derive(Deserialize)]
struct PostsResponse {
    posts: Vec<ForumPostRecord>,
}

#[derive(Debug, Deserialize)]
pub struct ProjectedPostsResponse {
    pub posts: Vec<serde_json::Value>,
    pub next_cursor: Option<i64>,
    pub projection: Option<serde_json::Value>,
}

fn forum_read_query(
    thread_id: Option<i64>,
    board: Option<&str>,
    since_post_id: Option<i64>,
    unread_for: Option<&str>,
    limit: u32,
) -> Vec<(&'static str, String)> {
    let mut q: Vec<(&str, String)> = vec![("limit", limit.to_string())];
    if let Some(t) = thread_id {
        q.push(("thread_id", t.to_string()));
    }
    if let Some(b) = board {
        q.push(("board", b.into()));
    }
    if let Some(s) = since_post_id {
        q.push(("since_post_id", s.to_string()));
    }
    if let Some(u) = unread_for {
        q.push(("unread_for", u.into()));
    }
    q
}

pub async fn forum_read(
    peer: &str,
    thread_id: Option<i64>,
    board: Option<&str>,
    since_post_id: Option<i64>,
    unread_for: Option<&str>,
    limit: u32,
) -> Result<Vec<ForumPostRecord>> {
    let url = format!("{}/forum/posts", base_url(peer));
    let q = forum_read_query(thread_id, board, since_post_id, unread_for, limit);
    let r = map_err(
        "forum_read.send",
        client()?.get(&url).query(&q).send().await,
    )?;
    let body: PostsResponse = json_body("forum_read", &url, r).await?;
    Ok(body.posts)
}

pub async fn forum_read_projected(
    peer: &str,
    thread_id: Option<i64>,
    board: Option<&str>,
    since_post_id: Option<i64>,
    unread_for: Option<&str>,
    limit: u32,
    compact: bool,
    body_max_chars: usize,
    include_refs: bool,
) -> Result<ProjectedPostsResponse> {
    let url = format!("{}/forum/posts", base_url(peer));
    let mut q = forum_read_query(thread_id, board, since_post_id, unread_for, limit);
    q.push(("compact", compact.to_string()));
    q.push(("body_max_chars", body_max_chars.to_string()));
    q.push(("include_refs", include_refs.to_string()));
    let r = map_err(
        "forum_read.send",
        client()?.get(&url).query(&q).send().await,
    )?;
    json_body("forum_read", &url, r).await
}

#[derive(Deserialize)]
struct PresenceResponse {
    agents: Vec<AgentPresenceRecord>,
}

pub async fn agent_presence_list(
    peer: &str,
    project: Option<&str>,
    role: Option<&str>,
    max_idle_secs: i64,
    limit: u32,
) -> Result<Vec<AgentPresenceRecord>> {
    let url = format!("{}/presence", base_url(peer));
    let mut q: Vec<(&str, String)> = vec![
        ("max_idle_secs", max_idle_secs.to_string()),
        ("limit", limit.to_string()),
    ];
    if let Some(p) = project {
        q.push(("project", p.into()));
    }
    if let Some(r) = role {
        q.push(("role", r.into()));
    }
    let r = map_err("presence.send", client()?.get(&url).query(&q).send().await)?;
    let body: PresenceResponse = json_body("presence", &url, r).await?;
    Ok(body.agents)
}

#[derive(Serialize)]
pub struct ForumPostRequest<'a> {
    pub author: &'a str,
    pub body: &'a str,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub thread_id: Option<i64>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub board: Option<&'a str>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub title: Option<&'a str>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub kind: Option<&'a str>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub tags: Option<&'a [String]>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub refs: Option<&'a Value>,
}

/// Issue a `POST /forum/post` to the peer. Returns the JSON body the daemon
/// emits (mirrors local `forum_post` shape: `{status, post_id, thread_id, ...}`).
pub async fn forum_post(peer: &str, req: ForumPostRequest<'_>) -> Result<Value> {
    let url = format!("{}/forum/post", base_url(peer));
    let r = map_err(
        "forum_post.send",
        client()?.post(&url).json(&req).send().await,
    )?;
    json_body("forum_post", &url, r).await
}

// ── XM v0.1 — cross-machine agent messaging ──────────────────────────────

#[derive(Serialize)]
struct AgentMessageRequest<'a> {
    from_session: &'a str,
    to_session: &'a str,
    payload: &'a Value,
}

#[derive(Deserialize)]
struct AgentMessageResponse {
    id: i64,
}

/// `POST /agent/messages` — write a message to `peer`'s inbox. Returns the
/// new row id assigned by the remote daemon. Tailnet-trusted; `from_session`
/// is caller-claimed (R-XM-A in design §3).
pub async fn agent_message(
    peer: &str,
    from_session: &str,
    to_session: &str,
    payload: &Value,
) -> Result<i64> {
    let url = format!("{}/agent/messages", base_url(peer));
    let body = AgentMessageRequest {
        from_session,
        to_session,
        payload,
    };
    let r = map_err(
        "agent_message.send",
        client()?.post(&url).json(&body).send().await,
    )?;
    let body: AgentMessageResponse = json_body("agent_message", &url, r).await?;
    Ok(body.id)
}

#[derive(Deserialize)]
struct InboxResponse {
    messages: Vec<AgentMessageRecord>,
}

/// `GET /agent/inbox` — read `peer`'s inbox for `to_session`. The returned
/// rows live in the remote node's SQLite; this client does NOT replicate
/// them locally (per design §3 split: payload is authoritative on the
/// recipient daemon, forum post is the wake signal).
pub async fn agent_inbox(
    peer: &str,
    to_session: &str,
    since_id: Option<i64>,
    unread_only: bool,
    limit: u32,
) -> Result<Vec<AgentMessageRecord>> {
    let url = format!("{}/agent/inbox", base_url(peer));
    let mut q: Vec<(&str, String)> = vec![
        ("to_session", to_session.into()),
        ("limit", limit.to_string()),
        ("unread_only", unread_only.to_string()),
    ];
    if let Some(s) = since_id {
        q.push(("since_id", s.to_string()));
    }
    let r = map_err(
        "agent_inbox.send",
        client()?.get(&url).query(&q).send().await,
    )?;
    let body: InboxResponse = json_body("agent_inbox", &url, r).await?;
    Ok(body.messages)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn base_url_handles_bare_host_port() {
        assert_eq!(base_url("100.93.4.56:7878"), "http://100.93.4.56:7878");
        assert_eq!(base_url("aio2.ts.net:7878/"), "http://aio2.ts.net:7878");
    }

    #[test]
    fn base_url_passes_through_explicit_scheme() {
        assert_eq!(base_url("http://x:7878/"), "http://x:7878");
        assert_eq!(base_url("https://x:7878"), "https://x:7878");
    }

    #[test]
    fn body_snippet_strips_control_chars_and_truncates() {
        let input = format!("ok\u{0000}{}\n", "x".repeat(600));
        let out = body_snippet(&input);
        assert!(out.starts_with("ok "));
        assert!(out.ends_with("..."));
        assert!(!out.contains('\u{0000}'));
    }

    #[test]
    fn forum_read_query_includes_cursor_and_scope() {
        let q = forum_read_query(Some(18), Some("design"), Some(366), Some("codex"), 25);
        assert_eq!(
            q,
            vec![
                ("limit", "25".into()),
                ("thread_id", "18".into()),
                ("board", "design".into()),
                ("since_post_id", "366".into()),
                ("unread_for", "codex".into()),
            ]
        );
    }

    #[test]
    fn decode_json_body_reports_context_on_shape_mismatch() {
        let result = decode_json_body::<PostsResponse>(
            "forum_read",
            "http://peer:7878/forum/posts",
            reqwest::StatusCode::OK,
            "text/plain",
            "not forum json",
        );
        let err = match result {
            Ok(_) => panic!("invalid response shape should be diagnostic"),
            Err(err) => err,
        };
        let msg = err.to_string();
        assert!(msg.contains("peer.forum_read.json"));
        assert!(msg.contains("url=http://peer:7878/forum/posts"));
        assert!(msg.contains("content_type=text/plain"));
        assert!(msg.contains("body=not forum json"));
    }
}
