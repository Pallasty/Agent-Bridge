# S5ZO story preflight adapter hardening

## Outcome

The unexported native story preflight now has the three safeguards required by
S5ZN. This is library-level readiness for a separate registration
implementation review; it is not an MCP registration or runtime enablement.

## Boundaries

- Source files are canonicalized under an explicitly configured allowed root,
  limited to 16 MiB or a smaller caller limit, read in bounded chunks, and
  decoded as strict UTF-8.
- The voice plan, mapping, role acceptance, and continuity acceptance are
  resolved from configured files under an allowed root. Every file is bounded,
  SHA-256 bound, and parsed as JSON before composition.
- Blocking work is owned by an async wrapper. A cancellation token is checked
  before and during every chunked read; cancellation waits for the worker to
  stop instead of detaching it.
- Failures remain typed `StoryContractError` values. No panic path is part of
  the public adapter contract.

## Evidence and nonclaims

The hardened path preserves the accepted S5ZF preflight digest
`6553dcec1ad51e1b6352d0fc7fa2068b38713d1e37dedacbe45b00f3aca4a1bb`.
Negative controls reject root escape, oversized sources, evidence hash drift,
pre-cancelled work, and runtime flags.

The module remains absent from `lib.rs`; no tool is registered or exposed, no
deployment is performed, and no model, ONNX, audio, cache, or memory action is
executed. The next gate is an owner-authorized Rust story registration
implementation review.
