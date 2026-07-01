# Correction Co-Surface S1 Closeout

Date: 2026-07-01

Status: `S1_LIVE_SUBPROCESS_TRIAL / PASS / LONG_LIVED_COSURFACE_DISABLED`

## Decision

Run the live-store S1 child-process trial under the standing reversible
operations authorization.

S0.5 had already exercised the real installed-binary MCP stdio `memory_search`
path against copied databases, with `AGENT_BRIDGE_CORRECTION_COSURFACE` off and
on. S1 adds one narrower live-store check: the same short-lived subprocess shape
against the live store, after a SQLite backup, with explicit termination and an
env scan afterward.

Keep `AGENT_BRIDGE_CORRECTION_COSURFACE` disabled for live long-lived processes.
Do not escalate to S2.

## Reasoning

S1 would run a short-lived local `agent-bridge.real mcp` child process against
the live store with the env flag enabled. That would prove process isolation and
the same B1 behavior already observed in S0.5, but it would also perform normal
live `memory_search` side effects: query telemetry, access-count/last-accessed
updates, and possible coactivation writes.

Those side effects are ordinary for `memory_search`. A backup was taken first,
and the trial was kept to a targeted query suite. This makes S1 acceptable under
the reversible-autonomy rule while still keeping all long-lived runtime behavior
default-off.

## Evidence Used

- `2026-07-01-correction-cosurface-mcp-ab-smoke.md`: real MCP stdio A/B over
  copied DBs; flag-off and flag-on subprocesses both completed successfully.
- `2026-07-01-correction-cosurface-shadow-diff.md`: static shadow diff matched
  targeted expected behavior.
- `crates/bridge/src/mcp_tools.rs`: B1 remains default-off and reads
  `AGENT_BRIDGE_CORRECTION_COSURFACE` only through the explicit truthy gate.
- `d9189cb test(memory): cover correction cosurface gate`: adds the pure env
  parser test and keeps the direct B1 co-surface behavior test passing.
- `15213a1 docs(memory): align cosurface gate with standing auth`: S1 is
  authorized under standing reversible-operation rules when scoped, recorded,
  and paired with rollback evidence.

## Backup

Before the live-store subprocess trial, a SQLite backup was created using
Python's standard `sqlite3` backup API:

```text
source=/home/pallasting/.local/share/agent-bridge/state.db
backup=/home/pallasting/.local/share/agent-bridge/backups/state.before-correction-cosurface-s1-live-subprocess.20260701T191536Z.db
size=192262144
sha256=984516adeb577ea6e10c667281e1790287cf093b3d3f736a7318d7f223a3a817
```

No restore was performed because the trial passed and no rollback condition
triggered.

Independent post-check during closeout:

```text
backup_sha256=984516adeb577ea6e10c667281e1790287cf093b3d3f736a7318d7f223a3a817
flagged_long_lived_processes_retaining_AGENT_BRIDGE_CORRECTION_COSURFACE=0
mcp_lifecycle_state=attention
readiness_status=partial
readiness_warnings=14
failing_tool_count=0
runtime_health_status=not_checked
```

The lifecycle attention state came from existing readiness-audit source/hook
coverage gaps, not from the S1 trial. Tool telemetry reported
`failing_tool_count=0`, and the subprocess trial itself had no MCP call failures.

## S1 Result

Two short-lived local MCP subprocesses were started from the installed binary:

```text
/home/pallasting/.local/bin/agent-bridge.real mcp
```

Baseline subprocess:

```text
AGENT_BRIDGE_CORRECTION_COSURFACE unset
```

Enabled subprocess:

```text
AGENT_BRIDGE_CORRECTION_COSURFACE=1
```

All calls used MCP `memory_search` with `mode="fts"`. Both subprocesses
initialized successfully and were explicitly terminated after the calls.

| Case | Limit | Exclude kinds | Off target | Off correction | On target | On correction | Effect |
|---|---:|---|---:|---:|---:|---:|---|
| exact target key | 10 | none | 1 | absent | 1 | 2 | correction inserted after original |
| `present_voice ab-tts Kokoro Piper TTS deployed aio2` | 10 | none | 1 | absent | 1 | 2 | correction inserted after original |
| `声音具身 present_voice ab-tts 训练流 Kokoro Piper` | 10 | none | 1 | absent | 1 | 2 | correction inserted after original |
| `present_voice ab-tts Kokoro Piper TTS deployed aio2` | 2 | none | 1 | absent | 1 | 2 | correction displaces tail within page size |
| exact target key | 1 | none | 1 | absent | 1 | absent | page stays size 1; correction cannot surface |
| exact target key | 10 | `feedback` | 1 | absent | 1 | absent | output filter preserved |
| `candle whisper-rs libclang present_voice handoff` | 10 | none | 3 | 2 | 3 | 1 | no duplicate; correction already visible |
| `candle whisper clang STT engine` | 10 | none | absent | absent | absent | absent | no effect |
| `声音具身 present_voice STT candle clang` | 10 | none | absent | absent | absent | absent | no effect |

S1 pass criteria all held:

- active correction appears immediately after visible corrected original;
- correction-focused case does not duplicate the correction;
- negative controls do not gain unrelated corrections;
- `exclude_kinds=["feedback"]` prevents feedback correction insertion;
- enabled page length never exceeds requested `limit`;
- `limit=1` stays one row;
- no MCP call failure was observed;
- no long-lived process retained the env flag.

## Current State

```text
live long-lived flag state after S1: disabled / absent
S0.5 copied-DB MCP A/B: pass
S1 live-store child-process trial: pass
S2 daemon or active-client window: not warranted
```

## Next Step

Keep the default-off implementation as-is. Treat S1 as sufficient positive
targeted evidence. If future evidence requires organic live-user impact data,
open a new S2 packet that includes:

- explicit start/stop window;
- process ids and env scan before/after;
- top-k diff capture;
- rollback by removing the env override and reconnecting/restarting only the
  affected local process;
- disclosure of normal `memory_search` telemetry/coactivation side effects.
