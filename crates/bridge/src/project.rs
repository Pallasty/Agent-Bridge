//! Project perception (W2): lightweight filesystem scan + git helpers.
//!
//! See `docs/DESIGN-warp-first-agent-shell.md` — no tree-sitter (D10).

use ab_core::{Error, Result};
use serde_json::{json, Value};
use std::collections::HashSet;
use std::path::{Path, PathBuf};
use std::process::Command;

/// Resolve optional cwd argument; default process current directory.
pub fn resolve_cwd(raw: Option<&str>) -> Result<PathBuf> {
    let base = match raw {
        Some(s) if !s.trim().is_empty() => PathBuf::from(s.trim()),
        _ => std::env::current_dir().map_err(Error::Io)?,
    };
    let meta = std::fs::metadata(&base).map_err(Error::Io)?;
    if !meta.is_dir() {
        return Err(Error::InvalidArgument(format!(
            "cwd is not a directory: {}",
            base.display()
        )));
    }
    Ok(base)
}

/// Auto-detect languages, build tooling hints, workspace members (Rust), git snapshot.
pub fn detect_project(cwd: &Path) -> Result<Value> {
    let scan_paths = walk_manifest_ancestors(cwd, 64);
    let mut languages: Vec<String> = Vec::new();
    let mut seen_lang: HashSet<&'static str> = HashSet::new();

    let mut has_cargo = false;
    let mut has_pkg_json = false;
    let mut has_py = false;
    let mut has_go = false;
    let mut has_make = false;

    let mut package_json_dir: Option<PathBuf> = None;

    for p in &scan_paths {
        if p.join("Cargo.toml").is_file() {
            has_cargo = true;
        }
        if p.join("package.json").is_file() {
            has_pkg_json = true;
            package_json_dir.get_or_insert_with(|| p.clone());
        }
        if p.join("pyproject.toml").is_file()
            || p.join("setup.py").is_file()
            || p.join("requirements.txt").is_file()
        {
            has_py = true;
        }
        if p.join("go.mod").is_file() {
            has_go = true;
        }
        if p.join("Makefile").is_file() || p.join("makefile").is_file() {
            has_make = true;
        }
    }

    let push_lang =
        |languages: &mut Vec<String>, seen: &mut HashSet<&'static str>, id: &'static str| {
            if seen.insert(id) {
                languages.push(id.to_string());
            }
        };

    if has_cargo {
        push_lang(&mut languages, &mut seen_lang, "rust");
    }
    if has_pkg_json {
        push_lang(&mut languages, &mut seen_lang, "javascript");
    }
    if has_py {
        push_lang(&mut languages, &mut seen_lang, "python");
    }
    if has_go {
        push_lang(&mut languages, &mut seen_lang, "go");
    }
    if has_make {
        push_lang(&mut languages, &mut seen_lang, "make");
    }

    let cargo_meta = cargo_metadata_workspace(cwd);
    let workspace_members = cargo_meta
        .as_ref()
        .map(|m| extract_workspace_package_names(m))
        .unwrap_or_default();

    let is_rust_workspace = workspace_members.len() > 1;

    let (build_system, test_command, lint_command, format_command) =
        primary_build_hints(has_cargo, is_rust_workspace, has_pkg_json, has_go, has_make);

    let mut npm_hints = json!({});
    if let Some(ref dir) = package_json_dir {
        npm_hints = package_json_hints(dir);
    }

    let git = collect_git_snapshot(cwd);

    Ok(json!({
        "cwd": cwd.display().to_string(),
        "languages": languages,
        "build_system": build_system,
        "workspace_members": workspace_members,
        "test_command": test_command,
        "lint_command": lint_command,
        "format_command": format_command,
        "package_hints": npm_hints,
        "git_branch": git.active_branch,
        "git_clean": git.clean,
        "recent_commit": git.recent_commit,
        "git_is_repo": git.is_repo,
    }))
}

fn primary_build_hints(
    has_cargo: bool,
    is_workspace: bool,
    has_pkg_json: bool,
    has_go: bool,
    has_make: bool,
) -> (Value, Option<String>, Option<String>, Option<String>) {
    if has_cargo {
        let (test, lint, fmt) = if is_workspace {
            (
                Some("cargo test --workspace".into()),
                Some("cargo clippy --workspace -- -D warnings".into()),
                Some("cargo fmt --all".into()),
            )
        } else {
            (
                Some("cargo test".into()),
                Some("cargo clippy --all -- -D warnings".into()),
                Some("cargo fmt --all".into()),
            )
        };
        return (json!("cargo"), test, lint, fmt);
    }
    if has_pkg_json {
        return (
            json!("node"),
            Some("npm test".into()),
            Some("npm run lint".into()),
            Some("npx prettier --write .".into()),
        );
    }
    if has_go {
        return (
            json!("go"),
            Some("go test ./...".into()),
            Some("go vet ./...".into()),
            Some("gofmt -w .".into()),
        );
    }
    if has_make {
        return (json!("make"), Some("make test".into()), None, None);
    }
    (json!(null), None, None, None)
}

fn package_json_hints(dir: &Path) -> Value {
    let path = dir.join("package.json");
    let Ok(raw) = std::fs::read_to_string(&path) else {
        return json!({});
    };
    let Ok(v) = serde_json::from_str::<Value>(&raw) else {
        return json!({});
    };

    let pkg_mgr = if dir.join("pnpm-lock.yaml").is_file() {
        "pnpm"
    } else if dir.join("yarn.lock").is_file() {
        "yarn"
    } else if dir.join("bun.lockb").is_file() {
        "bun"
    } else {
        "npm"
    };

    let scripts = v.get("scripts").cloned().unwrap_or(json!({}));
    let mut named = serde_json::Map::new();
    for key in ["test", "lint", "format", "build"] {
        if let Some(s) = scripts.get(key).and_then(|x| x.as_str()) {
            named.insert(key.to_string(), Value::String(s.to_string()));
        }
    }

    json!({
        "package_manager": pkg_mgr,
        "scripts": named,
    })
}

fn walk_manifest_ancestors(start: &Path, max_hops: usize) -> Vec<PathBuf> {
    let mut out = Vec::new();
    let mut cur = Some(start);
    let mut hops = 0;
    while let Some(p) = cur {
        if hops >= max_hops {
            break;
        }
        out.push(p.to_path_buf());
        cur = p.parent();
        hops += 1;
    }
    out
}

fn cargo_metadata_workspace(cwd: &Path) -> Option<Value> {
    let out = Command::new("cargo")
        .current_dir(cwd)
        .args(["metadata", "--no-deps", "--format-version", "1"])
        .output()
        .ok()?;
    if !out.status.success() {
        return None;
    }
    serde_json::from_slice(&out.stdout).ok()
}

fn extract_workspace_package_names(meta: &Value) -> Vec<String> {
    let Some(members) = meta.get("workspace_members").and_then(|m| m.as_array()) else {
        return Vec::new();
    };
    let Some(packages) = meta.get("packages").and_then(|p| p.as_array()) else {
        return Vec::new();
    };

    let id_set: HashSet<&str> = members.iter().filter_map(|v| v.as_str()).collect();
    let mut names: Vec<String> = packages
        .iter()
        .filter_map(|pkg| {
            let id = pkg.get("id").and_then(|v| v.as_str())?;
            if !id_set.contains(id) {
                return None;
            }
            pkg.get("name")
                .and_then(|n| n.as_str())
                .map(|s| s.to_string())
        })
        .collect();
    names.sort();
    names.dedup();
    names
}

struct GitSnap {
    is_repo: bool,
    active_branch: Option<String>,
    recent_commit: Option<String>,
    clean: Option<bool>,
}

fn collect_git_snapshot(cwd: &Path) -> GitSnap {
    let inside = git_output(cwd, &["rev-parse", "--is-inside-work-tree"]);
    let is_repo = inside
        .as_deref()
        .map(|s| s.trim() == "true")
        .unwrap_or(false);
    if !is_repo {
        return GitSnap {
            is_repo: false,
            active_branch: None,
            recent_commit: None,
            clean: None,
        };
    }
    let branch = git_output(cwd, &["rev-parse", "--abbrev-ref", "HEAD"])
        .map(|s| s.trim().to_string())
        .filter(|s| !s.is_empty());
    let recent_commit = git_output(cwd, &["log", "-1", "--oneline"]).map(|s| s.trim().to_string());
    let porcelain = git_output(cwd, &["status", "--porcelain"]).unwrap_or_default();
    let clean = Some(porcelain.trim().is_empty());
    GitSnap {
        is_repo: true,
        active_branch: branch,
        recent_commit,
        clean,
    }
}

fn git_output(cwd: &Path, args: &[&str]) -> Option<String> {
    let out = Command::new("git")
        .current_dir(cwd)
        .args(args)
        .output()
        .ok()?;
    if !out.status.success() {
        return None;
    }
    Some(String::from_utf8_lossy(&out.stdout).into_owned())
}

// --- changes_digest ---

/// `scope`: `working_tree` | `staged` | `last_commit` | `branch_vs_main`
pub fn changes_digest(cwd: &Path, scope: &str) -> Result<Value> {
    let inside = git_output(cwd, &["rev-parse", "--is-inside-work-tree"])
        .map(|s| s.trim() == "true")
        .unwrap_or(false);
    if !inside {
        return Err(Error::Backend(format!(
            "not a git repository: {}",
            cwd.display()
        )));
    }

    let branch_range: Option<String> = if scope == "branch_vs_main" {
        Some(
            merge_base_main(cwd)
                .map(|b| format!("{b}..HEAD"))
                .ok_or_else(|| {
                    Error::Backend(
                        "branch_vs_main: could not resolve merge-base with main/master".into(),
                    )
                })?,
        )
    } else {
        None
    };

    let numstat = match scope {
        "working_tree" => git_output_joined(cwd, &["diff", "--numstat"], &[])?,
        "staged" => git_output_joined(cwd, &["diff", "--cached", "--numstat"], &[])?,
        "last_commit" => git_output_joined(cwd, &["show", "--numstat", "--pretty=format:"], &[])?,
        "branch_vs_main" => {
            let range = branch_range.as_ref().map(|s| s.as_str()).unwrap_or("");
            git_output_joined(cwd, &["diff", "--numstat"], &[range])?
        }
        other => {
            return Err(Error::InvalidArgument(format!(
                "unknown scope '{other}'; expected working_tree|staged|last_commit|branch_vs_main"
            )));
        }
    };

    let name_stat = match scope {
        "working_tree" => git_output_joined(cwd, &["diff", "--name-status"], &[])?,
        "staged" => git_output_joined(cwd, &["diff", "--cached", "--name-status"], &[])?,
        "last_commit" => {
            git_output_joined(cwd, &["show", "--name-status", "--pretty=format:"], &[])?
        }
        "branch_vs_main" => {
            let range = branch_range.as_ref().map(|s| s.as_str()).unwrap_or("");
            git_output_joined(cwd, &["diff", "--name-status"], &[range])?
        }
        other => {
            return Err(Error::InvalidArgument(format!(
                "unknown scope '{other}'; expected working_tree|staged|last_commit|branch_vs_main"
            )));
        }
    };

    let files = parse_numstat(&numstat);
    let total_ins: u64 = files.iter().map(|f| u64::from(f.insertions)).sum();
    let total_del: u64 = files.iter().map(|f| u64::from(f.deletions)).sum();

    let name_status = parse_name_status(&name_stat);

    let summary: Vec<Value> = files
        .iter()
        .map(|f| {
            json!({
                "file": f.path,
                "insertions": f.insertions,
                "deletions": f.deletions,
                "change": format!("+{} -{}", f.insertions, f.deletions),
            })
        })
        .collect();

    Ok(json!({
        "scope": scope,
        "cwd": cwd.display().to_string(),
        "files_changed": files.len(),
        "insertions": total_ins,
        "deletions": total_del,
        "summary": summary,
        "name_status": name_status,
    }))
}

/// Read-only preflight before creating a PR/MR review artifact.
///
/// Checks whether `source` and `target` have a usable merge-base and summarizes
/// the review range as `merge-base..source`. This catches the dangerous case
/// where a default target branch is unrelated and would show a whole-tree diff.
pub fn git_topology_preflight(
    cwd: &Path,
    target: &str,
    source: &str,
    max_files: usize,
) -> Result<Value> {
    let inside = git_output(cwd, &["rev-parse", "--is-inside-work-tree"])
        .map(|s| s.trim() == "true")
        .unwrap_or(false);
    if !inside {
        return Err(Error::Backend(format!(
            "not a git repository: {}",
            cwd.display()
        )));
    }

    let target = target.trim();
    let source = source.trim();
    if target.is_empty() {
        return Err(Error::InvalidArgument("target must not be empty".into()));
    }
    if source.is_empty() {
        return Err(Error::InvalidArgument("source must not be empty".into()));
    }

    let target_sha = git_output(cwd, &["rev-parse", target]).map(|s| s.trim().to_string());
    let source_sha = git_output(cwd, &["rev-parse", source]).map(|s| s.trim().to_string());
    let merge_base = git_output(cwd, &["merge-base", target, source])
        .map(|s| s.trim().to_string())
        .filter(|s| !s.is_empty());

    let mut warnings: Vec<String> = Vec::new();
    if merge_base.is_none() {
        warnings.push(format!(
            "no merge-base between target '{target}' and source '{source}'; review diff may be a whole-tree comparison"
        ));
        return Ok(json!({
            "kind": "agent_bridge_git_topology_preflight.v0",
            "status": "blocked",
            "cwd": cwd.display().to_string(),
            "target": target,
            "source": source,
            "target_sha": target_sha,
            "source_sha": source_sha,
            "merge_base_found": false,
            "merge_base": Value::Null,
            "files_changed": Value::Null,
            "insertions": Value::Null,
            "deletions": Value::Null,
            "summary": [],
            "name_status": [],
            "warnings": warnings,
        }));
    }

    let merge_base = merge_base.unwrap();
    let range = format!("{merge_base}..{source}");
    let numstat = git_output_joined(cwd, &["diff", "--numstat"], &[&range])?;
    let name_stat = git_output_joined(cwd, &["diff", "--name-status"], &[&range])?;
    let files = parse_numstat(&numstat);
    let total_ins: u64 = files.iter().map(|f| u64::from(f.insertions)).sum();
    let total_del: u64 = files.iter().map(|f| u64::from(f.deletions)).sum();
    let name_status = parse_name_status(&name_stat);

    let max_files = max_files.max(1);
    if files.len() > max_files {
        warnings.push(format!(
            "files_changed={} exceeds max_files={max_files}; inspect target/source before opening review artifact",
            files.len()
        ));
    }

    let summary: Vec<Value> = files
        .iter()
        .map(|f| {
            json!({
                "file": f.path,
                "insertions": f.insertions,
                "deletions": f.deletions,
                "change": format!("+{} -{}", f.insertions, f.deletions),
            })
        })
        .collect();
    let status = if warnings.is_empty() {
        "ready"
    } else {
        "warning"
    };

    Ok(json!({
        "kind": "agent_bridge_git_topology_preflight.v0",
        "status": status,
        "cwd": cwd.display().to_string(),
        "target": target,
        "source": source,
        "target_sha": target_sha,
        "source_sha": source_sha,
        "merge_base_found": true,
        "merge_base": merge_base,
        "range": range,
        "files_changed": files.len(),
        "insertions": total_ins,
        "deletions": total_del,
        "summary": summary,
        "name_status": name_status,
        "warnings": warnings,
    }))
}

fn git_output_joined(cwd: &Path, base: &[&str], extra: &[&str]) -> Result<String> {
    let out = Command::new("git")
        .current_dir(cwd)
        .args(base.iter().chain(extra.iter()))
        .output()
        .map_err(Error::Io)?;
    if !out.status.success() {
        let stderr = String::from_utf8_lossy(&out.stderr);
        return Err(Error::Backend(format!(
            "git {} failed: {}",
            base.join(" "),
            stderr.trim()
        )));
    }
    Ok(String::from_utf8_lossy(&out.stdout).into_owned())
}

fn merge_base_main(cwd: &Path) -> Option<String> {
    for r in ["main", "origin/main", "master", "origin/master"] {
        let out = git_output(cwd, &["merge-base", "HEAD", r])?;
        let b = out.trim();
        if !b.is_empty() {
            return Some(b.to_string());
        }
    }
    None
}

#[derive(Debug, Clone)]
struct NumStatRow {
    path: String,
    insertions: u32,
    deletions: u32,
}

fn parse_numstat(raw: &str) -> Vec<NumStatRow> {
    let mut out = Vec::new();
    for line in raw.lines() {
        let line = line.trim();
        if line.is_empty() {
            continue;
        }
        let mut parts = line.splitn(3, '\t');
        let a = parts.next().unwrap_or("");
        let b = parts.next().unwrap_or("");
        let path = parts.next().unwrap_or("").trim();
        if path.is_empty() {
            continue;
        }
        let ins = if a == "-" { 0 } else { a.parse().unwrap_or(0) };
        let del = if b == "-" { 0 } else { b.parse().unwrap_or(0) };
        out.push(NumStatRow {
            path: path.to_string(),
            insertions: ins,
            deletions: del,
        });
    }
    out
}

fn parse_name_status(raw: &str) -> Vec<Value> {
    let mut out = Vec::new();
    for line in raw.lines() {
        let line = line.trim();
        if line.is_empty() {
            continue;
        }
        let mut it = line.splitn(2, '\t');
        let status = it.next().unwrap_or("").trim();
        let path = it.next().unwrap_or("").trim();
        if status.is_empty() {
            continue;
        }
        let mut m = serde_json::Map::new();
        m.insert("status".into(), Value::String(status.to_string()));
        if path.contains('\t') {
            let mut ps = path.splitn(2, '\t');
            let old_p = ps.next().unwrap_or("");
            let new_p = ps.next().unwrap_or("");
            m.insert("path".into(), Value::String(new_p.to_string()));
            m.insert("from".into(), Value::String(old_p.to_string()));
        } else {
            m.insert("path".into(), Value::String(path.to_string()));
        }
        out.push(Value::Object(m));
    }
    out
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::json;

    #[test]
    fn parse_numstat_basic() {
        let raw = "12\t3\tcrates/foo.rs\n-\t-\tbinary.dat\n";
        let rows = parse_numstat(raw);
        assert_eq!(rows.len(), 2);
        assert_eq!(rows[0].path, "crates/foo.rs");
        assert_eq!(rows[0].insertions, 12);
        assert_eq!(rows[0].deletions, 3);
        assert_eq!(rows[1].insertions, 0);
        assert_eq!(rows[1].deletions, 0);
    }

    #[test]
    fn parse_name_status_rename() {
        let raw = "R083\told.rs\tnew.rs\n";
        let v = parse_name_status(raw);
        assert_eq!(v.len(), 1);
        assert_eq!(v[0]["status"], "R083");
        assert_eq!(v[0]["path"], "new.rs");
        assert_eq!(v[0]["from"], "old.rs");
    }

    #[test]
    fn detect_project_agent_bridge_repo() {
        let manifest_dir = PathBuf::from(env!("CARGO_MANIFEST_DIR"));
        let repo_root = manifest_dir
            .ancestors()
            .find(|p| p.join("Cargo.toml").is_file() && p.join("crates").is_dir())
            .expect("workspace root")
            .to_path_buf();
        let v = detect_project(&repo_root).expect("detect");
        let langs = v["languages"].as_array().expect("languages");
        assert!(
            langs.iter().any(|x| x.as_str() == Some("rust")),
            "expected rust in {:?}",
            langs
        );
        let members = v["workspace_members"]
            .as_array()
            .cloned()
            .unwrap_or_default();
        assert!(
            members.iter().any(|m| m.as_str() == Some("ab-bridge")),
            "workspace_members: {:?}",
            members
        );
        assert_eq!(v["build_system"], json!("cargo"));
    }

    #[test]
    fn changes_digest_last_commit_smoke() {
        let manifest_dir = PathBuf::from(env!("CARGO_MANIFEST_DIR"));
        let repo_root = manifest_dir
            .ancestors()
            .find(|p| p.join("Cargo.toml").is_file() && p.join("crates").is_dir())
            .expect("workspace root")
            .to_path_buf();
        let v = changes_digest(&repo_root, "last_commit").expect("digest");
        assert_eq!(v["scope"], "last_commit");
        assert!(v["files_changed"].as_u64().is_some());
    }

    #[test]
    fn git_topology_preflight_blocks_unrelated_target() {
        let tmp = tempfile::tempdir().expect("tmp");
        init_git_repo(tmp.path());
        write_file(tmp.path().join("README.md"), "base\n");
        git_ok(tmp.path(), &["add", "README.md"]);
        git_ok(tmp.path(), &["commit", "-m", "base"]);
        git_ok(tmp.path(), &["branch", "target"]);
        git_ok(tmp.path(), &["checkout", "--orphan", "source"]);
        write_file(tmp.path().join("README.md"), "source\n");
        git_ok(tmp.path(), &["add", "README.md"]);
        git_ok(tmp.path(), &["commit", "-m", "source"]);

        let v = git_topology_preflight(tmp.path(), "target", "source", 100).expect("preflight");

        assert_eq!(v["status"], "blocked");
        assert_eq!(v["merge_base_found"], false);
        assert!(v["warnings"]
            .as_array()
            .expect("warnings")
            .iter()
            .any(|w| w.as_str().unwrap_or("").contains("no merge-base")));
    }

    #[test]
    fn git_topology_preflight_reports_ready_small_range() {
        let tmp = tempfile::tempdir().expect("tmp");
        init_git_repo(tmp.path());
        write_file(tmp.path().join("README.md"), "base\n");
        git_ok(tmp.path(), &["add", "README.md"]);
        git_ok(tmp.path(), &["commit", "-m", "base"]);
        git_ok(tmp.path(), &["branch", "target"]);
        git_ok(tmp.path(), &["checkout", "-b", "source"]);
        write_file(tmp.path().join("feature.txt"), "new\n");
        git_ok(tmp.path(), &["add", "feature.txt"]);
        git_ok(tmp.path(), &["commit", "-m", "feature"]);

        let v = git_topology_preflight(tmp.path(), "target", "source", 100).expect("preflight");

        assert_eq!(v["status"], "ready");
        assert_eq!(v["merge_base_found"], true);
        assert_eq!(v["files_changed"], 1);
        assert_eq!(v["insertions"], 1);
        assert_eq!(v["deletions"], 0);
    }

    fn init_git_repo(path: &Path) {
        git_ok(path, &["init", "-q"]);
        git_ok(
            path,
            &["config", "user.email", "agent-bridge@example.invalid"],
        );
        git_ok(path, &["config", "user.name", "Agent Bridge Test"]);
    }

    fn write_file(path: PathBuf, body: &str) {
        std::fs::write(path, body).expect("write");
    }

    fn git_ok(cwd: &Path, args: &[&str]) {
        let out = Command::new("git")
            .current_dir(cwd)
            .args(args)
            .output()
            .expect("git");
        assert!(
            out.status.success(),
            "git {:?} failed: {}",
            args,
            String::from_utf8_lossy(&out.stderr)
        );
    }
}
