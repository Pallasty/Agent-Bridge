# AG-UI Read-Only MCP Wrapper v0

- Date: 2026-08-25
- Status: D5 runtime gate authorized; integration candidate not yet published or activated
- Pure projector: `agent_bridge.ag_ui_readonly_projection.v0`
- Tool: `ag_ui_readonly_project`
- External wire pin: `@ag-ui/core@0.0.57`
- Related design: `AG_UI_SEMANTIC_BUS_READ_ONLY_ADAPTER_V0_2026_08_23.md`

> Version note (2026-08-26): this v0 contract remains supported unchanged. The same fieldless tool's
> opt-in v1 request/projection behavior is specified in
> `AG_UI_OPENBOT_REQUEST_COMPLETENESS_V1_D6_2026_08_26.md`.

## Decision summary

The source candidate contains a fieldless MCP wrapper that accepts one caller-supplied bounded AG-UI
batch and returns the existing pure, content-minimized projection. The wrapper owns no `Hub`, store,
transport, process, browser, mobile, policy, lease, filesystem, or environment handle. Its execution
body calls only `project_ag_ui_readonly` and formats that result for MCP.

The tool is default-off. It may be exposed only by an explicit named toolset or the already
explicit `all-dev` surface. It must remain absent from the default profile, `essential`, `standard`,
`codex-essential`, `codex-lean`, Claude standard, Gemini lean, ChatGPT read/collab, and hook
lifecycle surfaces.

`codex-ag-ui-readonly` means that the added AG-UI projector is read-only; it is otherwise the
existing `codex-lean` toolset, whose other tools retain their normal per-tool authority. The name is
not a claim that every tool in that toolset is read-only.

This document does not authorize remote publication, merge, deployment, MCP reconnection, runtime
activation, or AG-UI transport.

## Context

The pure projector at commit `122cb374744b21f46657fc29dda21994720b789b` passed focused unit,
sequence-corpus, canonicalization, leak, formatting, Clippy, and compile gates. The dormant wrapper
landed at `3e25f583578f7d737f671eea9da9339a69f5d0e2`; default-off source registration landed at
`1574541b389318059a6628473878afce2196c6a5`.

D4 independent protocol/security/content-minimization review returned `CHANGES_REQUIRED`: the MCP
schema declared the request, `protocol`, and `source` objects closed, but the server dispatched
arguments without performing JSON Schema validation and the pure validator ignored extra keys.
D4.1 therefore enforces those three closed objects inside the pure validator and returns only a
stable object coordinate on rejection. Unknown key names and their URL, path, endpoint, or
credential-shaped values are never echoed. Event objects remain governed by the pinned AG-UI
0.0.57 validator.

## Constraints

- The wrapper accepts only the existing projection request; it does not fetch or subscribe to an
  AG-UI endpoint.
- The protocol and package pin remains exactly `0.0.57`.
- The existing 500-event, 1 MiB request, and 256-byte identifier budgets remain authoritative.
- No raw event, message, reasoning, tool argument, tool result, state value, extension label,
  credential, URL, or path is returned.
- No AG-UI event can establish an AB `verified` outcome.
- The wrapper has no `Hub` constructor argument or stored field.
- Registration and runtime activation are later, separate gates.

## Architecture

```text
caller-supplied MCP arguments
            |
            v
AgUiReadonlyProjectTool               fieldless; no Hub; no I/O
            |
            | exactly one domain call
            v
project_ag_ui_readonly(&args)          pure AG-UI 0.0.57 projector
            |
            v
projection or typed redacted error     MCP text + structured content only
```

The source layout is:

```text
crates/bridge/src/ag_ui_readonly_projection.rs   pure protocol/state machine
crates/bridge/src/mcp_tools/ag_ui_readonly.rs    fieldless MCP transport wrapper
crates/bridge/src/mcp_tools.rs                   default-off policy and registration
```

`mcp_tools/ag_ui_readonly.rs` must use explicit imports. It must not use `super::*`, because that
would make the large `mcp_tools.rs` authority surface silently available to the wrapper.

## MCP interface

### Tool descriptor

| Field | Decision |
| --- | --- |
| Name | `ag_ui_readonly_project` |
| Title | `Project an AG-UI 0.0.57 batch read-only` |
| Annotation | `ToolAnnotations::read_only()` |
| Input | the existing `agent_bridge.ag_ui_readonly_projection_request.v0` object |
| Success | the existing `agent_bridge.ag_ui_readonly_projection.v0` object |
| Failure | typed, redacted `agent_bridge.ag_ui_readonly_projection_error.v0` object |
| Embedded resource | none |
| URI or filesystem input | none |

The MCP input schema mirrors the pure request and sets `additionalProperties=false` on the request,
`protocol`, and `source` objects. Event objects remain governed by the pinned pure validator rather
than a second partial event schema in the wrapper.

The wrapper must pass the complete MCP argument object directly to `project_ag_ui_readonly`. It must
not normalize, enrich, reorder, fetch, reconstruct, or persist events.

### Success response

The success `structured_content` is the pure projection object without an additional wrapper
envelope. Text content is a serialization of that same projection and contains no caller input not
already admitted by the pure projector. The wrapper adds no timestamp, host identity, runtime
version, tool list, or side-effect claim, keeping equal inputs semantically equal across calls.

### Error response

Errors expose only a stable code and bounded structural coordinates already carried by
`AgUiProjectionError`, for example an event index, field name, actual byte count, and maximum byte
count. They never echo the rejected value.

```json
{
  "schema": "agent_bridge.ag_ui_readonly_projection_error.v0",
  "read_only": true,
  "executes_actions": false,
  "writes_store": false,
  "changes_policy": false,
  "code": "identifier_too_long",
  "details": {
    "event_index": 3,
    "field": "runId",
    "actual_bytes": 300,
    "max_bytes": 256
  }
}
```

Human-readable MCP error text contains only the stable code. It must not use debug formatting on the
input or serialize the failing event.

## Identifier authority decision

`RUN_STARTED` outer `threadId`, `runId`, and optional `parentRunId` are the sole
projection-correlation identifiers. When `RUN_STARTED.input` repeats them, the pure projector
compares the validated raw strings byte-for-byte:

- `run_input_thread_id_mismatch` for a different thread ID;
- `run_input_run_id_mismatch` for a different run ID;
- `run_input_parent_run_id_mismatch` for a different or presence-mismatched parent run ID.

The outer values continue to drive the diagnostic state machine. A mismatch forces
`stream_complete=false`, never changes the verdict above `unknown` / `not_verified`, and never
returns either embedded value. Comparing raw bounded strings avoids treating a hash collision as
equality. This pure-projector hardening is required before wrapper registration.

## `CUSTOM` and `RAW` minimization decision

The wrapper and projector retain only:

- the number of `CUSTOM` / `RAW` events; and
- the serialized byte count of their payloads.

They retain no `CUSTOM.name`, `RAW.source`, name/source hash, or projected semantic event. Extension
labels can reveal vendors, tenants, internal operations, or routing conventions, while v0 has no
consumer that needs their correlation. This chooses the current implementation's more private
behavior over the earlier design table's name-hash wording.

## Exposure policy

The eventual registration design introduces a named `codex-ag-ui-readonly` toolset containing the
bounded Codex lean read surface plus `ag_ui_readonly_project`. The tool remains `Tier::Niche`, so the
normal profile-based default and standard surfaces do not gain it. `all-dev` may include it because
that surface is already an explicit broad development opt-in.

Required registry assertions:

| Toolset/profile | Expected exposure |
| --- | --- |
| unset/default | absent |
| `essential`, `compact`, `standard` | absent |
| `codex-essential`, `codex-lean` | absent |
| `claude-standard`, `gemini-lean` | absent |
| `chatgpt-read`, `chatgpt-collab`, `hook-lifecycle` | absent |
| `codex-ag-ui-readonly` | present |
| `all-dev` | present |

Changing `AGENT_BRIDGE_TOOLSET` still requires a fresh MCP process/reconnect. Source registration,
installation, and a fresh-process tool-list receipt remain distinct gates.

## Static architecture gate

Before source registration, an architecture test must read
`mcp_tools/ag_ui_readonly.rs` and enforce all of the following:

1. `AgUiReadonlyProjectTool` is a unit/fieldless struct and `new()` takes no arguments.
2. The file explicitly imports `project_ag_ui_readonly`; it does not use `super::*`.
3. The `execute` body contains exactly one domain-function call:
   `project_ag_ui_readonly(&args)`.
4. The `execute` body contains no `.await`, unsafe block, thread creation, background task, or
   callback registration.
5. Imports, type paths, and call paths are restricted to the projector plus MCP/result-formatting
   types. They contain none of these authority identifiers or paths: `Hub`, `StateStore`,
   `record_semantic_event`, `ToolPolicy`, `TokioCommand`, `crate::hub`, `ab_store`,
   `crate::security`, `crate::embodiment`, `crate::browser`, `crate::mobile`,
   `crate::world_tools`, `reqwest`, `std::process`, `tokio`, `std::fs`, `std::net`, or `std::env`.
6. The tool descriptor returns `ToolAnnotations::read_only()` and an output schema that fixes
   action/store/policy booleans to `false`.
7. The registry matrix proves the exposure table above and detects accidental profile widening.

The source gate is intentionally redundant with runtime tests. It makes a later edit that adds a
store or actuator dependency fail before a behavioral test can miss the path.

## Behavioral and protocol gates

Wrapper implementation is not admissible for registration until all of these pass:

- the pure projector cross-checks outer and embedded run identifiers;
- every one of the 33 known AG-UI 0.0.57 event types has valid, missing-required-field, and
  wrong-type table cases;
- a small independent model oracle covers run, step, and tool state transitions rather than only
  action prefixes;
- exact 256-byte identifier, 500-event, and 1 MiB request boundaries pass/fail on the correct side;
- multi-byte UTF-8 identifiers and request bodies are measured in bytes, not characters;
- reordered input object keys produce the same canonical projection digest;
- scalar and object canaries in all generic/content-bearing input fields never appear in success or
  error output;
- no verdict status or error value can equal the exact string `verified` through the wrapper's
  success or error paths;
- wrapper results match direct pure-projector results for every fixed fixture;
- default and named-toolset registry matrices match the exposure policy exactly.

## Falsifiers

Any of the following rejects the wrapper or returns it to design review:

- a default tool list exposes `ag_ui_readonly_project`;
- the wrapper owns or receives a `Hub` or other capability-bearing handle;
- a caller can supply a URL, credential, path, endpoint, agent transport, or persistence target;
- raw input content, extension names/sources, or rejected values appear in output or logs;
- an outer/embedded run-identifier mismatch is silently accepted as a complete stream;
- `TOOL_CALL_END`, `TOOL_CALL_RESULT`, or `RUN_FINISHED` yields `verified`;
- wrapper execution writes a semantic event or store row, touches the filesystem, opens a socket,
  starts a process, controls a browser/mobile/terminal surface, changes policy, or acquires a lease;
- registration, runtime activation, merge, push, or deployment is inferred from source-only tests.

## Alternatives considered

### Register the pure module directly from `mcp_tools.rs`

Rejected. It would mix policy registration, transport formatting, and the protocol state machine,
making the authority boundary harder to inspect and test.

### Give the wrapper a `Hub` for future extensibility

Rejected. The present tool has no legitimate use for stores, runtimes, browser/mobile surfaces, or
leases. Future capabilities must use a different, independently reviewed tool rather than widening
this wrapper.

### Expose the tool as ordinary `Standard` read-only functionality

Rejected. Read-only does not make a niche external-protocol surface universally useful, and default
exposure would expand every MCP client's schema and data-ingestion surface.

### Add AG-UI HTTP/SSE transport now

Rejected. Transport introduces authentication, endpoint trust, retry, stream lifetime, and
server-side request forgery concerns that are deliberately outside v0.

## Consequences

### Positive

- AG-UI compatibility becomes inspectable through MCP without gaining action authority.
- The wrapper remains small enough for static dependency and call-boundary tests.
- Default tool surfaces and current runtime behavior remain unchanged.
- Content minimization and AB-native verification semantics survive the transport boundary.

### Negative

- Callers must provide complete bounded batches; live streams are not supported.
- The explicit toolset and reconnect requirement add activation ceremony.
- Name/source omission prevents extension-type correlation beyond aggregate counts.
- The named toolset needs explicit documentation because only the projector, not the full
  `codex-lean` base surface, is read-only.

## Performance budget

- Time: linear in at most 500 events, with no network or storage wait.
- Memory: bounded by the 1 MiB input plus projection/state-machine allocations.
- Output: bounded by projected lifecycle/tool rows, counters, and violations; never includes raw
  content bodies.
- Concurrency: no spawned task and no state shared between calls.

## Gate sequence

1. **D0 — design:** complete.
2. **D1 — pure hardening:** complete; outer/embedded ID checks and protocol/boundary tests remain
   source-only.
3. **D2 — dormant wrapper:** complete at `3e25f583578f7d737f671eea9da9339a69f5d0e2`.
4. **D3 — source registration:** complete at `1574541b389318059a6628473878afce2196c6a5`;
   the tool remains default-off and undeployed.
5. **D4 — independent review:** complete with `CHANGES_REQUIRED` for runtime enforcement of the
   closed request envelope plus toolset-authority and document clarification.
6. **D4.1 — source remediation:** verified in this candidate; focused projection/wrapper tests,
   registry regression, all-target compilation, formatting, and content-minimization review pass.
7. **D5 — runtime gate:** authorized 2026-08-26; reconcile the shared remotes,
   merge/build/install, reconnect MCP, and verify the exact fresh-process tool list and projection
   behavior. Runtime acceptance remains process-bound evidence outside this source document.

Current verdict: `D5_AUTHORIZED_INTEGRATION_CANDIDATE_PENDING_RUNTIME_VERIFICATION`.

This verdict records authorization but does not claim that publication, deployment, MCP
reconnection, or runtime verification has completed.
