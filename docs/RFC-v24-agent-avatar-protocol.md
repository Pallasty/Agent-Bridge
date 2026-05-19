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
`AGENT_BRIDGE_CLIENT=claude-code` runtime-label probe also passed; a real
non-Codex client-session dogfood pass is still pending.

### Stage 5 - Read-only multi-agent surface

Build a panel or terminal view that shows avatar id, runtime, mode,
activity state, risk, block reason, evidence, and next action across agents.
No auto-control in this stage.

Implementation status: the first surface is `avatar_surface_snapshot`, a
Standard-profile read-only MCP tool implemented on 2026-05-19. It lists presence
rows through the same filters as `agent_presence_list`, projects each row into a
compact protocol view, prefers `capabilities.avatar_state`, and falls back to
compatibility `capabilities.pet_state` or generic presence identity. Optional
`include_raw_presence` and `include_compat` flags are for debugging only; the
default output is already shaped for a panel or terminal dashboard. Installed
binary validation confirmed the tool is present in the Standard profile, and a
real Claude Code dogfood session successfully wrote a `runtime=claude-code`
presence row that `avatar_surface_snapshot` read back as
`agent_id=claude-code-xiao-shu-dogfood` with both canonical and compatibility
state flags present.

---

## 11. Acceptance Tests

| Test | Expected result |
|---|---|
| Codex `pet_state_set` with Phase 6 facets | Existing sidecar keeps the new fields |
| Codex `pet_state_get` after write | Fields round-trip without losing old keys |
| Standard `pet_presence_sync` | Presence row carries canonical `avatar_state` plus compatibility `pet_state` |
| Standard `avatar_adapter_capabilities` | Tool reports adapter/surface availability without mutating state |
| Standard `avatar_state_get` | Existing pet sidecar projects to protocol v1 without mutating state |
| Standard `avatar_surface_snapshot` | Presence rows project to compact read-only `avatars[]` entries |
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
