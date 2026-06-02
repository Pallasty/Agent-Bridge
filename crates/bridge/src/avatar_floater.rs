//! Linux avatar floater launch helpers.
//!
//! The first Linux body backend is intentionally modest: reuse the read-only
//! daemon HTTP renderer route and open it in a small browser app window. Native
//! transparency/layer-shell can come later without changing the state contract.

use std::path::PathBuf;

pub const LINUX_RENDERER_TITLE: &str = "Linux Codex Avatar Renderer";

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct LinuxFloaterOptions {
    pub base_url: String,
    pub project: Option<String>,
    pub role: Option<String>,
    pub include_stale: bool,
    pub width: u32,
    pub height: u32,
    pub browser: Option<String>,
    pub transparent: bool,
}

pub fn linux_renderer_url(opts: &LinuxFloaterOptions) -> String {
    let base = opts.base_url.trim_end_matches('/');
    let mut query = Vec::new();
    if let Some(project) = opts.project.as_deref().and_then(non_empty) {
        query.push(format!("project={}", url_encode_query_value(project)));
    }
    if let Some(role) = opts.role.as_deref().and_then(non_empty) {
        query.push(format!("role={}", url_encode_query_value(role)));
    }
    if opts.include_stale {
        query.push("include_stale=true".to_string());
    }
    if opts.transparent {
        query.push("transparent=true".to_string());
    }

    let path = format!("{base}/avatar-surface/linux-renderer");
    if query.is_empty() {
        path
    } else {
        format!("{path}?{}", query.join("&"))
    }
}

pub fn browser_app_args(url: &str, width: u32, height: u32, _transparent: bool) -> Vec<String> {
    // Do not add Chrome's --enable-transparent-visuals here: on the current
    // Sway/Wayland Chrome build it exits before creating a toplevel. The
    // transparent renderer route is still used to probe compositor support.
    vec![
        format!(
            "--user-data-dir={}",
            default_user_data_dir().to_string_lossy()
        ),
        "--no-first-run".to_string(),
        "--no-default-browser-check".to_string(),
        format!("--app={url}"),
        format!("--window-size={width},{height}"),
        "--class=agent-bridge-avatar".to_string(),
        "--disable-features=Translate".to_string(),
    ]
}

pub fn sway_manage_command(title: &str, width: u32, height: u32, x: i32, y: i32) -> String {
    format!(
        "[title=\"{}\"] floating enable, sticky enable, border none, resize set width {} px height {} px, move position {} {}",
        sway_criteria_escape(title),
        width,
        height,
        x,
        y
    )
}

pub fn choose_browser(
    explicit_browser: Option<&str>,
    candidates: &[(String, bool)],
) -> Option<String> {
    explicit_browser
        .and_then(non_empty)
        .map(ToString::to_string)
        .or_else(|| {
            candidates
                .iter()
                .find_map(|(name, available)| available.then(|| name.clone()))
        })
}

pub fn browser_candidates_from_path() -> Vec<(String, bool)> {
    [
        "google-chrome",
        "chromium",
        "chromium-browser",
        "brave-browser",
        "microsoft-edge",
    ]
    .into_iter()
    .map(|name| (name.to_string(), executable_on_path(name)))
    .collect()
}

fn default_user_data_dir() -> PathBuf {
    std::env::var_os("XDG_RUNTIME_DIR")
        .map(PathBuf::from)
        .unwrap_or_else(std::env::temp_dir)
        .join(format!("agent-bridge-avatar-chrome-{}", std::process::id()))
}

fn non_empty(value: &str) -> Option<&str> {
    let trimmed = value.trim();
    (!trimmed.is_empty()).then_some(trimmed)
}

fn sway_criteria_escape(input: &str) -> String {
    input.replace('\\', "\\\\").replace('"', "\\\"")
}

fn executable_on_path(name: &str) -> bool {
    std::env::var_os("PATH")
        .map(|paths| {
            std::env::split_paths(&paths).any(|dir| {
                let path: PathBuf = dir.join(name);
                path.is_file()
            })
        })
        .unwrap_or(false)
}

fn url_encode_query_value(s: &str) -> String {
    let mut out = String::with_capacity(s.len());
    for &b in s.as_bytes() {
        let unreserved = b.is_ascii_alphanumeric()
            || b == b'-'
            || b == b'_'
            || b == b'.'
            || b == b'~'
            || b == b'/';
        if unreserved {
            out.push(b as char);
        } else {
            out.push_str(&format!("%{b:02X}"));
        }
    }
    out
}
