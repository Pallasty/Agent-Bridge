//! Tailscale REST API client for the agent-bridge MCP layer.
//!
//! Exposes ACL management (`/api/v2/tailnet/-/acl`) so the agent can edit
//! Access Control Lists without driving a browser. Uses OAuth 2 client-
//! credentials flow: tokens cached in-memory until expiry.
//!
//! Credentials come from env (`TAILSCALE_OAUTH_CLIENT_ID` +
//! `TAILSCALE_OAUTH_CLIENT_SECRET`). The OAuth client must be created in
//! the Tailscale admin console with the `acl` scope. See
//! https://tailscale.com/api for the spec.

use ab_core::{Error, Result};
use serde::Deserialize;
use std::time::{Duration, Instant};
use tokio::sync::Mutex;

const API_BASE: &str = "https://api.tailscale.com/api/v2";
const OAUTH_URL: &str = "https://api.tailscale.com/api/v2/oauth/token";

#[derive(Debug)]
pub struct TailscaleClient {
    client_id: String,
    client_secret: String,
    http: reqwest::Client,
    cache: Mutex<Option<TokenCache>>,
}

#[derive(Debug, Clone)]
struct TokenCache {
    access_token: String,
    expires_at: Instant,
}

#[derive(Debug, Deserialize)]
struct TokenResponse {
    access_token: String,
    expires_in: u64,
}

pub struct AclGetResult {
    /// Raw HuJSON body of the current tailnet ACL.
    pub body: String,
    /// `etag` header — feed back to `acl_set` for optimistic concurrency.
    pub etag: Option<String>,
}

impl TailscaleClient {
    pub fn from_env() -> Result<Self> {
        let client_id = std::env::var("TAILSCALE_OAUTH_CLIENT_ID").map_err(|_| {
            Error::Backend(
                "TAILSCALE_OAUTH_CLIENT_ID env not set; configure the OAuth client in \
                 .claude.json mcpServers.agent-bridge.env"
                    .into(),
            )
        })?;
        let client_secret = std::env::var("TAILSCALE_OAUTH_CLIENT_SECRET").map_err(|_| {
            Error::Backend(
                "TAILSCALE_OAUTH_CLIENT_SECRET env not set; configure the OAuth client in \
                 .claude.json mcpServers.agent-bridge.env"
                    .into(),
            )
        })?;
        let http = reqwest::Client::builder()
            .timeout(Duration::from_secs(15))
            .build()
            .map_err(|e| Error::Backend(format!("tailscale http client init: {e}")))?;
        Ok(Self {
            client_id,
            client_secret,
            http,
            cache: Mutex::new(None),
        })
    }

    async fn token(&self) -> Result<String> {
        let mut cache = self.cache.lock().await;
        if let Some(c) = cache.as_ref() {
            if Instant::now() + Duration::from_secs(30) < c.expires_at {
                return Ok(c.access_token.clone());
            }
        }
        let resp = self
            .http
            .post(OAUTH_URL)
            .form(&[
                ("client_id", self.client_id.as_str()),
                ("client_secret", self.client_secret.as_str()),
                ("grant_type", "client_credentials"),
            ])
            .send()
            .await
            .map_err(|e| Error::Backend(format!("tailscale oauth send: {e}")))?;
        let status = resp.status();
        if !status.is_success() {
            let body = resp.text().await.unwrap_or_default();
            return Err(Error::Backend(format!(
                "tailscale oauth http {status}: {body}"
            )));
        }
        let tr: TokenResponse = resp
            .json()
            .await
            .map_err(|e| Error::Backend(format!("tailscale oauth json: {e}")))?;
        let expires_at = Instant::now() + Duration::from_secs(tr.expires_in);
        let token = tr.access_token.clone();
        *cache = Some(TokenCache {
            access_token: tr.access_token,
            expires_at,
        });
        Ok(token)
    }

    /// GET `/tailnet/-/acl` — returns raw HuJSON + the `etag` header.
    pub async fn acl_get(&self) -> Result<AclGetResult> {
        let tok = self.token().await?;
        let resp = self
            .http
            .get(format!("{API_BASE}/tailnet/-/acl"))
            .header("Authorization", format!("Bearer {tok}"))
            .header("Accept", "application/hujson")
            .send()
            .await
            .map_err(|e| Error::Backend(format!("tailscale acl_get send: {e}")))?;
        let etag = resp
            .headers()
            .get("etag")
            .and_then(|v| v.to_str().ok().map(String::from));
        let status = resp.status();
        let body = resp
            .text()
            .await
            .map_err(|e| Error::Backend(format!("tailscale acl_get body: {e}")))?;
        if !status.is_success() {
            return Err(Error::Backend(format!(
                "tailscale acl_get http {status}: {body}"
            )));
        }
        Ok(AclGetResult { body, etag })
    }

    /// POST `/tailnet/-/acl/validate` — dry-run an ACL change.
    /// Returns the validation response body (often `{}` on success).
    pub async fn acl_validate(&self, body: &str) -> Result<String> {
        let tok = self.token().await?;
        let resp = self
            .http
            .post(format!("{API_BASE}/tailnet/-/acl/validate"))
            .header("Authorization", format!("Bearer {tok}"))
            .header("Content-Type", "application/hujson")
            .body(body.to_string())
            .send()
            .await
            .map_err(|e| Error::Backend(format!("tailscale acl_validate send: {e}")))?;
        let status = resp.status();
        let resp_body = resp.text().await.unwrap_or_default();
        if !status.is_success() {
            return Err(Error::Backend(format!(
                "tailscale acl_validate http {status}: {resp_body}"
            )));
        }
        Ok(resp_body)
    }

    /// POST `/tailnet/-/acl` — replace the ACL. If `etag` is supplied, the
    /// API returns 412 when the ACL changed since `acl_get` (optimistic
    /// concurrency).
    pub async fn acl_set(&self, body: &str, etag: Option<&str>) -> Result<String> {
        let tok = self.token().await?;
        let mut req = self
            .http
            .post(format!("{API_BASE}/tailnet/-/acl"))
            .header("Authorization", format!("Bearer {tok}"))
            .header("Content-Type", "application/hujson")
            .body(body.to_string());
        if let Some(e) = etag {
            req = req.header("If-Match", e);
        }
        let resp = req
            .send()
            .await
            .map_err(|e| Error::Backend(format!("tailscale acl_set send: {e}")))?;
        let status = resp.status();
        let resp_body = resp.text().await.unwrap_or_default();
        if !status.is_success() {
            return Err(Error::Backend(format!(
                "tailscale acl_set http {status}: {resp_body}"
            )));
        }
        Ok(resp_body)
    }
}
