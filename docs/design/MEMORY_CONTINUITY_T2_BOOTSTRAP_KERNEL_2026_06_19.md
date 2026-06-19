# Memory Continuity T2 Bootstrap Kernel

Date: 2026-06-19

T2 makes continuity metadata visible at session start without changing retrieval
authority. `session_bootstrap` still uses the same selected memory rows as before;
the new layer only changes presentation and budgeting over those already selected
rows.

## Behavior

Bootstrap now adds a bounded `Continuity Kernel` block when selected rows contain
continuity metadata. The block is grouped into three cognitive tiers:

- `must-block / constraints`: `actionability=must_block`, or roles `constraint` and `warning`
- `active state / procedures`: `actionability=plan_influence|needs_review`, or roles `state`, `procedure`, `preference`
- `evidence / background`: `actionability=background`, or roles `evidence`, `archive`

Each kernel row includes a compact retrieval reason:

```text
{why: must_block, role=constraint, conf=verified, radius=project}
```

Generic bootstrap rows also show the same reason string for memories with continuity
metadata. Raw `continuity_*` tags are hidden from the generic tag list to avoid
spending context on machine-oriented tag prefixes. Ordinary tags remain visible.

## Budget Contract

The kernel has its own block cap:

```text
BUDGET_CONTINUITY_KERNEL = 260 tokens
```

The cap is documented in the T0 baseline note as part of the bootstrap budget
contract; the branch no longer adds a separate T0 baseline MCP tool surface.
The kernel does not run extra store queries and does not reorder or suppress the
main memory row set. It is an overlay on selected rows only.

## Verification

Focused tests cover:

- Generic bootstrap rows keep ordinary tags, hide raw continuity tags, and render a reason string.
- Continuity Kernel grouping and tier order.
- `session_bootstrap` emits the kernel from selected scoped rows.

Commands:

```bash
cargo test -p ab-bridge continuity_kernel -- --nocapture
cargo test -p ab-bridge bootstrap_rows_render_continuity_reason_without_raw_continuity_tags -- --nocapture
```

## Next Step

T3 should capture low-friction feedback on whether retrieved or bootstrapped memory
rows were used, ignored, stale, duplicate, harmful, missing, or too large. That
feedback should be stored as telemetry first, then used to tune T2 budgets and
T4 consolidation candidates.
