# GTE 768 Mac Live Migration Verification

Date: 2026-06-25

Status: `MAC_FULL_GTE_VERIFIED / STALE_READERS_CLEARED / DUAL_NODE_LIVE_CUTOVER_NO_GO`.

Scope: read-only verification after the user completed the Mac-side full GTE
768 migration. This report records observed state only. It does not authorize
aio2 live DB mutation, reader reconnect, deployment, runtime env changes, or
production `memory_search` changes.

## Summary

Mac live memory state is fully migrated to GTE 768 by direct SQL invariants:

```text
host=maxiaodeMac-Pro.local
ssh=pallasting@100.91.146.24
live_db=/Users/pallasting/Library/Application Support/agent-bridge/state.db
active_total=3248
embedded=3248
null_or_empty=0
gte_good=3248
gte_bad_dim=0
old_or_non_gte_active_embedded=0
dominant_backend=gte-multilingual-base
dominant_bytes=3072
dominant_dim=768
```

Dual-node cut-over remains `NO_GO` because aio2 is not migrated. The Mac stale
MCP reader blocker was cleared in:

```text
docs/reports/goal-c-u/2026-06-25-gte-768-mac-stale-reader-cleanup.md
```

## Mac Direct SQL Evidence

Observed active embedding buckets:

```text
backend=gte-multilingual-base bytes=3072 dim=768 rows=3248
```

Observed memory status distribution:

```text
active=3248
tombstoned=2694
archived=442
superseded=145
```

DB sidecar hashes at verification time:

```text
state.db     bytes=1237393408 sha256=f260919c5751f443fbdf982348f19de682a10b42dd37e6601174ac66387d655f
state.db-wal bytes=83747272   sha256=481d4596b829cb28c1b04fa456b760b208a6afb127b6c1e5c34dd433628c22f6
state.db-shm bytes=98304      sha256=e92580d2a081e5ddb7768b44a894c85b9eb628bd388542bb17472cd29177c510
```

The Mac `~/.local/share/agent-bridge` path is a symlink to:

```text
/Users/pallasting/Library/Application Support/agent-bridge
```

## Mac Runtime Surface

Installed binary:

```text
path=/Users/pallasting/.local/bin/agent-bridge.real
sha256=886da427f62726472f67972b31bad960fc0d16a093a287a3dd068f9439eabf69
```

Doctor summary after stale-reader cleanup:

```text
ok=true
fails=0
warns=2
```

Warnings observed:

- `/Users/pallasting/.local/bin/ab-system-control` is missing.
- desktop runtime `system_control` is missing.

The desktop-helper warnings are not GTE vector blockers. Post-cleanup doctor
reported `3 MCP server(s) - all executing current agent-bridge.real`.

## Model Artifacts

Core GTE model hashes match aio2:

```text
model.onnx              5b9f03fdc40350a78fa064b4cfb6bf9a229a7c40aa87736f537e3ebd00aa2b86
tokenizer.json          3a56def25aa40facc030ea8b0b87f3688e4b3c39eb8b45d5702b3a1300fe2a20
config.json             6ef2538d4286a7cd18d05225f659d8a1bceca7adb01c186868e53dbd4f822e17
special_tokens_map.json 8c785abebea9ae3257b61681b4e6fd8365ceafde980c21970d001e834cf10835
tokenizer_config.json   24cebbf2ef20fc317256e03e52ac7b2ca326586f946a8427ecac036332bf0933
```

Mac still lacks `asset-manifest.txt`. This is not a core-model hash mismatch,
but the final acceptance packet should either install the manifest or explicitly
waive it.

## Continuity Report Discrepancy

Mac `continuity-report --json` reported:

```text
active_total=3248
embedded=0
```

That contradicts direct SQL, which shows all 3248 active rows have non-empty
3072-byte `gte-multilingual-base` embeddings. Treat direct SQL as the current
DB invariant and track the continuity-report discrepancy as a follow-up before
final acceptance.

## aio2 Contrast

aio2 remains unmigrated:

```text
live_db=/home/pallasting/.local/share/agent-bridge/state.db
active_total=500
embedded=491
null_or_empty=9
gte_good=0
old_or_non_gte_active_embedded=491
doctor_ok=true
doctor_fails=0
doctor_warns=0
```

Observed aio2 active embedding buckets:

```text
backend=unknown bytes=1536 dim=384 rows=244
backend=all-MiniLM-L6-v2 bytes=1536 dim=384 rows=238
backend=fnv1a-hash-384 bytes=1536 dim=384 rows=9
```

## Decision

Mac migration is verified by DB invariants.

Overall live cut-over remains blocked:

- aio2 has not been migrated to GTE 768;
- Mac `continuity-report` disagrees with direct SQL and should be corrected or
  explicitly waived before final acceptance.

Recommended next action: decide whether to authorize aio2 live migration as a
separate one-node maintenance step, while tracking the Mac continuity-report
discrepancy as a follow-up.
