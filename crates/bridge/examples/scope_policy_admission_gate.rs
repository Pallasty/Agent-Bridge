//! Report-only gate for project scope alias admission.
//!
//! This validates whether a proposed `AGENT_BRIDGE_PROJECT_SCOPE_ALIASES`
//! policy is narrow enough to support future trace/shadow project-id writes.
//! It does not write memories, mutate state.db, register an MCP tool, or switch
//! production write behavior.
//!
//! Optional env:
//! - `AB_SCOPE_POLICY_ADMISSION_CWD`
//! - `AB_SCOPE_POLICY_ADMISSION_CANONICAL`
//! - `AB_SCOPE_POLICY_ADMISSION_ALIASES`
//! - `AGENT_BRIDGE_PROJECT_SCOPE_ALIASES` (fallback aliases source)
//! - `AB_SCOPE_POLICY_ADMISSION_EXTRA_SCOPES` (semicolon or newline separated)
//!
//! Run:
//!   cargo run -p ab-bridge --example scope_policy_admission_gate
//!   AB_SCOPE_POLICY_ADMISSION_CANONICAL=project-id:git:github.com/pallasting/agent-bridge \
//!   AB_SCOPE_POLICY_ADMISSION_ALIASES='project-id:git:github.com/pallasting/agent-bridge=project:/Users/pallasting/Projects/agent-bridge' \
//!     cargo run -p ab-bridge --example scope_policy_admission_gate

use ab_bridge::project_identity::{
    approved_scope_alias_canonical, legacy_project_scope, normalize_project_id, project_id_scope,
    resolve_project_identity, ProjectIdentityInput, LEGACY_PROJECT_SCOPE_PREFIX,
    PROJECT_ID_SCOPE_PREFIX,
};
use std::path::{Path, PathBuf};

const ENV_CWD: &str = "AB_SCOPE_POLICY_ADMISSION_CWD";
const ENV_CANONICAL: &str = "AB_SCOPE_POLICY_ADMISSION_CANONICAL";
const ENV_ALIASES: &str = "AB_SCOPE_POLICY_ADMISSION_ALIASES";
const ENV_ALIASES_COMPAT: &str = "AGENT_BRIDGE_PROJECT_SCOPE_ALIASES";
const ENV_EXTRA_SCOPES: &str = "AB_SCOPE_POLICY_ADMISSION_EXTRA_SCOPES";

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
enum Admission {
    Admitted,
    NeedsReview,
    Blocked,
}

impl Admission {
    fn label(self) -> &'static str {
        match self {
            Self::Admitted => "admitted",
            Self::NeedsReview => "needs_review",
            Self::Blocked => "blocked",
        }
    }
}

#[derive(Clone, Debug, PartialEq, Eq)]
struct AdmissionDecision {
    scope: String,
    admission: Admission,
    reason: &'static str,
    mapped_canonical: Option<String>,
    production_write_eligible: bool,
}

#[derive(Clone, Debug, PartialEq, Eq)]
struct GateInput {
    cwd: String,
    canonical_scope: String,
    aliases: String,
    cases: Vec<ScopeCase>,
}

#[derive(Clone, Debug, PartialEq, Eq)]
struct ScopeCase {
    label: String,
    scope: String,
    expected: Admission,
}

#[derive(Clone, Debug, PartialEq, Eq)]
struct GateReport {
    input: GateInput,
    decisions: Vec<(ScopeCase, AdmissionDecision)>,
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

fn default_canonical_scope(cwd: &str) -> String {
    if let Some(scope) =
        env_non_empty(ENV_CANONICAL).and_then(|raw| normalize_canonical_scope(&raw))
    {
        return scope;
    }
    let cwd_path = Path::new(cwd);
    let git_remote = capture_git(cwd_path, &["remote", "get-url", "origin"]);
    let git_root = capture_git(cwd_path, &["rev-parse", "--show-toplevel"]);
    resolve_project_identity(ProjectIdentityInput {
        cwd,
        explicit_project_id: None,
        git_remote: git_remote.as_deref(),
        git_root: git_root.as_deref(),
    })
    .canonical_scope
}

fn load_input() -> anyhow::Result<GateInput> {
    let cwd = default_cwd()?;
    let canonical_scope = default_canonical_scope(&cwd);
    let aliases = env_non_empty(ENV_ALIASES)
        .or_else(|| env_non_empty(ENV_ALIASES_COMPAT))
        .unwrap_or_else(|| format!("{canonical_scope}={}", legacy_project_scope(&cwd)));
    let cases = default_cases(&cwd, &canonical_scope);
    Ok(GateInput {
        cwd,
        canonical_scope,
        aliases,
        cases,
    })
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
            expected: Admission::Admitted,
        },
        ScopeCase {
            label: "registered_child".to_string(),
            scope: format!("{}{}", legacy_project_scope(cwd), "/docs"),
            expected: Admission::Admitted,
        },
        ScopeCase {
            label: "unregistered_sibling".to_string(),
            scope: format!("{LEGACY_PROJECT_SCOPE_PREFIX}{parent}/{basename}-NOT-IN-POLICY"),
            expected: Admission::NeedsReview,
        },
        ScopeCase {
            label: "parent_dir".to_string(),
            scope: format!("{LEGACY_PROJECT_SCOPE_PREFIX}{parent}"),
            expected: Admission::NeedsReview,
        },
        ScopeCase {
            label: "non_project".to_string(),
            scope: "domain:rust".to_string(),
            expected: Admission::Blocked,
        },
        ScopeCase {
            label: "different_project_id".to_string(),
            scope: "project-id:git:example.com/other/agent-bridge".to_string(),
            expected: Admission::Blocked,
        },
        ScopeCase {
            label: "matching_project_id".to_string(),
            scope: canonical_scope.to_string(),
            expected: Admission::Admitted,
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
                    expected: Admission::NeedsReview,
                }),
        );
    }
    cases
}

fn normalize_canonical_scope(raw: &str) -> Option<String> {
    normalize_project_id(raw).map(|id| project_id_scope(&id))
}

fn is_project_id_scope(scope: &str) -> bool {
    scope
        .get(..PROJECT_ID_SCOPE_PREFIX.len())
        .is_some_and(|prefix| prefix.eq_ignore_ascii_case(PROJECT_ID_SCOPE_PREFIX))
}

fn is_legacy_project_scope(scope: &str) -> bool {
    scope
        .get(..LEGACY_PROJECT_SCOPE_PREFIX.len())
        .is_some_and(|prefix| prefix.eq_ignore_ascii_case(LEGACY_PROJECT_SCOPE_PREFIX))
}

fn evaluate_scope(scope: &str, canonical_scope: &str, aliases: &str) -> AdmissionDecision {
    let scope = scope.trim();
    let policy_canonical = normalize_canonical_scope(canonical_scope);
    let mapped_canonical = approved_scope_alias_canonical(scope, aliases);

    let (admission, reason) = if scope.is_empty() {
        (Admission::Blocked, "empty_scope")
    } else if is_project_id_scope(scope) {
        if mapped_canonical.as_deref() == policy_canonical.as_deref() {
            (Admission::Admitted, "explicit_project_id_matches_policy")
        } else {
            (
                Admission::Blocked,
                "explicit_project_id_differs_from_policy",
            )
        }
    } else if !is_legacy_project_scope(scope) {
        (Admission::Blocked, "non_project_scope")
    } else {
        match (mapped_canonical.as_deref(), policy_canonical.as_deref()) {
            (Some(mapped), Some(policy)) if mapped == policy => {
                (Admission::Admitted, "approved_alias_policy")
            }
            (Some(_), Some(_)) => (Admission::Blocked, "mapped_to_different_canonical"),
            _ => (Admission::NeedsReview, "scope_not_in_policy"),
        }
    };

    AdmissionDecision {
        scope: scope.to_string(),
        admission,
        reason,
        mapped_canonical,
        production_write_eligible: admission == Admission::Admitted,
    }
}

fn build_report(input: GateInput) -> GateReport {
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
        .all(|(case, decision)| decision.admission == case.expected);
    GateReport {
        input,
        decisions,
        passed,
    }
}

fn print_metric(metric: &str, value: impl AsRef<str>) {
    println!("| {metric} | `{}` |", value.as_ref());
}

fn print_report(report: &GateReport) {
    println!("# Scope Policy Admission Gate");
    println!();
    println!("- read_only: true");
    println!("- runtime_changes: none");
    println!("- writes_memory: false");
    println!("- writes_db: false");
    println!("- mcp_surface_change: false");
    println!();
    println!("## Inputs");
    println!();
    println!("| field | value |");
    println!("|---|---|");
    print_metric("cwd", &report.input.cwd);
    print_metric("canonical_scope", &report.input.canonical_scope);
    print_metric("aliases", &report.input.aliases);
    println!();
    println!("## Admission Cases");
    println!();
    println!("| case | expected | actual | eligible | reason | mapped canonical | scope |");
    println!("|---|---|---|---|---|---|---|");
    for (case, decision) in &report.decisions {
        println!(
            "| {} | `{}` | `{}` | `{}` | `{}` | `{}` | `{}` |",
            case.label,
            case.expected.label(),
            decision.admission.label(),
            decision.production_write_eligible,
            decision.reason,
            decision.mapped_canonical.as_deref().unwrap_or("<none>"),
            decision.scope,
        );
    }
    println!();
    println!(
        "## Gate Verdict: {}",
        if report.passed { "PASS" } else { "FAIL" }
    );
    println!();
    if report.passed {
        println!("- The alias policy is narrow enough for trace/shadow evaluation.");
        println!("- This does not authorize production canonical writes.");
    } else {
        println!("- The alias policy is too broad or does not admit required roots.");
        println!("- Do not use it for trace/shadow write eligibility until fixed.");
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
        project:/Users/pallasting/Projects/agent-bridge,\
        project:/Data/CascadeProjects/agent-bridge";

    fn decide(scope: &str) -> AdmissionDecision {
        evaluate_scope(scope, CANON, ALIASES)
    }

    #[test]
    fn registered_root_is_admitted() {
        let decision = decide("project:/Users/pallasting/Projects/agent-bridge");

        assert_eq!(decision.admission, Admission::Admitted);
        assert!(decision.production_write_eligible);
        assert_eq!(decision.reason, "approved_alias_policy");
        assert_eq!(decision.mapped_canonical.as_deref(), Some(CANON));
    }

    #[test]
    fn child_under_registered_root_is_admitted() {
        let decision = decide("project:/Users/pallasting/Projects/agent-bridge/docs");

        assert_eq!(decision.admission, Admission::Admitted);
        assert_eq!(decision.reason, "approved_alias_policy");
        assert_eq!(decision.mapped_canonical.as_deref(), Some(CANON));
    }

    #[test]
    fn unregistered_worktree_sibling_needs_review() {
        let decision = decide("project:/Users/pallasting/Projects/agent-bridge-NOT-IN-POLICY");

        assert_eq!(decision.admission, Admission::NeedsReview);
        assert!(!decision.production_write_eligible);
        assert_eq!(decision.reason, "scope_not_in_policy");
        assert!(decision.mapped_canonical.is_none());
    }

    #[test]
    fn parent_directory_needs_review() {
        let decision = decide("project:/Users/pallasting/Projects");

        assert_eq!(decision.admission, Admission::NeedsReview);
        assert_eq!(decision.reason, "scope_not_in_policy");
        assert!(decision.mapped_canonical.is_none());
    }

    #[test]
    fn non_project_scope_is_blocked() {
        let decision = decide("domain:rust");

        assert_eq!(decision.admission, Admission::Blocked);
        assert_eq!(decision.reason, "non_project_scope");
        assert!(decision.mapped_canonical.is_none());
    }

    #[test]
    fn different_explicit_project_id_is_blocked() {
        let decision = decide("project-id:git:example.com/other/agent-bridge");

        assert_eq!(decision.admission, Admission::Blocked);
        assert_eq!(decision.reason, "explicit_project_id_differs_from_policy");
        assert_eq!(
            decision.mapped_canonical.as_deref(),
            Some("project-id:git:example.com/other/agent-bridge")
        );
    }

    #[test]
    fn matching_explicit_project_id_is_admitted() {
        let decision = decide("Project-ID:git:GitHub.com/Pallasting/Agent-Bridge.git");

        assert_eq!(decision.admission, Admission::Admitted);
        assert_eq!(decision.reason, "explicit_project_id_matches_policy");
        assert_eq!(decision.mapped_canonical.as_deref(), Some(CANON));
    }

    #[test]
    fn gate_fails_when_alias_policy_admits_parent_directory() {
        let input = GateInput {
            cwd: "/Users/pallasting/Projects/agent-bridge".to_string(),
            canonical_scope: CANON.to_string(),
            aliases: format!("{CANON}=project:/Users/pallasting/Projects"),
            cases: default_cases("/Users/pallasting/Projects/agent-bridge", CANON),
        };

        let report = build_report(input);

        assert!(!report.passed);
        let parent = report
            .decisions
            .iter()
            .find(|(case, _)| case.label == "parent_dir")
            .expect("parent case");
        assert_eq!(parent.1.admission, Admission::Admitted);
        assert_eq!(parent.0.expected, Admission::NeedsReview);
    }

    #[test]
    fn default_gate_passes_for_current_root_alias() {
        let input = GateInput {
            cwd: "/Users/pallasting/Projects/agent-bridge".to_string(),
            canonical_scope: CANON.to_string(),
            aliases: format!("{CANON}=project:/Users/pallasting/Projects/agent-bridge"),
            cases: default_cases("/Users/pallasting/Projects/agent-bridge", CANON),
        };

        assert!(build_report(input).passed);
    }
}
