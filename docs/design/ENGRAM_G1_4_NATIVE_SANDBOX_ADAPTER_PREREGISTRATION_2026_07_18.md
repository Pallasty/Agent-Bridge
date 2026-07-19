# Engram G1.4 Native Sandbox Adapter Preregistration

Date: 2026-07-18

Status: **PREREGISTERED DESIGN ONLY / DEFAULT OFF / NO NATIVE EXECUTION OR DATA AUTHORITY**

## Decision

Freeze a separate public-synthetic KAT interface before implementing any
native sandbox adapter. The future KAT may exercise one fixed public probe
against synthetic temporary roots on Darwin and Linux. This gate itself only
validates public JSON and repository dependency metadata.

The design adopts the useful part of grok-build's nono approach: narrow child
capabilities, exact dependency review, platform-specific policy construction,
and fail-closed support reporting. It does not adopt graceful unsandboxed
fallback or treat a successful policy-activation call as proof of confinement.

No candidate source or binary, private/FIT/development/sealed material, real
freeze capability, run plan, native policy, child process, external network,
database, live store, retrieval path, MCP tool, deployment, or runtime setting
is in scope.

## Why nono alone is insufficient

Agent-Bridge currently pins:

- `nono = { version = "=0.53.0", default-features = false }`;
- crates.io checksum
  `ae7eb523cc2036e9ad6527411c3da5dc2172dc454cc3447a03b910420a39bfee`.

That exact dependency is a useful filesystem/network building block. It is not
the complete G1.4 adapter.

On Darwin, local source review of the pinned crate found that its generated
Seatbelt profile allows `process-exec` and `process-fork`. Therefore nono's
filesystem/network policy cannot satisfy the preregistered
`subprocess_spawn=deny` canary without a separately reviewed process-creation
control that overrides or replaces that behavior. The implementation gate must
repeat the dependency-source and rule-order review; this design receipt is not
dependency-source attestation.

On Linux, Landlock is primarily a filesystem restriction and network support
depends on ABI and fallback behavior. The planned shape is outer bwrap mount
overlays plus inner nono/Landlock, with separately reviewed syscall or stronger
controls for process creation, wall clock, and external entropy. If those
controls cannot be made exact on the target host, that platform is unsupported.

The existing Agent-Bridge workspace sandbox deliberately leaves network open
and permits child execution. Its implementation and test evidence are a design
reference only; they are explicitly inadmissible as evidence for this stricter
offline KAT.

## Three proof owners

The future adapter must not collapse all evidence into one `sandbox active`
flag.

| Owner | Must prove |
| --- | --- |
| Native kernel | Filesystem allow/deny, network deny, process deny, plugin-open deny, wall-clock deny, and external-entropy deny |
| Launch boundary | Fixed executable/argv, closed environment, registered mount/scratch/cwd bindings, and closure of every unregistered inherited descriptor |
| Supervisor mediation | Closed bounded output, log policy, resource/timeout accounting, one-shot attempt ownership, receipt order, and cleanup |

One owner may not claim another owner's control. Platform support is false if
any required owner lacks an enforceable control or executable canary.

## Future fixed KAT interface

The future mode is exactly
`PUBLIC_SYNTHETIC_NATIVE_SANDBOX_ADAPTER_KAT`. It remains default-off and
requires an explicit boolean enable plus a public-synthetic fixture marker.
The implementation gate must register immutable hashes for probe source, build
artifact, dependency tree, policy, mounts, environment, output schema, and
resource budget.

The probe must accept neither an arbitrary path nor a command/environment
payload. It may touch only per-attempt synthetic roots and sentinels. The
network canary may target only a loopback endpoint owned by the KAT supervisor;
external network is forbidden even for controls.

The closed phase order is:

1. artifact preflight;
2. one-shot claim;
3. platform support;
4. policy compile;
5. policy apply;
6. active attestation;
7. negative controls;
8. allowed canaries;
9. denied canaries;
10. cleanup; and
11. receipt finalization.

The run ID is consumed before attempt-specific validation. Any unsupported
primitive, compile/apply/active fault, canary mismatch, timeout, crash, schema
fault, resource fault, cleanup fault, or ambiguous control invalidates the
entire attempt. Selective retry and partial rerun are forbidden.

## Fourteen canaries

The first three must be allowed:

1. candidate-code read, represented only by the registered public probe root;
2. dependency read, represented only by its registered public dependency root;
3. ephemeral scratch write.

The remaining eleven must be denied:

1. repository metadata read;
2. private manifest read;
3. live-store read;
4. network connect;
5. subprocess spawn;
6. dynamic plugin load;
7. non-scratch write;
8. wall-clock read;
9. external-entropy read;
10. extra inherited-FD use; and
11. free-form output.

Every target is a synthetic sentinel or fixed public helper. Filesystem,
network, process, plugin, clock, and entropy canaries belong to native-kernel
evidence; inherited-FD denial belongs to the launch boundary; free-form output
denial belongs to supervisor mediation. Passing 13 of 14 is failure, not
degraded success.

## Liveness controls

A denied operation that would fail even without a sandbox is not evidence.
Every canary therefore needs a registered control proving that the probe and
synthetic target are live. Denied controls may run outside the target
enforcement only against the temporary synthetic resources. Network uses only
the supervisor's loopback endpoint; subprocess uses only a fixed inert helper;
output uses only a fixed public payload. Controls never read the actual
repository, a real private manifest, a live store, or an external network.

For each allowed canary, a separate mutant-policy control removes exactly that
grant and must observe denial. For each denied canary, the corresponding safe
synthetic operation must first succeed in its distinct control attempt before
the enforced denial is admissible. Control attempt IDs are distinct and bound
to the parent run; a control is never candidate/subject execution or an
unsandboxed fallback.

Control success proves canary liveness, not native confinement. Native proof
still requires the corresponding enforced attempt to produce the registered
denial.

## Darwin plan

The future Darwin adapter must bind, in reviewed order:

1. nono 0.53.0 Seatbelt filesystem/network rules;
2. an exact reviewed Seatbelt or stronger process-creation deny;
3. exact native clock and entropy controls;
4. launch-boundary FD/environment/mount/argv closure; and
5. supervisor output/resource/receipt mediation.

The implementation review must include `/private` aliases for `/var`, `/tmp`,
and `/etc`, rule ordering, mDNS/local-IPC exceptions, generated profile bytes,
and all process/clock/entropy/plugin canaries. If a supplementary control is
absent, the only result is `UNSUPPORTED_FAIL_CLOSED`.

## Linux plan

The future Linux adapter must bind, in reviewed order:

1. outer bwrap mount-namespace overlays;
2. inner nono 0.53.0 Landlock filesystem policy;
3. Landlock network restriction or the exact reviewed seccomp fallback;
4. exact reviewed process/clock/entropy syscall or stronger controls;
5. launch-boundary FD/environment/mount/argv closure; and
6. supervisor output/resource/receipt mediation.

It must report the Landlock ABI and network support actually used. Both outer
and inner filesystem denials need canaries, because success of one layer must
not hide absence of the other. No unsupported host may fall back to an
unsandboxed child.

## Receipts and trust anchor

The future closed receipt must bind the predecessor, contract, probe source and
build, platform, exact dependency/checksum, generated policy, mounts,
environment, output schema, resource budget, one-shot run, support/compile/
apply/active reports, all controls and canaries, cleanup, and verdict. Raw
paths, logs, environment values, and free-form probe text are forbidden from
the public receipt.

Each of the eleven phases has a distinct preregistered receipt schema and a
closed payload-field order. Artifact preflight, one-shot claim, platform
support, policy compile, policy apply, active attestation, controls, allowed
canaries, denied canaries, cleanup, and finalization may not substitute for one
another or collapse into one aggregate `all_true` report. Every event binds the
run, contract, evidence-source identity commitment, and immediately preceding
event. Missing, duplicate, reordered, or source-unbound evidence invalidates
the attempt. The final receipt explicitly carries
`authority_class=NONE_DESIGN_VALIDATION_ONLY`,
`production_admissible=false`, and `g1_4_execution_open=false`.

An append-only self-consistent hash chain does not authenticate its own
payload. The implementation gate must derive and freeze its expected chain
head before launching the probe, and its checker must independently construct
the expected chain. Even that process-local anchor remains public-KAT evidence
only. A real candidate runner still requires a separately reviewed durable,
authenticated, prelaunch anchor. This gate implements neither anchor nor
runner.

## Human audit and rollback

Routine design validation, an unchanged public-synthetic KAT, fail-closed
denial, and successful automatic rollback require no human approval. That is
the default for reversible work.

Manual safety audit is reserved for trust-boundary promotion: first real
capability/private-plan use, post-lock candidate or runner drift, access
widening, post-observation metric/resource/retry changes, unblinding or rerun,
sandbox/log/output/side-channel policy widening after preregistration or any
real-runner policy change, first real runner enablement, or suspected exposure.
It is not a per-run ceremony.

If automatic cleanup or rollback fails, the implementation must persist a
minimal durable lesson before any fresh run ID is attempted. The lesson may
contain reason codes and commitments, never raw candidate/private material.
The preregistered store class is
`agent_bridge_state_dir/engram_g14_public_synthetic_native_kat/rollback_lessons_v0`.
Only the supervisor writes versioned create-new records, fsyncs the record and
directory, reopens and verifies the durable bytes, and then acknowledges the
lesson. A missing or integrity-invalid lesson is absorbing and blocks every
new run claim.

## Registered artifacts

- contract:
  `scripts/eval/fixtures/engram_g14_native_sandbox_adapter_preregistration_contract_v0.json`;
- validator:
  `scripts/eval/engram_g14_native_sandbox_adapter_preregistration.py`;
- independent checker:
  `scripts/eval/check_engram_g14_native_sandbox_adapter_preregistration.py`;
- pinned shell entrypoint:
  `scripts/check-engram-g14-native-sandbox-adapter-preregistration.sh`.

The shell also pins the shared JSON helper and exposes two mandatory phases.
`--phase precommit` proves the entire current tree, index, worktree, and
untracked delta against base commit
`36d3e8a4f05caa2731dc8224b035e2f1ac4f4d73` is exactly the seven registered
documentation/evaluation paths. After commit, `--phase postcommit` requires a
non-base HEAD, a clean tracked/index/worktree/untracked state, and separately
compares base to HEAD against the same exact set. Any later path drift
invalidates this versioned gate. This is stronger than a symbol grep: no
generic, aliased, renamed, or symbol-free runtime change under `crates/` can
enter unnoticed.

Run:

```bash
scripts/check-engram-g14-native-sandbox-adapter-preregistration.sh --phase precommit
# After committing from a clean worktree:
scripts/check-engram-g14-native-sandbox-adapter-preregistration.sh --phase postcommit
```

## Authority boundary and only successor

The only positive facts are that the predecessor public harness is bound and
this native-adapter design is preregistered. Native implementation, native
execution, public KAT execution, candidate/private access, G1.4 execution,
result release, retrieval mutation, live write, deployment, and promotion all
remain false.

The only permitted successor is
`separate_public_synthetic_native_sandbox_adapter_kat_implementation_gate`.
That gate may implement and execute the fixed public probe on synthetic
temporary resources. It still may not accept candidate/private material,
consume real capability, run G1.4, or promote runtime behavior.
