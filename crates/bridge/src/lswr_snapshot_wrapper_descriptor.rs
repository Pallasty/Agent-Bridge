use crate::lswr_snapshot_display::LSWR_READONLY_BRIDGE_DISPLAY_MODEL_SCHEMA;
use crate::lswr_snapshot_report_acceptance::LSWR_READONLY_BRIDGE_ACCEPTANCE_MATRIX_SCHEMA;
use crate::lswr_snapshot_report_packet::LSWR_READONLY_BRIDGE_REPORT_PACKET_SCHEMA;
use serde::{Deserialize, Serialize};

pub const LSWR_READONLY_BRIDGE_WRAPPER_DESCRIPTOR_SCHEMA: &str =
    "agent_bridge.lswr.readonly_bridge_wrapper_descriptor.v0";

pub const LSWR_READONLY_BRIDGE_WRAPPER_NAME: &str = "lswr_readonly_bridge_display";

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct ReadOnlyBridgeWrapperDescriptor {
    pub schema: String,
    pub wrapper_name: String,
    pub state: String,
    pub purpose: String,
    pub schema_chain: WrapperSchemaChain,
    pub profile_gate: WrapperProfileGate,
    pub input_contract: WrapperInputContract,
    pub output_contract: WrapperOutputContract,
    pub safety_contract: WrapperSafetyContract,
    pub acceptance_contract: WrapperAcceptanceContract,
    pub next_steps: Vec<String>,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct WrapperSchemaChain {
    pub packet_schema: String,
    pub acceptance_schema: String,
    pub display_model_schema: String,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct WrapperProfileGate {
    pub current_exposure: String,
    pub candidate_tool_name: String,
    pub mcp_registry_change: bool,
    pub codex_essential_status: String,
    pub minimum_profile_after_registry: String,
    pub requires_separate_registry_change: bool,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct WrapperInputContract {
    pub mode: String,
    pub required_schema: String,
    pub requires_explicit_packet_payload: bool,
    pub accepts_host_path: bool,
    pub accepts_live_runtime: bool,
    pub accepts_gui_capture: bool,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct WrapperOutputContract {
    pub schema: String,
    pub contains_report_markdown: bool,
    pub contains_display_readback: bool,
    pub contains_mutating_handles: bool,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct WrapperSafetyContract {
    pub read_only: bool,
    pub mutation_surface: String,
    pub allowed_capabilities: Vec<String>,
    pub disallowed_capabilities: Vec<String>,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct WrapperAcceptanceContract {
    pub required_overall_verdict: String,
    pub required_display_status_label: String,
    pub required_display_status_tone: String,
    pub required_wrapper_ready: bool,
    pub required_matrix_gates: Vec<String>,
    pub review_sensitive_gates: Vec<String>,
    pub all_gate_verdict: String,
}

pub fn build_readonly_bridge_wrapper_descriptor() -> ReadOnlyBridgeWrapperDescriptor {
    ReadOnlyBridgeWrapperDescriptor {
        schema: LSWR_READONLY_BRIDGE_WRAPPER_DESCRIPTOR_SCHEMA.to_string(),
        wrapper_name: LSWR_READONLY_BRIDGE_WRAPPER_NAME.to_string(),
        state: "descriptor_only".to_string(),
        purpose: "Describe the future read-only UI/MCP wrapper boundary for LSWR report packets without registering a tool or reading live runtime state.".to_string(),
        schema_chain: WrapperSchemaChain {
            packet_schema: LSWR_READONLY_BRIDGE_REPORT_PACKET_SCHEMA.to_string(),
            acceptance_schema: LSWR_READONLY_BRIDGE_ACCEPTANCE_MATRIX_SCHEMA.to_string(),
            display_model_schema: LSWR_READONLY_BRIDGE_DISPLAY_MODEL_SCHEMA.to_string(),
        },
        profile_gate: WrapperProfileGate {
            current_exposure: "not_registered".to_string(),
            candidate_tool_name: LSWR_READONLY_BRIDGE_WRAPPER_NAME.to_string(),
            mcp_registry_change: false,
            codex_essential_status: "not_exposed".to_string(),
            minimum_profile_after_registry: "all".to_string(),
            requires_separate_registry_change: true,
        },
        input_contract: WrapperInputContract {
            mode: "explicit_report_packet_payload".to_string(),
            required_schema: LSWR_READONLY_BRIDGE_REPORT_PACKET_SCHEMA.to_string(),
            requires_explicit_packet_payload: true,
            accepts_host_path: false,
            accepts_live_runtime: false,
            accepts_gui_capture: false,
        },
        output_contract: WrapperOutputContract {
            schema: LSWR_READONLY_BRIDGE_DISPLAY_MODEL_SCHEMA.to_string(),
            contains_report_markdown: true,
            contains_display_readback: true,
            contains_mutating_handles: false,
        },
        safety_contract: WrapperSafetyContract {
            read_only: true,
            mutation_surface: "none".to_string(),
            allowed_capabilities: vec![
                "snapshot".to_string(),
                "query".to_string(),
                "display".to_string(),
                "report_markdown".to_string(),
            ],
            disallowed_capabilities: vec![
                "patch".to_string(),
                "action".to_string(),
                "invoke".to_string(),
                "runtime_launch".to_string(),
                "gui_capture".to_string(),
                "host_path_read".to_string(),
                "file_system_write".to_string(),
                "memory_graph_write".to_string(),
            ],
        },
        acceptance_contract: WrapperAcceptanceContract {
            required_overall_verdict: "accepted".to_string(),
            required_display_status_label: "Ready for read-only display".to_string(),
            required_display_status_tone: "success".to_string(),
            required_wrapper_ready: true,
            required_matrix_gates: vec![
                "schema_chain".to_string(),
                "packet_summary_consistency".to_string(),
                "read_only_safety".to_string(),
                "query_surface_contract".to_string(),
                "report_markdown_consistency".to_string(),
                "feedback_verdict_separation".to_string(),
            ],
            review_sensitive_gates: vec!["detailed_readback".to_string()],
            all_gate_verdict: "passed".to_string(),
        },
        next_steps: vec![
            "Keep this descriptor out of MCP registry changes until a separate exposure slice is opened.".to_string(),
            "Wrap only explicit report packet payloads; do not accept paths, launch runtime, or capture GUI state.".to_string(),
            "Expose the P30 display model only when the P29 matrix is accepted and display safety wrapper_ready is true.".to_string(),
        ],
    }
}
