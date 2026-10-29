# Agensh borrowing: bounded handoff digest replay

Status: offline implementation and mechanical replay complete. Model recovery,
owner-cost reduction and goal-drift benefit remain unmeasured. No deployment.

## Goal and authorization

The owner asked: “很好！按照你的思路继续设计/规划并落地建议的下一轮目标。”
This follows the Agensh review proposing a small handoff summary comparison.
The single delivery is an offline companion to existing `task_context`: retain
current findings and closed work, exclude explicitly inapplicable notes, and
preserve the next action and stop condition. This is one bounded spike, not a
new memory store, event router, scheduler or background collection lane.

The real problem is grounded in the [existing session review](2026-10-26-goal-drift-session-review.md):
MemT reopening suggestions, obsolete project recommendations and cumulative
repair chains. That review also supplies counterexamples: authorized changes,
necessary correctness repairs and an incomplete observation window. Frequency,
time lost and causal attribution remain unknown.

Acceptance: preserve supplied context exactly; retain closed-work reopening
conditions; separate foreign/revision-mismatched, superseded and unknown-status
records; reject missing failure reopening conditions, duplicate IDs and
overflow; bind historical excerpts to existing evidence; never turn mechanical
PASS into model recovery or acceptance. Stop after these checks and document
the result. Generic continuation does not open another helper or rollout.

## Source and reuse decision

Agensh revision `b05ca7f61fb53a274bce8175f9349caf8946e62a` separates findings,
failures, claims and patch summaries. The selected principle is to share
applicable known results before repeating exploration. No upstream code copied.

- [Board guide](https://github.com/microsoft/Agensh/blob/b05ca7f61fb53a274bce8175f9349caf8946e62a/board-service/README.md)
- [Notice shim](https://github.com/microsoft/Agensh/blob/b05ca7f61fb53a274bce8175f9349caf8946e62a/mini-router/mcp-notice-shim.cjs)
- [Idle prompt](https://github.com/microsoft/Agensh/blob/b05ca7f61fb53a274bce8175f9349caf8946e62a/prompts/idle.txt)

No idle nudges, forced publication, automatic task expansion or infrastructure
deployment is adopted. `CLOSED` and reopening conditions are AB prototype
additions, not upstream API claims. A `FACT` label does not establish truth.

## Implemented interface

[handoff_work_digest.py](../../scripts/eval/handoff_work_digest.py) uses only
Python's standard library. It reads explicit JSON and emits JSON to stdout.
It executes no evidence commands and accesses no AB database or network.

```sh
PYTHONDONTWRITEBYTECODE=1 python3 scripts/eval/handoff_work_digest.py --packet packet.json
PYTHONDONTWRITEBYTECODE=1 python3 scripts/eval/handoff_work_digest.py --replay scripts/eval/fixtures/handoff_work_digest_cases.json
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -p test_handoff_work_digest.py
```

Packet fields: `task_id`, `revision`, an existing nonempty `task_context` object,
and `records` (at most 32). Each record has `id`, `task_id`, `revision`, `kind`,
`status`, `text`, `source_ref`, `reopen_condition`. Kinds: `OBSERVED`, `FACT`,
`FAIL`, `CLAIM`, `PATCH_SUMMARY`, `CLOSED`. Status: `current`, `superseded`,
`unknown`. Source and reopening condition may be null, except FAIL/CLOSED need
a nonblank reopening condition. If that condition is unknown, retain the
uncertainty in working context rather than inventing one.

Only exact task/revision matches with current status and a source reference
enter `known_results`; exclusions carry IDs and reasons. Input is unchanged.
Labels are caller-supplied: the tool cannot determine semantic relevance,
automatically expire records, authenticate sources, or infer that reopening
conditions occurred. CLAIM is informational, not an exclusive lock or grant.

Default output budget: 16 KiB canonical JSON; excess raises an error rather than
clipping context. CLI input cap: 1 MiB. Pretty-print whitespace adds bytes beyond
the canonical budget. Invalid input exits 2; successful construction exits 0.

The companion preserves `task_context` as opaque data, not a second Rust
validator. The existing [session_handoff interface](../operations/SESSION_HANDOFF_TASK_CONTEXT.md)
must validate it on use. Do not pass companion fields to that strict interface.
An agent may retain the companion beside context in an existing task note after
review; the helper does not save or forward it. Existing work-memory ownership
and readback rules apply. This is optional, not a mandatory handoff step.

## Historical replay and results

The [fixture](../../scripts/eval/fixtures/handoff_work_digest_cases.json) freezes
six scenarios from the October 26 evidence and its SHA-256. Note text must
exactly match the referenced anchor. Task contexts, task/revision labels,
statuses, selected IDs and reopening conditions are author annotations at the
October 28 retrospective cutoff, not original historical handoffs or independent
labels. Missing original requests are explicitly unavailable with null sources.

Baseline: reconstructed context plus all selected historical records.
Candidate: identical context plus selected/excluded records and provenance.
This is not a captured production baseline or a blinded/counterfactual model
trial. The fixed expectations check selection, not semantic decision quality.

| Scenario | Retained anchors | Baseline / candidate bytes |
| --- | --- | --- |
| Closed MemT research | M03; M01/M02 superseded | 1286 / 1272 |
| Current development line | R02/R03; R01 other task | 1307 / 1469 |
| Cumulative repair chain | G02/G05 | 1091 / 1428 |
| Authorized change counterexample | G03 | 879 / 1216 |
| Necessary repair counterexample | G08 | 854 / 1190 |
| Incomplete observation counterexample | S01 | 819 / 1156 |

All six mechanical scenarios passed. Eight unittest methods passed, including
negative controls for changed source hash, altered excerpt, wrong expected
selection and path escape; CLI success/failure; duplicates; exact preservation;
unknown status; missing source; revision mismatch; literal instruction-like
data; and overflow. The initial six tests failed on the absent implementation
before it was written. FAIL behavior is synthetic-test coverage, not demonstrated
failed-route transfer in these historical examples.

Bytes measure UTF-8 sorted JSON with standard separators, not tokens. Five of
six candidates are larger: explicit selection/provenance is delivered, context
savings are not. No model answers generated: `model_recovery=NOT_RUN`,
`goal_recovery_success=null`, `owner_corrections=null`. No causal or natural-use
success rate is reported.

Private replay: `/home/pallasting/agensh-source-review-20261028/handoff-replay.json`.
The command above reproduces it. Changes are confined to the offline script,
tests, fixture and documentation. No rebuild, MCP restart, push, CI, memory
promotion or deployment was performed.

## Closure

Delivered: an executable offline companion and six source-bound mechanical
examples. Not delivered: automatic discovery, semantic summarization, live
injection, fresh-model recovery or reduced drift. Existing runtime unchanged.

Return to ordinary tasks. Further development requires a concrete failure of
this route and measurable task acceptance. Any future model comparison must
freeze equivalent inputs, hide reviewer expectations, capture actual answers
and costs, and retain no-improvement outcomes. This PASS does not start it.
