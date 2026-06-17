//! **Phase 1 P5 — Sleep replay (memory consolidation cron job).**
//!
//! Scans the `memory_coactivation` graph for tight clusters, asks the LLM
//! to synthesize a higher-order summary memory per cluster, then writes
//! `summarizes` edges from the summary back to each source. Sources also
//! get a `summarized_at:YYYY-MM-DD` tag so the next replay skips them.
//!
//! Designed to run nightly via cron (`0 4 * * *`), not in the live MCP
//! daemon. The cron entry opens its own short-lived sqlite handle (WAL
//! mode handles concurrent readers from the live MCP child).
//!
//! See `project_phase1_complete_p5_design_draft.md` for design rationale,
//! risk inventory, and the prompt template.

use ab_store::{default_db_path, MemoryRecord, SqliteStore, StateStore};
use anyhow::Result;
use std::collections::{BTreeMap, BTreeSet, HashMap};
use std::sync::Arc;
use std::time::{SystemTime, UNIX_EPOCH};

use crate::llm_client::{LlmClient, Message};

/// Cap on edges fetched from `top_coactivation_edges` per round. With ~5
/// avg cluster size this covers ~600 keys — plenty of room before the
/// `top_n` cutoff thins the candidate list.
const MAX_EDGES_FETCHED: u32 = 3_000;

/// Minimum edge `count` (Hebbian co-fire frequency) to participate in a
/// cluster. Filters away one-shot incidental coactivations.
const MIN_EDGE_COUNT: u64 = 2;

/// Hard cap on cluster size we'll try to consolidate. A cluster of >12
/// memories is more like a topic than a concept; the LLM will struggle to
/// synthesize one summary that covers all of them.
const MAX_CLUSTER_SIZE: usize = 12;

/// One contiguous cluster picked from the coactivation graph.
#[derive(Debug, Clone)]
pub struct Cluster {
    pub keys: Vec<String>,
    /// Sum of co-activation counts of all internal edges. Used to rank
    /// clusters before the `top_n` cutoff.
    pub total_weight: u64,
}

/// LLM-suggested summary for one cluster. Parsed from JSON.
#[derive(Debug, Clone)]
pub struct ClusterSummary {
    pub key: String,
    pub kind: String,
    pub tags: Vec<String>,
    pub body: String,
}

/// Public entry point — the dispatcher in `main.rs` calls this.
pub async fn run(top_n: usize, min_cluster_size: usize, dry_run: bool) -> Result<()> {
    if top_n == 0 {
        return Err(anyhow::anyhow!("--top-n must be ≥ 1"));
    }
    if min_cluster_size < 2 {
        return Err(anyhow::anyhow!("--min-cluster-size must be ≥ 2"));
    }

    let db_path = default_db_path();
    println!("# P5 dream replay  (top_n={top_n}, min_size={min_cluster_size}, dry_run={dry_run})");
    println!("DB: {}", db_path.display());

    let store = SqliteStore::open(&db_path)
        .await
        .map_err(|e| anyhow::anyhow!("open state.db at {db_path:?}: {e}"))?;
    let store: Arc<dyn StateStore> = Arc::new(store);

    let edges = store
        .top_coactivation_edges(MIN_EDGE_COUNT, MAX_EDGES_FETCHED)
        .await
        .map_err(|e| anyhow::anyhow!("top_coactivation_edges: {e}"))?;
    if edges.is_empty() {
        println!(
            "(no coactivation edges with count ≥ {MIN_EDGE_COUNT} — graph too sparse for replay)"
        );
        return Ok(());
    }
    println!("scanned {} candidate edges", edges.len());

    let clusters = build_clusters(&edges, min_cluster_size);
    println!(
        "formed {} raw clusters (size ≥ {min_cluster_size})",
        clusters.len()
    );

    let today_tag = today_tag();
    let mut accepted: Vec<(Cluster, Vec<MemoryRecord>)> = Vec::new();
    for cluster in clusters.iter() {
        if cluster.keys.len() > MAX_CLUSTER_SIZE {
            continue;
        }
        let members = load_members(store.as_ref(), &cluster.keys).await;
        if members.len() < min_cluster_size {
            continue;
        }
        if cluster_already_summarized(&members) {
            continue;
        }
        accepted.push((cluster.clone(), members));
        if accepted.len() >= top_n {
            break;
        }
    }
    println!(
        "after dedupe + size guard: {} clusters to summarize",
        accepted.len()
    );

    if accepted.is_empty() {
        println!("(nothing to do — all candidate clusters are already-summarized or out of range)");
        return Ok(());
    }

    if dry_run {
        for (i, (cluster, members)) in accepted.iter().enumerate() {
            println!();
            println!(
                "## cluster {}/{}  (weight={}, keys={})",
                i + 1,
                accepted.len(),
                cluster.total_weight,
                members.len()
            );
            for m in members {
                println!(
                    "  - [{kind}] {key}  (tags: {tags})",
                    kind = m.kind,
                    key = short(&m.key, 60),
                    tags = m.tags.join(", "),
                );
            }
        }
        println!();
        println!("(dry-run: no LLM calls, no writes)");
        return Ok(());
    }

    // Wet run: needs an LLM client (Anthropic or OpenAI-compat).
    let client =
        LlmClient::from_env().map_err(|e| anyhow::anyhow!("LLM client (P5 needs LLM): {e}"))?;
    println!("(LLM provider: {})", client.provider());

    let mut written = 0usize;
    for (i, (cluster, members)) in accepted.iter().enumerate() {
        println!();
        println!(
            "## consolidating cluster {}/{}  ({} members, weight={})",
            i + 1,
            accepted.len(),
            members.len(),
            cluster.total_weight
        );
        match summarize_cluster(&client, members).await {
            Ok(summary) => {
                match apply_summary(store.as_ref(), &summary, members, &today_tag).await {
                    Err(e) => eprintln!("  apply failed: {e}"),
                    Ok(canonical_key) => {
                        println!(
                            "  → wrote summary `{}` (llm_topic: `{}`, {} src edges)",
                            canonical_key,
                            summary.key,
                            members.len()
                        );
                        written += 1;
                    }
                }
            }
            Err(e) => {
                eprintln!("  LLM consolidation failed: {e}");
            }
        }
    }

    println!();
    println!("done — {} summary memories written", written);
    Ok(())
}

/// **Phase 1 P5 — dogfood metric.** Count clusters that would actually
/// be picked up by `dream replay` right now: union-find groups of size
/// ≥ `min_size`, after dropping `kind=skill` members and clusters where
/// majority are already summarized. This is the single number that tells
/// the user "is the coactivation graph dense enough yet for nightly
/// replay to do useful work?" — surfaced via `dream stats`.
///
/// Cheap when the graph is sparse (≤ a few cluster-member memory_get
/// calls). Bumps `access_count` as a side-effect of memory_get just like
/// dream_replay::run does.
pub async fn count_p5_ready_clusters(store: &dyn StateStore, min_size: usize) -> Result<usize> {
    if min_size < 2 {
        return Ok(0);
    }
    let edges = store
        .top_coactivation_edges(MIN_EDGE_COUNT, MAX_EDGES_FETCHED)
        .await
        .map_err(|e| anyhow::anyhow!("top_coactivation_edges: {e}"))?;
    if edges.is_empty() {
        return Ok(0);
    }
    let clusters = build_clusters(&edges, min_size);
    let mut ready = 0usize;
    for cluster in clusters.iter() {
        if cluster.keys.len() > MAX_CLUSTER_SIZE {
            continue;
        }
        let members = load_members(store, &cluster.keys).await;
        if members.len() < min_size {
            continue;
        }
        if cluster_already_summarized(&members) {
            continue;
        }
        ready += 1;
    }
    Ok(ready)
}

/// Build clusters via union-find over edges. Keeps total edge weight
/// per cluster (sum of `count`) so we can rank clusters by importance
/// before the `top_n` cutoff.
pub fn build_clusters(edges: &[ab_store::CoactivationEdge], min_size: usize) -> Vec<Cluster> {
    let mut uf = UnionFind::new();
    let mut weight_in_cluster: HashMap<String, u64> = HashMap::new();

    // First pass: build the disjoint sets + accumulate edge weight per
    // (eventual) cluster. We sum edge weight onto whichever endpoint —
    // after the union pass we re-aggregate by representative.
    for e in edges {
        uf.union(&e.key_a, &e.key_b);
        *weight_in_cluster.entry(e.key_a.clone()).or_insert(0) += e.count;
        *weight_in_cluster.entry(e.key_b.clone()).or_insert(0) += e.count;
    }

    // Group keys by representative.
    let mut by_root: BTreeMap<String, BTreeSet<String>> = BTreeMap::new();
    let mut weight_by_root: BTreeMap<String, u64> = BTreeMap::new();
    for (key, w) in &weight_in_cluster {
        let root = uf.find(key);
        by_root.entry(root.clone()).or_default().insert(key.clone());
        // Each edge contributes its count once to each endpoint, so we
        // double-count when summing per-key. Halve at the end to recover
        // total edge weight inside the cluster.
        *weight_by_root.entry(root).or_insert(0) += w;
    }

    let mut clusters: Vec<Cluster> = by_root
        .into_iter()
        .filter(|(_, set)| set.len() >= min_size)
        .map(|(root, set)| Cluster {
            keys: set.into_iter().collect(),
            total_weight: weight_by_root.get(&root).copied().unwrap_or(0) / 2,
        })
        .collect();

    // Heaviest first.
    clusters.sort_by(|a, b| b.total_weight.cmp(&a.total_weight));
    clusters
}

/// Members are loaded through the trait. `memory_get` does bump
/// `access_count` as a side-effect — that's fine for once-a-night
/// cron use.
///
/// `kind=skill` records are excluded from cluster membership (they are
/// reference material, not first-party agent memory; consolidating them
/// produces vague summaries that mix domains). Same exclusion P4 evolve
/// applies in `pick_evolution_neighbors`.
async fn load_members(store: &dyn StateStore, keys: &[String]) -> Vec<MemoryRecord> {
    let mut out = Vec::with_capacity(keys.len());
    for k in keys {
        match store.memory_get(k).await {
            Ok(Some(rec)) if rec.kind != "skill" => out.push(rec),
            Ok(_) => {} // skills excluded; missing key tolerated
            Err(_) => {}
        }
    }
    out
}

/// True if at least half the cluster is already summarized (any tag
/// starting with `summarized_at:`). Stricter than "any" so that a single
/// stale tag from a prior round doesn't permanently lock out the cluster
/// when new members are added.
pub fn cluster_already_summarized(members: &[MemoryRecord]) -> bool {
    if members.is_empty() {
        return true;
    }
    let n_summarized = members
        .iter()
        .filter(|m| m.tags.iter().any(|t| t.starts_with("summarized_at:")))
        .count();
    n_summarized * 2 >= members.len()
}

/// Stable short hash of a member-key set, used for the `dedupe:cluster:<hash>`
/// summary tag. Keys are sorted first so set-equal inputs hash identically
/// regardless of insertion order. djb2 — fast, small, no extra deps; the
/// dedupe tag is collision-tolerant (false collisions just collapse one
/// extra cluster pair, observable as a `supersedes` edge in the graph).
fn member_keys_hash(keys: &[String]) -> String {
    let mut sorted: Vec<&String> = keys.iter().collect();
    sorted.sort();
    let mut h: u64 = 5381;
    for k in &sorted {
        for b in k.as_bytes() {
            h = h.wrapping_mul(33).wrapping_add(*b as u64);
        }
        // Length-delimit so ["ab","c"] != ["a","bc"].
        h = h.wrapping_mul(33).wrapping_add(0xff);
    }
    format!("{h:016x}")
}

/// Today as `YYYY-MM-DD` UTC. Used for the `summarized_at:<date>` tag.
/// Inline date math (no chrono dep) — algorithm = Howard Hinnant's
/// civil_from_days, public domain.
fn today_tag() -> String {
    let now = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map(|d| d.as_secs() as i64)
        .unwrap_or(0);
    let (y, m, d) = ymd_from_unix(now);
    format!("summarized_at:{:04}-{:02}-{:02}", y, m, d)
}

fn ymd_from_unix(secs: i64) -> (i32, u32, u32) {
    let days = secs.div_euclid(86_400);
    let z = days + 719_468;
    let era = z.div_euclid(146_097);
    let doe = z - era * 146_097;
    let yoe = (doe - doe / 1_460 + doe / 36_524 - doe / 146_096) / 365;
    let y = yoe + era * 400;
    let doy = doe - (365 * yoe + yoe / 4 - yoe / 100);
    let mp = (5 * doy + 2) / 153;
    let d = (doy - (153 * mp + 2) / 5 + 1) as u32;
    let m = (if mp < 10 { mp + 3 } else { mp - 9 }) as u32;
    let y = (if m <= 2 { y + 1 } else { y }) as i32;
    (y, m, d)
}

/// Build the LLM prompt and call the chosen provider. Returns the parsed summary.
async fn summarize_cluster(client: &LlmClient, members: &[MemoryRecord]) -> Result<ClusterSummary> {
    let prompt = build_consolidation_prompt(members);
    let messages = vec![Message {
        role: "user".to_string(),
        content: prompt,
    }];
    let model = client.default_model();
    // 4096 leaves room for "thinking" models (minimax, deepseek-r1) that
    // burn budget before emitting the JSON. Anthropic Claude models
    // typically need <500.
    let resp = client
        .messages_create(&model, None, &messages, 4096)
        .await
        .map_err(|e| {
            anyhow::anyhow!("llm messages_create ({} / {model}): {e}", client.provider())
        })?;
    parse_summary_response(&resp.text).map_err(|reason| {
        anyhow::anyhow!("parse summary: {reason} (raw: {})", short(&resp.text, 200))
    })
}

pub fn build_consolidation_prompt(members: &[MemoryRecord]) -> String {
    fn truncate(s: &str, max: usize) -> String {
        let chars: Vec<char> = s.chars().collect();
        if chars.len() <= max {
            s.to_string()
        } else {
            let mut out: String = chars[..max].iter().collect();
            out.push_str(" …");
            out
        }
    }
    let n = members.len();
    let mut p = String::new();
    p.push_str(
        "You consolidate a co-activated memory cluster into ONE higher-order summary.\n\
         The members below have surfaced together in many search results, so they share \
         a concept. Your job: extract the SHARED idea, not list every member.\n\n",
    );
    p.push_str(&format!("CLUSTER ({n} members)\n"));
    for (i, m) in members.iter().enumerate() {
        p.push_str(&format!(
            "[{n}] key: {k}\n    kind: {kind}, tags: {tags}\n    body: {body}\n\n",
            n = i + 1,
            k = m.key,
            kind = m.kind,
            tags = m.tags.join(", "),
            body = truncate(&m.content, 400),
        ));
    }
    p.push_str(
        "Write a summary memory that captures the SHARED concept across these members.\n\
         Constraints:\n\
         - body: 200–600 chars, plain prose (no bullet lists)\n\
         - kind: pick ONE of `lesson` | `decision` | `architecture` | `context`\n\
         - tags: 2–5 short topic tags (lowercase, snake_case)\n\
         - key: format `summary_<topic_slug>_<YYYYMMDD>` where topic_slug is 2–4 words \
           snake_case describing the shared concept (e.g. `summary_p4_evolve_cache_pitfall_20260509`)\n\n\
         Return ONLY this JSON, no commentary, no markdown:\n\
         {\"key\": \"summary_…_YYYYMMDD\", \"kind\": \"lesson\", \"tags\": [\"a\", \"b\"], \"body\": \"…\"}\n",
    );
    p
}

/// Allowed `kind` values for a consolidation summary — mirrors the enum
/// stated in [`build_consolidation_prompt`]. Any other kind is an
/// instruction violation (or hallucination) and is rejected, not saved.
const SUMMARY_KINDS: [&str; 4] = ["lesson", "decision", "architecture", "context"];
/// Body length bounds (chars), mirroring the prompt's stated `200–600`.
const SUMMARY_BODY_MIN: usize = 200;
const SUMMARY_BODY_MAX: usize = 600;
/// Tag-count bounds, mirroring the prompt's stated `2–5`.
const SUMMARY_TAGS_MIN: usize = 2;
const SUMMARY_TAGS_MAX: usize = 5;

/// Strip optional ```json fences, extract the first {...} object, parse
/// the four required fields. Lenient about leading prose.
pub fn parse_summary_response(text: &str) -> std::result::Result<ClusterSummary, &'static str> {
    let trimmed = text.trim();
    let inner = trimmed
        .strip_prefix("```json")
        .or_else(|| trimmed.strip_prefix("```"))
        .unwrap_or(trimmed);
    let inner = inner.strip_suffix("```").unwrap_or(inner);
    let start = inner.find('{').ok_or("no JSON object")?;
    let end = inner.rfind('}').ok_or("no JSON object close")?;
    if end <= start {
        return Err("JSON braces in wrong order");
    }
    let json_slice = &inner[start..=end];

    let v: serde_json::Value = serde_json::from_str(json_slice).map_err(|_| "JSON parse failed")?;

    let key = v
        .get("key")
        .and_then(|x| x.as_str())
        .map(|s| s.trim().to_string())
        .filter(|s| !s.is_empty())
        .ok_or("missing or empty 'key'")?;
    let kind = v
        .get("kind")
        .and_then(|x| x.as_str())
        .map(|s| s.trim().to_string())
        .filter(|s| !s.is_empty())
        .ok_or("missing or empty 'kind'")?;
    let body = v
        .get("body")
        .and_then(|x| x.as_str())
        .map(|s| s.trim().to_string())
        .filter(|s| !s.is_empty())
        .ok_or("missing or empty 'body'")?;
    let tags: Vec<String> = v
        .get("tags")
        .and_then(|x| x.as_array())
        .map(|arr| {
            arr.iter()
                .filter_map(|t| t.as_str())
                .map(|s| s.trim().to_string())
                .filter(|s| !s.is_empty())
                .collect()
        })
        .unwrap_or_default();

    // G2 — enforce the prompt's OWN stated constraints
    // (`build_consolidation_prompt`). Previously these were advisory: parse
    // checked only non-empty presence, so a hallucinated kind, a one-sentence
    // body, or a tagless summary saved identically to a faithful one. Reject
    // (don't save) on violation; the caller logs the reason and skips the
    // cluster — graceful, no panic, no write, retried next run. The raw text
    // is echoed in the caller's wrap so the specific value stays visible.
    if !SUMMARY_KINDS.contains(&kind.as_str()) {
        return Err("kind not one of lesson|decision|architecture|context");
    }
    let body_len = body.chars().count();
    if body_len < SUMMARY_BODY_MIN || body_len > SUMMARY_BODY_MAX {
        return Err("body length outside 200..=600 chars");
    }
    if tags.len() < SUMMARY_TAGS_MIN || tags.len() > SUMMARY_TAGS_MAX {
        return Err("tag count outside 2..=5");
    }

    Ok(ClusterSummary {
        key,
        kind,
        tags,
        body,
    })
}

/// Reject a summary only when it sits dramatically further from the member
/// centroid than the loosest member itself. `0.5` ⇒ the summary may be up to
/// ~2× as far as the worst member before rejection — conservative on purpose so
/// that off-topic/hallucinated summaries are caught with near-zero false
/// rejects on faithful ones. Tunable later by autotune-v0 (G4).
const FAITHFULNESS_SAFETY_FRACTION: f32 = 0.5;

/// Verdict of the G3 faithfulness check (see [`faithfulness_verdict`]).
struct FaithfulnessVerdict {
    /// cosine(summary, member-centroid); meaningful only when `evaluated`.
    score: f32,
    /// self-calibrated accept floor (min member→centroid cosine × safety frac).
    floor: f32,
    /// the summary is faithful enough to keep.
    accept: bool,
    /// the check actually ran (false ⇒ degenerate input, fail-open accept).
    evaluated: bool,
}

/// **G3 — self-calibrating faithfulness check** in embedding space. A faithful
/// consolidation summary should sit inside the semantic neighbourhood of the
/// members it claims to summarize. The accept floor is derived from the
/// cluster's OWN cohesion (the loosest member's cosine to the centroid, scaled
/// by [`FAITHFULNESS_SAFETY_FRACTION`]), NOT a hand-set absolute threshold — so
/// it is robust to whichever embedding backend is active (ONNX vs hash) and
/// needs no calibration sign-off. Fail-OPEN on degenerate input (can't
/// calibrate ⇒ never block a write): empty summary vector, fewer than two
/// usable members, ragged dims, or a non-finite floor all accept. Pure ⇒
/// unit-testable without an embedder; the impure embed calls live in the caller.
fn faithfulness_verdict(summary: &[f32], members: &[Vec<f32>]) -> FaithfulnessVerdict {
    let pass = FaithfulnessVerdict {
        score: 0.0,
        floor: 0.0,
        accept: true,
        evaluated: false,
    };
    if summary.is_empty() {
        return pass;
    }
    // Fail-open on a degenerate (zero-norm) summary vector too — not just a
    // truly-empty one. `cosine_similarity` returns 0.0 for a zero vector, which
    // would otherwise read as "maximally off-topic" and REJECT a faithful
    // summary whose body merely happens to embed to zero (e.g. the hash backend
    // on punctuation-only text, or an unavailable backend returning zeros).
    // Mirrors the empty-vector guard above so the fail-open contract holds for
    // every degenerate input, not only the empty-slice case.
    let summary_norm: f32 = summary.iter().map(|x| x * x).sum::<f32>().sqrt();
    if summary_norm == 0.0 {
        return pass;
    }
    let dim = summary.len();
    let usable: Vec<&Vec<f32>> = members.iter().filter(|m| m.len() == dim).collect();
    if usable.len() < 2 {
        return pass;
    }
    let mut centroid = vec![0.0f32; dim];
    for m in &usable {
        for (c, x) in centroid.iter_mut().zip(m.iter()) {
            *c += *x;
        }
    }
    let n = usable.len() as f32;
    for c in centroid.iter_mut() {
        *c /= n;
    }
    let member_floor = usable
        .iter()
        .map(|m| ab_store::cosine_similarity(m, &centroid))
        .fold(f32::INFINITY, f32::min);
    if !member_floor.is_finite() {
        return pass;
    }
    let floor = member_floor * FAITHFULNESS_SAFETY_FRACTION;
    let score = ab_store::cosine_similarity(summary, &centroid);
    FaithfulnessVerdict {
        score,
        floor,
        accept: score >= floor,
        evaluated: true,
    }
}

/// **G1 — build the superseded backup record** that preserves a prior summary
/// before an in-place canonical-key overwrite. Pure (no store) so it is unit
/// testable. The canonical key is deterministic (same cluster → same key), so a
/// re-run upserts in place; the store's own dedupe-supersession only retires
/// *other* keys sharing a `dedupe_key`, so an in-place overwrite of THIS key
/// would silently drop the prior body. We snapshot it to a recoverable
/// `<canonical>_superseded_<contenthash>` row (status=`superseded` → auto-
/// dropped from search) pointing back via `superseded_by`, mirroring the
/// store's reconsolidation vocabulary. CRUCIAL: strip `dedupe:*` tags so that
/// saving this backup can't trigger the store's dedupe-supersession against the
/// still-active canonical row (which shares the same `dedupe:cluster:` tag).
fn build_clobber_backup(prior: &MemoryRecord, canonical_key: &str, today_tag: &str) -> MemoryRecord {
    let backup_key = format!(
        "{canonical_key}_superseded_{}",
        member_keys_hash(&[prior.content.clone()])
    );
    let mut tags: Vec<String> = prior
        .tags
        .iter()
        .filter(|t| !t.starts_with("dedupe:"))
        .cloned()
        .collect();
    if !tags.iter().any(|t| t == today_tag) {
        tags.push(today_tag.to_string());
    }
    MemoryRecord {
        key: backup_key,
        status: "superseded".to_string(),
        superseded_by: Some(canonical_key.to_string()),
        tags,
        ..prior.clone()
    }
}

/// Idempotent apply: save the summary, link sources via `summarizes`, tag
/// each source with `summarized_at:<today>` so the next replay skips this
/// cluster. All steps are best-effort — we log + continue on per-row failure.
async fn apply_summary(
    store: &dyn StateStore,
    summary: &ClusterSummary,
    members: &[MemoryRecord],
    today_tag: &str,
) -> Result<String> {
    let mut summary_tags = summary.tags.clone();
    if !summary_tags.iter().any(|t| t == "p5_replay") {
        summary_tags.push("p5_replay".to_string());
    }
    if !summary_tags.iter().any(|t| t == today_tag) {
        summary_tags.push(today_tag.to_string());
    }
    let importance = members.iter().map(|m| m.importance).fold(0.5_f64, f64::max);
    let related_keys: Vec<String> = members.iter().map(|m| m.key.clone()).collect();

    // Phase 2 #2 dedupe: derive the summary key deterministically from the
    // sorted member-key set. Same cluster (same member identity, regardless
    // of order) → same key → memory_save's key-based idempotence collapses
    // re-runs. The LLM's suggested key becomes a `llm_topic:<...>` tag so
    // human-readable topic info survives. This also handles the realistic
    // failure mode where `cluster_already_summarized` mis-fires (member tag
    // not yet propagated through FTS / re-clustering with shifted membership).
    let cluster_hash = member_keys_hash(&related_keys);
    let canonical_key = format!("summary_p5_cluster_{}", cluster_hash);
    let dedupe_tag = format!("dedupe:cluster:{}", cluster_hash);
    if !summary_tags.iter().any(|t| t == &dedupe_tag) {
        summary_tags.push(dedupe_tag);
    }
    if !summary.key.is_empty()
        && summary.key != canonical_key
        && !summary_tags.iter().any(|t| t.starts_with("llm_topic:"))
    {
        summary_tags.push(format!("llm_topic:{}", summary.key));
    }

    // G3 — faithfulness gate. A fact-summary can't be replayed like a skill, but
    // it CAN be checked for groundedness: a faithful summary sits in the same
    // embedding neighbourhood as the members it consolidates. Score it (always
    // tagged for observability + future autotune) and skip the write when the
    // summary is an egregious outlier (off-topic / hallucinated). Self-
    // calibrating + fail-open, so a faithful summary is essentially never lost.
    let summary_vec = ab_store::embed_text(&summary.body);
    let member_vecs: Vec<Vec<f32>> = members
        .iter()
        .map(|m| ab_store::embed_text(&m.content))
        .collect();
    let verdict = faithfulness_verdict(&summary_vec, &member_vecs);
    if verdict.evaluated {
        summary_tags.push(format!("faithfulness:{:.2}", verdict.score));
        if !verdict.accept {
            return Err(anyhow::anyhow!(
                "faithfulness gate rejected (score {:.2} < floor {:.2}; off-topic vs cluster) — summary skipped",
                verdict.score,
                verdict.floor
            ));
        }
    }

    let mem = MemoryRecord {
        key: canonical_key.clone(),
        kind: summary.kind.clone(),
        content: summary.body.clone(),
        tags: summary_tags,
        related_keys,
        scope: None,
        created_at: 0,
        updated_at: 0,
        last_accessed_at: 0,
        access_count: 0,
        importance,
        status: "active".to_string(),
        trigger_pattern: None,
        superseded_by: None,
    };

    // G1 — backup-before-clobber. If a different-bodied summary already lives
    // at this canonical key, snapshot it before the upsert overwrites it so a
    // worse re-run can never silently destroy a better prior summary. Best-
    // effort: a backup failure must not block the (idempotent) main write.
    if let Ok(Some(prior)) = store.memory_get(&canonical_key).await {
        if prior.content != mem.content {
            let backup = build_clobber_backup(&prior, &canonical_key, today_tag);
            let backup_key = backup.key.clone();
            if let Err(e) = store.memory_save(&backup).await {
                eprintln!("  backup-before-clobber {backup_key}: {e}");
            } else if let Err(e) = store
                .memory_link(&canonical_key, &backup_key, "supersedes", 1.5)
                .await
            {
                eprintln!("  supersedes edge {canonical_key}→{backup_key}: {e}");
            }
        }
    }

    store
        .memory_save(&mem)
        .await
        .map_err(|e| anyhow::anyhow!("memory_save({}): {e}", canonical_key))?;

    for src in members {
        if let Err(e) = store
            .memory_link(&canonical_key, &src.key, "summarizes", 1.0)
            .await
        {
            eprintln!("  memory_link {}↔{}: {e}", canonical_key, src.key);
        }
        // Tag-update by re-saving the source with the new tag appended.
        if src.tags.iter().any(|t| t == today_tag) {
            continue;
        }
        let mut new_tags = src.tags.clone();
        new_tags.push(today_tag.to_string());
        let updated = MemoryRecord {
            tags: new_tags,
            ..src.clone()
        };
        if let Err(e) = store.memory_save(&updated).await {
            eprintln!("  tag-update {}: {e}", src.key);
        }
    }
    Ok(canonical_key)
}

fn short(s: &str, max: usize) -> String {
    if s.chars().count() <= max {
        s.to_string()
    } else {
        let truncated: String = s.chars().take(max - 1).collect();
        format!("{truncated}…")
    }
}

/// Tiny union-find over String keys. Path compression but no union-by-rank
/// (cluster sizes here are tiny, ≤12).
struct UnionFind {
    parent: HashMap<String, String>,
}
impl UnionFind {
    fn new() -> Self {
        Self {
            parent: HashMap::new(),
        }
    }
    fn find(&mut self, x: &str) -> String {
        let mut node = x.to_string();
        // Walk to root.
        let mut path: Vec<String> = Vec::new();
        loop {
            let p = self
                .parent
                .entry(node.clone())
                .or_insert_with(|| node.clone())
                .clone();
            if p == node {
                break;
            }
            path.push(node.clone());
            node = p;
        }
        // Path compression.
        for n in path {
            self.parent.insert(n, node.clone());
        }
        node
    }
    fn union(&mut self, a: &str, b: &str) {
        let ra = self.find(a);
        let rb = self.find(b);
        if ra != rb {
            self.parent.insert(ra, rb);
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use ab_store::CoactivationEdge;

    fn edge(a: &str, b: &str, count: u64) -> CoactivationEdge {
        CoactivationEdge {
            key_a: a.into(),
            key_b: b.into(),
            count,
            first_at: 0,
            last_at: 0,
        }
    }

    #[test]
    fn build_clusters_groups_by_connected_component() {
        // Two disjoint triangles: {a,b,c} and {x,y,z}.
        let edges = vec![
            edge("a", "b", 5),
            edge("b", "c", 4),
            edge("a", "c", 3),
            edge("x", "y", 7),
            edge("y", "z", 6),
            edge("x", "z", 2),
        ];
        let clusters = build_clusters(&edges, 3);
        assert_eq!(clusters.len(), 2);
        // Sorted heaviest-first; xy/yz/xz total = 7+6+2 = 15 vs 5+4+3 = 12
        assert!(clusters[0].total_weight >= clusters[1].total_weight);
        assert_eq!(clusters[0].keys.len(), 3);
        assert_eq!(clusters[1].keys.len(), 3);
    }

    #[test]
    fn build_clusters_filters_below_min_size() {
        // Triangle + one isolated edge.
        let edges = vec![
            edge("a", "b", 5),
            edge("b", "c", 4),
            edge("a", "c", 3),
            edge("x", "y", 8), // pair-only, skipped at min_size=3
        ];
        let clusters = build_clusters(&edges, 3);
        assert_eq!(clusters.len(), 1);
        assert_eq!(clusters[0].keys.len(), 3);
    }

    #[test]
    fn build_clusters_chain_is_one_component() {
        // a-b-c-d-e chain → all five in one cluster.
        let edges = vec![
            edge("a", "b", 3),
            edge("b", "c", 3),
            edge("c", "d", 3),
            edge("d", "e", 3),
        ];
        let clusters = build_clusters(&edges, 3);
        assert_eq!(clusters.len(), 1);
        assert_eq!(clusters[0].keys.len(), 5);
    }

    fn mem_with_tags(key: &str, tags: &[&str]) -> MemoryRecord {
        MemoryRecord {
            key: key.into(),
            kind: "fact".into(),
            content: "x".into(),
            tags: tags.iter().map(|s| s.to_string()).collect(),
            related_keys: Vec::new(),
            scope: None,
            created_at: 0,
            updated_at: 0,
            last_accessed_at: 0,
            access_count: 0,
            importance: 0.5,
            status: "active".into(),
            trigger_pattern: None,
            superseded_by: None,
        }
    }

    #[test]
    fn faithfulness_accepts_summary_near_centroid() {
        let members = vec![
            vec![1.0, 0.0, 0.0],
            vec![0.9, 0.1, 0.0],
            vec![1.0, 0.1, 0.0],
        ];
        let summary = vec![0.95, 0.05, 0.0]; // sits among the members
        let v = faithfulness_verdict(&summary, &members);
        assert!(v.evaluated);
        assert!(v.accept, "faithful summary; score={} floor={}", v.score, v.floor);
    }

    #[test]
    fn faithfulness_rejects_orthogonal_summary() {
        // Proves the reject path actually fires (autotune-v0 §6 discipline).
        let members = vec![
            vec![1.0, 0.0, 0.0],
            vec![0.9, 0.1, 0.0],
            vec![1.0, 0.1, 0.0],
        ];
        let summary = vec![0.0, 0.0, 1.0]; // orthogonal → off-topic / hallucinated
        let v = faithfulness_verdict(&summary, &members);
        assert!(v.evaluated);
        assert!(
            !v.accept,
            "orthogonal summary must be rejected; score={} floor={}",
            v.score, v.floor
        );
    }

    #[test]
    fn faithfulness_fails_open_on_too_few_members() {
        // <2 usable members → can't establish cohesion → never block.
        let members = vec![vec![1.0, 0.0, 0.0]];
        let summary = vec![0.0, 0.0, 1.0];
        let v = faithfulness_verdict(&summary, &members);
        assert!(!v.evaluated);
        assert!(v.accept);
    }

    #[test]
    fn faithfulness_fails_open_on_empty_summary_embedding() {
        // Embedding unavailable → don't lose the summary.
        let members = vec![vec![1.0, 0.0, 0.0], vec![0.9, 0.1, 0.0]];
        let v = faithfulness_verdict(&[], &members);
        assert!(!v.evaluated);
        assert!(v.accept);
    }

    #[test]
    fn faithfulness_fails_open_on_zero_norm_summary() {
        // A NON-empty but all-zero summary vector (e.g. hash backend on
        // punctuation-only text, or a backend returning zeros) must NOT be read
        // as "maximally off-topic" and rejected — cosine() is 0.0 for it. The
        // fail-open contract has to cover zero-norm, not only the empty slice.
        let members = vec![vec![1.0, 0.0, 0.0], vec![0.9, 0.1, 0.0], vec![1.0, 0.1, 0.0]];
        let summary = vec![0.0, 0.0, 0.0]; // non-empty, zero norm
        let v = faithfulness_verdict(&summary, &members);
        assert!(!v.evaluated, "degenerate zero-norm summary must short-circuit");
        assert!(v.accept, "must fail-open, never reject a summary we can't score");
    }

    #[test]
    fn clobber_backup_strips_dedupe_tags_and_marks_superseded() {
        let mut prior = mem_with_tags(
            "summary_p5_cluster_abc",
            &[
                "p5_replay",
                "dedupe:cluster:abc",
                "llm_topic:foo",
                "summarized_at:2026-01-01",
            ],
        );
        prior.content = "the prior, better summary body".into();
        prior.kind = "lesson".into();
        let backup =
            build_clobber_backup(&prior, "summary_p5_cluster_abc", "summarized_at:2026-06-16");
        // dedupe tag stripped → saving the backup cannot dedupe-supersede the
        // still-active canonical row (the corruption trap).
        assert!(!backup.tags.iter().any(|t| t.starts_with("dedupe:")));
        // provenance tags kept.
        assert!(backup.tags.iter().any(|t| t == "p5_replay"));
        assert!(backup.tags.iter().any(|t| t == "llm_topic:foo"));
        // supersession vocabulary mirrors the store's reconsolidation path.
        assert_eq!(backup.status, "superseded");
        assert_eq!(
            backup.superseded_by.as_deref(),
            Some("summary_p5_cluster_abc")
        );
        // today tag appended.
        assert!(backup.tags.iter().any(|t| t == "summarized_at:2026-06-16"));
        // prior body + kind preserved (recoverable).
        assert_eq!(backup.content, "the prior, better summary body");
        assert_eq!(backup.kind, "lesson");
        // distinct, content-addressed key under the canonical namespace.
        assert!(backup.key.starts_with("summary_p5_cluster_abc_superseded_"));
        assert_ne!(backup.key, "summary_p5_cluster_abc");
    }

    #[test]
    fn clobber_backup_key_is_deterministic_by_content() {
        let mut a = mem_with_tags("k", &[]);
        a.content = "same body".into();
        let mut b = mem_with_tags("k", &["unrelated"]);
        b.content = "same body".into();
        // same content → same backup key (idempotent re-backup), regardless of
        // other fields differing.
        assert_eq!(
            build_clobber_backup(&a, "k", "t").key,
            build_clobber_backup(&b, "k", "t").key
        );
        let mut c = mem_with_tags("k", &[]);
        c.content = "different body".into();
        assert_ne!(
            build_clobber_backup(&a, "k", "t").key,
            build_clobber_backup(&c, "k", "t").key
        );
    }

    #[test]
    fn clobber_backup_does_not_duplicate_today_tag() {
        let mut prior = mem_with_tags("k", &["summarized_at:2026-06-16"]);
        prior.content = "body".into();
        let backup = build_clobber_backup(&prior, "k", "summarized_at:2026-06-16");
        let n = backup
            .tags
            .iter()
            .filter(|t| *t == "summarized_at:2026-06-16")
            .count();
        assert_eq!(n, 1);
    }

    #[test]
    fn cluster_already_summarized_majority_rule() {
        let members = vec![
            mem_with_tags("a", &["summarized_at:2026-05-09"]),
            mem_with_tags("b", &["summarized_at:2026-05-09"]),
            mem_with_tags("c", &[]),
        ];
        // 2 of 3 summarized → skip.
        assert!(cluster_already_summarized(&members));

        let mostly_fresh = vec![
            mem_with_tags("a", &["summarized_at:2026-05-08"]),
            mem_with_tags("b", &[]),
            mem_with_tags("c", &[]),
        ];
        // 1 of 3 summarized → still allow re-consolidation.
        assert!(!cluster_already_summarized(&mostly_fresh));
    }

    #[test]
    fn parse_summary_response_strips_fences_and_extracts_fields() {
        // Body must clear the 200-char floor (G2); keep the "fall back"
        // substring the assertion checks.
        let raw = "```json\n{\n  \"key\": \"summary_p4_evolve_cache_20260509\",\n  \
                   \"kind\": \"lesson\",\n  \"tags\": [\"p4\", \"cache\"],\n  \
                   \"body\": \"P4 evolve must fall back to the store when the in-memory \
                   cache is None, because a cold start or a cache eviction otherwise drops \
                   the write silently and the next read sees stale data; the shared lesson \
                   across these members is to treat the cache as an optimization, never the \
                   source of truth.\"\n}\n```";
        let s = parse_summary_response(raw).expect("parse ok");
        assert_eq!(s.key, "summary_p4_evolve_cache_20260509");
        assert_eq!(s.kind, "lesson");
        assert_eq!(s.tags, vec!["p4", "cache"]);
        assert!(s.body.contains("fall back"));
    }

    #[test]
    fn parse_summary_response_tolerates_leading_prose() {
        // Constraint-compliant fixture (G2): 2 tags + 200+ char body.
        let body = "y".repeat(250);
        let raw = format!(
            "Sure, here you go:\n{{\"key\":\"summary_x_20260509\",\"kind\":\"context\",\
             \"tags\":[\"a\",\"b\"],\"body\":\"{body}\"}}"
        );
        let s = parse_summary_response(&raw).expect("parse ok");
        assert_eq!(s.key, "summary_x_20260509");
    }

    #[test]
    fn parse_summary_response_rejects_missing_field() {
        let raw = "{\"key\":\"x\",\"kind\":\"\",\"tags\":[],\"body\":\"y\"}";
        let err = parse_summary_response(raw).expect_err("should reject empty kind");
        assert!(err.contains("kind"));
    }

    #[test]
    fn parse_summary_response_rejects_non_enum_kind() {
        // G2: a hallucinated kind no longer saves identically to a valid one.
        let body = "z".repeat(250);
        let raw = format!(
            "{{\"key\":\"summary_x_20260509\",\"kind\":\"banana\",\
             \"tags\":[\"a\",\"b\"],\"body\":\"{body}\"}}"
        );
        let err = parse_summary_response(&raw).expect_err("should reject non-enum kind");
        assert!(err.contains("kind"));
    }

    #[test]
    fn parse_summary_response_rejects_short_body() {
        // G2: a one-sentence body (LLM ignored the 200-char floor) is rejected.
        let raw = "{\"key\":\"summary_x_20260509\",\"kind\":\"lesson\",\
                   \"tags\":[\"a\",\"b\"],\"body\":\"too short to be a real summary\"}";
        let err = parse_summary_response(raw).expect_err("should reject short body");
        assert!(err.contains("body"));
    }

    #[test]
    fn parse_summary_response_rejects_overlong_body() {
        // G2: a 700-char body (likely "lists every member" — the exact failure
        // the prompt warns against) is rejected at the 600-char ceiling.
        let body = "w".repeat(700);
        let raw = format!(
            "{{\"key\":\"summary_x_20260509\",\"kind\":\"lesson\",\
             \"tags\":[\"a\",\"b\"],\"body\":\"{body}\"}}"
        );
        let err = parse_summary_response(&raw).expect_err("should reject overlong body");
        assert!(err.contains("body"));
    }

    #[test]
    fn parse_summary_response_rejects_too_few_tags() {
        // G2: a single-tag summary (LLM ignored the 2–5 instruction) is rejected.
        let body = "q".repeat(250);
        let raw = format!(
            "{{\"key\":\"summary_x_20260509\",\"kind\":\"lesson\",\
             \"tags\":[\"only_one\"],\"body\":\"{body}\"}}"
        );
        let err = parse_summary_response(&raw).expect_err("should reject <2 tags");
        assert!(err.contains("tag"));
    }

    #[test]
    fn parse_summary_response_rejects_too_many_tags() {
        // G2: a 6-tag summary exceeds the 5-tag ceiling.
        let body = "r".repeat(250);
        let raw = format!(
            "{{\"key\":\"summary_x_20260509\",\"kind\":\"lesson\",\
             \"tags\":[\"a\",\"b\",\"c\",\"d\",\"e\",\"f\"],\"body\":\"{body}\"}}"
        );
        let err = parse_summary_response(&raw).expect_err("should reject >5 tags");
        assert!(err.contains("tag"));
    }

    #[test]
    fn member_keys_hash_is_order_invariant() {
        let a = vec!["alpha".into(), "bravo".into(), "charlie".into()];
        let b = vec!["charlie".into(), "alpha".into(), "bravo".into()];
        assert_eq!(member_keys_hash(&a), member_keys_hash(&b));
    }

    #[test]
    fn member_keys_hash_distinguishes_different_sets() {
        let a = vec!["alpha".into(), "bravo".into()];
        let b = vec!["alpha".into(), "bravo".into(), "charlie".into()];
        assert_ne!(member_keys_hash(&a), member_keys_hash(&b));
    }

    #[test]
    fn member_keys_hash_length_delimits_concat_collisions() {
        // Without length delimiting, ["ab","c"] and ["a","bc"] would
        // hash identically under a naive byte-stream hash.
        let a = vec!["ab".into(), "c".into()];
        let b = vec!["a".into(), "bc".into()];
        assert_ne!(member_keys_hash(&a), member_keys_hash(&b));
    }
}
