# G2L execution authorization packet draft

Status: **DRAFT / PROPOSED — NOT OWNER SIGNED — NO EXECUTION AUTHORITY**.

This static packet is based only on commit
`b086e221d5a6d83a218ae70118b0dcac53570d73`, tree
`ceb87fe2664d0c05d813bccd22edb51325a9c70b`. It proposes the fields and
controls that a future owner-signed G2L execution authorization would have to
freeze. It does not discover, infer, approve, build, run, or deploy anything.
Every real WIT, dependency, toolchain, linker, component, output, target, and
runtime value remains `UNSET_REQUIRES_OWNER_SIGNATURE`.

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

Dependency, WIT, linker, component, output, runtime, and deploy gates are all
`false`. Checker PASS means only that this four-file draft remains internally
bound and fail-closed; it cannot open a gate.

The fixture binds all four files by canonical SHA-256. Canonical bytes replace
every lowercase 64-hex sequence with 64 ASCII zeroes before hashing, avoiding
self-reference. The checker uses Python standard-library file/JSON/hash
operations only and contains no process launch. The wrapper only `exec`s the
checker.
