# Xiao Shu focus-follow interaction acceptance

Date: 2026-08-24

## Result

The owner accepted the first complete prompt-to-arrival interaction on the
live Sway desktop.

- The Avatar-anchored prompt was fully visible and its v2.1 fade transition
  was described as smooth.
- The explicitly confirmed traversal moved Xiao Shu 473px in 10 bounded
  steps toward focused Sway node 13.
- Turn-left, walk-left, arrival nod, wave, and return to idle were all visible.
- The final docking location was accepted.
- Pointer position, keyboard focus, and desktop input were unchanged.

## State-continuity decision

A completed traversal now atomically records
`$XDG_RUNTIME_DIR/ab-focus-follow-ack.json`. Recommendation and prompt commands
consume this receipt by default, while an explicit target argument retains
override precedence. Only a current-schema receipt with `status=completed` is
trusted; cancelled, failed, malformed, and older-schema receipts fail closed.

This turns the previous caller-managed `last_target_node_id` input into a
usable local interaction memory and prevents repeated offers for the same
acknowledged focus target.

## Deferred polish

The owner observed that movement was functional and complete but that easing,
stride length, and animation cadence could become smoother. This is recorded
as a later animation-polish task, not a blocker for the interaction contract.

## Next bounded stage

Verify on the production binary that:

1. a completed traversal writes the acknowledgement receipt;
2. the same target produces `stay / target_unchanged` without an explicit
   `--last-target-node-id`;
3. a newly focused distant target can still produce a fresh recommendation.
