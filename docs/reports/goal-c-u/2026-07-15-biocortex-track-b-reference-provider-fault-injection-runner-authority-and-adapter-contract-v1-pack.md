# BioCortex Track B reference-provider fault-injection runner authority and adapter contract v1

## Outcome

The reference-provider runner now has a frozen, machine-checkable authority,
adapter, evidence-routing, and absorbing-STOP contract. The decision is
`RUNNER_AUTHORITY_AND_ADAPTER_CONTRACT_PASS_EXECUTION_REMAINS_BLOCKED`.

This packet does not implement a provider adapter or runner and does not bind
an endpoint, profile, credential, authority receipt, cost budget, paid
resource, lab, execution capability, experiment row, condition output, or
output permit. Its synthetic observation contains zero runtime rows, calls,
wire attempts, provider evidence rows, and provider-processing events.

## Authority is per phase, track, and assigned run

Two non-substitutable grants exist:

1. `PREFLIGHT_OBSERVATION_GRANT` permits only the frozen read-only metadata
   catalog for one assigned run.
2. `EXPERIMENT_EXECUTION_GRANT` permits only the exact assigned route's
   experiment-adapter operations.

The two grants must have distinct authorization requests, nonces, signature
receipts, and private capability commitments. A preflight grant cannot be
reused as execution authority. Both grants bind the predecessor's exact
`suite_id`, `simulation_run_id`, `namespace_id`, `assignment_sha256`, case,
and repetition. Repetitions use the inherited range 1 through 30; zero is not
a run and repetition 30 remains representable.

Every binding also freezes the contract, offline harness manifest, profile,
configuration, schedule, runner build, adapter build, adapter-set manifest,
STOP-control-plane manifest, resource scope, credential scope, cost scope,
retention policy, cleanup policy, and revocation epoch. The assignment block,
run ID, and namespace ID are recomputed with the exact predecessor domains and
byte framing; they cannot be regenerated or substituted by the future runner.

## Five artifacts participate with different authority algebra

| Artifact | Required for START | Positive execution authority | Other role |
|---|---:|---:|---|
| Owner scope receipt | yes | yes | owner intent and exact scope |
| Custodian credential receipt | yes | yes | credential lease and principal scope |
| Resource authority receipt | yes | yes | resource and cleanup boundary |
| Cost authority receipt | yes | yes | reserved cost boundary |
| Emergency STOP authority receipt | yes | no | veto and reductive-only STOP capability |

Effective cases and repetitions are the intersection of the owner,
custodian, resource, and cost receipts, while the emergency receipt must bind
the same assigned run. Effective operations are the four positive receipts'
intersection minus the union of forbidden operations from all five receipts.
The emergency principal therefore never needs signing, mutation, or fault-arm
authority and can never enlarge execution authority.

Resource, credential, cost, retention, and cleanup digests must match exactly
across all five receipts and the computed intersection. Execution case and
repetition are singleton values equal to the frozen assignment. The effective
operation list and field-level intersection hash are repeated in the public
bundle and private-capability commitment so a capability cannot be moved to a
different scope.

## Integrity is defined by bytes, not by 64-hex shapes

The contract freezes canonical JSON, four-byte big-endian length framing,
domain strings, raw-digest versus hexadecimal encoding, a framing
known-answer test, and the preimages for authorization requests, scope
receipts, receipt IDs, bundle IDs, the authority intersection, channel
bindings, control-ledger records, private capability commitments, and STOP
receipts.

Signature-receipt hashes must resolve to canonical allowlisted evidence, and
the referenced non-secret signature bytes must also resolve. A verifier must
actively verify those bytes with the exact trust-policy public key, version,
role mapping, and algorithm. A stored `SIGNATURE_VALID_TRUE` assertion is not
accepted as proof on its own.

Trusted time and row-currentness hashes likewise must resolve to signed,
binding-complete evidence. All timestamps must be calendar-valid RFC 3339 UTC
seconds. The checker rejects malformed calendar values and enforces issuance,
not-before, expiry, verification, checked-at, cleanup, and STOP ordering rather
than relying on lexical comparison.

The public bundle and all receipts explicitly remain non-bearer artifacts.
The executable capability is an opaque, non-serializable, process/session/run
bound 32-byte-secret commitment. START occurs only after one durable CAS from
`UNUSED` to `START_COMMITTED`; an unknown or failed CAS authorizes no provider
or fault call.

## STOP is OR-triggered, independently reachable, and absorbing

START requires every condition. STOP requires any one enumerated trigger,
including expiry, revocation, currentness failure, build or assignment drift,
scope breach, hidden retry, fault misfire, evidence failure, witness failure,
unknown provider activity, output/permit attempts, or an owner, custodian, or
emergency-operator request. The contract contains a total mapping from all ten
trigger classes to all 21 stop reasons and all five trigger roles; unknown or
orphan values fail closed.

STOP does not reuse any of the nine experiment-adapter credentials. Its five
reductive-only control interfaces are:

| Interface | Exact responsibility |
|---|---|
| Capability fence | CAS the assigned capability to fenced and block new calls |
| Fault disarm and egress isolation | Disarm only the assigned cut and isolate only the assigned namespace |
| Credential revocation | Revoke exact-run leases and confirm zero active commitments |
| Durable evidence retention | Preserve the current row, durable state, and allowlisted safe evidence |
| Scoped resource cleanup | Freeze assigned resources, then perform only reductive teardown within the cleanup scope |

Their order is fence, retain row and state, disarm and isolate, revoke, confirm
evidence persistence, then reductive cleanup. Execution-capability expiry or
revocation cannot make this control plane unreachable. Any control-interface
failure creates a durable failure ID, retains the row, preserves available
evidence, enters terminal quarantine, and cannot expand authority.

The STOP receipt has four observable lifecycle states:

- `STOP_REQUESTED` and `STOP_FENCING` have no completion timestamp;
- `STOP_ABSORBING_COMPLETE` requires the capability fenced, new calls blocked,
  row and evidence preserved, credential revoked, fault disarmed, cleanup
  complete, zero control failures, and zero unresolved ambiguities;
- `STOP_FAILED_QUARANTINED` is terminal, escalated, non-continuable, and has no
  successful completion timestamp.

The schema enforces both directions: all successful components with no
failures imply absorbing completion, while any failed component, control-plane
failure, or unresolved ambiguity implies terminal quarantine. No STOP receipt
is execution authority, an output permit, or an automatic-rerun permit.

## Adapter topology preserves least privilege

The experiment surface is nine separate interfaces, not one provider switch:

| Route | Interfaces | Cases | Planned rows | Runtime rows in this packet |
|---|---:|---:|---:|---:|
| Client-conformance double | no provider adapter | 14 | 420 | 0 |
| Managed Spanner / Cloud KMS plus client fault proxy | 4 | 7 | 210 | 0 |
| Self-hosted etcd / OpenBao adversarial lab | 5 | 13 | 390 | 0 |
| Total | 9 provider/lab interfaces | 34 | 1,020 | 0 |

The managed interfaces separate Spanner authority state, exact-version Cloud
KMS signing, the fault proxy, and read-only evidence collection. The
self-hosted interfaces separate etcd authority state, explicit-version
OpenBao Transit signing, an external restore witness, the lab fault
controller, and read-only evidence collection. Fault adapters accept disarm
and egress isolation only through the distinct STOP-only credential class.

Adapters return observations, receipts, counters, hashes, and safe event
indexes. They never return case classifications, authorize outputs, infer
provider processing, or turn `provider_called` into evidence eligibility.
Every assigned runtime attempt must be retained; only a completed evaluable
row with matching planned locus and eligible evidence counts toward acceptance
evidence.

## Provider profiles must prove their security assumptions

Managed profiles require short-lived, brokered credentials rather than an
ambient default chain. Google documents Workload Identity Federation as a way
to exchange supported external identities for short-lived Google credentials
and replace long-lived service-account keys. [Workload Identity Federation
best practices](https://docs.cloud.google.com/iam/docs/best-practices-for-using-workload-identity-federation?hl=en).

Cloud KMS signing remains bound to an exact key version and its request and
response integrity fields; audit collection is a separate evidence path, not
proof of provider processing. [Cloud KMS asymmetricSign](https://docs.cloud.google.com/kms/docs/reference/rest/v1/projects.locations.keyRings.cryptoKeys.cryptoKeyVersions/asymmetricSign),
[Cloud KMS audit logging](https://docs.cloud.google.com/kms/docs/audit-logging).

Self-hosted profiles must prove, rather than assume, etcd client and peer mTLS,
authentication, and RBAC because those controls are not all enabled by
default. [etcd security](https://etcd.io/docs/v3.6/op-guide/security/). The
restore witness remains outside the etcd snapshot/restore failure domain.

OpenBao profiles bind the explicit Transit version, HA route and executor
identities, audit-device union, and accounting for documented system paths
that do not traverse normal audit logging. [OpenBao Transit](https://openbao.org/api-docs/secret/transit/),
[OpenBao HA](https://openbao.org/docs/internals/high-availability/),
[OpenBao audit limitations](https://openbao.org/docs/next/audit/).

## S12 has three closed post-wire outcomes

The self-hosted S12 branch no longer conflates a standby target with the actual
executor. Pre-wire failure claims no executor. A correlated post-wire failure
is an explicit fail-closed classification. A successor success requires exact
target, route, executor, HA role, cluster, request, redirect, forward, audit,
wire, response, version, message, key, signature, and durable-receipt
correlation. An uncorrelated post-wire observation remains a retained
infrastructure failure; it is not silently converted into either branch.

## Validation and remaining boundary

The independent checker validates the two root-closed schemas, exact adapter
and control-plane catalogs, official-source claim catalog, route partition,
authority algebra, byte framing, predecessor lineage, strict timestamps,
STOP state machine, trigger mapping, zero-runtime observation, artifact hashes,
source AST purity, and frozen predecessor packet. Its directed-negative matrix
mutates role slots, run and phase bindings, repetitions, operation scope,
currentness, schema closure, adapter permissions, credentials, evidence
eligibility, S12 branches, STOP statuses, timestamps, trigger mappings, and
artifact hashes. Normal and self-test modes execute the same negative oracle
and emit identical deterministic results under multiple hash seeds.

Nothing in this result is provider reliability, exactly-once proof, production
readiness, security certification, output authorization, or evidence that one
application receipt equals one provider RPC or signature creation.

The Git gate treats users and processes with write access to the shared Git
common directory as trusted workspace principals. It rejects executable Git
filters and attribute sources, checks archive and worktree bytes, and verifies
that nested replay leaves no worktree registration or gate-temp entry behind;
it is not a defense against a concurrently hostile writer who already controls
that shared repository metadata.

## Next unit

The next bounded unit is
`REFERENCE_PROVIDER_MANAGED_AND_SELF_HOSTED_FAULT_INJECTION_RUNNER_V1_OFFLINE_AUTHORITY_VERIFIER_AND_ADAPTER_DOUBLE_IMPLEMENTATION`.
It may implement only offline authority verification, private-capability/control
ledger doubles, the nine experiment adapter doubles, and the five STOP-control
doubles against this frozen contract. Provider endpoints, real credentials,
paid resources, owned-lab execution, formal experiment rows, condition output,
and output permits remain blocked.

## Artifact binding

- `docs/design/fixtures/biocortex-ab-track-b-reference-provider-fault-injection-runner-authority-receipt-schema-v1.json`: `faea2234635441b0bc043b5d605a449decc61cc854e708f705f7bb09d58a7b90`
- `docs/design/fixtures/biocortex-ab-track-b-reference-provider-fault-injection-runner-adapter-contract-v1.json`: `d602d9f14f662145bd12f33304b2800bb9601ff4fd76634eb56c41b86aa17201`
- `docs/design/fixtures/biocortex-ab-track-b-reference-provider-fault-injection-runner-stop-receipt-schema-v1.json`: `7657cd25a9abf4037ce5eb4c403db36aebf4b43deb232886e62ff4afe9d45c36`
- `scripts/eval/biocortex_ab_track_b_reference_provider_fault_injection_runner_authority_and_adapter_contract_v1.py`: `38b0e31504b72f961baec7e037a9340a334d3655aff2ce4d90fd01db4afb45a3`
- `scripts/eval/check_biocortex_ab_track_b_reference_provider_fault_injection_runner_authority_and_adapter_contract_v1_pack.py`: `c8f2258f9f8bac956958d6ebd011790814b6df3bad7f72213dd8241add7b4605`
- `scripts/eval/fixtures/biocortex_ab_track_b_reference_provider_fault_injection_runner_authority_and_adapter_contract_v1_pack_synthetic_v0.json`: `75259e4d211d40d1b00caccd4b13ca593363884b507a59cd2b57b55c462f6300`
- `scripts/eval/fixtures/biocortex_ab_track_b_reference_provider_fault_injection_runner_authority_and_adapter_contract_v1_pack.expected.v0.tsv`: `948842558a2be55a10660305758db5532ae89ec8b3340338c989befb26d5ce4b`
- `docs/design/fixtures/biocortex-ab-track-b-reference-provider-fault-injection-offline-schedule-entry-schema-v1.json`: `135238e4f20ac6a5712606dc2b94aefaa9d6b54ec9dece234ac8f43381caa35b`
- `docs/design/fixtures/biocortex-ab-track-b-reference-provider-fault-injection-offline-run-row-schema-v1.json`: `a60b16cab0c1a3ac8314f4f4df19fae2cff59aa1a10e67fe446305dd70cb0ee1`
- `docs/design/fixtures/biocortex-ab-track-b-reference-provider-fault-injection-offline-harness-suite-receipt-schema-v1.json`: `711c85ce5d9c5eb13d5c39b65f684bb1d00cc9722ae03852b93a8352abbf2671`
- `scripts/eval/biocortex_ab_track_b_reference_provider_fault_injection_harness_v1.py`: `ed55297995d1f49d2b4f5b9c6116c4f5fd69ae5e2be0ea2658aae6b2ed7e0976`
- `scripts/eval/check_biocortex_ab_track_b_reference_provider_fault_injection_offline_harness_v1_pack.py`: `e05841c731dafcf9118e61937fa7f68a3810debb904124c590d07af1ced1f348`
- `scripts/eval/fixtures/biocortex_ab_track_b_reference_provider_fault_injection_offline_harness_v1_pack_synthetic_v0.json`: `fd993935d9847f2a75b665cc77d078946cf2c0bd2d24adbd43c2a50d1dbd6a85`
- `scripts/eval/fixtures/biocortex_ab_track_b_reference_provider_fault_injection_offline_harness_v1_pack.expected.v0.tsv`: `9c4a2f7ff0de15e5e37fd2d8b0292e8870eaa505102af04fa16c78c1eec50541`
- `scripts/eval/fixtures/biocortex_ab_track_b_reference_provider_fault_injection_offline_harness_v1_pack_v0.json`: `2e06aec1395957cd70ee86ab4af0452ca6c5da6a51112b4c21216bfd43e3a3ed`
- `docs/reports/goal-c-u/2026-07-15-biocortex-track-b-reference-provider-fault-injection-offline-harness-v1-pack.md`: `abedab430bb3d1b28bf508735f164569ae5878285324b35f28df13be3d5b6bf1`
- `scripts/check-biocortex-ab-track-b-reference-provider-fault-injection-offline-harness-v1-pack.sh`: `a8fc449406c599868322454d0f3bcc67ea21923441b04556db44a4dd3247f7cf`
