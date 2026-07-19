# BioCortex Track B T11 clock-skew verifier v1

Date: 2026-07-19

Status: exact reversible isolated-lab T11 implementation candidate. Authority is
consumed only by this exact successor's ordinary integration and passing full
gate.

## Scope

This component implements exactly
`REFERENCE_PROVIDER_MANAGED_AND_SELF_HOSTED_FAULT_INJECTION_RUNNER_V1_CLOCK_SKEW_SYNTHETIC_EXACT_T10_RECEIPT_TRACK_VALIDATION_REFERENCE_TIME_DECISION_RECHECK_REFERENCE_TIME_AND_MAXIMUM_CLOCK_SKEW_SECONDS_VERIFIER_ISOLATED_LAB_IMPLEMENTATION`.

It has sixteen public inputs: T10's thirteen non-mode inputs, separately
injected clock-skew policy, detached clock-skew request, and exact mode last.
Mode is observed first; only `SYNTHETIC_KAT` is accepted. T10 is called
exactly once, policy is decoded next, and request last.

## Frozen binding and arithmetic

The policy has exactly two ordered profiles, managed then self-hosted. A profile
matches the exact T10 receipt content hash, T10 track, validation reference,
decision recheck reference and maximum skew. The detached request is a closed
three-field nonnegative signed-int64 object. Maximum skew is at most 300.

The verifier rejects reference inversion, either absolute T10 validation or
decision label skew above the bound, and positive future observation offsets
above the bound. Managed deliberately tests a five-second future observation
against the validation reference; self-hosted tests the opposite direction.

All labels are public synthetic integers. The verifier accesses no wall,
monotonic, network, provider, signed or trusted time.

## Boundary

The integrated successor may raise the isolated-lab surface to nine components
covering T01–T11 and consumes this one local authority. It implements no
production ingestion control, runtime prerequisite, provider operation, real
evidence, durable custody/replay, output claim, owner TOCTOU or T12 behavior.
Production controls remain 0/14, runtime threats 0/20 and prerequisites 0/16.

## Verification

The independent checker exercises two positive tracks, 99 directed negatives,
12 source/AST guards, 20 fixture/schema guards and 16 self-tests. The receipt
is closed to 98 fields. All effects are reversible local code, fixtures, tests
and documentation.
