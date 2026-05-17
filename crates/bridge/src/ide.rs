//! IDE perception: a lightweight file-based bridge for editor state.
//!
//! The MCP stdio process cannot assume it lives inside VS Code/Cursor/Windsurf,
//! so v0 reads a small JSON snapshot written by whichever IDE integration is
//! available. This keeps the agent-facing contract stable while frontends vary.

use ab_core::{Error, Result};
use serde_json::{json, Map, Value};
use std::collections::BTreeMap;
use std::fs::OpenOptions;
use std::io::Write;
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
        "open_file" | "reveal_range" | "run_task" | "write_snapshot"
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

    let dir = resolve_command_dir(options.command_dir.as_deref(), options.cwd.as_deref())?;
    std::fs::create_dir_all(&dir).map_err(Error::Io)?;
    let request_path = dir.join(COMMANDS_FILE);
    let response_path = dir.join(RESPONSES_FILE);
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

    Ok(json!({
        "queued": true,
        "status": status,
        "id": id,
        "command": command,
        "command_dir": dir.display().to_string(),
        "request_path": request_path.display().to_string(),
        "response_path": response_path.display().to_string(),
        "response": response,
        "hint": if status == "timeout" {
            "command was queued but no IDE response arrived before wait_ms elapsed; make sure the IDE extension is running."
        } else {
            "IDE extension should consume ide-commands.jsonl and append to ide-responses.jsonl."
        },
    }))
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
        out.push(SnapshotSource {
            path: PathBuf::from(home)
                .join(".local/share/agent-bridge")
                .join("ide-snapshot.json"),
            source_kind: "data",
        });
    }

    out
}

fn resolve_command_dir(explicit_dir: Option<&Path>, cwd: Option<&Path>) -> Result<PathBuf> {
    if let Some(dir) = explicit_dir {
        return Ok(dir.to_path_buf());
    }
    if let Ok(dir) = std::env::var("AGENT_BRIDGE_IDE_COMMAND_DIR") {
        let dir = dir.trim();
        if !dir.is_empty() {
            return Ok(PathBuf::from(dir));
        }
    }
    if let Ok(snapshot) = std::env::var("AGENT_BRIDGE_IDE_SNAPSHOT") {
        let snapshot = snapshot.trim();
        if !snapshot.is_empty() {
            if let Some(parent) = Path::new(snapshot).parent() {
                return Ok(parent.to_path_buf());
            }
        }
    }

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
    Ok(base.join(".agent-bridge"))
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
