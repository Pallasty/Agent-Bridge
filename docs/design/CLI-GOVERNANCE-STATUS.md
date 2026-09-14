# CLI governance: current status and maintenance entry point

Updated: 2026-09-14. Audited source: `f7f70bfba49dfedd1033fc2afd279d6ae4a59ed5`.

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

## G6 behavior evidence

The G6 full execution tested implementation
`65ae01b6ce04cdc3e50ab2b7a5955c360a1fcf2d`, tree
`395214b125f3b4954e968b769e5d51023c24bcd3`: 77 Python tests, receipt controls
(3 positive / 7 negative), 13 Rust boundary tests, 405 pure behavior cases and
143 real CLI cases passed. These are G6 execution results, not newly rerun
behavior tests for G7. Subsequent archive and status commits have different
trees; do not substitute them as the tested implementation.

The [G6 bundle](../reports/main-rs-governance/2026-09-14-g6-cli-bundle/summary.json)
is fully committed. At G6, main.rs had 21,848 lines, SHA-256
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

## Assessed maintenance: weekly snapshot result

The owner accepted a retained-region hotspot assessment after G7. The
[assessment and repair contract](MAIN-RS-HOTSPOT-ASSESSMENT-2026-09-14.md)
records 116 mainline commits with no body changes in ten inspected functions,
but separately reproduces a weekly snapshot-key/output defect. The targeted
root-local repair returns the saved key and suppresses nested snapshot output.
Seven new isolated CLI cases run through `cli_dream_weekly_snapshot` whenever
regression profiles are selected, in addition to the existing G4 comparisons.
At that assessment, date consolidation and Dream diff extraction remained unscheduled.
This is defect-triggered maintenance, not a reopened extraction sequence.

Weekly repair acceptance: `98d905886c18e4bd294bb7c8362cf43e2e78942b`;
77 gate tests, 13 boundary tests, 405 pure cases, 143 existing CLI comparisons
and seven weekly/snapshot cases pass, with ab-bridge all-targets check.
See the [current verification record](../reports/main-rs-governance/2026-09-14-weekly-fix-verification.json).
The receipt chain now has eight transitions. After that repair, main.rs was 21,860 lines,
SHA-256 `5e93086a66df915654f2e792f31362dfa803b1dba6e1458424170cfff5b9cfd0`.
The earlier G6 bundle above remains historical; offline review of the new run
uses `2026-09-14-weekly-fix-cli-bundle` and the repair implementation commit.

## Authorized date consolidation

Following the hotspot assessment, the owner explicitly selected the two root
date conversions for consolidation. See the
[finite contract](CLI-CIVIL-DATE-CONSOLIDATION-2026-09-14.md).
`cli::civil_date` owns that arithmetic; clock reads and all three formatting
callers remain at the root. Four source-bound date tests join the selected
regression command. Cross-domain date consolidation and Dream diff extraction
remain outside this change.

Date consolidation acceptance: `d7a001b342b36615c46db2d107e9629d9ac8334b`;
four new date tests pass in addition to the existing gate, 150 CLI cases
(143 comparisons plus seven weekly cases), and all-targets check.
[Date verification](../reports/main-rs-governance/2026-09-14-civil-date-verification.json).
The date receipt chain had nine transitions. At that point main.rs was 21,828 lines,
SHA-256 `aaa1fecf5d6431414bbbc184955ed7ae9401e7981c29612126f01fb55ae643e4`.
For offline review use `2026-09-14-civil-date-cli-bundle` with the date
implementation commit; earlier bundles and their source hashes remain historical.

## Authorized Dream diff calculation extraction

The owner accepted the proposed Dream diff pure-computation boundary after date
consolidation. The [finite contract](CLI-DREAM-DIFF-PLAN-2026-09-14.md) records
`cli::dream_diff_plan`, with Store reads/access metadata writes, validation and
rendering retained at root. Six focused tests include 256 pure input pairs and
22 exact CLI output/state/read-order cases. main.rs is now 21,647 lines.
Acceptance: `f7f70bfba49dfedd1033fc2afd279d6ae4a59ed5`, tested tree
`b8695aa126b4d4e3503c1be3984d920a5cb9b65c`. All 77 gate tests, receipt
controls, 13 boundary tests, four date tests, six Dream diff tests, seven weekly
CLI cases, 405 existing pure cases and 143 existing CLI comparisons passed,
with ab-bridge all-targets check. The 22 new CLI cases also passed against the
final candidate binary. The receipt chain has ten transitions.
[Current verification](../reports/main-rs-governance/2026-09-14-dream-diff-verification.json)
records hashes and coverage limits. Current main.rs SHA-256:
`3a5358236d64994e9c146a484a323570f5473de42f671926f3920aa6b35ebca6`.

Offline review of the existing 143 comparisons uses
`2026-09-14-dream-diff-cli-bundle` and the implementation commit above; the
additional 22-case CLI log is separately hashed. Earlier bundles remain
historical. This bounded extraction is complete; no further implementation
goal is automatically scheduled.
