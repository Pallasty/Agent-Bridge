# AG-UI OpenBot Request Completeness v1 (D6)

- Date: 2026-08-26
- Status: local source candidate; no publication, merge, deployment, or runtime activation
- Agent-Bridge base: `8307c5478a54cfeba27d90161306c925a313bc01`
- External wire pin: `@ag-ui/core@0.0.57`
- OpenBot evidence pin: `CopilotKit/OpenBot@291bae6dc7b79821d10bc2719a22bcc995af613a`
- Existing contract preserved: `agent_bridge.ag_ui_readonly_projection_request.v0` ->
  `agent_bridge.ag_ui_readonly_projection.v0`
- New opt-in contract: `agent_bridge.ag_ui_readonly_projection_request.v1` ->
  `agent_bridge.ag_ui_readonly_projection.v1`

## Decision

Add an explicitly versioned completeness split without changing v0 behavior:

1. `TOOL_CALL_END` closes the tool request structure in v1.
2. A closed request with no `TOOL_CALL_RESULT` has no protocol-order violation in v1.
3. `run_stream_complete` reports whether the run, step, and tool-request structure is terminal,
   ordered, known, and violation-free.
4. `tool_result_observation_complete` reports whether every projected tool request has a result
   event in the supplied batch.
5. `stream_complete` remains the conservative conjunction of those two claims.
6. `TOOL_CALL_RESULT`, when present in the same run, remains only a content-minimized observation.
   It never establishes dispatch, success, or an external effect.
7. Cross-run tool-call events remain rejected. D6 does not infer a result link from
   `parentRunId`, message history, or repeated `toolCallId` values.

The same fieldless, default-off MCP tool dispatches by the explicit request schema. Existing v0
callers receive the unchanged v0 projection and claims shape. A caller must send request v1 to
receive the two new completeness dimensions.

## Why this is the narrow OpenBot-compatible seam

The pinned OpenBot agent emits this tool-request sequence:

```text
RUN_STARTED
TOOL_CALL_START
TOOL_CALL_ARGS
TOOL_CALL_END
RUN_FINISHED
```

It intentionally does not fabricate `TOOL_CALL_RESULT`; the computer gateway decides and performs
the request outside the agent stream. OpenBot's subsequent result can instead re-enter the next
`RunAgentInput.messages` history as a tool message. Therefore requiring a result event before the
origin run can be structurally complete is not compatible with this observed producer behavior.

Pinned primary evidence:

- [OpenBot production agent stream](https://github.com/CopilotKit/OpenBot/blob/291bae6dc7b79821d10bc2719a22bcc995af613a/agent-bot/src/index.ts)
- [OpenBot live connection test](https://github.com/CopilotKit/OpenBot/blob/291bae6dc7b79821d10bc2719a22bcc995af613a/server/tests/agent-connection-live.test.ts)
- [OpenBot history conversion](https://github.com/CopilotKit/OpenBot/blob/291bae6dc7b79821d10bc2719a22bcc995af613a/agent-bot/src/history.ts)
- [AG-UI 0.0.57 event definitions](https://github.com/ag-ui-protocol/ag-ui/blob/54f13419055b4d0f442c71e1efab18b310982ce1/sdks/typescript/packages/core/src/events.ts)

This evidence supports the request/result split only. It does not support accepting an untrusted
cross-run result as belonging to an earlier request.

## Contract matrix

| Request | Projection | `request_closed` at run end | Completeness claims |
| --- | --- | --- | --- |
| request v0 | projection v0 | preserves legacy open-call violations | legacy `stream_complete` only |
| request v1 | projection v1 | request structure is closed; no missing-result violation | `run_stream_complete`, `tool_result_observation_complete`, conservative `stream_complete` |

For the pinned OpenBot sequence, v1 returns:

```json
{
  "violations": [],
  "tool_calls": [{"status": "request_closed", "result_size_bucket": null}],
  "claims": {
    "all_actions_traceable": false,
    "external_effects_verified": false,
    "run_stream_complete": true,
    "tool_result_observation_complete": false,
    "stream_complete": false
  }
}
```

For a same-run result sequence, all three completeness booleans can be true, but the tool-call
verdict still remains `unknown` and `external_effects_verified` remains false.

## State boundary

The v1 structural states are:

```text
absent
  -> started                  request structure open
  -> args_observed*           request structure open
  -> request_closed           request structure closed; result not observed
  -> result_observed          result event observed; external effect still unknown
```

`Started` and `ArgsObserved` still cause `run_terminal_with_open_tool_call` and
`open_tool_call_at_batch_end`. `RequestClosed` does not cause those violations in v1. A result before
end, duplicate result, unknown call, cross-run start/args/end/result, open step, unknown event type,
or conflicting run/thread identity still prevents `run_stream_complete`.

AG-UI 0.0.57 permits event objects to carry future fields, and its verifier resets active tool calls
for each run. Agent-Bridge deliberately remains stricter by correlating tool-call IDs across the
whole supplied batch and rejecting cross-run reuse. This is an AB diagnostic policy, not a protocol
guarantee.

The omission counters cover fields explicitly handled by the pinned projector plus `rawEvent`; they
are not an attestation that every byte in protocol-permitted future metadata was classified. Future
event fields are never echoed, but their bytes may not appear in the omission counters. Any need for
exhaustive unknown-field accounting is a separate contract revision.

## Authority and privacy invariants

Both versions keep all of these fixed:

- `read_only=true`;
- `executes_actions=false`;
- `writes_store=false`;
- `changes_policy=false`;
- `all_actions_traceable=false`;
- `external_effects_verified=false`;
- every tool verdict is `unknown`;
- no raw message, argument, result, future metadata, credential, URL, or path is returned;
- the wrapper owns no transport, `Hub`, store, process, browser, mobile, lease, or policy handle;
- default and ordinary toolsets do not expose the tool.

## D6 acceptance tests

- exact pinned OpenBot request-only sequence: zero violations, structural run complete, result
  observation incomplete, conservative aggregate incomplete;
- v0 replay of that sequence: legacy violations and output shape unchanged;
- v1 complete same-run result: both dimensions and aggregate complete, no verified claim;
- v1 request still open at terminal: existing open-call violations preserved;
- v1 direct-child result attempt: rejected as cross-run reuse with no normal result transition;
- raw argument/result/future-field canaries absent from success output;
- wrapper result equals the pure projector for every fixed v0/v1 fixture;
- exhaustive and mixed-sequence fail-closed corpora remain green;
- formatting, focused tests, compile check, and independent security review pass before a local
  candidate commit.

## Gate boundary

D6 admits only a local source candidate. Remote publication, merge, deployment, MCP reconnection,
runtime tool-list verification, OpenBot network transport, result-history ingestion, cross-run result
linking, action dispatch, and effect verification are separate gates.
