//! Static BioCortex capability-ledger consumer dry-run.
//!
//! This module parses a precomputed BioCortex schema-v3 capability ledger as an
//! inert artifact. It deliberately does not call BioCortex, Agent-Bridge memory,
//! retrieval, MCP registration, Nexus, AiOT, network APIs, or runtime/executor
//! paths.

use serde::{Deserialize, Serialize};
use std::collections::BTreeMap;

pub const BIOCORTEX_CAPABILITY_LEDGER_CONSUMER_SCHEMA: &str =
    "agent_bridge.biocortex_capability_ledger.consumer_dry_run.v0";

const PASSED: &str = "passed";
const FAILED: &str = "failed";

const REQUIRED_FIELDS: &[(&str, &str, &str)] = &[
    ("schema_version", "3", "schema_version"),
    (
        "generated_by",
        "capability_ledger_shadow_adapter",
        "producer_identity",
    ),
    ("mode", "read_only_shadow", "shadow_mode"),
    (
        "source_kind_scaled_morphology_benchmark",
        "executable_report",
        "source_scaled_morphology",
    ),
    (
        "source_kind_temporal_credit_window",
        "executable_report",
        "source_temporal_credit",
    ),
    (
        "source_kind_scale_capstone",
        "executable_report",
        "source_scale_capstone",
    ),
    (
        "source_kind_retrieval_engine",
        "executable_report",
        "source_retrieval_engine",
    ),
    (
        "source_kind_g_next_verdict",
        "prose_verdict",
        "source_g_next_boundary",
    ),
    (
        "source_kind_scale_axis_verdict",
        "prose_verdict",
        "source_scale_axis_boundary",
    ),
    (
        "regional_scale_positive",
        "true",
        "capability_regional_scale",
    ),
    (
        "retrieval_projection_positive_read_only",
        "true",
        "capability_retrieval_projection_read_only",
    ),
    (
        "capacity_scales_with_size",
        "true",
        "capability_capacity_scales_with_size",
    ),
    (
        "scale_new_function_emergence",
        "false",
        "boundary_no_new_function_emergence",
    ),
    (
        "valence_is_supplied_world_interface",
        "true",
        "boundary_valence_supplied",
    ),
    (
        "runtime_authority_granted",
        "false",
        "hard_false_runtime_authority",
    ),
    ("executor_enabled", "false", "hard_false_executor"),
    (
        "adapter_mutation_api_exposed",
        "false",
        "hard_false_adapter_mutation",
    ),
    ("ab_memory_mutated", "false", "hard_false_ab_memory"),
    (
        "retrieval_order_mutated",
        "false",
        "hard_false_retrieval_order",
    ),
    (
        "language_generated",
        "false",
        "hard_false_language_generation",
    ),
    ("cognition_claimed", "false", "hard_false_cognition"),
];

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct BioCortexCapabilityLedgerConsumerSummary {
    pub schema: String,
    pub input_schema: String,
    pub input_schema_version: Option<String>,
    pub input_mode: Option<String>,
    pub input_generated_by: Option<String>,
    pub verdict: String,
    pub read_only_confirmed: bool,
    pub downstream_action: String,
    pub integration_decision: String,
    pub safety: BioCortexCapabilityLedgerConsumerSafety,
    pub checks: Vec<BioCortexCapabilityLedgerConsumerCheck>,
    pub guidance: Vec<String>,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct BioCortexCapabilityLedgerConsumerSafety {
    pub static_artifact_only: bool,
    pub memory_write_attempted: bool,
    pub retrieval_order_change_attempted: bool,
    pub runtime_authority_observed: bool,
    pub executor_enablement_observed: bool,
    pub mcp_tool_registration: bool,
    pub nexus_world_tick_touched: bool,
    pub aiot_runtime_called: bool,
    pub language_generation_observed: bool,
    pub cognition_claim_observed: bool,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct BioCortexCapabilityLedgerConsumerCheck {
    pub check: String,
    pub verdict: String,
    pub required: bool,
    pub evidence: String,
}

pub fn consume_biocortex_capability_ledger(
    ledger: &str,
) -> BioCortexCapabilityLedgerConsumerSummary {
    let (fields, parse_check) = parse_ledger(ledger);
    let mut checks = vec![parse_check];
    if !fields.is_empty() {
        checks.extend(REQUIRED_FIELDS.iter().map(|(field, expected, check_name)| {
            required_field_check(&fields, field, expected, check_name)
        }));
    }

    let accepted = checks.iter().all(|check| check.verdict == PASSED);
    let verdict = if accepted { "accepted" } else { "rejected" };

    BioCortexCapabilityLedgerConsumerSummary {
        schema: BIOCORTEX_CAPABILITY_LEDGER_CONSUMER_SCHEMA.to_string(),
        input_schema: "biocortex.capability_ledger.v3".to_string(),
        input_schema_version: fields.get("schema_version").cloned(),
        input_mode: fields.get("mode").cloned(),
        input_generated_by: fields.get("generated_by").cloned(),
        verdict: verdict.to_string(),
        read_only_confirmed: accepted,
        downstream_action: if accepted {
            "display_or_review_only"
        } else {
            "reject_static_ledger_artifact"
        }
        .to_string(),
        integration_decision: if accepted {
            "shadow_only_no_runtime_admission"
        } else {
            "blocked_by_static_ledger_validation"
        }
        .to_string(),
        safety: BioCortexCapabilityLedgerConsumerSafety {
            static_artifact_only: true,
            memory_write_attempted: false,
            retrieval_order_change_attempted: false,
            runtime_authority_observed: false,
            executor_enablement_observed: false,
            mcp_tool_registration: false,
            nexus_world_tick_touched: false,
            aiot_runtime_called: false,
            language_generation_observed: false,
            cognition_claim_observed: false,
        },
        checks,
        guidance: guidance_for(verdict),
    }
}

fn parse_ledger(
    ledger: &str,
) -> (
    BTreeMap<String, String>,
    BioCortexCapabilityLedgerConsumerCheck,
) {
    let mut fields = BTreeMap::new();
    for (index, raw_line) in ledger.lines().enumerate() {
        let line = raw_line.trim();
        if line.is_empty() {
            continue;
        }
        let Some((key, value)) = line.split_once('=') else {
            return (
                BTreeMap::new(),
                check(
                    "parse_key_value",
                    false,
                    true,
                    format!("line {} is not key=value: {line}", index + 1),
                ),
            );
        };
        if key.is_empty() {
            return (
                BTreeMap::new(),
                check(
                    "parse_key_value",
                    false,
                    true,
                    format!("line {} has an empty key", index + 1),
                ),
            );
        }
        if fields.insert(key.to_string(), value.to_string()).is_some() {
            return (
                BTreeMap::new(),
                check(
                    "parse_key_value",
                    false,
                    true,
                    format!("duplicate ledger key: {key}"),
                ),
            );
        }
    }

    let parsed_count = fields.len();
    (
        fields,
        check(
            "parse_key_value",
            parsed_count > 0,
            true,
            format!("parsed_fields={parsed_count}"),
        ),
    )
}

fn required_field_check(
    fields: &BTreeMap<String, String>,
    field: &str,
    expected: &str,
    check_name: &str,
) -> BioCortexCapabilityLedgerConsumerCheck {
    let actual = fields.get(field).map(String::as_str).unwrap_or("<missing>");
    check(
        check_name,
        actual == expected,
        true,
        format!("{field}={actual}, expected={expected}"),
    )
}

fn check(
    check: &str,
    ok: bool,
    required: bool,
    evidence: String,
) -> BioCortexCapabilityLedgerConsumerCheck {
    BioCortexCapabilityLedgerConsumerCheck {
        check: check.to_string(),
        verdict: if ok { PASSED } else { FAILED }.to_string(),
        required,
        evidence,
    }
}

fn guidance_for(verdict: &str) -> Vec<String> {
    if verdict == "accepted" {
        vec![
            "Ledger may be displayed or attached to a human review packet.".to_string(),
            "Do not write Agent-Bridge memory or graph edges from this artifact.".to_string(),
            "Do not mutate retrieval order, register MCP tools, or enable runtime/shadow execution."
                .to_string(),
        ]
    } else {
        vec![
            "Reject the ledger artifact and do not surface it as a valid BioCortex capability summary."
                .to_string(),
            "Keep runtime, retrieval, and memory surfaces untouched while investigating the failed check."
                .to_string(),
        ]
    }
}
