//! Cloudflare REST API client for the agent-bridge MCP layer.
//!
//! API-first SaaS pattern, 6th instance. Auth is `Authorization: Bearer
//! <token>`. Two env vars feed it:
//!   * `CLOUDFLARE_API_TOKEN` — the API token (Bearer)
//!   * `CLOUDFLARE_ACCOUNT_ID` — needed for /accounts/<id>/* endpoints
//!
//! The user's "Cloudflare Workers API" token has been observed to grant:
//!   ✅ /zones (list)            ✅ /accounts/<id>/workers/scripts
//!   ✅ /accounts/<id>/r2/buckets ✅ /accounts/<id>/storage/kv/namespaces
//!   ✅ /accounts/<id>/pages/projects
//!   ❌ /zones/<zid>/dns_records  ❌ /accounts/<id>/d1/database
//!
//! For each tool we surface a clear "permission denied" path-back when the
//! token's scope doesn't include the endpoint.

use ab_core::{Error, Result};
use serde::{Deserialize, Serialize};
use std::time::Duration;

const API_BASE: &str = "https://api.cloudflare.com/client/v4";
const USER_AGENT: &str = "agent-bridge-mcp";

#[derive(Debug)]
pub struct CloudflareClient {
    token: String,
    account_id: Option<String>,
    http: reqwest::Client,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ZoneSummary {
    pub id: String,
    pub name: String,
    pub status: String,
    pub paused: bool,
    pub r#type: String,
    pub name_servers: Vec<String>,
    pub created_on: String,
    pub modified_on: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct WorkerScript {
    pub id: String,
    pub created_on: String,
    pub modified_on: String,
    pub etag: Option<String>,
    pub handlers: Vec<String>,
    pub usage_model: Option<String>,
    pub routes: Vec<String>, // route patterns only
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct R2Bucket {
    pub name: String,
    pub creation_date: String,
    pub location: Option<String>,
    pub storage_class: Option<String>,
}

impl CloudflareClient {
    pub fn from_env() -> Result<Self> {
        let token = std::env::var("CLOUDFLARE_API_TOKEN").map_err(|_| {
            Error::Backend(
                "CLOUDFLARE_API_TOKEN env not set; place the token (the bare \
                 line under `## Cloudflare Workers API`) in \
                 /Media/Ubuntu/Documents/ClaudeCode.txt and reconnect MCP."
                    .into(),
            )
        })?;
        let account_id = std::env::var("CLOUDFLARE_ACCOUNT_ID").ok();
        let http = reqwest::Client::builder()
            .timeout(Duration::from_secs(20))
            .user_agent(USER_AGENT)
            .build()
            .map_err(|e| Error::Backend(format!("cloudflare http client init: {e}")))?;
        Ok(Self {
            token,
            account_id,
            http,
        })
    }

    fn account_id(&self) -> Result<&str> {
        self.account_id.as_deref().ok_or_else(|| {
            Error::Backend(
                "CLOUDFLARE_ACCOUNT_ID env not set; the line `ID：<32-hex>` \
                 under `# Cloudflare endpoint` must be readable in the creds \
                 file. Reconnect MCP after editing."
                    .into(),
            )
        })
    }

    fn auth_headers(&self, rb: reqwest::RequestBuilder) -> reqwest::RequestBuilder {
        rb.header("Authorization", format!("Bearer {}", self.token))
            .header("Accept", "application/json")
    }

    async fn get_json(&self, url: &str, ctx: &str) -> Result<serde_json::Value> {
        let resp = self
            .auth_headers(self.http.get(url))
            .send()
            .await
            .map_err(|e| Error::Backend(format!("cloudflare {ctx} send: {e}")))?;
        let status = resp.status();
        let body = resp
            .text()
            .await
            .map_err(|e| Error::Backend(format!("cloudflare {ctx} body: {e}")))?;
        if !status.is_success() {
            return Err(Error::Backend(format!(
                "cloudflare {ctx} http {status}: {body}"
            )));
        }
        let v: serde_json::Value = serde_json::from_str(&body)
            .map_err(|e| Error::Backend(format!("cloudflare {ctx} parse: {e}")))?;
        // CF wraps everything in {success, errors, result}. Treat success=false
        // as an error even when HTTP status is 2xx.
        if v.get("success").and_then(|b| b.as_bool()) == Some(false) {
            let msg = v
                .get("errors")
                .and_then(|e| e.as_array())
                .and_then(|arr| arr.first())
                .and_then(|e| e.get("message"))
                .and_then(|m| m.as_str())
                .unwrap_or("(no error message)");
            return Err(Error::Backend(format!("cloudflare {ctx}: {msg}")));
        }
        Ok(v)
    }

    pub async fn zone_list(&self, per_page: u32) -> Result<Vec<ZoneSummary>> {
        let url = format!(
            "{API_BASE}/zones?per_page={}",
            per_page.clamp(1, 50)
        );
        let v = self.get_json(&url, "zone_list").await?;
        Ok(v.get("result")
            .and_then(|x| x.as_array())
            .map(|arr| arr.iter().map(parse_zone).collect())
            .unwrap_or_default())
    }

    pub async fn worker_list(&self, per_page: u32) -> Result<Vec<WorkerScript>> {
        let acct = self.account_id()?;
        let url = format!(
            "{API_BASE}/accounts/{acct}/workers/scripts?per_page={}",
            per_page.clamp(1, 50)
        );
        let v = self.get_json(&url, "worker_list").await?;
        Ok(v.get("result")
            .and_then(|x| x.as_array())
            .map(|arr| arr.iter().map(parse_worker).collect())
            .unwrap_or_default())
    }

    pub async fn r2_bucket_list(&self) -> Result<Vec<R2Bucket>> {
        let acct = self.account_id()?;
        let url = format!("{API_BASE}/accounts/{acct}/r2/buckets");
        let v = self.get_json(&url, "r2_bucket_list").await?;
        // R2 is special: result is { buckets: [...] } not result: [...] directly.
        let arr = v
            .get("result")
            .and_then(|r| r.get("buckets"))
            .and_then(|x| x.as_array());
        Ok(arr
            .map(|a| a.iter().map(parse_r2_bucket).collect())
            .unwrap_or_default())
    }
}

fn parse_zone(v: &serde_json::Value) -> ZoneSummary {
    ZoneSummary {
        id: v.get("id").and_then(|x| x.as_str()).unwrap_or("").to_string(),
        name: v
            .get("name")
            .and_then(|x| x.as_str())
            .unwrap_or("")
            .to_string(),
        status: v
            .get("status")
            .and_then(|x| x.as_str())
            .unwrap_or("")
            .to_string(),
        paused: v.get("paused").and_then(|x| x.as_bool()).unwrap_or(false),
        r#type: v
            .get("type")
            .and_then(|x| x.as_str())
            .unwrap_or("")
            .to_string(),
        name_servers: v
            .get("name_servers")
            .and_then(|x| x.as_array())
            .map(|arr| {
                arr.iter()
                    .filter_map(|n| n.as_str().map(String::from))
                    .collect()
            })
            .unwrap_or_default(),
        created_on: v
            .get("created_on")
            .and_then(|x| x.as_str())
            .unwrap_or("")
            .to_string(),
        modified_on: v
            .get("modified_on")
            .and_then(|x| x.as_str())
            .unwrap_or("")
            .to_string(),
    }
}

fn parse_worker(v: &serde_json::Value) -> WorkerScript {
    let routes = v
        .get("routes")
        .and_then(|x| x.as_array())
        .map(|arr| {
            arr.iter()
                .filter_map(|r| r.get("pattern").and_then(|p| p.as_str()).map(String::from))
                .collect()
        })
        .unwrap_or_default();
    WorkerScript {
        id: v.get("id").and_then(|x| x.as_str()).unwrap_or("").to_string(),
        created_on: v
            .get("created_on")
            .and_then(|x| x.as_str())
            .unwrap_or("")
            .to_string(),
        modified_on: v
            .get("modified_on")
            .and_then(|x| x.as_str())
            .unwrap_or("")
            .to_string(),
        etag: v.get("etag").and_then(|x| x.as_str()).map(String::from),
        handlers: v
            .get("handlers")
            .and_then(|x| x.as_array())
            .map(|arr| {
                arr.iter()
                    .filter_map(|h| h.as_str().map(String::from))
                    .collect()
            })
            .unwrap_or_default(),
        usage_model: v
            .get("usage_model")
            .and_then(|x| x.as_str())
            .map(String::from),
        routes,
    }
}

fn parse_r2_bucket(v: &serde_json::Value) -> R2Bucket {
    R2Bucket {
        name: v
            .get("name")
            .and_then(|x| x.as_str())
            .unwrap_or("")
            .to_string(),
        creation_date: v
            .get("creation_date")
            .and_then(|x| x.as_str())
            .unwrap_or("")
            .to_string(),
        location: v
            .get("location")
            .and_then(|x| x.as_str())
            .map(String::from),
        storage_class: v
            .get("storage_class")
            .and_then(|x| x.as_str())
            .map(String::from),
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn parse_zone_typical() {
        let v: serde_json::Value = serde_json::from_str(r#"{
            "id":"abc","name":"example.com","status":"active","paused":false,"type":"full",
            "name_servers":["ns1.cloudflare.com","ns2.cloudflare.com"],
            "created_on":"2024-01-01T00:00:00Z","modified_on":"2024-06-01T00:00:00Z"
        }"#).unwrap();
        let z = parse_zone(&v);
        assert_eq!(z.id, "abc");
        assert_eq!(z.name, "example.com");
        assert_eq!(z.name_servers.len(), 2);
        assert!(!z.paused);
    }

    #[test]
    fn parse_worker_with_routes() {
        let v: serde_json::Value = serde_json::from_str(r#"{
            "id":"my-worker","created_on":"x","modified_on":"y",
            "etag":"abc","handlers":["fetch"],"usage_model":"standard",
            "routes":[{"pattern":"*.example.com/*","script":"my-worker"},
                      {"pattern":"api.foo/*","script":"my-worker"}]
        }"#).unwrap();
        let w = parse_worker(&v);
        assert_eq!(w.id, "my-worker");
        assert_eq!(w.routes, vec!["*.example.com/*".to_string(), "api.foo/*".to_string()]);
        assert_eq!(w.handlers, vec!["fetch".to_string()]);
    }

    #[test]
    fn parse_r2_bucket_minimal() {
        let v: serde_json::Value = serde_json::from_str(r#"{
            "name":"mybucket","creation_date":"2024-12-01T00:00:00Z"
        }"#).unwrap();
        let b = parse_r2_bucket(&v);
        assert_eq!(b.name, "mybucket");
        assert!(b.location.is_none());
    }
}
