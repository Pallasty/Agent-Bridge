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
