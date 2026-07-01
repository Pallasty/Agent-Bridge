# Correction Co-Surface S1 Closeout

Date: 2026-07-01

Status: `S1_NOT_RUN_NOT_NEEDED / KEEP_LIVE_FLAG_DISABLED / NO_RUNTIME_CHANGE`

## Decision

Do not run the live-store S1 child-process trial now.

S0.5 already exercised the real installed-binary MCP stdio `memory_search` path
against copied databases, with `AGENT_BRIDGE_CORRECTION_COSURFACE` off and on.
That test covered the behavior S1 was meant to de-risk without touching the live
memory store or any long-lived process environment.

Keep `AGENT_BRIDGE_CORRECTION_COSURFACE` disabled for live long-lived processes.
Do not escalate to S2.

## Reasoning

S1 would run a short-lived local `agent-bridge.real mcp` child process against
the live store with the env flag enabled. That would prove process isolation and
the same B1 behavior already observed in S0.5, but it would also perform normal
live `memory_search` side effects: query telemetry, access-count/last-accessed
updates, and possible coactivation writes.

Those side effects are ordinary for `memory_search`, but they are not necessary
for the correction co-surface correctness question. The copied-DB MCP smoke is a
cleaner proof because it used the real MCP subprocess path while keeping live DB
state untouched.

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
  authorized under standing reversible-operation rules, but authorization does
  not require running a trial when the trial adds no material signal.

## Current State

```text
live long-lived flag state: disabled / absent
S0.5 copied-DB MCP A/B: pass
S1 live-store child-process trial: intentionally not run
S2 daemon or active-client window: not warranted
```

## Next Step

Keep the default-off implementation as-is. If future evidence requires organic
live-user impact data, open a new S2 packet that includes:

- explicit start/stop window;
- process ids and env scan before/after;
- top-k diff capture;
- rollback by removing the env override and reconnecting/restarting only the
  affected local process;
- disclosure of normal `memory_search` telemetry/coactivation side effects.
