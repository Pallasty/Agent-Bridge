# Temporal Truth And Retrieval Telemetry Audit Preregistration

Date: 2026-07-10

Status: `PROTOCOL_FROZEN / READ_ONLY / KNOWN_PRIOR / NO_RUNTIME_AUTHORITY`

## Decision

Freeze two aggregate-only audits before running either helper against the live
Agent-Bridge store:

1. a structural stale-active evidence audit; and
2. a retrieval-telemetry causal-separability audit.

The first commit that contains this report, both helpers, and their synthetic
verifier is the protocol freeze anchor. The live result must name that exact
commit and use the tracked helper bytes from it.

This is not an independent confirmation of a hidden hypothesis. Forum #119
post #3072 and durable memory `ab_staleness_gate_pass_20260710` already report a
manual, truth-anchor-based staleness measurement (`M2=9/13`). The temporal
helper below mechanizes only structure that can be reproduced without reading
or publishing memory prose. It cannot reproduce or validate the manual
semantic labels.

The current schema was also inspected before this freeze and is known not to
contain a traffic-origin label. The telemetry experiment therefore tests the
fail-closed observability contract and quantifies the unresolved contamination
surface; it is not a blind discovery run.

## Source And Parallel Boundary

Parent source:

```text
c83ac016dc5d2844ad47d64dbe9d59aa259add6d
```

Explicit exclusions:

- the untracked Temporal Truth Projection v0 design in the separate
  `feat/temporal-truth-projection-v0-20260710` worktree;
- the uncommitted `supersede-enforcement` store mutation in a separate
  worktree;
- any correction, archive, supersede, importance, retrieval-ranking, schema,
  environment, daemon, deployment, version, tag, release, or CI action;
- ArrowQuant m24, which remains an independently occupied execution lane.

Those worktrees stay untouched. Their presence is prior context, not input to
the aggregate calculations.

## Audit T: Structural Temporal Signals

Question:

> Does the current store contain explicit lifecycle or freshness evidence that
> conflicts with an active/current retrieval posture?

The helper may read only these fields:

- `memories`: key, kind, tags, timestamps, access count, status,
  `superseded_by`, and `dedupe_key`;
- `memory_edges`: endpoints, edge type, and creation time.

It must not read `memories.content`, embeddings, retrieval queries, user text,
or agent transcripts.

Frozen signal classes:

| Signal | Mechanical definition |
|---|---|
| active with `superseded_by` | `status=active` and non-empty `superseded_by` |
| active supersedes target | active row is target of a `supersedes` edge |
| active invalidates target | active row is target of an `invalidates` edge |
| active declared target | active row is named by an active source's `continuity_supersedes:*` tag |
| declared edge missing | declared target exists but the matching `supersedes` edge does not |
| correction edge missing | active `feedback` key under `correction:*` has no outgoing `corrects` edge |
| corrected active target | active row is target of a `corrects` edge; observational, not actionable by itself |
| aging bounded state | active, non-constraint, `must_block`, version/project-phase bound, and not updated for 14 days |
| aging constraint | constraint with bounded freshness and no update for 45 days; review-only |
| duplicate active dedupe key | two or more active rows share one non-empty `dedupe_key` |
| malformed tags | tags are not a JSON string array |

The helper also counts active superseded/invalidated targets accessed after the
edge timestamp. It does not attribute causality to that access.

Verdict:

- `REVIEW_REQUIRED` if any actionable class is non-empty;
- `CLEAN` otherwise.

`active_corrected_target` and `aging_constraint_review` are informational and
do not independently trigger `REVIEW_REQUIRED`. A review verdict cannot
archive or supersede a row. Whole-row retirement from claim-level metadata is
specifically out of scope because one evidence row may contain more than one
claim.

## Audit R: Retrieval Causality

Question:

> Can eval-generated retrievals be separated from organic retrievals before
> outcome reinforcement or decay candidates are interpreted?

The helper may read:

- `retrieval_surfacing`: memory key, mode, rank, surfacing/use/consume
  timestamps, and optional `traffic_class`;
- active key membership from `memories`.

It must not select or inspect `retrieval_surfacing.query`. Query text, key
prefixes, timing clusters, process names, and session guesses are forbidden as
traffic-origin heuristics.

The additive label contract is exact:

```text
traffic_class = organic | eval
```

`bootstrap` remains identified by `mode=bootstrap` and stays outside the
search reinforce/decay aggregate. A later producer may label it separately,
but that is not required for this gate.

Frozen analysis slices:

- descriptive window: most recent 3 days;
- behavior-relevant slice: active-memory, non-bootstrap, unconsumed rows with
  `surfaced_at <= as_of - 25,200 seconds`, matching the current apply
  maturation constant;
- reinforce candidate: at least one used row for a key;
- decay candidate: at least two rows and zero used rows for a key.

The existing candidate set is calculated over all behavior-relevant rows, as
the current store does. If labels exist, a clean shadow candidate set is also
recomputed from `traffic_class=organic` only. Known eval intersections and
unknown-label upper bounds are reported as counts, never keys.

Verdict:

- no `traffic_class` column: `BLOCKED_NEEDS_TRAFFIC_CLASS`;
- column present but any relevant/window search row is invalid or unlabeled:
  `BLOCKED_PARTIAL_TRAFFIC_CLASS`;
- complete valid labels: `READY_FOR_CLEAN_SHADOW`.

Even `READY_FOR_CLEAN_SHADOW` does not authorize `retrieval_outcome_apply`, a
daemon tick, importance writes, or default behavior.

## Ambient Gate

Audit R independently reproduces the existing stage-2 maturation counters:

```text
total bootstrap stamps >= 100
distinct used-at days >= 7
clean stamps >= 50
clean = rank <= 30 and key is not distill_draft_*
```

All three conditions are required for `OPEN`; otherwise the result is `WAIT`.
The audit always emits `stage2_action_authorized=false`. An OPEN result would
admit only a separately preregistered reinforce-only shadow, never decay.

## Privacy And No-Write Contract

Both helpers must:

- open SQLite through a `mode=ro` URI and set `PRAGMA query_only=ON`;
- finish with connection `total_changes=0`;
- emit no database path, memory key, query, content, session id, or raw
  timestamped event;
- emit only counts, rates, fixed policy values, verdicts, and a SHA-256 digest
  over the private candidate manifest;
- write a real result only below ignored `data/` with mode `0600`;
- publish only a manually selected aggregate report plus the private result
  file hash.

The live database can receive unrelated concurrent writes. Connection-local
`mode=ro`, `query_only`, and `total_changes=0` prove this audit made no SQLite
changes; global file hashes or row-count equality are not used as false proof
against concurrent writers.

## Synthetic Acceptance

`scripts/verify-memory-evidence-audits.sh` must pass these fixtures before a
live run:

1. every temporal signal class, including post-signal access;
2. an unlabeled telemetry schema that blocks with non-zero contamination upper
   bounds;
3. a fully labeled schema that separates organic and eval candidate sets and
   admits clean shadow only;
4. a partially labeled schema that blocks;
5. incomplete schema rejection;
6. zero raw fixture identifiers in all output packets;
7. unchanged fixture table counts after every audit.

## Decision Matrix

| Observation | Next decision |
|---|---|
| temporal actionable count is zero | retain audit as a regression probe; no write |
| temporal actionable count is non-zero | review claim/row semantics and select a separate tiny repair protocol; no auto-retirement |
| traffic label absent/partial | keep outcome apply blocked; design an additive producer label in a new lane |
| traffic labels complete | run an organic-only shadow under a separate freeze; still no apply |
| ambient `WAIT` | collect more days; no stage-2 work |
| ambient `OPEN` | preregister reinforce-only ambient shadow; decay remains prohibited |

## Commands After Freeze

```bash
bash scripts/verify-memory-evidence-audits.sh

umask 077
mkdir -p data/eval/memory-evidence-audits-20260710
python3 scripts/eval/temporal_truth_drift_audit.py --json \
  > data/eval/memory-evidence-audits-20260710/temporal.json
python3 scripts/eval/retrieval_telemetry_causality_audit.py --json \
  > data/eval/memory-evidence-audits-20260710/telemetry.json
```

No remote CI may be triggered. Any push must use a `[skip ci]` commit.
