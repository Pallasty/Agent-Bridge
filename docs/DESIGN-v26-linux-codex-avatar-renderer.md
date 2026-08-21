# DESIGN - v26: Linux Codex Avatar Renderer

Status: draft, 2026-06-01.

Predecessors:
- `DESIGN-v23-codex-pet-presence-loop.md` - Codex pet sidecar state and
  presence loop.
- `RFC-v24-agent-avatar-protocol.md` - runtime-neutral avatar state contract.
- `RFC-v25-agent-shadow-cortex.md` - read-only Xiao Shu cortex, language,
  motion, and renderer dry-run surfaces.
- `docs/design/XIAO-SHU-V3-VISUAL-BASELINE-2026-05-26.md` - current Xiao Shu
  v3 visual and motion candidate baseline.

Trigger: Linux Codex sessions can already write and read Agent-Bridge pet and
avatar sidecar state, but this host does not currently expose the official
Codex custom-pet renderer as a visible desktop body. We want a Linux path that
can show a Mac-like embodied Codex companion while preserving the existing
Agent-Bridge safety boundary.

---

## 1. Decision

Build the first Linux embodied avatar as an **Agent-Bridge sidecar renderer**,
not as a mutation of Codex itself.

The first renderer target should be:

- a small transparent desktop floater;
- driven by `pet_state`, `avatar_state_get`, and eventually
  `avatar_surface_snapshot`;
- compatible with the Codex/Petdex sprite package shape where possible:
  `pet.json` plus a transparent sprite atlas;
- implemented as a replaceable output adapter, so the same avatar protocol can
  later drive Wayland-native, Qt/GTK, Live2D, VRM, browser-panel, and terminal
  renderers.

The product boundary stays unchanged:

- Agent-Bridge owns semantic state.
- Renderers consume state and show pixels.
- Official Codex pet packages are read-only assets unless a separate explicit
  promotion decision says otherwise.
- Avatar state is not proof of work.
- Voice and action requests remain behind existing sparse explicit gates.

---

## 2. Goals

| Goal | Acceptance |
|---|---|
| G1: Make Xiao Shu visible on Linux Codex | A local Linux session can show a small animated companion whose mode follows Agent-Bridge sidecar state |
| G2: Preserve protocol portability | Renderer consumes Agent Avatar Protocol fields, not Codex logs directly |
| G3: Reuse existing visual assets | The first path can render Codex-compatible sprite atlases and Xiao Shu sidecar prototype atlases |
| G4: Keep desktop integration reversible | The renderer can be stopped without changing Codex config, pet package selection, memory, or hooks |
| G5: Support Linux display diversity | The architecture can fall back from native Wayland/X11 integration to a WebView/browser floater |
| G6: Keep safety boundaries visible | No HTTP/MCP route directly emits audio, mutates the official pet package, approves actions, or controls the host desktop |

---

## 3. Non-goals

- Do not implement a full Live2D or VRM avatar as the first slice.
- Do not require GNOME, KDE, Sway, or another compositor-specific extension for
  the MVP.
- Do not make the renderer parse raw Codex transcripts as its primary contract.
- Do not add new Essential-profile MCP tools just to support pixels.
- Do not auto-switch Codex's selected avatar.
- Do not make renderer liveness a condition for Agent-Bridge correctness.

---

## 4. Open-Source Survey Findings

The current open-source desktop-pet ecosystem clusters into a few useful
patterns.

| Pattern | Representative projects | Rendering approach | Lessons for Agent-Bridge |
|---|---|---|---|
| Codex-compatible sprite pets | Petdex, codex-pet.com, OpenPets | `pet.json` plus transparent sprite atlas, often animated with CSS or simple frame stepping | Best first asset contract; cheap, inspectable, and close to the existing Xiao Shu V2/V3 work |
| Agent-aware desktop floater | OpenPets, Agent Paperclip, CommitCat, tama96 | Electron/Tauri/WebView transparent window with tray, local IPC, file watching, or MCP sidecar | Strong match for Agent-Bridge: keep state and renderer separate, use local IPC/file watcher, expose small safety surface |
| Shimeji-style mascot engines | Shimeji-Desktop, Shijima-Qt, wl_shimeji | XML/image behavior scripts, Java/Qt/C native windows, Wayland layer-shell in wl_shimeji | Borrow behavior grammar and Linux windowing lessons; avoid making this the MVP dependency |
| Live2D companions | Bongo Cat Next, Open-LLM-VTuber, Petto | Live2D WebGL or external viewer, transparent window, speech/ASR/TTS hooks | Good optional second renderer, especially for expressions; too much runtime and asset complexity for the first slice |
| 3D VRM companions | Mate Engine and similar Unity/VRM tools | 3D model renderer with motion, tracking, and touch areas | Keep as a future plugin backend, not default Codex work companion |
| Terminal pets | tama96 TUI and classic terminal/image protocols | ANSI/ratatui/Sixel/Kitty image protocol | Useful fallback for CLI-only hosts; lower embodied presence than a desktop floater |

Source links recorded for this design pass:

- `https://github.com/alvinunreal/openpets`
- `https://openpets.dev/docs`
- `https://github.com/crafter-station/petdex`
- `https://www.codex-pet.com/`
- `https://github.com/fredruss/claude-companion`
- `https://github.com/eunseo9311/commit-cat`
- `https://github.com/DalekCraft2/Shimeji-Desktop`
- `https://github.com/pixelomer/Shijima-Qt`
- `https://github.com/CluelessCatBurger/wl_shimeji`
- `https://github.com/liwenka1/bongo-cat-next`
- `https://github.com/Open-LLM-VTuber/Open-LLM-VTuber`
- `https://github.com/funnycups/petto`
- `https://github.com/shinyflvre/Mate-Engine`
- `https://github.com/siegerts/tama96`

---

## 5. Architecture

```text
Codex hooks / MCP calls / heartbeat / cortex preview
        |
        v
Agent-Bridge sidecar state
  - pet_state/<pet_id>.json
  - avatar_state_get projection
  - avatar_surface_snapshot projection
        |
        v
Renderer adapter boundary
  - normalize mode, activity_state, renderer_token
  - choose track and frame timing
  - choose asset source
        |
        v
Output backend
  - MVP: transparent WebView/Tauri/Electron floater
  - fallback: browser panel or TUI
  - later: Wayland/X11 native, Qt/GTK, Live2D, VRM
```

The renderer adapter should treat `motion.animation_hint.renderer_token` as a
hint, not an authority. If the token is unknown, fall back to a quiet idle loop
and surface the unresolved mapping in diagnostics.

---

## 6. Renderer Backends

### 6.1 MVP Backend: Sprite Floater

Use a transparent always-on-top window that renders a sprite atlas through CSS
or canvas frame stepping.

Inputs:

- sidecar JSON file watcher for `pet_state/<pet_id>.json`;
- optional polling of `avatar_state_get` for projected protocol fields;
- optional later HTTP endpoint when the daemon is running.

Assets:

- installed Codex-compatible packages under `${CODEX_HOME:-$HOME/.codex}/pets`;
- sidecar prototype atlases under `crates/bridge/assets/xiao-shu-prototypes`;
- future generated package candidates only after explicit review.

Behavior:

- `idle` -> idle breath or calm blink;
- `orienting` / `reviewing` -> focused review or look-sideways;
- `working` -> sorting/glow or running/work loop;
- `waiting_for_user` -> gentle hold state;
- `failed` -> visible mismatch/risk state;
- `verified` -> completion nod, not a jump for half-body shapes;
- unknown/stale -> quiet idle.

### 6.2 Browser Panel Fallback

The existing `/avatar-surface/panel` and `/avatar-surface/cortex-renderer-view`
path is a good fallback when transparent windows are unreliable. The MVP should
reuse that rendering logic where practical rather than duplicate every motion
mapping.

### 6.3 Native Linux Backend

After the MVP is proven, add a native output adapter if needed:

- Wayland `wlr-layer-shell` for wlroots compositors;
- X11 override-redirect or shaped window fallback;
- Qt/GTK shell when desktop environment compatibility is more important than
  low-level control.

This backend must be optional because GNOME/Mutter, KDE, Sway, and X11 differ
substantially in always-on-top, click-through, transparency, and window-tracking
behavior.

### 6.4 Live2D and VRM Backends

Live2D and VRM remain optional renderers behind the same protocol. They are
allowed to enrich expression and gaze, but they must not introduce a second
semantic state model.

### 6.5 Backend Selection And Transparency Portability (LCC-F1)

Slice 6 proved the browser app-window path cannot produce real alpha on this
host (opaque dark surface), and slice 7 proved native Wayland
`wlr-layer-shell` ARGB8888 does. So **transparency is verified only on wlroots
compositors.** On every other compositor there is no verified transparent
backend — that is a real portability gap, and it must be *explicit*, not a
silent blind spot.

`agent-bridge avatar backend-probe [--json]` makes it explicit. It is env-only
and read-only (no spawn, no compositor IPC, no desktop control): it reports the
detected compositor and a backend recommendation **with an inspectable reason**.
The pure core is `recommend_backend(detect_compositor())` in `avatar_floater.rs`
(unit-tested).

| Detected environment | Backend | Transparency |
|---|---|---|
| wlroots on Wayland (sway/hyprland/river/wayfire/labwc) | `native_transparent` | ✅ verified (slice 7) |
| GNOME / Mutter (Wayland) | `browser_degraded` | ❌ no `wlr-layer-shell` |
| KDE / KWin (Wayland) | `browser_degraded` | ❌ supports layer-shell but **unverified here** |
| X11 / unknown / no Wayland display | `browser_degraded` | ❌ |

The degraded path stays functional (a non-transparent floater); the probe just
names *why* transparency is unavailable. Launch flows should consult the probe
before claiming a transparent body. The matrix is conservative on purpose:
KDE/KWin does implement `wlr-layer-shell`, but until this project verifies alpha
there we never *claim* it — no unverified transparency assertions.

### 6.6 Floater Liveness And Supervision

The browser floater and the native surface are separate, CLI-launched
processes. Per G4/G6 the renderer's death must not affect Agent-Bridge
correctness — and it does not (fully decoupled). But for a *daily* companion,
silent death means the body simply vanishes with no signal.

Liveness contract (design):

- A launch should be probe-able for aliveness — pair a PID-liveness check with a
  *window-mapped* check, mirroring the dock's idempotent open ("if a window is
  already mapped, focus it; else launch"). Process-alive alone is not health.
- An optional supervisor may re-launch on death within a backoff, but it stays
  **off by default**, never escalates privileges, and never re-acquires desktop
  control beyond re-opening the same read-only renderer.
- Liveness remains one-way: observability + optional restart, never a
  correctness dependency. See `lesson_process_alive_vs_health_freshness`
  (process-alive ≠ fresh: pair kill-0 with window-mapped + recent state poll).

---

## 7. State And Mapping Contract

The renderer consumes a compact projection:

```json
{
  "agent_avatar_protocol": 1,
  "avatar_id": "xiao-shu-v2",
  "runtime": "codex",
  "project": "agent-bridge",
  "mode": "working",
  "activity_state": "documenting",
  "focus": "avatar-renderer",
  "risk_level": "low",
  "blocked_reason": null,
  "evidence": "pet_state_get returned current sidecar JSON",
  "next_action": "render sprite floater",
  "compat": {
    "codex": {
      "pet_id": "xiao-shu-v2",
      "package_contract": "codex-pet-atlas-8x9-v1"
    }
  }
}
```

Minimum mapping table:

| Protocol input | Renderer track | Notes |
|---|---|---|
| `mode=idle` | `idle_breathe` | low motion |
| `mode=orienting` | `focused_review` | reading intent |
| `mode=reviewing` | `look_sideways` or `focused_review` | review and mismatch scan |
| `mode=working` | `sorting_glow` | avoids literal running unless asset demands it |
| `mode=waiting_for_user` | `waiting_for_user` | stable hold, no pressure |
| `mode=failed` | `mismatch` | visible risk without alarm spam |
| `mode=verified` | `completion_nod` | v3 rule: half-body completion is nod/blink/smile |
| stale or unknown | `idle_breathe` | quiet fallback |

---

## 8. Safety And Privacy

- Renderer reads local compact state only; it should not receive full prompts,
  command transcripts, secrets, screenshots, or memory bodies.
- Renderer does not approve tools, click the desktop, type, or execute shell
  commands.
- Renderer may show speech bubbles from curated short state text, but audio
  output stays behind existing CLI-only gates.
- File watching is local and one-way: state -> pixels.
- IPC, if added, requires a local token or Unix-domain-socket permission model.
- Logs must avoid source code and prompt bodies by default.

---

## 9. Validation Plan

### Current-State Probe

Run these before implementation:

- `avatar_adapter_capabilities`: verify Linux exposes sidecar, presence, and
  notification surfaces, and note whether official pet package rendering is
  available.
- `pet_state_get`: verify the current `pet_id`, path, mode, and update time.
- `avatar_state_get`: verify protocol projection for the current pet state.
- `avatar_cortex_renderer_snapshot(mode=renderer_view|binding_plan)`: verify
  existing renderer-token mappings and binding safety.
- `desktop_snapshot`: record the active Linux desktop/window environment without
  mutating it.

### MVP Acceptance

- A Linux renderer window opens and can be closed cleanly.
- The window displays a nonblank transparent sprite at desktop scale.
- `pet_state_set(mode=working|reviewing|waiting_for_user|verified|failed)`
  changes the visible track within one second.
- Stale or malformed state falls back to quiet idle.
- CPU usage remains low during idle.
- No audio, notifications, package mutation, or host desktop control occurs.
- Browser/panel fallback remains available if transparent floater support fails.

---

## 10. Live Verification - 2026-06-01

Host probe:

- Current host node: `aio2`.
- Current project cwd: `/Data/CascadeProjects/agent-bridge`.
- Desktop compositor: Sway.
- Outputs: `DP-3` at `3840x2160`, `DP-1` at `1920x1080`.
- Active windows are regular Sway windows; this makes Wayland layer-shell a
  plausible later native backend, but a WebView/browser floater is still the
  safer MVP.

Agent-Bridge avatar probe:

- `avatar_adapter_capabilities` reports `frontend_detected=codex`.
- Codex input surfaces are available through hooks JSON and MCP.
- Codex output surfaces available now: sidecar state, presence, notification.
- Codex official pet package output is not available on this Linux host:
  `official_pet_package=false`.
- TTS is not available on this Linux host: `tts.backend=none`.
- Sidecar state exists at
  `/home/pallasting/.local/share/agent-bridge/pet_state/xiao-shu-v2.json`.

Codex package filesystem probe:

- `/home/pallasting/.codex/pets` does not exist on this host.
- `/home/pallasting/.codex/.codex-global-state.json` does not exist on this
  host.
- Therefore the first Linux visible body cannot depend on an installed official
  Codex pet package being present.

State correction and projection probe:

- Initial `pet_state_get` showed `xiao-shu-v2` in `mode=handoff` for a different
  project/worktree: `s15-audit`. This was expected sidecar behavior but is an
  important renderer-source warning.
- The sidecar was then updated to the current project with
  `mode=reviewing`, `activity_state=documenting-and-validating`,
  `focus=linux-avatar-renderer`, and `risk_level=low`.
- `pet_presence_sync` wrote presence for `session_id=aio2:agent-bridge:codex`
  without audio, notification, or Codex package mutation.
- `avatar_surface_snapshot(project=agent-bridge)` then returned one fresh avatar
  row with both `has_avatar_state=true` and `has_compat_pet_state=true`.

Renderer dry-run probe:

- `avatar_cortex_renderer_snapshot(mode=renderer_view)` reports
  `browser_renders_pixels=true`, `writes_files=false`,
  `mutates_renderer=false`, and `codex_pet_package_mutation=false`.
- Current sidecar renderer view exposes 5 tracks:
  - selected low-risk: `soft_bounce`, `idle_breathe`;
  - review-only medium-risk: `sorting_glow`, `look_sideways`, `alert_peek`.
- The binding plan selects only low-risk resolved candidates first and defers
  medium-risk or fallback tokens until manual review.

Renderer HTTP/browser proof:

- Temporary daemon HTTP route
  `/avatar-surface/linux-renderer-state?project=agent-bridge&include_stale=true`
  returned `surface=linux_codex_avatar_renderer_state`.
- State selection used `source=projected_avatar`, proving the current renderer
  can avoid stale cross-project raw pet state.
- Current plan mapped `mode=reviewing` to `track=look_sideways`,
  `renderer_token=xiao_shu::look_sideways::medium`, and sidecar asset route
  `/avatar-surface/sidecar-spritesheet?asset=xiao-shu-motion-canonical-look-sideways-v2`.
- Temporary browser proof route
  `/avatar-surface/linux-renderer?project=agent-bridge&include_stale=true`
  rendered to `/tmp/linux-codex-avatar-renderer.png` with Chrome headless.
- Screenshot verification: `520x680`, `unique_colors=4752`,
  `non_white_pixels=353600`, `non_white_ratio=1.0000`.
- Visual inspection showed the Xiao Shu sprite, current state, selected track,
  renderer token, sidecar asset route, and read-only safety flags on the page.

Design impact:

- The MVP renderer should prefer the projected avatar/presence path when it
  needs a project-specific current agent state.
- A raw `pet_state/<pet_id>.json` watcher is still useful for fast updates, but
  it must treat `project`, `cwd`, and `updated_at` as part of freshness and
  ownership validation.
- If the renderer watches only the default pet file, it may show another
  project's latest stop/handoff state.

Implementation slice 1:

- Added `crates/bridge/src/avatar_renderer.rs` as a pure state adapter.
- Added integration coverage in `crates/bridge/tests/avatar_renderer.rs`.
- The adapter chooses projected avatar/presence state over raw pet JSON.
- Raw pet JSON is accepted only when `project` and scoped `cwd` match.
- Cross-project raw pet state falls back to `idle` with
  `fallback_reason=raw_pet_scope_mismatch`.
- Added lifecycle-to-track mapping:
  - `idle` / stale / `handoff` -> `idle_breathe`;
  - `orienting` -> `focused_review`;
  - `reviewing` -> `look_sideways`;
  - `working` -> `sorting_glow`;
  - `waiting_for_user` -> `waiting_for_user`;
  - `failed` -> `mismatch`;
  - `verified` -> `completion_nod`.
- Added JSON payload surface `linux_codex_avatar_renderer_state` with explicit
  safety flags.

Implementation slice 2:

- Added daemon HTTP read-only routes:
  - `/avatar-surface/linux-renderer-state`
  - `/avatar-surface/linux-renderer`
- The HTML proof embeds the renderer payload and displays the selected sidecar
  spritesheet route without writing files, mutating renderer assets, emitting
  audio, or controlling the desktop.
- Added focused daemon HTTP HTML coverage for the Linux renderer proof.

Implementation slice 3:

- Added `crates/bridge/src/avatar_floater.rs` as the first Linux floater launch
  helper.
- Added `agent-bridge avatar linux-floater` CLI support.
- The CLI builds a daemon renderer URL and opens it in a small browser app
  window by default.
- `--dry-run --json` emits a launch plan without spawning a browser, so the
  floater contract can be tested without controlling the desktop.
- The first supported browser candidates are `google-chrome`, `chromium`,
  `chromium-browser`, `brave-browser`, and `microsoft-edge`; `--browser`
  can override detection.

Implementation slice 4:

- The Linux renderer page now carries a `data-state-url` pointing at
  `/avatar-surface/linux-renderer-state`.
- The page polls that state URL every second with `cache: "no-store"`.
- `applyRendererPayload(nextPayload)` updates the visible track, renderer
  token, sidecar asset route, status fields, and JSON debug payload without a
  full page refresh.
- The polling path remains read-only: no file writes, no notifications, no
  audio, no renderer mutation, and no desktop control.

Dogfood state-transition check:

- Started a temporary daemon on `127.0.0.1:7892`.
- Updated the sidecar to `mode=working`, ran `avatar sync-presence`, and queried
  `/avatar-surface/linux-renderer-state?project=agent-bridge&include_stale=true`.
  Result: `source=projected_avatar`, `mode=working`, `track=sorting_glow`,
  `renderer_token=xiao_shu::sorting_glow::medium`, asset
  `xiao-shu-motion-canonical-sorting-glow-v3`.
- Updated the sidecar to `mode=verified`, ran `avatar sync-presence`, and queried
  the same route. Result: `source=projected_avatar`, `mode=verified`,
  `track=completion_nod`, `renderer_token=xiao_shu::completion_nod::low`, asset
  `xiao-shu-v3-ai-completion-nod-v1`.
- The HTML route included the expected state URL, polling script, `fetch`
  call, current `completion_nod` track, and completion asset token.

Implementation slice 5:

- Tested a real Chrome app-window floater on Sway.
- Default Chrome profile handoff was unreliable for window identity, so
  `avatar linux-floater` now launches Chrome with an isolated user data dir:
  `--user-data-dir=$XDG_RUNTIME_DIR/agent-bridge-avatar-chrome-<pid>` when
  available, otherwise a temp dir. The per-launch suffix avoids stale Chrome
  `SingletonLock` failures after a crash or interrupted test run.
- Chrome app mode is launched with `--app=...` only. The local Chrome/Wayland
  build exits when `--new-window` is combined with `--app`.
- Added explicit Sway management support behind `--sway-manage`.
- `--sway-manage` runs a title-scoped `swaymsg` command after launch:
  floating enable, sticky enable, border none, resize, and move.
- The Sway management step retries briefly while Chrome creates the toplevel
  window, avoiding the race where `swaymsg` runs before the title exists.
- Browser processes are launched through external `setsid` on Unix. The Rust
  `pre_exec(setsid)` path was less reliable with this Chrome build.

Sway dogfood check:

- Direct Chrome app launch with isolated profile produced a stable Sway window:
  title `Linux Codex Avatar Renderer`, app_id
  `chrome-127.0.0.1__avatar-surface_linux-renderer-Default`.
- Without Sway management the window tiled at desktop scale.
- Manual `swaymsg` management transformed it to `floating=user_on`,
  `sticky=true`, `360x520`.
- CLI launch with
  `avatar linux-floater --sway-manage --sway-x 3460 --sway-y 180`
  returned `sway_managed=true`.
- Sway tree verification after CLI launch showed the renderer window at
  `360x520`, `floating=user_on`, `sticky=true`, `visible=true`.
- Conclusion before transparency: browser app-window plus Sway management is
  sufficient for a non-transparent dogfood window.

Implementation slice 6:

- Added `--transparent` to `avatar linux-floater`.
- `--transparent` appends `transparent=true` to the renderer route.
- The Linux renderer route now supports transparent pet-only mode:
  `data-transparent=true`, transparent page/stage CSS, hidden debug panel, and
  the same 1s state polling path.
- Do not pass Chrome `--enable-transparent-visuals`: on the current Sway/Wayland
  Chrome build it exits before creating a toplevel window.

Transparency dogfood check:

- The transparent HTML contract is present:
  `data-transparent=true`, `background:transparent`, hidden `.debug-panel`, and
  `transparent=true` preserved in the state URL.
- CLI launch with `--transparent --sway-manage` now creates a stable Sway
  window after removing `--new-window`, using per-launch profile dirs, and
  launching through external `setsid`.
- Screenshot crop of the transparent route at `360x520` showed an opaque dark
  browser surface, not compositor transparency. A second crop after killing the
  window showed the underlying Cursor text, proving the browser surface had been
  covering it.
- Therefore transparent background is not satisfied by the browser backend on
  this host. Native Wayland/layer-shell or another toolkit with real alpha is
  required for the mandatory transparent final target.

Verification:

- `cargo test -p ab-bridge --test avatar_floater` passed with 7 tests.
- `cargo test -p ab-bridge --test avatar_renderer` passed with 6 tests.
- `cargo test -p ab-bridge linux_renderer_html` passed with 2 tests.
- `cargo run -p ab-bridge -- avatar linux-floater --dry-run --json --project agent-bridge --include-stale --base-url http://127.0.0.1:7878`
  returned a read-only `linux_avatar_floater_launch_plan` using
  `browser=google-chrome`, `--window-size=360,520`, and the expected
  `/avatar-surface/linux-renderer?project=agent-bridge&include_stale=true`
  URL.
- The targeted tests were rerun after reverting unrelated repository-wide
  formatting spill from an accidental `cargo fmt --all`.
- `git diff --check` passed.

Fresh close-out verification, 2026-06-01:

- `cargo test -p ab-bridge --test avatar_floater --test avatar_renderer`
  passed with 13 tests.
- `cargo test -p ab-bridge linux_renderer_html` passed with 2 tests.
- `git diff --check` passed.
- Sway tree check returned no lingering `Linux Codex Avatar Renderer` or
  `agent-bridge-avatar` window entries after cleanup.

Implementation slice 7:

- Added `crates/bridge/src/avatar_native.rs` as the first native transparency
  spike.
- Added Linux-only dependencies on `smithay-client-toolkit` and
  `wayland-client`.
- Added `agent-bridge avatar linux-native-transparent`.
- The native probe uses wlroots layer-shell plus `wl_shm::Format::Argb8888`.
- Default probe shape is `360x520`, `layer=overlay`,
  `anchor=bottom-right`, and margins `right=96`, `bottom=96`.
- The probe does not emit audio, notifications, package mutations, file writes,
  renderer mutations, or desktop control.
- It draws a fully transparent buffer with a small opaque marker in the middle,
  so compositor screenshots can distinguish true alpha from an opaque dark
  window.

Native transparency dogfood check:

- Command:
  `target/debug/agent-bridge avatar linux-native-transparent --width 240 --height 240 --margin-right 420 --margin-bottom 320 --duration-ms 4000 --json`.
- Result payload returned `spawned=true`, `backend=wayland_wlr_layer_shell`,
  `transparent=true`, and `pixel_format=wl_shm::Argb8888`.
- During the 4s run, `grim` captured the expected probe region.
- A second crop after the probe exited was compared against the probe crop.
- Pixel result: `unchanged_ratio=0.9421`, `diff_ratio=0.0579`.
- The crop corner stayed identical before/after: `(60, 60, 60)`.
- The crop center changed from background `(60, 60, 60)` to marker
  `(77, 208, 225)`.
- Conclusion: native Wayland/layer-shell ARGB8888 satisfies the mandatory
  transparent-background requirement on this Sway host.

Implementation slice 8:

- Added native sprite atlas decoding with the lightweight `png` crate.
- Native rendering now supports sidecar PNG atlases using the same
  `1536x1872` atlas and `192x208` cell contract as the browser renderer.
- Added `asset_route -> asset_id` extraction so native rendering can consume
  renderer-plan asset routes.
- Added `native_sprite_asset_for_mode(mode)` as the first bridge from lifecycle
  mode to a native-renderable PNG sprite. When the shared renderer plan points
  at an SVG-only sidecar asset, the native backend falls back to a matching v3
  PNG candidate.
- `agent-bridge avatar linux-native-transparent` now accepts:
  `--mode`, `--asset`, `--frame-col`, `--frame-row`, `--cell-width`,
  `--cell-height`, and `--sprite-scale-percent`.
- `--asset none` keeps the old marker-only transparency probe available.

Native sprite dogfood check:

- Dry run with `--mode verified` selected
  `sprite.asset=xiao-shu-v3-ai-completion-nod-v1`.
- Real run:
  `target/debug/agent-bridge avatar linux-native-transparent --mode verified --width 360 --height 520 --margin-right 420 --margin-bottom 240 --duration-ms 4500 --json`.
- Result payload returned `spawned=true`, `transparent=true`, and the expected
  completion-nod sprite metadata.
- A compositor crop while visible showed Xiao Shu rendered over the desktop with
  the terminal text visible behind all transparent sprite pixels.
- Crop comparison after exit: `diff_ratio=0.2292`,
  `strong_diff_ratio=0.2272`.
- Crop corner stayed identical: `(20, 20, 20)` before and after.
- Conclusion: the native backend now renders a real transparent sprite, not
  only a marker.

Implementation slice 9:

- Added native atlas animation frame stepping for the Wayland/layer-shell
  backend.
- `NativeTransparentOptions` now carries `frame_count` and
  `frame_interval_ms`; defaults are `6` frames at `180ms`, matching the
  browser renderer's common idle/soft-bounce row contract.
- Added pure helpers for `animation_frame_index(elapsed_ms, frame_count,
  frame_interval_ms)` and `animated_frame_coords(base_col, base_row, ...)`,
  including atlas row wrapping.
- The native runtime now stores the decoded atlas, computes the current cell
  from elapsed time, redraws only when the frame index changes, and performs a
  Wayland roundtrip after redraw so SHM buffer releases are processed.
- `agent-bridge avatar linux-native-transparent` now accepts
  `--frame-count` and `--frame-interval-ms`.

Native animation dogfood check:

- Dry run:
  `cargo run -p ab-bridge -- avatar linux-native-transparent --dry-run --json --mode verified --width 240 --height 240 --frame-count 4 --frame-interval-ms 120`.
- The JSON plan reported `sprite.asset=xiao-shu-v3-ai-completion-nod-v1`,
  `frame_count=4`, and `frame_interval_ms=120`.
- Real short run:
  `target/debug/agent-bridge avatar linux-native-transparent --mode verified --width 260 --height 320 --margin-right 420 --margin-bottom 240 --duration-ms 1500 --frame-count 4 --frame-interval-ms 120 --json`.
- Result payload returned `spawned=true`, `transparent=true`, and the expected
  animated sprite metadata.
- Motion crop check with `--mode working` and `xiao-shu-v3-ai-soft-bounce-v1`
  compared two in-flight compositor screenshots inside the located sprite bbox
  `(3122,1563)-(3357,1811)`.
- Pixel result: `changed_ratio=0.7902`,
  `strong_changed_ratio=0.5556`, with `diff_bbox_in_crop=(0,7)-(235,248)`.
- Conclusion: the native backend now advances atlas frames in a real
  transparent Wayland surface.

Implementation slice 10:

- Added native live state polling for the Wayland/layer-shell backend.
- `NativeTransparentOptions` now carries `state_pet_id` and `state_poll_ms`.
  Passing `--pet-id` enables polling of the Agent-Bridge pet sidecar JSON at
  `~/.local/share/agent-bridge/pet_state/<pet_id>.json` (or the
  `XDG_DATA_HOME` equivalent).
- Added `NativeSpritePlan` plus pure helpers that accept either raw pet-state
  JSON or the HTTP renderer-state payload shape. This keeps the native backend
  compatible with both the local sidecar path and the daemon route planned for a
  later adapter.
- The native runtime now polls sidecar state on a timer, maps `mode` to a
  native PNG sprite/timing plan, hot-swaps the decoded atlas when the plan
  changes, resets animation timing, and redraws the transparent surface.
- `agent-bridge avatar linux-native-transparent` now accepts:
  `--pet-id` and `--state-poll-ms`.

Native live-state dogfood check:

- Dry run without a sidecar file:
  `cargo run -p ab-bridge -- avatar linux-native-transparent --dry-run --json --mode working --pet-id ab-native-live-test --state-poll-ms 250 --width 240 --height 240`.
- The JSON plan reported `state_poll.enabled=true`,
  `state_poll.pet_id=ab-native-live-test`, and
  `state_poll.poll_ms=250`.
- Real short run:
  `target/debug/agent-bridge avatar linux-native-transparent --mode working --pet-id ab-native-live-test --state-poll-ms 250 --width 260 --height 320 --margin-right 420 --margin-bottom 240 --duration-ms 1200 --json`.
- Result payload returned `spawned=true`, `transparent=true`, and
  `state_poll.enabled=true`.
- Isolated sidecar dry run:
  a temporary `ab-native-live-test.json` with `mode=working` was created, then
  `target/debug/agent-bridge avatar linux-native-transparent --dry-run --json --mode idle --pet-id ab-native-live-test --state-poll-ms 250 --width 240 --height 240`
  was run and the file was removed.
- Result payload selected `sprite.asset=xiao-shu-v3-ai-soft-bounce-v1` and
  `frame_interval_ms=160`, proving sidecar state overrides the static CLI mode
  for native rendering.

Implementation slice 11:

- Dogfooded end-to-end sidecar state transitions against the native
  Wayland/layer-shell transparent surface.
- Test pet id: `ab-native-live-test`, isolated from the default Xiao Shu pet.
- Flow:
  1. Start native renderer with
     `target/debug/agent-bridge avatar linux-native-transparent --mode idle --pet-id ab-native-live-test --state-poll-ms 150 --width 360 --height 520 --margin-right 420 --margin-bottom 240 --duration-ms 5000 --json`.
  2. Capture an idle screenshot.
  3. Write `mode=working` into
     `~/.local/share/agent-bridge/pet_state/ab-native-live-test.json`.
  4. Capture a working screenshot.
  5. Write `mode=verified` into the same sidecar file.
  6. Capture a verified screenshot.
  7. Remove the temporary sidecar file.
- Native process result returned `spawned=true`, `transparent=true`, and
  `state_poll.enabled=true`; stderr was empty.
- Compositor screenshot analysis found the sprite components at:
  idle `(3126,1572)-(3357,1817)`, working `(3122,1563)-(3357,1811)`,
  verified `(3126,1575)-(3355,1819)`.
- Crop comparison over union bbox `(3122,1563)-(3357,1819)`:
  idle vs working `changed_ratio=0.7161`,
  working vs verified `changed_ratio=0.7153`,
  idle vs verified `changed_ratio=0.6619`.
- Conclusion: native live polling can hot-swap visible sprite tracks while the
  transparent surface is running.

Implementation slice 12:

- Added daemon HTTP renderer-state polling for the native Wayland/layer-shell
  backend.
- `NativeTransparentOptions` now carries `state_url`,
  `state_http_timeout_ms`, and the existing `state_pet_id` fallback.
- `agent-bridge avatar linux-native-transparent` now accepts:
  `--state-url`, `--state-http-timeout-ms`, `--pet-id`, and
  `--state-poll-ms`.
- When `--state-url` is provided, the JSON plan reports
  `state_poll.source=http_renderer_state`, includes the URL and timeout, and
  treats HTTP as the primary live state source.
- If both `--state-url` and `--pet-id` are provided, HTTP is tried first; a
  failed HTTP poll falls back to the local pet sidecar for that poll.
- The runtime deliberately uses a tiny synchronous plain-HTTP request helper
  for local daemon routes instead of `reqwest::blocking`, because dropping a
  blocking reqwest runtime from this async CLI context can panic. This path is
  intended for local `http://127.0.0.1:...` renderer-state endpoints, not TLS
  or arbitrary remote URLs.
- The HTTP payload is mapped through the same
  `native_sprite_plan_from_state_value` helper as local sidecar JSON, so daemon
  renderer-state payloads and raw pet-state JSON continue to share the native
  sprite/timing adapter.

Native HTTP-state verification:

- Added red/green tests for:
  - HTTP renderer-state plan JSON.
  - HTTP priority with local sidecar fallback metadata.
  - Plain-HTTP URL request part parsing and HTTPS rejection.
- Dry run:
  `cargo run -p ab-bridge -- avatar linux-native-transparent --dry-run --json --mode idle --state-url http://127.0.0.1:9/avatar-surface/linux-renderer-state --pet-id http-fallback-test --state-poll-ms 150 --state-http-timeout-ms 250 --width 240 --height 240`.
- Result payload reported `state_poll.enabled=true`,
  `state_poll.source=http_renderer_state`,
  `state_poll.url=http://127.0.0.1:9/avatar-surface/linux-renderer-state`,
  `state_poll.pet_id=http-fallback-test`, and
  `state_poll.http_timeout_ms=250`.
- Runtime check with a local mock renderer-state server on
  `http://127.0.0.1:19187/state` returned `spawned=true`,
  `transparent=true`, and `state_poll.source=http_renderer_state`.
- The mock server observed 8 `GET /state` requests during the short native run,
  proving that the live transparent surface polls daemon-shaped HTTP state at
  runtime.

---

## 11. Implementation Plan

Current status: items 1-15 have landed in the repository as of 2026-08-21. The
native Wayland/layer-shell backend is the first backend on this host that
satisfies the mandatory transparent-background requirement, and it now renders a
real animated sidecar sprite that can poll local pet sidecar state or daemon
HTTP renderer-state and hot-swap tracks during a running transparent surface.
The foreground `linux-live` loop now supplies the first ergonomic, project-aware
presence and renderer dogfood path. The next boundary is real-use evidence, not
automatic service installation.

1. **Probe and record current Linux state.** Done.
   Save the exact sidecar path, active `pet_id`, official-package availability,
   desktop environment hints, and current renderer dry-run result.

2. **Choose the MVP state source.** Done.
   Use projected avatar state or presence rows as the authoritative
   project-aware source. Use raw pet JSON as a low-latency hint only when
   `project`, `cwd`, and freshness match the selected renderer scope.

3. **Extract a renderer state adapter.** Done.
   Add a small pure module or script that maps Avatar Protocol fields to
   `{track, asset, frame_timing, fallback_reason}`. Test it without pixels.

4. **Build a browser renderer proof.** Done.
   Reuse the existing sidecar renderer-view and sprite assets to render the MVP
   tracks in a standalone browser/WebView route.

5. **Wrap the proof as a Linux floater.** Done for browser app-window MVP.
   Choose Tauri/Electron/GTK after a minimal local probe. The first choice
   should prefer implementation speed and reliable transparency over native
   perfection.

6. **Dogfood state transitions.** Done for HTTP/browser MVP.
   Drive the floater with `pet_state_set` and real Codex hook events. Record
   visual review notes before adding more tracks.

7. **Decide native backend need.** Done.
   Only add Wayland/X11-specific overlay code if the WebView floater cannot
   satisfy daily Linux use.

8. **Build a native transparent backend spike.** Done.
   Prefer a small Wayland/wlroots path for this host first. The acceptance bar
   is a visible sprite or placeholder over a transparent window, verified by a
   compositor screenshot showing the desktop behind transparent pixels.

9. **Render a real native sprite.** Done.
   Decode sidecar PNG atlases, extract a single cell, and render it over the
   transparent Wayland surface using the same lifecycle mode mapping as the
   renderer state adapter where native PNG assets are available.

10. **Animate native sprite frames.** Done.
    Add frame stepping over sidecar PNG atlases, expose frame count and interval
    CLI controls, and verify in-flight compositor screenshot deltas.

11. **Poll local pet sidecar state.** Done.
    Allow the native backend to watch `pet_state/<pet_id>.json`, map state mode
    into a native sprite/timing plan, and hot-swap atlas animation while the
    transparent surface is running.

12. **Dogfood end-to-end sidecar transitions.** Done.
    Run the native surface while mutating a temporary pet sidecar through
    `idle -> working -> verified`, and verify visible compositor screenshot
    deltas across state changes.

13. **Poll daemon HTTP renderer-state.** Done.
    Allow the native backend to poll a local
    `/avatar-surface/linux-renderer-state` URL, prefer that source over raw
    sidecar state when configured, and retain `--pet-id` as a local fallback for
    failed HTTP polls.

14. **Run a bounded owner-local live loop.** Done for EAP-1A.
    `agent-bridge avatar linux-live` refreshes one stable presence row while the
    native transparent renderer polls the same pet sidecar. It is foreground
    only and keeps audio, notifications, desktop control, action execution,
    service installation and `embodiment-runtime-p4` disabled. A 10.059-second
    live run produced four heartbeats with zero failures; a concurrent avatar
    surface read returned exactly one stable row in the sidecar's real `handoff`
    state. The pet sidecar SHA-256 was identical before and after the run.

15. **Add default-off sparse Qwen voice feedback.** Done for EAP-1B.
    The live loop can explicitly attach an existing owner-local Qwen3-TTS worker
    to four eligible sidecar transitions. Initial state is silent; fixed lines,
    verified-evidence grounding, a five-minute default cooldown, a three-line
    session budget and no-overlap execution constrain output. The Linux
    `sink_monitor` and fast-emit paths now dispatch Qwen through the same backend
    selector used by synth-file verification instead of falling into the
    Kokoro/Piper binary path. Audio remains opt-in and no service or worker is
    installed or started by the command.

16. **Make bounded dogfood trials measurable.** Done for EAP-1C.
    The foreground receipt now carries a read-only, bounded observation record:
    sidecar poll/read-failure counts, mode-transition samples, maximum observed
    poll gap, process peak RSS and Qwen adapter invocation latency. It explicitly
    leaves compositor pixels, physical display/audio and worker VRAM unobserved,
    so operational sampling cannot be mistaken for end-to-end proof.

---

## 12. Open Questions

1. After ten or more useful real task transitions, should `linux-live` remain a
   foreground command or gain an owner-local systemd user service installer?
2. Should the first floater watch the sidecar JSON directly, poll MCP/HTTP, or
   support both?
3. Which Linux desktops must be treated as Tier 1: GNOME, KDE, Sway, Hyprland,
   or only the current host first?
4. Should Codex/Petdex `pet.json` be treated as the canonical asset format for
   all sprite renderers, or only as the first compatibility adapter?
5. How much speech-bubble text is acceptable before the pet starts feeling noisy?

---

## 13. Decision Summary

- The Linux Mac-like Codex body should be an Agent-Bridge sidecar renderer.
- The first visual backend should be a transparent sprite floater.
- Codex-compatible sprite atlases are the first asset contract.
- Agent Avatar Protocol remains the semantic contract.
- Wayland-native, Live2D, VRM, and terminal renderers are later adapters.
- Safety stays one-way and local: sidecar state becomes pixels, not authority.
