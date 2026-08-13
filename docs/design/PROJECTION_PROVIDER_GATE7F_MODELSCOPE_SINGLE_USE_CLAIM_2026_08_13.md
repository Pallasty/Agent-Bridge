# Projection Provider Gate 7F: ModelScope Single-Use Claim

Date: 2026-08-13

## Result

Gate 7F implements a non-actuating, local authority-consumption kernel. It
authenticates one exact candidate envelope and atomically commits both:

1. a permanent authority/nonce consumption row; and
2. the provider's sole active session lease.

Both writes occur inside one SQLite `BEGIN IMMEDIATE` transaction with WAL and
`synchronous=FULL`. A transaction interruption rolls back both rows. A
committed nonce is never made reusable, including after normal release or
crash recovery.

## Authenticity boundary

The candidate is authenticated with HMAC-SHA256 over the canonical candidate
payload plus the authenticity schema, algorithm, and `key_id`. Unknown fields,
wrong keys, tampering, expiry, synthetic fixtures, and candidates that already
claim execution authority are rejected before store mutation.

The caller injects key bytes. The kernel never reads an environment file,
persists key material, logs the MAC, or exposes a CLI. Key provisioning and
custody therefore remain outside this gate.

## Atomicity and recovery

The database has two independent durability meanings:

- `consumed_authorities` is permanent replay protection.
- `provider_session_leases` is recoverable concurrency ownership.

Expired leases may be deleted after a crash. Their associated nonce rows stay
consumed, so any retry requires a new owner decision and a new nonce. A busy
provider rejects a second nonce before consuming it. Releasing a session also
does not release its nonce.

## Closed runtime boundary

The claim receipt fixes:

```text
execution_capability_issued=false
studio_start_called=false
execution_authorized=false
runtime_admitted=false
mcp_registered=false
```

There is no production CLI, MCP tool, provider start call, prompt transport, or
artifact creation in this gate. The committed evidence is a synthetic contract
receipt, not a live authority or runtime claim.

## Evidence

```text
scripts/modelscope_abot_authority_store.py
tests/test_modelscope_abot_authority_store.py
docs/design/evidence/modelscope_abot_gate7f_single_use_claim_2026_08_13.json
```

Coverage proves atomic rollback, exact-one-winner concurrency, replay rejection
after release, busy rejection without nonce consumption, lease recovery without
nonce recovery, candidate tamper rejection, expiry rejection, and synthetic
fixture rejection.

## Verdict

`GATE7F_MODELSCOPE_SINGLE_USE_CLAIM_KERNEL_VERIFIED_NON_ACTUATING`

The next gate is Gate 7G: define a bounded execution-capability contract that
can reference a committed claim without itself starting Studio. Runtime
admission, MCP registration, and deployment remain separately gated.
