# Borrowed Patterns Backlog - 2026-06-09

Status: proposed backlog and first landing plan.

This note records local codebase patterns worth borrowing into Agent-Bridge.
It is intentionally a translation map, not a copy plan: some sources carry
licenses or experimental assumptions that make direct reuse undesirable.

## Goals

- Turn the workspace scan into durable Agent-Bridge memory and documentation.
- Separate implementation-grade patterns from older conceptual prototypes.
- Pick a small first slice that improves current Agent-Bridge behavior.
- Keep each borrowed idea tied to a verification path before code lands.

## Borrowable Patterns

### 1. MCP Lifecycle From Theia

Source:

- `../src/ai-mcp/src/browser/mcp-frontend-application-contribution.ts`
- `../src/ai-mcp/src/browser/mcp-command-contribution.ts`
- `../src/ai-mcp/src/node/mcp-server.ts`

Useful shape:

- Validate MCP server descriptions from preferences before they reach runtime.
- Diff old and new server maps, then add, update, or remove manager entries.
- Register tools under a provider namespace when a server starts.
- Unregister all tools for that provider when a server stops.
- Report started/configured state through user-facing commands.

Agent-Bridge translation:

- Add a read-only MCP lifecycle/status view before adding new write controls.
- Keep tool namespace and server namespace explicit in telemetry.
- Treat server config changes as a state transition, not an ad hoc side effect.

Risk:

- The Theia implementation is EPL/GPL Classpath. Borrow the architecture and
  behavior tests, not source text.

### 2. Workspace Boundary From Theia Workspace Agent

Source:

- `../src/ai-workspace-agent/src/browser/functions.ts`
- `../src/ai-workspace-agent/src/common/template.ts`

Useful shape:

- Resolve a single workspace root before file operations.
- Reject paths that escape the workspace.
- Respect user exclude patterns.
- Optionally respect `.gitignore`, with cached watcher invalidation.
- Teach the agent to verify paths step by step.

Agent-Bridge translation:

- Strengthen `ide_snapshot`, `ide_command`, and future IDE edit surfaces with
  explicit workspace containment evidence.
- Use the same contract for desktop/semantic-bus file-backed adapters when they
  expose local paths.

Risk:

- Path prefix checks must be canonicalized in Rust; string-prefix containment is
  not enough for symlinks or `..` segments.

### 3. Resource Change Broadcast From AIMemoryPalace

Source:

- `../AIMemoryPalace/src/vector_engine/mcp_service.py`

Useful shape:

- JSON-RPC resource list/register operations.
- Resource-changed notifications broadcast to other clients.
- Search results returned as URI-addressed matches with scores and metadata.

Agent-Bridge translation:

- Use as a conceptual model for Semantic System Bus object update packets.
- Prefer current MCP resources and Agent-Bridge event spine semantics over the
  older WebSocket protocol shape.

Risk:

- This source is an early prototype and not a modern MCP-compliant server.

### 4. Bidirectional State Synchronizer From QMSs

Source:

- `../QMSs/src/qfi/integration/symbiosis/core/bridge/state_synchronizer.py`
- `../QMSs/src/qfi/mcp/quantum/monitoring/sync_monitor.py`

Useful shape:

- Source-to-target field mapping tables.
- Cached source/target state.
- Conflict strategies such as `latest_wins` and `merge`.
- Bounded sync history.
- Callback dispatch after successful state transitions.
- Operation metrics: duration, data size, batch size, failure rate, cache hit rate.

Agent-Bridge translation:

- Use for memory-sync and presence-sync status modeling.
- Use for Semantic System Bus adapter conformance and runtime health history.
- Make conflict and health summaries visible before adding corrective actions.

Risk:

- Existing Agent-Bridge memory sync already has version-vector work; this should
  augment observability and adapters, not replace the conflict core.

### 5. Identity Boot From Nexus Civilization

Source:

- `../nexus-civilization/server/core/identity/agent_identity.py`
- `../nexus-civilization/server/core/systems/agent_boot.py`
- `../nexus-civilization/server/core/governance/agent.py`

Useful shape:

- Persistent identity seed, traits, lineage, and continuity log.
- Deterministic boot sequence: identity load, prompt assembly, recent memory
  recall, ACL filter, causal pull, continuity writeback.
- Governance loop shape: observe, diff, act, log.

Agent-Bridge translation:

- Feed Agent Avatar Protocol and presence with durable identity continuity.
- Add explicit "boot evidence" to future session bootstrap and avatar surfaces.
- Use governance-style observe/diff/log first; keep act paths gated.

Risk:

- Nexus is domain-specific. Borrow the stage model, not the game-world semantics.

### 6. File-Backed Session State From Claude-Code-Game-Studios

Source:

- `../Claude-Code-Game-Studios/.claude/docs/context-management.md`
- `../Claude-Code-Game-Studios/.claude/hooks/pre-compact.sh`
- `../Claude-Code-Game-Studios/.claude/hooks/log-agent.sh`

Useful shape:

- "The file is the memory, not the conversation."
- Pre-compact dump includes active state, changed files, WIP markers, recovery
  instructions, and a compaction log.
- Subagent start/stop audit trail is intentionally small and append-only.

Agent-Bridge translation:

- Continue using `work_memory` as short-lived state, but make recovery evidence
  more visible in hooks and readiness reports.
- Keep hook outputs bounded and resilient when optional dependencies are absent.

Risk:

- Shell hooks are frontend-specific; Agent-Bridge needs Rust core contracts plus
  thin frontend adapters.

### 7. MCP Reference Fixtures

Source:

- `../modelcontextprotocol/src/memory/index.ts`
- `../modelcontextprotocol/src/everything/everything.ts`
- `../modelcontextprotocol/typescript-sdk/src/inMemory.ts`

Useful shape:

- Graph memory fixture with entities, relations, and observations.
- Resource subscription/update notification fixture.
- In-memory transport pair for deterministic client/server tests.

Agent-Bridge translation:

- Use as conformance inspiration for Rust MCP tests and fixture payloads.
- Add adapter tests that verify tool schemas, resource reads, and cancellation
  without depending on a real stdio process.

Risk:

- Use local fixtures as behavioral references; keep Agent-Bridge protocol code
  aligned with current upstream docs when implementing changes.

## First Landing Slice

Pick a read-only slice before write-capable orchestration:

1. Add a borrowed-pattern backlog doc. Done in this file.
2. Persist a memory decision that captures the scan and priority order.
3. Verify current Agent-Bridge state:
   - MCP/memory/tool profile health.
   - runtime health for daemon-http and Palace.
   - semantic-bus conformance.
   - git cleanliness and current branch.
4. Publish a forum kanban thread with lanes:
   - Now: lifecycle/status observability.
   - Next: workspace boundary evidence.
   - Later: sync-state observability and identity boot continuity.
5. Implement the first small code slice only after the board is posted.

## Candidate Implementation Tasks

### AB-BORROW-1: MCP Lifecycle Status Digest

Outcome:

- A read-only summary that reports configured/running MCP surfaces, exposed tool
  counts, hot/failing tools, and missing runtime dependencies.

Likely reuse:

- Existing `capabilities`, `tool_atlas_snapshot`, `mcp_dispatch_audit`, and MCP
  server telemetry.

Acceptance:

- One command/tool returns a compact lifecycle digest.
- It does not start or stop servers.
- It marks daemon-http and Palace reachability separately from MCP stdio health.

### AB-BORROW-2: Workspace Boundary Evidence

Outcome:

- IDE and file-backed adapter reports include canonical root, containment status,
  and exclude-pattern evidence where available.

Acceptance:

- Path evidence is read-only.
- Symlink/`..` cases are tested with canonical paths.

### AB-BORROW-3: Sync-State History Packet

Outcome:

- Memory/presence/semantic-bus sync probes share a small status packet:
  state, last_sync_time, conflict_count, failure_count, and recovery hint.

Acceptance:

- Existing version-vector merge remains unchanged.
- Runtime-health and peer-conformance reports can render the packet.

### AB-BORROW-4: Identity Boot Evidence

Outcome:

- Session/avatar presence can show a compact boot evidence block:
  identity source, current focus, recent memory keys, lineage, and continuity
  writeback timestamp.

Acceptance:

- No private prompt or raw memory body is placed in presence rows.
- Evidence is compact and path/key based.

## Verification Notes From 2026-06-09

Initial MCP health check from Codex showed:

- MCP core tools are callable.
- Memory store is available.
- Shell execution through Agent-Bridge works.
- Event spine telemetry verifies a SHA-256 chain head.
- No other active presence rows were visible at the time of the check.
- `daemon-http` on `127.0.0.1:7878` and Palace on `127.0.0.1:7979` were
  unreachable in the local runtime-health probe.

That means the first implementation should treat HTTP/Palace availability as a
separate runtime concern rather than as proof that MCP itself is broken.

## Orca Borrows (2026-06-19)

Source: external evaluation of `stablyai/orca` (Electron/TS desktop ADE for fleets
of parallel CLI agents). Full plan + verification-status table in
`docs/design/ORCA_BORROW_PLAN_2026_06_19.md`; decision memory
`decision_orca_borrow_not_adopt_20260619`. Verdict = BORROW design only (same
"borrow-not-adopt" posture as rmux/camofox/SkillOpt/walkthrough-tdoc): Electron/TS
to Rust/MCP is a port not a drop-in, and orca is a multi-vendor GUI cockpit while
Agent-Bridge is a single-user backend. These are convergent-design borrows, NOT a
new subsystem. Each task carries an explicit pre-code verification gate.

**Status (verified 2026-06-26):** several borrows have since landed on master —
ORCA-1 (worktree_remove teardown safety) = `e3fc906`; ORCA-3 (prompt-injection
profile for steer, tracked in commit as forum OB-3) = `52ec1ba`; ORCA-6 (Codex
app-server read-only investigation) = DONE on branch
`spike/codex-appserver-host-channel` (memory
`session_handoff_codex_appserver_host_spike_20260620`). Separately the
changes_digest bounded patch-hunks borrow (forum OB-4) landed as `162e20a`. The
remaining ORCA-2 / ORCA-4 / ORCA-5 / ORCA-VERIFY items are still proposals. NOTE:
the commit-message "OB-N" enumeration is the forum numbering and does NOT line up
1:1 with this doc's "AB-BORROW-ORCA-N" IDs (forum OB-4 = changes_digest, not this
doc's ORCA-4 = annotation-as-steering).

### AB-BORROW-ORCA-1: worktree_remove teardown safety pipeline  [P1 — now]

Outcome:

- `worktree_remove` stops being a bare `git worktree remove [-f]` and gains
  defense-in-depth: path-safety reject (root/home/empty, canonicalized for
  symlink/`..`), git-registration verify, orphan-proof (`.git` points into THIS
  repo's admin dir), and SIGTERM of any agent/PTY whose cwd is under the worktree.

Likely reuse:

- `crates/agent/src/worktree.rs:72-81` (the remove fn), `agent_session_list` +
  `agent_kill` for the PTY-kill step, canonical-path rule from AB-BORROW-2.

Acceptance:

- Unit tests: dirty tree refused, root/home/empty rejected, foreign `.git`
  rejected, sibling session under path is SIGTERM'd before removal.
- No dependency on any orca wiki-only claim (design-level, orca-impl-independent).

Verification gate:

- None external — this is independently motivated by AB's own most-documented
  pain (CLAUDE-SIBLING S5/S6 + shared-tree churn / `.real`-clobber lessons). Ship
  behind the existing adversarial-audit-before-deploy discipline.

Boundary note:

- Borrow the small defensive checks only. Do NOT adopt orca's first-class
  worktree-object machinery (stable ID / store table / tri-modal create): orca
  isolates one-agent-per-worktree, AB's hazard is many-agents-in-ONE-shared-tree,
  which orca never has.

### AB-BORROW-ORCA-2: per-agent capability table + preflightTrust  [P2]

Outcome:

- Collapse the scattered `Frontend` match-arms (`crates/bridge/src/setup.rs:57`)
  into one declarative record per known agent CLI (launchCmd / expectedProcess /
  promptInjectionMode / resumeCommand / trustArtifact), read by
  `agent_steer_launch` / `agent_spawn`. Optionally pre-write the target CLI's
  trust artifact before injecting a steer prompt so an onboarding/trust prompt
  never swallows the first message.

Likely reuse:

- `setup.rs` Frontend enum, `agent_steer_launch`, remote_steer gate logic.

Acceptance:

- One capability table; adding a known CLI is a data row, not scattered arms.
- preflightTrust only lands if the swallow bug is reproduced (gate below).

Verification gate:

- FALSIFY FIRST: does AB's tmux-based steer actually hit "trust/onboarding prompt
  swallows the first injected message"? If yes, confirm the per-CLI trust-artifact
  format from orca SOURCE (wiki-only today) before relying on it. Config-table
  refactor itself has no orca dependency.

### AB-BORROW-ORCA-3: promptInjectionMode taxonomy for steer  [P2]

Outcome:

- `agent_steer_drive` gains an explicit injection-mode per target (argv /
  flag-prompt / flag-prompt-interactive / flag-interactive / stdin-after-start)
  plus a bracketed-paste + quiet-render readiness heuristic, replacing the
  best-effort settle + bare-Enter.

Acceptance:

- Each AB-supported backend tagged with a mode; steering a long prompt no longer
  drops the Enter / gets eaten by bracketed paste.

Verification gate:

- Validate against already-recorded steer gotchas (remote zsh equals-expansion
  family, long-prompt-not-submitted, has-session transient-false). orca's 5-mode
  union is primary-confirmed from source, so the taxonomy is trustworthy; the AB
  mapping is the work.

### AB-BORROW-ORCA-4: annotation-as-steering review loop  [P3 — demand-gated]

Outcome:

- A diff-line comment becomes a structured steer message injected back to the
  agent, collapsing review + instruction into one loop. Prereq: give
  `changes_digest` a hunk/patch scope (today it stops at numstat/name-status,
  `crates/bridge/src/project.rs:301`).

Likely reuse:

- `changes_digest` (+ new hunk scope), `present` / `build_walkthrough_html`,
  `present_await_decision` as the human gate, `agent_steer_drive` for injection.
  Forge write-back (pr_review/pr_comment/pr_merge) gated behind the human-confirm
  card — outward writes are NOT auto-authorized.

Acceptance:

- Step 1 (hunk scope) is small + unit-testable and lands first.
- Comment anchors to {file, line, commit/event-spine id}, preserving verify-first
  / no-green-laundering.

Verification gate:

- Demand-driven. Mirrors the deliberately-deferred Palace Review Artifact (tdoc
  comment round-trip judged "heavier than needed" on 2026-06-18). orca is a second,
  stronger data point that the round-trip is worth building WHEN there is demand.

### AB-BORROW-ORCA-5: dual graceful-degradation status channel  [P2 — coupled to Codex-no-hook]

Outcome:

- Worker status is observed via OSC stream-sniff (universal, hookless) AND an
  optional richer hook channel, degrading to a tui-idle / PaneSnapshot-diff
  heuristic. Closes the gap where steer_status is driver-written (an un-driven or
  hookless worker is invisible).

Likely reuse:

- `osc_parse` (OSC 9/99/133/777 already parsed), `agent_steer_capture`
  (PaneSnapshot cols/rows/cursor/highlighted), the SOP-P4 "worker posts
  steer_status" contract noted as not-yet-wired.

Acceptance:

- A hookless agent (e.g. Codex CLI) still surfaces live status to
  `agent_orchestrate_scan` via terminal-observe, not only last-drive state.

Verification gate:

- DIRECTLY couples to open question Q1 (Codex CLI has no hooks). FALSIFY: does
  Codex CLI emit any OSC (9999/133)? If yes, sniff it; if no, fall back to
  PaneSnapshot-diff / tui-idle. This reframes "Codex lacks a capability" as "AB
  lacks a hookless fallback observation channel" — which is exactly this task.

### 2026-06-20 verification update — Codex 0.141 host/hook surface (live-probed)

Empirical probe of Codex 0.141.0 on this machine OVERTURNED the "Codex has no
hooks" premise and reframed the AB-as-host "chimera" into two layers. Full
evidence + plan in `ORCA_BORROW_PLAN_2026_06_19.md` §8. Key facts:

- Codex has CC-compatible hooks (`~/.codex/hooks.json`: PreCompact/Stop/SessionEnd/
  UserPromptSubmit/PostToolUse); AB's hooks are installed AND trusted
  (`config.toml [hooks.state]` trusted_hash per hook) AND firing today
  (`hook-runs.jsonl`). AB is ALREADY a cross-CC+Codex cognitive substrate via
  convergent contracts (MCP + hooks.json) — zero per-CLI code.
- => Layer 1 (memory/lifecycle) is LIVE, not a build. The only open gate is
  fire-but-fail: `ab-precompact-hook` parses the CC payload shape (session_id +
  transcript JSONL) with no CLI branch; verify Codex's payload parity.
- => Layer 2 (fleet/host) is the real chimera frontier and Codex exposes a
  cleaner host channel than tmux screen-scrape (see AB-BORROW-ORCA-6).

### AB-BORROW-ORCA-6: Codex app-server as a structured host channel  [P2 — read-only investigation first]

Outcome:

- Evaluate driving an AB-hosted Codex via its `app-server` / `--remote
  ws://|unix://` / `remote-control` / `exec-server` programmatic control plane
  (orca-relay-like) instead of `remote_steer`'s tmux `capture-pane` screen-scrape.
  Screen-scrape is lossy (PaneSnapshot parses terminal chars); app-server gives
  structured events/state = qualitatively cleaner host integration.

Likely reuse:

- `remote_steer.rs` launch/observe path (as the fallback), the Multiplexer trait
  (a non-tmux backend could fill PaneSnapshot from app-server events).

Acceptance:

- A read-only assessment of app-server protocol stability (it carries an
  EXPERIMENTAL tag) and whether it exposes the lifecycle/status signals AB's
  orchestrate_scan needs. No code lands until stability is confirmed.

Verification gate:

- app-server/remote-control are flagged EXPERIMENTAL by Codex — do NOT build on
  it until the protocol is confirmed stable across a Codex minor bump. Investigate
  only; keep tmux capture-pane as the working baseline.

### AB-BORROW-ORCA-VERIFY: Codex pre_compact payload parity  [P1 — Layer 1 gate, GATED on owner for prod write]

Outcome:

- Confirm Codex actually produces non-empty curate output on pre_compact (not just
  fires the hook). NOTE (2026-06-20 read-only probe): `ab-precompact-hook` is
  ALREADY Codex-format-aware (transcript located under `~/.codex/sessions`; turn
  extraction branches on `response_item`/`payload`/`input_text`/`output_text`,
  matching the real Codex rollout jsonl) — so the fire-but-fail gate is largely
  CLOSED. The only residual is whether Codex delivers `session_id` in the hook
  stdin payload (the hook also falls back to `CLAUDE_SESSION_ID`).

Acceptance:

- A Codex session triggers compact and `session_curate`/`session_finalize` write
  real distilled memories (verified non-empty), OR the payload mismatch is found
  and `ab-*-hook` gains a CC-vs-Codex transcript-locating branch.

Verification gate:

- Triggering compact runs curate, which WRITES to the production state.db — a
  production write that is GATED on owner approval. Alternative read-only probe:
  exercise only the UserPromptSubmit injection path (read-only) to confirm payload
  parses. NOTE: `hook-runs.jsonl` output_bytes is a hardcoded-0 placeholder in
  ab-precompact-hook and CANNOT be used to judge fail.

### Parked (design-level, no current demand)

- Durable PTY-host process surviving daemon redeploy (orca forked node-pty daemon
  + token-auth Unix socket) — would ease `.real`-clobber orphan-session pain;
  validates AB's tmux-session-survives-the-client model. Park.
- completion -> phone push + remote follow-up injection (mobile dimension's only
  transferable nugget) — `notify`/Notifier trait gains a remote backend. Low
  priority: owner co-locates with the agents. Park.
