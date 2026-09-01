# macOS Trusted Deployment Compatibility V0

Status: **D1 AND D2 ACCEPTED / D3 EXISTING-PUBLISHER ADAPTATION STARTED / D4 MIGRATION ADAPTATION STARTED / NO DEPLOYMENT**

Date: 2026-08-29

## 1. Decision

Agent-Bridge needs a Darwin deployment backend that preserves the custody and
evidence properties of R9 without pretending that a macOS launchd host is a
Linux systemd host.

This is a sibling backend, not a fallback and not a relaxation. Production
entry points must select exactly one supported platform before inspecting or
mutating a deployment root:

- `linux-systemd-r9`, governed by the existing R9 contracts; or
- `darwin-launchd-v0`, governed by this document.

An unknown platform, mixed platform receipt, or receipt without an explicit
backend identifier fails closed. The Darwin backend must never consume or
rewrite a Linux R9 provisioning receipt.

## 2. Problem proved on the real Mac

The current macOS installation runs the wrapper and `.real` binary from
`/Users/pallasting/.local/bin` and keeps daemon, daemon-http, and Palace under
launchd. Current master still contains Darwin binary signing and launchd inode
refresh logic, but the trusted-root consumer also requires a provisioning
receipt whose source manifest includes the Linux systemd installer and whose
root activation uses Linux `renameat2(RENAME_NOREPLACE)`.

Consequently, current master compiles on macOS but cannot truthfully pass its
production deployment preflight there. Bypassing `AGENT_BRIDGE_DEPLOY_ROOT`,
manually copying the binary, or synthesizing a Linux receipt would destroy the
evidence chain and is rejected.

## 3. User-value objective

The owner should retain the ordinary workflow:

1. synchronize an exact published master;
2. build once;
3. deploy through one bounded command;
4. reconnect MCP;
5. verify the exact installed SHA and three service surfaces.

The trusted-root work may make the implementation safer, but it must not turn
routine Mac upgrades into repeated permission ceremonies or manual filesystem
assembly. Root birth and any migration remain explicit one-time gates. Normal
same-root upgrades reuse their verified custody receipt and do not ask the
owner to restate authorization already bound to the exact candidate.

## 4. Shared invariants with Linux R9

The Darwin backend must preserve all of these properties:

- authoritative remote/master is reread before build and after build;
- publication, build, install, service adoption, and fresh-MCP admission are
  distinct receipts;
- one explicit private deployment root derives binary, wrapper, assets,
  publisher state, runtime state, and rollback paths;
- the source seed is clean, published, and independently acquired;
- the production publisher never accepts a caller-supplied binary;
- one host-wide publisher lease serializes binary, wrapper, assets, pending
  admission, recovery, and rollback;
- an existing root is verified, never repaired in place during admission;
- every state migration is quiesced, receipt-bound, and rollback-preserving;
- installed binary and repository-matched assets are one candidate;
- long-lived processes must execute the installed inode;
- fresh MCP must report the same exact Git SHA before admission closes.

## 5. Darwin-specific custody contract

### 5.1 Root and filesystem

The root is an explicit absolute canonical path stored in installation state;
there is no silent fallback to `~/.local`. The recommended owner-local path is
under `~/Library/Application Support/AgentBridge/TrustedRuntime`, but the
provisioner must receive and bind the expanded absolute path.

Root admission requires:

- owner UID equals the invoking console user;
- root mode is exactly `0700` and private leaves use explicit modes;
- every ancestor is physical, non-symlink, and not replaceable by another
  user;
- the filesystem is local and supports the required Darwin inode operations;
- no unexpected POSIX ACL, Finder alias, quarantine flag, immutable flag,
  hard link, special file, or path-normalization ambiguity exists;
- APFS clones are treated as byte copies, not independent provenance; source
  and installed manifests still hash every admitted regular file.

Cloud-synchronized, network, removable, case-ambiguous, or owner-mismatched
roots fail closed.

### 5.2 Atomic activation

Root birth and candidate activation use a native helper around
`renameatx_np(..., RENAME_EXCL)` or an equivalently reviewed Darwin
no-replace primitive. Shell `mv`, check-then-rename, replacement rename, and a
Linux syscall shim are not admissible.

The helper must have synthetic races proving that a destination appearing
between preparation and activation is preserved and causes a typed failure.

### 5.3 Code signing and hashes

Mach-O signing changes installed bytes. The order is therefore frozen:

1. build the exact candidate;
2. copy into a private candidate leaf;
3. apply the configured ad-hoc or identity-bound signature;
4. run `codesign --verify --strict`;
5. hash the signed candidate;
6. atomically activate it;
7. re-read inode, signature, and hash from the installed path.

Receipts bind both the unsigned build digest and signed installed digest. A
post-receipt re-sign is drift.

### 5.4 Authentication

Interactive publication may bind a current-boot `ssh-agent` identity by
socket identity, public-key fingerprint, and live membership. Unattended
publisher operation requires a separately designed persistent credential
backend; it must not copy a private key from HOME into the trusted root.
macOS Keychain is a candidate backend, not admitted by this design gate.

## 6. launchd adoption contract

The exact initial service scope is limited to:

- `com.pallasting.agent-bridge.daemon`;
- the installed daemon-http label discovered from the canonical repository
  launchd manifest; and
- the installed Palace label discovered from that same manifest.

Implementation must reject duplicate labels, foreign plist paths, unexpected
program arguments, mixed binary paths, or an unparseable `launchctl print`
surface. Plists are rendered from repository assets, validated with
`plutil -lint`, staged privately, and installed with no-replace/backup
receipts.

Service adoption is a separate explicit gate after installation. It uses the
appropriate `bootout`/`bootstrap` or `kickstart -k` transaction, then proves:

- the expected label is loaded;
- program and first executable argument resolve to the trusted wrapper/binary;
- PID is new where restart is required;
- `lsof` maps the process to the installed binary inode;
- daemon-http, Palace, and the configured secondary listener return bounded
  health success;
- no old deleted executable remains for an in-scope service.

A mixed generation triggers rollback or stops with a recoverable pending
receipt. Health alone never substitutes for inode identity.

## 7. Runtime-state migration

The Darwin migration inventory covers the actual macOS state database family,
body-state leaves, publisher state, and repository-matched runtime assets. It
must not import unrelated caches, model weights, browser profiles, Keychain
items, OmniVoice development artifacts, or the dirty primary checkout.

Before migration, all known writers are enumerated and quiesced: launchd
services, sync jobs, maintenance jobs, MCP processes, hooks, and manual
processes holding the SQLite family. Descriptor evidence uses bounded Darwin
process inspection and fails closed when a relevant process cannot be
classified. SQLite moves through checkpoint plus backup API and integrity
verification; WAL, SHM, journal, lock, and super-journal files are never raw
copied.

## 8. Implementation increments

### D0 — design gate (this document)

Accepted when platform boundaries, shared invariants, Darwin primitives,
service scope, migration boundary, and evidence chain are explicit. D0 grants
no source implementation or deployment claim.

### D1 — read-only Darwin preflight

Add a platform-dispatched preflight that reports root eligibility, filesystem
and ACL/flag facts, launchd inventory, installed inode/signature/hash, legacy
state sources, writer inventory completeness, capacity, and exact blockers.
It performs zero writes and does not request permissions.

Acceptance requires deterministic JSON, macOS synthetic fixtures, one real
read-only run on this Mac, and unchanged binary/service/state inodes.

The D1 source candidate is `scripts/preflight-macos-trusted-deployment.py`.
It has no mutation subcommand: absent roots, services, binaries, and state are
reported as facts or blockers and are never created or repaired. Source tests
must close before the real-Mac zero-change proof advances this increment.

The 2026-08-29 real-Mac run returned `HOLD`, as expected before root birth. It
reported the absent trusted root, the currently valid signed installed binary,
all three loaded launchd surfaces, and the active legacy SQLite WAL/SHM plus
open-descriptor inventory. Before/after stat identity for the installed binary
and state database was exact, and launchd PID/program/plist observations were
unchanged. The synthetic D1 suite passed 6/6 under both the system Python and
the repository's uv Python runtime. This accepts the read-only preflight, not
root provisioning, migration, service adoption, deployment, or release.

### D2 — isolated root provisioner

Implement the Darwin no-replace helper and a Darwin-specific manifest/receipt
schema. Exercise plan/provision/verify only against a disposable private root.
Do not install the production wrapper or import production state.

The D2 source candidate separates the native no-replace primitive
(`scripts/macos-rename-exclusive.c`) from the plan/provision/verify custody
logic (`scripts/provision-macos-trusted-deployment-root.py`). Provision binds
the exact helper digest and confirmation, stages only beneath an explicit
owner-private parent, writes a Darwin-backend manifest and receipt, and then
activates with `renameatx_np(RENAME_EXCL)`. A failed exclusive activation
retains the staging tree for inspection and never repairs or replaces the
destination.

The provisioning receipt binds an immutable custody spine, not the future
contents of mutable namespaces. Root birth creates the exact private top-level
layout, including `build`, `publisher`, `lib`, and `share`; verification binds
those directory names and modes plus the immutable root manifest. Later gates
may populate only those admitted namespaces without invalidating root custody,
while an extra top-level namespace or manifest drift still fails closed.

The 2026-08-30 real disposable-root proof compiled the native helper with
warnings-as-errors, completed CLI plan/provision/verify with one stable tree
digest and a mode-0700 root, and then exercised an existing-destination race.
The helper returned the typed `73` refusal, preserved the destination marker,
and retained the source staging directory. The disposable proof directory was
moved to Trash after verification. No production root, state, binary, launchd
service, remote, or runtime was changed. This accepts D2 only.

### D3 — publisher and signed install

Bind the verified Darwin root to the shared publisher lease, exact remote,
private build cache, signed candidate, repository assets, rollback artifact,
and pending admission receipt. Stop before service adoption.

An isolated D3 implementation experiment was stopped after review showed that
it duplicated the mature publisher lease, exact-master build, signing, asset,
rollback, and pending-admission machinery already present in
`scripts/deploy_from_master.sh`. D3 is therefore redirected: add only the
smallest Darwin root/provisioning compatibility adapter to the existing
publisher, and reuse its established receipts and recovery path. A second
publisher implementation is explicitly out of scope.

The first redirected D3 slice adds Darwin `renameatx_np(RENAME_EXCL)` dispatch
to the existing trusted-root provisioner and publication/seed acquisition
paths while preserving Linux `renameat2(RENAME_NOREPLACE)`. This closes native
no-replace behavior in the mature publisher without adding a second lease,
builder, signer, asset installer, or pending-receipt implementation. It does
not yet admit a signed production install or service adoption.

The next redirected slice makes native Git clone output satisfy the existing
exact seed-config contract on macOS. The established seed acquisition and
provisioning clone paths rebuild only their owned `core`, authority-remote, and
branch sections, removing Darwin filesystem defaults or remote-HEAD branch
metadata before exact validation. Unknown configuration still fails closed;
publication, installation, and service adoption remain outside this gate.
Independent seed acquisition is narrowed to the complete `master` branch with
no tags; it remains a non-local, non-hardlinked, non-shallow clone and retains
the full authoritative branch ancestry required by later descendant checks.

A live macOS admission attempt on 2026-08-31 verified GitHub authority and
read-only plan equality at `a78f1533bf717d34312e59f1111b81ec3a176884`, but
independent seed acquisition remained `HOLD`: the current tree is about 136 MiB,
the complete `master` pack is about 47.5 MiB, and the observed SSH transfer did
not finish within the bounded 120-second clone window. No seed was activated.
Shallow, filtered, locally referenced, or alternate-credential acquisition is
not admitted by this slice; provisioning plan and production-root birth remain
open until an independent seed completes under an explicitly accepted route.
After both remotes advanced together, the read-only plan was repeated against
current common master `19fe2cedca1f1a609af83fae0da1977a3a7f691c` and again
returned `ready`. A later bounded retry received only about 452 KiB after
55 seconds and failed closed at the unchanged 120-second limit; its sibling
stage was removed and no seed was activated. The measured blocker therefore
remains unchanged.

#### D3 trusted source-closure audit

A read-only audit on 2026-08-31 rejected a source-closure implementation for
this slice. A conservative deterministic build/deploy closure can be described,
but it does not reduce the transfer performed by the currently admitted seed
acquisition protocol:

- the complete current tree contains 4,814 files and 136,663,961 bytes;
- a conservative closure containing every workspace member, the ten local
  packages transitively used by `agent-bridge`, compile-time external
  `include_*` inputs, the trusted orchestrators, wrapper/systemd files, runtime
  scripts, and admitted policy assets contains 673 files and 34,737,855 bytes;
- an archive of that closure compresses to 13,977,997 bytes, versus 39,891,700
  bytes for the complete current tree;
- the complete `master` history pack is 47,546,425 bytes; the current
  single-branch/no-tags clone must receive that pack before checkout selection
  can affect the working tree;
- a local lower-bound simulation of full commit/tree history plus only the
  current closure blobs is 17,349,209 bytes (3,068,052 bytes of commit/tree
  history and 14,281,157 bytes of current blobs). Reaching that route requires
  filtered partial-clone semantics and a path-scoped materialization contract.

The conservative closure was materialized only in an automatically removed
temporary directory. `cargo metadata --locked --offline --no-deps` accepted all
15 workspace members from it, every explicitly required input was present, and
the materialized tree contained no symlinks. This is manifest/static-input
evidence, not a release build.

Changing checkout selection alone is ineffective: seed acquisition fetches the
pack first, the root provisioner currently clones and checks out the complete
seed, and the publisher materializes the complete authoritative tree with
`git archive`. A useful closure route would therefore need a new partial-clone
filter contract, generated path manifest, blob-completeness receipt, provisioner
copy rule, and path-scoped archive rule. That is a new acquisition protocol,
not the minimum Darwin compatibility adapter, and the measured compressed
reduction is about 63.5%, below the 70% design threshold used for this audit.

Decision: `SOURCE_CLOSURE_AUDIT_COMPLETE; OPTIMIZATION_NOT_ADMITTED;
TRUSTED_SEED_NETWORK_HOLD`. Do not add a closure manifest or repeat the same
bounded clone merely to collect another timeout. Retain the existing complete
`master`/no-tags protocol and retry it only after the network route materially
improves or a separately authorized transport-design gate changes the contract.

### D4 — migration and launchd adoption

Run an explicitly authorized writer freeze, migrate and verify state, install
canonical plists, adopt services in order, prove inode/health convergence,
and close with fresh-MCP exact-SHA admission.

The first source-only D4 migration slice keeps the established migration tool
and dispatches its quiescence and open-descriptor gates by platform. Darwin
requires the fixed service, sync, maintenance, and avatar job set to be fully
unloaded rather than merely idle; it uses bounded fixed-path `lsof` inventory,
binds those Darwin facts into the receipt shape, and accepts Apple Python 3.9's
SQLite status API. Focused Darwin tests, the 20-test D1/D2 suite, and the
7-test publisher/seed suite pass. A real read-only probe correctly returned
`HOLD` for the loaded daemon and open production SQLite descriptors without
changing the database or installed-binary identities.

The second source-only slice platform-dispatches the existing atomic
runtime-state exchange. Darwin binds `renameatx_np(AT_FDCWD, ..., RENAME_SWAP)`
with `AT_FDCWD=-2` and `RENAME_SWAP=0x00000002`; Linux retains
`renameat2(..., RENAME_EXCHANGE)` with `AT_FDCWD=-100`. A real Darwin test uses
only disposable directories to prove inode/content exchange and reversal. A
disposable migration fixture then injects failure immediately before receipt
publication and proves the established automatic exchange-back restores the
empty runtime skeleton with no receipt or stage residue.

These source-only slices do not stop any production job, migrate production
state, activate the production Darwin runtime-state root, install/adopt a
plist, publish, deploy, or accept D4. Those remain separate gates.

## 9. Required negative tests

At minimum, implementation must reject:

- Linux receipt or backend identifier on Darwin;
- absent, relative, symlinked, network, cloud-synchronized, replaceable, or
  ACL/flag-ambiguous root;
- destination-appearance activation race;
- dirty or unpublished seed and remote movement during build;
- caller binary, post-sign hash drift, invalid signature, or wrong architecture;
- duplicate/foreign launchd label or unexpected program arguments;
- service health from an old/deleted inode;
- open SQLite writer, WAL reappearance, unknown sidecar, or incomplete process
  visibility;
- stale pending admission, concurrent publisher, or rollback from a different
  candidate;
- fresh MCP reporting a different Git SHA.

## 10. Frozen acceptance statement

Until D1 through D4 are separately implemented and accepted, the truthful
status is:

`DARWIN_TRUSTED_DEPLOYMENT_DESIGN_ACCEPTED; IMPLEMENTATION_PENDING; CURRENT_MAC_RUNTIME_UNCHANGED`.

The existing Linux R9 `HOLD` and its production evidence are unchanged by this
document.
