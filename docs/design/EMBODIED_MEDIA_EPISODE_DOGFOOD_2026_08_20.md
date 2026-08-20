# Embodied media episode dogfood gate

This lane asks one product question: does the narrow
`advance_track_then_project` episode reduce owner restatement or manual
intervention across repeated real tasks without repeating media actuation or
weakening its evidence boundary?

It does not add a tool, action, router, background service, or automatic policy
change. The scorecard is a local read-only evaluator over manually assembled,
metadata-only records.

## Pre-registered gate

Collect three paired real tasks. Each pair records a directly observed baseline
and the bounded episode using only non-negative counts. The lane is ready for
owner review only when:

- all three tasks pass the durable action, bounded settlement, exact Android
  draw, and cleanup contract;
- none reports a repeated external execution, operation-ID replacement,
  implicit UI fallback, background authority, arbitrary mobile control, or
  retained sensitive content; and
- at least two of the three pairs reduce owner restatements or manual
  interventions, with neither measure regressing.

The three-pair gate is code-locked. Do not append later routine successes to
dilute a negative result. Any paired task with more restatements or manual
interventions freezes the lane even if the other two improve.

Even then, the output is only `READY_FOR_OWNER_REVIEW`.
`runtime_influence_allowed` remains false. Tool routing, profile membership,
automatic action, and background monitoring require a separate owner-approved
change with rollback evidence.

The aggregate may report repeated paired operator-burden reduction, but it
keeps `behavior_lift_proven=false`: three observational pairs do not establish
exclusive causation. Owner review decides whether a stronger baseline or
held-out comparison is worth running.

## Privacy and evidence boundary

The record schema is closed. It accepts only opaque trial IDs, enums, booleans,
counts, and full SHA/Git references. It has no fields for prompts, transcripts,
track titles, artists, device identifiers, operation IDs, paths, or notes.
`real_task` and `operator_attested_real_task` are explicit operator claims, not
technical provenance. They prevent accidental synthetic enrollment but do not
prove how the task originated.

The first fixture is the already completed settled-recovery live acceptance.
It is admitted as a verified episode, but its paired baseline and operator
burden were not measured. Its result is therefore
`PASS_EPISODE_COLLECT_PAIRED_BASELINE`, not behavior lift.
Here `preregistered` refers to the live run's exact pending/recovery/draw
sequence being specified before actuation; it does not claim that this later
scorecard existed before the run.

For future pairs, `owner_restatements` counts repetitions of the original
intent after the initial request. `manual_interventions` counts any additional
owner action needed to complete or recover the episode, including explicit
phone confirmation when the trial requires it. Neither count may be silently
excluded because the intervention was expected.

The scorecard never upgrades the source evidence. In particular, it does not
claim a global dispatch count, independent playerctl delivery, exclusive
causation, long-lived track stability, human observation, or pixel
verification.

## Run

```bash
python3 scripts/embodied-media-episode-dogfood-scorecard.py \
  docs/design/fixtures/embodied-media-episode-dogfood-settled-recovery-2026-08-20.json
```

Add future preregistered records as additional positional arguments. Do not
fabricate paired baselines after an episode has run. A missing baseline remains
explicitly unavailable and does not count toward the three-task gate.
