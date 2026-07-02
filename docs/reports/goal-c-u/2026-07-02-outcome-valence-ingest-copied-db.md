# Outcome Valence Future-Ingest Copied-DB Smoke

Date: 2026-07-02

Scope: `project:/Data/CascadeProjects/agent-bridge`

Status: copied-DB verification passed; live store untouched

## Summary

The `AB_OUTCOME_VALENCE_IMPORTANCE` future-ingest gate was verified with
isolated copied databases and isolated presentation sidecar directories.

Result:

- Gate OFF writes durable valence labels but keeps default importance `0.5`.
- Gate ON writes durable valence labels, truthfully stamps
  `valence_applied:<v>` at birth, and derives initial importance from valence.
- No production store rows were written.
- No graph edges were written for fixture outcome rows.

## Code State

Repository state used for the run:

```text
HEAD = af17425 docs(memory): revalidate thread 104 onsen blocker
included code = 757bb7a feat(memory): durable valence labels + one-shot apply stamps (#51)
```

Installed binary after deploy:

```text
/home/pallasting/.local/bin/agent-bridge.real
sha256 = 093a63eae08f071bb9f40fec1686d5665bffd5c8728958135a1f42760f5c2257
size = 69116152 bytes
```

Deploy:

```text
scripts/deploy_from_master.sh --yes
source = origin/master @ af17425
rollback = cp '/home/pallasting/.local/bin/agent-bridge.real.bak-deploy-af17425-20260702T022356' '/home/pallasting/.local/bin/agent-bridge.real' && /mcp reconnect
```

Post-deploy doctor:

```text
8 ok / 1 warn / 0 fail
```

The warning is expected immediately after deploy: seven long-lived MCP child
processes still execute the deleted old `.real` and require `/mcp reconnect` or
host refresh. The copied-DB smoke used short-lived subprocesses from the newly
installed binary, so the validation itself exercised the current deployed code.

## Verification Commands

Focused #51 code tests:

```text
CARGO_BUILD_JOBS=2 cargo test -p ab-bridge outcome_valence --lib -- --nocapture
```

Result:

```text
15 passed; 0 failed
```

Covered the shared rule, label/stamp formatting, dry-run behavior, stamp-only
retro stamping, facet-change requalification, and audit-rerun behavior.

```text
CARGO_BUILD_JOBS=2 cargo test -p ab-bridge present_ingest::tests --lib -- --nocapture
```

Result:

```text
18 passed; 0 failed
```

Covered future-ingest gate defaults, gate-on derivation, label/stamp minting,
non-derivable rows, provenance, honest boundary, graph no-op, and integrity
guards.

The store filter check:

```text
CARGO_BUILD_JOBS=2 cargo test -p ab-store memory_add_tags --lib -- --nocapture
```

Result:

```text
0 matched tests; 414 filtered out
```

There is no same-name store unit test. The copied-DB smoke below exercised the
deployed store/write path that persists outcome row tags and importance.

Script checks:

```text
bash -n scripts/verify-outcome-valence-ingest-copied-db.sh
git diff --check
```

Both passed.

Copied-DB smoke:

```text
scripts/verify-outcome-valence-ingest-copied-db.sh
```

Result:

```text
verdict = PASS
schema = agent_bridge.outcome_valence_ingest_copied_db_smoke.v0
source_fixture_key_count_before = 0
source_fixture_key_count_after = 0
```

## Fixture

The script generated three unique verified outcome sidecars in temporary
`AGENT_BRIDGE_PRESENTATIONS_DIR` directories:

| Fixture | Verify | Decision | Expected valence |
|---|---|---|---:|
| approved | `rendered_ok` | `approved` | `+1.000` |
| neutral | `rendered_ok` | none | `+0.600` |
| rejected | `rendered_ok` | `rejected` | `-0.400` |

Both OFF and ON runs used copied DBs made from:

```text
/home/pallasting/.local/share/agent-bridge/state.db
```

The live source DB was opened read-only for backup and final key-count checks.

## Gate-Off Result

Environment:

```text
AGENT_BRIDGE_DB=<tmp>/off.state.db
AGENT_BRIDGE_PRESENTATIONS_DIR=<tmp>/presentations-off
AB_OUTCOME_VALENCE_IMPORTANCE unset
```

Tool result:

| Metric | Value |
|---|---:|
| `dry_run` | `false` |
| `verified_count` | 3 |
| `planned_count` | 3 |
| `written_count` | 3 |
| `skipped_over_cap` | 0 |
| `PRAGMA quick_check` | `ok` |
| fixture memory edges | 0 |

Persisted rows:

| Row | Importance | Required tags | Applied stamp |
|---|---:|---|---|
| approved | 0.5 | `valence:+1.000`, `valence_class:positive` | absent |
| neutral | 0.5 | `valence:+0.600`, `valence_class:positive` | absent |
| rejected | 0.5 | `valence:-0.400`, `valence_class:negative` | absent |

Interpretation: default-off behavior preserves the historical initial
importance while still writing durable valence labels for corpus integrity.

## Gate-On Result

Environment:

```text
AGENT_BRIDGE_DB=<tmp>/on.state.db
AGENT_BRIDGE_PRESENTATIONS_DIR=<tmp>/presentations-on
AB_OUTCOME_VALENCE_IMPORTANCE=true
```

Tool result:

| Metric | Value |
|---|---:|
| `dry_run` | `false` |
| `verified_count` | 3 |
| `planned_count` | 3 |
| `written_count` | 3 |
| `skipped_over_cap` | 0 |
| `PRAGMA quick_check` | `ok` |
| fixture memory edges | 0 |

Persisted rows:

| Row | Importance | Required tags |
|---|---:|---|
| approved | 0.9 | `valence:+1.000`, `valence_class:positive`, `valence_applied:+1.000` |
| neutral | 0.8 | `valence:+0.600`, `valence_class:positive`, `valence_applied:+0.600` |
| rejected | 0.3 | `valence:-0.400`, `valence_class:negative`, `valence_applied:-0.400` |

Interpretation: gate-on fresh rows get derived birth importance and a truthful
birth apply stamp, so the retro apply pass should not re-touch them while their
facets still derive the same valence.

## Checks

All script checks passed:

| Check | Result |
|---|---|
| source live DB untouched | pass |
| gate-off rows written | pass |
| gate-on rows written | pass |
| gate-off importance remains 0.5 | pass |
| gate-on importance derived | pass |
| gate-off labels without apply stamp | pass |
| gate-on labels with birth apply stamp | pass |
| no fixture graph edges | pass |
| copied DB quick checks | pass |

## Boundary

This pass did not:

- write to the production memory store;
- write to the production presentations directory;
- enable `AB_OUTCOME_VALENCE_IMPORTANCE` for long-lived services;
- run production `present_outcomes_ingest(dry_run=false)`;
- run production `outcome_valence_importance_apply(confirm_apply=true)`;
- write graph edges;
- alter retrieval ranking in production;
- change schema, systemd units, prompts, or daemon runtime flags.

The only persistent repo changes are this report and the reusable copied-DB
verification script:

```text
scripts/verify-outcome-valence-ingest-copied-db.sh
```

## Next Step

After MCP reconnect, rerun `agent-bridge.real doctor` and then run an installed
short-lived `outcome_valence_importance_apply(confirm_apply=false)` dry-run.
With #51 stamps in place, the expected production posture is:

- existing unstamped but already-targeted rows may need a stamp-only retro pass;
- freshly gate-on rows should be skipped as already stamped;
- no production confirm apply should happen without reviewing the dry-run rows.
