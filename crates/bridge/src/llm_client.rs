//! Provider-agnostic LLM client wrapper.
//!
//! The memory layer (Phase 1 P4b evolution filter, P5 cluster summary) calls
//! a hosted LLM. We support two protocols:
//!
//!   * Anthropic Messages API (`POST /v1/messages`) — used by api.anthropic.com,
//!     bltcy.ai, comfly.chat, wenwen-ai, anyrouter, etc.
//!   * OpenAI Chat Completions API (`POST /chat/completions`) — used by
//!     api.openai.com, Gemini's openai-compat endpoint, NVIDIA build,
//!     OpenRouter, Groq, opencode-zen, Together, DeepInfra, etc.
//!
//! `LlmClient::from_env()` picks one based on env. Selection precedence:
//!   1. `AGENT_BRIDGE_LLM_PROVIDER=anthropic|openai` — explicit override.
//!   2. If `ANTHROPIC_API_KEY` or `ANTHROPIC_AUTH_TOKEN` is set → Anthropic.
//!   3. If `OPENAI_API_KEY` is set → OpenAI.
//!   4. Otherwise → error with a hint about which env to set.
//!
//! All callers use the same `Message` + `MessagesResponse` types regardless
//! of which provider is chosen — protocol details stay inside the variant.

use ab_core::{Error, Result};

use crate::anthropic_api::AnthropicClient;
use crate::openai_api::OpenAiClient;

pub use crate::anthropic_api::{Message, MessagesResponse};

#[derive(Debug)]
pub enum LlmClient {
    Anthropic(AnthropicClient),
    OpenAi(OpenAiClient),
}

impl LlmClient {
    /// Build the right client based on env. See module docs for selection rules.
    pub fn from_env() -> Result<Self> {
        if let Ok(provider) = std::env::var("AGENT_BRIDGE_LLM_PROVIDER") {
            match provider.trim().to_ascii_lowercase().as_str() {
                "anthropic" => return Ok(Self::Anthropic(AnthropicClient::from_env()?)),
                "openai" => return Ok(Self::OpenAi(OpenAiClient::from_env()?)),
                other if !other.is_empty() => {
                    return Err(Error::Backend(format!(
                        "AGENT_BRIDGE_LLM_PROVIDER={other:?} is not recognized; \
                         use 'anthropic' or 'openai'"
                    )));
                }
                _ => {}
            }
        }

        let has_anthropic = std::env::var("ANTHROPIC_API_KEY")
            .ok()
            .filter(|s| !s.is_empty())
            .is_some()
            || std::env::var("ANTHROPIC_AUTH_TOKEN")
                .ok()
                .filter(|s| !s.is_empty())
                .is_some();
        if has_anthropic {
            return Ok(Self::Anthropic(AnthropicClient::from_env()?));
        }

        let has_openai = std::env::var("OPENAI_API_KEY")
            .ok()
            .filter(|s| !s.is_empty())
            .is_some();
        if has_openai {
            return Ok(Self::OpenAi(OpenAiClient::from_env()?));
        }

        Err(Error::Backend(
            "no LLM credentials found; set ANTHROPIC_API_KEY / ANTHROPIC_AUTH_TOKEN \
             or OPENAI_API_KEY (and optionally AGENT_BRIDGE_LLM_PROVIDER + \
             ANTHROPIC_BASE_URL / OPENAI_BASE_URL)"
                .into(),
        ))
    }

    /// Provider tag for logs. "anthropic" or "openai".
    pub fn provider(&self) -> &'static str {
        match self {
            Self::Anthropic(_) => "anthropic",
            Self::OpenAi(_) => "openai",
        }
    }

    /// Pick the model name for this client. `AGENT_BRIDGE_LLM_MODEL` env var
    /// overrides; otherwise we fall back to a sensible default per provider.
    pub fn default_model(&self) -> String {
        if let Ok(m) = std::env::var("AGENT_BRIDGE_LLM_MODEL") {
            if !m.is_empty() {
                return m;
            }
        }
        match self {
            Self::Anthropic(_) => crate::anthropic_api::DEFAULT_MODEL.to_string(),
            Self::OpenAi(_) => crate::openai_api::DEFAULT_MODEL.to_string(),
        }
    }

    /// One round-trip. Same shape as the Anthropic client.
    pub async fn messages_create(
        &self,
        model: &str,
        system: Option<&str>,
        messages: &[Message],
        max_tokens: u32,
    ) -> Result<MessagesResponse> {
        match self {
            Self::Anthropic(c) => c.messages_create(model, system, messages, max_tokens).await,
            Self::OpenAi(c) => c.messages_create(model, system, messages, max_tokens).await,
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::sync::Mutex;

    // Env var mutation isn't thread-safe; serialize tests in this module.
    static ENV_LOCK: Mutex<()> = Mutex::new(());

    fn clear_llm_env() {
        for k in [
            "AGENT_BRIDGE_LLM_PROVIDER",
            "ANTHROPIC_API_KEY",
            "ANTHROPIC_AUTH_TOKEN",
            "ANTHROPIC_BASE_URL",
            "OPENAI_API_KEY",
            "OPENAI_BASE_URL",
        ] {
            std::env::remove_var(k);
        }
    }

    #[test]
    fn from_env_explicit_anthropic() {
        let _g = ENV_LOCK.lock().unwrap();
        clear_llm_env();
        std::env::set_var("AGENT_BRIDGE_LLM_PROVIDER", "anthropic");
        std::env::set_var("ANTHROPIC_API_KEY", "sk-ant-test");
        let c = LlmClient::from_env().expect("anthropic from_env");
        assert_eq!(c.provider(), "anthropic");
        clear_llm_env();
    }

    #[test]
    fn from_env_explicit_openai() {
        let _g = ENV_LOCK.lock().unwrap();
        clear_llm_env();
        std::env::set_var("AGENT_BRIDGE_LLM_PROVIDER", "openai");
        std::env::set_var("OPENAI_API_KEY", "sk-test");
        let c = LlmClient::from_env().expect("openai from_env");
        assert_eq!(c.provider(), "openai");
        clear_llm_env();
    }

    #[test]
    fn from_env_fallback_prefers_anthropic_over_openai() {
        let _g = ENV_LOCK.lock().unwrap();
        clear_llm_env();
        std::env::set_var("ANTHROPIC_API_KEY", "sk-ant-test");
        std::env::set_var("OPENAI_API_KEY", "sk-test");
        let c = LlmClient::from_env().expect("fallback from_env");
        assert_eq!(c.provider(), "anthropic");
        clear_llm_env();
    }

    #[test]
    fn from_env_fallback_to_openai_when_no_anthropic() {
        let _g = ENV_LOCK.lock().unwrap();
        clear_llm_env();
        std::env::set_var("OPENAI_API_KEY", "sk-test");
        let c = LlmClient::from_env().expect("openai fallback");
        assert_eq!(c.provider(), "openai");
        clear_llm_env();
    }

    #[test]
    fn from_env_errors_when_no_creds() {
        let _g = ENV_LOCK.lock().unwrap();
        clear_llm_env();
        let err = LlmClient::from_env().expect_err("should error");
        let msg = format!("{err}");
        assert!(msg.contains("no LLM credentials"), "msg = {msg}");
    }

    #[test]
    fn from_env_unrecognized_provider() {
        let _g = ENV_LOCK.lock().unwrap();
        clear_llm_env();
        std::env::set_var("AGENT_BRIDGE_LLM_PROVIDER", "garbage");
        let err = LlmClient::from_env().expect_err("should error");
        let msg = format!("{err}");
        assert!(msg.contains("not recognized"), "msg = {msg}");
        clear_llm_env();
    }

    #[test]
    fn default_model_respects_env_override() {
        let _g = ENV_LOCK.lock().unwrap();
        clear_llm_env();
        std::env::set_var("OPENAI_API_KEY", "sk-test");
        std::env::set_var("AGENT_BRIDGE_LLM_MODEL", "custom-model");
        let c = LlmClient::from_env().unwrap();
        assert_eq!(c.default_model(), "custom-model");
        clear_llm_env();
    }
}
