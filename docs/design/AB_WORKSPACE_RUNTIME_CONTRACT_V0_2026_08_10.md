# AB Workspace Runtime Contract v0

## Decision

Agent-Bridge agent runtimes expose a construction-time, read-only execution
descriptor through `AgentRuntime::workspace_contract()`. The existing
`capabilities` MCP tool projects every registered backend and marks the daemon
default. No additional MCP tool is introduced.

The descriptor records:

- source kind and execution locality;
- one-shot, interactive, cancellation, and live-output support;
- local workspace sandbox, remote sandbox, and network-isolation support.

Support uses three states: `supported`, `unsupported`, and `unknown`. Missing
runtime declarations default to `unknown`, which never grants routing
authority.

## Routing Rule

`agent_spawn` validates requests that depend on declared runtime properties
before starting a process:

- the source kind must be `agent_prompt` and one-shot calls require explicit
  one-shot support;
- runtime locality must be known;
- interactive requests require explicit interactive support;
- a remote node requires `local_or_remote` locality;
- a requested workspace sandbox requires explicit support at the selected
  locality.

Ordinary local one-shot requests retain their existing behavior. Explicit
backend selection and the configured fallback order are unchanged.

## Boundary

This contract is metadata for compatibility checks, not proof that a sandbox
or network boundary was enforced for a particular run. Session receipts remain
the source of launch intent, and runtime-specific launchers remain responsible
for enforcement.

In particular, v0:

- does not integrate or deploy `cloudflare/computer`;
- does not add a generic shell or module execution source;
- does not claim network isolation for any current backend;
- does not enable remote sandboxing, cloud execution, or new defaults;
- does not change the installed Agent-Bridge daemon.

The useful pattern extracted from `cloudflare/computer` is explicit backend
capability discovery before execution. A future backend can implement this
trait contract, but admission still requires separate security, lifecycle, and
real-task evidence.

## Acceptance

- all built-in runtimes publish explicit descriptors;
- descriptors are stable-sorted and identify the default backend;
- unknown or unsupported requested capabilities fail before process spawn;
- focused contract tests and `cargo check -p ab-bridge --all-targets` pass.
