# GTE 768 Local Runtime Switch Plan Closure

Date: 2026-06-30 UTC / 2026-06-29 America/Los_Angeles
Host: `pallasting-ThinkBook-14-G5-IRH`
Repo: `/Data/CascadeProjects/agent-bridge`
Source commit: `9ab4df4777363653426f29f955da8d26e138973a`
Scope: close the persisted `gte_runtime_switch_plan` follow-up as a
read-only state-and-runbook report.

## Verdict

No runtime switch is required on this local node. The live Agent-Bridge memory
store is already on schema v38 and all active embeddings report
`gte-multilingual-base` with 3072-byte f32 vectors, i.e. 768 dimensions.

Do not run a live reindex or DB mutation for this item. Future GTE maintenance
should use the existing gated scripts and recovery packet flow below.

## Current Evidence

`agent-bridge.real doctor --json`:

- `ok=true`
- `fails=0`
- `warns=0`
- daemon runtime check: ok
- MCP server binary check: all current `agent-bridge.real`

`agent-bridge.real continuity-report --json`:

- db: `/home/pallasting/.local/share/agent-bridge/state.db`
- `active_total=565`
- `embedded=565`
- `dominant_backend=gte-multilingual-base`
- `dominant_count=565`
- `stale_vectors=0`
- `backends=[{"backend":"gte-multilingual-base","n":565}]`

Direct read-only SQL through Python's sqlite3 module:

- `schema_meta.version=38`
- active status rows: `565`
- active status rows with f32 embeddings: `565`
- active f32 vector byte length: `min=3072`, `max=3072`
- active int8 shadow rows: `19`
- active int8 vector byte length: `min=768`, `max=768`
- active backend counts: `gte-multilingual-base=565`

Direct SQL using the stricter `status='active' and superseded_by is null`
predicate reports `563` rows. The two-row difference is a pre-existing
metadata shape: two active `work_memory` rows point at each other through
`superseded_by`. Both rows still have valid GTE 768 embeddings. This is not a
GTE runtime-switch blocker, but it is worth keeping distinct from the
continuity-report active-row definition.

## Existing Gate Assets

Use these assets for any future GTE maintenance instead of inventing a new
switch path:

- `scripts/verify-gte-768-preflight.sh`
- `scripts/verify-gte-768-canonical-snapshot-gate.sh`
- `scripts/verify-gte-768-reader-compatibility-probe.sh`
- `scripts/fetch-gte-768-model-assets.sh`
- `scripts/deploy-gte-int8-embedding.sh`
- `scripts/diagnose-continuity-report-embedded-zero.sh`
- `scripts/quantize_gte_embedding_int8.py`

Related reports:

- `docs/reports/goal-c-u/2026-06-25-gte-embedder-flagday-acceptance-runbook.md`
- `docs/reports/goal-c-u/2026-06-25-gte-768-local-rehearsal.md`
- `docs/reports/goal-c-u/2026-06-25-gte-768-canonical-snapshot-gate.md`
- `docs/reports/goal-c-u/2026-06-25-gte-768-canonical-snapshot-rehearsal.md`
- `docs/reports/goal-c-u/2026-06-25-gte-768-live-maintenance-proposal.md`
- `docs/reports/goal-c-u/2026-06-25-gte-768-rollback-packet-draft.md`
- `docs/reports/goal-c-u/2026-06-25-gte-768-mac-live-migration-verification.md`
- `docs/reports/goal-c-u/2026-06-25-gte-768-aio2-live-migration-precheck.md`
- `docs/reports/goal-c-u/2026-06-25-gte-768-aio2-live-migration-result.md`
- `docs/reports/goal-c-u/2026-06-25-gte-768-aio2-final-authorization-packet.md`
- `docs/reports/goal-c-u/2026-06-25-gte-768-mac-stale-reader-cleanup.md`
- `docs/reports/goal-c-u/2026-06-25-gte-768-reader-compatibility-probe.md`
- `docs/reports/goal-c-u/2026-06-25-gte-768-case14-miss-review.md`
- `docs/reports/goal-c-u/2026-06-25-gte-768-owner-review-packet.md`

## Future Switch Gate

Only reopen a runtime switch if one of these facts changes:

- `schema_meta.version` is no longer `38`.
- active f32 embedding byte length is not exactly `3072`.
- active backend is not uniformly `gte-multilingual-base`.
- `continuity-report` shows stale vectors or unembedded active rows.
- MCP or daemon readers are pinned to an old binary.
- owner explicitly asks for a live migration, reindex, or rollback.

Before any future live mutation:

1. Capture a cold backup of `state.db`, `state.db-wal`, and `state.db-shm`
   when present.
2. Record `agent-bridge.real doctor --json` and
   `agent-bridge.real continuity-report --json`.
3. Run the GTE preflight and reader-compatibility probes.
4. Rehearse on a copied DB or canonical snapshot first.
5. Confirm recovery directory, rollback command sequence, and owner approval.

## Rollback Shape

If a future switch or reindex causes a regression:

1. Stop Agent-Bridge daemon and stale MCP readers.
2. Restore `state.db`, `state.db-wal`, and `state.db-shm` from the recovery
   directory captured immediately before mutation.
3. Restore the prior `agent-bridge.real` binary if the switch included a binary
   change.
4. Restart daemon/MCP processes.
5. Rerun `doctor`, `continuity-report`, and direct SQL checks for schema,
   backend, f32 byte length, and stale vectors.

For int8 shadow work specifically, use the rollback mode of
`scripts/deploy-gte-int8-embedding.sh` where applicable. That rollback does not
replace a full DB backup for dimension or backend migrations.

## Closure

`gte_runtime_switch_plan` is satisfied for the local node as a no-op runtime
decision: the desired runtime state already exists, and the safe future path is
captured through existing gate assets plus the rollback shape above.
