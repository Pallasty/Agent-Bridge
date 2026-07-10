//! BioCortex retrieval relevance-lift eval — the honest ruler.
//!
//! Read-only measurement instrument that answers the question the existing
//! `biocortex_retrieval_opt_in_*` tools deliberately CANNOT: does the BioCortex
//! biomimetic side-signal reorder actually lift the rank of the *relevant*
//! memories, or does it just shuffle the order around?
//!
//! `_batch_diagnostics` reports **hashed movement** (how much the order moved,
//! coverage, latency) but no relevance labels — so it cannot say whether the
//! right answer rose. This module supplies the missing yardstick.
//!
//! It is **pure**: it operates on rankings (ordered lists of keys) plus a
//! relevant set, and computes rank-of-source / MRR / recall@k for the baseline
//! ordering vs the reordered ordering, then a lift delta. No I/O, no store, no
//! shelling out — so the ruler itself is unit-testable in isolation.
//!
//! Anti-laundering contract: the verdict reports regressions **as
//! regressions**. A reorder that pushes relevant memories DOWN yields a
//! NEGATIVE lift — never clamped to zero, never relabeled "no change". And the
//! self-retrieval labels are a PROXY (the query is derived FROM the target), so
//! the verdict carries that caveat and never claims proven real-recall lift.

use std::collections::BTreeSet;

/// Standard recall@k cutoffs reported by the eval.
pub const RECALL_K_CUTOFFS: [usize; 4] = [1, 3, 5, 10];

/// Below this magnitude an MRR delta counts as "no change" (float noise guard).
const LIFT_EPS: f64 = 1e-6;

/// 1-based rank of `key` in `ranking` (position 1 = top). `None` if absent.
pub fn rank_of(ranking: &[String], key: &str) -> Option<usize> {
    ranking.iter().position(|k| k == key).map(|idx| idx + 1)
}

/// Reciprocal rank of the FIRST relevant key in `ranking`. `0.0` when no
/// relevant key appears anywhere in the ranking.
pub fn reciprocal_rank(ranking: &[String], relevant: &BTreeSet<String>) -> f64 {
    ranking
        .iter()
        .position(|k| relevant.contains(k))
        .map(|idx| 1.0 / (idx as f64 + 1.0))
        .unwrap_or(0.0)
}

/// recall@k = (# distinct relevant keys appearing in the top-k of `ranking`) /
/// |relevant|. Returns `0.0` when `relevant` is empty (no signal to measure).
pub fn recall_at(ranking: &[String], relevant: &BTreeSet<String>, k: usize) -> f64 {
    if relevant.is_empty() {
        return 0.0;
    }
    let hit = ranking
        .iter()
        .take(k)
        .filter(|key| relevant.contains(*key))
        .collect::<BTreeSet<_>>()
        .len();
    hit as f64 / relevant.len() as f64
}

/// Metrics for a single ranking against one sample's relevant set.
#[derive(Debug, Clone, PartialEq)]
pub struct RankingMetrics {
    /// 1-based rank of the primary source key (`None` = absent from this ranking).
    pub rank_of_source: Option<usize>,
    /// Reciprocal rank of the first relevant key (0.0 if none present).
    pub reciprocal_rank: f64,
    /// recall@k for each cutoff in [`RECALL_K_CUTOFFS`] (parallel order).
    pub recall_at: Vec<(usize, f64)>,
}

/// Compute metrics for one ranking. `source_key` is the primary target;
/// `relevant` is the full relevant set (source ∪ linked neighbours).
pub fn ranking_metrics(
    ranking: &[String],
    source_key: &str,
    relevant: &BTreeSet<String>,
) -> RankingMetrics {
    RankingMetrics {
        rank_of_source: rank_of(ranking, source_key),
        reciprocal_rank: reciprocal_rank(ranking, relevant),
        recall_at: RECALL_K_CUTOFFS
            .iter()
            .map(|&k| (k, recall_at(ranking, relevant, k)))
            .collect(),
    }
}

/// Direction of a single sample's reorder effect (keyed on reciprocal-rank delta).
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum LiftDirection {
    Improved,
    Worsened,
    Unchanged,
}

impl LiftDirection {
    pub fn as_str(self) -> &'static str {
        match self {
            LiftDirection::Improved => "improved",
            LiftDirection::Worsened => "worsened",
            LiftDirection::Unchanged => "unchanged",
        }
    }
}

/// Per-sample comparison of baseline vs reordered rankings.
#[derive(Debug, Clone)]
pub struct SampleLift {
    pub baseline: RankingMetrics,
    pub reordered: RankingMetrics,
    /// `reordered.reciprocal_rank - baseline.reciprocal_rank`. Positive = lift.
    pub rr_delta: f64,
    /// Signed change in source rank: `baseline_rank - reordered_rank`
    /// (positive = source moved UP / better). `None` if source absent in either.
    pub rank_delta: Option<i64>,
    pub direction: LiftDirection,
    /// Did the reorder actually change the ordering at all?
    pub order_changed: bool,
}

/// Compare a baseline ranking against the reordered ranking for one sample.
pub fn sample_lift(
    baseline_ranking: &[String],
    reordered_ranking: &[String],
    source_key: &str,
    relevant: &BTreeSet<String>,
) -> SampleLift {
    let baseline = ranking_metrics(baseline_ranking, source_key, relevant);
    let reordered = ranking_metrics(reordered_ranking, source_key, relevant);
    let rr_delta = reordered.reciprocal_rank - baseline.reciprocal_rank;
    let rank_delta = match (baseline.rank_of_source, reordered.rank_of_source) {
        (Some(b), Some(r)) => Some(b as i64 - r as i64),
        _ => None,
    };
    let direction = if rr_delta > LIFT_EPS {
        LiftDirection::Improved
    } else if rr_delta < -LIFT_EPS {
        LiftDirection::Worsened
    } else {
        LiftDirection::Unchanged
    };
    SampleLift {
        baseline,
        reordered,
        rr_delta,
        rank_delta,
        direction,
        order_changed: baseline_ranking != reordered_ranking,
    }
}

/// Honest verdict for the aggregate. Regressions surface as regressions; a
/// mean/vote disagreement surfaces as `Mixed` rather than being rounded toward
/// the favourable label.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum LiftVerdict {
    /// Net positive MRR lift AND more samples improved than worsened.
    LiftDemonstrated,
    /// Mean lift and sample-vote disagree in sign — not a clean result.
    Mixed,
    /// Reorder ran but produced no net change.
    NoLift,
    /// Net NEGATIVE lift — the reorder makes recall worse. Reported, not hidden.
    Regression,
    /// No samples, or no sample located its source — nothing to measure.
    Insufficient,
}

impl LiftVerdict {
    pub fn as_str(self) -> &'static str {
        match self {
            LiftVerdict::LiftDemonstrated => "lift_demonstrated",
            LiftVerdict::Mixed => "mixed",
            LiftVerdict::NoLift => "no_lift",
            LiftVerdict::Regression => "regression",
            LiftVerdict::Insufficient => "insufficient",
        }
    }
}

/// Aggregate lift across all samples.
#[derive(Debug, Clone)]
pub struct AggregateLift {
    pub sample_count: usize,
    /// Samples where the source key was present in the baseline ranking.
    pub source_found_count: usize,
    pub mrr_baseline: f64,
    pub mrr_reordered: f64,
    /// `mrr_reordered - mrr_baseline`. Signed — negative is a real result.
    pub mrr_lift: f64,
    /// Mean recall@k (baseline) for each cutoff, parallel to [`RECALL_K_CUTOFFS`].
    pub recall_baseline: Vec<(usize, f64)>,
    pub recall_reordered: Vec<(usize, f64)>,
    pub recall_lift: Vec<(usize, f64)>,
    pub improved: usize,
    pub worsened: usize,
    pub unchanged: usize,
    /// Samples whose ordering actually changed under the reorder.
    pub order_changed_count: usize,
    pub verdict: LiftVerdict,
}

/// Aggregate a batch of per-sample lifts into MRR / recall@k means and an
/// honest verdict.
pub fn aggregate_lift(samples: &[SampleLift]) -> AggregateLift {
    let n = samples.len();
    let nf = n.max(1) as f64;

    let source_found_count = samples
        .iter()
        .filter(|s| s.baseline.rank_of_source.is_some())
        .count();
    let mrr_baseline = samples
        .iter()
        .map(|s| s.baseline.reciprocal_rank)
        .sum::<f64>()
        / nf;
    let mrr_reordered = samples
        .iter()
        .map(|s| s.reordered.reciprocal_rank)
        .sum::<f64>()
        / nf;
    let mrr_lift = mrr_reordered - mrr_baseline;

    let mean_recall = |reordered: bool| -> Vec<(usize, f64)> {
        RECALL_K_CUTOFFS
            .iter()
            .enumerate()
            .map(|(i, &k)| {
                let mean = samples
                    .iter()
                    .map(|s| {
                        let m = if reordered { &s.reordered } else { &s.baseline };
                        m.recall_at.get(i).map(|(_, v)| *v).unwrap_or(0.0)
                    })
                    .sum::<f64>()
                    / nf;
                (k, mean)
            })
            .collect()
    };
    let recall_baseline = mean_recall(false);
    let recall_reordered = mean_recall(true);
    let recall_lift = recall_baseline
        .iter()
        .zip(recall_reordered.iter())
        .map(|((k, b), (_, r))| (*k, r - b))
        .collect::<Vec<_>>();

    let improved = samples
        .iter()
        .filter(|s| s.direction == LiftDirection::Improved)
        .count();
    let worsened = samples
        .iter()
        .filter(|s| s.direction == LiftDirection::Worsened)
        .count();
    let unchanged = n - improved - worsened;
    let order_changed_count = samples.iter().filter(|s| s.order_changed).count();

    let verdict = if n == 0 || source_found_count == 0 {
        LiftVerdict::Insufficient
    } else if mrr_lift > LIFT_EPS && improved > worsened {
        LiftVerdict::LiftDemonstrated
    } else if mrr_lift < -LIFT_EPS && worsened > improved {
        LiftVerdict::Regression
    } else if mrr_lift.abs() <= LIFT_EPS && improved == worsened {
        LiftVerdict::NoLift
    } else {
        // Mean and sample-vote disagree in sign (e.g. one large improvement
        // outweighing several small regressions). Do not round to the
        // favourable label.
        LiftVerdict::Mixed
    };

    AggregateLift {
        sample_count: n,
        source_found_count,
        mrr_baseline,
        mrr_reordered,
        mrr_lift,
        recall_baseline,
        recall_reordered,
        recall_lift,
        improved,
        worsened,
        unchanged,
        order_changed_count,
        verdict,
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn keys(ks: &[&str]) -> Vec<String> {
        ks.iter().map(|s| s.to_string()).collect()
    }

    fn relset(ks: &[&str]) -> BTreeSet<String> {
        ks.iter().map(|s| s.to_string()).collect()
    }

    #[test]
    fn rank_and_reciprocal_basics() {
        let r = keys(&["a", "b", "c", "src", "e"]);
        assert_eq!(rank_of(&r, "src"), Some(4));
        assert_eq!(rank_of(&r, "missing"), None);
        // first relevant is "src" at rank 4 -> 0.25
        assert!((reciprocal_rank(&r, &relset(&["src"])) - 0.25).abs() < 1e-9);
        // first relevant is "b" at rank 2 -> 0.5 (closer relevant wins)
        assert!((reciprocal_rank(&r, &relset(&["b", "src"])) - 0.5).abs() < 1e-9);
        assert_eq!(reciprocal_rank(&r, &relset(&["nope"])), 0.0);
    }

    #[test]
    fn recall_at_counts_relevant_in_topk() {
        let r = keys(&["a", "b", "c", "d"]);
        let rel = relset(&["a", "c"]);
        assert!((recall_at(&r, &rel, 1) - 0.5).abs() < 1e-9); // only "a" in top-1
        assert!((recall_at(&r, &rel, 3) - 1.0).abs() < 1e-9); // a,c in top-3
        assert_eq!(recall_at(&r, &relset(&[]), 5), 0.0); // empty relevant -> 0
    }

    #[test]
    fn good_signal_yields_positive_lift() {
        // baseline: src at rank 4 (rr 0.25); reordered: src at rank 1 (rr 1.0)
        let base = keys(&["a", "b", "c", "src", "e"]);
        let reord = keys(&["src", "a", "b", "c", "e"]);
        let rel = relset(&["src"]);
        let s = sample_lift(&base, &reord, "src", &rel);
        assert_eq!(s.direction, LiftDirection::Improved);
        assert_eq!(s.rank_delta, Some(3)); // 4 -> 1
        assert!(s.rr_delta > 0.0);
        assert!(s.order_changed);
        let agg = aggregate_lift(&[s]);
        assert_eq!(agg.verdict, LiftVerdict::LiftDemonstrated);
        assert!(agg.mrr_lift > 0.0);
    }

    #[test]
    fn bad_signal_yields_regression_not_laundered() {
        // baseline: src at rank 1 (rr 1.0); reordered: src at rank 4 (rr 0.25)
        let base = keys(&["src", "a", "b", "c"]);
        let reord = keys(&["a", "b", "c", "src"]);
        let rel = relset(&["src"]);
        let s = sample_lift(&base, &reord, "src", &rel);
        assert_eq!(s.direction, LiftDirection::Worsened);
        assert_eq!(s.rank_delta, Some(-3)); // 1 -> 4
        let agg = aggregate_lift(&[s]);
        // anti-laundering: regression is reported as a regression, lift stays negative.
        assert_eq!(agg.verdict, LiftVerdict::Regression);
        assert!(agg.mrr_lift < 0.0, "mrr_lift must NOT be clamped to 0");
    }

    #[test]
    fn unchanged_order_yields_no_lift() {
        let base = keys(&["src", "a", "b"]);
        let reord = base.clone();
        let rel = relset(&["src"]);
        let s = sample_lift(&base, &reord, "src", &rel);
        assert_eq!(s.direction, LiftDirection::Unchanged);
        assert!(!s.order_changed);
        let agg = aggregate_lift(&[s]);
        assert_eq!(agg.verdict, LiftVerdict::NoLift);
        assert!(agg.mrr_lift.abs() < 1e-9);
    }

    #[test]
    fn absent_source_is_insufficient() {
        // source never appears in baseline -> nothing to measure.
        let base = keys(&["a", "b", "c"]);
        let reord = keys(&["c", "b", "a"]);
        let rel = relset(&["src"]);
        let s = sample_lift(&base, &reord, "src", &rel);
        assert_eq!(s.baseline.rank_of_source, None);
        assert_eq!(s.rank_delta, None);
        let agg = aggregate_lift(&[s]);
        assert_eq!(agg.verdict, LiftVerdict::Insufficient);
    }

    #[test]
    fn mixed_when_mean_and_vote_disagree() {
        let rel = relset(&["src"]);
        // sample 1: huge improvement (rank 10 -> 1)
        let s1 = sample_lift(
            &keys(&["a", "b", "c", "d", "e", "f", "g", "h", "i", "src"]),
            &keys(&["src", "a", "b", "c", "d", "e", "f", "g", "h", "i"]),
            "src",
            &rel,
        );
        // samples 2 & 3: TINY regressions (rank 4 -> 5, rr 0.25 -> 0.20, -0.05 each)
        // chosen small enough that s1's +0.9 still wins the mean despite losing
        // the 1-vs-2 sample vote.
        let small_reg = || {
            sample_lift(
                &keys(&["a", "b", "c", "src", "e"]),
                &keys(&["a", "b", "c", "e", "src"]),
                "src",
                &rel,
            )
        };
        let agg = aggregate_lift(&[s1, small_reg(), small_reg()]);
        // improved=1, worsened=2 (vote says down) but mean MRR is up (huge s1).
        assert_eq!(agg.improved, 1);
        assert_eq!(agg.worsened, 2);
        assert!(agg.mrr_lift > 0.0);
        assert_eq!(agg.verdict, LiftVerdict::Mixed);
    }

    #[test]
    fn empty_batch_is_insufficient() {
        let agg = aggregate_lift(&[]);
        assert_eq!(agg.verdict, LiftVerdict::Insufficient);
        assert_eq!(agg.sample_count, 0);
    }
}
