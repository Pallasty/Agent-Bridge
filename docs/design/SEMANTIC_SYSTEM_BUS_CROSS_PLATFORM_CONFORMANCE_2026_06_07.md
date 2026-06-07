# Semantic System Bus Cross-Platform Adapter Conformance

**Status:** SSB-8 fixture-backed conformance
**Date:** 2026-06-07
**Parent roadmap:** [Semantic System Bus Roadmap](SEMANTIC_SYSTEM_BUS_ROADMAP_2026_06_07.md)
**Mapping memo:** [Cross-Platform Mapping](SEMANTIC_SYSTEM_BUS_CROSS_PLATFORM_MAPPING_2026_06_07.md)

## 0. Purpose

SSB-7 defined how macOS Accessibility (AX) and Windows UI Automation (UIA)
should map into the same Semantic System Bus vocabulary as Linux.

SSB-8 turns that design into fixture-backed contract tests. It still does not
add runtime adapters, new MCP tools, or host mutation paths.

The goal is to pin the adapter shape before implementation:

```text
macOS AX fixture     -> SSB fixture contract
Windows UIA fixture  -> SSB fixture contract
validator test       -> shared conformance rules
```

## 1. Fixtures

New fixtures:

```text
crates/bridge/fixtures/semantic_bus/macos_ax_snapshot_state.json
crates/bridge/fixtures/semantic_bus/macos_ax_verify_postcondition.json
crates/bridge/fixtures/semantic_bus/windows_uia_snapshot_state.json
crates/bridge/fixtures/semantic_bus/windows_uia_verify_postcondition.json
```

All four use:

```text
schema = agent_bridge.semantic_bus.fixture.v0
adapter_contract.schema = agent_bridge.semantic_bus.adapter_conformance.v0
```

## 2. Adapter Families

SSB-8 adds two conformance families:

```text
macos_desktop
windows_desktop
```

Accepted tools for these fixtures:

```text
desktop_snapshot
desktop_verify
```

Runtime adapter tools do not exist yet. These names describe the target semantic
surface, not a shipped macOS/Windows MCP tool.

## 3. macOS AX Fixtures

### macos_ax_snapshot_state

Represents a read-only snapshot of a macOS AX button:

```text
source_adapter = macos.ax
object_type = desktop.accessible.button
channels = workspace_session + cgwindow + ax
fallback_order = workspace_session -> cgwindow -> ax -> vision_grounding_ocr
```

The object keeps platform details under `state.platform`, including AX
identifier, bundle id, and CGWindow number. It emits:

- ungated `desktop.verify` affordance;
- gated `desktop.invoke` affordance metadata for `AXPress`;
- `desktop.snapshot.observed` event.

### macos_ax_verify_postcondition

Represents a read-only AX postcondition check:

```text
source_adapter = macos.ax.verify
object_type = desktop.verify.target.accessible
method = macos.ax.verify.polling
recover = proceed
```

It proves the verify-target object family from SSB-6 is platform-neutral.

## 4. Windows UIA Fixtures

### windows_uia_snapshot_state

Represents a read-only UIA button snapshot:

```text
source_adapter = windows.uia
object_type = desktop.accessible.button
channels = session + hwnd + uia
fallback_order = session -> hwnd -> uia -> vision_grounding_ocr
```

The object keeps platform details under `state.platform`, including
AutomationId, RuntimeId hash, HWND, and FrameworkId. It emits:

- ungated `desktop.verify` affordance;
- gated `desktop.invoke` affordance metadata for `InvokePattern`;
- `desktop.snapshot.observed` event.

### windows_uia_verify_postcondition

Represents a read-only UIA postcondition check:

```text
source_adapter = windows.uia.verify
object_type = desktop.verify.target.accessible
method = windows.uia.verify.polling
recover = proceed
```

It keeps Windows-specific identity under `state.platform` while preserving the
same SSB verifier vocabulary.

## 5. Validator Extension

The existing fixture minimum-contract test now includes the four new fixtures.

New focused test:

```text
cross_platform_adapter_conformance_fixtures_pin_mapping_contract
```

The test enforces:

- adapter family is `macos_desktop` or `windows_desktop`;
- accepted tool is `desktop_snapshot` or `desktop_verify`;
- `read_only=true`;
- `broad_host_mutation=false`;
- `mutation_surface=none`;
- `source_adapter` starts with `macos.` or `windows.`;
- `state.platform` exists for platform-specific identifiers;
- fallback order includes `vision_grounding_ocr`;
- verify fixtures emit `desktop.verify.target.*` objects;
- recover is one of `proceed`, `retry`, `replan`, `escalate`;
- mutating or coordinate affordances require a gate;
- read-only `desktop.verify` affordances stay ungated.

## 6. Boundaries

This slice intentionally does not:

- call macOS AX APIs;
- call Windows UIA APIs;
- add any new runtime scripts;
- add any new MCP tools;
- expose host mutation;
- assert that live macOS/Windows adapters already exist.

## 7. Next Slice

The next useful implementation step is one of:

1. a read-only macOS feasibility probe that reports AX permission and a bounded
   frontmost-app/window snapshot; or
2. a read-only adapter-contract fixture report that makes Palace/daemon-http
   show adapter conformance status.

The macOS probe is the stronger implementation proof if the next lane remains
local to this Mac. The Palace/daemon report is better if the next lane stays
purely product-visible and cross-platform.
