# S5ZT Story MCP registry wiring

## Outcome

The native `story_command_preflight` adapter is now wired into the Agent-Bridge
source composition root. The crate exports `story_contract` internally,
`mcp_tools` declares the adapter module, and the real runtime registry parses
the story configuration once per registry build.

Registration remains fail closed:

- disabled or unset activation leaves the tool absent;
- malformed enabled configuration emits a warning and leaves the tool absent;
- complete enabled configuration still passes through the `Niche` policy;
- codex-essential and codex-voice eager allowlists are unchanged.

## Isolation and verification

The shared files contained unrelated worktree changes. Only the three Story
hunks were staged. A clean tree was exported from that staged index and passed
`cargo check -p ab-bridge --lib --locked --offline`, proving the result does
not rely on the unrelated worktree-only `Cargo.toml` change. The isolated Rust
adapter suite passed 7 tests and the wiring source contract passed 4 tests.

This is source wiring, not runtime adoption. No binary was deployed, no client
was refreshed, and the tool has not been observed or invoked through a live
MCP client. Those actions belong to the next deployment-adoption review.
