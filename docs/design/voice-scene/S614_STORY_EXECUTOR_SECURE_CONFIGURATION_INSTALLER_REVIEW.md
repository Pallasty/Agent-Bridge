# S614 Story executor secure configuration installer review

S614 implements the previously specified fixed-path installation transaction,
but does not invoke it. The sole public effectful entrypoint has no key, path,
environment, or CLI parameters. It binds the exact S611 custody contract and
S613 installed-key composition review before targeting only:

- `/home/pallasting/.agent-bridge-secure/story-render` at mode `0700`;
- `authority-keys.v1.json` at mode `0600` with active key ID
  `story-render-owner-v1`;
- no nonce database until the first separately authorized consumption.

The transaction revalidates approved POSIX storage, canonical no-symlink path
components, UID/GID, and exact root mode using directory descriptors. It sets
and restores `umask 077`, creates the runtime directory relative to the verified
root descriptor, and generates exactly 32 nonzero bytes with
`secrets.token_bytes` only when invoked.

Both pinned policy documents are parsed directly from the same byte buffers
whose SHA-256 values were checked, avoiding a hash-then-reread path race.

Key publication uses an exclusive `0600` temporary file in the new directory,
a complete write plus file fsync, then a same-directory hard-link publication.
The link operation cannot replace an existing final target. The temporary link
is removed, the directory is fsynced, and the final file is reopened with
`O_NOFOLLOW|O_CLOEXEC` for same-fd type, mode, owner, link-count, and closed
schema validation. The returned result is redacted and validated by a dedicated
schema.

## Failure boundary

Before publication, rollback removes only the temporary file and runtime
directory created by this transaction, fsyncing the changed directory chain.
An unexpected collision is never deleted. Once the final key name has been
published, automated rollback stops: later failure raises
`InstallationRecoveryRequired` and preserves the key for explicit recovery or
revocation review.

Python cannot guarantee complete key zeroization. The mutable key and encoded
payload buffers are overwritten best-effort, but the CSPRNG return value, hex
string, JSON objects, and decoder copies may remain in allocator-managed
memory. The function is also an in-process API boundary, not a sandbox or a
hardware-backed keystore.

This review exercised only synthetic keys under pytest temporary directories.
The fixed runtime directory remains absent; no real key was generated, no nonce
database was created, and no executor, model, audio, playback, recording, or
memory operation ran. Actual installation still requires a fresh, explicit
owner authorization and does not authorize executor invocation.
