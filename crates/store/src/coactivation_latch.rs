//! Edge consolidation latch + regrowth cooldown for coactivation edges (T8 borrow).
//!
//! Ported (algorithm only — NOT a crate dependency) from `biocortex-rs` structural
//! plasticity (`apply_structural_plasticity`): an edge whose strength proves important
//! **latches** (becomes immune to pruning), and a pruned edge enters a regrowth
//! **cooldown** so it cannot be immediately re-learned and re-pruned. That re-learn /
//! re-prune oscillation is the churn that bloats `memory_coactivation` and pollutes the
//! cross-node memory sync.
//!
//! AB coactivation edges are integer `count`, undirected. This module is a PURE,
//! deterministic decision kernel + a churn simulator. It does **NOT** touch the store
//! (no sqlite, no schema, no writes). Wiring a `consolidated` column into
//! `memory_coactivation` (so `decay_coactivation_once` skips latched rows) is a separate,
//! lswr-gated step; this module is the offline kernel that justifies it.
//!
//! Run the synthetic churn demo:
//!   cargo run -p ab-store --no-default-features --example coactivation_churn_demo

/// What to do with a coactivation edge at a given event step.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum LatchDecision {
    /// `count` reached the consolidation threshold — latch it (immune to future pruning).
    Latch,
    /// Below the prune floor and not consolidated — prune it.
    Prune,
    /// Keep as-is.
    Hold,
}

/// Latch / prune / cooldown thresholds. All counts are integer (AB edges use `count`).
#[derive(Debug, Clone, Copy)]
pub struct LatchConfig {
    /// `count >= consolidate_at_count` latches the edge (then it never prunes).
    pub consolidate_at_count: u32,
    /// `count < prune_below_count` prunes the edge unless it is consolidated.
    pub prune_below_count: u32,
    /// Event steps a pruned edge stays suppressed before it may be re-established.
    pub regrowth_cooldown_steps: u32,
}

impl Default for LatchConfig {
    fn default() -> Self {
        // Conservative defaults; the real thresholds must be re-tuned against a
        // coactivation-count corpus before any runtime wiring (biocortex's float
        // weights do not transfer directly to AB's integer counts).
        Self {
            consolidate_at_count: 5,
            prune_below_count: 1,
            regrowth_cooldown_steps: 3,
        }
    }
}

impl LatchConfig {
    /// Pure per-edge decision given its current `count` and whether it is already
    /// consolidated. Deterministic; no I/O, no state mutation.
    pub fn decide(&self, count: u32, consolidated: bool) -> LatchDecision {
        if count >= self.consolidate_at_count {
            LatchDecision::Latch
        } else if consolidated {
            // A latched edge is immune to pruning even when its count dips.
            LatchDecision::Hold
        } else if count < self.prune_below_count {
            LatchDecision::Prune
        } else {
            LatchDecision::Hold
        }
    }

    /// Is re-establishing an edge currently blocked because it was pruned within the
    /// cooldown window? `pruned_at_step = None` means "not in cooldown".
    pub fn in_cooldown(&self, pruned_at_step: Option<u64>, step: u64) -> bool {
        match pruned_at_step {
            Some(p) => step.saturating_sub(p) < self.regrowth_cooldown_steps as u64,
            None => false,
        }
    }
}

/// Count how many times an edge is PRUNED while replaying its integer-`count` trajectory
/// (one entry per event step — co-fires raise it, decay passes lower it).
///
/// - `use_latch = false` is the current AB behaviour: prune whenever `count <
///   prune_below_count`; the next co-fire re-mints it, so a bursty-but-important edge is
///   pruned again and again (= churn).
/// - `use_latch = true` applies the borrow: once `count` reaches the consolidation
///   threshold the edge latches and never prunes again; a freshly pruned edge is
///   suppressed for the cooldown window so it cannot immediately re-prune.
///
/// Returns the number of prune events. Fewer prunes = less churn.
pub fn simulate_prunes(trajectory: &[u32], cfg: &LatchConfig, use_latch: bool) -> u32 {
    let mut consolidated = false;
    let mut pruned_at: Option<u64> = None;
    let mut prunes = 0u32;
    for (i, &count) in trajectory.iter().enumerate() {
        let step = i as u64;
        if !use_latch {
            if count < cfg.prune_below_count {
                prunes += 1;
            }
            continue;
        }
        // Cooldown: a recently-pruned edge is suppressed and cannot grow/latch yet.
        if cfg.in_cooldown(pruned_at, step) {
            continue;
        }
        pruned_at = None;
        if count >= cfg.consolidate_at_count {
            consolidated = true;
        }
        if !consolidated && count < cfg.prune_below_count {
            prunes += 1;
            pruned_at = Some(step);
        }
    }
    prunes
}

/// Aggregate churn outcome over many edges' trajectories.
#[derive(Debug, Clone, Default)]
pub struct ChurnReport {
    pub edges: usize,
    pub prunes_baseline: u32,
    pub prunes_latched: u32,
}

impl ChurnReport {
    /// Fraction of baseline prune events eliminated by latch+cooldown, in `[0, 1]`.
    pub fn churn_reduction(&self) -> f64 {
        if self.prunes_baseline == 0 {
            0.0
        } else {
            (self.prunes_baseline - self.prunes_latched) as f64 / self.prunes_baseline as f64
        }
    }
}

/// Replay every edge trajectory under both regimes and aggregate the churn delta.
pub fn measure_churn<'a, I>(trajectories: I, cfg: &LatchConfig) -> ChurnReport
where
    I: IntoIterator<Item = &'a [u32]>,
{
    let mut rep = ChurnReport::default();
    for traj in trajectories {
        rep.edges += 1;
        rep.prunes_baseline += simulate_prunes(traj, cfg, false);
        rep.prunes_latched += simulate_prunes(traj, cfg, true);
    }
    rep
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn important_but_bursty_edge_latches_and_stops_churning() {
        let cfg = LatchConfig::default(); // consolidate>=5, prune<1, cooldown 3
                                          // rises to 6 (latches at step 3), then dips to 0 three times.
        let traj = [1u32, 3, 5, 6, 0, 4, 0, 5, 0];
        let baseline = simulate_prunes(&traj, &cfg, false);
        let latched = simulate_prunes(&traj, &cfg, true);
        assert_eq!(baseline, 3, "baseline prunes once per below-floor dip");
        assert_eq!(latched, 0, "once consolidated, the edge never prunes again");
        assert!(latched < baseline);
    }

    #[test]
    fn weak_edge_that_never_consolidates_still_prunes() {
        let cfg = LatchConfig::default();
        // never reaches 5, so it never latches; cooldown still curbs immediate re-prune.
        let traj = [0u32, 0, 0, 0, 0];
        let baseline = simulate_prunes(&traj, &cfg, false);
        let latched = simulate_prunes(&traj, &cfg, true);
        assert_eq!(baseline, 5, "every step is below floor");
        // With cooldown=3: prune at 0, suppressed 1,2, prune at 3, suppressed 4 -> 2 prunes.
        assert_eq!(latched, 2, "cooldown suppresses immediate re-prunes");
        assert!(latched < baseline);
    }

    #[test]
    fn decide_is_pure_and_covers_each_branch() {
        let cfg = LatchConfig::default();
        assert_eq!(cfg.decide(6, false), LatchDecision::Latch);
        assert_eq!(cfg.decide(0, true), LatchDecision::Hold); // consolidated => immune
        assert_eq!(cfg.decide(0, false), LatchDecision::Prune);
        assert_eq!(cfg.decide(3, false), LatchDecision::Hold);
    }

    #[test]
    fn cooldown_window_is_inclusive_of_recent_prune() {
        let cfg = LatchConfig {
            regrowth_cooldown_steps: 3,
            ..LatchConfig::default()
        };
        assert!(cfg.in_cooldown(Some(10), 10));
        assert!(cfg.in_cooldown(Some(10), 12));
        assert!(!cfg.in_cooldown(Some(10), 13));
        assert!(!cfg.in_cooldown(None, 100));
    }

    #[test]
    fn measure_churn_aggregates_and_reports_reduction() {
        let cfg = LatchConfig::default();
        let a = [1u32, 5, 6, 0, 0];
        let b = [0u32, 5, 0, 5, 0];
        let trajs = [a.as_slice(), b.as_slice()];
        let rep = measure_churn(trajs, &cfg);
        assert_eq!(rep.edges, 2);
        assert!(rep.prunes_latched < rep.prunes_baseline);
        assert!(rep.churn_reduction() > 0.0 && rep.churn_reduction() <= 1.0);
    }
}
