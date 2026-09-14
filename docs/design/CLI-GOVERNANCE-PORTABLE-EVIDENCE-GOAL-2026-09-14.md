# G5: portable CLI evidence review

Date: 2026-09-14. User direction after G4 completion:
“很好！我们按照你的思路规划并落地下一治理目标。”

## Finite goal

G4 retains full CLI reports and build logs in a workstation-local directory;
its committed verification record contains hashes and local paths. Make those
results independently inspectable after source checkout on another machine.
Add a read-only verifier and commit the complete CLI evidence from this goal's
normal pre-commit run. This does not expand extraction or CLI behavior scope.

## Contract

`scripts/eval/cli_governance_bundle.py` accepts a run directory, a caller-selected
candidate commit and expected stages (all four by default). It resolves that
commit's tree and harness blobs from Git, then validates the existing G4 summary,
exact suite set, baseline identity, candidate tree/build identity, timestamps,
build-log hashes and full report hashes. It reuses G4's strict case, schema,
input hash and stability validation. Required files must be regular files,
not symbolic links. There are no report-supplied commands or file paths.

A portable directory contains summary.json, baseline-build.log,
candidate-build.log and the selected identity.json / instinct.json /
worktree.json. Files can be copied unchanged; local paths embedded in reports
are historical context, not inputs for the verifier. Git history must contain
the explicitly selected candidate commit and its harness sources.

```sh
python3 scripts/eval/cli_governance_bundle.py \
  --run-dir <portable-evidence-directory> \
  --candidate-commit <tested-implementation-commit>
```

For subset runs, supply the independently expected `--stages`, such as
`--stages s18 s20`; Instinct remains deduplicated. Do not use the later
archive/documentation commit as the candidate: its tree differs from the tree
that actually passed the tests. Changes to the verifier/tests conservatively
select the full existing gate and its four Python test suites.

## Meaning and limits

Offline verification checks internal integrity and binding to the selected
source tree/harnesses. It executes no Cargo builds or CLI commands and cannot
replace fresh execution, authenticate the report author, reproduce the deleted
binaries/archive or prove their declared digests came from those builds.
Someone editing reports and all matching hashes can fabricate consistent
claims; trusted commit selection and review remain necessary. G4 harness
exclusions, local-hook limitations and S5-V/S17 retention remain unchanged.

## Acceptance and stop

- A copied complete bundle passes; missing/changed files, failed cases,
  incorrect scope, wrong candidate tree/build identity and mismatched Git
  harness content fail, including a real fixture-repository CLI test.
- Normal pre-commit passes the new tests plus existing receipt controls,
  13 boundary tests, 405 pure cases and 143 fresh CLI cases.
- Archive that actual run, then verify against its implementation commit;
  record exact file hashes and source-sync commits without inventing SHAs.
- Deliver by SSH with skip-ci, without runtime changes or deployment; stop.
