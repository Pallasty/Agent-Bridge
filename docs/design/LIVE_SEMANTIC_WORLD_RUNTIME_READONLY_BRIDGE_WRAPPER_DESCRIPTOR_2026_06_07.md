# Live Semantic World Runtime Read-Only Bridge Wrapper Descriptor

Status: P31 draft, descriptor-only bridge continuation.

## Purpose

P31 defines the future wrapper boundary for the P30 display model without registering an MCP tool.

The descriptor is a deterministic JSON contract that tells a UI, agent surface, or later MCP wrapper what it may expose and what it must not do. It closes the gap between the display model and a future profile-gated wrapper while keeping this slice out of runtime launch, GUI capture, filesystem path reads, and mutation surfaces.

## Schema

The descriptor schema is `agent_bridge.lswr.readonly_bridge_wrapper_descriptor.v0`.

Top-level fields:

- `schema`
- `wrapper_name`
- `state`
- `purpose`
- `schema_chain`
- `profile_gate`
- `input_contract`
- `output_contract`
- `safety_contract`
- `acceptance_contract`
- `next_steps`

## Contract

`schema_chain` ties the wrapper path to the existing accepted chain:

- input packet: `agent_bridge.lswr.readonly_bridge_report_packet.v0`
- acceptance matrix: `agent_bridge.lswr.readonly_bridge_acceptance_matrix.v0`
- output display model: `agent_bridge.lswr.readonly_bridge_display_model.v0`

`profile_gate` keeps the current state explicit:

- current exposure is `not_registered`
- no MCP registry change is made in P31
- Codex essential remains `not_exposed`
- any future exposure requires a separate registry/profile change

`input_contract` requires an explicit report packet payload. It does not accept host paths, live runtime reads, or GUI capture.

`output_contract` allows the P30 display model, including report Markdown and display readback rows, but no mutating handles.

## Safety

The descriptor is read-only:

- `mutation_surface` is `none`
- allowed capabilities are snapshot/query/display/report Markdown
- disallowed capabilities include patch, action, invoke, runtime launch, GUI capture, host path read, filesystem write, and memory graph write

## Acceptance Boundary

The wrapper may expose a display model only when the P29/P30 chain reports:

- overall verdict `accepted`
- display status `Ready for read-only display`
- display status tone `success`
- display safety `wrapper_ready=true`
- all gates pass, including the review-sensitive `detailed_readback` gate

This preserves the P30 behavior where counts-only packets remain `Needs review` and are not wrapper-ready.

## Usage

The example prints the descriptor:

```sh
cargo run -p ab-bridge --example lswr_readonly_bridge_wrapper_descriptor
```

P31 intentionally does not touch `mcp_tools.rs`. The next exposure step should be opened as a separate slice so the profile gate, tool registry entry, and live MCP behavior can be reviewed independently.
