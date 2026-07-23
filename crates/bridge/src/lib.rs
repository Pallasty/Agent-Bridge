#![recursion_limit = "256"]

//! agent-bridge daemon — Unix socket JSON-RPC server.
//!
//! Routes incoming RPC calls to backend traits (Notifier, AgentRuntime, ...).

pub mod agent_task_contract;
pub mod operator_request;
pub mod anthropic_api;
pub mod avatar_alert;
pub mod avatar_cortex;
pub mod avatar_floater;
pub mod avatar_health;
pub mod avatar_native;
pub mod avatar_renderer;
pub mod avatar_seed;
pub mod avatar_surface;
pub mod biocortex_capability_ledger;
pub mod biocortex_composed_limit_cycle;
pub mod biocortex_relevance_eval;
pub mod biocortex_shadow;
pub mod bootstrap_bfs;
pub mod bootstrap_transitions;
pub mod brave_api;
pub mod browser_lite;
pub mod build_identity;
pub mod c3_self_check;
pub mod cloudflare_api;
pub mod context_budget;
/// Pure, shadow-only admission contract for typed context lanes.
#[cfg_attr(not(test), allow(dead_code))]
pub(crate) mod context_lane;
pub mod continuity;
pub mod creds;
pub mod curate;
pub mod daemon_http;
pub mod dream_digest;
pub mod dream_distill;
pub mod dream_replay;
pub mod embedding_dim_guard;
/// Default-off Slice C1 orchestration seam. No store adapter or runtime caller
/// is provided by this feature.
#[cfg(feature = "episode-observation-slice-c1")]
pub(crate) mod episode_observation_curation_batch;
#[cfg(feature = "episode-observation-slice-c2-synthetic")]
pub(crate) mod episode_observation_curation_batch_c2_synthetic;
#[cfg(feature = "episode-observation-c2c-runtime-assembly-synthetic")]
pub(crate) mod episode_observation_c2c_runtime_assembly_synthetic;
#[cfg(all(
    feature = "episode-observation-c2c-keychain-macos-runtime",
    target_os = "macos"
))]
pub mod episode_observation_c2c_keychain_macos_runtime;
pub mod event_spine;
pub mod github_api;
pub mod gitlab_api;
pub mod gos_lite;
pub mod hub;
#[cfg(feature = "g14-wasi-component-runtime")]
pub mod g14_component_runtime;
pub mod ide;
pub mod instinct;
pub mod llm_client;
pub mod locks;
pub mod lswr_interaction_feedback;
pub mod lswr_outcome_admission;
pub mod lswr_present;
pub mod lswr_snapshot_bridge;
pub mod lswr_snapshot_consumer;
pub mod lswr_snapshot_display;
pub mod lswr_snapshot_report;
pub mod lswr_snapshot_report_acceptance;
pub mod lswr_snapshot_report_packet;
pub mod lswr_snapshot_wrapper_descriptor;
pub mod lswr_snapshot_wrapper_exposure_dry_run;
pub mod lswr_snapshot_wrapper_preflight_report;
pub mod mcp_tools;
/// Default-off, synthetic-only one-shot adapter; no runtime caller is wired.
#[cfg(feature = "temporal-evidence-s4-synthetic")]
#[cfg_attr(not(test), allow(dead_code))]
pub(crate) mod memory_temporal_evidence_adapter_v1;
/// Default-off S5 source-artifact binding; no transport or runtime caller.
#[cfg(feature = "temporal-evidence-s5-candidate-synthetic")]
#[cfg_attr(not(test), allow(dead_code))]
pub(crate) mod memory_track_b_candidate_evidence_v1;
/// Internal raw-envelope resolver; no MCP, transport, or cross-repository API.
#[cfg_attr(not(test), allow(dead_code))]
pub(crate) mod memory_truth;
/// Fail-closed admission gate between raw store diagnostics and truth projection.
#[cfg_attr(not(test), allow(dead_code))]
pub(crate) mod memory_truth_adapter;
pub mod notion_api;
pub mod openai_api;
pub mod orphan_reaper;
pub mod outcome_valence;
pub mod palace_viewer;
pub mod peer_client;
pub mod pet_ground;
pub mod pet_presence;
pub mod pet_state;
pub mod present;
pub mod present_approval;
pub mod present_ingest;
pub mod project;
pub mod project_identity;
pub mod remote_embed;
pub mod remote_steer;
pub mod rescue;
pub mod retrieval_outcome;
pub mod router;
pub mod security;
pub mod seed_substrate;
pub mod semantic_event;
pub mod server;
pub mod session_handoff;
pub mod shadow_cortex;
pub mod skills;
pub mod socket_path;
pub mod sync;
pub mod tailscale_api;
pub mod tool_atlas;
pub(crate) mod tool_diagnostics;
pub mod trigger_recall_opt_in;
pub mod warp_actions;
pub mod warp_scheme;
pub mod workflow_feedback;
pub mod world_tools;

pub use hub::Hub;
pub use mcp_tools::build_registry;
pub use router::Router;
pub use server::serve;
pub use socket_path::default_socket_path;
