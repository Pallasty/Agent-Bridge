# Engram G1.4 G2B WASI artifact ordering repair

Date: 2026-07-19

Status: **ordering repair preregistered; pre-source evidence incomplete; No authority**.

## Decision

G2A proved that the original artifact gate was causally impossible: it required
component and custom-host source digests before source could exist, and required
a component binary and observed import manifest before a build could occur.
G2B replaces that one impossible barrier with three ordered barriers.

The rule is simple: evidence must exist after it can causally exist and before
the next risk-increasing action. Passing a barrier never grants the authority to
perform that action. Source, build, and run each require a separate owner
authorization gate.

## B0_PRE_SOURCE

`B0_PRE_SOURCE` must close before component or custom-host source authoring. It
contains only evidence that can exist without such source:

- verified public release and crate payload digests;
- minimal exact Wasmtime feature graph and complete Cargo lock checksums;
- exact host/guest targets and toolchain payload digests;
- a current pinned advisory database with an official or accepted-equivalent
  raw audit receipt;
- static compatibility of the exact WIT package/world shape and binding
  generator;
- the direct wall-clock, monotonic-clock, and poll host design, with broad WASI
  linkers, Tokio time, ambient clocks, and native/QEMU fallback forbidden.

G2A left release, advisory, WIT compatibility, and timer-path design evidence
partial or conditional, so the current state is
`PRE_SOURCE_EVIDENCE_INCOMPLETE`. G2B does not mark B0 complete.

Even when B0 later becomes complete, the state is only
`PRE_SOURCE_EVIDENCE_COMPLETE_AWAITING_OWNER_SOURCE_AUTHORIZATION`. Source may
begin only after a separate owner authorization.

## B1_POST_SOURCE_PRE_BUILD

`B1_POST_SOURCE_PRE_BUILD` can exist only after separately authorized public
source authoring and must close before any component or host build/compile. It
requires:

- exact component source digest;
- exact custom clock/poll host source digest;
- exact source-level import allowlist declaration digest;
- static proof that source directly implements wall, monotonic, and poll hosts;
- a forbidden-symbol scan excluding broad WASI linkers, Tokio time, ambient
  fallback, and native/QEMU fallback.

B1 completion does not authorize a build. It moves only to
`POST_SOURCE_PRE_BUILD_EVIDENCE_COMPLETE_AWAITING_OWNER_BUILD_AUTHORIZATION`.

## B2_POST_BUILD_PRE_RUN

`B2_POST_BUILD_PRE_RUN` can exist only after a separately authorized public
build and must close before any component execution or G1.4 run. It requires:

- component binary digest;
- observed component import/export manifest digest;
- reproducible build input/toolchain/output receipt digest;
- compiled exact-WIT bindgen compatibility receipt;
- observed imports exactly equal the three-interface allowlist;
- built linker evidence excluding every built-in WASI timer path.

B2 completion does not authorize a run. It moves only to
`POST_BUILD_PRE_RUN_EVIDENCE_COMPLETE_AWAITING_OWNER_RUN_AUTHORIZATION`.

## Transition and invalidation rules

Transitions are ordered and cannot skip barriers. Missing, unknown, expired, or
drifted evidence is `FAIL_CLOSED_NO_TRANSITION`. Upstream release, crate,
toolchain, WIT, or advisory drift invalidates the current and downstream
barriers. Source changes invalidate B1 and B2. Build-input changes invalidate
B2.

Source authorization never implies build authorization. Build authorization
never implies run authorization. Run authorization never implies access to
candidate/private/capability material. No green checker or green barrier is an
owner authorization.

## Result and successor

G2B repairs only the ordering contract. It authors no component or host source,
installs or compiles no dependency, builds or runs nothing, and changes no AB
runtime, store, MCP, policy, deployment, canary, or G1.4 state.

The only successor is `G2C_PRE_SOURCE_EVIDENCE_COMPLETION_REVIEW`. G2C is also
public/static/no-source/no-build/no-run and may close only the remaining B0
evidence. G2C itself cannot authorize source.

## Verification

```bash
scripts/check-engram-g14-wasi-g2b-ordering-repair.sh --phase precommit
scripts/check-engram-g14-wasi-g2b-ordering-repair.sh --phase postcommit
```

A passing checker is not acceptance authority. Independent clean-tree review
must publish the exact feature commit, tree, checker hash, and all seven feature
path hashes out of band.
