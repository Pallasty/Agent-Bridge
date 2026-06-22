//! Goal C — read-only trigger-aware FTS projection recall probe.
//!
//! Store tests prove `continuity_retrieval_trigger:*` is projected into
//! `memories.fts_content`; the fixed 18-case `recall_eval` corpus does not
//! overlap that trigger-tag cohort. This example asks the missing question:
//! does the projection make trigger rows more visible to continuation-intent
//! queries?
//!
//! Method. Open the live store read-only, copy active rows into two temporary
//! in-memory FTS5 tables, then compare:
//!
//! - `intent_content`: held-out query over authored `memories.content`;
//! - `intent_projected`: same held-out query over `fts_content`;
//! - `cjk_shingle_projected`: same held-out query over a scratch-only projected
//!   index augmented with generated CJK character trigrams;
//! - `projected_plus_cjk_acc`: existing projected search plus a conservative
//!   CJK trigram-overlap fallback for projected misses;
//! - `exact_projected`: authored trigger text over `fts_content`.
//!
//! The first two isolate trigger projection from production ranking. They do
//! not use access_count, importance, recency, graph expansion, semantic
//! embeddings, `memory_get`, or `memory_search`. The CJK shingle mode is an
//! eval-only recovery probe for Chinese paraphrase/tokenization misses. The
//! exact mode is a projection health probe and can expose FTS parser problems in
//! trigger text.
//!
//! Surface-free + read-only: SELECT from the real DB, write only to an in-memory
//! scratch DB. No MCP tool, no runtime retrieval change, no memory write.
//!
//!   cargo run -p ab-bridge --example trigger_recall_eval
//!   AB_BASELINE_DB=/tmp/state.copy.db cargo run -p ab-bridge --example trigger_recall_eval
//!
//! Debug one case:
//!
//!   cargo run -p ab-bridge --example trigger_recall_eval -- 4

use ab_store::default_db_path;
use std::collections::{BTreeSet, HashMap};
use std::path::PathBuf;
use tokio_rusqlite::rusqlite::{
    Connection as RusqliteConnection, OpenFlags, Result as SqlResult, params,
};

const TOP_K: usize = 10;
const MIN_CJK_SHINGLE_ACCEPT_OVERLAP: usize = 4;
const TRIGGER_PREFIX: &str = "continuity_retrieval_trigger:";

struct Case {
    id: &'static str,
    stratum: &'static str,
    query: &'static str,
    trigger: &'static str,
    expect: &'static [&'static str],
    note: &'static str,
}

struct NegativeControl {
    id: &'static str,
    query: &'static str,
    note: &'static str,
}

/// Cases selected from active Mac rows carrying `continuity_retrieval_trigger`
/// tags on 2026-06-22. `trigger` is the authored metadata. `query` is a
/// separate held-out continuation intent so the eval does not pass by exact
/// trigger echo.
const CORPUS: &[Case] = &[
    Case {
        id: "s132_handoff",
        stratum: "biocortex",
        query: "从 S132 继续到 S133 的静态实验设计人工审查,应该找哪条交接记忆",
        trigger: "Retrieve when continuing from S132 toward S133 static experiment-design manual review or board packet.",
        expect: &["biocortex_rs_s132_static_experiment_design_review_preflight_handoff_20260622"],
        note: "BioCortex S132 handoff continuation",
    },
    Case {
        id: "s132_evidence",
        stratum: "biocortex",
        query: "核对 BioCortex S132 到 S133 静态实验设计预检证据和 staged readiness gate",
        trigger: "Retrieve for biocortex S132/S133 static experiment-design review preflight work or staged readiness gates.",
        expect: &["biocortex_s132_static_experiment_design_review_preflight_20260622"],
        note: "BioCortex S132 evidence row",
    },
    Case {
        id: "t6_executor_preflight",
        stratum: "ab_t6",
        query: "继续 AB memory T6 shadow executor preflight 的部署验证和 stale MCP reconnect 检查",
        trigger: "Continuing AB memory T6 shadow executor preflight, deploy verification, or stale MCP reconnect work",
        expect: &["ab_memory_continuity_t6_shadow_executor_preflight_deployed_20260621"],
        note: "AB T6 shadow executor preflight",
    },
    Case {
        id: "goal_b_surface_growth",
        stratum: "goal_b",
        query: "Goal B 工具面膨胀现在应该先限制新增 gate tool 还是清理存量 cold tools",
        trigger: "When continuing Goal B tool-surface deflation, D2 metastasis, or tool-addition gate for Agent-Bridge",
        expect: &["goal_b_surface_growth_gate_engine_finding_20260621"],
        note: "Goal B tool-surface direction",
    },
    Case {
        id: "goal_c_recall_anchor",
        stratum: "goal_c",
        query: "为什么 Goal C 要把 recall_eval R@k 当成连续性的外部 falsifier 锚点",
        trigger: "When continuing Goal C continuity ledger, recall_eval anchor, or cold-start recall measurement for Agent-Bridge",
        expect: &["goal_c_recall_eval_falsifier_anchor_contribution_20260621"],
        note: "Goal C recall anchor",
    },
    Case {
        id: "biocortex_gate_program",
        stratum: "biocortex",
        query: "准备继续 BioCortex scale gate 或 retrieval gate 时,构建顺序和理论依据看哪条",
        trigger: "biocortex next gate / what to build / scale gate / retrieval gate / s89d / gate program / build order",
        expect: &["biocortex_gate_program_post_research_20260620"],
        note: "BioCortex gate program",
    },
    Case {
        id: "ghp12_scope_filter",
        stratum: "graph_hygiene",
        query: "GHP related_keys materialize 的 exact scope filter 部署后如何验证和继续",
        trigger: "GHP related_keys materialize exact scope filter deployed or verified",
        expect: &["ab_goal_c_ghp12_exact_scope_materialize_gate_deployed_20260621"],
        note: "GHP-1.2 exact-scope materialize",
    },
    Case {
        id: "goal_c_executor_constraint",
        stratum: "goal_c",
        query: "考虑给 Agent-Bridge 加自动自我改进 executor 时有哪些必须阻止的边界",
        trigger: "When considering Agent-Bridge self-improvement executor, new U MCP tool, or automated patch/commit workflow.",
        expect: &["ab_goal_c_gated_executor_decision_20260621"],
        note: "Goal C executor non-authorization",
    },
    Case {
        id: "goal_c_u_patch_plan",
        stratum: "goal_c",
        query: "规划 Goal C 的 U report generator 或 runbook 下一步时应该参考哪份 dry-run patch plan",
        trigger: "When planning Goal C G3, U report generator/runbook, recall_eval dependency, or G4 executor decision.",
        expect: &["ab_goal_c_u_dry_run_patch_plan_20260621"],
        note: "Goal C U dry-run patch plan",
    },
    Case {
        id: "onsen_handoff",
        stratum: "onsen",
        query: "打开 onsen-hd 会话时要恢复 Sprint 6 save/load cloud mock Steam readiness 的状态",
        trigger: "onsen-hd session open; Sprint 6 save/load + cloud(mock) + Steam readiness 全 land; ADR-015 P1/P2/P3a landed P3b pending; ADR-007 vendor target GodotSteam v4.19.1",
        expect: &["session_handoff_onsen_hd_opus_47_20260620"],
        note: "Cross-project Onsen handoff",
    },
    Case {
        id: "s131_handoff",
        stratum: "biocortex",
        query: "从 BioCortex S131 切到 S132 的静态实验设计 review-board 预检该接哪条 handoff",
        trigger: "Retrieve when continuing from S131 toward S132 static experiment-design review or review-board preflight.",
        expect: &["biocortex_rs_s131_static_experiment_design_packet_handoff_20260622"],
        note: "BioCortex S131 handoff continuation",
    },
    Case {
        id: "s131_evidence",
        stratum: "biocortex",
        query: "检查 S131/S132 static experiment design packet 的 staged gate 证据",
        trigger: "Retrieve for biocortex S131/S132 static experiment design packet work or staged readiness gates.",
        expect: &["biocortex_s131_static_experiment_design_packet_20260622"],
        note: "BioCortex S131 evidence row",
    },
    Case {
        id: "s130_handoff",
        stratum: "biocortex",
        query: "S130 static planning packet 完成后,下一段 biocortex-rs stage 应从哪里接",
        trigger: "Use when starting the next biocortex-rs stage after S130 static planning packet.",
        expect: &["biocortex_rs_s130_static_planning_packet_handoff_20260621"],
        note: "BioCortex S130 next-stage handoff",
    },
    Case {
        id: "s130_evidence",
        stratum: "biocortex",
        query: "继续 S130 staged-gate 或核对 static planning packet 验证证据时应该召回哪条",
        trigger: "Use when continuing biocortex-rs staged-gate work after S130 or checking S130 verification evidence.",
        expect: &["biocortex_s130_static_planning_packet_20260621"],
        note: "BioCortex S130 verification row",
    },
    Case {
        id: "t6_shadow_executor_next_invocation",
        stratum: "ab_t6",
        query: "T6 shadow executor preflight 已部署后,下一层 invocation evidence surface 应该怎么收窄",
        trigger: "next T6 step after shadow executor preflight is deployed",
        expect: &["ab_memory_continuity_t6_shadow_executor_invocation_next_20260621"],
        note: "AB T6 shadow executor next invocation",
    },
    Case {
        id: "t6_shadow_executor_next_gate",
        stratum: "ab_t6",
        query: "shadow_execution_gate 之后规划下一个 AB T6 gate 时有哪些边界",
        trigger: "Retrieve when planning the next AB T6 gate after shadow_execution_gate deployment.",
        expect: &["ab_memory_continuity_t6_shadow_executor_next_20260621"],
        note: "AB T6 next-gate procedure",
    },
    Case {
        id: "t6_shadow_execution_gate",
        stratum: "ab_t6",
        query: "核验 T6 memory continuity shadow execution gate 的部署和 MCP manifest 时看哪条",
        trigger: "Retrieve when continuing AB T6 memory continuity shadow execution gate, deployment verification, or MCP manifest checks.",
        expect: &["ab_memory_continuity_t6_shadow_execution_gate_deployed_20260621"],
        note: "AB T6 shadow execution gate deployed",
    },
    Case {
        id: "ghp12_reconnect",
        stratum: "graph_hygiene",
        query: "GHP-1.2 exact-scope materialize 之后用户重连 MCP,当前工具面和下一关怎么确认",
        trigger: "After GHP-1.2 exact-scope materialize deploy or MCP reconnect questions, recall verified tool surfaces and next gate.",
        expect: &["ab_goal_c_ghp12_reconnect_verified_20260621"],
        note: "GHP-1.2 reconnect verification",
    },
    Case {
        id: "t6_shadow_runtime_gate_deployed",
        stratum: "ab_t6",
        query: "T6 candidate expansion shadow runtime gate 已部署时,当前验证状态是哪条",
        trigger: "AB T6 candidate expansion shadow runtime gate deployed verification",
        expect: &["ab_memory_continuity_t6_shadow_runtime_gate_deployed_20260621"],
        note: "AB T6 shadow runtime gate deployed",
    },
    Case {
        id: "t6_shadow_runtime_next",
        stratum: "ab_t6",
        query: "shadow runtime gate 之后,下一步是否应该进入 shadow execution gate",
        trigger: "Next step after T6 candidate expansion shadow runtime gate",
        expect: &["ab_memory_continuity_t6_shadow_runtime_gate_next_20260621"],
        note: "AB T6 shadow runtime next step",
    },
    Case {
        id: "ghp1_strict_scope_deployed",
        stratum: "graph_hygiene",
        query: "GHP-1.1 strict-scope review packet 已部署后,related_keys 图卫生证据在哪里",
        trigger: "GHP-1.1 deployed exact scope review packet and related_keys graph hygiene",
        expect: &["ab_goal_c_ghp1_strict_scope_review_packet_deployed_20260621"],
        note: "GHP-1.1 strict-scope deployed",
    },
    Case {
        id: "ghp1_live_scope_observation",
        stratum: "graph_hygiene",
        query: "live related_keys review packet 选边范围太宽时,strict-scope 下一步应该看哪条 observation",
        trigger: "GHP-1 live review packet selected edges scope too broad strict-scope next step",
        expect: &["ab_goal_c_ghp1_live_packet_scope_observation_20260621"],
        note: "GHP-1 live scope observation",
    },
    Case {
        id: "goal_c_u_surface",
        stratum: "goal_c",
        query: "规划 Controlled RSI 的 U surface 报告优先路线时,哪条说明 report-first 而不是新 MCP 工具",
        trigger: "When planning Goal C U surface, controlled RSI report-first loop, or G3 dry-run patch plan.",
        expect: &["ab_goal_c_report_first_utility_surface_20260621"],
        note: "Goal C report-first U surface",
    },
    Case {
        id: "goal_c_honest_ledger",
        stratum: "goal_c",
        query: "整理 Goal C continuity honest ledger、LSWR-H1、BioCortex runtime influence 状态时该召回哪条",
        trigger: "When planning Goal C, continuity honest ledger, LSWR-H1, BioCortex runtime influence, or controlled RSI G2.",
        expect: &["ab_goal_c_continuity_honest_ledger_inventory_20260621"],
        note: "Goal C continuity honest ledger",
    },
    Case {
        id: "controlled_rsi_design",
        stratum: "goal_c",
        query: "Agent-Bridge 采用 Godel Agent 思路时,为什么是 governed loop 而不是 runtime self-patching",
        trigger: "When planning AB self-improvement, Goal C dashboard, Godel Agent adaptation, or SEPL overlap.",
        expect: &["ab_controlled_recursive_self_improvement_design_20260621"],
        note: "Controlled RSI design constraint",
    },
    Case {
        id: "nexus_wuxing_gdd35",
        stratum: "nexus",
        query: "重新审阅 #35 科技树五行生克 v0.2 或 tech-wuxing-sheng-ke 时应该找哪条状态",
        trigger: "#35 科技五行生克 / tech-wuxing-sheng-ke / 五行研究生克 v0.2 re-review",
        expect: &["nexus_35_tech_wuxing_shengke_v01_20260620"],
        note: "Nexus #35 Wuxing design review",
    },
    Case {
        id: "nexus_wuxing_math",
        stratum: "nexus",
        query: "五行生克的成熟数学模型、黄金比例控制网络和平衡靶调研结论在哪里",
        trigger: "五行生克 数学模型 / golden ratio / wuxing_dynamics 平衡靶 / #35 v0.2 / 循环平衡环",
        expect: &["nexus_wuxing_shengke_golden_ratio_survey_20260621"],
        note: "Nexus Wuxing math survey",
    },
    Case {
        id: "palace_apply_idempotent",
        stratum: "palace",
        query: "Palace materialization approved-plan live apply 和 idempotence 验证结果该看哪条",
        trigger: "When continuing Palace materialization apply, approved-plan idempotence, or graph edge materialization verification",
        expect: &["palace_materialization_apply_live_and_idempotent_plan_20260620"],
        note: "Palace materialization live apply",
    },
    Case {
        id: "palace_apply_operational",
        stratum: "palace",
        query: "解释 Palace materialization apply-gate 是否真的写过 live memory_edges 时召回哪条",
        trigger: "When checking Palace materialization apply-gate operational state or explaining whether a live memory_edges write occurred.",
        expect: &["palace_materialization_operational_apply_verified_20260620"],
        note: "Palace materialization operational proof",
    },
    Case {
        id: "t1_trigger_projection_v36",
        stratum: "ab_t6",
        query: "AB memory continuity T1 retrieval trigger FTS projection schema v36 部署证据在哪里",
        trigger: "AB memory continuity retrieval trigger FTS projection deployed schema v36 fts_content",
        expect: &["ab_memory_continuity_t1_retrieval_trigger_fts_projection_20260621"],
        note: "AB T1 trigger projection deployment",
    },
];

const NEGATIVE_CONTROLS: &[NegativeControl] = &[
    NegativeControl {
        id: "unrelated_recipe",
        query: "banana sourdough crochet tidepool recipe unrelated continuation",
        note: "Unrelated English nouns should not retrieve corpus gold keys",
    },
    NegativeControl {
        id: "unrelated_weather",
        query: "明天的天气预报 机场停车 折扣券 完全无关任务",
        note: "Unrelated Chinese daily-life query should not retrieve corpus gold keys",
    },
    NegativeControl {
        id: "unrelated_math_puzzle",
        query: "prime number crossword watercolor tutorial no agent bridge project state",
        note: "Generic puzzle/art query should not retrieve corpus gold keys",
    },
    NegativeControl {
        id: "project_adjacent_cjk_tourism",
        query: "五行山旅游攻略 黄金比例摄影构图 平衡车购买指南",
        note: "Shares CJK surface terms with the Wuxing math row but has tourism/shopping intent",
    },
    NegativeControl {
        id: "project_adjacent_cjk_health",
        query: "五行蔬菜汤 平衡饮食 黄金比例健身计划 控制体重",
        note: "Shares Wuxing/balance/golden-ratio terms but has health-plan intent",
    },
    NegativeControl {
        id: "project_adjacent_nexus_visual",
        query: "Nexus 游戏 五行角色皮肤 黄金配色 平衡性吐槽",
        note: "Shares Nexus and Wuxing vocabulary but asks about visual/balance feedback, not math survey evidence",
    },
];

struct MemoryRow {
    key: String,
    content: String,
    projected: String,
    triggers: Vec<String>,
}

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

fn main() -> Result<(), Box<dyn std::error::Error>> {
    let db_path: PathBuf = std::env::var("AB_BASELINE_DB")
        .ok()
        .map(PathBuf::from)
        .unwrap_or_else(default_db_path);
    let rows = load_active_rows(&db_path)?;
    verify_corpus(&rows)?;
    let fts = ScratchFts::build(&rows)?;

    if let Some(arg) = std::env::args().nth(1) {
        if let Ok(idx1) = arg.parse::<usize>() {
            return debug_case(&fts, idx1);
        }
    }

    let mut intent_content = Agg::default();
    let mut intent_projected = Agg::default();
    let mut cjk_shingle_projected = Agg::default();
    let mut projected_plus_cjk_acc = Agg::default();
    let mut exact_projected = Agg::default();
    let gold_keys: BTreeSet<&str> = CORPUS
        .iter()
        .flat_map(|case| case.expect.iter().copied())
        .collect();

    for case in CORPUS {
        let content_keys = fts.search(IndexKind::Content, case.query, TOP_K);
        intent_content.record(
            first_hit_rank(content_keys.as_deref().unwrap_or(&[]), case.expect),
            content_keys.err(),
        );

        let projected_keys = fts.search(IndexKind::Projected, case.query, TOP_K);
        intent_projected.record(
            first_hit_rank(projected_keys.as_deref().unwrap_or(&[]), case.expect),
            projected_keys.err(),
        );

        let cjk_keys = fts.search_projected_cjk_shingles(case.query, TOP_K);
        cjk_shingle_projected.record(
            first_hit_rank(cjk_keys.as_deref().unwrap_or(&[]), case.expect),
            cjk_keys.err(),
        );

        let projected_plus_keys = fts.search_projected_then_cjk_accepted(case.query, TOP_K);
        projected_plus_cjk_acc.record(
            first_hit_rank(projected_plus_keys.as_deref().unwrap_or(&[]), case.expect),
            projected_plus_keys.err(),
        );

        let trigger_keys = fts.search(IndexKind::Projected, case.trigger, TOP_K);
        exact_projected.record(
            first_hit_rank(trigger_keys.as_deref().unwrap_or(&[]), case.expect),
            trigger_keys.err(),
        );
    }

    let mut negative_false_hits = Vec::new();
    let mut negative_errors = Vec::new();
    let mut cjk_negative_false_hits = Vec::new();
    let mut cjk_negative_errors = Vec::new();
    let mut projected_plus_false_hits = Vec::new();
    let mut projected_plus_errors = Vec::new();
    for control in NEGATIVE_CONTROLS {
        match fts.search(IndexKind::Projected, control.query, TOP_K) {
            Ok(keys) => {
                for (idx, key) in keys.iter().enumerate() {
                    if gold_keys.contains(key.as_str()) {
                        negative_false_hits.push(format!("{}:{}@{}", control.id, key, idx + 1));
                    }
                }
            }
            Err(err) => negative_errors.push(format!("{}:{err}", control.id)),
        }
        match fts.search_projected_cjk_shingles(control.query, TOP_K) {
            Ok(keys) => {
                for (idx, key) in keys.iter().enumerate() {
                    if gold_keys.contains(key.as_str()) {
                        cjk_negative_false_hits.push(format!("{}:{}@{}", control.id, key, idx + 1));
                    }
                }
            }
            Err(err) => cjk_negative_errors.push(format!("{}:{err}", control.id)),
        }
        match fts.search_projected_then_cjk_accepted(control.query, TOP_K) {
            Ok(keys) => {
                for (idx, key) in keys.iter().enumerate() {
                    if gold_keys.contains(key.as_str()) {
                        projected_plus_false_hits.push(format!(
                            "{}:{}@{}",
                            control.id,
                            key,
                            idx + 1
                        ));
                    }
                }
            }
            Err(err) => projected_plus_errors.push(format!("{}:{err}", control.id)),
        }
    }

    let active_total = rows.len();
    let trigger_rows = rows.iter().filter(|r| !r.triggers.is_empty()).count();
    let projected_rows = rows.iter().filter(|r| r.content != r.projected).count();
    let n = CORPUS.len();

    println!("# Trigger-aware recall eval — continuity_retrieval_trigger cohort");
    println!("db:              {}", db_path.display());
    println!("active rows:     {active_total}");
    println!("trigger rows:    {trigger_rows}");
    println!("projected rows:  {projected_rows}");
    println!("corpus:          {n} cases (Mac active trigger-tag rows, 2026-06-22)");
    println!("negative_ctrls:  {} controls", NEGATIVE_CONTROLS.len());
    println!("top_k:           {TOP_K}");
    println!("mode contract:   intent_content vs intent_projected isolates trigger projection");
    println!(
        "read_only:       SELECT + in-memory FTS only; no memory_get, memory_search, writes, or reindex"
    );
    println!();

    println!("## Per-mode recall (success@k over {n} cases)");
    println!(
        "  {:<18} {:>7} {:>7} {:>7} {:>7}",
        "mode", "R@1", "R@5", "R@10", "MRR"
    );
    print_row("intent_content", &intent_content, n);
    print_row("intent_projected", &intent_projected, n);
    print_row("cjk_shingle_proj", &cjk_shingle_projected, n);
    print_row("projected+cjk_acc", &projected_plus_cjk_acc, n);
    print_row("exact_projected", &exact_projected, n);
    println!();

    println!("## Corpus strata");
    for (stratum, count) in stratum_counts() {
        println!("  {stratum:<14} {count:>3}");
    }
    println!();

    println!("## Projection delta");
    let added = added_hit_indices(&intent_content, &intent_projected);
    let improved = improved_rank_indices(&intent_content, &intent_projected);
    println!(
        "  added top-{TOP_K} hits over content-only: {} case(s){}",
        added.len(),
        fmt_idx(&added)
    );
    println!(
        "  improved first-hit rank:              {} case(s){}",
        improved.len(),
        fmt_idx(&improved)
    );
    println!();

    println!("## Negative controls");
    println!(
        "  projected false hits against corpus gold keys: {}",
        negative_false_hits.len()
    );
    if !negative_false_hits.is_empty() {
        println!("  false hits: {}", negative_false_hits.join(", "));
    }
    println!("  projected parser errors: {}", negative_errors.len());
    if !negative_errors.is_empty() {
        println!("  errors: {}", negative_errors.join(", "));
    }
    println!("  controls:");
    for control in NEGATIVE_CONTROLS {
        println!("    {:<22} {}", control.id, control.note);
    }
    println!();

    println!("## CJK shingle recovery probe");
    let cjk_added = added_hit_indices(&intent_projected, &cjk_shingle_projected);
    let cjk_improved = improved_rank_indices(&intent_projected, &cjk_shingle_projected);
    println!(
        "  added top-{TOP_K} hits over projected: {} case(s){}",
        cjk_added.len(),
        fmt_idx(&cjk_added)
    );
    println!(
        "  improved first-hit rank over projected: {} case(s){}",
        cjk_improved.len(),
        fmt_idx(&cjk_improved)
    );
    println!("  negative false hits: {}", cjk_negative_false_hits.len());
    if !cjk_negative_false_hits.is_empty() {
        println!("  false hits: {}", cjk_negative_false_hits.join(", "));
    }
    println!("  parser errors: {}", cjk_negative_errors.len());
    if !cjk_negative_errors.is_empty() {
        println!("  errors: {}", cjk_negative_errors.join(", "));
    }
    println!(
        "  contract: scratch-only generated CJK trigrams over projected text; no production tokenizer, schema, reindex, or ranking change"
    );
    println!();

    println!("## Projected plus CJK accepted-candidate fallback");
    let accepted_added = added_hit_indices(&intent_projected, &projected_plus_cjk_acc);
    let accepted_improved = improved_rank_indices(&intent_projected, &projected_plus_cjk_acc);
    println!("  gate: use projected search first; only projected misses may use CJK fallback");
    println!(
        "  fallback: require >= {MIN_CJK_SHINGLE_ACCEPT_OVERLAP} shared CJK trigram terms between query and candidate projected text"
    );
    println!(
        "  added top-{TOP_K} hits over projected: {} case(s){}",
        accepted_added.len(),
        fmt_idx(&accepted_added)
    );
    println!(
        "  improved first-hit rank over projected: {} case(s){}",
        accepted_improved.len(),
        fmt_idx(&accepted_improved)
    );
    println!("  accepted false hits: {}", projected_plus_false_hits.len());
    if !projected_plus_false_hits.is_empty() {
        println!("  false hits: {}", projected_plus_false_hits.join(", "));
    }
    println!("  parser errors: {}", projected_plus_errors.len());
    if !projected_plus_errors.is_empty() {
        println!("  errors: {}", projected_plus_errors.join(", "));
    }
    println!(
        "  contract: eval-only post-candidate filter; no production acceptance or ranking change"
    );
    println!();

    println!("## Per-case first-hit rank (- = no hit in top {TOP_K}; ERR = FTS parser error)");
    println!(
        "  {:<3} {:<34} {:<14} {:>8} {:>10} {:>10} {:>10} {:>10}  {}",
        "#", "id", "stratum", "content", "projected", "cjk_probe", "plus_acc", "exact", "note"
    );
    for (i, case) in CORPUS.iter().enumerate() {
        println!(
            "  {:<3} {:<34} {:<14} {:>8} {:>10} {:>10} {:>10} {:>10}  {}",
            i + 1,
            case.id,
            case.stratum,
            rank_cell(intent_content.ranks[i], intent_content.errors[i].as_deref()),
            rank_cell(
                intent_projected.ranks[i],
                intent_projected.errors[i].as_deref()
            ),
            rank_cell(
                cjk_shingle_projected.ranks[i],
                cjk_shingle_projected.errors[i].as_deref()
            ),
            rank_cell(
                projected_plus_cjk_acc.ranks[i],
                projected_plus_cjk_acc.errors[i].as_deref()
            ),
            rank_cell(
                exact_projected.ranks[i],
                exact_projected.errors[i].as_deref()
            ),
            case.note
        );
    }
    println!();

    println!("## Honest read");
    println!(
        "  intent_content misses:   {} case(s){}",
        miss_indices(&intent_content).len(),
        fmt_idx(&miss_indices(&intent_content))
    );
    println!(
        "  intent_projected misses: {} case(s){}",
        miss_indices(&intent_projected).len(),
        fmt_idx(&miss_indices(&intent_projected))
    );
    println!(
        "  cjk_shingle misses:     {} case(s){}",
        miss_indices(&cjk_shingle_projected).len(),
        fmt_idx(&miss_indices(&cjk_shingle_projected))
    );
    println!(
        "  projected+cjk misses:   {} case(s){}",
        miss_indices(&projected_plus_cjk_acc).len(),
        fmt_idx(&miss_indices(&projected_plus_cjk_acc))
    );
    println!(
        "  exact_projected errors:  {} case(s){}",
        error_indices(&exact_projected).len(),
        fmt_idx(&error_indices(&exact_projected))
    );
    println!(
        "  interpretation: intent_projected is the useful continuity metric. \
         exact_projected mainly checks that authored trigger text can be replayed \
         through the FTS query parser."
    );
    println!(
        "  negative controls:       {} false hit(s), {} parser error(s)",
        negative_false_hits.len(),
        negative_errors.len()
    );
    println!(
        "  cjk negative controls:   {} false hit(s), {} parser error(s)",
        cjk_negative_false_hits.len(),
        cjk_negative_errors.len()
    );
    println!(
        "  projected+cjk controls:  {} false hit(s), {} parser error(s)",
        projected_plus_false_hits.len(),
        projected_plus_errors.len()
    );
    println!(
        "  caveat: hand-curated corpus, N={n}. This is a broader trigger-cohort \
         falsifier, not a production ranking benchmark."
    );

    Ok(())
}

fn load_active_rows(db_path: &std::path::Path) -> SqlResult<Vec<MemoryRow>> {
    let db = RusqliteConnection::open_with_flags(db_path, OpenFlags::SQLITE_OPEN_READ_ONLY)?;
    let mut stmt = db.prepare(
        "SELECT key, content, COALESCE(fts_content, content), tags
         FROM memories
         WHERE status = 'active'
         ORDER BY rowid",
    )?;
    let rows = stmt
        .query_map([], |row| {
            let key: String = row.get(0)?;
            let content: String = row.get(1)?;
            let projected: String = row.get(2)?;
            let tags_s: String = row.get(3)?;
            let tags = parse_str_array(&tags_s);
            let triggers = tags
                .iter()
                .filter_map(|t| t.strip_prefix(TRIGGER_PREFIX).map(str::trim))
                .filter(|t| !t.is_empty())
                .map(ToString::to_string)
                .collect();
            Ok(MemoryRow {
                key,
                content,
                projected,
                triggers,
            })
        })?
        .collect::<SqlResult<Vec<_>>>()?;
    Ok(rows)
}

fn verify_corpus(rows: &[MemoryRow]) -> Result<(), Box<dyn std::error::Error>> {
    let by_key: HashMap<&str, &MemoryRow> = rows.iter().map(|r| (r.key.as_str(), r)).collect();
    let mut seen_ids = BTreeSet::new();
    let mut seen_queries = BTreeSet::new();

    for case in CORPUS {
        if !seen_ids.insert(case.id) {
            return Err(format!("duplicate case id: {}", case.id).into());
        }
        if !seen_queries.insert(case.query) {
            return Err(format!("duplicate query: {}", case.query).into());
        }
        if case.query == case.trigger {
            return Err(format!("{} uses exact trigger text as held-out query", case.id).into());
        }
        if case.stratum.trim().is_empty() {
            return Err(format!("{} has no stratum", case.id).into());
        }
        for expected in case.expect {
            let row = by_key
                .get(expected)
                .ok_or_else(|| format!("{} expected key missing: {expected}", case.id))?;
            if row.triggers.is_empty() {
                return Err(format!("{} expected key has no trigger: {expected}", case.id).into());
            }
        }
    }
    let mut seen_negative_ids = BTreeSet::new();
    let mut seen_negative_queries = BTreeSet::new();
    for control in NEGATIVE_CONTROLS {
        if !seen_negative_ids.insert(control.id) {
            return Err(format!("duplicate negative control id: {}", control.id).into());
        }
        if !seen_negative_queries.insert(control.query) {
            return Err(format!("duplicate negative control query: {}", control.query).into());
        }
    }
    Ok(())
}

#[derive(Clone, Copy)]
enum IndexKind {
    Content,
    Projected,
    ProjectedCjkShingle,
}

struct ScratchFts {
    db: RusqliteConnection,
    projected_by_key: HashMap<String, String>,
}

impl ScratchFts {
    fn build(rows: &[MemoryRow]) -> SqlResult<Self> {
        let db = RusqliteConnection::open_in_memory()?;
        db.execute_batch(
            "CREATE VIRTUAL TABLE content_fts USING fts5(
                 key UNINDEXED,
                 body,
                 tokenize = 'unicode61 remove_diacritics 2'
             );
             CREATE VIRTUAL TABLE projected_fts USING fts5(
                 key UNINDEXED,
                 body,
                 tokenize = 'unicode61 remove_diacritics 2'
             );
             CREATE VIRTUAL TABLE projected_cjk_fts USING fts5(
                 key UNINDEXED,
                 body,
                 tokenize = 'unicode61 remove_diacritics 2'
             );",
        )?;

        let mut projected_by_key = HashMap::new();
        {
            let mut content_stmt =
                db.prepare("INSERT INTO content_fts(key, body) VALUES (?1, ?2)")?;
            let mut projected_stmt =
                db.prepare("INSERT INTO projected_fts(key, body) VALUES (?1, ?2)")?;
            let mut projected_cjk_stmt =
                db.prepare("INSERT INTO projected_cjk_fts(key, body) VALUES (?1, ?2)")?;
            for row in rows {
                content_stmt.execute(params![row.key, row.content])?;
                projected_stmt.execute(params![row.key, row.projected])?;
                let cjk_augmented = augment_with_cjk_shingles(&row.projected);
                projected_cjk_stmt.execute(params![row.key, cjk_augmented])?;
                projected_by_key.insert(row.key.clone(), row.projected.clone());
            }
        }

        Ok(Self {
            db,
            projected_by_key,
        })
    }

    fn search_projected_cjk_shingles(
        &self,
        query: &str,
        limit: usize,
    ) -> Result<Vec<String>, String> {
        let mut terms = BTreeSet::new();
        for term in cjk_shingle_terms(query) {
            terms.insert(term);
        }

        if terms.is_empty() {
            return self.search(IndexKind::Projected, query, limit);
        }

        let mut parts = Vec::new();
        let any = sanitise_fts_query_any(query);
        if !any.is_empty() {
            parts.push(any);
        }
        parts.extend(terms);

        self.search_once(IndexKind::ProjectedCjkShingle, &parts.join(" OR "), limit)
    }

    fn search_projected_cjk_shingles_accepted(
        &self,
        query: &str,
        limit: usize,
    ) -> Result<Vec<String>, String> {
        let query_terms = cjk_shingle_terms(query);
        if query_terms.is_empty() {
            return self.search_projected_cjk_shingles(query, limit);
        }

        let query_terms = query_terms.into_iter().collect::<BTreeSet<_>>();
        let mut accepted = Vec::new();
        for key in self.search_projected_cjk_shingles(query, limit)? {
            let projected = self
                .projected_by_key
                .get(&key)
                .ok_or_else(|| format!("candidate key missing from projected map: {key}"))?;
            if cjk_shingle_overlap_count(&query_terms, projected) >= MIN_CJK_SHINGLE_ACCEPT_OVERLAP
            {
                accepted.push(key);
            }
        }
        Ok(accepted)
    }

    fn search_projected_then_cjk_accepted(
        &self,
        query: &str,
        limit: usize,
    ) -> Result<Vec<String>, String> {
        let projected = self.search(IndexKind::Projected, query, limit)?;
        if !projected.is_empty() {
            return Ok(projected);
        }
        self.search_projected_cjk_shingles_accepted(query, limit)
    }

    fn search(&self, kind: IndexKind, query: &str, limit: usize) -> Result<Vec<String>, String> {
        let precise = sanitise_fts_query(query);
        let any = sanitise_fts_query_any(query);
        let mut rows = self.search_once(kind, &precise, limit)?;
        if rows.is_empty() && any != precise {
            rows = self.search_once(kind, &any, limit)?;
        }
        Ok(rows)
    }

    fn search_once(
        &self,
        kind: IndexKind,
        match_expr: &str,
        limit: usize,
    ) -> Result<Vec<String>, String> {
        let sql = match kind {
            IndexKind::Content => {
                "SELECT key FROM content_fts
                 WHERE content_fts MATCH ?1
                 ORDER BY bm25(content_fts)
                 LIMIT ?2"
            }
            IndexKind::Projected => {
                "SELECT key FROM projected_fts
                 WHERE projected_fts MATCH ?1
                 ORDER BY bm25(projected_fts)
                 LIMIT ?2"
            }
            IndexKind::ProjectedCjkShingle => {
                "SELECT key FROM projected_cjk_fts
                 WHERE projected_cjk_fts MATCH ?1
                 ORDER BY bm25(projected_cjk_fts)
                 LIMIT ?2"
            }
        };
        let mut stmt = self.db.prepare(sql).map_err(|e| e.to_string())?;
        let rows = stmt
            .query_map(params![match_expr, limit as i64], |row| {
                row.get::<_, String>(0)
            })
            .map_err(|e| e.to_string())?
            .collect::<SqlResult<Vec<_>>>()
            .map_err(|e| e.to_string())?;
        Ok(rows)
    }
}

fn debug_case(fts: &ScratchFts, idx1: usize) -> Result<(), Box<dyn std::error::Error>> {
    let case = CORPUS
        .get(idx1.saturating_sub(1))
        .ok_or("case index out of range")?;
    println!("# debug trigger-aware case #{idx1}");
    println!("id:      {}", case.id);
    println!("query:   {}", case.query);
    println!("trigger: {}", case.trigger);
    println!("expect:  {:?}\n", case.expect);

    println!("## query diagnostics");
    dump_query_diagnostics("intent", case.query);
    dump_query_diagnostics("trigger", case.trigger);
    println!();

    for (label, kind, query) in [
        ("intent_content", IndexKind::Content, case.query),
        ("intent_projected", IndexKind::Projected, case.query),
        ("exact_projected", IndexKind::Projected, case.trigger),
    ] {
        println!("## {label}");
        match fts.search(kind, query, TOP_K) {
            Ok(keys) => dump_keys(case.expect, &keys),
            Err(err) => println!("  ERROR: {err}"),
        }
        println!();
    }

    println!("## cjk_shingle_projected");
    match fts.search_projected_cjk_shingles(case.query, TOP_K) {
        Ok(keys) => dump_keys(case.expect, &keys),
        Err(err) => println!("  ERROR: {err}"),
    }
    println!();

    println!("## projected_plus_cjk_accepted");
    match fts.search_projected_then_cjk_accepted(case.query, TOP_K) {
        Ok(keys) => dump_keys(case.expect, &keys),
        Err(err) => println!("  ERROR: {err}"),
    }
    println!();

    Ok(())
}

fn dump_query_diagnostics(label: &str, text: &str) {
    println!("### {label}");
    println!("  precise: {}", sanitise_fts_query(text));
    println!("  any:     {}", sanitise_fts_query_any(text));
    match fts_terms(text) {
        Ok(terms) => println!("  terms:   {}", terms.join(" | ")),
        Err(err) => println!("  terms:   ERROR: {err}"),
    }
}

fn fts_terms(text: &str) -> Result<Vec<String>, String> {
    let db = RusqliteConnection::open_in_memory().map_err(|e| e.to_string())?;
    db.execute_batch(
        "CREATE VIRTUAL TABLE term_probe USING fts5(
             body,
             tokenize = 'unicode61 remove_diacritics 2'
         );
         CREATE VIRTUAL TABLE term_vocab USING fts5vocab(term_probe, 'row');",
    )
    .map_err(|e| e.to_string())?;
    db.execute("INSERT INTO term_probe(body) VALUES (?1)", params![text])
        .map_err(|e| e.to_string())?;
    let mut stmt = db
        .prepare("SELECT term FROM term_vocab ORDER BY term")
        .map_err(|e| e.to_string())?;
    let terms = stmt
        .query_map([], |row| row.get::<_, String>(0))
        .map_err(|e| e.to_string())?
        .collect::<SqlResult<Vec<_>>>()
        .map_err(|e| e.to_string())?;
    Ok(terms)
}

fn augment_with_cjk_shingles(text: &str) -> String {
    let terms = cjk_shingle_terms(text);
    if terms.is_empty() {
        return text.to_string();
    }
    format!("{text}\n\ncjk_trigrams:\n{}", terms.join(" "))
}

fn cjk_shingle_terms(text: &str) -> Vec<String> {
    let mut terms = BTreeSet::new();
    let mut run = Vec::new();

    for ch in text.chars() {
        if is_cjk_unified(ch) {
            run.push(ch);
        } else {
            push_cjk_trigrams(&run, &mut terms);
            run.clear();
        }
    }
    push_cjk_trigrams(&run, &mut terms);

    terms.into_iter().collect()
}

fn cjk_shingle_overlap_count(query_terms: &BTreeSet<String>, text: &str) -> usize {
    cjk_shingle_terms(text)
        .into_iter()
        .filter(|term| query_terms.contains(term))
        .count()
}

fn push_cjk_trigrams(run: &[char], terms: &mut BTreeSet<String>) {
    if run.len() < 3 {
        return;
    }
    for window in run.windows(3) {
        let gram = window.iter().collect::<String>();
        terms.insert(format!("cjk_{gram}"));
    }
}

fn is_cjk_unified(ch: char) -> bool {
    matches!(
        ch,
        '\u{3400}'..='\u{4DBF}'
            | '\u{4E00}'..='\u{9FFF}'
            | '\u{F900}'..='\u{FAFF}'
            | '\u{20000}'..='\u{2A6DF}'
            | '\u{2A700}'..='\u{2B73F}'
            | '\u{2B740}'..='\u{2B81F}'
            | '\u{2B820}'..='\u{2CEAF}'
    )
}

fn dump_keys(expect: &[&str], keys: &[String]) {
    for (i, key) in keys.iter().enumerate() {
        let star = if expect.iter().any(|e| e == key) {
            " <== EXPECTED"
        } else {
            ""
        };
        println!("  {:>2}. {}{}", i + 1, key, star);
    }
}

fn parse_str_array(s: &str) -> Vec<String> {
    serde_json::from_str(s).unwrap_or_default()
}

fn first_hit_rank(keys: &[String], expect: &[&str]) -> Option<usize> {
    keys.iter()
        .position(|k| expect.iter().any(|e| e == k))
        .map(|i| i + 1)
}

fn print_row(label: &str, agg: &Agg, n: usize) {
    let nf = n as f64;
    println!(
        "  {:<18} {:>7.3} {:>7.3} {:>7.3} {:>7.3}",
        label,
        agg.r_at_1 as f64 / nf,
        agg.r_at_5 as f64 / nf,
        agg.r_at_10 as f64 / nf,
        agg.rr_sum / nf,
    );
}

fn added_hit_indices(before: &Agg, after: &Agg) -> Vec<usize> {
    before
        .ranks
        .iter()
        .zip(&after.ranks)
        .enumerate()
        .filter_map(|(i, (b, a))| {
            if b.is_none() && a.is_some() {
                Some(i + 1)
            } else {
                None
            }
        })
        .collect()
}

fn improved_rank_indices(before: &Agg, after: &Agg) -> Vec<usize> {
    before
        .ranks
        .iter()
        .zip(&after.ranks)
        .enumerate()
        .filter_map(|(i, (b, a))| match (b, a) {
            (Some(b), Some(a)) if a < b => Some(i + 1),
            (None, Some(_)) => Some(i + 1),
            _ => None,
        })
        .collect()
}

fn rank_cell(rank: Option<usize>, error: Option<&str>) -> String {
    if error.is_some() {
        return "ERR".to_string();
    }
    match rank {
        Some(r) => r.to_string(),
        None => "-".to_string(),
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

fn stratum_counts() -> Vec<(&'static str, usize)> {
    let mut counts: HashMap<&'static str, usize> = HashMap::new();
    for case in CORPUS {
        *counts.entry(case.stratum).or_default() += 1;
    }
    let mut rows = counts.into_iter().collect::<Vec<_>>();
    rows.sort_by(|(a, _), (b, _)| a.cmp(b));
    rows
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

fn sanitise_fts_query(q: &str) -> String {
    sanitise_fts_query_joined(q, " ")
}

fn sanitise_fts_query_any(q: &str) -> String {
    sanitise_fts_query_joined(q, " OR ")
}

fn sanitise_fts_query_joined(q: &str, join: &str) -> String {
    let trimmed = q.trim();
    if has_invalid_fts_column_prefix(trimmed) {
        let escaped = trimmed.replace('"', "\"\"");
        return format!("\"{escaped}\"");
    }

    let has_operator = trimmed.contains('"')
        || trimmed.contains('*')
        || trimmed.contains(':')
        || trimmed.contains(" AND ")
        || trimmed.contains(" OR ")
        || trimmed.contains(" NOT ")
        || trimmed.contains(" NEAR ")
        || trimmed.contains("NEAR(");
    if has_operator {
        return trimmed.to_string();
    }

    trimmed
        .split(|c: char| !c.is_alphanumeric() && c != '_')
        .filter(|s| !s.is_empty())
        .map(|s| format!("{s}*"))
        .collect::<Vec<_>>()
        .join(join)
}

fn has_invalid_fts_column_prefix(s: &str) -> bool {
    let mut in_quote = false;
    for (idx, ch) in s.char_indices() {
        if ch == '"' {
            in_quote = !in_quote;
            continue;
        }
        if ch != ':' || in_quote {
            continue;
        }
        if !has_valid_fts_column_prefix_before_colon(&s[..idx]) {
            return true;
        }
    }
    false
}

fn has_valid_fts_column_prefix_before_colon(before_colon: &str) -> bool {
    let before = before_colon.trim_end();
    if before.is_empty() {
        return false;
    }

    if let Some(stripped) = before.strip_suffix('}') {
        if let Some(open_idx) = stripped.rfind('{') {
            let inner = stripped[open_idx + 1..].trim();
            return !inner.is_empty() && inner.split_whitespace().all(|col| col == "content");
        }
    }

    let col = before
        .rsplit(|c: char| !c.is_alphanumeric() && c != '_')
        .next()
        .unwrap_or("");
    col == "content"
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
        assert!(
            CORPUS.len() >= 30,
            "trigger-aware corpus should stay at or above 30 cases"
        );
        assert!(
            NEGATIVE_CONTROLS.len() >= 3,
            "trigger-aware corpus should keep negative controls"
        );
        for case in CORPUS {
            assert_ne!(
                case.query, case.trigger,
                "{} must use a held-out intent query, not exact trigger text",
                case.id
            );
            assert!(!case.expect.is_empty(), "{} has no accept set", case.id);
        }
    }

    #[test]
    fn fts_query_sanitizer_matches_memory_search_plain_text_contract() {
        assert_eq!(sanitise_fts_query("warp ipc"), "warp* ipc*");
        assert_eq!(sanitise_fts_query_any("warp ipc"), "warp* OR ipc*");
        assert_eq!(sanitise_fts_query("lens:cosine"), "\"lens:cosine\"");
        assert_eq!(
            sanitise_fts_query("onsen-hd session open"),
            "onsen* hd* session* open*"
        );
        assert_eq!(
            sanitise_fts_query("onsen-hd session open; cloud(mock) ADR-015 v4.19.1"),
            "onsen* hd* session* open* cloud* mock* ADR* 015* v4* 19* 1*"
        );
    }

    #[test]
    fn unicode61_keeps_cjk_runs_as_long_terms() {
        let query_terms =
            fts_terms("五行生克的成熟数学模型、黄金比例控制网络和平衡靶调研结论在哪里")
                .expect("query terms");
        assert_eq!(
            query_terms,
            vec![
                "五行生克的成熟数学模型".to_string(),
                "黄金比例控制网络和平衡靶调研结论在哪里".to_string(),
            ]
        );

        let content_terms = fts_terms(
            "五行生克成熟数学模型调研 黄金比例反馈控制网络 黄金比例五行控制网络 平衡靶 循环平衡环",
        )
        .expect("content terms");
        assert!(content_terms.contains(&"五行生克成熟数学模型调研".to_string()));
        assert!(content_terms.contains(&"黄金比例五行控制网络".to_string()));
        assert!(!content_terms.contains(&query_terms[0]));
        assert!(!content_terms.contains(&query_terms[1]));
    }

    #[test]
    fn cjk_shingle_probe_recovers_paraphrase_overlap_without_changing_projected_fts() {
        let query = "五行生克的成熟数学模型、黄金比例控制网络和平衡靶调研结论在哪里";
        let row = MemoryRow {
            key: "target".to_string(),
            content: String::new(),
            projected:
                "五行生克成熟数学模型调研 黄金比例反馈控制网络 黄金比例五行控制网络 平衡靶 循环平衡环"
                    .to_string(),
            triggers: Vec::new(),
        };
        let fts = ScratchFts::build(&[row]).expect("scratch fts");

        let projected = fts
            .search(IndexKind::Projected, query, TOP_K)
            .expect("projected search");
        assert!(projected.is_empty(), "baseline unicode61 path should miss");

        let recovered = fts
            .search_projected_cjk_shingles(query, TOP_K)
            .expect("cjk shingle search");
        assert_eq!(recovered, vec!["target".to_string()]);

        let terms = cjk_shingle_terms(query);
        assert!(terms.contains(&"cjk_五行生".to_string()));
        assert!(terms.contains(&"cjk_成熟数".to_string()));
        assert!(terms.contains(&"cjk_控制网".to_string()));
    }

    #[test]
    fn cjk_shingle_acceptance_gate_separates_surface_overlap_from_specific_overlap() {
        let query = "五行生克的成熟数学模型、黄金比例控制网络和平衡靶调研结论在哪里";
        let query_terms = cjk_shingle_terms(query)
            .into_iter()
            .collect::<BTreeSet<_>>();

        let target =
            "五行生克成熟数学模型调研 黄金比例反馈控制网络 黄金比例五行控制网络 平衡靶 循环平衡环";
        let tourism = "五行山旅游攻略 黄金比例摄影构图 平衡车购买指南";

        assert!(cjk_shingle_overlap_count(&query_terms, target) >= MIN_CJK_SHINGLE_ACCEPT_OVERLAP);
        assert!(cjk_shingle_overlap_count(&query_terms, tourism) < MIN_CJK_SHINGLE_ACCEPT_OVERLAP);
    }

    #[test]
    fn projected_then_cjk_accepted_uses_cjk_only_as_miss_fallback() {
        let rows = [
            MemoryRow {
                key: "projected_hit".to_string(),
                content: String::new(),
                projected: "ordinary projected anchor".to_string(),
                triggers: Vec::new(),
            },
            MemoryRow {
                key: "cjk_fallback".to_string(),
                content: String::new(),
                projected:
                    "五行生克成熟数学模型调研 黄金比例反馈控制网络 黄金比例五行控制网络 平衡靶"
                        .to_string(),
                triggers: Vec::new(),
            },
        ];
        let fts = ScratchFts::build(&rows).expect("scratch fts");

        assert_eq!(
            fts.search_projected_then_cjk_accepted("ordinary anchor", TOP_K)
                .expect("projected first"),
            vec!["projected_hit".to_string()]
        );

        assert_eq!(
            fts.search_projected_then_cjk_accepted(
                "五行生克的成熟数学模型、黄金比例控制网络和平衡靶调研结论在哪里",
                TOP_K
            )
            .expect("cjk fallback"),
            vec!["cjk_fallback".to_string()]
        );
    }
}
