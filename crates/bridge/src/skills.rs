//! `agent-bridge skills` — index third-party Claude Code skill libraries.
//!
//! ### Subcommands
//!
//! - `skills index <source>` — clone (if URL) or read (if local path) a
//!   repo, walk for skill files, parse frontmatter, lint, and save each
//!   skill as a memory record (`kind = "skill"`).
//! - `skills seed` — index the curated seed corpus (see [`SEED_REPOS`]).
//! - `skills refresh` — re-index every previously-indexed GitHub source to
//!   pick up upstream changes (cron / Stop-hook friendly).
//! - `skills discover` — query GitHub topic search for candidate skill repos
//!   (does not index — surfaces a ranked list for the user to approve).
//! - `skills search <query>` — semantic search over indexed skills.
//! - `skills list` — list indexed skills (most-recent first).
//! - `skills show <key>` — print one skill's body and metadata.
//!
//! ### Discovery patterns
//!
//! Walks the cloned repo and matches, in priority order:
//!   1. `**/SKILL.md` (Anthropic canonical: parent dir name = skill name)
//!   2. `.claude/skills/**/*.md` (project-local Claude Code form)
//!   3. `skills/*.md` (some community repos)
//!
//! ### Lint
//!
//! Heuristic safety scan over each skill body. Flags `curl|bash`,
//! `wget|sh`, hardcoded credential paths, `rm -rf /` patterns, etc.
//! Severity counts land in `tags` (`lint:clean` / `lint:warn:N` /
//! `lint:danger:N`); the indexer **does not refuse to save** — surfacing
//! the warning to the user is the point. Manual review still recommended.

use ab_store::{MemoryListSort, MemoryRecord, SqliteStore, StateStore};
use anyhow::{anyhow, bail, Context, Result};
use std::collections::{BTreeMap, BTreeSet};
use std::path::{Path, PathBuf};
use std::process::{Command, Stdio};
use std::time::SystemTime;

/// Curated seed corpus (Phase A). All known to publish Claude Code skills
/// in the canonical `<skill-name>/SKILL.md` layout (or a close variant).
/// Add/remove entries here; `skills seed` indexes the lot.
pub const SEED_REPOS: &[&str] = &[
    "https://github.com/anthropics/skills",
    "https://github.com/anthropics/claude-plugins-official",
    "https://github.com/alirezarezvani/claude-skills",
    "https://github.com/Jeffallan/claude-skills",
    "https://github.com/Imbad0202/academic-research-skills",
    "https://github.com/daymade/claude-code-skills",
    "https://github.com/glebis/claude-skills",
    "https://github.com/ahmedasmar/devops-claude-skills",
];

#[derive(Debug, Clone)]
struct SkillFile {
    /// `<owner>/<repo>` — derived from the source URL or repo path.
    src: String,
    /// Skill name (folder name for SKILL.md, filename otherwise).
    name: String,
    /// Path inside the repo (relative).
    rel_path: PathBuf,
    /// Raw file body.
    body: String,
    /// Source/provenance tags derived from the checkout as a whole.
    source_tags: Vec<String>,
}

#[derive(Debug, Default, Clone)]
struct Frontmatter {
    name: Option<String>,
    description: Option<String>,
    allowed_tools: Vec<String>,
    /// agentskills.io spec optional field — license name or filename.
    license: Option<String>,
    /// agentskills.io spec optional field — environment requirements (≤500 chars).
    compatibility: Option<String>,
    /// Any other key=value pairs we don't model explicitly. Spec-defined
    /// `metadata` (arbitrary key-value mapping) lands here too — we don't
    /// expand it per-key because the spec leaves the inner shape open.
    extras: BTreeMap<String, String>,
}

/// Known vendor / first-party orgs whose skills we treat as `vendor-curated`
/// for ranking purposes. See `decision_skills_quality_tier_20260507`.
/// Anything not in this list classifies as `community`.
///
/// Sources: agentskills.io client list as of 2026-05-07. Add new orgs here
/// when they ship official skill catalogs we trust.
const KNOWN_VENDORS: &[&str] = &[
    "anthropics",
    "warpdotdev",
    "google-gemini",
    "google-ai-edge",
    "openai",
    "microsoft",
    "github",
    "block", // Goose
    "OpenHands",
    "letta-ai",
    "sst", // OpenCode
    "RooCodeInc",
    "mistralai",
    "bytedance",
    "spring-projects",
    "jetbrains",
    "snowflake",
    "databricks",
    "laravel",
    "cursor",
];

fn classify_vendor(src: &str) -> &'static str {
    let owner = src.split('/').next().unwrap_or(src);
    if KNOWN_VENDORS.iter().any(|v| v.eq_ignore_ascii_case(owner)) {
        "vendor-curated"
    } else {
        "community"
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
#[allow(dead_code)] // Info reserved for future heuristics that flag without warning.
enum LintSev {
    Info,
    Warn,
    Danger,
}

#[derive(Debug, Clone)]
struct LintFinding {
    sev: LintSev,
    rule: &'static str,
    snippet: String,
}

/// Indexer entry-point: handle either a URL or a local path.
pub async fn run_index(source: &str, verbose: bool) -> Result<usize> {
    let (owned_clone, repo_dir, src_id) = resolve_source(source)?;
    if verbose {
        eprintln!(
            "[skills] indexing {} (path: {})",
            src_id,
            repo_dir.display()
        );
    }
    let files = walk_skill_files(&repo_dir, &src_id)?;
    if files.is_empty() {
        eprintln!(
            "[skills] {}: no SKILL.md or .claude/skills/*.md files found",
            src_id
        );
        if owned_clone {
            let _ = std::fs::remove_dir_all(&repo_dir);
        }
        return Ok(0);
    }
    let store = open_store().await?;
    let mut saved = 0usize;
    for sf in files {
        match build_record(&sf) {
            Ok(rec) => {
                if verbose {
                    eprintln!(
                        "[skills]   + {} ({} chars, {} tags)",
                        rec.key,
                        rec.content.len(),
                        rec.tags.len()
                    );
                }
                store
                    .memory_save(&rec)
                    .await
                    .with_context(|| format!("memory_save failed for {}", rec.key))?;
                saved += 1;
            }
            Err(e) => eprintln!("[skills]   skipped {}: {}", sf.rel_path.display(), e),
        }
    }
    eprintln!("[skills] {}: indexed {} skills", src_id, saved);
    if owned_clone {
        let _ = std::fs::remove_dir_all(&repo_dir);
    }
    Ok(saved)
}

/// Index every entry in [`SEED_REPOS`]. Continues on per-repo failure.
pub async fn run_seed(verbose: bool) -> Result<()> {
    let mut total = 0usize;
    let mut failed = Vec::new();
    for url in SEED_REPOS {
        match run_index(url, verbose).await {
            Ok(n) => total += n,
            Err(e) => {
                eprintln!("[skills] {}: FAILED: {}", url, e);
                failed.push(*url);
            }
        }
    }
    eprintln!(
        "[skills] seed corpus: {} skills indexed, {} repos failed",
        total,
        failed.len()
    );
    if !failed.is_empty() {
        eprintln!("[skills] failed repos:");
        for u in failed {
            eprintln!("  - {}", u);
        }
    }
    Ok(())
}

/// Re-index every previously-indexed GitHub source.
///
/// Walks all `kind=skill` records, collects distinct `src:` tag values that
/// look like `<owner>/<repo>`, and re-runs [`run_index`] for each as
/// `https://github.com/<owner>/<repo>`. Local-path sources (basenames with
/// no `/`) are reported and skipped — they need a manual `skills index`.
///
/// When `prune` is set, after re-indexing each GitHub source we delete
/// records with that `src:` tag whose `updated_at` is still older than the
/// refresh's start time — those are skills that disappeared upstream. A
/// failed re-index for a source skips pruning of that source (don't
/// destroy data when we don't have a fresh authoritative state).
pub async fn run_refresh(verbose: bool, prune: bool) -> Result<()> {
    let store = open_store().await?;
    let rows = store
        .list_memories(Some("skill"), MemoryListSort::Recent, u32::MAX)
        .await
        .context("list_memories failed")?;
    if rows.is_empty() {
        eprintln!("[skills] none indexed yet — try `agent-bridge skills seed`");
        return Ok(());
    }
    let mut github_srcs: Vec<String> = Vec::new();
    let mut seen: std::collections::BTreeSet<String> = std::collections::BTreeSet::new();
    let mut local_srcs: std::collections::BTreeSet<String> = std::collections::BTreeSet::new();
    for r in &rows {
        let Some(src) = tag_value(&r.tags, "src:") else {
            continue;
        };
        if is_remote_src(&src) {
            if seen.insert(src.clone()) {
                github_srcs.push(src);
            }
        } else {
            local_srcs.insert(src);
        }
    }
    let started_at = SystemTime::now()
        .duration_since(SystemTime::UNIX_EPOCH)
        .map(|d| d.as_secs() as i64)
        .unwrap_or(0);
    eprintln!(
        "[skills] refresh: {} github source(s), {} local source(s) skipped, {} record(s) total{}",
        github_srcs.len(),
        local_srcs.len(),
        rows.len(),
        if prune { " (prune ON)" } else { "" }
    );
    if !local_srcs.is_empty() && verbose {
        eprintln!("[skills]   local sources (re-run `skills index <path>` manually):");
        for s in &local_srcs {
            eprintln!("[skills]     - {}", s);
        }
    }
    let mut total = 0usize;
    let mut failed: Vec<String> = Vec::new();
    let mut pruned_total = 0usize;
    for src in &github_srcs {
        let url = src_to_clone_url(src);
        match run_index(&url, verbose).await {
            Ok(n) => {
                total += n;
                if prune {
                    match prune_stale_for_src(&store, src, started_at, verbose).await {
                        Ok(d) => pruned_total += d,
                        Err(e) => {
                            eprintln!("[skills] {}: prune failed: {}", src, e);
                        }
                    }
                }
            }
            Err(e) => {
                eprintln!("[skills] {}: FAILED: {}", src, e);
                failed.push(src.clone());
            }
        }
    }
    eprintln!(
        "[skills] refresh done: {} skills indexed, {} repo(s) failed{}",
        total,
        failed.len(),
        if prune {
            format!(", {} stale record(s) pruned", pruned_total)
        } else {
            String::new()
        }
    );
    if !failed.is_empty() {
        eprintln!("[skills] failed repos:");
        for s in failed {
            eprintln!("  - {}", s);
        }
    }
    Ok(())
}

/// After a successful re-index of `src`, delete records with that `src:`
/// tag whose `updated_at` is still older than `threshold`. Those are
/// skills that existed before the refresh but were not re-saved during
/// it — i.e. disappeared upstream.
async fn prune_stale_for_src(
    store: &SqliteStore,
    src: &str,
    threshold: i64,
    verbose: bool,
) -> Result<usize> {
    let rows = store
        .list_memories(Some("skill"), MemoryListSort::Recent, u32::MAX)
        .await
        .context("list_memories failed")?;
    let stale: Vec<&MemoryRecord> = rows
        .iter()
        .filter(|r| is_stale_for_src(r, src, threshold))
        .collect();
    if stale.is_empty() {
        return Ok(0);
    }
    let mut deleted = 0usize;
    for r in &stale {
        match store.memory_delete(&r.key).await {
            Ok(true) => {
                deleted += 1;
                if verbose {
                    eprintln!("[skills]   - pruned {}", r.key);
                }
            }
            Ok(false) => {} // race: already gone
            Err(e) => eprintln!("[skills]   ! delete {} failed: {}", r.key, e),
        }
    }
    eprintln!("[skills] {}: pruned {} stale record(s)", src, deleted);
    Ok(deleted)
}

/// Decide whether `r` is a stale entry for `src`: same `src:` tag and
/// `updated_at` predates `threshold` (i.e. wasn't re-saved by the
/// just-completed re-index).
fn is_stale_for_src(r: &MemoryRecord, src: &str, threshold: i64) -> bool {
    let Some(rec_src) = tag_value(&r.tags, "src:") else {
        return false;
    };
    rec_src == src && r.updated_at < threshold
}

/// True for any `src_id` that maps to a remote (re-cloneable) source —
/// either GitHub `<owner>/<repo>` (one slash, both non-empty) or GitLab
/// `gitlab.com/<owner>/<repo>` (host-prefixed, three segments). Local-path
/// indexing produces a basename with no `/`, so this filter excludes those.
fn is_remote_src(src: &str) -> bool {
    if let Some(rest) = src.strip_prefix("gitlab.com/") {
        let mut parts = rest.split('/');
        let owner = parts.next().unwrap_or("");
        let repo = parts.next().unwrap_or("");
        return !owner.is_empty() && !repo.is_empty() && parts.next().is_none();
    }
    let mut parts = src.split('/');
    let owner = parts.next().unwrap_or("");
    let repo = parts.next().unwrap_or("");
    !owner.is_empty() && !repo.is_empty() && parts.next().is_none()
}

/// Topics queried by `skills discover`. Both are commonly used by repos
/// that publish Claude Code skill libraries. Add new ones here when the
/// ecosystem coalesces around different tags.
const DISCOVER_TOPICS: &[&str] = &["claude-skill", "claude-code-skill"];

#[derive(Debug, Clone)]
struct DiscoverHit {
    full_name: String,
    stars: u64,
    pushed_at: String,
    description: String,
}

/// Query GitHub topic search for candidate skill repos and print a ranked
/// list. Does not index anything — the user picks and runs `skills index`.
///
/// Uses unauthenticated REST API via `curl` (already a system tool — same
/// pattern as `git clone` for `index`). Auth doesn't help here: rate limits
/// for unauth search are 10 req/min, and we make 2 requests total.
pub async fn run_discover(limit: usize, include_indexed: bool) -> Result<()> {
    let store = open_store().await?;
    let known: std::collections::BTreeSet<String> = if include_indexed {
        Default::default()
    } else {
        let rows = store
            .list_memories(Some("skill"), MemoryListSort::Recent, u32::MAX)
            .await
            .context("list_memories failed")?;
        rows.iter()
            .filter_map(|r| tag_value(&r.tags, "src:"))
            .filter(|s| is_remote_src(s))
            .collect()
    };

    eprintln!(
        "[discover] querying {} (unauth GitHub REST)",
        DISCOVER_TOPICS
            .iter()
            .map(|t| format!("topic:{}", t))
            .collect::<Vec<_>>()
            .join(" + ")
    );

    let mut by_name: BTreeMap<String, DiscoverHit> = BTreeMap::new();
    let mut total_seen = 0usize;
    for topic in DISCOVER_TOPICS {
        match fetch_topic(topic) {
            Ok(hits) => {
                total_seen += hits.len();
                for h in hits {
                    // Dedupe across topics: keep the entry already present
                    // (no semantic difference — same repo, same fields).
                    by_name.entry(h.full_name.clone()).or_insert(h);
                }
            }
            Err(e) => eprintln!("[discover] topic:{} failed: {}", topic, e),
        }
    }
    let total_unique = by_name.len();
    let mut hits: Vec<DiscoverHit> = by_name
        .into_values()
        .filter(|h| include_indexed || !known.contains(&h.full_name))
        .collect();
    hits.sort_by(|a, b| b.stars.cmp(&a.stars).then(a.full_name.cmp(&b.full_name)));
    let kept = hits.len();

    eprintln!(
        "[discover] {} candidate(s) total → {} unique → {} not yet indexed",
        total_seen,
        total_unique,
        if include_indexed { total_unique } else { kept }
    );
    if hits.is_empty() {
        eprintln!("[discover] nothing to show — try `--all` to include already-indexed repos");
        return Ok(());
    }

    eprintln!("[discover] top {} by stars:\n", limit.min(hits.len()));
    for h in hits.iter().take(limit) {
        let date = h.pushed_at.get(..10).unwrap_or(&h.pushed_at);
        let already = if known.contains(&h.full_name) {
            " [indexed]"
        } else {
            ""
        };
        println!("  ★{:>6}  {}  {}{}", h.stars, date, h.full_name, already);
        if !h.description.is_empty() {
            println!("          {}", h.description);
        }
    }
    eprintln!(
        "\n[discover] index a candidate: agent-bridge skills index https://github.com/<full_name>"
    );
    Ok(())
}

/// Fetch one GitHub topic search page via unauth REST. Returns hits sorted
/// by GitHub's default (best-match). Caller dedupes across topics.
fn fetch_topic(topic: &str) -> Result<Vec<DiscoverHit>> {
    let url = format!(
        "https://api.github.com/search/repositories?q=topic:{}&per_page=100&sort=stars",
        topic
    );
    let out = Command::new("curl")
        .args([
            "-sS",
            "-f",
            "-H",
            "Accept: application/vnd.github+json",
            "-H",
            "User-Agent: agent-bridge-skills-discover",
            &url,
        ])
        .stderr(Stdio::piped())
        .output()
        .context("spawn curl")?;
    if !out.status.success() {
        let stderr = String::from_utf8_lossy(&out.stderr);
        bail!("curl failed: {}", stderr.trim());
    }
    parse_search_response(&out.stdout)
}

fn parse_search_response(body: &[u8]) -> Result<Vec<DiscoverHit>> {
    let v: serde_json::Value = serde_json::from_slice(body).context("parse GitHub search JSON")?;
    let items = v
        .get("items")
        .and_then(|x| x.as_array())
        .ok_or_else(|| anyhow!("response missing items[] array"))?;
    let mut out = Vec::with_capacity(items.len());
    for it in items {
        let Some(full_name) = it.get("full_name").and_then(|x| x.as_str()) else {
            continue;
        };
        let stars = it
            .get("stargazers_count")
            .and_then(|x| x.as_u64())
            .unwrap_or(0);
        let pushed_at = it
            .get("pushed_at")
            .and_then(|x| x.as_str())
            .unwrap_or("")
            .to_string();
        let description = it
            .get("description")
            .and_then(|x| x.as_str())
            .unwrap_or("")
            .to_string();
        out.push(DiscoverHit {
            full_name: full_name.to_string(),
            stars,
            pushed_at,
            description,
        });
    }
    Ok(out)
}

/// Search indexed skills semantically. Filters to `kind = "skill"`.
pub async fn run_search(query: &str, limit: usize) -> Result<()> {
    let store = open_store().await?;
    // memory_search has no kind filter; filter via the "skill" tag instead.
    let tag_filter = vec!["skill".to_string()];
    let hits = store
        .memory_search(query, &tag_filter, limit as u32)
        .await
        .context("memory_search failed")?;
    if hits.is_empty() {
        eprintln!("[skills] no matches for {:?}", query);
        return Ok(());
    }
    for h in hits {
        let summary = first_line(&h.record.content);
        let tools = h
            .record
            .tags
            .iter()
            .find(|t| t.starts_with("tools:"))
            .map(|s| s.as_str())
            .unwrap_or("tools:?");
        let lint = h
            .record
            .tags
            .iter()
            .find(|t| t.starts_with("lint:"))
            .map(|s| s.as_str())
            .unwrap_or("lint:?");
        println!(
            "{:.2}  {}\n      {}\n      [{}, {}]\n",
            h.score, h.record.key, summary, tools, lint
        );
    }
    Ok(())
}

/// List most recently saved skills.
pub async fn run_list(limit: usize) -> Result<()> {
    let store = open_store().await?;
    let rows = store
        .list_memories(Some("skill"), MemoryListSort::Recent, limit as u32)
        .await
        .context("list_memories failed")?;
    if rows.is_empty() {
        eprintln!("[skills] none indexed yet — try `agent-bridge skills seed`");
        return Ok(());
    }
    for r in rows {
        let summary = first_line(&r.content);
        println!("{}\n      {}\n", r.key, summary);
    }
    Ok(())
}

/// Install an indexed skill into `~/.claude/skills/<name>/` by re-cloning
/// the source repo and copying the original SKILL.md (plus siblings, for
/// canonical-layout skills that ship scripts/data). With `assume_yes`,
/// skips the lint-warning confirmation prompt.
pub async fn run_install(key: &str, assume_yes: bool) -> Result<()> {
    let store = open_store().await?;
    let rec = store
        .memory_get(key)
        .await
        .context("memory_get failed")?
        .ok_or_else(|| anyhow!("no skill with key {:?}", key))?;
    let src =
        tag_value(&rec.tags, "src:").ok_or_else(|| anyhow!("record {} has no src: tag", key))?;
    let rel = tag_value(&rec.tags, "path:").ok_or_else(|| {
        anyhow!(
            "record {} has no path: tag (re-run `skills index` / `skills seed` to backfill)",
            key
        )
    })?;
    let lint_tag = tag_value(&rec.tags, "lint:").unwrap_or_else(|| "lint:?".to_string());
    let dest_name = derive_flat_name(key, &rel);
    let dest_root = claude_skills_dir()?;
    let dest = dest_root.join(&dest_name);

    eprintln!("[install] {} → {}", key, dest.display(),);
    eprintln!("[install]   source: {} : {}", src_to_clone_url(&src), rel);
    eprintln!("[install]   lint:   {}", lint_tag);
    if (lint_tag.starts_with("lint:warn:") || lint_tag.starts_with("lint:danger:")) && !assume_yes {
        eprintln!("[install]   skill flagged by lint — review SKILL.md before approving.");
        eprintln!("[install]   re-run with `--yes` to install anyway.");
        bail!("aborted: lint flags require explicit --yes");
    }
    if dest.exists() && !assume_yes {
        eprintln!("[install]   destination already exists: {}", dest.display());
        eprintln!("[install]   re-run with `--yes` to overwrite.");
        bail!("aborted: destination exists");
    }

    // Clone, copy, clean up.
    let url = src_to_clone_url(&src);
    let clone_dir = clone_shallow(&url, &src.replace('/', "_"), None)?;
    let source_path = clone_dir.join(&rel);
    if !source_path.exists() {
        let _ = std::fs::remove_dir_all(&clone_dir);
        bail!(
            "expected file {} in cloned repo but it's missing — upstream may have moved",
            rel
        );
    }
    std::fs::create_dir_all(&dest_root)
        .with_context(|| format!("create dest root {}", dest_root.display()))?;
    if dest.exists() {
        std::fs::remove_dir_all(&dest)
            .or_else(|_| std::fs::remove_file(&dest))
            .with_context(|| format!("remove existing {}", dest.display()))?;
    }
    let canonical = source_path
        .file_name()
        .and_then(|n| n.to_str())
        .map(|n| n.eq_ignore_ascii_case("SKILL.md"))
        .unwrap_or(false);
    if canonical {
        // Copy the entire parent directory so sibling scripts/data come along.
        let parent = source_path
            .parent()
            .ok_or_else(|| anyhow!("SKILL.md has no parent dir"))?;
        copy_dir_recursive(parent, &dest)?;
    } else {
        // Single-file skill — drop just the .md.
        std::fs::create_dir_all(&dest)
            .with_context(|| format!("create dest dir {}", dest.display()))?;
        let leaf = source_path
            .file_name()
            .ok_or_else(|| anyhow!("source has no filename"))?;
        std::fs::copy(&source_path, dest.join(leaf))
            .with_context(|| format!("copy {} → {}", source_path.display(), dest.display()))?;
    }
    let _ = std::fs::remove_dir_all(&clone_dir);
    eprintln!("[install] done");
    Ok(())
}

fn tag_value(tags: &[String], prefix: &str) -> Option<String> {
    tags.iter()
        .find(|t| t.starts_with(prefix))
        .map(|t| t[prefix.len()..].to_string())
}

fn derive_flat_name(key: &str, rel_path: &str) -> String {
    // Prefer the parent dir of SKILL.md (canonical) or the filename stem
    // (single-file). Falls back to the last `/` segment of the key.
    let path = std::path::PathBuf::from(rel_path);
    if let Some(name) = path.file_name().and_then(|n| n.to_str()) {
        if name.eq_ignore_ascii_case("SKILL.md") {
            if let Some(parent) = path
                .parent()
                .and_then(|p| p.file_name())
                .and_then(|n| n.to_str())
            {
                return parent.to_string();
            }
        } else if name.ends_with(".md") {
            return name.trim_end_matches(".md").to_string();
        }
    }
    key.rsplit('/').next().unwrap_or(key).to_string()
}

fn claude_skills_dir() -> Result<PathBuf> {
    let home = std::env::var("HOME").context("HOME not set")?;
    Ok(PathBuf::from(home).join(".claude").join("skills"))
}

fn copy_dir_recursive(src: &Path, dest: &Path) -> Result<()> {
    std::fs::create_dir_all(dest).with_context(|| format!("create dir {}", dest.display()))?;
    for entry in std::fs::read_dir(src).with_context(|| format!("read dir {}", src.display()))? {
        let entry = entry?;
        let from = entry.path();
        let to = dest.join(entry.file_name());
        if entry.file_type()?.is_dir() {
            copy_dir_recursive(&from, &to)?;
        } else {
            std::fs::copy(&from, &to)
                .with_context(|| format!("copy {} → {}", from.display(), to.display()))?;
        }
    }
    Ok(())
}

/// Print one skill's body + metadata.
pub async fn run_show(key: &str, json: bool) -> Result<()> {
    let store = open_store().await?;
    let rec = store
        .memory_get(key)
        .await
        .context("memory_get failed")?
        .ok_or_else(|| anyhow!("no skill with key {:?}", key))?;
    if json {
        println!("{}", serde_json::to_string_pretty(&skill_show_json_payload(&rec))?);
        return Ok(());
    }
    println!("# {}", rec.key);
    println!("tags: {}", rec.tags.join(", "));
    println!("---");
    println!("{}", rec.content);
    Ok(())
}

fn skill_show_json_payload(rec: &MemoryRecord) -> serde_json::Value {
    let git = serde_json::json!({
        "commit": tag_value(&rec.tags, "git_commit:"),
        "branch": tag_value(&rec.tags, "git_branch:"),
        "origin": tag_value(&rec.tags, "git_origin:"),
        "src": tag_value(&rec.tags, "git_src:"),
    });
    let tools = tag_value(&rec.tags, "tools:")
        .map(|v| {
            v.split(',')
                .map(str::trim)
                .filter(|s| !s.is_empty())
                .map(str::to_string)
                .collect::<Vec<_>>()
        })
        .unwrap_or_default();

    serde_json::json!({
        "key": &rec.key,
        "kind": &rec.kind,
        "content": &rec.content,
        "tags": &rec.tags,
        "related_keys": &rec.related_keys,
        "scope": &rec.scope,
        "created_at": rec.created_at,
        "updated_at": rec.updated_at,
        "last_accessed_at": rec.last_accessed_at,
        "access_count": rec.access_count,
        "importance": rec.importance,
        "status": &rec.status,
        "source": tag_value(&rec.tags, "src:"),
        "path": tag_value(&rec.tags, "path:"),
        "lint": tag_value(&rec.tags, "lint:"),
        "vendor": tag_value(&rec.tags, "vendor:"),
        "license": tag_value(&rec.tags, "license:"),
        "compatibility": tag_value(&rec.tags, "compatibility:"),
        "tools": tools,
        "git": git,
        "risks": tag_values(&rec.tags, "risk:"),
    })
}

fn tag_values(tags: &[String], prefix: &str) -> Vec<String> {
    tags.iter()
        .filter_map(|t| t.strip_prefix(prefix).map(str::to_string))
        .collect()
}

// ── source resolution ─────────────────────────────────────────────────────

/// Returns `(owned_clone, repo_dir, src_id)`. `src_id` is `<owner>/<repo>`
/// for URLs, or the basename for local paths.
fn resolve_source(source: &str) -> Result<(bool, PathBuf, String)> {
    if source.starts_with("http://") || source.starts_with("https://") || source.starts_with("git@")
    {
        let spec = parse_remote_source(source)?;
        let dir = clone_shallow(&spec.clone_url, &spec.src_id, spec.checkout_ref.as_deref())?;
        Ok((true, dir, spec.src_id))
    } else {
        let p = PathBuf::from(source);
        if !p.exists() {
            bail!("source path does not exist: {}", p.display());
        }
        let canon = p.canonicalize().unwrap_or(p);
        let src_id = canon
            .file_name()
            .map(|s| s.to_string_lossy().to_string())
            .unwrap_or_else(|| "unknown".to_string());
        Ok((false, canon, src_id))
    }
}

#[derive(Debug, Clone, PartialEq, Eq)]
struct RemoteSourceSpec {
    clone_url: String,
    src_id: String,
    checkout_ref: Option<String>,
}

fn parse_remote_source(source: &str) -> Result<RemoteSourceSpec> {
    if source.starts_with("git@") {
        let src_id = parse_src_id(source)?;
        return Ok(RemoteSourceSpec {
            clone_url: source.to_string(),
            src_id,
            checkout_ref: None,
        });
    }

    let stripped = source.trim_end_matches('/').trim_end_matches(".git");

    if let Some((_, after)) = stripped.rsplit_once("gitlab.com") {
        let (owner, repo, rest) = parse_owner_repo_rest(after, source)?;
        let checkout_ref = parse_tree_ref(&rest, true);
        return Ok(RemoteSourceSpec {
            clone_url: format!("https://gitlab.com/{}/{}.git", owner, repo),
            src_id: format!("gitlab.com/{}/{}", owner, repo),
            checkout_ref,
        });
    }

    if let Some((_, after)) = stripped.rsplit_once("github.com") {
        let (owner, repo, rest) = parse_owner_repo_rest(after, source)?;
        let checkout_ref = parse_tree_ref(&rest, false);
        return Ok(RemoteSourceSpec {
            clone_url: format!("https://github.com/{}/{}.git", owner, repo),
            src_id: format!("{}/{}", owner, repo),
            checkout_ref,
        });
    }

    bail!("not a github/gitlab URL: {}", source)
}

/// Parse a clone URL into the canonical `src_id` we store in `src:` tags.
///
/// Format:
///   - GitHub: `<owner>/<repo>` (no host prefix — back-compat with all
///     pre-2026-05-07 records that assume github implicitly).
///   - GitLab: `gitlab.com/<owner>/<repo>` (host prefix lets the reverse
///     mapping in [`src_to_clone_url`] reconstruct the right URL).
///
/// Accepts both `https://...` and `git@...:...` forms for either host.
fn parse_src_id(url: &str) -> Result<String> {
    let stripped = url.trim_end_matches('/').trim_end_matches(".git");
    // GitLab first: an URL like `https://github.com/foo/gitlab.com-mirror`
    // would falsely match if we checked github first. (Vanishingly rare,
    // but the order is harmless.)
    if let Some((_, after)) = stripped.rsplit_once("gitlab.com") {
        let (owner, repo) = parse_owner_repo(after, url)?;
        return Ok(format!("gitlab.com/{}/{}", owner, repo));
    }
    if let Some((_, after)) = stripped.rsplit_once("github.com") {
        let (owner, repo) = parse_owner_repo(after, url)?;
        return Ok(format!("{}/{}", owner, repo));
    }
    bail!("not a github/gitlab URL: {}", url)
}

fn parse_owner_repo<'a>(after_host: &'a str, original: &str) -> Result<(&'a str, &'a str)> {
    // `after_host` is "/owner/repo" (https) or ":owner/repo" (ssh).
    let cleaned = after_host.trim_start_matches([':', '/']);
    let mut parts = cleaned.split('/');
    let owner = parts.next().unwrap_or("");
    let repo = parts.next().unwrap_or("");
    if owner.is_empty() || repo.is_empty() {
        bail!("could not parse owner/repo from {}", original);
    }
    Ok((owner, repo))
}

fn parse_owner_repo_rest<'a>(
    after_host: &'a str,
    original: &str,
) -> Result<(&'a str, &'a str, Vec<&'a str>)> {
    let cleaned = after_host.trim_start_matches([':', '/']);
    let mut parts = cleaned.split('/');
    let owner = parts.next().unwrap_or("");
    let repo = parts.next().unwrap_or("").trim_end_matches(".git");
    if owner.is_empty() || repo.is_empty() {
        bail!("could not parse owner/repo from {}", original);
    }
    Ok((owner, repo, parts.collect()))
}

fn parse_tree_ref(rest: &[&str], gitlab: bool) -> Option<String> {
    let ref_parts = if gitlab {
        if rest.len() >= 3 && rest[0] == "-" && rest[1] == "tree" {
            &rest[2..]
        } else {
            &[]
        }
    } else if rest.len() >= 2 && rest[0] == "tree" {
        &rest[1..]
    } else {
        &[]
    };
    if ref_parts.is_empty() {
        None
    } else {
        Some(ref_parts.join("/"))
    }
}

/// Reverse of [`parse_src_id`]: given a stored `src_id`, build the
/// HTTPS clone URL. Defaults to GitHub when no host prefix is present.
fn src_to_clone_url(src: &str) -> String {
    if let Some(rest) = src.strip_prefix("gitlab.com/") {
        format!("https://gitlab.com/{}", rest)
    } else {
        format!("https://github.com/{}", src)
    }
}

fn clone_shallow(url: &str, src_id: &str, checkout_ref: Option<&str>) -> Result<PathBuf> {
    let nonce = SystemTime::now()
        .duration_since(SystemTime::UNIX_EPOCH)
        .map(|d| d.as_nanos())
        .unwrap_or(0);
    let safe_id = src_id.replace('/', "_");
    let dir = std::env::temp_dir().join(format!("ab-skills-{}-{}", safe_id, nonce));
    let mut args = vec![
        "clone".to_string(),
        "--depth=1".to_string(),
        "--quiet".to_string(),
        "--filter=blob:none".to_string(),
    ];
    if let Some(r) = checkout_ref {
        args.push("--branch".to_string());
        args.push(r.to_string());
        args.push("--single-branch".to_string());
    }
    args.push(url.to_string());
    args.push(dir.to_string_lossy().to_string());

    let status = Command::new("git")
        .args(&args)
        .stdout(Stdio::null())
        .stderr(Stdio::inherit())
        .status()
        .with_context(|| format!("git clone {} failed to launch", url))?;
    if !status.success() {
        bail!("git clone {} exited with {:?}", url, status.code());
    }
    Ok(dir)
}

// ── walk ──────────────────────────────────────────────────────────────────

fn walk_skill_files(repo: &Path, src_id: &str) -> Result<Vec<SkillFile>> {
    let mut out = Vec::new();
    let source_tags = source_metadata_tags(repo);
    let walker = walkdir::WalkDir::new(repo)
        .max_depth(8)
        .follow_links(false)
        .into_iter()
        .filter_entry(|e| {
            // Skip .git, node_modules, target
            let name = e.file_name().to_string_lossy();
            !matches!(name.as_ref(), ".git" | "node_modules" | "target" | "dist")
        });
    for entry in walker.flatten() {
        if !entry.file_type().is_file() {
            continue;
        }
        let path = entry.path();
        let rel = path.strip_prefix(repo).unwrap_or(path).to_path_buf();
        let Some(name) = path.file_name().and_then(|n| n.to_str()) else {
            continue;
        };
        let comps: Vec<String> = rel
            .components()
            .map(|c| c.as_os_str().to_string_lossy().to_string())
            .collect();
        // Pattern 1 (canonical): any path ending in `<dir>/SKILL.md`. Most
        // community repos and Anthropic's official layout use this.
        let canonical = name.eq_ignore_ascii_case("SKILL.md");
        // Pattern 2: a single-file skill directly under .claude/skills/
        //   `[".claude", "skills", "<name>.md"]` (depth = 3).
        let claude_skills_top = comps.len() == 3
            && comps[0] == ".claude"
            && comps[1] == "skills"
            && name.ends_with(".md");
        // Pattern 3: a single-file skill directly under skills/
        //   `["skills", "<name>.md"]` (depth = 2).
        let skills_top = comps.len() == 2 && comps[0] == "skills" && name.ends_with(".md");
        if !canonical && !claude_skills_top && !skills_top {
            continue;
        }
        let body =
            std::fs::read_to_string(path).with_context(|| format!("read {}", path.display()))?;
        let skill_name = if canonical {
            // Use the FULL parent path (relative to repo root) so nested
            // SKILL.md files at e.g. `claude-api/REFERENCE/SKILL.md` get
            // a distinct key from the parent `claude-api/SKILL.md`.
            // Strip leading `skills/` or `.claude/skills/` boilerplate
            // so the key is `<src>/<name>` not `<src>/skills/<name>`.
            let parent = rel
                .parent()
                .filter(|p| !p.as_os_str().is_empty())
                .map(|p| p.to_string_lossy().to_string())
                .unwrap_or_else(|| "skill".to_string());
            strip_skills_prefix(&parent).to_string()
        } else {
            // strip extension
            name.trim_end_matches(".md").to_string()
        };
        out.push(SkillFile {
            src: src_id.to_string(),
            name: skill_name,
            rel_path: rel,
            body,
            source_tags: source_tags.clone(),
        });
    }
    Ok(out)
}

fn source_metadata_tags(repo: &Path) -> Vec<String> {
    let mut tags = Vec::new();
    let Some(commit) = git_output(repo, &["rev-parse", "HEAD"]) else {
        return tags;
    };
    tags.push(format!("git_commit:{}", commit));

    if let Some(branch) = git_output(repo, &["rev-parse", "--abbrev-ref", "HEAD"]) {
        if branch != "HEAD" {
            tags.push(format!("git_branch:{}", tag_safe_value(&branch)));
        }
    }
    if let Some(origin) = git_output(repo, &["config", "--get", "remote.origin.url"]) {
        tags.push(format!("git_origin:{}", tag_safe_value(&origin)));
        if let Ok(src) = parse_src_id(&origin) {
            tags.push(format!("git_src:{}", src));
        }
    }
    tags
}

fn git_output(repo: &Path, args: &[&str]) -> Option<String> {
    let out = Command::new("git")
        .arg("-C")
        .arg(repo)
        .args(args)
        .output()
        .ok()?;
    if !out.status.success() {
        return None;
    }
    let s = String::from_utf8_lossy(&out.stdout).trim().to_string();
    (!s.is_empty()).then_some(s)
}

fn tag_safe_value(s: &str) -> String {
    s.chars()
        .map(|c| if c.is_whitespace() { '_' } else { c })
        .collect()
}

/// Strip a leading boilerplate prefix (`.agents/skills/` per agentskills.io
/// spec, `.claude/skills/` legacy Claude Code, or bare `skills/`) from a
/// relative path so the resulting skill key is shorter and stable across
/// repo layouts.
fn strip_skills_prefix(path: &str) -> &str {
    for prefix in [".agents/skills/", ".claude/skills/", "skills/"] {
        if let Some(rest) = path.strip_prefix(prefix) {
            return rest;
        }
    }
    path
}

// ── frontmatter parser ────────────────────────────────────────────────────

fn split_frontmatter(body: &str) -> (Frontmatter, &str) {
    let trimmed = body.trim_start_matches('\u{feff}');
    let after_open = if let Some(rest) = trimmed.strip_prefix("---\n") {
        rest
    } else if let Some(rest) = trimmed.strip_prefix("---\r\n") {
        rest
    } else {
        return (Frontmatter::default(), trimmed);
    };
    // Locate the closing "---" on its own line; accept either LF or CRLF.
    let closing = ["\n---\n", "\n---\r\n"]
        .iter()
        .filter_map(|m| after_open.find(m).map(|i| (i, m.len())))
        .min_by_key(|(i, _)| *i);
    let (yaml_end, marker_len) = match closing {
        Some(v) => v,
        None => return (Frontmatter::default(), trimmed),
    };
    let yaml_section = &after_open[..yaml_end];
    let body_after = &after_open[yaml_end + marker_len..];

    let mut fm = Frontmatter::default();
    for line in yaml_section.lines() {
        let line = line.trim();
        if line.is_empty() || line.starts_with('#') {
            continue;
        }
        let Some((k, v)) = line.split_once(':') else {
            continue;
        };
        let key = k.trim();
        let mut val = v.trim().trim_matches('"').trim_matches('\'').to_string();
        match key {
            "name" => fm.name = Some(val),
            "description" => fm.description = Some(val),
            "license" => fm.license = Some(val),
            "compatibility" => fm.compatibility = Some(val),
            "allowed-tools" | "allowed_tools" | "tools" => {
                // Spec (agentskills.io): "space-separated string of pre-approved
                // tools". Tolerate two legacy forms still in the wild:
                //   - YAML inline list: `[Read, Grep]` → split on commas
                //   - Bare string: `Bash(git:*) Read` → split on whitespace
                let bracketed = val.starts_with('[') && val.ends_with(']');
                if bracketed {
                    val = val[1..val.len() - 1].to_string();
                }
                let split_iter: Box<dyn Iterator<Item = &str>> = if bracketed {
                    Box::new(val.split(','))
                } else {
                    Box::new(val.split_whitespace())
                };
                fm.allowed_tools = split_iter
                    .map(|s| s.trim().trim_matches('"').trim_matches('\'').to_string())
                    .filter(|s| !s.is_empty())
                    .collect();
            }
            other => {
                fm.extras.insert(other.to_string(), val);
            }
        }
    }
    (fm, body_after)
}

// ── lint ──────────────────────────────────────────────────────────────────

fn lint_body(body: &str) -> Vec<LintFinding> {
    let mut out = Vec::new();
    let cred_paths = [".ssh/id_", ".aws/credentials", "/.env\"", "/.env'"];
    let dangerous_rm = ["rm -rf /", "rm -rf $home", "rm -rf ~"];
    let pipe_shell_suffixes = [
        "| bash", "|bash", "| sh", "|sh", "| zsh", "|zsh", "| bash -",
    ];

    for (i, line) in body.lines().enumerate() {
        let lower = line.to_ascii_lowercase();
        let trimmed = lower.trim_end_matches(|c: char| c.is_whitespace() || c == ')');

        // pipe-to-shell: require BOTH a fetch verb AND a pipe-to-sh suffix
        // on the same line. Avoids the markdown-table false positives that
        // bare "| bash" patterns produce (`| Bash Tool | ...`).
        let fetches = lower.contains("curl ")
            || lower.contains("wget ")
            || lower.contains("fetch ")
            || lower.contains("iwr ")
            || lower.contains("invoke-webrequest");
        let pipes_to_shell = pipe_shell_suffixes
            .iter()
            .any(|s| trimmed.ends_with(s) || lower.contains(&format!("{} ", s)));
        if fetches && pipes_to_shell {
            out.push(LintFinding {
                sev: LintSev::Warn,
                rule: "pipe-to-shell",
                snippet: format!("L{}: {}", i + 1, line.trim()),
            });
        }
        for pat in cred_paths {
            if lower.contains(pat) {
                out.push(LintFinding {
                    sev: LintSev::Warn,
                    rule: "creds-path",
                    snippet: format!("L{}: {}", i + 1, line.trim()),
                });
                break;
            }
        }
        for pat in dangerous_rm {
            if lower.contains(pat) {
                out.push(LintFinding {
                    sev: LintSev::Danger,
                    rule: "dangerous-rm",
                    snippet: format!("L{}: {}", i + 1, line.trim()),
                });
                break;
            }
        }
        if lower.contains("eval $(") || lower.contains("eval `") {
            out.push(LintFinding {
                sev: LintSev::Warn,
                rule: "eval-substitution",
                snippet: format!("L{}: {}", i + 1, line.trim()),
            });
        }
    }
    out
}

fn lint_summary_tag(findings: &[LintFinding]) -> String {
    let danger = findings.iter().filter(|f| f.sev == LintSev::Danger).count();
    let warn = findings.iter().filter(|f| f.sev == LintSev::Warn).count();
    if danger > 0 {
        format!("lint:danger:{}", danger)
    } else if warn > 0 {
        format!("lint:warn:{}", warn)
    } else if !findings.is_empty() {
        format!("lint:info:{}", findings.len())
    } else {
        "lint:clean".to_string()
    }
}

fn operational_risk_tags(name: &str, description: &str, body: &str) -> Vec<String> {
    let name_lower = name.to_ascii_lowercase();
    let desc_lower = description.to_ascii_lowercase();
    let text = format!("{}\n{}", description, body);
    let lower = text.to_ascii_lowercase();
    let mut tags = BTreeSet::new();

    if lower.contains("pip install")
        || lower.contains("uv pip install")
        || lower.contains("conda install")
        || lower.contains("brew install")
        || lower.contains("npm install")
        || lower.contains("cargo install")
    {
        tags.insert("risk:pip_install");
    }
    if lower.contains("huggingface-cli download")
        || lower.contains("modelscope download")
        || lower.contains("ollama pull")
        || lower.contains("git clone")
        || lower.contains("curl ")
        || lower.contains("wget ")
    {
        tags.insert("risk:network_fetch");
    }
    if lower.contains("huggingface-cli download")
        || lower.contains("modelscope download")
        || lower.contains("ollama pull")
        || lower.contains("from ./")
        || lower.contains("--model ")
        || lower.contains("--model-path")
    {
        tags.insert("risk:model_download");
    }
    if lower.contains("vllm serve")
        || lower.contains("launch_server")
        || lower.contains("mlx_lm.server")
        || lower.contains("llama-server")
        || lower.contains("ollama serve")
        || lower.contains("server start")
    {
        tags.insert("risk:server_start");
    }
    if lower.contains("trainer.train")
        || lower.contains("finetune")
        || lower.contains("fine-tuning")
        || lower.contains("lora")
    {
        tags.insert("risk:finetune_write");
    }
    if lower.contains("trainer.train")
        || lower.contains("checkpoint")
        || lower.contains("output_dir")
        || lower.contains("--output")
        || lower.contains("--save")
        || lower.contains("--mlx-path")
        || lower.contains("write to")
    {
        tags.insert("risk:checkpoint_write");
    }
    if name_lower.contains("mlx")
        || desc_lower.contains("mlx framework")
        || (desc_lower.contains("apple silicon") && desc_lower.contains("mlx"))
    {
        tags.insert("risk:apple_mlx");
    }
    if desc_lower.contains("nvidia gpu")
        || lower.contains("cuda_visible_devices")
        || lower.contains("gpu-memory-utilization")
        || lower.contains("vram")
    {
        tags.insert("risk:gpu_required");
    }

    tags.into_iter().map(str::to_string).collect()
}

// ── record building ───────────────────────────────────────────────────────

fn build_record(sf: &SkillFile) -> Result<MemoryRecord> {
    let (fm, body) = split_frontmatter(&sf.body);
    // Key = repo + path-derived skill identifier. We deliberately do NOT
    // use frontmatter `name` here, because nested skills at different
    // paths can share the same `name` (e.g. multiple "README"-titled
    // SKILL.md files); the path discriminator keeps keys unique.
    let key = format!("skill:{}/{}", sf.src, sf.name);
    let description = fm
        .description
        .clone()
        .unwrap_or_else(|| first_line(body).to_string());
    let findings = lint_body(body);
    for f in &findings {
        if matches!(f.sev, LintSev::Warn | LintSev::Danger) {
            eprintln!(
                "[skills]   ! {} [{:?}/{}] {}",
                key, f.sev, f.rule, f.snippet
            );
        }
    }

    // `path:<rel>` records the original SKILL.md location inside the repo
    // so `skills install` can re-clone and copy the right folder. We keep
    // it as a tag (not the key) so the human-facing key stays short and
    // dedupe-friendly across boilerplate-prefix variations.
    let path_str = sf.rel_path.to_string_lossy().to_string();
    let mut tags = vec![
        "skill".to_string(),
        format!("src:{}", sf.src),
        format!("path:{}", path_str),
        lint_summary_tag(&findings),
        // vendor classification — feeds ranking / filtering. See
        // KNOWN_VENDORS const above for what counts as vendor-curated.
        format!("vendor:{}", classify_vendor(&sf.src)),
    ];
    tags.extend(sf.source_tags.iter().cloned());
    tags.extend(operational_risk_tags(&sf.name, &description, body));
    // Preserve agentskills.io spec optional fields as tags. They're not
    // used for embedding signal (which is description + body), but they
    // matter for compliance, redistribution, and environment-aware
    // filtering. Keeping them as tags lets `memory_search` filter without
    // re-parsing.
    if let Some(lic) = &fm.license {
        tags.push(format!("license:{}", lic));
    }
    if let Some(compat) = &fm.compatibility {
        tags.push(format!("compatibility:{}", compat));
    }
    if !fm.allowed_tools.is_empty() {
        // Stored comma-joined in the tag value for grep/filter ergonomics;
        // input parser accepts both space-separated (spec) and bracketed
        // YAML list (legacy).
        tags.push(format!("tools:{}", fm.allowed_tools.join(",")));
    }

    // Body for the memory record: description (for embedding signal) +
    // separator + the actual skill body. Description first means the
    // embedding gets a strong topical signal even when the body is long.
    let content = format!("{}\n\n{}", description, body.trim_start());

    let now = unix_now();
    Ok(MemoryRecord {
        key,
        kind: "skill".to_string(),
        content,
        tags,
        related_keys: Vec::new(),
        scope: Some("global".to_string()),
        created_at: now,
        updated_at: now,
        last_accessed_at: now,
        access_count: 0,
        importance: 0.5,
        status: "active".to_string(),
        trigger_pattern: None,
        superseded_by: None,
    })
}

// ── small helpers ─────────────────────────────────────────────────────────

fn first_line(s: &str) -> &str {
    s.lines()
        .find(|l| !l.trim().is_empty())
        .unwrap_or("")
        .trim()
}

fn unix_now() -> i64 {
    SystemTime::now()
        .duration_since(SystemTime::UNIX_EPOCH)
        .map(|d| d.as_secs() as i64)
        .unwrap_or(0)
}

async fn open_store() -> Result<SqliteStore> {
    let db_path = std::env::var("AGENT_BRIDGE_DB")
        .ok()
        .map(PathBuf::from)
        .unwrap_or_else(ab_store::default_db_path);
    SqliteStore::open(&db_path)
        .await
        .with_context(|| format!("open SqliteStore at {}", db_path.display()))
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn frontmatter_basic() {
        let body = "---\nname: foo\ndescription: A small thing\n---\nBody text\n";
        let (fm, rest) = split_frontmatter(body);
        assert_eq!(fm.name.as_deref(), Some("foo"));
        assert_eq!(fm.description.as_deref(), Some("A small thing"));
        assert!(rest.starts_with("Body"), "rest={:?}", rest);
    }

    #[test]
    fn frontmatter_allowed_tools_inline_list() {
        let body = "---\nname: x\nallowed-tools: [Read, Grep]\n---\nbody";
        let (fm, _) = split_frontmatter(body);
        assert_eq!(fm.allowed_tools, vec!["Read", "Grep"]);
    }

    #[test]
    fn frontmatter_missing_returns_full_body() {
        let body = "no frontmatter here\n";
        let (fm, rest) = split_frontmatter(body);
        assert!(fm.name.is_none());
        assert_eq!(rest, body);
    }

    #[test]
    fn parse_src_id_https() {
        assert_eq!(
            parse_src_id("https://github.com/anthropics/skills").unwrap(),
            "anthropics/skills"
        );
        assert_eq!(
            parse_src_id("https://github.com/foo/bar.git").unwrap(),
            "foo/bar"
        );
        assert_eq!(
            parse_src_id("git@github.com:foo/bar.git").unwrap(),
            "foo/bar"
        );
    }

    #[test]
    fn parse_src_id_gitlab() {
        assert_eq!(
            parse_src_id("https://gitlab.com/pallasting/agent-bridge-skills").unwrap(),
            "gitlab.com/pallasting/agent-bridge-skills"
        );
        assert_eq!(
            parse_src_id("https://gitlab.com/foo/bar.git").unwrap(),
            "gitlab.com/foo/bar"
        );
        assert_eq!(
            parse_src_id("git@gitlab.com:foo/bar.git").unwrap(),
            "gitlab.com/foo/bar"
        );
    }

    #[test]
    fn parse_remote_source_github_tree_url() {
        let spec = parse_remote_source("https://github.com/OpenBMB/MiniCPM/tree/minicpm5").unwrap();
        assert_eq!(spec.src_id, "OpenBMB/MiniCPM");
        assert_eq!(spec.clone_url, "https://github.com/OpenBMB/MiniCPM.git");
        assert_eq!(spec.checkout_ref.as_deref(), Some("minicpm5"));
    }

    #[test]
    fn parse_remote_source_github_plain_url() {
        let spec = parse_remote_source("https://github.com/anthropics/skills").unwrap();
        assert_eq!(spec.src_id, "anthropics/skills");
        assert_eq!(spec.clone_url, "https://github.com/anthropics/skills.git");
        assert_eq!(spec.checkout_ref, None);
    }

    #[test]
    fn parse_remote_source_gitlab_tree_url() {
        let spec =
            parse_remote_source("https://gitlab.com/pallasting/agent-bridge/-/tree/feature/foo")
                .unwrap();
        assert_eq!(spec.src_id, "gitlab.com/pallasting/agent-bridge");
        assert_eq!(
            spec.clone_url,
            "https://gitlab.com/pallasting/agent-bridge.git"
        );
        assert_eq!(spec.checkout_ref.as_deref(), Some("feature/foo"));
    }

    #[test]
    fn parse_remote_source_ssh_preserves_clone_url() {
        let spec = parse_remote_source("git@github.com:foo/bar.git").unwrap();
        assert_eq!(spec.src_id, "foo/bar");
        assert_eq!(spec.clone_url, "git@github.com:foo/bar.git");
        assert_eq!(spec.checkout_ref, None);
    }

    #[test]
    fn parse_src_id_rejects_unknown_host() {
        assert!(parse_src_id("https://codeberg.org/foo/bar").is_err());
        assert!(parse_src_id("not a url").is_err());
    }

    #[test]
    fn src_to_clone_url_round_trip() {
        // GitHub: no host prefix → github URL.
        assert_eq!(
            src_to_clone_url("anthropics/skills"),
            "https://github.com/anthropics/skills"
        );
        // GitLab: prefix preserved through the round trip.
        assert_eq!(
            src_to_clone_url("gitlab.com/pallasting/agent-bridge-skills"),
            "https://gitlab.com/pallasting/agent-bridge-skills"
        );
        // Round-trip both providers.
        for url in [
            "https://github.com/anthropics/skills",
            "https://gitlab.com/pallasting/agent-bridge-skills",
        ] {
            let src = parse_src_id(url).unwrap();
            assert_eq!(src_to_clone_url(&src), url);
        }
    }

    #[test]
    fn parse_search_response_extracts_fields() {
        let body = br#"{
            "total_count": 2,
            "items": [
                {
                    "full_name": "foo/bar",
                    "stargazers_count": 42,
                    "pushed_at": "2026-04-01T12:34:56Z",
                    "description": "neat library"
                },
                {
                    "full_name": "baz/qux",
                    "stargazers_count": 0,
                    "pushed_at": "2025-01-01T00:00:00Z",
                    "description": null
                }
            ]
        }"#;
        let hits = parse_search_response(body).unwrap();
        assert_eq!(hits.len(), 2);
        assert_eq!(hits[0].full_name, "foo/bar");
        assert_eq!(hits[0].stars, 42);
        assert!(hits[0].pushed_at.starts_with("2026-04-01"));
        assert_eq!(hits[0].description, "neat library");
        assert_eq!(hits[1].description, ""); // null → empty
    }

    #[test]
    fn parse_search_response_rejects_missing_items() {
        let body = br#"{"message": "something else"}"#;
        assert!(parse_search_response(body).is_err());
    }

    fn mk_skill(src: &str, updated_at: i64) -> MemoryRecord {
        MemoryRecord {
            key: format!("skill:{}/x", src),
            kind: "skill".to_string(),
            content: "body".to_string(),
            tags: vec!["skill".to_string(), format!("src:{}", src)],
            related_keys: vec![],
            scope: None,
            created_at: 0,
            updated_at,
            last_accessed_at: 0,
            access_count: 0,
            importance: 0.5,
            status: "active".to_string(),
            trigger_pattern: None,
            superseded_by: None,
        }
    }

    #[test]
    fn is_stale_for_src_basic() {
        let threshold = 1_000_000_i64;
        // Same src, older updated_at → stale.
        assert!(is_stale_for_src(
            &mk_skill("foo/bar", threshold - 1),
            "foo/bar",
            threshold
        ));
        // Same src, exactly at threshold → NOT stale (boundary: only strictly older).
        assert!(!is_stale_for_src(
            &mk_skill("foo/bar", threshold),
            "foo/bar",
            threshold
        ));
        // Same src, just-refreshed (updated_at >= threshold) → not stale.
        assert!(!is_stale_for_src(
            &mk_skill("foo/bar", threshold + 5),
            "foo/bar",
            threshold
        ));
        // Different src — must NOT match.
        assert!(!is_stale_for_src(
            &mk_skill("other/repo", threshold - 100),
            "foo/bar",
            threshold
        ));
        // No src tag at all → not stale.
        let mut rec = mk_skill("foo/bar", threshold - 1);
        rec.tags.retain(|t| !t.starts_with("src:"));
        assert!(!is_stale_for_src(&rec, "foo/bar", threshold));
    }

    #[test]
    fn is_remote_src_classification() {
        // GitHub: <owner>/<repo> (no host prefix — back-compat).
        assert!(is_remote_src("anthropics/skills"));
        assert!(is_remote_src("warpdotdev/oz-skills"));
        assert!(is_remote_src("oz-skills-test/.agents"));
        // GitLab: gitlab.com/<owner>/<repo>.
        assert!(is_remote_src("gitlab.com/pallasting/agent-bridge-skills"));
        assert!(is_remote_src("gitlab.com/foo/bar"));
        // Negatives.
        assert!(!is_remote_src(""));
        assert!(!is_remote_src("local-checkout"));
        assert!(!is_remote_src("anthropics"));
        assert!(!is_remote_src("a/b/c")); // 3-segment non-gitlab path
        assert!(!is_remote_src("/foo"));
        assert!(!is_remote_src("gitlab.com/onlyowner")); // gitlab needs 3 segments
        assert!(!is_remote_src("gitlab.com/owner/repo/extra")); // 4 segments
    }

    #[test]
    fn lint_flags_pipe_to_shell() {
        let body = "Run this:\n```\ncurl https://x | bash\n```\n";
        let f = lint_body(body);
        assert!(f.iter().any(|x| x.rule == "pipe-to-shell"));
    }

    #[test]
    fn derive_flat_name_basic() {
        assert_eq!(
            derive_flat_name("skill:anthropics/skills/pdf", "pdf/SKILL.md"),
            "pdf"
        );
        assert_eq!(
            derive_flat_name("skill:alirezarezvani/claude-skills/x", "skills/x/SKILL.md"),
            "x"
        );
        assert_eq!(
            derive_flat_name("skill:foo/bar/single", ".claude/skills/single.md"),
            "single"
        );
        // Fallback when path doesn't fit the patterns.
        assert_eq!(derive_flat_name("skill:foo/bar/baz", "weird/path"), "baz");
    }

    #[test]
    fn tag_value_extracts_prefixed_payload() {
        let tags = vec![
            "skill".to_string(),
            "src:anthropics/skills".to_string(),
            "path:pdf/SKILL.md".to_string(),
            "lint:clean".to_string(),
        ];
        assert_eq!(
            tag_value(&tags, "src:"),
            Some("anthropics/skills".to_string())
        );
        assert_eq!(tag_value(&tags, "path:"), Some("pdf/SKILL.md".to_string()));
        assert_eq!(tag_value(&tags, "missing:"), None);
    }

    #[test]
    fn skill_show_json_payload_extracts_metadata() {
        let mut rec = mk_skill("OpenBMB/MiniCPM", 42);
        rec.key = "skill:OpenBMB/MiniCPM/minicpm5-deploy-mlx".to_string();
        rec.content = "Deploy MiniCPM5 with MLX".to_string();
        rec.tags.extend([
            "path:skills/minicpm5-deploy-mlx/SKILL.md".to_string(),
            "lint:warn:1".to_string(),
            "vendor:community".to_string(),
            "git_commit:abc123".to_string(),
            "git_branch:minicpm5".to_string(),
            "git_origin:https://github.com/OpenBMB/MiniCPM.git".to_string(),
            "git_src:OpenBMB/MiniCPM".to_string(),
            "risk:apple_mlx".to_string(),
            "risk:model_download".to_string(),
            "license:Apache-2.0".to_string(),
            "compatibility:macos".to_string(),
            "tools:Bash,Read".to_string(),
        ]);

        let payload = skill_show_json_payload(&rec);
        assert_eq!(payload["source"], "OpenBMB/MiniCPM");
        assert_eq!(
            payload["path"],
            "skills/minicpm5-deploy-mlx/SKILL.md"
        );
        assert_eq!(payload["lint"], "warn:1");
        assert_eq!(payload["vendor"], "community");
        assert_eq!(payload["license"], "Apache-2.0");
        assert_eq!(payload["compatibility"], "macos");
        assert_eq!(payload["tools"], serde_json::json!(["Bash", "Read"]));
        assert_eq!(payload["git"]["commit"], "abc123");
        assert_eq!(payload["git"]["branch"], "minicpm5");
        assert_eq!(
            payload["risks"],
            serde_json::json!(["apple_mlx", "model_download"])
        );
    }

    #[test]
    fn strip_skills_prefix_handles_layouts() {
        assert_eq!(strip_skills_prefix("skills/xlsx"), "xlsx");
        assert_eq!(strip_skills_prefix(".claude/skills/foo"), "foo");
        // agentskills.io standard layout (used by warpdotdev/oz-skills,
        // sst/opencode, RooCodeInc/Roo-Code, etc.).
        assert_eq!(
            strip_skills_prefix(".agents/skills/mcp-builder"),
            "mcp-builder"
        );
        assert_eq!(strip_skills_prefix("a/b/c"), "a/b/c");
        // only strips a SINGLE leading segment — nested skills inside
        // skills/ keep their internal structure.
        assert_eq!(strip_skills_prefix("skills/api/REFERENCE"), "api/REFERENCE");
    }

    #[test]
    fn lint_does_not_fire_on_markdown_tables() {
        // Common false-positive shape: a markdown table cell containing the
        // word "Bash" or "sh" should not trigger pipe-to-shell.
        let body = "| Tool | Description |\n| Bash Tool | run shell |\n| Read | read files |\n";
        let f = lint_body(body);
        assert!(
            !f.iter().any(|x| x.rule == "pipe-to-shell"),
            "false positive: {:?}",
            f
        );
    }

    #[test]
    fn lint_flags_dangerous_rm() {
        let body = "rm -rf / # don't actually do this";
        let f = lint_body(body);
        assert!(f
            .iter()
            .any(|x| x.rule == "dangerous-rm" && x.sev == LintSev::Danger));
    }

    #[test]
    fn lint_clean_summary() {
        assert_eq!(lint_summary_tag(&[]), "lint:clean");
    }

    // ── agentskills.io spec compliance ──────────────────────────────────

    #[test]
    fn frontmatter_allowed_tools_space_separated_per_spec() {
        // Spec form: bare string, space-separated.
        let body = "---\nname: x\nallowed-tools: Bash(git:*) Bash(jq:*) Read\n---\nbody";
        let (fm, _) = split_frontmatter(body);
        assert_eq!(fm.allowed_tools, vec!["Bash(git:*)", "Bash(jq:*)", "Read"]);
    }

    #[test]
    fn frontmatter_allowed_tools_bracketed_list_still_works() {
        // Legacy form must keep working — we tolerate both.
        let body = "---\nname: x\nallowed-tools: [Read, Grep, Bash]\n---\nbody";
        let (fm, _) = split_frontmatter(body);
        assert_eq!(fm.allowed_tools, vec!["Read", "Grep", "Bash"]);
    }

    #[test]
    fn frontmatter_preserves_license_and_compatibility() {
        let body = "---\n\
            name: x\n\
            description: d\n\
            license: MIT\n\
            compatibility: Requires Python 3.14+ and uv\n\
            ---\nbody";
        let (fm, _) = split_frontmatter(body);
        assert_eq!(fm.license.as_deref(), Some("MIT"));
        assert_eq!(
            fm.compatibility.as_deref(),
            Some("Requires Python 3.14+ and uv")
        );
    }

    #[test]
    fn classify_vendor_known_orgs() {
        assert_eq!(classify_vendor("anthropics/skills"), "vendor-curated");
        assert_eq!(classify_vendor("warpdotdev/oz-skills"), "vendor-curated");
        assert_eq!(classify_vendor("openai/codex"), "vendor-curated");
        // Case-insensitive match for orgs like `OpenHands` whose canonical
        // capitalization differs from typical lowercase convention.
        assert_eq!(classify_vendor("openhands/some-repo"), "vendor-curated");
    }

    #[test]
    fn classify_vendor_unknown_is_community() {
        assert_eq!(classify_vendor("alirezarezvani/claude-skills"), "community");
        assert_eq!(classify_vendor("Jeffallan/claude-skills"), "community");
        assert_eq!(classify_vendor("random-user/random-repo"), "community");
        // Single-segment src (local dir test) — falls back to community.
        assert_eq!(classify_vendor("oz-skills-test"), "community");
    }

    #[test]
    fn build_record_emits_vendor_and_optional_tags() {
        let sf = SkillFile {
            src: "warpdotdev/oz-skills".to_string(),
            name: "mcp-builder".to_string(),
            rel_path: PathBuf::from(".agents/skills/mcp-builder/SKILL.md"),
            body: "---\n\
                name: mcp-builder\n\
                description: Build high-quality MCP servers.\n\
                license: Complete terms in LICENSE.txt\n\
                ---\n\
                # Body\n"
                .to_string(),
            source_tags: vec![
                "git_src:warpdotdev/oz-skills".to_string(),
                "git_commit:abc123".to_string(),
            ],
        };
        let rec = build_record(&sf).expect("record");
        let has = |needle: &str| rec.tags.iter().any(|t| t == needle);
        assert!(has("skill"));
        assert!(has("src:warpdotdev/oz-skills"));
        assert!(has("git_src:warpdotdev/oz-skills"));
        assert!(has("git_commit:abc123"));
        assert!(has("vendor:vendor-curated"), "tags={:?}", rec.tags);
        assert!(
            has("license:Complete terms in LICENSE.txt"),
            "license must be preserved; tags={:?}",
            rec.tags
        );
        assert!(rec.content.starts_with("Build high-quality MCP servers."));
    }

    #[test]
    fn build_record_community_vendor_classification() {
        let sf = SkillFile {
            src: "alirezarezvani/claude-skills".to_string(),
            name: "marketing".to_string(),
            rel_path: PathBuf::from("skills/marketing/SKILL.md"),
            body: "---\nname: marketing\ndescription: d\n---\nbody".to_string(),
            source_tags: Vec::new(),
        };
        let rec = build_record(&sf).expect("record");
        assert!(
            rec.tags.iter().any(|t| t == "vendor:community"),
            "tags={:?}",
            rec.tags
        );
    }

    #[test]
    fn build_record_tags_operational_risk() {
        let sf = SkillFile {
            src: "OpenBMB/MiniCPM".to_string(),
            name: "minicpm5-deploy-mlx".to_string(),
            rel_path: PathBuf::from("skills/minicpm5-deploy-mlx/SKILL.md"),
            body: "---\n\
                name: minicpm5-deploy-mlx\n\
                description: Run MiniCPM5 on Apple Silicon with MLX.\n\
                ---\n\
                pip install \"mlx-lm>=0.31\"\n\
                mlx_lm.server --model openbmb/MiniCPM5-1B-MLX --port 8000\n"
                .to_string(),
            source_tags: Vec::new(),
        };
        let rec = build_record(&sf).expect("record");
        let has = |needle: &str| rec.tags.iter().any(|t| t == needle);
        assert!(has("risk:pip_install"), "tags={:?}", rec.tags);
        assert!(has("risk:server_start"), "tags={:?}", rec.tags);
        assert!(has("risk:model_download"), "tags={:?}", rec.tags);
        assert!(has("risk:apple_mlx"), "tags={:?}", rec.tags);
    }
}
