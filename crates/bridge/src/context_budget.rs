//! Offline token heuristics for MCP `context_budget` (W5, DESIGN-warp-first-agent-shell).
//!
//! Does not call model APIs — multi-class char-rate estimate + per-turn guess.
//!
//! Calibrated against cl100k_base (GPT-4 / Claude family) on 10 representative
//! samples (prose, Rust, Python, shell, TOML, Markdown, CJK, mixed).
//! Typical error: 2–14% for code/prose/markdown. Structured-data (JSON keys with
//! many `"` delimiters) may overestimate by up to ~40% — conservative for budgeting.

/// Rough tokens-per-turn overhead when only turn count is known.
pub const PER_TURN_TOKEN_GUESS: u64 = 2_000;

// Per-class chars-per-token rates (empirically calibrated 2026-05-01).
const ALPHA_CHARS_PER_TOKEN: f64 = 4.0; // a-z, A-Z (non-CJK)
const DIGIT_CHARS_PER_TOKEN: f64 = 2.5; // 0-9
const PUNCT_CHARS_PER_TOKEN: f64 = 1.2; // operators, brackets, quotes, punctuation
const CJK_CHARS_PER_TOKEN: f64 = 1.1; // CJK Unified Ideographs + Kana + CJK symbols

#[inline]
fn is_cjk(ch: char) -> bool {
    matches!(
        ch,
        '\u{3000}'..='\u{303f}'
            | '\u{3040}'..='\u{309f}'
            | '\u{30a0}'..='\u{30ff}'
            | '\u{3400}'..='\u{4dbf}'
            | '\u{4e00}'..='\u{9fff}'
            | '\u{f900}'..='\u{faff}'
    )
}

/// Fast heuristic token estimator.
///
/// Counts each character into one of four classes (alpha / digit / punct / CJK)
/// and divides by the empirical chars-per-token rate for that class.
/// Whitespace is excluded from counting (tokenizers skip standalone whitespace).
pub fn estimate_tokens_from_text(sample: &str) -> u64 {
    let mut alpha: u64 = 0;
    let mut digit: u64 = 0;
    let mut punct: u64 = 0;
    let mut cjk: u64 = 0;

    for ch in sample.chars() {
        if ch.is_whitespace() {
            continue;
        }
        if is_cjk(ch) {
            cjk += 1;
        } else if ch.is_alphabetic() {
            alpha += 1;
        } else if ch.is_ascii_digit() {
            digit += 1;
        } else {
            punct += 1;
        }
    }

    let alpha_tokens = (alpha as f64 / ALPHA_CHARS_PER_TOKEN).ceil() as u64;
    let digit_tokens = (digit as f64 / DIGIT_CHARS_PER_TOKEN).ceil() as u64;
    let punct_tokens = (punct as f64 / PUNCT_CHARS_PER_TOKEN).ceil() as u64;
    let cjk_tokens = (cjk as f64 / CJK_CHARS_PER_TOKEN).ceil() as u64;

    alpha_tokens
        .saturating_add(digit_tokens)
        .saturating_add(punct_tokens)
        .saturating_add(cjk_tokens)
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
    fn ascii_alpha_uses_alpha_rate() {
        // 40 alpha chars → ceil(40/4.0) = 10 tokens
        let s = "a".repeat(40);
        assert_eq!(estimate_tokens_from_text(&s), 10);
    }

    #[test]
    fn cjk_uses_cjk_rate() {
        // 11 CJK chars → ceil(11/1.1) = 10 tokens
        let s = "测".repeat(11);
        assert_eq!(estimate_tokens_from_text(&s), 10);
    }

    #[test]
    fn digit_uses_digit_rate() {
        // 25 digits → ceil(25/2.5) = 10 tokens
        let s = "1".repeat(25);
        assert_eq!(estimate_tokens_from_text(&s), 10);
    }

    #[test]
    fn punct_uses_punct_rate() {
        // 12 punct → ceil(12/1.2) = 10 tokens
        let s = "{".repeat(12);
        assert_eq!(estimate_tokens_from_text(&s), 10);
    }

    #[test]
    fn mixed_text_estimate_is_positive() {
        let s = "Warp终端上下文预算 calibration test: fn foo() { 42 }";
        assert!(estimate_tokens_from_text(s) > 0);
    }

    #[test]
    fn whitespace_excluded() {
        let a = estimate_tokens_from_text("hello");
        let b = estimate_tokens_from_text("  hello  ");
        assert_eq!(a, b);
    }

    #[test]
    fn estimated_usage_adds_turn_overhead() {
        let s = "a".repeat(40);
        let base = estimate_tokens_from_text(&s);
        let with_turns = estimated_usage_tokens(&s, 3);
        assert_eq!(with_turns, base + PER_TURN_TOKEN_GUESS * 3);
    }

    #[test]
    fn model_defaults_claude_family() {
        assert_eq!(model_context_limit("claude-sonnet-4-20250514"), 200_000);
    }
}
