# AG-UI -> Semantic System Bus Read-Only Adapter v0

- Date: 2026-08-23
- Status: design-only; no runtime implementation
- External wire pin: `@ag-ui/core@0.0.57`
- External source pin: `ag-ui-protocol/ag-ui@54f13419055b4d0f442c71e1efab18b310982ce1`
- Reference consumer: `CopilotKit/OpenBot@2251ad266406ec8212235adba365d2c478437a0c`
- Proposed schema: `agent_bridge.ag_ui_readonly_projection.v0`

## Purpose

Define a bounded compatibility seam that explains an AG-UI event stream using Agent-Bridge Semantic
System Bus vocabulary without granting the stream execution authority.

The adapter is a pure projector:

```text
caller-supplied AG-UI events
        |
        v
validate version, order, ids, and budgets
        |
        v
derive redacted lifecycle and tool-call facts
        |
        v
return projection plus violations
```

It does not dial an AG-UI endpoint, register an agent, expose tools, execute tool calls, write memory,
write semantic events, acquire a body lease, change policy, or claim effects were verified.

## Input envelope

```json
{
  "schema": "agent_bridge.ag_ui_readonly_projection_request.v0",
  "protocol": {
    "name": "ag-ui",
    "core_version": "0.0.57"
  },
  "source": {
    "adapter_id": "caller-supplied",
    "agent_id_hash": "sha256:..."
  },
  "events": []
}
```

Required controls:

- `events`: 1-500 entries;
- serialized request: at most 1 MiB;
- any identifier: at most 256 UTF-8 bytes before hashing;
- unknown protocol version: reject the batch;
- unknown event type: count and omit by default;
- timestamps, sequence numbers, and run/tool IDs are observations, never authority tokens;
- no URL, auth header, cookie, credential, environment, or filesystem path is accepted as a control
  input in v0.

## Output envelope

```json
{
  "schema": "agent_bridge.ag_ui_readonly_projection.v0",
  "read_only": true,
  "executes_actions": false,
  "writes_store": false,
  "changes_policy": false,
  "protocol": {
    "name": "ag-ui",
    "core_version": "0.0.57"
  },
  "counts": {
    "input_events": 0,
    "projected_events": 0,
    "omitted_content_events": 0,
    "unknown_event_types": 0,
    "violations": 0
  },
  "runs": [],
  "tool_calls": [],
  "violations": [],
  "claims": {
    "all_actions_traceable": false,
    "external_effects_verified": false,
    "stream_complete": false
  }
}
```

No raw AG-UI event is echoed.

## Event mapping

| AG-UI 0.0.57 event | Projection | SSB verdict rule | Content handling |
| --- | --- | --- | --- |
| `RUN_STARTED` | run lifecycle opened | `unknown` | retain hashed `threadId`/`runId`; omit embedded input |
| `RUN_FINISHED` | run lifecycle closed | `unknown` for success/legacy; `not_verified` for `outcome.type=interrupt` | omit result and interrupt payloads |
| `RUN_ERROR` | run lifecycle failed | `not_verified` | retain bounded error class/code hash; omit message |
| `STEP_STARTED` | step lifecycle opened | `unknown` | hash step name/id |
| `STEP_FINISHED` | step lifecycle closed | `unknown` | no effect claim |
| `TOOL_CALL_START` | tool intent opened | `unknown` | hash tool-call ID; retain normalized tool name only if allowlisted-safe |
| `TOOL_CALL_ARGS` | intent payload observed | no event emitted by default | count bytes and chunks; never retain args/delta |
| `TOOL_CALL_END` | tool request assembly closed | `unknown` | not evidence of dispatch or effect |
| `TOOL_CALL_CHUNK` | compact tool-call fragment | omitted in v0 | count bytes only; do not reconstruct content |
| `TOOL_CALL_RESULT` | external result observed | always `unknown` in v0 | retain result-size bucket; omit content |
| `STATE_SNAPSHOT` | state observation | `unknown` | count keys/bytes; omit snapshot |
| `STATE_DELTA` | state observation | `unknown` | count operations/bytes; omit patch values and paths |
| `MESSAGES_SNAPSHOT` | content-bearing observation | omitted | count messages only |
| `ACTIVITY_SNAPSHOT` / `ACTIVITY_DELTA` | activity observation | `unknown` | counts only; no activity body |
| text/reasoning/thinking events | content-bearing observation | omitted | count chunks/bytes only |
| `CUSTOM` / `RAW` | unknown extension | omitted | event name hash and byte count only |

`TOOL_CALL_RESULT` is not an AB `verified` receipt. In AG-UI 0.0.57 it carries string content but no
normative success/failure field. Parsing the content to infer failure would violate the content
minimization boundary. Verification requires an adapter-owned postcondition/readback tied to the
intended effect.

## Tool-call state machine

Each hashed tool-call ID has one projection-local state:

```text
absent
  -> started
  -> args_observed*
  -> request_closed
  -> result_observed
```

Violations include:

- args, end, or result before start;
- more than one start for the same call;
- result before end;
- cross-run reuse of a tool-call ID;
- an open tool call at batch end;
- run finish/error while a tool call remains open;
- events after a terminal run event;
- conflicting run/thread IDs.

An incomplete batch is allowed but must set `stream_complete=false`. It may not emit
`all_actions_traceable=true`.

## SSB projection shape

When a lifecycle or tool event is projected, it uses the existing Semantic System Bus vocabulary:

```json
{
  "source": "ag_ui_readonly",
  "action": "intent_opened",
  "target": "sha256:tool-call-id",
  "object": {
    "object_type": "agent_tool_call",
    "source_adapter": "ag_ui_readonly",
    "label": "safe-normalized-tool-name-or-null",
    "object_id": "sha256:tool-call-id"
  },
  "affordance": {
    "action_type": "tool_call",
    "risk_level": "medium",
    "requires_gate": true,
    "expected_effect": null
  },
  "verdict": {
    "status": "unknown",
    "method": "ag_ui_event_projection_no_effect_readback",
    "evidence": null
  }
}
```

The v0 projector returns these shapes in memory only. It must not call
`StateStore::record_semantic_event`.

## Identity and correlation

- Raw `threadId`, `runId`, `messageId`, `toolCallId`, agent ID, and step names are not returned.
- IDs are domain-separated SHA-256 values such as
  `sha256("ag-ui/v0/tool-call" || 0x00 || raw_id)`.
- Hashes provide correlation inside the supplied batch; they grant no identity, lease, or policy
  authority.
- AG-UI `forwardedProps` is outside v0. It can contain deployment assertions and must not be treated
  as trusted without a separately designed verifier.
- AB's A2A AgentCard remains discovery metadata. It does not authenticate an AG-UI stream.

## Tool-name handling

Tool names can reveal vendors, tenants, or internal operations. The default projection returns only a
hash. A future caller may request a plain normalized name only when all of these hold:

1. the tool came from an AB-owned registry snapshot;
2. the name contains only `[A-Za-z0-9_.:-]` and is at most 128 bytes;
3. the caller explicitly opts in;
4. the output still carries no arguments or results.

Plain names never classify read/write effect by themselves. Unknown MCP tools remain write-like for
admission design, but this read-only projector performs no admission.

## Relationship to AB controls

- `ToolPolicy`: unchanged; the projector neither selects nor exposes tools.
- `skills_route`: may later supply advisory matching metadata, but cannot widen grants.
- `embodiment_lease`: unchanged; hashed IDs are not lease IDs.
- `macos_ax_action_admission`: unchanged; AG-UI intent is not AX admission.
- `SemanticEvent`: reused as vocabulary, not persisted in v0.
- A2A AgentCard: complementary discovery surface, not an AG-UI transport or trust proof.
- `WorkspaceRuntimeContract`: may describe a future adapter, but cannot claim computer isolation.

## Falsifiers and tests for P1

P1 implementation is not admissible unless pure unit tests prove:

1. a `TOOL_CALL_END` never yields `verified`;
2. a successful-looking `TOOL_CALL_RESULT` never yields `verified` without readback;
3. raw message, reasoning, arguments, result, snapshot, delta values, secrets, URLs, and paths do not
   appear in serialized output;
4. out-of-order and cross-run tool events are reported as violations;
5. unknown event types are omitted and counted;
6. request and per-field budgets fail closed;
7. the same input yields byte-identical canonical JSON;
8. no store write, network request, process spawn, browser action, mobile action, body lease, or policy
   change occurs;
9. protocol versions other than `0.0.57` are rejected;
10. incomplete input never claims stream completeness or global traceability.

Recommended fixtures:

- one complete text-only run;
- one complete tool-call run with chunked args and a result;
- one explicit run error;
- one interrupted run;
- one truncated stream;
- one reordered/cross-run adversarial stream;
- one content-leak corpus containing credential-, URL-, path-, and prompt-shaped canaries.

## P1 implementation boundary

The first candidate should be a pure Rust module, for example
`crates/bridge/src/ag_ui_readonly_projection.rs`, with no registration in `mcp_tools.rs`. A later
independent review may admit a read-only MCP wrapper only after the pure tests and leak corpus pass.

Not part of P1:

- outbound AG-UI client/server transport;
- OpenBot or CopilotKit dependencies;
- action policy evaluation;
- tool execution or result forwarding;
- human takeover mutation;
- per-agent container provisioning;
- durable semantic-event persistence;
- default tool-profile changes;
- deployment.

## Gate

Current verdict: `DESIGN_READY_FOR_INDEPENDENT_REVIEW`.

The next gate is review of mapping fidelity, content minimization, ordering rules, and the assertion
that no AG-UI lifecycle event can be laundered into a verified real-world outcome.
