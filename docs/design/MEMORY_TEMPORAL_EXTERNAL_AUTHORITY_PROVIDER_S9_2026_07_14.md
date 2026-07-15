# Memory Temporal External Authority Provider S9

Date: 2026-07-14

Decision: `BLOCKED_FAIL_CLOSED`

Status: `PROVIDER_NEUTRAL_ED25519_CURRENTNESS_AND_CUSTODY_CONTRACT_PREREGISTERED_NO_PROVIDER_NO_OWNER_TRUST_ANCHOR_NOT_AUTHORIZED_NOT_TRANSPORT`

## Outcome

S9 freezes a provider-neutral contract for the external currentness and key
custody dependencies that S8 could only simulate. Currentness verification is
executable while custody remains an opaque-identity/interface preregistration,
all behind the default-off feature
`temporal-evidence-s9-external-authority-provider-synthetic`, which depends on
`temporal-evidence-s8-restore-bound-key-epoch-synthetic`. The implementation is
private and uses only a deterministic test provider. There is no production
provider, network client, owner trust anchor, public constructor, `StateStore`
surface, Bridge forwarding, runtime influence, or transport authorization.

S9 changes the authentication shape from S8's synthetic shared HMAC to exact
Ed25519 verification under an owner-pinned public key. The only pin present in
the repository is a deterministic test pin. It is not an owner approval, a
production identity, or evidence that a signer is external to the rollback
domain. The production boundary therefore remains closed.

## Frozen predecessor

S9 is based on merge commit
`ad3500c831228b1f0e7e1ff2330c515aa997fa7b`. It preserves the S8 contract at
`039ec8237afa9b2ea3340918a2924f78f89223abbd4034d41c6d82a2e1519573`
and the S8 successor gate at
`c01e686d104392269d57c39a9a240b203016639c65f379f992e74d30248c5817`.
S9 does not edit the S8 verifier, its fixtures, or its fourteen-test evidence
surface. It does not migrate the S7 SQLite schema or attach an external check
to S8's local durable consume.

The S9 contract fixture is
`docs/design/fixtures/biocortex-ab-track-b-external-authority-provider-s9-v0.json`.
Its digest is
`d537b80ce0d2bbb3c4d01a988a9685432672078eae07d0b976b1268a27526fc4`.
The successor gate records that this contract is not an admission receipt.

## Two independent provider boundaries

S9 freezes two private interfaces. Keeping them independent prevents a
currentness provider's signed custody claim from satisfying the separate
key-custody boundary.

### `ExternalCurrentnessProvider`

The currentness provider accepts one fully bound request and returns either one
signed response or an explicit failure. A production implementation would have
to be outside the protected receiver, S7 sidecar, host, and backup domains. It
would also have to provide durable challenge uniqueness, linearizable
currentness, rollback resistance, split-brain fencing, and stable recovery
semantics. S9 supplies none of those operational properties; its implementation
is deterministic and test-only.

### `ExternalKeyCustodian`

The custodian boundary accepts only provider-scoped, opaque, immutable key
references. A reference identifies a provider cluster and incarnation, key
role, key ID, and immutable key version without carrying key bytes. S9's
custodian interface returns only an untrusted typed observation; it has no
custodian trust permit or signature verifier yet. A successor may add independently
signed custody evidence, but it must never accept, return, serialize, log, or
expose raw key material.

The two claim commitments are assertions by the currentness provider. A custody
commitment does not prove HSM or KMS custody. An old-key-use-denied commitment
does not prove cryptographic erasure, destruction of backup copies, or inability
to restore an earlier provider snapshot. Those claims require evidence from an
actual owner-approved KMS/HSM service and its operating controls.

## Exact request and response binding

The Ed25519-signed response is valid only when all of the following values are
encoded in the exact framed message and match the one current request:

- the S9 scope and trust-policy commitments;
- expected provider cluster and provider incarnation;
- provider leader term and monotonic revision;
- request ID, exact request digest, and nonzero currentness challenge;
- active key epoch and exact S8 epoch-record digest;
- exact S7 registry generation;
- receiver-identity, build-identity, and allowlist commitments;
- the complete keyset commitment;
- signer ID, immutable signer version, and owner-pinned Ed25519 key identity;
- currentness-provider custody-claim commitment; and
- currentness-provider old-key-use-denied claim commitment.

The request digest commits to the entire canonical typed request, not a selected
subset. Field substitution, provider identity changes, signer-version changes,
and signature or public-key changes fail closed. S9 has no wire parser; a later
network adapter must separately reject omitted, reordered, duplicate, trailing,
truncated, and oversized encodings. A self-asserted key delivered in the signed
response cannot replace the owner pin.

Leader term and revision are evidence fields, not a repository-owned
monotonicity anchor. Signing them prevents undetected byte substitution. It
does not show that a provider issued only one history, that a term was durably
fenced, or that a revision was not rolled back.

## Owner-pinned Ed25519 verification

The verifier is configured with an exact 32-byte Ed25519 public key plus exact
provider, signer, and signer-version identities. It verifies a 64-byte
signature over the frozen framed response. The private signing key is not
present in non-test repository code.

A production pin must be supplied out of band by the authority owner. The
signed response cannot authorize its own key. Rotation requires a separately
approved new pin and immutable signer version; no in-band rollover or grace
set is preregistered. The deterministic test key and pin exist solely to make
framing, binding, rejection, and failure behavior reproducible.

Ed25519 establishes only that the exact bytes were signed by the holder of the
private key corresponding to the selected public key. It does not establish:

- where the signer runs or whether it shares the receiver's rollback domain;
- whether provider state is linearizable, durable, or single-leader;
- whether the signer is backed by a KMS or HSM;
- whether old signing or data keys were destroyed;
- whether the owner approved the signer; or
- whether the signed facts are true.

## Freshness and lease profile

S9 deliberately selects
`ONE_ATTEMPT_NO_CACHE_NO_WALL_CLOCK`:

1. one admission attempt creates one request with one nonzero challenge;
2. the verifier calls the provider at most once;
3. the result cannot be cached or reused for another attempt;
4. timeout, unavailability, or ambiguity causes failure rather than retry;
5. a later attempt requires a new request ID and challenge; and
6. no local wall-clock value, TTL, grace interval, or reusable lease is used.

Avoiding wall-clock leases removes clock-skew and stale-cache assumptions, but
does not itself prove freshness. A real provider must durably consume each
challenge or otherwise bind every response to a unique linearizable operation.
The test provider's uniqueness set is process-local and is lost when the test
provider is reconstructed. A caller or provider that reuses a challenge can
therefore replay an old response; S9 records this as unresolved rather than
describing the single-attempt profile as anti-replay.

There is no automatic retry with the same challenge. Retrying a request whose
outcome is unknown could turn a lost successful provider operation into an
ambiguous state. Higher-level recovery must first query an actual provider by
the immutable request identity, and such a recovery protocol is not supplied
by S9.

## Fail-closed state and error semantics

Only an exactly bound, correctly signed, current response under the exact owner
pin may produce the private test token. The following conditions return no
token and never fall back to S8 local-only admission:

- timeout, transport unavailability, cancellation, or provider error;
- lost or ambiguous result;
- a provider adapter reporting malformed response data;
- invalid Ed25519 signature or wrong pinned key;
- provider cluster, incarnation, signer, or signer-version mismatch;
- request ID, request digest, challenge, epoch, record, or S7 generation
  mismatch;
- receiver, build, allowlist, keyset, trust-policy, or provider-claim commitment
  mismatch;
- zero or invalid term, revision, epoch, generation, or challenge;
- pending, revoked, indeterminate, unknown, or otherwise non-current status;
  and
- arithmetic overflow or noncanonical encoding.

The provider contract has no production constructor. Its private test token is
not serializable, cloneable, transferable, or sufficient to call Bridge or
mutate `StateStore`.

## Properties intentionally not claimed

S9 binds the vocabulary needed by a future external dependency, but it does
not close any of the following system properties:

### Durable challenge uniqueness

The repository cannot see whether a provider persists consumed challenges
outside all rollback domains. Reconstructing the deterministic test provider
loses its in-memory burn history.

### Split-brain and provider rollback

A term and revision signed by two unfenced leaders can each be internally
valid. A signer restored with its private key can also sign an old state. S9
has no external quorum, compare-and-swap register, transparency log, monotonic
hardware counter, or retained highest-observed provider state.

### Provider rotation and clock behavior

Rotation is specified as out-of-band repinning but not operationally
implemented. S9 has no owner key ceremony, overlap policy, compromise
revocation channel, or rollback-safe signer-version register. It uses no wall
clock, so it neither depends on nor attests provider clock correctness.

### Same-epoch rollback and atomic consume

S9 does not integrate the provider contract with the S8 verifier. Even a future
implementation that checks currentness and then performs S7 local consume has
a revocation race between those operations. It is not atomic, exactly-once, or
instantaneously revocable. A sidecar restored within the same active epoch is
still undetected unless the concrete replay identity is atomically consumed by
a genuinely external linearizable authority.

### KMS custody and destruction

Opaque references prevent this interface from returning raw keys. They do not
prove that a production adapter obeys the interface, that keys never existed
elsewhere, or that an old version was destroyed. Currentness-provider custody
and old-key-use-denied commitments remain unverified claims and do not satisfy
the separate custodian boundary. That boundary remains interface-only until
backed by an independently authenticated, owner-approved service and verifier.

## Executable evidence boundary

The deterministic tests may establish exact Ed25519 framing and verification,
full-field substitution rejection, owner-pin and signer-version binding,
single-attempt/no-cache behavior, fail-closed provider results, opaque key
references, and deterministic test-provider challenge reuse behavior. Negative
tests may demonstrate provider reconstruction, split histories, stale signed
responses, and the absence of real custody.

Those tests exercise a provider contract. They cannot establish a production
provider's topology, external durability, linearizability, custody, revocation,
destruction, availability, or owner authorization. Historical S8 through S2
regressions and Store/Bridge default-off checks remain release gates.

## Unchanged admission boundary

The successor remains `NOT_ADMITTED`. S9 is not a new payload schema, a live
provider connection, or a cross-repository packet. It adds no BioCortex runtime
influence, async receiver, `StateStore` method, Bridge caller, network traffic,
side effect, or transport.

The original five blockers remain:

```text
AUTHORITY_POLICY_CUSTODY_UNRESOLVED
CAPTURE_PROVENANCE_UNATTESTED
CROSS_BIOCORTEX_OPAQUE_HANDLE_TRANSPORT_UNIMPLEMENTED
PHYSICAL_PRIVACY_DELETION_UNRESOLVED
PRODUCTION_PRODUCER_PROFILE_UNADMITTED
```

The five S8 operational gaps also remain:

```text
CURRENTNESS_CHALLENGE_UNIQUENESS_UNATTESTED
EXPECTED_EPOCH_CURRENTNESS_EXTERNAL_CUSTODY_UNATTESTED
INSTANT_REVOCATION_UNAVAILABLE_WITH_LOCAL_CONSUME
OLD_EPOCH_KEY_DESTRUCTION_UNATTESTED
SAME_EPOCH_RESTORE_DETECTION_UNAVAILABLE
```

S9 adds the following provider-operational gaps:

```text
DURABLE_CHALLENGE_UNIQUENESS_UNAVAILABLE
EXTERNAL_AUTHORITY_PROVIDER_UNIMPLEMENTED
EXTERNAL_KEY_CUSTODIAN_UNIMPLEMENTED
OWNER_PINNED_TRUST_ANCHOR_UNAVAILABLE
PROVIDER_CLOCK_AND_FRESHNESS_UNATTESTED
PROVIDER_FAILURE_RESULT_AMBIGUITY_UNRESOLVED
PROVIDER_KEY_ROTATION_AND_REVOCATION_UNATTESTED
PROVIDER_LINEARIZABILITY_UNATTESTED
PROVIDER_SPLIT_BRAIN_FENCING_UNATTESTED
PROVIDER_STATE_ROLLBACK_UNATTESTED
```

## Next admissible step

Do not attach S9 to Bridge. The next tranche requires an owner-selected
currentness provider and key custodian, an independently delivered owner trust
pin, and evidence for durable unique challenges, linearizable term/revision
updates, split-brain fencing, provider rollback protection, signer rotation,
revocation, immutable key versions, and old-key-use denial. The adapter must
retain opaque references and must not expose raw keys.

If exactly-once or instantaneous revocation is required, the architecture must
also move concrete replay consumption into the same external linearizable
decision or introduce an equivalent atomic protocol. A remote currentness read
followed by local SQLite consume is insufficient. Until those dependencies and
receipts exist, the correct result remains `BLOCKED_FAIL_CLOSED`.
