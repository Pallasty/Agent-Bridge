# Optional SPEC-inspired next-step review

The opt-in source implementation and compatibility tests are complete. The fixed
replay found no incremental improvement: baseline and advisory each scored 9/9
effective next actions under both judges. Keep the option off by default; this
increment does not establish reduced goal drift in ordinary use.

## Problem and bounded change

The owner reported gradual goal drift: assistant-proposed supporting work and
small, unnoticed changes can accumulate while each individual step appears
reasonable. The preceding local session audit retained seven illustrative task
chains. They establish examples, not an occurrence rate or measured user time
lost. A separate six-case handoff-format pilot did not improve the next action.

The owner authorized a bounded implementation after discussing SPEC's separation
of outcomes, requirements, and tasks. This increment adds one optional advisory
to the existing `agent_task_contract_preview` MCP adapter. It asks the receiving
assistant to connect the next action to existing acceptance, explain supporting
work's present necessity, and honor explicit goal changes and existing authority.
It also discourages replacing an available useful action with another preparation
document or changing requirements merely to justify new tasks.

Leaving the existing behavior unchanged would preserve the task preview's
structural checks but provide no explicit next-action review. The narrow usable
closure here is an opt-in response instruction plus a bounded historical replay.
There is no new tool, stored goal, completion gate, automatic call site, or
background process. No additional implementation increment follows automatically.

## Interface and compatibility

Call `agent_task_contract_preview` with the existing `contract` and the top-level
boolean `include_next_step_review: true`. Only a `ready` preview adds
`next_step_review_instruction`. Omitted or false preserves the original response;
non-booleans return an input error; blocked previews do not attach the instruction.

The contract schema, pure compiler, existing fields, and authority semantics
are unchanged. Callers must read the optional field and supply the original task
context for the advisory to matter. The instruction does not retrieve or verify
user intent and cannot prove completion or value. See the
[interface guide](../../design/AGENT_TASK_CONTRACT_PREVIEW_V0.md#optional-next-step-review)
and [exact source text](../../../crates/bridge/src/agent_task_contract_next_step_review.md).

The instruction contains 165 English words. SHA-256:
`9afae097c872525829fa623a0a7afc86a6b1082a6cc6885b9dfe8b6fe3432f15`.

## Validation

Five focused MCP tests passed with
`cargo test -p ab-bridge --no-default-features --lib agent_task_contract_preview -- --test-threads=1`.
They cover the original preview, omitted/false output equivalence, exact additive
true output, blocked behavior, invalid boolean types, and non-execution of supplied
write intent. An independent source review found no blocking compatibility issue.
No CI or deployment was performed. The connected MCP runtime is unchanged.

## Bounded replay

Three task sessions were held out from the previous replay: R9 durable workload
receipts, R10 plan completion evidence, and the external controller's explicit
return to a Mac research prototype. These are not unseen research samples: the
researchers had already read their histories in the earlier audit.

Both arms share all 24 pre-cutoff visible source records and the same task
contract. Contracts are researcher reconstructions from those records, not
previously stored user-approved specifications. Their read-only boundary applies
only to offline recommendations and does not revoke historical authorization.
The existing MCP generated each baseline preview. Treatment was constructed by
adding the exact source advisory according to the tested adapter output contract;
the experiment did not run an upgraded installed MCP.

The protocol, inputs, rubric, scripts, and hashes were frozen before outputs:
three cases × two arms × three independent cold calls, with `gpt-6-astra` at medium
effort. No tools, repository context, retained memory, or parent session were
available. Outputs are next-action proposals only. Anonymous outputs are judged
against a fixed rubric by a cold model judge and a separate collaborator.

All 18 calls succeeded on their first attempt in distinct ephemeral threads, with
zero tool events. Both judges agreed on all four scoring fields for all 18 answers.
An effective proposal must satisfy the current goal, provide a concrete useful
next step, and introduce neither unnecessary interruption nor supporting expansion.

| Historical decision point | Baseline effective | Advisory effective |
| --- | ---: | ---: |
| R9: source ready, deployment prerequisites unresolved | 3/3 | 3/3 |
| R10: owner authorized a minimal completion evidence gate | 3/3 | 3/3 |
| Controller: owner approved returning to the Mac prototype | 3/3 | 3/3 |
| Total, under each judge | 9/9 | 9/9 |

All proposals honored existing authorization. No proposal requested user input;
neither judge found unnecessary support expansion. R9 proposals checked the known
publishing prerequisite, while Controller proposals continued the authorized
prototype. R10 advisory proposals combined chain inspection with implementation;
baseline proposals inspected the existing receipt chain and produced concrete
integration findings. That inspection addresses a real unknown, so phrasing the
next step as implementation did not justify a higher score.

The task calls reported 262,350 input tokens (17,664 cached) and 3,939 output tokens
over 190.404 seconds wall time. Three primary grading calls reported 49,253 input
and 1,346 output tokens. These counts exclude the coordinating session, collaborator
grading, source review, preparation, and compilation; they are not a total cost.

The baseline already contains curated, explicit acceptance criteria. This
comparison isolates the added instruction's benefit on that basis; it does not
test the full benefit of constructing a contract over an ordinary chat transcript.
Researcher summaries already call out unknowns, including the unverified R10
receipt-to-step chain; that curation may itself make the baseline easier. The
same visible prompts and CLI settings were reused, but reported input counts
varied by up to 782 tokens among identical-prompt calls. Full provider/system
inputs were not captured, so identical hidden context cannot be established.
Three purposefully selected tasks and short proposals cannot establish reduced
long-term drift, fewer user corrections, or time saved. Historical assistant test
claims were treated as reports, not independently verified outcomes.

Private evidence, frozen protocol, exact prompts, run outputs, and grading records
remain outside the repository in
`/Data/CascadeProjects/.analysis-reports/spec-action-check-20260909/`.

## Disposition

Source complete, default off, not deployed. This result does not support enabling
the advisory globally or adding another correction mechanism. The existing
structural preview remains the default. Any later natural use can be assessed
through the ordinary task's outcome; this increment creates no evidence-collection
queue and does not reopen R9, R10, Controller, or other frozen product lanes.
