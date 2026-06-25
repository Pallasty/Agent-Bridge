# GTE 768 Canonical Snapshot Rehearsal

Date: 2026-06-25

Status: `REHEARSAL_COMPLETED_REVIEW_METRICS`.

Scope: record the SSH acquisition, fingerprint gate, scratch-only GTE reindex,
and `recall_eval` replay on the canonical frozen Mac snapshot. This is evidence
for owner review only. It does not authorize live DB mutation, live reindex,
deployment, runtime env changes, or production `memory_search` changes.

## Snapshot Acquisition

SMB was unavailable, so the snapshot was acquired over SSH through Tailscale:

```text
host=maxiaodeMac-Pro.local
ssh=pallasting@100.91.146.24
```

Canonical Mac source:

```text
/Users/pallasting/.local/share/agent-bridge/snapshots/state.snapshot.20260623.db
```

Mac source state:

```text
bytes=1150906368
sidecars=none
fingerprint=active=3022 edges=5527 newest=1782205313
```

The Mac `sqlite3 -readonly` path could not open this artifact without sidecar
handling, so the source was read with an immutable SQLite URI:

```text
file:$SNAP?mode=ro&immutable=1
```

Checkpointed export path on the Mac:

```text
/Users/pallasting/.cache/agent-bridge/snapshot-export/state.snapshot.20260623.checkpointed-for-aio2.db
```

Transferred aio2 artifact:

```text
/home/pallasting/.cache/agent-bridge/inbox/state.snapshot.20260623.checkpointed-for-aio2.db
bytes=1150906368
sha256=21b218ddc5d9d9a868520d2441df5bb0b7d3546dba68a28a4db509f0d34189ae
fingerprint=active=3022 edges=5527 newest=1782205313
```

## Gate Script Hardening

While verifying the received artifact, the old Python `mode=ro` fingerprint
open created SQLite sidecars beside the local copy. That violated the script's
discovery-only/no-write contract.

The script now opens explicit snapshots with:

```text
mode=ro&immutable=1
```

After removing the generated local sidecars, the gate was rerun and passed with
no warnings:

```text
status=READY_FOR_CANONICAL_REHEARSAL warnings=0
```

## Scratch Rehearsal

Command:

```bash
scripts/verify-gte-768-canonical-snapshot-gate.sh \
  --snapshot /home/pallasting/.cache/agent-bridge/inbox/state.snapshot.20260623.checkpointed-for-aio2.db \
  --expect-active 3022 \
  --expect-edges 5527 \
  --expect-newest 1782205313 \
  --run-rehearsal \
  --strict
```

Scratch path:

```text
/home/pallasting/.cache/agent-bridge/gte-rehearsal/2026-06-25T130030Z-canonical-snapshot-gate/state.db
```

Reindex result:

```text
model=gte-multilingual-base
reindexed=3022
status=DONE
scratch_sha256_after_reindex=47519355bf612c8061f489491ebb373dc9ce116740e144ef46999776b2c9f607
```

Logs:

```text
/home/pallasting/.cache/agent-bridge/gte-rehearsal/2026-06-25T130030Z-canonical-snapshot-gate/reindex.log
/home/pallasting/.cache/agent-bridge/gte-rehearsal/2026-06-25T130030Z-canonical-snapshot-gate/recall_eval.log
```

## Model Artifact Hashes

```text
model.onnx              5b9f03fdc40350a78fa064b4cfb6bf9a229a7c40aa87736f537e3ebd00aa2b86
tokenizer.json          3a56def25aa40facc030ea8b0b87f3688e4b3c39eb8b45d5702b3a1300fe2a20
config.json             6ef2538d4286a7cd18d05225f659d8a1bceca7adb01c186868e53dbd4f822e17
special_tokens_map.json 8c785abebea9ae3257b61681b4e6fd8365ceafde980c21970d001e834cf10835
tokenizer_config.json   24cebbf2ef20fc317256e03e52ac7b2ca326586f946a8427ecac036332bf0933
```

## Recall Metrics

Overall 18-case recall:

```text
mode       R@1    R@5    R@10   MRR
fts        0.278  0.556  0.667  0.366
hybrid     0.278  0.500  0.667  0.364
semantic   0.111  0.778  0.833  0.418
```

Runtime gate anchor, hard tier:

```text
hard-tier R@10: fts=0.375 fts+graph=0.375 hybrid=0.375 semantic=0.750
```

This clears the runbook's hard-tier direction threshold of `semantic R@10 >=
0.625` and is higher than same-run FTS/hybrid on the canonical snapshot.

Hard-tier review targets:

```text
#1  fts=- rows=0  fts+graph=- hybrid=- semantic=10
#2  fts=- rows=0  fts+graph=- hybrid=- semantic=3
#8  fts=- rows=10 fts+graph=- hybrid=- semantic=2
#9  fts=- rows=10 fts+graph=- hybrid=- semantic=2
#14 fts=- rows=10 fts+graph=- hybrid=- semantic=-
```

Remaining semantic misses:

```text
#5, #10, #14
```

The important remaining hard-tier miss is `#14`. It must be reviewed before any
owner packet claims production readiness.

Eval-only role-aware hard-family aggregate:

```text
mode                       n  R@1    R@5    R@10   MRR
strict_projected_families  2  0.000  0.500  1.000  0.300
role_aware_hard_families   2  1.000  1.000  1.000  1.000
```

Family ranks:

```text
#2 tool-surface   strict=2  role_aware=1
#8 remote-session strict=10 role_aware=1
```

## Decision

The canonical snapshot acquisition blocker is resolved for aio2, and the
scratch-only GTE replay reproduces the expected positive direction on the
canonical frozen baseline.

This still does not authorize live cut-over. The next artifact should be an
owner-review packet covering:

- exact snapshot and model hashes;
- hard-tier semantic benefit and remaining misses;
- reader compatibility mode for 384/768 coexistence or serialized cut-over;
- live migration sequence;
- rollback packet;
- final owner greenlight.

Until that owner-review packet lands, live GTE reindex and production runtime
switch remain `NO_GO`.
