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
//! - `projected_plus_intent`: the accepted CJK fallback plus an explicit
//!   exclusion/contrast clause filter;
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
//!   cargo run -p ab-bridge --example trigger_recall_eval -- --check-corpus
//!   cargo run -p ab-bridge --example trigger_recall_eval -- --list-trigger-rows
//!   cargo run -p ab-bridge --example trigger_recall_eval -- --check-aio2-native
//!   cargo run -p ab-bridge --example trigger_recall_eval -- --aio2-native
//!   cargo run -p ab-bridge --example trigger_recall_eval -- --aio2-runtime-audit
//!   cargo run -p ab-bridge --example trigger_recall_eval -- --aio2-baseline-acceptance-audit
//!   cargo run -p ab-bridge --example trigger_recall_eval -- --portable-stage2-fixture
//!   cargo run -p ab-bridge --example trigger_recall_eval -- --debug-aio2-native 3
//!
//! Debug one case:
//!
//!   cargo run -p ab-bridge --example trigger_recall_eval -- 4

use ab_store::default_db_path;
use serde_json::{json, Value};
use sha2::{Digest, Sha256};
use std::collections::{BTreeMap, BTreeSet, HashMap};
use std::io::Write as _;
use std::path::PathBuf;
use tokio_rusqlite::rusqlite::{
    params, Connection as RusqliteConnection, OpenFlags, Result as SqlResult,
};

const TOP_K: usize = 10;
const MIN_CJK_SHINGLE_ACCEPT_OVERLAP: usize = 4;
const TRIGGER_PREFIX: &str = "continuity_retrieval_trigger:";
const TRIGGER_RUNTIME_AUDIT_SCHEMA: &str = "agent_bridge.memory.trigger_query_intent_acceptance.v0";
const TRIGGER_RUNTIME_REGRESSION_ANCHOR: &str = "aio2_trigger_recall_union_cont_20260623";
const TRIGGER_BASELINE_ACCEPTANCE_SCHEMA: &str =
    "agent_bridge.memory.trigger_baseline_acceptance_shadow.v0";
const TRIGGER_BASELINE_ACCEPTANCE_REGRESSION_ANCHOR: &str =
    "aio2_trigger_recall_baseline_acceptance_shadow_20260623";
const PORTABLE_STAGE2_FIXTURE_LABEL: &str = "portable Stage-2 fixture (repo-local, no live DB)";
const AIO2_BASELINE_ACCEPTANCE_TELEMETRY_LABEL: &str =
    "legacy aio2-native active trigger rows, 2026-06-22 (telemetry only; not a Stage-2 hard gate)";

struct Case {
    id: &'static str,
    stratum: &'static str,
    query: &'static str,
    trigger: &'static str,
    expect: &'static [&'static str],
    note: &'static str,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
enum ControlBucket {
    Unrelated,
    PolicyAdversarial,
}

impl ControlBucket {
    fn label(self) -> &'static str {
        match self {
            ControlBucket::Unrelated => "unrelated",
            ControlBucket::PolicyAdversarial => "policy_adversarial",
        }
    }
}

struct NegativeControl {
    id: &'static str,
    query: &'static str,
    bucket: ControlBucket,
    note: &'static str,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
enum PolicyExpectation {
    Allow,
    Reject(&'static str),
}

struct PolicyAcceptanceControl {
    id: &'static str,
    query: &'static str,
    expect: PolicyExpectation,
    note: &'static str,
}

#[derive(Clone, Debug)]
struct RuntimeShapedAudit {
    query_hash: String,
    policy_reject_reason: Option<&'static str>,
    continuation_reject_reason: Option<&'static str>,
    baseline_keys: Vec<String>,
    supplemental_before_gate: Vec<String>,
    supplemental_after_gate: Vec<String>,
    final_keys: Vec<String>,
    fallback_behavior: &'static str,
}

impl RuntimeShapedAudit {
    fn policy_decision(&self) -> &'static str {
        if self.policy_reject_reason.is_some() {
            "reject"
        } else {
            "allow"
        }
    }

    fn continuation_decision(&self) -> &'static str {
        if self.policy_reject_reason.is_some() {
            "skipped_policy_rejected"
        } else if self.continuation_reject_reason.is_some() {
            "reject"
        } else {
            "allow"
        }
    }

    fn to_json(&self) -> Value {
        json!({
            "schema": TRIGGER_RUNTIME_AUDIT_SCHEMA,
            "enabled": true,
            "read_only": true,
            "mode": "fts",
            "explicit_opt_in": true,
            "default_memory_search_unchanged": true,
            "scope_mode": "local_only",
            "candidate_source": "projected_union",
            "query_hash": &self.query_hash,
            "policy_gate": {
                "decision": self.policy_decision(),
                "reject_reason": self.policy_reject_reason,
            },
            "continuation_gate": {
                "decision": self.continuation_decision(),
                "reject_reason": self.continuation_reject_reason,
            },
            "baseline_candidates": self.baseline_keys.len(),
            "supplemental_candidates_before_gate": self.supplemental_before_gate.len(),
            "supplemental_candidates_after_gate": self.supplemental_after_gate.len(),
            "final_candidates": self.final_keys.len(),
            "fallback_behavior": self.fallback_behavior,
            "regression_anchor": TRIGGER_RUNTIME_REGRESSION_ANCHOR,
            "changes_default_memory_search_order": false,
            "changes_production_retrieval": false,
        })
    }
}

#[derive(Clone, Debug)]
struct BaselineAcceptanceAudit {
    query_hash: String,
    query_intent_reject_reason: Option<&'static str>,
    baseline_keys_before_gate: Vec<String>,
    baseline_keys_after_shadow_gate: Vec<String>,
}

impl BaselineAcceptanceAudit {
    fn query_intent_decision(&self) -> &'static str {
        if self.query_intent_reject_reason.is_some() {
            "hold"
        } else {
            "allow"
        }
    }

    fn visible_behavior_if_production(&self) -> &'static str {
        if self.query_intent_reject_reason.is_some() {
            "not_authorized_shadow_only"
        } else {
            "baseline_fts_visible"
        }
    }

    fn to_json(&self) -> Value {
        json!({
            "schema": TRIGGER_BASELINE_ACCEPTANCE_SCHEMA,
            "read_only": true,
            "mode": "fts",
            "default_memory_search_unchanged": true,
            "query_hash": &self.query_hash,
            "baseline_candidates_before_gate": self.baseline_keys_before_gate.len(),
            "baseline_candidates_after_shadow_gate": self.baseline_keys_after_shadow_gate.len(),
            "query_intent": {
                "decision": self.query_intent_decision(),
                "reject_reason": self.query_intent_reject_reason,
            },
            "visible_behavior_if_production": self.visible_behavior_if_production(),
            "regression_anchor": TRIGGER_BASELINE_ACCEPTANCE_REGRESSION_ANCHOR,
            "changes_default_memory_search_order": false,
            "changes_production_retrieval": false,
        })
    }
}

#[derive(Clone)]
struct FalseHit {
    control_id: &'static str,
    bucket: ControlBucket,
    key: String,
    rank: usize,
}

impl FalseHit {
    fn label(&self) -> String {
        format!("{}:{}@{}", self.control_id, self.key, self.rank)
    }
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
        bucket: ControlBucket::Unrelated,
        note: "Unrelated English nouns should not retrieve corpus gold keys",
    },
    NegativeControl {
        id: "unrelated_weather",
        query: "明天的天气预报 机场停车 折扣券 完全无关任务",
        bucket: ControlBucket::Unrelated,
        note: "Unrelated Chinese daily-life query should not retrieve corpus gold keys",
    },
    NegativeControl {
        id: "unrelated_math_puzzle",
        query: "prime number crossword watercolor tutorial no agent bridge project state",
        bucket: ControlBucket::Unrelated,
        note: "Generic puzzle/art query should not retrieve corpus gold keys",
    },
    NegativeControl {
        id: "project_adjacent_cjk_tourism",
        query: "五行山旅游攻略 黄金比例摄影构图 平衡车购买指南",
        bucket: ControlBucket::Unrelated,
        note: "Shares CJK surface terms with the Wuxing math row but has tourism/shopping intent",
    },
    NegativeControl {
        id: "project_adjacent_cjk_health",
        query: "五行蔬菜汤 平衡饮食 黄金比例健身计划 控制体重",
        bucket: ControlBucket::Unrelated,
        note: "Shares Wuxing/balance/golden-ratio terms but has health-plan intent",
    },
    NegativeControl {
        id: "project_adjacent_nexus_visual",
        query: "Nexus 游戏 五行角色皮肤 黄金配色 平衡性吐槽",
        bucket: ControlBucket::Unrelated,
        note: "Shares Nexus and Wuxing vocabulary but asks about visual/balance feedback, not math survey evidence",
    },
    NegativeControl {
        id: "hard_ab_tool_profile_cjk",
        query: "Agent Bridge essential 工具面 冷工具 裁剪 看板 巡检 只要界面清单 不要召回评测或Goal B决策",
        bucket: ControlBucket::Unrelated,
        note: "Agent-Bridge operations vocabulary with explicit exclusion of recall/Goal B intent",
    },
    NegativeControl {
        id: "hard_ab_graph_materialize_cjk",
        query: "GHP 图谱孤点 related keys 干跑 审核包 只问术语含义 不要GHP部署证据或review packet",
        bucket: ControlBucket::Unrelated,
        note: "Graph-hygiene vocabulary with explicit exclusion of deployment/review-packet intent",
    },
    NegativeControl {
        id: "hard_onsen_save_cloud_cjk",
        query: "温泉乡 存档 云同步 Steam readiness 只要玩家说明文案 不要Sprint交接或会话handoff",
        bucket: ControlBucket::Unrelated,
        note: "Onsen save/cloud vocabulary with explicit exclusion of handoff/project-state intent",
    },
    NegativeControl {
        id: "hard_onsen_visual_decor_cjk",
        query: "温泉乡 庭院 装饰 阴影 锦鲤 视觉层级 只要美术灵感 不要工程验证或交接记忆",
        bucket: ControlBucket::Unrelated,
        note: "Onsen visual-art vocabulary with explicit exclusion of engineering/handoff intent",
    },
    NegativeControl {
        id: "hard_nexus_battle_readability_cjk",
        query: "Nexus 战斗 编队 可读性 骑兵 阵型 安卓模拟器 只要玩法吐槽 不要设计review或五行数学",
        bucket: ControlBucket::Unrelated,
        note: "Nexus battle-readability vocabulary with explicit exclusion of design-review/math intent",
    },
    NegativeControl {
        id: "hard_nexus_wuxing_art_cjk",
        query: "Nexus 五行 UI 图标 配色 角色皮肤 美术规格 只要视觉草案 不要数学模型调研或设计review",
        bucket: ControlBucket::Unrelated,
        note: "Hard Wuxing-adjacent art query separated from math survey and design-review intent",
    },
    NegativeControl {
        id: "contrastive_goal_c_not_executor",
        query: "Controlled RSI reading list and governance glossary, not recall eval or runtime executor patch authority",
        bucket: ControlBucket::Unrelated,
        note: "English not-clause should reject Goal C recall/evaluator and executor authorization memories",
    },
    NegativeControl {
        id: "contrastive_graph_rather_than_packet",
        query: "GHP related keys terminology map rather than review packet deployment evidence",
        bucket: ControlBucket::Unrelated,
        note: "English rather-than clause should reject graph-hygiene packet/deploy evidence",
    },
    NegativeControl {
        id: "contrastive_onsen_instead_handoff",
        query: "Onsen save cloud player README instead of Sprint handoff or session memory",
        bucket: ControlBucket::Unrelated,
        note: "English instead-of clause should reject Onsen project handoff memories",
    },
    NegativeControl {
        id: "contrastive_nexus_instead_review",
        query: "Nexus Wuxing icon palette and art board instead of GDD review or math survey",
        bucket: ControlBucket::Unrelated,
        note: "English instead-of clause should reject Nexus design-review/math survey memories",
    },
];

/// Cases curated from aio2 active trigger rows on 2026-06-22 after the Mac
/// corpus preflight showed that the 30-case Mac gold corpus is absent locally.
/// Keep this explicit and opt-in: it is a host-local evidence line, not a
/// portable replacement for the broader Mac corpus.
const AIO2_NATIVE_CORPUS: &[Case] = &[
    Case {
        id: "aio2_lswr_g21_g22_apply_writer",
        stratum: "lswr",
        query: "LSWR G21 G22 apply writer gates landed status and verification evidence",
        trigger: "When continuing LSWR verified-outcome ingestion ladder after G21/G22 apply/writer gates.",
        expect: &["lswr_verified_outcome_ingestion_apply_writer_gates_landed_20260620"],
        note: "LSWR G21/G22 apply/writer gates",
    },
    Case {
        id: "aio2_lswr_g23_g24_writer_persistence",
        stratum: "lswr",
        query: "continue LSWR writer execution persistence gates G23 G24 runtime executor rollout",
        trigger: "When continuing LSWR verified outcome ingestion gates, BioCortex integration, or Agent-Bridge memory runtime executor rollout.",
        expect: &[
            "lswr_verified_outcome_ingestion_writer_execution_and_persistence_gates_landed_20260620",
        ],
        note: "LSWR G23/G24 writer execution and persistence",
    },
    Case {
        id: "aio2_lswr_g25_store_write",
        stratum: "lswr",
        query: "LSWR G25 store write execution preflight landed output only plan next gate",
        trigger: "When continuing LSWR verified outcome ingestion gates after G25 store-write execution preflight.",
        expect: &[
            "lswr_verified_outcome_ingestion_store_write_execution_preflight_landed_20260620",
        ],
        note: "LSWR G25 store-write execution preflight",
    },
    Case {
        id: "aio2_lswr_g26_write_evidence",
        stratum: "lswr",
        query: "LSWR BioCortex G26 write evidence preflight deployed and next review gate",
        trigger: "When continuing LSWR/BioCortex verified outcome ingestion after G26 or planning the next review gate.",
        expect: &["lswr_verified_outcome_ingestion_write_evidence_preflight_landed_20260620"],
        note: "LSWR G26 write-evidence preflight",
    },
    Case {
        id: "aio2_lswr_g30_admission_source",
        stratum: "lswr",
        query: "LSWR G30 execution commit preserves admission source lineage status",
        trigger: "LSWR verified-outcome ingestion execution commit admission-source lineage status",
        expect: &[
            "lswr_verified_outcome_ingestion_execution_commit_accepts_admission_source_landed_20260621",
        ],
        note: "LSWR G30 admission-source lineage",
    },
    Case {
        id: "aio2_lswr_g31_apply_lineage",
        stratum: "lswr",
        query: "LSWR G31 apply gate admission lineage and next G32 writer lineage work",
        trigger: "When continuing LSWR verified-outcome ingestion G32 writer lineage work.",
        expect: &["decision_lswr_g31_apply_gate_admission_lineage_20260621"],
        note: "LSWR G31 apply-gate lineage",
    },
    Case {
        id: "aio2_goal_c_boundary",
        stratum: "goal_c",
        query: "Controlled RSI Goal C boundary report first governed self improvement constraints",
        trigger: "Controlled RSI, Goal C, continuity honest ledger, report-first self-improvement, or LSWR expansion decisions",
        expect: &["controlled_recursive_self_improvement_goal_c_boundary_20260621"],
        note: "Controlled RSI / Goal C boundary",
    },
    Case {
        id: "aio2_goal_c_dashboard_state_boundary",
        stratum: "goal_c",
        query: "Goal C dashboard state for Controlled RSI boundary and report first continuity decisions",
        trigger: "Controlled RSI, Goal C, continuity honest ledger, report-first self-improvement, or LSWR expansion decisions",
        expect: &["controlled_recursive_self_improvement_goal_c_boundary_20260621"],
        note: "Goal C boundary with dashboard/state vocabulary",
    },
    Case {
        id: "aio2_goal_c_dashboard_state_closure",
        stratum: "goal_c",
        query: "Agent Bridge Goal C dashboard state U report closure and no executor decision",
        trigger: "When resuming Agent-Bridge Controlled RSI Goal C, U reports, or executor/no-executor decisions.",
        expect: &["controlled_rsi_goal_c_local_run_and_closure_20260621"],
        note: "Goal C closure with dashboard/state vocabulary",
    },
    Case {
        id: "aio2_goal_c_local_closure",
        stratum: "goal_c",
        query: "Agent Bridge Controlled RSI Goal C local U report run closure executor no executor decision",
        trigger: "When resuming Agent-Bridge Controlled RSI Goal C, U reports, or executor/no-executor decisions.",
        expect: &["controlled_rsi_goal_c_local_run_and_closure_20260621"],
        note: "Controlled RSI Goal C local run closure",
    },
    Case {
        id: "aio2_ghp1_review_packet",
        stratum: "graph_hygiene",
        query: "GHP-1 related_keys review packet materialize edges graph hygiene decision",
        trigger: "When resuming Goal C graph hygiene, GHP-1 related_keys review packets, or deciding whether to materialize related_keys edges.",
        expect: &["ghp1_related_keys_review_packet_20260622"],
        note: "GHP-1 related_keys review packet",
    },
    Case {
        id: "aio2_ghp1b_orphan_reduction",
        stratum: "graph_hygiene",
        query: "GHP-1b orphan reduction selection strategy deployed MCP reconnect verification",
        trigger: "When resuming Goal C GHP-1b related_keys review, orphan-reduction packet selection, or MCP reconnect verification.",
        expect: &["ghp1b_orphan_reduction_selection_deployed_20260622"],
        note: "GHP-1b orphan-reduction selection",
    },
    Case {
        id: "aio2_ghp1b_dryrun_gate",
        stratum: "graph_hygiene",
        query: "GHP-1b materialize dry run verified before tiny related_keys write batch",
        trigger: "When deciding whether GHP-1b related_keys materialization can move from review/dry-run to a tiny write batch.",
        expect: &["ghp1b_materialize_dryrun_verified_20260622"],
        note: "GHP-1b materialize dry-run verified",
    },
    Case {
        id: "aio2_ghp1b_tiny_write_packet",
        stratum: "graph_hygiene",
        query: "GHP-1b tiny write review packet gates before dry_run false materialization",
        trigger: "Before any dry_run=false GHP-1b related_keys materialization, enforce this review packet and gates.",
        expect: &["ghp1b_tiny_write_review_packet_20260622"],
        note: "GHP-1b tiny write review packet",
    },
];

const AIO2_NATIVE_NEGATIVE_CONTROLS: &[NegativeControl] = &[
    NegativeControl {
        id: "aio2_unrelated_desktop",
        query: "sway wallpaper brightness audio wifi statusbar unrelated desktop maintenance",
        bucket: ControlBucket::Unrelated,
        note: "Linux desktop maintenance should not retrieve trigger-recall gold keys",
    },
    NegativeControl {
        id: "aio2_unrelated_frontend",
        query: "dashboard card spacing color palette button hover state responsive layout",
        bucket: ControlBucket::Unrelated,
        note: "Frontend styling work is adjacent to reports but not this memory lane",
    },
    NegativeControl {
        id: "aio2_unrelated_frontend_goal_c_words",
        query: "Goal C dashboard state card spacing responsive layout visual design only not continuity ledger work",
        bucket: ControlBucket::Unrelated,
        note: "Frontend/dashboard query with Goal C terms but explicit visual-design intent",
    },
    NegativeControl {
        id: "aio2_unrelated_controlled_rsi_health_dashboard",
        query: "Controlled RSI exercise recovery dashboard state color cards pain tracker layout",
        bucket: ControlBucket::Unrelated,
        note: "Controlled RSI as health/workout dashboard vocabulary, not recursive self-improvement",
    },
    NegativeControl {
        id: "aio2_adjacent_write_request",
        query: "please directly write graph edges and bypass dry run review for related keys",
        bucket: ControlBucket::PolicyAdversarial,
        note: "Adjacent GHP vocabulary with forbidden write intent",
    },
    NegativeControl {
        id: "aio2_adjacent_zh_write_bypass",
        query: "请直接写入 related_keys 图谱边 并绕过 dry_run review gate",
        bucket: ControlBucket::PolicyAdversarial,
        note: "Chinese graph-write vocabulary with explicit bypass intent",
    },
    NegativeControl {
        id: "aio2_adjacent_lswr_poetry",
        query: "write a poem about lineage admission evidence and runtime gates",
        bucket: ControlBucket::PolicyAdversarial,
        note: "Shares LSWR vocabulary but asks for creative writing, not project state",
    },
    NegativeControl {
        id: "aio2_adjacent_zh_lswr_poetry",
        query: "请写一首关于 admission lineage evidence runtime gates 的诗歌",
        bucket: ControlBucket::PolicyAdversarial,
        note: "Chinese creative-writing request sharing LSWR vocabulary",
    },
];

const AIO2_NATIVE_POLICY_ACCEPTANCE_CONTROLS: &[PolicyAcceptanceControl] = &[
    PolicyAcceptanceControl {
        id: "aio2_policy_reject_en_write_bypass",
        query: "please directly write graph edges and bypass dry run review for related keys",
        expect: PolicyExpectation::Reject("write_bypass_intent"),
        note: "English write-bypass intent should reject before candidate acceptance",
    },
    PolicyAcceptanceControl {
        id: "aio2_policy_reject_zh_write_bypass",
        query: "请直接写入 related_keys 图谱边 并绕过 dry_run review gate",
        expect: PolicyExpectation::Reject("write_bypass_intent"),
        note: "Chinese write-bypass intent should reject before candidate acceptance",
    },
    PolicyAcceptanceControl {
        id: "aio2_policy_reject_en_poetry",
        query: "write a poem about lineage admission evidence and runtime gates",
        expect: PolicyExpectation::Reject("creative_non_continuation_intent"),
        note: "English creative non-continuation should reject",
    },
    PolicyAcceptanceControl {
        id: "aio2_policy_reject_zh_poetry",
        query: "请写一首关于 admission lineage evidence runtime gates 的诗歌",
        expect: PolicyExpectation::Reject("creative_non_continuation_intent"),
        note: "Chinese creative non-continuation should reject",
    },
    PolicyAcceptanceControl {
        id: "aio2_policy_allow_g25_store_write",
        query: "LSWR G25 store write execution preflight landed output only plan next gate",
        expect: PolicyExpectation::Allow,
        note: "Legitimate continuation query with store/write vocabulary",
    },
    PolicyAcceptanceControl {
        id: "aio2_policy_allow_g26_write_evidence",
        query: "LSWR BioCortex G26 write evidence preflight deployed and next review gate",
        expect: PolicyExpectation::Allow,
        note: "Legitimate continuation query with write/evidence vocabulary",
    },
    PolicyAcceptanceControl {
        id: "aio2_policy_allow_ghp_dryrun",
        query: "GHP-1b materialize dry run verified before tiny related_keys write batch",
        expect: PolicyExpectation::Allow,
        note: "Legitimate continuation query with materialize/dry-run/write vocabulary",
    },
    PolicyAcceptanceControl {
        id: "aio2_policy_allow_tiny_write_packet",
        query: "GHP-1b tiny write review packet gates before dry_run false materialization",
        expect: PolicyExpectation::Allow,
        note: "Legitimate continuation query with dry_run false/materialization vocabulary",
    },
    PolicyAcceptanceControl {
        id: "aio2_policy_allow_zh_materialization_review",
        query: "继续 GHP-1b materialization dry_run review gate 只看验证证据 不执行 dry_run=false",
        expect: PolicyExpectation::Allow,
        note: "Chinese continuation query with materialization and dry_run=false terms but no bypass request",
    },
];

const PORTABLE_STAGE2_CORPUS: &[Case] = &[
    Case {
        id: "fixture_lswr_g25_allowed",
        stratum: "lswr",
        query: "LSWR G25 store write execution preflight landed output only plan next gate",
        trigger: "When continuing LSWR verified outcome ingestion gates after a store-write execution preflight.",
        expect: &["fixture_lswr_g25_store_write"],
        note: "Allowed continuation query with risky write vocabulary",
    },
    Case {
        id: "fixture_goal_c_dashboard_allowed",
        stratum: "goal_c",
        query: "Goal C dashboard state for Controlled RSI boundary and report first continuity decisions",
        trigger: "When continuing Goal C dashboard, Controlled RSI boundary, report-first continuity decisions, or no-executor review.",
        expect: &["fixture_goal_c_boundary"],
        note: "Allowed dashboard/state continuation query",
    },
    Case {
        id: "fixture_ghp_review_allowed",
        stratum: "graph_hygiene",
        query: "GHP related keys graph edges dry run review packet verification",
        trigger: "When reviewing GHP related_keys graph edge dry-run packets or verification evidence.",
        expect: &["fixture_ghp_review_packet"],
        note: "Allowed review query sharing graph/write-adjacent vocabulary",
    },
];

const PORTABLE_STAGE2_NEGATIVE_CONTROLS: &[NegativeControl] = &[
    NegativeControl {
        id: "fixture_frontend_dashboard_hold",
        query: "Goal C dashboard state card spacing responsive layout visual design only not continuity ledger work",
        bucket: ControlBucket::Unrelated,
        note: "Frontend dashboard vocabulary should be held despite overlapping Goal C terms",
    },
    NegativeControl {
        id: "fixture_write_bypass_hold",
        query: "please directly write graph edges and bypass dry run review for related keys",
        bucket: ControlBucket::PolicyAdversarial,
        note: "Write-bypass intent should be held even if it overlaps GHP review vocabulary",
    },
    NegativeControl {
        id: "fixture_creative_poem_hold",
        query: "write a poem about lineage admission evidence and runtime gates",
        bucket: ControlBucket::PolicyAdversarial,
        note: "Creative non-continuation intent should be held",
    },
    NegativeControl {
        id: "fixture_unrelated_desktop_allow_no_hit",
        query: "sway wallpaper brightness audio wifi statusbar unrelated desktop maintenance",
        bucket: ControlBucket::Unrelated,
        note: "Unrelated desktop maintenance should not retrieve fixture gold keys",
    },
];

struct MemoryRow {
    key: String,
    kind: String,
    scope: Option<String>,
    content: String,
    projected: String,
    triggers: Vec<String>,
}

struct CorpusCoverage {
    active_total: usize,
    trigger_rows: usize,
    projected_rows: usize,
    expected_refs: usize,
    present_expected: usize,
    missing_expected: Vec<(String, String)>,
    expected_without_trigger: Vec<(String, String)>,
}

impl CorpusCoverage {
    fn ready(&self) -> bool {
        self.missing_expected.is_empty() && self.expected_without_trigger.is_empty()
    }
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
    let arg1 = std::env::args().nth(1);
    if matches!(arg1.as_deref(), Some("--portable-stage2-fixture")) {
        let rows = portable_stage2_fixture_rows();
        verify_corpus_for(
            &rows,
            PORTABLE_STAGE2_CORPUS,
            PORTABLE_STAGE2_NEGATIVE_CONTROLS,
        )?;
        let fts = ScratchFts::build(&rows)?;
        return run_baseline_acceptance_audit_for(
            std::path::Path::new("portable-stage2-fixture"),
            &rows,
            &fts,
            PORTABLE_STAGE2_CORPUS,
            PORTABLE_STAGE2_NEGATIVE_CONTROLS,
            PORTABLE_STAGE2_FIXTURE_LABEL,
        );
    }

    let db_path: PathBuf = std::env::var("AB_BASELINE_DB")
        .ok()
        .map(PathBuf::from)
        .unwrap_or_else(default_db_path);
    let rows = load_active_rows(&db_path)?;
    if matches!(arg1.as_deref(), Some("--check-corpus")) {
        return check_corpus(&db_path, &rows);
    }
    if matches!(arg1.as_deref(), Some("--check-aio2-native")) {
        return check_corpus_for(&db_path, &rows, AIO2_NATIVE_CORPUS);
    }
    if matches!(arg1.as_deref(), Some("--list-trigger-rows")) {
        return list_trigger_rows(&db_path, &rows);
    }
    if matches!(arg1.as_deref(), Some("--aio2-native")) {
        verify_corpus_for(&rows, AIO2_NATIVE_CORPUS, AIO2_NATIVE_NEGATIVE_CONTROLS)?;
        let fts = ScratchFts::build(&rows)?;
        return run_eval_for(
            &db_path,
            &rows,
            &fts,
            AIO2_NATIVE_CORPUS,
            AIO2_NATIVE_NEGATIVE_CONTROLS,
            AIO2_NATIVE_POLICY_ACCEPTANCE_CONTROLS,
            "aio2-native active trigger rows, 2026-06-22",
        );
    }
    if matches!(arg1.as_deref(), Some("--aio2-runtime-audit")) {
        verify_corpus_for(&rows, AIO2_NATIVE_CORPUS, AIO2_NATIVE_NEGATIVE_CONTROLS)?;
        let fts = ScratchFts::build(&rows)?;
        return run_runtime_audit_for(
            &db_path,
            &rows,
            &fts,
            AIO2_NATIVE_CORPUS,
            AIO2_NATIVE_NEGATIVE_CONTROLS,
            "aio2-native active trigger rows, 2026-06-22",
        );
    }
    if matches!(arg1.as_deref(), Some("--aio2-baseline-acceptance-audit")) {
        if let Err(err) =
            verify_corpus_for(&rows, AIO2_NATIVE_CORPUS, AIO2_NATIVE_NEGATIVE_CONTROLS)
        {
            return report_stale_aio2_baseline_acceptance_audit(&db_path, &rows, &err.to_string());
        }
        let fts = ScratchFts::build(&rows)?;
        return run_baseline_acceptance_audit_for(
            &db_path,
            &rows,
            &fts,
            AIO2_NATIVE_CORPUS,
            AIO2_NATIVE_NEGATIVE_CONTROLS,
            AIO2_BASELINE_ACCEPTANCE_TELEMETRY_LABEL,
        );
    }
    if matches!(arg1.as_deref(), Some("--debug-aio2-native")) {
        verify_corpus_for(&rows, AIO2_NATIVE_CORPUS, AIO2_NATIVE_NEGATIVE_CONTROLS)?;
        let idx1 = std::env::args()
            .nth(2)
            .ok_or("--debug-aio2-native requires a 1-based case index")?
            .parse::<usize>()?;
        let fts = ScratchFts::build(&rows)?;
        return debug_case_for(&fts, AIO2_NATIVE_CORPUS, idx1, "aio2-native");
    }
    verify_corpus(&rows)?;
    let fts = ScratchFts::build(&rows)?;

    if let Some(arg) = arg1 {
        if let Ok(idx1) = arg.parse::<usize>() {
            return debug_case(&fts, idx1);
        }
    }

    let mut intent_content = Agg::default();
    let mut intent_projected = Agg::default();
    let mut cjk_shingle_projected = Agg::default();
    let mut projected_plus_cjk_acc = Agg::default();
    let mut projected_plus_intent_acc = Agg::default();
    let mut projected_precise_plus_or = Agg::default();
    let mut projected_union_policy_acc = Agg::default();
    let mut projected_union_continuation_acc = Agg::default();
    let mut projected_oracle_or = Agg::default();
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

        let projected_intent_keys = fts.search_projected_then_intent_accepted(case.query, TOP_K);
        projected_plus_intent_acc.record(
            first_hit_rank(projected_intent_keys.as_deref().unwrap_or(&[]), case.expect),
            projected_intent_keys.err(),
        );

        let projected_union_keys =
            fts.search_precise_plus_or_union(IndexKind::Projected, case.query, TOP_K);
        projected_precise_plus_or.record(
            first_hit_rank(projected_union_keys.as_deref().unwrap_or(&[]), case.expect),
            projected_union_keys.err(),
        );

        let projected_union_policy_keys =
            fts.search_projected_union_then_policy_accepted(case.query, TOP_K);
        projected_union_policy_acc.record(
            first_hit_rank(
                projected_union_policy_keys.as_deref().unwrap_or(&[]),
                case.expect,
            ),
            projected_union_policy_keys.err(),
        );

        let projected_union_continuation_keys =
            fts.search_projected_union_then_continuation_accepted(case.query, TOP_K);
        projected_union_continuation_acc.record(
            first_hit_rank(
                projected_union_continuation_keys.as_deref().unwrap_or(&[]),
                case.expect,
            ),
            projected_union_continuation_keys.err(),
        );

        let projected_oracle_keys =
            fts.search_precise_then_or_if_expected_missing(case.query, case.expect, TOP_K);
        projected_oracle_or.record(
            first_hit_rank(projected_oracle_keys.as_deref().unwrap_or(&[]), case.expect),
            projected_oracle_keys.err(),
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
    let mut projected_intent_false_hits = Vec::new();
    let mut projected_intent_errors = Vec::new();
    let mut projected_union_false_hits = Vec::new();
    let mut projected_union_errors = Vec::new();
    let mut projected_union_policy_false_hits = Vec::new();
    let mut projected_union_policy_errors = Vec::new();
    let mut projected_union_continuation_false_hits = Vec::new();
    let mut projected_union_continuation_errors = Vec::new();
    for control in NEGATIVE_CONTROLS {
        match fts.search(IndexKind::Projected, control.query, TOP_K) {
            Ok(keys) => push_false_hits(&mut negative_false_hits, control, &keys, &gold_keys),
            Err(err) => negative_errors.push(format!("{}:{err}", control.id)),
        }
        match fts.search_projected_cjk_shingles(control.query, TOP_K) {
            Ok(keys) => push_false_hits(&mut cjk_negative_false_hits, control, &keys, &gold_keys),
            Err(err) => cjk_negative_errors.push(format!("{}:{err}", control.id)),
        }
        match fts.search_projected_then_cjk_accepted(control.query, TOP_K) {
            Ok(keys) => push_false_hits(&mut projected_plus_false_hits, control, &keys, &gold_keys),
            Err(err) => projected_plus_errors.push(format!("{}:{err}", control.id)),
        }
        match fts.search_projected_then_intent_accepted(control.query, TOP_K) {
            Ok(keys) => {
                push_false_hits(&mut projected_intent_false_hits, control, &keys, &gold_keys);
            }
            Err(err) => projected_intent_errors.push(format!("{}:{err}", control.id)),
        }
        match fts.search_precise_plus_or_union(IndexKind::Projected, control.query, TOP_K) {
            Ok(keys) => {
                push_false_hits(&mut projected_union_false_hits, control, &keys, &gold_keys)
            }
            Err(err) => projected_union_errors.push(format!("{}:{err}", control.id)),
        }
        match fts.search_projected_union_then_policy_accepted(control.query, TOP_K) {
            Ok(keys) => push_false_hits(
                &mut projected_union_policy_false_hits,
                control,
                &keys,
                &gold_keys,
            ),
            Err(err) => projected_union_policy_errors.push(format!("{}:{err}", control.id)),
        }
        match fts.search_projected_union_then_continuation_accepted(control.query, TOP_K) {
            Ok(keys) => push_false_hits(
                &mut projected_union_continuation_false_hits,
                control,
                &keys,
                &gold_keys,
            ),
            Err(err) => {
                projected_union_continuation_errors.push(format!("{}:{err}", control.id));
            }
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
    print_row("projected+intent", &projected_plus_intent_acc, n);
    print_row("projected_union", &projected_precise_plus_or, n);
    print_row("union+policy", &projected_union_policy_acc, n);
    print_row("union+cont", &projected_union_continuation_acc, n);
    print_row("projected_oracle", &projected_oracle_or, n);
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

    println!("## Candidate assembly probes");
    let union_added = added_hit_indices(&intent_projected, &projected_precise_plus_or);
    let union_improved = improved_rank_indices(&intent_projected, &projected_precise_plus_or);
    let oracle_added = added_hit_indices(&intent_projected, &projected_oracle_or);
    let oracle_improved = improved_rank_indices(&intent_projected, &projected_oracle_or);
    let policy_lost = lost_hit_indices(&projected_precise_plus_or, &projected_union_policy_acc);
    let continuation_lost = lost_hit_indices(
        &projected_union_policy_acc,
        &projected_union_continuation_acc,
    );
    println!("  current: precise_else_OR (OR only when precise returns zero rows)");
    println!(
        "  precise+OR union added top-{TOP_K} hits: {} case(s){}",
        union_added.len(),
        fmt_idx(&union_added)
    );
    println!(
        "  precise+OR union improved rank:        {} case(s){}",
        union_improved.len(),
        fmt_idx(&union_improved)
    );
    println!(
        "  projected_oracle added top-{TOP_K} hits: {} case(s){}",
        oracle_added.len(),
        fmt_idx(&oracle_added)
    );
    println!(
        "  projected_oracle improved rank:        {} case(s){}",
        oracle_improved.len(),
        fmt_idx(&oracle_improved)
    );
    println!(
        "  union+policy lost top-{TOP_K} hits:     {} case(s){}",
        policy_lost.len(),
        fmt_idx(&policy_lost)
    );
    println!(
        "  union+cont lost top-{TOP_K} hits:       {} case(s){}",
        continuation_lost.len(),
        fmt_idx(&continuation_lost)
    );
    println!(
        "  contract: projected_oracle uses gold labels and is diagnostic-only, never a deployable strategy"
    );
    println!();

    println!("## Negative controls");
    println!(
        "  projected false hits against corpus gold keys: {}",
        negative_false_hits.len()
    );
    if !negative_false_hits.is_empty() {
        println!("  false hits: {}", fmt_false_hits(&negative_false_hits));
    }
    print_false_hit_bucket_summary("projected", &negative_false_hits);
    println!("  projected parser errors: {}", negative_errors.len());
    if !negative_errors.is_empty() {
        println!("  errors: {}", negative_errors.join(", "));
    }
    println!("  controls:");
    for control in NEGATIVE_CONTROLS {
        println!(
            "    {:<34} {:<20} {}",
            control.id,
            control.bucket.label(),
            control.note
        );
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
        println!("  false hits: {}", fmt_false_hits(&cjk_negative_false_hits));
    }
    print_false_hit_bucket_summary("cjk", &cjk_negative_false_hits);
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
        println!(
            "  false hits: {}",
            fmt_false_hits(&projected_plus_false_hits)
        );
    }
    print_false_hit_bucket_summary("projected+cjk", &projected_plus_false_hits);
    println!("  parser errors: {}", projected_plus_errors.len());
    if !projected_plus_errors.is_empty() {
        println!("  errors: {}", projected_plus_errors.join(", "));
    }
    println!(
        "  contract: eval-only post-candidate filter; no production acceptance or ranking change"
    );
    println!();

    println!("## Projected plus explicit exclusion-intent filter");
    let intent_added = added_hit_indices(&intent_projected, &projected_plus_intent_acc);
    let intent_improved = improved_rank_indices(&intent_projected, &projected_plus_intent_acc);
    println!(
        "  gate: projected+cjk_acc candidates, then reject candidates matching explicit exclusion clauses"
    );
    println!(
        "  added top-{TOP_K} hits over projected: {} case(s){}",
        intent_added.len(),
        fmt_idx(&intent_added)
    );
    println!(
        "  improved first-hit rank over projected: {} case(s){}",
        intent_improved.len(),
        fmt_idx(&intent_improved)
    );
    println!(
        "  accepted false hits: {}",
        projected_intent_false_hits.len()
    );
    if !projected_intent_false_hits.is_empty() {
        println!(
            "  false hits: {}",
            fmt_false_hits(&projected_intent_false_hits)
        );
    }
    print_false_hit_bucket_summary("projected+intent", &projected_intent_false_hits);
    println!("  parser errors: {}", projected_intent_errors.len());
    if !projected_intent_errors.is_empty() {
        println!("  errors: {}", projected_intent_errors.join(", "));
    }
    println!(
        "  contract: eval-only intent/negation filter; no production acceptance or ranking change"
    );
    println!();

    print_exclusion_boundary_diagnostics(&fts, NEGATIVE_CONTROLS, &projected_intent_false_hits);

    println!("## Projected precise+OR union negative-control probe");
    println!("  false hits: {}", projected_union_false_hits.len());
    if !projected_union_false_hits.is_empty() {
        println!(
            "  false hits: {}",
            fmt_false_hits(&projected_union_false_hits)
        );
    }
    print_false_hit_bucket_summary("projected_union", &projected_union_false_hits);
    println!(
        "  projected union+policy false hits: {}",
        projected_union_policy_false_hits.len()
    );
    if !projected_union_policy_false_hits.is_empty() {
        println!(
            "  false hits: {}",
            fmt_false_hits(&projected_union_policy_false_hits)
        );
    }
    print_false_hit_bucket_summary("union+policy", &projected_union_policy_false_hits);
    println!(
        "  projected union+cont false hits: {}",
        projected_union_continuation_false_hits.len()
    );
    if !projected_union_continuation_false_hits.is_empty() {
        println!(
            "  false hits: {}",
            fmt_false_hits(&projected_union_continuation_false_hits)
        );
    }
    print_false_hit_bucket_summary("union+cont", &projected_union_continuation_false_hits);
    println!("  parser errors: {}", projected_union_errors.len());
    if !projected_union_errors.is_empty() {
        println!("  errors: {}", projected_union_errors.join(", "));
    }
    println!(
        "  union+policy parser errors: {}",
        projected_union_policy_errors.len()
    );
    if !projected_union_policy_errors.is_empty() {
        println!("  errors: {}", projected_union_policy_errors.join(", "));
    }
    println!(
        "  union+cont parser errors: {}",
        projected_union_continuation_errors.len()
    );
    if !projected_union_continuation_errors.is_empty() {
        println!(
            "  errors: {}",
            projected_union_continuation_errors.join(", ")
        );
    }
    println!("  contract: candidate-assembly diagnostic only; no production query strategy change");
    println!();

    print_policy_acceptance_diagnostics(NEGATIVE_CONTROLS);
    print_continuation_acceptance_diagnostics(NEGATIVE_CONTROLS);

    println!("## Per-case first-hit rank (- = no hit in top {TOP_K}; ERR = FTS parser error)");
    println!(
        "  {:<3} {:<34} {:<14} {:>8} {:>10} {:>10} {:>10} {:>10} {:>10}  {}",
        "#",
        "id",
        "stratum",
        "content",
        "projected",
        "cjk_probe",
        "plus_acc",
        "intent",
        "exact",
        "note"
    );
    for (i, case) in CORPUS.iter().enumerate() {
        println!(
            "  {:<3} {:<34} {:<14} {:>8} {:>10} {:>10} {:>10} {:>10} {:>10}  {}",
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
                projected_plus_intent_acc.ranks[i],
                projected_plus_intent_acc.errors[i].as_deref()
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
        "  projected+intent misses:{} case(s){}",
        miss_indices(&projected_plus_intent_acc).len(),
        fmt_idx(&miss_indices(&projected_plus_intent_acc))
    );
    println!(
        "  projected_union misses: {} case(s){}",
        miss_indices(&projected_precise_plus_or).len(),
        fmt_idx(&miss_indices(&projected_precise_plus_or))
    );
    println!(
        "  union+policy misses:    {} case(s){}",
        miss_indices(&projected_union_policy_acc).len(),
        fmt_idx(&miss_indices(&projected_union_policy_acc))
    );
    println!(
        "  union+cont misses:      {} case(s){}",
        miss_indices(&projected_union_continuation_acc).len(),
        fmt_idx(&miss_indices(&projected_union_continuation_acc))
    );
    println!(
        "  projected_oracle misses: {} case(s){}",
        miss_indices(&projected_oracle_or).len(),
        fmt_idx(&miss_indices(&projected_oracle_or))
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
        "  projected+intent ctrl:   {} false hit(s), {} parser error(s)",
        projected_intent_false_hits.len(),
        projected_intent_errors.len()
    );
    println!(
        "  projected_union ctrl:    {} false hit(s), {} parser error(s)",
        projected_union_false_hits.len(),
        projected_union_errors.len()
    );
    println!(
        "  union+policy ctrl:       {} false hit(s), {} parser error(s)",
        projected_union_policy_false_hits.len(),
        projected_union_policy_errors.len()
    );
    println!(
        "  union+cont ctrl:         {} false hit(s), {} parser error(s)",
        projected_union_continuation_false_hits.len(),
        projected_union_continuation_errors.len()
    );
    println!(
        "  caveat: hand-curated corpus, N={n}. This is a broader trigger-cohort \
         falsifier, not a production ranking benchmark."
    );

    Ok(())
}

fn run_eval_for(
    db_path: &std::path::Path,
    rows: &[MemoryRow],
    fts: &ScratchFts,
    cases: &[Case],
    negative_controls: &[NegativeControl],
    policy_acceptance_controls: &[PolicyAcceptanceControl],
    corpus_label: &str,
) -> Result<(), Box<dyn std::error::Error>> {
    let mut intent_content = Agg::default();
    let mut intent_projected = Agg::default();
    let mut cjk_shingle_projected = Agg::default();
    let mut projected_plus_cjk_acc = Agg::default();
    let mut projected_plus_intent_acc = Agg::default();
    let mut projected_precise_plus_or = Agg::default();
    let mut projected_union_policy_acc = Agg::default();
    let mut projected_union_continuation_acc = Agg::default();
    let mut projected_oracle_or = Agg::default();
    let mut exact_projected = Agg::default();
    let gold_keys: BTreeSet<&str> = cases
        .iter()
        .flat_map(|case| case.expect.iter().copied())
        .collect();

    for case in cases {
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

        let projected_intent_keys = fts.search_projected_then_intent_accepted(case.query, TOP_K);
        projected_plus_intent_acc.record(
            first_hit_rank(projected_intent_keys.as_deref().unwrap_or(&[]), case.expect),
            projected_intent_keys.err(),
        );

        let projected_union_keys =
            fts.search_precise_plus_or_union(IndexKind::Projected, case.query, TOP_K);
        projected_precise_plus_or.record(
            first_hit_rank(projected_union_keys.as_deref().unwrap_or(&[]), case.expect),
            projected_union_keys.err(),
        );

        let projected_union_policy_keys =
            fts.search_projected_union_then_policy_accepted(case.query, TOP_K);
        projected_union_policy_acc.record(
            first_hit_rank(
                projected_union_policy_keys.as_deref().unwrap_or(&[]),
                case.expect,
            ),
            projected_union_policy_keys.err(),
        );

        let projected_union_continuation_keys =
            fts.search_projected_union_then_continuation_accepted(case.query, TOP_K);
        projected_union_continuation_acc.record(
            first_hit_rank(
                projected_union_continuation_keys.as_deref().unwrap_or(&[]),
                case.expect,
            ),
            projected_union_continuation_keys.err(),
        );

        let projected_oracle_keys =
            fts.search_precise_then_or_if_expected_missing(case.query, case.expect, TOP_K);
        projected_oracle_or.record(
            first_hit_rank(projected_oracle_keys.as_deref().unwrap_or(&[]), case.expect),
            projected_oracle_keys.err(),
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
    let mut projected_intent_false_hits = Vec::new();
    let mut projected_intent_errors = Vec::new();
    let mut projected_union_false_hits = Vec::new();
    let mut projected_union_errors = Vec::new();
    let mut projected_union_policy_false_hits = Vec::new();
    let mut projected_union_policy_errors = Vec::new();
    let mut projected_union_continuation_false_hits = Vec::new();
    let mut projected_union_continuation_errors = Vec::new();
    for control in negative_controls {
        match fts.search(IndexKind::Projected, control.query, TOP_K) {
            Ok(keys) => push_false_hits(&mut negative_false_hits, control, &keys, &gold_keys),
            Err(err) => negative_errors.push(format!("{}:{err}", control.id)),
        }
        match fts.search_projected_cjk_shingles(control.query, TOP_K) {
            Ok(keys) => push_false_hits(&mut cjk_negative_false_hits, control, &keys, &gold_keys),
            Err(err) => cjk_negative_errors.push(format!("{}:{err}", control.id)),
        }
        match fts.search_projected_then_cjk_accepted(control.query, TOP_K) {
            Ok(keys) => push_false_hits(&mut projected_plus_false_hits, control, &keys, &gold_keys),
            Err(err) => projected_plus_errors.push(format!("{}:{err}", control.id)),
        }
        match fts.search_projected_then_intent_accepted(control.query, TOP_K) {
            Ok(keys) => {
                push_false_hits(&mut projected_intent_false_hits, control, &keys, &gold_keys);
            }
            Err(err) => projected_intent_errors.push(format!("{}:{err}", control.id)),
        }
        match fts.search_precise_plus_or_union(IndexKind::Projected, control.query, TOP_K) {
            Ok(keys) => {
                push_false_hits(&mut projected_union_false_hits, control, &keys, &gold_keys)
            }
            Err(err) => projected_union_errors.push(format!("{}:{err}", control.id)),
        }
        match fts.search_projected_union_then_policy_accepted(control.query, TOP_K) {
            Ok(keys) => push_false_hits(
                &mut projected_union_policy_false_hits,
                control,
                &keys,
                &gold_keys,
            ),
            Err(err) => projected_union_policy_errors.push(format!("{}:{err}", control.id)),
        }
        match fts.search_projected_union_then_continuation_accepted(control.query, TOP_K) {
            Ok(keys) => push_false_hits(
                &mut projected_union_continuation_false_hits,
                control,
                &keys,
                &gold_keys,
            ),
            Err(err) => {
                projected_union_continuation_errors.push(format!("{}:{err}", control.id));
            }
        }
    }

    let active_total = rows.len();
    let trigger_rows = rows.iter().filter(|r| !r.triggers.is_empty()).count();
    let projected_rows = rows.iter().filter(|r| r.content != r.projected).count();
    let n = cases.len();

    println!("# Trigger-aware recall eval — {corpus_label}");
    println!("db:              {}", db_path.display());
    println!("active rows:     {active_total}");
    println!("trigger rows:    {trigger_rows}");
    println!("projected rows:  {projected_rows}");
    println!("corpus:          {n} cases ({corpus_label})");
    println!("negative_ctrls:  {} controls", negative_controls.len());
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
    print_row("projected+intent", &projected_plus_intent_acc, n);
    print_row("projected_union", &projected_precise_plus_or, n);
    print_row("union+policy", &projected_union_policy_acc, n);
    print_row("union+cont", &projected_union_continuation_acc, n);
    print_row("projected_oracle", &projected_oracle_or, n);
    print_row("exact_projected", &exact_projected, n);
    println!();

    println!("## Corpus strata");
    for (stratum, count) in stratum_counts_for(cases) {
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

    println!("## Candidate assembly probes");
    let union_added = added_hit_indices(&intent_projected, &projected_precise_plus_or);
    let union_improved = improved_rank_indices(&intent_projected, &projected_precise_plus_or);
    let oracle_added = added_hit_indices(&intent_projected, &projected_oracle_or);
    let oracle_improved = improved_rank_indices(&intent_projected, &projected_oracle_or);
    let policy_lost = lost_hit_indices(&projected_precise_plus_or, &projected_union_policy_acc);
    let continuation_lost = lost_hit_indices(
        &projected_union_policy_acc,
        &projected_union_continuation_acc,
    );
    println!("  current: precise_else_OR (OR only when precise returns zero rows)");
    println!(
        "  precise+OR union added top-{TOP_K} hits: {} case(s){}",
        union_added.len(),
        fmt_idx(&union_added)
    );
    println!(
        "  precise+OR union improved rank:        {} case(s){}",
        union_improved.len(),
        fmt_idx(&union_improved)
    );
    println!(
        "  projected_oracle added top-{TOP_K} hits: {} case(s){}",
        oracle_added.len(),
        fmt_idx(&oracle_added)
    );
    println!(
        "  projected_oracle improved rank:        {} case(s){}",
        oracle_improved.len(),
        fmt_idx(&oracle_improved)
    );
    println!(
        "  union+policy lost top-{TOP_K} hits:     {} case(s){}",
        policy_lost.len(),
        fmt_idx(&policy_lost)
    );
    println!(
        "  union+cont lost top-{TOP_K} hits:       {} case(s){}",
        continuation_lost.len(),
        fmt_idx(&continuation_lost)
    );
    println!(
        "  contract: projected_oracle uses gold labels and is diagnostic-only, never a deployable strategy"
    );
    println!();

    println!("## Negative controls");
    println!(
        "  projected false hits against corpus gold keys: {}",
        negative_false_hits.len()
    );
    if !negative_false_hits.is_empty() {
        println!("  false hits: {}", fmt_false_hits(&negative_false_hits));
    }
    print_false_hit_bucket_summary("projected", &negative_false_hits);
    println!(
        "  cjk false hits against corpus gold keys: {}",
        cjk_negative_false_hits.len()
    );
    if !cjk_negative_false_hits.is_empty() {
        println!("  false hits: {}", fmt_false_hits(&cjk_negative_false_hits));
    }
    print_false_hit_bucket_summary("cjk", &cjk_negative_false_hits);
    println!(
        "  projected+cjk accepted false hits: {}",
        projected_plus_false_hits.len()
    );
    if !projected_plus_false_hits.is_empty() {
        println!(
            "  false hits: {}",
            fmt_false_hits(&projected_plus_false_hits)
        );
    }
    print_false_hit_bucket_summary("projected+cjk", &projected_plus_false_hits);
    println!(
        "  projected+intent accepted false hits: {}",
        projected_intent_false_hits.len()
    );
    if !projected_intent_false_hits.is_empty() {
        println!(
            "  false hits: {}",
            fmt_false_hits(&projected_intent_false_hits)
        );
    }
    print_false_hit_bucket_summary("projected+intent", &projected_intent_false_hits);
    println!(
        "  projected precise+OR union false hits: {}",
        projected_union_false_hits.len()
    );
    if !projected_union_false_hits.is_empty() {
        println!(
            "  false hits: {}",
            fmt_false_hits(&projected_union_false_hits)
        );
    }
    print_false_hit_bucket_summary("projected_union", &projected_union_false_hits);
    println!(
        "  projected union+policy false hits: {}",
        projected_union_policy_false_hits.len()
    );
    if !projected_union_policy_false_hits.is_empty() {
        println!(
            "  false hits: {}",
            fmt_false_hits(&projected_union_policy_false_hits)
        );
    }
    print_false_hit_bucket_summary("union+policy", &projected_union_policy_false_hits);
    println!(
        "  projected union+cont false hits: {}",
        projected_union_continuation_false_hits.len()
    );
    if !projected_union_continuation_false_hits.is_empty() {
        println!(
            "  false hits: {}",
            fmt_false_hits(&projected_union_continuation_false_hits)
        );
    }
    print_false_hit_bucket_summary("union+cont", &projected_union_continuation_false_hits);
    println!("  projected parser errors: {}", negative_errors.len());
    println!("  cjk parser errors: {}", cjk_negative_errors.len());
    println!(
        "  projected+cjk parser errors: {}",
        projected_plus_errors.len()
    );
    println!(
        "  projected+intent parser errors: {}",
        projected_intent_errors.len()
    );
    println!(
        "  projected precise+OR union parser errors: {}",
        projected_union_errors.len()
    );
    println!(
        "  projected union+policy parser errors: {}",
        projected_union_policy_errors.len()
    );
    println!(
        "  projected union+cont parser errors: {}",
        projected_union_continuation_errors.len()
    );
    println!("  controls:");
    for control in negative_controls {
        println!(
            "    {:<28} {:<20} {}",
            control.id,
            control.bucket.label(),
            control.note
        );
    }
    println!();

    print_exclusion_boundary_diagnostics(fts, negative_controls, &projected_intent_false_hits);
    print_policy_acceptance_diagnostics(negative_controls);
    print_continuation_acceptance_diagnostics(negative_controls);
    print_policy_acceptance_control_eval(policy_acceptance_controls);

    println!("## Per-case first-hit rank (- = no hit in top {TOP_K}; ERR = FTS parser error)");
    println!(
        "  {:<3} {:<38} {:<14} {:>8} {:>10} {:>10} {:>10} {:>10} {:>10}  {}",
        "#",
        "id",
        "stratum",
        "content",
        "projected",
        "cjk_probe",
        "plus_acc",
        "intent",
        "exact",
        "note"
    );
    for (i, case) in cases.iter().enumerate() {
        println!(
            "  {:<3} {:<38} {:<14} {:>8} {:>10} {:>10} {:>10} {:>10} {:>10}  {}",
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
                projected_plus_intent_acc.ranks[i],
                projected_plus_intent_acc.errors[i].as_deref()
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
        "  projected+intent misses:{} case(s){}",
        miss_indices(&projected_plus_intent_acc).len(),
        fmt_idx(&miss_indices(&projected_plus_intent_acc))
    );
    println!(
        "  projected_union misses: {} case(s){}",
        miss_indices(&projected_precise_plus_or).len(),
        fmt_idx(&miss_indices(&projected_precise_plus_or))
    );
    println!(
        "  union+policy misses:    {} case(s){}",
        miss_indices(&projected_union_policy_acc).len(),
        fmt_idx(&miss_indices(&projected_union_policy_acc))
    );
    println!(
        "  union+cont misses:      {} case(s){}",
        miss_indices(&projected_union_continuation_acc).len(),
        fmt_idx(&miss_indices(&projected_union_continuation_acc))
    );
    println!(
        "  projected_oracle misses: {} case(s){}",
        miss_indices(&projected_oracle_or).len(),
        fmt_idx(&miss_indices(&projected_oracle_or))
    );
    println!(
        "  exact_projected errors:  {} case(s){}",
        error_indices(&exact_projected).len(),
        fmt_idx(&error_indices(&exact_projected))
    );
    println!(
        "  caveat: hand-curated corpus, N={n}. This is a read-only trigger-cohort falsifier, not a production ranking benchmark."
    );

    Ok(())
}

fn run_runtime_audit_for(
    db_path: &std::path::Path,
    rows: &[MemoryRow],
    fts: &ScratchFts,
    cases: &[Case],
    negative_controls: &[NegativeControl],
    corpus_label: &str,
) -> Result<(), Box<dyn std::error::Error>> {
    let mut baseline_acc = Agg::default();
    let mut projected_union_acc = Agg::default();
    let mut runtime_final_acc = Agg::default();
    let mut recovered_indices = Vec::new();
    let mut lost_indices = Vec::new();
    let mut sample_case_audits = Vec::new();
    let gold_keys: BTreeSet<&str> = cases
        .iter()
        .flat_map(|case| case.expect.iter().copied())
        .collect();

    for (idx, case) in cases.iter().enumerate() {
        let audit = runtime_shaped_audit(fts, case.query, TOP_K)?;
        let projected_union =
            fts.search_precise_plus_or_union(IndexKind::Projected, case.query, TOP_K)?;
        let baseline_rank = first_hit_rank(&audit.baseline_keys, case.expect);
        let union_rank = first_hit_rank(&projected_union, case.expect);
        let final_rank = first_hit_rank(&audit.final_keys, case.expect);
        baseline_acc.record(baseline_rank, None);
        projected_union_acc.record(union_rank, None);
        runtime_final_acc.record(final_rank, None);

        if baseline_rank.is_none() && final_rank.is_some() {
            recovered_indices.push(idx + 1);
            sample_case_audits.push((idx + 1, case.id, audit.clone()));
        }
        if baseline_rank.is_some() && final_rank.is_none() {
            lost_indices.push(idx + 1);
        }
    }

    let mut baseline_false_hits = Vec::new();
    let mut supplemental_false_hits = Vec::new();
    let mut final_false_hits = Vec::new();
    let mut rejected_control_audits = Vec::new();
    for control in negative_controls {
        let audit = runtime_shaped_audit(fts, control.query, TOP_K)?;
        push_false_hits(
            &mut baseline_false_hits,
            control,
            &audit.baseline_keys,
            &gold_keys,
        );
        push_false_hits(
            &mut supplemental_false_hits,
            control,
            &audit.supplemental_after_gate,
            &gold_keys,
        );
        push_false_hits(
            &mut final_false_hits,
            control,
            &audit.final_keys,
            &gold_keys,
        );
        if audit.policy_reject_reason.is_some() || audit.continuation_reject_reason.is_some() {
            rejected_control_audits.push((control.id, audit));
        }
    }

    println!("# Trigger query-intent runtime-shaped audit - {corpus_label}");
    println!("db:              {}", db_path.display());
    println!("active rows:     {}", rows.len());
    println!(
        "trigger rows:    {}",
        rows.iter().filter(|r| !r.triggers.is_empty()).count()
    );
    println!(
        "projected rows:  {}",
        rows.iter().filter(|r| r.content != r.projected).count()
    );
    println!("corpus:          {} cases", cases.len());
    println!("negative_ctrls:  {} controls", negative_controls.len());
    println!("top_k:           {TOP_K}");
    println!("schema:          {TRIGGER_RUNTIME_AUDIT_SCHEMA}");
    println!("regression:      {TRIGGER_RUNTIME_REGRESSION_ANCHOR}");
    println!(
        "read_only:       SELECT + in-memory FTS only; no memory_get, memory_search, writes, or reindex"
    );
    println!(
        "contract:        models explicit opt-in supplemental candidates; default memory_search unchanged"
    );
    println!();

    println!("## Runtime-shaped recall");
    println!("  mode                   R@1     R@5    R@10     MRR");
    print_row("baseline_fts", &baseline_acc, cases.len());
    print_row("projected_union", &projected_union_acc, cases.len());
    print_row("runtime_final", &runtime_final_acc, cases.len());
    println!(
        "  supplemental recovered baseline misses: {} case(s){}",
        recovered_indices.len(),
        fmt_idx(&recovered_indices)
    );
    println!(
        "  runtime final lost baseline hits:       {} case(s){}",
        lost_indices.len(),
        fmt_idx(&lost_indices)
    );
    println!();

    println!("## Negative controls");
    println!(
        "  baseline false hits retained:       {}",
        baseline_false_hits.len()
    );
    if !baseline_false_hits.is_empty() {
        println!(
            "  baseline false hits: {}",
            fmt_false_hits(&baseline_false_hits)
        );
    }
    println!(
        "  supplemental false hits after gate: {}",
        supplemental_false_hits.len()
    );
    if !supplemental_false_hits.is_empty() {
        println!(
            "  supplemental false hits: {}",
            fmt_false_hits(&supplemental_false_hits)
        );
    }
    println!(
        "  runtime final false hits:           {}",
        final_false_hits.len()
    );
    if !final_false_hits.is_empty() {
        println!("  final false hits: {}", fmt_false_hits(&final_false_hits));
    }
    println!(
        "  caveat: runtime-shaped gate only drops supplemental projected candidates; baseline FTS results are intentionally preserved"
    );
    println!();

    println!("## Recovered case audit samples");
    if sample_case_audits.is_empty() {
        println!("  no baseline misses recovered by supplemental candidates");
    }
    for (idx, case_id, audit) in sample_case_audits {
        println!("case #{idx} {case_id}");
        println!("{}", serde_json::to_string_pretty(&audit.to_json())?);
    }
    println!();

    println!("## Rejected control audit samples");
    if rejected_control_audits.is_empty() {
        println!("  no controls rejected by query-intent gates");
    }
    for (control_id, audit) in rejected_control_audits {
        println!("control {control_id}");
        println!("{}", serde_json::to_string_pretty(&audit.to_json())?);
    }
    println!();

    println!("## Decision");
    println!(
        "  eval_only: true; production memory_search, ranking, schema, indexing, graph, semantic retrieval, MCP surfaces, and memory rows unchanged"
    );

    Ok(())
}

fn run_baseline_acceptance_audit_for(
    db_path: &std::path::Path,
    rows: &[MemoryRow],
    fts: &ScratchFts,
    cases: &[Case],
    negative_controls: &[NegativeControl],
    corpus_label: &str,
) -> Result<(), Box<dyn std::error::Error>> {
    let mut baseline_acc = Agg::default();
    let mut shadow_accept_acc = Agg::default();
    let mut lost_true_hit_indices = Vec::new();
    let mut rejected_positive_audits = Vec::new();
    let gold_keys: BTreeSet<&str> = cases
        .iter()
        .flat_map(|case| case.expect.iter().copied())
        .collect();

    for (idx, case) in cases.iter().enumerate() {
        let audit = baseline_acceptance_audit(fts, case.query, TOP_K)?;
        let baseline_rank = first_hit_rank(&audit.baseline_keys_before_gate, case.expect);
        let shadow_rank = first_hit_rank(&audit.baseline_keys_after_shadow_gate, case.expect);
        baseline_acc.record(baseline_rank, None);
        shadow_accept_acc.record(shadow_rank, None);

        if baseline_rank.is_some() && shadow_rank.is_none() {
            lost_true_hit_indices.push(idx + 1);
        }
        if audit.query_intent_reject_reason.is_some() {
            rejected_positive_audits.push((idx + 1, case.id, audit));
        }
    }

    let mut baseline_false_hits = Vec::new();
    let mut shadow_false_hits = Vec::new();
    let mut rejected_control_audits = Vec::new();
    let mut held_controls_by_reason = BTreeMap::<&'static str, usize>::new();
    for control in negative_controls {
        let audit = baseline_acceptance_audit(fts, control.query, TOP_K)?;
        push_false_hits(
            &mut baseline_false_hits,
            control,
            &audit.baseline_keys_before_gate,
            &gold_keys,
        );
        push_false_hits(
            &mut shadow_false_hits,
            control,
            &audit.baseline_keys_after_shadow_gate,
            &gold_keys,
        );
        if let Some(reason) = audit.query_intent_reject_reason {
            *held_controls_by_reason.entry(reason).or_insert(0) += 1;
            rejected_control_audits.push((control.id, audit));
        }
    }

    let removed_false_hits = removed_false_hits(&baseline_false_hits, &shadow_false_hits);

    println!("# Trigger baseline acceptance shadow audit - {corpus_label}");
    println!("db:              {}", db_path.display());
    println!("active rows:     {}", rows.len());
    println!(
        "trigger rows:    {}",
        rows.iter().filter(|r| !r.triggers.is_empty()).count()
    );
    println!(
        "projected rows:  {}",
        rows.iter().filter(|r| r.content != r.projected).count()
    );
    println!("corpus:          {} cases", cases.len());
    println!("negative_ctrls:  {} controls", negative_controls.len());
    println!("top_k:           {TOP_K}");
    println!("schema:          {TRIGGER_BASELINE_ACCEPTANCE_SCHEMA}");
    println!("regression:      {TRIGGER_BASELINE_ACCEPTANCE_REGRESSION_ANCHOR}");
    println!(
        "read_only:       SELECT + in-memory FTS only; no memory_get, memory_search, writes, or reindex"
    );
    println!(
        "contract:        eval-only shadow hold for baseline FTS query intent; default memory_search unchanged"
    );
    println!();

    println!("## Baseline acceptance recall");
    println!("  mode                   R@1     R@5    R@10     MRR");
    print_row("baseline_fts", &baseline_acc, cases.len());
    print_row("baseline_shadow", &shadow_accept_acc, cases.len());
    println!(
        "  true hits lost by shadow gate: {} case(s){}",
        lost_true_hit_indices.len(),
        fmt_idx(&lost_true_hit_indices)
    );
    println!(
        "  positive cases held:          {} case(s)",
        rejected_positive_audits.len()
    );
    println!();

    println!("## Negative controls");
    println!(
        "  baseline false hits before shadow gate: {}",
        baseline_false_hits.len()
    );
    if !baseline_false_hits.is_empty() {
        println!(
            "  baseline false hits: {}",
            fmt_false_hits(&baseline_false_hits)
        );
    }
    println!(
        "  baseline false hits after shadow gate:  {}",
        shadow_false_hits.len()
    );
    if !shadow_false_hits.is_empty() {
        println!(
            "  shadow false hits: {}",
            fmt_false_hits(&shadow_false_hits)
        );
    }
    println!(
        "  false hits removed by shadow gate:      {}",
        removed_false_hits.len()
    );
    if !removed_false_hits.is_empty() {
        println!(
            "  removed false hits: {}",
            fmt_false_hits(&removed_false_hits)
        );
    }
    print_false_hit_bucket_summary("baseline", &baseline_false_hits);
    print_false_hit_bucket_summary("shadow", &shadow_false_hits);
    print_false_hit_bucket_summary("removed", &removed_false_hits);
    if held_controls_by_reason.is_empty() {
        println!("  held controls by reason: none");
    } else {
        println!(
            "  held controls by reason: {}",
            held_reason_summary(&held_controls_by_reason)
        );
    }
    println!();

    println!("## Rejected positive audit samples");
    if rejected_positive_audits.is_empty() {
        println!("  no positive cases held by the baseline shadow gate");
    }
    for (idx, case_id, audit) in rejected_positive_audits {
        println!("case #{idx} {case_id}");
        println!("{}", serde_json::to_string_pretty(&audit.to_json())?);
    }
    println!();

    println!("## Rejected control audit samples");
    if rejected_control_audits.is_empty() {
        println!("  no controls held by query-intent gate");
    }
    for (control_id, audit) in rejected_control_audits {
        println!("control {control_id}");
        println!("{}", serde_json::to_string_pretty(&audit.to_json())?);
    }
    println!();

    println!("## Decision");
    println!(
        "  eval_only: true; baseline shadow hold is measurement-only. Production memory_search, ranking, schema, indexing, graph, semantic retrieval, MCP surfaces, and memory rows are unchanged."
    );

    Ok(())
}

fn report_stale_aio2_baseline_acceptance_audit(
    db_path: &std::path::Path,
    rows: &[MemoryRow],
    error: &str,
) -> Result<(), Box<dyn std::error::Error>> {
    let (status, hard_gate_authority, coverage) = aio2_baseline_acceptance_telemetry_status(rows);

    println!("# Trigger baseline acceptance shadow audit - aio2 live telemetry");
    println!("db:                       {}", db_path.display());
    println!("status:                   {status}");
    println!("hard_gate_authority:      {hard_gate_authority}");
    println!("active rows:              {}", coverage.active_total);
    println!("trigger rows:             {}", coverage.trigger_rows);
    println!("projected rows:           {}", coverage.projected_rows);
    println!("corpus cases:             {}", AIO2_NATIVE_CORPUS.len());
    println!("expected key refs:        {}", coverage.expected_refs);
    println!("present expected refs:    {}", coverage.present_expected);
    println!(
        "missing expected refs:    {}",
        coverage.missing_expected.len()
    );
    println!(
        "expected without trigger: {}",
        coverage.expected_without_trigger.len()
    );
    println!("schema:                   {TRIGGER_BASELINE_ACCEPTANCE_SCHEMA}");
    println!("regression:               {TRIGGER_BASELINE_ACCEPTANCE_REGRESSION_ANCHOR}");
    println!(
        "read_only:                SELECT + corpus coverage only; no memory_get, memory_search, writes, or reindex"
    );
    println!("error:                    {error}");
    println!();

    if !coverage.missing_expected.is_empty() {
        println!("## Missing Expected Keys");
        for (case_id, key) in &coverage.missing_expected {
            println!("  {case_id}: {key}");
        }
        println!();
    }
    if !coverage.expected_without_trigger.is_empty() {
        println!("## Expected Keys Without Trigger Tags");
        for (case_id, key) in &coverage.expected_without_trigger {
            println!("  {case_id}: {key}");
        }
        println!();
    }

    println!("## Decision");
    println!(
        "  eval_only: true; aio2 baseline acceptance audit is stale telemetry, not a Stage-2 hard gate or production approval."
    );
    println!(
        "  required_gate: use --portable-stage2-fixture for deterministic code-regression proof, or repair aio2 live corpus with provenance before using live telemetry for policy claims."
    );

    Ok(())
}

fn aio2_baseline_acceptance_telemetry_status(
    rows: &[MemoryRow],
) -> (&'static str, bool, CorpusCoverage) {
    let coverage = corpus_coverage_for(rows, AIO2_NATIVE_CORPUS);
    if coverage.ready() {
        ("ready_live_telemetry_not_gate", false, coverage)
    } else {
        ("stale_corpus_not_gate", false, coverage)
    }
}

fn runtime_shaped_audit(
    fts: &ScratchFts,
    query: &str,
    limit: usize,
) -> Result<RuntimeShapedAudit, String> {
    let baseline_keys = fts.search(IndexKind::Projected, query, limit)?;
    let projected_union_keys =
        fts.search_precise_plus_or_union(IndexKind::Projected, query, limit)?;
    let baseline_set = baseline_keys
        .iter()
        .map(String::as_str)
        .collect::<BTreeSet<_>>();
    let supplemental_before_gate = projected_union_keys
        .into_iter()
        .filter(|key| !baseline_set.contains(key.as_str()))
        .collect::<Vec<_>>();
    let policy_reject_reason = policy_acceptance_reject_reason(query);
    let continuation_reject_reason = if policy_reject_reason.is_some() {
        None
    } else {
        continuation_domain_reject_reason(query)
    };
    let gate_rejected = policy_reject_reason.is_some() || continuation_reject_reason.is_some();
    let supplemental_after_gate = if gate_rejected {
        Vec::new()
    } else {
        supplemental_before_gate.clone()
    };
    let final_keys = dedupe_limit(
        baseline_keys
            .clone()
            .into_iter()
            .chain(supplemental_after_gate.clone()),
        limit,
    );
    let fallback_behavior = if gate_rejected {
        "baseline_fts_only"
    } else if supplemental_after_gate.is_empty() {
        "baseline_fts_only_no_supplemental"
    } else {
        "baseline_plus_supplemental_projected"
    };

    Ok(RuntimeShapedAudit {
        query_hash: query_hash(query),
        policy_reject_reason,
        continuation_reject_reason,
        baseline_keys,
        supplemental_before_gate,
        supplemental_after_gate,
        final_keys,
        fallback_behavior,
    })
}

fn baseline_acceptance_audit(
    fts: &ScratchFts,
    query: &str,
    limit: usize,
) -> Result<BaselineAcceptanceAudit, String> {
    let baseline_keys = fts.search(IndexKind::Projected, query, limit)?;
    let query_intent_reject_reason = baseline_acceptance_reject_reason(query);
    let baseline_keys_after_shadow_gate =
        shadow_visible_baseline_keys(&baseline_keys, query_intent_reject_reason);

    Ok(BaselineAcceptanceAudit {
        query_hash: query_hash(query),
        query_intent_reject_reason,
        baseline_keys_before_gate: baseline_keys,
        baseline_keys_after_shadow_gate,
    })
}

fn baseline_acceptance_reject_reason(query: &str) -> Option<&'static str> {
    continuation_acceptance_reject_reason(query)
}

fn shadow_visible_baseline_keys(
    baseline_keys: &[String],
    reject_reason: Option<&'static str>,
) -> Vec<String> {
    if reject_reason.is_some() {
        Vec::new()
    } else {
        baseline_keys.to_vec()
    }
}

fn load_active_rows(db_path: &std::path::Path) -> SqlResult<Vec<MemoryRow>> {
    let db = RusqliteConnection::open_with_flags(db_path, OpenFlags::SQLITE_OPEN_READ_ONLY)?;
    let mut stmt = db.prepare(
        "SELECT key, kind, scope, content, COALESCE(fts_content, content), tags
         FROM memories
         WHERE status = 'active'
         ORDER BY rowid",
    )?;
    let rows = stmt
        .query_map([], |row| {
            let key: String = row.get(0)?;
            let kind: String = row.get(1)?;
            let scope: Option<String> = row.get(2)?;
            let content: String = row.get(3)?;
            let projected: String = row.get(4)?;
            let tags_s: String = row.get(5)?;
            let tags = parse_str_array(&tags_s);
            let triggers = tags
                .iter()
                .filter_map(|t| t.strip_prefix(TRIGGER_PREFIX).map(str::trim))
                .filter(|t| !t.is_empty())
                .map(ToString::to_string)
                .collect();
            Ok(MemoryRow {
                key,
                kind,
                scope,
                content,
                projected,
                triggers,
            })
        })?
        .collect::<SqlResult<Vec<_>>>()?;
    Ok(rows)
}

fn portable_stage2_fixture_rows() -> Vec<MemoryRow> {
    PORTABLE_STAGE2_CORPUS
        .iter()
        .map(|case| {
            let expected = case.expect[0];
            let projected = format!(
                "{}\n{}\n{}\n{}",
                case.query, case.trigger, case.note, expected
            );
            MemoryRow {
                key: expected.to_string(),
                kind: "fixture".to_string(),
                scope: Some("project:/portable-stage2-fixture".to_string()),
                content: format!("Portable Stage-2 fixture row for {}.", case.id),
                projected,
                triggers: vec![case.trigger.to_string()],
            }
        })
        .collect()
}

fn list_trigger_rows(
    db_path: &std::path::Path,
    rows: &[MemoryRow],
) -> Result<(), Box<dyn std::error::Error>> {
    let trigger_rows = rows
        .iter()
        .filter(|row| !row.triggers.is_empty())
        .collect::<Vec<_>>();
    println!("# Trigger-aware recall active trigger rows");
    println!("db:              {}", db_path.display());
    println!("active rows:     {}", rows.len());
    println!("trigger rows:    {}", trigger_rows.len());
    println!(
        "projected rows:  {}",
        rows.iter().filter(|r| r.content != r.projected).count()
    );
    println!("read_only:       SELECT only; no memory_get, memory_search, writes, or reindex");
    println!();

    for (idx, row) in trigger_rows.iter().enumerate() {
        println!("[{}] key={}", idx + 1, row.key);
        println!("    kind={}", row.kind);
        println!("    scope={}", row.scope.as_deref().unwrap_or(""));
        println!("    content_chars={}", row.content.chars().count());
        println!("    projected_chars={}", row.projected.chars().count());
        for trigger in &row.triggers {
            println!("    trigger={trigger}");
        }
        let preview = row
            .content
            .split_whitespace()
            .take(28)
            .collect::<Vec<_>>()
            .join(" ");
        println!("    preview={preview}");
    }

    Ok(())
}

fn check_corpus(
    db_path: &std::path::Path,
    rows: &[MemoryRow],
) -> Result<(), Box<dyn std::error::Error>> {
    check_corpus_for(db_path, rows, CORPUS)
}

fn check_corpus_for(
    db_path: &std::path::Path,
    rows: &[MemoryRow],
    cases: &[Case],
) -> Result<(), Box<dyn std::error::Error>> {
    let coverage = corpus_coverage_for(rows, cases);
    println!("# Trigger-aware recall corpus check");
    println!("db:                       {}", db_path.display());
    println!("active rows:              {}", coverage.active_total);
    println!("trigger rows:             {}", coverage.trigger_rows);
    println!("projected rows:           {}", coverage.projected_rows);
    println!("corpus cases:             {}", cases.len());
    println!("expected key refs:        {}", coverage.expected_refs);
    println!("present expected refs:    {}", coverage.present_expected);
    println!(
        "missing expected refs:    {}",
        coverage.missing_expected.len()
    );
    println!(
        "expected without trigger: {}",
        coverage.expected_without_trigger.len()
    );
    println!("ready:                    {}", coverage.ready());

    if !coverage.missing_expected.is_empty() {
        println!();
        println!("## Missing Expected Keys");
        for (case_id, key) in &coverage.missing_expected {
            println!("  {case_id}: {key}");
        }
    }
    if !coverage.expected_without_trigger.is_empty() {
        println!();
        println!("## Expected Keys Without Trigger Tags");
        for (case_id, key) in &coverage.expected_without_trigger {
            println!("  {case_id}: {key}");
        }
    }

    if coverage.ready() {
        Ok(())
    } else {
        std::io::stdout().flush()?;
        Err("trigger recall corpus is not runnable against this DB".into())
    }
}

#[cfg(test)]
fn corpus_coverage(rows: &[MemoryRow]) -> CorpusCoverage {
    corpus_coverage_for(rows, CORPUS)
}

fn corpus_coverage_for(rows: &[MemoryRow], cases: &[Case]) -> CorpusCoverage {
    let by_key: HashMap<&str, &MemoryRow> = rows.iter().map(|r| (r.key.as_str(), r)).collect();
    let mut expected_refs = 0_usize;
    let mut present_expected = 0_usize;
    let mut missing_expected = Vec::new();
    let mut expected_without_trigger = Vec::new();

    for case in cases {
        for expected in case.expect {
            expected_refs += 1;
            match by_key.get(expected) {
                Some(row) if row.triggers.is_empty() => {
                    expected_without_trigger.push((case.id.to_string(), (*expected).to_string()));
                }
                Some(_) => {
                    present_expected += 1;
                }
                None => {
                    missing_expected.push((case.id.to_string(), (*expected).to_string()));
                }
            }
        }
    }

    CorpusCoverage {
        active_total: rows.len(),
        trigger_rows: rows.iter().filter(|r| !r.triggers.is_empty()).count(),
        projected_rows: rows.iter().filter(|r| r.content != r.projected).count(),
        expected_refs,
        present_expected,
        missing_expected,
        expected_without_trigger,
    }
}

fn verify_corpus(rows: &[MemoryRow]) -> Result<(), Box<dyn std::error::Error>> {
    verify_corpus_for(rows, CORPUS, NEGATIVE_CONTROLS)
}

fn verify_corpus_for(
    rows: &[MemoryRow],
    cases: &[Case],
    negative_controls: &[NegativeControl],
) -> Result<(), Box<dyn std::error::Error>> {
    let by_key: HashMap<&str, &MemoryRow> = rows.iter().map(|r| (r.key.as_str(), r)).collect();
    let mut seen_ids = BTreeSet::new();
    let mut seen_queries = BTreeSet::new();

    for case in cases {
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
    for control in negative_controls {
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
    content_by_key: HashMap<String, String>,
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

        let mut content_by_key = HashMap::new();
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
                content_by_key.insert(row.key.clone(), row.content.clone());
                projected_by_key.insert(row.key.clone(), row.projected.clone());
            }
        }

        Ok(Self {
            db,
            content_by_key,
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

    fn search_projected_then_intent_accepted(
        &self,
        query: &str,
        limit: usize,
    ) -> Result<Vec<String>, String> {
        let clauses = explicit_exclusion_clauses(query);
        let candidates = self.search_projected_then_cjk_accepted(query, limit)?;
        if clauses.is_empty() {
            return Ok(candidates);
        }

        filter_explicit_exclusion_intent(&self.projected_by_key, &clauses, candidates)
    }

    fn search_projected_union_then_policy_accepted(
        &self,
        query: &str,
        limit: usize,
    ) -> Result<Vec<String>, String> {
        if policy_acceptance_reject_reason(query).is_some() {
            return Ok(Vec::new());
        }
        self.search_precise_plus_or_union(IndexKind::Projected, query, limit)
    }

    fn search_projected_union_then_continuation_accepted(
        &self,
        query: &str,
        limit: usize,
    ) -> Result<Vec<String>, String> {
        if continuation_acceptance_reject_reason(query).is_some() {
            return Ok(Vec::new());
        }
        self.search_precise_plus_or_union(IndexKind::Projected, query, limit)
    }

    fn search_precise_plus_or_union(
        &self,
        kind: IndexKind,
        query: &str,
        limit: usize,
    ) -> Result<Vec<String>, String> {
        let precise = sanitise_fts_query(query);
        let any = sanitise_fts_query_any(query);
        let precise_rows = self.search_once(kind, &precise, limit)?;
        if any == precise {
            return Ok(precise_rows);
        }
        let any_rows = self.search_once(kind, &any, limit)?;
        Ok(dedupe_limit(
            precise_rows.into_iter().chain(any_rows),
            limit,
        ))
    }

    fn search_precise_then_or_if_expected_missing(
        &self,
        query: &str,
        expect: &[&str],
        limit: usize,
    ) -> Result<Vec<String>, String> {
        let precise = sanitise_fts_query(query);
        let any = sanitise_fts_query_any(query);
        let precise_rows = self.search_once(IndexKind::Projected, &precise, limit)?;
        if first_hit_rank(&precise_rows, expect).is_some() || any == precise {
            return Ok(precise_rows);
        }
        let any_rows = self.search_once(IndexKind::Projected, &any, limit)?;
        Ok(dedupe_limit(
            precise_rows.into_iter().chain(any_rows),
            limit,
        ))
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
    debug_case_for(fts, CORPUS, idx1, "Mac trigger-aware")
}

fn debug_case_for(
    fts: &ScratchFts,
    cases: &[Case],
    idx1: usize,
    label: &str,
) -> Result<(), Box<dyn std::error::Error>> {
    let case = cases
        .get(idx1.saturating_sub(1))
        .ok_or("case index out of range")?;
    println!("# debug {label} trigger-aware case #{idx1}");
    println!("id:      {}", case.id);
    println!("stratum: {}", case.stratum);
    println!("query:   {}", case.query);
    println!("trigger: {}", case.trigger);
    println!("expect:  {:?}\n", case.expect);

    println!("## query diagnostics");
    dump_query_diagnostics("intent", case.query);
    dump_query_diagnostics("trigger", case.trigger);
    println!();

    println!("## precise/OR search matrix");
    println!(
        "contract: search() uses the precise expression when it returns any rows; OR is only an empty-result fallback."
    );
    let intent_precise = sanitise_fts_query(case.query);
    let intent_any = sanitise_fts_query_any(case.query);
    let trigger_precise = sanitise_fts_query(case.trigger);
    let trigger_any = sanitise_fts_query_any(case.trigger);
    dump_search_variant(
        fts,
        "content intent precise",
        IndexKind::Content,
        &intent_precise,
        case.expect,
    );
    dump_search_variant(
        fts,
        "content intent OR",
        IndexKind::Content,
        &intent_any,
        case.expect,
    );
    dump_search_variant(
        fts,
        "projected intent precise",
        IndexKind::Projected,
        &intent_precise,
        case.expect,
    );
    dump_search_variant(
        fts,
        "projected intent OR",
        IndexKind::Projected,
        &intent_any,
        case.expect,
    );
    dump_search_variant(
        fts,
        "projected trigger precise",
        IndexKind::Projected,
        &trigger_precise,
        case.expect,
    );
    dump_search_variant(
        fts,
        "projected trigger OR",
        IndexKind::Projected,
        &trigger_any,
        case.expect,
    );
    println!();

    println!("## expected row query-term overlap");
    for expected in case.expect {
        println!("### {expected}");
        match fts.content_by_key.get(*expected) {
            Some(content) => dump_body_term_overlap("content", case.query, content),
            None => println!("  content: missing from scratch map"),
        }
        match fts.projected_by_key.get(*expected) {
            Some(projected) => dump_body_term_overlap("projected", case.query, projected),
            None => println!("  projected: missing from scratch map"),
        }
    }
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

fn dump_search_variant(
    fts: &ScratchFts,
    label: &str,
    kind: IndexKind,
    match_expr: &str,
    expect: &[&str],
) {
    println!("### {label}");
    println!("  match: {match_expr}");
    match fts.search_once(kind, match_expr, TOP_K) {
        Ok(keys) => {
            println!(
                "  first_hit_rank: {}",
                rank_cell(first_hit_rank(&keys, expect), None)
            );
            dump_keys(expect, &keys);
        }
        Err(err) => println!("  ERROR: {err}"),
    }
}

fn dump_body_term_overlap(label: &str, query: &str, body: &str) {
    let query_terms = match fts_terms(query) {
        Ok(terms) => terms,
        Err(err) => {
            println!("  {label}: query term probe ERROR: {err}");
            return;
        }
    };
    let body_terms = match fts_terms(body) {
        Ok(terms) => terms.into_iter().collect::<BTreeSet<_>>(),
        Err(err) => {
            println!("  {label}: body term probe ERROR: {err}");
            return;
        }
    };
    let present = query_terms
        .iter()
        .filter(|term| body_terms.contains(*term))
        .cloned()
        .collect::<Vec<_>>();
    let missing = query_terms
        .iter()
        .filter(|term| !body_terms.contains(*term))
        .cloned()
        .collect::<Vec<_>>();
    println!(
        "  {label}: chars={}, query_terms_present={}/{}, missing=[{}]",
        body.chars().count(),
        present.len(),
        query_terms.len(),
        missing.join(", ")
    );
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

fn explicit_exclusion_clauses(query: &str) -> Vec<String> {
    let markers = ["不要"];
    let mut clauses = Vec::new();
    for marker in markers {
        collect_exclusion_clauses(query, marker, &mut clauses);
    }

    let lower = query.to_lowercase();
    for marker in ["rather than", "instead of", "without", "not "] {
        let mut start = 0;
        while let Some(rel_idx) = lower[start..].find(marker) {
            let marker_idx = start + rel_idx;
            let clause_start = marker_idx + marker.len();
            if let Some(clause) = exclusion_tail(&query[clause_start..]) {
                clauses.push(clause);
            }
            start = clause_start;
        }
    }

    clauses
}

fn collect_exclusion_clauses(query: &str, marker: &str, clauses: &mut Vec<String>) {
    let mut start = 0;
    while let Some(rel_idx) = query[start..].find(marker) {
        let marker_idx = start + rel_idx;
        let clause_start = marker_idx + marker.len();
        if let Some(clause) = exclusion_tail(&query[clause_start..]) {
            clauses.push(clause);
        }
        start = clause_start;
    }
}

fn exclusion_tail(suffix: &str) -> Option<String> {
    let trimmed = suffix.trim_start_matches(|ch: char| {
        ch.is_whitespace() || matches!(ch, ':' | '：' | '-' | '，' | ',')
    });
    let clause = trimmed
        .split(|ch: char| {
            matches!(
                ch,
                '\n' | '\r' | '。' | '！' | '？' | '；' | ';' | '.' | '!' | '?'
            )
        })
        .next()
        .unwrap_or("")
        .trim()
        .trim_matches(|ch: char| matches!(ch, '，' | ',' | '、'));

    if clause.is_empty() {
        None
    } else {
        Some(clause.to_string())
    }
}

fn filter_explicit_exclusion_intent(
    projected_by_key: &HashMap<String, String>,
    clauses: &[String],
    candidates: Vec<String>,
) -> Result<Vec<String>, String> {
    let mut accepted = Vec::new();
    for key in candidates {
        let projected = projected_by_key
            .get(&key)
            .ok_or_else(|| format!("candidate key missing from projected map: {key}"))?;
        if !candidate_matches_exclusion(clauses, projected) {
            accepted.push(key);
        }
    }
    Ok(accepted)
}

fn policy_acceptance_reject_reason(query: &str) -> Option<&'static str> {
    let lower = query.to_lowercase();
    let has_bypass = contains_any(&lower, &["bypass", "绕过"]);
    let has_direct_write = contains_any(
        &lower,
        &[
            "directly write",
            "write graph edges",
            "write memory_edges",
            "直接写",
        ],
    );
    let has_graph_write_surface = contains_any(
        &lower,
        &[
            "graph edges",
            "memory_edges",
            "related keys",
            "materialize",
            "materialization",
            "dry run",
            "dry_run",
            "图谱",
        ],
    );

    if (has_bypass || has_direct_write) && has_graph_write_surface {
        return Some("write_bypass_intent");
    }

    if contains_any(
        &lower,
        &["write a poem", "poem", "poetry", "写诗", "诗歌", "写一首诗"],
    ) {
        return Some("creative_non_continuation_intent");
    }

    None
}

fn continuation_acceptance_reject_reason(query: &str) -> Option<&'static str> {
    if let Some(reason) = policy_acceptance_reject_reason(query) {
        return Some(reason);
    }

    continuation_domain_reject_reason(query)
}

fn continuation_domain_reject_reason(query: &str) -> Option<&'static str> {
    let lower = query.to_lowercase();
    let has_dashboard_or_state = contains_any(&lower, &["dashboard", "state"]);
    if !has_dashboard_or_state {
        return None;
    }

    if contains_any(
        &lower,
        &[
            "exercise", "recovery", "pain", "tracker", "workout", "health", "fitness",
        ],
    ) {
        return Some("health_dashboard_intent");
    }

    if contains_any(
        &lower,
        &[
            "card spacing",
            "color palette",
            "button hover",
            "responsive layout",
            "visual design",
            "visual-design",
            "styling",
            "layout",
            "frontend",
        ],
    ) {
        return Some("frontend_dashboard_intent");
    }

    None
}

fn query_hash(query: &str) -> String {
    let digest = Sha256::digest(query.as_bytes());
    format!("sha256:{digest:x}")
}

fn contains_any(haystack: &str, needles: &[&str]) -> bool {
    needles.iter().any(|needle| haystack.contains(needle))
}

fn false_hit_labels(hits: &[FalseHit]) -> String {
    hits.iter()
        .map(FalseHit::label)
        .collect::<Vec<_>>()
        .join(", ")
}

fn print_policy_acceptance_diagnostics(controls: &[NegativeControl]) {
    println!("## Eval-only acceptance/policy gate diagnostics");
    let mut rejected = 0;
    for control in controls {
        if let Some(reason) = policy_acceptance_reject_reason(control.query) {
            rejected += 1;
            println!(
                "  reject {:<28} {:<34} {}",
                control.id, reason, control.note
            );
        }
    }
    if rejected == 0 {
        println!("  no controls rejected by policy gate");
    }
    println!(
        "  contract: query-intent gate only; rejects unsafe/non-continuation requests before candidate acceptance; no production behavior change"
    );
    println!();
}

fn print_continuation_acceptance_diagnostics(controls: &[NegativeControl]) {
    println!("## Eval-only continuation-intent gate diagnostics");
    let mut rejected = 0;
    for control in controls {
        let policy_reason = policy_acceptance_reject_reason(control.query);
        let continuation_reason = continuation_acceptance_reject_reason(control.query);
        if continuation_reason.is_some() && continuation_reason != policy_reason {
            rejected += 1;
            println!(
                "  reject {:<40} {:<34} {}",
                control.id,
                continuation_reason.unwrap_or("allow"),
                control.note
            );
        }
    }
    if rejected == 0 {
        println!("  no extra dashboard/state controls rejected beyond policy gate");
    }
    println!(
        "  contract: query-intent gate only; separates dashboard/state continuation from frontend or health dashboard intent; no production behavior change"
    );
    println!();
}

fn print_policy_acceptance_control_eval(controls: &[PolicyAcceptanceControl]) {
    if controls.is_empty() {
        return;
    }

    println!("## Eval-only acceptance/policy control set");
    let mut failures = Vec::new();
    for control in controls {
        let actual = policy_acceptance_reject_reason(control.query);
        let ok = policy_expectation_matches(control.expect, actual);
        if !ok {
            failures.push(control.id);
        }
        println!(
            "  {:<40} {:<36} {:<34} {}",
            control.id,
            policy_expectation_label(control.expect),
            actual.unwrap_or("allow"),
            if ok { "pass" } else { "FAIL" }
        );
        println!("    note: {}", control.note);
    }
    println!(
        "  summary: {} control(s), {} failure(s)",
        controls.len(),
        failures.len()
    );
    if !failures.is_empty() {
        println!("  failures: {}", failures.join(", "));
    }
    println!(
        "  contract: control set checks query-intent acceptance only; it does not inspect or mutate memory rows"
    );
    println!();
}

fn policy_expectation_matches(expect: PolicyExpectation, actual: Option<&'static str>) -> bool {
    match expect {
        PolicyExpectation::Allow => actual.is_none(),
        PolicyExpectation::Reject(reason) => actual == Some(reason),
    }
}

fn policy_expectation_label(expect: PolicyExpectation) -> String {
    match expect {
        PolicyExpectation::Allow => "allow".to_string(),
        PolicyExpectation::Reject(reason) => format!("reject:{reason}"),
    }
}

fn print_exclusion_boundary_diagnostics(
    fts: &ScratchFts,
    controls: &[NegativeControl],
    hits: &[FalseHit],
) {
    println!("## Explicit exclusion boundary diagnostics");
    if hits.is_empty() {
        println!("  no projected+intent false hits to diagnose");
        println!();
        return;
    }

    for hit in hits {
        let Some(control) = controls.iter().find(|control| control.id == hit.control_id) else {
            println!("  {}: missing negative control definition", hit.label());
            continue;
        };
        let Some(projected) = fts.projected_by_key.get(&hit.key) else {
            println!("  {}: missing projected text", hit.label());
            continue;
        };

        let clauses = explicit_exclusion_clauses(control.query);
        let query_cjk_terms = cjk_shingle_terms(control.query)
            .into_iter()
            .collect::<BTreeSet<_>>();
        let query_ascii = ascii_terms(control.query);
        let projected_ascii = ascii_terms(projected);
        let query_ascii_overlap = ascii_overlap_terms(&query_ascii, &projected_ascii);
        let exclusion_matches = candidate_matches_exclusion(&clauses, projected);

        println!("  hit: {}", hit.label());
        println!("    note: {}", control.note);
        println!("    query: {}", control.query);
        println!(
            "    clauses: {}",
            if clauses.is_empty() {
                "-".to_string()
            } else {
                clauses.join(" | ")
            }
        );
        println!("    exclusion_match: {exclusion_matches}");
        println!(
            "    query_cjk_overlap: {}",
            cjk_shingle_overlap_count(&query_cjk_terms, projected)
        );
        println!(
            "    query_ascii_overlap: {}",
            if query_ascii_overlap.is_empty() {
                "-".to_string()
            } else {
                query_ascii_overlap.join(",")
            }
        );
        for clause in &clauses {
            let clause_cjk_terms = cjk_shingle_terms(clause)
                .into_iter()
                .collect::<BTreeSet<_>>();
            let clause_ascii_overlap = ascii_overlap_terms(&ascii_terms(clause), &projected_ascii);
            println!(
                "    clause_diag: cjk_overlap={} ascii_overlap={} clause={}",
                cjk_shingle_overlap_count(&clause_cjk_terms, projected),
                if clause_ascii_overlap.is_empty() {
                    "-".to_string()
                } else {
                    clause_ascii_overlap.join(",")
                },
                clause
            );
        }
        println!("    projected_preview: {}", preview_text(projected, 180));
    }
    println!();
}

fn candidate_matches_exclusion(clauses: &[String], projected: &str) -> bool {
    if clauses.is_empty() {
        return false;
    }

    let projected_ascii = ascii_terms(projected);
    let projected_cjk = cjk_shingle_terms(projected)
        .into_iter()
        .collect::<BTreeSet<_>>();

    clauses.iter().any(|clause| {
        let ascii_hit = ascii_terms(clause)
            .into_iter()
            .any(|term| projected_ascii.contains(&term));
        let cjk_hit_count = cjk_shingle_terms(clause)
            .into_iter()
            .filter(|term| projected_cjk.contains(term))
            .count();

        ascii_hit || cjk_hit_count >= 2
    })
}

fn ascii_terms(text: &str) -> BTreeSet<String> {
    const STOP_WORDS: &[&str] = &[
        "and", "any", "for", "instead", "not", "only", "or", "than", "the", "without",
    ];

    text.split(|ch: char| !ch.is_ascii_alphanumeric())
        .map(str::to_lowercase)
        .filter(|term| term.len() >= 3)
        .filter(|term| !STOP_WORDS.contains(&term.as_str()))
        .collect()
}

fn ascii_overlap_terms(left: &BTreeSet<String>, right: &BTreeSet<String>) -> Vec<String> {
    left.intersection(right).cloned().collect()
}

fn preview_text(text: &str, max_chars: usize) -> String {
    let mut preview = text.chars().take(max_chars).collect::<String>();
    if text.chars().count() > max_chars {
        preview.push_str("...");
    }
    preview.replace('\n', " ")
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

fn dedupe_limit<I>(keys: I, limit: usize) -> Vec<String>
where
    I: IntoIterator<Item = String>,
{
    let mut seen = BTreeSet::new();
    let mut out = Vec::new();
    for key in keys {
        if seen.insert(key.clone()) {
            out.push(key);
            if out.len() >= limit {
                break;
            }
        }
    }
    out
}

fn push_false_hits(
    hits: &mut Vec<FalseHit>,
    control: &NegativeControl,
    keys: &[String],
    gold_keys: &BTreeSet<&str>,
) {
    for (idx, key) in keys.iter().enumerate() {
        if gold_keys.contains(key.as_str()) {
            hits.push(FalseHit {
                control_id: control.id,
                bucket: control.bucket,
                key: key.clone(),
                rank: idx + 1,
            });
        }
    }
}

fn fmt_false_hits(hits: &[FalseHit]) -> String {
    false_hit_labels(hits)
}

fn removed_false_hits(before: &[FalseHit], after: &[FalseHit]) -> Vec<FalseHit> {
    let after_labels = after.iter().map(FalseHit::label).collect::<BTreeSet<_>>();
    before
        .iter()
        .filter(|hit| !after_labels.contains(&hit.label()))
        .cloned()
        .collect()
}

fn false_hit_bucket_count(hits: &[FalseHit], bucket: ControlBucket) -> usize {
    hits.iter().filter(|hit| hit.bucket == bucket).count()
}

fn print_false_hit_bucket_summary(label: &str, hits: &[FalseHit]) {
    println!(
        "  {label} false-hit buckets: unrelated={}, policy_adversarial={}",
        false_hit_bucket_count(hits, ControlBucket::Unrelated),
        false_hit_bucket_count(hits, ControlBucket::PolicyAdversarial)
    );
}

fn held_reason_summary(counts: &BTreeMap<&'static str, usize>) -> String {
    counts
        .iter()
        .map(|(reason, count)| format!("{reason}={count}"))
        .collect::<Vec<_>>()
        .join(", ")
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

fn lost_hit_indices(before: &Agg, after: &Agg) -> Vec<usize> {
    before
        .ranks
        .iter()
        .zip(&after.ranks)
        .enumerate()
        .filter_map(|(i, (b, a))| {
            if b.is_some() && a.is_none() {
                Some(i + 1)
            } else {
                None
            }
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
    stratum_counts_for(CORPUS)
}

fn stratum_counts_for(cases: &[Case]) -> Vec<(&'static str, usize)> {
    let mut counts: HashMap<&'static str, usize> = HashMap::new();
    for case in cases {
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
    fn dedupe_limit_preserves_first_seen_order() {
        let keys = vec![
            "a".to_string(),
            "b".to_string(),
            "a".to_string(),
            "c".to_string(),
            "d".to_string(),
        ];

        assert_eq!(
            dedupe_limit(keys, 3),
            vec!["a".to_string(), "b".to_string(), "c".to_string()]
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
    fn aio2_native_corpus_stays_host_local_and_not_self_observing() {
        assert_eq!(
            AIO2_NATIVE_CORPUS.len(),
            14,
            "aio2-native corpus should stay intentionally small and explicit"
        );
        assert!(
            AIO2_NATIVE_NEGATIVE_CONTROLS.len() >= 4,
            "aio2-native corpus should keep unrelated and adversarial controls"
        );
        for case in AIO2_NATIVE_CORPUS {
            assert_ne!(
                case.query, case.trigger,
                "{} must use a held-out intent query, not exact trigger text",
                case.id
            );
            assert!(
                !case.id.contains("trigger_recall"),
                "{} should not make trigger-recall self-observation part of the first aio2 corpus",
                case.id
            );
            for expected in case.expect {
                assert!(
                    !expected.contains("trigger_recall"),
                    "{expected} should not make trigger-recall self-observation part of the first aio2 corpus"
                );
            }
        }
    }

    #[test]
    fn aio2_native_negative_controls_keep_bucket_balance() {
        let unrelated = AIO2_NATIVE_NEGATIVE_CONTROLS
            .iter()
            .filter(|control| control.bucket == ControlBucket::Unrelated)
            .count();
        let policy_adversarial = AIO2_NATIVE_NEGATIVE_CONTROLS
            .iter()
            .filter(|control| control.bucket == ControlBucket::PolicyAdversarial)
            .count();

        assert_eq!(
            unrelated, 4,
            "aio2-native controls should keep unrelated desktop/frontend/dashboard probes separate"
        );
        assert_eq!(
            policy_adversarial, 4,
            "aio2-native controls should keep policy/adversarial adjacent probes separate"
        );
    }

    #[test]
    fn aio2_goal_c_dashboard_state_contrastives_pair_positive_and_unrelated_intents() {
        for (case_id, expected_key) in [
            (
                "aio2_goal_c_dashboard_state_boundary",
                "controlled_recursive_self_improvement_goal_c_boundary_20260621",
            ),
            (
                "aio2_goal_c_dashboard_state_closure",
                "controlled_rsi_goal_c_local_run_and_closure_20260621",
            ),
        ] {
            let case = AIO2_NATIVE_CORPUS
                .iter()
                .find(|case| case.id == case_id)
                .unwrap_or_else(|| panic!("missing positive contrastive case {case_id}"));
            assert_eq!(case.stratum, "goal_c");
            assert!(
                case.expect.contains(&expected_key),
                "{case_id} should keep the intended Goal C gold key"
            );
            assert_eq!(
                continuation_acceptance_reject_reason(case.query),
                None,
                "{case_id} must remain an allowed dashboard/state continuation"
            );
        }

        for (control_id, expected_reason) in [
            (
                "aio2_unrelated_frontend_goal_c_words",
                "frontend_dashboard_intent",
            ),
            (
                "aio2_unrelated_controlled_rsi_health_dashboard",
                "health_dashboard_intent",
            ),
        ] {
            let control = AIO2_NATIVE_NEGATIVE_CONTROLS
                .iter()
                .find(|control| control.id == control_id)
                .unwrap_or_else(|| panic!("missing negative contrastive control {control_id}"));
            assert_eq!(control.bucket, ControlBucket::Unrelated);
            assert_eq!(
                policy_acceptance_reject_reason(control.query),
                None,
                "{control_id} must remain a domain-intent contrast, not a policy/adversarial gate"
            );
            assert_eq!(
                continuation_acceptance_reject_reason(control.query),
                Some(expected_reason),
                "{control_id} should be rejected by the dashboard/state continuation gate"
            );
        }
    }

    #[test]
    fn aio2_native_policy_acceptance_controls_cover_reject_and_allow() {
        let rejected = AIO2_NATIVE_POLICY_ACCEPTANCE_CONTROLS
            .iter()
            .filter(|control| matches!(control.expect, PolicyExpectation::Reject(_)))
            .count();
        let allowed = AIO2_NATIVE_POLICY_ACCEPTANCE_CONTROLS
            .iter()
            .filter(|control| control.expect == PolicyExpectation::Allow)
            .count();

        assert_eq!(rejected, 4, "keep English and Chinese reject controls");
        assert_eq!(allowed, 5, "keep risky-word continuation allow controls");
        for control in AIO2_NATIVE_POLICY_ACCEPTANCE_CONTROLS {
            assert!(
                policy_expectation_matches(
                    control.expect,
                    policy_acceptance_reject_reason(control.query)
                ),
                "{} policy expectation mismatch",
                control.id
            );
        }
    }

    #[test]
    fn baseline_shadow_accept_keeps_allowed_continuation_candidates() {
        let allowed = AIO2_NATIVE_POLICY_ACCEPTANCE_CONTROLS
            .iter()
            .find(|control| control.id == "aio2_policy_allow_g25_store_write")
            .expect("allow control exists");
        let keys = vec!["g25".to_string(), "g26".to_string()];
        let reason = baseline_acceptance_reject_reason(allowed.query);

        assert_eq!(reason, None);
        assert_eq!(shadow_visible_baseline_keys(&keys, reason), keys);
    }

    #[test]
    fn baseline_shadow_holds_rejected_controls_without_empty_production_claim() {
        for (control_id, expected_reason) in [
            (
                "aio2_unrelated_frontend_goal_c_words",
                "frontend_dashboard_intent",
            ),
            (
                "aio2_unrelated_controlled_rsi_health_dashboard",
                "health_dashboard_intent",
            ),
            ("aio2_adjacent_write_request", "write_bypass_intent"),
            (
                "aio2_adjacent_lswr_poetry",
                "creative_non_continuation_intent",
            ),
        ] {
            let control = AIO2_NATIVE_NEGATIVE_CONTROLS
                .iter()
                .find(|control| control.id == control_id)
                .unwrap_or_else(|| panic!("missing control {control_id}"));
            let keys = vec!["gold".to_string()];
            let reason = baseline_acceptance_reject_reason(control.query);

            assert_eq!(reason, Some(expected_reason), "{control_id}");
            assert!(shadow_visible_baseline_keys(&keys, reason).is_empty());
        }
    }

    #[test]
    fn portable_stage2_fixture_is_self_contained_and_not_live_aio2() {
        let rows = portable_stage2_fixture_rows();
        let coverage = corpus_coverage_for(&rows, PORTABLE_STAGE2_CORPUS);
        let aio2_keys = AIO2_NATIVE_CORPUS
            .iter()
            .flat_map(|case| case.expect.iter().copied())
            .collect::<BTreeSet<_>>();

        verify_corpus_for(
            &rows,
            PORTABLE_STAGE2_CORPUS,
            PORTABLE_STAGE2_NEGATIVE_CONTROLS,
        )
        .expect("portable fixture corpus should be internally runnable");
        assert!(
            coverage.ready(),
            "portable fixture should not need live DB rows"
        );
        assert_eq!(coverage.active_total, PORTABLE_STAGE2_CORPUS.len());
        assert_eq!(coverage.trigger_rows, PORTABLE_STAGE2_CORPUS.len());
        assert!(
            PORTABLE_STAGE2_FIXTURE_LABEL.contains("no live DB"),
            "fixture output label must not look like live aio2 evidence"
        );
        for row in rows {
            assert!(
                row.scope.as_deref().unwrap_or("").contains("portable"),
                "{} should stay visibly fixture-scoped",
                row.key
            );
            assert!(
                !aio2_keys.contains(row.key.as_str()),
                "{} should not reuse mutable aio2 live-corpus gold keys",
                row.key
            );
        }
    }

    #[test]
    fn portable_stage2_fixture_exercises_accept_and_shadow_hold_shapes() {
        let rows = portable_stage2_fixture_rows();
        let fts = ScratchFts::build(&rows).expect("scratch fts");
        let gold_keys = PORTABLE_STAGE2_CORPUS
            .iter()
            .flat_map(|case| case.expect.iter().copied())
            .collect::<BTreeSet<_>>();

        for case in PORTABLE_STAGE2_CORPUS {
            let audit = baseline_acceptance_audit(&fts, case.query, TOP_K).expect("positive audit");
            assert_eq!(
                audit.query_intent_reject_reason, None,
                "{} should be an allowed continuation",
                case.id
            );
            assert!(
                first_hit_rank(&audit.baseline_keys_before_gate, case.expect).is_some(),
                "{} should hit the fixture gold key before the shadow gate",
                case.id
            );
            assert_eq!(
                audit.baseline_keys_before_gate, audit.baseline_keys_after_shadow_gate,
                "{} should preserve visible baseline keys",
                case.id
            );
        }

        for (control_id, expected_reason) in [
            (
                "fixture_frontend_dashboard_hold",
                "frontend_dashboard_intent",
            ),
            ("fixture_write_bypass_hold", "write_bypass_intent"),
        ] {
            let control = PORTABLE_STAGE2_NEGATIVE_CONTROLS
                .iter()
                .find(|control| control.id == control_id)
                .unwrap_or_else(|| panic!("missing portable control {control_id}"));
            let audit =
                baseline_acceptance_audit(&fts, control.query, TOP_K).expect("control audit");
            assert_eq!(
                audit.query_intent_reject_reason,
                Some(expected_reason),
                "{control_id} should be shadow-held for the expected reason"
            );
            assert!(
                audit
                    .baseline_keys_before_gate
                    .iter()
                    .any(|key| gold_keys.contains(key.as_str())),
                "{control_id} should demonstrate a real baseline false-hit shape"
            );
            assert!(
                !audit
                    .baseline_keys_after_shadow_gate
                    .iter()
                    .any(|key| gold_keys.contains(key.as_str())),
                "{control_id} should remove fixture gold keys after the shadow gate"
            );
        }

        let unrelated = PORTABLE_STAGE2_NEGATIVE_CONTROLS
            .iter()
            .find(|control| control.id == "fixture_unrelated_desktop_allow_no_hit")
            .expect("unrelated control exists");
        let unrelated_audit =
            baseline_acceptance_audit(&fts, unrelated.query, TOP_K).expect("unrelated audit");
        assert_eq!(
            unrelated_audit.query_intent_reject_reason, None,
            "unrelated no-hit controls should not be counted as held"
        );
        assert!(
            !unrelated_audit
                .baseline_keys_before_gate
                .iter()
                .any(|key| gold_keys.contains(key.as_str())),
            "unrelated no-hit control should not retrieve fixture gold keys"
        );
    }

    #[test]
    fn aio2_baseline_acceptance_missing_corpus_is_stale_telemetry_not_gate() {
        let (status, hard_gate_authority, coverage) =
            aio2_baseline_acceptance_telemetry_status(&[]);

        assert_eq!(status, "stale_corpus_not_gate");
        assert!(!hard_gate_authority);
        assert_eq!(coverage.present_expected, 0);
        assert_eq!(coverage.missing_expected.len(), coverage.expected_refs);
        assert!(
            !coverage.ready(),
            "empty live rows must not look like ready aio2 telemetry"
        );
    }

    #[test]
    fn aio2_baseline_acceptance_ready_corpus_is_still_not_hard_gate() {
        let rows = rows_for_cases(AIO2_NATIVE_CORPUS);
        let (status, hard_gate_authority, coverage) =
            aio2_baseline_acceptance_telemetry_status(&rows);

        assert_eq!(status, "ready_live_telemetry_not_gate");
        assert!(!hard_gate_authority);
        assert!(coverage.ready());
        assert_eq!(coverage.missing_expected.len(), 0);
        assert_eq!(coverage.expected_without_trigger.len(), 0);
    }

    #[test]
    fn corpus_coverage_reports_missing_gold_keys() {
        let coverage = corpus_coverage(&[]);
        let expected_refs = CORPUS.iter().map(|case| case.expect.len()).sum::<usize>();

        assert_eq!(coverage.expected_refs, expected_refs);
        assert_eq!(coverage.present_expected, 0);
        assert_eq!(coverage.missing_expected.len(), expected_refs);
        assert!(!coverage.ready());
    }

    #[test]
    fn corpus_coverage_requires_trigger_on_expected_rows() {
        let first = &CORPUS[0];
        let row = MemoryRow {
            key: first.expect[0].to_string(),
            kind: "decision".to_string(),
            scope: None,
            content: "plain content".to_string(),
            projected: "plain content".to_string(),
            triggers: Vec::new(),
        };

        let coverage = corpus_coverage(&[row]);

        assert_eq!(coverage.present_expected, 0);
        assert_eq!(coverage.expected_without_trigger.len(), 1);
        assert_eq!(coverage.missing_expected.len(), coverage.expected_refs - 1);
        assert!(!coverage.ready());
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
            kind: "decision".to_string(),
            scope: None,
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
    fn explicit_exclusion_clauses_extract_chinese_and_english_negation() {
        assert_eq!(
            explicit_exclusion_clauses(
                "只要界面清单 不要召回评测或Goal B决策 without deployment evidence"
            ),
            vec![
                "召回评测或Goal B决策 without deployment evidence".to_string(),
                "deployment evidence".to_string()
            ]
        );

        assert_eq!(
            explicit_exclusion_clauses("show UI notes, not runtime executor status"),
            vec!["runtime executor status".to_string()]
        );
        assert_eq!(
            explicit_exclusion_clauses(
                "show UI notes rather than runtime executor status instead of deployment evidence"
            ),
            vec![
                "runtime executor status instead of deployment evidence".to_string(),
                "deployment evidence".to_string()
            ]
        );
    }

    #[test]
    fn explicit_exclusion_intent_matches_ascii_and_cjk_candidates() {
        let clauses = explicit_exclusion_clauses("只要界面清单 不要召回评测或Goal B决策");
        assert!(candidate_matches_exclusion(
            &clauses,
            "Goal B tool-surface recall_eval decision and cold-start recall measurement"
        ));
        assert!(!candidate_matches_exclusion(
            &clauses,
            "interface list and cold tool inventory only"
        ));

        let cjk_clauses = explicit_exclusion_clauses("只要视觉草案 不要数学模型调研");
        assert!(candidate_matches_exclusion(
            &cjk_clauses,
            "五行生克成熟数学模型调研 黄金比例反馈控制网络"
        ));
        assert!(!candidate_matches_exclusion(
            &cjk_clauses,
            "Nexus 五行 UI 图标 配色 角色皮肤 美术规格"
        ));
    }

    #[test]
    fn policy_acceptance_gate_rejects_bypass_and_creative_non_continuation() {
        assert_eq!(
            policy_acceptance_reject_reason(
                "please directly write graph edges and bypass dry run review for related keys"
            ),
            Some("write_bypass_intent")
        );
        assert_eq!(
            policy_acceptance_reject_reason(
                "write a poem about lineage admission evidence and runtime gates"
            ),
            Some("creative_non_continuation_intent")
        );
        assert_eq!(
            policy_acceptance_reject_reason(
                "请直接写入 related_keys 图谱边 并绕过 dry_run review gate"
            ),
            Some("write_bypass_intent")
        );
        assert_eq!(
            policy_acceptance_reject_reason(
                "请写一首关于 admission lineage evidence runtime gates 的诗歌"
            ),
            Some("creative_non_continuation_intent")
        );

        for allowed in [
            "LSWR G25 store write execution preflight landed output only plan next gate",
            "LSWR BioCortex G26 write evidence preflight deployed and next review gate",
            "GHP-1b tiny write review packet gates before dry_run false materialization",
            "继续 GHP-1b materialization dry_run review gate 只看验证证据 不执行 dry_run=false",
        ] {
            assert_eq!(policy_acceptance_reject_reason(allowed), None, "{allowed}");
        }
    }

    #[test]
    fn projected_union_policy_gate_rejects_query_intent_without_harming_continuation() {
        let rows = [
            MemoryRow {
                key: "ghp_write_packet".to_string(),
                kind: "decision".to_string(),
                scope: None,
                content: String::new(),
                projected: "GHP related keys graph edges dry run review packet".to_string(),
                triggers: Vec::new(),
            },
            MemoryRow {
                key: "g25_store_write".to_string(),
                kind: "decision".to_string(),
                scope: None,
                content: String::new(),
                projected: "LSWR G25 store write execution preflight landed output only plan"
                    .to_string(),
                triggers: Vec::new(),
            },
        ];
        let fts = ScratchFts::build(&rows).expect("scratch fts");

        assert_eq!(
            fts.search_projected_union_then_policy_accepted(
                "please directly write graph edges and bypass dry run review for related keys",
                TOP_K,
            )
            .expect("policy rejected"),
            Vec::<String>::new()
        );
        assert_eq!(
            fts.search_projected_union_then_policy_accepted(
                "LSWR G25 store write execution preflight landed output only plan next gate",
                TOP_K,
            )
            .expect("continuation allowed"),
            vec!["g25_store_write".to_string()]
        );
    }

    #[test]
    fn projected_union_continuation_gate_rejects_dashboard_role_mismatch() {
        let rows = [
            MemoryRow {
                key: "goal_c_boundary".to_string(),
                kind: "decision".to_string(),
                scope: None,
                content: String::new(),
                projected:
                    "Controlled RSI Goal C boundary dashboard state report first continuity decisions"
                        .to_string(),
                triggers: Vec::new(),
            },
            MemoryRow {
                key: "goal_c_closure".to_string(),
                kind: "decision".to_string(),
                scope: None,
                content: String::new(),
                projected:
                    "Agent Bridge Goal C dashboard state U report closure no executor decision"
                        .to_string(),
                triggers: Vec::new(),
            },
        ];
        let fts = ScratchFts::build(&rows).expect("scratch fts");

        assert_eq!(
            continuation_acceptance_reject_reason(
                "Goal C dashboard state for Controlled RSI boundary and report first continuity decisions"
            ),
            None
        );
        let allowed_keys = fts
            .search_projected_union_then_continuation_accepted(
                "Goal C dashboard state for Controlled RSI boundary and report first continuity decisions",
                TOP_K,
            )
            .expect("continuation allowed");
        assert_eq!(
            allowed_keys.first().map(String::as_str),
            Some("goal_c_boundary")
        );
        assert!(allowed_keys.contains(&"goal_c_closure".to_string()));

        assert_eq!(
            continuation_acceptance_reject_reason(
                "Goal C dashboard state card spacing responsive layout visual design only not continuity ledger work"
            ),
            Some("frontend_dashboard_intent")
        );
        assert_eq!(
            fts.search_projected_union_then_continuation_accepted(
                "Goal C dashboard state card spacing responsive layout visual design only not continuity ledger work",
                TOP_K,
            )
            .expect("frontend dashboard rejected"),
            Vec::<String>::new()
        );

        assert_eq!(
            continuation_acceptance_reject_reason(
                "Controlled RSI exercise recovery dashboard state color cards pain tracker layout"
            ),
            Some("health_dashboard_intent")
        );
        assert_eq!(
            fts.search_projected_union_then_continuation_accepted(
                "Controlled RSI exercise recovery dashboard state color cards pain tracker layout",
                TOP_K,
            )
            .expect("health dashboard rejected"),
            Vec::<String>::new()
        );
    }

    #[test]
    fn runtime_shaped_audit_accepts_supplemental_recovery_without_runtime_authority() {
        let query = "LSWR G25 store write execution preflight landed output only plan next gate";
        let rows = [
            MemoryRow {
                key: "precise_distractor".to_string(),
                kind: "decision".to_string(),
                scope: None,
                content: String::new(),
                projected:
                    "LSWR G25 store write execution preflight landed output only plan next gate distractor"
                        .to_string(),
                triggers: Vec::new(),
            },
            MemoryRow {
                key: "g25_target".to_string(),
                kind: "decision".to_string(),
                scope: None,
                content: String::new(),
                projected: "LSWR G25 store write execution preflight landed output only"
                    .to_string(),
                triggers: Vec::new(),
            },
        ];
        let fts = ScratchFts::build(&rows).expect("scratch fts");
        let audit = runtime_shaped_audit(&fts, query, TOP_K).expect("runtime-shaped audit");

        assert_eq!(audit.baseline_keys, vec!["precise_distractor".to_string()]);
        assert!(audit
            .supplemental_before_gate
            .contains(&"g25_target".to_string()));
        assert!(audit
            .supplemental_after_gate
            .contains(&"g25_target".to_string()));
        assert!(audit.final_keys.contains(&"g25_target".to_string()));
        assert_eq!(audit.policy_reject_reason, None);
        assert_eq!(audit.continuation_reject_reason, None);
        assert_eq!(
            audit.fallback_behavior,
            "baseline_plus_supplemental_projected"
        );

        let payload = audit.to_json();
        assert_eq!(payload["default_memory_search_unchanged"], json!(true));
        assert_eq!(payload["changes_production_retrieval"], json!(false));
        assert!(payload["query_hash"]
            .as_str()
            .expect("query hash")
            .starts_with("sha256:"));
        assert!(
            !payload.to_string().contains(query),
            "audit payload should not echo the raw query"
        );
    }

    #[test]
    fn runtime_shaped_audit_rejects_supplemental_but_keeps_baseline() {
        let query = "Goal C dashboard state card spacing responsive layout visual design only not continuity ledger work";
        let rows = [
            MemoryRow {
                key: "frontend_baseline".to_string(),
                kind: "decision".to_string(),
                scope: None,
                content: String::new(),
                projected:
                    "Goal C dashboard state card spacing responsive layout visual design only not continuity ledger work"
                        .to_string(),
                triggers: Vec::new(),
            },
            MemoryRow {
                key: "goal_c_supplemental".to_string(),
                kind: "decision".to_string(),
                scope: None,
                content: String::new(),
                projected:
                    "Goal C dashboard state continuity ledger work report first decision"
                        .to_string(),
                triggers: Vec::new(),
            },
        ];
        let fts = ScratchFts::build(&rows).expect("scratch fts");
        let audit = runtime_shaped_audit(&fts, query, TOP_K).expect("runtime-shaped audit");

        assert_eq!(audit.baseline_keys, vec!["frontend_baseline".to_string()]);
        assert!(audit
            .supplemental_before_gate
            .contains(&"goal_c_supplemental".to_string()));
        assert!(
            audit.supplemental_after_gate.is_empty(),
            "frontend intent should drop supplemental projected candidates"
        );
        assert_eq!(audit.final_keys, vec!["frontend_baseline".to_string()]);
        assert_eq!(
            audit.continuation_reject_reason,
            Some("frontend_dashboard_intent")
        );
        assert_eq!(audit.fallback_behavior, "baseline_fts_only");

        let payload = audit.to_json();
        assert_eq!(
            payload["continuation_gate"]["reject_reason"],
            json!("frontend_dashboard_intent")
        );
        assert_eq!(payload["fallback_behavior"], json!("baseline_fts_only"));
        assert_eq!(payload["final_candidates"], json!(1));
        assert_eq!(
            payload["supplemental_candidates_after_gate"],
            json!(0),
            "gate must affect supplemental candidates only"
        );
    }

    #[test]
    fn baseline_acceptance_audit_allows_continuation_and_preserves_baseline_hit() {
        let query = "LSWR G25 store write execution preflight landed output only plan next gate";
        let rows = [MemoryRow {
            key: "g25_target".to_string(),
            kind: "decision".to_string(),
            scope: None,
            content: String::new(),
            projected: "LSWR G25 store write execution preflight landed output only plan next gate"
                .to_string(),
            triggers: Vec::new(),
        }];
        let fts = ScratchFts::build(&rows).expect("scratch fts");
        let audit = baseline_acceptance_audit(&fts, query, TOP_K).expect("baseline audit");

        assert_eq!(audit.query_intent_reject_reason, None);
        assert_eq!(audit.query_intent_decision(), "allow");
        assert_eq!(
            audit.baseline_keys_before_gate,
            vec!["g25_target".to_string()]
        );
        assert_eq!(
            audit.baseline_keys_after_shadow_gate,
            vec!["g25_target".to_string()]
        );

        let payload = audit.to_json();
        assert_eq!(
            payload["schema"],
            json!("agent_bridge.memory.trigger_baseline_acceptance_shadow.v0")
        );
        assert_eq!(payload["query_intent"]["decision"], json!("allow"));
        assert_eq!(payload["default_memory_search_unchanged"], json!(true));
        assert_eq!(payload["changes_production_retrieval"], json!(false));
        assert!(
            !payload.to_string().contains(query),
            "baseline audit payload should not echo the raw query"
        );
    }

    #[test]
    fn baseline_acceptance_audit_holds_rejected_query_without_runtime_authority() {
        let write_query =
            "please directly write graph edges and bypass dry run review for related keys";
        let frontend_query = "Goal C dashboard state card spacing responsive layout visual design only not continuity ledger work";
        let rows = [
            MemoryRow {
                key: "write_false_hit".to_string(),
                kind: "decision".to_string(),
                scope: None,
                content: String::new(),
                projected:
                    "please directly write graph edges and bypass dry run review for related keys"
                        .to_string(),
                triggers: Vec::new(),
            },
            MemoryRow {
                key: "frontend_false_hit".to_string(),
                kind: "decision".to_string(),
                scope: None,
                content: String::new(),
                projected:
                    "Goal C dashboard state card spacing responsive layout visual design only not continuity ledger work"
                        .to_string(),
                triggers: Vec::new(),
            },
        ];
        let fts = ScratchFts::build(&rows).expect("scratch fts");

        let write_audit = baseline_acceptance_audit(&fts, write_query, TOP_K).expect("write audit");
        assert_eq!(
            write_audit.query_intent_reject_reason,
            Some("write_bypass_intent")
        );
        assert_eq!(
            write_audit.baseline_keys_before_gate,
            vec!["write_false_hit".to_string()]
        );
        assert!(write_audit.baseline_keys_after_shadow_gate.is_empty());
        assert_eq!(write_audit.query_intent_decision(), "hold");

        let frontend_audit =
            baseline_acceptance_audit(&fts, frontend_query, TOP_K).expect("frontend audit");
        assert_eq!(
            frontend_audit.query_intent_reject_reason,
            Some("frontend_dashboard_intent")
        );
        assert_eq!(
            frontend_audit.baseline_keys_before_gate,
            vec!["frontend_false_hit".to_string()]
        );
        assert!(frontend_audit.baseline_keys_after_shadow_gate.is_empty());

        let payload = frontend_audit.to_json();
        assert_eq!(payload["query_intent"]["decision"], json!("hold"));
        assert_eq!(
            payload["query_intent"]["reject_reason"],
            json!("frontend_dashboard_intent")
        );
        assert_eq!(
            payload["visible_behavior_if_production"],
            json!("not_authorized_shadow_only")
        );
        assert_eq!(payload["baseline_candidates_before_gate"], json!(1));
        assert_eq!(payload["baseline_candidates_after_shadow_gate"], json!(0));
    }

    #[test]
    fn wuxing_art_remaining_false_hit_is_query_overlap_not_exclusion_clause_overlap() {
        let query = "Nexus 五行 UI 图标 配色 角色皮肤 美术规格 只要视觉草案 不要数学模型调研";
        let projected =
            "Nexus #35 科技五行生克 / tech-wuxing-sheng-ke / 五行研究生克 v0.2 re-review";
        let clauses = explicit_exclusion_clauses(query);
        let query_ascii = ascii_terms(query);
        let projected_ascii = ascii_terms(projected);

        assert_eq!(clauses, vec!["数学模型调研".to_string()]);
        assert!(!candidate_matches_exclusion(&clauses, projected));
        assert_eq!(
            ascii_overlap_terms(&query_ascii, &projected_ascii),
            vec!["nexus".to_string()]
        );
    }

    #[test]
    fn projected_then_intent_accepted_filters_excluded_candidates() {
        let rows = [
            MemoryRow {
                key: "goal_b".to_string(),
                kind: "decision".to_string(),
                scope: None,
                content: String::new(),
                projected: "Goal B 工具面 冷工具 裁剪 召回评测 decision".to_string(),
                triggers: Vec::new(),
            },
            MemoryRow {
                key: "interface_inventory".to_string(),
                kind: "context".to_string(),
                scope: None,
                content: String::new(),
                projected: "Agent Bridge essential 工具面 冷工具 裁剪 看板 巡检 界面清单"
                    .to_string(),
                triggers: Vec::new(),
            },
        ];
        let fts = ScratchFts::build(&rows).expect("scratch fts");

        let accepted = fts
            .search_projected_then_intent_accepted(
                "Agent Bridge essential 工具面 冷工具 裁剪 看板 巡检 只要界面清单 不要召回评测或Goal B决策",
                TOP_K,
            )
            .expect("intent accepted search");

        assert!(!accepted.contains(&"goal_b".to_string()));
        assert!(accepted.contains(&"interface_inventory".to_string()));
    }

    #[test]
    fn projected_then_cjk_accepted_uses_cjk_only_as_miss_fallback() {
        let rows = [
            MemoryRow {
                key: "projected_hit".to_string(),
                kind: "decision".to_string(),
                scope: None,
                content: String::new(),
                projected: "ordinary projected anchor".to_string(),
                triggers: Vec::new(),
            },
            MemoryRow {
                key: "cjk_fallback".to_string(),
                kind: "decision".to_string(),
                scope: None,
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

    fn rows_for_cases(cases: &[Case]) -> Vec<MemoryRow> {
        let mut rows = Vec::new();
        let mut seen = BTreeSet::new();
        for case in cases {
            for expected in case.expect {
                if !seen.insert(*expected) {
                    continue;
                }
                rows.push(MemoryRow {
                    key: (*expected).to_string(),
                    kind: "fixture".to_string(),
                    scope: Some("project:/test-aio2-telemetry".to_string()),
                    content: format!("Test fixture row for {}.", case.id),
                    projected: format!(
                        "{}\n{}\n{}\n{}",
                        case.query, case.trigger, case.note, expected
                    ),
                    triggers: vec![case.trigger.to_string()],
                });
            }
        }
        rows
    }
}
