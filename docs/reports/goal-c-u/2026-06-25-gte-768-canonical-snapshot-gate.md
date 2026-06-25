# GTE 768 Canonical Snapshot Gate

Date: 2026-06-25

Status: `SUPERSEDED_BY_CANONICAL_REHEARSAL_REPORT`.

Scope: add and validate a read-only gate for the next GTE/768 step: finding or
explicitly accepting a canonical frozen Mac snapshot before any scratch-copy
rehearsal that could be used as production cut-over evidence.

2026-06-25 update: the canonical snapshot was later acquired by SSH and replayed
successfully. Current result packet:
`docs/reports/goal-c-u/2026-06-25-gte-768-canonical-snapshot-rehearsal.md`.

## References Checked

Forum thread #105:

- #2548/#2549: GTE preflight script landed; no live DB mutation, no reindex, no
  env switch, no deploy.
- #2550: GTE local asset + scratch rehearsal landed; 492/492 active rows could
  be reindexed to `gte-multilingual-base` on a copy, but recall benefit was not
  reproduced, so production live cut-over remains `NO-GO`.

Memory/reports:

- `main_recall_readonly_snapshot_open_hardening_20260623`: `recall_eval` opens
  `AB_BASELINE_DB` using `SqliteStore::open_read_only` and prints the pinned
  snapshot mode.
- `main_recall_case2_production_review_packet_20260623`: future production
  claims must compare against the same pinned `AB_BASELINE_DB` fingerprint.
- `agent_bridge_gte_dimension_gate_anchor_289f962_20260624`: GTE flag-day is
  still a future plan, not live cut-over approval.

Local docs:

- `docs/reports/goal-c-u/2026-06-25-gte-768-local-rehearsal.md`: technical
  asset/reindex path verified, production cut-over still `NO-GO`, next gate is
  a replay on the canonical frozen Mac snapshot that produced earlier positive
  evidence.
- `docs/reports/goal-c-u/2026-06-23-gte-embedder-flagday-acceptance-runbook.md`:
  live cut-over requires copied-DB rehearsal, reader compatibility decision,
  serialized dual-node deployment, store invariants, and rollback packet.
- `docs/design/MEMORY_AUTHORIZATION_CONTRACTS_2026_06_25.md`: a design or
  review packet alone is not authority to mutate runtime or store state.

Reference implementations reused:

- `scripts/verify-gte-768-preflight.sh`
- `crates/store/examples/reindex_to_active_model.rs`
- `crates/bridge/examples/recall_eval.rs`
- `SqliteStore::open_read_only`

## Implementation

Added:

- `scripts/verify-gte-768-canonical-snapshot-gate.sh`

Default behavior is discovery-only:

- runs the existing GTE preflight unless `--skip-preflight` is set;
- inventories local DB candidates under the configured search roots;
- classifies live DB, scratch rehearsal products, local recovery snapshots, and
  canonical-looking names separately;
- refuses to treat the live DB as a source snapshot;
- reports local recovery snapshots as non-canonical by themselves;
- exits non-zero under `--strict` when no canonical source is available.

Opt-in rehearsal behavior:

```bash
scripts/verify-gte-768-canonical-snapshot-gate.sh \
  --snapshot /path/to/canonical/frozen/state.db \
  --expect-active 3022 \
  --expect-edges 5527 \
  --expect-newest 1782205313 \
  --run-rehearsal
```

When invoked this way, the script copies only the explicit snapshot into a
scratch directory, reindexes that copy with `AGENT_BRIDGE_ONNX_MODEL`, and runs
`recall_eval` against the reindexed copy via `AB_BASELINE_DB`.

It still refuses:

- the live DB as a source;
- a source snapshot with a non-empty WAL sidecar.

## Local Run

Command:

```bash
scripts/verify-gte-768-canonical-snapshot-gate.sh
```

Observed GTE preflight:

- live store active rows: 492;
- embedded rows: 483;
- dominant backend: `all-MiniLM-L6-v2`;
- stale vectors: 253 / 52.4%;
- GTE assets present;
- 4 live readers are not using GTE, which is OK for scratch rehearsal but not
  OK for live cut-over.

Local DB inventory:

```text
scratch_rehearsal_product
  /home/pallasting/.cache/agent-bridge/gte-rehearsal/2026-06-25T1148-full-gte/state.db
  sha256=fa646691eba92c7b247763bcea60a0eb249735267cbcdee94aa42909cbe48057

local_recovery_snapshot_not_canonical_by_itself
  /home/pallasting/.cache/agent-bridge/recovery/2026-06-22T1136/state.db
  sha256=2bdf5d9180951c01730b5732a0e9eabd12d8ad957d49ff7ffc915eb9a4d7fd9b

local_recovery_snapshot_not_canonical_by_itself
  /home/pallasting/.cache/agent-bridge/recovery/2026-06-22T1246/state.db
  sha256=8c0ef83627eb90e3961abf281bcf62bbe2173898fc748dfa1fdec60f16705204

local_recovery_snapshot_not_canonical_by_itself
  /home/pallasting/.cache/agent-bridge/recovery/2026-06-22T1306/state.db
  sha256=7db8bea3ac23104ae05ad1ccbd4f55e6568740748fcd6e0ec06c46d8ab70785a

local_recovery_snapshot_not_canonical_by_itself
  /home/pallasting/.cache/agent-bridge/recovery/2026-06-25T1148/state.db
  sha256=3e340b36fc0bf22893f7f22579b2fc5a2e7b830b8b7c3b6073090a6e50d802d5

live_store_do_not_use
  /home/pallasting/.local/share/agent-bridge/state.db
  sha256=8108e3b195b6d6e4f61c259ed71aefeb1a0b38d2f1f82f12b96ac86fe0ecf0d0
```

Verdict:

```text
status=NO_GO_CANONICAL_SNAPSHOT_MISSING warnings=0
```

## Verification

Commands:

```bash
bash -n scripts/verify-gte-768-canonical-snapshot-gate.sh
scripts/verify-gte-768-canonical-snapshot-gate.sh
scripts/verify-gte-768-canonical-snapshot-gate.sh --skip-preflight --strict
scripts/verify-gte-768-canonical-snapshot-gate.sh \
  --skip-preflight \
  --snapshot "$HOME/.local/share/agent-bridge/state.db" \
  --strict
scripts/verify-gte-768-canonical-snapshot-gate.sh \
  --skip-preflight \
  --snapshot "$HOME/.cache/agent-bridge/recovery/2026-06-25T1148/state.db"
```

Results:

- syntax check passed;
- default discovery reports `NO_GO_CANONICAL_SNAPSHOT_MISSING`;
- strict discovery exits `1`;
- live DB source exits `1` with `NO_GO_LIVE_STORE_SOURCE`;
- recovery snapshot source reports `NO_GO_SNAPSHOT_HAS_WAL` because the
  recovery DB has a non-empty WAL sidecar.

## Decision

Do not proceed to live GTE migration or live reindex.

The current node has:

- GTE model assets;
- a working technical reindex path on a copy;
- a local scratch GTE rehearsal result;
- local recovery snapshots.

It does not currently have:

- a canonical frozen Mac snapshot;
- reproduced recall benefit on that canonical snapshot;
- reader compatibility approval;
- dual-node cut-over plan;
- rollback packet;
- owner greenlight for live mutation.

## Next Gate

Bring or locate the canonical frozen Mac snapshot that produced the earlier
positive evidence, then run:

```bash
scripts/verify-gte-768-canonical-snapshot-gate.sh \
  --snapshot /path/to/canonical/frozen/state.db \
  --run-rehearsal
```

If the replay reproduces the earlier benefit, the next artifact should be an
owner-review packet naming the exact snapshot sha256, model artifact hashes,
candidate commit, reader compatibility mode, rollback packet, and minimum
acceptance thresholds.
