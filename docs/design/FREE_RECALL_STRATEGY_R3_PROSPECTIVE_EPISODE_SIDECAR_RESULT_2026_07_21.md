# Free Recall Strategy R3 — Prospective Episode Sidecar Result

Date: 2026-07-21

Status: **COMPLETE / PUBLIC-SYNTHETIC ADMISSION PASS / OBSERVATION-ONLY DESIGN ELIGIBLE**

Preregistration:
`docs/design/FREE_RECALL_STRATEGY_R3_PROSPECTIVE_EPISODE_SIDECAR_PREREGISTRATION_2026_07_21.md`

Evaluator:
`scripts/eval/free_recall_strategy_r3_episode_sidecar.py`

## 1. Verdict

The prospective `agent_bridge.episode_observation.v0` sidecar contract passed
all preregistered public-synthetic gates. A deterministic, order-independent
reducer reconstructed complete episode membership and position exactly,
remained invariant under permitted delivery transformations, and abstained
without partial leakage on every malformed case.

At fixed budget 8, the deliberately structural probe improved set recall from
`0.125` to `1.0` (`+0.875`) for eligible clean episodes, with zero regressions.
Ambiguous seeds and malformed episodes returned the baseline byte-for-byte.

This is a contract-capability result, not evidence of real-store retrieval
lift and not a reproduction of the paper's learned recurrent index code.

## 2. Frozen fixture and reducer

- 24 clean episodes, 8 items each, 192 item observations and 240 total events;
- a shared 64-item vocabulary prevents item identity from encoding position;
- globally unique event IDs and opaque episode/item IDs;
- exact event replay is idempotent;
- conflicting reuse of an event ID invalidates the affected episode;
- only episodes with one open, one close, and contiguous unique positions
  `0..item_count-1` enter finalized output;
- output is the finalized ordered `(episode_id, item_ids)` bundle only.

The reducer first canonicalizes events by event ID, records conflicts, and only
then validates each episode. Event arrival order therefore has no semantic
authority.

## 3. Gate results

### Contract and reconstruction

| Measure | Result | Gate |
| --- | ---: | --- |
| Membership precision | `1.0` | pass |
| Membership recall | `1.0` | pass |
| Membership F1 | `1.0` | pass |
| Position accuracy | `1.0` | pass |
| Finalized clean episodes | `24 / 24` | pass |

The original, reversed, shuffled, duplicated, close-first, and
content-variant-permuted streams all produced the same finalized bundle hash:

`bb960618c0b0f98d728d2321186104453aa7d335e11f817df1af840aeafe861b`

### Fail-closed behavior

The following six malformed cases all abstained for the target episode,
preserved unrelated episode output byte-for-byte, returned the target baseline,
and leaked no partial membership:

- missing item;
- duplicate position;
- duplicate item at two positions;
- conflicting duplicate event ID;
- missing open;
- missing close.

The ambiguous-seed case also abstained and returned its baseline unchanged.

### Fixed-budget probe

| Measure | Baseline | Sidecar | Result |
| --- | ---: | ---: | --- |
| Set recall@8 | `0.125` | `1.0` | `+0.875` |
| Page budget | `8` | `8` | unchanged |
| Eligible regressions | — | `0` | pass |
| Expanded eligible pages | — | `24` | pass |

The synthetic baseline intentionally contains one true seed and seven
distractors. The lift therefore demonstrates that an already-complete explicit
episode bundle can be consumed within a fixed budget; it does not estimate the
frequency, quality, or value of such bundles in real AB traffic.

## 4. Independent determinism evidence

The evaluator passed `py_compile` and its complete self-test locally and in an
isolated tb14 worktree. Both machines emitted the same aggregate report SHA-256:

`b517f37887a310cfe31abb047c15af85d7ef0756b3288b1e363d60e32f47011f`

No wall clock, network, database, private memory, or environment-dependent
input participates in fixture generation or scoring.

## 5. Claim boundary

R3 establishes only that the explicit sidecar contract is mechanically viable
and fail-closed under the preregistered synthetic fault model. It does not show:

- that real session or curation boundaries correspond to useful recall sets;
- that producers can emit complete and correct observations;
- that the sidecar improves real retrieval relevance;
- that explicit positions approximate the learned recurrent strategy reported
  by Li et al.;
- that any storage, MCP, retrieval, training, BioCortex, or deployment change
  is safe or authorized.

## 6. Next admissible target: R4 design review

R3 opens only a design task for a default-off, observation-only integration
surface. The recommended R4 contract should:

1. keep append-only episode observations separate from `MemoryRecord` and from
   retrieval indexes;
2. store opaque IDs and structural fields, not duplicated memory content;
3. accept only explicit producer declarations (`session`, `curation_batch`, or
   `owner_bundle`) and never infer membership from similarity;
4. build a read-only finalized projection with the same reducer and abstention
   rules used here;
5. have no retrieval consumer, rank mutation, MCP write surface, or default-on
   producer;
6. define a bounded, separately authorized shadow-observation phase before any
   real-session capture or offline utility audit;
7. preserve a kill switch and make absence, conflict, or ambiguity equivalent
   to no sidecar evidence.

R4 design acceptance would still not authorize schema implementation, real
capture, execution, deployment, or a retrieval experiment. Each is a separate
gate.
