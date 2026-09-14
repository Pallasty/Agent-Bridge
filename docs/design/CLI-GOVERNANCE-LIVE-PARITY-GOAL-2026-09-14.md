# G4: fresh isolated CLI parity

Date: 2026-09-14. User direction: “很好！我们按照你的思路规划并落地下一治理目标。”

## Goal and scope

Close the maintenance gap between digest-bound historical CLI reports and fresh
execution during local pre-commit. This is a finite extension of G2, not an S22
extraction or a new product lane. S5-V/S17 retention decisions remain in force.

| Profiles | Existing unchanged harness | Fresh cases |
| --- | --- | ---: |
| S18 + S20 | instinct_cli_parity.py | 79 |
| S19 | worktree_session_cli_parity.py | 34 |
| S21 | dream_identity_cli_parity.py | 30 |

Selecting both Instinct profiles runs their shared harness once. Infrastructure
changes select all four profiles: 143 CLI cases, in addition to the existing
405 pure behavior probes and 13 Rust boundary tests. Unrelated documentation
selects no execution. Existing report/source bindings still apply.

## Construction and custody

The immutable baseline is commit `4287aee34b2286ffe38c08316f1b52f1d755bc75`.
The runner verifies ancestry, exports it with Git archive and safely extracts
it into a private temporary directory on the configured real-disk Cargo target.
It builds that source and the staged-aligned candidate sequentially with
`cargo build --locked -p ab-bridge --bin agent-bridge`, copying each executable
to its own private path before comparison. Cargo may reuse valid compilation
artifacts; every run invokes both builds. There is no saved baseline-binary
cache, installed-binary dependency, Git worktree mutation or deployment.

Build identity is the pinned baseline SHA or candidate index tree respectively.
Child processes do not inherit hook GIT_* variables. Exported source cannot
accidentally discover the parent repository during the build. The parent index
and tracked source must remain unchanged throughout execution.

Each invocation creates a unique `CARGO_TARGET_DIR/governance-live/run-*`
directory. Build logs, harness reports and a summary with source tree, archive,
binary and report hashes remain there. Temporary sources and binaries are
removed on completion. Failure leaves a summary with success=false and blocks
the commit. No old successful report is admitted as this invocation's result.

Reports must have the fixed schema and case count, matching binary/harness
hashes, successful distinct named cases and stable-input flags. Identity must
explicitly perform baseline/candidate comparison. Existing harnesses retain
their isolated HOME/database fixtures and clock/path normalization; these are
bounded regression scenarios, not proof of all CLI behavior or cryptographic
attestation. Local hooks remain locally bypassable.

## Acceptance and stop rule

- New execution/report validation tests and the existing gate suites pass.
- A normal pre-commit runs the complete selected chain, including fresh 143/143
  CLI comparisons, with no runtime/main.rs or bound historical-report edits.
- Failed builds cannot copy an old executable; malformed, incomplete, failed,
  duplicate, unstable or baseline-only reports fail admission.
- Fixture Git archive operations preserve parent HEAD, index and configuration.
- Source sync uses SSH and skip-ci; no installation or runtime restart.

Stop after verified source delivery and a durable execution record. Further
extraction or coverage expansion requires a separately bounded maintenance goal.
