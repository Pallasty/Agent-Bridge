//! Offline token heuristics for MCP `context_budget` (W5, DESIGN-warp-first-agent-shell).
//!
//! Does not call model APIs — mixed EN/CJK char-rate estimate + per-turn guess.

/// Rough tokens-per-turn overhead when only turn count is known (conversation skeleton).
pub const PER_TURN_TOKEN_GUESS: u64 = 2_000;

#[inline]
fn is_cjk(ch: char) -> bool {
    matches!(
        ch,
        '\u{3000}'..='\u{303f}' | '\u{3040}'..='\u{309f}' | '\u{30a0}'..='\u{30ff}' |
        '\u{3400}'..='\u{4dbf}' | '\u{4e00}'..='\u{9fff}' | '\u{f900}'..='\u{faff}'
    )
}

/// Fast heuristic: non‑CJK ≈ 3.5 chars/token; CJK ≈ 1.5 chars/token (DESIGN defaults).
pub fn estimate_tokens_from_text(sample: &str) -> u64 {
    let mut non_cjk: u64 = 0;
    let mut cjk: u64 = 0;
    for ch in sample.chars() {
        if ch.is_whitespace() {
            continue;
        }
        if is_cjk(ch) {
            cjk += 1;
        } else {
            non_cjk += 1;
        }
    }
    let en_tokens = (non_cjk as f64 / 3.5).ceil() as u64;
    let zh_tokens = (cjk as f64 / 1.5).ceil() as u64;
    en_tokens.saturating_add(zh_tokens)
}

/// Known-ish context windows (approximate; models vary by SKU/date).
pub fn model_context_limit(model: &str) -> u64 {
    let m = model.to_lowercase();
    if m.contains("gemini") {
        return 1_048_576;
    }
    if m.contains("gpt-4o") || m.contains("gpt-4-turbo") {
        return 128_000;
    }
    if m.contains("gpt-4") {
        return 128_000;
    }
    if m.contains("gpt-3.5") {
        return 16_385;
    }
    if m.contains("claude") || m.contains("opus") || m.contains("sonnet") || m.contains("haiku") {
        return 200_000;
    }
    200_000
}

pub fn budget_recommendation(pct_used: f64) -> &'static str {
    if pct_used < 60.0 {
        "nominal"
    } else if pct_used < 80.0 {
        "suggest_session_curate"
    } else {
        "urgent_handoff_or_compact"
    }
}

pub fn estimated_usage_tokens(text_sample: &str, conversation_turns: u64) -> u64 {
    estimate_tokens_from_text(text_sample)
        .saturating_add(conversation_turns.saturating_mul(PER_TURN_TOKEN_GUESS))
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn ascii_uses_divisor_35() {
        // 35 letters → ~10 tokens
        let s = "a".repeat(35);
        assert_eq!(estimate_tokens_from_text(&s), 10);
    }

    #[test]
    fn model_defaults_claude_family() {
        assert_eq!(model_context_limit("claude-sonnet-4-20250514"), 200_000);
    }
}
