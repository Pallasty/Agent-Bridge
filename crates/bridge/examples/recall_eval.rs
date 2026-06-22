//! T0 increment-2 — DRIFT-FREE recall quality eval over a FIXED held-out corpus.
//!
//! Part of the memory-continuity architecture (`docs/design/
//! MEMORY_CONTINUITY_COGNITIVE_ARCHITECTURE_2026_06_19.md`, forum #115,
//! Open-Q #5). Companion to `examples/recall_baseline.rs`.
//!
//! WHY a second baseline producer. `recall_baseline.rs` reports the per-mode
//! hit_rate the system *logged* over a time window. That number is a true
//! description of telemetry, but it is NOT "current recall quality": a long
//! window aggregates queries issued across multiple binary versions and corpus
//! states. (The 30d `search_hybrid` hit_rate of 0.254 was live-falsified as a
//! stale-binary artifact — old binaries lacked the FTS OR-fallback and logged
//! misses the current binary hits; see memory
//! `t0_recall_baseline_per_mode_20260619`.) To measure the CURRENT binary
//! without that drift, you need a FIXED query set with KNOWN ground truth, run
//! against the live store right now — reproducible before/after any T1-T7
//! ranking change, and the ground truth a BioCortex shadow-trial needs to
//! measure lift against.
//!
//! WHAT it does. For a hand-curated corpus of `(query, expected_keys)` cases it
//! runs each of the three real retrieval modes (`fts` / `hybrid` / `semantic`)
//! against the live store and reports, per mode: R@1 / R@5 / R@10 (success@k =
//! is any expected key within the top k) and MRR (mean reciprocal rank of the
//! first expected key). It then prints a per-case rank matrix so the queries
//! each mode misses are visible, not hidden behind an average.
//!
//! Queries are intentionally PARAPHRASED (and mostly Chinese over a mixed
//! ZH/EN corpus) — they do not echo the memory's key tokens — so the eval
//! tests genuine query→memory vocabulary bridging, the LEVER-3 pain point, not
//! lexical echo.
//!
//! Surface-free + read-only: only SELECT-side store calls (`memory_search`,
//! `memory_search_hybrid`, `memory_search_semantic`). NO new MCP tool, NO
//! ranking change, NO writes.
//!
//! HONESTY CONTRACT. This is a hand-curated corpus (small N, single curator).
//! It measures recall on THESE cases on the CURRENT binary — not a
//! comprehensive IR collection. v2 hardens the v1 caveats: (a) cases carry a
//! difficulty `tier` (easy/moderate/hard) so worst-case (pure paraphrase) and
//! near-average (lexical-anchored) recall report separately, not as one mean;
//! (b) the v1 caveat "a miss might just be a near-dup also-correct memory
//! outranking the designated key" is now DISCHARGED by content-reading each miss
//! and adding any genuinely-also-correct key to that case's accept-set (see
//! case #4) — so a remaining miss is a verified TRUE miss, not a measurement
//! artifact; (c) easy controls reuse the hard cases' targets with the lexical
//! tokens restored, proving the hard-case gap is query→memory vocabulary
//! bridging (LEVER-3), not absent data. Read the per-case matrix, not just the
//! aggregate. No green-laundering: misses are printed; every accept-set addition
//! is justified inline and was verified via memory_get on 2026-06-19.
//!
//! ## Running (semantic needs the SAME model the prod store was indexed with)
//! The live store's embeddings were produced by `para-ml`
//! (`paraphrase-multilingual-MiniLM-L12-v2`); query embeddings must match or
//! cosines are meaningless. The daemon sets `AGENT_BRIDGE_ONNX_MODEL=para-ml`,
//! so this example must too:
//!
//!   AGENT_BRIDGE_ONNX_MODEL=para-ml \
//!     cargo run -p ab-bridge --example recall_eval
//!   # custom (e.g. copied) db:
//!   AB_BASELINE_DB=/tmp/state.copy.db AGENT_BRIDGE_ONNX_MODEL=para-ml \
//!     cargo run -p ab-bridge --example recall_eval
//!
//! If built `--no-default-features` (onnx-embed off) or the model dir is
//! absent, the embedding backend silently degrades to a hash backend whose
//! cosines are near-orthogonal garbage. The harness DETECTS this (backend name
//! + a paraphrase-cosine readiness probe) and SKIPS semantic with a clear note
//! rather than reporting a false R@k=0.

use ab_store::{MemoryEdge, SqliteStore, StateStore, default_db_path};
use std::collections::BTreeSet;
use std::path::PathBuf;

/// Query difficulty, set by how much lexical signal the paraphrase leaves for
/// FTS. `Easy` = the query echoes the memory's distinctive tokens (a control /
/// ceiling: proves the harness CAN retrieve when overlap exists). `Moderate` =
/// a partial lexical anchor survives. `Hard` = pure cross-vocabulary paraphrase,
/// no token echo — the LEVER-3 worst case.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
enum Tier {
    Easy,
    Moderate,
    Hard,
}

impl Tier {
    fn label(self) -> &'static str {
        match self {
            Tier::Easy => "easy",
            Tier::Moderate => "moderate",
            Tier::Hard => "hard",
        }
    }
}

/// One held-out recall case. `expect` is the ACCEPT-SET of memory keys that
/// genuinely answer `query`; a hit at rank `r` means the first accept-set key
/// appeared at position `r` (1-based) in the top-k result. Accept-set entries
/// beyond the primary designated key are added only after content-reading
/// (memory_get) confirms they are also-correct — never to inflate R@k.
struct Case {
    query: &'static str,
    expect: &'static [&'static str],
    tier: Tier,
}

/// v2 corpus — keys verified present in the live store on 2026-06-19 (queried
/// via memory_get). Cases 1-16 are the v1 paraphrase set, now tier-tagged; case
/// 4 gained a content-verified also-correct key; cases 17-18 are Easy lexical
/// controls reusing the hard cases #7/#9 targets to isolate the vocabulary gap.
const CORPUS: &[Case] = &[
    Case {
        query: "记忆系统应该追求记住更多,还是用更少上下文恢复正确状态",
        expect: &[
            "ab_memory_continuity_cognitive_architecture_20260619",
            "curated_implicit_lessondc26f323",
        ],
        tier: Tier::Hard,
    },
    Case {
        query: "工具面太多了应该按什么维度归类收口,是直接删还是重新分级",
        expect: &["reference_ab_tool_surface_taxonomy_8class_retier_over_delete_20260618"],
        tier: Tier::Hard,
    },
    Case {
        query: "某个工具 p95 延迟看着很高但调用样本很少要不要当成异常",
        expect: &["tool_atlas_low_sample_p95_classification_20260619"],
        tier: Tier::Moderate, // "p95" survives as a lexical anchor
    },
    Case {
        query: "codex 的核心工具集和原生能力重叠,该不该因为很少用就降级",
        expect: &[
            "codex_essential_native_overlap_demotion_superseded_20260618",
            // also-correct, verified 2026-06-19 via memory_get: the sibling
            // decision that DID demote cold codex native-overlap tools
            // (codebase_* Essential→Standard, commit 89de8fe). Same topic as the
            // query; a reader asking "should we demote codex's native-overlap
            // tools for coldness" would accept it. Not laundering — it is a
            // genuine answer, not merely a high-ranking distractor.
            "mcp_codex_native_overlap_surface_narrowed_deployed_20260617",
        ],
        tier: Tier::Hard,
    },
    Case {
        query: "怎么查看 sibling 推到远端的文件内容又不影响我的工作树",
        expect: &["lesson_git_show_origin_master_read_without_pull_20260518"],
        tier: Tier::Hard,
    },
    Case {
        query: "memory_search 突然报数据库列不存在的错误是什么原因",
        expect: &["lesson_memory_search_fts5_lens_column_drift_20260518"],
        tier: Tier::Moderate, // "memory_search" / "列" echo
    },
    Case {
        query: "多个 agent 在同一个 git 仓库一起干活 HEAD 争用怎么预防",
        expect: &["lesson_multi_agent_shared_git_worktree_head_contention"],
        tier: Tier::Hard,
    },
    Case {
        query: "怎么远程给一个正在运行的长驻 agent 会话注入指令",
        expect: &["agentbridge_remote_session_steer_gap_20260529"],
        tier: Tier::Hard,
    },
    Case {
        query: "agent-bridge 这个项目的核心愿景定位是什么",
        expect: &["agent_bridge_northstar_bidirectional_bridge_20260529"],
        tier: Tier::Hard,
    },
    Case {
        query: "EdgeRazor 那篇论文有什么值得我们借鉴的地方",
        expect: &["aiot_edgerazor_borrow_eval_20260526"],
        tier: Tier::Moderate, // "EdgeRazor" echo
    },
    Case {
        query: "kilo 和 codex 两个远程执行器一起用实测验证过吗",
        expect: &["kilo_codex_dual_executor_live_verified_20260531"],
        tier: Tier::Moderate, // "kilo" / "codex" echo
    },
    Case {
        query: "skills lint 有没有规则检查严格度但缺少 preflight 的情况",
        expect: &["skills_lint_rigor_preflight_rule_impl_20260528"],
        tier: Tier::Moderate, // "skills lint" / "preflight" echo
    },
    Case {
        query: "有没有一个全局通用的 TELLS 基线技能",
        expect: &["global_tells_baseline_skill_20260529"],
        tier: Tier::Moderate, // "TELLS" echo
    },
    Case {
        query: "biocortex 影子试验是只读的吗,会不会改默认检索顺序",
        expect: &["ab_memory_continuity_t5_biocortex_shadow_trial_20260619"],
        tier: Tier::Hard,
    },
    Case {
        query: "palace 评审 artifact 从外部工具借鉴了哪些设计模式",
        expect: &["palace_review_artifact_external_patterns_20260618"],
        tier: Tier::Moderate, // "palace" / "artifact" echo
    },
    Case {
        query: "自检告警把 catalog 类记忆也算进计数导致误报",
        expect: &["lesson_c3_s2_self_check_counts_catalog_false_positive_20260518"],
        tier: Tier::Moderate, // "catalog" / "计数" / "误报" echo
    },
    // ── Easy lexical controls (ceiling) ─────────────────────────────────────
    // Same targets as hard cases #7 and #9, with the distinctive tokens
    // restored. Case #7's paraphrase ranked fts@6 and case #9's MISSED; if these
    // controls hit high, the hard-case gap is vocabulary bridging (LEVER-3), not
    // absent data.
    Case {
        query: "multi agent shared git worktree HEAD contention lesson",
        expect: &["lesson_multi_agent_shared_git_worktree_head_contention"],
        tier: Tier::Easy,
    },
    Case {
        query: "agent bridge northstar bidirectional bridge vision",
        expect: &["agent_bridge_northstar_bidirectional_bridge_20260529"],
        tier: Tier::Easy,
    },
];

const TOP_K: usize = 10;
const GRAPH_NEIGHBOR_LIMIT: usize = 8;
const HASH_BACKEND_NAME: &str = "fnv1a-hash-384";
const REVIEW_GATE_TARGET_CASES: &[usize] = &[1, 2, 5, 9, 14];

/// Per-mode tallies accumulated across the corpus.
#[derive(Default)]
struct ModeAgg {
    r_at_1: u32,
    r_at_5: u32,
    r_at_10: u32,
    rr_sum: f64,
    /// rank (1-based) of the first expected key per case, or None on miss.
    ranks: Vec<Option<usize>>,
}

impl ModeAgg {
    fn record(&mut self, rank: Option<usize>) {
        if let Some(r) = rank {
            if r <= 1 {
                self.r_at_1 += 1;
            }
            if r <= 5 {
                self.r_at_5 += 1;
            }
            if r <= 10 {
                self.r_at_10 += 1;
            }
            self.rr_sum += 1.0 / r as f64;
        }
        self.ranks.push(rank);
    }
}

/// Offline candidate-set expansion: keep baseline FTS candidates in their
/// original order, then append direct graph neighbors that were not already
/// present. This is a yardstick for recall headroom, not a production ranker.
#[derive(Default)]
struct CandidateExpansionAgg {
    baseline_ranks: Vec<Option<usize>>,
    ranks: Vec<Option<usize>>,
    expanded_candidate_counts: Vec<usize>,
    graph_neighbor_row_count: usize,
}

impl CandidateExpansionAgg {
    fn record(
        &mut self,
        baseline_rank: Option<usize>,
        expanded_rank: Option<usize>,
        expanded_candidate_count: usize,
        graph_neighbor_row_count: usize,
    ) {
        self.baseline_ranks.push(baseline_rank);
        self.ranks.push(expanded_rank);
        self.expanded_candidate_counts
            .push(expanded_candidate_count);
        self.graph_neighbor_row_count += graph_neighbor_row_count;
    }
}

struct ExpandedCandidates {
    keys: Vec<String>,
    graph_neighbor_row_count: usize,
}

/// First 1-based rank at which any expected key appears in `keys`.
fn first_hit_rank(keys: &[String], expect: &[&str]) -> Option<usize> {
    keys.iter()
        .position(|k| expect.iter().any(|e| e == k))
        .map(|i| i + 1)
}

fn graph_neighbor_key<'a>(edge: &'a MemoryEdge, source_key: &str) -> Option<&'a str> {
    if edge.from_key == source_key {
        Some(edge.to_key.as_str())
    } else if edge.to_key == source_key {
        Some(edge.from_key.as_str())
    } else {
        None
    }
}

fn expand_baseline_with_graph_neighbors(
    baseline_keys: &[String],
    edges_by_baseline_key: &[Vec<MemoryEdge>],
    neighbor_limit: usize,
) -> ExpandedCandidates {
    let mut keys = baseline_keys.to_vec();
    let mut seen = baseline_keys.iter().cloned().collect::<BTreeSet<_>>();
    let mut graph_neighbor_row_count = 0usize;

    for (source_key, edges) in baseline_keys.iter().zip(edges_by_baseline_key) {
        for edge in edges.iter().take(neighbor_limit) {
            graph_neighbor_row_count += 1;
            let Some(neighbor_key) = graph_neighbor_key(edge, source_key) else {
                continue;
            };
            if seen.insert(neighbor_key.to_string()) {
                keys.push(neighbor_key.to_string());
            }
        }
    }

    ExpandedCandidates {
        keys,
        graph_neighbor_row_count,
    }
}

#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    let db_path: PathBuf = std::env::var("AB_BASELINE_DB")
        .ok()
        .map(PathBuf::from)
        .unwrap_or_else(default_db_path);

    // Action A (#3746 / Goal C U-surface): select the embed model the store was
    // actually indexed with, so semantic is MEASURED against the right vector
    // space instead of being silently SKIPPED on a host/model mismatch — a
    // hard-coded para-ml assumption is wrong for a Mac multilingual-e5-small
    // store and made the main continuity metric lie by omission. An explicit
    // caller `AGENT_BRIDGE_ONNX_MODEL` always wins.
    if std::env::var("AGENT_BRIDGE_ONNX_MODEL").is_err() {
        if let Some(alias) = detect_store_model_alias(&db_path).await {
            std::env::set_var("AGENT_BRIDGE_ONNX_MODEL", alias);
            println!(
                "# auto-selected AGENT_BRIDGE_ONNX_MODEL={alias} (store's dominant embedding_backend)"
            );
        }
    }

    let store = SqliteStore::open(&db_path).await?;
    let n = CORPUS.len();

    // ── Debug dump: `recall_eval <case#>` prints the top-k of each mode (key,
    // score, cosine) for one case, so a surprising R@k can be falsified —
    // is the expected key absent (cosine), present-but-buried (blend), or is
    // every cosine garbage (hash fallback)?
    if let Some(arg) = std::env::args().nth(1) {
        if let Ok(idx1) = arg.parse::<usize>() {
            return debug_case(&store, idx1).await;
        }
    }

    // ── Embedding backend gate (semantic only) ──────────────────────────────
    // Query embeddings MUST match the model the store was indexed with (auto-
    // selected above). If the active backend is hash (onnx-embed off, or model
    // dir missing), report that and skip semantic rather than emit a false R@k=0.
    let backend = ab_store::embedding::default_backend();
    let backend_name = backend.name().to_string();
    let semantic_ready = if backend_name == HASH_BACKEND_NAME {
        false
    } else {
        confirm_real_embedder().await
    };

    println!("# T0 recall eval — drift-free, fixed held-out corpus");
    println!("db:              {}", db_path.display());
    println!("corpus:          {n} cases (v2, tiered: easy/moderate/hard)");
    println!("top_k:           {TOP_K}");
    println!("embed backend:   {backend_name}");
    println!(
        "semantic:        {}",
        if semantic_ready {
            "ENABLED (real model confirmed)"
        } else if backend_name == HASH_BACKEND_NAME {
            "SKIPPED (hash backend — rebuild with default features + AGENT_BRIDGE_ONNX_MODEL=para-ml)"
        } else {
            "SKIPPED (model not confirmed loaded within timeout — cosines would be hash garbage)"
        }
    );
    println!();

    // ── Run each mode over the corpus ───────────────────────────────────────
    let mut fts = ModeAgg::default();
    let mut hybrid = ModeAgg::default();
    let mut semantic = ModeAgg::default();
    let mut fts_graph = CandidateExpansionAgg::default();
    let mut fts_candidate_counts = Vec::with_capacity(CORPUS.len());

    for case in CORPUS {
        let fts_keys = keys_of(store.memory_search(case.query, &[], TOP_K as u32).await?);
        let fts_rank = first_hit_rank(&fts_keys, case.expect);
        fts_candidate_counts.push(fts_keys.len());
        fts.record(fts_rank);

        let mut edges_by_fts_key = Vec::with_capacity(fts_keys.len());
        for key in &fts_keys {
            edges_by_fts_key.push(store.memory_neighbors(key).await.unwrap_or_default());
        }
        let expanded = expand_baseline_with_graph_neighbors(
            &fts_keys,
            &edges_by_fts_key,
            GRAPH_NEIGHBOR_LIMIT,
        );
        fts_graph.record(
            fts_rank,
            first_hit_rank(&expanded.keys, case.expect),
            expanded.keys.len(),
            expanded.graph_neighbor_row_count,
        );

        let hyb_keys = keys_of(
            store
                .memory_search_hybrid(case.query, &[], TOP_K as u32, 60.0, 10)
                .await?,
        );
        hybrid.record(first_hit_rank(&hyb_keys, case.expect));

        if semantic_ready {
            let sem_keys = keys_of(
                store
                    .memory_search_semantic(case.query, TOP_K as u32, 0.0)
                    .await?,
            );
            semantic.record(first_hit_rank(&sem_keys, case.expect));
        } else {
            semantic.record(None);
        }
    }

    // ── Aggregate table ─────────────────────────────────────────────────────
    println!("## Per-mode recall (success@k over {n} cases)");
    println!(
        "  {:<10} {:>7} {:>7} {:>7} {:>7}",
        "mode", "R@1", "R@5", "R@10", "MRR"
    );
    print_mode_row("fts", &fts, n);
    print_mode_row("hybrid", &hybrid, n);
    if semantic_ready {
        print_mode_row("semantic", &semantic, n);
    } else {
        println!(
            "  {:<10} {:>7} {:>7} {:>7} {:>7}",
            "semantic", "—", "—", "—", "—"
        );
    }
    println!();

    println!("## Offline candidate expansion (FTS + direct graph neighbors)");
    print_candidate_expansion_summary(&fts_graph, n);
    println!(
        "  mode contract: baseline candidates keep their FTS order; up to \
         {GRAPH_NEIGHBOR_LIMIT} direct graph-neighbor rows per baseline candidate \
         are appended after baseline and deduped. This does not change live \
         memory_search candidates or ranking."
    );
    println!();

    // ── Per-tier breakdown (worst-case paraphrase vs lexically-anchored) ─────
    // The single aggregate above blends pure-paraphrase (hard) and
    // lexical-anchor (moderate/easy) cases. Splitting by tier shows the
    // near-average recall and the worst-case recall as separate numbers, and the
    // easy controls give the harness ceiling.
    println!("## Per-tier recall (success@k, by query difficulty)");
    println!(
        "  {:<16} {:>4} {:>7} {:>7} {:>7} {:>7}",
        "mode/tier", "n", "R@1", "R@5", "R@10", "MRR"
    );
    for tier in [Tier::Easy, Tier::Moderate, Tier::Hard] {
        let idxs: Vec<usize> = CORPUS
            .iter()
            .enumerate()
            .filter(|(_, c)| c.tier == tier)
            .map(|(i, _)| i)
            .collect();
        if idxs.is_empty() {
            continue;
        }
        print_tier_row("fts", &fts, &idxs, tier.label());
        print_candidate_expansion_tier_row("fts+graph", &fts_graph, &idxs, tier.label());
        print_tier_row("hybrid", &hybrid, &idxs, tier.label());
        if semantic_ready {
            print_tier_row("semantic", &semantic, &idxs, tier.label());
        }
        println!();
    }

    // ── Per-case rank matrix (the detail the aggregate hides) ────────────────
    println!(
        "## Per-case first-hit rank (— = no hit; fts/hybrid/semantic are top {TOP_K}, fts+graph may be appended)"
    );
    println!(
        "  {:<4} {:<9} {:>5} {:>9} {:>7} {:>9}  {}",
        "#", "tier", "fts", "fts+graph", "hybrid", "semantic", "query"
    );
    for (i, case) in CORPUS.iter().enumerate() {
        let q: String = case.query.chars().take(34).collect();
        println!(
            "  {:<4} {:<9} {:>5} {:>9} {:>7} {:>9}  {}",
            i + 1,
            case.tier.label(),
            rank_cell(fts.ranks[i]),
            rank_cell(fts_graph.ranks[i]),
            rank_cell(hybrid.ranks[i]),
            if semantic_ready {
                rank_cell(semantic.ranks[i])
            } else {
                "n/a".to_string()
            },
            q
        );
    }
    println!();

    // ── Honest read ─────────────────────────────────────────────────────────
    let fts_miss: Vec<usize> = miss_indices(&fts);
    let hyb_miss: Vec<usize> = miss_indices(&hybrid);
    println!("## Honest read");
    println!(
        "  fts misses (not in top {TOP_K}): {} case(s){}",
        fts_miss.len(),
        fmt_idx(&fts_miss)
    );
    println!(
        "  hybrid misses (not in top {TOP_K}): {} case(s){}",
        hyb_miss.len(),
        fmt_idx(&hyb_miss)
    );
    let fts_graph_added = candidate_expansion_added_indices(&fts_graph);
    println!(
        "  offline fts+graph added hits over fts misses: {} case(s){}",
        fts_graph_added.len(),
        fmt_idx(&fts_graph_added)
    );
    if semantic_ready {
        let sem_miss = miss_indices(&semantic);
        println!(
            "  semantic misses (not in top {TOP_K}): {} case(s){}",
            sem_miss.len(),
            fmt_idx(&sem_miss)
        );
    }
    println!(
        "  miss audit (2026-06-19, content-read on this store): the v1 \"a miss \
         might be a near-dup also-correct outranking the designated key\" caveat \
         was discharged by reading each fts miss. Result: of the 6 v1 fts misses, \
         only #4 was a genuine also-correct outrank (now folded into its \
         accept-set, so it scores as a hit); the rest are VERIFIED TRUE misses — \
         #1/#2 returned 0 fts rows (no token overlap at all), #5/#9 surfaced \
         same-domain answer-wrong memories, and #8's designated key has \
         importance=0.122 and is buried by the importance/recency blend (LEVER-3). \
         So the headroom is real, not a scoring artifact."
    );
    print_runtime_gate_anchor(
        &fts,
        &fts_graph,
        &hybrid,
        &semantic,
        semantic_ready,
        &fts_candidate_counts,
    );
    println!(
        "  caveat: hand-curated corpus, N={n}. The hard tier is the worst case \
         (pure paraphrase); read the per-tier table and per-case matrix, not just \
         the overall mean."
    );

    Ok(())
}

fn keys_of(hits: Vec<ab_store::MemorySearchHit>) -> Vec<String> {
    hits.into_iter().map(|h| h.record.key).collect()
}

/// Falsification dump for one case (1-based): show the top-k of each mode with
/// score + cosine, and mark the expected key(s).
async fn debug_case(store: &SqliteStore, idx1: usize) -> Result<(), Box<dyn std::error::Error>> {
    let case = CORPUS
        .get(idx1.saturating_sub(1))
        .ok_or("case index out of range")?;
    println!("# debug case #{idx1}");
    println!("query:  {}", case.query);
    println!("expect: {:?}\n", case.expect);

    let dump = |label: &str, hits: &[ab_store::MemorySearchHit]| {
        println!("## {label} (top {})", hits.len());
        for (i, h) in hits.iter().enumerate() {
            let star = if case.expect.iter().any(|e| *e == h.record.key) {
                " <== EXPECTED"
            } else {
                ""
            };
            let cos = h
                .cosine
                .map(|c| format!("{c:.3}"))
                .unwrap_or_else(|| "  -  ".to_string());
            println!(
                "  {:>2}. score={:>7.3} cos={} {}{}",
                i + 1,
                h.score,
                cos,
                h.record.key,
                star
            );
        }
        println!();
    };

    dump(
        "fts",
        &store.memory_search(case.query, &[], TOP_K as u32).await?,
    );
    dump(
        "hybrid",
        &store
            .memory_search_hybrid(case.query, &[], TOP_K as u32, 60.0, 10)
            .await?,
    );
    let backend = ab_store::embedding::default_backend();
    if backend.name() != HASH_BACKEND_NAME && confirm_real_embedder().await {
        dump(
            "semantic",
            &store
                .memory_search_semantic(case.query, TOP_K as u32, 0.0)
                .await?,
        );
    } else {
        println!(
            "## semantic — skipped (backend {} not a confirmed real model)",
            backend.name()
        );
    }
    Ok(())
}

fn print_mode_row(label: &str, agg: &ModeAgg, n: usize) {
    let nf = n as f64;
    println!(
        "  {:<10} {:>7.3} {:>7.3} {:>7.3} {:>7.3}",
        label,
        agg.r_at_1 as f64 / nf,
        agg.r_at_5 as f64 / nf,
        agg.r_at_10 as f64 / nf,
        agg.rr_sum / nf,
    );
}

fn print_candidate_expansion_summary(agg: &CandidateExpansionAgg, n: usize) {
    let baseline_miss_count = agg
        .baseline_ranks
        .iter()
        .filter(|rank| rank.is_none())
        .count();
    let expanded_hit_count = agg.ranks.iter().filter(|rank| rank.is_some()).count();
    let added_hit_count = candidate_expansion_added_indices(agg).len();
    let rr_sum = agg
        .ranks
        .iter()
        .filter_map(|rank| rank.map(|r| 1.0 / r as f64))
        .sum::<f64>();
    let avg_candidates = if agg.expanded_candidate_counts.is_empty() {
        0.0
    } else {
        agg.expanded_candidate_counts.iter().sum::<usize>() as f64
            / agg.expanded_candidate_counts.len() as f64
    };
    let added_hit_rate = if baseline_miss_count == 0 {
        0.0
    } else {
        added_hit_count as f64 / baseline_miss_count as f64
    };
    println!(
        "  {:<18} {:>4} {:>7} {:>7} {:>7} {:>7} {:>9} {:>9}",
        "mode", "n", "hit", "added", "rate", "MRR", "avg_cand", "nbr_rows"
    );
    println!(
        "  {:<18} {:>4} {:>7.3} {:>7} {:>7.3} {:>7.3} {:>9.2} {:>9}",
        "fts+graph",
        n,
        expanded_hit_count as f64 / n as f64,
        added_hit_count,
        added_hit_rate,
        rr_sum / n as f64,
        avg_candidates,
        agg.graph_neighbor_row_count
    );
}

/// One row of the per-tier table: recompute R@k/MRR over just the case indices
/// in `idxs` from the already-recorded per-case ranks.
fn print_tier_row(mode: &str, agg: &ModeAgg, idxs: &[usize], tier: &str) {
    let (mut r1, mut r5, mut r10, mut rr) = (0u32, 0u32, 0u32, 0.0f64);
    for &i in idxs {
        if let Some(r) = agg.ranks[i] {
            if r <= 1 {
                r1 += 1;
            }
            if r <= 5 {
                r5 += 1;
            }
            if r <= 10 {
                r10 += 1;
            }
            rr += 1.0 / r as f64;
        }
    }
    let nf = idxs.len() as f64;
    println!(
        "  {:<16} {:>4} {:>7.3} {:>7.3} {:>7.3} {:>7.3}",
        format!("{mode}/{tier}"),
        idxs.len(),
        r1 as f64 / nf,
        r5 as f64 / nf,
        r10 as f64 / nf,
        rr / nf,
    );
}

fn print_candidate_expansion_tier_row(
    mode: &str,
    agg: &CandidateExpansionAgg,
    idxs: &[usize],
    tier: &str,
) {
    let mut r1 = 0u32;
    let mut r5 = 0u32;
    let mut r10 = 0u32;
    let mut rr = 0.0f64;
    for &i in idxs {
        if let Some(r) = agg.ranks[i] {
            if r <= 1 {
                r1 += 1;
            }
            if r <= 5 {
                r5 += 1;
            }
            if r <= 10 {
                r10 += 1;
            }
            rr += 1.0 / r as f64;
        }
    }
    let nf = idxs.len() as f64;
    println!(
        "  {:<16} {:>4} {:>7.3} {:>7.3} {:>7.3} {:>7.3}",
        format!("{mode}/{tier}"),
        idxs.len(),
        r1 as f64 / nf,
        r5 as f64 / nf,
        r10 as f64 / nf,
        rr / nf,
    );
}

fn rank_cell(rank: Option<usize>) -> String {
    match rank {
        Some(r) => r.to_string(),
        None => "—".to_string(),
    }
}

fn miss_indices(agg: &ModeAgg) -> Vec<usize> {
    agg.ranks
        .iter()
        .enumerate()
        .filter_map(|(i, r)| if r.is_none() { Some(i + 1) } else { None })
        .collect()
}

fn candidate_expansion_added_indices(agg: &CandidateExpansionAgg) -> Vec<usize> {
    agg.baseline_ranks
        .iter()
        .zip(&agg.ranks)
        .enumerate()
        .filter_map(|(i, (baseline, expanded))| {
            if baseline.is_none() && expanded.is_some() {
                Some(i + 1)
            } else {
                None
            }
        })
        .collect()
}

fn tier_indices(tier: Tier) -> Vec<usize> {
    CORPUS
        .iter()
        .enumerate()
        .filter_map(|(i, case)| if case.tier == tier { Some(i) } else { None })
        .collect()
}

fn recall_at_10_for_indices(ranks: &[Option<usize>], idxs: &[usize]) -> f64 {
    if idxs.is_empty() {
        return 0.0;
    }
    let hits = idxs
        .iter()
        .filter(|&&i| ranks.get(i).and_then(|rank| *rank).is_some_and(|r| r <= 10))
        .count();
    hits as f64 / idxs.len() as f64
}

fn miss_indices_for(ranks: &[Option<usize>], idxs: &[usize]) -> Vec<usize> {
    idxs.iter()
        .filter_map(|&i| {
            if ranks.get(i).is_some_and(|rank| rank.is_none()) {
                Some(i + 1)
            } else {
                None
            }
        })
        .collect()
}

fn hard_zero_fts_miss_indices(fts: &ModeAgg, fts_candidate_counts: &[usize]) -> Vec<usize> {
    tier_indices(Tier::Hard)
        .into_iter()
        .filter_map(|i| {
            if fts.ranks.get(i).is_some_and(|rank| rank.is_none())
                && fts_candidate_counts.get(i) == Some(&0)
            {
                Some(i + 1)
            } else {
                None
            }
        })
        .collect()
}

fn print_runtime_gate_anchor(
    fts: &ModeAgg,
    fts_graph: &CandidateExpansionAgg,
    hybrid: &ModeAgg,
    semantic: &ModeAgg,
    semantic_ready: bool,
    fts_candidate_counts: &[usize],
) {
    let hard_idxs = tier_indices(Tier::Hard);
    let hard_fts_misses = miss_indices_for(&fts.ranks, &hard_idxs);
    let hard_graph_added = miss_indices_for(&fts.ranks, &hard_idxs)
        .into_iter()
        .filter(|idx1| fts_graph.ranks[*idx1 - 1].is_some())
        .collect::<Vec<_>>();
    let hard_zero_rows = hard_zero_fts_miss_indices(fts, fts_candidate_counts);

    println!();
    println!("## Runtime gate anchor (main recall_eval hard tier)");
    println!(
        "  contract: future runtime retrieval changes can claim continuity lift \
         only if this main hard-tier anchor moves; trigger-cohort-only \
         improvement is decorative."
    );
    println!(
        "  hard-tier R@10: fts={:.3} fts+graph={:.3} hybrid={:.3} semantic={}",
        recall_at_10_for_indices(&fts.ranks, &hard_idxs),
        recall_at_10_for_indices(&fts_graph.ranks, &hard_idxs),
        recall_at_10_for_indices(&hybrid.ranks, &hard_idxs),
        if semantic_ready {
            format!(
                "{:.3}",
                recall_at_10_for_indices(&semantic.ranks, &hard_idxs)
            )
        } else {
            "n/a".to_string()
        }
    );
    println!(
        "  hard fts misses: {} case(s){}",
        hard_fts_misses.len(),
        fmt_idx(&hard_fts_misses)
    );
    println!(
        "  hard zero-row fts misses: {} case(s){}",
        hard_zero_rows.len(),
        fmt_idx(&hard_zero_rows)
    );
    println!(
        "  hard fts+graph added hits over fts misses: {} case(s){}",
        hard_graph_added.len(),
        fmt_idx(&hard_graph_added)
    );
    println!("  review gate targets (#3897):");
    for &idx1 in REVIEW_GATE_TARGET_CASES {
        let i = idx1 - 1;
        let q: String = CORPUS[i].query.chars().take(30).collect();
        println!(
            "    #{:<2} fts={:<3} rows={:<2} fts+graph={:<3} hybrid={:<3} semantic={:<3} {}",
            idx1,
            rank_cell(fts.ranks[i]),
            fts_candidate_counts.get(i).copied().unwrap_or_default(),
            rank_cell(fts_graph.ranks[i]),
            rank_cell(hybrid.ranks[i]),
            if semantic_ready {
                rank_cell(semantic.ranks[i])
            } else {
                "n/a".to_string()
            },
            q,
        );
    }
}

fn fmt_idx(idx: &[usize]) -> String {
    if idx.is_empty() {
        String::new()
    } else {
        format!(
            " → #{}",
            idx.iter()
                .map(|i| i.to_string())
                .collect::<Vec<_>>()
                .join(", #")
        )
    }
}

/// Kick off model init and poll a paraphrase-cosine probe until the REAL
/// multilingual model is confirmed loaded (a strong paraphrase pair separates
/// clearly from an unrelated pair) or a timeout elapses. The hash fallback
/// gives both pairs a near-zero cosine, so the gap — not an absolute threshold —
/// is the signal. Returns true only when the real model is confirmed.
/// Action A: detect the embed model the live store was indexed with so the
/// query embedder matches the stored vector space. Returns the
/// `AGENT_BRIDGE_ONNX_MODEL` alias for the dominant *tagged* backend among
/// active rows, or None when it is the default (all-MiniLM) or unknown.
/// Read-only; a brief separate connection so it runs before embedder init.
async fn detect_store_model_alias(db_path: &std::path::Path) -> Option<&'static str> {
    let conn = tokio_rusqlite::Connection::open(db_path).await.ok()?;
    let name: Option<String> = conn
        .call(|c| {
            let v = c
                .query_row(
                    "SELECT embedding_backend FROM memories \
                     WHERE status='active' AND embedding IS NOT NULL \
                       AND embedding_backend IS NOT NULL \
                     GROUP BY embedding_backend ORDER BY COUNT(*) DESC LIMIT 1",
                    [],
                    |row| row.get::<_, String>(0),
                )
                .ok();
            Ok::<_, tokio_rusqlite::rusqlite::Error>(v)
        })
        .await
        .ok()?;
    match name.as_deref() {
        Some("multilingual-e5-small") => Some("e5-small"),
        Some("paraphrase-multilingual-MiniLM-L12-v2") => Some("para-ml"),
        _ => None, // all-MiniLM-L6-v2 is the default; nothing to override
    }
}

async fn confirm_real_embedder() -> bool {
    use ab_store::vector::{cosine_similarity, embed_text, warmup};
    warmup();
    // Strong same-language paraphrase vs. an unrelated sentence.
    let a = "an old stale build overwrote the deployed binary file";
    let b = "a previous outdated compile clobbered the binary that was shipped";
    let c = "cats enjoy napping in a warm patch of afternoon sunlight";
    for _ in 0..30 {
        let va = embed_text(a);
        let vb = embed_text(b);
        let vc = embed_text(c);
        let para = cosine_similarity(&va, &vb);
        let unrel = cosine_similarity(&va, &vc);
        // Real model: paraphrase cosine high AND clearly above unrelated.
        if para > 0.45 && (para - unrel) > 0.15 {
            return true;
        }
        tokio::time::sleep(std::time::Duration::from_millis(1000)).await;
    }
    false
}

#[cfg(test)]
mod tests {
    use super::*;
    use ab_store::MemoryEdge;

    fn edge(from_key: &str, to_key: &str, weight: f64) -> MemoryEdge {
        MemoryEdge {
            from_key: from_key.to_string(),
            to_key: to_key.to_string(),
            edge_type: "relates".to_string(),
            weight,
        }
    }

    #[test]
    fn offline_candidate_expansion_appends_direct_graph_neighbors_after_baseline() {
        let baseline = vec!["source".to_string()];
        let edges = vec![vec![edge("source", "target", 1.0)]];

        let expanded = expand_baseline_with_graph_neighbors(&baseline, &edges, 8);

        assert_eq!(expanded.keys, vec!["source", "target"]);
        assert_eq!(expanded.graph_neighbor_row_count, 1);
        assert_eq!(
            first_hit_rank(&expanded.keys, &["target"]),
            Some(2),
            "the graph-only relevant key should be visible as an appended candidate"
        );
    }

    #[test]
    fn offline_candidate_expansion_preserves_baseline_and_dedupes_neighbors() {
        let baseline = vec!["source".to_string(), "already_baseline".to_string()];
        let edges = vec![
            vec![
                edge("source", "already_baseline", 1.0),
                edge("source", "target", 0.9),
                edge("source", "target", 0.8),
            ],
            vec![edge("already_baseline", "later", 0.7)],
        ];

        let expanded = expand_baseline_with_graph_neighbors(&baseline, &edges, 8);

        assert_eq!(
            expanded.keys,
            vec!["source", "already_baseline", "target", "later"]
        );
        assert_eq!(expanded.graph_neighbor_row_count, 4);
    }

    #[test]
    fn review_gate_targets_are_hard_cases() {
        for &idx1 in REVIEW_GATE_TARGET_CASES {
            let case = CORPUS.get(idx1 - 1).expect("target case exists");
            assert_eq!(case.tier, Tier::Hard);
        }
    }

    #[test]
    fn hard_zero_fts_miss_indices_reports_only_hard_zero_row_misses() {
        let mut fts = ModeAgg {
            ranks: vec![Some(1); CORPUS.len()],
            ..ModeAgg::default()
        };
        let mut counts = vec![10; CORPUS.len()];

        fts.ranks[0] = None; // hard, zero rows
        counts[0] = 0;
        fts.ranks[1] = None; // hard, but has rows
        counts[1] = 2;
        fts.ranks[2] = None; // moderate, zero rows
        counts[2] = 0;

        assert_eq!(hard_zero_fts_miss_indices(&fts, &counts), vec![1]);
    }

    #[test]
    fn recall_at_10_for_indices_counts_only_requested_cases() {
        let ranks = vec![Some(1), Some(11), None, Some(10)];
        assert_eq!(recall_at_10_for_indices(&ranks, &[0, 1, 2]), 1.0 / 3.0);
        assert_eq!(recall_at_10_for_indices(&ranks, &[3]), 1.0);
    }
}
