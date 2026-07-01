# Correction Co-Surface Controlled A/B Enablement Packet

Date: 2026-07-01

Status: `STANDING_AUTH_PACKET / DOCS_ONLY / NO_RUNTIME_CHANGE`

## Decision

Do not enable `AGENT_BRIDGE_CORRECTION_COSURFACE` in this slice.

This packet defines the smallest controlled path for deciding whether the gated
B1 correction co-surface read path should be enabled beyond shadow evidence. It
is an authorization-boundary and experiment design packet only. It does not change live
environment variables, restart daemons, deploy binaries, write memory rows, add
graph edges, change ranking weights, or alter default retrieval behavior.

## Authorization Read

The standing operating rule is reversible autonomy: docs, branches, read-only
probes, local experiments, and backed-up reversible maintenance can proceed
without repeated permission, provided evidence and lessons are recorded.

The owner's newer standing instruction supersedes repeated per-step owner
approval for meaningfully reversible local operations. The subordinate
Agent-Bridge memory authorization carve-out is therefore interpreted as an
evidence/rollback gate, not as a requirement to stop for another approval round
when the proposed action is local, scoped, reversible, and recorded.

Enabling `AGENT_BRIDGE_CORRECTION_COSURFACE=1` changes the `memory_search` read
path for the process that carries the env flag. S1 is acceptable under standing
authorization because it is a short-lived local child process with process
termination as rollback. S2 must still be preceded by an S1 closeout and an
explicit rollback packet because it affects long-lived active clients or
daemons.

## Current Baseline

Repository baseline during this packet:

```text
master == origin/master == ec80b97 docs(memory): record correction cosurface mcp smoke
```

Related evidence:

- `2026-07-01-correction-cosurface-link-review.md`
- `2026-07-01-correction-cosurface-live-backfill-preflight.md`
- `2026-07-01-correction-cosurface-single-edge-backfill.md`
- `2026-07-01-correction-cosurface-shadow-diff.md`
- `2026-07-01-correction-cosurface-mcp-ab-smoke.md`
- `2026-07-01-correction-cosurface-s1-closeout.md`
- `2026-07-01-agent-bridge-open-queue-staleness-audit.md`
- `2026-07-01-reversible-autonomy-task-replan.md`

`2026-07-01-correction-cosurface-mcp-ab-smoke.md` is an important lowering-risk
artifact: it exercised the real MCP stdio `memory_search` path in two short-lived
subprocesses over copied databases, with the flag off and on. It did not write
to the live memory store and did not enable the flag in live Codex/Cursor MCP
sessions or daemons.

Live store read-only probe:

```text
active_memories=674
active_feedback_corrections=5
corrects_edges=5
candidate_edge_exists=1
```

Visible process environment scan:

```text
AGENT_BRIDGE_CORRECTION_COSURFACE absent from all visible agent-bridge.real
daemon, daemon-http, and mcp processes checked during this packet.
```

The one-row correction-edge backfill is complete. Do not repeat it.

## Gate Question

Which controlled local A/B window should run next for
`AGENT_BRIDGE_CORRECTION_COSURFACE=1`?

Execution should be scoped to one of these levels:

| Level | Scope | Risk | Default recommendation |
|---|---|---|---|
| S0 | Offline or frozen-copy shadow expansion | No live runtime behavior change | Autonomous |
| S0.5 | Copied-DB MCP A/B smoke | Real MCP tool path, still no live-store write | Done at `ec80b97` |
| S1 | Short-lived installed-binary MCP subprocess with env enabled | Live read-path experiment in an isolated child process | Authorized, but not currently needed; see S1 closeout |
| S2 | Time-bounded daemon or active MCP client window | Shared local runtime behavior change | Only after S1 passes and rollback is recorded |

S0.5 already validated the real MCP stdio tool path against copied stores. The
S1 closeout records why a live-store child-process trial is not worth running
now: it would add normal `memory_search` telemetry/coactivation side effects
without adding material B1 correctness signal. S2 is not warranted.

## Non-Goals

This packet does not execute:

- broad default enablement;
- daemon or MCP client restart;
- deploy or install;
- schema migration;
- memory content writes;
- live `corrects` edge backfill;
- PageRank, centrality, or feedback-weight ranking changes;
- BioCortex, T6, trigger-recall, or other runtime-influence gates;
- cross-node or fleet rollout;
- keeping the flag enabled after a trial without a closeout decision.

## Experiment Contract

The experiment answers one narrow question:

Does B1 reliably co-surface active correction rows immediately after visible
corrected originals, without duplication, output-filter leaks, page growth, or
unexpected broad search-order movement?

Expected behavior from the implementation:

- default-off is byte-equivalent to the ranked page before B1;
- when enabled, only visible anchors are probed;
- an active inbound `corrects` edge causes the correction to appear immediately
  after the original;
- the final page is truncated back to the caller's `limit`;
- `exclude_kinds` still applies to co-surfaced rows;
- no duplicate correction is inserted if the correction is already visible.

## Query Suite

Use this minimum suite before any keep-enabled decision.

| Case | Query or args | Expected enabled behavior |
|---|---|---|
| Exact corrected original | `session_handoff_present_voice_tts_subsystem_20260601`, mode `fts`, limit `10` | original rank 1, correction rank 2 |
| Original-focused English | `present_voice ab-tts Kokoro Piper TTS deployed aio2`, mode `fts`, limit `10` | original visible, correction inserted after it |
| Original-focused CJK mix | `声音具身 present_voice ab-tts 训练流 Kokoro Piper`, mode `fts`, limit `10` | original visible, correction inserted after it |
| Correction-focused English | `candle whisper-rs libclang present_voice handoff`, mode `fts`, limit `10` | no duplicate if correction already visible |
| Correction-focused STT | `whisper.cpp candle pure Rust STT verification`, mode `fts`, limit `10` | no duplicate if correction already visible |
| Negative control | `candle whisper clang STT engine`, mode `fts`, limit `10` | no correction insertion unless a corrected original is visible |
| CJK negative control | `声音具身 present_voice STT candle clang`, mode `fts`, limit `10` | no effect if neither target nor correction is visible |
| Feedback exclusion | same original-focused queries plus `exclude_kinds=["feedback"]` | baseline and enabled pages stay identical |
| Small page displacement | original-focused query, limit `2` | correction can displace weakest tail row, page length remains 2 |
| Limit one | exact corrected original, limit `1` | correction is not visible after truncate, page length remains 1 |

Optional expansion:

- repeat a subset in `hybrid` and `semantic` mode for documentation only;
- include broad recent-agent queries to confirm the flag is quiet when no
  corrected original appears;
- collect latency deltas, but treat correctness and guardrails as the primary
  gate.

## Measurement Format

For each case, record:

```text
case_id
mode
limit
exclude_kinds
baseline_keys
enabled_keys
inserted_keys
removed_tail_keys
correction_duplicate_count
page_len_baseline
page_len_enabled
elapsed_ms_baseline
elapsed_ms_enabled
status
```

Do not publish raw memory content unless a later review explicitly needs it.
Keys, kinds, ranks, and counts are sufficient for the gate.

## Pass Criteria

S1 can be marked `PASS` only if all are true:

1. original-focused cases place the active correction immediately after the
   corrected original whenever the original is visible and limit permits it;
2. correction-focused cases do not duplicate the correction;
3. negative controls do not gain unrelated corrections;
4. `exclude_kinds=["feedback"]` exactly prevents feedback correction insertion;
5. enabled page length never exceeds `limit`;
6. limit-1 behavior is documented as expected truncation;
7. no MCP errors, panics, or lifecycle warnings appear during the trial;
8. tail displacement is limited to the correction insertion contract;
9. no daemon or current Codex MCP process is left with the env flag enabled.

## Fail Or Stop Criteria

Stop the trial and leave the flag disabled if any are true:

- feedback rows appear despite `exclude_kinds=["feedback"]`;
- page length grows beyond the requested limit;
- a correction is duplicated on the page;
- a correction surfaces without a visible corrected original anchor;
- an inactive or superseded correction surfaces;
- negative controls show broad unrelated movement;
- latency or tool errors become operationally visible;
- the env flag leaks into a long-lived process unintentionally.

## Preferred S1 Execution Shape

Use a short-lived installed-binary MCP subprocess rather than the current Codex
MCP process:

```text
AGENT_BRIDGE_CORRECTION_COSURFACE=1 \
AGENT_BRIDGE_TOOL_PROFILE=all \
AGENT_BRIDGE_TOOLSET=all \
/home/pallasting/.local/bin/agent-bridge.real mcp
```

Drive it with newline-delimited JSON-RPC:

1. `initialize`
2. `notifications/initialized`
3. `tools/list`
4. `tools/call` for `memory_search` on the query suite
5. terminate the child process
6. scan visible `agent-bridge.real` processes to confirm no long-lived process
   retained `AGENT_BRIDGE_CORRECTION_COSURFACE`

For each query, run a baseline call with the env flag absent and an enabled call
with the env flag present. Keep the baseline and enabled subprocesses separate
so the process env is unambiguous.

Note: normal MCP `memory_search` may still update retrieval telemetry,
coactivation, access counts, or last-accessed metadata. That is ordinary
`memory_search` behavior, not a correction-edge or memory-content write. If the
owner wants a zero-live-write evidence pass, stay at S0 and use a frozen DB copy
or direct read-only shadow replica instead of MCP `memory_search`.

## S2 Escalation Conditions

Do not move to a daemon or active-client window unless S1 passes and a closeout
packet says why S2 adds value and records a rollback plan.

If S2 is run later, the window should be time-bounded and local-node-only:

- record start time, intended stop time, process ids, and authorization/rollback reference;
- capture the same top-k diff suite before and after;
- remove the env setting and restart affected processes at the end;
- verify the flag is absent from visible long-lived processes;
- post a closeout with keep-disable or keep-enable recommendation.

## Rollback

S1 rollback is process termination:

```text
terminate the child MCP subprocess
verify no visible long-lived agent-bridge.real process has
AGENT_BRIDGE_CORRECTION_COSURFACE set
```

S2 rollback, if ever run, is:

```text
remove the env override
restart only the affected local process or unit
verify no visible long-lived process retains the flag
rerun a small default-off memory_search smoke
```

No DB rollback is expected for B1 itself because B1 does not write memory rows,
schema, or `corrects` edges. Normal retrieval telemetry from `memory_search`
should be disclosed in the closeout.

## Board Update

Post this packet to thread #102 as a status/update, not as a per-step approval
request:

```text
Standing-auth update: S1 correction co-surface controlled A/B can proceed as a
reversible local child-process trial.
Scope: local short-lived installed-binary MCP subprocess only.
Flag: AGENT_BRIDGE_CORRECTION_COSURFACE=1.
No daemon restart, deploy, schema change, memory content write, or edge backfill.
Output: top-k diff closeout and keep-disabled/keep-enabled recommendation.
```

## Boundary

This report is the gate packet. It does not execute the gate.
