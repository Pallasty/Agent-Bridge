# Correction Co-Surface MCP A/B Smoke

Date: 2026-07-01

Status: `EPHEMERAL_MCP_AB_SMOKE / COPIED_DB / LIVE_COSURFACE_STILL_DISABLED`

## Decision

Keep live default behavior unchanged in this slice.

Use a copied database and two one-off `agent-bridge.real mcp` subprocesses to
exercise the real MCP `memory_search` implementation with
`AGENT_BRIDGE_CORRECTION_COSURFACE` off and on. This validates the runtime tool
path without writing query/coactivation side effects into the live memory store
and without changing daemon or systemd configuration.

## Scope

Live source DB copied with SQLite backup API:

```text
/home/pallasting/.local/share/agent-bridge/state.db
```

Runtime binary:

```text
/home/pallasting/.local/bin/agent-bridge.real
```

Relevant edge:

```text
correction:session_handoff_present_voice_tts_subsystem_20260601:e8f0ab2032038682
  --corrects-->
session_handoff_present_voice_tts_subsystem_20260601
```

## Method

1. Create a temporary `XDG_DATA_HOME`.
2. Copy the live store into independent off/on temp DBs through SQLite backup.
3. Start one `agent-bridge.real mcp` subprocess with
   `AGENT_BRIDGE_CORRECTION_COSURFACE` unset.
4. Start one `agent-bridge.real mcp` subprocess with
   `AGENT_BRIDGE_CORRECTION_COSURFACE=1`.
5. Call MCP `memory_search` with `mode="fts"` for the same targeted queries.
6. Close both subprocesses and remove the temporary copied DBs.

Common bounded-test environment:

```text
AGENT_BRIDGE_TOOL_PROFILE=all
AGENT_BRIDGE_TOOLSET=all
AGENT_BRIDGE_CLIENT=codex-cosurface-ab-smoke
AGENT_BRIDGE_EMBED_BACKEND=hash
AGENT_BRIDGE_DIM_GUARD_STRICT=0
```

`AGENT_BRIDGE_EMBED_BACKEND=hash` and strict dim guard bypass were used only to
avoid local embedding model warmup for this FTS-only smoke. All calls explicitly
used `mode="fts"`, so semantic/vector behavior was outside this test.

Process result:

| Run | returncode | initialize ok | missing call ids | stderr |
|---|---:|---|---:|---|
| co-surface off | 0 | yes | 0 | empty |
| co-surface on | 0 | yes | 0 | empty |

## Results

| Query label | Limit | Exclude kinds | Off target | Off correction | On target | On correction | Effect |
|---|---:|---|---:|---:|---:|---:|---|
| exact target key | 10 | none | 1 | absent | 1 | 2 | correction inserted after original |
| `present_voice ab-tts Kokoro Piper TTS deployed aio2` | 10 | none | 1 | absent | 1 | 2 | correction inserted after original |
| `声音具身 present_voice ab-tts 训练流 Kokoro Piper` | 10 | none | 1 | absent | 1 | 2 | correction inserted after original |
| `present_voice ab-tts Kokoro Piper TTS deployed aio2` | 2 | none | 1 | absent | 1 | 2 | correction displaces tail within page size |
| exact target key | 1 | none | 1 | absent | 1 | absent | page stays size 1; correction cannot surface |
| exact target key | 10 | `feedback` | 1 | absent | 1 | absent | output filter preserved |
| `candle whisper-rs libclang present_voice handoff` | 10 | none | 4 | 1 | 3 | 1 | no duplicate; correction was already visible |

Representative key order:

```text
exact-target-limit10 off:
1 session_handoff_present_voice_tts_subsystem_20260601
2 correction_cosurface_live_backfill_preflight_20260701
3 work_memory_3d56857a5eed_codex-correction-cosurface-backfill-20260701_active

exact-target-limit10 on:
1 session_handoff_present_voice_tts_subsystem_20260601
2 correction:session_handoff_present_voice_tts_subsystem_20260601:e8f0ab2032038682
3 correction_cosurface_live_backfill_preflight_20260701

present-voice-limit2 off:
1 session_handoff_present_voice_tts_subsystem_20260601
2 deploy_piper_live_aio2_plus_say_review_20260603

present-voice-limit2 on:
1 session_handoff_present_voice_tts_subsystem_20260601
2 correction:session_handoff_present_voice_tts_subsystem_20260601:e8f0ab2032038682
```

## Finding

The real MCP `memory_search` path matches the earlier static shadow diff:

1. When the corrected original is already visible, enabling the env gate
   co-surfaces the active correction immediately after the original.
2. The original's rank remains stable.
3. `exclude_kinds=["feedback"]` prevents feedback corrections from surfacing.
4. `limit=1` does not grow the result page.
5. If the correction is already visible, co-surface does not duplicate it.

This is now evidence from the actual MCP stdio tool path, not only a direct SQL
replica.

## Boundary

This smoke did not:

- enable `AGENT_BRIDGE_CORRECTION_COSURFACE` in live Codex/Cursor MCP sessions;
- change daemon/systemd/wrapper env;
- restart or deploy any runtime process;
- write to the live memory DB;
- test semantic or hybrid search;
- sample broad organic queries.

## Next Gate

The remaining gate for default enablement is a time-bounded live-window or
runtime shadow window that observes real client searches, still with:

- before/after top-k diff capture;
- `limit=1`, `limit=2`, and `exclude_kinds=["feedback"]` checks;
- explicit rollback by unsetting `AGENT_BRIDGE_CORRECTION_COSURFACE` and
  reconnecting the affected MCP process.
