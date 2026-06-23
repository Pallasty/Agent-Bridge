//! Goal C / N3 cross-store — OFFLINE, READ-ONLY para-ml recall probe over the live store.
//!
//! Complements design-lead's e5 `recall_whiten_probe.rs` (Mac/e5) by answering two
//! falsifiable questions it deliberately does NOT, on the aio2/para-ml store:
//!
//!  Q1 — CROSS-STORE / N3 anisotropy. e5-small is provably anisotropic (‖μ‖≈0.906,
//!       ranking near-random; whitening helps). Does para-ml ALSO suffer it? If para-ml
//!       is geometrically healthy and whitening gives ~0 gain, the cross-node fix is
//!       "both nodes converge on para-ml", NOT "whiten e5". Same μ/ratio + raw/centered/
//!       ABTT-k diagnostic, on the para-ml subset.
//!
//!  Q2 — HASH-NOISE / M6. ~18% of active rows are fnv1a-hash-384 / NULL-backend: 384-d
//!       NOISE vectors in the SAME space that DO compete in the real production cosine
//!       path (whiten_probe excludes non-target rows; memory_top_k_cosine does not).
//!       Rank the corpus over para-ml-only vs full-mix to quantify the recall cost of
//!       the un-reindexed ~18% — a falsifiable case for (or against) reindexing them.
//!
//! Honesty: read-only (SELECT only), no production search-path change, no recall_eval.rs /
//! mcp_tools.rs touch. Ranks raw cosine (= memory_top_k_cosine semantics, no blend).
//! Helpers (μ / power-iteration PCA / ABTT / Agg / rank_query / confirm_real_embedder)
//! mirror recall_whiten_probe.rs so the two probes are directly comparable.
//!
//!   AGENT_BRIDGE_ONNX_MODEL=para-ml \
//!     cargo run -p ab-bridge --example recall_paraml_noise_probe --release

use ab_store::default_db_path;
use ab_store::vector::{cosine_similarity, decode_embedding, embed_text, vector_dim, warmup};
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

// Same v2 held-out corpus as examples/recall_eval.rs and recall_whiten_probe.rs
// (keys verified present in the live store 2026-06-19). Kept in sync by hand.
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
        tier: Tier::Moderate,
    },
    Case {
        query: "codex 的核心工具集和原生能力重叠,该不该因为很少用就降级",
        expect: &[
            "codex_essential_native_overlap_demotion_superseded_20260618",
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
        tier: Tier::Moderate,
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
        tier: Tier::Moderate,
    },
    Case {
        query: "kilo 和 codex 两个远程执行器一起用实测验证过吗",
        expect: &["kilo_codex_dual_executor_live_verified_20260531"],
        tier: Tier::Moderate,
    },
    Case {
        query: "skills lint 有没有规则检查严格度但缺少 preflight 的情况",
        expect: &["skills_lint_rigor_preflight_rule_impl_20260528"],
        tier: Tier::Moderate,
    },
    Case {
        query: "有没有一个全局通用的 TELLS 基线技能",
        expect: &["global_tells_baseline_skill_20260529"],
        tier: Tier::Moderate,
    },
    Case {
        query: "biocortex 影子试验是只读的吗,会不会改默认检索顺序",
        expect: &["ab_memory_continuity_t5_biocortex_shadow_trial_20260619"],
        tier: Tier::Hard,
    },
    Case {
        query: "palace 评审 artifact 从外部工具借鉴了哪些设计模式",
        expect: &["palace_review_artifact_external_patterns_20260618"],
        tier: Tier::Moderate,
    },
    Case {
        query: "自检告警把 catalog 类记忆也算进计数导致误报",
        expect: &["lesson_c3_s2_self_check_counts_catalog_false_positive_20260518"],
        tier: Tier::Moderate,
    },
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
const POWER_ITERS: usize = 40;
const PARA_ML: &str = "paraphrase-multilingual-MiniLM-L12-v2";

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
        let mut u = vec![0f32; vector_dim()];
        for (d, slot) in u.iter_mut().enumerate() {
            *slot = (d as f32 * 0.1 + j as f32 * 1.7).sin();
        }
        norm_in_place(&mut u);
        for _ in 0..POWER_ITERS {
            let mut w = vec![0f32; vector_dim()];
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
    }
    fn row(&self, label: &str, n: usize) {
        let nf = n.max(1) as f64;
        println!(
            "  {:<22} {:>7.3} {:>7.3} {:>7.3} {:>7.3}",
            label,
            self.r1 as f64 / nf,
            self.r5 as f64 / nf,
            self.r10 as f64 / nf,
            self.rr / nf,
        );
    }
}

/// rank the query vector against the corpus; return 1-based rank of first
/// accept-set key, or None if outside top `TOP_K`.
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

    // ── load every active embedded row + its backend (read-only) ────────────
    let conn = Connection::open(&db_path).await?;
    let rows: Vec<(String, Option<String>, Vec<u8>)> = conn
        .call(|c| {
            let mut stmt = c.prepare(
                "SELECT key, embedding_backend, embedding FROM memories \
                 WHERE status='active' AND embedding IS NOT NULL",
            )?;
            let out = stmt
                .query_map([], |row| {
                    Ok((
                        row.get::<_, String>(0)?,
                        row.get::<_, Option<String>>(1)?,
                        row.get::<_, Vec<u8>>(2)?,
                    ))
                })?
                .collect::<Result<Vec<_>, _>>()?;
            Ok::<_, tokio_rusqlite::rusqlite::Error>(out)
        })
        .await?;

    // ── bucket into para-ml (target space) vs noise (hash/NULL/other space) ──
    let mut paraml: Vec<(String, Vec<f32>)> = Vec::new();
    let mut noise: Vec<(String, Vec<f32>)> = Vec::new();
    let (mut n_hash, mut n_null, mut n_other) = (0usize, 0usize, 0usize);
    for (k, be, b) in rows {
        let v = decode_embedding(&b);
        if v.len() != vector_dim() {
            continue;
        }
        match be.as_deref() {
            Some(PARA_ML) => paraml.push((k, v)),
            Some("fnv1a-hash-384") => {
                n_hash += 1;
                noise.push((k, v));
            }
            None => {
                n_null += 1;
                noise.push((k, v));
            }
            Some(_) => {
                n_other += 1;
                noise.push((k, v));
            }
        }
    }
    let n_paraml = paraml.len();
    let n_noise = noise.len();
    let n_total = n_paraml + n_noise;
    let fullmix: Vec<(String, Vec<f32>)> = paraml
        .iter()
        .cloned()
        .chain(noise.iter().cloned())
        .collect();

    if !confirm_real_embedder().await {
        eprintln!("ABORT: real para-ml query embedder not confirmed (hash fallback would be garbage). Run with AGENT_BRIDGE_ONNX_MODEL=para-ml and the model present.");
        std::process::exit(2);
    }

    // ── gold-key coverage: is each expected key para-ml / noise / absent? ────
    let paraml_keys: BTreeSet<&str> = paraml.iter().map(|(k, _)| k.as_str()).collect();
    let noise_keys: BTreeSet<&str> = noise.iter().map(|(k, _)| k.as_str()).collect();
    let answerable: Vec<bool> = CORPUS
        .iter()
        .map(|c| c.expect.iter().any(|e| paraml_keys.contains(e)))
        .collect();
    let n_answerable = answerable.iter().filter(|a| **a).count();
    let n_gold_noise = CORPUS
        .iter()
        .filter(|c| {
            !c.expect.iter().any(|e| paraml_keys.contains(e))
                && c.expect.iter().any(|e| noise_keys.contains(e))
        })
        .count();
    let n_gold_absent = CORPUS
        .iter()
        .filter(|c| {
            !c.expect.iter().any(|e| paraml_keys.contains(e))
                && !c.expect.iter().any(|e| noise_keys.contains(e))
        })
        .count();

    // ── Q1: para-ml anisotropy + whitening ──────────────────────────────────
    let mut mu = vec![0f32; vector_dim()];
    for (_, v) in &paraml {
        for (m, x) in mu.iter_mut().zip(v) {
            *m += x;
        }
    }
    for m in mu.iter_mut() {
        *m /= n_paraml.max(1) as f32;
    }
    let mu_norm: f32 = mu.iter().map(|x| x * x).sum::<f32>().sqrt();
    let mean_vnorm: f32 = paraml
        .iter()
        .map(|(_, v)| v.iter().map(|x| x * x).sum::<f32>().sqrt())
        .sum::<f32>()
        / n_paraml.max(1) as f32;
    let centered: Vec<Vec<f32>> = paraml
        .iter()
        .map(|(_, v)| v.iter().zip(&mu).map(|(a, b)| a - b).collect())
        .collect();
    let pcs = top_k_pcs(&centered, TOP_K);

    println!("# Goal C / N3 — para-ml recall probe (offline, read-only)");
    println!("db:            {}", db_path.display());
    println!(
        "active embedded: {n_total}  (para-ml {n_paraml} | noise {n_noise} = hash {n_hash} + NULL {n_null} + other {n_other}; noise frac {:.3})",
        n_noise as f64 / n_total.max(1) as f64
    );
    println!(
        "anisotropy:    ‖μ‖={mu_norm:.3}  mean‖v‖={mean_vnorm:.3}  ratio={:.3}  (→1.0 = severe; e5 was 0.906)",
        mu_norm / mean_vnorm.max(1e-6)
    );
    println!(
        "gold keys:     {n_answerable}/{} answerable (key is para-ml-indexed) | {n_gold_noise} noise-embedded | {n_gold_absent} absent",
        CORPUS.len()
    );
    println!();

    println!("## Q1 — para-ml anisotropy whitening (rank vs para-ml subset, n_answerable={n_answerable})");
    println!(
        "  {:<22} {:>7} {:>7} {:>7} {:>7}",
        "transform", "R@1", "R@5", "R@10", "MRR"
    );
    let variants: [(&str, usize, bool); 5] = [
        ("raw", 0, false),
        ("centered", 0, true),
        ("abtt-1", 1, true),
        ("abtt-5", 5, true),
        ("abtt-10", 10, true),
    ];
    for (label, k, transform) in variants {
        let tcorpus: Vec<(String, Vec<f32>)> = if transform {
            paraml
                .iter()
                .map(|(key, v)| (key.clone(), apply(v, &mu, &pcs, k)))
                .collect()
        } else {
            paraml.clone()
        };
        let mut agg = Agg::default();
        for (i, case) in CORPUS.iter().enumerate() {
            if !answerable[i] {
                continue;
            }
            let qraw = embed_text(case.query);
            let qv = if transform {
                apply(&qraw, &mu, &pcs, k)
            } else {
                qraw
            };
            agg.record(rank_query(&qv, &tcorpus, case.expect));
        }
        agg.row(label, n_answerable);
    }

    // ── Q2: hash/NULL noise impact on the REAL production cosine path ───────
    println!("\n## Q2 — hash/NULL noise impact (raw cosine, answerable cases, n={n_answerable})");
    println!(
        "  {:<22} {:>7} {:>7} {:>7} {:>7}",
        "ranking corpus", "R@1", "R@5", "R@10", "MRR"
    );
    let mut agg_clean = Agg::default();
    let mut agg_mix = Agg::default();
    let mut per_case: Vec<(String, &'static str, Option<usize>, Option<usize>)> = Vec::new();
    for (i, case) in CORPUS.iter().enumerate() {
        if !answerable[i] {
            continue;
        }
        let qv = embed_text(case.query);
        let r_clean = rank_query(&qv, &paraml, case.expect);
        let r_mix = rank_query(&qv, &fullmix, case.expect);
        agg_clean.record(r_clean);
        agg_mix.record(r_mix);
        per_case.push((
            case.query.chars().take(28).collect(),
            case.tier.label(),
            r_clean,
            r_mix,
        ));
    }
    agg_clean.row("para-ml-only (clean)", n_answerable);
    agg_mix.row("full-mix (+noise)", n_answerable);

    println!("\n## Per-case rank (— = miss; clean = para-ml-only, mix = +noise rows)");
    println!("  {:<9} {:>6} {:>6}  {}", "tier", "clean", "mix", "query");
    for (q, tier, rc, rm) in &per_case {
        let cell = |o: &Option<usize>| o.map(|x| x.to_string()).unwrap_or_else(|| "—".into());
        let flag = match (rc, rm) {
            (Some(a), Some(b)) if b > a => "  ← noise pushed down",
            (Some(_), None) => "  ← noise knocked out of top-10",
            _ => "",
        };
        println!(
            "  {:<9} {:>6} {:>6}  {}{}",
            tier,
            cell(rc),
            cell(rm),
            q,
            flag
        );
    }

    println!("\n## Read");
    println!("  Q1: rising R@k raw→centered→abtt ⇒ para-ml IS anisotropic (whiten it).");
    println!("      flat/declining ⇒ para-ml geometrically healthy ⇒ cross-node fix = converge on para-ml, NOT whiten.");
    println!("  Q2: clean ≫ mix ⇒ the un-reindexed {n_noise} noise rows ({:.0}%) measurably degrade recall ⇒ reindex them.", n_noise as f64 / n_total.max(1) as f64 * 100.0);
    println!("      clean ≈ mix ⇒ noise rows sit far from queries in cosine ⇒ reindex is hygiene, not a recall lever.");
    Ok(())
}
