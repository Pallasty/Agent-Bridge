//! agent-bridge daemon — Unix socket JSON-RPC server.
//!
//! Routes incoming RPC calls to backend traits (Notifier, AgentRuntime, ...).

pub mod anthropic_api;
pub mod avatar_alert;
pub mod avatar_cortex;
pub mod avatar_health;
pub mod avatar_seed;
pub mod avatar_surface;
pub mod bootstrap_bfs;
pub mod bootstrap_transitions;
pub mod brave_api;
pub mod c3_self_check;
pub mod cloudflare_api;
pub mod context_budget;
pub mod creds;
pub mod curate;
pub mod daemon_http;
pub mod dream_replay;
pub mod event_spine;
pub mod github_api;
pub mod gitlab_api;
pub mod hub;
pub mod ide;
pub mod instinct;
pub mod llm_client;
pub mod locks;
pub mod mcp_tools;
pub mod notion_api;
pub mod openai_api;
pub mod palace_viewer;
pub mod peer_client;
pub mod pet_presence;
pub mod pet_state;
pub mod present;
pub mod present_approval;
pub mod present_ingest;
pub mod project;
pub mod remote_steer;
pub mod rescue;
pub mod router;
pub mod security;
pub mod server;
pub mod session_handoff;
pub mod skills;
pub mod socket_path;
pub mod sync;
pub mod tailscale_api;
pub mod tool_atlas;
pub mod warp_actions;
pub mod warp_scheme;

pub use hub::Hub;
pub use mcp_tools::build_registry;
pub use router::Router;
pub use server::serve;
pub use socket_path::default_socket_path;
