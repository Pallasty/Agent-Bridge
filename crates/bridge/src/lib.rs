//! agent-bridge daemon — Unix socket JSON-RPC server.
//!
//! Routes incoming RPC calls to backend traits (Notifier, AgentRuntime, ...).

pub mod bootstrap_bfs;
pub mod bootstrap_transitions;
pub mod c3_self_check;
pub mod context_budget;
pub mod creds;
pub mod locks;
pub mod rescue;
pub mod curate;
pub mod daemon_http;
pub mod dream_replay;
pub mod hub;
pub mod ide;
pub mod peer_client;
pub mod mcp_tools;
pub mod palace_viewer;
pub mod project;
pub mod router;
pub mod security;
pub mod server;
pub mod session_handoff;
pub mod socket_path;
pub mod anthropic_api;
pub mod openai_api;
pub mod llm_client;
pub mod brave_api;
pub mod cloudflare_api;
pub mod github_api;
pub mod gitlab_api;
pub mod notion_api;
pub mod tailscale_api;
pub mod warp_actions;
pub mod warp_scheme;

pub use hub::Hub;
pub use mcp_tools::build_registry;
pub use router::Router;
pub use server::serve;
pub use socket_path::default_socket_path;
