use std::fs;
use std::path::PathBuf;

fn bridge_source(relative: &str) -> String {
    let path = PathBuf::from(env!("CARGO_MANIFEST_DIR")).join(relative);
    fs::read_to_string(&path).unwrap_or_else(|error| panic!("read {}: {error}", path.display()))
}

#[test]
fn daemon_root_retains_c3_wiring_while_module_owns_the_loop() {
    let main = bridge_source("src/main.rs");
    let module = bridge_source("src/c3_self_check.rs");

    let c3_start = main
        .find("if ab_bridge::c3_self_check::c3_disabled_via_env()")
        .expect("daemon root retains the C3 disable gate");
    let retrieval_start = main[c3_start..]
        .find("// Retrieval-outcome apply tick")
        .map(|offset| c3_start + offset)
        .expect("C3 startup remains before retrieval supervisor");
    let c3_root = &main[c3_start..retrieval_start];

    assert!(c3_root.contains("C3SupervisorConfig::from_env()"));
    assert!(c3_root.contains("let c3_store = hub.store.clone()"));
    assert!(c3_root.contains("spawn_supervisor(c3_store, c3_config)"));
    assert!(c3_root.contains("c3-self-check: disabled by env"));
    assert!(c3_root.contains("c3-self-check: spawning S1-S5 tick"));
    assert!(!c3_root.contains("tokio::time::interval"));
    assert!(!c3_root.contains("s1_check_and_alert"));
    assert!(!c3_root.contains("schema_meta_version().await"));
    assert!(!c3_root.contains("forum_post("));

    assert!(module.contains("tokio::time::interval"));
    assert!(module.contains("MissedTickBehavior::Delay"));
    assert!(module.contains("s1_check_and_alert()"));
    assert!(module.contains("store.schema_meta_version().await"));
    assert!(module.contains("store.s234_counts().await"));
    assert!(module.contains(".forum_post("));
}
