//! Anthropic API client for the agent-bridge MCP layer.
//!
//! Currently used by Phase 1 P4b (memory evolution) and reserved for P5
//! (sleep replay summary generation). Auth is `x-api-key: <key>` plus the
//! `anthropic-version` header. Token is read from env (`ANTHROPIC_API_KEY`)
//! to avoid baking secrets into binaries.
//!
//! Endpoint: POST https://api.anthropic.com/v1/messages
//!
//! We default to `claude-haiku-4-5-20251001` for memory evolution prompts:
//! cheap, fast (~1 s/round), good enough for tag/relation rewriting where
//! creativity matters less than consistency.

use ab_core::{Error, Result};
use serde::{Deserialize, Serialize};
use std::time::Duration;

const DEFAULT_API_BASE: &str = "https://api.anthropic.com/v1";
const ANTHROPIC_VERSION: &str = "2023-06-01";
const USER_AGENT: &str = "agent-bridge-mcp";

/// Default model for memory evolution / replay summaries. Override per call
/// via [`AnthropicClient::messages_create`] if you need a smarter model.
pub const DEFAULT_MODEL: &str = "claude-haiku-4-5-20251001";

/// Auth scheme — either Anthropic's official `x-api-key` header (used with
/// keys starting with `sk-ant-…`) or `Authorization: Bearer …` (used by
/// proxies like anyrouter that follow the OpenAI / OAuth-style pattern).
#[derive(Debug, Clone)]
enum AuthMode {
    XApiKey,
    Bearer,
}

#[derive(Debug)]
pub struct AnthropicClient {
    api_key: String,
    base_url: String,
    auth_mode: AuthMode,
    http: reqwest::Client,
}

#[derive(Debug, Clone, Serialize)]
pub struct Message {
    pub role: String,
    pub content: String,
}

/// Outcome of one `/v1/messages` round-trip. We surface the assistant's text
/// (concatenation of all `content[].text` parts) plus token usage so callers
/// can budget LLM cost.
#[derive(Debug, Clone, Deserialize)]
pub struct MessagesResponse {
    pub text: String,
    pub stop_reason: Option<String>,
    pub input_tokens: u32,
    pub output_tokens: u32,
}

impl AnthropicClient {
    /// Build a client from env. Honors three vars (in order of precedence):
    ///   * `ANTHROPIC_API_KEY` — official Anthropic auth (`x-api-key` header)
    ///   * `ANTHROPIC_AUTH_TOKEN` — proxy/OAuth-style Bearer auth (used by
    ///     anyrouter, openrouter, and Claude Code itself when paired with
    ///     a relay endpoint). Only consulted if `ANTHROPIC_API_KEY` is unset.
    ///   * `ANTHROPIC_BASE_URL` — overrides the default endpoint. Strip a
    ///     trailing `/v1` if present (we re-append it ourselves) so that
    ///     either `https://anyrouter.top` or `https://anyrouter.top/v1`
    ///     work without surprises.
    pub fn from_env() -> Result<Self> {
        let (api_key, auth_mode) = if let Ok(k) = std::env::var("ANTHROPIC_API_KEY") {
            if k.is_empty() {
                return Err(Error::Backend("ANTHROPIC_API_KEY is set but empty".into()));
            }
            (k, AuthMode::XApiKey)
        } else if let Ok(t) = std::env::var("ANTHROPIC_AUTH_TOKEN") {
            if t.is_empty() {
                return Err(Error::Backend(
                    "ANTHROPIC_AUTH_TOKEN is set but empty".into(),
                ));
            }
            (t, AuthMode::Bearer)
        } else {
            return Err(Error::Backend(
                "neither ANTHROPIC_API_KEY nor ANTHROPIC_AUTH_TOKEN is set; \
                 place credentials in /Media/Ubuntu/Documents/ClaudeCode.txt \
                 (under '# Anthropic API') and reconnect MCP."
                    .into(),
            ));
        };

        // Resolve base URL. Strip trailing /v1 so we can always append it once.
        let raw_base = std::env::var("ANTHROPIC_BASE_URL")
            .ok()
            .filter(|s| !s.is_empty())
            .unwrap_or_else(|| DEFAULT_API_BASE.trim_end_matches("/v1").to_string());
        let trimmed = raw_base.trim_end_matches('/');
        let trimmed = trimmed.trim_end_matches("/v1");
        let base_url = format!("{trimmed}/v1");

        let http = reqwest::Client::builder()
            .timeout(Duration::from_secs(60))
            .user_agent(USER_AGENT)
            .build()
            .map_err(|e| Error::Backend(format!("anthropic http client init: {e}")))?;
        Ok(Self {
            api_key,
            base_url,
            auth_mode,
            http,
        })
    }

    /// One `/v1/messages` round-trip. The full conversation is `messages`;
    /// the system prompt (if any) is the `system` arg. Output token cap is
    /// `max_tokens` (1..=8192). Returns text + usage; on HTTP/non-2xx we
    /// surface the API's error body verbatim so debugging is fast.
    pub async fn messages_create(
        &self,
        model: &str,
        system: Option<&str>,
        messages: &[Message],
        max_tokens: u32,
    ) -> Result<MessagesResponse> {
        let max_tokens = max_tokens.clamp(1, 8192);
        let url = format!("{}/messages", self.base_url);

        let mut body = serde_json::json!({
            "model": model,
            "max_tokens": max_tokens,
            "messages": messages,
        });
        if let Some(s) = system.filter(|s| !s.is_empty()) {
            body["system"] = serde_json::Value::String(s.to_string());
        }

        let req = self
            .http
            .post(&url)
            .header("anthropic-version", ANTHROPIC_VERSION)
            .header("content-type", "application/json")
            .json(&body);
        let req = match self.auth_mode {
            AuthMode::XApiKey => req.header("x-api-key", &self.api_key),
            AuthMode::Bearer => req.header("Authorization", format!("Bearer {}", self.api_key)),
        };

        let resp = req
            .send()
            .await
            .map_err(|e| Error::Backend(format!("anthropic messages_create send: {e}")))?;

        let status = resp.status();
        let body_text = resp
            .text()
            .await
            .map_err(|e| Error::Backend(format!("anthropic messages_create body: {e}")))?;

        if !status.is_success() {
            return Err(Error::Backend(format!(
                "anthropic messages_create http {status}: {body_text}"
            )));
        }

        let v: serde_json::Value = serde_json::from_str(&body_text)
            .map_err(|e| Error::Backend(format!("anthropic messages_create parse: {e}")))?;

        Ok(parse_messages_response(&v))
    }
}

fn parse_messages_response(v: &serde_json::Value) -> MessagesResponse {
    // content is an array of blocks: [{type: "text", text: "..."}, ...].
    // We concatenate all text blocks; non-text blocks (tool_use etc) are
    // ignored — this client is text-only by design.
    let text = v
        .get("content")
        .and_then(|c| c.as_array())
        .map(|arr| {
            arr.iter()
                .filter_map(|block| {
                    if block.get("type").and_then(|t| t.as_str()) == Some("text") {
                        block.get("text").and_then(|t| t.as_str()).map(String::from)
                    } else {
                        None
                    }
                })
                .collect::<Vec<_>>()
                .join("")
        })
        .unwrap_or_default();

    let stop_reason = v
        .get("stop_reason")
        .and_then(|s| s.as_str())
        .map(String::from);

    let usage = v.get("usage").cloned().unwrap_or(serde_json::Value::Null);
    let input_tokens = usage
        .get("input_tokens")
        .and_then(|n| n.as_u64())
        .unwrap_or(0) as u32;
    let output_tokens = usage
        .get("output_tokens")
        .and_then(|n| n.as_u64())
        .unwrap_or(0) as u32;

    MessagesResponse {
        text,
        stop_reason,
        input_tokens,
        output_tokens,
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn parse_typical_messages_response() {
        let v: serde_json::Value = serde_json::from_str(
            r#"{
            "id": "msg_01",
            "type": "message",
            "role": "assistant",
            "model": "claude-haiku-4-5-20251001",
            "content": [{"type":"text","text":"hello "}, {"type":"text","text":"world"}],
            "stop_reason": "end_turn",
            "usage": {"input_tokens": 17, "output_tokens": 5}
        }"#,
        )
        .unwrap();
        let r = parse_messages_response(&v);
        assert_eq!(r.text, "hello world");
        assert_eq!(r.stop_reason.as_deref(), Some("end_turn"));
        assert_eq!(r.input_tokens, 17);
        assert_eq!(r.output_tokens, 5);
    }

    #[test]
    fn parse_response_skips_non_text_blocks() {
        let v: serde_json::Value = serde_json::from_str(
            r#"{
            "content": [
                {"type":"text","text":"answer:"},
                {"type":"tool_use","id":"x","name":"y","input":{}},
                {"type":"text","text":" 42"}
            ]
        }"#,
        )
        .unwrap();
        let r = parse_messages_response(&v);
        assert_eq!(r.text, "answer: 42");
    }

    #[test]
    fn parse_response_handles_missing_fields() {
        let v: serde_json::Value = serde_json::from_str("{}").unwrap();
        let r = parse_messages_response(&v);
        assert_eq!(r.text, "");
        assert_eq!(r.stop_reason, None);
        assert_eq!(r.input_tokens, 0);
        assert_eq!(r.output_tokens, 0);
    }
}
