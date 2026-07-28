# Agent authority receipt durable-replay composition S5

Date: 2026-07-28

Status: **IMPLEMENTED_TEST_ONLY_COMPOSITION_PENDING_RESULT**

Runtime authority: **NONE**

## Decision

S5 closes one narrow gap left explicit by S4:

`receipt_identity_end_to_end_reverified=false`.

It does not add another replay algorithm. Current master already contains the
private, default-off S7 SQLite durable replay registry. S5 instead tests whether
an exact S3 Ed25519 receipt can be reverified, reduced to fixed commitments,
and consumed by that existing registry without accepting caller-selected
transaction, receipt, nonce, scope, or payload identities.

The implementation remains a test-only module behind
`agent-authority-s5-durable-replay-composition-synthetic`. The feature depends
on `temporal-evidence-s7-durable-replay-synthetic`. It adds no public export,
constructor, database path, `StateStore` method, Bridge caller, MCP/CLI/daemon
surface, or non-test capability.

## Frozen S3 compilation adapter

Rust rejects the S3 example's leading `//!` crate documentation when that file
is expanded through `include!` inside another module. S5 therefore compiles:

`crates/bridge/examples/agent_authority_signed_trust_root_s3.rs.inc`

The `.inc` file is a mechanical projection of the frozen S3 source with only
the first four `//!` markers changed to `//`. Before parsing the S5 fixture, the
test reconstructs those four markers and requires the resulting bytes to equal
the original S3 source byte-for-byte. The original source must also retain its
frozen SHA-256. This keeps all executable tokens, fixture paths, verifier
logic, and embedded S3 tests identical without editing the historical S3
artifact.

The adapter and composition modules are sibling modules registered only under
`cfg(all(test, feature = "..."))`. This keeps the included S3 self-tests out
of the focused S5 test-name filter while exposing only a `pub(super)` typed
projection to S5. The `.inc` suffix is not a Cargo example target.

## Verified starting point

- current local/GitLab/GitHub master:
  `0b95c231b4ac61743c297b45b0abf81690bd3fd6`;
- frozen S4 result:
  `17d106f21d4540b81c609eaaf8fca7ce9462faf6`;
- current-master plus S4 lineage merge:
  `5335bab516dccd6706094ecd96544e2c19463b4d`;
- S7 implementation:
  `21d16c64c00ca1ba66b6833cc018e2796e76b5ef`;
- S4 on the merged tree: 8 passed, 0 failed;
- current-master S7 baseline: 12 passed, 0 failed, with three ignored helper
  tests invoked by parent process tests.

The S7 baseline includes real multi-process contention, restart replay,
post-commit result loss, and actual child-process SIGKILL before and after
commit. S5 may reuse those executable semantics but cannot broaden their claim
beyond the tested local SQLite profile.

## Why S4 is not yet composed

S4 consumes only each S3 fixture case's status label. Its replay steps carry
independently authored `transaction_id`, `receipt_id`, and `nonce` strings.
The seven S4 steps marked reviewable after candidate-state commit or exact
idempotent confirmation all reference either:

- `verified_primary_control`; or
- `verified_secondary_control`.

None carries the exact receipt ID and nonce signed by its referenced S3 case.
The frozen S5 audit therefore records:

```text
s4_reviewable_step_count                  = 7
s4_end_to_end_identity_match_count        = 0
s4_end_to_end_identity_mismatch_count     = 7
```

S5 does not rewrite the S4 fixture or reinterpret those steps as composed.
They remain valid evidence for the S4 status-only model and invalid evidence
for end-to-end receipt identity.

## Exact S3 eligibility

The S3 corpus contains 27 cases and four controls derived as `verified`.
S4 uses only two of those controls. S5 freezes that exact intersection:

```text
verified_primary_control
verified_secondary_control
```

The future-skew and expiry-skew boundary controls remain S3 verifier tests.
They are not S4 replay inputs and are not S5 transaction inputs. A caller
cannot choose another S3 case merely because its fixture label says
`verified`.

For an eligible case, S5 must:

1. load the exact frozen S3 registry and receipt corpus bytes;
2. check every frozen source hash;
3. run S3 input validation and real `ring` Ed25519 verification;
4. require derived status `verified`, successful signature verification, and
   no reasons;
5. reconstruct the exact canonical signed claims bytes;
6. require `issued_at_unix <= consume_time_unix < expires_at_unix`;
7. derive all three S7 commitments from those typed claims; and only then
8. construct the private replay request.

Expected labels are comparison evidence only. They never authorize request
construction.

## Commitment derivation

All frames use:

```text
u64be(len(domain)) || domain ||
for each ordered part:
    u64be(len(part)) || part
```

The transaction identity, used directly as S7 `replay_key_sha256`, is:

```text
SHA256(
  frame(
    "agent_bridge.agent_authority.s5.receipt_transaction_identity.v0",
    receipt_id,
    nonce
  )
)
```

It deliberately excludes the payload digest. Reusing one signed receipt ID and
nonce with altered claims must collide with the first transaction identity,
not create a fresh replay key.

The scope commitment is:

```text
SHA256(
  frame(
    "agent_bridge.agent_authority.s5.signed_scope_commitment.v0",
    claims_schema,
    envelope_version,
    issuer_id,
    principal_id,
    action_class,
    target_digest,
    scope_digest,
    decision_source_digest,
    session_epoch_digest,
    resume_parent_digest,
    adapter_id,
    adapter_build_digest,
    adapter_capabilities_digest,
    evidence_digest,
    verifier_id,
    policy_version,
    key_id,
    algorithm
  )
)
```

The payload commitment is the SHA-256 of the exact S3 canonical claims bytes.
Receipt ID, nonce, timestamps, and every scope field are therefore signed and
payload-bound even where they are not repeated in the scope frame.

For the two eligible cases the exact expected commitments are frozen in:

`scripts/eval/fixtures/agent_authority_receipt_durable_replay_s5.expected.v0.json`

Fixture SHA-256:

`d9b091c93fb1606f55cf78f450785f87ea81c8c0fd8737fcf27252b565c65d3e`.

## Fault model

The S5 parent tests use only temporary owner-only directories and the existing
S7 test provisioning path. They must cover:

1. exact first consume returns a durable receipt;
2. reopen rejects the exact replay;
3. same replay key with substituted signed scope rejects as collision;
4. same replay key and scope with substituted canonical payload rejects as
   collision;
5. injected result loss after durable commit is indeterminate, then reopen
   rejects replay;
6. actual child-process SIGKILL after insert but before commit rolls back, so a
   later first consume succeeds;
7. actual child-process SIGKILL after commit preserves the tombstone, so reopen
   rejects replay; and
8. nonverified or non-allowlisted S3 cases fail before the registry is opened.

The SIGKILL helpers independently reload and reverify the exact S3 fixture. No
request commitments are passed through environment variables.

## Falsifiers

S5 fails closed if any of the following occurs:

- frozen source or fixture hash drift;
- an expected S3 label bypasses real verification;
- a caller supplies any transaction, receipt, nonce, scope, or payload
  commitment;
- an S4 reviewable step is misreported as end-to-end matched;
- two eligible S3 receipts derive the same transaction identity;
- a signed-field mutation produces an accepted request;
- exact replay succeeds after restart;
- a collision overwrites the first immutable row;
- pre-commit crash burns the transaction;
- post-commit crash releases a second success;
- an indeterminate outcome falls back to memory or retries automatically;
- a normal/default build exposes a constructor or caller; or
- any authority field becomes true.

## Non-claims

S5 does not establish a production trust root, root custody or rotation,
whole-file rollback resistance, universal power-loss durability, distributed
linearizability, cross-host exactly-once execution, side-effect atomicity,
privacy deletion, a runtime receiver, a production database identity, or any
right to dispatch.

It may claim only:

`EXACT_PUBLIC_TEST_S3_RECEIPT_IDENTITY_COMPOSED_WITH_EXISTING_SYNTHETIC_LOCAL_S7_DURABLE_REPLAY_UNDER_TESTED_FAULT_WINDOWS`

No production/private key, signing operation, credential, KMS/HSM, live
`state.db`, persistent production path, MCP/CLI/daemon/StateStore caller,
memory/graph/session/retrieval mutation, runtime/shadow/executor integration,
deployment, master merge, or production authority is admitted.
