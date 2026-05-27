# DESIGN - Cross-project event spine roadmap for Agent-Bridge

**Status**: design draft, verify-first backlog, 2026-05-27.
**Author**: `aio2:agent-bridge:master#eac41c7` (working tree had unrelated `skills_route` edits when drafted).
**Trigger**: scan `/Data/CascadeProjects` for reusable mechanisms that can improve Agent-Bridge.
**Decision frame**: borrow mechanisms only when they strengthen Agent-Bridge's existing role as an agent runtime bridge. Do not import full sibling architectures when a smaller sidecar or audit lane is enough.

---

## 0. Executive decision

The strongest cross-project theme is not "add more tools". Agent-Bridge already has many useful tool surfaces. The next leverage point is a typed, replayable, explainable **event spine** that ties together:

- MCP tool calls and failures.
- `skills route` / skill recommendation decisions.
- `agent_spawn` sessions and lifecycle transitions.
- IDE bridge commands and snapshots.
- memory search / bootstrap recall choices.
- Pet/Xiaoshu presence, voice, and renderer state.
- future Seed/Xiaoshu adaptive surfaces.

This should start as an additive sidecar over the current SQLite store and JSONL logs. SQLite remains the operational source of truth. The event spine supplies provenance, replay, audit, and evaluation.

---

## 1. Current Agent-Bridge baseline

| Surface | Current state | Evidence | Gap |
|---|---|---|---|
| MCP dispatch telemetry | Present: every tool call records timing, ok/error, sizes, client/profile/source/model/codex_host. | `crates/mcp/src/server.rs`, `record_mcp_tool_call_telemetry`; `mcp_dispatch_audit`. | Aggregate audit exists, but no durable tool atlas with learned failure modes/workarounds. |
| Skills routing | CLI and MCP `skills_route` are present in the current working tree. | `crates/bridge/src/skills.rs`, `route_payload_for_store`; `crates/bridge/src/mcp_tools.rs`, `SkillsRouteTool`. | No effectiveness feedback loop after a skill is recommended or used. |
| Agent sessions | Stored with runtime, cwd, start/end, exit code, stdout/stderr. | `crates/store/src/sqlite.rs`, `sessions`; `agent_session_list/get/wait`. | No structured lifecycle event stream or concurrency guard policy. |
| Forum/presence/work memory | Mature coordination surfaces exist. | `forum_digest`, `work_memory`, `agent_presence_*`. | Event-to-memory sediment is still mostly manual and non-replayable. |
| Instinct observer | Hardened and observability-only after null-path validation. | `docs/design/ECC_INSTINCT_MINING_PROBE_2026_05_24.md`. | Useful as a cautionary tale: validate sensors before building miners. |

---

## 2. Borrow map

| Source project | Mechanism worth borrowing | Agent-Bridge translation | Confidence |
|---|---|---|---|
| `nexus-civilization` | Append-only EventStore with hash chain, Arrow/DuckDB export, replay lanes. | Add `ab event` sidecar: typed events, hash verification, optional DuckDB/Parquet export, replay fixtures. | High |
| `AiOT` | Cursor-based event streams, typed sidecar contracts, `disabled/shadow/active` promotion gates, `/proc` heartbeat. | Add event stream readers and health publishers with explicit schemas and cursor discipline. Promotion gates for consumers. | High |
| `openkoi` | Tool Atlas, tool failure modes, usage pattern miner, skill effectiveness, token-budgeted recall. | Extend `mcp_dispatch_audit` into persisted reliability/failure-mode intelligence. Add skill outcome feedback and recall priority shaping. | High |
| `deer-flow` | Subagent lifecycle events, polling timeouts, subagent concurrency clamps, sandbox path masking. | Harden `agent_spawn`: event transitions, concurrency cap, bounded wait/poll semantics, virtual-path masking in bridge outputs. | High |
| `OpenHands` | Event stream subscribers, loop-prevention event IDs, paged event cache, observation masking condenser, risk taxonomy. | Add event IDs/loop prevention and condenser stages for bootstrap/work memory. Add unified `low/medium/high` risk hints. | High |
| `warp` | Terminal block metadata and request-id/service-id IPC framing. | Upgrade IDE bridge from JSONL-only fallback toward live IPC when an extension is available; keep JSONL as fallback. | Medium-high |
| `agent-bridge-seed` | Encoder signature, theme-only novelty probe, replay-from-source sidecar. | Add schema fingerprints for memory/skill indexes and explain retrieval by theme vs structural similarity. | High |
| `ai-os-memory` | Cost/resource monitors and adaptive quality reduction under pressure. | Add health/cost/resource context to dashboard and tool exposure decisions. Use as a signal, not as autonomy. | Medium |
| `Symbiosis` / `LuminaCore` | Scheduler, load balancing, dashboards. | Later: feed backend selection and surface dashboards after the event spine exists. | Low-medium |

---

## 3. Track backlog

### AB-EVENT-1 - Typed append-only event spine

**Goal**: create a replayable event sidecar without replacing SQLite.

**Minimum event fields**:

```text
schema_version
event_id
ts
source
actor
project
cwd
event_type
subject_id
summary
payload_json
source_event_ids
prev_hash
hash
```

**Initial producers**:

- MCP tool call telemetry.
- MCP tool failure ring.
- `skills_route` recommendation events.
- `agent_spawn` session start/end/failure.
- `ide_command` enqueue/response.

**Verification gate**:

- Write/read round trip preserves event order.
- Hash-chain verifier detects tampering.
- Export is read-only and does not mutate existing Agent-Bridge tables.
- Replay fixture can rebuild per-tool call counts equal to `mcp_dispatch_audit` for a fixed window.

### AB-TOOL-1 - Tool Atlas over dispatch telemetry

**Goal**: turn raw tool telemetry into operational intelligence.

**Borrowed shape**:

- `tool_name`
- `total_calls`
- `total_failures`
- `reliability`
- `last_failure_reason`
- `failure_type`
- `learned_workaround`
- `confidence`

**Implementation posture**:

Start as a derived read model over existing `mcp_tool_calls` and `mcp_tool_errors`. Persist later only if derived computation becomes expensive or if learned workarounds need durable edits.

**Verification gate**:

- Atlas output agrees with `mcp_dispatch_audit` totals for the same filters.
- At least one known failing tool produces a categorized failure mode.
- No profile tuning suggestion is emitted without supporting call/error evidence.

### AB-SKILL-1 - Skill effectiveness feedback

**Goal**: close the loop after `skills_route` recommends a skill.

**Events**:

- `skill_route.suggested`
- `skill_route.loaded`
- `skill_route.used`
- `skill_route.outcome`

**Scoring inputs**:

- user accepted/ignored route.
- task finished with tests/build/verification.
- lint/risk class of selected skill.
- repeated use for same category.

**Verification gate**:

- A dry-run task can record route -> use -> outcome without reading full skill bodies unless selected.
- Route ranking can show an "effectiveness evidence" block without changing base semantic retrieval.

### AB-AGENT-1 - Agent spawn lifecycle and concurrency guard

**Goal**: make spawned agents observable and bounded.

**Events**:

- `agent.started`
- `agent.running`
- `agent.completed`
- `agent.failed`
- `agent.timed_out`
- `agent.killed`

**Policy**:

- default concurrency cap per backend.
- bounded polling wait.
- stale running-session detection.

**Verification gate**:

- a successful one-shot spawn emits start and completed events.
- an unavailable backend emits failed with actionable reason.
- concurrent spawn requests above cap are rejected or queued deterministically.

### AB-CTX-1 - Budgeted recall and condenser pipeline

**Goal**: improve `session_bootstrap` and precompact context shaping.

**Borrowed order**:

1. anti-patterns and active error patterns.
2. task-relevant skills.
3. durable lessons/decisions.
4. similar prior tasks/work memories.
5. masked historical observations.

**Verification gate**:

- per-block token budgets are honored.
- old bulky observations are masked instead of injected verbatim.
- bootstrap still surfaces `session_handoff` and `work_memory` first when present.

### AB-SEC-1 - Unified risk taxonomy and virtual path masking

**Goal**: make bridge outputs safer and easier to reason about.

**Risk levels**:

- `low`: read-only, project-local inspection.
- `medium`: project-scoped edit/execution/install.
- `high`: system/global mutation, privilege escalation, untrusted code, secret exfiltration, destructive operations.

**Verification gate**:

- `shell_exec`, `agent_spawn`, mobile install/debug, skill install, and IDE command surfaces can expose a risk hint.
- local host paths in bridge-mediated output can be masked to stable virtual paths when a workspace mapping exists.
- path traversal tests cover `..`, backslash traversal, and mixed virtual/host paths.

### AB-IPC-1 - IDE bridge live IPC with JSONL fallback

**Goal**: improve IDE embedded capability while preserving current fallback reliability.

**Design**:

- request id.
- service id.
- framed payload.
- success/failure response.
- JSONL command file remains fallback when live extension is absent.

**Verification gate**:

- `ide_command` behavior is unchanged without live IPC.
- with IPC enabled, request/response correlation is deterministic.
- stale or crashed extension falls back to JSONL without losing command records.

### AB-SEED-1 - Index schema signature and perception probe

**Goal**: catch embedding/index drift and make retrieval explanations less opaque.

**Borrowed shape**:

- encoder/index signature over dimensions, labels, tokenizer/model, and ranking knobs.
- theme-only similarity readout separate from structural similarity.
- novelty vs recent centroid.

**Verification gate**:

- memory/skill index reports a stable signature.
- changing an index-relevant field changes the signature.
- `skills_route` or memory search can optionally show why top results matched.

### AB-EVAL-1 - Replay benchmark lanes for ranker/tool changes

**Goal**: do not change retrieval/tool ranking without replay evidence.

**Lanes**:

- baseline current behavior.
- candidate algorithm.
- optional shadow runtime.

**Verification gate**:

- fixed fixture produces comparable per-lane metrics.
- report includes coverage, agreement, deltas, runtime overhead, and source event ids.
- production ranking changes require a saved replay report.

### AB-DASH-1 - Health, cost, and resource pressure publisher

**Goal**: make local environment pressure visible to Agent-Bridge, Seed, and Xiaoshu.

**Signals**:

- CPU/memory pressure.
- tool call latency and error rate.
- MCP profile/tool exposure fit.
- optional token/cost estimates when available.
- stale heartbeat checks.

**Verification gate**:

- resource pressure can reduce noncritical dashboard/render work without hiding critical alerts.
- health report includes provenance: repo commit, dirty flag, timestamp, and schema version.

---

## 4. Sequencing

### Phase 0 - verify and document

- Publish this design.
- Publish board tasks.
- Verify current support for each track with read-only commands.
- Freeze falsifiers before implementation.

### Phase 1 - event spine and atlas

Build `AB-EVENT-1` and `AB-TOOL-1` first. They create the evidence substrate for every later change.

### Phase 2 - feedback loops

Build `AB-SKILL-1`, `AB-AGENT-1`, and `AB-CTX-1`. These start using the event spine to improve behavior.

### Phase 3 - safety and IDE transport

Build `AB-SEC-1` and `AB-IPC-1` once the event spine can audit changes.

### Phase 4 - Seed/Xiaoshu product surface

Build `AB-SEED-1`, `AB-EVAL-1`, and `AB-DASH-1` to expose the runtime state as an explainable, adaptive product surface.

---

## 5. Non-goals

- Do not replace SQLite with DuckDB in the operational path.
- Do not auto-apply learned workarounds or behavioral memories without review.
- Do not build a full provider router unless Agent-Bridge becomes a model host.
- Do not turn Xiaoshu into the scheduler. Xiaoshu should be the embodied surface over Agent-Bridge/Seed state, not a second control plane.
- Do not add always-loaded bootstrap content without a token-budget gate.

---

## 6. Product interpretation: Agent-Bridge, Seed, and Xiaoshu

The strongest product shape is:

```text
Agent-Bridge = runtime bridge, tools, telemetry, coordination, memory surfaces
Seed         = implicit perception / novelty / adaptive substrate
Xiaoshu      = embodied UI surface over state, attention, and ritual cues
```

Xiaoshu can become an independent product surface if it stays grounded in Agent-Bridge's event spine and Seed's perception layer. It should not need to own core scheduling or data truth. Its independent value is:

- read-only operational awareness.
- adaptive visual/voice presence.
- attention and review cues.
- human-friendly explanations of what the agent network is doing.

That gives Xiaoshu an extension path across IDE, local dashboard, terminal, and Mac app renderer without coupling it to one host UI.

---

## 7. Board payload

When posted to the forum/design board, use this task list:

1. `AB-EVENT-1`: typed append-only event spine sidecar.
2. `AB-TOOL-1`: Tool Atlas from MCP dispatch telemetry.
3. `AB-SKILL-1`: skill effectiveness feedback loop.
4. `AB-AGENT-1`: agent_spawn lifecycle events and concurrency guard.
5. `AB-CTX-1`: budgeted recall and condenser pipeline.
6. `AB-SEC-1`: unified risk taxonomy and virtual path masking.
7. `AB-IPC-1`: IDE live IPC with JSONL fallback.
8. `AB-SEED-1`: index signature and perception probe.
9. `AB-EVAL-1`: replay benchmark lanes.
10. `AB-DASH-1`: health/cost/resource publisher.

Initial implementation recommendation: start with `AB-EVENT-1` plus `AB-TOOL-1`, because they create evidence for every other track.

---

## 8. Phase 0 status verification - 2026-05-27

Read-only verification was run after publishing the design thread. This section records the current state before implementation.

### Commands used

```text
git status --short
git diff --check -- docs/design/CROSS_PROJECT_EVENT_SPINE_ROADMAP_2026_05_27.md
rg -n "mcp_tool_calls|mcp_tool_errors|mcp_dispatch_audit|record_mcp_tool_call|tool_atlas|failure_modes|learned_workaround" crates -g '*.rs'
rg -n "skills_route|skills_recommend|skill_effectiveness|skill_route|route_payload_for_store|route_skill_hits|outcome" crates -g '*.rs'
rg -n "save_session|finalise_session|agent_session|in_flight|max.*session|concurrency|timed_out|wait|agent_spawn" crates/agent crates/store crates/bridge/src/mcp_tools.rs -g '*.rs'
rg -n "event_id|prev_hash|hash_chain|event spine|append-only|source_event_ids" crates docs -g '*.rs' -g '*.md'
rg -n "session_bootstrap per-block|WORK_MEMORY_KIND|format_work_memory_block|error_pattern|token budget|mask|condenser|anti_pattern|session_handoff" crates/bridge/src/mcp_tools.rs crates/store/src -g '*.rs'
rg -n "risk_level|security_risk|SecurityPolicy|allow_shell_exec|mask.*path|sanitize.*path|path traversal|virtual path" crates/bridge/src crates/store/src crates/agent/src -g '*.rs'
rg -n "ide-commands.jsonl|ide-responses.jsonl|queue_ide_command|UnixStream|request_id|service_id|ipc|JSONL|snapshot" crates/bridge/src/ide.rs crates/bridge/src/mcp_tools.rs crates/bridge/src/daemon_http.rs -g '*.rs'
mcp_dispatch_audit(window_days=7, source=codex, top_n=10)
```

### Verification matrix

| Track | Status | Evidence | Implementation posture |
|---|---|---|---|
| `AB-EVENT-1` | gap, with reusable local pieces | `shadow_cortex` has event ids/source ids/replay fixtures; avatar and IDE surfaces already use append-only JSONL; no unified typed event spine or hash chain. | Build additive event spine sidecar, not a DB replacement. Reuse shadow-cortex replay concepts. |
| `AB-TOOL-1` | ready first | `mcp_tool_calls`, `mcp_tool_errors`, and `mcp_dispatch_audit` exist. Live audit saw 479 Codex calls over 7 days, 4 errors, all `agent_spawn`/`kilo` missing. No `tool_atlas` or learned workaround store exists. | Start as derived read model over current telemetry; persist only learned workaround state later. |
| `AB-SKILL-1` | blocked on current dirty `skills_route` state, then ready | `skills_route` exists in current working tree, but the files are dirty. No `skill_effectiveness` or route outcome tracking exists. | First resolve/commit current skills route changes, then add feedback events. |
| `AB-AGENT-1` | partial | Sessions store start/end/exit/stdout/stderr and `agent_session_wait` has timeout behavior. No concurrency cap or structured lifecycle event stream. Live audit found `agent_spawn` failures caused by missing `kilo`. | Use `agent_spawn` failure as first Tool Atlas failure mode and add lifecycle events after event spine v0. |
| `AB-CTX-1` | partial | `session_bootstrap` has per-block token budgets, `session_handoff` priority, `error_pattern`, and `work_memory`. No condenser/masking pipeline for old bulky observations. | Defer until event spine and Tool Atlas exist; then add masking as a bounded bootstrap improvement. |
| `AB-SEC-1` | partial | `SecurityPolicy` env gates exist. `risk_level` exists mainly in avatar/pet surfaces. No unified tool-risk taxonomy or bridge-wide virtual path masking. | Define taxonomy first; apply to high-risk tools incrementally. |
| `AB-IPC-1` | partial | IDE bridge uses `ide-commands.jsonl`, `ide-responses.jsonl`, and snapshot JSON. Daemon/avatar surfaces already use request ids in places. No live IDE IPC transport. | Keep JSONL fallback; design live IPC only after event spine can audit command delivery. |
| `AB-SEED-1` | partial | Memory has novelty probes, coactivation centroids, shadow-cortex signal schema. No index/encoder schema signature and no theme-only explanation path. | Start with signature reporting before changing retrieval ranking. |
| `AB-EVAL-1` | partial | L6 eval examples and shadow-cortex replay fixtures exist. No generic replay lanes for tool/ranker changes. | Reuse shadow-cortex fixture/report pattern for event spine replay. |
| `AB-DASH-1` | partial | `doctor`, `capabilities`, avatar health/presence, and dispatch audit exist. No general resource/cost pressure publisher. | Defer until event spine can carry health events; then add `/proc`/resource publisher. |

### Current implementation order after verification

1. Resolve the dirty `skills_route` working-tree state before depending on it.
2. Implement `AB-EVENT-1` minimal sidecar schema and verifier.
3. Implement `AB-TOOL-1` derived Tool Atlas from existing `mcp_tool_calls` and `mcp_tool_errors`.
4. Use the observed `agent_spawn` -> missing `kilo` failures as the first real atlas/failure-mode fixture.
5. Only after the event spine is producing evidence, continue to `AB-SKILL-1` and `AB-AGENT-1`.
