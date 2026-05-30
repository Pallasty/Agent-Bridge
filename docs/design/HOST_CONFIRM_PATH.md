# Host-confirm path — design memo

**Lane:** Linux Computer Use (thread 79) · **Status:** design + A-MVP in progress · **2026-05-30**

The four desktop tools are **isolated-only**: host mutation is structurally unreachable
through MCP (the wrapper never passes `--confirm`). This memo designs the deliberate
crossing of that boundary — letting `desktop_action`/`desktop_invoke` touch the **real**
desktop behind a human-in-the-loop confirmation. See [LINUX_COMPUTER_USE.md](LINUX_COMPUTER_USE.md) §3, §7.

## Priority order (decided): A → C → B

1. **A — two-phase `notify` + token** (foundation). Host-targeted call does not execute;
   it mints a token, stores a pending record, fires a desktop `notify`, and returns a
   *pending* envelope. A separate `desktop_confirm <token>` executes it. Self-contained,
   per-action, the safe default. **Build first** — everything else builds on this machinery.
2. **C — pre-authorized capability window** (convenience escalation). A human grants a
   time-boxed, scope-limited token up front; within the window, host actions execute
   without a per-action pending step. Reuses A's audit/store. Coarser ⇒ **opt-in, after A**.
3. **B — `present()` approval card** (best UX). Render an interactive approve/reject card
   via the output lane (#92). Needs a present **round-trip** (server write-back), which E2's
   current client-side filter/sort (`b361104`) does not provide ⇒ **last, coordinate with present owner**.

## The crux — threat model, stated honestly

On a single box where the agent has shell access, host mutation **cannot** be made
cryptographically agent-proof: the agent could read the pending file, the notification
store, etc. So A is **not** a sandbox against an adversarial agent. Its job is narrower
and real:

> **Prevent host mutation from ever happening as a silent side-effect.** Force every
> host action into a distinct two-phase op with a mandatory pending state, a
> human-readable summary, a human-visible `notify`, and an audit record of both phases —
> so a human deliberately assents before the real desktop is touched.

In the conversational loop the human-in-the-loop is concrete: the agent surfaces the
pending summary to the user and asks; the **user's assent in chat is the approval**; only
then does the agent call `desktop_confirm`. The token correlates the two phases and the
notify mirrors the request onto the screen. We document this honestly rather than claim a
guarantee we can't enforce.

## A — design

### Backend (`desktop_invoke.py` first, mirror to `desktop_action.py`)

Two new modes, alongside the existing `gate()`:

- `--request-host-confirm` — for a host (non-isolated, non-dry-run) target. **Locate** the
  element (validate it exists + build a summary) but **invoke nothing**. Mint
  `token = secrets.token_hex(16)`; write a pending record and return
  `{schema, pending:true, token, summary, expires_at, rc:0}`.
- `--confirm-token TOKEN` — load the pending record; validate (exists, unconsumed,
  `now ≤ expires_at`); mark **consumed** (single-use); then execute the stored **selector**
  (re-resolved fresh, with internal host-acknowledge — justified because a human approved).

Pending store: `~/.cache/agent-bridge/desktop_pending/<token>.json`
`{schema, ts, kind:"invoke", selector, action, summary, expires_at, status:"pending|consumed"}`.
Default TTL 120 s. Both phases append to the existing `desktop_invoke_audit.jsonl`.
The pending record stores the **selector**, not a stale handle — the element is re-resolved
at confirm time so the action reflects the live tree.

### MCP surface

- `desktop_invoke` gains `confirm_host: bool`. When `confirm_host && host target` (no
  `cage_pid`, not `dry_run`): instead of `host_invoke_not_exposed`, the wrapper runs the
  backend with `--request-host-confirm`, fires a `notify` (summary + token) to the host
  desktop, and returns the pending envelope `{pending, token, summary, expires_at}`.
  Without `confirm_host`, host targets still return `host_invoke_not_exposed` (default
  stays closed).
- New tool **`desktop_confirm`** `{token, timeout_ms?}` → backend `--confirm-token` →
  executes → returns the invoke result. Tier::Standard, not codex-essential.

### Security properties

- Default posture unchanged: a normal `desktop_invoke` on a host target is still DENIED.
  Host mutation requires the **explicit** `confirm_host:true` *and* a subsequent
  `desktop_confirm(token)` — two distinct, separately-auditable calls.
- Single-use, TTL-bounded tokens: a token executes at most once and expires.
- Every phase audited; the notify surfaces the pending action on the human's screen.
- `--i-understand-this-touches-the-real-desktop` remains the backend's internal host-ack,
  now reached only via a validated token (a human-approved confirm), never by the agent
  directly.

## C — pre-authorized capability window (shipped)

A human mints a time-boxed, scope-limited **grant** with
`scripts/desktop_grant.py grant --kind invoke|action [--app X] [--name Y] [--action click] --ttl S [--max-uses N]`
(also `list` / `revoke <id>|--all`). It writes `~/.cache/agent-bridge/desktop_grants/<id>.json`
`{kind, scope:{app,name,action}, expires_at, max_uses, uses, status}`. Within the window a
**covered** host action runs without a per-action pending token: the MCP tools gain
`use_grant:true`, which passes `--use-grant` to the backend; the backend calls
`find_matching_grant(kind, app, name, action)` (app/name substring, action exact) — if a
live grant covers it, it executes and `record_grant_use` increments the counter; otherwise
DENIED. Default-closed (no `use_grant`, or no covering grant ⇒ refused). Bounded by
**ttl + max_uses + scope + revoke**, every use audited with the `grant_id`.

The grant CLI is **human-only — deliberately NOT exposed via MCP** (the desktop_* tools
only *check* grants, never mint them). Same honest threat model as path A: on a shell-
accessible box this is not agent-proof; it requires a deliberate human pre-authorization
and bounds blast radius, rather than sandboxing an adversarial agent. C weakens per-action
review (window-blind within scope) — it is the opt-in escalation for trusted repetition,
strictly after the safe default (A).

Shared store: `scripts/desktop_confirm_store.py` holds both the one-shot tokens (A) and the
grants (C). Acceptance: `scripts/desktop_accept/run_grant_accept.sh` (cover / deny /
max-uses / expiry / revoke / scope-mismatch, 8/8).

## B — sketch (last, coordinate with present #92)

`present()` renders an interactive approve/reject card carrying the pending summary; the
human clicks Approve; the present runtime writes back the decision; the desktop backend
(polling the pending record, or via a present→tool callback) then executes. Requires a
present **server round-trip** that E2 does not yet expose. Best UX; gated on present-lane work.
