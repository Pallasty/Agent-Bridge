const ROOT: &str = include_str!("../src/main.rs");
const DISPLAY: &str = include_str!("../src/cli/avatar_presentation.rs");
const LIVE: &str = include_str!("../src/cli/avatar_live_view.rs");
const OBSERVER: &str = include_str!("../src/cli/avatar_observer_view.rs");

fn root_function(name: &str) -> &str {
    let start = ROOT.find(&format!("fn {name}(")).expect("root function");
    let tail = &ROOT[start..];
    &tail[..tail.find("\n}\n").expect("function end")]
}

fn ordered(source: &str, markers: &[&str]) {
    let mut rest = source;
    for marker in markers {
        let pos = rest
            .find(marker)
            .unwrap_or_else(|| panic!("missing/out-of-order {marker}"));
        rest = &rest[pos + marker.len()..];
    }
}

#[test]
fn presentation_modules_receive_values_without_live_authority() {
    for source in [DISPLAY, LIVE, OBSERVER] {
        for forbidden in [
            "std::fs",
            "std::process",
            "tokio::",
            "std::env::var",
            "SqliteStore",
            "StateStore",
            "&Hub",
            "SystemTime",
            "Instant::now",
            "read_pet_state(",
            "sync_pet_presence(",
            "read_sway_tree",
            "notify-send",
        ] {
            assert!(
                !source.contains(forbidden),
                "presentation acquired authority: {forbidden}"
            );
        }
    }
    for name in [
        "render_sprite_asset_audit",
        "render_sprite_asset_compile",
        "render_sprite_asset_contract",
        "render_focus_follow_plan",
        "render_focus_follow_recommendation",
        "render_focus_follow_prompt",
        "render_focus_follow_action",
        "render_focus_observer_json",
    ] {
        assert!(DISPLAY.contains(&format!("fn {name}(")));
        assert!(!ROOT.contains(&format!("fn {name}(")));
    }
    assert!(!ROOT.contains("\"surface\": \"linux_avatar_live_receipt\""));
    assert!(!ROOT.contains("\"surface\": \"linux_avatar_voice_observer_plan\""));
}

#[test]
fn asset_admission_and_write_order_remain_at_root() {
    ordered(
        root_function("run_avatar_sprite_asset_audit"),
        &[
            "audit_sprite_asset(",
            "render_sprite_asset_audit(",
            "if report.accepted",
            "sprite asset failed admission checks",
        ],
    );
    ordered(
        root_function("run_avatar_sprite_asset_compile"),
        &[
            "ensure!(!execute || confirm",
            "compile_sprite_atlas(",
            "render_sprite_asset_compile(",
        ],
    );
}

#[test]
fn focus_acquisition_action_and_prompt_error_order_remain_at_root() {
    ordered(
        root_function("run_avatar_focus_follow_plan"),
        &[
            "read_sway_tree_for_avatar().await?",
            "focus_follow_plan_from_sway_tree(",
            "render_focus_follow_plan(",
        ],
    );
    ordered(
        root_function("run_avatar_focus_follow_recommend"),
        &[
            "read_sway_tree_for_avatar().await?",
            "read_focus_follow_ack_target(",
            "focus_follow_recommendation(",
            "render_focus_follow_recommendation(",
        ],
    );
    ordered(
        root_function("run_avatar_focus_follow_action"),
        &[
            "execute_avatar_focus_follow_action(",
            ".await?",
            "render_focus_follow_action(",
        ],
    );
    ordered(
        root_function("run_avatar_focus_follow_prompt"),
        &[
            "read_sway_tree_for_avatar().await?",
            "std::fs::read(&receipt_path)",
            "focus_follow_prompt_preflight(",
            "if prompt.get(\"ready\")",
            "Command::new(\"notify-send\")",
            "if !output.status.success()",
            "if as_json",
            "return Ok(())",
            "std::fs::rename(&temp_path, &receipt_path)",
            "render_focus_follow_prompt(",
        ],
    );
}

#[test]
fn live_resources_and_clock_stay_at_composition_boundary() {
    ordered(
        root_function("run_avatar_linux_live"),
        &[
            "read_pet_state(",
            "detect_compositor()",
            "linux_live_plan(",
            "if dry_run",
            "if !native_compiled",
            "SqliteStore::open(",
            "sync_pet_presence(",
            "tokio::spawn(",
            "tokio::task::spawn_blocking(",
            "renderer_result.context(",
            "join Linux avatar live observation loop",
            "sync_pet_presence(",
            "started.elapsed()",
            "linux_live_receipt(",
            "render_linux_live_receipt(",
        ],
    );
    ordered(
        root_function("run_avatar_voice_observe"),
        &[
            "read_pet_state(",
            "voice_observer_plan(",
            "if dry_run",
            "if !ready",
            "Instant::now()",
            "run_linux_live_voice_feedback(",
            "started.elapsed()",
            "voice_observer_receipt(",
            "render_voice_observer_receipt(",
        ],
    );
    assert!(ROOT.contains("fn focus_observer_action_gate("));
    assert!(!OBSERVER.contains("fn focus_observer_action_gate("));
}

#[test]
fn startup_report_has_no_reconciliation_authority() {
    let report = include_str!("../src/cli/startup_report.rs");
    for forbidden in [
        "std::fs",
        "SqliteStore",
        "StateStore",
        "reconcile_workload_receipt_spool(",
        "acknowledge(",
    ] {
        assert!(!report.contains(forbidden));
    }
    assert!(!ROOT.contains("fn log_workload_receipt_reconciliation_report("));
    ordered(
        root_function("build_hub"),
        &[
            "SqliteStore::open(",
            "#[cfg(feature = \"r9-workload-receipts\")]",
            "reconcile_workload_receipt_spool(",
            "log_workload_receipt_reconciliation_report(",
            "auto_backend()",
        ],
    );
}
