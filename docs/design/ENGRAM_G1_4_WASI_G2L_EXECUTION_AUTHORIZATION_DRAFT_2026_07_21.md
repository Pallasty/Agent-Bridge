# G2L execution authorization packet draft

Status: **DRAFT / PROPOSED — NOT OWNER SIGNED — NO EXECUTION AUTHORITY**.

This static packet is based only on commit
`652c9e1a9ba148cd24a4fbc1987c9ab2a5d49c9e`, tree
`3b88a5a691db846c5a1bcb245779c149fa6017fc`. It proposes the fields and
controls that a future owner-signed G2L execution authorization would have to
freeze. It does not discover, infer, approve, build, run, or deploy anything.
The packet records already-observed canonical WIT and direct Rust tool
identities without authorizing their use. Every unobserved ABI, generated
binding, adapter, dependency, lockfile, cache, command, linker, component,
output, target, and runtime value remains `UNSET_REQUIRES_OWNER_SIGNATURE` or
`NOT_OBSERVED`.

## Observed canonical contract and tools

The observed canonical WIT is
`scripts/eval/fixtures/engram_g14_wasi_g2e_public_source_v0/world.wit`, SHA-256
`d47b294dc4c7ee3f48d7af8a6233022a75e79533a2f554ec1299639ba3e142be`.
It declares package `agent-bridge:g14-clock-probe@0.1.0`, world `probe`, and
the sole export `typed-report: func() -> typed-report`. Its result record is
`typed-report`, with ordered fields `wall-epoch-seconds: u64`,
`logical-nanoseconds: u64`, and `quantum-nanoseconds: u64`.

Direct observation records rustc
`/Users/pallasting/.rustup/toolchains/1.92.0-aarch64-apple-darwin/bin/rustc`,
SHA-256 `12cab30aa9890d54445e29149a1e82d18fbe457de12801bd11bbe7e5e7fe33a0`,
version `rustc 1.92.0 (ded5c06cf 2025-12-08)`, and cargo at the sibling
`cargo` path, SHA-256
`03e381389f5b7b8e695a744362f3866478f99034b2cf2df6afd4d42cfdab6f67`,
version `cargo 1.92.0 (344c4567c 2025-10-21)`. G2A's Wasmtime 46.0.1 is
recorded only as a candidate; it does not authorize dependency selection,
resolution, parsing, fetching, or use. ABI SHA, generated bindings, adapter,
`wasm-tools`, `wit-bindgen`, `cargo-component`, and `wasm-ld` were not
observed.

## Frozen tuple required before signature

The formal authorization must replace every placeholder in one reviewable,
immutable tuple: exact source commit/tree; WIT path, bytes SHA-256 and ABI
SHA-256; component-model and adapter identities; every dependency name,
source, version and SHA-256; exact lockfile; every tool absolute path, version
and SHA-256; allowed pre-existing cache roots; exact commands and arguments;
fresh worktree and bounded output/target roots; expected outputs and hashes;
cleanup, postcondition, rollback, and negative-evidence receipt contracts.
Partial replacement, discovery during execution, mutable selectors, PATH-only
tool identities, ranges, floating versions, or implicit commands fail closed.

## Approval and independent review

`owner_approval_received=false` and `execution_authorized=false`. The owner
identity, decision, signature, signed-at time, expiry, nonce, tuple SHA-256,
and maximum-use count are all unsigned placeholders. A reviewer independent
of packet preparation and execution must verify the exact tuple, command
allowlist, environment, paths, limits, stop conditions, rollback, and receipt
schemas before the owner signs. Review cannot substitute for owner approval.

The only successor is a separate formal execution authorization carrying the
owner signature over the fully populated tuple and the independent review
receipt. Editing this draft in place, checker PASS, commit, merge, build
availability, cache availability, or tool presence grants no authority.

## Proposed execution envelope

- Use distinct fresh clean source and review worktrees at the authorized
  commit/tree and fresh, non-existing bounded output and target directories.
- Run offline and locked, without private/candidate inputs, network, rustup,
  ambient credentials, privilege escalation, deployment, or produced-output
  execution. Pre-existing cache roots are read-only and must be signed.
- Execute only the exact ordered command allowlist. No shell expansion,
  command substitution, response files, nested build, hooks, aliases,
  wrappers, extra environment variables, retries, or unlisted cleanup.
- Refuse any identity drift, dirty worktree, existing target, unexpected file,
  network capability, private input, missing lock, nonzero preflight finding,
  command mismatch, output mismatch, timeout, or receipt failure.

## Receipt and rollback contract

Before any command, receipts must bind the authorization/signature/review,
commit/tree, worktree cleanliness, inputs, lockfile, dependencies, tools,
environment, cache roots, absence of network/private inputs, command allowlist,
and fresh directories. Per-command receipts bind argv, cwd, environment,
start/end, exit status, stdout/stderr hashes, and created/modified paths.

Postcondition receipts bind only expected outputs, exact hashes, target bounds,
no execution, no runtime/deploy, and no unexpected leftovers. Cleanup receipts
record every removed or retained path and verify the source worktree is
unchanged. Rollback is mandatory on any deviation and must preserve evidence,
remove only authorization-owned output/target paths, verify cleanup, and emit
a rollback receipt. Negative-evidence receipts explicitly record zero network
attempts, zero private inputs, zero rustup, zero dependency resolution, zero
output execution, zero runtime admission, and zero deployment actions.

## Closed gates and static integrity

Owner approval, independent review, execution authorization, dependency, WIT,
linker, component, output, runtime, and deploy gates are all
`false`. Checker PASS means only that this four-file draft remains internally
bound and fail-closed; it cannot open a gate.

The fixture binds all four files by canonical SHA-256. Canonical bytes replace
every lowercase 64-hex sequence with 64 ASCII zeroes before hashing, avoiding
self-reference. The checker uses Python standard-library file/JSON/hash
operations only and contains no process launch. The wrapper only `exec`s the
checker.
