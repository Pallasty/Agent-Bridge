use std::{
    fs,
    path::{Path, PathBuf},
    process::{Command, Output},
};

fn test_tempdir() -> tempfile::TempDir {
    let root = PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("../../target/s12-test-tmp");
    fs::create_dir_all(&root).expect("create S12 test temp root");
    tempfile::Builder::new()
        .prefix("agent-md-drift-")
        .tempdir_in(root)
        .expect("create S12 test temp dir")
}

fn run_agent_md_drift(xdg_data_home: &Path, agent_md: &Path, extra_args: &[&str]) -> Output {
    Command::new(env!("CARGO_BIN_EXE_agent-bridge"))
        .args([
            "dream",
            "agent-md-drift",
            "--window-days",
            "14",
            "--dry-run",
            "--agent-md-path",
            agent_md.to_str().expect("utf-8 AGENT.md path"),
        ])
        .args(extra_args)
        .env("XDG_DATA_HOME", xdg_data_home)
        .output()
        .expect("run agent-bridge dream agent-md-drift")
}

#[test]
fn agent_md_drift_empty_window_json_contract_is_exact_and_writes_no_proposals() {
    let dir = test_tempdir();
    let xdg = dir.path().join("xdg");
    fs::create_dir_all(xdg.join("agent-bridge")).expect("create isolated state dir");
    let agent_md = dir.path().join("AGENT.md");
    let profile = "# Agent Profile\nAlways verify evidence before claims.\n";
    fs::write(&agent_md, profile).expect("write isolated AGENT.md");

    let output = run_agent_md_drift(&xdg, &agent_md, &["--json"]);

    assert!(
        output.status.success(),
        "stdout={}; stderr={}",
        String::from_utf8_lossy(&output.stdout),
        String::from_utf8_lossy(&output.stderr)
    );
    assert_eq!(output.stderr, b"");
    assert_eq!(
        String::from_utf8(output.stdout).expect("utf-8 JSON output"),
        format!(
            concat!(
                "{{\n",
                "  \"agent_md_path\": \"{}\",\n",
                "  \"agent_md_bytes\": {},\n",
                "  \"window_days\": 14,\n",
                "  \"lessons_scanned\": 0,\n",
                "  \"covered\": 0,\n",
                "  \"skipped\": 0,\n",
                "  \"skipped_by_triage\": {{}},\n",
                "  \"skipped_samples\": [],\n",
                "  \"proposed\": 0,\n",
                "  \"proposals\": [],\n",
                "  \"dry_run\": true\n",
                "}}\n",
            ),
            agent_md.display(),
            profile.len(),
        )
    );
    assert!(
        xdg.join("agent-bridge/state.db").is_file(),
        "executor must still open the isolated Store"
    );
}
