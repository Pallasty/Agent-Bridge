# IDE Snapshot Bridge

`ide_snapshot` is the first IDE-facing perception tool for agent-bridge. It is
intentionally file-based: VS Code, Cursor, Windsurf, or a small script can write
the same JSON shape, and MCP clients can read it without linking to a specific
editor API.

For Codex running inside an IDE host, install the Codex MCP entry with:

```bash
agent-bridge setup --frontend codex-ide
```

This keeps `AGENT_BRIDGE_TOOLSET=codex-essential`, marks
`AGENT_BRIDGE_CODEX_HOST=ide`, and skips Codex desktop lifecycle hooks. The IDE
extension or script remains responsible for writing the snapshot file below.

## Lookup Order

The MCP tool reads the first existing file from:

1. the explicit `path` argument,
2. `AGENT_BRIDGE_IDE_SNAPSHOT`,
3. `<cwd-or-ancestor>/.agent-bridge/ide-snapshot.json`,
4. `$XDG_RUNTIME_DIR/agent-bridge/ide-snapshot.json`,
5. `$HOME/.local/share/agent-bridge/ide-snapshot.json`.

When nothing exists, the tool returns `available=false` plus the expected JSON
contract. This makes it safe to call at session bootstrap before an IDE
extension is installed.

## Snapshot Contract

Minimum useful payload:

```json
{
  "schema_version": 1,
  "ide": { "name": "vscode", "version": "1.x" },
  "workspace_root": "/abs/project",
  "active_file": "/abs/project/src/main.rs",
  "selection": {
    "file": "/abs/project/src/main.rs",
    "range": {
      "start": { "line": 12, "character": 4 },
      "end": { "line": 14, "character": 1 }
    },
    "text": "selected source text"
  },
  "open_files": [
    { "path": "/abs/project/src/main.rs", "language": "rust", "is_dirty": false }
  ],
  "diagnostics": [
    {
      "file": "/abs/project/src/main.rs",
      "severity": "error",
      "message": "cannot find value `foo` in this scope",
      "source": "rust-analyzer",
      "code": "E0425",
      "range": {
        "start": { "line": 12, "character": 4 },
        "end": { "line": 12, "character": 7 }
      }
    }
  ],
  "tasks": [
    { "name": "cargo test --workspace", "status": "failed", "summary": "1 test failed" }
  ]
}
```

Line and character values should use the IDE/LSP convention: zero-based lines
and UTF-16-ish editor characters are acceptable as long as the writer is
consistent. The agent treats ranges as hints, not as authoritative byte offsets.

## Workspace Boundary Evidence

`ide_snapshot` adds a read-only `workspace_boundary` object to the normalized
output. IDE writers do not need to provide this field. Agent-Bridge derives it
from `workspace_root`, `active_file`, `selection.file` / `selection.path` /
`selection.uri`, `open_files[*].path` / `file` / `uri`, and
`diagnostics[*].file` / `path` / `uri`.

The evidence canonicalizes the workspace root and candidate paths before
reporting containment. It reports relations such as `inside_workspace`,
`outside_workspace`, `missing_path`, and `no_workspace_root`; it does not block,
rewrite, or hide any snapshot field.

## Recommended Implementation Path

## Command Bridge

`ide_command` adds the write-side half of the bridge. The MCP tool appends
requests to:

```text
<workspace>/.agent-bridge/ide-commands.jsonl
```

The IDE extension consumes each JSONL request and appends a matching response to:

```text
<workspace>/.agent-bridge/ide-responses.jsonl
```

Request shape:

```json
{
  "schema_version": 1,
  "id": "idecmd-...",
  "created_at_unix_ms": 1780000000000,
  "command": "open_file",
  "args": {
    "path": "/abs/project/src/main.rs",
    "range": {
      "start": { "line": 12, "character": 4 },
      "end": { "line": 12, "character": 9 }
    }
  }
}
```

Response shape:

```json
{
  "schema_version": 1,
  "id": "idecmd-...",
  "command": "open_file",
  "ok": true,
  "completed_at": "2026-05-17T12:00:00.000Z",
  "result": { "file": "/abs/project/src/main.rs" }
}
```

Supported commands in the VS Code/Cursor example:

- `open_file`: `{ "path": "/abs/file", "range": optional, "preview": false }`
- `reveal_range`: same args as `open_file`; opens and scrolls to `range`
- `run_task`: `{ "name": "task name as shown by VS Code" }`
- `write_snapshot`: `{}`

`ide_command` is intentionally queue-based. If the extension is not running,
commands remain visible on disk and the MCP call returns `status=queued` or
`status=timeout` when `wait_ms` is set.

## Implementation Path

Phase 1, landed:

- `ide_snapshot` MCP tool reads, normalizes, truncates, and marks stale snapshots.
- `ide_snapshot` adds read-only workspace-boundary evidence for snapshot paths.
- The tool is editor-agnostic and registered in the Essential profile.

Phase 2, landed:

- Minimal dependency-free example lives at
  `examples/vscode-ide-snapshot/`.
- On `activeTextEditor` changes, selections, document open/close, saves, and
  diagnostics changes, rewrite the snapshot atomically.
- Prefer `<workspace>/.agent-bridge/ide-snapshot.json` for project-local state.
- Include only diagnostics for the active workspace unless the user opts into a
  global runtime snapshot.
- The same extension polls `ide-commands.jsonl` and writes command responses.

Phase 3, richer IDE actions:

- Add guarded `apply_workspace_edit` once review/confirmation semantics are
  settled.
- Add debug/session state and test result capture.
- Keep LSP-derived data separate from editor UI state so headless language
  servers can later feed the same contract.
