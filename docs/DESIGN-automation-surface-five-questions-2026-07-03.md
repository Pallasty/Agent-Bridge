# Automation-surface authoring checklist: the five questions (2026-07-03)

Borrowed from the SGLang team's agent-assisted development write-up
(LMSYS blog, 2026-07-02, "Agent-Assisted SGLang Development") — their
SKILL.md protocol requires every automated workflow to answer five
questions before it ships. Agent-bridge already practices most of this
ad hoc (safety ladders, shadow tools, rollback-map audits); this doc
names the checklist so future automation surfaces answer it *by
convention* instead of by accident.

Scope: anything that acts without a human in the loop — daemon ticks,
apply tools with a confirm path, reapers, sync passes. Read-only
reporting tools are exempt.

## The five questions

1. **When** — what triggers it, and what hard-stops it?
   Trigger: env gate (default-OFF, flipped in machine.env), cadence,
   maturation window. Hard-stop: the conditions under which it must
   refuse to act even when triggered (boot fences, shape validation,
   scan-saturation warnings, parameter rejection). Every kill/write
   path needs at least one named hard-stop.

2. **How to start** — what does preflight check?
   Gates read, migration/schema state present, required resources
   reachable. A surface that assumes state (e.g. a column added by a
   migration that only runs at store open) must verify or tolerate its
   absence.

3. **How to validate** — what proves a pass did the right thing?
   A read-only shadow/what-if twin (dry-run default on the tool), a
   live golden test for the destructive path, and an idempotency check
   (immediate rerun applies zero changes).

4. **How to decide** — what are the explicit outcome buckets and the
   quantified threshold for acting?
   Classification must be enumerable (applied / skipped / at-floor /
   at-ceiling / below-min / legacy…), and action gated on a measured
   gap, not intuition. Fix the measurement *before* looking at results
   (the SGLang "fixed workload before profiling" rule — same reason our
   probes pin a regime boundary first).

5. **How to deliver** — what artifact survives the pass?
   A rollback-map audit record persisted *before* writes and re-saved
   with per-row outcomes after, a one-line rollback in machine.env
   comments, and a CHANGELOG entry.

## Retro-audit of existing surfaces (all pass; gaps named)

| Surface | When/hard-stop | Preflight | Validate | Decide | Deliver |
|---|---|---|---|---|---|
| `outcome_valence_importance_apply` | env gate; clamp 0.1–0.9 | gate + rule derivability | dry-run default; idempotent | derivable vs kept-0.5 | rollback-map audit memory |
| `retrieval_outcome_apply` (daily tick) | gate; 7h maturation; param validate; max_changes | gate + params | shadow twin; live pass; idempotent rerun = 0 | applied/at-floor/at-ceiling/zero-step/below-min | consume-first txn + audit memory |
| `orphan_reaper` (hourly tick) | gate; boot fence; pgid shape; saturation warn | gate + /proc probes | live golden test (real setsid sleeper) | OwnerAlive/OrphanAlive/ZombieLeader/GoneOrReused/Legacy | finalised rows + report; kill unproven ⇒ row stays running |

Named gap: each surface formats its audit artifact bespoke (~70 lines
duplicated between the two apply passes). The "deliver" answer should
converge on a shared audit helper — already in the follow-up pool.

## Deliberately not borrowed (judged, not forgotten)

- **Per-round dual-role review** (their Humanize/RLCR: executor +
  reviewer every round). We review adversarially once, pre-merge; a
  per-round reviewer only pays off for long *unattended* optimization
  loops, which we don't run yet. Revisit if we build one.
- **Public task ledger** (their KDA-Pilot) — the forum already serves
  this role.
- **Fair-search / fixed-benchmark discipline** — already an iron law
  here (MEASURE-first, regime boundaries, shadow before apply).
