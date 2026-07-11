# Retrieval Traffic Class v42 Preregistration

Date: 2026-07-10

Status: `PROTOCOL_FROZEN / ADDITIVE_PROVENANCE / APPLY_OFF / NO_REMOTE_CI`

## Decision

Add an explicit traffic-origin label to `retrieval_surfacing` before any
surfaced-to-used telemetry is interpreted as causal evidence.

The first commit containing this report is the protocol anchor. Implementation
may follow only if it preserves every boundary below. This is not a blind
experiment: the prior aggregate audit already established that the live v41
schema has no origin label and that eval contamination is unidentifiable.

Parent source:

```text
223095947525a85fb88ddace286701ba47c12412
```

## Immediate Runtime Containment

Before this freeze, read-only inspection found the host's daemon had both the
collector and the importance consumer enabled even though the current decision
is collection-only. The daemon skips its t=0 tick and had consumed zero rows in
the preceding 24 hours, so the consumer was disabled before its next daily
pass:

```text
collector_enabled=true
apply_enabled=false
daemon healthz=200
```

The machine-env edit changed only the guarded default for
`AGENT_BRIDGE_RETRIEVAL_OUTCOME_APPLY` from `1` to `0`. Rollback is the inverse
one-line edit plus daemon restart, but reopening is forbidden until a labelled
organic-only shadow passes. The insecure full-file backup attempt was deleted
because this host filesystem did not honor restrictive modes; before/after
SHA-256 values and the inverse patch are the rollback evidence.

## Schema Contract

Schema v42 adds exactly one column and one index:

```sql
traffic_class TEXT NOT NULL DEFAULT 'unknown'
  CHECK (traffic_class IN ('unknown', 'organic', 'eval'))

CREATE INDEX idx_retrieval_surfacing_traffic_at
  ON retrieval_surfacing(traffic_class, surfaced_at DESC);
```

Meanings:

- `organic`: a normal user/agent runtime process explicitly identified at its
  process boundary;
- `eval`: a benchmark, smoke, verifier, or experiment process explicitly
  identified at its process boundary;
- `unknown`: historical rows, a missing label, an empty label, or an invalid
  label.

`mode=bootstrap` continues to identify the ambient retrieval channel. Traffic
origin and retrieval mode are orthogonal: an eval process invoking bootstrap
must write `traffic_class=eval`, not `organic` or a synthetic ambient class.

Migration rules:

1. Existing rows become `unknown`; no historical inference or backfill.
2. Fresh databases create the column with the same constraint.
3. Reopening a partially migrated database is idempotent and tolerates the
   existing concurrent-first-open race.
4. Row counts, query bytes, ranks, timestamps, used/consumed stamps, and ids are
   unchanged by migration.
5. The v41 binary must remain able to open a v42 DB and insert rows; omitted
   column values fall closed to `unknown` through the default.

## Producer Contract

The process-level input is:

```text
AGENT_BRIDGE_RETRIEVAL_TRAFFIC_CLASS=organic|eval
```

Rules:

- unset, empty, whitespace-only, or any other value normalizes to `unknown`;
- accepted values normalize case-insensitively to canonical lowercase;
- `memory_search` and semantic `session_bootstrap` capture the normalized value
  before spawning their fire-and-forget writer;
- no MCP tool argument or JSON schema field exposes this label, so a model call
  cannot self-classify to escape outcome accounting;
- the store normalizes again, so non-bridge callers cannot persist an invalid
  class;
- the production wrapper's per-machine env must explicitly default to
  `organic` at deployment;
- repository-owned eval processes must explicitly override to `eval`.

Initial repository eval coverage:

- `scripts/eval/ab_eval.py`;
- `scripts/eval/portfolio_continuity_ab_trial.py` (collector is already off and
  DB isolated, but provenance remains explicit);
- shell/Python verifier entry points that spawn `agent-bridge mcp` receive an
  explicit eval export when touched by this slice.

Unmodified external scripts are not silently trusted. If they omit the env,
their rows are `unknown` and keep causal admission closed.

## Consumer Boundary

This slice does not change any reinforce/decay formula, candidate threshold,
importance, consumption marker, daemon cadence, or apply SQL. The local daemon
consumer remains disabled.

The current summary/shadow/apply tools are legacy mixed-traffic surfaces until
a later protocol explicitly filters to organic rows and passes a labelled
shadow. V42 provenance alone cannot reopen them.

The causality audit must move from `BLOCKED_NEEDS_TRAFFIC_CLASS` to at most
`BLOCKED_PARTIAL_TRAFFIC_CLASS` immediately after migration because historical
rows remain unknown. `READY_FOR_CLEAN_SHADOW` requires complete valid labels in
its frozen relevant windows; deployment itself is not success.

## Ambient Gate Amendment

After v42, `ambient_gate.py` must:

1. calculate thresholds from `mode=bootstrap AND traffic_class=organic` only;
2. report eval and unknown bootstrap counts separately;
3. find the first organic bootstrap timestamp and block if any unknown/invalid
   bootstrap row occurs at or after that point;
4. return `WAIT_LABELLED_DATA` when no organic bootstrap row exists;
5. retain the existing 100 total / 7 days / 50 clean thresholds;
6. keep `stage2_action_authorized=false` in the sibling causality audit.

Historical unknown and explicitly eval bootstrap rows never contribute to the
ambient maturation threshold.

## Acceptance Gates

### Synthetic / Rust

1. v41 -> v42 migration preserves historical rows and labels them `unknown`.
2. Fresh v42 schema has one constrained column and the traffic/time index.
3. Store writes persist canonical `organic`, `eval`, and fail-closed `unknown`.
4. Invalid direct callers cannot create an out-of-vocabulary DB value.
5. Bridge env parsing covers unset, empty, whitespace, mixed case, accepted,
   and invalid inputs.
6. Search and bootstrap writers pass a captured process label; no tool schema
   contains `traffic_class`.
7. Repo eval harness subprocess environments contain `eval`.
8. Ambient fixtures prove organic-only counting, eval exclusion, historical
   unknown exclusion, and post-label unknown blocking.
9. Existing memory-evidence audit fixtures still pass.
10. `cargo fmt --all -- --check`, full `ab-store`, and targeted/full bridge
    tests pass locally.

### Copied DB

1. Make an online SQLite backup of live v41 into ignored/private storage.
2. Record source row counts and a canonical digest of all pre-v42
   `retrieval_surfacing` fields.
3. Open the copy with the candidate binary to migrate it.
4. Require schema version 42, unchanged row counts/digest, every historical row
   `unknown`, and zero organic/eval historical rows.
5. Run isolated organic, eval, unset, and invalid writer smokes against copies;
   require exact canonical labels and no raw query/key in public output.
6. Prove the current v41 binary can reopen the migrated copy and add an
   `unknown` row through its explicit old-column insert.

### Deployment

Deployment is admitted only after all preceding gates pass and master is at the
candidate commit.

1. Build locally from the exact commit; no remote CI.
2. Preserve the old binary with its source identity. The migration is additive
   and backward-compatible, so binary rollback does not require a DB downgrade.
3. Add guarded per-machine default `organic`; keep apply default `0`.
4. Install the candidate and restart bounded Agent-Bridge services.
5. Require installed source identity, schema 42, daemon/Palace health, collector
   on, apply off, and zero migration row-count drift.
6. Run only isolated/copied-DB writer smokes. Do not manufacture live organic
   evidence for acceptance.
7. A read-only live causality audit must return
   `BLOCKED_PARTIAL_TRAFFIC_CLASS` or `WAIT_LABELLED_DATA`, never
   `READY_FOR_CLEAN_SHADOW` on deployment day.

## Stop Conditions

Stop without deployment if any of these occurs:

- migration changes or drops an existing surfacing row;
- an invalid class reaches SQLite;
- an eval harness writes organic by default;
- a model-facing tool can choose the class;
- existing v41 binary cannot use the migrated DB;
- apply becomes enabled;
- ambient thresholds count eval/unknown rows;
- tests require raw production keys or queries in public artifacts;
- a remote CI run would be required.

## Authority

Passing v42 authorizes provenance collection only. It does not authorize
importance apply, organic-only consumer filtering, decay, ambient stage 2,
successor v3 execution, release, version, tag, or remote CI.
