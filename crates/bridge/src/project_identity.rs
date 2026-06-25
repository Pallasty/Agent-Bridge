pub const PROJECT_ID_SCOPE_PREFIX: &str = "project-id:";
pub const LEGACY_PROJECT_SCOPE_PREFIX: &str = "project:";

#[derive(Clone, Debug, PartialEq, Eq)]
pub enum ProjectIdentityEvidence {
    Explicit,
    GitRemote,
    GitRootName,
    PathFallback,
}

impl ProjectIdentityEvidence {
    pub fn is_high_confidence(&self) -> bool {
        matches!(self, Self::Explicit | Self::GitRemote)
    }

    pub fn label(&self) -> &'static str {
        match self {
            Self::Explicit => "explicit",
            Self::GitRemote => "git_remote",
            Self::GitRootName => "git_root_name",
            Self::PathFallback => "path_fallback",
        }
    }
}

#[derive(Clone, Debug, PartialEq, Eq)]
pub struct ProjectIdentity {
    pub identity: String,
    pub canonical_scope: String,
    pub legacy_scope: String,
    pub evidence: ProjectIdentityEvidence,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum ScopeWriteShadowAction {
    Canonicalize,
    KeepLegacyNeedsReview,
    KeepUnchanged,
    Blocked,
}

impl ScopeWriteShadowAction {
    pub fn label(&self) -> &'static str {
        match self {
            Self::Canonicalize => "canonicalize_in_shadow",
            Self::KeepLegacyNeedsReview => "keep_legacy_needs_review",
            Self::KeepUnchanged => "keep_unchanged",
            Self::Blocked => "blocked",
        }
    }
}

#[derive(Clone, Debug, PartialEq, Eq)]
pub struct ScopeWriteShadowDecision {
    pub requested_scope: String,
    pub canonical_policy_scope: Option<String>,
    pub reviewed_alias_registry_match: bool,
    pub action: ScopeWriteShadowAction,
    pub reason: &'static str,
    pub proposed_scope: Option<String>,
    pub would_store_scope_if_enabled: String,
    pub legacy_scope_preserved: Option<String>,
    pub shadow_write_eligible: bool,
}

#[derive(Clone, Copy, Debug, Default)]
pub struct ProjectIdentityInput<'a> {
    pub cwd: &'a str,
    pub explicit_project_id: Option<&'a str>,
    pub git_remote: Option<&'a str>,
    pub git_root: Option<&'a str>,
}

pub fn resolve_project_identity(input: ProjectIdentityInput<'_>) -> ProjectIdentity {
    let legacy_scope = legacy_project_scope(input.cwd);
    if let Some(identity) = input.explicit_project_id.and_then(normalize_project_id) {
        return ProjectIdentity {
            canonical_scope: project_id_scope(&identity),
            identity,
            legacy_scope,
            evidence: ProjectIdentityEvidence::Explicit,
        };
    }
    if let Some(identity) = input.git_remote.and_then(normalize_git_remote_identity) {
        return ProjectIdentity {
            canonical_scope: project_id_scope(&identity),
            identity,
            legacy_scope,
            evidence: ProjectIdentityEvidence::GitRemote,
        };
    }
    if let Some(slug) = input.git_root.and_then(normalize_repo_slug) {
        let identity = format!("name:{slug}");
        return ProjectIdentity {
            canonical_scope: project_id_scope(&identity),
            identity,
            legacy_scope,
            evidence: ProjectIdentityEvidence::GitRootName,
        };
    }

    let identity = format!("path:{}", normalize_path_for_scope(input.cwd));
    ProjectIdentity {
        canonical_scope: project_id_scope(&identity),
        identity,
        legacy_scope,
        evidence: ProjectIdentityEvidence::PathFallback,
    }
}

pub fn legacy_project_scope(cwd: &str) -> String {
    format!(
        "{LEGACY_PROJECT_SCOPE_PREFIX}{}",
        normalize_path_for_scope(cwd)
    )
}

pub fn project_id_scope(identity: &str) -> String {
    let identity = normalize_project_id(identity).unwrap_or_else(|| "unknown".to_string());
    format!("{PROJECT_ID_SCOPE_PREFIX}{identity}")
}

pub fn normalize_project_id(raw: &str) -> Option<String> {
    let mut s = raw.trim();
    if let Some(rest) = strip_project_id_scope_prefix(s) {
        s = rest.trim();
    }
    if s.is_empty() {
        return None;
    }
    let s = strip_dot_git(s).trim_end_matches('/').replace('\\', "/");
    let normalized = collapse_slashes(&s).to_ascii_lowercase();
    if normalized.is_empty() {
        None
    } else {
        Some(normalized)
    }
}

pub fn normalize_git_remote_identity(remote: &str) -> Option<String> {
    let remote = remote.trim();
    if remote.is_empty() {
        return None;
    }

    if let Some(rest) = remote.strip_prefix("git@") {
        let (host, path) = rest.split_once(':')?;
        return git_identity_from_host_path(host, path);
    }

    if let Some(idx) = remote.find("://") {
        let rest = &remote[idx + 3..];
        let (authority, path) = rest.split_once('/')?;
        let host = authority.rsplit('@').next().unwrap_or(authority);
        return git_identity_from_host_path(host, path);
    }

    if let Some((authority, path)) = remote.split_once(':') {
        if authority.contains('@') || (!authority.contains('/') && path.contains('/')) {
            let host = authority.rsplit('@').next().unwrap_or(authority);
            return git_identity_from_host_path(host, path);
        }
    }

    None
}

pub fn project_scopes_canonical_match(left: &str, right: &str) -> bool {
    let Some(left) = canonical_project_scope(left) else {
        return false;
    };
    let Some(right) = canonical_project_scope(right) else {
        return false;
    };
    left == right
}

pub fn project_scopes_alias_by_registry(left: &str, right: &str, aliases: &str) -> bool {
    if project_scopes_canonical_match(left, right) {
        return true;
    }
    let left_canonical = approved_scope_alias_canonical(left, aliases);
    let right_canonical = approved_scope_alias_canonical(right, aliases);
    matches!((left_canonical, right_canonical), (Some(a), Some(b)) if a == b)
}

pub fn approved_scope_alias_canonical(scope: &str, aliases: &str) -> Option<String> {
    if let Some(canonical) = canonical_project_scope(scope) {
        return Some(canonical);
    }
    let scope = scope.trim();
    if scope.is_empty() || aliases.trim().is_empty() {
        return None;
    }

    for entry in aliases.split([';', '\n']) {
        let Some((canonical_raw, alias_raw)) = entry.split_once('=') else {
            continue;
        };
        let Some(canonical) = canonical_project_scope(canonical_raw)
            .or_else(|| normalize_project_id(canonical_raw).map(|id| project_id_scope(&id)))
        else {
            continue;
        };
        if alias_raw
            .split(',')
            .map(str::trim)
            .filter(|alias| !alias.is_empty())
            .any(|alias| scope_alias_entry_matches(scope, alias))
        {
            return Some(canonical);
        }
    }
    None
}

pub fn evaluate_scope_write_shadow(
    requested_scope: &str,
    canonical_policy_scope: Option<&str>,
    aliases: Option<&str>,
) -> ScopeWriteShadowDecision {
    let requested_scope = requested_scope.trim();
    let canonical_policy_scope =
        canonical_policy_scope.and_then(|raw| normalize_project_id(raw).map(|id| project_id_scope(&id)));
    let aliases = aliases.map(str::trim).filter(|raw| !raw.is_empty());
    let explicit_canonical = canonical_project_scope(requested_scope);
    let legacy_scope = requested_scope
        .get(..LEGACY_PROJECT_SCOPE_PREFIX.len())
        .filter(|prefix| prefix.eq_ignore_ascii_case(LEGACY_PROJECT_SCOPE_PREFIX))
        .map(|_| requested_scope.to_string());
    let mapped_alias_canonical = if explicit_canonical.is_none() {
        aliases.and_then(|registry| approved_scope_alias_canonical(requested_scope, registry))
    } else {
        None
    };
    let reviewed_alias_registry_match = matches!(
        (mapped_alias_canonical.as_deref(), canonical_policy_scope.as_deref()),
        (Some(mapped), Some(policy)) if mapped == policy
    );

    let (action, reason, proposed_scope, would_store_scope_if_enabled, legacy_scope_preserved) =
        if requested_scope.is_empty() {
            (
                ScopeWriteShadowAction::Blocked,
                "empty_scope",
                None,
                requested_scope.to_string(),
                None,
            )
        } else if let Some(explicit) = explicit_canonical {
            match canonical_policy_scope.as_deref() {
                Some(policy) if explicit == policy => (
                    ScopeWriteShadowAction::Canonicalize,
                    "explicit_project_id_matches_policy",
                    Some(explicit.clone()),
                    explicit,
                    None,
                ),
                Some(_) => (
                    ScopeWriteShadowAction::Blocked,
                    "explicit_project_id_differs_from_policy",
                    Some(explicit),
                    requested_scope.to_string(),
                    None,
                ),
                None => (
                    ScopeWriteShadowAction::KeepUnchanged,
                    "explicit_project_id_without_policy",
                    Some(explicit),
                    requested_scope.to_string(),
                    None,
                ),
            }
        } else if legacy_scope.is_none() {
            (
                ScopeWriteShadowAction::KeepUnchanged,
                "non_project_scope",
                None,
                requested_scope.to_string(),
                None,
            )
        } else {
            match (
                mapped_alias_canonical.as_deref(),
                canonical_policy_scope.as_deref(),
            ) {
                (Some(mapped), Some(policy)) if mapped == policy => (
                    ScopeWriteShadowAction::Canonicalize,
                    "approved_alias_policy",
                    Some(mapped.to_string()),
                    mapped.to_string(),
                    Some(requested_scope.to_string()),
                ),
                (Some(mapped), Some(_)) => (
                    ScopeWriteShadowAction::Blocked,
                    "mapped_to_different_canonical",
                    Some(mapped.to_string()),
                    requested_scope.to_string(),
                    Some(requested_scope.to_string()),
                ),
                (Some(mapped), None) => (
                    ScopeWriteShadowAction::KeepLegacyNeedsReview,
                    "approved_alias_without_canonical_policy",
                    Some(mapped.to_string()),
                    requested_scope.to_string(),
                    Some(requested_scope.to_string()),
                ),
                (None, Some(_)) => (
                    ScopeWriteShadowAction::KeepLegacyNeedsReview,
                    "scope_not_in_policy",
                    None,
                    requested_scope.to_string(),
                    Some(requested_scope.to_string()),
                ),
                (None, None) => (
                    ScopeWriteShadowAction::KeepLegacyNeedsReview,
                    "no_reviewed_alias_policy",
                    None,
                    requested_scope.to_string(),
                    Some(requested_scope.to_string()),
                ),
            }
        };

    let shadow_write_eligible = matches!(action, ScopeWriteShadowAction::Canonicalize);
    ScopeWriteShadowDecision {
        requested_scope: requested_scope.to_string(),
        canonical_policy_scope,
        reviewed_alias_registry_match,
        action,
        reason,
        proposed_scope,
        would_store_scope_if_enabled,
        legacy_scope_preserved,
        shadow_write_eligible,
    }
}

fn canonical_project_scope(scope: &str) -> Option<String> {
    let raw = scope.trim();
    let rest = strip_project_id_scope_prefix(raw)?;
    normalize_project_id(rest).map(|id| project_id_scope(&id))
}

fn scope_alias_entry_matches(scope: &str, alias: &str) -> bool {
    if normalize_scope_for_alias_compare(scope) == normalize_scope_for_alias_compare(alias) {
        return true;
    }
    legacy_project_scope_is_at_or_under(scope, alias)
}

fn normalize_scope_for_alias_compare(scope: &str) -> String {
    let scope = scope.trim();
    if let Some(canonical) = canonical_project_scope(scope) {
        return canonical;
    }
    if let Some(path) = scope.strip_prefix(LEGACY_PROJECT_SCOPE_PREFIX) {
        return format!(
            "{LEGACY_PROJECT_SCOPE_PREFIX}{}",
            normalize_path_for_scope(path)
        );
    }
    scope.to_string()
}

fn legacy_project_scope_is_at_or_under(scope: &str, alias_root: &str) -> bool {
    let (Some(scope), Some(alias_root)) = (
        scope.trim().strip_prefix(LEGACY_PROJECT_SCOPE_PREFIX),
        alias_root.trim().strip_prefix(LEGACY_PROJECT_SCOPE_PREFIX),
    ) else {
        return false;
    };
    let scope = normalize_path_for_scope(scope);
    let alias_root = normalize_path_for_scope(alias_root);
    scope == alias_root
        || scope
            .strip_prefix(&alias_root)
            .is_some_and(|rest| rest.starts_with('/'))
}

fn git_identity_from_host_path(host: &str, path: &str) -> Option<String> {
    let host = host.trim().trim_matches('/').to_ascii_lowercase();
    if host.is_empty() {
        return None;
    }
    let path = strip_query_fragment(path)
        .trim()
        .trim_start_matches('/')
        .trim_start_matches(':');
    let mut parts: Vec<String> = path
        .split('/')
        .map(str::trim)
        .filter(|part| !part.is_empty())
        .map(|part| part.to_ascii_lowercase())
        .collect();
    let last = parts.last_mut()?;
    *last = strip_dot_git(last).to_string();
    if last.is_empty() {
        return None;
    }
    Some(format!("git:{host}/{}", parts.join("/")))
}

fn normalize_repo_slug(path: &str) -> Option<String> {
    let base = path_basename(path)?;
    let slug = strip_dot_git(&base).to_ascii_lowercase();
    if slug.is_empty() {
        None
    } else {
        Some(slug)
    }
}

fn path_basename(path: &str) -> Option<String> {
    normalize_path_for_scope(path)
        .split('/')
        .filter(|part| !part.is_empty())
        .last()
        .map(str::to_string)
}

fn normalize_path_for_scope(path: &str) -> String {
    let path = collapse_slashes(&path.trim().replace('\\', "/"));
    let trimmed = path.trim_end_matches('/');
    if path.starts_with('/') && trimmed.is_empty() {
        "/".to_string()
    } else if trimmed.is_empty() {
        ".".to_string()
    } else {
        trimmed.to_string()
    }
}

fn strip_project_id_scope_prefix(raw: &str) -> Option<&str> {
    raw.get(..PROJECT_ID_SCOPE_PREFIX.len())
        .filter(|prefix| prefix.eq_ignore_ascii_case(PROJECT_ID_SCOPE_PREFIX))
        .and_then(|_| raw.get(PROJECT_ID_SCOPE_PREFIX.len()..))
}

fn collapse_slashes(raw: &str) -> String {
    let mut out = String::with_capacity(raw.len());
    let mut prev_slash = false;
    for ch in raw.chars() {
        if ch == '/' {
            if !prev_slash {
                out.push(ch);
            }
            prev_slash = true;
        } else {
            out.push(ch);
            prev_slash = false;
        }
    }
    out
}

fn strip_dot_git(raw: &str) -> &str {
    if raw.to_ascii_lowercase().ends_with(".git") {
        &raw[..raw.len().saturating_sub(4)]
    } else {
        raw
    }
}

fn strip_query_fragment(raw: &str) -> &str {
    raw.find(['?', '#']).map(|idx| &raw[..idx]).unwrap_or(raw)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn git_remote_forms_normalize_to_same_identity() {
        let ssh = normalize_git_remote_identity("git@github.com:Pallasting/Agent-Bridge.git");
        let https = normalize_git_remote_identity("https://github.com/pallasting/agent-bridge");
        let ssh_url =
            normalize_git_remote_identity("ssh://git@github.com/pallasting/Agent-Bridge.git");

        assert_eq!(
            ssh.as_deref(),
            Some("git:github.com/pallasting/agent-bridge")
        );
        assert_eq!(ssh, https);
        assert_eq!(https, ssh_url);
    }

    #[test]
    fn explicit_project_id_wins_over_git_remote() {
        let id = resolve_project_identity(ProjectIdentityInput {
            cwd: "/Data/CascadeProjects/agent-bridge",
            explicit_project_id: Some("Project-ID:Team/AB"),
            git_remote: Some("git@github.com:pallasting/agent-bridge.git"),
            git_root: Some("/Data/CascadeProjects/agent-bridge"),
        });

        assert_eq!(id.identity, "team/ab");
        assert_eq!(id.canonical_scope, "project-id:team/ab");
        assert_eq!(id.evidence, ProjectIdentityEvidence::Explicit);
        assert!(id.evidence.is_high_confidence());
    }

    #[test]
    fn remote_identity_joins_mac_and_aio_paths() {
        let mac = resolve_project_identity(ProjectIdentityInput {
            cwd: "/Users/pallasting/Projects/Agent-Bridge",
            explicit_project_id: None,
            git_remote: Some("https://github.com/Pallasting/Agent-Bridge.git"),
            git_root: Some("/Users/pallasting/Projects/Agent-Bridge"),
        });
        let aio = resolve_project_identity(ProjectIdentityInput {
            cwd: "/Data/CascadeProjects/agent-bridge",
            explicit_project_id: None,
            git_remote: Some("git@github.com:pallasting/agent-bridge.git"),
            git_root: Some("/Data/CascadeProjects/agent-bridge"),
        });

        assert_eq!(mac.identity, aio.identity);
        assert_eq!(mac.canonical_scope, aio.canonical_scope);
        assert_ne!(mac.legacy_scope, aio.legacy_scope);
        assert_eq!(mac.evidence, ProjectIdentityEvidence::GitRemote);
    }

    #[test]
    fn git_root_name_is_low_confidence_fallback() {
        let id = resolve_project_identity(ProjectIdentityInput {
            cwd: "/work/Agent-Bridge",
            explicit_project_id: None,
            git_remote: None,
            git_root: Some("/work/Agent-Bridge"),
        });

        assert_eq!(id.identity, "name:agent-bridge");
        assert_eq!(id.evidence, ProjectIdentityEvidence::GitRootName);
        assert!(!id.evidence.is_high_confidence());
    }

    #[test]
    fn path_fallback_preserves_absolute_path_identity() {
        let id = resolve_project_identity(ProjectIdentityInput {
            cwd: "/tmp/Agent-Bridge",
            explicit_project_id: None,
            git_remote: None,
            git_root: None,
        });

        assert_eq!(id.identity, "path:/tmp/Agent-Bridge");
        assert_eq!(id.legacy_scope, "project:/tmp/Agent-Bridge");
        assert_eq!(id.evidence, ProjectIdentityEvidence::PathFallback);
    }

    #[test]
    fn same_basename_different_remotes_do_not_collapse() {
        let first = resolve_project_identity(ProjectIdentityInput {
            cwd: "/work/agent-bridge",
            explicit_project_id: None,
            git_remote: Some("git@github.com:pallasting/agent-bridge.git"),
            git_root: Some("/work/agent-bridge"),
        });
        let second = resolve_project_identity(ProjectIdentityInput {
            cwd: "/tmp/agent-bridge",
            explicit_project_id: None,
            git_remote: Some("git@gitlab.example.com:other/agent-bridge.git"),
            git_root: Some("/tmp/agent-bridge"),
        });

        assert_ne!(first.identity, second.identity);
        assert_ne!(first.canonical_scope, second.canonical_scope);
    }

    #[test]
    fn approved_alias_registry_maps_legacy_scopes_to_canonical_scope() {
        let aliases = "project-id:git:github.com/pallasting/agent-bridge=\
            project:/Data/CascadeProjects/agent-bridge,\
            project:/Users/pallasting/Projects/Agent-Bridge";

        assert!(project_scopes_alias_by_registry(
            "project:/Data/CascadeProjects/agent-bridge",
            "project:/Users/pallasting/Projects/Agent-Bridge",
            aliases
        ));
        assert!(project_scopes_alias_by_registry(
            "project:/Data/CascadeProjects/agent-bridge/sub",
            "project-id:git:github.com/pallasting/agent-bridge",
            aliases
        ));
        assert!(!project_scopes_alias_by_registry(
            "project:/Data/CascadeProjects",
            "project:/Users/pallasting/Projects/Agent-Bridge",
            aliases
        ));
    }

    #[test]
    fn canonical_project_scopes_normalize_case_and_dot_git() {
        assert!(project_scopes_canonical_match(
            "project-id:git:github.com/Pallasting/Agent-Bridge.git",
            "project-id:git:github.com/pallasting/agent-bridge"
        ));
    }

    #[test]
    fn scope_write_shadow_canonicalizes_registered_legacy_scope() {
        let aliases = "project-id:git:gitlab.com/pallasting/agent-bridge=\
            project:/Users/pallasting/Projects/agent-bridge";
        let decision = evaluate_scope_write_shadow(
            "project:/Users/pallasting/Projects/agent-bridge/docs",
            Some("project-id:git:gitlab.com/pallasting/agent-bridge"),
            Some(aliases),
        );

        assert_eq!(decision.action, ScopeWriteShadowAction::Canonicalize);
        assert_eq!(decision.action.label(), "canonicalize_in_shadow");
        assert_eq!(decision.reason, "approved_alias_policy");
        assert!(decision.reviewed_alias_registry_match);
        assert!(decision.shadow_write_eligible);
        assert_eq!(
            decision.proposed_scope.as_deref(),
            Some("project-id:git:gitlab.com/pallasting/agent-bridge")
        );
        assert_eq!(
            decision.would_store_scope_if_enabled,
            "project-id:git:gitlab.com/pallasting/agent-bridge"
        );
        assert_eq!(
            decision.legacy_scope_preserved.as_deref(),
            Some("project:/Users/pallasting/Projects/agent-bridge/docs")
        );
    }

    #[test]
    fn scope_write_shadow_keeps_unregistered_legacy_scope_for_review() {
        let aliases = "project-id:git:gitlab.com/pallasting/agent-bridge=\
            project:/Users/pallasting/Projects/agent-bridge";
        let decision = evaluate_scope_write_shadow(
            "project:/Users/pallasting/Projects/agent-bridge-shadow-worktree",
            Some("project-id:git:gitlab.com/pallasting/agent-bridge"),
            Some(aliases),
        );

        assert_eq!(
            decision.action,
            ScopeWriteShadowAction::KeepLegacyNeedsReview
        );
        assert_eq!(decision.reason, "scope_not_in_policy");
        assert!(!decision.reviewed_alias_registry_match);
        assert!(!decision.shadow_write_eligible);
        assert_eq!(
            decision.would_store_scope_if_enabled,
            "project:/Users/pallasting/Projects/agent-bridge-shadow-worktree"
        );
    }

    #[test]
    fn scope_write_shadow_blocks_alternate_forge_project_id() {
        let decision = evaluate_scope_write_shadow(
            "project-id:git:github.com/pallasting/agent-bridge",
            Some("project-id:git:gitlab.com/pallasting/agent-bridge"),
            None,
        );

        assert_eq!(decision.action, ScopeWriteShadowAction::Blocked);
        assert_eq!(decision.reason, "explicit_project_id_differs_from_policy");
        assert!(!decision.shadow_write_eligible);
    }

    #[test]
    fn scope_write_shadow_does_not_canonicalize_legacy_without_policy() {
        let decision = evaluate_scope_write_shadow(
            "project:/Users/pallasting/Projects/agent-bridge",
            None,
            None,
        );

        assert_eq!(
            decision.action,
            ScopeWriteShadowAction::KeepLegacyNeedsReview
        );
        assert_eq!(decision.reason, "no_reviewed_alias_policy");
        assert_eq!(decision.proposed_scope, None);
        assert_eq!(
            decision.legacy_scope_preserved.as_deref(),
            Some("project:/Users/pallasting/Projects/agent-bridge")
        );
    }
}
