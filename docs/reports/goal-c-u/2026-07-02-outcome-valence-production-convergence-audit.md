# Outcome Valence Production Convergence Audit

Date: 2026-07-02

Scope: `project:/Data/CascadeProjects/agent-bridge`

Status: read-only convergence audit complete; no production apply needed

## Summary

This audit records the current production posture after the outcome-valence
importance loop landed, the future-ingest copied-DB smoke passed, and a
concurrent session appears to have applied/stamped the remaining production
`present_outcome` rows.

Current state is converged:

- all active `present_outcome` rows are derivable;
- all active `present_outcome` rows carry `valence:*`, `valence_class:*`, and
  `valence_applied:*` tags;
- the dry-run has zero candidates;
- no `confirm_apply=true` pass is needed now.

This supersedes the earlier three-row dry-run snapshot in
`2026-07-02-outcome-valence-importance-dry-run.md`; that snapshot was accurate
at the time, but the production store has since advanced.

## Runtime And Repo State

```text
repo = clean
HEAD = 172e02da test(memory): script outcome valence ingest copied-db smoke
origin/master = 172e02da
installed binary sha256 = 093a63eae08f071bb9f40fec1686d5665bffd5c8728958135a1f42760f5c2257
doctor = ok=true, warns=0, fails=0
MCP servers = 9, all executing current agent-bridge.real
tool surface = 142 tools
```

## MCP Dry Run

Invocation:

```json
{
  "tool": "outcome_valence_importance_apply",
  "arguments": {
    "confirm_apply": false,
    "floor": 0.1,
    "ceiling": 0.9,
    "min_delta": 0.01,
    "max_apply_per_pass": 500
  }
}
```

Boundary reported by the tool:

```json
{
  "mode": "valence_importance_dry_run",
  "read_only": true,
  "mutates_ab_memory": false,
  "recomputes_stored_importance": false,
  "changes_memory_search_order": false,
  "writes_valence": false,
  "runs_biocortex": false,
  "supplies_to_biocortex": false
}
```

Dry-run summary:

| Metric | Value |
|---|---:|
| `present_outcome_rows` | 8 |
| `derivable_rows` | 8 |
| `skipped_already_stamped` | 8 |
| `candidates` | 0 |
| `importance_candidates` | 0 |
| `stamp_only_candidates` | 0 |
| `applied` | 0 |
| `stamped` | 0 |
| `failed` | 0 |
| `stamp_failed` | 0 |
| `capped_out` | 0 |

## SQLite Read-Only Cross-Check

Database:

```text
/home/pallasting/.local/share/agent-bridge/state.db
```

Read-only checks:

```text
PRAGMA quick_check = ok
active present_outcome rows = 8
rows with valence label = 8
rows with valence_class = 8
rows with valence_applied stamp = 8
```

Importance distribution:

| Importance | Rows |
|---:|---:|
| `0.800` | 3 |
| `0.590` | 5 |

Redacted row readback:

| Key hash prefix | Importance | Valence | Class | Applied stamp | Tags |
|---|---:|---|---|---|---:|
| `b755ce4b7520` | 0.800 | `valence:+0.600` | `valence_class:positive` | `valence_applied:+0.600` | 8 |
| `173c0ec15ace` | 0.800 | `valence:+0.600` | `valence_class:positive` | `valence_applied:+0.600` | 8 |
| `3af84defdcb2` | 0.800 | `valence:+0.600` | `valence_class:positive` | `valence_applied:+0.600` | 8 |
| `e849d055b194` | 0.590 | `valence:+0.180` | `valence_class:positive` | `valence_applied:+0.180` | 10 |
| `cc32ab3b3a4a` | 0.590 | `valence:+0.180` | `valence_class:positive` | `valence_applied:+0.180` | 10 |
| `f58660225805` | 0.590 | `valence:+0.180` | `valence_class:positive` | `valence_applied:+0.180` | 10 |
| `53f909ca07d1` | 0.590 | `valence:+0.180` | `valence_class:positive` | `valence_applied:+0.180` | 10 |
| `e79a0b841ad5` | 0.590 | `valence:+0.180` | `valence_class:positive` | `valence_applied:+0.180` | 10 |

Raw memory keys and scopes were not recorded in this report.

## Decision

Do not run production `outcome_valence_importance_apply(confirm_apply=true)`
now.

Reason: the current store is already converged and stamped. A confirmed apply
would produce no useful repair and would only add unnecessary audit noise.

## Boundary

This audit did not:

- run `confirm_apply=true`;
- write memory rows;
- write graph edges;
- change stored importance;
- change retrieval ranking;
- change DB schema;
- enable `AB_OUTCOME_VALENCE_IMPORTANCE`;
- run production `present_outcomes_ingest`;
- run BioCortex or pass anything to BioCortex;
- change tool profiles, systemd units, deployed binaries, prompts, or runtime
  flags.

## Next Step

Treat outcome-valence as landed and converged for the current production rows.
Future work should wait for either:

1. new real `present_outcome` rows that justify another dry-run, or
2. a fresh scoped owner packet for changing the default ingest gate posture.

