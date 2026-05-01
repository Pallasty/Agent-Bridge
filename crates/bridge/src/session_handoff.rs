//! Structured session handoff brief (W3): aggregate git snapshot + memory rows
//! without new tables — see DESIGN-warp-first-agent-shell.md (D9).

use ab_core::Result;
use ab_store::{MemoryListSort, MemoryRecord, StateStore};
use serde_json::{json, Value};
use std::path::{Path, PathBuf};
use std::process::Command;
use std::sync::Arc;

/// Collect a machine-readable handoff brief for the next agent session.
pub async fn build_handoff_brief(
    store: Arc<dyn StateStore>,
    cwd: PathBuf,
    max_todos: u32,
    max_handoff_memories: u32,
    last_task: Option<String>,
    status: Option<String>,
    open_questions: Vec<String>,
    conversation_text: Option<String>,
) -> Result<Value> {
    let git = tokio::task::spawn_blocking({
        let cwd = cwd.clone();
        move || collect_git_snapshot(&cwd)
    })
    .await
    .map_err(|e| ab_core::Error::Backend(format!("handoff git task: {e}")))?;

    let todos = store
        .list_memories(Some("todo"), MemoryListSort::ByImportance, max_todos)
        .await?;
    let handoffs = store
        .list_memories(
            Some("session_handoff"),
            MemoryListSort::Newest,
            max_handoff_memories,
        )
        .await?;

    let pending_items: Vec<String> = todos.iter().map(memory_one_liner).collect();
    let handoff_notes: Vec<Value> = handoffs.iter().map(memory_to_json).collect();
    let key_files: Vec<String> = git.key_files_modified.clone();

    let conversation_snippet = conversation_text.map(|s| clip_chars(&s, 4000));

    Ok(json!({
        "last_task": last_task,
        "status": status,
        "pending_items": pending_items,
        "key_files_modified": key_files,
        "active_branch": git.active_branch,
        "recent_commit": git.recent_commit,
        "open_questions": open_questions,
        "generated_at": utc_now_iso_stamp(),
        "git": {
            "is_repo": git.is_repo,
            "clean": git.clean,
            "porcelain": git.porcelain_lines,
        },
        "session_handoff_memories": handoff_notes,
        "conversation_snippet": conversation_snippet,
    }))
}

fn memory_one_liner(m: &MemoryRecord) -> String {
    let t = m.content.trim();
    let clipped = clip_chars(t, 500);
    if clipped.chars().count() < t.chars().count() {
        format!("{clipped}…")
    } else {
        clipped
    }
}

fn memory_to_json(m: &MemoryRecord) -> Value {
    json!({
        "key": m.key,
        "content": m.content,
        "tags": m.tags,
        "scope": m.scope,
        "updated_at": m.updated_at,
    })
}

fn clip_chars(s: &str, max: usize) -> String {
    let mut out = String::new();
    for (i, c) in s.chars().enumerate() {
        if i >= max {
            break;
        }
        out.push(c);
    }
    out
}

struct GitSnapshot {
    is_repo: bool,
    active_branch: Option<String>,
    recent_commit: Option<String>,
    clean: Option<bool>,
    porcelain_lines: Vec<String>,
    key_files_modified: Vec<String>,
}

fn collect_git_snapshot(cwd: &Path) -> GitSnapshot {
    if !cwd.is_dir() {
        return GitSnapshot {
            is_repo: false,
            active_branch: None,
            recent_commit: None,
            clean: None,
            porcelain_lines: vec![],
            key_files_modified: vec![],
        };
    }

    let inside = git_output(cwd, &["rev-parse", "--is-inside-work-tree"]);
    let is_repo = inside
        .as_deref()
        .map(|s| s.trim() == "true")
        .unwrap_or(false);

    if !is_repo {
        return GitSnapshot {
            is_repo: false,
            active_branch: None,
            recent_commit: None,
            clean: None,
            porcelain_lines: vec![],
            key_files_modified: vec![],
        };
    }

    let branch = git_output(cwd, &["rev-parse", "--abbrev-ref", "HEAD"])
        .map(|s| s.trim().to_string())
        .filter(|s| !s.is_empty());

    let recent_commit = git_output(cwd, &["log", "-1", "--oneline"]).map(|s| s.trim().to_string());

    let porcelain_raw = git_output(cwd, &["status", "--porcelain"]).unwrap_or_default();
    let porcelain_lines: Vec<String> = porcelain_raw
        .lines()
        .map(|l| l.to_string())
        .filter(|l| !l.is_empty())
        .collect();

    let clean = Some(porcelain_lines.is_empty());
    let key_files_modified = paths_from_porcelain(&porcelain_lines);

    GitSnapshot {
        is_repo: true,
        active_branch: branch,
        recent_commit,
        clean,
        porcelain_lines,
        key_files_modified,
    }
}

fn git_output(cwd: &Path, args: &[&str]) -> Option<String> {
    let out = Command::new("git")
        .current_dir(cwd)
        .args(args)
        .output()
        .ok()?;
    if !out.status.success() {
        return None;
    }
    Some(String::from_utf8_lossy(&out.stdout).into_owned())
}

/// After the two status columns (index + worktree), optional whitespace, then path.
fn paths_from_porcelain(lines: &[String]) -> Vec<String> {
    let mut out: Vec<String> = Vec::new();
    for line in lines {
        let t = line.trim();
        if t.len() < 3 {
            continue;
        }
        let rest = t[2..].trim_start();
        if rest.is_empty() {
            continue;
        }
        if rest.contains(" -> ") {
            if let Some(p) = rest.split(" -> ").last() {
                out.push(p.trim().to_string());
            }
        } else {
            out.push(rest.to_string());
        }
    }
    out.sort();
    out.dedup();
    out
}

fn utc_now_iso_stamp() -> String {
    Command::new("date")
        .args(["-u", "+%Y-%m-%dT%H:%M:%SZ"])
        .output()
        .ok()
        .filter(|o| o.status.success())
        .map(|o| String::from_utf8_lossy(&o.stdout).trim().to_string())
        .filter(|s| !s.is_empty())
        .unwrap_or_else(|| "1970-01-01T00:00:00Z".to_string())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn paths_from_porcelain_parses_simple() {
        let lines = vec![" M crates/a.rs".to_string(), "?? new.txt".to_string()];
        let p = paths_from_porcelain(&lines);
        assert!(p.contains(&"crates/a.rs".to_string()));
        assert!(p.contains(&"new.txt".to_string()));
    }
}
