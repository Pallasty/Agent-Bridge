# Visible goals during ordinary work

At task start, briefly state the intended outcome and meaningful acceptance
conditions. Reuse the user's request and already-retained task context. Do not
ask the user to reconfirm accepted requirements or require a new contract for
every small task.

When a task already uses `agent_task_contract_preview`, its default
`goal_summary.display` makes the submitted objective, acceptance criteria, and
boundaries readable. Show the relevant content in the working conversation;
do not assume a client automatically renders or pins an MCP response. The
summary reflects caller-supplied input, not independently verified user intent.

For example, this task's user-facing summary is:

> Outcome: make existing AB contract goals and changes readable.
> Acceptance: show the submitted outcome, criteria, and boundaries; report
> concrete goal changes with their reason and available user reference;
> preserve existing authority and completion rules.
> Scope: reuse the current contract entry. PI installation and integration
> remain a separate conditional possibility.

## Explain changes where they occur

Provide the earlier contract as `previous_contract` when comparing revisions.
Add `change_context` only for the changed goal or boundary fields whose reasons
and user references are available. Keep the earlier version intact in the
existing task context; this read-only tool does not store it for you.

For a newly requested acceptance condition, show:

> Acceptance changed: mouse navigation → mouse and keyboard navigation.
> Reason: the user added keyboard navigation in message 17.

The tool returns before/after values and caller-supplied explanation. It does
not read message 17, certify that it authorizes the change, or verify that the
result was delivered. If the reference or reason is missing, keep it unknown
and state the specific discrepancy. Avoid relabeling an assistant suggestion
as a user request.

For a route change with the same goal and boundaries, a short explanation is
enough: "The existing test helper already covers this behavior, so I will use
it for the accepted check." Continue within existing authorization. A list
reordering, retry count, or revision number alone is not a semantic goal change.
Do not repeat the complete unchanged goal after each tool call.

## Read the result accurately

### Carry requirements through an execution handoff

The preview and `agent_spawn` are separate interfaces. `agent_spawn` accepts a
prompt and runtime options; it does not accept a task contract or automatically
attach `compiled_instruction`. A ready preview therefore does not establish
that a child received the contract, followed it, or delivered its criteria.

When an already-authorized task needs a handoff, carry its existing objective,
acceptance criteria, and boundaries into the prompt. Retain the contract ID and
revision in the existing task context when available; do not create a contract
solely for a small handoff. Identify assistant-selected implementation choices
as such, separately from user requirements. Keep the available user reference;
missing provenance stays unknown. This does not require another approval.

For example: "Requirement: preserve keyboard navigation (user message 17).
Implementation choice: reuse the existing event handler (assistant choice).
Acceptance: the existing keyboard navigation check passes." Changing the
handler is a route choice; dropping keyboard navigation changes acceptance.

For runtime settings that matter to acceptance, distinguish the requested
setting from the returned or observed setting. An omitted model delegates
selection to the backend/configuration; it is not evidence of a particular
model. `runtime_id` identifies the backend, not the provider's actual model.
The spawn response reports a fallback when a backup runtime is used. Record a
relevant fallback in existing task context instead of silently treating it as
the originally intended backend. Do not copy credentials or full environment
variables into that context.

At completion, check the actual output against the retained criteria and name
any skipped or substituted requirement. Session termination, exit code, and
resource receipts do not independently establish semantic task completion.
Use the existing outcome provenance fields where that workflow already applies;
do not promote an agent report to independent verification or reopen a frozen
completion gate. These handoff practices provide visibility, not automatic
contract-to-process binding or a demonstrated reduction in goal drift.

### Interpret preview fields

- `goal_summary` is present for both ready and blocked submitted contracts.
- `goal_change_review` is present only when a baseline was supplied.
- A different contract identity or invalid baseline does not establish history.
- A reported delta is a field comparison, not a drift verdict or user approval.
- `status`, `violations`, `compiled_instruction`, and `safety` keep their existing
  meaning. A comparison cannot clear a blocked contract.
- Goal visibility does not turn an agent-reported completion into independent
  evidence. Verify the actual accepted postcondition through the available
  task-specific checks.

The source and interface checks establish callable behavior, not a measured
reduction in drift. During ordinary use, relevant evidence is whether an actual
unrequested change became visible earlier, owner restatement decreased, or
unnecessary confirmation increased. Do not create a collection service or a
new approval gate to obtain those observations.
