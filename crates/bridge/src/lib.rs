//! agent-bridge daemon — Unix socket JSON-RPC server.
//!
//! Routes incoming RPC calls to backend traits (Notifier, AgentRuntime, ...).

pub mod hub;
pub mod mcp_tools;
pub mod router;
pub mod server;
pub mod socket_path;

pub use hub::Hub;
pub use mcp_tools::build_registry;
pub use router::Router;
pub use server::serve;
pub use socket_path::default_socket_path;
