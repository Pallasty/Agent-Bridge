# Correction Co-Surface Shadow Diff

Date: 2026-07-01

Status: `READ_ONLY_SHADOW_DIFF / DEFAULT_FTS_ONLY / COSURFACE_STILL_DISABLED`

## Decision

Do not enable `AGENT_BRIDGE_CORRECTION_COSURFACE` in this slice.

Run a read-only shadow diff first, using the live store after the single-edge
backfill, to estimate what the gated co-surface read path would do on default
`memory_search` FTS result pages. The shadow shows the mechanism works for
queries that surface the corrected original, but the evidence is still a small
targeted slice, not a production enablement packet.

## Scope

Live store:

```text
/home/pallasting/.local/share/agent-bridge/state.db
```

Relevant edge:

```text
correction:session_handoff_present_voice_tts_subsystem_20260601:e8f0ab2032038682
  --corrects-->
session_handoff_present_voice_tts_subsystem_20260601
```

Read-only store facts during this shadow:

| Metric | Count |
|---|---:|
| active memories | 671 |
| active feedback corrections | 5 |
| `corrects` edges | 5 |
| candidate edge exists | 1 |

Runtime state:

- all visible `agent-bridge.real` processes lacked
  `AGENT_BRIDGE_CORRECTION_COSURFACE`;
- MCP lifecycle remained `ready`;
- readiness warnings remained `0`;
- failing tool count remained `0`.

## Method

The shadow did not call MCP `memory_search` and did not set the co-surface env
flag. It used Python's standard `sqlite3` module against the live DB in
read-only mode.

The replica covered the default FTS path sufficiently for this targeted check:

- FTS5 `MATCH` over `memories_fts`;
- plain-query token prefixing similar to `sanitise_fts_query`;
- OR fallback when implicit-AND produced no rows;
- exact-key fallback;
- FTS score blend:
  `max(-bm25, 0) + memory_score + 0.5 * importance + feedback_kind_boost`;
- visible-page coactivation rerank;
- B1 co-surface insertion:
  if a visible result is the target of an inbound active `corrects` edge, insert
  the active correction immediately after it, unless already present, then
  truncate back to page size.

This is not a full runtime equivalence proof. It intentionally excludes:

- semantic mode;
- hybrid mode;
- MCP telemetry side effects;
- live daemon env changes;
- broad user-query sampling.

## Targeted Query Results

Limit was 10 unless otherwise noted.

| Query label | Baseline target rank | Baseline correction rank | Shadow correction rank | Effect |
|---|---:|---:|---:|---|
| exact target key | 1 | absent | 2 | inserted after original |
| `present_voice ab-tts Kokoro Piper TTS deployed aio2` | 1 | absent | 2 | inserted after original |
| `声音具身 present_voice ab-tts 训练流 Kokoro Piper` | 1 | absent | 2 | inserted after original |
| `candle whisper clang STT engine` | absent | absent | absent | no effect |
| `candle whisper-rs libclang present_voice handoff` | 4 | 1 | 1 | no duplicate; correction already visible |
| `whisper.cpp candle pure Rust STT verification` | 3 | 1 | 1 | no duplicate; correction already visible |
| `声音具身 present_voice STT candle clang` | absent | absent | absent | no effect |

Interpretation:

- For original-focused queries, co-surface fixes the problematic shape:
  the stale or incomplete original would no longer appear without its correction.
- For correction-focused queries, the correction already ranks first; co-surface
  correctly does not duplicate it.
- For queries that do not surface the original or correction, co-surface is a
  no-op.

## Guardrails

`exclude_kinds=["feedback"]`:

```text
baseline == shadow
inserted = []
```

This preserves the output-filter contract.

Small page size:

| Case | Baseline | Shadow | Effect |
|---|---|---|---|
| limit=2 target-title query | original, deploy report | original, correction | correction displaces tail |
| limit=1 exact target key | original | original | correction inserted internally but truncated away |

This matches the implementation contract: co-surface does not grow the page; it
displaces the weakest tail result when there is room, and cannot be visible when
the caller asks for only one row.

## Finding

The backfilled edge is behaviorally useful under the gated B1 design:

1. It has no global ranking effect.
2. It only acts when the corrected original is already visible.
3. It keeps the original's rank stable and inserts the correction directly
   after it.
4. It avoids duplicate insertion when the correction is already visible.
5. It respects `exclude_kinds`.

The main limitation is exposure: with `limit=1`, the correction cannot surface.
That is expected and should be documented if the env gate is ever enabled.

## Recommendation

The next safe step, if owner-approved, is not broad default enablement. Use a
short shadow or A/B window:

1. enable `AGENT_BRIDGE_CORRECTION_COSURFACE=1` only in a controlled process or
   time-bounded daemon window;
2. log before/after top-k diffs for searches that hit corrected originals;
3. include at least `limit=1`, `limit=2`, and `exclude_kinds=["feedback"]`
   checks;
4. verify no unexpected correction duplication or page growth;
5. then decide whether to keep the flag enabled.

## Boundary

This report did not:

- enable `AGENT_BRIDGE_CORRECTION_COSURFACE`;
- restart daemons;
- deploy;
- write live DB rows;
- call MCP `memory_search`;
- change ranking weights;
- change default retrieval behavior.
