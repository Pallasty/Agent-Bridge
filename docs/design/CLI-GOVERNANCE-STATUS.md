# CLI governance: current status and maintenance entry point

Updated: 2026-09-14. Audited source: `5d94933b12851a96518ff5c8c32b9f25fc484c66`.

## Decision

S0–S21 sequential extraction is closed. G1–G6 maintenance implementation and
acceptance are complete. G7 closes out the documentation and handoff: this page
is the current navigation/status entry point; linked ADRs retain their detailed
contracts and historical evidence. No further numbered implementation goal is
scheduled. This is maintenance mode, not a claim that the code has no defects.

User basis for G7 after G6: “很好！我们按照你的思路规划并落地下一治理目标。”
The remaining handoff gap was scattered completion records and no single current
entry point. G7 adds that entry point and explicit restart conditions, without
changing code, enrollment, runtime authority or deployment.

## Completed work

| Goal | Result | Implementation / evidence |
| --- | --- | --- |
| S0–S21 | Sequential composition-root review/extraction closed; retained authority remains intentional | [Maintenance decision and retained regions](CLI-GOVERNANCE-MAINTENANCE-GOALS-2026-09-14.md) |
| G1 | S18–S21 report/source digest bindings | `affc6a71`; [G1–G3 record](../reports/main-rs-governance/2026-09-14-maintenance-verification.json) |
| G2 | Selected local boundary tests and pure behavior execution | Same G1–G3 record; subsequently extended by G4 |
| G3 | Finite maintenance and reopening contract | [Contract](CLI-GOVERNANCE-MAINTENANCE-GOALS-2026-09-14.md) |
| G4 | Fresh isolated CLI comparisons, baseline/candidate builds, shared Instinct deduplication | `af914459`; [G4 record](../reports/main-rs-governance/2026-09-14-live-parity-verification.json) |
| G5 | Portable offline evidence review against a caller-selected commit | `3cddd674`; [G5 record](../reports/main-rs-governance/2026-09-14-g5-verification.json) |
| G6 | Reject assume-unchanged/skip-worktree states before and after execution | `65ae01b6`; [G6 record](../reports/main-rs-governance/2026-09-14-g6-verification.json) |
| G7 | Unified status, verification entry points and stop/restart rules | This page and repository instructions; documentation-only closeout |

These labels are goals, not a count of commits; S5 in particular includes many
substeps. Old records describe their tested version. For example, G1–G3's
statement that full CLI reports were historical predates G4 automation.

## Latest accepted behavior evidence

The latest full execution tested implementation
`65ae01b6ce04cdc3e50ab2b7a5955c360a1fcf2d`, tree
`395214b125f3b4954e968b769e5d51023c24bcd3`: 77 Python tests, receipt controls
(3 positive / 7 negative), 13 Rust boundary tests, 405 pure behavior cases and
143 real CLI cases passed. These are G6 execution results, not newly rerun
behavior tests for G7. Subsequent archive and status commits have different
trees; do not substitute them as the tested implementation.

The [G6 bundle](../reports/main-rs-governance/2026-09-14-g6-cli-bundle/summary.json)
is fully committed. Current main.rs remains 21,848 lines, SHA-256
`3a619a93efe07da437732685a0de943335b5cea1ed374cbee8c499406edc79b1`.
Line count is context, not an optimization target or reason to reopen extraction.

## Verification routes

Run from the repository root with the relevant Git history available.

```sh
# Offline review of archived G6 CLI evidence; no Cargo or CLI execution:
python3 scripts/eval/cli_governance_bundle.py \
  --run-dir docs/reports/main-rs-governance/2026-09-14-g6-cli-bundle \
  --candidate-commit 65ae01b6ce04cdc3e50ab2b7a5955c360a1fcf2d

# Gate self-tests, receipt-chain and report/source admission for this history:
bash scripts/check-cli-composition-root-governance.sh c4162953 HEAD

# For a future reviewed, staged change: run the profiles selected by its diff.
CARGO_TARGET_DIR=/Data/ab-main-rs-governance-target CARGO_BUILD_JOBS=4 \
  python3 scripts/eval/cli_governance_evidence.py --base HEAD --head INDEX --run
```

The final command selects no execution for unrelated documentation. It is not
an unconditional full-regression command. Fresh execution requires a complete
checkout, staged source/scripts, no hidden index flags, and no concurrent edits
or staging during the run. Normal pre-commit performs selected admission and
execution automatically. Use a real-disk Cargo target; preserve inherited-Git
isolation in fixtures. See [G4](CLI-GOVERNANCE-LIVE-PARITY-GOAL-2026-09-14.md),
[G5](CLI-GOVERNANCE-PORTABLE-EVIDENCE-GOAL-2026-09-14.md) and
[G6](CLI-GOVERNANCE-INDEX-CUSTODY-GOAL-2026-09-14.md) for exact contracts.

## Deferred work and restart conditions

| Area | State | Evidence needed to reopen |
| --- | --- | --- |
| Startup/dependency construction/cross-domain routing | Retained at root | A concrete defect or independently characterized stable boundary with observable benefit |
| Avatar execution, locks, timers, cancellation and per-step authority | Retained under [S17](ADR-CLI-COMPOSITION-ROOT-GOVERNANCE-S16-S17-2026-09-13.md) | Second real consumer or stable authority interface, with deterministic acceptance |
| BioCortex file/Store/runtime custody | Retained under [S5-V](ADR-CLI-COMPOSITION-ROOT-GOVERNANCE-S5V-BIOCORTEX-EFFECTFUL-EXECUTOR-AUDIT-2026-07-31.md) | Apply its exact reopening conditions; renderer recurrence includes two independent merge conflicts or three non-format behavior changes in 90 days |
| Dream diff/weekly and date/JSON helpers | Unscheduled candidates | Actual command change/defect, repeated conflict, demonstrated duplication or real new consumer; preserve weekly snapshot-write authority |
| Gate reliability/coverage | Maintenance on demand | Reproducible failure, real source-custody gap or an uncovered behavior relevant to an actual change |

For a new request to continue, inspect the current state and name the concrete
trigger, benefit, owner/input/output boundary, effect/error order and finite
acceptance before implementation. A generic continuation request authorizes
assessment; it is not itself evidence that another extraction is useful.
If there is no supported new work item, report maintenance status and stop.
Do not generate another stage, duplicate archive or full rebuild solely to
produce a new completion record. Explicitly changed user scope still governs.

Known limits remain: enrollment is S18–S21, not every historical extraction;
local hooks are bypassable; offline hashes do not authenticate report authors
or reconstruct deleted binaries; checks are not a sandbox against arbitrary
concurrent edits. Harness timing exclusions and existing compiler warnings
remain. These limits are not newly discovered failures or automatically
scheduled engineering goals. Product-roadmap collection holds remain separate.

## G7 acceptance

Verify the documented offline route, current gate self-tests/admission, local
links and referenced Git identities; ensure this change contains only status
and instruction documents. Commit through normal pre-commit and synchronize
source by SSH with skip-ci. No runtime rebuild, installation or service restart
is required for this closeout.

Verified on 2026-09-14: offline review accepted the archived 143-case G6 bundle;
the check wrapper passed all 77 Python tests, 3 positive / 7 negative receipt
controls, the seven-receipt chain from `c4162953` and current report/source
bindings. Twelve local links, six commit references, the tested tree and current
main.rs digest/line count were checked. No fresh Rust/CLI behavior execution was
performed for G7. The change is limited to this status page, AGENTS.md and the
maintenance-document navigation link. G7 acceptance is complete; the governance
sequence is closed and future work follows the restart conditions above.
