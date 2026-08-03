use std::{
    fs,
    path::PathBuf,
    process::{Command, Output},
    time::{SystemTime, UNIX_EPOCH},
};

fn test_tempdir() -> tempfile::TempDir {
    let root = PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("../../target/s13-test-tmp");
    fs::create_dir_all(&root).expect("create S13 test temp root");
    tempfile::Builder::new()
        .prefix("skill-retro-")
        .tempdir_in(root)
        .expect("create S13 test temp dir")
}

fn unix_now() -> i64 {
    SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .expect("system time after Unix epoch")
        .as_secs() as i64
}

fn run_skill_retro(xdg_data_home: &std::path::Path, extra_args: &[&str]) -> Output {
    Command::new(env!("CARGO_BIN_EXE_agent-bridge"))
        .args(["dream", "skill-retro", "--days", "7"])
        .args(extra_args)
        .env("XDG_DATA_HOME", xdg_data_home)
        .output()
        .expect("run agent-bridge dream skill-retro")
}

#[test]
fn skill_retro_empty_window_json_contract_preserves_schema_time_relation_and_store_open() {
    let dir = test_tempdir();
    let xdg = dir.path().join("xdg");
    fs::create_dir_all(xdg.join("agent-bridge")).expect("create isolated state dir");
    let before = unix_now();

    let output = run_skill_retro(&xdg, &["--json"]);

    let after = unix_now();
    assert!(
        output.status.success(),
        "stdout={}; stderr={}",
        String::from_utf8_lossy(&output.stdout),
        String::from_utf8_lossy(&output.stderr)
    );
    assert_eq!(output.stderr, b"");
    let payload: serde_json::Value =
        serde_json::from_slice(&output.stdout).expect("parse SkillRetro JSON output");
    let now = payload["now_unix"].as_i64().expect("integer now_unix");
    assert!(
        (before..=after).contains(&now),
        "reported now_unix={now} must be captured during command [{before}, {after}]"
    );
    assert_eq!(
        payload,
        serde_json::json!({
            "window_days": 7,
            "cutoff_unix": now - 7 * 86_400,
            "now_unix": now,
            "lessons_total": 0,
            "lessons_consulted": 0,
            "consulted_ratio": 0.0,
            "mean_access_count": 0.0,
            "rows": [],
        })
    );
    assert!(
        xdg.join("agent-bridge/state.db").is_file(),
        "executor must still open the isolated Store"
    );
}
