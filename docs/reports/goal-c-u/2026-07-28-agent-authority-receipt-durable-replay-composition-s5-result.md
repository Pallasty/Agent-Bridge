# Agent authority receipt durable-replay composition S5 result

Date: 2026-07-28

Status: **PASS_TEST_ONLY_COMPOSITION**

Runtime authority: **NONE**

Implementation commit:
`625c263f85b9a4c94b98fa5aa4b9451f31f9c26e`

## Result

S5 proved the preregistered narrow claim:

`EXACT_PUBLIC_TEST_S3_RECEIPT_IDENTITY_COMPOSED_WITH_EXISTING_SYNTHETIC_LOCAL_S7_DURABLE_REPLAY_UNDER_TESTED_FAULT_WINDOWS`

The exact signed identity of the two S3 receipts referenced by S4 is now
reverified and reduced to fixed transaction, scope, and payload commitments
before the existing private S7 replay registry is opened. No caller supplies
the receipt ID, nonce, replay key, scope commitment, or payload commitment.

The implementation is compiled only under:

```text
cfg(all(
  test,
  feature = "agent-authority-s5-durable-replay-composition-synthetic"
))
```

It adds no public constructor, default path, `StateStore` method, Bridge
caller, MCP/CLI/daemon tool, receiver, migration, or runtime capability.

## Lineage

- current master used for the branch:
  `0b95c231b4ac61743c297b45b0abf81690bd3fd6`;
- frozen S4 result:
  `17d106f21d4540b81c609eaaf8fca7ce9462faf6`;
- non-destructive current-master plus S4 lineage merge:
  `5335bab516dccd6706094ecd96544e2c19463b4d`;
- existing S7 implementation:
  `21d16c64c00ca1ba66b6833cc018e2796e76b5ef`;
- S5 implementation:
  `625c263f85b9a4c94b98fa5aa4b9451f31f9c26e`.

The S4 lineage merge was conflict-free. S5 does not merge this feature branch
to master and does not deploy it.

## TDD evidence

The first focused command was rejected before compilation because `--locked`
correctly detected the new `ab-store` development-dependency registration.
That was not counted as RED. An offline unlocked run updated only the
`ab-store` dependency list in `Cargo.lock`, adding already-locked `anyhow` and
`base64`.

The subsequent locked RED exited 101 with 24 missing S5 function references
and one test-skeleton lifetime diagnostic. It reached the intended S5 module;
there was no malformed fixture, dependency download, or unrelated crate
failure.

The first GREEN run produced:

```text
8 passed; 0 failed; 2 ignored; 520 filtered out
```

The two ignored tests are child-process helpers. Their parent tests actually
spawned and killed them to exercise the pre-commit and post-commit SIGKILL
windows.

## Exact composition

The eligible intersection remains exactly:

```text
verified_primary_control
verified_secondary_control
```

Fresh S3 evaluation produced 27 cases:

- 23 rejected before composition because they were not independently verified;
- 2 independently verified controls rejected because they were not in the
  frozen S4-referenced allowlist;
- 2 independently verified and allowlisted receipts composed.

The primary and secondary transaction commitments were respectively:

```text
af2958488e09ae49c84e86f36682537547bdbab7677204a81be183a92ddb2233
a9847db819df31ecb6ad9d9acec4cfe4a5e826c46484097ec43fe8423fe45ea7
```

Both exact scope commitments were:

```text
d12591e0f0a6116474d2a4c3e80bc7dbd3deb3e9a67b932d901c6daee0dfb7a8
```

The exact canonical-payload commitments were:

```text
c0fa51ffc4c3a594cd7c8881d1a5bd34f9047e465cf86194f6eafd3e48234e81
6d2475a244cb378a397da03c97d9ae47deb7646a0564554b048a4b8c61a96850
```

The independent S4 audit still found seven reviewable S4 steps, zero exact
signed receipt/nonce matches, and seven mismatches. S5 does not retroactively
reinterpret S4's caller-authored identities as end-to-end evidence.

## Fault outcomes

All preregistered S5 outcomes passed:

- both exact receipts commit once and reject exact replay after reopen;
- signed-scope substitution collides without overwriting the first row;
- canonical-payload substitution collides without overwriting the first row;
- result loss after durable commit is indeterminate, then replay on reopen;
- actual SIGKILL before commit rolls back and permits one later first consume;
- actual SIGKILL after commit preserves the tombstone and rejects replay; and
- nonverified or non-allowlisted receipts never construct a replay request.

The inherited S7 matrix also passed:

```text
12 passed; 0 failed; 3 ignored; 498 filtered out
```

## Frozen S3 adapter

Rust does not admit the S3 example's leading inner doc comments through
`include!`. The test-only `.rs.inc` projection changes only those four comment
markers. Both the executable S5 check and an independent `cmp` check restored
the markers and required byte equality with the original source. The original
source also retained its frozen SHA-256:

```text
b845f23afddb48e0b5a60f90fc6317e79f0e8495914e4634281a315c3e1d0d19
```

No executable token, fixture path, S3 verification step, or S3 expected result
was altered.

## Verification matrix

- S5 focused run 1: 8 passed, 0 failed, 2 ignored.
- S5 focused run 2: 8 passed, 0 failed, 2 ignored.
- S5 result-tree rerun: 8 passed, 0 failed, 2 ignored.
- inherited S7: 12 passed, 0 failed, 3 ignored.
- S4: 8 passed, 0 failed.
- S3: 7 passed, 0 failed.
- S2: 6 passed, 0 failed.
- S0: 4 passed, 0 failed.
- `ab-store` feature off: check passed.
- `ab-store` S5 feature on: check passed.
- `ab-bridge --all-targets --no-default-features`: passed manually in
  19 minutes 28 seconds.
- repository pre-commit `ab-bridge --all-targets`: passed again on the exact
  staged implementation.
- JSON parse, exact source/fixture hashes, adapter byte equivalence,
  `rustfmt --check`, staged `git diff --check`, secret/private-key scan, and
  runtime/public-surface scan: passed.

Existing repository warnings remained for mixed-script test naming, unused
code, and the `ToolPolicy` visibility boundary. S5 introduced one expected
test-build warning for the included S3 example's unused `main`.

## S1 source-pin reconciliation

The current composed tree's S1 run produced 2 passed and 2 failed. Both
failures were the intended fail-closed diagnostic:

```text
t6_tests source hash changed
```

The frozen S1 pin is:

```text
d8b89e32212f2df1a5188c5d47addcc912f2f0b17518861cb53dea08d7cc1707
```

That hash exactly matches `crates/bridge/src/mcp_tools/tests.rs` at the frozen
S4 result commit. Current master has evolved that source to:

```text
118115073ef051c478eb109694d8ef0a8993af1f0f89dafde5131011b8b30289
```

A fresh detached run at `17d106f2` passed S1 4/4. The temporary verification
worktree was removed. S5 preserves the historical S1 pin and records the
current-main refusal rather than weakening or relabeling frozen evidence.

## Explicit nonclaims

S5 does not establish a production trust root, private-key custody, key
rotation, whole-file rollback resistance, universal power-loss durability,
distributed linearizability, cross-host exactly-once execution, side-effect
atomicity, privacy deletion, a runtime receiver, a production database
identity, or any right to dispatch.

Every S5 authority field remains false. No production/private key, signing
operation, credential, KMS/HSM, live `state.db`, production replay path,
MCP/CLI/daemon/StateStore caller, memory/graph/session/retrieval mutation,
runtime/shadow/executor integration, deployment, master merge, or production
authority was admitted.
