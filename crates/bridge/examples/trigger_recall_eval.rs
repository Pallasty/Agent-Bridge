//! Goal C trigger-aware recall eval over memories with `continuity_retrieval_trigger`.
//!
//! This is the missing held-out cohort for the v36 retrieval-trigger FTS
//! projection: the store tests prove trigger text is indexed; this example asks
//! whether rows that carry retrieval triggers are actually recoverable from
//! continuation-intent queries that do not simply repeat the authored trigger.
//!
//! Surface-free + read-only: only SELECT-side store calls (`memory_get` and
//! `memory_search`). NO new MCP tool, NO ranking change, NO writes, NO reindex.
//!
//! Running:
//!
//!   cargo run -p ab-bridge --example trigger_recall_eval
//!   AB_BASELINE_DB=/tmp/state.copy.db cargo run -p ab-bridge --example trigger_recall_eval
//!
//! Debug one case:
//!
//!   cargo run -p ab-bridge --example trigger_recall_eval -- 4

use ab_store::{MemorySearchHit, SqliteStore, StateStore, default_db_path};
use std::path::PathBuf;

const TOP_K: usize = 10;

struct Case {
    id: &'static str,
    query: &'static str,
    trigger: &'static str,
    expect: &'static [&'static str],
    note: &'static str,
}

/// Cases were selected from active Mac store rows carrying
/// `continuity_retrieval_trigger` tags on 2026-06-22. `trigger` is the authored
/// retrieval-trigger text; `query` is a held-out continuation intent authored
/// separately so the eval does not pass by echoing the exact projection string.
const CORPUS: &[Case] = &[
    Case {
        id: "s132_handoff",
        query: "从 S132 继续到 S133 的静态实验设计人工审查,应该找哪条交接记忆",
        trigger: "Retrieve when continuing from S132 toward S133 static experiment-design manual review or board packet.",
        expect: &["biocortex_rs_s132_static_experiment_design_review_preflight_handoff_20260622"],
        note: "BioCortex S132 handoff continuation",
    },
    Case {
        id: "s132_evidence",
        query: "核对 BioCortex S132 到 S133 静态实验设计预检证据和 staged readiness gate",
        trigger: "Retrieve for biocortex S132/S133 static experiment-design review preflight work or staged readiness gates.",
        expect: &["biocortex_s132_static_experiment_design_review_preflight_20260622"],
        note: "BioCortex S132 evidence row",
    },
    Case {
        id: "t6_executor_preflight",
        query: "继续 AB memory T6 shadow executor preflight 的部署验证和 stale MCP reconnect 检查",
        trigger: "Continuing AB memory T6 shadow executor preflight, deploy verification, or stale MCP reconnect work",
        expect: &["ab_memory_continuity_t6_shadow_executor_preflight_deployed_20260621"],
        note: "AB T6 shadow executor preflight",
    },
    Case {
        id: "goal_b_surface_growth",
        query: "Goal B 工具面膨胀现在应该先限制新增 gate tool 还是清理存量 cold tools",
        trigger: "When continuing Goal B tool-surface deflation, D2 metastasis, or tool-addition gate for Agent-Bridge",
        expect: &["goal_b_surface_growth_gate_engine_finding_20260621"],
        note: "Goal B tool-surface direction",
    },
    Case {
        id: "goal_c_recall_anchor",
        query: "为什么 Goal C 要把 recall_eval R@k 当成连续性的外部 falsifier 锚点",
        trigger: "When continuing Goal C continuity ledger, recall_eval anchor, or cold-start recall measurement for Agent-Bridge",
        expect: &["goal_c_recall_eval_falsifier_anchor_contribution_20260621"],
        note: "Goal C recall anchor",
    },
    Case {
        id: "biocortex_gate_program",
        query: "准备继续 BioCortex scale gate 或 retrieval gate 时,构建顺序和理论依据看哪条",
        trigger: "biocortex next gate / what to build / scale gate / retrieval gate / s89d / gate program / build order",
        expect: &["biocortex_gate_program_post_research_20260620"],
        note: "BioCortex gate program",
    },
    Case {
        id: "ghp12_scope_filter",
        query: "GHP related_keys materialize 的 exact scope filter 部署后如何验证和继续",
        trigger: "GHP related_keys materialize exact scope filter deployed or verified",
        expect: &["ab_goal_c_ghp12_exact_scope_materialize_gate_deployed_20260621"],
        note: "GHP-1.2 exact-scope materialize",
    },
    Case {
        id: "goal_c_executor_constraint",
        query: "考虑给 Agent-Bridge 加自动自我改进 executor 时有哪些必须阻止的边界",
        trigger: "When considering Agent-Bridge self-improvement executor, new U MCP tool, or automated patch/commit workflow.",
        expect: &["ab_goal_c_gated_executor_decision_20260621"],
        note: "Goal C executor non-authorization",
    },
    Case {
        id: "goal_c_u_patch_plan",
        query: "规划 Goal C 的 U report generator 或 runbook 下一步时应该参考哪份 dry-run patch plan",
        trigger: "When planning Goal C G3, U report generator/runbook, recall_eval dependency, or G4 executor decision.",
        expect: &["ab_goal_c_u_dry_run_patch_plan_20260621"],
        note: "Goal C U dry-run patch plan",
    },
    Case {
        id: "onsen_handoff",
        query: "打开 onsen-hd 会话时要恢复 Sprint 6 save/load cloud mock Steam readiness 的状态",
        trigger: "onsen-hd session open; Sprint 6 save/load + cloud(mock) + Steam readiness 全 land; ADR-015 P1/P2/P3a landed P3b pending; ADR-007 vendor target GodotSteam v4.19.1",
        expect: &["session_handoff_onsen_hd_opus_47_20260620"],
        note: "Cross-project Onsen handoff",
    },
];

#[derive(Default)]
struct Agg {
    r_at_1: u32,
    r_at_5: u32,
    r_at_10: u32,
    rr_sum: f64,
    ranks: Vec<Option<usize>>,
    errors: Vec<Option<String>>,
}

impl Agg {
    fn record(&mut self, rank: Option<usize>, error: Option<String>) {
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
        self.errors.push(error);
    }
}

#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    let db_path: PathBuf = std::env::var("AB_BASELINE_DB")
        .ok()
        .map(PathBuf::from)
        .unwrap_or_else(default_db_path);
    let store = SqliteStore::open(&db_path).await?;

    if let Some(arg) = std::env::args().nth(1) {
        if let Ok(idx1) = arg.parse::<usize>() {
            return debug_case(&store, idx1).await;
        }
    }

    let mut missing_expected = Vec::new();
    for case in CORPUS {
        for key in case.expect {
            if store.memory_get(key).await?.is_none() {
                missing_expected.push(*key);
            }
        }
    }

    let mut intent = Agg::default();
    let mut exact_trigger = Agg::default();

    for case in CORPUS {
        let (intent_keys, intent_error) = search_keys(&store, case.query).await;
        intent.record(first_hit_rank(&intent_keys, case.expect), intent_error);

        let (trigger_keys, trigger_error) = search_keys(&store, case.trigger).await;
        exact_trigger.record(first_hit_rank(&trigger_keys, case.expect), trigger_error);
    }

    let n = CORPUS.len();
    println!("# Trigger-aware recall eval — continuity_retrieval_trigger cohort");
    println!("db:              {}", db_path.display());
    println!("corpus:          {n} cases (Mac active trigger-tag rows, 2026-06-22)");
    println!("top_k:           {TOP_K}");
    println!(
        "mode contract:   exact_trigger = authored tag text; intent = held-out continuation query"
    );
    println!(
        "read_only:       memory_get + memory_search only; no writes, no reindex, no runtime path change"
    );
    if !missing_expected.is_empty() {
        println!("missing expect:  {}", missing_expected.join(", "));
    }
    println!();

    println!("## Per-mode recall (success@k over {n} cases)");
    println!(
        "  {:<14} {:>7} {:>7} {:>7} {:>7}",
        "mode", "R@1", "R@5", "R@10", "MRR"
    );
    print_row("intent", &intent, n);
    print_row("exact_trigger", &exact_trigger, n);
    println!();

    println!("## Per-case first-hit rank (— = no hit in top {TOP_K})");
    println!(
        "  {:<3} {:<28} {:>7} {:>13}  {}",
        "#", "id", "intent", "exact_trigger", "note"
    );
    for (i, case) in CORPUS.iter().enumerate() {
        println!(
            "  {:<3} {:<28} {:>7} {:>13}  {}",
            i + 1,
            case.id,
            rank_cell(intent.ranks[i], intent.errors[i].as_deref()),
            rank_cell(exact_trigger.ranks[i], exact_trigger.errors[i].as_deref()),
            case.note
        );
    }
    println!();

    let intent_misses = miss_indices(&intent);
    let exact_misses = miss_indices(&exact_trigger);
    let intent_errors = error_indices(&intent);
    let exact_errors = error_indices(&exact_trigger);
    println!("## Honest read");
    println!(
        "  intent misses:        {} case(s){}",
        intent_misses.len(),
        fmt_idx(&intent_misses)
    );
    println!(
        "  exact_trigger misses: {} case(s){}",
        exact_misses.len(),
        fmt_idx(&exact_misses)
    );
    println!(
        "  intent errors:        {} case(s){}",
        intent_errors.len(),
        fmt_idx(&intent_errors)
    );
    println!(
        "  exact_trigger errors: {} case(s){}",
        exact_errors.len(),
        fmt_idx(&exact_errors)
    );
    println!(
        "  interpretation: exact_trigger mainly verifies that v36 projected trigger text is searchable. \
         intent is the useful continuity metric because it asks whether a future session's natural \
         continuation query finds the triggered row without verbatim tag echo."
    );
    println!(
        "  caveat: hand-curated corpus, N={n}. Treat this as the first trigger-aware falsifier, \
         not a production ranking benchmark."
    );

    Ok(())
}

fn keys_of(hits: Vec<MemorySearchHit>) -> Vec<String> {
    hits.into_iter().map(|h| h.record.key).collect()
}

async fn search_keys(store: &SqliteStore, query: &str) -> (Vec<String>, Option<String>) {
    match store.memory_search(query, &[], TOP_K as u32).await {
        Ok(hits) => (keys_of(hits), None),
        Err(err) => (Vec::new(), Some(err.to_string())),
    }
}

fn first_hit_rank(keys: &[String], expect: &[&str]) -> Option<usize> {
    keys.iter()
        .position(|k| expect.iter().any(|e| e == k))
        .map(|i| i + 1)
}

async fn debug_case(store: &SqliteStore, idx1: usize) -> Result<(), Box<dyn std::error::Error>> {
    let case = CORPUS
        .get(idx1.saturating_sub(1))
        .ok_or("case index out of range")?;
    println!("# debug trigger-aware case #{idx1}");
    println!("id:      {}", case.id);
    println!("query:   {}", case.query);
    println!("trigger: {}", case.trigger);
    println!("expect:  {:?}\n", case.expect);

    dump_result(
        "intent",
        case.expect,
        store.memory_search(case.query, &[], TOP_K as u32).await,
    );
    dump_result(
        "exact_trigger",
        case.expect,
        store.memory_search(case.trigger, &[], TOP_K as u32).await,
    );
    Ok(())
}

fn dump_result<E: std::fmt::Display>(
    label: &str,
    expect: &[&str],
    result: Result<Vec<MemorySearchHit>, E>,
) {
    match result {
        Ok(hits) => dump(label, expect, &hits),
        Err(err) => {
            println!("## {label} — ERROR");
            println!("  {err}\n");
        }
    }
}

fn dump(label: &str, expect: &[&str], hits: &[MemorySearchHit]) {
    println!("## {label} (top {})", hits.len());
    for (i, h) in hits.iter().enumerate() {
        let star = if expect.iter().any(|e| *e == h.record.key) {
            " <== EXPECTED"
        } else {
            ""
        };
        println!(
            "  {:>2}. score={:>7.3} {}{}",
            i + 1,
            h.score,
            h.record.key,
            star
        );
    }
    println!();
}

fn print_row(label: &str, agg: &Agg, n: usize) {
    let nf = n as f64;
    println!(
        "  {:<14} {:>7.3} {:>7.3} {:>7.3} {:>7.3}",
        label,
        agg.r_at_1 as f64 / nf,
        agg.r_at_5 as f64 / nf,
        agg.r_at_10 as f64 / nf,
        agg.rr_sum / nf,
    );
}

fn rank_cell(rank: Option<usize>, error: Option<&str>) -> String {
    if error.is_some() {
        return "ERR".to_string();
    }
    match rank {
        Some(r) => r.to_string(),
        None => "—".to_string(),
    }
}

fn miss_indices(agg: &Agg) -> Vec<usize> {
    agg.ranks
        .iter()
        .enumerate()
        .filter_map(|(i, r)| if r.is_none() { Some(i + 1) } else { None })
        .collect()
}

fn error_indices(agg: &Agg) -> Vec<usize> {
    agg.errors
        .iter()
        .enumerate()
        .filter_map(|(i, e)| if e.is_some() { Some(i + 1) } else { None })
        .collect()
}

fn fmt_idx(idx: &[usize]) -> String {
    if idx.is_empty() {
        String::new()
    } else {
        format!(
            " -> #{}",
            idx.iter()
                .map(|i| i.to_string())
                .collect::<Vec<_>>()
                .join(", #")
        )
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn first_hit_rank_returns_first_expected_key() {
        let keys = vec![
            "distractor".to_string(),
            "expected_b".to_string(),
            "expected_a".to_string(),
        ];

        assert_eq!(
            first_hit_rank(&keys, &["expected_a", "expected_b"]),
            Some(2)
        );
    }

    #[test]
    fn corpus_queries_are_not_verbatim_triggers() {
        for case in CORPUS {
            assert_ne!(
                case.query, case.trigger,
                "{} must use a held-out intent query, not exact trigger text",
                case.id
            );
            assert!(!case.expect.is_empty(), "{} has no accept set", case.id);
        }
    }
}
