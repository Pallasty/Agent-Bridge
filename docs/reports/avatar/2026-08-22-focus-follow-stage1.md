# Xiao Shu focus-follow stage 1

Date: 2026-08-22

## Outcome

Stage 1 adds a read-only Sway focus-follow planner. It proposes where Xiao Shu
could dock near the currently focused non-Avatar window and describes a
bounded turn, walk, and arrival sequence. It does not execute the plan.

The behavior is intentionally **attention-following, not pointer-following**.
The planner never reads pointer coordinates, moves the pointer, changes
keyboard focus, emits input, or controls another application.

## Safety and ownership contract

- Default enabled: `false`
- Movement authorized: `false`
- Dispatch payload: `null`
- Maximum path points: 32
- Focus on Xiao Shu herself: fail closed
- Missing Avatar or usable target: fail closed
- Runtime actuator: absent

The command is:

```bash
agent-bridge avatar focus-follow-plan --json
```

## Motion vocabulary and asset status

The action registry reserves these v3 motions:

- `turn_left`, `turn_right`
- `walk_left`, `walk_right`
- `arrive_settle`
- `wave`

The concept contact sheet is
`crates/bridge/assets/xiao-shu-prototypes/xiao-shu-v3-ai-focus-follow-actions-v1-contact.png`.
It was generated from the existing Xiao Shu v3 character sheet to explore
turning, walking, arriving, and waving poses. Both generation attempts failed
the required transparent-alpha check, so this RGB contact sheet is explicitly
concept-only and is not a renderer asset.

## Verification

- Pure planner integration tests cover bounded planning, missing-Avatar
  failure, and refusing to follow itself.
- `cargo check -p ab-bridge --bin agent-bridge` passes.
- Live dry-run status: `planned`, proposed left docking, 11 path points.
- Avatar rectangle before and after: `(1367, 733, 90, 130)`; unchanged.
- Live output retained `dispatch=null`, `movement_authorized=false`,
  `moves_pointer=false`, and `changes_focus=false`.

## Next gate

Do not add movement until all of the following are separately reviewed:

1. Produce a transparent, identity-consistent production atlas.
2. Bind the atlas to a renderer-only action state machine.
3. Add explicit, default-off owner authorization for each movement request.
4. Keep pointer following and autonomous desktop control outside the design.
5. Prove cancel, cooldown, edge clamp, and no-focus-steal behavior in dry-runs.
