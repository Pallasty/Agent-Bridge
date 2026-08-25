use std::fs;
use std::path::PathBuf;

fn bridge_source(relative: &str) -> String {
    let path = PathBuf::from(env!("CARGO_MANIFEST_DIR")).join(relative);
    fs::read_to_string(&path).unwrap_or_else(|error| panic!("read {}: {error}", path.display()))
}

#[test]
fn daemon_root_retains_retrieval_wiring_while_module_owns_the_loop() {
    let main = bridge_source("src/main.rs");
    let module = bridge_source("src/retrieval_outcome.rs");

    let retrieval_start = main
        .find("if !ab_bridge::retrieval_outcome::apply_tick_enabled()")
        .expect("daemon root retains retrieval apply gate");
    let next_supervisor = main[retrieval_start..]
        .find("// Orphan reaper")
        .map(|offset| retrieval_start + offset)
        .expect("retrieval startup remains before orphan reaper");
    let root = &main[retrieval_start..next_supervisor];

    assert!(root.contains("apply_tick_secs()"));
    assert!(root.contains("hub.store.clone()"));
    assert!(root.contains("spawn_apply_supervisor(store, tick_secs)"));
    assert!(root.contains("retrieval-outcome-apply: disabled"));
    assert!(root.contains("retrieval-outcome-apply: no store configured"));
    assert!(!root.contains("tokio::time::interval"));
    assert!(!root.contains("run_apply_pass("));
    assert!(!root.contains("tick_rule_params()"));

    assert!(module.contains("tokio::time::interval"));
    assert!(module.contains("MissedTickBehavior::Delay"));
    assert!(module.contains("run_apply_pass(store, &params, 200, true, now)"));
    assert!(module.contains("retrieval-outcome-apply: pass ran"));
    assert!(module.contains("retrieval-outcome-apply: nothing to do"));
    assert!(module.contains("retrieval-outcome-apply: pass error"));
}
