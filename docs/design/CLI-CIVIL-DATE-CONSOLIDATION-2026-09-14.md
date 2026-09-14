# Consolidate the root's duplicate civil-date arithmetic

## Scope and authority

Source: `69081c537ae3ce25647e49a29ca79f9fd093d2e3`.
The owner accepted the proposal to unify the two root date conversions before
considering Dream diff extraction. This is a finite, duplication-driven follow-up
under the maintenance contract, not another sequential extraction stage.

Move `civil_from_days` to private binary module `cli::civil_date::from_days`,
remove the duplicate `days_to_ymd`, and route the three existing calls through
that implementation. Keep `chrono_like_date`, `time_slug` and
`chrono_now_utc_string` at the root with their existing clock acquisition,
seconds/day split, formats and casts. The module receives only a day count and
returns `(i32, u32, u32)`; it has no Store, I/O, clock, formatting or new public
library authority. Other date implementations and Dream diff/weekly are outside
this change.

## Equivalence argument and input domain

Each current caller obtains days from an i64 Unix-seconds value using
`div_euclid(86400)`. For this domain, adding 719468 and subtracting 146096 for
negative eras cannot overflow i64. Floor-era decomposition makes day-of-era
lie in `0..=146096`, so both the previous u32 and u64 intermediates represent it
exactly. Year-of-era is at most 399, and the day/month calculations fit both
widths. The era/year arithmetic fits i64 for the reachable range; both originals
cast the final year to i32. Preserve that cast even for extreme timestamps.

The module uses the previous civil_from_days arithmetic, with numeric separators
normalized. It introduces no new input clamp, saturation, Gregorian policy,
timezone conversion or validation error. This equivalence claim covers current
callers' reachable domain, not arbitrary i64 day inputs outside that domain.

## Tests and acceptance

`cli_civil_date` compiles the actual module and frozen copies of both originals.
A source-binding test reads the pinned Git blob and checks the copied functions
byte-for-byte. Its child Git command removes inherited GIT_* context. The other
three tests check:

- Ten known dates: epoch, pre-epoch, year zero, 1900/2000/2100 leap-century edges.
- 292,195 consecutive day values spanning an era before and after the civil
  algorithm origin, comparing both originals with the actual module.
- Eleven signed-seconds boundary cases and 10,000 deterministic samples across
  the i64 seconds domain, again comparing both originals.

Known-date expectations for representable positive years were independently
checked using Python's date arithmetic; the initial hand-entered 1900 day counts
were corrected before acceptance. The frozen source fixture intentionally keeps
its original formatting. Production module and integration test pass rustfmt;
no whole-main.rs formatting sweep is part of this change.

The four tests are added to the existing selected Cargo regression command, so
module/test/shared source edits select and run them through the existing gate.
Require normal pre-commit with receipt admission, 77 Python gate tests,
13 existing Rust boundary tests, four date tests, seven weekly/snapshot CLI
cases, 405 pure behavior cases and 143 original CLI comparisons, plus
ab-bridge all-targets check. Date correctness tests do not replace CLI evidence.

## Stop and rollback

Stop after this pair is unified, verified and delivered. Cross-domain date
helpers and Dream diff extraction remain separate candidates. Revert the module,
three call sites, removed helpers and test enrollment together to restore the
two original functions. No database migration, installation or service restart
is needed. main.rs decreases from 21,860 to 21,828 lines; the result is one owner
for duplicate arithmetic, not a target for further line reduction.

## Verified completion

Implementation `d7a001b342b36615c46db2d107e9629d9ac8334b` passed its normal
pre-commit and all-targets check: 77 Python gate tests, 13 boundary tests, four
date tests, seven weekly/snapshot cases, 405 pure cases and 143 original CLI
comparisons. Receipt controls passed and the historical chain now has nine
transitions. Existing compiler warnings remain.

The [verification record](../reports/main-rs-governance/2026-09-14-civil-date-verification.json)
binds source, tests, logs and the complete CLI bundle. Offline G5 verification
of that bundle passed against the implementation commit; it covers the original
143 CLI cases, with date-test evidence recorded separately. This consolidation
is complete; no additional extraction is scheduled by this record.
