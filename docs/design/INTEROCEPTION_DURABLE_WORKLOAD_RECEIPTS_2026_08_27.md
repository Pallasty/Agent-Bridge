# AB interoception: durable workload receipts

Status: R9 durable-v1 plus trusted deployment-root framework source-ready;
not published or deployed
Scope: body-bound local Agent workloads on Linux cgroup v2
Depends on: `INTEROCEPTION_CGROUP_WORKLOAD_CUSTODY_2026_08_27.md`

## Decision

The delegated cgroup supervisor's terminal receipt is an outbox item, not a
process-local cache. The admitted ordering is:

```text
START-bound durable manifest
  -> workload execution
  -> populated=0 + terminal counters
  -> durable receipt publish
  -> supervisor exit
  -> SQLite receipt-ledger + semantic-event transaction
  -> idempotent filesystem ACK/collection
```

The guarantee is **exactly-once durable commit plus a replay-safe ACK effect**.
SQLite and the filesystem do not share a transaction, so the design does not
claim exactly-once ACK delivery. A crash after database commit and before
collection leaves the receipt available; the next importer observes a ledger
duplicate and repeats the ACK safely.

The supervisor does not wait online for ACK. The runtime sole reaper currently
uses supervisor exit to terminalize the session; an online ACK wait would
deadlock that path. Persistence, not a live socket, bridges daemon restarts.

## Truth boundary

A recovered terminal receipt can prove only its own bounded workload-accounting
claim. It cannot recover the process-local host-body before/checkpoint/after
samples. Restart reconciliation therefore emits a standalone
`workload_receipt_reconciled` observation and explicitly records:

- `recovery_scope = standalone_workload_accounting`;
- `body_before_after_recovered = false`; and
- `task_span_closed_reconstructed = false`.

It never infers Complete from a missing scope, an absent process, a dead unit,
or an old manifest without a terminal receipt. Those states remain
`receipt_commit_unknown` or invalid.

## Binding

Bridge creates the opaque body `span_id` before calling the runtime. For a
trusted local-workload runtime it injects that ID through a reserved launch
control field which is consumed by the shared launcher and never forwarded to
the payload environment. Public `agent_spawn.env` is forbidden from supplying
the reserved field.

Before START, the launcher creates and syncs one private manifest containing a
fresh receipt ID, span binding, runtime ID, unit, and nonce. On restart the
scanner validates the receipt against that independently written manifest; it
does not accept the receipt's self-declared identity alone.

The first deployable layout is manifest schema 2, which requires the
`producer.lock` lease object. The earlier schema-1 source draft was never
deployed and is rejected rather than silently imported without ownership
proof.

Session IDs remain runtime-minted in this increment. Consequently restart
reconciliation binds a receipt to its pre-exec observation span, not to a
fabricated recovered session/body-span closure. Persisting the complete active
span and session binding is a later organ, not an implicit claim here.

## Filesystem protocol

Body-bound launches use a persistent private spool. Resolution is deterministic
and fail-closed, in this order: `AGENT_BRIDGE_CGROUP_RECEIPT_DIR`, the parent of
an explicit `AGENT_BRIDGE_DB`, `AGENT_BRIDGE_STATE_DIR/workload-receipts`,
`XDG_DATA_HOME/agent-bridge/workload-receipts`, then the HOME data fallback.
An explicitly empty value is an error. The common state-directory step is
important on hosts whose HOME mount cannot represent private POSIX ownership or
modes. Non-body launches keep the existing process-local receipt behavior.

Required properties:

- absolute, normalized, non-root, owner-bound root and entry directories with
  exact mode `0700`;
- physical path components only: every existing component is inspected without
  following symlinks, and replaceable foreign-owned or group/other-writable
  ancestors are rejected. A root-owned sticky `/tmp` is accepted only as the
  ancestor of an already-created owner-bound child, never as the direct parent
  for recursive runtime initialization;
- every owner-owned ancestor needed to reach a missing suffix has owner
  read/write/execute access; new directories are created one component at a
  time as `0700`, their parents are synced, and the trailing owner-owned suffix
  is reverse-synced and revalidated, including after an interrupted retry;
- bounded lowercase-hex receipt directory names;
- root-directory serialization and capacity admission before allocating a new
  entry, so concurrent preparers cannot grow beyond the scan bound;
- create-new `0600` manifest, producer-lease, and receipt files;
- one close-on-exec exclusive producer lease retained by the Bridge from
  manifest allocation through live Store commit/ACK; restart scanners import
  only entries whose lease is no longer owned;
- file sync, atomic publication, then containing-directory sync;
- regular-file, owner, mode, no-follow, size, schema, manifest-binding,
  terminal-resource-invariant, and digest checks on every import;
- bounded scan count and bounded field lengths; and
- no recursive cleanup of an unresolved or caller-selected path.

ACK atomically renames the validated receipt directory to an `.acked-*`
tombstone and syncs the spool root. Only after that durable transition does it
remove the known files and empty directory. A crash in cleanup can therefore
only leave an acknowledged tombstone, never turn an uncommitted receipt into a
missing ambiguous directory. Tombstone cleanup is authorized by the completed
rename itself and remains restartable even if an earlier cleaner already
removed `producer.lock`.

## SQLite protocol

`workload_receipt_commits` is a node-local immutable ledger independent of the
bounded `semantic_events` ring. Receipt ID is the primary key. The stored row
contains only:

- schema, receipt ID, opaque span ID, and commit time;
- receipt SHA-256;
- live-body or startup-reconciliation provenance;
- canonical PID-free redacted facts and their record hash.

Nonce, unit, PID, pidfd, cgroup path, socket path, spool path, command,
environment, prompt, and transcript are forbidden.

`BEGIN IMMEDIATE` validates the complete batch, admits new ledger rows, inserts
one semantic event, enforces the event ring cap, and commits. An identical
receipt ID/digest/span is a duplicate success. The same ID with a different
digest or span is a conflict; the transaction writes nothing and the outbox is
not acknowledged. All-duplicate replay inserts no second event. The default
non-SQLite Store implementation returns unsupported rather than a false
successful no-op.

For every batch that would add at least one ledger row, Store is also the
projection-binding boundary: every record must carry the same span and the
same canonical redacted facts; the event target and canonical event facts must
match them; and event facts/evidence/descriptor pass the same privacy ceiling.
A duplicate receipt identity does not by itself prove that a different live
event projection was recorded.

## Restart state machine

```text
ALLOCATED
  capacity admitted under the root lock; manifest and producer lease
  create-new + file/entry/root sync before START

START_AUTHORIZED
  parent has successfully written START; only now can the entry outlive the
  prepared-launch handle. Drop before this point removes the known files and
  empty entry because zero workload execs is protocol-proven

SEALED
  populated=0 observed; counters validated; receipt atomically published
  and directory-synced; supervisor may exit

COMMITTED
  immutable receipt ledger and semantic projection committed in one SQLite
  transaction; this is the only ACK authorization boundary

ACKED
  validated entry atomically renamed to an acknowledged tombstone and root
  synced; known files are then collected idempotently

UNKNOWN / INVALID
  missing terminal file, malformed data, binding mismatch, collision,
  ownership/mode/symlink/size violation, or Store conflict; never ACKed and
  never upgraded from scope absence
```

Startup reconciliation runs after SQLite migration/open and before runtimes or
MCP/HTTP serving surfaces are constructed. A scanner that finds an actively
leased entry reports `producer_active` and does not delay startup or import it.
An ownerless manifest without a terminal receipt receives only the bounded
supervisor sealing grace and remains `receipt_commit_unknown` afterwards.
Released producers may race to import; the receipt primary key and immediate
transaction serialize the commit, while ACK is intentionally idempotent.

All externally derived executable and launch-policy preflight happens before
durable allocation. Remaining state-local fallible setup, including generated
path encoding and socket preparation, is covered by a prepared-launch guard
that tracks whether START was actually authorized. Dropping it before START
performs bounded, known-file cleanup. No age, scope absence, or process lookup
is used to infer that an entry is safe to erase.

## Security and privacy ceiling

This increment retains the cgroup layer's same-UID, non-adversarial membership
boundary. A deliberately hostile unsandboxed same-UID payload is outside the
containment claim. Durable manifest binding prevents accidental/restart
misattribution; it is not a new hostile same-UID authentication boundary.

The public body receipt exposes only opaque receipt IDs and digests alongside
PID-free aggregates. Private unit, nonce, process, cgroup, socket, and path
material stays in the outbox and is removed after durable acknowledgement.

## Required admission

1. receipt publish followed by Store failure preserves the entry;
2. database commit followed by crash-before-cleanup replays as Duplicate and
   produces no second semantic event;
3. restart imports a manifest-bound terminal receipt and then empties its spool;
4. a manifest without terminal receipt remains `receipt_commit_unknown` even
   when its scope no longer exists;
5. malformed, oversized, symlinked, wrong-owner/mode, wrong-binding, and
   digest-collision inputs receive no ACK;
6. concurrent importers produce one ledger row and one semantic event;
7. multiple generation receipts commit atomically with one body-span event;
8. Store/event/public JSON contains no private custody fields;
9. normal exit, signal mirroring, cancellation escalation, PTY, ACP, retry,
   and scope cleanup regressions remain green; and
10. pre-START failure/drop leaves no manifest, allocation remains within the
    scan bound, a live producer cannot be stolen by another Bridge, and the
    reserved launch binding is absent even when inherited ambiently;
11. Store rejects cross-span, cross-projection, event-target/facts, descriptor,
    evidence, and sensitive-field mismatches without a ledger or event write;
    and
12. one installed-binary restart exercise proves commit-before-any-successful-
    ACK at the observable protocol boundary, exact replay, no false body-span
    reconstruction, and no residual spool/scope.

## Installed acceptance boundary

Source tests do not upgrade an installation. R9 publication adds three separate
gates:

- the deployer requires the immutable-ledger schema marker in every selected
  binary, including first installs and explicit binary selection;
- `agent-bridge doctor` resolves the same receipt-root precedence without
  creating anything. An absent root below a safe private parent is a pre-start
  warning; an unsafe path, owner, mode, or ancestor is a failure; and
- a read-only installed verifier binds an explicit expected commit and binary
  digest, checks the physical binary and receipt-root replacement boundaries,
  requires daemon, daemon-http, and Palace to execute that exact non-deleted
  path and content, checks both loopback health endpoints, and requires a strict
  zero-warning Doctor result bound to the verified receipt root.

The destructive-looking restart proof never operates on the production spool.
It copies the pinned installed binary byte-for-byte into a private disposable
runtime directory, uses an isolated database and spool, then changes only that
spool to mode `0500`. The workload supervisor can still seal inside its existing
entry, while live ACK cleanup fails the exact-root-mode precondition after the
SQLite transaction. The harness verifies the immutable live row/event, kills
only its first MCP process group, restores the isolated root, starts the same
copy, and requires Duplicate reconciliation, byte-for-byte unchanged database
rows, one workload execution, no reconstructed recovery event, no pending or
acknowledged receipt entries other than the persistent `.spool.lock`, and no
remaining exact transient scope.

These gates still do not authorize publication, service restart, or a new
installation location. The authoritative remote and the host path used for the
installed wrapper/binary remain separate authority and replacement-trust
decisions.

## 2026-08-28 source-candidate acceptance evidence

The clean source candidate is
`9bc924a2c1641983ac954ee9416e18ddb5fcdf77`. The exact locally built exercise
binary has SHA-256
`f0b5fbdfe295d91f7c21f529aff0e9414bd4ebbe8948b1c4a258bdcb111dce4c`.
The dedicated Python suites passed 62/62 cases, and the Rust, deploy-marker,
format, syntax, and diff checks were green.

An explicitly authorized isolated exercise against that exact binary returned
`PASS`: one stand-in execution reached committed SQLite state before any ACK
could succeed; one receipt survived the MCP1 interruption; MCP2 reported one
Duplicate; the one ledger row and two semantic events were unchanged; no
recovery event was emitted; and the receipt, private trial root, and exact
transient scope were absent at closure. The harness uses a socket-budgeted
private root and requires a primed read-only Linux body sample followed by an
exact `Verified` body event; `Unknown` cannot satisfy the gate.

The independent verifier returned `FAIL_CLOSED` against the pre-existing
installation. Service activity, health, and root bindings passed, while the
installed binary owner boundary, absent production receipt root, and deleted
executables for all three services blocked admission. No production service,
installed file, or production spool was changed. This evidence verifies the
source candidate and the fail-closed gate only: R9 remains undeployed, and the
exercise plus verifier must be repeated after authenticated publication,
authorized install, and explicit service adoption.

## 2026-08-28 trusted deployment-root closure

Implementation `a4f4f4e153a5a824f28e6f1486c670af38c15ea5` makes the
receipt-root contract deployable without treating the replaceable HOME mount
as part of the body. It remains a local source identity; an authoritative
published descendant is still required.

The closure has four linked organs:

1. **Publisher custody.** One explicit physical exact-`0700` deployment root
   owns a fixed GitLab safe clone, private Git configuration, toolchain, binary,
   wrapper, assets, configuration, publisher metadata, and runtime state.
   Production `--use-binary` is closed. A private `git archive` snapshot and
   before/after candidate hashes bind each build to one fetched master commit.
2. **Executable wrapper.** The wrapper derives identity from its physical
   installed sibling tree, does not fall back to HOME credentials or CLI paths
   on an alternate root, clears injection variables, and restores all
   parent-supplied root/state/receipt/asset/HOME/XDG/tmp pins after the bounded
   machine configuration is loaded.
3. **Writable workload tissue.** Durable receipts live below
   `$ROOT/runtime-state/workload-receipts`; non-durable supervisor allocations
   live below `$ROOT/runtime-state/workload-tmp` through the reserved
   `AGENT_BRIDGE_CGROUP_TRANSIENT_DIR` policy. The latter avoids trying to
   allocate under a read-only user bus directory. Child spawn input may
   override neither custody root.
4. **Current-boot service adoption.** Three complete user-systemd units are
   staged and activated as one transaction below the manager runtime control
   directory. The binder validates the real `UnitPath`, foreign drop-ins and
   its enumerated activation/reverse-relation allowlist, the preserved
   pre-existing `WantedBy` set, publisher pending identity, safe-clone
   candidate, asset bytes, and machine configuration before writing. After a
   successful single daemon reload it verifies effective fragment bytes,
   execution hooks, the same relation set, clean environment, and mount
   hardening. It never restarts or enables a service.

`$ROOT/publisher-state` and `$ROOT/runtime-state` are deliberately separate.
Wrapper installation, binary publication, and service binding share the same
physical mode-`0600` kernel mutex, so no one of those writers can validate one
asset generation and activate another.

The service machine file is data only at admission time: each non-comment line
must be `export KEY=literal`, keys come from a small allowlist, values cannot
contain quoting/expansion/commands, secrets and writable-state pins are
forbidden, and model/voice paths must remain physical beneath the private root.
This does not mean every legacy machine setting was silently retained. The
unsafe HOME configuration must be inventoried by key and each non-secret value
explicitly retained, replaced by a default, or retired. Secrets are provisioned
through the separate private credentials path.

The frozen production sequence is publication, private-root provisioning,
clean-environment safe-clone advancement and mode normalization, trusted
wrapper installation, publisher build/install, quiesced state migration,
current-boot binding, ordered service adoption, isolated restart exercise,
installed verifier, then fresh-MCP admission. Every clone operation and every
production script entry (wrapper installer, publisher, and binder) must use an
outer `env -i` with fixed system PATH and `/bin/bash --noprofile --norc`; an
inner script cannot remove interpreter-start injection that already happened.
State migration is a first-class gate: SQLite must use backup/checkpoint/
integrity validation rather than a raw DB/WAL/SHM copy, and existing
app-control/resident/Avatar leaves must be mapped into the one writable
runtime-state subtree.

Source proof now includes the Python 62-case gate, `ab-agent` 157-test suite,
four wrapper environment tests, trusted wrapper installer suite, publisher
lease/recovery suite, three deploy race/parity suites, and the adversarial
systemd transaction suite. It does not include a real hardened systemd service
smoke. External `Before`/`After` ordering edges are not part of the enumerated
relation gate. On transaction failure, activated fragments are deleted and a
compensating reload is attempted, but a failed compensation leaves manager
state unknown and prohibits service start until explicit recovery verification.
The current HOME `UnitPath`, two foreign model drop-ins, absent trusted-root
layout, unpublished GitLab commit, unsafe legacy machine configuration,
unmigrated SQLite/WAL, and limited `/Data` capacity therefore remain stop
conditions. See
`docs/reports/goal-c-u/2026-08-28-r9-installed-acceptance-gate.md` for the
authoritative ordered ledger and current live truth.
