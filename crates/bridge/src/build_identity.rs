//! Compile-time package and source identity.

pub const PACKAGE_VERSION: &str = env!("CARGO_PKG_VERSION");
pub const GIT_SHA: &str = env!("AGENT_BRIDGE_BUILD_SHA");
pub const GIT_DESCRIBE: &str = env!("AGENT_BRIDGE_BUILD_DESCRIBE");
pub const LONG_VERSION: &str = concat!(
    env!("CARGO_PKG_VERSION"),
    " (",
    env!("AGENT_BRIDGE_BUILD_DESCRIBE"),
    "; ",
    env!("AGENT_BRIDGE_BUILD_SHA"),
    ")"
);
