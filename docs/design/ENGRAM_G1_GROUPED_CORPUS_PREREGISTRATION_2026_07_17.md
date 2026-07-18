# Engram G1 Grouped-Corpus Preregistration

Date: 2026-07-17

Status: **READY FOR INDEPENDENT CONSUMER CORPUS-ASSEMBLY REVIEW**

## Authority boundary

This document fixes the proposed G1 corpus structure, metrics, access rules,
resource ceiling, and review custody. It does not contain raw probes, episode
keys, or partition membership. It does not freeze a corpus or authorize
candidate implementation, retrieval-order changes, BioCortex experiment
execution, live-store writes, or runtime promotion.

The machine-readable contract is
`scripts/eval/fixtures/engram_g1_grouped_corpus_design_v0.json`. Validate it
with `scripts/check-engram-g1-corpus-design.sh`.

## G0 binding and question

The design is bound to G0 packet
`hard_miss_cohort_20260622_23_g0` (`feb5c8c639f48a6179144cfbe6b16a548aef91a127840c37640b7673a88c97e1`),
which returned `PASS_OBSERVED_RELEVANT_FAILURE`. The admitted FIT-only episode
had signature `overgeneralization_gap`; the unrelated control retrieved the
accepted target while exact and related probes both passed.

The application question is therefore:

> Can a clustered-reorganization candidate reduce unrelated target intrusion
> without materially degrading exact or related retrieval?

Additional related-context lift is not the primary objective. A mechanism that
raises recall by broadening every neighborhood would fail this design.

## Grouped cohort

One episode group contains exactly three probes: exact, related, and unrelated.
The episode group is the indivisible split unit; its probes may never cross
partitions.

| Partition | Frozen groups | Candidate access |
|---|---:|---|
| FIT | 12 | visible |
| Development | 8 | reviewer-mediated results only |
| Sealed | 10 | custodian only |
| Total | 30 | — |

The admitted G0 incident belongs only to FIT, counts toward the primary-stratum
minimum, and is excluded from development and sealed evaluation. The scored
freeze target is 30 groups. The intake hard cap is 36 so reviewers may
adjudicate up to six alternates; only 30 groups may enter the eventual frozen
scored corpus.

The preregistered minimum composition is:

| Baseline signature | Role | FIT | Development | Sealed | Minimum |
|---|---|---:|---:|---:|---:|
| `overgeneralization_gap` | primary | 6 | 4 | 5 | 15 |
| `no_relevant_gap` | stability control | 3 | 3 | 3 | 9 |
| `ordinary_retrieval_gap` | exclusion control | 1 | 1 | 1 | 3 |

These minima allocate 27 of 30 slots. The final three may be filled only by
independently sourced eligible groups. A `generalization_gap` may enter that
remainder if independently observed. `ambiguous_dual_failure` is excluded.
The cohort must span at least four application families, and no family may
exceed 35% of frozen groups.

## Provenance and custody

Every probe must be consumer-owned, rights-cleared, and observed before the
candidate implementation hash is locked. Candidate authors may neither write
nor curate probes. At least two independent consumer reviewers must approve
the eventual roster and provenance receipts.

Three roles remain separate:

1. consumer curator — owns intake, provenance, grouping, and labels;
2. candidate implementer — sees FIT and reviewer-mediated development output;
3. sealed evaluator/custodian — alone sees sealed raw material, labels, and
   membership.

No person may hold more than one role. Sealed evaluation is one-shot and may
begin only after the candidate source/configuration hash is locked. The
candidate never receives sealed raw probes, labels, or partition membership.

## Frozen baseline and endpoints

Before any separate corpus-freeze decision, the proposed roster must be
replayed twice against the same frozen environment using FTS, hybrid, and
semantic retrieval at top 10. Every rank must be identical between the two
replays. The aggregate envelope counts a target intrusion if any preregistered
mode returns the accepted target in its top 10.

The primary endpoint is
`unrelated_target_intrusion_rate_at_10` on the `overgeneralization_gap` stratum.
Against the strongest preregistered baseline—defined as the baseline arm with
the lowest intrusion rate—the candidate must achieve at least 0.20 absolute
reduction. The episode group is the unit of analysis, and only the sealed
partition determines the final pass/fail verdict. FIT and development results
may guide fitting or reviewer-mediated debugging but cannot be pooled into the
decisive estimate.

The following gates apply simultaneously:

| Guard | Maximum absolute loss/increase |
|---|---:|
| Exact hit@10 loss | 0.02 |
| Related hit@10 loss | 0.02 |
| Exact MRR loss | 0.05 |
| Related MRR loss | 0.05 |
| Per-mode unrelated intrusion increase | 0.05 |
| `no_relevant_gap` control regression | 0.02 |

Passing the primary endpoint while failing any preservation or specificity
guard is a failure, not a trade-off to adjudicate after seeing sealed results.

## Later experiment shape, not execution authority

The proposed matched arms are `stable_control`, `density_only`,
`clustered_reorganization`, `mechanism_off`, and `cluster_shuffled`. They must
be deterministic, opt-in, and receive equal growth budgets. The mechanism-off
and cluster-shuffled arms are falsifiers: an apparent gain that survives both
does not support the reorganization mechanism.

These names reserve comparisons only. They do not authorize code, a runtime API
change, a BioCortex run, or a retrieval mutation.

## Resource ceiling and next gate

At the 36-group intake cap, three probes and three retrieval modes yield at
most 324 observations per replay. Two deterministic baseline replays yield at
most 648 observations. This ceiling cannot be increased after observing
results under this design revision.

A valid design receipt has verdict
`READY_FOR_CONSUMER_CORPUS_ASSEMBLY_REVIEW`. The next owner action is an
independent, private corpus-assembly review with provenance receipts. A later
corpus-freeze proposal must bind the exact roster, split manifest, baseline
replay receipts, reviewer identities, and hashes in a new gate. Until that
separate gate exists and passes, all implementation and experiment authorities
remain false.
