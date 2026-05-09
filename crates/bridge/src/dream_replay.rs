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

use ab_store::{
    default_db_path, MemoryRecord, SqliteStore, StateStore,
};
use anyhow::Result;
use std::collections::{BTreeMap, BTreeSet, HashMap};
use std::sync::Arc;
use std::time::{SystemTime, UNIX_EPOCH};

use crate::anthropic_api::{AnthropicClient, Message, DEFAULT_MODEL};

/// Pick the LLM model — `AGENT_BRIDGE_LLM_MODEL` env var overrides
/// [`DEFAULT_MODEL`]. Useful for routing to a free model on
/// alternate proxies (e.g. opencode-zen exposes `minimax-m2.5-free`)
/// when the user's primary Anthropic credit is unavailable.
fn pick_model() -> String {
    std::env::var("AGENT_BRIDGE_LLM_MODEL")
        .ok()
        .filter(|s| !s.is_empty())
        .unwrap_or_else(|| DEFAULT_MODEL.to_string())
}

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
    println!(
        "# P5 dream replay  (top_n={top_n}, min_size={min_cluster_size}, dry_run={dry_run})"
    );
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
    println!("formed {} raw clusters (size ≥ {min_cluster_size})", clusters.len());

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
    println!("after dedupe + size guard: {} clusters to summarize", accepted.len());

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

    // Wet run: needs the Anthropic client.
    let client = AnthropicClient::from_env()
        .map_err(|e| anyhow::anyhow!("Anthropic client (P5 needs LLM): {e}"))?;

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
                if let Err(e) = apply_summary(store.as_ref(), &summary, members, &today_tag).await
                {
                    eprintln!("  apply failed: {e}");
                } else {
                    println!("  → wrote summary `{}` ({} src edges)", summary.key, members.len());
                    written += 1;
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
pub async fn count_p5_ready_clusters(
    store: &dyn StateStore,
    min_size: usize,
) -> Result<usize> {
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
pub fn build_clusters(
    edges: &[ab_store::CoactivationEdge],
    min_size: usize,
) -> Vec<Cluster> {
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

/// Build the LLM prompt and call Anthropic. Returns the parsed summary.
async fn summarize_cluster(
    client: &AnthropicClient,
    members: &[MemoryRecord],
) -> Result<ClusterSummary> {
    let prompt = build_consolidation_prompt(members);
    let messages = vec![Message {
        role: "user".to_string(),
        content: prompt,
    }];
    let model = pick_model();
    // 4096 leaves room for "thinking" models (minimax, deepseek-r1) that
    // burn budget before emitting the JSON. Anthropic Claude models
    // typically need <500.
    let resp = client
        .messages_create(&model, None, &messages, 4096)
        .await
        .map_err(|e| anyhow::anyhow!("anthropic messages_create ({model}): {e}"))?;
    parse_summary_response(&resp.text)
        .map_err(|reason| anyhow::anyhow!("parse summary: {reason} (raw: {})", short(&resp.text, 200)))
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

    let v: serde_json::Value =
        serde_json::from_str(json_slice).map_err(|_| "JSON parse failed")?;

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

    Ok(ClusterSummary {
        key,
        kind,
        tags,
        body,
    })
}

/// Idempotent apply: save the summary, link sources via `summarizes`, tag
/// each source with `summarized_at:<today>` so the next replay skips this
/// cluster. All steps are best-effort — we log + continue on per-row failure.
async fn apply_summary(
    store: &dyn StateStore,
    summary: &ClusterSummary,
    members: &[MemoryRecord],
    today_tag: &str,
) -> Result<()> {
    let mut summary_tags = summary.tags.clone();
    if !summary_tags.iter().any(|t| t == "p5_replay") {
        summary_tags.push("p5_replay".to_string());
    }
    if !summary_tags.iter().any(|t| t == today_tag) {
        summary_tags.push(today_tag.to_string());
    }
    let importance = members
        .iter()
        .map(|m| m.importance)
        .fold(0.5_f64, f64::max);
    let related_keys: Vec<String> = members.iter().map(|m| m.key.clone()).collect();

    let mem = MemoryRecord {
        key: summary.key.clone(),
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

    store
        .memory_save(&mem)
        .await
        .map_err(|e| anyhow::anyhow!("memory_save({}): {e}", summary.key))?;

    for src in members {
        if let Err(e) = store
            .memory_link(&summary.key, &src.key, "summarizes", 1.0)
            .await
        {
            eprintln!("  memory_link {}↔{}: {e}", summary.key, src.key);
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
    Ok(())
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
        let raw = "```json\n{\n  \"key\": \"summary_p4_evolve_cache_20260509\",\n  \
                   \"kind\": \"lesson\",\n  \"tags\": [\"p4\", \"cache\"],\n  \
                   \"body\": \"P4 evolve must fall back to store when cache is None.\"\n}\n```";
        let s = parse_summary_response(raw).expect("parse ok");
        assert_eq!(s.key, "summary_p4_evolve_cache_20260509");
        assert_eq!(s.kind, "lesson");
        assert_eq!(s.tags, vec!["p4", "cache"]);
        assert!(s.body.contains("fall back"));
    }

    #[test]
    fn parse_summary_response_tolerates_leading_prose() {
        let raw = "Sure, here you go:\n{\"key\":\"summary_x_20260509\",\"kind\":\"context\",\
                   \"tags\":[\"a\"],\"body\":\"hello\"}";
        let s = parse_summary_response(raw).expect("parse ok");
        assert_eq!(s.key, "summary_x_20260509");
    }

    #[test]
    fn parse_summary_response_rejects_missing_field() {
        let raw = "{\"key\":\"x\",\"kind\":\"\",\"tags\":[],\"body\":\"y\"}";
        let err = parse_summary_response(raw).expect_err("should reject empty kind");
        assert!(err.contains("kind"));
    }
}
