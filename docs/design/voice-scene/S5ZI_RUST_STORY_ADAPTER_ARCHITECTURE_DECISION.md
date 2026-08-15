# ADR S5ZI: Rust-native story preflight integration

## Status

Accepted for the static migration path. Runtime registration remains
unauthorized.

## Context

S5ZH proves that the current story preflight can run by direct function call
inside one Python interpreter. Agent-Bridge itself is a Rust binary, so that
does not answer whether production should embed Python or port the deterministic
story logic into Rust. The decision must preserve the single-native-binary
deployment contract, avoid shell and child processes, retain exact S5ZF
semantics, and keep MCP registration separately gated.

The audited five Python modules contain 1694 lines and use only Python's
standard library. The bridge already depends on `serde_json` and `sha2`, has no
PyO3/libpython lifecycle, and deploys `agent-bridge.real` as a native binary
with external adapters handled separately.

## Options considered

| Option | Benefits | Costs |
|---|---|---|
| Incremental Rust-native port | Preserves native deployment, cancellation and error model; avoids Python ABI, GIL and interpreter lifecycle; reuses existing JSON/hash crates | Requires a bounded port and cross-language golden parity; temporarily maintains Python as an oracle |
| Embedded Python interpreter | Reuses the current Python implementation | Adds PyO3/libpython packaging, ABI, GIL, interpreter lifecycle and supply-chain complexity to the main process |

## Decision

Choose the incremental Rust-native port. Python remains a test oracle only and
receives no runtime authority. The migration is split into four reversible
units: S5ZJ typed request/canonical JSON/hash parity; S5ZK source ingest and
chapter selection parity; S5ZL voice-plan, transition and cache-key parity; and
S5ZM complete preflight plus negative-control parity. None registers an MCP
tool. Registration requires a separate owner-authorized gate after parity.

## Trade-offs accepted

We accept short-term duplication and the cost of cross-language golden tests in
exchange for avoiding a permanent interpreter inside the bridge. Each Rust
unit stays unregistered and can be removed while the accepted Python oracle
continues to function, providing a direct rollback.

## Consequences

The next implementation may add only a pure Rust story contract core. It must
not add PyO3, modify tool exposure, execute TTS, or claim full preflight parity.
This decision can be reopened only if a required Python-only dependency blocks
a bounded native port or measured parity-maintenance cost exceeds the measured
embedding cost; preference alone is not a revisit trigger.
