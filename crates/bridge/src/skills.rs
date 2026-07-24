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
//! - `skills sources` — summarize indexed sources, provenance, lint, and risk.
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

use ab_store::{
    MemoryEdge, MemoryListSort, MemoryRecord, MemorySearchHit, SqliteStore, StateStore,
};
use anyhow::{anyhow, bail, Context, Result};
use serde::Deserialize;
use sha2::{Digest, Sha256};
use std::collections::{BTreeMap, BTreeSet};
use std::path::{Path, PathBuf};
use std::process::{Command, Stdio};
use std::time::SystemTime;

const ROUTE_STRONG_SEMANTIC_COSINE: f32 = 0.50;

/// Explicit document-format requests deserve a small deterministic routing
/// preference over broad document-related semantic matches. This only affects
/// the final candidate order; it never installs or executes a skill.
const ROUTE_FILE_FORMATS: &[&str] = &["pdf", "docx", "xlsx", "pptx"];

/// Checked-in, observation-only quality cases. The evaluator never feeds these
/// labels back into retrieval or ranking.
const ROUTE_QUALITY_CORPUS: &str =
    include_str!("../../../docs/design/fixtures/skills-route-quality-query-cases-v0.json");

/// Checked-in post-retrieval labels for an observation-only provenance shadow.
const ROUTE_PROVENANCE_CORPUS: &str =
    include_str!("../../../docs/design/fixtures/skills-route-provenance-query-cases-v0.json");

/// Independent paired holdout used only to gate owner review of a possible
/// provenance preference. It is never consumed by runtime routing.
const ROUTE_PROVENANCE_HOLDOUT: &str =
    include_str!("../../../docs/design/fixtures/skills-route-provenance-holdout-v1.json");

/// The legacy aggregate was indexed before Git provenance existed. These
/// declarations make that absence visible without inventing an upstream.
const LEGACY_SOURCE_RECOVERY_MANIFEST: &str =
    include_str!("../../../docs/design/fixtures/skills-legacy-source-recovery-v0.json");

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
    let result = index_resolved_repo(&repo_dir, &src_id, verbose).await;
    if owned_clone {
        let _ = std::fs::remove_dir_all(&repo_dir);
    }
    result
}

async fn index_resolved_repo(repo_dir: &Path, src_id: &str, verbose: bool) -> Result<usize> {
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
/// Walks all `kind=skill` records, collects distinct remote `src:` tag values,
/// and re-runs indexing for each. When indexed records carry git provenance,
/// refresh preserves `git_origin` and `git_branch` instead of reconstructing a
/// default-branch URL from `src:` alone. Local-path sources are reported and
/// skipped — they need a manual `skills index`.
///
/// When `prune` is set, after re-indexing each GitHub source we delete
/// records with that `src:` tag whose `updated_at` is still older than the
/// refresh's start time — those are skills that disappeared upstream. A
/// failed re-index for a source skips pruning of that source (don't
/// destroy data when we don't have a fresh authoritative state).
pub async fn run_refresh(
    verbose: bool,
    src_filter: Option<&str>,
    checkout_ref_override: Option<&str>,
    prune: bool,
    dry_run: bool,
    json: bool,
) -> Result<()> {
    if json && !dry_run {
        bail!("`skills refresh --json` is currently only supported with `--dry-run`");
    }
    if checkout_ref_override.is_some() && src_filter.is_none() {
        bail!("`skills refresh --ref` requires `--src <source>` to avoid changing every source");
    }
    let store = open_store().await?;
    let rows = store
        .list_memories(Some("skill"), MemoryListSort::Recent, u32::MAX)
        .await
        .context("list_memories failed")?;
    if rows.is_empty() {
        eprintln!("[skills] none indexed yet — try `agent-bridge skills seed`");
        return Ok(());
    }
    let mut remote_plans: BTreeMap<String, RemoteIndexPlan> = BTreeMap::new();
    let mut local_srcs: BTreeSet<String> = BTreeSet::new();
    for r in &rows {
        let Some(src) = tag_value(&r.tags, "src:") else {
            continue;
        };
        if src_filter.is_some_and(|filter| filter != src) {
            continue;
        }
        if is_remote_src(&src) {
            let mut plan = remote_index_plan(&src, &r.tags);
            if src_filter == Some(src.as_str()) {
                if let Some(checkout_ref) = checkout_ref_override {
                    plan.checkout_ref = Some(checkout_ref.to_string());
                }
            }
            if let Some(existing) = remote_plans.get(&src) {
                if existing != &plan && verbose {
                    eprintln!(
                        "[skills]   source {} has mixed git provenance; keeping first plan {:?}, ignoring {:?}",
                        src, existing, plan
                    );
                }
            } else {
                remote_plans.insert(src.clone(), plan);
            }
        } else {
            local_srcs.insert(src);
        }
    }
    if dry_run {
        if json {
            println!(
                "{}",
                serde_json::to_string_pretty(&refresh_dry_run_payload(
                    &remote_plans,
                    &local_srcs,
                    rows.len(),
                    prune,
                    src_filter,
                    checkout_ref_override,
                ))?
            );
        } else {
            print_refresh_header(
                remote_plans.len(),
                local_srcs.len(),
                rows.len(),
                prune,
                dry_run,
            );
            if !local_srcs.is_empty() {
                print_refresh_local_sources(&local_srcs);
            }
            print_refresh_dry_run(&remote_plans, prune);
        }
        return Ok(());
    }
    print_refresh_header(
        remote_plans.len(),
        local_srcs.len(),
        rows.len(),
        prune,
        dry_run,
    );
    if !local_srcs.is_empty() && verbose {
        print_refresh_local_sources(&local_srcs);
    }
    let started_at = SystemTime::now()
        .duration_since(SystemTime::UNIX_EPOCH)
        .map(|d| d.as_secs() as i64)
        .unwrap_or(0);
    let mut total = 0usize;
    let mut failed: Vec<String> = Vec::new();
    let mut pruned_total = 0usize;
    for (src, plan) in &remote_plans {
        match run_index_remote_plan(plan, verbose).await {
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

fn print_refresh_header(
    remote_count: usize,
    local_count: usize,
    record_count: usize,
    prune: bool,
    dry_run: bool,
) {
    eprintln!(
        "[skills] refresh: {} remote source(s), {} local source(s) skipped, {} record(s) total{}",
        remote_count,
        local_count,
        record_count,
        refresh_mode_suffix(prune, dry_run)
    );
}

fn print_refresh_local_sources(local_srcs: &BTreeSet<String>) {
    eprintln!("[skills]   local sources (re-run `skills index <path>` manually):");
    for s in local_srcs {
        eprintln!("[skills]     - {}", s);
    }
}

fn refresh_mode_suffix(prune: bool, dry_run: bool) -> &'static str {
    match (prune, dry_run) {
        (true, true) => " (prune ON, dry-run)",
        (true, false) => " (prune ON)",
        (false, true) => " (dry-run)",
        (false, false) => "",
    }
}

fn refresh_dry_run_payload(
    remote_plans: &BTreeMap<String, RemoteIndexPlan>,
    local_srcs: &BTreeSet<String>,
    record_count: usize,
    prune: bool,
    src_filter: Option<&str>,
    checkout_ref_override: Option<&str>,
) -> serde_json::Value {
    serde_json::json!({
        "dry_run": true,
        "mutates": false,
        "total_records": record_count,
        "source_filter": src_filter,
        "checkout_ref_override": checkout_ref_override,
        "remote_source_count": remote_plans.len(),
        "local_source_count": local_srcs.len(),
        "prune_requested": prune,
        "actions": {
            "clone_repos": false,
            "write_memories": false,
            "prune_stale_records": false,
        },
        "remote_sources": remote_plans
            .iter()
            .map(|(src, plan)| {
                serde_json::json!({
                    "source": src,
                    "url": &plan.url,
                    "checkout_ref": &plan.checkout_ref,
                })
            })
            .collect::<Vec<_>>(),
        "local_sources_skipped": local_srcs.iter().cloned().collect::<Vec<_>>(),
        "prune_note": if prune {
            Some("stale deletes are only evaluated after a real successful source refresh")
        } else {
            None
        },
    })
}

fn print_refresh_dry_run(remote_plans: &BTreeMap<String, RemoteIndexPlan>, prune: bool) {
    eprintln!("[skills] dry-run: no repos cloned, no memories written, no stale records pruned");
    if remote_plans.is_empty() {
        return;
    }
    eprintln!("[skills]   remote sources to refresh:");
    for (src, plan) in remote_plans {
        eprintln!(
            "[skills]     - {}  url={}  ref={}",
            src,
            plan.url,
            plan.checkout_ref.as_deref().unwrap_or("<default>")
        );
    }
    if prune {
        eprintln!(
            "[skills]   prune preview: stale deletes are only evaluated after a real successful refresh"
        );
    }
}

#[derive(Debug, Clone, PartialEq, Eq)]
struct RemoteIndexPlan {
    src: String,
    url: String,
    checkout_ref: Option<String>,
}

fn remote_index_plan(src: &str, tags: &[String]) -> RemoteIndexPlan {
    RemoteIndexPlan {
        src: src.to_string(),
        url: tag_value(tags, "git_origin:").unwrap_or_else(|| src_to_clone_url(src)),
        checkout_ref: tag_value(tags, "git_branch:"),
    }
}

async fn run_index_remote_plan(plan: &RemoteIndexPlan, verbose: bool) -> Result<usize> {
    let clone_dir = clone_shallow(
        &plan.url,
        &plan.src.replace('/', "_"),
        plan.checkout_ref.as_deref(),
    )?;
    let result = index_resolved_repo(&clone_dir, &plan.src, verbose).await;
    let _ = std::fs::remove_dir_all(&clone_dir);
    result
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

/// Route a task to a small set of indexed skills.
///
/// This is intentionally not an installer. It is a context-budgeting surface:
/// keep Codex's active startup skills small, then retrieve only the few
/// procedures relevant to the current task from Agent-Bridge memory.
pub async fn run_route(query: &str, limit: usize, body_chars: usize, json: bool) -> Result<()> {
    let query = query.trim();
    if query.is_empty() {
        bail!("query is required");
    }
    let limit = limit.clamp(1, 50);
    let store = open_store().await?;
    let payload = route_payload_for_store(&store, query, limit, body_chars).await?;
    if json {
        println!("{}", serde_json::to_string_pretty(&payload)?);
    } else {
        print_route_plan(&payload);
    }
    Ok(())
}

/// Compare normal candidates with the subset that has reproducible upstream
/// provenance. This is evidence only: normal ordering and policy stay intact.
pub async fn run_route_audit(query: &str, limit: usize, json: bool) -> Result<()> {
    let query = query.trim();
    if query.is_empty() {
        bail!("query is required");
    }
    let limit = limit.clamp(1, 50);
    let store = open_store_read_only().await?;
    let candidates =
        route_skill_entries_strict(&store, query, route_candidate_limit(limit)).await?;
    let payload = route_provenance_shadow_payload(query, &candidates, limit);
    if json {
        println!("{}", serde_json::to_string_pretty(&payload)?);
    } else {
        println!(
            "[route-audit] candidate_pool={} baseline_verified={} verified_available={} verdict={}",
            payload["candidate_pool"],
            payload["baseline"]["provenance_counts"]["verified"],
            payload["verified_only"]["count"],
            payload["verdict"],
        );
    }
    Ok(())
}

/// Show the strict retrieval lanes behind a route decision without changing
/// ranking, provenance, admission, memory, or execution authority.
pub async fn run_route_diagnose(query: &str, limit: usize, json: bool) -> Result<()> {
    let query = query.trim();
    if query.is_empty() {
        bail!("query is required");
    }
    let limit = limit.clamp(1, 20);
    let store = open_store_read_only().await?;
    let overfetch = route_retrieval_limit(limit);
    let tag_filter = vec!["skill".to_string()];
    let formats = requested_file_formats(query);

    // Keep the evaluator's strict error behavior: diagnostics must not turn an
    // unhealthy search lane into a plausible empty result.
    let semantic = store
        .memory_search_semantic(query, overfetch, 0.25_f32)
        .await
        .context("route diagnostic semantic search failed")?;
    let primary_fts = store
        .memory_search(query, &tag_filter, overfetch)
        .await
        .context("route diagnostic FTS search failed")?;
    let (relaxed_query, relaxed_fts) = if primary_fts.is_empty() {
        if let Some(relaxed) = relaxed_fts_query(query) {
            let hits = store
                .memory_search(&relaxed, &tag_filter, overfetch)
                .await
                .context("route diagnostic relaxed FTS search failed")?;
            (Some(relaxed), Some(hits))
        } else {
            (None, None)
        }
    } else {
        (None, None)
    };
    let mut format_lanes = Vec::new();
    for format in &formats {
        let hits = store
            .memory_search(format, &tag_filter, route_candidate_limit(limit) as u32)
            .await
            .context("route diagnostic format FTS search failed")?;
        format_lanes.push((*format, hits));
    }

    let mut merged_fts = primary_fts.clone();
    if let Some(relaxed) = &relaxed_fts {
        merged_fts = relaxed.clone();
    }
    for (_, hits) in &format_lanes {
        merged_fts.extend(hits.clone());
    }
    // Match the runtime boundary exactly: feedback only observes the routed
    // top-k candidates, never the wider merge set.
    let pre_feedback: Vec<MemorySearchHit> = route_prioritize_explicit_format(
        query,
        route_merge_hits(semantic.clone(), merged_fts, route_candidate_limit(limit)),
    )
    .into_iter()
    .take(limit)
    .collect();
    let feedback = route_feedback_for_hits_strict(&store, &pre_feedback).await?;
    let final_hits = route_prioritize_explicit_format_routed(
        query,
        route_apply_feedback(pre_feedback.clone(), &feedback),
    );

    let payload = serde_json::json!({
        "schema_version": "skills-route-diagnostic-v0",
        "mode": "offline_observation_only",
        "query": query,
        "limit": limit,
        "policy_change": "none",
        "lanes": {
            "semantic": route_diagnostic_hits_json(&semantic, limit),
            "fts_primary": route_diagnostic_hits_json(&primary_fts, limit),
            "fts_relaxed": {
                "query": relaxed_query,
                "hits": relaxed_fts.as_ref().map(|hits| route_diagnostic_hits_json(hits, limit)),
            },
            "format": format_lanes.iter().map(|(format, hits)| serde_json::json!({
                "format": format,
                "hits": route_diagnostic_hits_json(hits, limit),
            })).collect::<Vec<_>>(),
            "merged_pre_feedback": route_diagnostic_hits_json(&pre_feedback, limit),
            "final": final_hits.iter().take(limit).map(|hit| serde_json::json!({
                "key": hit.hit.record.key,
                "score": hit.score,
                "feedback_score": hit.feedback.score,
                "feedback_count": hit.feedback.count,
            })).collect::<Vec<_>>(),
        },
    });
    if json {
        println!("{}", serde_json::to_string_pretty(&payload)?);
    } else {
        println!(
            "[route-diagnose] semantic={} fts={} relaxed={} format_lanes={} final={}",
            payload["lanes"]["semantic"].as_array().map_or(0, Vec::len),
            payload["lanes"]["fts_primary"]
                .as_array()
                .map_or(0, Vec::len),
            payload["lanes"]["fts_relaxed"]["hits"]
                .as_array()
                .map_or(0, Vec::len),
            formats.len(),
            payload["lanes"]["final"].as_array().map_or(0, Vec::len),
        );
        for hit in payload["lanes"]["final"].as_array().into_iter().flatten() {
            println!("- {} score={}", hit["key"], hit["score"]);
        }
    }
    Ok(())
}

fn route_diagnostic_hits_json(hits: &[MemorySearchHit], limit: usize) -> Vec<serde_json::Value> {
    hits.iter()
        .filter(|hit| is_skill_hit(hit))
        .take(limit)
        .map(|hit| {
            serde_json::json!({
                "key": hit.record.key,
                "score": hit.score,
                "cosine": hit.cosine,
            })
        })
        .collect()
}

/// Evaluate the current router against a small checked-in bilingual corpus.
/// This is an offline observation surface: it never changes retrieval order,
/// source provenance, memory, or Skill execution authority.
pub async fn run_route_eval(limit: usize, json: bool) -> Result<()> {
    let corpus = parse_route_quality_corpus()?;
    let limit = limit.clamp(1, 20);
    let store = open_store_read_only().await?;
    let mut cases = Vec::with_capacity(corpus.cases.len());
    let mut required = 0usize;
    let mut required_matched = 0usize;
    let mut expected_gaps = 0usize;
    let mut resolved_gaps = 0usize;

    for case in corpus.cases {
        let hits = route_skill_entries_strict(&store, &case.query, limit).await?;
        let returned_keys: Vec<String> =
            hits.iter().map(|hit| hit.hit.record.key.clone()).collect();
        let matched_keys: Vec<String> = case
            .expected_keys
            .iter()
            .filter(|key| returned_keys.iter().any(|returned| returned == *key))
            .cloned()
            .collect();
        let outcome = match case.expectation.as_str() {
            "must_match" => {
                required += 1;
                if !matched_keys.is_empty() {
                    required_matched += 1;
                }
                route_quality_outcome(&case.expectation, !matched_keys.is_empty())?
            }
            "known_gap" => {
                expected_gaps += 1;
                if !matched_keys.is_empty() {
                    resolved_gaps += 1;
                }
                route_quality_outcome(&case.expectation, !matched_keys.is_empty())?
            }
            other => bail!("unsupported route quality expectation {other:?}"),
        };
        cases.push(serde_json::json!({
            "id": case.id,
            "pair_id": case.pair_id,
            "language": case.language,
            "query": case.query,
            "expectation": case.expectation,
            "expected_keys": case.expected_keys,
            "returned_keys": returned_keys,
            "matched_keys": matched_keys,
            "outcome": outcome,
        }));
    }

    let payload = serde_json::json!({
        "schema_version": corpus.schema_version,
        "mode": "offline_observation_only",
        "limit": limit,
        "summary": {
            "required_cases": required,
            "required_matched": required_matched,
            "required_recall_at_k": if required == 0 { 0.0 } else { required_matched as f64 / required as f64 },
            "known_gap_cases": expected_gaps,
            "known_gap_cases_now_matched": resolved_gaps,
            "policy_change": "none",
        },
        "cases": cases,
    });
    if json {
        println!("{}", serde_json::to_string_pretty(&payload)?);
    } else {
        let summary = &payload["summary"];
        println!(
            "[route-eval] required recall@{limit}: {}/{}; known gaps: {} ({} now matched); policy change: none",
            summary["required_matched"], summary["required_cases"], summary["known_gap_cases"], summary["known_gap_cases_now_matched"],
        );
        for case in payload["cases"].as_array().into_iter().flatten() {
            println!(
                "- {} [{}]: {}",
                case["id"], case["language"], case["outcome"]
            );
        }
    }
    Ok(())
}

/// Run a checked-in provenance corpus after retrieval. The labels are not
/// consulted by the runtime router and cannot alter recommendation order.
pub async fn run_route_provenance_eval(
    fixture: Option<&Path>,
    limit: usize,
    json: bool,
) -> Result<()> {
    let corpus = parse_route_provenance_corpus(fixture)?;

    let limit = limit.clamp(1, 50);
    let store = open_store_read_only().await?;
    let mut rows = Vec::with_capacity(corpus.cases.len());
    let mut required = 0usize;
    let mut required_verified_hits = 0usize;
    let mut insufficient = 0usize;
    let mut fill_risks = 0usize;

    for case in corpus.cases {
        let candidates =
            route_skill_entries_strict(&store, &case.query, route_candidate_limit(limit)).await?;
        let baseline = candidates.iter().take(limit).collect::<Vec<_>>();
        let verified = candidates
            .iter()
            .filter(|hit| skill_provenance(&hit.hit.record.tags) == SkillProvenance::Verified)
            .take(limit)
            .collect::<Vec<_>>();
        let baseline_hit = baseline
            .iter()
            .any(|hit| case.relevant_skill_keys.contains(&hit.hit.record.key));
        let verified_hit = verified
            .iter()
            .any(|hit| case.relevant_skill_keys.contains(&hit.hit.record.key));
        let fill_risk = case.relevant_skill_keys.is_empty() && !verified.is_empty();

        match case.verified_coverage.as_str() {
            "required" => {
                required += 1;
                if verified_hit {
                    required_verified_hits += 1;
                }
            }
            "insufficient_expected" => insufficient += 1,
            other => bail!(
                "case {} has unsupported verified_coverage {other:?}",
                case.id
            ),
        }
        if fill_risk {
            fill_risks += 1;
        }
        rows.push(serde_json::json!({
            "id": case.id,
            "query": case.query,
            "expected_verified_coverage": case.verified_coverage,
            "baseline_relevant_hit": baseline_hit,
            "verified_relevant_hit": verified_hit,
            "verified_fill_risk": fill_risk,
            "baseline_keys": baseline.iter().map(|hit| &hit.hit.record.key).collect::<Vec<_>>(),
            "verified_keys": verified.iter().map(|hit| &hit.hit.record.key).collect::<Vec<_>>(),
        }));
    }

    let required_recall = required_verified_hits as f64 / required.max(1) as f64;
    let verdict = if required_recall >= 0.8 && fill_risks == 0 {
        "READY_FOR_OWNER_REVIEW"
    } else {
        "INCONCLUSIVE_NO_POLICY_CHANGE"
    };
    let payload = serde_json::json!({
        "schema_version": "skills-route-provenance-shadow-eval-v0",
        "mode": "offline_observation_only",
        "fixture": fixture.map(|path| path.display().to_string()).unwrap_or_else(|| "embedded".to_string()),
        "limit": limit,
        "summary": {
            "cases": rows.len(),
            "required_cases": required,
            "required_verified_recall_at_k": required_recall,
            "insufficient_expected_cases": insufficient,
            "verified_fill_risk_cases": fill_risks,
        },
        "verdict": verdict,
        "cases": rows,
        "boundary": {
            "read_only": true,
            "changes_route_policy": false,
            "labels_used_after_retrieval": true,
        },
    });
    if json {
        println!("{}", serde_json::to_string_pretty(&payload)?);
    } else {
        println!("[route-provenance-eval] verdict={verdict} required_verified_recall@{limit}={required_recall:.3} fill_risk_cases={fill_risks}");
    }
    Ok(())
}

/// Measure the provenance shadow against an independent bilingual holdout.
/// A passing verdict only permits owner review; it never changes runtime
/// retrieval, ranking, source admission, installation, or execution.
pub async fn run_route_provenance_gate(limit: usize, json: bool) -> Result<()> {
    let corpus = parse_route_provenance_holdout()?;
    let limit = limit.clamp(1, 50);
    let store = open_store_read_only().await?;
    let mut rows = Vec::with_capacity(corpus.cases.len());
    let mut required = 0usize;
    let mut baseline_required_hits = 0usize;
    let mut verified_required_hits = 0usize;
    let mut insufficient = 0usize;
    let mut fill_risks = 0usize;
    let mut baseline_to_verified_regressions = 0usize;

    for case in corpus.cases {
        let candidates =
            route_skill_entries_strict(&store, &case.query, route_candidate_limit(limit)).await?;
        let baseline = candidates.iter().take(limit).collect::<Vec<_>>();
        let verified = candidates
            .iter()
            .filter(|hit| skill_provenance(&hit.hit.record.tags) == SkillProvenance::Verified)
            .take(limit)
            .collect::<Vec<_>>();
        let baseline_hit = baseline
            .iter()
            .any(|hit| case.relevant_skill_keys.contains(&hit.hit.record.key));
        let verified_hit = verified
            .iter()
            .any(|hit| case.relevant_skill_keys.contains(&hit.hit.record.key));
        let fill_risk = case.relevant_skill_keys.is_empty() && !verified.is_empty();

        match case.verified_coverage.as_str() {
            "required" => {
                required += 1;
                if baseline_hit {
                    baseline_required_hits += 1;
                }
                if verified_hit {
                    verified_required_hits += 1;
                }
                if baseline_hit && !verified_hit {
                    baseline_to_verified_regressions += 1;
                }
            }
            "insufficient_expected" => insufficient += 1,
            other => bail!(
                "holdout case {} has unsupported verified_coverage {other:?}",
                case.id
            ),
        }
        if fill_risk {
            fill_risks += 1;
        }
        rows.push(serde_json::json!({
            "id": case.id,
            "pair_id": case.pair_id,
            "language": case.language,
            "expected_verified_coverage": case.verified_coverage,
            "baseline_relevant_hit": baseline_hit,
            "verified_relevant_hit": verified_hit,
            "verified_fill_risk": fill_risk,
            "baseline_keys": baseline.iter().map(|hit| &hit.hit.record.key).collect::<Vec<_>>(),
            "verified_keys": verified.iter().map(|hit| &hit.hit.record.key).collect::<Vec<_>>(),
        }));
    }

    let baseline_recall = baseline_required_hits as f64 / required.max(1) as f64;
    let verified_recall = verified_required_hits as f64 / required.max(1) as f64;
    let verdict = if verified_recall >= corpus.min_verified_recall
        && verified_recall + f64::EPSILON >= baseline_recall
        && baseline_to_verified_regressions == 0
        && fill_risks == 0
    {
        "READY_FOR_OWNER_REVIEW"
    } else {
        "INCONCLUSIVE_NO_POLICY_CHANGE"
    };
    let payload = serde_json::json!({
        "schema_version": corpus.schema_version,
        "mode": "offline_observation_only",
        "limit": limit,
        "summary": {
            "cases": rows.len(),
            "required_cases": required,
            "insufficient_expected_cases": insufficient,
            "baseline_required_recall_at_k": baseline_recall,
            "verified_required_recall_at_k": verified_recall,
            "baseline_to_verified_regression_cases": baseline_to_verified_regressions,
            "verified_fill_risk_cases": fill_risks,
        },
        "gate": {
            "min_cases": corpus.min_cases,
            "min_verified_recall": corpus.min_verified_recall,
            "requires_verified_recall_not_below_baseline": true,
            "requires_zero_fill_risk": true,
            "automatic_policy_change": false,
        },
        "verdict": verdict,
        "cases": rows,
    });
    if json {
        println!("{}", serde_json::to_string_pretty(&payload)?);
    } else {
        println!(
            "[route-provenance-gate] verdict={verdict} baseline_recall@{limit}={baseline_recall:.3} verified_recall@{limit}={verified_recall:.3} regressions={baseline_to_verified_regressions} fill_risk_cases={fill_risks}"
        );
    }
    Ok(())
}

fn route_quality_outcome(expectation: &str, matched: bool) -> Result<&'static str> {
    match (expectation, matched) {
        ("must_match", true) => Ok("matched"),
        ("must_match", false) => Ok("missed"),
        ("known_gap", true) => Ok("now_matched"),
        ("known_gap", false) => Ok("still_missing"),
        (other, _) => bail!("unsupported route quality expectation {other:?}"),
    }
}

#[derive(Debug, Deserialize)]
struct RouteQualityCorpus {
    schema_version: String,
    cases: Vec<RouteQualityCase>,
}

#[derive(Debug, Deserialize)]
struct RouteQualityCase {
    id: String,
    pair_id: String,
    language: String,
    query: String,
    expectation: String,
    expected_keys: Vec<String>,
}

#[derive(Debug, Deserialize)]
struct RouteProvenanceCorpus {
    schema: String,
    cases: Vec<RouteProvenanceCase>,
}

#[derive(Debug, Deserialize)]
struct RouteProvenanceCase {
    id: String,
    query: String,
    relevant_skill_keys: BTreeSet<String>,
    verified_coverage: String,
}

#[derive(Debug, Deserialize)]
struct RouteProvenanceHoldout {
    schema_version: String,
    min_cases: usize,
    min_verified_recall: f64,
    cases: Vec<RouteProvenanceHoldoutCase>,
}

#[derive(Debug, Deserialize)]
struct RouteProvenanceHoldoutCase {
    id: String,
    pair_id: String,
    language: String,
    query: String,
    relevant_skill_keys: BTreeSet<String>,
    verified_coverage: String,
}

fn parse_route_quality_corpus() -> Result<RouteQualityCorpus> {
    let corpus: RouteQualityCorpus = serde_json::from_str(ROUTE_QUALITY_CORPUS)
        .context("parse embedded Skills route quality corpus")?;
    if corpus.schema_version != "skills-route-quality-v0" || corpus.cases.is_empty() {
        bail!("invalid Skills route quality corpus")
    }
    Ok(corpus)
}

fn parse_route_provenance_corpus(fixture: Option<&Path>) -> Result<RouteProvenanceCorpus> {
    let raw = match fixture {
        Some(path) => std::fs::read_to_string(path)
            .with_context(|| format!("read fixture {}", path.display()))?,
        None => ROUTE_PROVENANCE_CORPUS.to_string(),
    };
    let corpus: RouteProvenanceCorpus =
        serde_json::from_str(&raw).context("parse Skills provenance evaluation corpus")?;
    if corpus.schema != "agent_bridge.skills_route.provenance_query_cases.v0"
        || corpus.cases.is_empty()
    {
        bail!("invalid Skills provenance evaluation fixture")
    }
    Ok(corpus)
}

fn parse_route_provenance_holdout() -> Result<RouteProvenanceHoldout> {
    let corpus: RouteProvenanceHoldout = serde_json::from_str(ROUTE_PROVENANCE_HOLDOUT)
        .context("parse Skills provenance holdout")?;
    if corpus.schema_version != "skills-route-provenance-holdout-v1"
        || corpus.min_cases < 20
        || corpus.cases.len() < corpus.min_cases
        || !(0.0..=1.0).contains(&corpus.min_verified_recall)
    {
        bail!("invalid Skills provenance holdout")
    }
    let mut pairs = BTreeMap::<&str, Vec<&RouteProvenanceHoldoutCase>>::new();
    for case in &corpus.cases {
        pairs.entry(&case.pair_id).or_default().push(case);
    }
    if pairs.values().any(|pair| {
        pair.len() != 2
            || pair
                .iter()
                .map(|case| case.language.as_str())
                .collect::<BTreeSet<_>>()
                != BTreeSet::from(["en", "zh"])
            || pair[0].relevant_skill_keys != pair[1].relevant_skill_keys
            || pair[0].verified_coverage != pair[1].verified_coverage
    }) {
        bail!("Skills provenance holdout must contain paired English and Chinese cases")
    }
    Ok(corpus)
}

fn route_provenance_shadow_payload(
    query: &str,
    candidates: &[RoutedSkillHit],
    limit: usize,
) -> serde_json::Value {
    let baseline = candidates.iter().take(limit).collect::<Vec<_>>();
    let verified = candidates
        .iter()
        .filter(|hit| skill_provenance(&hit.hit.record.tags) == SkillProvenance::Verified)
        .take(limit)
        .collect::<Vec<_>>();
    let count_by_provenance = |hits: &[&RoutedSkillHit]| {
        let mut counts = BTreeMap::<String, usize>::new();
        for hit in hits {
            bump(
                &mut counts,
                skill_provenance(&hit.hit.record.tags).as_str().to_string(),
            );
        }
        counts
    };
    let baseline_counts = count_by_provenance(&baseline);
    let candidate_refs = candidates.iter().collect::<Vec<_>>();
    let candidate_counts = count_by_provenance(&candidate_refs);
    let baseline_items = baseline
        .iter()
        .enumerate()
        .map(|(index, hit)| route_item_json(index + 1, hit, 0))
        .collect::<Vec<_>>();
    let verified_items = verified
        .iter()
        .enumerate()
        .map(|(index, hit)| route_item_json(index + 1, hit, 0))
        .collect::<Vec<_>>();

    serde_json::json!({
        "query": query,
        "candidate_pool": candidates.len(),
        "baseline": {
            "count": baseline_items.len(),
            "provenance_counts": baseline_counts,
            "skills": baseline_items,
        },
        "verified_only": {
            "count": verified_items.len(),
            "coverage_of_requested_limit": verified_items.len() as f64 / limit as f64,
            "coverage_of_candidate_pool": candidate_counts.get("verified").copied().unwrap_or(0) as f64 / candidates.len().max(1) as f64,
            "skills": verified_items,
        },
        "candidate_pool_provenance": candidate_counts,
        "verdict": "INCONCLUSIVE_NO_POLICY_CHANGE",
        "reason": "Provenance is a reproducibility signal, not a relevance label. Review this report across an explicit query corpus before changing recommendation order.",
        "actions": {"network": false, "write_memory": false, "reindex": false, "install": false, "execute_skill": false, "changes_route_policy": false},
    })
}

/// Build the JSON payload used by both `agent-bridge skills route` and MCP.
pub async fn route_payload_for_store(
    store: &dyn StateStore,
    query: &str,
    limit: usize,
    body_chars: usize,
) -> Result<serde_json::Value> {
    let query = query.trim();
    if query.is_empty() {
        bail!("query is required");
    }
    let limit = limit.clamp(1, 50);
    let hits = route_skill_entries(store, query, limit).await?;
    Ok(route_payload(query, &hits, body_chars))
}

async fn route_skill_entries(
    store: &dyn StateStore,
    query: &str,
    limit: usize,
) -> Result<Vec<RoutedSkillHit>> {
    let hits = route_skill_hits(store, query, limit).await?;
    let feedback = route_feedback_for_hits(store, &hits).await;
    Ok(route_prioritize_explicit_format_routed(
        query,
        route_apply_feedback(hits, &feedback),
    ))
}

/// Equivalent retrieval path for the offline evaluator. Unlike the runtime
/// router, it propagates backend failures so an unhealthy index cannot be
/// misreported as a routing-quality regression.
async fn route_skill_entries_strict(
    store: &dyn StateStore,
    query: &str,
    limit: usize,
) -> Result<Vec<RoutedSkillHit>> {
    let hits = route_skill_hits_strict(store, query, limit).await?;
    let feedback = route_feedback_for_hits_strict(store, &hits).await?;
    Ok(route_prioritize_explicit_format_routed(
        query,
        route_apply_feedback(hits, &feedback),
    ))
}

/// Retrieve the small top-k skill set for runtime context loading.
pub async fn route_skill_hits(
    store: &dyn StateStore,
    query: &str,
    limit: usize,
) -> Result<Vec<MemorySearchHit>> {
    let overfetch = route_retrieval_limit(limit);
    let formats = requested_file_formats(query);
    let semantic_hits = store
        .memory_search_semantic(query, overfetch, 0.25_f32)
        .await
        .unwrap_or_default();
    let tag_filter = vec!["skill".to_string()];
    let mut fts_hits = store
        .memory_search(query, &tag_filter, overfetch)
        .await
        .unwrap_or_default();
    if fts_hits.is_empty() {
        if let Some(relaxed) = relaxed_fts_query(query) {
            fts_hits = store
                .memory_search(&relaxed, &tag_filter, overfetch)
                .await
                .unwrap_or_default();
        }
    }
    // A multi-word FTS query can omit the exact format skill even though the
    // user explicitly requested that format. Fetch those tiny lexical lanes
    // separately, then let the path-based preference below rank them.
    for format in &formats {
        let format_hits = store
            .memory_search(format, &tag_filter, route_candidate_limit(limit) as u32)
            .await
            .unwrap_or_default();
        fts_hits.extend(format_hits);
    }
    let candidates = route_merge_hits(semantic_hits, fts_hits, route_candidate_limit(limit));
    Ok(route_prioritize_explicit_format(query, candidates)
        .into_iter()
        .take(limit)
        .collect())
}

async fn route_skill_hits_strict(
    store: &dyn StateStore,
    query: &str,
    limit: usize,
) -> Result<Vec<MemorySearchHit>> {
    let overfetch = route_retrieval_limit(limit);
    let formats = requested_file_formats(query);
    let semantic_hits = store
        .memory_search_semantic(query, overfetch, 0.25_f32)
        .await
        .context("route evaluation semantic search failed")?;
    let tag_filter = vec!["skill".to_string()];
    let mut fts_hits = store
        .memory_search(query, &tag_filter, overfetch)
        .await
        .context("route evaluation FTS search failed")?;
    if fts_hits.is_empty() {
        if let Some(relaxed) = relaxed_fts_query(query) {
            fts_hits = store
                .memory_search(&relaxed, &tag_filter, overfetch)
                .await
                .context("route evaluation relaxed FTS search failed")?;
        }
    }
    for format in &formats {
        let format_hits = store
            .memory_search(format, &tag_filter, route_candidate_limit(limit) as u32)
            .await
            .context("route evaluation format FTS search failed")?;
        fts_hits.extend(format_hits);
    }
    let candidates = route_merge_hits(semantic_hits, fts_hits, route_candidate_limit(limit));
    Ok(route_prioritize_explicit_format(query, candidates)
        .into_iter()
        .take(limit)
        .collect())
}

fn route_retrieval_limit(limit: usize) -> u32 {
    ((limit as u32).saturating_mul(20)).clamp(100, 500)
}

fn route_candidate_limit(limit: usize) -> usize {
    limit.saturating_mul(10).clamp(20, 100)
}

fn route_merge_hits(
    semantic_hits: Vec<MemorySearchHit>,
    fts_hits: Vec<MemorySearchHit>,
    limit: usize,
) -> Vec<MemorySearchHit> {
    let mut strong_semantic = Vec::new();
    let mut weak_semantic = Vec::new();
    for hit in semantic_hits.into_iter().filter(is_skill_hit) {
        if hit.cosine.unwrap_or(0.0) >= ROUTE_STRONG_SEMANTIC_COSINE {
            strong_semantic.push(hit);
        } else {
            weak_semantic.push(hit);
        }
    }

    let mut out = Vec::new();
    let mut seen = BTreeSet::new();
    for hit in strong_semantic
        .into_iter()
        .chain(fts_hits.into_iter().filter(is_skill_hit))
        .chain(weak_semantic.into_iter())
    {
        if seen.insert(hit.record.key.clone()) {
            out.push(hit);
            if out.len() >= limit {
                break;
            }
        }
    }
    out
}

fn is_skill_hit(hit: &MemorySearchHit) -> bool {
    hit.record.tags.iter().any(|t| t == "skill")
}

fn route_prioritize_explicit_format(
    query: &str,
    mut hits: Vec<MemorySearchHit>,
) -> Vec<MemorySearchHit> {
    let formats = requested_file_formats(query);
    if formats.is_empty() {
        return hits;
    }
    hits.sort_by(|a, b| {
        skill_format_match_score(&b.record, &formats)
            .cmp(&skill_format_match_score(&a.record, &formats))
    });
    hits
}

fn route_prioritize_explicit_format_routed(
    query: &str,
    mut hits: Vec<RoutedSkillHit>,
) -> Vec<RoutedSkillHit> {
    let formats = requested_file_formats(query);
    if formats.is_empty() {
        return hits;
    }
    hits.sort_by(|a, b| {
        skill_format_match_score(&b.hit.record, &formats)
            .cmp(&skill_format_match_score(&a.hit.record, &formats))
    });
    hits
}

fn requested_file_formats(query: &str) -> Vec<&'static str> {
    ROUTE_FILE_FORMATS
        .iter()
        .copied()
        .filter(|format| {
            query
                .split(|c: char| !c.is_ascii_alphanumeric())
                .any(|token| token.eq_ignore_ascii_case(format))
        })
        .collect()
}

fn skill_format_match_score(record: &MemoryRecord, formats: &[&str]) -> u8 {
    let Some(path) = tag_value(&record.tags, "path:") else {
        return 0;
    };
    let Some(skill_name) = path.rsplit('/').nth(1) else {
        return 0;
    };
    formats
        .iter()
        .map(|format| {
            if skill_name.eq_ignore_ascii_case(format) {
                2
            } else if skill_name
                .split(|c: char| !c.is_ascii_alphanumeric())
                .any(|token| token.eq_ignore_ascii_case(format))
            {
                1
            } else {
                0
            }
        })
        .max()
        .unwrap_or(0)
}

#[derive(Debug, Clone, Copy, Default, PartialEq)]
struct SkillRouteFeedback {
    score: f64,
    count: usize,
    positive_count: usize,
    negative_count: usize,
}

#[derive(Debug, Clone)]
struct RoutedSkillHit {
    hit: MemorySearchHit,
    score: f64,
    feedback: SkillRouteFeedback,
}

async fn route_feedback_for_hits(
    store: &dyn StateStore,
    hits: &[MemorySearchHit],
) -> BTreeMap<String, SkillRouteFeedback> {
    let mut out = BTreeMap::new();
    for hit in hits {
        let key = &hit.record.key;
        let edges = store.memory_neighbors(key).await.unwrap_or_default();
        let stats = route_feedback_stats_from_edges(key, &edges);
        if stats.count > 0 {
            out.insert(key.clone(), stats);
        }
    }
    out
}

async fn route_feedback_for_hits_strict(
    store: &dyn StateStore,
    hits: &[MemorySearchHit],
) -> Result<BTreeMap<String, SkillRouteFeedback>> {
    let mut out = BTreeMap::new();
    for hit in hits {
        let key = &hit.record.key;
        let edges = store
            .memory_neighbors(key)
            .await
            .with_context(|| format!("route strict feedback lookup failed for {key}"))?;
        let stats = route_feedback_stats_from_edges(key, &edges);
        if stats.count > 0 {
            out.insert(key.clone(), stats);
        }
    }
    Ok(out)
}

fn route_feedback_stats_from_edges(skill_key: &str, edges: &[MemoryEdge]) -> SkillRouteFeedback {
    let mut stats = SkillRouteFeedback::default();
    for edge in edges {
        if edge.to_key != skill_key || !edge.from_key.starts_with("skill_feedback:") {
            continue;
        }
        match edge.edge_type.as_str() {
            "applied_skill" => {
                stats.count += 1;
                stats.positive_count += 1;
                stats.score += (edge.weight - 1.0).clamp(0.05, 0.4);
            }
            "skill_feedback" => {
                stats.count += 1;
                stats.negative_count += 1;
                stats.score -= (0.5 - edge.weight).clamp(0.05, 0.3);
            }
            _ => {}
        }
    }
    stats.score = stats.score.clamp(-0.75, 0.75);
    stats
}

fn route_apply_feedback(
    hits: Vec<MemorySearchHit>,
    feedback: &BTreeMap<String, SkillRouteFeedback>,
) -> Vec<RoutedSkillHit> {
    let mut routed: Vec<(usize, RoutedSkillHit)> = hits
        .into_iter()
        .enumerate()
        .map(|(idx, hit)| {
            let fb = feedback.get(&hit.record.key).copied().unwrap_or_default();
            let score = hit.score + fb.score;
            (
                idx,
                RoutedSkillHit {
                    hit,
                    score,
                    feedback: fb,
                },
            )
        })
        .collect();
    routed.sort_by(|(idx_a, a), (idx_b, b)| {
        b.score
            .partial_cmp(&a.score)
            .unwrap_or(std::cmp::Ordering::Equal)
            .then_with(|| idx_a.cmp(idx_b))
    });
    routed.into_iter().map(|(_, hit)| hit).collect()
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum SkillFeedbackOutcome {
    Used,
    Helpful,
    NotHelpful,
    Ignored,
}

impl SkillFeedbackOutcome {
    pub fn parse(raw: &str) -> Result<Self> {
        match raw.trim().to_ascii_lowercase().as_str() {
            "used" | "use" => Ok(Self::Used),
            "helpful" | "success" | "accepted" => Ok(Self::Helpful),
            "not_helpful" | "not-helpful" | "unhelpful" | "bad" => Ok(Self::NotHelpful),
            "ignored" | "skip" | "skipped" => Ok(Self::Ignored),
            other => bail!(
                "unknown skill feedback outcome {other:?}; expected used|helpful|not-helpful|ignored"
            ),
        }
    }

    fn as_str(self) -> &'static str {
        match self {
            Self::Used => "used",
            Self::Helpful => "helpful",
            Self::NotHelpful => "not_helpful",
            Self::Ignored => "ignored",
        }
    }

    fn edge_type(self) -> &'static str {
        match self {
            Self::Used | Self::Helpful => "applied_skill",
            Self::NotHelpful | Self::Ignored => "skill_feedback",
        }
    }

    fn edge_weight(self) -> f64 {
        match self {
            Self::Helpful => 1.4,
            Self::Used => 1.1,
            Self::NotHelpful => 0.3,
            Self::Ignored => 0.2,
        }
    }

    fn importance(self) -> f64 {
        match self {
            Self::Helpful => 0.65,
            Self::Used => 0.55,
            Self::NotHelpful => 0.45,
            Self::Ignored => 0.30,
        }
    }
}

pub async fn run_feedback(
    skill_key: &str,
    query: &str,
    outcome: &str,
    note: Option<&str>,
    related_keys: &[String],
    json: bool,
) -> Result<()> {
    let store = open_store().await?;
    let payload =
        record_skill_feedback_for_store(&store, skill_key, query, outcome, note, related_keys)
            .await?;
    if json {
        println!("{}", serde_json::to_string_pretty(&payload)?);
    } else {
        println!(
            "[skills] recorded feedback {} -> {} ({})",
            payload
                .get("feedback_key")
                .and_then(|v| v.as_str())
                .unwrap_or("?"),
            payload
                .get("skill_key")
                .and_then(|v| v.as_str())
                .unwrap_or("?"),
            payload
                .get("outcome")
                .and_then(|v| v.as_str())
                .unwrap_or("?")
        );
    }
    Ok(())
}

pub async fn record_skill_feedback_for_store(
    store: &dyn StateStore,
    skill_key: &str,
    query: &str,
    outcome: &str,
    note: Option<&str>,
    related_keys: &[String],
) -> Result<serde_json::Value> {
    let skill_key = skill_key.trim();
    if skill_key.is_empty() {
        bail!("skill_key is required");
    }
    let query = query.trim();
    if query.is_empty() {
        bail!("query is required");
    }
    let outcome = SkillFeedbackOutcome::parse(outcome)?;
    let skill = store
        .memory_get(skill_key)
        .await?
        .ok_or_else(|| anyhow!("skill memory not found: {skill_key}"))?;
    if !skill.tags.iter().any(|t| t == "skill") {
        bail!("memory is not indexed as a skill: {skill_key}");
    }

    let rec = build_skill_feedback_record(skill_key, query, outcome, note, related_keys);
    let feedback_key = rec.key.clone();
    store.memory_save(&rec).await?;
    store
        .memory_link(
            &feedback_key,
            skill_key,
            outcome.edge_type(),
            outcome.edge_weight(),
        )
        .await?;

    let mut linked_related = Vec::new();
    for key in related_keys
        .iter()
        .map(|k| k.trim())
        .filter(|k| !k.is_empty() && *k != skill_key)
    {
        if store.memory_get(key).await?.is_some() {
            store
                .memory_link(&feedback_key, key, "context_for_skill", 0.8)
                .await?;
            linked_related.push(key.to_string());
        }
    }

    Ok(serde_json::json!({
        "status": "ok",
        "feedback_key": feedback_key,
        "skill_key": skill_key,
        "outcome": outcome.as_str(),
        "edge": {
            "from_key": feedback_key,
            "to_key": skill_key,
            "edge_type": outcome.edge_type(),
            "weight": outcome.edge_weight(),
        },
        "linked_related_keys": linked_related,
        "hint": "future skills_route calls can use these skill_feedback memories and graph edges as ranking evidence",
    }))
}

fn skill_feedback_key(
    skill_key: &str,
    query: &str,
    outcome: SkillFeedbackOutcome,
    note: Option<&str>,
) -> String {
    let mut hasher = Sha256::new();
    hasher.update(skill_key.trim().as_bytes());
    hasher.update(b"\0");
    hasher.update(query.trim().as_bytes());
    hasher.update(b"\0");
    hasher.update(outcome.as_str().as_bytes());
    hasher.update(b"\0");
    hasher.update(note.unwrap_or("").trim().as_bytes());
    let digest = hasher.finalize();
    let mut hex = String::with_capacity(16);
    for byte in digest.iter().take(8) {
        hex.push_str(&format!("{byte:02x}"));
    }
    format!("skill_feedback:{hex}")
}

fn build_skill_feedback_record(
    skill_key: &str,
    query: &str,
    outcome: SkillFeedbackOutcome,
    note: Option<&str>,
    related_keys: &[String],
) -> MemoryRecord {
    let skill_key = skill_key.trim();
    let query = query.trim();
    let note = note.map(str::trim).filter(|s| !s.is_empty());
    let key = skill_feedback_key(skill_key, query, outcome, note);
    let mut related = vec![skill_key.to_string()];
    for rel in related_keys.iter().map(|k| k.trim()) {
        if !rel.is_empty() && rel != skill_key && !related.iter().any(|k| k == rel) {
            related.push(rel.to_string());
        }
    }
    let mut content = format!(
        "skill feedback\nskill: {skill_key}\nquery: {query}\noutcome: {}\n",
        outcome.as_str()
    );
    if let Some(note) = note {
        content.push_str(&format!("note: {note}\n"));
    }

    let now = unix_now();
    MemoryRecord {
        key,
        kind: "skill_feedback".to_string(),
        content,
        tags: vec![
            "skill_feedback".to_string(),
            format!("skill_feedback:{}", outcome.as_str()),
            format!("skill_key:{skill_key}"),
            "src:skills_route".to_string(),
        ],
        related_keys: related,
        scope: Some("global".to_string()),
        created_at: now,
        updated_at: now,
        last_accessed_at: now,
        access_count: 0,
        importance: outcome.importance(),
        status: "active".to_string(),
        trigger_pattern: None,
        superseded_by: None,
    }
}

fn route_payload(query: &str, hits: &[RoutedSkillHit], body_chars: usize) -> serde_json::Value {
    let skills: Vec<_> = hits
        .iter()
        .enumerate()
        .map(|(idx, h)| route_item_json(idx + 1, h, body_chars))
        .collect();
    serde_json::json!({
        "query": query,
        "count": skills.len(),
        "skills": skills,
        "policy": {
            "startup_prompt": "keep only curated/router skills active",
            "runtime": "retrieve top-k indexed skill memories, then load full bodies only when needed",
            "full_body_command": "agent-bridge skills show <key>",
            "note": "skill routing is external procedural memory, not model-weight internalization"
        },
        "hint": if skills.is_empty() {
            "no indexed skills match; run `agent-bridge skills index <path-or-url>` or `agent-bridge skills seed`"
        } else {
            "use the top clean/high-confidence match first; review warn/danger lint and risk tags before following commands"
        }
    })
}

fn route_item_json(rank: usize, routed: &RoutedSkillHit, body_chars: usize) -> serde_json::Value {
    let hit = &routed.hit;
    let rec = &hit.record;
    let lint = tag_value(&rec.tags, "lint:").unwrap_or_else(|| "?".to_string());
    let risks = tag_values(&rec.tags, "risk:");
    let tools = tag_value(&rec.tags, "tools:")
        .map(|s| split_csv_tag(&s))
        .unwrap_or_default();
    let action = if lint.starts_with("danger") {
        "review_before_use"
    } else if lint.starts_with("warn") || !risks.is_empty() {
        "review_risk_then_use"
    } else {
        "safe_to_load_if_relevant"
    };
    let mut obj = serde_json::json!({
        "rank": rank,
        "key": rec.key,
        "score": routed.score,
        "confidence": route_confidence(route_confidence_score(hit)),
        "summary": first_line(&rec.content),
        "source": tag_value(&rec.tags, "src:"),
        "path": tag_value(&rec.tags, "path:"),
        "provenance": skill_provenance(&rec.tags).as_str(),
        "lint": lint,
        "risks": risks,
        "tools": tools,
        "retrieval": if hit.cosine.is_some() { "semantic" } else { "fts" },
        "action": action,
        "show": format!("agent-bridge skills show {}", rec.key),
        "show_json": format!("agent-bridge skills show {} --json", rec.key),
    });
    // Surface declared DIALS (authoring convention; see docs/skill-authoring-spec.md)
    // so a caller can see a skill's tunable knobs + baselines before loading the
    // full body. Omitted entirely for skills that don't opt into the convention,
    // keeping the route payload lean for the common case.
    let dials = parse_dials(&rec.content);
    if !dials.is_empty() {
        obj["dials"] = serde_json::json!(dials
            .iter()
            .map(|(name, value)| serde_json::json!({ "name": name, "value": value }))
            .collect::<Vec<_>>());
    }
    if routed.feedback.count > 0 {
        obj["feedback_score"] = serde_json::json!(routed.feedback.score);
        obj["feedback_count"] = serde_json::json!(routed.feedback.count);
        obj["positive_feedback_count"] = serde_json::json!(routed.feedback.positive_count);
        obj["negative_feedback_count"] = serde_json::json!(routed.feedback.negative_count);
    }
    if let Some(cosine) = hit.cosine {
        obj["cosine"] = serde_json::json!(cosine);
    }
    if body_chars > 0 {
        obj["body_preview"] = serde_json::json!(truncate_chars(&rec.content, body_chars));
    }
    obj
}

fn print_route_plan(payload: &serde_json::Value) {
    println!(
        "[route] query: {}",
        payload.get("query").and_then(|v| v.as_str()).unwrap_or("")
    );
    let skills = payload
        .get("skills")
        .and_then(|v| v.as_array())
        .cloned()
        .unwrap_or_default();
    if skills.is_empty() {
        println!(
            "[route] {}",
            payload
                .get("hint")
                .and_then(|v| v.as_str())
                .unwrap_or("no matches")
        );
        return;
    }
    println!(
        "[route] load at most {} skill(s); fetch full bodies only when the task will use them.",
        skills.len()
    );
    for item in skills {
        let rank = item.get("rank").and_then(|v| v.as_u64()).unwrap_or(0);
        let key = item.get("key").and_then(|v| v.as_str()).unwrap_or("");
        let score = item.get("score").and_then(|v| v.as_f64()).unwrap_or(0.0);
        let confidence = item
            .get("confidence")
            .and_then(|v| v.as_str())
            .unwrap_or("unknown");
        let lint = item.get("lint").and_then(|v| v.as_str()).unwrap_or("?");
        let risks = item
            .get("risks")
            .and_then(|v| v.as_array())
            .map(|v| {
                v.iter()
                    .filter_map(|x| x.as_str())
                    .collect::<Vec<_>>()
                    .join(",")
            })
            .filter(|s| !s.is_empty())
            .unwrap_or_else(|| "none".to_string());
        let action = item
            .get("action")
            .and_then(|v| v.as_str())
            .unwrap_or("review");
        let summary = item.get("summary").and_then(|v| v.as_str()).unwrap_or("");
        println!(
            "{rank}. {key}\n   score={score:.3} confidence={confidence} lint={lint} risks={risks} action={action}\n   {summary}"
        );
        if let Some(show) = item.get("show").and_then(|v| v.as_str()) {
            println!("   show: {show}");
        }
        if let Some(body) = item.get("body_preview").and_then(|v| v.as_str()) {
            println!("   preview: {}", body.replace('\n', " "));
        }
    }
}

fn route_confidence_score(hit: &MemorySearchHit) -> f64 {
    hit.cosine.map(f64::from).unwrap_or(hit.score)
}

fn route_confidence(score: f64) -> &'static str {
    if score >= 0.70 {
        "high"
    } else if score >= 0.50 {
        "medium"
    } else {
        "low"
    }
}

fn relaxed_fts_query(query: &str) -> Option<String> {
    const STOPWORDS: &[&str] = &[
        "and", "or", "the", "for", "with", "without", "into", "from", "that", "this", "when",
        "then", "than", "all", "not", "use", "using",
    ];
    let mut seen = BTreeSet::new();
    let mut terms = Vec::new();
    for raw in query.split(|c: char| !c.is_ascii_alphanumeric()) {
        let token = raw.trim().to_ascii_lowercase();
        if token.len() < 3 || STOPWORDS.contains(&token.as_str()) {
            continue;
        }
        if seen.insert(token.clone()) {
            terms.push(token);
        }
        if terms.len() >= 12 {
            break;
        }
    }
    if terms.is_empty() {
        None
    } else {
        Some(terms.join(" OR "))
    }
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

/// Persist a source-level review record. This consumes operator-reviewed
/// evidence and never changes routing or execution authority.
pub async fn run_admit(
    source: &str,
    spdx: &str,
    verdict: &str,
    evidence_url: Option<&str>,
    note: Option<&str>,
) -> Result<()> {
    let verdict = SourceAdmissionVerdict::parse(verdict)?;
    let spdx = spdx.trim();
    if spdx.is_empty()
        || !spdx
            .chars()
            .all(|c| c.is_ascii_alphanumeric() || matches!(c, '.' | '-' | '+'))
    {
        bail!("SPDX identifier must contain only ASCII letters, digits, '.', '-', or '+'");
    }
    let store = open_store().await?;
    let rows = store
        .list_memories(Some("skill"), MemoryListSort::Recent, u32::MAX)
        .await
        .context("list_memories failed")?;
    let inventory = skill_source_inventory(&rows, &BTreeMap::new());
    let summary = inventory
        .iter()
        .find(|item| item.source == source)
        .ok_or_else(|| anyhow!("no indexed Skills found for source {:?}", source))?;
    if summary.git_origins.len() != 1 || summary.git_commits.len() != 1 {
        bail!(
            "source {:?} needs exactly one origin and commit before admission",
            source
        );
    }
    let now = unix_now();
    let mut tags = vec![
        "skill_source_admission".to_string(),
        format!("src:{}", source),
        format!("admission:{}", verdict.as_str()),
        format!("spdx:{}", spdx),
        format!("git_origin:{}", summary.git_origins.iter().next().unwrap()),
        format!("git_commit:{}", summary.git_commits.iter().next().unwrap()),
    ];
    if let Some(branch) = summary.git_branches.iter().next() {
        tags.push(format!("git_branch:{}", branch));
    }
    if let Some(url) = evidence_url.filter(|url| !url.trim().is_empty()) {
        tags.push(format!("evidence_url:{}", tag_safe_value(url.trim())));
    }
    let content = format!(
        "Source admission for {source}.\n\nVerdict: {}\nSPDX: {spdx}\nEvidence: {}\nNote: {}",
        verdict.as_str(),
        evidence_url.unwrap_or("not provided"),
        note.unwrap_or("not provided").trim()
    );
    let record = MemoryRecord {
        key: format!("skill_source_admission:{source}"),
        kind: "skill_source_admission".to_string(),
        content,
        tags,
        related_keys: Vec::new(),
        scope: Some("global".to_string()),
        created_at: now,
        updated_at: now,
        last_accessed_at: now,
        access_count: 0,
        importance: 0.7,
        status: "active".to_string(),
        trigger_pattern: None,
        superseded_by: None,
    };
    store
        .memory_save(&record)
        .await
        .context("save source admission")?;
    println!(
        "[skills] admitted source={} verdict={} spdx={} commit={}",
        source,
        verdict.as_str(),
        spdx,
        summary.git_commits.iter().next().unwrap()
    );
    Ok(())
}

/// Summarize indexed skill sources without touching upstream repos.
pub async fn run_sources(json: bool, limit: usize) -> Result<()> {
    let store = open_store().await?;
    let rows = store
        .list_memories(Some("skill"), MemoryListSort::Recent, u32::MAX)
        .await
        .context("list_memories failed")?;
    let admission_rows = store
        .list_memories(
            Some("skill_source_admission"),
            MemoryListSort::Recent,
            u32::MAX,
        )
        .await
        .context("list source admissions failed")?;
    let admissions = source_admission_inventory(&admission_rows);
    let mut sources = skill_source_inventory(&rows, &admissions);
    attach_legacy_source_recovery(&mut sources)?;
    let returned = if limit == 0 {
        sources.len()
    } else {
        sources.len().min(limit)
    };

    if json {
        let payload = serde_json::json!({
            "total_skills": rows.len(),
            "total_sources": sources.len(),
            "returned": returned,
            "limit": if limit == 0 { serde_json::Value::Null } else { serde_json::json!(limit) },
            "sources": sources
                .iter()
                .take(returned)
                .map(SkillSourceSummary::to_json)
                .collect::<Vec<_>>(),
        });
        println!("{}", serde_json::to_string_pretty(&payload)?);
        return Ok(());
    }

    if sources.is_empty() {
        eprintln!("[skills] none indexed yet — try `agent-bridge skills seed`");
        return Ok(());
    }
    println!(
        "[skills] sources: {} source(s), {} skill(s)",
        sources.len(),
        rows.len()
    );
    for s in sources.iter().take(returned) {
        println!(
            "- {}  skills={} refreshable={} latest_updated_at={}",
            s.source, s.count, s.refreshable, s.latest_updated_at
        );
        println!(
            "  git: origin={} branch={} commit={}",
            display_set(&s.git_origins),
            display_set(&s.git_branches),
            display_set(&s.git_commits)
        );
        println!("  lint: {}", display_counts(&s.lint));
        println!("  vendor: {}", display_counts(&s.vendor));
        println!("  provenance: {}", display_counts(&s.provenance));
        if let Some(admission) = &s.admission {
            let freshness = s.admission_freshness.unwrap_or(AdmissionFreshness::Unknown);
            println!(
                "  admission: verdict={} spdx={} freshness={} reviewed_at={}",
                admission.verdict.as_str(),
                admission.spdx,
                freshness.as_str(),
                admission.reviewed_at
            );
            if freshness == AdmissionFreshness::Stale {
                println!("  action: re-review this source before relying on its admission");
            }
        }
        if let Some(recovery) = &s.recovery {
            println!(
                "  recovery: status={} provenance_change=none",
                recovery.status
            );
            println!("  recovery policy: {}", recovery.policy);
        }
        if !s.risks.is_empty() {
            println!("  risks: {}", display_counts(&s.risks));
        }
    }
    if returned < sources.len() {
        println!(
            "... {} more hidden; re-run with `--limit 0` for all sources",
            sources.len() - returned
        );
    }
    Ok(())
}

/// Batch-audit indexed skills by provenance, lint, and operational risk.
pub async fn run_audit(
    json: bool,
    src: Option<&str>,
    risks: &[String],
    lint: Option<&str>,
    vendor: Option<&str>,
    provenance: Option<&str>,
    limit: usize,
) -> Result<()> {
    let store = open_store().await?;
    let rows = store
        .list_memories(Some("skill"), MemoryListSort::Recent, u32::MAX)
        .await
        .context("list_memories failed")?;
    let filters = SkillAuditFilters::new(src, risks, lint, vendor, provenance)?;
    let matched: Vec<MemoryRecord> = rows
        .iter()
        .filter(|r| filters.matches(r))
        .cloned()
        .collect();
    let admission_rows = store
        .list_memories(
            Some("skill_source_admission"),
            MemoryListSort::Recent,
            u32::MAX,
        )
        .await
        .context("list source admissions failed")?;
    let admissions = source_admission_inventory(&admission_rows);
    let sources = skill_source_inventory(&rows, &admissions);
    let source_index: BTreeMap<&str, &SkillSourceSummary> = sources
        .iter()
        .map(|source| (source.source.as_str(), source))
        .collect();
    let summary = skill_audit_summary(&matched);
    let returned = if limit == 0 {
        matched.len()
    } else {
        matched.len().min(limit)
    };

    if json {
        let items = matched
            .iter()
            .take(returned)
            .map(|record| {
                let source = tag_value(&record.tags, "src:").unwrap_or_default();
                skill_audit_item_json(record, source_index.get(source.as_str()).copied())
            })
            .collect::<Vec<_>>();
        let payload = serde_json::json!({
            "total": rows.len(),
            "matched": matched.len(),
            "returned": returned,
            "limit": if limit == 0 { serde_json::Value::Null } else { serde_json::json!(limit) },
            "filters": filters.to_json(),
            "summary": summary.to_json(),
            "items": items,
        });
        println!("{}", serde_json::to_string_pretty(&payload)?);
        return Ok(());
    }

    println!(
        "[skills] audit: {} matched / {} indexed{}",
        matched.len(),
        rows.len(),
        filters.human_suffix()
    );
    print_count_map("sources", &summary.sources);
    print_count_map("lint", &summary.lint);
    print_count_map("vendor", &summary.vendor);
    print_count_map("provenance", &summary.provenance);
    print_count_map("risks", &summary.risks);
    if matched.is_empty() {
        return Ok(());
    }
    println!("\nrecords (showing {}):", returned);
    for r in matched.iter().take(returned) {
        let src = tag_value(&r.tags, "src:").unwrap_or_else(|| "?".to_string());
        let lint = tag_value(&r.tags, "lint:").unwrap_or_else(|| "?".to_string());
        let risks = tag_values(&r.tags, "risk:");
        println!(
            "- {}  [src={}, provenance={}, lint={}, risks={}]",
            r.key,
            src,
            skill_provenance(&r.tags).as_str(),
            lint,
            if risks.is_empty() {
                "none".to_string()
            } else {
                risks.join(",")
            }
        );
    }
    if returned < matched.len() {
        println!(
            "... {} more hidden; re-run with `--limit 0` for all records",
            matched.len() - returned
        );
    }
    Ok(())
}

#[derive(Debug, Clone)]
struct SkillAuditFilters {
    src: Option<String>,
    risks: Vec<String>,
    lint: Option<String>,
    vendor: Option<String>,
    provenance: Option<SkillProvenance>,
}

impl SkillAuditFilters {
    fn new(
        src: Option<&str>,
        risks: &[String],
        lint: Option<&str>,
        vendor: Option<&str>,
        provenance: Option<&str>,
    ) -> Result<Self> {
        Ok(Self {
            src: src.map(str::to_string),
            risks: risks
                .iter()
                .map(|r| r.strip_prefix("risk:").unwrap_or(r).to_string())
                .filter(|r| !r.trim().is_empty())
                .collect(),
            lint: lint
                .map(|l| l.strip_prefix("lint:").unwrap_or(l).to_string())
                .filter(|l| !l.trim().is_empty()),
            vendor: vendor
                .map(|v| v.strip_prefix("vendor:").unwrap_or(v).to_string())
                .filter(|v| !v.trim().is_empty()),
            provenance: provenance.map(SkillProvenance::parse).transpose()?,
        })
    }

    fn matches(&self, rec: &MemoryRecord) -> bool {
        if let Some(expected) = &self.src {
            if tag_value(&rec.tags, "src:").as_deref() != Some(expected.as_str()) {
                return false;
            }
        }
        if let Some(expected) = &self.vendor {
            if tag_value(&rec.tags, "vendor:").as_deref() != Some(expected.as_str()) {
                return false;
            }
        }
        if let Some(expected) = &self.lint {
            let actual = tag_value(&rec.tags, "lint:").unwrap_or_default();
            if expected == "warn" || expected == "danger" {
                if !actual.starts_with(expected) {
                    return false;
                }
            } else if actual != *expected {
                return false;
            }
        }
        if let Some(expected) = self.provenance {
            if skill_provenance(&rec.tags) != expected {
                return false;
            }
        }
        let actual_risks: BTreeSet<String> = tag_values(&rec.tags, "risk:").into_iter().collect();
        self.risks.iter().all(|r| actual_risks.contains(r))
    }

    fn human_suffix(&self) -> String {
        let mut parts = Vec::new();
        if let Some(src) = &self.src {
            parts.push(format!("src={src}"));
        }
        if !self.risks.is_empty() {
            parts.push(format!("risk={}", self.risks.join(",")));
        }
        if let Some(lint) = &self.lint {
            parts.push(format!("lint={lint}"));
        }
        if let Some(vendor) = &self.vendor {
            parts.push(format!("vendor={vendor}"));
        }
        if let Some(provenance) = self.provenance {
            parts.push(format!("provenance={}", provenance.as_str()));
        }
        if parts.is_empty() {
            String::new()
        } else {
            format!(" ({})", parts.join(" "))
        }
    }

    fn to_json(&self) -> serde_json::Value {
        serde_json::json!({
            "src": self.src,
            "risks": self.risks,
            "lint": self.lint,
            "vendor": self.vendor,
            "provenance": self.provenance.map(SkillProvenance::as_str),
        })
    }
}

#[derive(Debug, Default)]
struct SkillAuditSummary {
    sources: BTreeMap<String, usize>,
    lint: BTreeMap<String, usize>,
    vendor: BTreeMap<String, usize>,
    provenance: BTreeMap<String, usize>,
    risks: BTreeMap<String, usize>,
}

impl SkillAuditSummary {
    fn to_json(&self) -> serde_json::Value {
        serde_json::json!({
            "sources": self.sources,
            "lint": self.lint,
            "vendor": self.vendor,
            "provenance": self.provenance,
            "risks": self.risks,
        })
    }
}

fn skill_audit_summary(rows: &[MemoryRecord]) -> SkillAuditSummary {
    let mut summary = SkillAuditSummary::default();
    for r in rows {
        bump(
            &mut summary.sources,
            tag_value(&r.tags, "src:").unwrap_or_else(|| "?".to_string()),
        );
        bump(
            &mut summary.lint,
            tag_value(&r.tags, "lint:").unwrap_or_else(|| "?".to_string()),
        );
        bump(
            &mut summary.vendor,
            tag_value(&r.tags, "vendor:").unwrap_or_else(|| "?".to_string()),
        );
        bump(
            &mut summary.provenance,
            skill_provenance(&r.tags).as_str().to_string(),
        );
        for risk in tag_values(&r.tags, "risk:") {
            bump(&mut summary.risks, risk);
        }
    }
    summary
}

fn skill_audit_item_json(
    rec: &MemoryRecord,
    source: Option<&SkillSourceSummary>,
) -> serde_json::Value {
    let mut item = skill_show_json_payload(rec);
    if let Some(obj) = item.as_object_mut() {
        obj.remove("content");
        obj.insert(
            "summary".to_string(),
            serde_json::json!(first_line(&rec.content)),
        );
        obj.insert(
            "source_admission".to_string(),
            source
                .and_then(|source| {
                    source.admission.as_ref().map(|admission| {
                        admission.to_json_with_freshness(
                            source
                                .admission_freshness
                                .unwrap_or(AdmissionFreshness::Unknown),
                        )
                    })
                })
                .unwrap_or(serde_json::Value::Null),
        );
    }
    item
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
enum SourceAdmissionVerdict {
    Approved,
    Quarantined,
    ReviewRequired,
}

impl SourceAdmissionVerdict {
    fn parse(value: &str) -> Result<Self> {
        match value.trim() {
            "approved" => Ok(Self::Approved),
            "quarantined" => Ok(Self::Quarantined),
            "review-required" => Ok(Self::ReviewRequired),
            other => bail!("invalid admission verdict {:?}; expected approved, quarantined, or review-required", other),
        }
    }
    fn as_str(self) -> &'static str {
        match self {
            Self::Approved => "approved",
            Self::Quarantined => "quarantined",
            Self::ReviewRequired => "review-required",
        }
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
enum AdmissionFreshness {
    Current,
    Stale,
    Unknown,
}

impl AdmissionFreshness {
    fn as_str(self) -> &'static str {
        match self {
            Self::Current => "current",
            Self::Stale => "stale",
            Self::Unknown => "unknown",
        }
    }
}

#[derive(Debug, Clone, PartialEq, Eq)]
struct SkillSourceAdmission {
    verdict: SourceAdmissionVerdict,
    spdx: String,
    evidence_url: Option<String>,
    reviewed_at: i64,
    git_origin: Option<String>,
    git_commit: Option<String>,
}

impl SkillSourceAdmission {
    fn to_json_with_freshness(&self, freshness: AdmissionFreshness) -> serde_json::Value {
        serde_json::json!({"verdict": self.verdict.as_str(), "spdx": self.spdx, "freshness": freshness.as_str(), "evidence_url": self.evidence_url, "reviewed_at": self.reviewed_at, "git": {"origin": self.git_origin, "commit": self.git_commit}})
    }
}

fn source_admission_inventory(rows: &[MemoryRecord]) -> BTreeMap<String, SkillSourceAdmission> {
    let mut admissions = BTreeMap::new();
    for record in rows {
        let (Some(source), Some(verdict), Some(spdx)) = (
            tag_value(&record.tags, "src:"),
            tag_value(&record.tags, "admission:"),
            tag_value(&record.tags, "spdx:"),
        ) else {
            continue;
        };
        let Ok(verdict) = SourceAdmissionVerdict::parse(&verdict) else {
            continue;
        };
        let candidate = SkillSourceAdmission {
            verdict,
            spdx,
            evidence_url: tag_value(&record.tags, "evidence_url:"),
            reviewed_at: record.updated_at,
            git_origin: tag_value(&record.tags, "git_origin:"),
            git_commit: tag_value(&record.tags, "git_commit:"),
        };
        if admissions
            .get(&source)
            .is_none_or(|existing: &SkillSourceAdmission| {
                candidate.reviewed_at >= existing.reviewed_at
            })
        {
            admissions.insert(source, candidate);
        }
    }
    admissions
}

#[derive(Debug, Default, Clone, PartialEq, Eq)]
struct SkillSourceSummary {
    source: String,
    count: usize,
    refreshable: bool,
    latest_updated_at: i64,
    git_origins: BTreeSet<String>,
    git_branches: BTreeSet<String>,
    git_commits: BTreeSet<String>,
    lint: BTreeMap<String, usize>,
    vendor: BTreeMap<String, usize>,
    provenance: BTreeMap<String, usize>,
    risks: BTreeMap<String, usize>,
    admission: Option<SkillSourceAdmission>,
    admission_freshness: Option<AdmissionFreshness>,
    recovery: Option<LegacySourceRecovery>,
}

impl SkillSourceSummary {
    fn to_json(&self) -> serde_json::Value {
        serde_json::json!({
            "source": self.source,
            "count": self.count,
            "refreshable": self.refreshable,
            "latest_updated_at": self.latest_updated_at,
            "git": {
                "origins": set_to_json(&self.git_origins),
                "branches": set_to_json(&self.git_branches),
                "commits": set_to_json(&self.git_commits),
            },
            "lint": self.lint,
            "vendor": self.vendor,
            "provenance": self.provenance,
            "risks": self.risks,
            "admission": self.admission.as_ref().map(|admission| {
                admission.to_json_with_freshness(
                    self.admission_freshness.unwrap_or(AdmissionFreshness::Unknown),
                )
            }),
            "recovery": self.recovery.as_ref().map(LegacySourceRecovery::to_json),
        })
    }
}

fn skill_source_inventory(
    rows: &[MemoryRecord],
    admissions: &BTreeMap<String, SkillSourceAdmission>,
) -> Vec<SkillSourceSummary> {
    let mut by_source: BTreeMap<String, SkillSourceSummary> = BTreeMap::new();
    for r in rows {
        let Some(source) = tag_value(&r.tags, "src:") else {
            continue;
        };
        let entry = by_source
            .entry(source.clone())
            .or_insert_with(|| SkillSourceSummary {
                source: source.clone(),
                refreshable: is_remote_src(&source),
                ..SkillSourceSummary::default()
            });
        entry.count += 1;
        entry.latest_updated_at = entry.latest_updated_at.max(r.updated_at);
        if let Some(origin) = tag_value(&r.tags, "git_origin:") {
            entry.git_origins.insert(origin);
        }
        if let Some(branch) = tag_value(&r.tags, "git_branch:") {
            entry.git_branches.insert(branch);
        }
        if let Some(commit) = tag_value(&r.tags, "git_commit:") {
            entry.git_commits.insert(commit);
        }
        bump(
            &mut entry.lint,
            tag_value(&r.tags, "lint:").unwrap_or_else(|| "?".to_string()),
        );
        bump(
            &mut entry.vendor,
            tag_value(&r.tags, "vendor:").unwrap_or_else(|| "?".to_string()),
        );
        bump(
            &mut entry.provenance,
            skill_provenance(&r.tags).as_str().to_string(),
        );
        for risk in tag_values(&r.tags, "risk:") {
            bump(&mut entry.risks, risk);
        }
    }
    for summary in by_source.values_mut() {
        summary.admission = admissions.get(&summary.source).cloned();
        summary.admission_freshness = summary
            .admission
            .as_ref()
            .map(|admission| source_admission_freshness(summary, admission));
    }
    by_source.into_values().collect()
}

fn source_admission_freshness(
    source: &SkillSourceSummary,
    admission: &SkillSourceAdmission,
) -> AdmissionFreshness {
    let (Some(origin), Some(commit)) = (&admission.git_origin, &admission.git_commit) else {
        return AdmissionFreshness::Unknown;
    };
    if source.git_origins.is_empty() || source.git_commits.is_empty() {
        return AdmissionFreshness::Unknown;
    }
    if source.git_origins.len() == 1
        && source.git_commits.len() == 1
        && source.git_origins.contains(origin)
        && source.git_commits.contains(commit)
    {
        AdmissionFreshness::Current
    } else {
        AdmissionFreshness::Stale
    }
}

fn attach_legacy_source_recovery(sources: &mut [SkillSourceSummary]) -> Result<()> {
    let recovery = legacy_source_recovery_inventory()?;
    for summary in sources {
        summary.recovery = recovery.get(&summary.source).cloned();
    }
    Ok(())
}

#[derive(Debug, Clone, PartialEq, Eq, Deserialize)]
struct LegacySourceRecovery {
    source: String,
    status: String,
    evidence_required: String,
    policy: String,
}

impl LegacySourceRecovery {
    fn to_json(&self) -> serde_json::Value {
        serde_json::json!({
            "status": self.status,
            "evidence_required": self.evidence_required,
            "policy": self.policy,
            "provenance_change": "none",
        })
    }
}

#[derive(Debug, Deserialize)]
struct LegacySourceRecoveryManifest {
    schema_version: String,
    sources: Vec<LegacySourceRecovery>,
}

fn legacy_source_recovery_inventory() -> Result<BTreeMap<String, LegacySourceRecovery>> {
    let manifest: LegacySourceRecoveryManifest =
        serde_json::from_str(LEGACY_SOURCE_RECOVERY_MANIFEST)
            .context("parse embedded legacy Skills source recovery manifest")?;
    if manifest.schema_version != "skills-legacy-source-recovery-v0" {
        bail!("invalid legacy Skills source recovery manifest")
    }
    let mut out = BTreeMap::new();
    for entry in manifest.sources {
        if entry.source.trim().is_empty() || entry.status != "unresolved" {
            bail!("invalid legacy Skills source recovery entry")
        }
        if out.insert(entry.source.clone(), entry).is_some() {
            bail!("duplicate legacy Skills source recovery entry")
        }
    }
    Ok(out)
}

fn bump(map: &mut BTreeMap<String, usize>, key: String) {
    *map.entry(key).or_insert(0) += 1;
}

fn print_count_map(label: &str, map: &BTreeMap<String, usize>) {
    if map.is_empty() {
        return;
    }
    println!("{label}:");
    for (k, v) in map {
        println!("  {k}: {v}");
    }
}

fn set_to_json(values: &BTreeSet<String>) -> serde_json::Value {
    serde_json::Value::Array(
        values
            .iter()
            .map(|v| serde_json::Value::String(v.clone()))
            .collect(),
    )
}

fn display_set(values: &BTreeSet<String>) -> String {
    if values.is_empty() {
        "-".to_string()
    } else {
        values.iter().cloned().collect::<Vec<_>>().join(",")
    }
}

fn display_counts(counts: &BTreeMap<String, usize>) -> String {
    if counts.is_empty() {
        "none".to_string()
    } else {
        counts
            .iter()
            .map(|(k, v)| format!("{k}:{v}"))
            .collect::<Vec<_>>()
            .join(",")
    }
}

/// Install an indexed skill into `~/.claude/skills/<name>/` by re-cloning
/// the source repo and copying the original SKILL.md (plus siblings, for
/// canonical-layout skills that ship scripts/data). With `assume_yes`,
/// skips lint/risk/destination confirmation prompts. With `dry_run`, only
/// prints the plan and performs no clone/copy/write.
pub async fn run_install(key: &str, assume_yes: bool, dry_run: bool) -> Result<()> {
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
    let risks = tag_values(&rec.tags, "risk:");
    let approval_risks = install_approval_risks(&risks);
    let clone_plan = install_clone_plan(&src, &rec.tags);
    let dest_name = derive_flat_name(key, &rel);
    let dest_root = claude_skills_dir()?;
    let dest = dest_root.join(&dest_name);

    eprintln!(
        "[install{}] {} → {}",
        if dry_run { " dry-run" } else { "" },
        key,
        dest.display(),
    );
    eprintln!("[install]   source: {}", clone_plan.url);
    if let Some(branch) = &clone_plan.checkout_ref {
        eprintln!("[install]   branch: {}", branch);
    }
    if let Some(commit) = &clone_plan.expected_commit {
        eprintln!("[install]   commit: {}", commit);
    }
    eprintln!("[install]   path:   {}", rel);
    eprintln!("[install]   lint:   {}", lint_tag);
    eprintln!(
        "[install]   risks:  {}",
        if risks.is_empty() {
            "none".to_string()
        } else {
            risks.join(",")
        }
    );
    eprintln!(
        "[install]   dest:   {}",
        if dest.exists() { "exists" } else { "new" }
    );
    if dry_run {
        if lint_requires_approval(&lint_tag) {
            eprintln!("[install]   gate: lint requires --yes for real install");
        }
        if !approval_risks.is_empty() {
            eprintln!(
                "[install]   gate: operational risks require --yes for real install: {}",
                approval_risks.join(",")
            );
        }
        if dest.exists() {
            eprintln!("[install]   gate: existing destination requires --yes for overwrite");
        }
        eprintln!("[install] dry-run complete; no clone/copy/write performed.");
        return Ok(());
    }
    if lint_requires_approval(&lint_tag) && !assume_yes {
        eprintln!("[install]   skill flagged by lint — review SKILL.md before approving.");
        eprintln!("[install]   re-run with `--yes` to install anyway.");
        bail!("aborted: lint flags require explicit --yes");
    }
    if !approval_risks.is_empty() && !assume_yes {
        eprintln!(
            "[install]   operational risk tags require review: {}",
            approval_risks.join(",")
        );
        eprintln!("[install]   re-run with `--yes` to install anyway.");
        bail!("aborted: operational risk tags require explicit --yes");
    }
    if dest.exists() && !assume_yes {
        eprintln!("[install]   destination already exists: {}", dest.display());
        eprintln!("[install]   re-run with `--yes` to overwrite.");
        bail!("aborted: destination exists");
    }

    // Clone, copy, clean up.
    let clone_dir = clone_shallow(
        &clone_plan.url,
        &src.replace('/', "_"),
        clone_plan.checkout_ref.as_deref(),
    )?;
    if let Err(err) = verify_cloned_commit(&clone_dir, clone_plan.expected_commit.as_deref()) {
        let _ = std::fs::remove_dir_all(&clone_dir);
        return Err(err);
    }
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

#[derive(Debug, Clone, PartialEq, Eq)]
struct InstallClonePlan {
    url: String,
    checkout_ref: Option<String>,
    expected_commit: Option<String>,
}

fn install_clone_plan(src: &str, tags: &[String]) -> InstallClonePlan {
    InstallClonePlan {
        url: tag_value(tags, "git_origin:").unwrap_or_else(|| src_to_clone_url(src)),
        checkout_ref: tag_value(tags, "git_branch:"),
        expected_commit: tag_value(tags, "git_commit:"),
    }
}

fn verify_cloned_commit(repo: &Path, expected_commit: Option<&str>) -> Result<()> {
    let Some(expected) = expected_commit else {
        return Ok(());
    };
    let actual = git_output(repo, &["rev-parse", "HEAD"])
        .ok_or_else(|| anyhow!("failed to read cloned repo HEAD for commit verification"))?;
    if !commit_matches_expected(&actual, expected) {
        bail!(
            "cloned repo HEAD {} does not match indexed git_commit {}; re-run `skills index` before installing",
            actual,
            expected
        );
    }
    Ok(())
}

fn commit_matches_expected(actual: &str, expected: &str) -> bool {
    actual == expected || actual.starts_with(expected)
}

fn lint_requires_approval(lint_tag: &str) -> bool {
    let lint_tag = lint_tag.strip_prefix("lint:").unwrap_or(lint_tag);
    lint_tag.starts_with("warn:") || lint_tag.starts_with("danger:")
}

fn install_approval_risks(risks: &[String]) -> Vec<String> {
    const NEEDS_YES: &[&str] = &[
        "checkpoint_write",
        "finetune_write",
        "model_download",
        "network_fetch",
        "pip_install",
        "server_start",
    ];
    risks
        .iter()
        .filter(|r| NEEDS_YES.contains(&r.as_str()))
        .cloned()
        .collect()
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
        println!(
            "{}",
            serde_json::to_string_pretty(&skill_show_json_payload(&rec))?
        );
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
        "provenance": skill_provenance(&rec.tags).as_str(),
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

/// Reproducibility state for an indexed external Skill.
///
/// `verified` means the record has both a clone origin and a commit pin. A
/// branch is useful for refresh but is not sufficient to reproduce content.
/// `partial` retains any incomplete Git metadata without overstating trust;
/// `unknown` covers legacy or local imports that have no Git evidence.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
enum SkillProvenance {
    Verified,
    Partial,
    Unknown,
}

impl SkillProvenance {
    fn as_str(self) -> &'static str {
        match self {
            Self::Verified => "verified",
            Self::Partial => "partial",
            Self::Unknown => "unknown",
        }
    }

    fn parse(raw: &str) -> Result<Self> {
        match raw.trim().to_ascii_lowercase().as_str() {
            "verified" => Ok(Self::Verified),
            "partial" => Ok(Self::Partial),
            "unknown" => Ok(Self::Unknown),
            other => bail!("unknown provenance {other:?}; expected verified|partial|unknown"),
        }
    }
}

fn has_nonempty_tag(tags: &[String], prefix: &str) -> bool {
    tag_value(tags, prefix).is_some_and(|value| !value.trim().is_empty())
}

fn skill_provenance(tags: &[String]) -> SkillProvenance {
    let has_origin = has_nonempty_tag(tags, "git_origin:");
    let has_commit = has_nonempty_tag(tags, "git_commit:");
    if has_origin && has_commit {
        SkillProvenance::Verified
    } else if has_origin
        || has_commit
        || has_nonempty_tag(tags, "git_branch:")
        || has_nonempty_tag(tags, "git_src:")
    {
        SkillProvenance::Partial
    } else {
        SkillProvenance::Unknown
    }
}

fn split_csv_tag(s: &str) -> Vec<String> {
    s.split(',')
        .map(str::trim)
        .filter(|x| !x.is_empty())
        .map(str::to_string)
        .collect()
}

fn truncate_chars(s: &str, max_chars: usize) -> String {
    let mut out = String::new();
    for (idx, ch) in s.chars().enumerate() {
        if idx >= max_chars {
            out.push_str("...");
            break;
        }
        out.push(ch);
    }
    out
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

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
enum CloneMode {
    Partial,
    FullHttp11,
}

fn clone_args(url: &str, dir: &Path, checkout_ref: Option<&str>, mode: CloneMode) -> Vec<String> {
    let mut args = Vec::new();
    if mode == CloneMode::FullHttp11 {
        // Some GitHub partial-clone checkouts reset while lazy-fetching a
        // promised blob. The fallback trades a small amount of bandwidth for a
        // complete shallow checkout over HTTP/1.1.
        args.extend(["-c".to_string(), "http.version=HTTP/1.1".to_string()]);
    }
    args.extend([
        "clone".to_string(),
        "--depth=1".to_string(),
        "--quiet".to_string(),
    ]);
    if mode == CloneMode::Partial {
        args.push("--filter=blob:none".to_string());
    }
    if mode == CloneMode::FullHttp11 {
        args.push("--single-branch".to_string());
    }
    if let Some(r) = checkout_ref {
        args.push("--branch".to_string());
        args.push(r.to_string());
        if mode == CloneMode::Partial {
            args.push("--single-branch".to_string());
        }
    }
    args.push(url.to_string());
    args.push(dir.to_string_lossy().to_string());
    args
}

fn run_clone(args: &[String], url: &str) -> Result<std::process::ExitStatus> {
    Command::new("git")
        .args(args)
        .stdout(Stdio::null())
        .stderr(Stdio::inherit())
        .status()
        .with_context(|| format!("git clone {} failed to launch", url))
}

fn fallback_checkout_ref(checkout_ref: Option<&str>) -> Option<&str> {
    // `main` is the current default for the affected source. Omitting it lets
    // Git select the remote HEAD, which avoids the failing advertised-ref
    // partial-checkout path while retaining explicit non-default refs.
    match checkout_ref {
        Some("main") => None,
        other => other,
    }
}

fn clone_shallow(url: &str, src_id: &str, checkout_ref: Option<&str>) -> Result<PathBuf> {
    let nonce = SystemTime::now()
        .duration_since(SystemTime::UNIX_EPOCH)
        .map(|d| d.as_nanos())
        .unwrap_or(0);
    let safe_id = src_id.replace('/', "_");
    let dir = std::env::temp_dir().join(format!("ab-skills-{}-{}", safe_id, nonce));
    let status = run_clone(
        &clone_args(url, &dir, checkout_ref, CloneMode::Partial),
        url,
    )?;
    if !status.success() {
        eprintln!(
            "[skills] partial clone failed for {}; retrying full shallow clone over HTTP/1.1",
            src_id
        );
        let _ = std::fs::remove_dir_all(&dir);
        let fallback = run_clone(
            &clone_args(
                url,
                &dir,
                fallback_checkout_ref(checkout_ref),
                CloneMode::FullHttp11,
            ),
            url,
        )?;
        if !fallback.success() {
            bail!(
                "git clone {} failed: partial exited {:?}, HTTP/1.1 fallback exited {:?}",
                url,
                status.code(),
                fallback.code()
            );
        }
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

    // Structural coherence check for the DIALS / PRE-FLIGHT authoring convention
    // (see docs/skill-authoring-spec.md): a skill that declares a high RIGOR dial
    // is expected to ship a self-check matrix. This only fires for skills that
    // opt into the convention by declaring a `## DIALS` section with a RIGOR dial,
    // so it never warns on the many skills that don't use DIALS at all.
    if let Some(rigor) = parse_rigor_dial(body) {
        let has_preflight = body.lines().any(|l| {
            let t = l.trim_start();
            if !t.starts_with('#') {
                return false;
            }
            let h = t.to_ascii_lowercase();
            h.contains("pre-flight") || h.contains("preflight")
        });
        if rigor >= 4 && !has_preflight {
            out.push(LintFinding {
                sev: LintSev::Warn,
                rule: "rigor-without-preflight",
                snippet: format!(
                    "RIGOR:{rigor} declared but no `## PRE-FLIGHT` self-check section"
                ),
            });
        }
    }

    out
}

/// Parse every dial declared in a `## DIALS` section, in document order.
///
/// A dial line follows the authoring convention `- ` + "`NAME: N`" (see
/// docs/skill-authoring-spec.md), where NAME is an UPPER_SNAKE identifier and N
/// an integer. Returns an empty vec when the skill declares no `## DIALS`
/// section, so anything keyed off dials (the [`lint_body`] coherence check, the
/// `skills_route` metadata surface) only applies to skills that opt into the
/// convention. Only ASCII tokens are inspected, so CJK prose in the same line is
/// skipped without panicking on byte boundaries.
fn parse_dials(body: &str) -> Vec<(String, u32)> {
    let mut out = Vec::new();
    let mut in_dials = false;
    for line in body.lines() {
        let trimmed = line.trim_start();
        if trimmed.starts_with('#') {
            // Any heading line re-scopes us: enter DIALS on `## DIALS`,
            // leave it on any other heading.
            in_dials = trimmed.to_ascii_lowercase().contains("dials");
            continue;
        }
        if in_dials {
            if let Some(pair) = parse_dial_line(line) {
                out.push(pair);
            }
        }
    }
    out
}

/// Extract the first `NAME: N` dial from a line, where NAME is an UPPER_SNAKE
/// identifier (>= 2 chars) and N the first integer after the colon. Returns
/// `None` if the line carries no dial. Scans by byte but only ever slices at
/// ASCII positions, so non-ASCII bytes are walked over safely.
fn parse_dial_line(line: &str) -> Option<(String, u32)> {
    let b = line.as_bytes();
    let mut i = 0;
    while i < b.len() {
        if !b[i].is_ascii_uppercase() {
            i += 1;
            continue;
        }
        let start = i;
        while i < b.len() && (b[i].is_ascii_uppercase() || b[i] == b'_' || b[i].is_ascii_digit()) {
            i += 1;
        }
        let name = &line[start..i];
        let mut j = i;
        while j < b.len() && b[j] == b' ' {
            j += 1;
        }
        if name.len() >= 2 && j < b.len() && b[j] == b':' {
            j += 1;
            while j < b.len() && b[j] == b' ' {
                j += 1;
            }
            let dstart = j;
            while j < b.len() && b[j].is_ascii_digit() {
                j += 1;
            }
            if let Ok(v) = line[dstart..j].parse::<u32>() {
                return Some((name.to_string(), v));
            }
        }
        // `i` already sits past the uppercase run; keep scanning the rest.
    }
    None
}

/// The `RIGOR` dial value from a `## DIALS` section, if declared. Thin wrapper
/// over [`parse_dials`] used by the [`lint_body`] coherence check.
fn parse_rigor_dial(body: &str) -> Option<u32> {
    parse_dials(body)
        .into_iter()
        .find(|(name, _)| name == "RIGOR")
        .map(|(_, v)| v)
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

/// Open the existing state database without directory creation, migration, or
/// write-capable SQLite initialization. Observation commands fail closed when
/// the database is absent or cannot be read as-is.
async fn open_store_read_only() -> Result<SqliteStore> {
    let db_path = std::env::var("AGENT_BRIDGE_DB")
        .ok()
        .map(PathBuf::from)
        .unwrap_or_else(ab_store::default_db_path);
    SqliteStore::open_read_only(&db_path)
        .await
        .with_context(|| format!("open read-only SqliteStore at {}", db_path.display()))
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
    fn relaxed_fts_query_removes_stopwords_and_ors_terms() {
        let q = relaxed_fts_query(
            "memory systems and agent bridge memory retrieval graph without prompt bloat",
        )
        .expect("query");
        assert!(q.contains("memory"));
        assert!(q.contains("systems"));
        assert!(q.contains("retrieval"));
        assert!(q.contains(" OR "));
        assert!(!q.contains(" and "));
        assert!(!q.contains("without"));
    }

    #[test]
    fn route_merge_hits_puts_weak_semantic_after_fts() {
        let weak_semantic = test_skill_hit("skill:weak-semantic", 0.46, Some(0.46));
        let fts = test_skill_hit("skill:fts", 20.0, None);

        let hits = route_merge_hits(vec![weak_semantic], vec![fts], 2);

        assert_eq!(hits[0].record.key, "skill:fts");
        assert_eq!(hits[1].record.key, "skill:weak-semantic");
    }

    #[test]
    fn route_merge_limit_one_prefers_fts_over_weak_semantic() {
        let weak_semantic = test_skill_hit("skill:weak-semantic", 0.46, Some(0.46));
        let fts = test_skill_hit("skill:fts", 20.0, None);

        let hits = route_merge_hits(vec![weak_semantic], vec![fts], 1);

        assert_eq!(hits.len(), 1);
        assert_eq!(hits[0].record.key, "skill:fts");
    }

    #[test]
    fn route_merge_hits_keeps_strong_semantic_first() {
        let strong_semantic = test_skill_hit("skill:strong-semantic", 0.82, Some(0.82));
        let fts = test_skill_hit("skill:fts", 20.0, None);

        let hits = route_merge_hits(vec![strong_semantic], vec![fts], 2);

        assert_eq!(hits[0].record.key, "skill:strong-semantic");
        assert_eq!(hits[1].record.key, "skill:fts");
    }

    #[test]
    fn route_retrieval_limit_overfetches_before_final_cutoff() {
        assert_eq!(route_retrieval_limit(1), 100);
        assert_eq!(route_retrieval_limit(10), 200);
        assert_eq!(route_retrieval_limit(50), 500);
    }

    #[test]
    fn route_candidate_limit_preserves_format_matches_before_final_cutoff() {
        assert_eq!(route_candidate_limit(1), 20);
        assert_eq!(route_candidate_limit(5), 50);
        assert_eq!(route_candidate_limit(50), 100);
    }

    #[test]
    fn route_prioritizes_exact_file_format_skill_over_broad_document_matches() {
        let broad = test_skill_hit("skill:docs", 20.0, Some(0.8));
        let mut partial = test_skill_hit("skill:community/pdf-official", 12.0, None);
        partial
            .record
            .tags
            .push("path:pdf-official/SKILL.md".to_string());
        let mut exact = test_skill_hit("skill:anthropics/pdf", 8.0, None);
        exact.record.tags.push("path:pdf/SKILL.md".to_string());

        let hits = route_prioritize_explicit_format(
            "read, edit, and verify a PDF form",
            vec![broad, partial, exact],
        );

        assert_eq!(hits[0].record.key, "skill:anthropics/pdf");
        assert_eq!(hits[1].record.key, "skill:community/pdf-official");
        assert_eq!(hits[2].record.key, "skill:docs");
    }

    #[test]
    fn route_recognizes_explicit_formats_in_english_and_chinese_queries() {
        let cases = [
            ("read and edit a PDF form", vec!["pdf"]),
            ("编辑 PDF 表单并验证内容", vec!["pdf"]),
            ("update the DOCX contract", vec!["docx"]),
            ("修改 DOCX 合同", vec!["docx"]),
            ("recalculate the XLSX budget", vec!["xlsx"]),
            ("重算 XLSX 预算表", vec!["xlsx"]),
            ("prepare the PPTX presentation", vec!["pptx"]),
            ("整理 PPTX 演示文稿", vec!["pptx"]),
        ];

        for (query, expected) in cases {
            assert_eq!(requested_file_formats(query), expected, "{query}");
        }
    }

    #[test]
    fn route_prioritizes_exact_skill_for_each_supported_file_format() {
        for format in ROUTE_FILE_FORMATS {
            let broad = test_skill_hit("skill:docs", 20.0, Some(0.8));
            let mut partial =
                test_skill_hit(&format!("skill:community/{format}-official"), 12.0, None);
            partial
                .record
                .tags
                .push(format!("path:{format}-official/SKILL.md"));
            let mut exact = test_skill_hit(&format!("skill:official/{format}"), 8.0, None);
            exact.record.tags.push(format!("path:{format}/SKILL.md"));

            let hits = route_prioritize_explicit_format(
                &format!("处理 {format} 文件"),
                vec![broad, partial, exact],
            );

            assert_eq!(hits[0].record.key, format!("skill:official/{format}"));
            assert_eq!(
                hits[1].record.key,
                format!("skill:community/{format}-official")
            );
            assert_eq!(hits[2].record.key, "skill:docs");
        }
    }

    #[test]
    fn route_keeps_explicit_file_format_priority_after_feedback_sorting() {
        let mut broad = test_skill_hit("skill:docs", 20.0, Some(0.8));
        broad.record.tags.push("path:docx/SKILL.md".to_string());
        let mut exact = test_skill_hit("skill:pdf", 8.0, None);
        exact.record.tags.push("path:pdf/SKILL.md".to_string());

        let routed = route_apply_feedback(
            vec![broad, exact],
            &BTreeMap::from([(
                "skill:docs".to_string(),
                SkillRouteFeedback {
                    score: 0.4,
                    count: 1,
                    positive_count: 1,
                    negative_count: 0,
                },
            )]),
        );
        let routed = route_prioritize_explicit_format_routed("edit a PDF form", routed);

        assert_eq!(routed[0].hit.record.key, "skill:pdf");
        assert_eq!(routed[1].hit.record.key, "skill:docs");
    }

    #[test]
    fn route_leaves_general_queries_in_retrieval_order() {
        let first = test_skill_hit("skill:first", 20.0, None);
        let mut pdf = test_skill_hit("skill:pdf", 8.0, None);
        pdf.record.tags.push("path:pdf/SKILL.md".to_string());

        let hits = route_prioritize_explicit_format("review a design document", vec![first, pdf]);

        assert_eq!(hits[0].record.key, "skill:first");
        assert_eq!(hits[1].record.key, "skill:pdf");
    }

    #[test]
    fn route_item_confidence_uses_semantic_cosine() {
        let mut raw = test_skill_hit("skill:semantic", 2.0, Some(0.49));
        raw.record.tags.extend([
            "git_origin:https://github.com/acme/skills.git".to_string(),
            "git_commit:abc123".to_string(),
        ]);
        let hit = RoutedSkillHit {
            hit: raw,
            score: 2.0,
            feedback: SkillRouteFeedback::default(),
        };

        let item = route_item_json(1, &hit, 0);

        assert_eq!(item["confidence"], "low");
        assert_eq!(item["retrieval"], "semantic");
        assert_eq!(item["provenance"], "verified");
        let cosine = item["cosine"].as_f64().expect("cosine");
        assert!((cosine - 0.49).abs() < 1e-6);
    }

    #[test]
    fn skill_feedback_outcome_parses_aliases() {
        assert_eq!(
            SkillFeedbackOutcome::parse("not-helpful").expect("outcome"),
            SkillFeedbackOutcome::NotHelpful
        );
        assert_eq!(
            SkillFeedbackOutcome::parse("used").expect("outcome"),
            SkillFeedbackOutcome::Used
        );
        assert!(SkillFeedbackOutcome::parse("maybe").is_err());
    }

    #[test]
    fn skill_feedback_key_is_stable_and_hashed() {
        let key_a = skill_feedback_key(
            "skill:skills/agent-memory-systems",
            "memory systems and agent bridge",
            SkillFeedbackOutcome::Helpful,
            Some("worked well"),
        );
        let key_b = skill_feedback_key(
            "skill:skills/agent-memory-systems",
            "memory systems and agent bridge",
            SkillFeedbackOutcome::Helpful,
            Some("worked well"),
        );

        assert_eq!(key_a, key_b);
        assert!(key_a.starts_with("skill_feedback:"));
        assert!(!key_a.contains("agent-memory-systems"));
        assert!(key_a.len() <= "skill_feedback:".len() + 16);
    }

    #[test]
    fn skill_feedback_record_carries_graph_metadata() {
        let rec = build_skill_feedback_record(
            "skill:skills/agent-memory-systems",
            "memory systems and agent bridge",
            SkillFeedbackOutcome::Helpful,
            Some("loaded and used for graph design"),
            &["decision:skill-memory".to_string()],
        );

        assert_eq!(rec.kind, "skill_feedback");
        assert!(rec.tags.contains(&"skill_feedback".to_string()));
        assert!(rec.tags.contains(&"skill_feedback:helpful".to_string()));
        assert!(rec
            .tags
            .contains(&"skill_key:skill:skills/agent-memory-systems".to_string()));
        assert_eq!(rec.related_keys[0], "skill:skills/agent-memory-systems");
        assert!(rec
            .related_keys
            .contains(&"decision:skill-memory".to_string()));
        assert!(rec.content.contains("outcome: helpful"));
        assert!(rec.content.contains("loaded and used for graph design"));
    }

    #[test]
    fn route_feedback_stats_counts_positive_and_negative_edges() {
        let edges = vec![
            test_edge(
                "skill_feedback:helpful",
                "skill:target",
                "applied_skill",
                1.4,
            ),
            test_edge("skill_feedback:used", "skill:target", "applied_skill", 1.1),
            test_edge("skill_feedback:bad", "skill:target", "skill_feedback", 0.3),
            test_edge("unrelated", "skill:target", "relates", 1.0),
        ];

        let stats = route_feedback_stats_from_edges("skill:target", &edges);

        assert_eq!(stats.count, 3);
        assert_eq!(stats.positive_count, 2);
        assert_eq!(stats.negative_count, 1);
        assert!(stats.score > 0.0, "positive feedback should win here");
    }

    #[test]
    fn route_apply_feedback_promotes_nearby_verified_skill() {
        let high_raw = test_skill_hit("skill:raw", 10.0, None);
        let verified = test_skill_hit("skill:verified", 9.8, None);
        let mut feedback = BTreeMap::new();
        feedback.insert(
            "skill:verified".to_string(),
            SkillRouteFeedback {
                score: 0.35,
                count: 2,
                positive_count: 2,
                negative_count: 0,
            },
        );

        let ranked = route_apply_feedback(vec![high_raw, verified], &feedback);

        assert_eq!(ranked[0].hit.record.key, "skill:verified");
        assert_eq!(ranked[0].feedback.count, 2);
        assert!(ranked[0].score > ranked[1].score);
    }

    #[test]
    fn route_item_json_exposes_feedback_evidence() {
        let routed = RoutedSkillHit {
            hit: test_skill_hit("skill:verified", 9.8, None),
            score: 10.15,
            feedback: SkillRouteFeedback {
                score: 0.35,
                count: 2,
                positive_count: 2,
                negative_count: 0,
            },
        };

        let item = route_item_json(1, &routed, 0);

        assert_eq!(item["feedback_score"], 0.35);
        assert_eq!(item["feedback_count"], 2);
        assert_eq!(item["positive_feedback_count"], 2);
    }

    fn test_skill_hit(key: &str, score: f64, cosine: Option<f32>) -> MemorySearchHit {
        MemorySearchHit {
            record: MemoryRecord {
                key: key.to_string(),
                kind: "skill".to_string(),
                content: format!("{key} summary"),
                tags: vec!["skill".to_string(), "lint:clean".to_string()],
                related_keys: Vec::new(),
                scope: Some("global".to_string()),
                created_at: 0,
                updated_at: 0,
                last_accessed_at: 0,
                access_count: 0,
                importance: 0.5,
                status: "active".to_string(),
                trigger_pattern: None,
                superseded_by: None,
            },
            score,
            cosine,
        }
    }

    fn test_edge(from_key: &str, to_key: &str, edge_type: &str, weight: f64) -> MemoryEdge {
        MemoryEdge {
            from_key: from_key.to_string(),
            to_key: to_key.to_string(),
            edge_type: edge_type.to_string(),
            weight,
        }
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
    fn lint_flags_high_rigor_without_preflight() {
        let body = "## DIALS\n- `RIGOR: 4` — production\n\n## TELLS\n- ban panics\n";
        let f = lint_body(body);
        assert!(f.iter().any(|x| x.rule == "rigor-without-preflight"));
    }

    #[test]
    fn lint_clean_when_high_rigor_has_preflight() {
        let body = "## DIALS\n- `RIGOR: 5` — production\n\n## PRE-FLIGHT\n- [ ] tests run?\n";
        let f = lint_body(body);
        assert!(!f.iter().any(|x| x.rule == "rigor-without-preflight"));
    }

    #[test]
    fn lint_ignores_low_rigor_without_preflight() {
        // RIGOR below the threshold doesn't require a self-check matrix.
        let body = "## DIALS\n- `RIGOR: 2` — quick draft\n";
        let f = lint_body(body);
        assert!(!f.iter().any(|x| x.rule == "rigor-without-preflight"));
    }

    #[test]
    fn parse_dials_extracts_all_in_order() {
        let body = "## DIALS\n- `RIGOR: 4` — production\n- `BLAST_RADIUS: 2` — single file\n\n## NEXT\n- `IGNORED: 9`\n";
        let dials = parse_dials(body);
        assert_eq!(
            dials,
            vec![("RIGOR".to_string(), 4), ("BLAST_RADIUS".to_string(), 2)]
        );
    }

    #[test]
    fn parse_dials_empty_without_section() {
        assert!(parse_dials("# Skill\nNo dials. Apply RIGOR: 9 in prose.\n").is_empty());
    }

    #[test]
    fn parse_dial_line_ignores_cjk_and_lowercase() {
        // CJK prose around the dial must not panic or false-match; lowercase isn't a dial.
        assert_eq!(
            parse_dial_line("- `RIGOR: 3` — 严格度，1=草稿 5=生产"),
            Some(("RIGOR".to_string(), 3))
        );
        assert_eq!(parse_dial_line("- rigor: 3 (lowercase, not a dial)"), None);
        assert_eq!(parse_dial_line("纯中文一行，没有任何旋钮"), None);
    }

    #[test]
    fn lint_ignores_rigor_outside_dials_section() {
        // A skill that never opts into the DIALS convention is left alone,
        // even if the word RIGOR appears in prose.
        let body = "# Some Skill\nApply RIGOR: 9 when reviewing.\nNo dials here.\n";
        let f = lint_body(body);
        assert!(parse_rigor_dial(body).is_none());
        assert!(!f.iter().any(|x| x.rule == "rigor-without-preflight"));
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
    fn install_lint_gate_accepts_stripped_or_full_lint_tags() {
        assert!(!lint_requires_approval("clean"));
        assert!(!lint_requires_approval("lint:clean"));
        assert!(lint_requires_approval("warn:1"));
        assert!(lint_requires_approval("lint:warn:1"));
        assert!(lint_requires_approval("danger:2"));
        assert!(lint_requires_approval("lint:danger:2"));
    }

    #[test]
    fn install_approval_risks_only_flags_writey_or_network_actions() {
        let risks = vec![
            "apple_mlx".to_string(),
            "checkpoint_write".to_string(),
            "finetune_write".to_string(),
            "gpu_required".to_string(),
            "model_download".to_string(),
            "network_fetch".to_string(),
            "pip_install".to_string(),
            "server_start".to_string(),
        ];
        assert_eq!(
            install_approval_risks(&risks),
            vec![
                "checkpoint_write",
                "finetune_write",
                "model_download",
                "network_fetch",
                "pip_install",
                "server_start",
            ]
            .into_iter()
            .map(str::to_string)
            .collect::<Vec<_>>()
        );
    }

    #[test]
    fn install_clone_plan_prefers_recorded_git_provenance() {
        let tags = vec![
            "src:OpenBMB/MiniCPM".to_string(),
            "git_origin:https://github.com/OpenBMB/MiniCPM.git".to_string(),
            "git_branch:minicpm5".to_string(),
            "git_commit:44e6ae86fe8d7fbde2903beaeabccc3a45a8c19b".to_string(),
        ];
        assert_eq!(
            install_clone_plan("OpenBMB/MiniCPM", &tags),
            InstallClonePlan {
                url: "https://github.com/OpenBMB/MiniCPM.git".to_string(),
                checkout_ref: Some("minicpm5".to_string()),
                expected_commit: Some("44e6ae86fe8d7fbde2903beaeabccc3a45a8c19b".to_string()),
            }
        );
    }

    #[test]
    fn install_clone_plan_falls_back_to_source_id() {
        let plan = install_clone_plan("gitlab.com/example/repo", &[]);
        assert_eq!(
            plan,
            InstallClonePlan {
                url: "https://gitlab.com/example/repo".to_string(),
                checkout_ref: None,
                expected_commit: None,
            }
        );
    }

    #[test]
    fn commit_match_accepts_exact_or_expected_prefix_only() {
        let full = "44e6ae86fe8d7fbde2903beaeabccc3a45a8c19b";
        assert!(commit_matches_expected(full, full));
        assert!(commit_matches_expected(full, "44e6ae8"));
        assert!(!commit_matches_expected("44e6ae8", full));
        assert!(!commit_matches_expected(full, "deadbeef"));
    }

    #[test]
    fn refresh_remote_plan_preserves_recorded_git_provenance() {
        let tags = vec![
            "src:OpenBMB/MiniCPM".to_string(),
            "git_origin:https://github.com/OpenBMB/MiniCPM.git".to_string(),
            "git_branch:minicpm5".to_string(),
            "git_commit:44e6ae86fe8d7fbde2903beaeabccc3a45a8c19b".to_string(),
        ];
        assert_eq!(
            remote_index_plan("OpenBMB/MiniCPM", &tags),
            RemoteIndexPlan {
                src: "OpenBMB/MiniCPM".to_string(),
                url: "https://github.com/OpenBMB/MiniCPM.git".to_string(),
                checkout_ref: Some("minicpm5".to_string()),
            }
        );
    }

    #[test]
    fn refresh_remote_plan_falls_back_to_source_id() {
        assert_eq!(
            remote_index_plan("OpenBMB/MiniCPM", &[]),
            RemoteIndexPlan {
                src: "OpenBMB/MiniCPM".to_string(),
                url: "https://github.com/OpenBMB/MiniCPM".to_string(),
                checkout_ref: None,
            }
        );
    }

    #[test]
    fn refresh_mode_suffix_reports_dry_run_and_prune() {
        assert_eq!(refresh_mode_suffix(false, false), "");
        assert_eq!(refresh_mode_suffix(true, false), " (prune ON)");
        assert_eq!(refresh_mode_suffix(false, true), " (dry-run)");
        assert_eq!(refresh_mode_suffix(true, true), " (prune ON, dry-run)");
    }

    #[test]
    fn refresh_dry_run_payload_is_machine_readable_and_non_mutating() {
        let mut plans = BTreeMap::new();
        plans.insert(
            "OpenBMB/MiniCPM".to_string(),
            RemoteIndexPlan {
                src: "OpenBMB/MiniCPM".to_string(),
                url: "https://github.com/OpenBMB/MiniCPM.git".to_string(),
                checkout_ref: Some("minicpm5".to_string()),
            },
        );
        let local_srcs = BTreeSet::from(["local-skills".to_string()]);

        let payload = refresh_dry_run_payload(&plans, &local_srcs, 16, true, None, None);
        assert_eq!(payload["dry_run"], true);
        assert_eq!(payload["mutates"], false);
        assert_eq!(payload["total_records"], 16);
        assert!(payload["source_filter"].is_null());
        assert!(payload["checkout_ref_override"].is_null());
        assert_eq!(payload["remote_source_count"], 1);
        assert_eq!(payload["local_source_count"], 1);
        assert_eq!(payload["actions"]["clone_repos"], false);
        assert_eq!(payload["actions"]["write_memories"], false);
        assert_eq!(payload["actions"]["prune_stale_records"], false);
        assert_eq!(payload["remote_sources"][0]["source"], "OpenBMB/MiniCPM");
        assert_eq!(
            payload["remote_sources"][0]["url"],
            "https://github.com/OpenBMB/MiniCPM.git"
        );
        assert_eq!(payload["remote_sources"][0]["checkout_ref"], "minicpm5");
        assert_eq!(payload["local_sources_skipped"][0], "local-skills");
        assert!(payload["prune_note"]
            .as_str()
            .unwrap()
            .contains("successful"));
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
        assert_eq!(payload["path"], "skills/minicpm5-deploy-mlx/SKILL.md");
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
    fn skill_audit_filters_match_lint_risk_and_source() {
        let mut rec = mk_skill("OpenBMB/MiniCPM", 42);
        rec.tags.extend([
            "lint:warn:1".to_string(),
            "vendor:community".to_string(),
            "risk:server_start".to_string(),
            "risk:model_download".to_string(),
        ]);

        let filters = SkillAuditFilters::new(
            Some("OpenBMB/MiniCPM"),
            &["risk:server_start".to_string()],
            Some("warn"),
            Some("community"),
            None,
        )
        .expect("filters");
        assert!(filters.matches(&rec));

        let missing_risk =
            SkillAuditFilters::new(None, &["checkpoint_write".to_string()], None, None, None)
                .expect("filters");
        assert!(!missing_risk.matches(&rec));
    }

    #[test]
    fn skill_provenance_requires_origin_and_commit_for_verified() {
        let verified = vec![
            "git_origin:https://github.com/acme/skills.git".to_string(),
            "git_commit:abc123".to_string(),
        ];
        let partial = vec!["git_branch:main".to_string()];

        assert_eq!(skill_provenance(&verified), SkillProvenance::Verified);
        assert_eq!(skill_provenance(&partial), SkillProvenance::Partial);
        assert_eq!(skill_provenance(&[]), SkillProvenance::Unknown);
        assert!(SkillProvenance::parse("bad").is_err());
    }

    #[test]
    fn provenance_shadow_audit_filters_without_reordering_baseline() {
        let unknown = RoutedSkillHit {
            hit: test_skill_hit("skill:legacy/pdf", 10.0, None),
            score: 10.0,
            feedback: SkillRouteFeedback::default(),
        };
        let mut verified_hit = test_skill_hit("skill:upstream/pdf", 9.0, None);
        verified_hit.record.tags.extend([
            "git_origin:https://github.com/example/skills.git".to_string(),
            "git_commit:deadbeef".to_string(),
        ]);
        let verified = RoutedSkillHit {
            hit: verified_hit,
            score: 9.0,
            feedback: SkillRouteFeedback::default(),
        };

        let payload = route_provenance_shadow_payload("review a PDF", &[unknown, verified], 2);

        assert_eq!(payload["baseline"]["skills"][0]["key"], "skill:legacy/pdf");
        assert_eq!(
            payload["verified_only"]["skills"][0]["key"],
            "skill:upstream/pdf"
        );
        assert_eq!(payload["verdict"], "INCONCLUSIVE_NO_POLICY_CHANGE");
        assert_eq!(payload["actions"]["changes_route_policy"], false);
    }

    #[test]
    fn embedded_provenance_corpus_is_well_formed() {
        let corpus = parse_route_provenance_corpus(None).expect("embedded corpus");

        assert_eq!(
            corpus.schema,
            "agent_bridge.skills_route.provenance_query_cases.v0"
        );
        assert!(corpus
            .cases
            .iter()
            .any(|case| case.verified_coverage == "required"));
        assert!(corpus
            .cases
            .iter()
            .any(|case| case.verified_coverage == "insufficient_expected"));
    }

    #[test]
    fn provenance_holdout_has_independent_paired_gate_coverage() {
        let corpus = parse_route_provenance_holdout().expect("embedded holdout");

        assert_eq!(corpus.schema_version, "skills-route-provenance-holdout-v1");
        assert!(corpus.cases.len() >= 20);
        assert!(corpus
            .cases
            .iter()
            .any(|case| case.verified_coverage == "required"));
        assert!(corpus
            .cases
            .iter()
            .any(|case| case.verified_coverage == "insufficient_expected"));
    }

    #[test]
    fn skill_audit_filters_by_provenance() {
        let mut verified = mk_skill("OpenBMB/MiniCPM", 42);
        verified.tags.extend([
            "git_origin:https://github.com/OpenBMB/MiniCPM.git".to_string(),
            "git_commit:abc123".to_string(),
        ]);
        let unknown = mk_skill("local-skills", 43);
        let filter = SkillAuditFilters::new(None, &[], None, None, Some("verified"))
            .expect("verified filter");

        assert!(filter.matches(&verified));
        assert!(!filter.matches(&unknown));
    }

    #[test]
    fn skill_audit_summary_counts_sources_and_risks() {
        let mut a = mk_skill("OpenBMB/MiniCPM", 1);
        a.tags.extend([
            "lint:clean".to_string(),
            "vendor:community".to_string(),
            "risk:server_start".to_string(),
        ]);
        let mut b = mk_skill("OpenBMB/MiniCPM", 2);
        b.tags.extend([
            "lint:warn:1".to_string(),
            "vendor:community".to_string(),
            "risk:server_start".to_string(),
            "risk:pip_install".to_string(),
        ]);

        let summary = skill_audit_summary(&[a, b]);
        assert_eq!(summary.sources.get("OpenBMB/MiniCPM"), Some(&2));
        assert_eq!(summary.lint.get("clean"), Some(&1));
        assert_eq!(summary.lint.get("warn:1"), Some(&1));
        assert_eq!(summary.risks.get("server_start"), Some(&2));
        assert_eq!(summary.risks.get("pip_install"), Some(&1));
    }

    #[test]
    fn skill_source_inventory_groups_provenance_lint_and_risk() {
        let mut a = mk_skill("OpenBMB/MiniCPM", 10);
        a.tags.extend([
            "lint:clean".to_string(),
            "vendor:community".to_string(),
            "git_origin:https://github.com/OpenBMB/MiniCPM.git".to_string(),
            "git_branch:minicpm5".to_string(),
            "git_commit:abc123".to_string(),
            "risk:model_download".to_string(),
            "risk:apple_mlx".to_string(),
        ]);
        let mut b = mk_skill("OpenBMB/MiniCPM", 20);
        b.tags.extend([
            "lint:warn:1".to_string(),
            "vendor:community".to_string(),
            "git_origin:https://github.com/OpenBMB/MiniCPM.git".to_string(),
            "git_branch:minicpm5".to_string(),
            "git_commit:def456".to_string(),
            "risk:model_download".to_string(),
            "risk:server_start".to_string(),
        ]);
        let mut local = mk_skill("local-skills", 5);
        local
            .tags
            .extend(["lint:clean".to_string(), "vendor:community".to_string()]);

        let inventory = skill_source_inventory(&[a, b, local], &BTreeMap::new());
        assert_eq!(inventory.len(), 2);

        let local_summary = inventory
            .iter()
            .find(|s| s.source == "local-skills")
            .unwrap();
        assert_eq!(local_summary.count, 1);
        assert!(!local_summary.refreshable);

        let remote = inventory
            .iter()
            .find(|s| s.source == "OpenBMB/MiniCPM")
            .unwrap();
        assert_eq!(remote.count, 2);
        assert!(remote.refreshable);
        assert_eq!(remote.latest_updated_at, 20);
        assert_eq!(remote.git_branches.len(), 1);
        assert!(remote.git_branches.contains("minicpm5"));
        assert_eq!(remote.git_commits.len(), 2);
        assert_eq!(remote.lint.get("clean"), Some(&1));
        assert_eq!(remote.lint.get("warn:1"), Some(&1));
        assert_eq!(remote.risks.get("model_download"), Some(&2));
        assert_eq!(remote.risks.get("server_start"), Some(&1));
    }

    #[test]
    fn source_admission_is_joined_without_changing_skill_metadata() {
        let mut skill = mk_skill("example/skills", 10);
        skill.tags.extend([
            "git_origin:https://github.com/example/skills.git".to_string(),
            "git_commit:abc123".to_string(),
        ]);
        let mut admission = mk_skill("example/skills", 20);
        admission.kind = "skill_source_admission".to_string();
        admission.tags.extend([
            "admission:approved".to_string(),
            "spdx:MIT".to_string(),
            "evidence_url:https://github.com/example/skills/blob/main/LICENSE".to_string(),
            "git_origin:https://github.com/example/skills.git".to_string(),
            "git_commit:abc123".to_string(),
        ]);
        let admissions = source_admission_inventory(&[admission]);
        let inventory = skill_source_inventory(&[skill.clone()], &admissions);
        let source = &inventory[0];
        assert_eq!(source.admission.as_ref().unwrap().spdx, "MIT");
        assert_eq!(
            source.admission.as_ref().unwrap().verdict,
            SourceAdmissionVerdict::Approved
        );
        assert_eq!(
            source.admission_freshness,
            Some(AdmissionFreshness::Current)
        );
        assert!(tag_value(&skill.tags, "license:").is_none());
        let item = skill_audit_item_json(&skill, Some(source));
        assert_eq!(item["source_admission"]["spdx"], "MIT");
        assert_eq!(item["source_admission"]["freshness"], "current");
        assert_eq!(item["license"], serde_json::Value::Null);
    }

    #[test]
    fn source_admission_freshness_requires_exact_single_provenance() {
        let admission = SkillSourceAdmission {
            verdict: SourceAdmissionVerdict::Approved,
            spdx: "MIT".to_string(),
            evidence_url: None,
            reviewed_at: 1,
            git_origin: Some("https://github.com/example/skills.git".to_string()),
            git_commit: Some("abc123".to_string()),
        };
        let mut source = SkillSourceSummary {
            source: "example/skills".to_string(),
            ..SkillSourceSummary::default()
        };
        source
            .git_origins
            .insert("https://github.com/example/skills.git".to_string());
        source.git_commits.insert("abc123".to_string());
        assert_eq!(
            source_admission_freshness(&source, &admission),
            AdmissionFreshness::Current
        );

        source.git_commits.insert("def456".to_string());
        assert_eq!(
            source_admission_freshness(&source, &admission),
            AdmissionFreshness::Stale
        );

        source.git_commits.clear();
        assert_eq!(
            source_admission_freshness(&source, &admission),
            AdmissionFreshness::Unknown
        );
    }

    #[test]
    fn source_admission_verdict_is_closed_set() {
        assert_eq!(
            SourceAdmissionVerdict::parse("quarantined").unwrap(),
            SourceAdmissionVerdict::Quarantined
        );
        assert!(SourceAdmissionVerdict::parse("trusted").is_err());
    }

    #[test]
    fn legacy_source_recovery_manifest_keeps_legacy_sources_unresolved() {
        let recovery = legacy_source_recovery_inventory().unwrap();
        assert_eq!(recovery.len(), 3);
        for source in ["skills", "taste-skill", "ab-house-rules"] {
            let entry = recovery.get(source).unwrap();
            assert_eq!(entry.status, "unresolved");
            assert!(entry.policy.contains("Keep provenance unknown"));
        }
    }

    #[test]
    fn legacy_source_recovery_attaches_to_matching_source_only() {
        let mut sources = vec![
            SkillSourceSummary {
                source: "skills".to_string(),
                ..SkillSourceSummary::default()
            },
            SkillSourceSummary {
                source: "verified/source".to_string(),
                ..SkillSourceSummary::default()
            },
        ];
        attach_legacy_source_recovery(&mut sources).unwrap();
        assert_eq!(sources[0].recovery.as_ref().unwrap().status, "unresolved");
        assert!(sources[1].recovery.is_none());
        assert_eq!(
            sources[0].to_json()["recovery"]["provenance_change"],
            "none"
        );
    }

    #[test]
    fn route_quality_outcomes_distinguish_gaps_from_recovery() {
        assert_eq!(
            route_quality_outcome("must_match", true).unwrap(),
            "matched"
        );
        assert_eq!(
            route_quality_outcome("must_match", false).unwrap(),
            "missed"
        );
        assert_eq!(
            route_quality_outcome("known_gap", true).unwrap(),
            "now_matched"
        );
        assert_eq!(
            route_quality_outcome("known_gap", false).unwrap(),
            "still_missing"
        );
        assert!(route_quality_outcome("unexpected", false).is_err());
    }

    #[test]
    fn route_diagnostic_hits_include_only_skills_and_respect_limit() {
        let skill = mk_skill("example/skill", 1);
        let mut non_skill = mk_skill("example/non-skill", 1);
        non_skill.tags.clear();
        let rows = vec![
            MemorySearchHit {
                record: skill,
                score: 0.8,
                cosine: Some(0.7),
            },
            MemorySearchHit {
                record: non_skill,
                score: 1.0,
                cosine: None,
            },
        ];
        let payload = route_diagnostic_hits_json(&rows, 1);
        assert_eq!(payload.len(), 1);
        assert_eq!(payload[0]["key"], "skill:example/skill/x");
        let cosine = payload[0]["cosine"].as_f64().unwrap();
        assert!((cosine - 0.7).abs() < 1e-6);
    }

    #[test]
    fn route_quality_corpus_has_bilingual_required_and_gap_cases() {
        let corpus = parse_route_quality_corpus().unwrap();
        assert_eq!(corpus.schema_version, "skills-route-quality-v0");
        assert!(corpus
            .cases
            .iter()
            .any(|case| case.language == "en" && case.expectation == "must_match"));
        assert!(corpus
            .cases
            .iter()
            .any(|case| case.language == "zh" && case.expectation == "must_match"));
        assert!(corpus
            .cases
            .iter()
            .any(|case| case.expectation == "known_gap"));
        assert!(corpus
            .cases
            .iter()
            .all(|case| !case.expected_keys.is_empty()));

        let mut cases_by_pair = BTreeMap::<&str, Vec<&RouteQualityCase>>::new();
        for case in &corpus.cases {
            cases_by_pair.entry(&case.pair_id).or_default().push(case);
        }
        for pair in cases_by_pair.values() {
            assert_eq!(pair.len(), 2, "each pair must contain exactly two cases");
            let languages: BTreeSet<&str> =
                pair.iter().map(|case| case.language.as_str()).collect();
            assert_eq!(languages, BTreeSet::from(["en", "zh"]));
            assert_eq!(pair[0].expected_keys, pair[1].expected_keys);
        }
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

    #[test]
    fn partial_clone_plan_keeps_the_existing_fast_path() {
        let args = clone_args(
            "https://github.com/example/skills.git",
            Path::new("/tmp/skills"),
            Some("release"),
            CloneMode::Partial,
        );
        assert_eq!(
            args,
            vec![
                "clone",
                "--depth=1",
                "--quiet",
                "--filter=blob:none",
                "--branch",
                "release",
                "--single-branch",
                "https://github.com/example/skills.git",
                "/tmp/skills",
            ]
        );
    }

    #[test]
    fn full_clone_fallback_disables_filter_and_forces_http11() {
        let args = clone_args(
            "https://github.com/example/skills.git",
            Path::new("/tmp/skills"),
            None,
            CloneMode::FullHttp11,
        );
        assert_eq!(
            args[..6],
            [
                "-c",
                "http.version=HTTP/1.1",
                "clone",
                "--depth=1",
                "--quiet",
                "--single-branch"
            ]
        );
        assert!(!args.iter().any(|arg| arg == "--filter=blob:none"));
        assert_eq!(
            args[6..],
            ["https://github.com/example/skills.git", "/tmp/skills"]
        );
    }

    #[test]
    fn fallback_uses_remote_head_only_for_main() {
        assert_eq!(fallback_checkout_ref(Some("main")), None);
        assert_eq!(fallback_checkout_ref(Some("release")), Some("release"));
        assert_eq!(fallback_checkout_ref(None), None);
    }
}
