# Embodied media episode dogfood gate

This lane asks one product question: does the narrow
`advance_track_then_project` episode reduce owner restatement, manual
intervention, or agent orchestration burden across repeated real tasks without
repeating media actuation or weakening its evidence boundary?

It does not add a tool, action, router, background service, or automatic policy
change. The scorecard is a local read-only evaluator over manually assembled,
metadata-only records.

## Pre-registered gate

Collect three paired real tasks. Each pair records a directly observed baseline
and the bounded episode using only non-negative counts for owner restatements,
manual interventions, agent orchestration calls, failed/replanned calls, and
elapsed milliseconds. The lane is ready for
owner review only when:

- all three tasks pass the durable action, bounded settlement, exact Android
  draw, and cleanup contract;
- none reports a repeated external execution, operation-ID replacement,
  implicit UI fallback, background authority, arbitrary mobile control, or
  retained sensitive content; and
- at least two of the three pairs reduce owner restatements, manual
  interventions, agent orchestration calls, or failed/replanned calls, with no
  measured burden regressing.

The three-pair gate is code-locked. Do not append later routine successes to
dilute a negative result. Any paired task with more restatements or manual
interventions, orchestration calls, or failed/replanned calls freezes the lane
even if the other two improve. Elapsed time is reported descriptively but does
not drive the decision because device and network timing is noisy.

Even then, the output is only `READY_FOR_OWNER_REVIEW`.
`runtime_influence_allowed` remains false. Tool routing, profile membership,
automatic action, and background monitoring require a separate owner-approved
change with rollback evidence.

The aggregate may report repeated paired workflow-burden reduction, but it
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
`agent_orchestration_calls` counts the agent-visible calls needed to complete
the episode; nested calls inside the composite remain implementation detail and
are not added to this number. `failed_or_replanned_calls` counts non-proceed
calls that required another agent decision.

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

Pair 01 was preregistered before actuation at
`docs/design/evidence/embodied_media_episode_dogfood_pair_01_preregistration_2026_08_20.json`.
It compares the seven agent-visible calls of manual bounded recovery/projection
orchestration with two calls using the composite. Operation IDs, ADB serial,
and bind address are represented only by SHA-256 in that artifact.

Pair 01 was aborted and is not enrolled in the three-pair denominator. Its
mandatory failure record is
`docs/design/evidence/embodied_media_episode_dogfood_pair_01_aborted_2026_08_20.json`.
The durable backend reported one dispatch and later settled recovery without a
second dispatch, but the MCP wrapper rejected the recovered receipt after the
media mutation. The connector also used the unsafe default journal instead of
the configured secure journal. This exposed a wrapper/runtime version-pairing
gap, not a failed track-settlement predicate. New live collection remains
blocked until the action-before-version handshake is merged and deployed and a
fresh MCP process proves the secure journal environment before actuation.

Pair 02 was preregistered only after that admission gate passed at
`docs/design/evidence/embodied_media_episode_dogfood_pair_02_preregistration_2026_08_20.json`.
It uses fresh opaque operation identities and retains the same seven-call
baseline versus two-call trial measurement, so the protocol repair does not
retroactively change the comparison.

Pair 02 was also aborted and is not enrolled. Its failure record is
`docs/design/evidence/embodied_media_episode_dogfood_pair_02_aborted_2026_08_20.json`.
The repaired wrapper/runtime handshake, secure journal, settled recovery,
authenticated connection, and media sync all passed. The temporary collector
then read `/media_context/track/id`, while the versioned sync receipt exposes
`/media_context/track_id`; it stopped and cleaned up before exact draw, and the
trial was never started. No further live pair may run until receipt extraction
and cleanup are implemented as a versioned, unit-tested collector rather than
an inline acceptance script.

## Versioned collector gate

`scripts/embodied-media-episode-dogfood-collector.py` is the read-only gate for
future enrollment. It accepts a private bundle of raw tool payloads, requires
the exact seven-call baseline or two-call trial sequence, and emits only a
closed, content-free `agent_bridge.embodied_media_episode_collector_result.v0`
record. It does not start MCP, call the player, open ADB, or persist the input.

The validator fixes the sync binding at `/media_context/track_id`, requires the
same settled track in the action and projection, requires an exact revision and
frame-digest draw report, and requires verified cleanup. Served-only frames,
later revisions, recovery payloads containing a dispatch field, repeated
execution, type confusion, extra top-level input fields, and the obsolete
nested track path are rejected. Its normalized output hashes track identities
and omits operation IDs, device identifiers, sessions, titles, and artists.

The collector must be imported by any future live runner; duplicating these
JSON paths in an inline script is no longer admissible. Pair 03 may be
preregistered only after the runner itself is tested for stop-on-error cleanup
and uses this collector for its final decision.

## Bounded runner gate

`scripts/embodied-media-episode-dogfood-runner.py` implements that orchestration
boundary without adding an MCP tool. It validates every public binding before
starting MCP, writes raw tool payloads only into a caller-selected new 0700
directory as exclusive 0600 files, and delegates the sole success decision to
the versioned collector above. Standard output contains only the collector's
normalized result or a content-free rejection code.

The baseline path is fixed to seven calls and the trial path to two calls. A
baseline failure after projection start first attempts the allowlisted stop
tool; a lost start response or failed stop falls back to the exact no-shell ADB
`am force-stop` command for the pinned Companion package. A trial receipt whose
composite cleanup is not verified receives the same fallback. Cleanup cannot
turn a rejected or incomplete episode into success.

The runner tests cover sequence cardinality, operation-hash binding, malformed
public inputs before dispatch, exact track/revision/digest collection, sink
failure, lost start response, stop failure, trial cleanup failure, exclusive
receipt creation, and fixed fallback argv. These tests authorize a later Pair
03 preregistration; they do not themselves preregister it or authorize a media
action. A live pair still requires a fresh preregistration record and a new MCP
process on the deployed, version-paired runtime.
