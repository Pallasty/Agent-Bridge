//! Conservative, machine-readable inventory of effectful entry points.
//!
//! This module classifies what an entry point *may* do.  It deliberately does
//! not treat MCP annotations as a security attestation: annotations are
//! supplied by tool implementations and the inventory alone cannot prove that
//! an authorization guard was installed or executed.

use std::collections::BTreeSet;

use ab_mcp::ToolDescriptor;
use serde::{Deserialize, Serialize};
use sha2::{Digest as _, Sha256};

/// Schema used as part of the inventory digest domain.
pub const EFFECT_INVENTORY_SCHEMA_VERSION: &str = "agent_bridge_effect_inventory_v1";

/// Tool-name safety floor maintained independently from the lease evaluator.
///
/// MCP annotations are advisory metadata, not proof of implementation
/// behavior.  These known effect-capable operations therefore remain
/// exact-invocation protected even if a future descriptor accidentally claims
/// to be read-only.  Keep this list local to avoid a policy/evaluator import
/// cycle; drift is surfaced by the inventory digest and tests.
pub const KNOWN_EFFECTFUL_MCP_TOOLS: &[&str] = &[
    // Arbitrary command, terminal, application and desktop actuation.
    "shell_exec",
    "system_control",
    "terminal_send_keys",
    "terminal_split",
    "terminal_resize",
    "ide_command",
    "app_control",
    "macos_ax_focus_transaction",
    "warp_launch_workflow",
    "warp_open_settings",
    "warp_open_tab",
    "warp_open_window",
    "desktop_action",
    "desktop_invoke",
    "desktop_confirm",
    // Agent/process lifecycle and input injection.
    "agent_spawn",
    "agent_send_input",
    "agent_steer_launch",
    "agent_steer_drive",
    "agent_steer_kill",
    "agent_session_reconcile",
    // Browser code execution, navigation, submission and host-path writes.
    "browser_navigate",
    "browser_eval",
    "browser_click",
    "browser_fill_form",
    "browser_press_key",
    "browser_select_option",
    "browser_eval_in_frame",
    "browser_reload",
    "browser_back",
    "browser_forward",
    "browser_scroll",
    "browser_upload_file",
    "browser_set_emulation",
    "browser_hover",
    "browser_screenshot",
    "browser_screenshot_element",
    "browser_close_page",
    "modelscope_abot_run_once",
    // Worktree and device mutation.
    "worktree_create",
    "worktree_remove",
    "mobile_install_apk",
    "mobile_launch_app",
    "mobile_click",
    "mobile_input_text",
    "mobile_projection_start",
    "mobile_projection_update",
    "mobile_projection_sync_media",
    "mobile_projection_follow_media",
    "advance_track_then_project",
    // External/durable collaboration writes and authority mutation.
    "notify",
    "osc_parse",
    "forum_post",
    "forum_subscribe",
    "forum_set_thread_status",
    "agent_message",
    "agent_presence_announce",
    "world_patch",
    "tailscale_acl_set",
    "github_issue_create",
    "gitlab_issue_create",
    "notion_page_create",
    "oz_run_cancel",
    "operator_request_stage",
    // Audio/output actuation and terminal task receipts.
    "present_voice",
    "present_voice_confirm_audibility",
    "task_summary_finalize",
    // Durable planning, pet state, work memory and lifecycle producers.
    "plan_save",
    "plan_update",
    "pet_state_set",
    "pet_state_ritual",
    "work_memory",
    "session_bootstrap",
    "session_curate",
    "session_finalize",
    "session_lifecycle_step",
    "session_reflect",
    // Durable knowledge and index mutation (including tools that write files).
    "memory_save",
    "memory_delete",
    "memory_compact",
    "memory_purge_tombstones",
    "memory_prune_coactivation_noise",
    "memory_prune_degenerate_relates",
    "memory_archive_orphan_stubs",
    "memory_restore_archived",
    "memory_tombstone_aged_archived",
    "memory_decay_unused",
    "memory_reindex",
    "memory_export",
    "memory_import",
    "memory_link",
    "memory_correction",
    "memory_retrieval_feedback",
    "memory_consolidate",
    "memory_related_keys_materialize",
    "memory_link_orphans",
    "memory_graph_export",
    "memory_auto_curate",
    "codebase_reindex",
    // Legacy aliases are retained so an accidentally exposed descriptor still
    // fails closed at this layer.
    "notify.send",
    "terminal.send_keys",
    "terminal.split",
    "browser.navigate",
    "browser.eval",
    "browser.click",
    "browser.screenshot",
    "osc.parse",
];

#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord, Hash, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum EffectClass {
    Unknown,
    None,
    Observability,
    EphemeralLocal,
    DurableLocal,
    HostActuation,
    ProcessLifecycle,
    ExternalWrite,
    AuthorityMutation,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord, Hash, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum AuthorityPolicy {
    OpenRead,
    TargetCustodyRecovery,
    ExactInvocation,
    Deny,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord, Hash, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum TargetBinding {
    None,
    ArgumentsDigest,
    RuntimeResolved,
    CustodiedHandle,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord, Hash, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum IngressKind {
    Mcp,
    UnixRpc,
    DaemonHttp,
    Native,
    Direct,
    Background,
}

/// One classified operation.
///
/// `protected` and `attested` describe runtime evidence, not desired policy.
/// Inventory construction therefore leaves both false.  A later runtime
/// integration may set them only after it can prove the guard coverage.
#[derive(Debug, Clone, PartialEq, Eq, PartialOrd, Ord, Hash, Serialize, Deserialize)]
pub struct EffectDescriptor {
    pub ingress: IngressKind,
    pub operation: String,
    pub effect_class: EffectClass,
    pub authority_policy: AuthorityPolicy,
    pub target_binding: TargetBinding,
    pub protected: bool,
    pub attested: bool,
    pub reason: String,
}

/// Stable classification of all descriptors visible in one MCP registry.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct McpEffectInventory {
    pub schema_version: String,
    pub descriptors: Vec<EffectDescriptor>,
    pub digest_sha256: String,
    pub total_count: usize,
    pub unknown_count: usize,
    pub exact_invocation_count: usize,
    pub open_read_count: usize,
    pub recovery_count: usize,
}

/// Compact serializable attestation input for capability/status surfaces.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct EffectInventorySummary {
    pub schema_version: String,
    pub digest_sha256: String,
    pub total_count: usize,
    pub unknown_count: usize,
    pub exact_invocation_count: usize,
    pub open_read_count: usize,
    pub recovery_count: usize,
}

impl McpEffectInventory {
    /// Classify MCP tool descriptors with a fail-closed default.
    ///
    /// A descriptor is open only when every available annotation agrees with
    /// a side-effect-free read: read-only, non-destructive, closed-world and
    /// idempotent.  Missing or contradictory annotations require an exact
    /// invocation authorization.
    pub fn from_tool_descriptors(tool_descriptors: &[ToolDescriptor]) -> Self {
        let mut descriptors = tool_descriptors
            .iter()
            .map(classify_mcp_descriptor)
            .collect::<Vec<_>>();
        descriptors.sort();

        let total_count = descriptors.len();
        let unknown_count = descriptors
            .iter()
            .filter(|entry| entry.effect_class == EffectClass::Unknown)
            .count();
        let exact_invocation_count = descriptors
            .iter()
            .filter(|entry| entry.authority_policy == AuthorityPolicy::ExactInvocation)
            .count();
        let open_read_count = descriptors
            .iter()
            .filter(|entry| entry.authority_policy == AuthorityPolicy::OpenRead)
            .count();
        let recovery_count = descriptors
            .iter()
            .filter(|entry| entry.authority_policy == AuthorityPolicy::TargetCustodyRecovery)
            .count();
        let digest_sha256 = inventory_digest(&descriptors);

        Self {
            schema_version: EFFECT_INVENTORY_SCHEMA_VERSION.to_owned(),
            descriptors,
            digest_sha256,
            total_count,
            unknown_count,
            exact_invocation_count,
            open_read_count,
            recovery_count,
        }
    }

    /// Names whose conservative policy requires an exact invocation grant.
    pub fn exact_invocation_tool_names(&self) -> BTreeSet<String> {
        self.descriptors
            .iter()
            .filter(|entry| entry.authority_policy == AuthorityPolicy::ExactInvocation)
            .map(|entry| entry.operation.clone())
            .collect()
    }

    /// Classification candidates for a future narrower authorization lane.
    ///
    /// This is not a runtime guard allowlist: MCP annotations are advisory,
    /// and the two recovery implementations do not yet prove
    /// caller/task-to-target custody.
    pub fn unattested_non_exact_candidates(&self) -> BTreeSet<String> {
        self.descriptors
            .iter()
            .filter(|entry| {
                matches!(
                    entry.authority_policy,
                    AuthorityPolicy::OpenRead | AuthorityPolicy::TargetCustodyRecovery
                )
            })
            .map(|entry| entry.operation.clone())
            .collect()
    }

    pub fn summary(&self) -> EffectInventorySummary {
        EffectInventorySummary {
            schema_version: self.schema_version.clone(),
            digest_sha256: self.digest_sha256.clone(),
            total_count: self.total_count,
            unknown_count: self.unknown_count,
            exact_invocation_count: self.exact_invocation_count,
            open_read_count: self.open_read_count,
            recovery_count: self.recovery_count,
        }
    }

    /// Render a capability/status report without conflating classification
    /// with runtime protection.  Known uncovered ingress debt is always
    /// included; callers may omit the potentially large MCP descriptor list.
    pub fn report_json(&self, include_descriptors: bool) -> serde_json::Value {
        let mut report = serde_json::json!({
            "schema_version": EFFECT_INVENTORY_SCHEMA_VERSION,
            "summary": self.summary(),
            "digest_scope": {
                "includes": "sorted_mcp_descriptor_classification",
                "includes_uncovered_ingresses": false,
                "includes_runtime_policy_or_carveouts": false
            },
            "authorization_projection": {
                "runtime_authorization_attested": false,
                "descriptor_annotations_trusted_for_guard_exemption": false,
                "recovery_target_custody_attested": false,
                "descriptor_derived_guard_exempt_tools": [],
                "effective_runtime_guard_exemptions_attested": false,
                "runtime_policy_carveouts_reported_by": "security.invocation_lease.invalid_hold_open_tools",
                "live_serving_registry_attested_by_inventory_alone": false,
                "registry_guard_replacement_locked_by_inventory_alone": false,
                "pre_finalization_handle_bypass_closed_by_inventory_alone": false,
                "classification_cannot_attest_registry_type_state": true,
                "status": "classification_only_fail_closed_guard_projection_uses_no_descriptor_derived_exemptions"
            },
            "uncovered_ingresses": uncovered_ingresses(),
        });
        if include_descriptors {
            report
                .as_object_mut()
                .expect("effect inventory report is an object")
                .insert(
                    "mcp_descriptors".to_owned(),
                    serde_json::to_value(&self.descriptors)
                        .expect("effect descriptors are infallibly serializable"),
                );
        }
        report
    }
}

fn classify_mcp_descriptor(descriptor: &ToolDescriptor) -> EffectDescriptor {
    let name = descriptor.schema.name.clone();

    match name.as_str() {
        "agent_kill" => EffectDescriptor {
            ingress: IngressKind::Mcp,
            operation: name,
            effect_class: EffectClass::ProcessLifecycle,
            authority_policy: AuthorityPolicy::TargetCustodyRecovery,
            target_binding: TargetBinding::CustodiedHandle,
            protected: false,
            attested: false,
            reason: "recovery_operation_requires_runtime_target_custody_attestation".to_owned(),
        },
        "mobile_projection_stop" => EffectDescriptor {
            ingress: IngressKind::Mcp,
            operation: name,
            effect_class: EffectClass::HostActuation,
            authority_policy: AuthorityPolicy::TargetCustodyRecovery,
            target_binding: TargetBinding::CustodiedHandle,
            protected: false,
            attested: false,
            reason: "recovery_operation_requires_runtime_target_custody_attestation".to_owned(),
        },
        _ if KNOWN_EFFECTFUL_MCP_TOOLS.contains(&name.as_str()) => EffectDescriptor {
            ingress: IngressKind::Mcp,
            operation: name,
            effect_class: EffectClass::Unknown,
            authority_policy: AuthorityPolicy::ExactInvocation,
            target_binding: TargetBinding::ArgumentsDigest,
            protected: false,
            attested: false,
            reason: "known_effectful_tool_overrides_advisory_read_only_annotations".to_owned(),
        },
        _ if descriptor.annotations.is_some_and(|annotations| {
            annotations.read_only_hint
                && !annotations.destructive_hint
                && !annotations.open_world_hint
                && annotations.idempotent_hint == Some(true)
        }) =>
        {
            EffectDescriptor {
                ingress: IngressKind::Mcp,
                operation: name,
                effect_class: EffectClass::None,
                authority_policy: AuthorityPolicy::OpenRead,
                target_binding: TargetBinding::None,
                protected: false,
                attested: false,
                reason: "all_mcp_annotations_explicitly_agree_on_closed_world_read_only_behavior"
                    .to_owned(),
            }
        }
        _ => EffectDescriptor {
            ingress: IngressKind::Mcp,
            operation: name,
            effect_class: EffectClass::Unknown,
            authority_policy: AuthorityPolicy::ExactInvocation,
            target_binding: TargetBinding::ArgumentsDigest,
            protected: false,
            attested: false,
            reason: "missing_or_non_read_only_annotations_fail_closed".to_owned(),
        },
    }
}

#[derive(Serialize)]
struct DigestEnvelope<'a> {
    schema_version: &'static str,
    descriptors: &'a [EffectDescriptor],
}

fn inventory_digest(descriptors: &[EffectDescriptor]) -> String {
    // Struct field order and the pre-sorted descriptor vector make this JSON
    // representation deterministic for the current schema.  The schema value
    // domain-separates future encodings.
    let encoded = serde_json::to_vec(&DigestEnvelope {
        schema_version: EFFECT_INVENTORY_SCHEMA_VERSION,
        descriptors,
    })
    .expect("effect inventory contains only infallibly serializable values");
    hex_lower(&Sha256::digest(encoded))
}

fn hex_lower(bytes: &[u8]) -> String {
    let mut encoded = String::with_capacity(bytes.len() * 2);
    for byte in bytes {
        use std::fmt::Write as _;
        write!(&mut encoded, "{byte:02x}").expect("writing to String is infallible");
    }
    encoded
}

/// Known effect-capable ingress paths that are not yet covered or attested by
/// the MCP registry inventory.
///
/// This is intentionally an explicit debt register.  Absence from the MCP
/// registry must never be interpreted as evidence that an ingress is safe.
pub fn uncovered_ingresses() -> Vec<EffectDescriptor> {
    let mut entries = vec![
        uncovered(
            IngressKind::DaemonHttp,
            "POST /forum/post",
            EffectClass::ExternalWrite,
            TargetBinding::RuntimeResolved,
            "daemon_http_write_bypasses_mcp_registry_guard_attestation",
        ),
        uncovered(
            IngressKind::DaemonHttp,
            "POST /agent/messages",
            EffectClass::ExternalWrite,
            TargetBinding::RuntimeResolved,
            "daemon_http_write_bypasses_mcp_registry_guard_attestation",
        ),
        uncovered(
            IngressKind::DaemonHttp,
            "POST /avatar-surface/cortex-review-decision",
            EffectClass::AuthorityMutation,
            TargetBinding::RuntimeResolved,
            "daemon_http_decision_write_bypasses_mcp_registry_guard_attestation",
        ),
        uncovered(
            IngressKind::DaemonHttp,
            "daemon startup embed readiness reindex",
            EffectClass::DurableLocal,
            TargetBinding::RuntimeResolved,
            "startup_maintenance_effect_has_no_invocation_guard_attestation",
        ),
        uncovered(
            IngressKind::Native,
            "Warp native IPC",
            EffectClass::Unknown,
            TargetBinding::RuntimeResolved,
            "native_ipc_effect_closure_is_not_registered_or_attested_here",
        ),
        uncovered(
            IngressKind::Direct,
            "direct Hub/backend handles",
            EffectClass::Unknown,
            TargetBinding::RuntimeResolved,
            "direct_backend_handles_can_bypass_registry_authorization",
        ),
        uncovered(
            IngressKind::Background,
            "background/CLI",
            EffectClass::Unknown,
            TargetBinding::RuntimeResolved,
            "background_and_cli_effects_lack_registry_guard_attestation",
        ),
    ];
    entries.sort();
    entries
}

fn uncovered(
    ingress: IngressKind,
    operation: &str,
    effect_class: EffectClass,
    target_binding: TargetBinding,
    reason: &str,
) -> EffectDescriptor {
    EffectDescriptor {
        ingress,
        operation: operation.to_owned(),
        effect_class,
        authority_policy: AuthorityPolicy::ExactInvocation,
        target_binding,
        protected: false,
        attested: false,
        reason: reason.to_owned(),
    }
}

#[cfg(test)]
mod tests {
    use ab_mcp::{ToolAnnotations, ToolSchema};
    use serde_json::json;

    use super::*;

    fn tool(name: &str, annotations: Option<ToolAnnotations>) -> ToolDescriptor {
        ToolDescriptor {
            schema: ToolSchema {
                name: name.to_owned(),
                description: "test descriptor".to_owned(),
                input_schema: json!({"type": "object"}),
            },
            title: name.to_owned(),
            annotations,
            output_schema: None,
            security_schemes: None,
        }
    }

    #[test]
    fn missing_or_ambiguous_annotations_fail_closed_to_exact_invocation() {
        let ambiguous = ToolAnnotations {
            read_only_hint: true,
            destructive_hint: false,
            open_world_hint: false,
            idempotent_hint: None,
        };
        let inventory = McpEffectInventory::from_tool_descriptors(&[
            tool("missing", None),
            tool("ambiguous", Some(ambiguous)),
            tool("write", Some(ToolAnnotations::conservative())),
        ]);

        assert_eq!(inventory.total_count, 3);
        assert_eq!(inventory.unknown_count, 3);
        assert_eq!(inventory.exact_invocation_count, 3);
        assert_eq!(inventory.open_read_count, 0);
        assert_eq!(
            inventory.exact_invocation_tool_names(),
            BTreeSet::from([
                "ambiguous".to_owned(),
                "missing".to_owned(),
                "write".to_owned(),
            ])
        );
    }

    #[test]
    fn only_explicit_closed_world_read_only_descriptor_is_open() {
        let inventory = McpEffectInventory::from_tool_descriptors(&[tool(
            "observe",
            Some(ToolAnnotations::read_only()),
        )]);
        let entry = &inventory.descriptors[0];

        assert_eq!(entry.effect_class, EffectClass::None);
        assert_eq!(entry.authority_policy, AuthorityPolicy::OpenRead);
        assert_eq!(entry.target_binding, TargetBinding::None);
        assert!(!entry.protected);
        assert!(!entry.attested);
        assert_eq!(inventory.open_read_count, 1);
        assert_eq!(inventory.exact_invocation_count, 0);
        assert_eq!(
            inventory.unattested_non_exact_candidates(),
            BTreeSet::from(["observe".to_owned()])
        );
    }

    #[test]
    fn known_effectful_tool_overrides_read_only_annotation() {
        for name in [
            "shell_exec",
            "present_voice",
            "task_summary_finalize",
            "agent_session_reconcile",
            "agent_presence_announce",
            "forum_subscribe",
            "plan_save",
            "plan_update",
            "work_memory",
            "session_bootstrap",
            "session_finalize",
            "memory_save",
            "memory_related_keys_materialize",
            "codebase_reindex",
            "pet_state_set",
            "operator_request_stage",
        ] {
            let inventory = McpEffectInventory::from_tool_descriptors(&[tool(
                name,
                Some(ToolAnnotations::read_only()),
            )]);
            let entry = &inventory.descriptors[0];
            assert_eq!(
                entry.authority_policy,
                AuthorityPolicy::ExactInvocation,
                "{name} must not become open from advisory annotations"
            );
            assert_eq!(entry.target_binding, TargetBinding::ArgumentsDigest);
            assert_eq!(
                entry.reason,
                "known_effectful_tool_overrides_advisory_read_only_annotations"
            );
        }
    }

    #[test]
    fn recovery_tools_require_custodied_target_instead_of_exact_grant() {
        let inventory = McpEffectInventory::from_tool_descriptors(&[
            tool("mobile_projection_stop", None),
            tool("agent_kill", Some(ToolAnnotations::conservative())),
        ]);

        assert_eq!(inventory.recovery_count, 2);
        assert_eq!(inventory.exact_invocation_count, 0);
        assert_eq!(
            inventory.unattested_non_exact_candidates(),
            BTreeSet::from(["agent_kill".to_owned(), "mobile_projection_stop".to_owned()])
        );
        assert!(inventory.descriptors.iter().all(|entry| {
            entry.authority_policy == AuthorityPolicy::TargetCustodyRecovery
                && entry.target_binding == TargetBinding::CustodiedHandle
                && !entry.protected
                && !entry.attested
        }));
    }

    #[test]
    fn sorting_summary_and_digest_are_stable_across_input_order() {
        let first = McpEffectInventory::from_tool_descriptors(&[
            tool("zeta", None),
            tool("alpha", Some(ToolAnnotations::read_only())),
            tool("agent_kill", None),
        ]);
        let second = McpEffectInventory::from_tool_descriptors(&[
            tool("agent_kill", None),
            tool("zeta", None),
            tool("alpha", Some(ToolAnnotations::read_only())),
        ]);

        assert_eq!(first, second);
        assert_eq!(first.digest_sha256.len(), 64);
        assert_eq!(first.total_count, 3);
        assert_eq!(first.unknown_count, 1);
        assert_eq!(first.exact_invocation_count, 1);
        assert_eq!(first.open_read_count, 1);
        assert_eq!(first.recovery_count, 1);
        assert_eq!(first.summary().digest_sha256, first.digest_sha256);
        assert_eq!(
            first
                .descriptors
                .iter()
                .map(|entry| entry.operation.as_str())
                .collect::<Vec<_>>(),
            vec!["agent_kill", "alpha", "zeta"]
        );

        let compact = first.report_json(false);
        assert_eq!(compact["summary"]["digest_sha256"], first.digest_sha256);
        assert!(compact["uncovered_ingresses"].is_array());
        assert!(compact.get("mcp_descriptors").is_none());
        assert_eq!(
            compact["authorization_projection"]["descriptor_derived_guard_exempt_tools"],
            json!([])
        );
        assert_eq!(
            compact["authorization_projection"]
                ["live_serving_registry_attested_by_inventory_alone"],
            json!(false)
        );
        assert_eq!(
            compact["digest_scope"]["includes_runtime_policy_or_carveouts"],
            json!(false)
        );
        assert_eq!(
            compact["authorization_projection"]
                ["descriptor_annotations_trusted_for_guard_exemption"],
            json!(false)
        );

        let full = first.report_json(true);
        assert_eq!(full["mcp_descriptors"].as_array().unwrap().len(), 3);
        assert_eq!(full["uncovered_ingresses"], compact["uncovered_ingresses"]);
    }

    #[test]
    fn uncovered_inventory_is_explicit_nonempty_and_unattested() {
        let uncovered = uncovered_ingresses();
        let operations = uncovered
            .iter()
            .map(|entry| entry.operation.as_str())
            .collect::<BTreeSet<_>>();

        assert!(!uncovered.is_empty());
        for required in [
            "POST /forum/post",
            "POST /agent/messages",
            "POST /avatar-surface/cortex-review-decision",
            "daemon startup embed readiness reindex",
            "Warp native IPC",
            "direct Hub/backend handles",
            "background/CLI",
        ] {
            assert!(operations.contains(required), "missing {required}");
        }
        assert!(uncovered.iter().all(|entry| {
            !entry.protected
                && !entry.attested
                && !entry.reason.is_empty()
                && entry.authority_policy == AuthorityPolicy::ExactInvocation
        }));
    }
}
