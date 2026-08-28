# R9 installed acceptance gate

Date: 2026-08-28

Status: trusted deployment-root framework source-ready locally; not published,
provisioned, installed, restarted, or live-admitted; current installation
remains `FAIL_CLOSED`

## Decision boundary

Implementation commit
`a4f4f4e153a5a824f28e6f1486c670af38c15ea5` closes the source-side gap between
the R9 durable workload-receipt organ and a permission-capable installed body.
It is a local implementation identity, not publication authority. The clean
descendant that contains this report must still be published to the
authoritative GitLab `master` before any production use.

The earlier isolated restart exercise remains valid evidence for source
candidate `9bc924a2c1641983ac954ee9416e18ddb5fcdf77` and local binary SHA-256
`f0b5fbdfe295d91f7c21f529aff0e9414bd4ebbe8948b1c4a258bdcb111dce4c`.
It does not prove that the new deployment-root framework has been published or
that a production service has adopted it.

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

## Verification completed

All verification used debug/test artifacts and private fixtures; no release
test build or production path was used.

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
| Touched Rust formatting, changed shell syntax, staged whitespace | `PASS` |

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
- `/Data/.agent-bridge-state` is a physical euid-owned mode-`0700` candidate
  root, but it currently contains owner body state rather than the new
  source/config/toolchain/bin/publisher/runtime layout. Those required
  subtrees and publication credentials are not provisioned.
- The legacy machine file is on the unsafe HOME mount, contains a secret-like
  key, many settings outside the bounded service allowlist, legacy writable
  state paths, HOME resources, and development-tree assets. It must not be
  copied. Each required non-secret setting needs an explicit retain/default/
  retire decision; secrets must be provisioned separately.
- Existing SQLite plus WAL state remains on the unsafe mount. Migration must
  quiesce writers and use SQLite backup/checkpoint/integrity procedures; raw
  copying a database together with WAL/SHM files is prohibited. Existing
  app-control, resident, Avatar, and other body-state leaves also require an
  explicit mapping into `$ROOT/runtime-state` because the hardened units make
  the rest of `$ROOT` read-only.
- `/Data` has about 12 GiB free at 96% use. The root filesystem backing the
  intended `/var/tmp` production build cache has about 59 GiB free; production
  migration still needs an explicit capacity margin and rollback copy budget.
- Authenticated GitLab publication is unavailable from this session. The safe
  clone, deploy key, known-hosts file, trusted toolchain, minimal machine file,
  and credentials file are absent.
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

1. Publish one clean descendant containing implementation
   `a4f4f4e153a5a824f28e6f1486c670af38c15ea5` to authoritative GitLab
   `master` with an authenticated publisher identity. Record the exact 40-hex
   commit; a local commit, file remote, GitHub mirror, or copied binary is not a
   substitute.
2. Provision the private deployment root, fixed safe clone, exact GitLab deploy
   key and known-hosts file, trusted Cargo/rustc toolchain, build-cache base,
   minimal allowlisted machine file, and credentials independently. Never
   bootstrap them by copying the unsafe HOME files or secret-bearing output.
3. Through an outer clean launcher (`env -i`, fixed system PATH, and
   `/bin/bash --noprofile --norc`), fetch and advance the dedicated safe clone
   so both HEAD and `refs/remotes/gitlab/master` equal the published commit.
   Reapply its frozen private custody modes after checkout: source directories
   `0700`, deploy/systemd orchestrators `0700`, and wrapper installer/template/
   example `0600`.
4. Invoke the exact trusted wrapper installer through that same clean outer
   launcher. This forms and locks publisher custody but does not install a
   caller binary or import HOME credentials.
5. Invoke the publisher through that same clean outer launcher. It builds and
   installs the exact published master, assets, private runtime leaves, and
   pending admission receipt without restarting Linux services.
6. Explicitly quiesce the three old services and prove no state writer remains.
   Migrate SQLite through online backup/checkpoint/integrity validation and map
   each retained body-state organ into `$ROOT/runtime-state`; keep a bounded
   rollback source. Do not raw-copy DB/WAL/SHM.
7. Archive the old drop-ins and obsolete unit material, then invoke the exact
   current-boot binder through that same clean outer launcher only after the
   real manager `UnitPath` is safe. It must consume the exact publisher
   candidate and make no service restart.
8. Start the three services in the explicit dependency order and prove each
   adopted the exact non-deleted installed inode, pinned runtime state, and
   health endpoint. A mixed generation stops the release.
9. Run the isolated restart harness against the pinned installed binary and
   require one workload execution, exact Duplicate reconciliation, unchanged
   committed rows, and zero receipt/scope residue.
10. Run the independent installed verifier against
    `$ROOT/runtime-state/workload-receipts`; every aggregate and per-service
    check must pass in one bounded observation.
11. Perform a fresh independent MCP stdio probe and consume the publisher's
    pending fresh-MCP admission. Retain the exact probe/pending binding.

Any authority mismatch, unsafe path, unexpected machine key, unit dependency
or hook, state migration ambiguity, unstable executable identity, Doctor
failure/warning, health mismatch, harness residue, or insufficient rollback
capacity stops admission. It must not be reported as a partial PASS.

## Evidence ledger

| Evidence | State on 2026-08-28 | Admission meaning |
|---|---|---|
| Trusted-root implementation | `SOURCE_READY` at `a4f4f4e153a5a824f28e6f1486c670af38c15ea5` | Local code and adversarial fixtures are green; not publication authority. |
| Earlier isolated restart exercise | `PASS` at source candidate `9bc924a2...` | Durable receipt reconciliation behavior only; must repeat after authoritative install. |
| Authoritative GitLab publication | `BLOCKED` | Authenticated publisher identity/path is unavailable. |
| Private root provisioning | `NOT_DONE` | Candidate parent is safe; source/config/toolchain/bin/publisher/runtime layout is absent. |
| State migration | `NOT_DONE` | Unsafe SQLite/WAL and split body-state organs remain unmigrated. |
| Real systemd current-boot adoption | `NOT_DONE` | Current HOME `UnitPath` and drop-ins fail closed; fake-manager tests are not live proof. |
| Independent current-installed verifier | `FAIL_CLOSED` | Unsafe owner boundary, absent receipt root, and three deleted executables block admission. |
| R9 deployed/live-admitted | `NO` | No deployed/PASS claim is permitted. |

Until publication, provisioning, state migration, explicit adoption, isolated
exercise, installed verification, and fresh-MCP admission are all bound to one
authoritative candidate and green, the truthful status is: source-ready
trusted-root framework, current installation failed closed, R9 not deployed.
