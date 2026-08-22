# Sparse voice natural-observation checkpoint — 2026-08-22

## Outcome

The persistent Avatar and sparse-voice observer survived the Codex restart.
The first bounded runtime sample contains one policy-silent decision and one
successful playback handoff. There is no evidence of repeated speech. The
sample is intentionally classified as `collecting`, not as proof of long-term
delivery health.

## Evidence boundary

- MCP doctor returned healthy with zero non-OK checks after restart.
- The native renderer, voice supervisor, and voice observer remained running;
  the renderer-state endpoint was reachable.
- The private receipt log was mode `0600` and contained two v1 records: one
  `silent/mode_not_allowed` and one `played_unverified/speak`.
- Receipt fields contained no spoken text, LAN address, socket path, model
  path, or credentials.
- `played_unverified` proves a successful adapter playback handoff only. It
  does not prove physical audibility or subjective quality.

## Natural observation gate

Run `scripts/dock/face-voice-observation.sh` without creating synthetic
events. Review becomes useful after at least six successful speech decisions
over at least 24 hours. Until both thresholds are met, retain the frozen voice
profile and continue observation. A human listening report applies only to the
specific outcome heard and must not be generalized to later runs.

## Deferred

- Speech-rate tuning remains deferred to a dedicated profile task.
- Candidate voice exploration remains separate from this stability trial.
- Automatic claims of physical audibility remain out of scope without a
  separately linked human or sensory confirmation.
