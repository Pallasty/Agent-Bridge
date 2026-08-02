use std::process::{Command, Output};

const COMPOSITOR_ENV: [&str; 5] = [
    "XDG_SESSION_TYPE",
    "XDG_CURRENT_DESKTOP",
    "WAYLAND_DISPLAY",
    "SWAYSOCK",
    "HYPRLAND_INSTANCE_SIGNATURE",
];

fn run_backend_probe(extra_args: &[&str], env: &[(&str, &str)]) -> Output {
    let mut command = Command::new(env!("CARGO_BIN_EXE_agent-bridge"));
    command.args(["avatar", "backend-probe"]);
    command.args(extra_args);
    for key in COMPOSITOR_ENV {
        command.env_remove(key);
    }
    for (key, value) in env {
        command.env(key, value);
    }
    command.output().expect("run avatar backend-probe")
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

#[test]
fn avatar_backend_probe_unknown_environment_text_contract_is_exact() {
    let output = run_backend_probe(&[], &[]);
    assert_success_without_stderr(&output);
    assert_eq!(
        String::from_utf8(output.stdout).expect("utf-8 text output"),
        concat!(
            "avatar backend probe (read-only)\n",
            "  session_type    : ?\n",
            "  current_desktop : ?\n",
            "  wayland_display : false\n",
            "  wlroots_signal  : none\n",
            "  => backend      : browser_degraded\n",
            "     transparency : NOT available (degraded browser floater)\n",
            "     reason       : no wlroots/layer-shell signal (desktop=unknown) ",
            "→ transparent native backend unverified here; browser floater (opaque, ",
            "DESIGN-v26 slice 6). GNOME/Mutter lacks wlr-layer-shell; KDE/X11 alpha ",
            "not yet verified by this project.\n",
        )
    );
}

#[test]
fn avatar_backend_probe_unknown_environment_json_contract_is_exact() {
    let output = run_backend_probe(&["--json"], &[]);
    assert_success_without_stderr(&output);
    assert_eq!(
        String::from_utf8(output.stdout).expect("utf-8 JSON output"),
        concat!(
            "{\n",
            "  \"surface\": \"linux_avatar_backend_probe\",\n",
            "  \"compositor\": {\n",
            "    \"session_type\": null,\n",
            "    \"current_desktop\": null,\n",
            "    \"has_wayland_display\": false,\n",
            "    \"wlroots_signal\": null\n",
            "  },\n",
            "  \"recommendation\": {\n",
            "    \"backend\": \"browser_degraded\",\n",
            "    \"transparency_available\": false,\n",
            "    \"reason\": \"no wlroots/layer-shell signal (desktop=unknown) ",
            "→ transparent native backend unverified here; browser floater (opaque, ",
            "DESIGN-v26 slice 6). GNOME/Mutter lacks wlr-layer-shell; KDE/X11 alpha ",
            "not yet verified by this project.\"\n",
            "  },\n",
            "  \"read_only\": true\n",
            "}\n",
        )
    );
}

#[test]
fn avatar_backend_probe_wlroots_wayland_text_contract_is_exact() {
    let output = run_backend_probe(
        &[],
        &[
            ("XDG_SESSION_TYPE", "wayland"),
            ("XDG_CURRENT_DESKTOP", "sway"),
            ("WAYLAND_DISPLAY", "wayland-1"),
            ("SWAYSOCK", "/tmp/sway.sock"),
        ],
    );
    assert_success_without_stderr(&output);
    assert_eq!(
        String::from_utf8(output.stdout).expect("utf-8 text output"),
        concat!(
            "avatar backend probe (read-only)\n",
            "  session_type    : wayland\n",
            "  current_desktop : sway\n",
            "  wayland_display : true\n",
            "  wlroots_signal  : SWAYSOCK\n",
            "  => backend      : native_transparent\n",
            "     transparency : available\n",
            "     reason       : wlroots signal (SWAYSOCK) on Wayland → ",
            "wlr-layer-shell ARGB8888 (transparency verified, DESIGN-v26 slice 7)\n",
        )
    );
}

#[test]
fn avatar_backend_probe_help_contract_is_exact() {
    let output = run_backend_probe(&["--help"], &[]);
    assert_success_without_stderr(&output);
    assert_eq!(
        String::from_utf8(output.stdout).expect("utf-8 help output"),
        concat!(
            "Probe the compositor and report which avatar body backend can satisfy ",
            "transparency here (native wlr-layer-shell vs degraded browser). Env-only, ",
            "read-only — spawns nothing and controls nothing (LCC-F1)\n\n",
            "Usage: agent-bridge avatar backend-probe [OPTIONS]\n\n",
            "Options:\n",
            "      --json  Emit raw JSON instead of a human-readable summary\n",
            "  -h, --help  Print help\n",
        )
    );
}

#[test]
fn avatar_backend_probe_invalid_argument_error_contract_is_exact() {
    let output = run_backend_probe(&["--unexpected"], &[]);
    assert_eq!(output.status.code(), Some(2));
    assert_eq!(output.stdout, b"");
    assert_eq!(
        String::from_utf8(output.stderr).expect("utf-8 error output"),
        concat!(
            "error: unexpected argument '--unexpected' found\n\n",
            "Usage: agent-bridge avatar backend-probe [OPTIONS]\n\n",
            "For more information, try '--help'.\n",
        )
    );
}
