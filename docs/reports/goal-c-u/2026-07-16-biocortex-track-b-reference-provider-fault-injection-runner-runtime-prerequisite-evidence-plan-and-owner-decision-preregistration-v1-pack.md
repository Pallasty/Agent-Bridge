# Track B runner runtime-prerequisite evidence plan and owner-decision preregistration v1

Date: 2026-07-16
Scope: synthetic, deterministic, offline preregistration only

## Decision

`RUNTIME_PREREQUISITE_EVIDENCE_PLAN_AND_OWNER_DECISION_PREREGISTERED_FAIL_CLOSED`

The predecessor established synthetic conformance while leaving all production
bindings absent and all 16 runtime prerequisites unsatisfied. This packet now
freezes how future evidence would have to be collected, validated, rejected,
and presented to the owner. It does not collect that evidence and cannot encode
a positive runtime-admission decision.

Current state:

| Measure | Value |
|---|---:|
| Tracks covered | 2 |
| Prerequisite plan rows | 16 |
| Evidence prerequisites before owner decision | 15 |
| Owner-decision prerequisite | 1 |
| Distinct owner classes | 15 |
| Distinct evidence classes | 16 |
| Evidence items present | 0 |
| Prerequisites satisfied | 0 / 16 |
| Positive decision representable | false |
| Downstream gates authorized | 0 / 4 |

## Evidence plan

Every row is `PREREGISTERED_NOT_COLLECTED`, with `evidence_present=false` and
`satisfied=false`. Collection methods beginning with `FUTURE_` are declarative
labels, not commands or permissions.

| # | Prerequisite | Owner | Evidence class | Future collection method | Freshness or binding rule |
|---:|---|---|---|---|---|
| 1 | `PRODUCTION_AUTHORITY_VERIFIER_IMPLEMENTED` | `IMPLEMENTATION_OWNER` | `AUDITED_BUILD_AND_TEST_EVIDENCE` | `FUTURE_CI_ATTESTATION_EXPORT` | exact source commit and toolchain digest |
| 2 | `PRODUCTION_MANAGED_ADAPTER_SET_IMPLEMENTED` | `MANAGED_PROVIDER_OPERATOR` | `MANAGED_ADAPTER_CONFORMANCE_EVIDENCE` | `FUTURE_MANAGED_SANDBOX_CONFORMANCE_RUN` | exact adapter build and provider profile |
| 3 | `PRODUCTION_SELF_HOSTED_ADAPTER_SET_IMPLEMENTED` | `SELF_HOSTED_LAB_OPERATOR` | `SELF_HOSTED_ADAPTER_CONFORMANCE_EVIDENCE` | `FUTURE_SELF_HOSTED_LAB_CONFORMANCE_RUN` | exact adapter build and lab profile |
| 4 | `PRODUCTION_STOP_CONTROL_SET_IMPLEMENTED` | `SAFETY_OPERATOR` | `STOP_CONTROL_FAILURE_INJECTION_EVIDENCE` | `FUTURE_ISOLATED_FAILURE_INJECTION_DRILL` | exact control build and test environment |
| 5 | `TRUST_ROOT_AND_KEY_VERSION_POLICY_BOUND` | `SECURITY_OWNER` | `TRUST_ROOT_POLICY_BINDING_EVIDENCE` | `FUTURE_SECURITY_POLICY_EXPORT` | exact trust root, key version, and policy revision |
| 6 | `PROVIDER_ENDPOINT_AND_PROFILE_IDENTITY_BOUND` | `PROVIDER_OPERATOR` | `PROVIDER_IDENTITY_BINDING_EVIDENCE` | `FUTURE_PROVIDER_CONFIGURATION_EXPORT` | at most 24 hours old and rechecked at decision |
| 7 | `CREDENTIAL_BROKER_LEASE_AND_REVOCATION_BOUND` | `CREDENTIAL_BROKER_OWNER` | `CREDENTIAL_LIFECYCLE_EVIDENCE` | `FUTURE_CREDENTIAL_BROKER_LEASE_DRILL` | at most 60 minutes old with zero active leases |
| 8 | `RESOURCE_SCOPE_AND_COST_BUDGET_AUTHORITY_BOUND` | `RESOURCE_AND_COST_OWNER` | `RESOURCE_AND_BUDGET_AUTHORITY_EVIDENCE` | `FUTURE_BUDGET_AND_RESOURCE_AUTHORITY_EXPORT` | at most 24 hours old and rechecked at decision |
| 9 | `DURABLE_CONTROL_LEDGER_AND_ATOMIC_CAS_PROVEN` | `AUTHORITY_STORE_OWNER` | `DURABLE_LEDGER_LINEARIZABILITY_EVIDENCE` | `FUTURE_LEDGER_CAS_AND_LINEARIZABILITY_DRILL` | exact authority-store build and configuration |
| 10 | `TRUSTED_TIME_AND_CURRENTNESS_EVIDENCE_BOUND` | `TIME_AUTHORITY_OWNER` | `TRUSTED_TIME_CURRENTNESS_EVIDENCE` | `FUTURE_SIGNED_TIME_CURRENTNESS_CAPTURE` | at most five minutes old and rechecked at decision |
| 11 | `RUNNER_BUILD_PROCESS_SESSION_AND_CHANNEL_PROVENANCE_BOUND` | `RUNNER_OPERATOR` | `RUNNER_PROVENANCE_EVIDENCE` | `FUTURE_RUNNER_PROVENANCE_ATTESTATION` | exact build, process, session, and channel |
| 12 | `FAULT_DISARM_EGRESS_ISOLATION_AND_EMERGENCY_STOP_PROVEN` | `SAFETY_OPERATOR` | `SAFETY_STOP_DRILL_EVIDENCE` | `FUTURE_INDEPENDENT_STOP_AND_EGRESS_DRILL` | at most seven days old and exact runner build |
| 13 | `DURABLE_EVIDENCE_RETENTION_AND_SCOPED_CLEANUP_PROVEN` | `EVIDENCE_CUSTODIAN` | `EVIDENCE_RETENTION_CLEANUP_EVIDENCE` | `FUTURE_RETENTION_REPLAY_AND_CLEANUP_DRILL` | at most seven days old and exact storage policy |
| 14 | `REAL_PREREGISTERED_SCHEDULE_ASSIGNMENT_AND_ROW_CUSTODY_BOUND` | `TRIAL_CUSTODIAN` | `TRIAL_SCHEDULE_AND_CUSTODY_EVIDENCE` | `FUTURE_PREREGISTERED_SCHEDULE_AND_CUSTODY_EXPORT` | exact trial, schedule version, and row set |
| 15 | `INDEPENDENT_SECURITY_FAILURE_MODE_AND_ROLLBACK_REVIEW_APPROVED` | `INDEPENDENT_REVIEWER` | `INDEPENDENT_SECURITY_REVIEW_EVIDENCE` | `FUTURE_INDEPENDENT_REVIEW_PACKET` | exact evidence-set hash and reviewer identity |
| 16 | `OWNER_RUNTIME_ADMISSION_DECISION_RECORDED` | `OWNER` | `OWNER_DECISION_EVIDENCE` | `FUTURE_OWNER_SIGNED_DECISION_PACKET` | same validated evidence hash within 30 minutes |

Dependencies are topological and closed-world. The final owner-decision row
depends on every one of the first 15 rows. Each row also freezes four specific
rejection reason codes, an exact validation rule, and the evidence description
inherited from the predecessor boundary review.

## Owner preregistration

The current decision vocabulary contains only:

- `PENDING_PREREQUISITE_EVIDENCE`
- `REJECTED_FAIL_CLOSED`

The current state is `PENDING_PREREQUISITE_EVIDENCE`. Owner identity is not
bound, no decision has been recorded, and the current evidence-set hash is
`NONE`. The authority rule is owner-exclusive after the independent-review
prerequisite validates; no agent may substitute for the owner.

The six frozen transitions are:

| Trigger | Result | Reason |
|---|---|---|
| Any evidence item missing | pending | `WAITING_FOR_ALL_EVIDENCE` |
| Any evidence item invalid | rejected | `EVIDENCE_VALIDATION_FAILED` |
| Any evidence item stale | rejected | `EVIDENCE_FRESHNESS_FAILED` |
| Provenance or scope mismatch | rejected | `EVIDENCE_BINDING_FAILED` |
| Owner identity or decision absent | pending | `OWNER_DECISION_PENDING` |
| Positive decision requested in this schema | rejected | `POSITIVE_DECISION_NOT_REPRESENTABLE` |

## Separate gates

The following gates remain independent and unauthorized even if a future
runtime-admission process eventually succeeds:

1. `CONDITION_OUTPUT_GATE`
2. `OUTPUT_PERMIT_GATE`
3. `SCIENTIFIC_CLAIM_GATE`
4. `APPLICATION_CLAIM_GATE`

## Nonclaims

`BoundaryNonClaims.all_explicit()` checks an exact 31-field closed-world shape.
Thirty fields must be exact booleans equal to `false`; the remaining field must
be `side_effects_unlocked=NONE`.

This packet does not:

- implement or bind a production verifier, adapter, or STOP control;
- bind an endpoint, profile, trust root, key, credential, resource, or budget;
- access a provider, credential, paid resource, or real row;
- collect or accept runtime-prerequisite evidence;
- bind owner identity or record an owner decision;
- launch a runner, create runtime or experiment rows, or deploy anything;
- authorize condition output, output permit, runtime admission, or downstream claims;
- act as an evidence receipt, execution authority, output permit, or runtime admission.

## Verification design

The independent checker performs exact fixture/oracle/manifest comparison,
closed-world schema checks, source AST purity checks, and directed mutation
rejection across every plan row, all nonclaims, owner state and transitions,
downstream gates, predecessor bindings, predecessor manifest, and current
manifest. The Git gate runs the checker under isolated `python -S -P`, multiple
hash seeds, exact source/integration topology, exact seven-path delta, and an
isolated predecessor replay.

Directed negative count: `434`.

## Artifact binding

| Artifact | SHA-256 |
|---|---|
| Reviewer | `e03b428797f9d2ea6235a7d4f730a11bd5aee9a07e6aa30fd965acac4dca0e18` |
| Independent checker | `047588e55b061663cd6915463503a28005a21166be0450e52105780a5b11cd16` |
| Synthetic fixture | `156b9a0357f1d5773fdd39be25d832e1d9e2e1df0d766b1947bbcc9cee118db3` |
| Frozen TSV oracle | `a0549882234f4d363714321a2e0d19ac9d78e76a4d34d49d94422e30c2d76ce7` |

## Next bounded unit

`REFERENCE_PROVIDER_MANAGED_AND_SELF_HOSTED_FAULT_INJECTION_RUNNER_V1_RUNTIME_PREREQUISITE_EVIDENCE_PACKET_SCHEMAS_AND_OFFLINE_VALIDATOR_DOUBLES`

That successor may define synthetic evidence packet schemas and offline
validator doubles. It still may not collect real evidence, bind endpoints or
credentials, launch the runner, deploy, or represent a positive runtime
admission decision.
