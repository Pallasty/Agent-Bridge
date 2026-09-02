# Invocation Guardian v2 C3 protected-witness contract result

Date: 2026-09-02

Status: **C3 CONTRACT PASS; external provider/deployment evidence HOLD; C3-C4 and production HOLD**

## Outcome

The repository now contains a default-off asynchronous protected-witness
contract and a monotonic signed-receipt verifier. It freezes the evidence
semantics required before an external provider can be admitted, without
shipping a provider client, endpoint, credential, durable backend, or
production constructor.

## Closed source-level invariants

- consume and lookup use a closed asynchronous transport contract;
- provider identity, key generation, namespace and request bindings are
  verified through the canonical C0 signed receipt;
- the guardian maintains a dynamic epoch/revision/head/provider-time floor;
- same-epoch commits must advance exactly one revision from the pinned head;
- failover must advance exactly one epoch, begin at revision one, and continue
  from the prior head;
- position rollback, history forks, provider-time rollback, excessive clock
  skew, epoch jumps and revision gaps fail closed;
- `AlreadyCommitted` remains verified evidence and never becomes freshness;
- denial and transport uncertainty return no dispatch authority;
- the production transport constructor remains hard-coded unavailable.

## Verification

```text
cargo test -p ab-bridge --lib invocation_guardian_protected_witness_v2 \
  --features invocation-guardian-v2-protected-witness-contract \
  --no-default-features -j1
5 passed / 0 failed

git diff --check
PASS
```

## Explicit HOLD boundary

- no external anti-rollback provider or provider account exists;
- no real provider time, failover, stale-replica or disaster-recovery evidence;
- no credentials, network endpoint, namespace provisioning or key rotation;
- no coupling to the canary permit or marker dispatch path;
- no C2 deployment-isolation execution evidence on this host;
- no service installation, restart, production canary or global enforcement.

The next admissible goal is a default-off provider adapter laboratory with a
fake remote service and recorded recovery/failover vectors. C3 cannot pass
until an independently operated external provider reproduces those vectors.
