# Agent-Bridge Active Product Roadmap

Status: active product priorities for a single developer. This replaces research-chain sequencing as the default source of next goals; historical roadmaps and research reports remain evidence, not an automatic backlog.

## Product north star

Agent-Bridge should sustain one resident subject across model, process, session,
device, and body changes: preserve identity, commitments, experience, and
accountability; wake bounded cognition only when there is a reason to think;
and express through quiet, reversible bodies without making a model process,
CLI window, voice, or Avatar the identity itself. The short definition is
**persistent subject, intermittent cognition, reversible bodies**.

For the current owner-local system, that resident subject is Xiao Shu. This is
an operational continuity goal, not a claim of consciousness, sentience, or
uninterrupted subjective experience. The practical product test remains
whether AB restores the right state, reduces owner restatement and coordination
cost, and closes useful work without turning the owner into a research-program
operator. See `docs/design/RESIDENT_XIAOSHU_V0.md`.

## Priority lanes

1. **Persistent-subject core (about 60%)** — identity and commitment continuity, memory usefulness, cross-session/machine recovery, install/update truth, daemon/MCP reliability, and small actionable diagnostics.
2. **Intermittent cognition (about 25%)** — bounded model invocations, subagents, worktrees, terminal, and browser only when a real task needs them; cognitive providers are replaceable and do not own identity or durable authority.
3. **Reversible bodies (about 10%)** — Avatar, bubbles, and voice only where an owner-visible expression need and attention-cost measure justify them. Presentation may be autonomous inside its admitted reversible boundary.
4. **Research (at most 5%)** — world models, compressive/private-memory evaluation, trajectory learning, and broader embodiment. These remain default-frozen until a current user problem and measurable trial justify reopening one lane.

## Active sequence

- **R0 — project truth and roadmap reset:** one read-only command reports source, remote, installed-binary, dirty-WIP, and alignment status. Preserve all dirty worktrees.
- **R1 — real-task memory usefulness (decision complete):** the code-locked 20-task gate closed on 2026-08-11. The aggregate was a positive dogfood signal, so retain the current memory and continuity architecture without widening retrieval or opening another ranking/research lane. Routine positive sampling stops at the decision gate; record only meaningful missing, stale, or harmful recall events as regression evidence. See `docs/reports/goal-c-u/2026-08-11-r1-memory-usefulness-final-decision.md`.
- **R2 — lower coordination ceremony (dogfooding):** ordinary single-developer work uses the local plan, optional work memory, and final result; forum is reserved for parallel agents, cross-device handoff, shared high-risk changes, or active incidents. A single short-lived coordination registry holds at most five genuinely active shared threads. Historical forum `open` status is not the product backlog. See `docs/R2-LOW-CEREMONY-OPERATING-MODE.md`.
- **R3 — continuity dogfood:** keep bootstrap orientation exact-project and actionable across both semantic results and the Project State Digest; validate the behavior in daily tasks before adding new memory mechanisms. See `docs/R3-CONTINUITY-DOGFOOD.md`.
- **R4 — continuity and embodiment benefit dogfood (collection pending):** freeze the current capability surface and collect one privacy-minimal, owner-local evidence set across resumed tasks, foreground Avatar sessions, paired embodied tasks, and explicit Qwen voice sessions. The reducer has no runtime influence and exports only a hash-bound content-free aggregate. A complete sample leads to one owner decision: review one bounded shortcut for adoption, or retain the current on-demand commands and end expansion. See `docs/BENEFIT-DOGFOOD-V1.md`.
  - **R4-A — reversible Avatar expression (owner-reopened 2026-08-24; Increment 2 bounded live PASS, foreground dogfood admitted):** repeated live Focus-follow and bubble trials established a current owner-local use case, and the owner clarified that Xiao Shu's own reversible motion is AB expression rather than an external action needing per-gesture permission. Increment 1 removes that obsolete confirmation gate while adding durable negative outcomes, exact-window targeting, and verified arrival. Increment 2 is frozen as one owner-started, foreground, at-most-30-minute, non-service observer: the initial focus is baseline only; later candidates must pass dwell, cooldown, acknowledged-target, fullscreen, structured `ab-sensitive` mark, structured-identity, built-in/owner exact-denylist, pause, action-lock, travel/geometry, owner-drag, failure-backoff, and three-attempt-budget gates. It has no prompt, audio, pointer, focus, or input authority. The automated suite, adversarial review, deployed observer dispatch, matching outcome pair, and owner-visible replay are green; evidence is recorded in `docs/reports/avatar/2026-08-24-focus-follow-bounded-observer.md`. It may now be used only as an explicitly started foreground dogfood command. No service, autostart, persistence, or authority widening is admitted until daily-use value is observed and the owner labels it helpful, neutral, or distracting. Two increments without daily-use value refreeze the lane.
- **R5 — agent-beneficiary closure (P0 retained; P1a failed and rollback deployed/verified on 2026-08-25):** the optional agent-reported task outcome remains live through `session_finalize` and provenance-labeled in `practical_workflow_scorecard`; the atomic advisory receipt ledger remains intact behind broader profiles. The first eligible P1a capture produced one rejected request before one admitted, verified/achieved agent-reported outcome, so the frozen immediate-failure gate fired. The compact-profile exposure of `embodiment_record` and `embodiment_snapshot` was removed exactly as preregistered; a fresh Codex restart then reported no stale MCP children and the live 107-tool compact manifest retained `session_finalize` while excluding both receipt tools. The receipt lane had no natural sample and remains insufficient rather than failed. Do not resume collection, add automatic generation, or widen authority without a separately approved refreeze. See `docs/design/AGENT-BENEFICIARY-CLOSURE-V1.md`, `docs/R5-BENEFICIARY-CLOSURE-DOGFOOD.md`, `docs/reports/goal-c-u/2026-08-24-r5-p0-live-deployment-and-p1a-baseline.md`, and `docs/reports/goal-c-u/2026-08-25-r5-p1a-first-capture-fail.md`.
- **R6 — bounded session-finalize maintenance (deployed 2026-08-25):** seven-day production telemetry showed 169 error-free `session_finalize` calls but a 2.161-second P95 and 7.078-second maximum. A real-store-copy replay isolated repeated full importance-decay rewrites as the dominant avoidable cost. Decay now selects only rows due by `min(6 hours, 1% of the requested half-life)`, returns before scanning the edge graph when none are due, preserves the old anchor while deferred, catches up over the full elapsed interval when due, and still repairs future clock-skew anchors. This is batching, not dropped maintenance or a new background service. Keep ordinary telemetry; do not open a benchmark-only follow-up unless natural calls remain slow. See `docs/reports/goal-c-u/2026-08-25-r6-session-finalize-maintenance.md`.
- **R7 — Resident Xiao Shu v0 (owner-reopened and deployed 2026-08-25; M0/M1 technical, owner-local live, installed-binary, and R7-E1 owner-visible wake gates PASS; explicit owner label pending):** the observed product gap is that Xiao Shu's apparent continuity still depends too much on a live interactive CLI/model session. AB now owns a provider-independent identity manifest, bounded wake packet, typed advisory intent, compact sleep digest, single-writer fence, exactly-once wake journal, and one explicit `resident cognition` CLI. Codex runs ephemerally with strict config, user config/rules/hooks and model-facing tool features disabled, read-only/no-approval bounds, stdin-only context, schema binding, a 120-second deadline, process-group custody, and fail-closed JSONL event auditing. A live sequence retained the same subject across fresh processes, recovered the expected compact provider claim, recorded five verified completions plus one deliberately non-green hardening failure, rejected replay and concurrency in 0.02 seconds without a second provider, persisted no raw owner event, and left no provider child. R7-E1 now supplies the previously missing owner-only `resident evaluate` seam: it binds one fixed useful/neutral/distracting/harmful label to a completed wake's private hashes, makes same-label replay idempotent and conflicting labels fail closed, and lets the next explicit wake recover the label without pre-accepting its own result. The implementation and permission-capable durable-state-root fix are deployed at `cb01c6d6`; all long-running AB services execute the matching installed binary, Doctor closed at zero failures and zero warnings, and owner-visible wake `wake-ef3781a1c2fe8366bd31a421a8b1a6ae` completed with zero provider tool events while remaining explicitly unevaluated. The isolated fixed-label fixture is technical evidence only. This lane adds no daemon, scheduler, service, autostart, unattended wake, operation/tool authority, expression execution, automatic memory promotion, or general body runtime. Product closure now waits only for the owner's explicit label; even `useful` permits only a separate M2 shadow-design review. See `docs/design/RESIDENT_XIAOSHU_V0.md`, `docs/reports/goal-c-u/2026-08-25-r7-resident-xiaoshu-v0.md`, and `docs/reports/goal-c-u/2026-08-25-r7-owner-evaluation-v0.md`.

## Admission rule for new work

A new implementation lane must identify a recent real problem, a user-cost metric, a usable closure within one or two increments, and a real-task acceptance path. Source-only, fixture-only, or synthetic PASS may support safety but cannot by itself justify the next increment. Two increments without use-value evidence freeze the lane.

External papers and repositories may produce one value decision, one reusable principle, and at most one bounded spike. They do not automatically create sequential gates.

## Frozen until separately reopened

- Further private-custody or crash-artifact exclusion gates.
- Additional ExplicitTrajectory numbered gates.
- General world-model or effectful embodiment-runtime admission beyond the
  named R4-A reversible-expression and R7 read-only resident slices.
- New synthetic effect receipt, authority, or preflight protocol families.
- Voice or avatar expansion without observed recurring use.

Frozen work is retained and remains searchable. Freeze means “not an active product goal,” not rejection or deletion.
The retained R5 P0 record-only source, R4-A reversible-expression slice, and R7
resident identity/read-only cognition slice are narrow, non-transitive
exceptions. None reopens R5 collection, effectful embodiment runtime admission,
automatic execution, or the broader protocol backlog.
