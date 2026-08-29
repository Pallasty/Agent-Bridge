# macOS Trusted Deployment Compatibility V0

Status: **D1 READ-ONLY PREFLIGHT ACCEPTED / HOST HOLD OBSERVED / NO DEPLOYMENT**

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

### D3 — publisher and signed install

Bind the verified Darwin root to the shared publisher lease, exact remote,
private build cache, signed candidate, repository assets, rollback artifact,
and pending admission receipt. Stop before service adoption.

### D4 — migration and launchd adoption

Run an explicitly authorized writer freeze, migrate and verify state, install
canonical plists, adopt services in order, prove inode/health convergence,
and close with fresh-MCP exact-SHA admission.

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
