# AB interoception: durable workload receipts

Status: R9 durable-v1 source candidate with installed-acceptance gates; not deployed
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
