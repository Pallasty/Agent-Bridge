# DESIGN — v23: Codex Pet Presence Loop

Status: design draft, 2026-05-17.
Companion artifact: `/Users/pallasting/Projects/pets/xiao-shu`.
Predecessors:
- `DESIGN-v19-presence-identity.md` — presence registry and active-agent semantics.
- `DESIGN-v22-agent-bridge-memory-substrate.md` — memory substrate as stateful recall layer.
- Codex hook notes in memory: `UserPromptSubmit`, `PreCompact`, `Stop`, `SessionEnd`, and `sessionEndCurate`.

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
- It emits no audio and does not modify the official Codex pet package.
- Debug MCP validation confirmed `pet_presence_sync` is absent from Essential, present in Standard, and syncs `xiao-shu-dev / verified / Meijia / 180` into `agent_presence_list`.
- Post-install profile probe confirmed Essential exposes 36 tools with `pet_state_get`, `pet_state_set`, and `pet_state_ritual`, while Standard exposes 96 tools and includes `pet_presence_sync`.
- Post-install Standard sync probe wrote `xiao-shu-dev` into presence with `voice_policy.current_voice="Flo (中文（中国大陆）)"` and `current_rate=190`.

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

Phase 4 is now dogfoodable. Move in this order:

1. Use Phase 4.3 policy during real Codex work for at least one session: silent `working/reviewing`, sparse voice only on `verified/failed/waiting_for_user`.
2. Keep Codex MCP profile at Essential and continue watching `mcp_dispatch_audit` before exposing Standard presence tools.
3. Extend the Phase 5 presence convention only if the live multi-agent UI needs it: first reuse `capabilities.pet_state`, then consider a dedicated `pet_presence_announce` helper.
4. Return to Phase 3 skin switching after the presence loop is stable; do not auto-switch official Codex avatars until app reload behavior is proven.

This preserves the user's preferred pattern: prove the live mechanism first, then expand capability.
