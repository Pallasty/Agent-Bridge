//! **P2 — nightly distillation draft queue (propose-only).**
//!
//! Picks the top-N verified, still-undistilled mechanism rows (the same S1
//! detector session_bootstrap surfaces), asks `claude -p` for a
//! distill/merge/reject verdict + pub_* draft per candidate, and stores each
//! result as a `distill_draft_<source_key>` memory row for agent review.
//!
//! **This module NEVER writes pub_* rows.** The pilot measured a permissive
//! bias in the distiller (3/3 disagreements were "proposed more than the
//! human label"), so the write stays behind per-row agent review — see
//! `p2_distill_pilot_verdict_20260707` ruling #1.
//!
//! Queue lifecycle (self-cleaning, zero mandatory bookkeeping):
//!   - a draft leaves the pending queue when its SOURCE key shows up in any
//!     pub_* row's related_keys (distill or merge executed — the same
//!     provenance back-link that dequeues S1 candidates),
//!   - or when the source row gains the `distill:no` tag (reject executed),
//!   - or when the draft row itself gains a `resolved:*` tag (manual out).
//!   Deleting a draft row returns its candidate to the batch queue — the
//!   permanent way to dismiss a candidate is `distill:no` on the source,
//!   which is the S1 contract already.
//!
//! Designed to run nightly via cron (like `dream replay`), not in the live
//! MCP daemon: short-lived process, own sqlite handle, WAL handles the
//! concurrent live readers. Cost envelope from the pilot: ~62 s/candidate on
//! the default `claude -p` model → top-5 ≈ 5 min.

use ab_store::{default_db_path, MemoryListSort, MemoryRecord, SqliteStore, StateStore};
use anyhow::Result;
use std::collections::HashSet;
use std::sync::Arc;
use std::time::{SystemTime, UNIX_EPOCH};

/// Version tag stamped on every draft (`distill_prompt:v1`). Bump when the
/// template or few-shots change so draft quality can be compared across
/// prompt revisions (reflexio prompt-bank posture — pilot ruling #3).
pub const PROMPT_VERSION: &str = "v1";

/// v1 prompt = the pilot's PROMPT.md verbatim (four disciplines + draft
/// format contract + strict-JSON output). Validated 2026-07-07: 10/10
/// commit-ready drafts, 0 fabrications, 2/2 gold-replay dedup.
const PROMPT_TEMPLATE: &str = include_str!("distill_assets/prompt_v1.md");
const FEWSHOT_SOURCE: &str = include_str!("distill_assets/fewshot_source_v1.json");
const FEWSHOT_OUTPUT: &str = include_str!("distill_assets/fewshot_output_v1.json");

/// Kind of the queue rows this module writes.
pub const DRAFT_KIND: &str = "distill_draft";
const DRAFT_KEY_PREFIX: &str = "distill_draft_";

/// Per-kind fetch cap. Generous vs bootstrap's 200: the batch is not
/// latency-bound and an incomplete pub_* corpus index would cause duplicate
/// distills (the index is the merge/overlap evidence in the prompt).
const POOL_FETCH_LIMIT: u32 = 1_000;

/// Parsed + validated `claude -p` output for one candidate.
#[derive(Debug, Clone, PartialEq)]
pub struct DistillVerdict {
    /// "distill" | "merge" | "reject"
    pub verdict: String,
    pub reasoning: String,
    /// Required for merge; the existing pub_* row to fold the source into.
    pub existing_key: Option<String>,
    /// Required for distill; the proposed new pub_* row.
    pub draft: Option<ProposedPubRow>,
    /// Raw model output (post fence-strip) — embedded in the draft record so
    /// the reviewer sees exactly what the model said.
    pub raw_json: String,
}

/// The pub_* row a distill verdict proposes (prompt's draft format contract).
#[derive(Debug, Clone, PartialEq)]
pub struct ProposedPubRow {
    pub key: String,
    pub scope: Option<String>,
    pub content: String,
    pub tags: Vec<String>,
    pub retrieval_trigger: String,
    pub related_keys: Vec<String>,
}

/// Public entry point — the dispatcher in `main.rs` calls this.
pub async fn run(top_n: usize, dry_run: bool, timeout_secs: u64) -> Result<()> {
    if top_n == 0 {
        return Err(anyhow::anyhow!("--top-n must be ≥ 1"));
    }
    let db_path = default_db_path();
    println!("# P2 distill draft queue  (top_n={top_n}, dry_run={dry_run}, prompt={PROMPT_VERSION})");
    println!("DB: {}", db_path.display());

    let store = SqliteStore::open(&db_path)
        .await
        .map_err(|e| anyhow::anyhow!("open state.db at {db_path:?}: {e}"))?;
    let store: Arc<dyn StateStore> = Arc::new(store);

    // Same scope-less pool the bootstrap S1 block builds: pub_* rows live
    // under domain:* scopes and candidates under project scopes, so any
    // in-scope list would miss one side or the other.
    let mut pool: Vec<MemoryRecord> = Vec::new();
    for kind in ["lesson", "error_pattern", "present_outcome", "outcome"] {
        pool.extend(
            store
                .list_memories(Some(kind), MemoryListSort::Newest, POOL_FETCH_LIMIT)
                .await
                .unwrap_or_default(),
        );
    }
    let draft_rows = store
        .list_memories(Some(DRAFT_KIND), MemoryListSort::Newest, POOL_FETCH_LIMIT)
        .await
        .unwrap_or_default();

    let pub_rows: Vec<&MemoryRecord> = pool
        .iter()
        .filter(|r| r.key.starts_with("pub_") && r.status == "active")
        .collect();
    let pub_provenance: HashSet<String> = pub_rows
        .iter()
        .flat_map(|r| r.related_keys.iter().cloned())
        .filter(|k| !k.starts_with("pub_"))
        .collect();

    // Drafted-once = never re-drafted (regardless of review outcome): the
    // draft row itself is the LLM-call receipt. Union with provenance for
    // the picker's exclusion set.
    let mut exclusion = pub_provenance.clone();
    exclusion.extend(drafted_source_keys(&draft_rows));

    let corpus_index = pub_rows
        .iter()
        .map(|r| corpus_index_line(r))
        .collect::<Vec<_>>()
        .join("\n");
    println!(
        "pool: {} rows / pub corpus: {} rows / prior drafts: {}",
        pool.len(),
        pub_rows.len(),
        draft_rows.len()
    );

    let candidates = crate::mcp_tools::pick_distillation_candidates(pool, &exclusion, top_n);
    if candidates.is_empty() {
        println!("(queue dry — no verified, undistilled, undrafted candidates)");
        return Ok(());
    }
    println!("picked {} candidate(s):", candidates.len());
    for c in &candidates {
        println!("  - {} [{}]", c.key, c.kind);
    }
    if dry_run {
        println!("(dry-run — skipping claude -p and all writes)");
        return Ok(());
    }

    let batch_tag = today_batch_tag();
    let mut ok = 0usize;
    let mut failed = 0usize;
    for cand in &candidates {
        let prompt = build_prompt(&corpus_index, &candidate_json(cand));
        let started = SystemTime::now();
        let out = call_claude(&prompt, timeout_secs).await;
        let secs = started.elapsed().map(|d| d.as_secs_f64()).unwrap_or(0.0);
        let verdict = match out.and_then(|stdout| parse_verdict(&stdout)) {
            Ok(v) => v,
            Err(e) => {
                // No draft row on failure — the candidate stays in the queue
                // and the next nightly run retries it.
                eprintln!("  {} FAILED after {:.1}s: {e}", cand.key, secs);
                failed += 1;
                continue;
            }
        };
        let rec = build_draft_record(cand, &verdict, &batch_tag, secs);
        let draft_key = rec.key.clone();
        store
            .memory_save(&rec)
            .await
            .map_err(|e| anyhow::anyhow!("memory_save {draft_key}: {e}"))?;
        // Best-effort provenance edge; the related_keys list is the source
        // of truth, the edge just makes graph browsing nicer.
        if let Err(e) = store
            .memory_link(&draft_key, &cand.key, "derived_from", 1.0)
            .await
        {
            eprintln!("  edge {draft_key}→{}: {e}", cand.key);
        }
        println!(
            "  {} → {} [{}{}] ({secs:.1}s)",
            cand.key,
            draft_key,
            verdict.verdict,
            verdict
                .existing_key
                .as_deref()
                .map(|k| format!(" → {k}"))
                .unwrap_or_default(),
        );
        ok += 1;
    }
    println!("done: {ok} draft(s) written, {failed} failed (failed candidates stay queued)");
    Ok(())
}

/// Spawn `claude -p <prompt>` (the pilot's exact channel — zero API key,
/// default model) and return stdout. `AGENT_BRIDGE_CLAUDE_BIN` overrides the
/// binary, matching the agent-runtime convention.
async fn call_claude(prompt: &str, timeout_secs: u64) -> Result<String> {
    let bin = std::env::var("AGENT_BRIDGE_CLAUDE_BIN").unwrap_or_else(|_| "claude".into());
    let mut cmd = tokio::process::Command::new(&bin);
    cmd.arg("-p").arg(prompt);
    cmd.stdin(std::process::Stdio::null());
    cmd.stdout(std::process::Stdio::piped());
    cmd.stderr(std::process::Stdio::piped());
    // A timed-out child must not outlive the batch as an orphan LLM call.
    cmd.kill_on_drop(true);
    let child = cmd.spawn().map_err(|e| anyhow::anyhow!("spawn {bin}: {e}"))?;
    let output = tokio::time::timeout(
        std::time::Duration::from_secs(timeout_secs),
        child.wait_with_output(),
    )
    .await
    .map_err(|_| anyhow::anyhow!("claude -p exceeded {timeout_secs}s timeout"))?
    .map_err(|e| anyhow::anyhow!("wait {bin}: {e}"))?;
    if !output.status.success() {
        let stderr = String::from_utf8_lossy(&output.stderr);
        return Err(anyhow::anyhow!(
            "claude -p exit {}: {}",
            output.status,
            stderr.chars().take(500).collect::<String>()
        ));
    }
    Ok(String::from_utf8_lossy(&output.stdout).into_owned())
}

/// Strip an optional markdown code fence (the pilot saw `claude -p` wrap
/// JSON in ```json fences intermittently) and return the inner text.
fn strip_fences(raw: &str) -> &str {
    let raw = raw.trim();
    if !raw.starts_with("```") {
        return raw;
    }
    let body = raw.split_once('\n').map(|(_, rest)| rest).unwrap_or("");
    body.rsplit_once("```").map(|(inner, _)| inner).unwrap_or(body).trim()
}

/// Parse + validate one `claude -p` output into a `DistillVerdict`.
/// Validation is the propose-only contract's first line of defense: a
/// malformed verdict never becomes a queue row.
pub fn parse_verdict(stdout: &str) -> Result<DistillVerdict> {
    let raw = strip_fences(stdout);
    let v: serde_json::Value =
        serde_json::from_str(raw).map_err(|e| anyhow::anyhow!("bad JSON: {e}"))?;
    let verdict = v["verdict"]
        .as_str()
        .ok_or_else(|| anyhow::anyhow!("missing verdict"))?
        .to_string();
    if !matches!(verdict.as_str(), "distill" | "merge" | "reject") {
        return Err(anyhow::anyhow!("unknown verdict `{verdict}`"));
    }
    let reasoning = v["reasoning"].as_str().unwrap_or("").to_string();
    let existing_key = v["existing_key"].as_str().map(|s| s.to_string());
    let draft = match v.get("draft") {
        Some(serde_json::Value::Object(d)) => Some(parse_proposed_row(d)?),
        _ => None,
    };
    match verdict.as_str() {
        "distill" => {
            let d = draft
                .as_ref()
                .ok_or_else(|| anyhow::anyhow!("distill verdict without draft"))?;
            if !d.key.starts_with("pub_") {
                return Err(anyhow::anyhow!("draft key `{}` must start with pub_", d.key));
            }
            if d.content.trim().is_empty() {
                return Err(anyhow::anyhow!("distill draft has empty content"));
            }
        }
        "merge" => {
            let k = existing_key
                .as_deref()
                .ok_or_else(|| anyhow::anyhow!("merge verdict without existing_key"))?;
            if !k.starts_with("pub_") {
                return Err(anyhow::anyhow!("merge existing_key `{k}` must start with pub_"));
            }
        }
        _ => {}
    }
    Ok(DistillVerdict {
        verdict,
        reasoning,
        existing_key,
        draft,
        raw_json: raw.to_string(),
    })
}

fn parse_proposed_row(d: &serde_json::Map<String, serde_json::Value>) -> Result<ProposedPubRow> {
    let key = d
        .get("key")
        .and_then(|x| x.as_str())
        .ok_or_else(|| anyhow::anyhow!("draft missing key"))?
        .to_string();
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
    Ok(ProposedPubRow {
        key,
        scope: d.get("scope").and_then(|x| x.as_str()).map(|s| s.to_string()),
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
        related_keys: str_vec("related_keys"),
    })
}

/// Assemble the full prompt for one candidate from the versioned template.
pub fn build_prompt(corpus_index: &str, candidate_json: &str) -> String {
    PROMPT_TEMPLATE
        .replace("{CORPUS_INDEX}", corpus_index)
        .replace("{FEWSHOT_SOURCE}", FEWSHOT_SOURCE)
        .replace("{FEWSHOT_OUTPUT}", FEWSHOT_OUTPUT)
        .replace("{CANDIDATE}", candidate_json)
}

/// One pub_* row → one corpus-index line, pilot format:
/// `- <key> | trigger: <trigger> | head: <first 200 chars, newlines flattened>`.
pub fn corpus_index_line(r: &MemoryRecord) -> String {
    let trigger = r
        .tags
        .iter()
        .find_map(|t| t.strip_prefix("continuity_retrieval_trigger:"))
        .unwrap_or("-");
    let head: String = r.content.replace('\n', " ").chars().take(200).collect();
    format!("- {} | trigger: {} | head: {}", r.key, trigger, head)
}

/// Serialize a candidate in the pilot's shape: `tags` is a JSON-encoded
/// string (sqlite column form), matching what the validated prompt saw.
pub fn candidate_json(r: &MemoryRecord) -> String {
    serde_json::to_string_pretty(&serde_json::json!({
        "key": r.key,
        "kind": r.kind,
        "scope": r.scope,
        "tags": serde_json::to_string(&r.tags).unwrap_or_default(),
        "content": r.content,
    }))
    .unwrap_or_default()
}

/// Source keys already covered by any draft row — drafted-once semantics.
/// The non-pub filter drops merge targets (`existing_key` also lives in
/// `related_keys`) so only true sources count.
pub fn drafted_source_keys(draft_rows: &[MemoryRecord]) -> HashSet<String> {
    draft_rows
        .iter()
        .filter(|r| r.kind == DRAFT_KIND)
        .flat_map(|r| r.related_keys.iter())
        .filter(|k| !k.starts_with("pub_"))
        .cloned()
        .collect()
}

/// The source (candidate) key a draft row was distilled from.
pub fn draft_source_key(draft: &MemoryRecord) -> Option<&str> {
    draft
        .related_keys
        .iter()
        .find(|k| !k.starts_with("pub_"))
        .map(|s| s.as_str())
}

/// Self-cleaning pending filter for the review surface. See module docs for
/// the three exit conditions. `sources_distill_no` = candidate keys whose
/// source row carries `distill:no`.
pub fn pending_distill_drafts(
    draft_rows: Vec<MemoryRecord>,
    pub_provenance: &HashSet<String>,
    sources_distill_no: &HashSet<String>,
) -> Vec<MemoryRecord> {
    let mut out: Vec<MemoryRecord> = draft_rows
        .into_iter()
        .filter(|r| r.kind == DRAFT_KIND && r.status == "active")
        .filter(|r| !r.tags.iter().any(|t| t.starts_with("resolved:")))
        .filter(|r| match draft_source_key(r) {
            Some(src) => !pub_provenance.contains(src) && !sources_distill_no.contains(src),
            // A draft with no source key is malformed — keep it visible so
            // it gets looked at rather than silently orbiting forever.
            None => true,
        })
        .collect();
    out.sort_by(|a, b| b.created_at.cmp(&a.created_at).then(a.key.cmp(&b.key)));
    out
}

/// Build the queue row for one verdict. The row is the review packet: header
/// with verdict + suggested review action, then the model's raw JSON.
pub fn build_draft_record(
    candidate: &MemoryRecord,
    v: &DistillVerdict,
    batch_tag: &str,
    secs: f64,
) -> MemoryRecord {
    let mut tags = vec![
        DRAFT_KIND.to_string(),
        format!("verdict:{}", v.verdict),
        format!("distill_prompt:{PROMPT_VERSION}"),
        batch_tag.to_string(),
    ];
    if let Some(d) = &v.draft {
        tags.push(format!("proposes:{}", d.key));
    }
    if let Some(k) = &v.existing_key {
        tags.push(format!("merge_into:{k}"));
    }
    let mut related_keys = vec![candidate.key.clone()];
    if let Some(k) = &v.existing_key {
        related_keys.push(k.clone());
    }
    let action = match v.verdict.as_str() {
        "distill" => "审草稿 → 通过则 memory_save 该 pub_ 行（related_keys 必须含源行 key，即出处反连接）",
        "merge" => "把源行 key 并入 existing pub 行的 related_keys（+按 reasoning 酌情并增量内容）",
        _ => "认可 reject 则给源行加 tag distill:no",
    };
    let content = format!(
        "# 蒸馏草稿（propose-only — 评审通过前不是公共行）\n\n\
         - 源行: {} [{}]\n\
         - 裁决: {}{}\n\
         - 理由: {}\n\
         - prompt: {PROMPT_VERSION} · claude -p 默认模型 · {secs:.1}s · {batch_tag}\n\n\
         ## 评审动作\n{action}\n（执行后本草稿自动出队；仅想否决候选请打 distill:no，删除草稿行会让候选重新排队）\n\n\
         ## 模型原始产出\n```json\n{}\n```\n",
        candidate.key,
        candidate.kind,
        v.verdict,
        v.existing_key
            .as_deref()
            .map(|k| format!(" → {k}"))
            .unwrap_or_default(),
        if v.reasoning.is_empty() { "-" } else { &v.reasoning },
        v.raw_json,
    );
    MemoryRecord {
        key: format!("{DRAFT_KEY_PREFIX}{}", candidate.key),
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

fn today_batch_tag() -> String {
    let now = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map(|d| d.as_secs() as i64)
        .unwrap_or(0);
    batch_tag_from_unix(now)
}

/// `batch:YYYY-MM-DD` (UTC civil date, Hinnant's algorithm — same math as
/// `dream_replay::ymd_from_unix`). Split out so the conversion is testable
/// against a known timestamp.
fn batch_tag_from_unix(secs: i64) -> String {
    let days = secs.div_euclid(86_400);
    let z = days + 719_468;
    let era = z.div_euclid(146_097);
    let doe = (z - era * 146_097) as u64;
    let yoe = (doe - doe / 1_460 + doe / 36_524 - doe / 146_096) / 365;
    let y = yoe as i64 + era * 400;
    let doy = doe - (365 * yoe + yoe / 4 - yoe / 100);
    let mp = (5 * doy + 2) / 153;
    let d = doy - (153 * mp + 2) / 5 + 1;
    let m = if mp < 10 { mp + 3 } else { mp - 9 };
    let y = if m <= 2 { y + 1 } else { y };
    format!("batch:{:04}-{:02}-{:02}", y, m, d)
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

    // ── parse_verdict: the propose-only contract's validation gate ──

    #[test]
    fn parse_distill_with_fences_and_full_draft() {
        let out = r##"```json
{"verdict":"distill","reasoning":"真机制","existing_key":null,
 "draft":{"key":"pub_x","scope":"domain:devops","content":"# 标题\n正文…弯路勿走：x",
          "tags":["zone:public","derived:distilled"],"retrieval_trigger":"a / b",
          "related_keys":["src_row"]}}
```"##;
        let v = parse_verdict(out).unwrap();
        assert_eq!(v.verdict, "distill");
        let d = v.draft.unwrap();
        assert_eq!(d.key, "pub_x");
        assert_eq!(d.scope.as_deref(), Some("domain:devops"));
        assert_eq!(d.tags, vec!["zone:public", "derived:distilled"]);
        assert_eq!(d.related_keys, vec!["src_row"]);
    }

    #[test]
    fn parse_rejects_malformed_shapes() {
        // distill without draft
        assert!(parse_verdict(r#"{"verdict":"distill","reasoning":"x","draft":null}"#).is_err());
        // distill whose draft key is not pub_-prefixed
        assert!(parse_verdict(
            r#"{"verdict":"distill","draft":{"key":"x","content":"c"}}"#
        )
        .is_err());
        // merge without existing_key
        assert!(parse_verdict(r#"{"verdict":"merge","reasoning":"x"}"#).is_err());
        // unknown verdict
        assert!(parse_verdict(r#"{"verdict":"maybe"}"#).is_err());
        // non-JSON
        assert!(parse_verdict("I think this is a great mechanism!").is_err());
    }

    #[test]
    fn parse_merge_and_reject_minimal_forms() {
        let m = parse_verdict(
            r#"{"verdict":"merge","reasoning":"同机制","existing_key":"pub_y","draft":null}"#,
        )
        .unwrap();
        assert_eq!(m.existing_key.as_deref(), Some("pub_y"));
        let r = parse_verdict(r#"{"verdict":"reject","reasoning":"交付记录"}"#).unwrap();
        assert!(r.draft.is_none());
    }

    // ── draft record shape ──

    #[test]
    fn draft_record_distill_shape() {
        let cand = rec("lesson_a_20260707", "lesson", &[], &[]);
        let v = DistillVerdict {
            verdict: "distill".into(),
            reasoning: "why".into(),
            existing_key: None,
            draft: Some(ProposedPubRow {
                key: "pub_new".into(),
                scope: Some("domain:testing".into()),
                content: "c".into(),
                tags: vec![],
                retrieval_trigger: String::new(),
                related_keys: vec!["lesson_a_20260707".into()],
            }),
            raw_json: "{}".into(),
        };
        let r = build_draft_record(&cand, &v, "batch:2026-07-07", 61.5);
        assert_eq!(r.key, "distill_draft_lesson_a_20260707");
        assert_eq!(r.kind, DRAFT_KIND);
        assert_eq!(r.related_keys, vec!["lesson_a_20260707"]);
        for t in [
            "distill_draft",
            "verdict:distill",
            "distill_prompt:v1",
            "batch:2026-07-07",
            "proposes:pub_new",
        ] {
            assert!(r.tags.iter().any(|x| x == t), "missing tag {t}: {:?}", r.tags);
        }
        assert!(r.content.contains("propose-only"));
        assert!(r.content.contains("lesson_a_20260707"));
    }

    #[test]
    fn draft_record_merge_links_existing_pub_row() {
        let cand = rec("outcome_b_20260707", "outcome", &[], &[]);
        let v = DistillVerdict {
            verdict: "merge".into(),
            reasoning: "同机制".into(),
            existing_key: Some("pub_old".into()),
            draft: None,
            raw_json: "{}".into(),
        };
        let r = build_draft_record(&cand, &v, "batch:2026-07-07", 30.0);
        assert_eq!(r.related_keys, vec!["outcome_b_20260707", "pub_old"]);
        assert!(r.tags.iter().any(|t| t == "merge_into:pub_old"));
        assert!(r.tags.iter().any(|t| t == "verdict:merge"));
    }

    // ── queue semantics ──

    #[test]
    fn drafted_sources_exclude_merge_targets() {
        let rows = vec![
            rec("distill_draft_src1", DRAFT_KIND, &[], &["src1"]),
            rec("distill_draft_src2", DRAFT_KIND, &[], &["src2", "pub_old"]),
            rec("unrelated", "lesson", &[], &["src3"]),
        ];
        let s = drafted_source_keys(&rows);
        assert!(s.contains("src1") && s.contains("src2"));
        assert!(!s.contains("pub_old"), "merge target is not a source");
        assert!(!s.contains("src3"), "non-draft rows don't count");
    }

    #[test]
    fn pending_filter_three_exit_conditions() {
        let rows = vec![
            rec("distill_draft_a", DRAFT_KIND, &[], &["a"]), // stays
            rec("distill_draft_b", DRAFT_KIND, &[], &["b"]), // provenance → out
            rec("distill_draft_c", DRAFT_KIND, &[], &["c"]), // distill:no → out
            rec(
                "distill_draft_d",
                DRAFT_KIND,
                &["resolved:dismissed"],
                &["d"],
            ), // manual resolve → out
        ];
        let provenance: HashSet<String> = ["b".to_string()].into();
        let no: HashSet<String> = ["c".to_string()].into();
        let pending = pending_distill_drafts(rows, &provenance, &no);
        assert_eq!(
            pending.iter().map(|r| r.key.as_str()).collect::<Vec<_>>(),
            vec!["distill_draft_a"]
        );
    }

    #[test]
    fn pending_filter_drops_inactive_and_keeps_malformed_visible() {
        let mut archived = rec("distill_draft_a", DRAFT_KIND, &[], &["a"]);
        archived.status = "archived".into();
        let orphan = rec("distill_draft_weird", DRAFT_KIND, &[], &[]);
        let pending =
            pending_distill_drafts(vec![archived, orphan], &HashSet::new(), &HashSet::new());
        assert_eq!(
            pending.iter().map(|r| r.key.as_str()).collect::<Vec<_>>(),
            vec!["distill_draft_weird"],
            "archived exits; source-less draft stays visible for inspection"
        );
    }

    // ── prompt assembly ──

    #[test]
    fn prompt_replaces_all_placeholders() {
        let p = build_prompt("- pub_a | trigger: t | head: h", "{\"key\":\"cand\"}");
        for leftover in ["{CORPUS_INDEX}", "{FEWSHOT_SOURCE}", "{FEWSHOT_OUTPUT}", "{CANDIDATE}"] {
            assert!(!p.contains(leftover), "unreplaced {leftover}");
        }
        assert!(p.contains("- pub_a | trigger: t | head: h"));
        assert!(p.contains("{\"key\":\"cand\"}"));
        // the four hard disciplines travelled with the template
        assert!(p.contains("同义反复检查"));
        assert!(p.contains("弯路勿走"));
    }

    #[test]
    fn corpus_line_flattens_newlines_and_caps_cjk_safely() {
        let mut r = rec("pub_z", "lesson", &["continuity_retrieval_trigger:a / b"], &[]);
        r.content = format!("# 标题\n\n{}", "机".repeat(500));
        let line = corpus_index_line(&r);
        assert!(line.starts_with("- pub_z | trigger: a / b | head: # 标题  机"));
        assert!(!line.contains('\n'));
        // cap is chars, not bytes — must not panic mid-codepoint and must trim
        assert!(line.chars().count() < 240);
    }

    #[test]
    fn candidate_json_uses_sqlite_column_shape() {
        let r = rec("k", "lesson", &["t1", "t2"], &[]);
        let j: serde_json::Value = serde_json::from_str(&candidate_json(&r)).unwrap();
        // tags is a JSON-ENCODED STRING (what the validated pilot prompt saw),
        // not a nested array
        assert_eq!(j["tags"].as_str().unwrap(), r#"["t1","t2"]"#);
        assert_eq!(j["key"], "k");
    }

    #[test]
    fn batch_tag_civil_conversion() {
        assert_eq!(batch_tag_from_unix(0), "batch:1970-01-01");
        // live timestamp from the day this shipped (2026-07-07 ~15:48 UTC)
        assert_eq!(batch_tag_from_unix(1_783_439_296), "batch:2026-07-07");
        // leap day
        assert_eq!(batch_tag_from_unix(1_709_164_800), "batch:2024-02-29");
    }

    #[test]
    fn fence_stripping_variants() {
        assert_eq!(strip_fences("{\"a\":1}"), "{\"a\":1}");
        assert_eq!(strip_fences("```json\n{\"a\":1}\n```"), "{\"a\":1}");
        assert_eq!(strip_fences("```\n{\"a\":1}\n```"), "{\"a\":1}");
        assert_eq!(strip_fences("  ```json\n{\"a\":1}\n```  "), "{\"a\":1}");
    }
}
