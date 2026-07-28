# Agent Authority Signed Trust Root S3 Result

Date: 2026-07-16

Status: PASS_OFFLINE_SIGNED_PREFLIGHT_ONLY / PUBLIC_TEST_ROOT / NO_RUNTIME_AUTHORITY

## Result

The S3 offline verifier used ring 0.17.14 to verify canonical Ed25519-signed
authority receipts against a separately parsed public-test trust registry. The
frozen 27-case corpus derived its exact preregistered eight-state distribution
with zero false accepts, zero control false rejects, and zero status or reason
mismatches.

This result advances S2 from evaluator-owned synthetic equality to real
public-key signature verification. It does not establish a production trust
root, owner identity, atomic replay protection, runtime admission, or execution
authority.

## Lineage

- latest master ancestor:
  `c9c50917687c7715b031a6bfe8dd7801bfd737ee`
- S2 result ancestor:
  `cdd426b846ff6c29bf008eba62a2d7bd57d09d4f`
- S3 lineage merge:
  `c0267f617d1636e688cc3d6e12f326191574c198`
- verified S3 implementation commit:
  `ee95b0c8f11043f6888372e159c829f871dc52a4`

Both latest master and the S2 result were verified as ancestors of the S3
implementation commit.

## Frozen Artifacts

- trust registry SHA-256:
  `1e26edf7a5c71ac972d5c1c7e2496d8c1baa772d9571db995cfac04fe6c3d573`
- signed receipt corpus SHA-256:
  `1a15620e6dc16166d71b4458d5207eacf30579b8f631c48f85ac62fba2456d8d`
- deterministic report SHA-256:
  `0aa7604a3ce36d4a31f3b1f5b05d35e1f427ba24bd345971cfab811c866a3ad8`

The registry contains six records using only the public key from RFC 8032
section 7.1 test vector 1. The fixture signatures were precomputed with OpenSSL
3.5.5 and the published test seed. No private key or signing operation is
committed or embedded in the verifier. `ring` is a bridge dev-dependency only;
it was already present transitively in `Cargo.lock`.

## TDD Evidence

The checker tests were written before implementation. The first focused run
exited 101 with 32 missing type/function/API errors, including `TrustRegistry`,
`Corpus`, source loading, canonical claims, case/suite evaluation, verification
states, and signature outcomes.

The focused command was:

```text
CARGO_TARGET_DIR=/Data/CascadeProjects/agent-bridge-agent-compromise-resilience-s0-20260716/target \
  cargo test -p ab-bridge --no-default-features \
  --example agent_authority_signed_trust_root_s3 -- --nocapture
```

After the implementation and the explicit fixture erratum below, the exact
implementation commit passed 7 tests with 0 failures.

## Pre-Pass Erratum

The first GREEN attempt exposed one contradiction in the frozen fixture. The
`wrong_action_rejected` case changed its action to `memory_write` while still
selecting the primary key, which only authorized the T6 review action. The
key-binding-first pipeline therefore correctly derived `untrusted` before the
case could exercise the intended `out_of_scope` stage.

Before any passing result, registry version `2026-07-16.2` added a same-owner,
same-policy public-test key bound to `memory_write`; the case selected that key
and was re-signed. The expected state, counts, pipeline order, and authority
boundaries did not change. The design and preregistration record the erratum and
the final hashes above identify the corrected freeze.

## Derived Distribution

| State | Count |
|---|---:|
| verified | 4 |
| invalid | 4 |
| untrusted | 3 |
| revoked | 2 |
| stale | 4 |
| replayed | 1 |
| out_of_scope | 8 |
| unavailable | 1 |
| total | 27 |

Signature verification was attempted 21 times: 19 succeeded and 2 failed.
Malformed Base64, invalid signature length, unavailable verification, unknown
keys, structural failures, and trust-binding failures fail closed before a
signature attempt where appropriate.

## Verification Matrix

- S3 focused tests: 7 passed, 0 failed.
- S2 adjacent tests: 6 passed, 0 failed.
- S1 adjacent tests: 4 passed, 0 failed.
- S0 adjacent tests: 4 passed, 0 failed.
- `cargo check -p ab-bridge --all-targets --quiet`: exit 0, including the
  pre-commit hook on the exact staged implementation.
- two S3 report runs: byte-identical, both with SHA-256 `0aa7604a...`.
- JSON parsing and embedded source/hash pin checks: passed.
- `git diff --cached --check`: passed before the implementation commit.

Existing repository warnings remained: mixed-script test naming, dead code,
and the pre-existing `ToolPolicy` visibility warning. S3 introduced no new
warning.

## Explicit Nonclaims

Every report keeps all authority fields false. In particular, S3 does not:

- dispatch or run shadow work;
- enable runtime or an executor;
- write memory, graph, session, retrieval, or replay state;
- consume receipts from MCP or T6 runtime paths;
- prove a production trust root or production authority;
- deploy, merge to master, or grant authority.

`receipt_usable_for_later_owner_review` is true only for the four verified
controls. It is review evidence, not an admission or execution decision.

## Next Gate

Any S4 work must be separately authorized and preregistered. The useful next
question is trust-root lifecycle and atomic replay-state design under a pure
read-only interface. Production credentials, live mutation, runtime
consumption, shadow/executor enablement, deployment, and master merge remain
outside this result.
