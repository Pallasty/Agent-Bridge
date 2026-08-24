# Xiao Shu focus-follow stage 10: recommendation observation

Date: 2026-08-23

## Decision

The read-only focus-change recommendation surface is accepted for use as the
input to a future passive presentation layer. It remains default-off and has no
movement, pointer, focus, input, or state-write authority.

## Contract

`agent-bridge avatar focus-follow-recommend` compares the current focused Sway
node with an optional last acknowledged target and returns:

- `stay` when the target is unchanged or movement is below the configured
  threshold;
- `recommend_move` when a new target is far enough away;
- `suppress` when the underlying focus-follow plan is not actionable.

The command never dispatches movement. A recommendation still requires the
existing explicit `focus-follow-action --execute --confirm --reason ...` gate.

## Live observations

1. Stable focus: 15 samples over 30 seconds on node 14 all returned
   `stay / target_unchanged`.
2. Near focus change: node 14 to node 13 changed the target, but the required
   movement was only 19px. The first sample returned
   `stay / movement_below_threshold`; the next nine samples returned
   `stay / target_unchanged`.
3. Far focus change: node 13 to node 272 required 240px. The first sample
   returned `recommend_move / new_focus_target_outside_threshold`; after the
   observer advanced its in-memory last-target value, the next fourteen samples
   returned `stay / target_unchanged`.

Across all observations, `writes_state=false`, `moves_avatar=false`,
`moves_pointer=false`, and `changes_focus=false` remained true. No Avatar
movement or presentation was emitted.

## Next bounded stage

Add a passive, non-voice presentation preview for `recommend_move`, preferably
a short Avatar-adjacent bubble. The preview must be dismissible, rate-limited,
and non-executing. It must not turn a recommendation into movement or weaken
the existing per-call confirmation gate.
