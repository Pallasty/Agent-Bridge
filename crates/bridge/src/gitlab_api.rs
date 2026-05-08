//! GitLab REST API v4 client for the agent-bridge MCP layer.
//!
//! Mirrors `github_api`: drive GitLab admin/CRUD via fine-grained PAT
//! (`glpat-…`) without browser automation. Project may be passed as either
//! a numeric ID (`81993234`) or a path with namespace (`pallasting/agent-bridge`)
//! — the client URL-encodes the path form transparently.

use ab_core::{Error, Result};
use serde::{Deserialize, Serialize};
use std::time::Duration;

const API_BASE: &str = "https://gitlab.com/api/v4";
const USER_AGENT: &str = "agent-bridge-mcp";

#[derive(Debug)]
pub struct GitLabClient {
    token: String,
    http: reqwest::Client,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct GlIssueSummary {
    pub iid: u64,
    pub title: String,
    pub state: String,
    pub author: Option<String>,
    pub web_url: String,
    pub labels: Vec<String>,
    pub user_notes_count: u64,
    pub created_at: String,
    pub updated_at: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct GlMrSummary {
    pub iid: u64,
    pub title: String,
    pub state: String,
    pub draft: bool,
    pub author: Option<String>,
    pub web_url: String,
    pub source_branch: String,
    pub target_branch: String,
    pub created_at: String,
    pub updated_at: String,
}

impl GitLabClient {
    pub fn from_env() -> Result<Self> {
        let token = std::env::var("GITLAB_TOKEN").map_err(|_| {
            Error::Backend(
                "GITLAB_TOKEN env not set; place a fine-grained PAT (`glpat-…`) in \
                 /Media/Ubuntu/Documents/ClaudeCode.txt under '# GitLab PAT token' \
                 and reconnect MCP (the wrapper / creds loader exports it for the child)"
                    .into(),
            )
        })?;
        let http = reqwest::Client::builder()
            .timeout(Duration::from_secs(20))
            .user_agent(USER_AGENT)
            .build()
            .map_err(|e| Error::Backend(format!("gitlab http client init: {e}")))?;
        Ok(Self { token, http })
    }

    fn auth_headers(&self, rb: reqwest::RequestBuilder) -> reqwest::RequestBuilder {
        rb.header("PRIVATE-TOKEN", &self.token)
            .header("Accept", "application/json")
    }

    pub async fn issue_list(
        &self,
        project: &str,
        state: &str,
        per_page: u32,
        labels: Option<&str>,
    ) -> Result<Vec<GlIssueSummary>> {
        let proj = project_segment(project);
        let mut url = format!(
            "{API_BASE}/projects/{proj}/issues?state={state}&per_page={per_page}"
        );
        if let Some(l) = labels.filter(|s| !s.is_empty()) {
            url.push_str(&format!("&labels={}", urlencoding(l)));
        }
        let resp = self
            .auth_headers(self.http.get(&url))
            .send()
            .await
            .map_err(|e| Error::Backend(format!("gitlab issue_list send: {e}")))?;
        let status = resp.status();
        let body = resp
            .text()
            .await
            .map_err(|e| Error::Backend(format!("gitlab issue_list body: {e}")))?;
        if !status.is_success() {
            return Err(Error::Backend(format!(
                "gitlab issue_list http {status}: {body}"
            )));
        }
        let raw: Vec<serde_json::Value> = serde_json::from_str(&body)
            .map_err(|e| Error::Backend(format!("gitlab issue_list parse: {e}")))?;
        Ok(raw.into_iter().map(parse_issue).collect())
    }

    pub async fn issue_create(
        &self,
        project: &str,
        title: &str,
        description: &str,
        labels: Option<Vec<String>>,
    ) -> Result<GlIssueSummary> {
        let proj = project_segment(project);
        let url = format!("{API_BASE}/projects/{proj}/issues");
        let mut payload = serde_json::json!({ "title": title, "description": description });
        if let Some(ls) = labels.filter(|v| !v.is_empty()) {
            // GitLab takes a comma-separated string for labels in create
            payload["labels"] = serde_json::json!(ls.join(","));
        }
        let resp = self
            .auth_headers(self.http.post(&url))
            .json(&payload)
            .send()
            .await
            .map_err(|e| Error::Backend(format!("gitlab issue_create send: {e}")))?;
        let status = resp.status();
        let resp_body = resp
            .text()
            .await
            .map_err(|e| Error::Backend(format!("gitlab issue_create body: {e}")))?;
        if !status.is_success() {
            return Err(Error::Backend(format!(
                "gitlab issue_create http {status}: {resp_body}"
            )));
        }
        let v: serde_json::Value = serde_json::from_str(&resp_body)
            .map_err(|e| Error::Backend(format!("gitlab issue_create parse: {e}")))?;
        Ok(parse_issue(v))
    }

    pub async fn mr_list(
        &self,
        project: &str,
        state: &str,
        per_page: u32,
    ) -> Result<Vec<GlMrSummary>> {
        let proj = project_segment(project);
        let url = format!(
            "{API_BASE}/projects/{proj}/merge_requests?state={state}&per_page={per_page}"
        );
        let resp = self
            .auth_headers(self.http.get(&url))
            .send()
            .await
            .map_err(|e| Error::Backend(format!("gitlab mr_list send: {e}")))?;
        let status = resp.status();
        let body = resp
            .text()
            .await
            .map_err(|e| Error::Backend(format!("gitlab mr_list body: {e}")))?;
        if !status.is_success() {
            return Err(Error::Backend(format!(
                "gitlab mr_list http {status}: {body}"
            )));
        }
        let raw: Vec<serde_json::Value> = serde_json::from_str(&body)
            .map_err(|e| Error::Backend(format!("gitlab mr_list parse: {e}")))?;
        Ok(raw.into_iter().map(parse_mr).collect())
    }
}

/// If `project` is purely numeric, leave it alone (it's a project ID).
/// Otherwise treat it as `namespace/path` and URL-encode the slash.
fn project_segment(project: &str) -> String {
    if !project.is_empty() && project.chars().all(|c| c.is_ascii_digit()) {
        project.to_string()
    } else {
        urlencoding(project)
    }
}

fn parse_issue(v: serde_json::Value) -> GlIssueSummary {
    GlIssueSummary {
        iid: v.get("iid").and_then(|x| x.as_u64()).unwrap_or(0),
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
            .get("author")
            .and_then(|u| u.get("username"))
            .and_then(|x| x.as_str())
            .map(String::from),
        web_url: v
            .get("web_url")
            .and_then(|x| x.as_str())
            .unwrap_or("")
            .to_string(),
        labels: v
            .get("labels")
            .and_then(|x| x.as_array())
            .map(|arr| {
                arr.iter()
                    .filter_map(|l| l.as_str().map(String::from))
                    .collect()
            })
            .unwrap_or_default(),
        user_notes_count: v
            .get("user_notes_count")
            .and_then(|x| x.as_u64())
            .unwrap_or(0),
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

fn parse_mr(v: serde_json::Value) -> GlMrSummary {
    GlMrSummary {
        iid: v.get("iid").and_then(|x| x.as_u64()).unwrap_or(0),
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
        draft: v
            .get("draft")
            .and_then(|x| x.as_bool())
            .or_else(|| v.get("work_in_progress").and_then(|x| x.as_bool()))
            .unwrap_or(false),
        author: v
            .get("author")
            .and_then(|u| u.get("username"))
            .and_then(|x| x.as_str())
            .map(String::from),
        web_url: v
            .get("web_url")
            .and_then(|x| x.as_str())
            .unwrap_or("")
            .to_string(),
        source_branch: v
            .get("source_branch")
            .and_then(|x| x.as_str())
            .unwrap_or("")
            .to_string(),
        target_branch: v
            .get("target_branch")
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
            b',' => out.push(','),
            _ => out.push_str(&format!("%{b:02X}")),
        }
    }
    out
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn project_segment_numeric_passthrough() {
        assert_eq!(project_segment("81993234"), "81993234");
    }

    #[test]
    fn project_segment_path_encoded() {
        assert_eq!(
            project_segment("pallasting/agent-bridge"),
            "pallasting%2Fagent-bridge"
        );
    }
}
