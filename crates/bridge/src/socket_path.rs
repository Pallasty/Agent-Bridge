use std::path::PathBuf;

/// Default control socket path.
///
/// Linux: `$XDG_RUNTIME_DIR/agent-bridge/bridge.sock` when available.
/// macOS: `$TMPDIR/agent-bridge/bridge.sock` (per-user temp, set by launchd).
/// Fallback: `/tmp/agent-bridge-{uid}/bridge.sock`.
pub fn default_socket_path() -> PathBuf {
    // Linux: XDG_RUNTIME_DIR is the proper home for runtime sockets.
    #[cfg(target_os = "linux")]
    if let Ok(runtime) = std::env::var("XDG_RUNTIME_DIR") {
        let mut p = PathBuf::from(runtime);
        p.push("agent-bridge");
        p.push("bridge.sock");
        return p;
    }

    // macOS: launchd always sets TMPDIR to a per-user directory.
    #[cfg(target_os = "macos")]
    if let Ok(tmpdir) = std::env::var("TMPDIR") {
        let mut p = PathBuf::from(tmpdir);
        p.push("agent-bridge");
        p.push("bridge.sock");
        return p;
    }

    // POSIX fallback: /tmp/agent-bridge-{uid}/bridge.sock
    let uid = unsafe { libc_geteuid() };
    PathBuf::from(format!("/tmp/agent-bridge-{uid}/bridge.sock"))
}

// Avoid pulling in the `libc` crate just for one call.
extern "C" {
    fn geteuid() -> u32;
}
#[inline]
unsafe fn libc_geteuid() -> u32 {
    geteuid()
}
