# SEPL P1A2 AGENT.md CAS Rollback

## Scope

P1A2 adds a source-only, default-unreachable rollback primitive beside the
P1A1 AGENT.md CAS commit. It is an inherent `SqliteStore` method only. It is
not exposed through `StateStore`, MCP, CLI, scheduler, session bootstrap, or
automatic policy.

The request names the current expected content hash, an earlier lineage
version, and the historical body supplied by the caller. P1A1 stores content
hashes rather than historical bodies, so the caller must provide the bytes;
the bytes are accepted only when their SHA-256 equals the selected immutable
lineage record inside the commit transaction.

## Protocol

1. Validate the bound AGENT.md path, current expected hash, target version,
   body size/UTF-8, and observation timestamp using the P1A1 CAS path.
2. Open the bound path with Unix `O_NOFOLLOW`, retain identity, bytes, and
   permissions, then begin SQLite `BEGIN IMMEDIATE`.
3. Validate the binding, complete untruncated lineage, current head, and that
   the target version is strictly earlier than the current head.
4. Require the supplied historical body hash to equal the target version's
   content hash and the target record's own digest to verify.
5. Replace the file through the P1A1 same-directory temporary file, atomic
   rename, exact readback, and failure restoration path.
6. Append a new predecessor-bound head containing the historical content hash.
   History is never deleted or rewritten: rollback is an append-only return
   to an earlier content identity.

## Verification and Non-Claims

`rollback_verified` is true only after the target hash is lineage-bound and
the replacement is read back before SQLite commit. The predecessor record is
captured inside that same transaction and returned with the committed result;
the receipt does not depend on a post-commit lineage read. The receipt
identifies the target version, prior head, new appended version, and restored
hash.

The operation does not prove exclusion of a non-cooperating external writer
after final readback, cross-filesystem/SQLite atomicity, ownership/ACL/xattr
restoration, directory fsync durability, or semantic suitability of the
historical body. It does not write outcomes or memory and cannot make an
AGENT.md version live by itself.

## Test Floor

- rollback to a verified genesis body appends version 3 and preserves a valid
  three-record lineage;
- forged body bytes whose hash differs from the target lineage are rejected
  without file or lineage mutation;
- current and future target versions are rejected;
- all existing P0/P1A0/P1A1 tests remain green.
