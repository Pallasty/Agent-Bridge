//! Ad-hoc smoke test for the LlmClient wrapper. Runs one trivial
//! `messages_create` round-trip and prints provider + response.
//!
//! Run with explicit provider:
//!   AGENT_BRIDGE_LLM_PROVIDER=openai \
//!   OPENAI_API_KEY=... \
//!   OPENAI_BASE_URL=https://api-inference.modelscope.cn/v1 \
//!   AGENT_BRIDGE_LLM_MODEL=Qwen/Qwen3-235B-A22B-Instruct-2507 \
//!   cargo run --release -p ab-bridge --example llm_smoke
//!
//! Or with whatever ANTHROPIC_* env is currently set (auto-falls-back to
//! Anthropic protocol).

use ab_bridge::llm_client::{LlmClient, Message};

#[tokio::main]
async fn main() -> anyhow::Result<()> {
    let client = LlmClient::from_env()?;
    println!("provider = {}", client.provider());
    let model = client.default_model();
    println!("model = {model}");
    let resp = client
        .messages_create(
            &model,
            None,
            &[Message {
                role: "user".to_string(),
                content: "Reply with exactly one word: PASS".to_string(),
            }],
            32,
        )
        .await?;
    println!("text = {:?}", resp.text);
    println!("stop_reason = {:?}", resp.stop_reason);
    println!(
        "tokens: in={} out={}",
        resp.input_tokens, resp.output_tokens
    );
    Ok(())
}
