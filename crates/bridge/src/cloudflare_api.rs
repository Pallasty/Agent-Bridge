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
use serde_json::json;
use std::net::IpAddr;
use std::time::Duration;

const API_BASE: &str = "https://api.cloudflare.com/client/v4";
const USER_AGENT: &str = "agent-bridge-mcp";
const KITESURF_RESPONSE_MAX_BYTES: usize = 12 * 1024 * 1024;

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

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct KitesurfSnapshotRequest {
    pub url: String,
    pub viewport_width: u32,
    pub viewport_height: u32,
    pub wait_until: String,
    pub timeout_ms: u32,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct KitesurfSnapshot {
    pub source_url: String,
    pub screenshot_base64: String,
    pub markdown: String,
    pub accessibility_tree: serde_json::Value,
    pub title: Option<String>,
    pub http_status: Option<u16>,
    pub browser_ms_used: Option<u64>,
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
        let url = format!("{API_BASE}/zones?per_page={}", per_page.clamp(1, 50));
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

    /// Capture a stateless, read-only evidence bundle through Cloudflare
    /// Browser Run's Kitesurf beta. Authentication state, cookies, custom
    /// headers and arbitrary script injection are intentionally absent from
    /// this first integration slice.
    pub async fn kitesurf_snapshot(
        &self,
        request: &KitesurfSnapshotRequest,
    ) -> Result<KitesurfSnapshot> {
        let target = validate_kitesurf_target(&request.url)?;
        let acct = self.account_id()?;
        if acct.is_empty()
            || !acct
                .bytes()
                .all(|b| b.is_ascii_alphanumeric() || b == b'_' || b == b'-')
        {
            return Err(Error::Backend(
                "CLOUDFLARE_ACCOUNT_ID contains unsupported characters".into(),
            ));
        }
        let endpoint = format!("{API_BASE}/accounts/{acct}/browser-run/snapshot?browser=kitesurf");
        let payload = json!({
            "url": target.as_str(),
            "formats": ["screenshot", "markdown", "accessibilityTree"],
            "viewport": {
                "width": request.viewport_width.clamp(320, 3840),
                "height": request.viewport_height.clamp(240, 2160)
            },
            "gotoOptions": {
                "waitUntil": normalized_wait_until(&request.wait_until),
                "timeout": request.timeout_ms.clamp(1_000, 45_000)
            }
        });

        let mut response = self
            .auth_headers(self.http.post(endpoint).json(&payload))
            .timeout(Duration::from_secs(60))
            .send()
            .await
            .map_err(|e| Error::Backend(format!("cloudflare kitesurf snapshot send: {e}")))?;
        let status = response.status();
        let browser_ms_used = response
            .headers()
            .get("X-Browser-Ms-Used")
            .and_then(|value| value.to_str().ok())
            .and_then(|value| value.parse::<u64>().ok());
        if response.content_length().unwrap_or(0) > KITESURF_RESPONSE_MAX_BYTES as u64 {
            return Err(Error::Backend(format!(
                "cloudflare kitesurf snapshot response exceeds {} bytes",
                KITESURF_RESPONSE_MAX_BYTES
            )));
        }
        let mut body = Vec::with_capacity(
            response
                .content_length()
                .unwrap_or(0)
                .min(KITESURF_RESPONSE_MAX_BYTES as u64) as usize,
        );
        while let Some(chunk) = response
            .chunk()
            .await
            .map_err(|e| Error::Backend(format!("cloudflare kitesurf snapshot body: {e}")))?
        {
            if body.len().saturating_add(chunk.len()) > KITESURF_RESPONSE_MAX_BYTES {
                return Err(Error::Backend(format!(
                    "cloudflare kitesurf snapshot response exceeds {} bytes",
                    KITESURF_RESPONSE_MAX_BYTES
                )));
            }
            body.extend_from_slice(&chunk);
        }
        let value: serde_json::Value = serde_json::from_slice(&body)
            .map_err(|e| Error::Backend(format!("cloudflare kitesurf snapshot parse: {e}")))?;
        if !status.is_success()
            || value.get("success").and_then(serde_json::Value::as_bool) == Some(false)
        {
            let message = cloudflare_error_message(&value);
            return Err(Error::Backend(format!(
                "cloudflare kitesurf snapshot http {status}: {message}"
            )));
        }
        parse_kitesurf_snapshot(target.as_str(), browser_ms_used, &value)
    }
}

fn normalized_wait_until(value: &str) -> &'static str {
    match value {
        "load" => "load",
        "networkidle0" => "networkidle0",
        "networkidle2" => "networkidle2",
        _ => "domcontentloaded",
    }
}

fn validate_kitesurf_target(raw: &str) -> Result<reqwest::Url> {
    let url = reqwest::Url::parse(raw)
        .map_err(|e| Error::InvalidArgument(format!("invalid Kitesurf target URL: {e}")))?;
    if !matches!(url.scheme(), "http" | "https") {
        return Err(Error::InvalidArgument(
            "Kitesurf target URL must use http or https".into(),
        ));
    }
    if !url.username().is_empty() || url.password().is_some() {
        return Err(Error::InvalidArgument(
            "Kitesurf target URL must not contain credentials".into(),
        ));
    }
    let host = url
        .host_str()
        .ok_or_else(|| Error::InvalidArgument("Kitesurf target URL has no host".into()))?;
    let lowered = host.trim_end_matches('.').to_ascii_lowercase();
    if lowered == "localhost"
        || lowered.ends_with(".localhost")
        || lowered.ends_with(".local")
        || lowered.ends_with(".internal")
    {
        return Err(Error::InvalidArgument(
            "Kitesurf target must be a public web host".into(),
        ));
    }
    let ip_literal = lowered
        .strip_prefix('[')
        .and_then(|value| value.strip_suffix(']'))
        .unwrap_or(&lowered);
    if let Ok(ip) = ip_literal.parse::<IpAddr>() {
        let public = match ip {
            IpAddr::V4(v4) => {
                !(v4.is_private()
                    || v4.is_loopback()
                    || v4.is_link_local()
                    || v4.is_unspecified()
                    || v4.is_multicast()
                    || v4.octets()[0] == 0)
            }
            IpAddr::V6(v6) => {
                !(v6.is_loopback()
                    || v6.is_unspecified()
                    || v6.is_multicast()
                    || v6.is_unique_local()
                    || v6.is_unicast_link_local())
            }
        };
        if !public {
            return Err(Error::InvalidArgument(
                "Kitesurf target must not use a private or local IP address".into(),
            ));
        }
    }
    Ok(url)
}

fn cloudflare_error_message(value: &serde_json::Value) -> &str {
    value
        .get("errors")
        .and_then(serde_json::Value::as_array)
        .and_then(|errors| errors.first())
        .and_then(|error| error.get("message"))
        .and_then(serde_json::Value::as_str)
        .unwrap_or("request failed without an error message")
}

fn parse_kitesurf_snapshot(
    source_url: &str,
    browser_ms_used: Option<u64>,
    value: &serde_json::Value,
) -> Result<KitesurfSnapshot> {
    let result = value
        .get("result")
        .and_then(serde_json::Value::as_object)
        .ok_or_else(|| Error::Backend("cloudflare kitesurf snapshot missing result".into()))?;
    let screenshot_base64 = result
        .get("screenshot")
        .and_then(serde_json::Value::as_str)
        .filter(|value| !value.is_empty())
        .ok_or_else(|| Error::Backend("cloudflare kitesurf snapshot missing screenshot".into()))?
        .to_string();
    let markdown = result
        .get("markdown")
        .and_then(serde_json::Value::as_str)
        .unwrap_or_default()
        .to_string();
    let accessibility_tree = result
        .get("accessibilityTree")
        .cloned()
        .unwrap_or(serde_json::Value::Null);
    let meta = value.get("meta").and_then(serde_json::Value::as_object);
    Ok(KitesurfSnapshot {
        source_url: source_url.to_string(),
        screenshot_base64,
        markdown,
        accessibility_tree,
        title: meta
            .and_then(|meta| meta.get("title"))
            .and_then(serde_json::Value::as_str)
            .map(str::to_string),
        http_status: meta
            .and_then(|meta| meta.get("status"))
            .and_then(serde_json::Value::as_u64)
            .and_then(|status| u16::try_from(status).ok()),
        browser_ms_used,
    })
}

fn parse_zone(v: &serde_json::Value) -> ZoneSummary {
    ZoneSummary {
        id: v
            .get("id")
            .and_then(|x| x.as_str())
            .unwrap_or("")
            .to_string(),
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
        id: v
            .get("id")
            .and_then(|x| x.as_str())
            .unwrap_or("")
            .to_string(),
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
        location: v.get("location").and_then(|x| x.as_str()).map(String::from),
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
        let v: serde_json::Value = serde_json::from_str(
            r#"{
            "id":"abc","name":"example.com","status":"active","paused":false,"type":"full",
            "name_servers":["ns1.cloudflare.com","ns2.cloudflare.com"],
            "created_on":"2024-01-01T00:00:00Z","modified_on":"2024-06-01T00:00:00Z"
        }"#,
        )
        .unwrap();
        let z = parse_zone(&v);
        assert_eq!(z.id, "abc");
        assert_eq!(z.name, "example.com");
        assert_eq!(z.name_servers.len(), 2);
        assert!(!z.paused);
    }

    #[test]
    fn parse_worker_with_routes() {
        let v: serde_json::Value = serde_json::from_str(
            r#"{
            "id":"my-worker","created_on":"x","modified_on":"y",
            "etag":"abc","handlers":["fetch"],"usage_model":"standard",
            "routes":[{"pattern":"*.example.com/*","script":"my-worker"},
                      {"pattern":"api.foo/*","script":"my-worker"}]
        }"#,
        )
        .unwrap();
        let w = parse_worker(&v);
        assert_eq!(w.id, "my-worker");
        assert_eq!(
            w.routes,
            vec!["*.example.com/*".to_string(), "api.foo/*".to_string()]
        );
        assert_eq!(w.handlers, vec!["fetch".to_string()]);
    }

    #[test]
    fn parse_r2_bucket_minimal() {
        let v: serde_json::Value = serde_json::from_str(
            r#"{
            "name":"mybucket","creation_date":"2024-12-01T00:00:00Z"
        }"#,
        )
        .unwrap();
        let b = parse_r2_bucket(&v);
        assert_eq!(b.name, "mybucket");
        assert!(b.location.is_none());
    }

    #[test]
    fn kitesurf_target_accepts_public_http_and_https() {
        assert_eq!(
            validate_kitesurf_target("https://example.com/path")
                .unwrap()
                .as_str(),
            "https://example.com/path"
        );
        assert!(validate_kitesurf_target("http://example.com").is_ok());
    }

    #[test]
    fn kitesurf_target_rejects_credentials_local_hosts_and_non_web_schemes() {
        for target in [
            "file:///etc/passwd",
            "https://user:secret@example.com",
            "http://localhost:8080",
            "http://service.internal",
            "http://127.0.0.1",
            "http://10.0.0.8",
            "http://[::1]",
            "http://[fe80::1]",
        ] {
            assert!(
                validate_kitesurf_target(target).is_err(),
                "target should be rejected: {target}"
            );
        }
    }

    #[test]
    fn kitesurf_snapshot_parser_requires_visual_evidence() {
        let value = json!({
            "success": true,
            "result": {
                "screenshot": "aGVsbG8=",
                "markdown": "# Example",
                "accessibilityTree": { "role": "RootWebArea" }
            },
            "meta": { "status": 200, "title": "Example Domain" }
        });
        let snapshot = parse_kitesurf_snapshot("https://example.com/", Some(321), &value)
            .expect("valid snapshot");
        assert_eq!(snapshot.title.as_deref(), Some("Example Domain"));
        assert_eq!(snapshot.http_status, Some(200));
        assert_eq!(snapshot.browser_ms_used, Some(321));
        assert_eq!(snapshot.markdown, "# Example");

        let missing = json!({ "success": true, "result": { "markdown": "x" } });
        assert!(parse_kitesurf_snapshot("https://example.com/", None, &missing).is_err());
    }

    #[test]
    fn kitesurf_wait_until_fails_to_safe_default() {
        assert_eq!(normalized_wait_until("load"), "load");
        assert_eq!(normalized_wait_until("networkidle0"), "networkidle0");
        assert_eq!(normalized_wait_until("unexpected"), "domcontentloaded");
    }
}
