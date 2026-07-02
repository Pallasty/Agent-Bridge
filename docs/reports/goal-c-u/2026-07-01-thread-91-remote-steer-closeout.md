# Thread 91 Remote Steer Closeout

Date: 2026-07-01

Status: `APPLIED_NARROW_RESOLVE_PASS / REVERSIBLE`

## Summary

Thread `#91` is now resolved as a completed Agent-Bridge capability-gap lane.

Applied status change:

| Thread | Closeout post | Old status | New status | Reason |
|---:|---:|---|---|---|
| `#91` Agent-Bridge remote session steering gap | `#2832` | `open` | `resolved` | The thread records the full arc from gap/RFC through owner-approved P1-P4 implementation, merge, deploy, and live MCP round-trip verification. |

This is the focused follow-up recommended by:

```text
docs/reports/goal-c-u/2026-07-01-open-thread-map-board-hygiene-closeout.md
```

## Evidence Read

Full-thread read of `#91` showed:

- `#2168`: original gap recorded. XM messaging could not inject input into a
  blocking interactive session.
- `#2169` to `#2172`: SSH/tmux attach, `tmux send-keys`, `tmux -C`, and the
  AB-owned launch/orchestration design were validated and staged.
- `#2173`: owner approved full P1-P4 implementation. The implementation
  included `remote_steer`, `agent_steer_*`, `agent_orchestrate_scan`, the SOP,
  and gate discipline.
- `#2174`: DONE/LIVE. The feature was merged to master, deployed, and verified
  end-to-end through MCP into an aio2 tmux session with launch, drive, list,
  orchestrate scan, and kill.

Fresh readback in this pass:

```text
MCP lifecycle=ready
readiness_warnings=0
runtime_health_status=ready
failing_tool_count=0
```

Current MCP/tool surface includes:

```text
agent_steer_launch
agent_steer_drive
agent_steer_capture
agent_steer_list
agent_steer_kill
agent_orchestrate_scan
```

Current source still contains the landed surfaces:

```text
crates/bridge/src/remote_steer.rs
crates/bridge/src/mcp_tools.rs
docs/REMOTE_SESSION_STEERING_SOP.md
scripts/ab-steer-launch.sh
```

`agent_steer_list` returned `count=0` for local sessions during this pass. That
means no active local steer tmux session was running; it is not evidence that
the feature is absent.

## Queue Readback

After resolving `#91`:

```text
open_total=36
design_open=25
thread_91=resolved
thread_103=archived
thread_107=resolved
```

The remaining current Agent-Bridge keep-open anchors are still:

```text
#102 coordination/status hub
#105 Controlled RSI / Goal C ledger
#90 SEPL/L7 planning index
#106 GTE / ArrowQuant roadmap/status
#104 BioCortex opt-in continuation with Onsen Step B blocker
```

## Rollback

The status change is reversible:

```text
forum_set_thread_status(thread_id=91,status=open)
```

The closeout post `#2832` should remain as an audit note even if the thread is
reopened.

## Next Board-Hygiene Candidates

The next board-hygiene work should stay thread-specific. Do not batch older
research/product boards.

Reasonable future candidates:

1. `#33` Memory-Sync Hardening, but only after checking whether its P2P-later
   language means it should remain a long-lived ledger.
2. `#100` External Browser-Lite Spike, after a focused full-tail read.
3. `#26` security announcement, only with owner/security sign-off.

## Boundary

This pass did not:

- mutate code, runtime flags, deployed binaries, service definitions, DB
  schema, memory rows, memory graph edges, retrieval ranking, tool routing,
  prompts, profiles, or MCP exposure;
- run or kill steer sessions;
- deploy a binary or restart services;
- start SEPL/L7 code, correction co-surface S2, GTE/fleet rollout, graph
  writes, or any implementation from old board text.
