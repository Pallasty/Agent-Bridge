# Agent Authority Trust Lifecycle And Atomic Replay S4 Result

Date: 2026-07-16

Status: PASS_OFFLINE_LIFECYCLE_AND_ATOMIC_REPLAY_PREFLIGHT_ONLY / PUBLIC_TEST_KEYS / CANDIDATE_STATE_ONLY / NO_RUNTIME_AUTHORITY

## Result

The S4 offline reference evaluator verified a signed authority-key lifecycle
journal against a frozen public-test anchor, derived the preregistered
21-case lifecycle distribution, and evaluated 26 deterministic atomic replay
schedules containing 30 steps. All lifecycle status/reason comparisons,
candidate-state comparisons, and reviewability guards matched the freeze.

This result advances S3 from a static signed-receipt trust root to a test-only
trust lifecycle and an in-memory compare-and-swap replay model. It does not
reverify the exact S3 receipt identity as the S4 transaction identity, persist
candidate state, establish a production trust root, prove production
atomicity, consume runtime receipts, or grant execution authority.

## Lineage

- latest master ancestor:
  `c9c50917687c7715b031a6bfe8dd7801bfd737ee`
- S3 result ancestor:
  `149bafbc3a04126ea28f05a85c3e30d2748aceed`
- S4 lineage merge:
  `72ba3dabd2569e651e05a90dfc1c898fa366c24e`
- verified S4 implementation commit:
  `abfcd9cd4e5456217e6dfb89c81ee0dec872ea10`

Both latest master and the S3 result were verified as ancestors of the S4
implementation commit.

## Frozen Artifacts

- public-test trust anchor SHA-256:
  `daae7bea20842cd1f8116084f757843dcc9020aa2b3d40ab26ce3af9114f1fe5`
- signed lifecycle journal corpus SHA-256:
  `b1ffd8c38060f6f39925fea97ac3c21f20a138ea1debb430c06f9fa44b7c4342`
- atomic replay schedule corpus SHA-256:
  `dd24e1a8678205ce4f7ae6bae940eeb1e75136f7614b425b7989abe4e0d908d3`
- deterministic report SHA-256:
  `42c5de349919da911d42c85bcd47438fcfe51065c19d6f13c2d1571773ae2e40`

The anchor contains three RFC 8032 public test keys: one active lifecycle
authority, one audit-only signer, and one revoked lifecycle authority. The
temporary fixture generator used published test seeds only to precompute the
fixture signatures and was deleted after generation. No private seed, private
key, signing operation, production credential, or root service is committed.

## TDD Evidence

The eight S4 tests were written before the evaluator implementation. The RED
run exited 101 with 52 missing type/function/API errors, including the trust
anchor and corpus loaders, canonical event encoding, lifecycle and replay
evaluators, frozen source validation, mutation coverage, status enums, and
top-level report evaluation.

The focused command was:

```text
CARGO_TARGET_DIR=/Data/CascadeProjects/agent-bridge-agent-compromise-resilience-s0-20260716/target \
  cargo test -p ab-bridge --no-default-features \
  --example agent_authority_trust_lifecycle_atomic_replay_s4 -- --nocapture
```

The first GREEN run passed all eight tests. No expected label, expected count,
fixture hash, lifecycle precedence, replay precedence, or authority boundary
changed after RED.

## Lifecycle Result

| Status | Count |
|---|---:|
| current | 2 |
| invalid | 3 |
| untrusted | 3 |
| rollback | 2 |
| forked | 5 |
| revoked | 2 |
| stale | 2 |
| ambiguous | 1 |
| unavailable | 1 |
| total | 21 |

The evaluator attempted 83 real ring Ed25519 verifications: 82 succeeded and
the expected signature-tamper case failed. No adversarial case derived
`current`; neither control was falsely rejected; status and lexical-reason
mismatch counts were zero.

## Atomic Replay Result

| Outcome | Count |
|---|---:|
| committed | 4 |
| already_committed | 3 |
| nonce_replayed | 3 |
| version_conflict | 1 |
| prepared_not_committed | 1 |
| crashed_before_commit | 1 |
| commit_ack_lost | 1 |
| transaction_identity_conflict | 1 |
| receipt_ineligible | 7 |
| lifecycle_blocked | 8 |
| total | 30 |

Both forward and reverse competing-receipt schedules produced exactly one
candidate commit. Exact idempotent retries precede version checks. Exactly
seven steps were reviewable: acknowledged candidate commits and exact
idempotent confirmations only. Outcome, final-state, and false-reviewable
mismatch counts were zero.

## Verification Matrix

- S4 focused tests: 8 passed, 0 failed.
- S3 adjacent tests: 7 passed, 0 failed.
- S2 adjacent tests: 6 passed, 0 failed.
- S1 adjacent tests: 4 passed, 0 failed.
- S0 adjacent tests: 4 passed, 0 failed.
- `cargo check -p ab-bridge --all-targets --quiet`: exit 0 manually and in the
  implementation commit hook.
- two post-commit S4 report runs: byte-identical, both with SHA-256
  `42c5de349919da911d42c85bcd47438fcfe51065c19d6f13c2d1571773ae2e40`.
- JSON parsing, embedded lineage/source/hash pins, `rustfmt --check`, staged
  diff checks, and credential/private-seed scans: passed.

Existing repository warnings remained for mixed-script test naming, dead code,
and the pre-existing `ToolPolicy` visibility boundary. S4 introduced no new
warning in its ordinary example build.

## Explicit Nonclaims

Every report authority field is false. In particular, S4 does not:

- dispatch work or run shadow/executor paths;
- enable MCP, T6, runtime admission, or a runtime consumer;
- write memory, graph, session, retrieval, registry, or replay state;
- prove end-to-end S3 receipt-to-S4 transaction identity composition;
- establish or rotate a production trust root;
- prove production transactional durability or atomicity;
- use production keys, credentials, KMS, HSM, or network identity services;
- deploy, merge to master, or grant authority.

Candidate commits and idempotent confirmations are offline review evidence,
not admission, execution, or persistence decisions.

## Next Gate

Any S5 work must be separately preregistered. The narrow next question is
end-to-end S3 receipt identity binding plus crash-recovery fault injection
against an ephemeral transactional test store. Production roots, live state,
runtime integration, deployment, authority grants, and master merge remain
outside this result.
