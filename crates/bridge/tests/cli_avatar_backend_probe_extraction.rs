use std::{fs, path::PathBuf};

fn source(relative: &str) -> String {
    let path = PathBuf::from(env!("CARGO_MANIFEST_DIR")).join(relative);
    fs::read_to_string(path).unwrap_or_default()
}

#[test]
fn avatar_backend_probe_renderer_has_the_preregistered_private_cli_boundary() {
    let cli = source("src/cli/mod.rs");
    let module = source("src/cli/avatar.rs");
    let composition_root = source("src/main.rs");

    assert!(
        cli.contains("mod avatar;")
            && cli.contains("pub(super) use avatar::render_avatar_backend_probe_result;"),
        "cli must declare and re-export the private Avatar renderer"
    );
    assert!(
        module.contains("pub(crate) fn render_avatar_backend_probe_result("),
        "cli::avatar must own the completed BackendProbe result renderer"
    );
    assert!(
        !composition_root.contains("fn render_avatar_backend_probe_result("),
        "main.rs must not continue to own the completed-result renderer"
    );
    assert!(
        composition_root.contains("enum AvatarOp")
            && composition_root.contains("AvatarOp::BackendProbe { json: as_json }")
            && composition_root.contains("fn run_avatar_backend_probe(as_json: bool) -> Result<()>")
            && composition_root
                .contains("let info = ab_bridge::avatar_floater::detect_compositor();")
            && composition_root
                .contains("let rec = ab_bridge::avatar_floater::recommend_backend(&info);")
            && composition_root
                .contains("cli::render_avatar_backend_probe_result(&info, &rec, as_json)"),
        "main.rs must retain schema, dispatch, environment detection, recommendation, and invocation"
    );

    for forbidden in [
        "detect_compositor(",
        "recommend_backend(",
        "std::env",
        "SqliteStore",
        "std::fs",
        "Command::new",
        "launchctl",
        "heartbeat",
        "notification",
        "present_voice",
        "xiao_shu",
    ] {
        assert!(
            !module.contains(forbidden),
            "cli::avatar renderer must not absorb {forbidden} authority"
        );
    }
}
