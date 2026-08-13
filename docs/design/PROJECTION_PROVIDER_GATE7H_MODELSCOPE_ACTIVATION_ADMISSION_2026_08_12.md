# Projection Provider Gate 7H: ModelScope Activation Admission

Date: 2026-08-12

## Result

Gate 7H defines a default-off activation admission boundary for the Gate 7G
capability contract. It verifies the signed activation request, the Gate 7G
capability signature, the active Gate 7F lease, exact capability and lease
bindings, owner confirmation, explicit runtime opt-in, and a short expiry.

Only after all checks pass does it write one row to the local activation ledger.
The ledger is single-use per capability digest and activation ID. It records an
activation admission intent, not an executable capability.

## Atomic ledger

The activation row is written with `BEGIN IMMEDIATE` and is unique on both
`activation_id` and `capability_sha256`. It is bounded by the active Gate 7F
lease and cannot outlive it. A duplicate admission is rejected without a
second row. The ledger deliberately has no delete or reset path in this gate;
future capability consumption must be a separate transition.

## Admission requirements

The request must contain:

- exact provider, action, and endpoint;
- exact capability ID, capability digest, and Gate 7F lease ID;
- valid Gate 7G contract and active lease reference;
- HMAC-SHA256 request signature with caller-injected key;
- `owner_confirmation=true`;
- `runtime_opt_in=true`;
- a lifetime no longer than 30 seconds.

The default path remains closed because no request is admitted unless the
caller explicitly supplies the opt-in. This module does not read environment
files and does not infer consent from capability availability.

## Closed execution boundary

An admitted activation receipt still fixes:

```text
activation_consumed=false
execution_capability_issued=false
studio_start_called=false
execution_authorized=false
runtime_admitted=false
mcp_registered=false
```

There is no network request, subprocess, Studio start, prompt transport,
artifact creation, MCP registration, or deployment in Gate 7H.

## Evidence

```text
scripts/modelscope_abot_activation_admission.py
scripts/modelscope_abot_authority_store.py
tests/test_modelscope_abot_activation_admission.py
docs/design/evidence/modelscope_abot_gate7h_activation_admission_2026_08_12.json
```

## Verdict

`GATE7H_MODELSCOPE_ACTIVATION_ADMISSION_LEDGER_VERIFIED_NON_ACTUATING`

The next gate is Gate 7I: define single-use capability consumption against an
admitted activation row. It must remain separate from Studio invocation and
MCP registration.
