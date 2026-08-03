use std::{fs, path::PathBuf};

fn source(relative: &str) -> String {
    let path = PathBuf::from(env!("CARGO_MANIFEST_DIR")).join(relative);
    fs::read_to_string(path).unwrap_or_default()
}

#[test]
fn shell_init_snippet_has_the_preregistered_private_cli_boundary() {
    let cli = source("src/cli/mod.rs");
    let module = source("src/cli/shell_init.rs");
    let composition_root = source("src/main.rs");

    assert!(
        cli.contains("mod shell_init;")
            && cli.contains("pub(super) use shell_init::shell_init_snippet;"),
        "cli must declare and re-export the private ShellInit snippet mapping"
    );
    assert!(
        module.contains("pub(crate) fn shell_init_snippet(shell: ShellKind) -> &'static str"),
        "cli::shell_init must own the static ShellKind-to-snippet mapping"
    );
    assert!(
        !composition_root.contains("fn shell_init_snippet(shell: ShellKind)"),
        "main.rs must not continue to own the static snippet mapping"
    );
    assert!(
        composition_root.contains("enum ShellKind")
            && composition_root.contains("ShellInit {")
            && composition_root.contains("if let Cmd::ShellInit { shell } = &cmd")
            && composition_root.contains("print!(\"{}\", cli::shell_init_snippet(*shell));")
            && composition_root.contains("return Ok(());"),
        "main.rs must retain ShellInit schema, ShellKind, early dispatch, stdout, and return custody"
    );

    for forbidden in [
        "print!",
        "println!",
        "std::env",
        "std::fs",
        "std::io",
        "std::process",
        "Command::new",
        "SqliteStore",
        "StateStore",
        "Hub",
        "ab_terminal",
        "tokio",
        "reqwest",
        "launchctl",
    ] {
        assert!(
            !module.contains(forbidden),
            "cli::shell_init must not absorb {forbidden} authority"
        );
    }
}
