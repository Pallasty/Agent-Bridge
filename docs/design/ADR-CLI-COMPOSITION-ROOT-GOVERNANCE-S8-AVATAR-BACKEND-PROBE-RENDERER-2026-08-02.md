# ADR: CLI composition-root governance S8 Avatar BackendProbe renderer

## Status

Accepted for implementation on 2026-08-02.

- Base: `3e59f37351183214a8aac61e6eadc12e08bf85be`
- Coordination: Agent-Bridge forum thread #350
- Predecessor: S7 Avatar inventory and authority-safety stop, thread #297
- Scope: completed `BackendProbe` result rendering only
- Adoption posture: source-only; no deployment, restart, or reconnect

## Context

S7 rejected a wholesale `AvatarOp` move because the family spans Store, file,
process, launchd, window, audio, queue, ledger, and runtime authority. It named
the completed `BackendProbe` presentation tail as the narrowest conditional
future candidate while requiring environment detection and backend
recommendation to remain visible at the composition root.

The separately owned safety findings recorded by S7 now have closed successor
gates: replay preservation (#299), passive heartbeat process provenance (#315),
MCP enqueue fail-closed policy (#321), Aura path authority and bounded adoption
(#339), and HeartbeatAlert preview no-write semantics (#346). Those closures do
not make Avatar generally read-only and do not authorize any other extraction.

At the S8 base, `run_avatar_backend_probe` is 50 lines. Its first two statements
read compositor environment through `detect_compositor` and derive a backend
recommendation. The remaining branch only renders those completed values as
JSON or text. The renderer has no Store, file, process, launchd, audio, window,
network, queue, ledger, or runtime dependency.

## Decision

Create binary-private `cli::avatar` and move only the completed-result renderer
to `render_avatar_backend_probe_result`.

`main.rs` retains:

- the complete `AvatarOp` Clap schema and `BackendProbe` variant;
- the root dispatch arm and `run_avatar_backend_probe` executor;
- `as_json` selection and `Result` propagation;
- `detect_compositor`, including all process-environment custody;
- `recommend_backend` and the order detect -> recommend -> render.

`cli::avatar` receives only `&CompositorInfo`, `&BackendRecommendation`, and the
already parsed `as_json` boolean. The module remains private. Its renderer is
`pub(crate)` only because Rust cannot widen a child `pub(super)` item through a
parent re-export; this is the same binary-crate visibility pattern used by the
existing private CLI modules and does not expose a library API.

## Behavior contract

S8 freezes exact real-binary contracts for:

- unknown-environment human-readable stdout;
- unknown-environment pretty JSON bytes;
- wlroots Wayland human-readable stdout;
- `--help` stdout;
- invalid-argument exit code, empty stdout, and stderr.

The characterization suite must pass before production movement, the ownership
test must then fail because `cli::avatar` is absent, and both must pass after the
minimal move. No volatile normalization is needed for this command.

## Authority contract

The ownership test requires schema, dispatch, root executor, detection,
recommendation, and renderer invocation in `main.rs`. It forbids the private
module from containing environment detection/recommendation, Store, filesystem,
process, launchd, heartbeat, notification, voice, or Xiao Shu queue authority.

S8 does not change defaults, errors, output order, environment precedence,
backend policy, public library types, or any of the other 42 Avatar commands.
It does not establish a generic renderer framework.

## Alternatives

### Move the whole BackendProbe executor

Rejected. This would move environment custody and recommendation policy out of
the explicit composition root, contradicting S7.

### Move the complete Avatar family

Rejected. Physical grouping would conceal rather than reduce its authority
width.

### Leave the renderer in main.rs

Safe but misses the one S7-preregistered pure seam now protected by exact CLI
parity and a custody test. S8 uses the seam as a bounded architecture proof, not
as a line-count campaign.

## Stop and revisit conditions

Stop if the change requires moving or obscuring environment, Store, file,
process, launchd, audio, window, network, queue, ledger, default, error, or
runtime ownership. Any subsequent Avatar presentation move requires its own
evidence, RED ownership, parity artifacts, and authorization; S8 is not a
blanket reopen.

## Verification

Required before landing:

- exact CLI parity suite;
- S8 ownership/custody suite;
- adjacent `avatar_floater` unit tests;
- scoped rustfmt and `git diff --check`;
- repository pre-commit all-target check;
- fresh `ab-bridge --all-targets` test gate on the reconciled master;
- non-force fast-forward and readback from both remotes.
