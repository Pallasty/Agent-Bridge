//! agent-bridge daemon — Unix socket JSON-RPC server.
//!
//! Routes incoming RPC calls to backend traits (Notifier, AgentRuntime, ...).

pub mod context_budget;
pub mod curate;
pub mod hub;
pub mod mcp_tools;
pub mod project;
pub mod router;
pub mod server;
pub mod session_handoff;
pub mod socket_path;
pub mod warp_actions;

pub use hub::Hub;
pub use mcp_tools::build_registry;
pub use router::Router;
pub use server::serve;
pub use socket_path::default_socket_path;
