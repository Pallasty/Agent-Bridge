use ab_bridge::avatar_floater::{BackendRecommendation, CompositorInfo};
use anyhow::Result;

pub(crate) fn render_avatar_backend_probe_result(
    info: &CompositorInfo,
    rec: &BackendRecommendation,
    as_json: bool,
) -> Result<()> {
    if as_json {
        let payload = serde_json::json!({
            "surface": "linux_avatar_backend_probe",
            "compositor": {
                "session_type": info.session_type,
                "current_desktop": info.current_desktop,
                "has_wayland_display": info.has_wayland_display,
                "wlroots_signal": info.wlroots_signal,
            },
            "recommendation": {
                "backend": rec.backend.as_str(),
                "transparency_available": rec.transparency_available,
                "reason": rec.reason,
            },
            "read_only": true,
        });
        println!("{}", serde_json::to_string_pretty(&payload)?);
    } else {
        println!("avatar backend probe (read-only)");
        println!(
            "  session_type    : {}",
            info.session_type.as_deref().unwrap_or("?")
        );
        println!(
            "  current_desktop : {}",
            info.current_desktop.as_deref().unwrap_or("?")
        );
        println!("  wayland_display : {}", info.has_wayland_display);
        println!(
            "  wlroots_signal  : {}",
            info.wlroots_signal.as_deref().unwrap_or("none")
        );
        println!("  => backend      : {}", rec.backend.as_str());
        println!(
            "     transparency : {}",
            if rec.transparency_available {
                "available"
            } else {
                "NOT available (degraded browser floater)"
            }
        );
        println!("     reason       : {}", rec.reason);
    }
    Ok(())
}
