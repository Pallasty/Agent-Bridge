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

// ─── Backend selection (LCC-F1) ─────────────────────────────────────────────
//
// DESIGN-v26 verified true compositor transparency only on the native
// Wayland `wlr-layer-shell` ARGB8888 path (slice 7), and proved the browser
// app-window path CANNOT do real alpha on this host (slice 6: opaque dark
// surface). That leaves a portability gap: on non-wlroots compositors there is
// no verified transparent backend. These helpers turn that gap from a *silent*
// blind spot into an explicit, inspectable verdict — env-only, read-only, no
// process spawn or compositor IPC.

/// Which Linux body backend can satisfy the transparent-background requirement
/// on the detected compositor.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum AvatarBackend {
    /// Native Wayland `wlr-layer-shell` ARGB8888 — true compositor
    /// transparency. Verified only on wlroots compositors (DESIGN-v26 slice 7).
    NativeTransparent,
    /// Browser app-window floater — functional but NOT truly transparent on
    /// this path (DESIGN-v26 slice 6). The honest degraded fallback.
    BrowserDegraded,
}

impl AvatarBackend {
    pub fn as_str(self) -> &'static str {
        match self {
            AvatarBackend::NativeTransparent => "native_transparent",
            AvatarBackend::BrowserDegraded => "browser_degraded",
        }
    }
}

/// What we can learn about the current desktop session from env vars alone
/// (no spawning, no compositor IPC). All read-only.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct CompositorInfo {
    /// `XDG_SESSION_TYPE` (e.g. "wayland", "x11", "tty"), lowercased.
    pub session_type: Option<String>,
    /// `XDG_CURRENT_DESKTOP` token, lowercased (may be colon-separated).
    pub current_desktop: Option<String>,
    /// True when `WAYLAND_DISPLAY` is set.
    pub has_wayland_display: bool,
    /// The wlroots-family signal that was found (env var name or desktop
    /// token), or `None` when no wlroots/layer-shell signal is present.
    pub wlroots_signal: Option<String>,
}

/// A backend verdict with an inspectable reason — never a silent choice.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct BackendRecommendation {
    pub backend: AvatarBackend,
    pub transparency_available: bool,
    pub reason: String,
}

/// wlroots compositors known to implement `wlr-layer-shell` + ARGB8888 (the
/// path DESIGN-v26 verified). Conservative on purpose: KDE/KWin also supports
/// layer-shell, but it is left out until verified on this project so we never
/// *claim* unverified alpha. GNOME/Mutter is intentionally absent — it lacks
/// `wlr-layer-shell`.
const WLROOTS_DESKTOPS: &[&str] = &["sway", "hyprland", "river", "wayfire", "labwc", "wlroots"];

fn env_lower(key: &str) -> Option<String> {
    std::env::var(key)
        .ok()
        .map(|v| v.trim().to_lowercase())
        .filter(|s| !s.is_empty())
}

/// Detect the current compositor from env only. Pure w.r.t. the process
/// environment; spawns nothing.
pub fn detect_compositor() -> CompositorInfo {
    let current_desktop = env_lower("XDG_CURRENT_DESKTOP");
    let wlroots_signal = compositor_wlroots_signal(
        std::env::var_os("SWAYSOCK").is_some(),
        std::env::var_os("HYPRLAND_INSTANCE_SIGNATURE").is_some(),
        current_desktop.as_deref(),
    );
    CompositorInfo {
        session_type: env_lower("XDG_SESSION_TYPE"),
        current_desktop,
        has_wayland_display: std::env::var_os("WAYLAND_DISPLAY").is_some(),
        wlroots_signal,
    }
}

/// Pure core of wlroots detection, split out for testing without touching the
/// process environment. Precedence: SWAYSOCK > Hyprland signature > a known
/// wlroots token inside (possibly colon-separated) `XDG_CURRENT_DESKTOP`.
pub fn compositor_wlroots_signal(
    has_swaysock: bool,
    has_hyprland_sig: bool,
    current_desktop: Option<&str>,
) -> Option<String> {
    if has_swaysock {
        return Some("SWAYSOCK".to_string());
    }
    if has_hyprland_sig {
        return Some("HYPRLAND_INSTANCE_SIGNATURE".to_string());
    }
    current_desktop.and_then(|d| {
        d.split(':')
            .map(|t| t.trim())
            .find(|tok| WLROOTS_DESKTOPS.contains(tok))
            .map(|tok| format!("XDG_CURRENT_DESKTOP={tok}"))
    })
}

/// Choose a body backend from detected compositor info, with a reason string.
/// Pure + total: every environment gets an explicit verdict (no silent gap).
pub fn recommend_backend(info: &CompositorInfo) -> BackendRecommendation {
    let on_wayland =
        info.has_wayland_display || info.session_type.as_deref() == Some("wayland");

    if let Some(sig) = info.wlroots_signal.as_deref() {
        if on_wayland {
            return BackendRecommendation {
                backend: AvatarBackend::NativeTransparent,
                transparency_available: true,
                reason: format!(
                    "wlroots signal ({sig}) on Wayland → wlr-layer-shell ARGB8888 \
                     (transparency verified, DESIGN-v26 slice 7)"
                ),
            };
        }
        return BackendRecommendation {
            backend: AvatarBackend::BrowserDegraded,
            transparency_available: false,
            reason: format!(
                "wlroots token ({sig}) but no Wayland display → cannot bind \
                 layer-shell; browser floater (opaque)"
            ),
        };
    }

    let env_desc = info
        .current_desktop
        .clone()
        .or_else(|| info.session_type.clone())
        .unwrap_or_else(|| "unknown".to_string());
    BackendRecommendation {
        backend: AvatarBackend::BrowserDegraded,
        transparency_available: false,
        reason: format!(
            "no wlroots/layer-shell signal (desktop={env_desc}) → transparent \
             native backend unverified here; browser floater (opaque, DESIGN-v26 \
             slice 6). GNOME/Mutter lacks wlr-layer-shell; KDE/X11 alpha not yet \
             verified by this project."
        ),
    }
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

#[cfg(test)]
mod tests {
    use super::*;

    fn info(
        session_type: Option<&str>,
        current_desktop: Option<&str>,
        has_wayland_display: bool,
        wlroots_signal: Option<&str>,
    ) -> CompositorInfo {
        CompositorInfo {
            session_type: session_type.map(String::from),
            current_desktop: current_desktop.map(String::from),
            has_wayland_display,
            wlroots_signal: wlroots_signal.map(String::from),
        }
    }

    #[test]
    fn wlroots_signal_precedence_swaysock_first() {
        // SWAYSOCK wins even if Hyprland sig + a desktop token are also present.
        assert_eq!(
            compositor_wlroots_signal(true, true, Some("hyprland")),
            Some("SWAYSOCK".to_string())
        );
    }

    #[test]
    fn wlroots_signal_from_colon_separated_desktop() {
        // XDG_CURRENT_DESKTOP can be "sway:wlroots" etc.
        assert_eq!(
            compositor_wlroots_signal(false, false, Some("sway:wlroots")),
            Some("XDG_CURRENT_DESKTOP=sway".to_string())
        );
        assert_eq!(
            compositor_wlroots_signal(false, false, Some("hyprland")),
            Some("XDG_CURRENT_DESKTOP=hyprland".to_string())
        );
    }

    #[test]
    fn wlroots_signal_absent_for_non_wlroots() {
        assert_eq!(compositor_wlroots_signal(false, false, Some("gnome")), None);
        assert_eq!(compositor_wlroots_signal(false, false, Some("kde")), None);
        assert_eq!(compositor_wlroots_signal(false, false, None), None);
    }

    #[test]
    fn wlroots_on_wayland_picks_native_transparent() {
        let rec = recommend_backend(&info(
            Some("wayland"),
            Some("sway"),
            true,
            Some("SWAYSOCK"),
        ));
        assert_eq!(rec.backend, AvatarBackend::NativeTransparent);
        assert!(rec.transparency_available);
    }

    #[test]
    fn gnome_wayland_degrades_to_browser_no_transparency() {
        // GNOME/Mutter: Wayland but no wlr-layer-shell → honest degraded.
        let rec = recommend_backend(&info(Some("wayland"), Some("gnome"), true, None));
        assert_eq!(rec.backend, AvatarBackend::BrowserDegraded);
        assert!(!rec.transparency_available);
        assert!(rec.reason.contains("GNOME") || rec.reason.contains("unverified"));
    }

    #[test]
    fn x11_degrades_to_browser() {
        let rec = recommend_backend(&info(Some("x11"), Some("gnome"), false, None));
        assert_eq!(rec.backend, AvatarBackend::BrowserDegraded);
        assert!(!rec.transparency_available);
    }

    #[test]
    fn wlroots_token_without_wayland_degrades() {
        // wlroots desktop token but no Wayland display → cannot bind layer-shell.
        let rec = recommend_backend(&info(
            None,
            Some("sway"),
            false,
            Some("XDG_CURRENT_DESKTOP=sway"),
        ));
        assert_eq!(rec.backend, AvatarBackend::BrowserDegraded);
        assert!(!rec.transparency_available);
    }

    #[test]
    fn unknown_environment_still_gets_a_verdict() {
        // No silent gap: even a fully unknown env yields an explicit fallback.
        let rec = recommend_backend(&info(None, None, false, None));
        assert_eq!(rec.backend, AvatarBackend::BrowserDegraded);
        assert!(!rec.transparency_available);
        assert!(!rec.reason.is_empty());
    }
}
