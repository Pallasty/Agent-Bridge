# Agent Authority And Provenance Envelope S2 Result

Date: 2026-07-16

Status: PASS_STATIC_CONTRACT_ONLY / SYNTHETIC_ATTESTATION / NO_RUNTIME_AUTHORITY

## Result

The S2 static authority/provenance envelope and deterministic offline verifier
passed the preregistered fixture.

The result demonstrates that the contract can distinguish:

- claims bound to an evaluator-owned synthetic trusted receipt;
- malformed, forged, tampered, stale, replayed, out-of-scope, and unavailable
  receipts; and
- expected labels from independently derived verifier output.

It does not demonstrate real authentication or authorize T6.

## Lineage

- T6 source commit:
  a1c9469e9a14cd73159d34974f0e99714ce5a1f0
- S1 result commit:
  232cadaced8ac1ab6e18907d451fba9208d03079
- S2 protocol commit:
  8f1dce12c171135e354a8ddcc84b83e37d8dcc79
- S2 branch:
  codex/agent-compromise-authority-envelope-s2-20260716
- design board:
  thread 143, intent post 4517

The S2 branch starts at the S1 result and therefore preserves the S0 to S1 to
S2 evidence chain without rewriting prior hashes.

## TDD Evidence

The test skeleton was compiled before implementation. The RED run failed with
23 expected missing-item errors, including:

- Fixture and EmbeddedSources;
- VerificationStatus;
- load_fixture and embedded_sources;
- validate_fixture;
- canonical_claims_digest;
- evaluate_case and evaluate_suite.

After the minimal implementation, the same focused command passed all six
tests.

## Frozen Outcome

| Derived state | Count |
|---|---:|
| verified | 4 |
| invalid | 7 |
| stale | 2 |
| replayed | 1 |
| out_of_scope | 8 |
| unavailable | 1 |
| total | 23 |

Additional acceptance counters:

- trusted receipts: 22;
- false accepts: 0;
- control false rejects: 0;
- status mismatches: 0;
- reason mismatches: 0;
- all six verifier states represented: yes.

The four verified cases are inert controls. They only establish fixture-level
binding and clock-skew boundary behavior.

## Rejection Coverage

The seven invalid cases cover:

- unknown trusted receipt;
- forged synthetic attestation;
- presented/trusted canonical digest mismatch;
- untrusted issuer, principal, and verifier;
- unaccepted policy version;
- empty required decision-source digest;
- expiry not after issuance.

The remaining rejecting cases cover:

- expiry and future issuance outside skew;
- consumed nonce;
- action, target, scope, decision-source, session, resume, adapter, and
  evidence mismatch;
- independent verifier unavailability.

Reasons were derived and emitted in deterministic lexical order. Fixture
expected status and reasons were compared only after derivation.

## Canonical Binding

The checker domain-separates and length-prefixes a fixed ordered sequence of 20
claim fields. Strings and u64 timestamps use distinct type tags. The test suite
mutates each field independently and confirms every mutation changes the
canonical SHA-256 digest.

The checker separately computes:

- the trusted fixture receipt claims digest; and
- the Agent-presented claims digest.

Only equality permits later policy checks. A digest supplied by the Agent is
not used as authority.

## Hashes

- S2 fixture SHA-256:
  a51b545d91fceecf81ec03d5355a686e0728b6ab92130b9cfc75b9a1983cd82c
- deterministic report packet SHA-256:
  450a13f25802cba9da1700bee794c77f3c87d4f25fbfe3b34d8f2279571ccbf4
- S1 design SHA-256:
  0d9db25cc61bfe9ccd0f146b33a01ee033b5c5451784912419609c42fad5954d
- S1 mapping SHA-256:
  a08d3faf25b82fd84f5f0e27bba55485a6b3f9d3e00a9f22413eb9a971b37c8e
- S1 result SHA-256:
  8747ef00325852bdec3098565ca92c85000a8705e57a35e8381455ce8e98203e

Two post-commit report packets compared byte-for-byte equal and had the same
packet hash.

## Verification

Passed locally:

    cargo test -p ab-bridge --no-default-features
      --example agent_authority_provenance_envelope_s2 -- --nocapture
      6 passed; 0 failed

    cargo test -p ab-bridge --no-default-features
      --example agent_compromise_resilience_s1_mapping -- --nocapture
      4 passed; 0 failed

    cargo test -p ab-bridge --no-default-features
      --example agent_compromise_resilience_eval -- --nocapture
      4 passed; 0 failed

    cargo check -p ab-bridge --all-targets --quiet
      passed

Also passed:

- pre-commit all-target check on protocol commit 8f1dce12;
- rustfmt check for the S2 checker;
- JSON syntax parse for the fixture;
- staged diff check;
- exact-commit focused rerun;
- double-run byte comparison and SHA-256 recomputation.

The build emitted existing repository warnings in store and mcp_tools sources.
No warning pointed to the S2 example.

## Authority Boundary

Every report authority field is false:

- dispatch;
- shadow execution;
- runtime enablement;
- memory and graph writes;
- retrieval and session changes;
- cryptographic authenticity proof;
- production authority grant.

The synthetic attestation token is only an offline stand-in for successful
external receipt lookup. Because the trusted registry and presented cases are
co-located in a fixture, this stage cannot prove protection against an attacker
who can modify the evaluator trust root itself.

No credentials, keys, signatures, network verifier, replay database, T6/MCP
consumer, live state mutation, shadow execution, runtime enablement, deployment,
master merge, or production-security claim occurred.

## Next Admissible Gate

A later S3 may design and falsify the production trust-root boundary:

- authenticated issuer/principal source;
- real signature or equivalent verifier receipt;
- protected policy and target/scope registry;
- durable nonce/replay semantics;
- verifier availability and revocation behavior;
- a read-only T6 receipt-consumption preview.

Real credentials, runtime integration, or deployment remain separate
high-side-effect decisions and were not started by S2.
