//! Bounded, read-only code-review context assembled from existing AB signals.
//!
//! This module deliberately does not index source, mutate Git state, or persist
//! inferred test edges. It combines the bounded `changes_digest` patch with the
//! existing symbol extractor and codebase impact graph.

use ab_core::{Error, Result};
use ab_store::{codebase, ImpactNode, StateStore};
use serde::Serialize;
use serde_json::{json, Value};
use std::collections::{BTreeMap, BTreeSet, HashMap};
use std::path::{Component, Path, PathBuf};
use std::process::Command;
use std::sync::Arc;
use std::time::UNIX_EPOCH;

use crate::project::changes_digest;

const MAX_SOURCE_BYTES: u64 = 2 * 1024 * 1024;
const MAX_CHANGED_RANGES_PER_FILE: usize = 32;
const MAX_OUTPUT_FIELD_BYTES: usize = 512;

#[derive(Debug, Clone, Copy)]
pub struct ReviewContextLimits {
    pub max_files: usize,
    pub max_symbols: usize,
    pub max_impact_nodes: usize,
    pub max_depth: u32,
    pub per_hop_limit: u32,
}

impl Default for ReviewContextLimits {
    fn default() -> Self {
        Self {
            max_files: 12,
            max_symbols: 20,
            max_impact_nodes: 60,
            max_depth: 2,
            per_hop_limit: 20,
        }
    }
}

impl ReviewContextLimits {
    pub fn bounded(self) -> Self {
        Self {
            max_files: self.max_files.clamp(1, 50),
            max_symbols: self.max_symbols.clamp(1, 50),
            max_impact_nodes: self.max_impact_nodes.clamp(1, 200),
            max_depth: self.max_depth.clamp(1, 3),
            per_hop_limit: self.per_hop_limit.clamp(1, 50),
        }
    }
}

#[derive(Debug, Clone, Serialize)]
struct LineRange {
    start: u32,
    end: u32,
}

#[derive(Debug, Clone, Serialize)]
pub struct ChangedSymbolPreview {
    pub file: String,
    pub line: u32,
    pub kind: String,
    pub name: String,
    pub signature: String,
    pub language: String,
}

#[derive(Debug, Clone, Serialize)]
struct ChangedFilePreview {
    file: String,
    status: Option<String>,
    insertions: u64,
    deletions: u64,
    language: Option<String>,
    changed_ranges: Vec<LineRange>,
    changed_ranges_omitted: usize,
    symbol_names: Vec<String>,
    symbols_omitted: usize,
    patch_truncated: bool,
    skipped_reason: Option<String>,
}

#[derive(Debug)]
pub struct ReviewSeed {
    cwd: String,
    scope: String,
    files_changed: usize,
    insertions: u64,
    deletions: u64,
    branch_range: Option<String>,
    files: Vec<ChangedFilePreview>,
    symbols: Vec<ChangedSymbolPreview>,
    files_omitted: usize,
    symbols_omitted: usize,
    patch_truncated: bool,
    latest_changed_source_mtime: Option<i64>,
    warnings: Vec<String>,
}

#[derive(Debug, Clone, Serialize)]
struct ImpactPreview {
    target: String,
    qualified_name: String,
    file: String,
    hop_distance: u32,
    via_callee: String,
    likely_test: bool,
}

/// Blocking filesystem/Git phase. Call from `spawn_blocking` in async paths.
pub fn collect_review_seed(
    cwd: &Path,
    scope: &str,
    limits: ReviewContextLimits,
) -> Result<ReviewSeed> {
    let limits = limits.bounded();
    if scope != "working_tree" {
        return Err(Error::Backend(
            "code review context currently supports only scope=working_tree".into(),
        ));
    }
    let cwd = git_root(cwd)?;
    let digest = changes_digest(&cwd, scope)?;

    let files_changed = digest
        .get("files_changed")
        .and_then(Value::as_u64)
        .unwrap_or(0) as usize;
    let insertions = digest
        .get("insertions")
        .and_then(Value::as_u64)
        .unwrap_or(0);
    let deletions = digest.get("deletions").and_then(Value::as_u64).unwrap_or(0);
    let branch_range = digest
        .get("branch_range")
        .and_then(Value::as_str)
        .map(str::to_string);
    let mut warnings = digest
        .get("warnings")
        .and_then(Value::as_array)
        .into_iter()
        .flatten()
        .filter_map(Value::as_str)
        .map(str::to_string)
        .collect::<Vec<_>>();
    let untracked = git_untracked_count(&cwd)?;
    if untracked > 0 {
        warnings.push(format!(
            "{untracked} untracked file(s) are not represented by Git diff and were omitted"
        ));
    }
    let patch_truncated = digest
        .get("patch_truncated")
        .and_then(Value::as_bool)
        .unwrap_or(false);

    let status_by_path = digest
        .get("name_status")
        .and_then(Value::as_array)
        .into_iter()
        .flatten()
        .filter_map(|row| {
            Some((
                row.get("path")?.as_str()?.to_string(),
                row.get("status")?.as_str()?.to_string(),
            ))
        })
        .collect::<HashMap<_, _>>();
    let patch_by_path = digest
        .get("patches")
        .and_then(Value::as_array)
        .into_iter()
        .flatten()
        .filter_map(|row| {
            Some((
                row.get("file")?.as_str()?.to_string(),
                (
                    row.get("patch")?.as_str()?.to_string(),
                    row.get("truncated")
                        .and_then(Value::as_bool)
                        .unwrap_or(false),
                ),
            ))
        })
        .collect::<HashMap<_, _>>();

    let summaries = digest
        .get("summary")
        .and_then(Value::as_array)
        .cloned()
        .unwrap_or_default();
    let files_omitted = summaries.len().saturating_sub(limits.max_files);
    let mut bounded_patch_truncated = patch_truncated;
    let mut symbol_budget = limits.max_symbols;
    let mut symbols_omitted = 0usize;
    let mut files = Vec::new();
    let mut all_symbols = Vec::new();
    let mut latest_changed_source_mtime: Option<i64> = None;

    for row in summaries.into_iter().take(limits.max_files) {
        let Some(file) = row.get("file").and_then(Value::as_str) else {
            continue;
        };
        let insertions = row.get("insertions").and_then(Value::as_u64).unwrap_or(0);
        let deletions = row.get("deletions").and_then(Value::as_u64).unwrap_or(0);
        let (patch, file_patch_truncated) = patch_by_path
            .get(file)
            .map(|(patch, truncated)| (patch.as_str(), *truncated))
            .unwrap_or(("", false));
        let mut changed_ranges = parse_new_line_ranges(patch);
        let changed_ranges_omitted = changed_ranges
            .len()
            .saturating_sub(MAX_CHANGED_RANGES_PER_FILE);
        changed_ranges.truncate(MAX_CHANGED_RANGES_PER_FILE);
        bounded_patch_truncated |= changed_ranges_omitted > 0;

        let mut preview = ChangedFilePreview {
            file: file.to_string(),
            status: status_by_path.get(file).cloned(),
            insertions,
            deletions,
            language: None,
            changed_ranges,
            changed_ranges_omitted,
            symbol_names: Vec::new(),
            symbols_omitted: 0,
            patch_truncated: file_patch_truncated,
            skipped_reason: None,
        };

        let relative = match safe_relative_path(file) {
            Some(path) => path,
            None => {
                preview.skipped_reason = Some("unsafe_path".into());
                warnings.push(format!("ignored unsafe Git path: {file}"));
                files.push(preview);
                continue;
            }
        };
        let candidate = cwd.join(relative);
        if !candidate.exists() {
            preview.skipped_reason = Some("missing_or_deleted".into());
            files.push(preview);
            continue;
        }
        let Some(source_path) = confined_existing_file(&cwd, &candidate) else {
            preview.skipped_reason = Some("outside_repository".into());
            warnings.push(format!(
                "ignored Git path resolving outside repository: {file}"
            ));
            files.push(preview);
            continue;
        };
        let Some(language) = codebase::detect_language(&source_path) else {
            preview.skipped_reason = Some("unsupported_language".into());
            files.push(preview);
            continue;
        };
        preview.language = Some(language.to_string());
        if preview.changed_ranges.is_empty() {
            preview.skipped_reason = Some("no_bounded_hunk".into());
            files.push(preview);
            continue;
        }
        let metadata = std::fs::metadata(&source_path).map_err(Error::Io)?;
        if let Ok(modified) = metadata.modified() {
            if let Ok(duration) = modified.duration_since(UNIX_EPOCH) {
                latest_changed_source_mtime = Some(
                    latest_changed_source_mtime
                        .unwrap_or_default()
                        .max(duration.as_secs().min(i64::MAX as u64) as i64),
                );
            }
        }
        if metadata.len() > MAX_SOURCE_BYTES {
            preview.skipped_reason = Some("source_too_large".into());
            warnings.push(format!(
                "source exceeds {} bytes and was not parsed: {file}",
                MAX_SOURCE_BYTES
            ));
            files.push(preview);
            continue;
        }
        let content = std::fs::read_to_string(&source_path).map_err(Error::Io)?;
        let extracted = codebase::extract_symbols(&content, file, language);
        let selected =
            symbols_overlapping_ranges(extracted, &preview.changed_ranges, content.lines().count());
        let take = selected.len().min(symbol_budget);
        preview.symbol_names = selected[..take]
            .iter()
            .map(|symbol| symbol.name.clone())
            .collect();
        preview.symbols_omitted = selected.len().saturating_sub(take);
        symbols_omitted += preview.symbols_omitted;
        symbol_budget -= take;
        all_symbols.extend(selected[..take].iter().cloned());
        files.push(preview);
    }

    if files_omitted > 0 {
        warnings.push(format!(
            "{files_omitted} changed file(s) omitted by max_files={} limit",
            limits.max_files
        ));
    }
    if symbols_omitted > 0 {
        warnings.push(format!(
            "{symbols_omitted} changed symbol(s) omitted by max_symbols={} limit",
            limits.max_symbols
        ));
    }

    Ok(ReviewSeed {
        cwd: cwd.display().to_string(),
        scope: scope.to_string(),
        files_changed,
        insertions,
        deletions,
        branch_range,
        files,
        symbols: all_symbols,
        files_omitted,
        symbols_omitted,
        patch_truncated: bounded_patch_truncated,
        latest_changed_source_mtime,
        warnings,
    })
}

pub async fn enrich_review_seed(
    store: Arc<dyn StateStore>,
    seed: ReviewSeed,
    limits: ReviewContextLimits,
) -> Value {
    let limits = limits.bounded();
    let mut warnings = seed.warnings.clone();
    let mut impact = Vec::new();
    let mut likely_tests = Vec::new();
    let mut impact_nodes_omitted = 0usize;
    let mut impact_targets_omitted = 0usize;
    let mut seen = BTreeSet::new();
    let mut test_symbol_cache = BTreeMap::new();

    let index_status = match store.codebase_index_status(&seed.cwd).await {
        Ok(status) if status.symbols > 0 || status.imports > 0 || status.calls > 0 => {
            let possibly_stale = seed
                .latest_changed_source_mtime
                .zip(status.newest_indexed_at)
                .is_some_and(|(changed, indexed)| changed > indexed);
            if possibly_stale {
                warnings.push(
                    "codebase index may predate the newest changed source; impact evidence may be stale"
                        .into(),
                );
            }
            json!({
                "status": if possibly_stale { "possibly_stale" } else { "present" },
                "root_path": status.root_path,
                "symbols": status.symbols,
                "imports": status.imports,
                "calls": status.calls,
                "indexed_files": status.indexed_files,
                "oldest_indexed_at": status.oldest_indexed_at,
                "newest_indexed_at": status.newest_indexed_at,
                "latest_changed_source_mtime": seed.latest_changed_source_mtime,
            })
        }
        Ok(status) => {
            warnings.push(format!(
                "no codebase index exists for exact root '{}'; impact evidence is unavailable",
                seed.cwd
            ));
            json!({
                "status": "missing",
                "root_path": status.root_path,
                "symbols": 0,
                "imports": status.imports,
                "calls": status.calls,
                "indexed_files": status.indexed_files,
                "oldest_indexed_at": status.oldest_indexed_at,
                "newest_indexed_at": status.newest_indexed_at,
            })
        }
        Err(error) => {
            warnings.push(format!("codebase index status unavailable: {error}"));
            json!({
                "status": "unknown",
                "root_path": seed.cwd,
            })
        }
    };

    for (index, symbol) in seed.symbols.iter().enumerate() {
        if impact.len() >= limits.max_impact_nodes {
            impact_targets_omitted = seed.symbols.len().saturating_sub(index);
            break;
        }
        let remaining = limits.max_impact_nodes.saturating_sub(impact.len());
        match bounded_impact(
            store.as_ref(),
            &symbol.name,
            &seed.cwd,
            limits.max_depth,
            limits.per_hop_limit,
            remaining,
        )
        .await
        {
            Ok((nodes, truncated)) => {
                impact_nodes_omitted += usize::from(truncated);
                for node in nodes {
                    let key = format!(
                        "{}\0{}\0{}\0{}",
                        symbol.name, node.qualified_name, node.file_path, node.hop_distance
                    );
                    if !seen.insert(key) {
                        continue;
                    }
                    let likely_test = likely_test_node(&seed.cwd, &node, &mut test_symbol_cache);
                    let row = ImpactPreview {
                        target: clamp_text(&symbol.name, MAX_OUTPUT_FIELD_BYTES),
                        qualified_name: clamp_text(&node.qualified_name, MAX_OUTPUT_FIELD_BYTES),
                        file: clamp_text(
                            &display_relative(&seed.cwd, &node.file_path),
                            MAX_OUTPUT_FIELD_BYTES,
                        ),
                        hop_distance: node.hop_distance,
                        via_callee: clamp_text(&node.via_callee, MAX_OUTPUT_FIELD_BYTES),
                        likely_test,
                    };
                    if likely_test {
                        likely_tests.push(row.clone());
                    }
                    impact.push(row);
                }
            }
            Err(error) => warnings.push(format!(
                "impact lookup failed for '{}': {error}",
                symbol.name
            )),
        }
    }

    let partial = seed.patch_truncated
        || seed.files_omitted > 0
        || seed.symbols_omitted > 0
        || impact_nodes_omitted > 0
        || impact_targets_omitted > 0
        || !warnings.is_empty();
    let status = if seed.files_changed == 0 {
        "empty"
    } else if partial {
        "partial"
    } else {
        "ready"
    };

    json!({
        "kind": "agent_bridge.code_review_context_preview.v0",
        "status": status,
        "scope": seed.scope,
        "cwd": seed.cwd,
        "branch_range": seed.branch_range,
        "index": index_status,
        "change_summary": {
            "files_changed": seed.files_changed,
            "insertions": seed.insertions,
            "deletions": seed.deletions,
        },
        "changed_files": seed.files,
        "changed_symbols": seed.symbols,
        "impact": impact,
        "likely_test_callers": likely_tests,
        "omitted": {
            "files": seed.files_omitted,
            "symbols": seed.symbols_omitted,
            "impact_nodes": impact_nodes_omitted,
            "impact_targets": impact_targets_omitted,
        },
        "limits": {
            "max_files": limits.max_files,
            "max_symbols": limits.max_symbols,
            "max_impact_nodes": limits.max_impact_nodes,
            "max_depth": limits.max_depth,
            "per_hop_limit": limits.per_hop_limit,
            "max_source_bytes": MAX_SOURCE_BYTES,
            "max_changed_ranges_per_file": MAX_CHANGED_RANGES_PER_FILE,
        },
        "warnings": warnings,
        "evidence_boundary": {
            "git": "read_only_bounded_diff",
            "graph": "existing_codebase_index_only_no_auto_index",
            "target_resolution": "lexical_symbol_name_may_overmatch_common_names",
            "impact_omission_count": "lower_bound_when_traversal_stops_at_global_limit",
            "tests": "heuristic_callers_not_persisted_tested_by_edges",
            "mutations": [],
            "empty_impact_note": "No impact row can mean no indexed caller or a missing/stale index; it is not proof of no blast radius."
        }
    })
}

async fn bounded_impact(
    store: &dyn StateStore,
    target: &str,
    root: &str,
    max_depth: u32,
    per_hop_limit: u32,
    max_nodes: usize,
) -> Result<(Vec<ImpactNode>, bool)> {
    if max_nodes == 0 {
        return Ok((Vec::new(), true));
    }

    let mut nodes = Vec::new();
    let mut visited = BTreeSet::new();
    let mut frontier = vec![(target.to_string(), 1u32)];
    let mut truncated = false;
    let mut query_may_be_truncated = false;

    while !frontier.is_empty() {
        let mut next = Vec::new();
        for (callee, hop) in std::mem::take(&mut frontier) {
            if hop > max_depth {
                continue;
            }
            let hits = store
                .codebase_callers(&callee, None, Some(root), per_hop_limit)
                .await?;
            query_may_be_truncated |= hits.len() >= per_hop_limit as usize;
            for hit in hits {
                if hit.caller.is_empty() || !visited.insert(hit.caller.clone()) {
                    continue;
                }
                if nodes.len() >= max_nodes {
                    truncated = true;
                    break;
                }
                nodes.push(ImpactNode {
                    qualified_name: hit.caller.clone(),
                    file_path: hit.file_path,
                    hop_distance: hop,
                    via_callee: callee.clone(),
                });
                if hop < max_depth {
                    next.push((hit.caller, hop + 1));
                }
            }
            if truncated {
                break;
            }
        }
        if truncated {
            break;
        }
        frontier = next;
    }
    nodes.sort_by(|a, b| {
        a.hop_distance
            .cmp(&b.hop_distance)
            .then_with(|| a.qualified_name.cmp(&b.qualified_name))
            .then_with(|| a.file_path.cmp(&b.file_path))
    });
    Ok((nodes, truncated || query_may_be_truncated))
}

fn parse_new_line_ranges(patch: &str) -> Vec<LineRange> {
    let mut ranges = Vec::new();
    for line in patch.lines().filter(|line| line.starts_with("@@ ")) {
        let Some(token) = line.split_whitespace().find(|part| part.starts_with('+')) else {
            continue;
        };
        let mut parts = token.trim_start_matches('+').splitn(2, ',');
        let Some(start) = parts.next().and_then(|raw| raw.parse::<u32>().ok()) else {
            continue;
        };
        let count = parts
            .next()
            .and_then(|raw| raw.parse::<u32>().ok())
            .unwrap_or(1);
        let effective_count = count.max(1);
        ranges.push(LineRange {
            start,
            end: start.saturating_add(effective_count - 1),
        });
    }
    ranges
}

fn git_root(cwd: &Path) -> Result<PathBuf> {
    let output = Command::new("git")
        .current_dir(cwd)
        .args(["rev-parse", "--show-toplevel"])
        .output()
        .map_err(Error::Io)?;
    if !output.status.success() {
        return Err(Error::Backend("cwd is not inside a Git repository".into()));
    }
    let root = String::from_utf8(output.stdout)
        .map_err(|_| Error::Backend("Git repository root is not valid UTF-8".into()))?;
    Path::new(root.trim()).canonicalize().map_err(Error::Io)
}

fn git_untracked_count(root: &Path) -> Result<usize> {
    let output = Command::new("git")
        .current_dir(root)
        .args(["ls-files", "--others", "--exclude-standard", "-z"])
        .output()
        .map_err(Error::Io)?;
    if !output.status.success() {
        return Err(Error::Backend(
            "failed to inspect untracked Git files".into(),
        ));
    }
    Ok(output
        .stdout
        .split(|byte| *byte == 0)
        .filter(|p| !p.is_empty())
        .count())
}

fn symbols_overlapping_ranges(
    mut symbols: Vec<ab_store::CodebaseSymbol>,
    ranges: &[LineRange],
    line_count: usize,
) -> Vec<ChangedSymbolPreview> {
    symbols.sort_by_key(|symbol| symbol.line);
    symbols
        .iter()
        .enumerate()
        .filter_map(|(index, symbol)| {
            let next_line = symbols
                .get(index + 1)
                .map(|next| next.line.saturating_sub(1))
                .unwrap_or(line_count.max(1) as u32);
            let overlaps = ranges
                .iter()
                .any(|range| symbol.line <= range.end && next_line >= range.start);
            overlaps.then(|| ChangedSymbolPreview {
                file: clamp_text(&symbol.file_path, MAX_OUTPUT_FIELD_BYTES),
                line: symbol.line,
                kind: clamp_text(&symbol.kind, MAX_OUTPUT_FIELD_BYTES),
                name: clamp_text(&symbol.name, MAX_OUTPUT_FIELD_BYTES),
                signature: clamp_text(&symbol.signature, MAX_OUTPUT_FIELD_BYTES),
                language: clamp_text(&symbol.language, MAX_OUTPUT_FIELD_BYTES),
            })
        })
        .collect()
}

fn clamp_text(value: &str, max_bytes: usize) -> String {
    if value.len() <= max_bytes {
        return value.to_string();
    }
    let mut end = max_bytes;
    while !value.is_char_boundary(end) {
        end -= 1;
    }
    value[..end].to_string()
}

fn safe_relative_path(raw: &str) -> Option<PathBuf> {
    let path = Path::new(raw);
    if path.is_absolute()
        || path.components().any(|component| {
            matches!(
                component,
                Component::ParentDir | Component::RootDir | Component::Prefix(_)
            )
        })
    {
        return None;
    }
    Some(path.to_path_buf())
}

fn confined_existing_file(root: &Path, candidate: &Path) -> Option<PathBuf> {
    let root = root.canonicalize().ok()?;
    let canonical = candidate.canonicalize().ok()?;
    (canonical.starts_with(&root) && canonical.is_file()).then_some(canonical)
}

fn display_relative(root: &str, path: &str) -> String {
    Path::new(path)
        .strip_prefix(root)
        .ok()
        .map(|relative| relative.display().to_string())
        .unwrap_or_else(|| path.to_string())
}

fn likely_test_node(
    root: &str,
    node: &ImpactNode,
    test_symbol_cache: &mut BTreeMap<String, Option<BTreeSet<String>>>,
) -> bool {
    let path_lower = node.file_path.to_ascii_lowercase();
    let name_lower = node.qualified_name.to_ascii_lowercase();
    if path_lower.contains("/tests/")
        || path_lower.contains("/test/")
        || path_lower.ends_with("_test.rs")
        || path_lower.ends_with("_test.py")
        || path_lower.contains(".test.")
        || path_lower.contains(".spec.")
        || name_lower.starts_with("test_")
        || name_lower.contains("::tests::")
    {
        return true;
    }

    let root = Path::new(root);
    let Some(path) = confined_existing_file(root, Path::new(&node.file_path)) else {
        return false;
    };
    let cache_key = path.display().to_string();
    let test_symbols = test_symbol_cache.entry(cache_key).or_insert_with(|| {
        let metadata = std::fs::metadata(&path).ok()?;
        if metadata.len() > MAX_SOURCE_BYTES {
            return None;
        }
        let language = codebase::detect_language(&path)?;
        let content = std::fs::read_to_string(&path).ok()?;
        Some(
            codebase::extract_symbols(&content, &path.display().to_string(), language)
                .into_iter()
                .filter(|symbol| {
                    symbol.kind == "test_fn"
                        || symbol.name.starts_with("test_")
                        || symbol.name.ends_with("_test")
                })
                .map(|symbol| symbol.name)
                .collect(),
        )
    });
    let Some(test_symbols) = test_symbols.as_ref() else {
        return false;
    };
    let leaf = node
        .qualified_name
        .rsplit([':', '.'])
        .find(|part| !part.is_empty())
        .unwrap_or(node.qualified_name.as_str());
    test_symbols.contains(leaf)
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::process::Command;

    #[test]
    fn parses_added_and_deletion_only_hunks() {
        let patch = "@@ -2,0 +3,4 @@\n+new\n@@ -10,2 +14,0 @@\n-old\n";
        let ranges = parse_new_line_ranges(patch);
        assert_eq!(ranges.len(), 2);
        assert_eq!((ranges[0].start, ranges[0].end), (3, 6));
        assert_eq!((ranges[1].start, ranges[1].end), (14, 14));
    }

    #[test]
    fn maps_hunks_to_enclosing_symbols() {
        let content = "fn first() {\n    one();\n}\n\nfn second() {\n    two();\n}\n";
        let symbols = codebase::extract_symbols(content, "src/lib.rs", "rust");
        let selected = symbols_overlapping_ranges(
            symbols,
            &[LineRange { start: 6, end: 6 }],
            content.lines().count(),
        );
        assert_eq!(selected.len(), 1);
        assert_eq!(selected[0].name, "second");
    }

    #[test]
    fn rejects_absolute_and_parent_paths() {
        assert!(safe_relative_path("src/lib.rs").is_some());
        assert!(safe_relative_path("../outside.rs").is_none());
        assert!(safe_relative_path("/tmp/outside.rs").is_none());
    }

    #[test]
    fn limits_are_fail_closed() {
        let bounded = ReviewContextLimits {
            max_files: 0,
            max_symbols: usize::MAX,
            max_impact_nodes: usize::MAX,
            max_depth: 99,
            per_hop_limit: 0,
        }
        .bounded();
        assert_eq!(bounded.max_files, 1);
        assert_eq!(bounded.max_symbols, 50);
        assert_eq!(bounded.max_impact_nodes, 200);
        assert_eq!(bounded.max_depth, 3);
        assert_eq!(bounded.per_hop_limit, 1);
    }

    #[cfg(unix)]
    #[test]
    fn rejects_symlinked_source_outside_repository() {
        use std::os::unix::fs::symlink;

        let repo = tempfile::tempdir().expect("repo tempdir");
        let outside = tempfile::NamedTempFile::new().expect("outside file");
        let link = repo.path().join("linked.rs");
        symlink(outside.path(), &link).expect("create symlink");
        assert!(confined_existing_file(repo.path(), &link).is_none());
    }

    #[test]
    fn recognizes_rust_test_callers_from_existing_symbol_classifier() {
        let dir = tempfile::tempdir().expect("tempdir");
        let source = dir.path().join("src/lib.rs");
        std::fs::create_dir_all(source.parent().unwrap()).expect("mkdir");
        std::fs::write(
            &source,
            "#[tokio::test(flavor = \"current_thread\")]\nasync fn covers_preview() {}\n",
        )
        .expect("write source");
        let node = ImpactNode {
            qualified_name: "covers_preview".into(),
            file_path: source.display().to_string(),
            hop_distance: 1,
            via_callee: "preview".into(),
        };
        assert!(likely_test_node(
            dir.path().to_str().unwrap(),
            &node,
            &mut BTreeMap::new(),
        ));
    }

    #[test]
    fn collects_changed_symbol_from_working_tree_hunk() {
        let dir = tempfile::tempdir().expect("tempdir");
        let run_git = |args: &[&str]| {
            let status = Command::new("git")
                .current_dir(dir.path())
                .args(args)
                .status()
                .expect("run git");
            assert!(status.success(), "git {args:?}");
        };
        run_git(&["init", "--quiet"]);
        run_git(&["config", "user.name", "AB Test"]);
        run_git(&["config", "user.email", "ab-test@example.invalid"]);
        let source = dir.path().join("lib.rs");
        std::fs::write(&source, "fn first() {\n    one();\n}\n").expect("write initial");
        run_git(&["add", "lib.rs"]);
        run_git(&["commit", "--quiet", "-m", "initial"]);
        std::fs::write(&source, "fn first() {\n    two();\n}\n").expect("write change");

        let seed = collect_review_seed(dir.path(), "working_tree", ReviewContextLimits::default())
            .expect("collect seed");
        assert_eq!(seed.files_changed, 1);
        assert_eq!(seed.files.len(), 1);
        assert_eq!(seed.symbols.len(), 1);
        assert_eq!(seed.symbols[0].name, "first");
        assert!(!seed.patch_truncated);

        let nested = dir.path().join("nested");
        std::fs::create_dir(&nested).expect("create nested cwd");
        std::fs::write(nested.join("untracked.rs"), "fn omitted() {}\n")
            .expect("write untracked source");
        let nested_seed =
            collect_review_seed(&nested, "working_tree", ReviewContextLimits::default())
                .expect("collect seed from nested cwd");
        assert_eq!(
            nested_seed.cwd,
            dir.path().canonicalize().unwrap().display().to_string()
        );
        assert_eq!(nested_seed.symbols[0].name, "first");
        assert!(nested_seed
            .warnings
            .iter()
            .any(|warning| warning.contains("untracked file")));
    }

    #[test]
    fn rejects_non_working_tree_scope() {
        let dir = tempfile::tempdir().expect("tempdir");
        let error = collect_review_seed(dir.path(), "staged", ReviewContextLimits::default())
            .expect_err("staged scope must fail closed");
        assert!(error.to_string().contains("only scope=working_tree"));
    }

    #[tokio::test]
    async fn end_to_end_preview_is_bounded_and_marks_test_callers() {
        let repo = tempfile::tempdir().expect("repo tempdir");
        let db = tempfile::tempdir().expect("db tempdir");
        let run_git = |args: &[&str]| {
            let status = Command::new("git")
                .current_dir(repo.path())
                .args(args)
                .status()
                .expect("run git");
            assert!(status.success(), "git {args:?}");
        };
        run_git(&["init", "--quiet"]);
        run_git(&["config", "user.name", "AB Test"]);
        run_git(&["config", "user.email", "ab-test@example.invalid"]);
        let source = repo.path().join("lib.rs");
        std::fs::write(
            &source,
            "fn changed() {\n    one();\n}\nfn caller() {\n    changed();\n}\n#[test]\nfn covers_changed() {\n    changed();\n}\n",
        )
        .expect("write initial");
        run_git(&["add", "lib.rs"]);
        run_git(&["commit", "--quiet", "-m", "initial"]);
        std::fs::write(
            &source,
            "fn changed() {\n    two();\n}\nfn caller() {\n    changed();\n}\n#[test]\nfn covers_changed() {\n    changed();\n}\n",
        )
        .expect("write change");

        let root = repo.path().canonicalize().expect("canonical repo");
        let store = Arc::new(
            ab_store::SqliteStore::open(&db.path().join("state.db"))
                .await
                .expect("open store"),
        );
        store
            .codebase_index(root.to_str().unwrap(), &["rust".to_string()])
            .await
            .expect("index repo");
        let limits = ReviewContextLimits::default();
        let seed = collect_review_seed(&root, "working_tree", limits).expect("collect seed");
        let preview = enrich_review_seed(store.clone(), seed, limits).await;

        assert_eq!(preview["status"], "ready");
        assert_eq!(preview["index"]["status"], "present");
        assert_eq!(preview["changed_symbols"][0]["name"], "changed");
        assert!(preview["impact"].as_array().unwrap().len() >= 2);
        assert_eq!(
            preview["likely_test_callers"][0]["qualified_name"],
            "covers_changed"
        );
        let encoded = serde_json::to_vec(&preview).expect("encode preview");
        assert!(
            encoded.len() < 20_000,
            "preview was {} bytes",
            encoded.len()
        );

        let capped_limits = ReviewContextLimits {
            max_impact_nodes: 1,
            ..limits
        };
        let capped_seed =
            collect_review_seed(&root, "working_tree", capped_limits).expect("collect capped seed");
        let capped = enrich_review_seed(store, capped_seed, capped_limits).await;
        assert_eq!(capped["status"], "partial");
        assert_eq!(capped["impact"].as_array().unwrap().len(), 1);
        assert!(capped["omitted"]["impact_nodes"].as_u64().unwrap() >= 1);
    }
}
