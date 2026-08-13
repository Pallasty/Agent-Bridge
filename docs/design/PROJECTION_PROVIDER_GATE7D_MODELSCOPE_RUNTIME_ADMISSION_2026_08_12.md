# Projection Provider Gate 7D: ModelScope Runtime Admission Contract

Date: 2026-08-12

## Result

Gate 7D defines a fail-closed runtime admission template for the public
ABot-World ModelScope Studio. It is a policy packet and validator, not an
execution permit, runtime caller, MCP tool, or deployment authorization.

The packet binds the proven Gate 7A-7C evidence to five controls:

1. A fresh `AuthorityDecision` must be approved, owner-confirmed, scoped to
   `external_write`, and paired with a single-use nonce. Readiness occurs before
   authority consumption.
2. At most one session may run. Busy requests are rejected without a queue.
3. Every session has a 180-second hard deadline. Cancellation requests Studio
   stop and verifies iframe removal within 15 seconds; ambiguous teardown blocks
   another session.
4. Prompts retain only a digest, session identifiers are discarded after stop,
   transport frames are ephemeral, and only explicitly selected artifacts may
   persist.
5. A rollout requires a validated artifact hash and remains
   `simulated.generated`, `not_verified`, and non-canonical.

## Machine-readable packet

```text
docs/design/evidence/modelscope_abot_gate7d_runtime_admission_2026_08_12.json
```

Validation is offline and non-actuating:

```text
python3 scripts/modelscope_abot_provider.py \
  --validate-admission-packet \
  docs/design/evidence/modelscope_abot_gate7d_runtime_admission_2026_08_12.json
```

The validator rejects implicit owner authority, multiple active sessions,
queueing, unbounded deadlines, retained transport frames, truth promotion,
default exposure, MCP registration, or any claim that runtime is already
admitted.

## Current boundary

`admission_contract_ready=true` means the next implementation gate has a stable
input contract. It does not mean a live authority exists or that execution is
allowed. The checked-in packet therefore fixes these fields:

```text
execution_authorized=false
runtime_admitted=false
mcp_registered=false
deployment_authorized=false
```

## Verdict

`GATE7D_MODELSCOPE_RUNTIME_ADMISSION_CONTRACT_READY_EXECUTION_NOT_AUTHORIZED`

The next gate is Gate 7E: implement a default-off preflight adapter that accepts
the admission packet plus a candidate authority envelope, evaluates readiness
and policy without consuming the nonce, and still performs no Studio start.
