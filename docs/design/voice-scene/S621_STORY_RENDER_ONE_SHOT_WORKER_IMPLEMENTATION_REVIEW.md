# S621 Story render one-shot worker implementation review

## Status

Accepted as a source-only implementation review. No Worker, Supervisor, owner
broker, MCP tool, runtime enablement, or deployment is authorized by S621.

## Current source

The reviewed source contains the registered, read-only Story preflight and the
MCP cancellation path that aborts a tool future. It also contains an audited
owned-process-group reaper and already depends on `libc`, `serde`,
`serde_json`, `tokio`, and `uuid`.

The runtime surfaces required by S620 do not exist: there is no protocol codec,
one-shot Worker, Rust Supervisor, render MCP module, or
`story_command_render` registry entry. This review therefore avoids pretending
that S620's contract is an implementation.

## Implementation decision

The implementation is split into five gates:

1. Pure request/response codec and MCP redaction, with no I/O or authority.
2. Rust Supervisor tested only with synthetic child processes and temporary
   lock roots.
3. Private fixed-fixture Worker composition with injected fake authority and
   runner dependencies.
4. Independent owner-confirmation broker and real short-lived grant issuance.
5. Default-off MCP registration and separately authorized deployment review.

| Alternative | Benefit | Cost | Decision |
|---|---|---|---|
| Implement the complete runtime at once | Shortest path to a demo | Makes protocol, process, secret, model, and MCP failures inseparable | Reject |
| Begin with the real Python Worker | Exercises existing executor early | Reads/writes and model behavior obscure protocol correctness | Defer |
| Pure codec, then synthetic Supervisor | Deterministic failures and narrow rollback | More gates before audio | Select |

## S622 selected patch

The next patch may create only:

- `scripts/story_render_worker_protocol.py`
- `tests/test_story_render_worker_protocol.py`
- `docs/design/voice-scene/story_render_worker_request.schema.json`
- `docs/design/voice-scene/story_render_worker_response.schema.json`

The codec exposes four pure functions: `decode_request`,
`validate_worker_response`, `encode_error_response`, and
`project_mcp_response`. It receives bytes plus the S620 contract and may only
validate message shape, fixed bindings, limits, and redaction. It cannot verify
a MAC, consume a nonce, read environment or clock state, generate randomness,
touch the filesystem or network, import an executor/model runtime, or spawn a
process.

Rust, MCP Registry, Store, Audio, and the installed secure directory are
outside S622. This keeps its output reusable by both the future Worker and Rust
adapter without granting either runtime authority.

## Supervisor ownership decision

The later synthetic Supervisor will put the Child and host-lock descriptor in
an independently running cleanup task. The MCP future owns only a Drop guard
that signals cancellation. The cleanup task must terminate the process group,
wait for the Worker, validate or discard its bounded output, and release the
host lock. `kill_on_drop(true)` alone is insufficient because it does not prove
that descendants were killed or the process was waited before lock release.

Supervisor tests must cover success, malformed output, stdout/stderr overflow,
hang, cancellation, and a descendant that ignores `SIGTERM`. They may spawn
only repository-owned synthetic fixtures and write only beneath temporary test
directories. No new Cargo dependency is selected.

## Owner authority boundary

An MCP tool call is not independent proof of owner approval. Letting the MCP
process sign inline, letting the Worker self-sign, or accepting a caller-supplied
envelope as sufficient would allow an Agent to manufacture its own authority.
All three are rejected.

The real owner-confirmation mechanism remains a separate design gate after the
pure codec and synthetic Supervisor have passed. Until that gate is verified,
the real installed key cannot be read and no render tool can be registered.

## Consequences

The selected ladder delays another live audio trial, but it makes protocol
parsing, redaction, cancellation, process ownership, private custody, and owner
authority independently testable. S621 records 23 fail-closed cases and leaves
all implementation, execution, configuration, and deployment effects false.

The next gate is `story_render_worker_protocol_codec_implementation`.
