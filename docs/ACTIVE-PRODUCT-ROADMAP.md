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
- **R1 — real-task memory usefulness (decision complete):** the code-locked 20-task gate closed on 2026-08-11. The aggregate was a positive dogfood signal, so retain the current memory and continuity architecture without widening retrieval or opening another ranking/research lane. Routine positive sampling stops at the decision gate; record only meaningful missing, stale, or harmful recall events as regression evidence. See `docs/reports/goal-c-u/2026-08-11-r1-memory-usefulness-final-decision.md`.
- **R2 — lower coordination ceremony (dogfooding):** ordinary single-developer work uses the local plan, optional work memory, and final result; forum is reserved for parallel agents, cross-device handoff, shared high-risk changes, or active incidents. A single short-lived coordination registry holds at most five genuinely active shared threads. Historical forum `open` status is not the product backlog. See `docs/R2-LOW-CEREMONY-OPERATING-MODE.md`.
- **R3 — continuity dogfood:** keep bootstrap orientation exact-project and actionable across both semantic results and the Project State Digest; validate the behavior in daily tasks before adding new memory mechanisms. See `docs/R3-CONTINUITY-DOGFOOD.md`.
- **R4 — continuity and embodiment benefit dogfood (collection pending):** freeze the current capability surface and collect one privacy-minimal, owner-local evidence set across resumed tasks, foreground Avatar sessions, paired embodied tasks, and explicit Qwen voice sessions. The reducer has no runtime influence and exports only a hash-bound content-free aggregate. A complete sample leads to one owner decision: review one bounded shortcut for adoption, or retain the current on-demand commands and end expansion. See `docs/BENEFIT-DOGFOOD-V1.md`.
  - **R4-A — reversible Avatar expression (owner-reopened 2026-08-24; Increment 2 bounded live PASS, foreground dogfood admitted):** repeated live Focus-follow and bubble trials established a current owner-local use case, and the owner clarified that Xiao Shu's own reversible motion is AB expression rather than an external action needing per-gesture permission. Increment 1 removes that obsolete confirmation gate while adding durable negative outcomes, exact-window targeting, and verified arrival. Increment 2 is frozen as one owner-started, foreground, at-most-30-minute, non-service observer: the initial focus is baseline only; later candidates must pass dwell, cooldown, acknowledged-target, fullscreen, structured `ab-sensitive` mark, structured-identity, built-in/owner exact-denylist, pause, action-lock, travel/geometry, owner-drag, failure-backoff, and three-attempt-budget gates. It has no prompt, audio, pointer, focus, or input authority. The automated suite, adversarial review, deployed observer dispatch, matching outcome pair, and owner-visible replay are green; evidence is recorded in `docs/reports/avatar/2026-08-24-focus-follow-bounded-observer.md`. It may now be used only as an explicitly started foreground dogfood command. No service, autostart, persistence, or authority widening is admitted until daily-use value is observed and the owner labels it helpful, neutral, or distracting. Two increments without daily-use value refreeze the lane.
- **R5 — agent-beneficiary closure (P0 deployed 2026-08-24; P1a evidence reachability):** the optional agent-reported task outcome is live through `session_finalize`, remains provenance-labeled in `practical_workflow_scorecard`, and privacy-minimal non-mutating `BodyOperationEnvelope` receipts have an atomic advisory ledger behind the existing record-only embodiment surface. The first production agent-reported outcome claim is admitted. P1a adds profile-scoped, receipt-only forms of `embodiment_record` and `embodiment_snapshot` to the Codex compact profile so that deployed Codex can reach the already bounded receipt path, then runs the preregistered real-task evidence trial. It does not authorize authenticated owner/harness evidence, executor authority, mutation admission, automatic receipt generation, or a production body registry. Reuse Tool Atlas for tool pressure; do not add dynamic routing or a second tool-health system. See `docs/design/AGENT-BENEFICIARY-CLOSURE-V1.md`, `docs/R5-BENEFICIARY-CLOSURE-DOGFOOD.md`, and `docs/reports/goal-c-u/2026-08-24-r5-p0-live-deployment-and-p1a-baseline.md`.

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
The explicitly owner-reopened R5 source slice is the only current exception for
embodiment-contract work; it does not reopen embodiment runtime admission or
the broader protocol backlog.
