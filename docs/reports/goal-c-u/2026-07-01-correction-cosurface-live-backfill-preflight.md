# Correction Co-Surface Live Backfill Preflight

Date: 2026-07-01

Status: `READ_ONLY_PREFLIGHT / ONE_EDGE_BACKFILL_CANDIDATE / NO_LIVE_WRITE`

## Decision

Do not enable `AGENT_BRIDGE_CORRECTION_COSURFACE` and do not backfill live
edges in this slice.

The current master already contains the correction co-surface code path, but it
is default-off. A read-only live-store preflight found exactly one active
correction row that has a valid target and is missing its `corrects` edge. This
is a small, concrete owner-gated follow-up, not an automatic maintenance write.

## Current Code State

Correction co-surface is already landed on `origin/master` through PR #36:

- A1 write path: `memory_save` auto-links new out-of-tool
  `correction:<target>:*` feedback rows to `related_keys[0]` with a `corrects`
  edge when the target exists.
- B1 read path: `memory_search` can co-surface active correction rows directly
  after originals they correct.
- B1 is gated by `AGENT_BRIDGE_CORRECTION_COSURFACE`.
- Default OFF keeps normal output unchanged.
- Co-surfaced rows still honor `exclude_kinds`.

The prior closeout report is:

- `docs/reports/goal-c-u/2026-07-01-correction-cosurface-link-review.md`

## Verification Replayed On Current Head

Current head during this preflight:

```text
6066864 docs(agent): record kilo first-prompt verification
```

Effective tests:

```text
CARGO_BUILD_JOBS=1 cargo test -p ab-store \
  a1_memory_save_auto_links_corrects_edge_for_out_of_tool_correction \
  -- --nocapture
```

Result: passed, 1/1.

```text
CARGO_BUILD_JOBS=1 cargo test -p ab-bridge --no-default-features \
  b1_cosurface_inserts_corrector_after_corrected_original \
  -- --nocapture
```

Result: passed, 1/1.

Observed warnings were existing compiler warnings, including the mixed-script
confusable warning in `ab-store` and private/dead-code warnings in `ab-bridge`.

## Live Store Preflight

Database:

```text
/home/pallasting/.local/share/agent-bridge/state.db
```

Access mode:

```text
file:/home/pallasting/.local/share/agent-bridge/state.db?mode=ro&immutable=1
```

The host does not currently have the `sqlite3` CLI installed, so the query used
Python's standard `sqlite3` module in read-only immutable mode.

Counts:

| Metric | Count |
|---|---:|
| active memories | 664 |
| active feedback corrections | 5 |
| existing `corrects` edges | 4 |
| missing valid correction edges | 1 |

Per-correction edge state:

| Correction key | Target key | Target status | `corrects` edge |
|---|---|---|---|
| `correction:agent_bridge_shared_embedding_delegation_enabled_20260627:522e0cb357c6fecf` | `agent_bridge_shared_embedding_delegation_enabled_20260627` | active | present |
| `correction:agent_bridge_memory_authorization_contracts_20260625:0c4795435f1b72ec` | `agent_bridge_memory_authorization_contracts_20260625` | active | present |
| `correction:gte_768_mac_stale_reader_cleanup_20260625:5f475856968723ad` | `gte_768_mac_stale_reader_cleanup_20260625` | active | present |
| `correction:gte_768_owner_review_packet_20260625:e302f3890bd69931` | `gte_768_owner_review_packet_20260625` | active | present |
| `correction:session_handoff_present_voice_tts_subsystem_20260601:e8f0ab2032038682` | `session_handoff_present_voice_tts_subsystem_20260601` | active | missing |

## Backfill Candidate

Only one row is a valid backfill candidate:

```text
correction:session_handoff_present_voice_tts_subsystem_20260601:e8f0ab2032038682
  --corrects-->
session_handoff_present_voice_tts_subsystem_20260601
```

Why it qualifies:

- correction row is active;
- kind is `feedback`;
- key starts with `correction:`;
- `related_keys[0]` points at an existing target;
- target is active;
- no `corrects` edge currently exists.

This likely predates the A1 write-path auto-link behavior.

## Owner-Gated Backfill Shape

If the owner chooses to backfill, the intended blast radius is one idempotent
edge upsert:

```sql
INSERT INTO memory_edges (from_key, to_key, edge_type, weight, created_at)
SELECT
  'correction:session_handoff_present_voice_tts_subsystem_20260601:e8f0ab2032038682',
  'session_handoff_present_voice_tts_subsystem_20260601',
  'corrects',
  1.4,
  CAST(strftime('%s','now') AS INTEGER)
WHERE EXISTS (
  SELECT 1 FROM memories
  WHERE key = 'correction:session_handoff_present_voice_tts_subsystem_20260601:e8f0ab2032038682'
    AND status = 'active'
    AND kind = 'feedback'
)
AND EXISTS (
  SELECT 1 FROM memories
  WHERE key = 'session_handoff_present_voice_tts_subsystem_20260601'
)
ON CONFLICT(from_key, to_key, edge_type)
DO UPDATE SET weight = excluded.weight;
```

Prefer using the store `memory_link` path if it is exposed in the operator's
tool profile during the maintenance slice. In this Codex tool profile,
`memory_link` is not currently exposed, so raw SQL should remain an explicit
maintenance action rather than an incidental agent write.

## Enablement Boundary

Do not combine the backfill with enabling `AGENT_BRIDGE_CORRECTION_COSURFACE`.
They should be separate owner decisions:

1. Backfill the one missing `corrects` edge.
2. Run a short A/B or shadow window with `AGENT_BRIDGE_CORRECTION_COSURFACE=1`.
3. Inspect before/after top-k diffs for correction targets.
4. Only then decide whether to keep the env flag enabled.

## Non-Authorizations

This preflight does not authorize:

- live DB writes;
- environment changes;
- daemon restart;
- deployment;
- default `memory_search` behavior changes;
- semantic or FTS ranking-weight changes;
- graph hygiene beyond the single named correction edge;
- broad correction-edge inference from key parsing alone.

## Recommended Next Step

Post this preflight to the board as the owner review packet. If approved, run a
single-row maintenance backfill and record a post-backfill read-only verification
before any co-surface A/B enablement.
