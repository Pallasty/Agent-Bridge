//! End-to-end MCP regression, using the same stdlib client as manual binary checks.
//! No mocks: Cargo's freshly built server handles initialize/list/call/follow-up/EOF.
use std::path::Path;
use std::process::Command;

#[test]
fn capabilities_topics_and_followups_over_real_stdio() {
    let script = Path::new(env!("CARGO_MANIFEST_DIR"))
        .join("../../scripts/check-capabilities-sections-mcp.py");
    for profile in ["codex-essential", "all-dev"] {
        let output = tempfile::tempdir().expect("isolated MCP test output");
        let result = Command::new("python3")
            .arg(&script)
            .args(["--binary", env!("CARGO_BIN_EXE_agent-bridge")])
            .arg("--output")
            .arg(output.path())
            .args(["--profile", profile])
            .output()
            .expect("run Python stdlib MCP client");
        assert!(
            result.status.success(),
            "profile={profile}\nstdout={}\nstderr={}\nserver={}",
            String::from_utf8_lossy(&result.stdout),
            String::from_utf8_lossy(&result.stderr),
            std::fs::read_to_string(output.path().join("server.stderr.log")).unwrap_or_default()
        );
    }
}
