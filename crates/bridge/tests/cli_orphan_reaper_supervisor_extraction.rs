use std::fs;
use std::path::PathBuf;

fn bridge_source(relative: &str) -> String {
    let path = PathBuf::from(env!("CARGO_MANIFEST_DIR")).join(relative);
    fs::read_to_string(&path).unwrap_or_else(|error| panic!("read {}: {error}", path.display()))
}

#[test]
fn daemon_root_retains_reaper_admission_while_module_owns_effect_loop() {
    let main = bridge_source("src/main.rs");
    let module = bridge_source("src/orphan_reaper.rs");

    let reaper_start = main
        .find("if !ab_bridge::orphan_reaper::reaper_enabled()")
        .expect("daemon root retains orphan reaper gate");
    let serve_start = main[reaper_start..]
        .find("serve(&socket, Router::new(hub)).await")
        .map(|offset| reaper_start + offset)
        .expect("reaper startup remains before daemon serve");
    let root = &main[reaper_start..serve_start];

    assert!(root.contains("reaper_tick_secs()"));
    assert!(root.contains("hub.store.clone()"));
    assert!(root.contains("spawn_reaper_supervisor(store, tick_secs)"));
    assert!(root.contains("orphan-reaper: disabled"));
    assert!(root.contains("orphan-reaper: no store configured"));
    assert!(!root.contains("tokio::time::interval"));
    assert!(!root.contains("run_reaper_pass("));
    assert!(!root.contains("reaper_stale_secs()"));

    assert!(module.contains("tokio::time::interval"));
    assert!(module.contains("MissedTickBehavior::Delay"));
    assert!(module.contains("run_reaper_pass("));
    assert!(module.contains("reaper_stale_secs()"));
    assert!(module.contains("Duration::from_secs(3)"));
    assert!(module.contains("orphan-reaper: pass ran"));
    assert!(module.contains("orphan-reaper: nothing to reap"));
    assert!(module.contains("orphan-reaper: pass error"));
}
