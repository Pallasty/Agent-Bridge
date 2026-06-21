//! Goal C — OFFLINE, READ-ONLY whitening probe over the live e5 memory vectors.
//!
//! Falsifiable test of the #3746 root-cause: is the broken semantic recall
//! (R@10 0.11 « fts 0.67 on Mac) caused by e5-small embedding ANISOTROPY
//! (cosines saturate ~0.85, ranking near-random), and does cheap anisotropy
//! correction — mean-centering and "all-but-the-top-k" (ABTT, Mu et al. 2018) —
//! recover recall WITHOUT changing the embedder?
//!
//! Method. Load every `embedding_backend='multilingual-e5-small'` active vector
//! from the live store (the only rows in the e5 space; pre-v26 NULL-backend /
//! MiniLM rows live in a DIFFERENT space and are excluded so the transform is
//! estimated and tested on ONE space). Estimate the corpus mean μ and the top-k
//! principal directions (power iteration + deflation, no linalg crate). Then for
//! the SAME 18 held-out paraphrase cases `recall_eval` uses, rank each query
//! against the e5 corpus under: raw cosine / mean-centered / ABTT-1 / ABTT-5 /
//! ABTT-10, and report R@1/R@5/R@10 + MRR per transform.
//!
//! Honesty. (a) This ranks against the e5 SUBSET only — so the `raw` row here is
//! the control for "e5 over its own space", NOT the full-store number from
//! `recall_eval` (which also carries the 44% stale rows). The load-bearing
//! result is the DELTA raw→centered→ABTT, which isolates anisotropy. (b) Cases
//! whose designated key is not e5-indexed can never hit here; they are marked
//! `key∉e5` and excluded from the "answerable" aggregate. (c) Read-only: opens
//! the store, SELECTs, never writes. No production search-path change — if a
//! transform wins, the proven fix is handed to the memory-continuity lane.
//!
//!   AGENT_BRIDGE_ONNX_MODEL=e5-small \
//!     cargo run -p ab-bridge --example recall_whiten_probe --release

use ab_store::default_db_path;
use ab_store::vector::{cosine_similarity, decode_embedding, embed_text, warmup, VECTOR_DIM};
use std::collections::BTreeSet;
use std::path::PathBuf;
use tokio_rusqlite::Connection;

#[derive(Clone, Copy, PartialEq, Eq)]
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

struct Case {
    query: &'static str,
    expect: &'static [&'static str],
    tier: Tier,
}

// The same v2 held-out corpus as examples/recall_eval.rs (keys verified present
// in the live store 2026-06-19). Kept in sync by hand; this probe only needs
// (query, accept-set, tier).
const CORPUS: &[Case] = &[
    Case { query: "记忆系统应该追求记住更多,还是用更少上下文恢复正确状态", expect: &["ab_memory_continuity_cognitive_architecture_20260619", "curated_implicit_lessondc26f323"], tier: Tier::Hard },
    Case { query: "工具面太多了应该按什么维度归类收口,是直接删还是重新分级", expect: &["reference_ab_tool_surface_taxonomy_8class_retier_over_delete_20260618"], tier: Tier::Hard },
    Case { query: "某个工具 p95 延迟看着很高但调用样本很少要不要当成异常", expect: &["tool_atlas_low_sample_p95_classification_20260619"], tier: Tier::Moderate },
    Case { query: "codex 的核心工具集和原生能力重叠,该不该因为很少用就降级", expect: &["codex_essential_native_overlap_demotion_superseded_20260618", "mcp_codex_native_overlap_surface_narrowed_deployed_20260617"], tier: Tier::Hard },
    Case { query: "怎么查看 sibling 推到远端的文件内容又不影响我的工作树", expect: &["lesson_git_show_origin_master_read_without_pull_20260518"], tier: Tier::Hard },
    Case { query: "memory_search 突然报数据库列不存在的错误是什么原因", expect: &["lesson_memory_search_fts5_lens_column_drift_20260518"], tier: Tier::Moderate },
    Case { query: "多个 agent 在同一个 git 仓库一起干活 HEAD 争用怎么预防", expect: &["lesson_multi_agent_shared_git_worktree_head_contention"], tier: Tier::Hard },
    Case { query: "怎么远程给一个正在运行的长驻 agent 会话注入指令", expect: &["agentbridge_remote_session_steer_gap_20260529"], tier: Tier::Hard },
    Case { query: "agent-bridge 这个项目的核心愿景定位是什么", expect: &["agent_bridge_northstar_bidirectional_bridge_20260529"], tier: Tier::Hard },
    Case { query: "EdgeRazor 那篇论文有什么值得我们借鉴的地方", expect: &["aiot_edgerazor_borrow_eval_20260526"], tier: Tier::Moderate },
    Case { query: "kilo 和 codex 两个远程执行器一起用实测验证过吗", expect: &["kilo_codex_dual_executor_live_verified_20260531"], tier: Tier::Moderate },
    Case { query: "skills lint 有没有规则检查严格度但缺少 preflight 的情况", expect: &["skills_lint_rigor_preflight_rule_impl_20260528"], tier: Tier::Moderate },
    Case { query: "有没有一个全局通用的 TELLS 基线技能", expect: &["global_tells_baseline_skill_20260529"], tier: Tier::Moderate },
    Case { query: "biocortex 影子试验是只读的吗,会不会改默认检索顺序", expect: &["ab_memory_continuity_t5_biocortex_shadow_trial_20260619"], tier: Tier::Hard },
    Case { query: "palace 评审 artifact 从外部工具借鉴了哪些设计模式", expect: &["palace_review_artifact_external_patterns_20260618"], tier: Tier::Moderate },
    Case { query: "自检告警把 catalog 类记忆也算进计数导致误报", expect: &["lesson_c3_s2_self_check_counts_catalog_false_positive_20260518"], tier: Tier::Moderate },
    Case { query: "multi agent shared git worktree HEAD contention lesson", expect: &["lesson_multi_agent_shared_git_worktree_head_contention"], tier: Tier::Easy },
    Case { query: "agent bridge northstar bidirectional bridge vision", expect: &["agent_bridge_northstar_bidirectional_bridge_20260529"], tier: Tier::Easy },
];

const TOP_K: usize = 10;
const POWER_ITERS: usize = 40;

fn norm_in_place(v: &mut [f32]) {
    let n: f32 = v.iter().map(|x| x * x).sum::<f32>().sqrt();
    if n > 0.0 {
        for x in v.iter_mut() {
            *x /= n;
        }
    }
}

fn dot(a: &[f32], b: &[f32]) -> f32 {
    a.iter().zip(b).map(|(x, y)| x * y).sum()
}

/// Top-k principal directions of the centered corpus via power iteration with
/// deflation. Deterministic seed (no rng crate; resume-safe).
fn top_k_pcs(centered: &[Vec<f32>], k: usize) -> Vec<Vec<f32>> {
    let mut residual: Vec<Vec<f32>> = centered.to_vec();
    let mut pcs: Vec<Vec<f32>> = Vec::with_capacity(k);
    for j in 0..k {
        let mut u = vec![0f32; VECTOR_DIM];
        for (d, slot) in u.iter_mut().enumerate() {
            *slot = (d as f32 * 0.1 + j as f32 * 1.7).sin();
        }
        norm_in_place(&mut u);
        for _ in 0..POWER_ITERS {
            let mut w = vec![0f32; VECTOR_DIM];
            for x in &residual {
                let d = dot(x, &u);
                for (wi, xi) in w.iter_mut().zip(x) {
                    *wi += d * xi;
                }
            }
            norm_in_place(&mut w);
            u = w;
        }
        for x in residual.iter_mut() {
            let d = dot(x, &u);
            for (xi, ui) in x.iter_mut().zip(&u) {
                *xi -= d * ui;
            }
        }
        pcs.push(u);
    }
    pcs
}

/// center then strip the top-`k` principal directions (k=0 ⇒ mean-centered only).
fn apply(v: &[f32], mu: &[f32], pcs: &[Vec<f32>], k: usize) -> Vec<f32> {
    let mut x: Vec<f32> = v.iter().zip(mu).map(|(a, b)| a - b).collect();
    for u in pcs.iter().take(k) {
        let d = dot(&x, u);
        for (xi, ui) in x.iter_mut().zip(u) {
            *xi -= d * ui;
        }
    }
    x
}

#[derive(Default)]
struct Agg {
    r1: u32,
    r5: u32,
    r10: u32,
    rr: f64,
    ranks: Vec<Option<usize>>,
}
impl Agg {
    fn record(&mut self, rank: Option<usize>) {
        if let Some(r) = rank {
            if r <= 1 {
                self.r1 += 1;
            }
            if r <= 5 {
                self.r5 += 1;
            }
            if r <= 10 {
                self.r10 += 1;
            }
            self.rr += 1.0 / r as f64;
        }
        self.ranks.push(rank);
    }
}

/// rank the query vector against the (already-transformed) corpus; return the
/// 1-based rank of the first accept-set key, or None if outside top `TOP_K`.
fn rank_query(qv: &[f32], corpus: &[(String, Vec<f32>)], expect: &[&str]) -> Option<usize> {
    let mut scored: Vec<(f32, &str)> = corpus
        .iter()
        .map(|(k, v)| (cosine_similarity(qv, v), k.as_str()))
        .collect();
    scored.sort_by(|a, b| b.0.partial_cmp(&a.0).unwrap_or(std::cmp::Ordering::Equal));
    scored
        .iter()
        .take(TOP_K)
        .position(|(_, k)| expect.iter().any(|e| e == k))
        .map(|i| i + 1)
}

async fn confirm_real_embedder() -> bool {
    warmup();
    let a = "an old stale build overwrote the deployed binary file";
    let b = "a previous outdated compile clobbered the binary that was shipped";
    let c = "cats enjoy napping in a warm patch of afternoon sunlight";
    for _ in 0..60 {
        let (va, vb, vc) = (embed_text(a), embed_text(b), embed_text(c));
        let para = cosine_similarity(&va, &vb);
        let unrel = cosine_similarity(&va, &vc);
        if para > 0.45 && (para - unrel) > 0.15 {
            return true;
        }
        tokio::time::sleep(std::time::Duration::from_millis(1000)).await;
    }
    false
}

#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    let db_path: PathBuf = std::env::var("AB_BASELINE_DB")
        .ok()
        .map(PathBuf::from)
        .unwrap_or_else(default_db_path);

    // ── load the e5-space corpus (read-only) ────────────────────────────────
    let conn = Connection::open(&db_path).await?;
    let rows: Vec<(String, Vec<u8>)> = conn
        .call(|c| {
            let mut stmt = c.prepare(
                "SELECT key, embedding FROM memories \
                 WHERE status='active' AND embedding_backend='multilingual-e5-small' \
                   AND embedding IS NOT NULL",
            )?;
            let out = stmt
                .query_map([], |row| Ok((row.get::<_, String>(0)?, row.get::<_, Vec<u8>>(1)?)))?
                .collect::<Result<Vec<_>, _>>()?;
            Ok::<_, tokio_rusqlite::rusqlite::Error>(out)
        })
        .await?;

    let corpus_raw: Vec<(String, Vec<f32>)> = rows
        .into_iter()
        .map(|(k, b)| (k, decode_embedding(&b)))
        .filter(|(_, v)| v.len() == VECTOR_DIM)
        .collect();
    let n_corpus = corpus_raw.len();
    let e5_keys: BTreeSet<&str> = corpus_raw.iter().map(|(k, _)| k.as_str()).collect();

    if !confirm_real_embedder().await {
        eprintln!("ABORT: real e5 query embedder not confirmed (hash fallback would be garbage). Run with AGENT_BRIDGE_ONNX_MODEL=e5-small and the model present.");
        std::process::exit(2);
    }

    // ── estimate μ and top-k principal directions on the centered corpus ─────
    let mut mu = vec![0f32; VECTOR_DIM];
    for (_, v) in &corpus_raw {
        for (m, x) in mu.iter_mut().zip(v) {
            *m += x;
        }
    }
    for m in mu.iter_mut() {
        *m /= n_corpus.max(1) as f32;
    }
    // mean-cosine diagnostic: ‖μ‖ / mean‖v‖ — near 1.0 ⇒ severe anisotropy.
    let mu_norm: f32 = mu.iter().map(|x| x * x).sum::<f32>().sqrt();
    let mean_vnorm: f32 = corpus_raw
        .iter()
        .map(|(_, v)| v.iter().map(|x| x * x).sum::<f32>().sqrt())
        .sum::<f32>()
        / n_corpus.max(1) as f32;

    let centered: Vec<Vec<f32>> = corpus_raw
        .iter()
        .map(|(_, v)| v.iter().zip(&mu).map(|(a, b)| a - b).collect())
        .collect();
    let pcs = top_k_pcs(&centered, TOP_K);

    // ── build transformed corpora ───────────────────────────────────────────
    let variants: [(&str, usize, bool); 5] = [
        ("raw", 0, false),
        ("centered", 0, true),
        ("abtt-1", 1, true),
        ("abtt-5", 5, true),
        ("abtt-10", 10, true),
    ];
    // For each variant: transformed corpus + per-case agg over answerable cases.
    let answerable: Vec<bool> = CORPUS
        .iter()
        .map(|c| c.expect.iter().any(|e| e5_keys.contains(e)))
        .collect();
    let n_answerable = answerable.iter().filter(|a| **a).count();

    println!("# Goal C — e5 anisotropy whitening probe (offline, read-only)");
    println!("db:            {}", db_path.display());
    println!("e5 corpus:     {n_corpus} active multilingual-e5-small vectors");
    println!(
        "anisotropy:    ‖μ‖={mu_norm:.3}  mean‖v‖={mean_vnorm:.3}  ratio={:.3}  (→1.0 = severe)",
        mu_norm / mean_vnorm.max(1e-6)
    );
    println!(
        "cases:         {} total, {n_answerable} answerable (designated key is e5-indexed)",
        CORPUS.len()
    );
    println!("rank vs:       e5 subset only (isolates the transform; not the full-store recall_eval number)\n");

    println!(
        "## R@k over answerable cases (n={n_answerable}) — the load-bearing comparison"
    );
    println!("  {:<10} {:>7} {:>7} {:>7} {:>7}", "transform", "R@1", "R@5", "R@10", "MRR");

    let mut per_case_ranks: Vec<(String, Vec<Option<usize>>)> = Vec::new();
    for (i, case) in CORPUS.iter().enumerate() {
        per_case_ranks.push((case.query.chars().take(30).collect(), Vec::new()));
        let _ = i;
    }

    for (label, k, transform) in variants {
        let tcorpus: Vec<(String, Vec<f32>)> = if transform {
            corpus_raw
                .iter()
                .map(|(key, v)| (key.clone(), apply(v, &mu, &pcs, k)))
                .collect()
        } else {
            corpus_raw.clone()
        };
        let mut agg = Agg::default();
        for (i, case) in CORPUS.iter().enumerate() {
            let qraw = embed_text(case.query);
            let qv = if transform {
                apply(&qraw, &mu, &pcs, k)
            } else {
                qraw
            };
            let rank = rank_query(&qv, &tcorpus, case.expect);
            per_case_ranks[i].1.push(if answerable[i] { rank } else { None });
            if answerable[i] {
                agg.record(rank);
            }
        }
        let nf = n_answerable.max(1) as f64;
        println!(
            "  {:<10} {:>7.3} {:>7.3} {:>7.3} {:>7.3}",
            label,
            agg.r1 as f64 / nf,
            agg.r5 as f64 / nf,
            agg.r10 as f64 / nf,
            agg.rr / nf,
        );
    }

    // ── per-case first-hit rank matrix (answerable cases) ───────────────────
    println!("\n## Per-case first-hit rank (— = miss; columns = raw / centered / abtt-1/5/10)");
    println!(
        "  {:<4} {:<9} {:>5} {:>9} {:>7} {:>7} {:>8}  {}",
        "#", "tier", "raw", "centered", "abtt1", "abtt5", "abtt10", "query"
    );
    for (i, case) in CORPUS.iter().enumerate() {
        if !answerable[i] {
            continue;
        }
        let r = &per_case_ranks[i].1;
        let cell = |o: Option<usize>| o.map(|x| x.to_string()).unwrap_or_else(|| "—".into());
        println!(
            "  {:<4} {:<9} {:>5} {:>9} {:>7} {:>7} {:>8}  {}",
            i + 1,
            case.tier.label(),
            cell(r[0]),
            cell(r[1]),
            cell(r[2]),
            cell(r[3]),
            cell(r[4]),
            per_case_ranks[i].0,
        );
    }

    let skipped: Vec<usize> = (0..CORPUS.len()).filter(|i| !answerable[*i]).map(|i| i + 1).collect();
    if !skipped.is_empty() {
        println!(
            "\n  excluded (designated key not e5-indexed, needs reindex not whitening): #{}",
            skipped.iter().map(|i| i.to_string()).collect::<Vec<_>>().join(", #")
        );
    }
    println!("\n## Read");
    println!("  raw = e5 cosine over its own space (control). centered/abtt = anisotropy-corrected.");
    println!("  A rising R@k from raw→centered→abtt confirms anisotropy as the dominant cause and");
    println!("  names a cheap, embedder-preserving fix to hand to the memory-continuity lane.");

    Ok(())
}
