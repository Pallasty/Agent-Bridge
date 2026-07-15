# BioCortex Track B external atomic live-output boundary v1

## Technical summary

The external atomic live-output execution boundary is now preregistered as a
closed **design contract**, not implemented as a production runtime. The v1
packet separates 48 pre-linearization request identity bindings from 16
derived or provider-committed result fields, excludes `OPERATION_ID` from its
own derivation, binds the local guard receipt as non-authorizing evidence, and
defines one exact operation/slot/logical-sink/physical-sink/executor grain.

The only admissible decision is
`DESIGN_CONTRACT_PASS_BLOCKED_FAIL_CLOSED_PRODUCTION_PREREQUISITES_UNBOUND_OR_UNVERIFIED`.
In the fixed source-profile snapshot observed at `2026-07-15T15:00:00Z`, and
within its qualified repository and current-process/host non-secret audit
scope, all 18 production prerequisites remain unbound or unverified. External
organization state was not observed, host visibility is not complete, no
secret value was inspected, and no provider, KMS, generator, or physical sink
was called. The receipt is not an output permit; no capability or permit is
defined or emitted, condition output remains unauthorized, and side effects
remain `NONE`.

## Key findings

The following is a same-grain Boolean status view. Values are facts about this
packet, not percentages, coverage estimates, or production readiness scores.

| Boundary fact | Value | Evidence meaning |
|---|---:|---|
| Closed request/result envelopes frozen | true | 48 request identity bindings and 16 result bindings are exact |
| Non-self-referential operation ID rule frozen | true | `OPERATION_ID` is excluded from its own hash inputs |
| Authority/sink/fence state-vector machine frozen | true | 7 authority states, 4 physical-sink output states, 2 terminal-fence states, 13 separately linearized transitions, and 16 closed terminal vectors |
| Crash protocol frozen | true | 11 cuts bind durable pre-state, lookup outcome, next state, no reissue/reinvoke, and visibility |
| Production-prerequisite schema frozen | true | 18 one-to-one rows are required |
| Production provider bound and verified | false | no authenticated provider binding receipt |
| Owner trust pin verified | false | no independent owner handoff receipt |
| Custodian trust pin verified | false | no independent custodian handoff receipt |
| External linearizable authorize/consume/logical-sink reservation verified | false | no authority-database transaction receipt |
| Trusted currentness at use verified | false | no signed currentness receipt |
| Anti-rollback witness verified | false | no independent monotonic checkpoint |
| Global single use verified | false | no external uniqueness/replay-consume evidence |
| Private single-use capability verified | false | no runtime/protocol attestation |
| All generator paths guarded | false | no non-bypassable loaded-runtime proof |
| Guard-owned physical sink verified | false | no sink ownership attestation |
| First-byte CAS and durability verified | false | no physical-sink linearization receipt |
| Loaded runtime attested | false | no executor/model/sink measurement |
| Independent fault evidence verified | false | no split-brain/rollback experiment receipt |
| Operational crash-cut evidence verified | false | the matrix is preregistered but not executed against a provider |
| Production execution runtime verified | false | no production adapter or loaded-runtime evidence |
| Live-output permit defined | false | design receipt cannot authorize output |
| Live-output capability emitted | false | no runtime capability was constructed or delivered |
| Condition output authorized | false | fail-closed boundary remains active |
| Receipt is output permit | false | the deterministic receipt is non-authorizing |
| Side effects unlocked | NONE | no provider, generator, KMS, or sink operation was unlocked |

The two-domain state model fixes the ambiguity found during red-team review. A generator
cannot start from `START_COMMITTED`; it first requires a durable
`GENERATOR_START_COMMITTED` transition that consumes the private capability.
A crash before that transition can burn the attempt empty. Once generator
start is committed, an unproven zero-byte result is quarantined as ambiguous.
Authority state, physical-sink output state, and the sink-local terminal fence
form the preregistered recovery vector but are never claimed to share a
transaction or global CAS. The authority transition leaves physical-sink state
unchanged; a separate sink-domain absent-record CAS must create `(EMPTY,OPEN)`
for the exact reserved operation and slot. Under the required same-record,
linearizable-CAS semantics, a conforming implementation must make first-byte,
append, seal, and terminal-fence mutations compare and update that same sink
record revision. Installing a terminal fence over an absent record is a
separate CAS-create transition to `(EMPTY,TERMINAL_AUTHORITY_FENCED)`; installing
it over an existing record preserves the output state and updates that record
in place. A conforming write must therefore either linearize before the
terminal fence and appear in the post-fence strong read, or linearize afterward
and fail. None of those runtime semantics has been operationally verified here.

Terminal authority state is absorbing and dominates every later sink state.
The contract freezes all 4 × 4 terminal-authority/sink-output combinations.
In particular, `(AMBIGUOUS_QUARANTINED,FIRST_BYTE_COMMITTED)` and
`(PARTIAL_QUARANTINED,SEALED)` preserve their authority terminal, install or
confirm the sink-local fence, strong-reread at or after the fence revision, and
remain permanently reviewer-invisible. Only
`(SEALED_OBSERVED,SEALED)` may proceed to the separate post-generation map
gate. Provider/sink rollback or split-brain uses a separate irreversible
incident-quarantine overlay instead of rewriting a terminal state.

The authority transaction is deliberately narrow: it atomically checks
currentness/revocation, consumes the operation/challenge/replay identity, and
reserves/binds a **logical** sink slot in one authority database transaction.
It does not claim a common transaction across the authority database, KMS, and
physical output sink. First-byte durability is a later, separately fenced
physical-sink CAS.

Nine closed result/request constraints join the two envelopes: provider
incarnation and authority epoch must equal their expected values; term and
revision must meet their request floors; signer key version must match the
explicit nonzero requested version; conforming signature verification must use
the pinned public key and exact KMS resource; request digest, operation ID, and sink identity
must match their exact request derivations or commitments. The contract also
requires a closed 14-field authority-decision payload containing operation and
request identity, authority epoch/term/revision/sequence/state, currentness,
anti-rollback, logical-sink reservation/fence, actual sink identity, and actual
signer key version. `AUTHORITY_DECISION_SHA256` must equal SHA-256 of its exact
canonical bytes; that digest and `SIGNATURE_RECEIPT_SHA256` are excluded from
the payload to avoid a cycle. The embedded request digest must resolve to and
revalidate the exact closed 48-field request envelope, including the sink slot
and independent pins. Excluding only the decision digest and signature-receipt
digest, the final result envelope must contain exactly those 14 payload fields,
with every value byte-equal to the signed payload value. Its 890-byte
canonicalization KAT hashes to
`1a615a23…87db3`.

A conforming result must carry an immutable `SIGNATURE_RECEIPT_SHA256`, not
merely a signature digest. Its closed referenced receipt must contain
`SIGNED_MESSAGE_SHA256`, 64 decoded
Ed25519 signature bytes, KMS resource/version, public-key pin, response name,
CRC checks, algorithm, and protection level. The exact versioned resource and
response name must be byte-equal, and the public-key hash must cover the exact
raw 32-byte RFC 8032 verification key extracted by strict PEM→DER SPKI parsing
for the Ed25519 OID with absent parameters. The receipt content hash uses the
same restricted RFC 8785-compatible canonical JSON profile, rejects duplicate
keys before canonicalization, and is bounded to 65,536 canonical bytes. The
required pure-Ed25519 message is
unique: 93 exact ASCII domain bytes, a four-byte big-endian domain length, an
eight-byte big-endian payload length, and the raw 32 bytes obtained by strict
lower-hex decoding of `AUTHORITY_DECISION_SHA256`—137 bytes total. A conforming
signer must receive those exact framed bytes as provider `data`, not ASCII hex,
JSON, a provider digest slot, Ed25519ph, or a second hash. The frozen
signature-message framing KAT binds only those message bytes and their SHA-256;
it is not an Ed25519 signature, cryptographic, or KMS KAT. A conforming
same-domain CAS conflict must cause a strong reread and application of the
state-vector mapping, never an overwrite.

## Scope, data, and definitions

This packet's frozen preregistration baseline is
`1de35708f92beaae35bfb4b16ab25292f343cfd1`,
an explicit repair merge of the then-current `master` and the verified S12
dual-mode integration. Its tree is byte-identical to the certified S12
integration `f4ff82721caa3537e1e0ba2d7682017e09427858`; the latter has source
commit `611a10fb4133e6aa58ef76b6d02744b3a90fe09c` as its second parent.
The full S12 gate was actually replayed and emitted
`VALID_INTEGRATED_BIOCORTEX_AB_TRACK_B_RECOVERED_S9_DECISION_REVERIFICATION_S12`,
`gate=PASS`, `mode=integrated`, and the exact source/head bindings. The old
guard gate remains unchanged and is replayed on S12's first-parent historical
tree; successor seam changes are checked separately rather than weakening the
historical manifest.

“Unbound or unverified” means that this packet has no authenticated evidence
receipt for the named prerequisite inside the stated audit scope. It does not
mean that the provider or configuration is absent throughout the organization
or on every host. `caller_supplied_identity_digest_shapes_validated=true`
means only that the pure builder accepted nonzero SHA-256-shaped values. The
builder fixes `on_disk_artifact_identity_verified=false`; the outer checker
separately hashes the bytes it reads and joins them to the manifest. Neither
claim is loaded-code attestation.

## Method

The pure standard-library source reconstructs the exact contract and source
observation and rejects any byte or semantic drift. The outer checker:

1. requires canonical JSON with duplicate-key rejection and closed Draft
   2020-12 schemas;
2. checks the exact baseline, predecessor commits, provider-research rows, and
   on-disk evidence hashes;
3. statically restricts the pure source to a small standard-library import set
   and rejects filesystem-write, subprocess, network, and provider-style calls;
4. builds the receipt twice and requires byte identity; `--self-test` repeats
   the complete evaluation and compares the two full outputs;
5. executes 414 directed **single-field structural-drift** negative tests over request/result
   envelopes, prerequisites, invariants, transitions, crash rows, research
   sources, authority-decision and signature-message framing KATs, all 16
   terminal vectors, sink-fence rules, observation scope, receipt truth values,
   and canonical-input resource limits. Most contract mutations are rejected
   first by exact closed-contract equality; they are not 414 independent
   semantic, security, concurrency, fault, or cryptographic tests.

The structural oracle does not simulate a transaction, network partition,
leader failover, snapshot restore, KMS ambiguity, generator crash, or sink
write. Those remain production evidence gaps.

## Provider-reference research

The managed reference track is Google Cloud Spanner plus Cloud KMS/HSM.
Spanner read-write transactions using the default `SERIALIZABLE` isolation
provide external consistency, and clients can automatically retry transaction
functions; the harness must explicitly pin and assert `SERIALIZABLE`, reject
optional repeatable-read isolation, and perform no KMS, generator, or physical
sink side effect inside a retryable transaction closure. Cloud KMS supports
Ed25519 signing at an exact `CryptoKeyVersion` resource and request/response
integrity fields. The harness must use raw `data`, check the response `name`,
`verifiedDataCrc32c`, and `signatureCrc32c`, and additionally verify
`protectionLevel` before making an HSM-specific claim. These facts
support a managed semantics/client-conformance experiment; they do not create
a database/KMS/sink common transaction or a production deployment.
[Spanner transactions](https://docs.cloud.google.com/spanner/docs/transactions),
[external consistency](https://docs.cloud.google.com/spanner/docs/true-time-external-consistency),
[Cloud KMS algorithms](https://docs.cloud.google.com/kms/docs/algorithms),
[asymmetricSign](https://docs.cloud.google.com/kms/docs/reference/rest/v1/projects.locations.keyRings.cryptoKeys.cryptoKeyVersions/asymmetricSign),
[data-integrity guidance](https://docs.cloud.google.com/kms/docs/data-integrity-guidelines).

The self-hosted adversarial track is etcd plus OpenBao Transit. etcd KV
operations are strictly serializable and reads are linearizable by default,
but an explicit serializable read may be stale; snapshot recovery also
requires careful revision handling. The production-candidate path must reject
stale reads and nested etcd transactions, while a stale read may appear only
as an adversarial negative. OpenBao Transit supports Ed25519 and an explicit
signing key version, while version `0` means “latest” and is therefore
inadmissible for this experiment. This track can expose partition, leader,
ack-loss, restore, seal, and rotation failure modes, but it cannot prove
production externality, HSM custody, or Spanner behavior.
[etcd API guarantees](https://etcd.io/docs/v3.6/learning/api_guarantees/),
[etcd recovery](https://etcd.io/docs/v3.6/op-guide/recovery/),
[OpenBao Transit](https://openbao.org/docs/secrets/transit/),
[OpenBao Transit API](https://openbao.org/api-docs/secret/transit/).
The packet records exact URLs and a human-reported retrieval date of
2026-07-15; it does not attest webpage contents or hashes. The pages must be
refetched and their claims reverified before an experiment is executed.

## Limitations and robustness

- The audit does not observe external organization state and does not claim
  complete host visibility.
- All 18 production evidence digests are null; every corresponding verification
  is false.
- No credential value, provider configuration secret, production KMS key,
  generator, or physical sink was accessed.
- The design does not provide end-to-end exactly-once output. It preregisters a
  fail-closed protocol for proving or quarantining each ambiguous attempt.
- The terminal-fence transitions and 16-vector closure are design-only; they
  have not been executed against a real sink or crash-injection harness.
- The 890-byte authority-decision transcript KAT verifies canonicalization and
  SHA-256 framing only. The 137-byte signature-message framing KAT verifies
  domain/length/raw-digest framing and SHA-256 only; neither verifies an
  Ed25519 signature, public-key operation, base64url/CRC behavior, or KMS.
- The managed and self-hosted tracks answer different questions and cannot
  certify one another or act as winner/loser alternatives.
- Source-profile PASS is not admission, runtime safety, production readiness,
  an output permit, or authority to provision paid resources.
- Future host or external state is not automatically re-audited, and the host
  Rust toolchain bytes are not packet-attested. Gate toolchain and temporary
  parent paths remain non-adversarial local-host trust assumptions; the gate
  checks executable presence plus temp-directory owner/mode/symlink shape but
  does not establish hostile-local-user resistance.

## Recommended next steps

Proceed to
`REFERENCE_PROVIDER_MANAGED_AND_SELF_HOSTED_FAULT_INJECTION_EXPERIMENT_V1_PREREGISTRATION`
as two non-authorizing tracks:

1. Freeze a managed Spanner+KMS client-conformance harness that explicitly
   pins/asserts `SERIALIZABLE`, prohibits all external side effects inside
   retryable Spanner transaction closures, and signs only the exact 137-byte
   framed message reconstructed from a committed authority-decision digest at
   an exact key version with the KMS integrity checks listed above.
2. Freeze an etcd+OpenBao adversarial harness whose candidate path disables
   stale reads and nested transactions, requires explicit nonzero Transit key
   versions, and preregisters partition, failover, ack-loss, restore/revision,
   seal, and sign-observed/persist-failed cuts.
3. Keep credentials, provider provisioning, costs, production adapters, live
   generators, and live sinks out of scope until independent owner and
   custodian authority is authenticated and bound to this experiment.

Neither track may issue a live-output permit. Promotion requires authenticated
evidence for all 18 rows and a new independently reviewed production profile.

## Further questions

- Which logical sink-slot reservation model can be expressed entirely inside
  the selected authority database transaction?
- What independent monotonic witness remains trustworthy across provider
  restore, credential rotation, and regional failure?
- Which runtime isolation mechanism can prove that no stdout, log, callback,
  subprocess, or direct-model path bypasses the guard-owned sink?
- What exact operator and custodian handoffs are required before any paid or
  credentialed managed experiment is authorized?

## Artifact binding

- `docs/design/fixtures/biocortex-ab-track-b-external-atomic-live-output-boundary-design-receipt-schema-v1.json`: `cbb68b0c55e5504bfc6417280978d18c5228c353b1147a3d05b847edc2d3b99c`
- `docs/design/fixtures/biocortex-ab-track-b-external-atomic-live-output-execution-boundary-contract-v1.json`: `9688c4df6ce4a8cf84539a400b488f2c108da606ab2a9eb22e459376bd525046`
- `docs/design/fixtures/biocortex-ab-track-b-production-provider-prerequisite-observation-source-profile-schema-v1.json`: `5a4d7d0f817de1a4fbf307508bd1d775bec31e683a2487440befedcfa0e1b342`
- `scripts/eval/biocortex_ab_track_b_external_atomic_live_output_boundary_v1.py`: `0eb1d6830c8594c4d265440b7fb4bff0ecb507916f59c4057a24eba6fc90cac4`
- `scripts/eval/check_biocortex_ab_track_b_external_atomic_live_output_boundary_v1_pack.py`: `491af79c141317536b141ff1eb4b93df322bd38bc840f1d15061e68e317fa0a8`
- `scripts/eval/fixtures/biocortex_ab_track_b_external_atomic_live_output_boundary_v1_pack_synthetic_v0.json`: `7ed9352834de04729188d931ebce7b28d01c709b22e78f074d80248dac9a23f2`
- `scripts/eval/fixtures/biocortex_ab_track_b_external_atomic_live_output_boundary_v1_pack.expected.v0.tsv`: `f5798073ff1c78a38f20a41723df2aac4bf3ef1b104792c1b8533bc275b93093`
- `scripts/eval/fixtures/biocortex_ab_track_b_external_atomic_live_output_boundary_v1_pack_v0.json`: `b2c101068f237912f79aef6e975a0336d46845d86070ab307945420c3c9e1e96`
- `scripts/eval/fixtures/biocortex_ab_track_b_first_condition_output_guard_v1_pack_v0.json`: `a7d8e5bf314b873b539211d5909427b0e26a8209bf8ef141096e39eb75b9e1a6`
- `docs/design/fixtures/biocortex-ab-track-b-recovered-s9-decision-reverification-s12-v0.json`: `4efa9dc533cfca6c98473ae20cf8fc983292362e92b669575a81e80e189b1303`
- `scripts/check-memory-temporal-recovered-s9-decision-reverification-s12.sh`: `df9d0d6a358262773dbed9a2d5ca8d0ba375476542399c2a829b39367afa42d5`
