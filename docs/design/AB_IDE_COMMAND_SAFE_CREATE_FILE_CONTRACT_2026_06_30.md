# Agent-Bridge IDE Command Safe Create-File Contract - 2026-06-30

Status: runtime slice implemented for Agent-Bridge pre-queue evidence and
blocking. The IDE extension still remains final authority when it consumes the
queued request.

This memo defines the runtime contract for allowing
`apply_workspace_edit` to create new files without weakening the current
workspace-boundary gate.

## Decision

Keep the current mutating-command gate unchanged by default:

- `apply_workspace_edit`, `save_file`, and `format_document` still require
  contained workspace-boundary evidence before queueing.
- A missing path without an explicit create-file intent still blocks before
  Agent-Bridge writes `ide-commands.jsonl`.
- `save_file` and `format_document` stay existing-file-only commands.
- Agent-Bridge does not directly write files. It only queues an IDE command
  after preflight evidence says the request is safe enough for the IDE to
  review and execute.

New-file creation is supported only for `apply_workspace_edit`, and only when
each created file is declared per edit with `create: true`.

## Proposed Request Shape

```json
{
  "command": "apply_workspace_edit",
  "args": {
    "workspace_root": "/abs/project",
    "edits": [
      {
        "path": "src/new_file.rs",
        "create": true,
        "text": "fn main() {}\n"
      }
    ]
  }
}
```

Contract rules:

- `create` defaults to `false`.
- `create: true` is evaluated per edit, not as a broad top-level flag.
- `create: true` requires a path, file, or file URI and `text` as the full file
  contents. An empty string is valid for an empty file.
- `range` must be omitted or null for a create edit.
- Relative targets resolve against the workspace root. Absolute paths and file
  URIs must still prove the same parent containment.
- The target path must not already exist.
- The parent directory must already exist, canonicalize successfully, and be
  contained inside the canonical workspace root.
- Lexical normalization must not let `.` or `..` escape the canonical parent or
  workspace root.
- The first implementation must not create parent directories.
- Existing-file edits keep using the current rule: the referenced file itself
  must exist and canonicalize inside the workspace.
- Mixed batches are allowed only when every edit independently passes its own
  rule. One failing edit blocks the whole command before queueing.

This keeps the safety property simple: a create edit can only materialize a new
leaf file under an already verified workspace-contained parent directory.

## Boundary Evidence

Do not silently reinterpret the existing `workspace_boundary` object so that a
missing file becomes `contained`. Missing targets should remain visible as
missing-path evidence.

Agent-Bridge adds a create-file-specific preflight block when the command
includes create edits or when a missing edit path could be explained by this
contract:

```json
{
  "schema": "agent_bridge.ide_command.create_file_gate.v0",
  "mode": "pre_queue_evidence",
  "verdict": "allowed",
  "applies_to": ["args.edits[0]"],
  "checks": [
    {
      "edit": 0,
      "explicit_create": true,
      "parent_exists": true,
      "parent_contained": true,
      "target_missing": true,
      "range_absent": true,
      "auto_mkdir": false,
      "extension_final_authority": true
    }
  ]
}
```

For blocked requests, the response should keep the existing
`workspace_boundary` evidence and add `create_file_gate.verdict="blocked"` with
specific reasons such as:

- `create_flag_missing`
- `create_path_missing`
- `create_range_present`
- `create_text_missing`
- `create_parent_missing`
- `create_parent_outside_workspace`
- `create_target_exists`
- `create_target_status_unknown`
- `workspace_root_missing`
- `mixed_batch_edit_failed`

The IDE extension remains the final authority. It should repeat the same
parent-containment and target-missing checks immediately before applying the
edit, because the filesystem can change after Agent-Bridge queues the command.

## Acceptance Tests

- Existing contained `apply_workspace_edit` still queues without
  `create_file_gate`.
- Missing `apply_workspace_edit` path without `create: true` still blocks and
  does not write `ide-commands.jsonl`.
- `create: true` with a contained existing parent and missing target queues.
- `create: true` where the target already exists blocks.
- `create: true` with a missing parent blocks.
- `create: true` with an outside or symlink-escaped parent blocks.
- `create: true` with a non-null range blocks.
- `create: true` without string `text` blocks.
- A mixed batch blocks when any edit fails either the existing-file or
  create-file rule.
- `save_file` and `format_document` missing paths still block.
- `open_file` and `reveal_range` remain advisory-only.
- Every blocked mutating command still leaves `ide-commands.jsonl` untouched.

## Implementation Notes

The runtime slice is intentionally small and local to `crates/bridge/src/ide.rs`:

1. Parse create edit intent from `args.edits[*].create`.
2. For non-create edits, keep using existing path-candidate containment.
3. For create edits, canonicalize the workspace root and target parent, then
   prove parent containment before allowing a missing target.
4. Return both `workspace_boundary` and `create_file_gate` evidence when create
   edits are present.
5. Preserve the queued JSONL request unchanged when queueing is allowed.

This is intentionally narrower than a general filesystem write API. The bridge
keeps its queue-based IDE shape, and the IDE keeps its review/undo surface.

## References

- `docs/IDE-SNAPSHOT-BRIDGE.md`
- `docs/design/AB_WORKSPACE_BOUNDARY_EVIDENCE_PLAN_2026_06_30.md`
- `crates/bridge/src/ide.rs`
- Forum #102 posts #2625 and #2627
- Commits `b6604b3`, `ae674e8`, `ac71ac8`, and `ca57c56`
