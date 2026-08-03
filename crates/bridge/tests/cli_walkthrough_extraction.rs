use std::{fs, path::PathBuf};

fn source(relative: &str) -> String {
    let path = PathBuf::from(env!("CARGO_MANIFEST_DIR")).join(relative);
    fs::read_to_string(path).unwrap_or_default()
}

#[test]
fn walkthrough_content_predicate_has_the_preregistered_private_cli_boundary() {
    let cli = source("src/cli/mod.rs");
    let module = source("src/cli/walkthrough.rs");
    let composition_root = source("src/main.rs");

    assert!(
        cli.contains("mod walkthrough;")
            && cli.contains("pub(super) use walkthrough::walkthrough_region_has_content;"),
        "cli must declare and re-export the private Walkthrough content predicate"
    );
    assert!(
        module.contains("pub(crate) fn walkthrough_region_has_content(html: &str) -> bool"),
        "cli::walkthrough must own the completed-HTML content predicate"
    );
    assert!(
        !composition_root.contains("fn walkthrough_region_has_content(html: &str)"),
        "main.rs must not continue to own the pure content predicate"
    );

    let executor_start = composition_root
        .find("fn run_walkthrough(")
        .expect("Walkthrough executor start");
    let executor_end = composition_root[executor_start..]
        .find("\nasync fn run_avatar_surface(")
        .map(|offset| executor_start + offset)
        .expect("Walkthrough executor end");
    let executor = &composition_root[executor_start..executor_end];

    for retained in [
        "doc_arg == \"-\"",
        "std::io::stdin()",
        "std::fs::read_to_string(doc_arg)",
        "serde_json::from_str(&raw)",
        "presentations_dir()",
        "write_walkthrough_artifact(&dir, &doc, title, None)",
        "std::fs::read_to_string(&path)",
        "extract_ab_payload(&html)",
        "cli::walkthrough_region_has_content(&html)",
        "let self_check = payload_ok && region_has_content;",
        "if as_json",
        "println!",
        "anyhow::bail!",
        "Ok(())",
    ] {
        assert!(
            executor.contains(retained),
            "main.rs must retain Walkthrough authority/order marker {retained}"
        );
    }

    assert!(
        composition_root.contains("Walkthrough {")
            && composition_root.contains("if let Cmd::Walkthrough { doc, title, json } = &cmd")
            && composition_root.contains("return run_walkthrough(doc, title.as_deref(), *json);"),
        "main.rs must retain Walkthrough schema and early dispatch custody"
    );

    for forbidden in [
        "std::env",
        "std::fs",
        "std::io",
        "std::path",
        "PathBuf",
        "serde_json",
        "Value",
        "presentations_dir",
        "write_walkthrough_artifact",
        "extract_ab_payload",
        "print!",
        "println!",
        "anyhow",
        "Result",
        "async",
        "tokio",
        "Command::new",
        "SqliteStore",
        "StateStore",
        "Hub",
    ] {
        assert!(
            !module.contains(forbidden),
            "cli::walkthrough must not absorb {forbidden} authority"
        );
    }
}
