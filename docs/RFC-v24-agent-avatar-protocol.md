# RFC - v24: Agent Avatar Protocol

Status: draft, 2026-05-18.
Predecessors:
- `DESIGN-v19-presence-identity.md` - identity and `agent_presence` rows.
- `RFC-v20-tailscale-daemon.md` - cross-machine presence transport.
- `DESIGN-v23-codex-pet-presence-loop.md` - Xiao Shu / Codex pet presence loop.

Trigger: Phase 6 proved that Agent-Bridge can keep the official Codex pet
package stable while writing richer sidecar state and projecting it into
presence metadata. The next step is to make that state portable across Codex,
Claude Code, Warp, Gemini CLI, Auggie, local CLI, and daemon peers.

---

## 1. Goals

| Goal | Acceptance |
|---|---|
| G1: Define a runtime-neutral avatar state object | Non-Codex agents can read and write the core state without knowing Codex pet atlas geometry |
| G2: Keep Codex compatibility as an adapter | Existing `pet_state_get`, `pet_state_set`, `pet_state_ritual`, and official pet packages remain valid |
| G3: Reuse presence as the shared product surface | `agent_presence` rows can carry the same avatar state under `capabilities.avatar_state` or the compatibility key `capabilities.pet_state` |
| G4: Keep lifecycle modes stable | Rich detail lives in optional facets, not new top-level `mode` values |
| G5: Keep voice safe by default | Protocol fields never imply audio unless an output adapter applies an explicit sparse-gate policy |

## 2. Non-goals

- Do not define a sprite or animation package format.
- Do not require non-Codex runtimes to implement Codex pet rows, atlas size, or avatar selection UI.
- Do not add a mutating runtime-neutral MCP tool in this RFC.
- Do not add new Essential-profile tool exposure.
- Do not define remote control or orchestration semantics for other agents.
- Do not use avatar state as proof of work without separate command or test evidence.

---

## 3. Terminology

| Term | Meaning |
|---|---|
| Avatar protocol | The runtime-neutral state object defined by this RFC |
| Compatibility target | A frontend-specific renderer or contract, such as the Codex custom pet package |
| Input adapter | Code that translates frontend events into avatar protocol updates |
| Output adapter | Code that renders or publishes avatar protocol state |
| Sidecar state | Local JSON state stored under the Agent-Bridge state directory |
| Presence projection | Copying compact avatar state into `agent_presence.capabilities` |

---

## 4. Core Object

Version marker:

```json
{
  "agent_avatar_protocol": 1
}
```

Minimum portable object:

```json
{
  "agent_avatar_protocol": 1,
  "agent_id": "maxiaodeMac-Pro.local:agent-bridge:main",
  "runtime": "codex",
  "avatar_id": "xiao-shu-dev",
  "mode": "working",
  "updated_at": "2026-05-18T14:39:45Z"
}
```

Recommended full object:

```json
{
  "agent_avatar_protocol": 1,
  "agent_id": "maxiaodeMac-Pro.local:agent-bridge:main",
  "runtime": "codex",
  "avatar_id": "xiao-shu-dev",
  "project": "agent-bridge",
  "cwd": "/Users/pallasting/Projects/agent-bridge",
  "mode": "working",
  "activity_state": "verifying",
  "focus": "tests",
  "risk_level": "low",
  "blocked_reason": null,
  "evidence": "cargo test -p ab-bridge pet_state passed",
  "next_action": "sync presence",
  "voice_policy": {
    "default_silent": true,
    "allowed_modes": ["verified", "failed", "waiting_for_user", "handoff"],
    "voice": "Flo",
    "rate": 190
  },
  "compat": {
    "codex": {
      "pet_id": "xiao-shu-dev",
      "package_contract": "codex-pet-atlas-8x9-v1"
    }
  },
  "updated_at": "2026-05-18T14:39:45Z"
}
```

---

## 5. Field Contract

### 5.1 Required Fields

| Field | Type | Rule |
|---|---|---|
| `agent_avatar_protocol` | integer | Must be `1` for this RFC |
| `agent_id` | string | Stable identity. Prefer `session_identity` convention: `node:project:role[:tag]` |
| `runtime` | string | Runtime label such as `codex`, `claude-code`, `warp`, `gemini-cli`, `auggie`, or `local-cli` |
| `avatar_id` | string | Stable avatar identity. It does not have to be a Codex pet id |
| `mode` | string | Stable lifecycle mode from section 6 |
| `updated_at` | string | RFC3339 UTC timestamp |

### 5.2 Optional Context Fields

| Field | Type | Rule |
|---|---|---|
| `project` | string | Compact project slug |
| `cwd` | string | Local working directory, if safe and useful |
| `session_id` | string or null | Frontend session id, when available |
| `source` | string | Writer label, such as `mcp:pet_state_set` or `hook:session-end` |
| `reason` | string | Human-readable reason for the latest update |

### 5.3 Optional Behavior Facets

| Field | Type | Rule |
|---|---|---|
| `activity_state` | string | Fine-grained posture such as `planning`, `reading_diff`, `implementing`, `verifying`, `documenting` |
| `focus` | string | Compact domain label such as `mcp`, `hooks`, `presence`, `voice`, `docs`, `tests` |
| `risk_level` | string | `low`, `medium`, or `high`; UI hint only |
| `blocked_reason` | string or null | Short actionable reason when user or peer input is needed |
| `evidence` | string | Compact proof string, not a transcript |
| `next_action` | string | Next local step for presence panels and handoff |

Behavior facets are optional and forward-compatible. Missing facets mean
"unknown", not failure.

### 5.4 Voice Policy

`voice_policy` is optional and advisory.

```json
{
  "default_silent": true,
  "allowed_modes": ["verified", "failed", "waiting_for_user", "handoff"],
  "voice": "Flo",
  "rate": 190
}
```

Rules:

- Absence of `voice_policy` means silent by default.
- `default_silent=false` must not be assumed by adapters unless explicitly set.
- `allowed_modes` is a gate, not an instruction to speak.
- Output adapters must still respect their own enable flags, cooldowns, and user settings.

### 5.5 Compatibility Block

`compat` stores adapter-specific hints. It must not be required by the core
protocol.

```json
{
  "compat": {
    "codex": {
      "pet_id": "xiao-shu-dev",
      "package_contract": "codex-pet-atlas-8x9-v1"
    }
  }
}
```

Rules:

- Unknown compatibility targets are ignored.
- Core readers must not parse `compat.codex` to understand lifecycle state.
- Non-Codex writers may omit `compat` entirely.

---

## 6. Lifecycle Modes

The `mode` enum stays intentionally small:

| Mode | Meaning |
|---|---|
| `idle` | No active task or intentionally quiet |
| `orienting` | User intent received; agent is gathering context |
| `working` | Agent is implementing, executing, or otherwise doing task work |
| `reviewing` | Agent is reading, checking, planning, or comparing |
| `waiting_for_user` | Agent needs user input |
| `failed` | A command, test, or requested action failed and needs attention |
| `verified` | Concrete verification or completion evidence exists |
| `handoff` | Session is ending or state is being handed to future context |

Do not add mode values for every animation or mood. Add optional behavior
facets instead.

---

## 7. Storage And Projection

### 7.1 Sidecar Storage

Local sidecar state should live under the Agent-Bridge state directory, not a
Codex-specific directory. The existing `pet_state` path remains the Codex
compatibility path:

```text
<agent-bridge-state-dir>/pet_state/<pet_id>.json
```

Future runtime-neutral state may use:

```text
<agent-bridge-state-dir>/avatar_state/<avatar_id>.json
```

This RFC does not require that new path yet.

### 7.2 Presence Projection

Presence is the shared product surface. Projection should use compact fields:

```json
{
  "capabilities": {
    "avatar_state": {
      "agent_avatar_protocol": 1,
      "avatar_id": "xiao-shu-dev",
      "mode": "working",
      "activity_state": "verifying",
      "focus": "tests",
      "risk_level": "low",
      "blocked_reason": null,
      "evidence": "cargo test -p ab-bridge pet_state passed",
      "next_action": "sync presence"
    },
    "pet_state": {
      "pet_id": "xiao-shu-dev",
      "mode": "working"
    },
    "voice_policy": {
      "default_silent": true,
      "allowed_modes": ["verified", "failed", "waiting_for_user", "handoff"]
    }
  }
}
```

Compatibility rule:

- During migration, `pet_presence_sync` may continue writing `capabilities.pet_state`.
- New cross-runtime surfaces should prefer `capabilities.avatar_state`.
- If both exist, `avatar_state` is canonical and `pet_state` is the Codex
  compatibility projection.

### 7.3 Size Policy

Projection values must stay compact. Do not place command transcripts, large
logs, images, or memory dumps in presence rows. Use paths, identifiers, and
short evidence strings.

---

## 8. Adapter Model

| Adapter | Input | Output | Required support |
|---|---|---|---|
| Codex | Hooks and MCP calls | Official pet, sidecar state, TTS, notification | `pet_state_*` compatibility tools |
| Claude Code | Settings hooks and MCP calls | Sidecar state, presence, TTS, notification | MCP plus optional hooks |
| Warp | Shell integration, wrappers, MCP calls | Presence, terminal status, optional panel | No lifecycle hook dependency |
| Gemini CLI | MCP/config-driven events | Sidecar state and presence | Thin adapter until hooks exist |
| Auggie/local CLI | MCP or wrapper events | Sidecar state and presence | No Codex dependency |
| Daemon/HTTP peer | HTTP or MCP event ingestion | Cross-machine presence and panel | Protocol-first, renderer optional |

Input adapters may be lossy. Output adapters must be safe by default.

---

## 9. Compatibility And Versioning

Readers:

- Must ignore unknown fields.
- Must tolerate missing optional fields.
- Must reject or downgrade unsupported `agent_avatar_protocol` major versions.
- Should treat absent `agent_avatar_protocol` plus Codex-shaped `pet_state` as
  legacy v23 compatibility state.

Writers:

- Must write `agent_avatar_protocol: 1` when producing runtime-neutral state.
- Should preserve existing compatibility fields when updating a known state
  object, unless the caller explicitly clears them.
- Must not infer verification from `mode=verified` without an `evidence` string
  or external proof.

Version rule:

- Additive optional fields do not change the protocol version.
- Removing or changing the meaning of a required field requires a new major
  protocol number.

---

## 10. Migration Plan

### Stage 1 - RFC and vocabulary

- Land this RFC.
- Keep v23 as the Codex presence-loop design.
- Treat Phase 6 fields as the behavior facet vocabulary for protocol v1.

### Stage 2 - Read-only capability probe

Add a diagnostic tool that reports which adapter surfaces are available:

- hooks
- MCP
- presence
- TTS
- notification
- terminal
- HTTP daemon
- Codex pet package compatibility

This must be read-only.

Implementation status: implemented as Standard-profile MCP tool
`avatar_adapter_capabilities` on 2026-05-18. Release and installed-binary stdio
probes passed. A post-restart Codex dispatch audit confirmed the default
Codex-facing profile remains `essential`, so this Standard tool does not expand
the Codex Essential tool surface. It does not write sidecar state, emit TTS, or
send notifications.

### Stage 3 - Runtime-neutral state tools

Start with read-only `avatar_state_get`, which projects existing Codex-compatible
`pet_state` sidecar JSON into protocol v1 without mutating files. Then add
`avatar_state_set` or a compatibility alias that writes protocol v1 state. Keep
`pet_state_set` stable for existing Codex callers.

Implementation status: `avatar_state_get` is implemented as a Standard-profile
read-only tool on 2026-05-18. Debug and installed-binary stdio probes passed.
Mutating `avatar_state_set` is intentionally not started yet.

### Stage 4 - Presence projection migration

Project protocol v1 into `capabilities.avatar_state` while continuing to emit
`capabilities.pet_state` for Codex compatibility.

Implementation status: `pet_presence_sync` now emits both
`capabilities.avatar_state` and compatibility `capabilities.pet_state` on
2026-05-18. Debug and installed-binary Standard probes passed. An installed
`AGENT_BRIDGE_CLIENT=claude-code` runtime-label probe also passed. The first
CLI heartbeat dogfood is captured below; long-running non-Codex client-session
dogfood remains pending.

Native CLI status: `agent-bridge avatar sync-presence` now calls the same shared
projection path as `pet_presence_sync`, defaults to `runtime=local-cli`, and
uses the CLI process cwd unless `--cwd` is supplied. It is intended for
terminal wrappers, launchd heartbeats, and non-MCP agent clients. It writes
presence only; it does not mutate the official Codex pet package, emit audio,
or expand Codex Essential tool exposure. Debug dogfood on 2026-05-19 wrote
`agent_id=local-cli-avatar-heartbeat-dogfood` / `runtime=local-cli` /
`activity_state=heartbeat-probe`, and `/avatar-surface` read it back with a
fresh heartbeat age of 10 seconds.

Native launchd status: `agent-bridge avatar install-heartbeat`,
`avatar heartbeat-status`, and `avatar remove-heartbeat` now manage a per-user
LaunchAgent wrapper around `avatar sync-presence`. The installer defaults to a
stable launchd label as both `session_id` and `agent_id`, preventing one-shot
launchd pid churn from creating a new presence row on every interval.
Installed-binary dogfood on 2026-05-19 wrote
`~/Library/LaunchAgents/com.agentbridge.avatar-heartbeat.agent-bridge.plist`,
loaded it into `gui/501`, and kicked it immediately. `heartbeat-status` showed
`runs=2`, `last exit code=0`, and `run interval = 60 seconds`; `/avatar-surface`
read back `agent_id=com.agentbridge.avatar-heartbeat.agent-bridge`,
`runtime=local-cli`, `activity_state=launchd-heartbeat`, and heartbeat age
11 seconds.

Heartbeat health status: `agent-bridge avatar heartbeat-health` evaluates the
LaunchAgent, the actual binary named in the plist, and the stable presence row
through one shared read-only module. It reports launchd load state, run count,
last exit code, interval, plist/log paths, binary path, binary command support,
presence freshness, and the projected avatar fields. This is the
operator-facing health answer for independent Xiao Shu runtime checks.

Binary drift guard: `agent-bridge avatar install-heartbeat` now prefers
`~/.local/bin/agent-bridge.real` when it exists, then falls back to
`~/.local/bin/agent-bridge`. This aligns with the existing wrapper/background
job layout and keeps the heartbeat on the stable real binary even if the
front-door `agent-bridge` path is replaced. `heartbeat-health` reports
`binary_missing` or `binary_missing_command` when the configured binary cannot
run the required avatar heartbeat command.

Sparse alert gate: `agent-bridge avatar heartbeat-alert` consumes the same
read-only health payload and maintains a local transition receipt. It emits
only on first-unhealthy, event-key transition, forced run, or repeat-due
unhealthy state. Desktop notifications are the default alert channel; TTS is
explicit via `--tts`. The command appends JSONL events with
`seed_ready.substrate_input=avatar_health_transition_v1`, giving the Seed
substrate a future perception stream while keeping this stage operational
without a substrate dependency.

Independent alert runner: `agent-bridge avatar install-heartbeat-alert`,
`heartbeat-alert-status`, and `remove-heartbeat-alert` manage a second per-user
LaunchAgent for the sparse alert gate. The runner executes `avatar
heartbeat-alert` on a slower interval than the presence writer, so the watcher
can still report a broken heartbeat writer. The first dogfood install used
`--tts --tts-voice Flo --tts-rate 190`; while health was unchanged/healthy, the
runner wrote a Seed-ready event but emitted neither notification nor TTS.

Seed perception adapter: `agent-bridge avatar seed-events` reads the avatar
heartbeat alert JSONL and projects each non-preview alert into the existing
`substrate replay` event schema: `{text, key, ts, kind}`. The adapter is
read-only and does not require `AB_SUBSTRATE=1`; it only prepares a replay log
that can be fed to Seed by an explicit operator action. The first dogfood pass
converted 4 non-preview `avatar_health_transition_v1` records and `substrate
replay --use-hash` consumed them with `step_count_final=4`.

Xiao Shu cortex v0: `agent-bridge avatar cortex-replay` creates an isolated
shadow-only Seed cortex for the avatar stream. It reuses `avatar seed-events`,
feeds the records into a fresh `SeedBackend`, and writes a dedicated snapshot
under `~/.local/share/agent-bridge/avatar_cortex/`. This is separate from the
global memory substrate, does not require `AB_SUBSTRATE=1`, and explicitly does
not restart or activate AiOT daemon/sibling-gated work. The v0 shape is a
single-stream cortex; a future v1 can map health, voice, and session signals to
AiOT's MultiModalGrid cortical plan after shadow evidence accumulates.

Cortex runner: `agent-bridge avatar install-cortex-runner`, `cortex-status`,
and `remove-cortex-runner` provide a per-user LaunchAgent for the shadow cortex.
The runner periodically executes `avatar cortex-replay`, writing only the
dedicated avatar cortex parquet and leaving the global memory substrate
untouched. `cortex-status` is the read-only operator surface that combines
launchd state with snapshot row/fingerprint information.

Cortex HTTP projection: `/avatar-surface/cortex-status` exposes the same
runner/snapshot payload to browser and non-MCP clients, while
`/avatar-surface/panel` renders a Cortex Status band beside heartbeat health.
This keeps the shadow cortex observable from the independent panel without
turning it into a live Seed subscription or mutating the global substrate.
The status payload also carries a read-only `events` summary from
`avatar seed-events` and a compact `trend` object so clients can compare
snapshot step, event count, latest health status, and snapshot/event lag
without reading the alert JSONL or cortex parquet directly.
`trend.learning_state` is a UI-facing interpretation layer with stable states:
`caught_up`, `learning`, `behind`, and `stale`. It is advisory only; it does not
emit voice, trigger notifications, or mutate the Seed substrate.
`trend.behavior_policy` is also advisory: it can provide a panel badge, hint,
recommended action, and voice preview text, but `voice.allowed` and
`notification.allowed` default to false in the read-only HTTP/panel surface.
`avatar cortex-language` and `/avatar-surface/cortex-language` add the first
dynamic Xiao Shu language layer on top of that state. It is a deterministic
phrase composer, not an LLM and not a voice model: it reads the cortex state,
latest health event, event-window counters, and project slug, then returns a
short Chinese utterance, alternatives, slots, generator metadata, and safety
flags. The optional `language.memory` block is also read-only: it summarizes the
visible `events.recent` window as stable, transitioning, mixed, or unhealthy
short-term context, but does not write to persistent Agent-Bridge memory or the
global Seed substrate. The surface reports `emits_audio=false` and preserves the
explicit emit gate as the only path toward future spoken output.
`avatar cortex-motion` and `/avatar-surface/cortex-motion` add the matching
renderer-neutral behavior layer. They derive `gesture`, `mood`, `attention`, and
`animation_hint` from the cortex/language state, but keep
`codex_pet_package_mutation=false` and `requires_renderer_mapping=true` so
official Pet assets remain a packaging boundary rather than an internal
extension point.
`avatar cortex-renderer` and `/avatar-surface/cortex-renderer` are the first
adapter dry-run on that boundary: they map `motion.animation_hint.renderer_token`
into `pose`, `expression`, `motion`, `accessory`, and timeline slots, while
reporting `writes_files=false`, `mutates_renderer=false`, and
`codex_pet_package_mutation=false`. Each mapping can carry
`mapping.evidence`, a review block with visual intent, acceptance criteria,
risk level, review questions, binding stage, and the recommended next step.
`avatar cortex-renderer-registry` and
`/avatar-surface/cortex-renderer-registry` summarize those mappings as a
read-only candidate registry with counts by binding stage and risk level plus
the current live renderer token.
`avatar cortex-binding-plan` and `/avatar-surface/cortex-binding-plan` turn the
registry into the first safe implementation plan. They select only low-risk
resolved candidates, defer `needs_review` and fallback tokens, and expose the
phases, validation checklist, rollback points, and safety flags required before
any real renderer binding. The surface remains read-only and reports
`writes_files=false`, `mutates_renderer=false`, and
`codex_pet_package_mutation=false`.
`avatar cortex-binding-fixture` and `/avatar-surface/cortex-binding-fixture`
freeze the selected plan candidates into deterministic sidecar preview fixtures.
The surface emits slot-timeline golden payloads for `soft_bounce` and
`idle_breathe`, per-token assertions, return-to-idle and under-2s acceptance
gates, and the same mutation safety flags. These fixtures are review evidence
for a later sidecar visual adapter, not official package writes.
`avatar cortex-visual-adapter` and `/avatar-surface/cortex-visual-adapter`
consume those fixtures and project each slot timeline into observable preview
frames. The surface reports pose/expression/motion/accessory state labels,
final-state checks, and acceptance summaries while keeping `renders_pixels=false`,
`writes_files=false`, `mutates_renderer=false`, and
`codex_pet_package_mutation=false`.
`avatar cortex-renderer-view` and `/avatar-surface/cortex-renderer-view`
convert the same preview frames into a browser-only sidecar renderer view. This
is allowed to report `browser_renders_pixels=true`, but it keeps
`server_side_renders_pixels=false`, `writes_files=false`,
`mutates_renderer=false`, and `codex_pet_package_mutation=false`; the view can
also project resolved medium-risk deferred tokens as `review_only` tracks for
manual inspection. Those review tracks must not promote themselves into the
selected binding fixture or mutate the official package. The view remains a
manual visual-QA surface before any official package binding.
`avatar cortex-review-gate` and `/avatar-surface/cortex-review-gate` add a
read-only review gate over that browser view. The gate can report automatic
checks and pending manual decisions, but it does not write approval state or
promote `review_only` tracks into selected bindings. `can_promote_review_tracks`
must remain false until a separate explicit approval design exists. The browser
renderer view may accept `track` or `track_index` query parameters, and the
panel may link pending review tokens to those focused previews; these links are
navigation evidence only and do not approve, persist, or bind any track.
`avatar cortex-review-packet` and `/avatar-surface/cortex-review-packet` turn
pending review-only tracks into human inspection packets. Each packet can carry
visual questions, acceptance criteria, operator checks, and a focused renderer
route, but `writes_approval`, `persists_review_record`,
`approval_writes_allowed`, and `can_promote_review_tracks` must remain false
until a separate approval surface is designed.
`avatar cortex-review-report` and `/avatar-surface/cortex-review-report`
summarize whether those packets are ready for human visual review. The report
can mark implementation evidence ready for a human pass, but it must keep
`human_decision_count=0`, `ready_for_approval=false`,
`approval_writes_allowed=false`, `records_persisted=false`, and
`merge_without_human_review_allowed=false`.
`avatar cortex-preview` and `/avatar-surface/cortex-preview` expose that preview
as a dedicated read-only surface with `emits_audio=false`,
`emits_notification=false`, and `requires_explicit_emit_gate=true`.
`avatar cortex-voice-gate` and `/avatar-surface/cortex-voice-gate` then evaluate
the explicit gate as a dry-run surface: it requires `enabled=true`, an operator
reason, preview text, a clear cooldown check, and voice policy approval, but
still returns `dry_run=true`, `emits_audio=false`, and
`emits_notification=false`.
`avatar cortex-voice-emit` is the narrow real-output adapter: CLI-only, no HTTP
emit route, no notification, no global Seed mutation, and no audio unless the
operator supplies `--enabled`, a non-empty `--reason`, cooldown is clear (or
`--force` is used), and either the policy allows voice or the operator supplies
the explicit `--allow-policy-override` dogfood switch.

### Stage 5 - Read-only multi-agent surface

Build a panel or terminal view that shows avatar id, runtime, mode,
activity state, risk, block reason, evidence, and next action across agents.
No auto-control in this stage.

Implementation status: the first machine-readable surface is
`avatar_surface_snapshot`, a Standard-profile read-only MCP tool implemented on
2026-05-19. It lists presence rows through the same filters as
`agent_presence_list`, projects each row into a compact protocol view, prefers
`capabilities.avatar_state`, and falls back to compatibility
`capabilities.pet_state` or generic presence identity. Optional
`include_raw_presence` and `include_compat` flags are for debugging only; the
default output is already shaped for a panel or terminal dashboard. Installed
binary validation confirmed the tool is present in the Standard profile, and a
real Claude Code dogfood session successfully wrote a `runtime=claude-code`
presence row that `avatar_surface_snapshot` read back as
`agent_id=claude-code-xiao-shu-dogfood` with both canonical and compatibility
state flags present.

The first human-readable surface is `avatar_surface_report`, also Standard and
read-only. It reuses the same projection and returns a compact text report for
terminal or panel display, with optional projected `avatars[]` data for callers
that need both forms. Installed-binary validation passed with 82 Standard tools;
a probe wrote `agent_id=codex-xiao-shu-report-installed` and
`runtime=codex`, then `avatar_surface_report` read it back with
`activity_state=verifying-report`, `focus=avatar-surface-report`, and both
state flags present. A real Claude Code terminal dogfood pass then wrote
`agent_id=claude-code-xiao-shu-report-dogfood` and `runtime=claude-code`;
installed `avatar_surface_report` read it back as the first row with
`activity_state=dogfooding-avatar-report`, `focus=avatar-surface-report`, and
both state flags present. A local CLI wrapper dogfood pass then wrote
`agent_id=local-cli-avatar-report-dogfood` and `runtime=local-cli`, and the
native `agent-bridge avatar surface --role dogfood` CLI read it back through
the same shared projection. Daemon HTTP now exposes the same shared projection
as `/avatar-surface` JSON, `/avatar-surface/report` text, and
`/avatar-surface/panel` HTML so non-MCP clients and browsers can consume the
read-only surface without a Codex dependency. Local live validation passed
against both `cargo run` and the reinstalled signed binary: JSON/text/panel
routes returned avatar rows for `runtime=local-cli`, `runtime=claude-code`, and
`runtime=codex`, and a Chrome headless screenshot confirmed the HTML panel
renders nonblank. The panel now supports `refresh_secs` and `stale_secs`, emits
a meta refresh tag, shows a server-side last update timestamp, and marks rows
fresh/stale/unknown from `last_heartbeat_at`. The JSON endpoint includes
`generated_at` and `stale_secs` so non-browser clients can apply the same
freshness rule. The panel also renders a top heartbeat-health band from the
same launchd, binary, and presence projection as
`/avatar-surface/heartbeat-health`, which remains available as JSON for
external watchdogs and non-MCP clients.

---

## 11. Acceptance Tests

| Test | Expected result |
|---|---|
| Codex `pet_state_set` with Phase 6 facets | Existing sidecar keeps the new fields |
| Codex `pet_state_get` after write | Fields round-trip without losing old keys |
| Standard `pet_presence_sync` | Presence row carries canonical `avatar_state` plus compatibility `pet_state` |
| `agent-bridge avatar sync-presence` | Same presence projection is available for CLI/launchd heartbeats without an MCP client |
| `agent-bridge avatar install-heartbeat` | A per-user launchd job periodically refreshes one stable presence row |
| `agent-bridge avatar heartbeat-health` | Launchd, binary command support, and the stable presence row are summarized by one read-only health payload |
| `agent-bridge avatar heartbeat-alert` | Health transitions are gated sparsely, optionally notified/spoken, and logged as Seed-ready JSONL events |
| `agent-bridge avatar install-heartbeat-alert` | A separate per-user launchd job periodically runs the sparse alert gate without writing presence |
| `agent-bridge avatar seed-events` | Avatar alert JSONL projects into Seed replay-compatible perception records without live substrate mutation |
| `agent-bridge avatar cortex-replay` | Avatar Seed events replay into an isolated Xiao Shu cortex snapshot without touching the global substrate |
| `agent-bridge avatar install-cortex-runner` | A separate per-user launchd job keeps the isolated Xiao Shu cortex snapshot refreshed |
| `agent-bridge avatar cortex-status` | Launchd runner state and the latest cortex snapshot row/fingerprint are visible from one read-only command |
| `agent-bridge avatar cortex-language` | Dynamic Xiao Shu phrase composition is visible without LLM, voice model, audio, or notifications |
| `agent-bridge avatar cortex-motion` | Gesture/mood/attention semantics are visible without renderer mutation or official Pet package changes |
| `agent-bridge avatar cortex-renderer` | Renderer slot mapping is visible as a dry-run without writing files or mutating assets |
| `agent-bridge avatar cortex-renderer-registry` | Renderer token candidates and review stages are visible as a read-only registry |
| `agent-bridge avatar cortex-binding-plan` | First safe renderer binding candidates, validation gates, and rollback points are visible without mutation |
| `agent-bridge avatar cortex-binding-fixture` | Selected binding candidates are frozen as deterministic sidecar preview fixtures without mutation |
| `agent-bridge avatar cortex-visual-adapter` | Fixture timelines become observable sidecar preview frames without pixel rendering or mutation |
| `agent-bridge avatar cortex-renderer-view` | Preview frames and review-only deferred medium tracks become a browser sidecar renderer view without asset writes or package mutation |
| `agent-bridge avatar cortex-review-gate` | Renderer tracks are scored for manual visual review without approval writes or binding promotion |
| `agent-bridge avatar cortex-review-packet` | Pending review-only renderer tracks become human inspection packets without approval persistence or binding promotion |
| `agent-bridge avatar cortex-review-report` | Pending-track packets are summarized for human visual-review readiness without recording decisions, approval state, or merge readiness |
| `agent-bridge avatar cortex-preview` | Voice preview text is visible without emitting audio or notifications |
| `agent-bridge avatar cortex-voice-gate` | Explicit voice-gate dry-run reports whether a future emit would pass, without emitting audio |
| `agent-bridge avatar cortex-voice-emit` | CLI-only manual voice adapter can speak one gated line and record cooldown state |
| Standard `avatar_adapter_capabilities` | Tool reports adapter/surface availability without mutating state |
| Standard `avatar_state_get` | Existing pet sidecar projects to protocol v1 without mutating state |
| Standard `avatar_surface_snapshot` | Presence rows project to compact read-only `avatars[]` entries |
| Standard `avatar_surface_report` | Same projection renders a compact read-only terminal/panel report |
| `agent-bridge avatar surface` | Same projection is available without an MCP client |
| daemon HTTP `/avatar-surface*` | Same projection is available as JSON, text, and a read-only HTML panel with refresh/stale markers plus heartbeat health |
| daemon HTTP `/avatar-surface/heartbeat-health` | Same heartbeat health payload is available to browser and non-MCP clients |
| daemon HTTP `/avatar-surface/cortex-status` | Same shadow-cortex runner/snapshot/event-trend/policy payload is available to browser and non-MCP clients |
| daemon HTTP `/avatar-surface/cortex-language` | Same deterministic language preview is available to browser and non-MCP clients without emission |
| daemon HTTP `/avatar-surface/cortex-motion` | Same gesture/mood/attention preview is available to browser and non-MCP clients without renderer mutation |
| daemon HTTP `/avatar-surface/cortex-renderer` | Same renderer slot mapping dry-run is available to browser and non-MCP clients without asset mutation |
| daemon HTTP `/avatar-surface/cortex-renderer-registry` | Same renderer token registry is available to browser and non-MCP clients without asset mutation |
| daemon HTTP `/avatar-surface/cortex-binding-plan` | Same first-binding plan is available to browser and non-MCP clients without asset mutation |
| daemon HTTP `/avatar-surface/cortex-binding-fixture` | Same sidecar preview fixture payload is available to browser and non-MCP clients without asset mutation |
| daemon HTTP `/avatar-surface/cortex-visual-adapter` | Same sidecar preview frame payload is available to browser and non-MCP clients without pixel rendering |
| daemon HTTP `/avatar-surface/cortex-renderer-view` | Browser-only sidecar renderer view, including focused `track` / `track_index` previews for review-only deferred medium tracks, is available for manual visual QA without package mutation |
| daemon HTTP `/avatar-surface/cortex-review-gate` | Same read-only renderer review gate is available to browser and non-MCP clients without approval writes; panel links can open pending tracks for focused inspection only |
| daemon HTTP `/avatar-surface/cortex-review-packet` | Same pending-track human inspection packets are available without approval persistence, record writes, or binding promotion |
| daemon HTTP `/avatar-surface/cortex-review-report` | Same packet-readiness report is available without human decision writes, approval persistence, or merge readiness |
| daemon HTTP `/avatar-surface/cortex-preview` | Same voice preview is available to browser and non-MCP clients without emission |
| daemon HTTP `/avatar-surface/cortex-voice-gate` | Same explicit voice-gate dry-run is available to browser and non-MCP clients without emission |
| Non-Codex synthetic avatar state | Object validates without `compat.codex` |
| Unknown field injected | Reader ignores it |
| Missing optional facets | Reader returns null or unknown, not error |
| `mode=working` with `activity_state=verifying` | Mode remains stable; detail stays in facet |
| Voice policy absent | Output adapters remain silent |
| `voice_policy.allowed_modes` set | Adapter still requires explicit enable and cooldown pass |

---

## 12. Open Questions

1. Should the first implementation expose `avatar_state_get` as read-only before
   adding `avatar_state_set`?
2. Should `avatar_id` default to `pet_id` for Codex only, or should the default
   be a new runtime-neutral identity?
3. How long should `capabilities.pet_state` remain after `avatar_state` has
   enough non-Codex readers?
4. Should `risk_level` stay free-form string with recommended values, or be
   validated to `low|medium|high` in the writer?
5. Should `agent_id` always be the presence `session_id`, or can a frontend
   provide a stronger identity when available?

---

## 13. Decision Summary

- Codex is a first-class compatibility target, not the core product boundary.
- The protocol belongs to Agent-Bridge and should work for non-Codex agents.
- `mode` is stable lifecycle state.
- Behavior facets carry fine-grained expression.
- Voice stays silent by default and sparse by policy.
- Presence is the shared product surface.
- Official Codex pet packages remain unchanged.
