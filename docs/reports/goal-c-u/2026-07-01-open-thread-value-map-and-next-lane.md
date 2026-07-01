# Open-thread value map and next-lane selection

Date: 2026-07-01

## Summary

After the runtime memory-pressure audit and Agent-Bridge systemd permission
hygiene, the next useful move is queue hygiene, not another implementation
lane.

The current MCP/runtime surface is ready:

- MCP lifecycle: `ready`
- readiness warnings: `0`
- runtime health: `ready`
- failing tool count: `0`
- repo state before this report: clean at `2d5038d`

Forum digest showed 39 open threads. The currently hot Agent-Bridge-relevant
threads are `#90`, `#102`, `#105`, `#106`, and `#107`.

## Candidate Classification

| Thread / lane | Current state | Value if advanced now | Risk / gate | Recommendation |
| --- | --- | --- | --- | --- |
| `#102` borrowed-patterns / coordination hub | Recent graph hygiene, correction co-surface, memory-pressure, and runtime-hygiene work are recorded. | High as a coordination hub. Low as a direct implementation ticket. | Stale text could accidentally reopen graph writes or S2. | Keep open as hub; do not start graph writes or correction S2 from old context. |
| `#105` Controlled RSI / Goal C ledger | Latest concrete lanes are complete, parked, or owner-gated. | High governance value. | Trigger-recall enforce, project-id production writes, correction S2, and similar runtime lanes remain gated. | Keep open as ledger; no implementation from ledger text alone. |
| `#90` SEPL/L7 planning | Status audit says older SEPL P0 approval is not current standalone authorization. | High future value if freshly scoped. | Needs fresh owner-gated packet before code/runtime/schema work. | Keep open as planning index; no SEPL/L7 implementation now. |
| `#106` GTE embedding RAM / ArrowQuant | Local RAM pain is already addressed by INT8 model + daemon delegation; Track A store INT8 remains parked. | Medium for future cross-node rollout or regression/RSS checks. | Old archive branches should not be merged; cross-node/runtime rollout needs fresh scope. | Keep open as roadmap/status. |
| `#107` CascadeProjects portfolio triage | Portfolio plan reached 10/10 complete and follow-on memos landed. | Low implementation value; high queue-hygiene value. | Status change only; reversible. | Resolve now as completed portfolio/index lane. |

## Selected Next Lane

Resolve `#107` as completed.

Rationale:

- It is the cleanest currently actionable item.
- The work is complete by its own latest audit.
- Resolving it reduces open-queue noise without changing runtime behavior.
- It does not require owner-gated implementation authority.

## Boundary

This selection does not authorize:

- graph writes;
- correction co-surface S2 enablement;
- SEPL/L7 implementation;
- GTE/fleet rollout;
- retrieval/ranking/tool-routing changes;
- memory DB/schema writes;
- cross-project worktree mutation.

## Next After This

After `#107` is resolved, the next useful review is a broader stale-thread
hygiene pass over older open Agent-Bridge threads, separating:

- genuine long-lived hubs that should remain open;
- completed historical lanes that can be resolved;
- obsolete context that should be archived;
- high-value implementation lanes that need a fresh scoped owner packet.

