# Remote Session Steering — SOP & Design (P1–P4)

**Status**: P0 validated · P1 SOP (this doc, zero-code) · P2/P3 shipped as `remote_steer` module + `agent_steer_*` tools · P4 shipped as `agent_orchestrate_scan`.
**Origin**: forum thread #91; memory `agentbridge_remote_session_steer_gap_20260529`.
**Boundary (non-negotiable)**: *execution / collection* may be remotely driven; *research judgment* stays human-gated. Blind auto-answering of approval/quota gates is forbidden — those surface as `needs_human` (see biocortex S8d audit #1745 on why unattended research breeds true-by-construction conclusions).

---

## Why this exists

An interactive CLI agent (`codex resume`, `claude`) blocks on stdin and does **not** poll the
Agent-Bridge inbox, so XM v0.2 (`agent_message` + wake-signal) cannot reach it. The fix is not a
new PTY broker: a long-lived agent started inside a **named tmux session** can be both
attached (human-drive, preserving the accumulated context that anchors against drift) and
written to programmatically (`tmux send-keys`). That was validated end-to-end against a real
codex TUI (`• PONG`) on aio2.

## The convention

Long-lived steerable sessions have a **logical handle** `ab:<project>:<role>`
(e.g. `ab:biocortex-rs:codex`) used in presence, docs, and tool output.

tmux, however, rewrites `:` (its `session:window` target separator) and `.` to `_`, so the literal
**tmux session name** is the colon-free form:

```
ab__<project>__<role>          # delimiter '__', each component reduced to [A-Za-z0-9-]
```

e.g. `ab__biocortex-rs__codex`, `ab__aiot__reviewer`. The `ab__` prefix is what makes a session
discoverable as AB-owned and drivable; `agent_steer_list` and `agent_orchestrate_scan` filter on it.

⚠️ tmux target gotcha: the `=` exact-match prefix applies only to **session-target** commands
(`has-session`, `kill-session`, `attach` → use `-t =ab__…`). **Pane-target** commands
(`send-keys`, `capture-pane`) reject `=name` ("can't find pane") — use the **bare** name there
(`-t ab__…`), which still resolves to the exact session when it exists.

---

## P1 — Manual SOP (zero code, use any time)

### 1. Start the agent inside a named tmux (on the node that will host it)

```bash
# On the host (e.g. aio2). Requires tmux installed there.
scripts/ab-steer-launch.sh biocortex-rs codex -- codex resume
# …or by hand (note the tmux-safe name):
tmux new-session -d -s ab__biocortex-rs__codex 'codex resume'
```

### 2. Attach to drive it as a human (preserves the live context)

```bash
# From anywhere on the tailnet:
ssh -t pallasting@100.93.4.56 'tmux attach -t =ab__biocortex-rs__codex'
# (magicDNS is flaky on this tailnet — prefer the IP. SSH key: ~/.ssh/id_ed25519.)
```

Detaching (`Ctrl-b d`) leaves the agent running with its context intact; reconnect later and the
session is exactly where you left it. This is the recommended default entry point: it is the
remote-drive that **cannot** drift, because it is the same process and the same context.

### 3. (Optional) one-shot programmatic nudge without attaching

```bash
# pane-target commands use the BARE session name (no '=')
ssh pallasting@100.93.4.56 "tmux send-keys -t ab__biocortex-rs__codex -l 'status?' \; send-keys -t ab__biocortex-rs__codex Enter"
ssh pallasting@100.93.4.56 "tmux capture-pane -p -t ab__biocortex-rs__codex -S -40"
```

⚠️ Blind `send-keys` can be swallowed by a startup/approval gate. For programmatic driving prefer
the gate-aware `agent_steer_drive` tool (P2/P3) over raw send-keys.

---

## P2/P3 — AB-owned launch + gate-aware driver (`agent_steer_*`)

Implemented in `crates/bridge/src/remote_steer.rs` (pure mux/ssh/gate logic, unit-tested) with thin
MCP tool wrappers in `crates/bridge/src/mcp_tools.rs`. A `Multiplexer` abstraction keeps the API
from hard-binding to tmux (tmux is the only backend today; screen/dtach/pty-broker can follow).

| Tool | Purpose |
|------|---------|
| `agent_steer_launch` | AB starts `ab:<proj>:<role>` in a detached mux session (local or remote node via ssh), registers a steer handle into presence. |
| `agent_steer_drive`  | gate-aware: send input → settle/poll for `expect` → auto-answer **only** auto-answerable gates (trust-dir) → surface quota/approval/unknown gates as `needs_human`. Echoes a `purpose` (`exec`/`collect`/`research`); `research` flags the output as requiring a human ground-truth gate. |
| `agent_steer_capture`| read + clean (ANSI-stripped) pane contents. |
| `agent_steer_list`   | list live `ab:` sessions on a target (mux truth) joined with presence handles. |
| `agent_steer_kill`   | kill a steerable session + best-effort presence cleanup. |

**Gate policy** (the real work is here, not in send-keys):
- *auto-answerable*: trust-this-folder prompt → `Enter` (only when `auto_gate:true`, default).
- *needs_human*: quota / model-switch, command-approval, and any unrecognized prompt → driver
  stops and returns the gate excerpt. The operator answers (or pre-empts by launching with a
  low-gate profile: pre-trusted dir + `--dangerously-bypass-approvals-and-sandbox` / sandbox mode +
  a populated `~/.codex/AGENTS.md`, supplied via the launch `command`/`env`).

**Low-gate launch profile**: AB does not hard-code agent-specific bypass flags. Supply them through
`command` (e.g. `codex --dangerously-bypass-approvals-and-sandbox`) and `env` at launch; the chosen
profile is recorded in the presence steer handle for auditability.

---

## P4 — Blackboard multi-CC orchestration (`agent_orchestrate_scan`)

One orchestrator CC can supervise N remote worker CCs without holding their transcripts. The
bounded blackboard is AB presence + (optionally) `work_memory`:

**Worker status contract** — each worker keeps a compact status on its presence AgentCard under
`capabilities.steer_status`:

```json
{
  "focus": "S8e distractor falsifier",
  "last_action": "cargo test outcome_gated_retention — 2/2 green",
  "awaiting": null,                 // or a gate name the worker is blocked on
  "blockers": [],
  "needs_human_gate": false,        // true when a research judgment is pending
  "ts": "2026-05-29T17:40:00Z"
}
```

Workers refresh it via `agent_presence_announce(capabilities={steer_status:{…}})`. The orchestrator
calls `agent_orchestrate_scan` to get a **lazy roll-up** (summaries, never transcripts) of every
steerable worker + aggregate counts (`n_steerable`, `n_awaiting_gate`, `n_needs_human`). It pairs
this with `context_pressure_estimate` to self-monitor its own budget (pass the real `model_limit`
for 1M-context models, else it falsely reports saturated at 200k).

**Boundary in the loop**: the orchestrator may dispatch exec/collect work freely. Any worker output
that is a *research judgment* must pass a human ground-truth spot-check before it is treated as a
finding — `needs_human_gate:true` is the worker raising its hand for exactly that.

---

## Operational notes / constraints

- tmux must exist on the **target** node (installed locally via `brew install tmux`; aio2 has it).
- aio2's biocortex codex currently runs in a Cursor terminal (not tmux) → not attachable; to steer
  it, relaunch it inside `tmux new -s ab:biocortex-rs:codex` next time.
- ssh host: `pallasting@100.93.4.56:22`, key `~/.ssh/id_ed25519`. magicDNS unreliable → use the IP.
- codex weekly quota was <10% — a real budget constraint; the driver never auto-switches models.
- Deploying a rebuilt `agent-bridge` binary requires an MCP server reconnect to expose new tools.
