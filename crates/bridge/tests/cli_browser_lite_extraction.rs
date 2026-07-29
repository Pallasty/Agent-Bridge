use std::{fs, path::PathBuf};

fn source(relative: &str) -> String {
    let path = PathBuf::from(env!("CARGO_MANIFEST_DIR")).join(relative);
    fs::read_to_string(path).unwrap_or_default()
}

#[test]
fn browser_lite_has_the_preregistered_private_cli_boundary() {
    let cli = source("src/cli/mod.rs");
    let module = source("src/cli/browser_lite.rs");
    let composition_root = source("src/main.rs");

    assert!(
        cli.contains("mod browser_lite;"),
        "cli must declare a private browser_lite module"
    );
    assert!(
        module.contains("enum BrowserLiteOp")
            && module.contains("enum BrowserLiteBackend")
            && module.contains("fn run_browser_lite("),
        "cli::browser_lite must own schema and dispatch"
    );
    assert!(
        !composition_root.contains("enum BrowserLiteOp")
            && !composition_root.contains("enum BrowserLiteBackend"),
        "main.rs must not continue to own BrowserLite nested schema"
    );
    assert!(
        composition_root.contains("BrowserLite {")
            && composition_root.contains("run_browser_lite(op)"),
        "main.rs must retain the root command and delegate"
    );
    assert!(
        composition_root.contains("| Cmd::BrowserLite { .. }"),
        "main.rs must retain post-Hub exhaustiveness"
    );

    for forbidden in ["SqliteStore", "Hub", "ToolRegistry", "Cmd", "BioCortexOp"] {
        assert!(
            !module.contains(forbidden),
            "cli::browser_lite must not absorb {forbidden}"
        );
    }
}
