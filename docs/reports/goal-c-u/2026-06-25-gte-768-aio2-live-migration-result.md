# GTE 768 aio2 Live Migration Result

Date: 2026-06-25
Node: `pallasting-ThinkBook-14-G5-IRH` / aio2
Scope: one-node live migration to `gte-multilingual-base` only.

## Result

aio2 is live on `gte-multilingual-base` with active memory embeddings fully
reindexed to 768 dimensions.

Final installed binary:

- `/home/pallasting/.local/bin/agent-bridge.real`
- SHA-256: `db0d0e9f59893f42174b16b4c226e7a037374a84929df0f13ccb0ec460e9bde3`

Backup created before live mutation:

- `/home/pallasting/.local/share/agent-bridge/backups/gte-768-aio2-20260625T161024Z`
- Original binary SHA-256: `cb76bf46963aa90dc496dad4ea7bd17e897be6525c9174e9449b40dacae147e7`
- Original `state.db` SHA-256: `82550554d863a75d87033fa1d6b0034c33282befa7b52a6ed1624a8d6f47e5bc`

## Live DB Verification

Final direct SQL check:

- `active_total=504`
- `embedded=504`
- `null_or_empty=0`
- `gte_good=504`
- `gte_bad_dim=0`
- `old_or_non_gte_active_embedded=0`
- Active bucket: `gte-multilingual-base`, `3072` bytes, `768` dim, `504` rows

Final continuity/preflight:

- `active_total=504`
- `embedded=504`
- `dominant_backend=gte-multilingual-base`
- `dominant_count=504`
- `stale_vectors=0`
- `stale_frac=0.000`
- `scripts/verify-gte-768-preflight.sh --live-cutover --strict --ab-bin /home/pallasting/.local/bin/agent-bridge`
  returned `READY_FOR_SCRATCH_REHEARSAL warnings=0`.

Live readers verified with GTE env:

- daemon: `AGENT_BRIDGE_ONNX_MODEL=gte-multilingual-base`
- daemon-http: `AGENT_BRIDGE_ONNX_MODEL=gte-multilingual-base`
- palace: `AGENT_BRIDGE_ONNX_MODEL=gte-multilingual-base`

## Runtime Fixes Applied

The first post-cutover daily hygiene run exposed a one-row stale backend tag:

- `snapshot_daily_20260625_1621`
- vector length was already 768 dim, but `embedding_backend=fnv1a-hash-384`

Root cause: short-lived writer commands can start while the ONNX model is still
warming; the write path correctly labels the temporary hash fallback as
`fnv1a-hash-384`, leaving a row for stale reindex to repair.

Fixes:

- `memory_save` now waits briefly when a non-hash backend returns a cold hash
  fallback, then retries after model initialization settles.
- `memory_import` uses the same cold-fallback retry path.
- `memory_import` now stamps `embedding_backend` on insert/update/conflict-copy.
- `memory_import` embeds in bounded chunks controlled by
  `AGENT_BRIDGE_MEMORY_IMPORT_EMBED_BATCH_SIZE` (default 16).
- `memory_import` skips immediate embedding for non-active imported rows; those
  rows are not used by semantic search and can be embedded if restored later.

Systemd template fixes:

- `agent-bridge-sync.service` uses wrapper `agent-bridge`, not `.real`.
- `agent-bridge-memory-decay-unused.service` uses wrapper `agent-bridge`, not `.real`.
- `agent-bridge-sync.service` sets
  `AGENT_BRIDGE_MEMORY_IMPORT_EMBED_BATCH_SIZE=8`.
- `agent-bridge-sync.service` has `TimeoutStartSec=900`.

The local user units under `~/.config/systemd/user/` were updated and
`systemctl --user daemon-reload` was run.

## Sync/Daily Verification

Observed failure modes during validation:

- pre-fix sync OOM-killed at `9.3G` peak.
- chunked sync avoided OOM but hit old `TimeoutStartSec=120` at `4.9G` peak.
- final optimized sync completed successfully in about `26s`, with `500.5M`
  peak memory.
- timer-triggered sync completed successfully in about `23s`, with `479.2M`
  peak memory.

Sync pushes after final fixes:

- `89ff8d9` at `2026-06-25T17:02:11Z`
- `bb720e7` at `2026-06-25T17:03:08Z`

Daily hygiene after wrapper fix completed successfully, including
`dream snapshot --name daily`. The new daily snapshots are GTE-tagged.

Timers after verification:

- `agent-bridge-sync.timer`: active/waiting
- `agent-bridge-memory-decay-unused.timer`: active/waiting

## Tests

Passed:

- `CARGO_BUILD_JOBS=2 cargo test -p ab-store memory_import_ -- --nocapture`
- `CARGO_BUILD_JOBS=2 cargo test -p ab-store memory_reindex_only_stale -- --nocapture`
- `CARGO_BUILD_JOBS=2 cargo build --release -p ab-bridge --bin agent-bridge`

Warnings observed are pre-existing Rust warnings, including
`mixed_script_confusables` and bridge dead-code/private-interface warnings.

## Residual Note

Systemd emitted non-fatal warnings while starting one-shot services:

- `Failed to add ... inotify watch descriptor ... No space left on device`

The services still completed successfully. Current kernel inotify values:

- `fs.inotify.max_user_watches=126720`
- `fs.inotify.max_user_instances=128`
- `fs.inotify.max_queued_events=16384`

Treat this as a follow-up host tuning item if the warning recurs.
