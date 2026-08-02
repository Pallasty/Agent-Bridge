use std::{
    fs,
    path::Path,
    process::{Command, Output},
};

fn run_dream(xdg_data_home: &Path, args: &[&str]) -> Output {
    Command::new(env!("CARGO_BIN_EXE_agent-bridge"))
        .arg("dream")
        .args(args)
        .env("XDG_DATA_HOME", xdg_data_home)
        .output()
        .expect("run agent-bridge dream command")
}

fn assert_success_without_stderr(output: &Output) {
    assert!(
        output.status.success(),
        "stdout={}; stderr={}",
        String::from_utf8_lossy(&output.stdout),
        String::from_utf8_lossy(&output.stderr)
    );
    assert_eq!(output.stderr, b"");
}

fn title_timestamp<'a>(html: &'a str, prefix: &str) -> &'a str {
    let start = html
        .find(prefix)
        .map(|offset| offset + prefix.len())
        .expect("HTML title prefix");
    let end = html[start..]
        .find("</title>")
        .map(|offset| start + offset)
        .expect("HTML title suffix");
    &html[start..end]
}

fn assert_utc_second_timestamp(timestamp: &str) {
    let bytes = timestamp.as_bytes();
    assert_eq!(bytes.len(), 20, "timestamp={timestamp}");
    for (index, expected) in [
        (4, b'-'),
        (7, b'-'),
        (10, b' '),
        (13, b':'),
        (16, b':'),
        (19, b'Z'),
    ] {
        assert_eq!(bytes[index], expected, "timestamp={timestamp}");
    }
    for (index, byte) in bytes.iter().enumerate() {
        if ![4, 7, 10, 13, 16, 19].contains(&index) {
            assert!(byte.is_ascii_digit(), "timestamp={timestamp}");
        }
    }
}

#[test]
fn dream_promote_empty_html_contract_preserves_output_and_completed_report() {
    let dir = tempfile::tempdir().expect("dream promote temp dir");
    let xdg = dir.path().join("xdg");
    fs::create_dir_all(xdg.join("agent-bridge")).expect("create state dir");
    let report = dir.path().join("promote.html");

    let output = run_dream(
        &xdg,
        &[
            "promote",
            "--dry-run",
            "--html",
            report.to_str().expect("utf-8 report path"),
        ],
    );

    assert_success_without_stderr(&output);
    assert_eq!(
        String::from_utf8(output.stdout).expect("utf-8 promote stdout"),
        format!(
            "(no coactivation pairs with count ≥ 5)\nDB: {}\nhtml report: {}\n",
            xdg.join("agent-bridge/state.db").display(),
            report.display()
        )
    );

    let html = fs::read_to_string(&report).expect("read promote HTML");
    let timestamp = title_timestamp(&html, "<title>dream promote — ");
    assert_utc_second_timestamp(timestamp);
    assert_eq!(html.matches(timestamp).count(), 2);
    for marker in [
        "<h1>dream promote — Hebbian crystallization</h1>",
        r#"<span class="badge badge-dry">DRY RUN — NO WRITES</span>"#,
        r#"<span class="num">0</span>would promote"#,
        r#"<span class="num">0</span>skipped"#,
        r#"<span class="num">0</span>candidates"#,
        "<h2>Strength Map</h2>",
        "<h2>Decisions</h2>",
        "No co-activation pairs at or above the threshold.",
        &format!(
            "DB: <code>{}</code>",
            xdg.join("agent-bridge/state.db").display()
        ),
    ] {
        assert!(html.contains(marker), "promote HTML missing {marker}");
    }
}

#[test]
fn dream_codebase_report_empty_html_contract_preserves_output_and_completed_report() {
    let dir = tempfile::tempdir().expect("dream codebase report temp dir");
    let xdg = dir.path().join("xdg");
    fs::create_dir_all(xdg.join("agent-bridge")).expect("create state dir");
    let root = dir.path().join("indexed-root");
    let report = dir.path().join("codebase.html");

    let output = run_dream(
        &xdg,
        &[
            "codebase-report",
            "--root",
            root.to_str().expect("utf-8 root path"),
            "--top-n",
            "3",
            "--html",
            report.to_str().expect("utf-8 report path"),
        ],
    );

    assert_success_without_stderr(&output);
    assert_eq!(
        String::from_utf8(output.stdout).expect("utf-8 codebase stdout"),
        format!(
            "# Codebase call-graph audit\nroot: {}\nDB:   {}\n\n0 total calls across 0 files\n\n(no calls in `codebase_calls` for this root — run `agent-bridge codebase index` first, or check that the root path matches the indexed one)\n\nhtml report: {}\n",
            root.display(),
            xdg.join("agent-bridge/state.db").display(),
            report.display()
        )
    );

    let html = fs::read_to_string(&report).expect("read codebase HTML");
    let timestamp = title_timestamp(&html, "<title>codebase report — ");
    assert_utc_second_timestamp(timestamp);
    assert_eq!(html.matches(timestamp).count(), 3);
    for marker in [
        "<h1>codebase call-graph audit</h1>",
        &format!("<span>root <code>{}</code></span>", root.display()),
        r#"<span class="num">0</span>calls"#,
        r#"<span class="num">0</span>files with calls"#,
        "No calls indexed for this root.",
        "<h2>Per-language</h2>",
        "<h2>Hot callees — top 0</h2>",
        "<h2>Fan-out callers — top 0</h2>",
        "<h2>Fan-out files — top 0</h2>",
        "<h2>Orphan function candidates — 0 high-confidence</h2>",
        "<h2>Likely false positives — 0</h2>",
        &format!(
            "DB: <code>{}</code>",
            xdg.join("agent-bridge/state.db").display()
        ),
    ] {
        assert!(html.contains(marker), "codebase HTML missing {marker}");
    }
}
