//! **Consolidation middle — nightly digest-author draft queue (propose-only).**
//!
//! Synthesis-class queries ("回顾项目愿景…"-shaped) are answered by a SET of
//! scattered rows no retrieval mode can assemble (measured: the 62%-miss
//! class; connectivity diagnostic 2026-07-12). The write-side fix is a
//! consolidated `digest` row that IS the answer — validated by hand on S3
//! (`outcome_digest_answer_vehicle_prototype_validated_20260712`). This
//! module automates the authoring half: it picks under-served topics, asks
//! `claude -p` to synthesize a citation-ledger digest from real source rows,
//! and writes each result as a `digest_draft_<topic>` review row.
//!
//! **This module NEVER writes live `digest` rows.** Promotion is a separate,
//! eval-gated step (`scripts/eval/digest_gate.py`: shadow-DB copy, hit gate
//! rank≤5 on a target query, set_recall any_mode non-regression) followed by
//! a manual `memory_save` — see `docs/DESIGN-nightly-digest-author.md` §7.
//! `portfolio_state_digest` is explicitly outside this pipeline's territory
//! (manual-refresh discipline, `ab_writeside_digest_successor_no_advance_20260710`).
//!
//! Topic sources (deterministic, no LLM in the picker):
//!   - **T1** — synthesis eval fixture queries with no declared
//!     `answer_vehicle` (the measured coverage gap, 10/13 at design time).
//!   - **T2** — `memory_query_log` natural-language miss queries with
//!     count ≥ `min_miss_count` in the lookback window (bare-key lookups are
//!     get-misses, not synthesis misses — filtered out).
//!   - T3 (structural scatter clusters) is speced in the design doc and
//!     deliberately deferred: T1+T2 alone oversupply a top-3/night queue.
//!
//! Queue lifecycle (self-cleaning, mirrors `dream_distill`):
//!   - drafted-once: a topic with any existing draft row is never re-drafted;
//!     deleting the draft row re-queues the topic,
//!   - coverage dedup: a topic whose target query already surfaces a live
//!     digest (or `portfolio_state_digest`) in any mode's top-3 is skipped,
//!   - seed-overlap dedup: a topic whose seed set Jaccard-overlaps an
//!     existing live digest's `related_keys` above 0.6 is skipped.
//!
//! Kill switch: `AB_DIGEST_AUTHOR_DISABLE=1` exits before any read/write.
//! Rollback: every row this pipeline touches carries `derived:digest_author`.

use crate::dream_distill::{call_claude, corpus_index_line, strip_fences, today_batch_tag};
use ab_store::{default_db_path, MemoryListSort, MemoryRecord, SqliteStore, StateStore};
use anyhow::Result;
use std::collections::{HashMap, HashSet};
use std::sync::Arc;
use std::time::SystemTime;

/// Version tag stamped on every draft (`digest_prompt:v1`). Bump when the
/// template changes so draft quality can be compared across revisions.
pub const PROMPT_VERSION: &str = "v1";

const PROMPT_TEMPLATE: &str = include_str!("digest_assets/prompt_v1.md");

/// Kind of the queue rows this module writes.
pub const DRAFT_KIND: &str = "digest_draft";
const DRAFT_KEY_PREFIX: &str = "digest_draft_";
/// Kind of the promoted rows this module NEVER writes.
pub const LIVE_KIND: &str = "digest";
/// Rollback sweep tag — on drafts here, and on promoted rows via the gate.
pub const PIPELINE_TAG: &str = "derived:digest_author";
/// Outside pipeline territory: manual-refresh discipline (2026-07-10 ruling).
const PORTFOLIO_KEY: &str = "portfolio_state_digest";

/// Manifest caps: rows of FULL content shipped to the author. 12 rows /
/// 24k chars ≈ the S3 prototype's material volume; chars gate protects the
/// prompt from one pathological mega-row.
const MAX_MANIFEST_ROWS: usize = 12;
const MAX_MANIFEST_CHARS: usize = 24_000;
/// Per-mode search depth during assembly (same top-10 the eval measures).
const SEARCH_LIMIT: u32 = 10;
/// "Already covered": an existing digest in any mode's top-N for the query.
const COVERAGE_TOP_N: usize = 3;
/// Seed-set Jaccard overlap vs an existing digest's related_keys above this
/// = same topic, skip.
const SEED_OVERLAP_SKIP: f64 = 0.6;

/// Bookkeeping kinds never used as digest source material. Live digests are
/// also excluded: digest-of-digest chains would muddy the citation ledger
/// (each digest must cite primary rows; refresh goes through supersede).
const EXCLUDED_MANIFEST_KINDS: &[&str] = &[
    DRAFT_KIND,
    LIVE_KIND,
    "distill_draft",
    "work_memory",
    "session_handoff",
    "retrieval_feedback",
    "snapshot",
];

/// Where a topic came from (priority band is encoded in `score`).
#[derive(Debug, Clone, PartialEq)]
pub enum TopicSource {
    /// Eval fixture query with no declared answer_vehicle. Payload = fixture id.
    FixtureGap(String),
    /// Telemetry NL miss query. Payload = miss count in window.
    TelemetryMiss(u64),
}

#[derive(Debug, Clone)]
pub struct DigestTopic {
    /// Stable id for drafted-once semantics and the draft key.
    pub slug: String,
    pub source: TopicSource,
    /// Higher = picked first. T1 band starts at 1000, T2 at 100+count.
    pub score: f64,
    /// The retrieval need this digest must serve; fed to the author and to
    /// the promotion gate.
    pub target_queries: Vec<String>,
    /// Known-relevant keys (fixture gold_set for T1; empty for T2) — always
    /// included in the manifest regardless of search rank.
    pub seed_keys: Vec<String>,
}

/// Parsed + validated `claude -p` output for one topic.
#[derive(Debug, Clone, PartialEq)]
pub struct DigestVerdict {
    /// "author" | "decline"
    pub verdict: String,
    pub reasoning: String,
    pub draft: Option<ProposedDigestRow>,
    /// Raw model output (post fence-strip) — embedded in the draft record so
    /// the reviewer and the gate see exactly what the model said.
    pub raw_json: String,
}

/// The digest row an author verdict proposes.
#[derive(Debug, Clone, PartialEq)]
pub struct ProposedDigestRow {
    pub key: String,
    pub content: String,
    pub tags: Vec<String>,
    pub retrieval_trigger: String,
    pub source_keys: Vec<String>,
    pub target_queries: Vec<String>,
}

/// CLI options for one nightly run (see `DreamOp::Digest` in main.rs).
#[derive(Debug, Clone)]
pub struct DigestRunOpts {
    pub top_n: usize,
    pub dry_run: bool,
    pub timeout_secs: u64,
    /// Path to the synthesis eval fixture driving T1. Unreadable path is a
    /// logged skip, not an error (the nightly must not die on a repo move).
    pub fixtures: String,
    pub window_days: i64,
    pub min_miss_count: u64,
}

/// Public entry point — the dispatcher in `main.rs` calls this.
pub async fn run(opts: DigestRunOpts) -> Result<()> {
    if std::env::var("AB_DIGEST_AUTHOR_DISABLE").map(|v| v == "1") == Ok(true) {
        println!("# digest author disabled via AB_DIGEST_AUTHOR_DISABLE=1 — exiting");
        return Ok(());
    }
    if opts.top_n == 0 {
        return Err(anyhow::anyhow!("--top-n must be ≥ 1"));
    }
    let db_path = default_db_path();
    println!(
        "# digest author draft queue  (top_n={}, dry_run={}, prompt={PROMPT_VERSION})",
        opts.top_n, opts.dry_run
    );
    println!("DB: {}", db_path.display());

    let store = SqliteStore::open(&db_path)
        .await
        .map_err(|e| anyhow::anyhow!("open state.db at {db_path:?}: {e}"))?;
    let store: Arc<dyn StateStore> = Arc::new(store);

    // ── topic generation (deterministic) ──
    let mut topics: Vec<DigestTopic> = Vec::new();
    match std::fs::read_to_string(&opts.fixtures) {
        Ok(json) => match t1_topics_from_fixture_json(&json) {
            Ok(mut t1) => {
                println!("T1 fixture gaps: {} topic(s) from {}", t1.len(), opts.fixtures);
                topics.append(&mut t1);
            }
            Err(e) => println!("T1 skipped (fixture parse: {e})"),
        },
        Err(e) => println!("T1 skipped (fixture unreadable: {e})"),
    }
    let window_secs = opts.window_days.max(1) * 86_400;
    match store.memory_query_stats(window_secs).await {
        Ok(stats) => {
            let t2 = t2_topics_from_miss_queries(&stats.top_miss_queries, opts.min_miss_count);
            println!(
                "T2 telemetry misses: {} topic(s) (window {}d, min_count {})",
                t2.len(),
                opts.window_days,
                opts.min_miss_count
            );
            topics.extend(t2);
        }
        Err(e) => println!("T2 skipped (query stats: {e})"),
    }
    topics.sort_by(|a, b| b.score.total_cmp(&a.score).then(a.slug.cmp(&b.slug)));

    // ── exclusion state ──
    let draft_rows = store
        .list_memories(Some(DRAFT_KIND), MemoryListSort::Newest, 1_000)
        .await
        .unwrap_or_default();
    let drafted = drafted_topic_slugs(&draft_rows);
    let live_digests: Vec<MemoryRecord> = store
        .list_memories(Some(LIVE_KIND), MemoryListSort::Newest, 1_000)
        .await
        .unwrap_or_default()
        .into_iter()
        .filter(|r| r.status == "active")
        .collect();
    let mut covered_keys: HashSet<String> =
        live_digests.iter().map(|r| r.key.clone()).collect();
    covered_keys.insert(PORTFOLIO_KEY.to_string());
    let existing_digest_index = if live_digests.is_empty() {
        "(none)".to_string()
    } else {
        live_digests
            .iter()
            .map(|r| corpus_index_line(r))
            .collect::<Vec<_>>()
            .join("\n")
    };
    println!(
        "queue: {} topic(s) / prior drafts: {} / live digests: {}",
        topics.len(),
        draft_rows.len(),
        live_digests.len()
    );

    // ── assemble up to top_n workable topics ──
    let mut assembled: Vec<(DigestTopic, Vec<MemoryRecord>)> = Vec::new();
    for topic in &topics {
        if assembled.len() >= opts.top_n {
            break;
        }
        if drafted.contains(&topic.slug) {
            continue; // drafted-once
        }
        if let Some(hit) = seed_overlap_hit(&topic.seed_keys, &live_digests) {
            println!("  skip {} (seed overlap with live {hit})", topic.slug);
            continue;
        }
        // One search pass serves both the coverage check and the manifest.
        let mut ranked: HashMap<String, (usize, MemoryRecord)> = HashMap::new();
        let mut covered_by: Option<String> = None;
        for q in &topic.target_queries {
            for mode in ["fts", "hybrid", "semantic"] {
                let hits = match mode {
                    "hybrid" => store
                        .memory_search_hybrid(q, &[], SEARCH_LIMIT, 60.0, 10)
                        .await
                        .unwrap_or_default(),
                    "semantic" => store
                        .memory_search_semantic(q, SEARCH_LIMIT, 0.3)
                        .await
                        .unwrap_or_default(),
                    _ => store
                        .memory_search(q, &[], SEARCH_LIMIT)
                        .await
                        .unwrap_or_default(),
                };
                for (i, hit) in hits.into_iter().enumerate() {
                    if covered_by.is_none() && i < COVERAGE_TOP_N && covered_keys.contains(&hit.record.key)
                    {
                        covered_by = Some(hit.record.key.clone());
                    }
                    let rank = i + 1;
                    ranked
                        .entry(hit.record.key.clone())
                        .and_modify(|(best, _)| *best = (*best).min(rank))
                        .or_insert((rank, hit.record));
                }
            }
        }
        if let Some(k) = covered_by {
            println!("  skip {} (already covered by {k} in top-{COVERAGE_TOP_N})", topic.slug);
            continue;
        }
        // Seeds outrank everything (rank 0) — they are declared-relevant.
        for seed in &topic.seed_keys {
            if let Ok(Some(rec)) = store.memory_get(seed).await {
                ranked.insert(seed.clone(), (0, rec));
            }
        }
        let manifest = assemble_manifest(ranked.into_values().collect());
        if manifest.is_empty() {
            println!("  skip {} (no usable material)", topic.slug);
            continue;
        }
        assembled.push((topic.clone(), manifest));
    }

    if assembled.is_empty() {
        println!("(queue dry — no undrafted, uncovered topics with material)");
        return Ok(());
    }
    println!("picked {} topic(s):", assembled.len());
    for (t, m) in &assembled {
        println!("  - {} [{:?}] material={} rows", t.slug, t.source, m.len());
    }
    if opts.dry_run {
        println!("(dry-run — skipping claude -p and all writes)");
        return Ok(());
    }

    // ── author + write drafts ──
    let batch_tag = today_batch_tag();
    let mut ok = 0usize;
    let mut failed = 0usize;
    for (topic, manifest) in &assembled {
        let allowed: HashSet<String> = manifest.iter().map(|r| r.key.clone()).collect();
        let prompt = build_digest_prompt(
            &existing_digest_index,
            &topic.target_queries,
            &manifest_json(manifest),
        );
        let started = SystemTime::now();
        let out = call_claude(&prompt, opts.timeout_secs).await;
        let secs = started.elapsed().map(|d| d.as_secs_f64()).unwrap_or(0.0);
        let verdict = match out.and_then(|stdout| parse_digest_verdict(&stdout, &allowed)) {
            Ok(v) => v,
            Err(e) => {
                // No draft row on failure — the topic stays queued and the
                // next nightly run retries it.
                eprintln!("  {} FAILED after {:.1}s: {e}", topic.slug, secs);
                failed += 1;
                continue;
            }
        };
        let rec = build_digest_draft_record(topic, &verdict, manifest, &batch_tag, secs);
        let draft_key = rec.key.clone();
        let edge_targets: Vec<String> = rec
            .related_keys
            .iter()
            .filter(|k| allowed.contains(*k))
            .cloned()
            .collect();
        store
            .memory_save(&rec)
            .await
            .map_err(|e| anyhow::anyhow!("memory_save {draft_key}: {e}"))?;
        // Best-effort provenance edges; related_keys stays the source of truth.
        for src in &edge_targets {
            if let Err(e) = store.memory_link(&draft_key, src, "derived_from", 1.0).await {
                eprintln!("  edge {draft_key}→{src}: {e}");
            }
        }
        println!(
            "  {} → {} [{}{}] ({secs:.1}s)",
            topic.slug,
            draft_key,
            verdict.verdict,
            verdict
                .draft
                .as_ref()
                .map(|d| format!(" proposes {}", d.key))
                .unwrap_or_default(),
        );
        ok += 1;
    }
    println!("done: {ok} draft(s) written, {failed} failed (failed topics stay queued)");
    Ok(())
}

// ────────────────────────────── topic picker ──────────────────────────────

/// T1 — fixture queries with no declared answer_vehicle. Pure function over
/// the fixture JSON text so the parse is testable without a filesystem.
pub fn t1_topics_from_fixture_json(json: &str) -> Result<Vec<DigestTopic>> {
    let v: serde_json::Value =
        serde_json::from_str(json).map_err(|e| anyhow::anyhow!("bad fixture JSON: {e}"))?;
    let queries = v["queries"]
        .as_array()
        .ok_or_else(|| anyhow::anyhow!("fixture has no queries array"))?;
    let mut out = Vec::new();
    for (idx, q) in queries.iter().enumerate() {
        let has_vehicle = q["answer_vehicle"]
            .as_array()
            .map(|a| !a.is_empty())
            .unwrap_or(false);
        if has_vehicle {
            continue;
        }
        let (Some(id), Some(query)) = (q["id"].as_str(), q["query"].as_str()) else {
            continue;
        };
        let seed_keys: Vec<String> = q["gold_set"]
            .as_array()
            .map(|a| {
                a.iter()
                    .filter_map(|x| x.as_str().map(|s| s.to_string()))
                    .collect()
            })
            .unwrap_or_default();
        out.push(DigestTopic {
            slug: format!("t1_{}", sanitize_slug(id)),
            source: TopicSource::FixtureGap(id.to_string()),
            // Fixture order = curation order; earlier gaps first within T1.
            score: 1000.0 - idx as f64,
            target_queries: vec![query.to_string()],
            seed_keys,
        });
    }
    Ok(out)
}

/// T2 — telemetry NL miss queries. Bare-key lookups (`some_row_key_20260712`)
/// are get-misses, not synthesis misses; only natural-language queries count.
pub fn t2_topics_from_miss_queries(
    miss_queries: &[(String, u64)],
    min_count: u64,
) -> Vec<DigestTopic> {
    miss_queries
        .iter()
        .filter(|(q, count)| *count >= min_count && is_nl_miss_query(q))
        .map(|(q, count)| DigestTopic {
            slug: format!("t2_{:016x}", fnv1a64(q.trim())),
            source: TopicSource::TelemetryMiss(*count),
            score: 100.0 + *count as f64,
            target_queries: vec![q.trim().to_string()],
            seed_keys: Vec::new(),
        })
        .collect()
}

/// A query is natural language unless it is a bare key/identifier
/// (ASCII alphanumerics plus `_-.`). CJK and multi-word queries pass.
pub fn is_nl_miss_query(q: &str) -> bool {
    let t = q.trim();
    !t.is_empty()
        && !t
            .chars()
            .all(|c| c.is_ascii_alphanumeric() || matches!(c, '_' | '-' | '.'))
}

fn sanitize_slug(s: &str) -> String {
    s.to_lowercase()
        .chars()
        .map(|c| if c.is_ascii_alphanumeric() { c } else { '_' })
        .collect()
}

/// FNV-1a 64-bit — deterministic across runs/releases (std hashers are not),
/// which drafted-once semantics require.
pub fn fnv1a64(s: &str) -> u64 {
    let mut h: u64 = 0xcbf2_9ce4_8422_2325;
    for b in s.as_bytes() {
        h ^= u64::from(*b);
        h = h.wrapping_mul(0x100_0000_01b3);
    }
    h
}

/// Topic slugs already covered by any draft row — drafted-once semantics.
/// The slug travels in a `topic:<slug>` tag; the key prefix is the fallback
/// for rows whose tags were stripped.
pub fn drafted_topic_slugs(draft_rows: &[MemoryRecord]) -> HashSet<String> {
    let mut out = HashSet::new();
    for r in draft_rows.iter().filter(|r| r.kind == DRAFT_KIND) {
        for t in &r.tags {
            if let Some(slug) = t.strip_prefix("topic:") {
                out.insert(slug.to_string());
            }
        }
        if let Some(slug) = r.key.strip_prefix(DRAFT_KEY_PREFIX) {
            out.insert(slug.to_string());
        }
    }
    out
}

/// Seed-set Jaccard overlap vs each live digest's related_keys; above
/// [`SEED_OVERLAP_SKIP`] = same topic. Returns the overlapping digest's key.
pub fn seed_overlap_hit(seeds: &[String], live_digests: &[MemoryRecord]) -> Option<String> {
    if seeds.is_empty() {
        return None;
    }
    let seed_set: HashSet<&str> = seeds.iter().map(|s| s.as_str()).collect();
    for d in live_digests {
        let theirs: HashSet<&str> = d.related_keys.iter().map(|s| s.as_str()).collect();
        if theirs.is_empty() {
            continue;
        }
        let inter = seed_set.intersection(&theirs).count();
        let union = seed_set.union(&theirs).count();
        if union > 0 && inter as f64 / union as f64 > SEED_OVERLAP_SKIP {
            return Some(d.key.clone());
        }
    }
    None
}

// ─────────────────────────── material assembly ────────────────────────────

/// Order candidates by best rank (seeds carry rank 0), drop bookkeeping
/// kinds, and cap by rows and cumulative content chars.
pub fn assemble_manifest(mut ranked: Vec<(usize, MemoryRecord)>) -> Vec<MemoryRecord> {
    ranked.retain(|(_, r)| {
        r.status == "active"
            && !EXCLUDED_MANIFEST_KINDS.contains(&r.kind.as_str())
            && r.key != PORTFOLIO_KEY
    });
    ranked.sort_by(|a, b| a.0.cmp(&b.0).then(a.1.key.cmp(&b.1.key)));
    let mut out = Vec::new();
    let mut chars = 0usize;
    for (_, rec) in ranked {
        let len = rec.content.chars().count();
        if out.len() >= MAX_MANIFEST_ROWS || (!out.is_empty() && chars + len > MAX_MANIFEST_CHARS)
        {
            break;
        }
        chars += len;
        out.push(rec);
    }
    out
}

/// Manifest rows → the JSON array the prompt embeds (key/kind/scope/content).
pub fn manifest_json(manifest: &[MemoryRecord]) -> String {
    let arr: Vec<serde_json::Value> = manifest
        .iter()
        .map(|r| {
            serde_json::json!({
                "key": r.key,
                "kind": r.kind,
                "scope": r.scope,
                "content": r.content,
            })
        })
        .collect();
    serde_json::to_string_pretty(&arr).unwrap_or_default()
}

/// Assemble the full prompt from the versioned template.
pub fn build_digest_prompt(
    existing_digest_index: &str,
    target_queries: &[String],
    manifest_json: &str,
) -> String {
    let queries = target_queries
        .iter()
        .map(|q| format!("- {q}"))
        .collect::<Vec<_>>()
        .join("\n");
    PROMPT_TEMPLATE
        .replace("{EXISTING_DIGEST_INDEX}", existing_digest_index)
        .replace("{TARGET_QUERIES}", &queries)
        .replace("{MANIFEST}", manifest_json)
}

// ─────────────────────────── verdict validation ───────────────────────────

/// Parse + validate one `claude -p` output. Validation is the propose-only
/// contract's first line of defense — and the structural kill of the v21
/// "audit-loss" objection: a citation outside `allowed_keys` (the manifest)
/// can never become a queue row.
pub fn parse_digest_verdict(stdout: &str, allowed_keys: &HashSet<String>) -> Result<DigestVerdict> {
    let raw = strip_fences(stdout);
    let v: serde_json::Value =
        serde_json::from_str(raw).map_err(|e| anyhow::anyhow!("bad JSON: {e}"))?;
    let verdict = v["verdict"]
        .as_str()
        .ok_or_else(|| anyhow::anyhow!("missing verdict"))?
        .to_string();
    if !matches!(verdict.as_str(), "author" | "decline") {
        return Err(anyhow::anyhow!("unknown verdict `{verdict}`"));
    }
    let reasoning = v["reasoning"].as_str().unwrap_or("").to_string();
    let draft = match v.get("draft") {
        Some(serde_json::Value::Object(d)) => Some(parse_proposed_digest(d)?),
        _ => None,
    };
    if verdict == "author" {
        let d = draft
            .as_ref()
            .ok_or_else(|| anyhow::anyhow!("author verdict without draft"))?;
        if !d.key.starts_with("digest_") || d.key.len() <= "digest_".len() {
            return Err(anyhow::anyhow!("draft key `{}` must start with digest_", d.key));
        }
        if d.key.chars().any(char::is_whitespace) {
            return Err(anyhow::anyhow!("draft key `{}` contains whitespace", d.key));
        }
        if d.content.trim().is_empty() {
            return Err(anyhow::anyhow!("author draft has empty content"));
        }
        if !d.content.contains("空白") {
            return Err(anyhow::anyhow!(
                "author draft missing the mandatory 空白/未定 section"
            ));
        }
        if d.source_keys.is_empty() {
            return Err(anyhow::anyhow!("author draft has no source_keys"));
        }
        for k in &d.source_keys {
            if !allowed_keys.contains(k) {
                return Err(anyhow::anyhow!(
                    "source_keys contains `{k}` which is not in the manifest — \
                     fabricated citation, draft rejected"
                ));
            }
            if !d.content.contains(k.as_str()) {
                return Err(anyhow::anyhow!(
                    "source_keys lists `{k}` but the content never cites it — \
                     the ledger must cite every source"
                ));
            }
        }
        if d.target_queries.iter().all(|q| q.trim().is_empty()) {
            return Err(anyhow::anyhow!("author draft has no target_queries"));
        }
    }
    Ok(DigestVerdict {
        verdict,
        reasoning,
        draft,
        raw_json: raw.to_string(),
    })
}

fn parse_proposed_digest(
    d: &serde_json::Map<String, serde_json::Value>,
) -> Result<ProposedDigestRow> {
    let str_vec = |field: &str| -> Vec<String> {
        d.get(field)
            .and_then(|x| x.as_array())
            .map(|a| {
                a.iter()
                    .filter_map(|x| x.as_str().map(|s| s.to_string()))
                    .collect()
            })
            .unwrap_or_default()
    };
    Ok(ProposedDigestRow {
        key: d
            .get("key")
            .and_then(|x| x.as_str())
            .ok_or_else(|| anyhow::anyhow!("draft missing key"))?
            .to_string(),
        content: d
            .get("content")
            .and_then(|x| x.as_str())
            .unwrap_or("")
            .to_string(),
        tags: str_vec("tags"),
        retrieval_trigger: d
            .get("retrieval_trigger")
            .and_then(|x| x.as_str())
            .unwrap_or("")
            .to_string(),
        source_keys: str_vec("source_keys"),
        target_queries: str_vec("target_queries"),
    })
}

// ───────────────────────────── draft record ───────────────────────────────

/// Build the queue row for one verdict. The row is both the review packet
/// and the gate's input (the raw JSON block is what the gate materializes).
pub fn build_digest_draft_record(
    topic: &DigestTopic,
    v: &DigestVerdict,
    manifest: &[MemoryRecord],
    batch_tag: &str,
    secs: f64,
) -> MemoryRecord {
    let mut tags = vec![
        DRAFT_KIND.to_string(),
        PIPELINE_TAG.to_string(),
        format!("topic:{}", topic.slug),
        format!("verdict:{}", v.verdict),
        format!("digest_prompt:{PROMPT_VERSION}"),
        batch_tag.to_string(),
    ];
    if let Some(d) = &v.draft {
        tags.push(format!("proposes:{}", d.key));
    }
    let related_keys: Vec<String> = match &v.draft {
        Some(d) => d.source_keys.clone(),
        // Decline receipts keep the seeds (or the manifest head) so the
        // review surface can still show what was considered.
        None if !topic.seed_keys.is_empty() => topic.seed_keys.clone(),
        None => manifest.iter().take(5).map(|r| r.key.clone()).collect(),
    };
    let source_desc = match &topic.source {
        TopicSource::FixtureGap(id) => format!("T1 评测集载体缺口（fixture {id}）"),
        TopicSource::TelemetryMiss(count) => format!("T2 遥测 miss 簇（窗口内 {count} 次）"),
    };
    let action = match v.verdict.as_str() {
        "author" => {
            "跑评测门：python3 scripts/eval/digest_gate.py --draft-key <本行 key>；\
             双门 PASS 后由 agent 会话对活库 memory_save 该 digest 行（kind=digest，\
             tags 必含 digest + derived:digest_author，related_keys=source_keys）"
        }
        _ => "认可 decline 则给本行加 tag resolved:declined；不认可则删除本行让主题重新排队",
    };
    let queries = topic
        .target_queries
        .iter()
        .map(|q| format!("- {q}"))
        .collect::<Vec<_>>()
        .join("\n");
    let manifest_keys = manifest
        .iter()
        .map(|r| format!("- {} [{}]", r.key, r.kind))
        .collect::<Vec<_>>()
        .join("\n");
    let content = format!(
        "# digest 草稿（propose-only — 过评测门并人工晋升前不是 live digest）\n\n\
         - 主题: {} · {}\n\
         - 裁决: {}\n\
         - 理由: {}\n\
         - prompt: {PROMPT_VERSION} · claude -p 默认模型 · {secs:.1}s · {batch_tag}\n\n\
         ## 目标查询\n{}\n\n\
         ## 素材清单（模型只被允许引用这些 key）\n{}\n\n\
         ## 评审动作\n{}\n（执行后给本行加 resolved:promoted / resolved:declined；\
         删除本行会让主题重新排队）\n\n\
         ## 模型原始产出\n```json\n{}\n```\n",
        topic.slug,
        source_desc,
        v.verdict,
        if v.reasoning.is_empty() { "-" } else { &v.reasoning },
        queries,
        manifest_keys,
        action,
        v.raw_json,
    );
    MemoryRecord {
        key: format!("{DRAFT_KEY_PREFIX}{}", topic.slug),
        kind: DRAFT_KIND.to_string(),
        content,
        tags,
        related_keys,
        scope: None,
        created_at: 0,
        updated_at: 0,
        last_accessed_at: 0,
        access_count: 0,
        importance: 0.4,
        status: "active".to_string(),
        trigger_pattern: None,
        superseded_by: None,
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn rec(key: &str, kind: &str, tags: &[&str], related: &[&str]) -> MemoryRecord {
        MemoryRecord {
            key: key.into(),
            kind: kind.into(),
            content: format!("content of {key}"),
            tags: tags.iter().map(|s| s.to_string()).collect(),
            related_keys: related.iter().map(|s| s.to_string()).collect(),
            scope: None,
            created_at: 100,
            updated_at: 100,
            last_accessed_at: 0,
            access_count: 0,
            importance: 0.5,
            status: "active".into(),
            trigger_pattern: None,
            superseded_by: None,
        }
    }

    fn allowed(keys: &[&str]) -> HashSet<String> {
        keys.iter().map(|s| s.to_string()).collect()
    }

    // ── topic picker: T1 ──

    const FIXTURE: &str = r#"{
      "queries": [
        {"id": "S1", "query": "回顾项目愿景", "gold_set": ["a", "b"],
         "answer_vehicle": ["portfolio_state_digest"]},
        {"id": "S3", "query": "哪些图路线被证伪了？", "gold_set": ["c", "d"],
         "answer_vehicle": []},
        {"id": "S7", "query": "权限契约是什么？", "gold_set": ["e"]}
      ]
    }"#;

    #[test]
    fn t1_picks_only_vehicle_gaps_and_keeps_fixture_order() {
        let topics = t1_topics_from_fixture_json(FIXTURE).unwrap();
        assert_eq!(
            topics.iter().map(|t| t.slug.as_str()).collect::<Vec<_>>(),
            vec!["t1_s3", "t1_s7"],
            "declared-vehicle query S1 must be excluded (portfolio territory)"
        );
        assert!(topics[0].score > topics[1].score, "earlier fixture entry wins");
        assert_eq!(topics[0].seed_keys, vec!["c", "d"]);
        assert_eq!(topics[0].target_queries, vec!["哪些图路线被证伪了？"]);
        assert!(matches!(&topics[0].source, TopicSource::FixtureGap(id) if id == "S3"));
    }

    #[test]
    fn t1_rejects_malformed_fixture() {
        assert!(t1_topics_from_fixture_json("not json").is_err());
        assert!(t1_topics_from_fixture_json(r#"{"pairs": []}"#).is_err());
    }

    // ── topic picker: T2 ──

    #[test]
    fn t2_filters_bare_keys_and_low_counts() {
        let misses = vec![
            ("我们来检查记忆项目的当前状态".to_string(), 22u64),
            ("aiot_seed_track_closure_20260526".to_string(), 5),
            ("dbx AGPL".to_string(), 3),
            ("费米子".to_string(), 2),
            ("验证过的交付成果 PR 部署".to_string(), 3),
        ];
        let topics = t2_topics_from_miss_queries(&misses, 3);
        let slugs: Vec<&str> = topics.iter().map(|t| t.slug.as_str()).collect();
        assert_eq!(topics.len(), 3, "{slugs:?}");
        // bare key excluded even at count 5; CJK below min_count excluded
        assert!(topics.iter().all(|t| !t.target_queries[0].contains("aiot_seed")));
        assert!(topics[0].score > 100.0 + 21.0, "count feeds the score");
        assert!(matches!(topics[0].source, TopicSource::TelemetryMiss(22)));
    }

    #[test]
    fn nl_query_detection() {
        assert!(is_nl_miss_query("回顾项目愿景"));
        assert!(is_nl_miss_query("dbx AGPL"));
        assert!(is_nl_miss_query("why does decay fire"));
        assert!(!is_nl_miss_query("aiot_axis1a_r0_falsifier_20260526"));
        assert!(!is_nl_miss_query("v0.14.0"));
        assert!(!is_nl_miss_query("  "));
    }

    #[test]
    fn fnv_slug_is_stable_across_runs() {
        // Pinned expected value: drafted-once breaks if this ever drifts.
        assert_eq!(fnv1a64("abc"), 0xe71fa2190541574b);
        let a = format!("t2_{:016x}", fnv1a64("同一条查询"));
        let b = format!("t2_{:016x}", fnv1a64("同一条查询"));
        assert_eq!(a, b);
    }

    // ── exclusion semantics ──

    #[test]
    fn drafted_once_reads_topic_tags_and_key_prefix() {
        let rows = vec![
            rec("digest_draft_t1_s3", DRAFT_KIND, &["topic:t1_s3"], &[]),
            rec("digest_draft_legacy", DRAFT_KIND, &[], &[]),
            rec("unrelated", "lesson", &["topic:t1_s9"], &[]),
        ];
        let s = drafted_topic_slugs(&rows);
        assert!(s.contains("t1_s3"));
        assert!(s.contains("legacy"), "key prefix is the tag-stripped fallback");
        assert!(!s.contains("t1_s9"), "non-draft rows don't count");
    }

    #[test]
    fn seed_overlap_skips_same_topic_digest() {
        let live = vec![rec("digest_x", LIVE_KIND, &[], &["a", "b", "c"])];
        let hit = seed_overlap_hit(
            &["a".into(), "b".into(), "c".into(), "d".into()],
            &live,
        );
        assert_eq!(hit.as_deref(), Some("digest_x"), "3/4 jaccard = 0.75 > 0.6");
        assert!(seed_overlap_hit(&["x".into(), "y".into()], &live).is_none());
        assert!(seed_overlap_hit(&[], &live).is_none(), "seedless topics never match");
    }

    // ── manifest assembly ──

    #[test]
    fn manifest_orders_by_rank_and_drops_bookkeeping() {
        let mut archived = rec("gone", "lesson", &[], &[]);
        archived.status = "archived".into();
        let ranked = vec![
            (5, rec("fifth", "outcome", &[], &[])),
            (0, rec("seed", "decision", &[], &[])),
            (1, rec("digest_old", LIVE_KIND, &[], &[])),
            (1, rec("draft_row", DRAFT_KIND, &[], &[])),
            (1, rec(PORTFOLIO_KEY, "context", &[], &[])),
            (2, archived),
            (3, rec("third", "lesson", &[], &[])),
        ];
        let m = assemble_manifest(ranked);
        assert_eq!(
            m.iter().map(|r| r.key.as_str()).collect::<Vec<_>>(),
            vec!["seed", "third", "fifth"],
            "seeds first; digest/draft/portfolio/archived all excluded"
        );
    }

    #[test]
    fn manifest_caps_rows_and_chars() {
        let many: Vec<(usize, MemoryRecord)> = (0..20)
            .map(|i| (i, rec(&format!("k{i:02}"), "lesson", &[], &[])))
            .collect();
        assert_eq!(assemble_manifest(many).len(), MAX_MANIFEST_ROWS);

        let mut huge = rec("huge", "lesson", &[], &[]);
        huge.content = "机".repeat(MAX_MANIFEST_CHARS);
        let m = assemble_manifest(vec![(1, huge), (2, rec("small", "lesson", &[], &[]))]);
        assert_eq!(
            m.iter().map(|r| r.key.as_str()).collect::<Vec<_>>(),
            vec!["huge"],
            "chars cap stops after the first over-budget row but never yields empty"
        );
    }

    // ── prompt assembly ──

    #[test]
    fn prompt_replaces_all_placeholders() {
        let p = build_digest_prompt(
            "- digest_a | trigger: t | head: h",
            &["查询一".to_string(), "query two".to_string()],
            "[{\"key\":\"m1\"}]",
        );
        for leftover in ["{EXISTING_DIGEST_INDEX}", "{TARGET_QUERIES}", "{MANIFEST}"] {
            assert!(!p.contains(leftover), "unreplaced {leftover}");
        }
        assert!(p.contains("- 查询一\n- query two"));
        assert!(p.contains("[{\"key\":\"m1\"}]"));
        // the hard disciplines travelled with the template
        assert!(p.contains("引用账本体"));
        assert!(p.contains("空白/未定"));
        assert!(p.contains("decline 光荣"));
    }

    // ── verdict validation: the propose-only + anti-fabrication gate ──

    fn author_json(source_keys: &str, content: &str) -> String {
        format!(
            r#"{{"verdict":"author","reasoning":"ok","draft":{{
                "key":"digest_graph_routes_20260713","content":"{content}",
                "tags":["graph"],"retrieval_trigger":"graph / gnn",
                "source_keys":{source_keys},"target_queries":["哪些路线被证伪"]}}}}"#
        )
    }

    #[test]
    fn parse_author_happy_path_with_fences() {
        let body = author_json(
            r#"["row_a","row_b"]"#,
            "台账：结论一（→ row_a）；结论二（→ row_b）。空白/未定：X 未覆盖。",
        );
        let out = format!("```json\n{body}\n```");
        let v = parse_digest_verdict(&out, &allowed(&["row_a", "row_b", "row_c"])).unwrap();
        assert_eq!(v.verdict, "author");
        let d = v.draft.unwrap();
        assert_eq!(d.key, "digest_graph_routes_20260713");
        assert_eq!(d.source_keys, vec!["row_a", "row_b"]);
        assert_eq!(d.target_queries, vec!["哪些路线被证伪"]);
    }

    #[test]
    fn parse_kills_fabricated_citation() {
        // row_z is NOT in the manifest — the v21 audit-loss killer.
        let body = author_json(
            r#"["row_a","row_z"]"#,
            "结论（→ row_a）（→ row_z）。空白/未定：无。",
        );
        let err = parse_digest_verdict(&body, &allowed(&["row_a", "row_b"]))
            .unwrap_err()
            .to_string();
        assert!(err.contains("row_z") && err.contains("fabricated"), "{err}");
    }

    #[test]
    fn parse_kills_uncited_source_key() {
        // row_b is listed but never cited in the content — dead-weight ledger.
        let body = author_json(
            r#"["row_a","row_b"]"#,
            "只引用了一个（→ row_a）。空白/未定：无。",
        );
        let err = parse_digest_verdict(&body, &allowed(&["row_a", "row_b"]))
            .unwrap_err()
            .to_string();
        assert!(err.contains("row_b") && err.contains("never cites"), "{err}");
    }

    #[test]
    fn parse_rejects_malformed_shapes() {
        let ok_keys = allowed(&["row_a"]);
        // author without draft
        assert!(parse_digest_verdict(r#"{"verdict":"author","draft":null}"#, &ok_keys).is_err());
        // wrong key prefix
        assert!(parse_digest_verdict(
            &author_json(r#"["row_a"]"#, "x（→ row_a）空白/未定：无")
                .replace("digest_graph_routes_20260713", "pub_x"),
            &ok_keys
        )
        .is_err());
        // missing 空白 section
        assert!(parse_digest_verdict(
            &author_json(r#"["row_a"]"#, "只有台账（→ row_a）没有空缺段"),
            &ok_keys
        )
        .is_err());
        // empty source_keys
        assert!(
            parse_digest_verdict(&author_json("[]", "台账。空白/未定：无"), &ok_keys).is_err()
        );
        // unknown verdict / non-JSON
        assert!(parse_digest_verdict(r#"{"verdict":"maybe"}"#, &ok_keys).is_err());
        assert!(parse_digest_verdict("great digest!", &ok_keys).is_err());
    }

    #[test]
    fn parse_decline_minimal_form() {
        let v = parse_digest_verdict(
            r#"{"verdict":"decline","reasoning":"素材不成主题","draft":null}"#,
            &allowed(&[]),
        )
        .unwrap();
        assert_eq!(v.verdict, "decline");
        assert!(v.draft.is_none());
    }

    // ── draft record shape ──

    fn topic() -> DigestTopic {
        DigestTopic {
            slug: "t1_s3".into(),
            source: TopicSource::FixtureGap("S3".into()),
            score: 998.0,
            target_queries: vec!["哪些图路线被证伪了？".into()],
            seed_keys: vec!["c".into(), "d".into()],
        }
    }

    #[test]
    fn draft_record_author_shape() {
        let manifest = vec![rec("row_a", "decision", &[], &[]), rec("row_b", "outcome", &[], &[])];
        let v = DigestVerdict {
            verdict: "author".into(),
            reasoning: "why".into(),
            draft: Some(ProposedDigestRow {
                key: "digest_graph_routes_20260713".into(),
                content: "c".into(),
                tags: vec![],
                retrieval_trigger: String::new(),
                source_keys: vec!["row_a".into(), "row_b".into()],
                target_queries: vec!["q".into()],
            }),
            raw_json: "{}".into(),
        };
        let r = build_digest_draft_record(&topic(), &v, &manifest, "batch:2026-07-13", 95.0);
        assert_eq!(r.key, "digest_draft_t1_s3");
        assert_eq!(r.kind, DRAFT_KIND);
        assert_eq!(r.related_keys, vec!["row_a", "row_b"], "author → source_keys");
        for t in [
            "digest_draft",
            PIPELINE_TAG,
            "topic:t1_s3",
            "verdict:author",
            "digest_prompt:v1",
            "batch:2026-07-13",
            "proposes:digest_graph_routes_20260713",
        ] {
            assert!(r.tags.iter().any(|x| x == t), "missing tag {t}: {:?}", r.tags);
        }
        assert!(r.content.contains("propose-only"));
        assert!(r.content.contains("digest_gate.py"));
        assert!(r.content.contains("哪些图路线被证伪了？"));
    }

    #[test]
    fn draft_record_decline_keeps_seeds_as_audit_trail() {
        let manifest = vec![rec("row_a", "decision", &[], &[])];
        let v = DigestVerdict {
            verdict: "decline".into(),
            reasoning: "薄".into(),
            draft: None,
            raw_json: "{}".into(),
        };
        let r = build_digest_draft_record(&topic(), &v, &manifest, "batch:2026-07-13", 30.0);
        assert_eq!(r.related_keys, vec!["c", "d"], "decline → seeds");
        assert!(r.tags.iter().any(|t| t == "verdict:decline"));
        assert!(!r.tags.iter().any(|t| t.starts_with("proposes:")));
    }
}
