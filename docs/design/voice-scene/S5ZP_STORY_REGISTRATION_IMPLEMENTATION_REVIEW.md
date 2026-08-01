# S5ZP story registration implementation review

## Decision

Implement the Rust MCP transport adapter in isolation before any module-tree or
registry wiring. The isolated adapter is admitted; registry wiring is not.

## Why direct wiring is rejected

The MCP server handles `notifications/cancelled` by aborting the in-flight tool
task. Aborting drops the tool future. S5ZO supports explicit token
cancellation, but no drop guard currently turns future destruction into token
cancellation. A transport adapter must own such a guard so its blocking worker
observes cancellation after the MCP future is dropped.

In addition, both `lib.rs` and `mcp_tools.rs` contain active unrelated mobile
work. Direct edits would overlap that work and would invalidate the exact
registry provenance again. The current registry has no
`story_command_preflight` name collision, but absence of collision is not
permission to edit an active integration surface.

## Isolated adapter contract

The next unit may add `crates/bridge/src/mcp_tools/story.rs` and isolated tests.
It must:

- parse only `source_path`, `start`, and `dry_run=true`;
- require `AB_STORY_COMMAND_PREFLIGHT_ENABLE=1` and a complete source/evidence
  configuration before it can be considered exposable;
- construct a future-drop cancellation guard;
- return structured success and `ToolResult::error` for invalid inputs or
  contract failures;
- retain `Niche` placement with no default, codex-essential, or codex-voice
  extras.

The environment contract is frozen in the machine receipt. Missing variables,
invalid hashes, root escape, oversized files, evidence drift, runtime flags,
or cancellation must fail closed.

## Nonclaims

S5ZP does not add the adapter file, export `story_contract`, register or expose
the tool, deploy a binary, reconnect a client, load a model, render/play audio,
or write cache/memory. The next gate is `isolated_rust_story_mcp_adapter`.
