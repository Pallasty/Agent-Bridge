//! Phase 3 scope-canonicalization rescue gate.
//!
//! Read-only/report-only. Exercises the production project-identity registry
//! helper (`ab_bridge::project_identity::project_scopes_alias_by_registry`,
//! also used by memory scope relation code) against real Agent-Bridge scope
//! fragments. This produces the gate evidence required before any production
//! `project-id:` write switch:
//!
//! - Gate 1: a proposed explicit alias registry recovers worktree-suffixed
//!   legacy scopes that bare basename matching strands.
//! - Gate 2: a same-basename scope not in the registry must not collapse to
//!   Local.
//! - Gate 3: `project:/Data/CascadeProjects` must not become Local by basename
//!   or registry.
//!
//! No runtime change, no migration, no write switch. DB opened read-only.
//!
//! Optional env:
//! - `AB_SCOPE_CANON_GATE_DB` or legacy `AB_BASELINE_DB`
//! - `AB_SCOPE_CANON_GATE_REQUESTED`
//! - `AB_SCOPE_CANON_GATE_CANONICAL`
//!
//! Run:
//!   cargo run -p ab-bridge --example scope_canon_rescue_gate
//!   AB_SCOPE_CANON_GATE_DB=/tmp/state.copy.db cargo run -p ab-bridge --example scope_canon_rescue_gate

use ab_bridge::project_identity::project_scopes_alias_by_registry;
use ab_store::default_db_path;
use std::path::PathBuf;
use tokio_rusqlite::rusqlite::{Connection, OpenFlags};

/// The Mac checkout scope a session at `/Users/pallasting/Projects/agent-bridge` requests.
const DEFAULT_REQUESTED: &str = "project:/Users/pallasting/Projects/agent-bridge";
/// Match current live `memory_save(scope_identity_trace=true)` behavior on this checkout.
/// Operators can override this when they intentionally choose a GitHub canonical id.
const DEFAULT_CANONICAL: &str = "project-id:git:gitlab.com/pallasting/agent-bridge";
const ENV_DB: &str = "AB_SCOPE_CANON_GATE_DB";
const ENV_DB_LEGACY: &str = "AB_BASELINE_DB";
const ENV_REQUESTED: &str = "AB_SCOPE_CANON_GATE_REQUESTED";
const ENV_CANONICAL: &str = "AB_SCOPE_CANON_GATE_CANONICAL";

fn env_non_empty(name: &str) -> Option<String> {
    std::env::var(name)
        .ok()
        .map(|v| v.trim().to_string())
        .filter(|v| !v.is_empty())
}

fn db_path() -> PathBuf {
    env_non_empty(ENV_DB)
        .or_else(|| env_non_empty(ENV_DB_LEGACY))
        .map(PathBuf::from)
        .unwrap_or_else(default_db_path)
}

fn strip_project_prefix(scope: &str) -> &str {
    let scope = scope.trim();
    let Some(prefix) = scope.get(.."project:".len()) else {
        return scope;
    };
    if prefix.eq_ignore_ascii_case("project:") {
        scope.get("project:".len()..).unwrap_or(scope)
    } else {
        scope
    }
}

/// Bare lowercased basename of a `project:/abs/path` scope (the research "Arm D" identity).
fn basename_lower(scope: &str) -> String {
    strip_project_prefix(scope)
        .trim_end_matches('/')
        .rsplit('/')
        .next()
        .unwrap_or("")
        .to_ascii_lowercase()
}

fn main() {
    let db = db_path();
    let requested = env_non_empty(ENV_REQUESTED).unwrap_or_else(|| DEFAULT_REQUESTED.to_string());
    let canonical = env_non_empty(ENV_CANONICAL).unwrap_or_else(|| DEFAULT_CANONICAL.to_string());
    let conn = Connection::open_with_flags(&db, OpenFlags::SQLITE_OPEN_READ_ONLY)
        .expect("open store read-only");
    let mut stmt = conn
        .prepare(
            "SELECT scope, COUNT(*) FROM memories \
             WHERE status='active' AND scope LIKE 'project:%' \
             GROUP BY scope ORDER BY COUNT(*) DESC",
        )
        .unwrap();
    let rows: Vec<(String, i64)> = stmt
        .query_map([], |r| Ok((r.get(0)?, r.get(1)?)))
        .unwrap()
        .filter_map(Result::ok)
        .collect();

    // PROPOSED agent-bridge alias registry: canonical id <- every distinct legacy scope
    // whose basename begins with "agent-bridge" (the real fragments incl. worktree suffixes).
    // This models an explicit, owner-approvable alias set — NOT automatic basename merging.
    let req_base = basename_lower(&requested);
    let ab_fragments: Vec<(String, i64)> = rows
        .iter()
        .filter(|(s, _)| basename_lower(s).starts_with("agent-bridge"))
        .cloned()
        .collect();
    let aliases_joined: String = ab_fragments
        .iter()
        .map(|(s, _)| s.as_str())
        .collect::<Vec<_>>()
        .join(",");
    let registry = format!("{canonical}={aliases_joined}");

    println!("# Phase 3 scope-canon rescue gate (read-only)");
    println!("# store        = {}", db.display());
    println!("# requested    = {requested}");
    println!("# canonical    = {canonical}");
    println!(
        "# registry has {} agent-bridge legacy aliases\n",
        ab_fragments.len()
    );

    // Gate 1: worktree-suffix rescue.
    println!("{:<7} {:<7} {:>5}  scope", "ArmD", "Reg-E", "rows");
    let (mut basename_local, mut registry_local, mut rescued_only) = (0i64, 0i64, 0i64);
    for (scope, n) in &ab_fragments {
        let d = basename_lower(scope) == req_base; // bare basename (Arm D)
        let e = project_scopes_alias_by_registry(scope, &requested, &registry);
        if d {
            basename_local += n;
        }
        if e {
            registry_local += n;
        }
        if e && !d {
            rescued_only += n;
        }
        println!(
            "{:<7} {:<7} {:>5}  {}",
            if d { "Local" } else { "cross" },
            if e { "Local" } else { "cross" },
            n,
            scope
        );
    }
    println!("\n# basename(ArmD) Local rows : {basename_local}");
    println!("# registry(E)    Local rows : {registry_local}");
    println!(
        "# RESCUED by registry, MISSED by basename : {rescued_only}  <-- GATE 1 target (worktree-suffix rows)"
    );

    // Gate 2: same basename, different repo, not in the registry.
    let diff_remote = "project:/elsewhere/agent-bridge";
    let g2 = project_scopes_alias_by_registry(diff_remote, &requested, &registry);
    // A plausible sibling worktree-suffix that is NOT listed must also stay cross
    // (verifies the at-or-under matcher does not treat `agent-bridge-X` as under `agent-bridge`).
    let unlisted_sibling = "project:/Data/CascadeProjects/agent-bridge-NOT-IN-REGISTRY";
    let g2b = project_scopes_alias_by_registry(unlisted_sibling, &requested, &registry);

    // Gate 3: parent directory must not be Local.
    let parent = "project:/Data/CascadeProjects";
    let g3_reg = project_scopes_alias_by_registry(parent, &requested, &registry);
    let g3_base = basename_lower(parent) == req_base;

    println!(
        "\n# GATE 2a same-basename-diff-remote not-in-registry ({diff_remote}) -> registry Local? {g2}  (expect false)"
    );
    println!(
        "# GATE 2b unlisted sibling worktree-suffix ({unlisted_sibling}) -> registry Local? {g2b}  (expect false)"
    );
    println!(
        "# GATE 3  parent-dir ({parent}) -> registry Local? {g3_reg} | basename Local? {g3_base}  (expect false | false)"
    );

    let pass = rescued_only > 0 && !g2 && !g2b && !g3_reg && !g3_base;
    println!("\n# GATE VERDICT: {}", if pass { "PASS" } else { "FAIL" });
    if !pass {
        std::process::exit(1);
    }
}
