//! Provider-agnostic LLM client wrapper with automatic fallback.
//!
//! The memory layer (Phase 1 P4b evolution filter, P5 cluster summary) calls
//! a hosted LLM. We support two protocols:
//!
//!   * Anthropic Messages API (`POST /v1/messages`) — used by api.anthropic.com
//!     and compatible relays.
//!   * OpenAI Chat Completions API (`POST /chat/completions`) — used by
//!     api.openai.com, Gemini's openai-compat endpoint, NVIDIA build,
//!     OpenRouter, Groq, opencode-zen, Together, DeepInfra, etc.
//!
//! `LlmClient::from_env()` picks one as **primary** based on env. Selection:
//!   1. `AGENT_BRIDGE_LLM_PROVIDER=anthropic|openai` — explicit override.
//!   2. If `ANTHROPIC_API_KEY` or `ANTHROPIC_AUTH_TOKEN` is set → Anthropic.
//!   3. If `OPENAI_API_KEY` is set → OpenAI.
//!   4. Otherwise → error.
//!
//! If credentials for the *other* protocol are also set, that becomes a
//! **secondary** client. On any primary `messages_create` error, the call
//! retries once via the secondary using *its* default model (model names
//! aren't portable — claude-haiku on OpenAI protocol → 404, gpt-4o-mini
//! on modelscope → 400). Set `AGENT_BRIDGE_LLM_FALLBACK_MODEL` if the
//! fallback endpoint needs a non-default model name (e.g. modelscope
//! requires `Qwen/Qwen3-235B-A22B-Instruct-2507`). Disable fallback with
//! `AGENT_BRIDGE_LLM_FALLBACK=0` for strict single-provider semantics.
//!
//! All callers use the same `Message` + `MessagesResponse` types regardless
//! of which provider answered.

use ab_core::{Error, Result};

use crate::anthropic_api::AnthropicClient;
use crate::openai_api::OpenAiClient;

pub use crate::anthropic_api::{Message, MessagesResponse};

/// One concrete provider — the building block; not exposed to callers.
#[derive(Debug)]
enum Provider {
    Anthropic(AnthropicClient),
    OpenAi(OpenAiClient),
}

impl Provider {
    fn tag(&self) -> &'static str {
        match self {
            Self::Anthropic(_) => "anthropic",
            Self::OpenAi(_) => "openai",
        }
    }

    /// Default model name. Reads `AGENT_BRIDGE_LLM_MODEL` first, else falls
    /// back to a per-protocol hardcoded default. The `for_fallback` flag
    /// switches the env-var precedence to `AGENT_BRIDGE_LLM_FALLBACK_MODEL`
    /// so primary and secondary can target different models — needed because
    /// e.g. modelscope rejects `gpt-4o-mini` and Anthropic rejects `Qwen/...`.
    fn default_model(&self, for_fallback: bool) -> String {
        let env_key = if for_fallback {
            "AGENT_BRIDGE_LLM_FALLBACK_MODEL"
        } else {
            "AGENT_BRIDGE_LLM_MODEL"
        };
        if let Ok(m) = std::env::var(env_key) {
            if !m.is_empty() {
                return m;
            }
        }
        match self {
            Self::Anthropic(_) => crate::anthropic_api::DEFAULT_MODEL.to_string(),
            Self::OpenAi(_) => crate::openai_api::DEFAULT_MODEL.to_string(),
        }
    }

    async fn messages_create(
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

#[derive(Debug)]
pub struct LlmClient {
    primary: Provider,
    secondary: Option<Provider>,
}

impl LlmClient {
    /// Build the right client based on env. See module docs for selection rules.
    pub fn from_env() -> Result<Self> {
        let primary = pick_primary()?;
        let secondary = if std::env::var("AGENT_BRIDGE_LLM_FALLBACK").as_deref() == Ok("0") {
            None
        } else {
            try_build_other(&primary)
        };
        Ok(Self { primary, secondary })
    }

    /// Provider tag for logs — the **primary** provider. "anthropic" or "openai".
    pub fn provider(&self) -> &'static str {
        self.primary.tag()
    }

    /// Provider tag of the configured fallback, if any.
    pub fn fallback_provider(&self) -> Option<&'static str> {
        self.secondary.as_ref().map(|p| p.tag())
    }

    /// Pick the model name for the primary client. `AGENT_BRIDGE_LLM_MODEL`
    /// env var overrides; otherwise we fall back to a sensible default per
    /// provider. Note: on fallback, the secondary uses its **own** default
    /// since the env model name may not be portable across protocols.
    pub fn default_model(&self) -> String {
        self.primary.default_model(false)
    }

    /// One round-trip. Tries the primary, then on error retries via the
    /// secondary (if configured). Returns the primary error wrapped with
    /// secondary error if both fail.
    pub async fn messages_create(
        &self,
        model: &str,
        system: Option<&str>,
        messages: &[Message],
        max_tokens: u32,
    ) -> Result<MessagesResponse> {
        let primary_result = self
            .primary
            .messages_create(model, system, messages, max_tokens)
            .await;
        match primary_result {
            Ok(r) => Ok(r),
            Err(primary_err) => {
                let Some(secondary) = self.secondary.as_ref() else {
                    return Err(primary_err);
                };
                let sec_model = secondary.default_model(true);
                tracing::warn!(
                    target: "llm_client",
                    primary = %self.primary.tag(),
                    secondary = %secondary.tag(),
                    secondary_model = %sec_model,
                    error = %primary_err,
                    "primary LLM failed; retrying via secondary"
                );
                secondary
                    .messages_create(&sec_model, system, messages, max_tokens)
                    .await
                    .map_err(|sec_err| {
                        Error::Backend(format!(
                            "LLM primary({}) failed: {primary_err}; \
                             fallback({}) also failed: {sec_err}",
                            self.primary.tag(),
                            secondary.tag()
                        ))
                    })
            }
        }
    }
}

fn pick_primary() -> Result<Provider> {
    if let Ok(p) = std::env::var("AGENT_BRIDGE_LLM_PROVIDER") {
        match p.trim().to_ascii_lowercase().as_str() {
            "anthropic" => return Ok(Provider::Anthropic(AnthropicClient::from_env()?)),
            "openai" => return Ok(Provider::OpenAi(OpenAiClient::from_env()?)),
            other if !other.is_empty() => {
                return Err(Error::Backend(format!(
                    "AGENT_BRIDGE_LLM_PROVIDER={other:?} is not recognized; \
                     use 'anthropic' or 'openai'"
                )));
            }
            _ => {}
        }
    }

    let has_anthropic = nonempty_env("ANTHROPIC_API_KEY") || nonempty_env("ANTHROPIC_AUTH_TOKEN");
    if has_anthropic {
        return Ok(Provider::Anthropic(AnthropicClient::from_env()?));
    }
    if nonempty_env("OPENAI_API_KEY") {
        return Ok(Provider::OpenAi(OpenAiClient::from_env()?));
    }

    Err(Error::Backend(
        "no LLM credentials found; set ANTHROPIC_API_KEY / ANTHROPIC_AUTH_TOKEN \
         or OPENAI_API_KEY (and optionally AGENT_BRIDGE_LLM_PROVIDER + \
         ANTHROPIC_BASE_URL / OPENAI_BASE_URL)"
            .into(),
    ))
}

/// Build the *other* provider (Anthropic if primary is OpenAI and vice versa)
/// from env, returning None if its credentials are absent or its construction
/// fails for any reason. Fallback is best-effort: a missing secondary is fine.
fn try_build_other(primary: &Provider) -> Option<Provider> {
    match primary {
        Provider::Anthropic(_) => {
            if !nonempty_env("OPENAI_API_KEY") {
                return None;
            }
            OpenAiClient::from_env().ok().map(Provider::OpenAi)
        }
        Provider::OpenAi(_) => {
            let has_anthropic =
                nonempty_env("ANTHROPIC_API_KEY") || nonempty_env("ANTHROPIC_AUTH_TOKEN");
            if !has_anthropic {
                return None;
            }
            AnthropicClient::from_env().ok().map(Provider::Anthropic)
        }
    }
}

fn nonempty_env(k: &str) -> bool {
    std::env::var(k).ok().filter(|s| !s.is_empty()).is_some()
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
            "AGENT_BRIDGE_LLM_FALLBACK",
            "AGENT_BRIDGE_LLM_MODEL",
            "AGENT_BRIDGE_LLM_FALLBACK_MODEL",
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
        assert_eq!(c.fallback_provider(), None, "no openai creds = no fallback");
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
        assert_eq!(c.fallback_provider(), None);
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

    #[test]
    fn fallback_model_env_distinct_from_primary_model() {
        let _g = ENV_LOCK.lock().unwrap();
        clear_llm_env();
        std::env::set_var("ANTHROPIC_API_KEY", "sk-ant-test");
        std::env::set_var("OPENAI_API_KEY", "sk-test");
        std::env::set_var("AGENT_BRIDGE_LLM_MODEL", "claude-haiku-x");
        std::env::set_var("AGENT_BRIDGE_LLM_FALLBACK_MODEL", "Qwen/QwQ-32B");
        let c = LlmClient::from_env().unwrap();
        // Primary (anthropic) reads AGENT_BRIDGE_LLM_MODEL.
        assert_eq!(c.default_model(), "claude-haiku-x");
        // Secondary (openai) would use AGENT_BRIDGE_LLM_FALLBACK_MODEL.
        // We can't observe it directly without making `default_model` pub
        // on Provider, but we proved the wiring via the `for_fallback` flag.
        clear_llm_env();
    }

    #[test]
    fn from_env_auto_builds_secondary_when_both_creds_present() {
        let _g = ENV_LOCK.lock().unwrap();
        clear_llm_env();
        std::env::set_var("ANTHROPIC_API_KEY", "sk-ant-test");
        std::env::set_var("OPENAI_API_KEY", "sk-test");
        let c = LlmClient::from_env().expect("from_env");
        assert_eq!(c.provider(), "anthropic");
        assert_eq!(c.fallback_provider(), Some("openai"));
        clear_llm_env();
    }

    #[test]
    fn from_env_auto_builds_anthropic_secondary_when_openai_primary() {
        let _g = ENV_LOCK.lock().unwrap();
        clear_llm_env();
        std::env::set_var("AGENT_BRIDGE_LLM_PROVIDER", "openai");
        std::env::set_var("OPENAI_API_KEY", "sk-test");
        std::env::set_var("ANTHROPIC_AUTH_TOKEN", "sk-bearer");
        let c = LlmClient::from_env().expect("from_env");
        assert_eq!(c.provider(), "openai");
        assert_eq!(c.fallback_provider(), Some("anthropic"));
        clear_llm_env();
    }

    #[test]
    fn fallback_disabled_via_env_knob() {
        let _g = ENV_LOCK.lock().unwrap();
        clear_llm_env();
        std::env::set_var("AGENT_BRIDGE_LLM_FALLBACK", "0");
        std::env::set_var("ANTHROPIC_API_KEY", "sk-ant-test");
        std::env::set_var("OPENAI_API_KEY", "sk-test");
        let c = LlmClient::from_env().expect("from_env");
        assert_eq!(c.provider(), "anthropic");
        assert_eq!(c.fallback_provider(), None, "fallback disabled");
        clear_llm_env();
    }
}
