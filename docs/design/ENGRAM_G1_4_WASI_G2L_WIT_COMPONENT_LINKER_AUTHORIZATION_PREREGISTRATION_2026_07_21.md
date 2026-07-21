# G2L WIT/component/linker authorization preregistration

Status: **STATIC PREREGISTRATION ONLY — ALL EXECUTION AUTHORITY CLOSED**.

G2L follows the G2G FINAL PASS at master commit
`f0ea35edc066afe7adb71f7d7d9916cb630de938`, tree
`f63107ee0ad97ee4daad589a7323e31c72722ffe`. That G2G result proves only that
the frozen, input-bound host fixture compiled offline and locked in independent
receipts. It does **not** prove byte reproducibility, WIT generation or ABI
compatibility, component construction, linker construction, output behavior,
runtime admission, or deployment.

## Frozen future input tuple

Before any future execution request can be reviewed, a separate execution
authorization must freeze every value below; `UNSET_REQUIRES_SUCCESSOR` is a
closed placeholder, never permission to discover or fill a value by running a
tool.

- G2G master commit and tree above, plus receipt evidence references
  `scripts/eval/engram_g14_wasi_g2g_receipt_runner.py` and
  `scripts/eval/check_engram_g14_wasi_g2g_receipt_runner.py` at that tree.
- Exact WIT source path and bytes, with its SHA-256 and the exact derived ABI
  hash.
- Exact component-model version/profile and adapter identity/profile, including
  adapter path and SHA-256.
- Absolute paths, SHA-256 values, and version strings for every Rust, Cargo,
  wasm, WIT, component, and linker tool proposed for use.
- Every dependency package identity, source identity/location, package SHA-256,
  and the complete lockfile path and SHA-256.
- Cache policy and an explicit no-network policy, including allowed pre-existing
  cache roots and a ban on cache population or dependency resolution.
- Every output artifact path and target path, plus cleanup policy, cleanup
  verification, and leftover reporting.

## Mandatory execution preconditions

All of these are required and none is satisfied by this preregistration:

1. explicit owner approval in a separate G2L execution authorization;
2. independent review of that complete authorization before execution;
3. fresh, distinct, clean worktrees and fresh bounded target directories;
4. offline, locked, no private/candidate input, no network, and no rustup
   selector/re-entry;
5. no execution of any produced output and no runtime or deployment action;
6. pre/post input and tool identity receipts, command/exit receipts, negative
   evidence, cleanup receipts, postcondition receipts, and rollback receipts.

Any missing, ambiguous, mutable, or drifting value fails closed. Until the
separate authorization exists and passes review, no `cargo`, `rustc`, wasm,
WIT, component, linker, or related generation/build tool may be invoked.

## Closed authority boundary

The fixture freezes all seven current permissions to `false`:
`authorization_granted`, `dependency_resolution_allowed`,
`wit_generation_allowed`, `linker_build_allowed`, `component_build_allowed`,
`output_execution_allowed`, and `runtime_or_deploy_allowed`.

A PASS from this preregistration, its checker, or its wrapper proves only that
the static packet is internally bound and still fail-closed. It opens none of
those permissions. G2L is not an execution authorization. Its only permitted
successor is one separate, owner-approved, independently reviewed **execution
authorization** containing the complete frozen tuple and receipt contract.

## Static integrity and command surface

The JSON fixture binds this document, the fixture, checker, and wrapper by
canonical SHA-256. To avoid a self-referential digest cycle, canonical bytes are
the file bytes with every lowercase 64-hex digest replaced by 64 ASCII zeroes;
the checker independently recomputes that transform for all four files. The
checker uses only Python standard-library file and JSON operations, never
`subprocess`. The wrapper contains only an `exec python3` invocation of the
checker. The checker rejects forbidden process-launch APIs and forbidden
Rust/Cargo/wasm execution command surfaces in the wrapper.
