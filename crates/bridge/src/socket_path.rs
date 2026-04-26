use std::path::PathBuf;

/// Default control socket path.
///
/// `$XDG_RUNTIME_DIR/agent-bridge/bridge.sock` if available,
/// otherwise `/tmp/agent-bridge-{uid}/bridge.sock`.
pub fn default_socket_path() -> PathBuf {
    if let Ok(runtime) = std::env::var("XDG_RUNTIME_DIR") {
        let mut p = PathBuf::from(runtime);
        p.push("agent-bridge");
        p.push("bridge.sock");
        return p;
    }
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
