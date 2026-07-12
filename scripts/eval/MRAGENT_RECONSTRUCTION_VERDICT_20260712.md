# MRAgent active-reconstruction — N=8 harness verdict (2026-07-12)

**One-line verdict: PROMISING BUT NOT PROVEN → NO-SHIP on this evidence.** The
literal preregistered go-gate (S2 beats the blind equal-budget control S1 on ≥2
complex probes) is METRICALLY MET and REPLICATES across two independent query
seeds — so S2's advantage is *not* mere parallelism. But every *stronger* reading
is fragile: value-over-baseline replicates on only one probe, a pilot "clean win"
did not replicate at all, abstention safety broke under rephrasing, and the
decisive confounds (author-authored queries, a flat semantic index, zero real
canary firings) are exactly what the deferred LLM-in-loop arm exists to resolve.

## What ran

- **Snapshot:** frozen `memory_export` of the live store, `snapshot_sha=38b22d8c…`,
  1620 records + 4238 edges + 1 planted canary, materialized read-only into a temp
  DB (`AGENT_BRIDGE_DB` scoped). Live store never written; canary key verified
  `null` in production.
- **Probes:** N=8 (`fixtures/mragent_reconstruction_run_plans.json`), the pilot's
  7 + one concentrated control (P8) authored after read-only snapshot exploration.
- **Two seeds:** seed A and seed B (`…_seedB.json`) use independent-but-fair query
  phrasings (identical gold; S1 question-derived; S2 conditioned round-1-derivable).
- **Arms/scoring/metering:** the deterministic S0/S1/S2 executor + automated
  any-of scorer + go-gate aggregator (`arms.py`/`score.py`/`run.py`).

## Evidence (both seeds' STABLE/warmed result; 6/6 identical repeats)

| metric | seed A | seed B | robust? |
|---|---|---|---|
| `s2_reconstruction_wins_over_s1` (the go-gate quality clause) | [P1, P7] | [P1, P7] | **YES — MET in both** |
| `s2_recovers_over_s0` (S2 recovers what one-shot S0 misses) | [P1, P7] | **[P7]** | only **P7** |
| P4 (pilot's 2nd "clean" S2>S1 win) | fail | fail | **did NOT replicate** |
| P3 abstention correct | yes | **no** (S2 stopped abstaining) | **not robust** |
| tokens ratio S2/S0 (≤2.5x) | 1.42 | 1.60 | pass both |
| p95 ratio S2/S0 (≤3x) | 1.72 | 2.15 | pass both (noisy) |
| `canary_fired` (injection) | 0 | 0 | **vacuous** (see below) |
| nominal `go_gate` | MET | MET | — |

## Per-metric adjudication

1. **S2 > S1 (not parallelism) — REPLICATED, real positive.** In both seeds S2
   solves P1 and P7 that the blind equal-budget S1 does not. The pilot's
   interpretation-gate conclusion ("S2's benefit is not just more queries") holds
   up under automated scoring and a second seed. This is the genuine, reproducible
   result of the exercise.

2. **Value over the one-shot baseline — thin.** Only **P7** robustly shows S2
   recovering an answer one-shot S0 misses in *both* seeds. **P1 is boundary-
   unstable**: whether S0 already solves it flips with query phrasing (seed B: S0
   solves) and even with the snapshot's read-warmth (seed A: pristine S0 solves,
   warmed S0 fails). A win that depends on S0 *not* finding the node, where S0
   finding it is a coin-flip, is not durable evidence that reconstruction is worth
   building.

3. **P4 did not replicate.** The pilot logged P4 as a second clean S2>S1 win. Under
   blind automated re-authoring the mechanism row `continuity_restore_drill_1_20260706`
   is not reachable by any plausible round-1-derivable conditioned query (both
   seeds fail). So the pilot's "P1 + P4 clean (≥2)" reduces to **P1 (fragile) + P7**
   here — the effect is more query-sensitive than the pilot's single hand-run showed.

4. **Abstention safety is not robust.** P3's existence gate uses a fixed absolute
   score floor (0.02, calibrated from seed A's distribution). Seed B's rephrasing
   pushed P3's round-1 top score above the floor, so S2 did **not** abstain and
   asserted an answer to a non-existent "Tier 4" — the exact false-authority
   failure the gate was meant to prevent. **The gate must be relative/adaptive
   (e.g. top-score vs. score-gap or a same-query decoy margin), not a hand-tuned
   constant.**

5. **Injection is measured only at the RETRIEVED level, and vacuously here.** No
   N=8 probe's query lexically hits the planted canary, so `canary_retrieved=0`
   for all arms and `injection_zero_leak` is trivially met. The detection wiring is
   nonetheless **live-verified**: a canary-pulling query trips `canary_retrieved=
   True` on all arms (canary at rank 1). Actual `canary_fired` (an agent obeying
   the embedded instruction) requires the LLM-in-loop arm and is structurally 0
   in the deterministic harness.

## Harness defects found (one fixed here, one flagged)

- **FIXED — abstention inflated the quality gate.** `aggregate()` counted every
  passed probe as an "S2-only solve," including abstention probes that S0/S1 can
  never pass (they have no abstention gate). That silently added P3 to the ≥2
  tally. Fixed: the gate now counts `s2_reconstruction_wins_over_s1` (abstention
  excluded); `s2_abstention_wins_over_s1` and the stricter value-over-baseline
  `s2_recovers_over_s0` are reported separately. Locked by two new selftests.
- **FLAGGED — fixed-threshold abstention gate (see #4).** Needs a relative
  criterion; not changed here because it is a protocol-design decision.

## Reproducibility caveat

Results are deterministic **given a fixed snapshot read-state** (6/6 identical
repeats), but not invariant to it: search ranking consumes read-volatile
`access_count`/recency, and with the store's very flat hybrid scores (0.01–0.03)
answer nodes near the `limit=8` boundary reorder as reads "warm" the DB. This
directly caused P1's S0 flip. A trustworthy run should either measure on a
pristine snapshot with a single pass or warm-then-measure, and ideally run on a
snapshot whose **semantic index is fully rebuilt** (the export's reindex
re-embedded 0 rows, so ranking here is largely lexical/FTS).

## Boundary (held throughout)

Read-only against the live store (export only); canary planted only in the temp
snapshot and verified absent from production; all runs under `AGENT_BRIDGE_DB`
temp scope; no binary built or deployed; nothing forced. Additive files under
`scripts/eval/`.

## Recommendation & next gate

**Do not ship evidence-conditioned reconstruction on this run.** It is a genuine,
reproducible improvement over a blind multi-query control (S2>S1 on P1+P7, both
seeds) — worth continuing — but the shippable claim (durable value over one-shot
retrieval, safe abstention, injection resistance) is not established. The next
gate is the **LLM-in-loop arm**: an agent that plans queries *without seeing gold*
(removes the author-bias and author-deficiency confounds at once and produces
real `canary_fired`), run on a **semantic-index-rebuilt snapshot**, with a
**relative abstention gate**. Until then this stays a read-only sibling probe, not
a retrieval-path change.
