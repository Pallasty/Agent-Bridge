# Semantic System Bus Cross-Platform Mapping

**Status:** SSB-7 mapping memo
**Date:** 2026-06-07
**Parent roadmap:** [Semantic System Bus Roadmap](SEMANTIC_SYSTEM_BUS_ROADMAP_2026_06_07.md)

## 0. Purpose

SSB-5 and SSB-6 prove the Linux desktop read/verify loop can be normalized at
runtime:

```text
desktop_snapshot -> agent_bridge.semantic_bus.desktop_snapshot.v0
desktop_verify   -> agent_bridge.semantic_bus.desktop_verify.v0
```

SSB-7 pins how macOS Accessibility (AX) and Windows UI Automation (UIA) should
map into the same vocabulary before any runtime adapters are added.

The goal is not platform parity by copy-paste. The goal is a stable semantic bus
contract:

```text
platform-specific tree -> Semantic Object -> Affordance -> Event -> Verification
```

Linux remains the reference substrate, but the schema must not become a
Linux-only schema.

## 1. Non-Goals

This slice does not:

- add macOS or Windows runtime adapter code;
- expose new host mutation;
- add new MCP tools;
- change `desktop_snapshot` or `desktop_verify` behavior;
- claim that screenshots/OCR are unnecessary;
- require that every platform expose identical isolation primitives.

## 2. Cross-Platform Invariants

Every desktop adapter should preserve these invariants.

### 2.1 One Semantic Vocabulary

Adapters may carry platform-specific raw payloads, but the normalized output
must use the same SSB vocabulary:

```text
agent_bridge.semantic_bus.object.v0
agent_bridge.semantic_bus.desktop_snapshot.v0
agent_bridge.semantic_bus.desktop_verify.v0
agent_bridge.semantic_bus.action_result.v0
```

Platform-specific details belong under:

```text
source_adapter
state.platform
provenance
raw_snapshot / raw_verify
```

They should not create parallel object schemas such as `macos_ax_object.v0` or
`windows_uia_object.v0`.

### 2.2 Stable Object IDs

Object IDs must be stable enough for one observe/act/verify loop. They do not
need to survive application restart unless the source channel provides stable
identity.

Recommended form:

```text
desktop:<platform>:session:<session-id>
desktop:<platform>:window:<window-stable-id>
desktop:<platform>:accessible:<pid-or-process-id>:<path-or-runtime-hash>
```

Rules:

- prefer platform IDs over labels;
- include process identity when object identity is only local to a process;
- use labels only as fallback material;
- hash long path/runtime identifiers before exposing them to the LLM;
- keep raw platform identifiers available in `state.platform` when safe.

### 2.3 Read-Only Snapshot First

The first adapter on every platform should be a read-only snapshot normalizer:

```text
session/window/accessibility tree -> semantic_objects + affordances
```

Actions should remain metadata until the snapshot and verify paths have stable
objects and verifier semantics.

### 2.4 Verify Before Mutate

Before adding any mutating adapter, the platform needs a read-only verifier:

```text
same selector -> poll/read platform tree -> verdict + recover
```

The recover vocabulary stays the same:

```text
proceed | retry | replan | escalate
```

### 2.5 Pixels Are Fallback And Contradiction Evidence

Pixels/OCR are still useful, but the fallback order should be:

```text
platform tree -> platform window/process state -> screenshot/OCR
```

Use screenshots for:

- controls hidden from AX/UIA;
- canvas/game/private rendering surfaces;
- visual acceptance evidence;
- contradiction checks when semantic state and rendered UI disagree.

Do not treat OCR coordinates as semantic verification. Coordinate actions
derived from pixels remain high-risk and gated.

## 3. Adapter Family Names

Use these `source_adapter` prefixes.

| Platform | Prefix | Meaning |
|---|---|---|
| Linux | `linux.sway.session` | compositor/session state |
| Linux | `linux.sway.tree` | window tree |
| Linux | `linux.atspi` | accessibility tree |
| Linux | `linux.desktop_verify` | read-only postcondition verifier |
| macOS | `macos.workspace.session` | running apps/frontmost app/session state |
| macOS | `macos.cgwindow` | window inventory and geometry |
| macOS | `macos.ax` | AXUIElement accessibility tree |
| macOS | `macos.ax.verify` | read-only AX postcondition verifier |
| macOS | `macos.vision.ocr` | screenshot/OCR fallback |
| Windows | `windows.session` | desktop/session state |
| Windows | `windows.hwnd` | Win32 HWND/window inventory |
| Windows | `windows.uia` | UI Automation tree |
| Windows | `windows.uia.verify` | read-only UIA postcondition verifier |
| Windows | `windows.vision.ocr` | screenshot/OCR fallback |

## 4. Canonical Object Families

The same object families should be emitted on all desktop platforms.

### 4.1 Session

```text
object_type = desktop.session
```

State fields:

```text
platform
desktop_session
frontmost_app / focused_app
window_count
accessibility_available
screen_count
permission_state
```

### 4.2 Window

```text
object_type = desktop.window
```

State fields:

```text
title
app_id / bundle_id / exe
pid
window_id / hwnd
focused
visible / offscreen
minimized
rect
screen / output / monitor
z_order
```

Relations:

```text
member_of -> desktop.session
owns / contains -> desktop.accessible.*
```

### 4.3 Accessible Element

```text
object_type = desktop.accessible.<role>
```

State fields:

```text
role / control_type
subrole / localized_control_type
name / title / description
identifier / automation_id
value
enabled
focused
selected
expanded
checked
visible / offscreen
rect
pid
platform
```

Relations:

```text
member_of -> desktop.session
contained_by -> desktop.window
parent_of / child_of -> desktop.accessible.*
```

### 4.4 Verify Target

```text
object_type = desktop.verify.target.accessible
object_type = desktop.verify.target.window
```

This is the cross-platform form introduced by SSB-6. It captures a
postcondition selector and observed evidence, not a durable UI element.

## 5. macOS AX Mapping

### 5.1 Channels

Use a layered read path:

```text
NSWorkspace / running apps
CGWindowList / window geometry
AXUIElement tree
screenshot/OCR fallback
```

Recommended adapter contracts:

| SSB surface | macOS source | Notes |
|---|---|---|
| session | NSWorkspace + system AX object | frontmost app, running apps, permission state |
| window | CGWindowList + AX window | geometry, title, owner pid/name, focus |
| accessible | AXUIElement attributes | role, subrole, title, identifier, value, states |
| event | AXObserver notifications | focus/window/value changes when available |
| verify | repeated AX reads + CGWindowList | poll like Linux `desktop_verify` |
| fallback | screenshot/OCR | canvas/private/non-accessible controls |

### 5.2 AX Attribute Mapping

Use these AX attributes as source material when available.

| AX source | SSB field |
|---|---|
| `kAXRoleAttribute` | `state.role`, `object_type` suffix |
| `kAXSubroleAttribute` | `state.subrole` |
| `kAXRoleDescriptionAttribute` | `state.role_description` |
| `kAXTitleAttribute` | `label`, `state.title` |
| `kAXDescriptionAttribute` | `state.description` |
| `kAXIdentifierAttribute` | `state.identifier`, object-id candidate |
| `kAXValueAttribute` | `state.value` |
| `kAXEnabledAttribute` | `state.enabled` |
| `kAXFocusedAttribute` | `state.focused` |
| `kAXSelectedAttribute` | `state.selected` |
| `kAXPositionAttribute` + `kAXSizeAttribute` | `state.rect` |
| `kAXParentAttribute` / `kAXChildrenAttribute` | relations |
| `kAXWindowAttribute` | relation to `desktop.window` |
| `kAXWindowsAttribute` | app window list |
| `kAXMainWindowAttribute` | main window state |
| `kAXFocusedWindowAttribute` | focused window state |
| `kAXFocusedUIElementAttribute` | focused accessible state |

### 5.3 macOS Object IDs

Suggested IDs:

```text
desktop:macos:session:<boot-or-login-session-hash>
desktop:macos:window:cg:<window-number>
desktop:macos:window:ax:<pid>:<window-path-hash>
desktop:macos:accessible:<pid>:<ax-identifier-or-path-hash>
```

Priority:

1. stable AX identifier if present;
2. CGWindow number for windows;
3. AX path hash under pid and window;
4. role/title/index hash as fallback.

Do not rely on localized titles alone.

### 5.4 macOS Affordances

AX actions map to SSB affordances:

| AX capability | SSB action_type | Gate |
|---|---|---|
| read attributes | `desktop.verify` | no gate |
| `AXPress` / action list invoke | `desktop.invoke` | gate required |
| settable value/text attributes | `desktop.set_value` | gate required |
| focus/set focused window | `desktop.focus` | gate required |
| screen coordinate fallback | `desktop.action` | high-risk gate |

The first macOS implementation should emit mutating affordances as metadata only
unless a separate host-confirm path is explicitly designed.

### 5.5 macOS Verification

The verifier should poll:

```text
AX element existence
AX attribute state
focused AX element/window
CGWindow presence/geometry
```

Source verdict mapping:

| Platform result | SSB verdict | recover |
|---|---|---|
| expected AX/CG state observed | `verified` | `proceed` |
| selector absent or state mismatch | `not_verified` | `retry` or `replan` |
| TCC denied / AX unavailable / target app unresponsive | `blocked` or `error` | `escalate` |

Use `not_verified` for ordinary misses. Use `blocked` only when the system
permission or policy prevents observing or acting safely.

### 5.6 macOS Known Gaps

- TCC Accessibility permission is global and user-mediated.
- AX trees vary by toolkit and app; Electron and custom-rendered apps may expose
  partial trees.
- AX object references are not durable object IDs.
- There is no simple nested-desktop isolation equivalent to Linux nested sway.
- WindowServer/CGWindow geometry can diverge from AX hierarchy.
- Localized titles and labels are weak identity.

## 6. Windows UIA Mapping

### 6.1 Channels

Use a layered read path:

```text
desktop/session inventory
Win32 HWND window enumeration
UI Automation tree
screenshot/OCR fallback
```

Recommended adapter contracts:

| SSB surface | Windows source | Notes |
|---|---|---|
| session | desktop/session + foreground window | desktop and focus state |
| window | HWND / process / monitor data | title, pid, rect, visibility |
| accessible | UIA AutomationElement | properties, control type, patterns |
| event | UIA events | focus/property/structure/window changes |
| verify | repeated UIA/HWND reads | poll like Linux `desktop_verify` |
| fallback | screenshot/OCR | canvas/private/non-accessible controls |

### 6.2 UIA Property Mapping

Use these UIA properties as source material when available.

| UIA source | SSB field |
|---|---|
| `ControlType` | `state.control_type`, `object_type` suffix |
| `Name` | `label`, `state.name` |
| `AutomationId` | `state.automation_id`, object-id candidate |
| `RuntimeId` | object-id candidate |
| `ClassName` | `state.class_name` |
| `FrameworkId` | `state.framework_id` |
| `BoundingRectangle` | `state.rect` |
| `ProcessId` | `state.pid` |
| `NativeWindowHandle` | relation to `desktop.window` |
| `IsEnabled` | `state.enabled` |
| `HasKeyboardFocus` | `state.focused` |
| `IsKeyboardFocusable` | `state.focusable` |
| `IsOffscreen` | `state.offscreen` |
| selection/toggle/expand properties | `state.selected`, `checked`, `expanded` |

### 6.3 Windows Object IDs

Suggested IDs:

```text
desktop:windows:session:<session-id>
desktop:windows:window:hwnd:<hwnd>
desktop:windows:accessible:<pid>:runtime:<runtime-id-hash>
desktop:windows:accessible:<pid>:automation:<automation-id-hash>
```

Priority:

1. `RuntimeId` hash when available;
2. `NativeWindowHandle` for window objects;
3. `AutomationId` plus process and ancestry;
4. control type/name/index path as fallback.

`AutomationId` is useful but not globally unique. Pair it with process/window
context and ancestry.

### 6.4 Windows Affordances

UIA patterns map to SSB affordances:

| UIA pattern | SSB action_type | Gate |
|---|---|---|
| read properties | `desktop.verify` | no gate |
| `InvokePattern` | `desktop.invoke` | gate required |
| `SelectionItemPattern` | `desktop.select` | gate required |
| `TogglePattern` | `desktop.toggle` | gate required |
| `ValuePattern` | `desktop.set_value` | gate required |
| `RangeValuePattern` | `desktop.set_range` | gate required |
| `ExpandCollapsePattern` | `desktop.expand` / `desktop.collapse` | gate required |
| `ScrollPattern` | `desktop.scroll` | gate required |
| coordinate fallback | `desktop.action` | high-risk gate |

The first Windows implementation should emit these as affordance metadata only.
Actual mutation should wait for explicit host-confirm and audit semantics.

### 6.5 Windows Verification

The verifier should poll:

```text
UIA element existence
UIA property state
foreground/focused element
HWND window presence/geometry
```

Source verdict mapping:

| Platform result | SSB verdict | recover |
|---|---|---|
| expected UIA/HWND state observed | `verified` | `proceed` |
| selector absent or state mismatch | `not_verified` | `retry` or `replan` |
| integrity boundary / desktop locked / UIA unavailable | `blocked` or `error` | `escalate` |

### 6.6 Windows Known Gaps

- UIA availability varies by framework and app.
- UAC, integrity levels, secure desktop, and session boundaries can block access.
- `AutomationId` is not globally unique.
- Virtualized lists may not materialize offscreen children.
- Canvas/game/private rendering may expose only a shell node.
- RDP and multi-session contexts can change focus/window semantics.

## 7. Role And Control-Type Normalization

Normalize platform-specific roles into a small SSB role vocabulary.

| SSB suffix | Linux AT-SPI examples | macOS AX examples | Windows UIA examples |
|---|---|---|---|
| `button` | `push button`, `button` | `AXButton` | `Button` |
| `text` | `text`, `label` | `AXStaticText` | `Text` |
| `input` | `entry`, `text` | `AXTextField`, `AXTextArea` | `Edit` |
| `checkbox` | `check box` | `AXCheckBox` | `CheckBox` |
| `radio` | `radio button` | `AXRadioButton` | `RadioButton` |
| `menu` | `menu`, `menu item` | `AXMenu`, `AXMenuItem` | `Menu`, `MenuItem` |
| `list` | `list`, `list item` | `AXList`, `AXRow` | `List`, `ListItem` |
| `table` | `table`, `row`, `cell` | `AXTable`, `AXRow`, `AXCell` | `DataGrid`, `Table`, `DataItem` |
| `slider` | `slider` | `AXSlider` | `Slider` |
| `window` | application/window | `AXWindow` | `Window` |
| `web` | web/document roles | `AXWebArea` | `Document`, browser-specific controls |
| `custom` | toolkit-specific | app-specific AX role | custom control type |

Keep the raw role/control type in `state.platform.raw_role`.

## 8. Selector Contract

Selectors should be adapter-neutral where possible:

```json
{
  "platform": "macos|windows|linux",
  "object_id": "...",
  "app": "...",
  "pid": 1234,
  "role": "button",
  "name": "OK",
  "state": "enabled",
  "window": {
    "title": "...",
    "id": "..."
  }
}
```

Adapters may add platform-specific selector fields:

```text
macos.bundle_id
macos.ax_identifier
macos.ax_path
windows.automation_id
windows.runtime_id_hash
windows.hwnd
```

The verifier should accept the same selector emitted by the snapshot affordance.

## 9. Event Mapping

Map platform notifications into SSB events without requiring every adapter to be
event-driven on day one.

| Platform source | SSB event_type |
|---|---|
| snapshot poll found object | `desktop.snapshot.observed` |
| AX/UIA focus changed | `desktop.focus.changed` |
| AX/UIA value changed | `desktop.value.changed` |
| AX/UIA structure changed | `desktop.structure.changed` |
| window created/destroyed | `desktop.window.changed` |
| verifier completed | `desktop.verify.completed` |
| OCR fallback used | `desktop.vision.fallback_used` |

Polling adapters can synthesize events from diffs. Observer-backed adapters can
attach platform notification names under `payload_json.platform_event`.

## 10. Permission And Gate Posture

### macOS

Read-only AX snapshot still depends on Accessibility permission. If permission
is missing:

```text
verification.verdict = blocked
verification.reason = accessibility_permission_missing
verification.recover = escalate
```

Mutating AX actions, value writes, focus changes, and coordinate actions require
a human gate and audit trail.

### Windows

Read-only UIA snapshot may be blocked by integrity/session boundaries. If the
adapter cannot observe the target:

```text
verification.verdict = blocked
verification.reason = ui_access_denied | integrity_boundary | secure_desktop
verification.recover = escalate
```

Mutating UIA patterns and coordinate actions require a human gate and audit
trail.

## 11. First Implementation Order

When implementation begins, use this order.

### macOS

1. `desktop_snapshot`-style read-only adapter:
   `NSWorkspace + CGWindowList + AXUIElement`.
2. `semantic_bus=true` wrapper emitting
   `agent_bridge.semantic_bus.desktop_snapshot.v0`.
3. `desktop_verify`-style read-only adapter polling AX/CGWindow state.
4. Optional AXObserver event stream.
5. Gated `desktop.invoke` metadata only.

### Windows

1. `desktop_snapshot`-style read-only adapter:
   `HWND + UIA AutomationElement`.
2. `semantic_bus=true` wrapper emitting
   `agent_bridge.semantic_bus.desktop_snapshot.v0`.
3. `desktop_verify`-style read-only adapter polling UIA/HWND state.
4. Optional UIA event stream.
5. Gated pattern affordance metadata only.

Do not start with coordinate input.

## 12. Acceptance Fixtures

Add fixture-backed conformance before live adapters:

```text
crates/bridge/fixtures/semantic_bus/macos_ax_snapshot_state.json
crates/bridge/fixtures/semantic_bus/macos_ax_verify_postcondition.json
crates/bridge/fixtures/semantic_bus/windows_uia_snapshot_state.json
crates/bridge/fixtures/semantic_bus/windows_uia_verify_postcondition.json
```

Each fixture should prove:

- `source_adapter` starts with `macos.` or `windows.`;
- `read_only=true`;
- `broad_host_mutation=false`;
- screenshot/OCR is fallback, not primary state;
- verifier emits `recover` in the shared vocabulary;
- mutating affordances, if present, set `requires_gate=true`.

## 13. Implementation Decision

The SSB schema is adapter-neutral. macOS AX and Windows UIA should become
coverage adapters into the same contract, not forks of the contract.

Practical consequence:

```text
desktop_snapshot(semantic_bus=true)
desktop_verify(semantic_bus=true)
```

should look structurally the same to an AI caller on Linux, macOS, and Windows.
Only `source_adapter`, `state.platform`, and optional raw payloads should reveal
which OS produced the observation.

## 14. References

Local SDK references used while drafting this memo:

- `/Library/Developer/CommandLineTools/SDKs/MacOSX.sdk/System/Library/Frameworks/ApplicationServices.framework/Versions/A/Frameworks/HIServices.framework/Versions/A/Headers/AXAttributeConstants.h`
- `/Library/Developer/CommandLineTools/SDKs/MacOSX.sdk/System/Library/Frameworks/ApplicationServices.framework/Versions/A/Frameworks/HIServices.framework/Versions/A/Headers/AXUIElement.h`
- `/Library/Developer/CommandLineTools/SDKs/MacOSX.sdk/System/Library/Frameworks/ApplicationServices.framework/Versions/A/Frameworks/HIServices.framework/Versions/A/Headers/AXNotificationConstants.h`

External references checked for terminology:

- Apple Developer Documentation:
  [Accessibility attributes](https://developer.apple.com/documentation/applicationservices/carbon_accessibility/attributes?language=objc)
- Microsoft Learn:
  [Using UI Automation for Automated Testing](https://learn.microsoft.com/en-us/dotnet/framework/ui-automation/using-ui-automation-for-automated-testing)
