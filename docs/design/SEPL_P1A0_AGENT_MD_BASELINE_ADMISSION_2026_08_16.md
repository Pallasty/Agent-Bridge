# SEPL P1A0 AGENT.md Baseline Admission

Status: source-only implementation candidate

Authority packet: forum thread `#380`, posts `#6166` and `#6167`

Baseline: `fff3e734bf20064e05ffbe77abdfa41272cafbe4`

## Why P1A0 Precedes Commit

P0 records lineage by `resource_id`, but it does not bind that identifier to a
specific file path. The deployed lineage is also empty. A first operation that
changed AGENT.md and recorded only the new bytes would omit the actual
predecessor, so a later rollback could not restore the pre-commit baseline.

P1A0 closes those two prerequisites without changing AGENT.md:

1. bind one resource id to one canonical AGENT.md path;
2. open the current file with `O_NOFOLLOW`, retain that descriptor, and hash
   bytes read through it;
3. insert that content as version 1 with no predecessor;
4. seek and read the same descriptor again before the SQLite transaction
   commits;
5. require the two content hashes to match and the canonical path to still
   identify the opened device/inode.

## Storage Contract

The additive `resource_bindings` table is restricted to `agent_md` and binds:

- resource id;
- resource kind;
- canonical UTF-8 path;
- binding time;
- a domain-separated, length-framed SHA-256 over those fields.

The table and its explicit unique path index have fixed DDL identity and a
separate migration digest. The existing P0 migration digest and
`schema_meta.version` are unchanged.

## Admission Contract

`SqliteStore::admit_agent_md_baseline` is an inherent store method rather than
a `StateStore` method. It has no MCP, CLI, scheduler, drift, or daemon caller.
The request must name a non-empty visible resource id, an `AGENT.md` regular
file, and a non-negative observation time.

Admission rejects:

- missing, empty, non-UTF-8, non-regular, symlink, or larger-than-1-MiB files;
- a resource id already bound to another canonical path;
- a binding whose stored digest does not recompute;
- an existing lineage that is not the matching version-1 genesis;
- content or path-identity changes observed between initial read and
  transactional readback;
- incompatible pre-existing binding schema or migration digest.

Repeated admission of the same unchanged genesis is idempotent. A readback
mismatch rolls back both the new binding and genesis row. The receipt reports
`content_readback_observed_before_commit=true`,
`path_identity_observed_before_commit=true`, and the fixed observation scope
`opened_file_and_path_identity_before_sqlite_commit`.
It also reports `external_writer_exclusion_verified=false`: SQLite cannot make
an arbitrary, non-cooperating editor participate in the database transaction,
so P1A0 proves a bounded observation immediately before commit rather than a
durable claim about future path contents. Consumers must perform a fresh
readback or drift check when they need to reason about the path after admission.

## Safety Floor

- AGENT.md bytes are never written by P1A0.
- Unix `O_NOFOLLOW` plus opened-descriptor device/inode checks reject target
  symlinks and same-path replacement during the observed admission window.
- No claim is made that arbitrary external writers are locked out after the
  final identity check.
- Existing propose-only drift behavior is not called or changed.
- No `present_outcomes` or `outcomes_memory_drift` data is read or written.
- No resource commit, rollback, automatic policy, MCP tool, or CLI is added.
- Tests use only isolated temporary files and databases.

## Next Gate

P1A1 may add an explicit compare-and-swap commit primitive only after this
baseline exists. It must require the current file hash to equal the lineage
head, preserve file metadata, replace through a same-directory temporary file,
read the result back, append exactly one predecessor-bound version, and restore
the original bytes if any post-replacement step fails. MCP/CLI/runtime exposure
remains a later and separate authority gate.
