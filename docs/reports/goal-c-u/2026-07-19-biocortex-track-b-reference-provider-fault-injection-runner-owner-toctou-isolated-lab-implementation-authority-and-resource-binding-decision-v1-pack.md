# BioCortex Track B T12 owner-TOCTOU implementation authority decision v1

Date: 2026-07-19

Status: one exact reversible isolated-lab T12 implementation becomes authorized
only after this decision is ordinarily integrated and its full gate passes.

## Exact authorized successor

The owner directive authorizes only:

`REFERENCE_PROVIDER_MANAGED_AND_SELF_HOSTED_FAULT_INJECTION_RUNNER_V1_OWNER_TOCTOU_SYNTHETIC_EXACT_T11_RECEIPT_TRACK_VALIDATION_OWNER_EPOCH_AND_DECISION_RECHECK_OWNER_EPOCH_VERIFIER_ISOLATED_LAB_IMPLEMENTATION`.

This decision activates but does not consume the authority. Only the exact
successor's ordinary integration and passing full gate may consume it. Scope is
reversible local code, public fixtures, tests and documentation only.

## Contract

The future public API has eighteen inputs: T11's fifteen pre-mode inputs,
separately injected owner-epoch policy, detached owner-epoch request, then
`mode`. Mode is syntactically last and observed first. Non-exact,
production, and subclass modes reject before every other input.

In `SYNTHETIC_KAT`, T11 is called exactly once; policy is observed next and
request last. The request is a closed two-integer object:

1. `validation_owner_epoch`;
2. `decision_recheck_owner_epoch`.

The policy has exactly two ordered rows, managed then self-hosted. Each row
matches exact T11 receipt content SHA-256, track, and both epoch integers.
Both epochs are nonnegative signed-int64 labels and must be exactly equal.
A mismatch means the synthetic owner/set state changed between validation and
decision recheck and rejects fail-closed with
`E_PRODUCTION_OWNER_IDENTITY_OR_WINDOW_FAILED`.

The public profiles bind T11 managed receipt
`63f0c26f10f42c923b55c4e651c001f7c38c42d9e25d7db772b4abbeadbe2ed8`
to epoch 41 and self-hosted receipt
`ce5af4f0ada753ed9a526909d071e5cb14959a6183f9169e67854d9ebcc4aee1`
to epoch 73.

## Boundary

Epochs are fixed synthetic labels; they are not owner identities, signatures,
credentials, authorizations, wall time, trusted time, provider state, durable
ledger state, or production decision windows. No ambient, monotonic, network,
provider, signed or trusted source may be accessed.

This does not authorize actual owner verification, owner signature, owner
window, action, output, custody, replay, real evidence, production admission,
runtime/provider effects, or T13+. It merely makes the T12 owner-change
threat testable in an isolated lab.

Resources: standard-library Python only, network/spend/credentials zero, one
worker, exactly one T11 predecessor call, policy <=64 KiB, request <=16 KiB,
private scratch <=64 MiB, two profiles only.

Current released surface remains nine components/T01-T11. The future exact
T12 successor alone may reach ten components/T01-T12. Production controls
remain 0/14, runtime threats 0/20, prerequisites 0/16 and evidence zero.
