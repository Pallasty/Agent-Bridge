//! Compile-time package and source identity.

pub const PACKAGE_VERSION: &str = env!("CARGO_PKG_VERSION");
pub const GIT_SHA: &str = env!("AGENT_BRIDGE_BUILD_SHA");
pub const GIT_DESCRIBE: &str = env!("AGENT_BRIDGE_BUILD_DESCRIBE");
pub const R9_WORKLOAD_RECEIPTS_ENABLED: bool = cfg!(feature = "r9-workload-receipts");
#[cfg(feature = "r9-workload-receipts")]
pub const RUNTIME_PROFILE_MARKER: &str = "agent_bridge.runtime_profile.r9.v1";
#[cfg(not(feature = "r9-workload-receipts"))]
pub const RUNTIME_PROFILE_MARKER: &str = "agent_bridge.runtime_profile.maintenance.v1";
pub const LONG_VERSION: &str = concat!(
    env!("CARGO_PKG_VERSION"),
    " (",
    env!("AGENT_BRIDGE_BUILD_DESCRIBE"),
    "; ",
    env!("AGENT_BRIDGE_BUILD_SHA"),
    ")"
);
