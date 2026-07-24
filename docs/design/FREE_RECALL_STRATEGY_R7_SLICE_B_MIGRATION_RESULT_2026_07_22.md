# Free Recall Strategy R7 — Slice B Migration and Inert-Adapter Result

Date: 2026-07-22

Status: **PLAN GATE PASS / NO SOURCE AUTHORITY EXERCISED**

Preregistration:
`docs/design/FREE_RECALL_STRATEGY_R7_SLICE_B_MIGRATION_PREREGISTRATION_2026_07_22.md`

## 1. Verdict

R7 passes as a design and public-synthetic offline-validation gate. The next
Slice B has a constrained migration contract, a private inert-adapter boundary,
and a non-destructive rollback rule. It deliberately does not nominate a schema
version: current source shows that v43 is owned and identity-verified by the
temporal-evidence migration.

No SQL, Rust, Cargo feature, database, state file, private capture, producer,
runtime configuration, retrieval/sync/export path, merge, or deployment was
created or used for this result.

## 2. Evidence

The following public-synthetic command passed twice:

```text
python3 scripts/eval/free_recall_strategy_r7_slice_b_plan.py --selftest \
  --out /tmp/free-recall-r7-report-{a,b}.json
```

- canonical plan SHA-256:
  `4905580aef5cd620e562c4443a66cc9e2d09aa1379f633d2f6b6f1e8a7034391`;
- 35 directed mutations were supplied and all 35 were rejected as expected;
- canonical plan, mutation rejection, key-order invariance, and zero-authority
  gates all passed;
- the two serialized reports were byte-identical;
- `python3 -m py_compile` and `git diff --check` passed.

The validator is an offline specification checker. Its pass is not evidence
that a future SQLite migration builds, migrates, or runs.

## 3. Accepted design decisions

- The source gate must perform an explicit handoff with the current
  `schema_meta` owner; it may not pre-reserve a number or replicate a
  versionless additive pattern to evade the handoff.
- Default binaries retain no Slice B schema side effect. Only a future new,
  explicit default-off compile feature could prepare the relation, and a
  runtime-disabled adapter remains zero-write, zero-read, and invisible.
- The relation remains isolated from `memories`, FTS/vector/graph,
  retrieval, sync/export, and public surfaces.
- The adapter, if later authorized, is private to `SqliteStore`, has exactly
  append-validated-event and read-finalized-projection duties, and abstains on
  malformed/incomplete episode structures.
- Rollback disables behavior and retains the inert relation. Deletion or
  rewrite remains a separate destructive gate.

## 4. Next authority boundary

R8 may request separate owner authorization for **Slice B source only**:
reviewed migration code and a private inert adapter, on a disposable database
test fixture. A successful R7 plan does not authorize building, executing,
using a private/user database, producer wiring, runtime enablement, retrieval,
merge, deployment, or production key custody.
