# BioCortex Track B reference-provider fault-injection offline harness v1

## Outcome

The preregistered managed and self-hosted fault plan now has a deterministic,
pure offline protocol harness. It compiles the frozen two-track contract into
1,020 isolated simulation namespaces, executes all 34 case models for 30
repetitions, emits immutable event traces, and validates the result with an
independent oracle that does not call the candidate's classification function.

The decision is
`OFFLINE_HARNESS_PASS_PROVIDER_EXPERIMENT_REMAINS_BLOCKED`. This is an
implementation and local-conformance result, not a provider experiment. No
network, provider SDK, credential, paid resource, managed service, owned lab,
generator, sink, production adapter, or output-permit capability is present.

## Two evidence ledgers prevent simulator inflation

The 1,020 offline rows are deliberately split by what the harness can actually
observe. A planned evidence locus is never copied into the observed provenance
field.

| Offline ledger | Cases | Rows | What it supports | What it cannot support |
|---|---:|---:|---|---|
| Client-conformance observation | 14 | 420 | Local request-shape, fail-closed, framing, checksum, version, signature-binding, stale-read, nested-transaction, and Watch-authority guards | Provider processing, managed-service behavior, owned-lab behavior, reliability, production readiness |
| Model scenario | 20 | 600 | Deterministic state-machine and evidence-oracle rehearsal | Any observation about Spanner, Cloud KMS, etcd, OpenBao, HA, partitions, restore, or provider processing |
| Managed-service observation | 0 | 0 | Nothing yet | The seven managed-service/proxy cases remain unevaluated |
| Owned-lab observation | 0 | 0 | Nothing yet | The thirteen adversarial-lab cases remain unevaluated |
| Formal provider-experiment row | 0 | 0 | Nothing yet | None of the preregistered 1,020 experiment rows is satisfied |

The aggregate track results therefore remain:

- managed: `NOT_EVALUATED_INCOMPLETE_MANAGED_SERVICE_EVIDENCE_LOCUS`;
- self-hosted: `NOT_EVALUATED_INCOMPLETE_OWNED_LAB_EVIDENCE_LOCUS`.

The 420 local observations are real observations of this pure client harness,
but they still do not count toward the provider-experiment denominator. The
600 model rows use `simulated_classification`; they never populate the
contract's observed `case_classification` field.

## Frozen bindings and deterministic result

The logical predecessor is integration commit
`0be03cfdbee77f0bc29559e0795fa3ec77f07357`, whose source packet is
`8640a7ef39319befbbb265376c26dec03910db25`. The exact preregistration contract
SHA-256 is
`632dbf1d8202d94d6aef70d8b20c04050e647679da973d81afbe13d68344ad22`.
The current offline result is:

| Metric | Value |
|---|---:|
| Tracks | 2 |
| Cases | 34 |
| Repetitions per case | 30 |
| Offline rows | 1,020 |
| Client-conformance rows | 420 |
| Model-scenario rows | 600 |
| Provider-evidence rows | 0 |
| Experimental rows | 0 |
| Directed negative tests | 384 |
| Root-closed schema documents | 3 |
| Configuration SHA-256 | `fd993935d9847f2a75b665cc77d078946cf2c0bd2d24adbd43c2a50d1dbd6a85` |
| Schedule SHA-256 | `37e00bb606b09760d0280e240afbbc2585412c7080a5bf909a130edf305d70b3` |
| Offline rows SHA-256 | `e4458abb43b7de6d8fb40809e679393198b29c2303ba9824bae414455d6b305e` |

No success rate, failure rate, superiority score, effect size, production
readiness score, or cross-track comparison is computed. Categorical model
counts are implementation coverage, not provider performance statistics.

## Harness architecture

The source is a pure Python protocol kernel with no filesystem, process,
network, environment, clock, or random I/O:

```text
frozen preregistration contract + offline configuration
                         |
               deterministic compiler
        (assignment, variant, run, namespace)
                         |
             one-shot fault controller
                         |
        +----------------+----------------+
        |                                 |
 managed protocol model          self-hosted protocol model
 Spanner/KMS shapes               etcd/Transit/witness shapes
        |                                 |
        +---------- immutable trace ------+
                         |
              independent checker oracle
                         |
        client-observation or model ledger
```

The candidate creates traces and provisional classifications. The checker has
its own schedule framing, variant tables, classification table, closed
event-detail catalog, cut-point ordering, state transition replay, prepared
attempt/call/validation/receipt hash derivation, exact-key CAS replay, witness
record compiler, S12 correlation compiler, and evidence-ledger rules. It does
not call the candidate's classification, variant, transition, CAS, witness, or
correlation functions. A mutation that changes only an allowed enum or event
label without matching raw state is rejected.

## Schedule encoding is now byte-exact

The preregistration named a domain-separated SHA-256 order but did not specify
the byte delimiter or integer encoding. The harness closes that deferred
implementation detail without changing the predecessor contract:

1. Every frame part is prefixed by an unsigned 32-bit big-endian byte length.
2. Domain, track, and case identifiers use UTF-8 bytes.
3. Repetition uses an unsigned 32-bit big-endian integer.
4. Configuration and assignment digests enter run-ID framing as raw 32-byte
   values, not hexadecimal text.
5. Assignment hashes cover the complete ordered block before any run ID is
   derived; there is no self-reference.
6. Namespace IDs are derived from the raw simulation run ID.

All 30 managed blocks precede all 30 self-hosted blocks. Within each block the
case order is a hash sort, each namespace is unique, assignment is sealed
before candidate start, and a one-shot fault controller is armed before start.
Control cases record zero triggers; every fault case records exactly one at
the case-specific transition. The checker requires the exact predecessor →
trigger → successor ordering for every cut instead of accepting a generic
pre-execution trigger.

## The row model separates outcome, classification, and provenance

Each row contains three independent concepts:

- `row_outcome` says whether the offline attempt completed, hit an
  infrastructure failure, or stopped for a boundary breach.
- `case_classification` is populated only for a completed
  `CLIENT_CONFORMANCE_DOUBLE` row.
- `simulated_classification` is populated only for a completed model scenario.

Infrastructure and boundary-stop rows are retained with both classifications
null and `NOT_EVALUABLE_RETAINED`; they cannot be deleted, substituted, or
forced into a case's allowed enum. This resolves the preregistration tension
between “retain all failure/timeout/abort rows” and case enums that contain no
infrastructure category.

Each row also separates:

- the contract's `planned_evidence_locus`;
- the harness's `actual_evidence_origin`;
- nullable `provider_evidence_sha256`; and
- required `simulator_trace_sha256`.

For all 1,020 offline rows, provider evidence is null, `provider_called=false`,
`experimental_run_row=false`, and `counts_toward_experiment=false`.

## Managed protocol implementation

The managed model implements a modeled serializable exact-key transition
chain. Its 19-field authoritative operation record binds authority, challenge,
logical sink, message, key, outbox, attempt, call, validation, and receipt
state; every applied transition carries a closed 16-field exact-CAS envelope.
The prepared phase embeds the existing six-field prepared-attempt record, and
call consumption is durably committed before the local signing double is
invoked. Exact-version request handling, hash-linked response validation,
terminal ambiguity, and restart reconstruction all project from the final
record hash and revision in the canonical durable image.

| Cases | Offline implementation oracle |
|---|---|
| M00 | Serializable authority commit, durable outbox, prepared marker, one double call, raw-message/CRC/version/protection/signature validation, durable receipt |
| M01 | First database-only closure attempt aborts; second reuses stable inputs; the external call occurs only after commit |
| M02 | Static source allowlist and runtime sentinel reject an attempted signer side effect inside the retryable closure |
| M03 | Requested repeatable-read is rejected before transaction or signer work |
| M04 | An exact-key CAS double executes fifteen exact-record recoveries and fifteen bare-absence → same-operation terminal-fence CAS → confirming-strong-read → delayed-commit-conflict recoveries |
| M05 | One modeled serializable mutation binds authority, challenge consumption, logical sink reservation, exact message, exact key, and durable outbox; a retained digest-arm request then fails before a prepared attempt or signer call |
| M06 | A retained request carrying a mutated 137-byte frame fails before a prepared attempt or signer call |
| M07 | Fifteen CRC-over-Base64 errors and fifteen `verifiedDataCrc32c=false` responses fail closed |
| M08 | Five version-resource mutations receive six repetitions each; only response-name mismatch reaches the response validator |
| M09–M11 | Signature CRC, protection enum, and pinned-key/message verification mutations reach the relevant validator and cannot commit a receipt |
| M12 | Lost signer response becomes durable ambiguity; restart reconstructs from durable bytes and adds no sign call |
| M13 | Fifteen exact-receipt strong-read recoveries and fifteen terminal quarantines; in-memory signature bytes never authorize restart |
| M14 | Cooperative two-worker schedule produces one CAS owner, one application double call, one receipt, and no provider-processing claim |
| M15 | Crash after durable outbox but before attempt CAS reconstructs a new worker and does not reauthorize or reconsume the challenge |

The model does not claim that a single receipt proves a single Cloud KMS RPC
or a single signature creation. The underlying design continues to follow the
documented possibility of retried Spanner transaction functions and unknown
commit outcomes, while the exact terminal-fence protocol remains our
fail-closed design choice. [Spanner transactions](https://docs.cloud.google.com/spanner/docs/transactions),
[Spanner transaction timeout](https://docs.cloud.google.com/spanner/docs/transaction-timeout).

The KMS double uses only the `data` arm and the frozen 137 raw bytes. It checks
Castagnoli CRC32C over decoded data, `verifiedDataCrc32c`, response-name
equality, signature CRC32C, exact protection enum, and local Ed25519
verification. These fields mirror the official API shape but do not emulate
provider implementation behavior. [Cloud KMS asymmetricSign](https://docs.cloud.google.com/kms/docs/reference/rest/v1/projects.locations.keyRings.cryptoKeys.cryptoKeyVersions/asymmetricSign).

## Self-hosted protocol implementation

The self-hosted model implements a linearizable, top-level, non-nested,
non-leased exact-key CAS chain using the same closed 19-field operation record
and 16-field transition envelope. Every applied mutation binds its exact
previous record and mod revision; only the modeled top-level transaction
response revision is accepted as commit evidence, and the final row tip must
equal the replay winner. The model also includes exact lookup or same-key
terminal fencing after unknown outcomes; an external witness ledger excluded
from snapshot/restore control, keyed by the domain, authority, and logical
cluster lineage, with a closed 15-field record and previous-hash/generation
CAS; Watch invalidation; full cache reconciliation; and exact-version Transit
request and signature binding.

| Cases | Offline implementation oracle |
|---|---|
| S00 | Linearizable read, top-level non-nested CAS revision, durable attempt, explicit Transit version, exact-message signature validation |
| S01 | Fifteen current-quorum observations and fifteen fail-closed unavailability paths; isolated follower state is never authoritative |
| S02–S03 | Serializable-read and nested-transaction candidates fail before authority mutation |
| S04 | Fifteen exact-record lookups and fifteen bare-absence → same-key fence CAS → confirming-linearizable-read → delayed-commit-conflict paths |
| S05–S06 | Post-commit leader/ACK loss resolves only through exact linearizable lookup; no blind replay |
| S07–S08 | Quorum loss never falls back to stale reads; Watch remains telemetry and cannot authorize or resolve ambiguity |
| S09 | Old snapshot, stale/forked witness, and unavailable-witness variants receive ten repetitions each and incident-quarantine |
| S10 | Reused incumbent identity or mismatched witness binding incident-quarantines despite revision bump |
| S11 | Verified snapshot, bump, mark-compacted, external exact witness CAS, new IDs, Watch invalidation, and full linearizable rebuild are all required |
| S12 | Fifteen branch-specific validated standby receipts bind target, route, HA role, executor, cluster, request, forward/audit, wire attempt, response, and receipt; fifteen fail-closed paths claim no executor and accept no receipt |
| S13–S14 | Transit response loss and receipt-persist uncertainty reconstruct a worker from durable bytes and never re-sign from consumed/ambiguous state |
| S15 | Fifteen pinned-version successes and fifteen pinned-version-unavailable failures; latest is never substituted |
| S16–S17 | Version zero fails before a call; prefix/key/message mutations fail exact single, non-batch, context-free binding |

etcd's documented linearizable/stale-read, Watch, timeout-uncertainty, and
restore behavior motivates these cuts; the independent witness and terminal
fence are explicit protocol design choices, not properties attributed to
etcd. [etcd API guarantees](https://etcd.io/docs/v3.6/learning/api_guarantees/),
[etcd disaster recovery](https://etcd.io/docs/v3.6/op-guide/recovery/).

The Transit shape uses an explicit nonzero version, one non-batch request,
absent context, `prehashed=false`, exact Base64 input, versioned signature
prefix, pinned public key, and local Ed25519 verification. Route, target-node
seal status, executing node, request ID, forwarding, and audit identities stay
separate. [OpenBao Transit API](https://openbao.org/api-docs/secret/transit/),
[seal-status API](https://openbao.org/api-docs/system/seal-status/),
[OpenBao high availability](https://openbao.org/docs/internals/high-availability/).

## S12 branch semantics are made explicit

The frozen S12 case permits both a validated standby success and fail-closed
behavior. Its referenced executing-node invariant contained an unconditional
“no signature receipt” evidence phrase, which conflicts with the permitted
success branch if read literally. The harness therefore records a conservative
branch interpretation rather than silently weakening either side:

- success adds S10, S11, and S12 to the effective invariant set and requires
  exact version, exact message, pinned key, local verification, executing-node
  correlation, and a durable receipt;
- failure retains the target and route but does not preclaim an executing node,
  redirect, forwarder, audit record, or wire attempt; it requires zero accepted
  receipt and zero output.

This interpretation is explicitly surfaced in the suite receipt. The future
runner/adapter contract must formalize the branch wording before any real
resource authorization; the predecessor packet remains byte-for-byte frozen.

## Global invariants are compiled, not merely referenced

Every effective row invariant set equals all global invariants X01–X08 unioned
with the case's explicit references and any branch-specific additions. This is
necessary because X02 is not explicitly referenced by any individual case,
while X01, X04, and X06 have only sparse explicit references. A refs-only
implementation would lose fresh namespaces, no-permit, cross-track separation,
or resource-authority boundaries. Directed mutations remove X02 from every
case family and are rejected.

## Cryptographic and checksum known-answer tests

The exact inherited message remains 137 bytes with SHA-256
`f5dcb16eec00a302bf56c9cc681b5c09d598589c4c3e9ab2413b68c21f16982d`.
The pure reference double uses a fixed test-only Ed25519 seed. The checker
freezes the resulting public key and signature bytes, verifies the valid
signature using the candidate's arithmetic, verifies both an independently
mutated signature and a noncanonical x=0/sign=1 encoding fail, and pins the
standard CRC32C `123456789` result
`0xe3069283`. Valid immutable tuples are memoized only after real verification;
negative signature, prefix, key, and message tuples still execute the verifier.

This is not production cryptographic code or provider validation. The fixed
seed is test data, not a credential; the module has no key-loading or secret
interface.

## Independent validation and falsification

The checker performs 384 directed mutations. Retained infrastructure and
boundary-stop rows also have separate positive schema-acceptance probes; those
two probes are intentionally not counted as negative tests.

Fifty-six high-value row-level binding attacks must be rejected by both the
candidate's deterministic replay and the independent oracle. The remaining
mutations are routed according to responsibility to the independent oracle or
to candidate API/configuration guards; this test-routing count is not provider
evidence.

- for every one of the 34 cases: schedule/namespace, classification,
  simulator-as-provider provenance, experiment-denominator, global-invariant,
  event-order, semantic-token, and real-provider-call mutations;
- misuse of a retained infrastructure row as a case-classified oracle row;
- missing, substituted, and interleaved bundles;
- S12 success without full signing invariants;
- prepared-request substitution, marker reuse, zero-call receipt, and prepared
  record tampering before processing;
- direct pre-read terminal-fence, fence-overwrite, forbidden witness-actor, and
  S12 node-alias API probes;
- noncanonical Transit version prefixes plus omitted/extra request fields;
- nested provider-evidence injection and invariant overclaim;
- removal of a raw call event while retaining counters;
- all 15 external-witness record fields independently mutated;
- S12 route/executor, request-ID, audit, and failure-executor misbindings;
- wrong-position and duplicate fault triggers;
- corrupt durable restart image, false post-state, call, and receipt hashes;
- restart re-sign after terminal ambiguity;
- terminal-fence read/CAS reordering;
- call/prepared-operation misbinding, validation-before-processing, and missing
  observed-response traces found by the integrity review;
- nonzero S12 fail-branch work counters, weak/false CAS consistency or revision,
  and M15 hidden durable-image field drift found by the integrity review;
- durable operation-record field/hash/tip substitutions, broken compare or
  observed-record links, skipped or reordered phases, nested/leased applied
  transitions, false top-level revision sources, call-before-consumption,
  split M05 atomic bindings, M15 restart-tip loss, shifted causal-cut sequence,
  and staged-witness or snapshot self-proof rewrites;
- exact request/response/version/isolation/public-key/message evidence
  substitutions and semantic-token additions, removals, duplicates, or
  forbidden claims; and
- provider, credential, paid-resource, output-permit, production-adapter, and
  experiment-executed boundary flips.

It also validates three root-closed schema documents, exact canonical JSON, the
predecessor packet hashes, source AST purity, deterministic deep-copy reruns,
independently recomputed schedule/run IDs, 1,020 unique run keys, 1,020 unique
namespaces, 30 rows per case, track non-interleaving, variant balance, trace
hashes, row schemas, and the suite receipt schema. Dynamic maps remain typed;
the 88 event-detail shapes are closed by identical source/checker catalogs.

## Data-quality assessment

| Dimension | Assessment | Interpretation |
|---|---|---|
| Schedule completeness | Pass for offline rows | Exactly 1,020 offline rows; says nothing about provider experiment completeness |
| Uniqueness | Pass for offline namespace | Unique run key, simulation ID, and namespace |
| Assignment balance | Pass | Thirty deterministic blocks per track |
| Variant balance | Pass | 15/15, 10/10/10, and 6×5 closed rotations as frozen |
| Provenance | Pass | Planned locus and actual offline origin are separate; provider hash is null |
| Provider completeness | Not evaluated | Zero managed-service, owned-lab, provider-evidence, or experimental rows |
| Timeliness | Not applicable to provider state | No external runtime state was sampled |
| Production readiness | Not evaluated | Forbidden claim |

## Non-authorization boundary

All receipts and rows retain:

```text
experiment_executed=false
provider_called=false
credentials_accessed=false
paid_resources_provisioned=false
cost_authority_bound=false
production_adapter_in_scope=false
live_generator_in_scope=false
live_output_permit_defined=false
receipt_is_output_permit=false
condition_output_authorized=false
side_effects_unlocked=NONE
```

No offline row, manifest, report, classification, or receipt can become an
output permit or resource authorization.

## Next unit

The next frozen unit is
`REFERENCE_PROVIDER_MANAGED_AND_SELF_HOSTED_FAULT_INJECTION_RUNNER_V1_AUTHORITY_AND_ADAPTER_CONTRACT`.

It should define separate managed and owned-lab adapter interfaces, owner and
custodian authority receipts, credential/resource/cost scopes, stop receipts,
provider-profile evidence eligibility, and runtime retained-row semantics.
It must not itself start a provider, provision a resource, read a credential,
or convert this offline result into execution authority.

## Artifact binding

- `docs/design/fixtures/biocortex-ab-track-b-reference-provider-fault-injection-offline-schedule-entry-schema-v1.json`: `135238e4f20ac6a5712606dc2b94aefaa9d6b54ec9dece234ac8f43381caa35b`
- `docs/design/fixtures/biocortex-ab-track-b-reference-provider-fault-injection-offline-run-row-schema-v1.json`: `a60b16cab0c1a3ac8314f4f4df19fae2cff59aa1a10e67fe446305dd70cb0ee1`
- `docs/design/fixtures/biocortex-ab-track-b-reference-provider-fault-injection-offline-harness-suite-receipt-schema-v1.json`: `711c85ce5d9c5eb13d5c39b65f684bb1d00cc9722ae03852b93a8352abbf2671`
- `scripts/eval/biocortex_ab_track_b_reference_provider_fault_injection_harness_v1.py`: `ed55297995d1f49d2b4f5b9c6116c4f5fd69ae5e2be0ea2658aae6b2ed7e0976`
- `scripts/eval/check_biocortex_ab_track_b_reference_provider_fault_injection_offline_harness_v1_pack.py`: `e05841c731dafcf9118e61937fa7f68a3810debb904124c590d07af1ced1f348`
- `scripts/eval/fixtures/biocortex_ab_track_b_reference_provider_fault_injection_offline_harness_v1_pack_synthetic_v0.json`: `fd993935d9847f2a75b665cc77d078946cf2c0bd2d24adbd43c2a50d1dbd6a85`
- `scripts/eval/fixtures/biocortex_ab_track_b_reference_provider_fault_injection_offline_harness_v1_pack.expected.v0.tsv`: `9c4a2f7ff0de15e5e37fd2d8b0292e8870eaa505102af04fa16c78c1eec50541`
- `docs/design/fixtures/biocortex-ab-track-b-reference-provider-fault-injection-preregistration-receipt-schema-v1.json`: `02968490ff213aca8a1f2ac6d766d7711caedd4b9c1ff030caf206cc2c3fb21e`
- `docs/design/fixtures/biocortex-ab-track-b-reference-provider-fault-injection-pre-execution-observation-schema-v1.json`: `28272f4aa3336be1d3239e33573065c5ecd746a16bc97c7710b0ae9a6c5b77b5`
- `docs/design/fixtures/biocortex-ab-track-b-reference-provider-fault-injection-experiment-contract-v1.json`: `632dbf1d8202d94d6aef70d8b20c04050e647679da973d81afbe13d68344ad22`
- `scripts/eval/biocortex_ab_track_b_reference_provider_fault_injection_preregistration_v1.py`: `1644a95f21144b28335ca107638245fcc605add4b0ba438dafb50fab6e65a1e0`
- `scripts/eval/check_biocortex_ab_track_b_reference_provider_fault_injection_preregistration_v1_pack.py`: `874f5f5ac44e4a481f99fd7c23755067c2dba9d848df5ad5a43cb5f26ba422f8`
- `scripts/eval/fixtures/biocortex_ab_track_b_reference_provider_fault_injection_preregistration_v1_pack_synthetic_v0.json`: `efdc62c03295e22faa38001d232eed469fb1d723e0b92e059913237eab2e0d79`
- `scripts/eval/fixtures/biocortex_ab_track_b_reference_provider_fault_injection_preregistration_v1_pack.expected.v0.tsv`: `11e7e716d799966d1d29d00ee6368260b97f3814ae99c7fceed2fbfd31837f14`
- `scripts/eval/fixtures/biocortex_ab_track_b_reference_provider_fault_injection_preregistration_v1_pack_v0.json`: `4f15f205539796213ee6f7d0694b7c6bcaf69dae6014b1d084d66228b96486df`
- `docs/reports/goal-c-u/2026-07-15-biocortex-track-b-reference-provider-fault-injection-preregistration-v1-pack.md`: `6f6bbdf6c71ccb1a4eba916be90aa4f35a72548c9e3faf08980727625ba147c1`
- `scripts/check-biocortex-ab-track-b-reference-provider-fault-injection-preregistration-v1-pack.sh`: `5bbe2b94241fb7b5f3957fc999cb6ab6cc9be4a712fbda1999788f606ea774bc`
