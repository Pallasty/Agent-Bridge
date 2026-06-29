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

/// `scope`: `working_tree` | `working` | `staged` | `last_commit` | `branch_vs_main`
pub fn changes_digest(cwd: &Path, scope: &str) -> Result<Value> {
    let scope = normalize_changes_digest_scope(scope);
    let inside = git_output(cwd, &["rev-parse", "--is-inside-work-tree"])
        .map(|s| s.trim() == "true")
        .unwrap_or(false);
    if !inside {
        return Err(Error::Backend(format!(
            "not a git repository: {}",
            cwd.display()
        )));
    }

    let mut warnings: Vec<String> = Vec::new();
    let branch_range: Option<String> = if scope == "branch_vs_main" {
        match merge_base_main(cwd) {
            Some(base) => Some(format!("{base}..HEAD")),
            None => {
                warnings.push(
                    "branch_vs_main: could not resolve merge-base with main/master; diff omitted"
                        .to_string(),
                );
                None
            }
        }
    } else {
        None
    };

    let numstat = match scope {
        "working_tree" => git_output_joined(cwd, &["diff", "--numstat"], &[])?,
        "staged" => git_output_joined(cwd, &["diff", "--cached", "--numstat"], &[])?,
        "last_commit" => git_output_joined(
            cwd,
            &["show", "--first-parent", "--numstat", "--pretty=format:"],
            &[],
        )?,
        "branch_vs_main" => {
            if let Some(range) = branch_range.as_ref().map(|s| s.as_str()) {
                git_output_joined(cwd, &["diff", "--numstat"], &[range])?
            } else {
                String::new()
            }
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
        "last_commit" => git_output_joined(
            cwd,
            &[
                "show",
                "--first-parent",
                "--name-status",
                "--pretty=format:",
            ],
            &[],
        )?,
        "branch_vs_main" => {
            if let Some(range) = branch_range.as_ref().map(|s| s.as_str()) {
                git_output_joined(cwd, &["diff", "--name-status"], &[range])?
            } else {
                String::new()
            }
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

    // Patch/hunk scope: the same diff WITH its unified hunks, split per file and
    // bounded so a digest can show *what* changed, not just how much. Additive
    // (`patches`/`patch_truncated`) — existing consumers ignore the new fields,
    // and the signature is unchanged so no MCP-tool wiring shifts. Caps keep the
    // response bounded regardless of diff size (OB-4 step 1, ORCA_BORROW_PLAN §3).
    let patch_raw = match scope {
        "working_tree" => git_output_joined(cwd, &["diff"], &[])?,
        "staged" => git_output_joined(cwd, &["diff", "--cached"], &[])?,
        "last_commit" => {
            git_output_joined(cwd, &["show", "--first-parent", "--pretty=format:"], &[])?
        }
        "branch_vs_main" => {
            if let Some(range) = branch_range.as_ref().map(|s| s.as_str()) {
                git_output_joined(cwd, &["diff"], &[range])?
            } else {
                String::new()
            }
        }
        other => {
            return Err(Error::InvalidArgument(format!(
                "unknown scope '{other}'; expected working_tree|staged|last_commit|branch_vs_main"
            )));
        }
    };
    let mut patch_truncated = false;
    let mut patches: Vec<Value> = Vec::new();
    for (i, (path, text)) in split_patch_by_file(&patch_raw).into_iter().enumerate() {
        if i >= CHANGES_DIGEST_MAX_PATCH_FILES {
            patch_truncated = true;
            break;
        }
        let (body, file_trunc) =
            truncate_patch_lines(&text, CHANGES_DIGEST_MAX_PATCH_LINES_PER_FILE);
        patch_truncated |= file_trunc;
        patches.push(json!({ "file": path, "patch": body, "truncated": file_trunc }));
    }

    Ok(json!({
        "scope": scope,
        "cwd": cwd.display().to_string(),
        "files_changed": files.len(),
        "insertions": total_ins,
        "deletions": total_del,
        "summary": summary,
        "name_status": name_status,
        "patches": patches,
        "patch_truncated": patch_truncated,
        "warnings": warnings,
        "merge_base_found": scope != "branch_vs_main" || branch_range.is_some(),
        "branch_range": branch_range,
    }))
}

fn normalize_changes_digest_scope(scope: &str) -> &str {
    match scope {
        "working" => "working_tree",
        other => other,
    }
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

/// Caps that keep `changes_digest`'s `patches` bounded regardless of diff size:
/// at most this many files carry a patch, and each patch is truncated past this
/// many lines (with a marker). Both surface via `patch_truncated`.
const CHANGES_DIGEST_MAX_PATCH_FILES: usize = 50;
const CHANGES_DIGEST_MAX_PATCH_LINES_PER_FILE: usize = 200;

/// Extract the b-side (new) path from a `diff --git a/<old> b/<new>` header.
/// Best-effort: uses the last ` b/` marker, which is correct for the common
/// case (paths without an embedded ` b/`). Returns None if not a diff header.
fn diff_git_b_path(line: &str) -> Option<String> {
    let rest = line.strip_prefix("diff --git ")?;
    rest.rfind(" b/").map(|idx| rest[idx + 3..].to_string())
}

/// Split a unified `git diff` into `(file_path, patch_text)` pairs — one chunk
/// per file, each starting at its `diff --git` header and running to the next.
/// The path is the diff's b-side; an unparseable header falls back to `"?"`.
/// Pure (no git), so it is unit-tested without a repository.
fn split_patch_by_file(patch: &str) -> Vec<(String, String)> {
    let mut out: Vec<(String, String)> = Vec::new();
    let mut cur_path: Option<String> = None;
    let mut cur_lines: Vec<&str> = Vec::new();
    for line in patch.lines() {
        if line.starts_with("diff --git ") {
            if let Some(p) = cur_path.take() {
                out.push((p, cur_lines.join("\n")));
            }
            cur_lines.clear();
            cur_path = Some(diff_git_b_path(line).unwrap_or_else(|| "?".to_string()));
        }
        if cur_path.is_some() {
            cur_lines.push(line);
        }
    }
    if let Some(p) = cur_path.take() {
        out.push((p, cur_lines.join("\n")));
    }
    out
}

/// Truncate `text` to at most `max_lines` lines, appending a count marker when
/// trimmed. Returns `(body, truncated)`.
fn truncate_patch_lines(text: &str, max_lines: usize) -> (String, bool) {
    let lines: Vec<&str> = text.lines().collect();
    if lines.len() <= max_lines {
        (text.to_string(), false)
    } else {
        let omitted = lines.len() - max_lines;
        let kept = lines[..max_lines].join("\n");
        (format!("{kept}\n… ({omitted} more lines truncated)"), true)
    }
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
    fn diff_git_b_path_parses_new_side() {
        assert_eq!(
            diff_git_b_path("diff --git a/src/a.rs b/src/a.rs").as_deref(),
            Some("src/a.rs")
        );
        assert_eq!(diff_git_b_path("not a header"), None);
    }

    #[test]
    fn split_patch_by_file_splits_per_file() {
        let raw = [
            "diff --git a/src/a.rs b/src/a.rs",
            "index 111..222 100644",
            "--- a/src/a.rs",
            "+++ b/src/a.rs",
            "@@ -1,2 +1,3 @@",
            " keep",
            "-old",
            "+new",
            "+added",
            "diff --git a/docs/b.md b/docs/b.md",
            "index 333..444 100644",
            "--- a/docs/b.md",
            "+++ b/docs/b.md",
            "@@ -1 +1 @@",
            "-x",
            "+y",
        ]
        .join("\n");
        let pairs = split_patch_by_file(&raw);
        assert_eq!(pairs.len(), 2);
        assert_eq!(pairs[0].0, "src/a.rs");
        assert_eq!(pairs[1].0, "docs/b.md");
        // Each chunk starts at its own header and does not bleed into the next.
        assert!(pairs[0].1.starts_with("diff --git a/src/a.rs b/src/a.rs"));
        assert!(pairs[0].1.contains("+added"));
        assert!(!pairs[0].1.contains("docs/b.md"));
        assert!(pairs[1].1.contains("+y"));
        // Context line keeps its leading space.
        assert!(pairs[0].1.contains("\n keep"));
    }

    #[test]
    fn truncate_patch_lines_caps_and_marks() {
        let (body, trunc) = truncate_patch_lines("l1\nl2\nl3", 5);
        assert!(!trunc);
        assert_eq!(body, "l1\nl2\nl3");

        let (body, trunc) = truncate_patch_lines("l1\nl2\nl3\nl4\nl5", 2);
        assert!(trunc);
        assert!(body.starts_with("l1\nl2\n"));
        assert!(body.contains("3 more lines truncated"));
    }

    #[test]
    fn changes_digest_last_commit_emits_patches() {
        // End-to-end git→patch path against the real repo. `last_commit` (HEAD)
        // is churn-independent, so this does not race concurrent tests mutating
        // the working tree.
        let manifest_dir = PathBuf::from(env!("CARGO_MANIFEST_DIR"));
        let repo_root = manifest_dir
            .ancestors()
            .find(|p| p.join("Cargo.toml").is_file() && p.join("crates").is_dir())
            .expect("workspace root")
            .to_path_buf();
        let v = changes_digest(&repo_root, "last_commit").expect("changes_digest");
        let patches = v["patches"].as_array().expect("patches array");
        assert!(
            !patches.is_empty(),
            "expected non-empty patches for last_commit"
        );
        let first = &patches[0];
        assert!(first["file"].is_string());
        assert!(first["patch"]
            .as_str()
            .unwrap_or_default()
            .contains("diff --git"));
        assert!(first["truncated"].is_boolean());
        assert!(v["patch_truncated"].is_boolean());
    }

    #[test]
    fn changes_digest_last_commit_merge_head_uses_first_parent_patch() {
        let tmp = tempfile::tempdir().expect("tmp");
        init_git_repo(tmp.path());
        git_ok(tmp.path(), &["checkout", "-b", "main"]);
        write_file(tmp.path().join("README.md"), "base\n");
        git_ok(tmp.path(), &["add", "README.md"]);
        git_ok(tmp.path(), &["commit", "-m", "base"]);

        git_ok(tmp.path(), &["checkout", "-b", "feature"]);
        write_file(tmp.path().join("feature.txt"), "feature\n");
        git_ok(tmp.path(), &["add", "feature.txt"]);
        git_ok(tmp.path(), &["commit", "-m", "feature"]);

        git_ok(tmp.path(), &["checkout", "main"]);
        write_file(tmp.path().join("main.txt"), "main\n");
        git_ok(tmp.path(), &["add", "main.txt"]);
        git_ok(tmp.path(), &["commit", "-m", "main"]);
        git_ok(
            tmp.path(),
            &["merge", "--no-ff", "feature", "-m", "merge feature"],
        );

        let v = changes_digest(tmp.path(), "last_commit").expect("digest");
        let patches = v["patches"].as_array().expect("patches array");

        assert_eq!(v["scope"], "last_commit");
        assert_eq!(v["files_changed"], 1);
        assert_eq!(v["insertions"], 1);
        assert!(patches.iter().any(|patch| {
            patch["file"].as_str() == Some("feature.txt")
                && patch["patch"]
                    .as_str()
                    .unwrap_or_default()
                    .contains("diff --git a/feature.txt b/feature.txt")
        }));
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
    fn changes_digest_accepts_working_alias() {
        let manifest_dir = PathBuf::from(env!("CARGO_MANIFEST_DIR"));
        let repo_root = manifest_dir
            .ancestors()
            .find(|p| p.join("Cargo.toml").is_file() && p.join("crates").is_dir())
            .expect("workspace root")
            .to_path_buf();

        let v = changes_digest(&repo_root, "working").expect("digest");

        assert_eq!(v["scope"], "working_tree");
        assert!(v["files_changed"].as_u64().is_some());
    }

    #[test]
    fn changes_digest_branch_vs_main_without_merge_base_warns_instead_of_error() {
        let tmp = tempfile::tempdir().expect("tmp");
        init_git_repo(tmp.path());
        write_file(tmp.path().join("README.md"), "base\n");
        git_ok(tmp.path(), &["add", "README.md"]);
        git_ok(tmp.path(), &["commit", "-m", "base"]);
        git_ok(tmp.path(), &["checkout", "--orphan", "source"]);
        write_file(tmp.path().join("README.md"), "source\n");
        git_ok(tmp.path(), &["add", "README.md"]);
        git_ok(tmp.path(), &["commit", "-m", "source"]);

        let v = changes_digest(tmp.path(), "branch_vs_main").expect("digest");

        assert_eq!(v["scope"], "branch_vs_main");
        assert_eq!(v["merge_base_found"], false);
        assert!(v["branch_range"].is_null());
        assert_eq!(v["files_changed"], 0);
        assert_eq!(v["insertions"], 0);
        assert_eq!(v["deletions"], 0);
        assert_eq!(v["patches"].as_array().expect("patches").len(), 0);
        assert!(v["warnings"].as_array().expect("warnings").iter().any(|w| {
            w.as_str()
                .unwrap_or_default()
                .contains("could not resolve merge-base")
        }));
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
