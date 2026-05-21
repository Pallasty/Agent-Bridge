# RFC - v25: Agent Shadow Cortex

Status: draft, 2026-05-19.
Predecessors:
- `DESIGN-v22-agent-bridge-memory-substrate.md` - direct memory-substrate route.
- `SEED-VALUE-ASSESSMENT-2026-05-15.md` - project-decoupling decision.
- `DESIGN-P-epsilon-substrate-readiness-audit.md` - read-only substrate readiness metrics.
- `RFC-v24-agent-avatar-protocol.md` - portable agent state and presence projection.

Trigger: Nexus Civilization has validated a safer Seed integration pattern:
rules decide world changes, Seed emits structured attention signals, and the
advisor explains those signals without giving Seed authority over game state.
Agent-Bridge should use the same pattern for agent work before reconsidering
any default `AB_SUBSTRATE=1` memory-substrate route.

---

## 1. Decision

Introduce an **Agent Shadow Cortex** as a sidecar, shadow-only attention layer
for Agent-Bridge.

One-line rule:

> Agent-Bridge tools execute and audit work; Seed notices which work is
> important, surprising, risky, or continuous; agents consume those signals as
> hints, not commands.

This keeps the 2026-05-15 project-decoupling decision intact. Seed remains an
AiOT research substrate. Agent-Bridge does not make Seed its critical path.
Instead, Agent-Bridge becomes a real workload provider and evaluator for Seed.

---

## 2. Goals

| Goal | Acceptance |
|---|---|
| G1: Add a stable attention-signal contract | `AgentAttentionSignal` can describe memory, tool, skill, forum, hook, and presence attention without naming a Seed runtime |
| G2: Keep default behavior unchanged | No change to `memory_search`, tool dispatch, hook output, or Codex tool exposure when shadow cortex is disabled |
| G3: Reuse real Agent-Bridge event streams | Signals can be produced from MCP dispatch telemetry, memory query logs, forum posts, git/session events, and hook lifecycle events |
| G4: Support heuristic-first, Seed-second rollout | `heuristic` is the default implementation; `seed-shadow` and `seed-runtime` require explicit opt-in |
| G5: Produce feedback useful to Seed | Shadow reports capture where Seed helped, where it over-ranked noise, latency cost, and human/agent acceptance |
| G6: Provide advisor/router hints without authority | Signals may influence summaries, skill recommendations, bootstrap ordering, and audit views, but not direct tool execution |

---

## 3. Non-goals

- Do not enable `AB_SUBSTRATE=1` on the canonical daemon by default.
- Do not replace `memory_search`, FTS, semantic search, or coactivation.
- Do not let Seed execute MCP tools, write memories, submit commands, or mutate
  presence state.
- Do not expose new Essential-profile tools before the signal quality is known.
- Do not treat Seed salience as proof of task importance without evidence.
- Do not create a second narrative where Agent-Bridge success depends on Seed
  research success.

---

## 4. Product Shape

Nexus pattern:

```text
WorldEngine / CommandPipeline  = adjudication
Seed World Substrate           = attention
LLM Advisor                    = explanation
```

Agent-Bridge pattern:

```text
MCP tools / hooks / store       = execution and audit
Agent Shadow Cortex            = attention
Agent clients / skills / memory = explanation and optional routing hints
```

The crucial product boundary is the same: Seed returns structured signals, not
natural language advice and not actions.

---

## 5. Core Contract

Version marker:

```json
{
  "agent_shadow_cortex": 1
}
```

Minimum signal:

```json
{
  "agent_shadow_cortex": 1,
  "tick": 42,
  "at": "2026-05-19T18:40:00Z",
  "scope": "tool",
  "subject_id": "mcp_dispatch_audit",
  "signal_type": "risk",
  "salience": 0.82,
  "reason_codes": ["tool_failure_spike", "codex_profile_relevant"],
  "source_event_ids": ["dispatch:1779210682:abc"],
  "ttl_secs": 3600
}
```

Recommended full signal:

```json
{
  "agent_shadow_cortex": 1,
  "tick": 42,
  "at": "2026-05-19T18:40:00Z",
  "scope": "tool",
  "subject_id": "mcp_dispatch_audit",
  "signal_type": "risk",
  "salience": 0.82,
  "reason_codes": [
    "tool_failure_spike",
    "codex_profile_relevant",
    "recent_user_task"
  ],
  "source_event_ids": [
    "dispatch:1779210682:abc",
    "forum:6:264"
  ],
  "ttl_secs": 3600,
  "evidence": {
    "source": "mcp_dispatch",
    "count": 3,
    "window_secs": 604800,
    "profile": "essential",
    "model": "gpt-5.5"
  },
  "consumer_hints": [
    "include_in_session_bootstrap",
    "show_in_dream_weekly"
  ],
  "confidence": 0.64
}
```

### 5.1 Field Rules

| Field | Rule |
|---|---|
| `scope` | One of `memory`, `tool`, `skill`, `forum`, `hook`, `presence`, `repo`, `session`, `avatar`, `system` |
| `subject_id` | Stable compact target id, such as a memory key, tool name, thread id, hook name, file path, or project slug |
| `signal_type` | One of `surprise`, `risk`, `opportunity`, `continuity`, `anomaly`, `saturation`, `handoff` |
| `salience` | Float `0.0..1.0`; not an authority score |
| `reason_codes` | Machine-readable tags; no prose-only signals |
| `source_event_ids` | IDs needed for replay and audit |
| `ttl_secs` | Short enough that stale attention naturally expires |
| `evidence` | Small structured proof, not a transcript |
| `consumer_hints` | Optional downstream surfaces allowed to read the signal |

---

## 6. Event Sources

| Source | Current substrate value | Example reason codes |
|---|---|---|
| `mcp_dispatch` | Codex/model/profile/tool behavior | `tool_failure_spike`, `native_overlap`, `hot_tool`, `cold_tool`, `profile_mismatch` |
| `memory_query_log` | Recall success/failure and query pressure | `repeated_miss`, `high_latency`, `semantic_drift`, `project_relevant` |
| `forum_posts` | Cross-agent announcements and coordination | `decision_post`, `stale_rediscovery`, `parallel_owner`, `needs_ack` |
| `git_events` | Repo churn and release state | `remote_advanced`, `dirty_overlap`, `release_candidate`, `high_risk_diff` |
| `hook_lifecycle` | Precompact/session-end/stop behavior | `hook_failure`, `schema_contract_risk`, `curation_due` |
| `skill_usage` | Skill search, install, and usage outcome | `skill_candidate`, `skill_success`, `skill_rejected`, `security_review_due` |
| `presence/avatar` | Agent state and collaboration loops | `blocked_agent`, `handoff_available`, `avatar_state_changed` |

The first implementation should start with `mcp_dispatch`, `memory_query_log`,
and `forum_posts`. They already have real data, clear replay value, and direct
relevance to Codex tool routing.

---

## 7. Implementations

### 7.1 `NullAgentShadowCortex`

Safe no-op for disabled mode, tests, and rollback.

### 7.2 `HeuristicAgentShadowCortex`

Deterministic baseline. It scores events with explicit rules:

- repeated memory misses in a project window -> `risk`
- tool failures for the active Codex profile -> `risk`
- hot native-overlap tool in Codex -> `opportunity`
- forum post with release or design decision markers -> `handoff`
- dirty worktree plus remote advancement -> `risk`
- skill candidate with installable source and high match -> `opportunity`

This baseline is required so Seed can be judged against something real.

### 7.3 `SeedShadowAgentCortex`

Feature-flagged adapter that:

1. runs the heuristic baseline;
2. encodes Agent-Bridge events into primary/secondary perception vectors;
3. emits additional `seed_shadow` signals;
4. records side-by-side comparison metrics.

It does not require AiOT `seed_neuron` at runtime.

### 7.4 `SeedRuntimeAgentCortex`

Optional true Seed runtime bridge. The first implementation is an ephemeral
in-process replay over `ab-seed-bridge::SeedBackend<HashBackend>`; it calls the
same Rust Seed runtime used by the v22 substrate, but never installs the global
substrate, writes snapshots, or contacts the AiOT production daemon. Later
implementations may call a future MLX-backed runtime, but only under explicit
environment flags.

Runtime failure must degrade to deterministic shadow scoring.

---

## 8. Environment Flags

| Flag | Meaning |
|---|---|
| `AGENT_BRIDGE_SHADOW_CORTEX=off` | Disabled, returns no signals |
| `AGENT_BRIDGE_SHADOW_CORTEX=heuristic` | Default target for first ship |
| `AGENT_BRIDGE_SHADOW_CORTEX=seed-shadow` | Run heuristic plus deterministic Seed-shaped shadow scoring |
| `AGENT_BRIDGE_SHADOW_CORTEX=seed-runtime` | Run heuristic plus an explicit Seed runtime replay probe |
| `AGENT_BRIDGE_SHADOW_CORTEX_REPORT=1` | Write replayable side-by-side reports |
| `AGENT_BRIDGE_SHADOW_CORTEX_MAX_SIGNALS=N` | Clamp per-window output |

This is intentionally separate from `AB_SUBSTRATE`. `AB_SUBSTRATE` wraps the
embedding backend for memory substrate experiments. Shadow cortex observes
agent events and emits attention hints.

---

## 9. Allowed Consumers

| Consumer | Allowed use | Not allowed |
|---|---|---|
| `session_bootstrap` | Add a compact "Attention Signals" block | Reorder all memories solely by Seed salience |
| `skills_recommend` | Add a task-specific hint that a skill is worth checking | Auto-install or auto-run a skill |
| `mcp_dispatch_audit` | Show signals explaining profile/tool pressure | Demote tools automatically |
| `dream weekly` | Summarize top shadow-cortex signals and deltas | Declare Seed success from one week of correlation |
| avatar/presence surfaces | Show compact focus/risk cues | Treat avatar state as proof of work |
| future Codex tool router | Bias suggested toolset/profile in dry-run | Change live MCP exposure without explicit setup/restart |

---

## 10. Feedback Loop for Seed

This RFC explicitly treats Agent-Bridge as a real-world workload provider for
Seed, but not as a dependent critical path.

Feedback artifacts:

| Artifact | Purpose |
|---|---|
| Shadow report JSON | Side-by-side heuristic vs Seed signal ranking |
| Accepted-signal log | Which signals the agent/user actually used |
| Ignored-signal log | Which high-salience signals were noise |
| Latency envelope | Per-event and per-window runtime cost |
| Replay fixtures | Stable event windows from real work for AiOT regression |
| Human review notes | Qualitative examples of helpful or misleading attention |

Promotion rule:

Seed output can move from "research signal" to "product hint" only if it
beats the heuristic baseline on replayed windows and does not degrade latency,
clarity, or safety.

This gives Seed more usage experience and feedback without turning Agent-Bridge
into a narrative-shopping machine.

---

## 11. Evaluation Gates

### Gate A: Heuristic baseline

Pass criteria:

- produces stable JSON signals from at least `mcp_dispatch`, `memory_query_log`,
  and `forum_posts`;
- has unit tests for no-op, scoring, sorting, expiry, and replay;
- writes no new memories and runs no tools;
- can render a dry-run report from the current `state.db`.

### Gate B: Seed shadow

Pass criteria:

- deterministic `seed-shadow` report is replayable;
- top Seed-only signals include source IDs and reason codes;
- heuristic and Seed ranks are compared on at least 5 real windows;
- obvious false positives are visible in the report;
- disabled mode produces byte-equivalent downstream behavior.

### Gate C: Runtime bridge

Pass criteria:

- runtime failure falls back without failing the caller;
- p95 overhead stays under the agreed budget for Codex work;
- report includes runtime metrics analogous to `n_alive`, `step_count`,
  `mean_surprise`, `max_surprise`, and `depth_ratio` when available;
- runtime does not write to memory, forum, presence, or tool dispatch tables.

### Gate D: Consumer integration

Pass criteria:

- first consumer is read-only, preferably `dream weekly` or a CLI report;
- second consumer may be `session_bootstrap` behind a feature flag;
- no default `memory_search` ranking changes until offline recall evaluation
  beats current behavior.

---

## 12. First Implementation Slice

Recommended PR 1:

1. Add `crates/bridge/src/shadow_cortex.rs`.
2. Define `AgentAttentionSignal`, `SignalScope`, `SignalType`, and
   `ShadowCortexMode`.
3. Implement `NullAgentShadowCortex` and `HeuristicAgentShadowCortex`.
4. Add a CLI mirror:

   ```text
   agent-bridge dream shadow-cortex
       [--json]
       [--window-days N]
       [--max-signals N]
       [--source mcp_dispatch|memory|forum|all]
   ```

5. Add a read-only MCP tool only after the CLI report is useful.
6. Do not expose it in `codex-essential` until we see dispatch demand.

Current Gate A implementation status:

- `agent-bridge dream shadow-cortex` exists as a CLI-only, read-only report.
- It emits stable JSON from `mcp_dispatch`, `memory_query_log`, and
  `forum_posts`.
- It supports `--source all|mcp_dispatch|memory|forum|codex`, where `codex`
  narrows MCP dispatch telemetry to `source=codex`.
- It does not register a new MCP tool or change the Codex Essential surface.

Recommended PR 2:

1. Add deterministic event encoder.
2. Add `seed-shadow` scoring without true runtime.
3. Add side-by-side report artifacts.
4. Compare against Nexus-style attention qualitative review.

Current Gate B prep status:

- `agent-bridge dream shadow-cortex --fixture-out PATH` writes a deterministic
  replay fixture with normalized `events[]` plus the typed aggregate snapshots
  used by the heuristic scorer.
- `agent-bridge dream shadow-cortex --fixture-in PATH` rebuilds the heuristic
  report from that fixture instead of live `state.db`.
- Fixture replay is still CLI-only and does not register MCP tools, write
  memories, or call a Seed runtime.
- `seed-shadow` scoring now runs as a deterministic second scorer over the same
  fixture. It emits `seed_shadow_signals` plus `comparison.lane_coverage` for
  `heuristic`, `seed_shadow`, and `seed_runtime`.
- `comparison.verdict` uses explicit `ablation_state` /
  `insufficient_coverage` / `rank_tie_guarded` /
  `salience_saturation_guarded` guardrails before any correlation-style
  conclusion. This absorbs the v22 rank-tie pathology lesson and the first
  Mac-side saturation sweep: zero-coverage lanes are not negative evidence, and
  top-K signals that all hit a salience cap are not reliable rank evidence.
- `dream weekly` is now the first read-only consumer. It emits a compact
  `shadow_cortex` JSON summary and a `[bonus #4]` text one-liner over the
  Codex MCP lane. The full replay/evidence surface remains on
  `dream shadow-cortex`.
- `agent-bridge dream shadow-cortex-feedback record|list` now captures
  explicit accepted/ignored feedback as JSONL under
  `~/.cache/agent-bridge/shadow-cortex/feedback.jsonl` by default. This is
  intentionally outside `state.db`.
- `dream weekly` also summarizes the last 7 days of feedback counts, so
  accepted/ignored signal quality can be watched without opening the full
  JSONL log.

Recommended PR 3:

1. Add optional Seed runtime bridge.
2. Keep it off by default.
3. Add replay fixtures and runtime budget gates.
4. Keep `salience_saturation_state` visible in the comparison output so Gate C
   can distinguish Seed runtime quality from capped heuristic baselines.

Current Gate C feasibility status:

- `AGENT_BRIDGE_SHADOW_CORTEX=seed-runtime` now evaluates an explicit
  `seed_runtime` lane using an ephemeral `SeedBackend<HashBackend>` replay over
  the normalized Shadow Cortex events.
- Runtime evidence includes per-event `step_count`, surprise stats, and
  `neighbors`, plus explicit booleans showing it does not mutate the global
  substrate, write snapshots, or call the AiOT daemon.
- `comparison.verdict` becomes `seed_runtime_ready_for_review` when the runtime
  lane has coverage and passes the rank-tie/salience-saturation guards. This is
  intentionally a review verdict, not permission to wire runtime output into
  `session_bootstrap`, MCP exposure, or retrieval ranking.
- The runtime probe remains CLI/weekly only and read-only; any production
  daemon, Bench C, iter-11, or MLX adapter work is out of scope for this gate.

---

## 13. Why Not Direct `AB_SUBSTRATE=1`

The v22 memory-substrate route wraps the embedding backend and learns topology
from memory events. That is still a valid research seam, but current Agent-Bridge
signals do not justify default promotion:

- P-epsilon audits still show a hairball regime and low L2 coverage.
- Recent AiOT findings emphasize degenerate-pass detection and longer
  observation windows.
- Nexus shows that product value appears earlier when Seed is an attention
  layer, not an authority layer.
- Codex tool-routing work needs task/tool/session signals more than raw memory
  topology.

Therefore shadow cortex is the safer next move: useful feedback for Seed,
useful hints for Agent-Bridge, and reversible by design.

---

## 14. Open Questions

1. Should shadow reports live under the state directory or `~/.cache/agent-bridge`?
2. How should accepted/ignored feedback graduate from cache JSONL into a
   stronger evaluation artifact, if the weekly loop proves useful?
3. Should `forum_posts` be an input in the first PR, or only in replay mode to
   avoid accidental coordination bias?
4. How should later consumers follow `dream weekly` without widening
   `session_bootstrap` too early?
5. How should cross-device sync transport replay fixtures without syncing
   private tool telemetry by default?

---

## 15. Current Recommendation

Start with the CLI-only heuristic baseline. Do not add a new MCP tool yet.
The first live value is observability: a compact report that shows what the
agent should have noticed across tools, memory, forum, and repo state.

After the baseline is trusted, add `seed-shadow` and compare it against the
heuristic report. Only then consider a true Seed runtime bridge.
