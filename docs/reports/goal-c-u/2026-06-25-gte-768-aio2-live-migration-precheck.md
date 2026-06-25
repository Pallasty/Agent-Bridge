# GTE 768 aio2 Live Migration Precheck

Date: 2026-06-25

Status: `AIO2_ENV_HEALTHY / LIVE_READER_MISMATCH_NO_GO`.

Scope: read-only aio2 precheck after Mac GTE migration and stale-reader cleanup.
This report records current aio2 state only. It does not authorize live DB
mutation, live reindex, reader stop/reconnect, deployment, runtime env changes,
or production `memory_search` changes.

## Summary

aio2 runtime health is clean, but live migration is not yet allowed because
current live readers are not using GTE:

```text
doctor_ok=true
doctor_fails=0
doctor_warns=0
preflight_status=NO_GO_LIVE_READER_MISMATCH
live_readers_not_using_gte=4
```

The next safe gate is a final owner authorization packet that names the exact
maintenance window, write freeze, reader stop/reconnect plan, backups, rollback
owner, and go/no-go checkboxes.

## Current aio2 Store

Direct SQL:

```text
db=/home/pallasting/.local/share/agent-bridge/state.db
active_total=502
embedded=493
null_or_empty=9
gte_good=0
old_or_non_gte_active_embedded=493
```

Active embedding buckets:

```text
backend=unknown bytes=1536 dim=384 rows=244
backend=all-MiniLM-L6-v2 bytes=1536 dim=384 rows=240
backend=fnv1a-hash-384 bytes=1536 dim=384 rows=9
```

`continuity-report` summary:

```text
active_total=502
embedded=493
dominant_backend=all-MiniLM-L6-v2
dominant_count=240
stale_vectors=253
stale_frac=0.513
```

## Current aio2 Runtime

Doctor:

```text
ok=true
fails=0
warns=0
mcp_servers=2 MCP server(s) - all executing current agent-bridge.real
```

GTE model asset preflight:

```text
model.onnx OK
tokenizer.json OK
config.json OK
special_tokens_map.json OK
tokenizer_config.json OK
asset-manifest.txt present
```

Live reader inventory from `scripts/verify-gte-768-preflight.sh --live-cutover
--strict`:

```text
pid=2924 model=<unset> model_dir=<unset> cmd=/home/pallasting/.local/bin/agent-bridge.real daemon
pid=2925 model=<unset> model_dir=<unset> cmd=/home/pallasting/.local/bin/agent-bridge.real daemon-http --listen 0.0.0.0:7878
pid=566419 model=<unset> model_dir=<unset> cmd=/home/pallasting/.local/bin/agent-bridge.real mcp
pid=567010 model=<unset> model_dir=<unset> cmd=/home/pallasting/.local/bin/agent-bridge.real mcp
```

Preflight verdict:

```text
status=NO_GO_LIVE_READER_MISMATCH
warnings=0
```

## Decision

Do not run aio2 live reindex yet.

Required next gate:

- final owner authorization packet;
- memory write freeze;
- stop aio2 live readers or launch a controlled maintenance process isolated
  from current readers;
- capture DB/WAL/SHM and binary backups;
- run live reindex under explicit GTE env;
- verify 3072-byte `gte-multilingual-base` rows before reconnecting readers;
- reconnect only current GTE-capable readers;
- run doctor, direct SQL, and recall checks.
