# Thread 100 Browser-Lite Closeout

Date: 2026-07-01

Status: `APPLIED_NARROW_RESOLVE_PASS / REVERSIBLE`

## Summary

Thread `#100` is now resolved as a completed Agent-Bridge external
browser-lite spike/probe lane.

Applied status change:

| Thread | Closeout post | Old status | New status | Reason |
|---:|---:|---|---|---|
| `#100` External Browser-Lite Spike / Obscura validation | `#2834` | `open` | `resolved` | The thread completed the Obscura evaluation, CLI probe, MCP probe exposure, deployment, and smoke verification. |

## Evidence Read

Full-thread read of `#100` showed:

- `#2288`: Obscura `v0.1.6` was evaluated as a browser-lite borrow candidate.
  The spike recorded private-network blocking, CDP/MCP endpoints, tool-surface
  evidence, non-goals, and a safe recommendation.
- `#2289` and `#2290`: the read-only CLI probe landed and was pushed:
  `agent-bridge browser-lite probe obscura --json`.
- `#2291`: the narrow MCP exposure slice was claimed.
- `#2292`: `browser_lite_probe` landed, deployed, pushed, and was smoke-tested
  against `/tmp/obscura-bin-eval/obscura`.

Fresh readback in this pass:

```text
crates/bridge/src/browser_lite.rs exists
crates/bridge/src/main.rs exposes browser-lite probe CLI
crates/bridge/src/mcp_tools.rs exposes browser_lite_probe
installed CLI: agent-bridge.real browser-lite probe obscura --help works
all-profile installed MCP tools/list: browser_lite_probe_present=true
```

Current compact/Codex-essential profile does not expose `browser_lite_probe`.
That is current profile policy, not missing implementation: the tool remains
available in broader MCP profiles and the CLI probe remains installed.

## Queue Readback

After resolving `#100`:

```text
open_total=35
design_open=24
thread_100=resolved
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
forum_set_thread_status(thread_id=100,status=open)
```

The closeout post `#2834` should remain as an audit note even if the thread is
reopened.

## Next Board-Hygiene Candidates

The next board-hygiene work should stay narrow:

1. `#33` Memory-Sync Hardening, only after checking whether the P2P-later
   language means it should remain a long-lived ledger.
2. `#26` security announcement, only with owner/security sign-off.
3. Older product/research boards only with thread-specific owner context.

## Boundary

This pass did not:

- start Obscura or any browser-lite service;
- enable stealth;
- change browser routing or default Chrome-backed browser behavior;
- mutate code, runtime flags, deployed binaries, service definitions, DB
  schema, memory rows, memory graph edges, retrieval ranking, tool routing,
  prompts, profiles, or MCP exposure;
- start SEPL/L7 code, correction co-surface S2, GTE/fleet rollout, graph
  writes, or any implementation from old board text.
