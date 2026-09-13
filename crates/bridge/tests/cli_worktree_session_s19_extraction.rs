const ROOT: &str = include_str!("../src/main.rs");
const VIEW: &str = include_str!("../src/cli/worktree_session_view.rs");

fn root_function(name: &str) -> &str {
    let start = ROOT.find(&format!("fn {name}(")).unwrap();
    let tail = &ROOT[start..];
    &tail[..tail.find("\n}\n").unwrap()]
}

fn ordered(source: &str, markers: &[&str]) {
    let mut remaining = source;
    for marker in markers {
        let index = remaining
            .find(marker)
            .unwrap_or_else(|| panic!("missing or out of order: {marker}"));
        remaining = &remaining[index + marker.len()..];
    }
}

#[test]
fn value_module_cannot_discover_or_mutate_repositories() {
    for forbidden in [
        "std::fs",
        "std::env",
        "std::process",
        "Command::",
        "SystemTime",
        "Instant",
        "tokio::",
        "SqliteStore",
        "StateStore",
        "Hub",
    ] {
        assert!(
            !VIEW.contains(forbidden),
            "view acquired authority: {forbidden}"
        );
    }
    assert!(include_str!("../src/cli/mod.rs").contains("pub(super) mod worktree_session_view;"));
    assert!(!include_str!("../src/lib.rs").contains("mod worktree_session_view"));
    assert!(!ROOT.contains("fn plan_new_session("));
    assert!(!ROOT.contains("fn render_session_rows("));
}

#[test]
fn new_retains_discovery_clock_mkdir_git_and_success_order() {
    ordered(
        root_function("run_worktree_session_new"),
        &[
            "std::env::var(\"AGENT_BRIDGE_REPO\")",
            "[\"rev-parse\", \"--show-toplevel\"]",
            "SystemTime::now()",
            ".unwrap_or(0)",
            "plan_new_session(&repo_root, name, ts)",
            "std::fs::create_dir_all(parent)",
            "base.unwrap_or(\"HEAD\")",
            "eprintln!(\"# ε-5 worktree-session new\")",
            "Command::new(\"git\")",
            ".arg(\"-C\")",
            ".arg(&repo_root)",
            ".args([\"worktree\", \"add\", \"-b\", &branch])",
            ".arg(&path)",
            ".arg(base_ref)",
            "if !out.status.success()",
            "git worktree add failed:",
            "if !out.stdout.is_empty()",
            "eprint!(\"{}\", String::from_utf8_lossy(&out.stdout))",
            "eprintln!(\"  ✓ worktree created\")",
            "println!(\"{}\", path.display())",
        ],
    );
}

#[test]
fn list_rejects_git_failure_before_view_and_owns_empty_diagnostic() {
    ordered(
        root_function("run_worktree_session_list"),
        &[
            "std::env::var(\"AGENT_BRIDGE_REPO\")",
            "[\"rev-parse\", \"--show-toplevel\"]",
            ".args([\"worktree\", \"list\", \"--porcelain\"])",
            "if !out.status.success()",
            "git worktree list failed:",
            "render_session_rows(&out.stdout)",
            "if shown == 0",
            "(no session worktrees under {})",
            "repo_root.join(\".worktrees\").display()",
        ],
    );
    assert!(!VIEW.contains("no session worktrees under"));
}
