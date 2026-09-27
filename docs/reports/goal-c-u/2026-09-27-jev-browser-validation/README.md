# Jev validation evidence

Tested implementation: `af12defe56aa93f5cbb7c6257e7e9d0229a70030`.
The parent report explains acceptance, adoption holds and measurement limits.

| Evidence | Files |
| --- | --- |
| Failing original-code regressions | `red-unit.log`, `red-browser.log` |
| Corrected browser package and actual input checks | `browser-package.log`, `green-browser.log`, `legacy-browser.log` |
| Observation run 1 and final rerun | `observation-probe.json`, `observation-probe-final.json` and their `observation-summary*.json` companions |
| Final harness source/commands | `final-harness-checks.json`, `tested-source-final-sha256.json`, `validation-binding.json` |
| Initial package source/commands | `package-checks.json`, `tested-source-sha256.json` |
| Lint failure and baseline attribution | `browser-clippy.log`, `browser-clippy-final.log`, `clippy-baseline-comparison.json` |
| Owned browser/profile cleanup | `final-browser-custody.json`, `reference-test-cleanup.json`, `red-profile-cleanup.json`, `final-probe-cleanup.json`; legacy/run-1 cleanup is in `package-checks.json` |
| Earlier offline logic outcomes | `offline-probe-results.json` (explicit doubles; not real inference) |
| Unmodified source used by observation probe | `upstream/snapshot.js`, `upstream/LICENSE` |
| Required normal repository gate | `precommit.log`, `implementation-commit.json`, `cli-bundle/` |
| File integrity and source binding | `manifest.json` |

The original research archive retains additional setup/interruption logs and
the full 33-file upstream text snapshot. Its location is
`/Data/session-archives/20260927-jev-ultrafast-research/`.
Paths in historical reports identify the execution environment; they are not
instructions to execute or delete files on another machine.

The RED E2E preceded a cleanup-only repair to wait for its owned Chrome child
and retry profile removal. The final behavioral checks are the same; the old
cleanup warning and later independent removal receipt are retained.

Run 1 preceded the equivalent parity-arithmetic Clippy fix in the measurement
harness; final measurements were rerun after that change. The P0 production and
test files did not change between package verification and the final source.

`manifest.json` records SHA-256 for each retained file except itself. This checks
byte integrity, not authenticity of the experiment. The CLI bundle has its own
read-only verifier, bound to the independently selected implementation commit;
see the parent report for its command. No binary or Cargo cache is required to
inspect these JSON reports and logs.
