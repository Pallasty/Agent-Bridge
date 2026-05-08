//! Brave Search REST API client for the agent-bridge MCP layer.
//!
//! API-first SaaS pattern, 5th instance. Auth is `X-Subscription-Token: <token>`
//! (NOT Bearer). Tokens come from env (`BRAVE_SEARCH_TOKEN`) — Brave's API
//! keys start with `BSA`. Free tier allows ~1 query/sec, 2000/month.
//!
//! Endpoint: GET https://api.search.brave.com/res/v1/web/search?q=<q>&count=<n>

use ab_core::{Error, Result};
use serde::{Deserialize, Serialize};
use std::time::Duration;

const API_BASE: &str = "https://api.search.brave.com/res/v1";
const USER_AGENT: &str = "agent-bridge-mcp";

#[derive(Debug)]
pub struct BraveClient {
    token: String,
    http: reqwest::Client,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct WebHit {
    pub title: String,
    pub url: String,
    pub description: String,
    pub age: Option<String>,
    pub language: Option<String>,
}

impl BraveClient {
    pub fn from_env() -> Result<Self> {
        let token = std::env::var("BRAVE_SEARCH_TOKEN").map_err(|_| {
            Error::Backend(
                "BRAVE_SEARCH_TOKEN env not set; place a `BSA…` subscription \
                 token in /Media/Ubuntu/Documents/ClaudeCode.txt under \
                 '# Brave Search API' and reconnect MCP."
                    .into(),
            )
        })?;
        let http = reqwest::Client::builder()
            .timeout(Duration::from_secs(20))
            .user_agent(USER_AGENT)
            .build()
            .map_err(|e| Error::Backend(format!("brave http client init: {e}")))?;
        Ok(Self { token, http })
    }

    fn auth_headers(&self, rb: reqwest::RequestBuilder) -> reqwest::RequestBuilder {
        rb.header("X-Subscription-Token", &self.token)
            .header("Accept", "application/json")
    }

    pub async fn web_search(
        &self,
        query: &str,
        count: u32,
        country: Option<&str>,
        safesearch: Option<&str>,
    ) -> Result<Vec<WebHit>> {
        let mut url = format!(
            "{API_BASE}/web/search?q={}&count={}",
            urlencoding(query),
            count.clamp(1, 20)
        );
        if let Some(c) = country.filter(|s| !s.is_empty()) {
            url.push_str(&format!("&country={}", urlencoding(c)));
        }
        if let Some(s) = safesearch.filter(|s| !s.is_empty()) {
            url.push_str(&format!("&safesearch={}", urlencoding(s)));
        }
        let resp = self
            .auth_headers(self.http.get(&url))
            .send()
            .await
            .map_err(|e| Error::Backend(format!("brave web_search send: {e}")))?;
        let status = resp.status();
        let body = resp
            .text()
            .await
            .map_err(|e| Error::Backend(format!("brave web_search body: {e}")))?;
        if !status.is_success() {
            return Err(Error::Backend(format!(
                "brave web_search http {status}: {body}"
            )));
        }
        let v: serde_json::Value = serde_json::from_str(&body)
            .map_err(|e| Error::Backend(format!("brave web_search parse: {e}")))?;
        Ok(v.get("web")
            .and_then(|w| w.get("results"))
            .and_then(|x| x.as_array())
            .map(|arr| arr.iter().map(parse_web_hit).collect())
            .unwrap_or_default())
    }
}

fn parse_web_hit(v: &serde_json::Value) -> WebHit {
    WebHit {
        title: v
            .get("title")
            .and_then(|x| x.as_str())
            .unwrap_or("")
            .to_string(),
        url: v
            .get("url")
            .and_then(|x| x.as_str())
            .unwrap_or("")
            .to_string(),
        description: v
            .get("description")
            .and_then(|x| x.as_str())
            .unwrap_or("")
            .to_string(),
        age: v.get("age").and_then(|x| x.as_str()).map(String::from),
        language: v.get("language").and_then(|x| x.as_str()).map(String::from),
    }
}

fn urlencoding(s: &str) -> String {
    let mut out = String::with_capacity(s.len());
    for b in s.bytes() {
        match b {
            b'A'..=b'Z' | b'a'..=b'z' | b'0'..=b'9' | b'-' | b'_' | b'.' | b'~' => {
                out.push(b as char)
            }
            _ => out.push_str(&format!("%{b:02X}")),
        }
    }
    out
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn parse_typical_web_hit() {
        let v: serde_json::Value = serde_json::from_str(r#"{
            "title":"Rust Programming Language",
            "url":"https://www.rust-lang.org/",
            "description":"A language empowering everyone…",
            "age":"2023-01-15",
            "language":"en"
        }"#).unwrap();
        let h = parse_web_hit(&v);
        assert_eq!(h.title, "Rust Programming Language");
        assert_eq!(h.url, "https://www.rust-lang.org/");
        assert_eq!(h.age.as_deref(), Some("2023-01-15"));
        assert_eq!(h.language.as_deref(), Some("en"));
    }

    #[test]
    fn parse_minimal_web_hit() {
        let v: serde_json::Value = serde_json::from_str(r#"{
            "title":"x","url":"https://x","description":""
        }"#).unwrap();
        let h = parse_web_hit(&v);
        assert_eq!(h.title, "x");
        assert!(h.age.is_none());
        assert!(h.language.is_none());
    }

    #[test]
    fn url_encodes_query() {
        assert_eq!(urlencoding("hello world"), "hello%20world");
        assert_eq!(urlencoding("a&b=c"), "a%26b%3Dc");
        assert_eq!(urlencoding("rust-lang"), "rust-lang");
    }
}
