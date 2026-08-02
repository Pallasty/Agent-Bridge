use serde_json::{json, Value};
use std::{
    fs,
    path::Path,
    process::{Command, Output},
};

fn write_doc(dir: &Path, name: &str, doc: &Value) -> std::path::PathBuf {
    let path = dir.join(name);
    fs::write(
        &path,
        serde_json::to_vec(doc).expect("encode walkthrough doc"),
    )
    .expect("write walkthrough doc");
    path
}

fn run_walkthrough(dir: &Path, doc: &Path, extra_args: &[&str]) -> Output {
    Command::new(env!("CARGO_BIN_EXE_agent-bridge"))
        .arg("walkthrough")
        .arg(doc)
        .args(extra_args)
        .env("AGENT_BRIDGE_PRESENTATIONS_DIR", dir.join("presentations"))
        .output()
        .expect("run agent-bridge walkthrough")
}

fn expected_artifact(dir: &Path, doc: &Value) -> (String, std::path::PathBuf) {
    let canonical = serde_json::to_string(doc).expect("canonical walkthrough doc");
    let id = ab_bridge::present::derive_id(&format!("walkthrough:{canonical}"));
    let path = dir.join("presentations").join(format!("{id}.html"));
    (id, path)
}

#[test]
fn walkthrough_completed_content_text_contract_is_exact() {
    let dir = tempfile::tempdir().expect("walkthrough temp dir");
    let doc = json!({"summary": "S10 summary", "steps": []});
    let doc_path = write_doc(dir.path(), "doc.json", &doc);
    let (id, artifact_path) = expected_artifact(dir.path(), &doc);

    let output = run_walkthrough(dir.path(), &doc_path, &[]);

    assert!(
        output.status.success(),
        "stdout={}; stderr={}",
        String::from_utf8_lossy(&output.stdout),
        String::from_utf8_lossy(&output.stderr)
    );
    assert_eq!(output.stderr, b"");
    assert_eq!(
        String::from_utf8(output.stdout).expect("utf-8 text output"),
        format!(
            "walkthrough artifact written:\n  id        : {id}\n  path      : {}\n  self-check: PASS (#ab-payload round-trips + rendered region non-empty)\n  gallery   : present_list shows kind=walkthrough; open the .html to view/share\n",
            artifact_path.display()
        )
    );
    assert!(
        artifact_path.is_file(),
        "walkthrough artifact must be written"
    );
}

#[test]
fn walkthrough_completed_content_json_contract_is_exact() {
    let dir = tempfile::tempdir().expect("walkthrough temp dir");
    let doc = json!({"steps": [{"heading": "S10 heading"}]});
    let doc_path = write_doc(dir.path(), "doc.json", &doc);
    let (id, artifact_path) = expected_artifact(dir.path(), &doc);

    let output = run_walkthrough(dir.path(), &doc_path, &["--json"]);

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
            "{{\"id\":\"{id}\",\"path\":\"{}\",\"self_check\":true,\"payload_ok\":true,\"region_has_content\":true}}\n",
            artifact_path.display()
        )
    );
}

#[test]
fn walkthrough_empty_content_failure_contract_is_exact() {
    let dir = tempfile::tempdir().expect("walkthrough temp dir");
    let doc = json!({"summary": "", "steps": []});
    let doc_path = write_doc(dir.path(), "empty.json", &doc);
    let (id, artifact_path) = expected_artifact(dir.path(), &doc);

    let output = run_walkthrough(dir.path(), &doc_path, &[]);

    assert_eq!(output.status.code(), Some(1));
    assert_eq!(
        String::from_utf8(output.stdout).expect("utf-8 text output"),
        format!(
            "walkthrough artifact written:\n  id        : {id}\n  path      : {}\n  self-check: FAIL\n  gallery   : present_list shows kind=walkthrough; open the .html to view/share\n",
            artifact_path.display()
        )
    );
    assert_eq!(
        String::from_utf8(output.stderr).expect("utf-8 error output"),
        "Error: walkthrough self-check FAILED (payload_ok=true region_has_content=false) \
— the doc rendered no content; supply a summary and/or steps with evidence\n"
    );
    assert!(
        artifact_path.is_file(),
        "the existing write-before-self-check ordering must remain visible"
    );
}
