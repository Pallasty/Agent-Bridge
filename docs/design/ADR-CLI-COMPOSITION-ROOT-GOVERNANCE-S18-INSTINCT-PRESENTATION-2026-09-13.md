# S18 Instinct completed-result presentation

## Scope and source

The owner requested the next main.rs governance stage after S14–S17 closeout
on 2026-09-13. This stage selects a new Instinct presentation boundary; it does
not change the accepted S17 retain-root-adapters decision.

Source base: `4e57079292d8245fe3c721d57a6bb99adb7e806a`, fetched from both
GitHub and GitLab master with equal refs. The baseline main.rs has 22,472 lines.

Instinct already owns candidate generation, review decisions, preflight and
sidecar IO in its domain module. Nine completed-result output blocks remain
embedded in real_main: Candidates, ReviewPacket, ReviewDecision,
MemoryPreflight, MemoryWrite, ReviewStatus, ReviewInbox, ReviewContext and
RotateLog. Their field selection, defaults, truncation and formatting obscure
the root's actual admission and effect sequence.

## Accepted boundary

Move only these output blocks to binary-private cli::instinct_presentation.
Each renderer accepts a completed immutable serde_json::Value and the existing
display flags. Preserve the exact print calls, JSON serialization, field
fallbacks, list limits and explicit local-excerpt display flag.

The root retains CLI declarations and dispatch, all domain invocations and
error contexts, file/path/environment acquisition, approval checks, memory
record validation and timestamp acquisition, SQLite construction, memory save,
receipt creation and post-save plan augmentation. In particular, MemoryWrite
must reject inadmissible plans before record construction or opening SQLite,
and must save memory and its receipt before rendering the completed plan.
ReviewContext's include-local-excerpt argument remains explicit at both domain
acquisition and display. The renderer receives no Store, Hub, clock, path
reader, task runner or executable capability.

The JSON-to-MemoryRecord adapter is a separate potential future slice because
its current clock read must follow validation. WorktreeSession parsing is
another independent candidate; neither is needed to complete this stage.

## Preregistered acceptance

- Compare all nine baseline output blocks against the actual extracted module
  using deterministic completed-value fixtures and full exit/stdout/stderr
  equality. Read baseline code from the source commit, not the candidate.
- Cover empty and mistyped fields, complete results, Unicode and escaping,
  candidate/inbox limits, MemoryWrite key fallbacks, and explicit excerpt
  opt-in. JSON must preserve the complete input regardless of text flags.
- Compare isolated baseline/candidate CLI help, deterministic success/preview
  and error paths. Do not use real owner state or external services.
- Run existing Instinct domain tests and focused source-boundary checks for
  root-owned admission, writes, receipt ordering and private module ownership.
- Run cargo check -p ab-bridge --all-targets --quiet, scoped rustfmt,
  git diff --check, and staged/committed composition-root receipt admission.
- Bind the source diff and evidence in a fresh S18 receipt. Synchronize the
  verified commit to both SSH remotes, with [skip ci] and GitLab -o ci.skip.

No new runtime feature, deployment or live-value claim is part of acceptance.

## Reproduction

Build the source baseline and candidate with the same Cargo configuration,
preserving the baseline executable before building the candidate. Use a target
directory on real disk. The presentation probe reuses the built anyhow and
serde_json dependencies; --deps-dir selects an alternate target/dependency
directory. It extracts the original blocks with their reference-valued CLI
parameters intact and directly includes the actual candidate module.

```sh
python3 scripts/eval/instinct_presentation_parity.py --output-dir <report-dir>/presentation
python3 scripts/eval/instinct_cli_parity.py --baseline <baseline-bin> --candidate <candidate-bin> --output <report-dir>/cli-parity.json
cargo test -p ab-bridge --lib instinct::tests::observer_
cargo test -p ab-bridge --test cli_instinct_s18_extraction
cargo check -p ab-bridge --all-targets --quiet
bash scripts/check-cli-composition-root-governance.sh 4e57079292d8245fe3c721d57a6bb99adb7e806a HEAD
```

The CLI harness explicitly redirects credentials, all Instinct sidecars and
SQLite into reset fixtures. Ordinary generated timestamps are not evidence of
a rendering difference: exact CLI cases are restricted to deterministic
outputs; write failure/success cases check declared database postconditions.
All nine renderers, including time-derived IDs/paths in completed JSON, are
covered by the independent fixed-value byte comparison. These two evidence
classes remain distinct in the verification report.

## Outcome

All nine output tails are extracted. main.rs is now 22,070 lines, 402 fewer.
Replacing each old tail and its new call with the same marker gives
byte-identical whole-file content. Independent source review confirms the
same boundary; main, build_hub, MemoryRecord construction, CLI declarations
and the Instinct domain module are unchanged.

Verification passed: 236 completed-result byte comparisons, 18 JSON flag
invariance groups and an extra-output negative control; 79 isolated CLI cases
(77 exact CLI/filesystem cases and two exact CLI/validated business-effect
cases); 14 existing domain tests; four boundary tests; 20 Git/hook tests;
3 positive/7 negative governance controls; all-targets check and scoped format
checks. In the two actual-write cases both binaries persist exactly one
expected memory. Successful receipt creation precedes success output; receipt
failure returns exit 1 with empty stdout after the memory has been saved.
The blocked-write cases create no database.

The durable verification summary is
`docs/reports/main-rs-governance/2026-09-13-s18-verification.json`; the fresh
receipt is `docs/design/evidence/cli-composition-root-governance/2026-09-13-s18-instinct-presentation.json`.
S18 is complete as a behavior-preserving presentation extraction. A future
stage should select its own characterized boundary from current source.

## Rollback

Revert the S18 extraction commit to restore inline output. There is no state,
configuration or schema migration. Preserve earlier S14–S17 receipts and code.
