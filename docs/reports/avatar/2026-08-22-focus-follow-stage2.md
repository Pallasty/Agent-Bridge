# Xiao Shu focus-follow stage 2

Date: 2026-08-22

## Outcome

Stage 2 adds a default-off, foreground focus-follow action with explicit
per-request authorization and a renderer motion-override channel. Xiao Shu
still does not follow the pointer. She can move only when the owner explicitly
requests attention near the currently focused Sway window.

## Execution contract

All three execution inputs are mandatory:

```text
--execute --confirm --reason <non-empty operator reason>
```

The action:

- targets only the exact `agent-bridge-avatar` app id;
- defaults to dry-run;
- limits the path to 32 points, 48 pixels per step, and 900 pixels total;
- revalidates the focused window identity before every step;
- cancels on focus change, `Ctrl-C`, or an existing `--cancel-file`;
- never reads or moves the pointer, changes keyboard focus, or emits keyboard
  input.

## Visual state machine

The native renderer now checks a user-private, transient override at
`$XDG_RUNTIME_DIR/ab-face-motion-override.json` before its normal HTTP/pet
state. Authorized execution publishes only known asset routes:

| State | Action | Verified RGBA baseline |
| --- | --- | --- |
| turning | `turn_left` / `turn_right` | `xiao-shu-v3-ai-alert-peek-v3` |
| walking | `walk_left` / `walk_right` | `xiao-shu-v3-ai-soft-bounce-v1` |
| arriving | `arrive_settle` | `xiao-shu-v3-ai-completion-nod-v1` |
| completed | normal renderer state | override removed |

The baseline assets were decoded in tests and contain both transparent and
visible pixels. They are deliberately reused rather than mislabelling a failed
generated asset as production walking animation.

Every override carries the exact
`agent_bridge.avatar_native_motion_override.v1` schema and a 10-second expiry.
The renderer ignores expired files, so a hard process stop cannot leave Xiao
Shu indefinitely stuck in a transient action pose.

## Generated-asset decision

The built-in image generator was asked for an eight-frame, left-facing,
192x208-cell v3 walk strip with a genuine transparent background. It returned
a `1774x887` RGB image with a baked checkerboard, so it failed both geometry and
alpha requirements. The output remains outside the repository and is not
runtime-bound. The previous concept contact sheet remains concept-only.

## Verification gates

- Pure planner/action, alpha-binding, override parsing, and expiry tests: seven
  cases.
- Default invocation: dry-run, zero movement.
- Full authorization with `/dev/null` as an existing cancel marker: cancelled
  before step zero, zero movement.
- Build and tests with `linux-native-avatar`: passed.
- Live owner-authorized movement: completed 16 steps over a planned 761-pixel
  travel; Avatar moved from `(1367,733,90,130)` to `(606,765,90,130)`.
- Focused Sway node remained `13` before and after; no focus steal observed.
- Motion override absent after completion; cleanup passed.
- Sway reported the final content rectangle 19 pixels below the planned Y
  coordinate, consistent with compositor container/content coordinates. The X
  docking edge and non-overlap safety remained correct.

## Deferred visual work

- Dedicated left/right transparent walk cycles.
- A transparent wave sequence.
- Per-frame visual review at the final `90x130` projection size.
