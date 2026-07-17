//! Maximal Marginal Relevance (MMR) diversity re-ranking.
//!
//! The session_bootstrap semantic page tends to be flooded by highly
//! homogeneous memories (e.g. several near-identical handoff summaries of the
//! same work stream): cosine ranking scores them all high, and the page spends
//! its line budget on redundancy. MMR greedily re-selects candidates to
//! balance relevance against novelty vs. what was already picked:
//!
//! ```text
//! MMR(d) = λ · relevance(d) − (1 − λ) · max_sim(d, selected)
//! ```
//!
//! Similarity is token-set Jaccard over lowercased text split on
//! non-alphanumeric boundaries — no embeddings needed, O(n²) on a page-sized
//! candidate set. **Known limitation:** the split is Unicode-alphanumeric, so
//! an unsegmented CJK run collapses into a single token; two Chinese sentences
//! differing by one clause can score 0 similarity. Acceptable for the current
//! page (keys/content are mostly ASCII-tokenized), noted here so nobody
//! mistakes it for real CJK segmentation.
//!
//! Pure functions only — zero sqlite/IO dependencies, callers pass data in.

use std::collections::HashSet;

/// Re-rank by MMR and return the new order as indices into `texts`.
///
/// `texts[i]` and `relevance[i]` describe candidate `i`; the returned vec is a
/// permutation of `0..texts.len()` in selection order. Relevance is scale
/// normalized internally (divided by max |relevance|), so any score scale
/// works (blend scores above 1.0 included). Deliberately **not** min-max: a
/// homogeneous page has tiny score gaps, and min-max would stretch them to the
/// full [0, 1] range, letting a near-duplicate 0.02 behind the top hit
/// out-rank the similarity penalty — the exact flooding case MMR is here for.
///
/// `lambda` is clamped to `[0, 1]`; `1.0` means pure relevance (descending
/// sort), `0.0` pure diversity. Ties break toward higher raw relevance, then
/// toward the earlier original index, so the function is deterministic.
///
/// Degenerate inputs return the identity order untouched: fewer than 3
/// candidates (callers pass relevance-sorted lists, and with ≤2 items there is
/// nothing to diversify), or a `relevance` slice whose length does not match
/// `texts`.
pub fn mmr_rerank_by_text(texts: &[&str], relevance: &[f64], lambda: f64) -> Vec<usize> {
    let n = texts.len();
    let identity: Vec<usize> = (0..n).collect();
    if n <= 2 || relevance.len() != n {
        return identity;
    }
    let lambda = lambda.clamp(0.0, 1.0);

    // Lowercase once, then tokenize each candidate once — Jaccard is queried
    // O(n²) times below.
    let lowered: Vec<String> = texts.iter().map(|t| t.to_lowercase()).collect();
    let token_sets: Vec<HashSet<&str>> = lowered.iter().map(|s| tokenize(s)).collect();

    // Scale-normalize relevance into [-1, 1] so λ trades off against a
    // similarity term of comparable magnitude while absolute score gaps keep
    // their meaning (see the function doc for why not min-max).
    let scale = relevance
        .iter()
        .fold(0.0_f64, |acc, r| acc.max(r.abs()))
        .max(f64::EPSILON);

    let mut selected: Vec<usize> = Vec::with_capacity(n);
    let mut remaining: Vec<usize> = identity;

    while !remaining.is_empty() {
        let mut best_pos = 0usize;
        let mut best_score = f64::NEG_INFINITY;
        for (pos, &cand) in remaining.iter().enumerate() {
            let rel = relevance[cand] / scale;
            let max_sim = selected
                .iter()
                .map(|&sel| jaccard_similarity(&token_sets[cand], &token_sets[sel]))
                .fold(0.0_f64, f64::max);
            let score = lambda * rel - (1.0 - lambda) * max_sim;
            let wins = score > best_score
                || (score == best_score && relevance[cand] > relevance[remaining[best_pos]]);
            if wins {
                best_score = score;
                best_pos = pos;
            }
        }
        selected.push(remaining.remove(best_pos));
    }
    selected
}

/// Token set for Jaccard: expects pre-lowercased input, splits on any
/// non-alphanumeric char (Unicode-aware — see module doc for the CJK caveat).
fn tokenize(text: &str) -> HashSet<&str> {
    text.split(|c: char| !c.is_alphanumeric())
        .filter(|t| !t.is_empty())
        .collect()
}

/// Jaccard similarity |A ∩ B| / |A ∪ B|. Two empty sets are identical (1.0);
/// one empty set shares nothing (0.0).
fn jaccard_similarity(a: &HashSet<&str>, b: &HashSet<&str>) -> f64 {
    if a.is_empty() && b.is_empty() {
        return 1.0;
    }
    if a.is_empty() || b.is_empty() {
        return 0.0;
    }
    let intersection = a.intersection(b).count();
    let union = a.len() + b.len() - intersection;
    intersection as f64 / union as f64
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn near_duplicates_demoted_diverse_promoted() {
        // Two near-duplicate handoff-ish texts at the top, one different text
        // just behind — MMR should pull the diverse one up to second place.
        let texts = [
            "session handoff: fixed warp ipc socket reconnect bug in bridge",
            "session handoff: fixed the warp ipc socket reconnect bug (bridge)",
            "error pattern: sqlite busy timeout on memory_save under load",
        ];
        let relevance = [1.0, 0.98, 0.95];
        let order = mmr_rerank_by_text(&texts, &relevance, 0.7);
        assert_eq!(order[0], 0, "top relevance stays first");
        assert_eq!(order[1], 2, "diverse text must beat the near-duplicate");
        assert_eq!(order[2], 1);
    }

    #[test]
    fn lambda_one_is_pure_relevance_sort() {
        // Deliberately unsorted relevance: λ=1.0 must reduce to a descending
        // relevance sort regardless of text similarity.
        let texts = ["alpha beta", "alpha beta", "gamma delta", "alpha beta"];
        let relevance = [0.2, 0.9, 0.5, 0.7];
        let order = mmr_rerank_by_text(&texts, &relevance, 1.0);
        assert_eq!(order, vec![1, 3, 2, 0]);
    }

    #[test]
    fn lambda_is_clamped() {
        let texts = [
            "one topic here",
            "another subject there",
            "third thing entirely",
        ];
        let relevance = [1.0, 0.9, 0.8];
        // λ > 1 clamps to 1.0 → pure relevance order.
        assert_eq!(
            mmr_rerank_by_text(&texts, &relevance, 7.5),
            mmr_rerank_by_text(&texts, &relevance, 1.0),
        );
        // λ < 0 clamps to 0.0 → pure diversity order.
        assert_eq!(
            mmr_rerank_by_text(&texts, &relevance, -3.0),
            mmr_rerank_by_text(&texts, &relevance, 0.0),
        );
    }

    #[test]
    fn two_or_fewer_is_identity() {
        let texts = ["same text", "same text"];
        // Even identical texts with inverted relevance stay in input order.
        assert_eq!(mmr_rerank_by_text(&texts, &[0.1, 0.9], 0.7), vec![0, 1]);
    }

    #[test]
    fn empty_and_single_do_not_panic() {
        let none: [&str; 0] = [];
        assert!(mmr_rerank_by_text(&none, &[], 0.7).is_empty());
        assert_eq!(mmr_rerank_by_text(&["only"], &[1.0], 0.7), vec![0]);
        // Empty-string texts among real ones must not panic either.
        let texts = ["", "", "real content here"];
        let order = mmr_rerank_by_text(&texts, &[1.0, 0.9, 0.8], 0.7);
        assert_eq!(order.len(), 3);
    }

    #[test]
    fn mismatched_relevance_len_is_identity() {
        let texts = ["a b", "c d", "e f"];
        assert_eq!(mmr_rerank_by_text(&texts, &[1.0], 0.7), vec![0, 1, 2]);
    }

    #[test]
    fn output_is_permutation() {
        let texts = ["one", "two", "three", "four", "five"];
        let relevance = [0.9, 0.8, 0.7, 0.6, 0.5];
        let mut order = mmr_rerank_by_text(&texts, &relevance, 0.4);
        order.sort_unstable();
        assert_eq!(order, vec![0, 1, 2, 3, 4]);
    }

    #[test]
    fn jaccard_edges() {
        let a: HashSet<&str> = ["rust", "async"].into();
        let b: HashSet<&str> = ["rust", "web"].into();
        let empty: HashSet<&str> = HashSet::new();
        // {rust} / {rust, async, web} = 1/3.
        assert!((jaccard_similarity(&a, &b) - 1.0 / 3.0).abs() < 1e-12);
        assert!((jaccard_similarity(&a, &a) - 1.0).abs() < 1e-12);
        assert!((jaccard_similarity(&empty, &empty) - 1.0).abs() < 1e-12);
        assert!(jaccard_similarity(&a, &empty).abs() < 1e-12);
    }
}
