# AB interoception: trusted deployment-root provisioning

Date: 2026-08-28

Status: **the original R9-M2 source at
`55954e2458eefae261ae761e3035b88536fcc782` is published; the R9-M6 exact-agent,
large-model, and no-replace hardening is `SOURCE_READY` at
`4643c4cad3789380f15cba9e960727c23dbd90b8`; one eligible private input bundle
is prepared, but the final candidate-matching seed and read-only production
plan remain pending; the root is not provisioned or deployed and production
remains `HOLD`**.

Scope: one operator-confirmed creation of a new private Agent Bridge deployment
root before wrapper installation or publication

Depends on:

- `INTEROCEPTION_DURABLE_WORKLOAD_RECEIPTS_2026_08_27.md`;
- `INTEROCEPTION_TRUSTED_RUNTIME_STATE_MIGRATION_2026_08_28.md`; and
- `2026-08-28-r9-installed-acceptance-gate.md`.

## Decision

R9-M2 is the missing birth organ for the R9 trusted body. The wrapper,
publisher, state migrator, and current-boot binder already reject an unsafe or
incomplete root, but before this increment the operator still had to assemble
the source clone, Git key, known-hosts file, toolchain, configuration,
credentials, build cache, publisher mutex, and custody modes manually. That
made the most authority-sensitive step the least executable and least
auditable step.

The bounded provisioning flow is:

```text
published candidate + separately prepared private inputs
  -> read-only plan and complete input snapshot
  -> owner reviews exact candidate-bound confirmation
  -> private sibling stage
  -> clean local clone of the published seed
  -> normalized physical source/toolchain/config custody
  -> publisher mutex and bootstrap receipt
  -> complete file/directory fsync
  -> one atomic no-replace stage-to-root rename and parent fsync
  -> independent fixed-path verify
  -> wrapper verifies before and after acquiring the same mutex
  -> publisher verifies before mutation and again under that mutex
  -> authenticated GitLab fetch becomes publication authority
```

The user-cost measure is concrete: one reviewed manifest and one confirmation
replace an unbounded sequence of manual `mkdir`, `cp`, `chmod`, clone, and lock
steps. A bad manifest, stale input, wrong candidate, unsafe parent, insufficient
capacity, or wrong confirmation changes zero target paths. A valid root can be
independently reverified without revealing credential bytes.

## Commands and authority

`scripts/provision-trusted-deployment-root.py` exposes three commands:

- `plan --manifest M --deploy-root R` is the default read-only operation. It
  emits the exact `PROVISION:<candidate>:<plan_digest>` confirmation but never
  creates a root, stage, lock, receipt, Git ref, or build-cache entry.
- `provision --manifest M --deploy-root R --confirm ...` is the sole writing
  operation. It refuses an existing root and never merges into or overwrites
  one.
- `verify --deploy-root R [--inherited-lock-fd N]` is read-only and must run
  from the fixed provisioned source path. With an inherited descriptor it also
  proves that the caller owns the exact provisioned publisher-lock inode.

The provisioning receipt is a custody statement, not publication authority.
The source seed must already name one published candidate through exact clean
`HEAD` and `refs/remotes/gitlab/master`, but provisioning uses a local
`--no-local --no-hardlinks` clone and performs no network fetch. The publisher
must later authenticate to the exact GitLab SSH URL with either the installed
private key or the installed public selector plus its still-live bound agent
socket, and the installed known-hosts file. A local source, GitHub mirror, file
remote, receipt, or
operator confirmation cannot substitute for that fetch.

The receipt therefore records
`bootstrap_seed_not_publication_authority`. The publisher refuses a fetched
master different from the source candidate that provisioning verification
just returned. If GitLab advanced, the release owner must explicitly advance
the private clone's `HEAD` and `gitlab/master` together and rerun verification;
the publisher never silently upgrades the intended candidate.

## Manifest and input boundary

The exact mode-`0600`, euid-owned manifest binds:

- schema, one 40-hex candidate, canonical absent target root, exact GitLab SSH
  URL, and the canonical bootstrap source repository;
- exact path and SHA-256 for known-hosts, `machine.env`, and credentials plus
  exactly one Git authentication form: either the original private-key file,
  or an owned mode-`0600` agent socket with its inode facts, exact public-key
  selector bytes/fingerprint, and live membership;
- one physical private toolchain root; and
- maximum source/toolchain files and bytes plus at least a fixed 2 GiB
  post-copy free-space reserve.

The exact confirmation additionally binds freshly computed source and
toolchain manifests, all file input digests/sizes, candidate tree, and manifest
digest. `provision` recomputes the whole plan before accepting the confirmation;
a plan output is not a reusable write capability after any input changes.

Every manifest/input/source/toolchain ancestor must be physical and owned by
the effective user or root. A group/other-writable ancestor is admitted only
when it is the root-owned sticky boundary such as `/tmp`; an euid-owned mode
`0777` workspace remains replaceable and blocks. Source, toolchain, and target
paths may not overlap.

The source seed must be a standalone private repository, not a linked-worktree
Git file. It must be completely clean, have exact candidate-equal `HEAD` and
`gitlab/master`, the one exact GitLab URL, no gitlinks, no alternates, grafts,
local attributes, or HTTP alternates, and an exact bounded local Git config.
All Git operations use the system binary with global/system config disabled,
hooks disabled, object replacements disabled, prompting disabled, and a fixed
environment.

File mode requires a mode-`0600` OpenSSH private key. Agent mode never exports
that private key: it binds the exact public selector, socket custody, and live
membership, and installs only the selector plus a canonical authentication
descriptor. The known-hosts input may contain only `gitlab.com` or hashed host
entries. No credential value is printed.
The machine and credential files are copied byte-for-byte and receipt-bound;
their semantic admission remains the wrapper/binder's job. R9-M2 v1 provides
no in-place credential, machine-config, or toolchain rotation. Such a change
requires a separately governed update/reseal design or a fresh root; it cannot
rewrite this birth receipt.

## Physical tree and receipt

Provisioning creates only a new private sibling stage. It forms:

- `source/agent-bridge` as a non-local, non-hardlinked clone of the seed;
- `config/git/{gitlab_deploy_key,known_hosts}` in file mode, or
  `config/git/{gitlab_agent_key.pub,authentication.json,known_hosts}` in agent
  mode;
- `config/agent-bridge/{machine.env,credentials}`;
- a normalized `toolchain` containing executable `bin/cargo` and `bin/rustc`;
- private `build-cache`, `publisher-state/deploy`, and `provisioning`
  directories; and
- the exact mode-`0600`
  `publisher-state/deploy/publisher.kernel.lock`.

Every created directory is mode `0700`. Ordinary files are mode `0600`, owner
executables are mode `0700`, and the deploy/provision/migration/systemd
orchestrators receive their exact production modes. Symlinks, hardlinks,
devices, sockets, FIFOs, foreign ownership, unsafe local Git config, unknown
manifest keys, duplicate JSON keys, source dirt, collisions, and capacity
uncertainty fail closed.

The mode-`0600` receipt at `provisioning/current.json` binds the root
device/inode/owner/mode, candidate and initial tree, canonical manifest and
plan, initial source and toolchain manifests, installed input facts, publisher
lock inode, and its own domain-separated digest. The stored manifest is also
canonical and private.

Source is the one intentionally advancing component. `verify` accepts only a
clean exact `HEAD == gitlab/master` descendant of the birth candidate, exact
GitLab URL/config, no local overrides, private physical entries, and candidate-
matching critical orchestrator bytes. This permits explicit release-owner
advancement without turning the birth receipt into a mutable source snapshot.
The key, known-hosts, toolchain, machine config, credentials, root identity,
and publisher lock remain byte/inode bound.

All staged regular files and directories are synced before one Linux
`renameat2(RENAME_NOREPLACE)` activation; the parent is synced after it. A
target appearing during the final race window is preserved and causes a
fail-closed rejection. A pre-rename caught failure removes only the exact
deterministic private stage after proving it contains no unsafe
inode. A pre-existing stage is never reused or cleaned. A process/power loss
around activation remains fail-closed/manual-recovery territory; R9-M2 does
not claim unattended crash recovery or deletion authority over an ambiguous
root.

## Consumer handoff

The wrapper installer now requires the provisioner at its fixed mode-`0700`
source path. A dry run verifies the receipt read-only. A real install verifies
once before mutation, acquires the pre-provisioned publisher mutex, and
verifies again with that inherited descriptor before moving or installing the
wrapper.

The publisher likewise verifies before its first canonical mutation and again
after acquiring the exact same mutex. Its clean authenticated fetch must return
the same candidate as the immediately verified private source. Missing,
malformed, tampered, or stale provisioning evidence blocks before fetch,
build, or binary publication.

After authenticated publication the existing publisher pending-admission
receipt becomes the authority consumed by R9-M1 migration and systemd binding.
The provisioning receipt never claims that a binary was built, installed,
migrated, adopted, restarted, healthy, or visible through a fresh MCP.

## Current production truth

Production remains `HOLD`. R9-M6 now permits the already-enrolled current-boot
gcr agent as an exact root authentication input without copying its private
key. This is not an unattended credential claim: publication fails before Git
fetch whenever that exact agent identity is unavailable. The current
development worktrees live beneath the euid-owned
mode-`0777` `/Data/CascadeProjects` boundary and use linked-worktree Git
metadata, so they remain ineligible as a provisioning seed. An independent
private seed exists for the preceding published candidate, and R9-M6 prepared
an official Rust 1.96.1 toolchain, exact-revision GTE assets, minimal machine
file, empty credential policy file, known-hosts, and public agent selector at
`/Data/agent-bridge-r9-bootstrap/trusted-inputs-r9-m6`. Publication and a fresh
independent seed at the final R9-M6 reporting candidate are still required
before the production plan. `/Data/agent-bridge-r9` remains absent.

R9-M2 does not alter the Yama decision. The later migration window must still
quiesce ssh-agent, Waydroid, MCP, hook, CLI, and every other non-manager same-
UID process whose descriptor table cannot be proven. No service, timer, unit,
database, state leaf, root, key, credential, or receipt was changed in this
increment.

## Source-candidate acceptance

Acceptance requires zero-write plan and wrong-confirmation proof; happy atomic
provision/independent verify; descendant-only source advancement; inherited
lock identity; strict JSON/input digests; source authority/config/override
rejection; unsafe ancestors, symlinks, hardlinks, special files, overlaps,
capacity, stage collision, and post-provision tamper rejection; wrapper and
publisher consumer gates; and all existing R9-M1/R9 regressions.

Original implementation identity:
`55954e2458eefae261ae761e3035b88536fcc782`. R9-M6 compatibility and boundary
hardening identity: `4643c4cad3789380f15cba9e960727c23dbd90b8`.

Current verification: provisioning `14/14`, publication/seed `6/6`, credential
ceremony `4/4`, wrapper, publisher lease/recovery, R9-M1 migration `15/15`,
systemd
binder, post-build master race, pinned runtime assets, audio/runtime parity,
GTE readiness, shell syntax, Python AST, and whitespace gates all pass. Rust
1.96.1 built/tested `ab-core`; no Rust source changed.
Fixture success cannot be relabeled as GitLab publication, production root
creation, migration, systemd adoption, or live admission.
