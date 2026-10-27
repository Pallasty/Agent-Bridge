# CopilotKit research and task-continuity adoption — 2026-10-27

## Problem, authorization and bounded design

The owner reported repeated goal drift into detail work and now explicitly
requested: retain the four-project research in AB memory/board, then perform
research planning, design and validated implementation based on the advice.
The earlier [session retrospective](2026-10-26-goal-drift-session-review.md)
contains concrete examples. A 30-day occurrence count and time cost remain
unknown; this increment does not claim reduced drift.

The selected delivery is a reusable working-context format through existing
`work_memory` and goal-review instructions. No new task store, state machine,
model, service or approval layer is needed. The user can retain the original
request and corrections together with the current deliverable, gap and next
action, without requiring a new contract or restatement.

Source inspection found two relevant existing behaviors: `work_memory.save`
overwrites its slot, and `session_handoff::build_handoff_brief` clips the supplied
conversation to the first 4,000 characters. Neither behavior alone preserves
late corrections alongside the original goal. The procedure therefore reads
before replacing a session-owned slot, keeps the original request and ordered
additions separately, and checks the resulting note. It does not add automatic
merging or claim concurrent-update safety.

Acceptance: archive the research first; make the format reachable from the
existing goal-review entry; use this task's real request for a live save/update/
readback; retain unchanged request text; report evidence limits; close the
working slot at delivery. Once those checks pass, stop this increment.

## Fixed sources and reuse decision

| Project | Commit | Selected observation |
| --- | --- | --- |
| OpenMuse | `a4944f4c471d3dc93b8bfc060b5da309b5216ab2` | Task progress, input and artifacts are presented together; uncertain external actions restrict retry |
| OpenDuet | `5b0e15f9719db0628c02a3fe6386dcad683c8302` | Task framing preserves requests/corrections and says not to recursively start the same task |
| OpenDots | `8091324942b86789ed0da7facbee855145d933b0` | Page/conversation binding and separate voice/compute paths; retained as later interface reference |
| OpenBot | `3592f850eff49204d0f2b46a905d38f2627f2d81` | Governed actions and takeover; responsibility-run success is not independent goal acceptance |

Primary source entry: `https://github.com/CopilotKit/<project>` at each commit.
The specific OpenDuet reference is `openbot/shared/task-brief.ts`; OpenMuse is
`apps/server/src/engine/service.ts`. No upstream code was copied. OpenDuet
vendors OpenBot; OpenDots reuses pinned OpenBot computer services. MIT repository
licenses do not cover the Intelligence service. No installation, connected
service execution, model call or performance reproduction occurred.

AB already has a version-pinned read-only AG-UI/OpenBot projection. This work
does not expand it, certify compatibility with the new upstream version, or
reopen any frozen background, voice, collection or completion-producer lane.

Research memory: `ab_copilotkit_four_project_review_20261027`; existing design
board thread 115, post 6356. Private source manifest:
`/home/pallasting/.agent-bridge-secure/research/copilotkit-four-20261027/manifest.json`
(22 file bindings). The memory keeps the fuller comparative conclusions and
upstream verification limits.

## Validation and follow-up

The live check uses a session-owned `delivery` slot under
`codex-copilotkit-adoption-20261027`, not another task's shared active slot.
Save the current user's exact request with the chosen delivery, read it back,
then update progress from the retrieved note and confirm the original request
survives. Record actual user additions as absent; do not manufacture one to
claim a natural correction test. At closure, clear the slot and read it again.
Keep the tool responses in the private research directory.

This demonstrates the existing storage path and application of the new
procedure by this agent. It does not demonstrate a fresh model recovering the
goal, process-restart durability, independent user acceptance, reduced owner
effort, or semantic drift prevention. No new automated tests mirror the prose;
validation consists of real tool operations, exact-content comparisons, source
inspection, and documentation/link checks.

Next use is an ordinary handoff or compaction recovery with a genuine task.
Observe whether the agent restores the correct result and returns from detail
work without owner restatement. A new mechanism needs a demonstrated failure
of this route, not a generic continuation or this mechanics check alone.
