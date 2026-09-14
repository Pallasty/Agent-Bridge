#[test]
fn weekly_snapshot_composition_matches_persisted_state() {
    let root = std::path::Path::new(env!("CARGO_MANIFEST_DIR")).join("../..");
    let result = std::process::Command::new("python3")
        .arg(root.join("scripts/eval/dream_weekly_snapshot_check.py"))
        .arg("--binary")
        .arg(env!("CARGO_BIN_EXE_agent-bridge"))
        .output()
        .expect("run isolated weekly/snapshot regressions");
    assert!(
        result.status.success(),
        "{}\n{}",
        String::from_utf8_lossy(&result.stdout),
        String::from_utf8_lossy(&result.stderr)
    );
}
