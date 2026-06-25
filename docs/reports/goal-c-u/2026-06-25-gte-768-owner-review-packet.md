# GTE 768 Owner Review Packet

Date: 2026-06-25

Schema: `agent_bridge.memory.gte_768.owner_review_packet.v0`

Status: `OWNER_REVIEW_READY_CASE14_ADJUDICATED / LIVE_CUTOVER_NO_GO`.

Scope: owner/reviewer packet for deciding whether the GTE 768 evidence is
strong enough to plan a live maintenance window. This packet does not approve
live DB mutation, live reindex, deployment, runtime env changes, or production
`memory_search` changes.

## Decision Stub

Recommended owner decision:

```json
{
  "owner_decision": "accept_canonical_rehearsal_as_evidence_only",
  "approved_mode": null,
  "approved_implementation_commit": null,
  "approved_runtime_surface": null,
  "live_gte_reindex_authorized": false,
  "live_db_mutation_authorized": false,
  "default_memory_search_change_authorized": false,
  "runtime_env_switch_authorized": false,
  "deploy_authorized": false,
  "rollback_confirmed": false
}
```

Allowed next slice if owner accepts this packet:

- docs-only live maintenance proposal;
- copied-DB reader compatibility probe;
- rollback packet draft.

Still blocked:

- running `reindex_to_active_model` on a live state DB;
- setting live readers to `AGENT_BRIDGE_ONNX_MODEL=gte-multilingual-base`;
- deploying a runtime switch;
- changing default `memory_search` behavior, ranking, schema, or MCP surface;
- memory/graph writes as part of this GTE lane.

## Evidence Under Review

Primary report:

```text
docs/reports/goal-c-u/2026-06-25-gte-768-canonical-snapshot-rehearsal.md
```

Code/report head:

```text
c782979 docs(memory): record GTE canonical rehearsal
```

Forum:

```text
design thread 105 post #2553
design thread 105 post #2554
```

Current local checkout:

```text
HEAD=origin/master=c782979
worktree=clean before this packet
```

Current installed binary on aio2:

```text
/home/pallasting/.local/bin/agent-bridge.real
sha256=cb76bf46963aa90dc496dad4ea7bd17e897be6525c9174e9449b40dacae147e7
doctor: ok=true fails=0 warns=0
```

Current live store/readers are not cut over:

```text
live_db=/home/pallasting/.local/share/agent-bridge/state.db
active_total=495
embedded=486
dominant_backend=all-MiniLM-L6-v2
stale_vectors=253
stale_frac=0.521
live readers using GTE=0
live readers not using GTE=4
```

This is acceptable for scratch evidence and explicitly not acceptable for live
cut-over.

## Snapshot And Model Identity

Canonical snapshot source:

```text
host=maxiaodeMac-Pro.local
ssh=pallasting@100.91.146.24
source=/Users/pallasting/.local/share/agent-bridge/snapshots/state.snapshot.20260623.db
```

Transferred aio2 artifact:

```text
/home/pallasting/.cache/agent-bridge/inbox/state.snapshot.20260623.checkpointed-for-aio2.db
bytes=1150906368
sha256=21b218ddc5d9d9a868520d2441df5bb0b7d3546dba68a28a4db509f0d34189ae
fingerprint=active=3022 edges=5527 newest=1782205313
```

Scratch reindexed DB:

```text
/home/pallasting/.cache/agent-bridge/gte-rehearsal/2026-06-25T130030Z-canonical-snapshot-gate/state.db
reindexed_rows=3022
scratch_sha256_after_reindex=47519355bf612c8061f489491ebb373dc9ce116740e144ef46999776b2c9f607
```

GTE model artifact hashes:

```text
model.onnx              5b9f03fdc40350a78fa064b4cfb6bf9a229a7c40aa87736f537e3ebd00aa2b86
tokenizer.json          3a56def25aa40facc030ea8b0b87f3688e4b3c39eb8b45d5702b3a1300fe2a20
config.json             6ef2538d4286a7cd18d05225f659d8a1bceca7adb01c186868e53dbd4f822e17
special_tokens_map.json 8c785abebea9ae3257b61681b4e6fd8365ceafde980c21970d001e834cf10835
tokenizer_config.json   24cebbf2ef20fc317256e03e52ac7b2ca326586f946a8427ecac036332bf0933
```

## Recall Result

Overall 18-case recall:

```text
mode       R@1    R@5    R@10   MRR
fts        0.278  0.556  0.667  0.366
hybrid     0.278  0.500  0.667  0.364
semantic   0.111  0.833  0.889  0.436
```

Main hard-tier runtime anchor:

```text
hard-tier R@10: fts=0.375 fts+graph=0.375 hybrid=0.375 semantic=0.875
```

Acceptance comparison:

- semantic clears the runbook threshold `>= 0.625`;
- semantic beats same-run FTS and hybrid on the hard tier;
- semantic also beats same-run FTS and hybrid at overall R@10;
- result is from the canonical frozen snapshot, not the smaller local aio2
  recovery DB.

Hard-tier review targets:

```text
#1  fts=- rows=0  fts+graph=- hybrid=- semantic=10
#2  fts=- rows=0  fts+graph=- hybrid=- semantic=3
#8  fts=- rows=10 fts+graph=- hybrid=- semantic=2
#9  fts=- rows=10 fts+graph=- hybrid=- semantic=2
#14 fts=- rows=10 fts+graph=- hybrid=- semantic=3
```

Remaining semantic misses:

```text
#5, #10
```

Case `#14` was content-read after the first owner-review packet. The semantic
rank-3 row `ab_memory_continuity_t5_t6_shadow_evidence_batch_20260619` is
also-correct because it explicitly states the T5 shadow packets were
`read_only=true`, `changes_memory_search_order=false`, and did not change actual
return order. See:
`docs/reports/goal-c-u/2026-06-25-gte-768-case14-miss-review.md`.

Eval-only role-aware hard-family aggregate:

```text
mode                       n  R@1    R@5    R@10   MRR
strict_projected_families  2  0.000  0.500  1.000  0.300
role_aware_hard_families   2  1.000  1.000  1.000  1.000
```

This aggregate is accepted as eval evidence only. It does not authorize a
runtime projection or default-search behavior change.

## Gate Status

Runbook gates:

| Gate | Status | Notes |
| --- | --- | --- |
| Candidate commit explicit | `PARTIAL` | GTE-capable code exists on master, but no owner-approved implementation commit is named for live cut-over. |
| Rehearsal uses a copy | `PASS` | Canonical snapshot was copied into scratch and only the scratch DB was reindexed. |
| Reader compatibility decided | `OPEN` | No owner decision yet. Default assumption should be `atomic_node_cutover_only`. |
| Dual-node deployment serialized | `OPEN` | No maintenance window or dual-node deploy plan yet. |
| Store invariants hold | `PASS_FOR_SCRATCH_ONLY` | Scratch store has 3022 GTE rows; live stores were not mutated. |
| Recall benefit reproduced | `PASS_FOR_CANONICAL_REHEARSAL` | after #14 adjudication, hard-tier semantic R@10 `0.875` vs FTS/hybrid `0.375`. |
| Post-reconnect surface current | `PASS_FOR_CURRENT_AIO2_STATE` | doctor `ok=true fails=0 warns=0`; live readers are still non-GTE. |

Current overall state:

```text
canonical_evidence_ready=true
live_cutover_ready=false
owner_live_authorization=false
```

## Reader Compatibility Recommendation

Do not assume mixed 384/768 readers are safe merely because scratch reindex
worked.

Recommended default for any future live proposal:

```text
reader_compatibility_mode=atomic_node_cutover_only
```

A future packet may choose `mixed_readers_supported` only if it proves, on copied
DBs and with both old/new binaries, that:

- a 768-capable reader can open a pre-reindex 384 store without corrupting rows;
- a 384-era reader never attaches to a store after 768 vectors are written;
- dim-guard warnings are visible and block unsafe mixed states;
- semantic search either skips incompatible rows safely or treats them as stale;
- no active reader silently falls back to hash vectors under a GTE backend tag.

Until that proof exists, live cut-over must stop clients, back up DBs, install
the approved binary, reindex one node at a time, then reconnect clients.

## Required Live Proposal Shape

The next docs-only proposal must name:

- exact implementation commit to deploy;
- exact binary sha256 per node after build/deploy;
- exact model artifact directory and hashes per node;
- Mac and aio2 live DB backup paths for DB, WAL, and SHM;
- client stop/reconnect procedure;
- explicit choice of `atomic_node_cutover_only` or a proven
  `mixed_readers_supported`;
- one-node-at-a-time migration sequence;
- pre/post SQL checks for backend tags and embedding byte lengths;
- post-reconnect `doctor --json` and capabilities checks;
- rollback commands and verification.

Minimum pre-live checks:

```bash
scripts/verify-gte-768-preflight.sh
scripts/verify-gte-768-canonical-snapshot-gate.sh \
  --snapshot /home/pallasting/.cache/agent-bridge/inbox/state.snapshot.20260623.checkpointed-for-aio2.db \
  --expect-active 3022 \
  --expect-edges 5527 \
  --expect-newest 1782205313 \
  --strict
```

Minimum post-scratch comparison before owner greenlight:

```bash
AB_BASELINE_DB=/path/to/copied/reindexed/state.db \
AGENT_BRIDGE_ONNX_MODEL=gte-multilingual-base \
cargo run -p ab-bridge --example recall_eval
```

## Rollback Requirements

Rollback must be prepared before any live 768 vectors are written.

Required rollback facts per node:

- live DB backup path;
- live WAL/SHM backup or explicit absence;
- old binary path and sha256;
- candidate binary path and sha256;
- pre-cutover `doctor --json`;
- pre-cutover backend distribution and vector byte-length distribution.

Rollback rule:

```text
never start an old 384 reader against a 768 live store
```

If rollback is needed after 768 vectors are written:

1. Stop MCP/daemon readers for the node.
2. Restore the 384 DB backup and matching WAL/SHM state.
3. Restore the old binary.
4. Reconnect readers.
5. Verify doctor is clean.
6. Verify the restored store has 384-compatible backend and byte-length
   distribution.

## Stop Conditions

Stop before live mutation if any are true:

- owner has not named an approved implementation commit;
- owner has not chosen reader compatibility mode;
- Mac or aio2 model artifact hash differs from this packet without review;
- `doctor --json` has fails or stale current MCP warnings;
- any old reader can attach to a store that will receive 768 vectors;
- live DB backup, WAL/SHM backup, or binary backup is missing;
- copied-DB reindex writes hash fallback vectors;
- post-reindex copied DB does not report GTE backend and 3072-byte embeddings
  for active semantic rows;
- recall_eval cannot confirm real GTE semantic mode;
- hard-tier semantic R@10 drops below `0.625` without owner-accepted drift
  explanation.

## Owner Questions

Owner/reviewer should decide:

1. Accept or reject canonical rehearsal as sufficient evidence to plan live
   maintenance.
2. Whether to accept the `#14` also-correct adjudication as sufficient for the
   GTE evidence review.
3. Exact implementation commit for a future live proposal.
4. Reader compatibility mode: `atomic_node_cutover_only` unless mixed mode is
   proved separately.
5. Whether Mac and aio2 must cut over in the same window or can serialize across
   windows.
6. Whether inactive/stale rows remain at old dimensions or are handled in a
   later migration.
7. Who owns rollback during the maintenance window.

## Decision

This packet is ready for owner review as an evidence bundle.

Recommended outcome:

```text
ACCEPT_EVIDENCE_ONLY / AUTHORIZE_DOCS_ONLY_LIVE_PROPOSAL / LIVE_GTE_NO_GO
```

No production change should occur until a later owner decision explicitly names
the implementation commit, compatibility mode, maintenance window, rollback
packet, and final live authorization.
