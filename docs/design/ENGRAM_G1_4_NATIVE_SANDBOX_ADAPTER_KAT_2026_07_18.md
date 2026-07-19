# Engram G1.4 public-synthetic native sandbox adapter KAT

Date: 2026-07-18

Status: **implemented as a validated negative KAT; platform unsupported; no
authority**.

## Decision

The preregistered successor was implemented only far enough to answer the
native-control viability question with real public code. The answer is
fail-closed: the reviewed Darwin and Linux primitive plans cannot prove denial
of every wall-clock path. This gate therefore does not implement or attest a
complete native adapter, does not run the full 14-canary suite, and does not
open G1.4.

The terminal verdict is:

`REJECTED_FAIL_CLOSED_WALL_CLOCK_UNCONFINED_NO_AUTHORITY`.

This is a useful result rather than a degraded success. A sandbox that denies a
direct syscall while leaving libc, vDSO, or the Darwin commpage readable does
not satisfy the registered `wall_clock_read = deny` capability. The runner may
not silently weaken that capability, substitute a synthetic attestation, or
fall back to unsandboxed execution.

## Exact implementation surface

The KAT is a default-off, standard-library supervisor around one fixed public C
probe:

- `scripts/eval/fixtures/engram_g14_native_sandbox_adapter_probe_v0.c` accepts
  only `clock-control` and `clock-filtered`;
- it emits only `clock_mask=<unsigned decimal>\n`, bounded to 64 stdout bytes;
- it accepts no path, command, environment, candidate, corpus, capability, or
  private-material argument;
- the supervisor closes stdin and unregistered file descriptors, supplies a
  fixed environment and argv, bounds stdout/stderr and time, and uses a fresh
  synthetic root;
- the public result contains commitments and booleans, never raw paths, probe
  text, environment values, or platform error logs.

The implementation is intentionally outside runtime crates. It registers no
MCP tool, executor, daemon path, retrieval mutation, store write, or deployment
surface.

## Native viability finding

On Darwin, the KAT distinguishes three facts:

1. an unsandboxed fixed control proves that the clock probe is live;
2. a Seatbelt syscall filter can deny the direct `gettimeofday` syscall while
   libc/commpage clock paths remain readable;
3. a symbolic `(deny system-clock)` rule is rejected by the installed Seatbelt
   profile compiler rather than enforcing a complete clock capability.

The third control is accepted as unambiguous only with empty stdout, return
code 65, bounded stderr, and the allowlisted `unbound variable: system-clock`
diagnostic shape. Any other nonzero return, reason, overflow, or extra free-form
text invalidates the attempt instead of being laundered into "unsupported".

On Linux, the fixed probe installs a closed seccomp-BPF filter for direct
`clock_gettime`, `clock_gettime64`, `gettimeofday`, and `time` syscalls. A
remaining libc/vDSO path is terminal evidence that syscall filtering alone is
not complete wall-clock confinement.

The test does not claim that no stronger OS or virtualization design can ever
deny time. It proves the narrower and decision-relevant statement: the
preregistered nono/Seatbelt or nono/Landlock plus ordinary syscall-filter plan
is insufficient as currently specified.

## What remains valuable from nono

The exact `nono = 0.53.0` dependency and crates.io checksum remain pinned and
useful for a narrower role:

- filesystem allow/deny construction;
- network denial where the platform reports and proves the needed support;
- irreversible in-process restriction after the launch boundary is closed;
- platform support reporting that can feed a larger supervisor-owned proof.

It is not admissible as the entire G1.4 sandbox. In particular, its current
Darwin profile generation permits process execution/fork, and filesystem plus
network restriction does not prove process, plugin, wall-clock, entropy,
inherited-FD, or bounded-output controls. The existing Agent-Bridge workspace
sandbox is intentionally broader and is excluded as KAT evidence.

## One-shot and prelaunch anchoring

The supervisor consumes the fixed run ID before attempt-specific build or probe
execution. It then:

1. builds the pinned source with fixed compiler argv inside a fresh synthetic
   root;
2. constructs the exact expected 11-receipt negative chain;
3. durably writes an unauthenticated public-synthetic prelaunch anchor before
   launching the probe;
4. executes the fixed platform controls and compares their closed observation
   matrix to the preregistered negative expectation;
5. cleans and verifies the synthetic root before releasing the final receipt.

The anchor uses create-new, file fsync, directory fsync, and reopen verification.
It proves that this process committed to the expected negative chain before the
probe ran. It is explicitly `authenticated = false`; self-consistent hashes are
not authenticity or production authority. A real candidate runner would still
need a separately designed durable authenticated anchor.

## Receipt state machine

Exactly one closed receipt is emitted for each preregistered phase, in order:

1. `artifact_preflight`
2. `one_shot_claim`
3. `platform_support`
4. `policy_compile`
5. `policy_apply`
6. `active_attestation`
7. `negative_controls`
8. `allowed_canaries`
9. `denied_canaries`
10. `cleanup`
11. `receipt_finalize`

Platform support is false and terminal. The later execution receipts are still
present for closed accounting, but policy compile/apply/active and both canary
groups are explicitly false with zero observed canaries. They are not fallback
execution and cannot be interpreted as partial success.

Every event binds the run commitment, contract, evidence-source identity,
embedded payload, previous event, and its own hash. The final result exposes
the chain head. The independent checker also demonstrates that a fully
rehashed forged chain can be internally consistent; it is rejected because it
does not match the prelaunch anchor.

## Rollback lesson interlock

The durable namespace is:

`agent_bridge_state_dir/engram_g14_public_synthetic_native_kat/`.

Before temporary work begins, the supervisor writes a rollback obligation.
Normal verified cleanup removes it with directory fsync. If cleanup fails, a
minimal lesson is written under `rollback_lessons_v0` using one record per
create-new file, file and directory fsync, and reopen verification. Only after
that lesson is durable may the obligation be cleared. A missing, malformed, or
unwritable lesson leaves the obligation in place and blocks every new claim.

The lesson contains only hashes, phase/reason enums, sequence, and residue
count. It contains no raw path, candidate/private data, logs, environment, or
free-form text.

## Human safety audit boundary

No per-run human approval is needed for this unchanged public-synthetic,
reversible, fail-closed KAT. A denial also needs no approval. Automatic cleanup
is mandatory; cleanup failure produces the durable lesson above.

Human safety review becomes a gate only before a new trust-boundary claim, such
as:

- adopting a stronger clock-isolation primitive or widening the native policy;
- first real candidate/freeze capability or private run-plan access;
- changing source, compiler, dependency, policy, metrics, retries, outputs, or
  side-channel assumptions after a lock or observation;
- first real protocol-runner enablement, unblinding/rerun, or suspected
  exposure.

The negative KAT does not infer that such an audit happened and does not open a
successor automatically. The only permitted next action is a separate design
and security review for a stronger clock-isolation primitive.

## Verification

Before commit:

```bash
scripts/check-engram-g14-native-sandbox-adapter-kat.sh --phase precommit
```

After the exact nine-path change is committed from a clean worktree:

```bash
scripts/check-engram-g14-native-sandbox-adapter-kat.sh --phase postcommit
```

The integrated checker performs the real host KAT, independent receipt
verification, default-off and CLI-closure checks, mutation tests, one-shot
replay denial, output redaction checks, rollback-failure lesson persistence,
and unresolved rollback-obligation / lesson-write-failure interlock tests.

## Nonclaims

This gate does not claim or authorize:

- a complete native sandbox adapter;
- native enforcement of all 14 canaries;
- candidate source/configuration/binary access;
- fit, development, sealed, corpus, or other private data access;
- real freeze capability consumption or G1.4 execution;
- production admission, deployment, retrieval mutation, live-store writes,
  unblinding, release, or runtime promotion.
