# S611 Story executor secure runtime configuration contract

S611 rejects the earlier nonce location under `/Data/Models`: live mount
evidence shows `fuseblk` below broadly writable `root:root 0777` parents. The
selected custody root is the existing ext4, owner-only `0700`
`/home/pallasting/.agent-bridge-secure`. The planned `story-render` child,
authority key bundle, and nonce database are all currently absent.

The contract requires an exact `0700` runtime directory and exact `0600`
regular, non-symlink, single-link key/database files owned by UID/GID 1000.
Future loaders must walk parents with no-follow directory descriptors, open the
key using `O_NOFOLLOW|O_CLOEXEC`, then validate type, ownership, mode, and link
count with `fstat` on that same descriptor. Environment variables, default
paths, caller overrides, logging, receipts, and generation fallback cannot
serve as key custody.

The future SQLite store is fixed to `application_id=1094865475`,
`user_version=1`, `trusted_schema=OFF`, `synchronous=FULL`, WAL mode, and
`BEGIN IMMEDIATE`. Database, WAL, SHM, and lock files must remain in the same
private directory with fail-closed corruption handling.

Installation is not authorized here. A later installer must use `umask 077`,
exclusive/no-follow creation, same-directory atomic publication, file and
directory fsync, and transaction-scoped rollback. It may never copy secret
backups onto FUSE. Once a key signs an envelope or a nonce is consumed,
automatic rollback is forbidden and explicit revocation/recovery is required.

Before installation, the S608/S609 fixed nonce binding must be changed from the
rejected FUSE path to the selected POSIX path and independently reviewed.
