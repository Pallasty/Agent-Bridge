# `dream gap-audit` — Design

**Date**: 2026-05-16
**Author**: `maxiaodeMac-Pro.local:agent-bridge:main#0275dd57`
**Status**: Design phase. Operationalizes audit §9 action #5.
**Parent**: `docs/MONTHLY-GAP-COVERAGE-AUDIT-2026-05-16.md` (commit `1b62e0d`)

---

## 1 · Intent

§6.5 rule 4 says: "Monthly gap-coverage audit (composes with `dream weekly`)." The first monthly audit was done manually (`docs/MONTHLY-GAP-COVERAGE-AUDIT-2026-05-16.md`). This ship adds a CLI surface so future audits can be triggered + skimmed cheaply, and integrates into the existing `dream weekly` Monday-morning composite.

**Not in scope**: state generation. The audit doc + auto-memory entries remain the canonical source of truth. The CLI **surfaces** that state and **diffs** activity since a baseline date. State updates require a new manual audit doc.

## 2 · API surface

```
dream gap-audit [--since YYYY-MM-DD] [--json]
```

- `--since`: lookback for git-log delta. Default 7 days.
- `--json`: emit `GapAuditReport` struct as JSON. Default pretty markdown.

Wired into `dream weekly` as a new `[bonus #2]` section after the existing P-ε substrate-readiness pill. Skipped if the same date is the canonical audit date (avoid double-print on audit-publish day).

## 3 · Data model

```rust
struct GapEntry {
    id: &'static str,           // "A1" .. "E2"
    layer: &'static str,        // "L5" | "L6" | "L7" | "L8" | "?"
    status: GapStatus,          // closed / shelved / partial / planned / untouched
    text: &'static str,         // working def from audit §8
    last_touch: &'static str,   // commit SHA(s) or "—"
    gate_opens: Option<&'static str>,  // ISO date when falsifiability gate first measurable
    notes: &'static str,        // one-liner
}

enum GapStatus { Closed, Shelved, Partial, Planned, Untouched }
```

The 13-entry table is hardcoded against the canonical audit doc + L4/L8 audit-layer memo. **Each monthly audit publishes a new constant** named by date (`GAPS_AS_OF_2026_05_16`, `GAPS_AS_OF_2026_06_15`, ...) so `git log` traces gap-state evolution at the source-of-truth layer.

Output struct:

```rust
struct GapAuditReport {
    generated_at_unix: u64,
    baseline_date: &'static str,        // matches the constant in use
    since_unix: u64,
    counts: GapStatusCounts,            // { closed, shelved, partial, planned, untouched }
    gaps: Vec<GapEntry>,
    sectional_delta: Vec<SectionalDelta>,   // {prefix, commit_count, commits[]}
    outstanding_gates: Vec<OutstandingGate>,
}

struct SectionalDelta {
    prefix: String,         // "feat(l5):" / "feat(l6):" / "docs(infra):" / etc.
    commit_count: usize,
    commits: Vec<String>,   // first-line summaries
}

struct OutstandingGate {
    gap_id: &'static str,
    gate_label: &'static str,    // "L5-P1" / "L7-P2" / etc.
    opens_iso: &'static str,
    days_until: i64,             // negative if past due
}
```

## 4 · Sources

| Datum | Source | Frequency |
|---|---|---|
| 13-gap baseline state | hardcoded const + audit doc | monthly (manual audit cadence) |
| Sectional delta | `git log --since=<date> --oneline` parse | live |
| Outstanding gates | hardcoded `gate_opens` field + `now` | live |

**No SQL writes. Pure read.** Subprocess: `git log` with a controlled arg-list, no shell interp.

## 5 · Output (pretty)

```
════════════════════════════════════════════════════════════
  dream gap-audit — §6.5 rule 4 monthly cadence
  baseline: 2026-05-16 (next: 2026-06-15)
  since: 2026-05-09 → 2026-05-16 UTC
════════════════════════════════════════════════════════════

13-gap status (snapshot from monthly audit baseline):

| Gap | Layer | Status | Notes |
|---|---|---|---|
| A1 | L5? | ⚪ untouched | — |
| A3 | L5 | ✅ closed | gate 2026-06-14 |
| B1 | ?  | ⚪ untouched | — |
... [13 rows]

Status counts: 6 closed / 1 shelved / 1 partial / 2 planned / 3 untouched

Sectional commit delta since 2026-05-09:
  feat(l5):       3 commits  (P1+P2+P3 L5 v0 closure)
  feat(l6):       3 commits  (v0 + v2 + Option E, C1 shelve)
  feat(l7):       3 commits  (P1+P2+P3 L7 v0 closure)
  feat(c3):       2 commits  (S2-S4, S5)
  docs(infra):    3 commits  (§6.5, audit, Option E design)
  docs(strategy): 3 commits  (decoupling, assessment)
  Total: 17 in-scope ships in window

Outstanding falsifiability gates (open dates):
  L5-P1     2026-06-14   in 29 days
  L7-P1     2026-06-15   in 30 days
  L7-P2     2026-07-11   in 56 days

next audit: 2026-06-15
```

## 6 · `dream weekly` integration

Add new section between current "[bonus]" (substrate-readiness) and the closing "next: re-run" line:

```
[bonus #2] gap-audit (§6.5 rule 4)
─────────────────────────────────────────
  6 closed / 1 shelved / 1 partial / 2 planned / 3 untouched
  delta since 7d: 14 in-scope ships (5 layers touched)
  next outstanding gate: L5-P1 opens in 29 days
  (run `dream gap-audit` for full table)
```

One-liner; full table only on explicit `dream gap-audit` invocation.

## 7 · Tests

- `gap_audit_emits_all_13_entries` — count rows in fixed table
- `gap_audit_status_count_matches_table` — sum of counts = 13
- `gap_audit_outstanding_gates_in_future` — only future-dated gates listed
- `gap_audit_sectional_parser_handles_git_log_format` — git-log mock parse
- `gap_audit_json_round_trips` — serialize + deserialize idempotent
- `gap_audit_skips_section_zero_count` — empty delta sections suppressed

## 8 · LOC estimate

| File | Change | LOC |
|---|---|---|
| `crates/bridge/src/main.rs` | `Cmd::Dream` variant `GapAudit`, dispatcher, `run_dream_gap_audit`, sectional parser, gap-audit `[bonus #2]` in `run_dream_weekly` | ~280 |
| Tests (in same file) | 5-6 tests | ~120 |

**Total**: ~400 LOC. Estimated 2-3h impl + tests.

## 9 · Falsifiability of the audit itself

§6.5 rule 4 doesn't define a falsifiability gate for the audit. Proposed v0:

| Gate | Predicate | Threshold |
|---|---|---|
| AUDIT-G1 | `dream gap-audit` completes in | < 500 ms p95 |
| AUDIT-G2 | Status table is consistent with monthly audit doc | 100% (eyeball check on monthly cadence) |
| AUDIT-G3 | Sectional-delta counts match `git log --oneline \| wc -l` on same window | 100% sample check |

These are smoke tests, not real falsifiability gates — the audit is observational, not predictive. Listed for completeness; not load-bearing.

## 10 · Exit / shelve

If `dream gap-audit` proves useless in practice (sibling/user always reads the audit doc directly instead of the CLI):
- Remove `Cmd::Dream::GapAudit` variant
- Keep the hardcoded constant (it documents state at point-in-time)
- Remove the `[bonus #2]` section from `dream weekly`

Cost of shelve: ~20 LOC deletion. No data migration. Negligible.

## 11 · References

- audit doc: `docs/MONTHLY-GAP-COVERAGE-AUDIT-2026-05-16.md` (commit `1b62e0d`)
- L4/L8 mapping: memory `memory_l4_l8_gap_audit_mapping_20260516`
- roadmap §6.5 rule 4: `docs/AGENT-BRIDGE-CAPABILITY-ROADMAP-2026-05-15.md`
- existing `dream weekly`: `crates/bridge/src/main.rs` `run_dream_weekly` ~line 5640
