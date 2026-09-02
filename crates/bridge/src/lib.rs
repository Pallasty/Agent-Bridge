#![recursion_limit = "256"]

//! agent-bridge daemon — Unix socket JSON-RPC server.
//!
//! Routes incoming RPC calls to backend traits (Notifier, AgentRuntime, ...).

pub mod a2ui;
/// Pure AG-UI 0.0.57 projection. This module has no MCP registration, I/O,
/// persistence, lease, policy, or execution authority.
pub mod ag_ui_readonly_projection;
pub mod agent_spawn_governor;
pub mod agent_task_contract;
pub mod agent_task_outcome;
pub mod agent_world_trajectory;
pub mod anthropic_api;
pub mod avatar_alert;
pub mod avatar_asset_audit;
pub mod avatar_asset_compile;
pub mod avatar_cortex;
pub mod avatar_floater;
pub mod avatar_focus_follow;
pub mod avatar_focus_observer;
pub mod avatar_health;
pub mod avatar_live_observation;
pub mod avatar_live_voice;
pub mod avatar_native;
pub mod avatar_renderer;
pub mod avatar_seed;
pub mod avatar_surface;
pub mod biocortex_capability_ledger;
pub mod biocortex_composed_limit_cycle;
pub mod biocortex_relevance_eval;
pub mod biocortex_shadow;
pub mod body_observation;
pub mod body_telemetry;
pub mod bootstrap_bfs;
pub mod bootstrap_transitions;
pub mod brave_api;
pub mod browser_lite;
pub mod build_identity;
pub mod c3_self_check;
pub mod cloudflare_api;
pub mod coactivation_tick;
pub mod code_review_context;
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
pub mod effect_inventory;
pub mod embedding_dim_guard;
pub mod embodiment_projection;
/// Default-off P4 runtime gate; no MCP registration or adapter execution.
#[cfg(feature = "embodiment-runtime-p4")]
pub mod embodiment_runtime;
#[cfg(all(
    feature = "episode-observation-c2c-keychain-macos-runtime",
    target_os = "macos"
))]
pub mod episode_observation_c2c_keychain_macos_runtime;
#[cfg(feature = "episode-observation-c2c-keychain-macos-live-lab")]
pub(crate) mod episode_observation_c2c_live_lab_diagnostics;
#[cfg(feature = "episode-observation-c2c-runtime-assembly-synthetic")]
pub(crate) mod episode_observation_c2c_runtime_assembly_synthetic;
/// Default-off Slice C1 orchestration seam. No store adapter or runtime caller
/// is provided by this feature.
#[cfg(feature = "episode-observation-slice-c1")]
pub(crate) mod episode_observation_curation_batch;
#[cfg(feature = "episode-observation-slice-c2-synthetic")]
pub(crate) mod episode_observation_curation_batch_c2_synthetic;
pub mod event_spine;
#[cfg(feature = "g14-wasi-component-runtime")]
pub mod g14_component_runtime;
pub mod github_api;
pub mod gitlab_api;
pub mod gos_lite;
pub mod hub;
pub mod ide;
pub mod instinct;
#[cfg(all(unix, feature = "invocation-guardian-v2-canary"))]
pub mod invocation_guardian_canary;
#[cfg(unix)]
pub mod invocation_guardian_client;
#[cfg(unix)]
pub mod invocation_guardian_protocol;
#[cfg(unix)]
#[cfg_attr(not(test), allow(dead_code))]
pub(crate) mod invocation_guardian_protocol_v2;
#[cfg(all(unix, feature = "invocation-guardian-v2-protected-witness-contract"))]
pub(crate) mod invocation_guardian_protected_witness_v2;
#[cfg(all(unix, feature = "invocation-guardian-v2-provider-lab"))]
pub(crate) mod invocation_guardian_provider_lab_v2;
#[cfg(unix)]
#[cfg_attr(not(test), allow(dead_code))]
pub(crate) mod invocation_guardian_receipt_v2;
#[cfg(unix)]
pub mod invocation_guardian_service;
pub mod invocation_lease;
#[cfg(unix)]
#[cfg_attr(not(test), allow(dead_code))]
#[cfg(feature = "invocation-guardian-v2-canary")]
pub mod invocation_lease_scope;
#[cfg(all(unix, not(feature = "invocation-guardian-v2-canary")))]
#[cfg_attr(not(test), allow(dead_code))]
pub(crate) mod invocation_lease_scope;
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
/// Read-only client and verifier for the bounded Android companion LAN/IMU
/// protocol. This module does not discover, provision, start, or actuate a
/// mobile device.
pub mod mobile_companion;
/// Ephemeral, consent-gated, read-only projection sessions for mobile nodes.
pub mod mobile_projection;
pub mod notion_api;
pub mod openai_api;
pub mod operator_request;
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
pub mod resident_cognition;
pub mod resident_m2_shadow;
pub mod resident_owner_evaluation;
pub mod resident_risk_policy;
pub mod resident_wake_journal;
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
pub(crate) mod story_contract;
/// Dormant S630 durable replay composition; synthetic tests only.
#[cfg(target_os = "linux")]
#[cfg_attr(not(test), allow(dead_code))]
pub(crate) mod story_render_durable_synthetic_composition;
/// Dormant S626/S627 fixed provider and replay ledger; no real authority or I/O.
#[cfg(target_os = "linux")]
#[cfg_attr(not(test), allow(dead_code))]
pub(crate) mod story_render_fixed_synthetic_provider;
/// Dormant S635 generic Guardian entrypoint; no product entrypoint is wired.
#[cfg(target_os = "linux")]
#[cfg_attr(not(test), allow(dead_code))]
pub(crate) mod story_render_guardian;
/// Dormant S635 ABG2 and sealed Worker plan protocol; no runtime caller.
#[cfg(target_os = "linux")]
#[cfg_attr(not(test), allow(dead_code))]
pub(crate) mod story_render_guardian_protocol;
/// Default-off S635 GuardianV2 Host supervision; synthetic configuration only.
#[cfg(target_os = "linux")]
#[cfg_attr(not(test), allow(dead_code))]
pub(crate) mod story_render_guardian_supervision;
/// Dormant S629 file-backed replay continuity; isolated tests only.
#[cfg(target_os = "linux")]
#[cfg_attr(not(test), allow(dead_code))]
pub(crate) mod story_render_replay_continuity_file_synthetic;
/// Dormant S628 persistence seam and synthetic reopened-handle state machine.
#[cfg(target_os = "linux")]
#[cfg_attr(not(test), allow(dead_code))]
pub(crate) mod story_render_replay_continuity_synthetic;
/// Dormant S623 synthetic Supervisor; no Worker, MCP, or deployment caller.
#[cfg(target_os = "linux")]
#[cfg_attr(not(test), allow(dead_code))]
pub(crate) mod story_render_supervisor;
#[cfg(target_os = "linux")]
#[cfg_attr(not(test), allow(dead_code))]
pub(crate) mod story_render_synthetic_admission;
/// Dormant S624 synthetic composition; no authority, MCP, or runtime caller.
#[cfg(target_os = "linux")]
#[cfg_attr(not(test), allow(dead_code))]
pub(crate) mod story_render_synthetic_composition;
pub mod sync;
pub mod tailscale_api;
pub mod tool_atlas;
pub(crate) mod tool_diagnostics;
pub mod trigger_recall_opt_in;
pub mod warp_actions;
pub mod warp_scheme;
pub mod workflow_feedback;
pub mod workload_receipt_reconciliation;
pub mod world_tools;

pub use hub::Hub;
pub use mcp_tools::build_registry;
pub use router::Router;
pub use server::serve;
pub use socket_path::default_socket_path;
