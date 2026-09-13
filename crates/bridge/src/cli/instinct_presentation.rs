//! Presentation of completed Instinct reports; acquisition and writes stay at the root.

use anyhow::Result;
use serde_json::Value;

pub(crate) fn render_candidates(preview: &Value, as_json: bool) -> Result<()> {
    if as_json {
        println!("{}", serde_json::to_string_pretty(&preview)?);
    } else {
        println!(
            "instinct observer candidates: status={} count={} gate={} next={}",
            preview
                .get("status")
                .and_then(|v| v.as_str())
                .unwrap_or("unknown"),
            preview
                .get("candidate_count")
                .and_then(|v| v.as_u64())
                .unwrap_or(0),
            preview
                .pointer("/density_gate/verdict")
                .and_then(|v| v.as_str())
                .unwrap_or("unknown"),
            preview
                .get("recommended_next_step")
                .and_then(|v| v.as_str())
                .unwrap_or("unknown"),
        );
        if let Some(candidates) = preview.get("candidates").and_then(|v| v.as_array()) {
            for candidate in candidates.iter().take(10) {
                println!(
                    "- {} {} session={} state={}",
                    candidate
                        .get("candidate_id")
                        .and_then(|v| v.as_str())
                        .unwrap_or("?"),
                    candidate
                        .get("kind")
                        .and_then(|v| v.as_str())
                        .unwrap_or("?"),
                    candidate
                        .get("session_id")
                        .and_then(|v| v.as_str())
                        .unwrap_or("?"),
                    candidate
                        .get("review_state")
                        .and_then(|v| v.as_str())
                        .unwrap_or("?"),
                );
            }
        }
    }
    Ok(())
}

pub(crate) fn render_review_packet(packet: &Value, as_json: bool) -> Result<()> {
    if as_json {
        println!("{}", serde_json::to_string_pretty(&packet)?);
    } else {
        println!(
            "instinct review packet: status={} candidates={} written={} next={}",
            packet
                .get("status")
                .and_then(|v| v.as_str())
                .unwrap_or("unknown"),
            packet
                .get("candidate_count")
                .and_then(|v| v.as_u64())
                .unwrap_or(0),
            packet
                .get("written")
                .and_then(|v| v.as_bool())
                .unwrap_or(false),
            packet
                .get("recommended_next_step")
                .and_then(|v| v.as_str())
                .unwrap_or("unknown"),
        );
        println!(
            "json={} markdown={} memory_write={}",
            packet
                .get("json_path")
                .and_then(|v| v.as_str())
                .unwrap_or("-"),
            packet
                .get("markdown_path")
                .and_then(|v| v.as_str())
                .unwrap_or("-"),
            packet
                .get("writes_memory")
                .and_then(|v| v.as_bool())
                .unwrap_or(false),
        );
    }
    Ok(())
}

pub(crate) fn render_review_decision(record: &Value, as_json: bool) -> Result<()> {
    if as_json {
        println!("{}", serde_json::to_string_pretty(&record)?);
    } else {
        println!(
            "instinct review decision: status={} candidate={} decision={} written={} memory_write={}",
            record
                .get("status")
                .and_then(|v| v.as_str())
                .unwrap_or("unknown"),
            record
                .get("candidate_id")
                .and_then(|v| v.as_str())
                .unwrap_or("?"),
            record
                .get("decision")
                .and_then(|v| v.as_str())
                .unwrap_or("?"),
            record
                .get("written")
                .and_then(|v| v.as_bool())
                .unwrap_or(false),
            record
                .get("writes_memory")
                .and_then(|v| v.as_bool())
                .unwrap_or(false),
        );
        println!(
            "decisions={} next={}",
            record
                .get("decisions_path")
                .and_then(|v| v.as_str())
                .unwrap_or("-"),
            record
                .get("recommended_next_step")
                .and_then(|v| v.as_str())
                .unwrap_or("unknown"),
        );
    }
    Ok(())
}

pub(crate) fn render_memory_preflight(packet: &Value, as_json: bool) -> Result<()> {
    if as_json {
        println!("{}", serde_json::to_string_pretty(&packet)?);
    } else {
        println!(
            "instinct memory preflight: status={} candidate={} approved={} ready={} written={} memory_write={}",
            packet
                .get("status")
                .and_then(|v| v.as_str())
                .unwrap_or("unknown"),
            packet
                .get("candidate_id")
                .and_then(|v| v.as_str())
                .unwrap_or("?"),
            packet
                .get("approved_by_human_decision")
                .and_then(|v| v.as_bool())
                .unwrap_or(false),
            packet
                .get("ready_for_separate_memory_write")
                .and_then(|v| v.as_bool())
                .unwrap_or(false),
            packet
                .get("written")
                .and_then(|v| v.as_bool())
                .unwrap_or(false),
            packet
                .get("writes_memory")
                .and_then(|v| v.as_bool())
                .unwrap_or(false),
        );
        println!(
            "json={} markdown={} next={}",
            packet
                .get("json_path")
                .and_then(|v| v.as_str())
                .unwrap_or("-"),
            packet
                .get("markdown_path")
                .and_then(|v| v.as_str())
                .unwrap_or("-"),
            packet
                .get("recommended_next_step")
                .and_then(|v| v.as_str())
                .unwrap_or("unknown"),
        );
    }
    Ok(())
}

pub(crate) fn render_memory_write(plan: &Value, write: bool, as_json: bool) -> Result<()> {
    if as_json {
        println!("{}", serde_json::to_string_pretty(&plan)?);
    } else {
        println!(
            "instinct memory write: status={} key={} write={} memory_write={}",
            plan.get("status")
                .and_then(|v| v.as_str())
                .unwrap_or("unknown"),
            plan.pointer("/memory_record/key")
                .and_then(|v| v.as_str())
                .or_else(|| plan.get("saved_memory_key").and_then(|v| v.as_str()))
                .unwrap_or("-"),
            write,
            plan.get("writes_memory")
                .and_then(|v| v.as_bool())
                .unwrap_or(false),
        );
        println!(
            "db={} receipt={} next={}",
            plan.get("db_path").and_then(|v| v.as_str()).unwrap_or("-"),
            plan.pointer("/receipt/receipts_path")
                .and_then(|v| v.as_str())
                .unwrap_or("-"),
            plan.get("recommended_next_step")
                .and_then(|v| v.as_str())
                .unwrap_or("unknown"),
        );
    }
    Ok(())
}

pub(crate) fn render_review_status(status: &Value, as_json: bool) -> Result<()> {
    if as_json {
        println!("{}", serde_json::to_string_pretty(&status)?);
    } else {
        println!(
            "instinct review status: packets={} decisions={} preflights={} ready={} receipts={} parse_errors={} memory_write={}",
            status
                .get("packet_count")
                .and_then(|v| v.as_u64())
                .unwrap_or(0),
            status
                .get("decision_count")
                .and_then(|v| v.as_u64())
                .unwrap_or(0),
            status
                .get("preflight_count")
                .and_then(|v| v.as_u64())
                .unwrap_or(0),
            status
                .get("ready_preflight_count")
                .and_then(|v| v.as_u64())
                .unwrap_or(0),
            status
                .get("memory_write_receipt_count")
                .and_then(|v| v.as_u64())
                .unwrap_or(0),
            status
                .get("parse_error_count")
                .and_then(|v| v.as_u64())
                .unwrap_or(0),
            status
                .get("writes_memory")
                .and_then(|v| v.as_bool())
                .unwrap_or(false),
        );
        println!(
            "review_dir={} decisions={} receipts={}",
            status
                .get("review_dir")
                .and_then(|v| v.as_str())
                .unwrap_or("-"),
            status
                .get("decisions_path")
                .and_then(|v| v.as_str())
                .unwrap_or("-"),
            status
                .get("receipts_path")
                .and_then(|v| v.as_str())
                .unwrap_or("-"),
        );
    }
    Ok(())
}

pub(crate) fn render_review_inbox(inbox: &Value, limit: usize, as_json: bool) -> Result<()> {
    if as_json {
        println!("{}", serde_json::to_string_pretty(&inbox)?);
    } else {
        println!(
            "instinct review inbox: packet={} candidates={} pending={} approved={} rejected={} deferred={} memory_write={}",
            inbox
                .get("packet_id")
                .and_then(|v| v.as_str())
                .unwrap_or("-"),
            inbox
                .get("candidate_count")
                .and_then(|v| v.as_u64())
                .unwrap_or(0),
            inbox
                .get("pending_count")
                .and_then(|v| v.as_u64())
                .unwrap_or(0),
            inbox
                .get("approved_count")
                .and_then(|v| v.as_u64())
                .unwrap_or(0),
            inbox
                .get("rejected_count")
                .and_then(|v| v.as_u64())
                .unwrap_or(0),
            inbox
                .get("deferred_count")
                .and_then(|v| v.as_u64())
                .unwrap_or(0),
            inbox
                .get("writes_memory")
                .and_then(|v| v.as_bool())
                .unwrap_or(false),
        );
        println!(
            "packet_json={} decisions={}",
            inbox
                .get("packet_json")
                .and_then(|v| v.as_str())
                .unwrap_or("-"),
            inbox
                .get("decisions_path")
                .and_then(|v| v.as_str())
                .unwrap_or("-"),
        );
        if let Some(candidates) = inbox.get("candidates").and_then(|v| v.as_array()) {
            for candidate in candidates.iter().take(limit) {
                println!(
                    "{} kind={} decision={} session={} cues={}",
                    candidate
                        .get("candidate_id")
                        .and_then(|v| v.as_str())
                        .unwrap_or("-"),
                    candidate
                        .get("kind")
                        .and_then(|v| v.as_str())
                        .unwrap_or("-"),
                    candidate
                        .get("decision")
                        .and_then(|v| v.as_str())
                        .unwrap_or("-"),
                    candidate
                        .get("session_id")
                        .and_then(|v| v.as_str())
                        .unwrap_or("-"),
                    candidate
                        .get("matched_cues")
                        .and_then(|v| v.as_array())
                        .map(|items| {
                            items
                                .iter()
                                .filter_map(|v| v.as_str())
                                .collect::<Vec<_>>()
                                .join(",")
                        })
                        .unwrap_or_else(|| "-".to_string()),
                );
            }
        }
    }
    Ok(())
}

pub(crate) fn render_review_context(
    context: &Value,
    include_local_excerpt: bool,
    as_json: bool,
) -> Result<()> {
    if as_json {
        println!("{}", serde_json::to_string_pretty(&context)?);
    } else {
        println!(
            "instinct review context: packet={} candidate={} kind={} session={} excerpt_included={} memory_write={}",
            context
                .get("packet_id")
                .and_then(|v| v.as_str())
                .unwrap_or("-"),
            context
                .get("candidate_id")
                .and_then(|v| v.as_str())
                .unwrap_or("-"),
            context
                .pointer("/candidate/kind")
                .and_then(|v| v.as_str())
                .unwrap_or("-"),
            context
                .pointer("/candidate/session_id")
                .and_then(|v| v.as_str())
                .unwrap_or("-"),
            context
                .pointer("/local_log_match/raw_prompt_included")
                .and_then(|v| v.as_bool())
                .unwrap_or(false),
            context
                .get("writes_memory")
                .and_then(|v| v.as_bool())
                .unwrap_or(false),
        );
        println!(
            "matched_cues={} prompt_chars={} local_log_found={} next={}",
            context
                .pointer("/candidate/matched_cues")
                .and_then(|v| v.as_array())
                .map(|items| {
                    items
                        .iter()
                        .filter_map(|v| v.as_str())
                        .collect::<Vec<_>>()
                        .join(",")
                })
                .unwrap_or_else(|| "-".to_string()),
            context
                .pointer("/candidate/prompt_chars")
                .and_then(|v| v.as_u64())
                .map(|n| n.to_string())
                .unwrap_or_else(|| "-".to_string()),
            context
                .pointer("/local_log_match/found")
                .and_then(|v| v.as_bool())
                .unwrap_or(false),
            context
                .get("recommended_next_step")
                .and_then(|v| v.as_str())
                .unwrap_or("unknown"),
        );
        if include_local_excerpt {
            if let Some(excerpt) = context
                .pointer("/local_log_match/prompt_excerpt")
                .and_then(|v| v.as_str())
            {
                println!("local_prompt_excerpt={excerpt}");
            }
        }
    }
    Ok(())
}

pub(crate) fn render_rotate_log(plan: &Value, as_json: bool) -> Result<()> {
    if as_json {
        println!("{}", serde_json::to_string_pretty(&plan)?);
    } else {
        println!(
            "instinct observer log: {} {} -> {}",
            plan.get("status")
                .and_then(|v| v.as_str())
                .unwrap_or("unknown"),
            plan.get("log_path").and_then(|v| v.as_str()).unwrap_or(""),
            plan.get("archive_path")
                .and_then(|v| v.as_str())
                .unwrap_or("")
        );
    }
    Ok(())
}
