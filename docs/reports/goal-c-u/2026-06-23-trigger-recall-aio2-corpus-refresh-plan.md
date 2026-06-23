# Trigger Recall Aio2 Corpus Refresh Plan

Date: 2026-06-23

Scope: docs-only plan for resolving the stale `AIO2_NATIVE_CORPUS` blocker
found during Stage-2 preflight for
`trigger_recall_opt_in_pre_policy_hold_simulation`.

This plan does not mutate aio2 memory data, does not change default
`memory_search`, does not deploy, and does not authorize production
`enforce_hold`.

## Current State

The pre-policy hold simulation candidate is already on master by owner override:

- merge commit: `fbeebeb merge trigger pre-policy hold simulation candidate`;
- candidate commit: `2ceeef974066d382f69a0f2774ea08e452ca5252`;
- tool surface: `trigger_recall_opt_in_pre_policy_hold_simulation`;
- exposure: `Tier::Niche`;
- explicit boundary remains: no deploy/install, no default `memory_search`
  change, no production `enforce_hold`.

Stage-2 audit evidence is still blocked:

```text
cargo run -p ab-bridge --example trigger_recall_eval -- --aio2-baseline-acceptance-audit
Error: "aio2_lswr_g21_g22_apply_writer expected key missing: lswr_verified_outcome_ingestion_apply_writer_gates_landed_20260620"
```

## Verified Aio2 Evidence

Read-only checks on aio2 were run against:

```text
/home/pallasting/.local/share/agent-bridge/state.db
```

Findings:

| Check | Result |
|---|---:|
| total memories | `6299` |
| memories with non-empty `trigger_pattern` | `5` |
| active memories with non-empty `trigger_pattern` | `3` |
| exact key `lswr_verified_outcome_ingestion_apply_writer_gates_landed_20260620` | missing |
| `%outcome_ingestion_apply_writer%` key search | `0` |
| `lswr` / `verified_outcome` / `G21/G22` key/content/trigger query | no rows |
| local backup/recovery DB exact-key check | missing |
| local backup/recovery DB `%outcome_ingestion_apply_writer%` check | `0` |

Aio2 cross-node candidate behavior did pass:

```text
cargo test -p ab-bridge --lib trigger_recall_opt_in -- --nocapture
# 33 passed on aio2 detached candidate worktree
```

## Diagnosis

`crates/bridge/examples/trigger_recall_eval.rs` labels
`AIO2_NATIVE_CORPUS` as:

```text
aio2-native active trigger rows, 2026-06-22
```

That assumption no longer matches aio2 live DB on 2026-06-23. The failing
expected key and nearby LSWR verified-outcome rows are not present in current
live DB or local backups checked during this pass.

This is therefore a corpus/gold-set freshness problem, not evidence that the
pre-policy hold candidate code regressed.

## Options

### Option A: Restore Missing Trigger Rows

Restore the original LSWR trigger memories from an authoritative source, then
rerun the existing audit unchanged.

Use this only if the missing rows are supposed to be durable project evidence.
Do not reconstruct them from the eval fixture alone.

Acceptance evidence:

- exact expected keys exist in aio2 live DB;
- row status/scope/kind/content are verified against source evidence;
- `--aio2-baseline-acceptance-audit` passes unchanged.

Risk:

- may reintroduce stale or intentionally retired rows;
- needs clear provenance before any memory import/write.

### Option B: Refresh `AIO2_NATIVE_CORPUS`

Replace the host-local corpus with a new frozen sample from the current aio2 DB.

Use this if the old LSWR rows were legitimately retired and the audit is meant
to track current live trigger evidence rather than historical LSWR gates.

Required guardrails:

- use only active rows with non-empty `trigger_pattern`;
- freeze selected keys, queries, triggers, and notes in code review;
- include at least one accepted continuation case and one hard negative;
- state clearly that this remains host-local and date-stamped;
- preserve the existing `verify_corpus_for` fail-fast behavior.

Risk:

- current aio2 has only 3 active trigger rows, so a refreshed corpus may be too
small to support Stage-2 production confidence.

### Option C: Replace Host-Local Audit With Portable Fixture

Move Stage-2 baseline acceptance to a repo fixture independent of mutable aio2
memory DB state.

Use this if the audit is intended as a regression gate for code behavior rather
than a live-data audit.

Required guardrails:

- fixture includes redacted memory rows with stable keys/kinds/scopes/content;
- fixture includes accepted, held, and blocked-control shapes;
- live aio2 audit becomes optional telemetry, not a hard merge/deploy gate;
- report must say clearly when a result is fixture-only vs live-DB-backed.

Risk:

- weaker as evidence for live memory quality;
- stronger as evidence for repeatable code behavior.

## Recommendation

Use a two-step path:

1. Short term: make Stage-2 review use a portable fixture for deterministic code
   regression, while retaining the aio2 live audit as a separate telemetry line.
2. Medium term: define a new aio2 live-corpus refresh process with provenance
   and minimum sample-size rules before it becomes a hard gate again.

Do not unblock production `enforce_hold` from the current aio2 live audit,
because current active trigger evidence is too sparse.

## Next Implementation Slice

Recommended next slice:

```text
trigger_recall_eval_portable_stage2_fixture
```

Allowed work:

- add a fixture-backed Stage-2 eval mode;
- keep `--aio2-baseline-acceptance-audit` intact but mark its current state as
  blocked/stale in docs;
- add tests that distinguish fixture-backed pass from live-DB pass.

Forbidden work:

- memory DB mutation;
- importing reconstructed LSWR rows without provenance;
- default `memory_search` changes;
- production `enforce_hold`;
- deployment.

## Required Closeout Before Production Claims

Before any stronger production claim, produce one of:

- passing aio2 live audit with restored/provenance-checked corpus; or
- owner-approved replacement of the hard live-aio2 gate with a portable fixture
  gate plus a separate live telemetry requirement.

Until then, the safe state is:

```text
Niche simulation tool merged by owner override, deploy/production hold still blocked.
```
