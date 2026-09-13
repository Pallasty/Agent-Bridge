//! Deterministic WorktreeSession plans and presentation of completed Git output.

use std::path::{Path, PathBuf};

pub(crate) struct SessionPlan {
    pub(crate) branch: String,
    pub(crate) path: PathBuf,
}

pub(crate) fn plan_new_session(repo_root: &Path, name: Option<&str>, ts: u64) -> SessionPlan {
    let name_part = name
        .map(|s| {
            s.chars()
                .map(|c| {
                    if c.is_ascii_alphanumeric() || c == '-' || c == '_' {
                        c
                    } else {
                        '-'
                    }
                })
                .collect::<String>()
        })
        .filter(|s| !s.is_empty())
        .unwrap_or_else(|| "anon".to_string());
    let slug = format!("{name_part}-{ts}");
    let branch = format!("session/{slug}");
    let dir_name = format!("session-{slug}");
    let path = repo_root.join(".worktrees").join(&dir_name);
    SessionPlan { branch, path }
}

pub(crate) fn render_session_rows(porcelain: &[u8]) -> i32 {
    // Porcelain blocks are separated by blank lines; each block has
    // `worktree <path>`, optional `HEAD <sha>`, optional `branch <ref>`.
    let mut shown = 0;
    let mut path = String::new();
    let mut head = String::new();
    let mut branch = String::new();
    for raw in String::from_utf8_lossy(porcelain).lines() {
        if raw.is_empty() {
            if path.contains("/.worktrees/session-") {
                println!("{path}  {branch}  {head}");
                shown += 1;
            }
            path.clear();
            head.clear();
            branch.clear();
            continue;
        }
        if let Some(rest) = raw.strip_prefix("worktree ") {
            path = rest.to_string();
        } else if let Some(rest) = raw.strip_prefix("HEAD ") {
            head = rest.chars().take(8).collect();
        } else if let Some(rest) = raw.strip_prefix("branch ") {
            branch = rest.to_string();
        }
    }
    // Flush any trailing block (porcelain output may end without trailing
    // blank line on some git versions).
    if path.contains("/.worktrees/session-") {
        println!("{path}  {branch}  {head}");
        shown += 1;
    }
    shown
}
