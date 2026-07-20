# S21B-A14 proof-boundary register

S21B-A14 turns the finite A13 static-reachability result into a canonical
proof-boundary register. It records the A13 audit as input and enumerates the
evidence classes that remain unproven: runtime execution, owner authorization,
real-input scope, credentials and environment, temporal freshness and
revocation, and the trusted live-output boundary.

Every entry is deliberately marked `UNPROVEN_REQUIRED_FOR_CAPABILITY_CHANGE`.
The register does not close, waive, infer, or aggregate any missing evidence.
Its contract requires every listed class to be explicitly addressed by a new,
separately reviewed successor before a capability change can be considered.

The register is audit-only. It verifies the A13 input self digest and frozen
contract binding, then emits a self-digested statement with explicit negative
authority and capability fields. A changed A13 audit, altered list, or changed
negative field fails closed.
