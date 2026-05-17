# IDE Snapshot Bridge

`ide_snapshot` is the first IDE-facing perception tool for agent-bridge. It is
intentionally file-based: VS Code, Cursor, Windsurf, or a small script can write
the same JSON shape, and MCP clients can read it without linking to a specific
editor API.

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

## Recommended Implementation Path

Phase 1, now landed:

- `ide_snapshot` MCP tool reads, normalizes, truncates, and marks stale snapshots.
- The tool is editor-agnostic and registered in the Essential profile.

Phase 2, VS Code/Cursor extension:

- Minimal dependency-free example lives at
  `examples/vscode-ide-snapshot/`.
- On `activeTextEditor` changes, selections, document open/close, saves, and
  diagnostics changes, rewrite the snapshot atomically.
- Prefer `<workspace>/.agent-bridge/ide-snapshot.json` for project-local state.
- Include only diagnostics for the active workspace unless the user opts into a
  global runtime snapshot.

Phase 3, richer IDE actions:

- Add write-side tools only after the read contract is stable: open file, reveal
  range, apply workspace edit, run named task, fetch debug/session state.
- Keep LSP-derived data separate from editor UI state so headless language
  servers can later feed the same contract.
