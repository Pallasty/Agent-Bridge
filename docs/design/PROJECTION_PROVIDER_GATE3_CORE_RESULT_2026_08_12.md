# Projection Provider Gate 3: Core Contract Result

Date: 2026-08-12

## Scope

Gate 3 extracts a provider-neutral request and evidence contract into
`ab-world-core`. The contract is intentionally below MCP, storage, browser,
renderer, and engine adapters.

Implemented in `crates/world-core/src/projection_provider.rs`:

- `ProjectionRequestEnvelope` for a requested projection, source world
  revision, provider identity, requested outputs, constraints, and optional
  authority reference.
- `EngineExecutionReceipt` for structured execution evidence with provider,
  action, rollback, verdict, and truth-boundary fields.
- `ProjectionEvidenceClass` with the explicit ladder:
  `simulated.generated`, `simulated.executed`, `observed.real`.
- Pure validation that rejects schema/identity gaps, verdict mismatches,
  generated output promoted to execution truth, simulated claims of external
  effects, and incomplete verified rollback evidence.

The receipt fields accept the Onsen LSWR receipt shape, including aliases for
the existing `*_model_hash` names. This is a data-contract mapping only; it
does not claim that every provider is registered or executable.

## Verification

```text
cargo test -p ab-world-core --lib
39 passed; 0 failed

rustfmt --edition 2021 --check \
  crates/world-core/src/projection_provider.rs \
  crates/world-core/src/lib.rs
git diff --check
```

The repository-wide `cargo fmt --all --check` remains blocked by pre-existing
format differences in unrelated crates. No unrelated formatting changes were
included.

## Admission boundary

This gate remains design/core-contract only:

- no new MCP tool;
- no provider registry entry;
- no ABot-World model execution;
- no default-on runtime path;
- no authority promotion from `ProjectionRequestEnvelope`.

Verdict: `GATE3_PROVIDER_NEUTRAL_CORE_CONTRACT_VERIFIED_DEFAULT_OFF`.

The next separately reviewable gate is a read-only adapter mapper or fixture
comparison for ABot-World and the existing Godot receipt. It must preserve
the evidence ladder and must not turn generative output into execution truth.
