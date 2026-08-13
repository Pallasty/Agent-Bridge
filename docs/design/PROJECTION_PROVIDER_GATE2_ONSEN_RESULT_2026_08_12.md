# Projection Provider Gate 2 - Onsen Result

**Date:** 2026-08-12  
**Status:** structured-simulation proof passed  
**Runtime admission:** not granted

## Purpose

Record the first provider-neutral structured-simulation proof selected by
`ADR-PROJECTION-PROVIDER-CONVERGENCE-2026-08-12.md`. This result anchors evidence
from the Onsen Godot host without adding an Agent-Bridge provider, MCP tool, or
runtime dependency.

## Source Anchor

| Field | Value |
| --- | --- |
| repository | `pallasting/onsen-hd` |
| branch result | merged to `main` |
| commit | `0733ded52d8414377aaddb050cc5f113e612b810` |
| engine | Godot `4.6.3-stable (official)` |
| provider id | `onsen.godot.live_semantic_world_host` |
| receipt schema | `agent_bridge.engine_execution_receipt.v0` |
| evidence class | `simulated.executed` |

## Verified Loop

The headed, loopback-only debug host executed this bounded loop against the
human-visible live root viewport:

1. enter and freeze an operating shift for deterministic evidence capture;
2. observe `checkout_counter` at semantic cell `(7,2)`;
3. move it to `(0,0)` through the existing world patch path;
4. verify changed model hashes, changed render signature, expected effect, and
   pixel-grounded visibility;
5. restore the pre-patch facility layout;
6. replace the temporary checkpoint in probe save slot 99;
7. refresh the real render and re-observe the same target;
8. verify exact before/restored model and render hashes.

Observed terminal receipt fields:

```text
verdict=verified
verified=true
probe_checkpoint_restored=true
model_restored=true
render_restored=true
external_world_effect_claimed=false
generated_visual_claimed=false
verified_to=onsen_godot_live_root_viewport
```

The model restore hash was
`eb4dbd95bfc81be81c037539956d26c836aee2923b79efb6a5bd4c61e5fa3335`.
The render restore hash was
`d2a63b8888f47ffecc9a3a68134893bca298b074803f29430ef40a457033221b`.

## Negative Evidence

- A target without rendered nodes returned `not_verified`; model restoration
  alone did not produce a verified receipt.
- Failed receipts keep `truth_boundary.verified_to=null`.
- Read-only world queries emit no execution receipt.
- Rollback is admitted only for layout-local `move`, `rotate`, and `flip`.
  `remove` and `place` fail before mutation because the bounded snapshot does
  not cover progression or economy side effects.

## Verification Commands

The Onsen branch passed:

```text
godot --headless --path game/client --script res://scripts/smoke_lswr_engine_execution_receipt_v0.gd
godot --headless --path game/client --check-only --script res://scripts/autoload/live_semantic_world_host.gd
godot --headless --path game/client --script res://scripts/smoke_layout_move_v0.gd
godot --headless --path game/client --script res://scripts/smoke_layout_rotate_remove_v0.gd
git diff --check
```

The headed proof used `ONSEN_LSWR_HOST=1`, a loopback TCP request, and the
existing default-off debug host. The process was terminated after capture.

## Boundary Verdict

`GATE2_STRUCTURED_SIMULATION_PROOF_VERIFIED_PROVIDER_NOT_REGISTERED`

This establishes the `simulated.executed` provider contract on one existing
engine host. It does not establish Agent-Bridge provider registration, general
Godot adapter portability, ABot integration, UE5 integration, or real-world
effect authority.

## Next Gate

Gate 3 is contract extraction on the Agent-Bridge side: represent the request
and receipt types in `ab-world-core`, map the existing LSWR envelope without
adding a new MCP tool family, and keep all provider invocation default-off.
