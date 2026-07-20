# S21B-A9 canonical non-live plan and transcript

S21B-A9 adds the exact command `--dry-run-plan-v1` to the four named owned-lab
role artifacts. It accepts only the repository plan fixture's exact 371 bytes,
including its terminal LF. The SHA-256 of those bytes is
`00827c66e2f99be129a01c3b2b6ce5151aabb97d668280acff0366172cf75ee1`.

The plan is control metadata, not experiment input. Every capability field is
false. The implementation reads at most 372 bytes and compares bytes directly;
it does not parse permissive JSON, use the network, inspect a device, read real
experiment data, or perform an action. Missing, altered, reordered, extended,
or live-enabled input exits 65 without a transcript.

For the sole accepted plan, controller, observer, runner, and validator emit
one canonical JSON line each. The chain records plan validation, observation,
simulated dispatch, and terminal admission denial. Each line binds the plan
digest and states that plan metadata was read while real experiment input was
not read. This surface does not issue owner authority or an execution
capability and keeps `side_effects_unlocked` equal to `NONE`.

Validation is performed by
`scripts/check-memory-temporal-owned-lab-dry-run-plan-transcript-s21b-a9.sh`.
It runs package tests with one build job, checks all four positive transcripts,
and checks empty, truncated, appended, live-enabled, and unknown plan inputs.
