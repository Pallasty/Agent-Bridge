//! IDE perception: a lightweight file-based bridge for editor state.
//!
//! The MCP stdio process cannot assume it lives inside VS Code/Cursor/Windsurf,
//! so v0 reads a small JSON snapshot written by whichever IDE integration is
//! available. This keeps the agent-facing contract stable while frontends vary.

use ab_core::{Error, Result};
use serde_json::{json, Map, Value};
use std::collections::{BTreeMap, BTreeSet};
use std::fs::OpenOptions;
use std::io::{ErrorKind, Write};
use std::path::{Path, PathBuf};
use std::sync::atomic::{AtomicU64, Ordering};
use std::time::Duration;
use std::time::{SystemTime, UNIX_EPOCH};

const DEFAULT_STALE_AFTER_MS: u128 = 30_000;
const DEFAULT_MAX_OPEN_FILES: usize = 40;
const DEFAULT_MAX_DIAGNOSTICS: usize = 200;
const DEFAULT_MAX_SELECTION_CHARS: usize = 20_000;
const DEFAULT_MAX_MESSAGE_CHARS: usize = 1_000;
const COMMANDS_FILE: &str = "ide-commands.jsonl";
const RESPONSES_FILE: &str = "ide-responses.jsonl";
const WORKSPACE_BOUNDARY_SCHEMA: &str = "agent_bridge.workspace_boundary_evidence.v0";
const CREATE_FILE_GATE_SCHEMA: &str = "agent_bridge.ide_command.create_file_gate.v0";
const COMMAND_DIR_BOUNDARY_SCHEMA: &str = "agent_bridge.ide_command.command_dir_boundary.v0";

static COMMAND_COUNTER: AtomicU64 = AtomicU64::new(1);

#[derive(Debug, Clone)]
pub struct IdeSnapshotOptions {
    pub max_open_files: usize,
    pub max_diagnostics: usize,
    pub max_selection_chars: usize,
    pub stale_after_ms: u128,
}

impl Default for IdeSnapshotOptions {
    fn default() -> Self {
        Self {
            max_open_files: DEFAULT_MAX_OPEN_FILES,
            max_diagnostics: DEFAULT_MAX_DIAGNOSTICS,
            max_selection_chars: DEFAULT_MAX_SELECTION_CHARS,
            stale_after_ms: DEFAULT_STALE_AFTER_MS,
        }
    }
}

#[derive(Debug, Clone)]
struct SnapshotSource {
    path: PathBuf,
    source_kind: &'static str,
}

#[derive(Debug, Clone)]
pub struct IdeCommandOptions {
    pub command_dir: Option<PathBuf>,
    pub cwd: Option<PathBuf>,
    pub wait_ms: u64,
}

#[derive(Debug, Clone)]
struct ResolvedCommandDir {
    path: PathBuf,
    source: &'static str,
}

/// Read the current IDE snapshot from an explicit path, environment variable,
/// or a project-local `.agent-bridge/ide-snapshot.json`.
pub fn read_ide_snapshot(
    explicit_path: Option<&str>,
    cwd: Option<&Path>,
    options: IdeSnapshotOptions,
) -> Result<Value> {
    let candidates = snapshot_candidates(explicit_path, cwd);
    let Some(source) = candidates.iter().find(|c| c.path.is_file()).cloned() else {
        let paths: Vec<String> = candidates
            .iter()
            .map(|c| c.path.display().to_string())
            .collect();
        return Ok(json!({
            "available": false,
            "reason": "no IDE snapshot file found",
            "checked_paths": paths,
            "contract": snapshot_contract(),
        }));
    };

    let raw = std::fs::read_to_string(&source.path).map_err(Error::Io)?;
    let value: Value = serde_json::from_str(&raw).map_err(Error::Serde)?;
    normalise_snapshot(value, &source, options)
}

/// Queue an IDE command for an editor extension to execute.
///
/// Commands are append-only JSONL records. The VS Code/Cursor example watches
/// `ide-commands.jsonl` and writes matching responses to `ide-responses.jsonl`.
pub fn queue_ide_command(command: &str, args: Value, options: IdeCommandOptions) -> Result<Value> {
    let command = command.trim();
    if command.is_empty() {
        return Err(Error::InvalidArgument("command is required".into()));
    }
    if !matches!(
        command,
        "open_file"
            | "reveal_range"
            | "run_task"
            | "write_snapshot"
            | "apply_workspace_edit"
            | "save_file"
            | "format_document"
    ) {
        return Err(Error::InvalidArgument(format!(
            "unsupported IDE command: {command}"
        )));
    }
    if !args.is_object() {
        return Err(Error::InvalidArgument(
            "args must be a JSON object, even when empty".into(),
        ));
    }

    let resolved_dir = resolve_command_dir(options.command_dir.as_deref(), options.cwd.as_deref())?;
    let dir = resolved_dir.path;
    let request_path = dir.join(COMMANDS_FILE);
    let response_path = dir.join(RESPONSES_FILE);
    let command_dir_boundary =
        command_dir_boundary_evidence(&dir, resolved_dir.source, &args, options.cwd.as_deref());
    let workspace_boundary =
        command_workspace_boundary_evidence(command, &args, options.cwd.as_deref(), &dir);
    let create_file_gate = command_create_file_gate_evidence(
        command,
        &args,
        options.cwd.as_deref(),
        &dir,
        &workspace_boundary,
    );
    let create_file_gate_verdict = create_file_gate
        .as_ref()
        .and_then(|gate| gate.get("verdict"))
        .and_then(Value::as_str);
    let create_file_gate_blocks = create_file_gate_verdict == Some("blocked");
    let create_file_gate_allows = create_file_gate_verdict == Some("allowed");
    let workspace_boundary_contained = workspace_boundary_all_contained(&workspace_boundary);
    if mutating_ide_command(command)
        && (create_file_gate_blocks || (!workspace_boundary_contained && !create_file_gate_allows))
    {
        let actual_verdict = workspace_boundary
            .get("verdict")
            .and_then(Value::as_str)
            .unwrap_or("unknown")
            .to_string();
        let mut payload = Map::new();
        payload.insert("queued".to_string(), json!(false));
        payload.insert("status".to_string(), json!("blocked"));
        payload.insert("command".to_string(), json!(command));
        payload.insert("command_dir".to_string(), json!(dir.display().to_string()));
        payload.insert("command_dir_boundary".to_string(), command_dir_boundary);
        payload.insert(
            "request_path".to_string(),
            json!(request_path.display().to_string()),
        );
        payload.insert(
            "response_path".to_string(),
            json!(response_path.display().to_string()),
        );
        payload.insert("workspace_boundary".to_string(), workspace_boundary);
        payload.insert(
            "gate".to_string(),
            json!({
                "schema": "agent_bridge.ide_command.workspace_boundary_gate.v0",
                "required_verdict": "contained",
                "actual_verdict": actual_verdict,
                "create_file_gate_verdict": create_file_gate_verdict,
                "mutating_command": true,
                "queued": false,
            }),
        );
        if let Some(gate) = create_file_gate {
            payload.insert("create_file_gate".to_string(), gate);
        }
        let hint = if create_file_gate_blocks {
            "mutating IDE command was blocked by create-file preflight; create edits require an existing contained parent, missing target, and no range."
        } else {
            "mutating IDE commands require all referenced paths to exist and canonicalize inside the workspace before queueing."
        };
        payload.insert("hint".to_string(), json!(hint));
        return Ok(Value::Object(payload));
    }

    std::fs::create_dir_all(&dir).map_err(Error::Io)?;
    let now_ms = system_time_to_unix_ms(SystemTime::now()).unwrap_or(0);
    let id = format!(
        "idecmd-{now_ms}-{}-{}",
        std::process::id(),
        COMMAND_COUNTER.fetch_add(1, Ordering::Relaxed)
    );
    let request = json!({
        "schema_version": 1,
        "id": id,
        "created_at_unix_ms": now_ms,
        "command": command,
        "args": args,
    });
    append_jsonl(&request_path, &request)?;

    let response = if options.wait_ms > 0 {
        wait_for_response(&response_path, &id, options.wait_ms)?
    } else {
        None
    };
    let status = if response.is_some() {
        "completed"
    } else if options.wait_ms > 0 {
        "timeout"
    } else {
        "queued"
    };

    let mut payload = Map::new();
    payload.insert("queued".to_string(), json!(true));
    payload.insert("status".to_string(), json!(status));
    payload.insert("id".to_string(), json!(id));
    payload.insert("command".to_string(), json!(command));
    payload.insert("command_dir".to_string(), json!(dir.display().to_string()));
    payload.insert("command_dir_boundary".to_string(), command_dir_boundary);
    payload.insert(
        "request_path".to_string(),
        json!(request_path.display().to_string()),
    );
    payload.insert(
        "response_path".to_string(),
        json!(response_path.display().to_string()),
    );
    payload.insert("workspace_boundary".to_string(), workspace_boundary);
    if let Some(gate) = create_file_gate {
        payload.insert("create_file_gate".to_string(), gate);
    }
    payload.insert("response".to_string(), response.unwrap_or(Value::Null));
    payload.insert(
        "hint".to_string(),
        json!(if status == "timeout" {
            "command was queued but no IDE response arrived before wait_ms elapsed; make sure the IDE extension is running."
        } else {
            "IDE extension should consume ide-commands.jsonl and append to ide-responses.jsonl."
        }),
    );

    Ok(Value::Object(payload))
}

fn snapshot_candidates(explicit_path: Option<&str>, cwd: Option<&Path>) -> Vec<SnapshotSource> {
    let mut out = Vec::new();
    if let Some(path) = explicit_path.map(str::trim).filter(|s| !s.is_empty()) {
        out.push(SnapshotSource {
            path: PathBuf::from(path),
            source_kind: "argument",
        });
        return out;
    }

    if let Ok(path) = std::env::var("AGENT_BRIDGE_IDE_SNAPSHOT") {
        let path = path.trim();
        if !path.is_empty() {
            out.push(SnapshotSource {
                path: PathBuf::from(path),
                source_kind: "env",
            });
        }
    }

    let start = cwd
        .map(Path::to_path_buf)
        .or_else(|| std::env::current_dir().ok());
    if let Some(start) = start {
        let mut cur = Some(start.as_path());
        while let Some(dir) = cur {
            out.push(SnapshotSource {
                path: dir.join(".agent-bridge").join("ide-snapshot.json"),
                source_kind: "project",
            });
            cur = dir.parent();
        }
    }

    if let Ok(runtime) = std::env::var("XDG_RUNTIME_DIR") {
        out.push(SnapshotSource {
            path: PathBuf::from(runtime)
                .join("agent-bridge")
                .join("ide-snapshot.json"),
            source_kind: "runtime",
        });
    }

    if let Ok(home) = std::env::var("HOME") {
        let home = PathBuf::from(home);
        // Per-OS data dir (mirror of setup::agent_bridge_data_dir): macOS uses
        // ~/Library/Application Support; Linux honours XDG_DATA_HOME, then falls
        // back to ~/.local/share. Without the macOS branch the snapshot under
        // ~/Library/Application Support is never found on a Mac.
        #[cfg(target_os = "macos")]
        let data_dir = home.join("Library/Application Support/agent-bridge");
        #[cfg(not(target_os = "macos"))]
        let data_dir = std::env::var("XDG_DATA_HOME")
            .map(|x| PathBuf::from(x).join("agent-bridge"))
            .unwrap_or_else(|_| home.join(".local/share/agent-bridge"));
        out.push(SnapshotSource {
            path: data_dir.join("ide-snapshot.json"),
            source_kind: "data",
        });
    }

    out
}

fn resolve_command_dir(
    explicit_dir: Option<&Path>,
    cwd: Option<&Path>,
) -> Result<ResolvedCommandDir> {
    if let Some(dir) = explicit_dir {
        return Ok(ResolvedCommandDir {
            path: dir.to_path_buf(),
            source: "argument",
        });
    }
    if let Ok(dir) = std::env::var("AGENT_BRIDGE_IDE_COMMAND_DIR") {
        let dir = dir.trim();
        if !dir.is_empty() {
            return Ok(ResolvedCommandDir {
                path: PathBuf::from(dir),
                source: "env_command_dir",
            });
        }
    }
    if let Ok(snapshot) = std::env::var("AGENT_BRIDGE_IDE_SNAPSHOT") {
        let snapshot = snapshot.trim();
        if !snapshot.is_empty() {
            if let Some(parent) = Path::new(snapshot).parent() {
                return Ok(ResolvedCommandDir {
                    path: parent.to_path_buf(),
                    source: "env_snapshot_parent",
                });
            }
        }
    }

    let source = if cwd.is_some() {
        "cwd_default"
    } else {
        "process_cwd_default"
    };
    let base = cwd
        .map(Path::to_path_buf)
        .or_else(|| std::env::current_dir().ok())
        .ok_or_else(|| Error::InvalidArgument("could not resolve cwd".into()))?;
    let meta = std::fs::metadata(&base).map_err(Error::Io)?;
    if !meta.is_dir() {
        return Err(Error::InvalidArgument(format!(
            "cwd is not a directory: {}",
            base.display()
        )));
    }
    Ok(ResolvedCommandDir {
        path: base.join(".agent-bridge"),
        source,
    })
}

fn append_jsonl(path: &Path, value: &Value) -> Result<()> {
    let mut file = OpenOptions::new()
        .create(true)
        .append(true)
        .open(path)
        .map_err(Error::Io)?;
    let line = serde_json::to_string(value).map_err(Error::Serde)?;
    writeln!(file, "{line}").map_err(Error::Io)
}

fn wait_for_response(path: &Path, id: &str, wait_ms: u64) -> Result<Option<Value>> {
    let deadline = std::time::Instant::now() + Duration::from_millis(wait_ms);
    loop {
        if let Some(response) = find_response(path, id)? {
            return Ok(Some(response));
        }
        if std::time::Instant::now() >= deadline {
            return Ok(None);
        }
        std::thread::sleep(Duration::from_millis(100));
    }
}

fn find_response(path: &Path, id: &str) -> Result<Option<Value>> {
    let Ok(raw) = std::fs::read_to_string(path) else {
        return Ok(None);
    };
    for line in raw.lines().rev() {
        let line = line.trim();
        if line.is_empty() {
            continue;
        }
        let Ok(value) = serde_json::from_str::<Value>(line) else {
            continue;
        };
        if value.get("id").and_then(|v| v.as_str()) == Some(id) {
            return Ok(Some(value));
        }
    }
    Ok(None)
}

fn normalise_snapshot(
    raw: Value,
    source: &SnapshotSource,
    options: IdeSnapshotOptions,
) -> Result<Value> {
    if !raw.is_object() {
        return Err(Error::InvalidArgument(
            "IDE snapshot root must be a JSON object".into(),
        ));
    }

    let metadata = std::fs::metadata(&source.path).map_err(Error::Io)?;
    let modified_at_ms = metadata.modified().ok().and_then(system_time_to_unix_ms);
    let now_ms = system_time_to_unix_ms(SystemTime::now()).unwrap_or(0);
    let age_ms = modified_at_ms
        .map(|m| now_ms.saturating_sub(m))
        .unwrap_or_default();

    let schema_version = get_first(&raw, &["schema_version", "schemaVersion"]).cloned();
    let ide = get_first(&raw, &["ide", "editor"])
        .cloned()
        .unwrap_or(Value::Null);
    let workspace_root = get_first(&raw, &["workspace_root", "workspaceRoot"]).cloned();
    let active_file = get_first(&raw, &["active_file", "activeFile"]).cloned();
    let selection = get_first(&raw, &["selection", "activeSelection"])
        .map(|v| sanitise_selection(v, options.max_selection_chars))
        .unwrap_or(Value::Null);
    let open_files = get_first(&raw, &["open_files", "openFiles"])
        .map(|v| sanitise_open_files(v, options.max_open_files))
        .unwrap_or_else(|| json!([]));
    let diagnostics = get_first(&raw, &["diagnostics", "problems"])
        .map(|v| sanitise_diagnostics(v, options.max_diagnostics))
        .unwrap_or_else(|| json!([]));
    let diagnostic_counts = diagnostic_counts(&diagnostics);
    let tasks = get_first(&raw, &["tasks", "recent_tasks", "recentTasks"])
        .map(|v| sanitise_tasks(v, 20))
        .unwrap_or_else(|| json!([]));
    let workspace_boundary = workspace_boundary_evidence(
        workspace_root.as_ref(),
        active_file.as_ref(),
        &selection,
        &open_files,
        &diagnostics,
    );

    Ok(json!({
        "available": true,
        "schema_version": schema_version.unwrap_or(json!(1)),
        "source": {
            "kind": source.source_kind,
            "path": source.path.display().to_string(),
            "modified_at_unix_ms": modified_at_ms,
            "age_ms": age_ms,
        },
        "stale": age_ms > options.stale_after_ms,
        "stale_after_ms": options.stale_after_ms,
        "ide": ide,
        "workspace_root": workspace_root.unwrap_or(Value::Null),
        "active_file": active_file.unwrap_or(Value::Null),
        "selection": selection,
        "open_files": open_files,
        "diagnostics": diagnostics,
        "diagnostic_counts": diagnostic_counts,
        "tasks": tasks,
        "workspace_boundary": workspace_boundary,
        "limits": {
            "max_open_files": options.max_open_files,
            "max_diagnostics": options.max_diagnostics,
            "max_selection_chars": options.max_selection_chars,
            "max_message_chars": DEFAULT_MAX_MESSAGE_CHARS,
        },
    }))
}

fn get_first<'a>(v: &'a Value, keys: &[&str]) -> Option<&'a Value> {
    keys.iter().find_map(|k| v.get(*k))
}

fn sanitise_selection(v: &Value, max_chars: usize) -> Value {
    match v {
        Value::Object(map) => {
            let mut out = Map::new();
            for key in ["file", "path", "range", "start", "end", "language"] {
                if let Some(value) = map.get(key) {
                    out.insert(key.to_string(), value.clone());
                }
            }
            if let Some(text) = map.get("text").and_then(|x| x.as_str()) {
                let (truncated, was_truncated) = truncate_chars(text, max_chars);
                out.insert("text".into(), Value::String(truncated));
                out.insert("text_truncated".into(), Value::Bool(was_truncated));
                out.insert("text_chars".into(), json!(text.chars().count()));
            }
            Value::Object(out)
        }
        _ => Value::Null,
    }
}

fn sanitise_open_files(v: &Value, max_items: usize) -> Value {
    let Some(arr) = v.as_array() else {
        return json!([]);
    };
    let files: Vec<Value> = arr.iter().take(max_items).map(sanitise_open_file).collect();
    json!({
        "items": files,
        "total": arr.len(),
        "truncated": arr.len() > max_items,
    })
}

fn sanitise_open_file(v: &Value) -> Value {
    match v {
        Value::String(s) => json!({ "path": s }),
        Value::Object(map) => {
            let mut out = Map::new();
            for key in [
                "path",
                "file",
                "uri",
                "language",
                "language_id",
                "languageId",
                "is_dirty",
                "isDirty",
                "is_active",
                "isActive",
            ] {
                if let Some(value) = map.get(key) {
                    out.insert(key.to_string(), value.clone());
                }
            }
            Value::Object(out)
        }
        _ => Value::Null,
    }
}

fn sanitise_diagnostics(v: &Value, max_items: usize) -> Value {
    let Some(arr) = v.as_array() else {
        return json!([]);
    };
    let diagnostics: Vec<Value> = arr
        .iter()
        .take(max_items)
        .map(sanitise_diagnostic)
        .collect();
    json!({
        "items": diagnostics,
        "total": arr.len(),
        "truncated": arr.len() > max_items,
    })
}

fn sanitise_diagnostic(v: &Value) -> Value {
    let Some(map) = v.as_object() else {
        return Value::Null;
    };
    let mut out = Map::new();
    for key in ["file", "path", "uri", "range", "source", "code"] {
        if let Some(value) = map.get(key) {
            out.insert(key.to_string(), value.clone());
        }
    }
    if let Some(sev) = map.get("severity") {
        out.insert("severity".into(), Value::String(normalise_severity(sev)));
    }
    if let Some(message) = map.get("message").and_then(|x| x.as_str()) {
        let (truncated, was_truncated) = truncate_chars(message, DEFAULT_MAX_MESSAGE_CHARS);
        out.insert("message".into(), Value::String(truncated));
        if was_truncated {
            out.insert("message_truncated".into(), Value::Bool(true));
        }
    }
    Value::Object(out)
}

fn sanitise_tasks(v: &Value, max_items: usize) -> Value {
    let Some(arr) = v.as_array() else {
        return json!([]);
    };
    let items: Vec<Value> = arr.iter().take(max_items).cloned().collect();
    json!({
        "items": items,
        "total": arr.len(),
        "truncated": arr.len() > max_items,
    })
}

fn diagnostic_counts(diagnostics: &Value) -> Value {
    let mut counts: BTreeMap<String, u64> = BTreeMap::new();
    let items = diagnostics
        .get("items")
        .and_then(|v| v.as_array())
        .map(Vec::as_slice)
        .unwrap_or(&[]);
    for item in items {
        let sev = item
            .get("severity")
            .and_then(|v| v.as_str())
            .unwrap_or("unknown");
        *counts.entry(sev.to_string()).or_default() += 1;
    }
    json!(counts)
}

#[derive(Debug, Clone)]
struct PathInput {
    input: String,
    path: PathBuf,
}

fn workspace_boundary_evidence(
    workspace_root: Option<&Value>,
    active_file: Option<&Value>,
    selection: &Value,
    open_files: &Value,
    diagnostics: &Value,
) -> Value {
    let root_input = workspace_root.and_then(path_input_from_value);
    let (root_evidence, root_canonical) = workspace_root_evidence(root_input.as_ref());
    let mut candidates = Vec::new();

    if let Some(active_file) = active_file {
        push_path_candidate(&mut candidates, "active_file", active_file);
    }
    push_object_path_candidates(
        &mut candidates,
        "selection",
        selection,
        &["file", "path", "uri"],
    );
    push_array_item_path_candidates(
        &mut candidates,
        "open_files",
        open_files,
        &["path", "file", "uri"],
    );
    push_array_item_path_candidates(
        &mut candidates,
        "diagnostics",
        diagnostics,
        &["file", "path", "uri"],
    );

    workspace_boundary_evidence_from_parts(
        root_input.as_ref(),
        root_evidence,
        root_canonical,
        &candidates,
    )
}

fn command_workspace_boundary_evidence(
    command: &str,
    args: &Value,
    cwd: Option<&Path>,
    command_dir: &Path,
) -> Value {
    let root_input = command_workspace_root_input(args, cwd, command_dir);
    let (root_evidence, root_canonical) = workspace_root_evidence(root_input.as_ref());
    let candidates = command_path_candidates(command, args);

    workspace_boundary_evidence_from_parts(
        root_input.as_ref(),
        root_evidence,
        root_canonical,
        &candidates,
    )
}

fn workspace_boundary_evidence_from_parts(
    root_input: Option<&PathInput>,
    root_evidence: Value,
    root_canonical: Option<PathBuf>,
    candidates: &[(String, PathInput)],
) -> Value {
    let paths: Vec<Value> = candidates
        .iter()
        .map(|(role, input)| path_boundary_evidence(role, input, root_canonical.as_deref()))
        .collect();
    let verdict = workspace_boundary_verdict(root_input, root_canonical.as_ref(), &paths);

    json!({
        "schema": WORKSPACE_BOUNDARY_SCHEMA,
        "mode": "read_only_evidence",
        "workspace_root": root_evidence,
        "paths": paths,
        "excludes": {
            "status": "not_evaluated",
            "sources": []
        },
        "verdict": verdict,
    })
}

fn command_dir_boundary_evidence(
    command_dir: &Path,
    source: &str,
    args: &Value,
    cwd: Option<&Path>,
) -> Value {
    let effective_dir = effective_command_dir_path(command_dir);
    let root_input = command_workspace_root_input(args, cwd, command_dir);
    let (_root_evidence, root_canonical) = workspace_root_evidence(root_input.as_ref());

    let metadata = std::fs::metadata(&effective_dir).ok();
    let exists = metadata.is_some();
    let is_dir = metadata.as_ref().is_some_and(|m| m.is_dir());
    let canonical = if exists {
        std::fs::canonicalize(&effective_dir).ok()
    } else {
        None
    };

    let parent = effective_dir.parent().map(Path::to_path_buf);
    let parent_metadata = parent.as_ref().and_then(|p| std::fs::metadata(p).ok());
    let parent_exists = parent_metadata.is_some();
    let parent_is_dir = parent_metadata.as_ref().is_some_and(|m| m.is_dir());
    let parent_canonical = if parent_exists && parent_is_dir {
        parent.as_ref().and_then(|p| std::fs::canonicalize(p).ok())
    } else {
        None
    };

    let root = root_canonical.as_ref();
    let contained_existing = root
        .zip(canonical.as_ref())
        .is_some_and(|(root, dir)| dir == root || dir.starts_with(root));
    let contained_parent = root
        .zip(parent_canonical.as_ref())
        .is_some_and(|(root, parent)| parent == root || parent.starts_with(root));
    let relation = if root.is_none() {
        "no_workspace_root"
    } else if exists && !is_dir {
        "not_directory"
    } else if exists && canonical.is_none() {
        "canonicalize_failed"
    } else if exists && contained_existing {
        "inside_workspace"
    } else if exists {
        "outside_workspace"
    } else if parent_exists && !parent_is_dir {
        "parent_not_directory"
    } else if parent_exists && contained_parent {
        "will_create_inside_workspace"
    } else if parent_exists {
        "will_create_outside_workspace"
    } else {
        "parent_missing"
    };
    let contained = matches!(
        relation,
        "inside_workspace" | "will_create_inside_workspace"
    );
    let verdict = match relation {
        "inside_workspace" | "will_create_inside_workspace" => "contained",
        "outside_workspace" | "will_create_outside_workspace" => "external",
        "no_workspace_root" => "no_workspace_root",
        _ => "needs_review",
    };

    json!({
        "schema": COMMAND_DIR_BOUNDARY_SCHEMA,
        "mode": "pre_queue_evidence",
        "source": source,
        "path": command_dir.display().to_string(),
        "effective_path": effective_dir.display().to_string(),
        "relative_resolution": if command_dir.is_absolute() { "absolute" } else { "process_cwd" },
        "canonical": canonical.as_ref().map(|p| p.display().to_string()),
        "exists": exists,
        "is_dir": is_dir,
        "creates_dir_if_missing": !exists,
        "contained": contained,
        "relation": relation,
        "verdict": verdict,
        "workspace_root": root.map(|p| p.display().to_string()),
        "parent": parent.as_ref().map(|p| p.display().to_string()),
        "parent_canonical": parent_canonical.as_ref().map(|p| p.display().to_string()),
        "parent_exists": parent_exists,
        "parent_is_dir": parent_is_dir,
        "parent_contained": contained_parent,
        "queue_files": {
            "commands": command_dir.join(COMMANDS_FILE).display().to_string(),
            "responses": command_dir.join(RESPONSES_FILE).display().to_string(),
        },
    })
}

fn effective_command_dir_path(command_dir: &Path) -> PathBuf {
    if command_dir.is_absolute() {
        command_dir.to_path_buf()
    } else {
        std::env::current_dir()
            .map(|cwd| cwd.join(command_dir))
            .unwrap_or_else(|_| command_dir.to_path_buf())
    }
}

fn command_workspace_root_input(
    args: &Value,
    cwd: Option<&Path>,
    command_dir: &Path,
) -> Option<PathInput> {
    if let Some(root) =
        get_first(args, &["workspace_root", "workspaceRoot"]).and_then(path_input_from_value)
    {
        return Some(root);
    }
    if let Some(cwd) = cwd {
        return Some(path_input_from_path(cwd));
    }
    if command_dir.file_name().and_then(|s| s.to_str()) == Some(".agent-bridge") {
        if let Some(parent) = command_dir.parent() {
            return Some(path_input_from_path(parent));
        }
    }
    None
}

fn command_path_candidates(command: &str, args: &Value) -> Vec<(String, PathInput)> {
    let mut candidates = Vec::new();
    match command {
        "open_file" | "reveal_range" | "save_file" | "format_document" => {
            push_object_path_candidates(&mut candidates, "args", args, &["path", "file", "uri"]);
        }
        "apply_workspace_edit" => {
            push_object_path_candidates(&mut candidates, "args", args, &["path", "file", "uri"]);
            if let Some(edits) = args.get("edits").and_then(Value::as_array) {
                for (idx, edit) in edits.iter().enumerate() {
                    if let Some(map) = edit.as_object() {
                        for key in ["path", "file", "uri"] {
                            if let Some(value) = map.get(key) {
                                push_path_candidate(
                                    &mut candidates,
                                    &format!("args.edits[{idx}].{key}"),
                                    value,
                                );
                            }
                        }
                    }
                }
            }
        }
        _ => {}
    }
    candidates
}

fn mutating_ide_command(command: &str) -> bool {
    matches!(
        command,
        "apply_workspace_edit" | "save_file" | "format_document"
    )
}

fn workspace_boundary_all_contained(workspace_boundary: &Value) -> bool {
    workspace_boundary.get("verdict").and_then(Value::as_str) == Some("contained")
}

fn command_create_file_gate_evidence(
    command: &str,
    args: &Value,
    cwd: Option<&Path>,
    command_dir: &Path,
    workspace_boundary: &Value,
) -> Option<Value> {
    if command != "apply_workspace_edit" {
        return None;
    }

    let edits = args.get("edits").and_then(Value::as_array);
    let has_create_intent = edits
        .into_iter()
        .flatten()
        .any(|edit| edit.get("create").and_then(Value::as_bool) == Some(true));
    let has_missing_paths = workspace_boundary_paths(workspace_boundary)
        .iter()
        .any(|(_, relation)| relation == "missing_path");
    if !has_create_intent && !has_missing_paths {
        return None;
    }

    let root_input = command_workspace_root_input(args, cwd, command_dir);
    let (_root_evidence, root_canonical) = workspace_root_evidence(root_input.as_ref());
    let mut reasons = BTreeSet::new();
    let mut checks = Vec::new();
    let mut applies_to = Vec::new();
    let mut allowed_create_roles = BTreeSet::new();

    if has_create_intent && root_canonical.is_none() {
        reasons.insert("workspace_root_missing".to_string());
    }

    if let Some(edits) = edits {
        for (idx, edit) in edits.iter().enumerate() {
            let Some(edit_obj) = edit.as_object() else {
                continue;
            };
            if edit_obj.get("create").and_then(Value::as_bool) != Some(true) {
                continue;
            }
            applies_to.push(format!("args.edits[{idx}]"));
            let (check, check_allowed_roles, check_reasons) =
                create_file_edit_gate_check(idx, edit_obj, root_canonical.as_deref());
            for role in check_allowed_roles {
                allowed_create_roles.insert(role);
            }
            for reason in check_reasons {
                reasons.insert(reason);
            }
            checks.push(check);
        }
    }

    let mut uncovered_missing_path = false;
    for (role, relation) in workspace_boundary_paths(workspace_boundary) {
        match relation.as_str() {
            "inside_workspace" => {}
            "missing_path" if allowed_create_roles.contains(&role) => {}
            "missing_path" => {
                uncovered_missing_path = true;
                reasons.insert("create_flag_missing".to_string());
            }
            "no_workspace_root" => {
                reasons.insert("workspace_root_missing".to_string());
            }
            "outside_workspace" | "canonicalize_failed" => {
                reasons.insert("mixed_batch_edit_failed".to_string());
            }
            _ => {}
        }
    }
    if uncovered_missing_path && applies_to.is_empty() {
        checks.push(json!({
            "explicit_create": false,
            "allowed": false,
            "reasons": ["create_flag_missing"],
        }));
    }

    let reason_values: Vec<String> = reasons.into_iter().collect();
    let verdict = if reason_values.is_empty() {
        "allowed"
    } else {
        "blocked"
    };

    Some(json!({
        "schema": CREATE_FILE_GATE_SCHEMA,
        "mode": "pre_queue_evidence",
        "verdict": verdict,
        "applies_to": applies_to,
        "reasons": reason_values,
        "checks": checks,
    }))
}

fn create_file_edit_gate_check(
    idx: usize,
    edit: &Map<String, Value>,
    workspace_root: Option<&Path>,
) -> (Value, Vec<String>, BTreeSet<String>) {
    let path_inputs = edit_path_inputs(edit, idx);
    let range_absent = match edit.get("range") {
        Some(range) => range.is_null(),
        None => true,
    };
    let text_present = edit.get("text").is_some_and(Value::is_string);
    let mut reasons = BTreeSet::new();
    let mut allowed_roles = Vec::new();
    let mut path_checks = Vec::new();

    if !range_absent {
        reasons.insert("create_range_present".to_string());
    }
    if !text_present {
        reasons.insert("create_text_missing".to_string());
    }
    if path_inputs.is_empty() {
        reasons.insert("create_path_missing".to_string());
    }

    for (role, input) in path_inputs {
        let (path_check, path_allowed, path_reasons) =
            create_file_path_gate_check(&role, &input, workspace_root);
        if path_allowed && range_absent {
            allowed_roles.push(role);
        }
        for reason in path_reasons {
            reasons.insert(reason);
        }
        path_checks.push(path_check);
    }

    let parent_exists = !path_checks.is_empty()
        && path_checks
            .iter()
            .all(|check| check.get("parent_exists").and_then(Value::as_bool) == Some(true));
    let parent_contained = !path_checks.is_empty()
        && path_checks
            .iter()
            .all(|check| check.get("parent_contained").and_then(Value::as_bool) == Some(true));
    let target_missing = !path_checks.is_empty()
        && path_checks
            .iter()
            .all(|check| check.get("target_missing").and_then(Value::as_bool) == Some(true));
    let reason_values: Vec<String> = reasons.iter().cloned().collect();
    let allowed = reason_values.is_empty();

    (
        json!({
            "edit": idx,
            "role": format!("args.edits[{idx}]"),
            "explicit_create": true,
            "parent_exists": parent_exists,
            "parent_contained": parent_contained,
            "target_missing": target_missing,
            "range_absent": range_absent,
            "text_present": text_present,
            "auto_mkdir": false,
            "extension_final_authority": true,
            "allowed": allowed,
            "reasons": reason_values,
            "paths": path_checks,
        }),
        allowed_roles,
        reasons,
    )
}

fn create_file_path_gate_check(
    role: &str,
    input: &PathInput,
    workspace_root: Option<&Path>,
) -> (Value, bool, BTreeSet<String>) {
    let mut reasons = BTreeSet::new();
    let Some(root) = workspace_root else {
        reasons.insert("workspace_root_missing".to_string());
        return (
            json!({
                "role": role,
                "input": input.input.as_str(),
                "parent": Value::Null,
                "parent_canonical": Value::Null,
                "parent_exists": false,
                "parent_is_dir": false,
                "parent_contained": false,
                "target": Value::Null,
                "target_missing": false,
                "allowed": false,
                "reasons": ["workspace_root_missing"],
            }),
            false,
            reasons,
        );
    };

    let target = if input.path.is_absolute() {
        input.path.clone()
    } else {
        root.join(&input.path)
    };
    let parent = target.parent().map(Path::to_path_buf);
    let mut parent_exists = false;
    let mut parent_is_dir = false;
    let mut parent_canonical = None;
    let mut parent_contained = false;

    if let Some(parent) = parent.as_ref() {
        if let Ok(metadata) = std::fs::metadata(parent) {
            parent_exists = true;
            parent_is_dir = metadata.is_dir();
            if parent_is_dir {
                parent_canonical = std::fs::canonicalize(parent).ok();
                if let Some(canonical) = parent_canonical.as_ref() {
                    parent_contained = canonical == root || canonical.starts_with(root);
                }
            }
        }
    }

    let target_status = match std::fs::symlink_metadata(&target) {
        Ok(_) => "exists",
        Err(err) if err.kind() == ErrorKind::NotFound => "missing",
        Err(_) => "unknown",
    };
    let target_missing = target_status == "missing";
    if !parent_exists {
        reasons.insert("create_parent_missing".to_string());
    } else if !parent_is_dir {
        reasons.insert("create_parent_not_dir".to_string());
    }
    if parent_exists && parent_is_dir && !parent_contained {
        reasons.insert("create_parent_outside_workspace".to_string());
    }
    match target_status {
        "exists" => {
            reasons.insert("create_target_exists".to_string());
        }
        "unknown" => {
            reasons.insert("create_target_status_unknown".to_string());
        }
        _ => {}
    }

    let reason_values: Vec<String> = reasons.iter().cloned().collect();
    let allowed = reason_values.is_empty();
    (
        json!({
            "role": role,
            "input": input.input.as_str(),
            "parent": parent.as_ref().map(|p| p.display().to_string()),
            "parent_canonical": parent_canonical.as_ref().map(|p| p.display().to_string()),
            "parent_exists": parent_exists,
            "parent_is_dir": parent_is_dir,
            "parent_contained": parent_contained,
            "target": target.display().to_string(),
            "target_status": target_status,
            "target_missing": target_missing,
            "allowed": allowed,
            "reasons": reason_values,
        }),
        allowed,
        reasons,
    )
}

fn edit_path_inputs(edit: &Map<String, Value>, idx: usize) -> Vec<(String, PathInput)> {
    let mut inputs = Vec::new();
    for key in ["path", "file", "uri"] {
        if let Some(path_input) = edit.get(key).and_then(path_input_from_value) {
            inputs.push((format!("args.edits[{idx}].{key}"), path_input));
        }
    }
    inputs
}

fn workspace_boundary_paths(workspace_boundary: &Value) -> Vec<(String, String)> {
    workspace_boundary
        .get("paths")
        .and_then(Value::as_array)
        .map(|paths| {
            paths
                .iter()
                .filter_map(|path| {
                    let role = path.get("role").and_then(Value::as_str)?;
                    let relation = path.get("relation").and_then(Value::as_str)?;
                    Some((role.to_string(), relation.to_string()))
                })
                .collect()
        })
        .unwrap_or_default()
}

fn workspace_root_evidence(root: Option<&PathInput>) -> (Value, Option<PathBuf>) {
    let Some(root) = root else {
        return (
            json!({
                "input": Value::Null,
                "canonical": Value::Null,
                "exists": false,
                "is_dir": false,
                "reason": "workspace_root was not provided",
            }),
            None,
        );
    };

    let metadata = std::fs::metadata(&root.path).ok();
    let exists = metadata.is_some();
    let is_dir = metadata.as_ref().is_some_and(|m| m.is_dir());
    let canonical = if exists {
        std::fs::canonicalize(&root.path).ok()
    } else {
        None
    };
    let reason = match (exists, is_dir, canonical.is_some()) {
        (true, true, true) => "canonical workspace root resolved",
        (true, true, false) => "workspace_root could not be canonicalized",
        (true, false, _) => "workspace_root is not a directory",
        (false, _, _) => "workspace_root does not exist",
    };
    let usable_canonical = if is_dir { canonical.clone() } else { None };

    (
        json!({
            "input": root.input.as_str(),
            "canonical": canonical.as_ref().map(|p| p.display().to_string()),
            "exists": exists,
            "is_dir": is_dir,
            "reason": reason,
        }),
        usable_canonical,
    )
}

fn path_boundary_evidence(role: &str, input: &PathInput, workspace_root: Option<&Path>) -> Value {
    let candidate_path = match workspace_root {
        Some(root) if !input.path.is_absolute() => root.join(&input.path),
        _ => input.path.clone(),
    };
    let metadata = std::fs::metadata(&candidate_path).ok();
    let exists = metadata.is_some();

    let Some(root) = workspace_root else {
        let canonical = if input.path.is_absolute() && exists {
            std::fs::canonicalize(&candidate_path).ok()
        } else {
            None
        };
        return json!({
            "role": role,
            "input": input.input.as_str(),
            "canonical": canonical.as_ref().map(|p| p.display().to_string()),
            "exists": exists,
            "contained": false,
            "relation": "no_workspace_root",
            "reason": "workspace root was not provided or could not be canonicalized",
        });
    };

    if !exists {
        return json!({
            "role": role,
            "input": input.input.as_str(),
            "canonical": Value::Null,
            "exists": false,
            "contained": false,
            "relation": "missing_path",
            "reason": "candidate path does not exist; containment was not guessed",
        });
    }

    let Ok(canonical) = std::fs::canonicalize(&candidate_path) else {
        return json!({
            "role": role,
            "input": input.input.as_str(),
            "canonical": Value::Null,
            "exists": true,
            "contained": false,
            "relation": "canonicalize_failed",
            "reason": "candidate path exists but could not be canonicalized",
        });
    };
    let contained = canonical == root || canonical.starts_with(root);
    let relation = if contained {
        "inside_workspace"
    } else {
        "outside_workspace"
    };
    let reason = if contained {
        "canonical path has workspace root as ancestor"
    } else {
        "canonical path is outside the workspace root"
    };

    json!({
        "role": role,
        "input": input.input.as_str(),
        "canonical": canonical.display().to_string(),
        "exists": true,
        "contained": contained,
        "relation": relation,
        "reason": reason,
    })
}

fn workspace_boundary_verdict(
    root_input: Option<&PathInput>,
    root_canonical: Option<&PathBuf>,
    paths: &[Value],
) -> &'static str {
    if root_input.is_none() || root_canonical.is_none() {
        return "no_workspace_root";
    }
    if paths.is_empty() {
        return "no_candidate_paths";
    }
    if paths
        .iter()
        .any(|p| p.get("relation").and_then(Value::as_str) == Some("outside_workspace"))
    {
        return "outside_workspace";
    }
    if paths.iter().any(|p| {
        matches!(
            p.get("relation").and_then(Value::as_str),
            Some("missing_path" | "canonicalize_failed")
        )
    }) {
        return "needs_review";
    }
    "contained"
}

fn push_object_path_candidates(
    out: &mut Vec<(String, PathInput)>,
    prefix: &str,
    value: &Value,
    keys: &[&str],
) {
    let Some(map) = value.as_object() else {
        return;
    };
    for key in keys {
        if let Some(value) = map.get(*key) {
            push_path_candidate(out, &format!("{prefix}.{key}"), value);
        }
    }
}

fn push_array_item_path_candidates(
    out: &mut Vec<(String, PathInput)>,
    prefix: &str,
    value: &Value,
    keys: &[&str],
) {
    let Some(items) = value.get("items").and_then(Value::as_array) else {
        return;
    };
    for (idx, item) in items.iter().enumerate() {
        if item.is_string() {
            push_path_candidate(out, &format!("{prefix}[{idx}]"), item);
        } else if let Some(map) = item.as_object() {
            for key in keys {
                if let Some(value) = map.get(*key) {
                    push_path_candidate(out, &format!("{prefix}[{idx}].{key}"), value);
                }
            }
        }
    }
}

fn push_path_candidate(out: &mut Vec<(String, PathInput)>, role: &str, value: &Value) {
    if let Some(path_input) = path_input_from_value(value) {
        out.push((role.to_string(), path_input));
    }
}

fn path_input_from_value(value: &Value) -> Option<PathInput> {
    let raw = value.as_str()?.trim();
    if raw.is_empty() {
        return None;
    }
    let path_text = file_uri_to_path(raw).unwrap_or(raw);
    Some(PathInput {
        input: raw.to_string(),
        path: PathBuf::from(path_text),
    })
}

fn path_input_from_path(path: &Path) -> PathInput {
    PathInput {
        input: path.display().to_string(),
        path: path.to_path_buf(),
    }
}

fn file_uri_to_path(s: &str) -> Option<&str> {
    s.strip_prefix("file://localhost")
        .or_else(|| s.strip_prefix("file://"))
        .filter(|path| path.starts_with('/'))
}

fn normalise_severity(v: &Value) -> String {
    if let Some(s) = v.as_str() {
        return match s.trim().to_lowercase().as_str() {
            "1" | "error" | "err" => "error",
            "2" | "warning" | "warn" => "warning",
            "3" | "information" | "info" => "info",
            "4" | "hint" => "hint",
            other if other.is_empty() => "unknown",
            other => other,
        }
        .to_string();
    }
    match v.as_i64() {
        Some(1) => "error",
        Some(2) => "warning",
        Some(3) => "info",
        Some(4) => "hint",
        _ => "unknown",
    }
    .to_string()
}

fn truncate_chars(s: &str, max_chars: usize) -> (String, bool) {
    let mut out = String::new();
    let mut count = 0usize;
    for ch in s.chars() {
        if count >= max_chars {
            out.push_str("...");
            return (out, true);
        }
        out.push(ch);
        count += 1;
    }
    (out, false)
}

fn system_time_to_unix_ms(t: SystemTime) -> Option<u128> {
    t.duration_since(UNIX_EPOCH).ok().map(|d| d.as_millis())
}

fn snapshot_contract() -> Value {
    json!({
        "write_to": [
            "$AGENT_BRIDGE_IDE_SNAPSHOT",
            "<workspace>/.agent-bridge/ide-snapshot.json",
            "$XDG_RUNTIME_DIR/agent-bridge/ide-snapshot.json"
        ],
        "minimum_schema": {
            "schema_version": 1,
            "ide": { "name": "vscode|cursor|windsurf|other" },
            "workspace_root": "/abs/project",
            "active_file": "/abs/project/src/main.rs",
            "selection": {
                "file": "/abs/project/src/main.rs",
                "range": {
                    "start": { "line": 12, "character": 4 },
                    "end": { "line": 14, "character": 1 }
                },
                "text": "currently selected source"
            },
            "open_files": [
                { "path": "/abs/project/src/main.rs", "language": "rust", "is_dirty": false }
            ],
            "diagnostics": [
                {
                    "file": "/abs/project/src/main.rs",
                    "severity": "error|warning|info|hint",
                    "message": "diagnostic message",
                    "source": "rust-analyzer",
                    "code": "E0425",
                    "range": {
                        "start": { "line": 12, "character": 4 },
                        "end": { "line": 12, "character": 9 }
                    }
                }
            ]
        }
    })
}

#[cfg(test)]
mod tests {
    use super::*;

    fn temp_snapshot_path(name: &str) -> PathBuf {
        std::env::temp_dir().join(format!(
            "agent-bridge-{name}-{}-{}.json",
            std::process::id(),
            SystemTime::now()
                .duration_since(UNIX_EPOCH)
                .unwrap_or_default()
                .as_nanos()
        ))
    }

    fn path_entry_by_role<'a>(boundary: &'a Value, role: &str) -> &'a Value {
        boundary["paths"]
            .as_array()
            .expect("paths array")
            .iter()
            .find(|entry| entry["role"] == role)
            .unwrap_or_else(|| panic!("missing path role: {role}"))
    }

    #[test]
    fn missing_snapshot_returns_contract() {
        let path = temp_snapshot_path("missing");
        let v = read_ide_snapshot(
            Some(path.to_str().unwrap()),
            None,
            IdeSnapshotOptions::default(),
        )
        .expect("snapshot read");
        assert_eq!(v["available"], false);
        assert!(v["contract"].is_object());
    }

    #[test]
    fn snapshot_is_sanitised_and_counted() {
        let path = temp_snapshot_path("valid");
        let body = json!({
            "schema_version": 1,
            "ide": { "name": "vscode" },
            "workspace_root": "/tmp/project",
            "active_file": "/tmp/project/src/lib.rs",
            "selection": {
                "file": "/tmp/project/src/lib.rs",
                "text": "abcdef"
            },
            "open_files": [
                "/tmp/project/src/lib.rs",
                { "path": "/tmp/project/src/main.rs", "language": "rust", "is_dirty": true },
                { "path": "/tmp/project/README.md" }
            ],
            "diagnostics": [
                { "file": "/tmp/project/src/lib.rs", "severity": 1, "message": "boom" },
                { "file": "/tmp/project/src/main.rs", "severity": "warn", "message": "careful" }
            ]
        });
        std::fs::write(&path, serde_json::to_string(&body).unwrap()).expect("write snapshot");
        let v = read_ide_snapshot(
            Some(path.to_str().unwrap()),
            None,
            IdeSnapshotOptions {
                max_open_files: 2,
                max_diagnostics: 10,
                max_selection_chars: 3,
                stale_after_ms: 60_000,
            },
        )
        .expect("snapshot read");
        let _ = std::fs::remove_file(path);

        assert_eq!(v["available"], true);
        assert_eq!(v["selection"]["text"], "abc...");
        assert_eq!(v["selection"]["text_truncated"], true);
        assert_eq!(v["open_files"]["items"].as_array().unwrap().len(), 2);
        assert_eq!(v["open_files"]["truncated"], true);
        assert_eq!(v["diagnostic_counts"]["error"], 1);
        assert_eq!(v["diagnostic_counts"]["warning"], 1);
        assert_eq!(v["workspace_boundary"]["schema"], WORKSPACE_BOUNDARY_SCHEMA);
    }

    #[test]
    fn snapshot_workspace_boundary_reports_containment_and_missing_paths() {
        let tmp = tempfile::tempdir().expect("tempdir");
        let root = tmp.path().join("project");
        let src = root.join("src");
        let outside = tmp.path().join("outside");
        std::fs::create_dir_all(&src).expect("mkdir src");
        std::fs::create_dir_all(&outside).expect("mkdir outside");
        let lib = src.join("lib.rs");
        let main = src.join("main.rs");
        let outside_file = outside.join("note.txt");
        std::fs::write(&lib, "pub fn lib() {}\n").expect("write lib");
        std::fs::write(&main, "fn main() {}\n").expect("write main");
        std::fs::write(&outside_file, "outside\n").expect("write outside");

        let inside_dotdot = root.join("src").join("..").join("src").join("lib.rs");
        let outside_dotdot = root
            .join("src")
            .join("..")
            .join("..")
            .join("outside")
            .join("note.txt");
        let missing = root.join("missing.rs");
        let snapshot = tmp.path().join("snapshot.json");
        let body = json!({
            "schema_version": 1,
            "workspace_root": root.display().to_string(),
            "active_file": lib.display().to_string(),
            "selection": {
                "file": inside_dotdot.display().to_string(),
                "text": "selected"
            },
            "open_files": [
                { "path": outside_dotdot.display().to_string() },
                { "path": missing.display().to_string() }
            ],
            "diagnostics": [
                { "file": main.display().to_string(), "severity": "warning", "message": "warn" }
            ]
        });
        std::fs::write(&snapshot, serde_json::to_string(&body).unwrap()).expect("write snapshot");

        let v = read_ide_snapshot(
            Some(snapshot.to_str().unwrap()),
            None,
            IdeSnapshotOptions::default(),
        )
        .expect("snapshot read");
        let boundary = &v["workspace_boundary"];

        assert_eq!(boundary["workspace_root"]["exists"], true);
        assert_eq!(boundary["workspace_root"]["is_dir"], true);
        assert_eq!(boundary["verdict"], "outside_workspace");
        assert_eq!(
            path_entry_by_role(boundary, "active_file")["relation"],
            "inside_workspace"
        );
        assert_eq!(
            path_entry_by_role(boundary, "selection.file")["relation"],
            "inside_workspace"
        );
        assert_eq!(
            path_entry_by_role(boundary, "open_files[0].path")["relation"],
            "outside_workspace"
        );
        assert_eq!(
            path_entry_by_role(boundary, "open_files[1].path")["relation"],
            "missing_path"
        );
        assert_eq!(
            path_entry_by_role(boundary, "diagnostics[0].file")["relation"],
            "inside_workspace"
        );
    }

    #[test]
    fn snapshot_workspace_boundary_reports_no_workspace_root() {
        let tmp = tempfile::tempdir().expect("tempdir");
        let file = tmp.path().join("src.rs");
        std::fs::write(&file, "fn main() {}\n").expect("write file");
        let snapshot = tmp.path().join("snapshot.json");
        let body = json!({
            "schema_version": 1,
            "active_file": file.display().to_string(),
        });
        std::fs::write(&snapshot, serde_json::to_string(&body).unwrap()).expect("write snapshot");

        let v = read_ide_snapshot(
            Some(snapshot.to_str().unwrap()),
            None,
            IdeSnapshotOptions::default(),
        )
        .expect("snapshot read");
        let boundary = &v["workspace_boundary"];

        assert_eq!(boundary["verdict"], "no_workspace_root");
        assert_eq!(boundary["workspace_root"]["input"], Value::Null);
        assert_eq!(
            path_entry_by_role(boundary, "active_file")["relation"],
            "no_workspace_root"
        );
    }

    #[cfg(unix)]
    #[test]
    fn snapshot_workspace_boundary_canonicalizes_symlink_escape() {
        let tmp = tempfile::tempdir().expect("tempdir");
        let root = tmp.path().join("project");
        let outside = tmp.path().join("outside");
        std::fs::create_dir_all(&root).expect("mkdir root");
        std::fs::create_dir_all(&outside).expect("mkdir outside");
        let outside_file = outside.join("note.txt");
        let link = root.join("linked-note.txt");
        std::fs::write(&outside_file, "outside\n").expect("write outside");
        std::os::unix::fs::symlink(&outside_file, &link).expect("symlink");

        let snapshot = tmp.path().join("snapshot.json");
        let body = json!({
            "schema_version": 1,
            "workspace_root": root.display().to_string(),
            "active_file": link.display().to_string(),
        });
        std::fs::write(&snapshot, serde_json::to_string(&body).unwrap()).expect("write snapshot");

        let v = read_ide_snapshot(
            Some(snapshot.to_str().unwrap()),
            None,
            IdeSnapshotOptions::default(),
        )
        .expect("snapshot read");
        let boundary = &v["workspace_boundary"];

        assert_eq!(boundary["verdict"], "outside_workspace");
        assert_eq!(
            path_entry_by_role(boundary, "active_file")["relation"],
            "outside_workspace"
        );
    }

    #[test]
    fn ide_command_enqueue_writes_jsonl() {
        let dir = std::env::temp_dir().join(format!(
            "agent-bridge-ide-command-{}-{}",
            std::process::id(),
            SystemTime::now()
                .duration_since(UNIX_EPOCH)
                .unwrap_or_default()
                .as_nanos()
        ));
        let v = queue_ide_command(
            "open_file",
            json!({ "path": "/tmp/project/src/lib.rs" }),
            IdeCommandOptions {
                command_dir: Some(dir.clone()),
                cwd: None,
                wait_ms: 0,
            },
        )
        .expect("queue command");
        let raw = std::fs::read_to_string(dir.join(COMMANDS_FILE)).expect("commands file");
        let request: Value = serde_json::from_str(raw.lines().next().unwrap()).unwrap();
        let _ = std::fs::remove_dir_all(&dir);

        assert_eq!(v["status"], "queued");
        assert_eq!(request["command"], "open_file");
        assert_eq!(request["args"]["path"], "/tmp/project/src/lib.rs");
        assert_eq!(v["workspace_boundary"]["verdict"], "no_workspace_root");
    }

    #[test]
    fn ide_command_boundary_uses_cwd_for_relative_open_file() {
        let tmp = tempfile::tempdir().expect("tempdir");
        let root = tmp.path().join("project");
        let src = root.join("src");
        std::fs::create_dir_all(&src).expect("mkdir src");
        std::fs::write(src.join("lib.rs"), "pub fn lib() {}\n").expect("write lib");

        let v = queue_ide_command(
            "open_file",
            json!({ "path": "src/lib.rs" }),
            IdeCommandOptions {
                command_dir: None,
                cwd: Some(root.clone()),
                wait_ms: 0,
            },
        )
        .expect("queue command");
        let raw = std::fs::read_to_string(root.join(".agent-bridge").join(COMMANDS_FILE))
            .expect("commands file");
        let request: Value = serde_json::from_str(raw.lines().next().unwrap()).unwrap();
        let boundary = &v["workspace_boundary"];

        assert_eq!(v["status"], "queued");
        assert_eq!(request["args"]["path"], "src/lib.rs");
        assert_eq!(boundary["verdict"], "contained");
        assert_eq!(
            path_entry_by_role(boundary, "args.path")["relation"],
            "inside_workspace"
        );
    }

    #[test]
    fn ide_command_command_dir_boundary_reports_default_workspace_queue_dir() {
        let tmp = tempfile::tempdir().expect("tempdir");
        let root = tmp.path().join("project");
        std::fs::create_dir_all(&root).expect("mkdir root");

        let v = queue_ide_command(
            "write_snapshot",
            json!({}),
            IdeCommandOptions {
                command_dir: None,
                cwd: Some(root.clone()),
                wait_ms: 0,
            },
        )
        .expect("queue command");
        let boundary = &v["command_dir_boundary"];

        assert_eq!(v["status"], "queued");
        assert_eq!(boundary["schema"], COMMAND_DIR_BOUNDARY_SCHEMA);
        assert_eq!(boundary["source"], "cwd_default");
        assert_eq!(boundary["relation"], "will_create_inside_workspace");
        assert_eq!(boundary["verdict"], "contained");
        assert_eq!(boundary["creates_dir_if_missing"], true);
        assert_eq!(boundary["contained"], true);
        assert_eq!(
            boundary["queue_files"]["commands"],
            root.join(".agent-bridge")
                .join(COMMANDS_FILE)
                .display()
                .to_string()
        );
    }

    #[test]
    fn ide_command_command_dir_boundary_reports_existing_external_dir() {
        let tmp = tempfile::tempdir().expect("tempdir");
        let root = tmp.path().join("project");
        let src = root.join("src");
        let outside = tmp.path().join("outside-commands");
        std::fs::create_dir_all(&src).expect("mkdir src");
        std::fs::create_dir_all(&outside).expect("mkdir outside");
        std::fs::write(src.join("lib.rs"), "pub fn lib() {}\n").expect("write lib");

        let v = queue_ide_command(
            "open_file",
            json!({ "path": "src/lib.rs" }),
            IdeCommandOptions {
                command_dir: Some(outside.clone()),
                cwd: Some(root.clone()),
                wait_ms: 0,
            },
        )
        .expect("queue command");
        let boundary = &v["command_dir_boundary"];

        assert_eq!(v["status"], "queued");
        assert_eq!(boundary["source"], "argument");
        assert_eq!(boundary["relation"], "outside_workspace");
        assert_eq!(boundary["verdict"], "external");
        assert_eq!(boundary["creates_dir_if_missing"], false);
        assert_eq!(boundary["contained"], false);
        assert_eq!(v["workspace_boundary"]["verdict"], "contained");
        assert!(outside.join(COMMANDS_FILE).exists());
    }

    #[test]
    fn ide_command_command_dir_boundary_reports_external_auto_create_dir() {
        let tmp = tempfile::tempdir().expect("tempdir");
        let root = tmp.path().join("project");
        let outside = tmp.path().join("outside-commands");
        std::fs::create_dir_all(&root).expect("mkdir root");

        let v = queue_ide_command(
            "write_snapshot",
            json!({}),
            IdeCommandOptions {
                command_dir: Some(outside.clone()),
                cwd: Some(root.clone()),
                wait_ms: 0,
            },
        )
        .expect("queue command");
        let boundary = &v["command_dir_boundary"];

        assert_eq!(v["status"], "queued");
        assert_eq!(boundary["source"], "argument");
        assert_eq!(boundary["relation"], "will_create_outside_workspace");
        assert_eq!(boundary["verdict"], "external");
        assert_eq!(boundary["creates_dir_if_missing"], true);
        assert_eq!(boundary["contained"], false);
        assert!(outside.join(COMMANDS_FILE).exists());
    }

    #[test]
    fn ide_command_boundary_reports_outside_file_uri_without_blocking() {
        let tmp = tempfile::tempdir().expect("tempdir");
        let root = tmp.path().join("project");
        let outside = tmp.path().join("outside");
        std::fs::create_dir_all(&root).expect("mkdir root");
        std::fs::create_dir_all(&outside).expect("mkdir outside");
        let outside_file = outside.join("note.txt");
        std::fs::write(&outside_file, "outside\n").expect("write outside");
        let outside_uri = format!("file://{}", outside_file.display());

        let v = queue_ide_command(
            "reveal_range",
            json!({ "path": outside_uri }),
            IdeCommandOptions {
                command_dir: None,
                cwd: Some(root.clone()),
                wait_ms: 0,
            },
        )
        .expect("queue command");
        let raw = std::fs::read_to_string(root.join(".agent-bridge").join(COMMANDS_FILE))
            .expect("commands file");
        let request: Value = serde_json::from_str(raw.lines().next().unwrap()).unwrap();
        let boundary = &v["workspace_boundary"];

        assert_eq!(v["queued"], true);
        assert_eq!(request["command"], "reveal_range");
        assert_eq!(boundary["verdict"], "outside_workspace");
        assert_eq!(
            path_entry_by_role(boundary, "args.path")["relation"],
            "outside_workspace"
        );
    }

    #[test]
    fn ide_command_boundary_reports_apply_workspace_edit_paths_advisory_only() {
        let tmp = tempfile::tempdir().expect("tempdir");
        let root = tmp.path().join("project");
        let src = root.join("src");
        std::fs::create_dir_all(&src).expect("mkdir src");
        std::fs::write(src.join("lib.rs"), "pub fn lib() {}\n").expect("write lib");

        let v = queue_ide_command(
            "apply_workspace_edit",
            json!({
                "edits": [
                    { "path": "src/lib.rs", "text": "pub fn changed() {}\n" }
                ],
                "save": false
            }),
            IdeCommandOptions {
                command_dir: None,
                cwd: Some(root.clone()),
                wait_ms: 0,
            },
        )
        .expect("queue command");
        let raw = std::fs::read_to_string(root.join(".agent-bridge").join(COMMANDS_FILE))
            .expect("commands file");
        let request: Value = serde_json::from_str(raw.lines().next().unwrap()).unwrap();
        let boundary = &v["workspace_boundary"];

        assert_eq!(request["command"], "apply_workspace_edit");
        assert_eq!(request["args"]["edits"][0]["path"], "src/lib.rs");
        assert_eq!(boundary["verdict"], "contained");
        assert_eq!(
            path_entry_by_role(boundary, "args.edits[0].path")["relation"],
            "inside_workspace"
        );
    }

    #[test]
    fn ide_command_mutating_gate_blocks_outside_save_file_before_queueing() {
        let tmp = tempfile::tempdir().expect("tempdir");
        let root = tmp.path().join("project");
        let outside = tmp.path().join("outside");
        std::fs::create_dir_all(&root).expect("mkdir root");
        std::fs::create_dir_all(&outside).expect("mkdir outside");
        let outside_file = outside.join("note.txt");
        std::fs::write(&outside_file, "outside\n").expect("write outside");

        let v = queue_ide_command(
            "save_file",
            json!({ "path": outside_file.display().to_string() }),
            IdeCommandOptions {
                command_dir: None,
                cwd: Some(root.clone()),
                wait_ms: 0,
            },
        )
        .expect("queue command");
        let command_file = root.join(".agent-bridge").join(COMMANDS_FILE);
        let boundary = &v["workspace_boundary"];

        assert_eq!(v["queued"], false);
        assert_eq!(v["status"], "blocked");
        assert_eq!(v["gate"]["actual_verdict"], "outside_workspace");
        assert_eq!(boundary["verdict"], "outside_workspace");
        assert_eq!(
            path_entry_by_role(boundary, "args.path")["relation"],
            "outside_workspace"
        );
        assert!(
            !command_file.exists(),
            "blocked mutating command must not be queued"
        );
    }

    #[test]
    fn ide_command_mutating_gate_blocks_missing_edit_path() {
        let tmp = tempfile::tempdir().expect("tempdir");
        let root = tmp.path().join("project");
        std::fs::create_dir_all(&root).expect("mkdir root");

        let v = queue_ide_command(
            "apply_workspace_edit",
            json!({
                "edits": [
                    { "path": "src/new.rs", "text": "pub fn new_file() {}\n" }
                ],
                "save": false
            }),
            IdeCommandOptions {
                command_dir: None,
                cwd: Some(root.clone()),
                wait_ms: 0,
            },
        )
        .expect("queue command");
        let command_file = root.join(".agent-bridge").join(COMMANDS_FILE);
        let boundary = &v["workspace_boundary"];

        assert_eq!(v["queued"], false);
        assert_eq!(v["status"], "blocked");
        assert_eq!(v["gate"]["actual_verdict"], "needs_review");
        assert_eq!(v["create_file_gate"]["verdict"], "blocked");
        assert!(v["create_file_gate"]["reasons"]
            .as_array()
            .expect("reasons")
            .contains(&json!("create_flag_missing")));
        assert_eq!(boundary["verdict"], "needs_review");
        assert_eq!(
            path_entry_by_role(boundary, "args.edits[0].path")["relation"],
            "missing_path"
        );
        assert!(
            !command_file.exists(),
            "blocked mutating command must not be queued"
        );
    }

    #[test]
    fn ide_command_create_file_gate_allows_missing_create_edit_parent_contained() {
        let tmp = tempfile::tempdir().expect("tempdir");
        let root = tmp.path().join("project");
        let src = root.join("src");
        std::fs::create_dir_all(&src).expect("mkdir src");

        let v = queue_ide_command(
            "apply_workspace_edit",
            json!({
                "edits": [
                    { "path": "src/new.rs", "create": true, "text": "pub fn new_file() {}\n" }
                ],
                "save": false
            }),
            IdeCommandOptions {
                command_dir: None,
                cwd: Some(root.clone()),
                wait_ms: 0,
            },
        )
        .expect("queue command");
        let raw = std::fs::read_to_string(root.join(".agent-bridge").join(COMMANDS_FILE))
            .expect("commands file");
        let request: Value = serde_json::from_str(raw.lines().next().unwrap()).unwrap();
        let boundary = &v["workspace_boundary"];
        let create_gate = &v["create_file_gate"];

        assert_eq!(v["queued"], true);
        assert_eq!(request["command"], "apply_workspace_edit");
        assert_eq!(request["args"]["edits"][0]["create"], true);
        assert_eq!(boundary["verdict"], "needs_review");
        assert_eq!(
            path_entry_by_role(boundary, "args.edits[0].path")["relation"],
            "missing_path"
        );
        assert_eq!(create_gate["schema"], CREATE_FILE_GATE_SCHEMA);
        assert_eq!(create_gate["verdict"], "allowed");
        assert_eq!(create_gate["checks"][0]["allowed"], true);
        assert_eq!(create_gate["checks"][0]["parent_contained"], true);
        assert_eq!(create_gate["checks"][0]["target_missing"], true);
        assert_eq!(create_gate["checks"][0]["text_present"], true);
    }

    #[test]
    fn ide_command_create_file_gate_blocks_existing_create_target() {
        let tmp = tempfile::tempdir().expect("tempdir");
        let root = tmp.path().join("project");
        let src = root.join("src");
        std::fs::create_dir_all(&src).expect("mkdir src");
        std::fs::write(src.join("new.rs"), "pub fn existing() {}\n").expect("write existing");

        let v = queue_ide_command(
            "apply_workspace_edit",
            json!({
                "edits": [
                    { "path": "src/new.rs", "create": true, "text": "pub fn new_file() {}\n" }
                ],
                "save": false
            }),
            IdeCommandOptions {
                command_dir: None,
                cwd: Some(root.clone()),
                wait_ms: 0,
            },
        )
        .expect("queue command");
        let command_file = root.join(".agent-bridge").join(COMMANDS_FILE);

        assert_eq!(v["queued"], false);
        assert_eq!(v["status"], "blocked");
        assert_eq!(v["workspace_boundary"]["verdict"], "contained");
        assert_eq!(v["create_file_gate"]["verdict"], "blocked");
        assert!(v["create_file_gate"]["reasons"]
            .as_array()
            .expect("reasons")
            .contains(&json!("create_target_exists")));
        assert!(
            !command_file.exists(),
            "blocked create command must not be queued"
        );
    }

    #[test]
    fn ide_command_create_file_gate_blocks_missing_parent() {
        let tmp = tempfile::tempdir().expect("tempdir");
        let root = tmp.path().join("project");
        std::fs::create_dir_all(&root).expect("mkdir root");

        let v = queue_ide_command(
            "apply_workspace_edit",
            json!({
                "edits": [
                    { "path": "src/new.rs", "create": true, "text": "pub fn new_file() {}\n" }
                ],
                "save": false
            }),
            IdeCommandOptions {
                command_dir: None,
                cwd: Some(root.clone()),
                wait_ms: 0,
            },
        )
        .expect("queue command");
        let command_file = root.join(".agent-bridge").join(COMMANDS_FILE);

        assert_eq!(v["queued"], false);
        assert_eq!(v["status"], "blocked");
        assert_eq!(v["create_file_gate"]["verdict"], "blocked");
        assert!(v["create_file_gate"]["reasons"]
            .as_array()
            .expect("reasons")
            .contains(&json!("create_parent_missing")));
        assert!(
            !command_file.exists(),
            "blocked create command must not be queued"
        );
    }

    #[test]
    fn ide_command_create_file_gate_blocks_missing_text() {
        let tmp = tempfile::tempdir().expect("tempdir");
        let root = tmp.path().join("project");
        let src = root.join("src");
        std::fs::create_dir_all(&src).expect("mkdir src");

        let v = queue_ide_command(
            "apply_workspace_edit",
            json!({
                "edits": [
                    { "path": "src/new.rs", "create": true }
                ],
                "save": false
            }),
            IdeCommandOptions {
                command_dir: None,
                cwd: Some(root.clone()),
                wait_ms: 0,
            },
        )
        .expect("queue command");
        let command_file = root.join(".agent-bridge").join(COMMANDS_FILE);

        assert_eq!(v["queued"], false);
        assert_eq!(v["status"], "blocked");
        assert_eq!(v["create_file_gate"]["verdict"], "blocked");
        assert!(v["create_file_gate"]["reasons"]
            .as_array()
            .expect("reasons")
            .contains(&json!("create_text_missing")));
        assert!(
            !command_file.exists(),
            "blocked create command must not be queued"
        );
    }

    #[test]
    fn ide_command_create_file_gate_blocks_create_range() {
        let tmp = tempfile::tempdir().expect("tempdir");
        let root = tmp.path().join("project");
        let src = root.join("src");
        std::fs::create_dir_all(&src).expect("mkdir src");

        let v = queue_ide_command(
            "apply_workspace_edit",
            json!({
                "edits": [
                    {
                        "path": "src/new.rs",
                        "create": true,
                        "range": { "start": { "line": 0, "character": 0 }, "end": { "line": 0, "character": 0 } },
                        "text": "pub fn new_file() {}\n"
                    }
                ],
                "save": false
            }),
            IdeCommandOptions {
                command_dir: None,
                cwd: Some(root.clone()),
                wait_ms: 0,
            },
        )
        .expect("queue command");
        let command_file = root.join(".agent-bridge").join(COMMANDS_FILE);

        assert_eq!(v["queued"], false);
        assert_eq!(v["status"], "blocked");
        assert_eq!(v["create_file_gate"]["verdict"], "blocked");
        assert!(v["create_file_gate"]["reasons"]
            .as_array()
            .expect("reasons")
            .contains(&json!("create_range_present")));
        assert!(
            !command_file.exists(),
            "blocked create command must not be queued"
        );
    }

    #[test]
    fn ide_command_create_file_gate_blocks_outside_parent() {
        let tmp = tempfile::tempdir().expect("tempdir");
        let root = tmp.path().join("project");
        let outside = tmp.path().join("outside");
        std::fs::create_dir_all(&root).expect("mkdir root");
        std::fs::create_dir_all(&outside).expect("mkdir outside");
        let outside_target = outside.join("new.rs");

        let v = queue_ide_command(
            "apply_workspace_edit",
            json!({
                "edits": [
                    {
                        "path": outside_target.display().to_string(),
                        "create": true,
                        "text": "pub fn outside() {}\n"
                    }
                ],
                "save": false
            }),
            IdeCommandOptions {
                command_dir: None,
                cwd: Some(root.clone()),
                wait_ms: 0,
            },
        )
        .expect("queue command");
        let command_file = root.join(".agent-bridge").join(COMMANDS_FILE);

        assert_eq!(v["queued"], false);
        assert_eq!(v["status"], "blocked");
        assert_eq!(v["workspace_boundary"]["verdict"], "needs_review");
        assert_eq!(v["create_file_gate"]["verdict"], "blocked");
        assert!(v["create_file_gate"]["reasons"]
            .as_array()
            .expect("reasons")
            .contains(&json!("create_parent_outside_workspace")));
        assert!(
            !command_file.exists(),
            "blocked create command must not be queued"
        );
    }

    #[cfg(unix)]
    #[test]
    fn ide_command_create_file_gate_blocks_symlink_escaped_parent() {
        let tmp = tempfile::tempdir().expect("tempdir");
        let root = tmp.path().join("project");
        let outside = tmp.path().join("outside");
        std::fs::create_dir_all(&root).expect("mkdir root");
        std::fs::create_dir_all(&outside).expect("mkdir outside");
        std::os::unix::fs::symlink(&outside, root.join("linked-outside")).expect("symlink");

        let v = queue_ide_command(
            "apply_workspace_edit",
            json!({
                "edits": [
                    { "path": "linked-outside/new.rs", "create": true, "text": "pub fn outside() {}\n" }
                ],
                "save": false
            }),
            IdeCommandOptions {
                command_dir: None,
                cwd: Some(root.clone()),
                wait_ms: 0,
            },
        )
        .expect("queue command");
        let command_file = root.join(".agent-bridge").join(COMMANDS_FILE);

        assert_eq!(v["queued"], false);
        assert_eq!(v["status"], "blocked");
        assert_eq!(v["create_file_gate"]["verdict"], "blocked");
        assert!(v["create_file_gate"]["reasons"]
            .as_array()
            .expect("reasons")
            .contains(&json!("create_parent_outside_workspace")));
        assert!(
            !command_file.exists(),
            "blocked create command must not be queued"
        );
    }

    #[test]
    fn ide_command_create_file_gate_blocks_mixed_batch_failure() {
        let tmp = tempfile::tempdir().expect("tempdir");
        let root = tmp.path().join("project");
        let src = root.join("src");
        std::fs::create_dir_all(&src).expect("mkdir src");
        std::fs::write(src.join("lib.rs"), "pub fn lib() {}\n").expect("write lib");

        let v = queue_ide_command(
            "apply_workspace_edit",
            json!({
                "edits": [
                    { "path": "src/lib.rs", "text": "pub fn changed() {}\n" },
                    { "path": "src/new.rs", "create": true, "text": "pub fn new_file() {}\n" },
                    { "path": "missing/other.rs", "text": "pub fn missing() {}\n" }
                ],
                "save": false
            }),
            IdeCommandOptions {
                command_dir: None,
                cwd: Some(root.clone()),
                wait_ms: 0,
            },
        )
        .expect("queue command");
        let command_file = root.join(".agent-bridge").join(COMMANDS_FILE);

        assert_eq!(v["queued"], false);
        assert_eq!(v["status"], "blocked");
        assert_eq!(v["create_file_gate"]["verdict"], "blocked");
        assert!(v["create_file_gate"]["reasons"]
            .as_array()
            .expect("reasons")
            .contains(&json!("create_flag_missing")));
        assert!(
            !command_file.exists(),
            "mixed batch failure must not be queued"
        );
    }

    #[test]
    fn ide_command_save_and_format_missing_paths_do_not_use_create_file_gate() {
        let tmp = tempfile::tempdir().expect("tempdir");
        let root = tmp.path().join("project");
        std::fs::create_dir_all(&root).expect("mkdir root");

        for command in ["save_file", "format_document"] {
            let v = queue_ide_command(
                command,
                json!({ "path": "src/new.rs", "create": true }),
                IdeCommandOptions {
                    command_dir: None,
                    cwd: Some(root.clone()),
                    wait_ms: 0,
                },
            )
            .expect("queue command");

            assert_eq!(v["queued"], false, "{command} must stay blocked");
            assert!(
                v.get("create_file_gate").is_none(),
                "{command} must not use apply_workspace_edit create gate"
            );
        }
    }

    #[test]
    fn ide_command_wait_reads_response() {
        let dir = std::env::temp_dir().join(format!(
            "agent-bridge-ide-response-{}-{}",
            std::process::id(),
            SystemTime::now()
                .duration_since(UNIX_EPOCH)
                .unwrap_or_default()
                .as_nanos()
        ));
        std::fs::create_dir_all(&dir).expect("mkdir");
        let response_path = dir.join(RESPONSES_FILE);
        std::fs::write(
            &response_path,
            "{\"id\":\"known\",\"ok\":true,\"result\":{\"done\":true}}\n",
        )
        .expect("write response");
        let found = wait_for_response(&response_path, "known", 1).expect("response");
        let _ = std::fs::remove_dir_all(&dir);

        assert_eq!(found.unwrap()["result"]["done"], true);
    }
}
