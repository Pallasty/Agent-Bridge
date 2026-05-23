# DESIGN — v23: Codex Pet Presence Loop

Status: design draft, 2026-05-18.
Companion artifact: `/Users/pallasting/Projects/pets/xiao-shu`.
Predecessors:
- `DESIGN-v19-presence-identity.md` — presence registry and active-agent semantics.
- `DESIGN-v22-agent-bridge-memory-substrate.md` — memory substrate as stateful recall layer.
- Codex hook notes in memory: `UserPromptSubmit`, `PreCompact`, `Stop`, `SessionEnd`, and `sessionEndCurate`.
Successor:
- `RFC-v24-agent-avatar-protocol.md` — runtime-neutral Agent Avatar Protocol extracted from Phase 7.

---

## 0 · Why This Exists

Codex custom pets are currently treated as passive spritesheets. The Xiao Shu V2 experiment shows a better framing:

> The official pet atlas is only a packaging target. The creative source of truth can be richer: concept art, semantic state, project context, memory, hooks, and voice.

The design goal is to turn the pet from a decorative animation into a small, calm, stateful presence for the agent's working mind:

- what the agent is doing
- when the agent is blocked
- when the agent found risk
- when the agent completed verification
- what project or role the agent is currently inhabiting

This is intentionally not a noisy assistant or notification mascot. It should feel like a quiet workspace companion with visible state.

---

## 1 · Verified Facts From Xiao Shu V2

The first useful breakthrough was not "make a pet", but "separate creative fidelity from official packaging."

Hard loader contract:

- local package under `${CODEX_HOME:-$HOME/.codex}/pets/<pet-id>/`
- `pet.json`
- fixed atlas: `1536x1872`, 8 columns, 9 rows
- fixed cell size: `192x208`
- transparent background and transparent unused cells
- row contract: `idle`, `running-right`, `running-left`, `waving`, `jumping`, `failed`, `waiting`, `running`, `review`

Creative breakthrough:

- concept art can stay as the canonical body
- chroma key cutout can produce a transparent source
- official frames can be derived after the fact
- PNG is acceptable and safer than WebP in the current V2 run because WebP introduced transparent-pixel RGB residue during validation

Current V2 acceptance:

- `inspect_frames`: 0 errors, 0 warnings
- `validate_atlas`: 0 errors, 0 warnings
- installed package: `~/.codex/pets/xiao-shu-v2`

## 1.1 · Feasibility Probe: Agent-Bridge + Hooks

Live probe on 2026-05-17:

- Agent-Bridge MCP is available with memory, terminal, agent-spawn, browser, shell-exec, and hook awareness enabled.
- The live memory database is at `/Users/pallasting/Library/Application Support/agent-bridge/state.db`; pet state should use the same state-dir resolver rather than hardcoding a Linux path.
- Codex hooks are configured for `UserPromptSubmit`, `PreCompact`, `Stop`, and `SessionEnd`.
- Installed hook scripts in `~/.local/bin` match the repo sources under `crates/bridge/src/hooks`.
- `UserPromptSubmit` probe returned valid `hookSpecificOutput` JSON.
- `Stop` probe returned exactly `{}` in the safe no-DB path.
- `PreCompact` probe exits quietly when no transcript is found.
- `hook_status` under `AGENT_BRIDGE_TOOL_PROFILE=all` confirms `beforeSubmitPrompt`, `preCompact`, `sessionEndCurate`, `stop`, and `sessionEnd` exist, are executable, and have recent successful runs.
- `mcp_dispatch_audit` under the Essential profile reports 32 exposed tools and no current filtered failures; profile changes should still be telemetry-led.

Conclusion: Phase 1 is feasible without touching the official Codex pet renderer. The safe shape is a sidecar state layer: hooks update an atomic JSON file, while MCP exposes read/diagnostic access.

---

## 2 · Innovation Inventory

### 2.1 Content-Only Innovations

These require no Agent-Bridge code change and no Codex renderer change.

| Idea | Description | Example |
|---|---|---|
| Semantic action remap | Use official rows as semantic states, not literal sample motions | `running` means focused work / worldline simulation, not jogging |
| Micro-story rows | Each row becomes a tiny narrative loop | `review`: reads map, glances up, stamps decision |
| State skins | Multiple pet packages represent modes | `xiao-shu-dev`, `xiao-shu-nexus`, `xiao-shu-video`, `xiao-shu-night` |
| Project-aware art direction | Same character adapts to project context | Nexus uses pale-gold paper + cinnabar; video lane uses storyboard board |
| Completion ritual | Completion state uses a visual ceremony | cinnabar seal lands after validation passes |

### 2.2 Hook-Driven Innovations

These use existing hooks to create external behavior while keeping the official pet contract intact.

| Hook/Event | Pet Meaning | Possible Output |
|---|---|---|
| `UserPromptSubmit` | user has given intent; agent is orienting | set state to `review` or `waiting` depending on ambiguity |
| plan creation/update | agent is organizing work | set state to `review` |
| shell/tool execution start | agent is actively working | set state to `running` |
| failed command/test | risk or failure surfaced | set state to `failed`, optionally voice one short line |
| verification pass | work accepted locally | play completion ritual / voice "已验收" |
| `Stop` / `SessionEnd` | session memory and handoff | create daily/turn battle report |
| `PreCompact` / `sessionEndCurate` | memory preservation | store pet-state summary into memory note or session handoff |

### 2.3 Agent-Bridge MCP Innovations

These use MCP as the agent's local nervous system.

| MCP Area | Pet Use |
|---|---|
| memory | choose pet posture from remembered project context and user preferences |
| presence | show whether this agent is thinking, executing, blocked, reviewing, or complete |
| telemetry | use `mcp_dispatch_audit` to avoid adding tools blindly |
| terminal/session | infer long-running work, failures, and verification results |
| forum/presence future | show multi-agent work as multiple small presences, not just chat logs |

---

## 3 · Architecture Sketch

```
User prompt / tool run / test result / session end
        │
        ▼
Codex hooks + local run observers
        │
        ▼
Agent-Bridge event normalizer
        │
        ├── memory: remember stable user/project pet preferences
        ├── presence: current agent state and role
        ├── telemetry: hot/cold/error signals
        └── optional voice: short Chinese line at key gates
        │
        ▼
Pet presence state
        │
        ├── official pet atlas package remains unchanged
        ├── optional package switching by mode
        ├── optional external mini-renderer / desktop overlay
        └── optional TTS / notification ceremony
```

The key decision: do not overload the official atlas with runtime state. Use the atlas as a stable renderer asset, and let Agent-Bridge own the changing semantic state.

---

## 4 · State Model

```json
{
  "pet_id": "xiao-shu-v2",
  "project": "agent-bridge",
  "mode": "review",
  "mood": "calm",
  "reason": "reading current hook and memory design",
  "last_event": "UserPromptSubmit",
  "last_verified_at": "2026-05-17T09:59:30Z",
  "voice_line": null,
  "ritual": null
}
```

Recommended state vocabulary:

| State | Meaning | Default Visual |
|---|---|---|
| `idle` | present, calm, low motion | breathing / blink |
| `orienting` | reading intent and context | review row |
| `working` | executing tools or building | running row |
| `reviewing` | inspecting diffs, tests, docs | review row |
| `waiting_for_user` | blocked on approval or decision | waiting row |
| `failed` | command/test/tool failed | failed row |
| `verified` | local acceptance passed | completion ritual |
| `handoff` | session ending, memory writing | quiet report state |

---

## 5 · Voice Design

Voice should be sparse and intentional. The pet should not narrate every action.

Allowed first-line set:

- `已验收。`
- `这里有一个不匹配。`
- `我等你拍板。`
- `这版有感觉了。`
- `记忆已整理。`
- `我先把风险标出来。`

Rules:

- Chinese-first.
- One short sentence.
- Only on semantic gates: completion, failure, waiting, memory handoff.
- No continuous chatter.
- User must be able to disable voice globally.
- Voice should be account-scoped, not project-global by accident.

---

## 6 · Delivery Phases

### Phase 0 — Content Lab

Status: underway via Xiao Shu V2.

Deliverables:

- concept-art faithful pet package
- contact sheet and GIF previews
- documented V2 build pipeline

### Phase 1 — Pet State File and Hook Writer

Status: shipped as a first vertical slice on 2026-05-17.

Goal: ship a zero-renderer-change state layer.

Deliverables:

- `agent_bridge_state_dir()/pet_state/xiao-shu.json`
  - macOS: `~/Library/Application Support/agent-bridge/pet_state/xiao-shu.json`
  - Linux: `$XDG_DATA_HOME/agent-bridge/pet_state/xiao-shu.json` or `~/.local/share/agent-bridge/pet_state/xiao-shu.json`
- hook writer that updates state on prompt, stop, session end, and failures where detectable
- read-only MCP tool, for example `pet_state_get`
- optional non-MCP CLI helper for hook-side writes, to keep hook stdout clean

Acceptance:

- running a Codex session updates state without corrupting hook stdout
- hook outputs still obey Codex JSON contracts
- state writes are atomic
- `pet_state_get` works under the Codex Essential profile or has an explicit reason to stay Standard/Niche

Implemented vertical slice:

- `crates/bridge/src/pet_state.rs` provides the shared state-dir resolver, pet id normalization, JSON read, and atomic JSON write helper.
- `pet_state_get` is exposed under the Codex Essential MCP profile.
- `pet_state_set` is exposed under the Codex Essential MCP profile so Codex can set semantic states such as `working`, `failed`, `verified`, and `waiting_for_user` without relying on hook events.
- `ab-session-end-hook` writes `pet_state/xiao-shu-v2.json` as a silent side effect for `Stop` and `SessionEnd`.
- `ab-memory-hook` writes `mode=orienting` on `UserPromptSubmit` before memory injection, without storing the prompt body.
- Live installed state path: `/Users/pallasting/Library/Application Support/agent-bridge/pet_state/xiao-shu-v2.json`.
- Initial live installed MCP probe: `tools/list` includes `pet_state_get`; `mcp_dispatch_audit` reports 34 exposed Essential tools and 0 filtered errors.
- Live hook probe: `Stop` stdout is exactly `{}`, state JSON updates, and `hook_status` still reports `last_output_bytes=3` for `stop` and `sessionEnd`.
- Source `UserPromptSubmit` probe: output remains valid `hookSpecificOutput`, state JSON updates to `last_event=UserPromptSubmit` and `mode=orienting`.
- Local MCP set/get probe: `pet_state_set(mode=verified, voice_line="已验收。", ritual=seal)` writes state successfully; `pet_state_get` reads it back.
- Installed MCP set/get probe after release install: `tools/list` includes both `pet_state_get` and `pet_state_set`; `pet_state_set(mode=verified, voice_line="已验收。", ritual=seal)` writes the live sidecar state and `pet_state_get` reads it back. `mcp_dispatch_audit` reports 35 exposed Essential tools; the remaining recent errors are historical unknown-tool probes from before the current MCP surface was reloaded, not failures from the installed set/get path.

### Phase 2 — Rituals and Voice PoC

Goal: small, high-signal feedback.

Deliverables:

- local TTS or system notification for 3 gates: verified, failed, waiting
- configurable opt-in
- silence window to avoid repeated lines

Acceptance:

- `verified` speaks at most once per completed task
- `failed` speaks only after a real failure signal, not every warning
- no hook JSON pollution

Implemented vertical slice:

- `pet_state_ritual` is exposed under the Codex Essential MCP profile as the opt-in ritual/voice gate.
- Default behavior is preview-only: it computes `line`, `ritual`, and throttle metadata without emitting notifications or TTS.
- Actual notification/TTS requires `enabled=true` or `AB_PET_RITUAL_ENABLE=1`; this keeps hooks silent and JSON-safe.
- `pet_state_set` can now run the ritual gate in the same call with `auto_ritual=true`; if omitted, `AB_PET_AUTO_TTS` may enable selected modes.
- TTS supports optional macOS `say` voice/rate controls through `tts_voice`, `tts_rate`, `AB_PET_TTS_VOICE`, and `AB_PET_TTS_RATE`.
- Supported sparse gates:
  - `verified` -> `line="已验收。"`, `ritual=seal`, success notification severity
  - `failed` -> `line="这里卡住了，需要看一眼。"`, `ritual=ink_dim`, error notification severity
  - `waiting_for_user` -> `line="等你拍板。"`, `ritual=lantern`, attention notification severity
  - `handoff` -> `line="本轮交接已完成。"`, `ritual=handoff`, success notification severity
- High-frequency modes such as `working` intentionally return `status=ignored` and do not emit ritual cues.
- Duplicate and silence-window control is stored in a sidecar receipt file: `pet_state/xiao-shu-v2.ritual.json`.
- Debug MCP probe: `tools/list` includes `pet_state_ritual`, Essential exposed tool count becomes 36, preview skips emission, the first enabled notification emits once, and the repeated call is blocked by `duplicate_event`.
- Installed MCP probe after release install: Essential exposed tool count is 36, `pet_state_ritual` is present, `verified` emits one Notification Center cue, the duplicate `verified` call is blocked, and `failed` / `waiting_for_user` preview with the expected sparse Chinese lines.
- Local TTS probe: `pet_state_ritual(channel=tts, enabled=true, force=true, tts_voice=Tingting, tts_rate=180)` calls macOS `say` successfully and returns `tts.ok=true`.
- Live connected MCP acceptance: current Codex MCP reports 36 Essential tools; `verified`, `failed`, and `waiting_for_user` preview without emission; `pet_state_ritual(channel=tts, enabled=true, force=true, tts_voice=Tingting, tts_rate=180)` speaks once with `tts.ok=true`, then the repeated call is blocked by `duplicate_event`.
- Post-restart Flo acceptance: after reconnecting MCP, `pet_state_set(mode=verified, auto_ritual=true, force_ritual=true, ritual_cooldown_seconds=0)` emits through the configured environment with `tts.voice="Flo (中文（中国大陆）)"`, `tts.rate=190`, and `tts.ok=true`.

Daily operating protocol:

- Default to `channel=preview` while reasoning, reviewing, or checking whether a cue is appropriate.
- Use `channel=tts` only for sparse, meaningful gates: verified completion, real failure requiring attention, or explicit waiting-for-user handoff.
- Use `force=true` only for manual validation or when intentionally re-playing a cue; normal runs should rely on duplicate and silence-window protection.
- Keep hooks state-only. Hooks may write `pet_state`, but they must not emit audio, notifications, or non-contract stdout.
- Preferred Chinese voice on this Mac: `tts_voice=Meijia`, `tts_rate=180`.
- Current lively voice trial: `tts_voice="Flo (中文（中国大陆）)"`, `tts_rate=190`.

### Phase 3 — Project-Aware Pet Skins

Goal: switch visual identity by project without losing the same character.

Packages:

- `xiao-shu-dev`
- `xiao-shu-nexus`
- `xiao-shu-video`
- `xiao-shu-night`

Acceptance:

- each package validates against the official atlas contract
- state source remains shared
- package switching mechanism is verified against the actual Codex app behavior before automation

Phase 3 reconnaissance:

- Installed custom pet packages live under `~/.codex/pets/<pet-id>/` with `pet.json` plus a relative `spritesheetPath`.
- Current Codex selection is stored in `~/.codex/.codex-global-state.json` under `electron-persisted-atom-state.selected-avatar-id`.
- Initial selected value observed during live work: `custom:xiao-shu-v2`.
- A non-active probe package `~/.codex/pets/xiao-shu-dev` was installed by reusing the V2 PNG atlas and changing only metadata:
  - `id=xiao-shu-dev`
  - `displayName=Xiao Shu Dev`
  - `spritesheetPath=spritesheet.png`
- The `xiao-shu-dev` atlas still satisfies the official dimensions: `1536x1872`.
- Installing `xiao-shu-dev` did not change `selected-avatar-id`; active pet remained `custom:xiao-shu-v2`.
- Manual UI selection was then verified by the user: `Xiao Shu Dev` appeared in the Codex custom avatar list and was selected as the current desktop assistant.
- After manual selection, `selected-avatar-id` changed to `custom:xiao-shu-dev`.
- A matching `pet_state/xiao-shu-dev.json` state file was written with `mode=verified`, `last_event=phase3:xiao-shu-dev-selected`, and `voice_line=Dev 版已接管桌面助手。`.
- The probe package was promoted into a real deterministic Dev skin through `/Users/pallasting/Projects/pets/xiao-shu/build_xiao_shu_dev_skin.py`.
  - Source: validated V2 PNG atlas at `/Users/pallasting/Projects/pets/xiao-shu/run-v2/final/spritesheet.png`
  - Output: `/Users/pallasting/Projects/pets/xiao-shu/run-dev/final/spritesheet.png`
  - Installed package: `~/.codex/pets/xiao-shu-dev`
  - QA artifacts: `/Users/pallasting/Projects/pets/xiao-shu/run-dev/final/validation.json`, `/Users/pallasting/Projects/pets/xiao-shu/run-dev/qa/contact-sheet.png`, `/Users/pallasting/Projects/pets/xiao-shu/run-dev/qa/build-summary.json`
  - Contract validation: PNG, RGBA, `1536x1872`, transparent RGB residue `0`, no validation errors.
  - Visual rule: keep V2 silhouette and concept-art fidelity, add a small attached teal development-status bead per used frame, no text, detached effects, or atlas geometry changes.
- Current implementation gap: hook defaults still write `xiao-shu-v2.json` unless `AB_PET_ID` is set. Before automating project-aware skins, Agent-Bridge should either discover the active Codex avatar id from `.codex-global-state.json` or receive `AB_PET_ID=xiao-shu-dev` through setup/config.
- Direct Computer Use inspection of the Codex app was blocked by app safety policy for `com.openai.codex`; UI-level dynamic discovery still needs human/manual confirmation or another safe inspection path.

Switching hypothesis:

- Safe manual selection path: use Codex UI to choose a custom avatar from `~/.codex/pets`.
- Possible state path: change `selected-avatar-id` to `custom:<pet-id>`, but do not automate this until the UI reload behavior and app writeback behavior are proven.
- Recommended automation boundary: Agent-Bridge may suggest a skin based on project context, and may keep state aligned with the selected avatar, but should not mutate Codex's active avatar selection without explicit user action.

### Phase 4 — Controlled Auto-Ritual Hooks

Goal: let hooks trigger sparse voice cues without making every turn noisy.

Implemented rule:

- `UserPromptSubmit` remains state-only and silent.
- `Stop` remains state-only unless explicitly enabled.
- `SessionEnd` may auto-trigger `pet_state_ritual` in the background when `AB_PET_AUTO_TTS` includes `sessionEnd`.
- MCP `pet_state_set` may auto-trigger `pet_state_ritual` for semantic modes when either `auto_ritual=true` is passed or `AB_PET_AUTO_TTS` includes that mode.
- The hook keeps stdout JSON-safe: ritual emission is backgrounded and redirected.
- Auto ritual reuses the MCP tool's duplicate-event and cooldown receipt file rather than inventing a separate throttle path.
- The MCP path returns an `auto_ritual` object in the `pet_state_set` result, so callers can tell whether the cue emitted, skipped, or was blocked by duplicate/cooldown.

Configuration:

- `AB_PET_AUTO_TTS=sessionEnd` enables session-end handoff voice only.
- `AB_PET_AUTO_TTS=handoff` or `all` enables all handoff events, including `Stop`.
- `AB_PET_AUTO_TTS=verified,failed,waiting_for_user` enables the three sparse semantic gates for MCP `pet_state_set`.
- `AB_PET_AUTO_TTS_CHANNEL=tts|notification|both` selects the output channel; default is `tts`.
- `AB_PET_AUTO_TTS_COOLDOWN_SECONDS=1800` keeps repeated handoffs quiet for 30 minutes; MCP one-shot `auto_ritual=true` defaults to 300 seconds unless overridden with `ritual_cooldown_seconds`.
- `AB_PET_TTS_VOICE` and `AB_PET_TTS_RATE` still control macOS `say`.
- Per-call MCP overrides: `auto_ritual`, `ritual_channel`, `ritual_cooldown_seconds`, and `force_ritual`.

Acceptance:

- no audio on prompt submit
- no audio on normal stop unless enabled
- session-end handoff can speak one short line
- `pet_state_set(mode=verified|failed|waiting_for_user, auto_ritual=true)` can speak exactly one short line through the same duplicate/cooldown gate
- hook stdout remains exactly `{}` for `Stop` / `SessionEnd`

Validation on 2026-05-17:

- Unit coverage: `cargo test -p ab-bridge pet_state_auto -- --nocapture` and `cargo test -p ab-bridge pet_state -- --nocapture`.
- Build coverage: `cargo check -p ab-bridge`, debug MCP build, and release MCP build/install.
- MCP stdio probe with fake `say`: default `pet_state_set(mode=failed)` stays silent; explicit `pet_state_set(mode=verified, auto_ritual=true)` emits `已验收。`; `AB_PET_AUTO_TTS=waiting_for_user` emits `等你拍板。`.
- Dev-avatar selection probe: Codex state `custom:xiao-shu-dev` resolves to `pet_id=xiao-shu-dev` and emits through `Meijia` at rate `180`.
- Installed binary probe: `/Users/pallasting/.local/bin/agent-bridge mcp` emits the same `Meijia / 180` verified cue with `pet_id=xiao-shu-dev`.

### Phase 4.3 — Agent Workflow Policy

Goal: move from manual ritual calls to a predictable work-state contract that Codex can dogfood during real tasks.

Policy:

- `orienting`: hook-owned on `UserPromptSubmit`; always silent.
- `working`: agent-owned before meaningful implementation or verification work; silent.
- `reviewing`: agent-owned while reading diffs, docs, test output, or deciding next action; silent.
- `waiting_for_user`: agent-owned only when a real decision/approval is needed; may use `auto_ritual=true` if the user is blocked on this cue.
- `failed`: agent-owned when a command/test/tool fails and human attention is useful; may use `auto_ritual=true` for one short line.
- `verified`: agent-owned only after concrete local verification passes; may use `auto_ritual=true` for the completion ritual.
- `handoff`: hook-owned on session end; sparse auto voice is allowed only through `SessionEnd` config.

Guardrails:

- Do not use voice for routine progress updates.
- Do not mark `verified` from intention or partial inspection; require command/test/live probe evidence.
- Prefer state-only updates while actively working; reserve `auto_ritual=true` for gates that change what the user should do or know.
- Keep Codex's default MCP profile at Essential. Use Standard for one-shot presence experiments until telemetry proves a broader surface is worth exposing.

Live dogfood on 2026-05-17:

- Reconnected Codex MCP accepted the new `pet_state_set(auto_ritual...)` schema.
- Default `pet_state_set(mode=failed)` returned `auto_ritual.enabled=false`.
- Explicit `pet_state_set(mode=verified, auto_ritual=true, force_ritual=true, ritual_cooldown_seconds=0)` emitted `已验收。` with `tts.voice=Meijia`, `tts.rate=180`, and `pet_id=xiao-shu-dev`.
- `mcp_dispatch_audit(profile=essential, source=codex)` showed `pet_state_set`, `pet_state_get`, and `pet_state_ritual` as hot Codex tools with zero current errors; presence tools remain Standard.

### Phase 5 — Presence as Multi-Agent UI

Goal: connect pet state to Agent-Bridge presence.

Deliverables:

- presence rows include `activity_state`, `blocked_reason`, and optional `pet_state`
- multi-agent view can show who is executing, reviewing, waiting, or idle
- no new Essential tool exposure until telemetry says the existing profile is too narrow

Acceptance:

- stale agents disappear by TTL
- active agents update without manual session ids
- pet state does not become durable truth; it is current presence, not memory

Zero-schema prototype on 2026-05-17:

- Ran a one-shot Standard-profile MCP probe using installed `/Users/pallasting/.local/bin/agent-bridge mcp`.
- `session_identity` produced `maxiaodeMac-Pro.local:agent-bridge:main`.
- `agent_presence_announce` stored `capabilities.pet_presence=true`, compact `capabilities.pet_state`, and `capabilities.voice_policy`.
- `agent_presence_list(project=agent-bridge)` read the row back with `pet_id=xiao-shu-dev`, `mode=verified`, `current_voice=Meijia`, and `current_rate=180`.
- Conclusion: Phase 5 can start as a presence-capabilities convention before adding a dedicated pet-presence MCP tool.

Phase 5.1 helper:

- Added `pet_presence_sync` as a Standard-profile MCP tool.
- It reads the current pet state file, computes a presence session id with the v19 identity convention, merges `capabilities.pet_presence=true`, `capabilities.pet_state`, and `capabilities.voice_policy`, then upserts the row through the existing `agent_presence_announce` store path.
- Phase 7 migration adds canonical `capabilities.avatar_state` while keeping `capabilities.pet_state` as the Codex compatibility projection.
- It emits no audio and does not modify the official Codex pet package.
- Debug MCP validation confirmed `pet_presence_sync` is absent from Essential, present in Standard, and syncs `xiao-shu-dev / verified / Meijia / 180` into `agent_presence_list`.
- Post-install profile probe confirmed Essential exposes 36 tools with `pet_state_get`, `pet_state_set`, and `pet_state_ritual`, while Standard exposes 96 tools and includes `pet_presence_sync`.
- Post-install Standard sync probe wrote `xiao-shu-dev` into presence with `voice_policy.current_voice="Flo (中文（中国大陆）)"` and `current_rate=190`.

---

### Phase 6 — Behavior Facets As Product Layer

Goal: make Xiao Shu feel more context-aware without expanding or breaking the official Codex pet package.

Feasibility probe on 2026-05-18:

- The official pet renderer only needs the static pet package. The sidecar JSON can grow optional fields without touching the spritesheet or manifest contract.
- The current `mode` enum is intentionally coarse: `idle`, `orienting`, `working`, `reviewing`, `waiting_for_user`, `failed`, `verified`, and `handoff`.
- `pet_state_ritual` only emits for sparse gate modes: `verified`, `failed`, `waiting_for_user`, and `handoff`.
- Hooks currently write only `orienting` and `handoff`, which is the right safety baseline.
- `pet_presence_sync` already has an extension point: `activity_state`, `blocked_reason`, `capabilities.pet_state`, and `voice_policy`.

Conclusion: Phase 6 should not add many new top-level `mode` values. Keep `mode` as the stable lifecycle gate, then add optional behavior facets that richer UI, voice, and presence surfaces can consume.

Proposed sidecar shape:

```json
{
  "mode": "working",
  "activity_state": "verifying",
  "focus": "cargo-tests",
  "risk_level": "low",
  "blocked_reason": null,
  "evidence": "cargo test -p ab-bridge pet_state passed",
  "next_action": "sync presence"
}
```

Field policy:

- `mode`: stable lifecycle gate; keep the enum small.
- `activity_state`: fine-grained work posture such as `planning`, `reading_diff`, `implementing`, `verifying`, `syncing_presence`, or `documenting`.
- `focus`: compact domain label such as `mcp`, `hooks`, `voice`, `presence`, `docs`, `tests`, or project-specific labels.
- `risk_level`: `low`, `medium`, or `high`; used for UI emphasis, not automatic alarm.
- `blocked_reason`: short human-actionable reason only when the user or another agent is actually needed.
- `evidence`: one compact proof string, not a transcript.
- `next_action`: the next local step, used by presence and future panels.

Voice policy:

- Behavior facets must be silent by default.
- `auto_ritual=true` remains meaningful only at sparse gates.
- Fine-grained states may change presence/UI, but must not create a voice flood.

Presence policy:

- Emit canonical `capabilities.avatar_state` for protocol v1 readers and keep `capabilities.pet_state` for Codex compatibility.
- Add `capabilities.pet_behavior` only if the compact state grows too noisy.
- Keep `pet_presence_sync` in Standard until live telemetry or UI usage proves Essential needs it.

Phase 6 tasks:

1. **Phase 6.1 — Sidecar Optional Facets**
   - Extend `pet_state_set` schema with optional `activity_state`, `focus`, `risk_level`, `blocked_reason`, `evidence`, and `next_action`.
   - Persist those fields only when provided.
   - Keep old state files valid when fields are absent.
   - Add unit coverage for optional-field write/read.

2. **Phase 6.2 — Presence Projection**
   - Copy optional behavior facets into `pet_presence_sync`.
   - Prefer compact `capabilities.pet_state` first.
   - Add a unit test proving voice policy and behavior facets merge together.

3. **Phase 6.3 — Dogfood Policy**
   - During real Codex work, use `mode=reviewing` with `activity_state=reading_diff` during diff review.
   - Use `mode=working` with `activity_state=verifying` during test/build/install work.
   - Use `mode=verified` only after concrete evidence exists.
   - Keep `auto_ritual=false` except for explicit gate checks.

4. **Phase 6.4 — Product Surface Later**
   - After the state contract is stable, build a small read-only panel or presence view that renders the behavior facets.
   - Do not add new UI before sidecar and presence semantics are verified.

Acceptance:

- No change to official pet package format.
- Essential tool count does not increase.
- Existing `pet_state_get`, `pet_state_set`, and `pet_state_ritual` behavior stays backward compatible.
- `pet_presence_sync` can show `mode`, `activity_state`, `focus`, `risk_level`, `blocked_reason`, and `next_action`.
- Voice remains sparse and gated.
- `cargo test -p ab-bridge pet_state -- --nocapture`, `cargo test -p ab-bridge pet_presence -- --nocapture`, and `cargo check -p ab-bridge` pass.

---

### Phase 7 — Cross-Agent Pet Presence Protocol

Goal: make the pet layer Codex-compatible without making it Codex-bound.

Feasibility probe on 2026-05-18:

- The Codex-specific hard dependency is the renderer package contract: `pet.json`, the fixed `1536x1872` atlas, row semantics, and Codex's own avatar selection UI.
- Codex hooks are an input adapter, not the core protocol. They can update sidecar state, but they must remain JSON-contract safe.
- Agent-Bridge already supports multiple frontend setup profiles: Codex, Claude Code, Warp, Auggie, Gemini CLI, and local CLI. Only some frontends expose lifecycle hooks.
- Agent-Bridge already has runtime-neutral primitives: `pet_state` sidecar files, `session_identity`, `agent_presence_announce`, `agent_presence_list`, `pet_presence_sync`, MCP telemetry, and daemon/peer design.
- The current state path resolver already works outside Codex-specific directories by using the Agent-Bridge state dir.

Conclusion: the product should be a small cross-agent avatar protocol with Codex as one renderer/adapter. The core state should not know how Codex renders a spritesheet; the Codex adapter should translate core state into Codex-compatible assets, hooks, and sidecar writes.

Layer model:

| Layer | Responsibility | Codex dependency |
|---|---|---|
| Core protocol | agent/avatar identity, lifecycle mode, behavior facets, voice policy, evidence, next action | none |
| Input adapters | translate frontend events into protocol updates | per frontend |
| Output adapters | render/surface state through Codex pet, presence, TTS, notification, panel, or terminal | per surface |
| Compatibility targets | keep each frontend's native contract valid | yes, but isolated |

Core protocol sketch:

```json
{
  "schema_version": 1,
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
    "voice": "Flo (中文（中国大陆）)",
    "rate": 190,
    "allowed_modes": ["verified", "failed", "waiting_for_user", "handoff"]
  },
  "compat": {
    "codex": {
      "pet_id": "xiao-shu-dev",
      "package_contract": "8x9-atlas-v1"
    }
  }
}
```

Adapter matrix:

| Adapter | Input path | Output path | Product stance |
|---|---|---|---|
| Codex | `hooks.json` plus MCP calls | official pet package, sidecar state, TTS/notification | first-class compatibility target |
| Claude Code | settings hooks plus MCP calls | sidecar state, TTS/notification, presence | no Codex renderer assumption |
| Warp | terminal/OSC/wrapper events plus MCP | presence, terminal status, optional panel | no lifecycle-hook dependency |
| Gemini CLI | MCP/config-driven events | sidecar state and presence | adapter is thinner until hooks exist |
| Auggie/local CLI | MCP or wrapper events | presence and sidecar state | no hook assumption |
| Daemon/HTTP peer | HTTP/MCP event ingestion | cross-machine presence and panel | future surface, protocol-first |

Compatibility rules:

- Codex compatibility remains a leaf adapter. Never require other agents to implement Codex pet package geometry.
- Core protocol fields must be optional-forward-compatible: unknown fields are ignored, not rejected.
- `mode` remains the stable lifecycle gate; richer details live in behavior facets.
- Input adapters may be lossy. If a frontend cannot provide hooks, it may still update state from explicit MCP calls or session wrapper events.
- Output adapters must be safe by default: no voice unless sparse gates allow it.
- Presence is the shared product surface. The official Codex pet is a local visual surface.

Phase 7 tasks:

1. **Phase 7.1 — Protocol RFC**
   - Extract the core state schema from v23 into a small protocol section or new RFC.
   - Define required vs optional fields and compatibility semantics.
   - Define a version marker such as `agent_avatar_protocol=1`.
   - Status: drafted as `docs/RFC-v24-agent-avatar-protocol.md` on 2026-05-18.

2. **Phase 7.2 — Adapter Capability Probe**
   - Add a read-only diagnostic that reports which adapter surfaces are available: hooks, MCP, presence, TTS, notification, terminal, HTTP daemon.
   - Keep it diagnostic-only before adding any mutating behavior.
   - Status: implemented as Standard-profile `avatar_adapter_capabilities` on 2026-05-18; release and installed-binary stdio probes passed; post-restart Codex audit confirms the default Codex-facing profile remains `essential`, so the new Standard tool does not expand the default tool surface.

3. **Phase 7.3 — Runtime-Neutral State Tools**
   - Start with read-only `avatar_state_get`, projecting current Codex-shaped `pet_state` into RFC-v24 protocol v1.
   - Factor the current Codex-shaped `pet_state_set` semantics into a runtime-neutral `avatar_state_set` or keep the old name as a compatibility alias.
   - `pet_state_set` remains stable for Codex and existing callers.
   - Status: `avatar_state_get` implemented as a Standard-profile read-only projection on 2026-05-18; debug and installed-binary stdio probes passed; mutating `avatar_state_set` not started.

4. **Phase 7.4 — Cross-Agent Presence Projection**
   - Project the core protocol into `agent_presence_announce` capabilities consistently across Codex, Claude Code, Warp, Gemini, Auggie, and local CLI.
   - Use `session_identity` as the canonical agent id when a frontend does not provide one.
   - Status: first Codex/Standard projection implemented in `pet_presence_sync` on 2026-05-18; debug and installed-binary Standard probes passed with both `capabilities.avatar_state` and compatibility `capabilities.pet_state`; installed `AGENT_BRIDGE_CLIENT=claude-code` runtime-label probe also passed.
   - Native CLI heartbeat path: `agent-bridge avatar sync-presence` now reuses the same shared projection as `pet_presence_sync`, defaults `runtime=local-cli`, uses the CLI process cwd unless overridden, and writes the current pet sidecar into an `agent_presence` row without emitting audio or expanding the Codex Essential MCP surface. Debug dogfood wrote `agent_id=local-cli-avatar-heartbeat-dogfood` / `runtime=local-cli` / `activity_state=heartbeat-probe`, and HTTP `/avatar-surface` read it back fresh with an age of 10 seconds.
   - Native launchd heartbeat path: `agent-bridge avatar install-heartbeat`, `avatar heartbeat-status`, and `avatar remove-heartbeat` manage a per-user LaunchAgent that periodically runs `avatar sync-presence` with a stable `session_id`/`agent_id`. This avoids pid-based auto-tag fan-out across one-shot launchd runs. Installed-binary dogfood wrote and loaded `~/Library/LaunchAgents/com.agentbridge.avatar-heartbeat.agent-bridge.plist`; `heartbeat-status` showed `runs=2`, `last exit code=0`, and `run interval = 60 seconds`; HTTP `/avatar-surface` read back `agent_id=com.agentbridge.avatar-heartbeat.agent-bridge`, `runtime=local-cli`, `activity_state=launchd-heartbeat`, and heartbeat age 11 seconds.
   - Heartbeat health projection: `agent-bridge avatar heartbeat-health` now evaluates the LaunchAgent, the actual binary named in its plist, and its stable presence row together. It reports the launchd load state, run count, last exit code, interval, plist/log paths, binary path, binary command support, presence freshness, and projected avatar fields from one shared read-only module. This gives the operator a single answer for "is Xiao Shu independently alive?" instead of correlating `launchctl print`, `avatar --help`, and `/avatar-surface` by hand.
   - Binary drift guard: `install-heartbeat` now prefers `~/.local/bin/agent-bridge.real` when it exists, falling back to `~/.local/bin/agent-bridge`. This matches the existing wrapper/background-job layout on the Mac and prevents the heartbeat from depending on a front-door binary that may be replaced by wrapper/setup flows. `heartbeat-health` can now report `binary_missing` or `binary_missing_command` before the operator has to diagnose a stale presence row from logs.

5. **Phase 7.5 — Read-Only Multi-Agent Surface**
   - Build or prototype a read-only view that shows multiple agents with avatar id, mode, activity state, risk, block reason, and next action.
   - Do not ship auto-control from this panel until the state protocol has survived dogfood.
   - Status: implemented first as Standard-profile `avatar_surface_snapshot` on 2026-05-19. It reads `agent_presence_list`, prefers `capabilities.avatar_state`, falls back to compatibility `capabilities.pet_state` or generic presence identity, and returns compact `avatars[]` entries for a future panel or terminal dashboard. It is read-only and does not mutate sidecar state, write presence, emit audio, or send notifications. Installed-binary probes passed with 81 Standard tools, and a real Claude Code dogfood session wrote `runtime=claude-code` / `agent_id=claude-code-xiao-shu-dogfood`; the snapshot read it back with both `has_avatar_state=true` and `has_compat_pet_state=true`.
   - First human-facing surface: `avatar_surface_report` now renders the same projection as a compact terminal/panel-friendly text report. It stays Standard-profile and read-only. Installed-binary validation passed with 82 Standard tools; a probe wrote `agent_id=codex-xiao-shu-report-installed` / `runtime=codex` and `avatar_surface_report` read it back with `activity_state=verifying-report`, `focus=avatar-surface-report`, and both canonical and compatibility state flags present. A real Claude Code terminal dogfood pass then wrote `agent_id=claude-code-xiao-shu-report-dogfood` / `runtime=claude-code`; installed `avatar_surface_report` read it back as the first row with `activity_state=dogfooding-avatar-report`, `focus=avatar-surface-report`, and both state flags present. A local CLI wrapper pass then wrote `agent_id=local-cli-avatar-report-dogfood` / `runtime=local-cli`, and the native `agent-bridge avatar surface --role dogfood` CLI read it back through the same shared projection.
   - Daemon HTTP read-only panel: `/avatar-surface` returns the shared JSON projection, `/avatar-surface/report` returns the same report as `text/plain`, and `/avatar-surface/panel` renders a minimal HTML panel. All three routes are read-only and reuse `avatar_surface` rather than duplicating panel logic. Live probes passed on 2026-05-19 against both `cargo run` and the reinstalled signed binary; JSON/text/panel routes returned the local-cli, Claude Code, and Codex avatar rows, and Chrome headless produced a nonblank panel screenshot.
   - Long-running panel affordances: `/avatar-surface/panel` accepts `refresh_secs` and `stale_secs`, emits a meta refresh tag, shows the server-side last update timestamp, marks each row as fresh/stale/unknown from `last_heartbeat_at`, and now renders a top heartbeat-health band using the same launchd/binary/presence projection as `/avatar-surface/heartbeat-health`. `/avatar-surface` JSON also includes `generated_at` and `stale_secs` so non-browser clients can apply the same threshold. `/avatar-surface/heartbeat-health` exposes the same heartbeat health projection over HTTP for external watchdogs and non-MCP clients.
   - Sparse alert gate: `agent-bridge avatar heartbeat-alert` now reads the same heartbeat health projection and emits only on first-unhealthy, transition, forced, or repeat-due events. It writes a compact state file plus append-only JSONL event log under `~/Library/Application Support/agent-bridge/avatar_health/`. Desktop notification is enabled by default when an alert emits; TTS is explicit via `--tts`, preserving the sparse-voice policy. Each event includes `seed_ready.substrate_input=avatar_health_transition_v1` so the emerging Seed substrate can consume health transitions later without making current alerting depend on Seed.
   - Independent alert runner: `agent-bridge avatar install-heartbeat-alert`, `avatar heartbeat-alert-status`, and `avatar remove-heartbeat-alert` manage a second per-user LaunchAgent that periodically runs `avatar heartbeat-alert` instead of writing presence. This keeps the heartbeat writer and the heartbeat watcher independent. Local dogfood installed `~/Library/LaunchAgents/com.agentbridge.avatar-heartbeat-alert.agent-bridge.plist` with `--tts --tts-voice Flo --tts-rate 190`; `heartbeat-alert-status` showed `runs=2`, `last exit code=0`, and `run interval = 120 seconds`. The latest event was healthy/unchanged with `should_emit=false`, `emitted=false`, `notification=null`, and `tts=null`, so the runner did not make noise while the system was healthy.
   - Seed perception adapter: `agent-bridge avatar seed-events` projects the alert JSONL into the existing `substrate replay` event format: `{text, key, ts, kind}` plus avatar metadata. It is read-only, defaults to excluding preview/dogfood events, and does not call Seed or mutate substrate state. Local dogfood saw 9 alert events, skipped 5 preview events, emitted 4 `avatar_health_transition_v1` records, and `agent-bridge substrate replay --log /tmp/avatar-seed-events.jsonl --use-hash --json` parsed all 4 records with `step_count_final=4` and a Long snapshot row. This validates the perception boundary before any live Seed subscription.
   - Xiao Shu cortex v0: `agent-bridge avatar cortex-replay` reuses the `seed-events` projection, feeds it into a fresh isolated `SeedBackend`, and writes a dedicated shadow-only snapshot under `~/.local/share/agent-bridge/avatar_cortex/<project>/<heartbeat-label>.parquet`. It does not set `AB_SUBSTRATE=1`, does not write the global memory substrate, does not restart AiOT, and does not activate sibling-gated daemon work. This matches the AiOT 2026-05-18 cortical direction by starting as a single-stream shadow cortex; the future v1 path is a MultiModalGrid split across health/voice/session modalities after the dry-run has useful evidence. Local dogfood consumed 12 non-preview Xiao Shu events into `cortex_id=xiao-shu/agent-bridge/com.agentbridge.avatar-heartbeat.agent-bridge`, wrote one Long snapshot row, and reported `mutates_global_substrate=false`, `no_daemon_restart=true`, `no_sibling_activation=true`.
   - Cortex runner: `agent-bridge avatar install-cortex-runner`, `avatar cortex-status`, and `avatar remove-cortex-runner` manage a third per-user LaunchAgent that periodically refreshes the isolated Xiao Shu cortex snapshot. It runs `avatar cortex-replay` every 300 seconds using `~/.local/bin/agent-bridge.real`, writes only the dedicated avatar cortex parquet, and emits no audio/notification. Local dogfood installed `~/Library/LaunchAgents/com.agentbridge.avatar-cortex.agent-bridge.plist`; `cortex-status --json` showed `loaded=true`, `runs=2`, `last_exit_code=0`, `run_interval_secs=300`, `snapshot.latest_long.step=16`, and `mutates_global_substrate=false`.
   - Cortex panel projection: `/avatar-surface/cortex-status` now exposes the same runner/snapshot payload over HTTP, and `/avatar-surface/panel` renders a top-level Cortex Status band beside heartbeat health. The payload now includes a read-only `events` window derived from `avatar seed-events` plus a `trend` summary (`step_records_delta`, `snapshot_event_lag_secs`, `latest_status`, `latest_healthy`) so the panel can answer whether Xiao Shu's shadow cortex is advancing with the alert stream. `trend.learning_state` adds a stable semantic label: `caught_up` when snapshot step matches the visible event window, `learning` when events are ahead of the snapshot, `behind` when the snapshot is ahead of the current window, and `stale` when events or snapshots are missing. `trend.behavior_policy` maps that state into read-only UI behavior (`badge`, `panel_hint`, `recommended_action`) and explicitly keeps `voice.allowed=false` and `notification.allowed=false`; future voice work can reuse the preview text only after an explicit sparse-emission gate. Installed-binary dogfood on 2026-05-19 restarted `com.agentbridge.avatar-panel`, then verified the live endpoint returned `loaded=true`, `state=active`, `last_exit_code=0`, `snapshot.total_rows=2`, `snapshot.latest_long.step=21`, and `mutates_global_substrate=false`; the panel HTML showed `Cortex Status`, `rows=2 step=21`, and the latest fingerprint. A follow-up trend dogfood saw `events.records_count=33`, `latest.status=healthy`, `step_records_delta=-2` before kicking the cortex runner, then `snapshot.latest_long.step=33`, `step_records_delta=0`, `step_matches_records=true`, `snapshot_event_lag_secs=29`, and panel text `records=33 latest=healthy reason=unchanged` / `delta=0 lag=29s unhealthy=0`. The semantic-state dogfood saw live `learning_state.state=learning` while two events were ahead, then after `launchctl kickstart -k gui/501/com.agentbridge.avatar-cortex.agent-bridge` it changed to `learning_state.state=caught_up`, `reason=step_matches_records`, `step_matches_records=true`, and panel text `state=caught_up reason=step_matches_records`. The behavior-policy dogfood first showed `policy.badge=learning`, `recommended_action=wait_for_cortex_runner`, `voice.allowed=false`, and `notification.allowed=false`; after kicking the runner it changed to `badge=caught up`, `recommended_action=none`, `voice.allowed=false`, and panel text `badge=caught up action=none voice=false`. The explicit preview gate adds `agent-bridge avatar cortex-preview` and `/avatar-surface/cortex-preview`, both returning `surface=avatar_cortex_voice_preview`, `emits_audio=false`, `emits_notification=false`, `preview.text`, and `requires_explicit_emit_gate=true`; live CLI/HTTP dogfood saw the learning preview `小舒正在吸收新事件。`, then after a cortex runner kick saw the caught-up preview `小舒已追上最新事件。`, with `voice_allowed=false` throughout.
   - Cortex language layer: `agent-bridge avatar cortex-language` and `/avatar-surface/cortex-language` add a read-only phrase-composition layer before any voice model integration. The composer is deterministic and local: it maps `learning_state`, latest health status/reason, event counts, lag/delta, and project slug into a short Xiao Shu Chinese utterance plus alternatives, slots, generator metadata, and safety flags. `language.memory` adds a short-event-window observation over `events.recent` so Xiao Shu can say whether the last few health signals were stable, transitioning, mixed, or unhealthy without writing persistent memory. It reports `uses_llm=false`, `uses_voice_model=false`, `emits_audio=false`, and `requires_explicit_emit_gate=true`; `/avatar-surface/panel` renders the current language preview as a separate "Xiao Shu Language" band, and `avatar cortex-preview` uses the language utterance as its preview text while keeping `voice_allowed=false`.
   - Cortex motion layer: `agent-bridge avatar cortex-motion` and `/avatar-surface/cortex-motion` derive Xiao Shu's gesture/mood/attention semantics from the same cortex + language state. The payload stays renderer-neutral and sidecar-only: it returns `motion.gesture`, `motion.mood`, `motion.attention`, `motion.animation_hint`, source slots, and safety flags such as `codex_pet_package_mutation=false` and `requires_renderer_mapping=true`. `/avatar-surface/panel` renders it as a separate "Xiao Shu Motion" band so the product can dogfood behavior intention before binding anything to official Pet assets or desktop animation.
   - Cortex renderer adapter dry-run: `agent-bridge avatar cortex-renderer` and `/avatar-surface/cortex-renderer` map `motion.animation_hint.renderer_token` into a renderer-neutral slot contract (`pose_slot`, `expression_slot`, `motion_slot`, `accessory_slot`, and a small timeline). It is deliberately a dry-run adapter: `writes_files=false`, `mutates_renderer=false`, `codex_pet_package_mutation=false`, and `requires_human_binding=true`. `mapping.evidence` captures the binding-stage, visual intent, acceptance criteria, risk level, review questions, and recommended next step for each token. The panel renders it as "Xiao Shu Renderer" so motion intent and binding evidence can be reviewed before any official Pet package or desktop animation binding exists.
   - Cortex renderer registry: `agent-bridge avatar cortex-renderer-registry` and `/avatar-surface/cortex-renderer-registry` collect every known renderer token plus the fallback policy into a read-only binding candidate registry. It reports counts by binding stage and risk level, includes the current live token/stage/risk, and renders a "Xiao Shu Renderer Registry" panel band. This turns one-token dry-runs into a product view of the Xiao Shu motion library while still keeping `writes_files=false`, `mutates_renderer=false`, and `codex_pet_package_mutation=false`.
   - Cortex binding plan dry-run: `agent-bridge avatar cortex-binding-plan` and `/avatar-surface/cortex-binding-plan` turn the registry into a first-binding implementation plan without touching renderer assets. The plan selects only low-risk resolved candidates (`soft_bounce` and `idle_breathe`), defers `needs_review` and fallback tokens, lists validation and rollback gates, and renders a "Xiao Shu Binding Plan" panel band. It preserves `read_only=true`, `dry_run=true`, `writes_files=false`, `mutates_renderer=false`, `codex_pet_package_mutation=false`, and `requires_human_approval=true`.
   - Cortex binding fixture dry-run: `agent-bridge avatar cortex-binding-fixture` and `/avatar-surface/cortex-binding-fixture` freeze the selected binding-plan candidates into deterministic sidecar preview fixtures. The fixture surface emits two slot-timeline golden payloads (`soft_bounce` and `idle_breathe`), per-token golden assertions, all-return-to-idle and all-under-2s acceptance gates, and a "Xiao Shu Binding Fixture" panel band. It still reports `read_only=true`, `dry_run=true`, `writes_files=false`, `mutates_renderer=false`, and `codex_pet_package_mutation=false`; the output is evidence for a later sidecar visual adapter, not a package mutation.
   - Cortex sidecar visual adapter dry-run: `agent-bridge avatar cortex-visual-adapter` and `/avatar-surface/cortex-visual-adapter` consume the binding fixtures and project each slot timeline into observable preview frames. The adapter produces frame-by-frame pose/expression/motion/accessory state labels, final-state checks, and acceptance summaries while explicitly reporting `renders_pixels=false`, `writes_files=false`, `mutates_renderer=false`, and `codex_pet_package_mutation=false`. `/avatar-surface/panel` renders this as "Xiao Shu Visual Adapter", making the next visual behavior layer inspectable before any pixel renderer or official Pet package binding exists.
   - Cortex sidecar renderer view: `agent-bridge avatar cortex-renderer-view` and `/avatar-surface/cortex-renderer-view` turn those preview frames into a browser-only renderer view. This is the first intentionally pixel-rendering sidecar surface (`browser_renders_pixels=true`) while still keeping `writes_files=false`, `mutates_renderer=false`, `server_side_renders_pixels=false`, and `codex_pet_package_mutation=false`. The view now uses the installed `xiao-shu-dev` Codex pet spritesheet as a read-only browser asset source through `/avatar-surface/pet-spritesheet?pet_id=xiao-shu-dev`, with the old DOM/CSS drawing kept only as fallback. The view includes the two selected low-risk tracks plus three `review_only` medium tracks (`sorting_glow`, `look_sideways`, and `alert_peek`) sourced from deferred `needs_review` bindings; these are visual QA evidence only and do not change the binding plan. The first desktop review of `alert_peek` requested lower brightness, better aesthetics, future voice linkage, and a slightly thicker shape; the accepted visual baseline now uses the original sprite color with no filter and a smaller sidecar scale. The next review pass adds read-only `alert_peek` semantic variants (`current_alert_row`, `waiting_peek_row`, `sidecar_peek_v2`, `sidecar_peek_v4`, `sidecar_peek_v3`, and `focused_review_row`) through the renderer `variant` query parameter so posture can be compared before any binding or sparse voice cue is chosen. Those variants now carry `frame_choreography` tables so the browser plays atlas row/column frames with per-frame holds and attention-mark timing, instead of simulating the action with CSS scale/translate wobble. `sidecar_peek_v2` deliberately switches to `/avatar-surface/sidecar-spritesheet?asset=xiao-shu-alert-peek-v2`, a read-only prototype asset that keeps the same 192x208 cell and 1536x1872 atlas contract but redraws the action frames for clearer peek, hand, blink, and return poses without official package mutation. `sidecar_peek_v4` keeps v2's visible raised-hand skeleton while layering Xiao Shu's paper-charm palette, red ribbon, robe marks, and teal accessory through `/avatar-surface/sidecar-spritesheet?asset=xiao-shu-motion-canonical-peek-v4`; follow-up desktop review accepted it as the current visual-motion baseline and default semantic variant. The accepted v4 state now carries a read-only `voice_linkage_preview` in the renderer inspector with a suggested sparse utterance and `/avatar-surface/cortex-voice-gate` dry-run route, while keeping real output behind the existing CLI-only `avatar cortex-voice-emit` gate; the CLI gate/emit path can take `--preview-text` so a manual dogfood can speak the accepted v4 line exactly without adding an HTTP emit route. `/avatar-surface/cortex-voice-policy` and `agent-bridge avatar cortex-voice-policy` now expose the sparse voice intent table: most tracks remain silent/display-only, `alert_peek` v4 is manual CLI-only, and auto emit stays disabled. `/avatar-surface/cortex-voice-request` and `agent-bridge avatar cortex-voice-request` add the next two-step request layer: they preview the exact CLI-only emit args and confirmation requirements for the selected policy rule, but still emit no audio and add no HTTP emit route. `/avatar-surface/cortex-voice-confirm` and `agent-bridge avatar cortex-voice-confirm` add the confirmation-action dry-run shell: `confirm=true` plus an operator reason exposes the CLI command that would be run, while still emitting no audio, writing no confirmation record, and adding no HTTP emit route; the same confirmation now previews the higher-level `agent-bridge avatar cortex-voice-action` command for slash/panel handoff. `sidecar_peek_v3` keeps that motion grammar while moving the art back toward the `xiao-shu-dev` paper-charm silhouette, robe, red ribbon, and small accessory language through `/avatar-surface/sidecar-spritesheet?asset=xiao-shu-canonical-peek-v3`. Voice linkage remains future sparse voice design with no audio emission. `/avatar-surface/panel` links this as "Xiao Shu Renderer View" so manual visual QA can happen before any official package binding.
   - Cortex renderer review gate: `agent-bridge avatar cortex-review-gate` and `/avatar-surface/cortex-review-gate` score the five renderer tracks for manual visual review without writing approval state. The gate checks frames, return-to-idle, under-2s duration, named mapping resolution, and binding-stage consistency; selected low-risk tracks become baselines, while `review_only` medium tracks remain `manual_decision=pending` and `can_promote_binding=false`. `/avatar-surface/panel` renders this as "Xiao Shu Review Gate" so the next decision is an explicit human review, not an accidental binding promotion. The panel also links each pending token back into `/avatar-surface/cortex-renderer-view?track=...`, and the renderer view accepts `track` or `track_index` query params so desktop reviewers can open a specific action directly without changing any binding state.
   - Cortex renderer review packet: `agent-bridge avatar cortex-review-packet` and `/avatar-surface/cortex-review-packet` package the three pending review-only tracks into human inspection packets. Each packet carries the focused renderer route, automatic gate result, visual questions, acceptance criteria, required operator checks, and a conservative `default_decision=keep_pending`. This is still not an approval store: `writes_approval=false`, `persists_review_record=false`, `approval_writes_allowed=false`, and `can_promote_review_tracks=false`; `/avatar-surface/panel` renders it as "Xiao Shu Review Packet" so reviewers can inspect a pending action before any future approval surface is designed.
   - Cortex renderer review report: `agent-bridge avatar cortex-review-report` and `/avatar-surface/cortex-review-report` summarize whether the pending review packets are ready for human visual review. The report counts ready vs blocked packets, human feedback entries, and requested voice-linkage items, exposes a checklist for the manual pass, and keeps `human_decision_count=0`, `ready_for_approval=false`, `approval_writes_allowed=false`, `records_persisted=false`, and `merge_without_human_review_allowed=false`. `/avatar-surface/panel` renders this as "Xiao Shu Review Report" so the current branch can be judged ready for a human visual pass without implying merge, approval, or binding readiness.
   - Cortex voice gate dry-run: `agent-bridge avatar cortex-voice-gate` and `/avatar-surface/cortex-voice-gate` evaluate the explicit voice gate without calling TTS, desktop notifications, launchd mutation, or Seed/global substrate writes. The dry-run payload returns `surface=avatar_cortex_voice_gate_dry_run`, `dry_run=true`, `emits_audio=false`, `emits_notification=false`, `would_emit`, `gate.blocked_reasons`, `required.*`, and a non-persistent cooldown block. Current policy intentionally keeps `voice_policy_allowed=false`, so even `--enabled --reason ...` should return `would_emit=false` with `policy_voice_disabled` until a later human-approved sparse-emission policy changes that boundary. Installed-binary dogfood verified the default CLI gate blocks with `gate_disabled`, `missing_reason`, and `policy_voice_disabled`; explicit CLI and HTTP calls with `enabled=true` plus `reason=manual-dogfood` both narrowed the block to `policy_voice_disabled` while still returning `dry_run=true`, `emits_audio=false`, and `emits_notification=false`.
   - Cortex voice emit gate: `agent-bridge avatar cortex-voice-emit` is a CLI-only real-output adapter for manual dogfood. There is deliberately no HTTP emit route. The command reuses the same preview/gate decision, writes an audit event under `~/Library/Application Support/agent-bridge/avatar_cortex_voice/`, writes cooldown state only after successful TTS, emits no notification, and never mutates the global Seed substrate. Real audio requires all of: `--enabled`, non-empty `--reason`, cooldown clear or `--force`, and either `voice.allowed=true` or the explicit manual `--allow-policy-override`. Installed-binary dogfood on 2026-05-20 verified three paths: without policy override it stayed silent with `policy_voice_disabled`; with `--allow-policy-override --force --cooldown-secs 0 --tts-voice "Flo (中文（中国大陆）)" --tts-rate 190` it spoke the cortex preview once with `tts.ok=true`; an immediate second call with `--cooldown-secs 300` stayed silent with `cooldown_active`.
   - Cortex voice action wrapper: `agent-bridge avatar cortex-voice-action` consumes the request/confirm chain before entering the CLI-only emit gate. By default it is a dry-run (`read_only=true`, `actual_emit_invoked=false`) and reports why no real output happened; real audio still requires `--confirm --emit --reason ...`, then delegates to `cortex-voice-emit` with the confirmed line, suggested voice, suggested rate, cooldown, and manual policy override. There remains no HTTP emit route.
	   - Cortex voice action preview: `agent-bridge avatar cortex-voice-action-preview` and `/avatar-surface/cortex-voice-action-preview` provide the panel/slash-facing runbook for the wrapper. The preview reads the existing cooldown receipt, evaluates the same confirmed line and policy-override gate in dry-run mode, and reports `ready_to_emit_now`, blocked reasons, cooldown timing, and the exact `cortex-voice-action --confirm --emit ...` command. It never invokes TTS, writes files, or adds an HTTP emit route.
	   - Xiao Shu action request: `agent-bridge avatar xiao-shu-action-request` and `/avatar-surface/xiao-shu-action-request` provide the LLM-facing operation interface. The request accepts an actor, high-level intent, optional natural-language message, target track, and reason, then maps supported intents such as `voice_alert` into the existing voice action preview runbook. It explicitly reports `llm_safe=true`, `direct_pet_control_allowed=false`, `direct_llm_emit_allowed=false`, and `real_emit_requires_local_cli=true`; it produces request/confirm/preview/emit command candidates but never invokes TTS, writes records, or adds an HTTP emit route.
	   - Xiao Shu MCP pending-action queue: the MCP `xiao_shu_action_request` wrapper can now accept `enqueue=true` to append the request to a sidecar JSONL queue under `~/Library/Application Support/agent-bridge/avatar_cortex_action_requests/<project>/requests.jsonl`. This is the first durable request record for LLM-originated Xiao Shu actions, but it is still non-emitting: queued records are fixed at `state=pending_human_confirmation`, `direct_llm_emit_allowed=false`, `emits_audio=false`, `writes_cooldown_state=false`, and `codex_pet_package_mutation=false`. CLI/HTTP request surfaces remain read-only by default; the queued record exists only so a later panel or slash command can present an auditable pending action to the human before any local CLI emit step.
	   - Xiao Shu pending queue reader: `agent-bridge avatar xiao-shu-action-requests`, `/avatar-surface/xiao-shu-action-requests`, `/avatar-surface/panel`, and MCP `xiao_shu_action_request` with `list_queue=true` now expose the sidecar JSONL queue as a read-only inspection surface. The reader defaults to `state=pending_human_confirmation`, returns newest current records first, supports `request_id`, `state`, `all_states`, `details`, and `limit` filters, and preserves `actual_emit_invoked=false`, `emits_audio=false`, `writes_request_record=false`, `writes_cooldown_state=false`, and `codex_pet_package_mutation=false`. Broad list reads are compact by default so Codex/MCP telemetry is not flooded by nested renderer payloads; full nested records are returned when `request_id`, `all_states`, or explicit `details` is supplied. Queue history stays append-only, but the reader folds multiple records with the same `request_id` to their latest state so completed local actions disappear from the default pending view while remaining auditable with details/request-id reads.
	   - Xiao Shu queued action consumer: `agent-bridge avatar xiao-shu-action-request-action` is the first local operator consumer for queued LLM requests. By default it is a dry-run and reports the pending request, downstream `cortex-voice-action` readiness, blocked reasons, and the local command shape without writing a queue transition or emitting audio. Only a local CLI invocation with `--confirm --emit` may call the existing CLI-only voice action gate; when that path is actually invoked, the queue receives an append-only transition record such as `emitted`, `emit_failed`, or `emit_blocked`. There is deliberately no HTTP emit route and no MCP direct-control route; `/avatar-surface/panel` only prints the local CLI command for the human to copy or adapt.

Acceptance:

- Codex still loads the same official-compatible pet package.
- Existing Codex MCP tools remain backward compatible.
- Non-Codex adapters can write/read core avatar state without a Codex package.
- Presence rows can carry the same avatar protocol across at least two runtime labels.
- Essential Codex tool exposure does not grow without telemetry.
- Voice remains sparse and adapter-independent.

---

## 7 · Safety And Product Boundaries

- Do not make hooks noisy or fragile; hook JSON correctness has priority.
- Do not demote or expose new MCP tools based on intuition alone; use live telemetry.
- Do not auto-switch official Codex pet package until the app's real loading behavior is verified.
- Do not store large images in memory. Store paths, decisions, and compact summaries only.
- Do not let voice become a notification flood.
- Do not use pet state as a substitute for actual test or command verification.

---

## 8 · Near-Term Next Task

Phase 6.1 and Phase 6.2 are now live-verified in the current Codex/MCP path.
Move in this order:

1. Let the launchd heartbeat run through a longer dogfood window while the HTTP panel auto-refreshes, and watch `/avatar-surface/heartbeat-health` for stale/fresh correctness and binary drift across real pauses.
2. Dogfood the refreshed daemon HTTP panel from a long-lived local or tailnet `daemon-http` process during real multi-agent work.
3. Keep mutating `avatar_state_set` behind the RFC boundary until the read-only surfaces have survived that live panel dogfood pass.
4. Dogfood Phase 6.3 during real Codex work.
5. Add a Codex-side read-only panel only after the external HTTP surface is stable.
6. Return to Phase 3 skin switching after the behavior and presence loop is stable; do not auto-switch official Codex avatars until app reload behavior is proven.

This preserves the user's preferred pattern: prove the live mechanism first, then expand capability.
