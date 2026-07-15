# Memory Temporal External Operation Recovery S10

Date: 2026-07-14

Status:
`LOOKUP_ONLY_OPERATION_RECOVERY_PROTOCOL_PREREGISTERED_SYNTHETIC_JOURNAL_NO_PROVIDER_NO_OWNER_TRUST_ANCHOR_NOT_AUTHORIZED_NOT_TRANSPORT`

Decision: `BLOCKED_FAIL_CLOSED`

## Purpose

S9 deliberately left a timeout or lost response ambiguous. Repeating its
one-attempt currentness request could consume a challenge twice, create a
second decision, or confuse an operation that committed with one that never
ran. S10 freezes the narrower recovery protocol needed to query an already
submitted operation by exact identity.

The default-off Store feature is
`temporal-evidence-s10-operation-recovery-synthetic`. It depends on S9 and
adds one private sibling module. It has no network client, public export,
production permit constructor, production provider, `StateStore` method,
Bridge feature forwarding, Bridge caller, BioCortex runtime influence, or
transport.

S10 is a pre-adapter protocol experiment. It is not a claim that an external
journal exists or that crash recovery, exactly-once execution, provider
linearizability, rollback protection, or owner authorization is deployed.

## Frozen predecessor

S10 begins from the integrated S9 commit
`2e828d7b86444770c3ef3cd40ac17f26cac6fb0e`. The S9 contract, successor gate,
and Rust source remain byte-identical:

- S9 contract:
  `d537b80ce0d2bbb3c4d01a988a9685432672078eae07d0b976b1268a27526fc4`;
- S9 successor gate:
  `2181254b1e66444445734edb2f7dab70a85c0be5316d449f7152559d7e6428e5`;
- S9 Rust source:
  `dd92c2b064c1a4c1e5a4119777f1b5bf21a46d0fc9cb77656845f05e48655d9b`.

The machine-readable S10 contract is
`docs/design/fixtures/biocortex-ab-track-b-external-operation-recovery-s10-v0.json`.
The successor gate is
`docs/design/fixtures/biocortex-ab-track-b-successor-admission-gate-s10-v0.json`.

## Lookup-only protocol

The lookup key is the pair:

```text
operation_id + exact_s9_request_sha256
```

The query additionally binds a caller-supplied lookup challenge and the
expected provider profile, authority namespace, tenant, audience, provider
cluster and incarnation, and trust policy. The independently supplied permit,
not the query, pins the signer version and minimum observed term/revision
floors. S10 proves only that the challenge is nonzero. Its freshness and durable
uniqueness remain unattested. The challenge makes a signed lookup receipt
specific to that query value; it does not turn the observation into a lease.

The sealed lookup interface exposes only `lookup_operation`. It intentionally
has no submit, retry, mutate, activate, consume, or currentness method. In
particular:

- S10 never calls S9 `request_currentness`;
- `NOT_FOUND` never resubmits the operation;
- a new admission attempt requires a new S9 operation ID and challenge outside
  S10;
- repeating an exact lookup is contractually read-only and must not advance
  provider state; a future in-module adapter requires a separate side-effect
  and retry audit because the Rust trait alone cannot enforce that behavior;
- the same operation ID paired with a different S9 request digest is a
  conflict.

## Signed lookup receipt

The response is an exact length-framed Ed25519 message. It binds the query
digest, outcome, stored S9 request and decision digests, provider
cluster/incarnation, leader term, provider-asserted operation-commit revision, current
observed journal revision, journal generation and record sequence, result ID,
signer ID, and permit-pinned signer version. The result ID binds the asserted
operation-commit revision; the permit floor is checked against the distinct
observed journal revision. A valid signature authenticates the provider's
assertion but does not prove global immutability or detect signer equivocation.
Stability is therefore claimed only for the non-equivocating synthetic
sequence model; external lookup linearizability remains unattested.

Verification is ordered fail closed:

1. validate the independently supplied permit and exact query;
2. make one lookup call with no local fallback;
3. reject oversized or noncanonical response labels before framing them;
4. authenticate the complete response before interpreting its outcome or
   bindings;
5. require the authenticated response to bind the exact query;
6. require the pinned provider and signer identity and monotonic observed
   floors;
7. accept only an exact `COMMITTED` operation whose stored S9 request digest
   matches the query and whose decision/result-ID commitments are nonzero.

The only successful value is a private, non-serializable
`VerifiedExternalOperationRecoveryObservationV1`. It holds opaque digests and
monotonic metadata. It is explicitly not a currentness token or an admission
token and cannot be used by S8/S9, Bridge, or `StateStore`. S9 currently has no
detached verifier that can accept a retrieved decision without invoking
`request_currentness`, so S10 cannot reverify or resurrect that decision. A
successor must add a pure exact-decision verifier and a separately justified
currentness/consume protocol; it must never route recovery through a second
submission of the original S9 request.

## Outcomes and failures

The frozen outcomes are:

```text
COMMITTED
NOT_FOUND
PENDING
CONFLICT
INDETERMINATE
```

Only `COMMITTED` can produce the private recovery observation. Every other
outcome fails closed. Timeout, unavailable, unauthenticated, unauthorized,
stale, conflict, rate-limit, malformed, and indeterminate provider failures
also return no observation. There is no clock, TTL, receipt cache, offline
acceptance, or local S9 fallback.

## Synthetic journal evidence boundary

The test implementation uses a journal shared by reconstructed adapter objects
inside one process. It demonstrates only a sequence model:

- an adapter object can be discarded and reconstructed while the same shared
  journal returns the exact committed operation;
- repeated exact lookups with no intervening journal change return
  byte-identical signed content and do not mutate journal state;
- an unrelated journal revision advance may change the signed observed floor,
  but cannot change the operation-commit revision, stable result ID, record
  sequence, or stored decision digest;
- operation-ID/request-digest substitution is detected;
- destroying the journal makes the same operation indistinguishable from an
  operation that never executed.

That final case is required negative evidence. Process memory is not external
durability. Reconstructing an adapter is not a process crash, host loss, quorum
failure, snapshot restore, or disaster-recovery exercise. Consequently S10
does not close `PROVIDER_FAILURE_RESULT_AMBIGUITY_UNRESOLVED`,
`PROVIDER_LINEARIZABILITY_UNATTESTED`, or
`PROVIDER_STATE_ROLLBACK_UNATTESTED`.

A later signed `REVOKED` or other currentness state also cannot recall a
previously returned recovery observation. The observation never authorized use
in the first place. If policy permits another admission attempt after recovery
has resolved the original operation, that attempt must use a new S9 operation
ID and challenge outside S10; it is never an automatic retry.

## Reference provider research

No external resource is created in S10. The preferred production-validation
candidate for a later adapter is a dedicated authority service backed by
Google Cloud Spanner for the journal and an exact-version Google Cloud
KMS/Cloud HSM Ed25519 key for signing.

This choice is a research recommendation, not an owner trust pin or a deployed
provider. The relevant first-party properties are:

- Spanner read-write transactions are atomic and externally consistent, a
  stronger transaction property than linearizability
  ([transactions](https://docs.cloud.google.com/spanner/docs/transactions),
  [external consistency](https://docs.cloud.google.com/spanner/docs/true-time-external-consistency));
- Cloud KMS supports `EC_SIGN_ED25519`, and the asymmetric-sign API identifies
  the exact key version and returns integrity fields
  ([algorithms](https://docs.cloud.google.com/kms/docs/algorithms),
  [asymmetricSign](https://docs.cloud.google.com/kms/docs/reference/rest/v1/projects.locations.keyRings.cryptoKeys.cryptoKeyVersions/asymmetricSign));
- asymmetric rotation requires distributing a new public key and does not
  automatically disable older versions
  ([rotation](https://docs.cloud.google.com/kms/docs/key-rotation));
- disabling a key is not documented as instantaneous, while destruction is
  delayed and has a separate deletion timeline
  ([disable](https://docs.cloud.google.com/kms/docs/enable-disable),
  [destroy](https://docs.cloud.google.com/kms/docs/destroy-restore)).

The self-hosted experiment candidate is etcd 3.6 plus OpenBao Transit Ed25519.
It is useful for adapter and fault-injection work, but etcd snapshot restoration
can move revisions backward unless operators apply an estimated revision bump,
and the storage/key systems remain inside operator-controlled rollback domains
([etcd recovery](https://etcd.io/docs/v3.6/op-guide/recovery/),
[OpenBao Transit](https://openbao.org/docs/secrets/transit/)). It therefore
cannot unlock production admission.

Even the preferred managed candidate does not make the database transaction
and KMS signature one atomic cross-service commit, does not supply repository
owner approval, and does not prove host integrity, instantaneous revocation,
or immediate physical deletion. S10 preserves those gaps.

## Tests and falsifiers

The Rust suite covers one deterministic known-answer vector plus exact
committed recovery, absence of submit/currentness behavior, stable repeat
lookup, operation/request conflict, all query and signed-receipt substitutions,
wrong trust identity, every non-committed outcome, modeled provider failures,
adapter reconstruction with a shared journal, journal-loss ambiguity, later
revocation/consume vocabulary exclusion, distinct provider-asserted operation and
observed-journal revisions, and the zero-clock/cache/network/public-constructor
boundary. The signed-receipt substitution cases are re-signed with the test key
so post-authentication checks are exercised rather than merely failing at the
signature.

The independent Python checker recomputes the framed messages and RFC 8032
signature without `ring`, validates the fixtures and source surface, and emits
one deterministic TSV receipt. Its full-file Cargo and parent-module digests
make it a validator for the frozen S10 tree, not for a later successor tree
whose shared glue files must change. A successor gate must run this checker
against an archived S10 integration tree, then use its own checker to validate
the retained S10 semantic projection in the successor tree. The S10 gate also
reruns S9 through S2 and the Track B context-sampling compatibility checker
under the low-memory profile.

The experiment is falsified if any path can submit or retry S9 currentness,
produce a public/serializable/admission token, accept `NOT_FOUND` or ambiguous
results, use an unpinned response key, mutate the journal during lookup, add a
network/Bridge/`StateStore` surface, or describe shared process memory as
external durability.

## Unchanged admission boundary

The successor remains `NOT_ADMITTED`; every external admission and durability
receipt is null. S9's five original gaps and fifteen operational gaps remain.
S10 adds four explicit recovery gaps:

```text
RECOVERY_JOURNAL_EXTERNAL_DURABILITY_UNATTESTED
RECOVERY_LOOKUP_LINEARIZABILITY_UNATTESTED
RECOVERY_OPERATION_SUBMISSION_ATOMICITY_UNIMPLEMENTED
RECOVERY_OBSERVATION_TO_S9_REVERIFICATION_UNIMPLEMENTED
```

No side effect is unlocked.

## Next admissible step

Do not attach S10 to Bridge. The next tranche may freeze the atomic authority
operation state machine: one external transaction must register the unique S9
operation/challenge, consume the concrete replay identity, decide exact bytes,
and retain a queryable outcome that is stable absent equivocation before an
exact-version custodian key signs it. Crash cut points must be exercised around transaction commit,
signing, signature persistence, and response delivery.

A production adapter still requires the owner to select and provision the
provider/custodian, deliver the provider public key and trust profile through
an independent channel, and supply real topology, durability, fencing,
rollback, rotation, revocation, and custody evidence. Until then the only
correct decision is `BLOCKED_FAIL_CLOSED`.
