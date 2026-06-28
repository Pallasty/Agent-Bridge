//! Synthetic churn-reduction demo for the coactivation latch + cooldown (T8 borrow).
//!
//! Read-only, no store access. Replays a few integer-`count` edge trajectories (a co-fire
//! raises the count, a quiet window decays it) under the current AB regime vs the
//! latch+cooldown borrow, and prints the prune-event reduction. The thresholds are
//! placeholders — the runtime wiring (a `consolidated` column on `memory_coactivation`)
//! must re-tune them against a real coactivation-count corpus behind the lswr gate.
//!
//! Usage: cargo run -p ab-store --no-default-features --example coactivation_churn_demo

use ab_store::coactivation_latch::{measure_churn, LatchConfig};

fn main() {
    let cfg = LatchConfig::default();

    // Each trajectory = an edge's coactivation count over event steps.
    // Several are "important but bursty": they prove themselves (count >= consolidate),
    // then dip to 0 during quiet windows — exactly the re-learn/re-prune churn case.
    let edges: Vec<Vec<u32>> = vec![
        vec![1, 3, 5, 6, 0, 4, 0, 5, 0], // strong, oscillates -> baseline churns, latch stops it
        vec![0, 5, 0, 5, 0, 6, 0],       // proven then bursty
        vec![2, 4, 6, 0, 7, 0, 0, 8, 0], // very strong, deep dips
        vec![0, 0, 0, 0, 0],             // genuinely weak: never consolidates (control)
        vec![1, 1, 2, 1, 0, 1, 0],       // borderline weak
    ];
    let trajs: Vec<&[u32]> = edges.iter().map(|e| e.as_slice()).collect();
    let rep = measure_churn(trajs.iter().copied(), &cfg);

    println!("{{");
    println!("  \"schema\": \"agent_bridge.coactivation_churn_demo.v0\",");
    println!("  \"read_only\": true,");
    println!(
        "  \"config\": {{ \"consolidate_at_count\": {}, \"prune_below_count\": {}, \"regrowth_cooldown_steps\": {} }},",
        cfg.consolidate_at_count, cfg.prune_below_count, cfg.regrowth_cooldown_steps
    );
    println!("  \"edges\": {},", rep.edges);
    println!("  \"prunes_baseline\": {},", rep.prunes_baseline);
    println!("  \"prunes_latched\": {},", rep.prunes_latched);
    println!("  \"churn_reduction\": {:.4}", rep.churn_reduction());
    println!("}}");
}
