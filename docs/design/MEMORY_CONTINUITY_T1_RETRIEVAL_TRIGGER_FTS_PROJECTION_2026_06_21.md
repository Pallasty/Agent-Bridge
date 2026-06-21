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
