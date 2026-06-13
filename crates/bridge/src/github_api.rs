//! GitHub REST API client for the agent-bridge MCP layer.
//!
//! Mirrors the API-first SaaS admin pattern used by `tailscale_api`: drive
//! GitHub's admin/CRUD surface directly via Bearer token instead of browser
//! automation. Token comes from env (`GITHUB_TOKEN`) — fine-grained PAT
//! (`github_pat_…`) or classic (`ghp_…`).

use ab_core::{Error, Result};
use serde::{Deserialize, Serialize};
use std::time::Duration;

const API_BASE: &str = "https://api.github.com";
const USER_AGENT: &str = "agent-bridge-mcp";
const API_VERSION: &str = "2022-11-28";

#[derive(Debug)]
pub struct GitHubClient {
    token: String,
    http: reqwest::Client,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct IssueSummary {
    pub number: u64,
    pub title: String,
    pub state: String,
    pub author: Option<String>,
    pub html_url: String,
    pub labels: Vec<String>,
    pub comments: u64,
    pub created_at: String,
    pub updated_at: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct PullSummary {
    pub number: u64,
    pub title: String,
    pub state: String,
    pub draft: bool,
    pub author: Option<String>,
    pub html_url: String,
    pub head: String,
    pub base: String,
    pub created_at: String,
    pub updated_at: String,
}

impl GitHubClient {
    pub fn from_env() -> Result<Self> {
        let token = std::env::var("GITHUB_TOKEN").map_err(|_| {
            Error::Backend(
                "GITHUB_TOKEN env not set; place a fine-grained or classic PAT in \
                 /Media/Ubuntu/Documents/ClaudeCode.txt under '# Github PAT Token' \
                 and reconnect MCP (the wrapper exports it for the child process)"
                    .into(),
            )
        })?;
        let http = reqwest::Client::builder()
            .timeout(Duration::from_secs(20))
            .user_agent(USER_AGENT)
            .build()
            .map_err(|e| Error::Backend(format!("github http client init: {e}")))?;
        Ok(Self { token, http })
    }

    fn auth_headers(&self, rb: reqwest::RequestBuilder) -> reqwest::RequestBuilder {
        rb.header("Authorization", format!("Bearer {}", self.token))
            .header("Accept", "application/vnd.github+json")
            .header("X-GitHub-Api-Version", API_VERSION)
    }

    pub async fn issue_list(
        &self,
        owner: &str,
        repo: &str,
        state: &str,
        per_page: u32,
        labels: Option<&str>,
    ) -> Result<Vec<IssueSummary>> {
        let mut url =
            format!("{API_BASE}/repos/{owner}/{repo}/issues?state={state}&per_page={per_page}");
        if let Some(l) = labels.filter(|s| !s.is_empty()) {
            url.push_str(&format!("&labels={}", urlencoding(l)));
        }
        let resp = self
            .auth_headers(self.http.get(&url))
            .send()
            .await
            .map_err(|e| Error::Backend(format!("github issue_list send: {e}")))?;
        let status = resp.status();
        let body = resp
            .text()
            .await
            .map_err(|e| Error::Backend(format!("github issue_list body: {e}")))?;
        if !status.is_success() {
            return Err(Error::Backend(format!(
                "github issue_list http {status}: {body}"
            )));
        }
        let raw: Vec<serde_json::Value> = serde_json::from_str(&body)
            .map_err(|e| Error::Backend(format!("github issue_list parse: {e}")))?;
        Ok(raw
            .into_iter()
            // Filter PRs out — GitHub's /issues endpoint also returns pull requests
            .filter(|v| v.get("pull_request").is_none())
            .map(parse_issue)
            .collect())
    }

    pub async fn issue_create(
        &self,
        owner: &str,
        repo: &str,
        title: &str,
        body: &str,
        labels: Option<Vec<String>>,
    ) -> Result<IssueSummary> {
        let url = format!("{API_BASE}/repos/{owner}/{repo}/issues");
        let mut payload = serde_json::json!({ "title": title, "body": body });
        if let Some(ls) = labels.filter(|v| !v.is_empty()) {
            payload["labels"] = serde_json::json!(ls);
        }
        let resp = self
            .auth_headers(self.http.post(&url))
            .json(&payload)
            .send()
            .await
            .map_err(|e| Error::Backend(format!("github issue_create send: {e}")))?;
        let status = resp.status();
        let resp_body = resp
            .text()
            .await
            .map_err(|e| Error::Backend(format!("github issue_create body: {e}")))?;
        if !status.is_success() {
            return Err(Error::Backend(format!(
                "github issue_create http {status}: {resp_body}"
            )));
        }
        let v: serde_json::Value = serde_json::from_str(&resp_body)
            .map_err(|e| Error::Backend(format!("github issue_create parse: {e}")))?;
        Ok(parse_issue(v))
    }

    pub async fn pr_list(
        &self,
        owner: &str,
        repo: &str,
        state: &str,
        per_page: u32,
    ) -> Result<Vec<PullSummary>> {
        let url =
            format!("{API_BASE}/repos/{owner}/{repo}/pulls?state={state}&per_page={per_page}");
        let resp = self
            .auth_headers(self.http.get(&url))
            .send()
            .await
            .map_err(|e| Error::Backend(format!("github pr_list send: {e}")))?;
        let status = resp.status();
        let body = resp
            .text()
            .await
            .map_err(|e| Error::Backend(format!("github pr_list body: {e}")))?;
        if !status.is_success() {
            return Err(Error::Backend(format!(
                "github pr_list http {status}: {body}"
            )));
        }
        let raw: Vec<serde_json::Value> = serde_json::from_str(&body)
            .map_err(|e| Error::Backend(format!("github pr_list parse: {e}")))?;
        Ok(raw.into_iter().map(parse_pull).collect())
    }
}

fn parse_issue(v: serde_json::Value) -> IssueSummary {
    IssueSummary {
        number: v.get("number").and_then(|x| x.as_u64()).unwrap_or(0),
        title: v
            .get("title")
            .and_then(|x| x.as_str())
            .unwrap_or("")
            .to_string(),
        state: v
            .get("state")
            .and_then(|x| x.as_str())
            .unwrap_or("")
            .to_string(),
        author: v
            .get("user")
            .and_then(|u| u.get("login"))
            .and_then(|x| x.as_str())
            .map(String::from),
        html_url: v
            .get("html_url")
            .and_then(|x| x.as_str())
            .unwrap_or("")
            .to_string(),
        labels: v
            .get("labels")
            .and_then(|x| x.as_array())
            .map(|arr| {
                arr.iter()
                    .filter_map(|l| l.get("name").and_then(|n| n.as_str()).map(String::from))
                    .collect()
            })
            .unwrap_or_default(),
        comments: v.get("comments").and_then(|x| x.as_u64()).unwrap_or(0),
        created_at: v
            .get("created_at")
            .and_then(|x| x.as_str())
            .unwrap_or("")
            .to_string(),
        updated_at: v
            .get("updated_at")
            .and_then(|x| x.as_str())
            .unwrap_or("")
            .to_string(),
    }
}

fn parse_pull(v: serde_json::Value) -> PullSummary {
    PullSummary {
        number: v.get("number").and_then(|x| x.as_u64()).unwrap_or(0),
        title: v
            .get("title")
            .and_then(|x| x.as_str())
            .unwrap_or("")
            .to_string(),
        state: v
            .get("state")
            .and_then(|x| x.as_str())
            .unwrap_or("")
            .to_string(),
        draft: v.get("draft").and_then(|x| x.as_bool()).unwrap_or(false),
        author: v
            .get("user")
            .and_then(|u| u.get("login"))
            .and_then(|x| x.as_str())
            .map(String::from),
        html_url: v
            .get("html_url")
            .and_then(|x| x.as_str())
            .unwrap_or("")
            .to_string(),
        head: v
            .get("head")
            .and_then(|h| h.get("ref"))
            .and_then(|x| x.as_str())
            .unwrap_or("")
            .to_string(),
        base: v
            .get("base")
            .and_then(|h| h.get("ref"))
            .and_then(|x| x.as_str())
            .unwrap_or("")
            .to_string(),
        created_at: v
            .get("created_at")
            .and_then(|x| x.as_str())
            .unwrap_or("")
            .to_string(),
        updated_at: v
            .get("updated_at")
            .and_then(|x| x.as_str())
            .unwrap_or("")
            .to_string(),
    }
}

fn urlencoding(s: &str) -> String {
    let mut out = String::with_capacity(s.len());
    for b in s.bytes() {
        match b {
            b'A'..=b'Z' | b'a'..=b'z' | b'0'..=b'9' | b'-' | b'_' | b'.' | b'~' => {
                out.push(b as char)
            }
            b',' => out.push(','), // GitHub accepts comma-separated label list raw
            _ => out.push_str(&format!("%{b:02X}")),
        }
    }
    out
}
