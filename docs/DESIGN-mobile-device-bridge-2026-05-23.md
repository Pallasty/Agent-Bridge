# Mobile Device Bridge

Date: 2026-05-23
Status: MVP + Android dogfood follow-up implemented

## Problem

Phone install/debug work is currently too dependent on screenshots and visual
interpretation. Screenshots are useful as proof or fallback, but they are a
slow primary control loop: the agent has to infer state from pixels, then click
coordinates with weak semantics.

The better loop is structure-first:

1. read device, app, window, UI tree, and log state through ADB;
2. act through selectors or explicit input commands;
3. use screenshots only when structured APIs cannot see the target.

The phone still receives normal GUI actions, but the agent's decision source is
machine-readable state rather than image guessing.

## Feasibility Evidence

Local validation on 2026-05-23:

- `adb` is installed at `/opt/homebrew/share/android-commandlinetools/platform-tools/adb`.
- `adb devices -l` sees one physical phone and two emulators:
  - `3K661F0178H00000` (`PKW110`, Android 16)
  - `emulator-5554` (`sdk_gphone64_arm64`, Android 14)
  - `emulator-5556` (`sdk_gphone64_arm64`, Android 14)
- `dumpsys window` reports foreground apps without screenshot parsing.
- The physical device foreground is
  `com.nexuscivilization.game/com.godot.game.GodotAppLauncher`.
- `uiautomator dump` succeeds on the physical device and returns XML with
  bounds, classes, resource ids, focus flags, and text. For the Godot app, the
  scene is mostly `android.view.SurfaceView`, but the dump still exposes an
  overlay `android.widget.EditText` with text `AutoCity`.
- `logcat -d -t 30` succeeds and provides recent device/app runtime evidence.

Conclusion: the structure-first bridge is feasible on this host today. Game
canvas content will still need screenshot or engine-level hooks, but Android
chrome, overlays, native dialogs, installs, launches, logs, focus state, and
coordinate actions can all be handled through ADB.

## MVP Tool Surface

Implemented a small Android-first MCP surface in
`crates/bridge/src/mcp_tools.rs`:

- `mobile_list_devices`: list `adb devices -l` rows and basic model/version
  properties.
- `mobile_current_focus`: read foreground window/activity from `dumpsys window`.
- `mobile_screenshot`: capture a PNG through `adb exec-out screencap -p`,
  saved to disk by default or returned inline when requested.
- `mobile_health`: collect focus, foreground package, recent logcat
  crash/error markers, and optional UI/canvas analysis in one compact result.
- `mobile_debug_bundle`: collect a bounded local diagnostic directory with a
  JSON manifest, focus state, package details, recent logcat, crash-dropbox
  excerpts, UI XML, and an optional screenshot. It creates a new private
  directory (`0700` on Unix), private files (`0600`), and preserves partial
  results when one source is unavailable.
- `mobile_ui_snapshot`: run `uiautomator dump`, return XML plus a compact node
  summary suitable for selector choice. It now reports whether the visible tree
  is semantic, canvas-only, or SurfaceView-dominated.
- `mobile_wait_for_ui`: poll bounded UIAutomator snapshots until a full
  selector is present or absent. It supports consecutive-snapshot stability,
  compact matched nodes, and a hard total wait budget independent of the
  per-ADB timeout.
- `mobile_logcat_tail`: return recent `logcat` lines, optionally filtered.
- `mobile_install_apk`: install or reinstall an APK on a selected device.
- `mobile_launch_app`: launch an app package or component.
- `mobile_click`: click by coordinates, or resolve one matching UI node and
  click the center of its bounds.
- `mobile_input_text`: send text through `adb shell input text`.
- `mobile_projection_start`: replace any prior companion projection Activity,
  generate an in-memory one-use token, bind a random private-LAN port, and open
  a short-lived title/text projection consent page. It returns no token and
  never presses the consent button or starts the companion service.
- `mobile_projection_status`: inspect one session or recent sessions without
  touching the device. It reports observed pulls and uses deliberately honest
  lifecycle phases: an idle authenticated client is not called disconnected.
- `mobile_projection_update`: replace title/text within an active consented
  session while preserving its endpoint, token, expiry, and zero-authority
  boundary. Status distinguishes host-side revision update from authenticated
  delivery of that revision to the device.
- `mobile_projection_stop`: stop the host listener early and force-stop the
  selected companion package, without starting any background service.
- `mobile_apple_status`: read-only Apple mobile readiness probe for Xcode,
  libimobiledevice, third-party iOS tools, and USB-visible iPhone/iPad/iPod
  devices.
- `mobile_ios_list_devices`: list libimobiledevice-visible iOS devices and
  compact lockdownd info such as product type, iOS version, build, serial, and
  trust state.
- `mobile_ios_apps`: list installed iOS apps through `ideviceinstaller` and
  return compact bundle/version/display-name rows.
- `mobile_ios_syslog_tail`: capture a short `idevicesyslog` sample with an
  optional substring filter.

## Safety Boundaries

- Require a device serial when more than one device is connected.
- Default read tools to short output caps; let callers request larger snapshots.
- Return command status, stdout/stderr, duration, and the selected device.
- Keep mutation tools explicit. Installation, launch, click, and input should
  never be hidden inside read helpers.
- Keep screenshots as a fallback/proof channel, not the default decision
  source. Structured state remains the first read path.
- Do not expose arbitrary `adb shell` in the mobile bridge. `shell_exec` already
  exists for explicit raw command escape hatches.
- Projection payloads are authenticated but not encrypted. Do not project
  secrets, require the device holder's explicit consent, cap each listener at
  600 seconds, and report every authority bit as false.

## 2026-08-11 Projection Tool Addendum

The recovered Android companion and target-SDK-35 compatibility work made the
projection protocol usable, but starting it still required an operator to
coordinate a token environment variable, host process, expiry, and ADB extras.
`mobile_projection_start` closes that product-integration gap:

1. resolve one authorized ADB device;
2. generate 32 random bytes from the host OS without returning them;
3. bind `ProjectionSession` to a caller-selected private/link-local address and
   an OS-selected port;
4. use `am start -S` so an expired or active prior projection cannot absorb the
   new Intent or keep polling;
5. open the consent Activity and return `awaiting_device_consent` metadata;
6. serve the zero-authority frame from an in-process thread until expiry or MCP
   process shutdown.

The first live attempt exposed Android Activity reuse: a successful `am start`
could leave an expired Activity visible because the existing top instance did
not rerun `onCreate`. The `-S` replacement rule was added before acceptance.
The corrected MCP stdio path then replaced the old screen, required the device
holder to press **Allow and connect**, rendered the authenticated frame, and
stopped polling after **Disconnect**. `CompanionService` remained absent.

Lifecycle control was added after that first acceptance pass. Starting a new
session now stops older listeners for the same device serial. Runtime state is
kept in-process with bounded retention and exposes pull count, last-pull time,
consent observation, listener state, and stop/end state. The status phases are
`awaiting_consent`, `connected_recently`, `connected_then_idle`, `stopped`, and
`expired`; because the current polling protocol has no explicit disconnect
event, `connected_then_idle` intentionally does not claim one.

The projection frame is now revisioned inside the same short-lived session.
Updates do not reopen the Activity, extend TTL, change the token, or start a
service. The listener reports both `current_revision` and
`last_served_revision`; only equality (or a later served revision) proves that
an authenticated device pull observed the current content. One in-flight poll
may still receive the prior revision, so update itself returns
`updated_awaiting_authenticated_pull` rather than claiming delivery.

Physical-device acceptance on 2026-08-11 used serial
`3K661F0178H00000`. After the holder pressed **Allow and connect**, status
reported `connected_recently` with authenticated pulls. `mobile_projection_stop`
returned a successful ADB force-stop, status changed to `stopped`, the listener
ended, and both `pidof` and `dumpsys activity services` showed no remaining
companion process or service.

## Implementation Path

1. Added lightweight ADB helpers in `crates/bridge/src/mcp_tools.rs`. This
   matches the existing MCP tool style and avoids a premature crate split.
2. Registered the new tools as `Tier::Standard` and allowlisted them into
   `codex-essential` direct extras so Codex desktop can use them during Android
   install/debug lanes without widening to the full Standard surface.
3. Added parser helpers for:
   - `adb devices -l`
   - UI Automator `bounds="[x1,y1][x2,y2]"`
   - selector matching by `text`, `resource-id`, `content-desc`, `class`, or
     `package`
4. Added unit tests for parsing and policy exposure.
5. Verified on the current physical phone with read-only ADB calls first, then a
   safe targeted click/input only when the user intends to interact with the
   app.

No new external Rust dependency is required for the MVP. The UIAutomator XML
shape is intentionally narrow, so the first implementation uses a local
attribute scanner for `<node ...>` tags.

## Verification

- `cargo check -p ab-bridge` passed.
- `cargo build -p ab-bridge` passed.
- `cargo test -p ab-bridge mobile_` passed.
- `cargo test -p ab-bridge tool_policy_codex_essential_exposes_extras_list`
  passed.
- `rustfmt --edition 2021 --check crates/bridge/src/mcp_tools.rs` passed.
- `git diff --check` passed.
- MCP stdio smoke with `AGENT_BRIDGE_TOOLSET=codex-essential` listed all
  eight `mobile_*` tools.
- Installed wrapper smoke after replacing `~/.local/bin/agent-bridge.real`
  listed all eight `mobile_*` tools and `mobile_list_devices` returned the
  current three-device ADB set.
- A later clean release rebuild (`cargo clean -p ab-bridge &&
  cargo build --release -p ab-bridge`) fixed a stale release-artifact mismatch;
  `~/.local/bin/agent-bridge.real` now matches the clean release hash and the
  installed wrapper can call both `mobile_list_devices` and
  `mobile_current_focus` successfully.
- Android dogfood follow-up verification:
  - `cargo build -p ab-bridge` passed.
  - `cargo build --release -p ab-bridge` passed.
  - debug MCP stdio smoke listed and called `mobile_screenshot` and
    `mobile_health`.
  - installed wrapper smoke listed all 11 `mobile_*` tools in
    `codex-essential`.
  - `mobile_screenshot` saved readable PNGs at
    `/tmp/ab-mobile-screenshot-smoke.png` and
    `/tmp/ab-mobile-screenshot-installed.png`.
  - `mobile_health` returned `foreground_package=com.nexuscivilization.game`,
    `package_match=true`, `fatal_count=0`, and
    `analysis.surface_dominated=true` for the current Godot foreground app.
  - installed release hash:
    `ba964b64d84352136eeb7660299e0827f440b9df24da067d8a8b94a4901cb2f3`.
  - backup before this install:
    `/Users/pallasting/.local/bin/agent-bridge.real.bak-20260523-094522-pre-mobile-health-package-fallback`.
  - after MCP restart, live Codex `capabilities.tool_profile_extras` included
    `mobile_screenshot` and `mobile_health`; live calls to both tools succeeded
    against serial `3K661F0178H00000`.
  - final installed-wrapper smoke confirmed `mobile_health` falls back to the
    parsed foreground package for logcat summarization when `package` is omitted.

Note: `cargo fmt --check -p ab-bridge` still reports unrelated pre-existing
format differences in other package files, so it is not a clean signal for this
MVP unless the whole package formatting baseline is normalized.

## Client Tool Loading

This needs explicit attention whenever Agent-Bridge changes tool manifests.
There are three separate states that can otherwise be confused:

- the installed server binary contains and registers the tools;
- the selected `AGENT_BRIDGE_TOOLSET` / `AGENT_BRIDGE_TOOL_PROFILE` exposes
  those tools for a given client;
- the already-connected MCP client has refreshed its `tools/list` snapshot.

Current matrix from the installed wrapper on 2026-05-23:

- `codex-essential` exposes all 11 `mobile_*` tools.
- `codex-lean` exposes zero `mobile_*` tools.
- `claude-standard` exposes all 11 `mobile_*` tools.
- `gemini-lean` exposes zero `mobile_*` tools.
- `hook-lifecycle` exposes zero `mobile_*` tools.
- `all-dev` exposes all 11 `mobile_*` tools.

That matrix is intentional: mobile device control is useful for Codex desktop
and full/standard operator surfaces, but should stay out of lean Gemini and
lifecycle-hook profiles unless a specific use case appears.

Reconnect caveat: after installing a new binary, an already-attached Codex MCP
child can still report the old `tool_profile_extras` until the client respawns
the MCP server and re-reads `tools/list`. Acceptance checks should therefore
include both an installed-wrapper stdio smoke and a live-client capability
check.

`agent-bridge doctor` now reports this class of problem directly. On macOS it
uses executable/inode inspection to distinguish current `agent-bridge.real`,
stale `agent-bridge.real`, and old direct `agent-bridge` binary MCP children.
The observed cause on this host was stale MCP children, not missing registration
or profile filtering.

## Efficiency Evaluation

Measured on 2026-05-23 against physical Android serial
`3K661F0178H00000`:

| Task | Naked command | Agent-Bridge tool | Result |
| --- | ---: | ---: | --- |
| List devices | `adb devices -l`: ~0.01s, 347 bytes | `mobile_list_devices`: ~0.14s, 827 bytes | Naked command wins for raw speed; tool adds parsed fields and Android versions. |
| Current focus | `dumpsys window | grep`: ~0.11-0.17s, 162 bytes | `mobile_current_focus`: ~0.18-0.21s, 270 bytes | Similar enough; tool mainly removes command/grep friction. |
| Logcat tail | `logcat -d -t 80`: ~0.08s, 9.9KB | `mobile_logcat_tail`: ~0.13s, 10.3KB | Similar; tool is useful when filter/shape is applied. |
| UI snapshot | `uiautomator dump + cat`: ~2.58s, 13.8KB XML | `mobile_ui_snapshot`: ~3.35s, 15.8KB JSON | Current output is not efficient enough; it needs a compact projection. |

Simulated compact UI projection keeping only interactive/actionable fields
(`ordinal`, `text`, `content_desc`, `resource_id`, `class`, center point)
reduced the snapshot to 3.6KB: 73.9% smaller than raw XML and 77.2% smaller
than the current tool output.

Conclusion: Agent-Bridge mobile tools are justified for repeated/compound
debug loops, multi-device disambiguation, selector-based actions, and compact
decision summaries. They are not justified as a one-for-one replacement for
simple shell commands unless the tool adds parsing, safety, or projection.

iOS device validation on 2026-05-25 used a physical iPhone 7 Plus
(`iPhone9,2`) running iOS `15.8.7`. USB/ioreg saw the phone, then
`libimobiledevice` + `ideviceinstaller` were installed through Homebrew for the
minimal bridge path. Results:

| Task | Naked command result | Agent-Bridge value |
| --- | --- | --- |
| Device status | `idevice_id -l` + several `ideviceinfo -k ...` calls returned UDID, `iPhone9,2`, iOS `15.8.7`, build `19H411`, and `TrustedHostAttached=true`. | `mobile_ios_list_devices` folds this into one compact structured call. |
| Syslog | 4s of `idevicesyslog` returned 16,731 lines. | `mobile_ios_syslog_tail` makes this bounded and filterable so agents do not flood context. |
| Apps | `ideviceinstaller list --user` returned compact app CSV; `--xml` was too verbose for context-efficient use. | `mobile_ios_apps` extracts only bundle id, display name, and version. |

This clears the 30%+ usefulness bar for repeated iOS diagnostics: the bridge
does not make the underlying channel faster, but it removes repeated shell
composition, trust-state ambiguity, XML/plist parsing, and unbounded syslog
output.

Acceptance bar for future mobile tools:

- A naked one-line command should remain the preferred path when it is faster
  and equally clear.
- A bridge tool should reduce either tool calls, parsing burden, or consumed
  output by roughly 30%+ on a repeated workflow.
- UI tree tools must default to compact/actionable projections; raw XML/verbose
  JSON should be opt-in.
- Platform bring-up tools should start as capability/status probes before full
  install/click/input surfaces are added.

Apple mobile note: this Mac currently uses
`/Library/Developer/CommandLineTools`, and `xcrun` cannot find `simctl`,
`devicectl`, `xcdevice`, or `xctrace`. USB/ioreg sees one Apple mobile device
(`iPhone`, `SupportsIPhoneOS=true`). After installing `libimobiledevice` and
`ideviceinstaller`, the physical-device read path is available for device info,
app inventory, and syslog. Full Xcode is still required before simulator,
`devicectl`, XCUITest, WebDriverAgent, or selector/click-style iOS UI automation
should be treated as ready.

## Dogfood Follow-Up

Cross-agent dogfood on a real Godot Android playtest confirmed the bridge is
most useful when it bundles state and preserves structured fallbacks:

- `mobile_list_devices`, `mobile_launch_app`, `mobile_current_focus`, and
  coordinate `mobile_click` already reduced friction during multi-device
  testing.
- `mobile_ui_snapshot` is useful for Android chrome, dialogs, text fields, and
  overlays, but Godot itself appears mostly as a focused
  `android.view.SurfaceView`. The tool now surfaces `analysis.semantic_nodes`,
  `analysis.canvas_only`, and `analysis.surface_dominated` so agents can switch
  to screenshot or engine-side hooks without rediscovering that limitation.
- `mobile_screenshot` gives an explicit visual fallback for canvas targets.
- `mobile_health` bundles the first-pass playtest health check: focus package,
  package match, logcat fatal/error markers, and UI/canvas analysis.

## Open Follow-Ups

- Add WebView CDP attachment for debuggable WebViews.
- If full Xcode becomes available, expand Apple support in this order:
  simulator/device install and launch -> WDA/XCUITest UI snapshot -> selector
  actions. Until then, keep iOS support to `mobile_apple_status`,
  `mobile_ios_list_devices`, `mobile_ios_apps`, and `mobile_ios_syslog_tail`.
