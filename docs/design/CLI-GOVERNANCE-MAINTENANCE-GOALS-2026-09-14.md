# CLI governance maintenance goals

Current status and verification entry point: [CLI governance status](CLI-GOVERNANCE-STATUS.md).
This document retains the original G1–G3 contract and its historical completion.

## Decision and scope

On 2026-09-14 the owner requested implementation of the overall-assessment
recommendations after S21. The source base is
`f7a4d030d884835242a2b0b688d50f6e35ccbccf`, verified on both SSH masters.

Close sequential main.rs extraction. Establish a finite maintenance contract;
this is not S22 and does not authorize moving another executor. There is no
line-count budget. Existing S5-V and S17 retention decisions continue to apply.
The current main.rs remains 21,848 lines and is unchanged by this work.

## Goals and acceptance

| Goal | Deliverable | Acceptance / stop condition |
| --- | --- | --- |
| G1: machine-checkable evidence | Enroll S18–S21 in a report registry with source/harness digest bindings | Reject stale/missing report, changed enrolled module or harness without new evidence, removed enrollment, nonregular file, and unstaged substitute evidence |
| G2: actual local regression execution | Select fixed boundary tests and pure behavior probes in pre-commit | A selected failing test/probe blocks commit; tests use the staged checkout, and index/worktree drift fails; unrelated documentation selects none |
| G3: bounded maintenance | Record retained regions, candidate debt, and reopening rules in repository instructions | No automatic next extraction; each future proposal needs a concrete trigger, bounded benefit, authority contract and acceptance |

G1/G2 initially cover four extracted modules: Instinct presentation,
WorktreeSession view, Instinct record preparation, and Dream identity view.
This finite enrollment reuses available deterministic probes. Earlier stages
retain their original governance and review requirements; their entire
behavior is not newly enrolled by this implementation.

## Two distinct kinds of evidence

`docs/design/evidence/cli-governance-registry.json` binds each checked-in
verification report by SHA-256. The gate reads Git blobs from INDEX or an
explicit revision, never a loose worktree report. It requires nonempty fully
passing recorded probe/CLI counters and probe success, then compares the
report's module and harness digests with the proposed Git files. Actual Store
record definitions and the shared Dream helper file are also bound where
those probes use them. Regular-file checks reject symlink substitutions.

Historical reports remain historical: old main.rs or binary hashes are not
silently treated as hashes of the current root/binary. The existing receipt
transition checker still governs main.rs changes. A report update requires
regenerating evidence into a new verification record and updating the registry
path/digest, preserving earlier reports; merely editing a
module cannot borrow its old report. The fixed profile IDs cannot be removed
from the registry to bypass admission.

Fresh execution is separate. The runner invokes fixed Python scripts and Cargo
test targets, not command strings taken from a JSON report. These exercise
actual completed-value transformations/rendering against their original Git
baselines. G4 now adds fresh isolated CLI/SQLite comparisons using the existing
harnesses; see [the finite live-parity goal](CLI-GOVERNANCE-LIVE-PARITY-GOAL-2026-09-14.md).
Historical report digest validation remains separate from fresh CLI execution.

The gate does not provide cryptographic attestation that an author truthfully
produced every historical report. Review is still required for report/test
changes and semantics beyond the enrolled probes. Likewise, the local hook is
not a server-side enforcement guarantee and deliberate bypass remains possible.

## Selection and execution custody

- An enrolled module, its boundary test, its bound harness/dependency, or its
  report selects that profile.
- Registry, runner, pre-commit, check wrapper, transition checker and any gate-test changes
  conservatively select all four profiles. These infrastructure changes also run
  all four Python gate suites and receipt schema self-tests before domain tests.
- main.rs and other shared Rust, Cargo manifest/lock or .cargo configuration
  changes also select all four. Only one enrolled module/test changing does
  not itself select unrelated profiles, although a needed registry update does.
- Each validation checks all four report bindings even when no suite is selected.
- Deleting the registry or a required test/module fails admission.
- Execution requires INDEX or the checked-out HEAD, matching tracked worktree
  and index, and no untracked Rust/Python/Cargo configuration inputs. Explicit
  revision validation remains read-only and does not execute an unrelated tree.
- Execution also rejects tracked assume-unchanged/skip-worktree index flags;
  see [G6 custody checks](CLI-GOVERNANCE-INDEX-CUSTODY-GOAL-2026-09-14.md).
  Plain diff/status can hide changed files carrying these flags.
- Child regression processes receive no inherited GIT_* context. Fixture test
  suites also isolate that environment themselves; parent repository refs,
  index and configuration are regression-tested for preservation.
- The index and tracked worktree are checked again after execution. This prevents
  a successful test on different tracked content from authorizing the commit.
  It is not an isolation boundary against arbitrary concurrent external changes.

Cargo uses a real-disk target. Set CARGO_TARGET_DIR explicitly on other machines;
the current workstation fallback is `/Data/ab-main-rs-governance-target`.
The runner rejects /tmp and Linux tmpfs/ramfs targets. Existing all-targets
pre-commit checks still apply to Rust changes; the new runner adds focused
behavior validation for enrolled boundaries, including module-only changes.

## Retained decisions and deferred debt

Keep startup, shared dependency construction and cross-domain dispatch at the
root. Keep Avatar execution/observer safety, locks, timers, cancellation and
per-step authority under the S17 decision. Keep BioCortex file/Store/runtime
custody and evidence interpretation under S5-R/S5-S/S5-V.

Dream diff/weekly still combine acquisition, calculations and output. Treat
those as candidates when the corresponding command actually changes, develops
a defect, or becomes a repeated conflict surface. Weekly can save a snapshot;
it must not be moved as a supposedly pure report. Date/JSON map helpers are
lower-priority candidates for demonstrated duplication or a real consumer.
Neither candidate is scheduled as an implementation goal now.

Reopen only for a concrete defect/conflict, a real additional consumer, or an
independently characterized stable authority interface. BioCortex retains its
more specific S5-V conditions (including two independent merge conflicts or
three non-format behavior changes in 90 days for a retained renderer).

Before a future extraction, state the owner/input/output boundary, observable
error/effect order, actual benefit and finite acceptance. Stop if preserving
those properties requires a wider authority move. Completing G1–G3 ends this
work; it does not generate another numbered stage.

## Validation and reproduction

```sh
python3 -m unittest discover -s tests -p test_cli_governance_evidence.py
python3 -m unittest discover -s tests -p test_cli_composition_root_governance.py
python3 scripts/eval/cli_composition_root_governance.py self-test
# Validate the staged registry and its report/file bindings:
python3 scripts/eval/cli_governance_evidence.py --base HEAD --head INDEX
# With source/scripts staged and worktree aligned, execute selected profiles:
CARGO_TARGET_DIR=/Data/ab-main-rs-governance-target \
  python3 scripts/eval/cli_governance_evidence.py --base HEAD --head INDEX --run
```

The check wrapper runs all four gate test suites and revision-bound validation; it
does not silently execute behavior tests against a different checked-out tree.
The hook runs both transition and evidence admission before its original
all-targets check. Update evidence in the worktree first, stage the reviewed
files, then run/commit; an unstaged report cannot authorize a staged module.
New behavior failures require investigation or rollback, not lowering counts
or changing baselines to manufacture parity.

## Completion

G1–G3 are implemented. The normal pre-commit hook accepted implementation
commit `affc6a7148250ce0aba022934626a09c89761149`: 26 evidence-gate tests,
20 transition-gate tests, 3 positive/7 negative schema controls, 13 Rust boundary
tests and 405 fixed-input behavior cases passed. Negative controls were detected.
Main.rs is byte-identical to the source base.

The hook integration also exercises child Git-environment isolation; tests
verify that fixture repositories preserve the parent refs, index and config.
The source-bound acceptance record is
[maintenance verification](../reports/main-rs-governance/2026-09-14-maintenance-verification.json).
This closes the finite maintenance goals above. Deferred Dream work remains
trigger-based, not an automatically scheduled next stage.

## Rollback

Revert the new hook invocation, evidence runner/registry/tests and maintenance
instructions together. The existing receipt validator and all S0–S21 source
extractions remain intact. No runtime, database, schema or deployment migration
is involved. Source synchronization continues over SSH with [skip ci] and
GitLab ci.skip, per AGENTS.md.
