//! Structured session handoff brief (W3): aggregate git snapshot + memory rows
//! without new tables — see DESIGN-warp-first-agent-shell.md (D9).

use ab_core::Result;
use ab_store::{MemoryListSort, MemoryRecord, StateStore};
use serde_json::{json, Value};
use std::path::{Path, PathBuf};
use std::process::Command;
use std::sync::Arc;

const HANDOFF_CANDIDATE_LIMIT: u32 = 256;

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

    let cwd_text = cwd.to_string_lossy();
    let project_path = cwd_text.trim_end_matches('/');
    let expected_scope = format!("project:{project_path}");
    // Store visibility includes global and ancestor rows, so it is only a
    // coarse filter. A raw cwd with a trailing slash also admits stored
    // project scopes with or without that slash before exact filtering.
    let candidate_context = format!("{project_path}/");
    let todos = if max_todos == 0 {
        Vec::new()
    } else {
        store
            .list_memories_in_scope(
                &candidate_context,
                Some("todo"),
                MemoryListSort::ByImportance,
                HANDOFF_CANDIDATE_LIMIT,
            )
            .await?
    };
    let handoffs = if max_handoff_memories == 0 {
        Vec::new()
    } else {
        store
            .list_memories_in_scope(
                &candidate_context,
                Some("session_handoff"),
                MemoryListSort::Newest,
                HANDOFF_CANDIDATE_LIMIT,
            )
            .await?
    };
    // A full candidate window means more eligible rows may exist beyond it;
    // it is not a claim that another row definitely exists.
    let todo_candidate_limit_reached = todos.len() == HANDOFF_CANDIDATE_LIMIT as usize;
    let handoff_candidate_limit_reached = handoffs.len() == HANDOFF_CANDIDATE_LIMIT as usize;
    let pending_items: Vec<String> = todos
        .iter()
        .filter(|row| row.kind == "todo" && current_project_memory(row, &expected_scope))
        .take(max_todos as usize)
        .map(memory_one_liner)
        .collect();
    let handoff_notes: Vec<Value> = handoffs
        .iter()
        .filter(|row| {
            current_project_memory(row, &expected_scope)
                && crate::mcp_tools::bootstrap_handoff_priority_eligible(row, project_path)
        })
        .take(max_handoff_memories as usize)
        .map(memory_to_json)
        .collect();
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
        "candidate_limit_reached": {
            "todos": todo_candidate_limit_reached,
            "session_handoffs": handoff_candidate_limit_reached,
        },
        "conversation_snippet": conversation_snippet,
    }))
}

fn current_project_memory(row: &MemoryRecord, expected_scope: &str) -> bool {
    row.status == "active"
        && row.superseded_by.is_none()
        && row
            .scope
            .as_deref()
            .map(|scope| scope.trim_end_matches('/'))
            == Some(expected_scope)
        && !row.tags.iter().any(|tag| {
            tag.strip_prefix("continuity_confidence:")
                .is_some_and(|confidence| confidence.trim() == "stale")
        })
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
    use ab_store::{ImportConflictPolicy, SqliteStore};

    fn record(key: &str, kind: &str, scope: Option<&str>, rank: i64) -> MemoryRecord {
        MemoryRecord {
            key: key.into(),
            kind: kind.into(),
            content: key.into(),
            tags: if kind == "session_handoff" {
                vec!["continuity_role:state".into()]
            } else {
                vec![]
            },
            related_keys: vec![],
            scope: scope.map(str::to_string),
            created_at: rank,
            updated_at: 1_700_000_000,
            last_accessed_at: 17,
            access_count: 3,
            importance: rank as f64 / 1000.0,
            status: "active".into(),
            trigger_pattern: None,
            superseded_by: None,
        }
    }

    async fn import_records(
        dir: &tempfile::TempDir,
        records: &[MemoryRecord],
    ) -> Arc<dyn StateStore> {
        // macOS temp paths may begin with the /var symlink; honor the Store's
        // no-follow policy by resolving the existing fixture directory first.
        let db_path = dir
            .path()
            .canonicalize()
            .expect("canonical fixture directory")
            .join("state.db");
        let store = SqliteStore::open(&db_path)
            .await
            .expect("open fixture store");
        let jsonl = records
            .iter()
            .map(|row| serde_json::to_string(row).expect("serialize fixture"))
            .collect::<Vec<_>>()
            .join("\n");
        let import_path = dir.path().join("memories.jsonl");
        tokio::fs::write(&import_path, jsonl)
            .await
            .expect("write fixtures");
        let report = store
            .memory_import(&import_path, ImportConflictPolicy::Skip, None)
            .await
            .expect("import fixture rows");
        assert_eq!(report.inserted as usize, records.len());

        // Import preserves timestamps/status without memory_save's automatic
        // reconsolidation, but its wire path does not restore superseded_by.
        // Seed that retained-row edge case directly in this temporary DB.
        let pointers: Vec<_> = records
            .iter()
            .filter_map(|row| {
                row.superseded_by
                    .as_ref()
                    .map(|replacement| (row.key.clone(), replacement.clone()))
            })
            .collect();
        if !pointers.is_empty() {
            let conn = tokio_rusqlite::Connection::open(&db_path)
                .await
                .expect("open fixture pointer connection");
            conn.call(move |conn| -> tokio_rusqlite::rusqlite::Result<()> {
                for (key, replacement) in pointers {
                    conn.execute(
                        "UPDATE memories SET superseded_by = ?1 WHERE key = ?2",
                        [&replacement, &key],
                    )?;
                }
                Ok(())
            })
            .await
            .expect("seed fixture pointers");
        }
        Arc::new(store)
    }

    async fn brief(store: Arc<dyn StateStore>, cwd: &Path, limit: u32) -> Value {
        build_handoff_brief(
            store,
            cwd.to_path_buf(),
            limit,
            limit,
            None,
            None,
            vec![],
            None,
        )
        .await
        .expect("build fixture brief")
    }

    fn handoff_keys(value: &Value) -> Vec<&str> {
        value["session_handoff_memories"]
            .as_array()
            .expect("handoff array")
            .iter()
            .map(|row| row["key"].as_str().expect("handoff key"))
            .collect()
    }

    #[test]
    fn paths_from_porcelain_parses_simple() {
        let lines = vec![" M crates/a.rs".to_string(), "?? new.txt".to_string()];
        let p = paths_from_porcelain(&lines);
        assert!(p.contains(&"crates/a.rs".to_string()));
        assert!(p.contains(&"new.txt".to_string()));
    }

    #[tokio::test]
    async fn project_filter_precedes_output_caps_and_accepts_trailing_scope_slashes() {
        let dir = tempfile::tempdir().expect("fixture directory");
        let cwd = dir.path().join("project-current");
        let exact_scope = format!("project:{}", cwd.display());
        let trailing_scope = format!("{exact_scope}/");
        let ancestor = format!("project:{}", dir.path().display());
        // This sibling is a lexical prefix of cwd, exercising the scoped
        // Store SQL's broad LIKE match as well as the former unscoped read.
        let sibling = format!("project:{}", dir.path().join("project").display());
        let unrelated = format!("project:{}", dir.path().join("other").display());
        let mut rows = vec![];
        for kind in ["todo", "session_handoff"] {
            rows.push(record(
                &format!("{kind}-older"),
                kind,
                Some(&exact_scope),
                100,
            ));
            rows.push(record(
                &format!("{kind}-chosen"),
                kind,
                Some(&trailing_scope),
                200,
            ));
            for (index, scope) in [
                None,
                Some("global"),
                Some(ancestor.as_str()),
                Some(sibling.as_str()),
                Some(unrelated.as_str()),
                Some("domain:rust"),
            ]
            .into_iter()
            .enumerate()
            {
                rows.push(record(
                    &format!("{kind}-excluded-{index}"),
                    kind,
                    scope,
                    900,
                ));
            }
        }
        let store = import_records(&dir, &rows).await;
        let value = brief(store.clone(), &cwd, 1).await;
        assert_eq!(value["pending_items"], json!(["todo-chosen"]));
        assert_eq!(handoff_keys(&value), vec!["session_handoff-chosen"]);
        assert_eq!(
            value["candidate_limit_reached"],
            json!({"todos": false, "session_handoffs": false})
        );
        let slash_cwd = PathBuf::from(format!("{}/", cwd.display()));
        let slash_value = brief(store, &slash_cwd, 1).await;
        assert_eq!(slash_value["pending_items"], value["pending_items"]);
        assert_eq!(handoff_keys(&slash_value), handoff_keys(&value));
    }

    #[tokio::test]
    async fn stale_superseded_and_ineligible_rows_do_not_displace_current_state() {
        let dir = tempfile::tempdir().expect("fixture directory");
        let cwd = dir.path().join("project");
        let scope = format!("project:{}", cwd.display());
        let mut rows = vec![];
        for kind in ["todo", "session_handoff"] {
            rows.push(record(&format!("{kind}-current"), kind, Some(&scope), 100));
            let mut stale = record(&format!("{kind}-stale"), kind, Some(&scope), 900);
            stale.tags.push("continuity_confidence:stale".into());
            rows.push(stale);
            for status in ["superseded", "archived", "conflict"] {
                let mut row = record(&format!("{kind}-{status}"), kind, Some(&scope), 900);
                row.status = status.into();
                rows.push(row);
            }
            let mut pointer = record(&format!("{kind}-replaced"), kind, Some(&scope), 900);
            pointer.superseded_by = Some(format!("{kind}-current"));
            rows.push(pointer);
        }
        for (key, tags) in [
            ("auto", vec!["continuity_role:state", "auto_curated"]),
            (
                "unverified",
                vec!["continuity_role:state", "unverified_identifier"],
            ),
            (
                "background",
                vec![
                    "continuity_role:state",
                    "continuity_actionability:background",
                ],
            ),
            ("missing-metadata", vec![]),
        ] {
            let mut row = record(key, "session_handoff", Some(&scope), 900);
            row.tags = tags.into_iter().map(str::to_string).collect();
            rows.push(row);
        }
        let store = import_records(&dir, &rows).await;
        let value = brief(store, &cwd, 20).await;
        // A todo needs no continuity tags; a state handoff without an
        // explicit confidence keeps the existing bootstrap eligibility.
        assert_eq!(value["pending_items"], json!(["todo-current"]));
        assert_eq!(handoff_keys(&value), vec!["session_handoff-current"]);
    }

    #[tokio::test]
    async fn bounded_candidate_exhaustion_is_explicit_even_when_output_is_empty() {
        let dir = tempfile::tempdir().expect("fixture directory");
        let cwd = dir.path().join("project");
        let scope = format!("project:{}", cwd.display());
        let mut rows = vec![];
        for kind in ["todo", "session_handoff"] {
            rows.push(record(
                &format!("{kind}-beyond-cap"),
                kind,
                Some(&scope),
                100,
            ));
            for index in 0..256 {
                rows.push(record(
                    &format!("{kind}-global-{index}"),
                    kind,
                    Some("global"),
                    900,
                ));
            }
        }
        let store = import_records(&dir, &rows).await;
        // The caller's generous cap must not enlarge the bounded candidate
        // read. The exact-project row exists, but lies beyond this window.
        let value = brief(store, &cwd, 512).await;
        assert_eq!(value["pending_items"], json!([]));
        assert!(handoff_keys(&value).is_empty());
        assert_eq!(
            value["candidate_limit_reached"],
            json!({"todos": true, "session_handoffs": true})
        );
    }

    #[tokio::test]
    async fn brief_preserves_order_narrative_git_and_memory_without_read_side_effects() {
        let dir = tempfile::tempdir().expect("fixture directory");
        let cwd = dir.path().join("project");
        std::fs::create_dir(&cwd).expect("create project");
        assert!(Command::new("git")
            .args(["init", "-b", "handoff-test"])
            .current_dir(&cwd)
            .output()
            .expect("git init")
            .status
            .success());
        assert!(Command::new("git")
            .args([
                "-c",
                "user.name=Handoff Test",
                "-c",
                "user.email=handoff@example.invalid",
                "-c",
                "commit.gpgSign=false",
                "-c",
                "core.hooksPath=missing-test-hooks",
                "commit",
                "--allow-empty",
                "-m",
                "fixture"
            ])
            .current_dir(&cwd)
            .output()
            .expect("git commit")
            .status
            .success());
        std::fs::write(cwd.join("work.txt"), "pending work").expect("fixture change");
        let scope = format!("project:{}", cwd.display());
        let mut rows = vec![];
        for kind in ["todo", "session_handoff"] {
            for rank in [100, 300, 200] {
                rows.push(record(&format!("{kind}-{rank}"), kind, Some(&scope), rank));
            }
        }
        let store = import_records(&dir, &rows).await;
        store
            .memory_link("todo-300", "session_handoff-300", "related", 0.7)
            .await
            .expect("fixture edge");
        let mut before = vec![];
        for row in &rows {
            before.push(
                serde_json::to_value(store.memory_peek(&row.key).await.expect("peek before"))
                    .expect("serialize before"),
            );
        }
        let edges_before = serde_json::to_value(
            store
                .memory_neighbors("todo-300")
                .await
                .expect("edges before"),
        )
        .expect("serialize edges");
        let value = build_handoff_brief(
            store.clone(),
            cwd.clone(),
            2,
            2,
            Some("current task".into()),
            Some("in_progress".into()),
            vec!["open question".into()],
            Some("语".repeat(4002)),
        )
        .await
        .expect("build narrative brief");
        assert_eq!(value["pending_items"], json!(["todo-300", "todo-200"]));
        assert_eq!(
            handoff_keys(&value),
            vec!["session_handoff-300", "session_handoff-200"]
        );
        assert_eq!(value["last_task"], "current task");
        assert_eq!(value["status"], "in_progress");
        assert_eq!(value["open_questions"], json!(["open question"]));
        assert_eq!(value["conversation_snippet"], "语".repeat(4000));
        assert_eq!(value["active_branch"], "handoff-test");
        assert!(value["recent_commit"]
            .as_str()
            .expect("commit")
            .ends_with("fixture"));
        assert_eq!(value["git"]["is_repo"], true);
        assert_eq!(value["git"]["clean"], false);
        assert_eq!(value["key_files_modified"], json!(["work.txt"]));
        assert_eq!(value["git"]["porcelain"], json!(["?? work.txt"]));
        assert!(value["generated_at"]
            .as_str()
            .expect("timestamp")
            .ends_with('Z'));
        let zero = brief(store.clone(), &cwd, 0).await;
        assert_eq!(zero["pending_items"], json!([]));
        assert!(handoff_keys(&zero).is_empty());
        assert_eq!(
            zero["candidate_limit_reached"],
            json!({"todos": false, "session_handoffs": false})
        );
        for (row, expected) in rows.iter().zip(before) {
            assert_eq!(
                serde_json::to_value(store.memory_peek(&row.key).await.expect("peek after"))
                    .expect("serialize after"),
                expected,
                "memory changed: {}",
                row.key
            );
        }
        assert_eq!(
            serde_json::to_value(
                store
                    .memory_neighbors("todo-300")
                    .await
                    .expect("edges after")
            )
            .expect("serialize edges"),
            edges_before
        );
    }
}
