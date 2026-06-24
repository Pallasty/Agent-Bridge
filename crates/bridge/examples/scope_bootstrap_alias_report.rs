//! Read-only report for the session_bootstrap/list_memories_in_scope scope-alias gap.
//!
//! This example does not change runtime ranking, session_bootstrap output, or
//! state.db. It measures how many project-scoped memories the current
//! list_memories_in_scope SQL predicate can see for a cwd, then reports
//! same-project alias candidates that would need explicit review before any
//! startup-surface broadening.
//!
//! Usage:
//!
//!   cargo run -p ab-bridge --example scope_bootstrap_alias_report
//!   AB_SCOPE_BOOTSTRAP_CWD=/Users/pallasting/Projects/agent-bridge \
//!     cargo run -p ab-bridge --example scope_bootstrap_alias_report
//!   AB_SCOPE_BOOTSTRAP_DB=/tmp/state.copy.db \
//!     cargo run -p ab-bridge --example scope_bootstrap_alias_report

use ab_store::default_db_path;
use std::collections::BTreeMap;
use std::path::PathBuf;
use tokio_rusqlite::rusqlite::{Connection, OpenFlags};

#[derive(Clone, Debug)]
struct MemoryRow {
    key: String,
    kind: String,
    scope: Option<String>,
    updated_at: i64,
    importance: f64,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
enum AliasClass {
    CurrentVisible,
    SameBasenameNeedsReview,
    ContainsBasenameNeedsReview,
    Other,
}

impl AliasClass {
    fn label(self) -> &'static str {
        match self {
            Self::CurrentVisible => "current_visible",
            Self::SameBasenameNeedsReview => "same_basename_needs_review",
            Self::ContainsBasenameNeedsReview => "contains_basename_needs_review",
            Self::Other => "other",
        }
    }
}

fn normalize_name(raw: &str) -> Option<String> {
    let normalized = raw.trim().trim_end_matches('/').to_ascii_lowercase();
    (!normalized.is_empty()).then_some(normalized)
}

fn path_basename(raw: &str) -> Option<String> {
    let path = raw.trim().trim_end_matches('/').trim_end_matches('\\');
    let name = path
        .rsplit(['/', '\\'])
        .find(|part| !part.trim().is_empty())?;
    normalize_name(name)
}

fn project_scope_path(scope: &str) -> Option<&str> {
    scope
        .trim()
        .strip_prefix("project:")
        .map(str::trim)
        .filter(|path| !path.is_empty())
}

fn scope_is_global(scope: Option<&str>) -> bool {
    matches!(scope.map(str::trim), None | Some("") | Some("global"))
}

fn current_sql_local(scope: Option<&str>, cwd: &str) -> bool {
    let Some(scope) = scope.map(str::trim).filter(|scope| !scope.is_empty()) else {
        return false;
    };
    if scope == cwd {
        return true;
    }
    let Some(project_path) = project_scope_path(scope) else {
        return false;
    };
    let project_path = project_path.trim_end_matches('/');
    cwd == project_path
        || cwd
            .strip_prefix(project_path)
            .is_some_and(|rest| rest.starts_with('/'))
}

fn current_sql_visible(scope: Option<&str>, cwd: &str) -> bool {
    scope_is_global(scope) || current_sql_local(scope, cwd)
}

fn alias_class(scope: Option<&str>, cwd: &str) -> AliasClass {
    if current_sql_visible(scope, cwd) {
        return AliasClass::CurrentVisible;
    }
    let Some(scope) = scope.and_then(project_scope_path) else {
        return AliasClass::Other;
    };
    let Some(cwd_name) = path_basename(cwd) else {
        return AliasClass::Other;
    };
    let Some(scope_name) = path_basename(scope) else {
        return AliasClass::Other;
    };
    if scope_name == cwd_name {
        AliasClass::SameBasenameNeedsReview
    } else if scope_name.contains(&cwd_name) {
        AliasClass::ContainsBasenameNeedsReview
    } else {
        AliasClass::Other
    }
}

fn bump(map: &mut BTreeMap<String, usize>, key: impl Into<String>) {
    *map.entry(key.into()).or_default() += 1;
}

fn print_table(title: &str, rows: &[(String, String)]) {
    println!("\n## {title}\n");
    println!("| metric | value |");
    println!("|---|---:|");
    for (metric, value) in rows {
        println!("| {metric} | {value} |");
    }
}

fn db_path() -> PathBuf {
    std::env::var_os("AB_SCOPE_BOOTSTRAP_DB")
        .or_else(|| std::env::var_os("AGENT_BRIDGE_DB"))
        .map(PathBuf::from)
        .unwrap_or_else(default_db_path)
}

fn report_cwd() -> anyhow::Result<String> {
    if let Ok(cwd) = std::env::var("AB_SCOPE_BOOTSTRAP_CWD") {
        let cwd = cwd.trim();
        if !cwd.is_empty() {
            return Ok(cwd.to_string());
        }
    }
    Ok(std::env::current_dir()?.display().to_string())
}

fn load_rows(db: &PathBuf) -> anyhow::Result<Vec<MemoryRow>> {
    let conn = Connection::open_with_flags(db, OpenFlags::SQLITE_OPEN_READ_ONLY)?;
    let mut stmt = conn.prepare(
        "SELECT key, kind, scope, updated_at, importance
         FROM memories
         WHERE status = 'active'",
    )?;
    let rows = stmt
        .query_map([], |row| {
            Ok(MemoryRow {
                key: row.get(0)?,
                kind: row.get(1)?,
                scope: row.get(2)?,
                updated_at: row.get(3)?,
                importance: row.get(4).unwrap_or(0.5),
            })
        })?
        .collect::<Result<Vec<_>, _>>()?;
    Ok(rows)
}

fn main() -> anyhow::Result<()> {
    let db = db_path();
    let cwd = report_cwd()?;
    let max_samples = std::env::var("AB_SCOPE_BOOTSTRAP_MAX_SAMPLES")
        .ok()
        .and_then(|v| v.parse::<usize>().ok())
        .unwrap_or(20);
    let rows = load_rows(&db)?;

    let active_total = rows.len();
    let current_visible_total = rows
        .iter()
        .filter(|row| current_sql_visible(row.scope.as_deref(), &cwd))
        .count();
    let current_local_non_global = rows
        .iter()
        .filter(|row| {
            !scope_is_global(row.scope.as_deref()) && current_sql_local(row.scope.as_deref(), &cwd)
        })
        .count();
    let same_basename_omitted = rows
        .iter()
        .filter(|row| {
            alias_class(row.scope.as_deref(), &cwd) == AliasClass::SameBasenameNeedsReview
        })
        .count();
    let contains_basename_omitted = rows
        .iter()
        .filter(|row| {
            alias_class(row.scope.as_deref(), &cwd) == AliasClass::ContainsBasenameNeedsReview
        })
        .count();

    println!("# Scope Bootstrap Alias Report");
    println!();
    println!("- db: `{}`", db.display());
    println!("- cwd: `{cwd}`");
    println!("- read_only: true");
    println!("- runtime_changes: none");

    print_table(
        "Summary",
        &[
            ("active_total".into(), active_total.to_string()),
            (
                "current_sql_visible_total".into(),
                current_visible_total.to_string(),
            ),
            (
                "current_sql_local_non_global".into(),
                current_local_non_global.to_string(),
            ),
            (
                "same_basename_omitted_needs_review".into(),
                same_basename_omitted.to_string(),
            ),
            (
                "contains_basename_omitted_needs_review".into(),
                contains_basename_omitted.to_string(),
            ),
        ],
    );

    let mut class_counts: BTreeMap<String, usize> = BTreeMap::new();
    let mut omitted_kind_counts: BTreeMap<String, usize> = BTreeMap::new();
    let mut omitted_scope_counts: BTreeMap<String, usize> = BTreeMap::new();
    let mut samples: Vec<&MemoryRow> = Vec::new();

    for row in &rows {
        let class = alias_class(row.scope.as_deref(), &cwd);
        bump(&mut class_counts, class.label());
        if matches!(
            class,
            AliasClass::SameBasenameNeedsReview | AliasClass::ContainsBasenameNeedsReview
        ) {
            bump(&mut omitted_kind_counts, row.kind.clone());
            bump(
                &mut omitted_scope_counts,
                row.scope.as_deref().unwrap_or("<NULL>").to_string(),
            );
            samples.push(row);
        }
    }

    println!("\n## Class Counts\n");
    println!("| class | rows |");
    println!("|---|---:|");
    for (class, count) in &class_counts {
        println!("| {class} | {count} |");
    }

    println!("\n## Omitted Candidate Kinds\n");
    println!("| kind | rows |");
    println!("|---|---:|");
    for (kind, count) in &omitted_kind_counts {
        println!("| {kind} | {count} |");
    }

    println!("\n## Omitted Candidate Scopes\n");
    println!("| scope | rows |");
    println!("|---|---:|");
    for (scope, count) in &omitted_scope_counts {
        println!("| `{scope}` | {count} |");
    }

    samples.sort_by(|a, b| {
        b.importance
            .partial_cmp(&a.importance)
            .unwrap_or(std::cmp::Ordering::Equal)
            .then_with(|| b.updated_at.cmp(&a.updated_at))
            .then_with(|| a.key.cmp(&b.key))
    });
    samples.truncate(max_samples);

    println!("\n## Top Omitted Candidates\n");
    println!("| class | kind | importance | key | scope |");
    println!("|---|---|---:|---|---|");
    for row in samples {
        let class = alias_class(row.scope.as_deref(), &cwd).label();
        println!(
            "| {class} | {} | {:.3} | `{}` | `{}` |",
            row.kind,
            row.importance,
            row.key,
            row.scope.as_deref().unwrap_or("<NULL>")
        );
    }

    println!("\n## Recommendation\n");
    println!();
    println!("- Keep store SQL unchanged until alias evidence is explicit.");
    println!("- Treat same/contains basename rows as `needs_review`, not auto-admitted.");
    println!("- A future bootstrap supplement should show this trace before injecting rows.");

    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn current_sql_visible_keeps_global_and_exact_project_scope() {
        let cwd = "/Users/pallasting/Projects/agent-bridge";
        assert!(current_sql_visible(None, cwd));
        assert!(current_sql_visible(Some("global"), cwd));
        assert!(current_sql_visible(
            Some("project:/Users/pallasting/Projects/agent-bridge"),
            cwd
        ));
    }

    #[test]
    fn alias_class_marks_cross_host_same_basename_for_review() {
        let cwd = "/Users/pallasting/Projects/agent-bridge";
        assert_eq!(
            alias_class(Some("project:/Data/CascadeProjects/agent-bridge"), cwd),
            AliasClass::SameBasenameNeedsReview
        );
    }

    #[test]
    fn alias_class_marks_worktree_suffix_for_review_not_auto_admit() {
        let cwd = "/Users/pallasting/Projects/agent-bridge";
        assert_eq!(
            alias_class(
                Some("project:/Data/CascadeProjects/agent-bridge-palace-apply-audit"),
                cwd
            ),
            AliasClass::ContainsBasenameNeedsReview
        );
    }

    #[test]
    fn alias_class_does_not_admit_parent_directory() {
        let cwd = "/Users/pallasting/Projects/agent-bridge";
        assert_eq!(
            alias_class(Some("project:/Data/CascadeProjects"), cwd),
            AliasClass::Other
        );
    }
}
