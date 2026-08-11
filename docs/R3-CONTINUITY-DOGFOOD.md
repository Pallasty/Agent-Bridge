# R3 Continuity Dogfood

R3 asks whether existing continuity surfaces reduce context-recovery cost during
ordinary development. It does not introduce another memory mechanism or a
synthetic evaluation chain.

## Observed problem

A targeted semantic bootstrap surfaced the active R0/R1/R2 state, but unrelated
global historical `session_handoff` rows also received guaranteed orientation
space. Current master already restricts the semantic handoff prefix to current,
actionable, verified, exact-project rows. The Project State Digest still chose
its last handoff using only `status=active`, leaving a second route for the same
noise.

## Bounded correction

Both handoff priority routes now use `bootstrap_handoff_priority_eligible`.
Only an active, actionable, verified, exact-project handoff may displace current
state by kind alone. Global, cross-project, stale, auto-curated, unverified, and
background/archive handoffs remain searchable; they simply receive no guaranteed
prefix or digest slot.

Static bootstrap behavior, memory storage, semantic ranking, work-memory schema,
hooks, deployment, and runtime admission remain unchanged.

## Daily operating loop

1. Use a targeted bootstrap when starting or materially changing topic.
2. Save one short-lived active work-memory slot only when continuation value is
   expected.
3. Clear that slot when the task completes.
4. Save only durable decisions or lessons; do not duplicate the transcript.
5. Let normal session-end hooks handle curation. Use manual finalize only for
   diagnosis or hosts without hooks.

R3 remains dogfood, not a completed product claim. Further corrections require
another observed daily-task failure; a source regression test alone does not
justify expanding the continuity architecture.
