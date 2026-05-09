//! OpenAI-protocol HTTP client (Chat Completions API).
//!
//! Used as a fallback / alternate provider for the same memory-layer LLM
//! workloads that `anthropic_api.rs` serves: Phase 1 P4b (evolution filter)
//! and P5 (cluster summary). Speaking the OpenAI protocol unlocks a much
//! larger free-tier pool than Anthropic alone — Gemini's OpenAI-compatible
//! endpoint, NVIDIA build, OpenRouter, Groq, Together, DeepInfra,
//! opencode-zen, comfly, etc.
//!
//! Endpoint: POST `<base_url>/chat/completions`
//! Auth:     `Authorization: Bearer <key>`
//!
//! Response/request bodies use the same `Message {role, content}` and
//! `MessagesResponse {text, stop_reason, input_tokens, output_tokens}`
//! types as the Anthropic client, so callers are protocol-agnostic.

use ab_core::{Error, Result};
use std::time::Duration;

use crate::anthropic_api::{Message, MessagesResponse};

const DEFAULT_API_BASE: &str = "https://api.openai.com/v1";
const USER_AGENT: &str = "agent-bridge-mcp";

/// Default model. Picked to be present on most OpenAI-compat providers
/// (OpenRouter, NVIDIA build, Groq, Together) without 404. Override per call.
pub const DEFAULT_MODEL: &str = "gpt-4o-mini";

#[derive(Debug)]
pub struct OpenAiClient {
    api_key: String,
    base_url: String,
    http: reqwest::Client,
}

impl OpenAiClient {
    /// Build a client from env. Honors:
    ///   * `OPENAI_API_KEY` — Bearer key
    ///   * `OPENAI_BASE_URL` — endpoint override. Strip a trailing `/v1` if
    ///     present (we re-append it once) so users can paste either form.
    ///     For Gemini's openai-compat endpoint set this to
    ///     `https://generativelanguage.googleapis.com/v1beta/openai`.
    pub fn from_env() -> Result<Self> {
        let api_key = std::env::var("OPENAI_API_KEY")
            .ok()
            .filter(|s| !s.is_empty())
            .ok_or_else(|| {
                Error::Backend(
                    "OPENAI_API_KEY is not set; place credentials in \
                     ~/Documents/ClaudeCode.txt and reconnect MCP."
                        .into(),
                )
            })?;

        let raw_base = std::env::var("OPENAI_BASE_URL")
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
            .map_err(|e| Error::Backend(format!("openai http client init: {e}")))?;
        Ok(Self {
            api_key,
            base_url,
            http,
        })
    }

    /// One `chat/completions` round-trip.  Same shape as the Anthropic client:
    /// `system` becomes a leading `{role:"system", content:...}` message,
    /// `messages` are passed through, `max_tokens` clamped to [1, 8192].
    /// Errors surface the API's body verbatim for fast debugging.
    pub async fn messages_create(
        &self,
        model: &str,
        system: Option<&str>,
        messages: &[Message],
        max_tokens: u32,
    ) -> Result<MessagesResponse> {
        let max_tokens = max_tokens.clamp(1, 8192);
        let url = format!("{}/chat/completions", self.base_url);

        let mut all_messages: Vec<serde_json::Value> = Vec::with_capacity(messages.len() + 1);
        if let Some(s) = system.filter(|s| !s.is_empty()) {
            all_messages.push(serde_json::json!({
                "role": "system",
                "content": s,
            }));
        }
        for m in messages {
            all_messages.push(serde_json::json!({
                "role": m.role,
                "content": m.content,
            }));
        }

        let body = serde_json::json!({
            "model": model,
            "max_tokens": max_tokens,
            "messages": all_messages,
        });

        let resp = self
            .http
            .post(&url)
            .header("content-type", "application/json")
            .header("Authorization", format!("Bearer {}", self.api_key))
            .json(&body)
            .send()
            .await
            .map_err(|e| Error::Backend(format!("openai chat_completions send: {e}")))?;

        let status = resp.status();
        let body_text = resp
            .text()
            .await
            .map_err(|e| Error::Backend(format!("openai chat_completions body: {e}")))?;

        if !status.is_success() {
            return Err(Error::Backend(format!(
                "openai chat_completions http {status}: {body_text}"
            )));
        }

        let v: serde_json::Value = serde_json::from_str(&body_text)
            .map_err(|e| Error::Backend(format!("openai chat_completions parse: {e}")))?;
        Ok(parse_chat_completions_response(&v))
    }
}

fn parse_chat_completions_response(v: &serde_json::Value) -> MessagesResponse {
    // choices[0].message.content carries the text. Some providers emit
    // {role: "assistant", content: null, reasoning_content: "..."} for
    // reasoning models — fall back to reasoning_content if content is null.
    let (text, stop_reason) = v
        .get("choices")
        .and_then(|c| c.as_array())
        .and_then(|arr| arr.first())
        .map(|c0| {
            let msg = c0.get("message");
            let content = msg
                .and_then(|m| m.get("content"))
                .and_then(|c| c.as_str())
                .map(String::from)
                .or_else(|| {
                    msg.and_then(|m| m.get("reasoning_content"))
                        .and_then(|c| c.as_str())
                        .map(String::from)
                })
                .unwrap_or_default();
            let finish = c0
                .get("finish_reason")
                .and_then(|s| s.as_str())
                .map(String::from);
            (content, finish)
        })
        .unwrap_or_default();

    let usage = v.get("usage").cloned().unwrap_or(serde_json::Value::Null);
    let input_tokens = usage
        .get("prompt_tokens")
        .and_then(|n| n.as_u64())
        .unwrap_or(0) as u32;
    let output_tokens = usage
        .get("completion_tokens")
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
    fn parse_typical_chat_completions_response() {
        let v: serde_json::Value = serde_json::from_str(
            r#"{
            "id": "chatcmpl-x",
            "object": "chat.completion",
            "model": "gpt-4o-mini",
            "choices": [{
                "index": 0,
                "message": {"role":"assistant","content":"hello world"},
                "finish_reason": "stop"
            }],
            "usage": {"prompt_tokens": 12, "completion_tokens": 3, "total_tokens": 15}
        }"#,
        )
        .unwrap();
        let r = parse_chat_completions_response(&v);
        assert_eq!(r.text, "hello world");
        assert_eq!(r.stop_reason.as_deref(), Some("stop"));
        assert_eq!(r.input_tokens, 12);
        assert_eq!(r.output_tokens, 3);
    }

    #[test]
    fn parse_falls_back_to_reasoning_content_when_content_null() {
        let v: serde_json::Value = serde_json::from_str(
            r#"{
            "choices": [{
                "message": {"role":"assistant","content": null,"reasoning_content":"step by step: 42"},
                "finish_reason": "stop"
            }]
        }"#,
        )
        .unwrap();
        let r = parse_chat_completions_response(&v);
        assert_eq!(r.text, "step by step: 42");
    }

    #[test]
    fn parse_handles_empty_response() {
        let v: serde_json::Value = serde_json::from_str("{}").unwrap();
        let r = parse_chat_completions_response(&v);
        assert_eq!(r.text, "");
        assert_eq!(r.stop_reason, None);
        assert_eq!(r.input_tokens, 0);
        assert_eq!(r.output_tokens, 0);
    }
}
