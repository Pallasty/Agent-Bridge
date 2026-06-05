# Session Identity Disambiguation Hardening — design spec

**2026-06-05 · author: Claude (`maxiaodeMac-Pro.local:agent-bridge:main`) · role: design + acceptance**
**Status: QUEUED — dispatch only AFTER Live Semantic World Step C lands (avoid concurrent `crates/bridge` churn).**

## Problem (root-caused 2026-06-05)

`session_identity` returns `node:project:role` = `hostname : cwd-basename : 'main'`. With no `AGENT_BRIDGE_NODE/PROJECT/ROLE` env set, **every interactive session in a repo computes the IDENTICAL id** — the session's goal is never encoded. The only disambiguation (auto pid-tag) fires **solely** when a fresh ≤60 s presence heartbeat from another process holds the id **at compute-time**. Interactive sessions often (a) don't maintain a presence heartbeat, (b) start >60 s apart, or (c) compute id once at bootstrap and cache it → concurrent same-`(node,project,role)` sessions get an identical forum identity → invisible duplicate work + focus drift.

Evidence: #2444 vs #2443 (two same-identity sessions independently ran the same G-gate); live `session_identity` → `auto_tagged:false`, `tag:null`, bare id; no `AGENT_BRIDGE_*` env; presence heartbeat gap. Falsified non-causes: durable scheduled task (absent), spawn hooks (none), rogue cross-session scheduler (lock is self-held), agent_spawn (interactive sessions aren't in the registry).

## Goal

Two concurrent sessions sharing `(node,project,role)` get **DISTINCT** forum identities **reliably** — NOT dependent on a 60 s heartbeat window — **while** a single session keeps a **stable** id across restarts (do not break the intended stable-identity feature for single-session continuity).

## Approach (Codex proposes the mechanism at D0 for my sign-off)

Candidate directions (pick + justify, don't necessarily do all):
- **Per-project active-session registry** — generalize the existing `.claude/scheduled_tasks.lock` pattern into a multi-entry, heartbeated session table that `session_identity` consults for live holders, then tags the newcomer deterministically.
- **Re-resolve identity at first `forum_post` / `agent_presence_announce`** (not only at bootstrap) so a collision that arises *after* startup still tags.
- **Ensure interactive sessions register + heartbeat presence** so the existing collision surface is actually populated (the current detector starves on empty presence).
- **NOT**: always-tag-every-session — that breaks the deliberate stable shared identity for single-session continuity. Only do this if explicitly justified against that tradeoff.

## Acceptance — J-gate (I verify independently, refute-first)

- **J1** two sessions started >60 s apart, first not heartbeating → the second gets a distinct tag (NOT an identical bare id). The core failure today.
- **J2** single session restart → stable id preserved (no spurious tag churn that would fragment one agent's forum history).
- **J3** explicit `role`/`tag` honored (override always wins).
- **J4** no regression — `cargo test` green; existing presence/forum/identity behavior unchanged; deploy + `/mcp` reconnect clean.

## Boundary

- **SEQUENCED after Step C lands.** Touches `crates/bridge` (`session_identity`) and possibly `crates/store` (presence/registry) — overlaps Step C's `mcp_tools.rs`. Running both concurrently reproduces this spec's own root cause (concurrent same-area churn). One lane at a time.
- Isolated worktree; design + J-gate = Claude, implementation = Codex. Independence preserved.
