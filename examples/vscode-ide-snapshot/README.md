# Agent Bridge IDE Snapshot Extension

Minimal VS Code/Cursor extension that writes the JSON consumed by the
`ide_snapshot` MCP tool.

## Run In An Extension Host

From this directory:

```bash
code --extensionDevelopmentPath="$PWD"
```

Open a workspace in the launched Extension Development Host. The extension writes
to:

```text
<workspace>/.agent-bridge/ide-snapshot.json
```

Override with the `agentBridge.snapshotPath` setting or
`AGENT_BRIDGE_IDE_SNAPSHOT`.

## Smoke Test

After opening a workspace, call the MCP tool:

```json
{
  "name": "ide_snapshot",
  "arguments": { "cwd": "/abs/project" }
}
```

Expected result: `available=true`, the active file, current selection,
workspace diagnostics, open text documents, and recent completed tasks.

## Command Bridge

The extension also polls:

```text
<workspace>/.agent-bridge/ide-commands.jsonl
```

and appends results to:

```text
<workspace>/.agent-bridge/ide-responses.jsonl
```

Supported commands:

- `open_file`
- `reveal_range`
- `run_task`
- `write_snapshot`
- `apply_workspace_edit`
- `save_file`
- `format_document`

Example MCP call:

```json
{
  "name": "ide_command",
  "arguments": {
    "cwd": "/abs/project",
    "command": "open_file",
    "args": {
      "path": "/abs/project/src/main.rs",
      "range": {
        "start": { "line": 12, "character": 4 },
        "end": { "line": 12, "character": 9 }
      }
    },
    "wait_ms": 2000
  }
}
```

`apply_workspace_edit` can update existing files or create a new leaf file when
the backend queued an explicit create edit:

```json
{
  "name": "ide_command",
  "arguments": {
    "cwd": "/abs/project",
    "command": "apply_workspace_edit",
    "args": {
      "edits": [
        {
          "path": "src/new_file.rs",
          "create": true,
          "text": "pub fn new_file() {}\n"
        }
      ],
      "save": true
    }
  }
}
```

The extension repeats the final authority check before applying edits:
new-file edits require `create: true`, string `text`, no `range`, an existing
parent directory that canonicalizes inside the workspace, and a missing target.
Existing-file edit/save/format commands must canonicalize inside the workspace.

## Notes

- This example is dependency-free JavaScript, so no `npm install` step is
  required for development-host use.
- Production packaging can be added later with `vsce` once the contract has
  settled.
- Cursor can run VS Code-compatible extensions; use the same extension
  development flow there.
