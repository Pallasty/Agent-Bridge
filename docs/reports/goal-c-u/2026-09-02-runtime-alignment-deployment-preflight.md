# Runtime alignment deployment preflight — 2026-09-02

Status: `SOURCE_BUILD_PASS_MAINTENANCE_RELEASE_NO_GO`

## Decision

The clean repository baseline and GitHub `origin/master` both resolve to
`02e6bb6016d045e7f15ee49b6d854c6c18b260fd`. The installed
`agent-bridge.real` still reports source `e6ccdcc4a5af`, so source and runtime
remain intentionally divergent.

Do not replace the installed binary from this preflight. The current master is
buildable and its default Guardian boundary remains fail-closed, but the active
roadmap still marks R9 production adoption as `HOLD`. Source verification does
not satisfy trusted-root provisioning, runtime-state migration, ordered service
adoption, installed verification, or fresh-MCP acceptance.

## Verified evidence

All commands ran from a clean isolated worktree at the exact remote head.

```text
cargo check -p ab-bridge --bin agent-bridge -j1
PASS (dev profile)

python3 -m unittest tests/test_agent_bridge_project_truth_snapshot.py
PASS (13 tests)

cargo test -p ab-bridge --lib invocation_guardian -j1
PASS (24 tests; 2168 filtered out)
```

The ordinary `ab-bridge` default feature set is only `onnx-embed`. Guardian v2
canary, isolation probe, protected-witness contract, and provider lab remain
separate default-off features. The tested production constructor continues to
return HOLD for an otherwise valid non-root identity.

Compiler warnings were present but no compilation or test failure occurred.
This preflight made no installed-binary, wrapper, service, state-store, trusted
root, credential, or MCP-process change.

## Next gate

Keep the installed runtime at `e6ccdcc4a5af` until one of these independently
authorizes a deployment:

1. the R9 trusted-root sequence completes its currently documented production
   gates; or
2. a separately scoped default-runtime maintenance release identifies the
   exact admitted commit range, rollback artifact, service refresh plan, and
   installed/fresh-MCP acceptance checks without claiming R9 or Guardian
   admission.

Guardian source expansion remains frozen. This result does not reopen C2, C3,
Resident attention, scheduler, push, effect-authority, or proof-protocol work.

## Default-runtime maintenance release audit

The second gate above was evaluated and rejected. The installed-to-master range
contains 72 commits across 109 files, with 55,565 added and 1,221 removed lines.
It is not a narrow maintenance delta.

More importantly, R9 is present in ordinary runtime paths rather than only in
default-off laboratory binaries:

- `SqliteStore::open` admits the immutable workload-receipt ledger schema;
- `build_hub` invokes startup workload-receipt reconciliation;
- body task-span completion can atomically commit and acknowledge durable
  workload receipts when a bound receipt is present; and
- Doctor inspects the durable receipt root.

The Guardian canary, isolation, protected-witness, and provider-lab features
remaining default-off does not remove this R9 deployment boundary. Adding a
new ambient runtime switch solely to make this broad binary installable would
create another configuration state without completing the trusted-root,
migration, service-adoption, and rollback evidence that R9 already requires.

Therefore the exact maintenance-release decision is `NO_GO`. Keep the installed
binary unchanged. Reconsider deployment only through the existing R9 adoption
sequence or after a future, independently justified runtime release starts from
a newly measured narrow delta.
