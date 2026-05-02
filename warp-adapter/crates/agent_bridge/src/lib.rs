//! Warp-side Agent-Bridge adapter crate.
//!
//! This crate is the in-repo migration target for integrating Agent-Bridge
//! capabilities directly into Warp. The initial scope is protocol-first:
//! define stable request/response contracts and a backend trait that Warp
//! can implement incrementally.

pub mod protocol;

use std::path::PathBuf;

/// Default Unix socket path for local Agent-Bridge IPC.
///
/// We intentionally keep this under XDG runtime to avoid stale sockets and
/// cross-user leakage.
pub fn default_ipc_socket_path() -> PathBuf {
    if let Ok(runtime) = std::env::var("XDG_RUNTIME_DIR") {
        return PathBuf::from(runtime).join("warp-agent-bridge.sock");
    }
    std::env::temp_dir().join("warp-agent-bridge.sock")
}

