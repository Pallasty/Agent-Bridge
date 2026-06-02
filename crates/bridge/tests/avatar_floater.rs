use ab_bridge::avatar_floater::{
    browser_app_args, choose_browser, linux_renderer_url, sway_manage_command, LinuxFloaterOptions,
};

#[test]
fn renderer_url_encodes_project_role_and_stale_flag() {
    let opts = LinuxFloaterOptions {
        base_url: "http://127.0.0.1:7878/".to_string(),
        project: Some("agent bridge".to_string()),
        role: Some("codex/main".to_string()),
        include_stale: true,
        width: 360,
        height: 520,
        browser: None,
        transparent: false,
    };

    let url = linux_renderer_url(&opts);

    assert_eq!(
        url,
        "http://127.0.0.1:7878/avatar-surface/linux-renderer?project=agent%20bridge&role=codex/main&include_stale=true"
    );
}

#[test]
fn renderer_url_omits_empty_optional_query_values() {
    let opts = LinuxFloaterOptions {
        base_url: "http://127.0.0.1:7878".to_string(),
        project: None,
        role: None,
        include_stale: false,
        width: 360,
        height: 520,
        browser: None,
        transparent: false,
    };

    let url = linux_renderer_url(&opts);

    assert_eq!(url, "http://127.0.0.1:7878/avatar-surface/linux-renderer");
}

#[test]
fn renderer_url_includes_transparent_flag_when_requested() {
    let opts = LinuxFloaterOptions {
        base_url: "http://127.0.0.1:7878".to_string(),
        project: Some("agent-bridge".to_string()),
        role: None,
        include_stale: true,
        width: 360,
        height: 520,
        browser: None,
        transparent: true,
    };

    let url = linux_renderer_url(&opts);

    assert_eq!(
        url,
        "http://127.0.0.1:7878/avatar-surface/linux-renderer?project=agent-bridge&include_stale=true&transparent=true"
    );
}

#[test]
fn browser_app_args_use_small_app_window() {
    let args = browser_app_args(
        "http://127.0.0.1:7878/avatar-surface/linux-renderer",
        360,
        520,
        false,
    );

    assert!(!args.contains(&"--new-window".to_string()));
    assert!(args.contains(&"--window-size=360,520".to_string()));
    assert!(args.contains(&"--class=agent-bridge-avatar".to_string()));
    assert!(args
        .iter()
        .any(|arg| arg.starts_with("--user-data-dir=")
            && arg.contains("agent-bridge-avatar-chrome-")));
    assert!(args.contains(&"--app=http://127.0.0.1:7878/avatar-surface/linux-renderer".to_string()));
}

#[test]
fn browser_app_args_avoid_chrome_transparent_visuals_flag_on_wayland() {
    let args = browser_app_args(
        "http://127.0.0.1:7878/avatar-surface/linux-renderer?transparent=true",
        360,
        520,
        true,
    );

    assert!(!args.contains(&"--enable-transparent-visuals".to_string()));
}

#[test]
fn sway_manage_command_targets_renderer_title_and_sets_pet_window_shape() {
    let command = sway_manage_command("Linux Codex Avatar Renderer", 360, 520, 3460, 180);

    assert!(command.contains("[title=\"Linux Codex Avatar Renderer\"]"));
    assert!(command.contains("floating enable"));
    assert!(command.contains("sticky enable"));
    assert!(command.contains("border none"));
    assert!(command.contains("resize set width 360 px height 520 px"));
    assert!(command.contains("move position 3460 180"));
}

#[test]
fn choose_browser_prefers_explicit_browser_then_available_candidate() {
    assert_eq!(
        choose_browser(Some("custom-browser"), &[]),
        Some("custom-browser".to_string())
    );
    assert_eq!(
        choose_browser(
            None,
            &[
                ("missing".to_string(), false),
                ("chromium".to_string(), true)
            ]
        ),
        Some("chromium".to_string())
    );
    assert_eq!(
        choose_browser(None, &[("missing".to_string(), false)]),
        None
    );
}
