//! Report-only dry run for Phase 3 write-time project identity.
//!
//! This example does not write memories, mutate state.db, register an MCP tool,
//! or change runtime write behavior. It answers one question for a prospective
//! project-scoped memory write: would a future canonical `project-id:` scope be
//! production-eligible, and why?
//!
//! Usage:
//!
//!   cargo run -p ab-bridge --example scope_write_identity_dry_run
//!   AB_SCOPE_WRITE_DRY_RUN_CWD=/Data/CascadeProjects/agent-bridge-palace-apply-audit \
//!   AB_SCOPE_WRITE_DRY_RUN_GIT_REMOTE=git@gitlab.com:pallasting/agent-bridge.git \
//!     cargo run -p ab-bridge --example scope_write_identity_dry_run

use ab_bridge::project_identity::{
    legacy_project_scope, resolve_project_identity, ProjectIdentity, ProjectIdentityEvidence,
    ProjectIdentityInput, LEGACY_PROJECT_SCOPE_PREFIX, PROJECT_ID_SCOPE_PREFIX,
};
use std::path::Path;

const ENV_CWD: &str = "AB_SCOPE_WRITE_DRY_RUN_CWD";
const ENV_CURRENT_SCOPE: &str = "AB_SCOPE_WRITE_DRY_RUN_CURRENT_SCOPE";
const ENV_PROJECT_ID: &str = "AB_SCOPE_WRITE_DRY_RUN_PROJECT_ID";
const ENV_GIT_REMOTE: &str = "AB_SCOPE_WRITE_DRY_RUN_GIT_REMOTE";
const ENV_GIT_ROOT: &str = "AB_SCOPE_WRITE_DRY_RUN_GIT_ROOT";

#[derive(Clone, Debug, PartialEq, Eq)]
struct DryRunInput {
    cwd: String,
    current_scope: String,
    explicit_project_id: Option<String>,
    git_remote: Option<String>,
    git_root: Option<String>,
}

#[derive(Clone, Debug, PartialEq, Eq)]
struct DryRunReport {
    current_scope: String,
    proposed_scope: String,
    identity: ProjectIdentity,
    production_eligible: bool,
    blocked_reason: Option<&'static str>,
}

impl DryRunReport {
    fn legacy_scope_changed(&self) -> bool {
        self.current_scope != self.identity.legacy_scope
    }
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

fn load_input() -> anyhow::Result<DryRunInput> {
    let cwd = default_cwd()?;
    let current_scope =
        env_non_empty(ENV_CURRENT_SCOPE).unwrap_or_else(|| legacy_project_scope(&cwd));
    let cwd_path = Path::new(&cwd);
    let explicit_project_id = env_non_empty(ENV_PROJECT_ID);
    let git_remote = env_non_empty(ENV_GIT_REMOTE)
        .or_else(|| capture_git(cwd_path, &["remote", "get-url", "origin"]));
    let git_root = env_non_empty(ENV_GIT_ROOT)
        .or_else(|| capture_git(cwd_path, &["rev-parse", "--show-toplevel"]));

    Ok(DryRunInput {
        cwd,
        current_scope,
        explicit_project_id,
        git_remote,
        git_root,
    })
}

fn is_project_scope(scope: &str) -> bool {
    let scope = scope.trim();
    scope
        .get(..LEGACY_PROJECT_SCOPE_PREFIX.len())
        .is_some_and(|prefix| prefix.eq_ignore_ascii_case(LEGACY_PROJECT_SCOPE_PREFIX))
        || scope
            .get(..PROJECT_ID_SCOPE_PREFIX.len())
            .is_some_and(|prefix| prefix.eq_ignore_ascii_case(PROJECT_ID_SCOPE_PREFIX))
}

fn build_report(input: &DryRunInput) -> DryRunReport {
    let explicit_project_id = input.explicit_project_id.as_deref().or_else(|| {
        input
            .current_scope
            .trim()
            .get(..PROJECT_ID_SCOPE_PREFIX.len())
            .filter(|prefix| prefix.eq_ignore_ascii_case(PROJECT_ID_SCOPE_PREFIX))
            .and_then(|_| {
                input
                    .current_scope
                    .trim()
                    .get(PROJECT_ID_SCOPE_PREFIX.len()..)
            })
    });
    let identity = resolve_project_identity(ProjectIdentityInput {
        cwd: &input.cwd,
        explicit_project_id,
        git_remote: input.git_remote.as_deref(),
        git_root: input.git_root.as_deref(),
    });
    let blocked_reason = if !is_project_scope(&input.current_scope) {
        Some("non_project_scope")
    } else if !identity.evidence.is_high_confidence() {
        Some("resolver_evidence_not_high_confidence")
    } else {
        None
    };

    DryRunReport {
        current_scope: input.current_scope.clone(),
        proposed_scope: identity.canonical_scope.clone(),
        identity,
        production_eligible: blocked_reason.is_none(),
        blocked_reason,
    }
}

fn print_metric(metric: &str, value: impl AsRef<str>) {
    println!("| {metric} | `{}` |", value.as_ref());
}

fn main() -> anyhow::Result<()> {
    let input = load_input()?;
    let report = build_report(&input);

    println!("# Scope Write Identity Dry Run");
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
    print_metric("cwd", &input.cwd);
    print_metric("current_scope", &input.current_scope);
    print_metric(
        "explicit_project_id",
        input.explicit_project_id.as_deref().unwrap_or("<none>"),
    );
    print_metric(
        "git_remote",
        input.git_remote.as_deref().unwrap_or("<none>"),
    );
    print_metric("git_root", input.git_root.as_deref().unwrap_or("<none>"));

    println!();
    println!("## Decision");
    println!();
    println!("| field | value |");
    println!("|---|---|");
    print_metric("identity", &report.identity.identity);
    print_metric("evidence", report.identity.evidence.label());
    print_metric(
        "high_confidence",
        report.identity.evidence.is_high_confidence().to_string(),
    );
    print_metric("current_scope", &report.current_scope);
    print_metric("legacy_scope", &report.identity.legacy_scope);
    print_metric(
        "legacy_scope_changed",
        report.legacy_scope_changed().to_string(),
    );
    print_metric("proposed_scope", &report.proposed_scope);
    print_metric(
        "production_eligible",
        report.production_eligible.to_string(),
    );
    print_metric("blocked_reason", report.blocked_reason.unwrap_or("<none>"));

    println!();
    println!("## Recommendation");
    println!();
    match (report.production_eligible, &report.identity.evidence) {
        (true, ProjectIdentityEvidence::Explicit | ProjectIdentityEvidence::GitRemote) => {
            println!("- Future canonical writes may use `proposed_scope` behind an explicit gate.");
            println!("- Preserve the legacy scope as metadata during any production experiment.");
        }
        _ => {
            println!("- Keep the current legacy scope for production writes.");
            println!("- Treat the proposed scope as diagnostic only.");
        }
    }
    println!("- This report does not change `MemorySaveTool` behavior.");

    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    fn dry(
        cwd: &str,
        current_scope: &str,
        explicit_project_id: Option<&str>,
        git_remote: Option<&str>,
        git_root: Option<&str>,
    ) -> DryRunReport {
        build_report(&DryRunInput {
            cwd: cwd.to_string(),
            current_scope: current_scope.to_string(),
            explicit_project_id: explicit_project_id.map(str::to_string),
            git_remote: git_remote.map(str::to_string),
            git_root: git_root.map(str::to_string),
        })
    }

    #[test]
    fn git_remote_identity_is_production_eligible() {
        let report = dry(
            "/Users/pallasting/Projects/agent-bridge",
            "project:/Users/pallasting/Projects/agent-bridge",
            None,
            Some("git@gitlab.com:pallasting/agent-bridge.git"),
            Some("/Users/pallasting/Projects/agent-bridge"),
        );

        assert_eq!(report.identity.evidence, ProjectIdentityEvidence::GitRemote);
        assert_eq!(
            report.proposed_scope,
            "project-id:git:gitlab.com/pallasting/agent-bridge"
        );
        assert!(report.production_eligible);
        assert_eq!(report.blocked_reason, None);
    }

    #[test]
    fn worktree_suffix_is_rescued_only_by_remote_evidence() {
        let report = dry(
            "/Data/CascadeProjects/agent-bridge-palace-apply-audit",
            "project:/Data/CascadeProjects/agent-bridge-palace-apply-audit",
            None,
            Some("git@gitlab.com:pallasting/agent-bridge.git"),
            Some("/Data/CascadeProjects/agent-bridge-palace-apply-audit"),
        );

        assert_eq!(report.identity.evidence, ProjectIdentityEvidence::GitRemote);
        assert_eq!(
            report.proposed_scope,
            "project-id:git:gitlab.com/pallasting/agent-bridge"
        );
        assert!(report.production_eligible);
    }

    #[test]
    fn git_root_name_is_diagnostic_only() {
        let report = dry(
            "/Data/CascadeProjects/agent-bridge-palace-apply-audit",
            "project:/Data/CascadeProjects/agent-bridge-palace-apply-audit",
            None,
            None,
            Some("/Data/CascadeProjects/agent-bridge-palace-apply-audit"),
        );

        assert_eq!(
            report.identity.evidence,
            ProjectIdentityEvidence::GitRootName
        );
        assert_eq!(
            report.blocked_reason,
            Some("resolver_evidence_not_high_confidence")
        );
        assert!(!report.production_eligible);
    }

    #[test]
    fn parent_directory_is_blocked_without_explicit_project_id() {
        let report = dry(
            "/Data/CascadeProjects",
            "project:/Data/CascadeProjects",
            None,
            None,
            None,
        );

        assert_eq!(
            report.identity.evidence,
            ProjectIdentityEvidence::PathFallback
        );
        assert_eq!(
            report.blocked_reason,
            Some("resolver_evidence_not_high_confidence")
        );
        assert!(!report.production_eligible);
    }

    #[test]
    fn parent_directory_can_be_eligible_with_explicit_project_id() {
        let report = dry(
            "/Data/CascadeProjects",
            "project:/Data/CascadeProjects",
            Some("git:gitlab.com/pallasting/agent-bridge"),
            None,
            None,
        );

        assert_eq!(report.identity.evidence, ProjectIdentityEvidence::Explicit);
        assert_eq!(
            report.proposed_scope,
            "project-id:git:gitlab.com/pallasting/agent-bridge"
        );
        assert!(report.production_eligible);
    }

    #[test]
    fn same_basename_different_remotes_stay_distinct() {
        let first = dry(
            "/work/agent-bridge",
            "project:/work/agent-bridge",
            None,
            Some("git@gitlab.com:pallasting/agent-bridge.git"),
            Some("/work/agent-bridge"),
        );
        let second = dry(
            "/tmp/agent-bridge",
            "project:/tmp/agent-bridge",
            None,
            Some("git@github.com:other/agent-bridge.git"),
            Some("/tmp/agent-bridge"),
        );

        assert_ne!(first.proposed_scope, second.proposed_scope);
        assert!(first.production_eligible);
        assert!(second.production_eligible);
    }

    #[test]
    fn non_project_scope_is_not_eligible() {
        let report = dry(
            "/Users/pallasting/Projects/agent-bridge",
            "domain:rust",
            None,
            Some("git@gitlab.com:pallasting/agent-bridge.git"),
            Some("/Users/pallasting/Projects/agent-bridge"),
        );

        assert_eq!(report.blocked_reason, Some("non_project_scope"));
        assert!(!report.production_eligible);
    }
}
