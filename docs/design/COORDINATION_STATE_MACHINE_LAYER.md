# Coordination State-Machine Layer — on-revive design for RFC #1787 (A2/B)

> **Status: DESIGN-ONLY / PARKED.** This is on-revive 储备 for the PARKED
> master-worker orchestration RFC (#1787, forum thread #34). **Do NOT build
> now** — revive conditions are unmet (see §6). This memo exists so that *if*
> #1787 revives, we lift a verified contract instead of re-deriving one.
>
> Provenance: 2026-06-02 research into Nous **Hermes Agent Kanban** (a shipped
> reference implementation of the same idea) + a code audit of what
> agent-bridge already has. Verdict: **borrow the design, not the build.**

## 1. The one-sentence thesis

Hermes Kanban is *"a durable task board … that lets multiple named agents
collaborate **without fragile in-process subagent swarms**."* That is the exact
reframe RFC #1787 proposed. Two teams converged independently → the direction is
sound. Hermes = a **durable message-queue + state-machine**.

**Code audit finding:** agent-bridge already owns the *message-queue half*. What
is missing is the *state-machine half* — the layer that turns our existing
primitives into a cross-agent coordination board. This memo specs only that
layer. It is **a layer on top of existing tables, not a greenfield kanban.**

## 2. What we already have (DO NOT rebuild)

| Primitive | Where | Role it already plays |
|---|---|---|
| Inter-agent message bus | `agent_messages` table (W6); `agent_message_send` / `agent_inbox_fetch` / `mark_read` | ≡ Hermes "comments form the inter-agent protocol" |
| Single-session plan | `plans` table + `PlanRecord`/`PlanStep` (status, default `pending`); `plan_save`/`plan_load`/`plan_update_step` (W5) | per-agent TODO + step status — **single session, no assignee/deps/claim** |
| Spawn fabric | `agent_spawn` (multi-frontend: claude/kilo/opencode/oz/gemini/auggie), remote-ssh dispatch | the worker-lane *spawn mechanism* |
| Session lifecycle + liveness | `agent_session_*`, lifecycle reconciliation (`d0feb77`) | ≡ Hermes claim/heartbeat/crash-detect substrate; mirrors triple-anchor liveness |
| Context handoff buffer | `work_memory` (per project/session, slots, precompact trim) | ≡ the resume-context a blocked→unblocked worker needs |
| Human approval surface | `present_await_decision` (one-shot blocking card), dock Slice 1a (records-not-executes), `desktop_confirm` / `use_grant` (gated host exec) | ≡ Hermes block→human→unblock *surface* (but one-shot, not a resumable loop) |

## 3. The missing layer — 4 primitives to add (on revive)

1. **Task state machine as the coordination spine.**
   New `tasks` table: `(task_id, title, body, assignee, status, parent_task_id?,
   tenant?, idem_key?, created_at, updated_at)` with
   `status ∈ {triage, todo, ready, running, blocked, done, archived}`.
   `links` (parent→child) drive dependency promotion (`todo → ready` when all
   parents `done`). Reuse `agent_messages` as the comment/protocol channel keyed
   by `task_id`. This is the part `plans` is *not* (plans = single-session, no
   assignee/deps/claim).

2. **Runs vs Tasks separation.**
   New `task_runs` table: one row per execution attempt. A `task` is the logical
   unit; a `run` is an attempt. `agent_session` = one run's execution. Preserves
   full attempt history + per-run handoff metadata (summary, changed files,
   verify steps). Today `attempt`/`run_id`/`cloud_run_id` are per-spawn details
   with no logical-task aggregation above them.

3. **Resumable block → comment → unblock (no restart).**
   `block(reason)` → `blocked` state; human appends an `agent_messages` comment;
   `unblock` re-spawns the assignee **reusing `work_memory`** for context so the
   worker resumes rather than restarts. Today `present_await_decision` is
   one-shot; this turns it into a durable loop.

4. **Single-terminal-outcome contract + no-silent-drop.**
   Every claim resolves to **exactly one** of `complete` / `block` /
   crash-path (`crashed`/`gave_up`/`timed_out` on tool-less exit). Unresolvable
   `assignee` → task **stays `ready` + emits `skipped_nonspawnable` event**,
   never silently dropped (mirrors the "No silent caps" instinct). Builds on the
   existing lifecycle reconciliation, adding the *enforced single terminal*.

## 4. Two-surface invariant (lift verbatim from Hermes)

- **Agent surface:** workers act **only** through `task_*` tools, never shell
  out. Reads see a consistent view; writes can't drift.
- **Human surface:** dock / forum / CLI — all routing through the **same single
  SQLite truth**.
- This is *exactly* the dock's records-not-executes philosophy generalized:
  the board records intent; blessed paths (`agent_spawn`, `desktop_confirm`)
  execute. **No new execution authority is introduced.**

## 5. Non-goals (owner taste = lightweight)

- ❌ No heavyweight board GUI. The dock + forum are the human surface.
- ❌ No in-process subagent swarm (the very thing this replaces).
- ❌ No new HTTP origin / no new host-execution authority.
- ❌ Not a multi-tenant SaaS fleet — single owner, single node first.

## 6. Landing path & timing (§段③) — gated, not scheduled

**There is no calendar schedule** — without a proven hard need, this stays
parked. The path is trigger-driven:

| Gate | Trigger | Action |
|---|---|---|
| **G0 — now** | — | Design-only. **Do not build.** This memo + memory anchors are the whole deliverable. |
| **G1 — revive** | `crates/agent/` quiesces **OR** owner ACK on collision-check #4, **AND** a concrete hard need (a real multi-agent task in-process subagents handle poorly) | Unpark #1787; post intent to thread #34 before any code. |
| **Phase A** (S, ~1–2d) | post-G1 | `tasks` + `task_runs` tables + minimal state machine. **Manual promotion only, no dispatcher.** Reuse `agent_messages`. Smallest vertical slice. |
| **Phase B** (M, ~3–5d) | Phase A green | Dispatcher tick (dependency promotion + spawn) reusing `agent_spawn` + `agent_session`. Claim/TTL on top of lifecycle reconciliation. |
| **Phase C** (S–M) | Phase B green | block/unblock resumable loop (reuse `work_memory`) + reviewer gate + `skipped_nonspawnable` no-silent-drop. |

T-shirt sizes are rough and **only meaningful post-revive**; the binding gate is
G1's hard-need, not effort.

## 7. Collision posture (binding)

`crates/agent/` and `crates/store/` are **sibling-hot** (active churn:
`agent_spawn` retry, remote-ssh dispatch, session-lifecycle hardening; live
branches `agent-spawn-*`, `remote-session-steering`, `steer-control-plane-probe`).
**Any build under this memo MUST coordinate via forum thread #34 first** —
`git branch -a` (not just `-r`) + read the MEMORY.md dock/RFC anchors before
touching either crate. This memo is safe to land (docs-only, zero code).

---
*See also:* memory `reference_hermes_kanban_worker_lanes_20260602`,
`project_master_worker_orchestration_rfc_posted_20260524`,
`project_desktop_embodiment_dock_20260601`.
