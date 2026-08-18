# SEPL P1A1 AGENT.md CAS Commit Kernel

## Scope

P1A1 is a source-only, default-unreachable storage primitive. It accepts an
explicit `resource_id`, bound `AGENT.md` path, expected current content hash,
proposed UTF-8 bytes, and observation timestamp. It is exposed only as the
inherent `SqliteStore::commit_agent_md_cas` method. It is not part of
`StateStore`, MCP registration, CLI parsing, scheduler wiring, drift
automation, or live session bootstrap.

The P1A0 `resource_bindings` row is the authority for the resource ID to
canonical path relationship. The existing `resource_versions` head is the
compare-and-append authority.

## Commit Protocol

1. Validate the resource identity, `AGENT.md` filename, expected lowercase
   SHA-256, proposed size, proposed UTF-8, and non-negative timestamp.
2. Open the requested path and its canonical path with Unix `O_NOFOLLOW`,
   retaining the file descriptor, device/inode identity, original bytes, and
   permissions.
3. Start SQLite `BEGIN IMMEDIATE`. Recheck the opened path identity and read
   the current bytes through the retained descriptor. Reject if the current
   hash is not the caller's expected hash.
4. Verify the bound canonical path and its binding digest. Verify the lineage
   head hash and record digest, then validate the complete, non-truncated
   lineage with the P0 validator. Any malformed record, gap, or predecessor
   mismatch fails closed. The new version is exactly `head + 1` and references
   the current head version and record hash.
5. Write proposed bytes to a same-directory, create-new temporary file,
   preserve permissions, `fsync`, and atomically rename it over the canonical
   target.
6. Open the replaced target with `O_NOFOLLOW` and require exact byte/hash
   readback before inserting the predecessor-bound version row.
7. Insert one lineage row and commit the SQLite transaction.

The SQLite transaction remains open across the replacement and lineage insert,
so a normal failure cannot commit lineage without the replacement. If any
failure occurs after replacement, the original bytes and mode permissions are
written to another same-directory temporary file, atomically restored, and
read back before the error is returned. SQLite rollback handles the lineage
side. A failure to restore is surfaced as a stronger error and is never hidden.
Ownership, ACLs, extended attributes, and directory-entry durability are
outside this contract; the directory is not fsynced by P1A1.

## Explicit Non-Claims

The filesystem rename and SQLite commit are not one cross-system atomic
transaction. A non-cooperating external writer can race after the final
readback and before SQLite commit. The receipt therefore reports
`external_writer_exclusion_verified=false` and uses a bounded commit scope;
`content_readback_verified=true` means the replacement was read back before
the lineage commit attempt, not that future path contents are immutable.

P1A1 does not implement rollback, drift scheduling, outcome-sidecar reads or
writes, memory mutation, automatic policy, or live AGENT.md admission. Those
remain separately gated follow-up work.

## Test Floor

- successful version-2 predecessor-bound commit;
- stale expected hash leaves bytes and lineage unchanged;
- post-replace injected failure restores exact bytes and leaves lineage
  unchanged;
- concurrent CAS requests produce one winner and one stale peer failure;
- P0/P1A0 lineage and migration tests remain green.
