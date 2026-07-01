# Correction Co-Surface Copied-DB Extended Smoke

Date: 2026-07-01

Status: `SCRIPTED_COPIED_DB_SMOKE / PASS / LIVE_COSURFACE_DISABLED`

## Decision

Keep `AGENT_BRIDGE_CORRECTION_COSURFACE` disabled for long-lived live
Agent-Bridge processes.

The new reusable smoke script exercises the real MCP `memory_search` stdio path
against copied SQLite databases only. It extends the earlier copied-DB and S1
evidence from a single historical correction to all active live `corrects`
edges, without enabling S2 and without pointing the subprocesses at the live
store.

## What Landed

Script:

```text
scripts/verify-correction-cosurface-copied-db-smoke.sh
```

Default behavior:

- reads the live source DB only to `PRAGMA quick_check` and enumerate active
  `corrects` edges;
- copies the source DB into independent temporary off/on DBs with SQLite backup;
- starts two short-lived installed-binary MCP subprocesses;
- sets `AGENT_BRIDGE_DB` to the copied DB path for each subprocess;
- leaves `AGENT_BRIDGE_CORRECTION_COSURFACE` unset for the baseline subprocess;
- sets `AGENT_BRIDGE_CORRECTION_COSURFACE=1` only for the copied-DB enabled
  subprocess;
- calls MCP `memory_search(mode="fts")`;
- prints key/rank/kind evidence only, not memory content;
- removes the temp copied DBs unless `AB_KEEP_TMP=1`.

The script is parameterized by:

```text
AB_BIN
AB_SOURCE_DB
AB_MAX_CORRECTIONS
AB_KEEP_TMP
```

## Run

Command:

```text
scripts/verify-correction-cosurface-copied-db-smoke.sh > /tmp/ab-correction-cosurface-copied-db-smoke.json
```

Output artifact:

```text
/tmp/ab-correction-cosurface-copied-db-smoke.json
```

The JSON artifact is not committed. It contains memory keys and ranks only, not
raw memory content. Its full-file hash is intentionally not used as a stable
anchor because the artifact includes run timestamps and temp-path metadata.

## Result

Summary:

```json
{
  "status": "pass",
  "source_quick_check": "ok",
  "correction_edge_count": 5,
  "case_count": 20,
  "pass_count": 20,
  "fail_count": 0,
  "effects": {
    "inserted_after_original": 10,
    "limit_one_preserved": 5,
    "feedback_excluded": 5
  }
}
```

Edges covered:

| Correction key | Target key |
|---|---|
| `correction:agent_bridge_memory_authorization_contracts_20260625:0c4795435f1b72ec` | `agent_bridge_memory_authorization_contracts_20260625` |
| `correction:agent_bridge_shared_embedding_delegation_enabled_20260627:522e0cb357c6fecf` | `agent_bridge_shared_embedding_delegation_enabled_20260627` |
| `correction:gte_768_mac_stale_reader_cleanup_20260625:5f475856968723ad` | `gte_768_mac_stale_reader_cleanup_20260625` |
| `correction:gte_768_owner_review_packet_20260625:e302f3890bd69931` | `gte_768_owner_review_packet_20260625` |
| `correction:session_handoff_present_voice_tts_subsystem_20260601:e8f0ab2032038682` | `session_handoff_present_voice_tts_subsystem_20260601` |

Per edge, the script checked:

| Case | Expected property | Result |
|---|---|---|
| exact target key, limit 10 | enabled page inserts correction immediately after the target when baseline lacks the correction | pass for 5/5 |
| exact target key, limit 2 | enabled page can displace the tail while staying within limit | pass for 5/5 |
| exact target key, limit 1 | page remains length 1 and does not surface an extra correction | pass for 5/5 |
| exact target key, limit 10, `exclude_kinds=["feedback"]` | feedback correction does not surface | pass for 5/5 |

Representative first edge:

```text
exact_limit10:
  off target rank=1, off correction rank=absent
  on target rank=1, on correction rank=2

exact_limit2:
  off target rank=1, off correction rank=absent
  on target rank=1, on correction rank=2

exact_limit1:
  off target rank=1, off correction rank=absent
  on target rank=1, on correction rank=absent

exact_limit10_exclude_feedback:
  off target rank=1, off correction rank=absent
  on target rank=1, on correction rank=absent
```

## Board Read

Thread #102 had the S2 readiness decision post `2821` as the current
co-surface anchor. A later memory-pressure audit post `2823` noted a separate
systemd unit-permission hygiene follow-up. That follow-up is orthogonal to this
copied-DB co-surface smoke and was not mixed into this change.

Open `general` board read showed only threads #90 and #17 as open at the time
of this slice; no new co-surface runtime-enable request was observed.

## Interpretation

This strengthens the S0/S0.5 evidence line without widening runtime blast
radius:

- all active `corrects` edges behave as expected through real MCP stdio on DB
  copies;
- page-size truncation stays bounded;
- `exclude_kinds=["feedback"]` continues to block feedback corrections;
- no S2 daemon or active-client window is needed to answer the current
  correctness question.

The result does not prove organic live-user benefit. It supports keeping S2 as
a separate owner-gated runtime experiment if a future question needs that
broader evidence.

## Verification

```text
bash -n scripts/verify-correction-cosurface-copied-db-smoke.sh
git diff --check
scripts/verify-correction-cosurface-copied-db-smoke.sh
```

The script run passed with `20/20` cases.

## Boundary

This slice does not enable `AGENT_BRIDGE_CORRECTION_COSURFACE` in any live
long-lived process, restart daemons, deploy binaries, write the live memory DB,
write graph edges, change ranking policy, change MCP profiles, change tool
routing, or alter default retrieval behavior.
