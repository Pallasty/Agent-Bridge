# BioCortex Track B runner v1 offline integration and runtime-admission boundary review

## Outcome

The managed and self-hosted runner contract now has a deterministic offline
integration review over the previously landed authority verifier, nine
experiment adapter doubles, and five STOP-control doubles. The decision is
`OFFLINE_INTEGRATION_COMPLETE_FOR_SYNTHETIC_CONFORMANCE_RUNTIME_ADMISSION_BLOCKED_FAIL_CLOSED`.

This is a review result, not a runtime-admission result. The review confirms
that 15 synthetic components have the exact expected conformance shape while
also recording that zero production components are bound. It does not bind a
provider endpoint, access a credential, provision a resource, launch a runner,
create a runtime or experiment row, authorize deployment, or grant runtime
authority.

## Integration review grain

The component matrix has one authority verifier, nine experiment adapters, and
five STOP controls:

| Component class | Synthetic components reviewed | Synthetic complete | Production bound |
|---|---:|---:|---:|
| Offline authority verifier | 1 | 1 | 0 |
| Managed adapter doubles | 4 | 4 | 0 |
| Self-hosted adapter doubles | 5 | 5 | 0 |
| STOP-control doubles | 5 | 5 | 0 |
| Total | 15 | 15 | 0 |

Every matrix row explicitly carries
`synthetic_implemented=true`, `production_bound=false`, and
`runtime_authority_contribution=false`. The phrase "offline integration
complete" therefore means only that all expected synthetic components compose
under the frozen conformance contract. It cannot be interpreted as production
readiness or admission.

## Runtime prerequisites remain unsatisfied

The review freezes 16 prerequisites. Every row has a distinct prerequisite ID,
owner class, required evidence description, fail-closed status, and
`satisfied=false`.

| # | Runtime prerequisite | Current status |
|---:|---|---|
| 1 | Production authority verifier implementation | `MISSING_NOT_IMPLEMENTED` |
| 2 | Four managed production adapters | `MISSING_NOT_IMPLEMENTED` |
| 3 | Five self-hosted production adapters | `MISSING_NOT_IMPLEMENTED` |
| 4 | Five production STOP controls | `MISSING_NOT_IMPLEMENTED` |
| 5 | Trust root, key version, role, and revocation policy | `MISSING_NOT_BOUND` |
| 6 | Exact provider endpoint and profile identity | `MISSING_NOT_BOUND` |
| 7 | Credential lease, scope, and revocation broker | `MISSING_NOT_BOUND` |
| 8 | Resource scope, cost ceiling, and budget authority | `MISSING_NOT_BOUND` |
| 9 | Durable single-use control ledger and atomic CAS | `MISSING_NOT_PROVEN` |
| 10 | Signed trusted-time and currentness evidence | `MISSING_NOT_BOUND` |
| 11 | Runner build, process, session, and channel provenance | `MISSING_NOT_BOUND` |
| 12 | Fault disarm, egress isolation, and emergency STOP drill | `MISSING_NOT_PROVEN` |
| 13 | Durable evidence retention and reductive cleanup drill | `MISSING_NOT_PROVEN` |
| 14 | Real preregistered schedule, assignment, and row custody | `MISSING_NOT_BOUND` |
| 15 | Independent security, failure-mode, canary, and rollback review | `MISSING_NOT_APPROVED` |
| 16 | Explicit owner runtime-admission decision | `MISSING_OWNER_DECISION` |

The prerequisite list is conjunctive. Missing one row keeps admission blocked;
the current receipt records `0 / 16` satisfied. The offline reviewer has no API
for changing a prerequisite to satisfied and no production evidence resolver.

## Downstream authority remains separate

Runtime admission would not itself authorize condition output, an output
permit, a scientific claim, or an application claim. Those four gates are
listed separately and each carries `authorized=false` and
`SEPARATE_NOT_AUTHORIZED`.

The receipt also retains all of the following explicit nonclaims:

```text
provider_endpoint_bound=false
provider_called=false
wire_attempted=false
credentials_accessed=false
paid_resource_provisioned=false
production_authority_verifier_implemented=false
production_adapter_implemented=false
production_stop_control_implemented=false
real_runner_launched=false
runtime_row_created=false
experiment_row_created=false
condition_output_authorized=false
output_permit_defined=false
runtime_admission_ready=false
runtime_admission_granted=false
runtime_authority=false
deployment_authorized=false
scientific_claim_authorized=false
application_claim_authorized=false
review_receipt_is_execution_authority=false
review_receipt_is_output_permit=false
offline_review_is_runtime_admission=false
side_effects_unlocked=NONE
```

`BoundaryNonClaims.all_explicit()` checks the exact 23-field closed-world shape,
the exact Boolean types, every Boolean value being false, and
`side_effects_unlocked=NONE`. A missing field, extra field, truthy substitute,
integer-as-Boolean value, or non-NONE side-effect marker fails closed.

## Independent falsification

The standard-library-only checker reloads the reviewer by exact path, verifies
canonical duplicate-free JSON and deterministic TSV, recomputes predecessor
artifact hashes, independently checks the receipt matrices and hashes, and
enforces source AST purity. The reviewer source is denied filesystem,
environment, current-clock, process, network, dynamic-import, random, and
entropy APIs.

The directed suite rejects 186 mutations:

- 4 fixture-root and closed-world mutations;
- 46 nonclaim escalation or omission mutations;
- 16 track, adapter, and STOP catalog mutations;
- 48 runtime-prerequisite identity, status, and satisfaction mutations;
- 12 downstream-gate identity, status, and authorization mutations;
- 11 expected-oracle mutations;
- 14 predecessor receipt mutations;
- 17 predecessor boundary mutations;
- 12 predecessor result mutations; and
- 6 predecessor root-decision and track mutations.

These are deterministic regression controls, not exhaustive formal proof and
not a security certification.

## Git and replay boundary

The enclosing shell gate requires an exact seven-path all-add source commit
whose sole raw parent is integrated baseline
`a1c9469e9a14cd73159d34974f0e99714ce5a1f0`. A descendant state must contain an
ordinary two-parent merge of that exact source commit. The gate rejects shallow
history, replace refs, grafts, dirty worktrees, nondefault index flags, path
aliases, mode drift, and worktree/index/HEAD/source-blob divergence.

Routine `fast` validation executes the predecessor fast tier. Release-grade
`full-replay` executes the predecessor periodic full frozen-chain replay. Only
the latter may emit the full-replay integration marker. Neither tier grants
runtime authority.

## Deterministic receipt

```text
tracks_reviewed=2
integration_component_count=15
synthetic_components_complete=15
production_components_bound=0
runtime_prerequisite_count=16
runtime_prerequisites_satisfied=0
runtime_prerequisites_missing=16
downstream_separate_gate_count=4
nonclaim_field_count=23
all_nonclaims_explicit=true
runtime_admission_ready=false
runtime_admission_granted=false
runtime_authority=false
provider_calls=0
wire_attempts=0
credentials_accessed=0
runtime_rows=0
experiment_rows=0
condition_outputs=0
output_permits=0
side_effects_unlocked=NONE
content_sha256=f57a891ccb4d9e2650ed898dea5ec20b9cee36d401f8f911cd10fe42bbaa16ad
```

## Next bounded unit

The next bounded unit is
`REFERENCE_PROVIDER_MANAGED_AND_SELF_HOSTED_FAULT_INJECTION_RUNNER_V1_RUNTIME_PREREQUISITE_EVIDENCE_PLAN_AND_OWNER_DECISION_PREREGISTRATION`.
It may define an evidence-acquisition plan and a future owner decision packet.
It must remain preregistration-only and cannot implement production adapters,
bind credentials or endpoints, launch a runner, deploy, or record a positive
runtime-admission decision.

## Artifact binding

- Reviewer source: `0c63a8111b0a1ceb4eabe6c3bbab99ff87872ef95f9d433060be643b20a952d6`
- Independent checker: `2c42418dbf81f0034c4095b92b9857111fcc9f496272068f2ee7766b57e46c67`
- Synthetic fixture: `9104a4a3a41455d1293f7538a218d0454cb76cb423cfa7686931853f6a1dc756`
- Expected TSV: `fcbf33046f9049451bc4d11228e47de4da98e2dc6655d16833e143ec3ccfacb7`
- Predecessor manifest: `01f41e7a7a6760641bafc53b51fa6ea406ef18403bb7318b4f1c282f3b091d9b`
- Predecessor expected TSV: `df468939b9cd8c0d1f5df9e4ddef1e00dcd5834a6b5bbcd683e6969ae9cbf303`
- Predecessor reviewer implementation: `aa2682bd659723fda6cf3ca650690c1bebfd7f01eee0612507903409c75d2785`
- Predecessor checker: `ed11f6d6c31812a70520a7fe30d7a5984a4e429598e102aa8540a18f2398789b`
- Predecessor report: `01a2c9a617afb7a170cd52ad62e1e053ecb8b260cb64cbb929483489e4682dbc`
- Predecessor gate: `aa59a4f1ae0eb722a053779b79ab93f242b63747a54c48886f7abab463494925`
