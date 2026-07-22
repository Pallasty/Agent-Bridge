# Free Recall Strategy R4 — Observation-Only Integration Result

Date: 2026-07-21

Status: **COMPLETE / DESIGN CONTRACT PASS / R5 SOURCE-PLAN ELIGIBLE**

Preregistration:
`docs/design/FREE_RECALL_STRATEGY_R4_OBSERVATION_ONLY_INTEGRATION_PREREGISTRATION_2026_07_21.md`

Validator:
`scripts/eval/free_recall_strategy_r4_observation_contract.py`

## 1. Verdict

The R4 design contract passed its public-synthetic isolation, fail-closed,
mutation, and determinism gates. Agent-Bridge can represent a prospective
episode observation surface as a separate append-only relation without adding
fields to `MemoryRecord`, reusing lifecycle events as membership truth, or
granting any retrieval/runtime authority.

This result validates a design boundary only. No table, store trait, producer,
projection, MCP surface, real-session capture, retrieval consumer, build, or
deployment was created or authorized.

## 2. Source-grounded decisions

The review found two unsuitable shortcuts:

1. adding episode fields to `MemoryRecord` would couple an optional experiment
   to the canonical memory row and its many construction/serialization sites;
2. treating the existing `session_curate` semantic lifecycle event as episode
   truth would overstate its evidence: that event reports aggregate persistence
   outcome, not complete ordered membership.

The accepted design therefore uses an independent proposed relation,
`episode_observation_events`, with no FTS, vector, graph, coactivation, memory
write, or retrieval trigger. `observed_at` is append metadata only; declared
`episode_position` remains the sole ordering authority.

## 3. Contract gate results

| Gate | Result |
| --- | --- |
| Canonical manifest | pass |
| Isolation | pass |
| Fail closed | pass |
| Directed mutations | `36 / 36` rejected as intended |
| JSON key-order invariance | pass |
| Zero runtime authority | pass |

Canonical manifest SHA-256:

`7ed0de5578c7961d04fe734ab1bfd48e82e014efa7c56ae3ef5df57acc357032`

The directed mutations independently attempted to enable every authority flag,
enable shadow mode, couple the design to `memories` or `MemoryRecord`, add
forbidden content/identity/retrieval fields, attach triggers or consumers, use
time as ordering authority, allow partial output, weaken abstention, remove the
kill switch, claim real capture, and widen the next authority. Every mutation
failed for its preregistered reason.

## 4. Independent determinism evidence

The standard-library-only validator passed `py_compile` and its complete
self-test locally and in the isolated tb14 worktree. Both runs emitted the same
aggregate report SHA-256:

`53ed13ca93ca2933125a0aec3e6bc210f6a0301d78c5a7859c39b461e4325f20`

The validator opens no database, network, MCP surface, private fixture, clock,
or environment input.

## 5. Accepted minimum design

- contract remains `mode = disabled` and every authority flag is false;
- events are append-only and independent from canonical memory rows;
- allowed data is structural and opaque; no content, tags, embedding, raw
  memory key, query, scope, rank score, or identity is duplicated;
- R3 reduction semantics remain authoritative;
- absence, ambiguity, conflict, and incompleteness all abstain;
- disabled means zero producer calls, sidecar writes, retrieval projection
  reads, memory API differences, and retrieval output differences;
- a kill switch is mandatory.

## 6. Unresolved security boundary

`item_ref` is intentionally unresolved. A source implementation cannot be
accepted until a separate review chooses and falsifies its derivation, local
secret custody, domain separation, rotation, collision behavior, deletion
semantics, and bounded offline join procedure. R4 does not choose HMAC, random
handles, raw keys, or another mechanism by implication.

This is the main technical prerequisite for R5, not a documentation detail.

## 7. Next admissible target: R5 source-only plan

R5 may design, but not yet implement, the smallest default-off source slice:

1. resolve `item_ref` security and lifecycle semantics;
2. freeze a migration and rollback plan for a separate relation;
3. freeze a narrow store interface whose disabled implementation performs no
   writes;
4. identify exactly one explicit producer seam without inferring episodes;
5. keep the projection private and disconnected from retrieval;
6. specify source-level and disposable-database tests, including downgrade,
   malformed replay, kill-switch, and zero-diff baselines;
7. split source, build, execution, real capture, deployment, and retrieval
   experiments into separate owner authorization gates.

R5 eligibility is not R5 authorization. No source implementation should begin
from this result alone.
