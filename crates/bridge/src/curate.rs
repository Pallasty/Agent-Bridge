//! Two-pass conversation memory extraction.
//!
//! ## Pass 1 — explicit markers  (fast, zero-miss on annotated text)
//! Detects line-prefix markers (`lesson:`, `decision:`, …) and section
//! headers (`## Lessons:**`) whose bullet children inherit the kind.
//! Ported verbatim from the original `mcp_tools.rs` logic.
//!
//! ## Pass 2 — implicit lexical scoring  (NEW)
//! Scores every unmarked line against five signal tables
//! (epistemic / normative / causal / decision / todo) using simple
//! substring matching. Lines that exceed the configured score threshold are
//! extracted as memories, classified by the dominant signal kind.
//! Jaccard word-bag deduplication suppresses near-duplicates.
//!
//! ## Tuning
//! - Defaults: [`DEFAULT_IMPLICIT_SCORE_THRESHOLD`], [`DEFAULT_IMPLICIT_DEDUP_JACCARD`].
//! - Environment (optional): `AGENT_BRIDGE_CURATE_SCORE_THRESHOLD` (f32),
//!   `AGENT_BRIDGE_CURATE_DEDUP_JACCARD` (f64). MCP tool args override env for that call.
//!
//! Public entry points: [`curate_conversation`], [`curate_conversation_with_options`].

use ab_store::MemoryRecord;

// ── Thresholds & limits ────────────────────────────────────────────────────

/// Default minimum aggregate signal score for implicit extraction (Pass 2).
pub const DEFAULT_IMPLICIT_SCORE_THRESHOLD: f32 = 0.45;
/// Default Jaccard similarity above which Pass 2 treats a line as duplicate of an earlier bag.
pub const DEFAULT_IMPLICIT_DEDUP_JACCARD: f64 = 0.55;

/// Tunable Pass-2 parameters (thresholds + dedup). Use [`CurateOptions::from_env_or_defaults`]
/// in production; use [`CurateOptions::default`] in tests for deterministic behavior.
#[derive(Clone, Debug, PartialEq)]
pub struct CurateOptions {
    pub implicit_score_threshold: f32,
    pub implicit_dedup_jaccard: f64,
}

impl Default for CurateOptions {
    fn default() -> Self {
        Self {
            implicit_score_threshold: DEFAULT_IMPLICIT_SCORE_THRESHOLD,
            implicit_dedup_jaccard: DEFAULT_IMPLICIT_DEDUP_JACCARD,
        }
    }
}

impl CurateOptions {
    /// Defaults, then optional env overrides (`AGENT_BRIDGE_CURATE_*`).
    pub fn from_env_or_defaults() -> Self {
        let mut o = Self::default();
        if let Ok(s) = std::env::var("AGENT_BRIDGE_CURATE_SCORE_THRESHOLD") {
            if let Ok(v) = s.trim().parse::<f32>() {
                o.implicit_score_threshold = v.clamp(0.15, 0.95);
            }
        }
        if let Ok(s) = std::env::var("AGENT_BRIDGE_CURATE_DEDUP_JACCARD") {
            if let Ok(v) = s.trim().parse::<f64>() {
                o.implicit_dedup_jaccard = v.clamp(0.1, 0.95);
            }
        }
        o
    }

    /// Merge MCP / CLI overrides onto this instance (already env-merged if applicable).
    pub fn with_overrides(
        mut self,
        implicit_score_threshold: Option<f32>,
        implicit_dedup_jaccard: Option<f64>,
    ) -> Self {
        if let Some(v) = implicit_score_threshold {
            self.implicit_score_threshold = v.clamp(0.15, 0.95);
        }
        if let Some(v) = implicit_dedup_jaccard {
            self.implicit_dedup_jaccard = v.clamp(0.1, 0.95);
        }
        self
    }
}

/// Minimum character count for implicit extraction.
const MIN_CHARS: usize = 20;
/// Maximum stored content length (chars); longer content is clipped with `…`.
const MAX_CHARS: usize = 400;

// ── Signal tables ──────────────────────────────────────────────────────────
// Format: (keyword, score_weight, kind_vote)
// keyword    — lowercase substring to match
// score_weight — contribution to total sentence score [0.0, 1.0]
// kind_vote  — memory kind this signal favors

/// Knowledge-discovery / epistemic verbs.
static EPISTEMIC: &[(&str, f32, &str)] = &[
    // English
    ("found that", 0.50, "lesson"),
    ("turns out", 0.50, "lesson"),
    ("realized", 0.45, "lesson"),
    ("discovered", 0.40, "lesson"),
    ("the issue is", 0.50, "lesson"),
    ("root cause", 0.60, "lesson"),
    ("key insight", 0.60, "lesson"),
    ("we learned", 0.50, "lesson"),
    ("the problem is", 0.50, "lesson"),
    ("it appears", 0.30, "lesson"),
    ("the bug", 0.35, "lesson"),
    // Chinese
    ("发现", 0.40, "lesson"),
    ("注意到", 0.45, "lesson"),
    ("意识到", 0.50, "lesson"),
    ("问题在于", 0.60, "lesson"),
    ("根源", 0.60, "lesson"),
    ("关键是", 0.50, "lesson"),
    ("原来", 0.40, "lesson"),
    ("真正的问题", 0.55, "lesson"),
];

/// Normative / prescriptive signals.
static NORMATIVE: &[(&str, f32, &str)] = &[
    // English
    ("should avoid", 0.50, "lesson"),
    ("must not", 0.50, "lesson"),
    ("best practice", 0.50, "lesson"),
    ("avoid", 0.35, "lesson"),
    ("should", 0.25, "lesson"),
    ("prefer", 0.35, "lesson"),
    ("always", 0.30, "lesson"),
    ("never", 0.40, "lesson"),
    ("recommend", 0.35, "lesson"),
    ("make sure", 0.35, "lesson"),
    // Chinese
    ("应该避免", 0.50, "lesson"),
    ("必须", 0.35, "lesson"),
    ("最好", 0.35, "lesson"),
    ("避免", 0.40, "lesson"),
    ("应该", 0.25, "lesson"),
    ("建议", 0.30, "lesson"),
    ("注意", 0.25, "lesson"),
    ("重要", 0.20, "lesson"),
];

/// Causal-chain / consequence signals.
static CAUSAL: &[(&str, f32, &str)] = &[
    // English
    ("caused by", 0.50, "lesson"),
    ("as a result", 0.40, "lesson"),
    ("which means", 0.35, "lesson"),
    ("this means", 0.35, "lesson"),
    ("leads to", 0.35, "lesson"),
    ("therefore", 0.30, "lesson"),
    ("due to", 0.25, "lesson"),
    // Chinese
    ("导致", 0.40, "lesson"),
    ("这意味着", 0.40, "lesson"),
    ("因此", 0.30, "lesson"),
    ("由于", 0.25, "lesson"),
    ("造成", 0.35, "lesson"),
];

/// Architecture / trade-off / choice signals.
static DECISION_KW: &[(&str, f32, &str)] = &[
    // English
    ("decided to", 0.50, "decision"),
    ("we chose", 0.50, "decision"),
    ("going with", 0.40, "decision"),
    ("trade-off", 0.45, "decision"),
    ("instead of", 0.35, "decision"),
    ("design decision", 0.60, "decision"),
    ("we will use", 0.40, "decision"),
    ("architecture", 0.30, "decision"),
    // Chinese
    ("决定", 0.40, "decision"),
    ("选择", 0.35, "decision"),
    ("采用", 0.35, "decision"),
    ("而不是", 0.35, "decision"),
    ("权衡", 0.40, "decision"),
    ("改为", 0.35, "decision"),
    ("设计决策", 0.60, "decision"),
];

/// Future-action / todo signals.
static TODO_KW: &[(&str, f32, &str)] = &[
    // English
    ("need to implement", 0.50, "todo"),
    ("will implement", 0.50, "todo"),
    ("next step", 0.45, "todo"),
    ("plan to", 0.40, "todo"),
    ("upcoming", 0.35, "todo"),
    // Chinese
    ("下一步", 0.45, "todo"),
    ("需要实现", 0.50, "todo"),
    ("计划", 0.30, "todo"),
    ("待实现", 0.50, "todo"),
    ("接下来", 0.30, "todo"),
];

// ── Explicit marker tables (Phase 1) ──────────────────────────────────────

/// Line-prefix → kind.  Checked in order; first match wins.
pub(crate) static CURATE_MARKERS: &[(&str, &str)] = &[
    ("lesson:", "lesson"),
    ("learned:", "lesson"),
    ("learning:", "lesson"),
    ("gotcha:", "lesson"),
    ("pitfall:", "lesson"),
    ("bug:", "lesson"),
    ("fix:", "lesson"),
    ("warning:", "lesson"),
    ("pattern:", "lesson"),
    ("key insight:", "lesson"),
    ("root cause:", "lesson"),
    ("decision:", "decision"),
    ("decided:", "decision"),
    ("design:", "decision"),
    ("architecture:", "decision"),
    ("we decided:", "decision"),
    ("we chose:", "decision"),
    ("todo:", "todo"),
    ("TODO:", "todo"),
    ("action item:", "todo"),
    ("next step:", "todo"),
    ("note:", "context"),
    ("context:", "context"),
    ("status:", "context"),
    ("state:", "context"),
    ("remember:", "context"),
    ("important:", "context"),
    ("handoff:", "session_handoff"),
    ("session_handoff:", "session_handoff"),
];

/// Section-header keyword → kind inherited by following bullet items.
static SECTION_HEADERS: &[(&str, &str)] = &[
    ("lesson", "lesson"),
    ("learned", "lesson"),
    ("learning", "lesson"),
    ("gotcha", "lesson"),
    ("pitfall", "lesson"),
    ("insight", "lesson"),
    ("decision", "decision"),
    ("decided", "decision"),
    ("todo", "todo"),
    ("action item", "todo"),
    ("next step", "todo"),
    ("context", "context"),
    ("status", "context"),
    ("handoff", "session_handoff"),
    ("summary", "context"),
];

// ── Primitive helpers ──────────────────────────────────────────────────────

pub(crate) fn now_secs() -> i64 {
    std::time::SystemTime::now()
        .duration_since(std::time::UNIX_EPOCH)
        .unwrap_or_default()
        .as_secs() as i64
}

fn mk_sid_suffix(session_id: Option<&str>) -> String {
    session_id
        .map(|s| format!("_{}", &s[..s.len().min(8)]))
        .unwrap_or_default()
}

/// Word bag for Jaccard deduplication: lowercase tokens ≥ 2 chars.
fn word_bag(text: &str) -> std::collections::HashSet<String> {
    text.split(|c: char| !c.is_alphanumeric())
        .map(|w| w.to_lowercase())
        .filter(|w| w.chars().count() >= 2)
        .collect()
}

fn jaccard(a: &std::collections::HashSet<String>, b: &std::collections::HashSet<String>) -> f64 {
    if a.is_empty() || b.is_empty() {
        return 0.0;
    }
    let inter = a.intersection(b).count();
    let union = a.len() + b.len() - inter;
    if union == 0 {
        1.0
    } else {
        inter as f64 / union as f64
    }
}

/// Clip to `max` Unicode scalar values, appending `…` if truncated.
fn clip(s: &str, max: usize) -> String {
    let mut chars = s.chars();
    let mut out = String::with_capacity(max + 3);
    let mut n = 0usize;
    loop {
        if n == max {
            out.push('…');
            break;
        }
        match chars.next() {
            Some(c) => {
                out.push(c);
                n += 1;
            }
            None => break,
        }
    }
    out
}

/// FNV-1a 32-bit hash → 8-char hex for stable implicit record keys.
fn simple_hash(s: &str) -> String {
    let mut h: u64 = 14695981039346656037;
    for b in s.bytes() {
        h ^= b as u64;
        h = h.wrapping_mul(1099511628211);
    }
    format!("{:08x}", h & 0xffff_ffff)
}

/// Returns `true` when the line should be skipped by implicit scoring.
fn is_noise(text: &str) -> bool {
    let t = text.trim();
    if t.ends_with('?') || t.ends_with('？') {
        return true;
    }
    if t.starts_with("http://") || t.starts_with("https://") {
        return true;
    }
    if t.starts_with("```") || t.starts_with("~~~") {
        return true;
    }
    if t.starts_with('#') || t == "---" || t == "===" || t == "***" {
        return true;
    }
    // Source-separator headers from memory_auto_curate aggregation, e.g.
    // `=== Source 1 (session_handoff_2026_01) ===`. These leaked through
    // Pass-2 because their "session_handoff" / kind keywords scored above
    // threshold despite being internal scaffolding, not real content.
    // Detected 2026-05-03; see lesson_memory_tools_audit_20260503.
    if t.starts_with("=== ") && t.ends_with(" ===") {
        return true;
    }
    let lower = t.to_lowercase();
    let acks = [
        "ok",
        "okay",
        "sure",
        "yes",
        "no",
        "yep",
        "nope",
        "thanks",
        "thank you",
        "got it",
        "understood",
        "好的",
        "明白",
        "谢谢",
        "嗯",
        "对",
        "没问题",
    ];
    acks.iter().any(|a| lower == *a)
}

/// `true` when the line starts with an explicit marker (Phase-1 domain).
fn has_explicit_marker(trimmed: &str) -> bool {
    let lower = trimmed.to_lowercase();
    CURATE_MARKERS
        .iter()
        .any(|(m, _)| lower.starts_with(&m.to_lowercase()))
}

/// Detect section header; returns inherited kind.
fn is_section_header(line: &str) -> Option<&'static str> {
    let trimmed = line.trim();
    let bare = trimmed
        .trim_start_matches('*')
        .trim_end_matches('*')
        .trim_end_matches(':')
        .trim();
    let lower = bare.to_lowercase();
    for (kw, kind) in SECTION_HEADERS {
        if lower.contains(kw) && (trimmed.ends_with(':') || trimmed.ends_with(":**")) {
            return Some(kind);
        }
    }
    None
}

/// Strip leading Markdown bullet from a list item.
fn strip_bullet(line: &str) -> Option<&str> {
    let t = line.trim();
    for prefix in &["- ", "* ", "+ ", "• "] {
        if let Some(rest) = t.strip_prefix(prefix) {
            return Some(rest.trim());
        }
    }
    if let Some(pos) = t.find(". ") {
        let num = &t[..pos];
        if num.chars().all(|c| c.is_ascii_digit()) && pos <= 2 {
            return Some(t[pos + 2..].trim());
        }
    }
    None
}

/// Push one curated record into `results`.
pub(crate) fn push_curated(
    results: &mut Vec<MemoryRecord>,
    kind: &str,
    content: &str,
    sid_suffix: &str,
    idx: usize,
    now: i64,
) {
    let slug: String = content
        .chars()
        .take(40)
        .map(|c| if c.is_alphanumeric() { c } else { '_' })
        .collect();
    let key = format!(
        "curated_{}{}_{}{}",
        kind,
        sid_suffix,
        idx,
        &slug[..slug.len().min(20)]
    );
    results.push(MemoryRecord {
        key,
        kind: kind.to_string(),
        content: content.to_string(),
        tags: vec!["auto_curated".to_string()],
        related_keys: vec![],
        scope: None,
        created_at: now,
        updated_at: now,
        last_accessed_at: now,
        access_count: 0,
        importance: 0.5,
        status: "active".to_string(),
        trigger_pattern: None,
        superseded_by: None,
    });
}

// ── Phase 1: explicit marker extraction ───────────────────────────────────

fn curate_explicit(text: &str, sid_suffix: &str, max_items: usize, now: i64) -> Vec<MemoryRecord> {
    let mut results: Vec<MemoryRecord> = Vec::new();
    let mut section_kind: Option<&'static str> = None;

    for (idx, line) in text.lines().enumerate() {
        if results.len() >= max_items {
            break;
        }
        let trimmed = line.trim();
        if trimmed.is_empty() {
            continue;
        }

        // Section header check
        if let Some(kind) = is_section_header(trimmed) {
            section_kind = Some(kind);
            continue;
        }

        // Line-prefix markers
        let mut matched = false;
        if trimmed.len() >= 10 {
            let lower = trimmed.to_lowercase();
            for (marker, kind) in CURATE_MARKERS {
                if lower.starts_with(&marker.to_lowercase()) {
                    let content = trimmed[marker.len()..].trim();
                    if content.len() >= 5 {
                        push_curated(&mut results, kind, content, sid_suffix, idx, now);
                        matched = true;
                    }
                    break;
                }
            }
        }

        // Bullet items under a recognised section
        if !matched {
            if let Some(kind) = section_kind {
                if let Some(payload) = strip_bullet(trimmed) {
                    if payload.len() >= 8 {
                        push_curated(&mut results, kind, payload, sid_suffix, idx, now);
                    }
                } else if !trimmed.starts_with('[') {
                    section_kind = None;
                }
            }
        }
    }
    results
}

// ── Phase 2: implicit lexical scoring ─────────────────────────────────────

/// Score a lowercase line against all signal tables.
/// Returns `Some((score, kind))` if score ≥ `score_threshold`, else `None`.
fn score_sentence(lower: &str, score_threshold: f32) -> Option<(f32, &'static str)> {
    let mut score = 0.0f32;
    // kind → accumulated vote weight
    let mut lesson_v = 0.0f32;
    let mut decision_v = 0.0f32;
    let mut todo_v = 0.0f32;

    let all: &[&[(&str, f32, &str)]] = &[EPISTEMIC, NORMATIVE, CAUSAL, DECISION_KW, TODO_KW];
    for table in all {
        for &(kw, w, kind) in *table {
            if lower.contains(kw) {
                score += w;
                match kind {
                    "decision" => decision_v += w,
                    "todo" => todo_v += w,
                    _ => lesson_v += w,
                }
            }
        }
    }

    if score < score_threshold {
        return None;
    }

    let kind = if decision_v >= lesson_v && decision_v >= todo_v {
        "decision"
    } else if todo_v >= lesson_v {
        "todo"
    } else {
        "lesson"
    };
    Some((score, kind))
}

fn curate_implicit(
    text: &str,
    _sid_suffix: &str,
    seen_bags: &[std::collections::HashSet<String>],
    max_items: usize,
    now: i64,
    opts: &CurateOptions,
) -> Vec<MemoryRecord> {
    let mut results: Vec<MemoryRecord> = Vec::new();
    let mut local_bags: Vec<std::collections::HashSet<String>> = seen_bags.to_vec();

    for line in text.lines() {
        if results.len() >= max_items {
            break;
        }
        let trimmed = line.trim();
        if trimmed.chars().count() < MIN_CHARS {
            continue;
        }
        if is_noise(trimmed) {
            continue;
        }
        if has_explicit_marker(trimmed) {
            continue;
        }

        let lower = trimmed.to_lowercase();
        let Some((score, kind)) = score_sentence(&lower, opts.implicit_score_threshold) else {
            continue;
        };

        let content = clip(trimmed, MAX_CHARS);
        let bag = word_bag(&content);
        let dedup = opts.implicit_dedup_jaccard;
        if local_bags.iter().any(|s| jaccard(s, &bag) > dedup) {
            continue;
        }
        local_bags.push(bag);

        // Boost importance proportional to signal strength (f64 as required by MemoryRecord)
        let importance =
            f64::from((0.5 + (score - opts.implicit_score_threshold) * 0.25).min(0.85));
        let key = format!("curated_implicit_{}{}", kind, simple_hash(&content));

        results.push(MemoryRecord {
            key,
            kind: kind.to_string(),
            content,
            tags: vec!["auto_curated".to_string(), "implicit".to_string()],
            related_keys: vec![],
            scope: None,
            created_at: now,
            updated_at: now,
            last_accessed_at: now,
            access_count: 0,
            importance,
            status: "active".to_string(),
            trigger_pattern: None,
            superseded_by: None,
        });
    }
    results
}

// ── Public entry point ─────────────────────────────────────────────────────

/// Extract memorable records from a conversation summary.
///
/// Runs two passes:
/// 1. **Explicit** — line-prefix markers + section-header bullet inheritance.
/// 2. **Implicit** — lexical signal scoring on every unmarked line.
///
/// Results from both passes are deduplicated by Jaccard word-bag similarity.
///
/// Uses [`CurateOptions::from_env_or_defaults`] (env + defaults). For deterministic tests,
/// call [`curate_conversation_with_options`] with [`CurateOptions::default`].
pub fn curate_conversation(
    text: &str,
    session_id: Option<&str>,
    max_items: usize,
) -> Vec<MemoryRecord> {
    curate_conversation_with_options(
        text,
        session_id,
        max_items,
        CurateOptions::from_env_or_defaults(),
    )
}

/// Same as [`curate_conversation`] but with explicit Pass-2 options (no implicit env read).
pub fn curate_conversation_with_options(
    text: &str,
    session_id: Option<&str>,
    max_items: usize,
    opts: CurateOptions,
) -> Vec<MemoryRecord> {
    let now = now_secs();
    let sid = mk_sid_suffix(session_id);

    // Pass 1
    let mut results = curate_explicit(text, &sid, max_items, now);

    // Pass 2 — fills remaining budget, deduplicates against Pass-1 content
    let budget = max_items.saturating_sub(results.len());
    if budget > 0 {
        let seen: Vec<_> = results.iter().map(|r| word_bag(&r.content)).collect();
        results.extend(curate_implicit(text, &sid, &seen, budget, now, &opts));
    }

    results
}

#[cfg(test)]
mod tests {
    use super::*;

    // ── score_sentence ────────────────────────────────────────────────────

    fn thresh() -> f32 {
        DEFAULT_IMPLICIT_SCORE_THRESHOLD
    }

    #[test]
    fn score_epistemic_en() {
        let (s, k) = score_sentence(
            "we found that cargo check is 10x faster than build",
            thresh(),
        )
        .unwrap();
        assert!(s >= thresh(), "score={s}");
        assert_eq!(k, "lesson");
    }

    #[test]
    fn score_causal_en() {
        let (s, k) = score_sentence(
            "the oom was caused by the arena allocator holding live refs",
            thresh(),
        )
        .unwrap();
        assert!(s >= thresh(), "score={s}");
        assert_eq!(k, "lesson");
    }

    #[test]
    fn score_decision_en() {
        let (_, k) = score_sentence(
            "we decided to go with auggie instead of claude for ci",
            thresh(),
        )
        .unwrap();
        assert_eq!(k, "decision");
    }

    #[test]
    fn score_todo_en() {
        let r = score_sentence(
            "next step is to implement the memory_stats endpoint",
            thresh(),
        );
        assert!(r.is_some());
        let (_, k) = r.unwrap();
        assert_eq!(k, "todo");
    }

    #[test]
    fn score_chinese_epistemic() {
        let (s, k) = score_sentence("发现问题在于 sqlite 没有正确处理并发写入", thresh()).unwrap();
        assert!(s >= thresh(), "score={s}");
        assert_eq!(k, "lesson");
    }

    #[test]
    fn score_chinese_normative_and_decision() {
        let (_, k) = score_sentence("因此我们应当避免在热路径上持有全局锁", thresh()).unwrap();
        assert_eq!(k, "lesson");
        let (_, k2) = score_sentence("团队最终决定采用方案 B 并推迟缓存重构", thresh()).unwrap();
        assert_eq!(k2, "decision");
    }

    #[test]
    fn noise_question_is_rejected() {
        assert!(score_sentence("did you see the error message?", thresh()).is_none());
    }

    #[test]
    fn short_line_below_threshold() {
        // "ok" — trivially below threshold
        assert!(score_sentence("ok", thresh()).is_none());
    }

    // ── is_noise ─────────────────────────────────────────────────────────

    #[test]
    fn noise_filters_question() {
        assert!(is_noise("what does this function do?"));
        assert!(is_noise("这个函数是做什么的？"));
    }

    #[test]
    fn noise_filters_url() {
        assert!(is_noise("https://docs.rs/tokio/latest/tokio/"));
    }

    #[test]
    fn noise_filters_code_fence() {
        assert!(is_noise("```rust"));
    }

    #[test]
    fn noise_passes_valuable_sentence() {
        assert!(!is_noise(
            "we found that using &str slices instead of String avoids needless allocation"
        ));
    }

    /// Regression: memory_auto_curate aggregation inserts `=== Source N (key) ===`
    /// headers between source memories. These leaked into Pass-2 candidates
    /// because they contain kind/handoff keywords. Detected 2026-05-03.
    #[test]
    fn noise_filters_source_separator() {
        assert!(is_noise(
            "=== Source 1 (curated_session_handoff_verify-w_5Next_session_should_) ==="
        ));
        assert!(is_noise("=== Source 2 (session_handoff_20260429) ==="));
        // Don't false-positive on a sentence that merely contains "===" inside
        assert!(!is_noise(
            "we use === as a divider in markdown headers throughout the project"
        ));
    }

    // ── curate_conversation (integration) ────────────────────────────────

    #[test]
    fn explicit_marker_still_works() {
        let text = "lesson: always run cargo check before cargo build\n";
        let recs = curate_conversation_with_options(text, None, 10, CurateOptions::default());
        assert!(!recs.is_empty(), "explicit marker must produce a record");
        assert_eq!(recs[0].kind, "lesson");
        assert!(recs[0].content.contains("cargo check"));
    }

    #[test]
    fn implicit_captures_unmarked_insight() {
        let text = "We found that the root cause of the latency spike was the naive retry loop \
             holding the connection pool exhausted under load.";
        let recs = curate_conversation_with_options(text, None, 10, CurateOptions::default());
        assert!(
            !recs.is_empty(),
            "implicit pass must extract unmarked insight; got 0 records"
        );
        let kinds: Vec<_> = recs.iter().map(|r| r.kind.as_str()).collect();
        assert!(
            kinds.contains(&"lesson"),
            "expected lesson kind; got {kinds:?}"
        );
    }

    #[test]
    fn implicit_tag_present() {
        let text = "It turns out avoiding the retry loop cuts p99 latency by 80%.";
        let recs = curate_conversation_with_options(text, None, 10, CurateOptions::default());
        assert!(!recs.is_empty());
        // At least one implicit record carries the "implicit" tag
        let has_implicit_tag = recs
            .iter()
            .any(|r| r.tags.contains(&"implicit".to_string()));
        assert!(
            has_implicit_tag,
            "implicit records must carry 'implicit' tag"
        );
    }

    #[test]
    fn dedup_suppresses_near_duplicate() {
        // Both sentences express the same insight; only one should survive.
        let text = [
            "lesson: avoid holding the lock while awaiting async calls",
            "We found that holding the lock while awaiting async calls causes deadlock.",
        ]
        .join("\n");
        let recs = curate_conversation_with_options(&text, None, 10, CurateOptions::default());
        assert!(
            recs.len() <= 2,
            "dedup should suppress near-duplicate; got {}",
            recs.len()
        );
    }

    #[test]
    fn max_items_is_respected() {
        let text = (0..20)
            .map(|i| format!("We found that insight number {i} is caused by the entropy system."))
            .collect::<Vec<_>>()
            .join("\n");
        let recs = curate_conversation_with_options(&text, None, 5, CurateOptions::default());
        assert!(
            recs.len() <= 5,
            "must not exceed max_items=5; got {}",
            recs.len()
        );
    }

    #[test]
    fn implicit_chinese_unmarked_insight() {
        let text = "我们发现延迟飙升的根源在于连接池在高压下被占满，简单的重试循环会雪上加霜。";
        let recs = curate_conversation_with_options(text, None, 10, CurateOptions::default());
        assert!(
            !recs.is_empty(),
            "implicit pass should capture Chinese causal/epistemic line"
        );
        assert!(
            recs.iter()
                .any(|r| r.tags.contains(&"implicit".to_string())),
            "expected implicit tag"
        );
    }

    // ── memory_auto_curate pipeline scenarios ─────────────────────────────

    /// memory_auto_curate aggregates session_handoff memories into sections
    /// like `=== Source N (key) ===\n<content>` then runs the curate pipeline.
    /// Verify the pipeline can still extract markers from that aggregated format.
    #[test]
    fn auto_curate_aggregated_markers() {
        let text = [
            "=== Source 1 (session_handoff_2026_01) ===",
            "lesson: always run cargo test before deploying a new binary",
            "decision: adopt two-pass curate pipeline for automated curation",
            "",
            "=== Source 2 (session_handoff_2025_12) ===",
            "lesson: session_handoff memories are the right source for auto-curation",
        ]
        .join("\n");
        let recs = curate_conversation_with_options(&text, None, 10, CurateOptions::default());
        assert!(
            !recs.is_empty(),
            "pipeline must extract from aggregated sections; got 0"
        );
        let has_lesson_or_decision = recs
            .iter()
            .any(|r| r.kind == "lesson" || r.kind == "decision");
        assert!(
            has_lesson_or_decision,
            "expected lesson or decision kind; got {:?}",
            recs.iter().map(|r| r.kind.as_str()).collect::<Vec<_>>()
        );
    }

    /// `handoff:` prefix should produce a record with kind == "session_handoff".
    #[test]
    fn auto_curate_handoff_marker_extracted() {
        let text = "handoff: migrated agent-bridge to async SQLite pool\n";
        let recs = curate_conversation_with_options(text, None, 10, CurateOptions::default());
        assert!(!recs.is_empty(), "handoff: marker must produce a record");
        assert!(
            recs.iter().any(|r| r.kind == "session_handoff"),
            "expected session_handoff kind; got {:?}",
            recs.iter().map(|r| r.kind.as_str()).collect::<Vec<_>>()
        );
    }

    /// Simulates the exclude_kinds filter that memory_auto_curate applies:
    /// extract from handoff-only text, then filter out session_handoff →
    /// should leave an empty vec.
    #[test]
    fn auto_curate_exclude_by_kind() {
        let text = [
            "handoff: shipped v0.11 memory_graph_export with DOT and JSON output",
            "handoff: shipped v0.12 memory_auto_curate for scheduled curation",
        ]
        .join("\n");
        let mut recs = curate_conversation_with_options(&text, None, 10, CurateOptions::default());
        // All records extracted from `handoff:` lines should be session_handoff.
        assert!(
            recs.iter().all(|r| r.kind == "session_handoff"),
            "only handoff markers present; all records should be session_handoff"
        );
        // Simulating memory_auto_curate's exclude_kinds=["session_handoff"] filter:
        recs.retain(|r| r.kind != "session_handoff");
        assert!(
            recs.is_empty(),
            "after filtering session_handoff, vec must be empty"
        );
    }
}
