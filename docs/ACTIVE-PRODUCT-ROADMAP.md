# Agent-Bridge Active Product Roadmap

Status: active product priorities for a single developer. This replaces research-chain sequencing as the default source of next goals; historical roadmaps and research reports remain evidence, not an automatic backlog.

## Product north star

Agent-Bridge should reduce the cost of using several local AI development tools: recover the right context, continue unfinished work, coordinate an occasional subagent, and expose local capabilities without making the owner manage a research program.

## Priority lanes

1. **Core (about 70%)** — memory usefulness, session continuity, cross-machine sync, install/update truth, daemon/MCP reliability, and small actionable diagnostics.
2. **On demand (about 20%)** — subagents, worktrees, terminal, browser, and voice only when a real task uses them.
3. **Experiments (at most 10%)** — world models, embodiment, compressive/private-memory evaluation, avatars, and trajectory learning. These are default-frozen until a current user problem and measurable trial justify reopening one lane.

## Active sequence

- **R0 — project truth and roadmap reset:** one read-only command reports source, remote, installed-binary, dirty-WIP, and alignment status. Preserve all dirty worktrees.
- **R1 — real-task memory usefulness (collecting):** evaluate 20 real development tasks for helpful recall, stale/wrong recall, repeated explanation, payload size, and latency. The local recorder is implemented; the product conclusion remains blocked until 20 organically occurring tasks are observed.
- **R2 — lower coordination ceremony (dogfooding):** ordinary single-developer work uses the local plan, optional work memory, and final result; forum is reserved for parallel agents, cross-device handoff, shared high-risk changes, or active incidents. A single short-lived coordination registry holds at most five genuinely active shared threads. Historical forum `open` status is not the product backlog. See `docs/R2-LOW-CEREMONY-OPERATING-MODE.md`.
- **R3 — continuity dogfood:** make bootstrap, topic-shift recall, work memory, and final curation useful in daily tasks before adding new memory mechanisms.

## Admission rule for new work

A new implementation lane must identify a recent real problem, a user-cost metric, a usable closure within one or two increments, and a real-task acceptance path. Source-only, fixture-only, or synthetic PASS may support safety but cannot by itself justify the next increment. Two increments without use-value evidence freeze the lane.

External papers and repositories may produce one value decision, one reusable principle, and at most one bounded spike. They do not automatically create sequential gates.

## Frozen until separately reopened

- Further private-custody or crash-artifact exclusion gates.
- Additional ExplicitTrajectory numbered gates.
- World-model or embodiment runtime admission.
- New synthetic receipt/authority/preflight protocol families.
- Voice or avatar expansion without observed recurring use.

Frozen work is retained and remains searchable. Freeze means “not an active product goal,” not rejection or deletion.
