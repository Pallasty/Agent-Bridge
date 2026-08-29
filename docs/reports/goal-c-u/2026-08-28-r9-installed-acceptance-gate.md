# R9 installed acceptance gate

Date: 2026-08-28

Status: R9-M1–M5 source is published and independently seeded through
`08f0bbeecf8f991f1dd37693b45aeedd310f20da`; R9-M6 is `SOURCE_READY` at
`4643c4cad3789380f15cba9e960727c23dbd90b8` with one verified private input
bundle; the final R9-M6 descendant is not yet published or reacquired, and the
root is not provisioned, installed, migrated, restarted, or live-admitted;
production remains `HOLD` and the current installation remains `FAIL_CLOSED`

## Decision boundary

Implementation commit
`a4f4f4e153a5a824f28e6f1486c670af38c15ea5` closes the source-side gap between
the R9 durable workload-receipt organ and a permission-capable installed body.
It is an implementation identity, not publication authority by itself. The
reporting descendant `b2d06bc385c1aa25110c7a8f579fb4da8ced1847` was
published by fast-forward to authoritative GitLab `master` with `ci.skip` on
2026-08-29.

The earlier isolated restart exercise remains valid evidence for source
candidate `9bc924a2c1641983ac954ee9416e18ddb5fcdf77` and local binary SHA-256
`f0b5fbdfe295d91f7c21f529aff0e9414bd4ebbe8948b1c4a258bdcb111dce4c`.
It does not prove that the new deployment-root framework has been published or
that a production service has adopted it.

R9-M1 is the next bounded implementation inside R9, not an R10 lane. It closes
the split-brain risk between the legacy HOME database/body-state tree and the
new trusted-root database/body-state tree. Its source-ready implementation is
`eda927d1837b50c6680ce3ea337456a79e52a965`; this identity is local source
evidence, not publication or production-adoption authority.

R9-M2 closes the next bounded gap: creation of the deployment root itself. Its
source-ready implementation adds a zero-write plan, an exact-digest-confirmed
atomic provision operation, and an independent fixed-path verifier. The
resulting birth receipt is required by both wrapper and publisher before their
first build/install mutation and is rechecked while they hold the shared
publisher lock. A provisioned local seed is explicitly not publication
authority.

The original R9-M2 implementation identity is
`55954e2458eefae261ae761e3035b88536fcc782`. R9-M6 exact-agent, large-model,
and atomic no-replace hardening is
`4643c4cad3789380f15cba9e960727c23dbd90b8`. Neither identity is a live
provisioning receipt.

No production file, service, unit, database, credential, or workload-receipt
spool was changed in this increment. No service was stopped, restarted, or
reloaded. The only systemd exercise used a private fake-manager fixture.

## Source-ready trusted-root framework

### One explicit custody root and publisher

Production deployment now requires one pre-existing, physical, euid-owned,
exact-`0700` `AGENT_BRIDGE_DEPLOY_ROOT`. It has no HOME fallback. Its source
clone, Git metadata, scripts, GitLab SSH key and known-hosts file, toolchain,
installed binary, wrapper, assets, configuration, publisher metadata, and
runtime state are independently checked before use. The external private build
cache is separately bound to a deployment-root device/inode fingerprint.

The publisher now:

- accepts only the authenticated `pallasting/agent-bridge` GitLab SSH remote;
- executes Git, Cargo, rustc, and probe helpers through bounded clean
  environments, disables hooks/replacements/system attributes, and rejects
  local attributes, grafts, and object alternates;
- builds from a private `git archive` snapshot of one fetched 40-hex commit,
  then hashes the candidate before and after freezing it;
- disables production `--use-binary`; the retained synthetic option is
  canonicalized and contained below its private OS-temp fixture root;
- separates `$ROOT/publisher-state` from `$ROOT/runtime-state`, including
  private HOME/XDG/tmp, `workload-receipts`, and `workload-tmp` leaves;
- serializes wrapper, publisher, and systemd-binding mutations with the same
  physical mode-`0600` kernel lock;
- binds pending admission to binary SHA/inode/mode and the exact wrapper,
  audio, policy, and runtime-asset manifest; and
- never overwrites the wrapper. The installed wrapper must already match the
  authoritative candidate byte-for-byte.

### Wrapper and transient workload custody

The trusted wrapper derives its real binary and assets from its physical
sibling root, clears loader/shell/language injection variables, pins private
HOME/XDG/tmp and receipt paths, and prevents a loaded machine file from
overriding parent-supplied deployment pins. Alternate-root services never
fall back to the legacy HOME credential notebook or HOME CLI paths.

Non-receipt-bound cgroup supervisor allocations now use
`AGENT_BRIDGE_CGROUP_TRANSIENT_DIR`. A trusted service writes them below
`$ROOT/runtime-state/workload-tmp` even though its systemd runtime/bus
directory is read-only. Legacy invocations retain the old XDG runtime fallback
only when the explicit policy is absent. `agent_spawn` input cannot override
either the durable receipt root or transient custody root.

### Complete current-boot systemd binding

`scripts/systemd/install-trusted-daemon-root.sh` installs three complete
current-boot unit replacements under the validated user-manager runtime
control directory. It does not use drop-ins, `systemctl edit`, enable a unit,
or restart a service. All three files stage privately and each activates by a
same-filesystem rename. The successful path performs one `daemon-reload`. A
failed transaction deletes every fragment it activated and attempts a
compensating reload; that reload is best-effort. If it fails, the manager view
is unknown, no service may be started, and explicit recovery verification is
required.

Before its first write, the binder validates:

- the actual manager `UnitPath`, including passwd HOME and both user unit
  roots, as physical and non-replaceable;
- absence of foreign drop-ins and unexpected values in its enumerated
  activation/reverse-relation allowlist, while recording the pre-existing
  effective `WantedBy` set (empty for a clean un-enabled service or exactly
  `default.target` for the currently enabled services);
- the publisher pending candidate, installed asset fingerprint, safe-clone
  HEAD and `refs/remotes/gitlab/master`, exact GitLab URL, and candidate bytes
  of the installer, wrapper, audio, policy, and runtime assets; and
- the bounded machine configuration and every pinned filesystem input.

After the successful reload, it separately verifies the effective fragment
bytes/path/mode, no drop-ins, no execution hooks or environment files, the
enumerated activation/reverse relations including exact preservation of the
recorded `WantedBy`, and exact hardening, ExecStart, and environment state. The
effective unit uses clean `/usr/bin/env -i` execution, no capabilities,
`NoNewPrivileges`, strict filesystem protection, `/home` and `/root`
inaccessible, and the deployment root and user runtime read-only. Within
`$ROOT`, only `$ROOT/runtime-state` is writable; `PrivateTmp=yes` separately
provides the service-private temporary tree.

External `Before`/`After` ordering edges are not part of the enumerated
relation allowlist. They cannot grant activation by themselves, but remain an
ordering/denial-of-service residual for real-manager smoke and later stronger
root-managed isolation. The shared publisher mutex protects the cooperating
wrapper, publisher, and binder writers; it is not a same-UID adversary fence
and does not imply that all preflight inputs are rehashed after reload.

The machine configuration is parsed without sourcing or printing values. It
accepts only `export KEY=literal`, rejects duplicate, quoted, expanded,
command-bearing, secret-like, state-pin, legacy app-control, and unknown keys,
and admits only the bounded substrate/context/retrieval/toolset/embed and
voice/ONNX/Qwen settings. Every admitted asset path must be physical beneath
the trusted root with exact private parent custody. Qwen Rust enablement is
bound to its executable, model directory, and profile as one contract.

This is a current-boot adoption seam, not reboot-persistent unit authority.
The user manager and D-Bus remain a same-UID boundary. Stronger isolation would
require root-managed system units and dedicated service identities.

## R9-M1 trusted runtime-state migration source-ready implementation

The migration tool defaults to read-only `preflight`. Its only writing path is
an explicitly confirmed `migrate` operation bound to the exact publisher
candidate and pending-admission digest; `verify` is read-only. It never stops,
starts, enables, disables, reloads, or kills a process. The release operator
must perform and preserve quiescence.

The writer set is deliberately larger than the three long-running services. It
also includes sync, memory-decay-unused, distill, and digest timer/oneshot
pairs, plus the day2 audit timer/oneshot as a conservative gate. External MCP
servers, hooks, CLIs, and manual jobs with an open descriptor to the legacy or
destination SQLite/`-wal`/`-shm`/journal family block migration; they are reported, not
killed. A dormant same-UID process that later reopens the old path remains a
bounded handoff residual and must be held quiescent by the operator.

Unreadable same-UID descriptor tables fail closed under Yama. Only the exact
`systemd --user` manager and its exact same-scope `(sd-pam)` child are excluded
as user-manager infrastructure. Current ssh-agent, Waydroid, and other session
processes therefore remain an explicit live preflight blocker; no broad
permission-error skip was admitted.

Writer state is type-aware. Loaded services/oneshots must be
`inactive`/`dead` with `MainPID=0`; a loaded timer has no service-style PID
proof and must be `inactive`/`dead` plus `disabled` or `masked`. A missing
timer is accepted only as `LoadState=not-found` with an empty `UnitFileState`.
Malformed, ambiguous, stopped-but-enabled, or unknown states block and the
typed baseline becomes receipt evidence.

The database path is migrated through SQLite checkpoint, backup API, and
source/target integrity checks. A WAL-bearing preflight remains byte-passive
and defers its logical integrity check to the separately confirmed checkpoint;
a WAL-free source is checked immutably. DB/WAL/SHM, rollback/super-journals,
and locks are not raw-copied. The
explicit migration plan inventories every immediate legacy leaf and gives each
sidecar a retain, retire, or reconstruct disposition. Unknown/new entries,
symlinks, hard links, special files, type changes, duplicate destinations, and
target collisions fail closed.

Every inventory source must remain outside the trusted deployment root. The
existing `/Data/.agent-bridge-state` body-state source cannot be relabeled as
the new root and migrated into itself; a separate private root must be
provisioned after authoritative publication. The receipt also freezes the
post-checkpoint source DB-family sidecar state, so a recreated or replaced
legacy WAL/SHM/journal family invalidates `verify` and exposes a late writer.

A completed private receipt binds the candidate, pending admission, physical
root, plan, mappings/source and target manifests, source/target DB facts, and
the typed quiesced unit baseline. The binder must verify the exact candidate
migration tool, current receipt, and typed quiescence under the shared
publisher lock before any mutation. It repeats quiescence immediately before
fragment activation/reload, then reruns both receipt verification and
quiescence after `daemon-reload`; this catches a short-lived writer that
changed the legacy DB and exited between inactive-state samples. A rearmed
timer/service or stale receipt blocks acceptance. Exact-existing no-mutation
replay is admitted only in the same migration freeze window, before an adopted
service writes the target, and still verifies receipt plus quiescence. After
adoption, target-manifest drift is expected and binder replay must fail closed;
the installed verifier owns steady-state acceptance. The binder never starts
or restarts services.

This is source-ready local work only. No production state, SQLite database,
service, timer, unit, credential, drop-in, or migration receipt was changed.
The detailed contract is in
`docs/design/INTEROCEPTION_TRUSTED_RUNTIME_STATE_MIGRATION_2026_08_28.md`.

## R9-M2 trusted deployment-root provisioning source-ready implementation

The provisioning tool accepts only a clean, standalone, exact-candidate seed
with the authoritative GitLab remote and strictly private physical custody.
It separately binds known-hosts, minimal machine file, credentials, and a
bounded Cargo/rustc toolchain by digest and inode-safe inventory. Git
authentication is an exact tagged union: either the original mode-`0600`
private-key file or the R9-M6 mode-`0600` agent socket plus exact public
selector/fingerprint and live membership. Agent mode never exports a private
key. Source, toolchain, target, and legacy inventory roots may not overlap.
Unsafe writable ancestry, linked worktrees, symlinks, special files, hard
links, Git alternates/grafts, capacity shortfall, and input drift fail closed
before target creation.

`plan` is byte-passive and emits a canonical manifest plus confirmation token.
`provision` requires that exact token, constructs one private sibling stage,
clones without local-object or hard-link borrowing, copies and normalizes the
bounded inputs, creates the publisher lock and canonical birth receipt, fsyncs
the tree, and activates only by same-parent Linux atomic no-replace rename into
an absent root.
`verify` is read-only and accepts the birth candidate or a clean published
descendant while independently rebinding the fixed inputs, receipt, source
configuration, critical scripts, and optional inherited publisher-lock file
descriptor. The publisher additionally requires the fetched authoritative
master to equal the provisioning verifier's current source candidate.

Version 1 deliberately has no in-place key, credential, machine-file, or
toolchain rotation. A crash at the final activation durability boundary is an
operator-recovery residual, not a license to reuse a partial stage or infer
success. The detailed contract is in
`docs/design/INTEROCEPTION_TRUSTED_DEPLOYMENT_ROOT_PROVISIONING_2026_08_28.md`.

## R9-M3 authoritative publication and seed source-ready implementation

R9-M3 is source-ready locally at
`2107da2f0560f98c2820700f11c64093afd37783`. It binds an exact clean candidate
and current GitLab master into a zero-write plan; performs only an explicitly
confirmed fast-forward push with GitLab `ci.skip`; reacquires the result through
an independent authenticated, non-local, non-hardlinked clone; and verifies
remote, seed, tracking ref, configuration, gitlink absence, and private inode
custody before R9-M2 may consume it. CI was deliberately not introduced or
run for this increment.

The isolated publication/seed harness is `4/4 PASS` and the updated R9-M2
provisioning harness remains `10/10 PASS`. Correction measured 2026-08-29: an
owned mode-`0600` gcr agent socket authenticates GitLab as `@pallasting` and
reads authoritative master. The earlier denial reflected a missing inherited
`SSH_AUTH_SOCK`, not absence of a usable local identity. Publication and seed
remain distinct evidence, and production remains `HOLD`.

## R9-M4 GitLab deploy credential ceremony source-ready implementation

R9-M4 is source-ready locally at
`573ae19b6f530d0cfb52be9b88acb8292a5390e4`. It adds a zero-write plan,
exact-confirm fresh Ed25519 generation, GitLab-official host-key anchors,
public-only enrollment packet, private receipt, atomic no-replace activation,
and independent verification. The receipt says `local_key_not_enrolled`; no
local action is allowed to infer GitLab write authority.

R9-M4 `4/4`, R9-M3 `4/4`, and R9-M2 `10/10` targeted harnesses pass. CI was
explicitly skipped. No real key was generated or enrolled; because the
current operator can use the agent-only identity, R9-M4 is an optional durable
credential route rather than a publication prerequisite. Production remains
`HOLD`.

## R9-M5 existing-agent independent-seed source-ready implementation

R9-M5 is source-ready locally at
`c38497ec8ff033f483d99d8dbb98dfacb67b8dfd`. It extends the existing R9-M3
manifest without breaking fixed-file key mode: an operator may instead bind an
owned mode-`0600` agent socket, exact public-key file, and SHA-256 fingerprint.
The public key is passed to OpenSSH with `IdentitiesOnly=yes` as the selector
for the matching private identity that remains inside the agent. Socket
device/inode/mode/owner, public-key bytes/fingerprint, agent membership, and
known-hosts bytes are checked again before every Git operation.

Seed activation now fsyncs every cloned regular file and directory, uses Linux
atomic no-replace rename, and fsyncs the private seed parent. A destination
appearing during activation is never overwritten. The R9-M3 harness is now
`6/6 PASS`; R9-M2 remains `10/10 PASS`; Python AST and whitespace gates pass.
CI remains deliberately skipped. This source milestone does not generate or
export a private key, provision the trusted deployment root, mutate services,
or relax production `HOLD`.

## R9-M6 trusted inputs and exact-agent root compatibility

R9-M6 is source-ready at
`4643c4cad3789380f15cba9e960727c23dbd90b8`. It lets R9-M2 and the production
publisher consume the exact current-boot agent identity already proven by
R9-M5 while retaining fixed-private-key compatibility. The root stores only a
mode-`0600` public selector and canonical authentication descriptor; every Git
operation requires the same safe socket and loaded fingerprint again. Offline
receipt verification binds the durable public facts without claiming the
agent is permanently available.

The private bundle at
`/Data/agent-bridge-r9-bootstrap/trusted-inputs-r9-m6` contains a SHA-verified
official Rust 1.96.1 standalone toolchain, exact-revision GTE multilingual
model assets, GitLab known-hosts, the public selector, a four-key minimal
machine file, and an explicit no-persistent-provider-credentials file. It has
177 physical singly linked files, no special nodes or symlinks, exact private
modes, and 1,916,000,745 logical bytes. The prior unsafe HOME toolchain and
machine file were not copied.

R9-M6 also makes root activation `renameat2(RENAME_NOREPLACE)`, aligns trusted
Cargo/rustc modes at `0700`, corrects the critical `creds.example` source leaf,
and makes tree-file hashing honor the explicit bounded tree-byte limit so the
1,255,502,649-byte model is admissible. Provisioning is `14/14 PASS`; the
publisher, R9-M3/M5 `6/6`, R9-M4 `4/4`, R9-M1 `15/15`, wrapper, systemd,
remote-race, pinned-asset, audio parity, and GTE readiness gates pass. CI was
explicitly skipped. `/Data/agent-bridge-r9` remains absent.

## Verification ledger

The baseline rows below preserve earlier durable-receipt and trusted-root
evidence. R9-M6 reran the provisioning, publication/seed, credential,
migration, wrapper, publisher, post-build race, pinned-assets, runtime/audio,
GTE readiness, systemd binder, and syntax/whitespace gates. The unchanged Rust
`157` and wrapper-Rust `4/4` rows remain prior evidence because no Rust source
changed; the trusted Rust 1.96.1 toolchain separately built and tested
`ab-core` offline. A full workspace run reached the final large debug link but
stopped for `/Data` capacity, not a failed assertion, and its generated target
was removed. All verification used debug/test artifacts and private fixtures;
no production path was used.

| Gate | Result |
|---|---|
| Installed-verifier and restart-harness Python suites | `62/62 PASS` with warnings as errors |
| `ab-agent` full debug suite | `157 PASS`, 6 real-provider/configured-runtime tests ignored by design |
| Wrapper Rust environment suite | `4/4 PASS` |
| Trusted wrapper installer shell suite | `wrapper-trusted-install-ok` |
| Publisher lease/recovery/admission suite | `publisher-lease-v0-ok` |
| Post-build remote race gate | `postbuild-master-race-gate-ok` |
| Pinned master runtime assets | `pinned-master-runtime-assets-ok` |
| Binary/audio/runtime parity | `PASS` |
| Trusted systemd binder adversarial suite | `systemd-trusted-daemon-root-ok`; final implementation also passed repeated worker runs |
| Changed shell syntax, Python AST, and staged whitespace | `PASS`; no Rust source changed |
| R9-M1 migration harness | `15/15 PASS` with warnings as errors |
| R9-M2/M6 provisioning and agent-auth harness | `14/14 PASS` with warnings as errors |
| R9-M3/M5 publication and seed harness | `6/6 PASS` |
| R9-M4 optional credential harness | `4/4 PASS` |
| Trusted Rust 1.96.1 smoke | `ab-core` build/test and doc-test PASS offline; full workspace capacity-limited at final debug link |
| Migration-aware binder handoff | `systemd-trusted-daemon-root-ok`; receipt/quiescence gates exercised at initial, pre-activation, and post-reload boundaries |
| Independent adversarial review | `APPROVED WITH RESIDUALS`; no reproducible blocker, major, or minor defect |

The repository has unrelated pre-existing whole-workspace rustfmt drift; the
two touched Rust files pass exact `rustfmt --check` and were not widened into a
mechanical repository rewrite.

## Current live truth and blockers

The existing installation was deliberately left unchanged and remains outside
the trusted boundary:

- `/home/pallasting` and its user-unit directory are root-owned mode `0777` on
  the replaceable FUSE mount. The new `UnitPath` gate therefore refuses with
  zero manager/runtime-unit writes.
- The three current services still resolve units below that HOME. Daemon and
  daemon-http also have foreign `int8-model.conf` drop-ins. Their ONNX/embed
  settings must be moved into a reviewed allowlisted machine file and the
  drop-ins archived before binding.
- `/Data/.agent-bridge-state` is a physical euid-owned mode-`0700` legacy
  body-state source. R9-M1 forbids inventory sources from residing inside the
  deployment root, so this path cannot double as the new root. A separate
  private root with source/config/toolchain/bin/publisher/runtime layout and
  authentication must still be provisioned; no root was created here. The
  current development worktrees are mode `0777` and use linked Git metadata,
  while the HOME toolchain inherits the unsafe mode-`0777` FUSE boundary;
  R9-M2 correctly rejects both. R9-M6 instead prepared a private standalone
  input bundle and R9-M5 acquired a private seed at `08f0bbee`; a fresh seed at
  the final R9-M6 candidate is still required.
- The legacy machine file is on the unsafe HOME mount and contains a HOME model
  path plus settings outside the bounded service allowlist. It was not copied.
  R9-M6 retained four reviewed non-secret settings in a minimal private file.
  Current daemon, daemon-http, and Palace environments expose no secret-like
  keys, so no persistent external-provider credential was admitted.
- Existing SQLite plus WAL state remains on the unsafe mount. Migration must
  quiesce the complete service/timer/oneshot writer set and reject external
  MCP/hook/manual-process database descriptors before using SQLite checkpoint,
  backup, and integrity procedures; raw copying a database together with
  WAL/SHM, rollback/super-journal, or lock files is prohibited. Existing
  app-control, Resident, Avatar,
  and other body-state leaves require an exhaustive retain/retire/reconstruct
  plan into `$ROOT/runtime-state` because the hardened units make the rest of
  `$ROOT` read-only. Unknown entries or unsafe inode/collision states stop the
  migration.
- `/Data` has about 8 GiB free at 97% use after preparing the trusted bundle.
  The root filesystem backing the
  intended `/var/tmp` production build cache has about 59 GiB free; production
  migration still needs an explicit capacity margin and rollback copy budget.
- Current-boot GitLab operator authentication is available through the
  mode-`0600` gcr agent socket. R9-M6 binds it without exporting a private key,
  but this remains current-boot rather than unattended authority. The official
  toolchain, model assets, minimal machine file, known-hosts, public selector,
  and empty persistent-credential policy are prepared; final publication,
  fresh seed acquisition, and the read-only production plan remain pending.
- Yama currently hides descriptor tables for several non-manager same-UID
  session processes, including the SSH agent and Waydroid components. The
  strict migration gate intentionally blocks until those processes are
  quiesced or a separately reviewed privileged inspection path exists.
- A real systemd parser/mount-namespace/cgroup/service smoke has not run.
  Fake-manager transaction proof cannot be relabeled as live adoption.
- External `Before`/`After` ordering edges remain outside the enumerated
  activation/reverse-relation gate. Any failed compensating reload also leaves
  the manager view unknown until an explicit read-only recovery check proves
  otherwise.

The previously observed installed verifier result therefore remains
`FAIL_CLOSED`. The physical installed file had SHA-256
`624d379f4a71eced931d68a42e3ee4009744c16639b88f64f21dde945c1bb9c0`,
but its owner boundary failed, the production receipt root was absent, and
daemon, daemon-http, and Palace executed deleted old binary inodes. Service
activity and exact loopback `ok` health were not enough to override those
failures.

## Frozen release and acceptance order

The release owner must preserve this order. A later step cannot repair or
substitute for a missing earlier authority boundary.

1. Publish the final clean R9-M6 descendant to authoritative GitLab `master`
   with the exact authenticated agent identity and `ci.skip`. Record the exact
   40-hex commit; a local commit, file remote, GitHub mirror, or copied binary
   is not a substitute.
2. Independently reacquire a new private seed at that exact commit. Pair it
   with the already-verified private R9-M6 bundle outside the absent target and
   every legacy inventory source. Reverify all digests, socket membership, and
   capacity; never substitute unsafe HOME inputs or secret-bearing output.
3. Through an outer clean launcher (`env -i`, fixed system PATH, and
   `/bin/bash --noprofile --norc`), run the exact R9-M2 `plan`, inspect its
   canonical manifest, invoke `provision` with its exact confirmation token,
   and run the fixed-path independent `verify`. Preserve the birth receipt;
   do not manually assemble or repair the root in place.
4. Invoke the exact trusted wrapper installer through that same clean outer
   launcher. This forms and locks publisher custody but does not install a
   caller binary or import HOME credentials.
5. Invoke the publisher through that same clean outer launcher. It builds and
   installs the exact published master, assets, private runtime leaves, and
   pending admission receipt without restarting Linux services.
6. Explicitly quiesce the complete writer set: the three long-running
   services; sync, memory-decay-unused, distill, digest, and conservative day2
   timer/oneshot pairs; and every external MCP/hook/manual process holding a
   relevant legacy or destination SQLite descriptor. The migration tool does
   not stop or kill them.
7. Run R9-M1 `preflight`, then invoke its exact candidate-bound `migrate`
   confirmation and independent `verify`. Migrate SQLite through checkpoint,
   backup API, and integrity validation; apply the exhaustive sidecar plan;
   retain the bounded legacy rollback source; and require the complete private
   migration receipt. Do not raw-copy DB/WAL/SHM, journals, or locks.
8. Archive the old drop-ins and obsolete unit material, then invoke the exact
   current-boot binder through that same clean outer launcher only after the
   real manager `UnitPath` is safe. It must consume the exact publisher
   candidate, verify the migration receipt and typed quiescence before any
   mutation, revalidate quiescence before fragment activation/reload, rerun
   receipt verification plus quiescence after reload, and make no service
   restart. Exact-existing no-mutation replay is limited to this still-quiesced
   pre-adoption freeze window.
9. Start the three services in the explicit dependency order and prove each
   adopted the exact non-deleted installed inode, pinned runtime state, and
   health endpoint. A mixed generation stops the release.
10. Run the isolated restart harness against the pinned installed binary and
   require one workload execution, exact Duplicate reconciliation, unchanged
   committed rows, and zero receipt/scope residue.
11. Run the independent installed verifier against
    `$ROOT/runtime-state/workload-receipts`; every aggregate and per-service
    check must pass in one bounded observation.
12. Perform a fresh independent MCP stdio probe and consume the publisher's
    pending fresh-MCP admission. Retain the exact probe/pending binding.

Any authority mismatch, unsafe path, unexpected machine key, unit dependency
or hook, state migration ambiguity, unstable executable identity, Doctor
failure/warning, health mismatch, harness residue, or insufficient rollback
capacity stops admission. It must not be reported as a partial PASS.

## Evidence ledger

| Evidence | State through 2026-08-29 | Admission meaning |
|---|---|---|
| Trusted-root implementation | `SOURCE_READY` at `a4f4f4e153a5a824f28e6f1486c670af38c15ea5` | Local code and adversarial fixtures are green; not publication authority. |
| Earlier isolated restart exercise | `PASS` at source candidate `9bc924a2...` | Durable receipt reconciliation behavior only; must repeat after authoritative install. |
| R9-M1 migration implementation | `SOURCE_READY` at `eda927d1837b50c6680ce3ea337456a79e52a965` | Local implementation, adversarial fixtures, and independent review are green; no publication or production-migration claim. |
| R9-M2 provisioning implementation | original source published; R9-M6 hardening `SOURCE_READY` at `4643c4cad3789380f15cba9e960727c23dbd90b8` | Zero-write plan, exact-confirm provision, fixed-path verification, exact agent compatibility, and atomic no-replace activation are green; no live root was created. |
| R9-M3 publication/seed implementation | `SOURCE_READY` at `2107da2f0560f98c2820700f11c64093afd37783`; CI skipped | Fast-forward publication and independent seed fixtures are green; current-boot gcr agent authentication is verified. |
| R9-M4 credential ceremony | `SOURCE_READY` at `573ae19b6f530d0cfb52be9b88acb8292a5390e4`; CI skipped | Optional persistent-key route; no new key was generated or enrolled. |
| R9-M5 existing-agent seed extension | `PASS` at reporting/seed candidate `08f0bbeecf8f991f1dd37693b45aeedd310f20da`; CI skipped | Exact current-boot agent identity published and independently acquired one private seed. |
| R9-M6 trusted inputs and root agent compatibility | `SOURCE_READY` at `4643c4cad3789380f15cba9e960727c23dbd90b8`; inputs prepared; CI skipped | Private toolchain/model/config/public-auth inputs are verified; final publication, fresh seed, and read-only R9-M2 plan remain pending. |
| Authoritative GitLab publication | `PASS` at reporting candidate `b2d06bc385c1aa25110c7a8f579fb4da8ced1847`; CI skipped | GitLab master was independently reread after a non-force fast-forward push. This proves source publication only. |
| Private root provisioning | `NOT_DONE` | The birth organ and private inputs are ready, but the final candidate-matching seed and plan are pending; the live root is absent. |
| Production state migration | `NOT_DONE` | Unsafe SQLite/WAL and split body-state organs remain unmigrated; no live migration receipt exists. |
| Real systemd current-boot adoption | `NOT_DONE` | Current HOME `UnitPath` and drop-ins fail closed; fake-manager tests are not live proof. |
| Independent current-installed verifier | `FAIL_CLOSED` | Unsafe owner boundary, absent receipt root, and three deleted executables block admission. |
| R9 deployed/live-admitted | `NO` | No deployed/PASS claim is permitted. |

Until R9-M2 provisioning, complete-writer quiescence, R9-M1 migration
and receipt verification, current-boot binding, explicit adoption, isolated
exercise, installed verification, and fresh-MCP admission are all bound to one
authoritative candidate and green, the truthful status is: R9-M1–M5 source is
published and seeded through `08f0bbee`; R9-M6 source and private inputs are
ready but not yet finally published, reacquired, planned, or provisioned;
production remains on hold; the current installation remains failed closed.
