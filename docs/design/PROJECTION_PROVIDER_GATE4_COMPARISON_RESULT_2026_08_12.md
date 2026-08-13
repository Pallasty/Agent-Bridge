# Projection Provider Gate 4: Read-Only Comparison Contract

Date: 2026-08-12

## Scope

Gate 4 completes the provider-neutral comparison layer without invoking the
local ABot-World model. The model snapshot is present at:

```text
/Users/pallasting/.cache/modelscope/models/amap_cvlab--ABot-World-0-5B-LF
```

Its presence is asset availability only. No model load, inference, dependency
installation, MCP registration, or runtime admission occurred.

## Contract additions

`ab-world-core` now contains:

- `ProjectionRequestEnvelope.projection_class` and the ADR-compatible
  `source_world_ref` field, with a compatibility alias for the earlier
  `source_world_id` spelling.
- `SimulatedWorldRollout` for ABot-World-style generated hypotheses. It is
  fixed to `simulated.generated`, requires artifact hashes, and cannot claim
  an external effect or `verified_to` boundary.
- `ProjectionComparisonReceipt` for comparing immutable receipt references.
  It requires at least two aligned inputs and cannot modify or upgrade either
  input's evidence class.
- Stable wire values using dotted evidence classes:
  `simulated.generated`, `simulated.executed`, and `observed.real`.

The existing Onsen `EngineExecutionReceipt` remains the structured simulation
record at `simulated.executed`; it is not conflated with a generated rollout.

## Verification

```text
cargo test -p ab-world-core --lib
41 passed; 0 failed

cargo check -p ab-world-core --all-targets
passed

git diff --check
passed
```

## Admission boundary

This remains a read-only contract/fixture gate:

- no ABot-World inference;
- no new MCP tool;
- no provider registry entry;
- no generated output treated as world state;
- no runtime deployment.

Verdict: `GATE4_READ_ONLY_PROVIDER_COMPARISON_CONTRACT_VERIFIED_DEFAULT_OFF`.

The next gate, if later authorized, is an offline ABot-World artifact probe
that records model/runtime versions, input lineage, output hashes, and timing
without claiming engine execution or real-world observation.
