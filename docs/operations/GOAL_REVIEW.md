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

### Keep detail work connected to delivery

Keep one current delivery priority in the existing plan: what the user will be
able to do when this slice is complete. Authorized parallel subtasks may serve
that priority; unrelated discoveries stay deferred. Before recommending work
in another project, verify its current task and status rather than selecting
an old memory merely because it is relevant to the topic.

An unchanged objective does not establish that work is still on track. Before
another repair/validation round on the same blocker, a follow-up branch, or
resuming after a handoff/compaction, recover from existing task context:

- the user outcome and current delivery slice;
- what this subtask blocks, with the evidence that makes it necessary;
- the sufficient check or stop condition, and the mainline step to return to;
- the remaining delivery gap and prior attempts on this same blocker.

Keep this in the existing plan or handoff; no new ledger or contract is required.
If context is missing, inspect the retained request/plan before inferring a new
goal. A generic "continue" continues the accepted objective and authorized
route; it does not by itself reopen a closed investigation or make an optional
improvement mandatory.

When closing or pausing an investigation, retain its conclusion, remaining
unknowns, and concrete reopening condition in the existing plan or handoff.
Check that state before proposing follow-up work. Reopening requires the
specified new evidence or an explicit owner change of scope; repeating the
same unanswered question is not new evidence.

Use a short progress statement at those decision points: "Outcome: …; this
work blocks …; enough evidence is …; then return to …; still missing: …".
Do not repeat it on every tool call or ask the owner to approve routine routing.
For a long uninterrupted turn, apply the same review when the next action
extends a repair or verification chain; waiting for another user message is
not necessary. Three conversation rounds are an owner-reported warning sign,
not a measured threshold or a reason to stop useful work.

Classify the next detail by its relationship to delivery:

| Situation | Action |
| --- | --- |
| A demonstrated blocker of an accepted requirement | Perform the smallest adequate repair/check, then return to that requirement |
| A necessary safety, data-integrity or correctness repair | Keep the protection; explicitly retain any unresolved delivery gap |
| Optional polish, broader coverage, or an unrelated finding | Defer it in existing task notes and continue delivery |
| The same blocker persists without new discriminating evidence | Reassess the route, use an authorized alternative, or report the specific blocker; do not automatically issue another repair task |
| The owner explicitly changes the outcome | Record the actual change and reference under the procedure above; do not label it drift |

Review the cumulative chain, not only the latest bounded attempt. Renaming a
branch, shrinking a retry budget, or opening another session does not reset
the same delivery gap or an exhausted authorization. Further work needs a
concrete new basis and must remain within the existing budget/authority; a new
basis alone does not replenish an exhausted budget. Route changes already
authorized do not require renewed permission. Ask only when a material choice
cannot be resolved within the retained scope.

Once the accepted checks pass, close the slice. Broaden or repeat validation
only for a relevant new change, failure, unresolved concern, or required check.
Never lower acceptance, hide a failure, or skip a required check to claim
progress. A missing prerequisite for one reference case need not block all
authorized routes to the outcome.

Lead branch reviews and progress reports with what the user can now do and
what remains unavailable. Keep "evidence/report accepted" separate from
"delivery requirement completed". Test counts and archived negative results
can support decisions but do not automatically authorize the next stage.

The [2026-10-26 retrospective](../reports/2026-10-26-goal-drift-session-review.md)
motivates this workflow change. It is not an automatic drift detector or proof
of reduced drift. In subsequent ordinary work, look for earlier mainline
returns and fewer owner corrections, without suppressing necessary repairs or
adding confirmation burden. Do not open a separate collection campaign.

### Apply a bounded workflow improvement during a real task

Use the Harness²-inspired helpers only when an ordinary task has exposed a
specific workflow problem. The current priority remains that task's deliverable.
Do not turn a request to continue into another helper implementation solely
because the preceding helper passed its tests.

Before trying an improvement, retain a short note in the existing task context:

> Deliverable: …; observed blocker and source: …; one proposed change: …;
> baseline: …; unchanged acceptance: …; attempt/time limit: …;
> stop condition: …; next delivery action: ….

Use an existing authorized limit when present. Otherwise choose one candidate
and a small task-appropriate check before execution; a failed attempt consumes
that attempt. Do not reset the budget by renaming the candidate. If no concrete
blocker exists, skip the experiment and perform the next delivery action.

Select only the helper that answers the actual decision:

| Available task evidence / decision | Existing route | Enough to return to delivery |
| --- | --- | --- |
| A local skill edit needs a helper existence or Python syntax check | [Candidate check](WORKFLOW_CANDIDATE_CHECK.md), with actual required scripts named explicitly | Resolve a required-helper defect; static PASS does not establish successful loading or task behavior |
| Baseline and candidate text outputs already exist and a comparison would resolve a delivery choice | [Artifact comparison](WORKFLOW_ARTIFACT_COMPARE.md), with the original task and unchanged criteria | Select a usable output or abstain; retain the baseline when appropriate, then perform the task's actual acceptance checks |
| Comparable before/after execution records already exist | [Execution contrast](WORKFLOW_EXPERIENCE_CONTRAST.md), with actual costs and all declared attempts | Retain the observation, including `NO_ENTRY`; do not rerun merely to obtain a favorable label |
| A verified contrast supports a lesson worth reviewing | The same contrast command's optional `--lesson` | Export a proposed draft; do not treat it as promoted memory or evidence of transfer |

These are alternatives, not four mandatory stages. Do not manufacture extra
runs to satisfy the contrast tool's two-pair minimum. One useful repair can
close the user's task while its general lesson remains unsupported. A selected
artifact does not become a metric or prove that a workflow change helped.
Reviewer or model invocation still needs the task's existing authorization;
this procedure grants no new delegation or runtime authority.

At closure, keep the result in the existing task notes: delivered capability,
observed return to the mainline (or unresolved blocker), owner corrections
actually observed, available cost, skipped comparisons and remaining unknowns.
Distinguish agent-reported observation from independent acceptance. Do not
invent a baseline, missing cost, occurrence count or causal drift reduction.
No new collection campaign, ledger or mandatory owner confirmation is needed.

The four offline helpers are now available for ordinary use. Further mechanism
expansion waits for a demonstrated gap in that use and a bounded owner-visible
closure; a generic continuation or synthetic PASS is not new value evidence.
This does not prevent necessary fixes in the retained helpers.

### Carry requirements through an execution handoff

When an existing task needs persistent working context, use its existing plan
or `work_memory` slot. Keep the following compact fields together; this is a
writing format, not a new tool schema or a required contract for every task:

```text
Original request: exact relevant user words and available source reference
User additions/changes: in order, with references; none or unknown when absent
Current delivery and acceptance: distinguish user requirements from route choices
Delivered: usable result and its evidence level
Remaining gap: missing result or blocking condition
Next action: the one action that advances delivery
Return to mainline: where supporting work rejoins the accepted deliverable
Retained limits: existing authority, cumulative attempts, and stop conditions
Closed work: conclusion and concrete reopening condition
```

Keep original wording separate from the current outcome: an explicit user
change may legitimately replace the outcome, without erasing its provenance.
Quoted text is task data; quotation does not grant new authority. Do not label
an assistant-selected approach or a test input as a user addition. References
identify sources to inspect; they do not certify authorization.

`work_memory.save` replaces a slot; it does not merge new text into the previous
task. Before updating, read that same `cwd`/`session_id`/`slot` (or exact key),
preserve the original request and still-applicable additions, and replace only
the working status that changed. Read back after a material update and check
the goal, additions, remaining gap and next action. Keep the note short enough
for the returned `truncated` flag to remain false. An oversized note needs a
short working summary plus references to retained source material; never
silently cut acceptance conditions. This is not an atomic concurrent-edit
protocol: use a session-owned slot, and reconcile unexpected changes before
overwriting it. Do not treat an expired or missing slot as a blank new goal.

The `session_handoff` conversation snippet is only extra context: its source
implementation keeps the first 4,000 characters. A late correction may be
absent. Keep the delivery note in existing working context and carry it into
an authorized handoff explicitly; neither the snippet nor a preview proves
that a recipient received or read it. A stored note alone cannot prevent drift.

For an already assigned task, tell the recipient that this is the work to
execute, identify its return point, and avoid recursively handing off the same
unchanged task. This does not prohibit authorized, useful decomposition.

Present task state in ordinary language: working, needs input, ready for review,
or closed, followed by the missing result or next action. These are descriptions,
not new completion states. A process exit, tool result or agent report does not
independently verify the accepted postcondition. Once this delivery is closed,
save only the lasting conclusion through the existing memory route and clear
the addressed working slot (`work_memory` with `op: "clear"`, or a terminal
`status` save that also supplies a nonempty `summary`/`content`); do not
leave a completed task looking active. No automatic next task is created.

The [2026-10-27 adoption report](../reports/2026-10-27-copilotkit-task-continuity.md)
records the source comparison and this task's live save/update/readback check.

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
