# BioCortex Track B runner v1 offline authority verifier and adapter doubles

## Outcome

The frozen runner authority and adapter contract now has a pure offline
implementation of its authority-verification boundary, private-capability
control ledger, nine experiment adapter doubles, and five independent STOP
control doubles. The decision is
`OFFLINE_AUTHORITY_VERIFIER_AND_ADAPTER_DOUBLES_PASS_RUNTIME_EXECUTION_REMAINS_BLOCKED`.

This is implementation evidence for synthetic control-plane behavior only. It
does not bind or call a provider endpoint, read a credential, provision a paid
resource, launch a runner or lab, create an experiment row, authorize condition
output, or define an output permit. The deterministic receipt contains zero
provider calls, wire attempts, credential accesses, runtime rows, experiment
rows, condition outputs, and output permits.

## Authority evidence is resolved and actively verified

Each of the nine conformance fixtures carries a distinct exact-run authority
bundle with five role-separated scope receipts. The verifier first applies the
frozen authority schema and intersection semantics, then resolves all 45
signature-verification receipts, raw signature bytes, and trust-policy public
keys from a duplicate-free in-memory allowlist. It verifies Ed25519 over the
raw 32-byte canonical-payload digest and does not trust
`signature_valid_true` by itself.

Every bundle also resolves separately signed trusted-time and row-currentness
evidence. Those 18 control receipts bind track, phase, suite, run, namespace,
assignment, profile, resource, credential, cost, revocation epoch, and the
strict calendar-valid UTC check time. Missing evidence, a hash mismatch, an
invalid signature, a role or principal mismatch, or a binding mismatch fails
closed before START.

The Ed25519 seeds are deterministic test data derived from domain labels. The
module has no key-loading, credential, environment, random, filesystem, or
provider interface, and the reference arithmetic is not production key
handling or provider validation.

## Private capability and control ledger

The executable test capability is exactly 32 private bytes retained only in a
nonserializable process-local object. The public bundle contains only its
frozen binding commitment. A wrong private value, wrong adapter, cross-track
operation, or mismatched ledger anchor is rejected.

The frozen prose makes the full capability commitment depend on the control
ledger record hash while also describing the ledger as containing a capability
commitment. A literal single-record construction would be cyclic. The offline
implementation closes that detail with two monotonic layers:

1. An immutable `UNUSED` ledger anchor binds the private-secret commitment,
   exact adapter, complete capability-binding hash, assignment, run,
   namespace, phase, track, state, revision, and STOP fence.
2. The anchor hash enters the frozen full capability commitment. The ledger
   binds that final commitment once, before any state transition, and forbids
   rebinding.

START is one exact in-memory CAS from `UNUSED` to `START_COMMITTED`; the one
allowed adapter call is a second exact CAS to `CALL_CONSUMED`. Duplicate START,
duplicate call, cross-adapter call, forbidden operation, malformed request,
and call after STOP all reject without widening authority. This construction
does not change the predecessor packet or turn the synthetic capability into a
runtime capability.

## Nine least-privilege adapter doubles

The implementation preserves the exact frozen interface, operation,
credential-class, forbidden-operation, and evidence-return catalogs:

| Track | Adapter double | Conformance operation |
|---|---|---|
| Managed | Spanner authority | Explicit serializable authority transaction |
| Managed | Cloud KMS signer | Exact 137-byte, exact-version signing shape |
| Managed | Managed fault proxy | Arm the exact assigned cut |
| Managed | Managed evidence collector | Collect allowlisted non-secret fields |
| Self-hosted | etcd authority | Linearizable exact read |
| Self-hosted | OpenBao Transit | Single non-batch, context-free exact input shape |
| Self-hosted | External restore witness | Current linearizable read |
| Self-hosted | Lab fault controller | Arm the exact assigned lab cut |
| Self-hosted | Self-hosted evidence collector | Collect allowlisted non-secret fields |

Each invocation returns only deterministic observation hashes and safe
counters. It returns no case classification, provider-processing assertion,
credential material, execution authority, output permit, or condition output.
The nine opaque credential-handle commitments are distinct, and none overlaps a
STOP credential class.

## Five STOP doubles and six-step absorbing order

The five STOP-only doubles are capability fence, fault disarm and egress
isolation, credential revocation, durable evidence retention, and scoped
resource cleanup. One successful STOP uses six ordered receipts because the
retention interface is used both before disarm and after revocation:

1. Fence the capability and block new calls.
2. Persist the current row and durable state.
3. Disarm the assigned cut and isolate assigned-run egress.
4. Revoke exact-run credential leases and confirm zero active commitments.
5. Confirm evidence and retention bindings.
6. Freeze assigned resources and perform reductive cleanup.

The STOP capability is separate from every experiment credential and remains
reductive-only. The conformance suite injects one failure at each of the five
interfaces. Every injected failure preserves the row and available evidence,
blocks continuation and rerun, emits one durable failure ID, requires manual
escalation, and terminates as `STOP_FAILED_QUARANTINED`. The successful path
terminates as `STOP_ABSORBING_COMPLETE`.

## Independent falsification

The pack checker independently verifies the exact 9+5 catalogs, credential
separation, deterministic receipt, canonical fixtures, artifact manifest, and
source AST purity. Its 115 directed negatives cover:

- 29 root authority bindings and public non-authority flags;
- 25 role-receipt identity, principal, nonce, permit, and trust-policy fields;
- five actively corrupted scope signatures and two corrupted control-evidence
  signatures that retain positive assertion fields;
- missing signature/currentness evidence and wrong private capability bytes;
- every adapter's forbidden, unknown, and malformed-request path;
- every STOP control's forbidden, experiment, and empty operation path; and
- unknown STOP trigger, reason, role, and cross-run STOP capability.

The source-purity check rejects filesystem, environment, clock-now, process,
network, dynamic-import, and random/entropy APIs. Normal and self-test modes
must emit byte-identical TSV under multiple Python hash seeds. The enclosing
Git gate also runs the predecessor's `fast` tier for routine checks and reserves
the predecessor's complete frozen-chain execution for its explicit
`full-replay` tier.

## Non-authorization boundary

The conformance receipt and manifest retain:

```text
provider_calls=0
wire_attempts=0
credentials_accessed=0
paid_resources_provisioned=0
runtime_rows=0
experiment_rows=0
condition_outputs=0
output_permits=0
side_effects_unlocked=NONE
receipt_is_execution_authority=false
receipt_is_output_permit=false
runtime_authority=false
```

`offline_authority_verifier_implemented=true`,
`offline_adapter_doubles_implemented=9`, and
`offline_stop_control_doubles_implemented=5` describe only this synthetic
implementation. `production_adapter_implemented=false`,
`execution_capability_emitted=false`, and `live_endpoint_bound=false` remain
explicit.

## Next unit

The next bounded decision point is
`REFERENCE_PROVIDER_MANAGED_AND_SELF_HOSTED_FAULT_INJECTION_RUNNER_V1_OFFLINE_INTEGRATION_AND_RUNTIME_ADMISSION_BOUNDARY_REVIEW`.
It may review offline integration completeness and enumerate still-missing
runtime prerequisites. It does not grant provider, credential, resource,
runner, deployment, output, or scientific authority.

## Artifact binding

- `scripts/eval/biocortex_ab_track_b_reference_provider_fault_injection_runner_offline_authority_and_adapter_doubles_v1.py`: `aa2682bd659723fda6cf3ca650690c1bebfd7f01eee0612507903409c75d2785`
- `scripts/eval/check_biocortex_ab_track_b_reference_provider_fault_injection_runner_offline_authority_and_adapter_doubles_v1_pack.py`: `ed11f6d6c31812a70520a7fe30d7a5984a4e429598e102aa8540a18f2398789b`
- `scripts/eval/fixtures/biocortex_ab_track_b_reference_provider_fault_injection_runner_offline_authority_and_adapter_doubles_v1_pack_synthetic_v0.json`: `d480e337fbe0aad073c9250540898d3829c1a862c704fedc478e2c6c9dabe34b`
- `scripts/eval/fixtures/biocortex_ab_track_b_reference_provider_fault_injection_runner_offline_authority_and_adapter_doubles_v1_pack.expected.v0.tsv`: `df468939b9cd8c0d1f5df9e4ddef1e00dcd5834a6b5bbcd683e6969ae9cbf303`
- `docs/design/fixtures/biocortex-ab-track-b-reference-provider-fault-injection-runner-adapter-contract-v1.json`: `d602d9f14f662145bd12f33304b2800bb9601ff4fd76634eb56c41b86aa17201`
- `docs/design/fixtures/biocortex-ab-track-b-reference-provider-fault-injection-runner-authority-receipt-schema-v1.json`: `faea2234635441b0bc043b5d605a449decc61cc854e708f705f7bb09d58a7b90`
- `docs/design/fixtures/biocortex-ab-track-b-reference-provider-fault-injection-runner-stop-receipt-schema-v1.json`: `7657cd25a9abf4037ce5eb4c403db36aebf4b43deb232886e62ff4afe9d45c36`
- `scripts/eval/biocortex_ab_track_b_reference_provider_fault_injection_runner_authority_and_adapter_contract_v1.py`: `38b0e31504b72f961baec7e037a9340a334d3655aff2ce4d90fd01db4afb45a3`
- `scripts/eval/check_biocortex_ab_track_b_reference_provider_fault_injection_runner_authority_and_adapter_contract_v1_pack.py`: `c8f2258f9f8bac956958d6ebd011790814b6df3bad7f72213dd8241add7b4605`
- `scripts/eval/fixtures/biocortex_ab_track_b_reference_provider_fault_injection_runner_authority_and_adapter_contract_v1_pack_synthetic_v0.json`: `75259e4d211d40d1b00caccd4b13ca593363884b507a59cd2b57b55c462f6300`
- `scripts/eval/fixtures/biocortex_ab_track_b_reference_provider_fault_injection_runner_authority_and_adapter_contract_v1_pack.expected.v0.tsv`: `948842558a2be55a10660305758db5532ae89ec8b3340338c989befb26d5ce4b`
- `scripts/eval/fixtures/biocortex_ab_track_b_reference_provider_fault_injection_runner_authority_and_adapter_contract_v1_pack_v0.json`: `ff7cae32c8f19df080e40724ff353126c57caad1e23d957e467d490519738b12`
- `docs/reports/goal-c-u/2026-07-15-biocortex-track-b-reference-provider-fault-injection-runner-authority-and-adapter-contract-v1-pack.md`: `d64aabfc79b74819504997f11ced9c6bfeca3136e1c7248aec57259f3fae89de`
- `scripts/check-biocortex-ab-track-b-reference-provider-fault-injection-runner-authority-and-adapter-contract-v1-pack.sh`: `de303a52993d06e54fd9582f34a9cfcf65a4181889d976d4bd595a1150f207d6`
