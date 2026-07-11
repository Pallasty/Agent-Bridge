# Outcome-Apply Calibration v1 — preregistered procedure

Date: 2026-07-10 (design frozen before the calibration window closes)
Status: design + preregistration — no runtime change, no parameter change, apply stays default-OFF/manual/gated
Owner gate: 五问协议 object — the calibration REPORT requests activation; this document only fixes how the report will be produced.
Author lane: fable-b55243f8 (forum #119 posts 3072/3080 lineage)

## Decision

The apply machinery is complete and deliberately dormant: `retrieval_outcome_apply`
(PR #69) has parameterized rules shared verbatim with the `retrieval_outcome_shadow`
what-if harness, one-transaction consume-then-write, maturation, rollback maps, and a
daemon tick gated by `AGENT_BRIDGE_RETRIEVAL_OUTCOME_APPLY` (default OFF). What is
missing is not code but a **defensible parameter choice and an activation gate**. Two
preconditions cleared on 2026-07-10: collection was verified live (13k surfacing rows,
used-rate 9.7% non-ambient, rank-usage correlation present: used rows avg rank 2.95 vs
4.2 overall), and eval-traffic contamination — the reason the decay-candidate list was
poisoned — is now filtered at the source (`telemetry_class:"eval"`, commit `733f584e`).

This document preregisters the calibration procedure so parameters are chosen by
frozen rules over a clean window, not tuned after seeing what they would do to
favorite memories. Gates before numbers.

## Calibration window

- **Start**: first full day after eval-filter deployment (2026-07-11 00:00 local).
- **Length**: ≥7 calendar days (target close 2026-07-18), and MUST NOT exceed the
  measured ring-cap retention span — re-verify actual retention (`ORDER BY surfaced_at
  ASC LIMIT 1` age) on the close date before aggregating; if retention < window,
  shrink the window to retention and say so in the report.
- **Data-sufficiency gate** (all three, else extend the window; thresholds fixed from
  the 2026-07-10 7d baseline of ~4.3k non-ambient surfacings / ~270 used):
  1. ≥3,000 non-ambient, non-eval surfacings;
  2. ≥150 used-stamps;
  3. ≥25 distinct used keys.

## Contamination defenses (frozen now)

1. **Eval marking discipline**: every benchmark/measurement `memory_search`/`memory_get`
   in the window must carry `telemetry_class:"eval"` (or process env). Known scheduled
   measurement events are REGISTERED here in advance: the staleness-gate M2 re-measure
   (~2026-07-17) runs eval-marked. Lanes were notified in #119 post 3080.
2. **Unmarked-eval audit at close**: before aggregating, scan the window for replay
   signatures (same normalized query ≥10× from non-ambient modes with 0 used). Matches
   are excluded with the exclusion listed row-for-row in the report. If exclusions
   exceed 10% of non-ambient volume, the window is VOID — restart after fixing the
   leaking harness. No post-hoc judgment calls: the 10% rule is fixed here.
3. **Inherited exclusions**: ambient bootstrap rows and `eval:%` rows stay excluded by
   the aggregate layer; `protect_classes` stays ON (never-used telemetry on
   ambient-consumed classes is attribution bias, not deadness — "零信号≠负信号").

## Parameter selection (frozen procedure)

Grid over the shadow harness (`retrieval_outcome_shadow`, which shares the rule with
apply verbatim — preview cannot disagree with apply):

- `reinforce_step` ∈ {0.02, 0.05, 0.10}
- `decay_step` ∈ {0.01, 0.02, 0.05}
- `min_surfaced_for_decay` ∈ {2, 3, 5}
- `floor` = 0.1, `ceiling` = 0.9 fixed (v1 does not touch bounds)

Selection criteria, in lexicographic order (a candidate must pass 1–2 to be ranked by 3):

1. **No-saturation replay**: simulate 60 passes of the candidate rule on the window's
   aggregate (deterministic replay, same evidence re-applied). REJECT any candidate
   where >5% of touched keys end pinned at floor or ceiling, or where the touched
   keys' distinct-importance count collapses below 50% of its starting value. This is
   the reinforce-active saturation lesson (237 keys pinned at 0.95) applied in advance
   to the additive-step rule.
2. **Protected-face invariant**: zero prescribed actions on protected classes and on
   keys below `min_surfaced_for_decay` evidence.
3. **Rank-alignment score (maximize)**: split the window into halves; score = the
   degree to which keys the rule WOULD reinforce in the first half are used again in
   the second half, minus the degree to which keys it would decay are used again
   (a would-be-wrong-decay penalty, weighted 2× because a wrong decay hides a memory
   whereas a wrong reinforce only over-ranks one). Exact formula fixed in the
   calibration notebook committed WITH the report; ties → the more conservative
   (smaller-step) candidate.

## Activation gate (what the owner will be asked)

The calibration report requests exactly ONE step: a single **manual confirmed pass**
(`retrieval_outcome_apply confirm_apply=true`) with the selected parameters, preceded
by a DB backup, producing its built-in rollback map. NOT requested: daemon-tick
activation. After the manual pass, observe ≥7 days (`dream signal-fidelity`
n_ceiling_importance / top_distinct_importance, plus used-rate drift); only then may a
separate request propose the daemon tick. Rollback path: the pass's rollback map +
the pre-pass DB backup; a rollback, if taken, enters the loop as a negative outcome +
decision:rejected + lesson (回滚也是数据).

## Explicitly out of scope for v1

- Rule-shape changes (multiplicative-toward-target instead of additive step) — noted
  as the v2 candidate if the no-saturation replay shows additive+clamp pinning even at
  small steps; v1 only picks parameters for the shipped rule.
- Ambient bootstrap calibration (stage-2 of the dark-half loop, needs its own data).
- Any retrieval-ranking change (cosine-lead rerank stays DEFER).
- access_count hygiene (eval gets still bump access_count; known residual, separate
  slice if the reinforce-active trigger shows re-contamination).
