//! Notion REST API client for the agent-bridge MCP layer.
//!
//! API-first SaaS pattern, 4th instance. Auth is `Bearer <integration token>`
//! with a required `Notion-Version` header. Tokens are integration-scoped:
//! the bot only sees pages explicitly shared with it via the Notion UI's
//! "Add connections" action — failed search results with empty `results`
//! and HTTP 200 usually means the bot wasn't granted access yet.

use ab_core::{Error, Result};
use serde::{Deserialize, Serialize};
use std::time::Duration;

const API_BASE: &str = "https://api.notion.com/v1";
const NOTION_VERSION: &str = "2022-06-28";
const USER_AGENT: &str = "agent-bridge-mcp";

#[derive(Debug)]
pub struct NotionClient {
    token: String,
    http: reqwest::Client,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SearchHit {
    pub object: String, // "page" | "database"
    pub id: String,
    pub url: String,
    pub title: Option<String>,
    pub created_time: String,
    pub last_edited_time: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct PageMeta {
    pub id: String,
    pub url: String,
    pub title: Option<String>,
    pub parent_kind: Option<String>, // "page_id" | "database_id" | "workspace"
    pub parent_id: Option<String>,
    pub archived: bool,
    pub created_time: String,
    pub last_edited_time: String,
}

impl NotionClient {
    pub fn from_env() -> Result<Self> {
        let token = std::env::var("NOTION_TOKEN").map_err(|_| {
            Error::Backend(
                "NOTION_TOKEN env not set; place an integration token (`ntn_…` or \
                 legacy `secret_…`) in /Media/Ubuntu/Documents/ClaudeCode.txt under \
                 '# Notion API' and reconnect MCP. Also: the bot must be \
                 explicitly added to each page/database via the Notion UI before \
                 it can see them — check 'Add connections' in the page's ⋯ menu."
                    .into(),
            )
        })?;
        let http = reqwest::Client::builder()
            .timeout(Duration::from_secs(20))
            .user_agent(USER_AGENT)
            .build()
            .map_err(|e| Error::Backend(format!("notion http client init: {e}")))?;
        Ok(Self { token, http })
    }

    fn headers(&self, rb: reqwest::RequestBuilder) -> reqwest::RequestBuilder {
        rb.header("Authorization", format!("Bearer {}", self.token))
            .header("Notion-Version", NOTION_VERSION)
            .header("Content-Type", "application/json")
    }

    pub async fn search(
        &self,
        query: &str,
        filter_object: Option<&str>, // "page" | "database"
        page_size: u32,
    ) -> Result<Vec<SearchHit>> {
        let url = format!("{API_BASE}/search");
        let mut payload = serde_json::json!({
            "query": query,
            "page_size": page_size,
        });
        if let Some(f) = filter_object.filter(|s| !s.is_empty()) {
            payload["filter"] = serde_json::json!({ "value": f, "property": "object" });
        }
        let resp = self
            .headers(self.http.post(&url))
            .json(&payload)
            .send()
            .await
            .map_err(|e| Error::Backend(format!("notion search send: {e}")))?;
        let status = resp.status();
        let body = resp
            .text()
            .await
            .map_err(|e| Error::Backend(format!("notion search body: {e}")))?;
        if !status.is_success() {
            return Err(Error::Backend(format!(
                "notion search http {status}: {body}"
            )));
        }
        let v: serde_json::Value = serde_json::from_str(&body)
            .map_err(|e| Error::Backend(format!("notion search parse: {e}")))?;
        Ok(v.get("results")
            .and_then(|x| x.as_array())
            .map(|arr| arr.iter().map(parse_search_hit).collect())
            .unwrap_or_default())
    }

    pub async fn page_get(&self, page_id: &str) -> Result<PageMeta> {
        let url = format!("{API_BASE}/pages/{page_id}");
        let resp = self
            .headers(self.http.get(&url))
            .send()
            .await
            .map_err(|e| Error::Backend(format!("notion page_get send: {e}")))?;
        let status = resp.status();
        let body = resp
            .text()
            .await
            .map_err(|e| Error::Backend(format!("notion page_get body: {e}")))?;
        if !status.is_success() {
            return Err(Error::Backend(format!(
                "notion page_get http {status}: {body}"
            )));
        }
        let v: serde_json::Value = serde_json::from_str(&body)
            .map_err(|e| Error::Backend(format!("notion page_get parse: {e}")))?;
        Ok(parse_page_meta(&v))
    }

    /// Create a child page under `parent_page_id`. `content` is treated as a
    /// single paragraph block of plain text — for richer block content,
    /// follow up with `block_append`. Empty content is allowed.
    pub async fn page_create(
        &self,
        parent_page_id: &str,
        title: &str,
        content: &str,
    ) -> Result<PageMeta> {
        let url = format!("{API_BASE}/pages");
        let mut payload = serde_json::json!({
            "parent": { "page_id": parent_page_id },
            "properties": {
                "title": [
                    { "type": "text", "text": { "content": title } }
                ]
            }
        });
        if !content.is_empty() {
            payload["children"] = serde_json::json!([
                {
                    "object": "block",
                    "type": "paragraph",
                    "paragraph": {
                        "rich_text": [
                            { "type": "text", "text": { "content": content } }
                        ]
                    }
                }
            ]);
        }
        let resp = self
            .headers(self.http.post(&url))
            .json(&payload)
            .send()
            .await
            .map_err(|e| Error::Backend(format!("notion page_create send: {e}")))?;
        let status = resp.status();
        let resp_body = resp
            .text()
            .await
            .map_err(|e| Error::Backend(format!("notion page_create body: {e}")))?;
        if !status.is_success() {
            return Err(Error::Backend(format!(
                "notion page_create http {status}: {resp_body}"
            )));
        }
        let v: serde_json::Value = serde_json::from_str(&resp_body)
            .map_err(|e| Error::Backend(format!("notion page_create parse: {e}")))?;
        Ok(parse_page_meta(&v))
    }
}

fn parse_search_hit(v: &serde_json::Value) -> SearchHit {
    SearchHit {
        object: v
            .get("object")
            .and_then(|x| x.as_str())
            .unwrap_or("")
            .to_string(),
        id: v
            .get("id")
            .and_then(|x| x.as_str())
            .unwrap_or("")
            .to_string(),
        url: v
            .get("url")
            .and_then(|x| x.as_str())
            .unwrap_or("")
            .to_string(),
        title: extract_title(v),
        created_time: v
            .get("created_time")
            .and_then(|x| x.as_str())
            .unwrap_or("")
            .to_string(),
        last_edited_time: v
            .get("last_edited_time")
            .and_then(|x| x.as_str())
            .unwrap_or("")
            .to_string(),
    }
}

fn parse_page_meta(v: &serde_json::Value) -> PageMeta {
    let parent = v.get("parent");
    let (parent_kind, parent_id) = match parent {
        Some(p) => {
            let kind = p.get("type").and_then(|x| x.as_str()).map(String::from);
            let id = kind
                .as_deref()
                .and_then(|k| p.get(k))
                .and_then(|x| x.as_str())
                .map(String::from);
            (kind, id)
        }
        None => (None, None),
    };
    PageMeta {
        id: v
            .get("id")
            .and_then(|x| x.as_str())
            .unwrap_or("")
            .to_string(),
        url: v
            .get("url")
            .and_then(|x| x.as_str())
            .unwrap_or("")
            .to_string(),
        title: extract_title(v),
        parent_kind,
        parent_id,
        archived: v.get("archived").and_then(|x| x.as_bool()).unwrap_or(false),
        created_time: v
            .get("created_time")
            .and_then(|x| x.as_str())
            .unwrap_or("")
            .to_string(),
        last_edited_time: v
            .get("last_edited_time")
            .and_then(|x| x.as_str())
            .unwrap_or("")
            .to_string(),
    }
}

/// Notion stashes a page's title in `properties.<title-prop>.title[].plain_text`,
/// but the title property's *name* varies per database schema. For pages in
/// the workspace root it's "title"; for database items it might be "Name" or
/// anything the schema uses. We probe the common cases and fall back to
/// scanning all properties for the first one with `type == "title"`.
fn extract_title(v: &serde_json::Value) -> Option<String> {
    let props = v.get("properties")?;
    let direct = props
        .get("title")
        .or_else(|| props.get("Name"))
        .or_else(|| props.get("Title"));
    let prop = direct.or_else(|| {
        props.as_object().and_then(|m| {
            m.values().find(|p| {
                p.get("type")
                    .and_then(|t| t.as_str())
                    .map(|t| t == "title")
                    .unwrap_or(false)
            })
        })
    })?;
    let arr = prop.get("title").and_then(|x| x.as_array())?;
    let s = arr
        .iter()
        .filter_map(|seg| seg.get("plain_text").and_then(|x| x.as_str()))
        .collect::<Vec<_>>()
        .join("");
    if s.is_empty() {
        None
    } else {
        Some(s)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn parse_page_with_workspace_parent() {
        let v: serde_json::Value = serde_json::from_str(
            r#"{
            "id":"abc-123",
            "url":"https://notion.so/abc-123",
            "archived":false,
            "created_time":"2026-05-08T00:00:00Z",
            "last_edited_time":"2026-05-08T00:00:00Z",
            "parent":{"type":"workspace","workspace":true},
            "properties":{
                "title":{"type":"title","title":[{"plain_text":"Hello "},{"plain_text":"World"}]}
            }
        }"#,
        )
        .unwrap();
        let m = parse_page_meta(&v);
        assert_eq!(m.id, "abc-123");
        assert_eq!(m.title.as_deref(), Some("Hello World"));
        assert_eq!(m.parent_kind.as_deref(), Some("workspace"));
        assert!(m.parent_id.is_none()); // workspace has no id
    }

    #[test]
    fn parse_database_item_with_named_title_prop() {
        let v: serde_json::Value = serde_json::from_str(
            r#"{
            "id":"xyz",
            "url":"https://notion.so/xyz",
            "archived":false,
            "created_time":"x","last_edited_time":"x",
            "parent":{"type":"database_id","database_id":"db-456"},
            "properties":{
                "Status":{"type":"select"},
                "Name":{"type":"title","title":[{"plain_text":"Task A"}]}
            }
        }"#,
        )
        .unwrap();
        let m = parse_page_meta(&v);
        assert_eq!(m.title.as_deref(), Some("Task A"));
        assert_eq!(m.parent_kind.as_deref(), Some("database_id"));
        assert_eq!(m.parent_id.as_deref(), Some("db-456"));
    }
}
