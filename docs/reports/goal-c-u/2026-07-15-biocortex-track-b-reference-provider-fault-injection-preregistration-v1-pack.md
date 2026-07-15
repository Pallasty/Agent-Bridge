# BioCortex Track B reference-provider fault-injection experiment v1 preregistration

## Technical summary

The managed and self-hosted reference-provider experiments are now frozen as
one closed, non-authorizing preregistration. The packet defines 34 fault cases,
34 protocol invariants, 30 retained repetitions per case, and therefore 1,020
future run rows. **No run row exists today.** No credential was accessed, no
paid or laboratory resource was provisioned, no provider was called, and no
output permit, condition-output authorization, generator, or sink capability
was created.

The two tracks answer different questions. The managed track uses Google Cloud
Spanner and exact-version Cloud KMS to test client conformance against managed
serializable and signing semantics. The self-hosted track uses etcd 3.6 and
OpenBao Transit to expose partition, leader, acknowledgment, restore, seal,
rotation, and sign-observed/persist-failed behavior in an owned adversarial
lab. Neither track can certify, rank, or substitute for the other.

The packet decision is
`PREREGISTRATION_PASS_EXECUTION_BLOCKED_NO_AUTHORITY_OR_RUN_EVIDENCE`. “Pass”
applies only to the closed plan and deterministic structural oracle. It is not
provider evidence, runtime safety, production readiness, an expenditure
decision, or permission to start either experiment.

## The plan is complete; execution evidence is deliberately absent

The counts below are plan cardinalities, not completed samples, success rates,
or readiness scores.

| Track | Frozen question | Cases | Repetitions per case | Planned rows | Current rows | Evidence locus split |
|---|---|---:|---:|---:|---:|---|
| Managed Spanner + Cloud KMS | Does the client conform to the frozen protocol while using managed serializable and exact-version signing semantics? | 16 | 30 | 480 | 0 | 9 client-double cases; 7 managed-service/proxy cases |
| Self-hosted etcd + OpenBao | Does the protocol fail closed and recover deterministically under owned adversarial faults? | 18 | 30 | 540 | 0 | 5 client-double cases; 13 owned-lab cases |
| Total | No cross-track winner or pooled inference | 34 | 30 | 1,020 | 0 | Evidence remains separated by locus and track |

The contract binds 16 current official-documentation claims and 34 design
invariants. The checker executes 546 directed structural and frozen-semantic
mutations. Most of those mutations change one closed field and are rejected by
shape, identity, or exact semantic checks; they are not 546 independent provider,
concurrency, security, cryptographic, or fault-injection experiments.

## Scope, data, and metric definitions

The frozen baseline is integration commit
`3ca858bd6f0097dd0f7f928e7acb4aef030a47a2`, whose second parent for the
predecessor packet is source commit
`3054ffe692e2e8f4edf22bda86fcbe4c9e1077d2`. The predecessor manifest's exact
next-unit marker is this preregistration.

- **Track** is one non-equivalent provider question and claim ceiling.
- **Case** is one frozen control, negative-conformance condition, or fault cut
  with an allowed categorical result and forbidden claims.
- **Repetition** is one fresh namespace, configuration hash, assignment, and
  retained outcome. Thirty balanced blocks are planned per track.
- **Run row** is the future unit
  `(track_id, case_id, repetition_index)`. A planned row is not an observed row.
- **Evidence locus** says whether evidence comes from a local client double, a
  managed service plus a client-side fault proxy, or an owned self-hosted lab.
  Client-double evidence cannot prove provider behavior.
- **Conformance result** is categorical. No effect-size, failure-rate,
  reliability, superiority, or causal inference is preregistered.
- **Plan pass** means the plan is closed, deterministic, source-bound, and
  internally consistent. It never means that a case passed at runtime.

Every future run must bind assignment, configuration, provider profile,
pre-state, post-state, raw observation, and optional provider receipt by
SHA-256. Assignment must exist before candidate start, and the injection must
be armed after assignment but before candidate start. Control failures,
timeouts, infrastructure failures, safety stops, and aborted rows remain in
the denominator; post-outcome exclusion is forbidden.

## Managed track freezes a database outbox and a post-commit signer

The managed design is a three-stage state machine, not a distributed transaction
between Spanner and Cloud KMS:

1. An explicitly requested and asserted `SERIALIZABLE` Spanner read-write
   transaction checks authority, consumes the exact operation/challenge, binds
   a logical sink slot, and writes a durable `SIGN_PENDING` outbox row.
2. A worker CAS-claims that row as `SIGN_ATTEMPT_PREPARED`, durably binding the
   operation ID, canonical request digest, exact key version, public-key pin,
   message hash, and attempt sequence before any application-level KMS call.
   Each marker is single-consumption at the application boundary, and hidden
   provider retries are forbidden.
3. Only after confirming the prepared record may the worker call the exact
   nonzero `CryptoKeyVersion`, fully validate the response, verify Ed25519
   locally, and CAS the operation to one accepted durable receipt. A lost
   response or unresolved persist becomes durably `AMBIGUOUS_QUARANTINED`;
   restart may recover an exact receipt but may never re-sign or output from a
   prepared, ambiguous, or unresolved state.

The retryable transaction closure may contain Spanner reads and writes only.
KMS, generator, physical sink, filesystem, subprocess, network, semantically
meaningful logs, clocks, and randomness cannot occur inside it. All
nondeterministic inputs are captured once before the closure. If a transaction
attempt is retried, the same operation identity and precaptured inputs are
used and every closure attempt is counted.

The managed cases freeze these cuts:

| IDs | Fault family | Required disposition |
|---|---|---|
| M00 | clean serializable commit plus exact sign | conforming observation only within the managed claim ceiling |
| M01 | definite database abort | database-only retry of the pure closure; this is not strong-readback recovery |
| M04 | commit-response loss before or after resolution | exact record, or same-operation absent-to-terminal-fence transaction plus confirming strong read; bare absence is not terminal |
| M02, M03 | closure side effect and non-serializable isolation | reject before any provider-side effect |
| M05-M11 | digest-slot, message, raw-vs-Base64 CRC, version-resource, protection-level, and signature mutations | deterministic subcuts fail closed before durable receipt acceptance |
| M12, M13 | KMS response loss and sign-observed/receipt-persist-failed followed by restart | terminal durable ambiguity or exact receipt recovery; restart adds no application sign call and emits no output |
| M14 | two workers race on one outbox row | one prepared-attempt owner, one application KMS call, and one accepted durable receipt; no inference of one provider processing event |
| M15 | crash after outbox READY commit but before attempt CAS and KMS | recover without reauthorizing or re-consuming the challenge |

### Managed evidence layering

Official Spanner documentation directly states that serializable is the default,
read-write transactions are externally consistent, client transaction logic
can be retried, and side effects outside Spanner can therefore repeat. A
commit deadline can also expire even when the transaction may already have
committed. Requiring exact readback, a same-operation terminal fence for a
bare absent read, durable outbox/attempt transitions, and restart no-resign is
our design inference. These rules do not extend
Spanner atomicity to KMS or a physical sink. [Spanner transactions](https://docs.cloud.google.com/spanner/docs/transactions),
[external consistency](https://docs.cloud.google.com/spanner/docs/true-time-external-consistency),
[transaction timeout](https://docs.cloud.google.com/spanner/docs/transaction-timeout).

For `EC_SIGN_ED25519`, Cloud KMS directly documents PureEdDSA over raw data.
The exact frame is inherited by predecessor path and JSON pointer, predecessor
contract SHA-256, expected 137-byte length, and KAT message SHA-256
`f5dcb16eec00a302bf56c9cc681b5c09d598589c4c3e9ab2413b68c21f16982d`.
The harness must put the decoded 137 bytes in `data`, omit `digest` and
`digestCrc32c`, send
CRC32C over the raw data rather than its Base64 representation, and require
all of the following before accepting a receipt:

- `verifiedDataCrc32c == true`;
- locally recomputed CRC32C over raw signature bytes equals
  `signatureCrc32c`;
- response `name` is byte-equal to the requested exact version resource;
- response `protectionLevel` equals the preregistered expectation;
- version metadata has the pinned algorithm and enabled state; and
- the pinned exact-version public key verifies the signature over the exact
  137-byte message.

Wrong Castagnoli CRC32C over decoded raw bytes is expected to produce a
provider error; a successful response with `verifiedDataCrc32c=false` is a
separate negative subcut. Version-resource subcuts cycle deterministically by
repetition across omission, zero, parent resource, leading-zero noncanonical,
and response-name mismatch. The API fields and raw-data semantics are direct
facts. The local grammar, acceptance conjunction, attempt state machine, and
terminal ambiguity policy are fail-closed design choices. [Cloud KMS algorithms](https://docs.cloud.google.com/kms/docs/algorithms),
[asymmetricSign](https://docs.cloud.google.com/kms/docs/reference/rest/v1/projects.locations.keyRings.cryptoKeys.cryptoKeyVersions/asymmetricSign),
[CryptoKeyVersion](https://docs.cloud.google.com/kms/docs/reference/rest/v1/projects.locations.keyRings.cryptoKeys.cryptoKeyVersions),
[data-integrity guidance](https://docs.cloud.google.com/kms/docs/data-integrity-guidelines).

Before any managed call, the future execution profile must bind the client
library/build hash, retry and timeout configuration, database identity and
dialect, explicit isolation, exact key-version resource, public-key pin,
algorithm, enabled state, protection level, fault proxy, disabled hidden
provider retries, wire-attempt logging,
and separately authenticated owner, custodian, credential, resource, and cost
authority. `HSM` and `HSM_SINGLE_TENANT` are distinct enum values; acceptance
requires exact equality with the pinned expectation.

## Self-hosted track makes uncertainty and restore identity first-class

The candidate etcd path accepts only linearizable authority reads
(`RangeRequest.serializable=false`) and non-nested CAS transactions. It uses
the top-level transaction response revision, never a nested response revision
or Watch event, as transaction evidence. A timeout, EOF, network disruption,
or leader election produces `UNKNOWN`. Resolution has four closed branches:
an exact operation record resolves commit; a bare absent read resolves nothing;
a same-operation-key `ABSENT -> TERMINAL_FENCE` CAS winner followed by a
confirming linearizable read resolves a durably fenced absence; CAS conflict
requires another exact linearizable read. Blind mutation or Transit replay is
forbidden while the state is unresolved.

The self-hosted cases freeze these cuts:

| IDs | Fault family | Required disposition |
|---|---|---|
| S00-S03 | control, isolated follower, stale read, nested transaction | current quorum result or fail closed; stale and nested candidate paths are rejected |
| S04-S08 | leader unknown/post-commit loss, ACK loss, quorum loss, Watch lag | exact record or same-key terminal fence; bare absence and Watch never resolve ambiguity |
| S09-S11 | old snapshot, witness stale/fork/unavailable/conflict, reused identity, explicit rebase | invalid witness state is incident-quarantined; valid rebase needs verified snapshot, exact witness CAS, new identities, Watch invalidation, and full linearizable rebuild |
| S12 | active-node seal with HA takeover | distinguish target-node seal from service-wide failure; any successor response must pass the full exact-version verification path |
| S13-S14 | Transit response loss and sign-observed/etcd-persist-failed followed by restart | durable terminal ambiguity or exact receipt recovery; no re-sign, output, or one-call claim |
| S15-S17 | rotation, version zero, wrong prefix/key/message | accept only the pinned nonzero version or fail closed |

### Self-hosted evidence layering

etcd directly documents strict serializability for KV operations, possible stale results
for the optional serializable read mode, unspecified order for nested
transactions, non-linearizable Watch behavior, uncertainty after timeout or
network disruption, and restore-related revision rollback. Revision bump and
`mark-compacted` are recovery controls, not proof that writes after the
snapshot survived. etcd also directly describes restore as a new logical
cluster with rewritten member and cluster IDs. The independent witness is a
design inference frozen here as an abstract service outside the etcd snapshot
and restore-actor domain: current linearizable read plus exact
previous-record/generation CAS. Its record binds prior and new cluster and
incarnation IDs, revision floors, snapshot hash/revision, bump/compact flags,
rebase authorization, predecessor hash, and generation. Missing, unavailable,
stale, replayed, forked, mismatched, or conflicting witness state is incident
quarantined. Concrete witness product selection remains unbound. [etcd API guarantees](https://etcd.io/docs/v3.6/learning/api_guarantees/),
[etcd API](https://etcd.io/docs/v3.6/learning/api/),
[disaster recovery](https://etcd.io/docs/v3.6/op-guide/recovery/).

OpenBao directly documents Ed25519, Base64 input, an explicit signing `key_version`,
and the version-zero default meaning latest. The candidate path therefore
requires a non-derived, non-batch, context-free Ed25519 request with
`batch_input` and `context` absent, `key_version > 0`, `prehashed=false`, exact
137-byte decoded input, response version prefix equal
to the request, a pinned versioned public key, and local verification. Rotation
must never silently substitute latest. A sealed active node and overall HA
service availability are separate observations because an unsealed standby may
take over. Target-node `/sys/seal-status`, HA role, cluster/node identity,
request ID, redirect/forward, and audit evidence distinguish the routed node
from the node that processed a request. [OpenBao Transit](https://openbao.org/docs/secrets/transit/),
[Transit API](https://openbao.org/api-docs/secret/transit/),
[seal-status API](https://openbao.org/api-docs/system/seal-status/),
[high availability](https://openbao.org/docs/internals/high-availability/).

Before Transit, etcd must durably CAS the exact request bindings into
`SIGN_ATTEMPT_PREPARED`; each marker authorizes at most one application-level
Transit call. Only a fully validated response may CAS the operation
to `SIGN_RECEIPT_COMMITTED`. Persist uncertainty is resolved by exact
linearizable read or durable quarantine; etcd unavailability remains blocked,
and restart never reissues a prepared or ambiguous attempt. The conservative
cost is explicit: a crash after the prepared marker but before the wire call
may quarantine an attempt that the provider never saw.

The future self-hosted profile must bind etcd/OpenBao binary or image digests,
client versions and retries, full topology and resource caps, cluster/member
and node identities, snapshot hash/revision/restore parameters, independent
monotonic witness, Transit mount/key/version/public-key/minimum-version state,
fault-controller version, seed, monotonic clock, and every wire attempt and
redirect target.

## Methodology and falsification policy

For each track, repetitions 1 through 30 form balanced blocks. Within a block,
case order is the deterministic sort of
`SHA256(domain || track || repetition || case_id)`. Tracks may not interleave.
Each run receives a fresh namespace and a run ID derived from the frozen
domain, track, case, repetition, configuration hash, and assignment hash.

The primary result is the case's closed categorical classification. A case
passes only if all 30 retained rows are present and every row is in that
case's allowed set. Any of the following fails the entire applicable track:

- any permit or condition-output authorization;
- any unquarantined ambiguous operation;
- any duplicate or missing run key;
- any case with fewer than 30 retained rows;
- any exclusion chosen after observing an outcome;
- any external side effect inside a retryable Spanner closure;
- any candidate etcd stale read or nested transaction;
- any zero or implicit signing version;
- any cross-track certification or winner claim; or
- any resource use outside separately authenticated authority.

The pure standard-library builder validates the closed contract and the
zero-execution observation twice and requires byte-identical receipts. The
pre-execution schema deliberately permits exactly zero run rows; runtime row
shape, evidence-resolution joins, timestamp ordering, and cross-row uniqueness
belong to the named offline-harness unit. The outer checker rejects duplicate
JSON keys, requires canonical JSON, validates two closed Draft 2020-12 schemas,
restricts source imports and side-effect calls, verifies the predecessor
message KAT and evidence hashes, and runs 546 directed structural plus critical
frozen-semantic mutations under deterministic hash seeds in the Git gate.

## Data quality verdict: plan-safe, evidence-blocked

The intended use is to decide whether a separately authorized experiment may
classify each frozen fault case. It is not safe to infer provider behavior or
readiness from the current packet.

| Dimension | Current verdict | Severity / confidence | Execution-time remediation |
|---|---|---|---|
| Completeness | plan has all 34 cases; 0 of 1,020 run rows exist | blocking by design / high | require exactly 30 retained rows per case before any runtime result |
| Uniqueness | case, invariant, source, and planned run-key definitions are closed | execution not evaluated / high | reject duplicate track-case-repetition, run ID, or assignment hash |
| Validity | enums, nonzero-version rules, false permit fields, and plan counts validate | execution not evaluated / high | validate timestamps, hashes, evidence locus, result enum, and provider profile per row |
| Consistency | plan joins each case to allowed results, sources, and invariants | execution not evaluated / high | require row track/case/locus/configuration to match the frozen case |
| Referential integrity | all 16 source claims and all 34 invariants resolve and are exercised by the plan | execution not evaluated / high | require every raw/provider/pre/post hash to resolve to retained artifacts |
| Timeliness | official pages were manually refetched on 2026-07-15; content bytes are not packet-attested | material / high | refetch, review, and freeze page or upstream commit hashes plus SDK/API descriptors before execution |
| Assignment balance | 30 deterministic balanced blocks are specified | execution not evaluated / high | generate the sealed schedule before exposure and reject imbalance or substitution |
| Exposure order | assignment-before-start and arm-before-start are specified | execution not evaluated / high | retain monotonic timestamps proving assignment ≤ injection arm ≤ candidate start ≤ completion |

The current evidence is therefore safe only for preregistration. Experimental
completeness, duplicate assignment, imbalance, exposure-before-assignment,
provider profile consistency, and outcome classification remain
`NOT_EVALUATED_NO_RUN_ROWS`.

## Limitations, uncertainty, and robustness boundaries

- No external organization state, cloud account, key metadata, cluster,
  credential, provider response, process image, or network fault was observed.
- The official URLs and retrieval date are recorded, but page contents are not
  hashed or packet-attested. They must be reverified before execution.
- Google’s generic data-integrity page contains field-table wording that can
  differ from the current `asymmetricSign` schema; the experiment freezes the
  operation-specific REST schema as authoritative for signing fields.
- etcd's API overview and guarantees pages expose different detail around
  nested transactions; the candidate rejects decoded nested transactions
  rather than relying on one documentation rendering.
- A Spanner commit timestamp orders database work only. It is not a KMS or
  physical-sink timestamp and does not make those services atomic.
- One durable signature receipt does not prove one KMS/Transit RPC or one
  signature creation. Timeout, EOF, seal, or disconnect does not prove signing
  did not occur.
- A durable prepared marker intentionally chooses safety over availability: a
  crash after marker commit but before the provider call can cause conservative
  quarantine even when no provider processing occurred.
- OpenBao node seal is not equivalent to service-wide unavailability under HA.
- etcd revision is monotonic only inside a logical cluster incarnation.
  Revision bump does not restore lost writes or replace an independent witness.
- The 30-repetition rule is a strict conformance/falsification denominator, not
  a statistical power calculation or reliability estimate.
- Toolchain bytes and the external official pages are not attested by this
  packet. The Git gate treats the local host and its standard tools as a
  non-adversarial execution assumption.

## Recommended next step: implement only the offline doubles

Proceed to
`REFERENCE_PROVIDER_MANAGED_AND_SELF_HOSTED_FAULT_INJECTION_HARNESS_V1_OFFLINE_DOUBLE_IMPLEMENTATION`.
That unit should implement deterministic, no-network request builders,
response mutators, unknown-operation terminal-fence doubles, durable signing
attempt/restart state machines, an abstract restore-witness double, schedule
generation, runtime run-row validation, and exact 137-byte framing checks. It
must not add cloud or lab
credentials, provider provisioning, paid-resource operations, live adapters,
generators, sinks, or output permits.

After independent review of the offline harness, the self-hosted lab and the
managed service experiment should be authorized separately. The self-hosted
track needs explicit lab/resource/credential authority and an independent
restore witness. The managed track additionally needs authenticated
owner/custodian handoff, cloud resource and cost authority, exact account
preflight, and current SDK/API bindings.

## Further questions

- Which concrete service can satisfy the frozen out-of-restore-domain witness
  protocol and its linearizable CAS semantics without introducing a second
  rollback domain?
- Which supported managed fault mechanism can reproduce commit-response loss
  without confusing a client proxy result with a Spanner service guarantee?
- What operator workflow may inspect and retire a terminal ambiguity without
  ever making the prepared operation signable or output-eligible again?
- Which OpenBao client surface gives complete wire-attempt and redirect
  visibility with hidden retries disabled?
- What owner/custodian artifact binds the final resource, credential, cost,
  topology, and data-retention limits for each track?

## Artifact binding

- `docs/design/fixtures/biocortex-ab-track-b-reference-provider-fault-injection-preregistration-receipt-schema-v1.json`: `02968490ff213aca8a1f2ac6d766d7711caedd4b9c1ff030caf206cc2c3fb21e`
- `docs/design/fixtures/biocortex-ab-track-b-reference-provider-fault-injection-pre-execution-observation-schema-v1.json`: `28272f4aa3336be1d3239e33573065c5ecd746a16bc97c7710b0ae9a6c5b77b5`
- `docs/design/fixtures/biocortex-ab-track-b-reference-provider-fault-injection-experiment-contract-v1.json`: `632dbf1d8202d94d6aef70d8b20c04050e647679da973d81afbe13d68344ad22`
- `scripts/eval/biocortex_ab_track_b_reference_provider_fault_injection_preregistration_v1.py`: `1644a95f21144b28335ca107638245fcc605add4b0ba438dafb50fab6e65a1e0`
- `scripts/eval/check_biocortex_ab_track_b_reference_provider_fault_injection_preregistration_v1_pack.py`: `874f5f5ac44e4a481f99fd7c23755067c2dba9d848df5ad5a43cb5f26ba422f8`
- `scripts/eval/fixtures/biocortex_ab_track_b_reference_provider_fault_injection_preregistration_v1_pack_synthetic_v0.json`: `efdc62c03295e22faa38001d232eed469fb1d723e0b92e059913237eab2e0d79`
- `scripts/eval/fixtures/biocortex_ab_track_b_reference_provider_fault_injection_preregistration_v1_pack.expected.v0.tsv`: `11e7e716d799966d1d29d00ee6368260b97f3814ae99c7fceed2fbfd31837f14`
- `docs/design/fixtures/biocortex-ab-track-b-external-atomic-live-output-boundary-design-receipt-schema-v1.json`: `cbb68b0c55e5504bfc6417280978d18c5228c353b1147a3d05b847edc2d3b99c`
- `docs/design/fixtures/biocortex-ab-track-b-external-atomic-live-output-execution-boundary-contract-v1.json`: `9688c4df6ce4a8cf84539a400b488f2c108da606ab2a9eb22e459376bd525046`
- `docs/design/fixtures/biocortex-ab-track-b-production-provider-prerequisite-observation-source-profile-schema-v1.json`: `5a4d7d0f817de1a4fbf307508bd1d775bec31e683a2487440befedcfa0e1b342`
- `scripts/eval/biocortex_ab_track_b_external_atomic_live_output_boundary_v1.py`: `0eb1d6830c8594c4d265440b7fb4bff0ecb507916f59c4057a24eba6fc90cac4`
- `scripts/eval/check_biocortex_ab_track_b_external_atomic_live_output_boundary_v1_pack.py`: `491af79c141317536b141ff1eb4b93df322bd38bc840f1d15061e68e317fa0a8`
- `scripts/eval/fixtures/biocortex_ab_track_b_external_atomic_live_output_boundary_v1_pack_synthetic_v0.json`: `7ed9352834de04729188d931ebce7b28d01c709b22e78f074d80248dac9a23f2`
- `scripts/eval/fixtures/biocortex_ab_track_b_external_atomic_live_output_boundary_v1_pack.expected.v0.tsv`: `f5798073ff1c78a38f20a41723df2aac4bf3ef1b104792c1b8533bc275b93093`
- `scripts/eval/fixtures/biocortex_ab_track_b_external_atomic_live_output_boundary_v1_pack_v0.json`: `b2c101068f237912f79aef6e975a0336d46845d86070ab307945420c3c9e1e96`
- `docs/reports/goal-c-u/2026-07-15-biocortex-track-b-external-atomic-live-output-boundary-v1-pack.md`: `1987c5d89b859179715cdd940c63b18563c59d9b6bcaeb0fac642b4ca47563fe`
- `scripts/check-biocortex-ab-track-b-external-atomic-live-output-boundary-v1-pack.sh`: `8b5f6a19da7054dbc7a9d5c05326c80c2d50c07ed83965ee782c6e833c98083e`
