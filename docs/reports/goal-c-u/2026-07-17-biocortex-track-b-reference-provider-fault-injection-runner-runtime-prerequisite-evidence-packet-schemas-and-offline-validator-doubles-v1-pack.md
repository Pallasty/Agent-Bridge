# Track B runner runtime-prerequisite evidence packet schemas and offline validator doubles v1

Date: 2026-07-17
Scope: synthetic, deterministic, offline schema and validator-double implementation only

## Outcome

`REFERENCE_PROVIDER_FAULT_INJECTION_RUNNER_V1_RUNTIME_PREREQUISITE_EVIDENCE_PACKET_SCHEMAS_AND_OFFLINE_VALIDATOR_DOUBLES_IMPLEMENTED_RUNTIME_EVIDENCE_ZERO_NO_AUTHORITY`

The predecessor preregistered 16 runtime prerequisites and the evidence that a
future owner decision would require. This unit gives each prerequisite an
exact, closed-world packet schema and a deterministic offline validator double.
It defines a frozen known-answer-test (KAT) packet suite and how deviations
from those exact synthetic packets are rejected during offline conformance
testing; it is not a generic production-evidence validator and does not
collect, authenticate, accept, or store real evidence.

Schema conformance is not prerequisite satisfaction. A synthetically
well-formed packet remains test data, and an offline-double result is neither a
production validation result nor runtime authority. The current evidence set
therefore remains empty and the owner-decision state remains fail-closed.

| Measure | Value |
|---|---:|
| Tracks represented | 2 |
| Closed-world packet schemas | 16 |
| Pre-owner evidence packet schemas | 15 |
| Owner-decision packet schemas | 1 |
| Offline validator doubles | 16 |
| Freshness-arithmetic KATs | 15 |
| Real evidence items present | 0 |
| Production-validated evidence items | 0 |
| Runtime prerequisites satisfied | 0 / 16 |
| Owner identity bound | false |
| Owner decision recorded | false |
| Positive runtime-admission decision representable | false |
| Downstream gates authorized | 0 / 4 |

## Sixteen-schema catalog

Every schema is bound to one predecessor prerequisite, owner class, evidence
class, freshness rule, and subject identity. Unknown fields, wrong schema
versions, cross-prerequisite payloads, malformed digests, missing bindings, and
track substitutions are rejected. Packet bytes and fixture identities are
synthetic; they cannot stand in for provider, lab, custodian, reviewer, or
owner evidence.

| # | Packet schema | Bound prerequisite | Required subject or freshness binding |
|---:|---|---|---|
| 1 | `AUTHORITY_VERIFIER_BUILD_EVIDENCE_PACKET` | `PRODUCTION_AUTHORITY_VERIFIER_IMPLEMENTED` | exact source commit, verifier build, and toolchain digest |
| 2 | `MANAGED_ADAPTER_CONFORMANCE_EVIDENCE_PACKET` | `PRODUCTION_MANAGED_ADAPTER_SET_IMPLEMENTED` | exact managed-adapter build and managed-provider profile |
| 3 | `SELF_HOSTED_ADAPTER_CONFORMANCE_EVIDENCE_PACKET` | `PRODUCTION_SELF_HOSTED_ADAPTER_SET_IMPLEMENTED` | exact self-hosted-adapter build and owned-lab profile |
| 4 | `STOP_CONTROL_FAILURE_INJECTION_EVIDENCE_PACKET` | `PRODUCTION_STOP_CONTROL_SET_IMPLEMENTED` | exact STOP-control build and isolated test environment |
| 5 | `TRUST_ROOT_POLICY_BINDING_EVIDENCE_PACKET` | `TRUST_ROOT_AND_KEY_VERSION_POLICY_BOUND` | exact trust root, key version, and policy revision |
| 6 | `PROVIDER_IDENTITY_BINDING_EVIDENCE_PACKET` | `PROVIDER_ENDPOINT_AND_PROFILE_IDENTITY_BOUND` | exact endpoint/profile identity; at most 24 hours old and rechecked at decision |
| 7 | `CREDENTIAL_LIFECYCLE_EVIDENCE_PACKET` | `CREDENTIAL_BROKER_LEASE_AND_REVOCATION_BOUND` | exact broker and lease/revocation scope; at most 60 minutes old with zero active leases |
| 8 | `RESOURCE_AND_BUDGET_AUTHORITY_EVIDENCE_PACKET` | `RESOURCE_SCOPE_AND_COST_BUDGET_AUTHORITY_BOUND` | exact resource scope and budget authority; at most 24 hours old and rechecked at decision |
| 9 | `DURABLE_LEDGER_LINEARIZABILITY_EVIDENCE_PACKET` | `DURABLE_CONTROL_LEDGER_AND_ATOMIC_CAS_PROVEN` | exact authority-store build, configuration, and CAS/linearizability run |
| 10 | `TRUSTED_TIME_CURRENTNESS_EVIDENCE_PACKET` | `TRUSTED_TIME_AND_CURRENTNESS_EVIDENCE_BOUND` | exact trusted-time source; at most five minutes old and rechecked at decision |
| 11 | `RUNNER_PROVENANCE_EVIDENCE_PACKET` | `RUNNER_BUILD_PROCESS_SESSION_AND_CHANNEL_PROVENANCE_BOUND` | exact runner build, process, session, and channel |
| 12 | `SAFETY_STOP_DRILL_EVIDENCE_PACKET` | `FAULT_DISARM_EGRESS_ISOLATION_AND_EMERGENCY_STOP_PROVEN` | exact runner build; at most seven days old |
| 13 | `EVIDENCE_RETENTION_CLEANUP_EVIDENCE_PACKET` | `DURABLE_EVIDENCE_RETENTION_AND_SCOPED_CLEANUP_PROVEN` | exact storage policy; at most seven days old |
| 14 | `TRIAL_SCHEDULE_AND_CUSTODY_EVIDENCE_PACKET` | `REAL_PREREGISTERED_SCHEDULE_ASSIGNMENT_AND_ROW_CUSTODY_BOUND` | exact trial, schedule version, assigned row set, and custody identity |
| 15 | `INDEPENDENT_SECURITY_REVIEW_EVIDENCE_PACKET` | `INDEPENDENT_SECURITY_FAILURE_MODE_AND_ROLLBACK_REVIEW_APPROVED` | ordered content-derived packet IDs 1–14 and a domain-separated synthetic set hash; no real review |
| 16 | `OWNER_RUNTIME_ADMISSION_DECISION_PACKET` | `OWNER_RUNTIME_ADMISSION_DECISION_RECORDED` | pending-or-rejected state matrix at the frozen synthetic check instant; no owner freshness claim |

The first 15 schemas describe shapes for evidence that would have to originate
outside this offline pack. The KAT values themselves are synthetic and do not
meet that requirement. The sixteenth is a decision-envelope schema, not a
shortcut around those dependencies. It is topologically dependent on all 15
preceding prerequisites and cannot turn synthetic conformance results into an
owner decision.

## Offline validator doubles

Each schema has a pure offline validator double. A double consumes only the
supplied packet and the fixture's frozen validation context and timestamps.
It does not read ambient time, environment variables, credentials, network
state, provider state, mutable repository state, or external files. It cannot
call a provider, allocate resources, write evidence, invoke a runner, or change
an owner decision.

The doubles exercise the following fail-closed classes:

- absence of production evidence keeps every prerequisite pending and does not
  increment the satisfied count;
- malformed, incomplete, extra-field, or wrong-version packets are rejected;
- stale or future-dated packets are rejected against the explicit evaluation time;
- source, build, profile, track, scope, row, custody, provenance, or digest mismatches are rejected;
- dependency and evidence-set-hash mismatches are rejected;
- synthetically conformant packets are labelled offline conformance only and
  never become production evidence or prerequisite satisfaction.

The aggregate state is invariant under offline conformance: real evidence
items remain `0`, production-validated items remain `0`, and satisfied runtime
prerequisites remain `0 / 16`.

## Managed and self-hosted separation

The catalog preserves two non-substitutable tracks:

- `MANAGED_SPANNER_CLOUD_KMS`
- `SELF_HOSTED_ETCD_OPENBAO`

The managed-adapter schema is bound to the managed provider profile and may
exercise only managed-provider conformance vocabulary. The self-hosted-adapter
schema is bound to the owned-lab profile and may exercise only self-hosted
conformance vocabulary. Shared prerequisite schemas retain an explicit track
scope and exact subject bindings.

A managed packet cannot certify self-hosted partition, restore, process, or
storage behavior. A self-hosted packet cannot certify managed-service control
plane, service-side durability, or provider-identity behavior. The validators
reject track swaps, cross-track evidence hashes, mixed profile identities, and
attempts to complete one track with evidence assigned to the other. Neither
track ranks or certifies the other.

## Owner packet remains pending-or-rejected only

The owner-decision schema admits only the predecessor vocabulary:

- `PENDING_PREREQUISITE_EVIDENCE`
- `REJECTED_FAIL_CLOSED`

It contains no approved, admitted, authorized, or condition-output state. Its
schema and validator jointly allow exactly two pending reason combinations and
four fail-closed rejection reason combinations. In every combination the
production-validated evidence-set hash is `NONE`, because this unit validates
zero production evidence. Pending carries `NOT_PERFORMED/NONE`; rejected
carries `REJECTED_FAIL_CLOSED` at the exact frozen check instant. The owner
identity remains unbound and no owner decision is recorded.

No agent, validator double, fixture, checker, or manifest may substitute for
the owner. A future positive owner packet would require an authenticated and
production-validated evidence set from all first 15 prerequisites; this unit
cannot produce or represent that packet.

## Verification

Verification is deterministic and offline:

- whole-fixture canonical SHA binding, frozen TSV oracle, and manifest comparison;
- exact 16-schema cardinality and one-to-one prerequisite, owner-class, and
  evidence-class mapping;
- closed-world field, type, enum, digest, timestamp, dependency, and track checks;
- directed mutation rejection for missing and extra fields, schema/version
  drift, malformed digests, freshness boundaries, build/profile swaps,
  cross-track substitution, evidence-set mismatches, and positive owner states;
- source-AST purity checks that reject network, subprocess, provider, credential,
  ambient-clock, environment, filesystem-write, and nondeterministic behavior;
- isolated execution under `python -S -P`, multiple hash seeds, and a private
  temporary directory;
- exact source/integration Git topology, exact packet path and mode allowlist,
  byte identity across source, index, worktree, and integration archives, and
  isolated replay of the unmodified predecessor gates; on the current
  FUSE-mounted home, a no-network mount namespace maps one private, non-tmpfs
  POSIX cache onto the legacy cache target without changing frozen gate bytes;
- a post-check cleanliness assertion proving that verification did not modify
  the invoking worktree or index.

The frozen checker result is 111 artifact-integrity mutations rejected, 10
evidence-packet public-API semantic mutations rejected, 6 owner-packet
public-API semantic mutations rejected, and one valid
`REJECTED_FAIL_CLOSED` owner KAT accepted. Standard Draft 2020-12 validation
also accepts both schemas, all 15 evidence KATs, the pending owner KAT, and the
valid fail-closed rejected owner KAT.

The frozen predecessor bindings are source commit
`ca939cd3e097ebadb6adbea6d2778e2eff71da73` and integration commit
`8af4af0e5ceea8062b65ac06870cabf789567053`. The direct source baseline for
this successor is `8af4af0e5ceea8062b65ac06870cabf789567053`; the source
commit is integrated later by an ordinary two-parent merge into the current
`master` line.

The schemas also carry the S16 successor-gate digest as adjacent currentness
background. S16 is not this source commit's Git-topology predecessor, is not
runtime evidence, and cannot satisfy any prerequisite or owner decision.

## Nonclaims

This pack does not:

- implement or bind a production authority verifier, managed adapter,
  self-hosted adapter, or STOP-control set;
- collect, authenticate, accept, retain, or clean up real evidence;
- bind a provider endpoint, lab profile, trust root, key version, credential,
  broker lease, resource scope, cost budget, trusted-time source, runner
  process, session, channel, schedule, row set, reviewer, custodian, or owner;
- access secrets, provider APIs, paid resources, production services, or real
  experiment rows;
- launch the fault-injection runner, inject a fault, deploy a component, or
  create runtime or experiment output;
- make synthetic fixtures into evidence or make offline conformance into
  prerequisite satisfaction;
- record an owner decision or represent a positive runtime-admission decision;
- authorize runtime admission, condition output, output permit, scientific
  claims, application claims, or any other downstream gate;
- act as an evidence receipt, execution authority, output permit, runtime
  admission, security approval, provider attestation, or owner signature.

The four downstream gates remain separately unauthorized:

1. `CONDITION_OUTPUT_GATE`
2. `OUTPUT_PERMIT_GATE`
3. `SCIENTIFIC_CLAIM_GATE`
4. `APPLICATION_CLAIM_GATE`

## Artifact binding

| Artifact | Path | SHA-256 |
|---|---|---|
| Evidence packet Draft 2020-12 schema | `docs/design/fixtures/biocortex-ab-track-b-reference-provider-fault-injection-runner-runtime-prerequisite-evidence-packet-schema-v1.json` | `121c66331f159539722acb8f173696811487d8b76b9da07ab9d83340e28277d3` |
| Owner decision Draft 2020-12 schema | `docs/design/fixtures/biocortex-ab-track-b-reference-provider-fault-injection-runner-owner-decision-packet-schema-v1.json` | `7845de2ac7d1f069fd550f5625a1593c0a093563acbe1be1855bf7df0f3d4436` |
| Schema and validator-double implementation | `scripts/eval/biocortex_ab_track_b_reference_provider_fault_injection_runner_runtime_prerequisite_evidence_packet_schemas_and_offline_validator_doubles_v1.py` | `29a4b67049429c09981f1742f072a3fe382f381259fa238b69041b3d46939351` |
| Independent checker | `scripts/eval/check_biocortex_ab_track_b_reference_provider_fault_injection_runner_runtime_prerequisite_evidence_packet_schemas_and_offline_validator_doubles_v1_pack.py` | `d1f3f93a8808cce859415282fc757ef2a11a64fde165f7c37247437c8ea5cee7` |
| Synthetic fixture | `scripts/eval/fixtures/biocortex_ab_track_b_reference_provider_fault_injection_runner_runtime_prerequisite_evidence_packet_schemas_and_offline_validator_doubles_v1_pack_synthetic_v0.json` | `236839e4a8e831a84ef11c089cbd624152ddb456e583c2c414ece6c5ebb09f97` |
| Frozen TSV oracle | `scripts/eval/fixtures/biocortex_ab_track_b_reference_provider_fault_injection_runner_runtime_prerequisite_evidence_packet_schemas_and_offline_validator_doubles_v1_pack.expected.v0.tsv` | `24317b383b71933f206331f5629e1e6e0ea09a8e0ba8372ee6fb2b40a64c4210` |

## Next boundary

`REFERENCE_PROVIDER_MANAGED_AND_SELF_HOSTED_FAULT_INJECTION_RUNNER_V1_RUNTIME_PREREQUISITE_EVIDENCE_PACKET_OFFLINE_INTEGRATION_AND_PRODUCTION_EVIDENCE_INGESTION_BOUNDARY_REVIEW`

That successor may integrate the 16 schemas and validator doubles into one
deterministic offline aggregate and freeze the authentication, custody,
freshness, replay, and owner-handoff boundary that any future production
evidence ingestion path would have to cross. It still may not collect or
accept real evidence, bind an endpoint or credential, contact a provider,
launch the runner, record an owner decision, grant runtime admission, or
authorize any downstream output or claim.
