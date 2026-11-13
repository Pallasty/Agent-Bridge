//! Real stdio diagnostics and real setup in an isolated HOME.
use std::path::Path;
use std::process::Command;

#[test]
fn hook_effects_and_embedded_templates_over_real_stdio() {
    let script =
        Path::new(env!("CARGO_MANIFEST_DIR")).join("../../scripts/check-hook-effects-mcp.py");
    let output = tempfile::tempdir().expect("isolated hook evidence");
    let result = Command::new("python3")
        .arg(script)
        .args(["--binary", env!("CARGO_BIN_EXE_agent-bridge")])
        .arg("--output")
        .arg(output.path())
        .output()
        .expect("run hook MCP regression");
    assert!(
        result.status.success(),
        "stdout={}\nstderr={}\nserver={}",
        String::from_utf8_lossy(&result.stdout),
        String::from_utf8_lossy(&result.stderr),
        std::fs::read_to_string(output.path().join("server.stderr.log")).unwrap_or_default()
    );
}

#[test]
fn precompact_outcomes_and_persisted_readback_over_real_stdio() {
    let script = Path::new(env!("CARGO_MANIFEST_DIR"))
        .join("../../scripts/eval/precompact_effect_feedback.py");
    let output = tempfile::tempdir().expect("isolated precompact evidence");
    let result = Command::new("python3")
        .arg(script)
        .args(["--binary", env!("CARGO_BIN_EXE_agent-bridge")])
        .arg("--output")
        .arg(output.path())
        .output()
        .expect("run precompact regression");
    assert!(
        result.status.success(),
        "stdout={}\nstderr={}",
        String::from_utf8_lossy(&result.stdout),
        String::from_utf8_lossy(&result.stderr)
    );
}
