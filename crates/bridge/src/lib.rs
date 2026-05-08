//! agent-bridge daemon — Unix socket JSON-RPC server.
//!
//! Routes incoming RPC calls to backend traits (Notifier, AgentRuntime, ...).

pub mod context_budget;
pub mod creds;
pub mod curate;
pub mod daemon_http;
pub mod hub;
pub mod peer_client;
pub mod mcp_tools;
pub mod project;
pub mod router;
pub mod security;
pub mod server;
pub mod session_handoff;
pub mod socket_path;
pub mod github_api;
pub mod gitlab_api;
pub mod tailscale_api;
pub mod warp_actions;
pub mod warp_scheme;

pub use hub::Hub;
pub use mcp_tools::build_registry;
pub use router::Router;
pub use server::serve;
pub use socket_path::default_socket_path;
