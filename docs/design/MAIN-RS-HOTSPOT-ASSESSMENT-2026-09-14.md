# Retained main.rs hotspot assessment and weekly snapshot repair

## Scope and decision

Source `d2d280f236401c7bf62ab0bc624fdb19f9f3825d`. The owner accepted the
proposal to assess retained Dream diff/weekly, date/JSON helpers and actual gate
experience, then act on supported findings. This is a bounded follow-up under
G7 restart conditions, not a resumed extraction sequence.

The assessment found a reproducible weekly/snapshot composition defect. Fix
that defect now; retain the other candidates. File size alone does not justify
movement. Avatar/BioCortex authority and the product-roadmap holds remain intact.

## Evidence and candidate order

The [machine-readable scan](../reports/main-rs-governance/2026-09-14-hotspot-assessment.json)
lists all 116 first-parent commits touching main.rs between
2026-06-16T00:00:00Z and 2026-09-14T23:59:59Z, inclusive by committer time.
For each commit, compare each named top-level function body with its first
parent, from its signature through the first column-zero closing brace. All ten
inspected functions had zero body changes in that interval. Current function
hashes and line spans are recorded. This excludes preceding doc comments,
branch-local churn and conflict counts; it does not establish defect-freedom.
The local reproduction script is retained with the task analysis artifacts.

| Priority | Candidate / evidence | Decision and bounded acceptance |
| --- | --- | --- |
| 1 | weekly (303 lines at source) reconstructs a snapshot key and invokes an output-producing command internally | Fix now: one weekly document, actual persisted key, no-save/failure behavior preserved; seven isolated CLI cases plus existing gate |
| 2 | Six date-conversion implementations in five files, including civil_from_days and days_to_ymd in main.rs | Retain as a real duplication candidate. If touched next, start with the two root conversions; define signed input ranges and i32/i64 conversion semantics, then compare epoch, negative dates, leap-century and day-boundary cases. Do not merge all formatters or move clocks simply because formulas resemble each other |
| 3 | diff (379 lines) has no body edits in the interval; its three JSON helpers have one owning consumer | Retain until an actual diff requirement/defect or second consumer. Any extraction must preserve snapshot kind/schema validation, timestamp ordering, missing-field defaults, output ordering and Store-read/error order |
| 4 | Three G4–G6 build/comparison runs took 146.74, 142.43 and 141.12 seconds | No new gate optimization. These are governance acceptance runs, not daily developer samples; total-hook latency and operational false-positive/negative rates are not established. Investigate real delays/failures when they occur |

`kind_map`, `access_map` and `trans_set` are each called twice inside diff
(older/newer inputs), not by two independent consumers. Date wrappers differ in
format and time acquisition; sharing arithmetic would not justify sharing all
those responsibilities. No observed conflict count is inferred from commit
messages or line counts.

## Reproduced defect

The G6 candidate binary digest was verified before using a private copy with
isolated HOME, XDG directories, empty credentials, hash embedding and SQLite
fixtures. `dream weekly --json` exited 0 but emitted two JSON documents.
The final document reported `snapshot_weekly_<epoch>`, while SQLite contained
`snapshot_weekly_<epoch>_<YYYYMMDD_HHMM>`. Text mode had the same wrong-key
problem and leaked the nested snapshot JSON. A failed insert also leaked JSON
before the weekly report. Seven regression cases reject the old binary in
three cases and accept its four unaffected standalone/no-save cases.

## Repair contract

Keep snapshot acquisition and Store writes at the root. The standalone
`run_dream_snapshot` wrapper delegates to a root-local `capture_dream_snapshot`
that can suppress presentation and returns `Some(key)` only after a successful
save. Print-only returns None. Weekly uses the returned key, not a reconstructed
clock-derived name, and suppresses the nested snapshot presentation.

Standalone snapshot text/JSON, save acknowledgement and print-only behavior
remain. Weekly retains default snapshot creation, --no-snapshot, Store query
order, best-effort save warning/null key and later report sections. Intentional
output correction: weekly JSON is one document; weekly text starts with its own
report; both report the actual saved key. This is a bug fix, not byte parity
with the broken weekly output. CLI help/arguments and database schema do not
change. No scheduling, snapshot-write authority or cross-domain executor moves.

`cli_dream_weekly_snapshot` invokes seven real isolated Python CLI tests using
the Cargo-built executable. They cover weekly JSON, weekly text, no-snapshot,
SQLite-triggered save failure, standalone JSON, standalone text and print-only.
The existing selected regression command now includes this test target, and
harness changes select the full gate. Existing S18–S21 enrollment and baseline
comparisons remain unchanged; the new weekly cases are additional coverage.

## Acceptance and stop rule

Require old-binary negative controls, the seven new cases, governance receipt
admission, gate self-tests, existing 13 boundary tests / 405 pure cases / 143
CLI comparisons, and ab-bridge all-targets check. Preserve the actual source
before/after hashes and executed commit in the final verification record.
Whole-file rustfmt reports pre-existing formatting differences; verify changed
functions and the new Rust test without a repository-wide formatting sweep.

Stop after this repair, assessment delivery and source sync. Date consolidation
and diff extraction are not scheduled by this report. Rollback the wrapper,
key propagation and new regression enrollment together if needed; that restores
the previous known output defect. No database migration or deployment is needed.

## Completed acceptance

Implementation `98d905886c18e4bd294bb7c8362cf43e2e78942b` passed normal
pre-commit, all-targets check, 77 gate tests, 13 existing Rust boundary tests,
405 pure cases and 143 existing CLI comparisons. Seven additional real CLI
cases pass; three of those fail on the verified pre-fix binary. The same seven
also passed against the final live-run candidate binary with matching SHA-256.
The receipt chain now contains eight transitions.

The [verification record](../reports/main-rs-governance/2026-09-14-weekly-fix-verification.json)
binds current source, harness, build and test evidence. The committed
[CLI bundle](../reports/main-rs-governance/2026-09-14-weekly-fix-cli-bundle/summary.json)
passes G5 offline verification against the implementation commit. Its weekly
candidate/negative-control logs are additional evidence, separately hashed by
the verification record; the G5 verifier still checks its original 143 cases.
main.rs is now 21,860 lines. Assessment and targeted repair are complete.
