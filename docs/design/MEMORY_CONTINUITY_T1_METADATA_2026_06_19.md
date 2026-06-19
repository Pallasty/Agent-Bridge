# Memory Continuity T1 Metadata

Date: 2026-06-19

T1 adds a backward-compatible continuity metadata layer to AB memory without a SQLite
schema migration. The intent is to make continuity structure visible to retrieval
and future bootstrap budgeting while keeping older memory rows, exports, imports,
and direct store callers valid.

## Interface

`memory_save` now accepts an optional `continuity` object:

- `continuity_role`: `state`, `constraint`, `procedure`, `evidence`, `preference`, `warning`, `archive`
- `retrieval_trigger`: short free text, capped at 160 characters
- `confidence`: `verified`, `observed`, `inferred`, `user_stated`, `stale`
- `freshness_policy`: `never_expires`, `ttl`, `version_bound`, `project_phase_bound`
- `actionability`: `background`, `plan_influence`, `must_block`, `needs_review`
- `blast_radius`: `current_task`, `project`, `cross_project`, `global`
- `supersedes`: memory keys superseded by this row

`memory_get`, `memory_search`, and `memory_list` now surface parsed
`continuity_metadata` beside the existing memory fields. For rows without continuity
tags, the field is `null`.

## Storage Choice

Continuity metadata is encoded into stable tag prefixes:

- `continuity_role:<value>`
- `continuity_retrieval_trigger:<value>`
- `continuity_confidence:<value>`
- `continuity_freshness_policy:<value>`
- `continuity_actionability:<value>`
- `continuity_blast_radius:<value>`
- `continuity_supersedes:<memory_key>`

`supersedes` is also mirrored into `related_keys` so the existing graph hygiene and
related-key preflight can see the relationship before a dedicated supersession edge
writer exists.

This deliberately avoids adding mandatory fields to `MemoryRecord` or a new DB table
in the first implementation slice. The tradeoff is that retrieval cannot yet filter
these dimensions through indexed columns. That is acceptable for T1 because the goal
is to validate the taxonomy and response contract before committing to a migration.

## Migration Criteria

Move from tag-backed metadata to first-class storage only if one of these becomes true:

- Bootstrap budgeting needs fast indexed filters over actionability, role, or blast radius.
- Query telemetry shows continuity-tag filtering is frequent enough to justify indexes.
- Supersession needs transactional graph updates rather than related-key mirroring.
- Tag noise begins to degrade generic tag analytics or operator readability.

## Verification

Focused tests cover:

- Continuity tags round-trip and replace older continuity tags without dropping unrelated tags.
- `memory_save` accepts the continuity object.
- `memory_get` and `memory_search` expose parsed `continuity_metadata`.

Commands:

```bash
cargo test -p ab-bridge continuity_metadata -- --nocapture
```

## Next Step

T2 can use `continuity_metadata` to split bootstrap output by cognitive tier:
must-block constraints first, active state and procedures next, evidence and
background last, with budgets controlled by actionability and blast radius.
