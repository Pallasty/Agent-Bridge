//! **G4 §5.V4 — CURATE_SCORE_THRESHOLD sensitivity probe** (NOT a CI test).
//!
//! `DESIGN-dream-autotune-v0` §5.V4 gates building the autotune loop on a
//! prerequisite question: does varying `CURATE_SCORE_THRESHOLD` *materially*
//! change the extracted lesson set? If the threshold sits in a flat region,
//! autotuning it is pointless and G4 is falsified for this param (the design's
//! own words). This probe runs the REAL `curate` over a sample of local CC
//! transcripts at the candidate thresholds and reports the sensitivity.
//!
//! Read-only: it only reads ~/.claude transcripts and calls the pure
//! `curate_conversation_with_options`. `#[ignore]`d because it depends on local
//! data, so it never runs in CI.
//!
//! Run: `cargo test -p ab-bridge --test autotune_v4_sensitivity_probe -- --ignored --nocapture`

use ab_bridge::curate::{
    curate_conversation_with_options, CurateOptions, DEFAULT_IMPLICIT_DEDUP_JACCARD,
};
use std::collections::BTreeSet;
use std::fs;
use std::path::{Path, PathBuf};

fn find_jsonl(dir: &Path, out: &mut Vec<PathBuf>) {
    if let Ok(rd) = fs::read_dir(dir) {
        for e in rd.flatten() {
            let p = e.path();
            if p.is_dir() {
                find_jsonl(&p, out);
            } else if p.extension().map(|x| x == "jsonl").unwrap_or(false) {
                out.push(p);
            }
        }
    }
}

#[test]
#[ignore = "depends on local ~/.claude transcripts; run explicitly for G4 §5.V4"]
fn autotune_v4_threshold_sensitivity_probe() {
    let home = std::env::var("HOME").expect("HOME set");
    let root = PathBuf::from(home).join(".claude/projects");
    let mut files = Vec::new();
    find_jsonl(&root, &mut files);
    // Medium-sized sessions (30–250KB): lesson-dense but small enough that
    // curate's O(n²) Pass-2 Jaccard dedup stays fast. (The first cut — 40
    // LARGEST files + uncapped max_items — wedged ~1h: dedup blows up on
    // multi-MB input. That's itself a real curate finding, noted separately.)
    files.retain(|p| {
        let n = fs::metadata(p).map(|m| m.len()).unwrap_or(0);
        (30_000..=250_000).contains(&n)
    });
    files.sort(); // deterministic order
    let sample: Vec<_> = files.into_iter().take(30).collect();
    assert!(
        !sample.is_empty(),
        "no transcripts in 30–250KB under {root:?}"
    );

    let thresholds = [0.30f32, 0.45, 0.60];
    // High enough not to bind for the capped ~120K-char input, so the THRESHOLD
    // (not the item cap) is what limits output — preserving the sensitivity signal.
    let max_items = 2_000usize;

    let mut totals = [0usize; 3];
    let mut set_lo: BTreeSet<String> = BTreeSet::new();
    let mut set_hi: BTreeSet<String> = BTreeSet::new();

    for f in &sample {
        let raw = match fs::read_to_string(f) {
            Ok(t) => t,
            Err(_) => continue,
        };
        // JSONL → each record is one giant line; restore escaped newlines inside
        // the message bodies so curate scores natural lines, not whole JSON blobs.
        // JSON noise is constant across thresholds, so relative sensitivity holds.
        // Cap to ~120K chars so Pass-2 dedup stays fast on big sessions.
        let text: String = raw.replace("\\n", "\n").chars().take(120_000).collect();
        for (i, &th) in thresholds.iter().enumerate() {
            let opts = CurateOptions {
                implicit_score_threshold: th,
                implicit_dedup_jaccard: DEFAULT_IMPLICIT_DEDUP_JACCARD,
            };
            let out = curate_conversation_with_options(&text, None, max_items, opts);
            totals[i] += out.len();
            if i == 0 {
                for r in &out {
                    set_lo.insert(r.content.clone());
                }
            }
            if i == thresholds.len() - 1 {
                for r in &out {
                    set_hi.insert(r.content.clone());
                }
            }
        }
    }

    let inter = set_lo.intersection(&set_hi).count();
    let union = set_lo.union(&set_hi).count();
    let jaccard = if union == 0 {
        1.0
    } else {
        inter as f64 / union as f64
    };
    let drop_pct = if totals[0] == 0 {
        0.0
    } else {
        100.0 * (totals[0] as f64 - totals[2] as f64) / totals[0] as f64
    };

    println!("\n=== G4 §5.V4 threshold-sensitivity probe ===");
    println!("sample sessions: {}", sample.len());
    for (i, &th) in thresholds.iter().enumerate() {
        println!(
            "  threshold {th:.2} → {} lessons extracted (total over sample)",
            totals[i]
        );
    }
    println!("lesson-count change 0.30→0.60: {drop_pct:.1}%");
    println!(
        "lesson-set Jaccard(0.30, 0.60): {jaccard:.3}  (1.0 = identical sets; lower = more sensitive)"
    );
    let sensitive = drop_pct.abs() >= 20.0 || jaccard <= 0.80;
    println!(
        "VERDICT: threshold is {} → autotune {}",
        if sensitive { "SENSITIVE" } else { "FLAT" },
        if sensitive {
            "VIABLE for this param (proceed to V2 access-join check)"
        } else {
            "POINTLESS for this param (G4 falsified here → manual tune or skip)"
        }
    );
    println!("===========================================\n");
}
