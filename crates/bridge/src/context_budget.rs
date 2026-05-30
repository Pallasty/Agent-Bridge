//! Offline token heuristics for MCP `context_budget` (W5, DESIGN-warp-first-agent-shell).
//!
//! Does not call model APIs — multi-class char-rate estimate + per-turn guess.
//!
//! Calibrated against cl100k_base (GPT-4 / Claude family) on 10 representative
//! samples (prose, Rust, Python, shell, TOML, Markdown, CJK, mixed).
//! Typical error: 2–14% for code/prose/markdown. Structured-data (JSON keys with
//! many `"` delimiters) may overestimate by up to ~40% — conservative for budgeting.

/// Rough tokens-per-turn overhead when only turn count is known.
///
/// Calibration source: 2026-05-19 dogfood — 30-turn agent-bridge tool-heavy
/// session reported 30% used (60K) but real usage was ~55-70% (~120K).
/// Implied real avg ≈ 4150 tok/turn (file reads + tool results dominate).
/// 2000 was calibrated against light chat sessions; 4000 splits the
/// difference for mixed agentic work. Light chat will over-count; heavy
/// tool sessions still under-count modestly — pass `text_sample` for
/// accuracy when the call matters.
pub const PER_TURN_TOKEN_GUESS: u64 = 4_000;

/// Always-loaded system overhead in Claude Code style sessions.
///
/// Captures: system prompt + tool schemas (one-time per session, but
/// re-inflated each turn due to caching boundaries) + auto-loaded
/// MEMORY.md (~22 KB / ~6 K tok at typical project size) + assorted
/// CLAUDE.md / settings overlays. ~15 K is the agent-bridge baseline
/// after the 2026-05-19 MEMORY.md trim; pre-trim was closer to 18 K.
///
/// Added unconditionally to `estimated_usage_tokens` so a "0 turns,
/// no sample" reading is not pathologically zero — at session start
/// the assistant already carries ~15 K of context before the user
/// types anything.
pub const SYSTEM_BASELINE_TOKENS: u64 = 15_000;

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

/// Whether `model` belongs to an Anthropic family that offers a ≥1M-token
/// long-context beta.
///
/// The model id alone CANNOT distinguish the 200K-vs-1M SKU — the 1M window
/// is enabled by a request-time beta header, not encoded in the name — so
/// [`model_context_limit`] deliberately keeps the conservative 200K default.
/// This flag exists only so callers can be told they SHOULD pass an explicit
/// `context_window` when the session is actually running the long-context
/// beta. Without it, pressure is inflated up to 5× — the 2026-05-30 dogfood
/// failure (#1758): an opus-4.8 @ 1M session read 247% "saturated/urgent"
/// when real utilization was ~50%.
///
/// Scoped to opus-4.x / sonnet-4.x (the families with a documented 1M beta).
/// Gemini already resolves to its true ≥1M window in [`model_context_limit`],
/// so it is intentionally not flagged here.
pub fn model_supports_1m_beta(model: &str) -> bool {
    let m = model.to_lowercase();
    m.contains("opus-4") || m.contains("opus 4") || m.contains("sonnet-4") || m.contains("sonnet 4")
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
    SYSTEM_BASELINE_TOKENS
        .saturating_add(estimate_tokens_from_text(text_sample))
        .saturating_add(conversation_turns.saturating_mul(PER_TURN_TOKEN_GUESS))
}

/// **L6 P3** — categorical fatigue tier from context-window pct utilization.
///
/// Bands per roadmap §3.3:
/// - `fresh`    — `< 30%` used
/// - `engaged`  — `30% .. 60%`
/// - `strained` — `60% .. 85%`
/// - `saturated`— `≥ 85%`
///
/// Boundaries are exclusive at the upper edge so `30.0` falls in
/// `engaged`, not `fresh` — chosen to bias toward the more cautious
/// tier at exact-boundary inputs.
pub fn fatigue_tier(pct_used: f64) -> &'static str {
    if pct_used < 30.0 {
        "fresh"
    } else if pct_used < 60.0 {
        "engaged"
    } else if pct_used < 85.0 {
        "strained"
    } else {
        "saturated"
    }
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
    fn estimated_usage_adds_baseline_plus_turn_overhead() {
        let s = "a".repeat(40);
        let text = estimate_tokens_from_text(&s);
        let with_turns = estimated_usage_tokens(&s, 3);
        assert_eq!(
            with_turns,
            SYSTEM_BASELINE_TOKENS + text + PER_TURN_TOKEN_GUESS * 3
        );
    }

    /// Regression: 2026-05-19 dogfood found 30-turn no-sample reading at
    /// 30% (60K) when real usage was ~55-70%. Post-calibration the same
    /// inputs must read ≥55% on a 200K Claude window, putting the tier at
    /// "strained" (was "engaged") — matches observed agent-bridge tool-heavy
    /// average ≈ 4150 tok/turn + baseline overhead.
    #[test]
    fn no_sample_thirty_turns_reads_strained_post_calibration() {
        let est = estimated_usage_tokens("", 30);
        let pct = est as f64 / 200_000.0 * 100.0;
        assert!(
            pct >= 55.0,
            "30 turns no-sample must read ≥55% (got {:.1}%) — calibration regressed",
            pct
        );
        assert_eq!(
            fatigue_tier(pct),
            "strained",
            "30 turns no-sample must classify as strained, got {} at {:.1}%",
            fatigue_tier(pct),
            pct
        );
    }

    /// Regression: a fresh session (0 turns, no sample) must still acknowledge
    /// the system-prompt + MEMORY.md baseline overhead (~15K of 200K = ~7.5%),
    /// not pathologically report 0% used.
    #[test]
    fn fresh_session_carries_system_baseline() {
        let est = estimated_usage_tokens("", 0);
        assert_eq!(est, SYSTEM_BASELINE_TOKENS);
        let pct = est as f64 / 200_000.0 * 100.0;
        assert!(pct > 5.0 && pct < 15.0, "baseline pct = {:.1}", pct);
    }

    #[test]
    fn model_defaults_claude_family() {
        assert_eq!(model_context_limit("claude-sonnet-4-20250514"), 200_000);
    }

    #[test]
    fn one_m_beta_families_flagged_but_default_stays_200k() {
        // opus-4.x / sonnet-4.x: flagged as 1M-beta-capable, yet the
        // conservative default limit is unchanged (SKU is ambiguous from
        // the name — the caller must pass an explicit context_window).
        for m in [
            "claude-opus-4-8",
            "claude-opus-4.8",
            "claude-opus-4-1-20250805",
            "claude-sonnet-4-6",
            "claude-sonnet-4-20250514",
        ] {
            assert!(model_supports_1m_beta(m), "{m} should be 1M-beta-capable");
            assert_eq!(
                model_context_limit(m),
                200_000,
                "{m} default must stay conservative 200K"
            );
        }
        // Not 1M-beta families: older Claude, haiku, non-Anthropic.
        for m in [
            "claude-3-5-sonnet-20241022",
            "claude-haiku-4-5-20251001",
            "claude-3-opus",
            "gpt-4o",
            "gpt-4-turbo",
        ] {
            assert!(
                !model_supports_1m_beta(m),
                "{m} must NOT be flagged as 1M-beta"
            );
        }
    }

    #[test]
    fn fatigue_tier_bands_cover_full_range() {
        assert_eq!(fatigue_tier(0.0), "fresh");
        assert_eq!(fatigue_tier(29.99), "fresh");
        assert_eq!(fatigue_tier(30.0), "engaged");
        assert_eq!(fatigue_tier(59.99), "engaged");
        assert_eq!(fatigue_tier(60.0), "strained");
        assert_eq!(fatigue_tier(84.99), "strained");
        assert_eq!(fatigue_tier(85.0), "saturated");
        assert_eq!(
            fatigue_tier(150.0),
            "saturated",
            "out-of-range clamps to last tier"
        );
    }
}
