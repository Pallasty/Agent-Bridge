# Memory Continuity T1 Retrieval Trigger FTS Projection

Date: 2026-06-21

This slice promotes `continuity_retrieval_trigger:*` from descriptive metadata to
a narrowly indexed recall hint. It does not change the authored memory body,
memory ranking policy, graph expansion, or BioCortex influence gates.

## Problem

T1 continuity metadata intentionally stored retrieval triggers as tags. That made
the taxonomy backward-compatible, but `memories_fts` only indexed memory content.
As a result, hard paraphrase queries could still miss relevant rows even when the
row carried a human-authored trigger phrase.

The T6 heldout evidence showed only small graph-neighbor recall gain. The next
low-risk lever is to improve first-stage FTS candidate visibility before adding
more ranking complexity.

## Storage Contract

`memories.content` remains the durable authored body. A new nullable
`memories.fts_content` column stores a derived search projection:

- start with `content`;
- append only whitelisted `continuity_retrieval_trigger:` tag values;
- ignore all other tags, including other continuity dimensions;
- cap each projected trigger before indexing;
- dedupe repeated trigger strings.

The FTS table continues to store its own content. Insert/update/delete triggers
now write `COALESCE(new.fts_content, new.content)` into `memories_fts`.

## Migration

Schema v36 adds `memories.fts_content` if missing, backfills every row from its
current `content` and tags, rebuilds the FTS triggers, and repopulates
`memories_fts`.

Fresh stores still pass through the existing sequential migrations and therefore
receive the same v36 projection path as upgraded stores.

## Retrieval Boundary

This change only affects whether a memory can enter the FTS candidate set. It
does not:

- expose trigger text through `memory_get` or mutate `MemoryRecord.content`;
- index arbitrary tags;
- alter semantic embeddings;
- change graph expansion weights;
- grant BioCortex runtime influence.

Any production recall evaluation should run on a copied SQLite database because
opening the store with this branch migrates schema and rebuilds FTS rows.

## Verification

Focused verification in the isolated worktree:

```bash
cargo test -p ab-store memory_save_indexes_continuity_retrieval_trigger_projection -- --nocapture
cargo test -p ab-store memory_save_same_content_resave_refreshes_fts_projection -- --nocapture
cargo test -p ab-store memory_import_indexes_continuity_retrieval_trigger_projection -- --nocapture
cargo test -p ab-store fts_projection_migration_backfills_existing_trigger_tags -- --nocapture
cargo test -p ab-store memory_search -- --nocapture
cargo check -p ab-store --all-targets
git diff --check
```

The tests cover save-time projection, same-content resave refresh, import-time
projection, v36 backfill, non-trigger tag exclusion, and existing memory_search
behavior.

## Offline Copy Check

The first live-shape check used SQLite backups only; the production database
remained at schema v35 with no `fts_content` column.

Same live snapshot, baseline code at `7af6cf2`:

- schema: v35
- FTS: R@1 0.222, R@5 0.611, R@10 0.778, MRR 0.386
- offline FTS+graph: hit 0.889, added 2, added_hit_rate 0.500, MRR 0.391

Same live snapshot, this branch with v36 projection:

- schema: v36 on the copied DB only
- FTS: R@1 0.222, R@5 0.667, R@10 0.778, MRR 0.389
- offline FTS+graph: hit 0.889, added 2, added_hit_rate 0.500, MRR 0.394

Interpretation: this is a small but attribution-safe gain. It moved two hard-ish
cases closer to the head (#4 rank 6 to 5, #14 rank 7 to 6), which raises fixed
corpus FTS R@5 by one case without changing R@10. It is not enough to claim a
ranking breakthrough; it is enough to justify the projection as a low-risk
candidate visibility improvement.
