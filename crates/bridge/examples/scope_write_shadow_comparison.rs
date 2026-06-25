//! Report-only shadow comparison for future project-id memory writes.
//!
//! This example does not call `MemorySaveTool`, write memories, mutate state.db,
//! register an MCP tool, or change production write behavior. It compares the
//! current legacy/project scope that a future save request would carry against
//! the owner-policy canonical project ID and explicit alias registry.
//!
//! Optional env:
//! - `AB_SCOPE_SHADOW_CWD`
//! - `AB_SCOPE_SHADOW_CANONICAL`
//! - `AB_SCOPE_SHADOW_ALIASES`
//! - `AGENT_BRIDGE_PROJECT_SCOPE_ALIASES` (fallback aliases source)
//! - `AB_SCOPE_SHADOW_EXTRA_SCOPES` (semicolon or newline separated)
//!
//! Run:
//!   cargo run -p ab-bridge --example scope_write_shadow_comparison

use ab_bridge::project_identity::{
    evaluate_scope_write_shadow, legacy_project_scope, normalize_project_id, project_id_scope,
    resolve_project_identity, ProjectIdentityInput, ScopeWriteShadowAction as ShadowAction,
    ScopeWriteShadowDecision as ShadowDecision, LEGACY_PROJECT_SCOPE_PREFIX,
};
use std::path::{Path, PathBuf};

const ENV_CWD: &str = "AB_SCOPE_SHADOW_CWD";
const ENV_CANONICAL: &str = "AB_SCOPE_SHADOW_CANONICAL";
const ENV_ALIASES: &str = "AB_SCOPE_SHADOW_ALIASES";
const ENV_ALIASES_COMPAT: &str = "AGENT_BRIDGE_PROJECT_SCOPE_ALIASES";
const ENV_EXTRA_SCOPES: &str = "AB_SCOPE_SHADOW_EXTRA_SCOPES";

#[derive(Clone, Debug, PartialEq, Eq)]
struct ScopeCase {
    label: String,
    scope: String,
    expected: ShadowAction,
}

#[derive(Clone, Debug, PartialEq, Eq)]
struct ShadowInput {
    cwd: String,
    canonical_scope: String,
    aliases: String,
    cases: Vec<ScopeCase>,
}

#[derive(Clone, Debug, PartialEq, Eq)]
struct ShadowReport {
    input: ShadowInput,
    decisions: Vec<(ScopeCase, ShadowDecision)>,
    passed: bool,
}

fn env_non_empty(name: &str) -> Option<String> {
    std::env::var(name)
        .ok()
        .map(|v| v.trim().to_string())
        .filter(|v| !v.is_empty())
}

fn capture_git(cwd: &Path, args: &[&str]) -> Option<String> {
    let out = std::process::Command::new("git")
        .current_dir(cwd)
        .args(args)
        .output()
        .ok()?;
    if !out.status.success() {
        return None;
    }
    let text = String::from_utf8_lossy(&out.stdout).trim().to_string();
    (!text.is_empty()).then_some(text)
}

fn default_cwd() -> anyhow::Result<String> {
    if let Some(cwd) = env_non_empty(ENV_CWD) {
        return Ok(cwd);
    }
    Ok(std::env::current_dir()?.display().to_string())
}

fn normalize_canonical_scope(raw: &str) -> Option<String> {
    normalize_project_id(raw).map(|id| project_id_scope(&id))
}

fn default_canonical_scope(cwd: &str) -> anyhow::Result<String> {
    if let Some(scope) =
        env_non_empty(ENV_CANONICAL).and_then(|raw| normalize_canonical_scope(&raw))
    {
        return Ok(scope);
    }
    let cwd_path = Path::new(cwd);
    let git_remote = capture_git(cwd_path, &["remote", "get-url", "origin"]);
    let git_root = capture_git(cwd_path, &["rev-parse", "--show-toplevel"]);
    let identity = resolve_project_identity(ProjectIdentityInput {
        cwd,
        explicit_project_id: None,
        git_remote: git_remote.as_deref(),
        git_root: git_root.as_deref(),
    });
    Ok(identity.canonical_scope)
}

fn default_aliases(canonical_scope: &str) -> String {
    let aliases = [
        "project:/Data/CascadeProjects/agent-bridge",
        "project:/Programs/Users/Pallasting/Documents/CascadeProjects/agent-bridge",
        "project:/Users/pallasting/Projects/agent-bridge",
        "project:/Data/CascadeProjects/agent-bridge-lcc-voice-gate",
        "project:/Data/CascadeProjects/agent-bridge.wt-tts",
        "project:/Data/CascadeProjects/agent-bridge-lcc0",
    ];
    format!("{canonical_scope}={}", aliases.join(","))
}

fn alternate_project_id(canonical_scope: &str) -> &'static str {
    if canonical_scope.contains("github.com/pallasting/agent-bridge") {
        "project-id:git:gitlab.com/pallasting/agent-bridge"
    } else {
        "project-id:git:github.com/pallasting/agent-bridge"
    }
}

fn default_cases(cwd: &str, canonical_scope: &str) -> Vec<ScopeCase> {
    let cwd_path = PathBuf::from(cwd);
    let parent = cwd_path
        .parent()
        .map(|p| p.display().to_string())
        .unwrap_or_else(|| ".".to_string());
    let basename = cwd_path
        .file_name()
        .and_then(|s| s.to_str())
        .unwrap_or("agent-bridge");
    let mut cases = vec![
        ScopeCase {
            label: "registered_root".to_string(),
            scope: legacy_project_scope(cwd),
            expected: ShadowAction::Canonicalize,
        },
        ScopeCase {
            label: "registered_child".to_string(),
            scope: format!("{}/docs", legacy_project_scope(cwd)),
            expected: ShadowAction::Canonicalize,
        },
        ScopeCase {
            label: "known_worktree_suffix".to_string(),
            scope: "project:/Data/CascadeProjects/agent-bridge-lcc-voice-gate".to_string(),
            expected: ShadowAction::Canonicalize,
        },
        ScopeCase {
            label: "unregistered_sibling".to_string(),
            scope: format!("{LEGACY_PROJECT_SCOPE_PREFIX}{parent}/{basename}-NOT-IN-REGISTRY"),
            expected: ShadowAction::KeepLegacyNeedsReview,
        },
        ScopeCase {
            label: "parent_dir".to_string(),
            scope: format!("{LEGACY_PROJECT_SCOPE_PREFIX}{parent}"),
            expected: ShadowAction::KeepLegacyNeedsReview,
        },
        ScopeCase {
            label: "non_project".to_string(),
            scope: "domain:rust".to_string(),
            expected: ShadowAction::KeepUnchanged,
        },
        ScopeCase {
            label: "different_project_id".to_string(),
            scope: "project-id:git:example.com/other/agent-bridge".to_string(),
            expected: ShadowAction::Blocked,
        },
        ScopeCase {
            label: "matching_project_id".to_string(),
            scope: canonical_scope.to_string(),
            expected: ShadowAction::Canonicalize,
        },
        ScopeCase {
            label: "alternate_forge_project_id".to_string(),
            scope: alternate_project_id(canonical_scope).to_string(),
            expected: ShadowAction::Blocked,
        },
    ];
    if let Some(extra) = env_non_empty(ENV_EXTRA_SCOPES) {
        cases.extend(
            extra
                .split([';', '\n'])
                .map(str::trim)
                .filter(|s| !s.is_empty())
                .enumerate()
                .map(|(idx, scope)| ScopeCase {
                    label: format!("extra_{}", idx + 1),
                    scope: scope.to_string(),
                    expected: ShadowAction::KeepLegacyNeedsReview,
                }),
        );
    }
    cases
}

fn load_input() -> anyhow::Result<ShadowInput> {
    let cwd = default_cwd()?;
    let canonical_scope = default_canonical_scope(&cwd)?;
    let canonical_scope = normalize_canonical_scope(&canonical_scope)
        .ok_or_else(|| anyhow::anyhow!("invalid canonical scope: {canonical_scope}"))?;
    let aliases = env_non_empty(ENV_ALIASES)
        .or_else(|| env_non_empty(ENV_ALIASES_COMPAT))
        .unwrap_or_else(|| default_aliases(&canonical_scope));
    let cases = default_cases(&cwd, &canonical_scope);
    Ok(ShadowInput {
        cwd,
        canonical_scope,
        aliases,
        cases,
    })
}

fn evaluate_scope(scope: &str, canonical_scope: &str, aliases: &str) -> ShadowDecision {
    evaluate_scope_write_shadow(scope, Some(canonical_scope), Some(aliases))
}

fn build_report(input: ShadowInput) -> ShadowReport {
    let decisions: Vec<_> = input
        .cases
        .iter()
        .cloned()
        .map(|case| {
            let decision = evaluate_scope(&case.scope, &input.canonical_scope, &input.aliases);
            (case, decision)
        })
        .collect();
    let passed = decisions
        .iter()
        .all(|(case, decision)| decision.action == case.expected);
    ShadowReport {
        input,
        decisions,
        passed,
    }
}

fn print_metric(metric: &str, value: impl AsRef<str>) {
    println!("| {metric} | `{}` |", value.as_ref());
}

fn print_report(report: &ShadowReport) {
    println!("# Scope Write Shadow Comparison");
    println!();
    println!("- read_only: true");
    println!("- runtime_changes: none");
    println!("- writes_memory: false");
    println!("- writes_db: false");
    println!("- mcp_surface_change: false");
    println!("- production_write_switch_authorized: false");
    println!();
    println!("## Inputs");
    println!();
    println!("| field | value |");
    println!("|---|---|");
    print_metric("cwd", &report.input.cwd);
    print_metric("canonical_scope", &report.input.canonical_scope);
    print_metric("aliases", &report.input.aliases);
    println!();
    println!("## Shadow Cases");
    println!();
    println!("| case | expected | actual | shadow eligible | reason | proposed scope | would store scope | legacy scope preserved | current scope |");
    println!("|---|---|---|---|---|---|---|---|---|");
    for (case, decision) in &report.decisions {
        println!(
            "| {} | `{}` | `{}` | `{}` | `{}` | `{}` | `{}` | `{}` | `{}` |",
            case.label,
            case.expected.label(),
            decision.action.label(),
            decision.shadow_write_eligible,
            decision.reason,
            decision.proposed_scope.as_deref().unwrap_or("<none>"),
            decision.would_store_scope_if_enabled,
            decision
                .legacy_scope_preserved
                .as_deref()
                .unwrap_or("<none>"),
            decision.requested_scope,
        );
    }
    println!();
    println!(
        "## Gate Verdict: {}",
        if report.passed { "PASS" } else { "FAIL" }
    );
    println!();
    if report.passed {
        println!("- The policy is narrow enough for a no-op shadow comparison.");
        println!("- This report still does not authorize production canonical writes.");
    } else {
        println!("- The policy does not match the expected owner-decision packet.");
        println!("- Do not use it for shadow comparison until reviewed.");
    }
}

fn main() -> anyhow::Result<()> {
    let report = build_report(load_input()?);
    print_report(&report);
    if !report.passed {
        std::process::exit(1);
    }
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    const CANON: &str = "project-id:git:github.com/pallasting/agent-bridge";
    const ALIASES: &str = "project-id:git:github.com/pallasting/agent-bridge=\
        project:/Data/CascadeProjects/agent-bridge,\
        project:/Programs/Users/Pallasting/Documents/CascadeProjects/agent-bridge,\
        project:/Users/pallasting/Projects/agent-bridge,\
        project:/Data/CascadeProjects/agent-bridge-lcc-voice-gate,\
        project:/Data/CascadeProjects/agent-bridge.wt-tts,\
        project:/Data/CascadeProjects/agent-bridge-lcc0";

    fn decide(scope: &str) -> ShadowDecision {
        evaluate_scope(scope, CANON, ALIASES)
    }

    #[test]
    fn registered_root_canonicalizes_and_preserves_legacy_scope() {
        let decision = decide("project:/Data/CascadeProjects/agent-bridge");

        assert_eq!(decision.action, ShadowAction::Canonicalize);
        assert!(decision.shadow_write_eligible);
        assert_eq!(decision.reason, "approved_alias_policy");
        assert_eq!(decision.proposed_scope.as_deref(), Some(CANON));
        assert_eq!(decision.would_store_scope_if_enabled, CANON);
        assert_eq!(
            decision.legacy_scope_preserved.as_deref(),
            Some("project:/Data/CascadeProjects/agent-bridge")
        );
    }

    #[test]
    fn registered_child_canonicalizes_under_alias_root() {
        let decision = decide("project:/Data/CascadeProjects/agent-bridge/docs");

        assert_eq!(decision.action, ShadowAction::Canonicalize);
        assert_eq!(decision.reason, "approved_alias_policy");
        assert_eq!(decision.would_store_scope_if_enabled, CANON);
    }

    #[test]
    fn known_worktree_suffix_canonicalizes_when_explicitly_registered() {
        let decision = decide("project:/Data/CascadeProjects/agent-bridge-lcc-voice-gate");

        assert_eq!(decision.action, ShadowAction::Canonicalize);
        assert_eq!(decision.reason, "approved_alias_policy");
        assert_eq!(decision.would_store_scope_if_enabled, CANON);
    }

    #[test]
    fn unregistered_sibling_keeps_legacy_and_needs_review() {
        let decision = decide("project:/Data/CascadeProjects/agent-bridge-NOT-IN-REGISTRY");

        assert_eq!(decision.action, ShadowAction::KeepLegacyNeedsReview);
        assert!(!decision.shadow_write_eligible);
        assert_eq!(decision.reason, "scope_not_in_policy");
        assert_eq!(
            decision.would_store_scope_if_enabled,
            "project:/Data/CascadeProjects/agent-bridge-NOT-IN-REGISTRY"
        );
    }

    #[test]
    fn parent_dir_keeps_legacy_and_needs_review() {
        let decision = decide("project:/Data/CascadeProjects");

        assert_eq!(decision.action, ShadowAction::KeepLegacyNeedsReview);
        assert_eq!(decision.reason, "scope_not_in_policy");
    }

    #[test]
    fn non_project_scope_stays_unchanged() {
        let decision = decide("domain:rust");

        assert_eq!(decision.action, ShadowAction::KeepUnchanged);
        assert_eq!(decision.reason, "non_project_scope");
        assert_eq!(decision.would_store_scope_if_enabled, "domain:rust");
    }

    #[test]
    fn different_project_id_is_blocked() {
        let decision = decide("project-id:git:example.com/other/agent-bridge");

        assert_eq!(decision.action, ShadowAction::Blocked);
        assert_eq!(decision.reason, "explicit_project_id_differs_from_policy");
    }

    #[test]
    fn matching_project_id_canonicalizes_without_legacy_metadata() {
        let decision = decide("Project-ID:git:GitHub.com/Pallasting/Agent-Bridge.git");

        assert_eq!(decision.action, ShadowAction::Canonicalize);
        assert_eq!(decision.reason, "explicit_project_id_matches_policy");
        assert_eq!(decision.would_store_scope_if_enabled, CANON);
        assert_eq!(decision.legacy_scope_preserved, None);
    }

    #[test]
    fn alternate_forge_project_id_is_blocked_without_dual_forge_policy() {
        let decision = decide("project-id:git:gitlab.com/pallasting/agent-bridge");

        assert_eq!(decision.action, ShadowAction::Blocked);
        assert_eq!(decision.reason, "explicit_project_id_differs_from_policy");
    }

    #[test]
    fn default_report_passes_expected_owner_policy_controls() {
        let report = build_report(ShadowInput {
            cwd: "/Data/CascadeProjects/agent-bridge".to_string(),
            canonical_scope: CANON.to_string(),
            aliases: ALIASES.to_string(),
            cases: default_cases("/Data/CascadeProjects/agent-bridge", CANON),
        });

        assert!(report.passed);
        assert!(report
            .decisions
            .iter()
            .any(|(case, decision)| case.label == "known_worktree_suffix"
                && decision.action == ShadowAction::Canonicalize));
        assert!(report
            .decisions
            .iter()
            .any(|(case, decision)| case.label == "unregistered_sibling"
                && decision.action == ShadowAction::KeepLegacyNeedsReview));
    }
}
