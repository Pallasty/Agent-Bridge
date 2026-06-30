# AB Workspace Boundary Evidence Plan - 2026-06-30

Status: AB-BORROW-2 planning artifact. The first read-only `ide_snapshot`
evidence slice is implemented; `ide_command` follow-up remains pending.

This note closes the planning step for the borrowed workspace-boundary pattern
from `docs/design/BORROWED_PATTERNS_BACKLOG_2026_06_09.md`. It turns the
borrow into an Agent-Bridge-native evidence contract for `ide_snapshot`,
`ide_command`, and future file-backed adapters.

## Current State

`crates/bridge/src/ide.rs` already has a useful file-backed IDE bridge:

- `ide_snapshot` reads an explicit path, `AGENT_BRIDGE_IDE_SNAPSHOT`,
  ancestor `.agent-bridge/ide-snapshot.json`, runtime-dir snapshot, or data-dir
  snapshot.
- `ide_snapshot` is read-only and returns source path, age/staleness, raw
  `workspace_root`, active file, selection, open files, diagnostics, tasks, and
  derived `workspace_boundary` evidence.
- `ide_command` appends JSONL requests to an IDE command directory and can wait
  for a matching response.
- The command queue supports read/navigation commands and richer future commands
  such as `apply_workspace_edit`, `save_file`, and `format_document`.

The remaining part is command-side use of explicit workspace-boundary evidence:

- command directory resolution does not prove that queued command paths are
  under the workspace;
- exclude or `.gitignore` evidence is surfaced as advisory `not_evaluated`;
- mutating IDE commands do not yet require contained paths before queueing.

## Evidence Contract

Future read models should include a `workspace_boundary` object when a snapshot
or command has enough information to evaluate paths:

```json
{
  "schema": "agent_bridge.workspace_boundary_evidence.v0",
  "mode": "read_only_evidence",
  "workspace_root": {
    "input": "/abs/project",
    "canonical": "/abs/project",
    "exists": true,
    "is_dir": true
  },
  "paths": [
    {
      "role": "active_file",
      "input": "/abs/project/src/main.rs",
      "canonical": "/abs/project/src/main.rs",
      "exists": true,
      "contained": true,
      "relation": "inside_workspace",
      "reason": "canonical path has workspace root as ancestor"
    }
  ],
  "excludes": {
    "status": "not_evaluated",
    "sources": []
  },
  "verdict": "contained"
}
```

The evidence must be conservative:

- canonicalize both root and candidate before deciding containment;
- never use string-prefix checks as the authority;
- report `missing_path` instead of guessing when a candidate does not exist;
- report `no_workspace_root` when the writer did not provide one;
- report `outside_workspace` for canonical paths that escape the root;
- keep exclude handling advisory until a `.gitignore`/ignore parser is wired.

## First Code Slice

The first code slice is read-only:

1. Add a helper that resolves `workspace_root` and candidate paths into the
   evidence shape above.
2. Add `workspace_boundary` to `ide_snapshot` output for:
   - `active_file`;
   - `selection.file` or `selection.path`;
   - `open_files[*].path` / `file` / `uri` where file-path-like;
   - `diagnostics[*].file` / `path` / `uri`.
3. Do not block or rewrite values in this first slice. The output is evidence,
   not enforcement.

Acceptance tests for the first slice:

- canonical inside path is contained;
- `..` that normalizes inside is contained;
- `..` that escapes is outside;
- symlink inside the workspace pointing outside is outside after canonicalize;
- missing candidate reports `missing_path`;
- missing workspace root reports `no_workspace_root`;
- `ide_snapshot` remains available=false + contract when no snapshot exists.

## Command Queue Follow-Up

After read-only snapshot evidence lands, `ide_command` can consume the same
helper before queueing commands that carry paths.

Recommended behavior:

- `open_file` and `reveal_range`: include boundary evidence in the response; do
  not block in the first command slice unless the path is obviously invalid.
- `apply_workspace_edit`, `save_file`, and `format_document`: require a
  contained workspace path before queueing, because those commands can mutate
  user files when the IDE extension executes them.
- Keep the IDE extension responsible for its own final authority check. Agent-
  Bridge evidence is a safety preflight, not a sandbox.

## Non-Goals

- No direct file edits by Agent-Bridge.
- No attempt to sandbox the IDE process.
- No global filesystem crawl.
- No automatic `.gitignore` enforcement in the first slice.
- No change to MCP tool exposure profiles.

## Verification

For the planning slice in this document:

```bash
git diff --check
rg -n "workspace_boundary|AB-BORROW-2|ide_snapshot|ide_command" docs/design docs/IDE-SNAPSHOT-BRIDGE.md
```

For the later code slice:

```bash
cargo test -p ab-bridge --lib ide::tests -- --nocapture
```

If the later implementation touches MCP schema text, also run the focused MCP
registry tests for `ide_snapshot` and `ide_command`.
