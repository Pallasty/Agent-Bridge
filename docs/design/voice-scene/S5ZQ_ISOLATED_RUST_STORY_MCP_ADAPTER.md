# S5ZQ isolated Rust story MCP adapter

## Outcome

S5ZQ adds an isolated `StoryCommandPreflightTool` implementation without
declaring it in the module tree or registering it. The adapter is compiled only
through its path-bound integration test.

## Adapter behavior

- `StoryMcpConfig::from_env` and the testable `from_values` parser require the
  exact S5ZP activation, root, byte-limit, evidence-path, and evidence-hash
  contract. Disabled mode needs no file configuration; enabled mode requires
  every field.
- Input uses a deny-unknown-fields structure matching the frozen MCP schema:
  `source_path`, structured `start`, and `dry_run=true`.
- `StoryPreflightCancelOnDrop` owns the same cancellation token as the blocking
  worker. MCP abort drops the tool future and therefore the armed guard, which
  cancels the worker cooperatively. Normal completion disarms the guard.
- Accepted output is returned in both structured and legacy text channels.
  Rejections become `ToolResult::error`; they do not panic the MCP server.
- The descriptor is read-only and retains the S5ZP `Niche`, opt-in placement
  contract for future wiring.

## Verification and nonclaims

Seven Rust tests cover disabled/complete/malformed configuration, descriptor
shape, S5ZF parity, structured output, strict arguments, and cancellation. The
accepted preflight digest remains
`6553dcec1ad51e1b6352d0fc7fa2068b38713d1e37dedacbe45b00f3aca4a1bb`.

The file is not declared by `mcp_tools.rs`; `story_contract` is not exported by
`lib.rs`; no registry entry, exposure, deployment, reconnect, model, ONNX,
audio, cache, or memory action occurs. Coordinated module and registry wiring
review is the next gate.
