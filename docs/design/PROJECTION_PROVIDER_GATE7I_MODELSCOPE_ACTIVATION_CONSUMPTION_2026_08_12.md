# Projection Provider Gate 7I: ModelScope Activation Consumption

Date: 2026-08-12

## Result

Gate 7I verifies and consumes one admitted activation exactly once. The
consumption transition requires the Gate 7G capability contract to validate and
the Gate 7H activation ledger row to match its capability digest and ID.

The state transition is an SQLite `BEGIN IMMEDIATE` update guarded by:

```text
activation_consumed = 0
execution_capability_issued = 0
expires_at_unix_ms > now
```

Only one caller can commit the transition. A transaction interruption rolls the
state back, leaving the activation retryable. A committed activation cannot be
consumed again.

## Closed execution boundary

Consumption produces a local receipt only. It does not issue an executable
capability, start Studio, send a prompt, create an artifact, register MCP, or
admit a runtime. The receipt fixes:

```text
activation_consumed=true
execution_capability_issued=false
studio_start_called=false
execution_authorized=false
runtime_admitted=false
mcp_registered=false
```

This deliberate state means the activation ledger proves single-use accounting,
not external execution permission.

## Fail-closed checks

Consumption rejects malformed or tampered capability contracts, invalid
capability signatures, missing or released leases, missing activation rows,
expired activations, capability digest drift, ID mismatch, and replay.

There is no network, subprocess, environment-file read, Studio API call, or MCP
registration in Gate 7I.

## Evidence

```text
scripts/modelscope_abot_activation_consumption.py
scripts/modelscope_abot_authority_store.py
tests/test_modelscope_abot_activation_consumption.py
docs/design/evidence/modelscope_abot_gate7i_activation_consumption_2026_08_12.json
```

## Verdict

`GATE7I_MODELSCOPE_ACTIVATION_CONSUMPTION_VERIFIED_NON_ACTUATING`

The next gate is Gate 7J: design an external execution adapter boundary. It
must remain separately gated and must not be inferred from this local receipt.
