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
omitting the field or sending `false` omits the advisory attachment. Non-boolean
values, including `null`, return an input error. The default goal summary described
below is independent of this opt-in attachment.

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

## Visible goals and optional change comparison

Every MCP preview now includes `goal_summary`: the submitted objective,
acceptance criteria, authority boundary, reserved actions, continuity locks,
allowed changes, and a readable `display` string. It also labels the contract
identity, revision, preview status, and caller-supplied provenance. A blocked
contract remains inspectable, with its original violations and empty
`compiled_instruction`. The original pure compiler is unchanged.

The extra summary is an additive response field. Existing callers can keep
reading the original fields; omitted/false `include_next_step_review` still
behave identically to each other. This is an MCP response, not an always-visible
desktop panel or an automatic invocation for every task.

Supply an optional top-level `previous_contract` with the same v0 shape to add
`goal_change_review`. The baseline is supplied by the caller; the tool does not
retrieve or save an approved snapshot. It reports exact before/after values for
objective, acceptance criteria, and the four boundary fields, separately from
path, attempt, and observed-state changes. List comparison ignores order,
duplicates, and surrounding whitespace. It does not infer semantic equivalence,
intent, or drift from wording changes.

An optional `change_context` array attaches explanations to specific changed
fields. For example, alongside complete current and previous contracts:

```json
{
  "change_context": [
    {
      "field": "acceptance_criteria",
      "reason": "The user added keyboard navigation to the requested result",
      "user_change_ref": "session:example:user-message:17"
    }
  ]
}
```

The six allowed `field` values are `objective`, `acceptance_criteria`,
`authority_boundary`, `reserved_actions`, `continuity_locks`, and
`allowed_changes`. Each context object rejects unknown fields. Missing or blank
reasons and references stay unknown. Duplicate or unused explanations are
reported rather than selected as authorization. Non-empty context requires a
baseline; malformed optional inputs return an input error. Different contract
identities or an invalid baseline are not treated as a comparable history.

The review never grants authority, checks user-reference contents, changes the
original validation result, or creates an approval requirement. A changed field
with a non-advanced revision is reported for review, not used as a runtime gate.
Use existing user authorization and investigate an uncertain material change;
do not treat route adjustments as automatic reasons to ask again.

See [the operating examples](../operations/GOAL_REVIEW.md). No Store schema,
plan-completion mode, trusted evidence producer, or runtime enablement changes
are part of this interface.
