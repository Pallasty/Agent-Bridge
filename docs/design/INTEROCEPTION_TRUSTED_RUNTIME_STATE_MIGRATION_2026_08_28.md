# AB interoception: trusted runtime-state migration

Date: 2026-08-28

Status: **R9-M1 source at `eda927d1837b50c6680ce3ea337456a79e52a965`
is authoritatively published as an ancestor of integrated GitLab candidate
`b09eff1fab865526c862859f17bfb381c9bae1f0`, but not deployed or live-executed;
production remains `HOLD`**.

Scope: one operator-authorized migration from the legacy HOME-bound AB body
state into `$AGENT_BRIDGE_DEPLOY_ROOT/runtime-state`

Depends on:

- `INTEROCEPTION_DURABLE_WORKLOAD_RECEIPTS_2026_08_27.md`; and
- `2026-08-28-r9-installed-acceptance-gate.md`.

## Decision

R9-M1 is the migration organ inside R9, not a new R10 capability. Its value is
to prevent a split brain in which an old HOME database and a new trusted-root
database both appear valid and accept different writes. Publishing a binary
and binding hardened services are insufficient if an old daemon, maintenance
timer, MCP process, or hook can still reopen the legacy store.

The admitted handoff is therefore:

```text
published candidate + provisioned private root + publisher pending admission
  -> operator explicitly quiesces the complete writer set
  -> migration preflight and immutable plan
  -> separately confirmed migration execution
  -> SQLite checkpoint/backup/integrity verification
  -> explicitly classified sidecar transfer
  -> migration result receipt
  -> independent receipt verification
  -> binder revalidates receipt and quiescence before activation
  -> binder revalidates receipt and quiescence after daemon-reload
  -> explicit ordered service adoption
```

The migration tool does not stop, start, enable, disable, reload, or kill
anything. Those are operator actions outside its authority. Its default mode is
`preflight`. A state-changing execution requires the explicit `migrate`
command and its separate candidate/pending-bound confirmation value; omission
or mismatch fails closed. The confirmation is the exact
`MIGRATE:<40-hex-candidate>:<pending-admission-sha256>` value constructed from
the same preflight evidence; it is not a reusable yes/no flag.

## Complete writer-set boundary

The three long-running services are only part of the writer set. Before
execution, the gate must inspect all of the following by their real systemd
unit type rather than force timer and service properties into one shape:

- `agent-bridge-daemon.service`;
- `agent-bridge-daemon-http.service`;
- `agent-bridge-palace.service`;
- `agent-bridge-sync.timer` and `agent-bridge-sync.service`;
- `agent-bridge-memory-decay-unused.timer` and
  `agent-bridge-memory-decay-unused.service`;
- `agent-bridge-distill.timer` and `agent-bridge-distill.service`;
- `agent-bridge-digest.timer` and `agent-bridge-digest.service`; and
- `agent-bridge-day2-audit.timer` and
  `agent-bridge-day2-audit.service` as a conservative gate, even if the
  current audit path is expected to be read-only.

A loaded service or oneshot must be `inactive`/`dead` with `MainPID=0`. A timer
does not have a service-style `MainPID` proof. A timer is admitted only in one
of three exact shapes: loaded plus disabled, masked plus masked, or not-found
plus an empty `UnitFileState`. This models real systemd output and prevents a
stopped but armed timer, or contradictory load/unit-file metadata, from
starting a writer during migration. Unknown or partially loaded states block.
The receipt records the typed unit baseline, not merely a list of zero PIDs.

That unit list is necessary but not sufficient. An external MCP server,
interactive CLI, editor or shell hook, manually launched maintenance job, or
other same-UID process can hold a legacy or destination database, WAL, SHM,
rollback-journal, or super-journal descriptor without belonging to a
registered unit. Preflight and the
confirmed migration must inspect that process/file-descriptor boundary and
reject any such live holder. The tool reports it; it never kills it.

Linux Yama may make a same-UID descriptor table unreadable. That is not treated
as an empty table. The only exception is the exact user-manager infrastructure
pair: `systemd --user` in its own `user@UID.service/init.scope`, plus its exact
same-scope `(sd-pam)` child. Every other unreadable same-UID process fails
closed. On this node that conservative rule also blocks session helpers such as
the SSH agent and Waydroid until the operator quiesces them, or a future
privileged inspection helper supplies stronger evidence. The receipt names
this exact exception; it never claims an all-process proof.

A process that has no relevant descriptor at inspection time but can later
reopen the old path cannot be permanently fenced by a user-space migration
script. The operator must terminate those launch paths and keep them quiesced.
The systemd binder independently rechecks every registered unit immediately
before fragment activation and after `daemon-reload`; any rearmed writer stops
adoption. It also reruns receipt verification after reload, so a short-lived
oneshot that opens, changes, and closes the legacy DB between inactive-state
samples is detected through source DB/manifest drift. This is a bounded
handoff proof, not a same-UID adversary lock.

## Authority and preflight

Every invocation is rooted in one explicit physical, euid-owned, exact-`0700`
deployment root. It shares the publisher's physical mode-`0600` kernel mutex
with wrapper installation, publication, and systemd binding. HOME is never a
fallback for the target.

Every legacy inventory source must remain physically outside that deployment
root. A directory already containing legacy body state cannot be relabeled as
the new root and then migrated into itself. In particular, the current
`/Data/.agent-bridge-state` source cannot also serve as
`AGENT_BRIDGE_DEPLOY_ROOT`; production needs a separately provisioned private
trusted root. This source increment neither creates that root nor moves the
legacy source.

Preflight is read-only and produces a deterministic candidate plan. It must
bind and validate at least:

- the physical deployment-root device/inode and private parent chain;
- the authoritative source candidate and exact migration-tool bytes;
- the publisher pending-admission candidate, binary digest/inode, and asset
  binding;
- the explicit legacy source database and state root;
- the exact target database and runtime-state root;
- available capacity for the target, private staging, and bounded rollback
  source;
- the complete unit-state baseline and external file-descriptor scan;
- the SQLite database-family identity and either immutable integrity or an
  explicit WAL-integrity deferral to confirmed execution; and
- an exhaustive manifest and action for every admitted sidecar path.

The reviewed private plan is the exact mode-`0600`
`$ROOT/config/agent-bridge/state-migration.json`. The SQLite target is fixed at
`$ROOT/runtime-state/data/agent-bridge/state.db`; neither a plan nor ambient
environment can redirect it outside the trusted runtime-state skeleton.

Opening a WAL database with SQLite's nominal `mode=ro` can create or modify its
shared-memory index. Therefore preflight never opens a WAL-bearing source with
SQLite: it validates bounded physical family facts and reports that logical
integrity is deferred. Only the separately confirmed migration may open that
source read/write to checkpoint it; source and target integrity must then pass
before activation. A WAL-free source is checked immutably during preflight.

Preflight does not claim quiescence will remain true. Execution repeats all
mutable checks while holding the shared publisher mutex and refuses a changed
candidate, pending record, root identity, plan, manifest, database identity,
unit baseline, or path boundary.

## SQLite transfer contract

The database is a logical SQLite migration, not a filesystem copy:

1. prove the complete writer set quiescent;
2. inspect and checkpoint the source using SQLite's own API;
3. run a source integrity check;
4. create the target through SQLite's backup API in a private staging
   location;
5. run a target integrity check and compare the frozen database evidence;
6. sync the staged file and private parent chain; and
7. install it only into the exact empty target selected by the plan.

The source DB, `-wal`, `-shm`, rollback journal, super-journal, and lock
artifacts are never raw-copied as a unit. A WAL or SHM file is evidence that
SQLite must reconcile under the quiesced connection; it is not a transferable
body organ. The receipt binds the required post-checkpoint absence of every
source journal/WAL/SHM family member. `verify` rejects any member reappearing,
including one recreated by a late legacy writer. A lock is
runtime coordination state and must be retired or reconstructed, never
retained as live ownership proof.

The controlled SQLite checkpoint is the only admitted source mutation. No
legacy sidecar is deleted, and the post-checkpoint source database remains the
bounded rollback source with its exact identity and digest in the receipt.
Once trusted services adopt the target, rollback is an explicit release-owner
decision; the migration receipt alone does not make it safe to run both
generations.

## Sidecar manifest and collision policy

Every non-database entry in the legacy state root must have exactly one
reviewed disposition in the migration plan:

- **retain** — immutable or durable body state whose bytes are transferred,
  normalized to the trusted private modes, and then verified;
- **retire** — obsolete, cache-like, or superseded state intentionally absent
  from the trusted runtime root; retirement means exclusion from the target,
  not deletion of the legacy rollback source; or
- **reconstruct** — runtime coordination or derived state recreated empty or
  from an admitted deterministic rule at the target.

Non-body infrastructure can be declared only through a separate explicit
`ignore-infrastructure` decision; it is not a fourth sidecar migration action
and cannot conceal retained body state.

The mapping must cover the currently retained app-control, Resident, Avatar,
continuity, and other body-state leaves. A broad recursive copy is not an
inventory.

An unknown entry or an entry without exactly one disposition blocks the
migration. Symlinks in the source, target, staging, or parent chain; hard-linked
regular files; sockets, devices, FIFOs, or other special files; target
collisions; duplicate destinations; and type-changing mappings all block.
SQLite WAL/SHM files and lock artifacts cannot be smuggled through a generic
`retain` rule. Existing target content cannot be merged or overwritten merely
because its name matches.

The reviewed plan freezes disposition, validation, bounds, and exact
destination or reconstruction rule. The preflight-derived source manifest adds
relative path, source type, size, and content digest where applicable.
Execution rescans the complete tree and rejects any addition, removal,
replacement, metadata change, or plan/manifest mismatch.

## Result receipt

Only a completely installed and independently revalidated target can produce
the private mode-`0600` current receipt at
`$ROOT/publisher-state/migrations/current.json`. A failed or partial run cannot
leave a receipt that the binder will accept.

The receipt binds:

- the published candidate commit and publisher pending-admission identity;
- the physical deployment-root identity;
- the exact migration plan and exhaustive source manifest digests;
- the source and target database identities, exact post-checkpoint source
  WAL/SHM absence, backup evidence, and integrity results;
- retained, retired, and reconstructed sidecar outcomes;
- the complete pre-execution unit baseline and external descriptor proof; and
- the final target manifest and receipt digest.

`verify` is read-only. It recomputes the authority, plan/result, root, target
manifest, database, and unit-baseline bindings under the shared publisher lock
and emits only a bounded verified result. A syntactically valid JSON file is
not sufficient.

## Binder handoff

The current-boot binder must consume the exact migration tool from the
publisher candidate. Its mutating path then observes this order:

1. run the receipt verifier and typed writer-unit gate before the first
   manager or runtime-fragment mutation;
2. rerun both receipt verification and the writer-unit gate immediately before
   the first fragment activation and before `daemon-reload`; and
3. after `daemon-reload`, rerun both receipt verification and typed
   quiescence before the new effective units can be accepted.

The third and final receipt verification closes the short-lived-writer window
that a post-reload inactive/dead sample alone cannot prove. During the same
migration freeze window, if the exact trusted units already exist, every effective
binding is exact, and no adopted service has written the target, the binder may
take a separate exact-existing no-mutation replay path: it still verifies the
receipt and quiescence but performs neither fragment replacement nor
`daemon-reload`.

That replay is not a steady-state idempotency claim. After ordered adoption, a
healthy service is expected to change the target DB/manifest, so the frozen
migration receipt will drift and a later binder replay must fail closed.
Steady-state acceptance uses the installed verifier and fresh health/MCP
evidence; it does not weaken or regenerate the migration receipt around a live
body.

Any missing, replaced, or stale receipt; changed root/candidate/pending/plan/
manifest/database binding; malformed unit state; armed timer; active service;
nonzero service writer PID; or post-reload rearm fails closed. The binder still
does not start or restart a service.

## Failure and recovery semantics

- Preflight is safe to repeat and does not grant migration authority.
- `migrate` refuses a missing or stale explicit confirmation.
- No ambiguity is downgraded to a warning: unknown paths, capacity uncertainty,
  source mutation, external holders, database errors, collisions, and receipt
  mismatch are terminal.
- Private staging may be cleaned only when its ownership and exact attempt
  identity are proven; the legacy source is not cleanup material.
- An ordinary caught failure rolls the exchange back before returning. A
  process or power loss inside the exchange/receipt window is fail-closed, not
  automatically recovered: absence of the receipt prevents binding, and the
  deterministic stage/rollback paths require release-owner forensic recovery.
  R9-M1 does not claim an unattended crash-recovery state machine.
- A target installed without a valid current receipt is unadmitted and must
  not be bound or started.
- A valid receipt does not itself stop writers, mutate systemd, adopt a binary,
  or authorize a fresh MCP session.
- Source DB-family sidecar drift, including WAL/SHM reappearance, invalidates
  verification rather than being treated as routine SQLite noise.
- Exact-existing migration/binder replay is permitted only before service
  adoption while the migration freeze remains intact; it is not a day-two
  control path.

## Source-candidate acceptance

R9-M1 acceptance requires adversarial coverage for default-preflight behavior,
confirmation gating, complete unit and external-descriptor quiescence,
checkpoint/backup/integrity handling, all sidecar dispositions, unknown and
unsafe inode types, collisions, manifest/plan races, partial failure, receipt
tampering, and binder pre/post-reload rearm.

Final implementation identity:
`eda927d1837b50c6680ce3ea337456a79e52a965`. The migration harness passed
`15/15`; the installed-verifier/restart Python suites passed `62/62`; and the
trusted wrapper, publisher, post-build race, pinned-assets, runtime/audio
parity, and migration-aware systemd binder suites all passed. Shell syntax,
Python AST, and diff whitespace checks are green. An independent adversarial
review approved the stable tree with no reproducible blocker, major, or minor
defect, while retaining the crash-window manual-recovery and Yama inspection
limits stated here. Source fixtures cannot be relabeled as publication,
production migration, systemd adoption, or live admission.

## Current production truth

Production remains `HOLD`. A current-boot gcr agent identity authenticates the
operator publication step; an independent private deployment root, trusted
toolchain, minimal machine configuration, and credentials are not provisioned;
the existing `/Data/.agent-bridge-state` body-state source cannot double as the
new root; the active unit path remains on the unsafe HOME boundary; and all
three long-running services still execute deleted old binary inodes. No
production database, state leaf, service, unit, timer, credential, root, or
receipt was mutated in this increment.

The frozen release order is:

```text
publish authoritative candidate
  -> provision private root, source authority, toolchain, config, credentials
  -> run publisher
  -> explicitly quiesce the complete writer set
  -> run R9-M1 migration and independent receipt verification
  -> archive old drop-ins/unit material and run current-boot binder
  -> explicitly adopt services in dependency order
  -> run isolated restart harness and installed verifier
  -> perform fresh independent MCP admission
```
