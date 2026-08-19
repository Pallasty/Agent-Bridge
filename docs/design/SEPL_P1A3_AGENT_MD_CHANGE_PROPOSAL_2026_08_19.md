# SEPL P1A3 AGENT.md Change Proposal

## Scope

P1A3 adds a source-only, read-only proposal primitive beside the P1A1 CAS
commit and P1A2 rollback methods. It is an inherent `SqliteStore` method
only. It is not exposed through `StateStore`, MCP, CLI, scheduler, session
bootstrap, or an automatic producer.

The request supplies a candidate UTF-8 body and may identify an earlier
lineage version. The response contains current and proposed hashes, the
current immutable head, a bounded line-diff summary, and explicit mutation
flags. It never returns the candidate body and never writes a file or
lineage row.

## Protocol

1. Validate the resource id, `AGENT.md` filename, candidate size/UTF-8,
   optional expected current SHA-256, target version, and timestamp.
2. Open the requested path with Unix `O_NOFOLLOW`, resolve its canonical path,
   reopen it, and require device/inode/content identity to match.
3. In a read-only SQLite transaction, require the existing binding and its
   digest to match the canonical path, require a complete verified lineage,
   and require the current file hash to equal the verified head hash.
4. Recheck path identity and file bytes inside the transaction. If an
   expected current hash was supplied, require it to match this readback.
5. When a target version is supplied, require it to be earlier than the head,
   self-validating, and hash-equal to the candidate body.
6. Commit the read-only transaction and return hashes, version identity, line
   counts, changed/added/removed line counts, and mutation flags.

## Non-Claims

The proposal does not apply a change, reserve a write lease, prove semantic
suitability, provide a full patch body, exclude a non-cooperating writer
after the read-only observation, or make a proposal live. It does not expose
an execution path or write memory.

## Test Floor

- ordinary proposal returns hashes and a line summary without file or lineage
  mutation;
- historical target proposal succeeds only when the candidate body matches
  the target immutable hash;
- forged target bodies are rejected;
- stale expected current hashes are rejected;
- existing P0/P1A0/P1A1/P1A2 tests remain green.
