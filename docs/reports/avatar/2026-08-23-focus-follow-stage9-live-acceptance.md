# Xiao Shu focus-follow stage 9: live acceptance

Date: 2026-08-23

## Decision

The bounded Focus-follow behavior is accepted for explicit, owner-confirmed
desktop use. The production sequence is:

1. dedicated turn atlas;
2. dedicated directional walk atlas;
3. `xiao-shu-v3-ai-completion-nod-v2` arrival settle;
4. dedicated wave atlas;
5. return to idle.

Focus-follow remains default-off. It moves only the `agent-bridge-avatar`
window, does not move the pointer, does not change keyboard focus, and requires
an explicit confirmation and reason for every execution.

## Live evidence

The owner observed multiple complete traversals at desktop scale. Verified
routes included eight- and nine-step paths over approximately 352-404 pixels,
with both left- and right-facing choreography. Sway compositor state confirmed
the Avatar reached the planned focus-adjacent destination after each run.

The first acceptance pass exposed a dark horizontal artifact during
`arrive_settle`. Inspection found the previous completion atlas contained a
shadow band across the eye line and an abnormal closed-eye frame. A first
generated repair candidate was rejected because background extraction left
edge fringe and debris. The accepted v2 atlas instead reuses clean,
human-accepted Xiao Shu idle frames and arranges them into an anchored eight
frame nod sequence. The owner then observed two complete v2 traversals and
confirmed there was no shadow frame.

## Verification

- Installed binary and native renderer: `239d23d39a90`.
- `agent-bridge doctor --json`: `ok=true`, `fails=0`, `warns=0` after Codex
  restart.
- Core Avatar regression suites: 61 tests passed.
- HTTP asset route and completion-nod filtered tests passed.
- Runtime binding resolves `arrive_settle` to
  `xiao-shu-v3-ai-completion-nod-v2` with `alpha_ready=true` and
  `dedicated_motion=true`.
- Final owner verdict: accepted; no shadow frame.

## Next bounded stage

Build a read-only focus-change recommendation surface. It may observe the
current focused Sway node, compare it with the last acknowledged target, and
return one of `stay`, `recommend_move`, or `suppress`. It must not dispatch
movement, move the pointer, change focus, or weaken the existing per-call
confirmation gate. Automatic execution remains out of scope.
