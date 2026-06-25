# GTE 768 aio2 Final Authorization Packet

Date: 2026-06-25

Status: `AUTHORIZED_FOR_AIO2_ONE_NODE_LIVE_MIGRATION`.

Scope: final operator authorization and execution contract for migrating aio2
only from 384-era active memory embeddings to `gte-multilingual-base` 768-dim
embeddings. This packet does not authorize Mac rollback, mixed-reader mode,
default ranking changes, schema changes, or production `memory_search` behavior
changes beyond using the migrated store and GTE runtime env.

## Authorization

Operator authorization source:

```text
2026-06-25 user message: "授权你按照自己的思路操作。"
```

Authorized booleans:

```json
{
  "owner_decision": "authorize_aio2_one_node_gte_live_migration",
  "approved_mode": "atomic_node_cutover_only",
  "approved_implementation_commit": "81896a87b0312917899a23efee25b38170d2a923",
  "approved_runtime_surface": "aio2 local Agent-Bridge daemon/daemon-http/MCP readers only",
  "live_gte_reindex_authorized": true,
  "live_db_mutation_authorized": true,
  "runtime_env_switch_authorized": true,
  "deploy_authorized": true,
  "default_memory_search_change_authorized": false,
  "mixed_reader_mode_authorized": false,
  "mac_mutation_authorized": false,
  "rollback_confirmed": true
}
```

## Pre-Migration Facts

Source and binary:

```text
repo=/Data/CascadeProjects/agent-bridge
repo_head=81896a87b0312917899a23efee25b38170d2a923
old_binary=/home/pallasting/.local/bin/agent-bridge.real
old_binary_sha256=cb76bf46963aa90dc496dad4ea7bd17e897be6525c9174e9449b40dacae147e7
candidate_binary=/Data/CascadeProjects/agent-bridge/target/release/agent-bridge
candidate_binary_sha256=d8387cb8f4a125ad01f9454a2b0abdb4444bbada0872e1f831c4e02fc120fa66
candidate_binary_bytes=67220984
```

aio2 live DB before migration:

```text
live_db=/home/pallasting/.local/share/agent-bridge/state.db
active_total=503
embedded=494
null_or_empty=9
gte_good=0
old_or_non_gte_active_embedded=494
```

GTE model env to install:

```text
AGENT_BRIDGE_ONNX_MODEL=gte-multilingual-base
AGENT_BRIDGE_ONNX_MODEL_DIR=/home/pallasting/.cache/agent-bridge/onnx-models
```

GTE model assets:

```text
model.onnx OK
tokenizer.json OK
config.json OK
special_tokens_map.json OK
tokenizer_config.json OK
asset-manifest.txt present
```

Precheck blocker being intentionally resolved by this maintenance window:

```text
preflight_status=NO_GO_LIVE_READER_MISMATCH
reason=4 live readers were still running without AGENT_BRIDGE_ONNX_MODEL=gte-multilingual-base
```

## Backup Plan

Backup directory:

```text
/home/pallasting/.local/share/agent-bridge/backups/gte-768-aio2-20260625T161024Z
```

Required backup files:

```text
state.db
state.db-wal
state.db-shm
agent-bridge.real
machine.env
```

Rollback owner:

```text
codex:gpt-5:aio2-gte-live-migration-20260625
```

Rollback rule:

```text
never start an old 384-era reader against a 768 live store
```

If rollback is needed:

1. Stop aio2 MCP/daemon/daemon-http/palace readers.
2. Restore the backup DB/WAL/SHM.
3. Restore the backup `agent-bridge.real`.
4. Restore or remove the GTE entries in `machine.env`.
5. Restart services/readers under the restored 384-era runtime.
6. Verify doctor and backend/byte-length distribution before resuming writes.

## Execution Plan

1. Commit and push this authorization packet.
2. Enter write freeze by stopping aio2 systemd services/timers and MCP readers:
   `agent-bridge-daemon.service`, `agent-bridge-daemon-http.service`,
   `agent-bridge-palace.service`, `agent-bridge-sync.timer`,
   `agent-bridge-memory-decay-unused.timer`, and live `agent-bridge.real mcp`
   processes.
3. Confirm no live `agent-bridge.real daemon|daemon-http|mcp|palace` readers
   have DB handles open.
4. Copy DB/WAL/SHM, old binary, and `machine.env` to the backup directory and
   record sha256 hashes.
5. Install candidate binary to `/home/pallasting/.local/bin/agent-bridge.real`.
6. Add GTE env defaults to `/home/pallasting/.config/agent-bridge/machine.env`
   using guarded exports.
7. Run live reindex with explicit GTE env:

```bash
AGENT_BRIDGE_ONNX_MODEL=gte-multilingual-base \
AGENT_BRIDGE_ONNX_MODEL_DIR=/home/pallasting/.cache/agent-bridge/onnx-models \
cargo run -p ab-store --example reindex_to_active_model -- \
  /home/pallasting/.local/share/agent-bridge/state.db
```

8. Verify direct SQL reports all active embedded rows as
   `gte-multilingual-base` with byte length `3072`.
9. Restart daemon, daemon-http, palace, sync timer, and memory decay timer.
10. Allow MCP clients to reconnect under wrapper-injected GTE env.
11. Run `doctor --json`,
    `scripts/verify-gte-768-preflight.sh --live-cutover --strict`, direct SQL,
    and `recall_eval`.
12. Record post-migration report, board post, and memory.

## Stop Conditions

Stop and do not mutate the live DB if any are true before reindex:

- backup directory cannot be created;
- DB/WAL/SHM or binary backup is missing;
- candidate binary hash differs from this packet;
- model assets are missing;
- live readers keep respawning without GTE env before the reindex starts;
- old DB handles remain open after stop commands;
- reindex warmup reports hash fallback or aborts.

Stop and roll back if any are true after reindex:

- active GTE rows have byte length other than `3072`;
- any active embedded row remains non-GTE without an explicit waiver;
- `doctor --json` reports fails;
- live-cutover preflight reports reader mismatch after reconnect;
- semantic recall cannot run under real GTE mode.
