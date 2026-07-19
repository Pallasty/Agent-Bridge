# Engram G1.4 Native Sandbox Adapter Preregistration Result

Date: 2026-07-18

Verdict: **VALIDATED — DESIGN PREREGISTERED / DEFAULT OFF / AUTHORITY CLASS NONE**

## Delivered

- an immutable public JSON contract bound to the exact predecessor harness;
- an exact `nono 0.53.0` version/checksum/reference lock;
- separate native-kernel, launch-boundary, and supervisor proof ownership;
- Darwin Seatbelt and Linux bwrap/Landlock/seccomp fail-closed plans;
- the fixed 14-canary order and per-canary evidence owner;
- synthetic-only liveness controls for every canary;
- one-shot lifecycle, automatic cleanup, and durable rollback-lesson rule;
- prelaunch expected-head and future durable-anchor requirements;
- eleven distinct phase receipt schemas that reject aggregate `all_true`
  substitution;
- a supervisor-owned durable rollback-lesson schema and new-run interlock;
- human audit only for trust-boundary promotion; and
- an independent adversarial checker and pinned shell entrypoint.

No runtime crate changed. No process, nono/Seatbelt/Landlock/seccomp/bwrap
policy, candidate, private corpus, capability, network, database, live store,
retrieval path, MCP tool, deployment, or result-release surface was touched.

## Engineering conclusion

The useful nono shape is worth following, but `nono active` is not a security
verdict. The pinned package is a filesystem/network building block. It cannot
alone establish all G1.4 requirements, and on macOS its generated policy's
process-exec/fork allowance is specifically incompatible with the required
subprocess-deny claim unless separately overridden or replaced.

Accordingly, both platform plans are fail closed: absent an exact supplementary
process/clock/entropy/plugin control, support is false. The existing broader
workspace sandbox is a design reference and cannot be reused as KAT evidence.

## Test-first and adversarial evidence

The first checker run was intentionally red because the contract, validator,
and checker did not yet exist. No persistent state was created.

The independent checker rejects 1,105 recursive field, value, type,
length, and order mutations. It independently verifies the authority boundary,
dependency pin, platform gaps, three proof owners, 14 canaries, liveness
controls, eleven phase-specific receipt schemas, one-shot lifecycle,
receipt-anchor requirements, durable rollback policy, and eight manual-audit
transition events. Raw byte drift, duplicate JSON keys,
invalid UTF-8, non-standard JSON constants, a non-object root, and symlink
substitution fail closed; an identity-preserving hardlink remains valid.

The first independent read-only security review did not accept the initial
draft. It found that generic `PASS` wording could be laundered into admission,
the shared JSON helper was not pinned, the runtime leak grep was name-based,
phase evidence could collapse into one aggregate report, and rollback lessons
lacked a durable store/interlock. The revision removes generic PASS wording,
adds explicit no-authority/admission fields, independently pins and parses the
helper/contract boundary, locks the whole seven-path change set to the design
base, registers eleven distinct phase schemas, and blocks new runs until a
supervisor-owned lesson is durably written and reverified.

A follow-up focused review then rejected the claim that one base-to-current
comparison by itself proved both precommit and postcommit states. The shell and
contract now require two explicit phases with different invariants. A final
read-only focused review returned `PASS` for that correction; this review word
is review evidence only and is not emitted by the validation receipt.
As a negative control, `--phase postcommit` exits nonzero while HEAD is still
the registered design base, even though the semantic checker itself validates.

The validator has one input option, `--contract`. Its shared JSON helper is
separately byte-pinned, while the checker independently parses duplicate-free
strict JSON and recomputes both raw and canonical contract hashes. Static
checks prohibit process, network, database, or native-execution imports. The
shell requires an explicit phase. `--phase precommit` verifies the current
HEAD, index, worktree, and untracked paths against the registered base commit
and seven-path allowlist. `--phase postcommit` separately requires a non-base
HEAD, a clean tracked/index/worktree/untracked state, and an exact base-to-HEAD
seven-path delta. A generic, aliased, renamed, or symbol-free runtime change
therefore cannot hide behind a narrow symbol scan, and later path drift
invalidates this versioned gate.

The receipt explicitly states `authority_class=NONE_DESIGN_VALIDATION_ONLY`,
`admission_effect=NO_EXECUTION_OR_DATA_AUTHORITY`,
`production_admissible=false`, and `g1_4_execution_open=false`. The shell emits
`VALIDATED (design only; no authority; phase=...)`, never a generic PASS
verdict.

## Human audit answer

No human approval was required for this gate because it is isolated,
reversible, public, design-only, and runtime-disconnected. An unchanged future
public-synthetic KAT also needs no per-run approval. Failures roll back
automatically; rollback failure must record a durable minimal lesson.

Human safety audit remains mandatory only when evidence or capability crosses
into a persistent/high-blast trust boundary: real candidate/private access,
first real capability or runner, policy/access widening, post-lock or
post-observation drift, unblinding/rerun, or suspected exposure.

## Authority boundary and next gate

G1.4 remains closed. This validation does not authorize native adapter execution,
candidate implementation, private data access, sealed evaluation, unblinding,
retrieval/runtime change, deployment, or promotion.

The only permitted next action is
`separate_public_synthetic_native_sandbox_adapter_kat_implementation_gate`.
It may implement and run only the fixed public synthetic probe against
temporary synthetic resources, with no candidate/private/capability authority.
