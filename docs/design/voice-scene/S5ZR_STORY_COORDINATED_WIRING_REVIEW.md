# S5ZR coordinated story wiring review

## Outcome

The isolated story MCP adapter is ready for a minimal wiring patch, but the
patch is deferred. `lib.rs`, `mcp_tools.rs`, and `Cargo.toml` all have active
unrelated worktree overlap, while shared Cargo jobs are compiling the same
crate. S5ZR records that distinction as “patch contract admitted, wiring
implementation not admitted.”

## Frozen minimal patch

- Export `story_contract` as crate-private and declare the `mcp_tools::story`
  submodule.
- Parse `StoryMcpConfig` once during registry construction and register
  `StoryCommandPreflightTool` only for a complete enabled configuration.
- Keep `story_command_preflight` at `Niche`; do not add it to default,
  essential, or voice eager profiles.
- Treat an invalid enabled configuration as a warning plus an absent tool.
  Disabled mode remains silently absent.
- Add no dependency and make no `Cargo.toml` change.

The future implementation must prove disabled and invalid configurations are
absent, a complete configuration is visible only through the Niche/all-dev
surface, and eager profiles remain unchanged.

## Boundaries

This review does not modify the Rust module tree, registry, or manifest. It
does not register, expose, deploy, or invoke the tool; refresh a client; load a
model; render or play audio; or write memory. The next gate is a fresh
readiness recheck after the shared surfaces and Cargo activity are clean.
