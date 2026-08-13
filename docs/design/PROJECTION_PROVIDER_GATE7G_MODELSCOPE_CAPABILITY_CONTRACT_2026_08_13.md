# Projection Provider Gate 7G: ModelScope Capability Contract

Date: 2026-08-13

## Result

Gate 7G defines and validates a signed, bounded execution-capability contract
candidate. It references an authoritative Gate 7F claim and session lease, but
does not activate or consume an execution capability.

The contract binds:

- provider identity;
- capability ID;
- Gate 7F lease, candidate digest, and consumed nonce digest;
- the sole action `start_simulated_projection`;
- the sole endpoint `/on_click_start_ws`;
- a prompt SHA-256 digest without raw prompt content;
- a maximum 30-second contract lifetime, capped by the active lease lifetime;
- one concurrent session, no queue, no retry, and no retained transport frames.

## Authenticity and claim binding

The contract is authenticated with HMAC-SHA256 over its canonical content plus
the signature schema, algorithm, and `key_id`. Key material is caller-injected
and is neither loaded from configuration nor persisted by this module.

Contract construction and validation query the Gate 7F SQLite store for the
active lease. A released, expired, missing, or digest-mismatched lease fails
closed. A caller-provided claim alone is never sufficient.

## Non-admission boundary

This gate creates a contract candidate, not an executable bearer token. Every
valid contract fixes:

```text
activation_status=not_admitted
capability_contract_issued=true
execution_capability_issued=false
capability_consumed=false
studio_start_called=false
execution_authorized=false
runtime_admitted=false
mcp_registered=false
```

There is no CLI, MCP registration, network request, subprocess, provider start,
prompt transport, or artifact creation in this gate.

## Evidence

```text
scripts/modelscope_abot_capability_contract.py
tests/test_modelscope_abot_capability_contract.py
docs/design/evidence/modelscope_abot_gate7g_capability_contract_2026_08_13.json
```

The synthetic contract tests cover claim binding, signature tampering, wrong
keys, expiry, lease release, digest mismatch, exact operation scope, TTL caps,
raw-prompt exclusion, and closed runtime fields.

## Verdict

`GATE7G_MODELSCOPE_CAPABILITY_CONTRACT_VERIFIED_NOT_ADMITTED`

The next gate is Gate 7H: design capability activation admission and a separate
single-use activation ledger. Gate 7H must still remain non-actuating unless a
later gate explicitly admits a Studio execution path.
