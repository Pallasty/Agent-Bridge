use std::collections::{BTreeMap, HashMap};
use std::io::Write;
use std::path::{Path, PathBuf};
use std::time::{SystemTime, UNIX_EPOCH};

use serde::{Deserialize, Serialize};
use serde_json::{json, Value};

pub const OBSERVER_MAX_BYTES: u64 = 8 * 1024 * 1024;
const MIN_SESSIONS: usize = 5;
const MINEABLE_MEAN_GATE: f64 = 1.0;

const CORRECTION_CUES: &[&str] = &[
    "不对",
    "不是",
    "错了",
    "错误",
    "应该",
    "而不是",
    "别这样",
    "不要",
    "其实",
    "重来",
    "撤销",
    "回退",
    "改成",
    "不行",
    "有问题",
    "搞错",
    "弄反",
    "no,",
    "not quite",
    "that's not",
    "that is not",
    "wrong",
    "actually",
    "instead",
    "should be",
    "should not",
    "shouldn't",
    "don't",
    "do not",
    "revert",
    "undo",
    "rollback",
    "mistake",
    "incorrect",
    "fix that",
    "no.",
];

#[derive(Debug, Clone, Deserialize)]
struct ObservationRecord {
    ts: Option<f64>,
    sid: Option<String>,
    ev: Option<String>,
    prompt: Option<String>,
    tool: Option<String>,
    err: Option<bool>,
    err_source: Option<Value>,
    stderr_nonempty: Option<bool>,
    #[serde(rename = "in")]
    input_brief: Option<String>,
    #[serde(rename = "out")]
    output_brief: Option<String>,
}

#[derive(Debug, Clone, Default, Serialize, PartialEq, Eq)]
pub struct SessionSignalSummary {
    pub prompts: u64,
    pub corrections: u64,
    pub tools: u64,
    pub clean_errors: u64,
    pub clean_error_resolutions: u64,
    pub stderr_success: u64,
    pub legacy_untrusted_errors: u64,
    pub legacy_error_resolutions: u64,
    pub clean_mineable: u64,
    pub legacy_upper_bound_mineable: u64,
}

#[derive(Debug, Clone, Serialize, PartialEq)]
pub struct InstinctObserverStatus {
    pub enabled: bool,
    pub installed_path: String,
    pub installed: bool,
    pub executable: bool,
    pub log_path: String,
    pub log_dir_path: String,
    pub log_present: bool,
    pub log_dir_mode_octal: Option<String>,
    pub log_mode_octal: Option<String>,
    pub permissions_ok: bool,
    pub log_bytes: u64,
    pub max_bytes: u64,
    pub total_records: u64,
    pub sessions: usize,
    pub events: BTreeMap<String, u64>,
    pub top_tools: Vec<(String, u64)>,
    pub latest_event_at_unix: Option<f64>,
    pub latest_event_age_secs: Option<u64>,
    pub total_clean_mineable: u64,
    pub mean_clean_mineable_per_session: f64,
    pub total_legacy_upper_bound_mineable: u64,
    pub mean_legacy_upper_bound_per_session: f64,
    pub legacy_untrusted_errors: u64,
    pub stderr_success_records: u64,
    pub gate: String,
    pub verdict: String,
    pub legacy_upper_bound_verdict: String,
    pub recommendation: String,
    pub per_session: BTreeMap<String, SessionSignalSummary>,
}

#[derive(Debug, Clone, Default)]
struct SessionWorking {
    summary: SessionSignalSummary,
    clean_pending: HashMap<String, u64>,
    legacy_pending: HashMap<String, u64>,
}

pub fn default_observer_log_path() -> PathBuf {
    if let Some(path) = std::env::var_os("AB_INSTINCT_OBSERVER_LOG") {
        return PathBuf::from(path);
    }
    if Path::new("/Data").is_dir() {
        return PathBuf::from("/Data/agent-bridge/instinct-probe/observations.jsonl");
    }
    home_dir()
        .join(".cache")
        .join("agent-bridge")
        .join("instinct-probe")
        .join("observations.jsonl")
}

pub fn installed_observer_hook_path() -> PathBuf {
    home_dir()
        .join(".local")
        .join("bin")
        .join("ab-instinct-observer-hook")
}

fn home_dir() -> PathBuf {
    std::env::var("HOME")
        .map(PathBuf::from)
        .unwrap_or_else(|_| PathBuf::from("/tmp"))
}

pub fn observer_status() -> InstinctObserverStatus {
    observer_status_for_paths(
        installed_observer_hook_path(),
        default_observer_log_path(),
        std::env::var("AB_INSTINCT_OBSERVER").unwrap_or_else(|_| "1".to_string()) != "0",
    )
}

pub fn observer_status_json() -> Value {
    serde_json::to_value(observer_status()).unwrap_or_else(|e| {
        json!({
            "enabled": std::env::var("AB_INSTINCT_OBSERVER").unwrap_or_else(|_| "1".to_string()) != "0",
            "error": e.to_string()
        })
    })
}

pub fn observer_candidate_preview(limit: usize) -> Value {
    observer_candidate_preview_for_path(&default_observer_log_path(), limit)
}

pub fn default_review_dir_path() -> PathBuf {
    if let Some(path) = std::env::var_os("AB_INSTINCT_REVIEW_DIR") {
        return PathBuf::from(path);
    }
    if Path::new("/Data").is_dir() {
        return PathBuf::from("/Data/agent-bridge/instinct-review");
    }
    home_dir()
        .join(".cache")
        .join("agent-bridge")
        .join("instinct-review")
}

pub fn default_review_decisions_path() -> PathBuf {
    if let Some(path) = std::env::var_os("AB_INSTINCT_REVIEW_DECISIONS") {
        return PathBuf::from(path);
    }
    default_review_dir_path().join("decisions.jsonl")
}

pub fn default_memory_write_receipts_path() -> PathBuf {
    if let Some(path) = std::env::var_os("AB_INSTINCT_MEMORY_WRITE_RECEIPTS") {
        return PathBuf::from(path);
    }
    default_review_dir_path().join("memory-writes.jsonl")
}

pub fn observer_candidate_preview_for_path(log_path: &Path, limit: usize) -> Value {
    let records = load_records(log_path);
    let analyzed = analyze_records(&records);
    let summary = summarize(&records, analyzed);
    let verdict = verdict_for(
        summary.mean_clean_mineable_per_session,
        summary.per_session.len(),
    );
    let candidates = extract_candidate_preview(&records, limit);
    let candidate_count = candidates.len();

    json!({
        "schema": "agent_bridge.instinct_observer.phase1_candidate_preview.v0",
        "read_only": true,
        "phase": "phase1_candidate_preview",
        "status": if candidate_count > 0 { "candidates_available" } else { "no_candidates" },
        "log_path": log_path.display().to_string(),
        "limit": limit,
        "candidate_count": candidate_count,
        "density_gate": {
            "verdict": verdict,
            "gate": format!("mean>={MINEABLE_MEAN_GATE:.1} over >={MIN_SESSIONS} sessions"),
            "sessions": summary.per_session.len(),
            "total_clean_mineable": summary.total_clean_mineable,
            "mean_clean_mineable_per_session": summary.mean_clean_mineable_per_session,
        },
        "boundary_check": {
            "writes_memory": false,
            "writes_files": false,
            "persists_review_queue": false,
            "auto_apply_allowed": false,
            "human_review_required": true,
            "raw_prompt_included": false,
            "raw_tool_input_included": false,
            "raw_tool_output_included": false,
            "candidate_previews_are_redacted": true,
        },
        "recommended_next_step": if candidate_count > 0 {
            "human_review_candidates_before_any_memory_write"
        } else {
            "wait_for_more_observations"
        },
        "candidates": candidates,
    })
}

pub fn observer_review_packet(
    limit: usize,
    reviewer: Option<&str>,
    out_dir: Option<&Path>,
    write: bool,
) -> std::io::Result<Value> {
    let now_unix = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map(|d| d.as_secs())
        .unwrap_or(0);
    observer_review_packet_for_paths(
        &default_observer_log_path(),
        out_dir.unwrap_or(&default_review_dir_path()),
        limit,
        reviewer,
        now_unix,
        write,
    )
}

pub fn observer_review_packet_for_paths(
    log_path: &Path,
    out_dir: &Path,
    limit: usize,
    reviewer: Option<&str>,
    now_unix: u64,
    write: bool,
) -> std::io::Result<Value> {
    let preview = observer_candidate_preview_for_path(log_path, limit);
    let candidate_count = preview
        .get("candidate_count")
        .and_then(|v| v.as_u64())
        .unwrap_or(0);
    let packet_id = format!("instinct-review-{now_unix}");
    let json_path = out_dir.join(format!("{packet_id}.json"));
    let markdown_path = out_dir.join(format!("{packet_id}.md"));
    let status = if write {
        if candidate_count > 0 {
            "written"
        } else {
            "written_no_candidates"
        }
    } else if candidate_count > 0 {
        "preview_only"
    } else {
        "preview_no_candidates"
    };

    let mut packet = json!({
        "schema": "agent_bridge.instinct_observer.phase1_review_packet.v0",
        "packet_id": packet_id,
        "generated_at_unix": now_unix,
        "phase": "phase1_human_review_packet",
        "status": status,
        "dry_run": !write,
        "reviewer": reviewer,
        "review_dir": out_dir.display().to_string(),
        "json_path": json_path.display().to_string(),
        "markdown_path": markdown_path.display().to_string(),
        "source_log_path": log_path.display().to_string(),
        "candidate_count": candidate_count,
        "writes_files": write,
        "writes_memory": false,
        "persists_review_queue": false,
        "auto_apply_allowed": false,
        "human_review_required": true,
        "raw_prompt_included": false,
        "raw_tool_input_included": false,
        "raw_tool_output_included": false,
        "human_review_checklist": [
            "Open the Markdown packet and inspect each candidate id.",
            "Use the local observer log only when more context is needed.",
            "Approve only lessons that are stable, non-secret, and reusable.",
            "Reject or defer ambiguous candidates.",
            "Run a separate explicit command before any memory write."
        ],
        "allowed_review_actions": [
            "approve_candidate_for_future_explicit_memory_write",
            "reject_candidate",
            "defer_candidate_pending_more_context"
        ],
        "blocked_actions": [
            "auto_write_memory",
            "auto_apply_without_human_review",
            "include_raw_prompt_or_tool_payload",
            "treat_packet_as_approval_queue"
        ],
        "recommended_next_step": if candidate_count > 0 {
            "review_markdown_packet_before_any_memory_write"
        } else {
            "wait_for_more_observations"
        },
        "candidate_preview": preview,
    });

    if write {
        std::fs::create_dir_all(out_dir)?;
        set_private_dir_permissions(out_dir)?;
        packet["written"] = json!(true);
        let markdown = render_review_packet_markdown(&packet);
        let body = serde_json::to_string_pretty(&packet)
            .map_err(|e| std::io::Error::new(std::io::ErrorKind::InvalidData, e))?;
        write_private_file(&json_path, body.as_bytes())?;
        write_private_file(&markdown_path, markdown.as_bytes())?;
    } else {
        packet["written"] = json!(false);
    }

    Ok(packet)
}

pub fn observer_review_decision(
    packet_json: &Path,
    candidate_id: &str,
    decision: &str,
    reviewer: Option<&str>,
    note: Option<&str>,
    out_path: Option<&Path>,
    write: bool,
) -> std::io::Result<Value> {
    let now_unix = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map(|d| d.as_secs())
        .unwrap_or(0);
    observer_review_decision_for_paths(
        packet_json,
        out_path.unwrap_or(&default_review_decisions_path()),
        candidate_id,
        decision,
        reviewer,
        note,
        now_unix,
        write,
    )
}

pub fn observer_review_decision_for_paths(
    packet_json: &Path,
    decisions_path: &Path,
    candidate_id: &str,
    decision: &str,
    reviewer: Option<&str>,
    note: Option<&str>,
    now_unix: u64,
    write: bool,
) -> std::io::Result<Value> {
    let decision = normalize_review_decision(decision)?;
    let body = std::fs::read_to_string(packet_json)?;
    let packet: Value = serde_json::from_str(&body)
        .map_err(|e| std::io::Error::new(std::io::ErrorKind::InvalidData, e))?;
    let packet_schema = packet.get("schema").and_then(|v| v.as_str()).unwrap_or("");
    if packet_schema != "agent_bridge.instinct_observer.phase1_review_packet.v0" {
        return Err(std::io::Error::new(
            std::io::ErrorKind::InvalidInput,
            "packet_json is not an instinct phase1 review packet",
        ));
    }
    let candidate = packet
        .pointer("/candidate_preview/candidates")
        .and_then(|v| v.as_array())
        .and_then(|items| {
            items.iter().find(|candidate| {
                candidate.get("candidate_id").and_then(|v| v.as_str()) == Some(candidate_id)
            })
        })
        .ok_or_else(|| {
            std::io::Error::new(
                std::io::ErrorKind::NotFound,
                format!("candidate not found in review packet: {candidate_id}"),
            )
        })?;

    let decision_id = format!("instinct-decision-{now_unix}-{candidate_id}");
    let mut record = json!({
        "schema": "agent_bridge.instinct_observer.phase1_review_decision.v0",
        "decision_id": decision_id,
        "generated_at_unix": now_unix,
        "dry_run": !write,
        "status": if write { "recorded" } else { "preview_only" },
        "review_packet_id": packet.get("packet_id").cloned().unwrap_or(Value::Null),
        "review_packet_path": packet_json.display().to_string(),
        "candidate_id": candidate_id,
        "candidate_kind": candidate.get("kind").cloned().unwrap_or(Value::Null),
        "candidate_session_id": candidate.get("session_id").cloned().unwrap_or(Value::Null),
        "decision": decision,
        "reviewer": reviewer,
        "note": note,
        "decisions_path": decisions_path.display().to_string(),
        "writes_decision_log": write,
        "writes_memory": false,
        "persists_review_queue": false,
        "auto_apply_allowed": false,
        "raw_prompt_included": false,
        "raw_tool_input_included": false,
        "raw_tool_output_included": false,
        "candidate_can_enter_future_explicit_memory_write_preflight": decision == "approve",
        "memory_write_requires_separate_command": true,
        "recommended_next_step": if decision == "approve" {
            "run_separate_memory_write_preflight_for_approved_candidate"
        } else {
            "continue_reviewing_remaining_candidates"
        },
    });

    if write {
        if let Some(parent) = decisions_path.parent() {
            std::fs::create_dir_all(parent)?;
            set_private_dir_permissions(parent)?;
        }
        append_private_jsonl(decisions_path, &record)?;
        record["written"] = json!(true);
    } else {
        record["written"] = json!(false);
    }

    Ok(record)
}

pub fn observer_memory_preflight(
    packet_json: &Path,
    decisions_path: Option<&Path>,
    candidate_id: &str,
    memory_key: Option<&str>,
    memory_kind: Option<&str>,
    memory_body: Option<&str>,
    out_dir: Option<&Path>,
    write: bool,
) -> std::io::Result<Value> {
    let now_unix = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map(|d| d.as_secs())
        .unwrap_or(0);
    observer_memory_preflight_for_paths(
        packet_json,
        decisions_path.unwrap_or(&default_review_decisions_path()),
        out_dir.unwrap_or(&default_review_dir_path()),
        candidate_id,
        memory_key,
        memory_kind,
        memory_body,
        now_unix,
        write,
    )
}

pub fn observer_memory_preflight_for_paths(
    packet_json: &Path,
    decisions_path: &Path,
    out_dir: &Path,
    candidate_id: &str,
    memory_key: Option<&str>,
    memory_kind: Option<&str>,
    memory_body: Option<&str>,
    now_unix: u64,
    write: bool,
) -> std::io::Result<Value> {
    let body = std::fs::read_to_string(packet_json)?;
    let packet: Value = serde_json::from_str(&body)
        .map_err(|e| std::io::Error::new(std::io::ErrorKind::InvalidData, e))?;
    ensure_review_packet_schema(&packet)?;
    let candidate = find_candidate(&packet, candidate_id)?;
    let decision = latest_decision_for_candidate(decisions_path, candidate_id)?;
    let decision_status = decision
        .as_ref()
        .and_then(|v| v.get("decision"))
        .and_then(|v| v.as_str())
        .unwrap_or("missing");
    let approved = decision_status == "approve";
    let has_key = memory_key.is_some_and(|s| !s.trim().is_empty());
    let has_kind = memory_kind.is_some_and(|s| !s.trim().is_empty());
    let has_body = memory_body.is_some_and(|s| !s.trim().is_empty());
    let draft_complete = has_key && has_kind && has_body;
    let ready = approved && draft_complete;
    let preflight_id = format!("instinct-memory-preflight-{now_unix}-{candidate_id}");
    let json_path = out_dir.join(format!("{preflight_id}.json"));
    let markdown_path = out_dir.join(format!("{preflight_id}.md"));
    let blocked_reasons = memory_preflight_blocked_reasons(approved, has_key, has_kind, has_body);
    let status = if ready {
        if write {
            "written_ready_for_separate_memory_write"
        } else {
            "ready_for_separate_memory_write"
        }
    } else if write {
        "written_blocked"
    } else {
        "blocked"
    };

    let mut packet_out = json!({
        "schema": "agent_bridge.instinct_observer.phase1_memory_write_preflight.v0",
        "preflight_id": preflight_id,
        "generated_at_unix": now_unix,
        "dry_run": !write,
        "status": status,
        "review_packet_id": packet.get("packet_id").cloned().unwrap_or(Value::Null),
        "review_packet_path": packet_json.display().to_string(),
        "decisions_path": decisions_path.display().to_string(),
        "candidate_id": candidate_id,
        "candidate_kind": candidate.get("kind").cloned().unwrap_or(Value::Null),
        "candidate_session_id": candidate.get("session_id").cloned().unwrap_or(Value::Null),
        "latest_decision": decision.unwrap_or(Value::Null),
        "approved_by_human_decision": approved,
        "draft_complete": draft_complete,
        "ready_for_separate_memory_write": ready,
        "blocked_reasons": blocked_reasons,
        "memory_draft": {
            "key": memory_key,
            "kind": memory_kind,
            "body": memory_body,
            "body_chars": memory_body.map(|s| s.chars().count()).unwrap_or(0),
            "source": "human_supplied_cli_fields"
        },
        "json_path": json_path.display().to_string(),
        "markdown_path": markdown_path.display().to_string(),
        "writes_files": write,
        "writes_memory": false,
        "persists_review_queue": false,
        "auto_apply_allowed": false,
        "raw_prompt_included": false,
        "raw_tool_input_included": false,
        "raw_tool_output_included": false,
        "memory_write_requires_separate_command": true,
        "recommended_next_step": if ready {
            "run_separate_explicit_memory_write_command"
        } else {
            "record_approve_decision_and_supply_memory_draft"
        },
    });

    if write {
        std::fs::create_dir_all(out_dir)?;
        set_private_dir_permissions(out_dir)?;
        packet_out["written"] = json!(true);
        let markdown = render_memory_preflight_markdown(&packet_out);
        let body = serde_json::to_string_pretty(&packet_out)
            .map_err(|e| std::io::Error::new(std::io::ErrorKind::InvalidData, e))?;
        write_private_file(&json_path, body.as_bytes())?;
        write_private_file(&markdown_path, markdown.as_bytes())?;
    } else {
        packet_out["written"] = json!(false);
    }

    Ok(packet_out)
}

pub fn observer_memory_write_plan(preflight_json: &Path, write: bool) -> std::io::Result<Value> {
    let now_unix = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map(|d| d.as_secs())
        .unwrap_or(0);
    observer_memory_write_plan_for_path(preflight_json, now_unix, write)
}

pub fn observer_memory_write_plan_for_path(
    preflight_json: &Path,
    now_unix: u64,
    write: bool,
) -> std::io::Result<Value> {
    let body = std::fs::read_to_string(preflight_json)?;
    let preflight: Value = serde_json::from_str(&body)
        .map_err(|e| std::io::Error::new(std::io::ErrorKind::InvalidData, e))?;
    ensure_memory_preflight_schema(&preflight)?;
    let ready = preflight
        .get("ready_for_separate_memory_write")
        .and_then(|v| v.as_bool())
        .unwrap_or(false);
    let draft = preflight.get("memory_draft").unwrap_or(&Value::Null);
    let key = draft
        .get("key")
        .and_then(|v| v.as_str())
        .map(str::trim)
        .filter(|s| !s.is_empty());
    let kind = draft
        .get("kind")
        .and_then(|v| v.as_str())
        .map(str::trim)
        .filter(|s| !s.is_empty());
    let content = draft
        .get("body")
        .and_then(|v| v.as_str())
        .map(str::trim)
        .filter(|s| !s.is_empty());
    let draft_complete = key.is_some() && kind.is_some() && content.is_some();
    let executable = ready && draft_complete;
    let blocked_reasons =
        memory_write_blocked_reasons(ready, key.is_some(), kind.is_some(), content.is_some());

    Ok(json!({
        "schema": "agent_bridge.instinct_observer.phase1_memory_write_plan.v0",
        "generated_at_unix": now_unix,
        "dry_run": !write,
        "status": if executable {
            if write { "ready_to_write" } else { "preview_ready_to_write" }
        } else {
            "blocked"
        },
        "preflight_json": preflight_json.display().to_string(),
        "preflight_id": preflight.get("preflight_id").cloned().unwrap_or(Value::Null),
        "candidate_id": preflight.get("candidate_id").cloned().unwrap_or(Value::Null),
        "ready_for_separate_memory_write": ready,
        "draft_complete": draft_complete,
        "blocked_reasons": blocked_reasons,
        "writes_memory": write && executable,
        "auto_apply_allowed": false,
        "raw_prompt_included": false,
        "raw_tool_input_included": false,
        "raw_tool_output_included": false,
        "memory_record": if executable {
            json!({
                "key": key.unwrap(),
                "kind": kind.unwrap(),
                "content": content.unwrap(),
                "tags": [
                    "instinct",
                    "human_reviewed",
                    "phase1"
                ],
                "related_keys": [],
                "scope": Value::Null,
                "importance": importance_for_kind(kind.unwrap())
            })
        } else {
            Value::Null
        },
        "recommended_next_step": if executable {
            if write { "memory_save_will_run_now" } else { "rerun_with_write_to_save_memory" }
        } else {
            "fix_preflight_or_memory_draft_before_write"
        },
    }))
}

pub fn observer_memory_write_receipt(
    preflight_json: &Path,
    memory_key: &str,
    db_path: &Path,
    receipt_path: Option<&Path>,
) -> std::io::Result<Value> {
    let now_unix = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map(|d| d.as_secs())
        .unwrap_or(0);
    observer_memory_write_receipt_for_paths(
        preflight_json,
        receipt_path.unwrap_or(&default_memory_write_receipts_path()),
        memory_key,
        db_path,
        now_unix,
    )
}

pub fn observer_memory_write_receipt_for_paths(
    preflight_json: &Path,
    receipts_path: &Path,
    memory_key: &str,
    db_path: &Path,
    now_unix: u64,
) -> std::io::Result<Value> {
    let body = std::fs::read_to_string(preflight_json)?;
    let preflight: Value = serde_json::from_str(&body)
        .map_err(|e| std::io::Error::new(std::io::ErrorKind::InvalidData, e))?;
    ensure_memory_preflight_schema(&preflight)?;
    let expected_key = preflight
        .pointer("/memory_draft/key")
        .and_then(|v| v.as_str())
        .unwrap_or("");
    if expected_key != memory_key {
        return Err(std::io::Error::new(
            std::io::ErrorKind::InvalidInput,
            "memory key does not match preflight draft",
        ));
    }
    let receipt = json!({
        "schema": "agent_bridge.instinct_observer.phase1_memory_write_receipt.v0",
        "receipt_id": format!("instinct-memory-write-{now_unix}-{memory_key}"),
        "generated_at_unix": now_unix,
        "preflight_json": preflight_json.display().to_string(),
        "preflight_id": preflight.get("preflight_id").cloned().unwrap_or(Value::Null),
        "candidate_id": preflight.get("candidate_id").cloned().unwrap_or(Value::Null),
        "memory_key": memory_key,
        "memory_kind": preflight.pointer("/memory_draft/kind").cloned().unwrap_or(Value::Null),
        "db_path": db_path.display().to_string(),
        "receipts_path": receipts_path.display().to_string(),
        "writes_memory": true,
        "raw_prompt_included": false,
        "raw_tool_input_included": false,
        "raw_tool_output_included": false,
    });
    if let Some(parent) = receipts_path.parent() {
        std::fs::create_dir_all(parent)?;
        set_private_dir_permissions(parent)?;
    }
    append_private_jsonl(receipts_path, &receipt)?;
    Ok(receipt)
}

pub fn observer_review_status(
    review_dir: Option<&Path>,
    decisions_path: Option<&Path>,
    receipts_path: Option<&Path>,
    limit: usize,
) -> std::io::Result<Value> {
    observer_review_status_for_paths(
        review_dir.unwrap_or(&default_review_dir_path()),
        decisions_path.unwrap_or(&default_review_decisions_path()),
        receipts_path.unwrap_or(&default_memory_write_receipts_path()),
        limit,
    )
}

pub fn observer_review_status_for_paths(
    review_dir: &Path,
    decisions_path: &Path,
    receipts_path: &Path,
    limit: usize,
) -> std::io::Result<Value> {
    let mut packets = Vec::new();
    let mut preflights = Vec::new();
    let mut parse_errors = Vec::new();
    if review_dir.is_dir() {
        for entry in std::fs::read_dir(review_dir)? {
            let entry = entry?;
            let path = entry.path();
            if path.extension().and_then(|s| s.to_str()) != Some("json") {
                continue;
            }
            match std::fs::read_to_string(&path)
                .ok()
                .and_then(|body| serde_json::from_str::<Value>(&body).ok())
            {
                Some(value) => {
                    let schema = value.get("schema").and_then(|v| v.as_str()).unwrap_or("");
                    let mut compact = json!({
                        "path": path.display().to_string(),
                        "schema": schema,
                        "generated_at_unix": value.get("generated_at_unix").cloned().unwrap_or(Value::Null),
                    });
                    match schema {
                        "agent_bridge.instinct_observer.phase1_review_packet.v0" => {
                            compact["packet_id"] =
                                value.get("packet_id").cloned().unwrap_or(Value::Null);
                            compact["candidate_count"] =
                                value.get("candidate_count").cloned().unwrap_or(Value::Null);
                            compact["written"] =
                                value.get("written").cloned().unwrap_or(Value::Null);
                            packets.push(compact);
                        }
                        "agent_bridge.instinct_observer.phase1_memory_write_preflight.v0" => {
                            compact["preflight_id"] =
                                value.get("preflight_id").cloned().unwrap_or(Value::Null);
                            compact["candidate_id"] =
                                value.get("candidate_id").cloned().unwrap_or(Value::Null);
                            compact["ready_for_separate_memory_write"] = value
                                .get("ready_for_separate_memory_write")
                                .cloned()
                                .unwrap_or(Value::Null);
                            compact["written"] =
                                value.get("written").cloned().unwrap_or(Value::Null);
                            compact["memory_key"] = value
                                .pointer("/memory_draft/key")
                                .cloned()
                                .unwrap_or(Value::Null);
                            preflights.push(compact);
                        }
                        _ => {}
                    }
                }
                None => parse_errors.push(path.display().to_string()),
            }
        }
    }

    sort_generated_desc(&mut packets);
    sort_generated_desc(&mut preflights);
    let decisions = load_review_decisions(decisions_path)?;
    let receipts = load_memory_write_receipts(receipts_path)?;
    let mut decision_counts: BTreeMap<String, u64> = BTreeMap::new();
    for decision in &decisions {
        let key = decision
            .get("decision")
            .and_then(|v| v.as_str())
            .unwrap_or("unknown")
            .to_string();
        *decision_counts.entry(key).or_default() += 1;
    }

    Ok(json!({
        "schema": "agent_bridge.instinct_observer.phase1_review_status.v0",
        "read_only": true,
        "review_dir": review_dir.display().to_string(),
        "decisions_path": decisions_path.display().to_string(),
        "receipts_path": receipts_path.display().to_string(),
        "review_dir_exists": review_dir.is_dir(),
        "decisions_log_exists": decisions_path.is_file(),
        "receipts_log_exists": receipts_path.is_file(),
        "packet_count": packets.len(),
        "decision_count": decisions.len(),
        "preflight_count": preflights.len(),
        "memory_write_receipt_count": receipts.len(),
        "ready_preflight_count": preflights
            .iter()
            .filter(|p| p.get("ready_for_separate_memory_write").and_then(|v| v.as_bool()).unwrap_or(false))
            .count(),
        "decision_counts": decision_counts,
        "parse_error_count": parse_errors.len(),
        "parse_errors": parse_errors,
        "writes_memory": false,
        "auto_apply_allowed": false,
        "latest_packets": packets.into_iter().take(limit).collect::<Vec<_>>(),
        "latest_decisions": decisions.into_iter().rev().take(limit).collect::<Vec<_>>(),
        "latest_memory_write_receipts": receipts.into_iter().rev().take(limit).collect::<Vec<_>>(),
        "latest_preflights": preflights.into_iter().take(limit).collect::<Vec<_>>(),
    }))
}

pub fn observer_review_inbox(
    packet_json: Option<&Path>,
    review_dir: Option<&Path>,
    decisions_path: Option<&Path>,
    limit: usize,
) -> std::io::Result<Value> {
    let default_review_dir = default_review_dir_path();
    let review_dir = review_dir.unwrap_or(&default_review_dir);
    let packet_path = match packet_json {
        Some(path) => path.to_path_buf(),
        None => latest_review_packet_path(review_dir)?.ok_or_else(|| {
            std::io::Error::new(
                std::io::ErrorKind::NotFound,
                "no instinct review packet found",
            )
        })?,
    };
    observer_review_inbox_for_paths(
        &packet_path,
        decisions_path.unwrap_or(&default_review_decisions_path()),
        limit,
    )
}

pub fn observer_review_inbox_for_paths(
    packet_json: &Path,
    decisions_path: &Path,
    limit: usize,
) -> std::io::Result<Value> {
    let body = std::fs::read_to_string(packet_json)?;
    let packet: Value = serde_json::from_str(&body)
        .map_err(|e| std::io::Error::new(std::io::ErrorKind::InvalidData, e))?;
    ensure_review_packet_schema(&packet)?;
    let decisions = load_review_decisions(decisions_path)?;
    let mut latest_by_candidate: BTreeMap<String, Value> = BTreeMap::new();
    for decision in decisions {
        let Some(candidate_id) = decision.get("candidate_id").and_then(|v| v.as_str()) else {
            continue;
        };
        let current_ts = decision
            .get("generated_at_unix")
            .and_then(|v| v.as_u64())
            .unwrap_or(0);
        let existing_ts = latest_by_candidate
            .get(candidate_id)
            .and_then(|v| v.get("generated_at_unix"))
            .and_then(|v| v.as_u64())
            .unwrap_or(0);
        if !latest_by_candidate.contains_key(candidate_id) || current_ts >= existing_ts {
            latest_by_candidate.insert(candidate_id.to_string(), decision);
        }
    }

    let candidates = packet
        .pointer("/candidate_preview/candidates")
        .and_then(|v| v.as_array())
        .cloned()
        .unwrap_or_default();
    let mut rows = Vec::new();
    let mut pending_count = 0_u64;
    let mut approved_count = 0_u64;
    let mut rejected_count = 0_u64;
    let mut deferred_count = 0_u64;
    for candidate in candidates {
        let candidate_id = candidate
            .get("candidate_id")
            .and_then(|v| v.as_str())
            .unwrap_or("")
            .to_string();
        let latest = latest_by_candidate.get(&candidate_id);
        let decision = latest
            .and_then(|v| v.get("decision"))
            .and_then(|v| v.as_str())
            .unwrap_or("pending");
        match decision {
            "approve" => approved_count += 1,
            "reject" => rejected_count += 1,
            "defer" => deferred_count += 1,
            _ => pending_count += 1,
        }
        rows.push(json!({
            "candidate_id": candidate_id,
            "kind": candidate.get("kind").cloned().unwrap_or(Value::Null),
            "session_id": candidate.get("session_id").cloned().unwrap_or(Value::Null),
            "tool": candidate.get("tool").cloned().unwrap_or(Value::Null),
            "matched_cues": candidate.get("matched_cues").cloned().unwrap_or(Value::Null),
            "decision": decision,
            "latest_decision_at_unix": latest
                .and_then(|v| v.get("generated_at_unix"))
                .cloned()
                .unwrap_or(Value::Null),
            "reviewer": latest
                .and_then(|v| v.get("reviewer"))
                .cloned()
                .unwrap_or(Value::Null),
            "requires_local_log_lookup": candidate
                .get("requires_local_log_lookup")
                .cloned()
                .unwrap_or(Value::Null),
        }));
    }

    let candidate_count = rows.len();
    Ok(json!({
        "schema": "agent_bridge.instinct_observer.phase1_review_inbox.v0",
        "read_only": true,
        "packet_json": packet_json.display().to_string(),
        "decisions_path": decisions_path.display().to_string(),
        "packet_id": packet.get("packet_id").cloned().unwrap_or(Value::Null),
        "candidate_count": candidate_count,
        "pending_count": pending_count,
        "approved_count": approved_count,
        "rejected_count": rejected_count,
        "deferred_count": deferred_count,
        "writes_memory": false,
        "auto_apply_allowed": false,
        "candidates": rows.into_iter().take(limit).collect::<Vec<_>>(),
    }))
}

pub fn observer_review_context(
    packet_json: &Path,
    candidate_id: &str,
    log_path: Option<&Path>,
    include_local_excerpt: bool,
) -> std::io::Result<Value> {
    observer_review_context_for_paths(
        packet_json,
        candidate_id,
        log_path.unwrap_or(&default_observer_log_path()),
        include_local_excerpt,
    )
}

pub fn observer_review_context_for_paths(
    packet_json: &Path,
    candidate_id: &str,
    log_path: &Path,
    include_local_excerpt: bool,
) -> std::io::Result<Value> {
    let body = std::fs::read_to_string(packet_json)?;
    let packet: Value = serde_json::from_str(&body)
        .map_err(|e| std::io::Error::new(std::io::ErrorKind::InvalidData, e))?;
    ensure_review_packet_schema(&packet)?;
    let candidate = find_candidate(&packet, candidate_id)?;
    let session_id = candidate
        .get("session_id")
        .and_then(|v| v.as_str())
        .unwrap_or("");
    let event_at = candidate.get("event_at_unix").and_then(|v| v.as_f64());
    let mut local_log_match = Value::Null;
    if let Some(event_at) = event_at {
        if let Some(record) = find_observation_by_session_and_time(log_path, session_id, event_at) {
            local_log_match = json!({
                "found": true,
                "event_at_unix": record.ts,
                "event": record.ev,
                "prompt_chars": record.prompt.as_ref().map(|s| s.chars().count()),
                "prompt_excerpt": if include_local_excerpt {
                    record.prompt.clone().map(Value::String).unwrap_or(Value::Null)
                } else {
                    Value::Null
                },
                "raw_prompt_included": include_local_excerpt,
            });
        }
    }
    if local_log_match.is_null() {
        local_log_match = json!({
            "found": false,
            "raw_prompt_included": false,
        });
    }

    Ok(json!({
        "schema": "agent_bridge.instinct_observer.phase1_review_context.v0",
        "read_only": true,
        "packet_json": packet_json.display().to_string(),
        "log_path": log_path.display().to_string(),
        "packet_id": packet.get("packet_id").cloned().unwrap_or(Value::Null),
        "candidate_id": candidate_id,
        "candidate": {
            "kind": candidate.get("kind").cloned().unwrap_or(Value::Null),
            "session_id": candidate.get("session_id").cloned().unwrap_or(Value::Null),
            "event_at_unix": candidate.get("event_at_unix").cloned().unwrap_or(Value::Null),
            "matched_cues": candidate.get("matched_cues").cloned().unwrap_or(Value::Null),
            "prompt_chars": candidate.get("prompt_chars").cloned().unwrap_or(Value::Null),
            "requires_local_log_lookup": candidate.get("requires_local_log_lookup").cloned().unwrap_or(Value::Null),
        },
        "local_log_match": local_log_match,
        "writes_memory": false,
        "writes_decision": false,
        "auto_apply_allowed": false,
        "recommended_next_step": "decide_approve_reject_or_defer",
    }))
}

pub fn rotate_observer_log(dry_run: bool) -> std::io::Result<Value> {
    let now_unix = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map(|d| d.as_secs())
        .unwrap_or(0);
    rotate_observer_log_for_path(&default_observer_log_path(), now_unix, dry_run)
}

pub fn rotate_observer_log_for_path(
    log_path: &Path,
    now_unix: u64,
    dry_run: bool,
) -> std::io::Result<Value> {
    let meta = std::fs::metadata(log_path).ok();
    let log_exists = meta.as_ref().is_some_and(|m| m.is_file());
    let log_bytes = meta.as_ref().map(|m| m.len()).unwrap_or(0);
    let archive_path = observer_log_archive_path(log_path, now_unix);
    let action = if log_exists { "rotate_log" } else { "noop" };
    let mut status = if log_exists {
        if dry_run {
            "would_rotate"
        } else {
            "rotated"
        }
    } else {
        "no_log"
    };

    if log_exists && !dry_run {
        std::fs::rename(log_path, &archive_path)?;
    } else if !log_exists && !dry_run {
        status = "no_log";
    }

    Ok(json!({
        "schema": "agent_bridge_instinct_observer_log_rotation.v0",
        "dry_run": dry_run,
        "action": action,
        "status": status,
        "log_path": log_path.display().to_string(),
        "archive_path": archive_path.display().to_string(),
        "log_exists": log_exists,
        "log_bytes": log_bytes,
        "max_bytes": OBSERVER_MAX_BYTES,
        "rotation_recommended": log_bytes >= OBSERVER_MAX_BYTES,
    }))
}

fn render_review_packet_markdown(packet: &Value) -> String {
    let mut out = String::new();
    out.push_str("# Instinct Observer Review Packet\n\n");
    out.push_str(&format!(
        "- packet_id: `{}`\n",
        value_str(packet.get("packet_id"))
    ));
    out.push_str(&format!(
        "- generated_at_unix: `{}`\n",
        value_str(packet.get("generated_at_unix"))
    ));
    out.push_str(&format!(
        "- status: `{}`\n",
        value_str(packet.get("status"))
    ));
    out.push_str(&format!(
        "- candidate_count: `{}`\n",
        value_str(packet.get("candidate_count"))
    ));
    out.push_str(&format!(
        "- reviewer: `{}`\n",
        value_str(packet.get("reviewer"))
    ));

    out.push_str("\n## Boundary\n\n");
    out.push_str("- writes_memory: `false`\n");
    out.push_str("- persists_review_queue: `false`\n");
    out.push_str("- auto_apply_allowed: `false`\n");
    out.push_str("- raw_prompt_included: `false`\n");
    out.push_str("- raw_tool_input_included: `false`\n");
    out.push_str("- raw_tool_output_included: `false`\n");

    out.push_str("\n## Candidates\n\n");
    if let Some(candidates) = packet
        .pointer("/candidate_preview/candidates")
        .and_then(|v| v.as_array())
    {
        if candidates.is_empty() {
            out.push_str("_No candidates in this packet._\n");
        }
        for candidate in candidates {
            out.push_str(&format!(
                "### {} `{}`\n\n",
                value_str(candidate.get("candidate_id")),
                value_str(candidate.get("kind"))
            ));
            out.push_str(&format!(
                "- review_state: `{}`\n",
                value_str(candidate.get("review_state"))
            ));
            out.push_str(&format!(
                "- session_id: `{}`\n",
                value_str(candidate.get("session_id"))
            ));
            if let Some(tool) = candidate.get("tool") {
                out.push_str(&format!("- tool: `{}`\n", value_str(Some(tool))));
            }
            if let Some(cues) = candidate.get("matched_cues").and_then(|v| v.as_array()) {
                let joined = cues
                    .iter()
                    .map(|cue| value_str(Some(cue)))
                    .collect::<Vec<_>>()
                    .join(", ");
                out.push_str(&format!("- matched_cues: `{joined}`\n"));
            }
            out.push_str("- decision: `[ ] approve` `[ ] reject` `[ ] defer`\n");
            out.push_str("- reviewer_note:\n\n");
        }
    }

    out.push_str("\n## Review Checklist\n\n");
    if let Some(items) = packet
        .get("human_review_checklist")
        .and_then(|v| v.as_array())
    {
        for item in items {
            out.push_str(&format!("- [ ] {}\n", value_str(Some(item))));
        }
    }
    out.push_str("\nNo memory write is authorized by this packet.\n");
    out
}

fn render_memory_preflight_markdown(packet: &Value) -> String {
    let mut out = String::new();
    out.push_str("# Instinct Memory Write Preflight\n\n");
    out.push_str(&format!(
        "- preflight_id: `{}`\n",
        value_str(packet.get("preflight_id"))
    ));
    out.push_str(&format!(
        "- status: `{}`\n",
        value_str(packet.get("status"))
    ));
    out.push_str(&format!(
        "- candidate_id: `{}`\n",
        value_str(packet.get("candidate_id"))
    ));
    out.push_str(&format!(
        "- approved_by_human_decision: `{}`\n",
        value_str(packet.get("approved_by_human_decision"))
    ));
    out.push_str(&format!(
        "- ready_for_separate_memory_write: `{}`\n",
        value_str(packet.get("ready_for_separate_memory_write"))
    ));

    out.push_str("\n## Boundary\n\n");
    out.push_str("- writes_memory: `false`\n");
    out.push_str("- auto_apply_allowed: `false`\n");
    out.push_str("- raw_prompt_included: `false`\n");
    out.push_str("- raw_tool_input_included: `false`\n");
    out.push_str("- raw_tool_output_included: `false`\n");
    out.push_str("- memory_write_requires_separate_command: `true`\n");

    out.push_str("\n## Memory Draft\n\n");
    let draft = packet.get("memory_draft").unwrap_or(&Value::Null);
    out.push_str(&format!("- key: `{}`\n", value_str(draft.get("key"))));
    out.push_str(&format!("- kind: `{}`\n", value_str(draft.get("kind"))));
    out.push_str(&format!(
        "- body_chars: `{}`\n",
        value_str(draft.get("body_chars"))
    ));
    if let Some(body) = draft.get("body").and_then(|v| v.as_str()) {
        out.push_str("\n```text\n");
        out.push_str(body);
        out.push_str("\n```\n");
    } else {
        out.push_str("\n_No memory body supplied._\n");
    }

    out.push_str("\n## Blocked Reasons\n\n");
    if let Some(reasons) = packet.get("blocked_reasons").and_then(|v| v.as_array()) {
        if reasons.is_empty() {
            out.push_str("- none\n");
        }
        for reason in reasons {
            out.push_str(&format!("- `{}`\n", value_str(Some(reason))));
        }
    }
    out.push_str("\nThis packet does not write memory.\n");
    out
}

fn value_str(value: Option<&Value>) -> String {
    match value {
        Some(Value::String(s)) => s.clone(),
        Some(Value::Number(n)) => n.to_string(),
        Some(Value::Bool(b)) => b.to_string(),
        Some(Value::Null) | None => "-".to_string(),
        Some(other) => other.to_string(),
    }
}

fn ensure_review_packet_schema(packet: &Value) -> std::io::Result<()> {
    let packet_schema = packet.get("schema").and_then(|v| v.as_str()).unwrap_or("");
    if packet_schema == "agent_bridge.instinct_observer.phase1_review_packet.v0" {
        Ok(())
    } else {
        Err(std::io::Error::new(
            std::io::ErrorKind::InvalidInput,
            "packet_json is not an instinct phase1 review packet",
        ))
    }
}

fn ensure_memory_preflight_schema(packet: &Value) -> std::io::Result<()> {
    let schema = packet.get("schema").and_then(|v| v.as_str()).unwrap_or("");
    if schema == "agent_bridge.instinct_observer.phase1_memory_write_preflight.v0" {
        Ok(())
    } else {
        Err(std::io::Error::new(
            std::io::ErrorKind::InvalidInput,
            "preflight_json is not an instinct phase1 memory write preflight",
        ))
    }
}

fn find_candidate<'a>(packet: &'a Value, candidate_id: &str) -> std::io::Result<&'a Value> {
    packet
        .pointer("/candidate_preview/candidates")
        .and_then(|v| v.as_array())
        .and_then(|items| {
            items.iter().find(|candidate| {
                candidate.get("candidate_id").and_then(|v| v.as_str()) == Some(candidate_id)
            })
        })
        .ok_or_else(|| {
            std::io::Error::new(
                std::io::ErrorKind::NotFound,
                format!("candidate not found in review packet: {candidate_id}"),
            )
        })
}

fn latest_decision_for_candidate(
    decisions_path: &Path,
    candidate_id: &str,
) -> std::io::Result<Option<Value>> {
    let decisions = load_review_decisions(decisions_path)?;
    let mut latest: Option<Value> = None;
    for value in decisions
        .into_iter()
        .filter(|value| value.get("candidate_id").and_then(|v| v.as_str()) == Some(candidate_id))
    {
        let current_ts = value
            .get("generated_at_unix")
            .and_then(|v| v.as_u64())
            .unwrap_or(0);
        let latest_ts = latest
            .as_ref()
            .and_then(|v| v.get("generated_at_unix"))
            .and_then(|v| v.as_u64())
            .unwrap_or(0);
        if latest.is_none() || current_ts >= latest_ts {
            latest = Some(value);
        }
    }
    Ok(latest)
}

fn latest_review_packet_path(review_dir: &Path) -> std::io::Result<Option<PathBuf>> {
    if !review_dir.is_dir() {
        return Ok(None);
    }
    let mut latest: Option<(u64, PathBuf)> = None;
    for entry in std::fs::read_dir(review_dir)? {
        let entry = entry?;
        let path = entry.path();
        if path.extension().and_then(|s| s.to_str()) != Some("json") {
            continue;
        }
        let Ok(body) = std::fs::read_to_string(&path) else {
            continue;
        };
        let Ok(value) = serde_json::from_str::<Value>(&body) else {
            continue;
        };
        if value.get("schema").and_then(|v| v.as_str())
            != Some("agent_bridge.instinct_observer.phase1_review_packet.v0")
        {
            continue;
        }
        let generated_at = value
            .get("generated_at_unix")
            .and_then(|v| v.as_u64())
            .unwrap_or(0);
        if latest
            .as_ref()
            .is_none_or(|(latest_ts, _)| generated_at >= *latest_ts)
        {
            latest = Some((generated_at, path));
        }
    }
    Ok(latest.map(|(_, path)| path))
}

fn find_observation_by_session_and_time(
    log_path: &Path,
    session_id: &str,
    event_at: f64,
) -> Option<ObservationRecord> {
    load_records(log_path).into_iter().find(|record| {
        record.sid.as_deref() == Some(session_id)
            && record.ts.is_some_and(|ts| (ts - event_at).abs() < 0.001)
    })
}

fn load_review_decisions(decisions_path: &Path) -> std::io::Result<Vec<Value>> {
    let text = match std::fs::read_to_string(decisions_path) {
        Ok(text) => text,
        Err(e) if e.kind() == std::io::ErrorKind::NotFound => return Ok(Vec::new()),
        Err(e) => return Err(e),
    };
    let mut decisions = Vec::new();
    for line in text.lines().filter(|line| !line.trim().is_empty()) {
        let value: Value = serde_json::from_str(line)
            .map_err(|e| std::io::Error::new(std::io::ErrorKind::InvalidData, e))?;
        if value.get("schema").and_then(|v| v.as_str())
            != Some("agent_bridge.instinct_observer.phase1_review_decision.v0")
        {
            continue;
        }
        decisions.push(value);
    }
    decisions.sort_by_key(|value| {
        value
            .get("generated_at_unix")
            .and_then(|v| v.as_u64())
            .unwrap_or(0)
    });
    Ok(decisions)
}

fn load_memory_write_receipts(receipts_path: &Path) -> std::io::Result<Vec<Value>> {
    let text = match std::fs::read_to_string(receipts_path) {
        Ok(text) => text,
        Err(e) if e.kind() == std::io::ErrorKind::NotFound => return Ok(Vec::new()),
        Err(e) => return Err(e),
    };
    let mut receipts = Vec::new();
    for line in text.lines().filter(|line| !line.trim().is_empty()) {
        let value: Value = serde_json::from_str(line)
            .map_err(|e| std::io::Error::new(std::io::ErrorKind::InvalidData, e))?;
        if value.get("schema").and_then(|v| v.as_str())
            != Some("agent_bridge.instinct_observer.phase1_memory_write_receipt.v0")
        {
            continue;
        }
        receipts.push(value);
    }
    receipts.sort_by_key(|value| {
        value
            .get("generated_at_unix")
            .and_then(|v| v.as_u64())
            .unwrap_or(0)
    });
    Ok(receipts)
}

fn sort_generated_desc(items: &mut [Value]) {
    items.sort_by_key(|value| {
        std::cmp::Reverse(
            value
                .get("generated_at_unix")
                .and_then(|v| v.as_u64())
                .unwrap_or(0),
        )
    });
}

fn memory_preflight_blocked_reasons(
    approved: bool,
    has_key: bool,
    has_kind: bool,
    has_body: bool,
) -> Vec<&'static str> {
    let mut reasons = Vec::new();
    if !approved {
        reasons.push("latest_decision_is_not_approve");
    }
    if !has_key {
        reasons.push("missing_memory_key");
    }
    if !has_kind {
        reasons.push("missing_memory_kind");
    }
    if !has_body {
        reasons.push("missing_memory_body");
    }
    reasons
}

fn memory_write_blocked_reasons(
    ready: bool,
    has_key: bool,
    has_kind: bool,
    has_content: bool,
) -> Vec<&'static str> {
    let mut reasons = Vec::new();
    if !ready {
        reasons.push("preflight_not_ready");
    }
    if !has_key {
        reasons.push("missing_memory_key");
    }
    if !has_kind {
        reasons.push("missing_memory_kind");
    }
    if !has_content {
        reasons.push("missing_memory_content");
    }
    reasons
}

fn importance_for_kind(kind: &str) -> f64 {
    match kind {
        "decision" => 0.8,
        "lesson" => 0.7,
        "todo" => 0.6,
        "fact" | "context" => 0.5,
        "observation" => 0.3,
        _ => 0.5,
    }
}

fn normalize_review_decision(decision: &str) -> std::io::Result<&'static str> {
    match decision {
        "approve" => Ok("approve"),
        "reject" => Ok("reject"),
        "defer" => Ok("defer"),
        other => Err(std::io::Error::new(
            std::io::ErrorKind::InvalidInput,
            format!("unsupported review decision: {other}"),
        )),
    }
}

fn write_private_file(path: &Path, body: &[u8]) -> std::io::Result<()> {
    let mut file = std::fs::OpenOptions::new()
        .create(true)
        .truncate(true)
        .write(true)
        .open(path)?;
    file.write_all(body)?;
    set_private_file_permissions(path)?;
    Ok(())
}

fn append_private_jsonl(path: &Path, value: &Value) -> std::io::Result<()> {
    let mut file = std::fs::OpenOptions::new()
        .create(true)
        .append(true)
        .open(path)?;
    let line = serde_json::to_string(value)
        .map_err(|e| std::io::Error::new(std::io::ErrorKind::InvalidData, e))?;
    writeln!(file, "{line}")?;
    set_private_file_permissions(path)?;
    Ok(())
}

#[cfg(unix)]
fn set_private_dir_permissions(path: &Path) -> std::io::Result<()> {
    use std::os::unix::fs::PermissionsExt;
    std::fs::set_permissions(path, std::fs::Permissions::from_mode(0o700))
}

#[cfg(not(unix))]
fn set_private_dir_permissions(_path: &Path) -> std::io::Result<()> {
    Ok(())
}

#[cfg(unix)]
fn set_private_file_permissions(path: &Path) -> std::io::Result<()> {
    use std::os::unix::fs::PermissionsExt;
    std::fs::set_permissions(path, std::fs::Permissions::from_mode(0o600))
}

#[cfg(not(unix))]
fn set_private_file_permissions(_path: &Path) -> std::io::Result<()> {
    Ok(())
}

fn observer_log_archive_path(log_path: &Path, now_unix: u64) -> PathBuf {
    let file_name = log_path
        .file_name()
        .and_then(|name| name.to_str())
        .unwrap_or("observations.jsonl");
    log_path.with_file_name(format!("{file_name}.rotated-{now_unix}"))
}

pub fn observer_status_for_paths(
    installed_path: PathBuf,
    log_path: PathBuf,
    enabled: bool,
) -> InstinctObserverStatus {
    let installed = installed_path.exists();
    let executable = installed && is_executable(&installed_path);
    let log_dir_path = log_path
        .parent()
        .map(Path::to_path_buf)
        .unwrap_or_else(|| PathBuf::from(""));
    let log_dir_mode = private_dir_mode_octal(&log_dir_path);
    let log_meta = std::fs::metadata(&log_path).ok();
    let log_present = log_meta.as_ref().is_some_and(|m| m.is_file());
    let log_mode = private_file_mode_octal(&log_path);
    let permissions_ok = observer_permissions_ok(&log_dir_path, &log_path, log_present);
    let log_bytes = log_meta.as_ref().map(|m| m.len()).unwrap_or(0);
    let records = load_records(&log_path);
    let analyzed = analyze_records(&records);
    let summary = summarize(&records, analyzed);
    let recommendation = recommendation_for(enabled, &summary, log_present, log_bytes);

    InstinctObserverStatus {
        enabled,
        installed_path: installed_path.display().to_string(),
        installed,
        executable,
        log_path: log_path.display().to_string(),
        log_dir_path: log_dir_path.display().to_string(),
        log_present,
        log_dir_mode_octal: log_dir_mode,
        log_mode_octal: log_mode,
        permissions_ok,
        log_bytes,
        max_bytes: OBSERVER_MAX_BYTES,
        total_records: records.len() as u64,
        sessions: summary.per_session.len(),
        events: summary.events,
        top_tools: summary.top_tools,
        latest_event_at_unix: summary.latest_event_at_unix,
        latest_event_age_secs: summary.latest_event_age_secs,
        total_clean_mineable: summary.total_clean_mineable,
        mean_clean_mineable_per_session: summary.mean_clean_mineable_per_session,
        total_legacy_upper_bound_mineable: summary.total_legacy_upper_bound_mineable,
        mean_legacy_upper_bound_per_session: summary.mean_legacy_upper_bound_per_session,
        legacy_untrusted_errors: summary.legacy_untrusted_errors,
        stderr_success_records: summary.stderr_success_records,
        gate: format!("mean>={MINEABLE_MEAN_GATE:.1} over >={MIN_SESSIONS} sessions"),
        verdict: verdict_for(
            summary.mean_clean_mineable_per_session,
            summary.per_session.len(),
        ),
        legacy_upper_bound_verdict: verdict_for(
            summary.mean_legacy_upper_bound_per_session,
            summary.per_session.len(),
        ),
        recommendation,
        per_session: summary.per_session,
    }
}

#[derive(Debug, Clone)]
struct ObserverSummary {
    events: BTreeMap<String, u64>,
    top_tools: Vec<(String, u64)>,
    latest_event_at_unix: Option<f64>,
    latest_event_age_secs: Option<u64>,
    total_clean_mineable: u64,
    mean_clean_mineable_per_session: f64,
    total_legacy_upper_bound_mineable: u64,
    mean_legacy_upper_bound_per_session: f64,
    legacy_untrusted_errors: u64,
    stderr_success_records: u64,
    per_session: BTreeMap<String, SessionSignalSummary>,
}

fn load_records(path: &Path) -> Vec<ObservationRecord> {
    let Ok(text) = std::fs::read_to_string(path) else {
        return Vec::new();
    };
    text.lines()
        .filter_map(|line| {
            let line = line.trim();
            if line.is_empty() {
                None
            } else {
                serde_json::from_str::<ObservationRecord>(line).ok()
            }
        })
        .collect()
}

fn analyze_records(records: &[ObservationRecord]) -> BTreeMap<String, SessionSignalSummary> {
    let mut sorted = records.to_vec();
    sorted.sort_by(|a, b| {
        a.ts.unwrap_or(0.0)
            .partial_cmp(&b.ts.unwrap_or(0.0))
            .unwrap_or(std::cmp::Ordering::Equal)
    });

    let mut sessions: BTreeMap<String, SessionWorking> = BTreeMap::new();
    for record in &sorted {
        let sid = record.sid.as_deref().unwrap_or("?").to_string();
        let state = sessions.entry(sid).or_default();
        match record.ev.as_deref() {
            Some("UserPromptSubmit") => {
                state.summary.prompts += 1;
                if classify_prompt(record.prompt.as_deref().unwrap_or_default()) {
                    state.summary.corrections += 1;
                }
            }
            Some("PostToolUse") => {
                state.summary.tools += 1;
                let tool = record.tool.as_deref().unwrap_or("?").to_string();
                let clean_err = is_clean_error(record);
                let legacy_err = record.err.unwrap_or(false);
                let stderr_success = record.stderr_nonempty.unwrap_or(false) && !clean_err;
                let legacy_untrusted = legacy_err && !has_err_source(record);

                if stderr_success {
                    state.summary.stderr_success += 1;
                }
                if legacy_untrusted {
                    state.summary.legacy_untrusted_errors += 1;
                }

                if clean_err {
                    state.summary.clean_errors += 1;
                    *state.clean_pending.entry(tool.clone()).or_insert(0) += 1;
                } else if decrement_pending(&mut state.clean_pending, &tool) {
                    state.summary.clean_error_resolutions += 1;
                }

                if legacy_err {
                    *state.legacy_pending.entry(tool.clone()).or_insert(0) += 1;
                } else if decrement_pending(&mut state.legacy_pending, &tool) {
                    state.summary.legacy_error_resolutions += 1;
                }
            }
            _ => {}
        }
    }

    sessions
        .into_iter()
        .map(|(sid, mut state)| {
            state.summary.clean_mineable =
                state.summary.corrections + state.summary.clean_error_resolutions;
            state.summary.legacy_upper_bound_mineable =
                state.summary.corrections + state.summary.legacy_error_resolutions;
            (sid, state.summary)
        })
        .collect()
}

fn extract_candidate_preview(records: &[ObservationRecord], limit: usize) -> Vec<Value> {
    let mut sorted = records.to_vec();
    sorted.sort_by(|a, b| {
        a.ts.unwrap_or(0.0)
            .partial_cmp(&b.ts.unwrap_or(0.0))
            .unwrap_or(std::cmp::Ordering::Equal)
    });

    let mut candidates = Vec::new();
    let mut pending_errors: HashMap<(String, String), ObservationRecord> = HashMap::new();
    for record in &sorted {
        if candidates.len() >= limit {
            break;
        }
        let sid = record.sid.as_deref().unwrap_or("?").to_string();
        if !is_reviewable_session_id(&sid) {
            continue;
        }
        match record.ev.as_deref() {
            Some("UserPromptSubmit") => {
                let prompt = record.prompt.as_deref().unwrap_or_default();
                let cues = matched_correction_cues(prompt);
                if !cues.is_empty() {
                    candidates.push(json!({
                        "candidate_id": format!("instinct-candidate-{:04}", candidates.len() + 1),
                        "kind": "correction_prompt",
                        "review_state": "pending_human_review",
                        "session_id": sid,
                        "event_at_unix": record.ts,
                        "matched_cues": cues,
                        "prompt_chars": prompt.chars().count(),
                        "raw_prompt_included": false,
                        "requires_local_log_lookup": true,
                        "proposed_memory_write": {
                            "kind": "lesson_or_correction",
                            "auto_write_allowed": false
                        }
                    }));
                }
            }
            Some("PostToolUse") => {
                let tool = record.tool.as_deref().unwrap_or("?").to_string();
                let key = (sid.clone(), tool.clone());
                if is_clean_error(record) {
                    pending_errors.insert(key, record.clone());
                } else if let Some(failed) = pending_errors.remove(&key) {
                    candidates.push(json!({
                        "candidate_id": format!("instinct-candidate-{:04}", candidates.len() + 1),
                        "kind": "clean_error_resolution",
                        "review_state": "pending_human_review",
                        "session_id": sid,
                        "tool": tool,
                        "failed_at_unix": failed.ts,
                        "resolved_at_unix": record.ts,
                        "err_source": failed.err_source.clone(),
                        "failed_input_summary_available": failed.input_brief.as_ref().is_some_and(|s| !s.trim().is_empty()),
                        "failed_output_summary_available": failed.output_brief.as_ref().is_some_and(|s| !s.trim().is_empty()),
                        "resolved_input_summary_available": record.input_brief.as_ref().is_some_and(|s| !s.trim().is_empty()),
                        "resolved_output_summary_available": record.output_brief.as_ref().is_some_and(|s| !s.trim().is_empty()),
                        "raw_tool_input_included": false,
                        "raw_tool_output_included": false,
                        "requires_local_log_lookup": true,
                        "proposed_memory_write": {
                            "kind": "error_pattern_or_lesson",
                            "auto_write_allowed": false
                        }
                    }));
                }
            }
            _ => {}
        }
    }
    candidates
}

fn is_reviewable_session_id(sid: &str) -> bool {
    sid.len() >= 16
        && sid.contains('-')
        && sid
            .chars()
            .all(|ch| ch.is_ascii_alphanumeric() || ch == '-')
}

fn summarize(
    records: &[ObservationRecord],
    per_session: BTreeMap<String, SessionSignalSummary>,
) -> ObserverSummary {
    let mut events = BTreeMap::new();
    let mut tools = BTreeMap::new();
    let mut latest_event_at_unix: Option<f64> = None;
    for record in records {
        let ev = record.ev.as_deref().unwrap_or("?").to_string();
        *events.entry(ev.clone()).or_insert(0) += 1;
        if ev == "PostToolUse" {
            *tools
                .entry(record.tool.as_deref().unwrap_or("?").to_string())
                .or_insert(0) += 1;
        }
        if let Some(ts) = record.ts {
            latest_event_at_unix = Some(
                latest_event_at_unix
                    .map(|latest| latest.max(ts))
                    .unwrap_or(ts),
            );
        }
    }

    let mut top_tools: Vec<(String, u64)> = tools.into_iter().collect();
    top_tools.sort_by(|a, b| b.1.cmp(&a.1).then_with(|| a.0.cmp(&b.0)));
    top_tools.truncate(10);

    let sessions = per_session.len();
    let total_clean_mineable = per_session.values().map(|s| s.clean_mineable).sum();
    let total_legacy_upper_bound_mineable = per_session
        .values()
        .map(|s| s.legacy_upper_bound_mineable)
        .sum();
    let legacy_untrusted_errors = per_session
        .values()
        .map(|s| s.legacy_untrusted_errors)
        .sum();
    let stderr_success_records = per_session.values().map(|s| s.stderr_success).sum();

    ObserverSummary {
        events,
        top_tools,
        latest_event_at_unix,
        latest_event_age_secs: latest_event_at_unix.and_then(latest_age_secs),
        total_clean_mineable,
        mean_clean_mineable_per_session: mean(total_clean_mineable, sessions),
        total_legacy_upper_bound_mineable,
        mean_legacy_upper_bound_per_session: mean(total_legacy_upper_bound_mineable, sessions),
        legacy_untrusted_errors,
        stderr_success_records,
        per_session,
    }
}

fn classify_prompt(text: &str) -> bool {
    !matched_correction_cues(text).is_empty()
}

fn matched_correction_cues(text: &str) -> Vec<&'static str> {
    let low = text.to_lowercase();
    CORRECTION_CUES
        .iter()
        .copied()
        .filter(|cue| text.contains(cue) || low.contains(cue))
        .collect()
}

fn is_clean_error(record: &ObservationRecord) -> bool {
    record.err.unwrap_or(false) && has_err_source(record)
}

fn has_err_source(record: &ObservationRecord) -> bool {
    match &record.err_source {
        Some(Value::Null) | None => false,
        Some(Value::String(s)) => !s.trim().is_empty(),
        Some(_) => true,
    }
}

fn decrement_pending(pending: &mut HashMap<String, u64>, tool: &str) -> bool {
    let Some(count) = pending.get_mut(tool) else {
        return false;
    };
    if *count == 0 {
        return false;
    }
    *count -= 1;
    true
}

fn mean(total: u64, sessions: usize) -> f64 {
    if sessions == 0 {
        return 0.0;
    }
    let mean = total as f64 / sessions as f64;
    (mean * 1000.0).round() / 1000.0
}

fn verdict_for(mean: f64, sessions: usize) -> String {
    if sessions < MIN_SESSIONS {
        "INSUFFICIENT_SESSIONS".to_string()
    } else if mean >= MINEABLE_MEAN_GATE {
        "DENSITY_OK_PROCEED_PHASE1".to_string()
    } else {
        "NO_SIGNAL".to_string()
    }
}

fn recommendation_for(
    enabled: bool,
    summary: &ObserverSummary,
    log_present: bool,
    log_bytes: u64,
) -> String {
    if !enabled {
        return "observer_disabled".to_string();
    }
    if !log_present || summary.per_session.is_empty() {
        return "no_observations_yet".to_string();
    }
    if log_bytes >= OBSERVER_MAX_BYTES {
        return "rotate_observer_log".to_string();
    }
    match verdict_for(
        summary.mean_clean_mineable_per_session,
        summary.per_session.len(),
    )
    .as_str()
    {
        "INSUFFICIENT_SESSIONS" => "wait_for_sessions".to_string(),
        "DENSITY_OK_PROCEED_PHASE1" => "review_before_phase1_miner".to_string(),
        _ => "do_not_build_miner".to_string(),
    }
}

fn latest_age_secs(ts: f64) -> Option<u64> {
    let now = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .ok()?
        .as_secs_f64();
    if now >= ts {
        Some((now - ts).round() as u64)
    } else {
        Some(0)
    }
}

#[cfg(unix)]
fn mode_octal(path: &Path) -> Option<String> {
    use std::os::unix::fs::PermissionsExt;
    std::fs::metadata(path)
        .ok()
        .map(|m| format!("{:03o}", m.permissions().mode() & 0o777))
}

#[cfg(not(unix))]
fn mode_octal(_path: &Path) -> Option<String> {
    None
}

fn private_dir_mode_octal(path: &Path) -> Option<String> {
    mode_octal(path)
}

fn private_file_mode_octal(path: &Path) -> Option<String> {
    mode_octal(path)
}

#[cfg(unix)]
fn observer_permissions_ok(log_dir: &Path, log_path: &Path, log_present: bool) -> bool {
    use std::os::unix::fs::PermissionsExt;

    let dir_ok = std::fs::metadata(log_dir)
        .ok()
        .map(|m| {
            let mode = m.permissions().mode() & 0o777;
            // Directory should be owner-only; execute is needed to traverse.
            mode & 0o077 == 0 && mode & 0o700 == 0o700
        })
        .unwrap_or(true);
    let file_ok = if log_present {
        std::fs::metadata(log_path)
            .ok()
            .map(|m| {
                let mode = m.permissions().mode() & 0o777;
                // JSONL may contain prompt/tool summaries; no group/other or exec bits.
                mode & 0o177 == 0 && mode & 0o600 == 0o600
            })
            .unwrap_or(true)
    } else {
        true
    };
    dir_ok && file_ok
}

#[cfg(not(unix))]
fn observer_permissions_ok(_log_dir: &Path, _log_path: &Path, _log_present: bool) -> bool {
    true
}

#[cfg(unix)]
fn is_executable(path: &Path) -> bool {
    use std::os::unix::fs::PermissionsExt;
    std::fs::metadata(path)
        .map(|m| m.permissions().mode() & 0o111 != 0)
        .unwrap_or(false)
}

#[cfg(not(unix))]
fn is_executable(path: &Path) -> bool {
    path.is_file()
}

#[cfg(test)]
mod tests {
    use super::*;

    const TEST_SID: &str = "019e0000-0000-7000-8000-000000000001";

    fn write_jsonl(path: &Path, rows: &[Value]) {
        let mut text = String::new();
        for row in rows {
            text.push_str(&serde_json::to_string(row).unwrap());
            text.push('\n');
        }
        std::fs::write(path, text).unwrap();
    }

    #[test]
    fn observer_status_separates_clean_errors_from_legacy_noise() {
        let tmp = tempfile::tempdir().unwrap();
        let hook = tmp.path().join("ab-instinct-observer-hook");
        let log = tmp.path().join("observations.jsonl");
        std::fs::write(&hook, "#!/bin/sh\n").unwrap();
        write_jsonl(
            &log,
            &[
                json!({"ts": 1.0, "sid": "legacy", "ev": "PostToolUse", "tool": "Bash", "err": true}),
                json!({"ts": 2.0, "sid": "legacy", "ev": "PostToolUse", "tool": "Bash", "err": false}),
                json!({"ts": 3.0, "sid": "clean", "ev": "PostToolUse", "tool": "Bash", "err": true, "err_source": "exit_code"}),
                json!({"ts": 4.0, "sid": "clean", "ev": "PostToolUse", "tool": "Bash", "err": false}),
            ],
        );

        let status = observer_status_for_paths(hook, log, true);
        assert_eq!(status.total_clean_mineable, 1);
        assert_eq!(status.total_legacy_upper_bound_mineable, 2);
        assert_eq!(status.legacy_untrusted_errors, 1);
        assert_eq!(status.verdict, "INSUFFICIENT_SESSIONS");
        assert_eq!(status.recommendation, "wait_for_sessions");
    }

    #[cfg(unix)]
    #[test]
    fn observer_status_reports_private_sidecar_permissions() {
        use std::os::unix::fs::PermissionsExt;

        let tmp = tempfile::tempdir().unwrap();
        let hook = tmp.path().join("ab-instinct-observer-hook");
        let dir = tmp.path().join("instinct-probe");
        let log = dir.join("observations.jsonl");
        std::fs::create_dir(&dir).unwrap();
        std::fs::write(&hook, "#!/bin/sh\n").unwrap();
        write_jsonl(
            &log,
            &[json!({"ts": 1.0, "sid": "s", "ev": "UserPromptSubmit", "prompt": "hello"})],
        );
        std::fs::set_permissions(&dir, std::fs::Permissions::from_mode(0o700)).unwrap();
        std::fs::set_permissions(&log, std::fs::Permissions::from_mode(0o600)).unwrap();

        let status = observer_status_for_paths(hook.clone(), log.clone(), true);
        assert!(status.permissions_ok);
        assert_eq!(status.log_dir_mode_octal.as_deref(), Some("700"));
        assert_eq!(status.log_mode_octal.as_deref(), Some("600"));

        std::fs::set_permissions(&dir, std::fs::Permissions::from_mode(0o775)).unwrap();
        std::fs::set_permissions(&log, std::fs::Permissions::from_mode(0o664)).unwrap();
        let status = observer_status_for_paths(hook, log, true);
        assert!(!status.permissions_ok);
        assert_eq!(status.log_dir_mode_octal.as_deref(), Some("775"));
        assert_eq!(status.log_mode_octal.as_deref(), Some("664"));
    }

    #[test]
    fn observer_status_handles_missing_log_as_non_blocking() {
        let tmp = tempfile::tempdir().unwrap();
        let status = observer_status_for_paths(
            tmp.path().join("missing-hook"),
            tmp.path().join("missing.jsonl"),
            true,
        );
        assert_eq!(status.total_records, 0);
        assert_eq!(status.sessions, 0);
        assert_eq!(status.verdict, "INSUFFICIENT_SESSIONS");
        assert_eq!(status.recommendation, "no_observations_yet");
    }

    #[test]
    fn observer_status_detects_density_ok_after_five_sessions() {
        let tmp = tempfile::tempdir().unwrap();
        let hook = tmp.path().join("ab-instinct-observer-hook");
        let log = tmp.path().join("observations.jsonl");
        std::fs::write(&hook, "#!/bin/sh\n").unwrap();
        let rows: Vec<Value> = (0..5)
            .map(|idx| {
                json!({
                    "ts": idx as f64,
                    "sid": format!("s{idx}"),
                    "ev": "UserPromptSubmit",
                    "prompt": "不对，应该改成这样"
                })
            })
            .collect();
        write_jsonl(&log, &rows);

        let status = observer_status_for_paths(hook, log, true);
        assert_eq!(status.total_clean_mineable, 5);
        assert_eq!(status.mean_clean_mineable_per_session, 1.0);
        assert_eq!(status.verdict, "DENSITY_OK_PROCEED_PHASE1");
        assert_eq!(status.recommendation, "review_before_phase1_miner");
    }

    #[test]
    fn observer_candidate_preview_reports_redacted_phase1_candidates() {
        let tmp = tempfile::tempdir().unwrap();
        let log = tmp.path().join("observations.jsonl");
        write_jsonl(
            &log,
            &[
                json!({
                    "ts": 0.5,
                    "sid": "s1",
                    "ev": "UserPromptSubmit",
                    "prompt": "不对，这条 synthetic session 不应进入候选"
                }),
                json!({
                    "ts": 1.0,
                    "sid": TEST_SID,
                    "ev": "UserPromptSubmit",
                    "prompt": "不对，应该改成 secret prompt detail"
                }),
                json!({
                    "ts": 2.0,
                    "sid": TEST_SID,
                    "ev": "PostToolUse",
                    "tool": "Bash",
                    "err": true,
                    "err_source": "exit_code",
                    "in": "secret failing command",
                    "out": "secret failing output"
                }),
                json!({
                    "ts": 3.0,
                    "sid": TEST_SID,
                    "ev": "PostToolUse",
                    "tool": "Bash",
                    "err": false,
                    "in": "secret fixed command",
                    "out": "secret fixed output"
                }),
            ],
        );

        let preview = observer_candidate_preview_for_path(&log, 20);

        assert_eq!(
            preview["schema"],
            json!("agent_bridge.instinct_observer.phase1_candidate_preview.v0")
        );
        assert_eq!(preview["read_only"], json!(true));
        assert_eq!(preview["boundary_check"]["writes_memory"], json!(false));
        assert_eq!(
            preview["boundary_check"]["persists_review_queue"],
            json!(false)
        );
        assert_eq!(
            preview["boundary_check"]["raw_prompt_included"],
            json!(false)
        );
        assert_eq!(
            preview["boundary_check"]["raw_tool_output_included"],
            json!(false)
        );
        assert_eq!(preview["candidate_count"], json!(2));
        assert_eq!(preview["candidates"][0]["kind"], json!("correction_prompt"));
        assert_eq!(preview["candidates"][0]["session_id"], json!(TEST_SID));
        assert_eq!(
            preview["candidates"][1]["kind"],
            json!("clean_error_resolution")
        );
        assert_eq!(
            preview["candidates"][1]["failed_input_summary_available"],
            json!(true)
        );
        let text = serde_json::to_string(&preview).unwrap();
        assert!(!text.contains("secret prompt detail"));
        assert!(!text.contains("secret failing command"));
        assert!(!text.contains("secret failing output"));
        assert!(!text.contains("secret fixed command"));
        assert!(!text.contains("secret fixed output"));
    }

    #[test]
    fn observer_review_packet_writes_redacted_private_review_files_only_when_requested() {
        let tmp = tempfile::tempdir().unwrap();
        let log = tmp.path().join("observations.jsonl");
        let out_dir = tmp.path().join("review");
        write_jsonl(
            &log,
            &[
                json!({
                    "ts": 1.0,
                    "sid": TEST_SID,
                    "ev": "UserPromptSubmit",
                    "prompt": "错了，应该改成 secret review prompt"
                }),
                json!({
                    "ts": 2.0,
                    "sid": TEST_SID,
                    "ev": "PostToolUse",
                    "tool": "Bash",
                    "err": true,
                    "err_source": "exit_code",
                    "in": "secret review failing command",
                    "out": "secret review failing output"
                }),
                json!({
                    "ts": 3.0,
                    "sid": TEST_SID,
                    "ev": "PostToolUse",
                    "tool": "Bash",
                    "err": false,
                    "in": "secret review fixed command",
                    "out": "secret review fixed output"
                }),
            ],
        );

        let dry_run = observer_review_packet_for_paths(
            &log,
            &out_dir,
            20,
            Some("tester"),
            1_780_747_010,
            false,
        )
        .unwrap();
        assert_eq!(
            dry_run["schema"],
            "agent_bridge.instinct_observer.phase1_review_packet.v0"
        );
        assert_eq!(dry_run["dry_run"], json!(true));
        assert_eq!(dry_run["written"], json!(false));
        assert_eq!(dry_run["writes_files"], json!(false));
        assert_eq!(dry_run["writes_memory"], json!(false));
        assert!(
            !out_dir.exists(),
            "dry-run must not create a review directory"
        );

        let packet = observer_review_packet_for_paths(
            &log,
            &out_dir,
            20,
            Some("tester"),
            1_780_747_011,
            true,
        )
        .unwrap();
        assert_eq!(packet["dry_run"], json!(false));
        assert_eq!(packet["written"], json!(true));
        assert_eq!(packet["writes_files"], json!(true));
        assert_eq!(packet["writes_memory"], json!(false));
        assert_eq!(packet["persists_review_queue"], json!(false));
        assert_eq!(packet["candidate_count"], json!(2));

        let json_path = PathBuf::from(packet["json_path"].as_str().unwrap());
        let markdown_path = PathBuf::from(packet["markdown_path"].as_str().unwrap());
        assert!(json_path.exists());
        assert!(markdown_path.exists());
        assert_eq!(mode_octal(&out_dir).as_deref(), Some("700"));
        assert_eq!(mode_octal(&json_path).as_deref(), Some("600"));
        assert_eq!(mode_octal(&markdown_path).as_deref(), Some("600"));

        let json_body = std::fs::read_to_string(json_path).unwrap();
        let written_packet: Value = serde_json::from_str(&json_body).unwrap();
        assert_eq!(written_packet["written"], json!(true));
        let body = format!(
            "{}\n{}",
            json_body,
            std::fs::read_to_string(markdown_path).unwrap()
        );
        assert!(!body.contains("secret review prompt"));
        assert!(!body.contains("secret review failing command"));
        assert!(!body.contains("secret review failing output"));
        assert!(!body.contains("secret review fixed command"));
        assert!(!body.contains("secret review fixed output"));
        assert!(body.contains("No memory write is authorized"));
    }

    #[test]
    fn observer_review_decision_records_private_decision_without_memory_write() {
        let tmp = tempfile::tempdir().unwrap();
        let log = tmp.path().join("observations.jsonl");
        let out_dir = tmp.path().join("review");
        let decisions = out_dir.join("decisions.jsonl");
        write_jsonl(
            &log,
            &[json!({
                "ts": 1.0,
                "sid": TEST_SID,
                "ev": "UserPromptSubmit",
                "prompt": "不对，应该改成 secret decision prompt"
            })],
        );
        let packet = observer_review_packet_for_paths(
            &log,
            &out_dir,
            20,
            Some("tester"),
            1_780_747_020,
            true,
        )
        .unwrap();
        let packet_json = PathBuf::from(packet["json_path"].as_str().unwrap());

        let dry_run = observer_review_decision_for_paths(
            &packet_json,
            &decisions,
            "instinct-candidate-0001",
            "approve",
            Some("tester"),
            Some("stable reusable lesson"),
            1_780_747_021,
            false,
        )
        .unwrap();
        assert_eq!(dry_run["dry_run"], json!(true));
        assert_eq!(dry_run["written"], json!(false));
        assert_eq!(dry_run["writes_memory"], json!(false));
        assert!(!decisions.exists(), "dry-run must not create decisions log");

        let record = observer_review_decision_for_paths(
            &packet_json,
            &decisions,
            "instinct-candidate-0001",
            "approve",
            Some("tester"),
            Some("stable reusable lesson"),
            1_780_747_022,
            true,
        )
        .unwrap();
        assert_eq!(
            record["schema"],
            "agent_bridge.instinct_observer.phase1_review_decision.v0"
        );
        assert_eq!(record["written"], json!(true));
        assert_eq!(record["writes_decision_log"], json!(true));
        assert_eq!(record["writes_memory"], json!(false));
        assert_eq!(record["persists_review_queue"], json!(false));
        assert_eq!(
            record["candidate_can_enter_future_explicit_memory_write_preflight"],
            json!(true)
        );
        assert_eq!(mode_octal(&decisions).as_deref(), Some("600"));

        let body = std::fs::read_to_string(&decisions).unwrap();
        let rows: Vec<Value> = body
            .lines()
            .map(|line| serde_json::from_str(line).unwrap())
            .collect();
        assert_eq!(rows.len(), 1);
        assert_eq!(rows[0]["decision"], json!("approve"));
        assert_eq!(rows[0]["writes_memory"], json!(false));
        assert!(!body.contains("secret decision prompt"));
    }

    #[test]
    fn observer_review_inbox_merges_latest_decisions_without_memory_write() {
        let tmp = tempfile::tempdir().unwrap();
        let log = tmp.path().join("observations.jsonl");
        let out_dir = tmp.path().join("review");
        let decisions = out_dir.join("decisions.jsonl");
        write_jsonl(
            &log,
            &[
                json!({
                    "ts": 1.0,
                    "sid": TEST_SID,
                    "ev": "UserPromptSubmit",
                    "prompt": "不对，应该改成 secret inbox prompt"
                }),
                json!({
                    "ts": 2.0,
                    "sid": "019e0000-0000-7000-8000-000000000002",
                    "ev": "UserPromptSubmit",
                    "prompt": "不要使用 secret inbox second prompt"
                }),
            ],
        );
        let packet = observer_review_packet_for_paths(
            &log,
            &out_dir,
            20,
            Some("tester"),
            1_780_747_025,
            true,
        )
        .unwrap();
        let packet_json = PathBuf::from(packet["json_path"].as_str().unwrap());
        observer_review_decision_for_paths(
            &packet_json,
            &decisions,
            "instinct-candidate-0001",
            "approve",
            Some("tester"),
            Some("stable inbox lesson"),
            1_780_747_026,
            true,
        )
        .unwrap();

        let inbox = observer_review_inbox(Some(&packet_json), Some(&out_dir), Some(&decisions), 20)
            .unwrap();
        assert_eq!(
            inbox["schema"],
            "agent_bridge.instinct_observer.phase1_review_inbox.v0"
        );
        assert_eq!(inbox["read_only"], json!(true));
        assert_eq!(inbox["writes_memory"], json!(false));
        assert_eq!(inbox["candidate_count"], json!(2));
        assert_eq!(inbox["pending_count"], json!(1));
        assert_eq!(inbox["approved_count"], json!(1));
        assert_eq!(inbox["candidates"][0]["decision"], json!("approve"));
        assert_eq!(inbox["candidates"][1]["decision"], json!("pending"));
        let text = serde_json::to_string(&inbox).unwrap();
        assert!(!text.contains("secret inbox prompt"));
        assert!(!text.contains("secret inbox second prompt"));
    }

    #[test]
    fn observer_review_context_requires_explicit_local_excerpt() {
        let tmp = tempfile::tempdir().unwrap();
        let log = tmp.path().join("observations.jsonl");
        let out_dir = tmp.path().join("review");
        write_jsonl(
            &log,
            &[json!({
                "ts": 1.0,
                "sid": TEST_SID,
                "ev": "UserPromptSubmit",
                "prompt": "不对，应该改成 secret context prompt"
            })],
        );
        let packet = observer_review_packet_for_paths(
            &log,
            &out_dir,
            20,
            Some("tester"),
            1_780_747_027,
            true,
        )
        .unwrap();
        let packet_json = PathBuf::from(packet["json_path"].as_str().unwrap());

        let redacted =
            observer_review_context_for_paths(&packet_json, "instinct-candidate-0001", &log, false)
                .unwrap();
        assert_eq!(
            redacted["schema"],
            "agent_bridge.instinct_observer.phase1_review_context.v0"
        );
        assert_eq!(redacted["read_only"], json!(true));
        assert_eq!(redacted["writes_memory"], json!(false));
        assert_eq!(redacted["writes_decision"], json!(false));
        assert_eq!(
            redacted["local_log_match"]["raw_prompt_included"],
            json!(false)
        );
        assert_eq!(redacted["local_log_match"]["prompt_excerpt"], Value::Null);
        assert!(!serde_json::to_string(&redacted)
            .unwrap()
            .contains("secret context prompt"));

        let included =
            observer_review_context_for_paths(&packet_json, "instinct-candidate-0001", &log, true)
                .unwrap();
        assert_eq!(
            included["local_log_match"]["raw_prompt_included"],
            json!(true)
        );
        assert!(serde_json::to_string(&included)
            .unwrap()
            .contains("secret context prompt"));
    }

    #[test]
    fn observer_memory_preflight_requires_approved_decision_and_human_draft() {
        let tmp = tempfile::tempdir().unwrap();
        let log = tmp.path().join("observations.jsonl");
        let out_dir = tmp.path().join("review");
        let decisions = out_dir.join("decisions.jsonl");
        write_jsonl(
            &log,
            &[json!({
                "ts": 1.0,
                "sid": TEST_SID,
                "ev": "UserPromptSubmit",
                "prompt": "应该改成 secret preflight prompt"
            })],
        );
        let packet = observer_review_packet_for_paths(
            &log,
            &out_dir,
            20,
            Some("tester"),
            1_780_747_030,
            true,
        )
        .unwrap();
        let packet_json = PathBuf::from(packet["json_path"].as_str().unwrap());

        let blocked = observer_memory_preflight_for_paths(
            &packet_json,
            &decisions,
            &out_dir,
            "instinct-candidate-0001",
            Some("lesson:instinct-test"),
            Some("lesson"),
            Some("Human-authored reusable lesson."),
            1_780_747_031,
            false,
        )
        .unwrap();
        assert_eq!(blocked["approved_by_human_decision"], json!(false));
        assert_eq!(blocked["ready_for_separate_memory_write"], json!(false));
        assert_eq!(blocked["writes_memory"], json!(false));
        assert_eq!(
            blocked["blocked_reasons"],
            json!(["latest_decision_is_not_approve"])
        );

        observer_review_decision_for_paths(
            &packet_json,
            &decisions,
            "instinct-candidate-0001",
            "approve",
            Some("tester"),
            Some("stable enough"),
            1_780_747_032,
            true,
        )
        .unwrap();

        let preflight = observer_memory_preflight_for_paths(
            &packet_json,
            &decisions,
            &out_dir,
            "instinct-candidate-0001",
            Some("lesson:instinct-test"),
            Some("lesson"),
            Some("Human-authored reusable lesson."),
            1_780_747_033,
            true,
        )
        .unwrap();
        assert_eq!(preflight["approved_by_human_decision"], json!(true));
        assert_eq!(preflight["draft_complete"], json!(true));
        assert_eq!(preflight["ready_for_separate_memory_write"], json!(true));
        assert_eq!(preflight["writes_memory"], json!(false));
        assert_eq!(preflight["written"], json!(true));

        let json_path = PathBuf::from(preflight["json_path"].as_str().unwrap());
        let markdown_path = PathBuf::from(preflight["markdown_path"].as_str().unwrap());
        assert!(json_path.exists());
        assert!(markdown_path.exists());
        assert_eq!(mode_octal(&json_path).as_deref(), Some("600"));
        assert_eq!(mode_octal(&markdown_path).as_deref(), Some("600"));
        let body = format!(
            "{}\n{}",
            std::fs::read_to_string(json_path).unwrap(),
            std::fs::read_to_string(markdown_path).unwrap()
        );
        assert!(!body.contains("secret preflight prompt"));
        assert!(body.contains("Human-authored reusable lesson."));
        assert!(body.contains("This packet does not write memory"));
    }

    #[test]
    fn observer_memory_write_plan_requires_ready_preflight() {
        let tmp = tempfile::tempdir().unwrap();
        let log = tmp.path().join("observations.jsonl");
        let out_dir = tmp.path().join("review");
        let decisions = out_dir.join("decisions.jsonl");
        write_jsonl(
            &log,
            &[json!({
                "ts": 1.0,
                "sid": TEST_SID,
                "ev": "UserPromptSubmit",
                "prompt": "不对，应该改成 secret write prompt"
            })],
        );
        let packet = observer_review_packet_for_paths(
            &log,
            &out_dir,
            20,
            Some("tester"),
            1_780_747_040,
            true,
        )
        .unwrap();
        let packet_json = PathBuf::from(packet["json_path"].as_str().unwrap());
        observer_review_decision_for_paths(
            &packet_json,
            &decisions,
            "instinct-candidate-0001",
            "approve",
            Some("tester"),
            Some("stable enough"),
            1_780_747_041,
            true,
        )
        .unwrap();
        let preflight = observer_memory_preflight_for_paths(
            &packet_json,
            &decisions,
            &out_dir,
            "instinct-candidate-0001",
            Some("lesson:instinct-write-test"),
            Some("lesson"),
            Some("Human-authored memory body."),
            1_780_747_042,
            true,
        )
        .unwrap();
        let preflight_json = PathBuf::from(preflight["json_path"].as_str().unwrap());

        let preview =
            observer_memory_write_plan_for_path(&preflight_json, 1_780_747_043, false).unwrap();
        assert_eq!(
            preview["schema"],
            "agent_bridge.instinct_observer.phase1_memory_write_plan.v0"
        );
        assert_eq!(preview["writes_memory"], json!(false));
        assert_eq!(
            preview["memory_record"]["key"],
            json!("lesson:instinct-write-test")
        );

        let write_plan =
            observer_memory_write_plan_for_path(&preflight_json, 1_780_747_044, true).unwrap();
        assert_eq!(write_plan["writes_memory"], json!(true));
        assert_eq!(write_plan["memory_record"]["kind"], json!("lesson"));
        assert_eq!(
            write_plan["memory_record"]["content"],
            json!("Human-authored memory body.")
        );
        let text = serde_json::to_string(&write_plan).unwrap();
        assert!(!text.contains("secret write prompt"));
    }

    #[test]
    fn observer_review_status_summarizes_packets_decisions_and_preflights() {
        let tmp = tempfile::tempdir().unwrap();
        let log = tmp.path().join("observations.jsonl");
        let out_dir = tmp.path().join("review");
        let decisions = out_dir.join("decisions.jsonl");
        let receipts = out_dir.join("memory-writes.jsonl");
        write_jsonl(
            &log,
            &[json!({
                "ts": 1.0,
                "sid": TEST_SID,
                "ev": "UserPromptSubmit",
                "prompt": "不对，应该改成 secret status prompt"
            })],
        );
        let packet = observer_review_packet_for_paths(
            &log,
            &out_dir,
            20,
            Some("tester"),
            1_780_747_050,
            true,
        )
        .unwrap();
        let packet_json = PathBuf::from(packet["json_path"].as_str().unwrap());
        observer_review_decision_for_paths(
            &packet_json,
            &decisions,
            "instinct-candidate-0001",
            "approve",
            Some("tester"),
            Some("stable enough"),
            1_780_747_051,
            true,
        )
        .unwrap();
        let preflight = observer_memory_preflight_for_paths(
            &packet_json,
            &decisions,
            &out_dir,
            "instinct-candidate-0001",
            Some("lesson:instinct-status-test"),
            Some("lesson"),
            Some("Human-authored status lesson."),
            1_780_747_052,
            true,
        )
        .unwrap();
        let preflight_json = PathBuf::from(preflight["json_path"].as_str().unwrap());
        let receipt = observer_memory_write_receipt_for_paths(
            &preflight_json,
            &receipts,
            "lesson:instinct-status-test",
            tmp.path().join("state.db").as_path(),
            1_780_747_053,
        )
        .unwrap();
        assert_eq!(receipt["memory_key"], json!("lesson:instinct-status-test"));
        assert_eq!(mode_octal(&receipts).as_deref(), Some("600"));

        let status = observer_review_status_for_paths(&out_dir, &decisions, &receipts, 10).unwrap();
        assert_eq!(
            status["schema"],
            "agent_bridge.instinct_observer.phase1_review_status.v0"
        );
        assert_eq!(status["read_only"], json!(true));
        assert_eq!(status["writes_memory"], json!(false));
        assert_eq!(status["packet_count"], json!(1));
        assert_eq!(status["decision_count"], json!(1));
        assert_eq!(status["preflight_count"], json!(1));
        assert_eq!(status["ready_preflight_count"], json!(1));
        assert_eq!(status["memory_write_receipt_count"], json!(1));
        assert_eq!(status["decision_counts"]["approve"], json!(1));
        assert_eq!(
            status["latest_preflights"][0]["memory_key"],
            json!("lesson:instinct-status-test")
        );
        assert_eq!(
            status["latest_memory_write_receipts"][0]["memory_key"],
            json!("lesson:instinct-status-test")
        );
        let text = serde_json::to_string(&status).unwrap();
        assert!(!text.contains("secret status prompt"));
    }

    #[test]
    fn observer_log_rotation_dry_run_preserves_log() {
        let tmp = tempfile::tempdir().unwrap();
        let log = tmp.path().join("observations.jsonl");
        write_jsonl(
            &log,
            &[json!({"ts": 1.0, "sid": "s", "ev": "UserPromptSubmit", "prompt": "hello"})],
        );

        let plan = rotate_observer_log_for_path(&log, 1_780_747_000, true).unwrap();

        assert_eq!(
            plan["schema"],
            "agent_bridge_instinct_observer_log_rotation.v0"
        );
        assert_eq!(plan["dry_run"], json!(true));
        assert_eq!(plan["action"], "rotate_log");
        assert_eq!(plan["status"], "would_rotate");
        assert_eq!(plan["log_exists"], json!(true));
        assert_eq!(plan["log_bytes"].as_u64().unwrap() > 0, true);
        assert!(log.exists(), "dry-run must not move the live log");
        let archive = PathBuf::from(plan["archive_path"].as_str().unwrap());
        assert!(!archive.exists(), "dry-run must not create archive");
    }

    #[test]
    fn observer_log_rotation_moves_log_to_timestamped_archive() {
        let tmp = tempfile::tempdir().unwrap();
        let log = tmp.path().join("observations.jsonl");
        write_jsonl(
            &log,
            &[json!({"ts": 1.0, "sid": "s", "ev": "UserPromptSubmit", "prompt": "hello"})],
        );
        let original = std::fs::read_to_string(&log).unwrap();

        let plan = rotate_observer_log_for_path(&log, 1_780_747_001, false).unwrap();

        assert_eq!(
            plan["schema"],
            "agent_bridge_instinct_observer_log_rotation.v0"
        );
        assert_eq!(plan["dry_run"], json!(false));
        assert_eq!(plan["action"], "rotate_log");
        assert_eq!(plan["status"], "rotated");
        assert_eq!(plan["log_exists"], json!(true));
        assert!(!log.exists(), "rotation leaves hook to recreate live log");
        let archive = PathBuf::from(plan["archive_path"].as_str().unwrap());
        assert!(archive.exists(), "archive must be created by rename");
        assert_eq!(std::fs::read_to_string(archive).unwrap(), original);
    }
}
