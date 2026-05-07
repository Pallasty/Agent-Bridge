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
use ab_store::{AgentPresenceRecord, ForumPostRecord, ForumThreadRecord};
use serde::{Deserialize, Serialize};
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
    let r = map_err("forum_list_threads.status", r.error_for_status())?;
    let body: ThreadsResponse = map_err("forum_list_threads.json", r.json().await)?;
    Ok(body.threads)
}

#[derive(Deserialize)]
struct PostsResponse {
    posts: Vec<ForumPostRecord>,
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
    let r = map_err("forum_read.send", client()?.get(&url).query(&q).send().await)?;
    let r = map_err("forum_read.status", r.error_for_status())?;
    let body: PostsResponse = map_err("forum_read.json", r.json().await)?;
    Ok(body.posts)
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
    let r = map_err("presence.status", r.error_for_status())?;
    let body: PresenceResponse = map_err("presence.json", r.json().await)?;
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
    let r = map_err("forum_post.send", client()?.post(&url).json(&req).send().await)?;
    let r = map_err("forum_post.status", r.error_for_status())?;
    map_err("forum_post.json", r.json().await)
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
}
