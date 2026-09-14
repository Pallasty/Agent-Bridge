#[path = "../src/cli/dream_diff_plan.rs"]
mod candidate;
mod baseline {
    include!("fixtures/dream_diff_plan_baseline.rs");
}

use serde_json::{json, Value};

fn normalize(mut plan: candidate::DiffPlan<'_>) -> candidate::DiffPlan<'_> {
    // Only these three vectors originate from randomized HashMap iteration.
    plan.entered_top.sort();
    plan.dropped_top.sort();
    plan.access_changed.sort();
    plan
}

#[test]
fn baseline_calculation_and_helpers_are_bound_to_the_source_commit() {
    let mut command = std::process::Command::new("git");
    for (key, _) in std::env::vars_os() {
        if key.to_string_lossy().starts_with("GIT_") {
            command.env_remove(key);
        }
    }
    let output = command
        .args([
            "show",
            "e34700ca0adf5b21c892d872f6ab8fa09f146fa3:crates/bridge/src/main.rs",
        ])
        .current_dir(env!("CARGO_MANIFEST_DIR"))
        .output()
        .unwrap();
    assert!(output.status.success());
    let source = String::from_utf8(output.stdout).unwrap();
    let reference = include_str!("fixtures/dream_diff_plan_baseline.rs");
    let start = source
        .find("    // Auto-order: smaller captured_at = older.")
        .unwrap();
    let end = start + source[start..].find("    if as_json {").unwrap();
    assert!(reference.contains(&source[start..end]));
    for name in ["kind_map", "access_map", "trans_set"] {
        let start = source.find(&format!("fn {name}(")).unwrap();
        let end = start + source[start..].find("\n}").unwrap() + 2;
        assert!(reference.contains(&source[start..end]));
    }
}

#[test]
fn known_deltas_and_chronological_keys() {
    let old = json!({"captured_at":100,"memory":{"active_total":4,"avg_importance_active":0.25,"by_kind_non_skill":[{"kind":"z","count":2}]},"access":{"top_10_keys":[{"key":"a","access_count":3}]}});
    let new = json!({"captured_at":3700,"memory":{"active_total":9,"avg_importance_active":0.75,"by_kind_non_skill":[{"kind":"a","count":1}]},"access":{"top_10_keys":[{"key":"a","access_count":7}]}});
    let plan = candidate::calculate(new, old, "new", "old");
    assert_eq!((plan.k_old, plan.k_new, plan.dt_secs), ("old", "new", 3600));
    assert_eq!(plan.active_d, 5);
    assert_eq!(plan.avg_imp_d, 0.5);
    assert_eq!(
        plan.kind_deltas,
        vec![("a".into(), 0, 1), ("z".into(), 2, 0)]
    );
    assert_eq!(plan.access_changed, vec![("a".into(), 3, 7)]);
}

#[test]
fn tied_times_missing_fields_and_duplicate_rows_keep_original_rules() {
    let old = json!({"captured_at":4,"memory":{"active_total":"bad"},"access":{"top_10_keys":[{"key":"a","access_count":1},{"key":"a","access_count":6}]},"transitions":{"top_5":[{"from":"x","to":"y","count":1}]}});
    let new = json!({"captured_at":4,"access":{"top_10_keys":[{"key":"a","access_count":8}]},"transitions":{"top_5":[{"from":"x","to":"y","count":9}]}});
    let plan = candidate::calculate(old, new, "first", "second");
    assert_eq!(
        (plan.k_old, plan.k_new, plan.dt_secs),
        ("first", "second", 0)
    );
    assert_eq!(plan.active_d, 0);
    assert_eq!(plan.access_changed, vec![("a".into(), 6, 8)]);
    assert!(plan.trans_entered.is_empty() && plan.trans_dropped.is_empty());
}

#[test]
fn value_corpus_matches_original_computation() {
    let mut corpus: Vec<Value> = vec![
        Value::Null,
        json!({}),
        json!({"captured_at":"bad","memory":[]}),
    ];
    for i in 0..13 {
        corpus.push(json!({
            "captured_at":i*3600-100,
            "memory":{"active_total":i,"archived_total":12-i,"edge_count":i*2,"avg_importance_active":i as f64/16.0,"by_kind_non_skill":[{"kind":"a","count":i},{"kind":"z","count":3},{"kind":"a","count":i+1},{"kind":false,"count":9}]},
            "coactivation":{"total_pairs":i,"pairs_burst_lt_1h":i+2,"pairs_persistent_ge_6h":12-i},
            "access":{"top_10_keys":[{"key":format!("k{}",i%3),"access_count":i},{"key":"shared","access_count":i+1},{"key":"shared","access_count":i+2}]},
            "identity":{"current":{"tool_calls_total":i*3,"memory_saves":i}},
            "topology":{"non_skill_active_total":i,"orphan_count":i%3,"p4_evolved_coverage":i%4,"top_5_hubs":[{"key":format!("h{}",i%3),"degree":i},{"key":"shared","degree":3}]},
            "transitions":{"top_5":[{"from":format!("a{}",i%3),"to":"b","count":i},{"from":false,"to":"c","count":3}]}
        }));
    }
    for old in &corpus {
        for new in &corpus {
            assert_eq!(
                normalize(candidate::calculate(old.clone(), new.clone(), "a", "b")),
                normalize(baseline::calculate(old.clone(), new.clone(), "a", "b"))
            );
        }
    }
}

#[test]
fn integer_overflow_behavior_matches_original_in_the_current_profile() {
    let old = json!({"captured_at":i64::MIN});
    let new = json!({"captured_at":i64::MAX});
    let current =
        std::panic::catch_unwind(|| candidate::calculate(old.clone(), new.clone(), "a", "b"));
    let original = std::panic::catch_unwind(|| baseline::calculate(old, new, "a", "b"));
    match (current, original) {
        (Ok(a), Ok(b)) => assert_eq!(normalize(a), normalize(b)),
        (Err(_), Err(_)) => (),
        _ => panic!("overflow behavior changed"),
    }
}

#[test]
fn isolated_cli_output_and_read_effects_match_the_baseline() {
    let root = std::path::Path::new(env!("CARGO_MANIFEST_DIR")).join("../..");
    let output = std::process::Command::new("python3")
        .arg(root.join("scripts/eval/dream_diff_plan_cli_check.py"))
        .arg("--binary")
        .arg(env!("CARGO_BIN_EXE_agent-bridge"))
        .output()
        .unwrap();
    assert!(
        output.status.success(),
        "{}\n{}",
        String::from_utf8_lossy(&output.stdout),
        String::from_utf8_lossy(&output.stderr)
    );
}
