# LAN memory synchronization on the installed engines

The owner approved a bounded Mac/Linux LAN-first memory-sync increment on
2026-09-08. It uses the installed binaries and their existing Store merge rules.
No R9/R10 binary deployment, database relocation, HTTP listener, discovery
service, outcome producer, or plan-table replication is involved.

## Topology and scheduling

Each node retains its existing SQLite database and memory Git checkout. The
Mac hosts an owner-private bare Git repository at
`/Users/pallasting/Agent-Bridge-LAN/memory.git`. Linux connects through its
already-working SSH identity to `pallasting@192.168.1.2`; the Mac uses the local
path. The bare repo denies non-fast-forward updates and branch deletion.

The existing Linux `agent-bridge-sync` units and Mac `com.agentbridge.sync`
LaunchAgent call `scripts/lan-memory-sync.py` with a node-specific private JSON
configuration. Mac's interval is 20 seconds; Linux waits 20 seconds after the
previous invocation, with one-second timer accuracy/jitter. Running jobs do not
overlap through the helper lock, and AB's original `memory-sync` lock serializes
the actual Store/Git operation with ordinary session-end hooks.

One Linux cloud bridge uses a separate Git checkout pointing to the original
GitHub remote, the **same** local SQLite and the **same** AB lock. Its hourly
round imports other cloud-node changes and exports the local merged state. The
next LAN round propagates imported changes. This is low-frequency bidirectional
compatibility/backup, not a second independent merge engine or a pure one-way
mirror. Cloud failure does not change LAN remote selection; receipts for each
channel remain separate. Neither cloud outage nor embedding availability is
on the LAN transport path.

Git is transport, not live SQLite replication. AB still performs
pull → import with VersionVectorMerge → stable export → commit/push.
Existing same-key conflict copies and tombstones are retained. Legacy records
without version vectors retain the pre-existing timestamp fallback; this
increment does not claim strong consistency for concurrent legacy writes.

## Small wrapper corrections and honest status

The installed sync has two relevant limits: its pull is best effort, and a
previously committed but failed push may not be retried when the next export
has no new changes. The wrapper checks the configured origin and upstream,
checks remote reachability, runs the installed engine, then acquires the shared
AB lock and rechecks configuration before reconciling pending commits.
It uses ordinary fast-forward push and independently rereads the remote.
Concurrent divergence remains `retry` for the next existing Store merge; the
wrapper never force-pushes or resets history. Child Git/SSH processes have
bounded lifetimes and are cleaned up through their own process group.

`last-round.json` records the actual attempt (`complete`, `retry`, `busy` or
`failed`). `last-success.json` is retained separately and includes its timestamp.
A service exit of 3 is an intentional busy/retry result, not a target-import
receipt. A round's published commit proves transport custody only. Import
counters show that this node ran the importer but do not bind a particular
other node's database to that commit.

For a real handoff, check the exact row on the receiving node:

```bash
python3 ~/.local/lib/agent-bridge/lan-sync/lan-memory-sync.py \
  --config ~/.config/agent-bridge/lan-sync.json verify \
  --key HANDOFF_KEY --expected SOURCE_PROOF_JSON
```

Generate the source proof with the same command without `--expected`. Only
the key, content hash, updated time, lifecycle status and opaque serialized
version vector travel in this proof, not the memory content. All those fields
must match. The database is opened read-only and explicitly closed. Ordinary
retrieval still respects project scope and lifecycle; this exact check is for
arrival, not a claim about retrieval quality or user acceptance.

The first live proof exposed an incorrect JSON assumption for version vectors.
The actual representation is compact text (`nodehex:counter,...`); the proof
now preserves it verbatim, and regression fixtures use the production format.
The original failure is retained in the execution report.

## Configuration and validation

The private config includes version 1, node name, wrapper, canonical database,
AB lock directory, receipt directory, and each channel's checkout, origin,
branch and timeout. Both fetch and push URLs must match the configured origin.
An additional cloud clone must inherit the original checkout's repository-local
`user.name` and `user.email`; cloning alone does not copy those settings. The
first cloud attempt exposed this omission, retained its staged export and failed
truthfully. The identity was copied within that checkout only before retry.
Every caller uses the installed wrapper; its effective DB/repo/lock overrides
must be checked before activation because a machine file can override env vars.
The actual child's reported checkout is also checked when available.

The helper does not modify wrapper, binary, credentials or production SQL.
Use a real-disk temporary directory for the regression suite:

```bash
python3 -W error::ResourceWarning -m unittest discover -s tests -p test_lan_memory_sync.py -v
```

The tests use actual temporary bare Git repositories, clones and SQLite,
plus a small fake sync child for failure branches. Existing ab-store regressions
separately cover same-key concurrency, disjoint edits, deletion propagation,
and same-second deletion ordering. Live validation separately checks actual
Mac↔Linux handoff arrival and the installed schedules. Isolated transport
acceptance blocks non-LAN Git SSH destinations; it does not disconnect the
owner's whole machine from the internet or count fixtures as user experience.

## Preservation and rollback

Before changing a checkout origin, hold AB's existing JSON sync lock, preserve
the complete Git config and bundle, and retain a SQLite backup made with the
backup API and checked with `quick_check`. Never raw-copy a running DB/WAL.
Release the shared lock before invoking AB sync. First history transfer is
separate from steady-state latency; the first Linux 20-second fetch deadline
expired, and the unchanged engine then completed alignment in 43.859 seconds.

Actual backup roots for this delivery:

- Linux: `/Data/.agent-bridge-state/lan-sync/backup-20260908/`
- Mac: `/Users/pallasting/Agent-Bridge-LAN/backup-20260908/`

To revert the transport and cadence: stop the LAN/cloud timers, let active sync
finish, then acquire the original AB sync lock. Restore `git-config.at-cutover`
to the original checkout's `.git/config`; retain its current working files,
commits and all databases. Restore the backed-up Linux sync service/timer or
Mac plist, release the lock, reload the scheduler and resume the old cadence.
Disable the new cloud timer when reverting Linux. Keep the LAN bare repository,
cloud clone, bundles and receipts for recovery. Do **not** restore the old
SQLite backup by default: it would discard valid work written after cutover.
The original sync engine can reconcile the current database back to the old
cloud transport.

Execution results and configuration fingerprints are in
`/Data/CascadeProjects/.analysis-reports/ab-lan-sync-20260908/`.
