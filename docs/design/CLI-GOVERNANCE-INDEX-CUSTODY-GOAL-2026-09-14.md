# G6: index flags cannot hide regression inputs

Date: 2026-09-14. User direction after G5 completion:
“很好！我们按照你的思路规划并落地下一治理目标。”

## Observed gap and finite goal

In an isolated fixture at the G5 implementation, setting either
`git update-index --assume-unchanged` or `--skip-worktree` on tracked main.rs,
then changing its bytes, left `git diff --name-only` empty. The old
`ensure_checkout('INDEX')` accepted that checkout. Thus the regression runner
could test working bytes that did not match the admitted Git index.

Close this specific execution-custody gap. Keep S0–S21 closed, S5-V/S17 retained,
and G4 fresh execution/G5 offline review unchanged in scope. No runtime edits.

## Behavior

Before relying on diff, `ensure_checkout` reads `git ls-files -v -z` and rejects
tracked entries carrying assume-unchanged or skip-worktree (including both).
NUL-separated records preserve paths containing spaces and newlines. The same
check is already called before builds, before CLI comparisons and after the
regression chain, so flags introduced during execution also block admission.
The error names the flagged paths; the checker does not clear flags, overwrite
files or otherwise repair the owner's index.

The restriction applies to every tracked file, even an unchanged one. This is
an intentionally conservative execution precondition: sparse checkouts must use
a complete checkout for fresh regressions. Revision-only evidence validation
continues to inspect Git blobs without requiring worktree flags to be cleared.
Unrelated documentation changes still select no fresh execution.

To diagnose, inspect `git ls-files -v`. For an intentionally flagged individual
file, review its working content before clearing the relevant flag:

```sh
git update-index --no-assume-unchanged -- <reviewed-path>
git update-index --no-skip-worktree -- <reviewed-path>
git diff -- <reviewed-path>
```

These are operator recovery instructions, not actions performed by the gate.
A sparse checkout should instead be prepared as a complete checkout through its
normal Git workflow before invoking fresh tests.

## Acceptance and limits

Six new real-index regression tests cover hidden edits under each flag, combined
flags without edits, unusual filenames, unchanged read-only revision validation,
rejection before build-target creation, and flags introduced during the mocked
regression chain while keeping Git/custody checks real. Rejection preserves the
fixture index bytes. Normal pre-commit must pass all 77 Python tests, receipt
controls, 13 boundary tests, 405 pure cases and 143 fresh CLI cases.

This closes the demonstrated index-hint gap; it is not a filesystem sandbox or
protection against arbitrary concurrent changes that appear and disappear
between checks. Existing ignored/untracked input and external-toolchain limits
are not expanded into new claims. Offline G5 verification remains evidence
integrity review, not fresh execution or report-author authentication.

Stop after verified source delivery and a durable execution record. No additional
extraction or maintenance stage is automatically opened.

## Verified completion

Implementation `65ae01b6ce04cdc3e50ab2b7a5955c360a1fcf2d` passed its normal
pre-commit: 77 Python tests, receipt controls (3 positive / 7 negative),
13 Rust boundary tests, 405 pure cases and 143 fresh CLI cases.
The [verification record](../reports/main-rs-governance/2026-09-14-g6-verification.json)
binds the exact candidate tree and complete CLI evidence. Offline G5 review
of the archived bundle passed against that implementation commit:

```sh
python3 scripts/eval/cli_governance_bundle.py \
  --run-dir docs/reports/main-rs-governance/2026-09-14-g6-cli-bundle \
  --candidate-commit 65ae01b6ce04cdc3e50ab2b7a5955c360a1fcf2d
```

main.rs remains 21,848 lines and byte-identical to the G5 baseline. G6 is
complete within the stated scope; no further goal is opened by this record.
