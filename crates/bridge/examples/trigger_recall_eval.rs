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
//! - `exact_projected`: authored trigger text over `fts_content`.
//!
//! The first two isolate trigger projection from production ranking. They do
//! not use access_count, importance, recency, graph expansion, semantic
//! embeddings, `memory_get`, or `memory_search`. The third mode is a projection
//! health probe and can expose FTS parser problems in trigger text.
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
const TRIGGER_PREFIX: &str = "continuity_retrieval_trigger:";

struct Case {
    id: &'static str,
    query: &'static str,
    trigger: &'static str,
    expect: &'static [&'static str],
    note: &'static str,
}

/// Cases selected from active Mac rows carrying `continuity_retrieval_trigger`
/// tags on 2026-06-22. `trigger` is the authored metadata. `query` is a
/// separate held-out continuation intent so the eval does not pass by exact
/// trigger echo.
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
    let mut exact_projected = Agg::default();

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

        let trigger_keys = fts.search(IndexKind::Projected, case.trigger, TOP_K);
        exact_projected.record(
            first_hit_rank(trigger_keys.as_deref().unwrap_or(&[]), case.expect),
            trigger_keys.err(),
        );
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
    print_row("exact_projected", &exact_projected, n);
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

    println!("## Per-case first-hit rank (- = no hit in top {TOP_K}; ERR = FTS parser error)");
    println!(
        "  {:<3} {:<28} {:>8} {:>10} {:>10}  {}",
        "#", "id", "content", "projected", "exact", "note"
    );
    for (i, case) in CORPUS.iter().enumerate() {
        println!(
            "  {:<3} {:<28} {:>8} {:>10} {:>10}  {}",
            i + 1,
            case.id,
            rank_cell(intent_content.ranks[i], intent_content.errors[i].as_deref()),
            rank_cell(
                intent_projected.ranks[i],
                intent_projected.errors[i].as_deref()
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
        "  caveat: hand-curated corpus, N={n}. This is a first trigger-cohort \
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
        for expected in case.expect {
            let row = by_key
                .get(expected)
                .ok_or_else(|| format!("{} expected key missing: {expected}", case.id))?;
            if row.triggers.is_empty() {
                return Err(format!("{} expected key has no trigger: {expected}", case.id).into());
            }
        }
    }
    Ok(())
}

#[derive(Clone, Copy)]
enum IndexKind {
    Content,
    Projected,
}

struct ScratchFts {
    db: RusqliteConnection,
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
             );",
        )?;

        {
            let mut content_stmt =
                db.prepare("INSERT INTO content_fts(key, body) VALUES (?1, ?2)")?;
            let mut projected_stmt =
                db.prepare("INSERT INTO projected_fts(key, body) VALUES (?1, ?2)")?;
            for row in rows {
                content_stmt.execute(params![row.key, row.content])?;
                projected_stmt.execute(params![row.key, row.projected])?;
            }
        }

        Ok(Self { db })
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

    Ok(())
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
}
