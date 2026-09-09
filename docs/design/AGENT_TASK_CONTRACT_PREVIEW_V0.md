# Agent Task Contract Preview v0

`agent_task_contract_preview` is a pure, read-only compiler for reviewing one
bounded agent attempt before any orchestration action is authorized. It turns a
typed contract into either:

- `ready`, with a deterministic `compiled_instruction`; or
- `blocked`, with typed violations and an empty `compiled_instruction`.

The design borrows the useful separation of structured state, validation, and
compiled prompt from Seedance Skill OS, while keeping Agent-Bridge's authority
and evidence boundaries explicit.

## State precedence

The effective state is assembled in this order:

1. `continuity_locks`
2. `planned_state`
3. `observed_state`

Later layers override earlier layers. This makes accepted observed evidence
authoritative over a stale plan. A conflict with a continuity lock blocks the
preview unless the exact state key is present in `allowed_changes` as either
`<key>` or `state.<key>`.

## Fail-closed invariants

The v0 compiler blocks on:

- an unsupported schema version;
- an invalid or exhausted attempt budget;
- overlap between `this_attempt_only` and `reserved_actions`;
- rejected parent evidence;
- authority drift from accepted parent evidence unless
  `authority_boundary` is explicitly allowed to change; or
- an unapproved continuity-lock conflict.

Parent evidence is carried by exact reference, verdict, and authority boundary;
the compiler does not copy or reinterpret the referenced evidence body.
Unknown contract and parent-evidence fields are rejected instead of ignored.
Control characters and backslashes are escaped before text compilation so a
field cannot manufacture a second instruction section.

## Authority nonclaims

The preview always reports these fields explicitly:

- `read_only: true`
- `can_spawn_agent: false`
- `can_write_memory: false`
- `can_mutate_work_memory: false`
- `can_promote_canon: false`
- `can_enable_runtime: false`

The implementation has no `Hub`, store, agent-runtime, process-control, or
daemon-control dependency. A ready preview is review material, not permission
to execute the compiled instruction.

## Minimal input

```json
{
  "contract": {
    "schema_version": "agent_bridge.agent_task_contract.v0",
    "contract_id": "contract:example:001",
    "revision": 1,
    "objective": "Compile one bounded preview",
    "parent_evidence_refs": [],
    "this_attempt_only": ["compile the preview"],
    "reserved_actions": ["spawn an agent"],
    "continuity_locks": {},
    "allowed_changes": [],
    "acceptance_criteria": ["preview is deterministic"],
    "authority_boundary": "read_only",
    "attempt_no": 1,
    "attempt_budget": 3,
    "changed_variable": "contract compiler",
    "planned_state": {},
    "observed_state": {}
  }
}
```

Design discussion: Agent-Bridge forum thread `#142`.

## Optional next-step review

Set the top-level `include_next_step_review` boolean to `true` alongside the
existing `contract` to request an advisory instruction. The default is `false`;
omitting the field or sending `false` preserves the existing response. Non-boolean
values, including `null`, return an input error.

A `ready` response then adds `next_step_review_instruction`, asking the receiving
assistant to connect its next action to existing acceptance criteria, explain
why supporting work is necessary now, and honor the user's latest explicit
changes and existing authorization. Missing facts stay unknown. The assistant
should take an available useful action when the evidence supports it, and state
a specific discrepancy when a material change is uncertain. This does not require
another document or repeated approval.

The [source instruction](../../crates/bridge/src/agent_task_contract_next_step_review.md)
is separate from `compiled_instruction`. Contracts, validation, effective state,
authority, completion rules, and safety fields keep their existing meanings.
A `blocked` response never includes the advisory. The pure compiler and its
other callers do not opt in implicitly.

This is a caller-selected prompt, not a semantic drift detector. The preview
does not retrieve the original request, verify acceptance criteria against user
intent, or run the suggested action. Callers must supply that context and read
the additional response field for the instruction to have any effect. It cannot
establish that a task is complete or useful to the user. An updated MCP process
and refreshed client tool schema are needed before using the new parameter.
