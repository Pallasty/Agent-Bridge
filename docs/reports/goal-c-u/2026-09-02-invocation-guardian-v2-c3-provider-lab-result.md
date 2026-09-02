# Invocation Guardian v2 C3 provider lab result

Date: 2026-09-02

Status: **provider recovery vectors PASS; external provider evidence HOLD**

The default-off provider laboratory now exercises the frozen C3 transport and
receipt verifier with a fake remote-provider state machine. It proves:

- a commit followed by response loss is recovered only as `AlreadyCommitted`;
- a copied stale replica cannot move a guardian floor backwards;
- a failover advances exactly one epoch, starts at revision one, and continues
  from the prior head;
- token/scope conflict and unknown lookup fail closed.

Verification:

```text
cargo test -p ab-bridge --lib invocation_guardian_provider_lab_v2 \
  --features invocation-guardian-v2-provider-lab --no-default-features -j1
1 passed / 0 failed
git diff --check
PASS
```

The laboratory uses process-local memory and test signing keys. It provides no
external anti-rollback guarantee, provider account, endpoint, credentials, or
production authority and therefore does not satisfy C3.
